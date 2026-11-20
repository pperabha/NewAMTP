# AMTP paper (32): guide to the results and the code

For deciding what the paper should keep, add or cut. State of 20 Nov 2026.
- **Paper versions:** the 24-page version is AMTP (36) and the 6-page conference draft is double-blind.
- **Code and runs:** every experiment ran on AWS `r7i.4xlarge` at commit `74379b7` (Exp. 1, 2, 5) or `c79b2a0`
  (Exp. 3, 4). The ABS cost table ran at `8ed08b7`. The Sepolia runs are in [`chain/runs/`](../chain/runs/): the
  benchmark at `00888ca` and gas vs D at `ff7dcd5`.

| Look here | For |
|---|---|
| [`baselines/results/paper32/FIGURES.md`](../baselines/results/paper32/FIGURES.md) | **every figure (109)** with its picture, data, fairness note and where AMTP wins or loses (computed, not typed) |
| [`baselines/results/paper32/paper_figures/`](../baselines/results/paper32/paper_figures/) | the PDFs used in the paper (+ `paper_figures.zip`) |
| [`baselines/results/paper32/figures/figure_points.csv`](../baselines/results/paper32/figures/figure_points.csv) | every plotted number (with Q1 / Q3) |
| [`baselines/results/paper32/data/`](../baselines/results/paper32/data/) | the result CSVs of every run, each with a `.manifest.json` (command, commit, machine, settings) |
| [`README.md`](../README.md) | install, test, demo, rebuild the figures, re-run the experiments |

## 1. What each paper version shows

| Experiment | 24 pages (AMTP (36)) | 6 pages (draft) | other figures available |
|---|---|---|---|
| 1. Boolean search | Fig. 3 single-domain search vs kQ; Fig. 4 (A∧B)∨(C∧D) and (A∨B)∧(C∨D) over 4 domains | Fig. 3; Fig. 4 = (A∧B)∨(C∧D) | 35 in total: search vs N, query generation, server, verify, end-to-end; AND / OR shapes; D = 1–32 |
| 2. Proof, verification, tamper | Fig. 5 (a) verify, 1 domain; (b) verify, 4 domains; (c) attack types detected | Fig. 5 = (a); tamper as Table III | 39 in total: clustered / dispersed / partition-spread layouts (proof generation, verify, proof size), detection and verify time per attack |
| 3. Dynamic updates | text only | text only | 10: update time, per request, throughput vs b and vs N; time breakdown (`e3_b_breakdown_insert` on hold) |
| 4. Skewed growth (ablation) | Fig. 6 update time of every batch, skew 0.95 | Fig. 6 | 13: update vs skew (insert, delete), largest partition, query server / verify / proof size, splits + merges, other skews |
| 5. Multi-domain | Fig. 7 end-to-end vs D | text only | 12: query parts vs D, update isolation, root anchoring time and gas (local EVM), Sepolia gas and time |

Two extra figures wait for a decision: `e2_layouts_proof_kb` (proof size, clustered vs dispersed: the
(32) Exp. 2 question) and `e3_b_breakdown_insert` (where update time goes).

## 2. Results in one page

Every number is in `figure_points.csv`. Times are per query unless stated otherwise.

**Experiment 1 (N = 10⁵ per domain).**

Single-domain conjunctive server search:
- vs SE-COLLAB: AMTP 4.4–23× faster.
- vs Du et al.: AMTP at least 11× faster.
- vs Chen et al.:
  - AMTP 10–21% faster from kQ = 2.
  - Chen is faster at kQ = 1 (0.0083 vs 0.0088 ms).
  - Chen is faster up to N = 2.5 × 10⁴.

From N = 10⁴ to 1.25 × 10⁵, AMTP's search time rises by 18%, Chen's by 72% and SE-COLLAB's by 4.3×.

End to end (0.41–1.75 ms):
- AMTP needs 1.1–5.3× less time than Chen and 5.3–22× less than SE-COLLAB.
- **Du et al. is 22–31% faster for kQ ≥ 2 and at every N.**
- Chen is faster at N = 10⁴.

