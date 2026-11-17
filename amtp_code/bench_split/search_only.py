"""The server's search alone, without building any proof (lookup + eval), in two forms.

plain  (search_only(..., partition_first=False)):
  1. lookup  every query keyword: Cuckoo filter, then the B+ Search Tree (amtp.server.lookup, unchanged)
  2. sets    each keyword's set of files from its whole posting list (cid, partition, slot)
  3. eval    the Boolean expression over those sets (amtp.core.boolean.evaluate, unchanged)
  4. fetch   the ciphertext of every matching file from the DHT (as SE-COLLAB's search_core includes its fetch)

partition-first  (partition_first=True), the improved search:
  2a. focus  the partitions a match can lie in, from each keyword's partition list alone (boolean.focus: AND =
             intersection, OR = union; the same rule the server's AND pruning and the user apply). A posting list
             is stored per partition, so this needs one set of partition ids per keyword, not its files.
  2b. sets   each keyword's files only in those partitions
  then eval and fetch as above. A file matching B_Q lies in a partition of every keyword it satisfies, so the
  answer is the same (checked by the caller against the full response, and by tests/test_bench_split.py).

fast  (search_fast with a SearchIndex), partition-first on a search index built once per snapshot (setup):
  SearchIndex   for every keyword in at least KEEP_MIN_PARTS partitions (as the server keeps its R^post data):
                hex key -> (set of its partitions, {partition: its files there}); smaller keywords are read from the
                B+ tree at query time as in the plain form (most keywords are in one or two files)
  1. lookup  one dict access per keyword on the hex key (no hex decoding, no tree walk); keywords not in the index
             go through amtp.server.lookup (Cuckoo + B+ tree), so an absent keyword is still answered the same way
  2. focus   the partitions a match can lie in, from the stored partition sets without copying them
  3. sets    each keyword's files only in those partitions, read per partition (no scan of the whole list)
  4. eval / fetch as above
The Cuckoo filter, the B+ tree and the IMT are unchanged and still used to build the proof (amtp.server).

No IMT path, no Merkle path, no wire form: nothing that is only there for the proof.
"""
import sys
import time

from amtp.core import boolean
from amtp.index import KEEP_MIN_PARTS
from amtp.server import lookup


def search_only(state, b_q, dht, timing=None, partition_first=False):
    """Returns the cids (hex) of the matching files. `timing` (dict) receives lookup / focus / sets / eval / fetch
    in ms (focus = 0 for the plain form)."""
    t0 = time.perf_counter()
    postings = {h: lookup(state, bytes.fromhex(h)) for h in boolean.leaves(b_q)}
    t1 = time.perf_counter()
    if partition_first:
        F = _focus(b_q, {h: _leaf_pids(p) for h, p in postings.items()})
        tf = time.perf_counter()
        sets = {h: _sets_in(p, F) for h, p in postings.items()}
    else:
        tf = t1
        sets = {h: ({(cid, pid, slot) for pid, comp in p for cid, slot in comp} if p is not None else set())
                for h, p in postings.items()}
    t2 = time.perf_counter()
    match = boolean.evaluate(b_q, sets)
    t3 = time.perf_counter()
    cts = [dht.get(cid) for cid, _, _ in match]
    t4 = time.perf_counter()
    if timing is not None:
        timing.update(lookup=(t1 - t0) * 1e3, focus=(tf - t1) * 1e3, sets=(t2 - tf) * 1e3, eval=(t3 - t2) * 1e3,
                      fetch=(t4 - t3) * 1e3)
    assert len(cts) == len(match)
    return {cid.hex() for cid, _, _ in match}


_EMPTY = frozenset()


def _leaf_pids(p):
    """A keyword's partitions: kept in the Search Tree leaf when it is a PartPosting (AMTP_PART_LEAF),
    else read from the list (the leaf of a keyword in one or two partitions, or the flag off)."""
    if p is None:
        return _EMPTY
    pids = getattr(p, "pids", None)
    return pids if pids is not None else frozenset(pid for pid, _ in p)


def _sets_in(p, F):
    """The keyword's files in the partitions F. With a PartPosting leaf and F smaller than the list, read only
    the components of F (at: PID -> position); else scan the list."""
    if p is None:
        return set()
    at = getattr(p, "at", None)
    if at is not None and len(F) <= len(p):
        return {(cid, pid, slot) for pid in F if pid in at for cid, slot in p[at[pid]][1]}
    return {(cid, pid, slot) for pid, comp in p if pid in F for cid, slot in comp}


class SearchIndex:
    """Built once per snapshot (setup, not query time): hex key -> (frozenset of partitions, {pid: [(cid, slot)]})
    for every keyword in at least KEEP_MIN_PARTS partitions. build_ms and approx_bytes are reported by the runner."""

    def __init__(self, state, min_parts=KEEP_MIN_PARTS):
        t0 = time.perf_counter()
        self.by_key = {}
        size = 0
        for h, L in state.postings.items():
            if len(L) >= min_parts:
                by_pid = {pid: comp for pid, comp in L}          # references to the snapshot's lists, no copy
                pids = frozenset(by_pid)
                self.by_key[h.hex()] = (pids, by_pid)
                size += sys.getsizeof(by_pid) + sys.getsizeof(pids) + 113    # + the hex key string
        size += sys.getsizeof(self.by_key)
        self.build_ms = (time.perf_counter() - t0) * 1e3
        self.approx_bytes = size
        self.keys = len(self.by_key)


def _focus(ast, pids):
    """boolean.focus on stored sets: AND = intersection from the smallest, OR = union. Never copies a leaf set."""
    if ast[0] == "leaf":
        return pids[ast[1]]
    parts = [_focus(c, pids) for c in ast[1]]
    if ast[0] == "AND":
        parts.sort(key=len)
        out = parts[0]
        for p in parts[1:]:
            if not out:
                break
            out = out & p
        return out
    return frozenset().union(*parts)


def search_fast(state, index, b_q, dht, timing=None):
    """Partition-first search on a SearchIndex. Same answer as search_only (checked by the caller)."""
    t0 = time.perf_counter()
    by_key = index.by_key
    pids, by_pid = {}, {}
    for h in boolean.leaves(b_q):
        ent = by_key.get(h)
        if ent is None:                                   # small or absent keyword: Cuckoo filter + B+ tree
            p = lookup(state, bytes.fromhex(h))
            ent = (frozenset(pid for pid, _ in p), dict(p)) if p is not None else (frozenset(), {})
        pids[h], by_pid[h] = ent
    t1 = time.perf_counter()
    F = _focus(b_q, pids)
    tf = time.perf_counter()
    sets = {}
    for h, comps in by_pid.items():
        if len(F) <= len(comps):
            sets[h] = {(cid, pid, slot) for pid in F if pid in comps for cid, slot in comps[pid]}
        else:
            sets[h] = {(cid, pid, slot) for pid, comp in comps.items() if pid in F for cid, slot in comp}
    t2 = time.perf_counter()
    match = boolean.evaluate(b_q, sets)
    t3 = time.perf_counter()
    cts = [dht.get(cid) for cid, _, _ in match]
    t4 = time.perf_counter()
    if timing is not None:
        timing.update(lookup=(t1 - t0) * 1e3, focus=(tf - t1) * 1e3, sets=(t2 - tf) * 1e3, eval=(t3 - t2) * 1e3,
                      fetch=(t4 - t3) * 1e3)
    assert len(cts) == len(match)
    return {cid.hex() for cid, _, _ in match}
