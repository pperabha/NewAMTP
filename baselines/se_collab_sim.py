"""
se_collab_sim.py
============================================================================
Simulation of the baseline SE-COLLAB [37]
  S. Fugkeaw, J. Deevijit,
  "SE-COLLAB: Achieving Fine-Grained and Efficiently Verifiable Searchable
   Encryption With Boolean Multi-Keyword Search for Collaborative IIoT Data Sharing",
  IEEE Access, vol. 13, pp. 126012-126029, 2025. doi:10.1109/ACCESS.2025.3590026

This code follows the paper's Section IV-B (Phases 1-8):
  A. Trapdoor Transformation                (Algorithm 1 — Cloud Proxy, PRE)
  B. Secure Search Execution                (Algorithm 2 — BPL bitwise AND/OR/NOT)
  C. Result verification                    (Phase 6 — Merkle path + result proof)
It uses the same libraries as the paper (Charm-Crypto abenc_bsw07 + PyCryptodome).

Seven parties (Fig. 1): Attribute Authority (AA), Data Owner (DO) + Edge Proxy, Data User (DU),
                       Cloud Proxy, Cloud Storage, Blockchain

Measured for the comparison with AMTP (AMTP's Table IV):
  - Query Generation : 3 T_E + T_P                  (the trapdoor does not depend on the number of keywords)
  - Search           : j T_B                         (bitwise AND/OR/NOT on the BPL)
  - Verification     : T_E + T_P + t_leaf T_H        (Merkle paths of the results + result proof)
  - Update           : N/A                           (the paper defines no dynamic update)
  -> used in Experiment 1 (AND/OR/nested) and Experiment 2 (proof / verification)

Points the paper leaves unclear or gets wrong, decided here (see the [ASSUMPTION]/[FIX] comments);
every one keeps the paper's operation counts:
  1. [ASSUMPTION] no pairing group stated -> Charm SS512 (the default of abenc_bsw07)
  2. [FIX] C3 = g^{αr} needs g^α (the master key), which the DU does not have -> the DU holds its own s_u, C3 = PK_DU^r;
           the paper does not say how the proxy reads W_q -> C2 = hashed ElGamal with the key KDF(PK_Cloud^r)
  3. [ASSUMPTION] ExtractKeyword(T'q) -> the token I(w) = PRF(SymK_DO, w) is in C2;
           the DU gets SymK_DO by decrypting CT_key with CP-ABE
  4. [FIX] the printed ZKP check equations do not balance (δ' lacks W_q,B_q; V2' does not match V2)
           -> Chaum-Pedersen DLEQ NIZK (Fiat-Shamir); the signature σ = Schnorr in G1
  5. [ASSUMPTION] Algorithm 1 (PRE) is applied literally to C3; C2 is re-encrypted under the new key
  6. [ASSUMPTION] "ZKP over (T'q, R)" in Phase 6 -> the proxy's Schnorr proof (2 exp instead of TE+TP);
           the paper's Fig. 6 numbers correspond to the merkle_verify_ms column
  7. [ASSUMPTION] Blockchain = a simulated hash-chained ledger instead of Ganache/Web3
  8. [ASSUMPTION] Revocation: one CT_key per DO -> lazy re-encryption = one new encapsulation
           with a bumped attribute version
  9. [ASSUMPTION] BSW07 is single-authority per ciphertext -> one DO bound to one AA
 10. [ASSUMPTION] large N: the BPL of keywords with df < N/64 is stored as postings and converted at query time
 11. [ASSUMPTION] dataset keywords are multi-word phrases -> adjacent words in a query (no AND/OR/NOT between)
     form one keyword, e.g. "general method AND possible description" = 2 keywords
 12. [ASSUMPTION] cross-domain search: Phase 4 Step 1 lets the DU combine keys of several AAs into one trapdoor, and
     Tq = (g^r, H(Wq,Bq)e(g,g)^{ar}, PK^r) has no DO-specific part -> trapdoor / signature / NIZK / proxy check /
     PRE transform happen once per query (Table 4: TrapGen = 3E + Pe), while C2 carries the token I(w) of every owner
     (following item 3); the proxy then searches the index + builds the Merkle proof per owner and signs the
     combined result once (Phase 6 Step 3: Verify(pi, T'q, R)); the DU checks the Merkle root per owner
 13. [FIX] the proxy does not check the binding with a pairing (the paper's Phase 4 Step 2 checks only the signature
     + ZKP; Table 4 has P_e only in TrapGen) -> one pairing per query on the DU side, as TrapGen = 3E + P_e
 14. --proof-mode defaults to paths (one Merkle path per file, which can point to the tampered file, as in Phase 6);
     multi (multiproof) is an optimisation not in the paper, used only when requested
 15. the implemented verification cost = Merkle + Schnorr (2E), while the paper's Table 4 writes E + P_e + f_ct H
     without explaining "ZKP over (T'q, R)" -> no pairing without a purpose is added, so our verification is a
     lower bound
Note: the paper does not use the index Merkle root when checking results -> omitted results are not detected
(the paper's behaviour, not a simulation bug; selftest t_omission_not_detected)

Workload: AMTP's shared dataset (dataset-v4, arXiv 4 domains x 125,000 files, parts in datasets/arxiv/data_v4/)
through amtp_dataset.py
  - N documents = the first N/4 files of each domain (no randomness) -> every scheme gets the same documents
  - keywords are the ones stored in documents.csv; the encrypted contents are the real .txt files
  - exp1 checks every query against the ground truth of a plaintext index (must match exactly)
  - demo / selftest / paper / revocation use a synthetic corpus (they run without the dataset)

Run (install Charm-Crypto first, see baselines/README.md):
  python3 se_collab_sim.py demo                 # step by step on a small example
  python3 se_collab_sim.py selftest             # 18 correctness tests
  python3 se_collab_sim.py paper                # reproduce the paper's Figs. 2-6 (sanity check)
  python3 se_collab_sim.py exp1                 # replay results/exp1_queries.json (N = 10k..200k)
  python3 se_collab_sim.py exp2                   # replays results/exp2_layouts.json (N = 200k)
  python3 se_collab_sim.py exp5                   # replays results/exp5_workload.json (1 owner = 1 domain)
  python3 se_collab_sim.py revocation
Every suite writes results/secollab/secollab_<suite>.csv (mean, median, std over --reps runs after --warmup
warm-up runs), with the same columns as chen_et_al_sim.py
============================================================================
"""

# ----------------------------------------------------------------------------- imports
from __future__ import annotations

import argparse  # command-line arguments
import csv  # write results as CSV
import gc  # garbage collector off while timing
import hashlib  # SHA-256
import hmac  # HMAC (the PRF)
import json  # read/write query files
import math  # Bloom filter parameters
import os  # os.urandom() for keys + paths
import re  # tokenising / policy rewriting
import statistics as st  # mean / median / std
import struct  # length prefix in hashes
import sys  # path for importing amtp_dataset.py + sys.exit in the selftest
import time  # timing
from collections import Counter, defaultdict  # frequency counts / dict with defaults
from dataclasses import dataclass, field  # record classes
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np  # BPL bit vectors
from Crypto.Cipher import AES  # AES-CBC / AES-ECB (PyCryptodome, as in the paper)
from Crypto.Util.Padding import pad, unpad  # PKCS#7
from charm.schemes.abenc.abenc_bsw07 import CPabe_BSW07  # BSW07 CP-ABE (as in the paper)
from charm.toolbox.pairinggroup import GT, ZR, PairingGroup, pair  # bilinear pairing


# ============================================================================
# 1) Cryptographic primitives — hash, PRF, AES, PRP, Bloom filter, Merkle tree
# ============================================================================

# ---------------------------------------------------------------- hashing
def H(*parts: bytes, tag: bytes = b"") -> bytes:
    """Hash of several length-prefixed pieces (each piece prefixed with its length),
    so the concatenation is unambiguous, e.g. H("ab","c") != H("a","bc")."""
    h = hashlib.sha256()
    h.update(tag)                              # tag separating uses, e.g. b"PRF", b"AES", b"TQ"
    for p in parts:
        h.update(struct.pack(">I", len(p)))    # 4-byte length prefix
        h.update(p)
    return h.digest()


def prf(key: bytes, msg: bytes) -> bytes:
    """PRF = HMAC-SHA256, deterministic: the same key + the same keyword -> the same token
    (which is why the cloud can match keywords, and also why repeated queries are visible = leakage)."""
    return hmac.new(key, msg, hashlib.sha256).digest()


# ---------------------------------------------------------------- AES
def aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """AES-CBC encryption with a fresh random IV, prepended to the ciphertext."""
    iv = os.urandom(16)
    return iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext, 16))


def aes_decrypt(key: bytes, blob: bytes) -> bytes:
    """Decrypt: split off the IV (first 16 bytes), then unpad; a wrong key makes unpad raise ValueError."""
    iv, ct = blob[:16], blob[16:]
    return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)


class PRP:
    """Deterministic Enc(id) for the inverted index (one AES-ECB block).
    ECB is fine because the input is a single block and ids are unique."""

    def __init__(self, key: bytes):
        self._c = AES.new(key, AES.MODE_ECB)

    def enc_id(self, doc_id: int) -> bytes:
        return self._c.encrypt(doc_id.to_bytes(16, "big"))


