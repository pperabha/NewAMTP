"""
du_et_al_sim.py
===============================================================================
Simulation of the baseline Du et al. [7]
  J. Du, J. Zhou, Y. Lin, W. Zhang, J. Wei,
  "Secure and Verifiable Keyword Search in Multiple Clouds",
  IEEE Systems Journal, vol. 16, no. 2, pp. 2660-2671, 2022.

This code follows the paper's Section IV:
  A. Secure and Reliable File Distribution  (iterative encryption + RS erasure code)
  B. Secure Search                           (Bloom filter + BF tree + remapping)
  C. Integrity Verification                  (encoded file IDs with HMAC)

Measured for the comparison with AMTP (AMTP's Table IV):
  - Query Generation  : r * T_H per keyword            (build the trapdoor)
  - Search            : O(n_c * r * v_Q) * T_H         (each cloud walks its BF tree)
  - Verification      : O(n_c * |R|) * (T_H + T_HMAC)  (decode the encoded ID of every result from every cloud)
  - Update            : N/A                            (the paper does not support dynamic updates)

Points the paper leaves unclear or gets wrong, decided here (see the [ASSUMPTION]/[FIX] comments):
  1. Eq.(1) has its conditions swapped -> follow the example in the text (different index = the hash is the key)
  2. Algorithm 2 uses T.pl twice -> T.pl and T.pr
  3. Algorithm 4 adds a server to L when HM' == HM and returns V -> "not equal" and return L
  4. the HMAC length (32 bytes) differs from the ID (HMAC||fid) -> R is stretched to the ID length before XOR
  5. h(u.e, x) in remapping uses AES as a PRF (fast enough to build large trees)
  6. [ASSUMPTION] the paper's optimized Bloom filter tree (Section IV-B-5, Fig.3(b)):
     - d = the length the root needs = r(1+c)n'_root/(-ln(1-p^(1/r))) with n'_root = all distinct keywords;
       the trapdoor and every node's BF_org live in this space of size d (BF_org is stored as the list of set
       positions, because a d-bit array per leaf does not fit in RAM; u.E and M = C||BF_i in Algorithm 3 use
       this list)
     - each node is remapped (IV-B-4) into a BF of length d_u = (number of set positions)/(-ln(1-p^(1/r)))
       = r(1+c)n'_u/(-ln(1-p^(1/r))) of that node, so every node has a false-positive rate ~ p and can prune
     - the paper writes -r c n'/ln(1-p^(1/r)) (multiplying by c directly would shorten the filter, which seems
       wrong) -> r(1+c)n' is used
     - an earlier version used a basic tree with every node as long as a leaf (from z_max), which matches neither
       Fig.3(a) (a basic tree must be as long as the root) nor Fig.3(b): upper nodes were full of 1s and could
       not prune
  7. Du is a multi-cloud system without domains -> the N documents of all domains form one collection whose
     slices are spread over n_c clouds (the domain only records where a query came from)
  8. fid = position of the document in the sampled set (0..N-1) instead of the dataset's string doc_id
  9. the Bloom filter may give false positives, as in the paper -> results must cover the whole ground truth
     (missed = 0); extra files are recorded in the bloom_fp column (unlike Chen [40], whose results must match
     exactly)

Dataset and queries: the shared dataset (arXiv dataset-v4) through amtp_dataset.py, as for Chen [40]
  - documents = sample(N), the same set as every scheme; keywords W(d) from documents.csv; contents from
    files/*.txt
  - queries = replay of results/exp1_queries.json (the shared file) by default
  - results go to results/du/du_<suite>.csv in Chen's format: <metric>_ms, _ms_median, _ms_std
    over --reps runs after --warmup warm-up runs

Run (from baselines/):
  python3 du_et_al_sim.py demo                         # correctness + catching a cheating cloud (no dataset needed)
  python3 du_et_al_sim.py exp1                         # replay results/exp1_queries.json
  python3 du_et_al_sim.py exp2                                   # replays results/exp2_layouts.json (N = 200k), reference
  python3 du_et_al_sim.py clouds --n 10000 --clouds 4 8 16 32   # Du-only sensitivity (not Exp. 5)
===============================================================================
"""

# ----------------------------------------------------------------------------- imports
import argparse                                   # command-line arguments
import csv                                        # write results as CSV
import gc                                         # garbage collector off while timing / free RAM
import hashlib                                    # SHA-256 for H(.)
import hmac                                       # HMAC-SHA256 for verification
import json                                       # read the shared query file
import math                                       # log, ceil for the parameters
import re                                         # count the entries missing because of a cheating cloud
import os                                         # os.urandom for random keys
import random                                     # random secret vector / query choice
import statistics as st                           # mean / median / std of times
import sys                                        # path so amtp_dataset can be imported
import time                                       # perf_counter for timing
from dataclasses import dataclass                 # compact record type

import numpy as np                                # Bloom filter bit arrays and GF(256)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # AES-CTR / AES-ECB
from cryptography.hazmat.primitives.ciphers.aead import AESGCM                 # AES-GCM for u.E


# ============================================================================
# 0) operation counter -> checks that the numbers of T_H / T_HMAC match the formulas of Table IV
# ============================================================================
class OpCounter:                                  # holds the counters
    def __init__(self):                           # constructor
        self.reset()                              # all start at zero

    def reset(self):                              # reset before measuring each phase
        self.hash = 0                             # hash / PRF calls (T_H)
        self.hmac = 0                             # HMAC calls (T_HMAC)
        self.dec = 0                              # u.E decryptions (AES-GCM)
        self.visited = 0                          # nodes the clouds visit (v_Q over every cloud)

    def snapshot(self):                           # current counters as a dict
        return dict(hash=self.hash, hmac=self.hmac, dec=self.dec, visited=self.visited)


COUNT = OpCounter()                               # global counter for the whole file


# ============================================================================
# 1) Cryptographic primitives
# ============================================================================
def H(data: bytes) -> bytes:                      # H(.) = the paper's public hash function
    COUNT.hash += 1                               # one T_H
    return hashlib.sha256(data).digest()          # 32-byte digest


def HMAC(key: bytes, msg: bytes) -> bytes:        # HMAC(k, m) used in Algorithms 3/4
    COUNT.hmac += 1                               # one T_HMAC
    return hmac.new(key, msg, hashlib.sha256).digest()  # HMAC-SHA256, 32 bytes


def bf_hash(word: str, master_key: bytes, d: int) -> int:  # h(w, v_i) % d  (Section IV-B-2)
    COUNT.hash += 1                               # the paper counts it as a pseudorandom hash -> T_H
    digest = hmac.new(master_key, word.encode(), hashlib.sha256).digest()  # keyed PRF with the master key v_i
    return int.from_bytes(digest[:8], "big") % d  # first 64 bits mod d give the position in the bit array


def aes_ctr(key: bytes, nonce16: bytes, data: bytes) -> bytes:  # length-preserving Enc/Dec
    # [ASSUMPTION] the paper names no cipher; AES-CTR is used because the ciphertext is as long as the plaintext,
    # so every slice always has the same length, which Reed-Solomon requires
    c = Cipher(algorithms.AES(key), modes.CTR(nonce16)).encryptor()  # build AES-CTR
    return c.update(data) + c.finalize()          # CTR encrypts and decrypts with the same function


def iter_nonce(fid: int, k: int) -> bytes:        # nonce of iteration k of file fid
    # fid is included so (k_f, nonce) is never reused across files (keystream reuse)
    return hashlib.sha256(b"iter" + fid.to_bytes(8, "big") + k.to_bytes(4, "big")).digest()[:16]


def prf_positions(e: bytes, xs: np.ndarray, d: int) -> np.ndarray:  # vectorised h(u.e, x) % d
    # [ASSUMPTION] AES_{u.e}(x) as the PRF (AES is a PRP and therefore a PRF) instead of a hash,
    # because millions of bits are remapped when building the tree; batching is much faster than hashlib one by one
    xs = np.asarray(xs, dtype=np.uint64)          # set bit positions of the original BF
    blocks = np.zeros((xs.size, 2), dtype="<u8")  # 1 block AES = 16 byte = 2 x uint64
    blocks[:, 0] = xs                             # first 8 bytes = x, last 8 bytes = 0
    enc = Cipher(algorithms.AES(e), modes.ECB()).encryptor()  # AES-ECB with the node's key u.e
    out = enc.update(blocks.tobytes()) + enc.finalize()       # encrypt every block at once
    vals = np.frombuffer(out, dtype="<u8")[0::2]  # first 8 bytes of each block
    COUNT.hash += int(xs.size)                    # one T_H per position
    return (vals % np.uint64(d)).astype(np.int64) # mod d gives the new position


