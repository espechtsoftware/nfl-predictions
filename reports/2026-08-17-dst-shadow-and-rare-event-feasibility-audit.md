# DST shadow law and rare-event sampling feasibility audit

Date: 2026-08-17
Status: score-free source/mechanics audit; no cloud execution launched

## Scope and evidence boundary

This report answers the two prerequisite questions accepted in
`2026-08-17-extreme-tail-review-reconciliation-and-queue-amendment.md`:

1. Can the repository support a discrete, event-coherent DST shadow law using
   point-in-time inputs?
2. Can the current simulator support valid rare-event or importance sampling
   while retaining auditable weights for the original production law?

The audit inspected source code, schemas, tests and design documents only. It
did **not** inspect a partial ATLAS population, treatment body, effect,
historical score or lineup-selection score. It did not change a production
policy, launch a local heavy simulation, launch a cloud job or modify
`HANDOFF.md`.

Reviewed upstream decision artifacts:

- `reports/2026-08-17-extreme-tail-system-review-and-recommendations.md`,
  SHA-256
  `c2eedcae7c9f7dce15dd3ca4051d964a48284cb87647e254eea52e07f5175017`
- `reports/2026-08-17-extreme-tail-review-reconciliation-and-queue-amendment.md`,
  SHA-256
  `48fd7ac14feecb58db20121ce97f8daea99619c9206eefa99dc6726cf5811dcb`

## Executive verdict

| Question | Verdict | Consequence |
|---|---|---|
| Is DST currently a simulated lineup-world outcome? | **No.** Money policy supplies one static DST projection in every world. | The omission in the external review is confirmed. |
| Is the old `DST_CORR_DRAWS` arm an event law? | **No.** It is a scalar continuous anti-correlation transform. | Its prior result neither validates nor kills a discrete DST shadow. |
| Are historical DST component labels available? | **Yes.** The canonical PBP scorer already identifies all DraftKings DST components and points allowed. | A score-free source/mechanics phase is feasible without buying another feed. |
| Are sufficient PIT covariates available? | **Mostly.** Prior PBP form, opponent vulnerability, market snapshots and optional SIS context exist; weather and historical market timing require explicit as-of handling. | Freeze an as-of data contract before fitting. |
| Can the current possession simulator emit an event-coherent DST state? | **No.** It emits aggregate offensive points/safeties and then discards the drive path. | Add a research-only event ledger and explicit two-team coupling before a DST historical shadow. |
| Does the current simulator expose a sufficient restart/checkpoint state? | **No.** There is no public step/snapshot/restore API, independent per-world RNG or weight ledger. | Adaptive splitting/conditional SMC is a prerequisite engineering project, not a runnable arm. |
| Can ordinary importance weights simply be added around the current final worlds? | **Not validly.** The proposal density is unspecified, while finite-batch normalization and rank shaping make final worlds depend on the entire batch. | Do not reuse cross-entropy weights or label a tilted run “same law.” |

The immediate recommendation is therefore asymmetric:

- **DST:** proceed with the bounded source/mechanics and event-ledger work below,
  then run distribution/covariance characterization before any lineup scoring.
- **Rare-event sampling:** implement and prove a restartable research kernel and
  independent finalization law first. It is not ready for a cloud slot.

## A. Current DST mechanics

### A.1 Production and replay behavior

The live path appends DST rows with `draw_idx=-1`
(`src/nfl_dfs/inference/live_lineups.py:321-334`). `_row_draws` repeats the
point projection in every simulation for any negative draw index
(`src/nfl_dfs/backtest/engine.py:633-654`). The frozen production environment
explicitly sets `DST_CORR_DRAWS` to empty
(`src/nfl_dfs/inference/production_policy.py:151-176`). Thus the selector can
never choose a lineup because that lineup's DST booms in one particular world.

`src/nfl_dfs/inference/dst_projections.py` is a point/summary model, not a
world generator. It uses an opponent-implied-total signal, trailing DST form
and opposing-QB experience, with a fallback mean of 6.0 and fixed standard
deviation of 5.4 (`:22-24`). Its emitted `p_20_plus` is the constant `0.03`
(`:91`), so that field is not a calibrated slate-specific event probability.

