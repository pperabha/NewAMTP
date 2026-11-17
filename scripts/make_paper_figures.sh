#!/usr/bin/env bash
# Rebuild Figs. 3-10 of the paper from the result files stored in this repository (no experiment is re-run).
#
#   bash scripts/make_paper_figures.sh                 # -> baselines/results/paper_figures/
#   OUT=/tmp/figs bash scripts/make_paper_figures.sh   # another output folder
#
# The final PDFs are copied to $OUT/paper/fig03.pdf ... fig10.pdf with the paper's figure numbers.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
R=baselines/results
OUT=${OUT:-$R/paper_figures}
mkdir -p "$OUT/paper"

echo "== Experiment 1 (Figs. 3-5): server search time"
"$PY" baselines/plot_exp1.py --data $R/part_leaf/data --no-fetch $R/part_leaf/data_no_fetch --out "$OUT/exp1"
echo "== Experiment 2 (Figs. 6-8): tamper detection and user verification"
"$PY" baselines/plot_exp2.py --data $R/part_leaf/data --out "$OUT/exp2"
echo "== Experiment 3 (Fig. 9): ablation of adaptive partitioning (update cost)"
"$PY" baselines/plot_exp4.py --runs $R/runs/cloud --out "$OUT/exp3"
echo "== Experiment 4 (Fig. 10): multi-domain scalability"
"$PY" baselines/plot_exp5.py --data $R/part_leaf/data --no-fetch $R/part_leaf/data_no_fetch --out "$OUT/exp4"

cp "$OUT/exp1/final_search/exp1_a_single_search_vs_kQ.pdf"          "$OUT/paper/fig03.pdf"
cp "$OUT/exp1/final_search/exp1_b_multi_AND_of_OR_search_vs_kQ.pdf" "$OUT/paper/fig04.pdf"
cp "$OUT/exp1/final_search/exp1_c_multi_OR_of_AND_search_vs_kQ.pdf" "$OUT/paper/fig05.pdf"
cp "$OUT/exp2/exp2_a2_attack_types_detected.pdf"                    "$OUT/paper/fig06.pdf"
cp "$OUT/exp2/exp2_b_single_verify_vs_results.pdf"                  "$OUT/paper/fig07.pdf"
cp "$OUT/exp2/exp2_c_multi_verify_vs_results.pdf"                   "$OUT/paper/fig08.pdf"
cp "$OUT/exp3/exp4_a_update_vs_batch.pdf"                           "$OUT/paper/fig09.pdf"
cp "$OUT/exp4/exp5_search_vs_domains.pdf"                           "$OUT/paper/fig10.pdf"
echo "Figs. 3-10 -> $OUT/paper/"
