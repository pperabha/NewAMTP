"""Real ABS (Maji-Prabhakaran-Rosulek, ePrint 2008/328, Section 3.2) for σ_op: correctness, wrong /
missing attributes, tampering, collusion, another domain's key, and the AMTP update path with
AMTP_ABS=mpr. Skipped when Charm is not installed."""
import pytest

pytest.importorskip("charm.toolbox.pairinggroup")

from amtp.core import abs as A                                       # noqa: E402
from amtp.core.crypto import Ed25519Signer, Signer, abs_kind, sig_ok   # noqa: E402

MSG = b"H(U_op) of one insertion request"


@pytest.fixture(scope="module")
def da():
    return A.AbsAuthority()


@pytest.fixture(scope="module")
def owner(da):
    attrs = A.owner_attributes("D1")
    return da, da.public(A.owner_policy("D1")), da.attr_gen(attrs), attrs


def test_span_program_reconstructs_e1():
    """vM = [1, 0, .., 0] for every satisfying set, and no 0/1 combination of the rows of a
    non-satisfying set reaches it (checked over the integers for these small programs)."""
    for policy, good, bad in [
        (A.owner_policy("D1"), [["domain:d1", "role:owner"]], [["domain:d1"], ["role:owner"], []]),
        ("a AND (b OR c) AND d", [["a", "b", "d"], ["a", "c", "d"]], [["a", "b"], ["b", "c", "d"]]),
        ("a OR b", [["a"], ["b"]], [["c"]]),
        ("a", [["a"]], [["b"]]),
    ]:
        rows, labels, t = A.span_program(policy)
        for attrs in good:
            v = A._satisfying_vector(policy, attrs)
            assert [sum(v[i] * rows[i][j] for i in range(len(rows))) for j in range(t)] == [1] + [0] * (t - 1)
            assert all(labels[i] in attrs for i in range(len(v)) if v[i])
        for attrs in bad:
            assert A._satisfying_vector(policy, attrs) is None


def test_sign_verify(owner):
    da, pub, key, attrs = owner
    sig = A.sign(pub, key, MSG, attrs)
    assert A.verify(pub, MSG, sig)
    assert sig_ok(pub, MSG, sig)                                   # crypto.sig_ok dispatches to ABS


def test_signature_is_randomised(owner):
    da, pub, key, attrs = owner
    s1, s2 = A.sign(pub, key, MSG, attrs), A.sign(pub, key, MSG, attrs)
    assert s1 != s2 and A.verify(pub, MSG, s1) and A.verify(pub, MSG, s2)


def test_missing_attribute_cannot_sign(da, owner):
    _, pub, _, _ = owner
    only_domain = da.attr_gen(["domain:D1"])
    with pytest.raises(ValueError):
        A.sign(pub, only_domain, MSG, ["domain:d1"])


def test_wrong_attribute_key_does_not_verify(da, owner):
    """A key for {domain:D2, role:owner} under the same authority, used as if it held domain:D1."""
    _, pub, _, attrs = owner
    other = da.attr_gen(["domain:D2", "role:owner"])
    other.k_u["domain:d1"] = other.k_u.pop("domain:d2")
    assert not A.verify(pub, MSG, A.sign(pub, other, MSG, attrs))


def test_collusion_fails(da, owner):
    """Two users, one with domain:D1 and one with role:owner, pool their attribute keys."""
    _, pub, _, attrs = owner
    u1, u2 = da.attr_gen(["domain:D1"]), da.attr_gen(["role:owner"])
    pooled = A.AbsKey(u1.k_base, u1.k_0, {**u1.k_u, **u2.k_u})
    assert not A.verify(pub, MSG, A.sign(pub, pooled, MSG, attrs))
    pooled2 = A.AbsKey(u2.k_base, u2.k_0, {**u1.k_u, **u2.k_u})
    assert not A.verify(pub, MSG, A.sign(pub, pooled2, MSG, attrs))


def test_tampered_message_or_signature(owner):
    da, pub, key, attrs = owner
    sig = A.sign(pub, key, MSG, attrs)
    assert not A.verify(pub, MSG + b"!", sig)
    grp = A._group(pub.curve)
    elems = A._unpack(grp, sig)
    for k in range(len(elems)):                                    # replace each element in turn
        bad = list(elems)
        bad[k] = bad[k] * bad[k]
        assert not A.verify(pub, MSG, A._pack(grp, bad))
    assert not A.verify(pub, MSG, sig[:-3])                        # truncated
    assert not A.verify(pub, MSG, b"")
    assert not A.verify(pub, MSG, A._pack(grp, elems[:-1]))         # wrong element count