# ---------------------------------------------------------------- Bloom
class BloomFilter:
    """Bloom filter: "definitely absent" is always right, "maybe present" can be a false positive
    -> SE-COLLAB Phase 8: check the Bloom filter first, and only on a hit ask the smart contract to be sure."""

    def __init__(self, capacity: int = 10_000, error_rate: float = 1e-4):
        # standard formula: m = -n ln(p) / (ln2)^2 bits, k = (m/n) ln2 hash functions
        m = math.ceil(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.m = max(8, m)
        self.k = max(1, round(self.m / capacity * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8)

    def _idx(self, item: bytes) -> Iterable[int]:
        # double hashing: k positions from two hash values (h1 + i*h2) instead of k separate hashes
        d = hashlib.sha256(item).digest()
        h1 = int.from_bytes(d[:8], "big")
        h2 = int.from_bytes(d[8:16], "big") | 1
        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def add(self, item: bytes) -> None:
        for i in self._idx(item):
            self.bits[i >> 3] |= 1 << (i & 7)       # set bit i

    def __contains__(self, item: bytes) -> bool:
        # every position must be 1 for "maybe present"
        return all(self.bits[i >> 3] & (1 << (i & 7)) for i in self._idx(item))


# ---------------------------------------------------------------- Merkle
# prefixes separate leaves from internal nodes (prevents second-preimage attacks passing an internal node off as a leaf)
LEAF, NODE = b"\x00", b"\x01"


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(LEAF + data).digest()


def node_hash(l: bytes, r: bytes) -> bytes:
    return hashlib.sha256(NODE + l + r).digest()


class MerkleTree:
    """
    Merkle tree stored as a list of levels: levels[0] = leaves, levels[-1] = [root].
    A level with an odd number of nodes hashes its last node with itself.
    Supports:
      - update_leaf : update one leaf and recompute only the affected branch (SE-COLLAB Phase 6 Step 1)
      - proof       : the authentication path of one leaf (log n values)
      - multiproof  : one proof for several leaves sharing nodes (smaller when the leaves are close)
    """

    def __init__(self, leaf_data: Sequence[bytes] = (), prehashed: bool = False):
        leaves = list(leaf_data) if prehashed else [leaf_hash(d) for d in leaf_data]
        self.levels: List[List[bytes]] = [leaves]
        self._build()

    def _build(self) -> None:
        """Build every level from the leaves up to the root."""
        lvl = self.levels[0]
        self.levels = [lvl]
        while len(lvl) > 1:
            nxt = [node_hash(lvl[i], lvl[i + 1] if i + 1 < len(lvl) else lvl[i])
                   for i in range(0, len(lvl), 2)]
            self.levels.append(nxt)
            lvl = nxt

    @property
    def root(self) -> bytes:
        if not self.levels[0]:
            return hashlib.sha256(b"EMPTY").digest()   # root of an empty tree
        return self.levels[-1][0]

    def __len__(self) -> int:
        return len(self.levels[0])

    # ---- incremental update: only O(log n) hashes
    def update_leaf(self, idx: int, data: bytes) -> bytes:
        """Change the leaf at idx, then recompute the parents level by level up to the root."""
        self.levels[0][idx] = leaf_hash(data)
        for lv in range(len(self.levels) - 1):
            cur = self.levels[lv]
            p = idx // 2                                   # parent position
            l = cur[2 * p]
            r = cur[2 * p + 1] if 2 * p + 1 < len(cur) else l
            self.levels[lv + 1][p] = node_hash(l, r)
            idx = p
        return self.root

    # ---- proofs
    def proof(self, idx: int) -> List[Tuple[bool, bytes]]:
        """Authentication path: list of (sibling on the right?, sibling hash) from the leaf up to below the root."""
        path = []
        for lv in range(len(self.levels) - 1):
            cur = self.levels[lv]
            sib = idx ^ 1                                  # sibling = flip the last bit
            sib_h = cur[sib] if sib < len(cur) else cur[idx]
            path.append((sib > idx or sib >= len(cur), sib_h))
            idx //= 2
        return path

    def multiproof(self, idxs: Iterable[int]) -> Dict[Tuple[int, int], bytes]:
        """Multiproof: only the siblings the verifier cannot compute itself {(level, position): hash}.
        When two leaves are siblings of each other no sibling is sent -> a smaller proof."""
        known = set(idxs)
        out: Dict[Tuple[int, int], bytes] = {}
        for lv in range(len(self.levels) - 1):
            cur = self.levels[lv]
            nxt = set()
            for i in known:
                s = i ^ 1
                if s < len(cur) and s not in known:
                    out[(lv, s)] = cur[s]
                nxt.add(i // 2)
            known = nxt
        return out


def verify_path(leaf_h: bytes, idx: int, path: List[Tuple[bool, bytes]], root: bytes) -> bool:
    """DU side: recompute upward from the leaf hash + path and compare with the root (read from the blockchain).
    idx (the position) decides left/right -> the leaf's position is bound as well."""
    h = leaf_h
    for sib_right, sib in path:
        h = node_hash(h, sib) if (idx % 2 == 0) else node_hash(sib, h)
        idx //= 2
    return h == root


def verify_multiproof(leaves: Dict[int, bytes], n_leaves: int,
                      proof: Dict[Tuple[int, int], bytes], root: bytes) -> bool:
    """Check a multiproof: leaves = {position: leaf_hash}.
    Compute level by level, using self-computed values first and the proof otherwise; anything missing = fail."""
    cur = dict(leaves)
    width, lv = n_leaves, 0
    while width > 1:
        nxt = {}
        for i in sorted(cur):
            p = i // 2
            if p in nxt:
                continue
            l_i, r_i = 2 * p, 2 * p + 1
            l = cur.get(l_i, proof.get((lv, l_i)))
            if r_i < width:
                r = cur.get(r_i, proof.get((lv, r_i)))
            else:
                r = l                                   # the odd last node is hashed with itself
            if l is None or r is None:
                return False
            nxt[p] = node_hash(l, r)
        cur = nxt
        width = (width + 1) // 2
        lv += 1
    return cur.get(0) == root


# ============================================================================
# 2) Boolean queries — parse AND/OR/NOT and evaluate on the BPL
# ============================================================================

AST = Union[Tuple[str, str], Tuple[str, "AST"], Tuple[str, "AST", "AST"]]
_TOK = re.compile(r"\(|\)|\"[^\"]*\"|[^\s()]+")   # token = parenthesis, "quoted phrase", or a word without spaces/parentheses
_OPS = ("AND", "OR", "NOT", "(", ")")


def bool_parse(expr: str) -> AST:
    """Recursive-descent parser: each sub-function is one rule of the grammar above."""
    toks = _TOK.findall(expr)
    pos = 0

    def peek():
        # peek at the next token without advancing (upper-cased so and/And/AND are the same)
        return toks[pos].upper() if pos < len(toks) else None

    def take():
        nonlocal pos
        t = toks[pos]
        pos += 1
        return t

    def p_expr():                     # OR has the lowest precedence -> outermost level
        node = p_term()
        while peek() == "OR":
            take()
            node = ("OR", node, p_term())
        return node

    def p_term():                     # AND
        node = p_factor()
        while peek() == "AND":
            take()
            node = ("AND", node, p_factor())
        return node

    def p_factor():                   # NOT, parentheses, or a keyword
        t = peek()
        if t is None:
            raise ValueError("unexpected end of query")
        if t == "NOT":
            take()
            return ("NOT", p_factor())
        if t == "(":
            take()
            n = p_expr()
            if take() != ")":
                raise ValueError("missing ')'")
            return n
        if t in ("AND", "OR", ")"):
            raise ValueError(f"unexpected token {t}")
        # [ASSUMPTION] 11: adjacent words (no operator between) = one phrase keyword
        words = [take().strip('"')]
        while peek() is not None and peek() not in _OPS:
            words.append(take().strip('"'))
        return ("KW", " ".join(" ".join(words).split()).lower())   # normalise spaces + lower case

    ast = p_expr()
    if pos != len(toks):
        raise ValueError("trailing tokens")
    return ast


def bool_keywords(ast: AST) -> List[str]:
    """All distinct keywords of the AST (in order of appearance) = W_q in the paper."""
    out: List[str] = []

    def walk(n):
        if n[0] == "KW":
            if n[1] not in out:
                out.append(n[1])
        else:
            for c in n[1:]:
                walk(c)
    walk(ast)
    return out


def bool_map_leaves(ast: AST, f: Callable[[str], object]):
    """Replace every leaf by f(keyword), keeping the Boolean structure.
    Used when the DU turns plain keywords into PRF tokens  ('KW','pump') -> ('KW', PRF(K,'pump'))."""
    if ast[0] == "KW":
        return ("KW", f(ast[1]))
    return (ast[0],) + tuple(bool_map_leaves(c, f) for c in ast[1:])


def bool_canonical(ast: AST) -> str:
    """AST to one unambiguous string, e.g. AND(<hex>,OR(<hex>,<hex>)).
    Hashed as H(W_q, B_q) and sent in the trapdoor's C2."""
    if ast[0] == "KW":
        v = ast[1]
        return v.hex() if isinstance(v, bytes) else str(v)
    if ast[0] == "NOT":
        return f"NOT({bool_canonical(ast[1])})"
    return f"{ast[0]}({bool_canonical(ast[1])},{bool_canonical(ast[2])})"


def bool_eval(ast: AST, bpl: Dict[object, int], universe_mask: int) -> int:
    """Evaluate a query on the BPL (bit vectors as Python ints; bit i = document i).
      AND -> bitwise &,  OR -> bitwise |,  NOT -> universe_mask & ~x
    A keyword not in the index -> an all-zero vector."""
    op = ast[0]
    if op == "KW":
        return bpl.get(ast[1], 0)
    if op == "NOT":
        # & with the mask of the real document count, otherwise ~ in Python gives a negative number (unbounded bits)
        return universe_mask & ~bool_eval(ast[1], bpl, universe_mask)
    a = bool_eval(ast[1], bpl, universe_mask)
    b = bool_eval(ast[2], bpl, universe_mask)
    return a & b if op == "AND" else a | b


def bool_eval_sets(ast: AST, sets: Dict[object, set], universe: set) -> set:
    """Plain set-based reference evaluator, used in the selftest to check that bool_eval is correct."""
    op = ast[0]
    if op == "KW":
        return set(sets.get(ast[1], set()))
    if op == "NOT":
        return universe - bool_eval_sets(ast[1], sets, universe)
    a, b = bool_eval_sets(ast[1], sets, universe), bool_eval_sets(ast[2], sets, universe)
    return a & b if op == "AND" else a | b


# ============================================================================
# 3) Simulated blockchain — root anchoring, revocation contract  ([ASSUMPTION] 7)
# ============================================================================

@dataclass
class Block:
    height: int          # block number
    prev: bytes          # hash of the previous block (rewriting history is detected)
    kind: str            # transaction type: ROOT / REVOKE
    payload: Tuple
    digest: bytes = b""


@dataclass
class Ledger:
    call_latency_s: float = 0.0
    chain: List[Block] = field(default_factory=list)
    # ----- contract state -----
    merkle_roots: Dict[str, bytes] = field(default_factory=dict)       # DO id -> Merkle root of the data
    index_roots: Dict[str, bytes] = field(default_factory=dict)        # DO id -> Merkle root of the index
    revoked: Dict[bytes, Tuple[str, str, float]] = field(default_factory=dict)  # RT_k -> (du, domain, t)
    revoked_users: Dict[str, bytes] = field(default_factory=dict)      # du id -> RT_k
    query_log: List[Tuple] = field(default_factory=list)

    def _append(self, kind: str, payload: Tuple) -> Block:
        """Append a new block to the chain; digest = H(prev || kind || payload)."""
        if self.call_latency_s:
            time.sleep(self.call_latency_s)       # simulated blockchain latency
        prev = self.chain[-1].digest if self.chain else b"\x00" * 32
        b = Block(len(self.chain), prev, kind, payload)
        b.digest = H(prev, kind.encode(), repr(payload).encode(), tag=b"BLOCK")
        self.chain.append(b)
        return b

    # ---- anchor roots for integrity checks (Phase 3 Step 5 / Phase 6 Step 1)
    def anchor_roots(self, do_id: str, data_root: bytes, index_root: Optional[bytes] = None):
        """The DO stores its Merkle root on the chain -> the DU uses it as a reference the cloud cannot forge."""
        self.merkle_roots[do_id] = data_root
        if index_root is not None:
            self.index_roots[do_id] = index_root
        self._append("ROOT", (do_id, data_root.hex(), index_root.hex() if index_root else None))

    def get_root(self, do_id: str) -> bytes:
        """The DU reads the root from the chain when checking results (Phase 6 Step 2.3)."""
        if self.call_latency_s:
            time.sleep(self.call_latency_s)
        return self.merkle_roots[do_id]

    # ---- Federated revocation contract (Phase 8)
    def submit_revocation(self, du_id: str, domain: str, t: float) -> bytes:
        """Build the revocation token RT_k = H(DU_revoked || T_revoke || Domain_k) and record it on the chain."""
        rt = H(du_id.encode(), repr(t).encode(), domain.encode(), tag=b"RT")
        self.revoked[rt] = (du_id, domain, t)
        self.revoked_users[du_id] = rt
        self._append("REVOKE", (du_id, domain, t, rt.hex()))
        return rt

    def is_revoked(self, du_id: str) -> bool:
        """Exact (global) check — called only when the Bloom filter says "maybe" revoked."""
        if self.call_latency_s:
            time.sleep(self.call_latency_s)
        return du_id in self.revoked_users

    # ---- search log (Algorithm 2 line 27: LogSearchExecution)
    def log_search(self, du_id: str, query_digest: bytes, n_results: int):
        self.query_log.append((du_id, query_digest.hex(), n_results))


# ============================================================================
# 4) Scheme — AA / DO / DU / Cloud Proxy / Cloud Storage (Phase 1-8)
# ============================================================================

# ============================================================================
# helpers
# ============================================================================
class Timer:
    """Accumulating timer: use  with T("step name"): ...  and read T.ms["step name"] (milliseconds).
    The same name can be reused; the times are added up."""

    def __init__(self):
        self.ms: Dict[str, float] = defaultdict(float)
        self._k: Optional[str] = None

    def __call__(self, key: str):
        self._k = key
        return self

    def __enter__(self):
        self._t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.ms[self._k] += (time.perf_counter() - self._t) * 1e3


def to_bitset(positions: np.ndarray, n: int) -> int:
    """ConvertToBitwise (Algorithm 2 line 12): convert a posting list (document positions)
    -> a BPL bit vector stored as a Python int (bit i = 1 if document i has this keyword)."""
    if len(positions) < 48:
        # short posting: setting bits in a loop is faster than building an n-sized array
        v = 0
        for p in positions.tolist():
            v |= 1 << p
        return v
    # long posting: build a numpy bool array and pack it to bytes (little-endian so bit i is position i)
    b = np.zeros(n, dtype=bool)
    b[positions] = True
    return int.from_bytes(np.packbits(b, bitorder="little").tobytes(), "little")


def bitset_positions(v: int, n: int) -> np.ndarray:
    """Back: bit vector -> list of document positions whose bit is 1 (= Matching_DocIDs)."""
    if v == 0:
        return np.empty(0, dtype=np.int64)
    raw = np.frombuffer(v.to_bytes((n + 7) // 8, "little"), dtype=np.uint8)
    return np.flatnonzero(np.unpackbits(raw, bitorder="little")[:n])


# regex for attribute names in a policy (except the words and/or)
_ATTR = re.compile(r"\b(?!and\b|or\b|AND\b|OR\b)([A-Za-z][A-Za-z0-9]*)\b")


def versioned_policy(policy: str, versions: Dict[str, int]) -> str:
    """Add version numbers to the attributes of a policy, e.g. "(auditor or engineer)" -> "(AUDITORV2 or ENGINEERV1)".
    Used at revocation: bump the affected attribute's version -> the revoked user's old key cannot open the new CT_key."""
    return _ATTR.sub(lambda m: f"{m.group(1).upper()}V{versions.get(m.group(1).upper(), 1)}", policy)


# ============================================================================
# Phase 1/2: Attribute Authority
# ============================================================================
class AttributeAuthority:
    """AA_k: issues attribute keys to DUs and holds the CP-ABE master key
    (the system can have several AAs = multi-authority, each managing its own domain).
    [ASSUMPTION] 9: BSW07 is single-authority per ciphertext -> one DO bound to one AA."""

    def __init__(self, aa_id: str, group: PairingGroup):
        self.id, self.group = aa_id, group
        self.cpabe = CPabe_BSW07(group)
        # Phase 1: CreateAttributeAuthority -> PK = {g, h=g^β, f=g^(1/β), e(g,g)^α},  MK = (β, g^α)
        self.pk, self.mk = self.cpabe.setup()
        self.attr_version: Dict[str, int] = defaultdict(lambda: 1)   # version of each attribute (for revocation)
        self.users: Dict[str, List[str]] = {}            # du_id -> the attributes it holds

    def _vattrs(self, attrs: Iterable[str]) -> List[str]:
        return [f"{a.upper()}V{self.attr_version[a.upper()]}" for a in attrs]

    def attribute_keygen(self, du_id: str, attrs: List[str]):
        """Phase 2 Step 1: AttributeKeygen(PK_k, S_A) -> SK_DU
        Returns three values:
          sk_abe : CP-ABE secret key bound to the attributes (opens CT_key if the attributes satisfy the policy)
          s_u    : the DU's secret for trapdoors/signatures  [FIX] 2 (the paper uses g^α, which the DU lacks)
          PK_DU  : g^{s_u}, for the proxy to check signatures and the NIZK"""
        self.users[du_id] = [a.upper() for a in attrs]
        sk_abe = self.cpabe.keygen(self.pk, self.mk, self._vattrs(attrs))
        s_u = self.group.random(ZR)
        return sk_abe, s_u, self.pk["g"] ** s_u


# ============================================================================
# Phase 3: data structures stored in the cloud
# ============================================================================
@dataclass
class EncryptedDataset:
    do_id: str
    n: int                                 # number of documents
    ciphertexts: List[bytes]               # C_i (AES)
    enc_ids: List[bytes]                   # Enc(id_i)
    postings: Dict[bytes, np.ndarray]      # I(w) -> document positions (sorted) = inverted index
    bpl_dense: Dict[bytes, int]            # I(w) -> BPL bit vector (only keywords stored densely)
    data_tree: MerkleTree                  # leaf = H(Enc(id) || C_i)  -> used to check results in Phase 6
    index_tree: MerkleTree                 # leaf = H(I(w) || posting) -> the root is anchored but the paper does not use it for checks
    ct_key: dict                           # CP-ABE(K_wrap, P): the key wrapped under the access policy
    wrapped_symk: bytes                    # AES_{K_wrap}(SymK_DO)
    policy: str                            # access policy P, e.g. "(auditor or engineer)"
    aa_id: str                             # the AA managing this policy
    universe_mask: int = 0                 # (1<<n)-1, used for NOT


# ============================================================================
# Data Owner (+ Edge Proxy)
# ============================================================================
class DataOwner:
    """DO: encrypts the IIoT data, builds the index, anchors the roots on the chain."""

    def __init__(self, do_id: str, group: PairingGroup, aa: AttributeAuthority, policy: str):
        self.id, self.group, self.aa, self.policy = do_id, group, aa, policy
        g = aa.pk["g"]
        # Phase 2 Step 2: the DO's key pair  SK_DO = x_DO,  PK_DO = g^{x_DO}
        self.x = group.random(ZR)
        self.pk = g ** self.x
        self.symk = os.urandom(32)                       # SymK_DO (main 256-bit symmetric key)
        self._derive()
        self.dataset: Optional[EncryptedDataset] = None

    def _derive(self):
        """Derive purpose-specific subkeys from SymK_DO (no key used for several jobs)."""
        self.k_aes = H(self.symk, tag=b"AES")            # document encryption
        self.k_prf = H(self.symk, tag=b"PRF")            # keyword tokens I(w)
        self.prp = PRP(H(self.symk, tag=b"PRP")[:16])    # doc id encryption

    # Phase 2 Step 4: PRE key  PRE_{A->B} = PK_B^{x_A} = g^{x_A x_B}
    def rekeygen(self, pk_target):
        return pk_target ** self.x

    def _encapsulate(self, T: Timer):
        """Phase 3 Step 2: encrypt SymK with CP-ABE.
        BSW07 encrypts only elements of GT, so it is hybrid: random M ∈ GT -> K_wrap = H(M),
        and K_wrap AES-wraps SymK_DO (revocation can change K_wrap without touching C_i)."""
        with T("cpabe_encrypt"):
            M = self.group.random(GT)
            pol = versioned_policy(self.policy, dict(self.aa.attr_version))
            ct_key = self.aa.cpabe.encrypt(self.aa.pk, M, pol)
            k_wrap = H(self.group.serialize(M), tag=b"WRAP")
            wrapped = aes_encrypt(k_wrap, self.symk)
        return ct_key, wrapped

    def outsource(self, docs: Sequence[Tuple[int, bytes, Sequence[str]]],
                  dense_threshold: Optional[float] = None) -> Tuple[EncryptedDataset, Dict[str, float]]:
        """
        All of Phase 3.  docs = [(doc_id, plaintext, keywords)]

        dense_threshold: keywords with df >= threshold*n are stored as BPL bit vectors in advance,
        the rest as posting lists converted to bit vectors at query time (Algorithm 2 line 12).
        None = all dense if n <= 50k (exactly as in the paper); a 1/64 threshold above that.
        Reason: at N=10^6 each bit vector is 125 KB × tens of thousands of keywords = several GB of RAM.
        [ASSUMPTION] 10
        """
        T = Timer()
        n = len(docs)
        if dense_threshold is None:
            dense_threshold = 0.0 if n <= 50_000 else 1 / 64

        # ---- Step 1: encrypt documents  C_i = AES(SymK_DO, D_i)  (8-byte doc_id prepended to the plaintext)
        with T("aes_encrypt"):
            cts = [aes_encrypt(self.k_aes, d.to_bytes(8, "big") + p) for d, p, _ in docs]
            enc_ids = [self.prp.enc_id(d) for d, _, _ in docs]
        # ---- Step 2: CT_key = CP-ABE_Encrypt(PK_k, SymK_DO, P)
        ct_key, wrapped = self._encapsulate(T)

        # ---- Steps 3 + 4: inverted index  I(w) = PRF(SymK, w) -> {document positions} and the BPL
        with T("index_build"):
            inv: Dict[bytes, List[int]] = defaultdict(list)
            tok_cache: Dict[str, bytes] = {}             # cached tokens, no repeated PRF
            for pos, (_, _, kws) in enumerate(docs):
                for w in set(kws):
                    t = tok_cache.get(w)
                    if t is None:
                        t = tok_cache[w] = prf(self.k_prf, w.lower().encode())
                    inv[t].append(pos)
            postings = {t: np.asarray(v, dtype=np.int64) for t, v in inv.items()}
            dense = {t: to_bitset(a, n) for t, a in postings.items()
                     if len(a) >= dense_threshold * n}
        # ---- Step 5: Merkle trees of the index (H_root_index) + of the data (used in Phase 6)
        with T("merkle_build"):
            data_tree = MerkleTree([eid + ct for eid, ct in zip(enc_ids, cts)])
            index_tree = MerkleTree([t + postings[t].astype(">u4").tobytes() for t in sorted(postings)])

        self.dataset = EncryptedDataset(self.id, n, cts, enc_ids, postings, dense, data_tree,
                                        index_tree, ct_key, wrapped, self.policy, self.aa.id,
                                        (1 << n) - 1)
        # "index generation" as measured in the paper's Fig. 2 = index + Merkle (no AES/CP-ABE)
        T.ms["index_generation"] = T.ms["index_build"] + T.ms["merkle_build"]
        return self.dataset, dict(T.ms)


class EdgeProxy:
    """Edge Proxy (entity 4): sits at the IIoT gateway and encrypts/indexes on behalf of the DO,
    still inside the DO's domain (keys never leave it) — in this simulation it just calls the DO's work."""

    def __init__(self, owner: DataOwner):
        self.owner = owner

    def process(self, docs, **kw):
        return self.owner.outsource(docs, **kw)


# ============================================================================
# Schnorr signature (in G1)
# ============================================================================
def schnorr_sign(group, g, x, msg: bytes):
    """Schnorr signature: random k, R = g^k, c = H(R || msg), z = k + c·x  -> σ = (R, z)"""
    k = group.random(ZR)
    R = g ** k
    c = group.hash(group.serialize(R) + msg, ZR)
    return R, k + c * x


def schnorr_verify(group, g, X, msg: bytes, sig) -> bool:
    """Check: g^z == R · X^c   (X = the signer's public key)"""
    R, z = sig
    c = group.hash(group.serialize(R) + msg, ZR)
    return g ** z == R * (X ** c)


# ============================================================================
# Data User
# ============================================================================
@dataclass
class Trapdoor:
    """Trapdoor Tq = (C1, C2, C3) + signature σ + NIZK π  (Phase 4 Step 1)"""
    du_id: str
    do_id: str
    aa_id: str
    C1: object           # g^r  (randomization factor)
    C2: bytes            # AES_{KDF(Z)}( H(W_q,B_q) || canonical query using PRF tokens )
    C3: object           # PK_DU^r  (the DU public-key part)
    bind: bytes          # H(e(C3, h_k)) -- binds the trapdoor to authority k (one pairing)
    sigma: tuple = ()
    zkp: tuple = ()

    def digest(self, group) -> bytes:
        """Hash of the whole trapdoor, used as the signed message and bound to the NIZK."""
        return H(self.du_id.encode(), self.do_id.encode(), group.serialize(self.C1),
                 self.C2, group.serialize(self.C3), self.bind, tag=b"TQ")


class DataUser:
    """DU: builds trapdoors, verifies results, decrypts."""

    def __init__(self, du_id: str, group: PairingGroup):
        self.id, self.group = du_id, group
        self.keys: Dict[str, dict] = {}        # aa_id -> {sk, s, PK, aa}  (keys from several AAs allowed)
        self.domain_keys: Dict[str, bytes] = {}   # cache of decrypted SymK_DO

    def receive_keys(self, aa: AttributeAuthority, attrs: List[str]):
        sk, s, PK = aa.attribute_keygen(self.id, attrs)
        self.keys[aa.id] = {"sk": sk, "s": s, "PK": PK, "aa": aa}

    def unlock_domain(self, ds: EncryptedDataset) -> Optional[bytes]:
        """Decrypt CT_key with CP-ABE to get SymK_DO (needed both for PRF tokens and for decryption).
        If the attributes do not satisfy the policy -> None = this DO's data cannot be searched
        (this is where fine-grained access control is enforced on *search*)."""
        if ds.do_id in self.domain_keys:
            return self.domain_keys[ds.do_id]
        k = self.keys.get(ds.aa_id)
        if not k:
            return None                     # no key from the AA managing this DO
        aa = k["aa"]
        M = aa.cpabe.decrypt(aa.pk, k["sk"], ds.ct_key)
        if M is False or M is None:
            return None                     # attributes do not satisfy the policy
        try:
            symk = aes_decrypt(H(self.group.serialize(M), tag=b"WRAP"), ds.wrapped_symk)
        except ValueError:
            return None
        self.domain_keys[ds.do_id] = symk
        return symk

    def gen_trapdoor(self, ds, query: str, pk_cloud,
                     with_proofs: bool = True) -> Tuple[Trapdoor, Dict[str, float]]:
        """Phase 4 Step 1: build the trapdoor of a Boolean query.
        Cost: 3 exponentiations + 1 pairing (constant, independent of the number of keywords),
        plus the signature and NIZK when with_proofs=True (timed separately).
        ds = one owner or a list of owners (cross-domain search): [ASSUMPTION] 12 -> one trapdoor whose C2
        holds the token I(w) of every owner (exp / pairing / signature / NIZK once per query)."""
        T, g = Timer(), None
        multi = isinstance(ds, (list, tuple))
        dss = list(ds) if multi else [ds]
        symks = [self.unlock_domain(d) for d in dss]
        if any(x is None for x in symks):
            raise PermissionError("attributes do not satisfy the data owner's policy")
        if len({d.aa_id for d in dss}) != 1:
            raise ValueError("cross-domain trapdoor: owners must share one attribute authority in this simulation")
        k = self.keys[dss[0].aa_id]
        aa = k["aa"]
        g, grp = aa.pk["g"], self.group

        with T("trapdoor"):
            ast = bool_parse(query)                                         # query -> AST (B_q)
            parts = []
            for symk in symks:                                              # keyword -> I(w) of each owner
                k_prf = H(symk, tag=b"PRF")
                parts.append(bool_canonical(bool_map_leaves(ast, lambda w: prf(k_prf, w.encode()))))
            canon = (parts[0] if not multi else
                     "\n".join(f"{d.do_id}\t{c}" for d, c in zip(dss, parts))).encode()
            hq = H(canon, tag=b"WQBQ")                                   # H(W_q, B_q)
            r = grp.random(ZR)
            C1 = g ** r                                                  # exponentiation 1
            C3 = k["PK"] ** r                                            # exponentiation 2
            Z = pk_cloud ** r                                            # exponentiation 3: DH key with the proxy
            bind = H(grp.serialize(pair(C3, aa.pk["h"])), tag=b"BIND")   # pairing 1
            # [FIX] 2: C2 = the query encrypted with KDF(Z) -> only the proxy (who knows x_cloud) can decrypt it
            # [ASSUMPTION] 3: the payload is the canonical query whose leaves are PRF tokens
            C2 = aes_encrypt(H(grp.serialize(Z), tag=b"KDF"), hq + canon)
            do_id = dss[0].do_id if not multi else "MULTI:" + ",".join(d.do_id for d in dss)
            tq = Trapdoor(self.id, do_id, dss[0].aa_id, C1, C2, C3, bind)
        if with_proofs:
            d = tq.digest(grp)
            with T("signature"):                               # σ = Sign(SK_DU, Tq) prevents trapdoor forgery
                tq.sigma = schnorr_sign(grp, g, k["s"], d)     # [ASSUMPTION] 4: the paper names no scheme -> Schnorr
            with T("zkp"):
                # [FIX] 4: the paper's ZKP equations do not balance -> DLEQ instead
                # NIZK (Fiat-Shamir, Chaum-Pedersen DLEQ): proves that C1 and C3 use the same r,
                # i.e. log_g(C1) = log_PK(C3), without revealing r, bound to H(W_q,B_q)
                t = grp.random(ZR)
                V1, V2 = g ** t, k["PK"] ** t                  # commitment
                delta = grp.hash(grp.serialize(V1) + grp.serialize(V2) + d + hq, ZR)   # challenge δ
                tq.zkp = (V1, V2, t - delta * r, hq)           # response z = t - δr
        return tq, dict(T.ms)

    # ---------------- Phase 6: result verification
    def verify(self, resp: "SearchResponse", ledger: Ledger, pk_cloud, g,
               check_result_proof: bool = True) -> Tuple[bool, Dict[str, float], List[int]]:
        """Returns (passed?, time, positions of tampered documents).
        Two checks: (1) the Merkle path of every returned ciphertext against the root on the blockchain
                    (2) the proxy's result proof that this result comes from this trapdoor
        Note: it checks only that what was returned is correct, not that everything was returned (as the paper
        writes; see the note in the header).
        [ASSUMPTION] 6: the proxy's result proof = Schnorr (the paper says ZKP without details)"""
        T, ok, bad = Timer(), True, []
        with T("fetch_root"):
            root = ledger.get_root(resp.do_id)
        with T("merkle_verify"):
            if resp.proof_mode == "multi":
                leaves = {pos: leaf_hash(eid + ct) for pos, eid, ct in resp.results}
                # empty result: no ciphertext to check -> passes, as in path mode (it used to return False for lack of leaves)
                ok = verify_multiproof(leaves, resp.n_leaves, resp.proofs, root) if leaves else True
                if not ok:  # a multiproof cannot tell which one is wrong, so the whole set is marked
                    bad = [pos for pos, _, _ in resp.results]
            else:
                # one path per file: shows exactly which ciphertext was modified (tamper localisation)
                for (pos, eid, ct), path in zip(resp.results, resp.proofs):
                    if not verify_path(leaf_hash(eid + ct), pos, path, root):
                        ok = False
                        bad.append(pos)
        if check_result_proof:
            with T("result_proof_verify"):
                if not schnorr_verify(self.group, g, pk_cloud, resp.result_digest(), resp.result_sig):
                    ok = False
        return ok, dict(T.ms), bad

    def verify_multi(self, mresp: "MultiResponse", ledger: Ledger, pk_cloud, g):
        """Cross-domain: each owner's Merkle proof against that owner's root on the chain (Phase 6 Step 2)
        + the proxy's single result proof over the combined R (Phase 6 Step 3: Verify(pi, T'q, R))."""
        ok, ms = True, defaultdict(float)
        for r in mresp.responses:
            o, t, _ = self.verify(r, ledger, pk_cloud, g, check_result_proof=False)
            ok &= o
            for k_, v in t.items():
                ms[k_] += v
        T = Timer()
        with T("result_proof_verify"):
            if not schnorr_verify(self.group, g, pk_cloud, mresp.result_digest(), mresp.result_sig):
                ok = False
        ms["result_proof_verify"] += T.ms["result_proof_verify"]
        return ok, dict(ms)

    # ---------------- Phase 7: decryption
    def decrypt(self, ds: EncryptedDataset, resp: "SearchResponse") -> Tuple[List[Tuple[int, bytes]], Dict[str, float]]:
        """Step 1: CP-ABE opens CT_key -> SymK_DO,  Step 2: AES decrypts C_i -> D_i."""
        T = Timer()
        with T("cpabe_decrypt"):
            self.domain_keys.pop(ds.do_id, None)     # clear the cache to time the real CP-ABE
            symk = self.unlock_domain(ds)
        if symk is None:
            raise PermissionError("CP-ABE decryption failed")
        k_aes = H(symk, tag=b"AES")
        out = []
        with T("aes_decrypt"):
            for _, _, ct in resp.results:
                pt = aes_decrypt(k_aes, ct)
                out.append((int.from_bytes(pt[:8], "big"), pt[8:]))   # (doc_id, contents)
        return out, dict(T.ms)


# ============================================================================
# Cloud Proxy + Storage
# ============================================================================
@dataclass
class SearchResponse:
    """The result the proxy returns to the DU."""
    do_id: str
    tq_digest: bytes
    results: List[Tuple[int, bytes, bytes]]     # (position, Enc(id), C_i)
    proofs: object                              # one Merkle path per result, or a multiproof
    n_leaves: int
    proof_mode: str                             # "paths" (as in the paper) | "multi"
    result_sig: tuple = ()

    def result_digest(self) -> bytes:
        """Hash binding the trapdoor to the whole result set (signed by the proxy)."""
        return H(self.tq_digest, *[p.to_bytes(8, "big") + e + H(c) for p, e, c in self.results],
                 tag=b"RES")

    def proof_size_bytes(self) -> int:
        """Proof size: multiproof = 32 bytes per node; paths = 33 bytes per node (hash + left/right bit)."""
        if self.proof_mode == "multi":
            return 32 * len(self.proofs)
        return sum(33 * len(p) for p in self.proofs)


@dataclass
class MultiResponse:
    """Cross-domain: each owner's result + the proxy's single signature over the combined result."""
    responses: List[SearchResponse]
    result_sig: tuple = ()

    def result_digest(self) -> bytes:
        return H(*[r.result_digest() for r in self.responses], tag=b"MRES")


class CloudStorage:
    """Cloud Storage: ciphertexts, indexes and metadata of each DO."""

    def __init__(self):
        self.datasets: Dict[str, EncryptedDataset] = {}

    def store(self, ds: EncryptedDataset):
        self.datasets[ds.do_id] = ds


class CloudProxy:
    """Cloud Proxy: checks trapdoors, checks revocation, runs the PRE transform, searches, builds proofs."""

    def __init__(self, group: PairingGroup, g, ledger: Ledger, storage: CloudStorage,
                 bloom_capacity: int = 100_000):
        self.group, self.g, self.ledger, self.storage = group, g, ledger, storage
        # Phase 2 Step 3: the proxy's key pair  SK_Cloud = x_Cloud,  PK_Cloud = g^{x_Cloud}
        self.x = group.random(ZR)
        self.pk = g ** self.x
        self.bloom = BloomFilter(bloom_capacity, 1e-4)           # revoked DUs (fast check)
        self.pre_keys: Dict[str, object] = {}                    # do_id -> PRE_{DO->Cloud}
        self.du_registry: Dict[str, Tuple[str, object]] = {}     # (du_id, aa_id) -> PK_DU
        self.aa_pk: Dict[str, dict] = {}

    def register_user(self, du: DataUser):
        for aa_id, k in du.keys.items():
            self.du_registry[(du.id, aa_id)] = k["PK"]
            self.aa_pk[aa_id] = k["aa"].pk

    def revoked(self, du_id: str, T: Timer) -> bool:
        """Phase 8 Step 2: two-level check
          1) Bloom filter (fast, local) -> not found = definitely not revoked
          2) if the Bloom filter reports a hit, query the smart contract (exact, rules out false positives)"""
        with T("revocation_check"):
            if du_id.encode() not in self.bloom:
                return False
            return self.ledger.is_revoked(du_id)

    def admit_and_transform(self, tq: Trapdoor, T: Timer, check_proofs: bool = True):
        """Phase 4 Steps 2 + 3: receive the trapdoor -> check everything -> transform with PRE."""
        grp, g = self.group, self.g
        if self.revoked(tq.du_id, T):
            raise PermissionError("revoked user")
        PK = self.du_registry.get((tq.du_id, tq.aa_id))
        if PK is None:
            raise PermissionError("unknown user")
        d = tq.digest(grp)
        if check_proofs:
            with T("verify_signature"):                  # check that the DU really built the trapdoor
                if not schnorr_verify(grp, g, PK, d, tq.sigma):
                    raise PermissionError("bad signature")
            with T("verify_zkp"):
                # check the NIZK: g^z · C1^δ == V1  and  PK^z · C3^δ == V2
                V1, V2, z, hq_claim = tq.zkp
                delta = grp.hash(grp.serialize(V1) + grp.serialize(V2) + d + hq_claim, ZR)
                if g ** z * tq.C1 ** delta != V1 or PK ** z * tq.C3 ** delta != V2:
                    raise PermissionError("bad NIZK")
        # [FIX] 13: the paper (Phase 4 Step 2) has the proxy check only the signature + ZKP, with no pairing on the proxy
        #   (Table 4 has P_e only in TrapGen), so the binding is not re-checked with a pairing; it is still signed in Tq's digest
        with T("transform"):                             # Algorithm 1: Trapdoor Transformation (PRE) [ASSUMPTION] 5
            Z = tq.C1 ** self.x                          # Z = C1^{x_cloud} = PK_cloud^r (DH)
            payload = aes_decrypt(H(grp.serialize(Z), tag=b"KDF"), tq.C2)
            first = tq.do_id.split(":", 1)[1].split(",")[0] if tq.do_id.startswith("MULTI:") else tq.do_id
            rk = grp.hash(grp.serialize(self.pre_keys[first]), ZR)      # ReKey_Cloud from the PRE key (1 exp per query)
            C3p = tq.C3 * (g ** rk)                                       # C3' = g^ReKey · C3
            # C2' = the payload re-encrypted under a key bound to C3' (the form used with the DO's domain)
            C2p = aes_encrypt(H(grp.serialize(Z), grp.serialize(C3p), tag=b"KDF2"), payload)
            tq_p = (tq.C1, C2p, C3p, Z)                                   # T'q
        hq, canon = payload[:32], payload[32:]
        if check_proofs and hq != tq.zkp[3]:
            raise PermissionError("NIZK not bound to this query")       # the NIZK must belong to this query
        if H(canon, tag=b"WQBQ") != hq:
            raise PermissionError("query hash mismatch")                # the query was altered in transit
        return tq_p, d

    @staticmethod
    def _extract(tq_p, group) -> AST:
        """ExtractKeyword(T'q): decrypt C2' to get the query (an AST whose leaves are PRF tokens)."""
        C1, C2p, C3p, Z = tq_p
        payload = aes_decrypt(H(group.serialize(Z), group.serialize(C3p), tag=b"KDF2"), C2p)
        return _parse_canonical(payload[32:].decode())

    def _payload(self, tq_p) -> str:
        """ExtractKeyword(T'q): decrypt C2' to get the canonical query (leaf = PRF token)."""
        C1, C2p, C3p, Z = tq_p
        return aes_decrypt(H(self.group.serialize(Z), self.group.serialize(C3p), tag=b"KDF2"), C2p)[32:].decode()

    def _search_ds(self, ds, ast, d, proof_mode, T, tamper=None, tamper_pos=None, tamper_old=None):
        """Algorithm 2 on one owner's index + Merkle proof (not signed yet).
        tamper (a simulated malicious cloud, tests only) on the document at tamper_pos (None = the first result):
          modify = flip one bit of the ciphertext, omit = drop the result, inject = add a document that does not
          match the query (a real ciphertext with a valid Merkle path), old_version = send the old ciphertext
          tamper_old[pos]"""
        # Algorithm 2 lines 2-12: fetch the BPL of each keyword
        with T("bpl_retrieval"):
            bpl = {}
            for kw in bool_keywords(ast):
                if kw in ds.bpl_dense:
                    bpl[kw] = ds.bpl_dense[kw]
                elif kw in ds.postings:
                    bpl[kw] = to_bitset(ds.postings[kw], ds.n)      # ConvertToBitwise
        # line 13: EvaluateBoolean with bitwise AND/OR/NOT
        with T("boolean_eval"):
            match = bool_eval(ast, bpl, ds.universe_mask) if bpl or _has_not(ast) else 0
            positions = bitset_positions(match, ds.n)
        # lines 17-22: fetch the ciphertexts of the matching documents
        with T("result_fetch"):
            results = [(int(p), ds.enc_ids[p], ds.ciphertexts[p]) for p in positions]
        if tamper and (results or tamper == "inject"):
            bad = set(tamper_pos) if tamper_pos is not None else {results[0][0]}
            if tamper == "modify":
                results = [(p, e, c[:-1] + bytes([c[-1] ^ 1])) if p in bad else (p, e, c) for p, e, c in results]
            elif tamper == "omit":
                results = [r for r in results if r[0] not in bad]
            elif tamper == "inject":
                results = sorted(results + [(p, ds.enc_ids[p], ds.ciphertexts[p]) for p in bad])
            elif tamper == "old_version":
                results = [(p, e, tamper_old[p]) if p in bad else (p, e, c) for p, e, c in results]
        with T("proof_gen"):
            if proof_mode == "multi":
                proofs = ds.data_tree.multiproof(p for p, _, _ in results)
            else:
                proofs = [ds.data_tree.proof(p) for p, _, _ in results]
            resp = SearchResponse(ds.do_id, d, results, proofs, len(ds.data_tree), proof_mode)
        return resp

    def search(self, tq: Trapdoor, proof_mode: str = "paths", check_proofs: bool = True,
               tamper: Optional[str] = None, tamper_pos=None, tamper_old=None) -> Tuple[SearchResponse, Dict[str, float]]:
        """Phase 5: Algorithm 2 (Secure Search Execution) + the proof for Phase 6 (one owner)."""
        T = Timer()
        tq_p, d = self.admit_and_transform(tq, T, check_proofs)
        ds = self.storage.datasets[tq.do_id]
        with T("bpl_retrieval"):
            ast = _parse_canonical(self._payload(tq_p))
        resp = self._search_ds(ds, ast, d, proof_mode, T, tamper, tamper_pos, tamper_old)
        with T("proof_gen"):                                    # the proxy's result signature
            resp.result_sig = schnorr_sign(self.group, self.g, self.x, resp.result_digest())
        self.ledger.log_search(tq.du_id, d, len(resp.results))  # line 27: log to the chain
        # search_core = pure search time (compare with the paper's Figs. 4/5)
        T.ms["search_core"] = T.ms["bpl_retrieval"] + T.ms["boolean_eval"] + T.ms["result_fetch"]
        return resp, dict(T.ms)

    def search_multi(self, tq: Trapdoor, proof_mode: str = "paths",
                     check_proofs: bool = True) -> Tuple["MultiResponse", Dict[str, float]]:
        """Cross-domain search with a single trapdoor: check the signature / NIZK and transform (PRE) once,
        then search each owner's index (Algorithm 2) + a Merkle proof per owner, and sign the combined result once.
        [ASSUMPTION] 12 (Phase 4 Step 1: the DU combines keys of several AAs into one trapdoor; Tq has no
        DO-specific part)"""
        T = Timer()
        tq_p, d = self.admit_and_transform(tq, T, check_proofs)
        with T("bpl_retrieval"):
            parts = [line.split("\t", 1) for line in self._payload(tq_p).split("\n")]
        resps = [self._search_ds(self.storage.datasets[do_id], _parse_canonical(c), d, proof_mode, T)
                 for do_id, c in parts]
        mresp = MultiResponse(resps)
        with T("proof_gen"):
            mresp.result_sig = schnorr_sign(self.group, self.g, self.x, mresp.result_digest())
        self.ledger.log_search(tq.du_id, d, sum(len(r.results) for r in resps))
        T.ms["search_core"] = T.ms["bpl_retrieval"] + T.ms["boolean_eval"] + T.ms["result_fetch"]
        return mresp, dict(T.ms)


def _has_not(ast) -> bool:
    """Does the query contain NOT? (then it may have results even when no keyword is found, e.g. NOT x = every
    document)"""
    return ast[0] == "NOT" or (ast[0] in ("AND", "OR") and (_has_not(ast[1]) or _has_not(ast[2])))


def _parse_canonical(s: str) -> AST:
    """Back from bool_canonical -> AST (leaves are token hex strings)."""
    pos = 0

    def node():
        nonlocal pos
        for op in ("AND(", "OR(", "NOT("):
            if s.startswith(op, pos):
                pos += len(op)
                if op == "NOT(":
                    a = node()
                    pos += 1           # skip ')'
                    return ("NOT", a)
                a = node()
                pos += 1           # skip ','
                b = node()
                pos += 1           # skip ')'
                return (op[:-1], a, b)
        end = pos
        while end < len(s) and s[end] not in ",)":
            end += 1
        leaf = bytes.fromhex(s[pos:end])
        pos = end
        return ("KW", leaf)
    return node()


# ============================================================================
# System facade
# ============================================================================
class System:
    """Helper wiring all entities together for the experiments (no need to call each class)."""

    def __init__(self, curve: str = "SS512", ledger_latency_s: float = 0.0):
        self.group = PairingGroup(curve)            # [ASSUMPTION] 1: the paper names no curve -> SS512
        self.ledger = Ledger(call_latency_s=ledger_latency_s)
        self.storage = CloudStorage()
        self.aas: Dict[str, AttributeAuthority] = {}
        self.owners: Dict[str, DataOwner] = {}
        self.users: Dict[str, DataUser] = {}
        self.proxy: Optional[CloudProxy] = None

    def add_authority(self, aa_id: str) -> AttributeAuthority:
        aa = AttributeAuthority(aa_id, self.group)
        self.aas[aa_id] = aa
        if self.proxy is None:
            # every AA uses the same pairing group; the proxy uses the first AA's generator
            self.proxy = CloudProxy(self.group, aa.pk["g"], self.ledger, self.storage)
        return aa

    def add_owner(self, do_id: str, aa_id: str, policy: str) -> DataOwner:
        do = DataOwner(do_id, self.group, self.aas[aa_id], policy)
        self.owners[do_id] = do
        return do

    def add_user(self, du_id: str, attrs_by_aa: Dict[str, List[str]]) -> DataUser:
        """attrs_by_aa, e.g. {"AA_manu": ["auditor"], "AA_reg": ["regulator"]} = keys from several AAs."""
        du = DataUser(du_id, self.group)
        for aa_id, attrs in attrs_by_aa.items():
            du.receive_keys(self.aas[aa_id], attrs)
        self.users[du_id] = du
        self.proxy.register_user(du)
        return du

    def outsource(self, do_id: str, docs, use_edge_proxy: bool = True, **kw):
        """Phase 3 + PRE key to the proxy + store the data in the cloud + anchor the roots on the chain."""
        do = self.owners[do_id]
        ds, t = (EdgeProxy(do).process(docs, **kw) if use_edge_proxy else do.outsource(docs, **kw))
        T = Timer()
        with T("rekeygen"):                          # time the re-encryption key generation (the paper measures it too)
            self.proxy.pre_keys[do_id] = do.rekeygen(self.proxy.pk)
        t.update(T.ms)
        self.storage.store(ds)
        self.ledger.anchor_roots(do_id, ds.data_tree.root, ds.index_tree.root)
        return ds, t

    # ---------------- Phase 8: User Revocation
    def revoke(self, du_id: str, aa_id: str) -> Dict[str, float]:
        T = Timer()
        aa = self.aas[aa_id]
        # Step 1: send the revocation token to the smart contract + add it to the Bloom filter
        with T("submit_revocation"):
            self.ledger.submit_revocation(du_id, aa_id, time.time())
            self.proxy.bloom.add(du_id.encode())
        affected = aa.users.get(du_id, [])
        # Step 4: update the attribute keys only for the affected attribute and only for users holding it
        with T("attribute_key_update"):
            for a in affected:
                aa.attr_version[a] += 1              # bump the version -> old keys do not satisfy the new policy
            for uid, u in self.users.items():
                if uid == du_id or aa_id not in u.keys:
                    continue
                if set(aa.users[uid]) & set(affected):
                    sk = aa.cpabe.keygen(aa.pk, aa.mk, aa._vattrs(aa.users[uid]))
                    u.keys[aa_id]["sk"] = sk
                    u.domain_keys.clear()
        # Step 3: lazy re-encryption -> rotate K_wrap and build a new CT_key (C_i is not re-encrypted)
        # [ASSUMPTION] 8: one CT_key per DO -> "lazy" = one new encapsulation
        with T("lazy_reencrypt"):
            for do in self.owners.values():
                if do.aa.id != aa_id or do.dataset is None:
                    continue
                new_sk = self.group.random(ZR)       # SK'_DO
                pk_new = do.aa.pk["g"] ** new_sk     # PK'_DO
                do.rekeygen(pk_new)                  # PRE_{DO->DO'} = ReKeyGen(SK_DO, PK'_DO)
                ct_key, wrapped = do._encapsulate(Timer())
                do.dataset.ct_key, do.dataset.wrapped_symk = ct_key, wrapped
                do.x, do.pk = new_sk, pk_new
                self.proxy.pre_keys[do.id] = do.rekeygen(self.proxy.pk)
        return dict(T.ms)


# ============================================================================
# 5) Workload — AMTP's shared dataset (amtp_dataset.py) + a synthetic corpus for demo/selftest
# ============================================================================

Doc = Tuple[int, bytes, List[str]]       # (document position, plaintext contents, keyword list)

HERE = os.path.dirname(os.path.abspath(__file__))  # this file's folder (baselines/)
DEFAULT_QUERIES = os.path.join(HERE, "results", "exp1_queries.json")  # shared queries every scheme replays (as Du)
sys.path.insert(0, HERE)                          # so amtp_dataset.py next to this file can be imported


def dataset():
    """Import amtp_dataset only when needed (demo / selftest run without the dataset)."""
    import amtp_dataset                           # shared dataset loader
    return amtp_dataset                           # return the module


def to_secollab(docs, data_dir=None) -> List[Doc]:
    """Convert dataset Docs -> (position, real file contents, keywords) as used by DataOwner.outsource.
    position = index in the list (0..N-1) = the bit in the BPL and the leaf in the data Merkle tree"""
    D = dataset()
    return [(i, D.read_bytes(d, data_dir), list(d.keywords)) for i, d in enumerate(docs)]


def synthetic_corpus(n_docs: int, vocab: int = 20_000, kw_per_doc: int = 10,
                     zipf_s: float = 1.1, payload_bytes: int = 256, seed: int = 7) -> List[Doc]:
    """Build n_docs documents with ~kw_per_doc keywords each, drawn from vocab with a Zipf distribution.
    Used only by demo / selftest / paper / revocation (exp1/exp2 use the shared dataset)."""
    rng = np.random.default_rng(seed)
    ranks = np.arange(1, vocab + 1)
    p = 1.0 / ranks ** zipf_s                    # probability inversely proportional to rank^s
    p /= p.sum()
    words = [f"kw{i:05d}" for i in range(vocab)]
    draws = rng.choice(vocab, size=(n_docs, kw_per_doc * 2), p=p)   # draw twice as many, duplicates are removed
    docs: List[Doc] = []
    body = os.urandom(payload_bytes)             # contents shared by every document (saves RAM; contents do not affect search)
    for i in range(n_docs):
        kws = list(dict.fromkeys(words[j] for j in draws[i]))[:kw_per_doc]   # remove duplicates, keep the order
        docs.append((i, body, kws))
    return docs


def doc_freq(docs: Sequence[Doc]) -> Counter:
    """Document frequency: in how many documents each keyword appears."""
    c = Counter()
    for _, _, kws in docs:
        c.update(set(kws))
    return c


# ============================================================================
# 6) benchmark helpers (output format as in Chen: <name>_ms, _ms_median, _ms_std)
# ============================================================================

class Writer:
    """Collect rows, print them (without std/median, for readability) and write the CSV on close()."""

    def __init__(self, name: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)       # create the output folder
        self.path = os.path.join(out_dir, f"secollab_{name}.csv")  # output file
        self.rows = []                            # collected rows

    def add(self, **row):
        self.rows.append(row)                     # keep the row
        show = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()
                if not k.endswith("_std") and not k.endswith("_median")}  # drop columns not shown
        print("  " + "  ".join(f"{k}={v}" for k, v in show.items()), flush=True)  # print

    def close(self):
        if not self.rows:                         # no data
            return                                # nothing to write
        keys = list(dict.fromkeys(k for r in self.rows for k in r))  # all column names over every row (order kept)
        with open(self.path, "w", newline="", encoding="utf-8") as f:  # open the file
            w = csv.DictWriter(f, fieldnames=keys)  # writer
            w.writeheader()                       # header
            w.writerows(self.rows)                # data (missing cells of N/A rows stay empty)
        print(f"-> {os.path.relpath(self.path)}")  # print the file path
        dataset().write_manifest(self.path)       # machine / commit / command line (<csv>.manifest.json)


def summarize(samples, prefix: str = ""):
    """Aggregate runs -> columns <name>_ms (mean), <name>_ms_median, <name>_ms_std  (as in Chen)."""
    out = {}                                      # summary
    for k in samples[0]:                          # every metric
        v = [s.get(k, 0.0) for s in samples]      # values of every run
        out[f"{prefix}{k}_ms"] = st.mean(v)       # mean
        out[f"{prefix}{k}_ms_median"] = st.median(v)  # median
        out[f"{prefix}{k}_ms_std"] = st.pstdev(v)  # standard deviation
    return out                                    # return


def setup(docs, curve="SS512", dense_threshold=None):
    """Build the standard system for the experiments: 1 AA, 1 DO, 1 DU (attribute = auditor)."""
    s = System(curve)
    s.add_authority("AA1")
    s.add_owner("DO1", "AA1", "(auditor or engineer)")
    t0 = time.perf_counter()
    ds, tim = s.outsource("DO1", docs, dense_threshold=dense_threshold)
    tim["outsource_wall"] = (time.perf_counter() - t0) * 1e3
    du = s.add_user("DU1", {"AA1": ["auditor"]})
    du.unlock_domain(ds)          # the CP-ABE unlock is done once, not a per-query cost
    return s, ds, du, tim


def print_setup(n, ds, tim):
    """Show the setup information."""
    print(f" N={n}: outsource={tim['outsource_wall'] / 1e3:.1f}s index={tim['index_generation']:.0f}ms "
          f"keywords={len(ds.postings)}", flush=True)


def run_query(s, ds, du, q, proof_mode="paths"):
    """One full query: DU builds the trapdoor -> proxy searches + builds the proof -> DU verifies.
    Returns (time per phase, size/result information); the main time names follow Chen, then SE-COLLAB's sub-steps."""
    t0 = time.perf_counter()
    tq, tq_t = du.gen_trapdoor(ds, q, s.proxy.pk)
    t1 = time.perf_counter()
    resp, srv = s.proxy.search(tq, proof_mode=proof_mode)
    t2 = time.perf_counter()
    ok, ver, _ = du.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)
    t3 = time.perf_counter()
    assert ok                     # during a benchmark the result must always verify
    times = {
        "query_gen": (t1 - t0) * 1e3,             # trapdoor + signature + NIZK
        "server_total": (t2 - t1) * 1e3,          # everything the proxy does (admission + transform + search + proof)
        "verify_total": (t3 - t2) * 1e3,          # the DU verifies (Phase 6)
        "end_to_end": (t3 - t0) * 1e3,            # all phases (network excluded)
        "trapdoor": tq_t["trapdoor"],             # Tq only (3 exp + 1 pairing) = the paper's Fig. 3
        "admission": sum(srv.get(k, 0) for k in
                         ("revocation_check", "verify_signature", "verify_zkp")),
        "transform": srv["transform"],            # Algorithm 1
        "search_core": srv["search_core"],        # pure search (Algorithm 2) = Figs. 4/5
        "bpl_retrieval": srv["bpl_retrieval"],    # parts of search_core (written to the CSV to compare search without fetch)
        "boolean_eval": srv["boolean_eval"],
        "result_fetch": srv["result_fetch"],
        "search_no_fetch": srv["bpl_retrieval"] + srv["boolean_eval"],   # search_core without result_fetch
        "proof_gen": srv["proof_gen"],
        "merkle_verify": ver["merkle_verify"],    # = Fig. 6
        "result_proof_verify": ver.get("result_proof_verify", 0.0),
    }
    proof_bytes = resp.proof_size_bytes()
    info = dict(rQ=len(resp.results), proof_bytes=proof_bytes,
                # response = (8-byte position + Enc(id) + C_i) per result + proof + the proxy's signature
                response_bytes=sum(8 + len(e) + len(c) for _, e, c in resp.results) + proof_bytes
                + 2 * len(s.group.serialize(s.proxy.pk)),
                ids={p for p, _, _ in resp.results})  # result (compared with the ground truth, not written to the CSV)
    return times, info


def measure(s, ds, du, q, reps, warmup, proof_mode="paths"):
    """Warm up first, then measure reps runs with the garbage collector off (as in Chen)."""
    for _ in range(warmup):
        run_query(s, ds, du, q, proof_mode)
    samples, info = [], {}
    gc.disable()
    try:
        for _ in range(max(1, reps)):
            m, info = run_query(s, ds, du, q, proof_mode)
            samples.append(m)
    finally:
        gc.enable()
    return summarize(samples), info


def supports(shape: str) -> bool:
    """SE-COLLAB supports AND / OR / NOT -> every shape of Exp.1."""
    return True


# ============================================================================
# 7) Experiments (AMTP Section V-B) + sanity check against the SE-COLLAB paper
# ============================================================================
def suite_paper(args):
    """Reproduce the settings of Figs. 2-6 of the SE-COLLAB paper (sanity check, synthetic corpus)."""
    # Fig. 2: index generation time with 10-40 files of 8 KB each
    print("[paper] Fig.2 index generation, 10-40 files x 8 KB")
    w = Writer("paper_fig2", args.out)
    for n in (10, 20, 30, 40):
        samples = []
        for r in range(args.reps):
            docs = synthetic_corpus(n, vocab=200, kw_per_doc=10, payload_bytes=8192, seed=r)
            _, _, _, tim = setup(docs)
            samples.append({k: tim[k] for k in ("index_generation", "aes_encrypt", "cpabe_encrypt", "rekeygen")})
        w.add(files=n, **summarize(samples))
    w.close()

    docs = synthetic_corpus(2000, vocab=300, kw_per_doc=20, payload_bytes=1024, seed=1)
    s, ds, du, _ = setup(docs)
    vocab = [w_ for w_, _ in doc_freq(docs).most_common()]

    # Figs. 3/4: trapdoor and search vs the number of query keywords (25-200)
    print("[paper] Fig.3/4 trapdoor + search vs #query keywords (25-200, AND-chain)")
    w = Writer("paper_fig3_4", args.out)
    for k in (25, 50, 75, 100, 125, 150, 175, 200):
        # chained ANDs give few results -> the figure reflects the per-keyword cost, not the cost of many results
        res, qi = measure(s, ds, du, " AND ".join(vocab[:k]), args.reps, args.warmup)
        qi.pop("ids")
        w.add(keywords=k, **qi, **res)
    w.close()

    # Figs. 5/6: search and verification vs the number of returned ciphertexts (5-40)
    print("[paper] Fig.5/6 search + verification vs #returned ciphertexts (5-40)")
    # dedicated corpus: plant keyword "r<k>" in exactly k documents -> exact control of the result size
    base = synthetic_corpus(2000, vocab=300, kw_per_doc=10, payload_bytes=1024, seed=2)
    for k in (5, 10, 15, 20, 25, 30, 35, 40):
        for i in range(k):
            base[i * (len(base) // k)][2].append(f"r{k}")
    s, ds, du, _ = setup(base)
    w = Writer("paper_fig5_6", args.out)
    for k in (5, 10, 15, 20, 25, 30, 35, 40):
        res, qi = measure(s, ds, du, f"r{k}", args.reps, args.warmup)
        qi.pop("ids")
        assert qi["rQ"] == k
        w.add(ciphertexts=k, **qi, **res)
    w.close()


def suite_exp1(args):
    """AMTP Exp.1: every size N x every k_Q x the 4 query shapes (SE-COLLAB supports every shape).
    By default it replays the shared results/exp1_queries.json (or the file given with --queries), as Du does.
    Only if the file does not exist are queries generated with amtp_dataset.make_queries (same seed = same queries)
    and saved as the shared file -> an existing shared query file is never overwritten.
    Every query is checked against the ground truth of a plaintext index -> results must match exactly."""
    D = dataset()                                 # shared dataset
    path = args.queries or DEFAULT_QUERIES        # query file to replay
    replay = None                                 # queries loaded from the file
    if os.path.exists(path):                      # the shared query file exists
        with open(path, encoding="utf-8") as f:
            replay = json.load(f)                 # [{"N","kQ","shape","query",...}, ...]
        print(f"[queries] replay {os.path.relpath(path)} ({len(replay)} queries)")
    elif args.queries:                            # a file was given but not found
        raise SystemExit(f"query file not found: {path}")
    else:
        print("[queries] shared query file not found -> generating with amtp_dataset.make_queries (same seed = same queries)")
    sizes = sorted({x["N"] for x in replay}) if replay else args.sizes  # sizes to run
    print(f"[exp1] Boolean search scalability  sizes={sizes}")
    w = Writer("exp1_boolean_scalability", args.out)
    exported = []                                 # queries to save
    for n in sizes:                               # every database size
        src = D.sample(n, args.domains, args.data)  # n documents (the same set for every scheme)
        inv = D.inverted_index(src)               # plaintext index for the ground truth
        if replay:                                # queries from the file
            qs = [x for x in replay if x["N"] == n]
        else:                                     # generate queries
            qs = [dict(N=n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)]
            exported += [dict(q, dataset=D.DATASET_TAG, seed=args.seed, domains=args.domains) for q in qs]
        s, ds, du, tim = setup(to_secollab(src, args.data), dense_threshold=args.dense_threshold)
        print_setup(n, ds, tim)
        universe = set(range(n))
        for q in qs:                              # every query
            base = dict(N=n, kQ=q["kQ"], shape=q["shape"], domain=q.get("domain", ""))
            if not supports(q["shape"]):
                w.add(**base, status="N/A")
                continue
            ast = bool_parse(q["query"])
            res, qi = measure(s, ds, du, q["query"], args.reps, args.warmup)
            gt = bool_eval_sets(ast, inv, universe)  # correct answer
            assert qi.pop("ids") == gt, f"search result differs from the ground truth: {q['query']}"
            p_q = sum(len(inv.get(t, ())) for t in bool_keywords(ast))  # total postings of every keyword
            w.add(**base, status="ok", rQ=qi["rQ"], pQ=p_q, proof_bytes=qi["proof_bytes"],
                  response_bytes=qi["response_bytes"], **res)
        del s, ds, du, src, inv                   # free RAM before building the next N
        gc.collect()
    w.close()
    if exported:                                  # save the generated queries
        qpath = DEFAULT_QUERIES                   # shared query file (outside secollab/)
        D.save_queries(qpath, exported)
        print(f"-> {os.path.relpath(qpath)}  (replay the identical workload in AMTP / other baselines)")


def suite_exp2(args):
    """AMTP Exp.2: proof/verification vs r_Q on the same documents as every scheme
    (results/exp2_layouts.json: clustered / dispersed / partition_spread place the same keyword in the same files).
    SE-COLLAB has no partitions: clustered = adjacent leaves of the data Merkle tree (many shared path nodes);
    measured both with one proof path per file (as in the paper) and with a multiproof."""
    D = dataset()
    lay = D.load_exp2_layouts()
    n = lay["N"]
    print(f"[exp2] selective proof / verification  N={n} layouts={list(lay['layouts'])}")
    docs = to_secollab(D.sample(n, lay["domains"], args.data), args.data)
    for i, words in D.exp2_markers(lay, n).items():
        docs[i][2].extend(sorted(words))
    s, ds, du, tim = setup(docs, dense_threshold=args.dense_threshold)
    print_setup(n, ds, tim)
    w = Writer("exp2_selective_proof", args.out)
    for r in lay["rq"]:
        for name, spec in lay["layouts"].items():
            for mode in ("paths", "multi"):
                res, qi = measure(s, ds, du, f"{spec['prefix']}{r}", args.reps, args.warmup, mode)
                qi.pop("ids")
                assert qi["rQ"] == r                        # must return exactly r files
                w.add(N=n, rQ=r, layout=name, proof_mode=mode, proof_bytes=qi["proof_bytes"],
                      response_bytes=qi["response_bytes"], **res)
    w.close()


def suite_exp5(args):
    """AMTP Exp.5 on the shared workload results/exp5_workload.json: D data owners (1 owner = 1 domain) on the same
    proxy and ledger, following the paper's multi-DO model (each owner anchors its own root) -> no per-domain keyword
    is needed. Only the target owner (DO00 = groups[0]) is searched, with every query shape.
    update: SE-COLLAB has no dynamic update (it must outsource the whole set again) -> rows with status=N/A.
    The owners of one D are the first owners of the next D, so owners are added incrementally (no repeated
    outsourcing), and the roots of existing owners on the ledger are checked to stay unchanged when owners are added."""
    D = dataset()
    meta, groups, queries, _ = D.load_exp5_workload(args.exp5_workload, args.data)
    counts = [d for d in meta["domain_counts"] if d <= len(groups) and d in args.d_counts]
    inv = D.inverted_index(groups[0])
    universe = set(range(len(groups[0])))
    print(f"[exp5] multi-owner  D={counts} per-domain={meta['per_domain']} queries={len(queries)}")
    s = System()
    s.add_authority("AA1")
    dss = []
    du = None
    w = Writer("exp5_domains", args.out)
    for nd in counts:
        before = dict(s.ledger.merkle_roots)                # roots of existing owners before adding new owners
        t0 = time.perf_counter()
        for k in range(len(dss), nd):                       # new owners of this D
            s.add_owner(f"DO{k:02d}", "AA1", "(auditor or engineer)")
            dss.append(s.outsource(f"DO{k:02d}", to_secollab(groups[k], args.data),
                                   dense_threshold=args.dense_threshold)[0])
        if du is None:
            du = s.add_user("DU1", {"AA1": ["auditor"]})
            du.unlock_domain(dss[0])                        # search only the target owner
        print(f" D={nd}: outsource {time.perf_counter() - t0:.1f}s", flush=True)
        assert all(s.ledger.merkle_roots[k] == v for k, v in before.items()), "root of an existing owner changed"
        base = dict(scheme="SE-COLLAB[37]", deploy_model="per_owner", domains=nd, N_target=meta["per_domain"],
                    N_total=nd * meta["per_domain"])
        for q in queries:
            ast = bool_parse(q["query"])
            res, qi = measure(s, dss[0], du, q["query"], args.reps, args.warmup, args.proof_mode)
            assert qi.pop("ids") == bool_eval_sets(ast, inv, universe), f"result differs from the ground truth: {q['query']}"
            w.add(**base, kQ=q["kQ"], q=q["q"], shape=q["shape"], op="query", status="ok", proof_mode=args.proof_mode,
                  rQ=qi["rQ"],
                  proof_bytes=qi["proof_bytes"], response_bytes=qi["response_bytes"], **res)
        w.add(**base, op="update_one_domain", update_kind="none", status="N/A")
    w.close()


def measure_fn(fn, reps, warmup):
    """Like measure, but takes a function fn() -> (times, info); returns (time summary, info of every measured run)."""
    for _ in range(warmup):
        fn()
    samples, infos = [], []
    gc.disable()
    try:
        for _ in range(max(1, reps)):
            m, info = fn()
            samples.append(m)
            infos.append(info)
    finally:
        gc.enable()
    return summarize(samples), infos


def q_text(keywords) -> str:
    return " AND ".join(f'"{k}"' for k in keywords)


# ---------------- dataset-v4 suites (the advisor's plan; shared files in datasets/arxiv/data_v4/ used by every scheme)
def suite_search1(args):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl of every domain at every files-per-domain size;
    every query's result must equal its result_size in the file and the plaintext ground truth."""
    D = dataset()
    qs = D.search_single_queries()
    plan = D.search1_points(qs, args.fpd, args.fix, args.s1_kq, args.all_points)
    print(f"[search1] domains={args.s_domains} files/domain={args.fpd} queries={len(qs)} "
          f"points={sum(map(len, plan.values()))} proof={args.proof_mode}")
    w = Writer("search_single", args.out)
    for dname in args.s_domains:
        for n in args.fpd:
            mine = [q for q in plan[n] if q["domain"] == dname]
            if not mine:
                continue
            src = D.domain_docs(dname, n, args.data)
            inv = D.inverted_index(src)
            s, ds, du, tim = setup(to_secollab(src, args.data), dense_threshold=args.dense_threshold)
            print_setup(n, ds, tim)
            for q in mine:
                ast = bool_parse(q["text"])
                res, qi = measure(s, ds, du, q["text"], args.reps, args.warmup, args.proof_mode)
                ids = qi.pop("ids")
                assert len(ids) == q["result_size"][str(n)] and ids == bool_eval_sets(ast, inv, set(range(n))), \
                    f"result mismatch: {q['query_id']} n={n}"
                w.add(scheme="SE-COLLAB[37]", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", proof_mode=args.proof_mode, rQ=qi["rQ"], pQ=sum(len(inv.get(t, ())) for t in bool_keywords(ast)),
                      proof_bytes=qi["proof_bytes"], response_bytes=qi["response_bytes"], **res)
            del s, ds, du, src, inv
            gc.collect()
    w.close()


def suite_verify1(args):
    """Verification 1.1 (single domain): rows single_domain of verify_keywords.csv at --fix files per domain;
    x axis = target result size 10 / 100 / 1,000 / 10,000 (5 real keywords per target per domain)."""
    D = dataset()
    rows = D.verify_keywords("single_domain", args.fix)
    print(f"[verify1] files/domain={args.fix} keywords={len(rows)} proof={args.proof_mode}")
    w = Writer("verify_single", args.out)
    for dname in args.s_domains:
        s, ds, du, tim = setup(to_secollab(D.domain_docs(dname, args.fix, args.data), args.data),
                               dense_threshold=args.dense_threshold)
        print_setup(args.fix, ds, tim)
        for r in (r for r in rows if r["domain"] == dname):
            res, qi = measure(s, ds, du, q_text([r["keyword"]]), args.reps, args.warmup, args.proof_mode)
            qi.pop("ids")
            assert qi["rQ"] == r["result_size"], f"{r['keyword']}: {qi['rQ']} != {r['result_size']}"
            w.add(scheme="SE-COLLAB[37]", domain=dname, N=args.fix, keyword=r["keyword"],
                  target_results=r["target_results"], rank=r["rank"], status="ok", proof_mode=args.proof_mode,
                  rQ=qi["rQ"], proof_bytes=qi["proof_bytes"], response_bytes=qi["response_bytes"], **res)
        del s, ds, du
        gc.collect()
    w.close()


_CHEAT = {"modify": "modify", "hide": "omit", "inject": "inject", "old_version": "old_version"}


def run_tampered(s, ds, du, q, kind, pos, proof_mode, old=None):
    """One query round where the cloud cheats on the document at position pos; times only the DU's verification.
    modify = alter the ciphertext, hide = drop it, inject = add a document that does not match the query,
    old_version = the old ciphertext old[pos].
    Returns ({verify_total}, {detected, localized}): detected = verification fails; localized = documents the DU can
    point to (path mode points to ciphertexts that do not match the Merkle root; a multiproof cannot -> 0)."""
    tq, _ = du.gen_trapdoor(ds, q, s.proxy.pk)
    tamper = _CHEAT.get(kind) if pos else None
    resp, _ = s.proxy.search(tq, proof_mode=proof_mode, tamper=tamper, tamper_pos=pos, tamper_old=old)
    t0 = time.perf_counter()
    ok, _, bad = du.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)
    t1 = time.perf_counter()
    return {"verify_total": (t1 - t0) * 1e3}, {"detected": not ok, "localized": len(bad) if proof_mode == "paths" else 0}


def suite_tamper(args):
    """Verification 1.2 (single domain): tamper_sets.jsonl per domain: a keyword (~2,000 results) at files_per_domain.
    The cloud cheats on the first t documents of tamper_order (modify / hide / old_version) or adds the first t
    documents of amtp_dataset.inject_order that do not match the query (inject); measures verification time and
    counts detected runs / localized files.
    check_mode: early = --proof-mode (multiproof: checks the whole set, cannot localize), full = one path per file
    (localizes). SE-COLLAB checks the Merkle paths of the received ciphertexts -> modify / old_version are detected,
    but neither completeness nor whether a document matches the query is checked -> hide / inject are not detected."""
    D = dataset()
    sets = [r for r in D.tamper_sets() if r["domain"] in args.s_domains]
    w = Writer("tamper_detection", args.out)
    modes = [("early", args.proof_mode)] + ([("full", "paths")] if args.proof_mode != "paths" else [])
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = D.domain_docs(dname, n, args.data)
        pos_of = {d.doc_id: i for i, d in enumerate(src)}
        s, ds, du, tim = setup(to_secollab(src, args.data), dense_threshold=args.dense_threshold)
        print_setup(n, ds, tim)
        k_aes = H(du.unlock_domain(ds), tag=b"AES")
        inj = D.inject_order(ts, args.data)
        q = q_text([ts["query_keyword"]])
        base = dict(scheme="SE-COLLAB[37]", domain=dname, N=n, keyword=ts["query_keyword"], rQ=ts["result_size"])
        for check, mode in modes:
            res, infos = measure_fn(lambda: run_tampered(s, ds, du, q, "none", None, mode), args.reps, args.warmup)
            assert not any(i["detected"] for i in infos), "honest result failed verification"
            w.add(**base, check_mode=check, proof_mode=mode, tamper="none", tampered=0, status="ok",
                  detected_runs=0, runs=len(infos), localized=0, **res)
            for kind in args.tamper_kinds:
                for t in ts["tamper_counts"]:
                    ids = inj[:t] if kind == "inject" else ts["tamper_order"][:t]
                    pos = {pos_of[i] for i in ids}
                    old = ({p: aes_encrypt(k_aes, p.to_bytes(8, "big") + D.read_bytes(src[p], args.data)
                                           + D.OLD_VERSION_SUFFIX) for p in pos} if kind == "old_version" else None)
                    res, infos = measure_fn(lambda: run_tampered(s, ds, du, q, kind, pos, mode, old),
                                            args.reps, args.warmup)
                    w.add(**base, check_mode=check, proof_mode=mode, tamper=kind, tampered=t, status="ok",
                          detected_runs=sum(i["detected"] for i in infos), runs=len(infos),
                          localized=infos[-1]["localized"], **res)
        del s, ds, du, src
        gc.collect()
    w.close()


def multi_build(named_docs, args):
    """1 owner = 1 domain on the same proxy / ledger; one DU satisfies every owner's policy (one unlock per owner,
    outside the timing). Returns (System, [each owner's dataset], DU)."""
    s = System()
    s.add_authority("AA1")
    t0 = time.perf_counter()
    dss = []
    for name, docs in named_docs:
        s.add_owner(name, "AA1", "(auditor or engineer)")
        dss.append(s.outsource(name, to_secollab(docs, args.data), dense_threshold=args.dense_threshold)[0])
    du = s.add_user("DU1", {"AA1": ["auditor"]})
    for ds in dss:
        du.unlock_domain(ds)
    print(f" {len(dss)} owners, {sum(len(d) for _, d in named_docs)} files: outsource {time.perf_counter() - t0:.1f}s",
          flush=True)
    return s, dss, du


def run_xquery(s, dss, du, q, proof_mode):
    """Cross-domain search with a single trapdoor ([ASSUMPTION] 12): the DU builds the trapdoor once -> the proxy
    checks / transforms it once and searches every owner -> the DU checks the Merkle root per owner + one signature
    over the combined result. Returns (times, sizes / results per owner)."""
    t0 = time.perf_counter()
    tq, tq_t = du.gen_trapdoor(dss, q, s.proxy.pk)
    t1 = time.perf_counter()
    mresp, srv = s.proxy.search_multi(tq, proof_mode=proof_mode)
    t2 = time.perf_counter()
    ok, ver = du.verify_multi(mresp, s.ledger, s.proxy.pk, s.proxy.g)
    t3 = time.perf_counter()
    assert ok                     # during a benchmark the result must always verify
    times = {
        "query_gen": (t1 - t0) * 1e3, "server_total": (t2 - t1) * 1e3, "verify_total": (t3 - t2) * 1e3,
        "end_to_end": (t3 - t0) * 1e3, "trapdoor": tq_t["trapdoor"],
        "admission": sum(srv.get(k, 0) for k in ("revocation_check", "verify_signature", "verify_zkp")),
        "transform": srv["transform"], "search_core": srv["search_core"], "proof_gen": srv["proof_gen"],
        "bpl_retrieval": srv["bpl_retrieval"], "boolean_eval": srv["boolean_eval"], "result_fetch": srv["result_fetch"],
        "search_no_fetch": srv["bpl_retrieval"] + srv["boolean_eval"],                  # search_core without result_fetch
        "merkle_verify": ver.get("merkle_verify", 0.0), "result_proof_verify": ver.get("result_proof_verify", 0.0),
    }
    proof = sum(r.proof_size_bytes() for r in mresp.responses)
    info = {"rQ": sum(len(r.results) for r in mresp.responses), "proof_bytes": proof,
            "response_bytes": sum(8 + len(e) + len(c) for r in mresp.responses for _, e, c in r.results) + proof
            + 2 * len(s.group.serialize(s.proxy.pk)),
            "rQ_per_domain": [len(r.results) for r in mresp.responses]}
    return times, info


def suite_xsearch(args):
    """Search 2.1 (multi domain): queries_boolean_multi.jsonl over 4 domains (owners) of --fix files each;
    each domain's result must equal its result_size_per_domain in the file."""
    D = dataset()
    qs = D.boolean_multi_queries()
    names = list(D.DOMAINS)
    print(f"[xsearch] owners={names} files/domain={args.fix} queries={len(qs)} proof={args.proof_mode}")
    s, dss, du = multi_build([(d, D.domain_docs(d, args.fix, args.data)) for d in names], args)
    w = Writer("search_multi", args.out)
    for q in qs:
        res, infos = measure_fn(lambda: run_xquery(s, dss, du, q["text"], args.proof_mode), args.reps, args.warmup)
        info = infos[-1]
        want = [q["result_size_per_domain"][d][str(args.fix)] for d in names]
        assert info["rQ_per_domain"] == want, f"{q['query_id']}: {info['rQ_per_domain']} != {want}"
        info["rQ_per_domain"] = " ".join(map(str, want))
        w.add(scheme="SE-COLLAB[37]", domains=len(dss), N_per_domain=args.fix, query_id=q["query_id"], kQ=q["kQ"],
              shape=q["shape"], status="ok", proof_mode=args.proof_mode, **info, **res)
    w.close()


def suite_xverify(args):
    """Verification 2.1 (multi domain): rows multi_domain of verify_keywords.csv at --fix files per domain over 4 owners."""
    D = dataset()
    rows = D.verify_keywords("multi_domain", args.fix)
    names = list(D.DOMAINS)
    print(f"[xverify] files/domain={args.fix} keywords={len(rows)} proof={args.proof_mode}")
    s, dss, du = multi_build([(d, D.domain_docs(d, args.fix, args.data)) for d in names], args)
    w = Writer("verify_multi", args.out)
    for r in rows:
        res, infos = measure_fn(lambda: run_xquery(s, dss, du, q_text([r["keyword"]]), args.proof_mode),
                                args.reps, args.warmup)
        info = infos[-1]
        assert info["rQ_per_domain"] == r["result_size_per_domain"], f"{r['keyword']}: {info['rQ_per_domain']}"
        info["rQ_per_domain"] = " ".join(map(str, info["rQ_per_domain"]))
        w.add(scheme="SE-COLLAB[37]", domains=len(dss), N_per_domain=args.fix, keyword=r["keyword"],
              target_results=r["target_results"], rank=r["rank"], status="ok", proof_mode=args.proof_mode,
              **info, **res)
    w.close()


def suite_xdomains(args):
    """Search 2.2 / Verification 2.2: the same files (--fix per domain of all 4 datasets) regrouped into D = 1..32 owners
    by arXiv category (domain_groups.csv); every boolean_multi query is sent to every owner.
    The total must equal the per-domain totals in the file (the groups split the same files)."""
    D = dataset()
    qs = D.select_queries(D.boolean_multi_queries(), args.x_kq, args.shapes, args.max_queries)
    names = list(D.DOMAINS)
    print(f"[xdomains] D={args.d_counts} files/domain={args.fix} queries={len(qs)} proof={args.proof_mode}")
    w = Writer("domains_scaling", args.out)
    for dc in args.d_counts:
        groups = D.domain_groups(dc, args.fix, names, args.data)
        s, dss, du = multi_build([(f"DO{dc}_{g}", docs) for g, docs in groups], args)
        for q in qs:
            res, infos = measure_fn(lambda: run_xquery(s, dss, du, q["text"], args.proof_mode), args.reps, args.warmup)
            info = infos[-1]
            info.pop("rQ_per_domain")
            want = sum(q["result_size_per_domain"][d][str(args.fix)] for d in names)
            assert info["rQ"] == want, f"{q['query_id']} D={dc}: {info['rQ']} != {want}"
            w.add(scheme="SE-COLLAB[37]", domains=len(dss), N_total=sum(len(g) for _, g in groups),
                  query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"], status="ok", proof_mode=args.proof_mode,
                  **info, **res)
        del s, dss, du, groups
        gc.collect()
    w.close()


def suite_revocation(args):
    """Revocation cost as the number of users holding the same attribute as the revoked user grows
    (they must receive new keys in Step 4)."""
    print("[revocation] Phase-8 cost vs #users sharing the revoked user's attribute")
    w = Writer("revocation", args.out)
    docs = synthetic_corpus(1000, vocab=200, kw_per_doc=8)
    for users in (1, 5, 10, 20, 50):
        samples = []
        for _ in range(max(3, args.reps // 5)):
            s = System()
            s.add_authority("AA1")
            s.add_owner("DO1", "AA1", "(auditor or engineer)")
            s.outsource("DO1", docs)
            for u in range(users):
                s.add_user(f"u{u}", {"AA1": ["auditor"]})
            s.add_user("victim", {"AA1": ["auditor"]})      # the user to revoke
            samples.append(s.revoke("victim", "AA1"))
        w.add(users=users, **summarize(samples))
    w.close()


# ============================================================================
# 8) Demo — a small example showing every step  (python3 se_collab_sim.py demo)
# ============================================================================

def run_demo(_args=None):
    print("== SE-COLLAB demo ==")
    s = System()
    s.add_authority("AA_manu")                                           # Phase 1: the manufacturer's AA
    s.add_owner("factory", "AA_manu", "(auditor or engineer)")           # DO + access policy
    docs = synthetic_corpus(200, vocab=40, kw_per_doc=5, seed=1)
    ds, t = s.outsource("factory", docs)                                 # Phase 2-3
    print(f"[Phase 3] outsourced {ds.n} docs, {len(ds.postings)} keywords, "
          f"index {t['index_generation']:.2f} ms, Merkle root anchored on ledger")
    alice = s.add_user("alice", {"AA_manu": ["auditor"]})                # satisfies the policy
    eve = s.add_user("eve", {"AA_manu": ["supplier"]})                   # does not satisfy the policy
    q = "(kw00001 OR kw00002) AND kw00003"
    tq, tt = alice.gen_trapdoor(ds, q, s.proxy.pk)                       # Phase 4
    print(f"[Phase 4] query = {q}")
    print(f"          trapdoor {tt['trapdoor']:.2f} ms + signature {tt['signature']:.2f} ms "
          f"+ NIZK {tt['zkp']:.2f} ms")
    resp, st = s.proxy.search(tq)                                        # Phase 5
    print(f"[Phase 5] proxy admitted + transformed + searched: {len(resp.results)} results "
          f"(search core {st['search_core']:.3f} ms)")
    ok, vt, _ = alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)      # Phase 6
    print(f"[Phase 6] verify = {ok} (Merkle {vt['merkle_verify']:.3f} ms)")
    plain, _ = alice.decrypt(ds, resp)                                   # Phase 7
    print(f"[Phase 7] decrypted doc ids: {sorted(d for d, _ in plain)[:10]}")
    try:
        eve.gen_trapdoor(ds, q, s.proxy.pk)
    except PermissionError as e:
        print(f"[access ] eve (supplier) rejected: {e}")
    bad, _ = s.proxy.search(tq, tamper="modify")                         # cheating cloud: modifies a ciphertext
    ok, _, pos = alice.verify(bad, s.ledger, s.proxy.pk, s.proxy.g, check_result_proof=False)
    print(f"[attack ] modified ciphertext -> verify = {ok}, tampered position = {pos}")
    om, _ = s.proxy.search(tq, tamper="omit")                            # cheating cloud: drops a result
    ok, _, _ = alice.verify(om, s.ledger, s.proxy.pk, s.proxy.g)
    print(f"[attack ] omitted 1 result -> verify = {ok}  (SE-COLLAB does not check completeness: the gap AMTP closes)")
    s.revoke("alice", "AA_manu")                                         # Phase 8
    try:
        s.proxy.search(alice.gen_trapdoor(ds, q, s.proxy.pk)[0])
    except PermissionError as e:
        print(f"[Phase 8] after revocation alice rejected: {e}")


# ============================================================================
# 9) Selftest — correctness tests  (python3 se_collab_sim.py selftest)
# ============================================================================

def _env():
    """Example system: 2 AAs, 1 DO with policy = (auditor or engineer).
    alice = auditor (satisfies the policy), bob = engineer (satisfies), eve = supplier (does not)."""
    s = System()
    s.add_authority("AA_manu")
    s.add_authority("AA_reg")
    s.add_owner("factory", "AA_manu", "(auditor or engineer)")
    docs = synthetic_corpus(400, vocab=60, kw_per_doc=6, seed=1)
    ds, _ = s.outsource("factory", docs)
    alice = s.add_user("alice", {"AA_manu": ["auditor"], "AA_reg": ["regulator"]})
    bob = s.add_user("bob", {"AA_manu": ["engineer"]})
    eve = s.add_user("eve", {"AA_manu": ["supplier"]})
    return s, ds, docs, alice, bob, eve


def _expected(docs, query):
    """Correct answer: evaluate the query on the plaintext with plain sets (the reference)."""
    sets = {}
    for i, (_, _, kws) in enumerate(docs):
        for w in kws:
            sets.setdefault(w, set()).add(i)
    return bool_eval_sets(bool_parse(query), sets, set(range(len(docs))))


# covers: single keyword, AND, OR, both nested forms, NOT, and a keyword not in the index
SELFTEST_QUERIES = [
    "kw00001",
    "kw00001 AND kw00002",
    "kw00001 OR kw00007",
    "(kw00001 OR kw00002) AND (kw00003 OR kw00004)",
    "(kw00001 AND kw00002) OR (kw00003 AND kw00004)",
    "kw00001 AND NOT kw00002",
    "NOT kw00000",
    "kw00001 AND doesnotexist",
    "kw00001 OR doesnotexist",
]


def _t_boolean(env, q):
    """Search on encrypted data must equal the plaintext reference + verify + decrypt to the right doc ids."""
    s, ds, docs, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, q, s.proxy.pk)
    resp, _ = s.proxy.search(tq)
    assert {p for p, _, _ in resp.results} == _expected(docs, q)
    assert alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]
    plain, _ = alice.decrypt(ds, resp)
    assert sorted(d for d, _ in plain) == sorted(_expected(docs, q))


def t_multiproof_mode(env):
    """A multiproof must verify and be smaller than one proof path per file."""
    s, ds, docs, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001 OR kw00002", s.proxy.pk)
    resp, _ = s.proxy.search(tq, proof_mode="multi")
    assert alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]
    paths, _ = s.proxy.search(tq, proof_mode="paths")
    assert resp.proof_size_bytes() < paths.proof_size_bytes()


def t_trapdoor_size_constant(env):
    """The trapdoor has the same number of group elements whether the query has 1 or 20 keywords."""
    s, ds, _, alice, *_ = env
    t1 = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)[0]
    t2 = alice.gen_trapdoor(ds, " AND ".join(f"kw{i:05d}" for i in range(20)), s.proxy.pk)[0]
    assert type(t1.C1) is type(t2.C1) and type(t1.C3) is type(t2.C3)


def t_tamper_detected(env):
    """The cloud flips one ciphertext bit -> the DU must detect it and identify the document's position."""
    s, ds, _, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    resp, _ = s.proxy.search(tq, tamper="modify")
    ok, _, bad = alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g, check_result_proof=False)
    assert not ok and bad == [resp.results[0][0]]


