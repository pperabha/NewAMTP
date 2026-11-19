"""
plot_p32.py
============================================================================
Every figure of paper (32), Experiments 1-5 (docs/reports/2026-11-19-paper32-figure-plan.md): line charts only,
no title (the caption is in LaTeX), png + pdf, one metric per file so the paper can pick and combine them.

  .venv/bin/python baselines/plot_p32.py                       # data: baselines/results/runs/cloud (git-ignored copies)
  .venv/bin/python baselines/plot_p32.py --data baselines/results/paper32/data --out baselines/results/paper32/figures
  .venv/bin/python baselines/plot_p32.py --with-du             # Exp. 5: add Du's multi-cloud points (option B)
  .venv/bin/python baselines/plot_p32.py --run p32_exp2=<dir>  # take one run from another folder

Runs (folder <data>/<name>, or the first <data>/<name>_w* copy made by the Mac watcher):
  p32_ex1_search1         search1                Exp. 1 single domain (x = kQ at N = 100k, x = N at the fixed kQ)
  p32_x_search_verify     xsearch, xverify       Exp. 1 multi-domain Boolean shapes, Exp. 2 multi-domain verify
  p32_xdomains            xdomains               Exp. 1 / 2 over D = 1..32 (the same files regrouped)
  p32_ex2_verify1_tamper  verify1, tamper        Exp. 2 single-domain verify, tamper detection
  p32_exp2_exp5           exp2, exp5             Exp. 2 clustered / dispersed / partition_spread ((32)); Exp. 5 (+ Du clouds
                                                 with --with-du); p32_exp2 / p32_ex5 are taken if present
  p32_ex3                 update, update_n       Exp. 3 (x = b at N = 100k; x = N at b = 100)
  ex4_*skew*              splitmerge, skewproto  Exp. 4 (one folder per skew level, six jobs each)

Values: every timing is the MEAN of the run's 10 repetitions after 3 warm-up runs (column <metric>_ms, decision #46);
a query-level point (Exp. 1, 2, 5 queries, tamper verification) = the MEDIAN over the queries / keywords of that x,
with interquartile-range error bars (decision #66, issue #72); update-level points (Exp. 3, Exp. 4, update isolation,
Sepolia) = the mean over runs / batches / updates (#46), no bars. Every plotted number (and q1 / q3) goes to
<out>/figure_points.csv and every figure is listed with its data and fairness note in <out>/README.md.

Fair comparison (checked in each scheme's code, figure plan "ความยุติธรรม"):
  server search time = the server's posting retrieval + Boolean evaluation, without proof generation and without
  fetching records: AMTP server_search_pf (bench_split.run), SE-COLLAB / Du search_no_fetch (Du: slowest cloud),
  Chen server_total (no proof beyond an XOR and no fetch; Chen's server does NOT evaluate the AND: the DU decrypts
  the bitmaps and ANDs them). end-to-end = query generation + server + DU verification for every scheme (record
  decryption excluded; AMTP's anchored-root read excluded and reported apart). SE-COLLAB rows use proof_mode=paths.
============================================================================
"""
import argparse
import csv
import glob
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402
from plot_results import AXIS, EXP4_STYLE, GRID, INK2, KB, NAME, STYLE, SURFACE, plt  # noqa: E402

ORDER = ("amtp", "chen", "secollab", "du")
PAIR = ("amtp", "secollab")                 # multi-domain Boolean and multi-domain verify: SE-COLLAB only (owner)
COL = {                                    # metric -> scheme -> column (without _ms)
    "query_gen": {s: "query_gen" for s in ORDER},
    "search": {"amtp": "server_search_pf", "chen": "server_total", "secollab": "search_no_fetch",
               "du": "search_no_fetch"},
    "server": {s: "server_total" for s in ORDER},
    "proof": {"amtp": "server_proof", "secollab": "proof_gen"},      # Chen / Du: no separate proof generation
    "verify": {s: "verify_total" for s in ORDER},
    "e2e": {s: "end_to_end" for s in ORDER},
    "proof_kb": {s: "proof_bytes" for s in ORDER},
}
YLABEL = {"query_gen": "Query generation time (ms)", "search": "Server search time (ms)",
          "server": "Server time (ms)", "proof": "Proof generation time (ms)",
          "verify": "DU verification time (ms)", "e2e": "End-to-end time (ms)", "proof_kb": "Proof size (KB)"}
