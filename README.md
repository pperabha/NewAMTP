# AMTP: Adaptive Multi-Domain Merkle Tree Partitioning

Prototype and experiments for the paper **"AMTP: Adaptive Multi-Domain Merkle Tree Partitioning for Dynamic
Verifiable Search over Encrypted Cloud Data"** (Roiampaeng, Korcharoenkiat, Wenk, Saengbundit, Fugkeaw; SIIT,
Thammasat University).

AMTP is a Python 3.12 prototype of the full protocol (Phases 1-5 of the paper). It implements:
- **Partitions and lookup:** adaptive Merkle partitions with split / merge, and the B+ Search Tree with its Cuckoo
  filter.
- **Search proofs:**
  - Partition-Aware Posting Commitments (PAPCs) under an indexed Merkle tree (IMT);
  - Authenticated Selective Proof Assembly (ASPA).
- **Updates:** owner validation of every update.
- **Root Anchor:** an Ethereum smart contract (`chain/RootAnchor.sol`).
- **Real cryptography:**
  - BSW07 CP-ABE for document keys;
  - the attribute-based signature of Maji, Prabhakaran and Rosulek for update requests;
  - ECDSA (secp256k1) for root transitions, verified on-chain.

The three baselines of the paper (Chen et al. [40], Du et al. [7], SE-COLLAB [37]) are re-implemented in
`baselines/`.

**Reading the results:** [`docs/PAPER_GUIDE.md`](docs/PAPER_GUIDE.md) covers:
- which figure is in which version of the paper;
- every result with where AMTP wins and loses;
- likely reviewer questions;
- the security tests.

[`baselines/results/paper32/FIGURES.md`](baselines/results/paper32/FIGURES.md) shows all 109 figures.

