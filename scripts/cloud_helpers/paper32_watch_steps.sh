#!/bin/bash
# From the Mac: copy runs started by paper32_start_steps.sh every 15 min until each console.log ends (finished / failed).
#   bash scripts/cloud_helpers/paper32_watch_steps.sh w9:<ip>:p32_ex5 w10:<ip>:p32_ex3
L=$(cd "$(dirname "$0")/../.." && pwd)/baselines/results/runs/cloud; mkdir -p "$L"
O="-i ${KEY:-$HOME/Downloads/amtp-key.pem} -o BatchMode=yes -o ConnectTimeout=15"
while true; do
  active=0
  for m in "$@"; do
    w=${m%%:*}; r=${m#*:}; ip=${r%%:*}; n=${r#*:}
    rsync -a -e "ssh $O" "ubuntu@$ip:NewAMTP/baselines/results/runs/$n/" "$L/${n}_$w/" 2>/dev/null
    last=$(tail -1 "$L/${n}_$w/console.log" 2>/dev/null)
    echo "$(date '+%H:%M') $w $n: $last"
    case "$last" in "all steps finished"*|failed:*) ;; *) active=$((active + 1)) ;; esac
  done
  [ "$active" -eq 0 ] && break
  sleep 900
done
