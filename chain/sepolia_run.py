"""A whole AMTP run with the Root Anchor on a public test network (keys and RPC from <repo>/.env).

    .venv/bin/python chain/sepolia_run.py                  # deploys a fresh RootAnchor for this run
    .venv/bin/python chain/sepolia_run.py --address 0x...  # or uses an existing one (domains must be new to it)

The small two-domain world of amtp/scenario.py (A, B; one epoch per document): every update is a contract
transaction signed by the domain's owner key (A: AMTP_OWNER_KEY_D1, B: AMTP_OWNER_KEY_D2) and relayed by the admin;
every query reads (e*, R_D) from the chain. Then honest queries must verify and attacks must be rejected.
Writes a JSON record (transactions, gas, times, verdicts) to --out.
"""
import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "amtp_code"))
sys.path.insert(0, HERE)

from sepolia import EXPLORERS, read_env   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", default=None)
    ap.add_argument("--reads", type=int, default=20, help="latest() calls timed per read block")
    ap.add_argument("--out", default=os.path.join(REPO, "chain", "runs"))
    a = ap.parse_args()

    from eth_account import Account
    from web3 import Web3
    from amtp.chain_anchor import ChainAnchor
    from amtp.scenario import World

    env = read_env()
    w3 = Web3(Web3.HTTPProvider(env["AMTP_RPC"], request_kwargs={"timeout": 60}))
    cid = w3.eth.chain_id
    if cid not in EXPLORERS:
        raise SystemExit(f"chain id {cid} is not a known test network")
    keys = {"A": Account.from_key(env["AMTP_OWNER_KEY_D1"]), "B": Account.from_key(env["AMTP_OWNER_KEY_D2"])}
    t0 = time.perf_counter()
    chain = ChainAnchor(w3, Account.from_key(env["AMTP_ADMIN_KEY"]), address=a.address, owner_keys=keys)
    explorer = EXPLORERS[cid]
    print(f"RootAnchor {chain.address}  {explorer}/address/{chain.address}", flush=True)

    world = World(anchor=chain)                         # registers A, B and runs every start-up epoch on-chain
    print(f"set-up: {len(chain.txs)} transactions in {time.perf_counter() - t0:.0f} s", flush=True)

    def run(uid, domain, text, mode="honest"):
        user = world.users[uid]
        t_q, ctx = user.make_query(domain, text, world.anchor)   # reads (e*, R_D) from the chain
        out = world.adversary.search(t_q, mode)
        rep = user.verify(ctx, json.loads(json.dumps(out["response"])))
        return out, rep

    verdicts = []
    _, rep = run("nina", "A", "(diabetes AND insulin) OR obesity")
    verdicts.append(("honest", "accepted" if rep["accepted"] else f"rejected at {rep['failed']}"))
    run("mali", "A", "insulin")
    for mode in ("tamper_ct", "hide_posting", "forge_partition", "stale", "replay"):
        out, rep = run("mali", "A", "(diabetes AND insulin) OR obesity", mode)
        verdicts.append((mode, "accepted" if rep["accepted"] else f"rejected at {rep['failed']}"))
    n_before = len(chain.txs)
    world.publish_next("A")                             # one more epoch after the queries
    _, rep = run("nina", "A", "insulin")
    verdicts.append(("honest after a new epoch", "accepted" if rep["accepted"] else f"rejected at {rep['failed']}"))
    for v in verdicts:
        print(f"  {v[0]:<26} {v[1]}", flush=True)

    reads = {}
    for blk in ("latest", "finalized"):
        ts, seen = [], None
        for _ in range(a.reads):
            t = time.perf_counter()
            try:
                seen = chain.latest("A", block=blk)[0]
            except Exception:                          # the domain (or contract) is not in a finalized block yet
                seen = None
            ts.append((time.perf_counter() - t) * 1000)
        reads[blk] = {"median_ms": statistics.median(ts), "max_ms": max(ts),
                      "epoch_seen": seen if seen is not None else "not finalized yet"}
    submits = [t for t in chain.txs if t.op == "submit"]
    summary = {
        "chain_id": cid, "contract": chain.address, "explorer": f"{explorer}/address/{chain.address}",
        "transactions": len(chain.txs), "submits": len(submits),
        "submit_seconds_median": statistics.median(t.seconds for t in submits),
        "submit_seconds_max": max(t.seconds for t in submits),
        "submit_gas_median": statistics.median(t.gas for t in submits),
        "register_gas": [t.gas for t in chain.txs if t.op == "register"],
        "read_latest_root": reads, "verdicts": verdicts,
        "epochs": {d: chain.latest(d)[0] for d in ("A", "B")},
        "txs": [t.__dict__ for t in chain.txs], "post_query_epoch_txs": len(chain.txs) - n_before,
    }
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, time.strftime("sepolia_%Y%m%d_%H%M%S.json"))
    json.dump(summary, open(path, "w"), indent=1)
    print(f"submit: median {summary['submit_seconds_median']:.1f} s, max {summary['submit_seconds_max']:.1f} s, "
          f"gas median {summary['submit_gas_median']:.0f}; read latest() median "
          f"{reads['latest']['median_ms']:.0f} ms, finalized {reads["finalized"]["median_ms"]:.0f} ms (epoch seen there: {reads["finalized"]["epoch_seen"]}, latest: {reads["latest"]["epoch_seen"]})")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
