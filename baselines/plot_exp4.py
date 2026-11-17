"""
plot_exp4.py
============================================================================
Exp. 4 as an ablation of the update cost, no title (the caption is in LaTeX), same style as plot_exp1.py.

  python3 baselines/plot_exp4.py --runs baselines/results/runs/cloud --out baselines/results/part_leaf/graphs/exp4

Variants (bench/ablation.py, same placement rule "fill", same workload, same machine type):
  AMTP          adaptive partitions: split above theta_max, merge below theta_min
  Static-MT     the same partitions without split / merge (AMTP minus adaptation)
  Global-MT(v)  one partition for the whole domain, partition version kept (AMTP minus partitioning)
Workload: 100,000 initial files; phase 1 = 1,000 insert batches of b = 100 (95% into one hot group);
phase 2 = delete 65% of the hot group's live files, 100 per batch.

  exp4_a_update_vs_batch      update time per batch vs batch (theta_max 64), rolling median of 25 batches
  exp4_b_cumulative_vs_batch  total update time so far vs batch (theta_max 64)
  exp4_c_hash_vs_batch        hashed bytes per batch vs batch (theta_max 64): the work behind (a)
  exp4_d_maxpart_vs_batch     largest partition vs batch (theta_max 64): why Static-MT gets slower
  exp4_all_4                  (a)-(d) as one 2 x 2 figure

theta_max = 64 only (owner's choice; the 128 / 256 runs stay in runs/cloud/prune_w3, prune_w4, not plotted).
Inputs: <runs>/prune_w2/paper_prune_v/amtp/splitmerge_n100000_t64/ (AMTP, Static-MT) and
<runs>/prune_w5/paper_prune_v/amtp/splitmerge_n100000_t64_gmtv/ (Global-MT(v)). Every plotted number goes to
<out>/figure_points.csv.
============================================================================
"""
import argparse
import csv
import glob
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from matplotlib.ticker import FuncFormatter  # noqa: E402
from plot_exp1 import plain_log_y, style  # noqa: E402
from plot_results import EXP4_STYLE, INK2, SURFACE, plt  # noqa: E402

VARIANTS = ("AMTP", "Static-MT", "Global-MT(v)")
POINTS = []
ROLL = 25


def folder(runs, theta, gmtv=False):
    pat = f"prune_w*/paper_prune_v/amtp/splitmerge_n100000_t{theta}{'_gmtv' if gmtv else ''}"
    hits = sorted(glob.glob(os.path.join(runs, pat)))
    if len(hits) != 1:
        raise SystemExit(f"expected one folder for {pat}, found {hits}")
    return hits[0]


