# Archived D12800 PREREG-016 selector screen

This is an outcome-blind **in-sample mechanism screen** on the archived
D12800 candidate pool. It reuses the two 10,000-world banks that produced the
archived `dual_emax` book, so it is useful for diagnosing the selector's
behavior but is not a prospective estimate and does not authorize a live
change. The archive predates the Sunday final-status replacement pass; its
candidate pool and raw control therefore are not the current uploaded book.

## Frozen comparison

The control is the archived 97-row `dual_emax` book. The treatment is the
existing PREREG-016 `cap_prefix_then_fill` law: inclusive rungs 194/200/210/220,
weights 1/2/6/12, mean tie-break, pairwise roster-overlap cap gamma 4 during
the prefix, then unconstrained ladder fill. An uncapped `greedy_ladder` arm
isolates the cap's effect. All three arms use the same 12,555 candidates and
the same equal-mass pooled incumbent/corrected-HSIM worlds.

The reader uses explicit identity and candidate columns only; no `actual`
column, provider, or current-week outcome was read. The exact result is
`reports/reviews/evidence/2026-09-20-d12800-prereg016-archive-screen-result.json`
and the reader is beside it.

## Pooled simulated result

| arm | max mean | P194 | P200 | P210 | P220 | P230 | P240 | row mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dual_emax control | 203.451 | 64.595% | 54.120% | 36.250% | 22.255% | 12.120% | 6.280% | 137.183 |
| uncapped ladder | 203.094 | 63.765% | 53.485% | 36.595% | 23.025% | 12.140% | 6.155% | 137.604 |
| cap-4 ladder | 202.559 | 63.020% | 52.660% | 35.430% | 21.675% | 11.210% | 5.500% | 136.308 |

Relative to `dual_emax`, the uncapped ladder trades **−0.357** max-mean
points for **+0.770 P220 points**, with nearly flat P230 (+0.020 pp) and
slightly lower P240 (−0.125 pp). Adding the gamma-4 cap then loses another
**0.535** max-mean points, **1.350 P220 points**, **0.930 P230 points**, and
**0.655 P240 points** relative to the uncapped ladder. Against the control,
the cap-4 arm is lower on every listed max metric: −0.891 mean-max, −0.580
P220 points, −0.910 P230 points, and −0.780 P240 points.

The cap is active in the selection path even though it reaches all 97 slots:
the cap-4 and uncapped ladder orders differ at 86 positions and share only
50 of 97 members. Prefix length alone is not a valid cap-engagement measure.

## Reading

On this current-week simulated pool, `dual_emax` remains the strongest of the
three by mean-max and by the 230+/240+ portfolio tails. The uncapped ladder
does expose a possible 220+ tradeoff, but it is a same-bank, in-sample signal;
the gamma-4 cap makes that tradeoff worse here. This is consistent with the
lab's earlier finding that hard overlap caps can be population-dependent or
negative.

This result does not close the Week-3 question. The requested 220/230/240
ladder variant still needs its own declared weights and cap before a fresh
paired shadow. The decision-bearing experiment is the outcome-blind,
prelocked `dual_emax` versus frozen `cap_prefix_then_fill` shadow scored on
realized max-of-K and 200+/210+ clears, with simulated metrics and the
simulated-to-realized 220 ratio reported alongside it. No production selector
or current entry was changed from this screen.

Result SHA-256:
`321e667e93a1a8b612015abbeaf24b7ff7e98e135b40f4f53fa74bc6a857b9ef`.
