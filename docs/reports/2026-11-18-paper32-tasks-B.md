# งานของคน B (Prim) — ส่ง conference 19 พ.ย. 2026 21:00

คน A = เจ้าของงาน (ทำการทดลอง, AWS, กราฟ) · คน B = Prim (ทำของจริง, Sepolia, Overleaf, clean repo)
อ่านก่อน: `docs/reports/2026-11-18-paper32-task-split.md` (สิ่งที่ตกลงกันแล้ว + ตารางเวลา)
เหตุผลของการตัดสินใจทั้งหมด: `docs/reports/2026-11-18-paper32-plan-real-primitives.md`

## เวลาที่ต้องส่ง (สำคัญที่สุด)

| เวลา | ต้องเสร็จ |
|---|---|
| 19 พ.ย. **02:00** | B1 + B2 (ABS จริง ผ่าน test) push แล้ว · B3 (บัญชี Sepolia) พร้อม |
| **03:00** ⚑ | จุดตัดสินใจ: ถ้า ABS ยังไม่ผ่าน test → รันการทดลองด้วยตัวจำลอง และ B วัดเวลา ABS จริงแยกเป็นตาราง |
| **15:00** | B4 (Overleaf ส่วนที่ไม่ต้องรอผล) เสร็จ |
| **17:00 – 20:00** | B5 ใส่กราฟ + ข้อความผล (กราฟจาก A ประมาณ 17:00) |
| **21:00** | ส่ง |
| หลังส่ง | B6 clean repo |

## ตั้งเครื่อง (ครั้งเดียว)

```bash
git clone https://github.com/pperabha/NewAMTP.git && cd NewAMTP
git checkout feat/paper32-experiments
git checkout -b feat/real-abs                 # งานของ B อยู่ branch นี้ แล้ว push ให้ A merge
python3.12 -m venv .venv
.venv/bin/pip install -r chain/requirements.txt charm-crypto-framework==0.62   # Charm ต้องมี GMP + PBC (baselines/README.md)
.venv/bin/python datasets/arxiv/unpack.py      # -> data/amtp_file_db_v4/ (ใช้ตอน smoke เท่านั้น)
cd amtp_code && ../.venv/bin/python -m pytest -q                      # ต้องได้ 561 passed
AMTP_CPABE=bsw07 ../.venv/bin/python -m pytest -q                      # ต้องได้ 561 passed
```

กติกา: ห้ามแก้ไฟล์ใน `amtp_code/bench/`, `baselines/`, `datasets/`, `scripts/` (ของ A) · pytest ต้องผ่านก่อน push ·
ความปลอดภัยห้ามลด (ทุกการ accept ต้องผ่าน hash / Merkle / signature) · บอก A ทุกครั้งที่ push

## B1 — ABS จริงใน Charm (4–6 ชม.)

