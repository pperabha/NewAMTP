#!/usr/bin/env bash
# Exp. 4 of paper (32) on ONE instance = ONE skew level, as six background processes (at most one per
# physical core of an r7i.4xlarge: 8 cores / 16 vCPUs). Plan: 5 instances, skew 0 / 0.25 / 0.5 / 0.75 / 0.95.
#
#   SKEW=0.95 bash scripts/paper32_ex4_machine.sh          # start the six jobs (nohup), print their PIDs
#   SKEW=0.95 bash scripts/paper32_ex4_machine.sh status   # one line per job: running / done / FAILED + last line
#
# Jobs (seed k = run k of 10; bench.ablation and skewproto use the same seed -> the same workload):
#   gmtv_a  Global-MT(v)      seeds 1-4     index level (bench.ablation)
#   gmtv_b  Global-MT(v)      seeds 5-7
#   gmtv_c  Global-MT(v)      seeds 8-10
#   amtp_sm AMTP, Static-MT   seeds 1-10
#   proto_a AMTP full protocol (skewproto: σ_op ABS, DO validation, RootAnchor contract)  seeds 1-5
#   proto_b AMTP full protocol                                                            seeds 6-10
# Every other setting comes from scripts/paper32_env.sh (SM_N 25000, 250 batches of 100, θ 64/16, hot delete 0.65,
# ABS mpr SS512, CP-ABE bsw07, chain-local). Results: $BASE/<job>/amtp/..., logs: $BASE/<job>/logs, console.log.
set -u
cd "$(dirname "$0")/.."
REPO=$(pwd)
SKEW=${SKEW:?set SKEW, e.g. SKEW=0.95}
BASE=${BASE:-$REPO/baselines/results/runs/ex4_skew$SKEW}
JOBS="gmtv_a gmtv_b gmtv_c amtp_sm proto_a proto_b"

spec() {        # <job> -> "<step> <variants> <seed> <runs>"
  case $1 in
    gmtv_a)  echo "splitmerge Global-MT(v) 1 4" ;;
    gmtv_b)  echo "splitmerge Global-MT(v) 5 3" ;;
    gmtv_c)  echo "splitmerge Global-MT(v) 8 3" ;;
    amtp_sm) echo "splitmerge AMTP,Static-MT 1 10" ;;
    proto_a) echo "skewproto - 1 5" ;;
    proto_b) echo "skewproto - 6 5" ;;
  esac
}

if [ "${1:-start}" = status ]; then
  for j in $JOBS; do
    c="$BASE/$j/console.log"
    if [ ! -f "$c" ]; then st="not started"
    elif grep -q "^all steps finished" "$c"; then st="done"
    elif grep -q "^failed:" "$c"; then st="FAILED"
    elif kill -0 "$(cat "$BASE/$j/pid" 2>/dev/null)" 2>/dev/null; then st="running"
    else st="stopped?"; fi
    last=$(ls -t "$BASE/$j/logs/"*.log 2>/dev/null | head -1)
    printf "%-8s %-11s %s\n" "$j" "$st" "$( [ -n "$last" ] && tail -1 "$last" | cut -c1-110)"
  done
  exit 0
fi

source scripts/paper32_env.sh >/dev/null
echo "Exp. 4 skew $SKEW -> $BASE (commit $(git rev-parse --short HEAD), uncommitted: $(git status --porcelain --untracked-files=no | wc -l | tr -d ' '))"
for j in $JOBS; do
  read -r step variants seed runs <<< "$(spec "$j")"
  mkdir -p "$BASE/$j"
  [ "$variants" = - ] && variants=""
  RUN_DIR="$BASE/$j" SM_SKEWS="$SKEW" SM_SEED="$seed" SM_RUNS="$runs" SM_VARIANTS="$variants" \
    nohup bash scripts/aws_run_all.sh "$step" > "$BASE/$j/console.log" 2>&1 &
  echo $! > "$BASE/$j/pid"
  echo "  $j  pid $!  ($step, ${variants:-AMTP full protocol}, seeds $seed..$((seed + runs - 1)))"
done