The dormant `DST_CORR_DRAWS` code does create continuous draws by combining a
fixed `-0.491` opponent-offense correlation with iid Gaussian noise, clipping
and mean-renormalizing (`src/nfl_dfs/backtest/engine.py:654-680`). It does not
represent sacks, turnovers, return touchdowns, blocked kicks, safeties or
points-allowed tiers and cannot enforce an event identity with the opposing
offense. It remains a useful negative diagnostic, not an implementation of the
new mechanism.

### A.2 Repository-verified DraftKings DST scoring law

The component list below is not inherited from the external review. It is the
law implemented independently in `sql/features/024_team_defense_week.sql` and
`research/recourse_scoring.py:507-515`, with the event-credit and points-
allowed behavior pinned in `tests/test_feature_sql.py:111-135` and
`tests/test_recourse_scoring.py:262-315`:

- sack: +1;
- interception: +2;
- opponent fumble recovery: +2;
- safety: +2;
- blocked punt/field goal/extra point: +2;
- defensive or special-teams return touchdown: +6;
- defensive two-point conversion: +2; and
- points-allowed tiers: +10/+7/+4/+1/0/-1/-4.

It also handles franchise aliases and uses the recovery/TD team rather than
blindly assigning every special-teams event to `defteam`. Its points-allowed
calculation subtracts defensive touchdowns and safeties surrendered by the
offense before choosing the tier (`:104-143`). Where an authoritative
historical DST score is available in the salary feed, that exact score
overrides the reconstructed total (`:173-222`). The output retains each event
count **except `defensive_conversions`** plus `pa`; only the aggregate-score
lags `dst_points_l4` and `dst_points_l16` are materialized (`:224-233`). The
conversion count is used in the scalar expression but omitted from the final
selected component columns. D0 must correct that source-schema omission before
claiming a complete event vector.

There is **no yards-allowed fantasy-scoring component** in either canonical
DST implementation or its tests. The external review's conditional “any
DraftKings yards-allowed component that applies” therefore resolves to none
under this repository's frozen DK NFL Classic law. Defensive passing/rushing
yards may be predictive covariates, but they must not add fantasy points. A
future contest-format/rule change requires a versioned scoring-law update; it
must not be inferred from another fantasy platform.

Two small rule details also need an explicit 2026 freeze instead of an
assumption:

- The scorer subtracts the six points of an offensive pick-six/fumble-six from
  the affected DST's PA, while leaving the ensuing PAT charged to PA. The
  latter behavior is explicitly asserted in
  `test_dst_scorer_mirrors_event_and_points_allowed_rules`.
- A defensive two-point conversion earns +2 for the converting DST, but the
  current PA exclusion subtracts only defensive-return TD points and safeties,
  not the conversion from the other side's PA. No focused test resolves that
  reciprocal PA detail. D0 should bind the current-season contest rule or an
  authoritative example and then either retain it deliberately or repair both
  canonical implementations together.

### A.3 Canonical outcomes already in the repository

`src/nfl_dfs/research/recourse_scoring.py` independently supplies reusable PBP
event extraction. `DST_COMPONENTS` includes sacks, interceptions, fumble
recoveries, safeties, blocked kicks, return touchdowns and defensive
conversions (`:42-50`), while the skill-player scorer identifies QB
interceptions and fumbles lost (`:225`, `:316`). Its tests cover pick-sixes,
sacks, fumble recovery, points-allowed exclusions, blocks and returns
(`tests/test_recourse_scoring.py`). This is enough source material for a
single canonical, versioned team-game event vector; a third scorer should not
be invented.

The exact-score override matters. A PBP event vector can be mechanically
coherent while its reconstructed scalar total differs from an authoritative
feed row. The calibration frame must preserve both the component provenance
and an explicit reconciliation status/override rather than silently replacing
components to force the total.

### A.4 Existing tail-model scaffold

`src/nfl_dfs/research/dst_tail.py` already defines a useful strictly-prior
research panel. It uses opponent implied total/spread, DST score form, prior
sacks/takeaways/return-TD form and opponent sack/giveaway rates. Every rolling
window ends at `1 PRECEDING` (`:20-53`), and the classifier is season
walk-forward (`:71-107`). This is a reasonable baseline for occurrence
probabilities and calibration, but it predicts one threshold label. It does
not create a joint event vector or couple that vector to player worlds.

