"""
figure_catalog.py
============================================================================
Write a browsable catalog of every paper (32) figure: the picture, which paper version uses it, its data and
fairness note (from the README that plot_p32.py writes), and a one-line comparison per baseline computed from
figure_points.csv (where AMTP is better, where the baseline is better, by how much). Nothing is re-measured.

  .venv/bin/python baselines/figure_catalog.py            # -> baselines/results/paper32/FIGURES.md

Comparison rule: for a time, size, gas or partition-size figure lower is better; for throughput, detection rate
and attack types detected higher is better. Two values within 2% count as a tie. A query-level point is the median
over the queries of that x (as plotted), so the factors are factors between medians.
============================================================================
"""
import argparse
import csv
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "results" / "paper32"

# Which figure files each paper version uses (24 pages: AMTP (36); 6 pages: the conference draft, 19-20 Nov 2026).
IN_PAPER = {
    "e1_single_kq_search": "24 p.: Fig. 3 · 6 p.: Fig. 3",
    "e1_multi_AND_of_OR_search": "24 p.: Fig. 4",
    "e1_multi_OR_of_AND_search": "24 p.: Fig. 4 · 6 p.: Fig. 4",
    "e2_single_verify_verify": "24 p.: Fig. 5(a) · 6 p.: Fig. 5",
    "e2_multi_verify_verify": "24 p.: Fig. 5(b)",
    "e2_tamper_attack_types": "24 p.: Fig. 5(c) · 6 p.: Table III (as a table)",
    "e4_batches_skew0.95": "24 p.: Fig. 6 · 6 p.: Fig. 6",
    "e5_query_e2e": "24 p.: Fig. 7",
    "e2_layouts_proof_kb": "extra, on hold (owner asks the advisor)",
    "e3_b_breakdown_insert": "extra, on hold (owner asks the advisor)",
}

EXPERIMENTS = [
    ("e1", "Experiment 1: Boolean search scalability"),
    ("e2", "Experiment 2: selective proof, verification and tamper detection"),
    ("e3", "Experiment 3: dynamic update scalability"),
    ("e4", "Experiment 4: adaptive partitioning under skewed growth (ablation)"),
    ("e5", "Experiment 5: multi-domain scalability and isolation"),
]

HIGHER_BETTER = ("throughput", "detection", "attack_types")


def x_name(fig):
    for pre, name in (("e1_single_kq", "kQ"), ("e1_single_n", "N"), ("e1_multi", "kQ"), ("e1_domains", "D"),
                      ("e2_layout", "rQ"), ("e2_single_verify", "rQ"), ("e2_multi_verify", "rQ"),
                      ("e2_tamper", "t"), ("e3_b", "b"), ("e3_n", "N"), ("e4_batches", "batch"), ("e4", "skew"),
                      ("e5_sepolia", "D"), ("e5", "D")):
        if fig.startswith(pre):
            return name
    return "x"


def plural(name):
    return name + ("es" if name.endswith(("ch", "s", "x")) else "s")


def unit(fig):
    for key, u in (("e4_batches", "s"), ("_kb", "KB"), ("gas", "gas"), ("throughput", "requests/s"),
                   ("detection", "% detected"), ("attack_types", "attack types of 4"), ("false_alarms", "% false alarms"),
                   ("max_partition", "live entries"), ("splits_merges", "splits + merges per run")):
        if key in fig:
            return u
    return "ms"


def num(v):
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.1f}"
    if a >= 1:
        return f"{v:.2f}"
    return f"{v:.3g}"


def fx(x):
    try:
        f = float(x)
    except ValueError:
        return x
    if f.is_integer():
        return f"{int(f):,}"
    return f"{f:g}"


def factor_range(fs):
    lo, hi = min(fs), max(fs)
    return f"{lo:.2f}×" if abs(hi - lo) < 0.005 else f"{lo:.2f}–{hi:.2f}×"


def compare(fig, a, b, bname):
    """a, b: OrderedDict x -> y. Returns one line: where AMTP / the baseline is better and by how much."""
    hb = any(k in fig for k in HIGHER_BETTER)
    better, worse, tie = [], [], []
    for x, ya in a.items():
        if x not in b:
            continue
        yb = b[x]
        if ya == yb:
            tie.append(x)
            continue
        if hb:
            if yb == 0 or ya == 0:
                (better if ya > yb else worse).append((x, None))
                continue
            r = ya / yb
        else:
            if ya == 0 or yb == 0:
                (better if ya < yb else worse).append((x, None))
                continue
            r = yb / ya
        if abs(r - 1) <= 0.02:
            tie.append(x)
        elif r > 1:
            better.append((x, r))
        else:
            worse.append((x, 1 / r))
    n = len(better) + len(worse) + len(tie)
    many = n > 12
    parts = []
    for label, pts in (("AMTP better", better), (f"{bname} better", worse)):
        if not pts:
            continue
        fs = [r for _, r in pts if r is not None]
        where = f"{len(pts)} of {n} {plural(x_name(fig))}" if many else f"{x_name(fig)} = " + ", ".join(fx(x) for x, _ in pts)
        parts.append(f"{label} at {where}" + (f" ({factor_range(fs)})" if fs else " (other side 0)"))
    if tie:
        parts.append(f"tie at {len(tie)} of {n}" if many else f"tie at {x_name(fig)} = " + ", ".join(fx(x) for x in tie))
    if many:
        ma, mb = sum(a.values()) / len(a), sum(b[x] for x in a if x in b) / max(1, sum(1 for x in a if x in b))
        parts.append(f"mean over all {plural(x_name(fig))}: AMTP {num(ma)} vs {num(mb)} {unit(fig)}")
    return f"**vs {bname}:** " + "; ".join(parts) if parts else f"**vs {bname}:** no common points"


