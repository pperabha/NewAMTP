#!/bin/bash
# Start the Root-Anchor-on-Sepolia round on one cloud machine (r7i.4xlarge, as every run of the paper), from the Mac.
# The machines have no GitHub access: origin = ~/newamtp.bundle. The keys and the RPC URL go up as ~/NewAMTP/.env
# (test network only) and are deleted on the machine as soon as the job ends (and on a failed start).
#   git bundle create newamtp_chain.bundle 767289c..feat/chain-anchor
#   WANT=<short commit> BUNDLE=newamtp_chain.bundle bash scripts/cloud_helpers/start_chain.sh <ip>
#   (CHECK_ONLY=1: copy, check out, install, pytest; no start; .env removed again)
# Job (one after the other, the admin key sends every transaction, so never two at once):
#   1. chain/sepolia_bench.py: D1-D4 at N = 100,000 each, b = 1 10 100 1000, 3 warm-up + 15 rounds per b,
#      fresh contract; Phase 2 protocol time, anchor time (receipt), time to finality, gas, root reads
#   2. chain/gas_domains.py: gas against D = 1..32 (fresh contract)
# Results: ~/NewAMTP/baselines/results/runs/chain_aws/ ; log ~/chain.log, last line "chain finished rc=<rc>".
# The job runs as ~/chain_cloud_worker.sh so scripts/watch_stop.sh keeps the machine on while it runs.
set -u
ip=$1; K=${KEY:-$HOME/Downloads/amtp-key.pem}; WANT=${WANT:?set WANT}
BUNDLE=${BUNDLE:-newamtp_chain.bundle}; BRANCH=${BRANCH:-feat/chain-anchor}
ENVF=${ENVF:-$(cd "$(dirname "$0")/../.." && pwd)/.env}
[ -f "$ENVF" ] || { echo "no $ENVF"; exit 1; }
O="-i $K -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
scp -q $O "$BUNDLE" ubuntu@${ip}:newamtp.bundle || { echo "copy of the bundle failed"; exit 1; }
scp -q $O "$ENVF" ubuntu@${ip}:chain.env || { echo "copy of .env failed"; exit 1; }
ssh $O ubuntu@${ip} bash -s -- "$WANT" "$BRANCH" "${CHECK_ONLY:-}" <<'REMOTE'
set -u; want=$1; branch=$2; check_only=${3:-}
cleanup() { rm -f ~/chain.env ~/NewAMTP/.env; }
cd ~/NewAMTP || { echo "no ~/NewAMTP"; cleanup; exit 1; }
if pgrep -f '[c]loud_worker[.]sh|[b]ench[.]|[s]epolia_bench|[g]as_domains' > /dev/null; then
  echo "a job is already running, not touching it"; cleanup; exit 1; fi
git fetch -q origin 2>&1 && git checkout -q -B chain "origin/$branch" || { echo "git update failed"; cleanup; exit 1; }
head=$(git rev-parse --short HEAD); dirty=$(git status --porcelain --untracked-files=no | wc -l)
echo "commit $head dirty=$dirty cpus=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G data=$(ls data 2>/dev/null | tr '\n' ' ')"
[ "$head" = "$want" ] || { echo "expected $want"; cleanup; exit 1; }
[ "$dirty" = 0 ] || { echo "tracked files changed, not starting"; cleanup; exit 1; }
[ -e baselines/results/runs/chain_aws ] && { echo "runs/chain_aws already exists, not overwriting"; cleanup; exit 1; }
mv ~/chain.env ~/NewAMTP/.env && chmod 600 ~/NewAMTP/.env
PY=$(command -v python3.12 || command -v python3)
[ -x ~/venv_chain/bin/python ] || $PY -m venv ~/venv_chain
~/venv_chain/bin/pip install -q -r chain/requirements.txt 2>&1 | grep -v notice | tail -2
t=$(cd amtp_code && ~/venv_chain/bin/python -m pytest -q 2>&1 | tail -1); echo "pytest: $t"
case "$t" in *failed*|*error*|"") echo "pytest failed, not starting"; cleanup; exit 1 ;; esac
~/venv_chain/bin/python chain/sepolia.py status || { echo "network check failed"; cleanup; exit 1; }
[ -n "$check_only" ] && { cleanup; echo "check only: .env removed"; exit 0; }
cat > ~/chain_cloud_worker.sh <<'JOB'
#!/bin/bash
cd ~/NewAMTP
trap 'rm -f ~/NewAMTP/.env' EXIT
R=~/NewAMTP/baselines/results/runs/chain_aws; mkdir -p $R; rc=0
echo "commit $(git rev-parse --short HEAD), uncommitted changes: $(git status --porcelain --untracked-files=no | wc -l)"
echo "[$(date -u '+%F %T')] start sepolia_bench"
~/venv_chain/bin/python chain/sepolia_bench.py --n 100000 --b 1 10 100 1000 --warmup 3 --reps 15 --deploy \
  --out $R > $R/sepolia_bench.log 2>&1 || rc=1
echo "[$(date -u '+%F %T')] sepolia_bench rc=$rc"
echo "[$(date -u '+%F %T')] start gas_domains"
~/venv_chain/bin/python chain/gas_domains.py --max-d 32 --out $R > $R/gas_domains.log 2>&1 || rc=1
echo "[$(date -u '+%F %T')] gas_domains done"
rm -f ~/NewAMTP/.env
echo "chain finished rc=$rc"
JOB
pkill -f '[w]atch_stop[.]sh' ; rm -f ~/watch_stop.log
nohup setsid bash ~/chain_cloud_worker.sh > ~/chain.log 2>&1 < /dev/null &
sleep 2
nohup setsid bash scripts/watch_stop.sh > ~/watch_stop.out 2>&1 < /dev/null &
sleep 4; echo "started: $(pgrep -fc '[c]hain_cloud_worker[.]sh') job, $(pgrep -fc '[w]atch_stop[.]sh') watch_stop"; head -3 ~/chain.log
REMOTE
