# part_leaf — รอบ "Search Tree leaf by partition" (17 พ.ย. 2026) แยกจากผลเดิม

AMTP เปิดทุก query flag เหมือนรอบ prune (fill, AND pruning, result-only partition check, greedy planner) **บวก
`AMTP_PART_LEAF=1`**: leaf ของคำที่อยู่ตั้งแต่ 3 partition เก็บชุด partition และตำแหน่งของแต่ละ partition ไว้ด้วย
(proof และสิ่งที่ส่งให้ผู้ใช้เหมือนเดิมทุก byte) รันบน cloud 3 เครื่องที่ commit `d25616b`

**baseline ทุกตัววัดใหม่บนเครื่องเดียวกับชุด AMTP ที่อยู่กราฟเดียวกัน** (โค้ดและคำสั่งเหมือนรอบหลัก) รันต่อกันทีละงาน

โฟลเดอร์ผลเดิม (`new_purn/`, `search_split/`, `new_new/`, `new_amtp_result/`) ไม่ถูกแก้

## แต่ละรูปใช้ผลจากรอบไหน

| ส่วนในรูป | มาจาก |
|---|---|
| AMTP และ baseline ใน ex1 (search), ex2 (verify, tamper), ex5 query, และทุกรูปใน `search_only/` | **รอบนี้** · `data/` (รวมจาก `runs/cloud/partleaf_w1..w3/`) |
| ex3 (update) AMTP / Chen | รอบ fill (`new_new/data/fill/`) / `new_amtp_result/gamma_with_v/chen/` · ไม่รันใหม่ เพราะโค้ด update ไม่เปลี่ยน |
| ex4 (split / merge) | รอบ prune เครื่อง 2–5 (`runs/cloud/prune_w2..w5/`) · ไม่รันใหม่ |
| ex5 update | รอบนี้ (`amtp_exp5_domains.csv`) |

| เครื่อง | ชุด |
|---|---|
| w1 | AMTP search1, xsearch, exp5 · Chen / SE-COLLAB / Du search1 · SE-COLLAB xsearch, exp5 |
| w2 | AMTP xdomains, xverify · SE-COLLAB xdomains, xverify |
| w3 | AMTP, Chen, SE-COLLAB, Du verify1 และ tamper |

```
part_leaf/
  data/{amtp,chen,secollab,du}/   CSV + manifest ของรอบนี้ (สำเนาจาก runs/cloud/partleaf_w*)
  graphs/search_only/             search อย่างเดียว (bench_split.plot_search) + figure_points.csv
  graphs/paper/                   ex1–ex5 (baselines/plot_paper.py) + figure_points.csv
```

## กราฟ search อย่างเดียว: แยกตามการดึงไฟล์ (fetch)

Chen ไม่ส่งไฟล์กลับ (ส่งแค่ bitmap ที่เข้ารหัส) ส่วน SE-COLLAB (`search_core`) และ Du (`server_total`) ส่งไฟล์กลับ
กราฟโดเมนเดียวจึงมี 2 แบบ เพื่อให้ทุกเส้นในรูปเดียวกันทำงานเท่ากัน:

| ไฟล์ | AMTP | เทียบกับ |
|---|---|---|
| `Search_1.1/search_only_vs_kQ_no_fetch.png`, `Search_1.2/search_only_vs_files_no_fetch.png` | `server_search_pf` (ไม่ดึงไฟล์) | Chen |
| `Search_1.1/search_only_vs_kQ_with_fetch.png`, `Search_1.2/search_only_vs_files_with_fetch.png` | `server_search_pf_fetch` (ดึงไฟล์) | SE-COLLAB, Du |
| `Search_1.1/search_only_vs_kQ_all.png`, `Search_1.2/search_only_vs_files_all.png` | ทั้งสองเส้น (ทึบ = ไม่ดึงไฟล์, ประ = ดึงไฟล์) | ทุก baseline ในรูปเดียว · ชื่อเส้นบอกว่าเทียบกับใคร |
| `Search_2.1/*`, `Search_2.2/*`, `Exp5/*` (หลายโดเมน) | `server_search_pf_fetch` | SE-COLLAB (baseline หลายโดเมนมีตัวเดียว) |

