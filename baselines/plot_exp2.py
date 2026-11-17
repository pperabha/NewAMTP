"""
plot_exp2.py
============================================================================
Exp. 2 (verification) figures for the paper, no title (the caption is in LaTeX), same style as plot_exp1.py.

  python3 baselines/plot_exp2.py --data baselines/results/part_leaf/data --out baselines/results/part_leaf/graphs/exp2

  exp2_a_tamper_detection         detection rate (%) vs tampered files t, one panel per attack, every scheme
                                  (a scheme that cannot express an attack is left out of that panel and named in it)
  exp2_b_single_verify_vs_results single domain: user verification time vs returned files, every scheme
  exp2_c_multi_verify_vs_results  multi-domain: user verification time vs returned files, AMTP vs SE-COLLAB
  exp2_bc                         (b) and (c) side by side

Inputs: <data>/<scheme>/<scheme>_{tamper_detection,verify_single,verify_multi}.csv of one round.
Verification points: one per target result size; x = median returned files over the keywords of that target,
y = median verify_total over them (each already the median of its reps), bars = 25th-75th percentile.
Every plotted number goes to <out>/figure_points.csv.
============================================================================
"""
import argparse
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plot_paper as P  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402
from plot_exp1 import ORDER, plain_log_y, rows, style  # noqa: E402
from plot_results import INK2, NAME, STYLE, SURFACE, paper_line, plt  # noqa: E402

ATTACKS = (("modify", "Modified files"), ("hide", "Hidden files"), ("inject", "Injected files"),
           ("old_version", "Old versions of files"))


def save(f, out, name):
    for ext in ("png", "pdf"):
        f.savefig(os.path.join(out, f"{name}.{ext}"), facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(os.path.join(out, name + ".png")))


def tamper(out, data):
    data_by = {s: rows(data, s, "tamper_detection") for s in ORDER}
    f, axes = plt.subplots(1, 4, figsize=(14.0, 3.7), dpi=200, sharey=True)
    f.patch.set_facecolor(SURFACE)
    offset = {"amtp": 0.0, "chen": -2.0, "secollab": -4.0, "du": -6.0}   # drawn offset so equal lines stay visible (stated in the caption; figure_points.csv keeps the true values)
    for i, (ax, (kind, title)) in enumerate(zip(axes, ATTACKS)):
        style(ax)
        missing = []
        for s in ORDER:
            rs = [r for r in data_by[s] if r["tamper"] == kind and r["status"] == "ok" and r["detected_runs"] != ""]
            if not rs:
                missing.append(NAME[s])
                continue
            by_t = {}
            for r in rs:
                d = by_t.setdefault(int(r["tampered"]), [0, 0])
                d[0] += int(r["detected_runs"])
                d[1] += int(r["runs"])
            xs = sorted(by_t)
            ys = [100.0 * by_t[t][0] / by_t[t][1] for t in xs]
            color, marker = STYLE[s]
            paper_line(ax, xs, [y + offset[s] if 0 < y else y + (-offset[s]) for y in ys], [0.0] * len(xs),
                       color, marker, NAME[s])
            for t, y in zip(xs, ys):
                P.POINTS.append({"figure": f"Exp2_a_{kind}", "series": NAME[s], "x": t, "y": round(y, 3),
                                 "err_down": 0, "err_up": 0})
        ax.set_xscale("log")
        ticks = sorted({int(r["tampered"]) for r in data_by["amtp"] if r["tamper"] == kind})
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_ylim(-12, 112)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Tampered files $t$", color=INK2, fontsize=10.5)
        if i == 0:
            ax.set_ylabel("Tampered responses detected (%)", color=INK2, fontsize=10.5)
        ax.set_title(f"({'abcd'[i]}) {title}", fontsize=10.5, color=INK2, loc="left")
        if missing:
            ax.text(0.03, 0.45, "not applicable:\n" + ", ".join(missing), transform=ax.transAxes, fontsize=8.5,
                    color=INK2, va="center")
    seen = {}
    for ax in axes:                                        # every scheme appears in at least one panel
        for h, l in zip(*ax.get_legend_handles_labels()):
            seen.setdefault(l, h)
    labels = [NAME[s] for s in ORDER if NAME[s] in seen]
    f.legend([seen[l] for l in labels], labels, loc="upper center", ncol=4, frameon=False, fontsize=10,
             bbox_to_anchor=(0.5, 1.0))
    f.tight_layout(rect=(0, 0, 1, 0.9))
    save(f, out, "exp2_a_tamper_detection")


