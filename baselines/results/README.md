# Results

```
results/
  paper/                    every result behind the paper (see the table in ../../README.md, section 4)
    data/<scheme>/          AMTP, Chen et al., Du et al., SE-COLLAB: <scheme>_<suite>.csv + .manifest.json
    data_no_fetch/          SE-COLLAB and Du et al. search-only re-runs (search without returning ciphertexts)
    ablation/               Experiment 3: amtp_static_t64/ (AMTP, Static-MT), global_mt_v_t64/ (Global-MT(v))
    figures/                fig03 ... fig10 of the paper (scripts/make_paper_figures.sh); build/ is generated
  exp1_queries.json         shared query file of Experiment 1, replayed by every scheme
  exp2_layouts.json         shared layouts of the verification experiments
  exp5_workload.json        shared workload of Experiment 4 (32 domains x 5,000 files, queries, update files)
  runs/<run>/               new runs of scripts/aws_run_all.sh (git-ignored)
```

Suite names in the CSVs: `search_single` / `search_multi` (Experiment 1), `tamper_detection`, `verify_single`,
`verify_multi` (Experiment 2), `exp5_domains` (Experiment 4). Experiment 3 writes `updates.csv`, `layout.csv`,
`queries.csv` and `summary.md` per run folder.
