# Configuration of the paper (32) experiments (docs/reports/2026-11-18-paper32-experiment-layout.md). Source it
# before running any scheme (AMTP and the baselines read AMTP_QUERY_SET through baselines/amtp_dataset.py):
#
#   source scripts/paper32_env.sh
#   REPS=10 WARMUP=3 bash scripts/aws_run_all.sh search1 ...
#
# Every value is written to each result's manifest.json.
source "$(dirname "${BASH_SOURCE[0]:-$0}")/paper_env.sh"     # AMTP construction flags of the paper (all on)
export AMTP_QUERY_SET=p32         # Search 1.1 / 1.2: k_Q 1, 2, 4, 8, 16; Search 1.2 at k_Q = 4 (paper default)
export AMTP_CPABE=bsw07           # K_d under real CP-ABE (BSW07, Charm, SS512)
export AMTP_ABS=mpr               # σ_op = σ_d under real ABS (Maji-Prabhakaran-Rosulek, amtp/core/abs.py)
export AMTP_ABS_CURVE=SS512       # decision #54 C: the curve of CP-ABE and SE-COLLAB (symmetric pairing)
export AMTP_ANCHOR=${AMTP_ANCHOR:-chain-local}   # Root Anchor contract on an in-process EVM; chain = Sepolia (.env)
# AMTP query suites (search1, verify1, xsearch, xverify, xdomains, exp5) through bench_split.run: every row also has the
# server's search alone (server_search_pf: no proof, no fetch) next to DU verify and end-to-end (owner, 19 Nov)
export AMTP_MOD=${AMTP_MOD:-bench_split.run}
export REPS=${REPS:-10}           # advisor: 10 measured runs per point
export WARMUP=${WARMUP:-3}
# Exp. 3 of (32): (a) x = b at N = 100k (step update), (b) x = N at b = 100 (step update_n); partitions frozen (no split / merge)
export UPDATE_SIZES=${UPDATE_SIZES:-100000} UPDATE_B=${UPDATE_B:-1 10 100 1000}
export UPDATE_N_SIZES=${UPDATE_N_SIZES:-10000 25000 50000 75000 100000 125000} UPDATE_N_B=${UPDATE_N_B:-100}
# Exp. 4 (split / merge ablation, decisions #44 A+, #45 C): 20% of the dataset, 5 skew levels, θ_max 64, 10 runs
export SM_N=${SM_N:-25000} SM_BATCHES=${SM_BATCHES:-250} SM_B=${SM_B:-100} SM_THETAS=${SM_THETAS:-64}
export SM_SKEWS=${SM_SKEWS:-0,0.25,0.5,0.75,0.95} SM_RUNS=${SM_RUNS:-10} SM_HOT_DELETE=${SM_HOT_DELETE:-0.65}
export SM_VARIANTS=${SM_VARIANTS:-AMTP,Static-MT,Global-MT(v)} SM_QUERY_EVERY=${SM_QUERY_EVERY:-50}
echo "paper (32): query set $AMTP_QUERY_SET, CP-ABE $AMTP_CPABE, ABS $AMTP_ABS ($AMTP_ABS_CURVE), anchor $AMTP_ANCHOR, reps $REPS after $WARMUP warm-up; ex4 N=$SM_N x $SM_BATCHES batches of $SM_B, skews $SM_SKEWS, runs $SM_RUNS"