# ============================================================================
# 2) GF(256) + Reed-Solomon erasure code (Section IV-A-4)
#    systematic Cauchy RS: slices 0..t-1 = the data, slices t..n-1 = redundancy
#    the file can be recovered from any t slices -> (n, t) reliability as in the paper
# ============================================================================
GF_EXP = np.zeros(512, dtype=np.uint8)            # exponent table of GF(2^8)
GF_LOG = np.zeros(256, dtype=np.int32)            # logarithm table of GF(2^8)
_x = 1                                            # start at alpha^0 = 1
for _i in range(255):                             # all 255 non-zero elements
    GF_EXP[_i] = _x                               # alpha^i = _x
    GF_LOG[_x] = _i                               # log(_x) = i
    _x <<= 1                                      # multiply by alpha (= x)
    if _x & 0x100:                                # beyond 8 bits
        _x ^= 0x11D                               # reduce with the primitive polynomial x^8+x^4+x^3+x^2+1
GF_EXP[255:510] = GF_EXP[0:255]                   # repeat the table so multiplication needs no mod 255


def gf_mul(a: int, b: int) -> int:                # scalar multiplication in GF(256)
    if a == 0 or b == 0:                          # zero times anything is zero
        return 0                                  # return 0
    return int(GF_EXP[GF_LOG[a] + GF_LOG[b]])     # a*b = exp(log a + log b)


def gf_inv(a: int) -> int:                        # multiplicative inverse
    return int(GF_EXP[255 - GF_LOG[a]])           # a^-1 = alpha^(255 - log a)


def gf_mul_vec(c: int, vec: np.ndarray) -> np.ndarray:  # multiply every byte of vec by the scalar c
    out = np.zeros_like(vec)                      # zero result
    if c == 0:                                    # c = 0 gives all zeros
        return out                                # return immediately
    nz = vec != 0                                 # only the non-zero bytes
    out[nz] = GF_EXP[GF_LOG[vec[nz]] + GF_LOG[c]] # vectorised multiplication through the log/exp tables
    return out                                    # product vector


def gf_mat_inv(M):                                # inverse of a t x t matrix over GF(256)
    n = len(M)                                    # matrix size
    A = [row[:] + [1 if i == j else 0 for j in range(n)] for i, row in enumerate(M)]  # [M | I]
    for col in range(n):                          # Gauss-Jordan, column by column
        piv = next(r for r in range(col, n) if A[r][col] != 0)  # find a non-zero pivot
        A[col], A[piv] = A[piv], A[col]           # swap rows so the pivot is on the diagonal
        inv = gf_inv(A[col][col])                 # inverse of the pivot
        A[col] = [gf_mul(v, inv) for v in A[col]] # scale the pivot to 1
        for r in range(n):                        # eliminate this column from the other rows
            if r != col and A[r][col] != 0:       # skip the pivot row and rows already zero
                f = A[r][col]                     # factor to subtract
                A[r] = [a ^ gf_mul(f, b) for a, b in zip(A[r], A[col])]  # subtraction = XOR in GF(2^8)
    return [row[n:] for row in A]                 # the right half is M^-1


class ReedSolomon:                                # systematic RS erasure code
    def __init__(self, n: int, t: int):           # n = number of clouds, t = number of data slices
        assert 1 <= t <= n <= 255                 # limit of GF(256)
        self.n, self.t = n, t                     # parameters
        # Cauchy matrix: C[i][j] = 1 / (x_i XOR y_j) with x_i = t+i, y_j = j (all distinct)
        self.C = [[gf_inv((t + i) ^ j) for j in range(t)] for i in range(n - t)]
        # generator matrix G = [I_t ; C]  -> every t rows of G are invertible (MDS)
        self.G = [[1 if i == j else 0 for j in range(t)] for i in range(t)] + self.C

    def encode(self, data_slices):                # build the n-t redundant slices
        vecs = [np.frombuffer(s, dtype=np.uint8) for s in data_slices]  # slices to arrays
        parity = []                               # redundant slices
        for row in self.C:                        # each Cauchy row -> one redundant slice
            acc = np.zeros_like(vecs[0])          # accumulator
            for coef, v in zip(row, vecs):        # sum_j C[i][j] * s_j
                acc ^= gf_mul_vec(coef, v)        # addition in GF(2^8) = XOR
            parity.append(acc.tobytes())          # back to bytes
        return list(data_slices) + parity         # all n slices (C_{i,1..n})

    def decode(self, available: dict):            # available = {slice_index: bytes}, at least t slices
        idx = sorted(available)[: self.t]         # take the first t
        sub = [self.G[i] for i in idx]            # rows of G matching the available slices
        inv = gf_mat_inv(sub)                     # inverse of the submatrix
        vecs = [np.frombuffer(available[i], dtype=np.uint8) for i in idx]  # available slices
        out = []                                  # the t original data slices
        for row in inv:                           # each inverse row -> one original slice
            acc = np.zeros_like(vecs[0])          # accumulator
            for coef, v in zip(row, vecs):        # matrix multiplication over GF(256)
                acc ^= gf_mul_vec(coef, v)        # accumulate with XOR
            out.append(acc.tobytes())             # recovered slice
        return out                                # return C_{i,1..t}


# ============================================================================
# 3) Iterative encryption (Section IV-A-3, Eq.(1), Eq.(2), Eq.(4))
# ============================================================================
def secret_vector_length(t: int, T_zhang: int) -> int:  # Eq.(4): m = ceil(1 + t + (T-1) log_t t!)
    return math.ceil(1 + t + (T_zhang - 1) * math.log(math.factorial(t), t))  # cracking complexity equal to [19]


def gen_secret_vector(t: int, m: int, rng: random.Random):  # build the secret vector V (0-based)
    assert m >= t + 1                             # long enough to have V[t+1] = V[t]
    first = list(range(t))                        # the first t must be distinct -> every slice is encrypted
    rng.shuffle(first)                            # random permutation
    V = first + [first[-1]]                       # element t+1 = element t  ("tie the knot" with k_f)
    while len(V) < m:                             # fill the rest
        V.append(rng.randrange(t))                # random value in [0, t)
    return V                                      # return V of length m


def iterative_encrypt(slices, V, kf: bytes, fid: int):  # Eq.(1)
    A = list(slices)                              # array A starts as F_{i,1..t}
    for k in range(len(V) - 1):                   # m-1 iterations
        cur, nxt = V[k], V[k + 1]                 # slice to encrypt and the next slice
        # [FIX] Eq.(1) swaps its conditions; follow the example of Fig.2(a):
        #       V[k] != V[k+1] -> key = H(A[V[k+1]]),  V[k] == V[k+1] -> key = k_f
        key = hashlib.sha256(A[nxt]).digest() if cur != nxt else kf  # choose the key
        A[cur] = aes_ctr(key, iter_nonce(fid, k), A[cur])  # A[V[k]] = Enc(key, A[V[k]])
    return A                                      # gives C_{i,1..t}


def iterative_decrypt(cslices, V, kf: bytes, fid: int):  # Eq.(2) = the inverse of Eq.(1)
    B = list(cslices)                             # array B starts as C_{i,1..t}
    for k in reversed(range(len(V) - 1)):         # from the last iteration back to the first
        cur, nxt = V[k], V[k + 1]                 # the same index pair as during encryption
        # B[nxt] now has exactly its value at encryption iteration k, so the key is the same
        key = hashlib.sha256(B[nxt]).digest() if cur != nxt else kf  # the same key
        B[cur] = aes_ctr(key, iter_nonce(fid, k), B[cur])  # CTR: decrypt = encrypt again
    return B                                      # gives F_{i,1..t}


# ============================================================================
# 4) Dataset
# ============================================================================
@dataclass
class Doc:                                        # one document
    fid: int                                      # original file ID (fid_i)
    content: bytes                                # file contents (plaintext)
    keywords: set                                 # keyword set W_i


def synthetic_corpus(N, vocab_size, kw_per_doc, file_size, zipf_s=1.1, seed=1):
    """Build a synthetic corpus with Zipf keyword frequencies (skewed like real e-mail)."""
    rng = np.random.default_rng(seed)             # seeded RNG
    ranks = np.arange(1, vocab_size + 1)          # ranks 1..V
    probs = ranks ** (-zipf_s)                    # Zipf: p(rank) ∝ rank^-s
    probs /= probs.sum()                          # normalise to sum 1
    vocab = [f"kw{i:06d}" for i in range(vocab_size)]  # made-up keyword names
    docs = []                                     # all documents
    for i in range(N):                            # build N documents
        z = int(min(max(1, rng.poisson(kw_per_doc)), vocab_size))  # keywords of this document
        idx = rng.choice(vocab_size, size=z, replace=False, p=probs)  # distinct random keywords
        docs.append(Doc(i, rng.bytes(file_size), {vocab[k] for k in idx}))  # random content + keywords
    return docs                                   # return the documents


