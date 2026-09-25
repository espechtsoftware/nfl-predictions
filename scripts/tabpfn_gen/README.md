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

- **Measured calibration** (2025 walk-forward predictions, skill players; laptop, 2026-09-25):

| 2025 | n | actual ≤ q10 | ≤ q50 | ≤ q90 | mean q10 / q50 |
|---|---:|---:|---:|---:|---|
| played, QB | 647 | 0.165 | 0.502 | 0.906 | 6.52 / 13.99 |
| played, RB | 1,591 | 0.197 | 0.498 | 0.904 | 1.63 / 5.91 |
| played, TE | 1,275 | 0.231 | 0.490 | 0.910 | 0.77 / 4.33 |
| played, WR | 2,420 | 0.259 | 0.527 | 0.898 | 1.35 / 5.49 |
| did not play (all) | 6,912 | 1.000 | 1.000 | 1.000 | ≈ 0.1 / ≈ 0.6 |

- **Reading:**
  - Median and q90 are calibrated for players who played.
  - The **lower tail is too light, not too heavy**: actual falls below q10 16–26% of the time, against 10%.
  - TabPFN already puts near-zero quantiles on players who will not play, so its features separate inactivity.

  The feared double count of zero mass in the lower quantiles is **not visible** here. A `was_active` context filter
  would remove the zero rows and probably raise q10 further, making lower-tail calibration *worse* for players who play.
- **Status: repair pending, and re-scoped.** Before any context change, compare the current and filtered contexts on this
  same PIT table (played players, by position, plus the same for Questionable players, where availability and shape
  overlap). The operator decides; production owns the job (`tabpfn-gen`, env-gated, no new job).
