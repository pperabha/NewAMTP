# Search Tree leaf by partition (แบบ ก) และรอบ cloud "part leaf"

วันที่ 17 พ.ย. 2026 · branch `feat/search-tree-part-leaf`

## ทำไม

ตัวเลข search อย่างเดียวของ paper ใช้แบบ partition ก่อน (`2026-11-16-summary-all-changes.md` หัวข้อ 3) ผลบน cloud รอบ split (`00f9d42`) **ชนะ SE-COLLAB และ Du ทุกจุด แต่แพ้ Chen ทุกจุด** (1.4–2.3×)

**ต้นเหตุ:** leaf ของ B+ tree เก็บ posting เป็น list `[(PID, [(cid, ℓ), ...]), ...]` ถ้าจะรู้ว่าคำอยู่ partition ไหนต้องไล่ทั้ง list ทุก query ที่ kQ = 20 ขั้นนี้ (focus) ใช้ 56% ของเวลา search

## ทำอะไร

### 1. โค้ด: flag `AMTP_PART_LEAF` / `--part-leaf` (ค่าเริ่มต้นปิด)

| ไฟล์ | แก้อะไร |
|---|---|
| `amtp/index.py` | flag + class `PartPosting(list)`: list เดิม + `pids` (frozenset ของ PID) + `at` (PID → ตำแหน่งใน list) ใช้กับคำที่อยู่ตั้งแต่ `KEEP_MIN_PARTS` (= 3) partition ตอนสร้าง snapshot |
| `amtp/server.py` | `_and_plan` ใช้ `pids` แทนการสร้างเซตทุก query · `_focus_evidence` ใช้ `at` และ `bisect(..., key=)` บน list |
| `bench_split/search_only.py` | แบบ partition ก่อนใช้ `pids` / `at` ของ leaf จริง จึงวัดโครงสร้างของ server จริง |
| `bench/experiments.py`, `bench/ablation.py`, `baselines/amtp_dataset.py` | option `--part-leaf` และบันทึก `amtp_part_leaf` ลง manifest |
| `tests/test_part_leaf.py` | test ใหม่ 25 ตัว |

**ไม่เปลี่ยน:** Cuckoo filter, ตัว B+ tree, γ / ρ / IMT, proof และ wire format, ฝั่งผู้ใช้, Validator, engine / update, โค้ดของ baseline

**ความปลอดภัยไม่เปลี่ยน:** Search Tree ไม่ใช่หลักฐานและไม่ส่งให้ผู้ใช้ ผู้ใช้ยังตรวจทุกอย่างผ่าน γ, ρ, IMT, Merkle และ root ที่ anchor รับรอง ถ้า leaf ผิด ผู้ใช้จะปฏิเสธ · ไม่เปิดเผยข้อมูลใหม่ (server รู้อยู่แล้วว่า token อยู่ partition ไหน) · snapshot สร้างใหม่ทุก epoch จึงถูกต้องหลัง insert / delete / split / merge

**test:** response JSON เหมือนเดิมทุก byte เมื่อเปิด/ปิด flag ใหม่ ร่วมกับ flag เดิม 3 ชุด (12 query × 3 ชุดข้อมูล ใช้ focus evidence จริง) · การโจมตีทุกแบบยังถูกจับ · pytest: 545 passed (ปิด flag), 542 passed (เปิดทุก flag) · หลัง merge main ล่าสุดผ่านเท่าเดิม

### 2. SE-COLLAB เขียนตัวจับเวลาของตัวเองลง CSV

`se_collab_sim.py` จับเวลา `bpl_retrieval`, `boolean_eval`, `result_fetch` แยกไว้อยู่แล้ว แต่เขียนแค่ผลรวม `search_core` แก้ให้เขียนทั้ง 3 ตัวและ `search_no_fetch` = `bpl_retrieval + boolean_eval` (แก้แค่ส่วนเขียนผล ไม่แตะการทำงาน)

### 2b. Du: คอลัมน์ `search_no_fetch` (เพิ่ม ไม่แก้ของเดิม)

`du_et_al_sim.py` เพิ่ม `CloudServer.match_slots` (DFS เดิมด้วย `_match` แต่เก็บแค่ `node.slot` ไม่ส่งไฟล์ ไม่ทำ proof) และ `DuScheme.search_no_fetch` · `run_query` เรียกหลัง query ปกติจบ (ไม่กระทบตัวเลขเดิม) และ assert ว่า slot ตรงกับผล search ปกติทุก query · เขียน `search_no_fetch` (cloud ที่ช้าสุด) และ `search_no_fetch_sum`