**AMTP's query generation is slower than Chen's and Du's.**

Over 4 domains (only SE-COLLAB supports Boolean expressions), AMTP is faster:
- 2.8–5.1× for (A∧B)∨(C∧D);
- 1.8–7.8× for (A∨B)∧(C∨D);
- 2.4–4.9× for AND.
- **A pure OR is faster only with 2 keywords.**

**The conjunctions return a median of 1 file for kQ ≥ 2, and 6 for kQ = 1** (neither version says this).

**Experiment 2.**

Proof cost follows the partitions of the returned files. At rQ = 1,000, clustered (39 partitions) vs dispersed (880):
- proof generation 0.71 vs 5.7 ms;
- verification 16.7 vs 32.5 ms;
- proof size 55 vs 320 KB.

Proof size vs SE-COLLAB: AMTP's proof is smaller than SE-COLLAB's from rQ = 100 in every layout.

Proof generation vs SE-COLLAB:
- AMTP is faster for the clustered layout.
- **AMTP is slower for the dispersed layout from rQ = 100.**

**DU verification is slower than SE-COLLAB's from rQ = 100 and slower than Chen's everywhere.** It is faster than Du's
everywhere:

| scheme | verification, 1 domain, real keywords (ms) |
|---|---|
| AMTP | 0.52–69.8 |
| SE-COLLAB | 1.04–28.7 |
| Chen | 0.28–7.7 |
| Du | 0.75–179 |

Tamper detection (t = 5–1,000 tampered files):
- AMTP detects all 4 attacks in every run and accepts every honest response.
- Du misses injected files.
- SE-COLLAB misses hidden and injected files.
- Chen covers 2 of the 4 attacks and detects both.

**Experiment 3 (N = 10⁵).**

**Updates are 25–230× slower per request than Chen's:**
- AMTP: 287 ms as its own epoch and 35 ms in batches of 1,000, which is 3.5–28.5 requests/s.
- Chen: 1.2–1.5 ms, which is 700–800 requests/s.

ABS signing plus 2 verifications takes:
- 2.1 s of the 5.1 s protocol time at b = 100 (posting repair is 0.75 s and auth-tree maintenance 0.29 s);
- 21.2 s of 34.9 s at b = 1,000.

Without ABS, AMTP would still be about 10–25× slower than Chen at b = 100–1,000.

**Experiment 4 (25,000 documents + 250 batches of 100, then 65% of the hot group deleted; index level).**

Largest partition:
- AMTP keeps every partition at ≤ 64 entries.
- Static-MT's largest partition reaches 2,492–8,206 entries.
- Global-MT(v) is one tree of 33,000–48,000 entries.

Insertion batches cost 443–694 ms, which is 3.6–6.9× less than Static-MT and 9.9–15.8× less than Global-MT(v).

Deletions: Static-MT is slightly faster at skew 0. AMTP is up to 2.2× faster as the skew grows.

Splits and merges take 1–2% of the update time.

**The query side is where AMTP pays:**
- verification is 14–16% slower than Static-MT's and about 1.8× Global-MT(v)'s;
- proofs are 6% and 23–26% larger.

Through the full protocol, the same insertion batches take 3.7–4.2 s, of which about half is ABS.

**Experiment 5 (queried domain fixed at 5,000 documents, D = 1–32).**

End to end, AMTP takes 1.35–1.40 ms against SE-COLLAB's 9.38–9.40 ms, flat in D.

Update isolation:
- An update never changed another domain's root.
- The full update grows from 238 to 295 ms, because the contract recomputes the Global Root.

Sepolia: a root update costs 86.7k gas at D = 1 and about +16k per doubling of D, and takes 11–12 s to be mined.

## 3. Where the code differs from paper (32) as first written

Each item was decided by the team. Numbers such as #43 refer to the decision issues in the team's working
repository. A search of the text of AMTP (36) finds each one stated.

