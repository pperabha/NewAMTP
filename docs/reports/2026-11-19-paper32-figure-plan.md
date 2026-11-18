# รายการกราฟของ paper (32) (A8 ทำกราฟ, B5 ใส่ Overleaf)

**ทุกการทดลอง query ทั้ง single และ multi domain (Exp 1, 2, 5 และ 2.2) มี 3 ตัววัด (เจ้าของงาน 19 พ.ย.):**
1. **server search time อย่างเดียว** (ไม่รวม proof และ fetch): AMTP `server_search_pf` (`bench_split.run`, PR #63), Chen `server_total`
   (ไม่มี proof / fetch อยู่แล้ว), SE-COLLAB และ Du `search_no_fetch`
2. **DU verify time:** `verify_total`
3. **end-to-end:** query gen + server + verify (ไม่รวมเวลาอ่าน root และการถอดรหัส; `anchor_read` แยก)

กติกา: line chart เท่านั้น · ค่า = **mean** ของ 10 run หลัง warm-up 3 (#46) · บอกตรงๆ ว่า AMTP แพ้ตรงไหน
✅ = มีข้อมูล / กำลังรัน · ⏳ = ยังไม่ได้รัน · ❗ = ยังไม่มีโค้ด/ข้อมูล

## กราฟที่ต้องมีแน่นอน (เจ้าของงาน 19 พ.ย.)
| # | กราฟ | scheme |
|---|---|---|
| M1 | server search time อย่างเดียว, single domain (ไล่ kQ และไล่ N) | AMTP, Chen, Du, SE-COLLAB |
| M2 | Boolean server search time, multi domain, **(A∨B)∧(C∨D)** | AMTP, **SE-COLLAB เท่านั้น** |
| M3 | Boolean server search time, multi domain, **(A∧B)∨(C∧D)** | AMTP, **SE-COLLAB เท่านั้น** |
| M4 | tamper detection | AMTP, Chen, Du, SE-COLLAB |
| M5 | single domain verification time | AMTP, Chen, Du, SE-COLLAB |
| M6 | multi domain verification time | AMTP, **SE-COLLAB เท่านั้น** |
| M7 | ablation (Exp 4 ตามที่ตกลง) | AMTP, Static-MT, Global-MT(v) + AMTP (protocol เต็ม) |
| M8 | multi domain scalability (Exp 5) | AMTP, **SE-COLLAB เท่านั้น** ในกราฟหลัก (เจ้าของงานเลือก A, 19 พ.ย.) |

**M8 / Exp 5 กับ Du (เจ้าของงาน 19 พ.ย.: แบบ A แต่เก็บข้อมูลไว้ทั้งคู่):** กราฟหลักมีแค่ AMTP กับ SE-COLLAB และมีหนึ่งประโยคใน paper ว่า
Du เทียบตรงไม่ได้ เพราะ Du ไล่จำนวน cloud (n_c) ไม่ใช่จำนวน domain (D) และไม่มี Domain Root แยกกัน ข้อมูล Du ยังรันและเก็บครบ
(`du/exp5_clouds`, n_c = 4/8/16/32, N = 5k) สคริปต์ plot ของ Exp 5 มีสวิตช์ `--with-du` ไว้ใส่เส้น Du ที่ D = n_c = 4–32 (แบบ B)
ถ้าเปลี่ยนใจตอน plot ไม่ต้องรันใหม่

## ความยุติธรรมของการเทียบ (ตรวจในโค้ดแล้ว)
- ทุก scheme: dataset, keyword และ query ชุดเดียวกัน (`baselines/amtp_dataset.py`, `AMTP_QUERY_SET=p32`), N เดียวกัน, รันบน**เครื่องเดียวกัน**
  ใน step เดียวกัน, 10 run หลัง warm-up 3, ใช้ mean, ขนาด proof / response นับด้วยกติกาเดียวกัน (`baselines/wire_sizes.py`)
- **server search อย่างเดียว** = งานของ server ที่ดึง posting และประเมิน Boolean โดยไม่สร้าง proof และไม่ fetch ไฟล์:
  - AMTP `server_search_pf` = lookup + focus + posting sets + Boolean eval (ผลต้องตรงกับ response เต็ม ไม่งั้นหยุด)
  - SE-COLLAB `search_no_fetch` = `bpl_retrieval` + `boolean_eval` (search_core ลบ result_fetch)
  - Du `search_no_fetch` = Algorithm 2 (match Bloom-filter tree) ของทุก cloud ใช้ **cloud ที่ช้าที่สุด** (cloud ทำงานขนานกัน
    เหมือน `server_total` ของ Du; ผลรวมทุก cloud อยู่ใน `search_no_fetch_sum`); วัดหลัง query เต็ม (cache อุ่น → เข้าทาง Du)
  - Chen `server_total` = เดิน chain + homomorphic add + XOR proof (proof เป็นแค่ XOR); Chen **ไม่มี fetch** และ **AND ทำที่ user**
    (ถอดรหัส bitmap แล้ว AND) ต้องเขียนใน caption ว่า server ของ Chen ไม่ได้ประเมิน Boolean
- **verify** = ขั้นตรวจฝั่ง user ของแต่ละ scheme เอง (`verify_total`)
- **end-to-end** = query gen + server + verify ทุก scheme; ไม่รวมการถอดรหัสไฟล์ของทุก scheme; AMTP ไม่รวมเวลาอ่าน root (`anchor_read` แยก)
  เพราะ baseline ไม่มี chain
- สิ่งที่ AMTP ทำเพิ่มแต่ baseline ไม่มี (ไม่ได้ตัดออกจากเส้นหลัก แต่แยกคอลัมน์ให้เห็น): ABS ใน update (`abs_*`), anchor บน contract (`anchor`)

## Exp 1 Boolean Search Scalability ((32): query-generation, server search/proof-generation, end-to-end)
| รูป | x | y (panel) | scheme | ข้อมูล | สถานะ |
|---|---|---|---|---|---|
| 1a Search 1.1 | kQ ∈ {1,2,4,8,16}, N = 100k | query gen · server · end-to-end | AMTP, Chen, Du, SE-COLLAB | `search1` | ⏳ w6 |
| 1b Search 1.2 | N 10k–125k, kQ = 4 | query gen · server · end-to-end | 4 scheme | `search1` | ⏳ w6 |
| 1c Search 2.1 | kQ ∈ {2,4,8,16}, 1 รูปต่อ shape: AND, OR, (A∨B)∧(C∨D), (A∧B)∨(C∧D); 4 × 100k | query gen · server · end-to-end | AMTP, SE-COLLAB | `xsearch` | ⏳ w8 |
| 1d Search 2.2 (เพิ่มตามที่ตกลง) | D 1–32 (400k แบ่งใหม่) | server · end-to-end | AMTP, SE-COLLAB | `xdomains` | ⏳ w9 หลัง ex5 |

## Exp 2 Selective Proof and Verification ((32): proof generation, DU verification, proof size; clustered vs dispersed)
| รูป | x | y | scheme | ข้อมูล | สถานะ |
|---|---|---|---|---|---|
| 2a clustered vs dispersed (ตาม (32)) | rQ, N = 100k | proof gen · verify · proof size (เส้น clustered / dispersed / partition_spread) | AMTP (+ baseline ที่รันได้) | `exp2-layouts` + `exp2` | ❗ A2 (layout 100k ยังไม่สร้าง) |
| 2b Verify 1.1 (เพิ่ม) | rQ 10–10,000, N = 100k | verify · proof size | 4 scheme | `verify1` | ⏳ w7 |
| 2c Verify 1.2 tamper (เพิ่ม) | t ไฟล์ที่ถูกแก้, 4 attack | detection % · verify | 4 scheme | `tamper` | ⏳ w7 |
| 2d Verify 2.1 (เพิ่ม) | rQ รวม, 4 × 100k | verify · proof size | AMTP, SE-COLLAB | `xverify` | ⏳ w8 |
| 2e Verify 2.2 (เพิ่ม) | D 1–32 | verify | AMTP, SE-COLLAB | `xdomains` | ⏳ w9 |

## Exp 3 Dynamic Update Scalability ((32): update latency, posting-state repair, auth-tree maintenance, throughput; vs Chen; no split/merge)
| รูป | x | y | scheme | ข้อมูล | สถานะ |
|---|---|---|---|---|---|
| 3a | batch b ∈ {1,10,100,1000}, N = 100k | ms ต่อ update (insert / delete) · throughput | AMTP, Chen | `update` | ✅ รันอยู่ w10 |
| 3b | N 10k–125k, b = 100 | ms ต่อ update · throughput | AMTP, Chen | `update_n` | ✅ รันอยู่ w10 |
| 3c breakdown | b (และ N) | posting repair · auth tree · ABS (sign / CS verify / DO verify) · anchor (local EVM) | AMTP | `update`, `update_n` | ✅ (คอลัมน์มีแล้ว) |

## Exp 4 Adaptive Partitioning under Skewed Growth ((32): update, search/proof, verify, max partition, split/merge overhead vs skew)
| รูป | x | y | เส้น | ข้อมูล | สถานะ |
|---|---|---|---|---|---|
| 4a | skew 0 / 0.25 / 0.5 / 0.75 / 0.95 | update latency | AMTP, Static-MT, Global-MT(v), **AMTP (protocol เต็ม)** | ablation + skewproto | ✅ รันอยู่ w1–w5 |
| 4b | skew | search/proof latency | 3 variant | ablation queries | ✅ |
| 4c | skew | verification latency | 3 variant | ablation queries | ✅ |
| 4d | skew | partition ใหญ่สุด (log) | 3 variant | ablation layout | ✅ |
| 4e | skew | เวลา split/merge (restructure_ms) + จำนวน split/merge | AMTP, AMTP (protocol เต็ม) | ablation + skewproto | ✅ |

## Exp 5 Multi-Domain Scalability and Isolation ((32): query, proof gen, verify, root maintenance vs D; update one domain; Du where applicable)
| รูป | x | y | scheme | ข้อมูล | สถานะ |
|---|---|---|---|---|---|
| 5a | D 1–32 (domain เป้าหมาย 5k) | query · proof gen · verify | AMTP, SE-COLLAB (Du ที่ n_c = 4–32 เก็บไว้ ใส่ได้ด้วย `--with-du`) | `exp5`, Du `clouds` | ✅ รันอยู่ w9 |
| 5b root maintenance | D 1–32 | anchor time + gas ต่อ update (EVM ในเครื่อง) และ gas + เวลาจริงบน Sepolia | AMTP | `exp5` + `chain/runs/gas_domains_20261119_005048.csv` | ✅ / ✅ Sepolia เสร็จ |
| 5c update isolation | D 1–32 | ms ต่อ insert / delete ของ domain เป้าหมาย (Domain Root อื่นไม่เปลี่ยน = gate ผ่าน) | AMTP | `exp5` | ✅ |

## ไม่ใช่กราฟ (ตาราง / ข้อความใน paper)
- ตาราง ABS (Setup, AttrGen, Sign, Verify, ขนาดลายเซ็น; BN254 / MNT224 / SS512): `baselines/results/abs/abs_costs.csv` (B)
- Sepolia (`chain/runs/sepolia_bench_20261119_012227.*`, โค้ดปัจจุบัน ABS + CP-ABE จริง, D1 5k, b = 1/10/100): anchor median 11.0 s
  (max 60.4 s), finality ~1,015 s, gas 87.05k ต่อ root update (D = 1), อ่าน root latest 131 ms / finalized 149 ms;
  protocol b = 1: 84–96 ms, b = 10: 0.50–0.55 s, b = 100: 3.2 s → setup / Exp 3 / Exp 5
