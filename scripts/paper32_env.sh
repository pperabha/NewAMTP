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
export AMTP_ANCHOR=${AMTP_ANCHOR:-chain-local}   # Root Anchor contract on an in-process EVM; chain = Sepolia (.env)
export REPS=${REPS:-10}           # advisor: 10 measured runs per point
export WARMUP=${WARMUP:-3}
echo "paper (32): query set $AMTP_QUERY_SET, CP-ABE $AMTP_CPABE, anchor $AMTP_ANCHOR, reps $REPS after $WARMUP warm-up"