SHORT = {"modify": "modified", "hide": "hidden", "inject": "injected", "old_version": "old version"}


def tamper_summary(out, data):
    """One panel: how many of the 4 attack types each scheme detects in every run, vs tampered files t
    (same figure as plot_story.detection_vs_tampered, without the title; equal lines drawn slightly apart)."""
    f, ax = plt.subplots(figsize=(7.6, 4.4), dpi=200)
    f.patch.set_facecolor(SURFACE)
    style(ax)
    res, notes = {}, {}
    for s in ORDER:
        rs = [r for r in rows(data, s, "tamper_detection") if r["tamper"] != "none" and r["status"] == "ok"
              and r["detected_runs"] != ""]
        agg = {}
        for r in rs:
            a = agg.setdefault((int(r["tampered"]), r["tamper"]), [0, 0])
            a[0] += int(r["detected_runs"])
            a[1] += int(r["runs"])
        ts = sorted({t for t, _ in agg})
        kinds = sorted({k for _, k in agg}, key=list(SHORT).index)
        ys = [sum(1 for k in kinds if agg.get((t, k), [0, 0])[1] and agg[(t, k)][0] == agg[(t, k)][1]) for t in ts]
        missed = [SHORT[k] for k in kinds if any(agg[(t, k)][0] < agg[(t, k)][1] for t in ts if (t, k) in agg)]
        if len(kinds) < 4:
            notes[s] = f"{ys[-1]} of {len(kinds)} applicable  ·  returns no files"
        elif missed:
            notes[s] = f"{ys[-1]} of 4  ·  misses " + ", ".join(missed)
        else:
            notes[s] = f"{ys[-1]} of 4  ·  every attack"
        res[s] = (ts, ys)
    seen = {}
    for s in ORDER:
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
            P.POINTS.append({"figure": "Exp2_attack_types", "series": NAME[s], "x": t, "y": y,
                             "err_down": 0, "err_up": 0})
    ts = res["amtp"][0]
    ax.set_xscale("log")
    ax.set_xticks(ts)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(ts[0] * 0.75, ts[-1] * 14)
    ax.set_ylim(-0.3, 4.9)
    ax.set_yticks(range(5))
    rq = sorted({int(r["rQ"]) for r in rows(data, "amtp", "tamper_detection")})
    ax.set_xlabel(f"Tampered files $t$ (of {rq[0]:,}–{rq[-1]:,} returned)", color=INK2, fontsize=10.5)
    ax.set_ylabel("Attack types detected in every run (of 4)", color=INK2, fontsize=10.5)
    ax.legend(frameon=False, fontsize=9.5, loc="upper left", ncol=4)
    f.tight_layout()
    save(f, out, "exp2_a2_attack_types_detected")


