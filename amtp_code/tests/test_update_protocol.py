"""Phase 2 update protocol: signed requests, CS proposal, owner Validator, Root Anchor.

  1. honest transitions (insert, delete, split, merge; b = 1, 3, 10) are validated and anchored,
     and the validator's root equals the server's incremental root and the full rebuild
  2. with b = 1 the protocol gives exactly the roots of the plain engine (one op, one commit)
  3. a changed Δ, Aff_i, R_new, placement, request or any part of π^upd is rejected
  4. random changes to π^upd are rejected or harmless (same root and Δ)
  5. the anchor starts from R^(0) and enforces predecessor and e* + 1
1-4 run with both placement rules (amtp/variants.py: least, fill).
"""
import copy
import random

import pytest

from amtp.anchor import RootAnchor
from amtp.core.crypto import Signer
from amtp.core.hashing import H
from amtp.engine import Engine
from amtp.owner import DataOwner, DomainKeys
from amtp.core.crypto import AttributeAuthority
from amtp.server import CloudServer
from amtp.update import enc_aff, delta, genesis_root, request_digest
from amtp.validator import Invalid
from amtp.variants import AdaptivePolicy, GlobalPolicy

WORDS = [f"term{i}" for i in range(60)]
PLACEMENTS = ["least", "fill"]


def make_owner(policy=None, b=1, placement="least"):
    anchor, server = RootAnchor(), CloudServer()
    keys = DomainKeys()
    server.register_query_key("A", keys.k_a)
    owner = DataOwner("A", "Owner", keys, AttributeAuthority(), anchor, server,
                      ops_per_epoch=b, policy=policy or AdaptivePolicy(2, 2, 6, placement))
    return owner


def doc(i, rnd):
    return {"id": f"d{i}", "title": f"t{i}", "body": "", "policy": "doctor",
            "keywords": rnd.sample(WORDS, rnd.randint(1, 6))}


def random_requests(owner, rnd, n_ops, live, k):
    """One epoch's batch; deletes pick documents that were finalized before this batch."""
    reqs, fresh = [], []
    for _ in range(n_ops):
        if live and rnd.random() < 0.4:
            reqs.append(owner.delete_request(live.pop(rnd.randrange(len(live)))))
        else:
            d = doc(k[0], rnd)
            k[0] += 1
            reqs.append(owner.insert_request(d, bucket=rnd.randrange(2)))
            fresh.append(d["id"])
    live.extend(fresh)
    return reqs


