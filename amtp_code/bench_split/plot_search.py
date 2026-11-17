"""Search-only figures (line charts) from a bench_split run, next to the baselines' own search time.

    python -m bench_split.plot_search --amtp <run>/amtp --out ../baselines/results/search_split/graphs
        [--base ../baselines/results/new_amtp_result/gamma_with_v]   # SE-COLLAB, Chen, Du (not re-run)

y = server search time without any proof (ms), per scheme:
    AMTP                 server_search_pf(_fetch)   lookup + boolean.focus (partitions that can match) + file sets in
                                                    those partitions + Boolean evaluation (+ fetch); only the server's
                                                    own structures (the search-index form is not plotted)
    SE-COLLAB            search_core                BPL retrieval + Boolean evaluation + result fetch (its own split)
    Chen, Du             server_total               their server does only the search (Du: the slowest cloud)
Single-domain figures: *_no_fetch (AMTP vs Chen) and *_with_fetch (AMTP vs SE-COLLAB, Du); see NO_FETCH / WITH_FETCH.
One more figure per suite shows AMTP's server time split: search only vs the whole server time (search + proof).
Uses the drawing helpers of baselines/plot_paper.py (unchanged). Every plotted number goes to figure_points.csv.
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINES = os.path.normpath(os.path.join(HERE, "..", "..", "baselines"))
sys.path.insert(0, BASELINES)
import plot_paper as P  # noqa: E402

# partition first (boolean.focus). Fetch decides the pairing: SE-COLLAB's search_core and Du's server_total return
# the matching files, Chen returns only an encrypted bitmap. Single-domain figures come in two forms:
#   *_no_fetch    AMTP server_search_pf        vs Chen
#   *_with_fetch  AMTP server_search_pf_fetch  vs SE-COLLAB, Du
# Multi-domain figures (SE-COLLAB only) use the with-fetch form.
NO_FETCH = ("server_search_pf", "AMTP (no fetch)", ("chen",))
WITH_FETCH = ("server_search_pf_fetch", "AMTP (+ fetch)", ("secollab", "du"))
BASE_COL = {"secollab": "search_core", "chen": "server_total", "du": "server_total"}
# one figure with every scheme: both AMTP lines, each labelled with the baselines it is read against
ALL_LINES = (("server_search_pf", "AMTP, no fetch (vs Chen)", "-"),
             ("server_search_pf_fetch", "AMTP + fetch (vs SE-COLLAB, Du)", "--"))
YLABEL = "Server search time, without proof (ms)"


def rows_of(folder, scheme, suite):
    path = os.path.join(folder, f"{scheme}_{suite}.csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status", "ok") == "ok"]


def draw(fig_id, ax, amtp, base, key, form=WITH_FETCH):
    col, label, schemes = form
    color, marker = P.STYLE["amtp"]
    P.line(ax, fig_id, P.agg(amtp, key, col + "_ms_median"), label, color, marker)
    for s, rs in base.items():
        if s in schemes:
            P.scheme_line(ax, fig_id, s, P.agg(rs, key, BASE_COL[s] + "_ms_median"))


def draw_all(fig_id, ax, amtp, base, key):
    color, marker = P.STYLE["amtp"]
    for col, label, ls in ALL_LINES:
        P.line(ax, fig_id, P.agg(amtp, key, col + "_ms_median"), label, color, marker, ls)
    for s, rs in base.items():
        P.scheme_line(ax, fig_id, s, P.agg(rs, key, BASE_COL[s] + "_ms_median"))
    ax.set_yscale("log")                     # room above the lines for the five-entry legend
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi * 6)


def split_fig(fig_id, path, title, fixed, xlabel, amtp, key, ticks, log_x=False):
    """AMTP only: search (index) vs the whole server time (search + proof)."""
    f, ax = P.fig()
    color, marker = P.STYLE["amtp"]
    P.line(ax, fig_id, P.agg(amtp, key, "server_total_ms_median"), "AMTP server: search + proof", color, marker)
    P.line(ax, fig_id, P.agg(amtp, key, "server_search_pf_fetch_ms_median"), "AMTP server: search only (+ fetch)",
           color, marker, "--")
    P.save(f, ax, path, title, fixed, xlabel, "Server time (ms)", log_x=log_x, ticks=ticks)


def search1(amtp_dir, base_dir, out):
    amtp = rows_of(amtp_dir, "amtp", "search_single")
    if not amtp or "server_search_fetch_ms_median" not in amtp[0]:
        return
    base = {s: rows for s in BASE_COL if (rows := rows_of(os.path.join(base_dir, s), s, "search_single"))}
    ns = sorted({int(r["N"]) for r in amtp})
    by_n = {n: {int(r["kQ"]) for r in amtp if int(r["N"]) == n} for n in ns}
    n_fix = max(ns, key=lambda n: (len(by_n[n]), n))
    kq_fix = max(sorted({int(r["kQ"]) for r in amtp}), key=lambda k: (sum(1 for n in ns if k in by_n[n]), -k))
    doms = P.one([r["domain"] for r in amtp], "domain")
    at_n = lambda rs: [r for r in rs if int(r["N"]) == n_fix]                         # noqa: E731
    at_k = lambda rs: [r for r in rs if int(r["kQ"]) == kq_fix]                       # noqa: E731
    for form, tag, what, who in ((NO_FETCH, "no_fetch", "no fetch", "Chen returns no files"),
                                 (WITH_FETCH, "with_fetch", "with fetch", "SE-COLLAB and Du return the files")):
        f, ax = P.fig()
        draw(f"S1.1_search_only_{tag}", ax, at_n(amtp), {s: at_n(r) for s, r in base.items()},
             lambda r: int(r["kQ"]), form)
        P.save(f, ax, os.path.join(out, "Search_1.1", f"search_only_vs_kQ_{tag}"),
               f"Search 1.1 · single domain · vary keywords · {what}",
               f"{n_fix:,} files per domain · AND · median over {doms} · {who}",
               "Keywords in the AND query $k_Q$", YLABEL, ticks=sorted(by_n[n_fix]))
        if len(ns) > 1:
            f, ax = P.fig()
            draw(f"S1.2_search_only_{tag}", ax, at_k(amtp), {s: at_k(r) for s, r in base.items()},
                 lambda r: int(r["N"]), form)
            P.save(f, ax, os.path.join(out, "Search_1.2", f"search_only_vs_files_{tag}"),
                   f"Search 1.2 · single domain · vary files · {what}",
                   f"$k_Q$ = {kq_fix} · AND · median over {doms} · {who}", "Files in the domain", YLABEL,
                   log_x=True, ticks=ns)
    f, ax = P.fig()
    draw_all("S1.1_search_only_all", ax, at_n(amtp), {s: at_n(r) for s, r in base.items()}, lambda r: int(r["kQ"]))
    P.save(f, ax, os.path.join(out, "Search_1.1", "search_only_vs_kQ_all"),
           "Search 1.1 · single domain · vary keywords · all schemes",
           f"{n_fix:,} files per domain · AND · median over {doms} · Chen returns no files",
           "Keywords in the AND query $k_Q$", YLABEL, ticks=sorted(by_n[n_fix]))
    if len(ns) > 1:
        f, ax = P.fig()
        draw_all("S1.2_search_only_all", ax, at_k(amtp), {s: at_k(r) for s, r in base.items()}, lambda r: int(r["N"]))
        P.save(f, ax, os.path.join(out, "Search_1.2", "search_only_vs_files_all"),
               "Search 1.2 · single domain · vary files · all schemes",
               f"$k_Q$ = {kq_fix} · AND · median over {doms} · Chen returns no files", "Files in the domain",
               YLABEL, log_x=True, ticks=ns)
    split_fig("S1.1_amtp_split", os.path.join(out, "Search_1.1", "amtp_search_vs_server_vs_kQ"),
              "Search 1.1 · AMTP server time split", f"{n_fix:,} files per domain · AND query · domains {doms}",
              "Keywords in the AND query $k_Q$", at_n(amtp), lambda r: int(r["kQ"]), sorted(by_n[n_fix]))


def search21(amtp_dir, base_dir, out):
    amtp = rows_of(amtp_dir, "amtp", "search_multi")
    if not amtp or "server_search_fetch_ms_median" not in amtp[0]:
        return
    se = rows_of(os.path.join(base_dir, "secollab"), "secollab", "search_multi")
    nfix = P.one([int(r["N_per_domain"]) for r in amtp], "N")
    dcount = P.one([int(r["domains"]) for r in amtp], "D")
    for shape in [s for s in P.SHAPES if any(r["shape"] == s for r in amtp)]:
        a = [r for r in amtp if r["shape"] == shape]
        kqs = sorted({int(r["kQ"]) for r in a})
        f, ax = P.fig()
        draw(f"S2.1_{shape}_search_only", ax, a, {"secollab": [r for r in se if r["shape"] == shape]} if se else {},
             lambda r: int(r["kQ"]))
        P.save(f, ax, os.path.join(out, "Search_2.1", f"search_only_vs_kQ_{shape}"),
               f"Search 2.1 · multi-domain · {P.SHAPES[shape]}",
               f"{dcount} domains · {nfix} files per domain · query shape {shape}", "Keywords in the query $k_Q$",
               YLABEL, ticks=kqs)


def search22(amtp_dir, base_dir, out):
    amtp = rows_of(amtp_dir, "amtp", "domains_scaling")
    if not amtp or "server_search_fetch_ms_median" not in amtp[0]:
        return
    se = rows_of(os.path.join(base_dir, "secollab"), "secollab", "domains_scaling")
    ds = sorted({int(r["domains"]) for r in amtp})
    fixed = (f"{P.one([int(r['N_total']) for r in amtp], 'N')} files in total · "
             f"$k_Q$ = {P.one([int(r['kQ']) for r in amtp], 'kQ')} · shape {P.one([r['shape'] for r in amtp], 's')}")
    f, ax = P.fig()
    draw("S2.2_search_only", ax, amtp, {"secollab": se} if se else {}, lambda r: int(r["domains"]))
    P.save(f, ax, os.path.join(out, "Search_2.2", "search_only_vs_domains"), "Search 2.2 · multi-domain · vary domains",
           fixed, "Number of domains D", YLABEL, log_x=True, ticks=ds)


def exp5(amtp_dir, base_dir, out):
    """Exp. 5: one domain queried while the system holds D domains (search only, query rows)."""
    amtp = [r for r in rows_of(amtp_dir, "amtp", "exp5_domains") if r.get("op") == "query"]
    if not amtp or "server_search_fetch_ms_median" not in amtp[0]:
        return
    se = [r for r in rows_of(os.path.join(base_dir, "secollab"), "secollab", "exp5_domains") if r.get("op") == "query"]
    ds = sorted({int(r["domains"]) for r in amtp})
    f, ax = P.fig()
    draw("E5_search_only", ax, amtp, {"secollab": se} if se else {}, lambda r: int(r["domains"]))
    P.save(f, ax, os.path.join(out, "Exp5", "search_only_vs_domains"), "Exp 5 · query one domain · vary domains",
           f"{P.one([int(r['N_target']) for r in amtp], 'N')} files in the queried domain · exp5 workload",
           "Domains in the system D", YLABEL, log_x=True, ticks=ds)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amtp", required=True, help="folder with amtp_search_single.csv etc. of a bench_split run")
    ap.add_argument("--base", default=os.path.join(BASELINES, "results", "new_amtp_result", "gamma_with_v"),
                    help="folder with secollab/, chen/, du/ results (default: gamma_with_v, not re-run)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    search1(a.amtp, a.base, a.out)
    search21(a.amtp, a.base, a.out)
    search22(a.amtp, a.base, a.out)
    exp5(a.amtp, a.base, a.out)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "figure_points.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["figure", "series", "x", "y", "err_down", "err_up"])
        w.writeheader()
        w.writerows(P.POINTS)
    print(f"{len(P.POINTS)} points -> {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
