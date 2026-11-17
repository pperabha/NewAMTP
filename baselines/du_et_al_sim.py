"""
du_et_al_sim.py
===============================================================================
Simulation ของ baseline Du et al. [7]
  J. Du, J. Zhou, Y. Lin, W. Zhang, J. Wei,
  "Secure and Verifiable Keyword Search in Multiple Clouds",
  IEEE Systems Journal, vol. 16, no. 2, pp. 2660-2671, 2022.

โค้ดนี้จำลองตามที่ paper อธิบายไว้ใน Section IV:
  A. Secure and Reliable File Distribution  (iterative encryption + RS erasure code)
  B. Secure Search                           (Bloom filter + BF tree + remapping)
  C. Integrity Verification                  (encoded file ID ด้วย HMAC)

สิ่งที่วัดเพื่อเทียบกับ AMTP ตาม Table IV ของ AMTP:
  - Query Generation  : r * T_H ต่อ keyword          (สร้าง trapdoor)
  - Search            : O(n_c * r * v_Q) * T_H         (แต่ละ cloud เดิน BF tree)
  - Verification      : O(n_c * |R|) * (T_H + T_HMAC)  (ถอด encoded ID ทุกผลลัพธ์ทุก cloud)
  - Update            : N/A                            (paper ไม่รองรับ dynamic update)

จุดที่ paper เขียนไม่ชัด/มีบั๊ก และโค้ดนี้ตัดสินใจเอง (ดูคอมเมนต์ [ASSUMPTION]/[FIX]):
  1. Eq.(1) เงื่อนไขพิมพ์สลับกัน -> ใช้ตามตัวอย่างในข้อความ (index ต่างกัน = ใช้ hash เป็นคีย์)
  2. Algorithm 2 เรียก T.pl ซ้ำสองครั้ง -> แก้เป็น T.pl กับ T.pr
  3. Algorithm 4 เพิ่ม server เข้า L เมื่อ HM' == HM และ return V -> แก้เป็น "ไม่เท่ากัน" และ return L
  4. ความยาว HMAC (32 byte) ไม่เท่ากับ ID (HMAC||fid) -> ขยาย R ให้ยาวเท่า ID ก่อน XOR
  5. h(u.e, x) ใน remapping ใช้ AES เป็น PRF (เร็วพอสำหรับ build tree ขนาดใหญ่)
  6. [ASSUMPTION] ใช้ Bloom filter tree แบบ optimized ของ paper (Section IV-B-5, Fig.3(b)):
     - d = ความยาวที่ root ต้องใช้ = r(1+c)n'_root/(-ln(1-p^(1/r))) โดย n'_root = keyword ไม่ซ้ำทั้งหมด
       trapdoor และ BF_org ทุก node อยู่ใน space ขนาด d นี้ (BF_org เก็บเป็นรายการตำแหน่งที่เป็น 1
       เพราะ bit array ยาว d ต่อ leaf ใช้ RAM ไม่ไหว; u.E และ M = C||BF_i ใน Algorithm 3 ใช้รายการนี้)
     - แต่ละ node ถูก remap (IV-B-4) ลงใน BF ยาว d_u = (จำนวนตำแหน่งที่เป็น 1)/(-ln(1-p^(1/r)))
       = r(1+c)n'_u/(-ln(1-p^(1/r))) ของ node นั้นเอง ทุก node จึงมี false positive ~ p และตัดกิ่งได้
     - paper เขียนสูตรเป็น -r c n'/ln(1-p^(1/r)) (คูณ c ตรง ๆ จะทำให้ filter สั้นลง ไม่น่าใช่) -> ใช้ r(1+c)n'
     - ก่อนหน้านี้โค้ดใช้ basic tree ที่ทุก node ยาวเท่า leaf (คำนวณจาก z_max) ซึ่งไม่ตรงทั้ง Fig.3(a)
       (basic tree ต้องยาวเท่า root) และ Fig.3(b): node ระดับบนเต็มไปด้วย 1 จึงตัดกิ่งไม่ได้
  7. Du เป็นระบบ multi-cloud ไม่มีแนวคิด domain -> เอกสาร N ไฟล์ของทุก domain รวมเป็นชุดเดียว
     แล้วกระจาย slice ไป n_c cloud (domain ใช้แค่บันทึกว่า query มาจาก domain ไหน)
  8. fid = ลำดับของเอกสารในชุดที่ sample มา (0..N-1) แทน doc_id แบบ string ของ dataset
  9. Bloom filter มี false positive ได้ตาม paper -> ผลต้องครอบคลุม ground truth ทั้งหมด (missed = 0)
     ส่วนไฟล์เกินบันทึกไว้ในคอลัมน์ bloom_fp (ต่างจาก Chen [40] ที่ผลต้องตรงเป๊ะ)

Dataset และ query: ใช้ dataset กลาง (arXiv dataset-v4) ผ่าน amtp_dataset.py เหมือน Chen [40]
  - เอกสาร = sample(N) ชุดเดียวกับทุก scheme, keyword W(d) จาก documents.csv, เนื้อหาไฟล์จาก files/*.txt
  - query = replay results/exp1_queries.json (ไฟล์กลาง) โดยค่าเริ่มต้น
  - ผลเขียนลง results/du/du_<suite>.csv รูปแบบเดียวกับ Chen: <metric>_ms, _ms_median, _ms_std
    จาก --reps รอบ หลัง warm-up --warmup รอบ

วิธีรัน (จากโฟลเดอร์ baselines/):
  python3 du_et_al_sim.py demo                         # ความถูกต้อง + จับ cloud ที่โกง (ไม่ต้องมี dataset)
  python3 du_et_al_sim.py exp1                         # replay results/exp1_queries.json
  python3 du_et_al_sim.py exp2                                   # replays results/exp2_layouts.json (N = 200k), reference
  python3 du_et_al_sim.py clouds --n 10000 --clouds 4 8 16 32   # Du-only sensitivity (not Exp. 5)
===============================================================================
"""

# ----------------------------------------------------------------------------- imports
import argparse                                   # อ่าน argument จาก command line
import csv                                        # เขียนผลการทดลองเป็นไฟล์ CSV
import gc                                         # ปิด garbage collector ระหว่างจับเวลา / คืน RAM
import hashlib                                    # SHA-256 สำหรับ H(.)
import hmac                                       # HMAC-SHA256 สำหรับ verification
import json                                       # อ่านไฟล์ query กลาง
import math                                       # log, ceil สำหรับคำนวณพารามิเตอร์
import re                                         # อ่านจำนวนรายการที่ขาดจากเหตุผลของ cloud ที่โกง
import os                                         # os.urandom สร้างคีย์สุ่ม
import random                                     # สุ่ม secret vector / เลือก query
import statistics as st                           # mean / median / std ของเวลา
import sys                                        # เพิ่ม path ให้ import amtp_dataset ได้
import time                                       # perf_counter จับเวลา
from dataclasses import dataclass                 # โครงสร้างข้อมูลแบบสั้น

import numpy as np                                # จัดการ bit array ของ Bloom filter และ GF(256)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # AES-CTR / AES-ECB
from cryptography.hazmat.primitives.ciphers.aead import AESGCM                 # AES-GCM สำหรับ u.E


# ============================================================================
# 0) ตัวนับจำนวน operation  -> ใช้เช็กว่าจำนวน T_H / T_HMAC ตรงกับสูตรใน Table IV
# ============================================================================
class OpCounter:                                  # คลาสเก็บตัวนับ
    def __init__(self):                           # constructor
        self.reset()                              # เริ่มต้นที่ศูนย์ทั้งหมด

    def reset(self):                              # ล้างตัวนับก่อนวัดแต่ละ phase
        self.hash = 0                             # จำนวนครั้งที่เรียก hash / PRF (T_H)
        self.hmac = 0                             # จำนวนครั้งที่เรียก HMAC (T_HMAC)
        self.dec = 0                              # จำนวนครั้งที่ถอดรหัส u.E (AES-GCM)
        self.visited = 0                          # จำนวน node ที่ cloud เดินผ่าน (v_Q รวมทุก cloud)

    def snapshot(self):                           # คืนค่าตัวนับปัจจุบันเป็น dict
        return dict(hash=self.hash, hmac=self.hmac, dec=self.dec, visited=self.visited)


COUNT = OpCounter()                               # ตัวนับ global ใช้ทั้งไฟล์


# ============================================================================
# 1) Cryptographic primitives
# ============================================================================
def H(data: bytes) -> bytes:                      # H(.) = public hash function ใน paper
    COUNT.hash += 1                               # นับเป็น T_H หนึ่งครั้ง
    return hashlib.sha256(data).digest()          # คืน digest 32 byte


def HMAC(key: bytes, msg: bytes) -> bytes:        # HMAC(k, m) ใช้ใน Algorithm 3/4
    COUNT.hmac += 1                               # นับเป็น T_HMAC หนึ่งครั้ง
    return hmac.new(key, msg, hashlib.sha256).digest()  # HMAC-SHA256 ยาว 32 byte


def bf_hash(word: str, master_key: bytes, d: int) -> int:  # h(w, v_i) % d  (Section IV-B-2)
    COUNT.hash += 1                               # paper นับเป็น pseudorandom hash -> T_H
    digest = hmac.new(master_key, word.encode(), hashlib.sha256).digest()  # keyed PRF ด้วย master key v_i
    return int.from_bytes(digest[:8], "big") % d  # เอา 64 bit แรก mod d ได้ตำแหน่งใน bit array


def aes_ctr(key: bytes, nonce16: bytes, data: bytes) -> bytes:  # Enc/Dec แบบรักษาความยาว
    # [ASSUMPTION] paper ไม่ระบุ cipher; ใช้ AES-CTR เพราะความยาว ciphertext = plaintext
    # ทำให้ทุก slice ยาวเท่ากันเสมอ ซึ่งจำเป็นต่อ Reed-Solomon
    c = Cipher(algorithms.AES(key), modes.CTR(nonce16)).encryptor()  # สร้าง AES-CTR
    return c.update(data) + c.finalize()          # CTR เข้ารหัสและถอดรหัสด้วยฟังก์ชันเดียวกัน