def load(path, name):
    with open(os.path.join(path, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def series(runs, theta):
    """{variant: rows of updates.csv in batch order (insert phase then delete phase)}, and the layout rows"""
    up, lay = {}, {}
    sources = [folder(runs, theta)] + ([folder(runs, theta, gmtv=True)] if theta == 64 else [])
    for src in sources:
        for r in load(src, "updates.csv"):
            up.setdefault(r["variant"], []).append(r)
        for r in load(src, "layout.csv"):
            lay.setdefault(r["variant"], []).append(r)
    order = {"insert": 0, "hot_delete": 1}
    for v in up:
        up[v].sort(key=lambda r: (order[r["phase"]], int(r["batch"])))
    return up, lay


def rolling(ys, k=ROLL):
    h = k // 2
    return [statistics.median(ys[max(0, i - h): i + h + 1]) for i in range(len(ys))]


def line(ax, fig_id, xs, ys, v):
    color, marker, ls = EXP4_STYLE[v]
    ax.plot(xs, ys, color=color, linestyle=ls, linewidth=2.0, label=v)
    POINTS.extend({"figure": fig_id, "series": v, "x": x, "y": round(y, 6)} for x, y in zip(xs, ys))


def phase_mark(ax, n_insert):
    ax.axvline(n_insert, color=INK2, linewidth=1.0, linestyle=":")
    ax.text(n_insert, 1.0, " deletions start", transform=ax.get_xaxis_transform(), fontsize=8.5, color=INK2,
            va="top", ha="left")


def draw_a(ax, up):
    style(ax)
    for v in VARIANTS:
        if v in up:
            ys = [float(r["update_ms"]) / 1e3 for r in up[v]]
            line(ax, "Exp4_a", list(range(1, len(ys) + 1)), rolling(ys), v)
    plain_log_y(ax)
    phase_mark(ax, sum(1 for r in up["AMTP"] if r["phase"] == "insert"))
    ax.set_xlabel("Update batch ($b = 100$ operations)", color=INK2, fontsize=10.5)
    ax.set_ylabel("Update time per batch (s)", color=INK2, fontsize=10.5)


def draw_cum(ax, up):
    style(ax)
    for v in VARIANTS:
        if v in up:
            tot, ys = 0.0, []
            for r in up[v]:
                tot += float(r["update_ms"]) / 3.6e6
                ys.append(tot)
            line(ax, "Exp4_b", list(range(1, len(ys) + 1)), ys, v)
            ax.annotate(f"{ys[-1]:.1f} h", (len(ys), ys[-1]), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=8.5, color=EXP4_STYLE[v][0])
    ax.set_xlim(-80, 1900)
    phase_mark(ax, sum(1 for r in up["AMTP"] if r["phase"] == "insert"))
    ax.set_xlabel("Update batch ($b = 100$ operations)", color=INK2, fontsize=10.5)
    ax.set_ylabel("Total update time so far (h)", color=INK2, fontsize=10.5)


def draw_c(ax, up):
    style(ax)
    for v in VARIANTS:
        if v in up:
            ys = [float(r["hash_bytes"]) / 1e6 for r in up[v]]
            line(ax, "Exp4_c", list(range(1, len(ys) + 1)), rolling(ys), v)
    plain_log_y(ax)
    phase_mark(ax, sum(1 for r in up["AMTP"] if r["phase"] == "insert"))
    ax.set_xlabel("Update batch ($b = 100$ operations)", color=INK2, fontsize=10.5)
    ax.set_ylabel("Data hashed per batch (MB)", color=INK2, fontsize=10.5)


def draw_d(ax, lay, n_insert):
    style(ax)
    order = {"insert": 0, "hot_delete": 1}
    for v in VARIANTS:
        if v not in lay:
            continue
        rs = sorted(lay[v], key=lambda r: (order.get(r["phase"], -1), int(r["batch"])))
        xs = [int(r["batch"]) + 1 for r in rs]          # layout.csv numbers batches across both phases
        ys = [int(r["max_partition"]) for r in rs]
        color, marker, ls = EXP4_STYLE[v]
        ax.plot(xs, ys, color=color, marker=marker, markersize=5, markeredgecolor="white" if marker != "x" else color,
                linestyle=ls, linewidth=2.0, label=v)
        POINTS.extend({"figure": "Exp4_d", "series": v, "x": x, "y": y} for x, y in zip(xs, ys))
    plain_log_y(ax)
    ax.set_xlim(-80, 1760)                               # same x range as (a) and (c)
    phase_mark(ax, n_insert)
    ax.set_xlabel("Update batch ($b = 100$ operations)", color=INK2, fontsize=10.5)
    ax.set_ylabel("Largest partition (live files)", color=INK2, fontsize=10.5)


def save(f, out, name):
    for ext in ("png", "pdf"):
        f.savefig(os.path.join(out, f"{name}.{ext}"), facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(os.path.join(out, name + ".png")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="folder holding prune_w2 .. prune_w5")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    up, lay = series(a.runs, 64)
    n_insert = sum(1 for r in up["AMTP"] if r["phase"] == "insert")
    draws = (("exp4_a_update_vs_batch", lambda ax: draw_a(ax, up)),
             ("exp4_b_cumulative_vs_batch", lambda ax: draw_cum(ax, up)),
             ("exp4_c_hash_vs_batch", lambda ax: draw_c(ax, up)),
             ("exp4_d_maxpart_vs_batch", lambda ax: draw_d(ax, lay, n_insert)))
    for name, fn in draws:
        f, ax = plt.subplots(figsize=(5.6, 4.0), dpi=200)
        f.patch.set_facecolor(SURFACE)
        fn(ax)
        ax.legend(frameon=False, fontsize=8.5, loc="lower center" if name.endswith("theta") else "best",
                  ncol=2 if name.endswith("theta") else 1)
        f.tight_layout()
        save(f, a.out, name)
    keep = len(POINTS)
    f, axes = plt.subplots(2, 2, figsize=(11.0, 8.2), dpi=200)
    f.patch.set_facecolor(SURFACE)
    for (name, fn), ax, letter in zip(draws, axes.flat, "abcd"):
        fn(ax)
        ax.legend(frameon=False, fontsize=8, loc="lower center" if name.endswith("theta") else "best",
                  ncol=2 if name.endswith("theta") else 1)
        ax.text(0.5, -0.2, f"({letter})", transform=ax.transAxes, ha="center", va="top", fontsize=11.5, color=INK2)
    del POINTS[keep:]
    f.tight_layout()
    save(f, a.out, "exp4_all_4")
    path = os.path.join(a.out, "figure_points.csv")
    with open(path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["figure", "series", "x", "y"])
        w.writeheader()
        w.writerows(POINTS)
    print(f"{len(POINTS)} points -> {os.path.relpath(path)}  (rolling median over {ROLL} batches in (a), (c))")


if __name__ == "__main__":
    main()
