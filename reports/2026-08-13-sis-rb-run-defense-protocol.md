# SIS RB run-defense Points Saved protocol

Status: frozen 2026-08-13 after the disclosed exploratory correlation audit
and before implementing this cache arm, computing either arm's model output,
computing a final-served metric or reading a lineup score.

## Question and adaptive disclosure

The paid SIS run-context audit read active-RB outcomes and found that strictly
prior opponent run-defense Points Saved/play was inversely associated with RB
projection residual, beating projection by ten, and scoring at least 20, 25 or
30 points. Residual and beat-10 directions repeated in 2023, 2024 and 2025.
The feature is only moderately related to the incumbent opponent rush-EPA
field (`r=-0.4531`) and nearly unrelated to SIS opponent YAC/attempt
(`r=0.0890`). This is adaptive hypothesis generation, not confirmation. Only
the prospective gate below can license a lineup test.

## Terminal inheritance and only difference

Both arms inherit the terminal active-only label law, shared-33 feature list,
TabPFN 2.2.1, strictly-earlier-season context, 28,000-row context cap, RNG
sequence, four estimators, seed 7, target keys and 2022--2025 folds of accepted
cache `tabpfn_active_label_treatment_v2`. SCHED, team-QB and the SIS QB-line
features remain absent. The control must reproduce that inherited cache on
every key and numeric prediction within `1e-10` before scientific evaluation.

The treatment appends exactly one column, only on RB rows:

- `sis_rb_def_ps_per_play_l4`

QB/WR/TE values are null. No YAC, EPA, positive rate, Boom%, Bust%, offense
metric, interaction, hand coefficient, threshold, hyperparameter or sampling
change is permitted.

## Frozen point-in-time definition

Source is private write-once table
`nfl_raw.sis_team_run_context_game`, source run
`sis-team-run-context-tranche-2-v1`. The generator must bind table row count,
schema, source-run identity, original/recovery plan and state hashes, and full
content checksum in both arm reports.

For player target `(season, week, team, opponent)`:

1. Select the opponent's SIS team rows from the same season.
2. Sum `rdef_points_saved` and `rdef_attempts` over the opponent's last four
   completed games after `shift(1)`, requiring at least two games.
3. Define `sis_rb_def_ps_per_play_l4` as the summed numerator divided by the
   summed denominator; zero denominator is null.
4. Join by `(season, target_week, opponent)` and expose the value only for
   `position='RB'`.

Every supported source week must be less than target week. No current-week,
future-week, cross-season, league-average or zero fallback is allowed. Tests
must prove target-week mutation invariance, unique team-week source keys,
opponent rather than offense attachment, unchanged player row count and null
non-RB values.

## Frozen cache and score-free gate

- Control: `nfl_features.tabpfn_sis_rb_rdef_control_v1`
- Treatment: `nfl_features.tabpfn_sis_rb_rdef_treatment_v1`
- Folds: 2022 calibration plus 2023--2025 evaluation
- Positions: QB/RB/WR/TE with inherited encoding
- Quantiles: 0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70,
  0.80, 0.90, 0.95, 0.99
- Write contract: new research-only tables with `WRITE_EMPTY`

Mechanical validation requires exact key/source/law/hyperparameter equality,
ordered finite quantiles, the exact feature contracts, changed treatment
predictions, at least 80% supported active-RB rows in each 2023--2025 fold,
and exact inherited-control reproduction. A failure stops before scientific
scoring.

If mechanical validation passes, reconstruct both caches under the terminal
possession simulator, finite Dirichlet `K=28.154043586960896`, 10,000 worlds,
seed 0, fitted widening and 45/55 model/prop-market blend. Independently fit
each arm's final-served position scale from strictly earlier out-of-sample
folds: 2022 for 2023, 2022--2023 for 2024 and 2022--2024 for 2025. The
historical reconstruction panel is the active-label selection's bound source
`20260811-pitclean-e80-k1-role12union-a12ab31`. Mean preservation tolerance is
`1e-10`.

The primary population is active RBs in 2023--2025. Pass if and only if
treatment aggregate 30-point Brier is strictly below control and all
mechanical/mean invariants pass. Brier-20, CRPS, pinball losses, point MAE,
season slices, calibration, support and paired slate-cluster uncertainty are
diagnostics. There is no per-season sign veto.

A failure closes this exact one-column arm historically. Do not add YAC,
positive rate or Boom% after reading it. A pass licenses exactly one
separately frozen paired exact-80 comparison under the operator's terminal
weekly-maximum order `240,230,220,210,200,194,187`, with first differing count
deciding and mean weekly maximum breaking a complete threshold tie. This arm
does not alter production, authorize new SIS queries, or replace the distinct
alignment/conditional-allocation queue.
