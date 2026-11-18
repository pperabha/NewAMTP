"""AMTP on the shared dataset-v4, in the same format as the baselines (Section V).

    python -m bench.experiments exp1                 # replay baselines/results/exp1_queries.json (N = 10k..200k)
    python -m bench.experiments exp2-layouts         # write the shared baselines/results/exp2_layouts.json (N = 200k)
    python -m bench.experiments exp2                 # selective proof vs r_Q, every layout of that file
    python -m bench.experiments exp3                 # insert / delete batches of 1, 10, 100, 1000
    python -m bench.experiments exp5                 # 1..32 domains, replays baselines/results/exp5_workload.json
    python -m bench.experiments theta --n 200000     # θ_max sweep (θ_min = θ_max/4): query vs update cost
  dataset-v4 suites (advisor's plan; workload files in datasets/arxiv/data_v4/, the same for every scheme):
    python -m bench.experiments search1              # Search 1.1/1.2: single-domain AND queries, files/domain 10k..125k
    python -m bench.experiments verify1              # Verify 1.1: real keywords with ~10..10,000 results, one domain
    python -m bench.experiments tamper               # Verify 1.2: server modifies / hides t of ~2,000 results
    python -m bench.experiments xsearch              # Search 2.1: Boolean AND/OR queries over the 4 domains
    python -m bench.experiments xverify              # Verify 2.1: multi-domain keywords with ~10..10,000 results
    python -m bench.experiments xdomains             # Search/Verify 2.2: the same files as D = 1..32 domains
    (Exp. 4, adaptive vs Static-MT / Global-MT: python -m bench.ablation --source arxiv)

Everything runs the real AMTP code: Engine (Phases 2-3, incremental), RootAnchor with an
owner-signed transition, CloudServer admission + build_response (Phase 4, ASPA) and
DataUser.verify (Phase 5, all seven checks). Documents are the baselines' documents:
amtp_dataset.sample(N), W(d) from documents.csv, real file text encrypted with AES-GCM,
keyword keys h_w = H(AES-SIV_{K_s}(w)). Every measured query must be accepted and must
return exactly the plaintext ground truth, otherwise the run stops.

Results go to baselines/results/amtp/amtp_<suite>.csv with the baselines' columns
(<metric>_ms, _ms_median, _ms_std over --reps runs after --warmup runs), so
baselines/plot_results.py can draw AMTP next to Chen, Du and SE-COLLAB.

Choices (state them in the paper):
  * Exp. 1 / 2 / 3 put all N documents in ONE domain, i.e. the same collection every
    baseline searches; multi-domain behaviour is Exp. 5 and xdomain.
  * Every domain has its own keys (K_s, K_a), so the same word has a different h_w per domain.
    Cross-domain search follows the paper: one domain-bound query per domain, each verified
    against its own Domain Root (no shared index, no cross-domain snapshot).
  * Placement: a file goes to the least occupied partition serving its bucket
    (bucket = arXiv primary category folded into --buckets groups), as in bench.ablation.
  * Exp. 3 freezes the partitions (StaticPolicy): the paper excludes split/merge from Exp. 3.
  * Every update (exp3, theta, exp5) runs the same Phase 2 protocol (class Protocol): b signed requests
    are one epoch; update = owner request (tokens + σ_op) + CS prepare + owner Validator + Root Anchor
    (file encryption reported apart as encrypt).
  * search1 runs only the points the figures use (every k_Q at --fix files, k_Q = --s1-kq at every size);
    --all-points runs every query at every size.
  * end_to_end = query_gen + server_total + verify_total; decrypting the returned files
    (CP-ABE stand-in + AES-GCM) is reported separately as du_decrypt.
  * Sizes follow baselines/wire_sizes.py (binary: hash 32 B, numbers 8 B, ciphertexts their real
    length) for every scheme; proof_bytes excludes the files, response_bytes includes them.
  * Times are split by phase: query_gen; server_admission / _lookup / _eval / _proof / _fetch
    (server_total); verify_idx / _papc / _part / _comp / _ct (verify_total); du_decrypt.
  * exp3 runs the Phase 2 protocol: b signed requests form one epoch; prepare (CS: apply, adapt,
    repair, Aff_i, Δ_i, π^upd), validate (owner Validator, σ_root) and anchor are timed apart.
"""
import argparse
import csv
import gc
import json
import os
import re
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amtp.core import boolean                                    # noqa: E402
from amtp.anchor import RootAnchor, transition_message           # noqa: E402
from amtp.core.crypto import Signer, make_authority, make_ct          # noqa: E402
from amtp.dht import ciphertext_id                               # noqa: E402
from amtp.engine import Engine
from amtp.index import (set_and_plan_greedy, set_and_prune, set_gamma_v, set_part_leaf,  # noqa: E402
                        set_part_results)
from amtp.core.hashing import HashCounter, enc                   # noqa: E402
from amtp.core.crypto import keyword_cipher                      # noqa: E402
from amtp.nlp import norm                                         # noqa: E402
from amtp.owner import DomainKeys, keyword_key                   # noqa: E402
from amtp.update import request_digest                           # noqa: E402
from amtp.validator import Validator                             # noqa: E402
from amtp.adversary import flip_one_byte                         # noqa: E402
from amtp.server import CloudServer, build_response              # noqa: E402
from amtp.user import DataUser, Reject                           # noqa: E402
from amtp.variants import PLACEMENTS, AdaptivePolicy, StaticPolicy   # noqa: E402
from bench.workload import REPO_ROOT, _primary_categories, arxiv_loader   # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "baselines"))
import wire_sizes as W                                           # noqa: E402  (one size rule, every scheme)

RESULTS = os.path.join(REPO_ROOT, "baselines", "results")
DEFAULT_QUERIES = os.path.join(RESULTS, "exp1_queries.json")
OUT = os.path.join(RESULTS, "amtp")
POLICY = "auditor"


