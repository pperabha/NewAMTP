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
