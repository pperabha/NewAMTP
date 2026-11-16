"""
amtp_dataset.py
============================================================================
ตัวโหลด dataset กลางของ AMTP (arXiv, 4 domain) — ให้ทุก baseline ใช้ข้อมูลและ query ชุดเดียวกัน

Dataset: dataset-v4 (parts in datasets/arxiv/data_v4/, แตกด้วย python3 datasets/arxiv/unpack.py)
  D1 = cs, D2 = math, D3 = astro-hep, D4 = condmat-quant
  - เอกสารเริ่มต้น 125,000 ไฟล์ต่อ domain (is_initial = 1) เรียงตามเวลา (doc_id) รวม 500,000
  - insert pool 12,500 ไฟล์ต่อ domain (is_initial = 0) สำหรับ Experiment 3 / split-merge
  - keyword W(d) สกัดไว้แล้วด้วยโค้ด Phase 1 ของ AMTP (amtp/nlp.py: RAKE, kappa = 20 วลีต่อไฟล์, Norm แบบ idempotent)
    อยู่ในคอลัมน์ keywords ของ documents.csv
  ทุก scheme รวมถึง AMTP เอง (amtp_code/bench/) ใช้ keyword ชุดนี้ตรง ๆ ไม่สกัดเอง -> W(d) เหมือนกันทุก scheme
  เวลาสกัด keyword ของ AMTP รายงานแยกด้วย amtp_code/bench/extraction.py

วางข้อมูล: unpack.py แตกไว้ที่ <repo>/data/amtp_file_db_v4/  (หรือส่ง path ผ่าน --data / ตัวแปร AMTP_DATA)
  dataset-v3 เดิม (4 x 50,000, kappa = 10) ไม่มีใน NewAMTP แล้ว: ถ้ามีไฟล์ parts ของ v3 ใน datasets/arxiv/data/
  ใช้ python3 datasets/arxiv/unpack.py --v3 -> data/amtp_file_db/ แล้วใส่ --data data/amtp_file_db

การเลือก N เอกสาร (sample):
  เอา N / (จำนวน domain) ไฟล์แรกของแต่ละ domain ตามลำดับ doc_id (ไม่มีการสุ่ม)
  -> N เท่ากัน = เอกสารชุดเดียวกันเสมอ ทุก scheme ทุกเครื่อง

การสร้าง query (make_queries):
  สุ่มเอกสาร 1 ไฟล์ด้วย seed แล้วเอา k keyword ของไฟล์นั้น (เรียง doc_freq มากไปน้อย)
  -> query แบบ AND ได้ผลอย่างน้อย 1 ไฟล์เสมอ (ถ้า k <= จำนวน keyword ในไฟล์)
  รูปแบบ 4 แบบตาม AMTP Exp.1: single / conjunctive / disjunctive / or_and_or / and_or_and
  ไฟล์ query ที่บันทึกออก (results/exp1_queries.json) มี key N, kQ, shape, query, terms, domain, source_doc
  keyword เป็นวลีหลายคำได้ และเขียนใน query โดยไม่ใส่เครื่องหมายคำพูด เช่น "general method AND possible description"

ใช้จากโค้ดอื่น:
  import sys; sys.path.insert(0, "<repo>/baselines")
  from amtp_dataset import load, sample, read_bytes, insert_pool, make_queries, ground_truth
============================================================================
"""

import csv                                        # อ่าน documents.csv
import json                                       # อ่าน summary.json / เขียนไฟล์ query
import os                                         # จัดการ path
import random                                     # สุ่มเอกสารต้นแบบของ query (มี seed)
from collections import Counter, defaultdict      # นับ doc_freq / จัดกลุ่มตาม domain
from dataclasses import dataclass                 # โครงสร้างข้อมูลแบบสั้น

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # โฟลเดอร์รากของ repo
DEFAULT_DATA = os.environ.get("AMTP_DATA", os.path.join(REPO, "data", "amtp_file_db_v4"))  # ที่วาง dataset (v4)
DOMAINS = ["D1", "D2", "D3", "D4"]                # domain ทั้งหมด
DATASET_TAG = "amtp_file_db dataset-v4 (arXiv Kaggle, 4 x 125,000 + 10% insert pool, seed 42, AMTP Phase 1 keywords kappa=20)"  # ชื่อ dataset ที่จะบันทึกไว้ในไฟล์ผล


