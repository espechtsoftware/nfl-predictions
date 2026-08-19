# CLAUDE.md

DraftKings NFL DFS prediction and lineup-construction system on free data +
GCP. [README.md](README.md) is the authoritative document: the full design
guide (§0–§14), the Quick start (install, env vars, local usage, deploy),
and the section-to-code map at the top. Don't duplicate it — read it.

`HANDOFF.md` is the authoritative current-work record. Read it before doing
project work; the historical narrative below is context and may be
superseded by that file.

## Commands

```bash
source .venv/bin/activate
pytest                      # full suite, runs offline (no GCP needed)
nfl-dfs --help              # every pipeline job as a CLI subcommand
nfl-dfs build-features      # feature SQL + leakage checks (needs GCP auth)
```

Install: `pip install -e ".[dev,app]"` for code work; add `gcp` for
pipeline work. BigQuery is the only database — there is no local-data mode.
Config is env vars only, all read in `src/nfl_dfs/config.py`.

## Layout

- `src/nfl_dfs/` — `ingest/` → `features/` (+ `sql/features/`) → `models/`
  → `inference/` → `optimizer/` / `backtest/`, plus `app/` (FastAPI),
  `graph/`, `trends/`, `analysis/` (archetype clustering), `cli.py`.
  Map with guide sections: README top.
- `sql/` — BigQuery DDL/transforms. `${raw}`, `${features}`,
  `${predictions}`, `${prior_k}` are substituted by `bq.run_sql_file`.
- `tests/` — offline; synthetic player-week panel in `conftest.py`.

## Rules

- **Frozen-chain lessons (2026-08-18: seven serialized fix cycles, each
  costing a ~90-minute build+launch).** Four standing rules for anyone —
  human or model — working a frozen protocol chain:
  1. Before freezing/SHA-pinning any runner or receipt contract, run one
     outcome-blind smoke against the REAL artifacts it will consume.
     Synthetic contract tests alone passed a frozen runner carrying three
     schema defects; outcome-blind reality contact costs nothing
     scientifically and would have caught every one pre-freeze.
  2. Compare receipts by CONTENT identity — uri/generation/sha256/bytes,
     via `research/object_identity.py` — never by representation
     (absolute paths, timestamp string formats, key spellings). Four
     representation mismatches with byte-identical content each consumed
     a full fix cycle in one day.
  3. Never pin a script's own hash in a manifest that script later
     validates: every legitimate repair then fails its own gate. Include
     the explicit `<NAME>_REPAIR_SHA256` override pattern (must equal the
     exact current file hash — conscious, not silent) from day one.
  4. When a fail-closed gate trips, classify and then sweep the ENTIRE
     defect class across sibling consumers before starting the rebuild
     cycle; point-wise fixes made the same class recur across scripts.
- **Keep the handoff in the repository.** Update tracked `HANDOFF.md` at
  every material milestone and before any pause, machine move, or agent
  handoff. Record the exact branch/commit, completed work, validation and
  cloud execution IDs, unresolved risks, and the next concrete action.
  Commit and push the handoff with the associated code whenever possible.
  Local assistant memory, local-only notes/commits, and Cloud Run/Build
  artifacts are supporting evidence, never the sole handoff. Never put
  credentials or secret values in the handoff.
- **Point-in-time is sacred.** A feature row for week W may only see data
  from weeks < W (windows end at `1 PRECEDING`). The leakage checks in
  `features/leakage.py` run on every `build-features` and must pass; never
  weaken a check to make a build go green — first prove the build is
  actually point-in-time correct.
- **Walk-forward validation only** (by season). Never random splits.
- **Preflight support before freezing cell-dependent gates.** When a proposed
  protocol requires minimum counts in calibration cells, run an outcome-blind
  support census first and record the eligible row/event counts for every
  required cell. This preflight may inspect only identity, eligibility and
  support counts--never treatment effects, lift/error values, proper scores or
  outcomes used by the gate. If required support is absent, redesign the
  protocol before it is frozen rather than weakening an eligibility rule after
  a treatment grid has been observed.
