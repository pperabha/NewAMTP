# เตรียมโค้ดสำหรับส่ง (CSS453 Final Project)

วันที่ 17 พ.ย. 2026 · branch `release/submission` (แตกจาก `main` 0b597ab)

## ทำอะไร

guideline ข้อ 2 ขอโค้ดครบ, README บอกวิธี install / run / test และให้คนอื่นรันซ้ำได้ รอบนี้ทำเฉพาะส่วนที่ต้องมีก่อนส่ง
ไม่เปลี่ยนโค้ดของ AMTP หรือ baseline

| ข้อ | อะไร | ไฟล์ |
|---|---|---|
| 1 | README ภาษาอังกฤษใหม่: install, dataset, test, demo, ค่าที่ paper ใช้, สร้างรูปใหม่, รัน experiment ใหม่, code map, implementation notes | `README.md` |
| 1 | ตาราง Exp / Fig ใน paper → ข้อมูล → commit ของรอบที่รัน → สคริปต์ plot | `README.md` ส่วนที่ 4 |
| 2 | ค่าที่ paper ใช้เป็นสคริปต์ (ไม่เปลี่ยนค่าเริ่มต้นในโค้ด): fill, γ มี v, AND pruning + greedy, result-only partition proofs, part leaf | `scripts/paper_env.sh` |
| 3 | สร้าง Fig. 3–10 ด้วยคำสั่งเดียวจากข้อมูลใน repo → `fig03.pdf` … `fig10.pdf` | `scripts/make_paper_figures.sh` |
| 3 | สคริปต์ plot และรูปของ paper (เดิมยังไม่ได้ commit) | `baselines/plot_exp{1,2,4,5}.py`, `baselines/results/part_leaf/graphs/exp{1,2,4,5}/` |
| 4 | ลบ `runs/mac_and_prune/` และ `runs/mac_part_leaf/` (มี path ของเครื่อง, ไม่ใช่ข้อมูลของ paper) และ `.DS_Store` | `.gitignore` เพิ่ม `paper_figures/`, `.DS_Store` |
| - | แก้เอกสารเรื่อง Exp. 4 เดิมรันรอบเดียว (`runs: 1`) ที่ค้างจากรอบก่อน | `docs/paper_sync_2026-11-16.md`, `docs/paper_latex_2026-11-17_somo.tex`, `docs/reports/2026-11-17-paper-latex-somo.md` |

ชื่อ `plot_exp4.py` / `plot_exp5.py` และ suite `exp5` ยังเป็นเลขเดิม README บอกไว้ว่าเป็น Experiment 3 และ 4 ของ paper
(เปลี่ยนชื่อทีหลัง ไม่ทำในคืนส่ง)

## ตรวจแล้ว

- pytest จาก `amtp_code/`: ค่าเริ่มต้น 545 passed, 1 skipped · `scripts/paper_env.sh` 542 passed, 4 skipped
- `scripts/make_paper_figures.sh` สร้าง `fig03.pdf` … `fig10.pdf` ครบจากข้อมูลใน repo
- clone ใหม่ลงโฟลเดอร์เปล่าแล้วทำตาม README (install → pytest → สร้างรูป)
- ไม่มี path ของเครื่องเหลือในไฟล์ที่ track

## ยังไม่ได้ทำ (หลังส่ง)

เปลี่ยนชื่อ experiment ในโค้ดให้ตรงกับ paper, ตัด suite / แบบ search ที่ paper ไม่ใช้, แปลคอมเมนต์ภาษาไทยใน .py,
pin version ใน requirements, ย้ายผลรอบเก่าไป branch archive

## วิธีใช้

```bash
python3 -m venv .venv && .venv/bin/pip install -r amtp_code/requirements.txt
cd amtp_code && ../.venv/bin/python -m pytest -q && cd ..
bash scripts/make_paper_figures.sh
```
