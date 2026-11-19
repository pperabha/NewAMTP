# โครงการทดลองชุดใหม่ตาม paper (32) — ฉบับตกลงแล้ว

วันที่ 18 พ.ย. 2026 · branch `feat/paper32-experiments` (แตกจาก `feat/chain-anchor` ff7dcd5)
ที่มาของการตัดสินใจทั้งหมด: `docs/reports/2026-11-18-paper32-plan-real-primitives.md`

## กติกาที่ใช้กับทุกการทดลอง

| เรื่อง | ค่า |
|---|---|
| dataset | arXiv v4 ที่มีอยู่ (`datasets/arxiv/data_v4`), ไม่ใช้ Enron, ไม่ขยายถึง 10⁶ |
| ขนาด N (ไฟล์ต่อ domain) | 10k, 25k, 50k, 75k, 100k, 125k; ค่าคงที่เมื่อไม่ได้ไล่ N = 100k (`V4_FIX`) |
| รอบวัด | **reps = 10** หลัง warm-up 3 (อาจารย์สั่ง) |
| query default | 4 keyword (ตาม (32) "a query contains four keywords") |
| θ_max / θ_min | 64 / 16 (`docs/THETA_CHOICE.md`), placement = fill, query flags เปิดทั้งหมด (ค่าเริ่มต้นของโค้ด) |
| crypto จริงทั้งหมด | CP-ABE BSW07 (`AMTP_CPABE=bsw07`), **ABS จริง** สำหรับ σ_d / σ_op (ต้อง implement), Root Anchor บน Ethereum: เวลา protocol วัดบน `chain-local` ทุก ex; anchor time + gas + read latency วัดบน Sepolia ชุดแยก (#42) |
| update time | รายงาน **protocol time** (เตรียม + ตรวจ + เซ็น) แยกจาก **anchor time + gas** บน chain |
| กราฟ | line chart เท่านั้น, บอกตรงๆ ว่าแพ้ตรงไหน |

## โครง (ชื่อตาม paper (32))

```
ex1_search/                               (32) Exp 1: Boolean Search Scalability
├── Search_1.1_single_domain_vary_keywords   x = kQ ∈ {1,2,4,8,16} (AND), N = 100k        4 scheme
├── Search_1.2_single_domain_vary_files      x = N (10k–125k), kQ = 4                      4 scheme
├── Search_2.1_multi_domain_boolean          x = kQ ∈ {2,4,8,16}, 1 กราฟต่อรูปแบบ:          AMTP vs SE-COLLAB
│                                            AND, OR, (A∨B)∧(C∨D), (A∧B)∨(C∧D); 4 domain × 100k
└── Search_2.2_multi_domain_vary_domains     x = D (1–32), ไฟล์ชุดเดิมแบ่งกลุ่มใหม่            AMTP vs SE-COLLAB
    y ทุกกราฟ: server time และ end-to-end (บันทึก query gen, search-only, search+proof+fetch, verify ทุกจุด)

ex2_verify/                               (32) Exp 2: Selective Proof, Verification (+ Tamper Detection)
├── Verify_1.1_single_domain_vary_results    x = rQ (10, 100, 1,000, 10,000), N = 100k     4 scheme
├── Verify_1.2_single_domain_vary_tampered   x = จำนวนไฟล์ที่ถูกแก้ t, 4 attack             4 scheme
│                                            (modify, hide, inject, old_version): detection rate + verify time
├── Verify_2.1_multi_domain_vary_results     x = rQ รวม, 4 domain × 100k                    AMTP vs SE-COLLAB
├── Verify_2.2_multi_domain_vary_domains     x = D, y = เวลา verify อย่างเดียว               AMTP vs SE-COLLAB
│                                            คงที่: ไฟล์ชุดเดิม (100k/domain × 4 แบ่งกลุ่มใหม่) และ query ชุดเดิม -> rQ เท่าเดิม
└── Verify_3_clustered_vs_dispersed (ใหม่ ตาม (32))  N = 100k (ตัดสิน 18 พ.ย.), marker keyword ที่มีผล rQ ไฟล์ วางแบบ clustered
                                             (อยู่ใน partition น้อย) / dispersed (กระจายหลาย partition) / partition_spread;
                                             y = proof gen, verify, proof size; x = rQ หรือ sQ
                                             (โค้ดเดิม suite_exp2 + exp2_layouts.json ต้องสร้างใหม่บน v4)

ex3_update_cost/                          (32) Exp 3: Dynamic Update Scalability    AMTP vs Chen
├── (a) x = batch b ∈ {1, 10, 100, 1000}, y = ms ต่อ update (log), เส้น insert / delete, N = 100k
└── (b) x = N (10k–125k), b = 100, y = ms ต่อ update
    split / merge ไม่นับ (ตาม (32)); protocol time รวม ABS sign/verify จริง; anchor time แยกไปที่ ex5

ex4_split_merge/                          (32) Exp 4: Adaptive Partitioning under Skewed Growth
    AMTP vs Static-MT vs Global-MT(v), θ_max = 64, 10 run ต่อจุด (#45)
    3 variant วัดที่ระดับ index (`bench/ablation.py`) + เส้น AMTP ผ่าน protocol เต็ม (ABS + validator + anchor) (#44)
    เริ่ม 25k (20% ของ dataset) + insert 250 batch × 100 (→ 50k) แล้ว delete 65% ของกลุ่มร้อน (merge เกิดเฟสนี้)
    x = ระดับ skew = สัดส่วนไฟล์ใหม่ที่บังคับลงกลุ่มร้อน: 0, 0.25, 0.5, 0.75, 0.95 (ตัดสิน 18 พ.ย.)
    y = update latency, search/proof latency, verify latency, partition ใหญ่สุด, เวลา split/merge

ex5_multidomain/                          (32) Exp 5: Multi-Domain Scalability and Isolation
    x = D ∈ {1, 2, 4, 8, 16, 32}, domain เป้าหมายขนาดคงที่
    y = query, proof gen, verify, root maintenance (anchor time + gas บน Sepolia)
    update isolation: insert และ delete ลง domain เดียว, Domain Root ของ domain อื่นต้องไม่เปลี่ยน
    baseline: วัดทุกตัวที่วัดได้ (SE-COLLAB และ Du)
```

Search 2.2 / Verify 2.2 ซ้อนกับ ex5 (ทั้งคู่ไล่ D) แต่เก็บผลไว้ทั้งสองชุดในรอบรันเดียว ค่อยเลือกตอนทำกราฟ

## Exp 1: query ที่ใช้

- Search 1.1 / 1.2: ไฟล์ใหม่ `datasets/arxiv/data_v4/queries_search_single_p32.jsonl`
  สร้างด้วยวิธีเดิมของ `build_v4.py` ทุกอย่าง (AND ของ keyword จากไฟล์เดียวใน 10,000 ไฟล์แรก, 20 query ต่อ kQ ต่อ domain,
  seed เดิม) เปลี่ยนแค่ kQ เป็น 1, 2, 4, 8, 16 ตาม (32); ตรวจตัวสร้างโดยให้สร้างไฟล์เดิม (kQ 1, 2, 5, 10, 15, 20) ซ้ำได้ตรงทุก byte
- Search 2.1 / 2.2: `queries_boolean_multi.jsonl` เดิม (4 รูปแบบ × kQ 2, 4, 8, 16) ครบตาม (32) แล้ว
- ทุก scheme เลือกชุด query ผ่าน `AMTP_QUERY_SET` (`v4` = ไฟล์รอบ 17 พ.ย., `p32` = ไฟล์ใหม่ และ Search 1.2 ที่ kQ = 4)
  ใน `baselines/amtp_dataset.py` ที่เดียว และบันทึกลง manifest ทุกไฟล์ (`query_set`, `amtp_cpabe`, `amtp_anchor`)
- ตั้งค่าทั้งหมดด้วย `source scripts/paper32_env.sh` (flag ของ paper, p32, BSW07, chain-local, reps 10, warm-up 3)

## Exp 1: การอ่าน root จาก chain แยกออกจาก query gen

พอใช้ chain anchor จริง เวลา `query_gen` ของ AMTP รวมการที่ DU อ่าน (e*, R_D) จาก contract ด้วย (`anchor.latest()`
ใน `user.make_query`) ซึ่งเป็น RPC: บน EVM ในเครื่อง ~2.5 ms, บน Sepolia ~257 ms; baseline ไม่มีขั้นนี้ จึงไม่ยุติธรรม
แก้: `bench/experiments.run_query` ให้ DU อ่าน anchor ก่อนแล้วส่งค่าที่อ่านได้ (ค่าเดิมทุก byte) ให้ `make_query`
- `anchor_read_ms` = เวลาอ่าน root จาก RA (คอลัมน์ใหม่)
- `query_gen_ms` = สร้าง trapdoor อย่างเดียว (งานเดียวกับ query generation ของ baseline)
- `end_to_end_ms` = query gen + server + verify (นิยามเดิม) · `end_to_end_anchor_ms` = รวม anchor read ด้วย (คอลัมน์ใหม่)
ความปลอดภัยไม่เปลี่ยน: DU ยังอ่าน root จาก contract ทุก query และ verify กับค่านั้น

ผล smoke บน Mac (D1, 10k ไฟล์, 1 รอบ, BSW07 + chain-local, median ms): anchor_read 2.48 · query_gen 0.064 ·
search-only 0.018 · server total 0.133 · verify 0.199 · end-to-end 0.392 (รวม anchor 2.875) · CP-ABE decrypt ~2.1
(ไม่อยู่ใน end-to-end เหมือนเดิม)

ข้อเสนอ: Exp 1 / 2 (query จำนวนมาก) ใช้ contract บน EVM ในเครื่อง (`chain-local`) และรายงานเวลาอ่านบน Sepolia จริง
(~257 ms) แยกไว้ใน setup / Exp 5; การทดลองที่เขียน root (Exp 3–5) ใช้ Sepolia
**ตัดสินแล้ว (#42 = A):** เวลา protocol ทุก ex ใช้ `chain-local`; Sepolia เป็นชุดแยก (gas_domains D = 1–32 + บางจุดของ ex3)

## สถานะ

| ส่วน | สถานะ |
|---|---|
| โครงนี้ | ตกลงแล้ว 18 พ.ย. |
| ABS จริง | ยังไม่ทำ (σ_root รอคำตอบอาจารย์ ดู 5A ในรายงาน plan) |
| Exp 1 | กำลังทำ |
| Exp 2–5 | ยังไม่เริ่ม |
