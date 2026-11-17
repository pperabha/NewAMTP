# AMTP: Adaptive Multi-Domain Merkle Tree Partitioning

Prototype and experiments for the paper **"AMTP: Adaptive Multi-Domain Merkle Tree Partitioning for Dynamic
Verifiable Search over Encrypted Cloud Data"** (Roiampaeng, Korcharoenkiat, Wenk, Saengbundit, Fugkeaw; SIIT,
Thammasat University).

AMTP is a Python 3.12 prototype of the full protocol (Phases 1-5 of the paper): adaptive Merkle partitions with
split / merge, the B+ Search Tree and Cuckoo filter, Partition-Aware Posting Commitments (PAPCs) under an Index
Merkle Tree, Authenticated Selective Proof Assembly (ASPA), owner validation of every update, and a simulated Root
Anchor. The three baselines of the paper (Chen et al. [40], Du et al. [7], SE-COLLAB [37]) are re-implemented in
`baselines/`.

- [1. Install](#1-install)
- [2. Test](#2-test)
- [3. Run](#3-run)
- [4. Reproduce the paper's figures](#4-reproduce-the-papers-figures)
- [5. Re-run the experiments](#5-re-run-the-experiments)
- [6. Code map](#6-code-map)
- [7. Implementation notes](#7-implementation-notes)

## 1. Install

Requirements: Python 3.12, about 5 GB of free disk for the unpacked dataset. Tested on macOS (Apple silicon) and
Ubuntu 24.04 (AWS `r7i.4xlarge`).

```bash
git clone https://github.com/pperabha/NewAMTP.git
cd NewAMTP
python3.12 -m venv .venv          # Python 3.12 (the version every result was produced with)
.venv/bin/pip install -r amtp_code/requirements.txt
```

**Dataset** (needed for the experiments, not for the tests or the demo). The arXiv dataset used in the paper
(dataset-v4: 4 domains x 125,000 papers + 12,500 insertion pool, RAKE keywords, seed 42) is stored compressed in
`datasets/arxiv/data_v4/`. Unpack it once (a few minutes, standard library only; every part is checked by SHA-256):

```bash
.venv/bin/python datasets/arxiv/unpack.py          # -> data/amtp_file_db_v4/
.venv/bin/python baselines/amtp_dataset.py         # check: D1..D4 initial 125000 pool 12500
```

How the dataset was built from the Kaggle arXiv snapshot: [`datasets/arxiv/README.md`](datasets/arxiv/README.md).

**SE-COLLAB only (optional).** Its pairing operations need Charm-Crypto with the GMP and PBC libraries:

```bash
brew install gmp pbc                     # macOS; on Ubuntu: apt install libgmp-dev libpbc-dev
.venv/bin/pip install charm-crypto-framework==0.62
```

Details and troubleshooting: [`baselines/README.md`](baselines/README.md). Everything else runs without Charm.

## 2. Test

```bash
cd amtp_code
../.venv/bin/python -m pytest -q                                            # default = the paper's configuration
AMTP_AND_PRUNE=0 AMTP_AND_GREEDY=0 AMTP_PART_RESULTS=0 AMTP_PART_LEAF=0 \
    ../.venv/bin/python -m pytest -q                                        # plain construction
```

The tests cover the Merkle and IMT structures, the B+ tree and Cuckoo filter, encodings, the Phase 2 update
protocol and the owner's validator, AND pruning and focus evidence, the Search Tree auxiliary data (responses must be
byte-identical with and without it), the ablation variants, and a Phase 5 fuzzer with a malicious server
(`amtp/adversary.py`) that must be rejected.

## 3. Run

**Live demo** ([`demo_v2/`](demo_v2/README.md)): Root Anchor, Cloud Server, network path and client as four
separate processes on the real dataset (unpack it first, Section 1), with a "How it works" panel and attacks on
the network path that the client's verifier must reject:

```bash
.venv/bin/pip install -r demo_v2/requirements.txt                    # first time only
lsof -ti :8101,8102,8103,8104 | xargs kill                           # free the demo ports if a demo is still running
./demo_v2/run_demo.sh --files-per-domain 5000                        # opens http://127.0.0.1:8102
.venv/bin/python -m pytest demo_v2/tests -q                          # demo tests (four real processes)
```

**Small demo without the dataset** (two domains, four users, a malicious-server switch):

```bash
cd amtp_code && ../.venv/bin/python run.py         # then open http://127.0.0.1:5000
```

On macOS, port 5000 may be taken by AirPlay Receiver (the page answers 403); use another port:
`PORT=5077 ../.venv/bin/python run.py`, then open http://127.0.0.1:5077.

**Paper configuration.** The code's defaults are the configuration of every AMTP result in the paper: fill-first
placement, γ with the partition version, AND pruning with greedy expansion of H_full, result-only partition proofs,
and the auxiliary Search Tree data Aux_i(h_w) (Eq. 17). Each part can be switched off with an environment variable,
e.g. for the plain construction (responses verify the same way in both modes):

```bash
export AMTP_AND_PRUNE=0 AMTP_AND_GREEDY=0 AMTP_PART_RESULTS=0 AMTP_PART_LEAF=0
```

[`scripts/paper_env.sh`](scripts/paper_env.sh) sets the paper's values explicitly (useful in a shell where any of
these variables was changed).

**Smoke run of every experiment** (small sizes, one repetition; the numbers are not results):

```bash
bash scripts/smoke_all.sh
```

## 4. Reproduce the paper's figures

All raw results behind the paper are in [`baselines/results/paper/`](baselines/results/paper/). One command rebuilds
Figs. 3-10 from them:

```bash
bash scripts/make_paper_figures.sh                 # -> baselines/results/paper/figures/fig03.pdf ... fig10.pdf
```

The committed `fig03` ... `fig10` are the figures of the paper. Each plotting script also writes
`figure_points.csv` (every plotted number) into `baselines/results/paper/figures/build/`.

| Paper | Figure | Data (in `baselines/results/paper/`) | Commit of the run | Plot script |
|---|---|---|---|---|
| Exp. 1 | Fig. 3 single-domain search | `data/{amtp,chen}/*_search_single.csv`, `data_no_fetch/{secollab,du}/*_search_single.csv` | `d25616b`; SE-COLLAB `0ada140`, Du `331d608` | `baselines/plot_exp1.py` |
| Exp. 1 | Figs. 4-5 multi-domain search | `data/amtp/amtp_search_multi.csv`, `data_no_fetch/secollab/secollab_search_multi.csv` | `d25616b`; SE-COLLAB `0ada140` | `baselines/plot_exp1.py` |
| Exp. 2 | Fig. 6 tamper detection | `data/*/*_tamper_detection.csv` | `d25616b` | `baselines/plot_exp2.py` |
| Exp. 2 | Figs. 7-8 user verification | `data/*/*_verify_{single,multi}.csv` | `d25616b` | `baselines/plot_exp2.py` |
| Exp. 3 | Fig. 9 ablation (update cost) | `ablation/amtp_static_t64/` (AMTP, Static-MT), `ablation/global_mt_v_t64/` (Global-MT(v)) | `767289c` | `baselines/plot_exp3.py` |
| Exp. 4 | Fig. 10 multi-domain scalability | `data/amtp/amtp_exp5_domains.csv`, `data_no_fetch/secollab/secollab_exp5_domains.csv` | `d25616b`; SE-COLLAB `0ada140` | `baselines/plot_exp4.py` |

Every CSV has a `.manifest.json` next to it with the exact command, git commit, `git_dirty`, dataset and machine
(`ablation/*/manifest.json` for Experiment 3). The benchmark suite behind Experiment 4 is still called `exp5`
(its name before the paper's final numbering).

The runs come from four commits. Between them only search-side code and benchmark bookkeeping changed: the update
path measured in Experiment 3 (`amtp/engine.py`, `merkle.py`, `variants.py`, `core/`) is identical, and the
auxiliary Search Tree data added after Experiment 3 is off in that run and changes only the server's search time.
The search-only timings of SE-COLLAB and Du et al. (`data_no_fetch/`) were repeated on two further instances of the
same type, as stated in the paper.

## 5. Re-run the experiments

All runs in the paper used AWS `r7i.4xlarge` (16 vCPU, 128 GiB RAM), one job per machine, 15 repetitions after
3 warm-up runs. Full-size runs are long (Experiment 3 with Global-MT(v) took about 14 h).

```bash
source scripts/paper_env.sh
OUT=$PWD/baselines/results/runs/my_run            # run from the repository root
cd amtp_code
# Experiment 1: server search time (search-only timers, checked against the full verified response)
../.venv/bin/python bench_split/run.py search1 --reps 15 --warmup 3 --out $OUT/amtp
../.venv/bin/python bench_split/run.py xsearch --reps 15 --warmup 3 --out $OUT/amtp
# Experiment 2: tamper detection and user verification
../.venv/bin/python bench/experiments.py tamper  --reps 15 --warmup 3 --out $OUT/amtp
../.venv/bin/python bench/experiments.py verify1 --reps 15 --warmup 3 --out $OUT/amtp
../.venv/bin/python bench/experiments.py xverify --reps 15 --warmup 3 --out $OUT/amtp
# Experiment 3: ablation (one variant per machine; Global-MT(v) with --variants "Global-MT(v)")
../.venv/bin/python -m bench.ablation --source arxiv --n 100000 --theta-max 64 --theta-min 16 --placement fill \
    --batches 1000 --batch-size 100 --skews 0.95 --hot 1 --delete-frac 0 --fresh-source initial \
    --hot-delete-frac 0.65 --query-every 100 --runs 1 --seed 1 --variants AMTP,Static-MT \
    --out $OUT/amtp/splitmerge_n100000_t64
# Experiment 4: multi-domain scalability
../.venv/bin/python bench_split/run.py exp5 --reps 15 --warmup 3 --out $OUT/amtp
```

Baselines (run from `baselines/`, same query files and sizes):

```bash
cd baselines
../.venv/bin/python chen_et_al_sim.py search1 --reps 15 --warmup 3 --scope full --edb memory --out $OUT/chen
../.venv/bin/python du_et_al_sim.py  search1 --reps 15 --warmup 3 --out $OUT/du        # also verify1, tamper
../.venv/bin/python se_collab_sim.py search1 --reps 15 --warmup 3 --proof-mode paths --out $OUT/secollab
#   SE-COLLAB also: verify1, tamper, xsearch, xverify, exp5;  Chen also: verify1, tamper
```

`scripts/aws_run_all.sh` runs every step for every scheme on one machine (`DRY_RUN=1` prints the commands).
Then plot a run with the scripts of Section 4 (`--data $OUT`; for Experiment 3, a folder holding
`amtp_static_t64/` and `global_mt_v_t64/`).

## 6. Code map

| Paper | Code (`amtp_code/amtp/`) |
|---|---|
| Phase 1: encryption, keyword extraction, protected keys | `owner.py`, `nlp.py`, `core/crypto.py`, `core/hashing.py` |
| Phase 2: partitions, Search Tree, postings, PAPC, IMT, update protocol | `engine.py`, `index.py`, `bptree.py`, `cuckoo.py`, `update.py`, `server.py` |
| Phase 2, Step 5: owner validation and anchoring | `validator.py`, `anchor.py` |
| Phase 3: split / merge and posting repair | `engine.py`, `variants.py` (AMTP, Static-MT, Global-MT policies) |
| Phase 4: search, focus set, ASPA proofs | `server.py`, `core/boolean.py`, `core/merkle.py`, `dht.py` |
| Phase 5: verification and decryption | `user.py` |
| Malicious server for tests and demo | `adversary.py` |

Benchmarks: `amtp_code/bench/` (Experiments 2-3), `amtp_code/bench_split/` (search-only timing, Experiments 1 and 4).
Baselines and plotting: `baselines/`. Shared size rule for every scheme: `baselines/wire_sizes.py`.

## 7. Implementation notes

As stated in the paper's experimental setup:

- Ed25519 signatures stand in for ABS, and an attribute-policy key wrap stands in for CP-ABE (not
  collusion-resistant; it affects only decryption, which is reported separately).
- The Root Anchor is simulated in-process with the same predecessor and epoch checks; ledger latency is not included.
- Ciphertexts live in an in-process consistent-hashing DHT (6 nodes, replication factor 3). Network latency is
  excluded for every scheme.
- Parameters: θ_max = 64, θ_min = 16, G = 16 placement groups, B+ tree order 64.
- Every AMTP query in the experiments must pass all Phase 5 checks and return exactly the plaintext ground truth,
  otherwise the run aborts.

Design notes and baseline notes: `docs/` (`AMTP_PAPER.md`, `CHEN_NOTES.md`, `DU_NOTES.md`, `SE_COLLAB_NOTES.md`).
