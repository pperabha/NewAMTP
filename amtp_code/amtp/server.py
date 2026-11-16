"""Cloud Server: Phase 2 update preparation and Phase 4 search for an HONEST server.

There is no attack code here. The demo and the tests load the adversary plug-in
(amtp/adversary.py), which wraps this server; the benchmarks never do.
"""
import bisect
import math
import operator
import time

from .core import boolean
from .core.crypto import hmac_ok, sig_ok
from .dht import DHT, StorageError
from .engine import Engine
from .update import delta, enc_aff, request_digest
from .core.hashing import H, TAG_QUERY, enc_bq
from .index import KEEP_MIN_PARTS, SENTINEL_LO, and_plan_greedy_on, and_prune_on, part_results_on

def query_digest(domain, b_q, epoch, t, nonce_hex) -> bytes:
    """H(tag ‖ i ‖ Enc(B_Q) ‖ e* ‖ t ‖ η): the message under τ_Q, all fields binary."""
    return H(TAG_QUERY, domain, enc_bq(boolean.from_json(b_q)), epoch, t, bytes.fromhex(nonce_hex))


def bq_error(b_q):
    """None if B_Q is a canonical AND/OR tree over 32-byte hex query keys, else the reason."""
    try:
        ast = boolean.from_json(b_q)
        if any(len(bytes.fromhex(h)) != 32 for h in boolean.leaves(ast)):
            return "query keys must be 32-byte values"
        if enc_bq(boolean.canonical(ast)) != enc_bq(ast):
            return "B_Q is not in canonical form"
    except (TypeError, ValueError, IndexError, KeyError):
        return "B_Q is malformed"
    return None


