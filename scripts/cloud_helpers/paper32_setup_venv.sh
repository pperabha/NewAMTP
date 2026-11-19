#!/bin/bash
# Run ON a machine (ssh ubuntu@<ip> bash -s -- <commit> < paper32_setup_venv.sh): check out <commit> from ~/paper32.bundle and
# build ~/venv_p32 = python3.12 venv + chain/requirements.txt (web3, eth-tester, py-evm) + Charm copied from ~/NewAMTP/.venv
# (the compiled Charm 0.62 against /usr/local/lib/libpbc). Uses <venv>/bin/python -m pip only (see paper32_start_ex4.sh).
set -u; want=$1
cd ~/NewAMTP || { echo "no ~/NewAMTP"; exit 1; }
git fetch -q ~/paper32.bundle "+refs/heads/*:refs/remotes/paper32/*" && git checkout -q -B paper32 "$want" || { echo "git failed"; exit 1; }
head=$(git rev-parse --short HEAD); dirty=$(git status --porcelain --untracked-files=no | wc -l)
[ "$head" = "${want:0:7}" ] || { echo "head $head != $want"; exit 1; }
[ "$dirty" = 0 ] || { echo "tracked files changed"; exit 1; }
SP=~/NewAMTP/.venv/lib/python3.12/site-packages
if [ ! -x ~/venv_p32/bin/python ]; then
  python3.12 -m venv ~/venv_p32 && ~/venv_p32/bin/python -m pip install -q --upgrade pip 2>&1 | tail -1
  ~/venv_p32/bin/python -m pip install -q -r chain/requirements.txt 2>&1 | grep -v -i notice | tail -2
  for d in $(ls $SP | grep -i "^charm"); do cp -r "$SP/$d" ~/venv_p32/lib/python3.12/site-packages/; done
fi
~/venv_p32/bin/python -c "import charm, web3, eth_account, eth_tester; from charm.toolbox.pairinggroup import PairingGroup; PairingGroup('SS512')" \
  || { echo "venv_p32 broken"; exit 1; }
a=$(cd amtp_code && AMTP_ABS=mpr AMTP_ABS_CURVE=SS512 ~/venv_p32/bin/python -m pytest -q -x tests/test_abs.py tests/test_chain_anchor.py 2>&1 | tail -1)
echo "commit $head, venv_p32 ok, abs + chain tests: $a"
case "$a" in *failed*|*error*|"") exit 1 ;; esac