| Item | What the code does | Why |
|---|---|---|
| Root-transition signature σ_root | ECDSA over secp256k1, verified by the RootAnchor contract | an ABS pairing cannot be verified on-chain at practical gas |
| Request signatures σ_d = σ_op | real ABS (Maji–Prabhakaran–Rosulek) on SS512, policy `domain:Di ∧ role:owner`, verified by the CS and by the validating DO | decisions #43, #54 |
| Query speed-ups (always on) | AND pruning with greedy H_full, result-only partition proofs, Search Tree leaf by partition (Aux_i(h_w)) | same accept decision, much smaller proofs (stated in the construction of (36)) |
| Placement | fill-first: the fullest partition of the group below θ_max | decided 16 Nov (insert cost) |
| Epoch | one batch of ≤ b operations (b = 1 is (32) as written) | #50: one operation per epoch makes Exp. 4 infeasible |
| IMT | indexed Merkle tree with next pointers (absence proofs) | #51 |
| AAD and update request | `aad_d = Encode(i, id_d)`; `U_d` without the placement hint g_d (g_d is a CS-side hint outside the signature) | #48, #49: follow (32) |
| Timing network | protocol times measured against the same contract on a local EVM; Sepolia latency and gas measured apart | #42 |
| Dataset | the existing arXiv v4 only: 4 domains × 125,000 (+12,500 insertion pool); Exp. 4 starts at 25,000 | advisor (no 10⁶, no new data) |
| Statistics | mean of 10 runs after 3 warm-up runs; with several queries per point, the median over queries with IQR bars | #46, #66 |
| Exp. 4 | index level (AMTP / Static-MT / Global-MT(v)), 10 runs per point; the full-protocol AMTP run is reported in the text | #44, #45 |

## 4. What a reviewer is likely to ask

