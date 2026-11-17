"""Result-only partition check (study flag, amtp/server.py): partition slots and domain-tree leaves are opened
only for the returned files; the other covered partitions send just their version v, which γ binds. The
user accepts it only if the answer is still exact: honest answers are accepted and exact (with and without
AND pruning), every attack is still caught, and random changes are rejected or harmless."""
import copy
import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "baselines"))
import wire_sizes as W                                        # noqa: E402  (the one size rule)
from amtp.adversary import ATTACKS                            # noqa: E402
from amtp.index import and_prune_on, part_results_on, set_and_prune, set_part_results   # noqa: E402
from amtp.scenario import World                               # noqa: E402
from test_and_prune import QUERIES, _truth, _world            # noqa: E402
from test_phase5_fuzz import _cheat, _mutate, _result         # noqa: E402


@pytest.fixture
def flags():
    """Restore both study flags after each test."""
    old = (and_prune_on(), part_results_on())
    yield
    set_and_prune(old[0])
    set_part_results(old[1])


@pytest.fixture(scope="module")
def rich():
    old = and_prune_on()
    set_and_prune(True)          # keep R^post trees so both forms can be tested on one world
    try:
        yield _world()
    finally:
        set_and_prune(old)


def _ask(w, user, text):
    t_q, ctx = user.make_query("A", text, w.anchor)
    out = w.server.search(t_q)
    assert out["status"] == "ok"
    return ctx, json.loads(json.dumps(out["response"]))


@pytest.mark.skipif(os.environ.get("AMTP_PART_RESULTS", "1") != "0", reason="result-only proofs are on (default); run with AMTP_PART_RESULTS=0")
def test_default_is_off():
    assert not part_results_on()
    w = World()
    _, resp = _ask(w, w.users["mali"], "insulin OR diabetes")
    assert "versions" not in resp["proof"]


@pytest.mark.parametrize("prune", [False, True])
@pytest.mark.parametrize("text", QUERIES)
def test_honest_answers_are_accepted_and_exact(flags, rich, prune, text):
    w, words = rich
    user = w.users["mali"]
    set_part_results(True)
    set_and_prune(prune)
    ctx, resp = _ask(w, user, text)
    rep = user.verify(ctx, resp)
    assert rep["accepted"], (text, rep["failed"], rep["checks"])
    assert "versions" in resp["proof"]
    synthetic = {o["doc"] for o in user.decrypt(resp) if o["doc"].startswith("S-")}
    assert synthetic == _truth(words, text)
    # only the result files' partitions are opened
    assert {d["pid"] for d in resp["proof"]["partitions"]} == {r["pid"] for r in resp["R_ct"]}


def test_proofs_are_not_larger_and_results_equal(flags, rich):
    w, _ = rich
    user = w.users["mali"]
    set_and_prune(False)
    smaller, total_p, total_f = 0, 0, 0
    for text in QUERIES:
        set_part_results(False)
        _, full = _ask(w, user, text)
        set_part_results(True)
        ctx, part = _ask(w, user, text)
        assert user.verify(ctx, part)["accepted"]
        assert {r["cid"] for r in part["R_ct"]} == {r["cid"] for r in full["R_ct"]}
        p, f = W.amtp_proof_bytes(part["proof"]), W.amtp_proof_bytes(full["proof"])
        # fewer opened slots in a partition can need a few more sibling hashes in its slot multiproof
        assert p <= f * 1.05, (text, p, f)
        smaller += p < f
        total_p, total_f = total_p + p, total_f + f
    assert smaller >= len(QUERIES) // 2 and total_p < total_f


@pytest.mark.parametrize("prune", [False, True])
@pytest.mark.parametrize("mode", sorted(set(ATTACKS) - {"honest", "storage_loss"}))
def test_every_attack_is_still_caught(flags, prune, mode):
    set_part_results(True)
    set_and_prune(prune)
    w, _ = _world()
    user = w.users["mali"]
    for query in ("beta AND gamma AND delta", "alpha OR beta"):
        t_q, _ = user.make_query("A", query, w.anchor)
        assert w.adversary.search(t_q)["status"] == "ok"
        t_q, ctx = user.make_query("A", query, w.anchor)
        out = w.adversary.search(t_q, mode)
        assert out["attack"]["applied"], (mode, query)
        rep = user.verify(ctx, json.loads(json.dumps(out["response"])))
        assert not rep["accepted"], (mode, query)


def _answer(rich, text="beta AND delta"):
    w, _ = rich
    user = w.users["mali"]
    set_part_results(True)
    set_and_prune(False)
    ctx, resp = _ask(w, user, text)
    assert user.verify(ctx, copy.deepcopy(resp))["accepted"]
    assert resp["proof"]["versions"], "the test needs covered partitions without results"
    return user, ctx, resp


def _failed(user, ctx, resp):
    rep = user.verify(ctx, resp)
    return None if rep["accepted"] else rep["failed"]


def test_wrong_plain_version_is_caught(flags, rich):
    user, ctx, resp = _answer(rich)
    resp["proof"]["versions"][0][1] += 1
    assert _failed(user, ctx, resp) == "papc"


def test_missing_plain_version_is_caught(flags, rich):
    user, ctx, resp = _answer(rich)
    resp["proof"]["versions"].pop()
    assert _failed(user, ctx, resp) in ("papc", "part")


def test_extra_plain_version_is_caught(flags, rich):
    user, ctx, resp = _answer(rich)
    resp["proof"]["versions"].append(["ffffffffffffffff", 0])
    assert _failed(user, ctx, resp) == "part"


def test_result_partition_without_descriptor_is_caught(flags, rich):
    """The server hides a result partition's slot proof by listing it as a plain version instead."""
    user, ctx, resp = _answer(rich)
    d = resp["proof"]["partitions"].pop()
    resp["proof"]["versions"] = sorted(resp["proof"]["versions"] + [[d["pid"], d["v"]]])
    assert _failed(user, ctx, resp) == "part"


def test_described_partition_also_in_plain_list_is_caught(flags, rich):
    user, ctx, resp = _answer(rich)
    d = resp["proof"]["partitions"][0]
    resp["proof"]["versions"] = sorted(resp["proof"]["versions"] + [[d["pid"], d["v"]]])
    assert _failed(user, ctx, resp) == "papc"


@pytest.mark.parametrize("prune", [False, True])
@pytest.mark.parametrize("seed", range(2))
def test_random_changes_are_rejected_or_harmless(flags, rich, prune, seed):
    rnd = random.Random(seed)
    w, _ = rich
    user = w.users["mali"]
    set_part_results(True)
    set_and_prune(prune)
    for text in QUERIES:
        ctx, honest = _ask(w, user, text)
        assert user.verify(ctx, copy.deepcopy(honest))["accepted"], text
        truth = _result(honest)
        for i in range(120):
            resp = copy.deepcopy(honest)
            if i % 4 == 0:
                _cheat(rnd, resp)
            for _ in range(rnd.randint(0 if i % 4 == 0 else 1, 3)):
                _mutate(rnd, resp)
            rep = user.verify(ctx, resp)                     # must not raise
            if rep["accepted"]:
                assert _result(resp) == truth, (text, rep)
