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

## Current state — 2026-08-10 16:10 CDT

### Tail-improvement research resumed; role-belief test preregistered

- Branch `main`; the live adopted policy remains unchanged at
  `classic-k1-ce12-boom28-v1` from accepted panel
  `20260809-e80-k1-ce12-c616390`. Its true-80 selected weekly-max counts at
  187/194/200/210/220/230/240 remain `40/26/18/11/5/2/1`; mean/median are
  `181.1243/178.64`, and pool-oracle counts are `47/32/22/13/5/2/1`.
- A fresh accepted-panel audit found that the pool omits 36 of 612 player
  slots across 28 of 68 matched Millionaire winners, concentrated at WR (12),
  TE (11), and RB (7). Those missing slots averaged 21.11 actual points versus
  7.82 projected. The pool has an unselected weekly maximum on 25/107 slates,
  but only four nonredundant unselected oracles clear 200, so another flexible
  selector search is not justified on the same 107 outcomes.
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
  zero-tuning deterministic one-swap refinement is now implemented as a sixth
  early/late frozen book under `tail-first-v3-20260810`; it is
  prospective-shadow-only and cannot affect the adopted/UI portfolio. Deep
  generative dependence work is deferred until more field data exist.
- Exact next action: wait for all six exact union executions, run the union
  comparator on immutable digest `sha256:a410648b...`, and commit its JSON and
  Cloud Run execution. Launch the fixed arm only if that tracked union gate
  passes.

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
