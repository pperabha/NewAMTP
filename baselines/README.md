# Baselines

Python simulations of the baseline schemes compared against AMTP in Section V (Table IV),
each re-implemented from its paper.

| File | Scheme | Compared in |
|---|---|---|
| `du_et_al_sim.py` | Du et al. [7], *Secure and Verifiable Keyword Search in Multiple Clouds*, IEEE Systems Journal 2022 | Table IV, Exp. 1 (AND only), Exp. 2 (reference); multi-cloud sensitivity (not Exp. 5) |
| `se_collab_sim.py` | SE-COLLAB [37], *Fine-Grained and Efficiently Verifiable SE With Boolean Multi-Keyword Search for Collaborative IIoT*, IEEE Access 2025 | Table IV, Exp. 1, Exp. 2, Exp. 5 |
| `chen_et_al_sim.py` | Chen et al. [40], *Verifiable Multi-User Dynamic SSE With Forward and Backward Privacy Feasible for Cloud Storage*, IEEE TIFS 2026 | Table IV, Exp. 1 (AND only), Exp. 2, Exp. 3 |
| `amtp_dataset.py` | Shared loader for the AMTP dataset (`dataset-v4`): document sampling, insert pool, query generation, the v4 experiment files, ground truth | all experiments |

## Dataset (shared by every scheme)
Run `python3 datasets/arxiv/unpack.py` once after `git pull` (rebuilds `data/amtp_file_db_v4/` from the parts in git;
or pass `--data <path>`, or set `AMTP_DATA`). Check it with `python3 baselines/amtp_dataset.py`.

- dataset-v4: arXiv, 4 domains: D1 = cs, D2 = math, D3 = astro-hep, D4 = condmat-quant, with 125,000 initial files
  and 12,500 insert-pool files per domain (seed 42). Details: `datasets/arxiv/data_v4/README.txt`.
- Keywords W(d) are pre-extracted once with AMTP's Phase 1 procedure (`amtp_code/amtp/nlp.py`: RAKE, κ = 20 per file,
  idempotent Norm) in `documents.csv`. Every scheme, AMTP included, uses them as-is and never re-extracts;
  AMTP's extraction time is reported separately (`amtp_code/bench/extraction.py`).
- `sample(N)` = the first N/4 files of each domain in `doc_id` order (no randomness), so every scheme gets the same
  N documents. N ≤ 500,000. `domain_docs(d, n)` = the first n files of one domain (the v4 single-domain database).

## Advisor's experiment plan (dataset-v4)
The workload files in `datasets/arxiv/data_v4/` (built by `datasets/arxiv/build_v4.py`) fix every query, keyword and
tampered file, and every scheme reads them through `amtp_dataset.py`. Each suite checks every result against the
exact counts in those files and stops on a mismatch. Run everything on one machine with `bash scripts/aws_run_all.sh`.

| Suite (`<suite>` command) | Plan item | Workload file | Schemes | Result CSV |
|---|---|---|---|---|
| `search1` | Search 1.1 / 1.2: single domain, x = kQ (1–20) or files per domain (10k–125k) | `queries_search_single.jsonl` | all 4 | `<scheme>_search_single.csv` |
| `verify1` | Verify 1.1: single domain, x = result size (~10 / 100 / 1,000 / 10,000), 100k files | `verify_keywords.csv` (single_domain) | all 4 | `<scheme>_verify_single.csv` |
| `tamper` | Verify 1.2: server modifies, hides, injects or sends an old version of t files (~2,000 results, 100k files; t ≤ half of them) | `tamper_sets.jsonl` (+ `inject_order`) | all 4 | `<scheme>_tamper_detection.csv` |
| `xsearch` | Search 2.1: AND / OR / AND_of_OR / OR_of_AND over the 4 domains, 100k files each | `queries_boolean_multi.jsonl` | AMTP, SE-COLLAB | `<scheme>_search_multi.csv` |
| `xverify` | Verify 2.1: keywords found in every domain, x = total result size | `verify_keywords.csv` (multi_domain) | AMTP, SE-COLLAB | `<scheme>_verify_multi.csv` |
| `xdomains` | Search 2.2 / Verify 2.2: the same 400k files as D = 1, 2, 4, 8, 16, 32 domains | `domain_groups.csv` + boolean queries | AMTP, SE-COLLAB | `<scheme>_domains_scaling.csv` |

