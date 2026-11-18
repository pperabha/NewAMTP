"""Data Owner side (Phases 1-3): encrypt, sign update requests, validate the server's proposed
transition and authorize it on the Root Anchor.

  Phase 1   encrypt: CT_d (raw bytes), cid_d = H(CT_d), C(d) = {DEnc_Ks(Norm(w))}, h_w = H(C_w)
  Phase 2   insert_request / delete_request: U_op signed with σ_op (eq. 8-11)
            update: CS prepares the candidate -> this owner's Validator checks it and signs σ_root
            -> the Root Anchor accepts (e* + 1) -> the CS exposes the new snapshot
  Doc_i / Loc_i / Fwd_i and the partition descriptors are the Validator's trusted metadata.
"""
import os

from .core.crypto import Signer, keyword_cipher, make_ct
from .core.hashing import H, enc
from .dht import ciphertext_id
from .index import extract_keywords
from .nlp import norm
from .update import genesis_root, request_digest
from .validator import Validator
from .variants import AdaptivePolicy


class DomainKeys:
    """Per-domain secrets issued by the Domain Authority.
    K_s: keyword key (never given to the Cloud Server)
    K_a: query-authentication key (shared with authorised users and the CS)"""

    def __init__(self):
        self.k_s = os.urandom(64)   # AES-SIV-256 key
        self.k_a = os.urandom(32)


def keyword_key(k_s: bytes, word: str) -> bytes:
    """h_w = H(C_w) with C_w = DEnc_{K_s}(Norm(w)). Every keyword, at upload and in a query,
    goes through this one function, so index and query use the same Norm."""
    return H(keyword_cipher(k_s, norm(word)))


def keyword_ciphers(k_s: bytes, words) -> list:
    """C(d) = {C_w = DEnc_{K_s}(Norm(w))}, canonically ordered."""
    return sorted({keyword_cipher(k_s, norm(w)) for w in words if norm(w)})


class DataOwner:
    def __init__(self, domain, name, keys: DomainKeys, authority, anchor, server,
                 theta_min=1, theta_max=4, ops_per_epoch=1, policy=None):
        self.domain, self.name = domain, name
        self.keys, self.authority = keys, authority
        self.anchor, self.server = anchor, server
        self.signer = Signer()                    # ABS stand-in: signs σ_op (and σ_root, in-process anchor)
        # σ_root key: an anchor on a chain supplies the key its contract checks (chain_anchor.py)
        root_signer = anchor.root_signer(domain) if hasattr(anchor, "root_signer") else self.signer
        self.policy = policy or AdaptivePolicy(1, theta_min, theta_max)
        self.ops_per_epoch = ops_per_epoch
        genesis = server.create_domain(domain, self.policy, [self.signer.public], ops_per_epoch)
        self.validator = Validator(domain, root_signer, self.policy, genesis, [self.signer.public])
        anchor.register_domain(domain, root_signer.public, genesis_root(domain, genesis))
        self.structure_log = []                   # split / merge records, for the demo

    # trusted metadata (Doc_i, Loc_i, Fwd_i) lives in the validator
    @property
    def doc(self):
        return self.validator.doc

    @property
    def loc(self):
        return self.validator.loc

    @property
    def fwd(self):
        return self.validator.fwd

    @property
    def epoch(self):
        return self.validator.epoch

    # ---------- Phase 1 ----------
    def encrypt(self, doc: dict):
        """CT_d = <E_d, C_Kd, aad_d> as raw bytes, cid_d = H(CT_d), and C(d)."""
        k_d = os.urandom(32)
        aad = {"domain": self.domain, "doc": doc["id"]}           # aad_d = Encode(i, id_d), eq. (2) of (32)
        body = enc({"title": doc["title"], "body": doc["body"]})
        ct = make_ct(k_d, body, self.authority.wrap(k_d, doc["policy"]), aad)   # raw bytes
        # W(d): taken from the shared dataset (documents.csv) when given, so AMTP indexes exactly
        # the keyword sets every baseline uses; otherwise the demo extractor is applied.
        if doc.get("keywords") is not None:
            words = [k for k in doc["keywords"] if k and k.strip()]
        else:
            words = extract_keywords(doc["title"] + " " + doc["body"])
        c_d = keyword_ciphers(self.keys.k_s, words)
        return ct, ciphertext_id(ct), c_d

    # ---------- Phase 2: signed requests ----------
    def _signed(self, u):
        return {"U": u, "sig": self.signer.sign(request_digest(u))}

    def insert_request(self, doc: dict, bucket: int = 0):
        """<U_d, σ_d> of eqs. (8)-(9) of (32) (= U_ins, σ_op of the insertion); `bucket` is the placement
        hint for the CS, outside U_d and the signature."""
        ct, _, c_d = self.encrypt(doc)
        e_star, _ = self.anchor.latest(self.domain)
        req = self._signed({"domain": self.domain, "op": "insert", "epoch": e_star,
                            "nonce": os.urandom(16).hex(), "id": doc["id"], "ct": ct, "C": c_d})
        req["bucket"] = bucket
        return req

    def delete_request(self, doc_id: str):
        e_star, _ = self.anchor.latest(self.domain)
        return self._signed({"domain": self.domain, "op": "delete", "epoch": e_star,
                             "nonce": os.urandom(16).hex(), "id": doc_id, "cid": self.doc[doc_id]})

    # ---------- Phase 2, Step 5: validate, authorize, anchor ----------
    def update(self, requests):
        """One epoch: the CS prepares the candidate, this owner validates it and signs σ_root,
        the Root Anchor accepts it, then both sides advance. Raises validator.Invalid."""
        proposal = self.server.prepare_update(self.domain, requests)
        try:
            sig = self.validator.check(proposal, requests)
            self.anchor.submit(self.domain, proposal["epoch_new"], proposal["R_new"], sig,
                               proposal["delta"], prev=proposal["R_old"])
        except Exception:
            self.server.abort_update(self.domain)     # the CS falls back to the finalized state
            raise
        self.validator.advance()
        self.structure_log += [r for r in proposal["aff"] if r[0] in ("split", "merge")]
        return self.server.finalize_update(self.domain)

    def add_documents(self, docs):
        """Insert documents, b per epoch (b = ops_per_epoch). Returns the last snapshot."""
        state = None
        for i in range(0, len(docs), self.ops_per_epoch):
            state = self.update([self.insert_request(d) for d in docs[i:i + self.ops_per_epoch]])
        return state

    def delete_documents(self, doc_ids):
        state = None
        for i in range(0, len(doc_ids), self.ops_per_epoch):
            state = self.update([self.delete_request(d) for d in doc_ids[i:i + self.ops_per_epoch]])
        return state