### 3. กราฟ search อย่างเดียว (`bench_split/plot_search.py`)

Chen ไม่ส่งไฟล์กลับ ส่วน SE-COLLAB และ Du ส่ง กราฟโดเมนเดียวจึงมี 3 แบบ: `_no_fetch` (AMTP vs Chen), `_with_fetch` (AMTP vs SE-COLLAB, Du), `_all` (ทุก scheme, AMTP 2 เส้นที่บอกว่าเทียบกับใคร) · กราฟ exp5 search อย่างเดียว

## วัดบน Mac ก่อนขึ้น cloud (ใช้ตัดสินใจเท่านั้น) · `baselines/results/runs/mac_part_leaf/`

search1 D1, 10k / 50k / 100k, เปิดทุก flag, Chen บนเครื่องเดียวกัน (ms, ไม่รวม fetch):

| N, kQ | ก่อน | แบบ ก | Chen |
|---|---|---|---|
| 100k, 1 | 0.0038 | 0.0037 | 0.0062 |
| 100k, 5 | 0.0193 | 0.0145 | 0.0301 |
| 100k, 20 | 0.0980 | 0.0518 | 0.1205 |

- คอลัมน์ที่ไม่ใช่เวลา (proof_bytes, response_bytes, hash, rQ, pQ, sQ) ตรงกันทุกแถว (160 แถว)
- **snapshot (100k, tracemalloc):** 1,279 → 1,359 MB (+80 MB, +6%) · เวลาสร้าง 16.7 → 17.0 s (+1.5%) · 82,995 จาก 1,082,038 คำใช้ leaf ใหม่
- เวลาสร้าง snapshot ไม่ถูกนับใน update ของ ex3 / ex4 / ex5 (ตรวจโค้ดแล้ว: `finalize_update(snapshot=False)` และ ex4 สร้างตอน query checkpoint นอกช่วงจับเวลา)
- `git_dirty: true` เพราะวัดก่อน commit

## รอบ cloud "part leaf" (`d25616b`, 17 พ.ย. 01:52–04:46)

AMTP เปิดทุก flag เหมือนรอบ prune + `AMTP_PART_LEAF=1` · **baseline ทุกตัววัดใหม่บนเครื่องเดียวกับชุด AMTP ที่อยู่กราฟเดียวกัน** (โค้ดและคำสั่งเหมือนรอบหลัก) รันต่อกันทีละงาน · ex3 / ex4 ไม่รันใหม่ (โค้ด update ไม่เปลี่ยน)

| เครื่อง | ชุด |
|---|---|
| w1 | AMTP search1, xsearch, exp5 · Chen / SE-COLLAB / Du search1 · SE-COLLAB xsearch, exp5 |
| w2 | AMTP xdomains, xverify · SE-COLLAB xdomains, xverify |
| w3 | AMTP, Chen, SE-COLLAB, Du verify1 และ tamper |

ตรวจแล้ว: ทุก manifest เป็น `d25616b`, `git_dirty: false`, `amtp_part_leaf: true` · pytest บนเครื่องผ่านก่อนเริ่ม · ไม่มี FAIL · จุดตรวจผ่านทุก query

### ผล search อย่างเดียว (ms)

**Search 1.1 (N = 100k):**

| kQ | AMTP ไม่ fetch | Chen | AMTP + fetch | SE-COLLAB | Du |
|---|---|---|---|---|---|
| 1 | **0.0072** | 0.0082 | **0.0149** | 0.200 | 0.233 |
| 5 | **0.0245** | 0.0352 | **0.0288** | 0.261 | 0.385 |
| 10 | **0.0511** | 0.0665 | **0.0561** | 0.321 | 0.746 |
| 20 | **0.1034** | 0.1293 | **0.1098** | 0.442 | 1.458 |

**Search 1.2 (kQ = 5):** AMTP ไม่ fetch 0.0219 → 0.0254 เทียบ Chen 0.0220 → 0.0387 (10k → 125k) · AMTP + fetch 0.026 → 0.030 เทียบ SE-COLLAB 0.076 → 0.309 และ Du 0.308 → 0.390

