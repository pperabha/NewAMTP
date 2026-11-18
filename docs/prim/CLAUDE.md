# บันทึกของ Prim (คน B) — ให้ Claude ของ Prim อ่านต่อจากไฟล์นี้

ไฟล์นี้เป็นของคน B เท่านั้น (คน A ไม่ต้องแก้) · `CLAUDE.md` ที่ root เป็นของคน A คนเดียว:
ถ้าต้องการเปลี่ยนอะไรใน `CLAUDE.md` ให้บอกใน PR แล้วให้คน A เป็นคนแก้

## ตัวตนและกติกาของ Prim (ตั้งเมื่อ 18 พ.ย. 2026)

- Prim = **คน B**, GitHub `PrimRoseEverD`; คน A = เจ้าของงาน `ApiSom-o`
- commit: `git -c user.name=PrimRoseEverD -c user.email=6622780631@g.siit.tu.ac.th commit ...`
  ไม่มี "Claude", `Co-Authored-By` หรือลิงก์ session (กฎ R8)
- เสร็จ 1 task → commit + push + เปิด PR เข้า `feat/paper32-experiments` ได้เลยไม่ต้องถาม, ชื่อ PR ขึ้นต้นด้วย task id,
  แท็ก `@ApiSom-o`; ห้าม merge เอง
- ต้องตัดสินใจ → เปิด issue `Decision: ...` แท็กทั้งสองคน
- หลังเปิด PR หรือ issue ทุกครั้ง → **เตือน Prim ให้ไลน์บอกคน A** พร้อมลิงก์
- แก้ได้เฉพาะไฟล์ของ B: `amtp_code/amtp/core/`, `amtp_code/tests/test_abs*.py`, `amtp_code/bench/abs_bench.py`,
  `chain/`, paper, `docs/prim/`, report ของตัวเองใน `docs/reports/`
- งานและสิ่งที่ตกลงแล้วทั้งหมด: `docs/PAPER32_START_HERE.md` (อ่านก่อนทุกครั้ง)

## งานของ B (deadline ส่ง conference 19 พ.ย. 2026 21:00)

| # | งาน | กำหนด | สถานะ |
|---|---|---|---|
| B1+B2 | ABS จริง MPR (ePrint 2008/328 §3.2) บน Charm BN254, `AMTP_ABS=mpr`, test, bench | 02:00 | ✅ ทำแล้ว branch `feat/real-abs` (ดู log ด้านล่าง) |
| B3 | Sepolia | – | ❎ คน A ทำเอง (#42 = บัญชีเดียว) ไม่ต้องแตะ key / `.env` |
| B4 | Overleaf: ไฟล์ `docs/paper32_overleaf_B4.tex` แบบ หน้า / ค้น / ลบ / วาง | 15:00 | ⏳ |
| B5 | ใส่กราฟ + ผล (คน A ส่งให้ ~17:00) | 21:00 | ⏳ |
| B6 | clean repo (PR แยก, หลังส่ง) | หลังส่ง | ⏳ |

## สิ่งที่ตกลงแล้ว (ย่อ; ฉบับเต็มใน START_HERE)

- ABS curve **BN254**; **σ_d = σ_op ของคำขอ insert** (เซ็นครั้งเดียว + ประโยคใน paper ข้อ 9a); policy
  `domain:Di AND role:owner` ทั้ง insert และ delete (#43)
- σ_root = ECDSA ที่ contract ตรวจ (ไม่ใช่ ABS); CP-ABE = BSW07 SS512
- dataset arXiv v4, Exp 2 = 100k, reps 10 + warm-up 3, รายงาน **mean** (#46)

## Log

### 18–19 พ.ย. 2026 (B1+B2)

- ติดตั้ง GMP + PBC + Charm 0.62 ใน container (Python 3.12 `.venv`), pytest เดิม 561 passed
- เขียน `amtp_code/amtp/core/abs.py` ตามสูตร §3.2 ของ MPR (Setup, AttrGen, Sign, Verify), span program
  แบบ Lewko–Waters, G = G1 / H = G2 ของ BN254
- `crypto.Signer(domain=None)` เลือกตาม `AMTP_ABS` (`ed25519` ค่าเริ่มต้น / `mpr`), `sig_ok` ตรวจได้ทั้งสองแบบ
- เจอ: Charm แปลงจุด all-zero กลับเป็น identity ไม่ได้ แล้ว pairing ทำให้ process **crash** → `_unpack`
  ปฏิเสธ identity และ element ผิด group ก่อนถึง pairing (test ครอบคลุมทุกช่อง)
- BN254 ใน Charm/PBC ช้า: pairing ~22 ms → verify ~175 ms ต่อลายเซ็น (MNT224 ~4 ms, SS512 ~0.7 ms ต่อ pairing)
  ต้องแจ้งคน A เพราะทุก update request ถูก verify 2 ครั้ง (CS + DO)
- จุดที่คน A ต้องทำ: `owner.py:49` และ `bench/experiments.py:198` ส่งชื่อ domain เข้า `Signer(domain)`
  (ตอนนี้ไม่ส่ง จึงใช้ policy `domain:default AND role:owner`; ขนาดและเวลาเท่ากัน แต่ชื่อ domain ใน Υ ไม่ตรง)