## B. PIT-safe input inventory

The data contract should define a common Sunday-main lock timestamp and prove
that every feature was knowable at that instant. “Prior week” and “snapshot as
of lock” are different joins and both need assertions.

### B.1 Feasibility by season

This is the source boundary supported by repository code and durable intake
records. D0 must still census the physical warehouse before freezing exact row
counts; code-level availability is not a substitute for a table receipt.

| Seasons | Core event-law status | Market/weather timing status | Optional context |
|---|---|---|---|
| 2014-2017 | nflverse PBP is in the configured 2014-present backfill range, so canonical DST events and completed-prior-game form are feasible. These seasons precede the 2018-2025 possession-table fit and PFR advanced-defense coverage. | Only nflverse schedule lines/historical game weather are presently documented; they lack a common-lock snapshot receipt. Treat them as characterization proxies or omit them. | No FTN; no current SIS tranche. |
| 2018 | Core PBP plus the first season represented in the fitted possession terminals; PFR advanced defense begins here. | Same historical snapshot limitation. | No FTN; no current SIS tranche. |
| 2019 | Core PBP/possession support. | Same historical snapshot limitation. | SIS team context is present. |
| 2020 | Core PBP/possession support. | Same historical snapshot limitation. | The imported SIS team-context tranche has no 2020 season, so SIS must be null/absent rather than imputed from adjacent seasons. |
| 2021 | Core PBP/possession support. | Same historical snapshot limitation. | SIS team context is present. |
| 2022-2025 | Core PBP/possession support. | Same historical snapshot limitation; do not call nflverse closing lines common-lock PIT. | SIS team context and FTN pressure are present; the purchased weekly data may be used only through W-1. |
| 2026+ | PBP labels become available only after games complete; live features may use prior completed games. | `raw.odds_snapshots` first began landing in 2026 and carries `pulled_at`; `raw.weather` is likewise timestamped. These seasons can support a real latest-at-or-before-common-lock join. | SIS/Fantasy Points recurring acquisition is prospective and must fail closed when a source week or manifest is missing. |

The configured training window starts in 2015, but a D0 event-support census
may include 2014 as run-up. It should not silently mix those roles. The
possession terminal constants were fit on 2018-2025 only; using them in a
2014-2017 characterization is an explicit transport assumption, not a
season-specific fit.

Authoritative exact DST labels are available only where
`raw.dk_salaries_historical` has a matching team/opponent row. Repository
history documents broad RotoGuru coverage in 2014-2021 and later-source
coverage where imported, but it also documents historical salary gaps. The
event frame must therefore report exact-label coverage by season rather than
declare any entire 2022-2025 season exact without a warehouse census. PBP
reconstruction remains available where the exact override is absent.

### B.2 Input-level PIT rulings

| Source/input | Availability | PIT ruling | Intended use |
|---|---|---|---|
| `raw.pbp` completed-game events | Existing | Safe only from games completed before the target slate; all rolling windows must end at W-1 | Event labels; prior defense sacks/takeaways/returns; opponent dropbacks, sacks, giveaways, special-teams opportunities |
| `features.team_defense_week` | Existing | Its two aggregate lags are strictly prior; same-week component/score columns are labels only | Canonical event vector, PA tier and historical target |
| `research.dst_tail.DST_TAIL_SQL` features | Existing | Windows are explicitly prior | Baseline occurrence/tail model and support census |
| `features.defense_week_allowed` | Existing | Prior-six defense form when joined through the leakage-checked feature path | Opponent passing/rushing efficiency and red-zone context |
| FTN pressure (`features/017i_ftn_offense.sql`) | Existing, 2022+ | Prior-six only | Free pressure tendency ablation |
| SIS `raw.sis_team_context_game` | Existing for covered seasons | Use only games before target; `analysis/sis_team_context.py` already constructs prior-L4 windows | Optional pass-defense/pass-rush/blocking context, not a required v1 dependency |
| Schedule spread/total (`features.schedule_long`) | Existing | Historical nflverse lines are closing lines without a snapshot timestamp; they are a proxy, not proof of common-lock availability | Legacy historical baseline only, with an explicit proxy flag |
| `raw.odds_snapshots` | Existing prospectively | Safe when choosing the latest DraftKings row with `pulled_at <= common_lock`; never choose latest without the cutoff | Live total, spread and implied opponent points |
| `raw.weather` | Existing prospectively | Underlying rows have `pulled_at`; query as of lock. Current `features.game_weather` selects the latest snapshot and historical schedule fallback, so that view is not sufficient for strict historical as-of proof | Optional wind/precipitation/dome ablation |
| Prospective injury snapshots | Existing prospectively | Latest observation at or before lock; historical rows without reliable modification timestamps are not strict PIT | QB/OL/edge/returner availability only after a timestamp-completeness gate |
| Fantasy Points weekly reports | Existing for selected years | Completed prior weeks only; never target-week results | Optional contextual ablation after free/PBP law works |

