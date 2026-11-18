"""Update cost with the Root Anchor on a public chain: the Phase 2 protocol of bench/experiments.py exp3
(same Corpus, Engine, CloudServer.prepare_update, Validator) on the real dataset, with every transition sent
to the RootAnchor contract (AMTP_ANCHOR_ADDR in <repo>/.env).

    AMTP_DATA=/path/to/amtp_file_db_v4 .venv/bin/python chain/sepolia_bench.py --n 100000 --b 1 10 100 1000 \
        --warmup 3 --reps 15 --deploy

For each domain (D1..D4, each its own dataset domain): bulk-load n files, register the genesis root, anchor
epoch 1. Then for every b: warmup + reps rounds; a round inserts b fresh files (insert pool) as one epoch and
deletes them again as the next epoch, on one domain, the domains taking turns (the Global Root on the contract
changes with every domain). Per epoch it times
  request   owner builds b signed requests (tokens + σ_op, Ed25519)
  server    CS prepare_update
  validate  owner Validator replays the update and signs σ_root (secp256k1, the domain's chain key)
  anchor    send the contract transaction -> receipt with AMTP_CONFIRMATIONS confirmations (default 1)
  final     send -> the block is finalized (polled; 'finalized' block tag)
and reads (e*, R_D) back at the latest block after every epoch (must equal the engine's root).
Writes chain/runs/sepolia_bench_<time>.csv (one row per epoch) and .json (setup, summary, every tx).
"""
import argparse
import csv
import json
import os
import platform
import statistics as st
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "amtp_code"))
sys.path.insert(0, HERE)

