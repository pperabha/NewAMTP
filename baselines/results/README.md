# Results

```
results/
  paper32/                  every result behind paper (32) (24-page AMTP (36) and the 6-page version)
    data/<run>/<scheme>/    one folder per AWS run (table in ../../README.md, section 4): <scheme>_<suite>.csv
                            + .manifest.json (command, commit, machine, crypto and anchor settings)
    figures/                all figures (baselines/plot_p32.py), figure_points.csv, README.md (data + note)
    FIGURES.md              every figure with where AMTP wins and loses (baselines/figure_catalog.py)
    paper_figures/          the figures used in the paper (+ paper_figures.zip for Overleaf)
  abs/                      ABS cost table (amtp_code/bench/abs_bench.py, AWS r7i.4xlarge)
  cpabe/                    CP-ABE cost table
  paper/                    the earlier course version (CSS453, 17 Nov): Figs. 3-10 (scripts/make_paper_figures.sh)
  runs/cloud/               raw copies of every AWS run of paper (32), with logs and the aborted runs
  exp1_queries.json         shared query file of the earlier Experiment 1, replayed by every scheme
  exp2_layouts.json         shared marker-keyword layouts of Exp. 2 (clustered / dispersed / partition spread, N = 100k)
  exp5_workload.json        shared workload of Exp. 5 (32 domains x 5,000 files, queries, update files)
  runs/<run>/               new runs of scripts/aws_run_all.sh
```

Suite names in the CSVs:
- Exp. 1 and 2 over D = 1–32: `domains_scaling`; Exp. 1: `search_single`, `search_multi`.
- Exp. 2: `verify_single`, `verify_multi`, `tamper_detection`, `exp2_selective_proof`.
- Exp. 3: `exp3_dynamic_update`.
- Exp. 5: `exp5_domains`, and Du et al.'s clouds `clouds_sensitivity`.
- Exp. 4, AMTP through the full protocol: `skew_protocol`.

Exp. 4 at index level writes `updates.csv`, `layout.csv`, `queries.csv` and `summary.md` per job folder
(`ex4_w<k>_skew<s>/<job>/amtp/splitmerge_n25000_t64/`).
