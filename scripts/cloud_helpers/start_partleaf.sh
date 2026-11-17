#!/bin/bash
# Start the "part leaf" round (Search Tree leaf by partition, AMTP_PART_LEAF=1, with every query flag on as plan
# "prune") on one cloud machine, from the Mac. The machines have no GitHub access: origin = ~/newamtp.bundle.
#   git bundle create newamtp_partleaf.bundle 767289c..feat/search-tree-part-leaf
#   WANT=<short commit> BUNDLE=newamtp_partleaf.bundle bash scripts/cloud_helpers/start_partleaf.sh <1|2|3> <ip>
#   (CHECK_ONLY=1: copy, check out, pytest; no start)
# Every baseline is re-measured on the machine of the AMTP suite it is plotted with (code and commands unchanged):
# worker 1: AMTP search1, xsearch, exp5 (bench_split)  then  Chen, SE-COLLAB, Du search1; SE-COLLAB xsearch, exp5
# worker 2: AMTP xdomains (bench_split), xverify         then  SE-COLLAB xverify, xdomains
# worker 3: AMTP verify1, tamper                         with  Chen, SE-COLLAB, Du verify1, tamper
# worker 4: SE-COLLAB search1, xsearch, xdomains, exp5 only (its own timers bpl_retrieval / boolean_eval / result_fetch
#           written to the CSV, for search without fetch)   -> runs/paper_partleaf_se/
# worker 5: Du search1 only (extra columns search_no_fetch / _sum: Algorithm 2 returning only the matching slots,
#           timed after the full query; the other columns unchanged)   -> runs/paper_partleaf_du/
# Results: runs/paper_partleaf/{amtp,chen,secollab,du,logs} on each machine (worker 4: paper_partleaf_se). Not re-run: ex3 and ex4 (update code unchanged).
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
if pgrep -f '[c]loud_worker[.]sh|[b]ench[.]ablation|[b]ench[.]experiments|[b]ench_split|[c]hen_et_al_sim|[d]u_et_al_sim|[s]e_collab_sim' > /dev/null; then
  echo "w$w: a job is already running, not touching it"; exit 1; fi
git fetch -q origin 2>&1 && git checkout -q -B partleaf "origin/$branch" || { echo "w$w: git update failed"; exit 1; }
head=$(git rev-parse --short HEAD); dirty=$(git status --porcelain --untracked-files=no | wc -l)
echo "w$w: commit $head dirty=$dirty cpus=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G disk_free=$(df -h ~ | awk 'NR==2{print $4}') data=$(ls data 2>/dev/null | tr '\n' ' ')"
[ "$head" = "$want" ] || { echo "w$w: expected $want"; exit 1; }
[ "$dirty" = 0 ] || { echo "w$w: tracked files changed, not starting"; exit 1; }
d=paper_partleaf; [ "$w" = 4 ] && d=paper_partleaf_se; [ "$w" = 5 ] && d=paper_partleaf_du
[ -e baselines/results/runs/$d ] && { echo "w$w: runs/$d already exists, not overwriting"; exit 1; }
t=$(cd amtp_code && ../.venv/bin/python -m pytest -q 2>&1 | tail -1); echo "w$w: pytest, flags off: $t"
case "$t" in *failed*|*error*) echo "w$w: pytest failed, not starting"; exit 1 ;; *passed*) ;; *) echo "w$w: pytest gave no result, not starting"; exit 1 ;; esac
t=$(cd amtp_code && AMTP_PART_LEAF=1 AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 ../.venv/bin/python -m pytest -q 2>&1 | tail -1); echo "w$w: pytest, every flag on: $t"
case "$t" in *failed*|*error*) echo "w$w: pytest failed, not starting"; exit 1 ;; *passed*) ;; *) echo "w$w: pytest gave no result, not starting"; exit 1 ;; esac
[ -n "$check_only" ] && exit 0
case "$w" in 1|2|3|4|5) ;; *) echo "w$w: worker must be 1 to 5"; exit 1 ;; esac
cat > ~/partleaf_cloud_worker.sh <<'JOB'
#!/bin/bash
# $1 = worker. Every job runs alone, one after the other; a baseline runs on the machine of the AMTP suite it is
# plotted with. Baselines: their unchanged code through scripts/aws_run_all.sh (the commands of the main round).
cd ~/NewAMTP
export AMTP_PLACEMENT=fill AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 AMTP_PART_LEAF=1
RUN=paper_partleaf; [ "$1" = 4 ] && RUN=paper_partleaf_se; [ "$1" = 5 ] && RUN=paper_partleaf_du
R=~/NewAMTP/baselines/results/runs/$RUN; mkdir -p $R/logs; rc=0
echo "worker $1  commit $(git rev-parse --short HEAD), uncommitted changes: $(git status --porcelain --untracked-files=no | wc -l)"
split() {     # AMTP suite through bench_split (search-only columns + the full query), reps 15 / warmup 3
  local name=$1 t0=$SECONDS; shift; mkdir -p $R/amtp
  echo "[$(date -u '+%F %T')] start ${name}_amtp"
  if (cd amtp_code && ../.venv/bin/python -m bench_split.run "$@" --reps 15 --warmup 3 --out $R/amtp) > $R/logs/${name}_amtp.log 2>&1; then
    echo "[$(date -u '+%F %T')] done  ${name}_amtp ($((SECONDS - t0)) s)"
  else
    echo "[$(date -u '+%F %T')] FAIL  ${name}_amtp (see logs/${name}_amtp.log)"; rc=1
  fi
}
rest() {      # rest "<schemes>" <steps...>: scripts/aws_run_all.sh into the same run folder
  local schemes=$1; shift
  SCHEMES="$schemes" RUN_ID=$RUN bash scripts/aws_run_all.sh "$@" || rc=1
}
case $1 in
  1) split search1 search1; split xsearch xsearch; split exp5 exp5
     rest "chen secollab du" search1 xsearch exp5 ;;
  2) split xdomains xdomains --x-kq 4 --shapes AND
     rest "amtp secollab" xverify
     rest "secollab" xdomains ;;
  3) rest "amtp chen secollab du" verify1 tamper ;;
  4) rest "secollab" search1 xsearch xdomains exp5 ;;     # SE-COLLAB again, now writing its search split
  5) rest "du" search1 ;;                                 # Du again, now with search_no_fetch
esac
echo "partleaf finished rc=$rc"
JOB
pkill -f '[w]atch_stop[.]sh' ; rm -f ~/watch_stop.log
nohup setsid bash ~/partleaf_cloud_worker.sh $w > ~/partleaf.log 2>&1 < /dev/null &
sleep 2
nohup setsid bash scripts/watch_stop.sh > ~/watch_stop.out 2>&1 < /dev/null &
sleep 4; echo "w$w: started: $(pgrep -fc '[c]loud_worker[.]sh') job, $(pgrep -fc '[w]atch_stop[.]sh') watch_stop"; head -4 ~/partleaf.log
REMOTE
