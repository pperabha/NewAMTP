"""Shared by every demo_v2 process: import paths, the demo wire format, HTTP helpers, live events.

Nothing here is part of AMTP. The wire format only carries the real objects of amtp_code
(update requests, proposals, roots) between processes without changing them.
"""
import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in (os.path.join(REPO, "amtp_code"), os.path.join(REPO, "baselines")):
    if p not in sys.path:
        sys.path.insert(0, p)

THETA_MAX, THETA_MIN, BUCKETS = 64, 16, 16     # the paper's thresholds; 16 placement groups as in the experiments
OPS_PER_EPOCH = 8                              # b: at most 8 signed requests per epoch in the demo
POLICY = "auditor"                             # access policy of every demo file

STAND_INS = [
    {"paper": "Attribute-based signature (ABS)", "demo": "Ed25519 signature",
     "note": "proves the Data Owner approved a root; does not hide which owner signed"},
    {"paper": "CP-ABE", "demo": "policy key wrap (AES-GCM per attribute)",
     "note": "a user without the attributes cannot unwrap the file key; not collusion-resistant"},
    {"paper": "Blockchain smart contract (Root Anchor)", "demo": "Python class in its own process",
     "note": "same acceptance rules (signature, predecessor, e* + 1); no chain, no consensus"},
    {"paper": "Replicated DHT", "demo": "in-memory DHT inside the server process",
     "note": "6 nodes, 3 replicas, one machine"},
]
if os.environ.get("AMTP_CPABE", "wrap").lower() == "bsw07":      # real CP-ABE (amtp/core/cpabe.py)
    STAND_INS = [s for s in STAND_INS if s["paper"] != "CP-ABE"]


# ---------------------------------------------------------------- wire format
def pack(obj):
    """Python object -> JSON-safe object. bytes, tuples, sets and dicts with non-string keys are tagged
    so unpack() returns exactly the same types (the Validator hashes these values)."""
    if isinstance(obj, (bytes, bytearray)):
        return {"__b": bytes(obj).hex()}
    if isinstance(obj, tuple):
        return {"__t": [pack(x) for x in obj]}
    if isinstance(obj, (set, frozenset)):
        return {"__s": [pack(x) for x in obj]}
    if isinstance(obj, list):
        return [pack(x) for x in obj]
    if isinstance(obj, dict):
        if all(isinstance(k, str) for k in obj) and not any(k in ("__b", "__t", "__s", "__d") for k in obj):
            return {k: pack(v) for k, v in obj.items()}
        return {"__d": [[pack(k), pack(v)] for k, v in obj.items()]}
    return obj


def unpack(obj):
    if isinstance(obj, list):
        return [unpack(x) for x in obj]
    if isinstance(obj, dict):
        if len(obj) == 1:
            if "__b" in obj:
                return bytes.fromhex(obj["__b"])
            if "__t" in obj:
                return tuple(unpack(x) for x in obj["__t"])
            if "__s" in obj:
                return {unpack(x) for x in obj["__s"]}
            if "__d" in obj:
                return {unpack(k): unpack(v) for k, v in obj["__d"]}
        return {k: unpack(v) for k, v in obj.items()}
    return obj


def show(obj, n=16):
    """Display form: bytes as short hex, tuples as lists (for the UI only, never verified)."""
    if isinstance(obj, (bytes, bytearray)):
        return bytes(obj).hex()[:n]
    if isinstance(obj, (tuple, list, set, frozenset)):
        return [show(x, n) for x in obj]
    if isinstance(obj, dict):
        return {str(show(k, n)): show(v, n) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------- HTTP
class RemoteError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


def http(method, url, body=None, timeout=600):
    """One JSON request. Returns (parsed body, timing in ns: serialize, roundtrip, parse, bytes out, bytes in)."""
    t0 = time.perf_counter_ns()
    data = None if body is None else json.dumps(body).encode()
    t1 = time.perf_counter_ns()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw).get("detail", raw.decode("utf-8", "replace"))
        except Exception:
            detail = raw.decode("utf-8", "replace")
        raise RemoteError(e.code, detail) from None
    t2 = time.perf_counter_ns()
    out = json.loads(raw) if raw else None
    t3 = time.perf_counter_ns()
    return out, {"serialize_ns": t1 - t0, "roundtrip_ns": t2 - t1, "parse_ns": t3 - t2,
                 "bytes_out": len(data or b""), "bytes_in": len(raw)}


def get(url, timeout=600):
    return http("GET", url, None, timeout)[0]


def post(url, body, timeout=600):
    return http("POST", url, body, timeout)[0]


# ---------------------------------------------------------------- live events (WebSocket + history)
class EventHub:
    """Events of one process, pushed to every connected browser and kept in a short history."""

    def __init__(self, keep=400):
        self.keep, self.events, self.seq = keep, [], 0
        self.clients, self.loop, self.lock = set(), None, threading.Lock()

    def bind(self):
        self.loop = asyncio.get_running_loop()

    def publish(self, kind, **data):
        with self.lock:
            self.seq += 1
            ev = {"seq": self.seq, "ts": time.time(), "kind": kind, **data}
            self.events.append(ev)
            del self.events[:-self.keep]
        if self.loop is not None and self.clients:
            asyncio.run_coroutine_threadsafe(self._send(ev), self.loop)
        return ev

    async def _send(self, ev):
        for ws in list(self.clients):
            try:
                await ws.send_json(ev)
            except Exception:
                self.clients.discard(ws)

    def since(self, seq):
        with self.lock:
            return [e for e in self.events if e["seq"] > seq]

    async def serve(self, ws):
        self.bind()
        await ws.accept()
        self.clients.add(ws)
        try:
            while True:
                await ws.receive_text()
        except Exception:
            self.clients.discard(ws)


def add_cors(app):
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def ns_ms(ns):
    return round(ns / 1e6, 3)


def ev_counts(e):
    """What one keyword's evidence carries, for the panels (display only; DataUser.verify decides).
    Full evidence lists every partition of the keyword in L as (PID, component). Focus evidence (AND pruning,
    amtp/server.py _focus_evidence) sends only the components inside the focus set (segs, as
    [position, PID, component]) plus the adjacent γ leaves that prove absence from the other focus partitions
    (nb); n_sel is the number of partitions the keyword has."""
    if e.get("mode") == "focus":
        segs = e.get("segs", [])
        return {"partitions": len(segs), "entries": sum(len(c) for _, _, c in segs), "pruned": True,
                "neighbours": len(e.get("nb", [])), "of": e.get("n_sel")}
    L = e.get("L", [])
    return {"partitions": len(L), "entries": sum(len(c) for _, c in L), "pruned": False,
            "neighbours": 0, "of": len(L)}