Two source repairs are required before fitting:

1. Materialize lagged **component** rates/counts, not only lagged aggregate DST
   points, with support counts and missingness by season.
2. Add reusable `as_of_common_lock` selectors for odds and weather. In
   particular, `sql/features/020_game_weather.sql:4-10` currently chooses the
   latest forecast with no as-of cutoff, so it cannot be used unchanged in a
   historical PIT panel.

## C. Missing DST calibration and required coupling

### C.1 Calibration that does not yet exist

Before DST can enter a lineup world, the following must be estimated or
measured season-walk-forward:

- distribution of sacks conditional on opponent dropbacks, offensive sack
  tendency, defense pressure and game script;
- interception occurrence conditional on opponent pass volume and QB
  giveaway tendency;
- fumble occurrence, recovery team and fumble-return touchdown conditional on
  an actual fumble opportunity;
- defensive touchdown probability conditional on a turnover and return
  opportunity, separated from kick/punt/blocked-kick returns;
- safety, blocked-kick and defensive-conversion base rates with hierarchical
  shrinkage because their team-season support is sparse;
- points-allowed tier distribution conditional on opponent offense and market
  state; and
- the joint distribution, not just independent marginal rates, of the event
  counts above.

For the sparsest events, a hierarchical empirical/Beta-binomial or
template-resampling law is safer than a high-capacity classifier. Each fit
must report the season/event support that actually identifies its parameters.
An event with inadequate support should fall back to a pooled prior and say so;
it must not receive a volatile team-specific estimate.

### C.2 Event identities with the opponent offense

A coherent shadow needs one game/world ledger rather than an independent DST
bonus draw:

- Each DST interception is the same event as `-1` for the opposing QB.
- Each lost fumble is the same event as `+2` for the recovering DST and `-1`
  for the relevant offensive player. Main `simulate()` currently does not
  sample fumbles lost.
- Sacks should arise from opponent pass/dropback state. They do not directly
  deduct offensive DK points, but they can end drives, change field position
  and suppress passing output.
- A pick-six/fumble-six/blocked-kick return is conditional on its initiating
  event. It adds non-offensive scoreboard points, changes subsequent script
  and must **not** count against the scoring DST's PA tier in the opposite
  direction.
- A safety is simultaneously a DST event, non-offensive scoreboard event and
  possession change.
- Opponent offensive points must drive the PA band after excluding points the
  offense itself surrendered. Simply using the game's final total is wrong.
- A large lead may shift subsequent opportunity toward the DST's own RB and
  away from its opponent; that correlation requires explicit script feedback,
  not merely multiplying both by a post-hoc DST score.

This dependence is deliberately two-sided. It should create coherent
DST/lead-RB stories **and** remove impossible DST-boom/opponent-offense-boom
stories. A lower aggregate book maximum would not by itself prove a bug.

Returner identity is not presently part of the player simulation. Version 1
may score a team-level special-teams return without crediting a player if and
only if that limitation is explicit. Player-returner covariance is a later
mechanism requiring a PIT return-role source.

## D. Possession-simulator sufficiency for DST

The terminal probabilities in `src/nfl_dfs/models/game_sim.py` are real-PBP
fits from 2018-2025, not placeholders (`:1-29`, `:54-100`). They are useful
starting priors, but the current execution interface discards the state a DST
law needs:

