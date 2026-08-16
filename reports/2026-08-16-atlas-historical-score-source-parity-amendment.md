# ATLAS historical score source-parity amendment

Date frozen: 2026-08-16, before any repaired matched-diversity season output
was opened or reached the downstream realized-score runner

Amends:
`reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md`

Scope: mechanical source row count and floating-point parity criterion only

## Correction

The protocol's statement that the immutable native source contains 72,520
candidate rows is incorrect. The exact query used by the upstream ATLAS MVP,
including the 2025 Week 1 R3 repair substitution, contains **68,199** rows.
This is independently fixed by two immutable sources:

- the 270 source-artifact receipts in
  `20260815-atlas-current-money-transfer-v1/report.json` sum to 68,199
  candidate rows; and
- the exact five-panel plus repair-substitution BigQuery query returns 68,199
  unique `(panel_run_id, season, week, cand_ix)` rows and no duplicates.

The scorer must therefore require exactly 68,199 registered source rows, not
72,520. It may not add a panel, duplicate a candidate, restore the superseded
R3 source, or omit any row to reach another count.

Both `slate_player_features.actual` and
`replay_candidates_staging.actual_score` are BigQuery `FLOAT` columns.
Re-summing nine player floats reproduces every registered candidate score to
machine precision, but different floating-point association produces a raw
maximum absolute difference of `5.684341886080802e-14` (99th percentile
`2.842170943040401e-14`), not bitwise zero. The scorer must report the raw
maximum and require all 68,199 differences to be at most `1e-9` with zero
relative tolerance. Missing players, malformed rosters, non-finite values, or
a larger difference remain mechanical invalidity.

## Consequence

This amendment changes no roster identity, selected lineup, realized point
value, threshold, signal rule, score-free disposition, or production
consequence. It only makes the frozen parity assertion match the exact
upstream source population and the declared `FLOAT` storage types.
