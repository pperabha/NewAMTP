# AWS รอบ paper (32): เริ่ม ex4 + Sepolia root maintenance

## ex4 (เริ่ม 19 พ.ย. ~01:00)
- 5 × r7i.4xlarge (16 vCPU, 123 GiB): w1 skew 0, w2 0.25, w3 0.5, w4 0.75, w5 0.95; commit c79b2a0 (หัวของ PR #60) ผ่าน git bundle
- เครื่องละ 6 process (`scripts/paper32_ex4_machine.sh`): Global-MT(v) seeds 1–4 / 5–7 / 8–10, AMTP + Static-MT seeds 1–10,
  AMTP protocol เต็ม seeds 1–5 / 6–10; ทุกเครื่องผ่าน pytest + test ABS ก่อนเริ่ม
- เครื่องมือ (ใหม่ใน `scripts/cloud_helpers/`): `paper32_setup_venv.sh`, `paper32_start_ex4.sh`, `paper32_watch_ex4.sh`

## เหตุการณ์: venv บนเครื่อง
- `~/NewAMTP/.venv` บนเครื่องเป็นสำเนาของ `~/AMTP/.venv` และ `pip` ของมันยังชี้ไป `~/AMTP/.venv`: การ `pip install -r chain/requirements.txt`
  รอบแรกบน w1–w5 จึงไปลงที่ venv ของ repo เก่า (โค้ดของ `~/AMTP` ไม่ถูกแตะ)
- แก้: งาน protocol เต็มใช้ `~/venv_p32` (venv ใหม่ + chain requirements + Charm ที่ build แล้ว) และ restart เฉพาะ 2 งานนั้น;
  `~/AMTP/.venv` บน w1–w5 คืนสภาพเดิมแล้ว (ถอน 57 package, คืน numpy 2.5.4 และ pycryptodome 4.4.0) ตรงกับเครื่องที่ไม่ถูกแตะ (w6–w8) ทุกตัว
- กฎต่อไป: ห้ามใช้ `~/NewAMTP/.venv/bin/pip` บนเครื่องเหล่านี้; ใช้ `<venv>/bin/python -m pip` กับ venv ของเราเอง

## Sepolia: root maintenance ต่อจำนวน domain (B3, #42 A)
- `chain/runs/gas_domains_20261119_005048.{csv,json}`: contract ใหม่, D = 1..32, บัญชี admin เดียว
- submit (root update) gas: D = 1 86.7k, D = 4 118.5k, D = 16 150.5k, D = 32 166.5k; ~11 s ต่อ transaction;
  register domain 0.50M → 1.38M gas; ใช้ ETH แทบไม่ลด (ราคา gas ต่ำมาก)