HERE = os.path.dirname(os.path.abspath(__file__))  # this file's folder (baselines/)
sys.path.insert(0, HERE)                          # so amtp_dataset.py next to this file can be imported
DEFAULT_QUERIES = os.path.join(HERE, "results", "exp1_queries.json")  # shared query file (written by Chen's script)


def dataset():
    """Import amtp_dataset only when needed (the demo runs without the dataset)."""
    import amtp_dataset                           # shared dataset loader
    return amtp_dataset                           # return the module


def to_du(src, data_dir, extra=None):
    """Convert shared-dataset Docs -> Du Docs (fid = position, contents = the real .txt file, keywords = W(d)).
    extra = {position: planted keyword} (Exp. 2: test keywords from results/exp2_layouts.json)"""
    out = []                                      # result
    for i, d in enumerate(src):                   # every document
        with open(os.path.join(data_dir, d.file_path), "rb") as f:  # open the plaintext file (title + abstract)
            content = f.read()                    # Du spreads the real file contents over every cloud
        out.append(Doc(i, content, set(d.keywords) | set((extra or {}).get(i, ()))))  # fid = i ([ASSUMPTION] 8)
    return out                                    # return the list


# ============================================================================
# 5) Bloom filter tree (Section IV-B-3, Algorithm 1, Eq.(3))
# ============================================================================
class Node:                                       # T_node = <fid, BF, pl, pr> (+ e, E from remapping)
    __slots__ = ("bf", "d", "fid", "pl", "pr", "e", "E", "slot", "_enc")  # saves memory

    def __init__(self, bf, fid=None, pl=None, pr=None):  # constructor
        self.bf = bf                              # Bloom filter of the node
        self.d = 0                                # BF length of this node (optimized tree: nodes have different lengths)
        self.fid = fid                            # file ID (leaves only; non-leaf = None)
        self.pl, self.pr = pl, pr                 # left / right child
        self.e = None                             # random value u.e for remapping
        self.E = None                             # u.E = Enc(k_f, u.BF_org)
        self.slot = None                          # file index (the cloud uses it to find its stored slice)
        self._enc = None                          # cached AES key schedule of u.e (built at the first visit)

    def is_leaf(self):                            # leaf = no children
        return self.pl is None and self.pr is None


def node_bf_length(n_set_bits: int, r: int, fp: float) -> int:
    """Section IV-B-5 (optimized tree, Fig. 3(b)): BF length of a node = r*n'/(-ln(1 - p^(1/r))).
    n' = number of elements of the node (keywords in the subtree + random insertion c|W|) and r*n' = number of
    positions set in the node's BF_org (in the space of size d, large enough for the root, positions hardly collide)
    -> length = n_set_bits / (-ln(1 - p^(1/r)))  [ASSUMPTION] 6"""
    return max(8, math.ceil(n_set_bits / -math.log(1 - fp ** (1 / r))))


# ============================================================================
# 6) Cloud server (stores slice j and the remapped BF tree, runs SecureSearch)
# ============================================================================
class CloudServer:
    def __init__(self, j: int, d: int, behavior: str = "honest"):  # j = cloud number
        self.j = j                                # cloud number (1..n in the paper, 0..n-1 in the code)
        self.d = d                                # Bloom filter length
        self.root = None                          # root of the remapped BF tree
        self.slices = {}                          # slot -> C_{i,j}
        self.leaves = []                          # all leaves (to simulate the 'irrelevant' attack)
        self.behavior = behavior                  # honest / empty / drop / tamper / forge / irrelevant

    def _h(self, enc, x: int, d: int) -> int:     # scalar h(T.e, x) % d_u during search
        blk = int(x).to_bytes(8, "little") + b"\x00" * 8  # the same block as prf_positions
        v = int.from_bytes(enc.update(blk)[:8], "little")  # first 8 bytes of AES_{e}(x)
        COUNT.hash += 1                           # one T_H
        return v % d                              # position in this node's BF (length d_u)

    def _match(self, node: Node, Q) -> bool:      # match condition: T.BF[h(T.e,x)] = 1 for every x in Q
        bits = node.bf                            # packed-bytes BF
        enc = node._enc                           # AES key schedule of T.e
        if enc is None:                           # first visit of this node (the warm-up run builds it)
            enc = node._enc = Cipher(algorithms.AES(node.e), modes.ECB()).encryptor()  # cache it in the node
        d = node.d                                # BF length of this node
        for x in Q:                               # every trapdoor position
            p = self._h(enc, x, d)                # remap the position
            if not (bits[p >> 3] >> (7 - (p & 7))) & 1:  # read bit p (big-endian packbits order)
                return False                      # a 0 bit -> no match (stop at once)
        return True                               # all bits 1 -> match

    def secure_search(self, node: Node, Q, out):  # Algorithm 2: SecureSearch (DFS)
        COUNT.visited += 1                        # count visited nodes (v_Q)
        if not self._match(node, Q):              # lines 2 / 7: match check
            return                                # no match -> prune the whole branch
        if node.is_leaf():                        # line 6: a leaf
            out.append(dict(E=node.E, enc_id=node.fid, e=node.e,  # line 8: return T.E, T.fid, T.e
                            slice=self.slices[node.slot], slot=node.slot))  # and the slice bound to the leaf
        else:                                     # internal node
            self.secure_search(node.pl, Q, out)   # line 3: left child
            self.secure_search(node.pr, Q, out)   # [FIX] line 4: the paper repeats T.pl -> must be T.pr

    def match_slots(self, node: Node, Q, out):    # the same Algorithm 2, but returns only the slots of the matching leaves
        if not self._match(node, Q):              # (no E, ID', e or file slice) to time search without fetch
            return                                # only; never used to answer real queries
        if node.is_leaf():
            out.append(node.slot)
        else:
            self.match_slots(node.pl, Q, out)
            self.match_slots(node.pr, Q, out)

    def answer(self, Q, rng: random.Random):      # answer a query (with the cheating behaviours for the verification tests)
        out = []                                  # result
        self.secure_search(self.root, Q, out)     # search as in Algorithm 2
        b = self.behavior                         # this cloud's behaviour
        if b == "empty":                          # case (1): claim there is no result
            return []                             # return empty
        if b == "drop" and out:                   # case (3): incomplete result
            out.pop(rng.randrange(len(out)))      # drop one entry (random)
        if b == "collude_drop" and out:           # all clouds collude and drop the same file
            out.remove(min(out, key=lambda it: it["slot"]))  # drop the file with the smallest slot (agreed)
        if b == "tamper" and out:                 # case (4): modify a ciphertext slice
            it = out[0]                           # the first result
            s = bytearray(it["slice"])            # copy the slice
            s[0] ^= 0xFF                          # flip the first byte
            it["slice"] = bytes(s)                # put it back
        if b == "forge" and out:                  # case (4): forge the encoded ID
            out[0]["enc_id"] = os.urandom(len(out[0]["enc_id"]))  # random ID
        if b == "irrelevant":                     # case (2): add an irrelevant file
            got = {it["slot"] for it in out}      # slots already sent
            extra = [lf for lf in self.leaves if lf.slot not in got]  # other leaves
            if extra:                             # if any
                lf = rng.choice(extra)            # pick one at random
                out.append(dict(E=lf.E, enc_id=lf.fid, e=lf.e,  # send that leaf's real data
                                slice=self.slices[lf.slot], slot=lf.slot))
        return out                                # return the result


# ============================================================================
# 7) Du et al. scheme (Data owner + Data user)
# ============================================================================
@dataclass
class VerifyResult:                               # the data user's verification result
    fids: set                                     # file IDs that passed (union over clouds)
    malicious: dict                               # cloud j -> reason it was caught
    slices: dict                                  # fid -> {j: C_{i,j}} for recovering files
    filtered_out: int = 0                         # number of results filtered out (remapping collision / irrelevant result)
    filtered_per_cloud: dict = None               # cloud j -> number filtered out


