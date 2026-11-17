# รายการแก้ paper ให้ตรงกับโค้ด (paper sync)

วันที่ 17 พ.ย. 2026 · branch `docs/paper-sync`

## ทำอะไร

เพิ่มไฟล์ `docs/paper_sync_2026-11-16.md`: เทียบ paper ฉบับ "AMTP (14).pdf" กับโค้ดบน main ทีละส่วน และเขียนว่าต้องแก้อะไร
แต่ละข้อมี (1) ตำแหน่งใน paper (2) โค้ดทำอะไรจริง พร้อมไฟล์/ฟังก์ชัน (3) ข้อความใหม่ (4) LaTeX ที่วางได้
ไม่มีการแก้โค้ด

## ไฟล์ครอบคลุมส่วนไหน

| หัวข้อในไฟล์ | ส่วนของ paper |
|---|---|
| 1 | System Process: Phase 1–5, Algorithm 1–3 (batch ต่อ epoch, IMT แบบ next pointer, placement group + fill, AND pruning, proof ของ partition เฉพาะไฟล์ผลลัพธ์, Search Tree leaf แบบเก็บชุด partition) |
| 2 | Security Analysis: assumption, leakage, Proposition 1 (invariant chain / order, batch), Lemma ใหม่ 2 ข้อ, Theorem 1–2 |
| 3 | Evaluation: Table III–IV, cost paragraph, experimental set-up, dataset, baselines, นิยาม search อย่างเดียว, ประโยคใน Exp. 1–5 ที่ผิดไปแล้ว |
| 4 | สิ่งที่โค้ดมีแต่ไม่ต้องแก้ paper (Cuckoo filter, batched Merkle, ดัชนีแบบ fast ที่ไม่ใช้) |
| 5 | Abstract, Introduction, Related Work, System Model, Threat Model |

ระดับความสำคัญในไฟล์: **A** = paper เขียนไม่ตรงกับโค้ด (ต้องแก้) · **B** = โค้ดมีแต่ paper ไม่มี (ต้องเพิ่ม) · **C** = แก้เล็กน้อย

## อ้างอิงโค้ดรุ่นไหน

- เขียนจาก main `00f9d42` (16 พ.ย.) และตรวจซ้ำกับ `ca09924` (17 พ.ย.)
- ระหว่างนั้นมีโค้ดใน `amtp/` เปลี่ยนแค่ PR #32 (Search Tree leaf แบบเก็บชุด partition, `AMTP_PART_LEAF`) จึงอัปเดตข้อ 1.13, 3.4, 3.6, 3.6b ตาม
- การตัดสินใจที่ใช้: search อย่างเดียวใช้แบบ partition ก่อน ไม่ใช้ดัชนีแบบ fast (`2026-11-16-summary-all-changes.md` หัวข้อ 3)

## สิ่งที่พบระหว่างแก้ paper จริง (17 พ.ย.)

- invariant (chain) และ (order) ถ้าเขียนเป็นสมการจะล้นคอลัมน์ จึงเปลี่ยนเป็นข้อความในย่อหน้า (ข้อ 2.4)
- ใน proof ของ Proposition 1 ฟังก์ชันย้ายตำแหน่งใช้ ρ ซึ่งชนกับ ρ_h ที่เป็น PAPC ให้เปลี่ยนเป็น μ (ข้อ 2.4)
- สูตร leaf ของ IMT ต้องมี next(h): `Î_h = H(h ‖ ρ̂_h ‖ next(h))` (ข้อ 1.5, 1.11)

## ยังต้องตรวจก่อนส่ง

1. LaTeX ยังไม่ได้ compile กับไฟล์ .tex จริง ชื่อ macro และ environment ต้องปรับตาม paper
2. Lemma ใหม่และ Theorem 1 ที่แก้ ควรให้อาจารย์ตรวจ
3. เวอร์ชันของ library `cryptography` บนเครื่อง cloud (ไม่ได้บันทึกใน manifest)
4. ชื่อหมวด arXiv ของ D3 และ D4 (`datasets/arxiv/select_files_v4.py`)
5. citation ของ OXT (Cash et al., CRYPTO 2013) ในข้อ 5.3
6. ส่วน AND pruning, part-results และ part leaf เป็นการเปลี่ยน design ต้องให้อาจารย์อนุมัติ

## วิธีใช้

เปิด `docs/paper_sync_2026-11-16.md` แก้ paper ตามลำดับที่แนะนำ: set-up และ dataset (3.4, 3.5) → Phase 4–5 และ Algorithm 2–3
(1.7–1.11) → Security (2.1, 2.4–2.6) → Abstract / Introduction / Threat Model (5.1, 5.2, 5.5) → ที่เหลือ

## สถานะ

- เอกสารอย่างเดียว ไม่มีโค้ดเปลี่ยน ไม่ต้องรัน pytest
- เจ้าของงานกำลังแก้ paper ตามไฟล์นี้ (ทำไปแล้ว: Phase 5 Step 2 ส่วน full และ focus evidence, Proposition 1)
