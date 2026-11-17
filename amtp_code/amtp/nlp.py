"""Phase 1, Step 3 (Keyword Preparation): W(d) = { Norm(w) : w in Extract(d) } -- the RAKE prototype.

This is the extractor that produced the `keywords` column of the shared arXiv dataset
(dataset-v4, datasets/arxiv/; dataset-v3 used KAPPA = 10). In the experiments every scheme, AMTP included, reads
W(d) from documents.csv instead of re-extracting; the cost of this step is measured
separately by bench/extraction.py. (index.extract_keywords is the tiny single-word
extractor used only by the interactive demo.)

Steps
 1) normalise: tokenise, lowercase, light lemmatisation (suffix rules -ies/-s)
 2) length test: |f| < Θ_doc  -> RAKE over the whole document
                 |f| >= Θ_doc -> chunks of L_ch words, sliding by (L_ch - L_ov) words
 3) RAKE in each chunk: split candidate phrases at stop words / punctuation
    score(p) = Σ_{w∈p} deg(w) / freq(w)
 4) keep the top-κ per chunk -> union + de-duplicate + re-rank -> W_f (at most κ phrases)

Note: English text only (Thai would need a word segmenter such as PyThaiNLP).
"""
import re
from collections import defaultdict

# Phase 1 parameters fixed by the domain at setup (same values used to build dataset-v4)
THETA_DOC = 30000      # documents with more words are chunked
L_CH = 400             # chunk length (words), report: 300-500
L_OV = L_CH // 5       # chunk overlap = L_ch / 5
KAPPA = 20             # top-kappa keywords per document (dataset-v4; v3 used 10)
MAX_WORDS = 3          # max words per RAKE phrase

STOPWORDS = set("""
a about above across after afterwards again against all almost alone along already also although always am among
amongst an and another any anyhow anyone anything anyway anywhere are around as at back be became because become
becomes becoming been before beforehand behind being below beside besides between beyond both but by can cannot
could did do does doing done down due during each eg either else elsewhere enough etc even ever every everyone
everything everywhere except few for former formerly from further had has have having he hence her here hereafter
hereby herein hereupon hers herself him himself his how however i ie if in indeed into is it its itself just
keep last latter latterly least less made many may me meanwhile might more moreover most mostly much must my myself
namely neither never nevertheless next no nobody none noone nor not nothing now nowhere of off often on once one
only onto or other others otherwise our ours ourselves out over own per perhaps please put rather re same see seem
seemed seeming seems several she should since so some somehow someone something sometime sometimes somewhere still
such than that the their theirs them themselves then thence there thereafter thereby therefore therein thereupon
these they this those though through throughout thru thus to together too toward towards under until up upon us
very via was we well were what whatever when whence whenever where whereafter whereas whereby wherein whereupon
wherever whether which while whither who whoever whole whom whose why will with within without would yet you your
yours yourself yourselves
""".split())

# common verbs used as phrase delimiters (custom RAKE stoplist)
STOPWORDS |= set("""
was were is are be been being has have had will shall can may also new old within using used use make makes made
show shows showed shown include includes included including report reported reports reporting detect detected detects
observe observed note noted notes require requires required requested request requests approved approve approves
scheduled schedule submitted submit submits flagged flag initiated initiate completed complete reviewed review reviews
recorded record records found find finds given give gives taken take takes received receive receives sent send
started start began begin continued continue performed perform following follow followed followup per
admitted prescribed assigned recommended confirmed indicated raised opened closed blocked allowed logged triggered
attempted occurred identified updated
""".split())