class DuScheme:
    def __init__(self, n_clouds=5, t=3, T_zhang=10, r=7, c=0.1, fp=1e-6, seed=0):
        assert n_clouds >= t                      # at least t clouds are needed to recover a file
        self.n, self.t = n_clouds, t              # n clouds, files split into t slices
        self.r, self.c, self.fp = r, c, fp        # number of master keys, random-insertion ratio, expected FP
        self.rng = random.Random(seed)            # RNG for V and choices
        self.np_rng = np.random.default_rng(seed) # numpy RNG for random insertion
        self.m = secret_vector_length(t, T_zhang) # secret vector length from Eq.(4)
        self.rs = ReedSolomon(n_clouds, t)        # RS erasure code (n, t)
        self.clouds = []                          # list of CloudServers

    # ------------------------------------------------------------------ setup (offline)
    def setup(self, docs, behaviors=None):
        """Data owner: KeyGen, file distribution, BF generation, tree build, remap, ID encoding"""
        self.kf = os.urandom(32)                  # secret key k_f (shared with the data user)
        self.master_keys = [os.urandom(32) for _ in range(self.r)]  # master keys v_1..v_r
        self.V = gen_secret_vector(self.t, self.m, self.rng)  # secret vector V
        n_root = len(set().union(*(dc.keywords for dc in docs)))  # all distinct keywords = elements of the root
        # [ASSUMPTION] 6: d = the BF length the root needs, Section IV-B-5: d = r*n'/(-ln(1 - p^(1/r)))
        #   with n' = (1+c)*n_root (random insertion counted as c|W| extra keywords)
        #   the trapdoor and BF_org use this space of size d; each node is remapped into its own BF of length d_u
        self.d = math.ceil(self.r * (1 + self.c) * n_root / -math.log(1 - self.fp ** (1 / self.r)))
        self.pos_dtype = ">u4" if self.d < 2 ** 32 else ">u8"  # BF_org stored as a list of positions (big-endian)
        self.orig_len = {}                        # real file length (to cut the padding on recovery)
        behaviors = behaviors or ["honest"] * self.n  # behaviour of each cloud
        self.clouds = [CloudServer(j, self.d, behaviors[j]) for j in range(self.n)]  # build n clouds

        # ---- (A) file distribution: segmentation -> iterative enc -> RS -> send to cloud j
        all_slices = {}                           # fid -> [C_{i,1}, ..., C_{i,n}]
        for dc in docs:                           # every file
            self.orig_len[dc.fid] = len(dc.content)  # remember the real length
            L = math.ceil(len(dc.content) / self.t)  # slice length
            padded = dc.content.ljust(L * self.t, b"\x00")  # pad to a multiple
            F = [padded[k * L:(k + 1) * L] for k in range(self.t)]  # F_{i,1..t}
            C = iterative_encrypt(F, self.V, self.kf, dc.fid)  # Eq.(1)
            all_slices[dc.fid] = self.rs.encode(C)  # add the redundant slices to get n slices
            for j in range(self.n):               # send slice j to cloud j
                self.clouds[j].slices[dc.fid] = all_slices[dc.fid][j]

        # ---- (B) Bloom filter generation (Section IV-B-2) + random insertion
        # BF_i in the space of size d (large enough for the root), stored as the sorted list of set positions instead of a bit array
        # [ASSUMPTION] 6: a d-bit array per leaf does not fit in RAM; the position list is exactly the same BF
        leaf_pos = []                             # BF_i of every file (set positions)
        for dc in docs:                           # every file
            pos = [bf_hash(w, v, self.d) for w in dc.keywords for v in self.master_keys]  # h(w, v_i) % d
            n_rand = int(self.c * len(dc.keywords) * self.r)  # c * |W_i| * r
            pos.extend(self.np_rng.integers(0, self.d, n_rand).tolist())  # random insertion (blinding)
            leaf_pos.append(np.unique(np.asarray(pos, dtype=np.int64)))  # sort + deduplicate
        fids = [dc.fid for dc in docs]            # file IDs in order

        # ---- (C)+(D) optimized Bloom filter tree (Algorithm 1 + Section IV-B-5, Fig. 3(b))
        #   with remapping (IV-B-4) and encoded IDs (Algorithm 3), per cloud, in one pass
        kfjs = [self.kf + cl.j.to_bytes(4, "big") for cl in self.clouds]  # key k_f || j of each cloud
        _, roots = self._build(leaf_pos, fids, 0, len(docs), kfjs)
        for cl, root in zip(self.clouds, roots):  # root of each cloud's remapped tree
            cl.root = root
        del leaf_pos                              # the original BF_org is no longer needed (the data owner does not keep it): free RAM
        gc.collect()                              # collect now
        COUNT.reset()                             # setup is offline, not counted in the measured phases

    def _build(self, leaf_pos, fids, lo, hi, kfjs):
        """Algorithm 1 (BFTreeBuild, top-down split) with the optimized tree of Section IV-B-5:
        a node's BF_org = OR of the BF_i in its subtree (in the space of size d = union of positions);
        each node is remapped (IV-B-4) into a BF of length d_u computed from that node's own elements.
        Returns (set positions of BF_org, [the remapped node of each cloud])."""
        if hi - lo == 1:                          # lines 2-4: one BF left -> leaf
            pos = leaf_pos[lo]                    # BF_i of this file
            return pos, [self._remap(pos, cl, kfj, fid=fids[lo]) for cl, kfj in zip(self.clouds, kfjs)]
        half = lo + (hi - lo + 1) // 2            # line 10: split so that |BF_l| - |BF_r| <= 1
        lpos, lnodes = self._build(leaf_pos, fids, lo, half, kfjs)  # line 12: left child
        rpos, rnodes = self._build(leaf_pos, fids, half, hi, kfjs)  # line 13: right child
        pos = np.union1d(lpos, rpos)              # lines 6-9: T.BF = OR of every BF in the group
        nodes = []
        for cl, kfj, ln, rn in zip(self.clouds, kfjs, lnodes, rnodes):
            node = self._remap(pos, cl, kfj)      # remap the internal node into a BF of length d_u
            node.pl, node.pr = ln, rn             # link the children
            nodes.append(node)
        return pos, nodes

    def _encode_id(self, fid: int, Cij: bytes, bf_bytes: bytes, kfj: bytes) -> bytes:
        """Algorithm 3: ID'_{i,j} = (HMAC(kf||j, fid) || fid) XOR R_{i,j}"""
        M = Cij + bf_bytes                        # line 3: M_{i,j} = C_{i,j} || BF_i
        R = self._expand(HMAC(kfj, M), 40)        # line 5: R_{i,j} = HMAC(kf||j, M)
        fid_b = fid.to_bytes(8, "big")            # fid as 8 bytes
        ID = HMAC(kfj, fid_b) + fid_b             # line 6: ID_{i,j} = HMAC(kf||j, fid) || fid
        return bytes(a ^ b for a, b in zip(ID, R))  # line 7: ID' = ID XOR R

    @staticmethod
    def _expand(r32: bytes, n: int) -> bytes:     # [ASSUMPTION] stretch R (32 bytes) to n bytes
        return (r32 + H(r32))[:n]                 # not specified in the paper; use R || H(R) and cut

    def _remap(self, xs: np.ndarray, cl: CloudServer, kfj: bytes, fid=None) -> Node:
        """Section IV-B-4: build this cloud's remapped node with u.e (and u.E, ID' at a leaf).
        xs = { a | u.BF[a] = 1 } of BF_org (space of size d); BF_temp of length d_u of this node (optimized tree)."""
        new = Node(None)                          # this cloud's new node
        new.e = os.urandom(16)                    # u.e random and different for each cloud
        new.d = node_bf_length(len(xs), self.r, self.fp)  # d_u of this node (Section IV-B-5)
        tmp = np.zeros(new.d, dtype=bool)         # BF_temp
        tmp[prf_positions(new.e, xs, new.d)] = True  # BF_temp[h(u.e, x)] = 1
        new.bf = np.packbits(tmp).tobytes()       # packed bytes (8x less memory)
        if fid is not None:                       # leaf: add E and the encoded ID
            bfb = xs.astype(self.pos_dtype).tobytes()  # BF_org of this file (position list) [ASSUMPTION] 6
            nonce = os.urandom(12)                # AES-GCM nonce
            new.E = nonce + AESGCM(self.kf).encrypt(nonce, bfb, None)  # u.E = Enc(k_f, u.BF_org)
            new.slot = fid                        # bound to the slice stored in the cloud
            new.fid = self._encode_id(fid, cl.slices[fid], bfb, kfj)  # replace fid with ID'_{i,j}
            cl.leaves.append(new)                 # remember the leaf
        # [ASSUMPTION] u.E is used only by leaves returned in Algorithm 2, so internal nodes do not get one
        return new                                # return the new node

    # ------------------------------------------------------------------ Query generation
    def trapdoor(self, keywords):                 # Section IV-B-6
        Q = set()                                 # trapdoor Q = set of positions
        for w in keywords:                        # every keyword in W_q
            for v in self.master_keys:            # r master keys -> r * T_H per keyword
                Q.add(bf_hash(w, v, self.d))      # h(w, v_i) % d
        return sorted(Q)                          # send Q to every cloud (AND semantics)

    @staticmethod
    def supports(query_type: str) -> bool:        # Du et al. supports only conjunctions (AND)
        return query_type == "AND"                # the trapdoor is a position set -> every bit must be found = AND

    # ------------------------------------------------------------------ Search
    def search(self, Q):
        """Send Q to every cloud; return each cloud's response and search time."""
        responses, times = {}, []                 # results and times
        for cl in self.clouds:                    # each cloud works independently
            t0 = time.perf_counter()              # start timing
            responses[cl.j] = cl.answer(Q, self.rng)  # Algorithm 2
            times.append(time.perf_counter() - t0)  # this cloud's time
        return responses, times                   # return both

    def search_no_fetch(self, Q):
        """Algorithm 2 on every cloud, but returning only the matching slots (no file data): each cloud's time and
        slots. Used only to time search without fetch; measured after the full query, so the existing columns are
        unaffected."""
        slots, times = {}, []
        for cl in self.clouds:
            out = []
            t0 = time.perf_counter()
            cl.match_slots(cl.root, Q, out)
            times.append(time.perf_counter() - t0)
            slots[cl.j] = out
        return slots, times

    # ------------------------------------------------------------------ Verification
    def verify(self, Q, responses) -> VerifyResult:
        """Section IV-B-7 (filtering) + Algorithm 4 + cross-cloud comparison."""
        Qarr = np.array(Q, dtype=np.int64)        # trapdoor positions as an array
        verified, per_cloud, malicious = {}, {}, {}  # fid->{j:slice}, j->set(fid), j->reason
        filtered = 0                              # number filtered out
        irr = {}                                  # cloud j -> entries that failed filtering
        for j, items in responses.items():        # every cloud j
            kfj = self.kf + j.to_bytes(4, "big")  # key k_f || j
            ok = set()                            # fids of this cloud that passed
            for it in items:                      # every result cloud j sent
                COUNT.dec += 1                    # count the u.E decryptions
                try:                              # a modified u.E makes AES-GCM fail
                    bfb = AESGCM(self.kf).decrypt(it["E"][:12], it["E"][12:], None)  # u.BF_org
                except Exception:                 # cannot decrypt
                    malicious.setdefault(j, []).append("E tampered")  # caught
                    continue                      # skip this entry
                org = np.frombuffer(bfb, self.pos_dtype)  # BF_org = sorted list of set positions
                k = np.searchsorted(org, Qarr)    # look up each x of Q in BF_org
                if not ((k < org.size) & (org[np.minimum(k, org.size - 1)] == Qarr)).all():  # filtering: some x in Q has BF_org[x] = 0
                    # case (2), an irrelevant result, and a remapping collision of an honest cloud
                    # are filtered the same way in the paper (Section IV-B-7) and cannot be told apart,
                    # so the cloud is not accused, only the entry removed; the final result stays correct
                    filtered += 1                 # count everything filtered out
                    irr[j] = irr.get(j, 0) + 1    # per cloud (recorded for inspection only)
                    continue                      # skip
                # ---- Algorithm 4 lines 4-10
                R = self._expand(HMAC(kfj, it["slice"] + bfb), 40)  # R_{i,j} = HMAC(kf||j, C||BF)
                ID = bytes(a ^ b for a, b in zip(it["enc_id"], R))  # ID = ID' XOR R
                hm_ext, fid_b = ID[:32], ID[32:]  # split HM' and fid
                if not hmac.compare_digest(hm_ext, HMAC(kfj, fid_b)):  # HM' != HMAC(kf||j, fid)
                    # [FIX] Algorithm 4 line 10 says "=" -> it must be "!=" to mean malicious
                    malicious.setdefault(j, []).append("ID/slice verification failed")
                    continue                      # reject this entry
                fid = int.from_bytes(fid_b, "big")  # original file ID
                if fid in ok:                     # sent twice
                    malicious.setdefault(j, []).append("duplicate result")
                    continue                      # skip
                ok.add(fid)                       # passed
                verified.setdefault(fid, {})[j] = it["slice"]  # keep the slice to recover the file
            per_cloud[j] = ok                     # fids of cloud j that passed

        # ---- cross-cloud comparison (assumes "at least one honest cloud")
        clouds = [j for j in responses]           # all clouds
        union = set().union(*(per_cloud[j] for j in clouds))  # union over every cloud
        for j in clouds:                          # every cloud
            missing = union - per_cloud[j]        # entries other clouds sent but j did not
            if missing:                           # cases (1)/(3): empty or incomplete
                malicious.setdefault(j, []).append(f"incomplete: missing {len(missing)}")
        return VerifyResult(union, malicious, verified, filtered, irr)  # verification result

    # ------------------------------------------------------------------ Reconstruction
    def reconstruct(self, fid: int, slices: dict) -> bytes:
        """Section IV-A-5: RS decode from any t slices, then iterative decryption."""
        if len(slices) < self.t:                  # not enough slices
            raise ValueError("fewer than t slices received")
        C = self.rs.decode(slices)                # recover C_{i,1..t}
        F = iterative_decrypt(C, self.V, self.kf, fid)  # Eq.(2)
        return b"".join(F)[: self.orig_len[fid]]  # join the slices and cut the padding

    # ------------------------------------------------------------------ Update
    def update(self, *args, **kwargs):            # Table IV: Update = N/A
        raise NotImplementedError("Du et al. [7] does not support dynamic updates (N/A in Table IV)")


