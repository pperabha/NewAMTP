# ไฟล์ LaTeX พร้อมวาง (รวม paper sync ของเพื่อน + ที่เราแก้)

วันที่ 17 พ.ย. 2026 · branch `docs/paper-latex-somo` · ต่อจาก PR #33 และ PR #34

## ทำอะไร

เพิ่ม `docs/paper_latex_2026-11-17_somo.tex`: นำ `docs/paper_sync_2026-11-16.md` (รวมการแก้ของ PR #34) มาทำเป็นไฟล์ LaTeX
ไฟล์เดียว ทุกบล็อกมีคอมเมนต์ `%` บอกตำแหน่งใน AMTP (14).pdf และหมายเหตุจากโค้ด ส่วนที่เราแก้หรือเพิ่มมีป้าย
`% >>> [SOMO 17 Nov]` (ค้นคำว่า SOMO) ไม่มีโค้ดเปลี่ยน

## ที่เพิ่ม / แก้จากไฟล์ของเพื่อน

| ข้อ | ตำแหน่งใน paper | อะไร |
|---|---|---|
| 1.4 | Phase 2 Step 1 | คอมเมนต์: fill ใช้ในทุกการทดลอง (ค่าเริ่มต้นของ class ใน library คือ least) |
| 1.12 | III-A ย่อหน้า CS / DU | LaTeX ใหม่: ASPA ตัด posting เฉพาะ conjunction และมีหลักฐานว่าไม่ได้ซ่อน component ใน partition ที่อาจมีคำตอบ |
| 1.13 | Phase 2 Step 2 | part leaf: เติม "the response is the same with or without it" + ประโยคต้นทุน (ไม่บังคับ) |
| 2.1 | IV-A | ประโยคใหม่: Cuckoo filter และ Search Tree (รวมชุด partition ใน leaf) เป็นโครงสร้างค้นหาที่ไม่ต้องเชื่อถือ ผู้ใช้ไม่ใช้ |
| 2.3 | proof ของ Lemma 1 | LaTeX ของประโยคที่เพื่อนเขียนเป็นข้อความ |
| 2.7 | proof ของ Theorem 2 | LaTeX ของประโยคที่เพื่อนเขียนเป็นข้อความ |
| 3.4 | Experimental set-up | Exp. 3–4 รันก่อนมี part leaf (ไม่เปลี่ยน update และ proof) |
| 3.5 | Dataset | หมวด D3 / D4 ครบ และเงื่อนไข abstract ≥ 30 คำ |
| 3.6 | Baselines | LaTeX ใหม่: SE-COLLAB / Du search-only วัดซ้ำบนอีก 2 instance รุ่นเดียวกัน (ต่างกันไม่เกิน 7%) |
| 3.6b | Search-only time | ชุด partition เก็บเฉพาะคำที่อยู่ ≥ 3 partition · กราฟ `part_leaf/graphs/search_no_fetch/` |

part leaf ไม่มีสมการ lemma หรือ theorem ใหม่ (leaf ไม่ใช่ evidence, response เหมือนเดิมทุก byte) อยู่ในข้อ 1.13, 2.1, 3.4, 3.6b

## เพิ่ม (รอบ 2): สมการ part leaf และคู่มือวางทีละจุด

- `docs/paper_paste_guide_2026-11-17_somo.md`: แบบเดียวกับเอกสารของเพื่อน ทุกจุดมี หน้า (AMTP (21).pdf) · ข้อความที่ต้อง **ค้นหา** ใน .tex ·
  **ลบตั้งแต่ … ถึง …** · บล็อกที่ **วางแทน** / วางต่อท้าย · 10 จุด เรียงตามหน้า ข้อความค้นหาเอามาจาก PDF (21) จริง
- part leaf เขียนเป็นสมการ: `Aux_i(h_w) = (Sel_i(h_w), pos_w)` ถ้า `|Sel_i(h_w)| ≥ 3` ไม่งั้น `⊥` (`\label{eq:part-leaf}`)
  วางหลังย่อหน้า Search Tree ใน Phase 2 Step 2 · posting state (13)–(15) และ PAPC (16)–(18) ไม่เปลี่ยน · ไม่มี lemma / theorem ใหม่
- เพิ่ม: แถว Table II, ประโยค Phase 4 Step 2 (CS อ่าน `Sel_i(h)` และ component ผ่าน `pos_h`), ข้อ 2.1 / 3.4 / 3.6b อ้าง `Aux_i`
- DU bullet (1.12) กลับไปใช้ของเพื่อน (ของเราเดิมเปลี่ยนท้ายประโยคซึ่งต่อกับข้อความเดิมของ paper ไม่ได้)
- เครื่องนี้ไม่มี LaTeX จึงยังไม่ได้ compile · ตรวจวงเล็บ / environment ครบคู่แล้ว (450/450, equation 21/21)

## วิธีใช้

เปิดไฟล์ copy ทีละบล็อกไปวางใน Overleaf ตามคอมเมนต์ที่อยู่เหนือบล็อก ไฟล์นี้ compile ทั้งไฟล์ไม่ได้ (บางบล็อกเป็นส่วนของสมการ
หรือแถวของตาราง ต้องวางใน environment เดิม) ชื่อ macro อาจต้องปรับตาม .tex จริง

## ตรวจแล้ว

- วงเล็บ `{}` ครบคู่ (428/428) และ `\begin`/`\end` ครบคู่ทุก environment (equation, align, cases, lemma, proof, theorem)
- บรรทัดที่เป็น LaTeX ไม่มีอักขระนอก ASCII

## สถานะ

- เอกสารอย่างเดียว ไม่มีโค้ดเปลี่ยน ไม่ต้องรัน pytest
- ยังค้าง (จากรายการเดิม): compile กับ .tex จริง, อาจารย์ตรวจ Lemma / Theorem 1 และอนุมัติการเปลี่ยน design, เวอร์ชัน `cryptography`, citation OXT
