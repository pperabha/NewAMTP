"""
plot_results.py
============================================================================
วาดกราฟจากผลของ baseline (results/<scheme>/<scheme>_<suite>.csv) สไตล์เดียวกับกราฟของ Chen [40]
และชุดสีเดียวกับ the original AMTP plot palette -> ทุก scheme ดูเป็นงานเดียวกัน
ทุกจุด = median ของ --reps รอบ, error bar = ±1 std  (คอลัมน์ _ms_median / _ms_std)
Exp. 3 (update) and Exp. 4 (AMTP ablation, results/amtp/exp4*/ from bench.ablation) are drawn too.
Exp. 1 / Exp. 5 have several queries per (N, k_Q, shape) (results/exp1_queries.json): each point is the median over
those queries of their per-query medians, and the error bar spans the fastest to the slowest query (min–max).

วิธีรัน (pip install matplotlib):
  python3 plot_results.py secollab            # กราฟของ SE-COLLAB
  python3 plot_results.py chen du secollab    # หลาย scheme + กราฟเทียบกัน (compare_*)
ไฟล์ออกที่ results/<scheme>/figures/<scheme>_<ชื่อกราฟ>.png และ .pdf (PNG ใส่สไลด์, PDF ใส่ paper)
กราฟเทียบหลาย scheme (compare_*) ออกที่ results/compare/
============================================================================
"""

import argparse                                   # อ่าน argument จาก command line
import csv                                        # อ่านไฟล์ผล
import glob                                       # Exp. 4 result folders
import os                                         # จัดการ path
import statistics                                 # median / std across queries

import matplotlib                                 # วาดกราฟ

matplotlib.use("Agg")                             # วาดลงไฟล์ ไม่ต้องเปิดหน้าต่าง
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))  # โฟลเดอร์ baselines/

# ---- สีและ marker (ชุดเดียวกับ the original AMTP plot palette + สีที่ 5 ของกราฟ Chen) ----
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]  # น้ำเงิน ส้ม เขียว เหลือง ชมพู
MARKERS = ["o", "s", "^", "D", "v"]
SURFACE, INK, INK2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8985"

NAME = {"amtp": "AMTP", "chen": "Chen [40]", "du": "Du [7]", "secollab": "SE-COLLAB [37]"}  # ชื่อในหัวกราฟ
AND_SHAPES = ("single", "conjunctive")            # รูปแบบที่ทุก scheme รองรับ
SHAPE_LABEL = {"conjunctive": "A ∧ B ∧ …", "disjunctive": "A ∨ B ∨ …",
               "or_and_or": "(A ∨ B) ∧ (C ∨ D)", "and_or_and": "(A ∧ B) ∨ (C ∧ D)"}
# ส่วนประกอบของเวลา end-to-end (คอลัมน์, ชื่อใน legend) — ใช้ใน breakdown
PARTS = {
    "amtp": [("query_gen", "Trapdoor (DU)"), ("server_total", "Search + ASPA proof (CS)"),
             ("verify_total", "Verification, 7 checks (DU)")],
    "chen": [("query_gen", "Query generation (DU)"), ("server_total", "Server search (CS)"),
             ("du_decrypt", "Decrypt + AND (DU)"), ("verify_total", "Verification (DU)")],
    "du": [("query_gen", "Query generation (DU)"), ("server_total", "Server search (slowest cloud)"),
           ("verify_total", "Verification (DU)"), ("du_decrypt", "RS decode + decrypt (DU)")],
    "secollab": [("query_gen", "Query generation (DU)"), ("server_total", "Proxy search + proof (CS)"),
                 ("verify_total", "Verification (DU)")],
}


# ============================================================================
# 1) อ่านข้อมูล
# ============================================================================

DATASET = "dataset-v4 (arXiv)"    # caption label; --dataset overrides it

def load(scheme, suite, folder):
    """อ่าน results/<scheme>/<scheme>_<suite>.csv  (ไม่มีไฟล์ -> None)"""
    path = os.path.join(folder, scheme, f"{scheme}_{suite}.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)]


def ok(rows):
    """เฉพาะแถวที่วัดจริง (ตัดแถว N/A)"""
    return [r for r in rows if r.get("status", "ok") == "ok"]


# group keys of one plotted point: the query itself (terms, source_doc, domain, rQ, ...) is not a key
POINT_KEYS = ("N", "N_target", "domains", "n_clouds", "kQ", "shape", "op", "status")


def over_queries(rows):
    """Collapse the queries of one (N, k_Q, shape, ...) point into one row.
    <metric>_ms_median = median of the per-query medians; every numeric column c also gets c_qlo / c_qhi = its
    smallest / largest value across the queries (error bars, empty-result check); other numeric columns
    (rQ, pQ, response_bytes, ...) = median across queries."""
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r.get(k) for k in POINT_KEYS), []).append(r)
    out = []
    for g in groups.values():
        row = dict(g[0], n_queries=len(g))
        if len(g) > 1:
            for c in g[0]:
                try:
                    xs = [float(r[c]) for r in g]
                except (TypeError, ValueError):   # text column or empty (N/A rows)
                    continue
                if c in POINT_KEYS or c.endswith("_ms_std"):
                    continue
                row[c + "_qlo"], row[c + "_qhi"] = min(xs), max(xs)
                if c.endswith("_ms_median"):
                    row[c] = statistics.median(xs)
                else:
                    m = statistics.median(xs)
                    row[c] = int(m) if m == int(m) else round(m, 1)
        out.append(row)
    return out