# ---------------------------------------------------------------- documents
class Corpus:
    """Encrypts each dataset document once (Phase 1) and caches the result,
    so every N reuses the same ciphertexts and keyword keys."""

    def __init__(self, a):
        self.D = arxiv_loader()
        self.data = a.data
        self.keys = {}                                  # domain -> DomainKeys (K_s, K_a), one pair per domain
        self.authority = make_authority()
        cat = _primary_categories(self.D.load(a.data)["dir"])
        groups = sorted(set(cat.values()) | set(self.D.DOMAINS))
        self.bucket_of = {g: i % a.buckets for i, g in enumerate(groups)}
        self.cat = cat
        self._h, self._docs = {}, {}

    def keys_for(self, domain):
        if domain not in self.keys:
            self.keys[domain] = DomainKeys()
        return self.keys[domain]

    def c(self, word, domain):
        """C_w = DEnc_{K_s}(Norm(w)) under the domain's own K_s (h_w = H(C_w))."""
        if (domain, "C", word) not in self._h:
            self._h[(domain, "C", word)] = keyword_cipher(self.keys_for(domain).k_s, norm(word))
        return self._h[(domain, "C", word)]

    def encrypt_fresh(self, doc, domain):
        """Phase 1 file encryption of one document, new every call (not part of the update time)."""
        self._docs.pop((doc.doc_id, domain), None)
        return self.encrypt(doc, domain)

    def insert_request(self, encrypted, doc, domain, epoch, signer):
        """The signed insert request U_ins (Phase 2) for an encrypted document: the keyword tokens
        C(d) = {DEnc_{K_s}(Norm(w))} computed fresh (never from the cache), then σ_op. Part of the update time,
        as Chen's update counts its owner-side token generation."""
        cid, ct, _, bucket = encrypted
        k_s = self.keys_for(domain).k_s
        u = {"domain": domain, "op": "insert", "epoch": epoch, "nonce": os.urandom(16).hex(),
             "id": doc.doc_id, "ct": ct, "bucket": bucket,
             "C": sorted({keyword_cipher(k_s, norm(w)) for w in doc.keywords})}
        return {"U": u, "sig": signer.sign(request_digest(u))}

    @staticmethod
    def delete_request(doc_id, cid, domain, epoch, signer):
        u = {"domain": domain, "op": "delete", "epoch": epoch, "nonce": os.urandom(16).hex(), "id": doc_id, "cid": cid}
        return {"U": u, "sig": signer.sign(request_digest(u))}

    def h(self, word, domain):
        """h_w under the domain's own K_s (the same word has a different key in every domain)"""
        if (domain, word) not in self._h:
            self._h[(domain, word)] = keyword_key(self.keys_for(domain).k_s, word)
        return self._h[(domain, word)]

    def encrypt(self, doc, domain):
        """Phase 1 for one document: (cid, CT, keyword keys, bucket)."""
        key = (doc.doc_id, domain)
        if key not in self._docs:
            k_d = os.urandom(32)
            aad = {"domain": domain, "doc": doc.doc_id, "policy": POLICY}
            body = enc({"title": doc.doc_id,
                        "body": self.D.read_bytes(doc, self.data).decode("utf-8", "replace")})
            ct = make_ct(k_d, body, self.authority.wrap(k_d, POLICY), aad)    # raw CT bytes
            bucket = self.bucket_of[self.cat.get(doc.doc_id, doc.domain)]
            self._docs[key] = (ciphertext_id(ct), ct, frozenset(self.h(w, domain) for w in doc.keywords), bucket)
        return self._docs[key]

    def encrypt_version(self, doc, domain, suffix):
        """Another valid ciphertext of the same document with `suffix` appended (an older version of the file)."""
        k_d = os.urandom(32)
        aad = {"domain": domain, "doc": doc.doc_id, "policy": POLICY}
        body = enc({"title": doc.doc_id,
                    "body": (self.D.read_bytes(doc, self.data) + suffix).decode("utf-8", "replace")})
        return make_ct(k_d, body, self.authority.wrap(k_d, POLICY), aad)

    def user(self, domains):
        return DataUser("du", "du", "", [POLICY], self.authority.user_keys([POLICY]),
                        {d: self.keys_for(d) for d in domains})


def make_anchor():
    """The Root Anchor of a benchmark run: in-process (default, every result of the paper) or, with
    AMTP_ANCHOR=chain, a fresh RootAnchor contract on the network of <repo>/.env (chain/README.md);
    AMTP_ANCHOR=chain-local: the same contract on an in-process chain (eth-tester), to check a run."""
    mode = os.environ.get("AMTP_ANCHOR", "in-process")
    if mode == "in-process":
        return RootAnchor()
    from amtp.chain_anchor import ChainAnchor
    if mode == "chain-local":
        return ChainAnchor.local()
    if mode != "chain":
        raise SystemExit(f"AMTP_ANCHOR must be in-process, chain or chain-local, not {mode}")
    sys.path.insert(0, os.path.join(REPO_ROOT, "chain"))
    from sepolia import read_env
    env = {k: v for k, v in read_env().items() if k != "AMTP_ANCHOR_ADDR"}      # a fresh contract per build
    anchor = ChainAnchor.from_env(env)
    anchor.generate_owner_keys = True              # domain names of a run ("D", D1..): keys made for the run
    print(f" Root Anchor contract {anchor.address} (chain id {anchor.chain_id})", flush=True)
    return anchor


class Domain:
    """One AMTP domain: engine + owner signer, registered on the anchor and the server."""

    def __init__(self, name, corpus, docs, a, anchor, server, policy=None, extra_words=None):
        self.name, self.corpus = name, corpus
        self.signer = Signer()                     # σ_op (and σ_root with the in-process anchor)
        # σ_root: an anchor on a chain supplies the key its contract checks (amtp/chain_anchor.py)
        self.root_signer = anchor.root_signer(name) if hasattr(anchor, "root_signer") else self.signer
        server.register_query_key(name, corpus.keys_for(name).k_a)
        self.anchor, self.server = anchor, server
        self.eng = Engine(name, policy or AdaptivePolicy(a.buckets, a.theta_min, a.theta_max, a.placement))
        anchor.register_domain(name, self.root_signer.public, self.eng.R_D)      # R^(0)
        self.cids = []
        self.doc_ids = [d.doc_id for d in docs]
        for i, d in enumerate(docs):
            cid, ct, keys, bucket = corpus.encrypt(d, name)
            if extra_words and i in extra_words:
                keys = keys | {corpus.h(w, name) for w in extra_words[i]}
            server.store_ciphertext(cid, ct)
            self.eng.insert(cid, keys, bucket)
            self.cids.append(cid)
        self.eng.commit()
        self.finalize()

    def finalize(self):
        """Owner signs the transition, the anchor accepts it, the server exposes the snapshot."""
        _, prev = self.anchor.latest(self.name)
        sig = self.root_signer.sign(transition_message(self.name, self.eng.epoch, self.eng.R_D, prev))
        self.anchor.submit(self.name, self.eng.epoch, self.eng.R_D, sig)

    def publish_snapshot(self):
        state = self.eng.snapshot()
        if state.R_D != self.eng.R_D:
            raise SystemExit("CORRECTNESS GATE FAILED: incremental R_D != full rebuild")
        self.server.store_state(state)
        return state


class Protocol:
    """The Phase 2 update protocol on a bulk-loaded Domain (one code path for exp3, theta and exp5):
    the CS prepares the candidate (prepare_update: admit, apply, adapt, repair, Aff_i, Δ_i, π^upd), the owner's
    Validator checks it and signs σ_root, the Root Anchor checks predecessor and e* + 1. The bulk-loaded start
    state is trusted by the Validator (Validator.bootstrap); every measured update is fully validated."""

    def __init__(self, dom, policy=None):
        eng, server = dom.eng, dom.server
        if policy is not None:
            eng.policy = policy
        docs = dict(zip(dom.doc_ids, dom.cids))
        server.engines[dom.name], server.owner_keys[dom.name] = eng, [dom.signer.public]
        server.docs[dom.name] = dict(docs)
        self.dom = dom
        self.val = Validator.bootstrap(dom.name, dom.root_signer, eng.policy, eng, docs, [dom.signer.public])

    def epoch(self, make_requests):
        """One epoch; make_requests() builds the b signed requests (the owner's tokens + σ_op, files already
        encrypted). Returns ({request, server, validate, anchor, update, commit} ms, the CS's stats);
        update = request + server + validate + anchor."""
        dom = self.dom
        tr = time.perf_counter()
        requests = make_requests()
        t0 = time.perf_counter()
        prop = dom.server.prepare_update(dom.name, requests)
        t1 = time.perf_counter()
        sig = self.val.check(prop, requests)
        t2 = time.perf_counter()
        dom.anchor.submit(dom.name, prop["epoch_new"], prop["R_new"], sig, prop["delta"], prev=prop["R_old"])
        t3 = time.perf_counter()
        self.val.advance()
        dom.server.finalize_update(dom.name, snapshot=False)
        return {"request": (t0 - tr) * 1e3, "server": (t1 - t0) * 1e3, "validate": (t2 - t1) * 1e3,
                "anchor": (t3 - t2) * 1e3, "update": (t3 - tr) * 1e3,
                "commit": prop["stats"]["update_ms"]}, prop["stats"]

    def check(self):
        eng = self.dom.eng
        if eng.snapshot().R_D != eng.R_D or self.val.R_D != eng.R_D or self.dom.anchor.latest(self.dom.name)[1] != eng.R_D:
            raise SystemExit("CORRECTNESS GATE FAILED: incremental R_D != full rebuild / validator / anchor")