@dataclass
class Doc:
    doc_id: str                                   # รหัสเอกสาร เช่น "D1_000001"
    domain: str                                   # domain เช่น "D1"
    is_initial: bool                              # True = เอกสารเริ่มต้น, False = insert pool
    keywords: list                                # W(d) ที่สกัดไว้แล้ว (ไม่ซ้ำกันในไฟล์เดียว)
    file_path: str                                # path ของไฟล์ .txt (เทียบกับโฟลเดอร์ dataset)


# ============================================================================
# 1) โหลด dataset
# ============================================================================
def load(data_dir: str = None):
    """อ่าน documents.csv ครั้งเดียวแล้ว cache ไว้ คืน dict:
       {"initial": {domain: [Doc, ...]}, "pool": {domain: [Doc, ...]}, "dir": path}"""
    data_dir = data_dir or DEFAULT_DATA           # ใช้ path ที่ส่งมา หรือค่าเริ่มต้น
    cache = load.__dict__.setdefault("_cache", {})  # cache แยกตาม path
    if data_dir in cache:                         # เคยโหลดแล้ว
        return cache[data_dir]                    # คืนของเดิม
    path = os.path.join(data_dir, "documents.csv")  # ไฟล์หลักสำหรับ baseline
    if not os.path.exists(path):                  # ยังไม่ได้วาง dataset
        raise SystemExit(
            f"ไม่พบ {path}\n"
            "ยังไม่ได้แตก dataset -> รันจากโฟลเดอร์รากของ repo:  python3 datasets/arxiv/unpack.py\n"
            f"(หรือใส่ --data <โฟลเดอร์ dataset> / ตั้งตัวแปร AMTP_DATA)")
    initial, pool = defaultdict(list), defaultdict(list)  # แยกเอกสารเริ่มต้น / insert pool
    csv.field_size_limit(1 << 24)                 # คอลัมน์ keywords ยาวได้ (kappa = 20)
    with open(path, encoding="utf-8-sig", newline="") as f:  # utf-8-sig = ตัด BOM หัวไฟล์ออก
        for r in csv.DictReader(f):               # อ่านทีละแถว
            kws = list(dict.fromkeys(k.strip() for k in r["keywords"].split(";") if k.strip()))  # แยก keyword
            doc = Doc(r["doc_id"], r["domain_id"], r["is_initial"] == "1", kws, r["file_path"])  # สร้าง Doc
            (initial if doc.is_initial else pool)[doc.domain].append(doc)  # ใส่กลุ่มที่ถูกต้อง
    for group in (initial, pool):                 # เรียงตาม doc_id (= ลำดับเวลา) ให้แน่นอน
        for d in group:
            group[d].sort(key=lambda x: x.doc_id)
    cache[data_dir] = {"initial": dict(initial), "pool": dict(pool), "dir": data_dir}  # เก็บ cache
    return cache[data_dir]                        # คืนผล


def summary(data_dir: str = None) -> dict:
    """อ่าน summary.json (ตัวเลขสำหรับเขียน Dataset section ใน paper)"""
    with open(os.path.join(data_dir or DEFAULT_DATA, "summary.json"), encoding="utf-8") as f:
        return json.load(f)                       # คืน dict


