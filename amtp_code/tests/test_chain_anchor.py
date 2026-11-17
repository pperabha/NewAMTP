"""The Root Anchor as a smart contract (chain/RootAnchor.sol) on an in-process Ethereum chain (eth-tester).

    ../.venv/bin/python -m pytest -q tests/test_chain_anchor.py

Skipped when web3 / eth-tester are not installed (pip install -r ../chain/requirements.txt).
Checks: the contract computes the same R_G and the same signed digest as the Python code, it enforces every
rule of anchor.RootAnchor (predecessor, e* + 1, owner signature, admin-only setup), and a whole AMTP run
(updates, searches, attacks) works with the roots read from the chain.
"""
import json
import os

import pytest

pytest.importorskip("web3")
pytest.importorskip("eth_tester")

from eth_account import Account                                       # noqa: E402

from amtp.anchor import NO_DELTA, RootAnchor, transition_message      # noqa: E402
from amtp.chain_anchor import ChainAnchor, chain_digest                # noqa: E402
from amtp.core.crypto import Signer                                    # noqa: E402
from amtp.scenario import World                                        # noqa: E402

N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141   # secp256k1 order


def r32(i):
    return bytes([i]) * 32


@pytest.fixture()
def chain():
    return ChainAnchor.local()


def python_twin(regs, subs=()):
    """The in-process anchor fed the same registrations and transitions (signatures aside)."""
    py = RootAnchor()
    s = Signer()
    for d, r0 in regs:
        py.register_domain(d, s.public, r0)
    for d, e, r, delta in subs:
        py.submit(d, e, r, s.sign(transition_message(d, e, r, py.current[d][1], delta)), delta)
    return py


def step(chain, d, r_new, delta=NO_DELTA, signer=None, epoch=None, prev=None):
    e_star, cur = chain.latest(d)
    epoch = e_star + 1 if epoch is None else epoch
    prev = cur if prev is None else prev
    sig = (signer or chain.root_signer(d)).sign(transition_message(d, epoch, r_new, prev, delta))
    chain.submit(d, epoch, r_new, sig, delta, prev=prev)


def test_global_root_matches_python(chain):
    assert chain.R_G == RootAnchor().R_G                               # no domain yet: the padding leaf
    regs = [("D3", r32(3)), ("D1", r32(1)), ("D4", r32(4)), ("D2", r32(2)), ("D10", r32(10))]
    for d, r0 in regs:
        chain.register_domain(d, chain.root_signer(d).public, r0)
    assert chain.R_G == python_twin(regs).R_G                          # sorted names, 5 leaves -> padded to 8
    step(chain, "D2", r32(20), r32(99))
    step(chain, "D2", r32(21))
    assert chain.R_G == python_twin(regs, [("D2", 1, r32(20), r32(99)), ("D2", 2, r32(21), NO_DELTA)]).R_G
    assert chain.latest("D2") == (2, r32(21)) and chain.latest("D1") == (0, r32(1))


def test_signed_digest_matches_python(chain):
    args = ("D1", 7, r32(1), r32(2), r32(3))
    on_chain = chain.contract.functions.transitionDigest(b"D1", 7, r32(1), r32(2), r32(3)).call()
    py = chain_digest(transition_message("D1", 7, r32(2), r32(1), r32(3)), chain.chain_id, chain.address)
    assert bytes(on_chain) == py, args


def test_contract_rejects_bad_transitions(chain):
    chain.register_domain("D1", chain.root_signer("D1").public, r32(1))
    chain.register_domain("D2", chain.root_signer("D2").public, r32(2))
    with pytest.raises(ValueError, match="e\\* \\+ 1"):
        step(chain, "D1", r32(9), epoch=2)                             # skips an epoch
    with pytest.raises(ValueError, match="predecessor"):
        step(chain, "D1", r32(9), prev=r32(8))                         # not the anchored root
    with pytest.raises(ValueError, match="owner signature invalid"):
        step(chain, "D1", r32(9), signer=chain.root_signer("D2"))      # another domain's owner
    with pytest.raises(ValueError, match="owner signature invalid"):
        sig = chain.root_signer("D1").sign(transition_message("D1", 1, r32(9), r32(1), NO_DELTA))
        chain.submit("D1", 1, r32(8), sig, NO_DELTA)                   # signature on another root
    sig = chain.root_signer("D1").sign(transition_message("D1", 1, r32(9), r32(1), NO_DELTA))
    r, s, v = sig[:32], int.from_bytes(sig[32:64], "big"), sig[64]
    high_s = r + (N - s).to_bytes(32, "big") + bytes([55 - v])          # the same signature, malleated
    with pytest.raises(ValueError, match="malleable"):
        chain.submit("D1", 1, r32(9), high_s, NO_DELTA)
    chain.submit("D1", 1, r32(9), sig, NO_DELTA)                       # the honest one goes through
    with pytest.raises(ValueError, match="predecessor|e\\* \\+ 1"):
        chain.submit("D1", 1, r32(9), sig, NO_DELTA, prev=r32(1))      # replayed
    assert chain.latest("D1") == (1, r32(9))