def tamper_bars(out, data):
    """Bar chart (owner's request, kept in extra/): detection rate per attack type, one bar per scheme,
    over every tampered-file count t; n/a where the scheme cannot express the attack."""
    import numpy as np
    f, ax = plt.subplots(figsize=(8.4, 4.0), dpi=200)
    f.patch.set_facecolor(SURFACE)
    style(ax)
    ax.grid(False, axis="x")
    groups = list(ATTACKS) + [("none", "No tampering\n(false alarms)")]
    w = 0.8 / len(ORDER)
    x = np.arange(len(groups))
    for i, s in enumerate(ORDER):
        rs = [r for r in rows(data, s, "tamper_detection") if r["status"] == "ok" and r["detected_runs"] != ""]
        color, _ = STYLE[s]
        for j, (kind, _) in enumerate(groups):
            g = [r for r in rs if r["tamper"] == kind]
            xpos = x[j] - 0.4 + w * (i + 0.5)
            if not g:
                ax.text(xpos, 2, "n/a", ha="center", va="bottom", fontsize=7.5, color=INK2, rotation=90)
                continue
            det, runs = sum(int(r["detected_runs"]) for r in g), sum(int(r["runs"]) for r in g)
            y = 100.0 * det / runs
            ax.bar(xpos, y, w * 0.92, color=color, label=NAME[s] if j == 0 or not ax.get_legend_handles_labels()[1]
                   .count(NAME[s]) == 0 else None, zorder=3)
            if y == 0:
                ax.text(xpos, 1.5, "0", ha="center", va="bottom", fontsize=8, color=color)
            P.POINTS.append({"figure": "Exp2_bars", "series": NAME[s], "x": kind, "y": round(y, 3),
                             "err_down": 0, "err_up": 0})
    handles, labels = [], []
    for s in ORDER:
        handles.append(plt.Rectangle((0, 0), 1, 1, color=STYLE[s][0]))
        labels.append(NAME[s])
    ax.legend(handles, labels, frameon=False, fontsize=9.5, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.12))
    ax.set_xticks(x)
    ax.set_xticklabels([t for _, t in groups], fontsize=9.5, color=INK2)
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Tampered responses detected (%)", color=INK2, fontsize=10.5)
    f.tight_layout()
    save(f, out, "exp2_tamper_bars")


def verify_points(rs):
    """{x: (y, (down, up))} with x = median rQ of each target result size"""
    groups = {}
    for r in rs:
        groups.setdefault(int(r["target_results"]), []).append(r)
    pts = {}
    for _, g in sorted(groups.items()):
        x = statistics.median(int(r["rQ"]) for r in g)
        pts[x] = P.agg(g, lambda r: 0, "verify_total_ms_median")[0]
    return pts


def verify_panel(ax, fig_id, data, suite, schemes, xlabel):
    style(ax)
    xs = set()
    for s in schemes:
        pts = verify_points([r for r in rows(data, s, suite) if r.get("status", "ok") == "ok"])
        P.scheme_line(ax, fig_id, s, pts)
        xs |= set(pts)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    plain_log_y(ax)
    ax.set_xlabel(xlabel, color=INK2, fontsize=10.5)
    ax.set_ylabel("User verification time (ms)", color=INK2, fontsize=10.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="folder with amtp/, chen/, secollab/, du/ (same round)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    extra = os.path.join(a.out, "extra")                # not for the paper: per-attack detail, bar chart
    os.makedirs(extra, exist_ok=True)
    tamper(extra, a.data)
    tamper_bars(extra, a.data)
    tamper_summary(a.out, a.data)
    specs = (("b", "exp2_b_single_verify_vs_results", "verify_single", ORDER, "Returned files $r_Q$ (single domain)"),
             ("c", "exp2_c_multi_verify_vs_results", "verify_multi", ("amtp", "secollab"),
              "Returned files $r_Q$ (all queried domains)"))
    for letter, name, suite, schemes, xlabel in specs:
        f, ax = plt.subplots(figsize=(5.4, 3.9), dpi=200)
        f.patch.set_facecolor(SURFACE)
        verify_panel(ax, f"Exp2_{letter}", a.data, suite, schemes, xlabel)
        ax.legend(frameon=False, fontsize=9, loc="best")
        f.tight_layout()
        save(f, a.out, name)
    before = len(P.POINTS)
    f, axes = plt.subplots(1, 2, figsize=(11.0, 4.0), dpi=200)
    f.patch.set_facecolor(SURFACE)
    for ax, (letter, _, suite, schemes, xlabel) in zip(axes, specs):
        verify_panel(ax, f"Exp2_{letter}", a.data, suite, schemes, xlabel)
        ax.text(0.5, -0.22, f"({letter})", transform=ax.transAxes, ha="center", va="top", fontsize=11.5, color=INK2)
    del P.POINTS[before:]
    handles, labels = axes[0].get_legend_handles_labels()
    f.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 1.0))
    f.tight_layout(rect=(0, 0, 1, 0.92))
    save(f, a.out, "exp2_bc")
    path = os.path.join(a.out, "figure_points.csv")
    with open(path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["figure", "series", "x", "y", "err_down", "err_up"])
        w.writeheader()
        w.writerows(P.POINTS)
    print(f"{len(P.POINTS)} points -> {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