- **Data deficiency log.** Every time we find a gap or quality problem in
  source data (missing seasons, schema drift, unmatchable rows, absent
  fields), add a row to the "Data deficiency log" table in README.md's
  *Known gaps and future enhancements* section — date, deficiency, impact,
  status. It's an append-only decision aid for what to fix or accept later.
- **nflverse schema drifts.** Column renames upstream have already broken
  feature SQL once (see the log). When a build fails on an unknown column,
  check the live BigQuery schema before assuming the SQL is wrong.
- `.gitignore` patterns must stay root-anchored (`/models/`, not
  `models/`) — an unanchored pattern once silently kept
  `src/nfl_dfs/models/` out of git and the package had to be rebuilt from
  its tests.
- Season semantics: `config.current_season()` rolls over in March
  (planning clock); nflverse serves data only for started seasons — clamp
  with `nfl.get_current_season()` when loading (see `ingest/nflverse_job.py`).



## Handoff state (2026-08-05 final, Fable program complete — Opus operates from here)

Local box crashes under load (HYPERVISOR_ERROR, 5x): BQ queries and
SINGLE targeted test runs are fine locally; NEVER run parallel agents,
parallel pytest, or local sims — ALL heavy compute on Cloud Run. /tmp
dies on reboot — durable driver scripts + state files live in
~/nfl-panels/ (rerun any driver after a crash; state files resume).
The experiment ledger is reports/2026-07-25-system-study.md (89
addenda — READ THE LAST FIFTEEN before proposing anything; most "new"
ideas are already tested, and several early verdicts were RETRACTED
by later audits, so never cite an addendum without checking for a
correction in a later one).

- **SUPERSEDED REPLAY HEADLINE (HARVEST-FINAL-2, Addendum 87): 27/107 weeks
  best-of-40 >= 194, mean best 179.5, median percentile 14.2%** —
  per-season {2019:5, 2021:3, 2022:3, 2023:4, 2024:6, 2025:6},
  byte-identical to its validating arm across an image rebuild. **Corrections
  2026-08-07:** independent reconstruction found zero actual-score mismatches
  across all 17,851 candidates, but authoritative repricing makes 256 selected
  lineups illegal; the verifiably legal old book is 25/107, not 27. The later
  17/107 rebaseline also omitted historical DST aliases (478 salary rows
  across 2019/2021). **There is currently no citable complete-universe
  baseline; a fresh 0/0/0/40 panel is required.** See
  reports/replay-score-validity-audit.md.
- **PROVISIONAL PRODUCTION STACK (all code defaults, no envs; every scoring
  adoption must be revalidated after the corrected baseline)**: EW draw shaping +
  QF construction (N_QB_VARIANTS=4) + NAIVE-ownership chalk fade
  (OWN_MODEL default "" — the fade itself is +2 twice-proven; the
  trained booster added nothing and left the construction path) + NO
  punt mandate, NO punt-boom boost (deleted at +1/+2; the p90 punt
  VALUATION and $49k salary floor and stack mandate all KEPT —
  true-deletion tests cost tails) + SCHED features + TabPFN marginals
  + MODEL_ENSEMBLE=3 + prop-market blend, now props-first in LIVE
  paths too (parity fix; DK-PPG fallback). Tournament-only
  construction unchanged: chalk-fade on OUR objective,
  QB+2+bring-back, mandatory sim-mode.
- **VALIDATION LAWS (never relax)**: six-season panels, co-run
  control on the SAME image build (RNG stream order changes rebase
  everything — golden-hash parity tests in tests/test_sbi.py now pin
  default draws); LOSO >=4-of-6 with <=1 negative; vacuity checks
  (byte-identical arms = dead lever; env-name typos and column-gated
  levers both happened); post-ensemble AND post-selection law:
  verdicts don't transfer across a changed downstream stage; AUDIT
  BEFORE VERDICT — the fade mislabel, GREEN2 env typo, and TDLEDGER
  season-pooling defect were all caught by instrument/code audit,
  never by the panel number; deletion tests need the env to actually
  gate what its name claims.
