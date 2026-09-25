# `tabpfn_gen`: walk-forward TabPFN dk-points quantiles

`gen.py` fits TabPFN walk-forward (season S from seasons < S) on `nfl_features.player_week_training` and writes the mean
and the quantiles q01…q99 per (season, week, gsis_id) to `nfl_features.tabpfn_projections`. `--upcoming` / `TABPFN_UPCOMING`
predicts the target week from all labelled history. The lab reads this cache to shape its marginals.

## The estimand (integrity item 5.8, 2026-09-25)
- **Intended: conditional on playing** (production `343cdc86`). The 08-06 universe repair separated listed-inactive rows
  from active model-fitting rows through `was_active`. The mean model filters on it, and availability is modelled
  separately (Q haircut, cascade, inactives).
- **Current: unconditional.** The context is every labelled row (`context_law = all-prior-nonnull-labels`, `gen.py:195`,
  `:281`). It records `active_rows` / `inactive_rows` (`:331-332`) but does not filter on them. Since the 2022 panel break,
  most context rows are inactive zeros:

| seasons | labels per season | rows with no box-score line (all labelled 0) |
|---|---|---|
| 2014–2021 | 6.2k–6.9k | 12–15% |
| 2022–2026 | 12.8k–13.2k (1.6k in 2026 so far) | 54–56% |

- **Zero-mass calibration (the right check; production `d3cc4cb6`):** for 2025 RB/WR/TE players with a box score, the
  forecast P(0) lower bound (the highest quantile level ≤ 0.05) against the realized share of zeros:

| forecast P(0) ≥ | 0 | 0.01 | 0.05 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 |
|---|---|---|---|---|---|---|---|---|
| realized zeros | 0.006 | 0.017 | 0.071 | 0.119 | 0.203 | 0.295 | 0.458 | 0.652 |

  Calibrated within each bucket's interval. The median and q90 are calibrated as well: actual ≤ q50 in 49–53%, above q90 in
  9–12%.
- **A correction.** The laptop's first read ("actual ≤ q10 in 16–26%, lower tail too light") and production's ("< q10 in
  5–6%, too heavy") were both **artifacts of the point mass at 0**. q10 is exactly 0 for 48–62% of 2025 RB/TE/WR rows, and
  15–23% of players who played scored exactly 0, so "≤" and "<" land on opposite sides of the ties. Neither read is
  evidence about the tail.
- **Status: closed; no repair.** The intended estimand is conditional; the context is unconditional; zero-mass calibration
  for players who play is fine (the table above). A `was_active` filter is not warranted: TabPFN's features separate
  inactivity.