# ---------------------------------------------------------------- queries
_OPS = re.compile(r"(\(|\)|\bAND\b|\bOR\b)")


def quote_terms(query):
    """Shared queries write multi-word keywords without quotes; AMTP's parser wants them quoted."""
    parts = [p.strip() for p in _OPS.split(query)]
    return " ".join(p if p in ("(", ")", "AND", "OR") else f'"{p}"' for p in parts if p)


def ground_truth(text, inv, cids):
    """Evaluate the query on plaintext keyword sets (positions -> cids)."""
    ast = boolean.parse(text)
    sets = {w: inv.get(w, set()) for w in boolean.leaves(ast)}
    return {cids[i].hex() for i in boolean.evaluate(ast, sets)}


def load_queries(path, explicit):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        print(f"[queries] replay {os.path.relpath(path)} ({len(rows)} queries)")
        return rows
    if explicit:
        raise SystemExit(f"query file not found: {path}")
    raise SystemExit(f"{path} not found: run a baseline's exp1 first (it writes the shared queries)")


class AnchorRead:
    """The (e*, R_D) the DU has just read from the Root Anchor, handed to make_query unchanged. The read is a contract
    call (an RPC) when the anchor is on a chain, so it is timed on its own (anchor_read) and query_gen stays the
    trapdoor only, the same work as every baseline's query generation."""

    def __init__(self, domain, latest):
        self.domain, self.value = domain, latest

    def latest(self, domain):
        if domain != self.domain:
            raise ValueError(f"anchor read for {self.domain}, asked for {domain}")
        return self.value


def run_query(dom, state, user, text):
    """One full query: anchor read -> trapdoor -> admission + ASPA response -> 7 checks -> decrypt."""
    ta = time.perf_counter()
    read = AnchorRead(dom.name, dom.anchor.latest(dom.name))   # Phase 4 Step 1: the DU reads (e*, R_D) from the RA
    t0 = time.perf_counter()
    t_q, ctx = user.make_query(dom.name, text, read)
    t1 = time.perf_counter()
    h0 = HashCounter.calls
    reason = dom.server._admit(t_q)                     # same admission as CloudServer.search
    if reason:
        raise SystemExit(f"query rejected at admission: {reason}")
    t_adm = time.perf_counter()
    phase = {}
    resp = build_response(state, boolean.from_json(t_q["B_Q"]), t_q["nonce"], dom.server.dht, timing=phase)
    for desc in resp["proof"]["partitions"]:
        desc.pop("_positions", None)
    t2 = time.perf_counter()
    h1 = HashCounter.calls
    resp = json.loads(json.dumps(resp))                 # what travels to the user (not timed)
    t3 = time.perf_counter()
    rep = user.verify(ctx, resp)
    t4 = time.perf_counter()
    h2 = HashCounter.calls
    if not rep["accepted"]:
        raise SystemExit(f"CORRECTNESS GATE FAILED: honest query rejected at {rep['failed']}")
    t5 = time.perf_counter()
    opened = user.decrypt(resp)
    t6 = time.perf_counter()
    if any(o["status"] != "open" for o in opened):
        raise SystemExit("CORRECTNESS GATE FAILED: an authorised user could not decrypt a result")
    vp = rep["phase_ms"]
    times = {"anchor_read": (t0 - ta) * 1e3, "query_gen": (t1 - t0) * 1e3,
             "server_admission": (t_adm - t1) * 1e3, "server_lookup": phase["lookup"],
             "server_eval": phase["eval"], "server_proof": phase["proof"], "server_fetch": phase["fetch"],
             "server_total": (t2 - t1) * 1e3,
             "verify_idx": vp["idx"], "verify_papc": vp["papc"], "verify_part": vp["part"],
             "verify_comp": vp["comp"], "verify_ct": vp["ct"], "verify_total": (t4 - t3) * 1e3,
             "du_decrypt": (t6 - t5) * 1e3,
             "end_to_end": (t1 - t0 + t2 - t1 + t4 - t3) * 1e3,
             "end_to_end_anchor": (t0 - ta + t1 - t0 + t2 - t1 + t4 - t3) * 1e3}   # + the DU's anchor read
    ev = resp["proof"]["evidence"]
    info = {"rQ": len(resp["R_ct"]),
            "pQ": sum(len(c) for e in ev if e["status"] == "present"
                      for c in ([c for _, _, c in e["segs"]] if e.get("mode") == "focus" else [c for _, c in e["L"]])),
            "sQ": len(resp["proof"]["partitions"]),
            "keys_absent": sum(e["status"] == "absent" for e in ev),
            "proof_bytes": W.amtp_proof_bytes(resp["proof"]), "token_bytes": W.amtp_token_bytes(t_q),
            "response_bytes": W.amtp_response_bytes(resp), "hash_server": h1 - h0, "hash_verify": h2 - h1,
            "ids": {r["cid"] for r in resp["R_ct"]}}
    return times, info


def measure_fn(fn, a):
    """--warmup unrecorded runs of fn(), then --reps recorded ones with the GC off.
    fn() returns (times, info); returns (summary of times, last info, every recorded info)."""
    for _ in range(a.warmup):
        fn()
    samples, infos = [], []
    gc.disable()
    try:
        for _ in range(max(1, a.reps)):
            m, info = fn()
            samples.append(m)
            infos.append(info)
    finally:
        gc.enable()
    return summarize(samples), infos[-1], infos


def measure(dom, state, user, text, a):
    res, info, _ = measure_fn(lambda: run_query(dom, state, user, text), a)
    return res, info


_SUM = ("rQ", "pQ", "sQ", "keys_absent", "proof_bytes", "token_bytes", "response_bytes", "hash_server", "hash_verify")


def run_xquery(doms, states, user, text):
    """Cross-domain search as the paper defines it (System model, last paragraph): the user sends one
    domain-bound query per domain and verifies each response against that domain's own anchored root.
    Times and sizes are summed over the domains (sequential, one user); ids = union of the results,
    rQ_per_domain = result count of every domain in order."""
    times, info = {}, {k: 0 for k in _SUM}
    ids, per = set(), []
    for dom, state in zip(doms, states):
        t, i = run_query(dom, state, user, text)
        for k, v in t.items():
            times[k] = times.get(k, 0.0) + v
        for k in _SUM:
            info[k] += i[k]
        ids |= i["ids"]
        per.append(i["rQ"])
    info["ids"], info["rQ_per_domain"] = ids, per
    return times, info


