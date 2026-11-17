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

## ทำซ้ำ

```
D=$PWD/baselines/results/part_leaf/data; M=<repo>/baselines/results
cd amtp_code && ../.venv/bin/python -m bench_split.plot_search --amtp $D/amtp --base $D --out ../baselines/results/part_leaf/graphs/search_only
# paper: โฟลเดอร์ชั่วคราวที่มี data/* + amtp_exp3 (new_new/data/fill) + chen_exp3 (gamma_with_v/chen) + splitmerge_* (runs/cloud/prune_w2..w5)
.venv/bin/python baselines/plot_paper.py <tmp> --out baselines/results/part_leaf/graphs/paper
```

รายละเอียดและตัวเลข: `docs/reports/2026-11-17-search-tree-part-leaf.md`
