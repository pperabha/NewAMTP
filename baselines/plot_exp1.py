"""
plot_exp1.py
============================================================================
Exp. 1 figures for the paper: one figure = two panels side by side, no title (the caption is in LaTeX).

  (a) server search time without proof generation and without ciphertext retrieval
  (b) end-to-end search time (query generation + server + verification + decryption)

  python3 baselines/plot_exp1.py --data baselines/results/part_leaf/data \
      --no-fetch baselines/results/part_leaf/data_no_fetch --out baselines/results/part_leaf/graphs/exp1

Sources (every scheme of a panel from the same round):
  (a) AMTP server_search_pf, Chen server_total               <data>/{amtp,chen}
      SE-COLLAB, Du search_no_fetch                           <no-fetch>/{secollab,du}
  (b) every scheme end_to_end                                 <data>/{amtp,chen,secollab,du}
Same aggregation as plot_paper.py: per point the median over the queries of all domains (each already the median
of its reps); bars = 25th-75th percentile. Same colours and markers; legend order AMTP, Chen, SE-COLLAB, Du.
Every plotted number goes to <out>/figure_points.csv.
============================================================================
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plot_paper as P  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402
from plot_results import AXIS, GRID, INK2, SURFACE, plt  # noqa: E402

ORDER = ("amtp", "chen", "secollab", "du")
SEARCH_COL = {"amtp": "server_search_pf", "chen": "server_total", "secollab": "search_no_fetch",
              "du": "search_no_fetch"}
FROM_NO_FETCH = ("secollab", "du")


def rows(folder, scheme, suite):
    path = os.path.join(folder, scheme, f"{scheme}_{suite}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}")
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status", "ok") == "ok"]


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=10)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plain_log_y(ax):
    """log y with plain decimal labels at 1, 2, 5 x 10^k (no 4x10^-1 style labels)"""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())


def pair(fig_id, path, data, no_fetch, suite, keep, key, xlabel, ticks, k_label=False):
    f, axes = plt.subplots(1, 2, figsize=(11.0, 4.0), dpi=200)
    f.patch.set_facecolor(SURFACE)
    panels = (("a", "Search time, no proof, no fetch (ms)", lambda s: SEARCH_COL[s],
               lambda s: no_fetch if s in FROM_NO_FETCH else data),
              ("b", "End-to-end search time (ms)", lambda s: "end_to_end", lambda s: data))
    for ax, (letter, ylabel, col, src) in zip(axes, panels):
        style(ax)
        for s in ORDER:
            rs = [r for r in rows(src(s), s, suite) if keep(r)]
            P.scheme_line(ax, f"{fig_id}_{letter}", s, P.agg(rs, key, col(s) + "_ms_median"))
        plain_log_y(ax)
        ax.set_xticks(ticks)
        if k_label:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k"))
        ax.set_xlabel(xlabel, color=INK2, fontsize=11)
        ax.set_ylabel(ylabel, color=INK2, fontsize=11)
        ax.text(0.5, -0.22, f"({letter})", transform=ax.transAxes, ha="center", va="top", fontsize=11.5,
                color=INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    f.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 1.0))
    f.tight_layout(rect=(0, 0, 1, 0.92))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for ext in ("png", "pdf"):
        f.savefig(f"{path}.{ext}", facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(path + ".png"))


MEASURES = {"search": ("Search, no proof, no fetch (ms)", lambda s: SEARCH_COL[s], True),
            "server_search": ("Server search time (ms)", lambda s: SEARCH_COL[s], True),   # same data, plain label
            "server": ("Server time: search + proof + fetch (ms)", lambda s: "server_total", False),
            "end_to_end": ("End-to-end search time (ms)", lambda s: "end_to_end", False)}


def boolean(path, data, no_fetch, measures, only=None):
    """Search 2.1 (multi-domain Boolean): one column per query shape, one row per measure; AMTP vs SE-COLLAB
    (the only baseline with multi-domain Boolean queries)."""
    amtp = rows(data, "amtp", "search_multi")
    shapes = [s for s in P.SHAPES if any(r["shape"] == s for r in amtp) and (only is None or s in only)]
    kqs = sorted({int(r["kQ"]) for r in amtp})
    nd, nper = P.one([int(r["domains"]) for r in amtp], "D"), P.one([int(r["N_per_domain"]) for r in amtp], "N")
    one = len(measures) * len(shapes) == 1
    f, axes = plt.subplots(len(measures), len(shapes),
                           figsize=(5.4, 4.2) if one else (3.3 * len(shapes), 3.3 * len(measures) + 0.6),
                           dpi=200, squeeze=False)
    f.patch.set_facecolor(SURFACE)
    letters = iter("abcdefghijklmnop")
    for i, m in enumerate(measures):
        ylabel, col, nf = MEASURES[m]
        for j, shape in enumerate(shapes):
            ax = axes[i][j]
            style(ax)
            for s in ("amtp", "secollab"):
                src = no_fetch if (nf and s in FROM_NO_FETCH) else data
                rs = [r for r in rows(src, s, "search_multi") if r["shape"] == shape]
                P.scheme_line(ax, f"S2.1_{shape}_{m}", s, P.agg(rs, lambda r: int(r["kQ"]), col(s) + "_ms_median"))
            plain_log_y(ax)
            ax.set_xscale("log", base=2)
            ax.set_xticks(kqs)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax.xaxis.set_minor_formatter(NullFormatter())
            ax.set_xlabel("Keywords in the query $k_Q$", color=INK2, fontsize=10)
            if j == 0:
                ax.set_ylabel(ylabel, color=INK2, fontsize=10)
            tag = f"({next(letters)}) " if len(measures) * len(shapes) > 1 else ""
            ax.set_title(f"{tag}{shape.replace('_', '-')}: {P.SHAPES[shape]}", fontsize=10,
                         color=INK2, loc="left")
    handles, labels = axes[0][0].get_legend_handles_labels()
    f.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 1.0))
    f.tight_layout(rect=(0, 0, 1, 1 - 0.45 / (3.3 * len(measures) + 0.6)))
    for ext in ("png", "pdf"):
        f.savefig(f"{path}.{ext}", facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(path + ".png"), f"({nd} domains x {nper} documents)")


def search_set(out, data, no_fetch, n_fix, kqs_single):
    """Exp. 1 for the paper (owner's choice): server search time only (no end-to-end), plain label; the caption
    states that proof generation and ciphertext retrieval are excluded.
    (a) single domain, AND, every scheme  (b) 4 domains, AND-of-OR  (c) 4 domains, OR-of-AND (vs SE-COLLAB)"""
    kqs_multi = sorted({int(r["kQ"]) for r in rows(data, "amtp", "search_multi")})
    single = lambda r: int(r["N"]) == n_fix                                          # noqa: E731
    specs = [
        ("a", "exp1_a_single_search_vs_kQ", "search_single", single, ORDER, kqs_single, False,
         "Keywords in the AND query $k_Q$"),
        ("b", "exp1_b_multi_AND_of_OR_search_vs_kQ", "search_multi", lambda r: r["shape"] == "AND_of_OR",
         ("amtp", "secollab"), kqs_multi, True, "Keywords in $(A \\vee B) \\wedge (C \\vee D) \\dots$"),
        ("c", "exp1_c_multi_OR_of_AND_search_vs_kQ", "search_multi", lambda r: r["shape"] == "OR_of_AND",
         ("amtp", "secollab"), kqs_multi, True, "Keywords in $(A \\wedge B) \\vee (C \\wedge D) \\dots$"),
    ]
    ylabel, col, nf = MEASURES["server_search"]

    def draw(ax, spec):
        letter, _, suite, keep, schemes, ticks, log2, xlabel = spec
        style(ax)
        for s in schemes:
            src = no_fetch if (nf and s in FROM_NO_FETCH) else data
            rs = [r for r in rows(src, s, suite) if keep(r)]
            P.scheme_line(ax, f"Exp1s_{letter}", s, P.agg(rs, lambda r: int(r["kQ"]), col(s) + "_ms_median"))
        plain_log_y(ax)
        if log2:
            ax.set_xscale("log", base=2)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xticks(ticks)
        ax.set_xlabel(xlabel, color=INK2, fontsize=10.5)
        ax.set_ylabel(ylabel, color=INK2, fontsize=10.5)

    os.makedirs(out, exist_ok=True)
    for spec in specs:
        f, ax = plt.subplots(figsize=(5.4, 3.9), dpi=200)
        f.patch.set_facecolor(SURFACE)
        draw(ax, spec)
        ax.legend(frameon=False, fontsize=9, loc="best")
        f.tight_layout()
        for ext in ("png", "pdf"):
            f.savefig(os.path.join(out, f"{spec[1]}.{ext}"), facecolor=SURFACE, dpi=200)
        plt.close(f)
        print("->", os.path.relpath(os.path.join(out, spec[1] + ".png")))
    before = len(P.POINTS)
    f, axes = plt.subplots(1, 3, figsize=(15.0, 4.3), dpi=200)
    f.patch.set_facecolor(SURFACE)
    for ax, spec in zip(axes, specs):
        draw(ax, spec)
        ax.text(0.5, -0.24, f"({spec[0]})", transform=ax.transAxes, ha="center", va="top", fontsize=11.5,
                color=INK2)
    del P.POINTS[before:]
    handles, labels = axes[0].get_legend_handles_labels()
    f.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 1.0))
    f.tight_layout(rect=(0, 0, 1, 0.9))
    for ext in ("png", "pdf"):
        f.savefig(os.path.join(out, f"exp1_search_3.{ext}"), facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(os.path.join(out, "exp1_search_3.png")))


def final_set(out, data, no_fetch, n_fix, kqs_single):
    """The four Exp. 1 figures of the paper, each alone (legend inside) and all four as one 2 x 2 figure:
    (a) single domain, search only (no proof, no fetch) vs kQ   (b) single domain, end-to-end vs kQ
    (c) multi-domain AND-of-OR, end-to-end vs kQ                (d) multi-domain OR-of-AND, end-to-end vs kQ"""
    kqs_multi = sorted({int(r["kQ"]) for r in rows(data, "amtp", "search_multi")})
    single = lambda r: int(r["N"]) == n_fix                                          # noqa: E731
    specs = [
        ("a", "exp1_a_single_search_vs_kQ", "search_single", single, ORDER, "search", kqs_single, False,
         "Keywords in the AND query $k_Q$"),
        ("b", "exp1_b_single_end_to_end_vs_kQ", "search_single", single, ORDER, "end_to_end", kqs_single, False,
         "Keywords in the AND query $k_Q$"),
        ("c", "exp1_c_multi_AND_of_OR_end_to_end_vs_kQ", "search_multi", lambda r: r["shape"] == "AND_of_OR",
         ("amtp", "secollab"), "end_to_end", kqs_multi, True, "Keywords in $(A \\vee B) \\wedge (C \\vee D) \\dots$"),
        ("d", "exp1_d_multi_OR_of_AND_end_to_end_vs_kQ", "search_multi", lambda r: r["shape"] == "OR_of_AND",
         ("amtp", "secollab"), "end_to_end", kqs_multi, True, "Keywords in $(A \\wedge B) \\vee (C \\wedge D) \\dots$"),
    ]

    def draw(ax, spec):
        letter, _, suite, keep, schemes, m, ticks, log2, xlabel = spec
        ylabel, col, nf = MEASURES[m]
        style(ax)
        for s in schemes:
            src = no_fetch if (nf and s in FROM_NO_FETCH) else data
            rs = [r for r in rows(src, s, suite) if keep(r)]
            P.scheme_line(ax, f"Exp1_{letter}", s, P.agg(rs, lambda r: int(r["kQ"]), col(s) + "_ms_median"))
        plain_log_y(ax)
        if log2:
            ax.set_xscale("log", base=2)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xticks(ticks)
        ax.set_xlabel(xlabel, color=INK2, fontsize=10.5)
        ax.set_ylabel(ylabel, color=INK2, fontsize=10.5)

    os.makedirs(out, exist_ok=True)
    for spec in specs:                                      # one file per figure, legend inside
        f, ax = plt.subplots(figsize=(5.4, 3.9), dpi=200)
        f.patch.set_facecolor(SURFACE)
        draw(ax, spec)
        ax.legend(frameon=False, fontsize=9, loc="best")
        f.tight_layout()
        for ext in ("png", "pdf"):
            f.savefig(os.path.join(out, f"{spec[1]}.{ext}"), facecolor=SURFACE, dpi=200)
        plt.close(f)
        print("->", os.path.relpath(os.path.join(out, spec[1] + ".png")))
    before = len(P.POINTS)
    f, axes = plt.subplots(2, 2, figsize=(10.8, 8.0), dpi=200)  # all four, one legend on top
    f.patch.set_facecolor(SURFACE)
    for ax, spec in zip(axes.flat, specs):
        draw(ax, spec)
        ax.text(0.5, -0.2, f"({spec[0]})", transform=ax.transAxes, ha="center", va="top", fontsize=11.5,
                color=INK2)
    del P.POINTS[before:]                                   # same points as the single files: not written twice
    handles, labels = axes[0][0].get_legend_handles_labels()
    f.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 1.0))
    f.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ("png", "pdf"):
        f.savefig(os.path.join(out, f"exp1_all_4.{ext}"), facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(os.path.join(out, "exp1_all_4.png")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="folder with amtp/, chen/, secollab/, du/ (same round)")
    ap.add_argument("--no-fetch", required=True, help="folder with secollab/, du/ re-runs with search_no_fetch")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    amtp = rows(a.data, "amtp", "search_single")
    ns = sorted({int(r["N"]) for r in amtp})
    by_n = {n: sorted({int(r["kQ"]) for r in amtp if int(r["N"]) == n}) for n in ns}
    n_fix = max(ns, key=lambda n: (len(by_n[n]), n))
    kq_fix = max({int(r["kQ"]) for r in amtp}, key=lambda k: (sum(1 for n in ns if k in by_n[n]), -k))
    pair("S1.1", os.path.join(a.out, "search_1_1_vs_kQ"), a.data, a.no_fetch, "search_single",
         lambda r: int(r["N"]) == n_fix, lambda r: int(r["kQ"]), "Keywords in the AND query $k_Q$", by_n[n_fix])
    pair("S1.2", os.path.join(a.out, "search_1_2_vs_files"), a.data, a.no_fetch, "search_single",
         lambda r: int(r["kQ"]) == kq_fix, lambda r: int(r["N"]), "Documents in the domain", ns, k_label=True)
    nested = ("AND_of_OR", "OR_of_AND")           # the paper shows the two nested shapes only
    boolean(os.path.join(a.out, "search_2_1_nested_end_to_end_vs_kQ"), a.data, a.no_fetch, ["end_to_end"], nested)
    boolean(os.path.join(a.out, "search_2_1_nested_search_vs_kQ"), a.data, a.no_fetch, ["search"], nested)
    boolean(os.path.join(a.out, "search_2_1_nested_vs_kQ"), a.data, a.no_fetch, ["search", "end_to_end"], nested)
    boolean(os.path.join(a.out, "search_2_1_nested_server_vs_kQ"), a.data, a.no_fetch, ["server"], nested)
    single = os.path.join(a.out, "single")             # one shape, one measure per file
    os.makedirs(single, exist_ok=True)
    for shape in nested:
        for m in ("search", "server", "end_to_end"):
            boolean(os.path.join(single, f"search_2_1_{shape}_{m}_vs_kQ"), a.data, a.no_fetch, [m], (shape,))
    final_set(os.path.join(a.out, "final"), a.data, a.no_fetch, n_fix, by_n[n_fix])
    search_set(os.path.join(a.out, "final_search"), a.data, a.no_fetch, n_fix, by_n[n_fix])
    path = os.path.join(a.out, "figure_points.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["figure", "series", "x", "y", "err_down", "err_up"])
        w.writeheader()
        w.writerows(P.POINTS)
    print(f"{len(P.POINTS)} points -> {os.path.relpath(path)}  (S1.1: N = {n_fix:,}; S1.2: kQ = {kq_fix})")


if __name__ == "__main__":
    main()
