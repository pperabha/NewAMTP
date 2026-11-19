#!/usr/bin/env bash
# Smoke test: every step of scripts/aws_run_all.sh, for every scheme, with the same command lines but small
# sizes (1 rep, no warm-up). Run it before the cloud run; the numbers are NOT results.
#
#   bash scripts/smoke_all.sh                  # every step
#   bash scripts/smoke_all.sh search1 update   # only these steps
#
# Output: baselines/results/runs/smoke_<date>_<commit>/ (git-ignored). Every step must finish without FAIL.
# Sizes: 10k files per domain (the smallest dataset-v4 size), domain D1 for the single-domain steps;
# tamper needs 100k (the only size with tamper sets) so it runs D1 only; D = 1, 2 for the multi-domain steps.
# exp2 runs at the N of the committed baselines/results/exp2_layouts.json (100k); it cannot be made smaller.
set -u
cd "$(dirname "$0")/.."
export RUN_DIR=${RUN_DIR:-$(pwd)/baselines/results/runs/smoke_$(date '+%Y%m%d_%H%M')_$(git rev-parse --short HEAD)}
export REPS=1 WARMUP=0
export X_SEARCH1="--fpd 10000 --fix 10000 --s-domains D1"
export X_VERIFY1="--fix 10000 --s-domains D1"
export X_TAMPER="--s-domains D1"
export X_XSEARCH="--fix 10000"
export X_XVERIFY="--fix 10000"
export X_XDOMAINS="--fix 10000 --d-counts 1 2 --max-queries 2"
export X_EXP5="--d-counts 1 2"
export UPDATE_SIZES=10000 UPDATE_B="1 10"
export SM_N=2000 SM_B=100 SM_BATCHES=20 SM_RUNS=1 SM_THETAS=64 SM_QUERY_EVERY=10
exec bash scripts/aws_run_all.sh "$@"
