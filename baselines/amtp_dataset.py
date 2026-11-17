"""
amtp_dataset.py
============================================================================
Shared AMTP dataset loader (arXiv, 4 domains): every baseline uses the same data and queries.

Dataset: dataset-v4 (parts in datasets/arxiv/data_v4/, unpack with python3 datasets/arxiv/unpack.py)
  D1 = cs, D2 = math, D3 = astro-hep, D4 = condmat-quant
  - 125,000 initial documents per domain (is_initial = 1) in time order (doc_id), 500,000 in total
  - an insert pool of 12,500 documents per domain (is_initial = 0) for the update and split/merge experiments
  - keywords W(d) already extracted with AMTP's Phase 1 code (amtp/nlp.py: RAKE, kappa = 20 phrases per file,
    idempotent Norm), in the keywords column of documents.csv
  Every scheme, AMTP included (amtp_code/bench/), uses these keywords as they are and never extracts its own,
  so W(d) is the same for every scheme. AMTP's extraction time is reported separately by
  amtp_code/bench/extraction.py.

Data location: unpack.py writes <repo>/data/amtp_file_db_v4/  (or pass a path with --data / the AMTP_DATA variable)
  The older dataset-v3 (4 x 50,000, kappa = 10) is no longer in NewAMTP: with v3 parts in datasets/arxiv/data/,
  run python3 datasets/arxiv/unpack.py --v3 -> data/amtp_file_db/ and then pass --data data/amtp_file_db

Choosing N documents (sample):
  the first N / (number of domains) files of each domain in doc_id order (no randomness)
  -> the same N always gives the same documents, for every scheme on every machine

Building queries (make_queries):
  pick one document with a seed and take k of its keywords (in decreasing doc_freq)
  -> an AND query always has at least one result (when k <= the number of keywords in the file)
  shapes as in AMTP Exp. 1: single / conjunctive / disjunctive / or_and_or / and_or_and
  the saved query file (results/exp1_queries.json) has keys N, kQ, shape, query, terms, domain, source_doc
  keywords can be multi-word phrases and are written in a query without quotes,
  e.g. "general method AND possible description"

Use from other code:
  import sys; sys.path.insert(0, "<repo>/baselines")
  from amtp_dataset import load, sample, read_bytes, insert_pool, make_queries, ground_truth
============================================================================
"""

import csv                                        # read documents.csv
import json                                       # read summary.json / write query files
import os                                         # paths
import random                                     # pick the source documents of queries (seeded)
from collections import Counter, defaultdict      # count doc_freq / group by domain
from dataclasses import dataclass                 # compact record type

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DEFAULT_DATA = os.environ.get("AMTP_DATA", os.path.join(REPO, "data", "amtp_file_db_v4"))  # dataset location (v4)
DOMAINS = ["D1", "D2", "D3", "D4"]                # all domains
DATASET_TAG = "amtp_file_db dataset-v4 (arXiv Kaggle, 4 x 125,000 + 10% insert pool, seed 42, AMTP Phase 1 keywords kappa=20)"  # dataset name recorded in result files


@dataclass
class Doc:
    doc_id: str                                   # document id, e.g. "D1_000001"
    domain: str                                   # domain, e.g. "D1"
    is_initial: bool                              # True = initial document, False = insert pool
    keywords: list                                # extracted W(d) (no duplicates within one file)
    file_path: str                                # path of the .txt file (relative to the dataset folder)