def val(r, metric):
    """(median, error) of a timing in ms: error = (down, up) to the fastest / slowest query when the point has
    several queries, else ±1 std over the runs of its single query"""
    m = float(r[f"{metric}_ms_median"])
    lo, hi = r.get(f"{metric}_ms_median_qlo"), r.get(f"{metric}_ms_median_qhi")
    if lo is not None:
        return m, (m - lo, hi - m)
    return m, float(r[f"{metric}_ms_std"])


def is_empty(r):
    """True when no query of this point returned a file"""
    return float(r.get("rQ_qhi", r.get("rQ") or 0)) == 0


# ============================================================================
# 2) สไตล์กราฟ (เหมือนกราฟ Chen)
# ============================================================================
def new_fig(width=7.0, height=4.2):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    fig.patch.set_facecolor(SURFACE)              # พื้นหลังทั้งภาพ
    ax.set_facecolor(SURFACE)                     # พื้นหลังกราฟ
    for side in ("top", "right"):                 # ไม่มีกรอบบน/ขวา
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=10)
    ax.grid(True, color=GRID, linewidth=0.8)      # เส้น grid จาง ๆ
    ax.set_axisbelow(True)
    return fig, ax


def finish(fig, ax, title, xlabel, ylabel, note, path, legend_title=None, legend_out=True):
    """ใส่หัวกราฟ / ชื่อแกน / legend / หมายเหตุท้ายภาพ แล้วบันทึกเป็น PNG + PDF"""
    ax.set_title(title, loc="left", fontsize=12.5, color=INK, fontweight="bold")
    ax.set_xlabel(xlabel, color=INK2, fontsize=11)
    ax.set_ylabel(ylabel, color=INK2, fontsize=11)
    if ax.get_legend_handles_labels()[0]:
        kw = dict(loc="upper left", bbox_to_anchor=(1.02, 1.0)) if legend_out else dict(loc="upper left")
        ax.legend(frameon=False, fontsize=10, title=legend_title, title_fontsize=10, **kw)
    fig.text(0.01, 0.015, note, color=AXIS, fontsize=7.5 if len(note) < 110 else 6.8)  # หมายเหตุท้ายภาพ
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(f"{path}.{ext}", facecolor=SURFACE)
    plt.close(fig)
    print(f"-> {os.path.relpath(path)}.png / .pdf")


def line(ax, xs, ys, es, i, label, dashed=False):
    """เส้น + marker ขอบขาว + error bar: ±e, or (down, up) per point"""
    if any(isinstance(e, tuple) for e in es):     # asymmetric (min–max across queries)
        es = [[e[0] if isinstance(e, tuple) else e for e in es], [e[1] if isinstance(e, tuple) else e for e in es]]
    ax.errorbar(xs, ys, yerr=es, color=COLORS[i % 5], marker=MARKERS[i % 5], markersize=7,
                markeredgecolor="white", markeredgewidth=1.2, linewidth=2.6, capsize=0,
                linestyle="--" if dashed else "-", label=label)


def n_axis(ax, ns):
    """แกน N แบบ log พร้อม label 10k / 50k / ..."""
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(ns))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k"))
    ax.xaxis.set_minor_formatter(NullFormatter())


# ============================================================================
# 3) กราฟของแต่ละ scheme
# ============================================================================
def exp1_search_vs_n(scheme, rows, out, note):
    """end-to-end ของ query แบบ AND เทียบกับ N แยกเส้นตาม k_Q (เหมือนกราฟ Chen)"""
    rows = [r for r in ok(rows) if r["shape"] in AND_SHAPES]
    fig, ax = new_fig()
    ns = sorted({int(r["N"]) for r in rows})
    for i, k in enumerate(sorted({int(r["kQ"]) for r in rows})):
        krows = [r for r in rows if int(r["kQ"]) == k]
        pts = sorted((int(r["N"]), *val(r, "end_to_end")) for r in krows)
        empty = " (empty result)" if all(is_empty(r) for r in krows) else ""
        line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i, f"$k_Q$ = {k}{empty}",
             dashed=bool(empty))
    n_axis(ax, ns)
    ax.set_ylim(bottom=0)
    finish(fig, ax, f"Exp. 1 · {NAME[scheme]}: AND search time vs N", "Database size N (documents)",
           "End-to-end search time (ms)", note, os.path.join(out, f"{scheme}_exp1_search_vs_N"),
           legend_title="AND query")


def exp1_shapes_vs_n(scheme, rows, out, note, kq=4):
    """end-to-end เทียบกับ N แยกเส้นตามรูปแบบ Boolean ที่ k_Q คงที่ (scheme ที่รองรับ OR / nested)"""
    rows = [r for r in ok(rows) if int(r["kQ"]) == kq]
    shapes = [s for s in SHAPE_LABEL if any(r["shape"] == s for r in rows)]
    if len(shapes) < 2:                           # รองรับแค่ AND -> ไม่มีอะไรให้เทียบ
        return
    fig, ax = new_fig()
    for i, s in enumerate(shapes):
        pts = sorted((int(r["N"]), *val(r, "end_to_end")) for r in rows if r["shape"] == s)
        line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i, SHAPE_LABEL[s])
    n_axis(ax, sorted({int(r["N"]) for r in rows}))
    ax.set_ylim(bottom=0)
    finish(fig, ax, f"Exp. 1 · {NAME[scheme]}: Boolean shapes vs N ($k_Q$ = {kq})",
           "Database size N (documents)", "End-to-end search time (ms)", note,
           os.path.join(out, f"{scheme}_exp1_shapes_vs_N"), legend_title="Query shape")