class CloudServer:
    MAX_AGE_S = 300

    def __init__(self):
        self.states = {}          # domain -> {epoch: DomainState}
        self.query_keys = {}      # domain -> K_a
        self.dht = DHT()
        self.used_nonces = set()
        self.engines = {}         # domain -> Engine (the CS's working index)
        self.owner_keys = {}      # domain -> public keys allowed to sign U_op
        self.docs = {}            # domain -> Doc_i (id -> cid), finalized
        self.request_nonces = set()
        self._pending = {}        # domain -> candidate awaiting validation and anchoring

    # ----- Phase 2: update protocol (CS side) -----
    def create_domain(self, domain, policy, owner_keys, ops_per_epoch=1):
        """Set up the domain's index; returns the genesis PIDs (public setup data for R^(0))."""
        eng = Engine(domain, policy, ops_per_epoch)
        self.engines[domain] = eng
        self.owner_keys[domain] = list(owner_keys)
        self.docs[domain] = {}
        self.store_state(eng.snapshot())
        return sorted(eng.parts)

    def prepare_update(self, domain, requests) -> dict:
        """Admit up to b signed requests, apply them, adapt and repair, and return the candidate
        transition: roots, placements, Aff_i, Δ_i and the evidence π^upd for the validating owner."""
        eng = self.engines[domain]
        if domain in self._pending:
            raise ValueError("a candidate for this domain is still awaiting validation")
        if not requests or len(requests) > eng.ops_per_epoch:
            raise ValueError(f"an epoch takes 1..{eng.ops_per_epoch} requests")
        r_old, r_part_old, r_idx_old = eng.R_D, eng.part_tree.root, eng.imt.root
        docs, seen, placements, deletes, stored = dict(self.docs[domain]), set(), [], [], []
        eng.begin()                       # working successor: every change can be rolled back
        try:
            proposal = self._prepare(domain, eng, requests, docs, seen, placements, deletes, stored,
                                     r_old, r_part_old, r_idx_old)
        except Exception:
            eng.rollback()
            self._drop_stored(stored)
            raise
        self._pending[domain] = (docs, deletes, seen, stored)
        return proposal

    def _prepare(self, domain, eng, requests, docs, seen, placements, deletes, stored,
                 r_old, r_part_old, r_idx_old):
        for req in requests:
            u, sig = req["U"], req["sig"]
            if not any(sig_ok(k, request_digest(u), sig) for k in self.owner_keys[domain]):
                raise ValueError("σ_op invalid")
            if u["domain"] != domain or u["epoch"] != eng.epoch:
                raise ValueError("request is not for the current finalized epoch")
            if u["nonce"] in self.request_nonces or u["nonce"] in seen:
                raise ValueError("request nonce already used")
            seen.add(u["nonce"])
            if u["op"] == "insert":
                cid = H(u["ct"])
                if docs.get(u["id"]) is not None or cid in eng.loc:
                    raise ValueError("identifier or ciphertext already live")
                if not self.dht.has(cid):
                    stored.append(cid)
                self.dht.put(cid, u["ct"])
                placements.append(list(eng.insert(cid, {H(c) for c in u["C"]}, u["bucket"])))
                docs[u["id"]] = cid
            else:
                cid = u["cid"]
                if docs.get(u["id"]) != cid:
                    raise ValueError("delete of a document that is not live")
                eng.delete(cid)
                placements.append(None)
                deletes.append(cid)
                docs[u["id"]] = None
        st = eng.commit(evidence=True)
        pi = dict(st["pi"], R_part_old=r_part_old, R_idx_old=r_idx_old)
        d = delta(domain, eng.epoch, requests, enc_aff(st["aff"]), r_old, eng.R_D)
        proposal = {"domain": domain, "epoch_old": eng.epoch - 1, "epoch_new": eng.epoch,
                    "R_old": r_old, "R_new": eng.R_D, "placements": placements,
                    "aff": st["aff"], "delta": d, "pi": pi, "stats": {k: v for k, v in st.items()
                                                                       if k not in ("aff", "pi")}}
        return proposal

    def abort_update(self, domain):
        """The candidate was rejected (by the owner's Validator or the Root Anchor): discard it and
        restore the finalized predecessor, so a new candidate can be prepared against it (Phase 2,
        Step 5: obsolete proposals are regenerated against the current predecessor)."""
        _, _, _, stored = self._pending.pop(domain)
        self.engines[domain].rollback()
        self._drop_stored(stored)

    def _drop_stored(self, cids):
        for cid in cids:                  # ciphertexts first stored by the discarded candidate
            self.dht.delete(cid)

    def finalize_update(self, domain, snapshot=True):
        """After the Root Anchor accepted the transition: expose the successor snapshot and drop
        the ciphertexts of deleted documents (only now, as Phase 2 requires). snapshot=False skips
        building the query snapshot (update-only benchmarks)."""
        docs, deletes, seen, _ = self._pending.pop(domain)
        eng = self.engines[domain]
        eng.accept()
        self.docs[domain] = {i: c for i, c in docs.items() if c is not None}
        self.request_nonces |= seen
        for cid in deletes:
            if cid not in eng.loc:        # not re-inserted by the same batch
                self.dht.delete(cid)
        if not snapshot:
            return None
        state = eng.snapshot()
        if state.R_D != eng.R_D:
            raise RuntimeError("incremental R_D differs from the full rebuild")
        self.store_state(state)
        return state

    # ----- storage (called by the Data Owner) -----
    def store_ciphertext(self, cid, ct):
        self.dht.put(cid, ct)

    def store_state(self, state):
        self.states.setdefault(state.domain, {})[state.epoch] = state

    def register_query_key(self, domain, k_a):
        self.query_keys[domain] = k_a

    def current(self, domain):
        epochs = self.states[domain]
        return epochs[max(epochs)]

    # ----- Phase 4 -----
    def search(self, t_q: dict, respond=None) -> dict:
        """Admit the query, pin the current finalized snapshot and answer it. `respond(state, B_Q, η)`
        replaces the honest builder; only the adversary plug-in passes one."""
        start = time.perf_counter()
        reason = self._admit(t_q)
        if reason:
            return {"status": "rejected", "reason": reason}
        b_q = boolean.from_json(t_q["B_Q"])
        state = self.current(t_q["domain"])
        try:
            if respond is None:
                response = build_response(state, b_q, t_q["nonce"], self.dht)
            else:
                response = respond(state, b_q, t_q["nonce"])
        except StorageError as err:
            return {"status": "storage_error", "reason": str(err), "cs_ms": _ms(start)}
        for desc in response["proof"]["partitions"]:
            desc.pop("_positions", None)          # internal helper, not sent
        return {"status": "ok", "response": response, "cs_ms": _ms(start)}

    def _admit(self, t_q):
        domain = t_q.get("domain")
        if domain not in self.states:
            return "unknown domain"
        reason = bq_error(t_q["B_Q"])
        if reason:
            return reason
        msg = query_digest(domain, t_q["B_Q"], t_q["epoch"], t_q["t"], t_q["nonce"])
        if not hmac_ok(self.query_keys[domain], msg, bytes.fromhex(t_q["tau"])):
            return "query tag τ_Q is invalid (user has no query key for this domain)"
        if abs(time.time() - t_q["t"]) > self.MAX_AGE_S:
            return "timestamp too old"
        if t_q["nonce"] in self.used_nonces:
            return "nonce already used"
        if t_q["epoch"] != self.current(domain).epoch:
            return "requested epoch is not the current finalized epoch"
        self.used_nonces.add(t_q["nonce"])
        return None