def tamper_response(resp, kind, targets, extra=None):
    """The server's cheat on t files, the same changes as the CloudServer modes (amtp/server.py), with the honest proof:
      modify      flip one byte of the raw CT bytes of the returned files in `targets` (tamper_ct)
      hide        leave the files in `targets` out of R_ct (drop_result)
      inject      add the R_ct entries in `extra` (files that do not match the query; extra_result)
      old_version replace the ciphertext of the files in `targets` by extra[cid], an older version of the file"""
    if kind == "modify":
        for r in resp["R_ct"]:
            if r["cid"] in targets:
                r["ct"] = flip_one_byte(r["ct"])
    elif kind == "hide":
        resp["R_ct"] = [r for r in resp["R_ct"] if r["cid"] not in targets]
    elif kind == "inject":
        resp["R_ct"] = resp["R_ct"] + list(extra)
    elif kind == "old_version":
        for r in resp["R_ct"]:
            if r["cid"] in targets:
                r["ct"] = extra[r["cid"]].hex()
    else:
        raise ValueError(kind)


def full_check(user, ctx, resp):
    """Full check: verify the proof, then check EVERY returned file instead of stopping at the first fault, and
    count the files the user can name as wrong: modified (H(CT) != cid), not matching the query, or missing.
    Returns -1 if the proof itself is invalid (then no file can be named)."""
    try:
        m_h = user._check_ctx_anchor_idx(ctx, resp, {})
        descs = user._check_papc(resp, m_h, {})
        user._check_partitions(resp, m_h, descs, {})
    except Reject:
        return -1
    m_hat = boolean.evaluate(boolean.from_json(ctx["B_Q"]), m_h)
    proj = {(r["cid"], r["pid"], r["loc"]) for r in resp["R_ct"]}
    modified = sum(ciphertext_id(bytes.fromhex(r["ct"])).hex() != r["cid"] for r in resp["R_ct"])
    return len(m_hat - proj) + len(proj - m_hat) + modified


def run_tampered(dom, state, user, text, kind, targets, extra=None):
    """One query whose response the server tampered with. Times the user's normal verification (early abort:
    stops at the first failed check) and the full check (every file, names the wrong ones).
    Returns detected = rejected, the first Phase 5 check that failed and the number of files named."""
    t_q, ctx = user.make_query(dom.name, text, dom.anchor)
    if dom.server._admit(t_q):
        raise SystemExit("query rejected at admission")
    resp = build_response(state, boolean.from_json(t_q["B_Q"]), t_q["nonce"], dom.server.dht)
    for desc in resp["proof"]["partitions"]:
        desc.pop("_positions", None)
    if targets or extra:
        tamper_response(resp, kind, targets, extra)
    resp = json.loads(json.dumps(resp))
    t0 = time.perf_counter()
    rep = user.verify(ctx, resp)
    t1 = time.perf_counter()
    localized = full_check(user, ctx, resp)
    t2 = time.perf_counter()
    return ({"verify_total": (t1 - t0) * 1e3, "full_check": (t2 - t1) * 1e3},
            {"detected": not rep["accepted"], "failed": rep["failed"] or "", "localized": localized})


# ---------------------------------------------------------------- output (same as the baselines)
class Writer:
    """Collects rows, prints them without _std/_median, writes <out>/amtp_<name>.csv on close()."""

    def __init__(self, name, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        self.path = os.path.join(out_dir, f"amtp_{name}.csv")
        self.rows = []

    def add(self, **row):
        self.rows.append(row)
        show = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()
                if not k.endswith("_std") and not k.endswith("_median")}
        print("  " + "  ".join(f"{k}={v}" for k, v in show.items()), flush=True)

    def close(self):
        if not self.rows:
            return
        keys = list(dict.fromkeys(k for r in self.rows for k in r))
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self.rows)
        print(f"-> {os.path.relpath(self.path)}")
        arxiv_loader().write_manifest(self.path)              # machine / commit / command: <csv>.manifest.json


def summarize(samples, prefix=""):
    """<name>_ms (mean), <name>_ms_median, <name>_ms_std, like every baseline."""
    out = {}
    for k in samples[0]:
        v = [s[k] for s in samples]
        out[f"{prefix}{k}_ms"] = st.mean(v)
        out[f"{prefix}{k}_ms_median"] = st.median(v)
        out[f"{prefix}{k}_ms_std"] = st.pstdev(v)
    return out


def setup(name, corpus, docs, a, policy=None, extra_words=None):
    anchor, server = make_anchor(), CloudServer()
    t0 = time.perf_counter()
    dom = Domain(name, corpus, docs, a, anchor, server, policy, extra_words)
    state = dom.publish_snapshot()
    lay = dom.eng.layout()
    print(f" N={len(docs)}: setup={time.perf_counter() - t0:.1f}s partitions={lay['partitions']} "
          f"max={lay['max_partition']} keys={lay['keys']}", flush=True)
    return dom, state, lay


# ---------------------------------------------------------------- experiments
def suite_exp1(a):
    """Exp. 1: replay the shared queries for every N; AMTP answers every shape."""
    corpus = Corpus(a)
    rows = load_queries(a.queries or DEFAULT_QUERIES, a.queries)
    sizes = sorted({r["N"] for r in rows})
    print(f"[exp1] Boolean search scalability  sizes={sizes} θ=({a.theta_min},{a.theta_max})")
    w = Writer("exp1_boolean_scalability", a.out)
    for n in sizes:
        src = corpus.D.sample(n, a.domains, a.data)
        dom, state, lay = setup("D", corpus, src, a)
        user = corpus.user(["D"])
        inv = corpus.D.inverted_index(src)
        for q in (r for r in rows if r["N"] == n):
            text = quote_terms(q["query"])
            res, info = measure(dom, state, user, text, a)
            if info.pop("ids") != ground_truth(text, inv, dom.cids):
                raise SystemExit(f"CORRECTNESS GATE FAILED: result != ground truth for {q['query']}")
            w.add(N=n, kQ=q["kQ"], shape=q["shape"], domain=q.get("domain", ""), status="ok",
                  partitions=lay["partitions"], **info, **res)
        del dom, state, src, inv
        gc.collect()
    w.close()


def amtp_partition_order(corpus, src, a):
    """Positions of src grouped by the AMTP partition they land in (placement ignores keywords)."""
    probe, _, _ = setup("D", corpus, src, a)
    by_part = {}
    for i, cid in enumerate(probe.cids):
        pid, slot = probe.eng.loc[cid]
        by_part.setdefault(pid, []).append((slot, i))
    return [[i for _, i in sorted(by_part[p])] for p in sorted(by_part)]


