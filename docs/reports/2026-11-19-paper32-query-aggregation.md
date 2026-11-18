# การรวมผลข้าม query ในกราฟ (ตัดสิน 19 พ.ย. 2026)

## ตัดสิน (เจ้าของงาน)
- แต่ละ query = **mean ของ 10 run** หลัง warm-up 3 (#46, ตาม setup ของ (32) "averaged over ... independent runs")
- แต่ละจุดบนกราฟที่มีหลาย query (ex1, ex2 verify ตาม rQ) = **median ของ query ในจุดนั้น**, error bar = IQR (Q1–Q3)
  เหมือนกราฟรอบ (31) (`baselines/plot_paper.py` `agg()`)
- ไม่ขัด (32): (32) กำหนดแค่การเฉลี่ยข้าม run ของ query เดียวกัน ไม่ได้กำหนดการรวมข้าม query ที่ต่างกัน

## เหตุผล (ผลรอบ part_leaf, AWS r7i.4xlarge, reps 15)
- กราฟรอบก่อน: median ของ 15 run ต่อ query แล้ว median ของ 20 query ต่อจุด
- query ที่มีผลมาก ทำให้ mean ข้าม query ถูกดึงขึ้น เช่น `S2_00051` (AND-of-OR kQ 2, 12,933 records): AMTP 7.0 ms vs
  SE-COLLAB 1.1 ms; ถ้าใช้ mean ข้าม query จุด AND-of-OR kQ 2 แพ้ SE-COLLAB (1.11 vs 0.77 ms) และ single domain kQ 1, 2
  แพ้ Chen; ใช้ median: ชนะทุกจุด ยกเว้น 10k (เสมอ Chen 0.024 vs 0.023)
- ต้องบอกตรงๆ ใน paper: query ที่ผลเกิน ~1,000 records AMTP search ช้ากว่า SE-COLLAB; OR ล้วน (A∨B∨C∨D อยู่ใน Exp 1 ของ (32))
  แพ้ SE-COLLAB ที่ kQ ≥ 4 (kQ 16: 4.3 vs 1.8 ms)

## ที่แก้
- `docs/PAPER32_START_HERE.md`: บันทึกการตัดสินใต้ #46; B4 ข้อ 8 เพิ่มประโยค
- `docs/paper32_overleaf_B4.md` (ย่อหน้า setup): *"where a setting contains several queries, each point is the median of these
  per-query averages and the bars show the interquartile range"*
- กราฟ (A8): `plot_exp1/2` ต้องเปลี่ยนคอลัมน์จาก `_ms_median` เป็น `_ms` แล้วใช้ `agg()` (median + IQR ข้าม query) เหมือนเดิม

## สถานะ
- docs เท่านั้น ไม่มีโค้ดเปลี่ยน (ไม่ต้องรัน pytest)
