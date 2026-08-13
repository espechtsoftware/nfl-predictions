# SIS QB offensive-line context protocol

Status: frozen 2026-08-13 before implementing the cache arm, generating a
control or treatment cache, computing a model prediction, computing a
final-served score, generating a lineup or reading a lineup outcome.

## Question and adaptive disclosure

The paid SIS team-context audit was explicitly exploratory and read player
outcomes. On the accepted active-player population, recent offensive pass
blown-block rate was negatively associated with QB projection residual and
beating projection by ten points in all three evaluation seasons. Aggregate
blocking Points Earned/play was positively associated with beat-10 in all
three. This protocol therefore asks whether that fixed two-column
offensive-line bundle improves the accepted TabPFN marginal model's QB tail
probabilities.

This is an adaptive follow-up, not a pristine confirmation of the correlation.
The model gate below is frozen before model output and is the only result that
can license a lineup test. The audit's correlations cannot promote the arm.

## Terminal inheritance and only difference

Both arms inherit the terminal active-only label law, shared-33 feature list,
TabPFN version, strictly-earlier-season context, context cap, RNG sequence,
four estimators, seed, target keys and 2022--2025 folds of accepted cache
`tabpfn_active_label_treatment_v2`. SCHED and team-QB CPOE were rejected and
remain absent. The control must reproduce the inherited cache on every key and
numeric prediction within `1e-10` before the treatment is eligible.

The sole treatment difference is appending, only on QB rows:

- `sis_qb_pass_bb_l4`
- `sis_qb_block_pe_l4`

RB/WR/TE values for both columns are null. No hand coefficient, threshold,
interaction, pressure feature, opponent defense field, extra SIS column,
hyperparameter or context-sampling change is allowed.

## Frozen point-in-time feature definition

Source is the private, write-once
`nfl_raw.sis_team_context_game` table with source run
`sis-team-context-tranche-1-v1`. The generator must bind its row count,
schema, source-run identity and full-table content checksum in both arm
reports.

For each `(season, team, target_week)`:

1. At source game grain, compute `pass_block_blown_blocks / pass_block_snaps`;
   a zero denominator produces null.
2. Set `sis_qb_pass_bb_l4` to the arithmetic mean over the last four completed
   games in the same season, after `shift(1)`, requiring at least two non-null
   observations.
3. Set `sis_qb_block_pe_l4` identically from SIS
   `block_points_earned_per_play`.
4. Join by the player's point-in-time `(season, week, team)` and retain values
   only for `position='QB'`.

Every supported source week must be strictly less than the target week.
Weeks without two prior games remain null; there is no current-week,
future-week, cross-season, league-average or zero fallback. Tests must prove
target-week mutation invariance, unique team-week keys, unchanged player row
count and null non-QB values.

## Frozen cache pair and mechanical gate

- Control table: `nfl_features.tabpfn_sis_qb_line_control_v1`
- Treatment table: `nfl_features.tabpfn_sis_qb_line_treatment_v1`
- Target seasons: 2022, 2023, 2024, 2025
- Labels: only `was_active=true` context rows with non-null `y_dk_points`
- Positions: QB/RB/WR/TE with the inherited position encoding
- Quantiles: 0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60,
  0.70, 0.80, 0.90, 0.95, 0.99
- Context cap: 28,000; estimators: 4; RNG/model seed: 7
- Write contract: new research-only tables with `WRITE_EMPTY`

One immutable GPU image/code pair must generate both arms. Mechanical
validation requires exact target-key equality, exact common source and label
law, ordered finite quantiles, the exact feature contracts, changed treatment
predictions, at least 80% supported active-QB rows in each 2023--2025 fold,
and exact control reproduction. Any failure closes the run before scientific
scoring.

## Frozen score-free final-served gate

Reconstruct both caches under the terminal possession simulator, finite
Dirichlet `K=28.154043586960896`, 10,000 worlds, seed 0, fitted widening and
45/55 model/prop-market blend. Independently fit each arm's final-served
position-scale schedule on strictly prior out-of-sample folds: 2022 for 2023,
2022--2023 for 2024 and 2022--2024 for 2025. Applying a scale must preserve
each row mean within `1e-10`.

The historical reconstruction panel is
`20260811-pitclean-e80-k1-role12union-a12ab31`, the `historical_source` bound
by the terminal active-label selection. The later
`20260812-pitclean-e80-selected-tabpfn-active-v2` panel contains only the
2023--2025 exact-80 comparison folds and therefore cannot supply the required
2022 walk-forward calibration fold; it is not an interchangeable source.

The primary population is active QBs in 2023--2025. The arm passes if and only
if treatment aggregate 30-point Brier is strictly lower than control and all
mechanical/mean invariants pass. Brier-20, CRPS, pinball losses, point MAE,
season slices, calibration, feature support and paired slate-cluster
uncertainty are diagnostics. There is no per-season sign veto and no average
lineup-score condition.

A failure closes this exact two-column arm historically. Do not tune its
window, minimum games, population, columns or feature scope after seeing the
result. A pass licenses exactly one separately frozen paired exact-80
comparison; it does not itself promote production. That comparison must use
the operator's terminal weekly-maximum law in order
`240,230,220,210,200,194,187`, with the first nonzero count deciding and mean
weekly maximum only breaking a complete threshold tie.

The expected failure mode is declared before output: this is a QB marginal
feature entering a simulator whose principal measured defect is QB-to-receiver
joint-tail dependence. If the treatment improves MAE and/or CRPS but not the
registered QB Brier-30 gate, that confirms the recurring marginal-versus-tail
pattern and closes only this two-column arm. It does **not** imply that SIS is
uninformative. In particular, it does not close player-level defender/
receiver-alignment or conditional target-allocation mechanisms, which act on a
different channel and require separately frozen protocols.

## Production and acquisition safety

The feature is research-only until every licensed stage passes. Current live
models, UI and lineup policy remain unchanged. This protocol neither licenses
additional SIS queries nor changes the paused tranche-2 plan. Receiver
coverage/alignment, run-context and adjusted-blocking variants remain separate
future protocols and may not be folded into this arm.
