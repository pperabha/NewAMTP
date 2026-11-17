#!/usr/bin/env python3
"""
build_amtp_file_db.py
=====================
Build the plaintext database for AMTP: 4 domains x 50,000 files (.txt) with the keywords of every file,
real data from the arXiv dataset on Kaggle (1 file = 1 document: title + abstract).

Usage (Python 3.8+ only, nothing else to install):
    1) download https://www.kaggle.com/datasets/Cornell-University/arxiv
       and extract it to get arxiv-metadata-oai-snapshot.json
    2) put that file in the same folder as this script
    3) run:   python build_amtp_file_db.py arxiv-metadata-oai-snapshot.json

Output: folder amtp_file_db/
    files/D1_cs/D1_000001.txt ...        50,000 files per domain (initial set)
    insert_pool/D1_cs/D1_I00001.txt ...   spare files for insert experiments (not counted in the 50,000)
    amtp_plaintext.db                     SQLite: documents, keywords, postings (not encrypted)
    documents.csv                         doc_id, domain, path, keywords (opens in Excel)
    domain_keywords.csv                   keyword and number of files containing it, per domain
    summary.json, README.txt

Mapping to the paper:
    D_i            -> 4 domains (default: cs, math, physics, stat; arXiv primary category)
    d              -> one plaintext file (title + abstract)
    id_d           -> doc_id, domain-unique opaque identifier (e.g. D1_000001)
    W(d)           -> RAKE keywords extracted from exactly the file text, normalized (Phase 1 Step 3)
    Insert/Delete  -> insert_pool/ files + any initial file (Phase 2)
"""

import argparse
import csv
import json
import os
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from email.utils import parsedate_to_datetime

# --------------------------------------------------------------------------
# Domains: arXiv primary category (first entry of "categories") -> domain group
# --------------------------------------------------------------------------
PHYSICS_ARCHIVES = {
    "astro-ph", "cond-mat", "gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th", "math-ph", "nlin",
    "nucl-ex", "nucl-th", "physics", "quant-ph", "acc-phys", "ao-sci", "atom-ph", "chem-ph",
    "plasm-ph", "supr-con", "mtrl-th", "chao-dyn", "patt-sol", "solv-int", "adap-org", "comp-gas",
}
GROUPS = {
    "cs": {"cs", "cmp-lg"},
    "math": {"math", "alg-geom", "dg-ga", "funct-an", "q-alg"},
    "physics": PHYSICS_ARCHIVES,
    "stat": {"stat"},
    "eess": {"eess"},
    "q-bio": {"q-bio"},
    "q-fin": {"q-fin"},
    "econ": {"econ"},
}


def group_of(primary):
    archive = primary.split(".")[0]
    for g, archives in GROUPS.items():
        if archive in archives:
            return g
    return None


# --------------------------------------------------------------------------
# RAKE keyword extraction (Rose et al., 2010) -- fixed parameters, stdlib only
# --------------------------------------------------------------------------
STOPWORDS = frozenset("""
a about above across after afterwards again against all almost alone along already also although always am among amongst
an and another any anyhow anyone anything anyway anywhere are around as at back be became because become becomes becoming
been before beforehand behind being below beside besides between beyond both but by can cannot could did do does doing done
down due during each eg either else elsewhere enough etc even ever every everyone everything everywhere except few first for
former formerly from further get gets getting give given go going gone got had has have having he hence her here hereafter
hereby herein hereupon hers herself him himself his how however i ie if in inc indeed into is it its itself just keep last
latter latterly least less let lets like likely ltd made make many may me meanwhile might mine more moreover most mostly
much must my myself namely neither never nevertheless next no nobody none noone nor not nothing now nowhere of off often on
once one only onto or other others otherwise our ours ourselves out over own per perhaps please put rather re really said
same see seem seemed seeming seems several she should since so some somehow someone something sometime sometimes somewhere
still such take than that the their theirs them themselves then thence there thereafter thereby therefore therein thereupon
these they thing things this those though through throughout thru thus to together too toward towards under until up upon
us use used using very via want was we well were what whatever when whence whenever where whereafter whereas whereby wherein
whereupon wherever whether which while whither who whoever whole whom whose why will with within without would yet you
your yours yourself yourselves
paper article work propose proposed proposes show shows shown showed present presents presented demonstrate demonstrates
obtain obtained consider considered based new novel recent recently known various different several respectively
study studies studied investigate investigated discuss discussed
""".split())

