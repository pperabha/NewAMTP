"""
plot_exp5.py
============================================================================
Exp. 5 for the paper: server search time in the queried domain as the number of domains in the system grows.
Same style as plot_exp1.py (no title, the caption is in LaTeX, plain log-y labels, png + pdf).

  .venv/bin/python baselines/plot_exp5.py --data baselines/results/part_leaf/data \
      --no-fetch baselines/results/part_leaf/data_no_fetch --out baselines/results/part_leaf/graphs/exp5

  exp5_search_vs_domains   AMTP server_search_pf vs SE-COLLAB search_no_fetch, op = query rows of exp5_domains
                           (queried domain fixed; every point is the median over the Exp. 5 queries)

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
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402
from plot_exp1 import plain_log_y, rows, style  # noqa: E402
from plot_results import INK2, SURFACE, plt  # noqa: E402

NAME = "exp5_search_vs_domains"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="part_leaf/data (AMTP)")
    ap.add_argument("--no-fetch", required=True, help="part_leaf/data_no_fetch (SE-COLLAB search_no_fetch)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    query = lambda rs: [r for r in rs if r.get("op") == "query"]                    # noqa: E731
    amtp = query(rows(a.data, "amtp", "exp5_domains"))
    se = query(rows(a.no_fetch, "secollab", "exp5_domains"))
    if not se or "search_no_fetch_ms_median" not in se[0]:
        raise SystemExit("secollab_exp5_domains: no search_no_fetch column")
    key = lambda r: int(r["domains"])                                               # noqa: E731
    ds = sorted({key(r) for r in amtp})

    f, ax = plt.subplots(figsize=(5.4, 3.9), dpi=200)
    f.patch.set_facecolor(SURFACE)
    style(ax)
    P.scheme_line(ax, "Exp5", "amtp", P.agg(amtp, key, "server_search_pf_ms_median"))
    P.scheme_line(ax, "Exp5", "secollab", P.agg(se, key, "search_no_fetch_ms_median"))
    plain_log_y(ax)
    ax.set_yticks([0.02, 0.03, 0.04, 0.05, 0.07, 0.1])          # narrow range: 1-2-5 ticks alone give only two labels
    ax.set_ylim(0.018, 0.13)
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks(ds)
    ax.set_xlabel("Domains in the system $D$", color=INK2, fontsize=10.5)
    ax.set_ylabel("Server search time (ms)", color=INK2, fontsize=10.5)
    ax.legend(frameon=False, fontsize=9, loc="upper center", ncol=2)   # above both lines, clear of error bars
    f.tight_layout()
    for ext in ("png", "pdf"):
        f.savefig(os.path.join(a.out, f"{NAME}.{ext}"), facecolor=SURFACE, dpi=200)
    plt.close(f)
    print("->", os.path.relpath(os.path.join(a.out, NAME + ".png")))

    path = os.path.join(a.out, "figure_points.csv")
    with open(path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=list(P.POINTS[0].keys()))
        w.writeheader()
        w.writerows(P.POINTS)
    print(f"{len(P.POINTS)} points -> {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
