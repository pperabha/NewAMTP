"""Cryptographic primitives (all real, from the `cryptography` library).

  AES-GCM          document encryption E_d                     (real)
  AES-SIV          deterministic keyword encryption DEnc        (real)
  HMAC-SHA256      query authentication tag tau_Q               (real)
  Ed25519          owner signature σ_op (and σ_root in-process) (stand-in for ABS)
  MPR ABS          real ABS for σ_op = σ_d, core/abs.py         (AMTP_ABS=mpr)
  Policy key wrap  hides K_d behind an attribute policy         (stand-in for CP-ABE)
  BSW07 CP-ABE     real CP-ABE for K_d, core/cpabe.py           (AMTP_CPABE=bsw07)

About the two stand-ins (be explicit about this when presenting):
  * ABS is replaced by an ordinary Ed25519 signature: it proves "the Data Owner
    approved this root", but does not hide which owner signed.
  * CP-ABE is replaced by a policy-tree key wrap: each attribute has a secret
    key, AND splits K_d into XOR shares, OR copies it. A user without the right
    attributes really cannot unwrap K_d. Unlike real CP-ABE it is NOT
    collusion-resistant and the encryptor needs the attribute master secret.
    The full prototype should use a real scheme (e.g. FAME/BSW07 in Charm).
"""
import hmac
import hashlib
import json
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature, InvalidTag

from .boolean import parse
from .hashing import enc


# ---------- symmetric ----------

def aes_gcm_encrypt(key: bytes, plaintext: bytes, aad: bytes) -> dict:
    nonce = os.urandom(12)
    return {"N": nonce.hex(), "C": AESGCM(key).encrypt(nonce, plaintext, aad).hex()}


