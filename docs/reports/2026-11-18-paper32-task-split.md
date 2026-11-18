# แบ่งงาน 2 คน (ทำคู่ขนาน) — ส่ง conference 19 พ.ย. 2026 21:00

**คน A = เจ้าของงาน · คน B = Prim** (งานละเอียดของ B: `docs/reports/2026-11-18-paper32-tasks-B.md`)

branch หลักของงานนี้: `feat/paper32-experiments` · โครงการทดลอง: `docs/reports/2026-11-18-paper32-experiment-layout.md`
ที่มาของการตัดสินใจ: `docs/reports/2026-11-18-paper32-plan-real-primitives.md`

## สิ่งที่ตกลงกันแล้ว (ใช้ตามนี้ทั้งสองคน)

**การทดลอง (ตาม paper (32) + โครงของเรา)**
- ex1 Search: 1.1 vary kQ ∈ {1,2,4,8,16} (AND, 4 scheme) · 1.2 vary N, kQ = 4 (4 scheme) · 2.1 Boolean 4 รูปแบบ
  (AND, OR, (A∨B)∧(C∨D), (A∧B)∨(C∧D)) vs SE-COLLAB · 2.2 vary D vs SE-COLLAB · แกน y = server time และ end-to-end
- ex2 Verify: 1.1 vary rQ (4 scheme) · 1.2 tamper (4 attack, 4 scheme) · 2.1 multi-domain vary rQ vs SE-COLLAB ·
  2.2 vary D (y = verify time) vs SE-COLLAB · ใหม่ตาม (32): clustered vs dispersed + proof size
- ex3 Update AMTP vs Chen: (a) x = batch 1/10/100/1000, (b) x = N ที่ b = 100; ms ต่อ update, insert / delete;
  ไม่นับ split/merge
