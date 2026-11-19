# B5: รูปและข้อความผลการทดลองของ AMTP (32) สำหรับ Overleaf

วันที่ 19 พ.ย. 2026 · คน B · branch `docs/paper32-b5-results` (แตกจาก `feat/paper32-experiments` `b4cad59`)

## ทำอะไร
- `docs/paper32_overleaf_B5.md` (ใหม่): รูปผล 7 รูป (Fig. 3–9, แต่ละรูป 3–4 subfigure) ครอบคลุม M1–M8 ของ figure plan,
  บล็อก LaTeX (`figure*` + `\subfloat`), caption, และย่อหน้า Results ของ Exp 1–5 พร้อมตัวเลขจาก
  `baselines/results/paper32/figures/figure_points.csv` (PR #71) · วิธีวางแบบ ค้นหา / วางต่อท้าย
- เขียนจุดที่ AMTP แพ้ตามจริง (ตัวเลขชุด median หลัง #72): Chen ที่ kQ = 1 และ N 10k / 25k (search), Chen end-to-end ที่ N 10k;
  Du end-to-end ที่ kQ ≥ 2; OR ล้วนที่ kQ ≥ 4 (เจ้าของงานให้เก็บ); proof gen แบบ dispersed และ verify เทียบ SE-COLLAB ที่ rQ ≥ 100;
  update ช้ากว่า Chen 25–230 เท่า (ส่วนใหญ่เป็น ABS); Exp 4 ฝั่ง query (verify ช้ากว่า Static-MT 14–16% และ ~1.8× Global-MT(v))
- `docs/paper32_overleaf_B4.md` E1: เพิ่มประโยค "DU อ่าน root และถอดรหัสครั้งเดียวต่อ query นอกรอบที่จับเวลา" (#68 / PR #69)

## เจอระหว่างทำ (ต้องให้ A ตัดสิน)
- #66 กำหนดจุดที่มีหลาย query = median ของ query + error bar IQR และ E1 ของ B4 มีประโยคนี้ แต่ `baselines/plot_p32.py`
  (`mean_by`) ใช้ **mean ข้าม query และไม่มี error bar** → ประโยคใน Setup ไม่ตรงกับรูป ตัวเลขใน B5 เป็นค่าจากรูปปัจจุบัน (mean)
  ทางเลือก: plot ใหม่ด้วย median + IQR (แล้วอัปเดตตัวเลข B5) หรือ ตัดท่อนนั้นออกจาก Setup

## วิธีตรวจตัวเลข
`figure_points.csv` ของ PR #71: ทุกตัวเลขในย่อหน้าเทียบกับไฟล์นี้แล้ว (ค่า y ต่อ series ต่อ x)

## สถานะ
เอกสารอย่างเดียว ไม่แก้โค้ด · รอ A ตัดสินเรื่อง median/mean และประโยค OR · Prim วางลง Overleaf

## อัปเดตหลัง #72 (เจ้าของงานเลือก A)
- A plot ใหม่ (PR #71 commit `74f259e`): จุดของ query = median ข้าม query + IQR · ตัวเลขใน `docs/paper32_overleaf_B5.md`
  อัปเดตจาก `figure_points.csv` ฉบับนี้: Exp 1 (single, multi, Search 2.2), Exp 2 verify single / multi, Exp 5 query
- Exp 2 layouts, tamper, Exp 3, Exp 4, isolation, Sepolia: ค่าไม่เปลี่ยน (1 query ต่อจุด หรือเป็น mean ข้าม run)
- ผลที่เปลี่ยน: AMTP ชนะ Chen ที่ kQ ≥ 2 (แพ้เฉพาะ kQ 1 เล็กน้อย และ N 10k / 25k); (A∨B)∧(C∨D) ชนะทุก kQ; OR แพ้ที่ kQ ≥ 4;
  Exp 5 verify ของ AMTP เร็วกว่า SE-COLLAB แล้ว (0.81–0.84 vs 0.99–1.00 ms); Du ยังเร็วกว่าใน end-to-end ที่ kQ ≥ 2

## แก้ตาม review ของคน A (PR #73)
- Exp 4: partition ใหญ่สุดของ Static-MT 2,492–8,206; "no more than θ_max = 64"; ฝั่ง query เขียนเป็นสัดส่วนจริง
  (verify +14–16% เทียบ Static-MT, ~1.8× Global-MT(v); proof +6% และ +23–26%)
- Exp 3: throughput ของ Chen 700–800 req/s (insert)
- ประโยค OR: เจ้าของงานให้เก็บ → ลบป้าย [ถาม A]
- merge commit `9b49692` มี author ผิด (ใช้ git config ของเครื่อง) → เจ้าของงานจะ Squash and merge; ต่อไปใช้ `git -c user.name -c user.email`
  ทุกคำสั่งที่สร้าง commit รวม merge
