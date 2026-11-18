"""Real attribute-based signatures for σ_op (= σ_d of an upload; paper (32) eqs. 9 and 11).

Scheme: Maji, Prabhakaran, Rosulek, "Attribute-Based Signatures: Achieving Attribute-Privacy and
Collusion-Resistance", IACR ePrint 2008/328, Section 3.2 (single attribute authority). Written from the
equations of that section; the variable names below follow the paper.

    Setup     g, C <- G;  h_0..h_tmax <- H;  a_0, a, b <- Z_p*
              A_0 = h_0^a_0,  A_j = h_j^a,  B_j = h_j^b             (j = 1..tmax)
              MK = (a_0, a, b);  PK = (H, g, h_0..h_tmax, A_0..A_tmax, B_1..B_tmax, C)
    AttrGen   K_base <- G;  K_0 = K_base^(1/a_0);  K_u = K_base^(1/(a + b u))   (u in A)
    Sign      Υ -> monotone span program M (l x t), row labels u(i); v with vM = [1,0,..,0] and
              v_i = 0 for rows the signer lacks;  mu = H(m || Υ);  r_0 <- Z_p*, r_1..r_l <- Z_p
              Y = K_base^r_0,  W = K_0^r_0,  S_i = (K_u(i)^v_i)^r_0 (C g^mu)^r_i,
              P_j = prod_i (A_j B_j^u(i))^(M_ij r_i);   σ = (Y, W, S_1..S_l, P_1..P_t)
    Verify    reject if Y = 1;  e(W, A_0) = e(Y, h_0);  for j = 1..t:
              prod_i e(S_i, (A_j B_j^u(i))^M_ij) = e(Y, h_1) e(C g^mu, P_1)   (j = 1)
                                                 = e(C g^mu, P_j)            (j > 1)

Groups: G = G1, H = G2 of an asymmetric pairing e: G1 x G2 -> GT (the paper's e: G x H -> G_T).
Curve: BN254 by default (team decision, 18 Nov); AMTP_ABS_CURVE selects another Charm curve.
Attributes are strings mapped into Z_p* with the group hash (the paper's footnote 3).
The span program is the Lewko-Waters construction for AND/OR formulas: entries in {0, 1, -1}.
Security (paper Theorems 1-2): correct and perfectly private unconditionally; unforgeable, including
against colluding signers, in the generic group model.

Interface (same as the Ed25519 stand-in in crypto.py, so owner.py / server.py / validator.py do not
change): AbsSigner().public, .sign(msg) -> bytes, and verify(public, msg, sig) -> bool.
Select it with AMTP_ABS=mpr (crypto.Signer).
"""
import os
import struct

from .boolean import parse

SCHEME = "mpr"
DEFAULT_CURVE = "BN254"
T_MAX = 8                       # widest span program a domain's PK supports (an AND of up to 8 attributes)

_groups = {}


def _group(curve=None):
    curve = curve or os.environ.get("AMTP_ABS_CURVE", DEFAULT_CURVE)
    if curve not in _groups:
        from charm.toolbox.pairinggroup import PairingGroup
        _groups[curve] = PairingGroup(curve)
    return _groups[curve]


def _types():
    from charm.toolbox.pairinggroup import G1, G2, ZR, pair
    return G1, G2, ZR, pair


# ---------- claim-predicates and monotone span programs ----------

def owner_policy(domain: str) -> str:
    """The root-update / operation policy of a domain (issue #43): one policy for insert and delete."""
    return f'"domain:{domain}" AND "role:owner"'


def owner_attributes(domain: str):
    return [f"domain:{domain}", "role:owner"]


def canonical_policy(policy: str) -> str:
    """One string per policy (the parser lower-cases leaves and sorts children), hashed into mu."""
    def walk(node):
        if node[0] == "leaf":
            return '"' + node[1] + '"'
        return "(" + f" {node[0]} ".join(walk(c) for c in node[1]) + ")"
    return walk(parse(policy))


def span_program(policy: str):
    """Lewko-Waters: root vector (1); OR gives its vector to every child; AND (made binary) gives
    v||1 to the left child and 0..0||-1 to the right one. Returns (rows, labels, width)."""
    rows, labels, width = [], [], [1]

    def walk(node, vec):
        if node[0] == "leaf":
            rows.append(vec)
            labels.append(node[1])
            return
        kids = node[1]
        if node[0] == "OR":
            for k in kids:
                walk(k, vec)
            return
        if len(kids) > 2:                           # a AND b AND c = a AND (b AND c)
            kids = [kids[0], ("AND", kids[1:])]
        c = width[0]
        width[0] += 1
        walk(kids[0], vec + [0] * (c - len(vec)) + [1])
        walk(kids[1], [0] * c + [-1])

    walk(parse(policy), [1])
    t = width[0]
    return [r + [0] * (t - len(r)) for r in rows], labels, t


