#!/bin/bash
# Start the "part leaf" round (Search Tree leaf by partition, AMTP_PART_LEAF=1, with every query flag on as plan
# "prune") on one cloud machine, from the Mac. The machines have no GitHub access: origin = ~/newamtp.bundle.
#   git bundle create newamtp_partleaf.bundle 767289c..feat/search-tree-part-leaf
#   WANT=<short commit> BUNDLE=newamtp_partleaf.bundle bash scripts/cloud_helpers/start_partleaf.sh <1|2> <ip>
#   (CHECK_ONLY=1: copy, check out, pytest; no start)
# worker 1: bench_split search1, xsearch, xdomains (run_cloud.sh) + exp5, then Chen search1 on the same machine
#           (Chen's code unchanged; re-measured next to AMTP)            -> runs/paper_partleaf/{amtp,chen}
# worker 2: verify1, tamper, xverify of AMTP (scripts/aws_run_all.sh)    -> runs/paper_partleaf_v/
# The job runs inside ~/partleaf_cloud_worker.sh so that scripts/watch_stop.sh keeps the machine on while it runs and
# powers it off 10 min after it ends. Log: ~/partleaf.log, last line "partleaf finished rc=<rc>".
set -u
w=$1; ip=$2; K=${KEY:-$HOME/Downloads/amtp-key.pem}; WANT=${WANT:?set WANT}
BUNDLE=${BUNDLE:-newamtp_partleaf.bundle}
BRANCH=${BRANCH:-feat/search-tree-part-leaf}
scp -q -i $K -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$BUNDLE" ubuntu@${ip}:newamtp.bundle \
  || { echo "w$w: copy of the bundle failed"; exit 1; }
ssh -i $K -o BatchMode=yes -o ConnectTimeout=10 ubuntu@${ip} bash -s -- "$w" "$WANT" "$BRANCH" "${CHECK_ONLY:-}" <<'REMOTE'
set -u; w=$1; want=$2; branch=$3; check_only=${4:-}
cd ~/NewAMTP || { echo "w$w: no ~/NewAMTP"; exit 1; }
if pgrep -f '[c]loud_worker[.]sh|[b]ench[.]ablation|[b]ench[.]experiments|[b]ench_split|[c]hen_et_al_sim' > /dev/null; then
  echo "w$w: a job is already running, not touching it"; exit 1; fi
git fetch -q origin 2>&1 && git checkout -q -B partleaf "origin/$branch" || { echo "w$w: git update failed"; exit 1; }
head=$(git rev-parse --short HEAD); dirty=$(git status --porcelain --untracked-files=no | wc -l)
echo "w$w: commit $head dirty=$dirty cpus=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G disk_free=$(df -h ~ | awk 'NR==2{print $4}') data=$(ls data 2>/dev/null | tr '\n' ' ')"
[ "$head" = "$want" ] || { echo "w$w: expected $want"; exit 1; }
[ "$dirty" = 0 ] || { echo "w$w: tracked files changed, not starting"; exit 1; }
for d in paper_partleaf paper_partleaf_v; do
  [ -e baselines/results/runs/$d ] && { echo "w$w: runs/$d already exists, not overwriting"; exit 1; }; done
(cd amtp_code && ../.venv/bin/python -m pytest -q 2>&1 | tail -1)
(cd amtp_code && AMTP_PART_LEAF=1 AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 ../.venv/bin/python -m pytest -q 2>&1 | tail -1)
[ -n "$check_only" ] && exit 0
if [ "$w" = 1 ]; then
cat > ~/partleaf_cloud_worker.sh <<'JOB'
#!/bin/bash
cd ~/NewAMTP
export AMTP_PART_LEAF=1
RUN_NAME=paper_partleaf bash amtp_code/bench_split/run_cloud.sh
rc=$?
R=~/NewAMTP/baselines/results/runs/paper_partleaf
if [ $rc -eq 0 ]; then
  cd ~/NewAMTP/amtp_code; t0=$SECONDS
  echo "[$(date -u '+%F %T')] start exp5"
  if AMTP_PLACEMENT=fill AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 ../.venv/bin/python -m bench_split.run exp5 --reps 15 --warmup 3 --out $R/amtp > $R/logs/exp5.log 2>&1; then
    echo "[$(date -u '+%F %T')] done  exp5 ($((SECONDS - t0)) s)"
  else
    echo "[$(date -u '+%F %T')] FAIL  exp5 (see logs/exp5.log)"; rc=1
  fi
fi
cd ~/NewAMTP/baselines; t0=$SECONDS
echo "[$(date -u '+%F %T')] start chen_search1"
if ../.venv/bin/python chen_et_al_sim.py search1 --reps 15 --warmup 3 --scope full --edb memory --out $R/chen > $R/logs/chen_search1.log 2>&1; then
  echo "[$(date -u '+%F %T')] done  chen_search1 ($((SECONDS - t0)) s)"
else
  echo "[$(date -u '+%F %T')] FAIL  chen_search1 (see logs/chen_search1.log)"; rc=1
fi
echo "partleaf finished rc=$rc"
JOB
else
cat > ~/partleaf_cloud_worker.sh <<'JOB'
#!/bin/bash
cd ~/NewAMTP
AMTP_PLACEMENT=fill AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 AMTP_PART_LEAF=1 SCHEMES=amtp \
  RUN_ID=paper_partleaf_v bash scripts/aws_run_all.sh verify1 tamper xverify
echo "partleaf finished rc=$?"
JOB
fi
pkill -f '[w]atch_stop[.]sh' ; rm -f ~/watch_stop.log
nohup setsid bash ~/partleaf_cloud_worker.sh > ~/partleaf.log 2>&1 < /dev/null &
sleep 2
nohup setsid bash scripts/watch_stop.sh > ~/watch_stop.out 2>&1 < /dev/null &
sleep 4; echo "w$w: started: $(pgrep -fc '[c]loud_worker[.]sh') job, $(pgrep -fc '[w]atch_stop[.]sh') watch_stop"; head -4 ~/partleaf.log
REMOTE
