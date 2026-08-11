# Fantasy Points same-season Advanced Passing protocol

Preregistered on 2026-08-10 CDT before any exact-window Advanced Passing
value was joined to a target-week outcome. The completed season-N-1 Advanced
diagnostic and its failure are known; this protocol asks the distinct timing
question opened by the newly proven vendor Week(s) filter.

## Question and immutable collection

Do quarterback process traits measured over exactly the last four completed
weeks improve 30-point QB-tail forecasts beyond the existing pre-lock
projection and point-in-time controls?

Use only the tracked plan
`automation/fantasy_points/plans/same-season-advanced-passing-last-four-v1.json`.
It contains 56 grouped-header Player exports: seasons 2022--2025, target Weeks
5--18, and source Weeks W-4 through W-1. Same-week or future-week data,
cumulative-season exports, the vendor opponent, Week 1--4 targets, postseason
and files outside the final manifest are forbidden. Every artifact must pass
the downloader's response-payload, rendered-table and downloaded Season/G
scope checks; intake must independently verify its hash, shape, target week,
source weeks, context and `1 <= G <= 4`.

## Frozen rows, support and features

Resolve QB identities without outcomes against the corrected accepted replay
snapshot universe. Evaluation rows require an authoritative actual and a
non-null pre-lock `mean_projection`. A treatment row is supported only when
the source window has at least 80 quarterback dropbacks. Unsupported rows
remain in availability reporting but do not enter either comparison arm.

The control inputs are exactly the QB slice of the prior-season Advanced
diagnostic: `mean_projection`, salary, `target_share_last`,
`target_share_jump`, `snap_share_last`, `snap_share_jump`,
`team_vacated_target_share`, `depth_rank`, and `games_played_prior`.

Treatment adds the entire predeclared process-rate/time block rather than an
outcome-selected subset:

- `CPOE`, `aDOT`, `Deep Throw %`, `YAC %`, `ADJ CMP %`;
- `1Read %`, `ACC %`, `CATCH %`, `OFF %`, `HERO %`, `TWT %`;
- `DROP %`, `TTT`, `TTP`, `TTSK`, `TTSC`;
- `PRESS %`, `PRESS SK %`, `PrROE`, `CHK %`, and `RPO %`; and
- scramble rate, computed as `Scrambles::SCRM / Passing::DB`.

Percentages are converted consistently to fractions. Raw passing counts,
standard box-score outputs, fantasy-points columns, raw pressure/drop counts,
the vendor opponent and any unlisted derived interaction are excluded.
Training-fold median imputation and standardization apply to both arms. No
field subset, transform, support threshold, window, interaction,
winsorization or regularization sweep is licensed after outcomes are read.

## Frozen walk-forward comparison

Use target Weeks 5--18 and held-out seasons 2023, 2024 and 2025:

- held-out 2023 trains on target-season 2022;
- held-out 2024 trains on 2022--2023; and
- held-out 2025 trains on 2022--2024.

Within each fold, regression predicts `actual - mean_projection` with
`Ridge(alpha=10.0)`. Classification predicts `actual >= 20` and
`actual >= 30` with
`LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)`. Report fold and
aggregate Brier loss, residual MAE, event counts, missingness, support and
identity coverage, calibration deciles, and each treatment feature's
Spearman projection-residual and point-biserial 30-point correlations.
Descriptive correlations cannot select or remove fields.

## Frozen gate and consequence

The mechanism passes only if supported coverage is at least 50% in every
held-out fold and aggregate 30-point Brier loss is strictly lower for the
treatment. Per-season 30-point Brier, aggregate 20-point Brier and residual
MAE are mandatory diagnostics but are not vetoes, consistent with the
operator's extreme-tail objective.

A pass licenses one separately preregistered QB candidate-union test; it does
not directly change projections or production. A valid failure closes this
exact family. This protocol may not be amended from the observed diagnostic
or lineup outcomes.

## Pre-outcome status

Exact-window behavior is proven on two 2025 samples, and an outcome-blind
redundancy screen established that several process fields are not reproduced
by current QB features. The 56-export plan, manifest-locked importer,
strict-prior attachment, walk-forward diagnostic, CLI and backup coverage are
implemented. Focused synthetic tests and a parse of all 52 rows in the real
2025 Weeks 1--4 schema sample passed. Collection, table writes, outcome
diagnostic and any lineup test have not started.

Exact-tree Cloud Build `adc359ee-ee1d-4914-a251-680cf05dd221` passed 801
tests with 2 skipped and produced immutable image
`sha256:b1292d1ed171e20edf94e8a2f6ded5d63fdb1f83e9daa91e8d3acb6f37fa7d98`.
Use that digest only after the future 56-export run passes its locked importer.