def iter_nonce(fid: int, k: int) -> bytes:        # nonce ของ iteration ที่ k ของไฟล์ fid
    # ใส่ fid เข้าไปด้วย เพื่อไม่ให้ใช้ (k_f, nonce) ซ้ำข้ามไฟล์ (keystream reuse)
    return hashlib.sha256(b"iter" + fid.to_bytes(8, "big") + k.to_bytes(4, "big")).digest()[:16]


def prf_positions(e: bytes, xs: np.ndarray, d: int) -> np.ndarray:  # h(u.e, x) % d แบบ vector
    # [ASSUMPTION] ใช้ AES_{u.e}(x) เป็น PRF (AES เป็น PRP จึงเป็น PRF ได้) แทน hash
    # เพราะต้อง remap bit นับล้านตอน build tree; ทำเป็น batch ได้เร็วกว่า hashlib ทีละตัวมาก
    xs = np.asarray(xs, dtype=np.uint64)          # ตำแหน่ง bit ที่เป็น 1 ใน BF เดิม
    blocks = np.zeros((xs.size, 2), dtype="<u8")  # 1 block AES = 16 byte = 2 x uint64
    blocks[:, 0] = xs                             # 8 byte แรก = x, 8 byte หลัง = 0
    enc = Cipher(algorithms.AES(e), modes.ECB()).encryptor()  # AES-ECB ด้วยคีย์ u.e ของ node
    out = enc.update(blocks.tobytes()) + enc.finalize()       # เข้ารหัสทุก block ในครั้งเดียว
    vals = np.frombuffer(out, dtype="<u8")[0::2]  # เอา 8 byte แรกของแต่ละ block
    COUNT.hash += int(xs.size)                    # นับเป็น T_H ตามจำนวนตำแหน่ง
    return (vals % np.uint64(d)).astype(np.int64) # mod d ได้ตำแหน่งใหม่


# ============================================================================
# 2) GF(256) + Reed-Solomon erasure code (Section IV-A-4)
#    systematic Cauchy RS: slice 0..t-1 = ข้อมูลจริง, slice t..n-1 = redundant
#    กู้ไฟล์ได้จาก slice ใดก็ได้ t ชิ้น -> (n, t) reliability ตาม paper
# ============================================================================
GF_EXP = np.zeros(512, dtype=np.uint8)            # ตาราง exponent ของ GF(2^8)
GF_LOG = np.zeros(256, dtype=np.int32)            # ตาราง logarithm ของ GF(2^8)
_x = 1                                            # เริ่มที่ alpha^0 = 1
for _i in range(255):                             # วนสร้างสมาชิกทั้ง 255 ตัวที่ไม่ใช่ 0
    GF_EXP[_i] = _x                               # alpha^i = _x
    GF_LOG[_x] = _i                               # log(_x) = i
    _x <<= 1                                      # คูณด้วย alpha (= x)
    if _x & 0x100:                                # ถ้าเกิน 8 bit
        _x ^= 0x11D                               # ลดด้วย primitive polynomial x^8+x^4+x^3+x^2+1
GF_EXP[255:510] = GF_EXP[0:255]                   # ซ้ำตารางเพื่อไม่ต้อง mod 255 ตอนคูณ


def gf_mul(a: int, b: int) -> int:                # คูณ scalar ใน GF(256)
    if a == 0 or b == 0:                          # ศูนย์คูณอะไรก็ได้ศูนย์
        return 0                                  # คืน 0
    return int(GF_EXP[GF_LOG[a] + GF_LOG[b]])     # a*b = exp(log a + log b)


def gf_inv(a: int) -> int:                        # หาตัวผกผันการคูณ
    return int(GF_EXP[255 - GF_LOG[a]])           # a^-1 = alpha^(255 - log a)


def gf_mul_vec(c: int, vec: np.ndarray) -> np.ndarray:  # คูณ scalar c กับทุก byte ใน vec
    out = np.zeros_like(vec)                      # เตรียมผลลัพธ์เป็นศูนย์
    if c == 0:                                    # ถ้า c = 0 ผลเป็นศูนย์ทั้งหมด
        return out                                # คืนเลย
    nz = vec != 0                                 # เลือกเฉพาะ byte ที่ไม่ใช่ศูนย์
    out[nz] = GF_EXP[GF_LOG[vec[nz]] + GF_LOG[c]] # คูณแบบ vectorized ผ่านตาราง log/exp
    return out                                    # คืน vector ผลคูณ


def gf_mat_inv(M):                                # หา inverse ของเมทริกซ์ t x t ใน GF(256)
    n = len(M)                                    # ขนาดเมทริกซ์
    A = [row[:] + [1 if i == j else 0 for j in range(n)] for i, row in enumerate(M)]  # [M | I]
    for col in range(n):                          # Gauss-Jordan ทีละคอลัมน์
        piv = next(r for r in range(col, n) if A[r][col] != 0)  # หา pivot ที่ไม่ใช่ศูนย์
        A[col], A[piv] = A[piv], A[col]           # สลับแถวให้ pivot อยู่บนเส้นทแยง
        inv = gf_inv(A[col][col])                 # ตัวผกผันของ pivot
        A[col] = [gf_mul(v, inv) for v in A[col]] # ทำ pivot ให้เป็น 1
        for r in range(n):                        # กำจัดคอลัมน์นี้ในแถวอื่น
            if r != col and A[r][col] != 0:       # ข้ามแถว pivot และแถวที่เป็นศูนย์อยู่แล้ว
                f = A[r][col]                     # ตัวคูณที่ต้องลบ
                A[r] = [a ^ gf_mul(f, b) for a, b in zip(A[r], A[col])]  # ลบ = XOR ใน GF(2^8)
    return [row[n:] for row in A]                 # ครึ่งขวาคือ M^-1


class ReedSolomon:                                # RS erasure code แบบ systematic
    def __init__(self, n: int, t: int):           # n = จำนวน cloud, t = จำนวน slice ข้อมูล
        assert 1 <= t <= n <= 255                 # ข้อจำกัดของ GF(256)
        self.n, self.t = n, t                     # เก็บพารามิเตอร์
        # Cauchy matrix: C[i][j] = 1 / (x_i XOR y_j) กับ x_i = t+i, y_j = j (ไม่ซ้ำกันเลย)
        self.C = [[gf_inv((t + i) ^ j) for j in range(t)] for i in range(n - t)]
        # generator matrix G = [I_t ; C]  -> ทุก t แถวของ G invertible (MDS)
        self.G = [[1 if i == j else 0 for j in range(t)] for i in range(t)] + self.C

    def encode(self, data_slices):                # สร้าง n-t redundant slice
        vecs = [np.frombuffer(s, dtype=np.uint8) for s in data_slices]  # แปลง slice เป็น array
        parity = []                               # เก็บ redundant slice
        for row in self.C:                        # แต่ละแถวของ Cauchy -> 1 redundant slice
            acc = np.zeros_like(vecs[0])          # ตัวสะสมผลรวม
            for coef, v in zip(row, vecs):        # sum_j C[i][j] * s_j
                acc ^= gf_mul_vec(coef, v)        # บวกใน GF(2^8) = XOR
            parity.append(acc.tobytes())          # แปลงกลับเป็น bytes
        return list(data_slices) + parity         # คืนทั้งหมด n slice (C_{i,1..n})

    def decode(self, available: dict):            # available = {index_slice: bytes} อย่างน้อย t ชิ้น
        idx = sorted(available)[: self.t]         # เลือกมา t ชิ้นแรก
        sub = [self.G[i] for i in idx]            # แถวของ G ที่ตรงกับ slice ที่มี
        inv = gf_mat_inv(sub)                     # inverse ของ submatrix
        vecs = [np.frombuffer(available[i], dtype=np.uint8) for i in idx]  # slice ที่มี
        out = []                                  # slice ข้อมูลเดิม t ชิ้น
        for row in inv:                           # แต่ละแถวของ inverse -> 1 slice เดิม
            acc = np.zeros_like(vecs[0])          # ตัวสะสม
            for coef, v in zip(row, vecs):        # คูณเมทริกซ์ใน GF(256)
                acc ^= gf_mul_vec(coef, v)        # สะสมด้วย XOR
            out.append(acc.tobytes())             # เก็บ slice ที่กู้ได้
        return out                                # คืน C_{i,1..t}


# ============================================================================
# 3) Iterative encryption (Section IV-A-3, Eq.(1), Eq.(2), Eq.(4))
# ============================================================================
def secret_vector_length(t: int, T_zhang: int) -> int:  # Eq.(4): m = ceil(1 + t + (T-1) log_t t!)
    return math.ceil(1 + t + (T_zhang - 1) * math.log(math.factorial(t), t))  # cracking complexity เท่ากับ [19]


def gen_secret_vector(t: int, m: int, rng: random.Random):  # สร้าง secret vector V (0-based)
    assert m >= t + 1                             # ต้องยาวพอให้มี V[t+1] = V[t]
    first = list(range(t))                        # t ตัวแรกต้องไม่ซ้ำกัน -> ทุก slice ถูกเข้ารหัส
    rng.shuffle(first)                            # สลับลำดับแบบสุ่ม
    V = first + [first[-1]]                       # ตัวที่ t+1 = ตัวที่ t  ("ผูกปม" ด้วย k_f)
    while len(V) < m:                             # เติมส่วนที่เหลือ
        V.append(rng.randrange(t))                # ค่าสุ่มใน [0, t)
    return V                                      # คืน V ความยาว m


def iterative_encrypt(slices, V, kf: bytes, fid: int):  # Eq.(1)
    A = list(slices)                              # array A เริ่มจาก F_{i,1..t}
    for k in range(len(V) - 1):                   # ทำ m-1 iterations
        cur, nxt = V[k], V[k + 1]                 # slice ที่จะเข้ารหัส และ slice ถัดไป
        # [FIX] Eq.(1) พิมพ์เงื่อนไขสลับ ใช้ตามตัวอย่าง Fig.2(a):
        #       V[k] != V[k+1] -> คีย์ = H(A[V[k+1]]),  V[k] == V[k+1] -> คีย์ = k_f
        key = hashlib.sha256(A[nxt]).digest() if cur != nxt else kf  # เลือกคีย์
        A[cur] = aes_ctr(key, iter_nonce(fid, k), A[cur])  # A[V[k]] = Enc(key, A[V[k]])
    return A                                      # ได้ C_{i,1..t}


