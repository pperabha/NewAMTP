"""Data User side: build the trapdoor (Phase 4, Step 1), verify the answer
(Phase 5, Steps 1-3) and decrypt only after acceptance (Phase 5, Step 4)."""
import bisect
import json
import os
import time

from .core import boolean
from .core.crypto import aes_gcm_decrypt, hmac_tag, unpack_ct, unwrap, InvalidTag
from .dht import ciphertext_id
from .core.hashing import H, enc_bq, lp, u64
from .index import domain_root, gamma_inner, gamma_wire, imt_leaf, rho
from .core.merkle import merkle_root, multiverify
from .owner import keyword_key
from .server import query_digest

# The seven terms of Accept_Q, in the order Phase 5 evaluates them.
CHECKS = [
    ("ctx", "Query context", "Same domain, epoch, Boolean expression and nonce as the query I sent"),
    ("anchor", "Anchored snapshot", "H(i ‖ e ‖ R^part ‖ R^idx) equals the Domain Root read from the blockchain"),
    ("idx", "Index evidence", "One entry per keyword; every 'absent' claim has a valid non-membership proof"),
    ("papc", "Complete posting lists (PAPC)", "Rebuilt ρ̂ from the returned lists and found it in the index tree"),
    ("part", "Partition authentication", "Every listed location is inside its partition, and every partition is inside the domain"),
    ("comp", "Exact Boolean result", "My own Eval(B_Q) gives exactly the returned files: none missing, none extra"),
    ("ct", "Ciphertext integrity", "Every returned file hashes to its cid"),
]


def _ctx_bytes(field, value) -> bytes:
    """Binary encoding of one query-context field, for the b_ctx comparison."""
    if field == "B_Q":
        return enc_bq(boolean.from_json(value))
    if field == "epoch":
        return u64(value)
    if field == "nonce":
        return bytes.fromhex(value)
    if not isinstance(value, str):
        raise ValueError("domain must be a string")
    return lp(value)


def _ct_bytes(r) -> bytes:
    """The raw CT_d bytes of one R_ct entry (hex on the JSON wire)."""
    try:
        return bytes.fromhex(r["ct"])
    except (TypeError, ValueError):
        raise Reject("ct", f"file {str(r.get('cid'))[:8]} is not a well-formed ciphertext") from None


class Reject(Exception):
    def __init__(self, check, detail):
        super().__init__(detail)
        self.check, self.detail = check, detail