def _ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


def _components(state, h: bytes, posting=None):
    """L_h on the wire: [(PID, [(cid hex, ℓ), ...]), ...] in PID order."""
    posting = state.postings[h] if posting is None else posting
    return [(pid, [(cid.hex(), slot) for cid, slot in comp]) for pid, comp in posting]


def evaluate_on_state(state, b_q) -> set:
    sets = {}
    for h in boolean.leaves(b_q):
        hb = bytes.fromhex(h)
        sets[h] = {(cid, pid, slot) for pid, comp in _components(state, hb)
                   for cid, slot in comp} if lookup(state, hb) is not None else set()
    return boolean.evaluate(b_q, sets)


def build_response(state, b_q, nonce, dht, timing=None):
    """R_Q = <i, e*, B_Q, η, R^part, R^idx, R^ct_Q, Π_Q> with ASPA multiproofs.
    `timing` (a dict, benchmarks only) receives the time of each server phase in ms:
    lookup (Search Tree + IMT evidence), eval (Boolean evaluation), proof (ASPA), fetch (DHT)."""
    t0 = time.perf_counter()
    evidence, leaf_sets = [], {}
    postings = {h: lookup(state, bytes.fromhex(h)) for h in sorted(boolean.leaves(b_q))}
    pruned, focus_set = (_and_plan(state, b_q, postings) if and_prune_on() else (set(), None))
    for h, posting in postings.items():
        hb = bytes.fromhex(h)
        if posting is not None:
            pos = state.imt_pos[hb]
            imt_part = {"pos": pos, "next": state.imt_next[hb].hex(), "n": state.imt_n,
                        "proof": [x.hex() for x in state.imt.multiproof([pos])]}
            ent = (_focus_evidence(state, hb, posting, focus_set)
                   if h in pruned and not _full_is_no_larger(posting, focus_set) else None)
            if ent is not None and _focus_bytes(ent[0]) < _full_bytes(len(posting), state.post_count(hb)):
                ent, comps = ent
                evidence.append({"h": h, "status": "present", **ent, **imt_part})
            else:            # full list (also when the focus form would not be smaller: still sound,
                             # a keyword sent in full only narrows the focus set the user computes)
                comps = _components(state, hb, posting)
                evidence.append({"h": h, "status": "present", "L": comps, **imt_part})
            leaf_sets[h] = {(cid, pid, slot) for pid, comp in comps for cid, slot in comp}
        else:
            evidence.append(_absent_evidence(state, hb))
            leaf_sets[h] = set()

    t1 = time.perf_counter()
    m_q = boolean.evaluate(b_q, leaf_sets)
    t2 = time.perf_counter()
    m_cov = set().union(*leaf_sets.values()) if leaf_sets else set()
    # group the covered slots by partition once (O(|m_cov|)), instead of scanning
    # all of m_cov for every partition (O(|S_cov| x |m_cov|))
    slots_by_pid = {}
    for _, pid, slot in m_cov:
        slots_by_pid.setdefault(pid, set()).add(slot)
    versions = None
    if part_results_on():
        # result-only partition check: open only the returned files' slots; the other covered partitions
        # send just their version v (bound by γ), for the user's PAPC check
        opened = {}
        for _, pid, slot in m_q:
            opened.setdefault(pid, set()).add(slot)
        versions = [[pid, state.by_pid[pid].v] for pid in sorted(slots_by_pid) if pid not in opened]
        slots_by_pid = opened
    s_cov = sorted(slots_by_pid)

    partitions = []
    for pid in s_cov:
        positions = sorted(slots_by_pid[pid])
        tree = state.part_trees[pid]
        partitions.append({
            "pid": pid, "v": state.by_pid[pid].v, "R_P": tree.root.hex(),
            "n_slots": len(state.by_pid[pid].slots), "pos": state.part_pos[pid],
            "proof": [x.hex() for x in tree.multiproof(positions)],
            "_positions": positions,
        })
    dom_positions = sorted(state.part_pos[pid] for pid in s_cov)
    domain_proof = {"n": len(state.partitions),
                    "proof": [x.hex() for x in state.part_tree.multiproof(dom_positions)]
                    if dom_positions else []}

    t3 = time.perf_counter()
    r_ct = []
    for cid, pid, slot in sorted(m_q, key=lambda x: (x[1], x[2])):
        ct = dht.get(bytes.fromhex(cid))     # raw CT bytes; may raise StorageError
        r_ct.append({"cid": cid, "pid": pid, "loc": slot, "ct": ct.hex()})   # hex on the JSON wire
    if timing is not None:
        t4 = time.perf_counter()
        timing.update(lookup=(t1 - t0) * 1e3, eval=(t2 - t1) * 1e3, proof=(t3 - t2) * 1e3,
                      fetch=(t4 - t3) * 1e3)

    proof = {"evidence": evidence, "partitions": partitions, "domain": domain_proof}
    if versions is not None:
        proof["versions"] = versions
    return {
        "domain": state.domain, "epoch": state.epoch, "B_Q": b_q, "nonce": nonce,
        "R_part": state.R_part.hex(), "R_idx": state.R_idx.hex(), "R_ct": r_ct,
        "proof": proof,
    }


