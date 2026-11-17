"""Search Tree leaf by partition (AMTP_PART_LEAF, default off): the leaf of a keyword in at least KEEP_MIN_PARTS
partitions also keeps its partition set and component positions (PartPosting). It is server-side lookup data
only, so every response must be byte-for-byte the response without it, under every query-flag combination, and
the search-only forms of bench_split must still return the response's files."""
import json
import random

import pytest

from amtp.adversary import ATTACKS
from amtp.core import boolean
from amtp.core.hashing import H
from amtp.dht import DHT
from amtp.engine import Engine
from amtp.index import (KEEP_MIN_PARTS, PartPosting, and_plan_greedy_on, and_prune_on, part_leaf_on,
                        part_results_on, set_and_plan_greedy, set_and_prune, set_part_leaf, set_part_results)
from amtp.server import build_response
from amtp.variants import AdaptivePolicy
from bench.workload import Doc
from bench_split.search_only import search_only

VOCAB = [f"w{i}" for i in range(14)]


def _leaf(word):
    return ("leaf", H("kw", word).hex())


QUERIES = [
    _leaf("w0"),
    _leaf("never-indexed"),
    ("AND", [_leaf("w0"), _leaf("w1")]),
    ("AND", [_leaf("w0"), _leaf("w1"), _leaf("w2"), _leaf("w3")]),
    ("AND", [_leaf(f"w{i}") for i in range(10)]),
    ("AND", [_leaf("w12"), _leaf("w13")]),
    ("AND", [_leaf("w0"), _leaf("w12")]),
    ("OR", [_leaf("w4"), _leaf("w5")]),
    ("OR", [_leaf("w4"), _leaf("never-indexed")]),
    ("AND", [("OR", [_leaf("w0"), _leaf("w6")]), _leaf("w2")]),
    ("OR", [("AND", [_leaf("w1"), _leaf("w7")]), _leaf("w8")]),
    ("AND", [_leaf("w0"), _leaf("never-indexed")]),
]

FLAG_SETS = {"none": (False, False, False), "prune": (True, False, False), "all": (True, True, True)}


@pytest.fixture(params=list(FLAG_SETS), ids=list(FLAG_SETS))
def flags(request):
    old = (and_prune_on(), part_results_on(), and_plan_greedy_on(), part_leaf_on())
    prune, results, greedy = FLAG_SETS[request.param]
    set_and_prune(prune)
    set_part_results(results)
    set_and_plan_greedy(greedy)
    yield
    set_and_prune(old[0])
    set_part_results(old[1])
    set_and_plan_greedy(old[2])
    set_part_leaf(old[3])


def _engine(seed, n=220):
    rnd = random.Random(seed)
    eng, dht = Engine("A", AdaptivePolicy(4, 2, 8)), DHT()
    for i in range(n):
        words = rnd.sample(VOCAB[:12], rnd.randint(2, 7))
        if i in (0, 75):
            words.append("w12")
        if i in (10, 75):
            words.append("w13")
        d = Doc(f"d{i}", rnd.randrange(4), words)
        dht.put(d.cid, d.ct)
        eng.insert(d.cid, d.keys, d.bucket)
    eng.commit()
    return eng, dht


def _snapshot(eng, by_part):
    set_part_leaf(by_part)
    return eng.snapshot()


def test_default_is_off():
    import os
    if os.environ.get("AMTP_PART_LEAF", "0") == "1":
        pytest.skip("AMTP_PART_LEAF=1 in the environment")
    assert not part_leaf_on()


def test_leaf_holds_the_same_list(flags):
    eng, _ = _engine(3)
    plain, kept = _snapshot(eng, False), _snapshot(eng, True)
    n_kept = 0
    for h, L in plain.postings.items():
        K = kept.postings.get(h)
        assert list(K) == list(L)
        assert not isinstance(L, PartPosting)
        if len(L) >= KEEP_MIN_PARTS:
            n_kept += 1
            assert isinstance(K, PartPosting)
            assert K.pids == frozenset(pid for pid, _ in L)
            assert all(K[j][0] == pid for pid, j in K.at.items())
        else:
            assert not isinstance(K, PartPosting)
    assert n_kept > 0
    assert kept.R_D == plain.R_D


@pytest.mark.parametrize("seed", [3, 11, 29])
def test_responses_are_byte_identical(flags, seed):
    eng, dht = _engine(seed)
    plain, kept = _snapshot(eng, False), _snapshot(eng, True)
    for i, ast in enumerate(QUERIES):
        b_q = boolean.canonical(ast)
        a = json.dumps(build_response(plain, b_q, f"{i:032x}", dht), sort_keys=True)
        b = json.dumps(build_response(kept, b_q, f"{i:032x}", dht), sort_keys=True)
        assert a == b, f"query {i} differs"


def test_search_only_forms_return_the_response_files(flags):
    eng, dht = _engine(5)
    kept = _snapshot(eng, True)
    for i, ast in enumerate(QUERIES):
        b_q = boolean.canonical(ast)
        resp = json.loads(json.dumps(build_response(kept, b_q, f"{i:032x}", dht)))
        want = {r["cid"] for r in resp["R_ct"]}
        assert search_only(kept, b_q, dht, timing={}) == want
        assert search_only(kept, b_q, dht, timing={}, partition_first=True) == want


@pytest.mark.parametrize("mode", sorted(set(ATTACKS) - {"honest"}))
def test_every_attack_is_still_caught_with_the_leaf(mode):
    """The adversary plug-in wraps the Search Tree (hide_posting); with the new leaf every attack is still
    rejected by the unchanged user (and with AND pruning on, so the kept PIDs are used)."""
    import test_adversary as T
    old = (part_leaf_on(), and_prune_on())
    set_part_leaf(True)
    set_and_prune(True)
    try:
        T.test_every_attack_is_caught(mode)
    finally:
        set_part_leaf(old[0])
        set_and_prune(old[1])
