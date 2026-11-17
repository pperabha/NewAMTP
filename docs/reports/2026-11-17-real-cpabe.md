# CP-ABE จริง (BSW07) แทน policy key wrap

วันที่ 17 พ.ย. 2026 · branch `feat/real-cpabe` (แตกจาก main `e528855`)

## ทำอะไร

อาจารย์ขอให้ใช้ของจริงแทนตัวจำลอง รอบนี้ทำ **CP-ABE** ก่อน (Root Anchor บน blockchain และ ABS ทำรอบถัดไป)

- `amtp_code/amtp/core/cpabe.py` (ใหม่): CP-ABE แบบ **BSW07** (Bethencourt, Sahai, Waters, IEEE S&P 2007)
  จาก Charm บน curve **SS512** (curve เดียวกับ SE-COLLAB) การคำนวณ pairing ทำใน library C (PBC, GMP)
  Charm เป็นแค่ตัวเชื่อมกับ Python
- ทำเป็น KEM/DEM เพราะ CP-ABE เข้ารหัส element ของ G_T ไม่ใช่ bytes:
  `M ← G_T`, `C_abe = BSW07.Enc(PK, M, A_d)`, `k = SHA-256(M)`, `C_Kd = <C_abe, AES-GCM_k(K_d)>`
  สมการ (2)–(4) ในเปเปอร์ไม่ต้องเปลี่ยน
- interface เหมือนตัวจำลองเดิม (`wrap`, `user_keys`, `unwrap`) เลือกด้วย env
  `AMTP_CPABE=bsw07` (ค่าเริ่มต้น `wrap` = ตัวจำลองเดิม) ผ่าน `make_authority()` ใน `core/crypto.py`
- ชื่อ attribute: Charm ใช้ `_` เป็นตัวแบ่ง index ภายใน จึงแปลงชื่อเป็นตัวพิมพ์ใหญ่ และ escape ตัวอักษรอื่น
  (รวม `Q`) เป็น `Q` + hex สองหลัก (`lab_b` → `LABQ5FB`) แบบหนึ่งต่อหนึ่ง

## ไฟล์ที่เปลี่ยน

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| `amtp/core/cpabe.py` | ใหม่: BSW07 KEM/DEM, แปลง policy เป็นรูปแบบของ Charm |
| `amtp/core/crypto.py` | `make_authority()` และ `unwrap()` รองรับ blob แบบ `bsw07` |
| `amtp/scenario.py`, `bench/experiments.py`, `demo_v2/client_app.py` | `AttributeAuthority()` → `make_authority()` |
| `demo_v2/common.py` | ถ้า `AMTP_CPABE=bsw07` แถบ "Stand-ins" ในหน้า demo ไม่แสดงบรรทัด CP-ABE |
| `demo_v2/README.md` | วิธีเปิด demo ด้วย CP-ABE จริง |
| `bench/cpabe_bench.py` | ใหม่: วัดต้นทุน CP-ABE |
| `tests/test_cpabe.py` | ใหม่: 10 test |

ไม่ได้แตะ engine, index, proof หรือ Phase 5 checks (CP-ABE อยู่นอกการตรวจทั้งหมด)

## ผลวัด (Mac Intel, median 15 ครั้งหลัง warm-up 3 ครั้ง)

`baselines/results/cpabe/cpabe_costs.csv` (+ manifest) · policy = AND ของทุก attribute

| attribute | Setup | KeyGen | Enc (ต่อไฟล์) | Dec (ต่อไฟล์) | ขนาด C_Kd |
|---|---|---|---|---|---|
| 1 | 17.9 ms | 6.0 ms | 7.7 ms | 4.7 ms | 1,524 B |
| 2 | 18.1 ms | 11.8 ms | 13.7 ms | 8.1 ms | 1,976 B |
| 5 | 19.4 ms | 26.1 ms | 27.3 ms | 14.9 ms | 3,260 B |
| 10 | 17.7 ms | 52.4 ms | 52.2 ms | 26.7 ms | 5,288 B |
| 20 | 18.5 ms | 93.5 ms | 97.7 ms | 48.9 ms | 9,276 B |

ตัวจำลองเดิม: Enc 0.02–0.42 ms, Dec 0.004–0.15 ms, 159–3,217 B

ต้นทุนโตแบบเส้นตรงตามจำนวน attribute ตามที่ BSW07 ควรเป็น ตัวเลขนี้เป็นของ Mac ยังไม่ได้วัดบน AWS

## ผลต่อการทดลองในเปเปอร์

- **ไม่ต้องรันใหม่:** CP-ABE ใช้แค่ตอนเข้ารหัสไฟล์ (Phase 1) และตอนถอด (หลัง Phase 5) ไม่อยู่ใน search, proof,
  verify หรือ update ที่กราฟวัด
- **ผลข้างเคียงที่ต้องบอก:** C_Kd ใหญ่ขึ้น (~1.5 KB ที่ 1 attribute เทียบ 159 B) ทำให้ CT_d ใหญ่ขึ้น
  เวลา hash ciphertext ตอน verify (33% ของเวลา verify ที่ ~1,000 ไฟล์) จะเพิ่มตามขนาด ผลในเปเปอร์ยังวัดด้วย
  ตัวจำลอง ถ้าจะใส่ในเปเปอร์ให้เขียนว่า "experiments use the stand-in; real BSW07 costs are reported
  separately"

## การตรวจ

- `amtp_code`: `pytest -q` ผ่าน 556 ทั้งโหมดเดิม และ `AMTP_CPABE=bsw07` ผ่าน 556
- `tests/test_cpabe.py` (10 test): ถอดได้เมื่อ attribute ตรง, ไม่ได้เมื่อไม่ตรง, key จาก DA อื่นไม่ได้,
  blob ที่ถูกแก้ไม่ได้, **collusion resistance** (สองคนรวมกุญแจกันแล้วต้องเปิด AND ไม่ได้) และยืนยันว่าตัวจำลอง
  เดิม**สอบตก**ข้อนี้, CT bytes, และ Phase 1 → 5 ครบบน scenario world
- `demo_v2/tests`: 33 ผ่าน ตัวที่เหลือ `test_core_code_is_untouched` ตกเพราะมีไฟล์ใน `amtp_code` ยังไม่ commit
  จะผ่านหลัง commit
- demo จริงด้วย `AMTP_CPABE=bsw07` (300 ไฟล์ × 2 domain, port 8201): search ผ่านทุก check และถอดไฟล์ได้
  (`status: open`), เข้ารหัสราว 10 ms ต่อไฟล์

## วิธีรันซ้ำ

```bash
cd amtp_code
../.venv/bin/python -m pytest -q tests/test_cpabe.py
AMTP_CPABE=bsw07 ../.venv/bin/python -m pytest -q
../.venv/bin/python -m bench.cpabe_bench --out ../baselines/results/cpabe
cd .. && AMTP_CPABE=bsw07 ./demo_v2/run_demo.sh --files-per-domain 500
```

ต้องมี Charm (`charm-crypto-framework==0.62` + GMP, PBC) ตาม `baselines/README.md`

## สถานะ / ยังไม่ทำ

- ค่าเริ่มต้นยังเป็นตัวจำลอง (ผลเก่ารันซ้ำได้เหมือนเดิม)
- ยังไม่ได้วัดบน AWS และยังไม่ได้แก้เปเปอร์ (Setup และตารางต้นทุน) ต้องให้อาจารย์อนุมัติก่อน
- รอบถัดไป: Root Anchor เป็น Solidity contract (Hardhat ในเครื่อง + Sepolia testnet) และ ABS