- **ชนะทั้ง 3 baseline ทุกจุด** เมื่อเทียบคู่ที่ทำงานเท่ากัน (Chen กับเส้นไม่ fetch, SE-COLLAB และ Du กับเส้น + fetch)
- **ที่ 10k ไฟล์สูสีกับ Chen** (0.0219 เทียบ 0.0220) ต้องเขียนใน paper
- ถ้าเอาเส้น + fetch ไปเทียบกับ Chen จะแพ้ที่ kQ 1–2 และ 10k–25k (Chen ไม่ดึงไฟล์เลย)

**หลายโดเมน (เทียบ SE-COLLAB `search_core`):**

| กราฟ | ผล |
|---|---|
| exp5 (ค้นโดเมนเดียวเมื่อมี D โดเมน) | **ชนะทุก D** (0.045 เทียบ 0.075) |
| Search 2.1 AND, AND-of-OR, OR-of-AND | **ชนะทุกจุด** (AND-of-OR kQ 16 พลิกเป็นชนะ: 0.52 เทียบ 0.95) |
| Search 2.1 OR | แพ้ที่ kQ ≥ 4 (27.4 เทียบ 5.0 ms ที่ kQ 16: ดึง ciphertext หลายพันไฟล์) |
| Search 2.2 (ส่ง query ทุกโดเมน) | ชนะถึง 8 โดเมน (เดิมถึง 4) แพ้ที่ 16, 32 (0.32 / 0.64 เทียบ 0.16 / 0.22) |

### ผลอื่น (ทุก scheme บนเครื่องเดียวกัน)

| | AMTP | Chen | SE-COLLAB | Du |
|---|---|---|---|---|
| end-to-end search1 kQ 20 (ms) | 2.15 | 11.87 | 9.66 | **1.82** |
| end-to-end search1 kQ 1 (ms) | **0.35** | 0.36 | 9.34 | 0.49 |
| server รวม proof Search 2.2 D 32 (ms) | **5.55** | – | 5.58 | – |
| tamper: modify / hide / inject / old_version | 360/360 ทุกแบบ | – / 360 / 360 / – | 360 / 0 / 0 / 360 | 360 / 360 / 0 / 360 |
| แจ้งเตือนผิด | 0/60 | 0/60 | 0/60 | 0/60 |

- end-to-end ชนะ SE-COLLAB ทุกจุด ชนะ Chen ที่ kQ ≥ 2 (kQ 1 เกือบเท่ากัน) **ยังแพ้ Du ที่ kQ ≥ 2** (งานตรวจของผู้ใช้ ซึ่งแบบ ก ไม่ได้แตะ)
- server รวม proof ของ Search 2.2 ชนะทุก D แต่ที่ 32 โดเมนเฉียดมาก

## search ล้วน ทุก scheme ไม่ดึงไฟล์ (เครื่อง 4 SE-COLLAB `0ada140`, เครื่อง 5 Du `331d608`)

ทั้ง 2 เครื่องจบ `rc=0`, clean, ไม่มี FAIL · SE-COLLAB 4 ชุด, Du 880/880 แถว ok · กราฟ `baselines/results/part_leaf/graphs/search_no_fetch/` (AMTP เส้นเดียว `server_search_pf`, Chen `server_total`, SE-COLLAB / Du `search_no_fetch`)

เครื่องต่างกันเล็กน้อย: SE-COLLAB `search_core` บน w4 ช้ากว่าบน w1 1–3% · Du `server_total` บน w5 เร็วกว่าบน w1 2–7% (เข้าทาง Du) · Du `search_no_fetch` ≈ `server_total` (ต่างไม่ถึง 2%) เพราะ Du ส่งแค่ slot

| Search 1.1 (100k files, ms) | kQ 1 | 2 | 5 | 10 | 15 | 20 |
|---|---|---|---|---|---|---|
| **AMTP** | **0.0072** | **0.0131** | **0.0245** | **0.0511** | **0.0767** | **0.1034** |
| Chen | 0.0082 | 0.0158 | 0.0352 | 0.0665 | 0.0980 | 0.1293 |
| SE-COLLAB | 0.1991 | 0.2202 | 0.2613 | 0.3244 | 0.3922 | 0.4515 |
| Du | 0.2152 | 0.1866 | 0.3640 | 0.6929 | 1.0290 | 1.3523 |

