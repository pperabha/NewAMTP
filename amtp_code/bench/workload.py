"""Workloads for the benchmarks. Same seed -> identical documents, update
stream and queries for every variant (this is what makes the comparison fair).

Document sources:
  * arxiv_docs(n)      the shared arXiv dataset (dataset-v4, datasets/arxiv/data_v4/, primary dataset).
                       W(d) is read from documents.csv -- the same keyword sets every
                       baseline uses; nothing is re-extracted. Initial documents =
                       amtp_dataset.sample(n), fresh (inserted) documents = insert pool.
  * enron_docs(path)   real Enron maildir (download separately, see README)
  * synthetic_docs()   Zipf-distributed keywords, only for smoke-testing the
                       harness; never report these numbers as results.
"""
import email
import os
import random
import sqlite3
import sys
from email import policy as email_policy

from amtp.core.hashing import H, enc
from amtp.dht import ciphertext_id
from amtp.core.crypto import pack_ct
from amtp.index import extract_keywords


class Doc:
    __slots__ = ("doc_id", "bucket", "keys", "ct", "cid")

    def __init__(self, doc_id, bucket, words, domain="A"):
        self.doc_id, self.bucket = doc_id, bucket
        self.keys = frozenset(H("kw", w) for w in words)   # stands in for h_w = H(DEnc(w))
        # Small placeholder ciphertext: the structure benchmarks do not decrypt,
        # but the verifier still checks H(CT) = cid and the domain binding.
        self.ct = pack_ct({"N": "00", "C": H(doc_id, *sorted(words)).hex()}, {"t": "none"},
                          enc({"domain": domain, "doc": doc_id}))
        self.cid = ciphertext_id(self.ct)


def synthetic_docs(n, buckets, vocab=5000, kmin=8, kmax=20, seed=0):
    rnd = random.Random(seed)
    words = [f"w{i}" for i in range(vocab)]
    weights = [1.0 / (i + 1) for i in range(vocab)]          # Zipf, s = 1
    docs = []
    for i in range(n):
        k = rnd.randint(kmin, kmax)
        picked = set()
        while len(picked) < k:
            picked.update(rnd.choices(words, weights, k=k - len(picked)))
        docs.append(Doc(f"s{seed}-{i}", rnd.randrange(buckets), picked))
    return docs


def enron_docs(maildir, limit, buckets, seed=0):
    """Read the Enron maildir (maildir/<owner>/<folder>/<file>).
    Bucket = mailbox owner, folded into `buckets` groups."""
    owners = sorted(os.listdir(maildir))
    owner_bucket = {o: i % buckets for i, o in enumerate(owners)}
    paths = []
    for owner in owners:
        for root, _, files in os.walk(os.path.join(maildir, owner)):
            paths.extend((owner, os.path.join(root, f)) for f in files)
    random.Random(seed).shuffle(paths)
    docs = []
    for owner, path in paths:
        if len(docs) >= limit:
            break
        with open(path, "rb") as fh:
            msg = email.message_from_binary_file(fh, policy=email_policy.default)
        part = msg.get_body(preferencelist=("plain",))
        text = (msg.get("subject", "") or "") + " " + (part.get_content() if part else "")
        words = extract_keywords(text)
        if words:
            docs.append(Doc(path, owner_bucket[owner], words))
    return docs


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def arxiv_loader():
    """The shared loader baselines/amtp_dataset.py (same sampling for every scheme)."""
    path = os.path.join(REPO_ROOT, "baselines")
    if path not in sys.path:
        sys.path.insert(0, path)
    import amtp_dataset
    return amtp_dataset


def _primary_categories(data_dir):
    """doc_id -> arXiv primary category (from amtp_plaintext.db), used as the workload group."""
    db = os.path.join(data_dir, "amtp_plaintext.db")
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT doc_id, primary_category FROM documents"))
    finally:
        con.close()


