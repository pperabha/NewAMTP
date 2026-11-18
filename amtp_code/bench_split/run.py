"""Run a bench.experiments suite with the server's search measured on its own (bench_split/search_only.py).

    python -m bench_split.run search1  --reps 15 --warmup 3 --out <dir>
    python -m bench_split.run xsearch  --reps 15 --warmup 3 --out <dir>
    python -m bench_split.run xdomains --reps 15 --warmup 3 --x-kq 4 --shapes AND --out <dir>

Same arguments, flags (AMTP_PLACEMENT, AMTP_AND_PRUNE, ...), datasets, queries and CSV as bench.experiments. The only
difference: every measured query also runs the search alone, in three forms, in the same repetition, right before
the full query (bench.experiments.run_query, unchanged), and adds these columns (ms, mean / _median / _std):
    plain:            search_lookup, search_sets, search_eval, search_fetch,
                      server_search = lookup + sets + eval, server_search_fetch = + fetch (as SE-COLLAB's search_core)
    partition-first:  pf_lookup, pf_focus, pf_sets, pf_eval, pf_fetch, server_search_pf, server_search_pf_fetch
    fast (index):     fast_lookup, fast_focus, fast_sets, fast_eval, fast_fetch, server_search_fast,
                      server_search_fast_fetch
The search index of the fast form is built once per snapshot before any timing (setup); its build time, size and
number of keywords go to <out>/search_index_<suite>.json. Every other column is the one bench.experiments writes. A query
whose search-only files (any form) differ from the full response stops the run (correctness gate). No file of
amtp/ or bench/ is changed: run_query is wrapped here.
"""
import atexit
import json
import os
import sys
import weakref

from amtp.core import boolean
from bench import experiments as E
from bench_split.search_only import SearchIndex, search_fast, search_only

_full_query = E.run_query
_INDEX = {}          # id(state) -> (weak reference to the snapshot, SearchIndex): one index per snapshot, dropped
#                      with it (the suites free a snapshot after each size; the index must not keep it alive)
_STATS = []
_CALLS = [0]


def _index_for(state, domain):
    key = id(state)
    ent = _INDEX.get(key)
    if ent is None or ent[0]() is not state:
        idx = SearchIndex(state)
        _INDEX[key] = (weakref.ref(state, lambda _, k=key: _INDEX.pop(k, None)), idx)
        _STATS.append({"domain": domain, "epoch": state.epoch, "keywords_indexed": idx.keys,
                       "keywords_total": len(state.postings), "build_ms": round(idx.build_ms, 3),
                       "approx_mb": round(idx.approx_bytes / 2 ** 20, 2)})
        print(f"[search_index] {domain}: {idx.keys} keywords, built in {idx.build_ms:.1f} ms, "
              f"~{idx.approx_bytes / 2 ** 20:.1f} MB", flush=True)
        return idx
    return ent[1]


def _parts(ph, prefix, with_focus):
    s = ph["lookup"] + ph.get("focus", 0.0) + ph["sets"] + ph["eval"]
    out = {f"{prefix}_lookup": ph["lookup"], f"{prefix}_sets": ph["sets"], f"{prefix}_eval": ph["eval"],
           f"{prefix}_fetch": ph["fetch"]}
    if with_focus:
        out[f"{prefix}_focus"] = ph["focus"]
    return out, s


def run_query_split(dom, state, user, text):
    idx = _index_for(state, dom.name)                          # setup: built before the first timing
    t_q, _ = user.make_query(dom.name, text, E.anchor_read(dom)[0])   # the same B_Q as the full query (not timed;
    #                                                                   anchor read once per query, issue #68)
    b_q = boolean.from_json(t_q["B_Q"])
    plain, pf, fast = {}, {}, {}
    forms = [lambda: search_only(state, b_q, dom.server.dht, timing=plain),
             lambda: search_only(state, b_q, dom.server.dht, timing=pf, partition_first=True),
             lambda: search_fast(state, idx, b_q, dom.server.dht, timing=fast)]
    k = _CALLS[0] % 3                       # rotate which form runs first, so none always pays the cold caches
    _CALLS[0] += 1
    got = [f() for f in forms[k:] + forms[:k]]
    times, info = _full_query(dom, state, user, text)
    if any(ids != info["ids"] for ids in got):
        raise SystemExit("CORRECTNESS GATE FAILED: search-only files differ from the full response")
    for ph, prefix, name, with_focus in ((plain, "search", "server_search", False),
                                         (pf, "pf", "server_search_pf", True),
                                         (fast, "fast", "server_search_fast", True)):
        cols, s = _parts(ph, prefix, with_focus)
        times.update(cols)
        times[name] = s
        times[name + "_fetch"] = s + ph["fetch"]
    return times, info


def _out_dir(argv):
    return argv[argv.index("--out") + 1] if "--out" in argv else E.OUT


def _write_stats(path):
    if _STATS:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_STATS, f, indent=1)


def main():
    mode = next((x for x in sys.argv[1:] if not x.startswith("-")), "run")      # one file per suite, never overwritten
    atexit.register(_write_stats, os.path.join(_out_dir(sys.argv), f"search_index_{mode}.json"))
    E.run_query = run_query_split            # every suite (and run_xquery) looks run_query up at call time
    E.main()


if __name__ == "__main__":
    sys.exit(main())