def iterative_decrypt(cslices, V, kf: bytes, fid: int):  # Eq.(2) = ย้อนกลับของ Eq.(1)
    B = list(cslices)                             # array B เริ่มจาก C_{i,1..t}
    for k in reversed(range(len(V) - 1)):         # ย้อนจาก iteration สุดท้ายกลับไปแรก
        cur, nxt = V[k], V[k + 1]                 # คู่ index เดียวกับตอนเข้ารหัส
        # B[nxt] ตอนนี้มีค่าเท่ากับตอนเข้ารหัส iteration k พอดี จึงได้คีย์เดิม
        key = hashlib.sha256(B[nxt]).digest() if cur != nxt else kf  # คีย์เดิม
        B[cur] = aes_ctr(key, iter_nonce(fid, k), B[cur])  # CTR: ถอด = เข้ารหัสซ้ำ
    return B                                      # ได้ F_{i,1..t}


# ============================================================================
# 4) Dataset
# ============================================================================
@dataclass
class Doc:                                        # เอกสาร 1 ไฟล์
    fid: int                                      # file ID เดิม (fid_i)
    content: bytes                                # เนื้อหาไฟล์ (plaintext)
    keywords: set                                 # keyword set W_i


def synthetic_corpus(N, vocab_size, kw_per_doc, file_size, zipf_s=1.1, seed=1):
    """สร้าง corpus สังเคราะห์ ความถี่ keyword เป็น Zipf (skew แบบ email จริง)"""
    rng = np.random.default_rng(seed)             # RNG ที่ fix seed ได้
    ranks = np.arange(1, vocab_size + 1)          # อันดับ 1..V
    probs = ranks ** (-zipf_s)                    # Zipf: p(rank) ∝ rank^-s
    probs /= probs.sum()                          # normalize ให้รวมเป็น 1
    vocab = [f"kw{i:06d}" for i in range(vocab_size)]  # ชื่อ keyword สมมติ
    docs = []                                     # เก็บเอกสารทั้งหมด
    for i in range(N):                            # สร้าง N เอกสาร
        z = int(min(max(1, rng.poisson(kw_per_doc)), vocab_size))  # จำนวน keyword ของเอกสารนี้
        idx = rng.choice(vocab_size, size=z, replace=False, p=probs)  # สุ่ม keyword ไม่ซ้ำ
        docs.append(Doc(i, rng.bytes(file_size), {vocab[k] for k in idx}))  # เนื้อหาสุ่ม + keyword
    return docs                                   # คืนรายการเอกสาร


HERE = os.path.dirname(os.path.abspath(__file__))  # โฟลเดอร์ของไฟล์นี้ (baselines/)
sys.path.insert(0, HERE)                          # ให้ import amtp_dataset.py ที่อยู่ข้าง ๆ ได้
DEFAULT_QUERIES = os.path.join(HERE, "results", "exp1_queries.json")  # ไฟล์ query กลาง (Chen สร้างไว้)


def dataset():
    """import amtp_dataset ตอนใช้งานจริง (demo รันได้โดยไม่ต้องมี dataset)"""
    import amtp_dataset                           # ตัวโหลด dataset กลาง
    return amtp_dataset                           # คืน module


def to_du(src, data_dir, extra=None):
    """แปลง Doc ของ dataset กลาง -> Doc ของ Du (fid = ลำดับ, เนื้อหา = ไฟล์ .txt จริง, keyword = W(d))
    extra = {ตำแหน่ง: keyword ที่ฝังเพิ่ม} (Exp. 2: keyword ทดสอบจาก results/exp2_layouts.json)"""
    out = []                                      # ผลลัพธ์
    for i, d in enumerate(src):                   # ทุกเอกสาร
        with open(os.path.join(data_dir, d.file_path), "rb") as f:  # เปิดไฟล์ plaintext (title + abstract)
            content = f.read()                    # Du กระจายเนื้อหาไฟล์จริงไปทุก cloud
        out.append(Doc(i, content, set(d.keywords) | set((extra or {}).get(i, ()))))  # fid = i ([ASSUMPTION] 8)
    return out                                    # คืนรายการ


# ============================================================================
# 5) Bloom filter tree (Section IV-B-3, Algorithm 1, Eq.(3))
# ============================================================================
class Node:                                       # T_node = <fid, BF, pl, pr> (+ e, E จาก remapping)
    __slots__ = ("bf", "d", "fid", "pl", "pr", "e", "E", "slot", "_enc")  # ประหยัด memory

    def __init__(self, bf, fid=None, pl=None, pr=None):  # constructor
        self.bf = bf                              # Bloom filter ของ node
        self.d = 0                                # ความยาว BF ของ node นี้ (optimized tree: แต่ละ node ยาวไม่เท่ากัน)
        self.fid = fid                            # file ID (leaf เท่านั้น; nonleaf = None)
        self.pl, self.pr = pl, pr                 # ลูกซ้าย / ลูกขวา
        self.e = None                             # ค่าสุ่ม u.e สำหรับ remapping
        self.E = None                             # u.E = Enc(k_f, u.BF_org)
        self.slot = None                          # index ไฟล์ (cloud ใช้หา slice ที่เก็บไว้)
        self._enc = None                          # cache AES key schedule ของ u.e (สร้างตอนเข้า node ครั้งแรก)

    def is_leaf(self):                            # leaf = ไม่มีลูก
        return self.pl is None and self.pr is None


def node_bf_length(n_set_bits: int, r: int, fp: float) -> int:
    """Section IV-B-5 (optimized tree, Fig. 3(b)): ความยาว BF ของ node = r*n'/(-ln(1 - p^(1/r)))
    n' = จำนวน element ของ node (keyword ใน subtree + random insertion c|W|) และ r*n' = จำนวนตำแหน่ง
    ที่ถูกตั้งเป็น 1 ใน BF_org ของ node (ใน space ขนาด d ที่ใหญ่พอสำหรับ root ตำแหน่งแทบไม่ชนกัน)
    -> ความยาว = n_set_bits / (-ln(1 - p^(1/r)))  [ASSUMPTION] ข้อ 6"""
    return max(8, math.ceil(n_set_bits / -math.log(1 - fp ** (1 / r))))


# ============================================================================
# 6) Cloud server (เก็บ slice ที่ j, BF tree ที่ remap แล้ว, ทำ SecureSearch)
# ============================================================================
class CloudServer:
    def __init__(self, j: int, d: int, behavior: str = "honest"):  # j = หมายเลข cloud
        self.j = j                                # หมายเลข cloud (1..n ใน paper, 0..n-1 ในโค้ด)
        self.d = d                                # ความยาว Bloom filter
        self.root = None                          # root ของ BF tree ที่ remap แล้ว
        self.slices = {}                          # slot -> C_{i,j}
        self.leaves = []                          # leaf ทั้งหมด (ใช้จำลองการโกง 'irrelevant')
        self.behavior = behavior                  # honest / empty / drop / tamper / forge / irrelevant

    def _h(self, enc, x: int, d: int) -> int:     # h(T.e, x) % d_u แบบ scalar ระหว่างค้นหา
        blk = int(x).to_bytes(8, "little") + b"\x00" * 8  # block เดียวกับ prf_positions
        v = int.from_bytes(enc.update(blk)[:8], "little")  # AES_{e}(x) 8 byte แรก
        COUNT.hash += 1                           # นับเป็น T_H
        return v % d                              # ตำแหน่งใน BF ของ node นี้ (ยาว d_u)

    def _match(self, node: Node, Q) -> bool:      # เงื่อนไข match: T.BF[h(T.e,x)] = 1 ทุก x ใน Q
        bits = node.bf                            # BF แบบ packed bytes
        enc = node._enc                           # AES key schedule ของ T.e
        if enc is None:                           # ครั้งแรกที่เข้า node นี้ (รอบ warm-up สร้างไว้ให้)
            enc = node._enc = Cipher(algorithms.AES(node.e), modes.ECB()).encryptor()  # cache ไว้ใน node
        d = node.d                                # ความยาว BF ของ node นี้
        for x in Q:                               # ทุกตำแหน่งใน trapdoor
            p = self._h(enc, x, d)                # remap ตำแหน่ง
            if not (bits[p >> 3] >> (7 - (p & 7))) & 1:  # อ่าน bit ที่ p (ลำดับ big-endian ของ packbits)
                return False                      # มี bit เป็น 0 -> ไม่ match (หยุดทันที)
        return True                               # ทุก bit เป็น 1 -> match

    def secure_search(self, node: Node, Q, out):  # Algorithm 2: SecureSearch (DFS)
        COUNT.visited += 1                        # นับ node ที่เดินผ่าน (v_Q)
        if not self._match(node, Q):              # บรรทัด 2 / 7: เช็กเงื่อนไข match
            return                                # ไม่ match -> ตัดกิ่งนี้ทิ้งทั้งกิ่ง
        if node.is_leaf():                        # บรรทัด 6: เป็น leaf
            out.append(dict(E=node.E, enc_id=node.fid, e=node.e,  # บรรทัด 8: คืน T.E, T.fid, T.e
                            slice=self.slices[node.slot], slot=node.slot))  # และ slice ที่ผูกกับ leaf
        else:                                     # node ภายใน
            self.secure_search(node.pl, Q, out)   # บรรทัด 3: ลูกซ้าย
            self.secure_search(node.pr, Q, out)   # [FIX] บรรทัด 4: paper พิมพ์ T.pl ซ้ำ -> ต้องเป็น T.pr

    def match_slots(self, node: Node, Q, out):    # Algorithm 2 แบบเดียวกัน แต่คืนแค่ slot ของ leaf ที่ match
        if not self._match(node, Q):              # (ไม่หยิบ E, ID', e และ slice ของไฟล์) ใช้วัด search ไม่รวม fetch
            return                                # เท่านั้น ไม่ได้ใช้ตอบ query จริง
        if node.is_leaf():
            out.append(node.slot)
        else:
            self.match_slots(node.pl, Q, out)
            self.match_slots(node.pr, Q, out)

    def answer(self, Q, rng: random.Random):      # ตอบ query (รวมพฤติกรรมโกงไว้ทดสอบ verification)
        out = []                                  # ผลลัพธ์
        self.secure_search(self.root, Q, out)     # ค้นหาตาม Algorithm 2
        b = self.behavior                         # พฤติกรรมของ cloud นี้
        if b == "empty":                          # กรณี (1): บอกว่าไม่มีผลลัพธ์
            return []                             # คืนว่าง
        if b == "drop" and out:                   # กรณี (3): ส่งผลไม่ครบ
            out.pop(rng.randrange(len(out)))      # ตัดทิ้ง 1 รายการ (สุ่ม)
        if b == "collude_drop" and out:           # ทุก cloud สมรู้ร่วมคิด ตัดไฟล์เดียวกัน
            out.remove(min(out, key=lambda it: it["slot"]))  # ตัดไฟล์ที่ slot น้อยสุด (ตกลงกันไว้)
        if b == "tamper" and out:                 # กรณี (4): แก้ ciphertext slice
            it = out[0]                           # เลือกผลลัพธ์แรก
            s = bytearray(it["slice"])            # คัดลอก slice
            s[0] ^= 0xFF                          # พลิก byte แรก
            it["slice"] = bytes(s)                # ใส่กลับ
        if b == "forge" and out:                  # กรณี (4): ปลอม encoded ID
            out[0]["enc_id"] = os.urandom(len(out[0]["enc_id"]))  # ID สุ่ม
        if b == "irrelevant":                     # กรณี (2): ส่งไฟล์ที่ไม่เกี่ยวข้องเพิ่ม
            got = {it["slot"] for it in out}      # slot ที่ส่งอยู่แล้ว
            extra = [lf for lf in self.leaves if lf.slot not in got]  # leaf อื่น
            if extra:                             # ถ้ามี
                lf = rng.choice(extra)            # สุ่มมา 1 ตัว
                out.append(dict(E=lf.E, enc_id=lf.fid, e=lf.e,  # ส่งข้อมูลจริงของ leaf นั้น
                                slice=self.slices[lf.slot], slot=lf.slot))
        return out                                # คืนผลลัพธ์