ไม่มี scheme ไหนนับงานสร้าง proof ในตัวเลขเหล่านี้ ยกเว้น Chen ที่ XOR tag ต่อ entry อยู่ในลูปค้นหาเดียวกัน (แยกไม่ได้ถ้าไม่แก้โค้ด Chen และทำให้ Chen ช้าลงเพียงเล็กน้อย)

## กราฟ search ล้วน: ทุก scheme ไม่ดึงไฟล์ (`graphs/search_no_fetch/`)

ทุกเส้นวัดเฉพาะการค้นหา ไม่มี proof และไม่ดึงไฟล์ AMTP มีเส้นเดียว

| scheme | คอลัมน์ | มาจาก |
|---|---|---|
| AMTP | `server_search_pf` | `data/amtp` (w1, w2) |
| Chen | `server_total` (ไม่ดึงไฟล์อยู่แล้ว) | `data/chen` (w1) |
| SE-COLLAB | `search_no_fetch` = `bpl_retrieval` + `boolean_eval` (timer ใหม่ของมันเอง) | `data_no_fetch/secollab` (w4, commit `0ada140`) |
| Du | `search_no_fetch` = Algorithm 2 ส่งกลับแค่ slot ที่ตรง (cloud ที่ช้าสุด) | `data_no_fetch/du` (w5, commit `331d608`) |

- โค้ดเดิมของ SE-COLLAB และ Du ไม่เปลี่ยน แค่เพิ่มคอลัมน์ · Du ตรวจทุก query ว่า slot ที่ได้ตรงกับ search ปกติ
- เครื่องต่างกัน: SE-COLLAB บน w4 ช้ากว่าบน w1 1–3% (`search_core`), Du บน w5 เร็วกว่าบน w1 2–7% (`server_total`) · ส่วนต่างนี้เข้าทาง Du ไม่ใช่ทาง AMTP

| กราฟ | ผล |
|---|---|
| Search 1.1 (kQ 1–20, 100k files) | ✅ ชนะทั้ง 3 baseline ทุกจุด (kQ 20: AMTP 0.103 · Chen 0.129 · SE-COLLAB 0.452 · Du 1.352 ms) |
| Search 1.2 (10k–125k files, kQ 5) | ✅ ชนะทุกจุด · 10k เกือบเสมอ Chen (0.0219 vs 0.0220) |
| Search 2.1 AND, AND-of-OR, OR-of-AND | ✅ ชนะ SE-COLLAB ทุกจุด |
| Search 2.1 OR | ❌ แพ้ที่ kQ ≥ 4 (kQ 16: 4.28 vs 1.80) · ไม่ใช่เพราะ fetch: OR ต้องรวม file set จากทุก partition ที่มีคำใดคำหนึ่ง |
| Search 2.2 (D 1–32) | ✅ ชนะถึง D = 8 · ❌ แพ้ที่ D 16, 32 (ค้นแยกทีละโดเมน) |
| Exp 5 | ✅ ชนะทุก D (≈ 0.033 vs 0.066 ms) |

## ทำซ้ำ

```
D=$PWD/baselines/results/part_leaf/data; M=<repo>/baselines/results
cd amtp_code && ../.venv/bin/python -m bench_split.plot_search --amtp $D/amtp --base $D --out ../baselines/results/part_leaf/graphs/search_only
# search ล้วน ทุก scheme ไม่ดึงไฟล์ (SE-COLLAB / Du จากรอบ w4 / w5)
../.venv/bin/python -m bench_split.plot_search --amtp $D/amtp --base $D --no-fetch $D/../data_no_fetch --out ../baselines/results/part_leaf/graphs/search_no_fetch
# paper: โฟลเดอร์ชั่วคราวที่มี data/* + amtp_exp3 (new_new/data/fill) + chen_exp3 (gamma_with_v/chen) + splitmerge_* (runs/cloud/prune_w2..w5)
.venv/bin/python baselines/plot_paper.py <tmp> --out baselines/results/part_leaf/graphs/paper
```

รายละเอียดและตัวเลข: `docs/reports/2026-11-17-search-tree-part-leaf.md`

