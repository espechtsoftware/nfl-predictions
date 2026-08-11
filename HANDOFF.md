# Project handoff

This tracked file is the authoritative record for resuming development. It
must travel with the repository. Do not rely on assistant memory, an
individual workstation, unpushed commits, or cloud artifacts as the only copy
of project state.

## Handoff policy

Before pausing work, changing computers, or handing the project to another
agent or developer:

1. Update this file with the branch and commit, what changed, validation
   results, durable Cloud Build/Run IDs, unresolved risks, and the exact next
   action.
2. Commit the handoff together with the code it describes and push it whenever
   credentials and repository availability permit.
3. Keep secrets out of the repository. Record account/project identifiers and
   authentication requirements, never tokens or credential contents.
4. Treat local notes, assistant memory, and cloud logs as supporting evidence
   only. If they contain material state, summarize it here before stopping.

## Current state — 2026-08-11 09:53 CDT

Active branch is `main`; outcome-blind support-audit commit `569c3b3` is
pushed. The one authenticated support-window collection is active
under run `20260811T145426Z__same-season-advanced-receiving-support-windows-v1`.
The three operator-supplied outside-review documents
`reports/2026-08-10-scoring-strategy-recommendations.md`,
`reports/2026-08-11-fantasy-points-data-utilization.md`, and
`reports/2026-08-11-post-window-program-review.md` remain untracked and must
not be staged or modified.

### Tail-first law revised; role-union v2 adopted and live

- Corrected direct-role confirmation
  `20260810-lockfix-e80-k1-role12union-8677d21` passed immutable 2024
  preflight `replay-lockk1role-smoke-bbg27` and launched all six season jobs
  from corrected generation digest
  `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`:
  `replay-lockk1role-2019-7hb9j`, `replay-lockk1role-2021-42gdb`,
  `replay-lockk1role-2022-mhn54`, `replay-lockk1role-2023-qzfdq`,
  `replay-lockk1role-2024-w2ft7`, and `replay-lockk1role-2025-w4bnb`.
  All six completed successfully. Check-only acceptance execution
  `accept-replay-panel-vlxrz` passed 107 complete exact-80 books. Frozen
  comparator execution `compare-corrected-k1-direct-role-d2wn4`, using digest
  `sha256:5319704c23ac40f30771a43b2fb6b4d012a7b2d8f610b980ecfd509ba55deb6b`,
  returned disposition `pass` with zero source-containment, shared-score,
  p-line, or support mismatches. At 240/230/220/210 the corrected K1 source is
  `1/2/4/7` and direct-role is `2/3/5/7`; the broader
  187/194/200/210/220/230/240 grid is `34/22/11/7/5/3/2`, mean weekly best
  `180.1207`, median `178.44`, and pool oracle `42/28/16/9/5/3/2`.
  Direct-role is now the corrected research incumbent. Promotion execution
  `accept-replay-panel-2prcg` completed successfully and copied the complete
  candidate books plus player snapshots into the accepted research tables.