# ============================================================================
# 7) Du et al. scheme (Data owner + Data user)
# ============================================================================
@dataclass
class VerifyResult:                               # ผลการตรวจสอบของ data user
    fids: set                                     # file ID ที่ผ่านการตรวจ (union ข้าม cloud)
    malicious: dict                               # cloud j -> เหตุผลที่ถูกจับ
    slices: dict                                  # fid -> {j: C_{i,j}} สำหรับกู้ไฟล์
    filtered_out: int = 0                         # จำนวนผลที่ถูกกรองทิ้ง (remapping collision / irrelevant result)
    filtered_per_cloud: dict = None               # cloud j -> จำนวนที่ถูกกรองทิ้ง


class DuScheme:
    def __init__(self, n_clouds=5, t=3, T_zhang=10, r=7, c=0.1, fp=1e-6, seed=0):
        assert n_clouds >= t                      # ต้องมี cloud อย่างน้อย t ตัวถึงจะกู้ไฟล์ได้
        self.n, self.t = n_clouds, t              # n cloud, แบ่งไฟล์เป็น t slice
        self.r, self.c, self.fp = r, c, fp        # #master key, สัดส่วน random insertion, FP ที่คาดหวัง
        self.rng = random.Random(seed)            # RNG สำหรับ V และการเลือก
        self.np_rng = np.random.default_rng(seed) # RNG ของ numpy สำหรับ random insertion
        self.m = secret_vector_length(t, T_zhang) # ความยาว secret vector จาก Eq.(4)
        self.rs = ReedSolomon(n_clouds, t)        # RS erasure code (n, t)
        self.clouds = []                          # รายการ CloudServer

    # ------------------------------------------------------------------ setup (offline)
    def setup(self, docs, behaviors=None):
        """Data owner: KeyGen, file distribution, BF generation, tree build, remap, ID encoding"""
        self.kf = os.urandom(32)                  # secret key k_f (แชร์กับ data user)
        self.master_keys = [os.urandom(32) for _ in range(self.r)]  # master keys v_1..v_r
        self.V = gen_secret_vector(self.t, self.m, self.rng)  # secret vector V
        n_root = len(set().union(*(dc.keywords for dc in docs)))  # keyword ไม่ซ้ำทั้งหมด = element ของ root
        # [ASSUMPTION] ข้อ 6: d = ความยาว BF ที่ root ต้องใช้ ตามสูตร Section IV-B-5 d = r*n'/(-ln(1 - p^(1/r)))
        #   โดย n' = (1+c)*n_root (นับ random insertion เป็น keyword เพิ่ม c|W| ตัว)
        #   trapdoor และ BF_org ใช้ space ขนาด d นี้; แต่ละ node ถูก remap ลงใน BF ยาว d_u ของตัวเอง
        self.d = math.ceil(self.r * (1 + self.c) * n_root / -math.log(1 - self.fp ** (1 / self.r)))
        self.pos_dtype = ">u4" if self.d < 2 ** 32 else ">u8"  # BF_org เก็บเป็นรายการตำแหน่ง (big-endian)
        self.orig_len = {}                        # ความยาวไฟล์จริง (ใช้ตัด padding ตอนกู้)
        behaviors = behaviors or ["honest"] * self.n  # พฤติกรรมของแต่ละ cloud
        self.clouds = [CloudServer(j, self.d, behaviors[j]) for j in range(self.n)]  # สร้าง n cloud

        # ---- (A) file distribution: segmentation -> iterative enc -> RS -> ส่งไป cloud j
        all_slices = {}                           # fid -> [C_{i,1}, ..., C_{i,n}]
        for dc in docs:                           # ทุกไฟล์
            self.orig_len[dc.fid] = len(dc.content)  # จำความยาวจริง
            L = math.ceil(len(dc.content) / self.t)  # ความยาว slice
            padded = dc.content.ljust(L * self.t, b"\x00")  # เติม padding ให้หารลงตัว
            F = [padded[k * L:(k + 1) * L] for k in range(self.t)]  # F_{i,1..t}
            C = iterative_encrypt(F, self.V, self.kf, dc.fid)  # Eq.(1)
            all_slices[dc.fid] = self.rs.encode(C)  # เพิ่ม redundant slice ได้ n slice
            for j in range(self.n):               # ส่ง slice ที่ j ไป cloud j
                self.clouds[j].slices[dc.fid] = all_slices[dc.fid][j]

        # ---- (B) Bloom filter generation (Section IV-B-2) + random insertion
        # BF_i ใน space ขนาด d (ใหญ่พอสำหรับ root) เก็บเป็นรายการตำแหน่งที่เป็น 1 (เรียงแล้ว) แทน bit array
        # [ASSUMPTION] ข้อ 6: bit array ยาว d ต่อ leaf ใช้ RAM ไม่ไหว; รายการตำแหน่งแทน BF เดียวกันทุกประการ
        leaf_pos = []                             # BF_i ของทุกไฟล์ (ตำแหน่งที่เป็น 1)
        for dc in docs:                           # ทุกไฟล์
            pos = [bf_hash(w, v, self.d) for w in dc.keywords for v in self.master_keys]  # h(w, v_i) % d
            n_rand = int(self.c * len(dc.keywords) * self.r)  # c * |W_i| * r
            pos.extend(self.np_rng.integers(0, self.d, n_rand).tolist())  # random insertion (blinding)
            leaf_pos.append(np.unique(np.asarray(pos, dtype=np.int64)))  # เรียง + ตัดซ้ำ
        fids = [dc.fid for dc in docs]            # file ID ตามลำดับ

        # ---- (C)+(D) Bloom filter tree แบบ optimized (Algorithm 1 + Section IV-B-5, Fig. 3(b))
        #   พร้อม remapping (IV-B-4) และ encoded ID (Algorithm 3) แยกต่อ cloud ในรอบเดียว
        kfjs = [self.kf + cl.j.to_bytes(4, "big") for cl in self.clouds]  # คีย์ k_f || j ของแต่ละ cloud
        _, roots = self._build(leaf_pos, fids, 0, len(docs), kfjs)
        for cl, root in zip(self.clouds, roots):  # root ของ tree ที่ remap แล้วของแต่ละ cloud
            cl.root = root
        del leaf_pos                              # BF_org ต้นฉบับไม่ใช้แล้ว (เจ้าของข้อมูลไม่ต้องเก็บ) คืน RAM
        gc.collect()                              # เก็บกวาดทันที
        COUNT.reset()                             # setup เป็น offline ไม่นับรวมกับ phase ที่วัด

    def _build(self, leaf_pos, fids, lo, hi, kfjs):
        """Algorithm 1 (BFTreeBuild, top-down split) กับ optimized tree ของ Section IV-B-5:
        BF_org ของ node = OR ของ BF_i ใน subtree (ใน space ขนาด d = union ของตำแหน่ง)
        แต่ละ node ถูก remap (IV-B-4) ลงใน BF ยาว d_u ที่คำนวณจาก element ของ node นั้นเอง
        คืน (ตำแหน่งที่เป็น 1 ของ BF_org, [node ที่ remap แล้วของแต่ละ cloud])"""
        if hi - lo == 1:                          # บรรทัด 2-4: เหลือ BF เดียว -> leaf
            pos = leaf_pos[lo]                    # BF_i ของไฟล์นี้
            return pos, [self._remap(pos, cl, kfj, fid=fids[lo]) for cl, kfj in zip(self.clouds, kfjs)]
        half = lo + (hi - lo + 1) // 2            # บรรทัด 10: แบ่งให้ |BF_l| - |BF_r| <= 1
        lpos, lnodes = self._build(leaf_pos, fids, lo, half, kfjs)  # บรรทัด 12: ลูกซ้าย
        rpos, rnodes = self._build(leaf_pos, fids, half, hi, kfjs)  # บรรทัด 13: ลูกขวา
        pos = np.union1d(lpos, rpos)              # บรรทัด 6-9: T.BF = OR ของทุก BF ในกลุ่ม
        nodes = []
        for cl, kfj, ln, rn in zip(self.clouds, kfjs, lnodes, rnodes):
            node = self._remap(pos, cl, kfj)      # remap node ภายในลง BF ยาว d_u
            node.pl, node.pr = ln, rn             # ผูกลูก
            nodes.append(node)
        return pos, nodes

    def _encode_id(self, fid: int, Cij: bytes, bf_bytes: bytes, kfj: bytes) -> bytes:
        """Algorithm 3: ID'_{i,j} = (HMAC(kf||j, fid) || fid) XOR R_{i,j}"""
        M = Cij + bf_bytes                        # บรรทัด 3: M_{i,j} = C_{i,j} || BF_i
        R = self._expand(HMAC(kfj, M), 40)        # บรรทัด 5: R_{i,j} = HMAC(kf||j, M)
        fid_b = fid.to_bytes(8, "big")            # fid เป็น 8 byte
        ID = HMAC(kfj, fid_b) + fid_b             # บรรทัด 6: ID_{i,j} = HMAC(kf||j, fid) || fid
        return bytes(a ^ b for a, b in zip(ID, R))  # บรรทัด 7: ID' = ID XOR R

    @staticmethod
    def _expand(r32: bytes, n: int) -> bytes:     # [ASSUMPTION] ขยาย R (32 byte) ให้ยาว n byte
        return (r32 + H(r32))[:n]                 # paper ไม่ระบุ; ใช้ R || H(R) แล้วตัด

    def _remap(self, xs: np.ndarray, cl: CloudServer, kfj: bytes, fid=None) -> Node:
        """Section IV-B-4: สร้าง node ที่ remap แล้วของ cloud นี้ พร้อม u.e (และ u.E, ID' ที่ leaf)
        xs = { a | u.BF[a] = 1 } ของ BF_org (space ขนาด d); BF_temp ยาว d_u ของ node นี้ (optimized tree)"""
        new = Node(None)                          # node ใหม่ของ cloud นี้
        new.e = os.urandom(16)                    # u.e สุ่มไม่ซ้ำกันในแต่ละ cloud
        new.d = node_bf_length(len(xs), self.r, self.fp)  # d_u ของ node นี้ (Section IV-B-5)
        tmp = np.zeros(new.d, dtype=bool)         # BF_temp
        tmp[prf_positions(new.e, xs, new.d)] = True  # BF_temp[h(u.e, x)] = 1
        new.bf = np.packbits(tmp).tobytes()       # เก็บแบบ packed bytes (ประหยัด memory 8 เท่า)
        if fid is not None:                       # leaf: ใส่ E และ encoded ID
            bfb = xs.astype(self.pos_dtype).tobytes()  # BF_org ของไฟล์นี้ (รายการตำแหน่ง) [ASSUMPTION] ข้อ 6
            nonce = os.urandom(12)                # nonce ของ AES-GCM
            new.E = nonce + AESGCM(self.kf).encrypt(nonce, bfb, None)  # u.E = Enc(k_f, u.BF_org)
            new.slot = fid                        # ผูกกับ slice ที่เก็บใน cloud
            new.fid = self._encode_id(fid, cl.slices[fid], bfb, kfj)  # แทน fid ด้วย ID'_{i,j}
            cl.leaves.append(new)                 # จำ leaf ไว้
        # [ASSUMPTION] u.E ใช้เฉพาะ leaf ที่ถูกคืนใน Algorithm 2 จึงไม่สร้างให้ node ภายใน
        return new                                # คืน node ใหม่

    # ------------------------------------------------------------------ Query generation
    def trapdoor(self, keywords):                 # Section IV-B-6
        Q = set()                                 # trapdoor Q = เซตของตำแหน่ง
        for w in keywords:                        # ทุก keyword ใน W_q
            for v in self.master_keys:            # r master keys -> r * T_H ต่อ keyword
                Q.add(bf_hash(w, v, self.d))      # h(w, v_i) % d
        return sorted(Q)                          # ส่ง Q ให้ทุก cloud (AND semantics)

    @staticmethod
    def supports(query_type: str) -> bool:        # Du et al. รองรับเฉพาะ conjunctive (AND)
        return query_type == "AND"                # trapdoor เป็นเซตตำแหน่ง -> ต้องเจอครบทุก bit = AND

    # ------------------------------------------------------------------ Search
    def search(self, Q):
        """ส่ง Q ไปทุก cloud; คืน response และเวลาค้นหาของแต่ละ cloud"""
        responses, times = {}, []                 # ผลลัพธ์และเวลา
        for cl in self.clouds:                    # แต่ละ cloud ทำงานแยกกันอิสระ
            t0 = time.perf_counter()              # เริ่มจับเวลา
            responses[cl.j] = cl.answer(Q, self.rng)  # Algorithm 2
            times.append(time.perf_counter() - t0)  # เวลาของ cloud นี้
        return responses, times                   # คืนทั้งสองอย่าง

    def search_no_fetch(self, Q):
        """Algorithm 2 ทุก cloud แต่คืนแค่ slot ที่ match (ไม่หยิบข้อมูลของไฟล์): เวลาของแต่ละ cloud และ slot ที่ได้
        ใช้วัดเวลา search ไม่รวม fetch เท่านั้น วัดหลัง query เต็มจบแล้ว จึงไม่กระทบคอลัมน์เดิม"""
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
        """Section IV-B-7 (filtering) + Algorithm 4 + การเทียบผลข้าม cloud"""
        Qarr = np.array(Q, dtype=np.int64)        # ตำแหน่ง trapdoor เป็น array
        verified, per_cloud, malicious = {}, {}, {}  # fid->{j:slice}, j->set(fid), j->เหตุผล
        filtered = 0                              # จำนวนที่ถูกกรองทิ้ง
        irr = {}                                  # cloud j -> จำนวนรายการที่ไม่ผ่าน filtering
        for j, items in responses.items():        # ทุก cloud j
            kfj = self.kf + j.to_bytes(4, "big")  # คีย์ k_f || j
            ok = set()                            # fid ที่ผ่านของ cloud นี้
            for it in items:                      # ทุกผลลัพธ์ที่ cloud j ส่งมา
                COUNT.dec += 1                    # นับการถอด u.E
                try:                              # ถ้า u.E ถูกแก้ AES-GCM จะ error
                    bfb = AESGCM(self.kf).decrypt(it["E"][:12], it["E"][12:], None)  # u.BF_org
                except Exception:                 # ถอดไม่ได้
                    malicious.setdefault(j, []).append("E tampered")  # จับได้
                    continue                      # ข้ามรายการนี้
                org = np.frombuffer(bfb, self.pos_dtype)  # BF_org = รายการตำแหน่งที่เป็น 1 (เรียงแล้ว)
                k = np.searchsorted(org, Qarr)    # หา x แต่ละตัวของ Q ใน BF_org
                if not ((k < org.size) & (org[np.minimum(k, org.size - 1)] == Qarr)).all():  # filtering: มี x ใน Q ที่ BF_org[x] = 0
                    # กรณี (2) irrelevant result และ remapping collision ของ cloud ที่ซื่อสัตย์
                    # ถูกกรองทิ้งด้วยวิธีเดียวกันตาม paper (Section IV-B-7) แยกสองกรณีนี้ไม่ได้
                    # จึงไม่กล่าวหา cloud แค่ตัดออก ผลลัพธ์สุดท้ายจึงยังถูกต้อง
                    filtered += 1                 # นับจำนวนที่กรองทิ้งทั้งหมด
                    irr[j] = irr.get(j, 0) + 1    # นับแยกต่อ cloud (บันทึกไว้ดูเท่านั้น)
                    continue                      # ข้ามไป
                # ---- Algorithm 4 บรรทัด 4-10
                R = self._expand(HMAC(kfj, it["slice"] + bfb), 40)  # R_{i,j} = HMAC(kf||j, C||BF)
                ID = bytes(a ^ b for a, b in zip(it["enc_id"], R))  # ID = ID' XOR R
                hm_ext, fid_b = ID[:32], ID[32:]  # แยก HM' และ fid
                if not hmac.compare_digest(hm_ext, HMAC(kfj, fid_b)):  # HM' != HMAC(kf||j, fid)
                    # [FIX] Algorithm 4 บรรทัด 10 เขียน "=" -> ต้องเป็น "!=" จึงจะเป็น malicious
                    malicious.setdefault(j, []).append("ID/slice verification failed")
                    continue                      # ไม่รับรายการนี้
                fid = int.from_bytes(fid_b, "big")  # file ID เดิม
                if fid in ok:                     # ส่งซ้ำ
                    malicious.setdefault(j, []).append("duplicate result")
                    continue                      # ข้าม
                ok.add(fid)                       # ผ่านการตรวจ
                verified.setdefault(fid, {})[j] = it["slice"]  # เก็บ slice ไว้กู้ไฟล์
            per_cloud[j] = ok                     # fid ที่ผ่านของ cloud j

        # ---- เทียบผลข้าม cloud (อาศัยสมมติฐาน "มี cloud ซื่อสัตย์อย่างน้อย 1 ตัว")
        clouds = [j for j in responses]           # รายการ cloud ทั้งหมด
        union = set().union(*(per_cloud[j] for j in clouds))  # ผลรวมของทุก cloud
        for j in clouds:                          # ทุก cloud
            missing = union - per_cloud[j]        # รายการที่ cloud อื่นส่งแต่ j ไม่ส่ง
            if missing:                           # กรณี (1)/(3): ว่าง หรือ ไม่ครบ
                malicious.setdefault(j, []).append(f"incomplete: missing {len(missing)}")
        return VerifyResult(union, malicious, verified, filtered, irr)  # ผลการตรวจ

    # ------------------------------------------------------------------ Reconstruction
    def reconstruct(self, fid: int, slices: dict) -> bytes:
        """Section IV-A-5: RS decode จาก t slice ใดก็ได้ แล้ว iterative decrypt"""
        if len(slices) < self.t:                  # slice ไม่พอ
            raise ValueError("ได้ slice ไม่ถึง t ชิ้น")
        C = self.rs.decode(slices)                # กู้ C_{i,1..t}
        F = iterative_decrypt(C, self.V, self.kf, fid)  # Eq.(2)
        return b"".join(F)[: self.orig_len[fid]]  # ต่อ slice แล้วตัด padding

    # ------------------------------------------------------------------ Update
    def update(self, *args, **kwargs):            # Table IV: Update = N/A
        raise NotImplementedError("Du et al. [7] ไม่รองรับ dynamic update (N/A ใน Table IV)")