- `_simulate_team_drives` holds `zone`, terminal draws, points and safeties in
  local arrays, then returns only `(points, safeties_conceded)`
  (`:136-183`).
- It simulates the same team's next drive and skips the opponent's intervening
  drive. The next zone is therefore a fitted two-possession-later same-team
  quantity, not a literal turnover takeover spot.
- `simulate_game_points` runs each team's full sequence independently. Its
  only cross-team links are drive counts within one and safety credit
  (`:198-253`). It does not alternate possession, transfer a turnover's field
  position or maintain score-differential state.
- The dormant `SCRIPT_FEEDBACK` branch changes second-half drive counts after
  a coarse halftime margin (`:225-249`); production disables it and it still
  does not create an event ledger.
- `team_game_factors` converts aggregate points to multipliers by dividing by
  each finite simulation batch's sample mean (`:286-328`). Player opportunity
  and scoring events are then drawn separately in `models/simulate.py`.
- `models/simulate.py` samples QB interceptions but discards the event array
  after computing points (`:425-448`); it has no main-path fumbles-lost or
  sacks event and production disables the passing-TD ledger.

Therefore the current possession simulator is an outcome-factor generator,
not a joint football event generator. It is **not sufficient unchanged** for
event-coherent DST worlds.

## E. Bounded DST prerequisite and test plan

### Phase D0 — canonical source frame (no lineup outcomes)

1. Freeze a versioned scoring-law table from the two repository
   implementations: component values, PA tiers, explicit absence of a
   yards-allowed fantasy component, PAT handling and defensive-conversion PA
   handling. Resolve the untested conversion detail against the applicable
   contest rules before changing code.
2. Extract one versioned team-game event vector from the canonical
   `024_team_defense_week.sql`/`recourse_scoring.py` logic.
3. Include **all** event counts (including the currently omitted output column
   for defensive conversions), offensive points allowed, excluded non-offensive
   points, PA tier, authoritative scalar score, reconstruction score,
   reconciliation status and source hashes.
4. Census rows and nonzero support by season for every component and for
   15+/20+/25+ totals. Fail closed on duplicate `(season, week, game, team)`
   keys, opponent mismatches or unreconciled score differences.
5. Build strictly prior component/opponent windows and common-lock market/
   weather selectors. Run the repository leakage checks plus explicit
   `max(source_week) < target_week` and `pulled_at <= lock` assertions.

### Phase D1 — research-only event ledger

Add an opt-in interface such as `keep_event_ledger=True` that returns, per
game/team/world:

- own offensive points;
- opponent offensive points;
- non-offensive/safety points separately;
- drive count and terminal counts;
- sacks, interceptions, fumbles/recoveries, blocks, returns, return TDs,
  safeties and conversions; and
- the exact PA tier and derived DK DST score.

The default path must consume the exact same RNG stream and retain its golden
checksums. The research implementation should use explicit alternating
possessions if it claims turnover field-position or script coherence. Merely
adding counters to the current same-team-next-drive approximation is acceptable
only as a labeled lower-fidelity diagnostic.

Do not marginal-rank-map a floating DST score if that breaks the event sum.
Any marginal calibration must select/reweight attainable event vectors or
calibrate the component probabilities so the final DST score remains exactly
the sum of its discrete components and PA tier.

### Phase D2 — score-free distribution/mechanics gate

Evaluate season-walk-forward, with frozen thresholds and no lineup outcomes:

- event-count means, variances, zero mass and upper quantiles;
- exact scorer identity in every generated world;
- PA-tier frequency and 15+/20+/25+ reliability/Brier curves;
- proper distribution scores such as CRPS/log score where defined;
- covariance with opponent QB, WR and TE; own-team RB; spread; total; and
  underlying opponent offensive points;
- conservation checks for interceptions/fumbles/safeties/return touchdowns;
- calibration by season plus a sparse-event support table; and
- comparison against static DST and the old continuous correlation transform
  as diagnostics, without treating the latter as the control law.

Only a mechanically coherent, calibrated D2 pass licenses a separately frozen
candidate-story characterization. It does not license money-policy adoption.

## F. Rare-event/importance-sampling audit

