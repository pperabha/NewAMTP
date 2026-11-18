# รวม ABS จริงเข้าการทดลอง (#54 = C, SS512) + เวลา ABS แยกคอลัมน์

- merge `feat/real-abs` (PR #55 ของ B) เข้า branch นี้ (`git -c user.name=ApiSom-O merge`)
- `scripts/paper32_env.sh`: `AMTP_ABS=mpr`, `AMTP_ABS_CURVE=SS512` (#54 C)
- `amtp/owner.py`, `bench/experiments.py`: `Signer(domain)` (policy `domain:Di AND role:owner` ของ domain นั้นจริง)
- `bench/experiments.py` `SigTimer`: จับเวลา σ_op ที่ DO เซ็น (`abs_sign`), CS ตรวจตอน admission (`abs_verify_cs`) และ DO validator
  ตรวจซ้ำ (`abs_verify_do`) ต่อ epoch ใช้ `sig_ok` ตัวเดิมที่ protocol เรียก (ห่อแค่เพื่อจับเวลา ไม่มีการข้ามการตรวจ)
  คอลัมน์ `abs_ms` = ผลรวม; อยู่ใน exp3, exp5, skewproto (เวลาเหล่านี้รวมอยู่ใน request / server / validate แล้ว)
- manifest: `amtp_abs`, `amtp_abs_curve`
- ทดสอบ: pytest 575 passed (ค่าเริ่มต้น); ABS จริง SS512 + BSW07: ดู PR
- smoke บน Mac (รันพร้อม pytest อีกตัว ตัวเลขสูงกว่าจริง): SS512 ต่อ operation sign ~6.7 ms, verify ~4.8 ms × 2;
  ex3 b = 100 ที่ 10k: protocol 2.48 s ซึ่ง ABS 1.63 s (66%), posting repair 0.19 s, auth tree 0.09 s

## A3 (ex3) ใน PR เดียวกัน
- `scripts/aws_run_all.sh` step ใหม่ `update_n` = Exp 3 (b) ของ (32): x = N (`UPDATE_N_SIZES` 10k–125k) ที่ b = `UPDATE_N_B` (100)
  สำหรับ AMTP และ Chen (ผลแยกโฟลเดอร์ `amtp/update_n`, `chen/update_n`); step `update` เดิม = Exp 3 (a): x = b (1/10/100/1000) ที่ 100k
- `scripts/paper32_env.sh`: ค่า UPDATE_* ของ (32)
- ex3 ใช้ `StaticPolicy` (partition ตรึง) จึงไม่มี split / merge ตามที่ (32) กำหนด; เวลา posting repair / auth tree / ABS / anchor แยกคอลัมน์
- smoke `aws_run_all.sh update_n` (2k, 4k, b = 10) ผ่านทั้ง AMTP และ Chen
