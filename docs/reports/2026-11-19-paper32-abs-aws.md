# Table V วัดใหม่บน AWS r7i.4xlarge (เครื่องเดียวกับการทดลอง)

วันที่ 19 พ.ย. 2026 · คน A · branch `results/paper32-abs-aws`

## ทำอะไร
- รัน `amtp_code/bench/abs_bench.py --curves SS512 BN254 MNT224 --reps 15 --warmup 3` (ค่าเดียวกับรอบของ Prim) บน r7i.4xlarge
  (Xeon Platinum 8488C, 16 vCPU) ที่ commit 8ed08b7 ด้วย `~/venv_p32` (Charm 0.62); ปิดเครื่องหลังดึงผล
- `baselines/results/abs/abs_costs.csv` = ผลบน AWS; ผลเดิม (เครื่อง Linux อื่น, 4 vCPU) ย้ายไป `abs_costs_other_host.csv`

## Table V (policy 2 attribute, mean ของ 15 runs)
| scheme | sign (ms) | verify (ms) | size (B) |
|---|---|---|---|
| ABS, SS512 (used) | 8.4 | 6.4 | 554 |
| ABS, MNT224 | 15.6 | 50.7 | 418 |
| ABS, BN254 | 8.5 | 139.4 | 378 |
| Ed25519 (no attributes) | 0.03 | 0.09 | 64 |

- SS512 ตรงกับ Exp 3 บน AWS (sign 8.4, verify 6.4 ต่อครั้ง → 21.2 ms ต่อ request) · ลำดับเหมือนเดิม: SS512 verify เร็วที่สุดในกลุ่ม ABS
- ผลการทดลอง Exp 1–5 ไม่เปลี่ยน (Table V เป็น microbenchmark แยก)