def exp1_breakdown(scheme, rows, out, note):
    """แท่งซ้อน: เวลาแต่ละขั้นที่ N สูงสุด แยกตาม k_Q (query แบบ AND)"""
    rows = [r for r in ok(rows) if r["shape"] in AND_SHAPES]
    n = max(int(r["N"]) for r in rows)
    rows = sorted((r for r in rows if int(r["N"]) == n), key=lambda r: int(r["kQ"]))
    fig, ax = new_fig()
    xs = range(len(rows))
    bottom = [0.0] * len(rows)
    for i, (col, label) in enumerate(PARTS[scheme]):
        h = [val(r, col)[0] for r in rows]
        ax.bar(xs, h, 0.6, bottom=bottom, color=COLORS[i], edgecolor="white", linewidth=1.2, label=label)
        bottom = [b + v for b, v in zip(bottom, h)]
    top = max(bottom)
    for x, b in zip(xs, bottom):                  # ตัวเลขรวมบนแท่ง
        ax.text(x, b + top * 0.01, f"{b:.2f}", ha="center", va="bottom", color=INK2, fontsize=10)
    ax.set_xticks(list(xs), [f"$k_Q$ = {r['kQ']}\n$r_Q$ = {r['rQ']}" for r in rows])
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, top * 1.08)
    finish(fig, ax, f"Exp. 1 · {NAME[scheme]}: cost breakdown at N = {n:,}", "", "Time (ms, median)",
           note, os.path.join(out, f"{scheme}_exp1_breakdown_maxN"))


def exp2_verify_vs_rq(scheme, rows, out, note):
    """เวลา verify ของ DU เทียบกับ r_Q (log-log) แยก clustered / dispersed (+ proof_mode ถ้ามี)"""
    rows = ok(rows)
    n = int(rows[0]["N"])
    keys = sorted({(r["layout"], r.get("proof_mode") or "") for r in rows},
                  key=lambda k: (k[1] != "paths", k[1], k[0]))
    fig, ax = new_fig()
    for i, (layout, mode) in enumerate(keys):
        pts = sorted((int(r["rQ"]), *val(r, "verify_total")) for r in rows
                     if r["layout"] == layout and (r.get("proof_mode") or "") == mode)
        label = layout + (f" · {'multiproof' if mode == 'multi' else 'per-path (paper)'}" if mode else "")
        line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i, label,
             dashed=layout == "dispersed")
    ax.set_xscale("log")
    ax.set_yscale("log")
    finish(fig, ax, f"Exp. 2 · {NAME[scheme]}: verification vs $r_Q$ (N = {n:,})", "Number of results $r_Q$",
           "User verification time (ms)", note, os.path.join(out, f"{scheme}_exp2_verify_vs_rQ"), legend_out=False)


def clouds_axis(ax, cs):
    """แกนจำนวน cloud แบบ log2 พร้อม label 4 / 8 / 16 / 32"""
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(FixedLocator(cs))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())


def exp5_cost_vs_clouds(scheme, rows, out, note, kq=4):
    """Exp.5: ที่ N และ k_Q คงที่ เวลาแต่ละส่วนเทียบกับจำนวน cloud (แกน y แบบ log เพราะแต่ละเส้นห่างกันหลายเท่า)
    end-to-end = latency ที่ผู้ใช้รอ (cloud ค้นขนานกัน), server_sum = งานรวมของทุก cloud, verify = งานของ DU"""
    rows = sorted((r for r in ok(rows) if int(r["kQ"]) == kq), key=lambda r: int(r["n_clouds"]))
    if not rows:
        return
    n = int(rows[0]["N"])
    cs = [int(r["n_clouds"]) for r in rows]
    fig, ax = new_fig()
    series = [("end_to_end", "End-to-end latency (clouds in parallel)"),
              ("server_sum", "Total work of all clouds"), ("verify_total", "Verification (DU)")]
    for i, (col, label) in enumerate(series):
        if f"{col}_ms_median" not in rows[0]:
            continue
        ys, es = zip(*(val(r, col) for r in rows))
        line(ax, cs, ys, es, i, label)
    clouds_axis(ax, cs)
    ax.set_yscale("log")
    finish(fig, ax, f"Du-only sensitivity · {NAME[scheme]}: cost vs number of clouds (N = {n:,}, $k_Q$ = {kq})",
           "Number of clouds $n_c$", "Time (ms, median, log)", note,
           os.path.join(out, f"{scheme}_clouds_cost"))


def exp5_verify_vs_clouds(scheme, rows, out, note):
    """Exp.5: เวลา verify ของ DU เทียบกับจำนวน cloud แยกเส้นตาม k_Q (O(n_c·|R|) ตาม Table IV)"""
    rows = ok(rows)
    if not rows:
        return
    n = int(rows[0]["N"])
    fig, ax = new_fig()
    cs = sorted({int(r["n_clouds"]) for r in rows})
    for i, k in enumerate(sorted({int(r["kQ"]) for r in rows})):
        pts = sorted((int(r["n_clouds"]), *val(r, "verify_total"), r["rQ"]) for r in rows if int(r["kQ"]) == k)
        line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i,
             f"$k_Q$ = {k} ($r_Q$ = {pts[0][3]})")
    clouds_axis(ax, cs)
    ax.set_ylim(bottom=0)
    finish(fig, ax, f"Du-only sensitivity · {NAME[scheme]}: verification vs number of clouds (N = {n:,})",
           "Number of clouds $n_c$", "User verification time (ms)", note,
           os.path.join(out, f"{scheme}_clouds_verify"), legend_title="AND query")


