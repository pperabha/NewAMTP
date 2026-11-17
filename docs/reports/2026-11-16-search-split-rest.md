# ผลวัด search อย่างเดียวบน cloud: xdomains และ exp5 (รอบ split ครบแล้ว)

วันที่ 16 พ.ย. 2026 · branch `results/search-split-rest` · ต่อจาก `2026-11-16-search-split-partial.md` (PR #30)

## ทำอะไร

1. **ผลจาก cloud:** รอบวัด search อย่างเดียวเสร็จครบ (`split finished rc=0`, 23:13) ชุดที่เหลือ 2 ชุดอยู่ใน `baselines/results/runs/cloud/split_w1/paper_split/`
   - **xdomains** (Search 2.2): 120 แถว, ไฟล์รวม 400k แบ่งเป็น D = 1–32 โดเมน, kQ = 4, AND
   - **exp5** (หลายโดเมน): 396 แถว, D = 1–32, query โดเมนเดียว + update โดเมนเดียว
   - ตรวจแล้ว: commit `00f9d42`, `git_dirty: false`, เปิดทุก flag, placement fill · ไม่มี FAIL · จุดตรวจผ่านทุก query
   - `logs/plot.log` แสดงว่าเครื่อง cloud ไม่มี matplotlib (ตามคาด) จึง plot บน Mac
2. **`amtp_code/bench_split/plot_search.py`:** เพิ่มฟังก์ชัน `exp5()` วาดกราฟ search อย่างเดียวของ exp5 เทียบ SE-COLLAB (`search_core` แถว `op = query`) · test `bench_split` ผ่าน 7/7
3. **กราฟ:** `baselines/results/search_split/graphs/` เพิ่ม `Search_2.2/search_only_vs_domains.png` และ `Exp5/search_only_vs_domains.png` · `figure_points.csv` 116 จุด

## ผล (แบบ partition ก่อน, ms)

### exp5: ค้นโดเมนเดียวเมื่อระบบมี D โดเมน

| D | 1 | 2 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|---|
| AMTP search อย่างเดียว | 0.058 | 0.057 | 0.057 | 0.057 | 0.058 | 0.058 |
| SE-COLLAB `search_core` | 0.071 | 0.072 | 0.074 | 0.073 | 0.073 | 0.074 |
| AMTP end-to-end | 1.26 | 1.28 | 1.28 | 1.27 | 1.30 | 1.30 |
| SE-COLLAB end-to-end | 8.92 | 8.93 | 8.91 | 8.91 | 8.91 | 8.90 |
| AMTP update โดเมนเดียว | 72.9 | 76.4 | 78.6 | 75.0 | 77.2 | 82.7 |

**ชนะทุกจุด และคงที่ไม่ว่ามีกี่โดเมน** (search อย่างเดียวและ end-to-end)

### Search 2.2: ส่ง query ไปทุกโดเมน (ไฟล์รวมคงที่)

| D | 1 | 2 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|---|
| AMTP search อย่างเดียว | **0.110** | **0.125** | **0.162** | 0.249 | 0.397 | 0.721 |
| SE-COLLAB `search_core` | 0.852 | 0.517 | 0.339 | **0.231** | **0.156** | **0.217** |
| AMTP server รวม proof | 0.381 | 0.543 | 0.793 | 1.406 | 2.587 | 5.384 |
| SE-COLLAB server รวม | 5.61 | 5.32 | 5.09 | 5.14 | 5.07 | 5.47 |

- **search อย่างเดียว: ชนะถึง 4 โดเมน แพ้ตั้งแต่ 8 โดเมน** · AMTP ค้นแยกทีละโดเมน เวลาโตตาม D ส่วนที่โตคือ lookup (D = 32: 0.40 จาก 0.72 ms) · SE-COLLAB เร็วขึ้นเมื่อโดเมนเล็กลง
- **server รวม proof ยังชนะทุก D** (กราฟ `new_purn/.../Search_2.2/server_vs_domains.png`)
- ต้องเขียนใน paper: กรณีส่ง query ไปทุกโดเมนพร้อมกันเมื่อมีโดเมนมาก ส่วน search อย่างเดียวแพ้ SE-COLLAB

## สรุปผลรอบ search อย่างเดียวทั้งหมด

| กราฟ | SE-COLLAB | Chen | Du |
|---|---|---|---|
| Search 1.1 / 1.2 (โดเมนเดียว) | ✅ ทุกจุด | ❌ ทุกจุด | ✅ ทุกจุด |
| Search 2.1 AND, OR-of-AND | ✅ ทุกจุด | – | – |
| Search 2.1 AND-of-OR | ชนะ 3/4 (แพ้ kQ 16) | – | – |
| Search 2.1 OR | แพ้ kQ ≥ 4 (fetch) | – | – |
| Search 2.2 | ชนะถึง D = 4 | – | – |
| exp5 | ✅ ทุกจุด | – | – |

งานต่อที่ตัดสินใจแล้ว: เปลี่ยน leaf ของ Search Tree เป็นแบบ ก (ชุด partition + map PID → ไฟล์) เพื่อให้ search อย่างเดียวชนะ Chen จะทำใน PR แยก

## วิธี plot ซ้ำ

```
cd amtp_code
../.venv/bin/python -m bench_split.plot_search --amtp ../baselines/results/runs/cloud/split_w1/paper_split/amtp \
    --out ../baselines/results/search_split/graphs
```

## เพิ่มเติม: ex4 Global-MT(v) รอบ prune (เครื่อง 5)

- เสร็จ 17 พ.ย. 01:07 ดึงมาไว้ที่ `baselines/results/runs/cloud/prune_w5/` · ตรวจแล้ว: 1,674 batch, commit `767289c`, `git_dirty: false`, ไม่มี FAIL
- plot ใหม่: `baselines/results/new_purn/graphs/paper/ex4_split_merge/` (θ 64 และรูปเทียบ θ มีเส้น Global-MT(v) แล้ว) และ `story/main/` 2 รูป · `new_purn/README.md` อัปเดตแล้ว

| θ = 64 (median ต่อ batch) | update | query server | query ตรวจ | partition ใหญ่สุด |
|---|---|---|---|---|
| AMTP | **1.05 s** | 5.3 ms | 12.3 ms | 64 |
| Static-MT | 13.5 s | 5.0 ms | 10.2 ms | — |
| Global-MT(v) | 29.4 s | **3.1 ms** | **3.2 ms** | 132,600 |

AMTP update เร็วกว่า Global-MT(v) 28× แต่ query ช้ากว่า เพราะ Global-MT(v) มี partition เดียว (ต้องเขียนใน paper เหมือนรอบ fill)

## สถานะ

- เพิ่มผล กราฟ และฟังก์ชัน plot ใน `bench_split/` เท่านั้น ไม่มีโค้ดของ AMTP, benchmark หรือ baseline เปลี่ยน
- ทุกเครื่องของรอบ prune และรอบ search อย่างเดียวเสร็จครบแล้ว
