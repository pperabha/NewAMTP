# B5 แก้คู่มือ: Fig. 6 ใช้รูปสรุป tamper และคำว่า "returned files" (ตาม PR #74)

วันที่ 19 พ.ย. 2026 · คน B · branch `docs/paper32-b5-tamper` (แตกจาก `feat/paper32-experiments` `ba4248d`)

## ทำอะไร
- `docs/paper32_overleaf_B5.md`
  - Fig. 6: ช่อง (c) = `e2_tamper_attack_types.pdf` (รูปสรุปของ PR #74: AMTP 4/4, Du 3/4 พลาด injected, SE-COLLAB 2/4 พลาด
    hidden + injected, Chen 2/2 ที่ model ครอบคลุม) แทนช่อง hide / inject เดิม 2 ช่อง; กว้าง 0.29 / 0.29 / 0.40
  - caption และย่อหน้า tamper เขียนใหม่ตามรูปสรุป (t จาก 2,021–2,122 ไฟล์ที่ส่งกลับ ตามแกน x ของรูป)
  - คำที่หมายถึง r_Q: "matches" / "results" → "returned files" (Fig. 5 caption + ย่อหน้า, Fig. 6 caption + ย่อหน้า)
  - ข้อ 0.4b: วิธีแก้ถ้าวาง Fig. 5 / 6 ไปแล้ว
- ไม่มีตัวเลขเปลี่ยน (PR #74: figure_points.csv เหมือนเดิม ยกเว้นรูปใหม่)

## ขึ้นกับ
PR #74 (รูป `e2_tamper_attack_types.pdf` และแกน x ใหม่) · ถ้า PR #74 ยังไม่ merge รูปอยู่ใน branch `feat/paper32-tamper-summary`

## สถานะ
เอกสารอย่างเดียว ไม่แก้โค้ด