def arxiv_docs(n, buckets, extra=0, data_dir=None, domains=None, fresh_source="pool"):
    """n initial documents + `extra` fresh documents of the arXiv dataset.
    fresh_source = "pool": the insert pool; "initial": the next initial files of every domain after the first n
    (sample(n + extra) minus sample(n), round robin over the domains), so a run can insert as many real files as
    it starts with (e.g. 100k + 100k), more than the insert pool holds.
    Keywords = documents.csv (identical for all schemes). Bucket = arXiv primary category,
    folded into `buckets` groups (falls back to the domain if the .db is missing)."""
    ds = arxiv_loader()
    data_dir = os.path.abspath(os.path.expanduser(data_dir or ds.DEFAULT_DATA))
    initial = ds.sample(n, domains, data_dir)
    if fresh_source == "initial":
        have = {d.doc_id for d in initial}
        by_dom = {}
        for d in ds.sample(n + extra, domains, data_dir):
            if d.doc_id not in have:
                by_dom.setdefault(d.domain, []).append(d)
        lists = list(by_dom.values())
        pool = [x[i] for i in range(max(map(len, lists), default=0)) for x in lists if i < len(x)]
    else:
        pool = ds.insert_pool(domains, data_dir)
    if extra > len(pool):
        raise SystemExit(f"need {extra} fresh documents but the {fresh_source} source has {len(pool)}")
    cat = _primary_categories(data_dir)
    groups = sorted({cat.get(d.doc_id, d.domain) for d in initial + pool[:extra]})
    bucket_of = {g: i % buckets for i, g in enumerate(groups)}
    return [Doc(d.doc_id, bucket_of[cat.get(d.doc_id, d.domain)], d.keywords)
            for d in initial + pool[:extra]]


def keyword_bands(docs, lo=20, hi=400):
    """Keywords whose document-frequency rank lies in [lo, hi): not the giant
    stop-word-like ones, not the ultra rare ones."""
    freq = {}
    for d in docs:
        for h in d.keys:
            freq[h] = freq.get(h, 0) + 1
    ranked = sorted(freq, key=lambda h: (-freq[h], h))
    return ranked[lo:hi]


SHAPES = ["A", "A AND B", "A OR B", "(A OR B) AND (C OR D)", "(A AND B) OR (C AND D)"]


def make_queries(band, per_shape, seed):
    """Boolean ASTs over keyword keys (hex), same for every variant."""
    rnd = random.Random(seed)
    leaf = lambda: ("leaf", rnd.choice(band).hex())
    out = []
    for shape in SHAPES:
        for _ in range(per_shape):
            a, b, c, d = leaf(), leaf(), leaf(), leaf()
            ast = {
                "A": a,
                "A AND B": ("AND", [a, b]),
                "A OR B": ("OR", [a, b]),
                "(A OR B) AND (C OR D)": ("AND", [("OR", [a, b]), ("OR", [c, d])]),
                "(A AND B) OR (C AND D)": ("OR", [("AND", [a, b]), ("AND", [c, d])]),
            }[shape]
            out.append((shape, ast))
    return out


def update_stream(initial_docs, fresh_docs, batches, batch_size, skew, hot_buckets,
                  delete_frac, seed):
    """List of batches; each op is ('ins', doc, bucket) or ('del', cid).
    A fraction `skew` of inserts is forced into the hot buckets."""
    rnd = random.Random(seed)
    live = [d.cid for d in initial_docs]
    fresh = iter(fresh_docs)
    out = []
    for _ in range(batches):
        ops = []
        for _ in range(batch_size):
            if live and rnd.random() < delete_frac:
                ops.append(("del", live.pop(rnd.randrange(len(live)))))
                continue
            doc = next(fresh)
            bucket = rnd.choice(hot_buckets) if rnd.random() < skew else doc.bucket
            live.append(doc.cid)
            ops.append(("ins", doc, bucket))
        out.append(ops)
    return out


def hot_delete_stream(initial_docs, inserts, batch_size, hot_buckets, frac, seed):
    """Phase 2 of the split/merge workload: delete a fraction `frac` of the files that are live in the hot
    buckets after phase 1 (initial files of those buckets + the files phase 1 placed there), in random order,
    batch_size per batch. Concentrated deletes empty the hot partitions, so merges can happen; uniform
    deletes spread over the whole domain never bring a partition below θ_min.
    `inserts` = phase 1 batches (to know which files were added to / removed from the hot buckets)."""
    hot = set(hot_buckets)
    live = {d.cid for d in initial_docs if d.bucket in hot}
    for ops in inserts:
        for op in ops:
            if op[0] == "ins" and op[2] in hot:
                live.add(op[1].cid)
            elif op[0] == "del":
                live.discard(op[1])
    order = sorted(live)
    random.Random(seed).shuffle(order)
    gone = order[:int(len(order) * frac)]
    return [[("del", cid) for cid in gone[i:i + batch_size]] for i in range(0, len(gone), batch_size)]


__all__ = ["Doc", "synthetic_docs", "arxiv_docs", "enron_docs", "keyword_bands", "make_queries",
           "update_stream", "hot_delete_stream", "SHAPES", "enc"]