def lookup(state, hb: bytes):
    """Phase 4 lookup: the Cuckoo filter answers "absent" at once (no false negatives); otherwise
    the B+ Search Tree gives the posting state. None = not indexed. Neither structure is evidence:
    present keys are proven by PAPC + IMT, absent keys by IMT non-membership."""
    if not state.cuckoo.might_contain(hb):
        return None
    return state.postings.get(hb)


def _pids(posting):
    """The partitions of a posting list: kept in the Search Tree leaf (PartPosting), else read from the list."""
    if posting is None:
        return set()
    pids = getattr(posting, "pids", None)
    return pids if pids is not None else {pid for pid, _ in posting}


def _and_plan(state, b_q, postings):
    """AND pruning: which present keywords may be sent as focus evidence, and the focus set F.
    Every keyword in a chosen 'full' set is sent in full; for an AND node the child with the fewest
    partitions is chosen, an OR node needs all its children. F = boolean.focus over the full keywords
    (the rule the user applies). Returns (pruned keys, F); nothing is pruned if every key must be full."""
    sel = {h: _pids(p) for h, p in postings.items()}
    size = {h: (state.post_count(bytes.fromhex(h)) if p is not None else 0) for h, p in postings.items()}

    def data_key(s):
        """Tie-break from the data only (PIDs and component sizes), never from the keyword keys h, which
        are random per domain key: the same query on the same files picks the same full keyword."""
        return (sorted(s[0]), sorted(sorted((pid, len(c)) for pid, c in postings[h]) for h in s[1]
                                     if postings[h] is not None))

    def plan(node):
        if node[0] == "leaf":
            return sel[node[1]], {node[1]}
        subs = [plan(c) for c in node[1]]
        if node[0] == "AND":
            cost = [(len(s[0]), sum(size[h] for h in s[1])) for s in subs]
            best = min(cost)
            tied = [s for s, c in zip(subs, cost) if c == best]
            return tied[0] if len(tied) == 1 else min(tied, key=data_key)
        return set().union(*(s[0] for s in subs)), set().union(*(s[1] for s in subs))

    _, full = plan(b_q)
    full |= {h for h, p in postings.items() if p is None}          # absent keys: proven empty
    if and_plan_greedy_on():
        full = _grow_full(b_q, postings, sel, size, full, data_key)
    pruned = {h for h in postings if h not in full}
    if not pruned:
        return set(), None
    return pruned, boolean.focus(b_q, {h: sel[h] for h in full})


