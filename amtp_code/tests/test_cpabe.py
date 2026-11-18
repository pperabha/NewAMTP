"""Real CP-ABE (BSW07 in Charm) for K_d: correctness, access denial, collusion resistance, CT bytes,
and the full Phase 1 -> Phase 5 path with AMTP_CPABE=bsw07. Skipped when Charm is not installed."""
import os

import pytest

pytest.importorskip("charm.schemes.abenc.abenc_bsw07")

from amtp.core import cpabe                                        # noqa: E402
from amtp.core.crypto import (AttributeAuthority, aes_gcm_decrypt, make_authority, make_ct,  # noqa: E402
                              unpack_ct, unwrap)
from amtp.core.hashing import H                                    # noqa: E402

K = bytes(range(32))


@pytest.fixture(scope="module")
def da():
    return cpabe.CpAbeAuthority()


def test_policy_translation():
    assert cpabe.charm_policy("trial AND (budget OR ethics)") == "(TRIAL and (BUDGET or ETHICS))"
    assert cpabe.charm_policy("auditor") == "AUDITOR"
    assert cpabe.attribute_name("data-officer") == "DATAQ2DOFFICER"
    assert cpabe.attribute_name("lab_b") == "LABQ5FB" != cpabe.attribute_name("labb")
    assert cpabe.attribute_name("q") == "Q51"


def test_satisfying_key_recovers_k_d(da):
    blob = da.wrap(K, "trial AND (budget OR ethics)")
    assert unwrap(blob, da.user_keys(["trial", "ethics"])) == K
    assert unwrap(blob, da.user_keys(["TRIAL", "budget", "other"])) == K


def test_non_satisfying_key_gets_nothing(da):
    blob = da.wrap(K, "trial AND (budget OR ethics)")
    assert unwrap(blob, da.user_keys(["trial"])) is None
    assert unwrap(blob, da.user_keys(["budget", "ethics"])) is None
    assert unwrap(blob, {}) is None                        # a stand-in key dict is not a BSW07 key


def test_collusion_resistance(da):
    """Two users who each hold one half of an AND policy cannot combine their keys. The policy key
    wrap stand-in fails this test (XOR shares per attribute); real CP-ABE must pass it."""
    blob = da.wrap(K, "trial AND budget")
    alice, bob = da.user_keys(["trial"]), da.user_keys(["budget"])
    merged = cpabe.AttributeKey(
        {"D": alice.sk["D"], "Dj": {**alice.sk["Dj"], **bob.sk["Dj"]},
         "Djp": {**alice.sk["Djp"], **bob.sk["Djp"]}, "S": ["BUDGET", "TRIAL"]},
        ["BUDGET", "TRIAL"], alice.pk)
    assert unwrap(blob, merged) is None
    assert unwrap(blob, da.user_keys(["trial", "budget"])) == K


def test_stand_in_is_not_collusion_resistant():
    """Documents why the stand-in is replaced: merging two users' attribute keys opens an AND policy."""
    wrap = AttributeAuthority()
    blob = wrap.wrap(K, "trial AND budget")
    merged = {**wrap.user_keys(["trial"]), **wrap.user_keys(["budget"])}
    assert unwrap(blob, merged) == K


def test_other_domain_key_fails(da):
    other = cpabe.CpAbeAuthority()                         # another DA: other PK, MSK
    blob = da.wrap(K, "auditor")
    assert unwrap(blob, other.user_keys(["auditor"])) is None


def test_tampered_blob_is_rejected(da):
    blob = da.wrap(K, "auditor")
    bad = dict(blob, C=blob["C"][:-2] + ("00" if blob["C"][-2:] != "00" else "11"))
    assert unwrap(bad, da.user_keys(["auditor"])) is None
    assert unwrap(dict(blob, abe="AAAA"), da.user_keys(["auditor"])) is None


def test_ct_bytes_are_stable_and_decrypt(da):
    ct = make_ct(K, b'{"title":"t","body":"b"}', da.wrap(K, "auditor"), {"domain": "D1", "doc": "d1"})
    p = unpack_ct(ct)
    assert H(ct) == H(bytes(ct))
    k_d = unwrap(p["CK"], da.user_keys(["auditor"]))
    assert aes_gcm_decrypt(k_d, p["E"], p["aad_b"]) == b'{"title":"t","body":"b"}'


def test_make_authority_switch(monkeypatch):
    monkeypatch.setenv("AMTP_CPABE", "bsw07")
    assert isinstance(make_authority(), cpabe.CpAbeAuthority)
    monkeypatch.setenv("AMTP_CPABE", "wrap")
    assert isinstance(make_authority(), AttributeAuthority)
    with pytest.raises(ValueError):
        make_authority("rsa")


def test_end_to_end_with_real_cpabe(monkeypatch):
    """Phase 1 -> Phase 5 on the scenario world with real CP-ABE: the search is verified, and decryption
    opens exactly the files whose policy the user's attributes satisfy (same expectations as the
    stand-in in tests/test_demo.py)."""
    import json
    monkeypatch.setenv("AMTP_CPABE", "bsw07")
    from amtp.scenario import World
    w = World()
    assert isinstance(w.authority, cpabe.CpAbeAuthority)
    user = w.users["kit"]
    t_q, ctx = user.make_query("B", "trial", w.anchor)
    out = w.adversary.search(t_q, "honest")
    resp = json.loads(json.dumps(out["response"]))
    assert user.verify(ctx, resp)["accepted"]
    files = {f["doc"]: f["status"] for f in user.decrypt(resp)}
    assert files["B-03"] == "open" and files["B-04"] == "open"     # auditor OR researcher
    assert files["B-01"] == "locked"                                 # researcher AND lab_b
