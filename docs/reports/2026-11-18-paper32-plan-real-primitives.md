# สรุป 18 พ.ย. 2026: ของจริง (CP-ABE, blockchain) และแผนทำการทดลองใหม่ตาม paper (32)

branch `feat/chain-anchor` (PR นี้) · อ่านไฟล์นี้ไฟล์เดียวจะรู้ว่าตอนนี้อยู่ตรงไหนและต้องทำอะไรต่อ

## 1. ทำไมมีรอบนี้

- อาจารย์สั่งให้ใช้ **blockchain จริง** และ **CP-ABE จริง** แทนตัวจำลอง
- paper เวอร์ชัน **AMTP (32).pdf** เขียน Section V (Evaluation) ใหม่เป็นแผน 5 การทดลอง (ยังมีช่องว่าง `[X]`, `[signature scheme]` ฯลฯ)
  ซึ่งต่างจากผลที่เรารันมาเกือบทุกข้อ ทีมตัดสินใจ **ทำการทดลองใหม่ให้ตรงกับ (32)** และทำทุกอย่างเป็นของจริง
- ผลรอบเก่า (`baselines/results/paper/`, Figs. 3–10, repo ส่งงาน `ApiSom-o/AMTP-submission`) ยังอยู่ ไม่ได้ลบ

## 2. สถานะของจริงแต่ละตัว

| ส่วนใน paper | สถานะ | เปิดใช้ยังไง | รายละเอียด |
|---|---|---|---|
| CP-ABE (สมการ 3, 78) | **จริงแล้ว**: BSW07 ใน Charm, curve SS512 | `AMTP_CPABE=bsw07` (ค่าเริ่มต้นยังเป็นตัวจำลอง) | `docs/reports/2026-11-17-real-cpabe.md` |
| Root Anchor = smart contract | **จริงแล้ว**: `chain/RootAnchor.sol` deploy บน **Ethereum Sepolia** | `AMTP_ANCHOR=chain` (Sepolia) · `chain-local` (EVM ในเครื่อง) · ค่าเริ่มต้น in-process | `docs/reports/2026-11-17-chain-anchor.md`, `chain/README.md` |
| σ_root (สมการ 29) | ECDSA secp256k1 ที่ **contract ตรวจเอง** (`ecrecover`) | มากับ chain anchor | ดูข้อ 5A |
| σ_d, σ_op (สมการ 9, 11) = ABS | **ยังเป็นตัวจำลอง** (Ed25519) | – | ดูข้อ 5A |