def exp5_domains(scheme, rows, out, note):
    """Exp.5 (AMTP, SE-COLLAB): query ของ domain เป้าหมาย และการ update domain เดียว เทียบกับจำนวน domain D"""
    rows = ok(rows)
    q = [r for r in rows if r.get("op") == "query" and str(r.get("kQ")) == "4"]   # k_Q = 4 as before
    u = sorted((r for r in rows if r.get("op") == "update_one_domain"), key=lambda r: int(r["domains"]))
    if not q:
        return
    n = int(q[0]["N_target"])
    ds = sorted({int(r["domains"]) for r in q})
    fig, ax = new_fig()
    for i, s in enumerate(x for x in SHAPE_LABEL if any(r["shape"] == x for r in q)):
        pts = sorted((int(r["domains"]), *val(r, "end_to_end")) for r in q if r["shape"] == s)
        line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i, SHAPE_LABEL[s])
    clouds_axis(ax, ds)
    ax.set_ylim(bottom=0)
    finish(fig, ax, f"Exp. 5 · {NAME[scheme]}: query vs number of domains ($k_Q$ = {q[0]['kQ']})",
           f"Number of domains D ({n:,} documents per domain)", "End-to-end search time (ms)", note,
           os.path.join(out, f"{scheme}_exp5_query_vs_domains"), legend_title="Query shape")
    if u:
        fig, ax = new_fig()
        for i, (col, label) in enumerate([("domain_update", "Update target domain (R_D)"),
                                          ("anchor_update", "Signature + anchor + Global Root")]):
            ys, es = zip(*(val(r, col) for r in u))
            line(ax, [int(r["domains"]) for r in u], ys, es, i, label)
        clouds_axis(ax, ds)
        ax.set_yscale("log")
        finish(fig, ax, f"Exp. 5 · {NAME[scheme]}: updating one domain vs number of domains",
               "Number of domains D", "Time (ms, median, log)", note,
               os.path.join(out, f"{scheme}_exp5_update_vs_domains"))


# ============================================================================
# 4) อื่น ๆ ของแต่ละ scheme (Exp. 1 p_Q, Exp. 3, Exp. 4)
# ============================================================================
def exp1_time_vs_pq(scheme, raw, out, note):
    """one point per query: end-to-end time vs pQ (postings the proof opens), one colour per N"""
    raw = [r for r in ok(raw) if r.get("pQ") not in (None, "") and float(r["pQ"]) > 0]
    if not raw:
        return
    fig, ax = new_fig()
    for i, n in enumerate(sorted({int(r["N"]) for r in raw})):
        pts = [(float(r["pQ"]), float(r["end_to_end_ms_median"])) for r in raw if int(r["N"]) == n]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=16, color=COLORS[i % 5], marker=MARKERS[i % 5],
                   alpha=0.75, edgecolors="white", linewidths=0.4, label=f"N = {n:,}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    finish(fig, ax, f"Exp. 1 · {NAME[scheme]}: search time vs postings opened ($p_Q$)", "$p_Q$ (postings, log)",
           "End-to-end search time (ms, log)", note, os.path.join(out, f"{scheme}_exp1_time_vs_pQ"),
           legend_title="Database size")


def plain_log_labels(ax):
    """Label a short log y axis with plain numbers (3, 10, 20) instead of 3×10⁰"""
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: f"{v:g}" if f"{v:e}"[0] in "25" else ""))


def exp3_rows(rows, op="insert"):
    """Exp. 3 rows of one operation, with the time per file added (ms)"""
    out = []
    for r in ok(rows):
        if r["op"] == op:
            b = int(r["batch"])
            out.append(dict(r, per_file=float(r["update_ms_median"]) / b, per_file_std=float(r["update_ms_std"]) / b))
    return out


def exp3_update_vs_batch(scheme, rows, out, note):
    """Exp. 3: insert time per file vs batch size, one line per N (log-log)"""
    rows = exp3_rows(rows)
    if not rows:
        return
    fig, ax = new_fig()
    for i, n in enumerate(sorted({int(r["N"]) for r in rows})):
        pts = sorted((int(r["batch"]), r["per_file"], r["per_file_std"]) for r in rows if int(r["N"]) == n)
        line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i, f"N = {n:,}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    plain_log_labels(ax)
    finish(fig, ax, f"Exp. 3 · {NAME[scheme]}: insert time per file vs batch size", "Batch size (files)",
           "Time per file (ms, log)", note, os.path.join(out, f"{scheme}_exp3_insert_vs_batch"),
           legend_title="Database size")


EXP4_VARIANTS = ["AMTP", "Static-MT", "Global-MT", "Global-MT(v)"]


