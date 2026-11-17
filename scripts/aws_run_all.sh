#!/usr/bin/env bash
# Run the advisor's experiment plan (dataset-v4) for every scheme on one machine, one job at a time.
#
#   bash scripts/aws_run_all.sh                 # every step below, in order
#   bash scripts/aws_run_all.sh search1 tamper  # only these steps
#
# Every run writes into its own folder RUN_DIR (default baselines/results/runs/<date>_<commit>/, git-ignored):
#   RUN_DIR/<scheme>/<scheme>_<suite>.csv + .manifest.json   (scheme = amtp, chen, du, secollab)
#   RUN_DIR/amtp/splitmerge_n<N>_t<θ>/                       (split / merge)
#   RUN_DIR/logs/<step>.log
# so runs never mix. Plot one run with: python3 baselines/plot_paper.py RUN_DIR  (figures -> RUN_DIR/figures/)
#
# Steps:
#   check       dataset-v4 present, unit tests, selftests
#   search1     Search 1.1 / 1.2   single domain, AND queries: every kQ at 100k files (1.1) and kQ = 5 at
#                                  10k..125k files (1.2); only these points are run          (4 schemes)
#   verify1     Verify 1.1         single domain, real keywords with ~10..10,000 results    (4 schemes)
#   tamper      Verify 1.2         server modifies / hides / injects / sends old versions of t of ~2,000
#                                  results; early-abort and full-check time, files named      (4 schemes)
#   xsearch     Search 2.1         Boolean AND / OR queries over the 4 domains               (AMTP, SE-COLLAB)
#   xverify     Verify 2.1         multi-domain keywords with ~10..10,000 results            (AMTP, SE-COLLAB)
#   xdomains    Search / Verify 2.2  the same files as D = 1..32 domains, kQ = XD_KQ, shapes XD_SHAPES (AMTP, SE-COLLAB)
#   update      update cost at N = UPDATE_SIZES: one epoch of b signed requests, b in UPDATE_B;
#               update = owner request (tokens + σ_op) + CS prepare + Validator + anchor;
#               file encryption apart                                                       (AMTP, Chen)
#   exp5        Multi-domain scalability: D = 1..32 domains, target domain of 5,000 files; query cost and
#               the target domain's update (one epoch, Phase 2 protocol); other roots unchanged  (AMTP, SE-COLLAB)
#   theta       θ sweep (NOT in the default steps: not in the plan; ex4 covers θ = 64/128/256). Run by name only.
#   splitmerge  split / merge: start with SM_N files, insert as many again (95% into one hot group), then delete
#               65% of the hot group; θ_max = 64/128/256; layout + queries every SM_QUERY_EVERY batches
#               (AMTP vs Static-MT vs Global-MT); one batch of SM_B updates = one epoch (b, recorded in the CSV);
#               SM_VARIANTS picks the variants, SM_TAG suffixes the folder (a variant run on another machine)
#
# AMTP_GAMMA_V=0: AMTP's γ = H(PID ‖ H(Enc(L))) without v (study B4); the run folder ends in _gamma_no_v and
# every manifest records amtp_gamma_v. Default 1 (the paper's γ). Baselines are not affected.
# SCHEMES="amtp chen": run only these schemes' jobs (split a step over machines; the check step always runs).
# DRY_RUN=1: print the commands instead of running them. scripts/cloud_worker.sh holds the 10-machine plan.
# X_SEARCH1, X_VERIFY1, X_TAMPER, X_XSEARCH, X_XVERIFY, X_XDOMAINS, X_EXP5: extra options for every scheme of
# that step (empty by default; scripts/smoke_all.sh uses them to run every step small).
# Settings (environment variables, defaults below). Commit the code first: every manifest records the
# git commit and git_dirty. Logs go to $LOGS; a failed step is reported at the end, the others still run.
set -u
cd "$(dirname "$0")/.."
REPO=$(pwd)
PY=${PY:-$REPO/.venv/bin/python}
REPS=${REPS:-15}                                       # median of 15 runs after 3 warm-up runs
WARMUP=${WARMUP:-3}
GV=${AMTP_GAMMA_V:-1}; export AMTP_GAMMA_V=$GV         # 0: AMTP's γ without the version v (study B4)
RUN_ID=${RUN_ID:-$(date '+%Y%m%d_%H%M')_$(git rev-parse --short HEAD)$([ "$GV" = 0 ] && echo _gamma_no_v)}
RUN_DIR=${RUN_DIR:-$REPO/baselines/results/runs/$RUN_ID}
LOGS=${LOGS:-$RUN_DIR/logs}
O_AMTP="--out $RUN_DIR/amtp"; O_CHEN="--out $RUN_DIR/chen"; O_DU="--out $RUN_DIR/du"; O_SE="--out $RUN_DIR/secollab"
CHEN_OPTS=${CHEN_OPTS:---scope full --edb memory}     # full index in RAM; use "--scope auto" if RAM runs out
SE_OPTS=${SE_OPTS:---proof-mode paths}                 # SE-COLLAB's own per-file Merkle paths, every step alike
UPDATE_SIZES=${UPDATE_SIZES:-100000}                   # N (files from all 4 domains in one AMTP domain)
UPDATE_B=${UPDATE_B:-1 10 100 1000}                    # b = signed requests per epoch
XD_KQ=${XD_KQ:-4}                                      # xdomains: query kQ kept
XD_SHAPES=${XD_SHAPES:-AND}                            # xdomains: query shapes kept
THETA_N=${THETA_N:-200000}                           # needs shared exp1_queries.json at this N (10k..200k)
THETA_VALUES=${THETA_VALUES:-64 128 256}
SM_N=${SM_N:-100000}                                   # split / merge: initial files (all 4 domains, one AMTP domain)
SM_B=${SM_B:-100}                                      # b: updates per batch = per epoch (b = 1 is ~2.4x slower)
SM_BATCHES=${SM_BATCHES:-1000}                         # x SM_B files inserted = SM_N (+100%), from the next initial files
SM_SKEWS=${SM_SKEWS:-0.95}                             # share of new files forced into the hot group
SM_RUNS=${SM_RUNS:-3}
SM_HOT_DELETE=${SM_HOT_DELETE:-0.65}                   # then delete this share of the hot group's files
SM_THETAS=${SM_THETAS:-64 128 256}
SM_QUERY_EVERY=${SM_QUERY_EVERY:-100}
SM_VARIANTS=${SM_VARIANTS:-}                           # e.g. "AMTP,Static-MT" or "Global-MT(v)" (empty: bench default)
SM_TAG=${SM_TAG:-}                                     # suffix of the split / merge folder, e.g. _gmtv
[ -n "${DRY_RUN:-}" ] || mkdir -p "$LOGS"
COMMON="--reps $REPS --warmup $WARMUP"
echo "results -> $RUN_DIR"
FAILED=()

