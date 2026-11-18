"""Root Anchor on an Ethereum chain: the client side of chain/RootAnchor.sol.

Drop-in for anchor.RootAnchor (register_domain, submit, latest, R_G): the checks run in the contract,
not in Python. Two ways to get one:

    ChainAnchor.local()       in-process Ethereum (eth-tester + py-evm), contract deployed fresh; for tests
    ChainAnchor.from_env()    a real network: AMTP_RPC, AMTP_ANCHOR_ADDR, AMTP_ADMIN_KEY,
                              AMTP_OWNER_KEY_<DOMAIN> (e.g. AMTP_OWNER_KEY_D1); see chain/README.md

Keys: σ_op (insert / delete requests) stays Ed25519 and is checked by the owner's validator off-chain.
σ_root is signed with the domain's Ethereum key (secp256k1, the ABS stand-in on-chain) and checked by
the contract. The admin key only registers domains and pays gas to relay transitions; it cannot
forge a transition, because the contract checks the owner's signature.
"""
import hashlib
import json
import os
import time
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.exceptions import ContractLogicError

from .anchor import NO_DELTA

ARTIFACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "chain", "RootAnchor.json")


def _artifact():
    with open(ARTIFACT, encoding="utf-8") as f:
        return json.load(f)


def chain_digest(msg: bytes, chain_id: int, address: str) -> bytes:
    """The 32 bytes the owner signs: SHA-256(transition_message ‖ chainid ‖ contract), as
    RootAnchor.transitionDigest computes them (binds σ_root to one chain and one contract)."""
    return hashlib.sha256(msg + chain_id.to_bytes(8, "big") + bytes.fromhex(address[2:])).digest()


class EthRootSigner:
    """σ_root for the chain anchor. `public` is the owner's address, registered as the root-update key."""

    def __init__(self, account, chain_id: int, address: str):
        self._acct, self.chain_id, self.address = account, chain_id, address
        self.public = account.address

    def sign(self, msg: bytes) -> bytes:
        signed = self._acct.sign_message(encode_defunct(primitive=chain_digest(msg, self.chain_id, self.address)))
        return signed.signature            # r ‖ s ‖ v, 65 bytes, low s, v in {27, 28}


@dataclass
class TxRecord:
    op: str
    domain: str
    tx: str
    block: int
    gas: int
    seconds: float          # send -> receipt with the required confirmations


