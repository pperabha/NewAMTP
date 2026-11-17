"""Time AMTP's keyword extraction (Phase 1, Step 3: W(d) = {Norm(w) : w in Extract(d)}) apart from the other experiments.

Why apart: in the Search / Update experiments every scheme (AMTP, Chen, Du, SE-COLLAB) uses the same keywords
from documents.csv (no scheme extracts them itself), so the compared results exclude keyword extraction; this script
reports that cost separately (it is the DO's local work before upload, done once per document).

Method
  - documents = amtp_dataset.sample(N), the same set as the other experiments (+ the insert pool with --pool)
  - read the .txt files first (I/O not timed), then time only extract_keywords() = tokenise + Norm + RAKE
    (+ chunking for long documents)
  - garbage collector off while timing, warm-up runs not recorded, --repeats > 1 takes each document's median
  - check that the extracted keywords equal the keywords column of documents.csv (match_csv): must be 100%
  - the total time of each N in --sizes uses the same documents as sample(N) (the first N/4 files of each domain)

Output (folder --out)
  amtp_extraction_raw.csv      one row per document
  amtp_extraction_summary.csv  per domain and overall: ms per document (mean/median/std/p95/min/max), docs/s,
                               words per document
  amtp_extraction_by_n.csv     total extraction time of the whole document set for each N
  amtp_extraction_meta.json    machine spec + parameters (for the Experimental Setup)

Examples (run from amtp_code/)
  python -m bench.extraction --n 200000 --pool --sizes 10000 50000 100000 200000
  python -m bench.extraction --n 4000 --repeats 3                 # quick try
  python -m bench.extraction --data ~/amtp_file_db                # dataset elsewhere
"""
import argparse
import csv
import gc
import json
import os
import platform
import statistics as st
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amtp import nlp  # noqa: E402
from amtp.nlp import extract_keywords  # noqa: E402
from bench.workload import arxiv_loader  # noqa: E402


def read_text(data_dir, file_path):
    """Read a .txt file the same way as when the dataset was built (utf-8, undecodable bytes skipped); not timed."""
    with open(os.path.join(data_dir, file_path), "rb") as f:
        return f.read().decode("utf-8", "ignore")