scheme_of() {               # search1_amtp -> amtp, splitmerge_t64 -> amtp, check_pytest -> check
  case $1 in
    check_*) echo check ;;
    splitmerge_*) echo amtp ;;
    *) echo "${1##*_}" ;;
  esac
}

run() {                     # run <name> <dir> <command...>: log to $LOGS/<name>.log, keep going on failure
  local name=$1 dir=$2 s t0; shift 2
  s=$(scheme_of "$name")
  if [ -n "${SCHEMES:-}" ] && [ "$s" != check ] && [[ " $SCHEMES " != *" $s "* ]]; then
    return 0                # SCHEMES="amtp chen": only these schemes' jobs on this machine
  fi
  if [ -n "${DRY_RUN:-}" ]; then
    echo "[dry] $name: (cd $dir && $*)"
    return 0
  fi
  echo "[$(date '+%F %T')] start $name"
  t0=$SECONDS
  if (cd "$REPO/$dir" && "$@") > "$LOGS/$name.log" 2>&1; then
    echo "[$(date '+%F %T')] done  $name ($((SECONDS - t0)) s)"
  else
    echo "[$(date '+%F %T')] FAIL  $name after $((SECONDS - t0)) s (see $LOGS/$name.log)"
    FAILED+=("$name")
  fi
}