# ============================================================================
# 8) Query helpers
# ============================================================================
def supports(shape: str) -> bool:
    """trapdoor ของ Du คือเซตตำแหน่งที่ต้องเป็น 1 ครบทุกตำแหน่ง = AND เท่านั้น -> รองรับ single และ conjunctive"""
    return shape in ("single", "conjunctive")    # OR / nested = N/A


def parse_and_query(q: str):
    """แปลง query string แบบ "A AND B AND C" -> ["A", "B", "C"]  (single = keyword เดียว)"""
    return [t.strip() for t in q.split(" AND ")]  # แยกด้วย AND


def load_queries(args, D, sizes):
    """query กลาง: replay จากไฟล์ (ค่าเริ่มต้น results/exp1_queries.json) ถ้าไม่มีไฟล์จึงสร้างด้วย seed เดียวกัน"""
    path = args.queries or DEFAULT_QUERIES       # ไฟล์ query ที่จะใช้
    if os.path.exists(path):                      # มีไฟล์ query กลาง
        with open(path, encoding="utf-8") as f:   # เปิดไฟล์
            rows = json.load(f)                   # [{"N","kQ","shape","query",...}, ...]
        print(f"[queries] replay {os.path.relpath(path)} ({len(rows)} queries)")
        return rows, sorted({x["N"] for x in rows})  # query + ขนาด N ที่อยู่ในไฟล์
    if args.queries:                              # ระบุไฟล์มาแต่หาไม่เจอ
        raise SystemExit(f"ไม่พบไฟล์ query {path}")
    print("[queries] ไม่พบไฟล์ query กลาง -> สร้างด้วย amtp_dataset.make_queries (seed เดียวกัน = query เดียวกัน)")
    rows = []                                     # query ที่สร้างเอง
    for n in sizes:                               # ทุกขนาด
        src = D.sample(n, args.domains, args.data)  # เอกสาร n ไฟล์
        rows += [dict(N=n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)]
    return rows, sizes                            # คืนผล