- **SUPERSEDED MEASURED FRONTIER (Addenda 92-93, panel
  20260805-hf5 — retained only as defect evidence, NOT citable)**: its
  recorded pool oracle cleared 35/107 vs the selected book's 27, but the
  panel mixed all NFL-week games into a supposed Sunday main slate and used
  contaminated historical salaries; 256 selected lineups also fail current
  repricing. Its historical observation was
  **8 recoverable weeks across 4 seasons**; mean regret 6.8. But
  corr(oracle sim-rank, regret) is +0.030 among unselected oracles
  (the old +0.428/+0.211 figures were inflated and are RETRACTED), so
  there is no gradient to learn IN THE SIGNALS WE HAVE. **Selection is
  closed FOR THE CURRENT SIMULATOR AND STATIC FEATURE SET** (Addendum
  95 — do not overstate this as "selection is closed"): falsified five
  ways — LSE, sharp-LSE, QB-concentration, dollars-objective, and the
  decision-focused residual reranker (A1 +1 clear in 2 seasons, A2
  flat, A3 -3, shuffled control 25 — orthogonal features made it
  WORSE). Generator crowd-out is REFUTED: removing `lev` (48% of the
  pool, 8% of selections) costs 1 clear; removing `boom` costs 15;
  `dark` is the best value-per-candidate batch. Tail-line 187/194/200
  is flat. The only live capture paths are MORE ENTRIES per slate and
  genuinely new information (plan Workstream E).
  REOPENING CONDITION (preregistered, Addendum 95): a selector may be
  revisited ONLY on a genuinely new pre-lock signal (market MOVEMENT /
  cross-book dispersion, activated evidence, point-in-time tracking
  traits, or an adopted new dependence model) with evaluation frozen
  BEFORE new outcomes are seen. Retrospective tuning on these same 107
  slates is panel mining — forbidden.
  QUARANTINED RESEARCH DATA IN THE WAREHOUSE: predictions.replay_candidates
  (17,851 labeled candidates, full provenance + masks),
  predictions.slate_player_features (31,107 point-in-time rows), 107
  checksum-verified score artifacts in gs://nfl-predictions-503414-raw
  /cand_scores/20260805-hf5/. `research_eligible=FALSE` on both candidates
  and snapshots. Promotion gate:
  scripts/harvest_accept.py (10 checks + the §6.1 decision gate).
