# START HERE: งานรอบ paper (32) (ส่ง conference 19 พ.ย. 2026 21:00)

> **ถึง Claude ของ Prim:** อ่านไฟล์นี้ให้จบก่อนทำอะไร ไฟล์นี้สรุปทุกอย่างที่ต้องรู้ไว้ในที่เดียว
> คุณทำงานให้ **คน B (Prim)** ส่วนคน A คือเจ้าของงาน (ApiSom-o) ซึ่งทำงานกับ Claude อีกตัว
> ไฟล์รายละเอียดอยู่ท้ายไฟล์นี้ ให้เปิดอ่านเฉพาะตอนที่ต้องใช้
> ไฟล์นี้อัปเดตล่าสุด 18 พ.ย. 2026 ตอนดึก

## 1. งานนี้คืออะไร (สั้นๆ)

- **AMTP** คือ searchable encryption หลาย domain ที่ตรวจผลได้ผ่าน Merkle partitions, Search Tree และ ASPA proof
  root ของแต่ละ domain ถูก anchor ไว้บน Root Anchor
- อาจารย์สั่งให้ **ทำการทดลองใหม่ตาม paper `AMTP (32).pdf`** และใช้ **ของจริงทั้งหมด**:
  blockchain จริง, CP-ABE จริง, ABS จริง
- โค้ดหลักอยู่ที่ `amtp_code/amtp/` ส่วน benchmark อยู่ที่ `amtp_code/bench/` และ baseline (Chen, Du, SE-COLLAB) อยู่ที่ `baselines/`

## 2. สถานะตอนนี้

