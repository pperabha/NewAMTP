# ตรวจ paper sync list กับโค้ดและผลรัน แล้วแก้ 7 จุด

วันที่ 17 พ.ย. 2026 · branch `docs/paper-sync-fixes` · ต่อจาก PR #33 (`docs/paper_sync_2026-11-16.md`)

## ทำอะไร

อ่าน `docs/paper_sync_2026-11-16.md` ทั้งไฟล์ แล้วเทียบทีละข้อกับโค้ดบน main (`d2737c2`) ผลรันใน
`baselines/results/` และสคริปต์รัน แก้เฉพาะไฟล์นี้ ไม่มีโค้ดเปลี่ยน

## ข้อที่ตรวจแล้วตรงกับโค้ด (ไม่แก้)

- 1.1 aad มี policy (`owner.py`) · 1.2 request มี bucket (`update.py enc_request`) · 1.3 Δ ผูก `H(TAG_REQUESTS, H(U_1), …)`
- 1.4 กฎ fill (`variants.py place`: เต็มสุดที่ยังต่ำกว่า θ_max, เสมอกันเลือก PID เล็ก, เต็มหมดเลือกเต็มสุด) และการใช้ช่องที่ลบแล้วซ้ำ (`engine.py`)
- 1.5 IMT แบบ next pointer, sentinel ล่างตัวเดียว, `I_⊥` (`index.py imt_leaf`, `IMT_EMPTY`)
- 1.7 / 1.11 focus set, neighbour leaf, กฎ bracketing (a)–(d), reject partition ที่เปิดเป็น neighbour อย่างเดียว (`user.py _focus_root`)
- 1.8 / 1.11 Ver_Q ต้องเรียงและไม่ซ้ำกับ descriptor, descriptor ต้องตรงกับ partition ของผลลัพธ์ (`user.py _check_partitions`)
- PAPC `ρ = H(h ‖ n_h ‖ R^post)`, `γ = H(PID ‖ v ‖ H(Enc(L)))`
- 1.13 part leaf: ≥ 3 partition (`KEEP_MIN_PARTS`), ไม่ส่งให้ผู้ใช้, response เหมือนเดิมทุก byte
- 2.8 `MAX_AGE_S = 300`
- 3.4 DHT 6 node / replica 3 (`dht.py`), θ_min = 16, G = 16, ปิด GC, Ed25519 / AES-GCM / AES-SIV / HMAC (`core/crypto.py`)
- 3.5 snapshot 3,233,620 papers, record ล่าสุด 2026-10-30, seed 42, κ = 20, RAKE 1–3 คำ
- 3.6 Chen: XOR proof ต่อ entry อยู่ในลูปค้นหา และ search ครั้งแรกยุบ chain (`chen_et_al_sim.py search`)
- 3.6b correctness gate (`bench_split/run.py`: search อย่างเดียวได้ไฟล์ไม่ตรงกับ response เต็ม → หยุด)
- 3.7 Exp. 5 ไฟล์ในโดเมนที่ค้น 5,000 (`N_target`)

## ข้อที่แก้

| # | ข้อในไฟล์ | เดิม | แก้เป็น |
|---|---|---|---|
| 1 | 3.6 | baseline ทุกตัววัดบนเครื่องเดียวกับ AMTP | กราฟไม่ดึงไฟล์ใช้ SE-COLLAB (w4) และ Du (w5) จาก instance อื่นรุ่นเดียวกัน ต่างกัน 1–7% และเข้าทาง Du |
| 2 | 3.6b | leaf เก็บชุด partition "of each key" | เฉพาะคำที่อยู่ ≥ 3 partition (แก้ทั้งข้อความและ LaTeX) |
| 3 | 3.6b | legend "AMTP (search)", กราฟแยกตาม fetch | กราฟหลักของ paper คือ `part_leaf/graphs/search_no_fetch/` (ทุก scheme ไม่ดึงไฟล์, AMTP เส้นเดียว) |
| 4 | 3.5 | D3 = astro-ph and hep, D4 = cond-mat and quant-ph | หมวดครบตาม `select_files_v4.py` + เงื่อนไข abstract ≥ 30 คำ ไม่ถูก withdraw |
| 5 | 3.4 | เปิด partition set ใน Search Tree (ทุกการทดลอง) | เพิ่มว่า Exp. 3–4 รันก่อนมี part leaf ซึ่งไม่เปลี่ยน update และ proof |
| 6 | 3.7 | Exp. 4: 1,000 batches of 100, skew 0.95 | เพิ่ม phase ลบ 65% ของกลุ่ม hot (รวม ≈ 1,674 batch), 3 รอบ, วัด query ทุก 100 batch |
| 7 | หัวไฟล์, 1.4 | fill "the default" | fill ใช้ในทุกการทดลอง (default ของ benchmark; class ใน library default `least`) · เพิ่มย่อหน้าว่า flag ของ AND pruning / greedy / part results / part leaf ปิดเป็นค่าเริ่มต้นในโค้ด แต่เปิดในทุกการรันของ paper |

ข้อ 4 ตอบรายการ "ยังต้องตรวจก่อนส่ง" ข้อ 4 ใน `2026-11-17-paper-sync.md` แล้ว

## part leaf โดยย่อ (สำหรับคนแก้ paper)

leaf ของ Search Tree สำหรับคำที่อยู่ ≥ 3 partition เก็บ (1) ชุด partition `Sel_i(h)` (2) ตำแหน่งของแต่ละ partition ใน list
server จึงหา focus set และ focus evidence ได้โดยไม่ไล่ list ทั้งเส้น · ไม่ใช่ evidence ไม่ส่งให้ผู้ใช้ ไม่มีสมการเปลี่ยน
ต้นทุน: หน่วยความจำ snapshot +6%, เวลาสร้าง +1.5% · ผล: search อย่างเดียวโดเมนเดียวชนะ Chen, SE-COLLAB, Du ทุกจุด

## สถานะ

- เอกสารอย่างเดียว ไม่มีโค้ดเปลี่ยน ไม่ต้องรัน pytest
- ยังค้างจากรายการเดิม: compile LaTeX, อาจารย์ตรวจ Lemma / Theorem 1 และอนุมัติการเปลี่ยน design, เวอร์ชัน `cryptography`, citation OXT