- **REPLAY-UNIVERSE REPAIR (2026-08-06, NOT A SCORING ADOPTION):**
  the player-miss audit found historical usage was activity-spined and
  historical salary matching missed suffix names. Across the six-season
  panel, 204 omitted salary-listed player-weeks scored 20+ and 40 scored
  30+. The implementation moves salary before actuals/usage, retains zero
  labels for the selectable universe, separates 76,689 active model-fitting
  rows from 22,028 listed-inactive scoring rows via `was_active`, removes
  known-Out players in replay, and hard-fails any salary/training gap. A
  remote scratch build produced 98,717 rows and zero gaps. Production Cloud
  Run execution `build-features-gk966` reproduced those counts, passed all
  leakage checks, and left zero gaps. After the replay-provenance fix,
  app/build-features/train-weekly/project-slate share digest
  `sha256:c8f2703b...`; the app is ready on revision 00059. The corrected
  baseline attempt `20260806-universe-baseline-5e4646e` is INVALID: nullable
  `is_rookie` crashed cold-start filling before scoring (five failed, one
  cancelled). The bool path is fixed/tested; rerun on a new image and panel id.
  Its six execution ids and status live under reports/panel-runs/. Do not attribute a later
  score change to fast-role features: those columns are EXTRA_FEATURES-only
  and must run as a separate same-image arm after the corrected baseline.
  Use scripts/baseline_panel.sh: immutable digest, explicit CODE_SHA, unique
  panel id, captured execution ids, and per-season lineup tables. Candidate
  promotion now rejects blank/unknown code provenance (containers have no
  `.git`, so CODE_SHA is the tested fallback).
  Replacement preflight `20260806-universe-baseline-81b7ff3` fixed the null
  crash and completed two 2019 weeks, then was intentionally cancelled: the
  candidate lever record omitted EXTRA_FEATURES, so a treatment would not be
  self-identifying in BQ. It is non-citable/unpromoted. The next image records
  the full effective lever set; acceptance requires one code/config/lever/seed
  identity. Frozen role protocol: reports/fast-role-state-experiment.md.
  Replacement panel `20260806-universe-baseline-525ddb1` is INVALID: its 2019
  smoke passed, but 2022+ revealed LineStar adjacent-Thursday DST rows carrying
  the prior source week; old replay dropped one duplicate by input order and
  could use the wrong opponent/salary. Cancelled, staging-only, unpromoted.
  Expanded panels need 16Gi: initial 2022-25 executions hit the 12Gi cap
  before candidates and are durably listed as failed; same-image/4-CPU reruns
  were cancelled after the DST finding. scripts/baseline_panel.sh now defaults
  to 16Gi. DST salary rows must match schedule team+opponent+week, duplicates
  hard-fail, and smoke defaults to 2022. Fresh image/panel required.
  Panel `20260807-universe-baseline-124e853` COMPLETED and passed the then-current remote
  acceptance on `sha256:da6fe02c...`: 107/107 slates, 17,915 candidates,
  63,702 player snapshots, all promoted atomically for research. Recorded
  result: **17/107 >=194**, mean best 173.31, per-season 6/2/3/2/1/3;
  pool oracle 26/107, leaving nine recoverable weeks across five seasons.
  Later correction: DST salary aliases other than LAR were not normalized
  before the modern-code schedule join, dropping 228 rows in 2019 and 250 in
  2021. The 17/107 result is reproducible but invalid as a complete-universe
  control and was never a production feature adoption. Acceptance wrapper fix: an unset Cloud Run
  failedCount means zero; still require Completed=True and succeededCount=1.
  Corrected-panel missed-player job `analyze-missed-baseline-8p2mh` found
  1,004 player-slate misses at 20+ actual: 517 generation, 428 generated only
  in non-improving combinations, 59 true selection opportunities. Future
  immutable snapshots now include fast-role/archetype inputs; the running
  original-image arm remains score-valid but lacks those fields for mechanism
  analysis. See reports/corrected-panel-missed-player-analysis.md.
  The fast-role protocol was tightened before results: a pass on the original
  124e853 panel is promising only and must reproduce on a snapshot-capable
  same-image control/treatment pair before production adoption.
  FINAL FAST-ROLE VERDICT: REJECTED, 11/107 >=194 versus corrected control
  17/107; per-season 2/1/0/3/0/5 versus 6/2/3/2/1/3. Mean/median and >=187
  improved, but >=200 fell 11->6; primary tail gate governs. Unpromoted/off.
  Union oracle 32 vs 26 included six treatment-only clears (4 boom, 2 lev):
  discovery evidence for a fixed-budget baseline-scored alternative-belief
  generator only, never evidence to adopt the wholesale role model.
  Frozen follow-up: reports/role-belief-generator-experiment.md. It replaces
  12 boom with 4 alternate-role mean variants + 8 alternate-role worlds,
  cross-scores/selects under baseline draws, exact-pairs all 107 pool counts,
  and requires +2 clears plus season/mean/oracle/mechanism gates. Defaults
  remain EPI=0. ROLE_BELIEF_* are forbidden on production deployments.
  Panel 20260807-role-belief-v1-7976636 completed on digest sha256:4f2fa01d
  but is INVALIDATED before scoring/promotion: it inherited the DST omission
  and capped every slate 12 below source, yielding a degraded 12/107 control.
  The superseding runner uses full source counts and requires exact source
  reproduction. No adoption or promotion.
  Alias-corrected replacement `20260807-universe-baseline-82584d2` was also
  cancelled before acceptance: source inspection proved every historical
  NFL-week feed was being treated as a Sunday-main draft group. Replay now
  independently restricts the target season to regular-season Sunday
  13:00-through-late-afternoon games. A second audit found adjacent-game
  skill salaries were aggregated before opponent validation, and the
  replay-local DST actual scorer omitted several DK scoring events. Both
  paths are corrected in code; feature rebuild + a fresh six-season panel
  are still required. No adopted/graveyard score test may launch before it.
  Frozen sequence and complete arm ledger:
  reports/post-correction-revalidation-plan.md.
  Maintenance pause closed: s-features/s-train/s-project-tu/s-project-su are
  ENABLED on their existing CT schedules; no research lever was enabled.
  Durable record: reports/replay-universe-and-leaderboard-forensics.md.