def exp4_ablation(folder, out, note, compare_out=None):
    """Exp. 4 (bench.ablation output folder): update cost per batch and User verification vs skew, per variant.
    Each point = median over all batches (or queries) and runs, error bar = std over them."""
    def read(name):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    updates, queries = read("updates.csv"), read("queries.csv")
    if not updates:
        return
    tag = os.path.basename(os.path.normpath(folder))           # e.g. exp4 or exp4_n20k
    args = {}
    if os.path.exists(os.path.join(folder, "manifest.json")):
        import json
        with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
            args = json.load(f).get("args", {})
    setup = (f"N = {args['n']:,}, batch {args['batch_size']}, θ = {args['theta_max']}/{args['theta_min']}, "
             f"{args['runs']} run(s)") if args else ""
    variants = [v for v in EXP4_VARIANTS if any(r["variant"] == v for r in updates)]
    for rows, col, ylabel, title, name in (
            (updates, "update_ms", "Update time per batch (ms, log)", "update cost vs skew", "update_vs_skew"),
            (queries, "verify_ms", "User verification time (ms)", "User verification vs skew", "verify_vs_skew")):
        if not rows:
            continue
        fig, ax = new_fig()
        for i, v in enumerate(variants):
            pts = []
            for k in sorted({float(r["skew"]) for r in rows if r["variant"] == v}):
                xs = [float(r[col]) for r in rows if r["variant"] == v and float(r["skew"]) == k]
                pts.append((k, statistics.median(xs), statistics.pstdev(xs)))
            line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], i, v,
                 dashed=v.startswith("Global"))
        if col == "update_ms":
            ax.set_yscale("log")
        else:
            ax.set_ylim(bottom=0)
        ax.set_xticks(sorted({float(r["skew"]) for r in rows}))
        finish(fig, ax, f"Exp. 4 · AMTP ablation: {title}", "Skew (share of new files in one hot group)", ylabel,
               f"{DATASET} · {setup + ' · ' if setup else ''}median, ±1 std over batches · {note}",
               os.path.join(out, f"amtp_{tag}_{name}"), legend_title="Variant")
        if compare_out:                                # every variant in the combined style
            fig, ax = paper_fig()
            for v in variants[1:] + variants[:1]:     # AMTP drawn last, on top of Static-MT
                pts = []
                for k in sorted({float(r["skew"]) for r in rows if r["variant"] == v}):
                    xs = [float(r[col]) for r in rows if r["variant"] == v and float(r["skew"]) == k]
                    pts.append((k, statistics.median(xs), statistics.pstdev(xs)))
                color, marker, ls = EXP4_STYLE[v]
                paper_line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], color, marker, v, ls)
            ax.set_yscale("log")
            plain_log_labels(ax)
            ax.set_xticks(sorted({float(r["skew"]) for r in rows}))
            paper_finish(fig, ax, "a" if col == "update_ms" else "b", f"Exp. 4: {title}",
                         "Skew (share of new files in one hot group)", ylabel.replace(", log", ""),
                         f"{DATASET} · {setup + ' · ' if setup else ''}median, ±1 std over batches · "
                         f"Exp. 4 compares AMTP with its own ablations (no baseline has partitions) · {note}",
                         os.path.join(compare_out, f"compare_{tag}_{name}"))


# ============================================================================
# 5) Combined figures: every scheme of an experiment in one graph (results/compare/)
#    One fixed colour + marker per scheme in every figure; a variant of a scheme (SE-COLLAB multiproof,
#    deletes, AMTP's anchor share) is the same colour, dashed, marker x. Panels are lettered per experiment.
# ============================================================================
STYLE = {"amtp": ("#2a78d6", "o"), "chen": ("#eb6834", "s"), "du": ("#1baf7a", "^"),
         "secollab": ("#eda100", "D")}
EXP4_STYLE = {"AMTP": ("#2a78d6", "o", "-"), "Static-MT": ("#e87ba4", "v", ":"),
              "Global-MT": ("#52514e", "s", "-"), "Global-MT(v)": ("#52514e", "x", "--")}
KB = 1000                                         # 1 KB = 1000 B in every figure and table


def paper_line(ax, xs, ys, es, color, marker, label, ls="-"):
    """line + marker + error bar with caps; es = ±e or (down, up) per point"""
    if any(isinstance(e, tuple) for e in es):
        es = [[e[0] if isinstance(e, tuple) else e for e in es], [e[1] if isinstance(e, tuple) else e for e in es]]
    ax.errorbar(xs, ys, yerr=es, color=color, marker=marker, markersize=7, markeredgecolor="white" if marker != "x"
                else color, markeredgewidth=1.2 if marker != "x" else 1.8, linewidth=2.2, capsize=3, capthick=1.2,
                elinewidth=1.2, linestyle=ls, label=label)


def scheme_line(ax, scheme, pts, label=None, variant=False, ls=None):
    """pts = [(x, y, err)] for one scheme; variant -> dashed, marker x"""
    if not pts:
        return False
    color, marker = STYLE[scheme]
    pts = sorted(pts, key=lambda p: p[0])
    paper_line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], color,
               "x" if variant else marker, label or NAME[scheme], ls or ("--" if variant else "-"))
    return True


def paper_fig():
    fig, ax = new_fig(6.4, 4.6)
    ax.tick_params(labelsize=11)
    return fig, ax