def _focus_cost(n_sel: int, opened_segs: int, seg_postings: int, missing: int) -> int:
    """Estimated wire size of one keyword's focus evidence (as _focus_bytes counts it): its components in F,
    about two neighbour leaves per partition of F it lacks (at most n_sel), and the R^post multiproof."""
    nb = min(2 * missing, n_sel)
    opened = max(1, opened_segs + nb)
    size = 1 << max(0, (n_sel - 1).bit_length())
    siblings = int(opened * max(0.0, math.log2(size / opened))) if opened < size else 0
    return (3 * _INT + _HASH + opened_segs * 3 * _INT + seg_postings * (_HASH + _INT)
            + _INT + nb * (3 * _INT + _HASH) + _INT + siblings * _HASH)


_GREEDY_MIN_FOCUS = 8     # the planner runs only when F has more partitions than this


def _grow_full(b_q, postings, sel, size, full, data_key):
    """Greedy: send one more keyword in full while that lowers the estimated proof. A keyword sent in full
    costs its whole list but shrinks F (boolean.focus is an intersection under AND), so every other partial
    keyword opens fewer components. Each candidate is scored with set operations only; the other keywords'
    focus cost is scaled by |F'| / |F| (independence estimate). The user's check is unchanged: it already
    accepts any set of full keywords that bounds F.
    No repeated work: candidates are ordered once, the other keywords' cost is one sum per round, and for a
    flat AND F is narrowed by intersection (focus of a flat AND is the intersection of the full lists) instead
    of being recomputed from every full list; a nested query recomputes F with boolean.focus."""
    present = [h for h, p in postings.items() if p is not None]

    def partial_cost(h, F):
        s = sel[h]
        k = len(F & s)                    # components of h inside F; their postings ≈ k x average component size
        return min(_focus_cost(len(s), k, round(k * size[h] / len(s)), len(F) - k),
                   _full_bytes(len(s), size[h]))

    flat_and = b_q[0] == "AND" and all(c[0] == "leaf" for c in b_q[1])

    def narrowed(F, c):
        return F & sel[c] if flat_and else boolean.focus(b_q, {h: sel[h] for h in full | {c}})

    full = set(full)
    F = boolean.focus(b_q, {h: sel[h] for h in full})
    if F is None or len(F) <= _GREEDY_MIN_FOCUS:   # already small: another full list cannot pay for itself
        return full
    order = sorted(present, key=lambda h: (len(sel[h]), size[h], data_key((sel[h], {h}))))
    while F:
        partial = [h for h in order if h not in full]
        if not partial:
            break
        costs = {h: partial_cost(h, F) for h in partial}
        total = sum(costs.values())                # integers: total - costs[c] is exact
        best, best_gain = None, 0
        for c in partial:
            F2 = narrowed(F, c)
            if F2 is None:
                continue
            shrink = len(F2) / len(F)
            gain = (total - costs[c]) * (1 - shrink) - (_full_bytes(len(sel[c]), size[c]) - costs[c])
            if gain > best_gain:
                best, best_gain = c, gain
        if best is None:
            break
        F = narrowed(F, best)
        full.add(best)
    return full


_PID = operator.itemgetter(0)