### F.1 The current engine has no sufficient checkpoint

There is no public `state -> step -> state` interface. A drive's zone and
terminal outcome live only inside a vectorized function call; the trajectory
is discarded. `simulate()` uses one batch-global NumPy generator
(`src/nfl_dfs/models/simulate.py:254`) and consumes it sequentially across game
factors, opportunities, yardage and touchdowns. There are no independent
per-world RNG substreams that can be cloned and advanced after a checkpoint.

Two additional batch dependencies make post-hoc weighting unsafe:

1. `game_factor_matrix` and `team_game_factors` divide every world by a mean
   estimated from the same finite batch (`game_sim.py:271-282`, `:319-327`).
   Changing or resampling one world changes the other worlds' factor values.
2. `apply_draw_shape` widens and then rank-maps the entire batch through
   TabPFN/empirical marginals (`backtest/replay.py:325-385`). A final served
   world is therefore not currently a deterministic function of that world's
   own independent latent state alone.

The attainable-lineup reaction coordinate becomes available only after the
complete final-served player world and optimization. There is no intermediate
coordinate attached to a restartable football state.

Verdict: the current engine cannot support adaptive multilevel splitting,
conditional SMC or likelihood-ratio importance sampling with a defensible
claim that the samples target the unchanged production law.

### F.2 Minimum sufficient restart state

A restartable research kernel must serialize at least:

- immutable slate, component, marginal-model and policy identities/hashes;
- game/team/world identity and an independent counter-based RNG state;
- drive/half index, possession owner, both teams' current field-position state
  and remaining/target drive or clock state;
- own offensive, non-offensive and safety points separately;
- terminal/event counts, score margin and any script variables;
- player opportunity/allocation state, clearly divided into already sampled
  fixed state and future conditional state;
- the reaction-coordinate level/history and clone genealogy; and
- accumulated `log p`, `log q` (or exact stratum probability), proposal-kernel
  ID and support/absolute-continuity flags.

Restoring this record and continuing with the stored RNG counter must reproduce
an uninterrupted ordinary path byte-for-byte. Because the present simulator
skips opponent possessions, merely serializing its local `zone` array would
not create a meaningful joint-game checkpoint for a claim about football
event conditioning.

### F.3 Why current cross-entropy machinery cannot supply weights

Cross-entropy candidate generation changes which optimized lineups are found;
its sampling/ranking weights are not automatically Radon-Nikodym weights for a
changed football-world distribution. Reusing them would conflate proposal
search with probability estimation. A valid importance sampler must declare
the exact base density `p`, proposal density `q`, every tilted latent and
`log(p/q)` before observing results, with `q > 0` wherever the target event has
positive `p`.

Ordinary rejection sampling of completed production worlds would be unbiased,
but it would not solve the rare-support compute problem. Stratified sampling
can be a simpler first valid method only if stratum probabilities and
conditional draws are exact under the base law.

## G. Rare-event prerequisite and test plan

### Phase R0 — choose the estimand and algorithm before code

Freeze one of:

- adaptive multilevel splitting/subset simulation with a Markov mutation
  kernel proven invariant for the conditional base law; or
- explicit importance sampling with known base/proposal densities and exact
  log weights.

Freeze the reaction coordinate, levels/proposal family, ordinary-mixture
fraction, story/diversity strata, seed blocks, stopping rule and all numerical
gates before treatment output. An ordinary-law mixture component is required
to protect against missed modes.

### Phase R1 — restartable research kernel

1. Refactor to pure `initial_state`, `step`, `snapshot`, `restore` and
   `finalize` functions under an opt-in research interface.
2. Give each `(slate, seed, world, game)` an independent `SeedSequence` or
   counter-based stream.
3. Replace finite-batch sample normalization with frozen PIT constants, or
   formally include the complete ensemble in the state. The former is much
   more tractable.
4. Serialize the schema version and all input/policy hashes with each state.
5. Expose pre-shape latents and a deterministic finalizer.
6. Resolve the rank-transform problem. Prefer a frozen per-player PIT
   inverse-CDF map so one world's final draw is independent of who else was in
   its batch. Prove ordinary-law parity before using it for weighting.