def _satisfying_vector(policy: str, attrs) -> list:
    """v with vM = [1, 0, .., 0] using only rows whose attribute the signer holds (None if Υ(A) = 0).
    For the Lewko-Waters matrix v_i is 1 on a satisfying set of leaves (both children of an AND,
    one child of an OR) and 0 elsewhere."""
    have = {a.lower() for a in attrs}
    counter = [0]

    def walk(node):                                 # -> list of leaf indices used, or None
        if node[0] == "leaf":
            i = counter[0]
            counter[0] += 1
            return [i] if node[1] in have else None
        kids = node[1]
        if node[0] == "AND" and len(kids) > 2:
            kids = [kids[0], ("AND", kids[1:])]
        got = [walk(k) for k in kids]               # walk every child to keep the leaf numbering
        if node[0] == "OR":
            return next((g for g in got if g is not None), None)
        return None if any(g is None for g in got) else [i for g in got for i in g]

    used = walk(parse(policy))
    if used is None:
        return None
    v = [0] * counter[0]
    for i in used:
        v[i] = 1
    return v


# ---------- keys ----------

class AbsPublic:
    """What a verifier needs: the authority's PK and the domain's claim-predicate Υ."""

    def __init__(self, pk, policy, curve):
        self.pk, self.policy, self.curve = pk, canonical_policy(policy), curve
        self._msp = span_program(self.policy)
        self._ab = {}                      # (j, label) -> A_j B_j^u: fixed by PK and Υ, computed once

    def ab(self, j, label):
        if (j, label) not in self._ab:
            self._ab[j, label] = self.pk["A"][j] * (self.pk["B"][j] ** attr_value(label, self.curve))
        return self._ab[j, label]

    def __repr__(self):
        return f"AbsPublic({self.policy})"


class AbsKey:
    """SK_A = (K_base, K_0, {K_u | u in A})."""

    def __init__(self, k_base, k_0, k_u: dict):
        self.k_base, self.k_0, self.k_u = k_base, k_0, k_u


class AbsAuthority:
    """The Domain Authority's ABS: Setup (PK, MK) and AttrGen."""

    def __init__(self, t_max: int = T_MAX, curve: str = None):
        self.curve = curve or os.environ.get("AMTP_ABS_CURVE", DEFAULT_CURVE)
        grp = _group(self.curve)
        G1, G2, ZR, _ = _types()
        a0, a, b = grp.random(ZR), grp.random(ZR), grp.random(ZR)
        h = [grp.random(G2) for _ in range(t_max + 1)]
        self._mk = (a0, a, b)
        self.pk = {"g": grp.random(G1), "C": grp.random(G1), "h": h, "A0": h[0] ** a0,
                   "A": [None] + [h[j] ** a for j in range(1, t_max + 1)],
                   "B": [None] + [h[j] ** b for j in range(1, t_max + 1)], "t_max": t_max}

    def attr_gen(self, attrs) -> AbsKey:
        grp = _group(self.curve)
        G1, _, ZR, _ = _types()
        a0, a, b = self._mk
        k_base = grp.random(G1)
        k_u = {u.lower(): k_base ** (1 / (a + b * attr_value(u.lower(), self.curve))) for u in attrs}
        return AbsKey(k_base, k_base ** (1 / a0), k_u)

    def public(self, policy: str) -> AbsPublic:
        return AbsPublic(self.pk, policy, self.curve)


def attr_value(attr: str, curve=None):
    """u in Z_p* for an attribute string (paper footnote 3)."""
    _, _, ZR, _ = _types()
    return _group(curve).hash("AMTP-ABS-attr|" + attr, ZR)


def _mu(msg: bytes, policy: str, curve):
    _, _, ZR, _ = _types()
    return _group(curve).hash("AMTP-ABS-msg|" + msg.hex() + "|" + policy, ZR)


def _zr(x: int, curve):
    _, _, ZR, _ = _types()
    grp = _group(curve)
    return grp.init(ZR, x % int(grp.order()))


# ---------- Sign / Verify ----------