def stats(ms):
    s = sorted(ms)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return {"extract_ms": round(st.mean(s), 4), "extract_ms_median": round(st.median(s), 4),
            "extract_ms_std": round(st.pstdev(s), 4), "extract_ms_p95": round(p95, 4),
            "extract_ms_min": round(s[0], 4), "extract_ms_max": round(s[-1], 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200_000, help="initial number of documents to measure (at most 500,000 = 4 domains x 125,000)")
    ap.add_argument("--sizes", type=int, nargs="*", default=None, help="N values that get a total time (each <= --n)")
    ap.add_argument("--domains", nargs="+", default=None)
    ap.add_argument("--pool", action="store_true", help="also measure the insert pool (the new documents of the update experiment)")
    ap.add_argument("--repeats", type=int, default=1, help="timed runs per document (median used)")
    ap.add_argument("--warmup", type=int, default=200, help="documents run first to warm up (not recorded)")
    ap.add_argument("--data", default=None, help="amtp_file_db folder")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    ds = arxiv_loader()
    data_dir = os.path.abspath(os.path.expanduser(a.data or ds.DEFAULT_DATA))
    domains = a.domains or ds.DOMAINS
    args = (nlp.THETA_DOC, nlp.L_CH, nlp.L_OV, nlp.KAPPA, nlp.MAX_WORDS)   # the same values used to build dataset-v4

    docs = list(ds.sample(a.n, domains, data_dir))
    if a.pool:
        docs += [d for d in ds.insert_pool(domains, data_dir)]
    print(f"dataset: {data_dir}\n  {len(docs)} documents, params theta_doc={args[0]} L_ch={args[1]} L_ov={args[2]} "
          f"kappa={args[3]} max_words={args[4]}, repeats={a.repeats}")

    texts = [read_text(data_dir, d.file_path) for d in docs]      # I/O not timed
    for t in texts[:a.warmup]:                                     # warm-up
        extract_keywords(t, *args)

    rows = []
    gc_was = gc.isenabled()
    gc.disable()
    t_start = time.perf_counter()
    try:
        for i, (d, text) in enumerate(zip(docs, texts), 1):
            runs = []
            for _ in range(a.repeats):
                t0 = time.perf_counter()
                W, ext = extract_keywords(text, *args)
                runs.append((time.perf_counter() - t0) * 1e3)
            rows.append({"doc_id": d.doc_id, "domain": d.domain, "is_initial": int(d.is_initial),
                         "n_words": ext["n_words"], "n_chars": len(text), "mode": ext["mode"],
                         "n_chunks": len(ext["chunks"]), "n_keywords": len(W),
                         "extract_ms": round(st.median(runs), 5), "match_csv": int(W == list(d.keywords))})
            if i % 20000 == 0:
                gc.collect()
                print(f"  {i}/{len(docs)}  ({time.perf_counter() - t_start:.0f}s)", flush=True)
    finally:
        if gc_was:
            gc.enable()

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "amtp_extraction_raw.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    groups = [("ALL-initial", [r for r in rows if r["is_initial"]])]
    groups += [(f"{dom}-initial", [r for r in rows if r["is_initial"] and r["domain"] == dom]) for dom in domains]
    if a.pool:
        groups += [("ALL-pool", [r for r in rows if not r["is_initial"]])]
    summary = []
    for name, g in groups:
        if not g:
            continue
        ms = [r["extract_ms"] for r in g]
        summary.append({"group": name, "docs": len(g), **stats(ms),
                        "total_s": round(sum(ms) / 1e3, 3), "docs_per_s": round(len(g) / (sum(ms) / 1e3), 1),
                        "words_per_doc": round(st.mean(r["n_words"] for r in g), 1),
                        "keywords_per_doc": round(st.mean(r["n_keywords"] for r in g), 2),
                        "chunked_docs": sum(r["mode"] == "chunked" for r in g),
                        "match_csv_pct": round(100 * sum(r["match_csv"] for r in g) / len(g), 3)})
    with open(os.path.join(a.out, "amtp_extraction_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    by_n = []
    for n in sorted(set(a.sizes or [])):
        if n > a.n:
            print(f"  ! skip N={n} (> --n {a.n})")
            continue
        ids = {d.doc_id for d in ds.sample(n, domains, data_dir)}
        ms = [r["extract_ms"] for r in rows if r["doc_id"] in ids]
        by_n.append({"N": n, "docs": len(ms), "total_extract_s": round(sum(ms) / 1e3, 3), **stats(ms)})
    if by_n:
        with open(os.path.join(a.out, "amtp_extraction_by_n.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(by_n[0]))
            w.writeheader()
            w.writerows(by_n)

    meta = {
        "what": "AMTP Phase 1 keyword extraction (Extract + Norm), timed separately from search/update experiments",
        "date": datetime.now().isoformat(timespec="seconds"),
        "machine": {"platform": platform.platform(), "processor": platform.processor() or platform.machine(),
                    "cpu_count": os.cpu_count(), "python": sys.version.split()[0]},
        "params": {"theta_doc": args[0], "L_ch": args[1], "L_ov": args[2], "kappa": args[3], "max_phrase_words": args[4]},
        "dataset": getattr(ds, "DATASET_TAG", ""), "data_dir": data_dir, "domains": domains, "n": a.n, "pool": a.pool,
        "repeats": a.repeats, "warmup_docs": a.warmup, "timer": "time.perf_counter, gc disabled, file I/O excluded",
        "single_process": True,
    }
    with open(os.path.join(a.out, "amtp_extraction_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    for s in summary:
        print(f"{s['group']:12s} docs={s['docs']:6d}  mean={s['extract_ms']:.3f} ms  median={s['extract_ms_median']:.3f}  "
              f"p95={s['extract_ms_p95']:.3f}  total={s['total_s']:.1f}s  match_csv={s['match_csv_pct']}%")
    for b in by_n:
        print(f"N={b['N']:7d}  total extraction = {b['total_extract_s']:.2f}s")
    print(f"written -> {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
