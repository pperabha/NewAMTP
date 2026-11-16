#!/bin/bash
# Mac watcher for the "part leaf" round: every 3 min report new done / FAIL lines of ~/partleaf.log on each machine;
# when a machine's job has ended, copy its runs/paper_partleaf* folders and the log to runs/cloud/partleaf_w<N>/
# (before it powers itself off).   IPS="<ip worker 1> <ip worker 2> <ip worker 3>" REPO=<repo> bash watch_partleaf_local.sh
K=${KEY:-$HOME/Downloads/amtp-key.pem}
DEST=${REPO:?set REPO}/baselines/results/runs/cloud
read -r -a IPS <<< "${IPS:?set IPS}"
seen=(); done_=(); unr=()     # indexed by worker number (bash 3.2 on macOS: no associative arrays)
while true; do
  left=0
  for i in "${!IPS[@]}"; do
    w=$((i + 1)); ip=${IPS[$i]}
    [ -n "${done_[$w]:-}" ] && continue
    left=$((left + 1))
    out=$(ssh -n -i $K -o BatchMode=yes -o ConnectTimeout=8 ubuntu@${ip} \
      "grep -E 'done |FAIL|failed:|partleaf finished' ~/partleaf.log; echo JOBS=\$(pgrep -fc '[c]loud_worker[.]sh') END=\$(grep -c 'partleaf finished' ~/partleaf.log)" 2>/dev/null) || {
      [ -z "${unr[$w]:-}" ] && echo "$(date '+%H:%M') w$w: unreachable"; unr[$w]=1; continue; }
    [ -n "${unr[$w]:-}" ] && echo "$(date '+%H:%M') w$w: reachable again"; unr[$w]=""
    body=$(grep -v '^JOBS=' <<< "$out"); n=$(grep -c . <<< "$body"); s=${seen[$w]:-0}
    if [ "$n" -gt "$s" ]; then tail -n $((n - s)) <<< "$body" | sed "s/^/w$w: /"; seen[$w]=$n; fi
    if grep -q 'JOBS=0 END=[1-9]' <<< "$out"; then
      mkdir -p "$DEST/partleaf_w$w"
      if rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${ip}:NewAMTP/baselines/results/runs/paper_partleaf*" "$DEST/partleaf_w$w/" \
         && rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${ip}:partleaf.log" "$DEST/partleaf_w$w/"; then
        echo "$(date '+%H:%M') w$w: FINISHED, copied to runs/cloud/partleaf_w$w (powers off in ~10 min)"; done_[$w]=1
      else
        echo "w$w: finished but copy failed, retrying"
      fi
    fi
  done
  [ "$left" -eq 0 ] && { echo "partleaf: all machines finished and copied"; exit 0; }
  sleep 180
done
