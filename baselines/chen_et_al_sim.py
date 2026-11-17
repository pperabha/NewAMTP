"""
chen_et_al_sim.py
============================================================================
Simulation of the baseline Chen et al. [40]
  L. Chen, Y. Wu, H. Zhang, J. Weng, Z. Liu,
  "Verifiable Multi-User Dynamic Searchable Symmetric Encryption With Forward
   and Backward Privacy Feasible for Cloud Storage",
  IEEE Transactions on Information Forensics and Security, vol. 21, 2026.

This code follows the paper's Sections II and IV:
  A. Bitmap index + homomorphic addition   (Section II-A, II-F)
  B. Setup / Share / Update                 (Algorithms 1, 2, 3 — DO)
  C. Search                                 (Algorithm 4 — DU + CS)
  D. Verify                                 (Algorithm 5 — DU)
A comment [Alg.4 L20] means Algorithm 4, line 20 of the paper (read the two side by side).

Measured for the comparison with AMTP (AMTP's Table IV):
  - Query Generation : O(n_w) * T_PRF                     (DU builds the tokens)
  - Search           : O(n_w * n_u) * (T_H + T_A + T_X)   (CS walks the chain + adds ciphertexts)
  - Verification     : O(r_C) * (T_PRF + T_X)             (DU computes F1(id) for every result)
  - Update           : O(N_u * m) * (T_PRF + T_H + T_Enc) (one entry for every authorised user)
  OpCounter counts every T_PRF / T_H / T_A / T_X / T_Enc to check the formulas above.

Points the paper leaves unclear or gets wrong, decided here (see the [ASSUMPTION]/[FIX] comments):
  1. [FIX] Alg.2 line 2 samples K_u at every Share -> sample it only at the user's first Share
     (sampling it again would make earlier shared data unsearchable)
  2. [FIX] CntDiffs stores only Enc(w, c) but Alg.4 line 4 needs ST_c -> encrypt (w, c, ST_c)
  3. [FIX] Alg.5 returns accept after the first keyword -> check every keyword before accepting,
     and reject when the CS does not return (Sum_e, proof) for every keyword of q (selftest t_reject_dropped_keyword)
  4. [ASSUMPTION] F1 has no stated key -> use K'_u (the DU can compute the proof, the CS cannot forge it)
  5. [ASSUMPTION] no primitives stated -> HMAC-SHA256/512 (PRF), SHA-256 (H1, H2),
     SHAKE-256 (H3 needs a gamma-bit output), AES-256-GCM (SE), lambda = 128 bits
  6. [ASSUMPTION] gamma (bitmap length) = N (paper: gamma >= N_max) + room for new documents in exp3
  7. [ASSUMPTION] Update supports both addition (+2^id) and deletion (-2^id mod n) as in Fig. 1(b)(c)
  8. [ASSUMPTION] share() accepts several documents at once (bitmaps of the same keyword merged into one entry),
     used only to build the initial index; exp3 updates one document at a time as in the paper (--update-mode per-doc)
  9. [ASSUMPTION] --scope queried: the arXiv dataset has many distinct keywords (N = 200,000 -> ~1.29 million),
     and Chen's full index = keywords x gamma bits (~32 GB), so entries are built only for the queried keywords
     (each with its complete bitmap over every document, so search/verify time equals the full index); the
     storage size is still reported for the full index

Workload: AMTP's shared dataset (dataset-v4, arXiv 4 domains x 125,000 files, parts in datasets/arxiv/data_v4/)
through amtp_dataset.py
  - N documents = the first N/4 files of each domain (no randomness) -> every scheme gets the same documents
  - keywords are the ones stored in documents.csv; exp3 uses real documents from insert_pool
  - exp1 checks every query against the ground truth of a plaintext index (must match exactly)

Run (pip install cryptography; unpack the dataset with datasets/arxiv/unpack.py into <repo>/data/amtp_file_db_v4,
or pass --data):
  python3 chen_et_al_sim.py demo                       # step by step + catching a cheating CS
  python3 chen_et_al_sim.py selftest                   # 12 correctness tests
  python3 chen_et_al_sim.py exp1                       # replay results/exp1_queries.json (default)
  python3 chen_et_al_sim.py exp2                  # replays results/exp2_layouts.json (N = 200k)
  python3 chen_et_al_sim.py exp3 --sizes 10000 50000 100000 200000 --batches 1 10 100 1000 --users 1
Every suite writes results/chen/chen_<suite>.csv (mean, median, std over --reps runs after --warmup warm-up runs)
============================================================================
"""

# ----------------------------------------------------------------------------- imports
import argparse                                   # command-line arguments
import csv                                        # write results as CSV
import gc                                         # garbage collector off while timing
import hashlib                                    # SHA-256 / SHAKE-256
import hmac                                       # HMAC (the PRF)
import json                                       # read/write query files
import os                                         # os.urandom for keys + paths
import sqlite3                                    # on-disk EDB (large N)
import statistics as st                           # mean / median / std
import sys                                        # sys.exit in the selftest
import tempfile                                   # temporary folder for SQLite
import time                                       # perf_counter for timing
from collections import defaultdict               # dict with automatic defaults
from dataclasses import dataclass                 # compact record type

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # AES-GCM for SE

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wire_sizes as W                            # noqa: E402  the same size rule for every scheme


# ============================================================================
# 0) operation counter -> checks that the numbers of T_PRF / T_H / ... match the formulas of Table IV
# ============================================================================
class OpCounter:                                  # holds the counters
    def __init__(self):                           # constructor
        self.reset()                              # all start at zero

    def reset(self):                              # reset before measuring each phase
        self.prf = 0                              # calls of the PRF F / F1 (T_PRF)
        self.hash = 0                             # calls of H1 / H2 / H3 (T_H)
        self.add = 0                              # homomorphic additions (T_A)
        self.xor = 0                              # XORs (T_X)
        self.enc = 0                              # bitmap encryptions Enc(sk, bs) (T_Enc)
        self.visited = 0                          # EDB entries the CS visits (total chain length)

    def snapshot(self):                           # current counters as a dict
        return dict(prf=self.prf, hash=self.hash, add=self.add, xor=self.xor,
                    enc=self.enc, visited=self.visited)


COUNT = OpCounter()                               # global counter for the whole file


# ============================================================================
# 1) Cryptographic primitives — PRF, hash, homomorphic addition, bitmap, SE
# ============================================================================

LAMBDA_BYTES = 16  # λ (security parameter) = 128 bits = 16 bytes, for the state ST_c and user keys
PROOF_BYTES = 32  # size of vt / proof = 32 bytes (F1 is HMAC-SHA256, 32-byte output)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def random_bytes(nbytes: int = LAMBDA_BYTES) -> bytes:
    """Secure random bytes = {0,1}^λ in the paper."""
    return os.urandom(nbytes)  # nbytes random bytes from the OS


def _enc(*parts) -> bytes:
    """Concatenate several values unambiguously (the || of the paper).

    Why: "ab"+"c" and "a"+"bc" both give "abc" when joined directly,
    so every piece is prefixed with its length.
    """
    out = bytearray()  # output buffer
    for p in parts:  # one piece at a time
        if isinstance(p, int):  # a number (e.g. the counter c or an id)
            p = str(p).encode()  # to text, then bytes (negative numbers such as -1 allowed)
        elif isinstance(p, str):  # a string (e.g. a keyword)
            p = p.encode("utf-8")  # UTF-8 bytes (any language)
        out += len(p).to_bytes(4, "big")  # 4-byte length prefix
        out += p  # then the data itself
    return bytes(out)  # return bytes


def xor(a: bytes, b: bytes) -> bytes:
    """XOR of two byte strings of equal length (⊕ in the paper).

    Converted to integers first, then XORed (about 10x faster than a byte loop)."""
    COUNT.xor += 1  # one T_X
    x = int.from_bytes(a, "big") ^ int.from_bytes(b, "big")  # XOR the whole value at once
    return x.to_bytes(len(a), "big")  # back to bytes of the same length


# ---------------------------------------------------------------------------
# every PRF and hash the paper uses
# ---------------------------------------------------------------------------

def F(K_u: bytes, w: str):
    """F_{K_u}(w) -> (K_w, K'_w)   [Alg.2/3 line 5, Alg.4 line 11]

    The user key K_u derives two keys for keyword w:
      K_w  = state key (for H1, H2)
      K'_w = counter key (for H3, which derives the bitmap encryption key)
    """
    COUNT.prf += 1  # one T_PRF
    out = hmac.digest(K_u, _enc("F", w), "sha512")  # HMAC-SHA512 gives 64 bytes
    return out[:32], out[32:]  # first half = K_w, second half = K'_w


def F1(key: bytes, *parts) -> bytes:
    """F1(...) — the PRF that builds the validator vt and the proof  [Alg.2/3 line 18, Alg.5]

    [ASSUMPTION] the paper writes only F1(w||c) and F1(id), without a key.
    We use the user's key K'_u because (1) the DU must compute it during Verify
    and (2) the CS must not know the key, otherwise it could forge proofs.
    """
    COUNT.prf += 1  # one T_PRF
    return hmac.digest(key, _enc("F1", *parts), "sha256")  # one-shot HMAC-SHA256 (fast), 32 bytes


def H1(K_w: bytes, ST: bytes) -> bytes:
    """UT_c = H1(K_w, ST_c) — the "address" of an entry in the EDB  [line 13]"""
    COUNT.hash += 1  # one T_H
    return hashlib.sha256(_enc("H1", K_w, ST)).digest()  # SHA-256, 32 bytes


def H2(K_w: bytes, ST: bytes) -> bytes:
    """H2(K_w, ST_c) — the "mask" that hides the previous state  [line 14]

    Must be as long as ST (16 bytes) because it is XORed with ST_{c-1}.
    """
    COUNT.hash += 1  # one T_H
    return hashlib.sha256(_enc("H2", K_w, ST)).digest()[:LAMBDA_BYTES]  # cut to 16 bytes


