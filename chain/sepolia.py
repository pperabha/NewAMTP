"""Set up the Root Anchor on a public Ethereum network (Sepolia by default). Keys live in <repo>/.env (git-ignored).

    .venv/bin/python chain/sepolia.py keys       # new admin + owner keys into .env; prints the addresses only
    .venv/bin/python chain/sepolia.py status     # network, balances, contract
    .venv/bin/python chain/sepolia.py deploy     # deploy RootAnchor (admin pays gas); writes AMTP_ANCHOR_ADDR to .env

.env holds AMTP_RPC (your RPC URL), AMTP_ADMIN_KEY, AMTP_OWNER_KEY_<domain>, AMTP_ANCHOR_ADDR.
Use these keys on a test network only. Only the admin needs test ETH: it deploys, registers the domains and relays
every transition; the owners only sign.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "amtp_code"))
ENV = os.path.join(REPO, ".env")
EXPLORERS = {11155111: "https://sepolia.etherscan.io", 84532: "https://sepolia.basescan.org",
             421614: "https://sepolia.arbiscan.io"}


def read_env():
    env = {}
    if os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def set_env(key, value):
    lines = open(ENV, encoding="utf-8").read().splitlines() if os.path.exists(ENV) else []
    lines = [l for l in lines if not l.startswith(key + "=")] + [f"{key}={value}"]
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV, 0o600)


def cmd_keys(a):
    from eth_account import Account
    env = read_env()
    names = ["AMTP_ADMIN_KEY"] + [f"AMTP_OWNER_KEY_{d}" for d in a.domains]
    made = []
    for n in names:
        if env.get(n):
            print(f"{n}: kept (already in .env)")
            continue
        set_env(n, Account.create().key.hex())
        made.append(n)
    if "AMTP_RPC" not in env:
        set_env("AMTP_RPC", "")
    env = read_env()
    for n in names:
        print(f"{n[len('AMTP_'):]:<16} {Account.from_key(env[n]).address}")
    print(f"\n{len(made)} new key(s) in {ENV} (git-ignored). Send test ETH to the ADMIN_KEY address only.")


def connect():
    from web3 import Web3
    env = read_env()
    if not env.get("AMTP_RPC"):
        raise SystemExit(f"put your RPC URL in {ENV} as AMTP_RPC=https://...")
    w3 = Web3(Web3.HTTPProvider(env["AMTP_RPC"], request_kwargs={"timeout": 60}))
    if not w3.is_connected():
        raise SystemExit("cannot reach AMTP_RPC")
    return w3, env


def cmd_status(a):
    from eth_account import Account
    w3, env = connect()
    cid = w3.eth.chain_id
    print(f"chain id {cid}, block {w3.eth.block_number}")
    admin = Account.from_key(env["AMTP_ADMIN_KEY"]).address
    print(f"admin {admin}: {w3.from_wei(w3.eth.get_balance(admin), 'ether')} ETH")
    addr = env.get("AMTP_ANCHOR_ADDR")
    if addr:
        from amtp.chain_anchor import ChainAnchor
        c = ChainAnchor(w3, Account.from_key(env["AMTP_ADMIN_KEY"]), address=addr)
        print(f"RootAnchor {addr}: {c.contract.functions.domainCount().call()} domain(s), "
              f"R_G {c.R_G.hex()[:16]}…  {EXPLORERS.get(cid, '')}/address/{addr}")
    else:
        print("RootAnchor: not deployed yet (chain/sepolia.py deploy)")


def cmd_deploy(a):
    from eth_account import Account
    from amtp.chain_anchor import ChainAnchor
    w3, env = connect()
    cid = w3.eth.chain_id
    if cid not in EXPLORERS and not a.any_chain:
        raise SystemExit(f"chain id {cid} is not a known test network (use --any-chain to deploy anyway)")
    if env.get("AMTP_ANCHOR_ADDR") and not a.again:
        raise SystemExit(f"already deployed at {env['AMTP_ANCHOR_ADDR']} (use --again for a new contract)")
    admin = Account.from_key(env["AMTP_ADMIN_KEY"])
    if w3.eth.get_balance(admin.address) == 0:
        raise SystemExit(f"admin {admin.address} has no ETH: get test ETH from a faucet first")
    c = ChainAnchor(w3, admin)
    set_env("AMTP_ANCHOR_ADDR", c.address)
    print(f"RootAnchor deployed at {c.address}\n{EXPLORERS.get(cid, '')}/address/{c.address}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keys")
    k.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"])
    sub.add_parser("status")
    d = sub.add_parser("deploy")
    d.add_argument("--again", action="store_true")
    d.add_argument("--any-chain", action="store_true")
    a = ap.parse_args()
    {"keys": cmd_keys, "status": cmd_status, "deploy": cmd_deploy}[a.cmd](a)


if __name__ == "__main__":
    main()
