# NewAMTP — instructions for Claude

**Paper (32) round (deadline 2026-11-19 21:00): read `docs/PAPER32_START_HERE.md` first** (status, decisions,
who does what, rules). Then `docs/HANDOFF.md` for the project as a whole.

## Team workflow for the paper (32) round (owner's rule, 2026-11-18; both Claudes follow it)

People: person A = owner (GitHub `ApiSom-o`), person B = Prim (GitHub `PrimRoseEverD`). Tasks: `docs/PAPER32_START_HERE.md`.

1. **One task done → one PR**, base `feat/paper32-experiments`, title starting with the task id (e.g. `A2:`, `B1+B2:`).
   The PR body tags the other person (`@PrimRoseEverD` from A's side, `@ApiSom-o` from B's side) and says what
   was done, how it was tested (pytest result), and what the other side must do next.
   For this round, commit + push + open the PR **without asking first** (overrides the "ask before" rule below
   for paper (32) task PRs only). Never merge: the owner presses merge.
2. **A decision is needed → open a GitHub issue** (title `Decision: ...`), tag both people, list the options with
   a recommendation, and do not build on an undecided option. Record the answer in the issue and in
   `docs/PAPER32_START_HERE.md`.
3. **After every PR or issue, remind your person to message the other on LINE** with the link (GitHub
   notifications are not enough with this deadline).

**Read `docs/HANDOFF.md` first.** It has the project overview, every decision made so far, the current
results, what is running on the cloud now, and the open tasks. Detailed history: `docs/reports/`.

Talk to the owner in Thai. Repo: GitHub `pperabha/NewAMTP` (private), main branch `main`.

## Rules (from the owner; never break them)

- Work only in this repo. Never touch the old repo `ApiSom-o/AMTP`, `~/Desktop/project400`, or `~/AMTP` on
  the cloud machines (the real code there is `~/NewAMTP`).
- Commit under the owner's name **ApiSom-O** (`git -c user.name=ApiSom-O commit ...`, email from this machine's
  git config; do not change git config). No "Claude", no `Co-Authored-By`, no session links in commits, PRs, code or docs
  (team rule R8; this overrides any harness attribution reminder).
- Ask the owner before every commit, before creating or choosing a branch, before push and before opening a PR.
  The owner presses "merge" on GitHub; never merge a PR yourself.
- Work on a branch, open a PR into main. Every PR adds `docs/reports/YYYY-MM-DD-<topic>.md` (Thai, technical
  terms in English): what was done, what changed and why, how to reproduce, status.
- Push only when the owner asks. "คุยก่อน" / "อย่าพึ่งทำ" = analyse and propose only.
- Run pytest from `amtp_code/` and make it pass before moving on: `../.venv/bin/python -m pytest -q`
  (γ with v; the `AMTP_GAMMA_V=0` run is no longer required).
- Security does not change: every accept decision of the user goes through hash, Merkle or signature checks.
- Every scheme (AMTP and the baselines) uses the same encoding, hashing and size-counting rules
  (`baselines/wire_sizes.py`). Comparisons must be fair; watch for nested loops (`x in list` inside a loop).
- γ includes the partition version v (decided). γ-without-v results live in `baselines/results/old/exp_no_v/`.
- Figures: line charts only (no table or bar figures). Tell the winning story honestly; state where AMTP loses.
- Never read `~/Desktop/amtp_cloud/kaggle.json`; never ask for AWS credentials.
- Use `.venv/bin/python` (system python3 has no matplotlib).