@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("b", [1, 3, 10])
def test_honest_transitions_are_validated_and_anchored(b, placement):
    rnd = random.Random(b)
    owner = make_owner(b=b, placement=placement)
    eng = owner.server.engines["A"]
    live, k = [], [0]
    for _ in range(60 // b + 40):     # fill keeps partitions fuller: the first merge comes later (epoch 27 at b = 10)
        state = owner.update(random_requests(owner, rnd, b, live, k))
        assert owner.validator.R_D == eng.R_D == state.R_D == owner.anchor.latest("A")[1]
        assert owner.validator.epoch == eng.epoch == owner.anchor.latest("A")[0]
    kinds = {r[0] for r in owner.structure_log}
    assert {"split", "merge"} <= kinds
    assert set(owner.validator.loc) == set(eng.loc) and owner.validator.loc == eng.loc


@pytest.mark.parametrize("placement", PLACEMENTS)
def test_b1_protocol_equals_plain_engine(placement):
    rnd = random.Random(5)
    owner = make_owner(b=1, placement=placement)
    plain = Engine("A", AdaptivePolicy(2, 2, 6, placement))
    live, k = [], [0]
    for _ in range(80):
        req = random_requests(owner, rnd, 1, live, k)[0]
        u = req["U"]
        if u["op"] == "insert":
            plain.insert(H(u["ct"]), {H(c) for c in u["C"]}, req["bucket"])
        else:
            plain.delete(u["cid"])
        plain.commit()
        owner.update([req])
        assert plain.R_D == owner.server.engines["A"].R_D == owner.anchor.latest("A")[1]


def test_global_policy_unversioned_also_validates():
    rnd = random.Random(2)
    owner = make_owner(policy=GlobalPolicy(2), b=2)
    live, k = [], [0]
    for _ in range(30):
        owner.update(random_requests(owner, rnd, 2, live, k))
    assert owner.validator.R_D == owner.server.engines["A"].R_D


# ---------------------------------------------------------------- tampering
def _flip(b):
    return bytes([b[0] ^ 1]) + b[1:]


def _redelta(p, reqs):
    p["delta"] = delta("A", p["epoch_new"], reqs, enc_aff(p["aff"]), p["R_old"], p["R_new"])


def _keys_with(p, mode):
    return [h for h, e in p["pi"]["keys"].items() if e.get("mode") == mode]


TAMPERS = {
    "delta": lambda p, r: p.update(delta=_flip(p["delta"])),
    "R_new": lambda p, r: p.update(R_new=_flip(p["R_new"])),
    "aff_with_matching_delta": lambda p, r: (p["aff"].append(("move", b"\0" * 32, "x", 0, "y", 0)),
                                             _redelta(p, r)),
    "R_part_old": lambda p, r: p["pi"].update(R_part_old=_flip(p["pi"]["R_part_old"])),
    "imt_proof": lambda p, r: p["pi"]["imt_proof"].__setitem__(0, _flip(p["pi"]["imt_proof"][0])),
    "imt_n_old": lambda p, r: p["pi"].update(imt_n_old=p["pi"]["imt_n_old"] + 1),
    "drop_key": lambda p, r: p["pi"]["keys"].pop(next(iter(p["pi"]["keys"]))),
    "extra_key": lambda p, r: p["pi"]["keys"].update({b"\x42" * 32: {"new": True, "pos_new": 0}}),
    "next_pointer": lambda p, r: next(e for e in p["pi"]["keys"].values() if "next" in e).update(
        next=b"\xff" * 31 + b"\xfe"),
    "n_sel": lambda p, r: next(e for e in p["pi"]["keys"].values() if "n_sel" in e).update(
        n_sel=next(e for e in p["pi"]["keys"].values() if "n_sel" in e)["n_sel"] + 1),
    "placement": lambda p, r: p["placements"].__setitem__(
        next(i for i, x in enumerate(p["placements"]) if x), [p["placements"][next(
            i for i, x in enumerate(p["placements"]) if x)][0], 10_000]),
    "request_signature": lambda p, r: r[0].update(sig=_flip(r[0]["sig"])),
    "request_epoch": lambda p, r: r[0]["U"].update(epoch=r[0]["U"]["epoch"] + 1),
}


def _fresh_case(seed, placement="least"):
    """An owner whose validator is exactly at a proposal's predecessor."""
    rnd = random.Random(seed)
    owner = make_owner(b=3, placement=placement)
    live, k = [], [0]
    for _ in range(rnd.randint(3, 25)):
        owner.update(random_requests(owner, rnd, 3, live, k))
    reqs = random_requests(owner, rnd, 3, live, k)
    return owner, owner.server.prepare_update("A", reqs), reqs


def _paths(obj, path=()):
    yield path, obj
    if isinstance(obj, dict):
        for kk, v in obj.items():
            yield from _paths(v, path + (kk,))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _paths(v, path + (i,))


def _set(obj, path, value):
    for p in path[:-1]:
        obj = obj[p]
    if isinstance(obj, tuple):
        raise TypeError
    obj[path[-1]] = value


@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("seed", range(6))
def test_targeted_tampers_on_fresh_proposals(seed, placement):
    for name, fn in TAMPERS.items():
        owner, prop, reqs = _fresh_case(seed, placement)
        p, r = copy.deepcopy(prop), copy.deepcopy(reqs)
        try:
            fn(p, r)
        except (StopIteration, IndexError):
            continue
        with pytest.raises((Invalid, KeyError, ValueError, TypeError, IndexError)):
            owner.validator.check(p, r)
        owner.validator.check(prop, reqs)               # the honest proposal still passes


@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("seed", range(4))
def test_random_changes_to_evidence_are_rejected_or_harmless(seed, placement):
    rnd = random.Random(100 + seed)
    owner, prop, reqs = _fresh_case(seed, placement)
    honest_sig = owner.validator.check(prop, reqs)
    assert honest_sig
    for _ in range(150):
        p = copy.deepcopy(prop)
        paths = [q for q, v in _paths(p["pi"], ("pi",)) if isinstance(v, (bytes, int, str)) and q]
        path = rnd.choice(paths)
        val = p
        for x in path:
            val = val[x]
        new = (_flip(val) if isinstance(val, bytes) and val else
               val + rnd.choice([-1, 1]) if isinstance(val, int) else val + "0")
        try:
            _set(p, path, new)
        except TypeError:
            continue
        try:
            owner.validator.check(p, reqs)
        except (Invalid, KeyError, ValueError, TypeError, IndexError, AttributeError):
            continue
        assert p["R_new"] == prop["R_new"] and p["delta"] == prop["delta"]   # accepted => harmless


def test_anchor_genesis_and_ordering():
    owner = make_owner()
    assert owner.anchor.latest("A") == (0, genesis_root("A", sorted(owner.validator.slots)))
    rnd = random.Random(1)
    live, k = [], [0]
    reqs = random_requests(owner, rnd, 1, live, k)
    prop = owner.server.prepare_update("A", reqs)
    sig = owner.validator.check(prop, reqs)
    with pytest.raises(ValueError):
        owner.anchor.submit("A", prop["epoch_new"] + 1, prop["R_new"], sig, prop["delta"])
    with pytest.raises(ValueError):
        owner.anchor.submit("A", prop["epoch_new"], prop["R_new"], sig, _flip(prop["delta"]))
    with pytest.raises(ValueError):
        owner.anchor.submit("A", prop["epoch_new"], prop["R_new"], Signer().sign(b"x"), prop["delta"])
    owner.anchor.submit("A", prop["epoch_new"], prop["R_new"], sig, prop["delta"], prev=prop["R_old"])
    with pytest.raises(ValueError):                      # replaying the same transition
        owner.anchor.submit("A", prop["epoch_new"], prop["R_new"], sig, prop["delta"], prev=prop["R_old"])


def test_replayed_request_nonce_is_rejected():
    owner = make_owner()
    rnd = random.Random(3)
    live, k = [], [0]
    req = random_requests(owner, rnd, 1, live, k)[0]
    owner.update([req])
    stale = copy.deepcopy(req)
    stale["U"]["epoch"] = owner.validator.epoch
    stale["U"]["id"] = "other"
    stale["sig"] = owner.signer.sign(request_digest(stale["U"]))      # validly signed, old nonce
    with pytest.raises(ValueError):
        owner.server.prepare_update("A", [stale])