- **RESEARCH PROGRAM (reports/emerging-technologies-plan.md is the
  spec; reports/september-research-designs.md the queue)**: six
  workstreams BUILT under src/nfl_dfs/research/, adopt-only-as-proven.
  Verdicts so far: GFlowNet GATED OUT (its own cheap-diversity
  baselines beat it — world-argmax +7.9 / Gumbel-MILP +6.8 vs GFN
  +5.4 at equal count); parametric TD coupling BURIED VALIDLY
  (TDLEDGER2 19 vs 27 after all defects fixed); Chronos baselines-win
  (EWM/Kalman better everywhere, worst at cold start); SBI 2-of-3
  params identifiable (synthetic gate passed; walk-forward real-data
  inference is the next step, §6.8 needs listed in ledger); tracking
  v0 SHIPPED (1,384-player trait table + 96.3% high-confidence gsis
  crosswalk at ~/projects/other-nfl-projects/nfl-big-data-bowl-2026/;
  next gate = shadow features on thin-history players; free in-season
  refresh = nflverse NGS weekly aggregates); evidence + online
  conformal built and fixture-proven, data-gated on September news /
  scored rows. September generation arms (Schaake/EPI/CE) were repaired
  after the first cloud executions failed a mechanism audit; those executions
  are INVALID and must be rerun from the repaired image (system-study
  Addendum 97). Schaake is gated on realized variogram + upper-tail score and
  exact marginal preservation before any candidate panel. **Schaake was
  subsequently measured and rejected** (Addendum 99: worse variogram and
  tail Brier, exact marginals preserved). CE's first run was promising, but
  its immutable-image, exact-cap, independent-seed confirmation scored
  **26/107 versus the 27/107 boom-only control** (mean best 180.03 versus
  179.44), so CE is research-only and production is `N_CE=0,N_BOOM=40`.
  The plain Gumbel candidate arm was also completed and rejected (Addendum
  90: 26/107 versus 27/107, identical mean best); `N_GUMBEL` stays default
  off. Its audited fixed-budget confirmation was worse still (20/107).
  A distinct hierarchical game/team/player Gumbel arm was then frozen and
  tested at equal marginal shock variance: 23/107 versus 27/107. Two slates
  were short by one treatment candidate; even the conservative bound that
  both control clears disappear is 25/107, still above treatment. The whole
  Gumbel candidate-generation family is therefore closed, not deployed.
- **SHADOW COLLECTORS (all automatic, best-effort, deliberately NOT
  in status.FEEDS)**: predictions.div_shadow (prop-market divergence,
  writes only when props exist; grade with scripts/div_shadow_grade.py
  after 4-6 weeks — pre-registered bar inside), predictions.own_shadow
  (build-time predicted ownership incl. booster column),
  predictions.live_candidates (reranker training set). The config
  manifest (src/nfl_dfs/research/config_manifest.py) must show ZERO
  discrepancies (tests enforce).
- **GPU on Cloud Run works and is cheap** (L4, us-central1,
  --no-gpu-zonal-redundancy, 1h cap, ~$0.70/hr): jobs tabpfn-gen
  (TABPFN_UPCOMING=season:week — run WEEKLY Wed + after every
  build-features), tabpfn-comp, lem-train, lem-rollout. Sources
  versioned under scripts/.
- **September cadence (run-only; NO new code should be needed)**:
  Mon/Tue standings downloads (DK purges ~4 days) → import-ownership;
  Wed tabpfn-gen with TABPFN_UPCOMING; weekly ETR CSV to /market
  (paid pass Sep 8-9); persona shadow + env-forecast logged weekly and
  GRADED before any adoption; CQR auto-activates at >=100 scored
  rows; field-calibration after 2-3 weeks of standings; DIV_TILT
  shadow auto-collects (grade at week 4-6); entries per contest-mix
  memory (3 qualifiers x 14 + 4 Milly week 1; never <15 per contest).
- External reviews: 5 rounds (Gemini x4, Sol/GPT-5.6 with code
  access). Every actionable finding implemented and tested; review
  packages archived in reports/review-archive/ (superseded — the
  ledger is authoritative). The audit-before-verdict law is their
  legacy: reviews caught three invalid arms the panel would have
  sworn were real.