from sepolia import EXPLORERS, read_env                                 # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"])
    ap.add_argument("--n", type=int, default=10_000, help="files bulk-loaded per domain")
    ap.add_argument("--b", type=int, nargs="+", default=[100], help="signed requests per epoch (one or more)")
    ap.add_argument("--warmup", type=int, default=0, help="unmeasured rounds per b (still anchored)")
    ap.add_argument("--reps", type=int, default=4, help="measured rounds per b (a round = insert + delete epoch)")
    ap.add_argument("--policy", choices=["adaptive", "static"], default="adaptive",
                    help="adaptive = AMTP (split / merge); static = partitions frozen, as bench exp3")
    ap.add_argument("--deploy", action="store_true", help="deploy a fresh RootAnchor for this run")
    ap.add_argument("--data", default=None)
    ap.add_argument("--poll", type=float, default=4.0, help="seconds between finalized-block polls")
    ap.add_argument("--out", default=os.path.join(HERE, "runs"))
    ap.add_argument("--local", action="store_true", help="in-process chain (eth-tester) to check the script; no finality")
    a = ap.parse_args()

    from eth_account import Account
    from web3 import Web3
    from amtp.chain_anchor import ChainAnchor
    from amtp.engine import Engine
    from amtp.server import CloudServer
    from amtp.validator import Validator
    from amtp.variants import AdaptivePolicy, StaticPolicy
    from bench.experiments import Corpus

    if a.local:
        chain = ChainAnchor.local()
        w3, cid = chain.w3, chain.chain_id
        explorer = "local"
    else:
        env = read_env()
        w3 = Web3(Web3.HTTPProvider(env["AMTP_RPC"], request_kwargs={"timeout": 60}))
        cid = w3.eth.chain_id
        if cid not in EXPLORERS or not (a.deploy or env.get("AMTP_ANCHOR_ADDR")):
            raise SystemExit("needs a known test network and AMTP_ANCHOR_ADDR (chain/sepolia.py deploy)")
        owners = {d: Account.from_key(env[f"AMTP_OWNER_KEY_{d}"]) for d in a.domains}
        chain = ChainAnchor(w3, Account.from_key(env["AMTP_ADMIN_KEY"]),
                            address=None if a.deploy else env["AMTP_ANCHOR_ADDR"],
                            owner_keys=owners, confirmations=int(env.get("AMTP_CONFIRMATIONS", "1")))
        explorer = f"{EXPLORERS[cid]}/address/{chain.address}"
    already = [d for d in a.domains if chain.contract.functions.ownerOf(d.encode()).call() != "0x" + "0" * 40]
    if already:
        raise SystemExit(f"{already} already registered on {chain.address}: deploy a new contract "
                         f"(chain/sepolia.py deploy --again) for a new run")
    print(f"RootAnchor {chain.address}  {explorer}", flush=True)

    cfg = SimpleNamespace(data=a.data, buckets=16, theta_min=16, theta_max=64, placement="fill")
    corpus = Corpus(cfg)
    server = CloudServer()
    doms = {}
    for d in a.domains:                                    # bulk load + genesis + epoch 1, as bench Domain
        t0 = time.perf_counter()
        src = corpus.D.sample(a.n, [d], a.data)
        signer = __import__("amtp.core.crypto", fromlist=["Signer"]).Signer()     # σ_op (Ed25519)
        root = chain.root_signer(d)                                                 # σ_root (chain key)
        server.register_query_key(d, corpus.keys_for(d).k_a)
        eng = Engine(d, AdaptivePolicy(cfg.buckets, cfg.theta_min, cfg.theta_max, cfg.placement))
        chain.register_domain(d, root.public, eng.R_D)                            # R^(0)
        cids = []
        for doc in src:
            c_id, ct, keys, bucket = corpus.encrypt(doc, d)
            server.store_ciphertext(c_id, ct)
            eng.insert(c_id, keys, bucket)
            cids.append(c_id)
        eng.commit()
        _, prev = chain.latest(d, block="latest")
        from amtp.anchor import transition_message
        chain.submit(d, eng.epoch, eng.R_D, root.sign(transition_message(d, eng.epoch, eng.R_D, prev)), prev=prev)
        server.store_state(eng.snapshot())
        docs = dict(zip([x.doc_id for x in src], cids))
        server.engines[d], server.owner_keys[d], server.docs[d] = eng, [signer.public], dict(docs)
        if a.policy == "static":                         # as bench Protocol for exp3: partitions frozen
            eng.policy = StaticPolicy(cfg.buckets, cfg.theta_min, cfg.theta_max, cfg.placement)
        val = Validator.bootstrap(d, root, eng.policy, eng, docs, [signer.public])
        doms[d] = SimpleNamespace(eng=eng, signer=signer, val=val, pool=corpus.D.insert_pool([d], a.data), cursor=0)
        print(f" {d}: n={a.n} partitions={eng.layout()['partitions']} genesis + epoch 1 anchored "
              f"({time.perf_counter() - t0:.0f} s)", flush=True)

    rows, pending = [], []                                 # pending: (row, send time) waiting for finality
    names = list(doms)
    turn = 0
    for b, rnd, op in ((b, rnd, op) for b in a.b for rnd in range(a.warmup + a.reps) for op in ("insert", "delete")):
        if True:
            d = names[turn % len(names)]
            if op == "delete":
                turn += 1
            dom = doms[d]
            eng = dom.eng
            eng.ops_per_epoch = b
            if op == "insert":
                dom.batch = [dom.pool[(dom.cursor + i) % len(dom.pool)] for i in range(b)]
                dom.cursor = (dom.cursor + b) % len(dom.pool)
                dom.enc = [corpus.encrypt_fresh(x, d) for x in dom.batch]       # file encryption: not counted
            tr = time.perf_counter()
            if op == "insert":
                reqs = [corpus.insert_request(e, x, d, eng.epoch, dom.signer) for x, e in zip(dom.batch, dom.enc)]
            else:
                reqs = [Corpus.delete_request(x.doc_id, e[0], d, eng.epoch, dom.signer)
                        for x, e in zip(dom.batch, dom.enc)]
            t0 = time.perf_counter()
            prop = server.prepare_update(d, reqs)
            t1 = time.perf_counter()
            sig = dom.val.check(prop, reqs)
            t2 = time.perf_counter()
            sent_wall = time.time()
            chain.submit(d, prop["epoch_new"], prop["R_new"], sig, prop["delta"], prev=prop["R_old"])
            t3 = time.perf_counter()
            dom.val.advance()
            server.finalize_update(d, snapshot=False)
            tx = chain.txs[-1]
            tq = time.perf_counter()
            e_read, r_read = chain.latest(d, block="latest")
            read_ms = (time.perf_counter() - tq) * 1e3
            if (e_read, r_read) != (eng.epoch, eng.R_D):
                raise SystemExit(f"CORRECTNESS GATE FAILED: chain has ({e_read}, {r_read.hex()[:12]}) for {d}")
            row = {"domain": d, "epoch": eng.epoch, "op": op, "b": b, "round": rnd, "warmup": rnd < a.warmup,
                   "request_ms": (t0 - tr) * 1e3, "server_ms": (t1 - t0) * 1e3, "validate_ms": (t2 - t1) * 1e3,
                   "anchor_ms": (t3 - t2) * 1e3, "update_ms": (t3 - tr) * 1e3,
                   "update_without_anchor_ms": (t2 - tr) * 1e3, "read_latest_ms": read_ms,
                   "gas": tx.gas, "block": tx.block, "tx": tx.tx, "final_s": None}
            rows.append(row)
            pending.append((row, sent_wall))
            print(f"  b={b:<4} {d} epoch {eng.epoch:>3} {op:<6}{' (warm-up)' if rnd < a.warmup else ''} protocol {row['update_without_anchor_ms']:7.0f} ms + "
                  f"anchor {row['anchor_ms'] / 1e3:5.1f} s  gas {tx.gas}  block {tx.block}", flush=True)
            _poll_final(w3, pending, a.local)

    print("waiting until every transaction is in a finalized block ...", flush=True)
    while pending:
        time.sleep(a.poll)
        _poll_final(w3, pending, a.local)
    final_reads = []
    for d in doms:
        tq = time.perf_counter()
        e_f, r_f = chain.latest(d, block="latest" if a.local else "finalized")
        final_reads.append((time.perf_counter() - tq) * 1e3)
        if (e_f, r_f) != (doms[d].eng.epoch, doms[d].eng.R_D):
            raise SystemExit(f"CORRECTNESS GATE FAILED: finalized root of {d} differs")

    keys = ("request_ms", "server_ms", "validate_ms", "update_without_anchor_ms", "anchor_ms", "update_ms",
            "read_latest_ms", "gas", "final_s")
    meas = [r for r in rows if not r["warmup"]]
    by = {}
    for b in a.b:
        for op in ("insert", "delete"):
            g = [r for r in meas if r["b"] == b and r["op"] == op]
            by[f"b{b}_{op}"] = {**{k: st.median(r[k] for r in g) for k in keys},
                               "anchor_ms_max": max(r["anchor_ms"] for r in g),
                               "final_s_max": max(r["final_s"] for r in g), "epochs": len(g)}
    summary = {k: st.median(r[k] for r in meas) for k in ("anchor_ms", "final_s", "gas", "read_latest_ms")}
    summary.update(anchor_ms_max=max(r["anchor_ms"] for r in meas), final_s_max=max(r["final_s"] for r in meas),
                   read_finalized_ms=st.median(final_reads), epochs=len(meas), by_b_op=by)
    stamp = time.strftime("%Y%m%d_%H%M%S") + ("_local" if a.local else "")
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, f"sepolia_bench_{stamp}")
    with open(base + ".csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                                capture_output=True, text=True).stdout.strip())
    meta = {"command": " ".join(sys.argv), "git_commit": commit, "git_dirty": dirty, "chain_id": cid,
            "contract": chain.address, "explorer": explorer, "confirmations": chain.confirmations,
            "domains": a.domains, "n_per_domain": a.n, "b": a.b, "warmup": a.warmup, "reps": a.reps,
            "policy": a.policy,
            "theta": [cfg.theta_min, cfg.theta_max], "placement": cfg.placement,
            "machine": platform.platform(), "python": platform.python_version(),
            "setup_txs": [t.__dict__ for t in chain.txs if t.tx not in {r["tx"] for r in rows}],
            "summary_median": summary}
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    for key, v in by.items():
        print(f"  {key:<14} protocol {v['update_without_anchor_ms']:8.0f} ms  anchor {v['anchor_ms'] / 1e3:5.1f} s "
              f"(max {v['anchor_ms_max'] / 1e3:5.1f})  finalized {v['final_s']:5.0f} s  gas {v['gas']:.0f}")
    print("all: anchor median {anchor_ms:.0f} ms (max {anchor_ms_max:.0f}), finalized {final_s:.0f} s (max {final_s_max:.0f}), "
          "gas {gas:.0f}, read latest {read_latest_ms:.0f} ms, read finalized {read_finalized_ms:.0f} ms".format(**summary))
    print(f"-> {base}.csv / .json")


def _poll_final(w3, pending, local=False):
    """Fill final_s (send -> its block is finalized) for every pending row whose block is now finalized.
    Polled after every epoch (~ one block) and then every --poll seconds."""
    if not pending:
        return
    fin = w3.eth.block_number if local else w3.eth.get_block("finalized")["number"]
    now = time.time()
    for item in list(pending):
        row, sent = item
        if row["block"] <= fin:
            row["final_s"] = now - sent
            pending.remove(item)


if __name__ == "__main__":
    main()