def sign(public: AbsPublic, key: AbsKey, msg: bytes, attrs) -> bytes:
    """σ = (Y, W, S_1..S_l, P_1..P_t) on msg under the claim-predicate public.policy."""
    curve, pk, policy = public.curve, public.pk, public.policy
    grp = _group(curve)
    G1, G2, ZR, _ = _types()
    rows, labels, t = public._msp
    if t > pk["t_max"]:
        raise ValueError(f"policy needs width {t} > t_max {pk['t_max']}")
    v = _satisfying_vector(policy, attrs)
    if v is None:
        raise ValueError("the signer's attributes do not satisfy the policy")
    mu = _mu(msg, policy, curve)
    cg = pk["C"] * (pk["g"] ** mu)
    r0 = grp.random(ZR)
    while r0 == _zr(0, curve):
        r0 = grp.random(ZR)
    r = [grp.random(ZR) for _ in rows]
    Y, W = key.k_base ** r0, key.k_0 ** r0
    S = []
    for i, label in enumerate(labels):
        s = cg ** r[i]
        if v[i]:
            s = (key.k_u[label] ** (_zr(v[i], curve) * r0)) * s
        S.append(s)
    P = []
    for j in range(1, t + 1):
        p = grp.init(G2, 1)
        for i, label in enumerate(labels):
            m_ij = rows[i][j - 1]
            if m_ij:
                p = p * (public.ab(j, label) ** (_zr(m_ij, curve) * r[i]))
        P.append(p)
    return _pack(grp, [Y, W] + S + P)


def verify(public: AbsPublic, msg: bytes, sig: bytes) -> bool:
    curve, pk, policy = public.curve, public.pk, public.policy
    grp = _group(curve)
    G1, G2, ZR, pair = _types()
    rows, labels, t = public._msp
    l = len(labels)
    try:
        elems = _unpack(grp, sig, [b"1"] * (2 + l) + [b"2"] * t)    # Y, W, S_i in G1; P_j in G2
    except Exception:
        return False
    Y, W, S, P = elems[0], elems[1], elems[2:2 + l], elems[2 + l:]
    if Y == grp.init(G1, 1):
        return False
    if pair(W, pk["A0"]) != pair(Y, pk["h"][0]):
        return False
    cg = pk["C"] * (pk["g"] ** _mu(msg, policy, curve))
    one = pair(grp.init(G1, 1), grp.init(G2, 1))
    for j in range(1, t + 1):
        lhs = one
        for i, label in enumerate(labels):
            m_ij = rows[i][j - 1]
            if m_ij:
                ab = public.ab(j, label)
                lhs = lhs * pair(S[i], ab if m_ij == 1 else ab ** _zr(m_ij, curve))
        rhs = pair(cg, P[j - 1])
        if j == 1:
            rhs = pair(Y, pk["h"][1]) * rhs
        if lhs != rhs:
            return False
    return True


def _pack(grp, elems) -> bytes:
    """Group elements, each as (type tag, length, Charm serialisation)."""
    out = [struct.pack(">H", len(elems))]
    for e in elems:
        blob = grp.serialize(e)
        out.append(struct.pack(">H", len(blob)) + blob)
    return b"".join(out)


def _unpack(grp, data: bytes, kinds=None):
    """Parse a signature. Each element must carry its group's tag ('1:' G1, '2:' G2, as `kinds`) and
    must not be the identity: Charm does not decode the all-zero point back to the identity, and
    pairing such a value crashes the process, so a hostile CS input could otherwise stop the DO."""
    import base64
    (n,), pos, elems = struct.unpack_from(">H", data, 0), 2, []
    if kinds is not None and n != len(kinds):
        raise ValueError("wrong number of elements")
    for idx in range(n):
        (k,) = struct.unpack_from(">H", data, pos)
        pos += 2
        blob = data[pos:pos + k]
        pos += k
        if len(blob) != k or blob[1:2] != b":":
            raise ValueError("malformed element")
        if kinds is not None and blob[:1] != kinds[idx]:
            raise ValueError("element in the wrong group")
        if not any(base64.b64decode(blob[2:], validate=True)):
            raise ValueError("identity element")
        elems.append(grp.deserialize(blob))
    if pos != len(data):
        raise ValueError("trailing bytes")
    return elems


class AbsSigner:
    """A Data Owner's ABS signing state, with the same interface as the Ed25519 stand-in.

    The constructor plays the Domain Authority too (Setup + AttrGen for {domain:D, role:owner}), so
    Signer() keeps working in owner.py and bench/ without new arguments; each Signer() is one domain's
    authority, hence a key of another domain does not verify. Pass domain= to name the domain in Υ."""

    def __init__(self, domain: str = None, authority: AbsAuthority = None, attrs=None, policy: str = None):
        domain = domain or "default"
        self.authority = authority or AbsAuthority()
        self.attrs = [a.lower() for a in (attrs or owner_attributes(domain))]
        self.public = self.authority.public(policy or owner_policy(domain))
        self.key = self.authority.attr_gen(self.attrs)

    def sign(self, msg: bytes) -> bytes:
        return sign(self.public, self.key, msg, self.attrs)
