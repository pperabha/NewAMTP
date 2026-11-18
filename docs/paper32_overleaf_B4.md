# B4: วิธีแก้ AMTP (32) ใน Overleaf ทีละจุด (ส่วนที่ไม่ต้องรอผลการทดลอง)

คน B (PrimRoseEverD) · 19 พ.ย. 2026 · เทียบกับ **AMTP (32).pdf** (19 หน้า) · เลขหน้า = หน้าของ PDF นี้
ขอบเขตตาม `docs/PAPER32_START_HERE.md` ข้อ B4 (11 จุด + 9a) และการตัดสินใจ #42–#54
LaTeX ของตัวเร่ง / construction มาจาก `docs/paper_latex_2026-11-17_somo.tex` (อ้างเป็น "somo x.y")

## วิธีใช้ (เหมือน `docs/paper_paste_guide_2026-11-17_somo.md`)

1. ใน Overleaf เปิด `.tex` ของ paper กด **Ctrl+F** (Mac: Cmd+F)
2. วางข้อความใน **ค้นหา** (คำธรรมดา ไม่มีสูตร คัดจาก (32) ตรงตัว) ถ้าไม่เจอให้ค้นครึ่งแรก (ใน .tex อาจขึ้นบรรทัดใหม่กลางประโยค)
3. ทำตามคำสั่ง **ลบตั้งแต่ … ถึง …** แล้ว **วางแทน**, หรือ **วางต่อท้าย** / **วางก่อน**
4. Recompile แล้วเทียบตำแหน่งกับ PDF
5. ทำตามลำดับในไฟล์นี้ (เรียงตามหน้า) · ชื่อ macro (`\mathsf`, `\hat`) อาจต้องปรับตาม .tex
6. **ห้ามวาง** somo 1.1 (AAD มี policy) และ 1.2 (g_d ใน U_d) เพราะโค้ดแก้ให้ตรง (32) แล้ว (#48 A, #49 A);
   somo 1.4 เป็น comment อย่างเดียว; somo 3.4 / 3.6 / 3.6b / 3.7 เป็นของรอบ (31) ไม่วางตรงๆ (ข้อ E1–E3 ด้านล่างเขียนใหม่ให้รอบนี้)

ป้าย: **[B4-n]** = จุดที่ n ในตาราง B4 ของ START_HERE · **[somo x.y]** = บล็อกใน `_somo.tex` · **[#nn]** = issue ที่ตัดสินแล้ว

## สรุปจุดที่แก้ (ตรวจครบหลังแก้)

| หัวข้อ | ข้อในไฟล์นี้ |
|---|---|
| [B4-1] σ_root = ECDSA ที่ contract ตรวจ (6 ตำแหน่ง) | P5-2, P5-3, P8-4, P12-2, P15-1, P16-1, P16-2, P17-1 |
| [B4-2] LaTeX ตัวเร่ง + construction (somo 1.3, 1.5–1.13, 2.1–2.8, 3.1–3.3, 5.x) | เกือบทุกหน้า |
| [B4-3] dataset arXiv · [B4-4] ช่วง N · [B4-5] Exp 4 | E2, E3 |
| [B4-6] network ที่วัด · [B4-7] นิยาม end-to-end · [B4-8] setup · [B4-11] B = 64, RAKE | E1 |
| [B4-9] Exp 2 tamper, Fig. ??, "Enter Caption" | P4-1, P5-1, P6-1, E3 |
| [B4-9a] σ_d = σ_op | P6-2 |
| [B4-10] ρ_w แทน σ_w | G1 (ทำทั้งไฟล์ก่อน) |
| ABS = MPR บน SS512 (#54) + ตาราง ABS | E1, E4 |

---

## G1. ทำก่อนทุกข้อ: เปลี่ยนสัญลักษณ์ PAPC จาก σ เป็น ρ ทั้งไฟล์ [B4-10]

Table II (หน้า 4) เขียน `ρ_w` แต่สมการ (19), (20), (42), (49), (68) และ proof ของ Theorem 1 เขียน `σ_w` / `σ_h` / `σ̂_h`
ซึ่งชนกับ σ ของลายเซ็น (σ_d, σ_op, σ_root) และโค้ดใช้ `rho()`

ใน Overleaf ใช้ **Find/Replace** (ไม่ใช่ Replace All ทันที ให้กด Replace ทีละจุดและดูว่าเป็น PAPC):
- ค้น `\sigma_w` → แทนด้วย `\rho_w` (สมการ 19, 20, 42 และข้อความรอบๆ)
- ค้น `\sigma_h` → แทนด้วย `\rho_h` (สมการ 49 และ proof Theorem 1)
- ค้น `\hat{\sigma}` หรือ `\widehat{\sigma}` (ตาม macro ใน .tex) → แทนด้วย `\hat{\rho}` / `\widehat{\rho}` (สมการ 68 และ Theorem 1 (i))
- **ห้ามแตะ** `\sigma_d`, `\sigma_{op}`, `\sigma^{root}` (ลายเซ็น)

หลายสมการในนี้จะถูกแทนทั้งบล็อกอยู่แล้วในข้อถัดไป (P7-3, P10-1, P11-2) แต่ทำ G1 ก่อนจะไม่มีตัวหลุด

---

## หน้า 1–2: Abstract และ Introduction [somo 5.1, 5.2]

### P1-1. Abstract: ASPA
ค้นหา: `Proof Assembly (ASPA) shares Merkle paths across records`
→ ลบตั้งแต่ `Authenticated Selective Proof Assembly (ASPA) shares` ถึง `from the final Boolean result.` แล้ววาง

```latex
Authenticated Selective Proof Assembly (ASPA) sends, for a conjunction, only the posting components
that lie in partitions where a match is possible, proves that no other component was withheld, and
shares Merkle paths across the returned records and their partitions.
```

ถ้าต้องการ (ไม่บังคับ): ใน Abstract หลัง `insertion, deletion, split, and merge operations` เติม `applied in batches`

### P1-2. Introduction: ความท้าทายข้อที่สอง
ค้นหา: `the server must authenticate the complete posting state of every`
→ ลบประโยคตั้งแต่ `For a Boolean multi-keyword query, the server must` ถึง `requested AND/OR expression.` แล้ววาง

```latex
For a Boolean multi-keyword query, the server must authenticate every posting that can affect the
result, or prove that the remaining postings cannot, and return exactly the records determined by the
requested AND/OR expression.
```

### P2-1. Introduction: ย่อหน้า overview
ค้นหา: `every required component posting or its absence`
→ แทน `authenticate every required component posting or its absence` ด้วย
`authenticate every component posting state that can affect the result, or its absence`

ค้นหา: `Merkle paths across all records and partitions referenced by the`
→ ลบตั้งแต่ `Authenticated Selective Proof Assembly (ASPA) shares Merkle paths across all` ถึง `the resulting Boolean set.` แล้ววาง

```latex
Authenticated Selective Proof Assembly (ASPA) limits the proof to what the result depends on: for a
conjunction, the keys with the fewest partitions are sent in full and bound the partitions in which a
match can lie; every other key sends only its components in those partitions together with a proof
that it has no further component there. Partition proofs and ciphertext retrieval are restricted to
the resulting Boolean set.
```

### P2-2. Contribution ข้อ 3
ค้นหา: `ASPA shares authentication paths`
→ ลบทั้ง bullet `\item \textbf{Verifiable Boolean Multi-Keyword Search:}` ถึง `of empty Boolean results.` แล้ววาง

```latex
\item \textbf{Verifiable Boolean Multi-Keyword Search:} We develop PAPCs to authenticate complete
per-keyword posting states and support exact verification of conjunctive, disjunctive, and nested
AND/OR results without keyword-combination indexes. ASPA prunes a conjunction to the partitions in
which a match can lie, with a proof that no posting component was withheld, and opens partition proofs
only for the returned records, while still detecting omission, addition, duplication, substitution,
and ciphertext tampering, including empty Boolean results.
```

ไม่บังคับ: contribution ข้อ 2 หลัง `insertion, deletion, split, and merge procedures` เติม `, applied in batches of operations per epoch,`

### P2-3. Related Work II-A (แนะนำ) [somo 5.3]
ค้นหา: `These approaches advance verifiable retrieval and dynamic`
→ **วางก่อน** ย่อหน้านั้น (ต้องเพิ่ม bib entry `cash2013oxt` = Cash et al., "Highly-Scalable Searchable Symmetric Encryption with Support for Boolean Queries", CRYPTO 2013; ตรวจรายละเอียดก่อนใช้)

```latex
Conjunctive searchable encryption commonly starts from the least frequent keyword and filters its
postings with the remaining terms~\cite{cash2013oxt}. AMTP applies the same selectivity principle at
partition granularity and makes the pruned answer verifiable: the user checks that no posting component
inside the candidate partitions was withheld.
```

---

## หน้า 4: System Model และ Table II [somo 1.12, 1.13, 5.4]

### P4-1. Fig. ?? ตัวแรก [B4-9]
ค้นหา: `As illustrated in Fig.`
→ ใน figure ของ "AMTP System model" (Fig. 1) ให้มี `\label{fig:system}` (ถ้ายังไม่มี) แล้วแก้ประโยคเป็น
`As illustrated in Fig.~\ref{fig:system}, AMTP involves five entities.`
(ต้อง `\label` **หลัง** `\caption` ในบล็อก figure ไม่งั้นได้ ?? ต่อ)

### P4-2. DO bullet
ค้นหา: `metadata, and signs insertion or deletion requests`
→ แทน `and signs insertion or deletion requests.` ด้วย

```latex
and signs insertion or deletion requests; an insertion may carry a placement hint for the CS outside
the signed request.
```

### P4-3. CS bullet [somo 1.12, 5.4]
ค้นหา: `It prepares updates, split/merge operations, and posting`
→ แทน `It prepares updates, split/merge operations,` ด้วย
`It prepares updates in batches of at most $b$ operations per epoch, split/merge operations,`

ค้นหา: `using ASPA to share Merkle`
→ ลบตั้งแต่ `It returns ciphertexts and authenticated posting` ถึง `paths.` (จบ bullet CS) แล้ววาง

```latex
It returns ciphertexts and authenticated posting, membership, or non-membership evidence, using ASPA to
share Merkle paths across the opened records and partitions and, for conjunctions, to omit the posting
components that lie outside the partitions where a match can lie, together with evidence that no
component inside them was withheld.
```

### P4-4. DU bullet [somo 5.4]
ค้นหา: `It verifies every component posting`
→ แทน `It verifies every component posting state or authenticated absence` ด้วย
`It verifies every component posting state needed for the query or authenticated absence`

### P4-5. Table II: แถวใหม่และแก้คำอธิบาย [somo 1.13, 5.4]
ค้นหา: `Partitions containing postings for`
→ ไปท้ายแถวนั้น (หลัง `\\`) **วางต่อท้าย**

```latex
$\mathsf{Aux}_i(h_w)$ & Partition set and component positions kept in the Search Tree leaf \\
$\mathsf{next}(h_w)$ & Next indexed key after $h_w$ in the IMT chain \\
```

ค้นหา: `Union of component postings requiring authentica`
→ แทนคำอธิบายด้วย `Union of the component postings sent`
แล้ว**วางต่อท้าย**แถวนั้น

```latex
$\mathcal{B}$, $b$ & Batch of operations of one epoch and its maximum size \\
$H_{full}$, $F_Q$ & Query keys sent in full and focus set of $\mathcal{B}_Q$ \\
$S_{res}$, $\mathsf{Ver}_Q$ & Partitions of returned files and version list of the other covered partitions \\
```

หมายเหตุ: ไม่เพิ่มแถว `g_d` (U_d ไม่มี g_d แล้ว #49); placement hint อธิบายในข้อความ P4-2 และ leakage P13-1
ถ้าใน .tex Table II ใช้ `\mathcal{B}_Q` สำหรับ query expression ให้ใช้ตัวอื่นกับ batch ไม่ซ้ำ (เช่น `\mathcal{U}^{b}`) และเปลี่ยนทุกที่ใน P6-3, P8-1

---

## หน้า 5: ย่อหน้าหลัง entities, Threat Model, Phase 1 Step 1

### P5-1. Fig. ?? ตัวที่สอง [B4-9]
ค้นหา: `summarizes the overall workflow`
→ Fig. 2 ให้ `\label{fig:workflow}` แล้วแก้เป็น `Fig.~\ref{fig:workflow} summarizes the overall workflow.`
(caption ของ Fig. 2 แก้ใน P6-1)

### P5-2. ย่อหน้าหลัง entities [somo 5.4]
ค้นหา: `The Search Tree provides keyword lookup, while PAPCs`
→ ลบประโยคตั้งแต่ `The Search Tree provides` ถึง `within one finalized domain snapshot.` แล้ววาง

```latex
The Search Tree provides keyword lookup, while PAPCs and the Merkle hierarchy authenticate the postings
a query depends on and the locations of the returned ciphertexts within one finalized domain snapshot.
```

### P5-3. Threat Model: ความสามารถของ CS [somo 5.5a]
ค้นหา: `It may fabricate, sub`
→ ลบประโยคตั้งแต่ `It may fabricate,` ถึง `combine different epochs.` แล้ววาง

```latex
It may fabricate, substitute, omit, or duplicate results, select incorrect partitions, withhold posting
components of a pruned query key, misreport partition versions, report false empty results, replay stale
evidence, or combine different epochs.
```

### P5-4. Threat Model: DO ที่ validate [somo 5.5b]
ค้นหา: `The validating DO maintains`
→ ลบประโยค `The validating DO maintains complete domain-wide metadata and independently checks ...`
จนจบประโยคนั้น แล้ววาง

```latex
The validating DO maintains complete domain-wide metadata and independently checks the operations of a
batch, affected-state coverage, entry conservation, versions, posting repair, the ordering of the IMT
chain and of the posting-component trees, and preservation of unaffected state. Absence proofs for a key
or for a posting component are meaningful only relative to these validated orderings.
```

### P5-5. Threat Model: assumptions [B4-1]
ค้นหา: `ABS unforgeability, collusion-resistant`
→ แทน `ABS unforgeability,` ด้วย
`ABS unforgeability, EUF-CMA security of the root-update signature,`

### P5-6. Threat Model: leakage [somo 5.5d]
ค้นหา: `Deterministic keyword equality, posting and result sizes,`
→ แทน `posting and result sizes,` ด้วย `posting and result sizes, placement hints,`

### P5-7. Phase 1 Step 1 [B4-1]
ค้นหา: `DOs receive domain-authorized signing credentials`
→ แทน `Eligible DOs receive domain-authorized signing credentials $SK^{abs}$,` (ตาม macro) ด้วย

```latex
Eligible DOs receive domain-authorized signing credentials $SK^{abs}$ for requests and a root-update
signing key $SK^{root}$,
```

ค้นหา: `The DA registers`
→ แทน `The DA registers $PK_i$ and the applicable ABS authorization policies with the Root Anchor (RA).` ด้วย

```latex
The DA registers $PK_i$ and the root-update verification keys of the authorized DOs with the Root
Anchor (RA).
```

---

## หน้า 6: Fig. 2, Phase 1 Step 5, Phase 2 intro + Step 1

### P6-1. caption ของ Fig. 2 [B4-9]
ค้นหา: `Enter Caption`
→ แทนด้วย (และเพิ่ม `\label{fig:workflow}` หลัง `\caption{...}` ถ้ายังไม่มี)

```latex
AMTP workflow: (1) epoch-bound trapdoor generation, (2) Cuckoo filter and B$^{+}$ Search Tree lookup
of the protected keys, (3) Boolean evaluation and proof assembly at the CS, and the per-domain Merkle
hierarchy with occupancy-driven split and merge.
```

### P6-2. σ_d = σ_op [B4-9a]
ค้นหา: `The admission procedure verifies`
→ **วางก่อน** ประโยคนี้ (ต่อจากสมการ (9))

```latex
Since $U_d$ in (8) coincides with $U_{ins}$ in (10), the upload signature $\sigma_d$ is the
$\sigma_{op}$ of that insertion request; an upload is signed once.
```

### P6-3. Phase 2 intro: epoch = batch [#50, somo 1.3]
ค้นหา: `Each logical update is prepared against`
→ แทนประโยค `Each logical update is prepared against a finalized predecessor, independently validated by an authorized DO, and finalized by the RA.` ด้วย

```latex
Each update is prepared against a finalized predecessor, independently validated by an authorized DO,
and finalized by the RA. The CS groups up to $b$ admitted requests into one batch
$\mathcal{B} = (U_1,\dots,U_m)$, $1 \le m \le b$, prepared against the same finalized predecessor.
A batch and the restructuring it causes form one epoch transition; $b = 1$ gives one operation per epoch.
Request nonces must be distinct inside a batch and unused in earlier epochs.
```

---

## หน้า 7: Phase 2 Step 1–4

### P7-1. version ต่อ batch [#50, somo 1.3]
ค้นหา: `partition increments its version once for the logical update`
→ ลบตั้งแต่ `A modified existing partition increments` ถึง `starts at zero.` แล้ววาง

```latex
A modified existing partition increments its version once per batch, however many operations of
the batch touch it; a newly created partition starts at zero.
```

### P7-2. Search Tree leaf (part leaf) [somo 1.13]
ค้นหา: `the commitments below authenticate`
→ ประโยคจบที่ `the returned posting state.` **วางต่อท้าย** (ก่อน `Step 3`)

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
unchanged, and every response is the same with or without it.
```

(ตัดประโยคตัวเลข "6% memory / 1.5% build" ของ somo ออก เพราะเป็นตัวเลขรอบ (31); ถ้าจะใส่ต้องวัดใหม่)

### P7-3. γ เรียงตาม PID [somo 1.6]
ค้นหา: `Partition components are ordered by PID`
→ ประโยคนี้ **วางต่อท้าย**

```latex
The leaves of the $R^{post}_w$ tree are the $\gamma_{w,j}$ in strictly increasing $PID$ order; the
validating DO checks this order whenever a component is added or removed.
```

### P7-4. IMT แบบ indexed [#51, somo 1.5]
ค้นหา: `The Index Merkle Tree (IMT) contains`
→ ลบตั้งแต่ `The Index Merkle Tree (IMT) contains` ถึงจบสมการ (20) **และ**ประโยคถัดไป
`Non-membership proofs establish consecutive bracketing keys and their positions, including the sentinel-only empty index.`
(เก็บประโยค `Merkle commitments authenticate leaf positions ...` และ `An optional Cuckoo filter ...` ไว้) แล้ววาง

```latex
The Index Merkle Tree (IMT) is an indexed Merkle tree. Each indexed key has one leaf
\begin{equation}
I_w = H\big(h_w \,\|\, \rho_w \,\|\, \mathsf{next}(h_w)\big),
\end{equation}
where $\mathsf{next}(h_w)$ is the smallest indexed key above $h_w$, or the upper sentinel $h_{hi}$
for the largest key. A lower sentinel leaf $I_{lo} = H(h_{lo} \,\|\, 0^{\lambda} \,\|\, \mathsf{next}(h_{lo}))$
starts the chain, and
\begin{equation}
R^{idx}_{D_i} = \mathsf{MerkleRoot}\big(I_{lo}, I_{\pi(1)}, \dots, I_{\pi(q)}\big),
\end{equation}
where $\pi$ is the position assignment. Leaves keep their position: a new key is appended or reuses a
freed position, and a removed key leaves the fixed value $I_{\bot}$ at its position. An update therefore
changes only the leaf of the key and the leaf of its predecessor. A key $h$ is not indexed exactly when
one authenticated leaf $(h', \rho', \mathsf{next}(h'))$ satisfies
\begin{equation}
h' < h < \mathsf{next}(h').
\end{equation}
The validating DO checks that every insertion and removal keeps the next pointers in one strictly
increasing chain from $h_{lo}$ to $h_{hi}$ that contains exactly the indexed keys.
```

หลังวาง: สมการถูกเลขใหม่ทั้งไฟล์ ตรวจว่า `\eqref` ที่อ้าง (20) ยังชี้ถูก

### P7-5. Step 4 [#50, somo 1.3]
ค้นหา: `After applying the logical operation once`
→ แทน `After applying the logical operation once,` ด้วย `After applying the operations of the batch,`

---

## หน้า 8: Phase 2 Step 5, Phase 3

### P8-1. สมการ (27) AUDC และ (28) [#50, somo 1.3]
ค้นหา: `structs the Authenticated Update-Delta Commitment`
→ แทนสมการ (27) ด้วย

```latex
\begin{equation}
\Delta_i^{(e_i')} = H\big(i \,\|\, e_i' \,\|\, H(\mathcal{B}) \,\|\, H(\mathsf{Aff}_i) \,\|\,
R_{D_i}^{(e_i)} \,\|\, R_{D_i}^{(e_i')}\big), \qquad
H(\mathcal{B}) = H\big(H(U_1) \,\|\, \dots \,\|\, H(U_m)\big).
\end{equation}
```

→ ในสมการ (28) (หลัง `and submits`) แทน `U_{op}, \sigma_{op},` ด้วย `(U_k,\sigma_k)_{k=1}^{m},` ให้ได้

```latex
\mathcal{U}_i = \langle i, e_i, e_i', R_{D_i}^{(e_i)}, R_{D_i}^{(e_i')},
(U_k,\sigma_k)_{k=1}^{m}, \mathsf{Aff}_i, \Delta_i^{(e_i')}, \pi^{upd}_i \rangle .
```

### P8-2. IMT key ใหม่ [#51, somo 1.5]
ค้นหา: `New IMT keys require predecessor non`
→ แทนประโยคด้วย `A new IMT key requires the opened leaf of its predecessor, which is relinked to it.`

### P8-3. DO ตรวจ batch
ค้นหา: `The authorized DO checks the signed operation`
→ แทน `checks the signed operation,` ด้วย `checks the signed operations of the batch,`

### P8-4. สมการ (29) σ_root = ECDSA [B4-1]
ค้นหา: `then signs only a valid transition`
→ ในสมการ (29) แทน `\mathsf{ABS.Sign}\big(SK^{abs},` ด้วย `\mathsf{Sign}\big(SK^{root},` แล้ว**วางต่อท้าย**หลังสมการ

```latex
Here $\mathsf{Sign}$ is ECDSA over secp256k1, which the RA contract verifies on-chain; the
attribute-based signatures $\sigma_d$ and $\sigma_{op}$ authorize requests and are verified off-chain
by the CS and the validating DO.
```

ประโยคถัดไป `The RA verifies the signature under the domain's root-update policy` **ไม่ต้องแก้**

### P8-5. ท้าย Step 5 [#50]
ค้นหา: `each logical operation and any induced`
→ แทน `Thus, each logical operation and any induced restructuring form one authenticated epoch transition.` ด้วย
`Thus, each batch of operations and any induced restructuring form one authenticated epoch transition.`

### P8-6. Phase 3 intro [#50]
ค้นหา: `Following an insertion or deletion`
→ แทน `Following an insertion or deletion in Phase 2,` ด้วย `Following the operations of a batch in Phase 2,`

### P8-7. Phase 3 Step 1 [#50, somo 1.3]
ค้นหา: `For a single insertion into a previously upper-bounded`
→ ประโยคนี้และประโยคถัดไปคงไว้ แล้ว**วางต่อท้าย**ย่อหน้า (หลัง `within the same transition.`)

```latex
After a batch, a partition can exceed $\theta_{\max}$ by more than one entry. The CS then splits it
repeatedly until every resulting partition has at most $\theta_{\max}$ live entries. A partition
produced by a merge is not merged again in the same transition.
```

---

## หน้า 10: Phase 4 [somo 1.7, 1.8, 1.9, 1.13]

### P10-1. Step 2: focus set และ evidence สองแบบ [somo 1.7 + 1.13]
ค้นหา: `For every h ∈ HQ, it resolves the Search Tree` (ใน .tex น่าจะเป็น `it resolves the Search Tree and`)
→ ลบตั้งแต่ `For every $h \in \mathcal{H}_Q$, it resolves the Search Tree and constructs` ถึงจบประโยค
`partial component proofs alone do not establish posting completeness.` (รวมสมการ (49)) แล้ววาง

```latex
For every $h \in H_Q$, the CS resolves the Search Tree and obtains $\mathsf{Sel}_i(h)$ from
$\mathsf{Aux}_i(h)$ in \eqref{eq:part-leaf} when it is stored, and from $L_h$ otherwise; for
focus evidence it takes the components of $\mathsf{Seg}_h$ through $\mathsf{pos}_h$ without
scanning $L_h$.

\textbf{Focus set.} Let $H_{full} \subseteq H_Q$ be a set of keys whose complete posting state or
absence is sent. Define
\begin{equation}
\mathsf{Foc}(h) =
\begin{cases}
\mathsf{Sel}_i(h), & h \in H_{full} \ (\emptyset \text{ if } h \text{ is absent}),\\
\top, & \text{otherwise},
\end{cases}
\end{equation}
\begin{equation}
\mathsf{Foc}(X \wedge Y) = \bigcap_{Z \in \{X,Y\},\ \mathsf{Foc}(Z) \ne \top} \mathsf{Foc}(Z), \qquad
\mathsf{Foc}(X \vee Y) = \mathsf{Foc}(X) \cup \mathsf{Foc}(Y),
\end{equation}
where a conjunction with no bounded child and a disjunction with an unbounded child evaluate to $\top$.
The CS chooses $H_{full}$, containing every absent key, such that
\begin{equation}
F_Q = \mathsf{Foc}(B_Q) \ne \top .
\end{equation}
A document matching $B_Q$ lies in a partition of every key it satisfies; hence every element of $M_Q$
lies in a partition of $F_Q$. For a conjunction, sending the key with the fewest partitions in full
suffices; the CS adds further keys to $H_{full}$ while this lowers the proof size. With
$H_{full} = H_Q$ the response is the unpruned one.

\textbf{Evidence.} For every $h \in H_Q$ the CS constructs
\begin{equation}
E_h =
\begin{cases}
\langle \mathsf{present}, \mathsf{full}, L_h, \pi^{idx}_h \rangle, & h \in H_{full},\ h \text{ indexed},\\
\langle \mathsf{present}, \mathsf{focus}, n_h, R^{post}_h, \mathsf{Seg}_h, \mathsf{Nb}_h,
        \pi^{post}_h, \pi^{idx}_h \rangle, & h \notin H_{full},\\
\langle \mathsf{absent}, \pi^{nm}_h \rangle, & \text{otherwise},
\end{cases}
\end{equation}
with $n_h = |\mathsf{Sel}_i(h)|$ and
\begin{align}
\mathsf{Seg}_h &= \big[(pos_j, PID_{i,j}, L_{h,j}) : PID_{i,j} \in \mathsf{Sel}_i(h) \cap F_Q \big],\\
\mathsf{Nb}_h &= \big[(pos_k, PID_{i,k}, v_{i,k}, H(\mathsf{Enc}(L_{h,k})))\big],
\end{align}
where $\mathsf{Nb}_h$ holds, for every $t \in F_Q \setminus \mathsf{Sel}_i(h)$, the $\gamma$ leaves at
adjacent positions of the $R^{post}_h$ tree whose identifiers bracket $t$ (a single leaf at the first or
last position when $t$ lies outside the range). $\pi^{post}_h$ is one multiproof opening all leaves of
$\mathsf{Seg}_h$ and $\mathsf{Nb}_h$ in that tree, and $\pi^{idx}_h$ authenticates
$I_h = H(h \,\|\, \rho_h \,\|\, \mathsf{next}(h))$. Focus evidence does not reveal or authenticate the
components outside $F_Q$; it authenticates that the listed components are all the components of $h$
inside $F_Q$.
```

→ แล้วแทนสมการ (50) (`The corresponding component set is` ... `M_h = \{...\}`) ด้วย

```latex
The component set used for evaluation is
\begin{equation}
M_h =
\begin{cases}
\{(cid, PID_{i,j}, l) : (cid,l) \in L_{h,j}\}, & h \in H_{full},\\
\{(cid, PID_{i,j}, l) : (cid,l) \in L_{h,j},\ PID_{i,j} \in F_Q\}, & h \notin H_{full},
\end{cases}
\end{equation}
```

(ประโยค `with M_h = ∅ only for authenticated absence. The CS evaluates` และสมการ (51) คงไว้)
สัญลักษณ์: (32) ใช้ `\mathcal{B}_Q`, `\mathcal{H}_Q` ให้เปลี่ยน `B_Q`, `H_Q` ในบล็อกให้ตรง macro ของ .tex

### P10-2. Step 3: partition proof เฉพาะไฟล์ที่ส่งกลับ [somo 1.8]
ค้นหา: `Step 3: Selective Proof Assembly`
→ ลบตั้งแต่ประโยค `ASPA authenticates all component postings required to verify` ถึงจบสมการ (57) + `against $R^{part}_{D_i}$.`
(คงย่อหน้า `Finally, the CS retrieves ciphertexts only for` ไว้) แล้ววาง

```latex
ASPA authenticates the component postings sent for (51). Let
$M_{cov} = \bigcup_{h \in H_Q} M_h$ and $S_{cov} = \{PID : (cid,PID,l) \in M_{cov}\}$, and let
\begin{equation}
S_{res} = \{PID : (cid,PID,l) \in M_Q\}
\end{equation}
be the partitions of the returned files. For every $PID_{i,j} \in S_{res}$ the CS supplies
$B_{i,j} = \langle PID_{i,j}, v_{i,j}, R_{P_{i,j}} \rangle$ and one positional multiproof
\begin{equation}
Q_{Q,j} = \{ l : (cid, PID_{i,j}, l) \in M_Q \}, \qquad
\Pi^{part}_{Q,j} = \mathsf{MultiProof}(P_{i,j}, Q_{Q,j}).
\end{equation}
For every other covered partition it sends only the version,
\begin{equation}
\mathsf{Ver}_Q = \big[(PID_{i,j}, v_{i,j}) : PID_{i,j} \in S_{cov} \setminus S_{res}\big].
\end{equation}
These versions need no separate proof: $v_{i,j}$ is an input of $\gamma_{h,j}$, so a wrong version gives a
PAPC that is not in the IMT. With $J_{res}$ the positions of the partition states of $S_{res}$ in
$T^{part}_i$,
\begin{equation}
\Pi^{dom}_Q = \mathsf{MultiProof}(T^{part}_i, J_{res}),
\end{equation}
which authenticates $A_{i,j} = H(PID_{i,j} \,\|\, v_{i,j} \,\|\, R_{P_{i,j}})$ against $R^{part}_{D_i}$.
```

### P10-3. Step 4: (59) และท้าย Step 4 [somo 1.9]
ค้นหา: `Step 4: Snapshot-Bound Response`
→ แทนสมการ (59) ด้วย

```latex
\Pi_Q = \big\langle [E_h]_{h \in H_Q},\ [(B_{i,j}, \Pi^{part}_{Q,j})]_{PID_{i,j} \in S_{res}},\
\mathsf{Ver}_Q,\ \Pi^{dom}_Q \big\rangle
```

→ แทน `and partition evidence remains required whenever $M_{cov} \neq \emptyset$.` ด้วย
`and the version list remains required whenever $M_{cov} \neq \emptyset$; if $M_Q = \emptyset$, no partition descriptor is sent.`

### P10-4. Locality (61) [somo 1.9]
ค้นหา: `Posting resolution depends on`
→ แทนสมการ (61) ด้วย

```latex
p_Q = \sum_{h \in H_Q} |M_h|, \quad r_Q = |M_Q|, \quad s_Q = |S_{cov}|, \quad
s_Q^{res} = |S_{res}|, \quad f_Q = |F_Q|, \quad b_Q = |B_Q| .
```

→ ลบตั้งแต่ `Posting resolution depends on` ถึง `and partition-proof coverage on $s_Q$.` แล้ววาง

```latex
Posting resolution depends on $p_Q$, which counts the postings of the full keys and the postings of the
pruned keys inside $F_Q$. Ciphertext retrieval and partition proofs depend on $r_Q$ and $s_Q^{res}$.
For a conjunction, $p_Q$ is bounded by the posting state of its most selective key plus the components
of the other keys inside $F_Q$. For a disjunction and for a single keyword no key can be pruned, and
$p_Q$ is the sum of the complete posting states.
```

→ ลบประโยค `ASPA shares authentication paths over $M_{cov}$, whose coverage may exceed the final Boolean result.`

---

## หน้า 11: Algorithm 2 และ Phase 5 [somo 1.10, 1.11]

### P11-1. Algorithm 2 [somo 1.10]
ค้นหา: `Retrieve complete`
→ ลบบรรทัด 3–12 ของ Algorithm 2 (ตั้งแต่ `\For{each $h \in \mathcal{H}_Q$}` ถึง `Derive $S_{cov}$ and construct partition/domain multiproofs`) แล้ววาง

```latex
\State Resolve $\mathsf{Sel}_i(h)$ for every $h \in H_Q$; choose $H_{full}$ and compute $F_Q$
\For{each $h \in H_Q$}
  \If{$h$ is not indexed}
    \State Construct non-membership evidence; $M_h \gets \emptyset$
  \ElsIf{$h \in H_{full}$}
    \State Retrieve complete $L_h$; construct full $E_h$ and $M_h$
  \Else
    \State Construct focus $E_h$ from the components in $F_Q$ and the neighbour leaves; derive $M_h$
  \EndIf
\EndFor
\State $M_Q \gets \mathsf{Eval}(B_Q, \{M_h\}_{h \in H_Q})$
\State Derive $S_{cov}$, $S_{res}$ and $\mathsf{Ver}_Q$
\State Construct partition multiproofs for $S_{res}$ and the domain multiproof
```

### P11-2. Phase 5 Step 1: absent key [#51, somo 1.11]
ค้นหา: `including the ordering and positional adjacency`
→ ลบตั้งแต่ `For an absent key, it verifies` ถึง `Only a valid proof permits assigning $M_h = \emptyset$.` แล้ววาง

```latex
For an absent key, the evidence opens one IMT leaf $(h', \rho', \mathsf{next}(h'))$. The DU verifies it
against $R^{idx}_{D_i}$ and requires $h' < h < \mathsf{next}(h')$.
Only a valid proof permits assigning $M_h = \emptyset$.
```

### P11-3. Phase 5 Step 2: PAPC, focus key, version [somo 1.11]
ค้นหา: `For each present key, the DU parses the complete posting state`
→ แทน `For each present key,` ด้วย `For each key sent in full,`

ค้นหา: `The response must supply exactly one partition descriptor`
→ ลบประโยคนี้ (ถึง `for each covered partition.`) แล้ววาง

```latex
The version of each partition used in a $\gamma$ is taken from its descriptor $B_{i,j}$ if
$PID_{i,j} \in S_{res}$ and from $\mathsf{Ver}_Q$ otherwise; $\mathsf{Ver}_Q$ must be in canonical order
and must not repeat a described partition.
```

→ สมการ (68) หลัง G1 เป็น `\hat{\rho}_h = H(h \| |\mathsf{Sel}_i(h)| \| \hat{R}^{post}_h)` แล้ว;
แทนประโยค `It verifies $\pi^{idx}_h$ for $\hat{I}_h = H(h \| \hat{\rho}_h)$ against` ด้วย
`It verifies $\pi^{idx}_h$ for $\hat{I}_h = H(h \,\|\, \hat{\rho}_h \,\|\, \mathsf{next}(h))$ against`

ค้นหา: `No separate partial PAPC proof substitutes`
→ ลบตั้งแต่ `Reconstructing the PAPC from the complete posting state` ถึง `substitutes for this reconstruction.` แล้ววาง

```latex
If any evidence is in focus form, the DU computes $F_Q = \mathsf{Foc}(B_Q)$ from the full and absent
evidence only, and rejects if $F_Q = \top$. For a focus key $h$ it computes
\begin{equation}
\hat{\gamma}_{h,j} = H\big(PID_{i,j} \,\|\, v_{i,j} \,\|\, H(\mathsf{Enc}(L_{h,j}))\big)
\ \text{for } \mathsf{Seg}_h, \qquad
\hat{\gamma}_{h,k} = H\big(PID_{i,k} \,\|\, v_{i,k} \,\|\, x_k\big) \ \text{for } \mathsf{Nb}_h,
\end{equation}
where $x_k$ is the supplied inner hash, and verifies
\begin{equation}
\mathsf{MultiVerify}\big(R^{post}_h, n_h, \{(pos, \hat{\gamma})\}, \pi^{post}_h\big) = 1 .
\end{equation}
The opened leaves must be at distinct positions with strictly increasing identifiers. For every
$t \in F_Q$ the DU requires one of: (a) $\mathsf{Seg}_h$ contains $t$; (b) two opened leaves at adjacent
positions $k, k+1$ satisfy $PID_k < t < PID_{k+1}$; (c) the leaf at position $0$ is opened and has
$PID_0 > t$; (d) the leaf at position $n_h - 1$ is opened and has $PID_{n_h-1} < t$.
A partition of $F_Q$ that is opened only as a neighbour is rejected. The DU then computes
\begin{equation}
\hat{\rho}_h = H\big(h \,\|\, n_h \,\|\, R^{post}_h\big)
\end{equation}
and verifies $\pi^{idx}_h$ for $\hat{I}_h = H(h \,\|\, \hat{\rho}_h \,\|\, \mathsf{next}(h))$ against
$R^{idx}_{D_i}$.
For a full key, reconstructing the PAPC authenticates its partition count, identities, versions and
contents. For a focus key, the multiproof and the bracketing rule authenticate that the listed
components are exactly the components of the key inside $F_Q$.
```

### P11-4. Phase 5 Step 3: partitions [somo 1.11]
ค้นหา: `Step 3: Partition and Boolean-Result Verification`
→ ลบตั้งแต่ `For every covered partition, the DU constructs the position-to-identifier map` ถึง
`including those not selected by the final Boolean result.` (สมการ 69–70) แล้ววาง

```latex
The DU first evaluates $\hat{M}_Q = \mathsf{Eval}(B_Q, \{M_h\}_{h \in H_Q})$ and requires descriptors for
exactly $S_{res} = \{PID : (cid,PID,l) \in \hat{M}_Q\}$ and $\mathsf{Ver}_Q$ for exactly
$S_{cov} \setminus S_{res}$. For every described partition it constructs
\begin{equation}
V_{Q,j} = \{(l, cid) : (cid, PID_{i,j}, l) \in \hat{M}_Q\}
\end{equation}
and verifies $\mathsf{MultiVerify}(R_{P_{i,j}}, V_{Q,j}, \Pi^{part}_{Q,j}) = 1$.
This authenticates the location of every returned file. The locations of the other component postings
are bound by their PAPCs; the check that a file appears at one location across all query keys is kept.
```

ค้นหา: `partition evidence is unnecessary`
→ แทน `If $M_{cov} = \emptyset$, partition evidence is unnecessary.` ด้วย `If $\hat{M}_Q = \emptyset$, no partition descriptor is sent.`

ค้นหา: `Nonempty proof coverage must still be verified`
→ แทนประโยคนั้นด้วย `Component evidence and the version list are still verified when the result is empty.`

---

## หน้า 12: Algorithm 3, Verification guarantees, IV-A

### P12-1. Algorithm 3 [somo 1.11]
ค้นหา: `Derive Mcov and require exact descriptor` (ใน .tex: `require exact descriptor`)
→ บรรทัด 11: แทนด้วย `Derive $M_{cov}$; require descriptors for exactly $S_{res}$ and versions for the other covered partitions`
→ **วางก่อน**บรรทัด 13 (`for each present query key`): `\State Compute $F_Q$ if any evidence is in focus form`
→ บรรทัด 14 (`Reconstruct its PAPC and verify IMT membership`): แทนด้วย
`Reconstruct its PAPC (full) or verify its $R^{post}$ multiproof and the bracketing rule (focus), then verify IMT membership`
→ บรรทัด 16 (`for each covered partition`): แทนด้วย `for each partition of $S_{res}$`

### P12-2. Verification guarantees [somo 1.11]
ค้นหา: `Partition proofs authenticate the live`
→ ลบประโยคแรกตั้งแต่ `Partition proofs authenticate the live` ถึง `complete per-keyword mappings.` แล้ววาง

```latex
Partition proofs authenticate the live location of every returned file, while PAPC reconstruction,
focus evidence and IMT proofs authenticate, for every query key, all of its postings in the partitions
where a match can lie.
```

### P12-3. IV-A assumptions [B4-1, #51, somo 2.1]
ค้นหา: `ABS unforgeability under the applicable signing`
→ แทน `ABS unforgeability under the applicable signing policies,` ด้วย
`ABS unforgeability under the applicable signing policies, EUF-CMA security of the root-update signature (ECDSA),`

ค้นหา: `IMT non-membership requires authenticated`
→ ลบประโยค `IMT non-membership requires authenticated consecutive bracketing leaves or boundary sentinels.` แล้ววาง

```latex
IMT non-membership requires one authenticated leaf $(h', \rho', \mathsf{next}(h'))$ with
$h' < h < \mathsf{next}(h')$. Its meaning relies on the indexing invariant of Proposition~1: the next
pointers of the finalized IMT form one strictly increasing chain over exactly the indexed keys, and the
leaves of every $R^{post}$ tree are in strictly increasing $PID$ order.
The Cuckoo filter and the Search Tree, including the auxiliary data $\mathsf{Aux}_i$ in its leaves,
are untrusted lookup structures of the CS; the DU never uses them, and every accept decision rests on
the IMT, PAPC, and Merkle checks of Phase~5.
```

---

## หน้า 13: IV-B leakage, Lemma 1, Theorem 1 [somo 2.2, 2.3, 2.5, 2.6]

### P13-1. Leakage [somo 2.2]
ค้นหา: `observable split/merge relocations` (ท้าย bullet L_upd)
→ แทน `observable split/merge relocations.` ด้วย
`observable split/merge relocations, placement hints, and the batch size and order of operations in an epoch.`

ค้นหา: `component posting associations and sizes`
→ แทน `component posting associations and sizes,` ด้วย

```latex
the number of partitions of every query key, the component postings sent (complete for full keys,
inside the focus set for pruned keys) and their sizes, the identifiers and versions of neighbouring
partitions,
```

ค้นหา: `ponent postings reveal associations beyond the final Boolean` (ประโยค `Complete component postings reveal ...`)
→ แทนประโยคนั้นด้วย

```latex
The component postings sent reveal associations beyond the final Boolean result. AND pruning reduces
what the DU receives; the CS already holds the complete index, so its view is unchanged.
```

### P13-2. Lemma 1 proof [somo 2.3]
ค้นหา: `Canonical encodings and authenticated`
→ **วางก่อน** ประโยคนั้น

```latex
The same argument applies to the next pointer of an IMT leaf and to the leaf count $n_h$ and the leaf
positions of an $R^{post}_h$ tree.
```

### P13-3. Lemma ใหม่ 2 ตัวก่อน Theorem 1 [somo 2.5]
ค้นหา: `Theorem 1 (Exact Authenticated Boolean Results)`
→ **วางก่อน** `\begin{theorem}` ของ Theorem 1 (ถ้า .tex ใช้ environment ชื่ออื่นให้ปรับ)

```latex
\begin{lemma}[Focus containment]
Let $F_Q = \mathsf{Foc}(B_Q)$ be computed from the true partition sets $\mathsf{Sel}_i^{(e_Q)}(h)$ of the
keys in $H_{full}$, with $F_Q \ne \top$. Then every $(cid, PID, l) \in M_Q^{*}$ satisfies $PID \in F_Q$,
and
\begin{equation}
\mathsf{Eval}\big(B_Q, \{M_h^{*}\}\big) = \mathsf{Eval}\big(B_Q, \{\tilde{M}_h\}\big), \qquad
\tilde{M}_h =
\begin{cases}
M_h^{*}, & h \in H_{full},\\
\{(cid,PID,l) \in M_h^{*} : PID \in F_Q\}, & \text{otherwise.}
\end{cases}
\end{equation}
\end{lemma}
\begin{proof}
By induction on $B_Q$. A tuple of a leaf $h \in H_{full}$ lies in a partition of $\mathsf{Sel}_i(h)$.
A tuple in $\mathsf{Eval}(X \wedge Y)$ belongs to both children, hence to the focus of every bounded
child. A tuple in $\mathsf{Eval}(X \vee Y)$ belongs to one child, and the focus is the union. So
$M_Q^{*}$ lies in $F_Q$. Since $\cap$ and $\cup$ commute with restriction to $F_Q$, restricting every
leaf gives $M_Q^{*} \cap F_Q = M_Q^{*}$; restricting only some leaves gives a set between these two
equal sets.
\end{proof}

\begin{lemma}[Focus evidence]
Assume collision resistance of $H$ and the (order) invariant. If the DU accepts focus evidence for key
$h$ under the anchored $R^{idx}_{D_i}$ and a correctly computed $F_Q$, then the reconstructed set equals
$\{(cid,PID,l) \in M_h^{*} : PID \in F_Q\}$.
\end{lemma}
\begin{proof}
The IMT check binds $(h, n_h, R^{post}_h)$ through $\hat{\rho}_h$, so by Lemma~1 the opened leaves are
the committed $\gamma$ at their positions among $n_h$ leaves. Each component of $\mathsf{Seg}_h$ is
therefore the committed component of its partition, and its version is bound by $\gamma$. For
$t \in F_Q$ without a component in $\mathsf{Seg}_h$, the DU saw leaves at adjacent positions with
identifiers below and above $t$, or a boundary leaf on one side of $t$. By (order), no committed leaf
lies between adjacent positions, so $h$ has no component in $t$. An omitted or invented component thus
contradicts the multiproof or the bracketing rule, except with a collision.
\end{proof}
```

Lemma ใหม่จะเป็น Lemma 2 และ 3 (Lemma 1 = Hierarchical Commitment Binding) ตรงกับที่ Theorem 1 อ้าง

### P13-4. Theorem 1 statement [somo 2.6]
ค้นหา: `collision resistance of H, an authentic retained Domain Root,`
→ แทน `an authentic retained Domain Root,` ด้วย
`an authentic retained Domain Root whose state satisfies $\mathsf{Inv}$ (Proposition~1),`

---

## หน้า 13–14: Theorem 1 proof, Theorem 2 [somo 2.6, 2.7]

### P14-1. (i) Component authenticity
ค้นหา: `(i) Component authenticity`
→ ลบ (i) ทั้งข้อ (ตั้งแต่ `(i) Component authenticity.` ถึง `Thus, (88) holds for every $h \in \mathcal{H}_Q$.`) แล้ววาง

```latex
\emph{(i) Component authenticity.} For a full key, acceptance reconstructs $\hat{\rho}_h$ from the
complete posting state and verifies $H(h \,\|\, \hat{\rho}_h \,\|\, \mathsf{next}(h))$ in the IMT; the
versions come from descriptors or from $\mathsf{Ver}_Q$ and are inputs of $\gamma$. Under
$\neg\mathsf{Coll}$, $\hat{M}_h = M_h^{*}$ and the partition set of $h$ is the committed one, so the DU
computes the same $F_Q$ as in Lemma~2. For an absent claim, the opened leaf $(h',\rho',\mathsf{next}(h'))$
with $h' < h < \mathsf{next}(h')$ and the (chain) invariant give $M_h^{*} = \emptyset$. For a focus key,
Lemma~3 gives $\hat{M}_h = \{(cid,PID,l) \in M_h^{*} : PID \in F_Q\}$.
```

### P14-2. (ii) Location authenticity
ค้นหา: `(ii) Location authenticity`
→ ลบ (ii) ทั้งข้อ (ถึง `references its committed live location.`) แล้ววาง

```latex
\emph{(ii) Location authenticity.} For every $(cid,PID,l) \in \hat{M}_Q$, acceptance verifies $(l,cid)$
against the partition root and authenticates $A = H(PID \,\|\, v \,\|\, R_P)$ against $R^{part}_{D_i}$.
Hence every returned file is at its committed live location. Locations of postings that are not
returned are not opened; they are bound by the PAPC and are not needed for $\mathsf{Bad}_Q$.
```

### P14-3. (iii) สมการ (91)
ค้นหา: `(iii) Exact Boolean-result coverage`
→ แทน `By component authenticity and deterministic evaluation of the retained expression,` และสมการ (91) ด้วย

```latex
\emph{(iii) Exact Boolean-result coverage.} By (i) and Lemma~2,
\begin{equation}
\hat{M}_Q = \mathsf{Eval}\big(B_Q, \{\hat{M}_h\}_{h \in H_Q}\big)
          = \mathsf{Eval}\big(B_Q, \{M_h^{*}\}_{h \in H_Q}\big) = M_Q^{*} .
\end{equation}
```

(iv) ไม่แก้ · หลัง `\end{proof}` ของ Theorem 1 **วางต่อท้าย**

```latex
\emph{Remark.} Without pruning ($H_{full} = H_Q$) and with partition proofs for all of $M_{cov}$, the
theorem reduces to the unpruned construction. Both response forms are accepted by the same verifier.
```

### P14-4. Theorem 2 proof [somo 2.7]
ค้นหา: `posting state inconsistent with these subroots likewise implies`
→ ประโยคจบที่ `a collision.` **วางต่อท้าย**

```latex
This includes the versions in $\mathsf{Ver}_Q$, which are inputs of authenticated $\gamma$ values.
```

---

## หน้า 15: Theorem 3, Proposition 1 [B4-1, #50, somo 2.4]

### P15-1. Theorem 3 [B4-1]
ค้นหา: `Theorem 3 (Root-Transition Authorization)`
→ แทน statement + proof ด้วย (หรือแก้ทีละคำ: `ABS unforgeability` → `EUF-CMA security of the root-update signature`,
`\mathsf{Adv}^{UF}_{ABS}(\mathcal{B}_{ABS},\lambda)` → `\mathsf{Adv}^{EUF\text{-}CMA}_{Sig}(\mathcal{B}_{Sig},\lambda)`,
`ABS forgery` → `signature forgery`, `\mathsf{Forge}_{ABS}` → `\mathsf{Forge}_{Sig}`)

```latex
\begin{theorem}[Root-Transition Authorization]
Assume EUF-CMA security of the root-update signature scheme, collision resistance of $H$, and correct
atomic RA execution. For every PPT adversarial CS $\mathcal{A}$, there exist PPT reductions
$\mathcal{B}_{Sig}$ and $\mathcal{B}_H$ such that
\begin{equation}
\Pr[\mathsf{UnauthorizedAnchor}] \le \mathsf{Adv}^{EUF\text{-}CMA}_{Sig}(\mathcal{B}_{Sig},\lambda)
 + \mathsf{Adv}^{CR}_{H}(\mathcal{B}_H,\lambda),
\end{equation}
where $\mathsf{UnauthorizedAnchor}$ denotes RA acceptance of a transition tuple not authorized by an
eligible DO.
\end{theorem}
\begin{proof}
Let $\mathcal{S}$ be the set of transition tuples authorized by honest eligible DOs. Suppose the RA
accepts $(m,\sigma)$ for $m \notin \mathcal{S}$. If $H(m) \notin \{H(s) : s \in \mathcal{S}\}$, then
$\sigma$ is a valid signature under the domain's registered root-update key on an unauthorized digest,
yielding a signature forgery. Otherwise, some $s \in \mathcal{S}$ satisfies $m \ne s$ and $H(m) = H(s)$,
which yields a collision in $H$. Hence
$\mathsf{UnauthorizedAnchor} \subseteq \mathsf{Forge}_{Sig} \cup \mathsf{Coll}_H$, and the bound
follows by the union bound.
\end{proof}
```

ย่อหน้า `Atomic RA execution additionally accepts ...` และ (108) **ไม่แก้**

### P15-2. Proposition 1: invariant เพิ่ม 2 ข้อ [#50, #51, somo 2.4]
ค้นหา: `The invariant further requires unique document locations`
→ ลบประโยคนั้น (ถึง `valid partition identifiers and versions.`) แล้ววาง

```latex
The invariant further requires unique document locations, canonical duplicate-free postings, no
references to tombstones or retired partitions, and valid partition identifiers and versions. It also
requires two orderings: (chain) the next pointers of the IMT link $h_{lo}$ to $h_{hi}$ in strictly
increasing order over exactly the keys $h$ with $M_S(h) \ne \emptyset$; and (order) the leaves of every
$R^{\mathrm{post}}_h$ tree are the $\gamma_{h,j}$ for $PID_{i,j} \in \mathsf{Sel}_S(h)$, in strictly
increasing $PID$ order.
```

### P15-3. Proposition 1 proof: batch + เปลี่ยนชื่อ relocation map ρ → μ [somo 2.4]
- สมการ (112): `\mathsf{Apply}(S, U)` → `\mathsf{Apply}(S, \mathcal{B})`; ข้อความ `let an authorized operation $U$ produce` → `let an authorized batch $\mathcal{B} = (U_1,\dots,U_m)$ produce`
- สมการ (113)–(114): relocation map `\rho(cid, PID, \ell)` ชนกับ PAPC `\rho_h` → เปลี่ยนเป็น `\mu`:

```latex
\mu(cid, PID, \ell) = \big(cid, \mathsf{Loc}_{S'}(cid)\big), \qquad
M_{S'}(h) = \mu\big(M_{S^{+}}(h)\big).
```

- สมการ (116): `\mathsf{ValidTrans}(S, U, S')` → `\mathsf{ValidTrans}(S, \mathcal{B}, S')`
- `keys affected by the logical update` → `keys affected by the operations of the batch`
- ค้นหา `Thus, the logical update preserves` → ประโยคจบที่ `before structural adaptation.` **วางต่อท้าย**

```latex
For a batch, this argument is applied to $U_1,\dots,U_m$ in order. For a key that enters or leaves the
index, validation opens the leaf of its predecessor and checks the relinked pointers, which preserves
(chain). For a component that is added to or removed from a posting state, validation checks its
position against its neighbours in the $\gamma$ list, which preserves (order). Repeated splits of one
partition are validated on the DO's own partition model.
```

---

## หน้า 16–17: Table III, Table IV, ย่อหน้าต้นทุน [B4-1, somo 3.1–3.3]

### P16-1. Table III [somo 3.1, B4-1]
ค้นหา: `AMTP query keys, authenticated postings, results, and`
→ ลบแถว `$k_Q, p_Q, r_Q, s_Q$ & ...` และแถว `$u$ & Protected keys affected by an AMTP update` แล้ววาง

```latex
$k_Q, p_Q, r_Q, s_Q$ & AMTP query keys, postings sent, results, and covered partitions \\
$k_Q^{F}, f_Q, s_Q^{res}, n_h$ & Pruned keys, focus-set partitions, result partitions, and partitions of key $h$ \\
$b, u$ & Operations per epoch and protected keys affected by an AMTP update \\
```

ค้นหา: `Authorized root-transition signature cost`
→ แทนแถว `$T_{ABS}$ & Authorized root-transition signature cost` ด้วย

```latex
$T_{ABS}$ & Attribute-based request signature cost (sign and verify of $\sigma_{op}$) \\
$T_{Sig}$ & Root-transition signature cost (ECDSA, verified by the RA contract) \\
```

### P16-2. Table IV แถว AMTP [somo 3.2, B4-1]
แทน 3 ช่องของแถว AMTP (ช่อง Query Generation คงเดิม):
- Search / Proof Generation:

```latex
$k_Q T_{lookup} + T_{Eval} + \sum_{h \notin H_{full}} T_{MP}(f_Q, n_h)
 + \sum_{j \in S_{res}} T_{MP}(q_j, n_{i,j}) + T_{MP}(s_Q^{res}, m_i)$
```

- Verification:

```latex
$(p_Q + s_Q)\,T_H + \sum_{h \notin H_{full}} T_{MV}(f_Q, n_h) + k_Q\,T_{MV}(1, K_i)
 + \sum_{j \in S_{res}} T_{MV}(q_j, n_{i,j}) + T_{MV}(s_Q^{res}, m_i) + T_{Eval} + r_Q T_H$
```

- Update (ต่อ epoch ของ $b$ operation; ABS ต่อ request, ECDSA ต่อ epoch):

```latex
$T_{part} + u\,T_{post} + T_{IMT} + b\,T_{ABS} + T_{Sig}$
```

($K_i$ = จำนวน leaf ของ IMT, $q_j$ = ตำแหน่งผลลัพธ์ใน partition $j$ — ถ้าจะใส่ ให้เพิ่มใน Table III ด้วย)
หมายเหตุสำหรับ A: somo 3.2 เขียน update เป็น `+ T_ABS` เพราะตอนนั้น σ_root ยังเป็น ABS; รอบนี้ σ_op เป็น ABS ต่อ request และ σ_root เป็น ECDSA ต่อ epoch จึงแยกเป็น `b T_ABS + T_Sig`

### P17-1. ย่อหน้าหลัง Table IV [somo 3.3, B4-1]
ค้นหา: `AMTP avoids pairing-based operations and confines proof`
→ ลบตั้งแต่ `AMTP avoids pairing-based operations` ถึง `the resulting root transition.` แล้ววาง

```latex
AMTP avoids pairing-based operations in search and verification. For a conjunction, AND pruning limits
the postings sent to the complete state of the most selective keys and the components of the other keys
inside the focus set, so search and verification depend on $p_Q$ and $f_Q$ rather than on the total size
of all queried posting lists. Partition proofs are built only for the $s_Q^{res}$ partitions that hold a
returned file. A disjunction or a single keyword cannot be pruned: every posting of every key must be
authenticated, and the cost grows with the sum of the posting lists. Updates are processed per epoch of
$b$ operations and affect only the touched partitions, their posting states, and the corresponding IMT
leaves; each request carries one attribute-based signature, whose pairings dominate the update cost of
small batches, and one ECDSA signature, checked by the RA contract, authorizes the resulting root
transition.
```

(ประโยค `Thus, AMTP trades additional authenticated proof processing ...` คงไว้)

---

## หน้า 17: Evaluation setup และคำอธิบายการทดลอง [B4-3 ถึง B4-9, B4-11]

### E1. Experimental Setup (เขียนใหม่ทั้งย่อหน้า) [B4-6, B4-7, B4-8, B4-11, #46, #54]
ค้นหา: `AMTP is implemented in [lan`
→ ลบทั้งย่อหน้า `1) Experimental Setup:` ตั้งแต่ `AMTP is implemented in` ถึง `after [number] warm-up runs.` แล้ววาง

```latex
AMTP is implemented as a Python~3.12 prototype and evaluated on AWS \texttt{r7i.4xlarge} instances
(Intel Xeon Platinum 8488C, 16 vCPUs, 128\,GiB RAM, Ubuntu Linux), one job at a time per instance,
except Experiment~4, which ran six processes per instance, at most one per physical core.
Cryptographic operations use the \texttt{cryptography} library: SHA-256 for $H$, AES-256-GCM for
document encryption, AES-SIV for $\mathsf{DEnc}$, and HMAC-SHA256 for query authentication. $K_d$ is
protected by the BSW07 CP-ABE scheme, and requests are signed with the single-authority attribute-based
signature of Maji, Prabhakaran and Rosulek under the policy
$\mathsf{domain}{:}D_i \wedge \mathsf{role}{:}\mathsf{owner}$; both use Charm~0.62 on the symmetric
SS512 pairing group, for which the unforgeability proof of that ABS construction, including collusion
resistance, is given in the generic group model. Root transitions are signed with ECDSA over
secp256k1 and verified by the RootAnchor contract. Protocol costs are measured against the same
RootAnchor contract deployed on a local EVM; on-chain anchoring latency, read latency and gas are
measured separately on Ethereum Sepolia and reported apart; there, anchoring one root update takes
11.0\,s (median; about 17 minutes until the block is finalized) and reading the anchored root takes
131\,ms. The Search Tree is a B$^{+}$ tree of order
$B = 64$; keywords are extracted with RAKE, at most $\kappa = 20$ phrases of 1--3 words per document,
and documents longer than $\Theta_{doc}$ are chunked. Unless otherwise stated, each reported value is
averaged over 10 independent runs after 3 warm-up runs; where a setting contains several queries, each
point is the median of these per-query averages and the bars show the interquartile range. End-to-end query latency is query generation
plus server time plus DU verification; it excludes the DU's read of the anchored root, which is
reported separately, and the CP-ABE decryption of returned records.
```

แก้ 19 พ.ย. (PR นี้): ประโยค Exp 4 หกกระบวนการต่อเครื่อง (คน A ขอใน PR #59; แผน 5 เครื่อง × 6 process เริ่มรันแล้ว
`docs/reports/2026-11-19-paper32-aws-ex4-start.md`) และตัวเลข Sepolia จาก `chain/runs/sepolia_bench_20261119_012227.*`
(โค้ดปัจจุบัน ABS SS512 + BSW07, D = 1: anchor median 11.0 s, max 60.4 s, finality ~1,015 s, อ่าน root latest 131 ms /
finalized 149 ms) · gas ต่อ root update ตาม D (87k ที่ D = 1 → 166.5k ที่ D = 32, `chain/runs/gas_domains_20261119_005048.csv`)
เป็นผลของ Exp 5 ไว้เขียนใน B5 ไม่ใส่ใน Setup

ตรวจก่อนส่ง: ค่า `\Theta_{doc}` (ถ้า paper ไม่ได้นิยามสัญลักษณ์นี้ไว้ ให้เขียน "documents longer than the chunk limit are chunked" แทน) และเวอร์ชันของ `cryptography` บนเครื่อง AWS

### E2. ย่อหน้า dataset และพารามิเตอร์ [B4-3, B4-4]
ค้นหา: `Experiments use the Enron email dataset`
→ ลบตั้งแต่ `Experiments use the Enron email dataset` ถึง `preserves the resulting keyword-frequency skew.` แล้ววาง (somo 3.5 ปรับขนาดตามรอบนี้)

```latex
The evaluation uses the arXiv metadata snapshot from Kaggle (Cornell University; latest record dated
2026-10-30; 3{,}233{,}620 papers), organized into four domains by the primary arXiv category: $D_1$ = cs,
$D_2$ = math, $D_3$ = astrophysics, gravitation, high-energy and nuclear physics (astro-ph, gr-qc, hep-*,
nucl-*), and $D_4$ = condensed matter, quantum and other physics (cond-mat, quant-ph, physics, math-ph,
nlin). Papers with abstracts shorter than 30 words and withdrawn papers are skipped. Each domain has
125{,}000 initial documents in chronological order and a disjoint pool of 12{,}500 documents for
insertions (seed 42). Each document is a paper's title and abstract, and its keywords are extracted once
and used as they are by every scheme. A domain of $N$ documents is the first $N$ documents of that
domain, $N \in \{10, 25, 50, 75, 100, 125\} \times 10^{3}$; no synthetic replication is used.
```

ค้นหา: `AMTP uses θmax = [X] and θmin = [Y]` (ใน .tex: `\theta_{max} = [X]`)
→ แทนประโยคถึง `is fixed at [X].` ด้วย

```latex
AMTP uses $\theta_{\max} = 64$ and $\theta_{\min} = 16$ as the split and merge thresholds, fill-first
placement, AND pruning, result-only partition proofs, and partition sets in the Search Tree leaves.
Unless varied by an experiment, a query contains four keywords, a domain holds $N = 10^{5}$ documents,
and the number of domains is fixed at 4.
```

### E3. คำอธิบายการทดลองที่ขึ้นกับขนาด [B4-4, B4-5, B4-9]
ทำเฉพาะตัวเลขและชื่อ (เนื้อหาผลรอ B5):

- **Exp 1** ค้นหา `search scalability by varying the database size` → แทน
  `N \in \{10^4, 5 \times 10^4, 10^5, 5 \times 10^5, 10^6\}` ด้วย
  `the number of documents per domain $N \in \{10, 25, 50, 75, 100, 125\} \times 10^{3}$`
- **Exp 2** ค้นหา `Experiment 2: Selective Proof and Verification` →
  - หัวข้อ: `Experiment 2: Selective Proof, Verification, and Tamper Detection.`
  - แทน `The total database size is fixed at $N = 10^6$,` ด้วย `The domain size is fixed at $N = 10^{5}$,`
  - ท้ายย่อหน้า (หลัง `rather than the complete domain state.`) **วางต่อท้าย**

```latex
We also measure tamper detection: the CS modifies returned ciphertexts, hides matching files, injects
non-matching files, or returns an older valid version, applied to a varying number of returned files,
and we report the detection rate and the DU's verification time for every scheme.
```

- **Exp 3** ค้นหา `ordinary dynamic updates by varying N from` → แทน `$10^4$ to $10^6$` ด้วย
  `$10^4$ to $1.25 \times 10^5$ documents` และ `[1, 10, 100, 1000]` ด้วย `$b \in \{1, 10, 100, 1000\}$`
  แล้ว**วางต่อท้าย**ย่อหน้า

```latex
Update latency is reported as the protocol time (CS preparation, DO validation, and signing) with the
request-signature cost, the posting-state repair time, and the authentication-tree maintenance time as
separate components; anchoring latency and gas on Sepolia are reported apart.
```

- **Exp 4** [B4-5] ค้นหา `Experiment 4: Adaptive Partitioning under Skewed` → ประโยค `Starting from the same initial state, updates are increasingly concentrated on a subset of partitions to trigger split and merge operations.` แทนด้วย

```latex
Starting from 25{,}000 documents (20\% of a domain), 250 batches of 100 insertions are applied, with a
fraction $s \in \{0, 0.25, 0.5, 0.75, 0.95\}$ of each batch concentrated on one hot group, followed by the
deletion of 65\% of the hot group's live documents, so that both splits and merges occur.
```

- **Exp 5** ค้นหา `while the size and selectivity of the queried target domain are held fixed` → แทน `are held fixed` ด้วย `are held fixed (5{,}000 documents)`

### E4. ตารางต้นทุน ABS (ตามที่ A ขอใน #54)
**วางก่อน** `\subsection` หรือหัวข้อผลการทดลองแรก (หรือท้าย Setup) · ตัวเลข: `baselines/results/abs/abs_costs.csv`
(mean 15 รอบหลัง warm-up 3, policy 2 attribute = นโยบายของ AMTP; ตัวเลขด้านล่างเป็นของ container 4 vCPU —
**ถ้า A รัน `bench/abs_bench.py` บน AWS ให้ใช้ตัวเลข AWS แทน**; ใน container นี้ตัวเลขแกว่งระหว่างรอบ
เช่น SS512 verify 8.3 ms ในรอบแรก และ 12.7 ms ในรอบที่ใช้ในตาราง)

```latex
\begin{table}[t]
\centering
\caption{Cost of the request signature $\sigma_{op}$ (two-attribute policy)}
\label{tab:abs}
\begin{tabular}{lrrr}
\hline
Scheme & Sign (ms) & Verify (ms) & Size (B) \\
\hline
ABS, SS512 (used) & 10.6 & 12.7 & 554 \\
ABS, MNT224 & 19.5 & 73.9 & 418 \\
ABS, BN254 & 11.2 & 190.1 & 378 \\
Ed25519 (no attributes) & 0.04 & 0.12 & 64 \\
\hline
\end{tabular}
\end{table}
```

ประโยคประกอบ (วางในย่อหน้าผล update หรือ Setup):

```latex
Each update request is verified twice, by the CS at admission and by the validating DO, so the
attribute-based signature adds one signing and two verifications per request (Table~\ref{tab:abs}).
```

หมายเหตุ: กติกาทีม "กราฟเป็น line chart เท่านั้น" ใช้กับ figure; ตารางนี้เป็น LaTeX table ตามที่ A ขอใน #54

---

## ตรวจหลังแก้ (checklist)

- [ ] ค้น `ABS.Sign` เหลือ 2 ที่ (สมการ 9, 11) — สมการ 29 เป็น `Sign(SK^{root}, …)`
- [ ] ค้น `ABS forgery`, `Adv^{UF}_{ABS}`, `Forge_{ABS}` ไม่เหลือ
- [ ] ค้น `\sigma_w`, `\sigma_h` ไม่เหลือ (ยกเว้นลายเซ็น)
- [ ] ค้น `Fig. ??` และ `Enter Caption` ไม่เหลือ
- [ ] ค้น `[X]`, `[Y]`, `[lan`, `[30/50/100]`, `[number]`, `[signature scheme]` ไม่เหลือ
- [ ] ค้น `Enron`, `10^6`, `10^{6}` ไม่เหลือ (ยกเว้นถ้าอ้างในบริบทอื่น)
- [ ] ค้น `logical operation`, `logical update` เหลือเฉพาะที่หมายถึงการดำเนินการเดี่ยวภายใน batch
- [ ] เลขสมการเปลี่ยน: ตรวจ `\eqref` / "(n)" ที่พิมพ์เลขตรงๆ ในข้อความ (เช่น "(51)", "(8)", "(10)", "(22)")
- [ ] Recompile ไม่มี undefined reference