- The new operator-supplied post-window review has been reconciled against
  the actual code and durable results in
  `reports/2026-08-11-post-window-review-reconciliation.md`. Its strongest
  lead is valid but not yet a production-path finding: raw component draws
  exceeded q90/q95/q99 at 11.11%/7.10%/2.69%, before the fitted widening,
  TabPFN/empirical marginal shaper and 45/55 market blend that score the
  adopted books. The exact next diagnostic is frozen before generating those
  unseen final-path quantiles in
  `reports/2026-08-11-served-tail-calibration-protocol.md`. It must reproduce
  the exact 13,876 active accepted RB/WR/TE rows for held-out 2023--2025,
  match every persisted pre/post-blend mean within `1e-4`, report
  q90/q95/q99 exceedance, pinball, CRPS, 20/30 Brier and week-clustered
  uncertainty, and confirms the defect only if all three exceedances are
  high and q99's clustered 95% lower bound remains above 1%. A confirmation
  licenses one separately frozen mean-invariant recalibration; it cannot
  reopen a closed vendor arm. Advanced Rushing collection is deliberately
  deferred until this cheaper, directly relevant calibration path resolves.
  Implementation now reproduces the frozen production environment, aligns
  final draws to exact accepted rows, checks the accepted pre/post-blend
  means, and reports pinball, CRPS, Brier and both binomial and week-clustered
  exceedance uncertainty. The new CLI is
  `served-tail-calibration-diagnostic`; one-shot runner
  `scripts/cloud_served_tail_calibration.sh` requires an immutable image and
  records one execution/report. Twelve focused served-tail/Route-component
  tests pass, with compilation, CLI discovery, shell syntax and whitespace
  clean. Exact-tree Cloud Build
  `98d988c4-ba7e-4dc6-b36b-73ec5842d761` passed 827 tests with two expected
  skips and published immutable digest
  `sha256:4501adb4d4d7389feb931b4f2696eb780c18f3207d5e00732b54c5d616bdf7ff`.
  The one immutable execution `served-tail-calibration-6fk9k` completed and
  reproduced exact fold populations 4,666/4,596/4,614 with zero actual and
  post-shaper mean delta and maximum post-blend mean delta `3.55e-15`.
  Aggregate served q90/q95/q99 exceedance is
  `10.5794%/5.4627%/1.4774%`; q99's week-clustered 95% interval is
  `1.2526%--1.7021%`, wholly above nominal. The frozen defect gate therefore
  passes. The durable report is in
  `reports/served-tail-calibration-runs/20260811-served-tail-calibration-v1/`.
  One follow-up is now frozen before producing any corrected metric or score
  in `reports/2026-08-11-served-tail-recalibration-experiment.md`: fit one
  global mean-invariant RB/WR/TE spread scale only on 2019/2021/2022 final
  served draws, gate it on untouched 2023--2025 calibration/loss metrics,
  and only then run one exact-80 2023--2025 lineup treatment. The exact next
  action is to implement and validate Stage A; production remains unchanged.
  Stage A is now implemented locally: the shared scaler runs only after
  shaping and the market mean shift, changes only RB/WR/TE spread, preserves
  each mean within `1e-10`, and is pinned to identity by the live production
  policy. The frozen fitter evaluates `1.000..1.250` by `0.005` using only
  equal-season normalized q95/q99 pinball on 2019/2021/2022, then gates the
  one factor on exact untouched 2023--2025 rows. It reports paired
  week-clustered loss uncertainty and cannot launch a lineup treatment unless
  Stage A passes. Replay and live paths call the same helper. The complete
  local test suite passes with the expected skip, plus compilation, CLI,
  shell and whitespace checks. Exact-tree Cloud Build
  `fc4a2b96-e428-44b4-9f0f-93eff87efc81` from implementation commit
  `623b1b4` passed 831 tests with two expected skips and produced immutable
  digest
  `sha256:a7fb5dd48960cb26292a5ae60f6c71df8789cc06ba87497659916e63ed61972c`.
  The one immutable Stage A execution `served-tail-recalibration-l49zt`
  completed from that digest and passed every frozen gate. The pre-evaluation
  2019/2021/2022 fit used 4,395/4,755/4,625 rows and selected global factor
  `1.025`. On the untouched 13,876 evaluation rows, q90/q95/q99 exceedance
  improved from `10.5794%/5.4627%/1.4774%` to
  `10.2767%/5.2393%/1.3332%`; q99 absolute error improved 30.2% and the
  equal-season q95/q99 pinball ratio was `0.997879`. Both 20/30 Brier losses
  improved slightly. CRPS worsened 0.334%, within the frozen 0.5% limit, and
  every row mean was preserved within `7.11e-15`. The durable report is under
  `reports/served-tail-recalibration-runs/20260811-served-tail-recalibration-stage-a-v1/`.
  This licenses exactly one factor-1.025 direct-role exact-80 treatment on
  2023--2025; it does not yet alter production. The exact next action is to
  build and launch the now-implemented Stage B partial panel. Candidate
  persistence records the scale, canonical acceptance supports and strictly
  checks the exact requested season set, and the immutable wrapper is fixed
  to panel `20260811-lockfix-e80-k1-role12-tail1025-v1`, seasons 2023--2025,
  factor `1.025`, 80 entries, 12 direct-role candidates and 40 boom
  candidates. The comparator audits exact player-input/mean/seed/lever
  invariance apart from the scale, combines untouched source 2019/2021/2022
  with treatment 2023--2025 for 107-slate metrics, and applies the frozen
  240/230/220/210 decision order. Mixed high-threshold results require
  operator review. The complete local test suite, focused contracts,
  compilation, shell syntax and whitespace checks pass. Production is still
  pinned to identity. Exact-tree Cloud Build
  `82147e17-6c8d-4a99-bd3d-b56475d0724a` succeeded from commit `3431add` and
  published immutable digest
  `sha256:22f0936b307236a2cfc9462f50e9bf4bd31f57dfa0b7975132baec9766db90e8`.
  The sole Stage B launch used immutable 2024 smoke
  `replay-lockk1tail-smoke-md2tb` passed, then the wrapper launched
  `replay-lockk1tail-2023-bdhsj`, `replay-lockk1tail-2024-4727d`, and
  `replay-lockk1tail-2025-6mnfb`. The exact manifest is tracked under
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-tail1025-v1/`. Do not
  rerun this treatment or test another factor.
  All three treatment executions subsequently completed successfully.
  Check-only acceptance `accept-replay-panel-mmkps` passed the exact 54-slate,
  exact-80 contract. First comparator execution
  `compare-served-tail-stage-b-pgwcw` failed mechanically: its `1e-6`
  candidate-mean tolerance was below persisted float resolution, flagging
  4,342/13,562 shared rosters whose absolute deltas were only
  `0.000015--0.000031`, while all 29,285 player-input rows were invariant to
  `3.55e-15`. Its unbounded per-draw generator summary also exceeded a single
  structured Cloud log payload. Score fields became visible before this was
  diagnosed and are recorded without alteration in
  `comparison_failure_diagnostic.json`: the full challenger is
  `33/23/13/7/5/3/2` at 187/194/200/210/220/230/240 versus incumbent
  `34/22/11/7/5/3/2`, with means `179.952` versus `180.121`. The repair is
  frozen after disclosure: keep books and score law unchanged, use an absolute
  candidate-mean tolerance of `1e-4`, report the max delta, collapse only
  per-draw role provenance for bounded logging, and run one comparator-only
  execution from a new immutable image. Thirty-two focused tests pass; the
  unchanged-books local validation cleared all invariants and returned neutral
  because 240/230/220/210 tied at `2/3/5/7`. Mechanical repair commit
  `cb9d851` then passed `859 passed, 2 skipped` in exact-tree Cloud Build
  `56664509-b59c-4005-ad22-720b7d4228d3`, publishing immutable digest
  `sha256:52cf9615755f3c4228accabd180601231d9d605d1a31bd1285a2ab78ea84f937`.
  Comparator-only repair `compare-served-tail-stage-b-repair-lpgt2`
  completed successfully on the unchanged books and confirmed zero failures,
  the `0.0000305176` maximum shared-mean delta, and final disposition neutral.
  The treatment keeps 240/230/220/210 at `2/3/5/7`, improves 200 `11→13` and
  194 `22→23`, declines 187 `34→33`, and lowers mean/median slightly. It does
  not pass the frozen high-tail law and is not promoted. Production remains
  identity; never regenerate this treatment or retry its factor. The lower-
  threshold gain is retained only as a prospective diversification clue.
- The next post-window-review action is frozen in
  `reports/2026-08-11-advanced-receiving-support-window-collection.md` and the
  declarative plan
  `automation/fantasy_points/plans/same-season-advanced-receiving-support-windows-v1.json`.
  It contains exactly 108 unique grouped-header Player exports: 56 cumulative
  prior windows for 2022--2025 target Weeks 5--18 and 52 last-four-prior
  windows for target Weeks 6--18; Week 5 is not duplicated because both
  definitions are Weeks 1--4. Every source week is strictly before its target
  week. This phase permits only collection and an outcome-blind support and
  redundancy audit of six preregistered receiving fields; it cannot inspect
  target outcomes, choose a predictive feature, generate candidates, score a
  lineup, or alter production. The plan check validates all 28 catalog reports
  and expands to exactly 108 artifacts, and all 23 focused downloader tests
  pass. Commit `5627f30` freezes and pushes this protocol. The outcome-blind
  audit implementation is now local behind
  `fantasy-points-advanced-receiving-support-audit`: it accepts no outcome
  fields; reports fixed 20/40/80-route support, six-field availability,
  cumulative/last-four overlap and predictor-only redundancy; and requires the
  exact complete hash-locked 108-export manifest. The audit was further
  hardened to emit JSON `null` for undefined constant-column correlations and
  to measure every route/feature support rate against the full eligible target-
  slate player universe, not just vendor-returned rows. The exact predictor-
  only BigQuery query has been schema-validated live. Twenty-seven focused
  tests, compilation, CLI discovery and whitespace checks pass; the complete
  866-test collection also finishes successfully with its expected skips.
  Exact next action: let the active headless collection finish,
  require a complete zero-failure manifest, then run the support audit without
  target outcomes and freeze any subsequent shrinkage/gate before querying
  them.
- The outside review's prospective Route Share recommendation is now frozen
  before any 2026 Route value or outcome in
  `reports/2026-08-11-route-share-2026-operating-contract.md`. The declarative
  2026 plan uses exactly source Week W-1 for target Weeks 2--18, and the
  downloader can select one target via `--target-week`. The new weekly importer
  requires one complete frozen-plan manifest, re-hashes and schema-checks the
  artifact, proves source < target, resolves against point-in-time 2026
  rosters while retaining unresolved audits, archives exact bytes to a
  create-only hash-addressed GCS object, and append-only rejects any stored
  value/hash conflict. `017k_fantasy_points_route.sql` derives last/l4/jump/
  cross-season features mechanically from strictly earlier observations and
  joins the same nullable, labeled-fallback fields to training and inference;
  the production model remains unchanged unless an explicit shadow model opts
  into the already registered four features. A dedicated leakage assertion
  enforces source season/week < target season/week, and backup discovery has a
  focused actual-table guard. The live target-Week-2 plan/catalog check
  validates all 28 reports and expands to exactly one Week-1 artifact; the
  combined Route/training/inference SQL passes a BigQuery dry run. The complete
  local suite passes `850 passed, 2 skipped`, with compilation and whitespace
  checks clean. The implementation and operating docs are pushed in `9cf0965`;
  the three operator review documents remain deliberately untracked.
  Exact-tree container build `8153b6d9-9e56-406d-b692-1d7cf215f7d4`
  succeeded from `8bd5588` and published digest
  `sha256:44b478167ffb39d09357678d5e6469bd67c330805846825edcea325775292377`.
  This is a build artifact only; no live job has been redeployed from it.
- The review's other prospective recommendation is frozen, without using the
  stale offseason samples, in
  `reports/2026-08-11-fantasy-points-live-matchup-capture-contract.md`.
  The `fantasy-points-matchups` command now captures exactly QB Coverage
  Matchup, WR Coverage Matchup and OL/DL Matchups before the target week's
  first kickoff. It selects and verifies Schedule Week W, presses Apply and
  checks its values-response contract, requires the vendor All/default input
  scope, downloads grouped-header CSVs, and rejects the whole capture unless
  every vendor team/opponent pair exactly matches the project-derived 2026
  target-week schedule. Exact passing bytes/manifests can be archived under
  create-only hash-addressed GCS names; Weeks 1--3 retain the vendor's
  prior-season-input regime label and Week 4 onward requires active-season
  inputs. The UI Weekly guide now includes the exact operating command. The
  three existing offseason samples were mechanically checked and correctly
  fail the 2026 Week 1 gate (QB: 33 unexpected/32 missing pairs; WR: 46/32;
  OL/DL: 32/32). Fifty-eight focused Matchup/Route/downloader/backup/status
  tests pass, the installed console entry point is discoverable, and diff/
  shell checks are clean. The first accepted capture must wait for the vendor
  surface to roll to a matching 2026 schedule. The data remains collection-
  only until a separately frozen prospective scoring gate passes; no current
  production path depends on it.
  The complete committed-tree suite subsequently passed all 858 collected
  tests (856 passed, two expected skips). The durable reconciliation of the
  outside review now records this completed Route/matchup implementation and
  the three in-flight immutable Stage B execution IDs.
- The independent Route scoring law is now frozen before 2026 data in
  `reports/2026-08-11-route-share-2026-shadow-gate.md`. It replaces rare-event
  Brier as the sole decision maker with an all-row CRPS primary, q95/q99
  pinball and exceedance calibration, while retaining 20/30 Brier, paired
  week-clustered uncertainty and a reported minimum detectable effect. It
  requires at least 12 paired slates/2,500 covered rows/40 thirty-point events,
  then permits a future-only exact-80 shadow whose final decision is the
  operator's 240/230/220/210/200 lexicographic weekly-max objective. No 2026
  outcome may tune or backfill an earlier forecast. Next implementation step:
  persist the isolated pre-lock control/treatment player distributions without
  exposing the Route registry to production.
- The next paid-data correlation study was frozen and pushed before any
  outcome join at commit `8263fe8`:
  `reports/2026-08-10-fantasy-points-coverage-fit-experiment.md`. It tests only
  four supported WR/TE matchup-fit features derived from strict season N-1
  Man/Zone, Coverage Separation, and opponent Defense Coverage Matrix data.
  It reports Spearman correlation with projection residuals, binary
  correlation and quintile lift for 30-point events, plus fixed control versus
  treatment Brier/MAE metrics on held-out 2024/2025. No alignment, individual
  route, route-break, field, support, or model sweep is licensed.
- The coverage-fit importer/diagnostic is implemented locally behind
  `import-fantasy-points-coverage` and
  `fantasy-points-coverage-diagnostic`, with guarded runner
  `scripts/cloud_fantasy_points_coverage_diagnostic.sh`. Audit-only import
  verified 2,093 normalized receiver rows (2,044 resolved, 48 unresolved, one
  ambiguous, one known duplicate suppressed) and all 128 defense seasons.
  The fixed support rules cover 1,709/5,927 2024 and 1,683/5,775 2025 WR/TE
  snapshot rows. Because those roughly 1,700-row folds are adequate but below
  the provisional 50% availability gate, that gate was explicitly amended to
  25% before any outcome query; features, support thresholds, folds, models,
  and score gates are unchanged. Sixteen focused Coverage/Advanced/Route
  tests pass, along with compilation, shell syntax, and whitespace checks.
  Initial build `bfb523d3-0652-42cf-8c36-357e7166afa5` passed 768 tests with
  2 skipped. The first guarded write created both private raw tables (2,093
  receiver rows and 128 defense rows). The required repeat check exposed a
  reserved BigQuery alias in the check query; no outcome diagnostic had run.
  The alias was fixed with a regression test, and the repeated guarded write
  reported `already-identical` for both tables. Corrected exact-tree build
  `82a58b86-1b13-49b1-a4f9-7e8633d4212d` passed 770 tests with 2 skipped and
  produced digest
  `sha256:d7ff29257db2153d95fc3be1f98223c02e6ddd215b8da925386e35239aa68e22`.
  Backup execution `backup-tables-5bgsw` succeeded with 11 snapshots, 5
  expected absent tables and zero failures; it created UTC-date snapshots
  for both new tables with exact 2,093/128 row counts. Frozen execution
  `fantasy-points-coverage-diagnostic-wbwlf` then returned
  `coverage-fit-player-tail-passes`: aggregate 30-point Brier improved
  `0.01813348→0.01809495`, 2024 improved, and 2025 worsened only 0.20%
  within the frozen 1% limit. Aggregate 20-point Brier worsened 0.24% and MAE
  worsened 0.0123, both mandatory diagnostics. Coverage was 28.83%/29.14%.
  This is a narrow signal, not direct adoption.
- The one licensed coverage lineup test is now preregistered before any
  coverage candidate or lineup outcome in
  `reports/2026-08-10-fantasy-points-coverage-tail-union.md`. After Route
  resolves the source mechanically, it adds exactly twelve novel 2024/2025
  candidates using `proj_tourney + 30 * (treatment_p30-control_p30)`, keeps
  earlier seasons byte-identical, reuses unchanged worlds/selection and
  returns exactly 80. Implementation commit `d977d0c` adds the score-free
  signal loader, replay attachment, twelve-novel-candidate generator, strict
  PIT/parity comparator, CLI and guarded Cloud runner. The full 776-test local
  suite passed, with compilation and whitespace checks clean. Conditional
  wrapper `scripts/prop_lock_coverage_tail_union.sh` is frozen to code
  `d977d0c` and refuses to launch until the Route report mechanically selects
  direct or Route source. Real score-free loader audits produced 1,709 2024
  rows using source season 2023 and 1,683 2025 rows using source season 2024,
  with finite deltas throughout. Exact-tree Cloud Build
  `b9a70848-cf5b-469e-83d4-de43f3af9315` from wrapper tree `848d977` passed
  775 tests with 2 skipped and produced immutable digest
  `sha256:d3d53256d8db9c34f120108bead5bb44a3ab2f512c2db4a7c6956eeb1e3d5534`.
  Route selected the corrected direct-role source, so use this digest for the
  one `direct` coverage panel; there is no dose/feature retry.
- The frozen coverage launch is active. Immutable preflight
  `replay-lockk1cov-smoke-mnxfg` passed. Panel
  `20260810-lockfix-e80-k1-role12-cov12-d977d0c` launched all six executions:
  `replay-lockk1cov-2019-kh9xl`, `replay-lockk1cov-2021-l9bd9`,
  `replay-lockk1cov-2022-4xgrm`, `replay-lockk1cov-2023-nvhqp`,
  `replay-lockk1cov-2024-tvgnt`, and `replay-lockk1cov-2025-ptnj6`.
  All six executions completed successfully: 2019 in 1h32m28s, 2021 in
  1h13m6.01s, 2022 in 1h21m13.89s, 2023 in 1h8m49.79s, 2024 in 1h28m5.73s,
  and 2025 in 1h26m12.01s. Check-only exact-80 acceptance execution
  `accept-replay-panel-t56n4` passed 27,468 candidates across 107 exact-80
  slates with replay/live parity. Coverage candidates were 1.6% of the pool
  and 0.2% of selected slots; acceptance's selected 187/194/200 remained
  `34/22/11`. Frozen comparator execution
  `fantasy-points-coverage-tail-union-gxfwg` then passed every mechanical
  check. It added 432 novel candidates and changed 33 selected slots in each
  direction, but all 107 weekly maxima tied the source exactly. Selected
  187/194/200/210/220/230/240 remained `34/22/11/7/5/3/2`, as did the pool
  oracle `42/28/16/9/5/3/2`; disposition is `keep-source-incumbent`. This
  prior-season coverage candidate arm is closed with no retry.
- The operator supplied an outcome-viewed outside review of the paid Fantasy
  Points data. Its repository-verified disposition is tracked in
  `reports/2026-08-11-fantasy-points-utilization-reconciliation.md`. Weekly
  Route Share remains the clearest incremental asset, but the review omitted
  that the same four Route features worsened held-out residual MAE in both
  folds and aggregate (`2.882990→2.892476`) while improving tail Brier; a
  future full component-model test is therefore open but not a demonstrated
  mean repair. The review also incorrectly called Defense PROE redundant:
  current SQL joins only the offense's own lagged PROE, while the vendor
  Defense PROE is distinct opponent context. Target/Snap require an
  outcome-blind agreement audit before closure, and an early-week Advanced
  retry would still be an outcome-viewed subset. Do not alter the frozen
  unions or restore a significance veto. The eventual 2026 Route path needs
  an idempotent weekly ingest contract; the current importer is historical
  and hash-locked. A shareable operator-facing description of all six weekly
  report families and their current priority is tracked in
  `reports/2026-08-11-fantasy-points-weekly-reports-summary.md`.
- The vendor-window semantics audit is now complete for the first priority
  families. Advanced Receiving Weeks 1--4 versus 5--8 returned 285/299
  players, every populated `G<=4`, distinct hashes and zero unchanged common
  players across `G/RTE/TGT/YDS/FP`. Defense and Offense Coverage Matrix each
  returned 32/32 teams with `G=4` and distinct hashes. Advanced Passing,
  Advanced Rushing, Man-vs-Zone, Separation by Coverage/Alignment, RB+WR
  Efficiency and detailed Snaps also returned distinct exact-window files
  with `G<=4`. This opens same-season strictly prior-week inputs; it does not
  alter the completed N-1 verdicts or in-flight frozen coverage union. The
  full catalog/redundancy disposition is tracked in
  `reports/2026-08-11-fantasy-points-filter-surface-audit.md`.
- The outcome-blind exact-window redundancy audit is tracked in
  `reports/2026-08-11-fantasy-points-redundancy-audit.md`. Existing
  strictly-prior target/air-yard/snap shares, XFP, YPC and YPT reproduce the
  corresponding vendor values closely (typically 0.95--1.00 correlations),
  so they are excluded from bulk model search. Fantasy Points separation is
  distinct from NGS separation, and recent defensive shell deployment has no
  close existing feature. A second outcome-blind screen found Advanced
  Passing `HERO %`, deep-throw rate, pressure rate, turnover-worthy throw
  rate, checkdown rate and `PrROE` only weakly/moderately aligned with the
  nearest existing QB inputs; that complete process family is the best
  follow-up after the coverage diagnostic. Advanced Rushing is somewhat more
  redundant, although missed tackles forced per attempt remains distinct.
  No target-week outcome or residual was read and no second model test is yet
  licensed. A compact same-season Man/Zone diagnostic was
  therefore preregistered before any outcome join in
  `reports/2026-08-11-fantasy-points-same-season-coverage-protocol.md`.
  Its plan contains only Man-vs-Zone, Separation-by-Coverage and Defense
  Coverage Matrix for seasons 2022--2025, target Weeks 5--18 and exact
  last-four-prior windows. Plan/catalog validation expanded 168 safe exports.
  First bulk run `20260811T040729Z__same-season-coverage-last-four-v1` was
  stopped and rejected after the importer proved its apparently filtered
  files contained stale full-2025 rows (`G=17/18`). No row was consumed.
  The downloader now awaits and validates the exact report-values POST,
  rendered game counts, and downloaded Season/G scope. Live regression run
  `20260811T042431Z__apply-scope-regression-check` passed with 299 Season-2022
  rows and `G=1..4`. Run
  `20260811T042759Z__same-season-coverage-last-four-v1` safely completed all
  112 receiver exports, then stopped before the first matrix export because
  the rendered-row guard assumed a visible Season cell that the team grid
  omits. No matrix file was accepted. The guard now recognizes the actual
  Rank/Name/G layout while Apply and CSV gates still enforce Season. Live
  regression `20260811T053128Z__coverage-matrix-window-semantics-v1` passed
  two exact 32-team windows. New immutable run
  `20260811T053208Z__same-season-coverage-last-four-v1` revalidated and
  reused the exact 112-file prefix and is collecting the remaining matrices;
  do not consume it until its final manifest passes the locked importer. The importer,
  same-season PIT attachment/diagnostic, CLI commands and focused tests are
  implemented in the working milestone without reading outcomes. The two new
  raw table names are explicit daily-backup members and also match automatic
  Fantasy Points table discovery.
- The next distinct paid-data family is frozen before any exact-window
  Advanced Passing outcome join in
  `reports/2026-08-11-fantasy-points-same-season-advanced-passing-protocol.md`.
  Its tracked 56-export plan uses seasons 2022--2025, target Weeks 5--18 and
  exact W-4:W-1 windows. The treatment is the complete predeclared QB
  process-rate/time block with an 80-dropback support floor; walk-forward
  held-out seasons are 2023--2025 and only aggregate 30-point Brier plus 50%
  per-fold coverage gates the mechanism. The manifest-locked importer,
  strict-prior attachment, walk-forward diagnostic, CLI and explicit backup
  member are implemented; 12 focused coverage/passing/backup tests pass and
  the real 52-row schema sample parsed all 22 treatment features. Collection
  must wait for the active coverage plan to finish; no table write, outcome
  diagnostic or lineup arm has started.
- Exact-tree Cloud Build `adc359ee-ee1d-4914-a251-680cf05dd221` from commit
  `34dfaa6` passed 801 tests with 2 skipped and produced immutable image
  `sha256:b1292d1ed171e20edf94e8a2f6ded5d63fdb1f83e9daa91e8d3acb6f37fa7d98`.
  Use this digest for both same-season player-tail diagnostics after their
  respective manifest-locked imports; never run from mutable tag
  `same-season-data-34dfaa6`.
- Corrected same-season coverage run
  `20260811T053208Z__same-season-coverage-last-four-v1` completed all 168
  artifacts with zero failures. Audit normalized 16,482 receiver windows
  (16,119 resolved, 363 unresolved, zero ambiguous, three duplicate groups
  suppressed and 6,287 supported) and 1,792 defense rows across all 56
  target windows/32 teams. Both private tables were created; the mandatory
  repeat returned `already-identical`. Backup snapshots
  `fantasy_points_receiver_coverage_l4_20260811` and
  `fantasy_points_defense_coverage_l4_20260811` exist with exact
  16,482/1,792 rows. The one-shot cloud runner ran once with immutable digest
  `sha256:b1292d1e...7fa7d98`.
- Frozen execution `fantasy-points-same-season-coverage-k2zt2` completed
  successfully and returned `same-season-coverage-player-tail-fails`.
  Supported coverage was 23.41%/22.74%/21.79% in held-out 2023/2024/2025,
  below the frozen 30% gate in every fold, and aggregate 30-point Brier
  worsened `0.02956174→0.02971345`. Aggregate 20-point Brier also worsened
  `0.09749424→0.09760344`; residual MAE improved slightly
  `5.67203→5.66299`. The registered correlations were small and unstable.
  Durable artifacts are tracked under
  `reports/fantasy-points-same-season-coverage-runs/20260811-fp-same-season-coverage-l4-v1/`.
  The exact same-season coverage mechanism is closed with no candidate union
  or retry; proceed to the already-preregistered Advanced Passing collection.
- The auditable Playwright downloader under `automation/fantasy_points/` and
  `ops/fantasy_points_downloads.py` is authenticated and operational. It uses
  a persistent profile outside the repository, never commits credentials or
  licensed CSVs, validates the live vendor catalog, runs sequential exports,
  names every file by report/season/source weeks/target week, and writes a
  SHA-256/CSV-shape/retrieval-time manifest. Plans support explicit windows
  and generated cumulative-prior or last-four-prior target-week policies;
  invalid same/future-week source windows fail closed. Direct authenticated
  report routes, custom Headless UI Season/Week controls, context-first
  navigation, mandatory `Apply`, post-Apply exact-week revalidation, custom
  export switches/action and bounded empty-SPA retries are implemented.
  Playwright 1.62, Chromium 151 and system libraries are installed. Seventeen
  focused downloader tests pass. Successful ignored manifests include
  `20260811T033115Z__advanced-receiving-window-semantics-v1`,
  `20260811T033342Z__coverage-matrix-window-semantics-v1`, and
  `20260811T035458Z__coverage-matrix-offense-window-semantics-v1`. Never
  record or request credentials in chat or Git. Long interrupted plans can
  now start a new immutable run with `--reuse-from`; the downloader rechecks
  the exact plan hash, ordered filters, file hash/shape and Season/G scope of
  every copied prefix artifact. The original run is never mutated.
- The live Fantasy Points menu is now guarded in full: exactly 28 NFL reports,
  of which 25 support historical Season + Week(s) plans and only QB Coverage,
  WR Coverage and OL/DL Matchups remain nonhistorical/prospective. The new
  remainder plan sampled both 2025 Weeks 1--4 and 5--8 for all nine previously
  unexercised historical families. Immutable resumed run
  `20260811T062906Z__remaining-catalog-window-semantics-v1` completed all 18
  exact-scope exports. Two fail-closed DOM repairs were required before that
  completion: metric halves may render as separate rows, and Routes Run has
  hidden title copies before its visible heading; Fantasy Points Scored also
  uses Rank/Name/POS/G identity rows. Twenty focused downloader tests and live
  scope regressions pass.
- The remainder audit found no missed immediate priority. Basic stats, Bell
  Cow, detailed Fantasy Points and Routes Run are redundant; Routes Run's
  alignment counts correlate 0.9987--0.9998 with Separation by Alignment.
  Named routes are too sparse over four weeks. Broader Horizontal/Vertical
  route-break groups are the only new lead, with 104--122 players at 20-route
  support per window; keep that lead outcome-blind and behind the already
  preregistered Advanced Passing diagnostic.
- Advanced Passing collection
  `20260811T063609Z__same-season-advanced-passing-last-four-v1` completed all
  56 exact W-4:W-1 artifacts with zero failures. Audit normalized 2,879 QB
  windows (2,868 resolved, 11 unresolved, zero ambiguous, 1,636 supported at
  80 dropbacks). The private table was created and the required repeat
  returned `already-identical`; backup
  `fantasy_points_advanced_passing_l4_20260811` is verified at 2,879 rows.
  One-shot runner `scripts/cloud_fantasy_points_same_season_passing.sh` is
  frozen to the source run/count, accepted panel and immutable image. Launch
  it once with digest `sha256:b1292d1e...7fa7d98`, then record the one
  preregistered result with no scientific retry.
- Frozen execution `fantasy-points-same-season-passing-s887m` completed
  successfully and returned `same-season-passing-player-tail-fails`.
  Supported accepted-QB coverage was 28.39%/26.88%/25.96%, below the 50%
  gate in every fold. Aggregate 30-point Brier worsened
  `0.06357934→0.06628405` and declined separately in 2023, 2024 and 2025;
  20-point Brier worsened `0.19692595→0.20648459` and MAE
  `6.41074→6.67482`. Durable artifacts are under
  `reports/fantasy-points-same-season-passing-runs/20260811-fp-same-season-passing-l4-v1/`.
  The exact Advanced Passing mechanism is closed with no candidate arm or
  retry. Next use the catalog audit's outcome-blind route-break support lead;
  do not test sparse individual named routes.
- The next outcome-unseen mechanism is frozen before collection in
  `reports/2026-08-11-fantasy-points-same-season-route-shape-protocol.md` and
  plan `same-season-route-shape-last-four-v1.json`. It uses only the four
  independent Horizontal/Vertical/Static/Shallow route-count shares, with
  Backfield implicit, Overall routes >=30, seasons 2022--2025, target Weeks
  5--18 and exact W-4:W-1 windows. The five vendor counts partition Overall
  routes exactly in both samples; 30-route support covered 58.2%/52.2% of
  accepted WR/TE rows with prior activity. No conditional efficiency,
  separation score, named route or outcome-selected field is licensed.
  Preregistration commit `99f665d` was pushed before implementation. The
  manifest-locked importer, strict-prior attachment, frozen walk-forward
  diagnostic, CLI and explicit daily-backup member are now implemented.
  The complete 812-test offline suite passes with one expected skip;
  compilation, CLI discovery and whitespace checks are clean. Immutable run
  `20260811T073453Z__same-season-route-shape-last-four-v1` then completed all
  56 exact exports with zero failures. The outcome-blind importer normalized
  16,482 receiver windows (16,119 resolved, 363 unresolved, zero ambiguous),
  suppressed three duplicate groups, validated exact component sums for all
  16,485 source rows and marked 9,489 rows supported. The private table was
  created and the mandatory repeat returned `already-identical`. Backup
  execution `backup-tables-p8ckj` completed successfully; snapshot
  `fantasy_points_route_shape_l4_20260811` has exactly 16,482 rows. One-shot wrapper
  `scripts/cloud_fantasy_points_same_season_route_shape.sh` is frozen to the
  source run/counts, accepted panel and an immutable image. Exact-tree Cloud
  Build `1dfbb3a2-9ab5-410a-933c-0913af4f17f1` from commit `3039af9` passed
  811 tests with two expected skips and published digest
  `sha256:35283c02d0be0bfb1be32fd4c9f8a3d9ee81da15ff20e6dc6d471772a11f3d76`.
  Frozen execution `fantasy-points-same-season-route-shape-fsrdg` completed
  successfully with disposition `same-season-route-shape-player-tail-fails`.
  Held-out support passed at 34.32%/33.60%/34.20%, but aggregate 30-point
  Brier worsened `0.02080521→0.02094089` and worsened in all three folds.
  Aggregate 20-point Brier worsened `0.07253747→0.07256688`; residual MAE
  worsened `4.92840→4.93420`, and correlations were small. Durable artifacts
  are under `reports/fantasy-points-same-season-route-shape-runs/20260811-fp-same-season-route-shape-l4-v1/`.
  The mechanism is closed with no candidate union or retry. No lineup or
  production policy changed. Next perform an outcome-blind strict-prior
  audit of the already downloaded weekly Defense PROE series, the remaining
  distinct opponent-context question, before licensing any model test.
- The outcome-blind weekly Defense PROE audit is now complete. The four
  registered licensed files normalized to 2,174 unique defense-game rows.
  A strict W-4:W-1 mean with at least three games covered all 1,646 scheduled
  defense-week contexts in target Weeks 5--18 for every 2022--2025 season.
  Its maximum absolute Spearman correlation with the nine existing opponent
  inputs was only 0.2955; no outcome column was queried. One single-feature
  QB/WR/TE diagnostic is frozen before outcomes in
  `reports/2026-08-11-fantasy-points-defense-proe-protocol.md`: heldouts
  2023--2025, 90% per-fold coverage and strictly improved aggregate 30-point
  Brier. The private raw table was created with 2,174 rows and the mandatory
  repeat returned `already-identical`. Backup execution `backup-tables-bd497`
  completed successfully; snapshot `fantasy_points_defense_proe_20260811`
  has exactly 2,174 rows. The frozen diagnostic, CLI and one-shot runner are
  implemented; eight focused Defense PROE/backup tests plus compilation,
  CLI discovery, shell parsing and whitespace checks pass. Exact-tree Cloud
  Build `6b84f0cc-bda4-434f-92ba-1b829f5a8c3d` from commit `e34a078`
  passed 815 tests with two expected skips and published immutable digest
  `sha256:0450ef0f2e3b332d7bf415263e044e081111644c25c001d92e94e71bc9ba6573`.
  Frozen execution `fantasy-points-defense-proe-cfvsv` completed successfully
  with disposition `defense-proe-pass-game-tail-fails`. Coverage was 100% in
  all three held-out folds, but aggregate 30-point Brier worsened
  `0.0092894466→0.0092929218`; 2023 and 2025 improved slightly while 2024
  worsened. Aggregate 20-point Brier also worsened
  `0.0334110003→0.0334847264`; residual MAE improved slightly
  `2.7439164→2.7432783`. Descriptive correlations were tiny and sign-unstable.
  Durable artifacts are under
  `reports/fantasy-points-defense-proe-runs/20260811-fp-defense-proe-l4-v1/`.
  The exact mechanism is closed with no candidate union or retry; no lineup
  or production policy changed. Next freeze the full weekly Route Share
  component-model test already left open by the utilization reconciliation,
  without changing its four registered Route inputs after outcomes.
- The full Route Share component-model test is now frozen before any new
  component prediction, simulation or lineup outcome in
  `reports/2026-08-11-fantasy-points-route-component-protocol.md`. It adds
  exactly `fp_route_share_last/l4/jump/cross_season` to same-code K=1
  LightGBM components, evaluates active corrected Sunday-main RB/WR/TE rows
  in held-out 2023--2025, and gates only on 80% per-fold prior coverage plus
  strictly improved aggregate 30-point Brier. Component errors, composed
  point MAE/CRPS, 20-point Brier, quantile exceedance, folds and positions are
  mandatory diagnostics, not vetoes. This is explicitly retrospectively
  motivated because the auxiliary Route outcomes are already viewed; no
  threshold, position subset, coefficient, window, model or feature retry is
  licensed. Next implement the outcome-free attachment/control/treatment
  harness and focused tests, then commit before its one immutable Cloud run.
  A pre-implementation clarification makes all eleven component diagnostics
  use QB/RB/WR/TE Sunday-main rows while the composed primary gate uses only
  Route-relevant RB/WR/TE rows, and pins the adopted possession/team-factor
  simulator; no outcome had been generated under either arm.
  The strict-prior full-panel attachment, K=1 control/treatment harness,
  supported component metrics, empirical CRPS, common-seed 10,000-draw
  simulation, frozen gate, CLI and one-shot Cloud runner are now implemented.
  Route fields are opt-in candidate features only; production is unchanged
  with `EXTRA_FEATURES` unset. The live source contract is exactly 26,881
  resolved rows, four hashes and 1,029 players. Thirty-four focused Route,
  component, feature-set and status tests pass; compilation, CLI discovery,
  shell syntax and whitespace checks are clean. Commit/push this outcome-free
  implementation. Exact-tree Cloud Build
  `fac5d0cb-67d9-4272-9934-80bda8b429ac` from commit `e19df7f` passed 821
  tests with two expected skips and published immutable digest
  `sha256:39d656915f75f67a41b0543456d16acda951f5b2fb4f5b92c09b2fa209827d7b`.
  Outcome-free preflight found all 28,091 accepted 2023--2025 QB/RB/WR/TE
  keys in the training table, with zero position or actual-score provenance
  mismatches. Frozen execution `fantasy-points-route-components-xvvbf`
  completed successfully with disposition `route-share-component-tail-fails`.
  Prior coverage passed at 95.71%/96.06%/96.60%, but aggregate 30-point
  Brier worsened `0.0140014643→0.0140280477`; 2023 improved while 2024 and
  2025 worsened. This is nevertheless the first paid-data component result
  with a consistent mean/distribution-quality gain: composed point MAE
  improved in all three folds and aggregate `3.7879193→3.7315403`, while
  CRPS improved `2.5794510→2.5687227`. Aggregate 20-point Brier worsened
  `0.0499138020→0.0501555362`, and q90/q95/q99 exceedance moved farther
  above nominal. Durable artifacts are under
  `reports/fantasy-points-route-component-runs/20260811-fp-route-components-v1/`.
  Under the tail-first gate, the exact historical component mechanism is
  closed with no lineup arm, calibration retry or production change. Preserve
  the exact Route contract only as a 2026 prospective shadow candidate while
  continuing to the next paid-data hypothesis, preregistered before its
  outcomes; do not describe the mean gain as evidence of improved
  extreme-lineup selection.
- Contest-placement/ROI evidence is now summarized durably in
  `reports/2026-08-10-contest-placement-roi-audit.md`. The local 2025 files
  are first-place-only; BigQuery has 103,556 ownership rows but no
  `contest_entries` table and zero contest-fill rows, so historical ranks
  2--5 and realized GPP ROI cannot currently be computed. Across 68 known
  Millionaire winning lines the corrected direct-role book is 0 wins, 0
  within 20, 2 within 30, 8 within 40, with 57.14 mean gap. On the one 2025
  Week 5 contest with supplied min-cash metadata, 3/80 direct-role lineups
  clear the 169.34 Milly min-cash line and best is 190.04 versus the 246.82
  winner. Preserve full 2026 standings and payout curves immediately after
  settlement; simulated ROI remains an internal upper-bound diagnostic, not
  a bankroll forecast.
- The README season-start schedule and in-app Weekly guide now make the
  ephemeral data requirement explicit: every Monday/Tuesday, upload Entry
  History and preserve the full standings CSV for one target GPP per slate.
  Winner-only roster files such as `reports/2025-milly-rosters.csv` contain
  exactly nine first-place players per week and cannot recover ranks 2--5 or
  realized ROI. The focused UI/status suite passes 13 tests.
- The passed Route Share signal will now be tested from the direct-role
  incumbent. Before launch, `scripts/prop_lock_route_tail_union.sh` freezes
  treatment `20260810-lockfix-e80-k1-role12-route12-aa087b8`, generator code
  `aa087b8`, the exact direct-role settings, and twelve Route candidates on
  2024/2025 only. Use immutable generation digest
  `sha256:b907bc6242d6b872cf10e4ff9ea59e56d89a1b99861780007eb767636a97041c`.
  The wrapper requires the direct-role promotion record. Shell syntax and
  whitespace checks passed. Immutable 2024 preflight
  `replay-lockk1route-smoke-vg5w8` passed, and all six immutable season jobs
  are running: `replay-lockk1route-2019-xmlzn`,
  `replay-lockk1route-2021-qqfch`, `replay-lockk1route-2022-mg9ns`,
  `replay-lockk1route-2023-bn27p`, `replay-lockk1route-2024-5lbcf`, and
  `replay-lockk1route-2025-vm6zd`. All six completed successfully. Exact-80
  check execution `accept-replay-panel-gw5qm` passed all 107 slates. Frozen
  comparison `fantasy-points-route-tail-union-nqx99` returned
  `keep-corrected-incumbent`: the union contained all 27,036 source rows and
  432 novel Route candidates, changed 25 selected slots in each direction and
  selected 10 Route rows, but all 107 weekly maxima tied exactly. Selected
  187/194/200/210/220/230/240 remains `34/22/11/7/5/3/2`, mean weekly best
  `180.1207`, median `178.44`. The Route lineup arm is closed with no retry;
  do not promote its staging rows. Use the direct-role incumbent as the
  coverage source and as the no-floor incumbent unless a later arm promotes.
- The preregistered corrected no-floor candidate union finished generation. Its
  launcher had required the never-launched CE12+role branch; before any
  corrected no-floor generation or outcome read, the protocol and launcher
  were amended to require the accepted direct-role source
  `20260810-lockfix-e80-k1-role12union-8677d21`. The independent no-floor
  treatment remains byte-for-byte the frozen K1 binary ablation. Shell syntax
  and whitespace checks pass. Immutable preflight
  `replay-locknofloor-smoke-dzrqw` passed, and all six season jobs completed
  successfully:
  `replay-locknofloor-2019-4ztp8`, `replay-locknofloor-2021-fjsrj`,
  `replay-locknofloor-2022-swpsn`, `replay-locknofloor-2023-lsb6k`,
  `replay-locknofloor-2024-kjftz`, and `replay-locknofloor-2025-kqwdn`.
  Check-only acceptance execution `accept-replay-panel-jbxkq` passed all 107
  exact-80 slates. The first union execution
  `corrected-floor-union-6rv2c` failed before producing any confirmation JSON
  or comparison result: `floor_union_confirmation.load_panel()` incorrectly
  required `research_eligible=TRUE` even for the staging add-on, whose 25,890
  valid rows are false by construction after check-only acceptance. A second
  pre-result launcher defect was also fixed: gcloud rejected the repeated
  direct-role panel value when source and incumbent were the same, so the
  unchanged CLI call is now passed as one shell argument. The staging loader
  now follows the already-validated Route loader rule—eligibility is required
  only in the accepted table—and a regression test covers both tables. This
  is an operational repair with no score outcome observed, not a parameter or
  decision-rule retry. Exact-tree Cloud Build
  `cb203be1-0765-479b-8fc4-e5d69c8dd056` succeeded and produced immutable
  evaluator digest
  `sha256:bcb88cff4e7f70ea34e0f52997254f420a39041e680eb4e26752ed2f9596fd69`.
  Repaired execution `corrected-floor-union-k8v5b` passed all 107 exact-80
  mechanical checks. It added 6,969 novel candidates and moved selected
  187/194/200/210/220/230/240 from `34/22/11/7/5/3/2` to
  `34/22/13/7/5/3/2`, with mean `180.1207→180.0084` and paired 5 wins/98
  ties/4 losses. Because every active 240→230→220→210 threshold tied, the
  frozen disposition is `keep-corrected-incumbent`; no-floor is not promoted
  and receives no retry. Durable artifacts are under
  `reports/floor-union-runs/20260810-corrected-role-nofloor-union-loaderfix/`.
- The operator's paid-data operations request is implemented on branch `main`
  at commit `ea6dca4`. The README season-start schedule now requires the final
  evidence-selected Fantasy Points reports, exact filters and pre-lock
  deadline to replace the temporary in-app Weekly-guide message before Week
  1; rejected reports will not become recurring downloads, and same-week
  completed data remains forbidden. Daily backups explicitly include
  `fantasy_points_route_share` and `fantasy_points_advanced_prior` and also
  discover every future base `nfl_raw.fantasy_points_*` table. Focused backup
  and UI/status validation passed 16 tests locally. Exact-tree Cloud Build
  `1253eb90-fca7-4bd2-bcac-e4b8e47b9a31` passed 764 tests with 2 skipped and
  produced immutable digest
  `sha256:3c5b0a6f2a450b252ef47a3b41600fd1517923f0f64672a8005593e53f7188a8`.
  Only year-round job `backup-tables` was updated; scheduler `s-backup`
  remains enabled at 07:00 UTC. Verification execution
  `backup-tables-9sqrb` completed with 9 snapshots kept/created, 5 expected
  absent tables and zero failures. It created
  `fantasy_points_route_share_20260810` (27,305 rows) and
  `fantasy_points_advanced_prior_20260810` (3,771 rows) in `nfl_backups`.
- The hash-locked prior-season Fantasy Points Advanced importer and frozen
  player-tail diagnostic are implemented at commit `b014748` behind CLI
  commands `import-fantasy-points-advanced` and
  `fantasy-points-advanced-diagnostic`. It imports only the preregistered
  Passing/Receiving/Rushing fields, resolves identities without outcomes,
  suppresses the known Brock Wright split rates, and attaches exactly season
  N-1 to target season N. Required event counts, Advanced-feature missingness
  and stable 30-point calibration deciles are emitted without changing the
  frozen models or gate. Twelve focused Advanced/Route tests pass; Python
  compilation, shell parsing and whitespace checks are clean. Outcome-blind
  audit-only import found 3,772 source rows, 3,771 normalized rows, 3,705
  resolved normalized rows, 64 unresolved source rows, two ambiguous source
  rows and one coalesced duplicate group. The guarded first write created
  private table `nfl_raw.fantasy_points_advanced_prior` with all 3,771 rows;
  a second write returned `already-identical` without mutation. Direct
  family/season verification found the expected twelve unique source hashes,
  3,705 resolved rows and only the known split duplicate. Exact-commit Cloud
  Build `cfe28aad-21be-4de0-9bcb-d90ff28c7ddc` from tree `755a216` passed
  762 tests with 2 skipped and produced immutable digest
  `sha256:1a0745b2a6aae3b78cfc4dfebb9be1661004c33e24fcf834d427705d9d1f1e6f`.
  Frozen execution `fantasy-points-advanced-diagnostic-vb9xz` completed
  cleanly in 1m44s with disposition `advanced-prior-player-tail-fails`.
  Coverage passed at 60.27%--66.87%, both folds and aggregate 30-point Brier
  improved slightly (`0.013278655→0.013268547` aggregate), but only WR/TE
  improved by position; QB and RB worsened. Aggregate 20-point Brier worsened
  `0.049025677→0.049177765` and residual MAE worsened
  `3.279949→3.303976`. The required two-position gate therefore fails. No
  Advanced candidate arm is licensed, and no position/field/model retry is
  allowed. Durable result artifacts are tracked under
  `reports/fantasy-points-advanced-runs/20260810-fp-advanced-prior-v1/`.
- `fantasy-points/qbCoverageMatchupExport.csv` was validated as a clean
  37-QB/32-column grouped export, SHA-256
  `888d31272b16b921af50fdeec0bcf20ed526873443495c4983079842a1b83c32`.
  The initial prospective interpretation was later disproved: its opponent
  pairs reproduce 2025 Week 1, not 2026 Week 1, while its metrics contain
  completed 2025 totals. It is a schema sample only and is forbidden from
  replays, diagnostics, promotion and live projections.
- The WR Coverage Matchup sample is also validated: 374 unique
  RB/FB/WR/TE rows, 38 grouped columns, no malformed populated values, and
  SHA-256
  `e0e369d4fee3130d0cfea29709d66ad9f74a6ae02f7495e2509c97ac6a221a5a`.
  Its matchup layer also reproduces 2025 Week 1 and has the same schema-only
  disposition. Future matchup snapshots require a mechanical target-schedule
  match plus a pre-lock retrieval timestamp before prospective use.
- The OL/DL Matchups sample and corrected matchup timing disposition are
  recorded on branch `main` at commit `797b6c0`. The file is a complete
  32-team/20-column grouped export, SHA-256
  `15dfbc9759b123d835998546610c3404893a0a9e227c67f865bdc4c31db349db`.
  Its 16 reciprocal pairs exactly match 2025 Week 1 while every row declares
  completed `Season=2025`, `G=17`; none of those pairs matches 2026 Week 1.
  It is hindsight schema evidence only, cannot support historical testing,
  and may be recollected prospectively only after the vendor rolls the page
  to the target schedule and before the shared slate lock.
- Paid acquisition follow-up: Basic Receiving, Routes Run and Bell Cow were
  declined as materially redundant with the existing weekly share and
  Advanced exports. The operator was asked to preserve 2022--2025 Receiving
  Man-vs-Zone and Separation-by-Coverage/Alignment/Routes/Route-Breaks files,
  plus one current WR Coverage Matchup snapshot. These are acquisition-only;
  none is licensed for a model, diagnostic or lineup arm until its schema and
  point-in-time availability are inspected and a distinct protocol is frozen.
- All four Receiving Man-vs.-Zone exports are now validated and hash-locked at
  commit `ded9344`: 545/517/528/526 rows in 2022--2025 with identical grouped
  Overall/Man/Zone/Single-High/Two-High schemas. They are season aggregates
  and therefore strict N-1 priors only. A vendor semantic defect makes QB
  `FP/RR` unusable (one receiving route paired with full QB fantasy scores as
  high as 336.46); any future treatment must exclude QB, freeze minimum route
  support before outcomes, and use a separate protocol. The files are not
  added to the already-frozen Advanced diagnostic. Continue acquisition with
  Separation by Coverage, Alignment, Routes and Route Breaks, then one
  current prospective WR Coverage Matchup snapshot.
- Receiving Separation-by-Routes is also validated at commit `525ee31`:
  540/513/522/519 RB/FB/WR/TE rows for 2022--2025, 95 unique grouped
  columns covering Overall plus twelve named route families, and no malformed
  numeric cells. Blank route splits are legitimate; the known 2022 Brock
  Wright split is the only duplicate. This is sparse full-season aggregate
  data, so any later N-1 diagnostic must freeze a small football-motivated
  feature block and minimum route support before outcomes. It is acquisition-
  only and does not alter the frozen Advanced treatment.
- Receiving Separation-by-Route-Breaks is validated at 540/513/522/519 rows
  with 41 grouped columns spanning horizontal, vertical, static, shallow and
  backfield concepts. It is a lower-dimensional possible alternative to the
  individual-route grid, not permission to test both after outcomes. The same
  N-1, minimum-support and separate-preregistration restrictions apply.
- Defense Coverage Matrix 2022--2025 is validated at exactly 32 teams and 22
  complete columns per season. Hashes and the unprefixed/misspelled 2025
  source filename are recorded in the intake report. The vendor repeats
  `FP/DB` within both Man/Zone and middle-of-field groups even with group
  headers, so any importer must assign those four fields by frozen positional
  context and reject reordered schemas. These are N-1-only acquisition data;
  acquire the four Offense Coverage Matrix files before considering a
  distinct scheme-matchup protocol.
- Offense Coverage Matrix 2022--2025 is also complete and validated at the
  same 32-team/22-column shape with all cells populated. Exact hashes are in
  the intake report. Both sides of a possible N-1 scheme-matchup signal now
  exist, but no diagnostic is licensed until the remaining Separation by
  Alignment family is acquired and a small support-aware feature block is
  frozen before any outcome join.
- Receiving Separation-by-Coverage 2022--2025 is complete and hash-locked on
  branch `main` at commit `7635c5e`: 540/513/522/519 rows with a stable
  38-column grouped schema spanning
  Overall, Man, Zone, Red Zone, and Cover 2/3/4/6. All populated metrics parse
  numerically; the skill-position identity universes match the other
  separation reports. Four 2024 Denver players each have one overall route
  without a Man/Zone/Red Zone assignment, now recorded in the deficiency log;
  future code must preserve that missing classification. The data remains
  strict season N-1 and acquisition-only. Separation by Alignment is the last
  requested historical receiver family before an outcome-unseen scheme
  protocol may be designed.
- Receiving Separation-by-Alignment is now also validated on branch `main`
  at commit `fcce6d5`: 540/513/522/519 rows with a stable 41-column grouped
  schema. Wide, Slot,
  Inline and Backfield route counts reconcile exactly to Overall for every
  row, every populated metric parses numerically, and the identity universes
  match the other separation reports. Exact hashes are in the intake report.
  This completes the requested historical receiver-separation acquisition;
  all files remain strict N-1, acquisition-only evidence until a small
  support-aware feature block and gate are preregistered before outcomes.

- Optimization has resumed with one new point-in-time information path rather
  than another selector sweep on the same 107 outcomes. Protocol
  `reports/2026-08-10-market-tail-disagreement-experiment.md` freezes a
  common-slate-lock diagnostic of signed production-versus-DraftKings
  alternate-yardage tail disagreement before querying its current-panel
  outcomes. Availability-only inspection found all 18 corrected main slates
  and 1,576/1,700 covered primary-market player rows in 2024/2025; 2023 has
  only four covered slates and is excluded. The diagnostic trains fixed
  low-capacity control/treatment models on 2024 and evaluates 2025 30-point
  Brier, 20-point Brier and residual MAE. If and only if it passes, one
  predeclared twelve-candidate market-belief union may run against live v2;
  it preserves incumbent scoring/selection worlds and uses the revised
  240→230→220→210 operational law. This is distinct from and does not reopen
  the rejected raw `ALT_CEIL`, `DIV_TILT`, or q99-wildcard mechanisms.
- Preregistration `53c78d8` and implementation `391934e` are pushed on
  `main`. Guarded implementation lives in
  `analysis/market_tail_disagreement.py`, CLI
  `market-tail-diagnostic`, and
  `scripts/cloud_market_tail_diagnostic.sh`. Nine focused market tests pass,
  Python compilation, shell parsing and `git diff --check` are clean.
- Full exact-tree validation build `9780568e-c338-49fd-af55-27909542625c`
  passed 727 tests with 2 skipped and produced immutable digest
  `sha256:4bed5d04fe433b0a9da6fc2a4f4d3464af8aeab9cafa653e30d4d3366841355e`.
  Frozen execution `market-tail-diagnostic-jg52t` then completed and failed
  the mechanism gate: 2024 edge-quintile residual separation was negative
  (`-0.3587`) despite positive 2025/aggregate signs, and held-out 30-point
  Brier worsened `0.0305295→0.0305408`. Residual MAE and WR/TE-only metrics
  improved slightly, but those diagnostics cannot override the frozen gate.
  No lineup union may launch, current live v2 is unchanged, and no quota was
  spent. Durable artifacts are tracked under
  `reports/market-tail-runs/20260810-market-tail-v1/`.
- While enforcing the alternate-prop common lock, a more important existing
  point-in-time defect was confirmed in `models.prop_market.market_points()`:
  historical standard props use each game's two-hour pre-kick close, so
  late-afternoon main-slate players receive lines written after the shared
  1 p.m. DFS lock. Availability-only audit found post-lock market use on
  1,842/1,788/1,716 accepted player-weeks in 2023/2024/2025; honest pre-lock
  rows are absent for 1,841/1,617/1,315 of them. Full correction and
  revalidation order are frozen in
  `reports/2026-08-10-prop-common-lock-correction.md`. Existing panels remain
  preserved but are point-in-time-ineligible for new decisions until K3,
  K1, CE and role are rebuilt on the fixed common-lock reader. The live
  mechanism remains provisionally served because freezer snapshots occur
  before lock, but its historical adoption evidence must be re-established.
  No quota spend is authorized.
- The strict reader is now implemented in `models/prop_market.py`. It derives
  the exact domestic Sunday-main cutoff from schedules, selects the latest
  row strictly before it (including a valid opening when no later row exists),
  logs excluded post-lock volume, and returns model-only fallback when honest
  coverage is absent. A companion repair consolidates multiple prop aliases
  to one player-week; the live warehouse read now returns 4,452/4,687/5,008
  unique priced player-weeks in 2023/2024/2025 with zero duplicates. Eleven
  focused market tests pass, including London/1 p.m./late/SNF cutoff, exact-
  lock exclusion, latest-valid selection, TD-only, no-prop and alias cases.
  Exact-tree Cloud Build and both immutable one-week replay smokes passed;
  the validated digest and durable execution IDs are recorded below.
- Revalidation runner `scripts/prop_lock_rebaseline.sh` freezes the corrected
  panel chain and 2024 preflight: K3
  `20260810-lockfix-e80-k3-8677d21`, K1
  `20260810-lockfix-e80-k1-8677d21`, CE12
  `20260810-lockfix-e80-k1-ce12-8677d21`, and role union
  `20260810-lockfix-e80-k1-ce12-roleunion-8677d21`. It is shell-parse clean;
  CE/role modes fail closed until their exact corrected source panel has been
  accepted. Cloud Build `3470d0d4-df09-4776-96e8-eaf5a76d0243` passed 729
  tests with 2 skipped and produced immutable generation digest
  `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`.
  Corrected K3 2024 preflight `replay-lockk3-smoke-tmjcp` passed, logging
  15,007 excluded post-lock prop rows and completing the full one-week
  true-80 path. Six K3 executions are now running:
  `replay-lockk3-2019-mf5jk`, `replay-lockk3-2021-b8w7x`,
  `replay-lockk3-2022-zsjcj`, `replay-lockk3-2023-dzhqz`,
  `replay-lockk3-2024-7dqbl`, and `replay-lockk3-2025-n95bb`. K1 2024
  preflight `replay-lockk1-smoke-zgm9n` also passed with the same corrected
  coverage. Its six executions are `replay-lockk1-2019-65m5t`,
  `replay-lockk1-2021-qwvqg`, `replay-lockk1-2022-gsddd`,
  `replay-lockk1-2023-75d9m`, `replay-lockk1-2024-9hlf4`, and
  `replay-lockk1-2025-nj6sn`. Both durable manifests are tracked under their
  `reports/panel-runs/` panel directories. Do not inspect partial scores;
  monitor only execution state and row completeness. Once all twelve are
  clean, run check-only acceptance on both and compare under the revised
  240→230→220→210 law before launching CE.
- `scripts/prop_lock_finish_controls.sh` now freezes that completion sequence:
  K3 check→promote, K1 check, then the existing ensemble mechanism comparator
  at exact 80 entries. It deliberately leaves K1 in staging for an explicit
  corrected tail-first decision. Shell parsing and `git diff --check` pass;
  the wrapper and handoff are pushed on `main` at `b6d4d38`.
- One previously untested combination is now preregistered before corrected
  outcomes are available: retain the complete corrected CE/role source pool,
  add the exact binary no-salary-floor K1 pool, and reselect the same 80
  entries at line 194. An outcome-free join of the preserved old pools found
  7,848 distinct no-floor rosters absent from the role pool (73.35/slate), so
  the mechanism is real rather than a relabeling. Full frozen construction,
  the 240→230→220→210 gate, no-retry rule, and live-feasibility requirement
  are in `reports/2026-08-10-corrected-floor-union-experiment.md`. Do not
  launch it until corrected K1→CE→role is complete; do not inspect an old or
  partial union score.
- Outcome-blind implementation support for that future test now lives in
  `research/candidate_union.py`. It preserves source candidate order, appends
  only add-on-novel rosters, fails closed if shared actual/mean/probability/
  world masks differ, reruns the unchanged 194 coverage selector at an exact
  entry count, and applies the highest-difference-first tail law. Thirteen
  focused union/portfolio tests pass; Python compilation and
  `git diff --check` are clean. No corrected no-floor score panel or union has
  been launched.
- `scripts/prop_lock_rebaseline.sh nofloor` now prepares the exact corrected
  K1 no-floor source `20260810-lockfix-e80-k1-nofloor-8677d21`. It refuses to
  launch until all 107 corrected role-source slates are present in the
  accepted table, then changes only `MIN_LINEUP_SALARY=0` from the frozen K1
  control. Shell parsing and whitespace checks pass. Do not invoke it before
  the corrected role comparison is complete; implementation readiness is not
  permission to inspect this score arm early.
- The floor-union evaluator is now complete behind CLI command
  `corrected-floor-union` and guarded runner
  `scripts/cloud_corrected_floor_union.sh`. It constructs exactly one union,
  requires shared rosters to match at all persisted 187/194/200/210/220
  masks, returns 80 entries, and applies 240→230→220→210 against both the
  role source and the actual corrected incumbent. Fifteen focused union,
  selector and portfolio tests pass; compilation, shell parsing and
  whitespace checks are clean. Exact-tree Cloud Build
  `a4079b03-2a23-453f-85b1-917550fc73c0` passed 742 tests with 2 skipped and
  produced immutable evaluator digest
  `sha256:ef0747eb3232ad797488dd8f38dcec522ea8815615120d31b2f7a39e332da85f`.
  The union has not been executed and no union score has been queried.
- A new no-cost information path is preregistered before reading its outcomes:
  lagged weekly NFL Next Gen Stats receiver separation, cushion, intended air
  depth, air-yard share and YAC above expectation. Availability-only audit
  found 8,976 2019--2025 rows and roughly 88% coverage weighted by candidate
  roster appearances. The frozen 2024/2025 low-capacity comparison prioritizes
  30-point Brier loss and requires nonworsening 20-point Brier/MAE plus
  coverage and fold safeguards. Full point-in-time construction and gate:
  `reports/2026-08-10-ngs-receiver-tail-experiment.md`. Do not query its
  outcomes or launch a feature/lineup arm until the corrected K1 control is
  complete and the protocol implementation is immutable.
- The NGS diagnostic is now implemented behind CLI command
  `ngs-receiver-tail-diagnostic`. It excludes week-zero aggregates and
  postseason rows, joins across careers with a strict earlier-week boundary,
  target-weights the last four observations, restricts evaluation to players
  actually present in the corrected K1 candidate pool, and fails closed on an
  incomplete true-80 source. A guarded Cloud Run harvester refuses to start
  until corrected K1 check-only acceptance is recorded. Twelve combined NGS,
  candidate-union, and participation tests pass; compilation, shell parsing,
  and whitespace checks are clean. No outcome query or NGS execution has run.
- A pre-outcome static audit corrected the NGS premise: production already
  uses same-season `separation_l4`, PBP air-yard share, and aDOT. The frozen
  control and implementation now include those raw fields explicitly; the
  treatment asks only whether cross-season last-four carry-forward plus NGS
  cushion/YACOE adds value. This correction occurred before any outcome or
  cloud diagnostic. Build `f68cedf9-2634-413c-bd8c-2e517691755d` contains
  the superseded control and must never run the NGS job even though validation
  completed. Corrected exact-tree build
  `e8dd679c-7a40-4e98-8525-31e4ecf700eb` from commit `2d75ba0` passed 738
  tests with 2 skipped and produced immutable digest
  `sha256:fe380648b9a146a95b8c4d942c484979b50f95762f16a277d704151106a82374`.
  Only that digest may run the NGS job after corrected K1 acceptance.
- Frozen execution `ngs-receiver-tail-diagnostic-nkb2h` subsequently
  completed cleanly after K1 check-only acceptance and returned
  `ngs-receiver-tail-gate-fails`. Coverage was 97.43%/98.25% in 2024/2025
  over 2,936 held-out player-weeks, but aggregate 30-point Brier worsened
  `0.0230785→0.0231012`, 20-point Brier worsened
  `0.0912537→0.0914343`, and residual MAE worsened `5.65602→5.66138`.
  No NGS lineup arm is licensed and no field/regularization/window retry is
  allowed. This does not negate the distinct passed true-route purchase
  diagnostic, because these NGS descriptors do not measure route volume or
  first-read opportunity.
- All twelve corrected-control executions completed cleanly. Both K3 and K1
  now contain 107/107 slates and exactly 8,560 selected rows (80 per slate).
  The apparent earlier K3 2019 Week 17 omission was only asynchronous
  warehouse-write lag; no repair, rerun, or score decision was made. No
  partial score was queried. Frozen finish wrapper
  `scripts/prop_lock_finish_controls.sh` is now running on the corrected
  generation digest; K3 check-only acceptance execution is
  `accept-replay-panel-tk27s`, followed by K3 promotion, K1 check, and the
  K1-versus-K3 ensemble comparison.
- K3 check-only acceptance passed in `accept-replay-panel-tk27s`: 25,778
  candidates, 50,098 immutable player rows, complete mean/label/artifact
  parity, and selected 187/194/200 counts `25/18/8` versus pool-oracle
  `38/22/12`. The subsequent promotion execution
  `accept-replay-panel-tbjlb` failed safely after the repeated acceptance
  pass because staging contains the new 210/220 masks (44 columns) while the
  older accepted table has 42; BigQuery rolled back the transaction and no
  candidate or snapshot row was promoted. `harvest_accept.py` now additively
  migrates its complete candidate schema and uses an explicit name-aligned
  target/source column list instead of positional `SELECT *`. Seven focused
  acceptance tests, compilation and whitespace checks pass locally. Build a
  fresh validation image, retry only K3 promotion from the unchanged staging
  panel, then resume K1 check and comparison; do not rerun generation.
- Repair build `a49f788a-9135-48a9-977b-3aebf7364712` passed 743 tests with
  2 skipped and produced digest
  `sha256:3f1aabf90065150e787c53fb5233741657c3b5219a2f231b444db899b8e14593`.
  Retry execution `accept-replay-panel-c6zpv` repeated the full K3 acceptance
  pass but failed before DML because BigQuery counts each of the repair's 44
  `ALTER TABLE IF NOT EXISTS` statements toward its table-update rate limit.
  Accepted candidates/snapshots still remain at zero. The superseding repair
  now reads the existing schema and performs one schema API update containing
  only missing fields, retaining the explicit name-aligned transactional
  insert. Validate a new image and retry promotion after the metadata-rate
  cooldown; do not reuse `c6zpv` or rerun generation.
- K1 check-only acceptance subsequently passed in
  `accept-replay-panel-9qw7z`: 25,766 candidates, the same 50,098 immutable
  player rows, and complete parity/legality/artifact checks. Its selected
  187/194/200/210/220/230/240 grid is `34/21/11/7/4/2/1`, mean weekly maximum
  `178.9327`, and pool-oracle grid `41/28/16/9/4/2/1`. The corresponding K3
  selected grid is `25/18/8/3/1/1/1`, mean `175.5402`, and oracle grid
  `38/22/12/5/1/1/1`. K1 therefore provisionally wins the revised high-to-low
  law at the first non-tied threshold (230), while tying at 240 and improving
  every lower reported threshold. Still require the frozen ensemble mechanism
  comparator after schema-safe K3 promotion before promoting K1 or launching
  CE.
- The final schema-safe acceptance repair at commit `9021a11` was validated by
  Cloud Build `8d4c5d94-52bc-4db2-9fef-8a6dbda65f85`: 743 tests passed with
  2 skipped, producing immutable digest
  `sha256:8dea3952912a8464882ed07d3286da50f59e96b2cc9425f93a2c1fd59820d76b`.
  K3 promotion execution `accept-replay-panel-25jbg` then completed cleanly.
  Direct warehouse verification found exactly 25,778 accepted candidate rows,
  50,098 eligible immutable player-feature rows and the complete 44-column
  accepted schema. K1 promotion execution `accept-replay-panel-rbbgs` also
  completed cleanly and direct verification found 25,766 accepted candidates
  plus 50,098 eligible feature rows. The workstation reboot interrupted only
  the local wrapper after the durable K1 execution; it did not affect the
  transaction.
- Frozen ensemble comparison `compare-adoption-panel-bspsn` completed with no
  mechanism failures. K1 changed only the ensemble member count, retained the
  identical player/input universe, and improved the exact-80 selected
  187/194/200/210/220/230/240 grid from K3's `25/18/8/3/1/1/1` to
  `34/21/11/7/4/2/1`; mean weekly best improved `175.5402→178.9327`.
  The revised tail-first operational gate passes, even though the superseded
  per-season stability gate does not. K1 is therefore adopted as the corrected
  control. Corrected CE12 source panel
  `20260810-lockfix-e80-k1-ce12-8677d21` was launched from the original
  generation digest. Preflight execution `replay-lockce-smoke-l7mzs` passed
  the full 2024 true-80 path in 8m10s. The six asynchronous executions are
  `replay-lockce-2019-bp8b2`, `replay-lockce-2021-6f6j6`,
  `replay-lockce-2022-j5lsm`, `replay-lockce-2023-2ntf7`,
  `replay-lockce-2024-7ff5s`, and `replay-lockce-2025-7gxrm`. Their immutable
  manifest is tracked under the CE12 panel directory. Monitor execution state
  and final row completeness only; do not inspect partial score outcomes.
- Before any corrected CE12 score was inspected, its comparator was updated
  to match the current operator objective. The original fixed 200-point gate
  remains in the report as an immutable scientific diagnostic, while the
  active fixed-budget disposition now uses the documented
  240→230→220→210 highest-difference-first decision plus mandatory mechanism
  validity. New guarded runner
  `scripts/cloud_compare_corrected_k1_ce_panel.sh` freezes the corrected K1
  and CE12 panel IDs. Nine focused CE/union tests pass; Python compilation,
  shell parsing and whitespace checks are clean. Comparator commit `db093ad`
  is pushed on `main`. Exact-commit Cloud Build
  `b3772bb8-e30a-4ca8-ac95-f9edc40911bd` passed 745 tests with 2 skipped and
  produced immutable acceptance/comparator digest
  `sha256:aab92b9120661e8764a4acd3d012298e5e5fcd746052452997a514f5afdaa6d1`.
  Use that digest only after CE12 reaches 107/107 complete slates; do not score
  or compare a partial panel.
- The operator purchased the standalone Fantasy Points Data Suite for $200.
  Licensed downloads are excluded by repository `.gitignore` under
  `fantasy-points/`. The untouched first export,
  `2022-receivingRouteShareReportExport.csv`, has SHA-256
  `68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637`,
  647 valid 2022 player rows, Weeks 1--18 and QB/RB/FB/WR/TE coverage. The
  2023--2025 Route Share exports are also complete and schema/range valid at
  621/625/637 rows; exact hashes are tracked in the intake report. One
  vendor-origin Brock Wright duplicate splits non-overlapping week blocks and
  must be coalesced by player-week; vendor team abbreviations and multi-team
  labels also require an explicit crosswalk. Continue untouched 2022--2025
  exports for the remaining Weekly Reports and Advanced Receiving before
  freezing the importer/schema. The four Fantasy Points Scored files are now
  also complete and valid, but are identity/scoring audits only rather than
  replacement labels. The four offense PROE exports are complete at exactly
  32 teams per season with valid weeks/game counts. Do not commit licensed
  source rows or use same-week postgame values in a replay.
  All four Snap Share exports also pass at 647/621/625/637 rows. The exact
  hashes, byte-identical extra 2024 file, and the replaced, filtered first 2022
  download caveat are recorded in the intake report. All four Target Share
  exports now pass at 647/621/625/637 rows with exact hashes in the intake
  report. All four Defense PROE exports also pass at 32 unique defenses and
  exact hashes recorded in the intake report. Advanced Receiving Player
  exports now pass at 545/517/528/526 rows with 63 common columns and exact
  hashes recorded in the intake report. They are full-season aggregates, not
  weekly histories, so they are eligible only as strict prior-season inputs.
  The known 2022 Brock Wright split requires count-aware coalescing. The
  separately named Defense Advanced Receiving files remain 32-team season
  aggregates and are not accepted as player history. Advanced Rushing Player
  exports are also complete at 354/334/322/329 player rows. Their two-row
  grouped schema cleanly identifies the repeated Zone and Man/Gap metric
  blocks; exact hashes are in the intake report. Like Advanced Receiving,
  they are strict prior-season inputs only: season N is forbidden for every
  target in season N and first becomes eligible in season N+1. Advanced
  Passing Player exports are also complete at 83/80/77/77 QBs with a clean
  grouped 59-column schema and exact hashes in the intake report; the same
  strict prior-season restriction applies. No further Fantasy Points download
  is currently requested.
- Before any Advanced value was joined to a target-season outcome, one narrow
  prior-season player-tail diagnostic was frozen in
  `reports/2026-08-10-fantasy-points-prior-season-advanced-tail.md`. It joins
  only season N-1 to target season N, uses fixed process-trait blocks for
  QB/RB/WR-TE, and evaluates 2024/2025 30-point Brier with position/fold
  safeguards. Outcome-blind coverage is 60.27%--66.87% across the required
  position/fold cells. Implement the exact hash-locked parser and diagnostic;
  no target-season aggregate, field subset or model retry is permitted.
- Corrected CE12 completed all 107 slates with season counts
  `17/18/18/18/18/18`, 25,766 candidate rows and exactly 8,560 selected rows.
  All six authoritative executions completed cleanly. Check-only acceptance
  `accept-replay-panel-55vrb` passed candidate/feature parity, legality,
  artifacts and exact-80 structure. Its selected 187/194/200 grid is
  `37/25/13` and the panel is mechanically eligible for comparison. Frozen
  K1-versus-CE12 comparison execution
  `compare-corrected-k1-ce-panel-s98dc` completed from immutable image digest
  `sha256:d4566a1031efd391ece5758dd294cd01069e5dae3d4f1bee5c04f0af6ec13b33`
  with zero mechanical failures. CE12 moved selected
  187/194/200/210/220/230/240 from K1's `34/21/11/7/4/2/1` to
  `37/25/13/6/3/1/1` and mean weekly best `178.9327→179.4993`; its pool
  oracle moved `41/28/16/9/4/2/1→44/30/17/9/3/1/1`. It therefore loses at
  the first non-tied active threshold (230) and also at 220/210. Frozen
  tail-first disposition is `reject`; do not promote CE12. Corrected K1
  remains the accepted incumbent. CE's rejection does not measure the
  distinct role-belief generator; freeze any direct K1+role test before
  generating or reading a corrected role outcome.
- Direct corrected K1+role confirmation is now frozen before any treatment
  generation in
  `reports/2026-08-10-corrected-k1-direct-role-union.md`. It excludes CE,
  retains K1's 40 boom candidates, and adds exactly 12 candidates using the
  pre-existing six role fields and seed 7331. Final output remains exactly 80
  and the only active decision is 240→230→220→210 at the first difference.
  Guarded generation runner `scripts/prop_lock_direct_role_union.sh`,
  comparator `scripts/compare_corrected_k1_direct_role.py`, and Cloud Run
  harvester `scripts/cloud_compare_corrected_k1_direct_role.sh` are
  implemented. Sixteen focused role/CE/union tests pass; both shell scripts
  parse and the comparator compiles. Build an exact-tree comparator image,
  then launch the single treatment panel from the original corrected
  generation digest
  `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`.
  Initial validation build `fbb4221a-7825-4999-903e-f02a0f9ab2cb` from
  preregistration/implementation commit `e0e1a04` was cancelled during its
  test step, before any image or panel launch: a prelaunch packaging audit
  found Dockerfile's explicit script allow-list omitted the new comparator.
  Commit `875164e` added that copy line. Superseding exact-tree Cloud Build
  `b45029c0-a715-403e-8dba-c3323e27da91` passed 756 tests with 2 skipped and
  produced immutable comparison digest
  `sha256:5319704c23ac40f30771a43b2fb6b4d012a7b2d8f610b980ecfd509ba55deb6b`.
  Launch the single direct-role treatment from the original corrected
  generation digest, then use this later digest for check/comparison.
- At approximately 15:18 CDT, an operational recent-log check on the final
  running 2022 CE execution unintentionally surfaced the already-written Week
  16 and Week 17 best-score log lines before the panel was complete. No gate,
  comparator, code, candidate construction, or planned next action was changed
  after that accidental exposure; all CE decision rules and the immutable
  comparator image had already been frozen. Do not use those two partial
  values for any decision and do not query further execution logs; monitor
  only status and row completeness until 107/107.
- Before joining any paid Route Share value to an outcome, the exact first
  paid-data diagnostic was frozen in
  `reports/2026-08-10-fantasy-points-route-share-experiment.md`. It normalizes
  only the four validated Route Share files, enforces source hashes and
  conflict-safe identity resolution, and adds exactly last/l4/jump plus a
  cross-season indicator under a strict earlier-week join. Corrected K1
  player folds train 2024 on 2022--2023 and 2025 on 2022--2024, using fixed
  Ridge/logistic controls. The active gate prioritizes aggregate and WR/TE
  30-point Brier with per-fold/coverage safeguards; 20-point Brier and MAE are
  diagnostics. Outcome-blind availability is 82.07%/82.95% in 2024/2025.
  Implement and validate this exact diagnostic without inspecting intermediate
  outcomes; no field/window/model retry is permitted.
- The Route Share-only importer and diagnostic are now implemented behind CLI
  commands `import-fantasy-points-route` and
  `fantasy-points-route-diagnostic`, with guarded runner
  `scripts/cloud_fantasy_points_route_diagnostic.sh`. Four focused tests pass;
  compilation, shell parsing and whitespace checks are clean. Audit-only import
  normalized 27,305 weekly rows; the first authorized `WRITE_EMPTY` created
  private table `nfl_raw.fantasy_points_route_share` with 26,881 resolved rows,
  1,029 resolved GSIS players, four exact source hashes and values in `[0,1]`.
  A repeated write returned `already-identical` without mutation. No outcome
  diagnostic had run at implementation time. Implementation commit `501760b`
  is pushed on `main`. Exact-tree Cloud Build
  `24d0a97b-b51e-43c0-a733-332f24064d25` passed 749 tests with 2 skipped and
  produced immutable digest
  `sha256:a08ae363d937a428849f62b3bd07ea7527d8dd4ab487496d0408fa3da9e49d42`.
  The single frozen diagnostic is now running as durable Cloud Run execution
  `fantasy-points-route-diagnostic-rthzs`. It completed successfully in 2m17s
  and passed every gate. Strict-prior coverage was 82.35%/83.02% in
  2024/2025; aggregate 30-point Brier improved
  `0.00968358→0.00965675`, and WR/TE 30-point Brier improved
  `0.00763166→0.00760188`, with nonworsening fold safeguards. The treatment
  also improved 20-point Brier; diagnostic-only MAE worsened slightly
  `2.88299→2.89248`. This licenses one separately preregistered Route Share
  candidate-union test but does not itself change production. The immutable
  final report is under
  `reports/fantasy-points-route-runs/20260810-fp-route-share-v1/`; do not retry
  or tune this player diagnostic.
- Before any Route Share lineup was generated or scored, its one licensed
  candidate test was frozen in
  `reports/2026-08-10-fantasy-points-route-tail-union.md`. After the corrected
  K1→CE12→role chain mechanically selects its incumbent, reproduce that source
  and add exactly twelve novel candidates per 2024--2025 slate using
  `proj_tourney + 30 * (treatment_p30 - control_p30)` from the same held-out
  Route models. Other seasons reproduce source exactly; production worlds and
  the 194 selector remain unchanged. Exact source containment/invariance and
  twelve novel candidates per treated slate are mandatory before applying the
  240→230→220→210 law. No dose/scale/model retry is allowed.
- The preregistered Route candidate construction is now implemented but has
  not run. It reconstructs the exact held-out control/treatment p30 models
  without requiring target outcomes, persists the strict-prior audit fields,
  and adds the paid signal only to the 2024/2025 candidate objective. The
  engine applies the incumbent pool cap first, then adds exactly twelve
  source-banned `route_tail` rosters using the frozen coefficient; unsupported
  doses, missing/non-finite signals, failed solves or duplicate rosters abort.
  Other seasons add zero candidates. Six focused Route tests plus the related
  generation/persistence/replay suites pass (61 tests total); compilation and
  whitespace checks are clean. Implementation commit `2c0f93b` is pushed.
  A post-commit audit found that the first implementation carried the delta
  into candidate construction but did not persist its source season/week and
  control/treatment probabilities. Those audit fields are now carried into
  the immutable feature snapshot, and the relevant 31 tests pass. Cloud Build
  `d01b4116-2abf-45af-b56c-1a0b1f7342bf` is therefore superseded even if it
  succeeds; build the audit-complete commit before any execution. Do not
  launch the arm until the corrected generator chain chooses its incumbent.
- The Route union protocol's artifact condition was clarified before any arm
  generation: whole NPZ checksums necessarily differ when twelve candidate
  rows are appended. Both artifacts must be present/hash-addressed, while all
  persisted shared-candidate actual/mean/probability/support fields must match.
- The guarded Route union evaluator is implemented behind CLI
  `route-tail-union` and `scripts/cloud_route_tail_union.sh`. It fails before
  scoring unless source containment/shared supports, exact 12-per-treated-
  slate Route provenance, zero additions elsewhere, strict-prior signal
  provenance, artifacts, exact-80 completeness, and persisted-selection
  reproduction all pass. Two focused evaluator tests plus 43 related tests
  pass; compilation, shell parsing and whitespace checks are clean. No Route
  lineup exists. Audit-complete generator build
  `6c96b5bb-5958-4b17-bf1a-7ec2bdcfc9d1` from commit `aa087b8` passed 751
  tests with 2 skipped and produced immutable generation digest
  `sha256:b907bc6242d6b872cf10e4ff9ea59e56d89a1b99861780007eb767636a97041c`.
  Evaluator build `cff83915-db3e-4576-b547-090f8c1cac0a` from commit
  `c94c0e6` also passed and produced immutable comparison digest
  `sha256:d4566a1031efd391ece5758dd294cd01069e5dae3d4f1bee5c04f0af6ec13b33`.
  Do not launch Route generation until the corrected CE/role chain chooses
  its incumbent.
- One corrected-history selector confirmation is now frozen before either
  corrected control outcome is read:
  `reports/2026-08-10-corrected-extreme-selector-confirmation.md`. After the
  K3→K1→CE12→role chain chooses its final mechanically accepted generator,
  apply the already-deployed prospective 220→210→200 lexicographic selector
  exactly once to that source pool and compare its same-80 weekly maxima at
  240→230→220→210. It excludes every other selector variant and cannot
  influence which generator pool is chosen. Guarded implementation is
  `research/extreme_selector_confirmation.py`, CLI command
  `corrected-extreme-selector`, and
  `scripts/cloud_corrected_extreme_selector.sh`; thirteen focused selector,
  union and portfolio tests pass, along with compilation, shell parsing and
  whitespace validation. Implementation/protocol commit `177c113` is pushed;
  exact-tree build `604b1496-5bc2-406f-9565-dd41c6870c96` passed 740 tests
  with 2 skipped and produced immutable digest
  `sha256:370695d6f576b6d71d770b4a0f9fa6745376167600188a481db51e9eedc34fce`.
  Use that digest for the eventual selector confirmation. No corrected
  selector score has been queried.
- The operator supplied an outside strategy review. Its reconciled,
  repository-verified disposition is tracked in
  `reports/2026-08-10-strategy-review-reconciliation.md`. The useful new
  direction is explicit opponent-field/payout simulation, which is distinct
  from the rejected ownership fade and supported by the cited primary DFS
  optimization research. It is prospective/data-blocked: the warehouse has
  103,556 aggregate ownership rows from 1,258 contests/72 slates and 68 winner
  rosters, but no historical opponent lineups, payout curves, field sizes,
  min-cash lines or duplication labels. Seek a metadata-only export first and
  use 2026 full standings for field-model validation. The review's proposed
  ordinary-tail widening reverses the measured calibration direction
  (`7.37%/0.72%` exceedance is conservative, not too thin); its claimed-new
  within-team Dirichlet mechanism already failed at K=20 and K=8; and its
  world-argmax proposal is the existing boom generator. Do not launch those
  three as new arms. Constant-budget candidate reallocation remains a lower-
  priority possible arm after the corrected queue, not a current sweep.

- The operator explicitly revised the operational objective after the valid
  role union improved the same 80-entry portfolio at every 210+ threshold.
  Scientific dispositions remain immutable, but season-sign requirements and
  the role gate's requirement to rescue previously sub-200 pools are no
  longer operational vetoes. The hard gates are point-in-time/mechanical
  validity, exact final entry count, reproducibility/live parity, and no
  hidden outcome-tuned parameter. The primary score comparison now proceeds
  from 240→230→220→210→200; lower thresholds, means and season signs are
  diagnostics. Full law and audit:
  `reports/2026-08-10-tail-first-adoption-review.md`.
- A fresh warehouse inventory covered every corrected-universe, complete,
  mechanically valid true-80 panel. The role union is the strongest: selected
  187/194/200/210/220/230/240 is `39/27/18/12/6/3/2`, mean `182.5725`, and
  pool oracle `48/32/22/13/6/3/2`. Against CE12/boom28 it improves 15 paired
  weekly maxima, declines on 6, ties 86, and has positive mean delta in five
  of six seasons. No older valid arm beats it under the revised high-tail
  law. Incomplete-universe and otherwise invalid panels remain ineligible.
- Repository policy `classic-k1-ce12-role12-boom28-v2` now names valid panel
  `20260810-e80-k1-ce12-roleunion-c616390`: K1 baseline registry `tail_k1`,
  alternate K1 registry `tail_k1_role`, exact six frozen role inputs, CE seed
  1701, role seed 7331, 12 CE / 12 role / 28 boom generation, line 194, $49k
  floor, 45/55 blend, and 80 final entries. The role candidates add only
  pre-selection compute. Prior `classic-k1-ce12-boom28-v1` is implemented as
  a labeled fallback if the role registry/load/quota fails.
- Live inference now lets each loaded booster materialize its own registered
  feature columns rather than depending on process-global `EXTRA_FEATURES`.
  This is required for a baseline and alternate-role registry to serve safely
  in the same web process. JSON exposes the baseline and role model versions,
  effective policy, and fallback flag; CSV headers expose the effective
  policy. A new isolated weekly role training job, early/late role-union
  shadow jobs, and two role-union freezer books are defined. Prospective
  freezer policy is `tail-first-v6-20260810` with eleven books.
- Branch `main`; implementation commits `031c0c1` and `75c8791` are pushed.
  Exact-tree Cloud Build `ab7073fa-a53b-4253-a481-9e47c150c7cd` passed `724`
  tests with `2` skipped in 353.27 seconds. The deployable immutable image is
  `sha256:41de2eaee84bb9eb72b07b6a96b35b7223951e4fa0c979780dd703b1c11d7349`.
  An earlier green build `3ca9d329-e5ce-44d3-be5b-ecbf381f7aec` is not the
  final tree and must not be deployed. Focused offline validation includes a
  real 80-lineup role-union build and the labeled CE-only fallback; Python
  compilation, shell parsing, deployment-contract validation, and
  `git diff --check` are green.
- Isolated role training execution `train-weekly-k1-role-zhd7w` completed
  successfully in 3m25.78s and registered all 11 K=1 component models as
  `pooled/components__tail_k1_role/2026-W33`. A read-back check proved that
  every component contains the exact six frozen role fields, while baseline
  `pooled/components__tail_k1/2026-W32` excludes them. Both registries report
  ensemble size one.
- Cloud Run service `nfl-dfs-app` now serves v2 from ready revision
  `nfl-dfs-app-00065-v8d`, with 100% traffic on the exact validated digest.
  Startup logs are clean. Existing IAP correctly redirects an unauthenticated
  `/health` request to Google sign-in, so the real authenticated
  UI -> 80 lineups -> DKEntries check remains a first-live-slate task rather
  than bypassing IAP. The complete offline live-builder path already passed.
- Jobs `train-weekly`, `train-weekly-k1`, `train-weekly-k1-role`,
  `project-slate`, `shadow-k1`, `shadow-k1-nofloor`, `shadow-k3`,
  `shadow-k1-roleunion`, `freeze-tail-early`, and `freeze-tail-late` are all
  pinned to the same exact digest. `scripts/verify_deployment.py --json`
  reports zero contract failures. The three new schedules
  `s-train-k1-role`, `s-shadow-k1-roleunion-early`, and
  `s-shadow-k1-roleunion-late` target the intended jobs and use the existing
  compute service account. All 17 seasonal schedulers are `PAUSED`; year-round
  ingestion, backups, scoring, trends, and freshness jobs were not changed.

- The predecessor/fallback `classic-k1-ce12-boom28-v1` comes from accepted
  panel `20260809-e80-k1-ce12-c616390`. Its true-80 selected weekly-max counts at
  187/194/200/210/220/230/240 remain `40/26/18/11/5/2/1`; mean/median are
  `181.1243/178.64`, and pool-oracle counts are `47/32/22/13/5/2/1`.
- A fresh accepted-panel audit found that the pool omits 36 of 612 player
  slots across 28 of 68 matched Millionaire winners, concentrated at WR (12),
  TE (11), and RB (7). Those missing slots averaged 21.11 actual points versus
  7.82 projected. The pool has an unselected weekly maximum on 25/107 slates,
  but only four nonredundant unselected oracles clear 200, so another flexible
  selector search is not justified on the same 107 outcomes.
- The 36 omitted winner slots average $4,128 salary and 5.88% realized
  ownership, with 61.1% below 5%, versus $5,644 and 13.88% for covered winner
  slots. Eleven misses are fast-role players and six are vacancy/promotions.
  Treat this as support for better cheap-player role inputs; the already
  rejected generic ownership-scoring arm remains closed.
- The existing point-in-time breakout analysis was run on the final accepted
  snapshots and persisted 27,266 same-slate/same-position matched pairs to
  `nfl_predictions.archetype_matched_pairs`. Fast-role-rise players produced
  +2.1908 mean DK points and +0.03791 probability of 20+ versus controls over
  5,540 pairs; both effects are positive in all six seasons. Vacancy/promotion
  produced +1.3849 and +0.01920 over 8,490 pairs, again positive in every
  season. Cheap-DST and cold-start/rookie states were negative and are not
  reopened.
- A separate walk-forward TabPFN calibration audit found fast-role q90/q99
  exceedance of 9.76%/1.06% and vacancy/promotion exceedance of 9.03%/1.20%,
  close to their nominal 10%/1% rates. Ordinary players were overestimated at
  7.37%/0.72%. This rejects a generic role-tail widening as the immediate
  path and supports one bounded test of the already-frozen role-belief
  candidate generator.
- Protocol `reports/2026-08-10-k1-ce-role-belief-experiment.md` freezes the
  exact pre-existing six role inputs, seed 7331, and 12-candidate dose before
  treatment outcomes. The union panel
  `20260810-e80-k1-ce12-roleunion-c616390` adds 12 role candidates to the
  accepted 12 CE / 28 boom allocation and must create at least two new
  role-caused 200-point oracle weeks. Only then may fixed panel
  `20260810-e80-k1-ce12-role12-c616390` replace 12 boom solves, yielding equal
  12 CE / 12 role / 16 boom compute and exact per-slate source pool sizes.
- The fixed scoring gate follows the operator's tail-first utility: at least
  +2 selected 200-point weeks; selected 210/220/230/240 and pool-oracle
  200/210/220/230/240 all nonworse; a novel role frontier; and full mechanical
  validity. Mean, 187/194 counts, and season signs are diagnostics, not vetoes.
  No parameter retry is allowed after a valid rejection.
- All six union seasons completed cleanly and immutable comparator execution
  `compare-k1-role-panel-ps9mx` returned a mechanically valid `reject` with
  zero failures. The union retained all 25,787 source rosters, added 1,269
  novel role rosters, held every common score/support value invariant, and
  reached 11 role-specific realized frontiers. However, it created zero new
  200-point weeks on slates whose source oracle was below 200 (required two),
  so the equal-budget fixed panel was not launched and remains closed. The
  originally rejected added-budget union moved selected
  210/220/230/240 `11/5/2/1→12/6/3/2`, oracle
  `13/5/2/1→13/6/3/2`, and mean `181.12→182.57`. That machine disposition is
  preserved, but the operator's documented tail-first override adopts the
  mechanically valid union because these are direct gains in the stated
  tournament objective. Tracked report and execution are under
  `reports/panel-runs/20260810-e80-k1-ce12-roleunion-c616390/`.
- New guarded runner/comparator scripts and focused tests are implemented.
  The comparator proves feature/common-world invariance, exact seed/lever
  identity, union containment, fixed pool equality, source CE preservation,
  and exact 12-role realization on all slates. `31` focused role/CE/budget
  tests pass; both shell scripts parse, the comparator compiles, and
  `git diff --check` is clean. The Docker image now explicitly packages the
  comparator.
- Preregistration/runner commit `c02cded` is pushed on `main`. Full validation
  build `35ec292e-94ea-48b2-8597-23292b77dbd3` passed `716` tests with `2`
  skipped in 387.33 seconds and produced immutable comparator digest
  `sha256:a410648bc20b10ec65e7ca49a2bc67108771067136259d73fad65f8cdb72087f`.
- Union preflight `replay-e80k1ru-smoke-l4fjb` passed on the frozen generation
  digest. The six exact asynchronous union executions are
  `replay-e80k1ru-2019-kn4jf`, `replay-e80k1ru-2021-6sj8b`,
  `replay-e80k1ru-2022-6n9gr`, `replay-e80k1ru-2023-t5r9v`,
  `replay-e80k1ru-2024-zg8lx`, and `replay-e80k1ru-2025-wtsxz`. Their immutable
  manifest is tracked under
  `reports/panel-runs/20260810-e80-k1-ce12-roleunion-c616390/`. Do not inspect
  partial scores or infer status from a job's latest execution.
- No Odds API historical quota was spent. Official historical player props
  are potentially useful from May 2023 onward, but route/target/alignment data
  is a more direct paid-data lead for the observed WR/TE misses. Any quota
  backfill remains a separately approved, credit-capped experiment.
- The ranked follow-on queue is now tracked in
  `reports/2026-08-10-scoring-opportunity-roadmap.md`. The preferred paid-data
  pilot is Fantasy Points Data only if checkout is below $200 and full
  2022-2025 CSV exports are confirmed; requested fields and the walk-forward
  player-tail -> union-oracle -> fixed-budget gates are frozen there. A later
  Odds API pilot is capped to three volume markets and 20,000 credits. The
  Historical threshold diagnostics found 200 coverage at 19/12 weeks over
  200/210 versus the 194 control's 18/11, while 187 coverage reached 17/13;
  all three tied at 5/2/1 for 220/230/240. Both threshold alternatives and
  the zero-tuning deterministic one-swap refinement are now implemented as
  prospective early/late books under `tail-first-v4-20260810`; none can affect
  the adopted/UI portfolio. Deep generative dependence work is deferred until
  more field data exist.
- Threshold-shadow implementation commit `d4a5e15` is pushed on `main`; 15
  focused selector/freezer tests pass, including a proof that 187/194/200 use
  their distinct persisted support masks. Full Cloud Build
  `a000bbb2-5327-4de5-b216-0b35b4daf896` passed 717 tests with 2 skipped and
  produced immutable digest
  `sha256:9d02ecc3cfa1951d74056c64593314ce47facecbadeb500c998f6aa98ed7e297`.
  Only `freeze-tail-early` and `freeze-tail-late` were updated to that digest;
  both retain their exact early/late commands, GCP project environment, 1 CPU,
  1Gi, one retry and 3600-second timeout. Schedulers
  `s-freeze-tail-early` / `s-freeze-tail-late` remain PAUSED at 11:05 / 11:50
  Sunday CT. Neither job was executed off-season. This supersedes the v3
  freezer digest without changing the adopted/UI lineup path.
- One-swap implementation commit `b90047b` is pushed on `main`; 14 focused
  shadow/refinement tests pass. Full validation build
  `7ab5a1e2-1994-4ec5-8ac8-a188669b54c5` passed 716 tests with 2 skipped in
  453.35 seconds and produced immutable digest
  `sha256:603d20c09a878a1679b6559d4be56a6a59d0f7b367a1fb99019883203337e18d`.
  Only `freeze-tail-early` and `freeze-tail-late` were redeployed to that
  exact digest; both preserve `nfl-dfs freeze-tail-portfolios --slot
  early|late`, 1Gi/1 CPU, one retry, and 3600 seconds. Schedulers
  `s-freeze-tail-early` / `s-freeze-tail-late` remain PAUSED on their original
  11:05/11:50 Sunday CT schedules. No live app or adopted lineup path changed.
- The next-data review found a usable no-cost diagnostic before buying route
  data: installed `nflreadpy` currently serves 46,168 / 45,919 / 45,184
  participation plays for 2023 / 2024 / 2025, including every offensive
  player ID on a play. The frozen protocol in
  `reports/2026-08-10-pass-participation-proxy.md` derives strictly lagged
  player-on-field shares for all dropbacks and red-zone dropbacks, then tests
  whether those four fields improve 2024/2025 walk-forward residual MAE and
  20-point Brier loss beyond the accepted pre-lock projection, salary,
  position, target/snap share, and vacancy features. The feed is
  season-delayed and presence is not a route, so it can only support or reject
  a paid route-data trial; it cannot become a production input or historical
  lineup arm. Implementation, CLI, and three focused tests are complete; nine
  combined participation/selector tests pass. Implementation/protocol commit
  `0261801` is pushed on `main`; full validation build
  `6200e344-837e-4935-9adf-8eb062383017` passed 720 tests with 2 skipped and
  produced immutable digest
  `sha256:2665a7f9a683e2d737d620519a15a431e4a5c7baa6feb43aade7f2f4084fde62`.
  Guarded runner `scripts/cloud_pass_participation_proxy.sh` requires an
  immutable digest, deploys the unscheduled diagnostic with 2 CPU / 4Gi / no
  retries, records the execution and manifest, and harvests exactly one JSON
  disposition under `reports/pass-participation-runs/`.
  Execution `pass-participation-proxy-vmxdq` completed cleanly. Across 9,887
  held-out 2024-2025 player-weeks, the treatment improved residual MAE
  `3.71089→3.67957`, 20-point Brier `0.045375→0.045226`, and WR/TE Brier
  `0.039258→0.039082`; both primary metrics improved in each season. All
  frozen conditions pass and disposition is `supports-paid-route-trial`.
  This justifies verifying/buying the under-$200 full-history true-route
  export, not adding the season-delayed proxy or claiming a lineup result.
  Fantasy Points remains first because it explicitly advertises weekly route
  share plus CSV/Excel. Lower-cost fallback questions are logged for
  Reception Perception ($99.99/year historical tables, but no public CSV or
  complete-player promise) and SIS DataHub ($99.99/month with CSV, but no
  public confirmation of route fields/history); do not buy either without
  confirming the missing contract.
- Research on the subsequent selector question is recorded in
  `reports/2026-08-10-scoring-opportunity-roadmap.md`. After current shadows,
  prospective snapshots may retain 210/220 support and freeze a deterministic
  220→210→200 lexicographic book. A separate mechanism test may reduce seed
  noise when estimating 210/220 support only after exposing an exact change
  of measure on the possession simulator's own latent variables. The existing
  CE weights are not valid for this purpose because CE deforms deterministic
  means rather than sampling the production law. Any valid proposal must pass
  analytic likelihood-ratio checks, confidence-interval parity, ESS,
  max-weight, repeated-seed variance, marginal-invariance and roster-stability
  gates before any portfolio. This is not a retry of the already-adopted CE
  candidate generator and may not inspect the 107 known scores to set rules.
- Prospective extreme-selector protocol
  `reports/2026-08-10-prospective-extreme-selector.md` is now frozen and
  implemented without consulting historical outcomes. Candidate persistence
  adds complete 210/220 masks; policy `tail-first-v5-20260810` retains the
  prior eight books and adds one K=1 book that greedily covers new worlds
  lexicographically at 220→210→200. The implementation validates nested masks,
  deterministic priority/tiebreaks, 80 unique rosters and old 194 selection
  reproduction. Thirty-five combined selector/persistence/participation tests
  pass locally. This mechanism was subsequently retained in the eleven-book
  `tail-first-v6-20260810` policy alongside two role-union books.
  Implementation commit `d1c9318` is pushed on `main`; full validation build
  `9e3e6c14-f70a-4f8d-9863-7120c5fae74f` passed 721 tests with 2 skipped and
  produced immutable digest
  `sha256:75daf1607c2f08197d1357c10702434161b1093cff2a21e8cdc7ca7d5bcdf95c`.
  That digest is historical. The four paused shadow generators and two paused
  freezers now use the final v2 digest recorded above; the original three
  generators record `CODE_SHA=75c8791` and preserve their exact command,
  registry/K, possession mode, generator quotas, salary floor, 45/55 blend,
  30,000 worlds, 4 CPU / 8Gi, retry and timeout settings. Freezers preserve
  their early/late commands and 1 CPU / 1Gi settings. All ten shadow/freezer
  schedulers remain PAUSED. No off-season shadow or freezer was executed.
- Exact next action: monitor the six coverage executions without reading
  partial scores; after all succeed, run check-only exact-80 acceptance and
  the one frozen comparator against direct role. The no-floor union is closed.
  For paid data, run the preregistered 168-export same-season coverage
  collection sequentially, validate every manifest/schema/game count, then
  implement the frozen importer and diagnostic without reading outcomes
  until its PIT/support tests pass. Keep all
  17 seasonal schedules paused until the Aug 24 resume date. On the first real
  Sunday-main slate, run the authenticated UI -> 80 lineups -> DKEntries smoke
  and confirm v2 provenance; deliberately exercise and label the CE-only
  fallback in a controlled smoke. New historical experiments must use the
  revised tail-first law; do not tune the role seed, six fields, or
  12-candidate dose on these 107 outcomes.

## Previous state — 2026-08-09 21:05 CDT

### Pre-season arm/UI promotion gate complete

- Branch `main`; implementation commit `f647d00` promotes the adopted policy
  through every money-lineup path. The frozen production decision is
  `classic-k1-ce12-boom28-v1`, sourced from historical panel
  `20260809-e80-k1-ce12-c616390`: K=1 `tail_k1`, possession simulation,
  45/55 model/prop-market blend, $49,000 salary floor, fixed greedy coverage
  at 194, 80 default entries, candidate multiple 2, seed 1701, and fixed
  12 CE / 28 boom replacement allocation. The selected weekly-max counts over
  107 slates at 187/194/200/210/220/230/240 are
  `40/26/18/11/5/2/1`; mean/median weekly maxima are `181.1243/178.64`.
  Its candidate-pool oracle counts are `47/32/22/13/5/2/1`.
- `src/nfl_dfs/inference/production_policy.py` is now the single frozen
  mapping consumed by projection and live lineup code. It passes a
  request-local environment mapping rather than mutating process environment,
  and overrides every research lever capable of changing a roster. The
  projection job explicitly loads and verifies a one-member model from the
  isolated `tail_k1` registry. The simulator, replay shaper, optimizer,
  generator, selector, and provenance paths accept that explicit mapping.
- `/lineups`, `/lineups.csv`, and `/lineups/entries.csv` all use the same
  policy. The UI defaults to 80 and displays the policy plus exact loaded model
  version; JSON returns the full policy identity and both CSV routes return
  `X-Lineup-Policy` / `X-Model-Version`. The selector remains fixed at 194
  when a field size is supplied; field-size winning-line estimates are
  comparator metadata only. `sim=false` remains an explicitly labeled,
  non-adopted plain-MILP emergency escape hatch. DKEntries files still govern
  their actual reserved entry count.
- Validation is complete. The full local suite reached 100% green. Cloud Build
  `9b67b443-1924-4200-b749-ddc0bd147b5d` passed `712` tests with `2` skipped
  in 351.73 seconds, including a real offline K=1 end-to-end build of 80 legal,
  distinct, $49k+ lineups and an 81-line DraftKings CSV. Validated immutable
  image digest:
  `sha256:78ba7d76efcbe81913cef33a879dea1197b1440804c67d73d8bd6ae29219bc47`.
- Cloud Run service `nfl-dfs-app` is deployed from that exact digest as ready
  revision `nfl-dfs-app-00064-qgn` with 100% traffic. Its existing IAP policy
  correctly rejects unauthenticated and ordinary identity-token curls, so the
  external smoke was limited to Cloud Run readiness rather than bypassing IAP.
  The `project-slate` job is also ready on the exact digest and explicitly
  declares `MODEL_ENSEMBLE=1`, `MODEL_REGISTRY_VARIANT=tail_k1`,
  `BLEND_MODEL_WEIGHT=.45`, and possession simulation; its project setting and
  Odds API secret reference were preserved. It was not executed off-season
  because no matching live slate exists.
- All fourteen seasonal schedulers were rechecked after deployment and are
  `PAUSED`: `s-nflverse`, `s-features`, `s-train`, `s-train-k1`,
  `s-project-tu`, `s-project-su`, all six K=1/no-floor/K=3 early/late shadows,
  and both freeze-tail jobs. Year-round backups, odds/DK/CFB/weather ingestion,
  and freshness monitoring were left alone. This also prevents another
  expected off-season `shadow-k1-nofloor` no-slate failure alert.
- The alternate use of existing 2022-2025 ownership was completed, not lost:
  the contest-aware ownership predictor passed its calibration gate but its
  single frozen true-80 scoring arm failed to improve the adopted K=1 tail
  book and is rejected. The CE reranker confirmation also failed its adoption
  gate. Neither may enter live behavior; both remain durable negative evidence
  rather than tasks to rerun or tune on the same 107 outcomes.
- Exact next action: keep the fourteen jobs paused through Aug 23. On Mon Aug
  24, run the resume command in the README season-start table, verify the
  Tuesday K=1 training completes before projections, and use the first real
  Sunday-main slate for the authenticated UI -> 80 lineups -> DKEntries CSV
  smoke. Grade the already frozen K=1, no-floor, K=3, top-p, and mixed books
  prospectively without changing their membership. New data signals remain
  shadow-only until they have pre-lock evidence; do not retune this adopted
  policy against the known historical outcomes.

## Previous state — 2026-08-09 20:12 CDT

### Autonomous scoring research resumed after context recovery

- Live Cloud Run history and every tracked manifest were reconciled after the
  operator reported that research had stopped unexpectedly. There is no
  unharvested scoring execution: all six true-80 K=1 no-floor seasons,
  acceptance `accept-replay-panel-8m9hv`, and comparator
  `compare-adoption-panel-7c4cs` completed. The concurrent work was the Odds
  API shadow/telemetry implementation, which also completed. Paused Week-1
  prospective schedulers do not pause historical mechanism research.
- Two bounded next paths are preregistered before new outcomes. The first is
  the one allowed corrected-universe K=1 CE confirmation: union panel
  `20260809-e80-k1-ceunion-c616390` (`12 CE / 40 boom`) must pass its
  candidate-oracle gate before fixed replacement panel
  `20260809-e80-k1-ce12-c616390` (`12 CE / 28 boom`) can launch. Both retain
  immutable generation digest `sha256:98a31edd...`, K=1, true 80, $49k,
  45/55, line 194, and seed 1701. Protocol:
  `reports/2026-08-09-k1-ce-true80-experiment.md`.
- The recovered parallel ownership direction is also frozen. Do not repeat
  the failed generic `OWN_MODEL=fade` test: its target averaged incompatible
  cash/GPP, Classic/Showdown, and slate scopes. Build a walk-forward
  large-field Sunday-main Milly ownership target from the existing 2022-2025
  data and exact accepted K=1 snapshots. It earns one fixed K=1 scoring arm
  only after the preregistered held-out ownership-calibration gate passes.
  Protocol: `reports/2026-08-09-milly-ownership-alternative.md`.
- The reviewed CE runner and comparator are now implemented. The union runner
  pins the old generation image/code, K=1, seed 1701, 80 entries, and
  `12 CE / 40 boom`; the fixed runner refuses to launch unless the tracked
  union JSON passes, then derives all 107 caps from the promoted source before
  launching `12 CE / 28 boom`. The comparator proves exact feature invariance,
  source-roster union containment/shared-world equality, active CE candidates,
  fixed pool equality, and the complete 187-240 tail grid. Focused validation:
  32 tests passed across the new comparator, canonical tail gate, and
  generation-budget controls; both shell scripts parse and `git diff --check`
  passes.
- CE infrastructure commit `2650c77` is pushed on `main`. Union panel
  `20260809-e80-k1-ceunion-c616390` is now launched on immutable generation
  digest `sha256:98a31edd...`; its durable 2022 one-week preflight execution is
  `replay-e80k1ceu-smoke-z4rlq` and passed. The six durable season executions
  are `replay-e80k1ceu-2019-7zp2w`, `replay-e80k1ceu-2021-hhbfh`,
  `replay-e80k1ceu-2022-wnsz6`, `replay-e80k1ceu-2023-vrmsz`,
  `replay-e80k1ceu-2024-9r566`, and `replay-e80k1ceu-2025-zjw6k`; all were
  launched asynchronously and must be checked by these exact IDs rather than
  by each job's latest execution.
- The contest-aware ownership diagnostic is implemented while CE computes.
  It deterministically selects the largest-field mass-valid Classic Milly,
  excludes parenthetical alternate/single-game slates and high-roller copies,
  maps DK defense nicknames to snapshot team codes, never imputes unmatched
  ownership as zero, and trains 2023/2024/2025 strictly on earlier seasons.
  It compares the low-capacity contest model to both the existing all-contest
  model and a prior-season-mass-calibrated version of the current naive proxy,
  emitting preregistered correlations/MAE/top-quartile/position calibration,
  join coverage, and a binary gate. Ten focused ownership/current-model/CE
  tests pass; both evaluator scripts compile/parse and whitespace checks pass.
- Exact next action: finish/record the CE union preflight and six execution
  IDs; commit/push the ownership evaluator; run a full Cloud Build; then use
  its immutable digest for the CE comparator and ownership diagnostic. The
  first queued build `0405d235-34af-49b0-bd72-d189f913f0e3` was cancelled
  before use because review caught that Docker's explicit script allow-list
  omitted the two new cloud entry points; no image from that build is valid.
  Dockerfile now includes both scripts. Never query or launch fixed-arm lineup
  outcomes unless the tracked union mechanism/frontier gate passes.
- Replacement full Cloud Build
  `28ea77e8-1775-4b3d-a9d6-56888997f292` passed 694 tests with 2 skipped from
  pushed packaging commit `1933b85`. Its immutable audit/evaluator digest is
  `sha256:a1217fec4074fe97f4e811bed439a9239ddfd662b5484b7ddeae46dfc539ea22`.
  The frozen ownership diagnostic launched on that exact digest as durable
  execution `evaluate-milly-ownership-6s2rq`; it failed closed before model
  training or a scientific verdict because a few accepted snapshot rows have
  null display names and collapsed to duplicate `PLAYER_NAN` join keys. The
  repair retains those rows in full-slate naive normalization but assigns
  them unique, explicitly unmatched ID keys; ownership truth still may never
  be zero-filled. No preregistered feature, model setting, fold, comparator,
  or gate changed. Eight focused tests pass after the repair, including a
  two-null-row regression. The retry must use a distinct run directory/ID.
  Failure provenance is tracked under
  `reports/ownership-runs/20260809-milly-k1-c616390/`.
- Null-name repair build `1e5f3245-30ec-4637-b42d-85fa90add577` passed 695
  tests with 2 skipped and produced immutable digest
  `sha256:3929447c0dfb376dc70847a1d4d6291333a42b8d4c96fe8f66b4c25abf0be17a`.
  Distinct retry `evaluate-milly-ownership-kb9fl` failed closed before model
  training or a scientific verdict on the next genuine identity ambiguity:
  separate Ryan Griffin players at different native positions share a name.
  The join key now includes native position plus normalized name, which is
  present on both truth and snapshots and is not a model feature. All eight
  focused tests pass. Preserve the v2 failure directory and use a distinct v3
  retry after full validation; do not reinterpret either failure as evidence
  for or against ownership modeling.
- Position-aware build `7cbd0f43-930c-491d-93d2-2bfe37c73655` passed 695
  tests with 2 skipped and produced immutable digest
  `sha256:a306743b802b2904907f998b0653c626dc8c19e22dbe55795472dbe89942feb2`.
  V3 execution `evaluate-milly-ownership-644mf` completed and appeared to
  pass every frozen gate. Its recorded aggregate contest-aware MAE/Spearman are
  `2.8147/0.7924` versus old all-contest `3.6142/0.5657` and naive
  `4.6548/0.2589`; it appeared to beat both metrics in all three 2023-2025
  seasons and lower top-quartile MAE to `7.5983` versus `9.8483/11.5424`.
  These metrics are now **scientifically superseded**, not an adoption input:
  serve-path review found salary/value ranks were recomputed after the truth
  join, leaking which players appeared in settled ownership instead of using
  the full-slate ranks available live. No scoring arm launched from V3.
- Coverage review found the only zero-match week is a scope mismatch, not a
  name join failure: Christmas 2022 fell on Sunday; the accepted Week-16
  replay contains only the two Sunday games, while DK's named Milly was its
  large Saturday main slate. V3 held-out metrics are unaffected (the week is
  2022 training-only and contributed no joined row), but its coverage
  denominator is also superseded. The evaluator now declares this one
  calendar-proven exclusion, requires every other week to retain >=90% mass,
  and will emit a final v4 report over 71 eligible contest/slate pairs. Nine
  focused tests pass. Do not launch the scoring arm until that clean report is
  tracked and passes the original gate on full-slate rank features.
- Reporting build `5e6db78f-665d-4ab4-867e-2b618f05612f` was cancelled before
  use after the rank-skew audit; no image/result from it is valid. The
  evaluator and reusable training frame now preserve features computed on the
  complete accepted slate through the truth join. Off-by-default downstream
  plumbing for `OWN_MODEL=milly_fade` is implemented but not launched: it
  fits only earlier-season eligible Milly rows, normalizes predicted ownership
  within position to the incumbent penalty scale, and keeps the simulated
  field naive. Focused ownership/replay/infrastructure validation is 28
  passed. Do not run a lineup panel until the corrected diagnostic passes.
- The one allowed downstream arm is now fully guarded but remains unlaunched.
  `OWN_MODEL=milly_fade` changes only the optimizer's ownership fade, never the
  field sampler. Its runner requires the clean 71-slate v4 JSON before it can
  launch true-80 K=1 `0/0/0/40`; its comparator requires exact invariant
  upstream player features, unchanged shared candidate worlds, the frozen
  `proj_tourney = proj - 25*own_est` delta, estimate/candidate/selection
  movement, ownership sum/product diagnostics, and the existing tail-first
  gate. Focused validation across ownership, comparator, panel gate, replay,
  live smoke, and infrastructure is 39 passed; shell parsing, compilation and
  whitespace checks pass. Corrected diagnostic build
  `fa00ea6f-ffd0-49c6-8352-553c24989eb2` passed 697 tests with 2 skipped from
  rank-aligned commit `638ce2a` and produced immutable digest
  `sha256:1530d8d9f9bd67a4928b40c7c42edcc740a8ab2887ddfcda1a6ca5dcb7852959`.
  Corrected v4 execution `evaluate-milly-ownership-wd4ll` passed every frozen
  diagnostic condition over 9,010 held-out rows and 71 eligible slates.
  Aggregate contest-aware MAE/Spearman are `2.8666/0.7865`, versus old
  all-contest `3.6142/0.5657` and naive `4.6548/0.2589`; top-quartile MAE is
  `7.7347` versus `9.8483/11.5424`. It beats both metrics in every held-out
  2023-2025 season, retains `98.90%` ownership mass overall, and retains at
  least `93.74%` in every eligible week. The tracked clean report is
  `reports/ownership-runs/20260809-milly-k1-c616390-v4/`; superseded v3 still
  must never be used.
- The ownership panel preflight is now pinned to 2023 so it must train on 2022
  and exercise the actual `milly_fade` serve path; a 2022 smoke would only
  exercise the intentional cold-start fallback. Focused ownership/comparator/
  replay tests pass (19 tests), shell parsing and whitespace checks pass.
  Exact next action: commit/push this diagnostic milestone, run a full Cloud
  Build of the final guarded scoring code, then launch the one frozen ownership
  panel from that immutable digest. In parallel, continue polling the six exact
  CE union execution IDs and compare the union only after all six succeed.
- Final scoring-code Cloud Build
  `53c60d18-3f77-4a70-bd4c-906261c3d7c6` passed 700 tests with 2 skipped from
  commit `f3086097b79f13de9a7e9eccef570f9063f53d3a` and produced immutable
  digest `sha256:5cab563fdb9bad9f4241631f05bad51e73929851f0aa0acb3cc7cd7135a2c3c0`.
  The guarded 2023 preflight `replay-e80k1milly-smoke-tt2g5` fit on 3,146
  exact 2022 rows, then failed before candidates because DST concatenation
  promoted `is_cold_start` to pandas `object` and LightGBM requires numeric
  serve columns. No season execution launched and no lineup outcome was
  viewed. Provenance is tracked at
  `reports/panel-runs/20260809-e80-k1-millyown-f308609/`.
- The failed preflight manifest also records a supplied full `CODE_SHA` that
  had the correct `f308609` prefix but did not equal the actual image-source
  commit. This did not create panel rows, but it is an audit defect. The runner
  now requires the supplied full SHA to equal local HEAD. The serve repair
  coerces every declared ownership feature to float and adds a regression for
  object-typed `is_cold_start`; 20 focused ownership/comparator/replay tests
  pass. Exact next action: commit/push this fail-closed repair, run a new full
  Cloud Build, and retry from a distinct commit-derived panel ID. Never reuse
  the failed f308609 panel or its digest for the ownership scoring panel.
- Repair build `59f7cbd2-09f5-4cd1-819a-fe1bba0c6d8f` passed 701 tests with
  2 skipped from exact commit `6d4a549e518fbed0677158b57b07fe0532b72a4f`
  and produced immutable digest
  `sha256:24d1b2b778c3e5ca905270d8836b7ee4b1e9632912ff6aa0609c77516813e7aa`.
  Corrected 2023 preflight `replay-e80k1milly-smoke-7zvnq` passed after
  fitting 3,146 exact 2022 ownership rows and serving the actual model.
  True-80 K=1 ownership panel `20260809-e80-k1-millyown-6d4a549` is launched
  with exact season executions `replay-e80k1milly-2019-578rs`,
  `replay-e80k1milly-2021-27qdm`, `replay-e80k1milly-2022-k2cmq`,
  `replay-e80k1milly-2023-rsntz`, `replay-e80k1milly-2024-p82td`, and
  `replay-e80k1milly-2025-2nmwq`. Do not read or compare partial outcomes;
  wait for all six exact IDs to succeed, then run the frozen ownership
  mechanism/tail comparator on the same immutable digest.
- CE union executions for 2019, 2021, 2022, 2023, and 2024 have completed
  successfully. The 2025 execution has written all 18 slates but is still
  finalizing. Exact next action: wait for `replay-e80k1ceu-2025-zjw6k` to
  report success, then run the union comparator. Launch fixed CE replacement
  only if its tracked binary union gate passes.
- All six CE union executions ultimately reported success. Comparator v1
  `compare-k1-ce-panel-kkkzh` failed closed with one reported mechanism issue:
  2,229/50,098 feature payloads were not bit-exact. A column-level audit shows
  zero row/identity/config/actual differences and zero numeric differences
  above `1e-12`; the maximum is `3.552713678800501e-15`. All 25,787 source
  candidates have exact shared actual/p-line/sim-mean/support values; union
  adds 12 candidates on every slate and 1,284 novel CE rosters. V1 is
  preserved under the union panel directory and remains mechanically invalid.
- V1's provisional tail result is highly favorable but not yet a gate pass:
  selected 187/194/200/210/220/230/240 moves `36/22/12/6/3/1/1` to
  `39/26/16/11/5/2/1`; pool oracle moves `44/30/19/9/3/1/1` to
  `47/33/22/13/5/2/1`. The comparator repair keeps bit-exact mismatches as a
  diagnostic, uses `1e-12` only for numeric materiality, and still requires
  every nonnumeric field exactly equal. The gate, CE seed/dose, and thresholds
  are unchanged. Eleven focused comparator/panel tests and the live corrected
  query pass; shell parsing and whitespace checks pass. Exact next action:
  commit/push, full Cloud Build, run labeled union v2, and launch the frozen
  fixed replacement only if `ce_comparison_v2.json` passes.
- Comparator build `4acbc4dd-d54e-4556-9097-1870589f8dcb` passed 701 tests
  with 2 skipped from `04ec460` and produced immutable reporting digest
  `sha256:342c96629fd335c57ab2ff695b79ee29d9b11df73a001ddf7d34ee0c8fee0eff`.
  Labeled v2 execution `compare-k1-ce-panel-wbspp` passed all original union
  gates with zero material feature, shared-world, or candidate mechanism
  failures. The tracked `ce_comparison_v2.json` is the valid gate record; v1
  remains preserved as false-positive audit provenance.
- Fixed equal-budget panel `20260809-e80-k1-ce12-c616390` froze all 107
  source-pool caps before treatment scoring (range 224–251), uses old immutable
  generation digest `sha256:98a31edd...`, code `c616390`, K=1, true 80,
  `12 CE / 28 boom`, and seed 1701. Preflight
  `replay-e80k1cef-smoke-mcv5c` passed. Exact season executions are
  `replay-e80k1cef-2019-4xr9f`, `replay-e80k1cef-2021-sfdjt`,
  `replay-e80k1cef-2022-9km62`, `replay-e80k1cef-2023-8p8z9`,
  `replay-e80k1cef-2024-7tz6v`, and `replay-e80k1cef-2025-xjhhh`.
  Do not read partial outcomes. Once all six succeed, run the frozen fixed
  comparator and promote only if its selected-tail and oracle gates pass.
- Ownership panel remains healthy and partial outcomes remain unread; current
  no-score progress is 7/10/8/12/9/8 slates for 2019/2021/2022/2023/2024/2025.
  Exact next action: monitor the six fixed CE and six ownership execution IDs,
  compare each only after its complete six-season success contract, update
  both protocols/HANDOFF, and continue from whichever mechanisms pass.
- The contest-aware ownership scoring panel subsequently completed all 107
  slates and all six exact executions reported `Completed=True` with one
  successful task and no failures. Comparator execution
  `compare-k1-milly-ownership-wcqqj` found no tail benefit: selected
  187/194/200/210/220/230/240 moves `36/22/12/6/3/1/1` to
  `33/22/12/6/3/1/1`, mean/median weekly max moves
  `179.60/178.82 -> 178.60/177.14`, and pool oracle moves
  `44/30/19/9/3/1/1` to `41/29/18/8/3/1/1`. It therefore fails both the
  required +2 selected-200 lift and the non-worse oracle-200 safeguard.
  The arm is rejected and must not be tuned on these outcomes.
- Ownership comparator v1 labeled the result `invalid` only because 330
  upstream payloads were not bit-exact. Column-aware local re-audit found zero
  material/categorical mismatches, maximum numeric delta `3.5527e-15`, exact
  shared candidate worlds, all 54 trained slates changed, and frozen fade
  equation error `3.9968e-15`. The comparator repair retains that bit-level
  diagnostic while applying the already-established `1e-12` numeric
  materiality rule. Its local disposition is the scientifically correct
  `reject`; no arm setting, tail gate, or result changed. One partial 2023
  weekly score was inadvertently surfaced while checking a raw progress log,
  after all settings and gates were frozen; it was not used for any change or
  decision. Exact next action: commit/push the reporter-only repair, complete
  a full Cloud Build, run a labeled immutable ownership v2, and continue
  monitoring the fixed CE panel (currently 74/107 slates, no failed
  execution).
- Ownership reporter build `b6528016-6572-4b79-8278-a4b1d2999110` passed 702
  tests with 2 skipped from pushed main commit `54b29ca` and produced
  immutable digest
  `sha256:40839f1d99e9a08f54a1343c49c539ed7fe5329d3f1400b8c6cd5bf4f1fc18b3`.
  Labeled v2 execution `compare-k1-milly-ownership-wqgj5` returned valid
  `reject` with zero failures and the unchanged tail metrics above. Its
  tracked `ownership_comparison_v2.json` is the definitive disposition; v1
  remains preserved as false-positive audit provenance. Close this historical
  ownership arm and do not try field-only ownership (the current 194 coverage
  selector does not read opponent-field ownership) or tune the fade dose on
  these outcomes. Fixed CE is now 90/107 slates with 2021 and 2024 complete;
  exact next action is to wait for all six CE execution IDs to succeed, then
  run the frozen fixed comparator on immutable reporting digest
  `sha256:342c9662...0eff`.
- All six fixed CE executions completed successfully and immutable comparator
  `compare-k1-ce-panel-87l22` returned `pass` with zero failures. Selected
  187/194/200/210/220/230/240 improves from `36/22/12/6/3/1/1` to
  `40/26/18/11/5/2/1`; mean/median weekly maximum moves
  `179.60/178.82 -> 181.12/178.64`; pool oracle improves from
  `44/30/19/9/3/1/1` to `47/32/22/13/5/2/1`. The fixed tail-first gate passes
  by +6 selected 200 weeks, +5 selected 210 weeks, and +3 oracle-200 weeks.
- The fixed mechanism audit proves equal pools on all 107 slates (25,787 rows
  each), exactly 12 CE candidates per slate replacing 12 boom candidates,
  1,284 novel CE rosters, exact shared candidate worlds, zero material player
  feature differences, and zero failures. Canonical promote execution
  `accept-replay-panel-p6ll4` independently passed all completeness,
  provenance, feature, authoritative-actual, score-artifact, mask, selection,
  and parity contracts, then atomically promoted 25,787 candidates and 50,098
  player features. `20260809-e80-k1-ce12-c616390` is now the accepted
  historical research baseline. At this historical milestone live/UI behavior
  remained unchanged pending the README's pre-season arm-policy gate; the
  current section records that gate's later completion.
- The promoted baseline has 6 recoverable >=194 weeks across 4 seasons and 4
  recoverable >=200 weeks. Canonical acceptance therefore passes the original
  reranker-development opportunity gate. Exact next action: commit/push the
  CE comparison and promotion artifacts, then preregister a corrected
  true-80 tail-first reranker confirmation on this accepted CE pool before
  evaluating its outcomes. Do not reuse the old 40-entry constants or choose
  a feature arm after seeing new results.
- The one allowed true-80 fixed-pool reranker confirmation is now frozen in
  `reports/2026-08-10-k1-ce-reranker-confirmation.md` before any reranker
  outcome. It uses only the prior structure/provenance lead, strictly
  earlier-season equal-slate-weighted ridge training (`alpha=10`), a fixed
  +/-15 point candidate-world shift, 2019 cold-start fallback, the unchanged
  194 coverage selector with 80 entries, and a within-slate shuffled-shift
  control at seed 314159. Candidate generation and oracle are fixed. Adoption
  requires +2 selected 200 weeks, non-worse 210/oracle-200, a valid mechanism,
  and a lexicographic win over the shuffled control; season signs/mean remain
  diagnostics. Ownership/disagreement arms are not reopened. Thirteen focused
  reranker/panel tests and 38 reranker/infrastructure/persistence tests pass;
  shell parsing, compilation, and whitespace checks pass. Exact next action:
  commit/push, run a full Cloud Build, then execute the one immutable evaluator
  and close or promote the selector arm from its frozen report.
- Reranker Cloud Build `44264eea-f58b-419a-a9b6-a77f13d60dff` passed 707
  tests with 2 skipped from pushed commit `cbd770a` and produced immutable
  digest
  `sha256:09a7ed659928afef1e720b40fc55e2aec8ca643e706c720dee21047aa5d0dd9f`.
  Execution `evaluate-k1-ce-reranker-vhg99` completed with zero mechanism
  failures and valid `reject`. Source/primary/shuffled selected
  187/194/200/210/220/230/240 are respectively
  `40/26/18/11/5/2/1`, `42/26/18/12/5/2/1`, and
  `39/26/19/11/5/2/1`; mean weekly maximum is `181.12/181.40/180.57`.
  The primary moves 1,449 selected slots but adds no 200 week (required +2)
  and loses the lexicographic negative-control comparison because the shuffled
  book reaches 19 at 200. Close A1 and do not run A2/A3, alternate alpha/cap,
  or another shuffle seed on these outcomes.
- Exact next action: commit/push the reranker report, then treat historical
  scoring discovery as closed at the promoted K=1 `12 CE / 28 boom` baseline.
  Complete the README pre-season arm-policy/UI gate so live lineup generation,
  API, UI, and CSV paths explicitly use and expose the adopted policy; keep
  any genuinely new data (Odds API shadow/prospective ownership) point-in-time
  and shadow-only until its own held-out gate passes.

### Recovery provenance

- GitHub `main` was stale at `4619015`; the missing August 7–8 work had been
  built and run in Google Cloud but had not been pushed.
- The latest source was recovered from Cloud Build
  `f182b575-0396-4973-86b9-5ecdebce7f55`, object
  `gs://nfl-predictions-503414_cloudbuild/source/1786195071.986052-229507cc4ee34d3a8067eb4d60e09ba9.tgz`.