def aes_gcm_decrypt(key: bytes, box: dict, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(bytes.fromhex(box["N"]), bytes.fromhex(box["C"]), aad)


# ---------- outsourced object CT_d = <E_d, C_Kd, aad_d> (Phase 1, eq. 4) ----------

CT_MAGIC = b"AMTP-CT1"
_CT_FIELDS = 4          # N_d, C_d (ciphertext ‖ GCM tag), C_Kd, aad_d


def make_ct(k_d: bytes, plaintext: bytes, ck: dict, aad: dict) -> bytes:
    """Encrypt one document and return CT_d as raw bytes. aad_d is encoded once and the same
    bytes are both the AES-GCM associated data and the aad field of CT_d."""
    aad_b = enc(aad)
    return pack_ct(aes_gcm_encrypt(k_d, plaintext, aad_b), ck, aad_b)


def pack_ct(e: dict, ck: dict, aad_b: bytes) -> bytes:
    """CT_d bytes: CT_MAGIC, then N_d, C_d, C_Kd and aad_d, each with a 4-byte big-endian length.
    cid_d = H(CT_d) is computed over exactly these bytes."""
    out = [CT_MAGIC]
    for part in (bytes.fromhex(e["N"]), bytes.fromhex(e["C"]), enc(ck), aad_b):
        out += [len(part).to_bytes(4, "big"), part]
    return b"".join(out)


def unpack_ct(ct: bytes) -> dict:
    """Parse CT_d bytes into {"E": {"N", "C"}, "CK", "aad", "aad_b"}; raises ValueError if malformed."""
    if not isinstance(ct, bytes) or not ct.startswith(CT_MAGIC):
        raise ValueError("not an AMTP ciphertext")
    parts, i = [], len(CT_MAGIC)
    for _ in range(_CT_FIELDS):
        if i + 4 > len(ct):
            raise ValueError("truncated ciphertext")
        n = int.from_bytes(ct[i:i + 4], "big")
        i += 4
        if i + n > len(ct):
            raise ValueError("truncated ciphertext")
        parts.append(ct[i:i + n])
        i += n
    if i != len(ct):
        raise ValueError("trailing bytes in ciphertext")
    nonce, c, ck_b, aad_b = parts
    ck, aad = json.loads(ck_b), json.loads(aad_b)
    if not isinstance(ck, dict) or not isinstance(aad, dict):
        raise ValueError("malformed ciphertext fields")
    return {"E": {"N": nonce.hex(), "C": c.hex()}, "CK": ck, "aad": aad, "aad_b": aad_b}


def keyword_cipher(k_s: bytes, word: str) -> bytes:
    """C_w = DEnc_{K_s}(w) for an already normalised keyword (Norm is applied by
    owner.keyword_key). Same word + same key -> same ciphertext."""
    return AESSIV(k_s).encrypt(word.encode(), None)


def hmac_tag(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def hmac_ok(key: bytes, msg: bytes, tag: bytes) -> bool:
    return hmac.compare_digest(hmac_tag(key, msg), tag)


# ---------- signatures: σ_op (= σ_d of an upload) ----------

class Ed25519Signer:
    """The ABS stand-in: an ordinary Ed25519 key (AMTP_ABS=ed25519, the default)."""

    def __init__(self, domain: str = None):
        self._sk = Ed25519PrivateKey.generate()
        self.public = self._sk.public_key()

    def sign(self, msg: bytes) -> bytes:
        return self._sk.sign(msg)


def abs_kind(kind: str = None) -> str:
    kind = (kind or os.environ.get("AMTP_ABS", "ed25519")).lower()
    if kind not in ("ed25519", "mpr"):
        raise ValueError(f"unknown AMTP_ABS={kind!r} (use 'ed25519' or 'mpr')")
    return kind


def Signer(domain: str = None, kind: str = None):
    """A Data Owner's request signer: AMTP_ABS=mpr -> real ABS (Maji-Prabhakaran-Rosulek, core/abs.py,
    needs Charm; the constructor also runs the domain's ABS Setup + AttrGen); unset or 'ed25519' -> the
    Ed25519 stand-in. Both have .public and .sign(msg); sig_ok verifies either."""
    if abs_kind(kind) == "mpr":
        from .abs import AbsSigner
        return AbsSigner(domain)
    return Ed25519Signer(domain)


def sig_ok(public, msg: bytes, sig: bytes) -> bool:
    if type(public).__name__ == "AbsPublic":
        from .abs import verify
        return verify(public, msg, sig)
    if not isinstance(public, Ed25519PublicKey) or not isinstance(sig, (bytes, bytearray)):
        return False
    try:
        public.verify(sig, msg)
        return True
    except InvalidSignature:
        return False


# ---------- attribute policy key wrap (CP-ABE stand-in) ----------

class AttributeAuthority:
    """Plays the Domain Authority's role of issuing attribute keys."""

    def __init__(self):
        self._msk = os.urandom(32)

    def attribute_key(self, attr: str) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=b"attr:" + attr.lower().encode(),
        ).derive(self._msk)

    def user_keys(self, attrs) -> dict:
        return {a.lower(): self.attribute_key(a) for a in attrs}

    def wrap(self, secret: bytes, policy: str) -> dict:
        return self._wrap(secret, parse(policy))

    def _wrap(self, secret, node):
        if node[0] == "leaf":
            box = aes_gcm_encrypt(self.attribute_key(node[1]), secret, node[1].encode())
            return {"t": "attr", "a": node[1], **box}
        if node[0] == "OR":
            return {"t": "or", "k": [self._wrap(secret, c) for c in node[1]]}
        shares = [os.urandom(len(secret)) for _ in node[1][:-1]]
        last = secret
        for s in shares:
            last = bytes(x ^ y for x, y in zip(last, s))
        shares.append(last)
        return {"t": "and", "k": [self._wrap(s, c) for s, c in zip(shares, node[1])]}


def make_authority(kind: str = None):
    """The Domain Authority's CP-ABE: AMTP_CPABE=bsw07 -> real BSW07 (core/cpabe.py, needs Charm);
    unset or 'wrap' -> the policy key wrap above (the stand-in used for the paper's experiments)."""
    kind = (kind or os.environ.get("AMTP_CPABE", "wrap")).lower()
    if kind == "wrap":
        return AttributeAuthority()
    if kind == "bsw07":
        from .cpabe import CpAbeAuthority
        return CpAbeAuthority()
    raise ValueError(f"unknown AMTP_CPABE={kind!r} (use 'wrap' or 'bsw07')")


def unwrap(blob: dict, user_keys):
    """Return K_d, or None if the user's attributes do not satisfy the policy."""
    t = blob.get("t")
    if t == "bsw07":
        from .cpabe import unwrap as abe_unwrap
        return abe_unwrap(blob, user_keys)
    if not isinstance(user_keys, dict):
        return None
    if t == "attr":
        key = user_keys.get(blob["a"])
        if key is None:
            return None
        try:
            return aes_gcm_decrypt(key, blob, blob["a"].encode())
        except InvalidTag:
            return None
    parts = [unwrap(child, user_keys) for child in blob["k"]]
    if t == "or":
        return next((p for p in parts if p is not None), None)
    if any(p is None for p in parts):
        return None
    out = parts[0]
    for p in parts[1:]:
        out = bytes(x ^ y for x, y in zip(out, p))
    return out


__all__ = [
    "aes_gcm_encrypt", "aes_gcm_decrypt", "make_ct", "pack_ct", "unpack_ct", "CT_MAGIC",
    "keyword_cipher", "hmac_tag", "hmac_ok",
    "Signer", "sig_ok", "AttributeAuthority", "make_authority", "unwrap", "InvalidTag",
]
