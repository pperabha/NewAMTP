#!/usr/bin/env python3
"""Search 1.1 / 1.2 queries for the paper (32) experiments: queries_search_single_p32.jsonl

The same generator as build_v4.py (experiment_files, "Search 1.1 / 1.2" block), run on the unpacked dataset:
AND queries inside one domain, the k keywords of one anchor file (one of the first 10,000 files, so the query is never
empty at any size), 20 queries per k_Q per domain, seed 42, exact plaintext result size at every size. Only k_Q
changes: (32) uses k_Q in {1, 2, 4, 8, 16}.

    python3 datasets/arxiv/make_queries_p32.py                       # -> data_v4/queries_search_single_p32.jsonl
    python3 datasets/arxiv/make_queries_p32.py --check               # rebuild the v4 file (k_Q 1,2,5,10,15,20)
                                                                     # and compare it byte for byte

Reads documents.csv through baselines/amtp_dataset.py (--data or AMTP_DATA, default data/amtp_file_db_v4).
Standard library only.
"""
import argparse
import json
import os
import random
import sys
from bisect import bisect_left
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "baselines"))
import amtp_dataset as D  # noqa: E402

POINTS = [10_000, 25_000, 50_000, 75_000, 100_000, 125_000]
KQ_P32 = [1, 2, 4, 8, 16]
KQ_V4 = [1, 2, 5, 10, 15, 20]


class DomainIndex:
    """Plaintext index of one domain (position = 0-based doc_id order of its initial files), as in build_v4.py."""

    def __init__(self, docs):
        self.doc_ids = [d.doc_id for d in docs]
        self.doc_kws = [d.keywords for d in docs]
        post = defaultdict(list)
        for p, kws in enumerate(self.doc_kws):
            for k in kws:
                post[k].append(p)                       # increasing p -> sorted
        self.post = dict(post)
        self.n = len(docs)

    def positions(self, k):
        return set(self.post.get(k, ()))


def build_expr(shape, kw):
    return kw[0] if shape == "single" else {"op": shape, "args": list(kw)}


def expr_text(e):
    return '"%s"' % e if isinstance(e, str) else " AND ".join('"%s"' % k for k in e["args"])


def evaluate(e, idx):
    if isinstance(e, str):
        return idx.positions(e)
    return set.intersection(*(idx.positions(k) for k in e["args"]))


def counts_at(positions, points):
    s = sorted(positions)
    return {str(N): bisect_left(s, N) for N in points}


def single_queries(indexes, kqs, seed=42, queries_per_k=20, anchor_n=10_000, points=POINTS):
    """build_v4.experiment_files, block "Search 1.1 / 1.2", unchanged except for the k_Q list."""
    anchor_n = min(anchor_n, min(ix.n for ix in indexes.values()))
    qrng = random.Random("%d-queries" % seed)
    rows, qid = [], 0
    for dom, idx in indexes.items():
        for k in kqs:
            ok = [p for p in range(anchor_n) if len(idx.doc_kws[p]) >= k]
            if not ok:
                print("  warning: no anchor file with >= %d keywords in %s" % (k, dom))
                continue
            for _ in range(queries_per_k):
                p = ok[qrng.randrange(len(ok))]
                kw = qrng.sample(sorted(idx.doc_kws[p]), k)
                shape = "single" if k == 1 else "AND"
                e = build_expr(shape, kw)
                qid += 1
                rows.append({"query_id": "S1_%05d" % qid, "domain": dom, "kQ": k, "shape": shape,
                             "expression": e, "text": expr_text(e), "keywords": kw,
                             "source_doc": idx.doc_ids[p], "result_size": counts_at(evaluate(e, idx), points)})
    return rows


def dumps(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=None, help="unpacked dataset (default AMTP_DATA or data/amtp_file_db_v4)")
    ap.add_argument("--out", default=os.path.join(D.V4_DIR, "queries_search_single_p32.jsonl"))
    ap.add_argument("--check", action="store_true", help="rebuild the v4 file and compare it byte for byte")
    a = ap.parse_args()
    data = a.data or os.environ.get("AMTP_DATA")
    initial = D.load(data)["initial"]
    indexes = {dom: DomainIndex(initial[dom]) for dom in D.DOMAINS}
    if a.check:
        want = open(os.path.join(D.V4_DIR, "queries_search_single.jsonl"), encoding="utf-8").read()
        got = dumps(single_queries(indexes, KQ_V4))
        print("check: identical to queries_search_single.jsonl" if got == want else "check: DIFFERENT")
        return 0 if got == want else 1
    rows = single_queries(indexes, KQ_P32)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(rows))
    empty = sum(1 for q in rows if q["result_size"][str(POINTS[0])] == 0)
    print(f"-> {os.path.relpath(a.out, REPO)}: {len(rows)} queries (k_Q {KQ_P32}, {len(indexes)} domains), "
          f"empty at {POINTS[0]:,} files: {empty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
