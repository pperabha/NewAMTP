# B5: รูปและผลการทดลองของ AMTP (32) สำหรับ Overleaf

คน B (PrimRoseEverD) · 19 พ.ย. 2026 · ข้อมูล: PR #71 (`results/paper32-figures`) `baselines/results/paper32/`
รูป: `baselines/results/paper32/figures/*.pdf` (103 รูป) · ตัวเลขทุกตัวในไฟล์นี้มาจาก `figure_points.csv` ของ PR #71
วิธีใช้เหมือน B4: ค้นหา / ลบ / วาง (`docs/paper32_overleaf_B4.md`) · ทำ B4 ให้เสร็จก่อน (Setup, ตัวเลข N ของแต่ละ Exp)

## 0. ต้องรู้ก่อนวาง

1. **ค่าที่ plot (#72 = A, เจ้าของงาน):** จุดของ query (Exp 1, Exp 2 verify, Exp 5 query, tamper verify) = **median ข้าม query + error
   bar IQR** ตาม #66 และประโยค Setup ใน E1 ของ B4 ใช้ได้ตามเดิม · Exp 3, Exp 4, update isolation และ Sepolia = mean ข้าม run / batch
   (#46) ไม่มี bar · **ตัวเลขทั้งหมดในไฟล์นี้มาจาก `figure_points.csv` ฉบับหลัง #72 (commit `74f259e`)**
2. **อัปโหลดรูป:** สร้างโฟลเดอร์ `figs/` ใน Overleaf แล้วอัปโหลดเฉพาะ PDF ที่ใช้ (รายการในข้อ 1 ของแต่ละรูป)
   จาก `baselines/results/paper32/figures/` (อยู่ใน `feat/paper32-experiments` แล้ว หลัง merge PR #71)
3. **preamble:** ถ้ายังไม่มี ให้เพิ่ม `\usepackage[caption=false,font=footnotesize]{subfig}` (แบบที่ IEEEtran แนะนำ)
4. **เลขรูป:** paper มี Fig. 1 (system model) และ Fig. 2 (workflow) แล้ว รูปผลเริ่มที่ Fig. 3 · ใช้ `\ref` เสมอ
5. ห้ามใช้ `e5_root_gas_localevm` (gas ของ py-evm ไม่ตรง Ethereum) · ใช้ `e5_sepolia_gas` เท่านั้น
6. เจ้าของงาน (#66): **ไม่อธิบาย** query ที่ผลมากหรือ OR ล้วนในเนื้อหา แต่รูป OR ยังอยู่ตาม (32) · กติกาทีม: บอกตรงๆ ว่าแพ้ตรงไหน
   → ประโยคที่บอกแพ้ใน OR เขียนเป็นข้อเท็จจริงสั้นๆ ไม่อธิบายเหตุ และติดป้าย **[ถาม A]** ให้ A เลือกเก็บหรือตัด

## 1. เพิ่มใน Setup [ตาม #68 / PR #69] (ใส่ใน E1 ของ B4 แล้ว: ทำข้อนี้เฉพาะถ้าวาง E1 ฉบับเก่าไปแล้ว)

ค้นหา: `and the CP-ABE decryption of returned records.` (ท้ายย่อหน้า Setup ที่วางจาก B4 E1)
→ **วางต่อท้าย**

```latex
The DU reads the anchored root and decrypts the returned records once per query, outside the timed
repetitions; query generation, the CS's work, and all verification checks run in every repetition.
```

---

## 2. Experiment 1: Boolean Search Scalability

### Fig. 3 (single domain) [M1] · รูป: `e1_single_kq_search`, `e1_single_n_search`, `e1_single_kq_e2e`, `e1_single_n_e2e`

ค้นหา: `Experiment 1: Boolean Search Scalability` → ย่อหน้าคำอธิบายจบที่ `supported by their constructions.`
→ **วางต่อท้าย** (บล็อกรูป + ย่อหน้าผล)

```latex
\begin{figure*}[t]
\centering
\subfloat[Server search, $N = 10^5$]{\includegraphics[width=0.24\textwidth]{figs/e1_single_kq_search.pdf}\label{fig:e1-kq-search}}\hfil
\subfloat[Server search, $k_Q = 4$]{\includegraphics[width=0.24\textwidth]{figs/e1_single_n_search.pdf}\label{fig:e1-n-search}}\hfil
\subfloat[End-to-end, $N = 10^5$]{\includegraphics[width=0.24\textwidth]{figs/e1_single_kq_e2e.pdf}\label{fig:e1-kq-e2e}}\hfil
\subfloat[End-to-end, $k_Q = 4$]{\includegraphics[width=0.24\textwidth]{figs/e1_single_n_e2e.pdf}\label{fig:e1-n-e2e}}
\caption{Single-domain conjunctive search. Server search is posting retrieval and Boolean evaluation,
without proof generation or ciphertext retrieval. Chen et al.'s server does not evaluate the
conjunction (the DU intersects the decrypted bitmaps); Du et al.\ is the slowest of its clouds.
End-to-end is query generation, server time, and DU verification.}
\label{fig:e1-single}
\end{figure*}

\textbf{Results.} Fig.~\ref{fig:e1-single} shows single-domain conjunctive queries. AMTP's server
search is 4.4--23$\times$ faster than SE-COLLAB and at least 11$\times$ faster than Du et al.\ at
every $k_Q$. Against Chen et al., AMTP is 10--21\% faster from $k_Q = 2$, although Chen et al.'s
server does not evaluate the conjunction, and slightly slower for a single keyword (0.0088 vs.\
0.0083\,ms). As the domain grows from $10^4$ to $1.25 \times 10^5$ documents, AMTP's search time
rises by 18\% (0.020 to 0.023\,ms), Chen et al.'s by 72\%, and SE-COLLAB's by 4.3$\times$; Chen et al.\
is faster at $10^4$ and $2.5 \times 10^4$ documents, and AMTP from $5 \times 10^4$. End to end, AMTP
takes 0.41--1.75\,ms, 1.1--5.3$\times$ less than Chen et al., whose DU work grows with the bitmap
length, and 5.3--22$\times$ less than SE-COLLAB, whose query generation alone costs 3.3\,ms. Du et al.\
is 22--31\% faster end to end for $k_Q \ge 2$ and at every domain size, and Chen et al.\ is faster at
$10^4$ documents (0.44 vs.\ 0.54\,ms).
```

### Fig. 4 (multi-domain Boolean) [M2, M3] · รูป: `e1_multi_AND_search`, `e1_multi_OR_search`, `e1_multi_AND_of_OR_search`, `e1_multi_OR_of_AND_search`
→ **วางต่อท้าย** ย่อหน้าผลของ Fig. 3

```latex
\begin{figure*}[t]
\centering
\subfloat[$A \wedge B \wedge \dots$]{\includegraphics[width=0.24\textwidth]{figs/e1_multi_AND_search.pdf}}\hfil
\subfloat[$A \vee B \vee \dots$]{\includegraphics[width=0.24\textwidth]{figs/e1_multi_OR_search.pdf}}\hfil
\subfloat[$(A \vee B) \wedge (C \vee D)$]{\includegraphics[width=0.24\textwidth]{figs/e1_multi_AND_of_OR_search.pdf}}\hfil
\subfloat[$(A \wedge B) \vee (C \wedge D)$]{\includegraphics[width=0.24\textwidth]{figs/e1_multi_OR_of_AND_search.pdf}}
\caption{Server search time for Boolean queries over four domains of $10^5$ documents each (one
domain-bound query per domain). SE-COLLAB is the only baseline that supports these expressions.}
\label{fig:e1-multi}
\end{figure*}

Fig.~\ref{fig:e1-multi} compares the four Boolean forms of the experiment with SE-COLLAB over four
domains. AMTP is faster at every $k_Q$ for conjunctions (2.4--4.9$\times$), for
$(A \wedge B) \vee (C \wedge D)$ (2.8--5.1$\times$), and for $(A \vee B) \wedge (C \vee D)$
(1.8--7.8$\times$). For a disjunction, AMTP is faster with two keywords and SE-COLLAB from four
keywords (4.5 vs.\ 1.7\,ms at $k_Q = 16$). % [ถาม A] เก็บหรือตัดประโยค OR นี้ (#66)
```

ถ้าต้องการรูป end-to-end ของ multi-domain ด้วย (ไม่บังคับ): `e1_multi_*_e2e` — ตัวเลข: AND AMTP 1.3–6.3 vs SE-COLLAB 9.5–10.4 ms;
(A∨B)∧(C∨D) ชนะทุก kQ (3.4–7.8 vs 9.9–11.8 ms); (A∧B)∨(C∧D) ชนะที่ kQ 2–8 แต่**แพ้ที่ kQ 16** (18.9 vs 11.2 ms); OR แพ้ทุก kQ

### Search 2.2 (ไม่บังคับ, ซ้อนกับ Exp 5) · `e1_domains_search`, `e1_domains_e2e`
ตัวเลข (ไฟล์ 400k แบ่งเป็น D domain, query ไปทุก domain): search AMTP 0.027 → 0.59 ms (เพิ่มตาม D เพราะส่ง query ทุก domain),
SE-COLLAB 0.83 → 0.18 ms → AMTP เร็วกว่าถึง D = 8, **ช้ากว่าที่ D = 16, 32**; end-to-end AMTP เร็วกว่าถึง D = 16 (6.9 vs 9.6 ms),
**ช้ากว่าที่ D = 32** (13.3 vs 10.0 ms) · ถ้าใส่ ต้องเขียนจุดที่แพ้ด้วย

---

## 3. Experiment 2: Selective Proof, Verification, and Tamper Detection

### Fig. 5 (clustered vs dispersed ตาม (32)) · รูป: `e2_layouts_proof`, `e2_layouts_verify`, `e2_layouts_proof_kb`
ค้นหา: `Experiment 2: Selective Proof` → ย่อหน้าคำอธิบาย (ที่แก้ใน B4 E3 แล้ว) จบที่ `for every scheme.`
→ **วางต่อท้าย**

```latex
\begin{figure*}[t]
\centering
\subfloat[Proof generation]{\includegraphics[width=0.32\textwidth]{figs/e2_layouts_proof.pdf}\label{fig:e2-proof}}\hfil
\subfloat[DU verification]{\includegraphics[width=0.32\textwidth]{figs/e2_layouts_verify.pdf}\label{fig:e2-verify}}\hfil
\subfloat[Proof size]{\includegraphics[width=0.32\textwidth]{figs/e2_layouts_proof_kb.pdf}\label{fig:e2-size}}
\caption{Selective proof for one domain of $10^5$ documents and a marker keyword with $r_Q$ matches
placed in few partitions (clustered), in many partitions (dispersed), or one per partition (partition
spread). Chen et al.\ and Du et al.\ have no separate proof-generation step.}
\label{fig:e2-layouts}
\end{figure*}

\textbf{Results.} Fig.~\ref{fig:e2-layouts} shows that AMTP's proof work follows the partitions that
the matches occupy. For $r_Q = 1{,}000$, the clustered layout covers 39 partitions and the dispersed
one 880: proof generation takes 0.71 vs.\ 5.7\,ms, verification 16.7 vs.\ 32.5\,ms, and the proof
55 vs.\ 320\,KB. SE-COLLAB's proof does not depend on the layout and grows with $r_Q$ (561\,KB at
$r_Q = 1{,}000$); AMTP's proof is smaller in every layout from $r_Q = 100$ (at most 1.0\,MB vs.\
2.8\,MB at $r_Q = 5{,}000$). AMTP generates proofs faster than SE-COLLAB for clustered matches at every
$r_Q$, but more slowly for dispersed matches from $r_Q = 100$ (22.7 vs.\ 17.5\,ms at $r_Q = 5{,}000$),
and its verification is slower than SE-COLLAB's from $r_Q = 100$ (84--129 vs.\ 55--58\,ms at
$r_Q = 5{,}000$). Chen et al.\ verifies fastest with a constant 32-byte tag, and Du et al.\ is the slowest
(361--369\,ms, 17\,MB at $r_Q = 5{,}000$).
```

### Fig. 6 (verify ตาม r_Q, tamper) [M4, M5, M6] · รูป: `e2_single_verify_verify`, `e2_multi_verify_verify`, `e2_tamper_hide_detection`, `e2_tamper_inject_detection`
→ **วางต่อท้าย** ย่อหน้าผลของ Fig. 5

```latex
\begin{figure*}[t]
\centering
\subfloat[Verification, one domain]{\includegraphics[width=0.24\textwidth]{figs/e2_single_verify_verify.pdf}\label{fig:e2-v1}}\hfil
\subfloat[Verification, four domains]{\includegraphics[width=0.24\textwidth]{figs/e2_multi_verify_verify.pdf}\label{fig:e2-v2}}\hfil
\subfloat[Detection: hidden files]{\includegraphics[width=0.24\textwidth]{figs/e2_tamper_hide_detection.pdf}\label{fig:e2-hide}}\hfil
\subfloat[Detection: injected files]{\includegraphics[width=0.24\textwidth]{figs/e2_tamper_inject_detection.pdf}\label{fig:e2-inject}}
\caption{(a), (b) DU verification for real keywords with $r_Q$ results; (c), (d) share of tampered
responses that the DU rejects when $t$ returned files are hidden or non-matching files are injected.
Four domains: SE-COLLAB is the only baseline.}
\label{fig:e2-verify-tamper}
\end{figure*}

For real keywords (Fig.~\ref{fig:e2-v1}), AMTP verifies in 0.52--69.8\,ms for $r_Q$ from 10 to
10{,}000, faster than Du et al.\ (0.75--179\,ms) and faster than SE-COLLAB only at $r_Q = 10$
(SE-COLLAB: 1.04--28.7\,ms); Chen et al.\ is the fastest (0.28--7.7\,ms). AMTP's proof is 6--573\,KB,
against 6--1{,}431\,KB for SE-COLLAB and 35\,KB--8.7\,MB for Du et al. Over four domains
(Fig.~\ref{fig:e2-v2}) the picture is the same: AMTP is faster than SE-COLLAB at $r_Q = 10$ and slower
beyond (258 vs.\ 109\,ms at $r_Q = 10{,}000$), with a smaller proof from $r_Q = 100$ (2.2 vs.\ 5.3\,MB
at $r_Q = 10{,}000$).
AMTP rejected every tampered response for all four attacks (modified, hidden, injected, and older
versions of files) and all $t$ from 5 to 1{,}000, and accepted every honest response.
SE-COLLAB did not detect hidden or injected files (Fig.~\ref{fig:e2-hide}, \ref{fig:e2-inject}),
Du et al.\ did not detect injected files, and Chen et al.'s model does not cover modified or older
ciphertexts. For hidden files, AMTP rejects in about 31\,ms, against 6\,ms for Chen et al.,
23\,ms for SE-COLLAB (which does not detect them), and 145\,ms for Du et al.
```

---

## 4. Experiment 3: Dynamic Update Scalability

### Fig. 7 · รูป: `e3_b_per_request`, `e3_n_per_request`, `e3_b_breakdown_insert`
ค้นหา: `Experiment 3: Dynamic Update Scalability` → ย่อหน้าจบที่ `reported apart.` (ประโยคที่เพิ่มใน B4 E3)
→ **วางต่อท้าย**

```latex
\begin{figure*}[t]
\centering
\subfloat[Per request vs.\ batch size, $N = 10^5$]{\includegraphics[width=0.32\textwidth]{figs/e3_b_per_request.pdf}\label{fig:e3-b}}\hfil
\subfloat[Per request vs.\ $N$, $b = 100$]{\includegraphics[width=0.32\textwidth]{figs/e3_n_per_request.pdf}\label{fig:e3-n}}\hfil
\subfloat[AMTP insertion breakdown, $N = 10^5$]{\includegraphics[width=0.32\textwidth]{figs/e3_b_breakdown_insert.pdf}\label{fig:e3-break}}
\caption{Dynamic updates without split or merge. AMTP: signed requests (ABS), CS preparation, DO
validation, and anchoring on a local EVM; Chen et al.: token generation and CS update, without update
verification or request authorization. In (c), ABS, posting repair, and authentication-tree
maintenance are parts of the request, CS preparation, and DO validation.}
\label{fig:e3}
\end{figure*}

\textbf{Results.} Updates are AMTP's most expensive operation (Fig.~\ref{fig:e3}). One insertion takes
287\,ms when every request is its own epoch and 35\,ms per request in batches of 1{,}000, whereas
Chen et al.\ needs 1.2--1.5\,ms per request at every batch size; AMTP's throughput rises from 3.5 to
28.5 requests per second against about 700 for Chen et al. Most of the gap is authorization: the
attribute-based request signature and its two verifications take 2.1\,s of the 5.1\,s protocol time of
a batch of 100 insertions and 21.2\,s of 34.9\,s for a batch of 1{,}000, while posting repair (0.75\,s)
and authentication-tree maintenance (0.29\,s) remain small. For $b = 1$, anchoring on the contract
(142\,ms) is half of the update. As the domain grows from $10^4$ to $1.25 \times 10^5$ documents at
$b = 100$, AMTP's cost per request grows by 1.5$\times$ (35 to 53\,ms) and Chen et al.'s by 3$\times$
(0.54 to 1.64\,ms). Deletions behave like insertions. On Sepolia, anchoring an update adds 11.0\,s
(median), outside these protocol times.
```

---

## 5. Experiment 4: Adaptive Partitioning under Skewed Growth [M7]

### Fig. 8 · รูป: `e4_update_insert`, `e4_update_delete`, `e4_max_partition`, `e4_query_verify`
ค้นหา: `Experiment 4: Adaptive Partitioning under Skewed` → ย่อหน้าจบที่ `keeping restructuring overhead bounded.`
→ **วางต่อท้าย**

```latex
\begin{figure*}[t]
\centering
\subfloat[Insertion batches]{\includegraphics[width=0.24\textwidth]{figs/e4_update_insert.pdf}\label{fig:e4-ins}}\hfil
\subfloat[Deletion batches]{\includegraphics[width=0.24\textwidth]{figs/e4_update_delete.pdf}\label{fig:e4-del}}\hfil
\subfloat[Largest partition]{\includegraphics[width=0.24\textwidth]{figs/e4_max_partition.pdf}\label{fig:e4-max}}\hfil
\subfloat[DU verification]{\includegraphics[width=0.24\textwidth]{figs/e4_query_verify.pdf}\label{fig:e4-ver}}
\caption{Skewed growth: 25{,}000 documents, 250 batches of 100 insertions with a fraction $s$ on one
hot group, then deletion of 65\% of the hot group. AMTP, Static-MT, and Global-MT(v) are compared at
the index level; AMTP (full protocol) adds signed requests, DO validation, and anchoring around the same
index work and is not directly comparable with the other two.}
\label{fig:e4}
\end{figure*}

\textbf{Results.} Adaptive partitioning keeps every partition at $\theta_{\max} = 64$ live entries for
all skew levels, whereas the largest Static-MT partition grows to 3{,}209--8{,}206 entries and
Global-MT(v) keeps all 33{,}000--48{,}000 entries in one tree (Fig.~\ref{fig:e4-max}). An insertion
batch costs 443--694\,ms in AMTP, 3.6--6.9$\times$ less than Static-MT and 9.9--15.8$\times$ less than
Global-MT(v) (Fig.~\ref{fig:e4-ins}). For deletions, Static-MT is about as fast as AMTP without skew
(1.26 vs.\ 1.32\,s per batch), and AMTP is up to 2.2$\times$ faster as the skew grows
(Fig.~\ref{fig:e4-del}). Splits and merges take 7--9\,ms per batch, about 1--2\% of AMTP's update time,
with 282--376 restructuring events per run. The price is on the query side: with more, smaller
partitions, AMTP's verification (4.7--6.0\,ms) and proofs (60--79\,KB) are slightly larger than
Static-MT's (4.3--5.2\,ms, 56--74\,KB) and Global-MT(v)'s (2.6--3.3\,ms, 47--64\,KB)
(Fig.~\ref{fig:e4-ver}).
```

---

## 6. Experiment 5: Multi-Domain Scalability and Isolation [M8]

### Fig. 9 · รูป: `e5_query_e2e`, `e5_query_verify`, `e5_isolation_update`, `e5_sepolia_gas`
ค้นหา: `Experiment 5: Multi-Domain Scalability and Isolation` → ย่อหน้าจบที่ `are compared with Du et al. [7].`
→ **วางต่อท้าย**

```latex
\begin{figure*}[t]
\centering
\subfloat[End-to-end query]{\includegraphics[width=0.24\textwidth]{figs/e5_query_e2e.pdf}\label{fig:e5-e2e}}\hfil
\subfloat[DU verification]{\includegraphics[width=0.24\textwidth]{figs/e5_query_verify.pdf}\label{fig:e5-ver}}\hfil
\subfloat[Update of one domain]{\includegraphics[width=0.24\textwidth]{figs/e5_isolation_update.pdf}\label{fig:e5-iso}}\hfil
\subfloat[Gas per root update (Sepolia)]{\includegraphics[width=0.24\textwidth]{figs/e5_sepolia_gas.pdf}\label{fig:e5-gas}}
\caption{Multi-domain scalability with the queried domain fixed at 5{,}000 documents. (c) one epoch on
the target domain with the RootAnchor contract on a local EVM; every other Domain Root is checked to be
unchanged. (d) gas of one root submission on Ethereum Sepolia.}
\label{fig:e5}
\end{figure*}

\textbf{Results.} Query cost does not depend on the number of domains (Fig.~\ref{fig:e5}): from
$D = 1$ to 32, AMTP's end-to-end time stays at 1.35--1.40\,ms against 9.38--9.40\,ms for SE-COLLAB,
its server search at 0.037--0.039\,ms against 0.065--0.067\,ms, and its verification at
0.81--0.84\,ms against 0.99--1.00\,ms. Updating one domain never changed another Domain Root. Its protocol
time stays at 96--103\,ms, while the full update grows from 238 to 295\,ms because the contract
recomputes the Global Root over all $D$ domains (anchoring 142 to 192\,ms on the local EVM). On
Sepolia, a root update costs 86.7k gas for one domain and grows by about 16k gas each time $D$
doubles, to 166.5k gas at $D = 32$ (the depth of the Global Root tree), and typically takes 11--12\,s to be
mined.
```

ถ้าจะใส่ Du (ไม่บังคับ, เจ้าของงานเลือกรูปหลักเป็น AMTP vs SE-COLLAB): Du ต้องมีอย่างน้อย 3 cloud จึงเริ่มที่ D = 4 (`--with-du`)

---

## 7. ตาราง ABS (B4 E4)
ใช้ตาราง E4 ของ B4 · ตัวเลข SS512 ในตารางควรตรงกับที่ใช้ในการทดลอง (sign + 2 verify ต่อ request ≈ 21 ms ต่อ request จาก Exp 3
`ABS sign + 2 verify` 2,119 ms / 100 requests)

## 8. ตรวจหลังวาง
- [ ] ทุก `\ref{fig:e…}` ไม่เป็น ??, เลขรูป 3–9 เรียงตามลำดับที่อ้าง
- [x] #72 = A: median + IQR (รูปและตัวเลขในไฟล์นี้ตรงกันแล้ว)
- [ ] [ถาม A] ประโยค OR ใน Exp 1
- [ ] Recompile: รูป `figure*` 4 ช่องอ่านออก (ถ้าแน่นไป ใช้ 2×2 ด้วย `\\` หลังช่องที่ 2 และ width=0.45)
- [ ] ความยาว paper: ถ้าเกิน ตัดรูป (ไม่บังคับ) ก่อน แล้วรวม Fig. 5 + 6 เป็นรูปเดียว
