"""Ablation benchmark: AMTP vs Static-MT vs Global-MT under skewed growth
(the shape of Experiment 4 in the report).

    python -m bench.ablation --source synthetic --n 5000          # smoke test
    python -m bench.ablation --source arxiv --n 100000 --runs 30  # shared arXiv dataset (dataset-v4)

One update batch of --batch-size operations is ONE epoch (b = batch size, recorded as column "b"
and in manifest.json). Sizes follow baselines/wire_sizes.py (binary, the rule of every scheme).
    python -m bench.ablation --source enron --enron ./maildir --n 100000 --runs 30

Fairness built in:
  * every variant runs the same engine code; only the partition policy differs
  * update cost = the whole batch on the Cloud Server: placing / removing every file (slot Merkle paths,
    postings) AND the commit (adapt, PAPC / IMT / partition-tree repair). Timing only the commit would leave
    out the slot-tree work, whose path is longer in a big partition (Global-MT, a bloated Static-MT one);
    hash_calls / hash_bytes count the same whole batch
  * same seed -> same initial documents, update stream and queries for all variants
  * AMTP and Static-MT start from the identical partition layout
  * θ values are inputs fixed before the run (tune them on a separate seed)
  * correctness gates: incremental R_D must equal a full rebuild, and every
    query response must pass the 7 Phase 5 checks; otherwise the run aborts
  * raw per-batch / per-query rows are written to CSV; nothing is averaged away
"""
import argparse
import csv
import gc
import json
import os
import platform
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amtp.core import boolean                                    # noqa: E402
from amtp.core.hashing import HashCounter                        # noqa: E402
from amtp.dht import DHT                                          # noqa: E402
from amtp.engine import Engine                                    # noqa: E402
from amtp.index import and_plan_greedy_on, and_prune_on, part_leaf_on, part_results_on, set_gamma_v   # noqa: E402
from amtp.server import build_response                            # noqa: E402
from amtp.user import DataUser                                    # noqa: E402
from amtp.variants import PLACEMENTS, AdaptivePolicy, GlobalPolicy, StaticPolicy   # noqa: E402
from bench.workload import REPO_ROOT                             # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "baselines"))
import wire_sizes as W                                            # noqa: E402
from bench.workload import (arxiv_docs, arxiv_loader, enron_docs, hot_delete_stream, keyword_bands,   # noqa: E402
                            make_queries, synthetic_docs, update_stream)

DOMAIN = "A"
VARIANTS = ("AMTP", "Static-MT", "Global-MT", "Global-MT(v)")


def build(variant, docs, a):
    if variant == "Global-MT":
        eng = Engine(DOMAIN, GlobalPolicy(a.buckets))
    elif variant == "Global-MT(v)":
        eng = Engine(DOMAIN, GlobalPolicy(a.buckets, versioned=True))
    else:
        eng = Engine(DOMAIN, AdaptivePolicy(a.buckets, a.theta_min, a.theta_max, a.placement))
    for d in docs:
        eng.insert(d.cid, d.keys, d.bucket)
    eng.commit()
    if variant == "Static-MT":                       # same start as AMTP, then frozen
        eng.policy = StaticPolicy(a.buckets, a.theta_min, a.theta_max, a.placement)
    return eng