# ============================================================================
# 9) Benchmark helpers (รูปแบบผลลัพธ์เหมือน Chen [40] / SE-COLLAB: <ชื่อ>_ms, _ms_median, _ms_std)
# ============================================================================
class Writer:
    """สะสมผลแต่ละแถว พิมพ์ขึ้นจอ และเขียน results/du/du_<name>.csv ตอน close()"""

    def __init__(self, name: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)       # สร้างโฟลเดอร์ผลลัพธ์
        self.path = os.path.join(out_dir, f"du_{name}.csv")  # ไฟล์ปลายทาง
        self.rows = []                            # แถวที่สะสมไว้

    def add(self, **row):
        self.rows.append(row)                     # เก็บแถว
        show = {k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in row.items()
                if k in ("N", "n_clouds", "kQ", "shape", "status", "rQ", "bloom_fp",
                         "query_gen_ms", "server_total_ms", "verify_total_ms", "end_to_end_ms")}  # คอลัมน์ที่โชว์
        print("  " + "  ".join(f"{k}={v}" for k, v in show.items()), flush=True)  # พิมพ์ขึ้นจอ

    def close(self):
        if not self.rows:                         # ไม่มีข้อมูล
            return                                # ไม่ต้องเขียน
        keys = list(dict.fromkeys(k for r in self.rows for k in r))  # รวมชื่อคอลัมน์ทุกแถว (คงลำดับ)
        with open(self.path, "w", newline="", encoding="utf-8") as f:  # เปิดไฟล์
            w = csv.DictWriter(f, fieldnames=keys)  # writer
            w.writeheader()                       # หัวตาราง
            w.writerows(self.rows)                # ข้อมูล (แถว N/A ช่องที่ไม่มีจะว่าง)
        print(f"-> {os.path.relpath(self.path)}")  # แจ้งที่อยู่ไฟล์
        dataset().write_manifest(self.path)       # เครื่อง / commit / คำสั่งที่ใช้รัน (<csv>.manifest.json)


def summarize(samples):
    """รวมผลหลายรอบ -> <ชื่อ>_ms (mean), <ชื่อ>_ms_median, <ชื่อ>_ms_std"""
    out = {}                                      # ผลสรุป
    for k in samples[0]:                          # ทุก metric
        v = [x[k] for x in samples]               # ค่าทุกรอบ
        out[f"{k}_ms"] = st.mean(v)               # ค่าเฉลี่ย
        out[f"{k}_ms_median"] = st.median(v)      # มัธยฐาน
        out[f"{k}_ms_std"] = st.pstdev(v)         # ส่วนเบี่ยงเบนมาตรฐาน
    return out                                    # คืนผล


def build(src, n_clouds, args, extra=None):
    """Data owner setup (offline): กระจายไฟล์ + สร้าง BF tree แล้ว remap ต่อ cloud คืน (scheme, docs, info)"""
    docs = to_du(src, args.data_dir, extra)       # เอกสารพร้อมเนื้อหาไฟล์จริง
    sch = DuScheme(n_clouds=n_clouds, t=args.t, r=args.r, c=args.c, fp=args.fp, seed=args.seed)  # scheme
    t0 = time.perf_counter()                      # จับเวลา setup
    sch.setup(docs)                               # Section IV-A + IV-B
    t_setup = (time.perf_counter() - t0) * 1e3    # เวลา setup (ms)
    info = dict(n_clouds=n_clouds, t=args.t, r=args.r, d_bits=sch.d, m=sch.m,  # พารามิเตอร์
                setup_ms=t_setup,                 # เวลา setup ของ data owner
                cs_storage_bytes=storage_bytes(sch))  # ขนาดที่ cloud ทั้งหมดเก็บ
    print(f" N={len(docs)} n_c={n_clouds}: d={sch.d} bits, m={sch.m}, setup={t_setup / 1e3:.1f}s, "
          f"cloud storage={info['cs_storage_bytes'] / 1e6:.1f} MB", flush=True)
    return sch, docs, info                        # คืนผล


def storage_bytes(sch):
    """ขนาดข้อมูลที่ทุก cloud เก็บ: slice ทุกไฟล์ + BF tree (BF, e ทุก node; E, ID' ที่ leaf)"""
    total = 0                                     # รวม byte
    for cl in sch.clouds:                         # ทุก cloud
        total += sum(len(x) for x in cl.slices.values())  # ciphertext slices
        stack = [cl.root]                         # เดิน tree แบบไม่ recursive
        while stack:                              # ทุก node
            u = stack.pop()                       # node ปัจจุบัน
            total += len(u.bf) + len(u.e)         # BF + e
            if u.is_leaf():                       # leaf
                total += len(u.E) + len(u.fid)    # E + encoded ID
            else:                                 # node ภายใน
                stack += [u.pl, u.pr]             # ลูกทั้งสอง
    return total                                  # คืนผล


def run_query(sch, terms):
    """query เต็ม 1 รอบ: DU สร้าง trapdoor -> ทุก cloud ค้น -> DU verify -> DU กู้ไฟล์
    คืน (เวลาแยกตามขั้น, จำนวน operation, ข้อมูลขนาด/ผลลัพธ์)"""
    COUNT.reset()                                 # ล้างตัวนับ
    t0 = time.perf_counter()                      # เริ่ม
    Q = sch.trapdoor(terms)                       # Section IV-B-6: r * kQ hash
    t1 = time.perf_counter()                      # จบ query generation
    c_q = COUNT.snapshot()                        # นับ T_H ตอนสร้าง trapdoor
    COUNT.reset()                                 # ล้างก่อนวัด search
    responses, t_clouds = sch.search(Q)           # Algorithm 2 ทุก cloud (จับเวลาแยกต่อ cloud)
    c_s = COUNT.snapshot()                        # T_H และจำนวน node ที่เดินผ่านรวมทุก cloud
    COUNT.reset()                                 # ล้างก่อนวัด verify
    t2 = time.perf_counter()                      # เริ่ม verify
    vr = sch.verify(Q, responses)                 # filtering + Algorithm 4 + เทียบผลข้าม cloud
    t3 = time.perf_counter()                      # จบ verify
    c_v = COUNT.snapshot()                        # T_HMAC / T_H / Dec ตอน verify
    for fid in vr.fids:                           # Section IV-A-5: กู้ทุกไฟล์ที่ผ่าน
        sch.reconstruct(fid, vr.slices[fid])      # RS decode + iterative decrypt
    t4 = time.perf_counter()                      # จบการกู้ไฟล์
    assert not vr.malicious, f"cloud ที่ซื่อสัตย์ถูกจับว่าโกง: {vr.malicious}"  # benchmark ทุก cloud honest
    server_max = max(t_clouds) * 1e3              # cloud ทำงานขนานกัน -> latency = cloud ที่ช้าที่สุด
    times = {
        "query_gen": (t1 - t0) * 1e3,             # สร้าง trapdoor
        "server_total": server_max,               # ค้นฝั่ง cloud (ขนาน = ช้าสุด) เทียบกับ server_total ของ Chen
        "server_sum": sum(t_clouds) * 1e3,        # งานรวมทุก cloud = O(n_c r v_Q) ใน Table IV
        "verify_total": (t3 - t2) * 1e3,          # filtering + HMAC ทุกผลลัพธ์ทุก cloud + เทียบข้าม cloud
        "du_decrypt": (t4 - t3) * 1e3,            # RS decode + iterative decrypt ทุกไฟล์ผลลัพธ์
    }
    # end_to_end = until the DU holds the verified result set (shared definition, baselines/README.md);
    # recovering the files (du_decrypt) is reported separately. No network time.
    times["end_to_end"] = times["query_gen"] + server_max + times["verify_total"]
    # search ไม่รวม fetch (คอลัมน์เพิ่ม ไม่เปลี่ยนคอลัมน์เดิม): Algorithm 2 เดิมแต่คืนแค่ slot ที่ match วัดหลังทุกขั้นข้างบน
    nf_slots, t_nf = sch.search_no_fetch(Q)
    for j, items in responses.items():            # ต้องได้ leaf ชุดเดียวกับ query เต็ม
        assert sorted(nf_slots[j]) == sorted(it["slot"] for it in items), "search_no_fetch != search"
    times["search_no_fetch"] = max(t_nf) * 1e3    # ขนาน = cloud ที่ช้าที่สุด (เหมือน server_total)
    times["search_no_fetch_sum"] = sum(t_nf) * 1e3
    ops = dict(hash_qgen=c_q["hash"], hash_search=c_s["hash"], visited=c_s["visited"],  # จำนวน op
               hmac_verify=c_v["hmac"], hash_verify=c_v["hash"], dec_verify=c_v["dec"])
    R = [len(v) for v in responses.values()]      # |R| ของแต่ละ cloud
    info = dict(rQ=len(vr.fids), R_per_cloud=st.mean(R),  # จำนวนผลลัพธ์ที่ผ่าน / ต่อ cloud
                filtered_out=vr.filtered_out,     # ผลจาก remapping collision ที่ถูกกรองทิ้ง
                token_bytes=4 * len(Q),           # trapdoor = len(Q) ตำแหน่ง ตำแหน่งละ 4 byte ส่งให้ทุก cloud
                # proof = หลักฐานที่ DU ใช้ตรวจ (E = Enc(BF_org), enc_id, e) ไม่รวม slice ของไฟล์
                proof_bytes=sum(len(it["E"]) + len(it["enc_id"]) + len(it["e"])
                                for items in responses.values() for it in items),
                response_bytes=sum(len(it["E"]) + len(it["enc_id"]) + len(it["e"]) + len(it["slice"])
                                   for items in responses.values() for it in items),  # ที่ทุก cloud ส่งกลับ
                ids=set(vr.fids))                 # ผลลัพธ์ (ไว้เทียบ ground truth ไม่เขียนลง CSV)
    return times, ops, info                       # คืนผล