## รูป Exp. 1 สำหรับ paper (`graphs/exp1/`)

รูปละ 2 แผง ไม่มี title (ใช้ caption ใน LaTeX) · มีทั้ง `.png` และ `.pdf` · legend เรียง AMTP, Chen, SE-COLLAB, Du ทุกรูป

| ไฟล์ | (a) search อย่างเดียว ไม่มี proof ไม่ดึงไฟล์ | (b) end-to-end |
|---|---|---|
| `search_1_1_vs_kQ` | x = kQ 1–20, 100k ไฟล์ | เหมือนกัน |
| `search_1_2_vs_files` | x = 10k–125k ไฟล์, kQ 5 | เหมือนกัน |

Boolean หลายโดเมน (Search 2.1: 4 โดเมน × 100k ไฟล์, kQ 2–16, query โดเมนละหนึ่งอัน) · AMTP vs SE-COLLAB (baseline เดียวที่ทำ Boolean หลายโดเมน) · เฉพาะ 2 shape ที่ซ้อนกัน: AND-of-OR `(A ∨ B) ∧ (C ∨ D)` และ OR-of-AND `(A ∧ B) ∨ (C ∧ D)` (AND / OR ล้วนยังอยู่ใน `search_no_fetch/Search_2.1/` และ `paper/ex1_search/Search_2.1/`)

| ไฟล์ | แผง |
|---|---|
| `search_2_1_nested_end_to_end_vs_kQ` | end-to-end (2 แผง) |
| `search_2_1_nested_search_vs_kQ` | search อย่างเดียว ไม่มี proof ไม่ดึงไฟล์ (2 แผง) |
| `search_2_1_nested_vs_kQ` | ทั้งสองแบบ (a–b search, c–d end-to-end) |
| `search_2_1_nested_server_vs_kQ` | server time ทั้งหมด (search + proof + fetch, `server_total`) 2 แผง |
| `single/search_2_1_<shape>_<search\|server\|end_to_end>_vs_kQ` | แผงเดียวต่อไฟล์: 2 shape × 3 แบบ = 6 ไฟล์ |

(a) AMTP `server_search_pf`, Chen `server_total` จาก `data/` · SE-COLLAB / Du `search_no_fetch` จาก `data_no_fetch/`
(b) `end_to_end` ของทุก scheme จาก `data/` (รอบเดียวกับ AMTP) · จุด = median ของทุก query ใน 4 โดเมน, แท่ง = IQR

```
.venv/bin/python baselines/plot_exp1.py --data baselines/results/part_leaf/data \
    --no-fetch baselines/results/part_leaf/data_no_fetch --out baselines/results/part_leaf/graphs/exp1
```

### ชุดสุดท้ายของ Exp. 1 (`graphs/exp1/final/`)

| ไฟล์ | อะไร |
|---|---|
| `exp1_a_single_search_vs_kQ` | โดเมนเดียว, search อย่างเดียว ไม่มี proof ไม่ดึงไฟล์, AMTP vs Chen / SE-COLLAB / Du |
| `exp1_b_single_end_to_end_vs_kQ` | โดเมนเดียว, end-to-end, ทุก scheme |
| `exp1_c_multi_AND_of_OR_end_to_end_vs_kQ` | 4 โดเมน, `(A ∨ B) ∧ (C ∨ D) …`, end-to-end, AMTP vs SE-COLLAB |
| `exp1_d_multi_OR_of_AND_end_to_end_vs_kQ` | 4 โดเมน, `(A ∧ B) ∨ (C ∧ D) …`, end-to-end, AMTP vs SE-COLLAB |
| `exp1_all_4` | ทั้ง 4 รูปเป็น 2 × 2 (a)–(d), legend เดียวด้านบน |

หมายเหตุ: ที่ kQ = 2 ชุด query ของ AND-of-OR คือ `(A ∨ B)` (OR ล้วน ตัด partition ไม่ได้ จึงช้ากว่า kQ = 4) และของ OR-of-AND คือ `(A ∧ B)` (AND ล้วน)

## รูป Exp. 2 (verify) สำหรับ paper (`graphs/exp2/`)

