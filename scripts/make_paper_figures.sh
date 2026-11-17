#!/usr/bin/env bash
# Rebuild Figs. 3-10 of the paper from the result files in baselines/results/paper/ (no experiment is re-run).
#
#   bash scripts/make_paper_figures.sh                 # -> baselines/results/paper/figures/fig03.pdf ... fig10.pdf
#   OUT=/tmp/figs bash scripts/make_paper_figures.sh   # another output folder
#
# Every plotting script also writes figure_points.csv (every plotted number) and extra views into $OUT/build/.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
D=baselines/results/paper
OUT=${OUT:-$D/figures}
B=$OUT/build
mkdir -p "$B"

echo "== Experiment 1 (Figs. 3-5): server search time"
"$PY" baselines/plot_exp1.py --data $D/data --no-fetch $D/data_no_fetch --out "$B/exp1"
echo "== Experiment 2 (Figs. 6-8): tamper detection and user verification"
"$PY" baselines/plot_exp2.py --data $D/data --out "$B/exp2"
echo "== Experiment 3 (Fig. 9): ablation of adaptive partitioning (update cost)"
"$PY" baselines/plot_exp3.py --data $D/ablation --out "$B/exp3"
echo "== Experiment 4 (Fig. 10): multi-domain scalability"
"$PY" baselines/plot_exp4.py --data $D/data --no-fetch $D/data_no_fetch --out "$B/exp4"

copy() { for ext in pdf png; do cp "$1.$ext" "$OUT/$2.$ext"; done; }
copy "$B/exp1/final_search/exp1_a_single_search_vs_kQ"          fig03
copy "$B/exp1/final_search/exp1_b_multi_AND_of_OR_search_vs_kQ" fig04
copy "$B/exp1/final_search/exp1_c_multi_OR_of_AND_search_vs_kQ" fig05
copy "$B/exp2/exp2_a2_attack_types_detected"                    fig06
copy "$B/exp2/exp2_b_single_verify_vs_results"                  fig07
copy "$B/exp2/exp2_c_multi_verify_vs_results"                   fig08
copy "$B/exp3/exp3_a_update_vs_batch"                           fig09
copy "$B/exp4/exp4_search_vs_domains"                           fig10
echo "Figs. 3-10 -> $OUT/"
