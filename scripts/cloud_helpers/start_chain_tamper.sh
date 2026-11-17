#!/bin/bash
# Queue Experiment 2's tamper detection with the Root Anchor on Sepolia behind the running start_chain.sh job, on
# the same machine (one admin key, so never two jobs at once). The new job waits until ~/chain_cloud_worker.sh has
# ended, checks out WANT, runs pytest, then
#   AMTP_ANCHOR=chain bench.experiments tamper --reps 15 --warmup 3     (D1-D4, N = 100,000; a fresh contract each)
# Its own copy of .env is deleted when it ends. watch_stop.sh keeps the machine on while either job runs.
#   git bundle create newamtp_chain.bundle 767289c..feat/chain-anchor
#   WANT=<short commit> BUNDLE=newamtp_chain.bundle bash scripts/cloud_helpers/start_chain_tamper.sh <ip>
# Results: ~/NewAMTP/baselines/results/runs/chain_aws/tamper/ ; log ~/chain_tamper.log ("chain tamper finished rc=").
set -u
ip=$1; K=${KEY:-$HOME/Downloads/amtp-key.pem}; WANT=${WANT:?set WANT}
BUNDLE=${BUNDLE:-newamtp_chain.bundle}
ENVF=${ENVF:-$(cd "$(dirname "$0")/../.." && pwd)/.env}
O="-i $K -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
scp -q $O "$BUNDLE" ubuntu@${ip}:newamtp_tamper.bundle || { echo "copy of the bundle failed"; exit 1; }
scp -q $O "$ENVF" ubuntu@${ip}:chain_tamper.env || { echo "copy of .env failed"; exit 1; }
ssh $O ubuntu@${ip} bash -s -- "$WANT" <<'REMOTE'
set -u; want=$1
chmod 600 ~/chain_tamper.env
cd ~/NewAMTP && git fetch -q ~/newamtp_tamper.bundle "feat/chain-anchor:refs/remotes/bundle/chain" \
  || { echo "bundle fetch failed"; rm -f ~/chain_tamper.env; exit 1; }
git cat-file -e "$want" || { echo "commit $want not in the bundle"; rm -f ~/chain_tamper.env; exit 1; }
cat > ~/chain_tamper_cloud_worker.sh <<JOB
#!/bin/bash
trap 'rm -f ~/chain_tamper.env ~/NewAMTP/.env' EXIT
while pgrep -f '[c]hain_cloud_worker[.]sh' > /dev/null; do sleep 20; done
cd ~/NewAMTP
git checkout -q -B chain_tamper $want || { echo "checkout failed"; echo "chain tamper finished rc=1"; exit 1; }
echo "commit \$(git rev-parse --short HEAD), uncommitted changes: \$(git status --porcelain --untracked-files=no | wc -l)"
cp ~/chain_tamper.env ~/NewAMTP/.env && chmod 600 ~/NewAMTP/.env
t=\$(cd amtp_code && ~/venv_chain/bin/python -m pytest -q 2>&1 | tail -1); echo "pytest: \$t"
case "\$t" in *failed*|*error*|"") echo "chain tamper finished rc=1"; exit 1 ;; esac
R=~/NewAMTP/baselines/results/runs/chain_aws/tamper; mkdir -p \$R; rc=0
echo "[\$(date -u '+%F %T')] start tamper (AMTP_ANCHOR=chain)"
(cd amtp_code && AMTP_ANCHOR=chain ~/venv_chain/bin/python -m bench.experiments tamper --reps 15 --warmup 3 \
   --out \$R) > \$R/tamper.log 2>&1 || rc=1
echo "[\$(date -u '+%F %T')] tamper done"
echo "chain tamper finished rc=\$rc"
JOB
nohup setsid bash ~/chain_tamper_cloud_worker.sh > ~/chain_tamper.log 2>&1 < /dev/null &
sleep 2; echo "queued: $(pgrep -fc '[c]hain_tamper_cloud_worker[.]sh') tamper job; running now: $(pgrep -fc '[c]hain_cloud_worker[.]sh') chain job"
tail -1 ~/chain.log
REMOTE