def paper_finish(fig, ax, letter, title, xlabel, ylabel, note, path, ncol=2):
    """(letter) title, two-column legend inside the top of the plot, headroom so it covers no data"""
    ax.set_title(f"({letter}) {title}", fontsize=13, color=INK)
    ax.set_xlabel(xlabel, color=INK2, fontsize=12)
    ax.set_ylabel(ylabel, color=INK2, fontsize=12)
    handles = ax.get_legend_handles_labels()[0]
    lo, hi = ax.get_ylim()
    rows = -(-len(handles) // ncol)
    if ax.get_yscale() == "log":
        ax.set_ylim(lo, hi * (hi / lo) ** (0.12 * rows + 0.05))
    else:
        ax.set_ylim(lo, hi + (hi - lo) * (0.12 * rows + 0.05))
    if handles:
        ax.legend(loc="upper center", ncol=ncol, frameon=False, fontsize=9.5, handlelength=2.6, columnspacing=1.2)
    fig.text(0.01, 0.012, note, color=AXIS, fontsize=6.6, wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(f"{path}.{ext}", facecolor=SURFACE)
    plt.close(fig)
    print(f"-> {os.path.relpath(path)}.png / .pdf")


def by(rows, **kw):
    return [r for r in ok(rows) if all(str(r.get(k)) == str(v) for k, v in kw.items())]


def size_err(rows, col="response_bytes"):
    """(x-less) points of a byte column in KB with min–max across queries"""
    out = []
    for r in rows:
        y = float(r[col]) / KB
        out.append((y, (y - float(r.get(col + "_qlo", r[col])) / KB, float(r.get(col + "_qhi", r[col])) / KB - y)))
    return out


def figs_exp1(data, out, note, kq=4):
    """(a) AND end-to-end vs N, all schemes; (b) OR / nested vs N (schemes that support them);
    (c) bytes returned per AND query vs N"""
    fig, ax = paper_fig()
    ns = set()
    for s, rows in data.items():
        pts = [(int(r["N"]), *val(r, "end_to_end")) for r in ok(rows) if r["shape"] in AND_SHAPES and int(r["kQ"]) == kq]
        ns |= {p[0] for p in pts}
        scheme_line(ax, s, pts)
    n_axis(ax, sorted(ns))
    ax.set_yscale("log")
    paper_finish(fig, ax, "a", f"Exp. 1: AND search time vs N ($k_Q$ = {kq})", "Database size N (documents)",
                 "End-to-end search time (ms)", note, os.path.join(out, "compare_exp1_and_vs_N"))
    fig, ax = paper_fig()
    lss = {"disjunctive": "-", "or_and_or": "--", "and_or_and": ":"}
    na = []
    for s, rows in data.items():
        drawn = False
        for sh, ls in lss.items():
            pts = [(int(r["N"]), *val(r, "end_to_end")) for r in by(rows, kQ=kq, shape=sh)]
            if scheme_line(ax, s, pts, f"{NAME[s]}: {SHAPE_LABEL[sh]}", ls=ls):
                drawn = True
        if not drawn:
            na.append(NAME[s])
    n_axis(ax, sorted(ns))
    ax.set_yscale("log")
    paper_finish(fig, ax, "b", f"Exp. 1: OR / nested search time vs N ($k_Q$ = {kq})", "Database size N (documents)",
                 "End-to-end search time (ms)", note + (f" · not supported (N/A): {', '.join(na)}" if na else ""),
                 os.path.join(out, "compare_exp1_or_vs_N"))
    fig, ax = paper_fig()
    for s, rows in data.items():
        rows = [r for r in ok(rows) if r["shape"] in AND_SHAPES and int(r["kQ"]) == kq and r.get("response_bytes")]
        scheme_line(ax, s, [(int(r["N"]), *ye) for r, ye in zip(rows, size_err(rows))])
    n_axis(ax, sorted(ns))
    ax.set_yscale("log")
    paper_finish(fig, ax, "c", f"Exp. 1: data returned per AND query ($k_Q$ = {kq})", "Database size N (documents)",
                 "Response size (KB, 1 KB = 1000 B)", note.replace("fastest–slowest query", "smallest–largest response"),
                 os.path.join(out, "compare_exp1_response_vs_N"))


def fig_exp1_pq(raw, out, note):
    """(d) AMTP: one point per query, end-to-end time vs pQ (postings the proof opens), one colour per N"""
    raw = [r for r in ok(raw) if r.get("pQ") not in (None, "") and float(r["pQ"]) > 0]
    if not raw:
        return
    fig, ax = paper_fig()
    for i, n in enumerate(sorted({int(r["N"]) for r in raw})):
        pts = [(float(r["pQ"]), float(r["end_to_end_ms_median"])) for r in raw if int(r["N"]) == n]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=16, color=COLORS[i % 5], marker=MARKERS[i % 5],
                   alpha=0.75, edgecolors="white", linewidths=0.4, label=f"N = {n:,}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    paper_finish(fig, ax, "d", "Exp. 1: AMTP search time vs postings opened ($p_Q$)", "$p_Q$ (postings opened by the proof)",
                 "End-to-end search time (ms)", note, os.path.join(out, "compare_exp1_time_vs_pQ"))


EXP2_LAYOUT = {"clustered": "clustered", "dispersed": "dispersed",
               "partition_spread": "one file per AMTP partition (AMTP worst case)"}


def rq_axis(ax, rqs):
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(rqs))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.xaxis.set_minor_formatter(NullFormatter())


