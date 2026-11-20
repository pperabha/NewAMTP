# Guide ผลรอบ paper (32) สำหรับอาจารย์ + README รอบ (32) + ผลดิบ AWS

วันที่ 20 พ.ย. 2026 · คน A · branch `docs/paper32-advisor-guide` (แตกจาก `feat/paper32-experiments` 4b6dcd4)

## ทำไม
ฉบับ 24 หน้า (AMTP (36)) เขียนเสร็จแล้ว เจ้าของงานจะส่ง repo ให้อาจารย์ดู เพื่อให้อาจารย์ตัดสินว่าใน Overleaf ควรใส่อะไร
และตัดอะไร จึงต้องมีที่เดียวที่บอกได้ว่ามีผลอะไรบ้าง, รูปไหนอยู่ในฉบับไหน และ AMTP ชนะหรือแพ้ตรงไหน

## ทำอะไร
- `docs/PAPER_GUIDE.md` (อังกฤษ ตามที่เจ้าของงานเลือก) มี 5 ส่วน:
  - รูปของแต่ละฉบับ (24 / 6 หน้า) และรูปที่ยังรอตัดสิน
  - ผลทั้ง 5 การทดลองในหน้าเดียว บอกจุดที่แพ้ทุกจุด
  - จุดที่ reviewer น่าจะถาม (มีหรือไม่มีในฉบับ 24 / 6 หน้า)
  - security tests (attack → check ที่จับ → ไฟล์ test)
  - แผนที่ paper ↔ code
  - ส่วน "จุดที่โค้ดต่างจาก (32)" เอาออกตามที่เจ้าของงานสั่ง (20 พ.ย.)
- `baselines/figure_catalog.py` → `baselines/results/paper32/FIGURES.md`:
  - รวมทุกรูป (109 รูป: 108 png + false alarms ที่มีแต่ตัวเลข) พร้อมรูป, data และ note
  - แต่ละ baseline มี 1 บรรทัดบอกว่า AMTP ดีกว่าที่ x ไหน แย่กว่าที่ x ไหน กี่เท่า คำนวณจาก `figure_points.csv` ไม่ได้พิมพ์เอง
  - กติกา: เวลา / ขนาด / gas / partition ต่ำกว่าดีกว่า; throughput / detection / attack types สูงกว่าดีกว่า; ต่างกันไม่เกิน 2% = เสมอ
- `README.md` เขียนใหม่สำหรับรอบ (32):
  - install มี Charm และ `chain/requirements.txt`
  - test ทั้ง default และ paper config
  - rebuild รูปด้วย `plot_p32.py` และตาราง run folder → commit → step
  - re-run ด้วย `paper32_env.sh` + `aws_run_all.sh` + `paper32_ex4_machine.sh`
  - implementation notes บอกว่า default ใช้ stand-in ส่วน paper config ใช้ของจริง
- `baselines/results/runs/cloud/` ผลดิบของทุกเครื่อง (340 ไฟล์ 40 MB: log, console, CSV, manifest รวม `*_aborted_68`) commit
  เข้า repo private ตามที่เจ้าของงานเลือก เช็คแล้วว่าไม่มี key, `.env` หรือ path ในเครื่อง
- `chain/README.md`: แก้แถว σ_op (ตอนนี้ใช้ ABS จริงได้ด้วย `AMTP_ABS=mpr`)
- `docs/HANDOFF.md`: สถานะล่าสุด 20 พ.ย.

## ตรวจแล้ว
- `plot_p32.py --data baselines/results/paper32/data` สร้างใหม่ใน scratch แล้วได้ `figure_points.csv` เหมือนไฟล์ที่ commit ทุก byte (108 รูป, 12 s)
- commit ของทุก run ดูจาก manifest:
  - Exp. 1, 2, 5 = `74379b7`
  - Exp. 3, 4 = `c79b2a0`
  - ABS = `8ed08b7`
  - Sepolia = `00888ca` / `ff7dcd5`
- กรณีที่ Static-MT เร็วกว่า AMTP ที่ skew 0.95 มีแค่ batch 4–7 (ช่วง insert ตอนต้น ไม่เกิน 1.39×) ไม่ได้อยู่ในช่วง delete
  ข้อความใน paper ว่า "AMTP stays fastest through the deletion phase" จึงถูก
- pytest:
  - default: 575 passed, 4 skipped
  - paper config (`paper32_env.sh`): ดูใน PR
- security tests (6 ไฟล์ใน guide ส่วนที่ 5): 111 passed, 1 skipped

## ทำซ้ำ
```bash
.venv/bin/python baselines/plot_p32.py --data baselines/results/paper32/data --out baselines/results/paper32/figures
.venv/bin/python baselines/figure_catalog.py
```

## สถานะ
- รอเจ้าของงาน merge PR นี้เข้า `feat/paper32-experiments` แล้ว merge #40 เข้า main
- repo ใหม่สำหรับส่งอาจารย์ (snapshot ไม่มี docs ภายใน) ทำจาก branch นี้ รอเจ้าของงานเลือกชื่อ / public หรือ private / GitHub ของอาจารย์
