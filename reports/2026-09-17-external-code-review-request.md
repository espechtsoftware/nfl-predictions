# Code-review request for an independent agent (2026-09-17)

Written for the reviewing agent on the operator's second machine. Read this file first, then
`reports/2026-09-15-week2-operating-handoff.md` (§2 running processes, §3a weekly cadence, §4 the Sunday money path,
§9 the defect list) and `reports/2026-09-16-findings-since-week1-synthesis.md` (what the science currently says).
The operator runs both machines; the other agent (on the workstation) is operating the live week and is the audience
for your findings.

## What this project is, in one paragraph

A DraftKings NFL DFS system: free public data plus two paid charting feeds land in BigQuery (`nfl_raw`), features are
built point-in-time (`nfl_features`), a model plus a prop-market blend produces projections (`nfl_predictions`), a
simulator draws 10,000 worlds per slate, a solver generates thousands of candidate lineups, and a greedy
expected-maximum selector picks the book that is entered on Sunday. A separate lab repository (`nfl2`, GCP project
`nfl-2-506823`) runs preregistered experiments against a frozen 72-slate development panel; adoption into the money
path requires a passing preregistered read, never a hunch.

## Scope: what to review, in priority order

1. **The Sunday money path**, end to end, for correctness under time pressure and for silent-failure modes:
   `scripts/week_env.sh`, `scripts/sunday_runbook.sh`, `scripts/sunday_build_host.sh`, `scripts/sunday_after_build.sh`,
   `scripts/sunday_watch_dk_entries.sh`, `scripts/sunday_watch_late_inactives.py`, `scripts/arm_week_timers.sh`,
   `scripts/fill_dk_entries.py`, and the host tools under `/home/erich/week1-sunday/tools/` (tracked copies in
   `scripts/week1_*`). Specific question: **where else can a wrong-but-plausible input pass silently?** Five such
   defects were found in one week (see §9 of the operating handoff, defects 24–28); assume more exist.
2. **The projection and blend path**: `src/nfl_dfs/inference/run_projections.py` (especially the props-first blend and
   its DK-points-per-game fallback), `src/nfl_dfs/models/prop_market.py`, `sql/features/*.sql` for point-in-time
   correctness (`features/leakage.py` must never be weakened). Defect 27 is the worked example: at week ≤ 3 the
   fallback makes projections a copy of last week's box score, and nothing downstream noticed.
3. **The lab experiment harness** (`nfl2`): `experiments/119_dose12800.py`, `scripts/prereg099_*.py`,
   `scripts/run_119_local_v*.sh`, and `LAB_RULES.md`/`COORDINATION.md`. Question: are the frozen readers genuinely
   fail-closed, and does any amendment path let an outcome be seen before the design is fixed?
4. **Anything you consider dangerous** that we are not looking at.

## Ground rules (these are hard)

- **Read-only on this machine's live state.** Do not run Cloud Run jobs, do not push to `main`, do not touch anything
  under `/home/erich/week1-sunday/ENTERED/` or `results/2026-09-13/` (DraftKings entry keys and exports; never commit
  them), and do not kill host processes. The workstation is running a live experiment and the week's builds.
- **No silent fixes.** Propose changes as patches on your own branch; do not merge or rebase anything.
- Treat `HANDOFF.md` as the authoritative state record, newest entry at the top.

## How to deliver your findings (this is the channel)

1. Branch from `origin/main` in the relevant repository: `review/2026-09-code-review-<yourname>`.
2. Write one report at `reports/reviews/2026-09-17-code-review-<yourname>.md` (in `nfl2`, use `handoffs/` instead,
   which is that repository's cross-team convention). Structure it as: **(a)** findings ranked by expected cost, each
   with file and line, what breaks, how to reproduce, and a suggested fix; **(b)** anything you verified as correct
   that looked suspicious, so we do not re-audit it; **(c)** open questions for the operating agent.
3. Optional: patches as separate commits on the same branch, one concern per commit, tests included where they make
   sense. Never commit generated data or entry files.
4. `git push origin review/2026-09-code-review-<yourname>` and tell the operator the branch name. The operating agent
   polls `git fetch origin` and reads any branch matching `review/*`.
5. If you need something run on the workstation (a query, a build, a test at production scale), write the exact
   command into your report under a heading **"Requests for the operating agent"**; do not ask the operator to relay
   prose.

## What a useful review looks like here

The project's own standing rules say verdicts come from evidence, not from plausibility: every claim in your report
should name the file and the observable consequence. Findings that would have caught defects 24–28 before they
happened are worth more than style. If you find nothing in a subsystem, say so explicitly — that is a useful result.