def figs_exp2(data, out, note):
    """one graph per layout of results/exp2_layouts.json: User verification vs r_Q, every scheme;
    then the bytes returned vs r_Q (dispersed)"""
    layouts = [l for l in EXP2_LAYOUT if any(by(rows, layout=l) for rows in data.values())]
    n = next(int(r["N"]) for rows in data.values() for r in ok(rows))
    letters = iter("abcdefgh")
    for lay in layouts:
        fig, ax = paper_fig()
        for s, rows in data.items():
            rows = by(rows, layout=lay)
            if s == "secollab":
                scheme_line(ax, s, [(int(r["rQ"]), *val(r, "verify_total")) for r in rows
                                    if r.get("proof_mode") == "paths"], "SE-COLLAB [37] (per-path, paper)")
                scheme_line(ax, s, [(int(r["rQ"]), *val(r, "verify_total")) for r in rows
                                    if r.get("proof_mode") == "multi"], "SE-COLLAB [37] (multiproof)", variant=True)
            else:
                scheme_line(ax, s, [(int(r["rQ"]), *val(r, "verify_total")) for r in rows])
        rq_axis(ax, sorted({int(r["rQ"]) for rows in data.values() for r in ok(rows)}))
        ax.set_yscale("log")
        paper_finish(fig, ax, next(letters), f"Exp. 2: User verification vs $r_Q$ ({lay.replace('_', ' ')})",
                     "Number of results $r_Q$", "User verification time (ms)",
                     f"N = {n:,} · layout: {EXP2_LAYOUT[lay]} (same files in every scheme, results/exp2_layouts.json)"
                     f" · Chen [40], Du [7]: no Merkle proof, each result checked on its own (reference) · {note}", os.path.join(out, f"compare_exp2_verify_vs_rQ_{lay}"))
    fig, ax = paper_fig()
    for s, rows in data.items():
        rows = [r for r in by(rows, layout="dispersed") if r.get("response_bytes") and r.get("proof_mode", "paths") != "multi"]
        scheme_line(ax, s, [(int(r["rQ"]), float(r["response_bytes"]) / KB, 0) for r in rows],
                    NAME[s] + (" (per-path)" if s == "secollab" else ""))
    rq_axis(ax, sorted({int(r["rQ"]) for rows in data.values() for r in ok(rows)}))
    ax.set_yscale("log")
    paper_finish(fig, ax, next(letters), "Exp. 2: data returned vs $r_Q$ (dispersed)", "Number of results $r_Q$",
                 "Response size (KB, 1 KB = 1000 B)", f"N = {n:,} · results + proof · {note}",
                 os.path.join(out, "compare_exp2_response_vs_rQ"))


def figs_exp3(data, out, note):
    """(a) inserting / deleting one file vs N; (b) time per file vs batch size at the largest N"""
    data = {s: {op: exp3_rows(rows, op) for op in ("insert", "delete")} for s, rows in data.items()}
    na = ", ".join(NAME[s] for s in ("du", "secollab") if s not in data)
    tail = note + (f" · no dynamic update (N/A): {na}" if na else "")
    fig, ax = paper_fig()
    ns = set()
    for s, ops in data.items():
        for op in ("insert", "delete"):
            pts = [(int(r["N"]), r["per_file"], r["per_file_std"]) for r in ops[op] if int(r["batch"]) == 1]
            ns |= {p[0] for p in pts}
            scheme_line(ax, s, pts, f"{NAME[s]}: {op}", variant=op == "delete")
    n_axis(ax, sorted(ns))
    ax.set_yscale("log")
    paper_finish(fig, ax, "a", "Exp. 3: updating one file vs N", "Database size N (documents)", "Time (ms)", tail,
                 os.path.join(out, "compare_exp3_update_one_vs_N"))
    fig, ax = paper_fig()
    n = max(ns)
    for s, ops in data.items():
        for op in ("insert", "delete"):
            pts = [(int(r["batch"]), r["per_file"], r["per_file_std"]) for r in ops[op] if int(r["N"]) == n]
            scheme_line(ax, s, pts, f"{NAME[s]}: {op}", variant=op == "delete")
    rq_axis(ax, sorted({int(r["batch"]) for ops in data.values() for r in ops["insert"]}))
    ax.set_yscale("log")
    paper_finish(fig, ax, "b", f"Exp. 3: time per file vs batch size (N = {n:,})", "Batch size (files)",
                 "Time per file (ms)", tail, os.path.join(out, "compare_exp3_per_file_vs_batch"))


def figs_exp5(data, out, note, note_u, kq=4):
    """(a) query of the target domain vs D, schemes with domains; (b) updating one domain vs D"""
    fig, ax = paper_fig()
    ds = set()
    for s, rows in data.items():
        for sh, ls in (("conjunctive", "-"), ("disjunctive", "--")):
            pts = [(int(r["domains"]), *val(r, "end_to_end")) for r in by(rows, op="query", kQ=kq, shape=sh)]
            ds |= {p[0] for p in pts}
            scheme_line(ax, s, pts, f"{NAME[s]}: {SHAPE_LABEL[sh]}", ls=ls)
    clouds_axis(ax, sorted(ds))
    ax.set_yscale("log")
    absent = "Chen [40], Du [7]: one data owner, no domains (not shown)"
    paper_finish(fig, ax, "a", f"Exp. 5: query of one domain vs D ($k_Q$ = {kq})",
                 "Number of domains D (5,000 documents each)", "End-to-end search time (ms)",
                 f"{absent} · results/exp5_workload.json · {note}", os.path.join(out, "compare_exp5_query_vs_domains"))
    fig, ax = paper_fig()
    na = []
    for s, rows in data.items():
        u = by(rows, op="update_one_domain")
        if not u:
            na.append(NAME[s])
            continue
        scheme_line(ax, s, [(int(r["domains"]), *val(r, "update")) for r in u], f"{NAME[s]}: update one domain")
        scheme_line(ax, s, [(int(r["domains"]), *val(r, "anchor_update")) for r in u],
                    f"{NAME[s]}: signature + anchor + Global Root", variant=True)
    clouds_axis(ax, sorted(ds))
    ax.set_yscale("log")
    paper_finish(fig, ax, "b", "Exp. 5: updating one domain vs D", "Number of domains D (5,000 documents each)",
                 "Time (ms)", (f"no dynamic update (N/A): {', '.join(na)} · " if na else "") + f"{absent} · {note_u}",
                 os.path.join(out, "compare_exp5_update_vs_domains"))