ตัวเลขจาก Sepolia (contract `0xf04b5287a1Db458C4D25bef73b55fAf89AcF3Ec0`,
https://sepolia.etherscan.io/address/0xf04b5287a1Db458C4D25bef73b55fAf89AcF3Ec0):

| วัดอะไร | ค่า (median) | ไฟล์ |
|---|---|---|
| world เล็ก 2 domain: เขียน root ต่อ epoch (ส่ง -> receipt) | 11.6 s (max 24.3 s), gas 89,021 ต่อ submit | `chain/runs/sepolia_20261117_203549.json` |
| update จริงบน arXiv (10,000 ไฟล์/domain, D1–D4, b = 100, 32 epoch) | protocol (request + server + validate) **0.92 s**, anchor **10.75 s** (max 23.0 s), gas 111,838, finalized ~16 นาที, อ่าน `latest()` 257 ms | `chain/runs/sepolia_bench_20261117_210628.{csv,json}` (เพิ่มใน PR นี้) |

test ETH ที่ใช้ทั้งหมดยังไม่ถึง 0.000001 ETH (test ETH ไม่มีมูลค่า ขอฟรีจาก faucet)

## 3. สิ่งที่อยู่ใน PR นี้

- commit ของ chain anchor ทั้งหมด (contract, client `amtp/chain_anchor.py`, test, script Sepolia, benchmark บน chain)
- merge main (CP-ABE จริง, PR #38) เข้ามา: conflict จุดเดียวที่ `scenario.World.__init__` เก็บทั้งสองฝั่ง
  (`make_authority()` จาก main + `anchor=` จาก branch นี้)
- ผล Sepolia bench ที่ยังไม่ได้ commit (`chain/runs/sepolia_bench_20261117_210628.*`)
- รายงานนี้ + ส่วน "สถานะล่าสุด" บนสุดของ `docs/HANDOFF.md`

ตรวจแล้ว: pytest **561 passed** (venv ที่มีทั้ง web3 และ Charm) และ **561 passed** เมื่อ `AMTP_CPABE=bsw07`;
test chain + CP-ABE รันด้วยกันผ่าน 18 ตัว (รวม AMTP ทั้งระบบบน chain และถอดไฟล์ด้วย BSW07 จริง)
ใน venv ที่ไม่มี Charm: 551 passed (test CP-ABE ข้าม)

## 4. ตัดสินใจแล้ว

- **ใช้ arXiv ไม่ใช้ Enron** (ต่างจากที่ (32) เขียน ต้องแก้ประโยค dataset ใน Setup)
  - Enron มี ~517k อีเมลและซ้ำกันเยอะ ต้องเติม synthetic ให้ถึง 10⁶: record ที่ copy มามี keyword เหมือนต้นฉบับ
    ทำให้ rQ และ posting โตตามจำนวน copy ไม่ใช่ตามข้อมูลจริง และไม่มี domain ตามธรรมชาติ
  - arXiv snapshot บน Kaggle มีหลายล้าน paper ตอนนี้ใช้แค่ 550k: **เลือกเพิ่มให้ถึง 10⁶ ได้โดยไม่มี synthetic**
  - เปลี่ยน dataset = ต้องทำ pipeline, keyword, query, workload ใหม่ทั้ง 4 scheme; คง arXiv แก้ paper ประโยคเดียว
- merge main เข้า `feat/chain-anchor` (ทำแล้ว)

## 5. ข้อเสนอที่รอเจ้าของงาน / อาจารย์ตัดสิน

### 5A. ABS: σ_d, σ_op เป็น ABS จริง, σ_root เป็น ECDSA ที่ contract ตรวจ

- σ_d และ σ_op ตรวจนอก chain (CS และ DO ใน Python) -> ใช้ ABS จริงได้ตรงตาม paper
  (Charm ไม่มี ABS สำเร็จรูป ต้อง implement scheme จาก paper ต้นฉบับ เช่น Maji–Prabhakaran–Rosulek)
- σ_root ต้องให้ smart contract ตรวจ: Ethereum มีตัวตรวจ ECDSA ในตัว (`ecrecover`) แต่ไม่มีตัวตรวจ ABS
  (ต้องเขียน pairing ทั้ง scheme เป็น Solidity เอง ยากและแพงมาก) จึงใช้ ECDSA ซึ่งโค้ดทำอยู่แล้ว
- Theorem 3 ต้องการแค่ "ปลอมลายเซ็นไม่ได้" ซึ่ง ECDSA (EUF-CMA) ให้ได้ ทฤษฎีจึงยังถูก
  สิ่งที่หายไปคือการอนุมัติ root แบบอิง attribute ซึ่ง paper ไม่ได้อ้างคุณสมบัตินี้
- ประโยค "The RA verifies the signature under the domain's root-update policy" **ไม่ต้องแก้**
- จุดที่ต้องแก้ใน paper:

| จุด | แก้เป็น |
|---|---|
| Phase 1 Step 1 "registers PK_i and the applicable ABS authorization policies with the RA" | "…and the root-update verification keys of the authorized DOs" (DO ได้ SK^root เพิ่ม) |
| สมการ (29) | `ABS.Sign(SK^abs, ·)` -> `Sign(SK^root, ·)` (ECDSA secp256k1) |
| Threat model + IV-A assumptions | "ABS unforgeability" -> "ABS unforgeability and EUF-CMA security of the root-update signature" |
| Theorem 3 + proof | `Adv^UF_ABS` -> `Adv^EUF-CMA_Sig`, "ABS forgery" -> "signature forgery" |
| Table III/IV + ย่อหน้าหลัง Table IV | T_ABS -> T_Sig, "the ABS operation authorizes" -> "one signature authorizes" |
| Setup `[signature scheme]` | "ABS (<scheme>) for requests; ECDSA (secp256k1) for root transitions, verified by the RA contract on Ethereum Sepolia" |

### 5B. N = ขนาดของ domain ที่ถูก query และ D = 1 ใน Exp 1–4

- (32) เขียน "vary the database size from 10⁴ to 10⁶", "the number of domains is fixed at [X]" และใน Exp 5
  "the size … of the queried target domain are held fixed" แต่**ไม่ได้บอกว่า N นับต่อ domain หรือรวม**
- ถ้า [X] = 4 และ N รวม = 10⁶ แต่ละ domain มี 250k: AMTP ค้นจริง 250k แต่ Chen / SE-COLLAB ค้นทั้ง 10⁶ -> เทียบไม่ยุติธรรม
- ข้อเสนอ: N = จำนวนไฟล์ใน domain ที่ถูก query, **[X] = 1 ใน Exp 1–4** (database ทั้งหมด = 1 domain = N ไฟล์
  ทุก scheme ค้นข้อมูลขนาดเท่ากัน) ส่วน Exp 5 ไล่ D = 1…32 โดยแต่ละ domain ขนาดคงที่ (เช่น 10⁴ หรือ 5×10⁴;
  10⁶ ต่อ domain ไม่ได้ เพราะ D = 32 จะเป็น 3.2 ล้านไฟล์)
- ถ้าอยากได้ D = 4 ก็ทำได้ ตัวเลขเท่าเดิม (domain อื่นไม่ถูกแตะ) แต่ใช้ RAM 4 เท่า

### 5C. รายงาน update เป็น protocol time กับ anchor time แยกกัน

- (32) Exp 3: "update latency, affected posting-state repair time, authentication-tree maintenance time, total update
  throughput … compared with Chen"; Exp 5: "root-maintenance overhead"; Phase 2 Step 5: update เสร็จเมื่อ RA รับ root
  แต่**ไม่ได้บอกว่า update latency รวมเวลารอ blockchain หรือไม่**
- update หนึ่งครั้ง = (1) CS เตรียม update (repair + tree) (2) DO ตรวจและเซ็น (3) ส่ง tx และรอ block
  - protocol time = (1) + (2): ระดับ ms ถึงไม่ถึง 1 s
  - anchor time = (3): ~11 s บน Sepolia ส่วนใหญ่คือรอ block (~12 s) ไม่ใช่งานของ AMTP
- ถ้ารวมกัน AMTP ~12 s ต่อ update เทียบ Chen ไม่กี่ ms (Chen ไม่มี chain) กราฟจะวัดความเร็วของ Ethereum ไม่ใช่ AMTP
- ข้อเสนอ: Exp 3 ใช้ protocol time เทียบ Chen (แยก repair / tree ตามที่ paper ขอ); Exp 5 "root-maintenance overhead"
  = anchor time + gas จาก Sepolia จริง เทียบกับ D; paper เขียนให้ชัดว่าวัดอะไรแยกอะไร

## 6. paper (32) เทียบกับสิ่งที่เรามี (งานที่ต้องทำ)

| | (32) เขียนว่า | ตอนนี้ | ต้องทำ |
|---|---|---|---|
| Setup | Enron + synthetic, N 10⁴–10⁶, รอบ [30/50/100], ค่า θ / D / signature เว้นว่าง | arXiv 4 × 125k, 15–30 รอบ | arXiv 10⁶ จริง (ข้อ 4), เติมค่าว่าง |
| Exp 1 Search | N ∈ {10⁴, 5×10⁴, 10⁵, 5×10⁵, 10⁶}, kQ ∈ {1, 2, 4, 8, 16}, A∧B∧C∧D, A∨B∨C∨D, (A∨B)∧(C∨D), (A∧B)∨(C∧D); วัด query gen, server search/proof gen, end-to-end; เทียบ SE-COLLAB (+ ตัวอื่นเท่าที่รองรับ) | สูงสุด 125k, kQ ชุดอื่น, ไม่มี OR ล้วน, กราฟ paper เป็น search-only | query ชุดใหม่ + รันใหม่ |
| Exp 2 Selective proof | N = 10⁶, เปลี่ยน pQ / rQ / sQ, query แบบ clustered กับ dispersed; วัด proof gen, verify, proof size | Exp 2 ตอนนี้ = tamper detection + verify vs rQ ที่ 100k | ออกแบบใหม่ทั้งหมด (ตัวสร้าง query ที่คุมการกระจายข้าม partition); tamper detection ไม่อยู่ใน (32) |
| Exp 3 Dynamic update | N 10⁴–10⁶, batch 1/10/100/1000, insert + delete, เทียบ Chen, ไม่นับ split/merge; วัด update latency, repair, tree, throughput | `suite_exp3` + update ของ Chen sim มีแล้ว แต่ไม่ได้อยู่ใน paper ล่าสุด | วิธีตัด split/merge + protocol/anchor (5C) |
| Exp 4 Skewed growth | Global-MT, Static-MT, skew เพิ่มขึ้นทีละระดับ; วัด update, search/proof, verify, partition ใหญ่สุด, split/merge overhead | ablation θ64 (skew ระดับเดียว) | ไล่ระดับ skew + แยกเวลา split/merge |
| Exp 5 Multi-domain | D = 1…32; query, proof gen, verify, root maintenance; update domain เดียวโดย domain อื่นไม่เปลี่ยน; เทียบ Du | query + update_one_domain (insert อย่างเดียว) เทียบ SE-COLLAB | เพิ่ม delete, เทียบ Du, root maintenance จาก Sepolia |

## 7. ตัวเลขที่มีอยู่แล้ว (รอบ part-leaf บน AWS, N สูงสุด 125k) ที่ใช้คาดว่าจะชนะ/แพ้ตรงไหน

AND, single domain, 100k ไฟล์, kQ = 5 (ms, median):

| | AMTP | Chen |
|---|---|---|
| search อย่างเดียว | 0.026 | 0.036 (ชนะ; ที่ 10k เสมอ 0.024 กับ 0.023) |
| search + proof + fetch | 0.223 | 0.036 (**แพ้ ~6 เท่า**) |
| end-to-end | 0.70 | 2.16 (ชนะ; ที่ 10k แพ้ 0.63 กับ 0.38) |

end-to-end ของ Chen โตตาม N (ต้องถอด bitmap ขนาด N bit) ของ AMTP เกือบคงที่ ที่ 10⁶ น่าจะชนะห่างขึ้น (ยังไม่ได้วัด)

Boolean เทียบ SE-COLLAB (search อย่างเดียว, ms):

| query | AMTP | SE-COLLAB | ผล |
|---|---|---|---|
| AND kQ 2–16 | 0.05–0.27 | 0.27–0.67 | ชนะ |
| (A∨B)∧(C∨D) kQ 2–16 | 0.09–0.50 | 0.52–0.96 | ชนะ |
| (A∧B)∨(C∧D) kQ 2–16 | 0.05–0.46 | 0.29–1.22 | ชนะ |
| OR kQ 4 | 1.09 | 1.06 | เสมอ |
| OR kQ 8 / 16 | 2.4 / 4.3 | 1.3 / 1.8 | **แพ้ ~2 เท่า** |

รวม proof + fetch แล้ว AMTP ยังชนะ SE-COLLAB ทุกแบบ ยกเว้น OR kQ ≥ 4 และ (A∧B)∨(C∧D) kQ 16
สรุป: (32) ขอวัด "search/proof-generation" ด้วย -> จะแพ้ Chen ทุกจุดในส่วน server ต้องรายงานตามจริง
(Chen ไม่พิสูจน์ความครบถ้วนของ Boolean) ส่วน end-to-end น่าจะชนะ

update isolation (Exp 5 เดิม, insert 1 ไฟล์ลง domain เป้าหมาย, 15 รอบ): ทุกรอบโค้ดเช็กว่า Domain Root ของ domain อื่น
ไม่เปลี่ยน (ไม่งั้นหยุดด้วย `ISOLATION FAILED`) ผ่านทุก D; update ~75–80 ms คงที่ไม่ว่า D = 1 หรือ 32;
anchor in-process 0.12 -> 0.23 ms (`baselines/results/paper/data/amtp/amtp_exp5_domains.csv`, `op = update_one_domain`)

## 8. ลดขนาด dataset แล้วการทดลองจะเร็วขึ้นไหม

- **เวลารันทั้งหมด (wall clock) เร็วขึ้น**: เวลา build index, RAM และเวลาโหลดโตตาม N
- **ตัวเลขที่วัดได้ของ AMTP แทบไม่เปลี่ยน**: search 0.024 ms ที่ 10k -> 0.027 ms ที่ 125k (เกือบคงที่ เพราะขึ้นกับ pQ / rQ / sQ
  ไม่ใช่ N) แต่ baseline บางตัวโตตาม N (end-to-end ของ Chen 0.38 -> 2.54 ms) ลด N จึงทำให้ AMTP ดูดีน้อยลง
- (32) กำหนด N ถึง 10⁶ ถ้าจะตรง paper ลด N สูงสุดไม่ได้ ที่ลดได้คือจำนวนรอบ (ตามค่าที่ paper เติม) และจำนวน batch ใน Exp 4

## 9. งานถัดไป (เรียงลำดับ)

1. รอตัดสิน 5A / 5B / 5C (5A ต้องถามอาจารย์)
2. ABS จริงสำหรับ σ_d / σ_op (ถ้า 5A ผ่าน)
3. เลือก arXiv เพิ่มให้มี domain ขนาด 10⁶ (`datasets/arxiv/select_files_v4.py`) + keyword
4. ทดสอบ build ที่ 10⁶ (AMTP และ baseline ทั้ง 3 โดยเฉพาะ SE-COLLAB ที่ใช้ pairing): เวลาและ RAM
5. ตัวสร้าง query / workload ของแต่ละ Exp ตาม (32) (Exp 2 clustered / dispersed, Exp 4 ระดับ skew)
6. smoke test ทุก Exp บน Mac -> รันจริงบน AWS (anchor บน Sepolia: Exp 3 ~1,320 epoch ~4.5 ชม., Exp 5 ~200 epoch,
   Exp 4 ~5,000 epoch ~17 ชม. ต้องแยก account รันขนาน) -> กราฟ (line chart เท่านั้น)

## 10. วิธีรัน

```bash
# venv ที่มีทั้ง chain และ CP-ABE จริง (Python 3.12; Charm ต้องมี GMP + PBC ตาม baselines/README.md)
python3.12 -m venv .venv && .venv/bin/pip install -r chain/requirements.txt charm-crypto-framework==0.62
cd amtp_code
../.venv/bin/python -m pytest -q                         # 561 passed
AMTP_CPABE=bsw07 ../.venv/bin/python -m pytest -q        # 561 passed, CP-ABE จริง
AMTP_CPABE=bsw07 AMTP_ANCHOR=chain-local ../.venv/bin/python -m bench.experiments exp5 ...   # EVM ในเครื่อง
# Sepolia: ทำตาม chain/README.md (key ใน .env ที่ git ignore, RPC URL, test ETH จาก faucet, deploy)
```

## สถานะ

- merge แล้วบน `feat/chain-anchor`, รอเจ้าของงานกด merge PR เข้า main
- ยังไม่ได้แก้ paper และยังไม่ได้รันการทดลองชุดใหม่