# ============================================================================
# 2) เลือกเอกสาร
# ============================================================================
def sample(n: int, domains=None, data_dir: str = None):
    """เอกสารเริ่มต้น n ไฟล์: แบ่งเท่า ๆ กันทุก domain ที่เลือก เอาไฟล์แรก ๆ ตามลำดับ doc_id
    ตัวอย่าง n = 10,000 กับ 4 domain -> D1..D4 domain ละ 2,500 ไฟล์แรก"""
    ds = load(data_dir)                           # dataset
    domains = list(domains or DOMAINS)            # domain ที่ใช้
    per, extra = divmod(n, len(domains))          # จำนวนต่อ domain (เศษให้ domain แรก ๆ)
    out = []                                      # ผลลัพธ์
    for i, d in enumerate(domains):               # ทุก domain
        want = per + (1 if i < extra else 0)      # จำนวนที่ต้องการจาก domain นี้
        have = ds["initial"].get(d, [])           # เอกสารที่มี
        if want > len(have):                      # ขอเกินที่มี
            raise SystemExit(f"ขอ {want} ไฟล์จาก {d} แต่มีแค่ {len(have)} (N สูงสุด = {len(have):,} x จำนวน domain)")
        out.extend(have[:want])                   # เอาไฟล์แรก ๆ
    return out                                    # คืนรายการ Doc


def read_bytes(doc: Doc, data_dir: str = None) -> bytes:
    """เนื้อหาไฟล์ .txt ของเอกสาร (title + abstract) สำหรับ scheme ที่ต้องเข้ารหัสไฟล์จริง"""
    with open(os.path.join(load(data_dir)["dir"], doc.file_path), "rb") as f:  # path เทียบกับโฟลเดอร์ dataset
        return f.read()                           # คืน bytes


def insert_pool(domains=None, data_dir: str = None):
    """เอกสาร insert pool (ไม่อยู่ในชุดเริ่มต้น) สำหรับ Experiment 3 สลับ domain ทีละไฟล์ D1, D2, D3, D4, D1, ..."""
    ds = load(data_dir)                           # dataset
    lists = [ds["pool"].get(d, []) for d in (domains or DOMAINS)]  # pool ของแต่ละ domain
    out = []                                      # ผลลัพธ์
    for i in range(max(len(x) for x in lists)):   # วนตามลำดับ
        out.extend(x[i] for x in lists if i < len(x))  # หยิบ domain ละ 1 ไฟล์
    return out                                    # คืนรายการ Doc


# ============================================================================
# 3) Query และ ground truth
# ============================================================================
def doc_freq(docs) -> Counter:
    """document frequency: keyword แต่ละตัวอยู่ในกี่เอกสาร"""
    c = Counter()                                 # ตัวนับ
    for d in docs:                                # ทุกเอกสาร
        c.update(d.keywords)                      # keyword ในไฟล์เดียวไม่ซ้ำอยู่แล้ว
    return c                                      # คืนผล


def boolean_shapes(terms):
    """query 4 รูปแบบตาม AMTP Exp.1 (ชื่อและรูปแบบเหมือน se_collab boolean_shapes)"""
    t = list(terms)                               # keyword
    if len(t) == 1:                               # keyword เดียว
        return {"single": t[0]}                   # มีแบบเดียว
    half = len(t) // 2                            # แบ่งครึ่ง
    L, R = t[:half], t[half:]                     # ซ้าย / ขวา
    return {
        "conjunctive": " AND ".join(t),           # A AND B AND C AND D
        "disjunctive": " OR ".join(t),            # A OR B OR C OR D
        "or_and_or": f"({' OR '.join(L)}) AND ({' OR '.join(R)})",   # (A OR B) AND (C OR D)
        "and_or_and": f"({' AND '.join(L)}) OR ({' AND '.join(R)})",  # (A AND B) OR (C AND D)
    }