- ex4 Ablation AMTP / Static-MT / Global-MT: **20% ของ dataset** (เริ่ม 25k + 250 batch × 100), θ_max 64,
  **5 ระดับ skew** (0, 0.25, 0.5, 0.75, 0.95), **10 run** (#45); 3 variant ที่ระดับ index + เส้น AMTP protocol เต็ม (#44)
- ex5 Multi-domain D = 1–32: query, proof gen, verify, root maintenance (anchor time + gas บน Sepolia ชุดแยก, #42), update isolation
  (insert + delete), baseline ทุกตัวที่รันได้ (SE-COLLAB, Du)
- Search 2.2 / Verify 2.2 ซ้อนกับ ex5: เก็บผลทั้งสองชุด

**ขนาดและการวัด**
- dataset arXiv v4 (ไม่ใช้ Enron); ex1/2/3/5 ขนาดเดียวกับ (31): 100k ต่อ domain, ไล่ 10k–125k, ex5 domain เป้าหมาย 5k
- reps = 10 หลัง warm-up 3 · query default 4 keyword · θ_max 64 / θ_min 16
- **AMTP เปิดตัวเร่งทั้งหมด (ค่าเริ่มต้นของโค้ด อยู่แล้ว):** fill placement (เติมให้เต็ม), AND pruning (+ greedy),
  result-only partition proofs, part leaf; ใส่คำอธิบาย LaTeX ลง (32) (`docs/paper_latex_2026-11-17_somo.tex`)
- update: รายงาน protocol time แยกจาก anchor time + gas
- query อ่าน root จาก contract บน EVM ในเครื่อง (`anchor_read` แยก); เวลาอ่านบน Sepolia รายงานใน setup

**ของจริงทั้งหมด**
- CP-ABE BSW07 (เสร็จ) · Root Anchor contract บน Sepolia (เสร็จ) · σ_root = ECDSA ที่ contract ตรวจ (เสร็จ; แก้ (32) 6 จุด)
- **ABS จริง** สำหรับ σ_d / σ_op ตรวจนอก chain (CS + DO) — ยังไม่ทำ (scheme: Maji–Prabhakaran–Rosulek, ePrint 2008/328;
  ต้องดาวน์โหลด PDF เองใน browser เพราะเว็บบล็อกการดึงอัตโนมัติ)

## จุดต่อระหว่างสองคน (ทำให้ทำคู่ขนานได้)

- ABS เข้าทาง **env `AMTP_ABS`** (`ed25519` = ตัวจำลองเดิม, `mpr` = ABS จริง) แบบเดียวกับ `AMTP_CPABE`:
  คน B แก้เฉพาะ `amtp/core/crypto.py` (+ ไฟล์ใหม่ `amtp/core/abs.py`) ให้ `Signer` / `sig_ok` เลือก scheme ตาม env
  จุดที่ใช้: `amtp/owner.py:49`, `bench/experiments.py:198` (สร้าง Signer), `amtp/server.py:86`, `amtp/validator.py:335` (ตรวจ)
- คน A เขียนการทดลองโดยไม่แตะไฟล์ crypto; ตอนรวมงานแค่เพิ่ม `export AMTP_ABS=mpr` ใน `scripts/paper32_env.sh`
- ห้ามแก้ไฟล์เดียวกันพร้อมกัน: A = `amtp_code/bench/`, `baselines/`, `datasets/`, `scripts/` · B = `amtp_code/amtp/core/`,
  `amtp_code/tests/test_abs*.py`, `chain/`, paper

## คน A — การทดลอง, AWS, กราฟ

| # | งาน | ประมาณ |
|---|---|---|
| A1 | ex1 ให้ครบ (มีแล้ว: query p32, anchor_read; เหลือตรวจ Chen/Du รองรับ kQ 16 และสคริปต์รัน) | 1–2 ชม. |
| A2 | ex2: สร้าง layout clustered / dispersed ใหม่บน v4 (โค้ดเดิม `suite_exp2` + `exp2_layouts.json`), verify / tamper เดิม | 2–3 ชม. |
| A3 | ex3: (b) ไล่ N, ไม่นับ epoch ที่มี split/merge, Chen ทั้ง (a) และ (b) | 2 ชม. |
| A4 | ex4: 20% (25k), 5 ระดับ skew (`SM_SKEWS`), 10 run, แยกเวลา split/merge, เส้น AMTP protocol เต็ม | 3 ชม. |
| A5 | ex5: เพิ่ม delete, Du, root maintenance จาก Sepolia | 2 ชม. |
| A6 | smoke ทุก ex บน Mac (ขนาดเล็ก) + แผนเครื่อง AWS (~14 เครื่อง) + สคริปต์ปล่อยงาน | 1–2 ชม. |
| A7 | รันจริงบน AWS, เฝ้า, ดึงผลกลับ (ตรวจ manifest: query_set p32, cpabe bsw07, ABS mpr, anchor) | ~10 ชม. (ส่วนใหญ่รอ) |
| A8 | plot กราฟทุก ex (line chart, บอกตรงที่แพ้) | 3 ชม. |

## คน B — ของจริง, Sepolia, Overleaf, clean repo

| # | งาน | ประมาณ |
|---|---|---|
| B1 | ดาวน์โหลด PDF ABS (ePrint 2008/328) → implement ใน Charm (`amtp/core/abs.py`), policy ต่อ domain เช่น `domain:D1 AND role:owner` | 4–6 ชม. |
| B2 | ต่อ ABS เข้า σ_d / σ_op ผ่าน `AMTP_ABS`, test: เซ็นแล้วผ่าน, attribute ไม่ครบไม่ผ่าน, แก้ลายเซ็นไม่ผ่าน, รวม key ไม่ผ่าน; pytest ทั้งสองโหมด; วัดเวลา sign/verify | 2–3 ชม. |
| B3 | Sepolia: บัญชีเดียว (#42 = A), เช็กยอด test ETH สำหรับชุดแยก (~200 tx) | 0.5 ชม. |
| B4 | Overleaf (ไม่ต้องรอผล): วาง LaTeX ตัวเร่ง (AND pruning, result-only, part leaf), แก้ 6 จุด σ_root = ECDSA, dataset arXiv แทน Enron, ช่วง N, setup (Python 3.12, AWS r7i.4xlarge, SHA-256, AES-GCM, BSW07, ABS, Sepolia, reps 10/warm-up 3, θ 64/16) | 3–4 ชม. |
| B5 | ใส่กราฟและตัวเลขจริงลง Overleaf, เขียนข้อความผลแต่ละ ex | 3 ชม. |
| B6 | clean repo หลังได้ผลครบ (ไม่ทำระหว่าง AWS กำลังรัน): ลบ worktree/branch ที่ไม่ใช้, ไฟล์ผลชั่วคราว, อัปเดต README / HANDOFF | 1–2 ชม. |

## ตารางเวลา

| เวลา | คน A | คน B |
|---|---|---|
| 18 พ.ย. คืนนี้ – ตี 3 | A1–A6 | B1–B3 |
| 19 พ.ย. ตี 3–5 | รวมงาน: merge ABS ของ B, smoke ทุก ex ด้วยของจริงทั้งหมด, commit, push, เปิดเครื่อง AWS | (ช่วย smoke / review) |
| ตี 5 – บ่าย 3 | A7 รัน AWS | B4 Overleaf |
| บ่าย 3 – 6 โมงเย็น | A8 กราฟ | B4 ต่อ / ตรวจ |
| 6 โมงเย็น – 3 ทุ่ม | ส่งกราฟ + ตัวเลข | B5 Overleaf, ส่ง |
| หลังส่ง | | B6 clean repo |

**ความเสี่ยง:** ABS (ยังไม่เคยทำ) ถ้าไม่ทันตี 3 → รันด้วยตัวจำลอง และวัดเวลา ABS จริงแยกเป็นตาราง; AWS ล้ม → มีเวลารันซ้ำได้ 1 รอบ;
ราคา gas Sepolia (เช็กก่อนรัน)