`baselines/plot_exp2.py --data baselines/results/part_leaf/data --out baselines/results/part_leaf/graphs/exp2` · png + pdf · ไม่มี title

| ไฟล์ | อะไร |
|---|---|
| `exp2_a2_attack_types_detected` | สรุปในแผงเดียว: จำนวนชนิดการโจมตี (จาก 4) ที่จับได้ทุกรอบ vs t (แบบเดียวกับ `story/main/detection_vs_tampered` แต่ไม่มี title และใช้ข้อมูลรอบนี้) |
| `exp2_b_single_verify_vs_results` | โดเมนเดียว: เวลาตรวจของผู้ใช้ vs ไฟล์ที่ได้กลับ, ทุก scheme |
| `exp2_c_multi_verify_vs_results` | หลายโดเมน: เวลาตรวจ vs ไฟล์ที่ได้กลับ, AMTP vs SE-COLLAB |
| `exp2_bc` | (b) และ (c) คู่กัน |

`extra/` (ไม่ใช้ใน paper เก็บไว้ดูละเอียดหรือใช้ในสไลด์):

| ไฟล์ | อะไร |
|---|---|
| `extra/exp2_a_tamper_detection` | % ที่จับได้ vs t แยก 4 แผงตามชนิดการโจมตี (เส้นที่ 0% / 100% วาดเลื่อนเล็กน้อย; ค่าจริงใน `figure_points.csv`) |
| `extra/exp2_tamper_bars` | กราฟแท่ง (เจ้าของขอ): % ที่จับได้ต่อชนิดการโจมตี รวมทุก t, แท่งละ scheme, `n/a` = ใช้กับ scheme นั้นไม่ได้, กลุ่มสุดท้าย = ไม่โกง (แจ้งเตือนผิด 0% ทุกตัว) |

## รูป Exp. 4 (ablation ของ update cost) (`graphs/exp4/`)

`baselines/plot_exp4.py --runs baselines/results/runs/cloud --out baselines/results/part_leaf/graphs/exp4` · ข้อมูลรอบ prune เฉพาะ θ_max 64 (`runs/cloud/prune_w2`, `prune_w5`, commit `767289c`; θ 128 / 256 ใน `prune_w3`, `prune_w4` ไม่ได้ใช้ตามที่เจ้าของเลือก), รันรอบเดียวต่อ variant

| ไฟล์ | อะไร |
|---|---|
| `exp4_a_update_vs_batch` | เวลา update ต่อ batch vs batch (θ_max 64) AMTP / Static-MT / Global-MT(v), median เลื่อน 25 batch |
| `exp4_b_cumulative_vs_batch` | เวลา update สะสม (ชั่วโมง) vs batch (θ_max 64): AMTP 0.9 h, Static-MT 5.9 h, Global-MT(v) 13.8 h |
| `exp4_c_hash_vs_batch` | ข้อมูลที่ hash ต่อ batch (MB) vs batch (θ_max 64): งานเบื้องหลังเวลาใน (a) |
| `exp4_d_maxpart_vs_batch` | partition ใหญ่สุด vs batch (θ_max 64): เหตุที่ Static-MT ช้าลง |
| `exp4_all_4` | (a)–(d) แบบ 2 × 2 |

### Exp. 1 แบบ server search time อย่างเดียว (`graphs/exp1/final_search/`) · ที่เจ้าของเลือกใช้ใน paper

ข้อมูลเดียวกับ (a) ของ `final/` (ไม่มี proof ไม่ดึงไฟล์) แต่แกน y เขียน "Server search time (ms)" ส่วนที่ไม่รวมบอกใน caption · ไม่มีแผง end-to-end

| ไฟล์ | อะไร |
|---|---|
| `exp1_a_single_search_vs_kQ` | โดเมนเดียว AND, ทุก scheme |
| `exp1_b_multi_AND_of_OR_search_vs_kQ` | 4 โดเมน, AND-of-OR, vs SE-COLLAB |
| `exp1_c_multi_OR_of_AND_search_vs_kQ` | 4 โดเมน, OR-of-AND, vs SE-COLLAB |
| `exp1_search_3` | (a)–(c) แถวเดียว legend ด้านบน (สำหรับ `figure*` เต็มความกว้างหน้า) |