# ============================================================================
# 6) main
# ============================================================================
def main():
    global DATASET
    ap = argparse.ArgumentParser(description="plot baseline results")
    ap.add_argument("schemes", nargs="+", choices=list(NAME), help="scheme ที่จะวาด")
    ap.add_argument("--results", default=os.path.join(HERE, "results"), help="โฟลเดอร์ผล (มี <scheme>/ อยู่ข้างใน)")
    ap.add_argument("--out", default=None, help="โฟลเดอร์รูปเดียวสำหรับทุกกราฟ (ค่าเริ่มต้น <results>/<scheme>/figures และ <results>/compare)")
    ap.add_argument("--reps", type=int, default=30, help="จำนวนรอบที่วัด (เขียนในหมายเหตุท้ายภาพ)")
    ap.add_argument("--note", default="test machine (not final numbers)", help="หมายเหตุท้ายภาพ")
    ap.add_argument("--dataset", default="dataset-v4 (arXiv)", help="ชื่อ dataset ที่เขียนในหมายเหตุท้ายภาพ")
    a = ap.parse_args()
    DATASET = a.dataset
    base = f"{DATASET} · median of {a.reps} runs, error bars ±1 std · {a.note}"
    perq = f"{DATASET} · median over queries (each: median of {a.reps} runs), error bars: fastest–slowest query · {a.note}"
    one = f"{DATASET} · one point per query (median of {a.reps} runs), every shape · {a.note}"
    cmp_out = a.out or os.path.join(a.results, "compare")    # กราฟรวมทุก scheme
    os.makedirs(cmp_out, exist_ok=True)
    every = {suite: {} for suite in ("exp1_boolean_scalability", "exp2_selective_proof", "exp3_dynamic_update",
                                     "exp5_domains")}
    for s in a.schemes:
        out = a.out or os.path.join(a.results, s, "figures")  # รูปของ scheme นี้
        os.makedirs(out, exist_ok=True)
        rows = load(s, "exp1_boolean_scalability", a.results)
        if rows:
            if s == "amtp":                              # AMTP's cost follows pQ, not N
                exp1_time_vs_pq(s, rows, out, one)
                fig_exp1_pq(rows, cmp_out, one)
            rows = over_queries(rows)
            note = perq if any(r["n_queries"] > 1 for r in rows) else base
            every["exp1_boolean_scalability"][s] = rows
            na = "" if s in ("secollab", "amtp") else f" · OR / nested: N/A (unsupported by {NAME[s].split()[-1]})"
            exp1_search_vs_n(s, rows, out, note + na)
            exp1_shapes_vs_n(s, rows, out, note)
            exp1_breakdown(s, rows, out, note)
        rows = load(s, "exp2_selective_proof", a.results)
        if rows:
            every["exp2_selective_proof"][s] = rows
            exp2_verify_vs_rq(s, rows, out, base)
        rows = load(s, "exp3_dynamic_update", a.results)
        if rows:
            every["exp3_dynamic_update"][s] = rows
            exp3_update_vs_batch(s, rows, out, base)
        if s == "amtp":                                  # Exp. 4: bench.ablation folders results/amtp/exp4*/
            for folder in sorted(glob.glob(os.path.join(a.results, "amtp", "exp4*", ""))):
                exp4_ablation(folder, out, a.note, cmp_out)
        rows = load(s, "clouds_sensitivity", a.results)  # Du only: n_c sweep (not Exp. 5)
        if rows:
            rows = over_queries(rows)
            note = perq if any(r["n_queries"] > 1 for r in rows) else base
            exp5_cost_vs_clouds(s, rows, out, note)
            exp5_verify_vs_clouds(s, rows, out, note)
        rows = load(s, "exp5_domains", a.results)
        if rows:
            rows = over_queries(rows)
            every["exp5_domains"][s] = rows
            exp5_domains(s, rows, out, perq if any(r["n_queries"] > 1 for r in rows) else base)
    e = every
    if e["exp1_boolean_scalability"]:
        figs_exp1(e["exp1_boolean_scalability"], cmp_out, perq)
    if e["exp2_selective_proof"]:
        figs_exp2(e["exp2_selective_proof"], cmp_out, base)
    if e["exp3_dynamic_update"]:
        figs_exp3(e["exp3_dynamic_update"], cmp_out, base)
    if e["exp5_domains"]:
        figs_exp5(e["exp5_domains"], cmp_out, perq, base)


if __name__ == "__main__":
    main()