step_check() {
  run check_dataset baselines "$PY" amtp_dataset.py
  run check_pytest amtp_code "$PY" -m pytest -q
  run check_chen baselines "$PY" chen_et_al_sim.py selftest
  run check_secollab baselines "$PY" se_collab_sim.py selftest
  run check_du baselines "$PY" du_et_al_sim.py demo
}
step_search1() {
  run search1_amtp amtp_code "$PY" -m bench.experiments search1 $COMMON $O_AMTP ${X_SEARCH1:-}
  run search1_chen baselines "$PY" chen_et_al_sim.py search1 $COMMON $CHEN_OPTS $O_CHEN ${X_SEARCH1:-}
  run search1_du baselines "$PY" du_et_al_sim.py search1 $COMMON $O_DU ${X_SEARCH1:-}
  run search1_secollab baselines "$PY" se_collab_sim.py search1 $COMMON $SE_OPTS $O_SE ${X_SEARCH1:-}
}
step_verify1() {
  run verify1_amtp amtp_code "$PY" -m bench.experiments verify1 $COMMON $O_AMTP ${X_VERIFY1:-}
  run verify1_chen baselines "$PY" chen_et_al_sim.py verify1 $COMMON $CHEN_OPTS $O_CHEN ${X_VERIFY1:-}
  run verify1_du baselines "$PY" du_et_al_sim.py verify1 $COMMON $O_DU ${X_VERIFY1:-}
  run verify1_secollab baselines "$PY" se_collab_sim.py verify1 $COMMON $SE_OPTS $O_SE ${X_VERIFY1:-}
}
step_tamper() {
  run tamper_amtp amtp_code "$PY" -m bench.experiments tamper $COMMON $O_AMTP ${X_TAMPER:-}
  run tamper_chen baselines "$PY" chen_et_al_sim.py tamper $COMMON $CHEN_OPTS $O_CHEN ${X_TAMPER:-}
  run tamper_du baselines "$PY" du_et_al_sim.py tamper $COMMON $O_DU ${X_TAMPER:-}
  run tamper_secollab baselines "$PY" se_collab_sim.py tamper $COMMON $SE_OPTS $O_SE ${X_TAMPER:-}
}
step_xsearch() {
  run xsearch_amtp amtp_code "$PY" -m bench.experiments xsearch $COMMON $O_AMTP ${X_XSEARCH:-}
  run xsearch_secollab baselines "$PY" se_collab_sim.py xsearch $COMMON $SE_OPTS $O_SE ${X_XSEARCH:-}
}
step_xverify() {
  run xverify_amtp amtp_code "$PY" -m bench.experiments xverify $COMMON $O_AMTP ${X_XVERIFY:-}
  run xverify_secollab baselines "$PY" se_collab_sim.py xverify $COMMON $SE_OPTS $O_SE ${X_XVERIFY:-}
}
step_xdomains() {
  run xdomains_amtp amtp_code "$PY" -m bench.experiments xdomains $COMMON --x-kq $XD_KQ --shapes $XD_SHAPES $O_AMTP ${X_XDOMAINS:-}
  run xdomains_secollab baselines "$PY" se_collab_sim.py xdomains $COMMON $SE_OPTS --x-kq $XD_KQ --shapes $XD_SHAPES $O_SE ${X_XDOMAINS:-}
}
step_update() {
  run update_amtp amtp_code "$PY" -m bench.experiments exp3 $COMMON --sizes $UPDATE_SIZES --batches $UPDATE_B $O_AMTP
  run update_chen baselines "$PY" chen_et_al_sim.py exp3 $COMMON --sizes $UPDATE_SIZES --batches $UPDATE_B $O_CHEN
}
step_exp5() {
  run exp5_amtp amtp_code "$PY" -m bench.experiments exp5 $COMMON $O_AMTP ${X_EXP5:-}
  run exp5_secollab baselines "$PY" se_collab_sim.py exp5 $COMMON $SE_OPTS $O_SE ${X_EXP5:-}
}
step_theta() {
  run theta_amtp amtp_code "$PY" -m bench.experiments theta $COMMON --n "$THETA_N" --theta-values $THETA_VALUES $O_AMTP
}
step_splitmerge() {
  local t var=()
  [ -n "$SM_VARIANTS" ] && var=(--variants "$SM_VARIANTS")
  for t in $SM_THETAS; do
    run "splitmerge_t$t$SM_TAG" amtp_code "$PY" -m bench.ablation --source arxiv --n "$SM_N" \
      --theta-max "$t" --theta-min $((t / 4)) --batches "$SM_BATCHES" --batch-size "$SM_B" --delete-frac 0 \
      --fresh-source initial --skews "$SM_SKEWS" --runs "$SM_RUNS" --hot-delete-frac "$SM_HOT_DELETE" \
      --query-every "$SM_QUERY_EVERY" ${var[@]+"${var[@]}"} \
      --out "$RUN_DIR/amtp/splitmerge_n${SM_N}_t${t}${SM_TAG}"
  done
}

STEPS=("$@")
[ ${#STEPS[@]} -eq 0 ] && STEPS=(check search1 verify1 tamper xsearch xverify xdomains update exp5 splitmerge)
echo "commit $(git rev-parse --short HEAD), uncommitted changes: $(git status --porcelain --untracked-files=no | wc -l)"
for s in "${STEPS[@]}"; do
  "step_$s"
done
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "all steps finished, results in $RUN_DIR"
else
  echo "failed: ${FAILED[*]}"
  exit 1
fi