class ChainAnchor:
    def __init__(self, w3: Web3, admin, address: str = None, owner_keys: dict = None,
                 confirmations: int = 1, read_block: str = "latest", generate_owner_keys: bool = False):
        """admin: eth_account LocalAccount (deploys if address is None, registers, relays).
        owner_keys: {domain: LocalAccount}; generate_owner_keys creates missing ones (local chain only).
        read_block: the block the Data User reads roots at ("latest" or "finalized")."""
        self.w3, self.admin = w3, admin
        self.chain_id = w3.eth.chain_id
        self.owner_keys = dict(owner_keys or {})
        self.generate_owner_keys = generate_owner_keys
        self.confirmations, self.read_block = confirmations, read_block
        art = _artifact()
        if address is None:
            c = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
            rcpt = self._send(c.constructor(), "deploy", "")[1]
            address = rcpt["contractAddress"]
        self.address = Web3.to_checksum_address(address)
        self.contract = w3.eth.contract(address=self.address, abi=art["abi"])
        self.domains = []                  # domains this client registered or was told about
        self.txs = []                      # TxRecord of every transaction this client sent

    # ---------------------------------------------------------------- construction

    @classmethod
    def local(cls, **kw):
        """In-process chain (eth-tester): a funded admin, the contract deployed, owner keys generated."""
        from web3 import EthereumTesterProvider
        w3 = Web3(EthereumTesterProvider())
        admin = Account.create()
        w3.eth.send_transaction({"from": w3.eth.accounts[0], "to": admin.address, "value": 10 ** 20})
        return cls(w3, admin, generate_owner_keys=True, **kw)

    @classmethod
    def from_env(cls, env=os.environ, **kw):
        w3 = Web3(Web3.HTTPProvider(env["AMTP_RPC"], request_kwargs={"timeout": 60}))
        admin = Account.from_key(env["AMTP_ADMIN_KEY"])
        owners = {k[len("AMTP_OWNER_KEY_"):]: Account.from_key(v) for k, v in env.items()
                  if k.startswith("AMTP_OWNER_KEY_")}
        kw.setdefault("confirmations", int(env.get("AMTP_CONFIRMATIONS", "1")))
        kw.setdefault("read_block", env.get("AMTP_READ_BLOCK", "latest"))
        return cls(w3, admin, address=env.get("AMTP_ANCHOR_ADDR") or None, owner_keys=owners, **kw)

    # ---------------------------------------------------------------- RootAnchor interface

    def root_signer(self, domain) -> EthRootSigner:
        """The signer DataOwner hands to its validator for σ_root."""
        if domain not in self.owner_keys:
            if not self.generate_owner_keys:
                raise KeyError(f"no Ethereum key for domain {domain} (set AMTP_OWNER_KEY_{domain})")
            self.owner_keys[domain] = Account.create()
        return EthRootSigner(self.owner_keys[domain], self.chain_id, self.address)

    def register_domain(self, domain, owner_public_key, r0: bytes):
        """Setup (eq. 1): owner_public_key is the owner's address (EthRootSigner.public)."""
        self._send(self.contract.functions.register(domain.encode(), owner_public_key, r0), "register", domain)
        if domain not in self.domains:
            self.domains.append(domain)

    def submit(self, domain, epoch, r_d: bytes, sig: bytes, delta: bytes = NO_DELTA, prev: bytes = None):
        if prev is None:
            prev = self.latest(domain, block="latest")[1]
        self._send(self.contract.functions.submit(domain.encode(), epoch, prev, r_d, delta, sig), "submit", domain)

    def latest(self, domain, block=None):
        """What a Data User reads: (e*, R_D^(e*)), at read_block unless given."""
        e, r = self.contract.functions.latest(domain.encode()).call(block_identifier=block or self.read_block)
        return e, bytes(r)

    @property
    def R_G(self) -> bytes:
        return bytes(self.contract.functions.globalRoot().call(block_identifier=self.read_block))

    @property
    def block(self) -> int:
        return self.w3.eth.block_number

    @property
    def current(self) -> dict:
        return {d: self.latest(d) for d in self.domains}

    # ---------------------------------------------------------------- transactions

    def _send(self, fn, op, domain):
        """Sign with the admin key, send, wait for the receipt (+ confirmations). A revert raises
        ValueError with the contract's reason, as RootAnchor raises ValueError."""
        t0 = time.perf_counter()
        try:
            tx = fn.build_transaction({"from": self.admin.address, "chainId": self.w3.eth.chain_id,
                                       "nonce": self.w3.eth.get_transaction_count(self.admin.address, "pending")})
        except Exception as e:                     # gas estimation runs the call: a revert shows here
            if not _is_revert(e):                  # (web3: ContractLogicError; eth-tester: TransactionFailed)
                raise
            raise ValueError(_reason(e)) from None
        h = self.w3.eth.send_raw_transaction(self.admin.sign_transaction(tx).raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=600)
        if rcpt["status"] != 1:
            raise ValueError(f"{op} transaction reverted: {h.hex()}")
        while self.w3.eth.block_number < rcpt["blockNumber"] + self.confirmations - 1:
            time.sleep(1)
        rec = TxRecord(op, domain, "0x" + h.hex().removeprefix("0x"), rcpt["blockNumber"], rcpt["gasUsed"], time.perf_counter() - t0)
        if op != "deploy":
            self.txs.append(rec)
        return rec, rcpt


def _is_revert(e) -> bool:
    return isinstance(e, ContractLogicError) or "execution reverted" in str(e)


def _reason(e) -> str:
    msg = str(e.message if getattr(e, "message", None) else e)
    return msg.split("execution reverted: ", 1)[-1]