# ============================================================================
# 8) Query helpers
# ============================================================================
def supports(shape: str) -> bool:
    """Du's trapdoor is a set of positions that must all be 1 = AND only -> supports single and conjunctive."""
    return shape in ("single", "conjunctive")    # OR / nested = N/A


def parse_and_query(q: str):
    """Split a query string "A AND B AND C" -> ["A", "B", "C"]  (single = one keyword)."""
    return [t.strip() for t in q.split(" AND ")]  # split at AND


def load_queries(args, D, sizes):
    """Shared queries: replayed from a file (default results/exp1_queries.json); generated with the same seed only
    if the file does not exist."""
    path = args.queries or DEFAULT_QUERIES       # query file to use
    if os.path.exists(path):                      # the shared query file exists
        with open(path, encoding="utf-8") as f:   # open the file
            rows = json.load(f)                   # [{"N","kQ","shape","query",...}, ...]
        print(f"[queries] replay {os.path.relpath(path)} ({len(rows)} queries)")
        return rows, sorted({x["N"] for x in rows})  # queries + the sizes N in the file
    if args.queries:                              # a file was given but not found
        raise SystemExit(f"query file not found: {path}")
    print("[queries] shared query file not found -> generating with amtp_dataset.make_queries (same seed = same queries)")
    rows = []                                     # generated queries
    for n in sizes:                               # every size
        src = D.sample(n, args.domains, args.data)  # n documents
        rows += [dict(N=n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)]
    return rows, sizes                            # return


# ============================================================================
# 9) Benchmark helpers (output format as in Chen [40] / SE-COLLAB: <name>_ms, _ms_median, _ms_std)
# ============================================================================
class Writer:
    """Collect rows, print them, and write results/du/du_<name>.csv on close()."""

    def __init__(self, name: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)       # create the output folder
        self.path = os.path.join(out_dir, f"du_{name}.csv")  # output file
        self.rows = []                            # collected rows

    def add(self, **row):
        self.rows.append(row)                     # keep the row
        show = {k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in row.items()
                if k in ("N", "n_clouds", "kQ", "shape", "status", "rQ", "bloom_fp",
                         "query_gen_ms", "server_total_ms", "verify_total_ms", "end_to_end_ms")}  # columns shown
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


def summarize(samples):
    """Aggregate runs -> <name>_ms (mean), <name>_ms_median, <name>_ms_std."""
    out = {}                                      # summary
    for k in samples[0]:                          # every metric
        v = [x[k] for x in samples]               # values of every run
        out[f"{k}_ms"] = st.mean(v)               # mean
        out[f"{k}_ms_median"] = st.median(v)      # median
        out[f"{k}_ms_std"] = st.pstdev(v)         # standard deviation
    return out                                    # return


