# Root Anchor on Ethereum

`RootAnchor.sol` is the Root Anchor (RA) of the paper as a smart contract: it stores `(e*, R_D)` per domain, accepts
a transition only if the predecessor is the anchored root, the epoch is `e* + 1` and the domain's root-update key
signed it, and recomputes the Global Root `R_G`. Only roots go on-chain. `amtp_code/amtp/chain_anchor.py` is the
client: a drop-in for the in-process `amtp/anchor.py` (`register_domain`, `submit`, `latest`, `R_G`).

| | in-process anchor (default) | chain anchor |
|---|---|---|
| checks | Python (`anchor.py`) | the contract |
| σ_root (ABS stand-in) | Ed25519 | secp256k1 ECDSA, bound to the chain id and the contract address |
| σ_op (requests) | Ed25519, checked by the owner's validator | same |
| R_G | Python | the contract (byte-identical, tested) |

The hashes in the contract match `core/hashing.py` and `core/merkle.py` byte for byte, and `tests/test_chain_anchor.py`
checks it.

## Install and test (no network needed)

```bash
.venv/bin/pip install -r chain/requirements.txt        # AMTP + web3 + an in-process Ethereum (eth-tester)
cd amtp_code && ../.venv/bin/python -m pytest -q tests/test_chain_anchor.py
```

The tests deploy the contract on an in-process chain and check: the same `R_G` and signed digest as Python; every
rejection (skipped epoch, wrong predecessor, another domain's key, a signature on another root, a malleated
signature, a replay, a second registration, a non-admin registration, a signature from another deployment); and a
whole AMTP run (updates as contract transactions, searches that read the root from the chain, attacks rejected).
Without web3 installed these tests are skipped and everything else runs as before.

## On Sepolia (a public test network)

1. **Keys** (once): `.venv/bin/python chain/sepolia.py keys` writes an admin key and one owner key per domain
   (D1-D4) into `<repo>/.env` (git-ignored, mode 600) and prints the addresses. Test networks only.
2. **RPC URL**: create a free Sepolia endpoint (Alchemy or Infura) and put it in `.env` as `AMTP_RPC=https://...`.
3. **Test ETH**: send Sepolia ETH from a faucet to the **admin** address (well under 0.1 ETH is enough). The owners
   only sign; the admin pays gas for deployment, registration and every relayed transition.
4. **Deploy**: `.venv/bin/python chain/sepolia.py deploy` (writes `AMTP_ANCHOR_ADDR` to `.env`), then
   `.venv/bin/python chain/sepolia.py status`.

In code: `ChainAnchor.from_env()` reads `.env`'s variables from the environment (`set -a; source .env; set +a`).
`AMTP_CONFIRMATIONS` (default 1) is how many blocks a transition waits for; `AMTP_READ_BLOCK` (`latest` or
`finalized`) is the block the Data User reads roots at.

## Rebuild the contract

`RootAnchor.json` (ABI + bytecode) is committed, so running needs no compiler. After editing the contract:
`.venv/bin/python chain/build.py` (solc 0.8.28 through py-solc-x, EVM `cancun`).
