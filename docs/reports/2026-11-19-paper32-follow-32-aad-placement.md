# โค้ดให้ตรง (32): AAD ของไฟล์ (#48) และ placement group นอก U_ins (#49)

- **#48 = A:** `aad_d = Encode(i, id_d)` ตามสมการ (2) ของ (32) (เดิมมี policy ด้วย)
  - แก้ `amtp/owner.py` `encrypt`, `bench/experiments.py` (encrypt, encrypt_version), `bench/workload.py`, `amtp/user.py` `decrypt`
    (ไม่คืน policy ใน item แล้ว ไม่มีที่ไหนใช้), `tests/test_ct_bytes.py`
  - ความปลอดภัยไม่ลด: CT_d ทั้งก้อนถูก hash เป็น cid_d ใน Merkle tree และ policy ถูกผูกใน ciphertext ของ BSW07
- **#49 = A:** U_d / U_ins ตาม (8) / (10) ไม่มี g_d และลายเซ็น σ_op ไม่ครอบ g_d
  - placement group ย้ายไปเป็น field `bucket` ของคำขอ (ข้าง `U`, `sig`) = input ของ placement policy ของ CS ฝั่งเดียว
  - validator ไม่เคยใช้ bucket (ตรวจแค่ว่า partition active และ slot ถูกต้อง) จึงไม่ต้องแก้
  - แก้ `amtp/update.py` `enc_request`, `amtp/server.py`, `amtp/owner.py` `insert_request`, `bench/experiments.py` `insert_request`,
    `tests/test_update_protocol.py`; ex4 (`bench/ablation.py`) ใช้ engine ตรงๆ จึงไม่กระทบ skew
- ทดสอบ: pytest 561 passed (ค่าเริ่มต้น) / 561 passed (`AMTP_CPABE=bsw07`); demo_v2 tests 34 passed (หลัง commit)
- ผลต่อ paper: **ห้ามวาง somo 1.1 และ 1.2** (ไม่ต้องแก้สมการ (2), (8), (10))