def suite_exp2_layouts(a):
    """Write the shared Exp. 2 file (baselines/results/exp2_layouts.json) that every scheme replays:
    clustered and dispersed in document order (amtp_dataset.exp2_doc_layouts), plus AMTP's worst case
    'partition_spread' = one file per AMTP partition, round robin (needs AMTP's placement, hence here)."""
    corpus = Corpus(a)
    n = a.n
    src = corpus.D.sample(n, a.domains, a.data)
    parts = amtp_partition_order(corpus, src, a)
    layouts = corpus.D.exp2_doc_layouts(n, a.rq)
    spread = {}
    for r in (r for r in a.rq if r <= n):
        chosen, depth = [], 0
        while len(chosen) < r:
            chosen += [p[depth] for p in parts if depth < len(p)][:r - len(chosen)]
            depth += 1
        spread[str(r)] = chosen
    layouts["partition_spread"] = {"prefix": "par", "docs": spread,
                                   "note": f"one file per AMTP partition (θ = {a.theta_max}/{a.theta_min}, "
                                           f"{len(parts)} partitions), round robin"}
    out = {"N": n, "rq": a.rq, "dataset": corpus.D.DATASET_TAG, "domains": a.domains, "layouts": layouts}
    with open(corpus.D.EXP2_FILE, "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
                                   for k, v in out.items()) + "\n}\n")
    print(f"-> {os.path.relpath(corpus.D.EXP2_FILE)}  N={n} layouts={list(layouts)}")


def suite_exp2(a):
    """Exp. 2: one marker keyword matching exactly r_Q files, at fixed N, in every layout of the shared
    file baselines/results/exp2_layouts.json (the same files in every scheme)."""
    corpus = Corpus(a)
    lay_file = corpus.D.load_exp2_layouts()
    n = lay_file["N"]
    src = corpus.D.sample(n, lay_file["domains"], a.data)
    print(f"[exp2] selective proof / verification  N={n} layouts={list(lay_file['layouts'])}")
    extra = corpus.D.exp2_markers(lay_file, n)
    dom, state, lay = setup("D", corpus, src, a, extra_words=extra)
    user = corpus.user(["D"])
    w = Writer("exp2_selective_proof", a.out)
    for r in lay_file["rq"]:
        for name, spec in lay_file["layouts"].items():
            res, info = measure(dom, state, user, f"{spec['prefix']}{r}", a)
            info.pop("ids")
            if info["rQ"] != r:
                raise SystemExit(f"expected {r} results, got {info['rQ']}")
            w.add(N=n, rQ=r, layout=name, partitions=lay["partitions"],
                  **{k: info[k] for k in ("sQ", "proof_bytes", "response_bytes", "hash_server", "hash_verify")},
                  **res)
    w.close()


def suite_exp3(a):
    """Exp. 3 (update cost): at fixed N, b fresh documents (insert pool) are inserted as ONE epoch of b
    signed requests, then deleted again as one epoch. Partitions are frozen (no split/merge).
    Each epoch runs the Phase 2 protocol and times its parts:
      encrypt  Phase 1 file encryption of the b documents (reported apart, NOT in update)
      request  owner builds the b signed requests: keyword tokens C(d) (fresh) + σ_op (delete: σ_op only)
      server   CS prepare_update: admit, apply, repair PAPC / IMT / partition trees, Aff_i, Δ_i, π^upd
      validate owner Validator: replay the update on trusted metadata, check π^upd, sign σ_root
      anchor   Root Anchor: predecessor, e* + 1, σ_root
    update = request + server + validate + anchor: like Chen's update (owner token generation + CS apply),
    without the file encryption."""
    corpus = Corpus(a)
    pool = corpus.D.insert_pool(a.domains, a.data)
    print(f"[exp3] dynamic update  sizes={a.sizes} b={a.batches}")
    w = Writer("exp3_dynamic_update", a.out)
    for n in a.sizes:
        src = corpus.D.sample(n, a.domains, a.data)
        dom, _, lay = setup("D", corpus, src, a)
        eng = dom.eng
        proto = Protocol(dom, StaticPolicy(a.buckets, a.theta_min, a.theta_max, a.placement))
        epoch = proto.epoch
        cursor = 0

        for b in a.batches:
            eng.ops_per_epoch = b
            rows = {"insert": [], "delete": []}
            stats = {}
            for rep in range(a.warmup + a.reps):
                batch = [pool[(cursor + i) % len(pool)] for i in range(b)]
                cursor = (cursor + b) % len(pool)
                t0 = time.perf_counter()
                enc_b = [corpus.encrypt_fresh(d, "D") for d in batch]      # file encryption: not counted
                t_enc = (time.perf_counter() - t0) * 1e3
                gc.disable()
                try:
                    ins, st_ins = epoch(lambda: [corpus.insert_request(e, d, "D", eng.epoch, dom.signer)
                                                 for d, e in zip(batch, enc_b)])
                    dele, st_del = epoch(lambda: [Corpus.delete_request(d.doc_id, e[0], "D", eng.epoch, dom.signer)
                                                  for d, e in zip(batch, enc_b)])
                finally:
                    gc.enable()
                for d in batch:                                # drop the cached ciphertexts
                    corpus._docs.pop((d.doc_id, "D"), None)
                if rep < a.warmup:
                    continue
                rows["insert"].append({**ins, "encrypt": t_enc})
                rows["delete"].append(dele)
                stats = {"insert": st_ins, "delete": st_del}
            proto.check()
            for op in ("insert", "delete"):
                res = summarize(rows[op])
                mean = res["update_ms"]
                s = stats[op]
                w.add(N=n, batch=b, b=b, op=op, partitions=lay["partitions"], **res,
                      per_doc_ms=mean / b, throughput_docs_s=b / (mean / 1e3),
                      hash_calls=s["hash_calls"], keys_refreshed=s["keys_refreshed"],
                      posting_components_refreshed=s["posting_components_refreshed"],
                      partitions_changed=s["partitions_changed"], splits=s["splits"], merges=s["merges"])
        del dom, proto
        gc.collect()
    w.close()


def suite_exp5(a):
    """Exp. 5: D independent domains, replaying the shared baselines/results/exp5_workload.json (the same
    domains, queries and update files as SE-COLLAB). The target domain (groups[0], identical for every D) is
    queried, then updated alone. Measures query cost, the anchor's Global Root update, and checks that every
    other Domain Root is unchanged."""
    corpus = Corpus(a)
    meta, groups, queries, fresh = corpus.D.load_exp5_workload(a.exp5_workload, a.data)
    if len(fresh) < a.warmup + a.reps:
        raise SystemExit("exp5_workload.json has fewer update files than warmup + reps")
    target = groups[0]
    inv = corpus.D.inverted_index(target)
    counts = [d for d in meta["domain_counts"] if d <= len(groups) and d in a.d_counts]
    print(f"[exp5] multi-domain  D={counts} per-domain={meta['per_domain']} queries={len(queries)}")
    w = Writer("exp5_domains", a.out)
    for nd in counts:
        anchor, server = RootAnchor(), CloudServer()
        t0 = time.perf_counter()
        doms = [Domain(f"D{k:02d}", corpus, groups[k], a, anchor, server) for k in range(nd)]
        states = [d.publish_snapshot() for d in doms]
        t_setup = time.perf_counter() - t0
        user = corpus.user([d.name for d in doms])
        print(f" D={nd}: setup={t_setup:.1f}s", flush=True)
        base = dict(scheme="AMTP", deploy_model="domains", domains=nd, N_target=meta["per_domain"],
                    N_total=nd * meta["per_domain"])
        for q in queries:
            text = quote_terms(q["query"])
            res, info = measure(doms[0], states[0], user, text, a)
            if info.pop("ids") != ground_truth(text, inv, doms[0].cids):
                raise SystemExit(f"CORRECTNESS GATE FAILED: result != ground truth for {q['query']}")
            w.add(**base, kQ=q["kQ"], q=q["q"], shape=q["shape"], op="query", status="ok", **info, **res)
        samples = []
        target = doms[0]
        proto = Protocol(target)                             # the target domain's own policy (adaptive)
        for rep in range(a.warmup + a.reps):                 # update the target domain only: one insert = one epoch
            before = {d.name: anchor.latest(d.name) for d in doms[1:]}
            e = corpus.encrypt_fresh(fresh[rep], target.name)          # file encryption: not counted
            gc.disable()                                     # same timing rule as exp3
            try:
                times, _ = proto.epoch(lambda: [corpus.insert_request(e, fresh[rep], target.name,
                                                                      target.eng.epoch, target.signer)])
            finally:
                gc.enable()
            if any(anchor.latest(d.name) != before[d.name] for d in doms[1:]):
                raise SystemExit("ISOLATION FAILED: updating one domain changed another Domain Root")
            if rep >= a.warmup:
                samples.append(times)
        proto.check()
        w.add(**base, op="update_one_domain", update_kind="dynamic", b=1, status="ok",
              untouched_roots_unchanged=nd - 1, **summarize(samples))
        del doms, states, anchor, server
        gc.collect()
    w.close()


