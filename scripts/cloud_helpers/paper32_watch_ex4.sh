#!/bin/bash
# From the Mac: copy Exp. 4 results every 15 min until no job runs; prints one status line per machine.
#   bash scripts/cloud_helpers/paper32_watch_ex4.sh 1:<ip>:0 2:<ip>:0.25 3:<ip>:0.5 4:<ip>:0.75 5:<ip>:0.95
# Copies into baselines/results/runs/cloud/ex4_w<k>_skew<s>/ of this checkout.
L=$(cd "$(dirname "$0")/../.." && pwd)/baselines/results/runs/cloud; mkdir -p "$L"
O="-i ${KEY:-$HOME/Downloads/amtp-key.pem} -o BatchMode=yes -o ConnectTimeout=15"
while true; do
  active=0
  for m in "$@"; do
    w=${m%%:*}; r=${m#*:}; ip=${r%%:*}; s=${r#*:}
    rsync -a -e "ssh $O" "ubuntu@$ip:NewAMTP/baselines/results/runs/ex4_skew$s/" "$L/ex4_w${w}_skew$s/" 2>/dev/null
    st=$(ssh $O ubuntu@$ip "cd ~/NewAMTP && SKEW=$s bash scripts/paper32_ex4_machine.sh status" 2>/dev/null)
    echo "$(date '+%H:%M') w$w skew $s: $(echo "$st" | awk '{print $1"="$2}' | tr '\n' ' ')"
    n=$(echo "$st" | grep -c -E "running|stopped"); [ -z "$st" ] && n=1
    active=$((active + n))
  done
  [ "$active" -eq 0 ] && break
  sleep 900
done