SHAPES = {"AND": "AND", "OR": "OR", "AND_of_OR": "(A∨B)∧(C∨D)", "OR_of_AND": "(A∧B)∨(C∧D)"}
KINDS = {"modify": "Modified records", "hide": "Hidden records", "inject": "Injected records",
         "old_version": "Old versions"}
LAYOUT_LS = {"clustered": "-", "dispersed": "--", "partition_spread": ":"}
OP_LS = {"insert": "-", "delete": "--", "hot_delete": "--"}
VARIANTS = ("AMTP", "Static-MT", "Global-MT(v)", "AMTP (full protocol)")
V_STYLE = {**EXP4_STYLE, "AMTP (full protocol)": ("#173f73", "D", "-.")}

POINTS, INDEX = [], []
DATA, OUT, OVR = None, None, {}


# ---------------------------------------------------------------- data
ALIASES = {"p32_exp2": ["p32_exp2_exp5"], "p32_ex5": ["p32_exp2_exp5"]}   # w10 ran exp2 + exp5 as one run (#68 re-run)


def find(name):
    """folder of run <name>: --run override, <data>/<name>, the first <data>/<name>_w* copy (never *_aborted_*),
    then the same for its aliases (a run that holds several steps)"""
    if name in OVR:
        return OVR[name]
    for n in ALIASES.get(name, []) + [name]:
        p = os.path.join(DATA, n)
        if os.path.isdir(p):
            return p
        g = [d for d in sorted(glob.glob(p + "_w*")) if "aborted" not in d]
        if g:
            return g[0]
    return None


def read(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status", "ok") in ("ok", "")]


def rows(run, scheme, suite, sub=""):
    rs = read(os.path.join(run, scheme, sub, f"{scheme}_{suite}.csv")) if run else []
    if scheme == "secollab":
        rs = [r for r in rs if r.get("proof_mode", "paths") in ("paths", "")]
    return rs


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def mean_by(rs, key, col, scale=1.0):
    """{x: mean of col over the rows of x = key(row)}; empty / missing values skipped"""
    g = {}
    for r in rs:
        v = num(r.get(col))
        if v is not None:
            g.setdefault(key(r), []).append(v * scale)
    return {x: statistics.mean(v) for x, v in g.items()}


class Pts(dict):
    """{x: median}; .err = {x: (q1, q3)} drawn as IQR error bars"""
    err = None


def median_by(rs, key, col, scale=1.0):
    """{x: median of col over the rows (queries) of x = key(row)} with the interquartile range in .err (#66)"""
    g = {}
    for r in rs:
        v = num(r.get(col))
        if v is not None:
            g.setdefault(key(r), []).append(v * scale)
    out = Pts({x: statistics.median(v) for x, v in g.items()})
    out.err = {}
    for x, v in g.items():
        q1, _, q3 = statistics.quantiles(v, n=4, method="inclusive") if len(v) > 1 else (v[0], v[0], v[0])
        out.err[x] = (q1, q3)
    return out


def metric_pts(rs, scheme, metric, key):
    col = COL[metric].get(scheme)
    if col is None:
        return {}
    if metric == "proof_kb":
        return median_by(rs, key, col, 1 / KB)
    return median_by(rs, key, col + "_ms")


# ---------------------------------------------------------------- drawing
def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=10)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def log_axis(axis):
    axis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    axis.set_minor_formatter(NullFormatter())


def S(label, color, marker, ls, pts):
    return {"label": label, "color": color, "marker": marker, "ls": ls, "pts": pts}


def scheme_series(scheme, pts, suffix="", ls="-"):
    color, marker = STYLE[scheme]
    return S(NAME[scheme] + suffix, color, marker, ls, pts)