def H3(K_prime_w: bytes, c: int, gamma: int) -> int:
    """sk_c = H3(K'_w, c) — key of the additively homomorphic encryption  [line 16, Alg.4 line 37]

    The key must be a random number in [0, n) with n = 2^γ (γ = number of bitmap bits),
    so SHAKE-256 is used: a hash with any requested output length.
    """
    COUNT.hash += 1  # one T_H
    nbytes = (gamma + 7) // 8  # bytes needed for γ bits (rounded up)
    digest = hashlib.shake_256(_enc("H3", K_prime_w, c)).digest(nbytes)  # request nbytes of output
    return int.from_bytes(digest, "little") & ((1 << gamma) - 1)  # to an integer, cut to γ bits


# ---------------------------------------------------------------------------
# Symmetric encryption with homomorphic addition  (Section II-F)
# ---------------------------------------------------------------------------

class HomAdd:
    """"Additive" encryption as in Section II-F of the paper

        Enc(sk, m) = (sk + m) mod n
        Dec(sk, c) = (c - sk) mod n
        Add(c1, c2) = (c1 + c2) mod n      -> decrypts with sk1 + sk2 to m1 + m2

    n = 2^γ, so "mod n" is a fast AND with (n - 1).
    """

    def __init__(self, gamma: int):
        self.gamma = gamma  # γ = bitmap length = maximum number of documents
        self.n = 1 << gamma  # n = 2^γ (public parameter)
        self.mask = self.n - 1  # helper for mod n (x mod 2^γ = x AND (2^γ - 1))
        self.nbytes = (gamma + 7) // 8  # bytes of one ciphertext (for size accounting)

    def enc(self, sk: int, m: int) -> int:
        COUNT.enc += 1  # one T_Enc
        return (sk + m) & self.mask  # c = (sk + m) mod n

    def dec(self, sk: int, c: int) -> int:
        return (c - sk) & self.mask  # m = (c - sk) mod n  (the AND with the mask also handles negative values)

    def add(self, c1: int, c2: int) -> int:
        COUNT.add += 1  # one T_A
        return (c1 + c2) & self.mask  # c~ = (c1 + c2) mod n

    def neg(self, m: int) -> int:
        """Negative value mod n, used to delete a document, e.g. -2^3 mod 2^4 = 8  (Fig. 1c)."""
        return (-m) & self.mask  # -m mod n


# ---------------------------------------------------------------------------
# Bitmap index  (Section II-A)
# ---------------------------------------------------------------------------