# ============================================================================
# 1) load the dataset
# ============================================================================
def load(data_dir: str = None):
    """Read documents.csv once and cache it; returns a dict:
       {"initial": {domain: [Doc, ...]}, "pool": {domain: [Doc, ...]}, "dir": path}"""
    data_dir = data_dir or DEFAULT_DATA           # the given path, or the default
    cache = load.__dict__.setdefault("_cache", {})  # one cache entry per path
    if data_dir in cache:                         # already loaded
        return cache[data_dir]                    # return the cached copy
    path = os.path.join(data_dir, "documents.csv")  # the main file for the baselines
    if not os.path.exists(path):                  # dataset not unpacked yet
        raise SystemExit(
            f"not found: {path}\n"
            "dataset not unpacked yet -> from the repository root run:  python3 datasets/arxiv/unpack.py\n"
            f"(or pass --data <dataset folder> / set AMTP_DATA)")
    initial, pool = defaultdict(list), defaultdict(list)  # split initial documents / insert pool
    csv.field_size_limit(1 << 24)                 # the keywords column can be long (kappa = 20)
    with open(path, encoding="utf-8-sig", newline="") as f:  # utf-8-sig drops a leading BOM
        for r in csv.DictReader(f):               # one row at a time
            kws = list(dict.fromkeys(k.strip() for k in r["keywords"].split(";") if k.strip()))  # split the keywords
            doc = Doc(r["doc_id"], r["domain_id"], r["is_initial"] == "1", kws, r["file_path"])  # build the Doc
            (initial if doc.is_initial else pool)[doc.domain].append(doc)  # put it in the right group
    for group in (initial, pool):                 # sort by doc_id (= time order) to be deterministic
        for d in group:
            group[d].sort(key=lambda x: x.doc_id)
    cache[data_dir] = {"initial": dict(initial), "pool": dict(pool), "dir": data_dir}  # store in the cache
    return cache[data_dir]                        # return


def summary(data_dir: str = None) -> dict:
    """Read summary.json (numbers for the paper's Dataset section)."""
    with open(os.path.join(data_dir or DEFAULT_DATA, "summary.json"), encoding="utf-8") as f:
        return json.load(f)                       # return a dict


# ============================================================================
# 2) choose documents
# ============================================================================
def sample(n: int, domains=None, data_dir: str = None):
    """n initial documents split evenly over the chosen domains, the first files in doc_id order.
    Example: n = 10,000 with 4 domains -> the first 2,500 files of each of D1..D4."""
    ds = load(data_dir)                           # dataset
    domains = list(domains or DOMAINS)            # domains used
    per, extra = divmod(n, len(domains))          # per-domain count (the remainder goes to the first domains)
    out = []                                      # result
    for i, d in enumerate(domains):               # every domain
        want = per + (1 if i < extra else 0)      # number wanted from this domain
        have = ds["initial"].get(d, [])           # documents available
        if want > len(have):                      # asked for more than available
            raise SystemExit(f"asked for {want} files from {d} but it has only {len(have)} (max N = {len(have):,} x number of domains)")
        out.extend(have[:want])                   # take the first files
    return out                                    # return the list of Doc


def read_bytes(doc: Doc, data_dir: str = None) -> bytes:
    """Content of a document's .txt file (title + abstract), for schemes that encrypt real files."""
    with open(os.path.join(load(data_dir)["dir"], doc.file_path), "rb") as f:  # path relative to the dataset folder
        return f.read()                           # return bytes


def insert_pool(domains=None, data_dir: str = None):
    """Insert-pool documents (not in the initial set) for the update experiments, alternating domains one file at
    a time: D1, D2, D3, D4, D1, ..."""
    ds = load(data_dir)                           # dataset
    lists = [ds["pool"].get(d, []) for d in (domains or DOMAINS)]  # pool of each domain
    out = []                                      # result
    for i in range(max(len(x) for x in lists)):   # round robin
        out.extend(x[i] for x in lists if i < len(x))  # one file per domain
    return out                                    # return the list of Doc


# ============================================================================
# 3) queries and ground truth
# ============================================================================
def doc_freq(docs) -> Counter:
    """Document frequency: in how many documents each keyword appears."""
    c = Counter()                                 # counter
    for d in docs:                                # every document
        c.update(d.keywords)                      # keywords within one file are already unique
    return c                                      # return


def boolean_shapes(terms):
    """Query shapes as in AMTP Exp. 1 (names and forms as in se_collab boolean_shapes)."""
    t = list(terms)                               # keyword
    if len(t) == 1:                               # single keyword
        return {"single": t[0]}                   # only one shape
    half = len(t) // 2                            # split in half
    L, R = t[:half], t[half:]                     # left / right
    return {
        "conjunctive": " AND ".join(t),           # A AND B AND C AND D
        "disjunctive": " OR ".join(t),            # A OR B OR C OR D
        "or_and_or": f"({' OR '.join(L)}) AND ({' OR '.join(R)})",   # (A OR B) AND (C OR D)
        "and_or_and": f"({' AND '.join(L)}) OR ({' AND '.join(R)})",  # (A AND B) OR (C AND D)
    }