# ---------------------------------------------------------------- dataset-v4 suites (advisor's plan)
def q_text(keywords):
    return " AND ".join(f'"{k}"' for k in keywords)


def suite_search1(a):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl, every domain, every files-per-domain
    size. Each query must return exactly its result_size from the file and the plaintext ground truth."""
    corpus = Corpus(a)
    qs = corpus.D.search_single_queries()
    plan = corpus.D.search1_points(qs, a.fpd, a.fix, a.s1_kq, a.all_points)
    print(f"[search1] domains={a.s_domains} files/domain={a.fpd} queries={len(qs)} "
          f"points={sum(map(len, plan.values()))}")
    w = Writer("search_single", a.out)
    for dname in a.s_domains:
        for n in a.fpd:
            mine = [q for q in plan[n] if q["domain"] == dname]
            if not mine:
                continue
            src = corpus.D.domain_docs(dname, n, a.data)
            dom, state, lay = setup(dname, corpus, src, a)
            user = corpus.user([dname])
            inv = corpus.D.inverted_index(src)
            for q in mine:
                res, info = measure(dom, state, user, q["text"], a)
                ids = info.pop("ids")
                if len(ids) != q["result_size"][str(n)] or ids != ground_truth(q["text"], inv, dom.cids):
                    raise SystemExit(f"CORRECTNESS GATE FAILED: {q['query_id']} at n={n}")
                w.add(scheme="AMTP", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", partitions=lay["partitions"], **info, **res)
            del dom, state, src, inv
            gc.collect()
        corpus._docs.clear()                                   # next domain: free its cached ciphertexts
        corpus._h.clear()
    w.close()


def suite_verify1(a):
    """Verification 1.1 (single domain): verify_keywords.csv single_domain rows at --fix files per domain;
    x-axis = target result size (10 / 100 / 1,000 / 10,000), 5 real keywords per target and domain."""
    corpus = Corpus(a)
    rows = corpus.D.verify_keywords("single_domain", a.fix)
    print(f"[verify1] files/domain={a.fix} keywords={len(rows)}")
    w = Writer("verify_single", a.out)
    for dname in a.s_domains:
        src = corpus.D.domain_docs(dname, a.fix, a.data)
        dom, state, lay = setup(dname, corpus, src, a)
        user = corpus.user([dname])
        for r in (r for r in rows if r["domain"] == dname):
            res, info = measure(dom, state, user, q_text([r["keyword"]]), a)
            info.pop("ids")
            if info["rQ"] != r["result_size"]:
                raise SystemExit(f"CORRECTNESS GATE FAILED: {r['keyword']} gave {info['rQ']} not {r['result_size']}")
            w.add(scheme="AMTP", domain=dname, N=a.fix, keyword=r["keyword"], target_results=r["target_results"],
                  rank=r["rank"], status="ok", partitions=lay["partitions"],
                  **{k: info[k] for k in ("rQ", "sQ", "proof_bytes", "response_bytes", "hash_server", "hash_verify")},
                  **res)
        del dom, state, src
        gc.collect()
    w.close()


def suite_tamper(a):
    """Verification 1.2 (single domain): tamper_sets.jsonl. Per domain, the query keyword (~2,000 results) at its
    files_per_domain; the server modifies / hides / replaces by an older version the first t doc_ids of tamper_order,
    or injects the first t files of amtp_dataset.inject_order (files that do not match). Records the detection, the
    first failed check, the early-abort verification time, the full-check time and how many files the user names."""
    corpus = Corpus(a)
    sets = [r for r in corpus.D.tamper_sets() if r["domain"] in a.s_domains]
    print(f"[tamper] {[(r['domain'], r['query_keyword'], r['result_size']) for r in sets]} kinds={a.tamper_kinds}")
    w = Writer("tamper_detection", a.out)
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = corpus.D.domain_docs(dname, n, a.data)
        by_id = {d.doc_id: d for d in src}
        dom, state, lay = setup(dname, corpus, src, a)
        user = corpus.user([dname])
        cid_of = {d.doc_id: corpus.encrypt(d, dname)[0].hex() for d in src}
        inj = corpus.D.inject_order(ts, a.data)
        text = q_text([ts["query_keyword"]])
        base = dict(scheme="AMTP", domain=dname, N=n, keyword=ts["query_keyword"], rQ=ts["result_size"],
                    partitions=lay["partitions"])

        def row(kind, t, res, infos):
            w.add(**base, tamper=kind, tampered=t, status="ok", detected_runs=sum(i["detected"] for i in infos),
                  runs=len(infos), failed_check=infos[-1]["failed"], localized=infos[-1]["localized"], **res)

        res, _, infos = measure_fn(lambda: run_tampered(dom, state, user, text, "none", None), a)
        if any(i["detected"] for i in infos):
            raise SystemExit("CORRECTNESS GATE FAILED: honest response rejected")
        row("none", 0, res, infos)
        for kind in a.tamper_kinds:
            for t in ts["tamper_counts"]:
                if kind == "inject":
                    targets, extra = set(), []
                    for i in inj[:t]:
                        cid = bytes.fromhex(cid_of[i])
                        pid, slot = state.loc[cid]
                        extra.append({"cid": cid_of[i], "pid": pid, "loc": slot, "ct": dom.server.dht.get(cid).hex()})
                else:
                    targets = {cid_of[i] for i in ts["tamper_order"][:t]}
                    extra = ({cid_of[i]: corpus.encrypt_version(by_id[i], dname, corpus.D.OLD_VERSION_SUFFIX)
                              for i in ts["tamper_order"][:t]} if kind == "old_version" else None)
                res, _, infos = measure_fn(lambda: run_tampered(dom, state, user, text, kind, targets, extra), a)
                row(kind, t, res, infos)
        del dom, state, src, cid_of, by_id
        gc.collect()
    w.close()


def multi_build(corpus, named_docs, a):
    """One AMTP domain per (name, docs), each with its own keys and Domain Root, on one anchor and server."""
    anchor, server = make_anchor(), CloudServer()
    t0 = time.perf_counter()
    doms = [Domain(name, corpus, docs, a, anchor, server) for name, docs in named_docs]
    states = [d.publish_snapshot() for d in doms]
    print(f" {len(doms)} domains, {sum(len(d) for _, d in named_docs)} files: setup={time.perf_counter() - t0:.1f}s",
          flush=True)
    return doms, states, corpus.user([d.name for d in doms])


def suite_xsearch(a):
    """Search 2.1 (multi domain): queries_boolean_multi.jsonl (AND / OR / AND_of_OR / OR_of_AND, kQ 2..16) over
    the four domains, --fix files each. One query per domain, each verified on its own root (the paper's
    model); every domain's count must equal result_size_per_domain."""
    corpus = Corpus(a)
    qs = corpus.D.boolean_multi_queries()
    names = list(corpus.D.DOMAINS)
    print(f"[xsearch] domains={names} files/domain={a.fix} queries={len(qs)}")
    doms, states, user = multi_build(corpus, [(d, corpus.D.domain_docs(d, a.fix, a.data)) for d in names], a)
    w = Writer("search_multi", a.out)
    for q in qs:
        res, info, _ = measure_fn(lambda: run_xquery(doms, states, user, q["text"]), a)
        info.pop("ids")
        want = [q["result_size_per_domain"][d][str(a.fix)] for d in names]
        if info["rQ_per_domain"] != want:
            raise SystemExit(f"CORRECTNESS GATE FAILED: {q['query_id']} per-domain {info['rQ_per_domain']} != {want}")
        info["rQ_per_domain"] = " ".join(map(str, info["rQ_per_domain"]))
        w.add(scheme="AMTP", domains=len(doms), N_per_domain=a.fix, query_id=q["query_id"], kQ=q["kQ"],
              shape=q["shape"], status="ok", **info, **res)
    w.close()