def build(src, n_clouds, args, extra=None):
    """Data owner setup (offline): distribute the files + build the BF tree and remap it per cloud; returns
    (scheme, docs, info)."""
    docs = to_du(src, args.data_dir, extra)       # documents with their real contents
    sch = DuScheme(n_clouds=n_clouds, t=args.t, r=args.r, c=args.c, fp=args.fp, seed=args.seed)  # scheme
    t0 = time.perf_counter()                      # time the setup
    sch.setup(docs)                               # Section IV-A + IV-B
    t_setup = (time.perf_counter() - t0) * 1e3    # setup time (ms)
    info = dict(n_clouds=n_clouds, t=args.t, r=args.r, d_bits=sch.d, m=sch.m,  # parameters
                setup_ms=t_setup,                 # the data owner's setup time
                cs_storage_bytes=storage_bytes(sch))  # size stored by all clouds
    print(f" N={len(docs)} n_c={n_clouds}: d={sch.d} bits, m={sch.m}, setup={t_setup / 1e3:.1f}s, "
          f"cloud storage={info['cs_storage_bytes'] / 1e6:.1f} MB", flush=True)
    return sch, docs, info                        # return


def storage_bytes(sch):
    """Data stored by all clouds: every file slice + the BF tree (BF, e at every node; E, ID' at leaves)."""
    total = 0                                     # total bytes
    for cl in sch.clouds:                         # every cloud
        total += sum(len(x) for x in cl.slices.values())  # ciphertext slices
        stack = [cl.root]                         # walk the tree without recursion
        while stack:                              # every node
            u = stack.pop()                       # current node
            total += len(u.bf) + len(u.e)         # BF + e
            if u.is_leaf():                       # leaf
                total += len(u.E) + len(u.fid)    # E + encoded ID
            else:                                 # internal node
                stack += [u.pl, u.pr]             # both children
    return total                                  # return


def run_query(sch, terms):
    """One full query: DU builds the trapdoor -> every cloud searches -> DU verifies -> DU recovers the files.
    Returns (time per phase, operation counts, size/result information)."""
    COUNT.reset()                                 # reset the counters
    t0 = time.perf_counter()                      # start
    Q = sch.trapdoor(terms)                       # Section IV-B-6: r * kQ hash
    t1 = time.perf_counter()                      # end of query generation
    c_q = COUNT.snapshot()                        # T_H while building the trapdoor
    COUNT.reset()                                 # reset before timing the search
    responses, t_clouds = sch.search(Q)           # Algorithm 2 on every cloud (timed per cloud)
    c_s = COUNT.snapshot()                        # T_H and visited nodes over every cloud
    COUNT.reset()                                 # reset before timing verification
    t2 = time.perf_counter()                      # start verification
    vr = sch.verify(Q, responses)                 # filtering + Algorithm 4 + cross-cloud comparison
    t3 = time.perf_counter()                      # end of verification
    c_v = COUNT.snapshot()                        # T_HMAC / T_H / Dec during verification
    for fid in vr.fids:                           # Section IV-A-5: recover every file that passed
        sch.reconstruct(fid, vr.slices[fid])      # RS decode + iterative decrypt
    t4 = time.perf_counter()                      # end of file recovery
    assert not vr.malicious, f"honest cloud flagged as malicious: {vr.malicious}"  # every cloud is honest in the benchmark
    server_max = max(t_clouds) * 1e3              # clouds work in parallel -> latency = the slowest cloud
    times = {
        "query_gen": (t1 - t0) * 1e3,             # build the trapdoor
        "server_total": server_max,               # cloud-side search (parallel = the slowest), compared with Chen's server_total
        "server_sum": sum(t_clouds) * 1e3,        # total work of every cloud = O(n_c r v_Q) in Table IV
        "verify_total": (t3 - t2) * 1e3,          # filtering + HMAC of every result of every cloud + cross-cloud comparison
        "du_decrypt": (t4 - t3) * 1e3,            # RS decode + iterative decryption of every result file
    }
    # end_to_end = until the DU holds the verified result set (shared definition, baselines/README.md);
    # recovering the files (du_decrypt) is reported separately. No network time.
    times["end_to_end"] = times["query_gen"] + server_max + times["verify_total"]
    # search without fetch (extra columns, existing columns unchanged): the same Algorithm 2 returning only the matching slots, measured after every step above
    nf_slots, t_nf = sch.search_no_fetch(Q)
    for j, items in responses.items():            # must give the same leaves as the full query
        assert sorted(nf_slots[j]) == sorted(it["slot"] for it in items), "search_no_fetch != search"
    times["search_no_fetch"] = max(t_nf) * 1e3    # parallel = the slowest cloud (as server_total)
    times["search_no_fetch_sum"] = sum(t_nf) * 1e3
    ops = dict(hash_qgen=c_q["hash"], hash_search=c_s["hash"], visited=c_s["visited"],  # operation counts
               hmac_verify=c_v["hmac"], hash_verify=c_v["hash"], dec_verify=c_v["dec"])
    R = [len(v) for v in responses.values()]      # |R| of each cloud
    info = dict(rQ=len(vr.fids), R_per_cloud=st.mean(R),  # number of results that passed / per cloud
                filtered_out=vr.filtered_out,     # results from remapping collisions that were filtered out
                token_bytes=4 * len(Q),           # trapdoor = len(Q) positions of 4 bytes each, sent to every cloud
                # proof = the evidence the DU checks (E = Enc(BF_org), enc_id, e), file slices excluded
                proof_bytes=sum(len(it["E"]) + len(it["enc_id"]) + len(it["e"])
                                for items in responses.values() for it in items),
                response_bytes=sum(len(it["E"]) + len(it["enc_id"]) + len(it["e"]) + len(it["slice"])
                                   for items in responses.values() for it in items),  # sent back by every cloud
                ids=set(vr.fids))                 # result (compared with the ground truth, not written to the CSV)
    return times, ops, info                       # return


def measure(sch, terms, reps, warmup):
    """Warm up first, then measure reps runs with the garbage collector off (as for Chen / SE-COLLAB)."""
    for _ in range(warmup):                       # warm-up runs
        run_query(sch, terms)                     # not recorded
    samples, ops, info = [], {}, {}               # results
    gc.disable()                                  # GC off so the timing does not fluctuate
    try:
        for _ in range(max(1, reps)):             # measured runs
            m, ops, info = run_query(sch, terms)  # measure
            samples.append(m)                     # keep the times
    finally:
        gc.enable()                               # GC back on
    return summarize(samples), ops, info          # summary of times + ops + sizes


def run_queries(w, sch, docs, src, qs, n, info, args, D):
    """Measure every query of size n and write it to the Writer (shared by exp1 and clouds)."""
    inv = D.inverted_index(src)                   # plaintext index for the ground truth
    for q in qs:                                  # every query
        base = dict(N=n, n_clouds=info["n_clouds"], kQ=q["kQ"], shape=q["shape"],
                    domain=q.get("domain", ""))   # main columns
        if not supports(q["shape"]):              # OR / nested
            w.add(**base, status="N/A")           # record as not supported
            continue                              # skip
        terms = parse_and_query(q["query"])       # the query's keywords
        res, ops, qi = measure(sch, terms, args.reps, args.warmup)  # measure
        ids = qi.pop("ids")                       # actual result
        gt = D.ground_truth(inv, terms)           # correct answer
        missed = len(gt - ids)                    # files that should be returned but were not
        assert missed == 0, f"search result misses {missed} files: {q['query']}"  # a Bloom filter has no false negatives
        w.add(**base, status="ok", **qi, gt=len(gt), bloom_fp=len(ids - gt),  # record
              **res, **ops, d_bits=info["d_bits"], setup_ms=info["setup_ms"],
              cs_storage_bytes=info["cs_storage_bytes"])


# ============================================================================
# 10) Experiments (AMTP Section V-B)
# ============================================================================
def suite_exp1(args):
    """AMTP Exp.1: replay the shared queries at every size N (Du supports only AND -> N/A for the others)."""
    D = dataset()                                 # shared dataset
    args.data_dir = D.load(args.data)["dir"]      # real dataset folder (to read the .txt files)
    qs_all, sizes = load_queries(args, D, args.sizes)  # shared queries
    print(f"[exp1] Boolean search scalability  sizes={sizes} n_clouds={args.clouds[0]}")
    w = Writer("exp1_boolean_scalability", args.out)  # output file
    for n in sizes:                               # every database size
        src = D.sample(n, args.domains, args.data)  # n documents (the same set for every scheme)
        sch, docs, info = build(src, args.clouds[0], args)  # setup
        run_queries(w, sch, docs, src, [x for x in qs_all if x["N"] == n], n, info, args, D)  # measure
        del sch, docs, src                        # free RAM before the next size
        gc.collect()
    w.close()                                     # write the CSV