### Phase R2 — unit and toy-law proof

- Exact snapshot/restore equality against uninterrupted paths at multiple
  checkpoint locations and seeds.
- Two clones are identical through the checkpoint and diverge only after
  their independently advanced mutation streams.
- Analytic toy Markov chain: event probability, normalizing constant and
  likelihood-ratio estimate agree with the closed form.
- Proposal support is absolute-continuous; no nonfinite weights; empirical
  mean weight is compatible with one.
- Genealogy, unique-ancestor count, ESS and maximum normalized weight are
  emitted and deterministic from a receipt.
- Opt-in disabled preserves current ordinary-law golden checksums.

### Phase R3 — ordinary-law numerical agreement

Before one rare world can generate a lineup:

- weighted estimates agree with ordinary Monte Carlo at 187 and 194 within
  preregistered confidence intervals across independent seed blocks;
- repeated weighted estimates are stable and report uncertainty appropriate
  to genealogy/weights;
- every world has an auditable weight and no weighted world enters an
  unweighted money selector;
- final-served player means/quantiles remain within frozen tolerances; and
- cross-score any generated column on the untouched ordinary production
  worlds.

The previously documented prospective efficiency gates should remain:

- at least 25% lower relative standard error at 210/220;
- ESS at least 25%;
- maximum normalized weight at most 1%; and
- at least +10 percentage points of exact-80 overlap/stability under the
  registered comparison.

Failure of ordinary-law agreement is terminal for the claimed same-law method,
even if the tilted sample contains attractive stories.

## Queue consequence

This audit satisfies the requested readiness determination but does not launch
either mechanism.

1. The **DST source/mechanics phase is feasible now** as local code/schema
   work. It remains behind the already frozen earlier queue entries for heavy
   compute.
2. A **DST historical lineup run is not yet licensed**. D0-D2 must pass first.
3. **Rare-event sampling is not a queued cloud arm**. R0-R2 are mandatory
   prerequisites, followed by R3 numerical agreement.
4. These mechanisms use different research laws and receipts. DST changes the
   simulated joint law; rare-event sampling must estimate a frozen law without
   changing its target. They must not be combined until each passes alone.

## Validation performed

The current scoring-law claims were checked against the focused repository
tests, not inferred from an external rules summary:

```text
.venv/bin/python -m pytest -q \
  tests/test_feature_sql.py::test_dst_actuals_credit_event_team_and_exclude_offense_points \
  tests/test_feature_sql.py::test_historical_dst_exact_labels_preserve_rescheduled_game_exception \
  tests/test_recourse_scoring.py::test_dst_scorer_mirrors_event_and_points_allowed_rules
... [100%]
```

All three passed. `git diff --check` also passed for this report. No simulation
or outcome-scoring test was run.

## Evidence files bound for this audit

The following source hashes describe the mechanics inspected here:

| File | SHA-256 |
|---|---|
| `src/nfl_dfs/inference/dst_projections.py` | `1b257641548b7b4e9603893551183b5a2b8fb8083034b88e6ef7b17b9d45c514` |
| `src/nfl_dfs/models/game_sim.py` | `60efa921436dd1c185fd980db3bdec8ae99147d45b73fa557dc9173a664aebf8` |
| `src/nfl_dfs/models/simulate.py` | `850f33bca392e580a2e73b49aa01289d0404631c479606d67c4c227d42b7f47c` |
| `src/nfl_dfs/backtest/engine.py` | `394e54a77260d5972ab2ad1c94824a42592a33eeba2255c436232ec53eed8e95` |
| `src/nfl_dfs/backtest/replay.py` | `f7b654f336b34d0ec47bfec214c85cb7c507b34e9632e916548573187843a789` |
| `sql/features/024_team_defense_week.sql` | `5cd626b3407f6c2f3a1bebf044310b0424d72d9c9f0caec430df10f01723e419` |
| `src/nfl_dfs/research/recourse_scoring.py` | `59568badb3dc9072bcdc5dc071c469eb9a8ea105508923a954543b4ec2ebd35d` |
| `src/nfl_dfs/research/dst_tail.py` | `fa4295304aa18e86506bebc9b57273da93d61d35175e6127f997889229e14ca1` |
