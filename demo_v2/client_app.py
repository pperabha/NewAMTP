"""Client process: the Data User and the Data Owners (real amtp.user.DataUser / amtp.owner.DataOwner).

Holds K_s, the owners' signing keys, the attribute keys and the Validators' trusted metadata.
Talks to the Cloud Server only through HTTP (searches go through the network-path process) and reads
(e*, R_D) from the Root Anchor process. The verdict of a search comes only from DataUser.verify run here.
This process is never told whether, or how, the server or the network is cheating.
"""
import argparse
import os
import threading
import time
from collections import Counter

import common
from common import (BUCKETS, OPS_PER_EPOCH, POLICY, STAND_INS, THETA_MAX, THETA_MIN, RemoteError, get, http,
                    ev_counts, ns_ms, pack, post, show, unpack)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import amtp_dataset as DS
import wire_sizes as W
from amtp.anchor import NO_DELTA, RootAnchor, transition_message
from amtp.core import boolean
from amtp.core.crypto import make_authority
from amtp.core.hashing import H, HashCounter
from amtp.engine import Engine
from amtp.index import domain_root, gamma_has_v
from amtp.owner import DataOwner, DomainKeys
from amtp.user import CHECKS, DataUser
from amtp.validator import Validator
from amtp.variants import AdaptivePolicy
from bench.workload import _primary_categories

now = time.perf_counter_ns
UPLOAD_CHUNK = 250


# ---------------------------------------------------------------- remote proxies (thin adapters)
class RemoteAnchor:
    """The Root Anchor process, with the method names amtp_code calls on a RootAnchor."""

    def __init__(self, url):
        self.url, self.ns = url, {}

    def latest(self, domain):
        t = now()
        r = get(f"{self.url}/latest/{domain}")
        self.ns["latest"] = now() - t
        return r["epoch"], bytes.fromhex(r["R_D"])

    def register_domain(self, domain, owner_public_key, r0):
        post(f"{self.url}/register", pack({"domain": domain, "r0": r0, "owner_key": owner_public_key.public_bytes(
            Encoding.Raw, PublicFormat.Raw)}))

    def submit(self, domain, epoch, r_d, sig, delta=NO_DELTA, prev=None):
        t = now()
        try:
            post(f"{self.url}/submit", pack({"domain": domain, "epoch": epoch, "r_d": r_d, "sig": sig,
                                             "delta": delta, "prev": prev}))
        except RemoteError as e:
            raise ValueError(f"Root Anchor refused: {e.detail}") from None
        finally:
            self.ns["submit"] = now() - t

    def state(self):
        return get(f"{self.url}/state")


class RemoteServer:
    """The Cloud Server's owner-facing calls, with the method names DataOwner uses."""

    def __init__(self, url):
        self.url, self.ns, self.proposal = url, {}, None

    def _call(self, name, body):
        t = now()
        try:
            return post(f"{self.url}/owner/{name}", body)
        except RemoteError as e:
            raise ValueError(f"Cloud Server refused: {e.detail}") from None
        finally:
            self.ns[name] = now() - t

    def create_domain(self, domain, policy, owner_keys, ops_per_epoch=1):
        return self._call("create_domain", pack({
            "domain": domain, "buckets": policy.buckets, "theta_min": policy.theta_min,
            "theta_max": policy.theta_max, "ops_per_epoch": ops_per_epoch,
            "owner_key": owner_keys[0].public_bytes(Encoding.Raw, PublicFormat.Raw)}))["genesis"]

    def prepare_update(self, domain, requests):
        self.proposal = unpack(self._call("prepare_update", pack({"domain": domain, "requests": requests})))
        return self.proposal

    def abort_update(self, domain):
        self._call("abort_update", {"domain": domain})

    def finalize_update(self, domain, snapshot=True):
        return self._call("finalize_update", {"domain": domain})


def time_validator(validator, sink):
    """Record how long the real Validator.check takes (it runs here, in the owner's process)."""
    orig = validator.check

    def check(proposal, requests):
        t = now()
        try:
            return orig(proposal, requests)
        finally:
            sink["validate"] = now() - t
    validator.check = check


