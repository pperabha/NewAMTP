# วิธีวาง LaTeX ลง Overleaf ทีละจุด (part leaf + ส่วนที่เราแก้) · _somo

เทียบกับ **AMTP (21).pdf** (17 พ.ย.) · เลขหน้าเป็นหน้าของ PDF นี้ · LaTeX เดียวกับ `docs/paper_latex_2026-11-17_somo.tex`

## วิธีใช้ (แบบเดียวกับเอกสารของเพื่อน)

1. ใน Overleaf เปิดไฟล์ `.tex` ของ paper แล้วกด **Ctrl+F** (Mac: Cmd+F)
2. วางข้อความในช่อง **ค้นหา** ข้อความเหล่านี้เลือกมาเฉพาะคำธรรมดา ไม่มีสูตร จึงเจอในไฟล์ `.tex` ได้ตรงๆ
   ถ้าไม่เจอ ให้ลองค้นแค่ครึ่งแรกของข้อความ (ใน .tex อาจขึ้นบรรทัดใหม่กลางประโยค)
3. ทำตามคำสั่ง: **ลบตั้งแต่ … ถึง …** แล้ว **วางแทน**, หรือ **วางต่อท้าย** / **วางก่อน** ข้อความที่ค้นเจอ
4. กด Recompile แล้วเทียบกับ PDF ว่าอยู่ถูกที่

ทำตามลำดับในเอกสารนี้ (เรียงตามหน้า) · ข้อที่มีป้าย **แทนของเพื่อน** ให้ใช้ของเราแทนบล็อกในเอกสารของเพื่อน

## part leaf: posting list เปลี่ยนไหม

**ไม่เปลี่ยน** สมการ (13)–(15) (`L_w`, `L_{w,j}`, `Sel_i(h_w)`) และ PAPC (16)–(18) เหมือนเดิมทุกตัว
สิ่งที่เพิ่มคือ **ข้อมูลเสริมใน leaf ของ Search Tree** ซึ่งตอนนี้เขียนเป็นสมการได้ (ข้อ 2 ข้างล่าง, `\label{eq:part-leaf}`)
ไม่มี lemma หรือ theorem ใหม่ เพราะผู้ใช้ไม่เคยเห็นข้อมูลนี้ และ response เหมือนเดิมทุก byte
ครบชุดของ part leaf ใน paper = ข้อ **2, 3, 4, 5, 8, 10** ข้างล่าง

---

## 1. (1.12) [C] CS bullet · หน้า 4 · **แทนของเพื่อน** (จุดที่ 2 ของ 5.4 ในเอกสารเพื่อน)

ค้นหา: `using ASPA to share Merkle paths`
→ ลบตั้งแต่ `using ASPA` ถึง `Merkle paths.` (รวมจุด) แล้ววาง

```latex
using ASPA to share Merkle paths across the opened records and partitions and, for
conjunctions, to omit the posting components that lie outside the partitions where a match
can lie, together with evidence that no component inside them was withheld.
```

เหตุผล: ของเพื่อน "omit posting components that cannot contain a match" ไม่ได้บอกว่าตัดเฉพาะ AND และมีหลักฐานว่าตัดถูก
(DU bullet หน้า 5: **ใช้ของเพื่อนตามเดิม** ไม่ต้องแก้เพิ่ม)

## 2. (1.13) [B] Table II แถวใหม่ · หน้า 4 · part leaf

ค้นหา: `Partitions containing postings for`
→ ไปท้ายแถวนั้น (หลัง `\\`) แล้ว**วางต่อท้าย** เป็นแถวใหม่

```latex
$\mathsf{Aux}_i(h_w)$ & Partition set and component positions kept in the Search Tree leaf \\
```

## 3. (1.13) [B] Phase 2 Step 2: สมการ leaf ของ Search Tree · หน้า 7 · part leaf

ค้นหา: `the commitments below authenticate`
→ ประโยคนี้จบที่ `the returned posting state.` **วางต่อท้าย** (ย่อหน้าเดิม ก่อน `Step 3: PAPC`)

```latex
For a key in at least three partitions, the leaf of $h_w$ also keeps auxiliary lookup data
next to $L_w$:
\begin{equation}
\mathsf{Aux}_i(h_w) =
\begin{cases}
\big(\mathsf{Sel}_i(h_w),\, \mathsf{pos}_w\big), & |\mathsf{Sel}_i(h_w)| \ge 3,\\
\bot, & \text{otherwise},
\end{cases}
\label{eq:part-leaf}
\end{equation}
where $\mathsf{pos}_w(PID_{i,j}) = j$ when $(PID_{i,j}, L_{w,j})$ is the $j$-th component of
$L_w$. Both are derived from $L_w$ when the snapshot is built, so the CS obtains
$\mathsf{Sel}_i(h_w)$ and any single component without scanning $L_w$. $\mathsf{Aux}_i$ is
lookup data, not evidence: it is never sent to the DU, the posting state and the PAPC are
unchanged, and every response is the same with or without it. On 100{,}000 documents it adds
6\% to the snapshot memory and 1.5\% to its build time.
```

## 4. (1.7) [B] Phase 4 Step 2: CS อ่านชุด partition จาก leaf · หน้า 10 · part leaf

ค้นหา: `the CS resolves the Search Tree and obtains`
→ ลบตั้งแต่ `For every` (ต้นประโยคนี้) ถึง `.` หลัง `\mathsf{Sel}_i(h)` แล้ววาง

