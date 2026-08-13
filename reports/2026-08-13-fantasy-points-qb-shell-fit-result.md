# Fantasy Points same-season QB shell-fit result

Date: 2026-08-13. The sole frozen diagnostic execution
`fantasy-points-qb-shell-pgnfj` completed cleanly from source commit `62d4eb0`
and immutable image digest
`sha256:9aa494e18c6dd2fbd855a200dc5101208f63eeb3279af595fb0430d6e0770ad5`.
The full validation build `c42bb2a2-727a-4880-83ca-8fa0f0da99d1` passed
1,094 tests with 2 skipped before the diagnostic launched.

## Disposition

**`fp-qb-shell-player-tail-fails`**. The mechanism cleared its coverage gate
but worsened the registered aggregate 30-point Brier loss. It does not proceed
to candidate generation, lineup scoring, or an exact-80 comparison.

## Identity and point-in-time support

- Offense source:
  `20260813T141434Z__same-season-qb-shell-fit-last-four-v1`
- Defense source:
  `20260811T053208Z__same-season-coverage-last-four-v1`
- Source table: 1,792 rows, 56 target windows, 32 teams
- Evaluation panel: `20260810-lockfix-e80-k1-8677d21`
- Target weeks: 5--18; every source window ends at target week minus one
- Held-out folds: 2023, 2024 and 2025
- Base QB rows: 3,884; supported QB rows across the full construction: 3,830
- Held-out supported rows scored: 2,918
- Coverage: 2023 `100.00%`, 2024 `99.30%`, 2025 `99.39%`

Thus the failure is not attributable to the frozen 70% support floor.

## Registered and diagnostic metrics

| Metric | Control | Treatment | Treatment minus control |
|---|---:|---:|---:|
| Aggregate 30-point Brier | 0.018710730 | 0.018717604 | +0.000006874 |
| Aggregate 20-point Brier | 0.066310479 | 0.066446932 | +0.000136452 |
| Aggregate residual MAE | 3.400413904 | 3.405619489 | +0.005205585 |

Lower is better for all three. The 30-point fold deltas were approximately
`-0.000043705` in 2023, `+0.000011914` in 2024 and `+0.000050327` in 2025.
One improving fold therefore did not offset deterioration in the other two.

The two descriptive features also lacked a stable held-out relationship with
the target. Their point-biserial 30-point correlations ranged from about
`-0.0715` to `+0.0335`, and each feature's sign changed across seasons.
Projection-residual Spearman correlations were all between approximately
`-0.0328` and `+0.0218`.

## Consequence

Close this exact last-four, team-level Man/Zone plus one-high/two-high QB
shell-fit mechanism. Do not tune its window, support threshold, included
shells, grade formula, control, estimator, or gate on this observed result.

This does not invalidate the vendor's prospective QB/WR matchup tools or the
separately scoped player-alignment/conditional receiver-allocation lead; those
are different data and mechanisms. No lineup score was read, and the active
production/scoring baseline remains unchanged.
