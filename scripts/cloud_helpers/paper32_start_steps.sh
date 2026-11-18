#!/bin/bash
# Paper (32) round: run steps of scripts/aws_run_all.sh on one instance (from the Mac), one job at a time, all on ~/venv_p32.
#   BUNDLE=paper32.bundle bash scripts/cloud_helpers/paper32_start_steps.sh <ip> <commit> <run name> <step>...
#   e.g. ... 43.210.22.111 c79b2a0 p32_ex3 update update_n
# Results: ~/NewAMTP/baselines/results/runs/<run name>/ (logs/, console.log); last line of console.log: "all steps finished" / "failed: ...".
ip=$1; want=$2; name=$3; shift 3; BUNDLE=${BUNDLE:?set BUNDLE}
here=$(cd "$(dirname "$0")" && pwd)
O=(-i "${KEY:-$HOME/Downloads/amtp-key.pem}" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
scp -q "${O[@]}" "$BUNDLE" ubuntu@$ip:paper32.bundle || { echo "$ip copy failed"; exit 1; }
ssh "${O[@]}" ubuntu@$ip bash -s -- "$want" < "$here/paper32_setup_venv.sh" || exit 1
ssh "${O[@]}" ubuntu@$ip bash -s -- "$name" "$@" <<'REMOTE'
set -u; name=$1; shift; cd ~/NewAMTP
if pgrep -f '[b]ench[.]|[a]ws_run_all' > /dev/null; then echo "a job is already running"; exit 1; fi
t=$(cd amtp_code && ~/venv_p32/bin/python -m pytest -q -x 2>&1 | tail -1); echo "pytest (venv_p32): $t"
case "$t" in *failed*|*error*|"") echo "pytest failed, not starting"; exit 1 ;; esac
R=~/NewAMTP/baselines/results/runs/$name
[ -e "$R" ] && { echo "$R exists, not overwriting"; exit 1; }
mkdir -p "$R"; source scripts/paper32_env.sh > /dev/null
RUN_DIR="$R" PY=~/venv_p32/bin/python nohup bash scripts/aws_run_all.sh "$@" > "$R/console.log" 2>&1 &
echo $! > "$R/pid"; echo "started $name ($*) pid $!"
REMOTE