- [1. Install](#1-install)
- [2. Test](#2-test)
- [3. Run the demo](#3-run-the-demo)
- [4. Rebuild the paper's figures](#4-rebuild-the-papers-figures)
- [5. Re-run the experiments](#5-re-run-the-experiments)
- [6. Code map](#6-code-map)
- [7. Implementation notes](#7-implementation-notes)

## 1. Install

You need Python 3.12 and about 5 GB of free disk for the unpacked dataset. Tested on macOS (Apple silicon) and on
Ubuntu 24.04 (AWS `r7i.4xlarge`, where every result of the paper was produced).

```bash
git clone https://github.com/pperabha/NewAMTP.git
cd NewAMTP
python3.12 -m venv .venv
.venv/bin/pip install -r chain/requirements.txt    # AMTP + the Root Anchor client (web3, an in-process EVM)
```

**Charm** (pairings for CP-ABE, ABS and SE-COLLAB). It needs the GMP and PBC C libraries:

```bash
brew install gmp pbc                                  # macOS
# Ubuntu: sudo apt-get install -y libgmp-dev libssl-dev flex bison autoconf automake libtool autoconf-archive
#         git clone https://github.com/blynn/pbc.git && cd pbc && ./setup && ./configure && make && sudo make install && sudo ldconfig
.venv/bin/pip install charm-crypto-framework==0.62
```

Troubleshooting: [`baselines/README.md`](baselines/README.md).

Without Charm or web3 the code still runs on its stand-ins (Section 7), and the tests that need them are skipped.
`amtp_code/requirements.txt` is the smaller set without the chain client.

**Dataset.** You need it for the experiments and the demo, but not for the tests. The arXiv dataset of the paper is
dataset-v4:
- 4 domains × 125,000 papers, plus a pool of 12,500 papers for insertions;
- RAKE keywords;
- seed 42.

It is stored compressed in `datasets/arxiv/data_v4/`. Unpack it once (a few minutes; every part is checked by
SHA-256):

```bash
.venv/bin/python datasets/arxiv/unpack.py          # -> data/amtp_file_db_v4/
.venv/bin/python baselines/amtp_dataset.py         # check: D1..D4 initial 125000 pool 12500
```

How the dataset was built from the Kaggle arXiv snapshot: [`datasets/arxiv/README.md`](datasets/arxiv/README.md).

## 2. Test

```bash
cd amtp_code
../.venv/bin/python -m pytest -q                                          # stand-in crypto, in-process anchor
bash -c 'source ../scripts/paper32_env.sh && ../.venv/bin/python -m pytest -q'   # the paper's configuration
```

The tests cover:
- the Merkle and IMT structures, the B+ tree and the Cuckoo filter, and the encodings;
- CP-ABE and ABS;
- the RootAnchor contract on an in-process chain;
- the Phase 2 update protocol and the owner's validator;
- AND pruning and focus evidence;
- the ablation variants.

They also include a malicious server (`amtp/adversary.py`) whose every attack must be rejected by the check it
targets. The list is in [`docs/PAPER_GUIDE.md`](docs/PAPER_GUIDE.md#4-security-tests-functional-not-timed).

## 3. Run the demo

The live demo is in [`demo_v2/`](demo_v2/README.md). Four separate processes run on the real dataset: the Root
Anchor, the Cloud Server, a network path and the Data User's client.

The page shows each process. It has a "How it works" panel and switches that make the server (or the network)
cheat. The client's verifier must reject every cheat.

**Once** (after Section 1; the demo needs the unpacked dataset):

```bash
.venv/bin/pip install -r demo_v2/requirements.txt            # the demo's web packages (FastAPI, uvicorn, websockets)
.venv/bin/python datasets/arxiv/unpack.py                    # skip if data/amtp_file_db_v4/ already exists
```

**Start** (from the repository root):

```bash
lsof -ti :8101,8102,8103,8104 | xargs kill                   # stop a demo that is still running (no output if none)
./demo_v2/run_demo.sh --files-per-domain 5000
```

1. The browser opens **http://127.0.0.1:8102** (open it by hand if it does not).
2. The page shows the loading progress of 4 domains × 5,000 real files. This takes about 30 s to 1.5 min,
   depending on the machine. Search when it says ready.
3. Try the example buttons (left), then a cheat from "Server behaviour" (middle), and search again. The verdict
   turns REJECTED and the right panel names the check that failed. The full list of scenarios is in
   [`demo_v2/README.md`](demo_v2/README.md#scenarios).
4. Stop with **Ctrl-C** in the terminal.

Options:
- `--files-per-domain 500`: a faster start for a rehearsal.
- `--base-port 8201`: if ports 8101-8104 are taken (the page is then on 8202).
- `--domains D1,D2`
- `--no-browser`
- A dataset in another folder: `AMTP_DATA=/path/to/amtp_file_db_v4 ./demo_v2/run_demo.sh`.

If it does not start:
- `No module named 'fastapi'`: run the first "Once" command.
- "a demo process stopped during start-up": the dataset is not unpacked, or a port is still in use (run the `lsof`
  line).

Demo tests (four real processes on 300 files of two domains, about 10 s): `.venv/bin/python -m pytest demo_v2/tests -q`.

## 4. Rebuild the paper's figures

The results behind the paper are in [`baselines/results/paper32/data/`](baselines/results/paper32/data/), one folder
per run. Every CSV has a `.manifest.json` next to it with:
- the exact command and the git commit;
- `git_dirty`;
- the dataset and the machine;
- every crypto and anchor setting.

The raw copies with logs, including the aborted runs, are in `baselines/results/runs/cloud/`.

```bash
.venv/bin/python baselines/plot_p32.py --data baselines/results/paper32/data --out baselines/results/paper32/figures
.venv/bin/python baselines/figure_catalog.py       # -> baselines/results/paper32/FIGURES.md
```

This rebuilds all 108 figures (png + pdf) and `figure_points.csv` (every plotted number, with Q1 / Q3) in about
15 s. A rebuild gives a `figure_points.csv` identical to the committed one. The figures used in the paper are
copied into [`baselines/results/paper32/paper_figures/`](baselines/results/paper32/paper_figures/).

| Paper | Run folder (`paper32/data/`) | Commit | Steps |
|---|---|---|---|
| Exp. 1 single domain | `p32_ex1_search1_w6` | `74379b7` | `search1` (4 schemes) |
| Exp. 1 multi-domain Boolean, Exp. 2 multi-domain verify | `p32_x_search_verify_w8` | `74379b7` | `xsearch`, `xverify` (AMTP, SE-COLLAB) |
| Exp. 1 / 2 over D = 1–32 | `p32_xdomains_w9` | `74379b7` | `xdomains` (AMTP, SE-COLLAB) |
| Exp. 2 single-domain verify, tamper detection | `p32_ex2_verify1_tamper_w7` | `74379b7` | `verify1`, `tamper` (4 schemes) |
| Exp. 2 clustered / dispersed layouts, Exp. 5 | `p32_exp2_exp5_w10` | `74379b7` | `exp2` (4 schemes), `exp5` (AMTP, SE-COLLAB, Du clouds) |
| Exp. 3 | `p32_ex3_w10` | `c79b2a0` | `update`, `update_n` (AMTP, Chen) |
| Exp. 4 | `ex4_w<k>_skew<s>` (one machine per skew) | `c79b2a0` | `splitmerge`, `skewproto` |
| ABS costs (table) | `baselines/results/abs/` | `8ed08b7` | `bench.abs_bench` |
| Sepolia latency and gas | `chain/runs/` | `00888ca`, `ff7dcd5` | `chain/sepolia_bench.py`, `chain/gas_domains.py` |

The figures of the earlier course version (CSS453, 17 Nov) stay reproducible:
`bash scripts/make_paper_figures.sh`, from `baselines/results/paper/`.

## 5. Re-run the experiments

Every run of the paper used AWS `r7i.4xlarge` (16 vCPU, 128 GiB RAM), one job per machine, except Exp. 4 (six
processes per machine). Each point is 10 repetitions after 3 warm-up runs. A full-size step takes hours; Exp. 4
takes several hours per skew level.

**Paper configuration.** Source this before any run, for AMTP and the baselines alike:

```bash
source scripts/paper32_env.sh
```

It sets the following:
- **Crypto:** real CP-ABE (`AMTP_CPABE=bsw07`) and real ABS (`AMTP_ABS=mpr`, `AMTP_ABS_CURVE=SS512`).
- **Root Anchor:** the RootAnchor contract on an in-process EVM (`AMTP_ANCHOR=chain-local`).
- **Queries:** the query set of the paper (`AMTP_QUERY_SET=p32`), with search-only timers (`AMTP_MOD=bench_split.run`).
- **Repetitions:** 10 after 3 warm-up runs.
- **Exp. 3 and 4 sizes.**

The AMTP construction is always the paper's: fill-first placement, γ with the partition version, AND pruning with
greedy H_full, result-only partition proofs, and the Search Tree leaf by partition.

**Smoke run of every step** (small sizes, one repetition; the numbers are not results):

```bash
source scripts/paper32_env.sh && bash scripts/smoke_all.sh
```

**Full-size runs** (one machine runs every scheme of a step, so the schemes are compared on the same machine):

```bash
source scripts/paper32_env.sh
RUN_DIR=$PWD/baselines/results/runs/mine/p32_ex1_search1 bash scripts/aws_run_all.sh check search1
RUN_DIR=$PWD/baselines/results/runs/mine/p32_x_search_verify bash scripts/aws_run_all.sh xsearch xverify
RUN_DIR=$PWD/baselines/results/runs/mine/p32_xdomains bash scripts/aws_run_all.sh xdomains
RUN_DIR=$PWD/baselines/results/runs/mine/p32_ex2_verify1_tamper bash scripts/aws_run_all.sh verify1 tamper
RUN_DIR=$PWD/baselines/results/runs/mine/p32_exp2_exp5 bash scripts/aws_run_all.sh exp2 exp5
RUN_DIR=$PWD/baselines/results/runs/mine/p32_ex3 bash scripts/aws_run_all.sh update update_n
SKEW=0.95 BASE=$PWD/baselines/results/runs/mine/ex4_skew0.95 bash scripts/paper32_ex4_machine.sh   # Exp. 4: one machine
                                                      # per skew (0, 0.25, 0.5, 0.75, 0.95), six background jobs; "status" to check
.venv/bin/python baselines/plot_p32.py --data baselines/results/runs/mine --out baselines/results/runs/mine/figures
```

`DRY_RUN=1` prints the commands of a step. `SCHEMES="amtp chen"` runs only these schemes. ABS costs:
`cd amtp_code && ../.venv/bin/python -m bench.abs_bench --curves SS512 BN254 MNT224 --reps 15 --warmup 3`.

Sepolia (needs keys, an RPC URL and test ETH): [`chain/README.md`](chain/README.md).

## 6. Code map

| Paper | Code (`amtp_code/amtp/`) |
|---|---|
| Phase 1: setup, encryption, CP-ABE, ABS, keywords, protected keys | `owner.py`, `nlp.py`, `core/crypto.py`, `core/hashing.py`, `core/cpabe.py`, `core/abs.py` |
| Phase 2: partitions, Search Tree, postings, PAPC, IMT, update protocol | `engine.py`, `index.py`, `bptree.py`, `cuckoo.py`, `update.py`, `server.py` |
| Phase 2: owner validation and Root Anchor | `validator.py`, `chain_anchor.py` (client of `chain/RootAnchor.sol`), `anchor.py` (in-process) |
| Phase 3: split / merge and posting repair | `engine.py`, `variants.py` (AMTP, Static-MT, Global-MT policies) |
| Phase 4: search, focus set, ASPA proofs | `server.py`, `core/boolean.py`, `core/merkle.py`, `dht.py` |
| Phase 5: verification and decryption | `user.py` |
| Malicious server for tests and demo | `adversary.py` |

Other code:
- **Benchmarks:** `amtp_code/bench/` (`experiments.py`, `ablation.py`, `abs_bench.py`) and `amtp_code/bench_split/`
  (search-only timers).
- **Baselines and plotting:** `baselines/`, with notes in `docs/CHEN_NOTES.md`, `docs/DU_NOTES.md` and
  `docs/SE_COLLAB_NOTES.md`.
- **Shared size rule** for every scheme: `baselines/wire_sizes.py`.

## 7. Implementation notes

**Paper configuration** (`scripts/paper32_env.sh`):
- **CP-ABE:** BSW07 on Charm (SS512) protects K_d.
- **Request signatures:** σ_d = σ_op use the MPR attribute-based signature (SS512) under the policy
  `domain:Di ∧ role:owner`. The CS and the validating DO both verify them.
- **Root transitions:** σ_root is ECDSA over secp256k1, verified by the RootAnchor contract.
- **Where the contract runs:**
  - Protocol times are measured against the contract on an in-process EVM.
  - Ethereum Sepolia latency and gas are measured apart (`chain/runs/`).

**Defaults without that file:**
- Ed25519 stands in for ABS.
- An attribute-policy key wrap stands in for CP-ABE.
- An in-process Root Anchor runs the same predecessor and epoch checks.

The fast unit tests and the demo use these defaults.

**Common to both:**
- Ciphertexts live in an in-process consistent-hashing DHT (6 nodes, replication factor 3). Network latency is
  excluded for every scheme.
- Parameters: θ_max = 64, θ_min = 16, G = 16 placement groups, B+ tree order 64.
- Every AMTP query in the experiments must pass all Phase 5 checks and return exactly the plaintext ground truth,
  otherwise the run aborts.