def suite_xverify(a):
    """Verification 2.1 (multi domain): verify_keywords.csv multi_domain rows at --fix files per domain over the
    four domains; x-axis = total result size; counts per domain must match the file."""
    corpus = Corpus(a)
    rows = corpus.D.verify_keywords("multi_domain", a.fix)
    names = list(corpus.D.DOMAINS)
    print(f"[xverify] files/domain={a.fix} keywords={len(rows)}")
    doms, states, user = multi_build(corpus, [(d, corpus.D.domain_docs(d, a.fix, a.data)) for d in names], a)
    w = Writer("verify_multi", a.out)
    for r in rows:
        res, info, _ = measure_fn(lambda: run_xquery(doms, states, user, q_text([r["keyword"]])), a)
        info.pop("ids")
        if info["rQ_per_domain"] != r["result_size_per_domain"]:
            raise SystemExit(f"CORRECTNESS GATE FAILED: {r['keyword']} {info['rQ_per_domain']}")
        info["rQ_per_domain"] = " ".join(map(str, info["rQ_per_domain"]))
        w.add(scheme="AMTP", domains=len(doms), N_per_domain=a.fix, keyword=r["keyword"],
              target_results=r["target_results"], rank=r["rank"], status="ok", **info, **res)
    w.close()


def suite_xdomains(a):
    """Search 2.2 / Verification 2.2: the same files (--fix per dataset domain, all four) regrouped into
    D = 1..32 domains by arXiv category (domain_groups.csv); every boolean_multi query sent to every domain.
    Total result count must equal the sum of the file's per-domain counts (the groups partition the files)."""
    corpus = Corpus(a)
    qs = corpus.D.select_queries(corpus.D.boolean_multi_queries(), a.x_kq, a.shapes, a.max_queries)
    names = list(corpus.D.DOMAINS)
    print(f"[xdomains] D={a.d_counts} files/domain={a.fix} kQ={a.x_kq or 'all'} shapes={a.shapes or 'all'} "
          f"queries={len(qs)}")
    w = Writer("domains_scaling", a.out)
    for dc in a.d_counts:
        groups = corpus.D.domain_groups(dc, a.fix, names, a.data)
        doms, states, user = multi_build(corpus, [(f"{dc}:{g}", docs) for g, docs in groups], a)
        for q in qs:
            res, info, _ = measure_fn(lambda: run_xquery(doms, states, user, q["text"]), a)
            info.pop("ids")
            info.pop("rQ_per_domain")
            want = sum(q["result_size_per_domain"][d][str(a.fix)] for d in names)
            if info["rQ"] != want:
                raise SystemExit(f"CORRECTNESS GATE FAILED: {q['query_id']} D={dc} gave {info['rQ']} not {want}")
            w.add(scheme="AMTP", domains=len(doms), N_total=sum(len(g) for _, g in groups), query_id=q["query_id"],
                  kQ=q["kQ"], shape=q["shape"], status="ok", **info, **res)
        del doms, states, user, groups
        corpus._docs.clear()                               # new domain names next D: drop cached ciphertexts
        corpus._h.clear()
        gc.collect()
    w.close()