def bitmap_from_ids(ids, gamma: int) -> int:
    """Build a bitmap from document ids: document id = i  ->  bit i set (value 2^i)."""
    buf = bytearray((gamma + 7) // 8)  # empty bit buffer (all 0) of γ bits
    for i in ids:  # every id
        if not 0 <= i < gamma:  # id beyond the bitmap capacity
            raise ValueError(f"document id {i} outside the bitmap range (gamma={gamma})")  # error
        buf[i >> 3] |= 1 << (i & 7)  # set bit i (byte i//8, bit i%8)
    return int.from_bytes(buf, "little")  # bit buffer to one integer


def ids_from_bitmap(bs: int):
    """Read a bitmap back as document ids (positions of the set bits)."""
    if bs == 0:  # no bit set
        return []  # so no documents
    raw = bs.to_bytes((bs.bit_length() + 7) // 8, "little")  # integer to bytes
    out = []  # result list
    for byte_index, byte in enumerate(raw):  # one byte at a time
        if byte:  # skip all-zero bytes (much faster on sparse bitmaps)
            for bit in range(8):  # each bit of that byte
                if byte >> bit & 1:  # bit set
                    out.append(byte_index * 8 + bit)  # bit position = document id
    return out  # return the ids


def int_to_bytes(x: int, nbytes: int) -> bytes:
    """Integer to fixed-length bytes (for disk storage / size accounting)."""
    return x.to_bytes(nbytes, "little")  # little-endian, as in bitmap_from_ids


def bytes_to_int(b: bytes) -> int:
    """Bytes back to an integer."""
    return int.from_bytes(b, "little")  # little-endian


# ---------------------------------------------------------------------------
# SE — plain symmetric encryption (for CntDiffs in the users' queues)
# ---------------------------------------------------------------------------

def se_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """SE.Enc — AES-GCM encryption  (Enc_{K'_u}(w, c) in Alg.2/3 line 12)"""
    nonce = os.urandom(12)  # fresh 12-byte nonce every time (never reused)
    return nonce + AESGCM(_aes_key(key)).encrypt(nonce, plaintext, None)  # nonce sent with the ciphertext


def se_decrypt(key: bytes, blob: bytes) -> bytes:
    """SE.Dec — AES-GCM decryption  (Alg.4/5 line 3)"""
    return AESGCM(_aes_key(key)).decrypt(blob[:12], blob[12:], None)  # the first 12 bytes are the nonce


def _aes_key(key: bytes) -> bytes:
    """Stretch the key to exactly 32 bytes for AES-256 (K'_u is 16 bytes, so it is expanded with SHA-256)."""
    return hashlib.sha256(_enc("SE", key)).digest()  # 32-byte key


# ============================================================================
# 2) EDB — the CS's encrypted database (RAM or SQLite)
# ============================================================================

class MemoryEDB:
    """EDB in a Python dict"""

    def __init__(self, gamma: int):
        self.nbytes = (gamma + 7) // 8  # size of one e_c (bytes), for storage accounting
        self._d = {}  # the actual dict: key = UT, value = (e, C, vt)

    def get(self, ut: bytes):
        return self._d.get(ut)  # (e, C, vt), or None if absent

    def put(self, ut: bytes, e: int, c_st, vt: bytes):
        self._d[ut] = (e, c_st, vt)  # write / overwrite the entry at address ut

    def put_many(self, rows):
        for ut, e, c_st, vt in rows:  # every row
            self._d[ut] = (e, c_st, vt)  # one row at a time

    def delete(self, ut: bytes):
        self._d.pop(ut, None)  # delete the entry (no error if absent)

    def __len__(self):
        return len(self._d)  # number of entries

    def size_bytes(self) -> int:
        """Approximate storage = sum of the sizes of UT + e + C + vt over every entry."""
        total = 0  # counter
        for ut, (e, c_st, vt) in self._d.items():  # every entry
            total += len(ut) + self.nbytes + len(vt) + (len(c_st) if c_st else 0)  # add each part's size
        return total  # bytes

    def close(self):
        pass  # nothing to close in RAM


class SqliteEDB:
    """EDB in an SQLite file — the same data, without using RAM."""

    def __init__(self, gamma: int, path: str):
        self.nbytes = (gamma + 7) // 8  # size of e_c in bytes (always the same)
        self.conn = sqlite3.connect(path)  # open / create the database file
        self.conn.execute("PRAGMA journal_mode=OFF")  # journal off for faster writes (experiments only)
        self.conn.execute("PRAGMA synchronous=OFF")  # do not wait for the disk on every write (faster)
        self.conn.execute("DROP TABLE IF EXISTS edb")  # start fresh: drop the old table
        self.conn.execute(  # create the table: ut is the primary key
            "CREATE TABLE edb (ut BLOB PRIMARY KEY, e BLOB, cst BLOB, vt BLOB)"
        )

    def get(self, ut: bytes):
        row = self.conn.execute("SELECT e, cst, vt FROM edb WHERE ut=?", (ut,)).fetchone()  # look up by ut
        if row is None:  # not found
            return None  # None, like dict.get
        return bytes_to_int(row[0]), row[1], row[2]  # e from bytes back to an integer

    def put(self, ut: bytes, e: int, c_st, vt: bytes):
        self.conn.execute(  # INSERT OR REPLACE = overwrite if present
            "INSERT OR REPLACE INTO edb VALUES (?,?,?,?)",
            (ut, int_to_bytes(e, self.nbytes), c_st, vt),
        )

    def put_many(self, rows):
        self.conn.executemany(  # many rows in one statement (faster)
            "INSERT OR REPLACE INTO edb VALUES (?,?,?,?)",
            ((ut, int_to_bytes(e, self.nbytes), c, vt) for ut, e, c, vt in rows),
        )

    def delete(self, ut: bytes):
        self.conn.execute("DELETE FROM edb WHERE ut=?", (ut,))  # delete the row

    def __len__(self):
        return self.conn.execute("SELECT COUNT(*) FROM edb").fetchone()[0]  # count rows

    def size_bytes(self) -> int:
        q = "SELECT COALESCE(SUM(LENGTH(ut)+LENGTH(e)+LENGTH(vt)+COALESCE(LENGTH(cst),0)),0) FROM edb"  # total size
        return self.conn.execute(q).fetchone()[0]  # bytes

    def close(self):
        self.conn.close()  # close the file


# ============================================================================
# 3) Scheme — DataOwner / CloudServer / DataUser (Algorithm 1-5)
# ============================================================================

ADD = "add"  # update type: add a keyword-document pair
DEL = "del"  # update type: delete a keyword-document pair


# ---------------------------------------------------------------------------
# messages passed between DO / CS / DU
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """token_i = (K_w, ST_c, c)  [Alg.4 L12] — sent from the DU to the CS at search time"""
    K_w: bytes  # state key of the keyword (32 bytes)
    ST_c: bytes  # latest state of the keyword (16 bytes)
    c: int  # latest counter (how many times this keyword has been updated, from 0)

    def size_bytes(self) -> int:
        return len(self.K_w) + len(self.ST_c) + 8  # size on the wire (c counted as 8 bytes)


@dataclass
class UpdateMessage:
    """Message from the DO to the CS at Share/Update  [Alg.2 L20, Alg.3 L21]"""
    u: str  # the user these entries belong to
    entries: list  # list of (UT_c, e_c, C_STc, vt)
    diffs: list  # CntDiffs = list of ciphertexts Enc_{K'_u}(w, c, ST_c)
    ids: list  # ids of the documents involved (for the AccessList at Share)

    def size_bytes(self, nbytes_e: int) -> int:
        """Message size (communication overhead of an update)."""
        s = sum(len(ut) + nbytes_e + len(c) + len(vt) for ut, e, c, vt in self.entries)  # entry sizes
        return s + sum(len(d) for d in self.diffs)  # plus the CntDiffs size


# ---------------------------------------------------------------------------
# helpers to pack/unpack CntDiffs
# ---------------------------------------------------------------------------

def _pack_diff(w: str, c: int, ST_c: bytes) -> bytes:
    """Pack (w, c, ST_c) into one byte string before encryption."""
    return c.to_bytes(8, "big", signed=True) + ST_c + w.encode("utf-8")  # 8 byte c + 16 byte ST + keyword


def _unpack_diff(b: bytes):
    """Unpack bytes back to (w, c, ST_c)."""
    c = int.from_bytes(b[:8], "big", signed=True)  # the first 8 bytes are the counter
    ST_c = b[8:8 + LAMBDA_BYTES]  # the next 16 bytes are the state
    w = b[8 + LAMBDA_BYTES:].decode("utf-8")  # the rest is the keyword
    return w, c, ST_c  # all three values


# ============================================================================
# Cloud Server (CS)
# ============================================================================

class CloudServer:
    """CS: stores the EDB, AccessList and Queues, and runs the server side of Search."""

    def __init__(self, gamma: int, edb=None):
        self.he = HomAdd(gamma)  # additive encryption (the CS only uses Add)
        self.EDB = edb if edb is not None else MemoryEDB(gamma)  # encrypted database
        self.AccessList = defaultdict(set)  # AccessList[id] = users allowed to see document id
        self.Queues = defaultdict(list)  # Queues[u] = CntDiffs waiting for DU u to fetch

    # ---------------- data from the DO (Alg.2 L22-24, Alg.3 L22-23) ----------------
    def receive(self, msg: UpdateMessage, register_access: bool):
        if register_access:  # a Share (new access)
            for doc_id in msg.ids:  # every document
                self.AccessList[doc_id].add(msg.u)  # [Alg.2 L22] AccessList[id] ∪= {u}
        self.Queues[msg.u].extend(msg.diffs)  # [L23] put all CntDiffs in u's queue
        self.EDB.put_many(msg.entries)  # [L24] EDB[UT_c] <- (e_c, C_STc, vt)

    # ---------------- the DU fetches its queue (Alg.4 L1, Alg.5 L1) ----------------
    def fetch_queue(self, u: str):
        diffs = self.Queues.pop(u, [])  # take u's whole queue (and empty it)
        return diffs  # to the DU (encrypted; the CS cannot read it)

    # ---------------- server side of Search (Alg.4 L16-33) ----------------
    def search(self, tokens):
        R = []  # [L16] R <- ⊥ (empty result)
        for tok in tokens:  # [L17] every token (one token per keyword)
            Sum_e = 0  # [L18] ciphertext sum starts at 0
            proof = bytes(PROOF_BYTES)  # proof starts at all zeros (XOR with 0 keeps the value)
            ST_i = tok.ST_c  # start from the latest state
            for i in range(tok.c, -1, -1):  # [L19] for i = c down to 0 (newest to oldest)
                UT_i = H1(tok.K_w, ST_i)  # [L20] address of entry i
                entry = self.EDB.get(UT_i)  # [L21] fetch (e_i, C_ST{i-1}, vt)
                if entry is None:  # cannot happen if every party follows the protocol
                    break  # stop (the DU's verification will fail)
                e_i, C_prev, vt = entry  # unpack
                COUNT.visited += 1  # (not in the paper) count the visited entries for the report
                Sum_e = self.he.add(Sum_e, e_i)  # [L22] add the encrypted bitmaps homomorphically
                proof = xor(proof, vt)  # [L23] combine the proofs with XOR
                self.EDB.delete(UT_i)  # [L24] delete the old entry (the sum is written back later)
                if C_prev is None:  # [L25] C = ⊥ means this is the sum from an earlier search
                    break  # [L26] no need to go further
                ST_i = xor(H2(tok.K_w, ST_i), C_prev)  # [L28] unmask to get the previous state ST_{i-1}
            UT_c = H1(tok.K_w, tok.ST_c)  # address of the latest state
            self.EDB.put(UT_c, Sum_e, None, proof)  # [L30] store the sum in one place (C = ⊥): the next search is faster
            R.append((Sum_e, proof))  # [L31] add this keyword's result to R
        return R  # [L33] send R back to the DU


# ============================================================================
# Data Owner (DO)
# ============================================================================

class DataOwner:
    """DO: the data owner, fully trusted — builds the encrypted index and sends it to the CS."""

    def __init__(self, gamma: int):
        self.setup(gamma)  # Setup runs as soon as the DO is created

    # ---------------- Setup (Alg.1) ----------------
    def setup(self, gamma: int):
        self.gamma = gamma  # γ = maximum number of documents (= bitmap length)
        self.he = HomAdd(gamma)  # [Alg.1 L1] n <- Setup(1^λ) with n = 2^γ
        self.CT = defaultdict(dict)  # [L2] CT[u][w] = (ST_c, c), the state of each keyword per user
        self.UsersKeys = {}  # UsersKeys[u] = (K_u, K'_u), each user's keys
        self.AccessList = defaultdict(set)  # the DO's copy: which users document id is shared with
        self.doc_keywords = {}  # the DO knows its own data: the keywords of document id (needed for deletion)
        return self.he.n  # [L4] public parameter n (the empty EDB is already in the CS)

    # ---------------- core of Share/Update (lines 4-19) ----------------
    def _gen_entries(self, u: str, docs, op: str) -> UpdateMessage:
        """Build encrypted entries for user u from the documents docs = [(id, keywords), ...]."""
        K_u, K_prime_u = self.UsersKeys[u]  # user u's keys
        by_kw = defaultdict(list)  # group: keyword -> list of ids
        for doc_id, kws in docs:  # every document
            for w in kws:  # every keyword of the document
                by_kw[w].append(doc_id)  # record that keyword w is in document doc_id
        entries, diffs = [], []  # output
        for w, ids in by_kw.items():  # [L4] for w in W(id)
            K_w, K_prime_w = F(K_u, w)  # [L5] K_w || K'_w <- F_{K_u}(w)
            state = self.CT[u].get(w)  # [L6] (ST_c, c) <- CT[u][w]
            if state is None:  # [L7] keyword not seen yet for user u
                c, ST_prev = -1, random_bytes()  # [L8] c <- -1, a random starting ST
            else:  # seen before
                ST_prev, c = state  # the current state and counter become the "previous" ones
            ST_c = random_bytes()  # [L10] fresh random state (the core of forward privacy)
            c = c + 1  # [L10] counter + 1
            self.CT[u][w] = (ST_c, c)  # [L11] store the new state in CT
            # [FIX] the paper stores only (w, c), but the DU needs ST_c to build the token (Alg.4 L4), so ST_c is added
            diffs.append(se_encrypt(K_prime_u, _pack_diff(w, c, ST_c)))  # [L12] CntDiffs ∪= Enc_{K'_u}(w,c,ST_c)
            UT_c = H1(K_w, ST_c)  # [L13] new address (fresh every time, so the CS cannot link it to earlier ones)
            C_ST = xor(H2(K_w, ST_c), ST_prev)  # [L14] hide the previous state (only someone who knows ST_c can open it)
            bs = bitmap_from_ids(ids, self.gamma)  # [L15] build the bitmap: the bits of these documents are 1
            if op == DEL:  # [ASSUMPTION] deletion (described in Fig. 1c but not written in Alg.3)
                bs = self.he.neg(bs)  # use -bs mod n instead (Fig. 1c): after the addition those bits return to 0
            sk_c = H3(K_prime_w, c, self.gamma)  # [L16] bitmap encryption key of update c
            e_c = self.he.enc(sk_c, bs)  # [L17] e_c = (sk_c + bs) mod n
            vt = xor(F1(K_prime_u, w, c - 1), F1(K_prime_u, w, c))  # [L18] F1(w||c-1) ⊕ F1(w||c)
            for doc_id in ids:  # [L18] ... ⊕ F1(id) for every document of this update
                vt = xor(vt, F1(K_prime_u, doc_id))  # running XOR
            entries.append((UT_c, e_c, C_ST, vt))  # keep the entry for the CS
        all_ids = [doc_id for doc_id, _ in docs]  # every id in this message
        return UpdateMessage(u=u, entries=entries, diffs=diffs, ids=all_ids)  # pack the message

    # ---------------- Share (Alg.2) ----------------
    def register_user(self, u: str):
        """[Alg.2 L2-3] Create DU u's keys (once, the first time) and return them for sending to the DU."""
        if u not in self.UsersKeys:  # [FIX] the paper samples them at every Share -> sample only at the user's first Share
            self.UsersKeys[u] = (random_bytes(), random_bytes())  # [L2-3] K_u, K'_u <- {0,1}^λ
        return self.UsersKeys[u]  # [L21] send (K_u, K'_u) to DU u

    def share(self, u: str, docs, cs: CloudServer):
        """Alg.2: give user u access to the documents docs = [(id, keywords), ...].
        Used both to share existing documents with a new user and to add new documents to the system."""
        keys = self.register_user(u)  # prepare the user's keys
        todo = []  # documents that really need entries
        for doc_id, kws in docs:  # every document
            kws = set(kws)  # drop duplicate keywords within one document
            if doc_id in self.doc_keywords and self.doc_keywords[doc_id] != kws:  # same id, different keywords
                raise ValueError(f"doc {doc_id} already exists; use update() to change its keywords")  # prevents corrupted data
            if u in self.AccessList[doc_id]:  # this user already has access to this document
                continue  # skip (adding the bitmap twice would carry into other bits)
            self.AccessList[doc_id].add(u)  # [L1] AccessList[id] ∪= {u}
            self.doc_keywords[doc_id] = kws  # the DO remembers the document's keywords
            todo.append((doc_id, kws))  # entries to build
        msg = self._gen_entries(u, todo, ADD)  # [L4-19] build the encrypted entries
        cs.receive(msg, register_access=True)  # [L20, L22-24] send them to the CS
        return keys, msg  # return the keys (for the DU) and the message (for size accounting)

    # ---------------- Update (Alg.3) ----------------
    def update(self, docs, op: str, cs: CloudServer):
        """Alg.3: add (op=ADD) or delete (op=DEL) keyword-document pairs of already shared documents.

        docs = [(id, keywords), ...]   with op=DEL and keywords=None the whole document is deleted
        """
        per_user = defaultdict(list)  # each user -> the documents to update for them
        for doc_id, kws in docs:  # every document
            current = self.doc_keywords.get(doc_id, set())  # the keywords this document has now
            if op == ADD:  # addition
                kws = set(kws) - current  # add only the keywords not present yet (no double bits)
                self.doc_keywords[doc_id] = current | kws  # update the DO's records
            else:  # deletion
                kws = current if kws is None else set(kws) & current  # only keywords that are present can be deleted
                self.doc_keywords[doc_id] = current - kws  # update the DO's records
                if not self.doc_keywords[doc_id]:  # the document has no keywords left (whole document deleted)
                    del self.doc_keywords[doc_id]  # forget the document
            if not kws:  # nothing to do
                continue  # skip
            for u in self.AccessList.get(doc_id, ()):  # [Alg.3 L1-2] userList <- AccessList[id]
                per_user[u].append((doc_id, kws))  # every authorised user needs their own entries
            if op == DEL and doc_id not in self.doc_keywords:  # whole document deleted
                self.AccessList.pop(doc_id, None)  # clear the document's access list
        msgs = []  # the messages sent
        for u, udocs in per_user.items():  # [L2] for u in userList  -> cost O(N_u · m)
            msg = self._gen_entries(u, udocs, op)  # [L4-19] build the entries for user u
            cs.receive(msg, register_access=False)  # [L21-23] send them to the CS
            msgs.append(msg)  # record
        return msgs  # return the messages (for size accounting)


# ============================================================================
# Data User (DU)
# ============================================================================

class DataUser:
    """DU: an authorised user that searches and verifies results."""

    def __init__(self, u: str, keys, gamma: int):
        self.u = u  # user name / id
        self.K_u, self.K_prime_u = keys  # keys from the DO (K_u, K'_u)
        self.he = HomAdd(gamma)  # additive encryption (the DU uses Dec)
        self.gamma = gamma  # γ
        self.CT = {}  # CT[w] = (ST_c, c), the DU's copy of the states (from the queue)

    # ---------------- fetch the queue (Alg.4 L1-5, Alg.5 L1-5) ----------------
    def sync(self, cs: CloudServer):
        diffs = cs.fetch_queue(self.u)  # [L1] diffs <- fetch Queues[u] from CS
        for diff in diffs:  # [L2] for diff in diffs
            w, c, ST_c = _unpack_diff(se_decrypt(self.K_prime_u, diff))  # [L3] (w', c) <- SE.Dec(K'_u, diff)
            old = self.CT.get(w)  # the state the DU already has
            if old is None or c > old[1]:  # keep only newer states
                self.CT[w] = (ST_c, c)  # [L4] CT[u][w'] <- (ST_c, c)
        return len(diffs)  # number of diffs fetched

    # ---------------- build the Token (Alg.4 L6-15) ----------------
    def gen_token(self, q):
        tokens = []  # Token = empty set
        for w in q:  # [L6] for each w_i in q
            state = self.CT.get(w)  # [L7] (ST_c, c) <- CT[u][w_i]
            if state is None:  # [L8] keyword never seen
                return None  # [L9] return ∅ (AND with an empty set is empty)
            ST_c, c = state  # unpack
            K_w, _ = F(self.K_u, w)  # [L11] K_w || K'_w <- F_{K_u}(w) (only K_w goes to the CS)
            tokens.append(Token(K_w=K_w, ST_c=ST_c, c=c))  # [L12-13] Token ∪= {(K_w, ST_c, c)}
        return tokens  # [L15] send the Token to the CS

    # ---------------- decrypt + AND (Alg.4 L34-43) ----------------
    def decrypt(self, q, R):
        bitmaps = []  # bitmap of each keyword (kept for Verify)
        for w, (Sum_e, _proof) in zip(q, R):  # [L34] for each (Sum_e, proof) in R
            _, c = self.CT[w]  # latest counter of this keyword
            _, K_prime_w = F(self.K_u, w)  # counter key K'_w
            Sum_sk = 0  # [L35] key sum starts at 0
            for j in range(c, -1, -1):  # [L36] for j = c to 0
                sk_j = H3(K_prime_w, j, self.gamma)  # [L37] key of update j
                Sum_sk = (Sum_sk + sk_j) & self.he.mask  # [L38] add the keys mod n
            bitmaps.append(self.he.dec(Sum_sk, Sum_e))  # [L40] bs_w <- Dec(Sum_sk, Sum_e)
        Bs = bitmaps[0]  # start from the first keyword's bitmap
        for bs in bitmaps[1:]:  # [L42] Bs <- bs_w1 ∧ ... ∧ bs_wq
            Bs &= bs  # AND one by one = documents with "every" keyword
        return Bs, bitmaps  # [L43] return Bs (and the per-keyword bitmaps for verification)

    # ---------------- Verify (Alg.5 L6-17) ----------------
    def verify(self, q, bitmaps, R) -> bool:
        if len(R) != len(q) or len(bitmaps) != len(q):  # [L6] (Sum_e, proof) must be present for every w_i in q
            return False  # the CS dropped some keyword's result -> reject (zip would silently drop the extra part)
        for w, bs_w, (_Sum_e, proof) in zip(q, bitmaps, R):  # [L6] for each w_i in q
            _, c = self.CT[w]  # [L7] (ST_c, c) <- CT[u][w_i]
            proof_p = xor(F1(self.K_prime_u, w, -1), F1(self.K_prime_u, w, c))  # [L8] F1(w||-1) ⊕ F1(w||c)
            for doc_id in ids_from_bitmap(bs_w):  # [L9] for each id in bs_w
                proof_p = xor(proof_p, F1(self.K_prime_u, doc_id))  # [L10] proof' ⊕= F1(id)
            if proof_p != proof:  # [L12] mismatch  [FIX] the paper returns after the first keyword -> check every keyword
                return False  # [L15] reject (the CS returned missing / extra / forged results)
        return True  # [L13] every keyword passes -> accept

    # ---------------- one complete search ----------------
    def search(self, q, cs: CloudServer):
        """Convenience: sync -> token -> CS search -> decrypt -> verify.
        Returns (ids matching every keyword, verification result True/False)."""
        self.sync(cs)  # fetch the queue so the states are current
        tokens = self.gen_token(q)  # build the token
        if tokens is None:  # a keyword that never existed
            return [], True  # empty result (nothing to verify)
        R = cs.search(tokens)  # the CS searches and replies
        Bs, bitmaps = self.decrypt(q, R)  # decrypt and AND
        ok = self.verify(q, bitmaps, R)  # verify
        return ids_from_bitmap(Bs), ok  # document ids and the verification result




def supports(shape: str) -> bool:
    """[40] supports only AND (Alg.4 L42: Bs = bs_w1 ∧ ... ∧ bs_wq) -> only single and conjunctive."""
    return shape in ("single", "conjunctive")  # OR / nested = N/A


# ============================================================================
# 4) Workload — AMTP's shared dataset (amtp_dataset.py in the same folder)
# ============================================================================
HERE = os.path.dirname(os.path.abspath(__file__))  # this file's folder (baselines/)
SHARED_QUERIES = os.path.join(HERE, "results", "exp1_queries.json")  # shared query file for every scheme
sys.path.insert(0, HERE)                          # so amtp_dataset.py next to this file can be imported


def dataset():
    """Import amtp_dataset only when needed (demo / selftest run without the dataset)."""
    import amtp_dataset                           # shared dataset loader
    return amtp_dataset                           # return the module


FILE_LEN = {}                                     # bit position -> plaintext size of the file (for response_bytes)


def to_chen(docs, start: int = 0):
    """Convert dataset Docs -> (bit position, set(keywords)) as used by Chen's DataOwner.
    The bitmap needs numbers 0..gamma-1 instead of document ids, so the list order is the bit position,
    and FILE_LEN keeps each position's file size: [40] returns only a bitmap, not the files, so the size of
    the standard AES-GCM ciphertext of each result file follows the shared rule (wire_sizes.py)."""
    root = dataset().load()["dir"] if docs and hasattr(docs[0], "file_path") else None
    if start == 0:
        FILE_LEN.clear()
    for i, d in enumerate(docs):
        if root is not None:
            FILE_LEN[start + i] = os.path.getsize(os.path.join(root, d.file_path))
    return [(start + i, set(d.keywords)) for i, d in enumerate(docs)]  # keywords are already unique within a file


def parse_and_query(q: str):
    """Split a query string "A AND B AND C" -> ["A", "B", "C"]  (single = one keyword)."""
    return [t.strip() for t in q.split(" AND ")]  # split at AND


# ============================================================================
# 5) benchmark helpers (output format as in SE-COLLAB: <name>_ms, _ms_median, _ms_std)
# ============================================================================
class Writer:
    """Collect rows, print them (without std/median, for readability) and write the CSV on close()."""

    def __init__(self, name: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)       # create the output folder
        self.path = os.path.join(out_dir, f"chen_{name}.csv")  # output file
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
    """Aggregate runs -> columns <name>_ms (mean), <name>_ms_median, <name>_ms_std  (as in SE-COLLAB)."""
    out = {}                                      # summary
    for k in samples[0]:                          # every metric
        v = [s.get(k, 0.0) for s in samples]      # values of every run
        out[f"{prefix}{k}_ms"] = st.mean(v)       # mean
        out[f"{prefix}{k}_ms_median"] = st.median(v)  # median
        out[f"{prefix}{k}_ms_std"] = st.pstdev(v)  # standard deviation
    return out                                    # return


def popcount(x: int) -> int:
    return bin(x).count("1")                      # number of set bits = number of documents in the bitmap


def setup(docs, gamma, args, users=1, needed=None):
    """Build the standard system for the experiments: 1 DO, 1 CS, `users` DUs (each sees every document).

    Chen's index size = (distinct keywords) x (gamma bits) per user — the arXiv dataset has very many distinct
    keywords (N = 200,000 -> ~1.29 million -> ~32 GB), so there are two modes (--scope):
      full    : entries for every keyword (exactly as in the paper)
      queried : [ASSUMPTION] entries only for the keywords the experiment uses (needed), each with its bitmap
                over every document -> that keyword's search/verify time equals the full mode exactly
                (search walks only the chains of the queried keywords and touches no other entries)
      auto    : full if the size is within --max-edb-gb, else queried
    cs_storage_bytes always reports the full index size (computable directly: every entry has the same size)."""
    nbytes = (gamma + 7) // 8                     # size of one ciphertext (bytes)
    entry = 32 + nbytes + LAMBDA_BYTES + PROOF_BYTES  # 1 entry = UT + e + C_ST + vt
    distinct = len({w for _, kws in docs for w in kws})  # distinct keywords = entries per user
    full_bytes = distinct * entry * users         # full index size (bytes)
    scope = args.scope                            # the chosen mode
    if scope == "auto":                           # choose automatically
        scope = "full" if full_bytes <= args.max_edb_gb * 1e9 or needed is None else "queried"
    if scope == "queried":                        # build only the keywords used
        docs = [(i, kws & needed) for i, kws in docs if kws & needed]  # drop unused keywords (the remaining bitmaps are complete)
    used = len({w for _, kws in docs for w in kws}) * entry * users  # size actually built
    tmpdir = None                                 # temporary SQLite folder
    if args.edb == "sqlite" or (args.edb == "auto" and used > args.ram_limit_gb * 1e9):  # larger than RAM
        tmpdir = tempfile.mkdtemp(prefix="chen_edb_")  # create the temporary folder
        edb = SqliteEDB(gamma, os.path.join(tmpdir, "edb.sqlite"))  # EDB on disk
    else:                                         # otherwise in RAM
        edb = MemoryEDB(gamma)                    # EDB in a dict
    do = DataOwner(gamma)                         # Alg.1 Setup
    cs = CloudServer(gamma, edb)                  # CS with an empty EDB
    dus = []                                      # list of DUs
    t0 = time.perf_counter()                      # time the outsourcing
    for k in range(users):                        # every user
        name = f"DU{k + 1}"                       # user name
        keys = do.register_user(name)             # the DO creates the keys
        do.share(name, docs, cs)                  # Alg.2 Share of every document (batched, see [ASSUMPTION] 8)
        dus.append(DataUser(name, keys, gamma))   # the DU holds the keys
    t_out = (time.perf_counter() - t0) * 1e3      # outsourcing time (ms)
    for du in dus:                                # first sync (done once, not a per-query cost)
        du.sync(cs)                               # fetch the queue
    info = dict(index_scope=scope, gamma=gamma, keywords=distinct,  # setup information
                edb_entries=distinct * users, cs_storage_bytes=full_bytes,
                outsource_ms=t_out if scope == "full" else "",  # the outsourcing time is meaningful only in full mode
                edb_backend="sqlite" if tmpdir else "memory")
    return do, cs, dus, info, tmpdir             # return everything


def teardown(cs, tmpdir):
    """Close the EDB and delete the temporary SQLite files."""
    cs.EDB.close()                                # close the EDB
    if tmpdir:                                    # when SQLite is used
        for f in os.listdir(tmpdir):              # delete every file in the folder
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)                          # delete the folder
    gc.collect()                                  # free RAM before the next round


def print_setup(n, info):
    """Show the setup information."""
    t = f"{info['outsource_ms'] / 1e3:.1f}s" if info["outsource_ms"] != "" else "-"  # outsourcing time
    print(f" N={n}: scope={info['index_scope']} outsource={t} keywords={info['keywords']} "
          f"full EDB={info['cs_storage_bytes'] / 1e9:.2f} GB ({info['edb_backend']})")


def run_query(du, cs, q):
    """One full query: DU builds the token -> CS searches + combines proofs -> DU decrypts + ANDs -> DU verifies.
    Returns (time per phase, operations per phase, size/result information)."""
    COUNT.reset()                                 # reset the counters
    t0 = time.perf_counter()                      # start
    du.sync(cs)                                   # Alg.4 L1-5 (the queue is empty: synced at setup)
    tokens = du.gen_token(q)                      # Alg.4 L6-15
    t1 = time.perf_counter()                      # end of query generation
    c_q = COUNT.snapshot()                        # T_PRF while building the token (should be kQ)
    if tokens is None:                            # a keyword not in the index
        return ({"query_gen": (t1 - t0) * 1e3, "server_total": 0.0, "du_decrypt": 0.0,
                 "verify_total": 0.0, "end_to_end": (t1 - t0) * 1e3}, {}, dict(rQ=0, pQ=0, ids=set()))
    COUNT.reset()                                 # reset before timing the search
    R = cs.search(tokens)                         # Alg.4 L16-33
    t2 = time.perf_counter()                      # end of the server search
    c_s = COUNT.snapshot()                        # T_H / T_A / T_X on the CS
    Bs, bitmaps = du.decrypt(q, R)                # Alg.4 L34-43
    ids = ids_from_bitmap(Bs)                     # result as a list of ids
    t3 = time.perf_counter()                      # end of decryption
    COUNT.reset()                                 # reset before timing verification
    ok = du.verify(q, bitmaps, R)                 # Alg.5
    t4 = time.perf_counter()                      # end of verification
    c_v = COUNT.snapshot()                        # T_PRF / T_X during verification
    assert ok                                     # during a benchmark the result must always verify
    times = {
        "query_gen": (t1 - t0) * 1e3,             # build the token
        "server_total": (t2 - t1) * 1e3,          # everything the CS does (walk the chains + Add + XOR proof)
        "du_decrypt": (t3 - t2) * 1e3,            # the DU adds the H3 keys + Dec + AND
        "verify_total": (t4 - t3) * 1e3,          # Alg.5
        "end_to_end": (t4 - t0) * 1e3,            # all phases (network excluded)
    }
    ops = dict(prf_qgen=c_q["prf"], hash_search=c_s["hash"], add_search=c_s["add"],  # operation counts
               xor_search=c_s["xor"], visited=c_s["visited"], prf_verify=c_v["prf"], xor_verify=c_v["xor"])
    nbytes = cs.he.nbytes                         # size of one Sum_e
    info = dict(rQ=len(ids), pQ=sum(popcount(b) for b in bitmaps),  # number of results / total postings
                proof_bytes=len(R) * W.HASH,      # proof size (32-byte vt per keyword)
                token_bytes=sum(t.size_bytes() for t in tokens),  # size of the token the DU sends
                # response = (Sum_e + vt) per keyword + result files (id + standard ciphertext) as in wire_sizes.py
                response_bytes=len(R) * (nbytes + W.HASH)
                + sum(W.result_entry_bytes(W.std_ct_bytes(FILE_LEN.get(i, 0))) for i in ids),
                ids=set(ids))                     # result (compared with the ground truth, not written to the CSV)
    return times, ops, info                       # return


def measure(du, cs, q, reps, warmup):
    """Warm up first, then measure reps runs with the garbage collector off (as in SE-COLLAB).
    Note: the first search merges a keyword's entries into one, so the measured runs see the merged state
    (the chain already has length 1 at the start, since setup does a single Share, so the results are equal)."""
    for _ in range(warmup):                       # warm-up runs
        run_query(du, cs, q)                      # not recorded
    samples, ops, info = [], {}, {}               # results
    gc.disable()                                  # GC off so it cannot disturb the timing
    try:
        for _ in range(max(1, reps)):             # measured runs
            m, ops, info = run_query(du, cs, q)   # measure
            samples.append(m)                     # keep the times
    finally:
        gc.enable()                               # GC back on
    return summarize(samples), ops, info          # summary of times + ops + sizes


# ============================================================================
# 6) Experiments (AMTP Section V-B)
# ============================================================================
def suite_exp1(args):
    """AMTP Exp.1: every size N x every k_Q x the 4 query shapes (Chen supports only AND -> N/A for the others).
    By default it replays the shared results/exp1_queries.json (or the file given with --queries), like Du and
    SE-COLLAB. Only if that file does not exist are queries generated with amtp_dataset.make_queries (same seed =
    same queries) and saved as the shared file, so an existing shared file is never overwritten.
    Every supported query is checked against the ground truth of a plaintext index -> results must match exactly."""
    D = dataset()                                 # shared dataset
    path = args.queries or SHARED_QUERIES         # query file to replay (shared file by default)
    replay = None                                 # queries loaded from the file
    if os.path.exists(path):                      # replay the shared workload
        with open(path, encoding="utf-8") as f:   # open the file
            replay = json.load(f)                 # [{"N","kQ","shape","query",...}, ...]
        print(f"[queries] replay {os.path.relpath(path)} ({len(replay)} queries)")
    elif args.queries:                            # an explicit file that does not exist is an error
        raise SystemExit(f"query file not found: {path}")
    else:
        print("[queries] no shared query file -> generating with amtp_dataset.make_queries (same seed = same queries)")
    sizes = sorted({x["N"] for x in replay}) if replay else args.sizes  # sizes to run
    print(f"[exp1] Boolean search scalability  sizes={sizes}")
    w = Writer("exp1_boolean_scalability", args.out)  # output file
    exported = []                                 # queries to save
    for n in sizes:                               # every database size
        src = D.sample(n, args.domains, args.data)  # n documents (the same set for every scheme)
        docs = to_chen(src)                       # convert the format
        inv = D.inverted_index(src)               # plaintext index for the ground truth
        if replay:                                # queries from the file
            qs = [x for x in replay if x["N"] == n]
        else:                                     # generate queries
            qs = [dict(N=n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)]
            exported += [dict(q, dataset=D.DATASET_TAG, seed=args.seed, domains=args.domains) for q in qs]
        needed = {t for q in qs if supports(q["shape"]) for t in parse_and_query(q["query"])}  # keywords to search
        do, cs, dus, info, tmp = setup(docs, n, args, needed=needed)  # gamma = N  ([ASSUMPTION] 6)
        print_setup(n, info)                      # show information
        for q in qs:                              # every query
            base = dict(N=n, kQ=q["kQ"], shape=q["shape"], domain=q.get("domain", ""))  # main columns
            if not supports(q["shape"]):          # OR / nested
                w.add(**base, status="N/A")       # record as not supported
                continue                          # skip
            terms = parse_and_query(q["query"])   # the query's keywords
            res, ops, qi = measure(dus[0], cs, terms, args.reps, args.warmup)  # measure
            gt = D.ground_truth(inv, terms)       # correct answer
            assert qi.pop("ids") == gt, f"search result differs from the ground truth: {q['query']}"  # must match exactly
            w.add(**base, status="ok", index_scope=info["index_scope"],
                  keywords=info["keywords"], cs_storage_bytes=info["cs_storage_bytes"],  # full index size (computed)
                  **qi, **res, **ops)  # record
        del do, dus, docs, src, inv               # free RAM
        teardown(cs, tmp)                         # close / delete the EDB
    w.close()                                     # write the CSV
    if exported:                                  # save the generated queries
        qpath = SHARED_QUERIES                    # shared query file (outside chen/)
        D.save_queries(qpath, exported)           # write
        print(f"-> {os.path.relpath(qpath)}  (replay the identical workload in AMTP / other baselines)")


def suite_exp2(args):
    """AMTP Exp.2: proof/verification vs r_Q on the same documents as every scheme
    (results/exp2_layouts.json: clustered / dispersed / partition_spread place the same keyword in the same files).
    Chen has no partitions or Merkle trees: verification computes F1(id) for every result, so it depends only on r_Q.
    End-to-end time still differs between layouts: ids_from_bitmap scans the bitmap up to its highest set bit
    (an implementation detail, not the algorithm) -> layouts with files near the end (dispersed) decode more slowly
    than clustered, which ends at N/3."""
    D = dataset()                                 # shared dataset
    lay = D.load_exp2_layouts()                   # shared layouts
    n = lay["N"]                                  # database size (from the shared file)
    print(f"[exp2] selective proof / verification  N={n} layouts={list(lay['layouts'])}")
    docs = to_chen(D.sample(n, lay["domains"], args.data))  # n documents
    for i, words in D.exp2_markers(lay, n).items():  # plant the keyword so it has exactly r results
        docs[i][1].update(words)
    needed = {f"{v['prefix']}{r}" for v in lay["layouts"].values() for r in lay["rq"]}  # keywords to search
    do, cs, dus, info, tmp = setup(docs, n, args, needed=needed)  # build the system
    print_setup(n, info)                          # show information
    w = Writer("exp2_selective_proof", args.out)  # output file
    for r in lay["rq"]:                           # every r_Q
        for name, spec in lay["layouts"].items():  # every layout
            res, ops, qi = measure(dus[0], cs, [f"{spec['prefix']}{r}"], args.reps, args.warmup)  # measure
            qi.pop("ids")                         # no need to write the id list
            assert qi["rQ"] == r                  # must return exactly r files
            w.add(N=n, rQ=r, layout=name, proof_bytes=qi["proof_bytes"],
                  response_bytes=qi["response_bytes"], **res, **ops)  # record
    w.close()                                     # write the CSV
    teardown(cs, tmp)                             # close / delete the EDB


def run_tampered(du, cs, q, kind, ids):
    """One query round with a cheating CS; times only the DU's verification (Alg.5); returns ({verify_total}, {detected}).
    hide: the DU's result misses the documents at positions ids; inject: the result gains documents at positions ids
    that do not match the query.
    [ASSUMPTION] [40] adds ciphertexts homomorphically (Sum_e = bitmap + Sum_sk mod 2^gamma), so a cheating CS can
    add / subtract 2^id on Sum_e; the bitmap the DU decrypts then has those bits changed, simulated by flipping the
    bits after decryption (as in t_reject_missing)."""
    du.sync(cs)
    tokens = du.gen_token(q)
    R = cs.search(tokens)
    _, bitmaps = du.decrypt(q, R)
    if ids and kind == "hide":
        for doc_id in ids:
            bitmaps[0] &= ~(1 << doc_id)
    elif ids and kind == "inject":
        for doc_id in ids:
            bitmaps[0] |= 1 << doc_id
    t0 = time.perf_counter()
    ok = du.verify(q, bitmaps, R)
    t1 = time.perf_counter()
    return {"verify_total": (t1 - t0) * 1e3}, {"detected": not ok}


# ---------------- dataset-v4 suites (the advisor's plan; shared files in datasets/arxiv/data_v4/ used by every scheme)
def suite_search1(args):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl of every domain at every files-per-domain size
    (Chen supports single / AND, which are all the shapes of this file); results must equal result_size and the
    ground truth."""
    D = dataset()
    qs = D.search_single_queries()
    plan = D.search1_points(qs, args.fpd, args.fix, args.s1_kq, args.all_points)
    print(f"[search1] domains={args.s_domains} files/domain={args.fpd} queries={len(qs)} "
          f"points={sum(map(len, plan.values()))}")
    w = Writer("search_single", args.out)
    for dname in args.s_domains:
        for n in args.fpd:
            mine = [q for q in plan[n] if q["domain"] == dname]
            if not mine:
                continue
            src = D.domain_docs(dname, n, args.data)
            inv = D.inverted_index(src)
            needed = {k for q in mine for k in q["keywords"]}
            do, cs, dus, info, tmp = setup(to_chen(src), n, args, needed=needed)
            print_setup(n, info)
            for q in mine:
                res, ops, qi = measure(dus[0], cs, q["keywords"], args.reps, args.warmup)
                ids = qi.pop("ids")
                assert len(ids) == q["result_size"][str(n)] and ids == D.ground_truth(inv, q["keywords"]), \
                    f"result mismatch: {q['query_id']} n={n}"
                w.add(scheme="Chen[40]", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", index_scope=info.get("index_scope", ""), **qi, **res, **ops)
            teardown(cs, tmp)
            del do, cs, dus, src, inv
            gc.collect()
    w.close()


def suite_verify1(args):
    """Verification 1.1 (single domain): rows single_domain of verify_keywords.csv at --fix files per domain
    (reference values: Chen has no Merkle proofs and checks F1(id) for every result)."""
    D = dataset()
    rows = D.verify_keywords("single_domain", args.fix)
    print(f"[verify1] files/domain={args.fix} keywords={len(rows)}")
    w = Writer("verify_single", args.out)
    for dname in args.s_domains:
        mine = [r for r in rows if r["domain"] == dname]
        do, cs, dus, info, tmp = setup(to_chen(D.domain_docs(dname, args.fix, args.data)), args.fix, args,
                                       needed={r["keyword"] for r in mine})
        print_setup(args.fix, info)
        for r in mine:
            res, ops, qi = measure(dus[0], cs, [r["keyword"]], args.reps, args.warmup)
            qi.pop("ids")
            assert qi["rQ"] == r["result_size"], f"{r['keyword']}: {qi['rQ']} != {r['result_size']}"
            w.add(scheme="Chen[40]", domain=dname, N=args.fix, keyword=r["keyword"], target_results=r["target_results"],
                  rank=r["rank"], status="ok", **qi, **res, **ops)
        teardown(cs, tmp)
        del do, cs, dus
        gc.collect()
    w.close()


def suite_tamper(args):
    """Verification 1.2 (single domain): tamper_sets.jsonl per domain: a keyword (~2,000 results) at files_per_domain.
    The CS hides the first t documents of tamper_order (hide) or adds the first t documents of
    amtp_dataset.inject_order that do not match the query (inject); measures verification time and counts the
    detected runs.
    modify / old_version = N/A: [40] returns only the id bitmap (Sum_e, proof) and neither returns nor
    authenticates the files' ciphertexts.
    localized = 0: [40]'s proof is one XOR value per keyword, so it only passes / fails and cannot point to the
    tampered document (the full check therefore equals a normal verification)."""
    D = dataset()
    sets = [r for r in D.tamper_sets() if r["domain"] in args.s_domains]
    w = Writer("tamper_detection", args.out)
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = D.domain_docs(dname, n, args.data)
        pos_of = {d.doc_id: i for i, d in enumerate(src)}
        inj = D.inject_order(ts, args.data)
        q = [ts["query_keyword"]]
        do, cs, dus, info, tmp = setup(to_chen(src), n, args, needed=set(q))
        print_setup(n, info)
        base = dict(scheme="Chen[40]", domain=dname, N=n, keyword=q[0], rQ=ts["result_size"])

        def measure_t(kind, ids):
            for _ in range(args.warmup):
                run_tampered(dus[0], cs, q, kind, ids)
            samples, det = [], 0
            gc.disable()
            try:
                for _ in range(max(1, args.reps)):
                    m, i = run_tampered(dus[0], cs, q, kind, ids)
                    samples.append(m)
                    det += i["detected"]
            finally:
                gc.enable()
            return summarize(samples), det, len(samples)

        res, det, runs = measure_t("none", None)
        assert det == 0, "honest result failed verification"
        w.add(**base, tamper="none", tampered=0, status="ok", detected_runs=0, runs=runs, localized=0, **res)
        for kind in args.tamper_kinds:
            for t in ts["tamper_counts"]:
                if kind in ("modify", "old_version"):
                    w.add(**base, tamper=kind, tampered=t, status="N/A")
                    continue
                ids = [pos_of[i] for i in (inj if kind == "inject" else ts["tamper_order"])[:t]]
                res, det, runs = measure_t(kind, ids)
                w.add(**base, tamper=kind, tampered=t, status="ok", detected_runs=det, runs=runs, localized=0, **res)
        teardown(cs, tmp)
        del do, cs, dus, src
        gc.collect()
    w.close()


def compact(dus, cs, keywords):
    """(Not timed) Let the users search the touched keywords so the CS merges their entries into one, as [40] does;
    keeps the EDB from growing during experiments repeated many times."""
    for du in dus:                                # every user
        du.sync(cs)                               # fetch the queue
        toks = [t[0] for t in (du.gen_token([w]) for w in keywords) if t]  # one token per keyword
        cs.search(toks)                           # the CS walks and merges the entries


def suite_exp3(args):
    """AMTP Exp.3: dynamic update — insert b real documents from the insert pool, then delete the same set
    (database size stays at N).  --update-mode per-doc = Share/Update one document at a time as in the paper,
    --users = N_u (cost grows with N_u · m)."""
    D = dataset()                                 # shared dataset
    print(f"[exp3] dynamic update  sizes={args.sizes} batches={args.batches} users={args.users} "
          f"mode={args.update_mode}")
    pool = D.insert_pool(args.domains, args.data)  # new documents not in the initial set (v4: 50,000 files)
    # [40]'s update cost does not depend on existing entries (every keyword update creates a new O(1) entry per user)
    # so no initial index is built (scope=queried, needed empty) and the EDB stays in RAM at every N
    # -> every N is measured the same way (scope=auto used to build the full index at 10k / 50k but not at 100k / 200k)
    args.scope, args.edb = "queried", "memory"    # the same for every N (independent of --scope / --edb)
    needed = set()                                # no initial entries needed to measure updates
    w = Writer("exp3_dynamic_update", args.out)   # output file
    for n in args.sizes:                          # every database size
        docs = to_chen(D.sample(n, args.domains, args.data))  # n initial documents
        gamma = n + max(args.batches)             # room in the bitmap for new documents ([ASSUMPTION] 6)
        do, cs, dus, info, tmp = setup(docs, gamma, args, users=args.users, needed=needed)  # build the system
        print_setup(n, info)                      # show information
        nbytes = cs.he.nbytes                     # size of e_c
        cursor = 0                                # position in the insert pool (wraps around when exhausted)
        for b in args.batches:                    # every batch size
            ins, dele = [], []                    # time of each run
            ops_ins = ops_del = {}                # operations of the last run
            pairs_all, bytes_ins, bytes_del = [], [], []  # number of pairs / message size
            for r in range(args.warmup + args.reps):  # warm-up + measured runs
                batch = [pool[(cursor + i) % len(pool)] for i in range(b)]  # b real documents from the pool
                cursor = (cursor + b) % len(pool)  # advance the position
                new = to_chen(batch, start=n)     # bit positions n .. n+b-1 (free, since every run deletes them)
                pairs = sum(len(k) for _, k in new)  # number of keyword-document pairs
                gc.disable()                      # GC off while timing
                try:
                    COUNT.reset()                 # reset the counters
                    mb = 0                        # DO -> CS message size
                    t0 = time.perf_counter()      # ---- INSERT (Alg.2 Share for every user) ----
                    if args.update_mode == "per-doc":  # as in the paper: one document at a time
                        for d in new:
                            for du in dus:        # every authorised user -> O(N_u · m)
                                mb += do.share(du.u, [d], cs)[1].size_bytes(nbytes)
                    else:                         # batch: the same keyword becomes one entry
                        for du in dus:
                            mb += do.share(du.u, new, cs)[1].size_bytes(nbytes)
                    t_ins = (time.perf_counter() - t0) * 1e3  # insert time (ms)
                    c_ins, b_ins = COUNT.snapshot(), mb  # insert operations and size
                    COUNT.reset()                 # reset the counters
                    mb = 0                        # reset the size
                    t0 = time.perf_counter()      # ---- DELETE (Alg.3 Update, op = DEL) ----
                    if args.update_mode == "per-doc":  # one document at a time
                        for doc_id, _ in new:
                            mb += sum(m.size_bytes(nbytes) for m in do.update([(doc_id, None)], DEL, cs))
                    else:                         # batch
                        mb += sum(m.size_bytes(nbytes) for m in do.update([(i, None) for i, _ in new], DEL, cs))
                    t_del = (time.perf_counter() - t0) * 1e3  # delete time (ms)
                    c_del, b_del = COUNT.snapshot(), mb  # delete operations and size
                finally:
                    gc.enable()                   # GC back on
                compact(dus, cs, {x for _, k in new for x in k})  # merge entries (not timed)
                if r < args.warmup:               # warm-up run
                    continue                      # not recorded
                ins.append({"update": t_ins})     # keep the insert time
                dele.append({"update": t_del})    # keep the delete time
                ops_ins, ops_del = c_ins, c_del   # operations of the last run
                pairs_all.append(pairs)           # number of pairs
                bytes_ins.append(b_ins)           # insert message size
                bytes_del.append(b_del)           # delete message size
            for op, samples, ops, mbytes in (("insert", ins, ops_ins, bytes_ins),
                                             ("delete", dele, ops_del, bytes_del)):  # record both operations
                res = summarize(samples)          # update_ms / _median / _std
                mean_ms = res["update_ms"]        # mean time of the whole batch
                w.add(N=n, batch=b, op=op, users=args.users, update_mode=args.update_mode,
                      index_scope=info["index_scope"], edb_backend=info["edb_backend"],
                      pairs=st.mean(pairs_all),
                      message_bytes=st.mean(mbytes), **res,
                      per_doc_ms=mean_ms / b,     # mean time per document
                      throughput_docs_s=b / (mean_ms / 1e3),  # documents per second
                      throughput_pairs_s=st.mean(pairs_all) / (mean_ms / 1e3),  # keyword-document pairs per second
                      prf=ops["prf"], hash=ops["hash"], enc=ops["enc"], xor=ops["xor"])  # operation counts (last run)
        del do, dus, docs                         # free RAM
        teardown(cs, tmp)                         # close / delete the EDB
    w.close()                                     # write the CSV



# ============================================================================
# 7) Demo — a small example showing every step  (python3 chen_et_al_sim.py demo)
# ============================================================================

def run_demo(_args=None):
    g = 8  # 8-bit bitmap = documents with id 0-7 (small, easy to read)

    def show_bits(x: int) -> str:
        return "".join("1" if x >> i & 1 else "0" for i in range(g))  # bit of f0 on the left (as in Fig. 1)

    print("=== 1) Setup ===")  # step 1
    do = DataOwner(g)  # the DO runs Setup (n = 2^8)
    cs = CloudServer(g)  # the CS starts with an empty EDB
    print(f"n = 2^{g} = {do.he.n}")  # show the public parameter

    print("\n=== 2) Share: the DO shares 4 documents with alice ===")  # step 2
    docs = [(0, ["w1", "w2"]), (1, ["w2"]), (2, ["w1", "w2"]), (3, ["w1"])]  # example documents
    keys, msg = do.share("alice", docs, cs)  # Alg.2
    for ut, e, c_st, vt in msg.entries:  # show the entries the CS receives
        print(f"  UT={ut.hex()[:12]}..  e_c={show_bits(e)} (random, unreadable)  vt={vt.hex()[:12]}..")  # all the CS sees
    print(f"  EDB has {len(cs.EDB)} entries, alice's queue has {len(cs.Queues['alice'])} diff")  # CS state

    print("\n=== 3) Search: alice searches w1 AND w2 ===")  # step 3
    du = DataUser("alice", keys, g)  # alice gets her keys from the DO
    du.sync(cs)  # fetch the queue -> latest states of w1, w2
    q = ["w1", "w2"]  # query
    tokens = du.gen_token(q)  # build the token
    R = cs.search(tokens)  # the CS searches and combines
    Bs, bitmaps = du.decrypt(q, R)  # alice decrypts
    for w, bs in zip(q, bitmaps):  # show each keyword's bitmap
        print(f"  bs_{w} = {show_bits(bs)}  -> documents {ids_from_bitmap(bs)}")  # after decryption
    print(f"  AND    = {show_bits(Bs)}  -> result {ids_from_bitmap(Bs)}")  # AND result
    print(f"  verify = {du.verify(q, bitmaps, R)}")  # verification result

    print("\n=== 4) Update: add w1 to f1, then delete f2 entirely ===")  # step 4
    old_ut = H1(tokens[0].K_w, tokens[0].ST_c)  # the address the CS learned from the previous search
    m = do.update([(1, ["w1"])], ADD, cs)[0]  # Alg.3 add
    print(f"  new UT = {m.entries[0][0].hex()[:12]}..  (not {old_ut.hex()[:12]}.. -> forward privacy)")  # new address
    do.update([(2, None)], DEL, cs)  # Alg.3 delete a whole file
    ids, ok = du.search(q, cs)  # search again
    print(f"  w1 AND w2 -> {ids}  verify={ok}")  # should give [0, 1]

    print("\n=== 5) Cheating CS: hides one document ===")  # step 5
    du.sync(cs)  # fetch the queue (empty)
    R = cs.search(du.gen_token(["w1"]))  # the CS searches normally
    Bs, bitmaps = du.decrypt(["w1"], R)  # alice decrypts
    bitmaps[0] &= ~1  # suppose the result misses document f0
    print(f"  verify = {du.verify(['w1'], bitmaps, R)}  (must be False)")  # must be detected


# ============================================================================
# 8) Selftest — correctness tests  (python3 chen_et_al_sim.py selftest)
# ============================================================================

def run_selftest(_args=None):
    g = 64  # 64-bit bitmap, enough for the tests
    base_docs = [(0, ["cancer", "biopsy"]), (1, ["fraud", "bank"]),  # example database
                 (2, ["cancer", "fraud", "bank"]), (3, ["cancer", "bank"])]

    def make(edb=None):
        """Build a fresh system: DO + CS + DU 'alice' who sees every document."""
        do = DataOwner(g)  # Setup
        cs = CloudServer(g, edb)  # CS
        keys, _ = do.share("alice", base_docs, cs)  # share every document with alice
        return do, cs, DataUser("alice", keys, g)  # return all three parties

    def t_fig1():  # Fig. 1(c) example: deleting f3 from 1100 (mod 2^4) gives 0100
        he = HomAdd(4)  # gamma = 4
        assert ids_from_bitmap(he.add(bitmap_from_ids([2, 3], 4), he.neg(bitmap_from_ids([3], 4)))) == [2]

    def t_search():  # single and multi-keyword search
        do, cs, du = make()
        assert du.search(["cancer"], cs) == ([0, 2, 3], True)
        assert du.search(["cancer", "bank"], cs) == ([2, 3], True)
        assert du.search(["cancer", "fraud", "bank"], cs) == ([2], True)

    def t_unknown():  # missing keyword -> empty
        do, cs, du = make()
        assert du.search(["nothing"], cs) == ([], True)

    def t_updates():  # add / delete a keyword / delete a whole file
        do, cs, du = make()
        do.update([(1, ["cancer"])], ADD, cs)
        assert du.search(["cancer"], cs) == ([0, 1, 2, 3], True)
        do.update([(2, ["cancer"])], DEL, cs)
        assert du.search(["cancer"], cs) == ([0, 1, 3], True)
        do.update([(3, None)], DEL, cs)
        assert du.search(["cancer"], cs) == ([0, 1], True)
        assert du.search(["bank"], cs) == ([1, 2], True)

    def t_aggregation():  # searching again after the CS merged the entries (C = ⊥) gives the same result
        do, cs, du = make()
        first = du.search(["bank"], cs)
        n = len(cs.EDB)
        assert first == du.search(["bank"], cs) == ([1, 2, 3], True) and len(cs.EDB) == n
        do.update([(0, ["bank"])], ADD, cs)
        assert du.search(["bank"], cs) == ([0, 1, 2, 3], True)

    def t_long_chain():  # add one file at a time, 20 times (long chain)
        do, cs, du = make()
        for i in range(10, 30):
            do.share("alice", [(i, ["bank", "new"])], cs)
        assert du.search(["bank", "new"], cs) == (list(range(10, 30)), True)

    def t_reject_missing():  # the CS hides a document -> reject
        do, cs, du = make()
        du.sync(cs)
        R = cs.search(du.gen_token(["cancer"]))
        _, bms = du.decrypt(["cancer"], R)
        bms[0] &= ~(1 << 2)
        assert du.verify(["cancer"], bms, R) is False

    def t_reject_dropped():  # the CS skips an old entry while combining -> reject
        do, cs, du = make()
        do.update([(1, ["cancer"])], ADD, cs)
        du.sync(cs)
        tok = du.gen_token(["cancer"])[0]
        e_new, _, vt_new = cs.EDB.get(H1(tok.K_w, tok.ST_c))
        R = [(e_new, vt_new)]
        _, bms = du.decrypt(["cancer"], R)
        assert du.verify(["cancer"], bms, R) is False

    def t_reject_dropped_keyword():  # the CS omits one query keyword's result (drops "bank") -> reject
        do, cs, du = make()
        du.sync(cs)
        q = ["cancer", "bank"]
        R = cs.search(du.gen_token(q))[:1]  # only the result of "cancer" is left
        _, bms = du.decrypt(q, R)
        assert du.verify(q, bms, R) is False

    def t_reject_forged():  # the CS forges the proof -> reject
        do, cs, du = make()
        du.sync(cs)
        Sum_e, proof = cs.search(du.gen_token(["bank"]))[0]
        R = [(Sum_e, bytes(len(proof)))]
        _, bms = du.decrypt(["bank"], R)
        assert du.verify(["bank"], bms, R) is False

    def t_forward():  # a new update gets a new UT that an old token cannot compute
        do, cs, du = make()
        du.sync(cs)
        old = du.gen_token(["bank"])[0]
        msgs = do.update([(0, ["bank"])], ADD, cs)
        assert msgs[0].entries[0][0] != H1(old.K_w, old.ST_c)

    def t_multi_user():  # bob sees only some documents, and a deletion must disappear for everyone
        do, cs, du_a = make()
        keys_b, _ = do.share("bob", base_docs[:2], cs)
        du_b = DataUser("bob", keys_b, g)
        assert du_b.search(["cancer"], cs) == ([0], True)
        assert du_a.search(["cancer"], cs) == ([0, 2, 3], True)
        do.update([(0, None)], DEL, cs)
        assert du_b.search(["cancer"], cs) == ([], True)
        assert du_a.search(["cancer"], cs) == ([2, 3], True)

    def t_sqlite():  # the SQLite EDB must give the same results as the RAM one
        with tempfile.TemporaryDirectory() as d:
            edb = SqliteEDB(g, os.path.join(d, "edb.sqlite"))
            do, cs, du = make(edb)
            do.update([(1, ["cancer"])], ADD, cs)
            assert du.search(["cancer", "bank"], cs) == ([1, 2, 3], True)
            edb.close()

    tests = [t_fig1, t_search, t_unknown, t_updates, t_aggregation, t_long_chain,  # all tests
             t_reject_missing, t_reject_dropped, t_reject_dropped_keyword, t_reject_forged, t_forward,
             t_multi_user, t_sqlite]
    failed = 0  # count failures
    for t in tests:  # run one by one
        try:
            t()  # test
            print(f"  PASS  {t.__name__}")  # pass
        except Exception as ex:  # fail
            failed += 1  # count
            print(f"  FAIL  {t.__name__}: {ex!r}")  # show the reason
    print(f"{len(tests) - failed}/{len(tests)} passed")  # summary
    sys.exit(1 if failed else 0)  # error exit code if any test failed




# ============================================================================
# 9) main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Chen et al. [40] simulation")  # argument parser
    ap.add_argument("mode", choices=["demo", "selftest", "exp1", "exp2", "exp3", "all",
                                     "search1", "verify1", "tamper"])  # mode to run
    # ---- shared dataset (amtp_dataset.py) ----
    ap.add_argument("--data", default=None, help="dataset folder (default <repo>/data/amtp_file_db_v4 or AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="domains used")
    ap.add_argument("--seed", type=int, default=42, help="query generation seed (equals the dataset seed)")
    # ---- names and defaults shared by every baseline (du / se_collab / chen) ----
    ap.add_argument("--reps", type=int, default=30, help="number of measured runs")
    ap.add_argument("--warmup", type=int, default=3, help="number of warm-up runs (not counted)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000],
                    help="sizes N of exp1/exp3 (at most 500,000 = 4 domains x 125,000)")
    ap.add_argument("--kq", type=int, nargs="+", default=[1, 2, 4, 8, 16], help="keywords per query")
    ap.add_argument("--queries-per-kq", type=int, default=1, help="queries per k_Q (exp1)")
    # ---- Chen only ----
    ap.add_argument("--queries", default=None,
                    help=f"query JSON to replay (default {os.path.relpath(SHARED_QUERIES)})")
    ap.add_argument("--batches", type=int, nargs="+", default=[1, 10, 100, 1000], help="batch sizes of exp3")
    ap.add_argument("--users", type=int, default=1, help="number of authorised DUs N_u (exp3)")
    ap.add_argument("--update-mode", choices=["per-doc", "batch"], default="per-doc",
                    help="exp3: per-doc = as in the paper, batch = keywords merged over the batch")
    ap.add_argument("--scope", choices=["auto", "full", "queried"], default="auto",
                    help="build the full index or only the queried keywords (see setup())")
    ap.add_argument("--max-edb-gb", type=float, default=4.0, help="scope=auto: a full index larger than this -> queried")
    ap.add_argument("--edb", choices=["auto", "memory", "sqlite"], default="auto",
                    help="EDB storage (auto = SQLite above --ram-limit-gb)")
    ap.add_argument("--ram-limit-gb", type=float, default=2.0, help="RAM limit of the EDB before switching to SQLite")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "chen"), help="output folder")
    Dm = dataset()                                # defaults of the v4 suites, shared by every scheme
    ap.add_argument("--s-domains", nargs="+", default=list(Dm.DOMAINS), help="v4 single-domain suites: domain")
    ap.add_argument("--fpd", type=int, nargs="+", default=Dm.V4_SIZES, help="search1: files per domain")
    ap.add_argument("--fix", type=int, default=Dm.V4_FIX, help="verify1: files per domain")
    ap.add_argument("--s1-kq", type=int, default=Dm.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--tamper-kinds", nargs="+", default=Dm.TAMPER_KINDS, choices=Dm.TAMPER_KINDS)
    a = ap.parse_args()                           # parse arguments
    run = {"demo": run_demo, "selftest": run_selftest,  # function of each mode
           "exp1": suite_exp1, "exp2": suite_exp2, "exp3": suite_exp3, "search1": suite_search1,
           "verify1": suite_verify1, "tamper": suite_tamper}
    for name in (["exp1", "exp2", "exp3"] if a.mode == "all" else [a.mode]):  # all = run every experiment
        run[name](a)                              # run


if __name__ == "__main__":
    main()