def suite_exp2(args):
    """AMTP Exp.2: verification vs r_Q on the same documents as every scheme (results/exp2_layouts.json), as a
    reference. Du has no Merkle tree and no proof covering several files: each result is checked with the HMAC of its
    encoded ID (Algorithm 4) and compared across clouds -> verification cost = O(n_c |R|), independent of where the
    files are (layout)."""
    D = dataset()                                 # shared dataset
    args.data_dir = D.load(args.data)["dir"]      # real dataset folder (to read the .txt files)
    lay = D.load_exp2_layouts()                   # shared layouts
    n = lay["N"]                                  # database size (from the shared file)
    print(f"[exp2] verification vs r_Q  N={n} n_clouds={args.clouds[0]} layouts={list(lay['layouts'])}")
    src = D.sample(n, lay["domains"], args.data)  # n documents (the same set for every scheme)
    sch, docs, info = build(src, args.clouds[0], args, D.exp2_markers(lay, n))  # setup + test keywords
    w = Writer("exp2_selective_proof", args.out)  # output file
    for r in lay["rq"]:                           # every r_Q
        for name, spec in lay["layouts"].items():  # every layout
            res, ops, qi = measure(sch, [f"{spec['prefix']}{r}"], args.reps, args.warmup)  # measure
            ids = qi.pop("ids")                   # result
            gt = set(spec["docs"][str(r)])        # files with the planted keyword (position = fid)
            assert not (gt - ids), f"result misses {len(gt - ids)} files"  # a Bloom filter has no false negatives
            w.add(N=n, rQ=r, layout=name, n_clouds=info["n_clouds"], gt=len(gt), bloom_fp=len(ids - gt),
                  **{k: v for k, v in qi.items() if k != "rQ"}, rQ_returned=qi["rQ"], **res, **ops)  # record
    w.close()                                     # write the CSV
    del sch, docs                                 # free RAM
    gc.collect()


def old_slice(sch, fid, content, j=0):
    """Slice of cloud j of an old version (content) of file fid that the data owner once distributed: the same steps
    as setup (A)."""
    L = math.ceil(len(content) / sch.t)
    padded = content.ljust(L * sch.t, b"\x00")
    C = iterative_encrypt([padded[k * L:(k + 1) * L] for k in range(sch.t)], sch.V, sch.kf, fid)
    return sch.rs.encode(C)[j]


def run_tampered(sch, terms, kind, fids, extra=None, gt=None):
    """One query round where cloud 0 cheats (the other clouds are honest); times only the DU's verification.
    modify = flip the first byte of a slice (the tamper behaviour), hide = drop results, inject = add the leaf of a
    file that does not match the query (irrelevant; extra = [leaf]), old_version = slices of an old version of a file
    (extra = {fid: slice}).
    Returns ({verify_total}, {detected, localized, result_ok}): detected = cloud 0 flagged as malicious;
    localized = entries of cloud 0 the DU can point to as wrong (HMAC failure, missing, or filtered out);
    result_ok = the final filtered result equals the correct answer gt (fids of the files with the keyword)."""
    Q = sch.trapdoor(terms)
    responses, _ = sch.search(Q)
    if fids or extra:
        if kind == "modify":
            for it in responses[0]:
                if it["slot"] in fids:
                    sl = bytearray(it["slice"])
                    sl[0] ^= 0xFF
                    it["slice"] = bytes(sl)
        elif kind == "hide":
            responses[0] = [it for it in responses[0] if it["slot"] not in fids]
        elif kind == "inject":
            responses[0] = responses[0] + [dict(E=lf.E, enc_id=lf.fid, e=lf.e, slice=sch.clouds[0].slices[lf.slot],
                                                slot=lf.slot) for lf in extra]
        elif kind == "old_version":
            for it in responses[0]:
                if it["slot"] in fids:
                    it["slice"] = extra[it["slot"]]
    t0 = time.perf_counter()
    vr = sch.verify(Q, responses)
    t1 = time.perf_counter()
    failed, missing = 0, 0
    for msg in vr.malicious.get(0, []):
        m = re.match(r"incomplete: missing (\d+)", msg)
        if m:
            missing = int(m.group(1))
        else:
            failed += 1                                       # entries whose HMAC / u.E fails
    # an entry whose HMAC fails is also "missing" from cloud 0 -> counted once per file; inject = entries removed by the Bloom-filter filtering
    # (an honest run can also have entries filtered because of remapping collisions, so filtered counts only for inject)
    bad = (vr.filtered_per_cloud or {}).get(0, 0) if kind == "inject" else max(failed, missing)
    injected = {lf.slot for lf in extra} if kind == "inject" and extra else set()
    # final result correct = every matching file present and no injected file (Du's own Bloom false positives are not counted as wrong)
    ok = gt is not None and gt <= set(vr.fids) and not (injected & set(vr.fids))
    return ({"verify_total": (t1 - t0) * 1e3}, {"detected": 0 in vr.malicious, "localized": bad, "result_ok": ok})


# ---------------- dataset-v4 suites (the advisor's plan; shared files in datasets/arxiv/data_v4/ used by every scheme)
def suite_search1(args):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl of every domain at every files-per-domain size
    (Du supports AND, which covers every shape of this file); no file may be missing (a Bloom filter has no false
    negatives); false positives that pass the filtering are recorded in the bloom_fp column."""
    D = dataset()
    args.data_dir = D.load(args.data)["dir"]
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
            sch, docs, info = build(src, args.clouds[0], args)
            for q in mine:
                res, ops, qi = measure(sch, q["keywords"], args.reps, args.warmup)
                ids = qi.pop("ids")
                gt = D.ground_truth(inv, q["keywords"])
                assert len(gt) == q["result_size"][str(n)] and not (gt - ids), f"missing results: {q['query_id']} n={n}"
                w.add(scheme="Du[7]", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", n_clouds=info["n_clouds"], gt=len(gt), bloom_fp=len(ids - gt),
                      **{k: v for k, v in qi.items() if k != "rQ"}, rQ=len(gt), rQ_returned=qi["rQ"], **res, **ops)
            del sch, docs, src, inv
            gc.collect()
    w.close()


def suite_verify1(args):
    """Verification 1.1 (single domain): rows single_domain of verify_keywords.csv at --fix files per domain
    (reference values: Du checks each result with an HMAC and compares across clouds)."""
    D = dataset()
    args.data_dir = D.load(args.data)["dir"]
    rows = D.verify_keywords("single_domain", args.fix)
    print(f"[verify1] files/domain={args.fix} keywords={len(rows)} n_clouds={args.clouds[0]}")
    w = Writer("verify_single", args.out)
    for dname in args.s_domains:
        src = D.domain_docs(dname, args.fix, args.data)
        inv = D.inverted_index(src)
        sch, docs, info = build(src, args.clouds[0], args)
        for r in (r for r in rows if r["domain"] == dname):
            res, ops, qi = measure(sch, [r["keyword"]], args.reps, args.warmup)
            ids = qi.pop("ids")
            gt = inv.get(r["keyword"], set())
            assert len(gt) == r["result_size"] and not (gt - ids), f"missing results: {r['keyword']}"
            w.add(scheme="Du[7]", domain=dname, N=args.fix, keyword=r["keyword"], target_results=r["target_results"],
                  rank=r["rank"], status="ok", n_clouds=info["n_clouds"], gt=len(gt), bloom_fp=len(ids - gt),
                  **{k: v for k, v in qi.items() if k != "rQ"}, rQ=len(gt), rQ_returned=qi["rQ"], **res, **ops)
        del sch, docs, src, inv
        gc.collect()
    w.close()


def suite_tamper(args):
    """Verification 1.2 (single domain): tamper_sets.jsonl per domain: a keyword (~2,000 results) at files_per_domain.
    Cloud 0 cheats on the first t documents of tamper_order (modify / hide / old_version) or adds the first t files of
    amtp_dataset.inject_order that do not match the query (inject); measures verification time, detected runs,
    localized entries and whether the final result is correct.
    Du catches hide by comparing results across clouds (needs at least one honest cloud; if every cloud drops the
    same file it is not caught, see demo 'ALL collude drop'); inject is filtered out by the Bloom filter without
    accusing the cloud (Section IV-B-7).
    Du's verification already checks every entry (no early abort), so the full check equals a normal verification."""
    D = dataset()
    args.data_dir = D.load(args.data)["dir"]
    sets = [r for r in D.tamper_sets() if r["domain"] in args.s_domains]
    w = Writer("tamper_detection", args.out)
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = D.domain_docs(dname, n, args.data)
        fid_of = {d.doc_id: i for i, d in enumerate(src)}       # fid = position in the list (to_du)
        inj = D.inject_order(ts, args.data)
        terms = [ts["query_keyword"]]
        sch, docs, info = build(src, args.clouds[0], args)
        leaf_of = {lf.slot: lf for lf in sch.clouds[0].leaves}
        base = dict(scheme="Du[7]", domain=dname, N=n, keyword=terms[0], rQ=ts["result_size"],
                    n_clouds=info["n_clouds"], cheating_clouds=1)

        gt = {fid_of[d.doc_id] for d in src if terms[0] in d.keywords}

        def measure_t(kind, fids, extra=None):
            for _ in range(args.warmup):
                run_tampered(sch, terms, kind, fids, extra, gt)
            samples, infos = [], []
            gc.disable()
            try:
                for _ in range(max(1, args.reps)):
                    m, i = run_tampered(sch, terms, kind, fids, extra, gt)
                    samples.append(m)
                    infos.append(i)
            finally:
                gc.enable()
            return summarize(samples), infos

        def row(kind, t, res, infos):
            w.add(**base, tamper=kind, tampered=t, status="ok", detected_runs=sum(i["detected"] for i in infos),
                  runs=len(infos), localized=infos[-1]["localized"],
                  result_ok_runs=sum(i["result_ok"] for i in infos), **res)

        res, infos = measure_t("none", None)
        assert not any(i["detected"] for i in infos), "honest cloud flagged as malicious"
        row("none", 0, res, infos)
        for kind in args.tamper_kinds:
            for t in ts["tamper_counts"]:
                if kind == "inject":
                    res, infos = measure_t(kind, set(), [leaf_of[fid_of[i]] for i in inj[:t]])
                else:
                    fids = {fid_of[i] for i in ts["tamper_order"][:t]}
                    extra = ({f: old_slice(sch, f, docs[f].content + D.OLD_VERSION_SUFFIX) for f in fids}
                             if kind == "old_version" else None)
                    res, infos = measure_t(kind, fids, extra)
                row(kind, t, res, infos)
        del sch, docs, src
        gc.collect()
    w.close()


