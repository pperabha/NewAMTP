# B4: คู่มือแก้ AMTP (32) ใน Overleaf (ส่วนที่ไม่ต้องรอผล)

วันที่ 19 พ.ย. 2026 · คน B · branch `docs/paper32-b4-overleaf` (แตกจาก `feat/paper32-experiments` `7c28cd3`)

## ทำอะไร

- `docs/paper32_overleaf_B4.md` (ใหม่): คู่มือแบบ หน้า / ข้อความที่ต้องค้น (คัดจาก AMTP (32).pdf ตรงตัว) / ลบ / วาง
  เรียงตามหน้า ครอบคลุม B4 ข้อ 1–11 + 9a ของ `docs/PAPER32_START_HERE.md`
  - [B4-1] σ_root = ECDSA (Phase 1 Step 1, สมการ 29, threat model, IV-A, Theorem 3, Table III/IV, ย่อหน้าหลัง Table IV)
  - [B4-2] LaTeX จาก `_somo`: 1.3 (batch, #50), 1.5 + 2.1 + 1.11 Step 1 (IMT indexed, #51), 1.6, 1.7–1.13, 2.2–2.7,
    3.1–3.3, 5.1–5.5 · ไม่วาง 1.1, 1.2 (#48, #49), 1.4 (comment), 3.4/3.6/3.6b/3.7 (ของรอบ (31))
  - [B4-3/4/5/6/7/8/11] ย่อหน้า Setup และ dataset เขียนใหม่ (Python 3.12, r7i.4xlarge, BSW07 + MPR บน SS512,
    ECDSA ใน RootAnchor, EVM ในเครื่อง vs Sepolia, B = 64, RAKE κ = 20, mean ของ 10 รอบหลัง warm-up 3,
    นิยาม end-to-end), ช่วง N, Exp 4 (25k + 250 × 100, skew 0–0.95, delete 65%), Exp 5 (5k)
  - [B4-9] Exp 2 + tamper detection, Fig. ?? 2 ที่, caption "Enter Caption" · [B4-9a] σ_d = σ_op · [B4-10] ρ_w
  - ตาราง ABS (#54): sign / verify / ขนาด ของ SS512, MNT224, BN254 และ Ed25519
- `baselines/results/abs/abs_costs.csv` วัดใหม่ตอนเครื่องว่าง (รอบก่อนวัดขณะ pytest รันอยู่)

## จุดที่ตัดสินเอง (ให้ A ตรวจ)

1. Table IV update: `T_part + u T_post + T_IMT + b T_ABS + T_Sig` (somo 3.2 เขียน `+ T_ABS` เพราะตอนนั้น σ_root เป็น ABS;
   รอบนี้ ABS ต่อ request, ECDSA ต่อ epoch) และ Table III แยก T_ABS (request) กับ T_Sig (root)
2. ไม่เพิ่มแถว `g_d` ใน Table II (#49: U_d ไม่มี g_d) แต่ DO bullet และ leakage พูดถึง "placement hint" นอกลายเซ็น
3. ตัดประโยค "6% memory / 1.5% build time" ของ part leaf ออก เพราะเป็นตัวเลขรอบ (31)
4. Setup ใช้สัญลักษณ์ `Θ_doc` สำหรับการแบ่ง chunk ตามข้อ 11 ถ้า paper ไม่มีสัญลักษณ์นี้ให้เขียนเป็นคำ
5. ตาราง ABS ใช้ตัวเลขจาก container (4 vCPU, แกว่ง); ควรรัน `bench/abs_bench.py` บน AWS แล้วแทน

## วิธีใช้

เปิด `docs/paper32_overleaf_B4.md` ทำ G1 (σ → ρ) ก่อน แล้วไล่ตามหน้า · checklist ท้ายไฟล์

## สถานะ

- เสร็จ: คู่มือ · ยังไม่ได้วางใน Overleaf (B วางเอง) · คำอธิบายผลการทดลองรอ B5