def make_queries(docs, kqs, per_kq: int = 1, seed: int = 42):
    """Build queries for every k_Q: pick a source document (fixed seed) and take k of its keywords,
    in decreasing doc_freq (so OR results have a reasonable size).
    If k exceeds the number of keywords in the file (at most kappa = 20), keywords of another random document are
    added -> the AND result may be empty.
    Returns a list of dicts {kQ, shape, query, terms, source_doc, domain}."""
    df = doc_freq(docs)                           # doc_freq of this document set
    out = []                                      # result
    for k in kqs:                                 # every k_Q
        rng = random.Random(f"{seed}-{k}")        # one seed per k -> the queries of one k do not depend on other k
        for j in range(per_kq):                   # queries per k
            cand = [d for d in docs if len(d.keywords) >= k] or docs  # files with enough keywords
            src = cand[rng.randrange(len(cand))]  # source document
            terms = sorted(src.keywords, key=lambda w: (-df[w], w))[:k]  # the k keywords of this file with the highest df
            while len(terms) < k:                 # not enough yet (k > keywords in the file, e.g. k = 16)
                extra = docs[rng.randrange(len(docs))]  # another random file
                terms += [w for w in sorted(extra.keywords, key=lambda w: (-df[w], w)) if w not in terms][:k - len(terms)]
            for shape, q in boolean_shapes(terms).items():  # every shape
                out.append({"kQ": k, "q": j, "shape": shape, "query": q, "terms": terms,
                            "source_doc": src.doc_id, "domain": src.domain})
    return out                                    # return the list of queries


def inverted_index(docs):
    """keyword -> set of document positions (0..N-1), used to compute the correct answer."""
    inv = defaultdict(set)                        # index
    for i, d in enumerate(docs):                  # every document
        for w in d.keywords:                      # every keyword
            inv[w].add(i)                         # record
    return inv                                    # return the index


def ground_truth(inv, terms):
    """Correct answer of an AND query: positions of the documents that contain every keyword."""
    sets = [inv.get(w, set()) for w in terms]     # posting of each keyword
    return set.intersection(*sets) if sets else set()  # intersection