def suite_clouds(args):
    """Du-only sensitivity (not AMTP Exp.5, which varies domains: Du has a single data owner and no domains):
    varies the number of clouds n_c at a fixed N (AND queries from the shared file at that N, or generated with the
    same seed)."""
    D = dataset()                                 # shared dataset
    args.data_dir = D.load(args.data)["dir"]      # dataset folder
    src = D.sample(args.n, args.domains, args.data)  # N documents
    qs, _ = load_queries(args, D, [args.n])       # shared queries
    qs = [x for x in qs if x["N"] == args.n and x["kQ"] in args.kq and supports(x["shape"])]
    if not qs:                                    # the shared file has no queries for this N -> generate with the same seed
        qs = [dict(N=args.n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)
              if supports(q["shape"])]
    print(f"[clouds] multi-cloud sensitivity  N={args.n} clouds={args.clouds} queries={len(qs)}")
    w = Writer("clouds_sensitivity", args.out)           # output file
    for n_c in args.clouds:                       # every number of clouds
        if n_c < args.t:                          # RS needs at least t clouds
            print(f"  skip n_c={n_c} < t={args.t}")
            continue
        sch, docs, info = build(src, n_c, args)   # setup
        run_queries(w, sch, docs, src, qs, args.n, info, args, D)  # measure
        del sch, docs                             # free RAM
        gc.collect()
    w.close()                                     # write the CSV


def demo(_args=None):
    """Correctness tests on a synthetic corpus (no dataset needed): search, file recovery, catching cheating clouds."""
    docs = synthetic_corpus(300, 400, 12, 2048, seed=3)  # small corpus
    src = max(docs, key=lambda x: len(x.keywords))  # source document of the query
    kws = sorted(src.keywords)[:2]                # two keywords of one document -> the AND has at least one result
    gt = {dc.fid for dc in docs if set(kws) <= dc.keywords}  # correct answer
    print(f"query={kws}  ground truth={len(gt)} files")  # show the query
    scenarios = {                                 # test scenarios (n=5, t=3)
        "all honest": ["honest"] * 5,
        "cloud1 empty": ["honest", "empty", "honest", "honest", "honest"],
        "cloud2 drop": ["honest", "honest", "drop", "honest", "honest"],
        "cloud3 tamper": ["honest", "honest", "honest", "tamper", "honest"],
        "cloud4 forge": ["honest", "honest", "honest", "honest", "forge"],
        "cloud0 irrelevant": ["irrelevant", "honest", "honest", "honest", "honest"],
        "ALL collude drop": ["collude_drop"] * 5,  # Du's limitation: every cloud drops the same file -> not detected
    }
    for name, beh in scenarios.items():           # one scenario at a time
        sch = DuScheme(n_clouds=5, t=3, seed=11)  # fresh scheme
        sch.setup(docs, behaviors=beh)            # setup with the behaviours
        Q = sch.trapdoor(kws)                     # trapdoor
        resp, _ = sch.search(Q)                   # search
        vr = sch.verify(Q, resp)                  # verify
        ok_files = sum(sch.reconstruct(fid, vr.slices[fid]) == docs[fid].content  # recovered exactly
                       for fid in vr.fids if len(vr.slices[fid]) >= sch.t)
        print(f"{name:22s} verified={len(vr.fids):3d} (gt={len(gt)}, fp={len(vr.fids - gt)}) "
              f"reconstructed_ok={ok_files:3d} filtered={vr.filtered_per_cloud} malicious={vr.malicious}")


# ============================================================================
# 11) main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Du et al. [7] simulation")  # argument parser
    ap.add_argument("mode", choices=["demo", "exp1", "exp2", "clouds", "search1", "verify1", "tamper"])  # mode to run
    # ---- shared dataset (amtp_dataset.py), same names as Chen ----
    ap.add_argument("--data", default=None, help="dataset folder (default <repo>/data/amtp_file_db_v4 or AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="domains used")
    ap.add_argument("--seed", type=int, default=42, help="query generation seed (equals the dataset seed)")
    ap.add_argument("--queries", default=None,
                    help=f"query JSON file to replay (default {os.path.relpath(DEFAULT_QUERIES)})")
    # ---- names and defaults as in Chen / SE-COLLAB ----
    ap.add_argument("--reps", type=int, default=30, help="number of measured runs")
    ap.add_argument("--warmup", type=int, default=3, help="number of warm-up runs (not counted)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000],
                    help="sizes N of exp1 when there is no shared query file (at most 500,000 = 4 domains x 125,000)")
    ap.add_argument("--kq", type=int, nargs="+", default=[1, 2, 4, 8, 16], help="keywords per query")
    ap.add_argument("--queries-per-kq", type=int, default=1, help="queries per k_Q")
    ap.add_argument("--n", type=int, default=10_000, help="database size of clouds")
    # ---- Du only ----
    ap.add_argument("--clouds", type=int, nargs="+", default=[5],
                    help="number of clouds n_c (exp1 uses the first value, clouds runs every value, e.g. 4 8 16 32)")
    ap.add_argument("--t", type=int, default=3, help="number of data slices (a file is recoverable from t clouds)")
    ap.add_argument("--r", type=int, default=7, help="number of Bloom filter master keys")
    ap.add_argument("--c", type=float, default=0.1, help="random-insertion ratio")
    ap.add_argument("--fp", type=float, default=1e-6, help="acceptable Bloom filter false-positive rate")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "du"), help="output folder")
    Dm = dataset()                                # defaults of the v4 suites, shared by every scheme
    ap.add_argument("--s-domains", nargs="+", default=list(Dm.DOMAINS), help="v4 single-domain suites: domain")
    ap.add_argument("--fpd", type=int, nargs="+", default=Dm.V4_SIZES, help="search1: files per domain")
    ap.add_argument("--fix", type=int, default=Dm.V4_FIX, help="verify1: files per domain")
    ap.add_argument("--s1-kq", type=int, default=Dm.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--tamper-kinds", nargs="+", default=Dm.TAMPER_KINDS, choices=Dm.TAMPER_KINDS)
    a = ap.parse_args()                           # parse arguments
    {"demo": demo, "exp1": suite_exp1, "exp2": suite_exp2, "clouds": suite_clouds, "search1": suite_search1,
     "verify1": suite_verify1, "tamper": suite_tamper}[a.mode](a)  # run


if __name__ == "__main__":
    main()