def pairs(fig, series):
    names = list(series)
    if any(s.startswith("AMTP (") and s != "AMTP (Sepolia)" for s in names):          # e2_layouts_*: per layout
        out = []
        for s in names:
            m = re.match(r"AMTP \((.+)\)$", s)
            if m:
                other = next((t for t in names if t != s and t.endswith(f"({m.group(1)})")), None)
                if other:
                    out.append((s, other))
        return out
    if any(s.startswith("AMTP insert") for s in names):                               # e3: insert vs insert
        return [(s, t) for s in names if s.startswith("AMTP ")
                for t in names if not t.startswith("AMTP") and t.split()[-1] == s.split()[-1]]
    if "AMTP" in names:
        return [("AMTP", t) for t in names if t != "AMTP"]
    return []


def load_notes(readme):
    notes = {}
    if readme.exists():
        for line in readme.read_text().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 3 and re.match(r"e\d_", cells[0]):
                notes[cells[0]] = (cells[1], cells[2].lstrip("; ").strip())
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures", default=str(ROOT / "figures"))
    ap.add_argument("--out", default=str(ROOT / "FIGURES.md"))
    args = ap.parse_args()
    figdir, out = Path(args.figures), Path(args.out)
    data = OrderedDict()
    with open(figdir / "figure_points.csv") as f:
        for r in csv.DictReader(f):
            data.setdefault(r["figure"], OrderedDict()).setdefault(r["series"], OrderedDict())[r["x"]] = float(r["y"])
    notes = load_notes(figdir / "README.md")
    rel = Path(".") if figdir.parent == out.parent else None
    link = (lambda n: f"{figdir.name}/{n}") if rel is not None else (lambda n: str(figdir / n))

    L = ["# Paper (32): every figure, with where AMTP wins and loses",
         "",
         f"Generated by `baselines/figure_catalog.py` from `{figdir.name}/figure_points.csv` (no number is typed by hand).",
         "Figures are built by `baselines/plot_p32.py` (line charts, png + pdf). Every timing is the mean of 10 runs after",
         "3 warm-up runs; a query-level point is the median over the queries of that x, with interquartile-range bars;",
         "Exp. 3, Exp. 4, update isolation and Sepolia points are means over runs / batches / updates.",
         "",
         "Each comparison line says at which x AMTP is better and at which the baseline is better, with the factor",
         "(how many times better). Lower is better for times, sizes, gas and partition sizes; higher is better for",
         "throughput, detection rate and attack types detected. Within 2% = tie.",
         "",
         "**In paper:** `24 p.` = the 24-page version AMTP (36); `6 p.` = the 6-page conference draft. A figure with no",
         "tag is in neither version (some of its numbers may be quoted in the text).",
         ""]
    L.append("Contents: " + " · ".join(f"[Exp. {k[1]}](#{t.lower().replace(' ', '-').replace(':', '').replace(',', '').replace('(', '').replace(')', '')})"
                                       for k, t in EXPERIMENTS))
    L.append("")
    for key, title in EXPERIMENTS:
        figs = [f for f in data if f.startswith(key + "_")]
        if not figs:
            continue
        L += [f"## {title}", ""]
        for fig in figs:
            series = data[fig]
            L.append(f"### `{fig}`" + (f" ({IN_PAPER[fig]})" if fig in IN_PAPER else ""))
            L.append("")
            if (figdir / f"{fig}.png").exists():
                L.append(f'<img src="{link(fig + ".png")}" width="520" alt="{fig}">')
                L.append("")
            src, note = notes.get(fig, ("", ""))
            if src:
                L.append(f"Data: `{src.replace('<data>/', 'data/')}`" + (f". {note}" if note else ""))
                L.append("")
            ps = pairs(fig, series)
            if ps:
                for s, t in ps:
                    line = compare(fig, series[s], series[t], t)
                    if s != "AMTP":
                        line = line.replace("**vs ", f"**{s} vs ", 1).replace("AMTP better", f"{s} better")
                    L.append(f"- {line}")
            for s, pts in series.items():
                vals = list(pts.values())
                if not ps or s.startswith("AMTP"):
                    L.append(f"- {s}: {num(min(vals))}–{num(max(vals))} {unit(fig)}"
                             + (f" over {x_name(fig)} = {fx(next(iter(pts)))}…{fx(list(pts)[-1])}" if len(pts) > 1 else ""))
            L.append("")
    out.write_text("\n".join(L) + "\n")
    print(f"{out}: {len(data)} figures")


if __name__ == "__main__":
    main()
