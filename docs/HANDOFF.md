# HANDOFF — ทุกอย่างที่ต้องรู้เพื่อทำงาน NewAMTP ต่อ (15 พ.ย. 2026)

เอกสารนี้เขียนให้ผู้ช่วย (Claude) ในบัญชีใหม่ของเจ้าของงาน อ่านไฟล์นี้ไฟล์เดียวแล้วทำงานต่อได้ทันที
เนื้อหาสรุปจากการทำงานตลอด 13–15 พ.ย. ส่วนรายละเอียดแต่ละเรื่องอยู่ใน `docs/reports/` (ทุก PR มีรายงาน 1 ไฟล์)

---

## 0. เริ่มต้นอ่านอะไรก่อน

| ลำดับ | ไฟล์ | ทำไม |
|---|---|---|
| 1 | ไฟล์นี้ | ภาพรวม กติกา สถานะ งานค้าง |
| 2 | `CLAUDE.md` (root) | กติกาสั้นๆ ที่ต้องทำตามทุกครั้ง |
| 3 | `docs/ENGINE_REDESIGN.md` | เป้าหมายของ engine, กติกาทีม R1–R9, register คอขวด B#/W# |
| 4 | `docs/AMTP_PAPER.md` | scheme ตาม paper |
| 5 | `docs/reports/*.md` (เรียงตามวันที่) | ประวัติการตัดสินใจและผลแต่ละรอบ |

---

## 1. งานนี้คืออะไร

- **โปรเจกต์:** AMTP (Adaptive Merkle-tree … verifiable keyword search บนข้อมูลเข้ารหัสหลาย domain) เป็นงานวิจัยของเจ้าของงานกับเพื่อนในทีม
- **repo:** GitHub `pperabha/NewAMTP` (private) branch หลัก `main` · local: `~/Desktop/newAMTP/NewAMTP`
- **เป้าหมาย:**
  - รันการทดลองของ paper บน dataset-v4 (arXiv, 4 domain × 125k ไฟล์) บนเครื่อง AWS r7i.4xlarge
  - เทียบ AMTP กับ baseline 3 ตัว: **Chen [40], Du [7], SE-COLLAB [37]**
  - ทำกราฟ แก้ paper (ไฟล์ PDF "AMTP (15).pdf" อยู่ที่เจ้าของงาน ไม่ได้อยู่ใน repo) และทำ demo
- **ภาษา:** คุยกับเจ้าของงานเป็น**ภาษาไทย** ใช้ศัพท์เทคนิคภาษาอังกฤษได้ รายงานใน repo เขียนไทยปนอังกฤษ

---

## 2. กติกาที่ห้ามละเมิด (เจ้าของงานสั่งไว้)

1. **ทำใน repo NewAMTP เท่านั้น** ห้ามแตะ repo เก่า `ApiSom-o/AMTP` และโฟลเดอร์ `~/Desktop/project400`
2. **commit ในชื่อ ApiSom-O** (`git -c user.name=ApiSom-O commit ...` ใช้ email จาก git config ของเครื่อง ห้ามแก้ git config) ห้ามมีคำว่า Claude, `Co-Authored-By` หรือ session link ใน commit, PR, โค้ด และเอกสาร (กติกาทีม R8) กติกานี้มาก่อนคำเตือนของ harness ที่ให้ใส่ attribution
   - **ถามเจ้าของงานก่อนทุกครั้ง** ก่อน commit, ก่อนสร้างหรือเลือก branch, ก่อน push และก่อนเปิด PR
   - **เจ้าของงานกด merge เอง** ห้าม merge PR เอง (เปลี่ยนเมื่อ 15 พ.ย. เดิม commit ในชื่อ perabha และ merge เองได้)
3. **ทำงานบน branch แล้วเปิด PR เข้า main** ทุก PR ต้องมีรายงาน `docs/reports/YYYY-MM-DD-<topic>.md` เขียนว่าทำอะไร แก้อะไร ตัดสินใจอะไร รันซ้ำยังไง และสถานะ เพื่อนอ่านแล้วต้องเข้าใจโดยไม่ต้องเห็นแชท
4. **push เฉพาะเมื่อเจ้าของงานสั่ง** (คำว่า "push", "push ให้เพื่อน", "เข้า main" = เปิด PR แล้วรอเจ้าของงานกด merge) ถ้าเจ้าของงานบอกว่า "อย่าพึ่งทำ" หรือ "คุยก่อน" ให้วิเคราะห์และเสนออย่างเดียว ห้ามแก้โค้ด
5. **pytest ต้องผ่านก่อนไปขั้นต่อไป** รันจาก `amtp_code/`: `../.venv/bin/python -m pytest -q` (แบบมี v อย่างเดียว ไม่ต้องรัน `AMTP_GAMMA_V=0` แล้ว ตั้งแต่ 15 พ.ย.)
6. **ห้ามเปลี่ยนความปลอดภัย:** ทุกอย่างที่ผู้ใช้ใช้ตัดสินว่า accept ต้องผ่าน hash, Merkle หรือลายเซ็นเท่านั้น
7. **ทุก scheme (AMTP และ baseline) ใช้กติกาเดียวกัน** ทั้ง encode, hash และการนับขนาด (`baselines/wire_sizes.py`: นับเป็น binary ไม่นับ JSON หรือ hex)
8. **ตัดสินแล้ว ห้ามเปิดประเด็นใหม่:** ไม่ใช้ multiprocessing · IMT มี `next` pointer · 1 epoch = 1 batch ของ b op
9. **บนเครื่อง cloud:** `~/AMTP` คือ repo เก่า ห้ามแก้ (งานจริงอยู่ที่ `~/NewAMTP`)
10. **ห้ามอ่าน** `~/Desktop/amtp_cloud/kaggle.json` · **ห้ามขอ** AWS credential จากเจ้าของงาน
11. ผลการทดลอง commit ได้แล้ว (เดิมห้าม แต่เจ้าของงานยกเลิกกติกานี้เพื่อให้เพื่อนเห็นผล) รวมถึง `baselines/results/runs/` ยกเว้นไฟล์สถานะของ watcher (`.seen_*`, `.pulled_*`) และ smoke run บน Mac (`runs/smoke_*`) ซึ่งมี path ในเครื่อง

