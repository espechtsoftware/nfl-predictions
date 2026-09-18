# CLAUDE.md

DraftKings NFL DFS prediction and lineup-construction system on free data +
GCP. [README.md](README.md) is the entry point: overview, architecture
diagram, local setup (install, env vars, tests), how the production cadence
and the frozen research chains are orchestrated, the `nfl-dfs` CLI, and the
*Known gaps* section that hosts the Data deficiency log.
[docs/design-guide.md](docs/design-guide.md) holds the original design guide
(§0–§14): data sources, warehouse schema, feature/model theory, optimizer,
backtesting, roadmap. Don't duplicate either — read them.

This file holds only what is durable: where the current state is written
down, how the teams work together, the standing rules, and where results
live. Facts that change (branches, commits, image digests, run ids, what is
running, this week's plan, adopted parameters, experiment verdicts) are
deliberately NOT here — they live in the files below, which are updated with
the work. If something in this file contradicts one of them, the dated file
wins and this file needs a fix.

## Where the current state lives (read in this order)

1. **`HANDOFF.md`** — the authoritative current-work record, newest entries at
   the top. Every material milestone, pause, machine move or agent handoff
   adds an entry: exact branch/commit, what was completed, validation and
   cloud execution ids, unresolved risks, the next concrete action. Its first
   line points at the current take-over document.
2. **The take-over document** — `reports/<date>-…-operating-handoff.md`
   (newest wins). Written so another model can run the coming week without
   the operator re-explaining: ground rules, where everything is, what is
   running, the week day by day, the Sunday money path, settlement, lab and
   production operations, open defects, machine-move checklist.
3. **The briefing for a new model** — `reports/<date>-project-briefing-for-a-new-model.md`
   (newest wins): background, how work is validated here, where the science
   stands, what the last weeks measured, the build process end to end.
4. **`README.md` → Data deficiency log** for every known source-data gap.

Local assistant memory, chat, local-only notes and cloud artifacts are
supporting evidence, never the handoff. Never put credentials, DraftKings
entry keys or the operator's entries exports in any tracked file.

## Two teams, one operator

Two repositories, two GCP projects, one operator (Erich) who owns every
protocol and bankroll decision (contest mix, entry counts, dose, adopting any
selector or filter; pushes to `main`).

- **Production** — this repo, GCP project in `src/nfl_dfs/config.py`. Owns
  the warehouse, the cadence jobs, the money path (the Sunday build, vetting,
  DraftKings upload files, settlement) and the frozen production research
  chains.
- **The lab** — `~/projects/nfl2` (its own GCP project and Cloud Run lanes).
  Owns fast preregistered cohorts: `PREREG-0NN.md` (frozen design + decision
  rule), `experiments/NNN_*.py`, a frozen reader `scripts/preregNNN_report.py`,
  a launcher `scripts/queue_NNN.sh`, and `LEDGER.md` (one row per cohort, the
  reader's verbatim output attached). Its laws are `LAB_RULES.md`; the
  protocol between the teams is `COORDINATION.md` in that repo.

How the teams communicate (see `COORDINATION.md` for the binding text):
decisions and priorities go through the operator, always; technical findings
travel as **committed, pushed files** (reports, PREREG amendments, HANDOFF
entries, LEDGER rows) — never only chat, never only a working tree. The party
that froze a preregistration reads it first; the other party re-runs the same
frozen reader before the row enters the ledger. Shared Cloud Run jobs are
driven only through the launcher registry (`scripts/launcher_registry.sh`,
single-writer lanes); a registered script is never edited while it runs. A
read-only monitor (`scripts/lab_action_note_monitor.py`, unit files under
`deploy/systemd/`) mirrors lab action notes to production. One agent may hold
both roles for a stretch; the artefacts still flow through the same files, so
the next agent can pick either role up from them.

The harness that runs the assistant refuses some commands (pushes to `main`,
create-once publishes, some job executions and unit-file writes). The
convention: print the exact one-line command for the operator, record it in
HANDOFF, and continue with everything else — never route around a refusal.

## Commands

```bash
source .venv/bin/activate
pytest                      # full suite, runs offline (no GCP needed)
nfl-dfs --help              # every pipeline job as a CLI subcommand
nfl-dfs build-features      # feature SQL + leakage checks (needs GCP auth)
```

Install: `pip install -e ".[dev,app]"` for code work; add `gcp` for
pipeline work. BigQuery is the only database — there is no local-data mode.
Config is env vars only, all read in `src/nfl_dfs/config.py`. Work in a git
worktree per task (`git worktree add`), never in a dirty main checkout; the
`.venv` of a checkout is an editable install of *that* checkout, so pass
`PYTHONPATH=<worktree>/src` or build the worktree its own venv.

## Layout

- `src/nfl_dfs/` — `ingest/` → `features/` (+ `sql/features/`) → `models/`
  → `inference/` → `optimizer/` / `backtest/`, plus `app/` (FastAPI),
  `graph/`, `trends/`, `analysis/` (archetype clustering), `research/`
  (frozen chains), `cli.py`. Map with guide sections: README top.
- `sql/` — BigQuery DDL/transforms. `${raw}`, `${features}`,
  `${predictions}`, `${prior_k}` are substituted by `bq.run_sql_file`.
- `tests/` — offline; synthetic player-week panel in `conftest.py`.
- `scripts/` — cadence and money-path drivers (the Sunday path; the current
  take-over document names the scripts in use), frozen-chain controllers,
  readers; `deploy/systemd/` — host monitors; `reports/` — dated evidence.

## Rules

- **Frozen-chain lessons (2026-08-18: seven serialized fix cycles, each
  costing a ~90-minute build+launch).** Standing rules for anyone —
  human or model — working a frozen protocol chain:
  1. Before freezing/SHA-pinning any runner or receipt contract, run one
     outcome-blind smoke against the REAL artifacts it will consume — AND the
     plain full-path smoke at small scale with nothing uploaded, because an
     outcome-blind smoke cannot reach the outcome path (2026-09-15: three
     banks lost to a one-line outcome bug the mechanics smoke could not see).
     Exercise any sampler or fill loop once at production size.
  2. Compare receipts by CONTENT identity — uri/generation/sha256/bytes,
     via `research/object_identity.py` — never by representation
     (absolute paths, timestamp string formats, key spellings).
  3. Never pin a script's own hash in a manifest that script later
     validates: every legitimate repair then fails its own gate. Include
     the explicit `<NAME>_REPAIR_SHA256` override pattern from day one.
  4. When a fail-closed gate trips, classify and then sweep the ENTIRE
     defect class across sibling consumers before starting the rebuild
     cycle; point-wise fixes made the same class recur across scripts.
  5. Cloud Run us-central1 sits AT the JobsPerProject quota. New chains must
     REUSE an existing job (`gcloud run jobs update` + per-execution
     `--args`), never create per-cell or per-run jobs, and disclose the
     reused job name in the run manifest. Deleting old jobs erases their
     execution history and is an operator-only decision.
  6. Before arming any host queue or launcher that can update or execute a
     shared Cloud Run job, acquire that job's single-writer lane through
     `scripts/launcher_registry.sh run`. Keep the lane for the complete host
     launch chain, never edit a registered running script, and reconcile an
     ambiguous/nonzero local `gcloud` return against the exact provider claim
     before retrying. A launcher that dies with the host leaves a receipt
     that must be adjudicated by hand before the lane is reused.
  7. A chain whose validators embed the current commit, an absolute host
     path or a contest-specific constant will fail at the next commit, host
     or week. Prefer content identities, repository-relative paths and
     parameters resolved from the warehouse; keep the Week-1 originals as
     records and generalise beside them.
- **Money-path rules** (each one cost real money in Week 1 of 2026; the
  current take-over document carries the full list): never enter an untested
  rule on an entered book — test it on the historical books first; remove a
  player from entered lineups only when DraftKings marks him OUT/IR or the
  official inactives name him, and answer "replace X" with his live status
  first; never select lineups on raw expected payout (a 1-in-10,000 event
  decides it); the T-70 rebuild must use the salary pull made after the
  10:30 CT inactives.
- **`reports/OPEN-DEFECTS.md` is the register of known, unfixed problems.**
  Read it before proposing work and before any weekly cadence. Every entry
  carries an impact, a deadline and a definition of "resolved"; an item
  leaves only by being fixed and tested or by an explicit recorded
  decision. Add to it whenever you knowingly leave something broken --
  including when the reason is good, such as refusing a production change
  close to a live entry. A defect you chose not to fix and did not write
  down is indistinguishable from one you missed.
- **Frozen prospective gates must be ARMED, and armed on the CURRENT policy.**
  Run `python scripts/check_prospective_gates.py` every week before the
  Sunday build, and whenever a construction lever changes. It is
  fail-closed three ways: a gate inside (or two weeks before) its graded
  window whose scheduler is not ENABLED; a target Cloud Run job whose env
  contradicts the policy the gate declares; and ANY shadow/freeze scheduler
  not classified in its registry. **Why it exists (2026-09-18):** the 2026
  Route Share gate grades Weeks 2-18 and needs a pair frozen before each
  lock; its four schedulers sat PAUSED and were noticed two days before
  Week 2. Eighteen of twenty shadow schedulers were paused. Worse, the two
  jobs it names still carried `N_BOOM=28` while the money path is boom-first
  `N_BOOM=160`/`N_LEV=40`, so resuming them would have burned a graded week
  comparing a policy we no longer run. **An invalid week that looks complete
  is worse than a missing week.** Never resume a paused shadow job without
  checking its env against the current policy first, and never silence the
  checker by moving a live gate into `DORMANT` -- that list requires a
  written reason and is the one place this check can be defeated.
- **Keep the handoff in the repository.** Update tracked `HANDOFF.md` at
  every material milestone and before any pause, machine move, or agent
  handoff. Commit and push the handoff with the associated code whenever
  possible.
- **Point-in-time is sacred.** A feature row for week W may only see data
  from weeks < W (windows end at `1 PRECEDING`). The leakage checks in
  `features/leakage.py` run on every `build-features` and must pass; never
  weaken a check to make a build go green — first prove the build is
  actually point-in-time correct.
- **Walk-forward validation only** (by season). Never random splits.
- **Preflight support before freezing cell-dependent gates.** Run an
  outcome-blind support census first and record the eligible row/event
  counts for every required cell; it may inspect only identity, eligibility
  and support counts — never treatment effects, lift, proper scores or
  outcomes used by the gate. If support is absent, redesign before freezing.
- **Data deficiency log.** Every source-data gap or quality problem gets a
  row in README's *Known gaps* table — date, deficiency, impact, status.
- **nflverse schema drifts.** When a build fails on an unknown column, check
  the live BigQuery schema before assuming the SQL is wrong.
- `.gitignore` patterns must stay root-anchored (`/models/`, not `models/`).
- Season semantics: `config.current_season()` rolls over in March
  (planning clock); nflverse serves data only for started seasons — clamp
  with `nfl.get_current_season()` when loading (see `ingest/nflverse_job.py`).
- **Hardware.** Run at most one resource-intensive local command at a time
  (one targeted pytest module, one build, one simulation); put heavy compute
  on Cloud Run or Cloud Build; treat `/tmp` as nondurable; parallel agents
  only with disjoint file ownership and separate worktrees.

## Where results live (never cite from memory)

- **The experiment ledger**: `reports/2026-07-25-system-study.md` (numbered
  addenda; read the last fifteen before proposing anything — most "new"
  ideas were tested, and several early verdicts were RETRACTED by later
  audits, so never cite an addendum without checking for a correction) and
  the lab's `LEDGER.md` (one row per preregistered cohort, verbatim reader
  output). Verdicts, numbers and adopted levers are quoted from there and
  from the dated reports they point to, not from this file.
- **The adopted production stack** is documented where it is implemented
  (`src/nfl_dfs/inference/production_policy.py` and the manifest test
  `src/nfl_dfs/research/config_manifest.py`, which must show zero
  discrepancies); a change there is a production adoption and needs its
  validation trail in HANDOFF. Frozen chains pinned to an older environment
  fail closed against the live policy — that is the guard working
  (`reports/2026-09-11-frozen-factorial-policy-drift.md`).
- **Validation laws that do not change**: six-season panels with a co-run
  control on the SAME image build; leave-one-season-out with at most one
  negative; vacuity checks (byte-identical arms are a dead lever); the
  post-ensemble and post-selection law (a verdict does not transfer across a
  changed downstream stage); audit before verdict (instrument and code
  audits caught every invalid arm the panel number would have accepted);
  preregister the reopening condition before new outcomes are seen —
  retrospective tuning on already-examined slates is panel mining.
- **Where the science stands** is summarised, with pointers, in the newest
  briefing (§3 and §7); the standing structural conclusion and the open
  question are there, not here.