class DataUser:
    def __init__(self, uid, name, role, attrs, attr_keys, domain_keys):
        self.uid, self.name, self.role = uid, name, role
        self.attrs = sorted(attrs)
        self.attr_keys = attr_keys        # from the DA (CP-ABE stand-in)
        self.domain_keys = domain_keys    # domain -> DomainKeys (K_s, K_a)

    # ---------- Phase 4, Step 1 ----------
    def make_query(self, domain, text, anchor):
        if domain not in self.domain_keys:
            raise PermissionError(f"{self.name} has no query key for domain {domain}")
        keys = self.domain_keys[domain]
        words_ast = boolean.parse(text)
        word_of = {}

        def protect(word):
            h = keyword_key(keys.k_s, word).hex()
            word_of[h] = word
            return h

        b_q = boolean.canonical(boolean.map_leaves(words_ast, protect))
        b_q = json.loads(json.dumps(b_q))                 # same form the server sees
        epoch, r_d = anchor.latest(domain)                # independently read (R_D, e*)
        t, nonce = int(time.time()), os.urandom(16).hex()
        tau = hmac_tag(keys.k_a, query_digest(domain, b_q, epoch, t, nonce)).hex()
        t_q = {"domain": domain, "B_Q": b_q, "epoch": epoch, "t": t, "nonce": nonce, "tau": tau}
        ctx = {"domain": domain, "B_Q": b_q, "epoch": epoch, "nonce": nonce,
               "R_D": r_d.hex(), "word_of": word_of, "text": boolean.to_text(words_ast)}
        return t_q, ctx

    # ---------- Phase 5, Steps 1-3 ----------
    def verify(self, ctx, resp):
        start = time.perf_counter()
        results, m_hat, failed = {}, None, None
        phase, t = {}, time.perf_counter()

        def lap(name):
            nonlocal t
            now = time.perf_counter()
            phase[name] = (now - t) * 1e3
            t = now
        try:
            m_h = self._check_ctx_anchor_idx(ctx, resp, results)
            lap("idx")                                        # b_ctx, b_anchor, b_idx
            descs = self._check_papc(resp, m_h, results)
            lap("papc")
            self._check_partitions(resp, m_h, descs, results)
            lap("part")
            m_hat = self._check_result(ctx, resp, m_h, results)
            lap("comp")
            self._check_ciphertexts(ctx, resp, results)
            lap("ct")
        except Reject as r:
            results[r.check] = (False, r.detail)
            failed = r.check
        except (KeyError, ValueError, TypeError, IndexError, OverflowError, AttributeError) as err:
            # Malformed response: reject at the first check not yet passed
            failed = next(k for k, *_ in CHECKS if k not in results)
            results[failed] = (False, f"malformed evidence ({type(err).__name__})")
        checklist = []
        for key, label, meaning in CHECKS:
            ok, detail = results.get(key, (None, "not checked: an earlier check already failed"))
            checklist.append({"key": key, "label": label, "meaning": meaning,
                              "ok": ok, "detail": detail})
        return {"accepted": failed is None, "failed": failed, "checks": checklist,
                "M_hat": sorted(m_hat) if m_hat is not None else None,
                "verify_ms": round((time.perf_counter() - start) * 1000, 2), "phase_ms": phase}

    def _check_ctx_anchor_idx(self, ctx, resp, results):
        # b_ctx
        for field in ("domain", "epoch", "B_Q", "nonce"):
            if _ctx_bytes(field, resp[field]) != _ctx_bytes(field, ctx[field]):
                raise Reject("ctx", f"{field} differs from my query "
                                    f"(got {str(resp[field])[:24]}, expected {str(ctx[field])[:24]})")
        results["ctx"] = (True, f"domain {ctx['domain']}, epoch {ctx['epoch']}, nonce matches")

        # b_anchor
        computed = domain_root(resp["domain"], resp["epoch"],
                               bytes.fromhex(resp["R_part"]), bytes.fromhex(resp["R_idx"]))
        if computed.hex() != ctx["R_D"]:
            raise Reject("anchor", f"rebuilt root {computed.hex()[:12]}… ≠ anchored "
                                   f"{ctx['R_D'][:12]}… (old or forged snapshot)")
        results["anchor"] = (True, f"matches R_D = {ctx['R_D'][:12]}… on the anchor")

        # b_idx
        r_idx = bytes.fromhex(resp["R_idx"])
        wanted = boolean.leaves(boolean.from_json(ctx["B_Q"]))
        ev = resp["proof"]["evidence"]
        if sorted(e["h"] for e in ev) != sorted(wanted):
            raise Reject("idx", "evidence is missing or duplicated for some keyword")
        m_h, absent = {}, 0
        for e in ev:
            h = e["h"]
            if e["status"] not in ("present", "absent"):
                raise Reject("idx", f"unknown evidence status {str(e['status'])[:16]!r}: "
                                    "every keyword must be proven present or absent")
            if e["status"] == "absent":
                lo = e["lo"]
                lo_h, lo_next = bytes.fromhex(lo["h"]), bytes.fromhex(lo["next"])
                if not (lo_h < bytes.fromhex(h) < lo_next):
                    raise Reject("idx", "absent-proof predecessor does not bracket the keyword "
                                        "(h_lo < h < next(h_lo) fails): the keyword is indexed")
                leaves = {lo["pos"]: imt_leaf(lo_h, bytes.fromhex(lo["rho"]), lo_next)}
                if not multiverify(r_idx, e["n"], leaves, [bytes.fromhex(x) for x in e["proof"]]):
                    raise Reject("idx", "non-membership proof does not match R^idx")
                m_h[h] = set()
                absent += 1
            else:
                m_h[h] = self._parse_postings(e)
        results["idx"] = (True, f"{len(ev) - absent} keyword(s) present, "
                                f"{absent} proven absent")
        return m_h

    @staticmethod
    def _parse_postings(e):
        mode = e.get("mode", "full")
        if mode == "focus":
            segs = e["segs"]
            js = [j for j, _, _ in segs]
            if js != sorted(set(js)):
                raise Reject("idx", "focus components are not in canonical order")
            comps = [(pid, comp) for _, pid, comp in segs]
        elif mode == "full":
            comps = e["L"]
        else:
            raise Reject("idx", f"unknown evidence form {mode!r}")
        pids, seen = [], set()
        out = set()
        for pid, comp in comps:
            if not comp:
                raise Reject("idx", "empty posting component")
            if [s for _, s in comp] != sorted(s for _, s in comp):
                raise Reject("idx", "posting list is not in canonical order")
            for cid, slot in comp:
                if cid in seen:
                    raise Reject("idx", "same file listed twice for one keyword")
                seen.add(cid)
                out.add((cid, pid, slot))
            pids.append(pid)
        if pids != sorted(set(pids)):
            raise Reject("idx", "partition list is not canonical")
        return out

    def _check_papc(self, resp, m_h, results):
        descs = {d["pid"]: d for d in resp["proof"]["partitions"]}
        if len(descs) != len(resp["proof"]["partitions"]):
            raise Reject("papc", "a partition descriptor appears twice")
        vers = {pid: d["v"] for pid, d in descs.items()}      # PID -> v for every γ the user rebuilds
        if "versions" in resp["proof"]:
            # result-only partition check: the other covered partitions send only v, bound by γ (a wrong v
            # gives a γ that is not in R^post, so ρ̂ misses the IMT)
            plain = resp["proof"]["versions"]
            pids = [pid for pid, _ in plain]
            if pids != sorted(set(pids)) or any(pid in vers for pid in pids):
                raise Reject("papc", "plain version list is not canonical or repeats a described partition")
            vers.update((pid, v) for pid, v in plain)
        r_idx = bytes.fromhex(resp["R_idx"])
        ev = resp["proof"]["evidence"]
        focus_set = None
        if any(e.get("mode") == "focus" for e in ev):
            # AND pruning: the fully sent (and absent) keywords must bound where every match can lie
            known = {e["h"]: ({pid for pid, _ in e["L"]} if e["status"] == "present" else set())
                     for e in ev if e.get("mode", "full") == "full"}
            focus_set = boolean.focus(boolean.from_json(resp["B_Q"]), known)
            if focus_set is None:
                raise Reject("papc", "partial posting lists, but the full ones do not bound the "
                                     "partitions a match can lie in")
        n_ok = 0
        for e in ev:
            if e["status"] == "absent":          # already proven by the non-membership check
                continue
            hb = bytes.fromhex(e["h"])
            if e.get("mode") == "focus":
                r_post = self._focus_root(e, vers, focus_set)
                leaf = imt_leaf(hb, rho(hb, e["n_sel"], r_post), bytes.fromhex(e["next"]))
            else:
                gammas = []
                for pid, comp in e["L"]:
                    if pid not in vers:
                        raise Reject("papc", f"no version supplied for partition {pid}")
                    gammas.append(gamma_wire(pid, vers[pid], comp))
                leaf = imt_leaf(hb, rho(hb, len(e["L"]), merkle_root(gammas)), bytes.fromhex(e["next"]))
            if not multiverify(r_idx, e["n"], {e["pos"]: leaf},
                               [bytes.fromhex(x) for x in e["proof"]]):
                raise Reject("papc", "rebuilt ρ̂ is not in the index tree: "
                                     "a posting list was changed or shortened")
            n_ok += 1
        results["papc"] = (True, f"rebuilt and matched {n_ok} posting commitment(s)"
                                 + (f", partial lists cover all {len(focus_set)} focus partition(s)"
                                    if focus_set is not None else ""))
        return descs

    @staticmethod
    def _focus_root(e, vers, focus_set) -> bytes:
        """R^post of a keyword sent as focus evidence. Opens its components in F (segs) and the two
        adjacent γ leaves around every partition of F it has no component in (nb), all in ONE multiproof
        of its R^post tree of n_sel leaves. γ leaves are in strictly increasing PID order (the DO's
        Validator checks every insertion against its neighbours), so adjacent leaves p_j < t < p_{j+1}
        prove the keyword has no component in t. Returns R^post; the caller checks ρ in the IMT."""
        n_sel = e["n_sel"]
        if not isinstance(n_sel, int) or n_sel < 1:
            raise Reject("papc", "a present keyword must have at least one posting component")
        leaves, label, seg_pids = {}, {}, set()
        for j, pid, comp in e["segs"]:
            if pid not in vers:
                raise Reject("papc", f"no version supplied for partition {pid}")
            leaves[j], label[j] = gamma_wire(pid, vers[pid], comp), pid
            seg_pids.add(pid)
        for j, pid, v, inner in e["nb"]:
            if j in leaves:
                raise Reject("papc", "one γ position is opened twice")
            leaves[j], label[j] = gamma_inner(pid, v, bytes.fromhex(inner)), pid
        if any(not (isinstance(j, int) and 0 <= j < n_sel) for j in leaves):
            raise Reject("papc", "a γ position lies outside the keyword's posting tree")
        r_post = bytes.fromhex(e["R_post"])
        if leaves:
            if not multiverify(r_post, n_sel, leaves, [bytes.fromhex(x) for x in e["post_proof"]]):
                raise Reject("papc", "an opened γ is not in the keyword's R^post: "
                                     "a posting component was changed or invented")
        elif e["post_proof"]:
            raise Reject("papc", "a proof without opened γ leaves")
        order = sorted(label.items())                      # (position, PID), by position
        if any(a[1] >= b[1] for a, b in zip(order, order[1:])):
            raise Reject("papc", "opened γ leaves are not in PID order")
        pos_of = [j for j, _ in order]
        pid_of = [p for _, p in order]
        for t in focus_set:
            if t in seg_pids:
                continue
            k = bisect.bisect_left(pid_of, t)
            if k < len(pid_of) and pid_of[k] == t:
                raise Reject("papc", f"partition {t} is opened only as a neighbour, its component is withheld")
            lo = pos_of[k - 1] if k > 0 else -1               # position just below t (-1 = none)
            hi = pos_of[k] if k < len(pid_of) else n_sel      # position just above t (n_sel = none)
            if hi != lo + 1:
                raise Reject("papc", f"no adjacent γ leaves prove the keyword is absent from partition {t}: "
                                     "a posting component was withheld")
        return r_post

    def _check_partitions(self, resp, m_h, descs, results):
        m_cov = set().union(*m_h.values()) if m_h else set()
        s_cov = {pid for _, pid, _ in m_cov}
        if "versions" in resp["proof"]:
            # result-only partition check: open exactly the locations of the files Eval(B_Q) selects; every
            # other covered partition must appear in the plain version list (checked by PAPC through γ)
            opened = boolean.evaluate(boolean.from_json(resp["B_Q"]), m_h)
            plain = {pid for pid, _ in resp["proof"]["versions"]}
            if set(descs) != {pid for _, pid, _ in opened} or plain != s_cov - set(descs):
                raise Reject("part", "partition descriptors do not match the result partitions")
        else:
            opened = m_cov
            if set(descs) != s_cov:
                raise Reject("part", "partition descriptors do not match the covered partitions")
        where = {}
        for cid, pid, slot in m_cov:
            if where.setdefault(cid, (pid, slot)) != (pid, slot):
                raise Reject("part", f"file {cid[:8]} claimed at two different locations")
        # group the opened locations by partition once (O(|opened|)), instead of scanning
        # all of them for every partition (O(|S_cov| x |m_cov|))
        by_pid = {}
        for cid, pid, slot in opened:
            by_pid.setdefault(pid, []).append((cid, slot))
        dom_leaves, positions = {}, set()
        for pid, d in descs.items():
            v_map = {}
            for cid, slot in by_pid.get(pid, ()):
                if v_map.setdefault(slot, cid) != cid:
                    raise Reject("part", "two files claim the same slot")
            if not multiverify(bytes.fromhex(d["R_P"]), d["n_slots"],
                               {s: bytes.fromhex(c) for s, c in v_map.items()},
                               [bytes.fromhex(x) for x in d["proof"]]):
                raise Reject("part", f"slot proof fails inside partition {pid}")
            if d["pos"] in positions:
                raise Reject("part", "two partitions claim one position")
            positions.add(d["pos"])
            dom_leaves[d["pos"]] = H(pid, d["v"], bytes.fromhex(d["R_P"]))
        if dom_leaves:
            dp = resp["proof"]["domain"]
            if not multiverify(bytes.fromhex(resp["R_part"]), dp["n"], dom_leaves,
                               [bytes.fromhex(x) for x in dp["proof"]]):
                raise Reject("part", "partition root A = H(PID ‖ v ‖ R_P) is not in the "
                                     "domain's partition tree (forged partition)")
        results["part"] = (True, f"{len(opened)} location(s) in {len(descs)} partition(s), "
                                 f"one shared domain multiproof"
                                 + (" (result files only)" if opened is not m_cov else ""))

    def _check_result(self, ctx, resp, m_h, results):
        m_hat = boolean.evaluate(boolean.from_json(ctx["B_Q"]), m_h)
        proj = [(r["cid"], r["pid"], r["loc"]) for r in resp["R_ct"]]
        if len(set(proj)) != len(proj):
            raise Reject("comp", "a file is returned twice")
        missing, extra = m_hat - set(proj), set(proj) - m_hat
        if missing or extra:
            parts = []
            if missing:
                parts.append(f"{len(missing)} matching file(s) missing")
            if extra:
                parts.append(f"{len(extra)} file(s) that do not match")
            raise Reject("comp", ", ".join(parts))
        results["comp"] = (True, f"{len(m_hat)} file(s), exactly as Eval(B_Q) predicts")
        return m_hat

    def _check_ciphertexts(self, ctx, resp, results):
        for r in resp["R_ct"]:
            ct = _ct_bytes(r)
            if ciphertext_id(ct).hex() != r["cid"]:
                raise Reject("ct", f"file {r['cid'][:8]} was modified: H(CT) ≠ cid")
            try:
                aad = unpack_ct(ct)["aad"]
            except ValueError:
                raise Reject("ct", f"file {r['cid'][:8]} is not a well-formed ciphertext") from None
            if aad.get("domain") != ctx["domain"]:
                raise Reject("ct", "file belongs to another domain")
        results["ct"] = (True, f"all {len(resp['R_ct'])} hash(es) match")

    # ---------- Phase 5, Step 4 ----------
    def decrypt(self, resp):
        out = []
        for r in resp["R_ct"]:
            ct = unpack_ct(_ct_bytes(r))          # already checked by b_ct before decryption
            item = {"cid": r["cid"], "pid": r["pid"], "loc": r["loc"], "doc": ct["aad"]["doc"]}
            k_d = unwrap(ct["CK"], self.attr_keys)
            if k_d is None:
                item["status"] = "locked"
            else:
                try:
                    doc = json.loads(aes_gcm_decrypt(k_d, ct["E"], ct["aad_b"]))
                    item.update(status="open", title=doc["title"], body=doc["body"])
                except InvalidTag:
                    item["status"] = "decrypt_error"
            out.append(item)
        return out