- Cross-domain search follows the paper (System model): the user sends one domain-bound query per domain and verifies
  each response against that domain's own root; times and sizes are summed over the domains. Every AMTP domain has
  its own keys (K_s, K_a). In SE-COLLAB every domain is one data owner and the user passes each owner's policy; as in
  its paper (Phase 4 Step 1, Table 4) one trapdoor, signature, NIZK, proxy check and PRE transform serve the whole
  query, and only the index search, Merkle proof and Merkle check repeat per owner (`[ASSUMPTION]` 12).
- Tampering (`tamper`), t = `tamper_counts` of the file, applied to the same files in every scheme:
  `modify` (change returned file bytes), `hide` (leave matching files out), `inject` (add files that do not match,
  the first t of `amtp_dataset.inject_order`), `old_version` (an older, validly encrypted version of the file,
  `OLD_VERSION_SUFFIX` appended). Columns: `detected_runs` / `runs` (runs where verification rejected),
  `verify_total_ms` (normal verification, stops at the first failed check), `localized` (files the user can name
  as wrong). AMTP also reports `full_check_ms` (check every file and name the wrong ones) and `failed_check`.
  SE-COLLAB writes `check_mode` = early (multiproof, cannot name files) and full (one Merkle path per file).
  Du: cloud 0 cheats, the others are honest; `result_ok_runs` counts runs whose final filtered result is correct.
  Chen returns only a result bitmap, so `modify` / `old_version` are N/A and its aggregate proof names no file.
- Split / merge (`bench.ablation`): `--fresh-source initial` inserts the next initial files after the first `--n`
  (100k start + 100k inserts is possible), `--hot-delete-frac 0.65` then deletes that share of the hot group's files
  so partitions merge, and `--query-every k` writes the layout (max / min / mean partition size) and the query cost
  every k batches (`batch` column) for AMTP, Static-MT and Global-MT. `scripts/aws_run_all.sh splitmerge` runs
  θ_max = 64 / 128 / 256 (θ_min = θ_max / 4).
- The older suites below (`exp1`, `exp2`, `exp5`) still run on dataset-v4 with their shared files.

- `make_queries(docs, kQs, seed=42)` builds the 4 Exp. 1 shapes from one seeded source document:
  `single`, `conjunctive` (A AND B …), `disjunctive` (A OR B …), `or_and_or` = (A OR B) AND (C OR D),
  `and_or_and` = (A AND B) OR (C AND D). Files have ≤ 10 keywords, so AND queries with kQ = 16 are always empty.
- Keywords are RAKE phrases and may contain spaces. Queries write them without quotes
  (`general method AND possible description`); every parser treats the words between operators as one keyword.
- `read_bytes(doc)` returns the file's text for schemes that encrypt the real content (SE-COLLAB; Du reads the files itself).
- The shared Exp. 1 workload is `results/exp1_queries.json` (`N, kQ, q, shape, query, terms, domain, source_doc,
  query_set`): **20 queries per kQ** (`q` = 0..19), each in every shape, and **the same queries at every N**, so a
  line over N shows the effect of N alone. The queries are drawn from the N = 10,000 documents; `sample(N)` takes the
  first files of each domain, so those documents are in every larger N. Every scheme's `exp1` replays the file by
  default and never overwrites it. Write it with `python3 amtp_dataset.py queries` (`--per-kq`, `--sizes`, `--kq`,
  `--seed`). Files have at most 10 keywords, so AND queries with kQ = 16 always return nothing (an empty-result case).