- Its audit image is
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:4100028f3d5c29c4b6de423e590054dc765f605a4a88d57670a64ca6f8c21acb`.
  The underlying fully tested replay image is tag `ee6f433`, digest
  `sha256:6e34cb1f3580be71ad2acd50f0faeacf45b59a7039fe7e32b0996ecf26dda9d0`.
- The recovery branch was fast-forwarded into `main` and pushed. Local and
  remote `main` both pointed to `1e3361f` before the 80-entry audit began.
  GitHub-only reports were preserved; no files were deleted during recovery.

### Environment on the replacement computer

- System tools: GitHub CLI 2.97.0, Google Cloud CLI 579.0.0, jq 1.8.1,
  Python 3.14.4, `python3-venv`, and `libgomp1`.
- `.venv` contains editable `.[gcp,app,dev,tuning]` dependencies and passes
  `pip check`.
- GitHub CLI is authenticated as `espechtsoftware`; gcloud and Application
  Default Credentials are authenticated as `espechtsoftware@gmail.com` for
  project/quota project `nfl-predictions-503414`.
- Local `.env` sets `GCP_PROJECT=nfl-predictions-503414` and is gitignored.
  No credential material belongs in this file.
- `ingest-odds` and `ingest-props` now resolve `ODDS_API_KEY` from Secret
  Manager secret `odds-api-key:latest`; both retain immutable image digest
  `sha256:6c556b9e...` and their existing enabled schedules. The default
  compute service account has `roles/secretmanager.secretAccessor`. The
  deployment script now preserves this secret reference and no longer reads
  or distributes a workstation-local Odds API key. No secret value was read.

### Odds API shadow-data implementation milestone

- On `main` after `04fd2ab`, the existing game-lines and live-props requests
  now record secret-free request identity, HTTP status, returned markets, and
  provider quota headers in new partitioned table
  `nfl_raw.odds_api_requests`. Sanitized exceptions intentionally discard the
  provider URL/query so an HTTP or transport failure cannot put the API key
  in logs or BigQuery. Audit-write failures do not trigger a Cloud Run retry
  that would repeat paid calls.
- The fixed nine-market live-only bundle covers pass attempts/completions,
  rush attempts, pass interceptions, rush/reception touchdown allocation,
  and dual-role yards/TDs. It writes only to partitioned
  `nfl_raw.prop_lines_shadow`; repository search confirms no production
  model, API, optimizer, or UI consumer reads that table. Every shadow call
  requires a fresh provider-reported remaining balance and preserves a
  5,000-credit reserve. Missing quota headers fail closed. Historical shadow
  backfill is not implemented and remains prohibited.
- A related point-in-time defect was fixed before season start: `ingest-props`
  formerly assigned all currently listed NFL events—including August
  preseason—to the next regular-season week. It now filters events to the
  next regular-season week's exact US-local game-date window before either
  paid prop request. The deficiency is recorded in README.
- Initial source commit `910bc6e` is pushed on `main`. Focused offline
  validation was green: 26 tests across request sanitization,
  quota capture/persistence, reserve boundaries, local-date filtering,
  base/shadow table isolation, existing game-line behavior, and prop parsing;
  Python compilation and `git diff --check` also passed. Cloud Build
  `5ad9f2e5-4141-41bc-b1f2-3e1ff71b247b` passed 685 tests with 2 skipped and
  produced immutable digest
  `sha256:8dc28e1c06f618118ad2e7695864a56e7428033e367146249520a0f246da1617`.
  Both additive DDL tables were created and verified empty/partitioned before
  deployment. `ingest-odds` generation 32 and `ingest-props` generation 29
  are Ready on that digest; Secret Manager bindings, CPU/memory, command,
  service account, retries/timeouts, and the existing enabled scheduler
  cadences remained unchanged. Only `ingest-props` added
  `ODDS_SHADOW_MARKETS_ENABLED=1` and reserve `5000`.
- Preseason smoke `ingest-props-mmx2l` completed but correctly keeps this
  milestone open. The provider already lists all 16 Week 1 events. The job
  therefore made one events request and inferred 16 base plus 16 shadow
  attempts; four games returned 82 legitimate very-early DraftKings
  anytime-TD base rows, while the shadow returned zero rows. Exact credits
  cannot be cited because the 33-row audit batch failed to load. No job retry
  occurred and no shadow row landed.
- The audit failure was a schema-contract defect: the new table declared five
  fields `NOT NULL`, while the shared DataFrame loader appends an autodetected
  nullable schema. Production columns have been safely relaxed to NULLABLE,
  the tracked DDL now matches, and audit DataFrames explicitly assign Arrow
  string/boolean/integer/timestamp dtypes so all-null fields cannot infer an
  incompatible type. A new `check-odds-quota` command uses the provider's
  free `/sports` endpoint, requires its audit row to persist, and avoids
  repeating any event prop request. Updated focused validation is 27 passed.
- Follow-up commit `ca47ac6` is pushed. Cloud Build
  `313ca4a3-6acc-4f60-83e1-194ef05f6b65` passed 686 tests with 2 skipped and
  produced digest
  `sha256:59ed4fbf111a688125619cfebe41721b54b85e20fcdb762b486274b673880b53`;
  both ingestion jobs were moved to it without other template/schedule
  changes. Free quota-only execution `ingest-props-n5zch` then reproduced a
  second distinct schema defect and was explicitly cancelled before any
  automatic retries. It made no event-prop call and wrote no prop rows.
- Exact warehouse error from an isolated synthetic conversion (which failed
  before writing data): the partitioned+clustered destination expected
  clustering `(request_kind,is_shadow,http_status)`, while the shared loader
  repeated only its `requested_at` partition contract. BigQuery requires both
  when the job supplies partitioning. The same defect would have rejected the
  first nonempty `prop_lines_shadow` append. `load_dataframe` now accepts and
  applies explicit clustering fields; audit and shadow callers pin the exact
  DDL order. A focused helper regression plus all Odds tests pass (28 tests).
- Final source commit `aad6739` is pushed on `main`. Cloud Build
  `00a055a7-d31b-463b-b757-b704560fb21e` passed 687 tests with 2 skipped and
  produced immutable digest
  `sha256:0a55920d638951aaa6516b059f7ae3d1218cc6ee0d89a332805ca611fefc052d`.
  `ingest-odds` generation 34 and `ingest-props` generation 31 are Ready on
  that exact digest with their original scheduled args. Secret refs,
  resources, retries, timeout, service account, and schedulers remain intact;
  `s-odds` is enabled at `0 9,15 * * 3-7` and `s-props` at
  `30 9 * * 3-7`, both America/Chicago.
- Final free validation `ingest-props-8tgqd` completed successfully using
  only the execution-time `check-odds-quota` args override. Its one audit row
  persisted with HTTP 200, endpoint `/sports`, `requests_last=0`,
  `requests_remaining=99940`, and `requests_used=60`. It wrote zero base and
  shadow prop rows; `prop_lines_shadow` remains empty. The audit table has
  one row and zero endpoints containing a query string or API-key-like text.
  The scheduled job template still runs ordinary `ingest-props`, not the
  diagnostic override.
- This milestone is closed. Do not buy or backfill historical Odds markets:
  the account has ample prospective quota, but the new data is not allowed
  into models/UI until held-out residual, tail-calibration, and
  candidate-oracle gates are frozen and passed. Next concrete action is to
  inspect `odds_api_requests` and `prop_lines_shadow` after the next scheduled
  in-season pull, verify actual per-market cost/coverage, and then freeze the
  prospective evaluation before any lineup outcome is viewed.

### Latest validated research state

- Under the operator's explicitly amended aggregate-tail utility, true-80
  K=1 panel `20260808-e80-k1-c616390` is now the **promoted tail-first
  research baseline**. Promotion execution `accept-replay-panel-jhcwr`
  passed on validated digest
  `sha256:4182a4c077a1dcc183be3c82dfcfa44d60d8909dc5807a4996622a49bab29fdd`:
  25,787 candidates, 107 slates, exactly 8,560 selected rows, 50,098 eligible
  player snapshots, zero missing joins, and candidate/live mean parity within
  `2.34e-05`. At the frozen 194 selector its 187/194/200/210/220/230/240
  counts are `36/22/12/6/3/1/1`, mean weekly maximum 179.60, and pool-oracle
  >=200 count 19. K=3 `20260808-e80-k3-c616390` remains the stability and
  production reference at `29/19/8/5/1/1/1`, mean 177.08, oracle >=200 count
  12. This promotion changes the research incumbent only; no live deployment
  default has been changed.

- Final K=1 no-salary-floor panel `20260809-e80-k1-nofloor-c616390`
  completed on all 107 slates with 25,904 candidates and exactly 8,560
  selections. Acceptance `accept-replay-panel-8m9hv` passed on reporting
  digest `sha256:67e20d8308bd...ed4f3f6`; salary comparator
  `compare-adoption-panel-7c4cs` had zero failures. Selected
  187/194/200/210/220/230/240 moves from `36/22/12/6/3/1/1` to
  `37/24/16/8/3/1/1`; mean/median moves 179.60/178.82 to 179.11/177.52.
  Five weeks are gained and one lost at 200; season deltas are
  `{2019:+2, 2021:+1, 2022:0, 2023:0, 2024:0, 2025:+1}`. The source/treatment
  pool oracle grid moves `44/30/19/9/3/1/1` to `43/28/18/9/3/1/1`, so the
  frozen oracle safeguard fails and formal disposition remains
  `tail-first-not-supported`. Never promote the staging panel or tune an
  intermediate floor/selector on it. Because submitted weekly highs are the
  operator's explicit utility, the exact unchanged policy is retained only
  as a distinct prospective `tail_k1_nofloor` shadow; it is not a historical
  adoption and remains excluded from the UI.

- Prospective K=1 shadow infrastructure is implemented on `main` in commits
  `97cee37` and `0e0278d`. Canonical model labels
  remain unchanged; `MODEL_REGISTRY_VARIANT=tail_k1` writes/loads only
  `comp_*__tail_k1` labels, and the loader verifies their stored member count
  is exactly the configured K=1. New `nfl-dfs shadow-k1` refuses canonical or
  incorrectly sized models, selects the same Sunday-main draft group as the
  UI, freezes exactly 80 entries at line 194 with notes disabled, and writes
  a distinct `live_shadow` run synchronously. Missing artifact storage,
  partial lineup counts, feature/candidate warehouse failures, and score
  artifact failures make the job fail rather than silently lose prospective
  evidence. The app and canonical K=3 registry are untouched. Focused local
  validation is green: 47 tests across shadow/registry, persistence, live
  smoke, ensemble, and research infrastructure; Python compilation, CLI
  discovery, shell syntax, and diff whitespace also pass.

- First full validation of commit `97cee37` passed Cloud Build
  `fc5691cf-b359-466c-85cb-b28b2424fec4` with 667 passed and 2 skipped,
  producing digest
  `sha256:39b097ebf714beefecc5478f70c9449de2788ff7371db7b3df375dc29506260c`.
  Jobs `train-weekly-k1` and `shadow-k1` were deployed on that digest; paused
  schedulers are `s-train-k1` (Tue 08:30 CT), `s-shadow-k1-early` (Sun 10:30),
  and `s-shadow-k1-late` (Sun 11:20). Training smoke
  `train-weekly-k1-hrhl8` completed successfully, creating isolated
  `comp_targets__tail_k1/2026-W32`. The canonical `comp_targets` latest object
  remains `2026-W32` and its full listing checksum remained exactly
  `e85a892e48da1b31eb87712b1ace96ea8f8c25f841d9bcdca9084a29b6cd1a8d`.
  A post-deploy review then found that an August preseason DK group could be
  the largest upcoming Sunday before Week 1. Commit `0e0278d` requires the DK
  group's Eastern date to equal the next regular-season week's Sunday. A
  read-only live check resolves the target to 2026w01 / 2026-09-13, finds no
  matching current DK group, and fails closed before model loading or writes.
- Replacement Cloud Build `d5c080e9-03a6-46e8-b8d9-aca3874b287c` passed the
  full suite again (667 passed, 2 skipped) and produced the date-gated K=1
  digest
  `sha256:d7df959ce3f7ed6f41427b6015f4e275606c07e91671aa24872422c8f3319998`.
  Both `train-weekly-k1` and `shadow-k1` are now pinned to that digest. The
  verified shadow contract is `nfl-dfs shadow-k1`, K=1, variant `tail_k1`,
  possession mode, generation `0/0/0/40`, $49k salary floor, 45/55 blend,
  30,000 live worlds, 8Gi/4 CPU, and code SHA `0e0278d`; training uses the
  same image with only K=1/variant settings. All three scheduler states and
  schedules were rechecked and remain PAUSED. Canonical registry checksum is
  still unchanged after that deployment. This image is superseded for the
  paired shadow jobs by the `cb57798` build below.
- Same-time K=3 reference shadow is implemented, validated, and deployed from
  source commit `cb57798`. New `nfl-dfs shadow-k3` requires the
  canonical registry and K=3, shares every 80-entry/194-tail generation,
  date, persistence, and artifact contract with K=1, and records distinct
  `live-shadow-tail_k3-*` panel IDs. K=1 remains `live-shadow-tail_k1-*`.
  Final Cloud Build `a97781f2-c764-4067-b578-feacf931f03c` passed 668 tests
  (2 skipped), producing digest
  `sha256:939778e31defe13dc48b6410d3621422070864cbc60f7fd9680e1faf0d555b89`.
  `train-weekly-k1`, `shadow-k1`, and `shadow-k3` are all pinned to that exact
  digest; verified shadow envs differ only in declared K/registry/command and
  otherwise share the frozen possession, 0/0/0/40, $49k, 45/55, 30k-world,
  artifact-bucket, 8Gi/4 CPU contract. Paired schedules are 10:30 and 11:20
  CT; all five new schedules, including K=1 training, are PAUSED. The
  canonical registry checksum remains unchanged. This control makes future
  K=1 gains/losses paired under near-identical pre-lock information rather
  than judged in isolation.

- Prospective selector/mix freezing and grading are implemented, fully
  validated, and deployed for paused off-season operation. After each
  complete early/late K=1/K=3 source pair, `freeze-tail-portfolios` verifies
  unlabeled live provenance, exact 80-entry counts, registry/K isolation,
  score artifacts, p-line/mask parity, and exact persisted coverage
  reconstruction before appending immutable memberships. It freezes four
  separately labeled books: K=1 194 coverage, K=1 top individual p-line,
  K=3 194 coverage, and 20 K=1 / 60 K=3 coverage. The mixed rule keeps the
  first 20 entries from K=1's own complete coverage order, then walks K=3's
  complete coverage order until it has 60 rosters not already present;
  duplicate count and every source rank/panel/candidate are persisted. This
  exact asymmetric backfill rule is frozen before prospective outcomes and
  must not be changed after Week 1.
- Portfolio run IDs are fixed as
  `live-tail-portfolios-<season>w<week>-early|late`; an existing run is
  accepted only when its complete identity matches byte-for-byte on the
  membership keys. `grade-tail-portfolios` later joins the frozen nine-player
  rosters to authoritative skill/DST DK points, fails on any missing or
  duplicate actual, reports the full 187/194/200/210/220/230/240 grid and
  paired >=200 gains/losses versus K=1 coverage, and never mutates candidates
  or memberships. Focused local validation is green: 38 tests across the new
  freezer/grader, portfolio helpers, both shadow arms, and persistence;
  Python compilation, CLI discovery, shell syntax, and diff whitespace also
  pass. Source commit `c916de4` passed Cloud Build
  `f19ebeb0-5e19-4288-bb50-7bd11bc5e713` with 673 tests passed and 2 skipped,
  producing immutable digest
  `sha256:747aa216d61e25e33a2c31d1d6722449369bb62bab3a8337eff9e71fe19e1e30`.
  Cloud Run jobs `freeze-tail-early` and `freeze-tail-late` are Ready on that
  exact digest with 1Gi/1 CPU, `nfl-dfs freeze-tail-portfolios --slot
  early|late`, one retry, and a 3600-second timeout. Schedulers
  `s-freeze-tail-early` (`5 11 * * 7`) and `s-freeze-tail-late`
  (`50 11 * * 7`) use `America/Chicago` and are both verified PAUSED. Neither
  job has been executed because no matching regular-season Sunday-main source
  panel exists yet.

- Prospective policy v2 is now validated and deployed from source commit
  `e356e1c`. Cloud Build `c2f468ac-405d-4cef-98ed-8cadcda8c08c` passed 675
  tests (2 skipped) and produced immutable digest
  `sha256:19c30dbb0d1ee9fddd55d4f79fc036ba716a2e1dd8788a6f6afa2d23a5381b36`.
  `shadow-k1`, new `shadow-k1-nofloor`, `shadow-k3`, `freeze-tail-early`, and
  `freeze-tail-late` are all Ready on that digest. The three 8Gi/4-CPU shadow
  jobs share possession, `0/0/0/40`, 45/55, 30k-world, artifact, and 80-entry
  contracts; K1/K1-no-floor/K3 differ only in command/panel identity,
  registry/K, and salary floor ($49k/$0/$49k). The freezer now requires all
  three complete unlabeled pools and writes five separately labeled books:
  K1 coverage, K1 top-p, exact K1 no-floor coverage, K3 coverage, and 20/60
  K1/K3. Policy version is `tail-first-v2-20260809`.
- New schedulers `s-shadow-k1-nofloor-early` (Sun 10:30 CT) and
  `s-shadow-k1-nofloor-late` (Sun 11:20 CT) are verified PAUSED alongside
  K1/K3/freezer/training schedules; all nine research schedules remain
  PAUSED. Preseason smoke `shadow-k1-nofloor-b5wqp` failed closed exactly as
  intended—no 2026-09-13 all-Sunday DK group—before model loading,
  generation, or writes. `live_candidates_shadow` still does not exist, so
  zero prospective rows were created. Do not treat this expected failed
  execution as an infrastructure defect.

- The old 27/107 result and the later 17/107 result are invalid controls. The
  former contains illegal repriced lineups; the latter omitted historical DST
  aliases. See the detailed corrections in `CLAUDE.md`.
- The formerly promoted `20260808-livefaithful-b3-ee6f433` (18/107) is
  superseded because its same-image exact replica failed. The current
  accepted and promoted deterministic control is
  `20260808-deterministic-baseline-c616390` on digest `sha256:98a31edd...`:
  107/107 slates, 17,432 candidates, exactly 40 selected per slate, 11/107
  selected clears at 194, mean selected best 173.06, and 20/107 pool-oracle
  clears. Check execution `accept-replay-panel-2t7vn` and promotion execution
  `accept-replay-panel-mlbxt` passed the canonical acceptance and replay/live
  mean-parity contracts. Full same-image replica
  `20260808-deterministic-replica-c616390` passed exact comparison in
  `compare-exact-replay-4j5hz`; the control is reproducible.
- The baseline uses `N_CE=0`, `N_EPISTEMIC=0`, `N_GUMBEL=0`, `N_BOOM=40`,
  `MODEL_ENSEMBLE=3`, and possession simulation. CE, Gumbel, hierarchical
  Gumbel, fast-role, and role-belief variants remain rejected or research-only.
- Cloud Build `b36ed2c6-caa0-4333-9e41-0cafed5f30b8` validated the underlying
  source with `614 passed, 2 skipped` before producing image `ee6f433`.
- Targeted tests on this replacement machine passed for configuration,
  market-implied projections, notes, live smoke, the most recent app flows,
  the two formerly CI-failing replay tests, exact-replay comparator helpers
  (6 tests), and adoption-mechanism helpers (7 tests). Do not run parallel
  tests, local simulations, or other sustained heavy work; use Cloud
  Run/Build.

### Operator tail-first policy amendment — 2026-08-09

- The operator clarified after the completed K=1 comparison, but before the
  candidate-multiple-4 panel completed, that aggregate high-scoring weeks are
  the real utility and that declines in individual seasons are acceptable.
  Mean score is secondary. Future decisions must therefore report season
  variation as risk information, not use the prior four-positive-season and
  at-most-one-negative-season law as an automatic veto.
- Preserve every earlier comparator and disposition under its originally
  frozen law; do not relabel those results as preregistered successes. Under
  the newly clarified utility, however, true-80 K=1 is the current
  **tail-first historical leader**: versus accepted K=3 it moves the
  187/194/200/210/220 counts from `29/19/8/5/1` to `36/22/12/6/3`, keeps
  230/240 at `1/1`, and raises mean weekly maximum 177.08 to 179.60. Its
  season deltas at 200 are `{2019:+3, 2021:-1, 2022:+2, 2023:-1, 2024:0,
  2025:+1}`. This is an explicitly post-result operational interpretation,
  not a retroactive change to `compare-adoption-panel-x9tsz`.
- Freeze the prospective tail-first adoption rule now: require a valid and
  reproducible mechanism, at least **+2 aggregate weeks >=200**, non-worsening
  aggregate >=210, and non-worsening candidate-pool oracle >=200. Report the
  full 187/194/200/210/220/230/240 grid, all season deltas, and mean weekly
  maximum, but neither season signs, >=194, nor mean are hard vetoes. Prefer
  Pareto improvements at 220/230/240; if extreme-tail counts trade off, keep
  the arm research-only until a payout utility is frozen from prospective
  contest/field data rather than inventing retrospective weights.
- The in-progress candidate-multiple-4 arm must still receive its original
  frozen scientific disposition. Because this amendment precedes its full
  result, also apply the prospective tail-first rule as a separately labeled
  operational disposition. Do not inspect or tune individual weeks, K,
  selection line, or another candidate multiple from the outcome.

### Tail-first reinterpretation of earlier valid arms — 2026-08-09

- Reassess only arms whose original rejection depended on the former
  lower-threshold/mean/season-uniformity utility. Do not reopen mechanisms
  that directly lost the 200/210 tail, failed a held-out mechanism gate, or
  were measured only on an invalid historical universe.
- The leading prospective selector hypothesis is **K=1 top individual
  p-line**. On the valid true-80 pool it reached 15 weeks >=200 and 8 >=210,
  versus 12/6 for the promoted K=1 194-coverage book and 8/5 for K=3. This
  rule was found among several post-result sensitivities, so it is not a
  historical adoption; freeze it as a distinct prospective shadow before
  outcomes and grade it with multiplicity clearly reported. K=1 coverage at
  selection line 200 is a weaker secondary clue: 15/6/3 at 200/210/220,
  versus 12/6/3 at line 194.
- The outcome-viewed 20/60 K=1/K=3 allocation is a prospective hedge lead,
  not an adoption. It tied homogeneous K=1 at 12 weeks >=200 and 3 >=220
  while improving 6->7 at >=210. A live implementation must reselect the
  declared quotas from each frozen pool and deterministically backfill
  cross-book duplicate rosters.
- Read-only recomputation of the full valid 40-entry A01/A03 tails found that
  both were more interesting under the amended utility than their old 194
  verdicts showed. The accepted K=3 source's
  187/194/200/210/220/230/240 grid is `26/11/1/1/1/0/0`, mean 173.06, and
  pool-oracle >=200 count 8. Model-only A01 is
  `22/11/3/2/2/0/0`, mean 172.14, oracle 8; both added >=200 weeks were in
  2023. No-floor A03 is `21/11/3/2/1/0/0`, mean 172.43, oracle 9; its added
  >=200 weeks were in 2023 and 2024. Each would satisfy the new aggregate
  tail rule if it had been frozen before those results, but the policy was
  changed afterward. Treat them as hypotheses for fresh K=1 true-80 tests,
  with model-only first because it also added a 220+ week and its 2023w3
  winner is absent from the current K=1 selected book. No-floor is lower
  priority because all three of its historical 200+ weeks are already
  present in the current K=1 book.
- Keep candidate-multiple 4, coherent member-sampled worlds, the conditional
  dependence forest, and K=3 ranked selectors closed: they failed the newly
  important tail directly. Older CE/Gumbel/role arms are not promoted by a
  looser utility because their comparison universe is superseded or their
  tail mechanism was null; CE may receive a clean corrected K=1 exploratory
  test only after the higher-prior selector/model-only work, not a parameter
  sweep.

### Work in progress

- Same-image reproduction panel
  `20260808-livefaithful-b3r-ee6f433` completed and passed ordinary acceptance:
  107 slates, 17,426 candidates, 18/107 clears, mean selected best 175.36.
- Single-member ensemble ablation
  `20260808-a02-ensemble1-ee6f433` completed and passed ordinary acceptance:
  107 slates, 17,488 candidates, 18/107 clears, mean selected best 174.55,
  pool oracle 26/107.
- The exact B3-to-B3r parity audit **failed** in Cloud Run execution
  `compare-exact-replay-pckdb`. All 50,098 player-feature keys and values
  match within the registered tolerance and every candidate's actual score
  matches, but 2019 and 2024 do not reproduce their simulated worlds: 14
  roster keys differ per side, 41 selected flags differ, and 22 slate
  artifacts differ. The other four seasons reproduce exactly. The failure is
  a real reproducibility defect, not an ordinary score loss.
- Do not interpret the K=3 versus K=1 arm yet. Its ordinary acceptance is
  useful only as completeness evidence; the frozen adoption comparator is
  blocked until the same-image control is reproducible.
- Investigation found stable warehouse inputs and exact persisted ensemble
  member point predictions. Component canonicalization eliminated the first
  hypothesis—sub-machine input drift—from the cheap probe and exposed the
  remaining CPU-dependent tied-rank behavior in marginal shaping.
- The first determinism repair was implemented and fully tested: the shared
  live/replay simulator rounds component means to 10 decimal places at its
  boundary and logs raw/effective SHA-256 fingerprints; replay also deduplicates
  its display-only `player_ids` join (which had duplicated 31 old training
  rows) and orders DST inputs. The exact comparator can now compare two
  staging-only smoke probes before a full panel is spent.
- Targeted validation for the repair is green: components (including exact
  seeded equality under machine-epsilon perturbations), replay-shape SQL,
  simulator golden/RNG-parity tests, live smoke, and exact-comparator helper
  tests. The first full repair build,
  `9e42b0d2-418b-4b7d-ae01-93406f247148`, reached 620 passed and 2 skipped but
  failed one repository-layout assertion: recovery had preserved the obsolete
  `sql/features/019_dk_salary_week.sql` alongside its expanded replacement,
  `001a_dk_salary_week.sql`. The obsolete duplicate has now been removed and
  all 66 feature-SQL tests pass locally. Replacement build
  `3a27a669-bf91-465e-ad0c-8aa4a90e2f67` passed the complete suite (619
  passed, 2 skipped) and produced immutable digest
  `sha256:efa18a9a56b62c5c2606eaae3ad37a9765306863a389de8d4af09f8329545a55`.
- The first cheap 2019 probe pair completed on that digest:
  `replay-det19a-2019-lzfjv` and `replay-det19b-2019-45g2g`. Each persisted
  164 candidates for one slate and exactly 40 selected. Their raw component
  hash (`77d4194f...`) and canonical component hash (`3a5abdc4...`) were
  identical, with the same `5e-11` maximum adjustment.
- Exact comparator `compare-exact-replay-g5hf5` nevertheless failed. All 335
  player snapshots and all 164 candidate roster keys matched; player feature
  summaries, actual scores and selected flags were exact. Only the joint
  world assignment drifted: the 164x10,000 totals matrices differed by at
  most 3.1025 points, changing 3 threshold masks and several candidate
  quantiles. This isolated the remaining defect to marginal reshaping:
  NumPy's unstable default quicksort gave tied simulator outcomes different
  ordinal ranks on different CPU implementations while preserving every
  player's marginal distribution.
- Commit `1ab4d32` makes the simulation-column index the stable tie-break for
  both TabPFN and empirical marginal shaping. The focused replay-shape,
  empirical-marginal, draw-widen and SBI suites pass (29 tests). Cloud Build
  `f0251844-2cfe-470c-a12b-f1591f1c97af` then passed the complete suite (620
  passed, 2 skipped) and produced digest
  `sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`.
- The fresh 2019 pair on that digest, `replay-det19c-2019-87z8s` and
  `replay-det19d-2019-cjgvc`, again persisted 164 candidates and 40 selected
  with the same component hashes as the failed pair. Exact comparator
  `compare-exact-replay-zznbf` **passed**: all 335 player snapshots and 164
  candidates matched, candidate ordering did not move, every mismatch count
  and numeric delta was zero, and the full 164x10,000 totals artifact was
  bit-for-bit identical. The 2019 cheap gate is closed.
- The 2024 pair on the same digest, `replay-det24a-2024-bkhfb` and
  `replay-det24b-2024-8zvzx`, also passed in comparator execution
  `compare-exact-replay-mrdnx`: all 700 player snapshots and 161 candidates
  matched, candidate ordering and every mismatch count were zero, and the
  161x10,000 totals artifact was bit-for-bit identical. Both formerly
  drifting-season smoke gates are now closed.
- Fresh default panel `20260808-deterministic-baseline-c616390` completed in
  executions `replay-detbase1-2019-wvc7l`, `...-2021-qtkn4`,
  `...-2022-prk7g`, `...-2023-xkxmz`, `...-2024-x9vv7`, and
  `...-2025-sh6dq`, after preflight `replay-detbase1-smoke-b5djr`. Acceptance
  found 50,098 unique player snapshots, zero missing candidate slates or
  roster players, 17,432 candidates, and exact 107-slate/40-selected
  completeness. Selected clears are 26/107 at 187, 11/107 at 194, and 1/107
  at 200; pool oracle is 20/107 at 194. The 18/107 unstable-world checkpoint
  is not a valid scoring control for later arms.
- Full same-image replica `20260808-deterministic-replica-c616390` completed
  in executions `replay-detrep1-2019-jk6g9`, `...-2021-2hm8h`,
  `...-2022-l7kgq`, `...-2023-r6mqz`, `...-2024-9jdm8`, and
  `...-2025-qmpp2`, after preflight `replay-detrep1-smoke-zzr66`. Check-only
  acceptance execution `accept-replay-panel-2qfbr` passed with the same
  107-slate counts and headline metrics as the promoted control.
- Exact comparator execution `compare-exact-replay-4j5hz` **passed** against
  the promoted control: all 50,098 feature keys and 17,432 candidate keys
  joined with zero mismatch counts, all candidate simulation summaries had
  zero numeric delta, candidate ordering never moved, and all 107
  roster-aligned 10,000-world score matrices were bit-for-bit identical.
  Feature-value round trips were within the registered floating-point
  tolerance (maximum `3.56e-15`). The full deterministic control gate is now
  closed; scoring arms may proceed in the frozen order.
- A01 model-only panel `20260808-a01-modelonly-c616390` completed from the
  same image after preflight `replay-a01model1-smoke-rpw6n`; its six season
  execution IDs are retained in the report directory. The generic baseline
  acceptance execution `accept-replay-panel-xmdlw` intentionally failed only
  its hard-coded 45/55 blend assertion; it still proved 107-slate
  completeness, 50,098 unique feature rows, zero missing joins, and candidate
  mean parity. The wrapper now preserves failed audit logs automatically.
- Mechanism-aware blend comparator `compare-adoption-panel-bc4qd` passed with
  no failures: 15,538 covered player-weeks moved by 0.941 points on average,
  model and market inputs were invariant, all 53 no-market slates reproduced
  exactly, and candidate/player means joined within `2.36e-05`. Model-only
  tied the control at 11/107 clears at 194, fell 26→22 at 187, rose 1→3 at
  200, lowered mean selected best 173.06→172.14, and lowered pool oracle
  20→19. The preregistered disposition is `unsupported-neutral`: neither the
  deletion nor strong incumbent-support directional gate passed. Model-only
  is not adopted; the existing blend remains the default pending future
  evidence.
- A02 K=1 panel `20260808-a02-ensemble1-c616390` completed all six seasons
  after preflight `replay-a02ens1-smoke-cppnj`; check execution
  `accept-replay-panel-w86nj` passed with 17,423 candidates, 107/107 slates,
  50,098 unique feature rows, 16/107 selected clears at 194, mean selected
  best 174.55, and 24/107 pool-oracle clears.
- First ensemble comparator `compare-adoption-panel-5r5vx` failed only the
  assertion that post-shaping player means must move. Code audit proved that
  assertion targets the wrong layer: K changes component beliefs and the
  joint-world rank copula, while full-coverage TabPFN marginal shaping fixes
  each player's downstream marginal distribution. K=1 provenance was exact,
  all 47,692 offensive rows showed K=3 member disagreement, K=1 differed from
  the K=3 member mean by 0.281 points, all other inputs/seeds matched, and the
  post-shaping mean was therefore invariant. The comparator now treats that
  downstream mean as a diagnostic rather than a required direction; focused
  mechanism/panel tests pass (12 tests). No scoring gate was changed. Cloud
  Build `a8ed72ec-d909-447f-881e-3eeaca6b2e7f` then passed the full suite
  (621 passed, 2 skipped) and produced reporting digest
  `sha256:5b7e8e38399c29315a11a8c13c4c2453dc15042c06ed5c29e45b67ac37ebe712`.
- Corrected ensemble comparator `compare-adoption-panel-6kf7z` passed with no
  mechanism failures, but its disposition is `unsupported-neutral`. K=1
  improved the 194 count 11→16, the 200 count 1→9, mean selected best
  173.06→174.55, and pool oracle 20→24. Season deltas were
  `{2019:+1, 2021:0, 2022:+3, 2023:+3, 2024:-1, 2025:-1}`: only three
  positive seasons and two negative seasons, versus the frozen requirements
  of at least four positive and at most one negative. K=1 is not adopted;
  the aggregate gain is retained as a future confirmation candidate.
- A03 salary-floor deletion panel `20260808-a03-nofloor-c616390` changed only
  `MIN_LINEUP_SALARY=0` on the same immutable generation digest after
  preflight `replay-a03floor1-smoke-pddht`. Season executions were
  `replay-a03floor1-2019-cjn9c`, `replay-a03floor1-2021-tl84k`,
  `replay-a03floor1-2022-br5km`, `replay-a03floor1-2023-z8gpc`,
  `replay-a03floor1-2024-nd7bv`, and `replay-a03floor1-2025-vcmkx`; all six
  completed successfully. Check execution `accept-replay-panel-pwlzs` passed
  with 17,514 candidates, 107/107 slates, 50,098 unique feature rows, zero
  missing joins, and replay/live mean parity.
- Salary comparator `compare-adoption-panel-2k87b` passed with no mechanism
  failures. Upstream feature values were invariant. The source generated zero
  candidates below $49k; the deletion generated 3,729 and selected 468 of
  them, with treatment candidate salary minimum $34,100 and selected minimum
  $43,100. The arm tied at 11/107 clears at 194 and 20/107 pool-oracle clears,
  but fell 26→21 at 187 and reduced mean selected best 173.06→172.43. Its
  season-194 deltas were `{2019:0, 2021:0, 2022:0, 2023:+1, 2024:0,
  2025:-1}`. The frozen gate fails; disposition is `unsupported-neutral`.
  Keep the $49k floor and do not tune an intermediate floor on this panel.
- The A03 audit layer was validated in Cloud Build
  `eccb96c1-8fbc-420f-ba37-5d90db0790fc` (624 passed, 2 skipped). Its immutable
  reporting digest is
  `sha256:f6cb471cbb50d5aca186e7f318e29f24d46b83c772cac4951a4c0f4f101ceaee`.
- The operator clarified that the weekly maximum from the submitted portfolio
  is much more important than average lineup score and that 80 entries are
  more likely than 40. Frozen-mask analysis reselected both accepted K=3 and
  staging K=1 candidate pools at 40/80 entries and selection lines
  187/194/200. The 40-entry reconstructions had zero persisted-selection
  mismatches.
- With selection line 194, frozen K=3 moved 11→18 at 194, 1→7 at 200, and
  1→3 at 210 when entries increased 40→80. Frozen K=1 moved 16→22 at 194,
  9→15 at 200, and 5→9 at 210. At 80, K=1 beats K=3 at every measured
  threshold 187 through 220 and its >=200 season deltas are
  `{2019:+3, 2021:0, 2022:+2, 2023:0, 2024:+1, 2025:+2}`—four positive,
  zero negative.
- The 80-entry books each left only one consequential >=200 candidate-pool
  winner unselected. K=3's 2023-week-3 winner was buried at p-line rank
  144/159 and depended on a +30.61 Keenan Allen surprise. K=1's
  2019-week-6 winner ranked 53/161 and could replace one selected entry with
  zero final simulated-coverage loss; it was an ATL/NYJ construction versus
  the selected SEA construction. Deeper audit showed free swaps were common,
  not special to the winners: 32/79 K=3 and 24/81 K=1 unselected candidates
  on those slates had a non-worsening coverage swap. This is a non-unique
  frontier, not permission to hindsight-tune selection. Full evidence is in
  `reports/2026-08-08-80-entry-tail-audit.md`.
- A deterministic, outcome-blind one-swap refinement was added to make that
  claim stronger and reproducible. K=3's missed oracle ranked 25th/30th/26th
  by probability/mean/q99 within its 32-candidate free frontier; local search
  improved coverage 1,795→1,797 but still missed it. K=1's oracle ranked
  4th/10th/4th within 24, yet local search improved coverage 3,595→3,598 with
  other candidates and also missed it. Neither realized maximum changed.
- The frozen 80 result is a lower-bound diagnostic: replay generates
  `CAND_MULT * n_entries` leverage candidates, so a true 80-entry replay has
  160 initial leverage candidates versus 80 in these source pools. The panel,
  acceptance, and comparison runners now accept explicit entry counts while
  defaulting to 40. New selector/audit helpers and focused tests are green.
- Production-faithful 80-entry panels are running on immutable generation
  digest `sha256:98a31edd...`. K=3 preflight
  `replay-e80k3a-smoke-rw4tk` passed, then launched season executions
  `replay-e80k3a-2019-ghcpn`, `...-2021-kl7r7`, `...-2022-t4wzx`,
  `...-2023-6wmkq`, `...-2024-b8ltc`, and `...-2025-qrpkg`. K=1 preflight
  `replay-e80k1a-smoke-gkdnq` passed, then launched
  `replay-e80k1a-2019-hgqwn`, `...-2021-xxqks`, `...-2022-t8d9w`,
  `...-2023-zwbc4`, `...-2024-2z87w`, and `...-2025-k544g`. The manifests
  under `reports/panel-runs/` are authoritative; all 12 season jobs were
  running without a failed condition at the last check.
- Reporting build `38655fa6-f535-45fd-9c03-90392373a167` passed from commit
  `5120014` and produced digest `sha256:835c8320...`. Final comparator build
  `1bce24eb-079e-41d4-8606-e8a63c49605d`, including the explicitly
  preregistered >=200 directional report, also passed and produced immutable
  reporting digest
  `sha256:89f692b6209adbbd070e7b26c998f59f265207877de79496d4419884159410c7`.
- Off-by-default future-arm instrumentation now supports
  `ENSEMBLE_WORLD_MODE=member_sample`: balanced seed-8161 member assignment,
  one coherent member belief per world, centered player point shifts before
  the frozen marginal shaper, and explicit provenance. It requires K>=2 and
  the replay draw path, so it cannot silently affect ordinary projections or
  live defaults. Focused and full local tests pass. It is not preregistered or
  launched; define its same-image comparator only after the running 80-entry
  K=3/K=1 result establishes which configuration is the incumbent.
- Before querying any realized scores from the running true-80 panels, a
  cross-model 80-entry allocation diagnostic was frozen. Report K=1/K=3
  splits `0/80, 20/60, 40/40, 60/20, 80/0`, always selecting at 194 inside
  each model's own true-80 pool and scoring the complete realized tail grid.
  The primary 40/40 split must beat the stronger homogeneous endpoint by at
  least two >=200 weeks, satisfy the standing 4-positive/<=1-negative season
  law, and preserve the 194/210/oracle/mean safeguards. Count cross-book
  duplicate rosters; retaining them in weekly-max scoring is conservative.
  Endpoint strength is ordered by >=200, then >=210, >=194, then mean weekly
  maximum. Use `scripts/analyze_mixed_tail_portfolios.py` after acceptance.

### Deployment caution (superseded by the completed gate above)

The recovered source defaults to the corrected `0/0/0/40` generation budget,
a three-member model ensemble, the 45/55 model/market blend, and the $49k
salary floor. A01, A02, and A03 retain their original scientific
dispositions. Under the later operator-utility amendment, true-80 K=1 with
fixed `12 CE / 28 boom` is now the accepted historical research baseline.
K=3 was the live/stability reference until the pre-season policy gate. That
gate is now complete: the adopted K=1 fixed-CE policy is live, while K=3
remains an isolated prospective stability shadow.

### Next concrete action

The true-80 K=1 model-only arm is complete and closed. All six season jobs
completed cleanly: `replay-e80k1mo-2019-hcxpf`,
`replay-e80k1mo-2021-6s8rw`, `replay-e80k1mo-2022-n5f6s`,
`replay-e80k1mo-2023-n4h4g`, `replay-e80k1mo-2024-qtbq2`, and
`replay-e80k1mo-2025-prbcr`. Reporting build
`95911a3d-8925-4859-bee4-afa5bb69ad8c` passed 673 tests with 2 skipped and
produced audit/comparator digest `sha256:67e20d8308bd...ed4f3f6`. Check-only
acceptance `accept-replay-panel-ggzqg` failed
only its intentionally inapplicable 45/55 assertion while proving complete
107-slate/80-entry provenance and mean joins. Purpose-built comparator
`compare-adoption-panel-qlh5s` had zero failures and returned
`tail-first-not-supported`: selected 187/194/200/210/220/230/240 moved from
`36/22/12/6/3/1/1` to `33/21/12/7/4/1/1`, pool-oracle >=200 fell `19→17`,
and mean weekly max fell `179.60→178.33`. The 200 count trades a new 220.48
in 2025 Week 9 for the lost 201.74 in Week 5; both winning rosters are absent
from the opposing pool. Full mechanism and missed-oracle evidence is in
`reports/2026-08-09-k1-model-only-true80-experiment.md` and the tracked panel
artifacts. Never promote or retune this arm.

The true-80 K=1 salary-floor deletion is complete. The immutable 2022 smoke
`replay-e80k1nf-smoke-7rrbr` and all six season executions passed:
`replay-e80k1nf-2019-nrw5b`, `replay-e80k1nf-2021-zjwt8`,
`replay-e80k1nf-2022-rdvll`, `replay-e80k1nf-2023-57cw8`,
`replay-e80k1nf-2024-gdx9t`, and `replay-e80k1nf-2025-2bpt5`. The complete
result, gained/lost weeks, mechanism, formal failed gate, and post-result
prospective-shadow decision are in
`reports/2026-08-09-k1-no-floor-true80-experiment.md`; immutable acceptance
and comparison artifacts are tracked under
`reports/panel-runs/20260809-e80-k1-nofloor-c616390/`.

The isolated `shadow-k1-nofloor` path is complete and closed until genuine
2026 pre-lock slates exist. Do not add a no-floor/top-p combination, tune an
intermediate salary floor, or query/freeze it before Week 1. No further
historical selector/floor sweep is justified on these 107 known outcomes.

Next, continue the genuinely new-information path: add quota telemetry and a
strictly point-in-time shadow bundle for the already-paid Odds API's unused
volume, touchdown-allocation, and dual-role markets. Preserve existing base
market columns and ingestion jobs, bound requests from measured remaining
quota, store per-book prices/timestamps and response quota headers, and keep
all new features out of production decisions until their held-out residual,
tail-calibration, and candidate-oracle gates are frozen and passed. Do not
launch a historical credit-consuming backfill until the account's remaining
quota and exact request cost are known.

The data-acquisition audit requested during this run is tracked in
`reports/2026-08-09-data-acquisition-priorities.md`. Its ordering is: complete
Classic contest-entry/payout standings first (free and directly aligned with
winning money), one independent ownership/projection source as a measured
trial, expanded shadow use of the already-paid Odds API, then route-level
usage data only if it adds held-out signal. BigQuery has 369,727 prop rows in
10 markets but the vendor exposes many unused volume/TD/combo/tail markets;
the first proposed expansion is shadow-only and quota-metered. The replacement
computer does not need a local Odds API key: both ingestion jobs and the
tracked deployment script now use the existing Secret Manager reference.

Historical full-field backfill was subsequently audited because DraftKings'
free full-standings CSV expires after 10 days. Affordable UI/backtest products
exist, but no public vendor documentation yet guarantees a bulk raw-field
export. First choice is DFS Hero's $1/five-day all-tools trial: BacktestIQ says
it uses real historical opponent fields. Before renewal, require 2023–2025 NFL
Sunday Classic coverage plus either import/grading of our exact 80-lineup
portfolios or usable score/rank/payout output. FantasyCruncher NFL Pro is the
fallback at its current $89.95/month and explicitly includes NFL Lineup Study;
ask support about retained years, contest list, payouts, and export before
purchase. FantasyLabs ($39.95/month NFL) documents historical ownership and
NFL Contest Dashboard lineups but not export or depth. Fantasy Team Advice
advertises projected/live ownership rather than historical fields, and the
claimed Sports Data Direct $34.95 feed could not be verified as current. No
purchase/account creation has been authorized. The exact vendor gate and
primary-source links are preserved in the acquisition report.

The operator subsequently activated DFS Hero's $1 Power trial. Direct access
to the offseason NFL Contest Analyzer listed 309 DraftKings contests for
2025-10-05 and supplied contest-level field, payout, min-cash, and winner
metadata. It did not supply the required underlying fields: both the 161,764-
entry main-slate Millionaire and the distinct main-slate `$40K MEGA mini-MAX`
opened to `Contest data not available`, leaving no leaderboard or CSV export.
DFS Hero therefore fails the current backfill gate unless its support team can
identify a working retained 2023–2025 NFL Classic field and explain a temporary
offseason defect. Do not allow the $149.95 renewal. The fallback remains a
pre-purchase export/coverage confirmation from FantasyCruncher rather than
another blind subscription.

A targeted GitHub/public-repository audit found no usable archive of settled
historical DraftKings NFL ownership or full contest fields. The closest live
repository, `925Sports/925Sports-nfl-dfs-data`, was created in August 2026 and
publishes current projected `RST%` ownership from a Google Sheet, not settled
post-lock historical ownership. Older optimizer repositories contain
salaries/scores or expect the user to supply projected ownership; exact
DraftKings standings-header searches found no public field archive. This is
not presently an acquisition path: BigQuery already has 103,556 actual
ownership records across 1,258 contests and every week of 2022–2025. Continue
searching only for the material gaps—verified 2019–2021 actual ownership or
complete entry/rank/payout fields—and keep source provenance/license checks.
The linked evidence is preserved in the acquisition report.

The operator then confirmed the acquisition direction: existing 2022–2025
actual ownership is sufficient. Do not buy or prioritize additional aggregate
historical ownership, including the 2019–2021 gap. Historical acquisition now
requires complete entry-level lineups/ranks/duplication/payouts to justify
cost; an independent projected-ownership feed remains only a prospective,
timestamped signal trial.

The arm/UI promotion gate in the README's August 24 runbook completed on
August 9; see the current section above for the policy, validation, image,
revision, and exact resume action. Keep all fourteen seasonal schedules paused
until August 24. Do not execute either source shadow or freezer before DK
posts the matching regular-season Sunday main slate. Never mutate the pre-lock
candidate or membership records, and do not retune K, the 194 control target,
the top-p rule, the 20/60 quota, or its asymmetric duplicate backfill on the
107 known historical slates or after prospective outcomes begin.

### 2026-08-08 true-80 completion update

- Both production-faithful panels completed and passed acceptance. K=3
  `20260808-e80-k3-c616390` has 25,813 candidates; K=1
  `20260808-e80-k1-c616390` has 25,787; both cover 107 slates with exact 80
  selections. K=3 check/promote executions were
  `accept-replay-panel-vlw7c` / `accept-replay-panel-d6fbn`; K=1 check was
  `accept-replay-panel-cjct8`.
- At selection line 194, K=3/K=1 scored 29/36 >=187, 19/22 >=194, 8/12
  >=200, 5/6 >=210, 1/3 >=220, and mean weekly maxima 177.08/179.60.
  K=1's >=200 season deltas are `{2019:+3, 2021:-1, 2022:+2, 2023:-1,
  2024:0, 2025:+1}`. Only three seasons improve and two regress, so the new
  high-tail gate fails. At 194 four improve but two regress, so the old gate
  also fails. Do not adopt K=1 or weaken the stability law.
- Official comparator `compare-adoption-panel-x9tsz` ran on digest
  `sha256:458dd21d9074a1a3a35222c5b3aa67c4e331b4ee2e3ea62768c7870ef52fe4a1`
  after Cloud Build `1520f9b3-9f76-47bc-ba15-47f4d621c22b` passed 636 tests.
  Mechanism failures were zero; disposition is `unsupported-neutral`.
- The primary 40/40 mixed book failed (9 >=200, three negative seasons).
  Sensitivity 20/60 tied K=1 at 12 >=200 and improved to 7 >=210, but it is
  post-result sensitivity only and improves just three seasons vs K=3. The
  40/40 book had 392 duplicate roster slots across 96 slates.
- K=3's true pool has 12 >=200 opportunities and captures 8; K=1 has 19 and
  captures 12. The four/seven consequential misses are fully audited. A
  deterministic pre-lock one-swap refinement recovers none, so no simple
  greedy repair is supported. Week-level results are in
  `reports/2026-08-08-true80-weekly-max.csv`.
- Next preregistered pair uses same-image digest `sha256:458dd21d...` and code
  `d99b125`: control `20260808-e80-msctl-d99b125` versus treatment
  `20260808-e80-msarm-d99b125`, true 80, K=3, selection line 194, default
  `0/0/0/40`, with treatment only `ENSEMBLE_WORLD_MODE=member_sample` seed
  8161. Use the unchanged >=200 high-tail gate and the new `member_world`
  mechanism comparator. Do not tune allocation/K/line/seed/budgets.
- Member-world preflights passed: control `replay-e80msc-smoke-mzzgb` and
  treatment `replay-e80msm-smoke-ns5pj`. Treatment logged balanced member
  counts `[3334,3333,3333]` at seed 8161. All six season executions per arm
  are launched; immutable IDs are authoritative in each panel's
  `reports/panel-runs/.../executions.txt` manifest.
- Member-world reporting build `b9c6fb26-6a7d-4e40-bd49-4863fc0d2a99`
  passed 638 tests (2 skipped) and produced immutable digest
  `sha256:29bb404d84e1a6d8d27d94f4204ffa6fbac7d97dab164c54069c4a4a9ec02dea`.
  Use it for both acceptance runs and the `member_world` comparator.
- The deeper true-80 missed-winner audit now measures each oracle against its
  nearest selected simulated-support substitute. None of the 11
  consequential >=200 misses is support-dominated by a selected lineup; the
  nearest support Jaccard is only 0.140-0.464, while every selected entry owns
  unique worlds. This rules out simple duplicate pruning and attributes the
  residual misses to joint-outcome beliefs/candidate ranking. Focused
  validation: `tests/test_tail_portfolio.py`, 7 passed. Full Cloud Build
  `8b8ba490-a181-408b-bba0-a13a36b69790` passed 638 tests (2 skipped) and
  produced immutable audit-tooling digest `sha256:c591980d...`. Production
  selection was not changed.
- The member-world pair completed with all 12 season executions clean: both
  panels have 25,813 candidates, 107 slates, and exactly 80 selections per
  slate. Control check/promote executions were
  `accept-replay-panel-jcx6k` / `accept-replay-panel-wkxsd`; treatment check
  was `accept-replay-panel-b4tqk`; official comparator was
  `compare-adoption-panel-hz7f7`. All durable acceptance/comparison artifacts
  are tracked under the two panel report directories.
- The mechanism passed strongly: 24,118 support masks, 3,545 rosters, and
  2,100 selected slots per side changed with zero invariant-feature or
  same-roster-actual mismatches. At the frozen 194 selector, treatment moved
  187/194/200/210 counts from 29/19/8/5 to 32/20/6/4 and mean weekly max
  177.08→177.94. Its >=200 season deltas are `{-1,0,0,0,-1,0}`; pool oracle
  remains 12. It fails the primary high-tail, stability, and 210 gates and is
  `unsupported-neutral`; keep `ENSEMBLE_WORLD_MODE` off.
- Treatment expands consequential >=200 misses from four to six. The lost
  2019w15 204.66 and 2024w5 211.12 control winners remained available in the
  treatment pool with nearly unchanged marginal probability/mean but were
  displaced by changed joint-world overlap. Outcome-blind local refinement
  recovers none of the six misses. Full evidence is in the 80-entry audit.
- Candidate-budget comparator instrumentation is implemented and focused
  validation is green (39 tests plus shell syntax). It requires default
  `CAND_MULT=2` versus explicit 4, exact invariant features/seeds/shared-roster
  worlds, a strict source candidate subset with extra leverage candidates on
  all 107 slates, and selected-book movement. It also fixes disposition
  reporting so a genuine primary high-tail pass is labeled
  `high-tail-improves`; no score threshold changed. The exact arm and frozen
  gate are in Addendum 113 and the 80-entry audit.
- Full candidate-budget reporting validation passed in Cloud Build
  `d0fc0c32-e055-4765-bcf6-3854aa7ec29d` (641 passed, 2 skipped). Its
  immutable reporting digest is
  `sha256:6c4d71ab991fe26460d77094b84e7cef3579a33a18437d1ba28998e29e50bf70`.
  Use this digest for the treatment acceptance and `candidate_budget`
  comparator.
- Candidate-multiple-4 treatment `20260808-e80-cm4-d99b125` passed preflight
  execution `replay-e80cm4-smoke-2wbs8` in 17m42s. First-slate throughput of
  14-16 minutes proved the inherited 10,800-second task timeout insufficient
  for 17-18 weeks. Before any score was inspected, all six season executions
  were cancelled, their 1,610 partial candidate and 2,406 feature rows were
  transactionally deleted, and the identical jobs were relaunched with only
  timeout extended to 21,600 seconds. Authoritative execution IDs are
  `replay-e80cm4-2019-sb95x`, `replay-e80cm4-2021-2zmrk`,
  `replay-e80cm4-2022-hns7s`, `replay-e80cm4-2023-bfk69`,
  `replay-e80cm4-2024-slxz5`, and `replay-e80cm4-2025-9zsqq`. The cancelled
  IDs and reason are retained in `superseded-executions.txt`; image, CPU,
  memory, args, arm, and seeds did not change. Do not inspect realized scores
  before the full panel completes; row-count/status monitoring is allowed.
- The authoritative candidate-multiple-4 panel has now persisted all 107
  slates, 42,706 candidates, and exactly 8,560 selected rows. Executions for
  2021-2025 are clean successes. The 2019 container explicitly logged
  `exit(0)` at `2026-08-09T10:07:53Z` after persisting all 17 slates, but its
  Cloud Run execution/task metadata remains `Completed=Unknown` with a
  `WaitingForOperation` 30-minute retry condition. Canonical acceptance
  correctly aborted rather than bypass that clean-success contract. Do not
  delete, rerun, promote, or manually override the panel; wait for the control
  plane to reconcile, then rerun `cloud_accept_panel.sh` in check mode.
- Reporting code now implements the separately labeled prospective
  tail-first gate documented above while retaining the frozen scientific
  disposition. It requires +2 aggregate >=200, non-worse >=210, non-worse
  pool-oracle >=200, and a valid panel/mechanism; season signs, >=194, and
  mean remain diagnostics. Focused comparator validation passes 26 tests.
  Full Cloud Build validation is the next step; use its resulting reporting
  digest only after the original immutable candidate-budget comparison is
  also preserved.
- Tail-first reporting validation passed Cloud Build
  `c1080fc9-3210-401c-9f7a-21e048a98d9e` with 655 tests passed and 2 skipped;
  validated image digest is
  `sha256:81ac495c696ca05cddf39208a652896bc73e55dc49e21e8377adbe5fbfa758a9`.
  The earlier direct Docker build `b95d8af8-bb47-423d-ba87-d1371612c0ed`
  succeeded but did not run tests and must not be cited as validation.
- Original-image acceptance execution `accept-replay-panel-fjwz7` passed mean
  parity, all 107 slates, 42,706 candidate rows, 50,098 unique feature rows,
  exact labels/joins, and selected structure, but failed only the old fixed
  candidate range `(80, 400)` on 46 deliberately enlarged slates. This is a
  reporting-contract defect: that ceiling predated and cannot represent the
  registered `CAND_MULT=4` arm. No scoring gate is changing.
- Acceptance now requires a caller-declared candidate multiple to match every
  persisted `lever_env`. Default multiple 2 preserves the old `(80, 400)`
  range exactly; true-80 multiple 4 receives the bounded `(80, 480)` range
  derived from `entries * (multiple + 2)`. The wrapper passes the declaration
  explicitly. Focused acceptance/comparator validation passes 32 tests plus
  shell syntax. Build, rerun check mode as `... check 80 4`, then run the
  immutable mechanism comparison and the separately labeled tail-first
  report; never promote a failed treatment.
- The accepted K=3 missed-winner analysis now separates genuinely lost weeks
  from redundant high scores: 16 unselected >=200 rows span eight slates, but
  ten are on slates where the submitted book already cleared 200; six rows
  create only four consequential missed weeks. Outcome-blind top-80 books by
  p-line/mean/q99 each recover two of those misses but fall from 8→7 aggregate
  >=200 weeks. The best K=3 60/20 coverage/rank hedge only ties eight >=200
  (though 5→6 at 210) and worsens 194. K=1 ranking/hybrid sensitivities reach
  14-15 >=200, but remain positive in only three seasons and negative in two
  versus K=3. No selector change is supported. New reusable ranked/hybrid
  diagnostics pass all nine focused tests; details are in the 80-entry audit.
  The high-unselected table now includes selected weekly best, signed gain,
  and whether the candidate actually adds a 200+ week, so dominated raw
  scores cannot be misread as missed winners.
- Exact weekly pool maxima are selected on 74/107 slates and omitted on 33;
  omitted-oracle median regret is 6.36 and max regret 35.52, while all-slate
  mean regret is 2.72. Only five omitted maxima reach 200: the four threshold
  misses plus 2019w15, where unselected 207.14 beats selected 204.66 by 2.48
  but does not add another 200+ week. The analyzer now prints this broader
  weekly-max view via `--top-unselected-oracles` so threshold summaries cannot
  hide smaller payout-relevant upgrades.
- Against 68 known same-week Milly winning scores, corrected true-80 K=3
  beats 0, comes within 20 points in 0, within 30 in 2, and within 40 in 7;
  mean gap is 60.69. Its candidate-pool oracle also beats 0/68 and narrows
  mean gap only to 57.69. K=1 likewise beats 0 and is never within 20. Thus
  194/200 are comparison markers, not top-prize claims; almost all of the
  first-place gap precedes selection. The analyzer now reports this same-week
  winning-line context automatically.
- Only 7/33 omitted weekly oracles have a non-worsening coverage swap, and
  zero of the five omitted 200+ oracles do. Even 2019w15's 207.14 costs six
  simulated covered worlds in its best swap. Thus the high omissions are not
  free/tied selector choices; current pre-lock beliefs explicitly prefer the
  scenarios that occupy those slots.
- Paired-week evidence also supports retaining the frozen stability law.
  Preregistered K=1 coverage has seven gained versus three lost 200+ weeks
  against K=3 (one-sided exact paired `p=0.172`). Post-result top-p-line has
  eleven gained versus four lost (`p=0.059` uncorrected), but was selected
  from several sensitivities. Treat it only as a prospective shadow lead, not
  as permission to relax the historical gate or play it as the incumbent.
- The four consequential K=3 missed oracles are not obvious contrarian
  lottery tickets. Their naive pre-lock ownership-product ranks are at the
  78.8th-95.0th percentiles of the selected books, and all are more popular
  by proxy than that week's selected-best lineup. They span five or six games
  rather than sharing an omitted concentrated-stack shape. Actual duplication
  cannot be recovered without historical classic entry rows, so this is a
  caution—not a payout claim—but it further argues against hindsight swaps.
- Full validation of ranked/hybrid diagnostics passed Cloud Build
  `b24be18a-13c8-4912-b324-04d872981ebe` (643 passed, 2 skipped), producing
  immutable tooling digest
  `sha256:805a7c1e4e8bfdcf088bc0c4a169ef31196a9a35f88e68c58f24a9bbe91ce5f0`.
- Superseding full validation including weekly-oracle, coverage-cost, and
  same-week Milly-line context passed Cloud Build
  `9a33319b-db99-4f4d-95ae-58016db7382f` (643 passed, 2 skipped), producing
  immutable audit digest
  `sha256:21489a693a72cb533551e9603db60b53af2fe3e8867fd788e6cac96a304cac59`.
- A conditional dependence mechanism was logged and frozen in the 80-entry
  audit before launch: learn walk-forward conditional weights over fixed-role
  historical game-residual templates with an MMD-style random-feature forest,
  then rank-reorder the current calibrated marginals. Off-by-default
  implementation uses `SCHAAKE_TEMPLATE_MODE=forest`; focused tests cover
  leakage exclusion, context weighting, integration, exact marginals, and
  default seeded-path invariance. The exact seed/dimensions and three-season
  gate are frozen in the audit. It must first beat production on both held-out
  role-pair variogram error and joint-q90 tail Brier while preserving every
  marginal draw multiset. Only a passing dependence gate may reach a newly
  preregistered candidate-oracle stage; do not tune it on the 107 realized
  portfolio outcomes.
- The diagnostic is hardened with `SCHAAKE_DIAG_ONLY=1`, which returns before
  role-belief, market-blend, candidate-generation, persistence, and lineup
  scoring paths. `scripts/cloud_dependence_panel.sh` launches only the frozen
  2023-2025 reports after an immutable-image smoke, and
  `scripts/compare_dependence_panel.py` applies the machine-readable weighted
  aggregate/stability gate. `scripts/cloud_finish_dependence_panel.sh`
  requires three clean immutable executions and verifies each diagnostic-only
  exit before recording either a positive or negative scientific result.
- Conditional-dependence Cloud Build
  `107a8e47-1a31-4dc6-a7b8-5d95562bdb60` passed 650 tests (2 skipped) from
  mechanism commit `3dbebb2` and produced immutable digest
  `sha256:12cdf18151af051ac766e302514cceaf34c3d9cf320d13bd1467ed8e88e96978`.
  Use that digest for the smoke and frozen 2023-2025 dependence-only panel.
  Commit `a8c0c38` is only the local log harvester/docs and need not be in the
  diagnostic image.
- Immutable-image smoke `conditional-schaake-smoke-xnt89` passed. Frozen run
  `20260809-forest-dep-3dbebb2` launched 2023/2024/2025 executions
  `dependence-forest-2023-hrh2x`, `dependence-forest-2024-zvrz9`, and
  `dependence-forest-2025-srdqt`. The exact manifest is tracked under
  `reports/dependence-runs/20260809-forest-dep-3dbebb2/`.
- All three dependence executions completed cleanly and emitted the required
  diagnostic-only exit. The forest improved role-pair variogram error in all
  three seasons and aggregate **0.168911→0.165064**, but worsened joint-q90
  tail Brier aggregate **0.017582→0.017635**; only 2023 improved both metrics.
  Machine disposition is `dependence-gate-fails`. The mechanism is valid and
  active (2,304/2,576/2,848 templates; mean effective weights about
  229/239/238) but does not proceed to candidates or scoring. Do not tune its
  seed, forest size, leaf size, RFF dimension, roles, features, or seasons on
  this result.
- The known-real-winner audit now resolves all 612 player slots from 68 Milly
  winners against the immutable accepted K=3 snapshots. The pool exposes
  8.51/9 winning players on average, but its closest candidate contains only
  3.46. That assembly is not below an exposure-preserving null (3.30), and
  winner-pair occurrence is 0.368 versus null 0.366; selection is likewise
  3.31 versus 3.22 and 0.325 versus 0.330. The old broad assembly-defect story
  does not survive the corrected true-80 baseline. Only 33/612 winner slots
  are missing from the entire pool; they average 22.74 actual versus 7.19
  projected (+15.55 surprise), led by WR/TE. New reusable
  `real_winner_overlap.py` diagnostics and two focused tests are tracked. No
  construction or selector lever is adopted from this outcome-aware audit.
- The same real-winner diagnostic on rejected K=1 finds essentially equal
  player coverage (8.50/9; 34 missing slots) but modestly higher pool/selected
  closest-roster overlap (3.53/3.44 versus K=3 3.46/3.31) and realized
  oracle/selected-best overlap (2.31/2.24 versus 2.07/1.97). Paired
  selected-best overlap gains 25, ties 27, and loses 16 weeks. This is a
  legitimate prospective K=1-shadow lead but cannot override its frozen
  three-positive/two-negative season defect.
- Real-winner audit Cloud Build
  `3469c6ad-06fa-4058-8287-f8d4adecc81e` passed 652 tests (2 skipped) from
  code commit `dd08bd8` and produced immutable digest
  `sha256:81b9faa89829bc5035fdb135e9df8c39ed0f74b5f8ddc6ee5f5dcf2e29950a4a`.
- Candidate-budget acceptance repair passed Cloud Build
  `0cba47ea-954e-451e-b481-f93585d4b593` with 657 tests passed and 2 skipped;
  validated reporting digest is
  `sha256:4182a4c077a1dcc183be3c82dfcfa44d60d8909dc5807a4996622a49bab29fdd`.
  Check-only acceptance `accept-replay-panel-z5ncj` then passed the complete
  42,706-row, 107-slate, true-80 multiple-4 panel. Do not promote it.
- Candidate-budget comparator `compare-adoption-panel-ljdlp` completed with
  zero failures. The treatment is a strict superset on all 107 slates:
  25,813 shared rows plus 16,893 new leverage rows, 153-160 extras per slate,
  exact shared actual/p-line/mean/support values, exact invariant player
  features, and 1,832 selected slots changed in each direction.
- At the frozen 194 selector, candidate multiple 2→4 moves
  187/194/200/210/220/230/240 from `29/19/8/5/1/1/1` to
  `30/22/9/2/1/1/1`; mean weekly maximum moves 177.08→177.27. The 200 gain is
  only +1, all in 2021, and 210 loses three weeks. Frozen disposition is
  `unsupported-neutral`; the prospectively amended operational disposition
  is `tail-first-not-supported`. Raw candidate scaling is rejected and closed
  on this historical panel; do not tune multiple 3/5/8 or selection line.
- Deeper treatment audit finds 16 pool-oracle weeks >=200 versus 12 for the
  control, but only 9 are selected. Seven consequential >=200 oracle weeks
  remain unselected: 2025w12 220.86, 2019w9 216.42, 2025w11 213.58, 2025w2
  210.64, 2019w6 205.44, 2023w16 202.74, and 2025w9 202.50. Only 2025w2 has
  a non-worsening one-swap; the outcome-blind refinement still misses it.
  Across all realized rows, 55 unselected >=200 candidates span 14 slates,
  but most are redundant to an already higher selected score.
- Exact source/treatment joining shows all four newly created >=200 oracle
  weeks are extra leverage rosters and all remain unselected: 2025w11
  213.58, 2025w2 210.64, 2023w16 202.74, and 2025w9 202.50. Conversely, the
  sole selected >=200 gain—2021w11 205.20—already existed in the smaller
  control pool; the added candidates only changed coverage interactions
  enough to select it. That reshuffle displaced control 210+ winners in
  2022w14 (214.02→206.42), 2023w3 (212.38→201.28), and 2024w5
  (211.12→202.42). This is direct evidence that selection/belief interaction,
  not absence from the raw generator, limits the submitted extreme tail.
- The enlarged pool preserves individual real-winner-player coverage at
  8.51/9 and the same 33/612 missing winner slots. Closest candidate overlap
  rises modestly 3.46→3.57, but selected overlap remains 3.31 and same-week
  first-place gaps remain enormous (selected/pool mean 60.17/55.68; 0/68
  wins or within 20). More leverage candidates add opportunities without
  fixing selection or rare-boom beliefs.
- Declared sensitivities do not displace K=1. Multiple-4 at selector 187
  reaches 10 >=200 and 5 >=210; top simulated-mean selection reaches 10/6
  and 2 >=220, but both trail K=1's 12/6/3 and are outcome-viewed
  sensitivities. K=1 remains the tail-first historical leader under the
  operator's amended utility. Next work must develop K=1 under the new
  prospective policy or add genuinely new prospective field/belief data—not
  mine another selector/multiple on these 107 known outcomes.