def t_omission_not_detected(env):
    """SE-COLLAB's weakness: it checks only the received ciphertexts, not completeness
    -> a cloud that silently drops one result still passes (the gap AMTP's PAPC closes)."""
    s, ds, _, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    full, _ = s.proxy.search(tq)
    resp, _ = s.proxy.search(tq, tamper="omit")
    assert len(resp.results) == len(full.results) - 1
    assert alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]


def t_unauthorised_user(env):
    """eve (supplier) does not satisfy the policy -> cannot open CT_key -> cannot build a trapdoor."""
    s, ds, _, _, _, eve = env
    try:
        eve.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    except PermissionError:
        return
    raise AssertionError("unauthorised user formed a trapdoor")


def t_forged_signature(env):
    """alice's trapdoor relabelled as bob's -> the signature does not match and the proxy must reject it."""
    s, ds, _, alice, _, _ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    tq.du_id = "bob"
    try:
        s.proxy.search(tq)
    except PermissionError:
        return
    raise AssertionError("forged trapdoor accepted")


def t_incremental_merkle(_env=None):
    """Incremental leaf updates must give the same root as rebuilding the whole tree."""
    data = [bytes([i]) * 4 for i in range(37)]       # 37 = odd, also tests the odd-node case
    t = MerkleTree(data)
    data[13] = b"new!"
    t.update_leaf(13, data[13])
    assert t.root == MerkleTree(data).root


