"""
se_collab_sim.py
============================================================================
Simulation ของ baseline SE-COLLAB [37]
  S. Fugkeaw, J. Deevijit,
  "SE-COLLAB: Achieving Fine-Grained and Efficiently Verifiable Searchable
   Encryption With Boolean Multi-Keyword Search for Collaborative IIoT Data Sharing",
  IEEE Access, vol. 13, pp. 126012-126029, 2025. doi:10.1109/ACCESS.2025.3590026

โค้ดนี้จำลองตามที่ paper อธิบายไว้ใน Section IV-B (Phase 1-8):
  A. Trapdoor Transformation                (Algorithm 1 — Cloud Proxy, PRE)
  B. Secure Search Execution                (Algorithm 2 — BPL bitwise AND/OR/NOT)
  C. Result verification                    (Phase 6 — Merkle path + result proof)
ใช้ไลบรารีชุดเดียวกับ paper (Charm-Crypto abenc_bsw07 + PyCryptodome)

มี 7 ฝ่าย (Fig. 1): Attribute Authority (AA), Data Owner (DO) + Edge Proxy, Data User (DU),
                   Cloud Proxy, Cloud Storage, Blockchain

สิ่งที่วัดเพื่อเทียบกับ AMTP ตาม Table IV ของ AMTP:
  - Query Generation : 3 T_E + T_P                  (trapdoor ไม่ขึ้นกับจำนวน keyword)
  - Search           : j T_B                         (bitwise AND/OR/NOT บน BPL)
  - Verification     : T_E + T_P + t_leaf T_H        (Merkle path ของผลลัพธ์ + result proof)
  - Update           : N/A                           (paper ไม่ได้กำหนด dynamic update)
  -> ใช้ใน Experiment 1 (AND/OR/nested) และ Experiment 2 (proof / verification)

จุดที่ paper เขียนไม่ชัด/มีบั๊ก และโค้ดนี้ตัดสินใจเอง (ดูคอมเมนต์ [ASSUMPTION]/[FIX]):
(ทุกจุดยังคงจำนวน operation ตาม paper)
  1. [ASSUMPTION] ไม่ระบุ pairing group -> ใช้ Charm SS512 (ค่าเริ่มต้นของ abenc_bsw07)
  2. [FIX] C3 = g^{αr} ต้องใช้ g^α (master key) ซึ่ง DU ไม่มี -> ให้ DU ถือ s_u ของตัวเอง, C3 = PK_DU^r
           และไม่บอกว่า proxy อ่าน W_q ได้อย่างไร -> C2 = hashed-ElGamal ด้วยคีย์ KDF(PK_Cloud^r)
  3. [ASSUMPTION] ExtractKeyword(T'q) -> token I(w) = PRF(SymK_DO, w) อยู่ใน C2;
           DU ได้ SymK_DO จากการถอด CT_key ด้วย CP-ABE
  4. [FIX] สมการตรวจ ZKP ที่พิมพ์ไว้ไม่สมดุล (δ' ไม่มี W_q,B_q; V2' ไม่ตรงกับ V2)
           -> ใช้ Chaum-Pedersen DLEQ NIZK (Fiat-Shamir); signature σ = Schnorr ใน G1
  5. [ASSUMPTION] Algorithm 1 (PRE) ทำตามตัวอักษรกับ C3; C2 เข้ารหัสใหม่ภายใต้คีย์ใหม่
  6. [ASSUMPTION] "ZKP over (T'q, R)" ใน Phase 6 -> Schnorr proof ของ proxy (2 exp แทน TE+TP)
           ตัวเลข Fig. 6 ของ paper เทียบกับคอลัมน์ merkle_verify_ms
  7. [ASSUMPTION] Blockchain = ledger จำลองแบบ hash-chained แทน Ganache/Web3
  8. [ASSUMPTION] Revocation: CT_key ต่อ DO มีชิ้นเดียว -> lazy re-encryption = encapsulate ใหม่ 1 ครั้ง
           พร้อม bump เวอร์ชัน attribute
  9. [ASSUMPTION] BSW07 เป็น single-authority ต่อ ciphertext -> DO 1 ราย ผูกกับ AA 1 ตัว
 10. [ASSUMPTION] N ใหญ่: BPL ของ keyword ที่ df < N/64 เก็บเป็น posting แล้วแปลงตอน query
 11. [ASSUMPTION] keyword ของ dataset เป็นวลีหลายคำ -> คำที่อยู่ติดกันใน query (ไม่มี AND/OR/NOT คั่น)
     รวมเป็น keyword เดียว เช่น "general method AND possible description" = 2 keyword
 12. [ASSUMPTION] cross-domain search: Phase 4 Step 1 ให้ DU รวมคีย์จากหลาย AA เป็น trapdoor เดียว และ
     Tq = (g^r, H(Wq,Bq)e(g,g)^{ar}, PK^r) ไม่มีส่วนที่ขึ้นกับ DO -> trapdoor / signature / NIZK / ตรวจของ proxy /
     PRE transform เกิดครั้งเดียวต่อ query (Table 4: TrapGen = 3E + Pe) ส่วน C2 พก token I(w) ของทุก owner
     (ต่อจากข้อ 3) แล้ว proxy ค้น index + สร้าง Merkle proof ต่อ owner และเซ็นผลรวมครั้งเดียว
     (Phase 6 Step 3: Verify(pi, T'q, R)); DU ตรวจ Merkle root ต่อ owner
 13. [FIX] proxy ไม่ตรวจ bind ด้วย pairing (paper Phase 4 Step 2 ตรวจแค่ signature + ZKP; Table 4 มี P_e
     เฉพาะใน TrapGen) -> pairing เกิดครั้งเดียวต่อ query ฝั่ง DU ตาม TrapGen = 3E + P_e
 14. ค่าเริ่มต้นของ --proof-mode = paths (Merkle path ทีละไฟล์ ชี้ไฟล์ที่ถูกแก้ได้ ตาม Phase 6);
     multi (multiproof) เป็นการ optimize ที่ไม่อยู่ใน paper ใช้เมื่อสั่งเท่านั้น
 15. ต้นทุน verify ที่ implement = Merkle + Schnorr (2E) ส่วน Table 4 ของ paper เขียน E + P_e + f_ct H
     แต่ไม่ได้อธิบาย "ZKP over (T'q, R)" -> ไม่เติม pairing ที่ไม่มีหน้าที่; verify ของเราจึงเป็น lower bound
หมายเหตุ: paper ไม่ได้ใช้ index Merkle root ตอนตรวจผล -> ผลลัพธ์ที่ถูกตัดทิ้งจะตรวจไม่เจอ
(เป็นพฤติกรรมของ paper ไม่ใช่บั๊กของการจำลอง; selftest ข้อ t_omission_not_detected)

Workload: dataset กลางของ AMTP (dataset-v4, arXiv 4 domain x 125,000 ไฟล์, ไฟล์ใน datasets/arxiv/data_v4/) ผ่าน amtp_dataset.py
  - N เอกสาร = N/4 ไฟล์แรกของแต่ละ domain (ไม่สุ่ม) -> ทุก scheme ได้เอกสารชุดเดียวกัน
  - keyword ใช้ที่สกัดไว้ใน documents.csv ตรง ๆ, เนื้อหาที่เข้ารหัส = ไฟล์ .txt จริง
  - exp1 ตรวจผลทุก query กับ ground truth จาก plaintext index (ต้องตรงเป๊ะ)
  - demo / selftest / paper / revocation ใช้ corpus สังเคราะห์ (รันได้โดยไม่ต้องมี dataset)

วิธีรัน (ต้องลง Charm-Crypto ก่อน ดู baselines/README.md):
  python3 se_collab_sim.py demo                 # ดูการทำงานทีละขั้นด้วยตัวอย่างเล็ก ๆ
  python3 se_collab_sim.py selftest             # ทดสอบความถูกต้อง 18 ข้อ
  python3 se_collab_sim.py paper                # จำลอง Fig. 2-6 ของ paper (sanity check)
  python3 se_collab_sim.py exp1                 # replay results/exp1_queries.json (N = 10k..200k)
  python3 se_collab_sim.py exp2                   # replays results/exp2_layouts.json (N = 200k)
  python3 se_collab_sim.py exp5                   # replays results/exp5_workload.json (1 owner = 1 domain)
  python3 se_collab_sim.py revocation
ผลทุก suite เขียนลง results/secollab/secollab_<suite>.csv (mean, median, std จาก --reps รอบ หลัง warm-up --warmup รอบ)
รูปแบบคอลัมน์เหมือน chen_et_al_sim.py
============================================================================
"""

# ----------------------------------------------------------------------------- imports
from __future__ import annotations

import argparse  # อ่าน argument จาก command line
import csv  # เขียนผลการทดลองเป็นไฟล์ CSV
import gc  # ปิด garbage collector ระหว่างจับเวลา
import hashlib  # SHA-256
import hmac  # HMAC (ใช้ทำ PRF)
import json  # อ่าน/เขียนไฟล์ query
import math  # คำนวณพารามิเตอร์ Bloom filter
import os  # os.urandom() สุ่มคีย์ + จัดการ path
import re  # ตัดคำ / แปลง policy
import statistics as st  # mean / median / std
import struct  # length-prefix ใน hash
import sys  # เพิ่ม path ให้ import amtp_dataset.py + sys.exit ใน selftest
import time  # จับเวลา
from collections import Counter, defaultdict  # นับความถี่ / dict ค่าเริ่มต้น
from dataclasses import dataclass, field  # คลาสเก็บข้อมูล
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np  # bit vector ของ BPL
from Crypto.Cipher import AES  # AES-CBC / AES-ECB (PyCryptodome เหมือน paper)
from Crypto.Util.Padding import pad, unpad  # PKCS#7
from charm.schemes.abenc.abenc_bsw07 import CPabe_BSW07  # CP-ABE แบบ BSW07 (เหมือน paper)
from charm.toolbox.pairinggroup import GT, ZR, PairingGroup, pair  # bilinear pairing


# ============================================================================
# 1) Cryptographic primitives — hash, PRF, AES, PRP, Bloom filter, Merkle tree
# ============================================================================

# ---------------------------------------------------------------- hashing
def H(*parts: bytes, tag: bytes = b"") -> bytes:
    """Hash หลายชิ้นต่อกันแบบ length-prefixed (ใส่ความยาวนำหน้าแต่ละชิ้น)
    เพื่อให้การต่อข้อมูลไม่กำกวม เช่น H("ab","c") != H("a","bc")"""
    h = hashlib.sha256()
    h.update(tag)                              # tag แยกการใช้งาน เช่น b"PRF", b"AES", b"TQ"
    for p in parts:
        h.update(struct.pack(">I", len(p)))    # ความยาว 4 ไบต์นำหน้า
        h.update(p)
    return h.digest()


def prf(key: bytes, msg: bytes) -> bytes:
    """PRF = HMAC-SHA256 ผลลัพธ์ deterministic: คีย์เดียวกัน + keyword เดียวกัน -> token เดียวกัน
    (นี่คือเหตุผลที่ cloud match keyword ได้ แต่ก็ทำให้รู้ว่า query ซ้ำกัน = leakage)"""
    return hmac.new(key, msg, hashlib.sha256).digest()


# ---------------------------------------------------------------- AES
def aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """เข้ารหัส AES-CBC โดยสุ่ม IV ใหม่ทุกครั้ง แล้วแปะ IV ไว้หน้า ciphertext"""
    iv = os.urandom(16)
    return iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext, 16))


def aes_decrypt(key: bytes, blob: bytes) -> bytes:
    """ถอดรหัส: แยก IV (16 ไบต์แรก) ออกก่อน แล้ว unpad; ถ้าคีย์ผิด unpad จะ throw ValueError"""
    iv, ct = blob[:16], blob[16:]
    return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)


class PRP:
    """Enc(id) แบบ deterministic สำหรับ inverted index (AES-ECB หนึ่งบล็อก)
    ใช้ ECB ได้เพราะ input เป็นบล็อกเดียวและ id ไม่ซ้ำกัน"""

    def __init__(self, key: bytes):
        self._c = AES.new(key, AES.MODE_ECB)

    def enc_id(self, doc_id: int) -> bytes:
        return self._c.encrypt(doc_id.to_bytes(16, "big"))