def save_queries(path, rows):
    """Save queries as JSON (main keys as in SE-COLLAB's exp1_queries.json + dataset/domain)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)  # create the folder
    with open(path, "w", encoding="utf-8") as f:  # open the file
        json.dump(rows, f, indent=1, ensure_ascii=False)  # write


SHARED_QUERIES = os.path.join(REPO, "baselines", "results", "exp1_queries.json")  # replayed by every scheme
EXP1_SIZES = [10_000, 50_000, 100_000, 200_000]   # Exp. 1 database sizes
EXP1_KQS = [1, 2, 4, 8, 16]                       # Exp. 1 keywords per query
EXP1_PER_KQ = 20                                  # queries per kQ; plots take the median over them


def build_shared_queries(sizes=EXP1_SIZES, kqs=EXP1_KQS, per_kq=EXP1_PER_KQ, seed=42, domains=None, data_dir=None):
    """The shared Exp. 1 workload: per_kq queries for every kQ, in every Boolean shape, and the SAME queries at
    every N, so a line over N shows the effect of N alone. The queries are drawn from the smallest database
    (sample(min(sizes))); sample(N) takes the first files of each domain, so that set is part of every larger N
    and every source document (hence every AND query with kQ <= its keyword count) has a result at every N."""
    domains = list(domains or DOMAINS)
    base = min(sizes)
    queries = make_queries(sample(base, domains, data_dir), kqs, per_kq, seed)
    return [dict(N=n, **q, query_set=f"N={base}", dataset=DATASET_TAG, seed=seed, domains=domains)
            for n in sizes for q in queries]


# ============================================================================
# 4) Shared Exp. 2 layouts and Exp. 5 workload (every scheme replays the same file)
# ============================================================================
EXP2_FILE = os.path.join(REPO, "baselines", "results", "exp2_layouts.json")
EXP2_RQ = [10, 100, 1000, 5000]


def exp2_doc_layouts(n, rqs=EXP2_RQ):
    """Positions (0..n-1 in sample(n) order) that get the marker keyword, per layout and r_Q:
    clustered = r consecutive files from n/3, dispersed = every n/r-th file."""
    return {"clustered": {"prefix": "clu", "docs": {str(r): list(range(n // 3, n // 3 + r)) for r in rqs}},
            "dispersed": {"prefix": "dis", "docs": {str(r): [i * (n // r) for i in range(r)] for r in rqs}}}


def load_exp2_layouts(path=EXP2_FILE):
    """The shared Exp. 2 file: {"N", "rq", "layouts": {name: {"prefix", "docs": {r: [positions]}, ...}}}.
    The marker keyword of (layout, r) is prefix + r, e.g. "dis1000"."""
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found: run  cd amtp_code && python -m bench.experiments exp2-layouts")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def exp2_markers(layouts, n):
    """position -> marker keywords to add, for every (layout, r_Q) of the shared file (checks N)"""
    if layouts["N"] != n:
        raise SystemExit(f"exp2_layouts.json is for N = {layouts['N']}, not {n}")
    extra = defaultdict(set)
    for lay in layouts["layouts"].values():
        for r, docs in lay["docs"].items():
            for i in docs:
                extra[i].add(f"{lay['prefix']}{r}")
    return extra


EXP5_FILE = os.path.join(REPO, "baselines", "results", "exp5_workload.json")
EXP5_DOMAIN_COUNTS = [1, 2, 4, 8, 16, 32]


def make_exp5_workload(per_domain=5_000, domain_counts=EXP5_DOMAIN_COUNTS, kqs=(1, 2, 4, 8), per_kq=5,
                       n_updates=33, seed=42, data_dir=None):
    """Exp. 5: D domains of per_domain files each. groups[k] = the k-th slice of sample(per_domain * max D)
    (as AMTP's suite_exp5 always did); groups[0] is the target domain at every D. Queries are drawn from
    groups[0] only; update_docs = the insert-pool files added to the target domain (warm-up + reps).
    k_Q = 16 is left out: no file has more than 10 keywords, so every AND query would be empty."""
    max_d = max(domain_counts)
    pool = sample(per_domain * max_d, data_dir=data_dir)
    groups = [pool[k * per_domain:(k + 1) * per_domain] for k in range(max_d)]
    return {"dataset": DATASET_TAG, "seed": seed, "per_domain": per_domain, "domain_counts": list(domain_counts),
            "groups": [[d.doc_id for d in g] for g in groups],
            "queries": make_queries(groups[0], list(kqs), per_kq, seed),
            "update_docs": [d.doc_id for d in insert_pool(data_dir=data_dir)[:n_updates]]}


# ============================================================================
# 4b) dataset-v4 experiment files (advisor's plan; datasets/arxiv/data_v4/, built by build_v4.py)
#     Every scheme reads the same files, so every scheme answers the same queries on the same files.
# ============================================================================
V4_DIR = os.path.join(REPO, "datasets", "arxiv", "data_v4")
V4_SIZES = [10_000, 25_000, 50_000, 75_000, 100_000, 125_000]   # files per domain in the v4 files
V4_FIX = 100_000                                  # files per domain where the size is fixed (tamper_sets use it)
D_COUNTS = [1, 2, 4, 8, 16, 32]                   # columns of domain_groups.csv
TAMPER_KINDS = ["modify", "hide", "inject", "old_version"]
S1_KQ = 5                                         # Search 1.2: k_Q of the files-per-domain figure
# modify = change returned file bytes; hide = leave matching files out; inject = add files that do not match the
# query; old_version = return an older (validly encrypted) version of the file. Applied to t files, t = tamper_counts.
OLD_VERSION_SUFFIX = b"\n[previous version of this file]"   # the "older version" every scheme encrypts


def _jsonl(name):
    with open(os.path.join(V4_DIR, name), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def search_single_queries():
    """Search 1.1 / 1.2: AND queries inside one domain. Keys: query_id, domain, kQ, shape (single / AND),
    text (AMTP syntax, quoted), keywords, result_size {files_per_domain: exact count}"""
    return _jsonl("queries_search_single.jsonl")


def search1_points(queries, sizes, fix=V4_FIX, kq=S1_KQ, every=False):
    """{files per domain: queries to run there}. Only the points the plan's figures use: every k_Q at `fix`
    files (Search 1.1) and k_Q = `kq` at every size (Search 1.2). every=True: every query at every size."""
    return {n: [q for q in queries if every or n == fix or q["kQ"] == kq] for n in sizes}


def boolean_multi_queries():
    """Search 2.1: AND / OR / AND_of_OR / OR_of_AND, keywords from several domains.
    result_size_per_domain {domain: {files_per_domain: exact count}}"""
    return _jsonl("queries_boolean_multi.jsonl")


def select_queries(qs, kqs=None, shapes=None, max_queries=0):
    """The same query subset for every scheme: keep kQ in `kqs` and shape in `shapes` (None = all),
    then the first max_queries (0 = all)."""
    out = [q for q in qs if (not kqs or q["kQ"] in kqs) and (not shapes or q["shape"] in shapes)]
    return out[:max_queries or None]


def tamper_sets():
    """Verify 1.2: per domain at files_per_domain, query_keyword (~2,000 results, every t <= half of them), tamper_counts and the
    seeded tamper_order (doc_ids): tamper the first t doc_ids for every t."""
    return _jsonl("tamper_sets.jsonl")


def inject_order(tset, data_dir=None):
    """Verify 1.2, attack inject: seeded order of files of the same database that do NOT contain the query keyword
    (as many as the largest tamper count); the first t are added to the result. Same for every scheme."""
    docs = domain_docs(tset["domain"], tset["files_per_domain"], data_dir)
    cand = [d.doc_id for d in docs if tset["query_keyword"] not in d.keywords]
    rng = random.Random(f"inject-{tset['domain']}-{tset['files_per_domain']}-{tset['query_keyword']}")
    return rng.sample(cand, max(tset["tamper_counts"]))


def verify_keywords(setting, files_per_domain):
    """Verify 1.1 (setting single_domain) / 2.1 (multi_domain): rows with keyword, domain, target_results,
    rank, result_size (int) and, for multi_domain, result_size_per_domain (list, D1..D4)"""
    out = []
    with open(os.path.join(V4_DIR, "verify_keywords.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["setting"] != setting or int(r["files_per_domain"]) != files_per_domain:
                continue
            r = dict(r, files_per_domain=int(r["files_per_domain"]), target_results=int(r["target_results"]),
                     rank=int(r["rank"]), result_size=int(r["result_size"]))
            if setting == "multi_domain":
                r["result_size_per_domain"] = [int(x) for x in r["result_size_per_domain"].split()]
            out.append(r)
    if not out:
        raise SystemExit(f"verify_keywords.csv has no {setting} rows for {files_per_domain} files per domain")
    return out


def domain_docs(domain, n, data_dir=None):
    """The database of n files of one domain = its first n initial files (doc_id order, nested)."""
    have = load(data_dir)["initial"].get(domain, [])
    if n > len(have):
        raise SystemExit(f"{domain} has {len(have)} initial files, asked for {n}")
    return have[:n]


def domain_groups(d_count, files_per_domain, domains=None, data_dir=None):
    """Search 2.2 / Verify 2.2: the first files_per_domain files of every domain, regrouped into d_count
    domains by arXiv primary category (domain_groups.csv, column D<d_count>). Returns [(group id, [Doc])]
    sorted by group id; the groups partition the same files at every d_count."""
    import sqlite3
    domains = list(domains or DOMAINS)
    group_of = {}
    with open(os.path.join(V4_DIR, "domain_groups.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            group_of[(r["domain_id"], r["primary_category"])] = r[f"D{d_count}"]
    db = os.path.join(load(data_dir)["dir"], "amtp_plaintext.db")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cat = dict(con.execute("SELECT doc_id, primary_category FROM documents WHERE is_initial = 1"))
    finally:
        con.close()
    groups = defaultdict(list)
    for d in domains:
        for doc in domain_docs(d, files_per_domain, data_dir):
            groups[group_of[(d, cat[doc.doc_id])]].append(doc)
    return sorted(groups.items())


def load_exp5_workload(path=EXP5_FILE, data_dir=None):
    """Read the shared Exp. 5 file and map doc_ids back to Doc: (meta, groups, queries, update_docs)"""
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found: run  python3 baselines/amtp_dataset.py exp5")
    with open(path, encoding="utf-8") as f:
        w = json.load(f)
    ds = load(data_dir)
    by_id = {d.doc_id: d for g in (ds["initial"], ds["pool"]) for docs in g.values() for d in docs}
    return w, [[by_id[i] for i in g] for g in w["groups"]], w["queries"], [by_id[i] for i in w["update_docs"]]


# ============================================================================
# 5) Run manifest: which machine and code produced a result file
# ============================================================================
def machine_info():
    """CPU, cores, RAM, OS and Python of this machine (read from the system, never typed by hand)"""
    import platform
    import subprocess
    import sys

    def sysctl(key):
        try:
            return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    cpu, mem = sysctl("machdep.cpu.brand_string"), sysctl("hw.memsize")
    if not cpu and os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            cpu = next((l.split(":", 1)[1].strip() for l in f if l.startswith("model name")), "")
    if not mem and hasattr(os, "sysconf"):
        try:
            mem = str(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
        except (ValueError, OSError):
            mem = ""
    mac = platform.mac_ver()[0]
    return {"cpu": cpu or platform.processor(), "machine": platform.machine(), "cores": os.cpu_count(),
            "memory_bytes": int(mem) if mem.isdigit() else None,
            "os": f"macOS {mac}" if mac else platform.platform(), "platform": platform.platform(),
            "python": sys.version.split()[0], "python_impl": platform.python_implementation()}


def write_manifest(csv_path):
    """Write <csv>.manifest.json next to a result CSV: command line, git commit, time and machine_info()"""
    import subprocess
    import sys
    import time

    def git(*cmd):
        try:
            return subprocess.run(["git", *cmd], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    out = os.path.splitext(csv_path)[0] + ".manifest.json"
    info = {"result": os.path.basename(csv_path), "command": " ".join(sys.argv),
            "written": time.strftime("%Y-%m-%d %H:%M:%S %z"), "git_commit": git("rev-parse", "HEAD"),
            "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
            "dataset": DATASET_TAG, "machine": machine_info(),
            "amtp_gamma_v": os.environ.get("AMTP_GAMMA_V", "1") != "0",   # AMTP: γ with the version v (B4 study)
            "amtp_placement": os.environ.get("AMTP_PLACEMENT", "fill"),   # AMTP: placement rule (amtp/variants.py)
            "amtp_and_prune": os.environ.get("AMTP_AND_PRUNE", "1") != "0",   # AMTP: AND pruning (amtp/server.py)
            "amtp_part_results": os.environ.get("AMTP_PART_RESULTS", "1") != "0",   # AMTP: result-only part check
            "amtp_and_greedy": os.environ.get("AMTP_AND_GREEDY", "1") != "0",   # AMTP: AND pruning planner
            "amtp_part_leaf": os.environ.get("AMTP_PART_LEAF", "1") != "0",   # AMTP: Search Tree leaf by partition
            "amtp_anchor": os.environ.get("AMTP_ANCHOR", "in-process")}   # AMTP: Root Anchor (bench make_anchor)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="check the dataset, or write the shared Exp. 1 / Exp. 5 workload file")
    ap.add_argument("mode", nargs="?", choices=["check", "queries", "exp5"], default="check")
    ap.add_argument("--data", default=None)
    ap.add_argument("--sizes", type=int, nargs="+", default=EXP1_SIZES)
    ap.add_argument("--kq", type=int, nargs="+", default=EXP1_KQS)
    ap.add_argument("--per-kq", type=int, default=EXP1_PER_KQ)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=SHARED_QUERIES)
    a = ap.parse_args()
    if a.mode == "exp5":                          # (re)write the shared Exp. 5 workload
        w = make_exp5_workload(seed=a.seed, data_dir=a.data)
        with open(EXP5_FILE, "w", encoding="utf-8") as f:   # one line per key: 160,000 doc_ids
            f.write("{\n" + ",\n".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
                                       for k, v in w.items()) + "\n}\n")
        print(f"-> {os.path.relpath(EXP5_FILE)}  ({len(w['groups'])} domains x {w['per_domain']} files, "
              f"{len(w['queries'])} queries, {len(w['update_docs'])} update files)")
    elif a.mode == "queries":                     # (re)write the shared query file
        rows = build_shared_queries(a.sizes, a.kq, a.per_kq, a.seed, data_dir=a.data)
        save_queries(a.out, rows)
        print(f"-> {os.path.relpath(a.out)}  ({len(rows)} queries, {a.per_kq} per kQ, the same at every N)")
    else:
        ds = load(a.data)                         # load
        for d in DOMAINS:                         # count per domain
            print(d, "initial", len(ds["initial"].get(d, [])), "pool", len(ds["pool"].get(d, [])))
        docs = sample(10_000, data_dir=a.data)    # try choosing 10,000 files
        for q in make_queries(docs, [1, 4])[:3]:  # try building queries
            print(q["kQ"], q["shape"], q["query"])