def figure(fig_id, series, xlabel, ylabel, source, note="", logx=False, logy=True, xticks=None, kfmt=False,
           pct=False, vline=None):
    """one line chart; skipped (not an error) when no series has a point"""
    series = [s for s in series if s["pts"]]
    if not series:
        print(f"   skip {fig_id} (no data)")
        return
    f, ax = plt.subplots(figsize=(5.4, 4.0), dpi=200)
    f.patch.set_facecolor(SURFACE)
    style(ax)
    for i, s in enumerate(series):
        xs = sorted(s["pts"])
        ys = [s["pts"][x] for x in xs]
        # detection rates sit on the same 0 / 100 % lines: earlier series drawn wider so every scheme stays visible
        lw, ms = (3.2 - 0.6 * i, 9 - 1.5 * i) if pct else (1.8, 5)
        err = getattr(s["pts"], "err", None)
        if err:
            lo = [max(0.0, y - err[x][0]) for x, y in zip(xs, ys)]
            hi = [max(0.0, err[x][1] - y) for x, y in zip(xs, ys)]
            ax.errorbar(xs, ys, yerr=[lo, hi], color=s["color"], marker=s["marker"], linestyle=s["ls"], linewidth=lw,
                        markersize=ms, label=s["label"], capsize=3, elinewidth=1.0, capthick=1.0)
        else:
            ax.plot(xs, ys, color=s["color"], marker=s["marker"], linestyle=s["ls"], linewidth=lw, markersize=ms,
                    label=s["label"])
        for x, y in zip(xs, ys):
            row = {"figure": fig_id, "series": s["label"], "x": x, "y": round(y, 6)}
            if err:
                row.update(q1=round(err[x][0], 6), q3=round(err[x][1], 6))
            POINTS.append(row)
    allx = sorted({x for s in series for x in s["pts"]})
    if logx:
        ax.set_xscale("log")
        log_axis(ax.xaxis)
        if xticks is None and len(allx) <= 8:              # label the measured points only (no 5000 next to 10000)
            xticks = allx
    if logy and not pct:
        ax.set_yscale("log")
        log_axis(ax.yaxis)
    if pct:
        ax.set_ylim(-5, 105)
    if xticks is not None:
        ax.set_xticks(xticks)
        ax.xaxis.set_minor_formatter(NullFormatter())
        if not kfmt:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1000 else f"{v:g}"))
    if kfmt:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k"))
    if vline is not None:                                  # (x, label): e.g. where the deletions start
        ax.axvline(vline[0], color=INK2, linestyle=":", linewidth=1.0)
        ax.annotate(vline[1], (vline[0], 1), xycoords=("data", "axes fraction"), xytext=(4, -2),
                    textcoords="offset points", va="top", fontsize=8.5, color=INK2)
    ax.set_xlabel(xlabel, color=INK2, fontsize=11)
    ax.set_ylabel(ylabel, color=INK2, fontsize=11)
    ax.legend(frameon=False, fontsize=8.5, loc="best")
    f.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, fig_id)
    for ext in ("png", "pdf"):
        f.savefig(f"{path}.{ext}", facecolor=SURFACE, dpi=200)
    plt.close(f)
    INDEX.append((fig_id, source, note))
    print("->", os.path.relpath(path + ".png"))


NOTE_SEARCH = ("server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not "
               "evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud")
NOTE_E2E = "query generation + server + DU verification; record decryption and AMTP's root read excluded"