def test_identity_y_rejected(owner):
    """The paper's first verification step: Y = 1 is rejected (otherwise W = 1 passes e(W,A0)=e(Y,h0))."""
    da, pub, key, attrs = owner
    from charm.toolbox.pairinggroup import G1
    grp = A._group(pub.curve)
    elems = A._unpack(grp, A.sign(pub, key, MSG, attrs))
    elems[0] = elems[1] = grp.init(G1, 1)
    assert not A.verify(pub, MSG, A._pack(grp, elems))


def test_identity_or_wrong_group_in_any_slot_rejected(owner):
    """An all-zero (identity) or wrong-group element anywhere is refused before any pairing: Charm
    crashes the process when it pairs a decoded all-zero point, so a hostile CS must not reach that."""
    from charm.toolbox.pairinggroup import G1, G2
    da, pub, key, attrs = owner
    grp = A._group(pub.curve)
    good = A._unpack(grp, A.sign(pub, key, MSG, attrs))
    n_g1 = len(good) - A.span_program(pub.policy)[2]
    for k in range(len(good)):
        bad = list(good)
        bad[k] = grp.init(G1 if k < n_g1 else G2, 1)
        assert not A.verify(pub, MSG, A._pack(grp, bad))
        bad[k] = grp.random(G2 if k < n_g1 else G1)
        assert not A.verify(pub, MSG, A._pack(grp, bad))


def test_policy_bound_into_mu(da, owner):
    """A signature under 'domain:D1 AND role:owner' does not verify under a weaker claim of the same PK."""
    _, pub, key, attrs = owner
    sig = A.sign(pub, key, MSG, attrs)
    assert not A.verify(da.public('"role:owner"'), MSG, sig)


def test_other_domain_key_does_not_verify():
    """Each domain has its own ABS Setup (one AbsSigner = one domain's DA), as owners use it."""
    d1, d2 = A.AbsSigner("D1"), A.AbsSigner("D2")
    assert A.verify(d1.public, MSG, d1.sign(MSG))
    assert not A.verify(d1.public, MSG, d2.sign(MSG))
    assert not sig_ok(d1.public, MSG, Ed25519Signer().sign(MSG))     # an Ed25519 signature is not an ABS one


def test_or_and_wider_policies(da):
    attrs = ["a", "c", "d"]
    pub = da.public("a AND (b OR c) AND d")
    key = da.attr_gen(attrs)
    assert A.verify(pub, MSG, A.sign(pub, key, MSG, attrs))
    five = " AND ".join(f'"x{i}"' for i in range(5))
    k5 = da.attr_gen([f"x{i}" for i in range(5)])
    pub5 = da.public(five)
    assert A.verify(pub5, MSG, A.sign(pub5, k5, MSG, [f"x{i}" for i in range(5)]))


def test_env_switch(monkeypatch):
    monkeypatch.setenv("AMTP_ABS", "mpr")
    s = Signer("D7")
    assert isinstance(s, A.AbsSigner) and s.public.policy == A.canonical_policy(A.owner_policy("D7"))
    assert sig_ok(s.public, MSG, s.sign(MSG))
    monkeypatch.setenv("AMTP_ABS", "ed25519")
    assert isinstance(Signer(), Ed25519Signer)
    monkeypatch.setenv("AMTP_ABS", "nope")
    with pytest.raises(ValueError):
        abs_kind()


def test_update_protocol_with_real_abs(monkeypatch):
    """Phase 1 -> 5 on scenario.World with σ_op under real ABS: the initial uploads, a new insertion and
    a deletion are accepted end to end (CS admission, DO validation, anchoring) and a later query
    verifies; a request signed with another domain's ABS key is refused by the CS."""
    import json
    monkeypatch.setenv("AMTP_ABS", "mpr")
    from amtp.scenario import World
    w = World()
    owner = w.owners["B"]
    assert isinstance(owner.signer, A.AbsSigner)
    epoch0 = w.anchor.latest("B")[0]
    doc = w.publish_next("B")                                       # insert (σ_op = σ_d of the upload)
    owner.delete_documents([doc["id"]])                             # delete
    assert w.anchor.latest("B")[0] == epoch0 + 2
    user = w.users["kit"]
    t_q, ctx = user.make_query("B", "trial", w.anchor)
    resp = json.loads(json.dumps(w.adversary.search(t_q, "honest")["response"]))
    assert user.verify(ctx, resp)["accepted"]

    forged = owner.delete_request(next(iter(owner.doc)))
    forged["sig"] = w.owners["A"].signer.sign(__import__("amtp.update", fromlist=["x"]).request_digest(forged["U"]))
    with pytest.raises(ValueError, match="σ_op invalid"):
        w.server.prepare_update("B", [forged])
    assert w.anchor.latest("B")[0] == epoch0 + 2