def _focus_evidence(state, hb: bytes, posting, focus_set):
    """Focus evidence of one present keyword for the partitions F: its component in every partition of F it
    has (segs), and for every partition of F it lacks the two adjacent γ leaves around that PID (nb, as
    preimages PID, v, H(Enc(L))), opened together in its R^post tree. ρ = H(h ‖ |Sel| ‖ R^post) as usual."""
    at = getattr(posting, "at", None)                 # kept in the Search Tree leaf (PartPosting)
    if at is None:
        at = {pid: j for j, (pid, _) in enumerate(posting)}
    n = len(posting)
    seg_pos, nb_pos = set(), set()
    for t in focus_set:
        if t in at:
            seg_pos.add(at[t])
        else:
            k = bisect.bisect_left(posting, t, key=_PID)     # posting[k-1] < t < posting[k] by PID
            if k > 0:
                nb_pos.add(k - 1)
            if k < n:
                nb_pos.add(k)
    nb_pos -= seg_pos
    segs, comps = [], []
    for j in sorted(seg_pos):
        pid, comp = posting[j]
        wire = [(cid.hex(), slot) for cid, slot in comp]
        segs.append([j, pid, wire])
        comps.append((pid, wire))
    inner = state.post_inner(hb)                          # H(Enc(L_j)), kept with the snapshot
    nb = [[j, posting[j][0], state.by_pid[posting[j][0]].v, inner[j].hex()]
          for j in sorted(nb_pos)]
    tree = state.post_tree(hb)
    opened = sorted(seg_pos | nb_pos)
    ent = {"mode": "focus", "n_sel": n, "R_post": tree.root.hex(), "segs": segs, "nb": nb,
           "post_proof": [x.hex() for x in tree.multiproof(opened)] if opened else []}
    return ent, comps


_HASH, _INT = 32, 8       # the size rule of baselines/wire_sizes.py (binary: hash 32 B, number 8 B)


def _full_is_no_larger(posting, focus_set) -> bool:
    """For a keyword in fewer than KEEP_MIN_PARTS partitions (its R^post data is not kept): True when its full
    list is no larger than ANY focus evidence could be (a lower bound: the fixed fields, its components inside
    F, and at least one neighbour leaf if it lacks a partition of F). Then the full list is sent without
    building the focus evidence: the same choice, without rebuilding a tree that would be thrown away."""
    if len(posting) >= KEEP_MIN_PARTS:
        return False
    inside = sum(3 * _INT + len(c) * (_HASH + _INT) for pid, c in posting if pid in focus_set)
    n_inside = sum(1 for pid, _ in posting if pid in focus_set)
    fixed = _INT + _HASH + _INT + _INT + _INT        # n_sel, R^post, #segs, #nb, #proof (as _focus_bytes)
    lower = fixed + inside + (3 * _INT + _HASH if len(focus_set) > n_inside else 0)
    return _full_bytes(len(posting), sum(len(c) for _, c in posting)) <= lower


def _full_bytes(n_comps: int, n_postings: int) -> int:
    """Wire size of a full posting list L_h of n_comps components holding n_postings files
    (as wire_sizes.amtp_proof_bytes counts it)."""
    return _INT + n_comps * 2 * _INT + n_postings * (_HASH + _INT)


def _focus_bytes(ent) -> int:
    """Wire size of the focus part of an evidence entry (as wire_sizes.amtp_proof_bytes counts it)."""
    return (_INT + _HASH + _INT + sum(3 * _INT + len(c) * (_HASH + _INT) for _, _, c in ent["segs"])
            + _INT + len(ent["nb"]) * (3 * _INT + _HASH) + _INT + len(ent["post_proof"]) * _HASH)


def _absent_evidence(state, hb: bytes):
    """Non-membership: the predecessor leaf h_lo with h_lo < h < next(h_lo). (If the key IS
    indexed, the honest predecessor has next(h_lo) = h and the user's bracket check fails.)"""
    lo = state.postings.predecessor(hb) or SENTINEL_LO     # B+ tree: largest indexed key below h
    pos = state.imt_pos[lo]
    leaf = {"pos": pos, "h": lo.hex(), "rho": state.imt_rho[lo].hex(),
            "next": state.imt_next[lo].hex()}
    return {"h": hb.hex(), "status": "absent", "lo": leaf, "n": state.imt_n,
            "proof": [x.hex() for x in state.imt.multiproof([pos])]}