- scheme: **Maji–Prabhakaran–Rosulek, "Attribute-Based Signatures"** (IACR ePrint 2008/328; CT-RSA 2011)
  ใช้ practical instantiation (monotone span program + pairing) **ตามสูตรในเปเปอร์ทุกตัว ห้ามเขียนจากความจำ**
  (เว็บ eprint บล็อกการดึงอัตโนมัติ: เปิด https://eprint.iacr.org/2008/328.pdf ใน browser แล้วบันทึกเอง)
- ไฟล์ใหม่ `amtp_code/amtp/core/abs.py` แบบเดียวกับ `amtp/core/cpabe.py` (CP-ABE จริง): Charm, curve **SS512**
  (ตัวเดียวกับ BSW07 / SE-COLLAB); ถ้า scheme ต้องการ asymmetric pairing ให้บอก A ก่อนเลือก curve
- policy ต่อ domain (ตาม (32) "document-operation and root-update policies"):
  - upload / update (σ_d, σ_op): **`domain:Di AND role:owner` ตัวเดียวกันทั้ง insert และ delete (#43 = A)**
  - attribute ของ DO: เช่น `{domain:D1, role:owner}`
- แปลง policy (AND / OR) เป็น monotone span program ในไฟล์เดียวกัน

## B2 — ต่อ ABS เข้า σ_d / σ_op + test + วัดเวลา (2–3 ชม.)

- เลือก scheme ด้วย env **`AMTP_ABS`** (`ed25519` = ตัวจำลองเดิม ค่าเริ่มต้น, `mpr` = ABS จริง) แบบเดียวกับ `AMTP_CPABE`
  ใน `amtp/core/crypto.py` (`make_authority()` เป็นตัวอย่าง)
- จุดที่ต้องรองรับ (interface เดิม: `Signer().public`, `Signer().sign(msg)`, `sig_ok(public, msg, sig)`):
  - สร้าง signer: `amtp/owner.py:49`, `bench/experiments.py:198` (ไฟล์ของ A — ถ้าต้องแก้จริงให้คุยกับ A ก่อน)
  - ตรวจ: `amtp/server.py:86` (CS ตรวจ σ_op), `amtp/validator.py:335` (DO ตรวจซ้ำ)
- **σ_root ไม่เปลี่ยน**: บน chain ใช้ ECDSA ที่ contract ตรวจ (`amtp/chain_anchor.py`, `chain/RootAnchor.sol`)
- test ใหม่ `amtp_code/tests/test_abs.py`: เซ็นแล้วตรวจผ่าน · attribute ไม่ครบไม่ผ่าน · ข้อความ / ลายเซ็นถูกแก้ไม่ผ่าน ·
  **สองคนรวม key กันแล้วต้องไม่ผ่าน (collusion)** · key ของ domain อื่นไม่ผ่าน · Phase 1 → 5 ครบบน `scenario.World`
- pytest ต้องผ่านทั้ง `AMTP_ABS=ed25519` และ `AMTP_ABS=mpr` (และคู่กับ `AMTP_CPABE=bsw07`)
- วัดเวลา: `amtp_code/bench/abs_bench.py` แบบ `bench/cpabe_bench.py` → `baselines/results/abs/abs_costs.csv`
  (+ manifest): Setup, KeyGen, Sign, Verify, ขนาดลายเซ็น ที่ policy 1, 2, 5 attribute; median 15 รอบหลัง warm-up 3
- push branch `feat/real-abs` แล้วบอก A (A จะ merge เข้า `feat/paper32-experiments` และเพิ่ม `AMTP_ABS=mpr` ใน
  `scripts/paper32_env.sh`)

## B3 — บัญชี Sepolia (เปลี่ยนแล้ว: บัญชีเดียว, #42 = A)

- เวลา protocol ทุก ex วัดบน EVM ในเครื่อง (`AMTP_ANCHOR=chain-local`); Sepolia ใช้แค่ชุดเล็กแยก
  (`chain/gas_domains.py --max-d 32` + บางจุดของ ex3) จึงใช้บัญชี admin บัญชีเดียว ไม่ต้องทำ `sepolia_fund.py`
- เช็กยอด test ETH (`chain/sepolia.py status`): ประมาณ 200 tx × ~110k gas; **ห้าม commit key / `.env`**
- RPC URL: ใช้ของ Alchemy / Infura (free) ใส่ `.env` เป็น `AMTP_RPC=...`

## B4 — Overleaf ส่วนที่ไม่ต้องรอผล (3–4 ชม.)

1. **ตัวเร่งความเร็ว** (ไม่มีใน (32) แต่โค้ดใช้): วาง LaTeX จาก `docs/paper_latex_2026-11-17_somo.tex`
   (ทุกจุดมี `% >>> [SOMO 17 Nov]`): AND pruning / focus evidence (Foc, H_full), result-only partition proofs,
   part leaf (`eq:part-leaf`) — เทียบกับ Phase 4–5 ของ (32) ที่เขียนว่า "complete L_h" และ partition proof ของทุก M_cov
2. **σ_root = ECDSA** (6 จุด):
   Phase 1 Step 1 ("registers PK_i and the applicable ABS authorization policies" → "... and the root-update verification
   keys of the authorized DOs") · สมการ (29) `ABS.Sign(SK^abs, ·)` → `Sign(SK^root, ·)` (ECDSA secp256k1) ·
   Threat model + IV-A ("ABS unforgeability" → "+ EUF-CMA security of the root-update signature") ·
   Theorem 3 + proof (`Adv^UF_ABS` → `Adv^EUF-CMA_Sig`) · Table III/IV T_ABS → T_Sig · ย่อหน้าหลัง Table IV
3. **dataset**: Enron → arXiv (ใช้ย่อหน้า dataset ของ AMTP (31)); ช่วง N: ex1/2/3/5 ตาม (31) (100k ต่อ domain, ไล่ 10k–125k),
   ex2 "N = 10⁶" → 100k, ex4 = 25k (20%) + 5 ระดับ skew, ex5 domain เป้าหมาย 5k
4. **setup** (เติมช่อง [ ]): Python 3.12; AWS r7i.4xlarge (Xeon Platinum 8488C, 16 vCPU, 128 GiB, Ubuntu);
   `cryptography`: SHA-256, AES-256-GCM, AES-SIV (DEnc), HMAC-SHA256; CP-ABE BSW07 (Charm 0.62, SS512); ABS MPR (Charm);
   σ_root ECDSA secp256k1 ตรวจใน RootAnchor contract บน Ethereum Sepolia; reps 10 หลัง warm-up 3; θ_max 64, θ_min 16,
   fill placement; query default 4 keyword; เวลาอ่าน root จาก Sepolia ~257 ms รายงานแยก (query วัดกับ contract บน EVM ในเครื่อง)
5. ชื่อและเนื้อหา Exp 2 เพิ่ม tamper detection; แก้ "Fig. ??" และ caption "Enter Caption"

## B5 — กราฟ + ผลลง Overleaf (17:00–20:00)

- A ส่งไฟล์ `fig*.pdf` + ตัวเลขสรุป (ชนะ / แพ้ตรงไหน) ประมาณ 17:00
- เขียนผลแต่ละ ex ตามจริง บอกตรงๆ ว่า AMTP แพ้ตรงไหน (เช่น server time รวม proof แพ้ Chen, OR kQ ≥ 8 แพ้ SE-COLLAB)

## B6 — clean repo (หลังส่ง)

- ห้ามทำระหว่าง AWS กำลังรัน · ลบ branch / worktree ที่ไม่ใช้แล้ว, ไฟล์ผลชั่วคราว, อัปเดต README + `docs/HANDOFF.md`
- ทำเป็น PR แยก ให้เจ้าของงานกด merge เอง