# ---------------------------------------------------------------- Exp. 1
def exp1():
    run = find("p32_ex1_search1")
    data = {s: rows(run, s, "search_single") for s in ORDER}
    amtp = data["amtp"]
    if amtp:
        sizes = sorted({int(r["N"]) for r in amtp})
        fix = 100_000 if 100_000 in sizes else max(sizes)
        small = [r for r in amtp if int(r["N"]) != fix]
        nkq = sorted({int(r["kQ"]) for r in small})
        for m in ("search", "query_gen", "server", "e2e", "verify"):
            note = NOTE_SEARCH if m == "search" else NOTE_E2E if m == "e2e" else ""
            figure(f"e1_single_kq_{m}", [scheme_series(s, metric_pts([r for r in data[s] if int(r["N"]) == fix],
                                                                     s, m, lambda r: int(r["kQ"])))
                                         for s in ORDER],
                   "Number of keywords $k_Q$", YLABEL[m], f"{run} search_single N={fix}", note,
                   xticks=sorted({int(r["kQ"]) for r in amtp}))
            if len(nkq) == 1:
                figure(f"e1_single_n_{m}", [scheme_series(s, metric_pts([r for r in data[s] if int(r["kQ"]) == nkq[0]],
                                                                        s, m, lambda r: int(r["N"])))
                                            for s in ORDER],
                       "Files in the domain $N$", YLABEL[m], f"{run} search_single kQ={nkq[0]}", note,
                       xticks=sizes, kfmt=True)
    run = find("p32_x_search_verify")
    multi = {s: rows(run, s, "search_multi") for s in PAIR}
    for shape in SHAPES:
        for m in ("search", "e2e", "query_gen", "server", "verify"):
            rs = {s: [r for r in multi[s] if r["shape"] == shape] for s in PAIR}
            if not rs["amtp"]:
                continue
            figure(f"e1_multi_{shape}_{m}", [scheme_series(s, metric_pts(rs[s], s, m, lambda r: int(r["kQ"])))
                                             for s in PAIR],
                   "Number of keywords $k_Q$", YLABEL[m], f"{run} search_multi shape={shape} (4 domains)",
                   (NOTE_SEARCH if m == "search" else "") + "; SE-COLLAB only (multi-domain Boolean)",
                   xticks=sorted({int(r["kQ"]) for r in rs["amtp"]}))
    run = find("p32_xdomains")
    xd = {s: rows(run, s, "domains_scaling") for s in PAIR}
    for m in ("search", "e2e", "verify", "server", "query_gen"):
        figure(f"e1_domains_{m}", [scheme_series(s, metric_pts(xd[s], s, m, lambda r: int(r["domains"])))
                                   for s in PAIR],
               "Number of domains $D$", YLABEL[m], f"{run} domains_scaling", "same files regrouped into D domains",
               logx=True, xticks=sorted({int(r["domains"]) for r in xd["amtp"]}) or None)


# ---------------------------------------------------------------- Exp. 2
SHORT = {"modify": "modified", "hide": "hidden", "inject": "injected", "old_version": "old version"}