```latex
For every $h \in H_Q$, the CS resolves the Search Tree and obtains $\mathsf{Sel}_i(h)$ from
$\mathsf{Aux}_i(h)$ in \eqref{eq:part-leaf} when it is stored, and from $L_h$ otherwise; for
focus evidence it takes the components of $\mathsf{Seg}_h$ through $\mathsf{pos}_h$ without
scanning $L_h$.
```

## 5. (2.1) [B] IV-A Assumptions: ประโยคความปลอดภัยของ part leaf · หน้า 14 · ใหม่

ค้นหา: `The RA correctly verifies root authorization`
→ **วางก่อน** ประโยคนี้ (ต่อท้ายประโยค `... strictly increasing $PID$ order.`)

```latex
The Cuckoo filter and the Search Tree, including the auxiliary data
$\mathsf{Aux}_i$ in its leaves, are untrusted lookup structures of the CS; the DU never uses
them, and every accept decision rests on the IMT, PAPC, and Merkle checks of Phase~5.
```

## 6. (2.3) [C] proof ของ Lemma 1 · หน้า 15 · ข้อของเพื่อน (ยังไม่อยู่ใน PDF 21)

ค้นหา: `Canonical encodings and authenticated structure exclude ambiguous openings`
→ **วางก่อน** ประโยคนี้

```latex
The same argument applies to the next pointer of an IMT leaf and to the leaf count $n_h$ and
the leaf positions of an $R^{post}_h$ tree.
```

## 7. (2.7) [C] proof ของ Theorem 2 · หน้า 16 · ข้อของเพื่อน (ยังไม่อยู่ใน PDF 21)

ค้นหา: `inconsistent with these subroots likewise implies`
→ ประโยคนี้จบที่ `a collision.` **วางต่อท้าย** (ก่อน `Therefore,`)

```latex
This includes the versions in $\mathsf{Ver}_Q$, which are inputs of authenticated $\gamma$
values.
```

## 8. (3.4) [A] Experimental Setup · หน้า 18–19 · part leaf (แก้ 2 จุด)

จุดที่ 1 — ค้นหา: `and result-only partition proofs`
→ ลบ `and result-only partition proofs;` แล้ววาง

```latex
result-only partition proofs, and the auxiliary Search Tree data of \eqref{eq:part-leaf};
```

จุดที่ 2 — ค้นหา: `Experiment 4 also uses`
→ ประโยคนี้จบที่ `\theta_{\max}/4$.` **วางต่อท้าย**

```latex
Experiments~3 and~4 were run before the auxiliary Search Tree data was added; it changes
neither the update procedure nor any proof or response, only the server's search time.
```

## 9. (3.6) [C] Baselines: เครื่องที่ใช้วัด · หน้า 19 · ใหม่

ค้นหา: `All schemes run on the same machine`
→ ลบตั้งแต่ `All schemes run` ถึง `query files.` แล้ววาง

```latex
All schemes run on AWS \texttt{r7i.4xlarge} instances with the same documents, keywords, and
query files, one job at a time. Each baseline is measured on the instance of the AMTP suite it
is compared with, except the search-only runs of SE-COLLAB and Du et al., which were repeated
on two further instances of the same type; on the same workload, instances of this type
differed by at most 7\%.
```

## 10. (3.6b + 3.6) [B] Search-only time · หน้า 19 · part leaf + ไม่ดึงไฟล์ (แก้ 3 จุด)

จุดที่ 1 — ค้นหา: `from the partition lists of the keys`
→ ลบ `from the partition lists of the keys,` แล้ววาง

```latex
from the partition sets of the keys (read from $\mathsf{Aux}_i$ in \eqref{eq:part-leaf} for
keys in at least three partitions),
```

จุดที่ 2 — ค้นหา: `No structure beyond those of Phase 2 is used.`
→ ลบประโยคนี้ แล้ววาง

```latex
It uses only the Cuckoo filter and the Search Tree of Phase~2.
```

จุดที่ 3 — ค้นหา: `For the search-only comparison, SE-COLLAB reports`
→ ลบตั้งแต่ `For the search-only comparison` ถึง `which is its best case.` (จบย่อหน้า) แล้ววาง

```latex
For the search-only comparison, every scheme is timed without proof generation and without
returning ciphertexts. AMTP's search time is the lookup, focus-set derivation, and Boolean
evaluation. For SE-COLLAB we use its own timers for posting retrieval and Boolean evaluation;
for Du et al.\ the server traversal that returns only the matching positions (slowest cloud);
for Chen et al.\ the whole server time, which also includes one XOR per visited entry for its
proof tag. Chen et al.\ is measured after warm-up, when its update chain has been collapsed by
the first search, which is its best case.
```

กราฟที่ใช้กับย่อหน้านี้: `baselines/results/part_leaf/graphs/search_no_fetch/` (ทุก scheme ไม่ดึงไฟล์ AMTP เส้นเดียว)

---

## ไม่ต้องแก้

- สมการ (13)–(18), Algorithm 2–3, Phase 5, Lemma 2–3, Theorem 1: part leaf ไม่กระทบ
- Fig. 2: ไม่ต้องวาด `Aux` (ถ้าอยากวาด ใส่กล่องเล็ก "Sel, pos" ข้าง leaf ที่มี ≥ 3 partition)
- Table IV: ไม่บังคับ (ต้นทุน search-only `k_Q T_lookup + T_Foc + T_Eval` อยู่ในข้อ 3.6b ของเพื่อน)