def make_queries(docs, kqs, per_kq: int = 1, seed: int = 42):
    """สร้าง query ทุก k_Q: สุ่มเอกสารต้นแบบ (seed คงที่) แล้วเอา keyword ของไฟล์นั้น k ตัว
    keyword เรียงจาก doc_freq มากไปน้อย (ผลลัพธ์ของ OR จะมีขนาดพอสมควร)
    ถ้า k มากกว่าจำนวน keyword ในไฟล์ (สูงสุด kappa = 20) จะเติมจากเอกสารสุ่มอีกไฟล์ -> AND อาจได้ผลว่าง
    คืน list ของ dict {kQ, shape, query, terms, source_doc, domain}"""
    df = doc_freq(docs)                           # doc_freq ของชุดเอกสารนี้
    out = []                                      # ผลลัพธ์
    for k in kqs:                                 # ทุก k_Q
        rng = random.Random(f"{seed}-{k}")        # seed แยกตาม k -> query ของ k หนึ่งไม่ขึ้นกับ k อื่น
        for j in range(per_kq):                   # จำนวน query ต่อ k
            cand = [d for d in docs if len(d.keywords) >= k] or docs  # ไฟล์ที่มี keyword พอ
            src = cand[rng.randrange(len(cand))]  # เอกสารต้นแบบ
            terms = sorted(src.keywords, key=lambda w: (-df[w], w))[:k]  # k keyword ที่ df สูงสุดของไฟล์นี้
            while len(terms) < k:                 # ยังไม่ครบ (k > จำนวน keyword ในไฟล์ เช่น k = 16)
                extra = docs[rng.randrange(len(docs))]  # สุ่มอีกไฟล์
                terms += [w for w in sorted(extra.keywords, key=lambda w: (-df[w], w)) if w not in terms][:k - len(terms)]
            for shape, q in boolean_shapes(terms).items():  # ทุกรูปแบบ
                out.append({"kQ": k, "q": j, "shape": shape, "query": q, "terms": terms,
                            "source_doc": src.doc_id, "domain": src.domain})
    return out                                    # คืนรายการ query


def inverted_index(docs):
    """keyword -> เซตตำแหน่งเอกสาร (0..N-1) ใช้หาคำตอบที่ถูกต้อง"""
    inv = defaultdict(set)                        # index
    for i, d in enumerate(docs):                  # ทุกเอกสาร
        for w in d.keywords:                      # ทุก keyword
            inv[w].add(i)                         # จด
    return inv                                    # คืน index


def ground_truth(inv, terms):
    """คำตอบที่ถูกต้องของ query แบบ AND: ตำแหน่งเอกสารที่มีทุก keyword"""
    sets = [inv.get(w, set()) for w in terms]     # posting ของแต่ละ keyword
    return set.intersection(*sets) if sets else set()  # intersection


def save_queries(path, rows):
    """บันทึก query เป็น JSON (key หลักเหมือน exp1_queries.json ของ SE-COLLAB + dataset/domain)"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)  # สร้างโฟลเดอร์
    with open(path, "w", encoding="utf-8") as f:  # เปิดไฟล์
        json.dump(rows, f, indent=1, ensure_ascii=False)  # เขียน


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
            "amtp_and_prune": os.environ.get("AMTP_AND_PRUNE", "0") == "1",   # AMTP: AND pruning (amtp/server.py)
            "amtp_part_results": os.environ.get("AMTP_PART_RESULTS", "0") == "1",   # AMTP: result-only part check
            "amtp_and_greedy": os.environ.get("AMTP_AND_GREEDY", "0") == "1",   # AMTP: AND pruning planner
            "amtp_part_leaf": os.environ.get("AMTP_PART_LEAF", "0") == "1"}   # AMTP: Search Tree leaf by partition
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
        ds = load(a.data)                         # โหลด
        for d in DOMAINS:                         # แสดงจำนวนต่อ domain
            print(d, "initial", len(ds["initial"].get(d, [])), "pool", len(ds["pool"].get(d, [])))
        docs = sample(10_000, data_dir=a.data)    # ลองเลือก 10,000 ไฟล์
        for q in make_queries(docs, [1, 4])[:3]:  # ลองสร้าง query
            print(q["kQ"], q["shape"], q["query"])