def test_setup_is_admin_only_and_once(chain):
    chain.register_domain("D1", chain.root_signer("D1").public, r32(1))
    with pytest.raises(ValueError, match="already registered"):
        chain.register_domain("D1", chain.root_signer("D1").public, r32(5))
    stranger = Account.create()
    chain.w3.eth.send_transaction({"from": chain.w3.eth.accounts[0], "to": stranger.address, "value": 10 ** 18})
    other = ChainAnchor(chain.w3, stranger, address=chain.address)
    with pytest.raises(ValueError, match="only admin"):
        other.register_domain("D9", stranger.address, r32(9))


def test_signature_is_bound_to_the_contract(chain):
    """A σ_root for one deployment is worthless on another one with the same domain and roots."""
    twin = ChainAnchor(chain.w3, chain.admin, owner_keys=chain.owner_keys, generate_owner_keys=True)
    for c in (chain, twin):
        c.register_domain("D1", c.root_signer("D1").public, r32(1))
    sig = chain.root_signer("D1").sign(transition_message("D1", 1, r32(9), r32(1), NO_DELTA))
    with pytest.raises(ValueError, match="owner signature invalid"):
        twin.submit("D1", 1, r32(9), sig, NO_DELTA)


def test_amtp_run_on_the_chain():
    """The whole protocol with the roots on the chain: every update is a contract transaction, every
    query reads (e*, R_D) from the chain, honest answers verify and attacks are still rejected."""
    chain = ChainAnchor.local()
    world = World(anchor=chain)
    for d in world.owners:                                              # one epoch per document at start
        assert chain.latest(d)[0] == sum(t.op == "submit" and t.domain == d for t in chain.txs) > 0
    assert {t.op for t in chain.txs} == {"register", "submit"}

    def run(uid, domain, text, mode="honest"):
        user = world.users[uid]
        t_q, ctx = user.make_query(domain, text, world.anchor)
        out = world.adversary.search(t_q, mode)
        if out["status"] != "ok":
            return out, None
        return out, user.verify(ctx, json.loads(json.dumps(out["response"])))

    _, rep = run("nina", "A", "(diabetes AND insulin) OR obesity")
    assert rep["accepted"], rep["failed"]
    run("mali", "A", "insulin")
    for mode, check in {"tamper_ct": "ct", "hide_posting": "papc", "stale": "anchor", "replay": "ctx"}.items():
        out, rep = run("mali", "A", "(diabetes AND insulin) OR obesity", mode)
        assert out["attack"]["applied"] and not rep["accepted"] and rep["failed"] == check, mode
    e_before = chain.latest("A")[0]
    world.publish_next("A")                                            # one more epoch through the contract
    assert chain.latest("A")[0] == e_before + 1
    _, rep = run("nina", "A", "insulin")
    assert rep["accepted"], rep["failed"]


@pytest.mark.skipif(not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "..", "chain", "RootAnchor.json")),
                    reason="contract not built")
def test_artifact_is_built_from_the_source():
    """RootAnchor.json must be the build of RootAnchor.sol (rebuild with chain/build.py after an edit)."""
    here = os.path.join(os.path.dirname(__file__), "..", "..", "chain")
    art = json.load(open(os.path.join(here, "RootAnchor.json")))
    assert art["solc"] == "0.8.28" and art["bytecode"].startswith("0x")
    assert {f["name"] for f in art["abi"] if f["type"] == "function"} >= {"register", "submit", "latest", "globalRoot"}