| Search 1.2 (kQ 5, ms) | 10k | 25k | 50k | 75k | 100k | 125k |
|---|---|---|---|---|---|---|
| **AMTP** | **0.0219** | **0.0225** | **0.0234** | **0.0244** | **0.0245** | **0.0254** |
| Chen | 0.0220 | 0.0244 | 0.0281 | 0.0314 | 0.0352 | 0.0387 |
| SE-COLLAB | 0.0756 | 0.0988 | 0.1380 | 0.2152 | 0.2613 | 0.3135 |
| Du | 0.2879 | 0.3134 | 0.3370 | 0.3476 | 0.3640 | 0.3637 |

- **โดเมนเดียว: ชนะทั้ง 3 baseline ทุกจุด** (10k ไฟล์เกือบเสมอ Chen)
- Search 2.1 AND, AND-of-OR, OR-of-AND: ชนะ SE-COLLAB ทุกจุด
- **Search 2.1 OR: ยังแพ้ที่ kQ ≥ 4 แม้ไม่ดึงไฟล์** (kQ 4: 1.089 vs 1.062, kQ 16: 4.28 vs 1.80) · สาเหตุไม่ใช่ fetch แต่ OR ต้องรวม file set ของทุก partition ที่มีคำใดคำหนึ่ง
- Search 2.2: ชนะถึง D = 8 แพ้ที่ D 16, 32 (0.313 vs 0.143, 0.633 vs 0.192)
- Exp 5: ชนะทุก D (≈ 0.033 vs 0.066 ms)

## ผลและกราฟอยู่ที่ไหน

| อะไร | ที่ |
|---|---|
| ผลดิบจาก cloud | `baselines/results/runs/cloud/partleaf_w1..w5/` (w4 SE-COLLAB, w5 Du: รอบไม่ดึงไฟล์) |
| ผล SE-COLLAB / Du ไม่ดึงไฟล์ | `baselines/results/part_leaf/data_no_fetch/{secollab,du}/` |
| กราฟ search ล้วน ทุก scheme ไม่ดึงไฟล์ | `baselines/results/part_leaf/graphs/search_no_fetch/` |
| ผลรวม 3 เครื่อง | `baselines/results/part_leaf/data/{amtp,chen,secollab,du}/` |
| กราฟ search อย่างเดียว | `baselines/results/part_leaf/graphs/search_only/` (README บอกว่ารูปไหนเทียบกับใคร) |
| กราฟ ex1–ex5 | `baselines/results/part_leaf/graphs/paper/` (ex3 จากรอบ fill, ex4 จากรอบ prune) |
| ผลบน Mac | `baselines/results/runs/mac_part_leaf/` |

## ต้องเขียนใน paper

- 1–2 ประโยคในส่วน Search Tree: leaf ของคำที่อยู่หลาย partition เก็บชุด partition และตำแหน่ง + ต้นทุน (+6% หน่วยความจำ snapshot, +1.5% เวลาสร้าง) **ไม่มีสมการเปลี่ยน**
- นิยาม search อย่างเดียวของแต่ละ scheme และเรื่อง fetch (Chen ไม่ส่งไฟล์) · Chen มี XOR tag ต่อ entry ในลูปค้นหา (แยกไม่ได้ถ้าไม่แก้โค้ด Chen)
- baseline ของรอบนี้วัดบนเครื่องเดียวกับ AMTP
- จุดที่แพ้: OR ที่ kQ สูง, Search 2.2 ที่ 16–32 โดเมน (search อย่างเดียว), end-to-end เทียบ Du, ที่ 10k ไฟล์สูสีกับ Chen

## วิธีรันซ้ำ

```
cd amtp_code
../.venv/bin/python -m pytest -q tests/test_part_leaf.py
AMTP_PART_LEAF=1 AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 ../.venv/bin/python -m pytest -q
# cloud (เครื่องไม่มีสิทธิ์เข้า GitHub)
git bundle create newamtp_partleaf.bundle 767289c..feat/search-tree-part-leaf
WANT=<commit> BUNDLE=newamtp_partleaf.bundle bash scripts/cloud_helpers/start_partleaf.sh <1|2|3|4> <ip>
IPS="<ip1> <ip2> <ip3>" REPO=$PWD bash scripts/cloud_helpers/watch_partleaf_local.sh
# กราฟ: ดู baselines/results/part_leaf/README.md
```

## สถานะ

- โค้ด, ผล 3 เครื่อง, กราฟ: เสร็จ
- เครื่อง 4 (SE-COLLAB) และ 5 (Du) รอบไม่ดึงไฟล์: เสร็จ ดึงผลแล้ว ทำกราฟ `search_no_fetch/` แล้ว (`plot_search.py --no-fetch`) · pytest 545 passed