def measure(sch, terms, reps, warmup):
    """warm-up ก่อน แล้ววัดจริง reps รอบ ปิด garbage collector ระหว่างวัด (เหมือน Chen / SE-COLLAB)"""
    for _ in range(warmup):                       # รอบอุ่นเครื่อง
        run_query(sch, terms)                     # ไม่บันทึก
    samples, ops, info = [], {}, {}               # ที่เก็บผล
    gc.disable()                                  # ปิด GC ไม่ให้เวลาแกว่ง
    try:
        for _ in range(max(1, reps)):             # รอบที่วัดจริง
            m, ops, info = run_query(sch, terms)  # วัด
            samples.append(m)                     # เก็บเวลา
    finally:
        gc.enable()                               # เปิด GC กลับ
    return summarize(samples), ops, info          # สรุปเวลา + op + ขนาด


def run_queries(w, sch, docs, src, qs, n, info, args, D):
    """วัดทุก query ของขนาด n แล้วเขียนลง Writer (ใช้ร่วมกันทั้ง exp1 และ clouds)"""
    inv = D.inverted_index(src)                   # plaintext index ไว้หา ground truth
    for q in qs:                                  # ทุก query
        base = dict(N=n, n_clouds=info["n_clouds"], kQ=q["kQ"], shape=q["shape"],
                    domain=q.get("domain", ""))   # คอลัมน์หลัก
        if not supports(q["shape"]):              # OR / nested
            w.add(**base, status="N/A")           # บันทึกว่าไม่รองรับ
            continue                              # ข้าม
        terms = parse_and_query(q["query"])       # keyword ของ query
        res, ops, qi = measure(sch, terms, args.reps, args.warmup)  # วัด
        ids = qi.pop("ids")                       # ผลลัพธ์จริง
        gt = D.ground_truth(inv, terms)           # คำตอบที่ถูกต้อง
        missed = len(gt - ids)                    # ไฟล์ที่ควรได้แต่ไม่ได้
        assert missed == 0, f"ผลค้นหาขาดไป {missed} ไฟล์: {q['query']}"  # Bloom filter ไม่มี false negative
        w.add(**base, status="ok", **qi, gt=len(gt), bloom_fp=len(ids - gt),  # บันทึก
              **res, **ops, d_bits=info["d_bits"], setup_ms=info["setup_ms"],
              cs_storage_bytes=info["cs_storage_bytes"])


# ============================================================================
# 10) Experiments (ตาม AMTP Section V-B)
# ============================================================================
def suite_exp1(args):
    """AMTP Exp.1: replay query กลางทุกขนาด N (Du รองรับแค่ AND -> แบบอื่นเขียน N/A)"""
    D = dataset()                                 # dataset กลาง
    args.data_dir = D.load(args.data)["dir"]      # โฟลเดอร์ dataset จริง (ไว้อ่าน .txt)
    qs_all, sizes = load_queries(args, D, args.sizes)  # query กลาง
    print(f"[exp1] Boolean search scalability  sizes={sizes} n_clouds={args.clouds[0]}")
    w = Writer("exp1_boolean_scalability", args.out)  # ไฟล์ผล
    for n in sizes:                               # ทุกขนาด database
        src = D.sample(n, args.domains, args.data)  # เอกสาร n ไฟล์ (ชุดเดียวกันทุก scheme)
        sch, docs, info = build(src, args.clouds[0], args)  # setup
        run_queries(w, sch, docs, src, [x for x in qs_all if x["N"] == n], n, info, args, D)  # วัด
        del sch, docs, src                        # คืน RAM ก่อนขนาดถัดไป
        gc.collect()
    w.close()                                     # เขียน CSV


def suite_exp2(args):
    """AMTP Exp.2: verify เทียบกับ r_Q บนเอกสารชุดเดียวกับทุก scheme (results/exp2_layouts.json) เป็นค่าอ้างอิง
    Du ไม่มี Merkle tree หรือ proof ที่ครอบหลายไฟล์: ตรวจทีละผลลัพธ์ด้วย HMAC ของ encoded ID (Algorithm 4)
    และเทียบผลข้าม cloud -> ต้นทุน verify = O(n_c |R|) ไม่ขึ้นกับตำแหน่งของไฟล์ (layout)"""
    D = dataset()                                 # dataset กลาง
    args.data_dir = D.load(args.data)["dir"]      # โฟลเดอร์ dataset จริง (ไว้อ่าน .txt)
    lay = D.load_exp2_layouts()                   # layout กลาง
    n = lay["N"]                                  # ขนาด database (ตามไฟล์กลาง)
    print(f"[exp2] verification vs r_Q  N={n} n_clouds={args.clouds[0]} layouts={list(lay['layouts'])}")
    src = D.sample(n, lay["domains"], args.data)  # เอกสาร n ไฟล์ (ชุดเดียวกันทุก scheme)
    sch, docs, info = build(src, args.clouds[0], args, D.exp2_markers(lay, n))  # setup + keyword ทดสอบ
    w = Writer("exp2_selective_proof", args.out)  # ไฟล์ผล
    for r in lay["rq"]:                           # ทุก r_Q
        for name, spec in lay["layouts"].items():  # ทุก layout
            res, ops, qi = measure(sch, [f"{spec['prefix']}{r}"], args.reps, args.warmup)  # วัด
            ids = qi.pop("ids")                   # ผลลัพธ์
            gt = set(spec["docs"][str(r)])        # ไฟล์ที่ฝัง keyword ไว้ (ตำแหน่ง = fid)
            assert not (gt - ids), f"ผลขาด {len(gt - ids)} ไฟล์"  # Bloom filter ไม่มี false negative
            w.add(N=n, rQ=r, layout=name, n_clouds=info["n_clouds"], gt=len(gt), bloom_fp=len(ids - gt),
                  **{k: v for k, v in qi.items() if k != "rQ"}, rQ_returned=qi["rQ"], **res, **ops)  # บันทึก
    w.close()                                     # เขียน CSV
    del sch, docs                                 # คืน RAM
    gc.collect()


def old_slice(sch, fid, content, j=0):
    """slice ของ cloud j ของไฟล์ fid รุ่นเก่า (content) ที่ data owner เคยกระจายไว้: ขั้นตอนเดียวกับ setup (A)"""
    L = math.ceil(len(content) / sch.t)
    padded = content.ljust(L * sch.t, b"\x00")
    C = iterative_encrypt([padded[k * L:(k + 1) * L] for k in range(sch.t)], sch.V, sch.kf, fid)
    return sch.rs.encode(C)[j]


def run_tampered(sch, terms, kind, fids, extra=None, gt=None):
    """query หนึ่งรอบที่ cloud 0 โกง (cloud อื่นซื่อสัตย์) จับเวลาเฉพาะ DU verify
    modify = พลิก byte แรกของ slice (เหมือนพฤติกรรม tamper), hide = ตัดผลทิ้ง (drop), inject = ใส่ leaf ของไฟล์ที่ไม่ตรง
    query (irrelevant; extra = [leaf]), old_version = slice ของไฟล์รุ่นเก่า (extra = {fid: slice})
    คืน ({verify_total}, {detected, localized, result_ok}) detected = cloud 0 ถูกระบุว่า malicious;
    localized = จำนวนรายการของ cloud 0 ที่ DU ชี้ได้ว่าผิด (HMAC ไม่ผ่าน, ขาด, หรือถูกกรองทิ้ง);
    result_ok = ผลสุดท้ายหลังกรอง = คำตอบที่ถูก gt (fid ของไฟล์ที่มี keyword)"""
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
            failed += 1                                       # รายการที่ HMAC / u.E ไม่ผ่าน
    # รายการที่ HMAC ไม่ผ่านก็ "ขาด" จาก cloud 0 ด้วย -> นับไฟล์ละครั้ง; inject = รายการที่ถูกกรองทิ้งด้วย Bloom filter
    # (ตอนไม่โกงก็มีรายการถูกกรองจาก remapping collision ได้ จึงนับ filtered เฉพาะแบบ inject)
    bad = (vr.filtered_per_cloud or {}).get(0, 0) if kind == "inject" else max(failed, missing)
    injected = {lf.slot for lf in extra} if kind == "inject" and extra else set()
    # ผลสุดท้ายถูก = มีไฟล์ที่ตรงครบ และไม่มีไฟล์ที่ถูก inject (Bloom false positive ของ Du เองไม่นับเป็นผิด)
    ok = gt is not None and gt <= set(vr.fids) and not (injected & set(vr.fids))
    return ({"verify_total": (t1 - t0) * 1e3}, {"detected": 0 in vr.malicious, "localized": bad, "result_ok": ok})