| # | Point | 24 pages | 6 pages |
|---|---|---|---|
| 1 | No forward / backward privacy: deterministic keyword tokens, and an insertion sends all tokens of a document (Chen et al. has both properties) | stated ("AMTP does not claim forward or backward search privacy") | not stated |
| 2 | Exp. 1 conjunctions are very selective (median 1 returned file for kQ ≥ 2) | not stated | not stated |
| 3 | The headline metric (server search) excludes proof generation; end to end, Du is 22–31% faster | stated | stated |
| 4 | Verification is slower than SE-COLLAB's from rQ = 100 and slower than Chen's everywhere | stated | stated |
| 5 | Updates are 25–230× slower than Chen's, and ABS is 41–61% of the protocol time: why ABS and not a plain signature (Ed25519: 0.03 / 0.09 ms)? | numbers stated, no reason given | numbers stated, no reason given |
| 6 | "Finalized" snapshot: 11.0 s is block inclusion, while finality on Sepolia is about 17 minutes (median 1,015 s) | stated | only 11.0 s |
| 7 | "Indexing invariant" | defined (Prop. 1) | used, not defined |
| 8 | The tamper table has 4 generic attacks, while the threat model lists AMTP-specific ones (the test suite covers them, Section 5) | not mentioned | not mentioned |
| 9 | Related work lacks classic verifiable SSE (Kurosawa–Ohtaki; Bost et al.), authenticated set operations (Papamanthou et al.) and vChain | not cited | not cited |
| 10 | Exp. 5: a flat query cost in D is expected, because each query is domain-bound; the informative part is isolation and the cost of root maintenance | partly | partly |
| 11 | Scale (10⁵ per domain), a Python prototype, baselines re-implemented by the authors | stated; no code link | stated; no code link (double-blind: needs an anonymous link) |
| 12 | 6 of the 23 references (6-page draft) come from one group | n/a | kept (owner's decision) |

Bibliographic details for row 9 must be checked before citing.

## 5. Security tests (functional, not timed)

These run in `amtp_code/tests/` on a small synthetic world. At `8ed08b7`: 111 passed, 1 skipped in about 25 s.

```bash
cd amtp_code
../.venv/bin/python -m pytest -q tests/test_adversary.py tests/test_and_prune.py tests/test_update_protocol.py \
    tests/test_abort_update.py tests/test_chain_anchor.py tests/test_imt_indexed.py
```

| Attack by the server | Rejected by | Test |
|---|---|---|
| modify a returned file | `b_ct` | `test_adversary.py` (`tamper_ct`) |
| hide a matching file / add a non-matching one | `b_comp` | `drop_result`, `extra_result` |
| remove an entry from a posting list | `b_papc` | `hide_posting` |
| claim that a keyword does not exist | `b_idx` | `false_absent`; `test_imt_indexed.py` |
| forge a partition's content | `b_part` | `forge_partition` |
| answer from an old epoch (rollback) | `b_anchor` | `stale` |
| replay an earlier response | `b_ctx` | `replay` |
| withhold or relabel a component of a pruned key, drop a neighbour, change a component, wrong tree size, no key sent in full | `b_papc` (focus evidence) | `test_and_prune.py` |
| tamper with an update proposal | DO validation | `test_update_protocol.py`, `test_abort_update.py` |
| replay an update request (nonce) | DO validation | `test_update_protocol.py` |
| skip an epoch, wrong predecessor, another domain's signer, signature on another root, malleable signature | RootAnchor contract | `test_chain_anchor.py` |

Every conjunct of Accept_Q has an attack that fails exactly there.

## 6. Paper ↔ code

| Paper | Code (`amtp_code/amtp/`) |
|---|---|
| Phase 1: setup, document encryption, CP-ABE, ABS, keyword extraction and protection | `owner.py`, `nlp.py`, `core/crypto.py`, `core/hashing.py`, `core/cpabe.py`, `core/abs.py` |
| Phase 2: partitions, Search Tree, postings, PAPC, IMT, update protocol | `engine.py`, `index.py`, `bptree.py`, `cuckoo.py`, `update.py`, `server.py` |
| DO validation and Root Anchor | `validator.py`, `chain_anchor.py` (client of [`chain/RootAnchor.sol`](../chain/RootAnchor.sol)); `anchor.py` (in-process anchor for unit tests) |
| Phase 3: split / merge, posting repair | `engine.py`, `variants.py` (AMTP, Static-MT, Global-MT policies) |
| Phase 4: search, focus set, ASPA | `server.py`, `core/boolean.py`, `core/merkle.py`, `dht.py` |
| Phase 5: verification and decryption | `user.py` |
| Malicious server (tests, demo) | `adversary.py` |

Other code:
- **Benchmarks:** `amtp_code/bench/` (`experiments.py`, `ablation.py`, `abs_bench.py`) and `amtp_code/bench_split/`
  (search-only timers).
- **Baselines:** `baselines/chen_et_al_sim.py`, `du_et_al_sim.py`, `se_collab_sim.py`. Their notes are in
  [`docs/CHEN_NOTES.md`](CHEN_NOTES.md), [`docs/DU_NOTES.md`](DU_NOTES.md) and
  [`docs/SE_COLLAB_NOTES.md`](SE_COLLAB_NOTES.md). The size rule shared by every scheme is in
  `baselines/wire_sizes.py`, and the dataset loader in `baselines/amtp_dataset.py`.
- **Figures:** `baselines/plot_p32.py` draws them and `baselines/figure_catalog.py` writes `FIGURES.md`.

How the comparison is kept fair:
- **Same inputs and machine.** Every scheme uses the same documents, keywords, queries, N and machine, in the same
  step.
- **Search time.** Server search time excludes proof generation and file retrieval for every scheme:
  - Chen et al. is measured in its best case, after its update chain has collapsed.
  - Du et al. is measured on its slowest cloud, with a warm cache.
- **End to end.** End to end is query generation + server + DU verification. It excludes:
  - record decryption, for every scheme;
  - AMTP's root read, which is reported apart.