---

## 3. สิ่งที่ตัดสินใจไปแล้ว

| เรื่อง | การตัดสินใจ |
|---|---|
| γ | **γ = H(PID ‖ v ‖ H(Enc(L)))** มี version v (paper eq. 17) ผลแบบไม่มี v ย้ายไป `baselines/results/old/exp_no_v/` แล้ว (PR #15) โค้ดยังรองรับ `AMTP_GAMMA_V=0` |
| เวลาของ ex3 (update) | update = request + CS + **Validator** + anchor (paper เขียนว่าไม่นับ Validator ต้องแก้ข้อความใน paper ให้ตรง ยังไม่ได้แก้) |
| สถิติ | 15 รอบ หลัง warm-up 3 รอบ · ค่าต่อ query = median ของรอบ · ค่าต่อจุด = median ข้าม query · KB = 1000 B · `hash_calls` ใช้เป็นตัวเลขที่ไม่ขึ้นกับเครื่อง |
| ablation (ex4) | เทียบ AMTP กับ Static-MT และ **Global-MT(v)** (มี v เหมือนกันเพื่อความยุติธรรม) · Global-MT แบบไม่มี v เก่าใช้เทียบไม่ได้ · Global-MT(v) รันแยกด้วย `bench.ablation --variants` ด้วย seed และ workload เดียวกับ w1 |
| θ_max | ค่าหลัก 64 (`docs/THETA_CHOICE.md`) มีผลที่ 128 และ 256 ด้วย |
| กราฟ | **เจ้าของงานไม่เอากราฟแบบตารางหรือแท่ง** เอาแต่กราฟเส้น อยากได้รูปที่เล่าด้านที่เราชนะ แต่ต้องซื่อสัตย์ หัวกราฟต้องบอกจุดที่วัด ด้านที่แพ้เก็บไว้ใน `graph_op/limits/` |
| Exp 2 layouts | พักไว้ ยังไม่รันเพิ่ม |
| การวางไฟล์ (15 พ.ย.) | **fill**: partition ของกลุ่มที่มีไฟล์มากที่สุดแต่ยังไม่ถึง θ_max ถ้าเต็มหมดวางต่อแล้วให้ split แก้ · Static-MT ใช้กติกาเดียวกัน · ex3 ฟรีซ partition เหมือน paper · merge ตาม paper สมการ 34 · รันด้วย `AMTP_PLACEMENT=fill` (`docs/reports/2026-11-15-fill-placement.md`) |
| engine (15 พ.ย.) | commit อัปเดต Merkle tree แบบรวมครั้งเดียว (`MerkleTree.set_leaves`) และค้น Search Tree ครั้งเดียวต่อ keyword: ผลเหมือนเดิมทุก bit แต่ hash ฝั่ง server ลด 41–71% ทุก variant · **ผล update บน cloud ทุกชุดก่อนหน้านี้ (รวม Global-MT(v) ของ w3) เทียบกับรอบใหม่ไม่ได้** (`docs/reports/2026-11-15-engine-batched-merkle.md`) |
| แผน cloud รอบใหม่ (15 พ.ย.) | `PLAN=fill RUN_NAME=paper_fill bash scripts/cloud_worker.sh <1..5>` (ผลอยู่ใน `runs/paper_fill_v/`) · 5 เครื่อง `AMTP_PLACEMENT=fill`: ex4 AMTP + Static-MT ที่ θ = 64 / 128 / 256 เครื่องละ θ · AMTP ที่เหลือ (search1, verify1, tamper, multi-domain, ex3, ex5) 1 เครื่อง · AMTP θ = 64 + Global-MT(v) 1 เครื่อง · baseline และ Global-MT แบบไม่มี v ไม่รันใหม่ |
| สถานะรอบ fill (16 พ.ย.) | ที่ `869cf73` **ครบทุกชุดแล้ว รวม Global-MT(v) ของ worker7** (AMTP เร็วกว่า Global-MT(v) 25.7× ตอน update แต่ query ช้ากว่า ~1.7× → คุ้มจนถึง ~1,260 query ต่อ epoch) · ผลครบทุกชุดและกราฟใหม่อยู่ใน `baselines/results/new_new/` (`data/fill/`, `graphs/fill/`) แยกจากผลเดิม · ex4 AMTP เร็วกว่า Static-MT 13.4× / 11.7× / 9.9× (θ 64 / 128 / 256) · ex3 b = 1,000 insert 14.1 s (เดิม 76.5 s) (`docs/reports/2026-11-16-cloud-gmtv-fill.md`) |
| ข้ามไปก่อน (15 พ.ย.) | จัดไฟล์ตาม keyword (กลัวผิด design) · cache (เจ้าของงานตัดสินใจไม่ทำ 16 พ.ย.) |
| **placement หลักของ paper (16 พ.ย.)** | **fill** เป็นวิธีหลัก · ค่าเริ่มต้นของ `bench.experiments` และ `bench.ablation` เปลี่ยนจาก least เป็น fill แล้ว (`AMTP_PLACEMENT=least` ยังเลือกได้) · class `AdaptivePolicy` ยังมีค่าเริ่มต้น least เพื่อให้ test และ demo เดิมไม่เปลี่ยน · ผล Mac ใน `mac_and_prune/` ใช้ least ใช้เทียบผลของ flag ได้ แต่ไม่ใช่ตัวเลข paper (`docs/reports/2026-11-16-fill-default.md`) |
| query flags (16 พ.ย., อยู่ใน main แล้ว) | `--and-prune`, `--part-results`, `--and-greedy` (หรือ env `AMTP_AND_PRUNE` / `AMTP_PART_RESULTS` / `AMTP_AND_GREEDY` = 1) ค่าเริ่มต้นปิด · ผลบน Mac และข้อจำกัด: `docs/reports/2026-11-16-and-pruning.md` · ต้องแก้ paper (ASPA eq. 52–57) และให้อาจารย์อนุมัติก่อนใช้ |
| แผน cloud "prune" (16 พ.ย.) | `PLAN=prune RUN_NAME=paper_prune bash scripts/cloud_worker.sh <1..5>` · 5 เครื่อง เปิดทุก query flag, placement fill, reps 15: 1 = AMTP search1, verify1, tamper, xsearch, xverify, xdomains, exp5 · 2–4 = ex4 AMTP + Static-MT θ 64 / 128 / 256 · 5 = ex4 Global-MT(v) θ 64 · ex3 และ baseline ไม่รันใหม่ (โค้ด update และ baseline ไม่เปลี่ยน) · เริ่มรัน 16 พ.ย. ~11:00 ที่ `767289c` |
| สถานะรอบ prune (16 พ.ย. 18:00) | **เครื่อง 1 เสร็จแล้ว** ผลอยู่ที่ `runs/cloud/prune_w1/` กราฟอยู่ที่ `baselines/results/new_purn/graphs/` (ex1, ex2, ex5 ใช้ผลรอบนี้ ex3 ใช้ผลรอบ fill) · AND kQ 16 end-to-end 85.7 → 6.5 ms (SE-COLLAB 10.5) · OR และ keyword เดียวไม่ดีขึ้น และ server ช้าลง 4–13% (วัดบน Mac ยืนยันแล้ว) · update ex5 ช้าลง ~20% (เก็บ R^post ตอนสร้าง snapshot) · ex4 เครื่อง 2–5 ยังรัน คาดว่าเสร็จ 19:00–03:00 (`docs/reports/2026-11-16-prune-results.md`) |
| ex4 รอบ prune (16 พ.ย. 19:30) | เครื่อง 2 (θ 64) และ 3 (θ 128) เสร็จแล้ว ผลอยู่ที่ `runs/cloud/prune_w2/`, `prune_w3/` · update เท่ารอบ fill (AMTP 1.05 / 1.20 s, Static-MT 13.5 / 13.6 s → 12.9× / 11.3×) · query ต่อ batch เร็วขึ้น ~3× ทุก variant (AMTP server 15.9 → 5.3 ms, ตรวจ 35.7 → 12.3 ms ที่ θ 64) · AMTP ยังช้ากว่า Static-MT ตอน query เล็กน้อย (ตรวจ 12.3 เทียบ 10.2 ms) · เครื่อง 4 (θ 256) และ 5 (Global-MT(v)) ยังรัน ยังไม่มีกราฟ ex4 ของรอบนี้ |
| **วัด search แยกจาก proof (16 พ.ย.)** | อาจารย์ให้แยกการทดลองตามขั้น · โค้ดอยู่ใน `amtp_code/bench_split/` (ไม่แก้ไฟล์เดิม): search ของ server อย่างเดียว 3 แบบ (เต็ม, partition ก่อน, fast = มีดัชนีค้นหาต่อ snapshot) มีจุดตรวจว่าได้ไฟล์ตรงกับ response จริง · **ตกลงกันแล้ว:** (1) รัน `bench_split` บน cloud 1 เครื่อง: search1, xsearch, xdomains, exp5 เปิด flag เหมือนรอบ prune (เก็บทั้ง 3 แบบในรอบเดียว) (2) เอาผลให้อาจารย์ดู โดยเสนอแบบ fast เป็นตัวเลขหลัก (3) ถ้าอาจารย์รับดัชนีค้นหาในการออกแบบ ค่อยใส่ดัชนีใน server จริงเป็น flag `AMTP_SEARCH_INDEX` (ค่าเริ่มต้นปิด) พร้อมตัวจับเวลา search / prep ใน `build_response` แล้วรันชุด search อีกรอบเป็นตัวเลขสุดท้าย ถ้าไม่รับ ใช้แบบ partition ก่อน · ใน paper ใช้ตัวเลข search ชุดเดียว (`docs/reports/2026-11-16-search-split-plan.md`) · กำลังรันบน cloud ที่ `00f9d42` (เริ่ม 16 พ.ย. 19:47 เวลาไทย) |
| **ตัวเลข search อย่างเดียว = partition ก่อน (16 พ.ย. ค่ำ, แทนข้อตกลงข้างบน)** | เจ้าของงานเลือกแบบ **partition ก่อน** (`server_search_pf_fetch`) เป็นตัวเลขของ paper · **ไม่ใช้แบบ fast** เพราะ server จริงไม่มีดัชนีค้นหา · ไม่ทำ `AMTP_SEARCH_INDEX` · ไม่ต้องรันใหม่ (รอบที่รันเก็บคอลัมน์ `pf_*` แล้ว) · `bench_split/plot_search.py` plot คอลัมน์นี้ · สรุปรวมทุกการแก้และส่วนของ paper ที่ต้องแก้: `docs/reports/2026-11-16-summary-all-changes.md` |

---

## 4. แผนที่โค้ด

```
amtp_code/
  amtp/                 โค้ด scheme
    engine.py           index ฝั่ง server: partition, posting, IMT, γ/ρ, การสร้าง π^upd
    server.py           CloudServer, build_response (ASPA multiproof)
    user.py             DataUser: make_query, verify (7 check: ctx, anchor, idx, papc, part, comp, ct), decrypt
    validator.py        Validator ของ DO: ตรวจ update proposal (_imt_root, check_removed_predecessors, bracket_new_keys)
    variants.py         AdaptivePolicy (AMTP), StaticPolicy, GlobalPolicy (versioned=True คือ Global-MT(v))
    bptree.py           B+ Search Tree (h → {pid: {cid: slot}}) ใช้ให้หาเร็ว ไม่ใช่หลักฐาน
    core/merkle.py      Merkle tree + multiproof (leaf/node hash แบบเรียก SHA-256 ครั้งเดียว ตั้งแต่ PR #16)
    core/hashing.py     H() แบบ length-prefixed, HashCounter, encoding
    core/crypto.py      AES-GCM, CT format (make_ct/pack_ct), attribute wrap C_Kd
    web/app.py          demo (Flask) · scenario.py, adversary.py
  bench/
    experiments.py      ทุก suite: search1, verify1, tamper, xsearch, xverify, xdomains, exp3, exp5, ...
    ablation.py         split/merge (ex4) · --variants "AMTP,Static-MT,Global-MT,Global-MT(v)"
  tests/                333 test (มี test เทียบกับโค้ดเดิม: test_validator_imt_checks.py, test_fast_hash_paths.py)
baselines/
  chen_et_al_sim.py, du_et_al_sim.py, se_collab_sim.py   baseline
  wire_sizes.py         กติกานับขนาดร่วมกันทุก scheme
  plot_paper.py         กราฟตามแผนของ paper → <run>/figures/ (ex1–ex5)
  plot_story.py         กราฟเล่าเรื่อง → new_amtp_result/graph_op/{main,limits}/
  plot_results.py       style ของกราฟ (สี/marker ของแต่ละ scheme) ใช้ร่วมกัน
  old/                  สคริปต์ plot เก่าที่ไม่ใช้แล้ว
  results/
    new_amtp_result/gamma_with_v/   ชุดผลหลัก (CSV + manifest + figures) ← ใช้ชุดนี้
    new_amtp_result/graph_op/       กราฟเล่าเรื่อง
    runs/cloud/w1..w10/             ผลดิบจากแต่ละเครื่อง + log
    old/exp_no_v/                   ผลแบบไม่มี v (เก็บไว้เฉยๆ)
scripts/
  cloud_worker.sh       แผนรันบนเครื่อง cloud แต่ละเครื่อง
  watch_stop.sh         รันบนเครื่อง cloud: ดับเครื่องเมื่องานจบ (หลังรอ 10 นาที) หรือว่างเกิน 30 นาที
  merge_runs.py         รวมผลจากหลายเครื่อง
  cloud_helpers/        สคริปต์ที่ใช้ระหว่างงาน 14–15 พ.ย. (ดูหัวข้อ 7)
docs/reports/           รายงานต่อ PR
```

**Python:** ใช้ `.venv/bin/python` ที่ root ของ repo (python3 ของระบบไม่มี matplotlib) ส่วน charm-crypto ติดตั้งอยู่ใน .venv แล้ว

---

## 5. ผลหลักตอนนี้ (γ มี v, บน cloud)

ทุกตัวเลขอยู่ใน `baselines/results/new_amtp_result/gamma_with_v/` และ `graph_op/figure_points.csv`

**การจับการโจมตี** (keyword ที่มี 2,021 ผลลัพธ์, t = 5–1,000 ไฟล์ถูกแก้, D1–D4):

| | modify | hide | inject | old_version | ฟ้องผิด |
|---|---|---|---|---|---|
| AMTP | ✓ | ✓ | ✓ | ✓ | 0/60 |
| SE-COLLAB | ✓ | ✗ | ✗ | ✓ | 0 |
| Du | ✓ | ✓ | ✗ | ✓ | 0 |
| Chen | N/A | ✓ | ✓ | N/A | 0 |

Chen ไม่ส่งไฟล์กลับ จึงทดสอบ modify และ old_version กับ Chen ไม่ได้

**ขนาด proof** (rQ = 2,550): AMTP 573 KB · SE-COLLAB 1,431 KB (2.5×) · Du 8,711 KB (15×) · Chen 0 B (ไม่มี proof แยก) · แต่ที่ rQ = 10 SE-COLLAB เล็กกว่าเล็กน้อย

**เวลา query** (kQ = 5, N = 100k, AND, ก่อน PR #16):
- end-to-end: AMTP 10.7 ms · SE-COLLAB 9.1 · Chen 2.1 · Du 0.5
- เวลาของ AMTP 79% อยู่ที่ผู้ใช้ตรวจผล: part 76%, papc 20%
- ฝั่ง server AMTP (2.1 ms) เร็วกว่า SE-COLLAB (4.8 ms)
- AMTP เร็วกว่า SE-COLLAB เมื่อผลลัพธ์ไม่เกิน ~322 ไฟล์, ไฟล์ต่อ domain ไม่เกิน ~76k หรือ kQ ไม่เกิน ~4.5

**ex3 update** (หลังแก้ Validator, b = 1000 insert): AMTP 76 s · Chen 1.37 s → AMTP ช้ากว่า Chen 56–104× (เป็นราคาของการที่ Validator ตรวจทุก epoch)

**ex4 split/merge** (median ต่อ batch):

| θ_max | AMTP | Static-MT | AMTP เร็วกว่า | partition ใหญ่สุด AMTP / Static |
|---|---|---|---|---|
| 64 | 4.9 s | 24.2 s | 4.9× | 64 / 629 |
| 128 | 8.9 s | 37.3 s | 4.2× | 128 / 1,027 |
| 256 | 13.7 s | 37.5 s | 2.7× | 256 / 1,621 |

Global-MT(v) ที่ θ = 64 (ครบ 1,674 batch, w3 commit `089726d`, เร็วต่อ hash ใกล้ w1 ต่างกัน 2.7%): update 66.2 s ต่อ batch (ช้ากว่า AMTP 13.5×) แต่ query เร็วกว่า AMTP (verify 27.3 เทียบ 44.6 ms, server 10.2 เทียบ 15.0 ms) เพราะมี partition เดียว **AMTP ไม่ได้ชนะทุกด้าน** แต่ได้สมดุลที่ดีกว่า: AMTP คุ้มกว่าจนกว่าจะมี query เกิน ~2,800 ครั้งต่อ epoch · ค่าและกราฟใหม่อยู่ใน `baselines/results/new_new/` แยกจากผลเดิม (`docs/reports/2026-11-16-cloud-gmtv-fill.md`)

**ex5 หลาย domain:** query บน domain เดียวใช้ 4.0 → 4.1 ms จาก 1 ถึง 32 domain (SE-COLLAB 8.9 ms) · update หนึ่ง domain ใช้ 106–112 ms คงที่

---

## 6. โค้ดชุดไหนสร้างผลชุดไหน (สำคัญมาก)

| ผล | commit ที่รัน | หมายเหตุ |
|---|---|---|
| ex1, ex2, tamper, ex4 θ = 64/128/256, ex5 | `7485556` | รอบหลักบน 10 เครื่อง |
| ex3 (update) | `a131032` | หลังแก้ลูปซ้อนจุดแรกใน Validator (PR #11) |
| Global-MT(v) θ = 64 (กำลังรัน) | `089726d` | `--variants "Global-MT(v),Global-MT"` |
| รอบ fill (AMTP ทุกชุด, ex4) | `869cf73` | placement fill ไม่เปิด query flag · `new_new/` |
| รอบ prune (AMTP ex1, ex2, ex5, tamper) | `767289c` | fill + ทุก query flag · `runs/cloud/prune_w1/`, `new_purn/` · ex4 ของรอบนี้ (เครื่อง 2–5) ยังรัน |
| **main ก่อนรอบ fill** | หลัง PR #16 | ตรวจ Merkle เร็วขึ้น 1.2–1.25× (hash เท่าเดิมทุกตัว) และแก้ลูปซ้อนที่เหลือใน Validator **ยังไม่ได้รันบน cloud** ถ้าจะใช้ตัวเลขเวลาใหม่ต้องรัน ex1, ex2, ex3, ex5 ของ AMTP ใหม่ (ex4 ไม่กระทบ) |

---

## 7. (เสร็จแล้ว 16 พ.ย.) w3 (Global-MT(v)) — ดึงผลและ plot แล้ว เก็บขั้นตอนไว้อ้างอิง

- เครื่อง `amtp-worker3` IP `43.209.20.247` (IP เปลี่ยนทุกครั้งที่เปิดเครื่องใหม่) user `ubuntu`
- กุญแจ SSH: `~/Desktop/amtp_cloud/amtp-key.pem` (อยู่ในเครื่องเจ้าของงาน ไม่อยู่ใน repo)
- ความคืบหน้า: 15 พ.ย. 13:15 (เวลาไทย) อยู่ที่ batch 793 จาก 1,674 · batch ละ ~70 วินาที · **คาดว่าเสร็จจันทร์ 16 พ.ย. ราว 03:00–08:00 เวลาไทย**
- บนเครื่องมี `watch_gmtv.sh` รันอยู่ งานจบแล้วจะ**ดับเครื่องเองใน ~10 นาที** ผลยังอยู่ในดิสก์
- ผลอยู่ที่ `~/NewAMTP/baselines/results/runs/paper_v_gmtv/amtp/splitmerge_n100000_t64/` (updates.csv, layout.csv, queries.csv, manifest.json, summary.md) · log อยู่ที่ `~/gmtv_w3.log`

**ขั้นตอนเมื่อเสร็จ:**
1. ถ้าเครื่องดับแล้ว ให้เจ้าของงานเปิดใน AWS Console แล้วส่ง IP ใหม่มา ถ้า IP บ้านของเจ้าของงานเปลี่ยน ต้องแก้ Security Group (SSH port 22) ให้รับ IP ปัจจุบันของ Mac (ดูได้ด้วย `curl -s https://checkip.amazonaws.com`)
2. ดึงผล:
   ```
   rsync -a -e "ssh -i ~/Desktop/amtp_cloud/amtp-key.pem" \
     ubuntu@<IP>:NewAMTP/baselines/results/runs/paper_v_gmtv baselines/results/runs/cloud/w3/
   rsync -a -e "ssh -i ~/Desktop/amtp_cloud/amtp-key.pem" ubuntu@<IP>:gmtv_w3.log baselines/results/runs/cloud/w3/
   ```
3. เช็ก: Global-MT(v) ครบ 1,674 batch ไหม · log มี FAIL ไหม · manifest เป็น commit 089726d และ `git_dirty: false`
4. **เช็กว่า w3 เร็วเท่า w1:** w3 รัน Global-MT (ไม่มี v) ด้วย ให้เทียบเวลาต่อ hash กับ Global-MT ของ w1 (`gamma_with_v/amtp/splitmerge_n100000_t64/updates.csv`) ช่วงแรกเช็กแล้วต่างกันแค่ ~6% (1.86 เทียบ 1.98 µs ต่อ hash) ถ้าต่างกันมาก ต้องเขียนกำกับไว้ หรือใช้ hash_calls เทียบแทน
5. plot: เพิ่ม Global-MT(v) เป็นเส้นที่สามในรูป split/merge
   - `plot_story.py` (ค่าคงที่ `SM_VARIANTS` และฟังก์ชัน `sm_rows` ซึ่งตอนนี้อ่านแค่โฟลเดอร์ใน gamma_with_v ต้องอ่านไฟล์ของ w3 ด้วย)
   - และ/หรือรวม CSV เข้า gamma_with_v แล้วใช้ `plot_paper.py` (มี `EXP4_STYLE["Global-MT(v)"]` อยู่แล้วใน plot_results.py)
6. เขียนรายงาน แล้วเปิด PR และ merge (เจ้าของงานอนุญาตไว้แล้วว่าผล cloud ที่เสร็จให้ push ให้เพื่อนเห็นได้เลย ถ้าเจอปัญหาให้หยุดถามก่อน)

**watcher ฝั่ง Mac** (`scripts/cloud_helpers/watch_gmtv_local.sh`): ทุก 3 นาทีจะเช็กเครื่องแล้ว rsync ผลมาเมื่องานจบ ต้องตั้ง `REPO` ให้ชี้ที่ repo ถ้าไม่ได้อยู่ที่ path default ถ้าใช้ Monitor ของ Claude Code จะหมดเวลาทุก 30 นาที ต้องเปิดใหม่

---

## 8. งานค้างและเรื่องที่รอเจ้าของงานตัดสินใจ

| # | เรื่อง | สถานะ / ข้อเสนอ |
|---|---|---|
| 1 | ผล Global-MT(v) ของ w3 | ดูหัวข้อ 7 |
| 2 | **รันบน cloud ใหม่หลัง PR #16** | ยังไม่ได้ตัดสินใจ ถ้ารันต้องรัน ex1, ex2, ex3, ex5 ของ AMTP (baseline ใช้ผลเดิมได้ เพราะโค้ดไม่เปลี่ยน) · วัดบน Mac แล้ว: query เร็วขึ้น 1.2×, update insert ที่ b = 1000 จาก 51.8 เหลือ 35.2 s, Validator insert จาก 27.6 เหลือ 14.6 s (ดู `docs/reports/2026-11-15-verify-speed.md`) |
| 3 | **ขนาดไฟล์ที่ส่งกลับใหญ่กว่า baseline 307 B ต่อไฟล์** | ส่วนเกินมาจาก C_Kd 160 B, aad 52 B, cid+PID+ℓ +40 B, ห่อ body 31 B, หัว CT ~24 B · **C_Kd ถูกเก็บเป็นข้อความ hex** (`aes_gcm_encrypt` คืน hex แล้ว `enc(ck)` เก็บข้อความนั้น) ใหญ่ขึ้น ~60 B และขัดกติกา "นับเป็น binary" · ทางเลือก: ก. เก็บเป็น binary, ข. แยกต้นทุน access control ให้เห็นใน paper, ค. เลิกส่ง cid ซ้ำ (ต้องยืนยันก่อน) · **ตัดสินใจแล้ว 16 พ.ย.: ไม่แก้** (แก้แล้ว cid ทุกตัวเปลี่ยน และ response_bytes ของทุกรอบที่มีจะเทียบกันไม่ได้ ได้คืนแค่ ~3–5% ของขนาด response และไม่เปลี่ยนว่าใครชนะ) · ถ้า paper เทียบขนาด response รวมไฟล์ ให้เขียนว่า ~212 B ต่อไฟล์เป็นต้นทุน access control (C_Kd + aad) ที่ baseline ไม่มี และ C_Kd เก็บเป็น hex · ไม่กระทบกราฟที่มี เพราะทุกกราฟใช้ proof_bytes ไม่ใช่ response_bytes |
| 4 | **ลดเวลาตรวจลงอีก** (อาจารย์เสนอ reuse proof / cache proof) | เสนอไว้แล้ว ยังไม่ได้ทำ ดูหัวข้อ 9 |
| 5 | ข้อความใน paper | ยังไม่ได้แก้ ต้องแก้: เครื่อง (AWS ไม่ใช่ Mac), 15 รอบ (ไม่ใช่ 30), dataset 4 × 125k, พารามิเตอร์ Exp1–4, Exp3 นับ Validator, ส่วน Results / Conclusion / การทดลอง tamper · ยังไม่ได้ตกลงว่าใครเขียน |
| 6 | demo | เพื่อน (PrimRoseEverD) push "Demo v2" เข้า main แล้ว (`amtp_code/web/`) ยังไม่ได้ทดสอบ |
| 7 | ข้อเขียนของเพื่อนเรื่อง "จุดที่ชู / จุดที่ต้องยอมรับ" | ตรวจกับตัวเลขแล้ว · ข้อ "update ต่อไฟล์คงที่เมื่อฐานข้อมูลโต" ไม่จริง ควรเขียนว่า "โตช้ากว่า Static-MT มาก" · "ต้นทุนคงที่เมื่อเพิ่มโดเมน" ต้องเติม "ที่ domain เดียว" · "proof ต่อรายการเล็กลงเมื่อผลลัพธ์เยอะ" ถูก (617 → 224 B ต่อผลลัพธ์ ส่วน SE-COLLAB คงที่ 561 B) · "search โตตามความยาว posting" ถูก · ควรเพิ่มเรื่อง "update ช้ากว่า Chen" ในส่วนที่ต้องยอมรับ |
| 8 | ข้อความใน paper เรื่อง ex3 | paper เขียนว่าไม่นับ Validator แต่เราเลือกนับ ต้องแก้ข้อความ |

---

## 9. เรื่องลดเวลา (วิเคราะห์ไว้แล้ว ยังไม่ได้ทำ ยกเว้นข้อ A)

**ข้อเท็จจริงจาก profile** (kQ = 5, N = 100k):
- ผู้ใช้ hash ~4,700 ครั้งต่อ query
- posting ของ keyword หนึ่งกระจายอยู่หลายร้อย partition ทำให้ทุก posting ต้องมี path ภายใน partition บวก path ใน domain tree ซึ่งเป็นต้นทุนหลักของ check part

| แนวทาง | สถานะ | ผล / ข้อควรระวัง |
|---|---|---|
| A. ปรับโค้ดตรวจ (hash เท่าเดิม) | **ทำแล้ว PR #16** | เร็วขึ้น 1.2–1.25× · ปรับต่อได้อีกไม่มาก เพราะเวลาที่เหลือเป็น SHA-256 จริงกับ logic ของการตรวจ |
| B. cache ฝั่งผู้ใช้ (reuse proof) | เสนอแล้ว | เก็บของที่ตรวจผ่านแล้ว (keyword → L, partition → (v, R_P), (R_P, slot) → cid) โดยใช้ root ของ epoch เป็น key และเก็บหลัง accept เท่านั้น · ข้าม epoch ได้ถ้า v / ρ ไม่เปลี่ยน (จุดที่ v ช่วยให้เล่าได้ดี) · ช่วยแค่ query ที่ keyword ซ้ำ ไม่ช่วย query แรก · ต้องวัด cold กับ warm แยกกัน และผลหลักใน paper ต้องเป็น cold เพราะ baseline ก็ cache ได้ |
| C. จัดไฟล์ที่ keyword เดียวกันไว้ partition เดียวกัน | เสนอแล้ว | ลดจำนวน partition ต่อ query ต้องวัดก่อน |
| D. AND pruning | future work | เปลี่ยนโครงสร้าง index และ proof |
| E. accumulator (RSA / pairing) | ไม่แนะนำ | แพง และขัดกติกาที่ให้ใช้แค่ hash / Merkle / ลายเซ็น |

เจ้าของงานสั่งชัดว่า "อย่าพึ่งลดจำนวน hash" (ข้อ B–D) ต้องรอคำสั่งก่อน

---

## 10. วิธีทำงานกับเครื่อง cloud (บทเรียนที่เจอ)

- 10 เครื่อง r7i.4xlarge (16 vCPU) ชื่อ `amtp-worker1..10` · โค้ดอยู่ที่ `~/NewAMTP` · venv อยู่ที่ `~/NewAMTP/.venv` · ทุกเครื่องมี `scripts/watch_stop.sh` สำหรับดับเครื่อง
- **IP เปลี่ยนทุกครั้งที่ start เครื่อง** ต้องให้เจ้าของงานส่ง IP มา · **IP บ้านของเจ้าของงานก็เปลี่ยนได้** ถ้า ssh timeout ให้เช็ก IP ของ Mac แล้วให้เจ้าของงานแก้ Security Group
- **zsh:** `$ip:c` ถูกตีความเป็น modifier ให้ใช้ `${ip}` · `set -- $p` ไม่แยกคำ ให้รันผ่าน `bash <<'EOF'` · string ของ argument ไม่แยกคำ ให้ใช้ bash
- **`pkill -f` / `pgrep -f`:** pattern จะไปเจอคำสั่ง ssh ของเราเอง ให้ใช้วงเล็บเหลี่ยม เช่น `'[/]gmtv[.]sh'`
- ตอนรันใหม่บน cloud: บันทึก commit และ `git status` ใน log ทุกครั้ง (`cloud_worker.sh` และ `gmtv.sh` ทำแล้ว) และตั้ง watcher ดับเครื่องทุกครั้ง
- ตัวอย่างคำสั่งรัน: ex3 = `bench.experiments exp3 --reps 15 --warmup 3 --sizes 100000 --batches 1 10 100 1000` (ดู `scripts/cloud_helpers/exp3fix.sh`) · Global-MT(v) = ดู `scripts/cloud_helpers/gmtv.sh`

**สคริปต์ใน `scripts/cloud_helpers/`:**

| ไฟล์ | หน้าที่ |
|---|---|
| `gmtv.sh`, `exp3fix.sh` | งานที่รันบนเครื่อง cloud |
| `watch_gmtv.sh`, `watch_exp3fix.sh` | รันบนเครื่อง cloud: ดับเครื่องเมื่องานจบ |
| `watch_cloud.sh`, `watch_gmtv_local.sh`, `watch_exp3fix_local.sh` | รันบน Mac: เช็กทุก 3 นาที แล้ว rsync ผลกลับมาก่อนเครื่องดับ (IP ข้างในเป็นของรอบที่แล้ว ต้องแก้) |
| `scan_in.py` | สแกนหา `x in <list>` ในลูป (หาลูปซ้อน) |
| `prof_verify.py`, `ab_verify.py` | profile และ A/B การตรวจของผู้ใช้บน query จริง |

---

## 11. สิ่งที่เจ้าของงานชอบ / ไม่ชอบ

- ตอบเป็นภาษาไทย อธิบายแบบเข้าใจง่าย ถ้าเจ้าของงานงงให้อธิบายด้วยภาพหรือขั้นตอน
- ถ้าบอกว่า "คุยกันก่อน" หรือ "อย่าพึ่งทำ" ห้ามแก้อะไร
- อยากให้เทียบแบบ**ยุติธรรม** และระวังลูปซ้อน
- อยากให้เล่าด้านที่เราชนะ แต่ห้ามบิดตัวเลข: ต้องบอกช่วงที่แพ้ใน paper ด้วย
- ส่งงานให้เพื่อนผ่าน PR พร้อมรายงานเสมอ
- เคยมีหน้า Artifact สรุปผล (private): https://claude.ai/artifact/4zKSNXm3aQPU7xMnZjp7dg (เป็นของบัญชีเดิม บัญชีใหม่อาจเปิดไม่ได้)

---

## 12. ประวัติ PR (ย่อ)

| PR | เรื่อง |
|---|---|
| #3 | step 1–8: โค้ดตาม paper (encoding, B+ tree, update protocol, Validator, bench) |
| #4 | แผนการทดลองบน cloud, flag `AMTP_GAMMA_V` |
| #5–#9 | ผลบน cloud, ย้ายสคริปต์ plot เก่า, `--variants` สำหรับ Global-MT(v) |
| #10 | graph_op (กราฟเส้นเล่าเรื่อง main/limits) + ex3 หลังแก้ Validator |
| #11 | Validator: ตรวจ next pointer ของ IMT จาก O(n·m) เป็น O((n+m) log n) |
| #12 | commit `baselines/results/runs/` |
| #13, #14 | split/merge θ = 128, 256 |
| #15 | ย้ายผลแบบไม่มี v ไป `old/exp_no_v` |
| #16 | ตรวจ Merkle เร็วขึ้น 1.2× (hash เท่าเดิม) + แก้ลูปซ้อนที่เหลือใน Validator |
| #17–#23 | AND pruning, part-results, greedy planner, γ แบบเร็ว, snapshot, ผล new_new, placement fill เป็นค่าเริ่มต้น + แผน cloud "prune" (ดู `docs/reports/2026-11-16-*.md`) |
| #24 | ผลรอบ prune เครื่อง 1 + กราฟ `new_purn/` + overhead ของ flag |
| #25, #27 | `amtp_code/bench_split/`: วัด search ของ server แยกจาก proof · แก้หน่วยความจำสะสมก่อนขึ้น cloud |
| #26 | demo_v2: นับหลักฐานแบบ focus ในหน้า Evidence |
| #28 | ผล ex4 รอบ prune θ 64 / 128 + สคริปต์ cloud + ข้อตกลงเรื่องวัด search |
| #29 | ผล ex4 θ 256 รอบ prune · เลือกแบบ partition ก่อน · สรุปรวมทุกการแก้ (`2026-11-16-summary-all-changes.md`) |
| #30 | ผล search อย่างเดียวบน cloud: search1, xsearch + กราฟ `baselines/results/search_split/` + กราฟ ex4 รอบ prune (`2026-11-16-search-split-partial.md`) |
| (PR ถัดไป) | ผล search อย่างเดียว: xdomains, exp5 + กราฟ Search 2.2, Exp5 (`2026-11-16-search-split-rest.md`) |
