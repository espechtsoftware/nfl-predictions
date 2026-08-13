# Incumbent tail-mask support audit

Date: 2026-08-13. Outcome-free diagnostic frozen from the accepted panel
`20260812-pitclean-e80-selected-tabpfn-active-v2` before any seed-envelope
replicate was run.

## Population and method

- Source: promoted `nfl_predictions.replay_candidates` rows for seasons
  2023--2025.
- Population: 54 slates, 13,750 candidates, 4,320 selected entries, and
  10,000 worlds per candidate.
- Support counts are `BIT_COUNT(FROM_HEX(clear_bits_T))`. The stored masks are
  hexadecimal strings, not base64. Using `FROM_BASE64` would produce invalid
  counts and is explicitly prohibited.
- No realized score, player outcome, arm comparison, or lineup score was used
  to compute this report.

## Measurements

| cohort | rows | mean >=187 | mean >=194 | mean >=200 | mean >=210 | mean >=220 | zero >=220 | max >=210 | max >=220 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selected | 4,320 | 32.0410 | 15.3412 | 7.3750 | 2.1958 | 0.7806 | 1,825 (42.25%) | 16 | 6 |
| unselected | 9,430 | 24.0052 | 10.2618 | 4.9729 | 1.3453 | 0.3610 | 6,664 (70.67%) | 16 | 5 |
| all | 13,750 | — | — | — | 1.6125 | 0.4928 | 8,489 (61.74%) | 16 | 6 |

Every candidate has fewer than 30 supporting worlds at both 210 and 220.
Among selected candidates, the fractions below 30 are 52.04% at 187, 91.99%
at 194, 99.70% at 200, and 100% at 210 and 220.

Overall support deciles are:

- 210: `[0,0,0,1,1,1,2,2,3,4,16]`;
- 220: `[0,0,0,0,0,0,0,1,1,1,6]`.

Selected support deciles are:

- 210: `[0,0,1,1,1,2,2,3,3,5,16]`;
- 220: `[0,0,0,0,0,1,1,1,1,2,6]`.

At 10,000 worlds the selected candidates' empirical standard-error scale is
approximately `sqrt(k)/10000` for such rare events. A one-world 220 mask is
therefore not a precise estimate of a candidate's true tail probability, and
small changes in worlds can alter lexicographic ordering.

## Interpretation

This is strong evidence that the frozen prospective 220→210→200 selector is
ranking on extremely sparse masks. It is not evidence that a lower threshold
will score better, and it does not invalidate the adopted 194 portfolio. The
194 selector uses union coverage across roughly 250 candidates and already has
paired historical evidence; nevertheless, the audit corrects the claim that
its individual masks are intrinsically high-support.

The live prospective shadow uses 30,000 worlds. If the measured probabilities
carried over unchanged, selected mean support at 220 would rise only from 0.78
to about 2.34 worlds. That scaling is illustrative because the live pool is a
different snapshot; it is still too sparse to assume seed-stable ranking.

## Consequence

Keep the 220-first book shadow-only. Before treating live performance as a
test of the selector idea, measure at least two things without changing its
frozen rule:

1. pairwise selected-roster overlap and mask-support distribution across the
   preregistered incumbent seed replicas; and
2. on a small frozen slate sample, 30,000-world support versus a larger
   ordinary-world reference using identical candidate rosters.

If the 220-first top-80 is unstable, prefer additional ordinary worlds as the
first benchmark. A stratified estimator may proceed only after exact weighted
joint-law validation; this audit alone does not license it.

## Reproducible query

```sql
WITH c AS (
  SELECT
    selected,
    BIT_COUNT(FROM_HEX(clear_bits_187)) AS s187,
    BIT_COUNT(FROM_HEX(clear_bits_194)) AS s194,
    BIT_COUNT(FROM_HEX(clear_bits_200)) AS s200,
    BIT_COUNT(FROM_HEX(clear_bits_210)) AS s210,
    BIT_COUNT(FROM_HEX(clear_bits_220)) AS s220
  FROM `nfl-predictions-503414.nfl_predictions.replay_candidates`
  WHERE panel_run_id = '20260812-pitclean-e80-selected-tabpfn-active-v2'
    AND season BETWEEN 2023 AND 2025
)
SELECT IF(selected, 'selected', 'unselected') AS cohort,
       COUNT(*) AS n,
       AVG(s187), AVG(s194), AVG(s200), AVG(s210), AVG(s220),
       COUNTIF(s187 < 30), COUNTIF(s194 < 30), COUNTIF(s200 < 30),
       COUNTIF(s210 < 30), COUNTIF(s220 < 30), COUNTIF(s220 = 0),
       MAX(s210), MAX(s220)
FROM c
GROUP BY cohort;
```