def run_queries(eng, queries, dht, verifier):
    state = eng.snapshot()
    if state.R_D != eng.R_D:
        raise SystemExit("CORRECTNESS GATE FAILED: incremental R_D != full rebuild")
    rows = []
    for i, (shape, ast) in enumerate(queries):
        b_q = boolean.canonical(ast)
        nonce = f"{i:032x}"
        gc.disable()                                    # as in every other suite: no GC pause in a timing
        try:
            t0 = time.perf_counter()
            resp = build_response(state, b_q, nonce, dht)
            server_ms = (time.perf_counter() - t0) * 1000
            resp = json.loads(json.dumps(resp))
            ctx = {"domain": DOMAIN, "B_Q": json.loads(json.dumps(b_q)), "epoch": state.epoch,
                   "nonce": nonce, "R_D": state.R_D.hex()}
            rep = verifier.verify(ctx, resp)
        finally:
            gc.enable()
        if not rep["accepted"]:
            raise SystemExit(f"CORRECTNESS GATE FAILED: honest query rejected at {rep['failed']}")
        ev = resp["proof"]["evidence"]
        rows.append({
            "shape": shape, "results": len(resp["R_ct"]),
            "keys_present": sum(e["status"] == "present" for e in ev),
            "partitions_covered": len(resp["proof"]["partitions"]),
            "server_ms": round(server_ms, 4), "verify_ms": rep["verify_ms"],
            "proof_bytes": W.amtp_proof_bytes(resp["proof"]), "response_bytes": W.amtp_response_bytes(resp),
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["synthetic", "arxiv", "enron"], default="synthetic")
    ap.add_argument("--data", help="arXiv dataset folder amtp_file_db/ (default <repo>/data/amtp_file_db_v4 or AMTP_DATA)")
    ap.add_argument("--enron", help="path to the Enron maildir/ folder")
    ap.add_argument("--n", type=int, default=5000, help="initial number of documents")
    ap.add_argument("--buckets", type=int, default=16, help="workload groups (e.g. mailbox owners)")
    ap.add_argument("--theta-max", type=int, default=256)
    ap.add_argument("--theta-min", type=int, default=64)
    ap.add_argument("--placement", choices=PLACEMENTS, default=os.environ.get("AMTP_PLACEMENT", "fill"),
                    help="where a new file goes (amtp/variants.py): least = least occupied partition of its bucket, "
                         "fill = fullest partition below θ_max (same rule for AMTP and Static-MT); default fill (the paper's rule) or AMTP_PLACEMENT")
    ap.add_argument("--batches", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--skews", default="0,0.5,0.8,0.95",
                    help="fraction of inserts forced into the hot bucket(s)")
    ap.add_argument("--hot", type=int, default=1, help="number of hot buckets")
    ap.add_argument("--delete-frac", type=float, default=0.1, help="phase 1: share of ops that delete a random file")
    ap.add_argument("--fresh-source", choices=["pool", "initial"], default="pool",
                    help="arxiv: inserted files from the insert pool, or the next initial files after the first --n "
                         "(lets a run insert as many files as it starts with)")
    ap.add_argument("--query-every", type=int, default=0,
                    help="also measure the queries and the layout every k batches (time series); 0 = only at the end")
    ap.add_argument("--hot-delete-frac", type=float, default=0.0,
                    help="phase 2 (split/merge test): then delete this share of the hot buckets' live files, "
                         "--batch-size per batch, so hot partitions shrink below θ_min (0 = no phase 2)")
    ap.add_argument("--queries-per-shape", type=int, default=10)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--global-versioned", action="store_true",
                    help="also run Global-MT(v): one partition with version bumps")
    ap.add_argument("--variants", default=None,
                    help="comma list of the variants to run, e.g. \"Global-MT(v),Global-MT\" (default: AMTP, "
                         "Static-MT, Global-MT, + Global-MT(v) with --global-versioned). The documents, update stream "
                         "and queries come from the seed only, so a variant run alone sees the same workload")
    ap.add_argument("--out", default="results")
    ap.add_argument("--gamma-no-v", action="store_true",
                    help="γ = H(PID ‖ H(Enc(L))) without the partition version v (study B4; same as AMTP_GAMMA_V=0)")
    a = ap.parse_args()
    os.environ["AMTP_PLACEMENT"] = a.placement           # recorded in every manifest
    if a.gamma_no_v or os.environ.get("AMTP_GAMMA_V", "1") == "0":
        os.environ["AMTP_GAMMA_V"] = "0"                  # recorded in every manifest
        set_gamma_v(False)

    variants = ["AMTP", "Static-MT", "Global-MT"] + (["Global-MT(v)"] if a.global_versioned else [])
    if a.variants:
        variants = [v.strip() for v in a.variants.split(",") if v.strip()]
        unknown = [v for v in variants if v not in VARIANTS]
        if unknown or not variants:
            ap.error(f"--variants: unknown {unknown}; choose from {', '.join(VARIANTS)}")
    skews = [float(s) for s in a.skews.split(",")]
    os.makedirs(a.out, exist_ok=True)
    manifest = {"args": vars(a), "b": a.batch_size, "placement": a.placement, "gamma_v": os.environ.get("AMTP_GAMMA_V", "1") != "0",
                # query flags (read from the environment by amtp/index.py; they change only the per-batch queries)
                "and_prune": and_prune_on(), "part_results": part_results_on(), "and_greedy": and_plan_greedy_on(), "part_leaf": part_leaf_on(),
                "python": sys.version, "platform": platform.platform(),
                "machine": platform.machine(), "processor": platform.processor(),
                "cpus": os.cpu_count(), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    if a.source == "arxiv":                     # same git commit / machine record as the other suites
        info = json.load(open(arxiv_loader().write_manifest(os.path.join(a.out, "manifest.csv"))))
        os.remove(os.path.join(a.out, "manifest.manifest.json"))
        manifest.update({k: info[k] for k in ("command", "git_commit", "git_dirty", "dataset", "machine")})
    with open(os.path.join(a.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    files = {k: open(os.path.join(a.out, f"{k}.csv"), "w", newline="") for k in
             ("updates", "layout", "queries")}
    writers = {}
    verifier = DataUser("bench", "bench", "", [], {}, {})
    summary = {}

    for run in range(a.runs):
        seed = a.seed + run
        extra = a.batches * a.batch_size
        if a.source == "arxiv":
            docs = arxiv_docs(a.n, a.buckets, extra, a.data, fresh_source=a.fresh_source)   # same W(d) as baselines
        elif a.source == "enron":
            if not a.enron:
                raise SystemExit("--enron PATH is required with --source enron")
            docs = enron_docs(a.enron, a.n + extra, a.buckets, seed)
        else:
            docs = synthetic_docs(a.n + extra, a.buckets, seed=seed)
        initial, fresh = docs[:a.n], docs[a.n:]
        dht = DHT()
        for d in docs:
            dht.put(d.cid, d.ct)
        queries = make_queries(keyword_bands(initial), a.queries_per_shape, seed)
        hot = list(range(a.hot))

        for si, skew in enumerate(skews):
            stream = update_stream(initial, fresh, a.batches, a.batch_size, skew, hot,
                                   a.delete_frac, seed * 1000 + si)
            phases = ["insert"] * len(stream)
            if a.hot_delete_frac > 0:
                drops = hot_delete_stream(initial, stream, a.batch_size, hot, a.hot_delete_frac,
                                          seed * 1000 + si + 500)
                stream, phases = stream + drops, phases + ["hot_delete"] * len(drops)
            for variant in variants:
                eng = build(variant, initial, a)
                tag = {"run": run, "seed": seed, "variant": variant, "skew": skew, "b": a.batch_size}
                splits = merges = 0
                last_insert = phases.count("insert") - 1

                def checkpoint(bi, final=False):
                    lay = _layout(eng)
                    _write(writers, files, "layout", {**tag, "batch": bi, "phase": phases[bi] if phases else "",
                                                      **lay, "splits": splits, "merges": merges})
                    for row in run_queries(eng, queries, dht, verifier):
                        _write(writers, files, "queries", {**tag, "batch": bi, **row})
                        if final:
                            for k in ("verify_ms", "server_ms", "proof_bytes"):
                                summary[(variant, skew)].setdefault(k, []).append(row[k])
                    return lay

                for bi, ops in enumerate(stream):
                    c0, b0 = HashCounter.snapshot()
                    gc.disable()                        # as in every other suite: no GC pause in a timing
                    try:
                        t0 = time.perf_counter()
                        for op in ops:
                            if op[0] == "ins":
                                eng.insert(op[1].cid, op[1].keys, op[2])
                            else:
                                eng.delete(op[1])
                        st = eng.commit()
                        t1 = time.perf_counter()
                    finally:
                        gc.enable()
                    c1, b1 = HashCounter.snapshot()
                    st.update(commit_ms=st["update_ms"], update_ms=(t1 - t0) * 1000,      # the whole batch
                              hash_calls=c1 - c0, hash_bytes=b1 - b0)
                    splits += st["splits"]
                    merges += st["merges"]
                    _write(writers, files, "updates", {**tag, "batch": bi, "phase": phases[bi], **_round(st)})
                    summary.setdefault((variant, skew), {}).setdefault("update_ms", []).append(st["update_ms"])
                    summary[(variant, skew)].setdefault("restructure_ms", []).append(st["restructure_ms"])
                    summary[(variant, skew)].setdefault("hash_calls", []).append(st["hash_calls"])
                    summary[(variant, skew)].setdefault("hash_bytes", []).append(st["hash_bytes"])
                    if bi < len(stream) - 1 and ((a.query_every and (bi + 1) % a.query_every == 0)
                                                 or (a.hot_delete_frac > 0 and bi == last_insert)):
                        checkpoint(bi)
                lay = checkpoint(len(stream) - 1, final=True)
                summary[(variant, skew)].setdefault("max_partition", []).append(lay["max_partition"])
                print(f"run {run} skew {skew:<4} {variant:<12} partitions={lay['partitions']:<5} "
                      f"max={lay['max_partition']:<6} splits={splits} merges={merges}", flush=True)

    for fh in files.values():
        fh.close()
    _print_summary(summary, variants, skews, a.out)


def _layout(eng):
    """Engine.layout() + the mean partition size (live files per partition)."""
    lay = eng.layout()
    lay["mean_partition"] = round(statistics.mean(eng.live.values()), 2) if eng.live else 0
    return lay


def _round(st):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()}


def _write(writers, files, name, row):
    if name not in writers:
        writers[name] = csv.DictWriter(files[name], fieldnames=list(row))
        writers[name].writeheader()
    writers[name].writerow(row)


def _print_summary(summary, variants, skews, out):
    cols = ["update_ms", "restructure_ms", "hash_calls", "hash_bytes", "server_ms", "verify_ms", "proof_bytes",
            "max_partition"]
    lines = ["| skew | variant | " + " | ".join(f"mean {c}" for c in cols) + " |",
             "|---|---|" + "---|" * len(cols)]
    for skew in skews:
        for v in variants:
            vals = summary[(v, skew)]
            lines.append(f"| {skew} | {v} | " + " | ".join(
                f"{statistics.mean(vals[c]):.3f}" if c.endswith("_ms")
                else f"{statistics.mean(vals[c]):.0f}" for c in cols) + " |")
    text = "\n".join(lines)
    print("\n" + text)
    with open(os.path.join(out, "summary.md"), "w") as fh:
        fh.write(text + "\n\nMeans over every batch of every run (paper (32): values averaged over the runs; "
                 "restructure_ms = split / merge and relocation inside the commit). Raw rows: updates.csv.\n")


if __name__ == "__main__":
    main()
