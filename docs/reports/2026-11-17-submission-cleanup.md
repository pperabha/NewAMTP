# จัด repo ให้เหลือเฉพาะผลของ paper และเปลี่ยนชื่อให้ตรง paper

วันที่ 17 พ.ย. 2026 · branch `release/submission-cleanup` (ต่อจาก `release/submission`)

## ทำอะไร

| อะไร | ก่อน | หลัง |
|---|---|---|
| ข้อมูลของ paper | `results/part_leaf/data`, `data_no_fetch`, `runs/cloud/prune_w2`, `prune_w5` | `results/paper/data`, `data_no_fetch`, `ablation/amtp_static_t64`, `ablation/global_mt_v_t64` |
| ไฟล์ที่ paper ไม่ใช้ใน data | `*_domains_scaling.*`, `search_index_*.json` | ลบ |
| ผลรอบเก่า | `results/old`, `new_new`, `new_purn`, `new_amtp_result`, `search_split`, `runs/` ทั้งหมด, `part_leaf/graphs` | ลบ (ยังอยู่ใน branch `archive/results-2026-11-17`) |
| สคริปต์ plot | `plot_exp4.py` (Exp. 3), `plot_exp5.py` (Exp. 4) | `plot_exp3.py`, `plot_exp4.py` · ชื่อไฟล์รูป `exp3_*`, `exp4_*` |
| รูปของ paper | หลายโฟลเดอร์ | `results/paper/figures/fig03` … `fig10` (pdf + png) · ผลกลางทางอยู่ `figures/build/` (git-ignore) |
| โค้ดเก่า | `amtp_code/bench/old`, `baselines/old`, `baselines/plot_story.py` | ลบ |

ไม่เปลี่ยนโค้ดของ AMTP หรือ baseline ชื่อ suite `exp5` ในโค้ดยังเหมือนเดิม (README บอกว่าเป็น Experiment 4)

## ตรวจแล้ว

- `figure_points.csv` ของทุกรูปเทียบกับก่อนย้าย: Exp. 1 328 จุด, Exp. 2 150, Exp. 3 15,117, Exp. 4 12 · เหมือนกันทุกค่า
- pytest: ค่าเริ่มต้น 545 passed · `scripts/paper_env.sh` 542 passed
- `bash scripts/make_paper_figures.sh` สร้าง fig03 … fig10 ครบ

## repo ที่ส่ง (AMTP-submission)

สร้างจาก branch นี้เป็น commit เดียว โดยไม่ใส่เอกสารภายในทีม: `CLAUDE.md`, `docs/HANDOFF.md`, `docs/reports/`,
`docs/paper_*`, `README_TH.md`, `scripts/cloud_helpers/`

## รอบ 2: แปลคอมเมนต์เป็นอังกฤษ + pin version

- แปลคอมเมนต์ docstring ข้อความ help และข้อความ error ภาษาไทยเป็นอังกฤษใน 8 ไฟล์: `chen_et_al_sim.py`,
  `du_et_al_sim.py`, `se_collab_sim.py`, `amtp_dataset.py`, `plot_results.py`, `amtp/nlp.py`,
  `bench/extraction.py`, `datasets/arxiv/dataset_forAMTP.py` (รวม 1,581 token)
- แก้ทีละ token (comment / string) แล้วตรวจด้วย tokenize ว่า token ที่เป็นโค้ดทุกตัวเหมือนเดิม และไฟล์ parse ได้
- ไม่แตะ `"ไทย"` ใน `tests/test_fast_hash_paths.py` เพราะเป็นข้อมูลทดสอบ UTF-8
- `amtp_code/requirements.txt` pin version ที่ทดสอบจาก clone ใหม่ (Python 3.12): flask 3.1.3, cryptography 50.0.2,
  pytest 9.2.0, numpy 2.5.5, pycryptodome 4.5.0, matplotlib 3.11.2 · Charm 0.62 (ไม่บังคับ)

ตรวจแล้ว: Chen selftest 13/13 · Du demo ผ่าน · SE-COLLAB selftest 18/18 · pytest 545 / 542 · venv ใหม่จาก requirements
ที่ pin แล้ว pytest 545 passed · `make_paper_figures.sh` ครบ