def suite_theta(a):
    """θ sweep at fixed N: query cost (shared Exp. 1 queries at that N) and update cost
    (frozen partitions, 1 and 100 fresh documents) for each θ_max, with θ_min = θ_max / 4."""
    corpus = Corpus(a)
    rows = [r for r in load_queries(a.queries or DEFAULT_QUERIES, a.queries) if r["N"] == a.n]
    if not rows:
        raise SystemExit(f"no shared queries for N = {a.n}")
    pool = corpus.D.insert_pool(a.domains, a.data)
    src = corpus.D.sample(a.n, a.domains, a.data)
    inv = corpus.D.inverted_index(src)
    print(f"[theta] N={a.n} θ_max={a.theta_values} θ_min=θ_max/4 queries={len(rows)}")
    w = Writer("theta_sweep", a.out)
    cursor = 0
    for tmax in a.theta_values:
        a.theta_max, a.theta_min = tmax, tmax // 4
        dom, state, lay = setup("D", corpus, src, a)
        user = corpus.user(["D"])
        q_samples, info_sum = [], {"sQ": [], "proof_bytes": [], "pQ": []}
        for q in rows:
            text = quote_terms(q["query"])
            res, info = measure(dom, state, user, text, a)
            if info.pop("ids") != ground_truth(text, inv, dom.cids):
                raise SystemExit(f"CORRECTNESS GATE FAILED: result != ground truth for {q['query']}")
            q_samples.append({k[:-3]: res[k + "_median"] for k in
                              ("query_gen_ms", "server_total_ms", "verify_total_ms", "end_to_end_ms")})
            for k in info_sum:
                info_sum[k].append(info[k])
        proto = Protocol(dom, StaticPolicy(a.buckets, a.theta_min, a.theta_max, a.placement))   # frozen, as in exp3
        upd = {}
        for b in (1, 100):
            dom.eng.ops_per_epoch = b
            samples = []
            for rep in range(a.warmup + a.reps):
                batch = [pool[(cursor + i) % len(pool)] for i in range(b)]
                cursor = (cursor + b) % len(pool)
                enc_b = [corpus.encrypt_fresh(d, "D") for d in batch]
                gc.disable()
                try:
                    ins, st_ins = proto.epoch(lambda: [corpus.insert_request(e, d, "D", dom.eng.epoch, dom.signer)
                                                       for d, e in zip(batch, enc_b)])   # insert b files: one epoch
                    proto.epoch(lambda: [Corpus.delete_request(d.doc_id, e[0], "D", dom.eng.epoch, dom.signer)
                                         for d, e in zip(batch, enc_b)])                 # and delete them again
                finally:
                    gc.enable()
                for d in batch:                                # drop the cached ciphertexts
                    corpus._docs.pop((d.doc_id, "D"), None)
                if rep >= a.warmup:
                    samples.append(ins)
                    upd.setdefault(f"keys_refreshed_b{b}", st_ins["keys_refreshed"])
            for part in ("update", "server", "validate"):
                upd[f"insert_b{b}_{part}_ms_median"] = st.median(x[part] for x in samples)
            upd[f"insert_b{b}_ms_median"] = upd[f"insert_b{b}_update_ms_median"]
            upd[f"insert_b{b}_per_doc_ms"] = upd[f"insert_b{b}_update_ms_median"] / b
        proto.check()
        w.add(N=a.n, theta_max=tmax, theta_min=tmax // 4, partitions=lay["partitions"],
              max_partition=lay["max_partition"],
              **{f"query_{k}_ms_median": st.median(x[k] for x in q_samples)
                 for k in ("query_gen", "server_total", "verify_total", "end_to_end")},
              sQ_median=st.median(info_sum["sQ"]), proof_bytes_median=st.median(info_sum["proof_bytes"]),
              **upd)
        del dom, state, proto
        gc.collect()
    w.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["exp1", "exp2-layouts", "exp2", "exp3", "exp5", "theta",
                                     "search1", "verify1", "tamper", "xsearch", "xverify", "xdomains"])
    ap.add_argument("--data", default=None, help="dataset folder (default <repo>/data/amtp_file_db_v4 or AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="dataset domains to sample")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--queries", default=None,
                    help=f"query file to replay (default {os.path.relpath(DEFAULT_QUERIES)})")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000])
    ap.add_argument("--n", type=int, default=200_000, help="N for exp2-layouts / theta")
    ap.add_argument("--rq", type=int, nargs="+", default=[10, 100, 1000, 5000])
    ap.add_argument("--batches", type=int, nargs="+", default=[1, 10, 100, 1000])
    ap.add_argument("--exp5-workload", default=os.path.join(RESULTS, "exp5_workload.json"),
                    help="shared Exp. 5 workload (python3 baselines/amtp_dataset.py exp5)")
    ap.add_argument("--buckets", type=int, default=16, help="placement groups (arXiv primary categories)")
    ap.add_argument("--theta-max", type=int, default=64)                 # docs/THETA_CHOICE.md
    ap.add_argument("--theta-min", type=int, default=16)
    ap.add_argument("--placement", choices=PLACEMENTS, default=os.environ.get("AMTP_PLACEMENT", "fill"),
                    help="where a new file goes (amtp/variants.py): least = least occupied partition of its bucket, "
                         "fill = fullest partition below θ_max (the same rule in every suite); default fill (the paper's rule) or AMTP_PLACEMENT")
    ap.add_argument("--theta-values", type=int, nargs="+", default=[64, 128, 256, 512, 1024],
                    help="θ_max values for the theta sweep (θ_min = θ_max / 4)")
    D = arxiv_loader()
    ap.add_argument("--s-domains", nargs="+", default=list(D.DOMAINS), help="v4 single-domain suites: domains")
    ap.add_argument("--fpd", type=int, nargs="+", default=D.V4_SIZES, help="search1: files per domain")
    ap.add_argument("--fix", type=int, default=D.V4_FIX, help="verify1 / xsearch / xverify / xdomains: files per domain")
    ap.add_argument("--s1-kq", type=int, default=D.S1_KQ, help="search1: k_Q run at every size (Search 1.2)")
    ap.add_argument("--all-points", action="store_true",
                    help="search1: every query at every size (default: only the points of Search 1.1 / 1.2)")
    ap.add_argument("--d-counts", type=int, nargs="+", default=D.D_COUNTS, help="xdomains / exp5: number of domains")
    ap.add_argument("--max-queries", type=int, default=0, help="xdomains: first n boolean_multi queries (0 = all)")
    ap.add_argument("--x-kq", type=int, nargs="+", default=None, help="xdomains: keep only these kQ (default all)")
    ap.add_argument("--shapes", nargs="+", default=None, choices=["AND", "OR", "AND_of_OR", "OR_of_AND"],
                    help="xdomains: keep only these query shapes (default all)")
    ap.add_argument("--tamper-kinds", nargs="+", default=D.TAMPER_KINDS, choices=D.TAMPER_KINDS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--gamma-no-v", action="store_true",
                    help="γ = H(PID ‖ H(Enc(L))) without the partition version v (study B4; same as AMTP_GAMMA_V=0)")
    ap.add_argument("--and-prune", action="store_true",
                    help="AND pruning: full list of one keyword, other keywords only in its partitions "
                         "(on by default; AMTP_AND_PRUNE=0 turns it off)")
    ap.add_argument("--and-greedy", action="store_true",
                    help="AND pruning planner: send more keywords in full when that lowers the proof "
                         "(on by default; AMTP_AND_GREEDY=0 turns it off)")
    ap.add_argument("--part-results", action="store_true",
                    help="result-only partition check: open partition slots only for the returned files "
                         "(on by default; AMTP_PART_RESULTS=0 turns it off)")
    ap.add_argument("--part-leaf", action="store_true",
                    help="Search Tree leaf keeps each keyword's partition set and component positions "
                         "(on by default; AMTP_PART_LEAF=0 turns it off; same answers and proof bytes)")
    a = ap.parse_args()
    os.environ["AMTP_PLACEMENT"] = a.placement           # recorded in every manifest
    if a.gamma_no_v or os.environ.get("AMTP_GAMMA_V", "1") == "0":
        os.environ["AMTP_GAMMA_V"] = "0"                  # recorded in every manifest
        set_gamma_v(False)
    if a.and_prune or os.environ.get("AMTP_AND_PRUNE", "1") != "0":
        os.environ["AMTP_AND_PRUNE"] = "1"                # recorded in every manifest
        set_and_prune(True)
    if a.and_greedy or os.environ.get("AMTP_AND_GREEDY", "1") != "0":
        os.environ["AMTP_AND_GREEDY"] = "1"               # recorded in every manifest
        set_and_plan_greedy(True)
    if a.part_results or os.environ.get("AMTP_PART_RESULTS", "1") != "0":
        os.environ["AMTP_PART_RESULTS"] = "1"             # recorded in every manifest
        set_part_results(True)
    if a.part_leaf or os.environ.get("AMTP_PART_LEAF", "1") != "0":
        os.environ["AMTP_PART_LEAF"] = "1"                # recorded in every manifest
        set_part_leaf(True)
    run = {"exp1": suite_exp1, "exp2-layouts": suite_exp2_layouts, "exp2": suite_exp2, "exp3": suite_exp3, "exp5": suite_exp5,
           "theta": suite_theta, "search1": suite_search1, "verify1": suite_verify1, "tamper": suite_tamper,
           "xsearch": suite_xsearch, "xverify": suite_xverify, "xdomains": suite_xdomains}
    for name in [a.mode]:
        run[name](a)


if __name__ == "__main__":
    main()
