"""Real CP-ABE for K_d (Phase 1, eq. 3): BSW07 [Bethencourt, Sahai, Waters, IEEE S&P 2007] from Charm.

C_Kd = CPABE.Enc(PK_i, K_d, A_d) is built as a KEM/DEM pair, because CP-ABE encrypts an element of
the target group G_T, not bytes:

    M <- G_T at random,  C_abe = BSW07.Enc(PK, M, A_d),  k = SHA-256(serialise(M)),
    C_Kd = <C_abe, AES-GCM_k(K_d)>.

A user whose attribute key satisfies A_d recovers M, then k, then K_d. BSW07 is collusion-resistant:
two users who each hold part of the policy cannot combine their keys (tests/test_cpabe.py).

The pairing arithmetic runs in the PBC and GMP C libraries; Charm is the Python binding. The curve
is SS512 (symmetric pairing), the same group the SE-COLLAB baseline uses.

Interface: same as the stand-in in crypto.py (AttributeAuthority.wrap / user_keys and unwrap), so
owner.py, user.py and the demo do not change. Select it with AMTP_CPABE=bsw07 (see make_authority).
"""
import base64
import hashlib

from cryptography.exceptions import InvalidTag

from .boolean import parse

SCHEME = "bsw07"
CURVE = "SS512"
_AAD = b"AMTP-CPABE-KEM"

_state = {}


def _charm():
    """Import Charm once (it is optional for the rest of AMTP)."""
    if not _state:
        from charm.core.engine.util import bytesToObject, objectToBytes
        from charm.schemes.abenc.abenc_bsw07 import CPabe_BSW07
        from charm.toolbox.pairinggroup import GT, PairingGroup

        group = PairingGroup(CURVE)
        _state.update(group=group, scheme=CPabe_BSW07(group), GT=GT,
                      to_b=objectToBytes, from_b=bytesToObject)
    return _state


def attribute_name(attr: str) -> str:
    """Charm attribute names may hold only letters and digits ('_' separates Charm's internal share
    index). Upper-case the attribute and escape every other character, and 'Q' itself, as 'Q' + two hex
    digits, so the mapping is one-to-one: 'lab_b' -> 'LABQ5FB', 'data-officer' -> 'DATAQ2DOFFICER'."""
    out = []
    for ch in attr.strip().upper():
        out.append(ch if ch.isascii() and ch.isalnum() and ch != "Q" else f"Q{ord(ch):02X}")
    return "".join(out)


def charm_policy(policy: str) -> str:
    """Translate an AMTP policy ('trial AND (budget OR ethics)', the Boolean grammar of core/boolean.py)
    into Charm's syntax ('(TRIAL and (BUDGET or ETHICS))')."""
    def walk(node):
        if node[0] == "leaf":
            value = node[1][1] if isinstance(node[1], tuple) else node[1]
            return attribute_name(value)
        op = " and " if node[0] == "AND" else " or "
        return "(" + op.join(walk(c) for c in node[1]) + ")"
    return walk(parse(policy))


class AttributeKey:
    """SK^cp of one Data User: a BSW07 secret key for a set of attributes."""

    def __init__(self, sk, attrs, pk):
        self.sk = sk
        self.attrs = tuple(attrs)
        self.pk = pk          # the domain's public parameters, needed by BSW07.Dec

    def __repr__(self):
        return f"AttributeKey({', '.join(self.attrs)})"


class CpAbeAuthority:
    """Domain Authority for CP-ABE: Setup (PK, MSK), KeyGen for users, Enc for owners."""

    scheme = SCHEME

    def __init__(self):
        c = _charm()
        self._c = c
        self.pk, self._msk = c["scheme"].setup()

    def user_keys(self, attrs) -> AttributeKey:
        names = sorted({attribute_name(a) for a in attrs})
        return AttributeKey(self._c["scheme"].keygen(self.pk, self._msk, names), names, self.pk)

    def wrap(self, secret: bytes, policy: str) -> dict:
        """C_Kd for K_d = secret under access policy A_d. JSON-safe (stored inside CT_d)."""
        from .crypto import aes_gcm_encrypt          # local import: crypto.py imports this module
        c = self._c
        m = c["group"].random(c["GT"])
        ct = c["scheme"].encrypt(self.pk, m, charm_policy(policy))
        dem = aes_gcm_encrypt(_kdf(c, m), secret, _AAD)
        return {"t": SCHEME, "abe": base64.b64encode(c["to_b"](ct, c["group"])).decode(), **dem}


def _kdf(c, m) -> bytes:
    return hashlib.sha256(b"AMTP-CPABE-K\x00" + c["group"].serialize(m)).digest()


def unwrap(blob: dict, key):
    """K_d, or None if the key's attributes do not satisfy the policy (or the blob is not valid)."""
    from .crypto import aes_gcm_decrypt
    if not isinstance(key, AttributeKey) or blob.get("t") != SCHEME:
        return None
    c = _charm()
    try:
        ct = c["from_b"](base64.b64decode(blob["abe"]), c["group"])
        m = c["scheme"].decrypt(key.pk, key.sk, ct)
    except Exception:            # malformed ciphertext from an untrusted source
        return None
    if m is False or m is None:  # Charm returns False when the attributes do not satisfy the policy
        return None
    try:
        return aes_gcm_decrypt(_kdf(c, m), blob, _AAD)
    except (InvalidTag, ValueError, KeyError):
        return None
