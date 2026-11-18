# รายการกราฟของ paper (32) (A8 ทำกราฟ, B5 ใส่ Overleaf)

กติกา: line chart เท่านั้น · ค่า = **mean** ของ 10 run หลัง warm-up 3 (#46) · บอกตรงๆ ว่า AMTP แพ้ตรงไหน
✅ = มีข้อมูล / กำลังรัน · ⏳ = ยังไม่ได้รัน · ❗ = ยังไม่มีโค้ด/ข้อมูล

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
| 5a | D 1–32 (domain เป้าหมาย 5k) | query · proof gen · verify | AMTP, SE-COLLAB; Du ที่ n_c = 4–32 | `exp5`, Du `clouds` | ✅ รันอยู่ w9 |
| 5b root maintenance | D 1–32 | anchor time + gas ต่อ update (EVM ในเครื่อง) และ gas + เวลาจริงบน Sepolia | AMTP | `exp5` + `chain/runs/gas_domains_20261119_005048.csv` | ✅ / ✅ Sepolia เสร็จ |
| 5c update isolation | D 1–32 | ms ต่อ insert / delete ของ domain เป้าหมาย (Domain Root อื่นไม่เปลี่ยน = gate ผ่าน) | AMTP | `exp5` | ✅ |

## ไม่ใช่กราฟ (ตาราง / ข้อความใน paper)
- ตาราง ABS (Setup, AttrGen, Sign, Verify, ขนาดลายเซ็น; BN254 / MNT224 / SS512): `baselines/results/abs/abs_costs.csv` (B)
- เวลาอ่าน root บน Sepolia, เวลาจน finality, protocol vs anchor บน Sepolia: `chain/sepolia_bench.py` (กำลังรัน) → setup / Exp 5
