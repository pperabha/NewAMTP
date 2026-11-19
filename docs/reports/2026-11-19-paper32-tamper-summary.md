# A8 เพิ่มเติม: รูปสรุป tamper detection + แกน x ของรูป verify

วันที่ 19 พ.ย. 2026 · คน A · branch `feat/paper32-tamper-summary` (จาก `feat/paper32-experiments` eba0c31)

## ทำอะไร
- `baselines/plot_p32.py`: รูปใหม่ `e2_tamper_attack_types` (แบบเดียวกับ `plot_exp2.py` รอบก่อน, owner ขอ): แกน y = จำนวนแบบการโจมตี
  (modified, hidden, injected, old version) ที่ scheme จับได้ **ทุก run**, แกน x = จำนวนไฟล์ที่ถูกแก้ t, ข้อความท้ายเส้นบอกว่าพลาดแบบไหน
  ผล: AMTP 4 of 4 ทุก t · Du 3 of 4 (พลาด injected) · Chen 2 of 2 ที่ใช้ได้ (ไม่มี model ของ modify / old) · SE-COLLAB 2 of 4 (พลาด hidden, injected)
- แกน x ของรูป verify และ layout: "Matching records r_Q" → "Returned files r_Q" (owner เลือก) ตัวเลขไม่เปลี่ยน
- รูปอื่นไม่ได้ commit ใหม่ (ต่างกันแค่ CreationDate)

## สร้างใหม่
`.venv/bin/python baselines/plot_p32.py --data baselines/results/paper32/data --out baselines/results/paper32/figures`