def qq(word):
    return f'"{word}"'


# ---------------------------------------------------------------- the client
class Client:
    def __init__(self, cfg):
        if not gamma_has_v():
            raise SystemExit("this demo runs the paper's γ = H(PID ‖ v ‖ H(Enc(L))); unset AMTP_GAMMA_V=0")
        self.cfg = cfg
        self.anchor, self.rserver = RemoteAnchor(cfg.anchor), RemoteServer(cfg.server)
        self.authority = make_authority()
        self.keys, self.owners, self.pool, self.df, self.stats = {}, {}, {}, {}, {}
        self.user = DataUser("u1", "Demo user", POLICY, [POLICY], self.authority.user_keys([POLICY]), self.keys)
        self.lock = threading.RLock()
        self.ready, self.error, self.progress, self.startup = False, None, {}, {}
        self.examples, self.history, self.last, self.inserted = {}, [], {}, {}
        self.vtime = {}
        self.bucket_of = None

    # ------------------------------------------------------------ start-up: bulk load of the real dataset
    def load(self):
        try:
            t_all = now()
            t = now()
            data = DS.load()
            cat = _primary_categories(data["dir"])
            groups = sorted(set(cat.values()) | set(DS.DOMAINS))
            table = {g: i % BUCKETS for i, g in enumerate(groups)}
            self.bucket_of = lambda d: table[cat.get(d.doc_id, d.domain)]
            self.startup["read_dataset_ms"] = ns_ms(now() - t)
            for domain in self.cfg.domains:
                self._load_domain(domain, data)
            self.startup["total_ms"] = ns_ms(now() - t_all)
            self.startup["path"] = ("bulk path: every file encrypted for real, indexed with Engine.insert and one "
                                    "commit, one owner-signed transition per domain. Every later update uses the "
                                    "full update protocol (signed requests, Validator, Root Anchor).")
            self.ready = True
        except Exception as e:                       # shown on the dashboard instead of a silent failure
            self.error = f"{type(e).__name__}: {e}"
            raise

    def _doc(self, d):
        text = DS.read_bytes(d).decode("utf-8", "replace")
        return {"id": d.doc_id, "title": text.split("\n", 1)[0].strip()[:200], "body": text,
                "policy": POLICY, "keywords": d.keywords}

    def _load_domain(self, domain, data):
        n, tm = self.cfg.files_per_domain, {}
        say = lambda s: self.progress.__setitem__(domain, s)
        say("creating domain")
        keys = self.keys[domain] = DomainKeys()
        policy = AdaptivePolicy(BUCKETS, THETA_MIN, THETA_MAX)
        owner = DataOwner(domain, f"Owner of {domain}", keys, self.authority, self.anchor, self.rserver,
                          ops_per_epoch=OPS_PER_EPOCH, policy=policy)       # create_domain + genesis root R^(0)
        post(f"{self.cfg.server}/owner/register_query_key", pack({"domain": domain, "k_a": keys.k_a}))
        docs = DS.sample(n, [domain])
        eng = Engine(domain, AdaptivePolicy(BUCKETS, THETA_MIN, THETA_MAX))   # the owner's own copy of the index
        docmap, df, chunk = {}, Counter(), []
        t_enc = t_up = t_idx = 0
        for i, d in enumerate(docs):
            t = now()
            ct, cid, c_d = owner.encrypt(self._doc(d))                     # Phase 1, real
            hs = {H(c) for c in c_d}
            t_enc += now() - t
            bucket = self.bucket_of(d)
            chunk.append((d.doc_id, ct, hs, bucket))
            t = now()
            eng.insert(cid, hs, bucket)
            t_idx += now() - t
            docmap[d.doc_id] = cid
            df.update(d.keywords)
            if len(chunk) == UPLOAD_CHUNK or i == len(docs) - 1:
                say(f"encrypting and uploading {i + 1:,} / {len(docs):,}")
                t = now()
                post(f"{self.cfg.server}/owner/bulk_load", pack({"domain": domain, "docs": chunk}))
                t_up += now() - t
                chunk = []
        say("building the index (server and owner, in parallel)")
        remote = {}
        th = threading.Thread(target=lambda: remote.update(post(f"{self.cfg.server}/owner/bulk_commit",
                                                                {"domain": domain})))
        th.start()
        t = now()
        eng.commit()
        t_idx += now() - t
        th.join()
        if remote.get("R_D") != eng.R_D.hex():
            raise RuntimeError(f"{domain}: the server's root differs from the root the owner computed itself")
        say("anchoring the root")
        t = now()
        _, prev = self.anchor.latest(domain)
        sig = owner.signer.sign(transition_message(domain, eng.epoch, eng.R_D, prev))
        self.anchor.submit(domain, eng.epoch, eng.R_D, sig)
        owner.validator = Validator.bootstrap(domain, owner.signer, owner.policy, eng, docmap, [owner.signer.public])
        self.vtime[domain] = {}
        time_validator(owner.validator, self.vtime[domain])
        tm["anchor_ms"] = ns_ms(now() - t)
        say("server builds the query snapshot")
        st = post(f"{self.cfg.server}/owner/bulk_finalize", {"domain": domain})
        tm.update(encrypt_ms=ns_ms(t_enc), upload_ms=ns_ms(t_up), owner_index_ms=ns_ms(t_idx),
                  server=st.get("bulk"))
        self.owners[domain], self.df[domain] = owner, df
        self.pool[domain] = list(data["pool"].get(domain, []))
        self.inserted[domain] = []
        self.stats[domain] = {"files": len(docs), "distinct_keywords": len(df),
                              "keyword_file_pairs": sum(df.values()), "insert_pool": len(self.pool[domain]),
                              "partitions_at_start": st["partitions"]}
        self.startup[domain] = tm
        self.examples[domain] = self._examples(docs, df)
        say("ready")

    @staticmethod
    def _examples(docs, df):
        ok = lambda k: k and '"' not in k
        top = [k for k, _ in df.most_common(60) if ok(k)]
        rare = next((k for d in docs for k in d.keywords if ok(k) and df[k] == 1), top[-1])
        rich = [d for d in docs if sum(ok(k) for k in d.keywords) >= 4]
        groups = [[k for k in d.keywords if ok(k)][:4] for d in rich[:3]]
        typo = top[0][:-1] + ("x" if top[0][-1] != "x" else "y")
        while typo in df:
            typo += "x"
        out = [
            {"label": "Rare keyword", "why": f"in {df[rare]} file", "query": qq(rare)},
            {"label": "Frequent keyword", "why": f"in {df[top[0]]:,} files", "query": qq(top[0])},
            {"label": "AND of two", "why": "both keywords of one file",
             "query": " AND ".join(qq(k) for k in groups[0][:2]) if groups else qq(top[0])},
            {"label": "Boolean, 12 keywords", "why": "(A AND B AND C AND D) OR (…) OR (…)",
             "query": " OR ".join("(" + " AND ".join(qq(k) for k in g) + ")" for g in groups)},
            {"label": "Boolean, 20 keywords", "why": "OR of the 20 most frequent keywords",
             "query": " OR ".join(qq(k) for k in top[:20])},
            {"label": "Misspelled keyword", "why": f"'{top[0]}' with a typo", "query": qq(typo)},
        ]
        return out

    # ------------------------------------------------------------ Phase 4 + 5: one domain-bound query
    def query(self, domain, text):
        steps = []

        def step(key, label, ns=None, note="", ok=True):
            steps.append({"key": key, "label": label, "ms": None if ns is None else ns_ms(ns), "note": note, "ok": ok})

        t = now()
        ast = boolean.parse(text)                      # raises ParseError on a malformed query
        step("parse", "Parse and normalise the query", now() - t,
             f"{len(boolean.leaves(ast))} keyword(s): {boolean.to_text(ast)[:120]}")
        t = now()
        t_q, ctx = self.user.make_query(domain, text, self.anchor)      # reads (e*, R_D) from the Root Anchor
        total = now() - t
        step("anchor", "Read (e*, R_D) from the Root Anchor", self.anchor.ns["latest"],
             f"epoch {ctx['epoch']}, R_D = {ctx['R_D'][:16]}…")
        step("token", "Build keyword tokens h_w with K_s and the tag τ_Q with K_a", total - self.anchor.ns["latest"],
             f"{len(ctx['word_of'])} token(s), {W.amtp_token_bytes(t_q)} bytes; no keyword text leaves this process")
        out, net = http("POST", f"{self.cfg.search}/search", {"t_q": t_q})
        server_ns = (out.get("server") or {}).get("total_ns", 0)
        step("send", "Send the token, receive the response", net["roundtrip_ns"] + net["serialize_ns"] + net["parse_ns"],
             f"{net['bytes_out']:,} bytes out, {net['bytes_in']:,} bytes in")
        res = {"domain": domain, "kq": len(ctx["word_of"]), "steps": steps, "checks": [], "results": [],
               "result_count": 0, "timing": {
                   "parse_ms": steps[0]["ms"], "anchor_read_ms": steps[1]["ms"], "token_ms": steps[2]["ms"],
                   "server_ms_reported": ns_ms(server_ns), "server_phase_ms_reported": (out.get("server") or {}).get("phase_ms", {}),
                   "network_ms": ns_ms(max(net["roundtrip_ns"] - server_ns, 0)),
                   "serialize_ms": ns_ms(net["serialize_ns"] + net["parse_ns"]),
                   "verify_ms": None, "decrypt_ms": None},
               "sizes": {"token_bytes": W.amtp_token_bytes(t_q), "wire_bytes_in": net["bytes_in"]},
               "anchored": {"epoch": ctx["epoch"], "R_D": ctx["R_D"],
                            "source": "Root Anchor process (simulated: a Python class, not a blockchain)"}}
        if out.get("status") != "ok":
            res.update(verdict="NO ANSWER", reason=f"the server returned no result: {out.get('reason')}", failed=None)
            step("verify", "Verify the response", None, "nothing to verify", ok=False)
            return res
        resp = out["response"]
        h0 = HashCounter.calls
        t = now()
        rep = self.user.verify(ctx, resp)                # the seven Phase 5 checks; the only source of the verdict
        verify_ns = now() - t
        hashes = HashCounter.calls - h0
        res["checks"] = rep["checks"]
        res["timing"].update(verify_ms=ns_ms(verify_ns), verify_phase_ms={k: round(v, 3) for k, v in rep["phase_ms"].items()})
        failed = rep["failed"]
        anchor_check = next(c for c in rep["checks"] if c["key"] == "anchor")
        step("verify", "Run the seven checks on the response", verify_ns,
             f"{hashes:,} hash computations", ok=rep["accepted"])
        step("root", "Rebuild the Domain Root and compare it with the anchored R_D", None,
             anchor_check["detail"], ok=bool(anchor_check["ok"]))
        res["proof"] = self._inspect(ctx, resp, hashes)
        res["sizes"].update(proof_bytes=res["proof"]["proof_bytes"], response_bytes=res["proof"]["response_bytes"])
        if rep["accepted"]:
            t = now()
            items = self.user.decrypt(resp)              # Phase 5 step 4: only after acceptance
            dec_ns = now() - t
            res["timing"]["decrypt_ms"] = ns_ms(dec_ns)
            step("decrypt", "Decrypt the files", dec_ns, f"{len(items)} file(s)")
            res.update(verdict="VERIFIED", failed=None, reason="all seven checks passed", result_count=len(items),
                       results=[{"doc": i.get("doc"), "status": i["status"], "title": i.get("title", ""),
                                 "snippet": i.get("body", "")[:240], "pid": i["pid"], "loc": i["loc"]}
                                for i in items[:40]],
                       files=[{"doc": i.get("doc"), "title": i.get("title", ""), "status": i["status"],
                               "pid": i["pid"], "loc": i["loc"], "cid": i["cid"][:16]} for i in items])
            self.last[domain] = (ctx, resp)
        else:
            label = next(c["label"] for c in rep["checks"] if c["key"] == failed)
            detail = next(c["detail"] for c in rep["checks"] if c["key"] == failed)
            res.update(verdict="REJECTED", failed=failed, reason=f"{label}: {detail}")
            step("decrypt", "Decrypt the files", None, "skipped: the response was rejected", ok=False)
        return res

    @staticmethod
    def _inspect(ctx, resp, hashes):
        """What the response contains, for the inspector panel. Display only: the verdict is already made."""
        proof = resp.get("proof", {})
        ev, parts, dom = proof.get("evidence", []), proof.get("partitions", []), proof.get("domain", {})
        try:
            rebuilt = domain_root(resp["domain"], resp["epoch"], bytes.fromhex(resp["R_part"]),
                                  bytes.fromhex(resp["R_idx"])).hex()
        except Exception:
            rebuilt = None
        try:
            pb, rb = W.amtp_proof_bytes(proof), W.amtp_response_bytes(resp)
        except Exception:
            pb = rb = None
        return {
            "epoch": resp.get("epoch"), "R_part": resp.get("R_part"), "R_idx": resp.get("R_idx"),
            "rebuilt_R_D": rebuilt, "proof_bytes": pb, "response_bytes": rb, "hashes_checked": hashes,
            "files_returned": len(resp.get("R_ct", [])),
            "partitions_touched": len(parts), "partitions_total": dom.get("n"),
            "imt_leaves": ev[0].get("n") if ev else None,
            "domain_proof_hashes": len(dom.get("proof", [])),
            "evidence_total": len(ev),
            "evidence": [{"word": ctx["word_of"].get(e.get("h"), "?"), "h": str(e.get("h"))[:16],
                          "status": e.get("status"), **ev_counts(e),
                          "imt_pos": e.get("pos", (e.get("lo") or {}).get("pos")),
                          "bracket": None if e.get("status") != "absent" else {
                              "lo": e["lo"]["h"][:16], "next": e["lo"]["next"][:16]},
                          "proof_hashes": len(e.get("proof", [])),
                          "siblings": [x[:16] for x in e.get("proof", [])[:4]]} for e in ev[:24]],
            "partitions": [{"pid": d.get("pid"), "v": d.get("v"), "R_P": str(d.get("R_P"))[:16],
                            "n_slots": d.get("n_slots"), "pos": d.get("pos"),
                            "proof_hashes": len(d.get("proof", []))} for d in parts[:48]],
        }

    def audit(self):
        """R_G is not used to accept a result. The client recomputes it from the anchored Domain Roots
        with the anchor's own formula (RootAnchor._global) and shows whether it matches."""
        st = self.anchor.state()
        local = RootAnchor()
        local.current = {d: (v["epoch"], bytes.fromhex(v["R_D"])) for d, v in st["domains"].items()}
        local._global()
        return {"reported_R_G": st["R_G"], "recomputed_R_G": local.R_G.hex(), "match": local.R_G.hex() == st["R_G"],
                "domains": st["domains"], "block": st["block"],
                "note": "audit value only: query results are accepted against the Domain Root"}

    def search(self, text, domains):
        with self.lock:
            runs = [self.query(d, text) for d in domains]
            done = [r for r in runs if r.get("proof")]
            verdict = ("VERIFIED" if all(r["verdict"] == "VERIFIED" for r in runs) else
                       "REJECTED" if any(r["verdict"] == "REJECTED" for r in runs) else "NO ANSWER")
            summary = {
                "query": text, "domains": domains, "kq": runs[0]["kq"], "verdict": verdict,
                "results": sum(r["result_count"] for r in runs),
                "partitions_touched": sum(r["proof"]["partitions_touched"] for r in done),
                "partitions_total": sum(r["proof"]["partitions_total"] or 0 for r in done),
                "server_ms": round(sum(r["timing"]["server_ms_reported"] for r in runs), 3),
                "verify_ms": round(sum(r["timing"]["verify_ms"] or 0 for r in runs), 3),
                "token_ms": round(sum(r["timing"]["token_ms"] for r in runs), 3),
                "network_ms": round(sum(r["timing"]["network_ms"] for r in runs), 3),
                "proof_bytes": sum(r["sizes"].get("proof_bytes") or 0 for r in runs),
                "hashes_checked": sum(r["proof"]["hashes_checked"] for r in done),
            }
            self.history.append({"n": len(self.history) + 1, **summary})
            return {"summary": summary, "runs": runs, "audit": self.audit()}

    def reverify(self, domain):
        """Check the last accepted response again, now against the root anchored at this moment."""
        with self.lock:
            if domain not in self.last:
                raise HTTPException(400, "no accepted response kept for this domain yet")
            ctx, resp = self.last[domain]
            epoch, r_d = self.anchor.latest(domain)
            fresh = dict(ctx, epoch=epoch, R_D=r_d.hex())
            t = now()
            rep = self.user.verify(fresh, resp)
            return {"domain": domain, "response_epoch": resp["epoch"], "anchored_epoch": epoch,
                    "accepted": rep["accepted"], "failed": rep["failed"], "checks": rep["checks"],
                    "verify_ms": ns_ms(now() - t)}

    # ------------------------------------------------------------ Phase 2 + 3: updates (full protocol)
    def epoch(self, domain, make_requests):
        owner, vt = self.owners[domain], self.vtime[domain]
        before = self.anchor.state()
        t = now()
        requests = make_requests()
        req_ns = now() - t
        vt.clear()
        self.rserver.ns.clear()
        self.rserver.proposal = None
        t = now()
        try:
            owner.update(requests)                 # prepare (CS) -> Validator.check -> Root Anchor -> finalize (CS)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "ops": [r["U"]["op"] for r in requests]}
        total = now() - t
        after, p = self.anchor.state(), self.rserver.proposal
        st = p["stats"]
        return {
            "ok": True, "domain": domain, "epoch_new": p["epoch_new"], "ops": [r["U"]["op"] for r in requests],
            "ids": [r["U"]["id"] for r in requests],
            "R_old": p["R_old"].hex(), "R_new": p["R_new"].hex(), "delta": p["delta"].hex(),
            "stats": {k: st[k] for k in ("splits", "merges", "partitions_changed", "keys_refreshed",
                                         "posting_components_refreshed")},
            "structure": [show(r) for r in p["aff"] if r[0] in ("split", "merge")],
            "partitions_changed": [show(r) for r in p["aff"] if r[0] in ("part", "new", "retired")][:24],
            "domains_changed": [d for d in after["domains"] if after["domains"][d] != before["domains"].get(d)],
            "domains_unchanged": [d for d in after["domains"] if after["domains"][d] == before["domains"].get(d)],
            "R_G_before": before["R_G"], "R_G_after": after["R_G"], "anchor_block": after["block"],
            "timing": {"request_ms": ns_ms(req_ns), "prepare_ms": ns_ms(self.rserver.ns.get("prepare_update", 0)),
                       "validate_ms": ns_ms(vt.get("validate", 0)), "anchor_ms": ns_ms(self.anchor.ns.get("submit", 0)),
                       "finalize_ms": ns_ms(self.rserver.ns.get("finalize_update", 0)), "total_ms": ns_ms(total + req_ns)},
        }

    def _layout(self, domain):
        return get(f"{self.cfg.server}/layout/{domain}")["partitions"]

    def _take(self, domain, n, bucket=None):
        pool, out = self.pool[domain], []
        for d in list(pool):
            if bucket is None or self.bucket_of(d) == bucket:
                out.append(d)
                pool.remove(d)
                if len(out) == n:
                    break
        return out

    def _insert_epoch(self, domain, docs):
        owner = self.owners[domain]
        r = self.epoch(domain, lambda: [owner.insert_request(self._doc(d), self.bucket_of(d)) for d in docs])
        if r["ok"]:
            self.inserted[domain] += [d.doc_id for d in docs]
        return r

    def insert(self, domain, count):
        with self.lock:
            epochs, left = [], count
            while left > 0:
                docs = self._take(domain, min(left, OPS_PER_EPOCH))
                if not docs:
                    break
                epochs.append(self._insert_epoch(domain, docs))
                left -= len(docs)
                if not epochs[-1]["ok"]:
                    break
            return self._report(domain, "insert", epochs)

    def delete(self, domain, doc_id=None):
        with self.lock:
            owner = self.owners[domain]
            doc_id = doc_id or (self.inserted[domain][-1] if self.inserted[domain] else next(iter(owner.doc)))
            if doc_id not in owner.doc:
                raise HTTPException(404, "that document is not live in this domain")
            r = self.epoch(domain, lambda: [owner.delete_request(doc_id)])
            if r["ok"] and doc_id in self.inserted[domain]:
                self.inserted[domain].remove(doc_id)
            return self._report(domain, "delete", [r])

    def split(self, domain):
        """Insert real insert-pool files into the placement group closest to a split, 8 per epoch, until the
        server's policy splits a partition (n > θ_max). The group is chosen from the server's public layout;
        every epoch is still validated by the owner."""
        with self.lock:
            by_bucket = {}
            for p in self._layout(domain):
                for b in p["buckets"]:
                    by_bucket.setdefault(b, []).append(p["live"])
            have = Counter(self.bucket_of(d) for d in self.pool[domain])
            need = {b: sum(THETA_MAX - n for n in lives) + 1 for b, lives in by_bucket.items()}
            fit = [b for b in need if have[b] >= need[b]]
            if not fit:
                raise HTTPException(409, "the insert pool has too few files of any one group to force a split")
            bucket = min(fit, key=lambda b: (need[b], b))
            epochs, done = [], 0
            while done < need[bucket] + OPS_PER_EPOCH:
                docs = self._take(domain, OPS_PER_EPOCH, bucket)
                if not docs:
                    break
                epochs.append(self._insert_epoch(domain, docs))
                done += len(docs)
                if not epochs[-1]["ok"] or epochs[-1]["stats"]["splits"]:
                    break
            out = self._report(domain, "split", epochs)
            out["plan"] = {"group": bucket, "partitions_in_group": len(by_bucket[bucket]),
                           "sizes_before": sorted(by_bucket[bucket]), "inserts_needed": need[bucket],
                           "inserted": done, "theta_max": THETA_MAX}
            return out

    def merge(self, domain):
        """Delete files of the smallest non-empty partition, 8 per epoch, until it has fewer than θ_min files
        and the server's policy merges it with a partner (n + n_k ≤ θ_max)."""
        with self.lock:
            owner, parts = self.owners[domain], self._layout(domain)
            live = [p for p in parts if p["live"] > 0]
            target = min(live, key=lambda p: (p["live"], p["pid"]))
            n_after = min(target["live"] - 1, THETA_MIN - 1)
            if not any(p["pid"] != target["pid"] and p["live"] + n_after <= THETA_MAX for p in parts):
                raise HTTPException(409, "no partition can take the merged files")
            ids = [i for i, cid in owner.doc.items() if owner.loc[cid][0] == target["pid"]]
            to_delete, epochs = ids[:max(target["live"] - (THETA_MIN - 1), 1)], []
            for i in range(0, len(to_delete), OPS_PER_EPOCH):
                batch = to_delete[i:i + OPS_PER_EPOCH]
                epochs.append(self.epoch(domain, lambda: [owner.delete_request(x) for x in batch]))
                if not epochs[-1]["ok"] or epochs[-1]["stats"]["merges"]:
                    break
            out = self._report(domain, "merge", epochs)
            out["plan"] = {"partition": target["pid"], "size_before": target["live"],
                           "deletes_planned": len(to_delete), "theta_min": THETA_MIN}
            return out

    def _report(self, domain, kind, epochs):
        ok = [e for e in epochs if e["ok"]]
        st = get(f"{self.cfg.server}/stats")["domains"][domain]
        return {"kind": kind, "domain": domain, "epochs": epochs, "ok": bool(ok) and len(ok) == len(epochs),
                "splits": sum(e["stats"]["splits"] for e in ok), "merges": sum(e["stats"]["merges"] for e in ok),
                "files_changed": sum(len(e["ops"]) for e in ok),
                "total_ms": round(sum(e["timing"]["total_ms"] for e in ok), 3),
                "partitions_now": st["partitions"], "files_now": st["files"],
                "anchored": {"epoch": st["epoch"], "R_D": st["R_D"]}, "audit": self.audit()}


