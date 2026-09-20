# Served-p90 projection-floor selection diagnostic

Run date: 2026-09-20. This is a retrospective diagnostic on the frozen 107-slate panel. It uses the same persisted 194-point masks and exact selector as the mean-floor screen, replacing only the weakest-player signal with served `proj_p90`. It reads historical labels after selection and does not change the live book.

## Results

| arm | feasible | candidates/slate mean (min) | selected max mean | selected max clears 187/194/200/210/220/230/240 | pool oracle 200/220/240 | overlap |
|---|---:|---:|---:|---|---|---:|
| control | 107/107 | 252.8 (235) | 177.76 | 38/24/13/5/3/2/2 | 16/3/2 | — |
| floor8 | 107/107 | 248.1 (135) | 177.55 | 38/24/13/5/3/2/1 | 16/3/1 | 76.7/80 |
| floor10 | 106/107 | 240.7 (38) | 177.63 | 38/25/13/5/3/2/1 | 16/3/1 | 73.7/80 |
| floor12 | 106/107 | 217.9 (11) | 176.42 | 35/22/12/4/2/2/1 | 14/2/1 | 64.6/80 |

## Paired slate differences

Intervals are 10,000 slate-cluster bootstrap resamples. Infeasible slates are excluded from the paired score comparison and reported in the table above.

| arm | common feasible slates | selected-max mean delta (95% CI) | 200-clear delta | 220-clear delta | 240-clear delta | oracle-200 delta |
|---|---:|---:|---:|---:|---:|---:|
| floor8 | 107 | -0.210 [-0.487, +0.032] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | -0.009 [-0.028, +0.000] | +0.000 [+0.000, +0.000] |
| floor10 | 106 | -0.184 [-0.598, +0.176] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | -0.009 [-0.028, +0.000] | +0.000 [+0.000, +0.000] |
| floor12 | 106 | -1.393 [-3.035, -0.080] | -0.009 [-0.047, +0.019] | -0.009 [-0.028, +0.000] | -0.009 [-0.028, +0.000] | -0.019 [-0.047, +0.000] |

## Reading

- A p90 floor of 12 is materially less destructive than a mean floor of 12: it retains 2 historical 220+ and 230+ pool-oracle slates among the feasible slates. It still has one infeasible slate, loses the control at the selected 210/220/240 counts, and has a negative selected-max mean.
- Floors of 8 and 10 are nearly the control in this historical screen. Floor 8 is feasible everywhere and preserves 220/230, but loses one 240 clear. Floor 10 is infeasible on one slate, ties the control at 220/230, and loses one 240 clear.
- This does not justify adding a p90 floor to the Week-3 first shadow: the p90 signal is a different policy lever and remains outcome-informed here. If the mean-floor shadow is informative, the p90 threshold can be registered as a later separate arm without changing the generator or p90 punt valuation.

Evidence: [result JSON](reviews/evidence/2026-09-20-projection-p90-selection-screen-result.json), [reader](../../scripts/reproduce_projection_p90_selection_screen.py).
