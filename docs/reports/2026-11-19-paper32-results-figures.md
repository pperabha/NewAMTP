# A8: ผลจริงของ paper (32) และรูปทั้งหมด (Exp 1-5)

วันที่ 19 พ.ย. 2026 · คน A · branch `results/paper32-figures` (แตกจาก `feat/paper32-experiments` b4cad59)

## ทำอะไร
- เก็บผลจาก AWS (10 เครื่อง, r7i.4xlarge, ของจริงทั้งหมด: CP-ABE BSW07, ABS MPR SS512, RootAnchor contract บน EVM ในเครื่อง)
  ไว้ที่ `baselines/results/paper32/data/` (ไม่รวมรันที่ยกเลิกก่อนแก้ #68 และ `p32_ex5_w9` รุ่นเก่า)
- สร้างรูป 103 รูป (png + pdf), `figure_points.csv`, `README.md` ที่ `baselines/results/paper32/figures/` ด้วย
  `baselines/plot_p32.py` (ค่า = mean ของ 10 reps หลัง warm-up 3; รูปเส้นเท่านั้น; ไม่มี title)

## รันที่ commit ไหน
- Exp 3 (update), Exp 4 (ex4 ทั้ง 5 skew): c79b2a0
- Exp 1, 2, 5 (query suites): 74379b7 (หลังแก้ #68: anchor read + CP-ABE decrypt วัดครั้งเดียวต่อ query)
- ทุก manifest `git_dirty: false`, ไม่มี FAIL

## หมายเหตุสำหรับ caption / ข้อความ
- M1 (single-domain server search): AMTP แพ้ Chen ที่ kQ = 1 (และใกล้เคียงที่ kQ 2-4); ชนะที่ kQ >= 8 และชนะ SE-COLLAB / Du ทุกจุด
- Chen ไม่ประเมิน AND ที่ server (DU ทำ); Du = cloud ที่ช้าที่สุด
- Exp 4: เส้น "AMTP (full protocol)" รวม ABS + validator + anchor จึงไม่เทียบตรงกับ index-level ของ Static-MT / Global-MT(v)
- gas ในรูป `e5_sepolia_*` มาจาก Sepolia (`chain/runs/gas_domains_20261119_005048.csv`);
  `e5_root_gas_localevm` ห้ามใช้ใน paper (ตาราง gas ของ py-evm ต่างจาก Sepolia)

## สร้างรูปใหม่
`.venv/bin/python baselines/plot_p32.py --data baselines/results/paper32/data --out baselines/results/paper32/figures`
