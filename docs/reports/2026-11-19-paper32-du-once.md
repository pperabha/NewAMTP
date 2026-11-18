# #68 A: งานฝั่ง DU (อ่าน root, ถอดรหัส CP-ABE) ทำครั้งเดียวต่อ query นอกรอบที่จับเวลา

วันที่ 19 พ.ย. 2026 · คน A · branch `feat/paper32-du-once` (ต่อจาก `feat/paper32-a2-exp2` #67) · issue #68 (เจ้าของงานเลือก A)

## ปัญหา
เวลา query ของ AMTP รอบ paper (32) ช้ากว่ารอบก่อน 1.4–1.5× (flag เหมือนกัน, SE-COLLAB บนเครื่องเดียวกันเท่าเดิม). A/B บน Mac
(exp5 D = 1, 10 run หลัง warm-up 3): ทุก repetition `run_query` ให้ DU ถอดรหัสทุกผลด้วย BSW07 (~120 ms pairing, ไม่นับเวลา) และอ่าน
root จาก EVM (~2.5 ms) ใน process เดียวกับ server → ไล่ cache ของ CPU ก่อนรอบถัดไป. ในระบบจริง DU กับ CS อยู่คนละเครื่อง.

## แก้อะไร (`amtp_code/bench/experiments.py`, `amtp_code/bench_split/run.py`)
- `once(key, fn)`: ภายใน `measure_fn` การอ่าน root (`anchor_read`) และการถอดรหัส (`decrypt_checked`, correctness gate: ผู้มีสิทธิ์
  ถอดรหัสได้ทุกผล) ทำครั้งแรกของ query (รอบ warm-up) แล้วรอบถัดไปใช้ค่าและเวลาเดิม; นอก `measure_fn` ทำทุกครั้งเหมือนเดิม
- ส่วนที่จับเวลา (query gen, admission + server, DU verify ทั้ง 7 checks) ยังทำทุก repetition → protocol / ความปลอดภัยไม่เปลี่ยน
- `du_decrypt` / `anchor_read` ยังรายงาน (จากครั้งที่ทำจริง) · bench_split และ tamper ใช้ `anchor_read` เดียวกัน

## ผล A/B (Mac, mean, ms)
| config | search อย่างเดียว | lookup | proof | query gen | server รวม | verify | e2e |
|---|---|---|---|---|---|---|---|
| ตัวแทน (AES, anchor ใน process) | 0.0204 | 0.115 | 0.126 | 0.062 | 0.424 | 1.27 | 1.76 |
| จริง ก่อนแก้ | 0.0327 | 0.152 | 0.168 | 0.083 | 0.613 | 1.49 | 2.18 |
| จริง หลังแก้ | 0.0231 | 0.125 | 0.138 | 0.066 | 0.538 | 1.46 | 2.06 |

ส่วนที่ยังต่างจากตัวแทนคือ fetch (+0.09) และ verify_ct (+0.16) = ต้นทุนจริง: ciphertext ของ CP-ABE จริงทำให้ response ใหญ่ขึ้น
85 → 169 KB (ต้องส่งและ hash มากขึ้น)

## ทดสอบ
pytest 575 passed (config จริง: bsw07, mpr SS512, chain-local) และ 575 (default); smoke AMTP search1 / tamper / xdomains บน Mac;
pytest 576 passed บนเครื่อง cloud ทุกเครื่องก่อนเริ่ม

## รันใหม่บน cloud (74379b7, ทุก scheme บนเครื่องเดียวกัน)
w6 search1 · w7 verify1 + tamper · w8 xsearch + xverify · w9 xdomains · w10 exp2 + exp5. run เดิมที่หยุดอยู่ในช่วง AMTP (ยังไม่มี
baseline) ย้ายไป `*_aborted_68`. ไม่ต้องรันใหม่: Exp 3, Exp 4, ผล baseline รอบก่อน
