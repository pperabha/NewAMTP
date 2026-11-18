# Root Anchor บน Ethereum (smart contract)

วันที่ 17 พ.ย. 2026 · branch `feat/chain-anchor` (แตกจาก `release/submission-cleanup` 6eda17f)
ไม่เกี่ยวกับ repo ที่ส่งอาจารย์ (`ApiSom-o/AMTP-submission`)

## ทำอะไร

paper นิยาม Root Anchor เป็น "blockchain smart contract" แต่ prototype จำลองไว้ใน process (`amtp/anchor.py`)
รอบนี้เขียนเป็น contract จริง และให้ AMTP ใช้ได้ทั้งบน chain จำลองใน process (สำหรับ test) และ network สาธารณะ (Sepolia)

| ไฟล์ | อะไร |
|---|---|
| `chain/RootAnchor.sol` | contract: เก็บ (e*, R_D) ต่อ domain, ตรวจ predecessor + e' = e* + 1 + ลายเซ็น owner แบบ atomic, คำนวณ R_G ใน contract |
| `chain/RootAnchor.json` | ABI + bytecode (solc 0.8.28, EVM cancun) commit ไว้ คนรันไม่ต้องมี compiler |
| `chain/build.py` | compile ใหม่ (py-solc-x) |
| `chain/sepolia.py` | `keys` (สร้าง key ลง `.env`), `status`, `deploy` |
| `chain/requirements.txt`, `chain/README.md` | ติดตั้ง / วิธีใช้ |
| `amtp_code/amtp/chain_anchor.py` | `ChainAnchor` ใช้แทน `RootAnchor` ได้ทันที (`register_domain`, `submit`, `latest`, `R_G`), `ChainAnchor.local()` / `from_env()` |
| `amtp_code/amtp/owner.py` | ถ้า anchor มี `root_signer` ใช้ key นั้นเซ็น σ_root (anchor เดิมไม่มี -> ใช้ Ed25519 เหมือนเดิม) |
| `amtp_code/amtp/scenario.py` | `World(anchor=...)` |
| `amtp_code/tests/test_chain_anchor.py` | 7 test (skip ถ้าไม่มี web3) |

## ตัดสินใจ

- **σ_root ใช้ secp256k1 ECDSA** เพราะ EVM ตรวจ Ed25519 ไม่ได้ในราคาที่รับได้ (ไม่มี precompile) contract ตรวจด้วย `ecrecover`
  ข้อความที่เซ็น = SHA-256(transition_message ‖ chainid ‖ address ของ contract) จึงเอาลายเซ็นไปใช้กับ chain / contract อื่นไม่ได้
  ปฏิเสธลายเซ็นที่ s สูง (malleable) · σ_op ยังเป็น Ed25519 ที่ validator ตรวจนอก chain เหมือนเดิม
- **R_G คำนวณใน contract** ตาม paper ("RA derives R*_G") hash ตรงกับ `core/hashing.py` / `core/merkle.py` ทุก byte (มี test)
- **admin** deploy, register domain และเป็นคนส่ง transaction (จ่าย gas) แต่ปลอม transition ไม่ได้ เพราะ contract ตรวจลายเซ็น owner
- ค่าเริ่มต้นยังเป็น anchor ใน process: experiment และ demo เดิมไม่เปลี่ยน
- web3 ต้องใช้ pycryptodome < 4 -> `chain/requirements.txt` ใช้ 3.24.1 (มีแค่ SE-COLLAB ที่ใช้ API เดียวกัน)

## ตรวจแล้ว

- `tests/test_chain_anchor.py` 7 passed: R_G และ digest ตรงกับ Python; ปฏิเสธ epoch ข้าม, predecessor ผิด, key ของ domain อื่น,
  ลายเซ็นบน root อื่น, ลายเซ็น malleable, replay, register ซ้ำ, คนที่ไม่ใช่ admin register, ลายเซ็นจาก contract อีกตัว;
  AMTP ทั้งระบบบน chain (update เป็น transaction, query อ่าน root จาก chain, tamper / hide / stale / replay ถูก reject)
- pytest ทั้งหมด: มี web3 550 passed · ไม่มี web3 543 passed (test chain skip) · venv ใหม่จาก `chain/requirements.txt` 550 passed

## ยังไม่ได้ทำ

- deploy บน Sepolia: รอ RPC URL และ test ETH ของ admin (key สร้างแล้วใน `.env` ของเครื่องนี้)
- วัดเวลาเขียน root ต่อ epoch (receipt / finalized), gas ต่อ epoch, เวลาอ่าน `latest()`
- demo (`demo_v2/anchor_app.py`) ใช้ chain anchor และแสดง tx hash

## รันบน Sepolia จริง (17 พ.ย. 2026)

- contract หลัก (สำหรับ D1-D4): `0xf04b5287a1Db458C4D25bef73b55fAf89AcF3Ec0`
  https://sepolia.etherscan.io/address/0xf04b5287a1Db458C4D25bef73b55fAf89AcF3Ec0
- รอบทดลอง `chain/sepolia_run.py` (world เล็ก 2 domain ของ `scenario.py`, deploy contract ใหม่):
  `0xC0051fD71465485c1FEb316BBc164d34D089f750` บันทึกใน `chain/runs/sepolia_20261117_203549.json`
  - 15 transaction (register 2, submit 13) ทุก transition ผ่าน contract บน network จริง
  - query อ่าน root จาก chain: honest -> accepted; tamper_ct / hide_posting / forge_partition / stale / replay -> rejected
    ที่ ct / papc / part / anchor / ctx; หลัง epoch ใหม่ honest -> accepted
  - เวลาเขียน root ต่อ epoch (ส่ง -> receipt 1 confirmation): median 11.6 วินาที, max 24.3 วินาที (block time ~12 วินาที)
  - gas ต่อ submit: median 89,021 · register 505k-589k (เก็บชื่อ domain + เรียง + R_G)
  - อ่าน `latest()` จาก Mac ผ่าน Alchemy: median 241 ms (รวม network) · ที่ block finalized ยังไม่เห็น domain
    เพราะ contract เพิ่ง deploy (finality ~13 นาที)
- admin ใช้ ETH ไปไม่ถึง 0.000001 จาก 0.05
