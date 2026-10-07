# O-40: the position-matchup (DVP) ablation -- the SCREEN disclosed and the CONFIRMATORY rule frozen (2026-10-07)

The operator (10-07): "five alarm fire ... top priority now". The outside reviewer found that the projection model has no
position-level matchup input. The laptop confirmed it: OPEN-DEFECTS O-40.

## 1. The SCREEN (already run and SEEN; it decides nothing)

The laptop ran a walk-forward ablation on today's production base and read it BEFORE any rule was frozen. The reviewer's
freeze-first note arrived while it ran.
- Script: `scripts/o40_matchup_ablation.py` (`screen` mode). Raw: `~/private/matchup/ablation-20261007.{log,csv}`.
- Arms: BASE (production `NUMERIC_FEATURES`) vs DVP4 (+ qb/rb/wr/te_fp_allowed_adj_l6) vs DEF7 (+ the three defence
  EPA / red-zone columns as well).
- Measure: every active player-week; the mean within-week × position Spearman (groups ≥ 10); MAE. Seen:

| target | DVP4 − BASE rank corr | DVP4 − BASE MAE | DEF7 − BASE rank corr | DEF7 − BASE MAE |
|---|---|---|---|---|
| 2023 | +0.0005 | −0.0018 | −0.0007 | −0.0053 |
| 2024 | +0.0021 | +0.0030 | −0.0004 | +0.0044 |
| 2025 | −0.0007 | −0.0045 | (see the csv) | +0.0037 |
| 2026 W3–W4 (descriptive) | −0.0063 | −0.0249 | −0.0101 | −0.0124 |

Reading: projection-level changes in the 3rd–4th decimal. Because it was seen, the screen cannot decide; the confirmation
below must run on UNTOUCHED seasons.

## 2. The CONFIRMATORY ablation (frozen here, before it runs)

- **The base:** the O-22-REPAIRED model (the reviewer, 10-07). The decision must be measured on the base Week 6 will run.
  `production/o22-leak-fixes-20261005` (including the as-of 0bc6b6bc) merges Monday 10-12; the four DVP columns are
  registered as CANDIDATE_FEATURES; build-features runs with the UNCHANGED leakage checks passing.
- **Arms:** BASE_R (repaired) vs DVP4_R (repaired + the four position columns) = the DECISION; DEF7_R exploratory.
- **Targets:** 2020, 2021, 2022 (untouched by the screen), each walk-forward trained on seasons before it.
- **PRIMARY:** per target season, the mean over weeks of the within-week Spearman between actual DK points and the
  projection, computed by position with the four positions weighted equally. The rows are player-weeks whose BASE_R
  projection is ≥ 5 (the same rows in both arms). The measure is DVP4_R − BASE_R.
- **PASS** requires all three:
  - (1) the difference > 0 in at least 2 of 3 target seasons (leave one season out, at most one negative);
  - (2) the pooled difference over the three seasons has a week-resampled one-sided 95% lower bound > 0 (B = 20,000,
    seed 20261040, weeks resampled within each season);
  - (3) no target season's MAE is worse by more than 1% (guard).
- **NOT PASS** otherwise. 2026 W3–W4 are printed, descriptive only.
- **What a PASS buys:** the projection-level gate only. The consumer test (the reviewer's (d): the 2026 W2–W5 fixed-book
  replay, REPAIRED vs REPAIRED + DVP4 supplies through the same union, primary P(≥ 1 big), guards declared before it
  runs) decides Week 6 with the operator.