- `plot_results.py` plots, per point, the median over its queries of their per-query medians; the error bar spans the
  fastest to the slowest query. It also draws `compare_exp1_response_vs_N` (bytes returned to the DU per query,
  `response_bytes`, which for Chen includes the N-bit result bitmaps) and `amtp_exp1_time_vs_pQ` (one point per query:
  AMTP's time follows the number of postings its proof opens, pQ).
- Exp. 3 inserts real documents from `insert_pool()` (round-robin over domains).
- **Exp. 2 layouts** are shared too: `results/exp2_layouts.json` lists, for N = 200,000 and r_Q = 10 / 100 / 1000 / 5000,
  which documents get the marker keyword (`clu<r>`, `dis<r>`, `par<r>`), so every scheme embeds it in the same files:
  `clustered` = r consecutive files from N/3, `dispersed` = every N/r-th file (document order), and
  `partition_spread` = one file per AMTP partition, round robin (AMTP's worst case; it needs AMTP's placement, so
  `python -m bench.experiments exp2-layouts` in `amtp_code/` writes the whole file).
- **Exp. 5 workload** is `results/exp5_workload.json` (`python3 amtp_dataset.py exp5`): 32 domains of 5,000 files
  (`groups[k]` = the k-th slice of `sample(160,000)`, so D = 1–8 are all cs), the target domain `groups[0]` at every
  D, 5 queries per k_Q = 1 / 2 / 4 / 8 drawn from `groups[0]` in every shape (k_Q = 16 left out: always empty), and
  the 33 insert-pool files (warm-up + reps) added to the target domain. Only schemes with domains take part: AMTP
  (one domain each, one anchor) and SE-COLLAB (one data owner each, one proxy and ledger). Chen and Du have a single
  data owner and no domains and are not in Exp. 5.

## AMTP in the same format
`amtp_code/bench/experiments.py` runs AMTP itself (Engine, CloudServer + ASPA, DataUser 7 checks, RootAnchor) on the
same documents and queries and writes `results/amtp/amtp_<suite>.csv` with the same columns, so `plot_results.py`
can put AMTP next to the baselines. From `amtp_code/`:
```
python -m bench.experiments exp1                # replay results/exp1_queries.json (N = 10k..200k)
python -m bench.experiments exp2-layouts       # write results/exp2_layouts.json (N = 200k, needs AMTP's placement)
python -m bench.experiments exp2                # every layout of results/exp2_layouts.json
python -m bench.experiments exp3                # insert/delete batches; see docs/IMT_UPDATE_COST.md first
python -m bench.experiments exp5                # replay results/exp5_workload.json: query + one-domain update
```
Exp. 1–3 put all N documents in one domain (the collection the baselines search); Exp. 5 varies the number of
domains. Every query must pass the 7 checks and equal the plaintext ground truth. `end_to_end` excludes
decrypting the returned files (`du_decrypt`).

## Shared conventions (all baselines)
Every baseline is one file with `demo` (and `selftest` for SE-COLLAB / Chen; no dataset needed) plus one command per AMTP
experiment it supports:

| | `exp1` | `exp2` | `exp3` | `exp5` | other |
|---|---|---|---|---|---|
| Du [7] | AND only | reference | — | — (no domains) | `clouds` |
| SE-COLLAB [37] | ✓ all shapes | ✓ | — | ✓ (update N/A) | `paper`, `revocation` |
| Chen [40] | AND only | ✓ | ✓ | — (no domains) | — |

**Same options everywhere:** `--data`, `--domains`, `--seed 42`, `--reps 30`, `--warmup 3`, `--sizes`, `--kq`,
`--queries-per-kq`, `--queries`, `--exp5-workload`, `--out` (default `baselines/results/<scheme>/`).
Every scheme (AMTP, Chen, Du, SE-COLLAB) replays `results/exp1_queries.json` by default and never overwrites it;
`--queries <file>` replays another file.

**Run manifest:** next to every result CSV the writer saves `<csv>.manifest.json` (`amtp_dataset.write_manifest`):
the command line, git commit (and whether the tree had uncommitted changes), time, dataset tag and the machine
read from the system (CPU, cores, RAM, OS, Python).

**Output:** one folder per paper, one CSV per suite: `results/<scheme>/<scheme>_<suite>.csv` with `<scheme>` = `du`,
`secollab`, `chen` (e.g. `results/secollab/secollab_exp1_boolean_scalability.csv`). The shared
`results/exp1_queries.json` stays at the top level. Layout: [`results/README.md`](results/README.md). Each timing has three columns: `<metric>_ms` (mean),
`<metric>_ms_median`, `<metric>_ms_std`, over `--reps` measured runs after `--warmup` unrecorded runs with GC off.

**End-to-end (all schemes):** `end_to_end_ms` is the time from query generation until the data user holds the
verified result set: query generation + server search/proof (slowest cloud for Du) + any client step needed to learn
which documents match + verification. Recovering the returned files afterwards (AES / CP-ABE / RS decode) is reported
separately in `du_decrypt_ms` (AMTP, Du) and is not part of `end_to_end_ms`. Exception: Chen returns no files, and its
`du_decrypt_ms` is the bitmap decryption + AND that yields the result ids, so it is part of Chen's `end_to_end_ms`.
SE-COLLAB does not measure file decryption. Network time is never included.

**Common Exp. 1 columns:** `N, kQ, shape, domain, status, rQ, response_bytes`, timings `query_gen`, `server_total`,
`verify_total`, `end_to_end` (`pQ` in Chen and SE-COLLAB). Scheme-specific columns follow (Chen: `du_decrypt`, op counts;
Du: `server_sum`, `du_decrypt`, `bloom_fp`; SE-COLLAB: `trapdoor`, `search_core`, `merkle_verify`, …). Shapes a scheme cannot answer are rows with
`status=N/A`. Every supported query is checked against the plaintext ground truth during the run.

**Code comments:** fixed paper bugs are tagged `[FIX]`, choices for details the paper leaves out are tagged
`[ASSUMPTION]`. Each file header lists all of them.

## Requirements
```
pip install numpy cryptography          # Du [7], Chen [40]
```
SE-COLLAB additionally needs PyCryptodome and Charm-Crypto (same libraries as its paper).
Charm needs the GMP and PBC C libraries first:
```
# macOS
brew install gmp pbc                     # if pbc is not found, build it from source as below
# Ubuntu
sudo apt-get install -y libgmp-dev libssl-dev flex bison autoconf automake libtool autoconf-archive
git clone https://github.com/blynn/pbc.git && cd pbc && ./setup && ./configure && make && sudo make install && sudo ldconfig
# then
pip install numpy pycryptodome charm-crypto-framework
```
Tested on macOS with Python 3.12 (`brew install gmp pbc`, then pip as above). On macOS, if Charm cannot find GMP/PBC: `export CFLAGS="-I$(brew --prefix)/include" LDFLAGS="-L$(brew --prefix)/lib"` and reinstall.

## Figures
```
pip install matplotlib
python3 plot_results.py secollab              # results/secollab/figures/secollab_*.png / .pdf
python3 plot_results.py amtp chen du secollab # + results/compare/: every scheme of an experiment in one graph
python3 old/plot_v4.py                        # (old) dataset-v4 suites + split / merge -> results/figures_v4/
```
**dataset-v4 figures (`old/plot_v4.py`, replaced by `plot_paper.py`)**, from the CSVs of `scripts/aws_run_all.sh` (`--results <dir>` if they were
copied elsewhere). One folder per item of the advisor's plan, every title starts with that item:
`Search_1.1_single_domain_vary_keywords/` (time, verification and response size vs k_Q at `--fix` files),
`Search_1.2_single_domain_vary_files/` (vs files at k_Q = `--kq`), `Verify_1.1_single_domain_vary_results/`,
`Verify_1.2_single_domain_vary_tampered/` (`<kind>_vs_t` per tamper kind, `detection_matrix`: detected runs and files
named per scheme, `tamper_summary.csv` / `.md`), `Search_2.1_multi_domain_boolean/` (one figure per shape),
`Verify_2.1_multi_domain_vary_results/`, `Search_2.2_` / `Verify_2.2_multi_domain_vary_domains/` (vs D at
k_Q = `--xkq`) and `Split_merge/` (largest / mean partition, verification and update cost per batch for each θ, then
the same vs θ). Each point = median over the queries of that point; bars = 25th–75th percentile across queries.
Every plotted number is also written to `figure_points.csv`.
**Combined figures (`results/compare/`)**, one fixed colour + marker per scheme in every figure (AMTP blue ●,
Chen orange ■, Du green ▲, SE-COLLAB yellow ◆); a variant of a scheme (SE-COLLAB multiproof, deletes, AMTP's anchor
share) is the same colour, dashed, marker ×. Error bars: fastest–slowest query (Exp. 1, 5) or ±1 std over runs.
Schemes that cannot take part are named in the note under the figure (N/A). Sizes use 1 KB = 1000 B.

| Exp. | Figures |
|---|---|
| 1 | `compare_exp1_and_vs_N` (all 4), `compare_exp1_or_vs_N` (AMTP, SE-COLLAB), `compare_exp1_response_vs_N` |
| 2 | `compare_exp2_verify_vs_rQ_{clustered,dispersed,partition_spread}` (AMTP, Chen, SE-COLLAB per-path + multiproof), `compare_exp2_response_vs_rQ` |
| 3 | `compare_exp3_update_one_vs_N`, `compare_exp3_per_file_vs_batch` (AMTP, Chen insert + delete) |
| 4 | `compare_exp4*_update_vs_skew`, `compare_exp4*_verify_vs_skew` (AMTP vs Static-MT / Global-MT / Global-MT(v)) |
| 5 | `compare_exp5_query_vs_domains` (AMTP, SE-COLLAB), `compare_exp5_update_vs_domains` (AMTP; SE-COLLAB N/A) |

Same style for every scheme (one palette in `baselines/plot_results.py`): median of `--reps` runs, error bars ±1 std,
PNG for slides and PDF for the paper. Figures: `exp1_search_vs_N` (AND, one line per k_Q), `exp1_shapes_vs_N`
(all Boolean shapes at k_Q = 4, schemes with OR support), `exp1_breakdown_maxN` (stacked phases at the largest N),
`exp2_verify_vs_rQ` (clustered / dispersed), `exp3_insert_vs_batch` (insert time per file, one line per N) and, for
AMTP, `amtp_<folder>_update_vs_skew` / `_verify_vs_skew` for every Exp. 4 folder `results/amtp/exp4*/` written by
`python -m bench.ablation --out ../baselines/results/amtp/exp4`. The reported run is `exp4_n200k/`:
`python -m bench.ablation --source arxiv --n 200000 --theta-max 64 --theta-min 16 --batches 20 --batch-size 100
--runs 3 --global-versioned --out ../baselines/results/amtp/exp4_n200k` (about 5.5 h on the test machine, mostly
Global-MT(v)); `exp4_n20k/` is the earlier single run at N = 20,000. Chen's figures in `results/chen/figures/` without the `chen_` prefix were made before this
script and are kept as they are.

## Du et al. [7]
Paper-vs-code check: [`docs/DU_NOTES.md`](../docs/DU_NOTES.md).
Single file, needs `numpy` + `cryptography`. Reads the shared dataset through `amtp_dataset.py` (keywords W(d) from
`documents.csv`, file contents from `files/*.txt`) and **replays `results/exp1_queries.json` by default**.
```
python3 du_et_al_sim.py demo                                   # correctness + malicious-cloud detection (no dataset needed)
python3 du_et_al_sim.py exp1                                   # replay results/exp1_queries.json (N = 10k..200k)
python3 du_et_al_sim.py exp2                                   # replay results/exp2_layouts.json (N = 200k), reference
python3 du_et_al_sim.py clouds --n 10000 --clouds 4 8 16 32    # Du-only multi-cloud sensitivity (not Exp. 5)
```
- Same flags and output format as Chen: `--reps 30 --warmup 3`, results in `results/du/du_<suite>.csv`
  (`du_exp1_boolean_scalability.csv`, `du_clouds_sensitivity.csv`) as `<metric>_ms`, `_ms_median`, `_ms_std`.
- Columns: `query_gen_ms`, `server_total_ms` (slowest cloud, clouds search in parallel), `server_sum_ms` (total work of
  all clouds = O(n_c·r·v_Q)), `verify_total_ms`, `du_decrypt_ms` (RS decode + iterative decrypt of every result,
  not part of the end-to-end time), `end_to_end_ms` (query_gen + server_total + verify_total), `rQ`, `gt`,
  `bloom_fp`, `token_bytes`, `response_bytes`, `cs_storage_bytes`, `setup_ms`,
  plus operation counts (`hash_qgen`, `hash_search`, `visited`, `hmac_verify`, `hash_verify`, `dec_verify`) for Table IV.
- Supports conjunctive (AND) queries only; OR / nested shapes are written as rows with `status=N/A`.
- Exp. 2 (reference, `du_exp2_selective_proof.csv`): Du has no Merkle tree or proof shared by several files; the DU
  checks each result with HMAC of its encoded ID and compares the clouds' answers, so verification is O(n_c·|R|)
  whatever the layout. Bloom-filter false positives are allowed and counted in `bloom_fp` (`rQ` = files that
  carry the marker, `rQ_returned` = files returned).
- Dynamic update is not supported (`N/A` in Table IV / Exp. 3).
- Multi-cloud sensitivity (`du_clouds_sensitivity.csv`, N = 10,000, n_c = 4 / 8 / 16 / 32, the AND queries of
  `exp1_queries.json` at N = 10,000): `python3 plot_results.py du` draws `du_clouds_cost` (latency, total cloud work,
  verification vs n_c at k_Q = 4) and `du_clouds_verify` (DU verification vs n_c per k_Q). It varies the number of
  clouds holding one collection, not the number of domains, so it is not Exp. 5 and is not drawn next to AMTP.
- Du is multi-cloud, not multi-domain: the N documents of all domains form one collection whose slices are spread
  over n_c clouds (default 5, t = 3). The `domain` column only records where the query came from.
- Every result is checked against the plaintext ground truth: nothing may be missing; extra files from Bloom-filter
  false positives are allowed (as in the paper) and counted in `bloom_fp`.
- Paper bugs fixed and unspecified details are marked `[FIX]` / `[ASSUMPTION]` in the code (9 items, listed in the
  file header).

## SE-COLLAB [37]
Single file, Charm-Crypto BSW07 + PyCryptodome (same stack as the paper).
Paper-vs-code check (what matches, what was interpreted, how to read the numbers): [`docs/SE_COLLAB_NOTES.md`](../docs/SE_COLLAB_NOTES.md).
```
python3 se_collab_sim.py demo                                  # Phase 1-8 walkthrough + tamper / omission attacks
python3 se_collab_sim.py selftest                              # 18 tests incl. tamper / omission / revocation / phrase keywords
python3 se_collab_sim.py paper                                 # reproduce SE-COLLAB Figs. 2-6 (sanity check)
python3 se_collab_sim.py exp1                                  # replay results/exp1_queries.json (N = 10k..200k)
python3 se_collab_sim.py exp2                                  # replay results/exp2_layouts.json (N = 200k)
python3 se_collab_sim.py exp5                                  # replay results/exp5_workload.json (1 owner = 1 domain)
python3 se_collab_sim.py revocation                            # Phase-8 cost vs affected users
```
- Supports AND / OR / NOT, so every Exp. 1 shape is measured.
- Dynamic update is not specified in the paper (`N/A` for Exp. 3 and the Exp. 5 update rows). Exp. 5 uses the
  paper's multi-owner model: one data owner per domain, each anchoring its own root on the shared ledger; the run
  checks that adding owners leaves the earlier owners' roots unchanged.
- Phase-6 verification checks returned ciphertexts only, not posting completeness, so
  omitted results go undetected (selftest `t_omission_not_detected`).
- `server_total_ms` = proxy admission + PRE transform + search + proof. Extra timings: `trapdoor` (Fig. 3),
  `search_core` (Figs. 4/5), `merkle_verify` (Fig. 6), `result_proof_verify`, `admission`, `transform`, `proof_gen`.
- Exp. 2 has no partitions: `layout` = the three layouts of `results/exp2_layouts.json`, `proof_mode` = `paths` (paper) or `multi`.
- `demo`, `selftest`, `paper` and `revocation` use a small synthetic corpus and do not need the dataset.
- Paper gaps filled by the code (pairing group, trapdoor C3, ZKP equations, phrase keywords, …) are listed in the
  file header as `[FIX]` / `[ASSUMPTION]`.

## Chen et al. [40]
Paper-vs-code check: [`docs/CHEN_NOTES.md`](../docs/CHEN_NOTES.md).
Single file, symmetric primitives only (HMAC-SHA256/512, SHA-256, SHAKE-256, AES-256-GCM, λ = 128).
Reads the shared dataset through `amtp_dataset.py`. Needs only `cryptography`.
```
python3 chen_et_al_sim.py demo                                 # step-by-step + malicious-CS detection
python3 chen_et_al_sim.py selftest                             # 12 checks incl. omission / dropped entry / forged proof
python3 chen_et_al_sim.py exp1                                 # replay results/exp1_queries.json (N = 10k..200k)
python3 chen_et_al_sim.py exp2                                 # replay results/exp2_layouts.json (N = 200k)
python3 chen_et_al_sim.py exp3 --sizes 10000 50000 100000 200000 --batches 1 10 100 1000 --users 1
```
- Supports conjunctive (AND) queries only. OR / nested shapes are written as rows with `status=N/A`.
- Exp. 1 checks every result against the plaintext ground truth. Columns: `query_gen_ms`, `server_total_ms`,
  `du_decrypt_ms`, `verify_total_ms`, `end_to_end_ms`, `rQ`, `pQ`, `proof_bytes`, `token_bytes`, `response_bytes`,
  plus operation counts (`prf_qgen`, `hash_search`, `add_search`, `xor_search`, `prf_verify`, ...) for Table IV.
- **Index size.** [40] stores one γ = N-bit ciphertext per distinct keyword. With this dataset the full index is
  0.10 GB at N = 10k, 2.20 GB at 50k, 8.29 GB at 100k and 32.29 GB at 200k with dataset-v3 (distinct keywords × N
  bits, `cs_storage_bytes` of the Exp. 1 run; built at 10k and 50k, computed only at 100k and 200k).
  `--scope auto` (the default) builds the full index when it fits in `--max-edb-gb` (4 GB). Above that it builds only
  the queried keywords, each with its complete bitmap, so search and verify timings are unchanged (`index_scope`
  column). Setup time is reported only for full builds.
- Exp. 2: no partitions or Merkle tree. Verification computes F1(id) for every returned posting, so it depends on
  r_Q only. End-to-end still differs between layouts: turning the result bitmap into ids scans it up to its highest
  set bit (an implementation cost), so layouts with files near N (dispersed) take longer than clustered (ends near
  N/3). `response_bytes` = the bitmap ciphertexts + proofs returned by the CS.
- Exp. 3: the only baseline with dynamic updates. Each run inserts b real insert-pool documents, then deletes them.
  Every N uses the same setup: no initial index (`index_scope=queried` with no keywords) and the EDB in memory
  (`edb_backend=memory`), because an update's cost does not depend on the existing entries. (Earlier runs built the
  full index at 10k / 50k only, so N = 50k was measured differently from 100k / 200k.)
  (`--update-mode per-doc` follows the paper, `--users` sets N_u). Columns: `update_ms`, `per_doc_ms`,
  `throughput_docs_s`, `throughput_pairs_s`, `message_bytes`, and `prf`/`hash`/`enc` counts (= O(N_u·m)).
- Paper bugs fixed and unspecified details are marked `[FIX]` / `[ASSUMPTION]` in the code (9 items, listed in the
  file header).