# ---------------------------------------------------------------- Bloom
class BloomFilter:
    """Bloom filter: ตอบ "ไม่อยู่แน่นอน" ได้ 100% แต่ "อาจจะอยู่" มีโอกาส false positive
    -> SE-COLLAB Phase 8: เช็ค Bloom ก่อน ถ้าเจอค่อยถาม smart contract ให้ชัวร์"""

    def __init__(self, capacity: int = 10_000, error_rate: float = 1e-4):
        # สูตรมาตรฐาน: m = -n ln(p) / (ln2)^2 บิต, k = (m/n) ln2 hash functions
        m = math.ceil(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.m = max(8, m)
        self.k = max(1, round(self.m / capacity * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8)

    def _idx(self, item: bytes) -> Iterable[int]:
        # double hashing: สร้าง k ตำแหน่งจาก hash 2 ค่า (h1 + i*h2) แทนการใช้ k hash แยกกัน
        d = hashlib.sha256(item).digest()
        h1 = int.from_bytes(d[:8], "big")
        h2 = int.from_bytes(d[8:16], "big") | 1
        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def add(self, item: bytes) -> None:
        for i in self._idx(item):
            self.bits[i >> 3] |= 1 << (i & 7)       # set บิตที่ i

    def __contains__(self, item: bytes) -> bool:
        # ต้องเป็น 1 ครบทุกตำแหน่งถึงจะ "อาจจะอยู่"
        return all(self.bits[i >> 3] & (1 << (i & 7)) for i in self._idx(item))


# ---------------------------------------------------------------- Merkle
# prefix แยก leaf กับ internal node (กัน second-preimage attack ที่เอา node ภายในมาแอบอ้างเป็น leaf)
LEAF, NODE = b"\x00", b"\x01"


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(LEAF + data).digest()


def node_hash(l: bytes, r: bytes) -> bytes:
    return hashlib.sha256(NODE + l + r).digest()


class MerkleTree:
    """
    Merkle tree เก็บแบบ list ของแต่ละชั้น: levels[0] = leaves, levels[-1] = [root]
    ถ้าชั้นไหนมีจำนวน node เป็นเลขคี่ ตัวสุดท้ายจะ hash กับตัวเอง
    รองรับ:
      - update_leaf : อัปเดต leaf เดียวแล้วคำนวณใหม่เฉพาะ branch ที่โดน (SE-COLLAB Phase 6 Step 1)
      - proof       : authentication path ของ leaf เดียว (log n ค่า)
      - multiproof  : proof รวมหลาย leaf ที่แชร์ node ร่วมกัน (ขนาดเล็กกว่าเมื่อ leaf อยู่ใกล้กัน)
    """

    def __init__(self, leaf_data: Sequence[bytes] = (), prehashed: bool = False):
        leaves = list(leaf_data) if prehashed else [leaf_hash(d) for d in leaf_data]
        self.levels: List[List[bytes]] = [leaves]
        self._build()

    def _build(self) -> None:
        """สร้างทุกชั้นจาก leaves ขึ้นไปจนถึง root"""
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
            return hashlib.sha256(b"EMPTY").digest()   # root ของต้นไม้ว่าง
        return self.levels[-1][0]

    def __len__(self) -> int:
        return len(self.levels[0])

    # ---- incremental update: ใช้แค่ O(log n) hash
    def update_leaf(self, idx: int, data: bytes) -> bytes:
        """เปลี่ยน leaf ที่ idx แล้วไล่คำนวณ parent ขึ้นไปทีละชั้นจนถึง root"""
        self.levels[0][idx] = leaf_hash(data)
        for lv in range(len(self.levels) - 1):
            cur = self.levels[lv]
            p = idx // 2                                   # ตำแหน่ง parent
            l = cur[2 * p]
            r = cur[2 * p + 1] if 2 * p + 1 < len(cur) else l
            self.levels[lv + 1][p] = node_hash(l, r)
            idx = p
        return self.root

    # ---- proofs
    def proof(self, idx: int) -> List[Tuple[bool, bytes]]:
        """Authentication path: list ของ (sibling อยู่ขวาไหม, hash ของ sibling) ไล่จาก leaf ถึงใต้ root"""
        path = []
        for lv in range(len(self.levels) - 1):
            cur = self.levels[lv]
            sib = idx ^ 1                                  # พี่น้อง = flip บิตสุดท้าย
            sib_h = cur[sib] if sib < len(cur) else cur[idx]
            path.append((sib > idx or sib >= len(cur), sib_h))
            idx //= 2
        return path

    def multiproof(self, idxs: Iterable[int]) -> Dict[Tuple[int, int], bytes]:
        """Multiproof: เก็บเฉพาะ sibling ที่ผู้ตรวจคำนวณเองไม่ได้ {(ชั้น, ตำแหน่ง): hash}
        ถ้า leaf สองตัวเป็นพี่น้องกันเอง ก็ไม่ต้องส่ง sibling -> proof เล็กลง"""
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
    """ฝั่ง DU: เอา leaf hash + path มาคำนวณย้อนขึ้นไป แล้วเทียบกับ root (ที่ดึงจาก blockchain)
    ใช้ idx (ตำแหน่ง) ตัดสินซ้าย/ขวา -> ผูกตำแหน่งของ leaf ไว้ด้วย"""
    h = leaf_h
    for sib_right, sib in path:
        h = node_hash(h, sib) if (idx % 2 == 0) else node_hash(sib, h)
        idx //= 2
    return h == root


def verify_multiproof(leaves: Dict[int, bytes], n_leaves: int,
                      proof: Dict[Tuple[int, int], bytes], root: bytes) -> bool:
    """ตรวจ multiproof: leaves = {ตำแหน่ง: leaf_hash}
    คำนวณขึ้นทีละชั้น ใช้ค่าที่คำนวณเองได้ก่อน ถ้าไม่มีค่อยดึงจาก proof; ขาดตัวไหน = ไม่ผ่าน"""
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
                r = l                                   # node คี่ตัวท้าย hash กับตัวเอง
            if l is None or r is None:
                return False
            nxt[p] = node_hash(l, r)
        cur = nxt
        width = (width + 1) // 2
        lv += 1
    return cur.get(0) == root


# ============================================================================
# 2) Boolean query — แปลง AND/OR/NOT และประเมินบน BPL
# ============================================================================

AST = Union[Tuple[str, str], Tuple[str, "AST"], Tuple[str, "AST", "AST"]]
_TOK = re.compile(r"\(|\)|\"[^\"]*\"|[^\s()]+")   # token = วงเล็บ, "วลีในเครื่องหมายคำพูด", หรือคำที่ไม่มีช่องว่าง/วงเล็บ
_OPS = ("AND", "OR", "NOT", "(", ")")


def bool_parse(expr: str) -> AST:
    """Recursive-descent parser: แต่ละฟังก์ชันย่อยคือกฎหนึ่งข้อของไวยากรณ์ข้างบน"""
    toks = _TOK.findall(expr)
    pos = 0

    def peek():
        # ดู token ถัดไปโดยไม่เลื่อน (แปลงเป็นตัวใหญ่ เพื่อให้ and/And/AND เหมือนกัน)
        return toks[pos].upper() if pos < len(toks) else None

    def take():
        nonlocal pos
        t = toks[pos]
        pos += 1
        return t

    def p_expr():                     # OR มี precedence ต่ำสุด -> อยู่ชั้นนอกสุด
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

    def p_factor():                   # NOT, วงเล็บ, หรือ keyword
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
        # [ASSUMPTION] ข้อ 11: คำที่อยู่ติดกัน (ไม่มี operator คั่น) = keyword วลีเดียว
        words = [take().strip('"')]
        while peek() is not None and peek() not in _OPS:
            words.append(take().strip('"'))
        return ("KW", " ".join(" ".join(words).split()).lower())   # normalize ช่องว่าง + ตัวเล็ก

    ast = p_expr()
    if pos != len(toks):
        raise ValueError("trailing tokens")
    return ast


def bool_keywords(ast: AST) -> List[str]:
    """ดึง keyword ทั้งหมดที่ไม่ซ้ำกันใน AST (เรียงตามลำดับที่พบ) = W_q ในเปเปอร์"""
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
    """แทน leaf ทุกตัวด้วย f(keyword) โดยคงโครงสร้าง Boolean ไว้
    ใช้ตอน DU แปลง keyword ธรรมดา -> PRF token  ('KW','pump') -> ('KW', PRF(K,'pump'))"""
    if ast[0] == "KW":
        return ("KW", f(ast[1]))
    return (ast[0],) + tuple(bool_map_leaves(c, f) for c in ast[1:])


def bool_canonical(ast: AST) -> str:
    """แปลง AST เป็น string รูปแบบเดียวที่ไม่กำกวม เช่น AND(<hex>,OR(<hex>,<hex>))
    ใช้ hash เป็น H(W_q, B_q) และส่งไปใน C2 ของ trapdoor"""
    if ast[0] == "KW":
        v = ast[1]
        return v.hex() if isinstance(v, bytes) else str(v)
    if ast[0] == "NOT":
        return f"NOT({bool_canonical(ast[1])})"
    return f"{ast[0]}({bool_canonical(ast[1])},{bool_canonical(ast[2])})"


def bool_eval(ast: AST, bpl: Dict[object, int], universe_mask: int) -> int:
    """ประเมิน query บน BPL (bit vector เก็บเป็น Python int; บิตที่ i = เอกสาร i)
      AND -> bitwise &,  OR -> bitwise |,  NOT -> universe_mask & ~x
    keyword ที่ไม่อยู่ใน index -> vector ศูนย์ทั้งหมด"""
    op = ast[0]
    if op == "KW":
        return bpl.get(ast[1], 0)
    if op == "NOT":
        # ต้อง & กับ mask ของจำนวนเอกสารจริง ไม่งั้น ~ ใน Python จะได้เลขติดลบ (บิตไม่จำกัด)
        return universe_mask & ~bool_eval(ast[1], bpl, universe_mask)
    a = bool_eval(ast[1], bpl, universe_mask)
    b = bool_eval(ast[2], bpl, universe_mask)
    return a & b if op == "AND" else a | b


def bool_eval_sets(ast: AST, sets: Dict[object, set], universe: set) -> set:
    """ตัวประเมินแบบ set ธรรมดา (reference) ใช้ใน selftest เพื่อเช็คว่า bool_eval ให้ผลถูกต้อง"""
    op = ast[0]
    if op == "KW":
        return set(sets.get(ast[1], set()))
    if op == "NOT":
        return universe - bool_eval_sets(ast[1], sets, universe)
    a, b = bool_eval_sets(ast[1], sets, universe), bool_eval_sets(ast[2], sets, universe)
    return a & b if op == "AND" else a | b


# ============================================================================
# 3) Blockchain จำลอง — anchor root, revocation contract  ([ASSUMPTION] ข้อ 7)
# ============================================================================

@dataclass
class Block:
    height: int          # ลำดับบล็อก
    prev: bytes          # hash ของบล็อกก่อนหน้า (ทำให้แก้ย้อนหลังไม่ได้โดยไม่ถูกจับ)
    kind: str            # ประเภทธุรกรรม: ROOT / REVOKE
    payload: Tuple
    digest: bytes = b""


@dataclass
class Ledger:
    call_latency_s: float = 0.0
    chain: List[Block] = field(default_factory=list)
    # ----- state ของ contract -----
    merkle_roots: Dict[str, bytes] = field(default_factory=dict)       # DO id -> Merkle root ของข้อมูล
    index_roots: Dict[str, bytes] = field(default_factory=dict)        # DO id -> Merkle root ของ index
    revoked: Dict[bytes, Tuple[str, str, float]] = field(default_factory=dict)  # RT_k -> (du, domain, t)
    revoked_users: Dict[str, bytes] = field(default_factory=dict)      # du id -> RT_k
    query_log: List[Tuple] = field(default_factory=list)

    def _append(self, kind: str, payload: Tuple) -> Block:
        """เพิ่มบล็อกใหม่ต่อท้าย chain; digest = H(prev || kind || payload)"""
        if self.call_latency_s:
            time.sleep(self.call_latency_s)       # จำลองความหน่วงของ blockchain
        prev = self.chain[-1].digest if self.chain else b"\x00" * 32
        b = Block(len(self.chain), prev, kind, payload)
        b.digest = H(prev, kind.encode(), repr(payload).encode(), tag=b"BLOCK")
        self.chain.append(b)
        return b

    # ---- anchor root เพื่อตรวจ integrity (Phase 3 Step 5 / Phase 6 Step 1)
    def anchor_roots(self, do_id: str, data_root: bytes, index_root: Optional[bytes] = None):
        """DO เอา Merkle root ไปเก็บบน chain -> DU ใช้เป็นค่าอ้างอิงที่ cloud ปลอมไม่ได้"""
        self.merkle_roots[do_id] = data_root
        if index_root is not None:
            self.index_roots[do_id] = index_root
        self._append("ROOT", (do_id, data_root.hex(), index_root.hex() if index_root else None))

    def get_root(self, do_id: str) -> bytes:
        """DU อ่าน root จาก chain ตอนตรวจผลลัพธ์ (Phase 6 Step 2.3)"""
        if self.call_latency_s:
            time.sleep(self.call_latency_s)
        return self.merkle_roots[do_id]

    # ---- Federated revocation contract (Phase 8)
    def submit_revocation(self, du_id: str, domain: str, t: float) -> bytes:
        """สร้าง revocation token  RT_k = H(DU_revoked || T_revoke || Domain_k)  แล้วบันทึกบน chain"""
        rt = H(du_id.encode(), repr(t).encode(), domain.encode(), tag=b"RT")
        self.revoked[rt] = (du_id, domain, t)
        self.revoked_users[du_id] = rt
        self._append("REVOKE", (du_id, domain, t, rt.hex()))
        return rt

    def is_revoked(self, du_id: str) -> bool:
        """เช็คแบบแม่นยำ (global) — ถูกเรียกเฉพาะตอน Bloom filter บอกว่า "อาจจะ" ถูก revoke"""
        if self.call_latency_s:
            time.sleep(self.call_latency_s)
        return du_id in self.revoked_users

    # ---- บันทึกการค้นหา (Algorithm 2 บรรทัด 27: LogSearchExecution)
    def log_search(self, du_id: str, query_digest: bytes, n_results: int):
        self.query_log.append((du_id, query_digest.hex(), n_results))


# ============================================================================
# 4) Scheme — AA / DO / DU / Cloud Proxy / Cloud Storage (Phase 1-8)
# ============================================================================

# ============================================================================
# helpers
# ============================================================================
class Timer:
    """ตัวจับเวลาแบบสะสม: ใช้  with T("ชื่อขั้นตอน"): ...  แล้วอ่านผลจาก T.ms["ชื่อขั้นตอน"] (มิลลิวินาที)
    เรียกชื่อเดิมซ้ำได้ เวลาจะถูกบวกเพิ่ม"""

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
    """ConvertToBitwise (Algorithm 2 บรรทัด 12): แปลง posting list (ตำแหน่งเอกสาร)
    -> BPL bit vector เก็บเป็น Python int (บิตที่ i = 1 ถ้าเอกสาร i มี keyword นี้)"""
    if len(positions) < 48:
        # posting สั้น: วนลูป set บิตตรง ๆ เร็วกว่าสร้าง array ขนาด n
        v = 0
        for p in positions.tolist():
            v |= 1 << p
        return v
    # posting ยาว: ใช้ numpy สร้าง bool array แล้ว pack เป็น bytes (little-endian ให้บิต i ตรงตำแหน่ง i)
    b = np.zeros(n, dtype=bool)
    b[positions] = True
    return int.from_bytes(np.packbits(b, bitorder="little").tobytes(), "little")


def bitset_positions(v: int, n: int) -> np.ndarray:
    """แปลงกลับ: bit vector -> list ตำแหน่งเอกสารที่บิตเป็น 1 (= Matching_DocIDs)"""
    if v == 0:
        return np.empty(0, dtype=np.int64)
    raw = np.frombuffer(v.to_bytes((n + 7) // 8, "little"), dtype=np.uint8)
    return np.flatnonzero(np.unpackbits(raw, bitorder="little")[:n])


# regex จับชื่อ attribute ใน policy (ยกเว้นคำว่า and/or)
_ATTR = re.compile(r"\b(?!and\b|or\b|AND\b|OR\b)([A-Za-z][A-Za-z0-9]*)\b")


def versioned_policy(policy: str, versions: Dict[str, int]) -> str:
    """ใส่เลขเวอร์ชันให้ attribute ใน policy เช่น "(auditor or engineer)" -> "(AUDITORV2 or ENGINEERV1)"
    ใช้ตอน revocation: bump เวอร์ชัน attribute ที่โดน -> คีย์เก่าของคนถูก revoke ใช้กับ CT_key ใหม่ไม่ได้"""
    return _ATTR.sub(lambda m: f"{m.group(1).upper()}V{versions.get(m.group(1).upper(), 1)}", policy)


# ============================================================================
# Phase 1/2: Attribute Authority
# ============================================================================
class AttributeAuthority:
    """AA_k: ออก attribute key ให้ DU และถือ master key ของ CP-ABE
    (ระบบมีได้หลาย AA = multi-authority แต่ละ AA ดูแลโดเมนของตัวเอง)
    [ASSUMPTION] ข้อ 9: BSW07 เป็น single-authority ต่อ ciphertext -> DO 1 รายผูกกับ AA 1 ตัว"""

    def __init__(self, aa_id: str, group: PairingGroup):
        self.id, self.group = aa_id, group
        self.cpabe = CPabe_BSW07(group)
        # Phase 1: CreateAttributeAuthority -> PK = {g, h=g^β, f=g^(1/β), e(g,g)^α},  MK = (β, g^α)
        self.pk, self.mk = self.cpabe.setup()
        self.attr_version: Dict[str, int] = defaultdict(lambda: 1)   # เวอร์ชันของแต่ละ attribute (ใช้ตอน revoke)
        self.users: Dict[str, List[str]] = {}            # du_id -> รายชื่อ attribute ที่ถือ

    def _vattrs(self, attrs: Iterable[str]) -> List[str]:
        return [f"{a.upper()}V{self.attr_version[a.upper()]}" for a in attrs]

    def attribute_keygen(self, du_id: str, attrs: List[str]):
        """Phase 2 Step 1: AttributeKeygen(PK_k, S_A) -> SK_DU
        คืนค่า 3 อย่าง:
          sk_abe : CP-ABE secret key ผูกกับ attribute (ใช้ถอด CT_key ได้ถ้า attribute ตรง policy)
          s_u    : secret ของ DU สำหรับสร้าง trapdoor/ลายเซ็น  [FIX] ข้อ 2 (paper ใช้ g^α ซึ่ง DU ไม่มี)
          PK_DU  : g^{s_u} ให้ proxy ใช้ตรวจลายเซ็นและ NIZK"""
        self.users[du_id] = [a.upper() for a in attrs]
        sk_abe = self.cpabe.keygen(self.pk, self.mk, self._vattrs(attrs))
        s_u = self.group.random(ZR)
        return sk_abe, s_u, self.pk["g"] ** s_u


# ============================================================================
# Phase 3: โครงสร้างข้อมูลที่เก็บบน cloud
# ============================================================================
@dataclass
class EncryptedDataset:
    do_id: str
    n: int                                 # จำนวนเอกสาร
    ciphertexts: List[bytes]               # C_i (AES)
    enc_ids: List[bytes]                   # Enc(id_i)
    postings: Dict[bytes, np.ndarray]      # I(w) -> ตำแหน่งเอกสาร (เรียงแล้ว) = inverted index
    bpl_dense: Dict[bytes, int]            # I(w) -> BPL bit vector (เฉพาะ keyword ที่เก็บแบบ dense)
    data_tree: MerkleTree                  # leaf = H(Enc(id) || C_i)  -> ใช้ตรวจผลลัพธ์ใน Phase 6
    index_tree: MerkleTree                 # leaf = H(I(w) || posting) -> root ถูก anchor แต่เปเปอร์ไม่ได้ใช้ตรวจ
    ct_key: dict                           # CP-ABE(K_wrap, P): ห่อคีย์ภายใต้ access policy
    wrapped_symk: bytes                    # AES_{K_wrap}(SymK_DO)
    policy: str                            # access policy P เช่น "(auditor or engineer)"
    aa_id: str                             # AA ที่ดูแล policy นี้
    universe_mask: int = 0                 # (1<<n)-1 ใช้กับ NOT


# ============================================================================
# Data Owner (+ Edge Proxy)
# ============================================================================
class DataOwner:
    """DO: เข้ารหัสข้อมูล IIoT, สร้าง index, anchor root ขึ้น chain"""

    def __init__(self, do_id: str, group: PairingGroup, aa: AttributeAuthority, policy: str):
        self.id, self.group, self.aa, self.policy = do_id, group, aa, policy
        g = aa.pk["g"]
        # Phase 2 Step 2: คีย์คู่ของ DO  SK_DO = x_DO,  PK_DO = g^{x_DO}
        self.x = group.random(ZR)
        self.pk = g ** self.x
        self.symk = os.urandom(32)                       # SymK_DO (คีย์ symmetric หลัก 256 บิต)
        self._derive()
        self.dataset: Optional[EncryptedDataset] = None

    def _derive(self):
        """แตก SymK_DO เป็นคีย์ย่อยตามหน้าที่ (ไม่ใช้คีย์เดียวกันกับหลายงาน)"""
        self.k_aes = H(self.symk, tag=b"AES")            # เข้ารหัสเอกสาร
        self.k_prf = H(self.symk, tag=b"PRF")            # สร้าง keyword token I(w)
        self.prp = PRP(H(self.symk, tag=b"PRP")[:16])    # เข้ารหัส doc id

    # Phase 2 Step 4: PRE key  PRE_{A->B} = PK_B^{x_A} = g^{x_A x_B}
    def rekeygen(self, pk_target):
        return pk_target ** self.x

    def _encapsulate(self, T: Timer):
        """Phase 3 Step 2: เข้ารหัส SymK ด้วย CP-ABE
        BSW07 เข้ารหัสได้แค่ element ใน GT จึงทำ hybrid: สุ่ม M ∈ GT -> K_wrap = H(M)
        แล้วเอา K_wrap ไป AES ห่อ SymK_DO อีกที (เวลา revoke เปลี่ยน K_wrap ได้โดยไม่ต้องแตะ C_i)"""
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
        Phase 3 ทั้งหมด.  docs = [(doc_id, plaintext, keywords)]

        dense_threshold: keyword ที่มี df >= threshold*n จะเก็บเป็น BPL bit vector ไว้ล่วงหน้า
        ส่วนที่เหลือเก็บเป็น posting list แล้วแปลงเป็น bit vector ตอน query (Algorithm 2 บรรทัด 12)
        None = ถ้า n <= 50k เก็บ dense ทั้งหมด (ตรงตามเปเปอร์); ถ้าใหญ่กว่านั้นใช้ threshold 1/64
        เหตุผล: N=10^6 แต่ละ bit vector ยาว 125KB × หลายหมื่น keyword จะกิน RAM หลาย GB
        [ASSUMPTION] ข้อ 10
        """
        T = Timer()
        n = len(docs)
        if dense_threshold is None:
            dense_threshold = 0.0 if n <= 50_000 else 1 / 64

        # ---- Step 1: เข้ารหัสเอกสาร  C_i = AES(SymK_DO, D_i)  (แปะ doc_id 8 ไบต์ไว้หน้า plaintext)
        with T("aes_encrypt"):
            cts = [aes_encrypt(self.k_aes, d.to_bytes(8, "big") + p) for d, p, _ in docs]
            enc_ids = [self.prp.enc_id(d) for d, _, _ in docs]
        # ---- Step 2: CT_key = CP-ABE_Encrypt(PK_k, SymK_DO, P)
        ct_key, wrapped = self._encapsulate(T)

        # ---- Step 3 + 4: inverted index  I(w) = PRF(SymK, w) -> {ตำแหน่งเอกสาร} และ BPL
        with T("index_build"):
            inv: Dict[bytes, List[int]] = defaultdict(list)
            tok_cache: Dict[str, bytes] = {}             # cache token ไม่ต้องคำนวณ PRF ซ้ำ
            for pos, (_, _, kws) in enumerate(docs):
                for w in set(kws):
                    t = tok_cache.get(w)
                    if t is None:
                        t = tok_cache[w] = prf(self.k_prf, w.lower().encode())
                    inv[t].append(pos)
            postings = {t: np.asarray(v, dtype=np.int64) for t, v in inv.items()}
            dense = {t: to_bitset(a, n) for t, a in postings.items()
                     if len(a) >= dense_threshold * n}
        # ---- Step 5: Merkle tree ของ index (H_root_index) + ของข้อมูล (ใช้ใน Phase 6)
        with T("merkle_build"):
            data_tree = MerkleTree([eid + ct for eid, ct in zip(enc_ids, cts)])
            index_tree = MerkleTree([t + postings[t].astype(">u4").tobytes() for t in sorted(postings)])

        self.dataset = EncryptedDataset(self.id, n, cts, enc_ids, postings, dense, data_tree,
                                        index_tree, ct_key, wrapped, self.policy, self.aa.id,
                                        (1 << n) - 1)
        # "index generation" ตามที่เปเปอร์วัดใน Fig. 2 = สร้าง index + Merkle (ไม่รวม AES/CP-ABE)
        T.ms["index_generation"] = T.ms["index_build"] + T.ms["merkle_build"]
        return self.dataset, dict(T.ms)


class EdgeProxy:
    """Edge Proxy (entity ที่ 4): อยู่ที่ IIoT gateway ทำงานเข้ารหัส/สร้าง index แทน DO
    แต่ยังอยู่ในโดเมนของ DO (คีย์ไม่ออกไปนอกโดเมน) — ในการจำลองนี้แค่เรียกงานของ DO ต่อ"""

    def __init__(self, owner: DataOwner):
        self.owner = owner

    def process(self, docs, **kw):
        return self.owner.outsource(docs, **kw)


# ============================================================================
# Schnorr signature (ใน G1)
# ============================================================================
def schnorr_sign(group, g, x, msg: bytes):
    """ลายเซ็น Schnorr: สุ่ม k, R = g^k, c = H(R || msg), z = k + c·x  -> σ = (R, z)"""
    k = group.random(ZR)
    R = g ** k
    c = group.hash(group.serialize(R) + msg, ZR)
    return R, k + c * x


def schnorr_verify(group, g, X, msg: bytes, sig) -> bool:
    """ตรวจ: g^z == R · X^c   (X = public key ของผู้เซ็น)"""
    R, z = sig
    c = group.hash(group.serialize(R) + msg, ZR)
    return g ** z == R * (X ** c)


# ============================================================================
# Data User
# ============================================================================
@dataclass
class Trapdoor:
    """Trapdoor Tq = (C1, C2, C3) + ลายเซ็น σ + NIZK π  (Phase 4 Step 1)"""
    du_id: str
    do_id: str
    aa_id: str
    C1: object           # g^r  (randomization factor)
    C2: bytes            # AES_{KDF(Z)}( H(W_q,B_q) || query แบบ canonical ที่ใช้ PRF token )
    C3: object           # PK_DU^r  (ส่วนของ public key ของ DU)
    bind: bytes          # H(e(C3, h_k)) -- ผูก trapdoor เข้ากับ authority k (pairing 1 ครั้ง)
    sigma: tuple = ()
    zkp: tuple = ()

    def digest(self, group) -> bytes:
        """hash ของ trapdoor ทั้งก้อน ใช้เป็นข้อความที่ถูกเซ็นและผูกกับ NIZK"""
        return H(self.du_id.encode(), self.do_id.encode(), group.serialize(self.C1),
                 self.C2, group.serialize(self.C3), self.bind, tag=b"TQ")


class DataUser:
    """DU: สร้าง trapdoor, ตรวจผลลัพธ์, ถอดรหัส"""

    def __init__(self, du_id: str, group: PairingGroup):
        self.id, self.group = du_id, group
        self.keys: Dict[str, dict] = {}        # aa_id -> {sk, s, PK, aa}  (ถือคีย์จากหลาย AA ได้)
        self.domain_keys: Dict[str, bytes] = {}   # cache SymK_DO ที่ถอดได้แล้ว

    def receive_keys(self, aa: AttributeAuthority, attrs: List[str]):
        sk, s, PK = aa.attribute_keygen(self.id, attrs)
        self.keys[aa.id] = {"sk": sk, "s": s, "PK": PK, "aa": aa}

    def unlock_domain(self, ds: EncryptedDataset) -> Optional[bytes]:
        """ใช้ CP-ABE ถอด CT_key เพื่อได้ SymK_DO (ต้องใช้ทั้งสร้าง PRF token และถอดรหัส)
        ถ้า attribute ไม่ตรง policy -> คืน None = ค้นหาข้อมูลของ DO นี้ไม่ได้
        (นี่คือจุดที่ fine-grained access control บังคับใช้กับการ "ค้นหา")"""
        if ds.do_id in self.domain_keys:
            return self.domain_keys[ds.do_id]
        k = self.keys.get(ds.aa_id)
        if not k:
            return None                     # ไม่มีคีย์จาก AA ที่ดูแล DO นี้
        aa = k["aa"]
        M = aa.cpabe.decrypt(aa.pk, k["sk"], ds.ct_key)
        if M is False or M is None:
            return None                     # attribute ไม่ผ่าน policy
        try:
            symk = aes_decrypt(H(self.group.serialize(M), tag=b"WRAP"), ds.wrapped_symk)
        except ValueError:
            return None
        self.domain_keys[ds.do_id] = symk
        return symk

    def gen_trapdoor(self, ds, query: str, pk_cloud,
                     with_proofs: bool = True) -> Tuple[Trapdoor, Dict[str, float]]:
        """Phase 4 Step 1: สร้าง trapdoor สำหรับ Boolean query
        ต้นทุน: exponentiation 3 ครั้ง + pairing 1 ครั้ง (คงที่ ไม่ขึ้นกับจำนวน keyword)
        บวก signature และ NIZK ถ้า with_proofs=True (จับเวลาแยก)
        ds = owner เดียว หรือ list ของ owner (cross-domain search): [ASSUMPTION] ข้อ 12 -> trapdoor ก้อนเดียว
        ที่มี token I(w) ของทุก owner ใน C2 (exp / pairing / signature / NIZK ครั้งเดียวต่อ query)"""
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
            ast = bool_parse(query)                                         # แปลง query -> AST (B_q)
            parts = []
            for symk in symks:                                              # keyword -> I(w) ของแต่ละ owner
                k_prf = H(symk, tag=b"PRF")
                parts.append(bool_canonical(bool_map_leaves(ast, lambda w: prf(k_prf, w.encode()))))
            canon = (parts[0] if not multi else
                     "\n".join(f"{d.do_id}\t{c}" for d, c in zip(dss, parts))).encode()
            hq = H(canon, tag=b"WQBQ")                                   # H(W_q, B_q)
            r = grp.random(ZR)
            C1 = g ** r                                                  # exp ครั้งที่ 1
            C3 = k["PK"] ** r                                            # exp ครั้งที่ 2
            Z = pk_cloud ** r                                            # exp ครั้งที่ 3: คีย์ DH กับ proxy
            bind = H(grp.serialize(pair(C3, aa.pk["h"])), tag=b"BIND")   # pairing ครั้งที่ 1
            # [FIX] ข้อ 2: C2 = เข้ารหัส query ด้วย KDF(Z) -> มีแต่ proxy (ที่รู้ x_cloud) ที่ถอดได้
            # [ASSUMPTION] ข้อ 3: payload คือ query แบบ canonical ที่ leaf เป็น PRF token
            C2 = aes_encrypt(H(grp.serialize(Z), tag=b"KDF"), hq + canon)
            do_id = dss[0].do_id if not multi else "MULTI:" + ",".join(d.do_id for d in dss)
            tq = Trapdoor(self.id, do_id, dss[0].aa_id, C1, C2, C3, bind)
        if with_proofs:
            d = tq.digest(grp)
            with T("signature"):                               # σ = Sign(SK_DU, Tq) กันปลอม trapdoor
                tq.sigma = schnorr_sign(grp, g, k["s"], d)     # [ASSUMPTION] ข้อ 4: paper ไม่ระบุ scheme -> Schnorr
            with T("zkp"):
                # [FIX] ข้อ 4: สมการ ZKP ใน paper ไม่สมดุล -> ใช้ DLEQ แทน
                # NIZK (Fiat-Shamir, Chaum-Pedersen DLEQ): พิสูจน์ว่า C1 กับ C3 ใช้ r ตัวเดียวกัน
                # คือ log_g(C1) = log_PK(C3) โดยไม่เปิดเผย r และผูกกับ H(W_q,B_q)
                t = grp.random(ZR)
                V1, V2 = g ** t, k["PK"] ** t                  # commitment
                delta = grp.hash(grp.serialize(V1) + grp.serialize(V2) + d + hq, ZR)   # challenge δ
                tq.zkp = (V1, V2, t - delta * r, hq)           # response z = t - δr
        return tq, dict(T.ms)

    # ---------------- Phase 6: ตรวจผลลัพธ์
    def verify(self, resp: "SearchResponse", ledger: Ledger, pk_cloud, g,
               check_result_proof: bool = True) -> Tuple[bool, Dict[str, float], List[int]]:
        """คืน (ผ่านไหม, เวลา, ตำแหน่งเอกสารที่ถูกแก้)
        ตรวจ 2 อย่าง: (1) Merkle path ของทุก ciphertext ที่ได้ เทียบกับ root บน blockchain
                     (2) result proof ของ proxy ว่าผลนี้มาจาก trapdoor นี้จริง
        ข้อสังเกต: ตรวจแค่ "ที่ได้มาถูกต้อง" ไม่ได้ตรวจ "ได้มาครบ" (ตามที่ paper เขียน; ดูหมายเหตุใน header)
        [ASSUMPTION] ข้อ 6: result proof ของ proxy = Schnorr (paper เขียนว่า ZKP แต่ไม่ระบุรายละเอียด)"""
        T, ok, bad = Timer(), True, []
        with T("fetch_root"):
            root = ledger.get_root(resp.do_id)
        with T("merkle_verify"):
            if resp.proof_mode == "multi":
                leaves = {pos: leaf_hash(eid + ct) for pos, eid, ct in resp.results}
                # ผลว่าง: ไม่มี ciphertext ให้ตรวจ -> ผ่าน เหมือนแบบ path ทีละตัว (เดิมคืน False เพราะไม่มี leaf)
                ok = verify_multiproof(leaves, resp.n_leaves, resp.proofs, root) if leaves else True
                if not ok:  # multiproof ระบุตัวที่ผิดไม่ได้ จึงมาร์กทั้งชุด
                    bad = [pos for pos, _, _ in resp.results]
            else:
                # แบบ path ทีละตัว: ระบุได้ชัดว่า ciphertext ตัวไหนถูกแก้ (tamper localisation)
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
        """cross-domain: Merkle proof ของแต่ละ owner กับ root ของ owner นั้นบน chain (Phase 6 Step 2)
        + result proof ของ proxy ครั้งเดียวกับผลรวม R (Phase 6 Step 3: Verify(pi, T'q, R))"""
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

    # ---------------- Phase 7: ถอดรหัส
    def decrypt(self, ds: EncryptedDataset, resp: "SearchResponse") -> Tuple[List[Tuple[int, bytes]], Dict[str, float]]:
        """Step 1: CP-ABE ถอด CT_key -> SymK_DO,  Step 2: AES ถอด C_i -> D_i"""
        T = Timer()
        with T("cpabe_decrypt"):
            self.domain_keys.pop(ds.do_id, None)     # ล้าง cache เพื่อวัดเวลา CP-ABE จริง
            symk = self.unlock_domain(ds)
        if symk is None:
            raise PermissionError("CP-ABE decryption failed")
        k_aes = H(symk, tag=b"AES")
        out = []
        with T("aes_decrypt"):
            for _, _, ct in resp.results:
                pt = aes_decrypt(k_aes, ct)
                out.append((int.from_bytes(pt[:8], "big"), pt[8:]))   # (doc_id, เนื้อหา)
        return out, dict(T.ms)


# ============================================================================
# Cloud Proxy + Storage
# ============================================================================
@dataclass
class SearchResponse:
    """ผลลัพธ์ที่ proxy ส่งกลับให้ DU"""
    do_id: str
    tq_digest: bytes
    results: List[Tuple[int, bytes, bytes]]     # (ตำแหน่ง, Enc(id), C_i)
    proofs: object                              # Merkle path ต่อผลลัพธ์ หรือ multiproof
    n_leaves: int
    proof_mode: str                             # "paths" (ตามเปเปอร์) | "multi"
    result_sig: tuple = ()

    def result_digest(self) -> bytes:
        """hash ที่ผูก trapdoor กับชุดผลลัพธ์ทั้งหมด (proxy เซ็นค่านี้)"""
        return H(self.tq_digest, *[p.to_bytes(8, "big") + e + H(c) for p, e, c in self.results],
                 tag=b"RES")

    def proof_size_bytes(self) -> int:
        """ขนาด proof: multiproof = 32 ไบต์ต่อ node; paths = 33 ไบต์ต่อ node (hash + บิตซ้าย/ขวา)"""
        if self.proof_mode == "multi":
            return 32 * len(self.proofs)
        return sum(33 * len(p) for p in self.proofs)


@dataclass
class MultiResponse:
    """cross-domain: ผลของแต่ละ owner + ลายเซ็นของ proxy ครั้งเดียวกับผลรวม"""
    responses: List[SearchResponse]
    result_sig: tuple = ()

    def result_digest(self) -> bytes:
        return H(*[r.result_digest() for r in self.responses], tag=b"MRES")


class CloudStorage:
    """Cloud Storage: เก็บ ciphertext, index, metadata ของแต่ละ DO"""

    def __init__(self):
        self.datasets: Dict[str, EncryptedDataset] = {}

    def store(self, ds: EncryptedDataset):
        self.datasets[ds.do_id] = ds


class CloudProxy:
    """Cloud Proxy: ตรวจ trapdoor, เช็ค revocation, ทำ PRE transform, ค้นหา, สร้าง proof"""

    def __init__(self, group: PairingGroup, g, ledger: Ledger, storage: CloudStorage,
                 bloom_capacity: int = 100_000):
        self.group, self.g, self.ledger, self.storage = group, g, ledger, storage
        # Phase 2 Step 3: คีย์คู่ของ proxy  SK_Cloud = x_Cloud,  PK_Cloud = g^{x_Cloud}
        self.x = group.random(ZR)
        self.pk = g ** self.x
        self.bloom = BloomFilter(bloom_capacity, 1e-4)           # รายชื่อ DU ที่ถูก revoke (เช็คเร็ว)
        self.pre_keys: Dict[str, object] = {}                    # do_id -> PRE_{DO->Cloud}
        self.du_registry: Dict[str, Tuple[str, object]] = {}     # (du_id, aa_id) -> PK_DU
        self.aa_pk: Dict[str, dict] = {}

    def register_user(self, du: DataUser):
        for aa_id, k in du.keys.items():
            self.du_registry[(du.id, aa_id)] = k["PK"]
            self.aa_pk[aa_id] = k["aa"].pk

    def revoked(self, du_id: str, T: Timer) -> bool:
        """Phase 8 Step 2: เช็ค 2 ชั้น
          1) Bloom filter (เร็ว, local) -> ถ้าไม่เจอ = ไม่ถูก revoke แน่นอน
          2) ถ้า Bloom บอกว่าเจอ ค่อย query smart contract (แม่นยำ, กัน false positive)"""
        with T("revocation_check"):
            if du_id.encode() not in self.bloom:
                return False
            return self.ledger.is_revoked(du_id)

    def admit_and_transform(self, tq: Trapdoor, T: Timer, check_proofs: bool = True):
        """Phase 4 Step 2 + 3: รับ trapdoor -> ตรวจทุกอย่าง -> transform ด้วย PRE"""
        grp, g = self.group, self.g
        if self.revoked(tq.du_id, T):
            raise PermissionError("revoked user")
        PK = self.du_registry.get((tq.du_id, tq.aa_id))
        if PK is None:
            raise PermissionError("unknown user")
        d = tq.digest(grp)
        if check_proofs:
            with T("verify_signature"):                  # ตรวจว่า DU เป็นคนสร้าง trapdoor จริง
                if not schnorr_verify(grp, g, PK, d, tq.sigma):
                    raise PermissionError("bad signature")
            with T("verify_zkp"):
                # ตรวจ NIZK: g^z · C1^δ == V1  และ  PK^z · C3^δ == V2
                V1, V2, z, hq_claim = tq.zkp
                delta = grp.hash(grp.serialize(V1) + grp.serialize(V2) + d + hq_claim, ZR)
                if g ** z * tq.C1 ** delta != V1 or PK ** z * tq.C3 ** delta != V2:
                    raise PermissionError("bad NIZK")
        # [FIX] ข้อ 13: paper (Phase 4 Step 2) ให้ proxy ตรวจแค่ signature + ZKP ไม่มี pairing ฝั่ง proxy
        #   (Table 4 มี P_e เฉพาะใน TrapGen) จึงไม่ตรวจ bind ด้วย pairing ซ้ำ; bind ยังถูกเซ็นอยู่ใน digest ของ Tq
        with T("transform"):                             # Algorithm 1: Trapdoor Transformation (PRE) [ASSUMPTION] ข้อ 5
            Z = tq.C1 ** self.x                          # Z = C1^{x_cloud} = PK_cloud^r (DH)
            payload = aes_decrypt(H(grp.serialize(Z), tag=b"KDF"), tq.C2)
            first = tq.do_id.split(":", 1)[1].split(",")[0] if tq.do_id.startswith("MULTI:") else tq.do_id
            rk = grp.hash(grp.serialize(self.pre_keys[first]), ZR)      # ReKey_Cloud จาก PRE key (1 exp ต่อ query)
            C3p = tq.C3 * (g ** rk)                                       # C3' = g^ReKey · C3
            # C2' = เข้ารหัส payload ใหม่ภายใต้คีย์ที่ผูกกับ C3' (รูปแบบที่ใช้กับโดเมนของ DO)
            C2p = aes_encrypt(H(grp.serialize(Z), grp.serialize(C3p), tag=b"KDF2"), payload)
            tq_p = (tq.C1, C2p, C3p, Z)                                   # T'q
        hq, canon = payload[:32], payload[32:]
        if check_proofs and hq != tq.zkp[3]:
            raise PermissionError("NIZK not bound to this query")       # NIZK ต้องเป็นของ query นี้
        if H(canon, tag=b"WQBQ") != hq:
            raise PermissionError("query hash mismatch")                # query ถูกแก้ระหว่างทาง
        return tq_p, d

    @staticmethod
    def _extract(tq_p, group) -> AST:
        """ExtractKeyword(T'q): ถอด C2' ได้ query (AST ที่ leaf เป็น PRF token)"""
        C1, C2p, C3p, Z = tq_p
        payload = aes_decrypt(H(group.serialize(Z), group.serialize(C3p), tag=b"KDF2"), C2p)
        return _parse_canonical(payload[32:].decode())

    def _payload(self, tq_p) -> str:
        """ExtractKeyword(T'q): ถอด C2' ได้ query แบบ canonical (leaf = PRF token)"""
        C1, C2p, C3p, Z = tq_p
        return aes_decrypt(H(self.group.serialize(Z), self.group.serialize(C3p), tag=b"KDF2"), C2p)[32:].decode()

    def _search_ds(self, ds, ast, d, proof_mode, T, tamper=None, tamper_pos=None, tamper_old=None):
        """Algorithm 2 บน index ของ owner เดียว + Merkle proof (ยังไม่เซ็น)
        tamper (จำลอง cloud ที่ประสงค์ร้าย ใช้ใน test เท่านั้น) กับเอกสารตำแหน่ง tamper_pos (None = ผลลัพธ์ตัวแรก):
          modify = flip 1 บิตใน ciphertext, omit = ตัดผลลัพธ์ทิ้ง, inject = ใส่เอกสารที่ไม่ตรง query
          (ciphertext จริงพร้อม Merkle path ที่ถูกต้อง), old_version = ส่ง ciphertext รุ่นเก่า tamper_old[pos]"""
        # Algorithm 2 บรรทัด 2-12: ดึง BPL ของแต่ละ keyword
        with T("bpl_retrieval"):
            bpl = {}
            for kw in bool_keywords(ast):
                if kw in ds.bpl_dense:
                    bpl[kw] = ds.bpl_dense[kw]
                elif kw in ds.postings:
                    bpl[kw] = to_bitset(ds.postings[kw], ds.n)      # ConvertToBitwise
        # บรรทัด 13: EvaluateBoolean ด้วย bitwise AND/OR/NOT
        with T("boolean_eval"):
            match = bool_eval(ast, bpl, ds.universe_mask) if bpl or _has_not(ast) else 0
            positions = bitset_positions(match, ds.n)
        # บรรทัด 17-22: ดึง ciphertext ของเอกสารที่ match
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
        """Phase 5: Algorithm 2 (Secure Search Execution) + สร้าง proof สำหรับ Phase 6 (owner เดียว)"""
        T = Timer()
        tq_p, d = self.admit_and_transform(tq, T, check_proofs)
        ds = self.storage.datasets[tq.do_id]
        with T("bpl_retrieval"):
            ast = _parse_canonical(self._payload(tq_p))
        resp = self._search_ds(ds, ast, d, proof_mode, T, tamper, tamper_pos, tamper_old)
        with T("proof_gen"):                                    # result signature ของ proxy
            resp.result_sig = schnorr_sign(self.group, self.g, self.x, resp.result_digest())
        self.ledger.log_search(tq.du_id, d, len(resp.results))  # บรรทัด 27: บันทึกลง chain
        # search_core = เวลาค้นหาล้วน ๆ (เทียบกับ Fig. 4/5 ของเปเปอร์)
        T.ms["search_core"] = T.ms["bpl_retrieval"] + T.ms["boolean_eval"] + T.ms["result_fetch"]
        return resp, dict(T.ms)

    def search_multi(self, tq: Trapdoor, proof_mode: str = "paths",
                     check_proofs: bool = True) -> Tuple["MultiResponse", Dict[str, float]]:
        """cross-domain search ด้วย trapdoor ก้อนเดียว: ตรวจ signature / NIZK และ transform (PRE) ครั้งเดียว
        แล้วค้น index ของแต่ละ owner (Algorithm 2) + Merkle proof ต่อ owner และเซ็นผลรวมครั้งเดียว
        [ASSUMPTION] ข้อ 12 (Phase 4 Step 1: DU รวมคีย์จากหลาย AA เป็น trapdoor เดียว; Tq ไม่มีส่วนที่ขึ้นกับ DO)"""
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
    """มี NOT ใน query ไหม (ถ้ามี ต่อให้ไม่เจอ keyword เลยก็อาจได้ผลลัพธ์ เช่น NOT x = ทุกเอกสาร)"""
    return ast[0] == "NOT" or (ast[0] in ("AND", "OR") and (_has_not(ast[1]) or _has_not(ast[2])))


def _parse_canonical(s: str) -> AST:
    """แปลงกลับจาก bool_canonical -> AST (leaf เป็น hex ของ token)"""
    pos = 0

    def node():
        nonlocal pos
        for op in ("AND(", "OR(", "NOT("):
            if s.startswith(op, pos):
                pos += len(op)
                if op == "NOT(":
                    a = node()
                    pos += 1           # ข้าม ')'
                    return ("NOT", a)
                a = node()
                pos += 1           # ข้าม ','
                b = node()
                pos += 1           # ข้าม ')'
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
    """ตัวช่วยต่อ entity ทั้งหมดเข้าด้วยกันสำหรับการทดลอง (ไม่ต้องเรียกทีละคลาสเอง)"""

    def __init__(self, curve: str = "SS512", ledger_latency_s: float = 0.0):
        self.group = PairingGroup(curve)            # [ASSUMPTION] ข้อ 1: paper ไม่ระบุ curve -> SS512
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
            # ทุก AA ใช้ pairing group เดียวกัน; proxy ใช้ generator ของ AA ตัวแรก
            self.proxy = CloudProxy(self.group, aa.pk["g"], self.ledger, self.storage)
        return aa

    def add_owner(self, do_id: str, aa_id: str, policy: str) -> DataOwner:
        do = DataOwner(do_id, self.group, self.aas[aa_id], policy)
        self.owners[do_id] = do
        return do

    def add_user(self, du_id: str, attrs_by_aa: Dict[str, List[str]]) -> DataUser:
        """attrs_by_aa เช่น {"AA_manu": ["auditor"], "AA_reg": ["regulator"]} = รับคีย์จากหลาย AA"""
        du = DataUser(du_id, self.group)
        for aa_id, attrs in attrs_by_aa.items():
            du.receive_keys(self.aas[aa_id], attrs)
        self.users[du_id] = du
        self.proxy.register_user(du)
        return du

    def outsource(self, do_id: str, docs, use_edge_proxy: bool = True, **kw):
        """Phase 3 + ส่ง PRE key ให้ proxy + เก็บข้อมูลบน cloud + anchor root ขึ้น chain"""
        do = self.owners[do_id]
        ds, t = (EdgeProxy(do).process(docs, **kw) if use_edge_proxy else do.outsource(docs, **kw))
        T = Timer()
        with T("rekeygen"):                          # วัดเวลา re-encryption key generation (เปเปอร์วัดด้วย)
            self.proxy.pre_keys[do_id] = do.rekeygen(self.proxy.pk)
        t.update(T.ms)
        self.storage.store(ds)
        self.ledger.anchor_roots(do_id, ds.data_tree.root, ds.index_tree.root)
        return ds, t

    # ---------------- Phase 8: User Revocation
    def revoke(self, du_id: str, aa_id: str) -> Dict[str, float]:
        T = Timer()
        aa = self.aas[aa_id]
        # Step 1: ส่ง revocation token ขึ้น smart contract + ใส่ใน Bloom filter
        with T("submit_revocation"):
            self.ledger.submit_revocation(du_id, aa_id, time.time())
            self.proxy.bloom.add(du_id.encode())
        affected = aa.users.get(du_id, [])
        # Step 4: อัปเดต attribute key เฉพาะ attribute ที่โดน และเฉพาะ user ที่ถือ attribute นั้น
        with T("attribute_key_update"):
            for a in affected:
                aa.attr_version[a] += 1              # bump เวอร์ชัน -> คีย์เก่าใช้กับ policy ใหม่ไม่ได้
            for uid, u in self.users.items():
                if uid == du_id or aa_id not in u.keys:
                    continue
                if set(aa.users[uid]) & set(affected):
                    sk = aa.cpabe.keygen(aa.pk, aa.mk, aa._vattrs(aa.users[uid]))
                    u.keys[aa_id]["sk"] = sk
                    u.domain_keys.clear()
        # Step 3: lazy re-encryption -> หมุน K_wrap และสร้าง CT_key ใหม่ (C_i ไม่ต้องเข้ารหัสใหม่)
        # [ASSUMPTION] ข้อ 8: CT_key มีชิ้นเดียวต่อ DO -> "lazy" = encapsulate ใหม่ครั้งเดียว
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
# 5) Workload — dataset กลางของ AMTP (amtp_dataset.py) + corpus สังเคราะห์สำหรับ demo/selftest
# ============================================================================

Doc = Tuple[int, bytes, List[str]]       # (ตำแหน่งเอกสาร, เนื้อหา plaintext, รายการ keyword)

HERE = os.path.dirname(os.path.abspath(__file__))  # โฟลเดอร์ของไฟล์นี้ (baselines/)
DEFAULT_QUERIES = os.path.join(HERE, "results", "exp1_queries.json")  # query กลางที่ทุก scheme replay (เหมือน Du)
sys.path.insert(0, HERE)                          # ให้ import amtp_dataset.py ที่อยู่ข้าง ๆ ได้


def dataset():
    """import amtp_dataset ตอนใช้งานจริง (demo / selftest จะได้รันได้โดยไม่ต้องมี dataset)"""
    import amtp_dataset                           # ตัวโหลด dataset กลาง
    return amtp_dataset                           # คืน module


def to_secollab(docs, data_dir=None) -> List[Doc]:
    """แปลง Doc ของ dataset -> (ตำแหน่ง, เนื้อหาไฟล์จริง, keywords) ที่ DataOwner.outsource ใช้
    ตำแหน่ง = ลำดับในรายการ (0..N-1) = บิตใน BPL และ leaf ใน data Merkle tree"""
    D = dataset()
    return [(i, D.read_bytes(d, data_dir), list(d.keywords)) for i, d in enumerate(docs)]


def synthetic_corpus(n_docs: int, vocab: int = 20_000, kw_per_doc: int = 10,
                     zipf_s: float = 1.1, payload_bytes: int = 256, seed: int = 7) -> List[Doc]:
    """สร้างเอกสาร n_docs ชิ้น แต่ละชิ้นมี keyword ~kw_per_doc ตัว สุ่มจาก vocab ตามการกระจาย Zipf
    ใช้กับ demo / selftest / paper / revocation เท่านั้น (การทดลอง exp1/exp2 ใช้ dataset กลาง)"""
    rng = np.random.default_rng(seed)
    ranks = np.arange(1, vocab + 1)
    p = 1.0 / ranks ** zipf_s                    # ความน่าจะเป็นแปรผกผันกับอันดับ^s
    p /= p.sum()
    words = [f"kw{i:05d}" for i in range(vocab)]
    draws = rng.choice(vocab, size=(n_docs, kw_per_doc * 2), p=p)   # สุ่มเผื่อ 2 เท่าเพราะจะตัดตัวซ้ำ
    docs: List[Doc] = []
    body = os.urandom(payload_bytes)             # เนื้อหาใช้ร่วมกันทุกเอกสาร (ประหยัด RAM; เนื้อหาไม่มีผลต่อการค้นหา)
    for i in range(n_docs):
        kws = list(dict.fromkeys(words[j] for j in draws[i]))[:kw_per_doc]   # ตัดตัวซ้ำ คงลำดับ
        docs.append((i, body, kws))
    return docs


def doc_freq(docs: Sequence[Doc]) -> Counter:
    """document frequency: keyword แต่ละตัวอยู่ในกี่เอกสาร"""
    c = Counter()
    for _, _, kws in docs:
        c.update(set(kws))
    return c


# ============================================================================
# 6) ตัวช่วยของ benchmark (รูปแบบผลลัพธ์เหมือน Chen: <ชื่อ>_ms, _ms_median, _ms_std)
# ============================================================================

class Writer:
    """สะสมผลแต่ละแถว พิมพ์ขึ้นจอ (ไม่แสดง std/median ให้อ่านง่าย) และเขียน CSV ตอน close()"""

    def __init__(self, name: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)       # สร้างโฟลเดอร์ผลลัพธ์
        self.path = os.path.join(out_dir, f"secollab_{name}.csv")  # ไฟล์ปลายทาง
        self.rows = []                            # แถวที่สะสมไว้

    def add(self, **row):
        self.rows.append(row)                     # เก็บแถว
        show = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()
                if not k.endswith("_std") and not k.endswith("_median")}  # ตัดคอลัมน์ที่ไม่ต้องโชว์
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


def summarize(samples, prefix: str = ""):
    """รวมผลหลายรอบ -> คอลัมน์ <ชื่อ>_ms (mean), <ชื่อ>_ms_median, <ชื่อ>_ms_std  (เหมือน Chen)"""
    out = {}                                      # ผลสรุป
    for k in samples[0]:                          # ทุก metric
        v = [s.get(k, 0.0) for s in samples]      # ค่าทุกรอบ
        out[f"{prefix}{k}_ms"] = st.mean(v)       # ค่าเฉลี่ย
        out[f"{prefix}{k}_ms_median"] = st.median(v)  # มัธยฐาน
        out[f"{prefix}{k}_ms_std"] = st.pstdev(v)  # ส่วนเบี่ยงเบนมาตรฐาน
    return out                                    # คืนผล


def setup(docs, curve="SS512", dense_threshold=None):
    """สร้างระบบมาตรฐานสำหรับการทดลอง: AA 1 ตัว, DO 1 ตัว, DU 1 คน (attribute = auditor)"""
    s = System(curve)
    s.add_authority("AA1")
    s.add_owner("DO1", "AA1", "(auditor or engineer)")
    t0 = time.perf_counter()
    ds, tim = s.outsource("DO1", docs, dense_threshold=dense_threshold)
    tim["outsource_wall"] = (time.perf_counter() - t0) * 1e3
    du = s.add_user("DU1", {"AA1": ["auditor"]})
    du.unlock_domain(ds)          # CP-ABE unlock ทำครั้งเดียว ไม่นับเป็นต้นทุนต่อ query
    return s, ds, du, tim


def print_setup(n, ds, tim):
    """แสดงข้อมูลของ setup"""
    print(f" N={n}: outsource={tim['outsource_wall'] / 1e3:.1f}s index={tim['index_generation']:.0f}ms "
          f"keywords={len(ds.postings)}", flush=True)


def run_query(s, ds, du, q, proof_mode="paths"):
    """query เต็มหนึ่งรอบ: DU สร้าง trapdoor -> proxy ค้นหา+สร้าง proof -> DU ตรวจผล
    คืน (เวลาแยกตามขั้น, ข้อมูลขนาด/ผลลัพธ์) ชื่อเวลาหลักเหมือน Chen แล้วตามด้วยขั้นย่อยของ SE-COLLAB"""
    t0 = time.perf_counter()
    tq, tq_t = du.gen_trapdoor(ds, q, s.proxy.pk)
    t1 = time.perf_counter()
    resp, srv = s.proxy.search(tq, proof_mode=proof_mode)
    t2 = time.perf_counter()
    ok, ver, _ = du.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)
    t3 = time.perf_counter()
    assert ok                     # ระหว่าง benchmark ผลต้องผ่านการตรวจเสมอ
    times = {
        "query_gen": (t1 - t0) * 1e3,             # trapdoor + signature + NIZK
        "server_total": (t2 - t1) * 1e3,          # ทุกอย่างที่ proxy ทำ (admission + transform + ค้นหา + proof)
        "verify_total": (t3 - t2) * 1e3,          # DU ตรวจผล (Phase 6)
        "end_to_end": (t3 - t0) * 1e3,            # รวมทุกขั้น (ไม่รวม network)
        "trapdoor": tq_t["trapdoor"],             # เฉพาะ Tq (3 exp + 1 pairing) = Fig. 3 ของ paper
        "admission": sum(srv.get(k, 0) for k in
                         ("revocation_check", "verify_signature", "verify_zkp")),
        "transform": srv["transform"],            # Algorithm 1
        "search_core": srv["search_core"],        # ค้นหาล้วน (Algorithm 2) = Fig. 4/5
        "bpl_retrieval": srv["bpl_retrieval"],    # ส่วนของ search_core (เขียนลง CSV เพื่อเทียบ search ไม่รวม fetch)
        "boolean_eval": srv["boolean_eval"],
        "result_fetch": srv["result_fetch"],
        "search_no_fetch": srv["bpl_retrieval"] + srv["boolean_eval"],   # search_core ไม่รวม result_fetch
        "proof_gen": srv["proof_gen"],
        "merkle_verify": ver["merkle_verify"],    # = Fig. 6
        "result_proof_verify": ver.get("result_proof_verify", 0.0),
    }
    proof_bytes = resp.proof_size_bytes()
    info = dict(rQ=len(resp.results), proof_bytes=proof_bytes,
                # response = (ตำแหน่ง 8B + Enc(id) + C_i) ทุกผลลัพธ์ + proof + ลายเซ็นของ proxy
                response_bytes=sum(8 + len(e) + len(c) for _, e, c in resp.results) + proof_bytes
                + 2 * len(s.group.serialize(s.proxy.pk)),
                ids={p for p, _, _ in resp.results})  # ผลลัพธ์ (ไว้เทียบกับ ground truth ไม่เขียนลง CSV)
    return times, info


def measure(s, ds, du, q, reps, warmup, proof_mode="paths"):
    """warm-up ก่อน แล้ววัดจริง reps รอบ ปิด garbage collector ระหว่างวัด (เหมือน Chen)"""
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
    """SE-COLLAB รองรับ AND / OR / NOT -> ทุกรูปแบบของ Exp.1"""
    return True


# ============================================================================
# 7) Experiments (ตาม AMTP Section V-B) + sanity check ของ paper SE-COLLAB
# ============================================================================
def suite_paper(args):
    """จำลองการตั้งค่าของ Fig. 2-6 ใน paper SE-COLLAB (sanity check, corpus สังเคราะห์)"""
    # Fig. 2: เวลาสร้าง index ตอนมีไฟล์ 10-40 ไฟล์ ขนาดไฟล์ละ 8 KB
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

    # Fig. 3/4: trapdoor และ search เทียบกับจำนวน keyword ใน query (25-200)
    print("[paper] Fig.3/4 trapdoor + search vs #query keywords (25-200, AND-chain)")
    w = Writer("paper_fig3_4", args.out)
    for k in (25, 50, 75, 100, 125, 150, 175, 200):
        # ใช้ AND ต่อกัน ผลลัพธ์จะน้อย -> กราฟสะท้อนต้นทุนต่อ keyword ไม่ใช่ต้นทุนจากจำนวนผลลัพธ์
        res, qi = measure(s, ds, du, " AND ".join(vocab[:k]), args.reps, args.warmup)
        qi.pop("ids")
        w.add(keywords=k, **qi, **res)
    w.close()

    # Fig. 5/6: search และ verification เทียบกับจำนวน ciphertext ที่คืนกลับ (5-40)
    print("[paper] Fig.5/6 search + verification vs #returned ciphertexts (5-40)")
    # corpus เฉพาะ: ฝัง keyword "r<k>" ให้อยู่ในเอกสารพอดี k ชิ้น -> คุมจำนวนผลลัพธ์ได้แน่นอน
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
    """AMTP Exp.1: วนทุกขนาด N x ทุก k_Q x query 4 รูปแบบ (SE-COLLAB รองรับทุกรูปแบบ)
    ค่าเริ่มต้น replay query กลาง results/exp1_queries.json (หรือไฟล์ที่ให้ใน --queries) เหมือน Du
    ถ้าไม่มีไฟล์ จึงสร้างด้วย amtp_dataset.make_queries (seed เดียวกัน = query เดียวกัน) แล้วบันทึกเป็นไฟล์กลาง
    -> ไม่เขียนทับไฟล์ query กลางที่มีอยู่แล้ว
    ทุก query ถูกเทียบกับ ground truth จาก plaintext index -> ผลต้องตรงเป๊ะ"""
    D = dataset()                                 # dataset กลาง
    path = args.queries or DEFAULT_QUERIES        # ไฟล์ query ที่จะ replay
    replay = None                                 # query ที่โหลดจากไฟล์
    if os.path.exists(path):                      # มีไฟล์ query กลาง
        with open(path, encoding="utf-8") as f:
            replay = json.load(f)                 # [{"N","kQ","shape","query",...}, ...]
        print(f"[queries] replay {os.path.relpath(path)} ({len(replay)} queries)")
    elif args.queries:                            # ระบุไฟล์มาแต่หาไม่เจอ
        raise SystemExit(f"ไม่พบไฟล์ query {path}")
    else:
        print("[queries] ไม่พบไฟล์ query กลาง -> สร้างด้วย amtp_dataset.make_queries (seed เดียวกัน = query เดียวกัน)")
    sizes = sorted({x["N"] for x in replay}) if replay else args.sizes  # ขนาดที่ต้องรัน
    print(f"[exp1] Boolean search scalability  sizes={sizes}")
    w = Writer("exp1_boolean_scalability", args.out)
    exported = []                                 # query ที่จะบันทึกออก
    for n in sizes:                               # ทุกขนาด database
        src = D.sample(n, args.domains, args.data)  # เอกสาร n ไฟล์ (ชุดเดียวกันทุก scheme)
        inv = D.inverted_index(src)               # plaintext index ไว้หา ground truth
        if replay:                                # ใช้ query จากไฟล์
            qs = [x for x in replay if x["N"] == n]
        else:                                     # สร้าง query เอง
            qs = [dict(N=n, **q) for q in D.make_queries(src, args.kq, args.queries_per_kq, args.seed)]
            exported += [dict(q, dataset=D.DATASET_TAG, seed=args.seed, domains=args.domains) for q in qs]
        s, ds, du, tim = setup(to_secollab(src, args.data), dense_threshold=args.dense_threshold)
        print_setup(n, ds, tim)
        universe = set(range(n))
        for q in qs:                              # ทุก query
            base = dict(N=n, kQ=q["kQ"], shape=q["shape"], domain=q.get("domain", ""))
            if not supports(q["shape"]):
                w.add(**base, status="N/A")
                continue
            ast = bool_parse(q["query"])
            res, qi = measure(s, ds, du, q["query"], args.reps, args.warmup)
            gt = bool_eval_sets(ast, inv, universe)  # คำตอบที่ถูกต้อง
            assert qi.pop("ids") == gt, f"ผลค้นหาไม่ตรง ground truth: {q['query']}"
            p_q = sum(len(inv.get(t, ())) for t in bool_keywords(ast))  # ผลรวม posting ของทุก keyword
            w.add(**base, status="ok", rQ=qi["rQ"], pQ=p_q, proof_bytes=qi["proof_bytes"],
                  response_bytes=qi["response_bytes"], **res)
        del s, ds, du, src, inv                   # คืน RAM ก่อนสร้าง N ถัดไป
        gc.collect()
    w.close()
    if exported:                                  # บันทึก query ที่สร้าง
        qpath = DEFAULT_QUERIES                   # ไฟล์ query กลาง (นอกโฟลเดอร์ secollab/)
        D.save_queries(qpath, exported)
        print(f"-> {os.path.relpath(qpath)}  (replay the identical workload in AMTP / other baselines)")


def suite_exp2(args):
    """AMTP Exp.2: proof/verification เทียบกับ r_Q บนเอกสารชุดเดียวกับทุก scheme
    (results/exp2_layouts.json: clustered / dispersed / partition_spread ฝัง keyword เดียวกันในไฟล์เดียวกัน)
    SE-COLLAB ไม่มี partition: clustered = leaf ติดกันใน data Merkle tree (แชร์ path กันเยอะ)
    และวัดทั้งแบบ proof ทีละ path (ตาม paper) และ multiproof"""
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
                assert qi["rQ"] == r                        # ต้องได้ผลพอดี r ไฟล์
                w.add(N=n, rQ=r, layout=name, proof_mode=mode, proof_bytes=qi["proof_bytes"],
                      response_bytes=qi["response_bytes"], **res)
    w.close()


def suite_exp5(args):
    """AMTP Exp.5 บน workload กลาง results/exp5_workload.json: D data owner (1 owner = 1 domain) บน proxy และ
    ledger เดียวกัน ตามรูปแบบหลาย DO ของ paper (แต่ละ owner anchor root ของตัวเอง) -> ไม่ต้องใช้ keyword ประจำ domain
    ค้นเฉพาะ owner เป้าหมาย (DO00 = groups[0]) ทุกรูปแบบ query
    update: SE-COLLAB ไม่มี dynamic update (ต้อง outsource ใหม่ทั้งชุด) -> แถว status=N/A
    owner ของ D หนึ่งเป็นชุดแรกของ D ถัดไป จึงเพิ่ม owner ต่อจากเดิม (ไม่ outsource ซ้ำ)
    และตรวจว่า root ของ owner เดิมบน ledger ไม่เปลี่ยนเมื่อเพิ่ม owner ใหม่"""
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
        before = dict(s.ledger.merkle_roots)                # root ของ owner เดิมก่อนเพิ่ม owner ใหม่
        t0 = time.perf_counter()
        for k in range(len(dss), nd):                       # owner ใหม่ของ D นี้
            s.add_owner(f"DO{k:02d}", "AA1", "(auditor or engineer)")
            dss.append(s.outsource(f"DO{k:02d}", to_secollab(groups[k], args.data),
                                   dense_threshold=args.dense_threshold)[0])
        if du is None:
            du = s.add_user("DU1", {"AA1": ["auditor"]})
            du.unlock_domain(dss[0])                        # ค้นเฉพาะ owner เป้าหมาย
        print(f" D={nd}: outsource {time.perf_counter() - t0:.1f}s", flush=True)
        assert all(s.ledger.merkle_roots[k] == v for k, v in before.items()), "root ของ owner เดิมเปลี่ยน"
        base = dict(scheme="SE-COLLAB[37]", deploy_model="per_owner", domains=nd, N_target=meta["per_domain"],
                    N_total=nd * meta["per_domain"])
        for q in queries:
            ast = bool_parse(q["query"])
            res, qi = measure(s, dss[0], du, q["query"], args.reps, args.warmup, args.proof_mode)
            assert qi.pop("ids") == bool_eval_sets(ast, inv, universe), f"ผลไม่ตรง ground truth: {q['query']}"
            w.add(**base, kQ=q["kQ"], q=q["q"], shape=q["shape"], op="query", status="ok", proof_mode=args.proof_mode,
                  rQ=qi["rQ"],
                  proof_bytes=qi["proof_bytes"], response_bytes=qi["response_bytes"], **res)
        w.add(**base, op="update_one_domain", update_kind="none", status="N/A")
    w.close()


def measure_fn(fn, reps, warmup):
    """เหมือน measure แต่รับฟังก์ชัน fn() -> (times, info) คืน (สรุปเวลา, info ทุกรอบที่วัด)"""
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


# ---------------- dataset-v4 suites (แผนของอาจารย์; ไฟล์กลางใน datasets/arxiv/data_v4/ ใช้ร่วมกับทุก scheme)
def suite_search1(args):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl ทุก domain ทุกขนาด files-per-domain
    ผลของทุก query ต้องเท่ากับ result_size ในไฟล์และ ground truth จาก plaintext"""
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
                    f"ผลไม่ตรง: {q['query_id']} n={n}"
                w.add(scheme="SE-COLLAB[37]", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", proof_mode=args.proof_mode, rQ=qi["rQ"], pQ=sum(len(inv.get(t, ())) for t in bool_keywords(ast)),
                      proof_bytes=qi["proof_bytes"], response_bytes=qi["response_bytes"], **res)
            del s, ds, du, src, inv
            gc.collect()
    w.close()


def suite_verify1(args):
    """Verification 1.1 (single domain): verify_keywords.csv แถว single_domain ที่ --fix ไฟล์ต่อ domain
    แกน x = ขนาดผลลัพธ์เป้าหมาย 10 / 100 / 1,000 / 10,000 (keyword จริง 5 ตัวต่อเป้าหมายต่อ domain)"""
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
    """query หนึ่งรอบที่ cloud โกงกับเอกสารตำแหน่ง pos แล้วจับเวลาเฉพาะ DU verify
    modify = แก้ ciphertext, hide = ตัดทิ้ง, inject = ใส่เอกสารที่ไม่ตรง query, old_version = ciphertext รุ่นเก่า old[pos]
    คืน ({verify_total}, {detected, localized}) detected = verify ไม่ผ่าน; localized = จำนวนเอกสารที่ DU ชี้ตัวได้
    (แบบ path ทีละตัวชี้ ciphertext ที่ไม่ตรง Merkle root ได้; multiproof ชี้ตัวไม่ได้ -> 0)"""
    tq, _ = du.gen_trapdoor(ds, q, s.proxy.pk)
    tamper = _CHEAT.get(kind) if pos else None
    resp, _ = s.proxy.search(tq, proof_mode=proof_mode, tamper=tamper, tamper_pos=pos, tamper_old=old)
    t0 = time.perf_counter()
    ok, _, bad = du.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)
    t1 = time.perf_counter()
    return {"verify_total": (t1 - t0) * 1e3}, {"detected": not ok, "localized": len(bad) if proof_mode == "paths" else 0}


def suite_tamper(args):
    """Verification 1.2 (single domain): tamper_sets.jsonl ต่อ domain: keyword (~2,000 ผลลัพธ์) ที่ files_per_domain
    cloud โกงกับเอกสาร t ตัวแรกของ tamper_order (modify / hide / old_version) หรือใส่เอกสาร t ตัวแรกของ
    amtp_dataset.inject_order ที่ไม่ตรง query (inject) วัดเวลา verify และนับว่าจับได้กี่รอบ / ชี้ตัวได้กี่ไฟล์
    check_mode: early = --proof-mode (multiproof: ตรวจทั้งก้อน ชี้ตัวไม่ได้), full = path ทีละตัว (ชี้ตัวได้)
    SE-COLLAB ตรวจ Merkle path ของ ciphertext ที่ได้รับ -> modify / old_version จับได้ แต่ไม่ตรวจความครบและไม่ตรวจว่า
    เอกสารตรง query -> hide / inject จับไม่ได้"""
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
            assert not any(i["detected"] for i in infos), "ผลที่ซื่อสัตย์ไม่ผ่าน verify"
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
    """1 owner = 1 domain บน proxy / ledger เดียวกัน DU คนเดียวผ่าน policy ของทุก owner (unlock ครั้งเดียวต่อ owner
    นอกการจับเวลา) คืน (System, [dataset ของแต่ละ owner], DU)"""
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
    """ค้นข้าม domain ด้วย trapdoor ก้อนเดียว ([ASSUMPTION] ข้อ 12): DU สร้าง trapdoor ครั้งเดียว -> proxy ตรวจ / transform
    ครั้งเดียวแล้วค้นทุก owner -> DU ตรวจ Merkle root ต่อ owner + ลายเซ็นผลรวมครั้งเดียว คืน (เวลา, ขนาด / ผลต่อ owner)"""
    t0 = time.perf_counter()
    tq, tq_t = du.gen_trapdoor(dss, q, s.proxy.pk)
    t1 = time.perf_counter()
    mresp, srv = s.proxy.search_multi(tq, proof_mode=proof_mode)
    t2 = time.perf_counter()
    ok, ver = du.verify_multi(mresp, s.ledger, s.proxy.pk, s.proxy.g)
    t3 = time.perf_counter()
    assert ok                     # ระหว่าง benchmark ผลต้องผ่านการตรวจเสมอ
    times = {
        "query_gen": (t1 - t0) * 1e3, "server_total": (t2 - t1) * 1e3, "verify_total": (t3 - t2) * 1e3,
        "end_to_end": (t3 - t0) * 1e3, "trapdoor": tq_t["trapdoor"],
        "admission": sum(srv.get(k, 0) for k in ("revocation_check", "verify_signature", "verify_zkp")),
        "transform": srv["transform"], "search_core": srv["search_core"], "proof_gen": srv["proof_gen"],
        "bpl_retrieval": srv["bpl_retrieval"], "boolean_eval": srv["boolean_eval"], "result_fetch": srv["result_fetch"],
        "search_no_fetch": srv["bpl_retrieval"] + srv["boolean_eval"],                  # search_core ไม่รวม result_fetch
        "merkle_verify": ver.get("merkle_verify", 0.0), "result_proof_verify": ver.get("result_proof_verify", 0.0),
    }
    proof = sum(r.proof_size_bytes() for r in mresp.responses)
    info = {"rQ": sum(len(r.results) for r in mresp.responses), "proof_bytes": proof,
            "response_bytes": sum(8 + len(e) + len(c) for r in mresp.responses for _, e, c in r.results) + proof
            + 2 * len(s.group.serialize(s.proxy.pk)),
            "rQ_per_domain": [len(r.results) for r in mresp.responses]}
    return times, info


def suite_xsearch(args):
    """Search 2.1 (multi domain): queries_boolean_multi.jsonl บน 4 domain (owner) domain ละ --fix ไฟล์
    ผลของแต่ละ domain ต้องเท่ากับ result_size_per_domain ในไฟล์"""
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
    """Verification 2.1 (multi domain): verify_keywords.csv แถว multi_domain ที่ --fix ไฟล์ต่อ domain บน 4 owner"""
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
    """Search 2.2 / Verification 2.2: ไฟล์ชุดเดียวกัน (--fix ต่อ domain ของ dataset ทั้ง 4) แบ่งใหม่เป็น D = 1..32 owner
    ตามหมวด arXiv (domain_groups.csv) ส่ง query ทุกตัวของ boolean_multi ไปทุก owner
    ผลรวมต้องเท่ากับผลรวมราย domain ในไฟล์ (กลุ่มแบ่งไฟล์ชุดเดียวกัน)"""
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
    """วัดต้นทุน revocation เมื่อจำนวน user ที่ถือ attribute เดียวกับคนถูก revoke เพิ่มขึ้น
    (คนพวกนี้ต้องได้คีย์ใหม่ใน Step 4)"""
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
            s.add_user("victim", {"AA1": ["auditor"]})      # คนที่จะถูก revoke
            samples.append(s.revoke("victim", "AA1"))
        w.add(users=users, **summarize(samples))
    w.close()


# ============================================================================
# 8) Demo — ตัวอย่างเล็ก ๆ ให้เห็นทุกขั้นตอน  (python3 se_collab_sim.py demo)
# ============================================================================

def run_demo(_args=None):
    print("== SE-COLLAB demo ==")
    s = System()
    s.add_authority("AA_manu")                                           # Phase 1: AA ของผู้ผลิต
    s.add_owner("factory", "AA_manu", "(auditor or engineer)")           # DO + access policy
    docs = synthetic_corpus(200, vocab=40, kw_per_doc=5, seed=1)
    ds, t = s.outsource("factory", docs)                                 # Phase 2-3
    print(f"[Phase 3] outsourced {ds.n} docs, {len(ds.postings)} keywords, "
          f"index {t['index_generation']:.2f} ms, Merkle root anchored on ledger")
    alice = s.add_user("alice", {"AA_manu": ["auditor"]})                # ผ่าน policy
    eve = s.add_user("eve", {"AA_manu": ["supplier"]})                   # ไม่ผ่าน policy
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
    bad, _ = s.proxy.search(tq, tamper="modify")                         # cloud โกง: แก้ ciphertext
    ok, _, pos = alice.verify(bad, s.ledger, s.proxy.pk, s.proxy.g, check_result_proof=False)
    print(f"[attack ] modified ciphertext -> verify = {ok}, tampered position = {pos}")
    om, _ = s.proxy.search(tq, tamper="omit")                            # cloud โกง: ตัดผลลัพธ์ทิ้ง
    ok, _, _ = alice.verify(om, s.ledger, s.proxy.pk, s.proxy.g)
    print(f"[attack ] omitted 1 result -> verify = {ok}  (SE-COLLAB ไม่ตรวจความครบ: gap ที่ AMTP ปิด)")
    s.revoke("alice", "AA_manu")                                         # Phase 8
    try:
        s.proxy.search(alice.gen_trapdoor(ds, q, s.proxy.pk)[0])
    except PermissionError as e:
        print(f"[Phase 8] after revocation alice rejected: {e}")


# ============================================================================
# 9) Selftest — ทดสอบความถูกต้อง  (python3 se_collab_sim.py selftest)
# ============================================================================

def _env():
    """ระบบตัวอย่าง: AA 2 ตัว, DO 1 ราย policy = (auditor or engineer)
    alice = auditor (ผ่าน policy), bob = engineer (ผ่าน), eve = supplier (ไม่ผ่าน)"""
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
    """คำตอบที่ถูกต้อง: ประเมิน query บน plaintext ด้วย set ธรรมดา (ใช้เป็นเฉลย)"""
    sets = {}
    for i, (_, _, kws) in enumerate(docs):
        for w in kws:
            sets.setdefault(w, set()).add(i)
    return bool_eval_sets(bool_parse(query), sets, set(range(len(docs))))


# ครอบคลุม: keyword เดี่ยว, AND, OR, nested ทั้งสองแบบ, NOT, และ keyword ที่ไม่มีใน index
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
    """ผลค้นหาบนข้อมูลเข้ารหัส ต้องตรงกับเฉลยบน plaintext + ตรวจผ่าน + ถอดรหัสได้ doc id ตรง"""
    s, ds, docs, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, q, s.proxy.pk)
    resp, _ = s.proxy.search(tq)
    assert {p for p, _, _ in resp.results} == _expected(docs, q)
    assert alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]
    plain, _ = alice.decrypt(ds, resp)
    assert sorted(d for d, _ in plain) == sorted(_expected(docs, q))


def t_multiproof_mode(env):
    """multiproof ต้องตรวจผ่าน และมีขนาดเล็กกว่า proof แบบทีละ path"""
    s, ds, docs, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001 OR kw00002", s.proxy.pk)
    resp, _ = s.proxy.search(tq, proof_mode="multi")
    assert alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]
    paths, _ = s.proxy.search(tq, proof_mode="paths")
    assert resp.proof_size_bytes() < paths.proof_size_bytes()


def t_trapdoor_size_constant(env):
    """trapdoor มีจำนวน group element เท่าเดิม ไม่ว่า query จะมี keyword 1 หรือ 20 ตัว"""
    s, ds, _, alice, *_ = env
    t1 = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)[0]
    t2 = alice.gen_trapdoor(ds, " AND ".join(f"kw{i:05d}" for i in range(20)), s.proxy.pk)[0]
    assert type(t1.C1) is type(t2.C1) and type(t1.C3) is type(t2.C3)


def t_tamper_detected(env):
    """cloud แก้ ciphertext 1 บิต -> DU ต้องจับได้ และระบุได้ว่าเป็นเอกสารตำแหน่งไหน"""
    s, ds, _, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    resp, _ = s.proxy.search(tq, tamper="modify")
    ok, _, bad = alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g, check_result_proof=False)
    assert not ok and bad == [resp.results[0][0]]


def t_omission_not_detected(env):
    """จุดอ่อนของ SE-COLLAB: ตรวจแค่ ciphertext ที่ได้รับ ไม่ได้ตรวจความครบ
    -> cloud แอบตัดผลลัพธ์ทิ้ง 1 ตัวก็ยังตรวจผ่าน (ช่องโหว่ที่ PAPC ของ AMTP ปิด)"""
    s, ds, _, alice, *_ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    full, _ = s.proxy.search(tq)
    resp, _ = s.proxy.search(tq, tamper="omit")
    assert len(resp.results) == len(full.results) - 1
    assert alice.verify(resp, s.ledger, s.proxy.pk, s.proxy.g)[0]


def t_unauthorised_user(env):
    """eve (supplier) ไม่ผ่าน policy -> ถอด CT_key ไม่ได้ -> สร้าง trapdoor ไม่ได้"""
    s, ds, _, _, _, eve = env
    try:
        eve.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    except PermissionError:
        return
    raise AssertionError("unauthorised user formed a trapdoor")


def t_forged_signature(env):
    """เอา trapdoor ของ alice มาแก้ชื่อเป็น bob -> ลายเซ็นไม่ตรง proxy ต้องปฏิเสธ"""
    s, ds, _, alice, _, _ = env
    tq, _ = alice.gen_trapdoor(ds, "kw00001", s.proxy.pk)
    tq.du_id = "bob"
    try:
        s.proxy.search(tq)
    except PermissionError:
        return
    raise AssertionError("forged trapdoor accepted")


def t_incremental_merkle(_env=None):
    """อัปเดต leaf แบบ incremental ต้องได้ root เท่ากับการสร้างต้นไม้ใหม่ทั้งต้น"""
    data = [bytes([i]) * 4 for i in range(37)]       # 37 = เลขคี่ ทดสอบกรณี node คี่ด้วย
    t = MerkleTree(data)
    data[13] = b"new!"
    t.update_leaf(13, data[13])
    assert t.root == MerkleTree(data).root


def t_phrase_keywords(_env=None):
    """keyword หลายคำแบบ dataset-v3 (ไม่มี/มีเครื่องหมายคำพูด) ต้องค้นเจอเป็น keyword เดียว"""
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
    """หลัง revoke mallory: ค้นหาไม่ได้, คีย์เก่าเปิด CT_key ใหม่ไม่ได้, alice ยังใช้งานได้"""
    s = System()
    s.add_authority("AA")
    s.add_owner("do", "AA", "(auditor or engineer)")
    ds, _ = s.outsource("do", synthetic_corpus(100, vocab=30, kw_per_doc=4))
    a = s.add_user("alice", {"AA": ["auditor"]})
    m = s.add_user("mallory", {"AA": ["auditor"]})
    s.proxy.search(m.gen_trapdoor(ds, "kw00001", s.proxy.pk)[0])     # ก่อน revoke ค้นหาได้
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
        except Exception as e:  # noqa: BLE001 - รายงานทุกความล้มเหลว
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")
    print(f"{passed}/{len(tests)} passed")
    if passed != len(tests):
        sys.exit(1)


# ============================================================================
# 10) main
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="SE-COLLAB [37] simulation")  # ตัวอ่าน argument
    ap.add_argument("mode", choices=["demo", "selftest", "paper", "exp1", "exp2", "exp5", "revocation", "all",
                                     "search1", "verify1", "tamper", "xsearch", "xverify", "xdomains"],
                    help="all = paper + exp1 + exp2 + revocation")  # โหมดที่จะรัน
    # ---- dataset กลาง (amtp_dataset.py) ----
    ap.add_argument("--data", default=None, help="โฟลเดอร์ dataset (ค่าเริ่มต้น <repo>/data/amtp_file_db_v4 หรือ AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="domain ที่ใช้")
    ap.add_argument("--seed", type=int, default=42, help="seed ของการสร้าง query (เท่ากับ seed ของ dataset)")
    # ---- ชื่อและค่าเริ่มต้นเหมือน chen_et_al_sim.py ----
    ap.add_argument("--reps", type=int, default=30, help="จำนวนรอบที่วัดจริง")
    ap.add_argument("--warmup", type=int, default=3, help="จำนวนรอบ warm-up (ไม่นับ)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000],
                    help="ขนาด N ของ exp1 (สูงสุด 500,000 = 4 domain x 125,000)")
    ap.add_argument("--kq", type=int, nargs="+", default=[1, 2, 4, 8, 16], help="จำนวน keyword ต่อ query")
    ap.add_argument("--queries-per-kq", type=int, default=1, help="จำนวน query ต่อ k_Q (exp1)")
    ap.add_argument("--queries", default=None,
                    help=f"ไฟล์ query JSON ที่จะ replay (ค่าเริ่มต้น {os.path.relpath(DEFAULT_QUERIES)})")
    ap.add_argument("--exp5-workload", default=os.path.join(HERE, "results", "exp5_workload.json"),
                    help="workload กลางของ exp5 (python3 amtp_dataset.py exp5)")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "secollab"), help="โฟลเดอร์ผลลัพธ์")
    # ---- เฉพาะ SE-COLLAB ----
    ap.add_argument("--dense-threshold", type=float, default=None,
                    help="สัดส่วน df ที่เก็บ BPL แบบ dense (0 = dense ทั้งหมด, ดู [ASSUMPTION] ข้อ 10)")
    # ---- tamper / xdomain (ค่าเริ่มต้นจาก amtp_dataset ใช้ร่วมกับ AMTP) ----
    Dm = dataset()
    ap.add_argument("--s-domains", nargs="+", default=list(Dm.DOMAINS), help="v4 single-domain suites: domain")
    ap.add_argument("--fpd", type=int, nargs="+", default=Dm.V4_SIZES, help="search1: จำนวนไฟล์ต่อ domain")
    ap.add_argument("--fix", type=int, default=Dm.V4_FIX, help="verify1 / xsearch / xverify / xdomains: ไฟล์ต่อ domain")
    ap.add_argument("--s1-kq", type=int, default=Dm.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--d-counts", type=int, nargs="+", default=Dm.D_COUNTS, help="xdomains: จำนวน domain")
    ap.add_argument("--max-queries", type=int, default=0, help="xdomains: ใช้ query n ตัวแรก (0 = ทั้งหมด)")
    ap.add_argument("--x-kq", type=int, nargs="+", default=None, help="xdomains: เฉพาะ kQ เหล่านี้ (ค่าเริ่มต้น ทุกค่า)")
    ap.add_argument("--shapes", nargs="+", default=None, choices=["AND", "OR", "AND_of_OR", "OR_of_AND"],
                    help="xdomains: เฉพาะรูป query เหล่านี้ (ค่าเริ่มต้น ทุกแบบ)")
    ap.add_argument("--tamper-kinds", nargs="+", default=Dm.TAMPER_KINDS, choices=Dm.TAMPER_KINDS)
    ap.add_argument("--proof-mode", choices=["paths", "multi"], default="paths",
                    help="v4 suites: แบบ proof (paths = Merkle path ทีละไฟล์ตาม Phase 6 ของ paper; "
                         "multi = multiproof ที่เราเพิ่มเอง ไม่อยู่ใน paper)")
    a = ap.parse_args()                           # อ่าน argument
    run = {"demo": run_demo, "selftest": run_selftest, "paper": suite_paper, "exp1": suite_exp1,
           "exp2": suite_exp2, "exp5": suite_exp5, "revocation": suite_revocation, "search1": suite_search1,
           "verify1": suite_verify1, "tamper": suite_tamper, "xsearch": suite_xsearch, "xverify": suite_xverify,
           "xdomains": suite_xdomains}  # ฟังก์ชันของแต่ละโหมด
    for name in (["paper", "exp1", "exp2", "revocation"] if a.mode == "all" else [a.mode]):
        run[name](a)                              # เรียกใช้


if __name__ == "__main__":
    main()
