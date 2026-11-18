"""Phase 2 update protocol: shared encodings for the Cloud Server and the validating Data Owner.

  U_op   signed insert / delete request (eq. 8-11)         enc_request, request_digest
  Aff_i  affected-state descriptor (eq. 26, 45)             aff_records, enc_aff
  Δ_i    authenticated update-delta commitment (eq. 27)      delta
  R^(0)  genesis Domain Root anchored at setup (eq. 1)       genesis_root

Both sides build Aff_i with aff_records, so an honest server and the validator produce the same
bytes and therefore the same Δ_i.
"""
from .core.hashing import (H, TAG_AFF, TAG_DELTA, TAG_REQUEST, TAG_REQUESTS, cid_bytes, lp)
from .core.merkle import merkle_root
from .index import EMPTY_SLOT, SENTINEL_HI, SENTINEL_LO, ZERO, domain_root, imt_leaf


# ------------------------------------------------------------ requests U_op
def enc_request(u: dict) -> bytes:
    """U_ins = <i, insert, e*, η, id_d, CT_d, C(d)>,  U_del = <i, delete, e*, η, id_d, cid_d>  (eqs. (8), (10) of (32)).
    The placement group is not part of U_op and is not signed: it is a hint to the CS's placement policy
    (request field "bucket", next to "U" and "sig"); no verification step depends on it."""
    if u["op"] == "insert":
        c = sorted(u["C"])
        return lp(TAG_REQUEST, u["domain"], "insert", u["epoch"], bytes.fromhex(u["nonce"]), u["id"],
                  u["ct"], len(c), *c)
    if u["op"] == "delete":
        return lp(TAG_REQUEST, u["domain"], "delete", u["epoch"], bytes.fromhex(u["nonce"]), u["id"],
                  cid_bytes(u["cid"]))
    raise ValueError(f"unknown operation {u['op']!r}")


def request_digest(u: dict) -> bytes:
    """H(U_op): the digest signed as σ_op."""
    return H(enc_request(u))


def requests_digest(requests) -> bytes:
    """H over the epoch's batch of requests, in order (b = 1 is a single request)."""
    return H(TAG_REQUESTS, *[request_digest(r["U"]) for r in requests])


# ------------------------------------------------------------ Aff_i
def aff_records(ops, structs, moves, parts_changed, parts_new, parts_retired) -> list:
    """Canonical Aff_i: the logical operations in order (kind, cid, PID, ℓ), the restructuring
    records in order, the relocations Move_i sorted by cid (start location -> final location),
    then the partition-state changes sorted by PID."""
    out = [("op", k, cid, pid, slot) for k, cid, pid, slot in ops]
    out += [tuple(s) for s in structs]
    out += [("move", cid, a[0], a[1], b[0], b[1]) for cid, (a, b) in sorted(moves.items())]
    out += [("part", pid, v0, v1) for pid, (v0, v1) in sorted(parts_changed.items())]
    out += [("new", pid, v) for pid, v in sorted(parts_new.items())]
    out += [("retired", pid, v) for pid, v in sorted(parts_retired.items())]
    return out


def enc_aff(records) -> bytes:
    return lp(TAG_AFF, len(records), *[lp(*r) for r in records])


def delta(domain, epoch_new, requests, aff_bytes, r_old: bytes, r_new: bytes) -> bytes:
    """Δ_i = H(i ‖ e' ‖ H(U_op) ‖ H(Aff_i) ‖ R^(e) ‖ R^(e'))."""
    return H(TAG_DELTA, domain, epoch_new, requests_digest(requests), H(aff_bytes), r_old, r_new)


# ------------------------------------------------------------ genesis
def genesis_roots(pids):
    """(R^part(0), R^idx(0)) for initial empty partitions `pids` and the sentinel-only index."""
    r_part = merkle_root([H(pid, 0, merkle_root([])) for pid in sorted(pids)])
    r_idx = merkle_root([imt_leaf(SENTINEL_LO, ZERO, SENTINEL_HI)])
    return r_part, r_idx


def genesis_root(domain, pids) -> bytes:
    """R^(0)_D = H(i ‖ 0 ‖ R^part(0) ‖ R^idx(0)) (eq. 1)."""
    return domain_root(domain, 0, *genesis_roots(pids))


__all__ = ["enc_request", "request_digest", "requests_digest", "aff_records", "enc_aff", "delta",
           "genesis_root", "genesis_roots", "EMPTY_SLOT"]