def t_phrase_keywords(_env=None):
    """Multi-word keywords as in dataset-v3 (with or without quotes) must be found as one keyword."""
    assert bool_parse("general method AND possible description") == \
        ("AND", ("KW", "general method"), ("KW", "possible description"))
    assert bool_parse('("Mordell-Weil  group") OR x') == ("OR", ("KW", "mordell-weil group"), ("KW", "x"))
    s = System()
    s.add_authority("AA")
    s.add_owner("do", "AA", "(auditor or engineer)")
    docs = [(0, b"a", ["general method", "neural network"]), (1, b"b", ["general method"]),
            (2, b"c", ["possible description", "neural network"])]
    ds, _ = s.outsource("do", docs)
    a = s.add_user("alice", {"AA": ["auditor"]})
    for q, want in (("general method AND neural network", {0}),
                    ("(general method) OR (possible description)", {0, 1, 2})):
        resp, _ = s.proxy.search(a.gen_trapdoor(ds, q, s.proxy.pk)[0])
        assert {p for p, _, _ in resp.results} == want == _expected(docs, q)


def t_revocation(_env=None):
    """After revoking mallory: search fails, the old key cannot open the new CT_key, alice still works."""
    s = System()
    s.add_authority("AA")
    s.add_owner("do", "AA", "(auditor or engineer)")
    ds, _ = s.outsource("do", synthetic_corpus(100, vocab=30, kw_per_doc=4))
    a = s.add_user("alice", {"AA": ["auditor"]})
    m = s.add_user("mallory", {"AA": ["auditor"]})
    s.proxy.search(m.gen_trapdoor(ds, "kw00001", s.proxy.pk)[0])     # search works before the revocation
    s.revoke("mallory", "AA")
    try:
        s.proxy.search(m.gen_trapdoor(ds, "kw00001", s.proxy.pk)[0])
        raise AssertionError("revoked user could still search")
    except PermissionError:
        pass
    m.domain_keys.clear()
    assert m.unlock_domain(ds) is None
    resp, _ = s.proxy.search(a.gen_trapdoor(ds, "kw00001", s.proxy.pk)[0])
    assert a.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]