def attack_types(tam, run):
    """one panel: how many of the 4 attack types each scheme detects in EVERY run, vs tampered files t
    (equal lines drawn slightly apart; the note at the right end names what is missed)"""
    res, notes = {}, {}
    for s in ORDER:
        agg = {}
        for r in tam[s]:
            if r["tamper"] == "none" or r.get("detected_runs", "") == "":
                continue
            a = agg.setdefault((int(r["tampered"]), r["tamper"]), [0, 0])
            a[0] += int(r["detected_runs"])
            a[1] += int(r["runs"])
        if not agg:
            continue
        ts = sorted({t for t, _ in agg})
        kinds = sorted({k for _, k in agg}, key=list(SHORT).index)
        ys = [sum(1 for k in kinds if agg.get((t, k), [0, 0])[1] and agg[(t, k)][0] == agg[(t, k)][1]) for t in ts]
        missed = [SHORT[k] for k in kinds if any(agg[(t, k)][0] < agg[(t, k)][1] for t in ts if (t, k) in agg)]
        if len(kinds) < 4:
            notes[s] = f"{ys[-1]} of {len(kinds)} applicable  ·  no modify / old model"
        elif missed:
            notes[s] = f"{ys[-1]} of 4  ·  misses " + ", ".join(missed)
        else:
            notes[s] = f"{ys[-1]} of 4  ·  every attack"
        res[s] = (ts, ys)
    if "amtp" not in res:
        return
    f, ax = plt.subplots(figsize=(7.6, 4.4), dpi=200)
    f.patch.set_facecolor(SURFACE)
    style(ax)
    seen = {}
    for s in ORDER:
        if s not in res:
            continue
        ts, ys = res[s]
        tie = seen.get(ys[0], 0)
        seen[ys[0]] = tie + 1
        off = 0.12 * tie
        color, marker = STYLE[s]
        ax.plot(ts, [y - off for y in ys], color=color, marker=marker, markersize=7, markeredgecolor="white",
                linewidth=2.2, label=NAME[s])
        ax.annotate(notes[s], (ts[-1], ys[-1] - off), xytext=(8, -9 if tie else 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK2)
        for t, y in zip(ts, ys):
            POINTS.append({"figure": "e2_tamper_attack_types", "series": NAME[s], "x": t, "y": y})
    ts = res["amtp"][0]
    ax.set_xscale("log")
    ax.set_xticks(ts)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(ts[0] * 0.75, ts[-1] * 14)
    ax.set_ylim(-0.3, 4.9)
    ax.set_yticks(range(5))
    rq = sorted({int(r["rQ"]) for r in tam["amtp"] if r.get("rQ")})
    ax.set_xlabel(f"Tampered files $t$ (of {rq[0]:,}–{rq[-1]:,} returned)", color=INK2, fontsize=11)
    ax.set_ylabel("Attack types detected in every run (of 4)", color=INK2, fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left", ncol=4)
    f.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "pdf"):
        f.savefig(os.path.join(OUT, f"e2_tamper_attack_types.{ext}"), facecolor=SURFACE, dpi=200)
    plt.close(f)
    INDEX.append(("e2_tamper_attack_types", f"{run} tamper_detection",
                  "attack types (modified, hidden, injected, old version) detected in every run; Chen has no "
                  "modified / old-version attack model"))
    print(f"-> {os.path.relpath(os.path.join(OUT, 'e2_tamper_attack_types.png'))}")


def exp2():
    run = find("p32_exp2")
    data = {s: rows(run, s, "exp2_selective_proof") for s in ORDER}
    layouts = sorted({r["layout"] for r in data["amtp"]}, key=list(LAYOUT_LS).index)
    for m in ("proof", "verify", "proof_kb", "server", "e2e"):
        for lay in layouts:                                    # one figure per layout, every scheme
            figure(f"e2_layout_{lay}_{m}", [scheme_series(s, metric_pts([r for r in data[s] if r["layout"] == lay],
                                                                        s, m, lambda r: int(r["rQ"])))
                                            for s in ORDER],
                   "Returned files $r_Q$", YLABEL[m], f"{run} exp2_selective_proof layout={lay}",
                   "Chen and Du have no separate proof generation" if m == "proof" else "", logx=True)
        ser = []                                               # AMTP: the three layouts on one figure
        for s in ("amtp", "secollab"):
            for lay in layouts:
                pts = metric_pts([r for r in data[s] if r["layout"] == lay], s, m, lambda r: int(r["rQ"]))
                ser.append(scheme_series(s, pts, f" ({lay.replace('_', ' ')})", LAYOUT_LS[lay]))
        figure(f"e2_layouts_{m}", ser, "Returned files $r_Q$", YLABEL[m], f"{run} exp2_selective_proof",
               "clustered = few partitions, dispersed = many, partition spread = one record per partition",
               logx=True)
    run = find("p32_ex2_verify1_tamper")
    v1 = {s: rows(run, s, "verify_single") for s in ORDER}
    for m in ("verify", "proof_kb", "e2e", "search", "server"):
        figure(f"e2_single_verify_{m}", [scheme_series(s, metric_pts(v1[s], s, m, lambda r: int(r["target_results"])))
                                         for s in ORDER],
               "Returned files $r_Q$ (target)", YLABEL[m], f"{run} verify_single",
               NOTE_SEARCH if m == "search" else "", logx=True)
    tam = {s: rows(run, s, "tamper_detection") for s in ORDER}
    for kind, title in KINDS.items():
        ser, ser_t = [], []
        for s in ORDER:
            rs = [r for r in tam[s] if r["tamper"] == kind]
            det = {}
            for r in rs:
                det.setdefault(int(r["tampered"]), []).append(100 * float(r["detected_runs"]) / max(1, float(r["runs"])))
            ser.append(scheme_series(s, {t: statistics.mean(v) for t, v in det.items()}))
            ser_t.append(scheme_series(s, median_by(rs, lambda r: int(r["tampered"]), "verify_total_ms")))
        figure(f"e2_tamper_{kind}_detection", ser, f"{title} $t$", "Detection rate (%)", f"{run} tamper_detection",
               "a scheme without this attack model has no line (Chen: modify / old version N/A)", logx=True,
               logy=False, pct=True)
        figure(f"e2_tamper_{kind}_verify", ser_t, f"{title} $t$", YLABEL["verify"], f"{run} tamper_detection",
               "time until the DU rejects", logx=True)
    attack_types(tam, run)
    for s in ORDER:                                            # false alarms: honest responses rejected
        honest = [r for r in tam[s] if r["tamper"] == "none"]
        if honest:
            POINTS.append({"figure": "e2_tamper_false_alarms", "series": NAME[s], "x": "honest",
                           "y": sum(float(r["detected_runs"]) for r in honest)})
    run = find("p32_x_search_verify")
    vm = {s: rows(run, s, "verify_multi") for s in PAIR}
    for m in ("verify", "proof_kb", "e2e", "search"):
        figure(f"e2_multi_verify_{m}", [scheme_series(s, metric_pts(vm[s], s, m, lambda r: int(r["target_results"])))
                                        for s in PAIR],
               "Returned files $r_Q$ (target, 4 domains)", YLABEL[m], f"{run} verify_multi",
               "SE-COLLAB only (multi domain)", logx=True)


# ---------------------------------------------------------------- Exp. 3
def exp3():
    run = find("p32_ex3")
    for sub, x, xlabel, tag in (("", "batch", "Requests per epoch $b$", "b"), ("update_n", "N", "Files in the domain $N$", "n")):
        a, c = rows(run, "amtp", "exp3_dynamic_update", sub), rows(run, "chen", "exp3_dynamic_update", sub)
        if not a:
            continue
        key = lambda r: int(r[x])  # noqa: E731
        xs = sorted({key(r) for r in a})
        logx, kfmt = (True, False) if tag == "b" else (False, True)
        src = f"{run}/{sub or '.'} exp3_dynamic_update"
        for col, ylabel, fid in (("update_ms", "Update time per epoch (ms)", "update"),
                                 ("per_doc_ms", "Update time per request (ms)", "per_request"),
                                 ("throughput_docs_s", "Throughput (requests / s)", "throughput")):
            ser = []
            for scheme, rs in (("amtp", a), ("chen", c)):
                for op in ("insert", "delete"):
                    ser.append(scheme_series(scheme, mean_by([r for r in rs if r["op"] == op], key, col),
                                             f" {op}", OP_LS[op]))
            figure(f"e3_{tag}_{fid}", ser, xlabel, ylabel, src,
                   "AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token "
                   "generation + CS apply, no update verification", logx=logx, xticks=xs, kfmt=kfmt)
        parts = (("protocol_ms", "protocol (no anchor)", "#2a78d6", "o"), ("server_ms", "CS prepare", "#eb6834", "s"),
                 ("validate_ms", "DO validation", "#1baf7a", "^"), ("abs_ms", "ABS sign + 2 verify", "#8f5bd6", "D"),
                 ("posting_repair_ms", "posting repair", "#e87ba4", "v"), ("auth_tree_ms", "auth-tree maintenance", "#7a7a7a", "P"),
                 ("anchor_ms", "anchor (local EVM)", "#c9a227", "X"))
        for op in ("insert", "delete"):
            rs = [r for r in a if r["op"] == op]
            figure(f"e3_{tag}_breakdown_{op}", [S(lbl, col_, mk, "-", mean_by(rs, key, col)) for col, lbl, col_, mk in parts],
                   xlabel, "Time per epoch (ms)", src,
                   "ABS is part of request / CS prepare / DO validation; posting repair + auth tree are inside CS prepare",
                   logx=logx, xticks=xs, kfmt=kfmt)


# ---------------------------------------------------------------- Exp. 4
def ex4_load():
    dirs = [OVR[k] for k in OVR if k.startswith("ex4")] or sorted(glob.glob(os.path.join(DATA, "ex4_*skew*")))
    upd, lay, qry, proto = [], [], [], []
    for d in dirs:
        for f in glob.glob(os.path.join(d, "*", "amtp", "splitmerge_*", "updates.csv")):
            upd += read(f)
            lay += read(f.replace("updates.csv", "layout.csv"))
            qry += read(f.replace("updates.csv", "queries.csv"))
        for f in glob.glob(os.path.join(d, "*", "amtp", "skewproto_*", "amtp_skew_protocol.csv")):
            proto += read(f)
    return upd, lay, qry, proto


def last_rows(rs):
    """rows of the last batch of every (variant, skew, seed)"""
    last = {}
    for r in rs:
        k = (r["variant"], r["skew"], r["seed"])
        last[k] = max(last.get(k, -1), int(r["batch"]))
    return [r for r in rs if int(r["batch"]) == last[(r["variant"], r["skew"], r["seed"])]]


def exp4():
    upd, lay, qry, proto = ex4_load()
    if not upd and not proto:
        print("   skip Exp. 4 (no data)")
        return
    allr = upd + proto
    skews = sorted({float(r["skew"]) for r in allr})
    sk = lambda r: float(r["skew"])  # noqa: E731
    src = "ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64"

    def by_var(rs, col, phase=None):
        return [S(v, V_STYLE[v][0], V_STYLE[v][1], V_STYLE[v][2],
                  mean_by([r for r in rs if r["variant"] == v and (phase is None or r["phase"] == phase)], sk, col))
                for v in VARIANTS]

    for phase, tag in (("insert", "insert"), ("hot_delete", "delete")):
        figure(f"e4_update_{tag}", by_var(allr, "update_ms", phase), "Skew level", "Update time per batch (ms)", src,
               "mean over every batch of the phase and the 10 runs; AMTP (full protocol) = signed requests, DO "
               "validation and anchor (local EVM) around the same index work", logy=True, xticks=skews)
    figure("e4_restructure", [s for s in by_var(allr, "restructure_ms") if s["label"].startswith("AMTP")],
           "Skew level", "Split / merge time per batch (ms)", src, "restructure_ms inside the commit", xticks=skews)
    sm = {}
    for r in last_rows([r for r in lay if r["variant"] == "AMTP"]):
        sm.setdefault(float(r["skew"]), []).append(float(r["splits"]) + float(r["merges"]))
    figure("e4_splits_merges", [S("AMTP", *V_STYLE["AMTP"][:3], {k: statistics.mean(v) for k, v in sm.items()})],
           "Skew level", "Splits + merges per run", src, "", logy=False, xticks=skews)
    lp = last_rows(lay) + last_rows(proto)
    figure("e4_max_partition", by_var(lp, "max_partition"), "Skew level", "Largest partition (records)", src,
           "after the last batch (insert + hot delete)", xticks=skews)
    lq = last_rows(qry)
    for col, ylabel, fid in (("server_ms", "Server time per query (ms)", "query_server"),
                             ("verify_ms", "DU verification time (ms)", "query_verify")):
        figure(f"e4_{fid}", by_var(lq, col)[:3], "Skew level", ylabel, src, "queries after the last batch", xticks=skews)
    figure("e4_proof_kb", [S(s["label"], s["color"], s["marker"], s["ls"], {k: v / KB for k, v in s["pts"].items()})
                           for s in by_var(lq, "proof_bytes")[:3]],
           "Skew level", "Proof size (KB)", src, "queries after the last batch", xticks=skews)
    for sk_ in skews:                                    # every batch of the run, index level only (owner)
        series = []
        for v in VARIANTS[:3]:
            rs = [r for r in upd if r["variant"] == v and float(r["skew"]) == sk_]
            series.append(S(v, *V_STYLE[v][:3], mean_by(rs, lambda r: int(r["batch"]), "update_ms", 1 / 1000)))
        for s in series:
            s["marker"] = None
        dels = [int(r["batch"]) for r in upd if float(r["skew"]) == sk_ and r["phase"] == "hot_delete"]
        figure(f"e4_batches_skew{sk_:g}", series, "Update batch ($b = 100$ operations)", "Update time per batch (s)",
               src, f"skew {sk_:g}: mean over the 10 runs at every batch (insert batches, then hot delete); index level",
               vline=(min(dels), "deletions start") if dels else None)


# ---------------------------------------------------------------- Exp. 5
def exp5(with_du):
    run = find("p32_ex5")
    a = rows(run, "amtp", "exp5_domains")
    se = rows(run, "secollab", "exp5_domains")
    du = read(os.path.join(run, "du", "exp5_clouds", "du_clouds_sensitivity.csv")) if run and with_du else []
    q = {"amtp": [r for r in a if r["op"] == "query"], "secollab": [r for r in se if r["op"] == "query"]}
    d = lambda r: int(r["domains"])  # noqa: E731
    ds = sorted({d(r) for r in q["amtp"]}) or None
    for m in ("search", "proof", "verify", "e2e", "query_gen", "server"):
        ser = [scheme_series(s, metric_pts(q[s], s, m, d)) for s in PAIR]
        note = "queried domain fixed at 5,000 records"
        if with_du and m in ("search", "verify", "e2e", "query_gen", "server"):
            ser.append(scheme_series("du", metric_pts(du, "du", m, lambda r: int(r["n_clouds"])), " (n_c clouds)"))
            note += "; Du: x = number of clouds n_c (Du has no domains), its own AND queries at N = 5,000"
        figure(f"e5_query_{m}", ser, "Number of domains $D$", YLABEL[m], f"{run} exp5_domains", note,
               logx=True, xticks=ds)
    u = [r for r in a if r["op"] == "update_one_domain"]
    for col, ylabel, fid, logy in (("update_ms", "Update time of one domain (ms)", "isolation_update", True),
                                   ("protocol_ms", "Update time without anchor (ms)", "isolation_protocol", True),
                                   ("anchor_ms", "Root maintenance time (ms)", "root_anchor_ms", True),
                                   ("anchor_gas", "Gas per root update (local EVM)", "root_gas_localevm", False)):
        figure(f"e5_{fid}", [scheme_series("amtp", mean_by([r for r in u if r["update_kind"] == k], d, col),
                                           f" {k}", OP_LS[k]) for k in ("insert", "delete")],
               "Number of domains $D$", ylabel, f"{run} exp5_domains op=update_one_domain",
               "one epoch on the target domain; every other Domain Root unchanged (checked); RootAnchor on a local EVM"
               + ("; NOT for the paper: py-evm's gas schedule differs from Ethereum (same transaction: 64.1k local vs "
                  "86.7k on Sepolia at D = 1); use e5_sepolia_gas" if col == "anchor_gas" else ""),
               logx=True, logy=logy, xticks=ds)
    gas = read(os.path.join(REPO, "chain", "runs", "gas_domains_20261119_005048.csv"))
    if gas:
        x = lambda r: int(r["D"])  # noqa: E731
        xs = [d for d in (1, 2, 4, 8, 16, 32) if any(x(r) == d for r in gas)]
        figure("e5_sepolia_gas", [scheme_series("amtp", mean_by(gas, x, "submit_gas"), " (Sepolia)")],
               "Number of domains $D$", "Gas per root update", "chain/runs/gas_domains_20261119_005048.csv",
               "Ethereum Sepolia, one submit per D", logx=True, logy=False, xticks=xs)
        figure("e5_sepolia_time", [scheme_series("amtp", mean_by(gas, x, "submit_s", 1000), " (Sepolia)")],
               "Number of domains $D$", "Anchoring latency (ms)", "chain/runs/gas_domains_20261119_005048.csv",
               "time until the transaction is mined", logx=True, logy=False, xticks=xs)


def write_index():
    with open(os.path.join(OUT, "figure_points.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["figure", "series", "x", "y", "q1", "q3"])
        w.writeheader()
        w.writerows(POINTS)
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Paper (32) figures (baselines/plot_p32.py)\n\nEvery timing = mean of 10 runs after 3 warm-up runs (#46). "
                "Query-level points (Exp. 1, 2, 5 queries, tamper verification) = median over the queries of that x, "
                "error bars = interquartile range (#66); Exp. 3, Exp. 4, update isolation and Sepolia = mean over "
                "runs / batches / updates, no bars. Numbers (and q1 / q3) in figure_points.csv.\n\n| figure | data | note |\n|---|---|---|\n")
        for fid, src, note in INDEX:
            f.write(f"| {fid} | {src.replace(DATA, '<data>').replace(REPO + os.sep, '')} | {note} |\n")
    print(f"-> {os.path.relpath(OUT)}/figure_points.csv, README.md ({len(INDEX)} figures)")


def main():
    global DATA, OUT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(HERE, "results", "runs", "cloud"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "paper32", "figures"))
    ap.add_argument("--run", action="append", default=[], help="NAME=DIR: take run NAME from DIR")
    ap.add_argument("--with-du", action="store_true", help="Exp. 5: add Du's multi-cloud points (n_c = D)")
    ap.add_argument("--only", nargs="+", choices=["exp1", "exp2", "exp3", "exp4", "exp5"])
    a = ap.parse_args()
    DATA, OUT = os.path.abspath(a.data), os.path.abspath(a.out)
    for item in a.run:
        k, v = item.split("=", 1)
        OVR[k] = os.path.abspath(v)
    todo = a.only or ["exp1", "exp2", "exp3", "exp4", "exp5"]
    for name in todo:
        print(f"[{name}]")
        exp5(a.with_du) if name == "exp5" else globals()[name]()
    os.makedirs(OUT, exist_ok=True)
    write_index()


if __name__ == "__main__":
    main()
