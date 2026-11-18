#!/bin/bash
# Paper (32) round, Exp. 4 on one instance (from the Mac). The machines have no GitHub access: the code goes up as a git bundle.
#   git bundle create paper32.bundle 7485556..feat/paper32-experiments
#   BUNDLE=paper32.bundle bash scripts/cloud_helpers/paper32_start_ex4.sh <ip> <skew> <commit>
# Copies the bundle, checks out <commit> (must be clean), runs pytest, sets up ~/venv_p32 (paper32_setup_venv.sh), then
# starts scripts/paper32_ex4_machine.sh: the four index-level jobs on ~/NewAMTP/.venv, the two full-protocol jobs on ~/venv_p32.
# NEVER run ~/NewAMTP/.venv/bin/pip on these machines: that venv is a copy of ~/AMTP/.venv and its pip writes into ~/AMTP/.venv.
ip=$1; skew=$2; want=$3; BUNDLE=${BUNDLE:?set BUNDLE}
here=$(cd "$(dirname "$0")" && pwd)
O=(-i "${KEY:-$HOME/Downloads/amtp-key.pem}" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
scp -q "${O[@]}" "$BUNDLE" ubuntu@$ip:paper32.bundle || { echo "$ip copy failed"; exit 1; }
ssh "${O[@]}" ubuntu@$ip bash -s -- "$want" < "$here/paper32_setup_venv.sh" || exit 1
ssh "${O[@]}" ubuntu@$ip bash -s -- "$skew" <<'REMOTE'
set -u; s=$1; cd ~/NewAMTP
t=$(cd amtp_code && ../.venv/bin/python -m pytest -q -x 2>&1 | tail -1); echo "pytest (.venv): $t"
case "$t" in *failed*|*error*|"") echo "pytest failed, not starting"; exit 1 ;; esac
source scripts/paper32_env.sh > /dev/null
BASE=~/NewAMTP/baselines/results/runs/ex4_skew$s
for j in gmtv_a:splitmerge:Global-MT\(v\):1:4 gmtv_b:splitmerge:Global-MT\(v\):5:3 gmtv_c:splitmerge:Global-MT\(v\):8:3 \
         amtp_sm:splitmerge:AMTP,Static-MT:1:10 proto_a:skewproto:-:1:5 proto_b:skewproto:-:6:5; do
  IFS=: read -r name step variants seed runs <<< "$j"
  [ "$variants" = - ] && variants=""; py=~/NewAMTP/.venv/bin/python; [ "$step" = skewproto ] && py=~/venv_p32/bin/python
  mkdir -p "$BASE/$name"
  RUN_DIR="$BASE/$name" SM_SKEWS="$s" SM_SEED="$seed" SM_RUNS="$runs" SM_VARIANTS="$variants" PY="$py" \
    nohup bash scripts/aws_run_all.sh "$step" > "$BASE/$name/console.log" 2>&1 &
  echo $! > "$BASE/$name/pid"; echo "  $name pid $! ($step, ${variants:-AMTP full protocol}, seeds $seed..$((seed + runs - 1)))"
done
REMOTE