def run_selftest(_args=None):
    env = _env()
    tests = [(f"t_boolean[{q}]", (lambda q=q: _t_boolean(env, q))) for q in SELFTEST_QUERIES]
    tests += [(f.__name__, (lambda f=f: f(env))) for f in (
        t_multiproof_mode, t_trapdoor_size_constant, t_tamper_detected, t_omission_not_detected,
        t_unauthorised_user, t_forged_signature, t_incremental_merkle, t_phrase_keywords, t_revocation)]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001 - report every failure
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")
    print(f"{passed}/{len(tests)} passed")
    if passed != len(tests):
        sys.exit(1)


# ============================================================================
# 10) main
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="SE-COLLAB [37] simulation")  # argument parser
    ap.add_argument("mode", choices=["demo", "selftest", "paper", "exp1", "exp2", "exp5", "revocation", "all",
                                     "search1", "verify1", "tamper", "xsearch", "xverify", "xdomains"],
                    help="all = paper + exp1 + exp2 + revocation")  # mode to run
    # ---- shared dataset (amtp_dataset.py) ----
    ap.add_argument("--data", default=None, help="dataset folder (default <repo>/data/amtp_file_db_v4 or AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="domains used")
    ap.add_argument("--seed", type=int, default=42, help="query generation seed (equals the dataset seed)")
    # ---- names and defaults as in chen_et_al_sim.py ----
    ap.add_argument("--reps", type=int, default=30, help="number of measured runs")
    ap.add_argument("--warmup", type=int, default=3, help="number of warm-up runs (not counted)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000],
                    help="sizes N of exp1 (at most 500,000 = 4 domains x 125,000)")
    ap.add_argument("--kq", type=int, nargs="+", default=[1, 2, 4, 8, 16], help="keywords per query")
    ap.add_argument("--queries-per-kq", type=int, default=1, help="queries per k_Q (exp1)")
    ap.add_argument("--queries", default=None,
                    help=f"query JSON file to replay (default {os.path.relpath(DEFAULT_QUERIES)})")
    ap.add_argument("--exp5-workload", default=os.path.join(HERE, "results", "exp5_workload.json"),
                    help="shared exp5 workload (python3 amtp_dataset.py exp5)")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "secollab"), help="output folder")
    # ---- SE-COLLAB only ----
    ap.add_argument("--dense-threshold", type=float, default=None,
                    help="df ratio above which the BPL is stored densely (0 = all dense, see [ASSUMPTION] 10)")
    # ---- tamper / xdomain (defaults from amtp_dataset, shared with AMTP) ----
    Dm = dataset()
    ap.add_argument("--s-domains", nargs="+", default=list(Dm.DOMAINS), help="v4 single-domain suites: domain")
    ap.add_argument("--fpd", type=int, nargs="+", default=Dm.V4_SIZES, help="search1: files per domain")
    ap.add_argument("--fix", type=int, default=Dm.V4_FIX, help="verify1 / xsearch / xverify / xdomains: files per domain")
    ap.add_argument("--s1-kq", type=int, default=Dm.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--d-counts", type=int, nargs="+", default=Dm.D_COUNTS, help="xdomains: number of domains")
    ap.add_argument("--max-queries", type=int, default=0, help="xdomains: use the first n queries (0 = all)")
    ap.add_argument("--x-kq", type=int, nargs="+", default=None, help="xdomains: only these kQ (default: all)")
    ap.add_argument("--shapes", nargs="+", default=None, choices=["AND", "OR", "AND_of_OR", "OR_of_AND"],
                    help="xdomains: only these query shapes (default: all)")
    ap.add_argument("--tamper-kinds", nargs="+", default=Dm.TAMPER_KINDS, choices=Dm.TAMPER_KINDS)
    ap.add_argument("--proof-mode", choices=["paths", "multi"], default="paths",
                    help="v4 suites: proof form (paths = one Merkle path per file as in the paper's Phase 6; "
                         "multi = our own multiproof, not in the paper)")
    a = ap.parse_args()                           # parse arguments
    run = {"demo": run_demo, "selftest": run_selftest, "paper": suite_paper, "exp1": suite_exp1,
           "exp2": suite_exp2, "exp5": suite_exp5, "revocation": suite_revocation, "search1": suite_search1,
           "verify1": suite_verify1, "tamper": suite_tamper, "xsearch": suite_xsearch, "xverify": suite_xverify,
           "xdomains": suite_xdomains}  # function of each mode
    for name in (["paper", "exp1", "exp2", "revocation"] if a.mode == "all" else [a.mode]):
        run[name](a)                              # run


if __name__ == "__main__":
    main()