# ---------------------------------------------------------------- HTTP API + the page
def create_app(cfg):
    app = FastAPI(title="AMTP demo: client (Data User + Data Owner)")
    client = Client(cfg)
    app.state.client = client
    threading.Thread(target=client.load, daemon=True).start()
    static = os.path.join(common.HERE, "static")

    def need_ready(domains=None):
        if not client.ready:
            raise HTTPException(503, client.error or "the dataset is still loading")
        for d in domains or []:
            if d not in client.owners:
                raise HTTPException(404, f"unknown domain {d}")

    @app.get("/")
    def page():
        return FileResponse(os.path.join(static, "index.html"))

    @app.get("/api/status")
    def status():
        return {
            "ready": client.ready, "error": client.error, "progress": client.progress,
            "config": {"files_per_domain": cfg.files_per_domain, "domains": cfg.domains, "theta_max": THETA_MAX,
                       "theta_min": THETA_MIN, "groups": BUCKETS, "ops_per_epoch": OPS_PER_EPOCH,
                       "gamma": "γ = H(PID ‖ v ‖ H(Enc(L)))  (v kept, as in the paper)"},
            "dataset": {"name": DS.DATASET_TAG, "loaded": client.stats,
                        "totals": {"domains": len(client.stats),
                                   "files": sum(s["files"] for s in client.stats.values()),
                                   "keyword_file_pairs": sum(s["keyword_file_pairs"] for s in client.stats.values())}},
            "startup": client.startup, "stand_ins": STAND_INS, "examples": client.examples,
            "urls": {"server": cfg.public_server, "anchor": cfg.public_anchor, "network": cfg.public_search},
            "query_language": "AND, OR, parentheses and \"quoted phrases\". No NOT. Keywords match exactly "
                              "(no fuzzy search).",
            "checks": [{"key": k, "label": l, "meaning": m} for k, l, m in CHECKS],
        }

    @app.post("/api/search")
    def search(body: dict):
        domains = body.get("domains") or cfg.domains
        need_ready(domains)
        text = (body.get("query") or "").strip()
        try:
            boolean.parse(text)
        except ValueError as e:
            raise HTTPException(400, f"cannot read the query: {e}")
        return client.search(text, domains)

    @app.get("/api/history")
    def history():
        return client.history

    @app.get("/api/audit")
    def audit():
        return client.audit()

    @app.post("/api/reverify")
    def reverify(body: dict):
        need_ready([body.get("domain")])
        return client.reverify(body["domain"])

    @app.post("/api/owner/{action}")
    def owner(action: str, body: dict):
        domain = body.get("domain")
        need_ready([domain])
        if action == "insert":
            return client.insert(domain, max(1, min(int(body.get("count", 1)), 64)))
        if action == "delete":
            return client.delete(domain, body.get("doc_id"))
        if action == "split":
            return client.split(domain)
        if action == "merge":
            return client.merge(domain)
        raise HTTPException(404, "unknown action")

    if os.path.isdir(static):
        app.mount("/static", StaticFiles(directory=static), name="static")
    return app


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8102)
    ap.add_argument("--server", default="http://127.0.0.1:8101", help="Cloud Server (owner calls)")
    ap.add_argument("--search", default="http://127.0.0.1:8104", help="where searches are sent (the network path)")
    ap.add_argument("--anchor", default="http://127.0.0.1:8103")
    ap.add_argument("--files-per-domain", type=int, default=5000)
    ap.add_argument("--domains", default="D1,D2,D3,D4")
    a = ap.parse_args()
    a.domains = [d for d in a.domains.split(",") if d]
    a.public_server, a.public_anchor, a.public_search = a.server, a.anchor, a.search
    uvicorn.run(create_app(a), host="127.0.0.1", port=a.port, log_level="warning")