# ---------------- dataset-v4 suites (แผนของอาจารย์; ไฟล์กลางใน datasets/arxiv/data_v4/ ใช้ร่วมกับทุก scheme)
def suite_search1(args):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl ทุก domain ทุกขนาด files-per-domain
    (Du รองรับ AND ซึ่งเป็นทุกรูปแบบของไฟล์นี้) ต้องไม่มีไฟล์ขาด (Bloom filter ไม่มี false negative)
    false positive ที่หลุดการกรองบันทึกไว้ในคอลัมน์ bloom_fp"""
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
                assert len(gt) == q["result_size"][str(n)] and not (gt - ids), f"ผลขาด: {q['query_id']} n={n}"
                w.add(scheme="Du[7]", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", n_clouds=info["n_clouds"], gt=len(gt), bloom_fp=len(ids - gt),
                      **{k: v for k, v in qi.items() if k != "rQ"}, rQ=len(gt), rQ_returned=qi["rQ"], **res, **ops)
            del sch, docs, src, inv
            gc.collect()
    w.close()


def suite_verify1(args):
    """Verification 1.1 (single domain): verify_keywords.csv แถว single_domain ที่ --fix ไฟล์ต่อ domain (ค่าอ้างอิง:
    Du ตรวจด้วย HMAC ทีละผลลัพธ์และเทียบข้าม cloud)"""
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
            assert len(gt) == r["result_size"] and not (gt - ids), f"ผลขาด: {r['keyword']}"
            w.add(scheme="Du[7]", domain=dname, N=args.fix, keyword=r["keyword"], target_results=r["target_results"],
                  rank=r["rank"], status="ok", n_clouds=info["n_clouds"], gt=len(gt), bloom_fp=len(ids - gt),
                  **{k: v for k, v in qi.items() if k != "rQ"}, rQ=len(gt), rQ_returned=qi["rQ"], **res, **ops)
        del sch, docs, src, inv
        gc.collect()
    w.close()


def suite_tamper(args):
    """Verification 1.2 (single domain): tamper_sets.jsonl ต่อ domain: keyword (~2,000 ผลลัพธ์) ที่ files_per_domain
    cloud 0 โกงกับเอกสาร t ตัวแรกของ tamper_order (modify / hide / old_version) หรือใส่ไฟล์ t ตัวแรกของ
    amtp_dataset.inject_order ที่ไม่ตรง query (inject) วัดเวลา verify, จับได้กี่รอบ, ชี้ตัวได้กี่รายการ และผลสุดท้ายถูกไหม
    Du จับ hide ได้ด้วยการเทียบผลข้าม cloud (ต้องมี cloud ซื่อสัตย์อย่างน้อย 1 ตัว; ถ้าทุก cloud ตัดไฟล์เดียวกัน
    จะจับไม่ได้ ดู demo 'ALL collude drop') inject ถูกกรองทิ้งด้วย Bloom filter โดยไม่กล่าวหา cloud (Section IV-B-7)
    verify ของ Du ตรวจทุกรายการอยู่แล้ว (ไม่มี early abort) full check จึงเท่ากับ verify ปกติ"""
    D = dataset()
    args.data_dir = D.load(args.data)["dir"]
    sets = [r for r in D.tamper_sets() if r["domain"] in args.s_domains]
    w = Writer("tamper_detection", args.out)
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = D.domain_docs(dname, n, args.data)
        fid_of = {d.doc_id: i for i, d in enumerate(src)}       # fid = ลำดับในรายการ (to_du)
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
        assert not any(i["detected"] for i in infos), "cloud ที่ซื่อสัตย์ถูกจับว่าโกง"
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
    เปลี่ยนจำนวน cloud n_c ที่ N คงที่ (query AND จากไฟล์กลางที่ N นั้น หรือสร้างใหม่ด้วย seed เดียวกัน)"""
    D = dataset()                                 # dataset กลาง
    args.data_dir = D.load(args.data)["dir"]      # โฟลเดอร์ dataset
    src = D.sample(args.n, args.domains, args.data)  # เอกสาร N ไฟล์
    qs, _ = load_queries(args, D, [args.n])       # query กลาง
    qs = [x for x in qs if x["N"] == args.n and x["kQ"] in args.kq and supports(x["shape"])]
    if not qs:                                    # ไฟล์กลางไม่มี N นี้ -> สร้างด้วย seed เดียวกัน
        qs = [dict(N=args.n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)
              if supports(q["shape"])]
    print(f"[clouds] multi-cloud sensitivity  N={args.n} clouds={args.clouds} queries={len(qs)}")
    w = Writer("clouds_sensitivity", args.out)           # ไฟล์ผล
    for n_c in args.clouds:                       # ทุกจำนวน cloud
        if n_c < args.t:                          # RS ต้องมี cloud อย่างน้อย t ตัว
            print(f"  skip n_c={n_c} < t={args.t}")
            continue
        sch, docs, info = build(src, n_c, args)   # setup
        run_queries(w, sch, docs, src, qs, args.n, info, args, D)  # วัด
        del sch, docs                             # คืน RAM
        gc.collect()
    w.close()                                     # เขียน CSV


def demo(_args=None):
    """ทดสอบความถูกต้องด้วย corpus สังเคราะห์ (ไม่ต้องมี dataset): ค้นหา, กู้ไฟล์, จับ cloud ที่โกง"""
    docs = synthetic_corpus(300, 400, 12, 2048, seed=3)  # corpus เล็ก
    src = max(docs, key=lambda x: len(x.keywords))  # เอกสารต้นแบบของ query
    kws = sorted(src.keywords)[:2]                # query 2 คำจากเอกสารเดียว -> AND ได้ผลอย่างน้อย 1 ไฟล์
    gt = {dc.fid for dc in docs if set(kws) <= dc.keywords}  # คำตอบที่ถูก
    print(f"query={kws}  ground truth={len(gt)} files")  # แสดง query
    scenarios = {                                 # สถานการณ์ทดสอบ (n=5, t=3)
        "all honest": ["honest"] * 5,
        "cloud1 empty": ["honest", "empty", "honest", "honest", "honest"],
        "cloud2 drop": ["honest", "honest", "drop", "honest", "honest"],
        "cloud3 tamper": ["honest", "honest", "honest", "tamper", "honest"],
        "cloud4 forge": ["honest", "honest", "honest", "honest", "forge"],
        "cloud0 irrelevant": ["irrelevant", "honest", "honest", "honest", "honest"],
        "ALL collude drop": ["collude_drop"] * 5,  # ข้อจำกัดของ Du: ทุก cloud ตัดไฟล์เดียวกัน -> จับไม่ได้
    }
    for name, beh in scenarios.items():           # รันทีละสถานการณ์
        sch = DuScheme(n_clouds=5, t=3, seed=11)  # scheme ใหม่
        sch.setup(docs, behaviors=beh)            # setup พร้อมพฤติกรรม
        Q = sch.trapdoor(kws)                     # trapdoor
        resp, _ = sch.search(Q)                   # ค้นหา
        vr = sch.verify(Q, resp)                  # ตรวจสอบ
        ok_files = sum(sch.reconstruct(fid, vr.slices[fid]) == docs[fid].content  # กู้ได้ตรงต้นฉบับ
                       for fid in vr.fids if len(vr.slices[fid]) >= sch.t)
        print(f"{name:22s} verified={len(vr.fids):3d} (gt={len(gt)}, fp={len(vr.fids - gt)}) "
              f"reconstructed_ok={ok_files:3d} filtered={vr.filtered_per_cloud} malicious={vr.malicious}")


# ============================================================================
# 11) main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Du et al. [7] simulation")  # ตัวอ่าน argument
    ap.add_argument("mode", choices=["demo", "exp1", "exp2", "clouds", "search1", "verify1", "tamper"])  # โหมดที่จะรัน
    # ---- dataset กลาง (amtp_dataset.py) ชื่อเดียวกับ Chen ----
    ap.add_argument("--data", default=None, help="โฟลเดอร์ dataset (ค่าเริ่มต้น <repo>/data/amtp_file_db_v4 หรือ AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="domain ที่ใช้")
    ap.add_argument("--seed", type=int, default=42, help="seed ของการสร้าง query (เท่ากับ seed ของ dataset)")
    ap.add_argument("--queries", default=None,
                    help=f"ไฟล์ query JSON ที่จะ replay (ค่าเริ่มต้น {os.path.relpath(DEFAULT_QUERIES)})")
    # ---- ชื่อและค่าเริ่มต้นเหมือน Chen / SE-COLLAB ----
    ap.add_argument("--reps", type=int, default=30, help="จำนวนรอบที่วัดจริง")
    ap.add_argument("--warmup", type=int, default=3, help="จำนวนรอบ warm-up (ไม่นับ)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000],
                    help="ขนาด N ของ exp1 เมื่อไม่มีไฟล์ query กลาง (สูงสุด 500,000 = 4 domain x 125,000)")
    ap.add_argument("--kq", type=int, nargs="+", default=[1, 2, 4, 8, 16], help="จำนวน keyword ต่อ query")
    ap.add_argument("--queries-per-kq", type=int, default=1, help="จำนวน query ต่อ k_Q")
    ap.add_argument("--n", type=int, default=10_000, help="ขนาด database ของ clouds")
    # ---- เฉพาะ Du ----
    ap.add_argument("--clouds", type=int, nargs="+", default=[5],
                    help="จำนวน cloud n_c (exp1 ใช้ค่าแรก, clouds วนทุกค่า เช่น 4 8 16 32)")
    ap.add_argument("--t", type=int, default=3, help="จำนวน slice ข้อมูล (กู้ไฟล์ได้จาก t cloud)")
    ap.add_argument("--r", type=int, default=7, help="จำนวน master key ของ Bloom filter")
    ap.add_argument("--c", type=float, default=0.1, help="สัดส่วน random insertion")
    ap.add_argument("--fp", type=float, default=1e-6, help="false positive ที่ยอมรับได้ของ Bloom filter")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "du"), help="โฟลเดอร์ผลลัพธ์")
    Dm = dataset()                                # ค่าเริ่มต้นของ v4 suites ใช้ร่วมกับทุก scheme
    ap.add_argument("--s-domains", nargs="+", default=list(Dm.DOMAINS), help="v4 single-domain suites: domain")
    ap.add_argument("--fpd", type=int, nargs="+", default=Dm.V4_SIZES, help="search1: จำนวนไฟล์ต่อ domain")
    ap.add_argument("--fix", type=int, default=Dm.V4_FIX, help="verify1: ไฟล์ต่อ domain")
    ap.add_argument("--s1-kq", type=int, default=Dm.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--tamper-kinds", nargs="+", default=Dm.TAMPER_KINDS, choices=Dm.TAMPER_KINDS)
    a = ap.parse_args()                           # อ่าน argument
    {"demo": demo, "exp1": suite_exp1, "exp2": suite_exp2, "clouds": suite_clouds, "search1": suite_search1,
     "verify1": suite_verify1, "tamper": suite_tamper}[a.mode](a)  # เรียกใช้


if __name__ == "__main__":
    main()