LATEX_MATH = re.compile(r"\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", re.S)
LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?(\{[^}]*\})?")
PHRASE_SPLIT = re.compile(r"[.!?,;:\"()\[\]{}<>|/\\=*_+~`#&%$@^\t]+|\s[-]+\s")
TOKEN = re.compile(r"[a-z0-9']+")


def rake(text, top_k, max_words, min_word_len):
    """Top-k RAKE phrases, normalized (lowercase, single-spaced), deterministic order."""
    text = LATEX_CMD.sub(" , ", LATEX_MATH.sub(" , ", text))
    text = re.sub(r"\s+", " ", text.lower())
    phrases = []
    for frag in PHRASE_SPLIT.split(text):
        cur = []
        for tok in TOKEN.findall(frag) + [None]:
            t = tok.strip("'") if tok else None
            if t is None or t in STOPWORDS or len(t) < min_word_len or not t.isalpha():
                if cur and len(cur) <= max_words:
                    phrases.append(tuple(cur))
                cur = []
            else:
                cur.append(t)
    if not phrases:
        return []
    freq, degree = Counter(), Counter()
    for p in phrases:
        for w in p:
            freq[w] += 1
            degree[w] += len(p)
    score = {w: degree[w] / freq[w] for w in freq}
    ranked = sorted({" ".join(p): sum(score[w] for w in p) for p in set(phrases)}.items(),
                    key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:top_k]]


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def created_date(rec):
    try:
        return parsedate_to_datetime(rec["versions"][0]["created"]).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return (rec.get("update_date") or "") + " 00:00:00"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build the AMTP 4-domain plaintext file database from Kaggle arXiv")
    ap.add_argument("arxiv_json", help="arxiv-metadata-oai-snapshot.json")
    ap.add_argument("--out", default="amtp_file_db")
    ap.add_argument("--domains", default="cs,math,physics,stat", help="4 groups, e.g. cs,math,physics,eess")
    ap.add_argument("--per-domain", type=int, default=50_000, help="initial files per domain")
    ap.add_argument("--extra", type=int, default=5_000, help="insert-pool files per domain (not in the 50,000)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--top-k", type=int, default=15, help="RAKE: max keywords per file")
    ap.add_argument("--max-words", type=int, default=3, help="RAKE: max words per keyword phrase")
    ap.add_argument("--min-word-len", type=int, default=3, help="RAKE: min letters per word")
    ap.add_argument("--min-abstract-words", type=int, default=30)
    args = ap.parse_args()

    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    for d in domains:
        if d not in GROUPS:
            sys.exit("Unknown domain group '%s'. Choose from: %s" % (d, ", ".join(GROUPS)))
    need = args.per_domain + args.extra
    want = need + max(200, need // 100)          # small buffer for files that yield no keyword
    rng = random.Random(args.seed)

    # ---- One pass: reservoir-sample `want` papers per domain ----
    print("Reading %s (about 2.5M papers, takes a few minutes) ..." % args.arxiv_json)
    res = {d: [] for d in domains}
    seen = {d: 0 for d in domains}
    lines = skipped = 0
    with open(args.arxiv_json, encoding="utf-8") as f:
        for line in f:
            lines += 1
            if lines % 250_000 == 0:
                print("  %d papers read  %s" % (lines, {d: seen[d] for d in domains}))
            try:
                rec = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            cats = (rec.get("categories") or "").split()
            if not cats:
                continue
            g = group_of(cats[0])
            if g not in res:
                continue
            abstract = clean(rec.get("abstract"))
            title = clean(rec.get("title"))
            if len(abstract.split()) < args.min_abstract_words or "withdrawn" in abstract.lower()[:200]:
                continue
            item = (str(rec.get("id")), title, abstract, cats[0], " ".join(cats), created_date(rec))
            n = seen[g]
            if n < want:
                res[g].append(item)
            else:
                j = rng.randint(0, n)
                if j < want:
                    res[g][j] = item
            seen[g] = n + 1
    print("Done: %d papers read. Eligible per domain: %s" % (lines, seen))
    short = [d for d in domains if seen[d] < need]
    if short:
        sys.exit("Not enough papers in %s (need %d each). Try another group with --domains." % (short, need))

    # ---- Build documents: keywords from exactly the file text ----
    os.makedirs(args.out, exist_ok=True)
    db_path = os.path.join(args.out, "amtp_plaintext.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE domains  (domain_id TEXT PRIMARY KEY, name TEXT, arxiv_group TEXT, initial_files INTEGER, insert_pool_files INTEGER);
        CREATE TABLE documents(doc_id TEXT PRIMARY KEY, domain_id TEXT, is_initial INTEGER, file_path TEXT,
                               arxiv_id TEXT, title TEXT, primary_category TEXT, categories TEXT, created TEXT,
                               n_keywords INTEGER, content TEXT);
        CREATE TABLE keywords (keyword_id INTEGER PRIMARY KEY, keyword TEXT UNIQUE);
        CREATE TABLE postings (keyword_id INTEGER, doc_id TEXT, PRIMARY KEY (keyword_id, doc_id)) WITHOUT ROWID;
    """)
    kw_id = {}
    csv_rows = []
    dom_df = {}
    stats = {}
    for di, g in enumerate(domains, 1):
        dom = "D%d" % di
        items = sorted(res[g])                                 # canonical order before shuffling
        rng.shuffle(items)
        docs = []
        no_kw = 0
        for it in items:
            if len(docs) == need:
                break
            text = it[1] + "\n\n" + it[2]
            kws = rake(text, args.top_k, args.max_words, args.min_word_len)
            if not kws:
                no_kw += 1
                continue
            docs.append((it, text, kws))
        initial, pool = docs[:args.per_domain], docs[args.per_domain:]
        initial.sort(key=lambda x: (x[0][5], x[0][0]))          # chronological = insertion order
        pool.sort(key=lambda x: (x[0][5], x[0][0]))
        df = Counter()
        for is_init, group, prefix, sub in [(1, initial, dom + "_", "files"), (0, pool, dom + "_I", "insert_pool")]:
            folder = os.path.join(args.out, sub, "%s_%s" % (dom, g))
            os.makedirs(folder, exist_ok=True)
            width = 6 if is_init else 5
            rows, post = [], []
            for n, (it, text, kws) in enumerate(group, 1):
                doc_id = "%s%0*d" % (prefix, width, n)
                rel = "%s/%s_%s/%s.txt" % (sub, dom, g, doc_id)
                with open(os.path.join(args.out, rel), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text + "\n")
                for k in kws:
                    if k not in kw_id:
                        kw_id[k] = len(kw_id) + 1
                        con.execute("INSERT INTO keywords VALUES (?,?)", (kw_id[k], k))
                    post.append((kw_id[k], doc_id))
                    if is_init:
                        df[k] += 1
                rows.append((doc_id, dom, is_init, rel, it[0], it[1], it[3], it[4], it[5], len(kws), text))
                csv_rows.append([doc_id, dom, g, is_init, rel, it[0], len(kws), "; ".join(kws)])
            con.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
            con.executemany("INSERT INTO postings VALUES (?,?)", post)
        con.execute("INSERT INTO domains VALUES (?,?,?,?,?)", (dom, g, ",".join(sorted(GROUPS[g])), len(initial), len(pool)))
        con.commit()
        dom_df[dom] = (g, df)
        kpf = sorted(len(x[2]) for x in initial)
        stats[dom] = {
            "name": g, "initial_files": len(initial), "insert_pool_files": len(pool),
            "eligible_papers_in_arxiv": seen[g], "dropped_no_keyword": no_kw,
            "distinct_keywords": len(df), "keyword_postings": sum(df.values()),
            "keywords_per_file": {"mean": round(sum(kpf) / len(kpf), 2), "median": kpf[len(kpf) // 2],
                                  "min": kpf[0], "max": kpf[-1]},
            "max_keyword_doc_freq": max(df.values()),
            "keywords_in_2plus_files": sum(1 for v in df.values() if v >= 2),
            "created_range": [initial[0][0][5], initial[-1][0][5]],
        }
        print("  %s (%s): %d files + %d insert-pool, %d distinct keywords"
              % (dom, g, len(initial), len(pool), len(df)))

    con.executescript("""
        CREATE INDEX idx_postings_doc ON postings(doc_id);
        CREATE INDEX idx_documents_domain ON documents(domain_id, is_initial);
        CREATE VIEW domain_keyword_df AS
            SELECT d.domain_id, k.keyword, COUNT(*) AS doc_freq
            FROM postings p JOIN keywords k ON k.keyword_id = p.keyword_id
                            JOIN documents d ON d.doc_id = p.doc_id
            WHERE d.is_initial = 1
            GROUP BY d.domain_id, k.keyword;
    """)
    con.commit()
    con.close()

    with open(os.path.join(args.out, "documents.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "domain_id", "domain_name", "is_initial", "file_path", "arxiv_id", "n_keywords", "keywords"])
        w.writerows(csv_rows)
    with open(os.path.join(args.out, "domain_keywords.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["domain_id", "domain_name", "keyword", "doc_freq"])
        for dom, (g, df) in dom_df.items():
            for k, v in sorted(df.items(), key=lambda kv: (-kv[1], kv[0])):
                w.writerow([dom, g, k, v])

    summary = {
        "source": "arXiv metadata (Kaggle: Cornell-University/arxiv), one file = title + abstract",
        "seed": args.seed, "papers_read": lines,
        "domains": stats,
        "total_initial_files": sum(s["initial_files"] for s in stats.values()),
        "keyword_extraction": {"method": "RAKE", "top_k_per_file": args.top_k,
                               "max_words_per_keyword": args.max_words, "min_word_len": args.min_word_len,
                               "normalization": "LaTeX removed, lowercase, single-spaced, deduplicated per file"},
    }
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(README.format(n=args.per_domain, extra=args.extra, doms=", ".join(
            "D%d=%s" % (i, g) for i, g in enumerate(domains, 1)), seed=args.seed, k=args.top_k))
    print("\nAll done -> %s" % os.path.abspath(args.out))


README = """AMTP plaintext file database  (source: arXiv on Kaggle, seed {seed})
Domains: {doms}

files/<domain>/          {n} plaintext files per domain = the initial dataset. Each file = title + abstract.
                         File order (doc_id) is chronological, i.e. the order to insert them.
insert_pool/<domain>/    {extra} more files per domain that are NOT in the initial set (for insertion experiments).
amtp_plaintext.db        SQLite database, NOT encrypted (the Data Owner encrypts it in Phase 1):
                           documents(doc_id, domain_id, is_initial, file_path, arxiv_id, title,
                                     primary_category, categories, created, n_keywords, content)
                           keywords(keyword_id, keyword)
                           postings(keyword_id, doc_id)        = plaintext inverted index, i.e. W(d)
                           domains(domain_id, name, ...)
                           view domain_keyword_df(domain_id, keyword, doc_freq)
                         Open with "DB Browser for SQLite" (free) or Python's sqlite3.
documents.csv            same documents with their keywords, opens in Excel.
domain_keywords.csv      every keyword and how many initial files contain it, per domain.
summary.json             numbers for the dataset description in the paper.

Keywords W(d): RAKE, at most {k} phrases per file (1-3 words each), LaTeX removed, lowercase.
Ground truth: a single-keyword query on domain Di must return exactly the doc_ids in
  SELECT p.doc_id FROM postings p JOIN keywords k USING(keyword_id) JOIN documents d USING(doc_id)
  WHERE k.keyword = '...' AND d.domain_id = 'D1' AND d.is_initial = 1;
"""

if __name__ == "__main__":
    main()
