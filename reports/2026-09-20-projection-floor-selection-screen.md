# Projection-floor evidence reproduction and selection-only screen

Run date: 2026-09-20. This is a retrospective historical screen on the frozen panel `20260811-pitclean-e80-k1-role12union-a12ab31`; it does not change the live book or authorize a policy. The script decoded only persisted simulated clear masks, `p_line`, and `sim_mean` to select, then read historical `actual_score` values for evaluation. No current-week table was queried.

## Independent reproduction

The standalone BigQuery reader and local join reproduced the proposal exactly: 27,051 candidates, 50,418 player snapshots, 243,459 roster-player joins, 107 slates, and 8,560 persisted selections with zero missing joins. The weakest-player bucket counts, means, tail rates, winner counts, top-10 rates, and selection shares match the workstation table after rounding. The weakest-player salary/projection/actual table also matches after rounding:

| bucket | lineups | weakest salary | weakest proj | weakest actual | P(actual >=10/15/20) | P(actual <=2) |
|---|---:|---:|---:|---:|---|---:|
| min < 6 | 420 | 3867.4 | 4.6 | 3.0 | 0.10/0.04/0.02 | 0.66 |
| min 6-8 | 1091 | 4085.8 | 7.1 | 5.3 | 0.20/0.09/0.04 | 0.45 |
| min 8-10 | 2516 | 4279.9 | 9.1 | 7.6 | 0.29/0.14/0.08 | 0.28 |
| min 10-12 | 3782 | 4127.5 | 11.1 | 7.5 | 0.28/0.15/0.08 | 0.28 |
| all >= 12 | 19242 | 4411.8 | 14.5 | 8.9 | 0.38/0.21/0.11 | 0.25 |

Evidence: [reproduction result](reviews/evidence/2026-09-20-projection-floor-reproduction-result.json), [reproduction script](../../scripts/reproduce_projection_floor_evidence.py).

## Historical selection-only screen

I filtered the frozen candidate pool by the lowest served non-DST `proj` in each nine-player roster, then reran the exact persisted production selector (`select_from_support`) at 80 entries and a 194-point clear line. The control reproduced the persisted selection set and order on all 107 slates (zero set and order mismatches).

| arm | feasible slates | candidates/slate mean (min) | selected max mean | P(selected max >=187/194/200/210/220/230/240) counts | pool-oracle counts at 200/220/240 | control overlap |
|---|---:|---:|---:|---|---|---:|
| control | 107/107 | 252.8 (235) | 177.76 | 38/24/13/5/3/2/2 | 16/3/2 | — |
| floor8 | 107/107 | 238.7 (121) | 177.57 | 38/24/14/5/3/2/1 | 16/3/1 | 69.1/80 |
| floor10 | 106/107 | 215.2 (21) | 175.75 | 36/23/13/5/2/2/1 | 15/2/1 | 51.3/80 |
| floor12 | 106/107 | 179.8 (2) | 169.67 | 26/16/8/3/0/0/0 | 10/0/0 | 32.1/80 |

### Paired slate differences

Intervals below are percentile intervals from 10,000 slate-cluster bootstrap resamples. A floor arm is compared with control only on slates where it can still produce 80 rows; infeasibility is reported separately.

| arm | common slates | selected-max mean delta (95% CI) | 200-clear delta | 220-clear delta | 240-clear delta | oracle-200 delta |
|---|---:|---:|---:|---:|---:|---:|
| floor8 | 107 | -0.188 [-1.017, +0.562] | +0.009 [+0.000, +0.028] | +0.000 [+0.000, +0.000] | -0.009 [-0.028, +0.000] | +0.000 [+0.000, +0.000] |
| floor10 | 106 | -2.065 [-3.625, -0.631] | +0.000 [-0.028, +0.028] | -0.009 [-0.028, +0.000] | -0.009 [-0.028, +0.000] | -0.009 [-0.028, +0.000] |
| floor12 | 106 | -8.138 [-10.845, -5.578] | -0.047 [-0.094, +0.000] | -0.028 [-0.066, +0.000] | -0.019 [-0.047, +0.000] | -0.057 [-0.104, -0.019] |

## Interpretation

- A served-mean floor of 8 is feasible on all 107 historical slates, retains 69.1 of 80 control rows on average, ties the control at 194 and 220, gains one 200-clear, and loses one 240-clear. Its selected-max mean is slightly lower; the result is not a promotion signal.
- A floor of 10 is infeasible on one slate and loses high-tail support in this screen. A floor of 12 is also infeasible on one slate, removes all historical 220+ pool-oracle opportunities, and is clearly unsuitable as a live rule.
- The screen is useful because it isolates a selection mechanism and exactly reconstructs the incumbent selector, but it is still outcome-informed historical evidence with only 107 slate clusters. The correct next step remains the pre-registered Week-3 prospective control/floor-8/floor-10 shadow, with floor 12 kept as a feasibility falsifier only.
- Do not add a p90 floor or alter generation in this experiment. A generation floor would change the corpus and needs a separate arm.

Evidence: [selection result](reviews/evidence/2026-09-20-projection-floor-selection-screen-result.json), [selection script](../../scripts/reproduce_projection_floor_selection_screen.py).
