# Paper ↔ code sync list (AMTP (14).pdf vs main `00f9d42`; re-checked against `ca09924`)

Code changes since `00f9d42` that touch the paper: only PR #32 (Search Tree leaf by partition, `AMTP_PART_LEAF`):
items 1.13, 3.4, 3.6, 3.6b were updated on 17 Nov. Nothing else in `amtp/` changed.

Re-checked against the code and the runs on 17 Nov (after PR #33): items 1.4, 3.4, 3.5, 3.6, 3.6b and 3.7 corrected
(report `docs/reports/2026-11-17-paper-sync-fixes.md`).

Code flags: AND pruning, the greedy planner, result-only partition proofs and the Search Tree partition sets are
study flags that are **off by default in the library** (`AMTP_AND_PRUNE`, `AMTP_AND_GREEDY`, `AMTP_PART_RESULTS`,
`AMTP_PART_LEAF`); every paper run sets them on (plus `AMTP_PLACEMENT=fill`). The verifier accepts both response
forms whatever the flags are. The paper describes the flags-on form as the design.

Scope: System Process (III-C), Security Analysis (IV), Evaluation (V: cost model and set-up only).
Each item: where in the paper, what the code does, the new wording (plain text), and LaTeX.
Notation: the paper's Table II calls the PAPC `ρ_w`, but eqs. (19), (42), (68) print `σ_w`, which is also the
signature symbol. The code uses `ρ`. **Use `\rho_w` everywhere for the PAPC** (items below do).

Priority: **A** = the paper describes something the code does not do (must fix) · **B** = the code does more
than the paper says (must add) · **C** = small consistency fix.

---

## 1. System Process

### 1.1 [C] Phase 1 Step 2: associated data includes the policy

Code (`owner.py` `encrypt`): `aad = {domain, doc id, policy}`. Paper: `aad_d = Encode(i, id_d)`.

Text: "It defines public associated metadata aad_d = Encode(i, id_d, A_d), where A_d is the document access policy."

```latex
It defines public associated metadata $aad_d = \mathsf{Encode}(i, id_d, \mathbb{A}_d)$, where
$\mathbb{A}_d$ is the document access policy, and computes
```

### 1.2 [B] Phase 1 Step 5 and Phase 2 Step 1: placement group in the insert request

Code (`update.py` `enc_request`): `U_ins = <i, insert, e*, η, id_d, CT_d, g_d, C(d)>`. `g_d` ("bucket") is a
placement group chosen by the DO (in the experiments: the arXiv primary category folded into 16 groups). It is
signed with the request. It only guides where the CS places the file; no verification step depends on it.

Text: "The DO also assigns a placement group g_d ∈ {0, …, G−1} (for example a topic or department label). The
group is a placement hint: the CS places documents of the same group in the same partitions, and correctness of
search and verification does not depend on it."

```latex
The DO also assigns a placement group $g_d \in \{0,\dots,G-1\}$, for example a topic label.
The group is only a placement hint: the CS stores documents of one group in the same partitions,
and no verification step depends on it. The request is
\begin{equation}
U_d = \langle i, \mathsf{insert}, e_i^{*}, \eta_d, id_d, CT_d, g_d, C(d) \rangle .
\end{equation}
```

Apply the same change to eq. (10): `U_ins = <i, insert, e_i, η_d, id_d, CT_d, g_d, C(d)>`.

### 1.3 [A] One epoch = one batch of at most b operations (not one operation)

Code (`server.py` `prepare_update`, `engine.py` `commit`): an epoch takes 1..b signed requests
(`ops_per_epoch`); a modified partition increments its version **once per batch**; Δ binds the ordered list of
request digests; a large batch can need several splits of one partition. The paper says "each logical operation
and any induced restructuring form one authenticated epoch transition" and uses `H(U_op)` in eq. (27).
Experiments 3 and 4 use b = 1 … 1000, so the text must allow batches.

Places to change: Phase 2 intro, Step 1 ("increments its version once for the logical update"), Step 4
("After applying the logical operation once"), eq. (27), eq. (28), Step 5 last sentence, Phase 3 intro and
Step 1 ("For a single insertion … a balanced split produces two partitions within the bounds"), Proposition 1.

Text (Phase 2 intro): "The CS groups up to b admitted requests into one batch B = (U_1, …, U_m), 1 ≤ m ≤ b,
prepared against the same finalized predecessor. A batch and the restructuring it causes form one epoch
transition; b = 1 gives one operation per epoch."

Text (Step 1): "A modified existing partition increments its version once per batch, however many operations of
the batch touch it."

Text (Phase 3 Step 1): "After a batch, a partition can exceed θ_max by more than one entry. The CS then splits
it repeatedly until every resulting partition has at most θ_max live entries. A partition produced by a merge
is not merged again in the same transition."

```latex
The CS groups up to $b$ admitted requests into one batch
$\mathcal{B} = (U_1,\dots,U_m)$, $1 \le m \le b$, prepared against the same finalized predecessor.
A batch and the restructuring it causes form one epoch transition; $b = 1$ gives one operation per epoch.
Request nonces must be distinct inside a batch and unused in earlier epochs.

% Step 1
A modified existing partition increments its version once per batch, however many operations of
the batch touch it; a newly created partition starts at zero.

% eq. (27)
\begin{equation}
\Delta_i^{(e_i')} = H\big(i \,\|\, e_i' \,\|\, H(\mathcal{B}) \,\|\, H(\mathsf{Aff}_i) \,\|\,
R_{D_i}^{(e_i)} \,\|\, R_{D_i}^{(e_i')}\big), \qquad
H(\mathcal{B}) = H\big(H(U_1) \,\|\, \dots \,\|\, H(U_m)\big).
\end{equation}

% eq. (28): replace U_op, \sigma_op by the batch
\mathcal{U}_i = \langle i, e_i, e_i', R_{D_i}^{(e_i)}, R_{D_i}^{(e_i')},
(U_k,\sigma_k)_{k=1}^{m}, \mathsf{Aff}_i, \Delta_i^{(e_i')}, \pi^{upd} \rangle .

% Phase 3, Step 1
After a batch, a partition can exceed $\theta_{\max}$ by more than one entry. The CS then splits it
repeatedly until every resulting partition has at most $\theta_{\max}$ live entries. A partition
produced by a merge is not merged again in the same transition.
```

### 1.4 [B] Phase 2 Step 1: placement rule and position reuse

Code (`variants.py` `place`, placement `fill`, used in every experiment (the benchmark default; the library class
default is `least`); `engine.py` `insert`): the new file goes to the
fullest partition of its group that still has fewer than θ_max live entries (ties: smaller PID); if every
partition of the group is full, to the fullest one, and the split at commit repairs it. Inside the partition it
takes a freed (tombstone) position if one exists, otherwise it is appended. Partitions created by a merge serve
the groups of both sources.

Text: "For insertion, the CS places cid_d in the partition of group g_d with the most live entries among those
below θ_max (ties broken by the smaller PID). If all partitions of the group are full, it uses the fullest one
and Phase 3 splits it. Inside the partition, the entry takes a position freed by an earlier deletion if one
exists; otherwise it is appended. The placement rule is a choice of the CS; the validating DO checks the
resulting state, not the rule."

```latex
For insertion, the CS recomputes $cid_d = H(CT_d)$, rejects existing live identifiers, and places
$cid_d$ in the partition of group $g_d$ with the most live entries among those with
$n_{i,j} < \theta_{\max}$ (ties broken by the smaller $PID$). If every partition of the group is full,
it uses the fullest one and Phase~3 splits it. Inside the partition, the entry takes a position freed
by an earlier deletion if one exists; otherwise it is appended. This fill-first rule keeps a batch of
$b$ insertions in about $b/\theta_{\max}$ partitions per group. The rule is a choice of the CS:
the validating DO checks the resulting state, not the rule.
```

### 1.5 [A] Phase 2 Step 3: the IMT is an indexed Merkle tree with next pointers

Code (`index.py` `imt_leaf`, `imt_next`; `engine.py` `_update_imt`): `I_w = H(h_w ‖ ρ_w ‖ next(h_w))`.
Positions are **not** sorted: a new key is appended or reuses a freed position, a removed key frees its
position (value `I_⊥`) and its predecessor is relinked. The only sentinel leaf is the lower one
(`h_lo = 0^λ`, `ρ = 0^λ`); the upper sentinel `h_hi = 1^λ` appears only as a next value. Non-membership is
**one** opened leaf with `h_lo' < h < next(h_lo')`. The paper (eq. 20 and the following paragraph) describes a
sorted tree with two bracketing leaves.

Text: "The Index Merkle Tree (IMT) is an indexed Merkle tree. Each indexed key has one leaf
I_w = H(h_w ‖ ρ_w ‖ next(h_w)), where next(h_w) is the smallest indexed key above h_w, or the upper sentinel
h_hi for the largest key. A lower sentinel leaf I_lo = H(h_lo ‖ 0^λ ‖ next(h_lo)) starts the chain. Leaves keep
their position: a new key is appended or reuses a freed position, and a removed key leaves the fixed value I_⊥
at its position. An update therefore changes the leaf of the key and the leaf of its predecessor only. A key h
is not indexed exactly when one authenticated leaf (h', ρ', next(h')) satisfies h' < h < next(h'). The validating
DO checks that every insertion and removal keeps the next pointers in one strictly increasing chain from h_lo to
h_hi."

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

Also change in Step 5 ("New IMT keys require predecessor non-membership evidence") to: "A new IMT key requires
the opened leaf of its predecessor, which is relinked to it."

### 1.6 [C] Phase 2 Step 3: γ leaves are in PID order (needed by 1.8)

Already in the paper ("Partition components are ordered by PID"); make it explicit for the R^post tree, because
AND pruning relies on it.

```latex
The leaves of the $R^{post}_w$ tree are the $\gamma_{w,j}$ in strictly increasing $PID$ order; the
validating DO checks this order whenever a component is added or removed.
```

### 1.7 [B] Phase 4 Step 2: focus set and two evidence forms (AND pruning)

Code (`server.py` `_and_plan`, `_grow_full`, `_focus_evidence`; `boolean.py` `focus`). The CS chooses a set of
"full" keys `H_full ⊆ H_Q` (it always contains the absent keys). For an AND node it needs only one child sent in
full (it picks the child with the fewest partitions, then adds more keys while that lowers the proof size); an
OR node needs all its children. The focus set `F_Q` is the set of partitions in which a match can lie. Every
other present key is sent as *focus evidence*: only its components inside `F_Q`, plus neighbour γ leaves proving
it has no component in the other partitions of `F_Q`.

Text: replace eq. (49) and the paragraph after it with:

"Focus set. Let H_full ⊆ H_Q be a set of keys whose complete posting state or absence is sent. Define Foc
recursively: Foc(h) = Sel_i(h) if h ∈ H_full (the empty set for an absent key) and Foc(h) = ⊤ (unbounded)
otherwise; Foc(X ∧ Y) is the intersection of the bounded children, or ⊤ if none is bounded; Foc(X ∨ Y) is the
union of the children if all are bounded, otherwise ⊤. The CS chooses H_full such that F_Q = Foc(B_Q) ≠ ⊤.
A document matching B_Q lies in a partition of every key it satisfies, so every match lies in F_Q.
For a conjunction, sending the key with the fewest partitions in full is enough; the CS adds further keys to
H_full while this lowers the proof size. If H_full = H_Q, the response is the unpruned one.

Evidence. For h ∈ H_full the CS sends the complete posting state as before. For every other key it sends focus
evidence: its number of partitions n_h = |Sel_i(h)|, the root R^post_h, the components L_{h,j} with their leaf
positions for PID_{i,j} ∈ Sel_i(h) ∩ F_Q, and, for every partition t ∈ F_Q \ Sel_i(h), the two γ leaves at
adjacent positions whose PIDs bracket t (one leaf at the first or last position if t is outside the range).
A neighbour leaf is sent as its preimage (PID, v, H(Enc(L))), without its postings. One multiproof π^post_h
opens all these leaves in the R^post_h tree."

```latex
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
$I_h = H(h \,\|\, \rho_h \,\|\, \mathsf{next}(h))$.
The component set used for evaluation is
\begin{equation}
M_h =
\begin{cases}
\{(cid, PID_{i,j}, l) : (cid,l) \in L_{h,j}\}, & h \in H_{full},\\
\{(cid, PID_{i,j}, l) : (cid,l) \in L_{h,j},\ PID_{i,j} \in F_Q\}, & h \notin H_{full},
\end{cases}
\end{equation}
and $M_Q = \mathsf{Eval}(B_Q, \{M_h\}_{h \in H_Q})$ is unchanged, because every match lies in $F_Q$.
```

Remove the sentence "partial component proofs alone do not establish posting completeness" (no longer true in
this form) and replace it with: "Focus evidence does not reveal or authenticate the components outside F_Q; it
authenticates that the listed components are all the components of h inside F_Q."

### 1.8 [B] Phase 4 Step 3: partition proofs only for the returned files (result-only partition check)

Code (`server.py` `build_response`, `part_results_on`): partition descriptors and slot multiproofs are built
only for partitions that hold a **result** file, and only the result positions are opened. Every other covered
partition sends just `(PID, v)`; `v` is bound by γ.

Text: replace eqs. (52)–(57):

"Let M_cov = ∪ M_h and S_cov its partitions, as before, and let S_res = {PID : (cid, PID, l) ∈ M_Q} be the
partitions of the returned files. For every PID_{i,j} ∈ S_res the CS supplies B_{i,j} = ⟨PID, v, R_P⟩ and one
positional multiproof for Q_{Q,j} = {l : (cid, PID_{i,j}, l) ∈ M_Q}. For every other covered partition it sends
only the version: Ver_Q = [(PID_{i,j}, v_{i,j}) : PID_{i,j} ∈ S_cov \ S_res]. These versions need no proof of
their own: a wrong version changes γ and the reconstructed PAPC then fails the IMT check. One domain multiproof
opens the partition states of S_res."

```latex
Let $M_{cov} = \bigcup_{h \in H_Q} M_h$ and $S_{cov} = \{PID : (cid,PID,l) \in M_{cov}\}$, and let
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
\Pi^{dom}_Q = \mathsf{MultiProof}(T^{part}_i, J_{res}).
\end{equation}
```

### 1.9 [B] Phase 4 Step 4, eq. (59) and the locality paragraph, eq. (61)

```latex
\Pi_Q = \big\langle [E_h]_{h \in H_Q},\ [(B_{i,j}, \Pi^{part}_{Q,j})]_{PID_{i,j} \in S_{res}},\
\mathsf{Ver}_Q,\ \Pi^{dom}_Q \big\rangle .

% eq. (61)
p_Q = \sum_{h \in H_Q} |M_h|, \quad r_Q = |M_Q|, \quad s_Q = |S_{cov}|, \quad
s_Q^{res} = |S_{res}|, \quad f_Q = |F_Q|, \quad b_Q = |B_Q| .
```

Text for the locality paragraph: "Posting resolution depends on p_Q, which now counts only the postings of full
keys and the postings of pruned keys inside F_Q. Ciphertext retrieval and partition proofs depend on r_Q and
s_Q^res. For a conjunction, p_Q is bounded by the posting state of its most selective key plus the matching
components of the others; for a disjunction and for a single keyword no key can be pruned and p_Q is the sum of
the complete posting states."

```latex
Posting resolution depends on $p_Q$, which counts the postings of the full keys and the postings of the
pruned keys inside $F_Q$. Ciphertext retrieval and partition proofs depend on $r_Q$ and $s_Q^{res}$.
For a conjunction, $p_Q$ is bounded by the posting state of its most selective key plus the components
of the other keys inside $F_Q$. For a disjunction and for a single keyword no key can be pruned, and
$p_Q$ is the sum of the complete posting states.
```

### 1.10 [B] Algorithm 2 (replace lines 3–12)

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

### 1.11 [A/B] Phase 5: verification steps

**Step 1 (absent key).** Replace "including the ordering and positional adjacency of the bracketing leaves":

```latex
For an absent key, the evidence opens one IMT leaf $(h', \rho', \mathsf{next}(h'))$. The DU verifies it
against $R^{idx}_{D_i}$ and requires $h' < h < \mathsf{next}(h')$.
Only a valid proof permits assigning $M_h = \emptyset$.
```

**Step 2 (PAPC).** Keep eqs. (66)–(68) for full evidence with `\hat{\rho}_h` and the leaf
`H(h ‖ \hat{\rho}_h ‖ next(h))`; add the focus case and the version source.

Text: "The version of every partition used in a γ comes from its descriptor B_{i,j} if the partition is in
S_res and from Ver_Q otherwise; Ver_Q must be in canonical order and must not repeat a described partition. If
any evidence is in focus form, the DU computes F_Q = Foc(B_Q) from the full and absent evidence and rejects if
F_Q = ⊤. For a focus key it rebuilds γ for each component of Seg_h, takes the neighbour leaves from their
preimages, and verifies π^post_h against R^post_h with n_h leaves. It requires all opened leaves to be at
distinct positions with strictly increasing PIDs, and for every t ∈ F_Q: either Seg_h contains t, or two opened
leaves at adjacent positions bracket t, or the leaf at position 0 has a PID above t, or the leaf at position
n_h − 1 has a PID below t. A partition of F_Q opened only as a neighbour is rejected. It then computes
ρ̂_h = H(h ‖ n_h ‖ R^post_h) and verifies the IMT leaf."

```latex
The version of each partition used in a $\gamma$ is taken from its descriptor $B_{i,j}$ if
$PID_{i,j} \in S_{res}$ and from $\mathsf{Ver}_Q$ otherwise; $\mathsf{Ver}_Q$ must be in canonical order
and must not repeat a described partition.

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
```

Replace the last sentence of Step 2 ("No separate partial PAPC proof substitutes for this reconstruction"):
"For a full key, reconstructing the PAPC authenticates its partition count, identities, versions and contents.
For a focus key, the multiproof and the bracketing rule authenticate that the listed components are exactly the
components of the key inside F_Q."

**Step 3 (partitions).** Replace eq. (69) and the sentence after eq. (70):

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

Also change "If M_cov = ∅, partition evidence is unnecessary" to "If M̂_Q = ∅, no partition descriptor is sent."
and, in "An empty response …": replace "Nonempty proof coverage must still be verified even when the final
Boolean result is empty" by "Component evidence and the version list are still verified when the result is
empty."

**Algorithm 3**: line 11 "Derive M_cov; require descriptors for exactly S_res and versions for the other covered
partitions"; add before line 13 "Compute F_Q if any evidence is in focus form"; line 14 "Reconstruct its PAPC
(full) or verify its R^post multiproof and the bracketing rule (focus), then verify IMT membership"; line 16
"for each partition of S_res".

**Verification guarantees paragraph**: replace the first sentence by: "Partition proofs authenticate the live
location of every returned file, while PAPC reconstruction, focus evidence and IMT proofs authenticate, for
every query key, all of its postings in the partitions where a match can lie."

### 1.12 [C] Entity descriptions (Section III-A)

- CS: "It returns ciphertexts and authenticated posting, membership, or non-membership evidence, using ASPA to
  share Merkle paths **and to omit posting components that cannot contain a match**."
- DU: "It verifies every component posting state **needed for the query** or authenticated absence …".

### 1.13 [B] Phase 2 Step 2: Search Tree leaf by partition (added 17 Nov, PR #32 `AMTP_PART_LEAF`)

Code (`index.py` `PartPosting`, used when `AMTP_PART_LEAF=1`, on in the "part leaf" cloud round): for a keyword in
at least 3 partitions (`KEEP_MIN_PARTS`), the Search Tree leaf keeps, next to the same list L_w, the set of its
partitions Sel_i(h_w) and the position of each partition's component in the list. Built once with the snapshot.
The server reads them for the focus set and the focus evidence instead of rebuilding them per query. The leaf is
never sent and never trusted; responses are identical byte for byte (25 tests); no equation changes.
Measured cost (Mac, 100k files): snapshot memory +6% (1,279 → 1,359 MB), build time +1.5%.

Text (add after "The Search Tree is a B+ tree of order B …"): "For a key with postings in at least three
partitions, the leaf also stores Sel_i(h_w) and the position of each component in L_w, so the CS reads the
partition set of a key without scanning its posting state. The leaf is lookup data, not evidence."

```latex
For a key with postings in at least three partitions, the leaf also stores $\mathsf{Sel}_i(h_w)$ and the
position of each component in $L_w$, so the CS reads the partition set of a key without scanning its
posting state. The leaf is lookup data, not evidence: it is never sent to the DU.
```

---

## 2. Security Analysis

### 2.1 [A] IV-A assumptions

Replace "IMT non-membership requires authenticated consecutive bracketing leaves or boundary sentinels" by:

```latex
IMT non-membership requires one authenticated leaf $(h', \rho', \mathsf{next}(h'))$ with
$h' < h < \mathsf{next}(h')$. Its meaning relies on the indexing invariant of Proposition~1: the next
pointers of the finalized IMT form one strictly increasing chain over exactly the indexed keys, and the
leaves of every $R^{post}$ tree are in strictly increasing $PID$ order.
```

### 2.2 [B] IV-B leakage

- `L_upd`: add "placement group" and "batch size and order of operations in an epoch".
- `L_qry`: replace "component posting associations and sizes" by "the number of partitions of every query key,
  the component postings sent (complete for full keys, inside the focus set for pruned keys) and their sizes,
  the identifiers and versions of neighbouring partitions".
- Replace "Complete component postings reveal associations beyond the final Boolean result" by: "The component
  postings sent reveal associations beyond the final Boolean result. AND pruning reduces what the DU receives;
  the CS already holds the complete index, so its view does not change."

```latex
The component postings sent reveal associations beyond the final Boolean result. AND pruning reduces
what the DU receives; the CS already holds the complete index, so its view is unchanged.
```

### 2.3 [C] Lemma 1

Add to the proof: "The same argument applies to the next pointer of an IMT leaf and to the leaf count n_h and
positions of an R^post tree."

### 2.4 [A] Proposition 1: extend the invariant, allow batches

Add two conditions to Inv(S), as text in the paragraph "The invariant further requires …" (an equation
block overflows the two-column layout; tried 17 Nov):

```latex
The invariant further requires unique document locations, canonical duplicate-free postings, no
references to tombstones or retired partitions, and valid partition identifiers and versions. It also
requires two orderings: (chain) the next pointers of the IMT link $h_{lo}$ to $h_{hi}$ in strictly
increasing order over exactly the keys $h$ with $M_S(h) \ne \emptyset$; and (order) the leaves of every
$R^{\mathrm{post}}_h$ tree are the $\gamma_{h,j}$ for $PID_{i,j} \in \mathsf{Sel}_S(h)$, in strictly
increasing $PID$ order.
```

Symbol clash: the proof writes the relocation map as `ρ(cid, PID, ℓ)` (eqs. 113–114 in AMTP (14)), but `ρ_h` is
now the PAPC everywhere. Rename the relocation map to `\mu`:

```latex
\mu(cid, PID, \ell) = \big(cid, \mathsf{Loc}_{S'}(cid)\big), \qquad
M_{S'}(h) = \mu\big(M_{S^{+}}(h)\big).
```

Also in the proof: eq. (112) `Apply(S, U)` → `Apply(S, \mathcal{B})`; eq. (116) `ValidTrans(S, U, S')` →
`ValidTrans(S, \mathcal{B}, S')`; "keys affected by the logical update" → "keys affected by the operations of
the batch".

Proof additions: "Let a batch B = (U_1, …, U_m) produce S^+ = Apply(S, B); the argument for one operation is
applied to U_1, …, U_m in order. For a key that enters or leaves the index, validation opens the leaf of its
predecessor and checks the relinked pointers, which preserves (chain). For a component that is added to or
removed from a posting state, validation checks its position against its neighbours in the γ list, which
preserves (order). Repeated splits of one partition are validated on the DO's own partition model."

### 2.5 [B] New lemmas before Theorem 1

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

### 2.6 [A] Theorem 1: statement and proof

Statement: add the invariant to the assumptions.

```latex
\begin{theorem}[Exact Authenticated Boolean Results]
Assume collision resistance of $H$, an authentic retained Domain Root whose state satisfies
$\mathsf{Inv}$ (Proposition~1), and the Phase~5 verification rules. For every PPT adversarial CS
$\mathcal{A}$ there exists a PPT collision finder $\mathcal{B}$ such that
$\Pr[\mathsf{Bad}_Q] \le \mathsf{Adv}^{CR}_H(\mathcal{B},\lambda)$.
\end{theorem}
```

Proof, step (i) — replace:

```latex
\emph{(i) Component authenticity.} For a full key, acceptance reconstructs $\hat{\rho}_h$ from the
complete posting state and verifies $H(h \,\|\, \hat{\rho}_h \,\|\, \mathsf{next}(h))$ in the IMT; the
versions come from descriptors or from $\mathsf{Ver}_Q$ and are inputs of $\gamma$. Under
$\neg\mathsf{Coll}$, $\hat{M}_h = M_h^{*}$ and the partition set of $h$ is the committed one, so the DU
computes the same $F_Q$ as in Lemma~2. For an absent claim, the opened leaf $(h',\rho',\mathsf{next}(h'))$
with $h' < h < \mathsf{next}(h')$ and the (chain) invariant give $M_h^{*} = \emptyset$. For a focus key,
Lemma~3 gives $\hat{M}_h = \{(cid,PID,l) \in M_h^{*} : PID \in F_Q\}$.
```

Step (ii) — replace "For every (cid, PID, l) ∈ M_cov" by the result set:

```latex
\emph{(ii) Location authenticity.} For every $(cid,PID,l) \in \hat{M}_Q$, acceptance verifies $(l,cid)$
against the partition root and authenticates $A = H(PID \,\|\, v \,\|\, R_P)$ against $R^{part}_{D_i}$.
Hence every returned file is at its committed live location. Locations of postings that are not
returned are not opened; they are bound by the PAPC and are not needed for $\mathsf{Bad}_Q$.
```

Step (iii) — replace eq. (91):

```latex
\emph{(iii) Exact Boolean-result coverage.} By (i) and Lemma~2,
\begin{equation}
\hat{M}_Q = \mathsf{Eval}\big(B_Q, \{\hat{M}_h\}_{h \in H_Q}\big)
          = \mathsf{Eval}\big(B_Q, \{M_h^{*}\}_{h \in H_Q}\big) = M_Q^{*} .
\end{equation}
```

Step (iv) unchanged. Add after the proof:

```latex
\emph{Remark.} Without pruning ($H_{full} = H_Q$) and with partition proofs for all of $M_{cov}$, the
theorem reduces to the unpruned construction. Both response forms are accepted by the same verifier.
```

### 2.7 [C] Theorem 2 proof, last paragraph

"By Lemma 1, any accepted partition or posting state inconsistent with these subroots likewise implies a
collision" stays true. Add: "This includes the versions in Ver_Q, which are inputs of authenticated γ values."

### 2.8 [C] Query admission (IV-G)

Unchanged: the code checks HMAC, |t_CS − t| ≤ δ_t (δ_t = 300 s in the prototype), unused nonce, epoch = current.

---

## 3. Evaluation

### 3.1 [B] Table III: add symbols

| Notation | Description |
|---|---|
| `p_Q` | (change) postings sent: complete for full keys, inside the focus set for pruned keys |
| `s_Q^res` | partitions that hold a returned file |
| `f_Q` | partitions of the focus set |
| `k_Q^F`, `n_h` | pruned query keys; partitions of key h |
| `b` | operations per epoch |

```latex
$k_Q, p_Q, r_Q, s_Q$ & AMTP query keys, postings sent, results, and covered partitions \\
$k_Q^{F}, f_Q, s_Q^{res}, n_h$ & Pruned keys, focus-set partitions, result partitions, and partitions of key $h$ \\
$b, u$ & Operations per epoch and protected keys affected by an AMTP update \\
```

### 3.2 [A] Table IV: AMTP row

Search / proof generation:

```latex
$k_Q T_{lookup} + T_{Eval} + \sum_{h \notin H_{full}} T_{MP}(f_Q, n_h)
 + \sum_{j \in S_{res}} T_{MP}(q_j, n_{i,j}) + T_{MP}(s_Q^{res}, m_i)$
```

Verification:

```latex
$(p_Q + s_Q)\,T_H + \sum_{h \notin H_{full}} T_{MV}(f_Q, n_h) + k_Q\,T_{MV}(1, K_i)
 + \sum_{j \in S_{res}} T_{MV}(q_j, n_{i,j}) + T_{MV}(s_Q^{res}, m_i) + T_{Eval} + r_Q T_H$
```

(`K_i` = number of IMT leaves; `q_j` = result positions in partition j; the first term is the γ hashing, which
replaces `C_idx`.) Update, per epoch of b operations:

```latex
$T_{part} + u\,T_{post} + T_{IMT} + T_{ABS}$ \quad (per epoch of $b$ operations)
```

### 3.3 [A] Cost paragraph after Table IV

Text: "AMTP avoids pairing-based operations. For a conjunction, AND pruning limits the postings sent to the
complete state of the most selective keys and the components of the other keys inside the focus set, so search
and verification depend on p_Q and f_Q rather than on the total size of all queried posting lists. Partition
proofs are built only for the s_Q^res partitions that hold a returned file. A disjunction or a single keyword
cannot be pruned: every posting of every key must be authenticated, and the cost grows with the sum of the
posting lists. Updates are processed per epoch of b operations and affect only the touched partitions, their
posting states and the corresponding IMT leaves."

```latex
AMTP avoids pairing-based operations. For a conjunction, AND pruning limits the postings sent to the
complete state of the most selective keys and the components of the other keys inside the focus set,
so search and verification depend on $p_Q$ and $f_Q$ rather than on the total size of all queried
posting lists. Partition proofs are built only for the $s_Q^{res}$ partitions that hold a returned file.
A disjunction or a single keyword cannot be pruned: every posting of every key must be authenticated,
and the cost grows with the sum of the posting lists. Updates are processed per epoch of $b$ operations
and affect only the touched partitions, their posting states, and the corresponding IMT leaves.
```

### 3.4 [A] Experimental set-up (replace the whole paragraph)

Facts from the run manifests (`baselines/results/runs/cloud/prune_w1/.../*.manifest.json`) and the code.
**Check before submission:** the `cryptography` version on the cloud machines (not recorded in the manifest).

Text: "AMTP is implemented as a Python 3.12 prototype. All measurements run on AWS r7i.4xlarge instances
(Intel Xeon Platinum 8488C, 16 vCPUs, 128 GiB RAM, Ubuntu Linux), one job at a time per instance, single
process. Cryptographic operations use the cryptography library: SHA-256 for H, AES-256-GCM for document
encryption, AES-SIV for DEnc, and HMAC-SHA256 for query authentication. Root-transition and request
authorization use Ed25519 signatures as a stand-in for ABS, and K_d is protected by an attribute-policy key
wrap as a stand-in for CP-ABE; this stand-in is not collusion-resistant and affects only decryption, which is
reported separately. The Root Anchor is simulated in-process with the same predecessor and epoch checks, so
ledger latency is not included. Ciphertexts are stored in an in-process consistent-hashing DHT with 6 nodes and
replication factor 3. Network latency is excluded for all schemes. AMTP uses θ_max = 64, θ_min = 16, G = 16
placement groups (arXiv primary categories), fill-first placement, AND pruning, result-only partition proofs and
partition sets in the Search Tree leaves. Exp. 3 and 4 were run before the Search Tree partition sets were added;
these sets change neither the update procedure nor any proof or response, only the server's search time.
The initial N documents are loaded in bulk and anchored by the owner; every later update runs the full protocol
(signed requests, CS preparation, DO validation, anchoring). Each query is run 15 times after 3 unrecorded
warm-up runs with garbage collection disabled; we report the median of the 15 runs per query and the median
over queries per data point. Server time is reported as search (lookup and Boolean evaluation), proof
generation, and ciphertext fetch; user time as query generation and verification. Sizes are counted in binary
encoding with the same rules for every scheme (1 KB = 1000 bytes)."

```latex
AMTP is implemented as a Python~3.12 prototype. All measurements run on AWS \texttt{r7i.4xlarge}
instances (Intel Xeon Platinum 8488C, 16 vCPUs, 128\,GiB RAM, Ubuntu Linux), one job at a time per
instance, in a single process. Cryptographic operations use the \texttt{cryptography} library:
SHA-256 for $H$, AES-256-GCM for document encryption, AES-SIV for $\mathsf{DEnc}$, and HMAC-SHA256 for
query authentication. Request and root-transition authorization use Ed25519 signatures as a stand-in
for ABS, and $K_d$ is protected by an attribute-policy key wrap as a stand-in for CP-ABE; this stand-in
is not collusion-resistant and affects only decryption, which is reported separately. The Root Anchor
is simulated in-process with the same predecessor and epoch checks, so ledger latency is not included.
Ciphertexts are stored in an in-process consistent-hashing DHT with 6 nodes and a replication factor
of 3. Network latency is excluded for all schemes.

AMTP uses $\theta_{\max} = 64$, $\theta_{\min} = 16$, $G = 16$ placement groups (arXiv primary
categories), fill-first placement, AND pruning, result-only partition proofs, and partition sets in the
Search Tree leaves. Experiments~3 and~4 were run before the Search Tree partition sets were added;
these sets change neither the update procedure nor any proof or response, only the server's search time.
The initial documents are loaded in bulk and anchored by the owner; every later update runs the full protocol (signed
requests, CS preparation, DO validation, and anchoring). Each query is run 15 times after 3 unrecorded
warm-up runs with garbage collection disabled; we report the median of the 15 runs per query and the
median over queries per data point. Server time is split into search, proof generation, and ciphertext
fetch (defined below); user time into query generation and verification. Sizes are
counted in binary encoding with the same rules for every scheme (1\,KB = 1000 bytes).
```

### 3.5 [A] Dataset paragraph (replace)

Text: "The evaluation uses the arXiv metadata snapshot from Kaggle (Cornell University; latest record dated
2026-10-30; 3,233,620 papers), organized into four domains by the primary (first) arXiv category: D1 = cs, D2 = math, D3 = astrophysics,
gravitation, high-energy and nuclear physics (astro-ph, gr-qc, hep-*, nucl-*), D4 = condensed matter, quantum and
other physics (cond-mat, quant-ph, physics, math-ph, nlin), each with the archives' former names. Papers whose
abstract has fewer than 30 words or that are withdrawn are skipped. Each domain has 125,000 initial documents in
chronological order and a disjoint pool of 12,500 documents for insertions (seed 42). Each document is a paper's
title and abstract. Keywords W(d)
are extracted once with the Phase 1 procedure (RAKE, at most κ = 20 phrases of 1–3 words per document) and are
used as they are by every scheme; AMTP's extraction time is reported separately. A domain of n documents is the
first n documents of that domain, n ∈ {10, 25, 50, 75, 100, 125} × 10^3; no synthetic replication is used.
Single-domain experiments are run on each of the four domains separately and the median over domains is
reported; multi-domain experiments query several domains with one domain-bound query each."

```latex
The evaluation uses the arXiv metadata snapshot from Kaggle (Cornell University; latest record dated
2026-10-30; 3{,}233{,}620 papers), organized into four domains by the primary arXiv category: $D_1$ = cs, $D_2$ = math,
$D_3$ = astrophysics, gravitation, high-energy and nuclear physics (astro-ph, gr-qc, hep-*, nucl-*), and
$D_4$ = condensed matter, quantum and other physics (cond-mat, quant-ph, physics, math-ph, nlin).
Papers with abstracts shorter than 30 words and withdrawn papers are skipped. Each domain has
125{,}000 initial documents in chronological order and a disjoint pool of 12{,}500 documents for
insertions (seed 42). Each document is a paper's title and abstract. Keywords $W(d)$ are extracted once with the Phase~1 procedure (RAKE, at
most $\kappa = 20$ phrases of 1--3 words per document) and are used as they are by every scheme; AMTP's
extraction time is reported separately. A domain of $n$ documents is the first $n$ documents of that
domain, $n \in \{10, 25, 50, 75, 100, 125\} \times 10^{3}$; no synthetic replication is used.
Single-domain experiments run on each of the four domains separately and report the median over domains;
multi-domain experiments send one domain-bound query to each queried domain.
```

Delete: "Experiments 1–3 place all N documents in a single AMTP domain" and "N ∈ {10^4, 5×10^4, 10^5, 2×10^5}".
D3 and D4 categories checked on 17 Nov against `datasets/arxiv/select_files_v4.py` (`GROUPS`; former archive names
such as cmp-lg, alg-geom, supr-con are folded into the same domains) and `datasets/arxiv/data_v4/download_info.txt`.

### 3.6 [C] Baselines paragraph

Keep, with two changes. (1) In the part-leaf round (17 Nov, `d25616b`) every baseline was re-measured on the
same machine as the AMTP suite it is plotted with: "All schemes run on the same instance, documents, keywords and
query files; each baseline is measured on an instance of the same type (AWS r7i.4xlarge), in most figures the
instance of the AMTP suite it is compared with." Exception: in the no-fetch search figures
(`baselines/results/part_leaf/graphs/search_no_fetch/`) SE-COLLAB and Du come from separate re-runs on two other
instances of the same type (`runs/cloud/partleaf_w4`, `partleaf_w5`). Re-measured on those instances, SE-COLLAB's
`search_core` was 1–3% slower and Du's server time 2–7% faster than on the AMTP instance, so the difference
favours Du. If the paper states it: "Instances of the same type differed by at most 7% on the same workload." (2) Add the timing
definitions used for the search-only comparison (updated 17 Nov: SE-COLLAB and Du now record search without
fetch, PR #32):

```latex
For the search-only comparison, every scheme is timed without proof generation and without returning
ciphertexts. AMTP's search time is the lookup, focus-set derivation, and Boolean evaluation. For
SE-COLLAB we use its own timers for posting retrieval and Boolean evaluation; for Du et al.\ the server
traversal that returns only the matching positions; for Chen et al.\ the whole server time, which also
includes one XOR per visited entry for its proof tag. Chen et al.\ is measured after warm-up, when its
update chain has been collapsed by the first search, which is its best case. Where ciphertext retrieval
is included, AMTP is compared with SE-COLLAB and Du et al.\ only, since Chen et al.\ returns no
ciphertexts.
```

### 3.6b [B] Search-only measurement (decided 16 Nov: no search index, two forms only)

Decision: the paper reports the server's search time in two forms, both on the structures the design already
has (Cuckoo filter + B+ Search Tree). The "fast" form with a per-snapshot search index is **not** used.

| Form | What it does | CSV column (without / with fetch) | Role in the paper |
|---|---|---|---|
| partition-first | lookup → focus set F_Q from the partition lists → file sets only inside F_Q → Eval | `server_search_pf` / `server_search_pf_fetch` | **main line** (this is what the server does with AND pruning) |
| full | lookup → file sets from the whole posting lists → Eval | `server_search` / `server_search_fetch` | reference line: the search without the focus set |

Both forms give the same files for every query (checked against the full verified response in every run).
For a single keyword and for a disjunction the two forms are the same work, since nothing can be pruned.
Proof-generation time is reported as server total minus search plus fetch (same repetition).

Update 17 Nov (PR #32): the main numbers now come from the "part leaf" cloud round (`d25616b`), where the
partition-first search reads the partition sets kept in the Search Tree leaf (item 1.13). Results:
`baselines/results/part_leaf/`, report `docs/reports/2026-11-17-search-tree-part-leaf.md`. Replace "No structure
beyond those of Phase 2 is used" by "It uses only the Cuckoo filter and the Search Tree of Phase 2, whose
leaves keep the partition set of every key in at least three partitions". (Not "of each key": a key in one or two
partitions has no stored set; its set is read from its short posting list.)

Text: "Search time is the time the CS needs to find the matching files, without building any proof: it looks up
every query key in the Cuckoo filter and the B+ Search Tree, derives the focus set F_Q from the partition sets
of the keys (kept in the Search Tree leaf for keys in at least three partitions), builds each key's file set inside F_Q only, and evaluates B_Q. We also
report the search without the focus set, where each file set is built from the complete posting list. It uses
only the Cuckoo filter and the Search Tree of Phase 2. Proof-generation time is the remaining server time: IMT paths, posting evidence, and partition
and domain multiproofs. Every search-only result is compared with the result of the full verified query, and a
difference aborts the run."

```latex
\textbf{Search-only time.} Search time is the time the CS needs to find the matching files, without
building any proof: it looks up every query key in the Cuckoo filter and the B+ Search Tree, derives
the focus set $F_Q$ from the partition sets of the keys (kept in the Search Tree leaf for keys in at
least three partitions), builds each
key's file set inside $F_Q$ only, and evaluates $B_Q$. We also report the search without the focus set,
where each file set is built from the complete posting list. It uses only the Cuckoo filter and the
Search Tree of Phase~2. Proof-generation time is the
remaining server time: IMT paths, posting evidence, and the partition and domain multiproofs. Every
search-only result is compared with the result of the full verified query, and a difference aborts the
run.
```

Figures for the paper (17 Nov): use `baselines/results/part_leaf/graphs/search_no_fetch/` — every scheme
without proof and without fetch, one AMTP line: AMTP `server_search_pf`, Chen `server_total`, SE-COLLAB and Du
`search_no_fetch` (their own timers; definitions in 3.6). Its legend says just "AMTP". The older folder
`part_leaf/graphs/search_only/` pairs AMTP with or without fetch against each baseline and is no longer needed
for the paper. Numbers: `search_no_fetch/figure_points.csv`; table in `docs/reports/2026-11-17-search-tree-part-leaf.md`.
If the full form is ever drawn: "AMTP" = partition-first, "AMTP (no focus set)" = full.
`bench_split/plot_search.py` (main `1d7e4fc`) already draws partition-first as the AMTP line and no longer
plots the fast form; the full form is not drawn (optional reference line, plot code only).

Cost model (Table IV, optional extra row or footnote), search only:

```latex
$k_Q T_{lookup} + T_{Foc}(k_Q, \textstyle\sum_h n_h) + T_{Eval}$ \quad (search only, no proof)
```

where `T_Foc` is the set work on the partition lists (`n_h` = partitions of key h).

What to state (part-leaf round on cloud, from the PR #32 report; superseded the Mac preview of 16 Nov):
- Single domain (Search 1.1 / 1.2, no fetch): faster than Chen, SE-COLLAB and Du at every point; at 10k files
  about equal to Chen (0.0219 vs 0.0220 ms).
- Search 2.1: faster than SE-COLLAB for AND, AND-of-OR, OR-of-AND; **slower for OR at k_Q ≥ 4** (also without
  fetch: an OR has to union the file sets of every partition that holds any key).
- Search 2.2 (query sent to every domain): faster up to 8 domains, **slower at 16 and 32**.
- Exp. 5: faster at every D.
- End-to-end (with the user's verification): faster than SE-COLLAB everywhere, than Chen at k_Q ≥ 2,
  **slower than Du at k_Q ≥ 2**.

### 3.7 Experiment descriptions (not rewritten now — results not complete)

Statements in the current text that are already wrong against the code and must change when the descriptions
are rewritten:

| Paper says | Code / runs |
|---|---|
| 30 runs | 15 runs |
| MacBook Pro M3 | AWS r7i.4xlarge |
| κ = 10, 4 × 50,000 + 5,000 | κ = 20, 4 × 125,000 + 12,500 |
| Exp. 1: N ∈ {10^4 … 2×10^5}, kQ ∈ {1,2,4,8,16}, "kQ = 16 always empty" | Search 1.1 / 1.2: files per domain 10k–125k, kQ up to 20; with κ = 20 a 16-key AND is not always empty |
| Exp. 2: marker keyword, three placements | Verify 1.1 / 2.1: five real keywords whose result size is closest to 10 / 100 / 1,000 / 10,000; a separate tamper experiment (modify, hide, inject, old version) |
| Exp. 3: "DO transition validation is not included in the update latency" | update time = request + CS + **DO validation** + anchoring |
| Exp. 4: N = 20,000, 20 batches of 100, Global-MT | 100,000 initial files (one domain, 4 categories); phase 1: 1,000 insert batches of 100 (b = 100), 95% of them into one hot group; phase 2: delete 65% of the hot group's live files, 100 per batch (≈ 1,674 batches in all); one run per variant and θ_max (manifest `runs: 1`); queries measured every 100 batches; variants AMTP, Static-MT, Global-MT(v) (Global-MT with partition versions), θ_max ∈ {64, 128, 256} |
| Exp. 5: SE-COLLAB only | unchanged in structure; target domain 5,000 files, D ∈ {1 … 32} |

---

## 4. Things the code has that need **no** paper change

- Cuckoo filter in front of the B+ tree (already "optional", not evidence).
- Batched Merkle updates (`set_leaves`), fast γ encoding, deterministic tie-break of the planner, kept R^post
  trees for keys in ≥ 3 partitions: implementation details with identical outputs.
- `bench_split` search index (`SearchIndex`, the "fast" form): **not used in the paper** (decided 16 Nov). Do
  not plot or cite the `server_search_fast*` and `fast_*` columns, and do not mention a search index anywhere.
- Global Root: `R_G = MerkleRoot([H(i ‖ e_i ‖ R_{D_i})]_i)`; the paper does not define it — optional one-line
  definition in Phase 2 Step 5.

---

## 5. Abstract, Introduction, Related Work, System Model, Threat Model

No structural change. The sentences below describe the old proof form ("complete posting state of every
keyword", "paths for everything the component postings reference") and must follow the new one.

### 5.1 [A] Abstract

Old: "Authenticated Selective Proof Assembly (ASPA) shares Merkle paths across records and partitions referenced
by the component postings, decoupling proof coverage from the final Boolean result."

New text: "Authenticated Selective Proof Assembly (ASPA) sends, for a conjunction, only the posting components
that lie in partitions where a match is possible, proves that nothing else was withheld, and shares Merkle paths
across the returned records and their partitions."

```latex
Authenticated Selective Proof Assembly (ASPA) sends, for a conjunction, only the posting components
that lie in partitions where a match is possible, proves that no other component was withheld, and
shares Merkle paths across the returned records and their partitions.
```

Also: "bind complete posting states to partition identities, versions, and ciphertext locations" can stay (the
PAPC still commits the complete state). Optional: after "insertion, deletion, split, and merge operations" add
"applied in batches".

### 5.2 [A] Introduction

(a) Second challenge. Old: "the server must authenticate the complete posting state of every queried keyword".

```latex
For a Boolean multi-keyword query, the server must authenticate every posting that can affect the
result, or prove that the remaining postings cannot, and return exactly the records determined by the
requested AND/OR expression.
```

and "authenticate all component posting states or their absence" → "authenticate every component posting state
that can affect the result, or its absence".

(b) Overview paragraph. Old: "Authenticated Selective Proof Assembly (ASPA) shares Merkle paths across all
records and partitions referenced by the component postings, while ciphertext retrieval is restricted to the
resulting Boolean set."

```latex
Authenticated Selective Proof Assembly (ASPA) limits the proof to what the result depends on: for a
conjunction, the keys with the fewest partitions are sent in full and bound the partitions in which a
match can lie; every other key sends only its components in those partitions together with a proof
that it has no further component there. Partition proofs and ciphertext retrieval are restricted to
the resulting Boolean set.
```

(c) Global Root. The code computes `R_G = MerkleRoot([H(i ‖ e_i ‖ R_{D_i})]_i)`; the paper writes
`MerkleRoot(R_{D_1}, …, R_{D_n})`. Either keep the paper's short form and call it a sketch, or write:

```latex
$R_G = \mathsf{MerkleRoot}\big(H(1 \| e_1 \| R_{D_1}), \dots, H(n \| e_n \| R_{D_n})\big)$
```

(d) Third contribution. Old: "ASPA shares authentication paths across the component postings and referenced
partitions".

```latex
\item \textbf{Verifiable Boolean Multi-Keyword Search:} We develop PAPCs to authenticate complete
per-keyword posting states and support exact verification of conjunctive, disjunctive, and nested
AND/OR results without keyword-combination indexes. ASPA prunes a conjunction to the partitions in
which a match can lie, with a proof that no posting component was withheld, and opens partition proofs
only for the returned records, while still detecting omission, addition, duplication, substitution,
and ciphertext tampering, including empty Boolean results.
```

(e) Second contribution: optional "…insertion, deletion, split, and merge procedures, applied in batches of
operations per epoch, …".

### 5.3 [B] Related Work

No claim is wrong. One addition is recommended for honesty: starting a conjunction from the most selective
keyword is a known idea in conjunctive SSE (the s-term of OXT, Cash et al., CRYPTO 2013). AMTP's part is making
the pruned answer verifiable. Add to II-A (and add the reference; check the citation details before use):

```latex
Conjunctive searchable encryption commonly starts from the least frequent keyword and filters its
postings with the remaining terms~\cite{cash2013oxt}. AMTP applies the same selectivity principle at
partition granularity and makes the pruned answer verifiable: the user checks that no posting component
inside the candidate partitions was withheld.
```

Table I: unchanged.

### 5.4 [C] System Model (III-A)

- CP paragraph: fine.
- DO: "signs insertion or deletion requests" → "signs insertion or deletion requests, each insertion carrying a
  placement group".
- CS: "It prepares updates" → "It prepares updates in batches of at most b operations per epoch"; and the ASPA
  clause as in 1.12.
- DU: as in 1.12.
- Paragraph after the entities. Old: "PAPCs and the Merkle hierarchy authenticate complete postings and
  ciphertext locations within one finalized domain snapshot."

```latex
The Search Tree provides keyword lookup, while PAPCs and the Merkle hierarchy authenticate the postings
a query depends on and the locations of the returned ciphertexts within one finalized domain snapshot.
```

- Table II: use `\rho_w` for the PAPC in every equation; add rows:

```latex
$\mathsf{next}(h_w)$ & Next indexed key after $h_w$ in the IMT chain \\
$g_d$, $G$ & Placement group of document $d$ and number of groups \\
$\mathcal{B}$, $b$ & Batch of operations of one epoch and its maximum size \\
$H_{full}$, $F_Q$ & Query keys sent in full and focus set of $B_Q$ \\
$S_{res}$, $\mathsf{Ver}_Q$ & Partitions of returned files and version list of the other covered partitions \\
```

  and change "M_cov: Union of component postings requiring authentication" to "Union of the component postings
  sent".
- Fig. 2 (Search and Adaptive Merkle Tree): if it draws the IMT as sorted leaves, add the next pointer to the
  leaf label; not checked (figure not readable in the extracted text).

### 5.5 [A/C] Threat Model (III-B)

(a) Adversary abilities: add the two behaviours the new checks exist for.

```latex
It may fabricate, substitute, omit, or duplicate results, select incorrect partitions, withhold posting
components of a pruned query key, misreport partition versions, report false empty results, replay stale
evidence, or combine different epochs.
```

(b) Trusted DO paragraph: the non-membership proofs (IMT and focus evidence) rely on order invariants that only
the validating DO enforces. State it.

```latex
The validating DO maintains complete domain-wide metadata and independently checks the operations of a
batch, affected-state coverage, entry conservation, versions, posting repair, the ordering of the IMT
chain and of the posting-component trees, and preservation of unaffected state.
```

and add after it: "Absence proofs for a key or for a posting component are meaningful only relative to these
validated orderings."

(c) Guarantee bullets: unchanged in meaning. In "Completeness", no change. In "Snapshot consistency", no change.

(d) Leakage sentence: add "placement groups" to the list ("Deterministic keyword equality, posting and result
sizes, placement groups, access and update patterns, …").