| ส่วน | สถานะ | อยู่ที่ไหน / ใช้ยังไง |
|---|---|---|
| Root Anchor = smart contract จริง | ✅ เสร็จ | `chain/RootAnchor.sol`, `amtp_code/amtp/chain_anchor.py`; env `AMTP_ANCHOR=chain-local` (EVM ในเครื่อง) หรือ `chain` (Sepolia ตาม `.env`) |
| σ_root = ECDSA ที่ contract ตรวจเอง | ✅ เสร็จ | contract เรียก `ecrecover`; ส่ง root ที่ผิดลำดับ ผิด epoch หรือลายเซ็นผิด → contract ไม่รับ |
| ทดสอบบน Sepolia แล้ว | ✅ | ส่ง root ~11.6 s, gas ~89k/tx, อ่าน root ~241–257 ms; 5 attack ถูกปฏิเสธ (`chain/runs/`) |
| CP-ABE จริง (BSW07, Charm, SS512) | ✅ เสร็จ | `AMTP_CPABE=bsw07` (`amtp/core/cpabe.py`) |
| **ABS จริง** สำหรับ σ_op (= σ_d) | ✅ เสร็จ (PR #55 ของ B, MPR บน Charm) | `AMTP_ABS=mpr AMTP_ABS_CURVE=SS512` (#54 C) อยู่ใน `paper32_env.sh` แล้ว |
| ex1 Search | 🟡 คน A ทำอยู่ | query set p32 (kQ 1/2/4/8/16) ✅, เวลาอ่าน root แยกเป็นคอลัมน์ `anchor_read` ✅, เหลือสคริปต์รัน |
| ex2 Verify / tamper / clustered-dispersed | ⏳ คน A | |
| ex3 update vs Chen, ex5 D = 1–32 | ⏳ คน A | **ต้องรอ ABS** (มี update ผ่าน protocol เต็ม); ex3 ต้องเพิ่มเวลา posting repair / auth-tree แยก, ex5 ต้องต่อ contract + delete + Du (ตามที่ (32) บอกให้วัด) |
| ex4 ablation | ⏳ คน A | 3 variant ที่ระดับ index (`bench/ablation.py`) ไม่ใช้ ABS + เส้น AMTP ผ่าน protocol เต็ม (ต้องรอ ABS) (#44 = A+) |
| รันบน AWS + กราฟ | ⏳ คน A | ex1, ex2 และ ex4 ส่วน 3 variant ปล่อยได้ก่อน เพราะไม่ใช้ ABS |
| Overleaf | ⏳ **B (B4, B5)** | ดูข้อ 6 |

**ABS กระทบอะไรบ้าง** (ตรวจในโค้ดแล้ว): ABS ใช้เฉพาะตอน **update** คือ DO เซ็นที่ `amtp/owner.py:94` และ
`bench/experiments.py:133,138` จากนั้น CS ตรวจที่ `amtp/server.py:86` และ DO ตรวจซ้ำที่ `amtp/validator.py:335`
ฝั่ง search และ verify ของ DU ไม่ใช้ ABS เลย (ตรวจด้วย Merkle proof + root ที่อ่านจาก contract)
ดังนั้นถ้า ABS ช้า จะกระทบแค่ ex3, ex5 และเส้น AMTP protocol เต็มของ ex4

## 3. สิ่งที่ตกลงกันแล้ว (ห้ามเปลี่ยนเอง ถ้าคิดว่าควรเปลี่ยนให้ถาม A ก่อน)

- dataset **arXiv v4 ที่มีอยู่จริงเท่านั้น** (ไม่ใช้ Enron, ไม่สร้างข้อมูลเพิ่มให้ถึง 10⁶: อาจารย์สั่ง) ขนาดของแต่ละ ex:

  | Exp | ขนาด |
  |---|---|
  | ex1 1.1 / ex2 1.1, 1.2 | 1 domain × 100k |
  | ex1 1.2 | 1 domain × 10k, 25k, 50k, 75k, 100k, 125k (kQ = 4) |
  | ex1 2.1, 2.2 / ex2 2.1, 2.2 | 4 domain × 100k = 400k (2.2 แบ่งกลุ่มใหม่เป็น D = 1–32) |
  | ex2 clustered / dispersed | **1 domain × 100k** (แทน N = 10⁶ ของ (32)) |
  | ex3 | 100k × b 1/10/100/1000 และ N 10k–125k ที่ b = 100 |
  | ex4 | เริ่ม 25k + insert 250 batch × 100 (→ 50k) แล้ว delete 65% ของกลุ่มร้อน; skew = **0, 0.25, 0.5, 0.75, 0.95**; **10 run** ต่อจุด (#45) |
  | ex5 | D = 1–32, ทุก domain 5k (สูงสุด 160k) |
- reps = 10 หลัง warm-up 3 · query default 4 keyword · θ_max 64 / θ_min 16
- AMTP เปิดตัวเร่งทั้งหมด (fill placement, AND pruning + greedy, result-only partition proofs, part leaf) และเอาคำอธิบาย LaTeX ใส่ลง (32)
- σ_root = **ECDSA** ที่ contract ตรวจ (ABS ตรวจบน chain ไม่ได้จริง: pairing แพงเกินไปสำหรับ gas และยังไม่มีงานไหนทำ)
- σ_op / σ_d = **ABS จริง** ตรวจนอก chain (CS + DO) ตามบทบาทใน (32)
- query อ่าน root จาก contract ทุกครั้ง; เวลาอ่าน (`anchor_read`) รายงานแยกจาก end-to-end
- update รายงาน protocol time แยกจาก anchor time + gas

**ตัดสินแล้ว 18 พ.ย. (issue #42–#45):**
- **#42 = A:** เวลา protocol ทุก ex วัดกับ contract บน EVM ในเครื่อง (`chain-local`: bytecode และ `ecrecover` ตัวเดียวกัน
  ไม่มีเวลารอ block มาปน); anchor time + gas + read latency วัดบน Sepolia เป็นชุดเล็กแยก (ex5 D = 1–32 ด้วย
  `chain/gas_domains.py` + บางจุดของ ex3) → **B3 ใช้บัญชี Sepolia บัญชีเดียว**
- **#43 = A:** ABS ใช้ policy เดียวกันทั้ง insert และ delete: `domain:Di AND role:owner` (upload policy = operation policy)
- **#44 = A+:** ex4 เทียบ AMTP / Static-MT / Global-MT(v) ที่ระดับ index (`bench/ablation.py`) **และ** เพิ่มเส้น AMTP ผ่าน
  protocol เต็ม (ABS + DO validator + anchor) ทุก skew เพื่อวัด split/merge overhead ใน protocol จริง
- **#45 = C:** ex4 รัน **10 run** ต่อจุด (variant × skew) ใช้ ~10 เครื่อง (ประมาณ ~5 ชม.)
- **หลัก: ยึด (32) ตามตัวอักษร ยกเว้นสิ่งที่ตกลงกันในรายการนี้** (เจ้าของงาน 18 พ.ย.)
- **#48 = A:** AAD ของไฟล์ = `Encode(i, id_d)` ตาม (32) (โค้ดแก้)
- **#49 = A:** U_d / U_ins ตาม (8) / (10) ไม่มี g_d; placement group เป็น input ของ CS ฝั่งเดียว (โค้ดแก้)
- **#50 = B:** epoch = batch ≤ b operation (b = 1 = (32)); แก้ paper ด้วย somo 1.3, 2.4–2.6
- **#54 = C:** ABS ใช้ curve **SS512** (curve เดียวกับ CP-ABE / SE-COLLAB; verify BN254 ~210 ms ช้าเกินสำหรับ ex4)
  `AMTP_ABS=mpr AMTP_ABS_CURVE=SS512` ใน `paper32_env.sh`; เวลา ABS รายงานแยกคอลัมน์ (`abs_sign`, `abs_verify_cs`, `abs_verify_do`);
  paper: ตาราง abs_costs ทั้ง 3 curve + ประโยคว่าใช้กรณี G = H ของ MPR (B ยืนยันจาก PDF ว่า proof ครอบคลุม)
- **#51 = B:** IMT แบบ indexed Merkle tree (next pointer); แก้ paper ด้วย somo 1.5, 2.1, 1.11 Step 1
- **#46 = B (ตาม setup ของ (32)):** ทุกค่าที่รายงานเป็น **mean** ของ 10 run หลัง warm-up 3 (*"averaged over 10 independent runs"*)
  กราฟใช้คอลัมน์ `_ms` (mean) ไม่ใช่ `_ms_median`; ex4 = mean ของ 10 run (แต่ละ run = mean ต่อ batch)
- **รวมข้าม query (เจ้าของงาน 19 พ.ย., ไม่ขัด (32)):** แต่ละ query = **mean ของ 10 run** (#46) แล้วแต่ละจุดบนกราฟที่มีหลาย query
  (ex1, ex2 verify ตาม rQ) = **median ของ query ในจุดนั้น** และ error bar = IQR (Q1–Q3) เหมือนกราฟรอบ (31) (`plot_paper.agg`)
  เหตุผล: query ที่มีผลมาก (เช่น AND-of-OR kQ 2 ที่ 12,933 records) ไม่ใช่ run ซ้ำของ query เดียวกัน; (32) กำหนดแค่การเฉลี่ยข้าม run
  ต้องเขียนใน setup (B4 ข้อ 8) และบอกตรงๆ ว่า query ที่ผลเกิน ~1,000 records AMTP search ช้ากว่า SE-COLLAB และ OR ล้วนแพ้ที่ kQ ≥ 4

## 4. งานของ B ทีละขั้น

### ตั้งเครื่อง (ครั้งเดียว)

```bash
git clone https://github.com/pperabha/NewAMTP.git && cd NewAMTP
git checkout feat/paper32-experiments
git checkout -b feat/real-abs
python3.12 -m venv .venv
.venv/bin/pip install -r chain/requirements.txt charm-crypto-framework==0.62   # Charm ต้องมี GMP + PBC (baselines/README.md)
.venv/bin/python datasets/arxiv/unpack.py
cd amtp_code && ../.venv/bin/python -m pytest -q                 # ต้องได้ 561 passed
AMTP_CPABE=bsw07 ../.venv/bin/python -m pytest -q                # ต้องได้ 561 passed
```

### B1 + B2: ABS จริง (ส่ง **02:00**, ตัดสินใจ go/no-go **03:00**)

1. scheme: **Maji–Prabhakaran–Rosulek, "Attribute-Based Signatures"** (IACR ePrint 2008/328)
   - เว็บ eprint บล็อกการดึงอัตโนมัติ (403) ให้ Prim เปิด https://eprint.iacr.org/2008/328.pdf ใน browser แล้วบันทึกไฟล์ให้ Claude อ่าน
   - **เขียนตามสูตรในเปเปอร์เท่านั้น ห้ามเขียนจากความจำ**
2. ไฟล์ใหม่ `amtp_code/amtp/core/abs.py` แบบเดียวกับ `amtp/core/cpabe.py`: ใช้ Charm curve **BN254** (asymmetric pairing
   ตามที่ MPR ต้องใช้; ตกลงแล้ว 18 พ.ย.; CP-ABE ยังใช้ SS512 เพราะเป็น primitive แยกกัน); แปลง policy AND/OR เป็น monotone span program
   **σ_d = σ_op ของคำขอ insert:** U_d (8) กับ U_ins (10) เป็น tuple เดียวกัน upload จึงเซ็น ABS ครั้งเดียว (ไม่ต้องแก้ `owner.py`, `server.py`, `validator.py`)
3. policy ต่อ domain: **`domain:Di AND role:owner` ตัวเดียวกันทั้ง insert และ delete (#43 = A)**; attribute ของ DO เช่น `{domain:D1, role:owner}`
4. ต่อเข้า `amtp/core/crypto.py` ผ่าน env **`AMTP_ABS`** (`ed25519` = ตัวเดิม ค่าเริ่มต้น, `mpr` = ABS จริง)
   ทำแบบเดียวกับ `make_authority()` ที่เลือก CP-ABE ตาม `AMTP_CPABE`
   - **interface ต้องเหมือนเดิม:** `Signer()`, `.public`, `.sign(msg)`, `sig_ok(public, msg, sig)` เพื่อไม่ต้องแก้ไฟล์ของ A
   - ถ้า ABS ต้องมี authority หรือ policy ส่งเข้ามาตอนสร้าง ให้ใส่ค่าเริ่มต้นไว้ใน `crypto.py` และบอก A ก่อนแก้ `bench/`
5. test ใหม่ `amtp_code/tests/test_abs.py` ต้องครอบคลุม:
   - เซ็นแล้วตรวจผ่าน
   - attribute ไม่ครบ → ไม่ผ่าน
   - ข้อความหรือลายเซ็นถูกแก้ → ไม่ผ่าน
   - **สองคนรวม key กัน (collusion) → ไม่ผ่าน**
   - key ของ domain อื่น → ไม่ผ่าน
   - Phase 1 → 5 ครบบน `scenario.World`
6. pytest ต้องผ่านทั้ง `AMTP_ABS=ed25519` และ `AMTP_ABS=mpr` (และคู่กับ `AMTP_CPABE=bsw07`)
7. วัดเวลาด้วย `amtp_code/bench/abs_bench.py` (แบบ `bench/cpabe_bench.py`) → `baselines/results/abs/abs_costs.csv`
   - วัด Setup, KeyGen, Sign, Verify และขนาดลายเซ็น ที่ policy 1, 2 และ 5 attribute
   - median 15 รอบหลัง warm-up 3
8. push `feat/real-abs` แล้ว **บอก A** (A จะ merge และเพิ่ม `AMTP_ABS=mpr` ใน `scripts/paper32_env.sh` เอง)

ถ้าตี 3 ยังไม่ผ่าน test: A จะรันการทดลองด้วยตัวเดิม (Ed25519) แล้ว B วัดเวลา ABS จริงแยกเป็นตาราง

### B3: Sepolia (ส่ง 02:00)

- **ใช้บัญชีเดียว (#42 = A)**: ไม่ต้องทำ `sepolia_fund.py` แล้ว
- เช็กว่ามี test ETH พอ (`chain/sepolia.py status`) สำหรับชุด Sepolia: `chain/gas_domains.py --max-d 32` (~64 tx) +
  บางจุดของ ex3 (~100 tx) ≈ 200 tx × ~110k gas; บอก A ถ้า ETH เหลือน้อย
- **ห้าม commit `.env` หรือ private key**; RPC ใส่ `.env` เป็น `AMTP_RPC=...`

### B4: Overleaf ส่วนที่ไม่ต้องรอผล (ส่ง **15:00**)

| # | ใน (32) ตอนนี้ | แก้เป็น |
|---|---|---|
| 1 | σ_root เซ็นด้วย ABS | ECDSA secp256k1 ที่ contract ตรวจ แก้ 6 จุด: Phase 1 Step 1, สมการ (29), Threat model + IV-A, Theorem 3 + proof, Table III/IV (T_ABS → T_Sig), ย่อหน้าหลัง Table IV |
| 2 | (32) ยังไม่มีการแก้ construction ชุด 17 พ.ย. | **ยึด (32) เป็นหลัก ยกเว้นสิ่งที่ตกลงกัน** วางจาก `docs/paper_latex_2026-11-17_somo.tex` **เฉพาะ**: 1.3 (epoch = batch, #50 B) · 1.4 (fill, comment) · 1.5 + 2.1 + 1.11 Step 1 (IMT แบบ indexed, #51 B) · 1.6 · 1.7–1.13 (ตัวเร่ง + part leaf) · 1.11 ที่เหลือ · 2.2 (leakage: คง "placement group" เพราะ CS ยังเห็น hint) · 2.3–2.8 (Proposition 1 / Theorem 1 รองรับ batch และตัวเร่ง; ใช้ ECDSA กับ σ_root) · 3.1–3.3 · 5.x · **ห้ามวาง 1.1 และ 1.2** (โค้ดแก้ให้ตรง (32) แล้ว: AAD = Encode(i, id_d) #48 A, U_d / U_ins ไม่มี g_d #49 A) · **ห้ามวาง 3.4 / 3.6 ตรงๆ** (ของรอบ (31)) |
| 3 | dataset Enron | arXiv (ใช้ย่อหน้า dataset ของ AMTP (31)) |
| 4 | N ∈ {10⁴, 5×10⁴, 10⁵, 5×10⁵, 10⁶} (Exp 1), 10⁴–10⁶ (Exp 3), N = 10⁶ (Exp 2) | Exp 1/3: 10k, 25k, 50k, 75k, 100k, 125k ต่อ domain; Exp 2: N = 100k; Exp 4: 25k → 50k, skew 0/0.25/0.5/0.75/0.95; Exp 5: 5k ต่อ domain; จำนวน domain [X] = 4 |
| 5 | Exp 4 ใช้ dataset เต็ม | 20% (25k + 250 batch × 100) × 5 ระดับ skew |
| 6 | **ใหม่** ยังไม่บอกว่าวัดบน network ไหน | เพิ่มใน setup: *Protocol costs are measured against the same RootAnchor contract deployed on a local EVM; on-chain anchoring latency, read latency and gas are measured separately on Ethereum Sepolia and reported apart.* |
| 7 | **ใหม่** ยังไม่ได้นิยาม end-to-end | end-to-end = query gen + server + verify; **ไม่รวม** เวลาอ่าน root (รายงานแยก) และการถอดรหัส CP-ABE ของ record |
| 8 | setup ยังมีช่อง [ ] | Python 3.12; AWS r7i.4xlarge (Xeon Platinum 8488C, 16 vCPU, 128 GiB, Ubuntu); `cryptography`: SHA-256, AES-256-GCM, AES-SIV, HMAC-SHA256; CP-ABE BSW07 (Charm 0.62, SS512); ABS MPR (Charm, **SS512**, symmetric pairing; #54 C); Sepolia; *"each reported value is averaged over 10 independent runs after 3 warm-up runs"* (mean, #46) + *"for settings with several queries, each point is the median over the queries and bars show the interquartile range"*; θ 64/16; fill placement; query 4 keyword |
| 9a | สมการ (9) σ_d แยกจาก (11) σ_op | เพิ่ม: *"Since U_d in (8) coincides with U_ins in (10), the upload signature σ_d is the σ_op of that insertion request; an upload is signed once."* |
| 10 | สัญลักษณ์ PAPC: Table II เขียน ρ_w แต่สมการ (19), (20), (42), (49), (68) และ proof Theorem 1 เขียน σ_w (ชนกับ σ ของลายเซ็น σ_d / σ_op / σ_root) | ใช้ **ρ_w ทุกที่** (ตรง Table II และโค้ด `rho()`) |
| 11 | setup: ช่องที่ยังไม่บอกค่า | Search Tree = B+ tree order **B = 64**; keyword extraction = RAKE, สูงสุด κ = 20 ต่อไฟล์ (1–3 คำ), แบ่ง chunk เมื่อไฟล์ยาวเกิน Θ_doc (ตรงประโยค "chunked documents" ของ (32)) |
| 9 | Exp 2 | ชื่อและเนื้อหาเพิ่ม tamper detection; แก้ "Fig. ??" และ caption "Enter Caption" |

ต้องหาด้วยว่าใน (32) มีประโยคที่ระบุชื่อ blockchain หรือบอกว่า "query อ่านจาก public chain" ทุกครั้งหรือไม่ ถ้ามี ต้องแก้ให้ตรงกับข้อ 6

### B5: กราฟ + ผล (17:00–20:00) และ B6: clean repo (หลังส่ง)

- B5: A ส่ง `fig*.pdf` + ตัวเลขสรุปให้ประมาณ 17:00; เขียนผลตามจริง **บอกตรงๆ ว่า AMTP แพ้ตรงไหน**
- B6: ห้ามทำตอน AWS กำลังรัน; ทำเป็น PR แยกให้เจ้าของงานกด merge

## 5. กฎ (สำหรับ Claude ของ B)

- **workflow ของทีม (ดู `CLAUDE.md` หัวข้อ "Team workflow"):** เสร็จ 1 task → เปิด PR เข้า `feat/paper32-experiments`
  tag อีกฝั่ง · ต้องตัดสินใจ → เปิด issue `Decision: ...` · หลังเปิด PR หรือ issue ให้เตือนคนของคุณทักไลน์บอกเพื่อน

- **แก้ได้เฉพาะไฟล์ของ B:** `amtp_code/amtp/core/`, `amtp_code/tests/test_abs*.py`, `amtp_code/bench/abs_bench.py`,
  `chain/` และ paper; **ห้ามแก้** `amtp_code/bench/` (ไฟล์อื่น), `baselines/`, `datasets/`, `scripts/` (ของ A)
- ความปลอดภัยห้ามลด: ทุกการ accept ต้องผ่าน hash, Merkle หรือ signature check ห้ามข้าม check เพื่อให้เร็วขึ้น
- pytest ต้องผ่านก่อน push ทุกครั้ง (`cd amtp_code && ../.venv/bin/python -m pytest -q`)
- commit ด้วยชื่อของ Prim เอง; **ห้ามใส่ "Claude", `Co-Authored-By` หรือลิงก์ session** ใน commit, PR, code หรือ docs
- ห้าม merge PR เอง (เจ้าของงานเป็นคนกด) ให้ push branch แล้วบอก A
- ห้ามอ่านหรือ commit `.env`, private key และ credentials ของ AWS
- ภาษา: report ใน `docs/reports/` เขียนภาษาไทย ใช้ศัพท์เทคนิคเป็น English

## 6. ตารางเวลา (19 พ.ย.)

| เวลา | A | B |
|---|---|---|
| ตอนนี้ – 02:00 | ex1–ex5 + smoke บน Mac; ปล่อย ex1, ex2, ex4 ขึ้น AWS | **B1 + B2 ABS, B3 Sepolia** |
| **03:00** ⚑ | go/no-go ABS | |
| 03:00 – 05:00 | merge ABS, smoke, ปล่อย ex3–ex5 | ช่วย review |
| 05:00 – 15:00 | เฝ้า AWS, รันซ้ำที่ล้ม | **B4 Overleaf (15:00)** |
| 15:00 – 17:00 | กราฟ | B4 ตรวจ |
| 17:00 – 21:00 | ส่งกราฟ + ตัวเลข | **B5, ส่ง 21:00** |

## 7. ไฟล์รายละเอียด (อ่านเมื่อต้องใช้)

| ไฟล์ | มีอะไร |
|---|---|
| `docs/reports/2026-11-18-paper32-tasks-B.md` | งานของ B ฉบับเต็ม |
| `docs/reports/2026-11-18-paper32-task-split.md` | แบ่งงาน A/B และจุดต่อ |
| `docs/reports/2026-11-18-paper32-experiment-layout.md` | โครงการทดลอง ex1–ex5 ทุกกราฟ |
| `docs/reports/2026-11-18-paper32-plan-real-primitives.md` | เหตุผลของการตัดสินใจทั้งหมด (ABS, ECDSA, dataset, N) |
| `docs/reports/2026-11-17-chain-anchor.md`, `chain/README.md` | contract, การ deploy, Sepolia |
| `docs/reports/2026-11-17-real-cpabe.md` | CP-ABE จริง (ใช้เป็นต้นแบบของ `abs.py`) |
| `docs/paper_latex_2026-11-17_somo.tex` | LaTeX ตัวเร่งที่ต้องวางใน (32) |
| `docs/HANDOFF.md` | ภาพรวมโปรเจกต์ทั้งหมด |
