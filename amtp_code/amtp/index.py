"""Domain state: partitions, Search Tree postings, PAPC and IMT (Phases 2-3).

DomainState is the Cloud Server's read-only query snapshot of one finalized epoch. The Engine
(engine.py) maintains the commitments incrementally and the owner's Validator checks each
transition on its dirty paths; Engine.snapshot() then rebuilds this snapshot in full and the
server checks that its R_D equals the incremental one.
"""
import gc
import hashlib
import os
import re
from dataclasses import dataclass, field

from .bptree import BPlusTree
from .core.hashing import TAG_POSTING, H, HashCounter, enc_posting
from .cuckoo import CuckooFilter
from .core.merkle import MerkleTree, merkle_root

EMPTY_SLOT = b""
SENTINEL_LO = b"\x00" * 32
SENTINEL_HI = b"\xff" * 32
ZERO = b"\x00" * 32

STOPWORDS = set("""
a an and are as at be been but by for from has have in into is it its of on or
our the their this to was were will with we after before during under over per
all any can more most new not no only other same than then these those very
""".split())


def extract_keywords(text: str) -> set:
    """Simple keyword extractor for the demo (the prototype uses RAKE)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS and not w.isdigit()}


@dataclass
class Partition:
    pid: str
    v: int
    slots: list = field(default_factory=list)  # slot ℓ -> cid (bytes) or EMPTY_SLOT

    @property
    def count(self) -> int:
        return sum(1 for s in self.slots if s != EMPTY_SLOT)

    def tree(self) -> MerkleTree:
        return MerkleTree(self.slots)


# γ with or without the partition version v (study B4). Default: with v, the paper's definition.
# AMTP_GAMMA_V=0 in the environment (or set_gamma_v(False) before any Engine / Validator / DataUser is built)
# gives γ = H(PID ‖ H(Enc(L))): a version bump then changes only the partition leaf A_j, not every γ of the
# partition. Server, Validator and user must use the same setting (one process, one setting).
_GAMMA_V = os.environ.get("AMTP_GAMMA_V", "1") != "0"


def set_gamma_v(on: bool) -> None:
    global _GAMMA_V
    _GAMMA_V = bool(on)


def gamma_has_v() -> bool:
    return _GAMMA_V


# AND pruning (study, default off): the server answers an AND with the full posting list of one keyword
# and, for every other keyword, only its components in the partitions that list covers (amtp/server.py).
# AMTP_AND_PRUNE=1 in the environment, or set_and_prune(True) before the snapshots are built. The user
# accepts both answer forms whatever this setting is (amtp/user.py).
_AND_PRUNE = os.environ.get("AMTP_AND_PRUNE", "0") == "1"


def set_and_prune(on: bool) -> None:
    global _AND_PRUNE
    _AND_PRUNE = bool(on)


def and_prune_on() -> bool:
    return _AND_PRUNE


# AND pruning planner (study, default off): besides the keyword with the fewest partitions, send more
# keywords in full when that shrinks the focus set enough to lower the proof (amtp/server.py _grow_full).
# Server choice only; the user's check is the same. AMTP_AND_GREEDY=1 or set_and_plan_greedy(True).
_AND_GREEDY = os.environ.get("AMTP_AND_GREEDY", "0") == "1"


def set_and_plan_greedy(on: bool) -> None:
    global _AND_GREEDY
    _AND_GREEDY = bool(on)


def and_plan_greedy_on() -> bool:
    return _AND_GREEDY


# Result-only partition check (study, default off): the server opens partition slots and domain-tree leaves
# only for the returned files; the versions v of the other covered partitions travel as a plain list and are
# bound by γ = H(PID ‖ v ‖ H(Enc(L))). AMTP_PART_RESULTS=1 or set_part_results(True). The user accepts both
# answer forms whatever this setting is (amtp/user.py).
_PART_RESULTS = os.environ.get("AMTP_PART_RESULTS", "0") == "1"


def set_part_results(on: bool) -> None:
    global _PART_RESULTS
    _PART_RESULTS = bool(on)


def part_results_on() -> bool:
    return _PART_RESULTS


# Search Tree leaf by partition (study, default off): the leaf of a keyword in at least KEEP_MIN_PARTS partitions
# also keeps the set of its partitions and where each partition's component sits in the list (PartPosting), so
# a query reads them instead of rebuilding them from the list. Same list, same answers, same proof bytes; the
# Search Tree is not evidence. AMTP_PART_LEAF=1 or set_part_leaf(True) before the snapshots are built.
_PART_LEAF = os.environ.get("AMTP_PART_LEAF", "0") == "1"


def set_part_leaf(on: bool) -> None:
    global _PART_LEAF
    _PART_LEAF = bool(on)


def part_leaf_on() -> bool:
    return _PART_LEAF


class PartPosting(list):
    """A Search Tree leaf: the same list [(PID, [(cid, ℓ), ...]), ...] in PID order, plus
    pids = frozenset of its PIDs and at = {PID: position of that PID's component in the list}.
    Built once with the snapshot; never sent and never trusted by the user."""
    __slots__ = ("pids", "at")

    def __init__(self, entries):
        super().__init__(entries)
        self.at = {pid: j for j, (pid, _) in enumerate(self)}
        self.pids = frozenset(self.at)


_U64_MAX = (1 << 64) - 1
_LEN8 = (8).to_bytes(4, "big")
_LEN32 = (32).to_bytes(4, "big")


def gamma_wire(pid: str, v: int, component) -> bytes:
    """γ of a posting component as it arrives on the wire (cid hex or bytes, slot int): the SAME bytes, the
    same input checks (ValueError on a bad cid or slot) and the same HashCounter counts as gamma(), without
    the generic per-part encoding of H. Used in the user's PAPC check (the hot loop); falls back to gamma()
    for γ without v or a non-string PID."""
    if not _GAMMA_V or type(pid) is not str or type(v) is not int or v < 0 or v > _U64_MAX:
        return gamma(pid, v, component)
    parts = [TAG_POSTING, len(component).to_bytes(8, "big")]
    for cid, slot in component:
        b = bytes.fromhex(cid) if isinstance(cid, str) else cid
        if not isinstance(b, bytes) or len(b) != 32:
            raise ValueError("cid must be 32 bytes")
        if type(slot) is not int or slot < 0:
            raise ValueError(f"expected a non-negative integer, got {slot!r}")
        parts.append(b)
        parts.append(slot.to_bytes(8, "big"))
    enc = b"".join(parts)
    inner = hashlib.sha256(len(enc).to_bytes(4, "big") + enc).digest()       # H(Enc(L))
    p = pid.encode("utf-8")
    g = hashlib.sha256(len(p).to_bytes(4, "big") + p + _LEN8 + v.to_bytes(8, "big") + _LEN32 + inner).digest()
    HashCounter.calls += 2
    HashCounter.bytes += (4 + len(enc)) + (4 + len(p) + 4 + 8 + 4 + 32)
    return g


def gamma_inner(pid: str, v: int, inner: bytes) -> bytes:
    """γ from its inner hash H(Enc(L)): H(PID ‖ v ‖ inner), or H(PID ‖ inner) when γ leaves v out"""
    return H(pid, v, inner) if _GAMMA_V else H(pid, inner)


def gamma(pid: str, v: int, component) -> bytes:
    """γ_{w,j} = H(PID ‖ v ‖ H(Enc(L_{w,j}))) with the binary posting encoding enc_posting
    (entries (cid, ℓ) in slot order; cid as bytes or hex). Without v: see set_gamma_v."""
    return gamma_inner(pid, v, H(enc_posting(component)))


def rho(h: bytes, n_sel: int, r_post: bytes) -> bytes:
    """ρ_w = H(h_w ‖ |Sel(h_w)| ‖ R^post)  (written σ_h in AMTP_6)"""
    return H(h, n_sel, r_post)


def imt_leaf(h: bytes, r: bytes, nxt: bytes) -> bytes:
    """I_w = H(h_w ‖ ρ_w ‖ next(h_w)): indexed Merkle tree leaf. next(h_w) is the smallest
    indexed key above h_w (SENTINEL_HI for the largest key), so a single authenticated
    leaf with h_lo < h < next(h_lo) proves that h is not indexed."""
    return H(h, r, nxt)


IMT_EMPTY = H("imt-empty")      # value of a freed IMT position (deleted key)


def sorted_imt_layout(keys) -> list:
    """Initial IMT layout: lower sentinel, then the keys in ascending order.
    Later keys are appended (or fill freed positions), so positions are NOT sorted."""
    return [SENTINEL_LO] + sorted(keys)


def imt_next(keys) -> dict:
    """next(h) for the lower sentinel and every key, from the sorted key list."""
    order = [SENTINEL_LO] + sorted(keys) + [SENTINEL_HI]
    return {order[i]: order[i + 1] for i in range(len(order) - 1)}


KEEP_MIN_PARTS = 3      # AND pruning: keep R^post data for keywords in at least this many partitions


class DomainState:
    """One finalized snapshot of a domain at one epoch."""

    def __init__(self, domain: str, epoch: int, partitions, fwd: dict, imt_layout=None):
        self.domain = domain
        self.epoch = epoch
        self.partitions = partitions            # ordered: position in partition tree
        self.fwd = fwd                          # cid -> set of keyword keys h
        self.imt_layout = imt_layout            # IMT position -> key h / None (freed); None = sorted
        # The build allocates millions of lists and dicts and creates no reference cycles; the cyclic GC would
        # rescan them over and over (measured: +26% build time with AND pruning, N = 50k). Pause it here;
        # reference counting still frees everything as usual.
        paused = gc.isenabled()
        gc.disable()
        try:
            self._build()
        finally:
            if paused:
                gc.enable()

    def _build(self):
        # Loc_i: where every cid lives
        self.loc = {}
        self.part_trees = {}
        for p in self.partitions:
            self.part_trees[p.pid] = p.tree()
            for slot, cid in enumerate(p.slots):
                if cid != EMPTY_SLOT:
                    self.loc[cid] = (p.pid, slot)
        self.by_pid = {p.pid: p for p in self.partitions}
        self.part_pos = {p.pid: i for i, p in enumerate(self.partitions)}

        # Partition tree: leaves A_{i,j} = H(PID ‖ v ‖ R_P)
        self.A = [H(p.pid, p.v, self.part_trees[p.pid].root) for p in self.partitions]
        self.part_tree = MerkleTree(self.A)

        # Search Tree postings: h -> [(PID, [(cid, ℓ), ...]), ...]
        groups = {}
        for cid, keys in self.fwd.items():
            pid, slot = self.loc[cid]
            for h in keys:
                groups.setdefault(h, {}).setdefault(pid, []).append((cid, slot))
        # B+ Search Tree T^S_i over the protected keys, plus the Cuckoo filter in front of it
        by_part = part_leaf_on()

        def leaf(h):
            L = [(pid, sorted(entries, key=lambda e: e[1])) for pid, entries in sorted(groups[h].items())]
            return PartPosting(L) if by_part and len(L) >= KEEP_MIN_PARTS else L
        self.postings = BPlusTree.from_sorted((h, leaf(h)) for h in sorted(groups))
        self.cuckoo = CuckooFilter.from_keys(self.postings.keys())

        # PAPC per keyword, then the indexed IMT: leaf H(h ‖ ρ ‖ next(h)) at its position
        self.rho = {}
        # AND pruning only: for every keyword in at least KEEP_MIN_PARTS partitions, the R^post tree, the inner
        # hashes H(Enc(L_j)) of its components (the neighbour preimages of a focus proof) and its number of
        # postings. Index data built with the snapshot (same work as the γ below), not a cache filled by
        # queries. Smaller keywords (most of them: the median keyword is in one file) are rebuilt on demand
        # in a few hashes; keeping them would cost several Python objects each.
        self._post_trees, self._post_inner, self._post_count = {}, {}, {}
        keep = and_prune_on()
        for h, L in self.postings.items():
            if keep and len(L) >= KEEP_MIN_PARTS:
                tree, inners, count = self._post_parts(L)
                self._post_trees[h], self._post_inner[h], self._post_count[h] = tree, inners, count
                r_post = tree.root
            else:
                r_post = merkle_root([gamma(pid, self.by_pid[pid].v, comp) for pid, comp in L])
            self.rho[h] = rho(h, len(L), r_post)
        layout = self.imt_layout or sorted_imt_layout(self.rho)
        if set(layout) - {None, SENTINEL_LO} != set(self.rho) or layout[0] != SENTINEL_LO:
            raise ValueError("IMT layout does not hold exactly the indexed keys")
        self.imt_next = imt_next(self.rho)
        self.imt_rho = {**self.rho, SENTINEL_LO: ZERO}
        self.imt_pos = {h: i for i, h in enumerate(layout) if h is not None}
        self.imt_n = len(layout)
        self.imt = MerkleTree([IMT_EMPTY if h is None else imt_leaf(h, self.imt_rho[h], self.imt_next[h])
                               for h in layout])

        self.R_part = self.part_tree.root
        self.R_idx = self.imt.root
        self.R_D = domain_root(self.domain, self.epoch, self.R_part, self.R_idx)

    def post_tree(self, h: bytes) -> MerkleTree:
        """The R^post tree of keyword h (γ in PID order): kept from the build (AND pruning, keyword in at least
        KEEP_MIN_PARTS partitions), otherwise rebuilt here from the snapshot's own postings (not kept)."""
        tree = self._post_trees.get(h)
        return tree if tree is not None else self._post_parts(self.postings[h])[0]

    def post_inner(self, h: bytes) -> list:
        """H(Enc(L_j)) of every component of keyword h, in PID order (see post_tree)."""
        inner = self._post_inner.get(h)
        return inner if inner is not None else self._post_parts(self.postings[h])[1]

    def post_count(self, h: bytes) -> int:
        """Number of postings (files) of keyword h."""
        n = self._post_count.get(h)
        return n if n is not None else sum(len(comp) for _, comp in self.postings[h])

    def _post_parts(self, L):
        inners = [H(enc_posting(comp)) for _, comp in L]
        tree = MerkleTree([gamma_inner(pid, self.by_pid[pid].v, x) for (pid, _), x in zip(L, inners)])
        return tree, inners, sum(len(comp) for _, comp in L)


def domain_root(domain: str, epoch: int, r_part: bytes, r_idx: bytes) -> bytes:
    """R_D^(e) = H(i ‖ e ‖ R^part ‖ R^idx)"""
    return H(domain, epoch, r_part, r_idx)