# words that are "headings / labels" in form-like documents (domain-specific stoplist): never keywords
STOPWORDS |= set("""
affected host attending physician counterparty amount reference request type course item risk category
action diagnosis medication chief complaint history comment customer transaction student patient lab
result vital sign stable observation during contacted forwarded linked taken thb follow-up
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*|[.,;:!?()\[\]{}\"\n\t/|]")
_DELIM = set(".,;:!?()[]{}\"\n\t/|")


_NO_LEMMA = set("""
diabetes graphics logistics savings electronics physics mathematics economics news series species analytics
statistics sales sports glasses credentials diagnostics ethics politics aids status bus gas lens
""".split())


def lemmatise(w: str) -> str:
    """Light rule-based lemmatiser, used instead of a full lemmatiser to avoid a dependency."""
    if w in _NO_LEMMA:
        return w
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is", "os")):
        return w[:-1]
    return w


def tokenize(text: str):
    """Return the list of tokens (words, or None for a delimiter)."""
    out = []
    for t in _TOKEN_RE.findall(text):
        if t in _DELIM:
            out.append(None)
        else:
            out.append(normalise_token(t))
    return out


def normalise_token(t: str) -> str:
    """Norm of one word: lowercase -> drop possessive 's -> strip ' and - at both ends -> lemmatise.
    Must be idempotent (Norm(Norm(w)) = Norm(w)): keywords stored in documents.csv go through Norm again at
    query time (before the fix, "government's" -> "government'" but the query "government'" -> "government", so it
    was not found)."""
    w = t.lower()
    if w.endswith("'s"):
        w = w[:-2]
    w = w.strip("'-")
    return lemmatise(w).strip("'-")


def word_count(tokens) -> int:
    return sum(1 for t in tokens if t is not None)


def chunk_tokens(tokens, L_ch: int, L_ov: int):
    """Split into chunks of L_ch words with stride L_ch - L_ov words (overlap of L_ov words)."""
    word_pos = [i for i, t in enumerate(tokens) if t is not None]
    n = len(word_pos)
    stride = L_ch - L_ov
    chunks = []
    start = 0
    while start < n:
        end = min(start + L_ch, n)
        t0 = word_pos[start]
        t1 = word_pos[end - 1] + 1
        chunks.append({"word_start": start, "word_end": end, "tokens": tokens[t0:t1]})
        if end == n:
            break
        start += stride
    return chunks


def _valid_word(w: str) -> bool:
    return len(w) >= 2 and not w.isdigit() and not re.fullmatch(r"[0-9\-']+", w)


def candidate_phrases(tokens, max_words=3):
    phrases, cur = [], []
    for t in tokens:
        if t is None or t in STOPWORDS or not _valid_word(t):
            if cur:
                phrases.append(tuple(cur))
            cur = []
        else:
            cur.append(t)
    if cur:
        phrases.append(tuple(cur))
    return [p for p in phrases if 1 <= len(p) <= max_words]


def rake(tokens, max_words=3):
    """RAKE: score(p) = Σ deg(w)/freq(w)"""
    phrases = candidate_phrases(tokens, max_words)
    freq, deg = defaultdict(int), defaultdict(int)
    for p in phrases:
        for w in p:
            freq[w] += 1
            deg[w] += len(p)       # deg(w) counts the word itself (= co-occurrence degree + freq)
    word_score = {w: deg[w] / freq[w] for w in freq}
    scores = {}
    for p in set(phrases):
        scores[" ".join(p)] = round(sum(word_score[w] for w in p), 4)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked, {"n_candidates": len(phrases), "n_unique": len(scores)}


def extract_keywords(text: str, theta_doc: int, L_ch: int, L_ov: int, kappa: int, max_words=3):
    """Return (W_f, trace); the trace shows every step in the UI."""
    tokens = tokenize(text)
    n_words = word_count(tokens)
    trace = {
        "n_words": n_words,
        "theta_doc": theta_doc,
        "length_test": f"|d| = {n_words} {'≤' if n_words <= theta_doc else '>'} τ = {theta_doc}",
        "mode": "whole" if n_words <= theta_doc else "chunked",
        "normalised_preview": " ".join(t if t is not None else "|" for t in tokens[:80]),
        "chunks": [],
    }
    if n_words <= theta_doc:
        segs = [{"word_start": 0, "word_end": n_words, "tokens": tokens}]
    else:
        segs = chunk_tokens(tokens, L_ch, L_ov)
    best = {}
    for ci, seg in enumerate(segs):
        ranked, stats = rake(seg["tokens"], max_words)
        top = ranked[:kappa]
        for kw, sc in top:
            best[kw] = max(best.get(kw, 0), sc)
        words_only = [t for t in seg["tokens"] if t is not None]
        trace["chunks"].append({
            "index": ci,
            "word_range": [seg["word_start"], seg["word_end"]],
            "overlap_with_prev": (L_ov if ci > 0 and trace["mode"] == "chunked" else 0),
            "preview": " ".join(words_only[:30]) + (" ..." if len(words_only) > 30 else ""),
            "candidates": stats["n_unique"],
            "top": [{"phrase": k, "score": s} for k, s in top],
        })
    final = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))[:kappa]
    trace["union_size"] = len(best)
    trace["keywords"] = [{"keyword": k, "score": s} for k, s in final]
    return [k for k, _ in final], trace


def phase1_keywords(text: str) -> list:
    """W(d) with the fixed Phase 1 parameters (identical to documents.csv of dataset-v4)."""
    return extract_keywords(text, THETA_DOC, L_CH, L_OV, KAPPA, MAX_WORDS)[0]


def norm(w: str) -> str:
    """Norm(w): the single keyword normalisation used at upload (W(d)) and at query time.
    Tokenise, lowercase, drop possessive 's, light lemmatisation, join with one space.
    Idempotent, so a keyword already in W(d) maps to itself."""
    return " ".join(t for t in tokenize(w) if t is not None)


normalise_query_term = norm          # older name, same function
