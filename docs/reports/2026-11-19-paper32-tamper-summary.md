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

## เพิ่ม: รูป ablation ต่อ batch (owner ขอ, แบบรอบก่อน)
- `e4_batches_skew{0,0.25,0.5,0.75,0.95}`: แกน x = batch (b = 100), แกน y = เวลา update ต่อ batch (s), เส้นจุดบอก "deletions start",
  เฉพาะระดับ index (AMTP, Static-MT, Global-MT(v)); ไม่มีเส้น AMTP full protocol (owner ไม่เอา); ค่า = mean ของ 10 run ต่อ batch
- จุดพุ่งครั้งเดียวที่ batch 25 และ 247 (AMTP และ Static-MT): IMT ขยายความจุเป็นสองเท่า (imt_ms ~10×, hash calls ~7× ใน batch นั้น)
  เป็นงานจริงของโครงสร้าง ไม่ใช่ noise ของการวัด (เกิดทุก seed, ทุก variant ที่มี IMT)
