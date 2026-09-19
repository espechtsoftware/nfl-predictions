# Observed-zero target prior: bounded historical calibration screen

Freeze before reading the diagnostic's historical target labels. This reopens the opportunity-prior implementation after the current salary repair exposed structural zero support. It is a player-level, season walk-forward exploratory screen, not a new lineup-panel read, adoption authority, or validation of realized 220+ performance. No current-season outcomes are available to the reader.

## Support and fixed input

The existing hsim benchmark training extract ends in 2024. Its outcome-free support census is retained, but it cannot supply a six-season test including 2025. Use instead the already-frozen **common, byte-verified control/repaired historical training panel through 2025** from the complete-chain preflight: 102,927 rows, Parquet SHA `445de23a683c17437723c98f4619296f742d13f5843bcb90a77b97af88308419`. The [current support census](reviews/evidence/2026-09-19-zero-target-prior-current-support.json) records all eligible cells without reading labels. It has 97/114/153/184/192/198 eligible rows in 2019/2021/2022/2023/2024/2025, respectively. This does not silently change the live hsim historical fit.

Eligible rows are RB/WR/TE with observed `target_share_l4 == 0`, prior snap share at least .20, at least one prior game, and the original hsim activity mask true. The original mask, positional target fallbacks and all noneligible weights remain unchanged. Carry priors are unchanged. Historical validation targets are `y_targets` divided by that season/week/team's total nonnegative, nonmissing `y_targets` across its training rows; all rows with missing targets or a zero team total are separately counted and excluded from target-share loss. Do not fill missing labels as observed zero. Report identity uniqueness, all cohort counts and team target coverage limitations.

## Two fixed arms against observed zero

1. **One-prior-game rule:** eligible zero receives the existing positional target fallback divided by `1 + min(games_played_prior, 4)`. This is a fixed support regularizer; prior-games count is not claimed to equal the count of observed target-share rows in the rolling window.
2. **Past-season empirical rule:** estimate the next target share among eligible past rows, grouped by position, snap bin [.20,.50)/[.50,.80)/[.80,1], and prior-games bin 1/2–4/5+. Smooth each cell with 20 pseudo-observations at that position's eligible-past-row mean. If that position has no eligible past labels, use its existing positional fallback. Every fit uses seasons strictly before the evaluated season. No hyperparameter or bin search.

Evaluation seasons are 2019, 2021, 2022, 2023, 2024 and 2025; 2014 onward may supply earlier fitting rows, including 2020 when it is prior to evaluation. Both arms are read once and both are published even if adverse. The learned rule for a prospective 2026 influence trace, if nominated, fits only through 2025. It does not inspect 2026 Week1 outcomes during this diagnostic.

## Reporting and bounded nomination rule

Primary descriptive loss: mean squared target-share error over eligible observed-zero rows, paired by player/week. Report each season, position, snap bin and prior-games bin; positive-target incidence and target mass establish how often structural zero is contradicted by later historical usage. Secondary: team-normalized squared share error over **all original active receiving-position rows** with observed targets, comparing the original weights with changed weights normalized within each full team basket. This exposes displacement costs for established players. Include zero-weight team baskets and observed target mass outside the activity mask; no silent zero division or dropping a disagreeing position.

A rule can be nominated for an outcome-free full-simulator influence trace only if eligible-row loss improves in at least five of six seasons, pooled loss improves, and pooled team-normalized loss does not worsen. Report both rules independently; do not tune the loser after opening results. Any p-values, if supplied, use a family size of two; no significance claim is required or implied by this exploratory nomination screen. Changing upstream support still requires downstream calibration, independent-bank selection metrics, first-lineup/prefix/contest checks and source review before considering entered use. A success here is not permission to infer NFL score gains from target-share fit.

Local cap: one process, under five minutes, no new warehouse writes, cloud jobs or vendor requests. The full-chain repair test remains the critical path. No arbitrary floor is installed in live code.
