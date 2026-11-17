"""Gas of the Root Anchor against the number of domains D (the contract recomputes R_G over every domain).

    .venv/bin/python chain/gas_domains.py --max-d 32            # on the network of <repo>/.env (fresh contract)
    .venv/bin/python chain/gas_domains.py --max-d 32 --local    # in-process chain (same EVM bytecode)

Deploys a fresh RootAnchor, then for D = 1 .. max-d: registers domain D<D> (gas of a registration with D domains)
and anchors one transition of D1 (gas of a transition with D domains registered). Roots are random 32-byte values:
gas does not depend on them. Owner keys are generated for the run (they only sign; the admin pays gas).
Writes chain/runs/gas_domains_<time>.csv (D, register_gas, submit_gas, submit_s, block, tx) and .json.
"""
import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "amtp_code"))
sys.path.insert(0, HERE)

from sepolia import EXPLORERS, read_env                                 # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-d", type=int, default=32)
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "runs"))
    a = ap.parse_args()

    from eth_account import Account
    from web3 import Web3
    from amtp.anchor import transition_message
    from amtp.chain_anchor import ChainAnchor

    if a.local:
        chain = ChainAnchor.local()
        explorer = "local"
    else:
        env = read_env()
        w3 = Web3(Web3.HTTPProvider(env["AMTP_RPC"], request_kwargs={"timeout": 60}))
        if w3.eth.chain_id not in EXPLORERS:
            raise SystemExit("not a known test network")
        chain = ChainAnchor(w3, Account.from_key(env["AMTP_ADMIN_KEY"]), generate_owner_keys=True)
        explorer = f"{EXPLORERS[w3.eth.chain_id]}/address/{chain.address}"
    print(f"RootAnchor {chain.address}  {explorer}", flush=True)

    rows = []
    for d in range(1, a.max_d + 1):
        name = f"D{d}"
        chain.register_domain(name, chain.root_signer(name).public, os.urandom(32))
        reg = chain.txs[-1]
        e, prev = chain.latest("D1", block="latest")
        r_new = os.urandom(32)
        chain.submit("D1", e + 1, r_new, chain.root_signer("D1").sign(transition_message("D1", e + 1, r_new, prev)),
                     prev=prev)
        sub = chain.txs[-1]
        if chain.latest("D1", block="latest") != (e + 1, r_new):
            raise SystemExit("CORRECTNESS GATE FAILED: D1's root on the chain is not the submitted one")
        rows.append({"D": d, "register_gas": reg.gas, "submit_gas": sub.gas, "submit_s": round(sub.seconds, 3),
                     "block": sub.block, "tx": sub.tx})
        print(f"  D={d:>2}  register {reg.gas:>7}  submit {sub.gas:>7}  ({sub.seconds:.1f} s)", flush=True)

    stamp = time.strftime("%Y%m%d_%H%M%S") + ("_local" if a.local else "")
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, f"gas_domains_{stamp}")
    with open(base + ".csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                                capture_output=True, text=True).stdout.strip())
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"command": " ".join(sys.argv), "git_commit": commit, "git_dirty": dirty,
                   "chain_id": chain.chain_id, "contract": chain.address, "explorer": explorer,
                   "machine": platform.platform(), "rows": rows}, f, indent=1)
    print(f"-> {base}.csv / .json")


if __name__ == "__main__":
    main()
