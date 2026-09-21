# `served50_p90_50` measured: it is a punt-shifting transform, not a belief perturbation

Against `research/exploration-sleeve-20260921` @ `41c104c3`
(`src/nfl2/forecast_views.py`). Measured on the last Week-2 pre-lock batch,
`nfl_predictions.player_projections`, the same 412-row population the proper
scoring used.

## First, a correction to what we told you

We said view 4 "will inflate QB hardest, which is the position whose upper tail
we have the most evidence is too wide." **That is backwards.** QB is inflated
*least*:

| pos | n | served mean | p90 mean | view mean | **lift** |
|---|---|---|---|---|---|
| RB | 107 | 6.14 | 15.70 | 10.92 | **+77.9%** |
| TE | 108 | 3.61 | 9.19 | 6.40 | **+77.1%** |
| WR | 166 | 6.18 | 15.14 | 10.66 | **+72.4%** |
| QB | 31 | 17.80 | 36.79 | 27.30 | **+53.3%** |

The driver is not position, it is **relative variance**. Positions with low
means (TE 3.61, RB 6.14) lift most; QB has the highest mean, so it lifts least.
Our QB-calibration point was real but we attached it to the wrong mechanism.

## The actual mechanism

`proj_p90` is essentially a fixed-z offset from the mean: over 444 rows the
implied `z = (p90 - mean) / sd` averages **1.50** (sd 0.20). So

```
view = 0.5*served + 0.5*p90  ≈  served * (1 + 0.75 * CV)      CV = sd / mean
```

The lift is **proportional to the coefficient of variation**, and mean CV on
this batch is **1.92**. That makes the view a CV-weighted rescale, not a
uniform "more upper tail" shift.

## What that does to the ordering

Lift by served-projection bucket, monotone across all five:

| served projection | n | mean | **lift** |
|---|---|---|---|
| under 5 | 215 | 1.70 | **+151.7%** |
| 5–10 | 91 | 7.53 | +65.2% |
| 10–15 | 60 | 12.22 | +58.1% |
| 15–20 | 34 | 17.11 | +51.5% |
| 20+ | 12 | 21.55 | **+47.0%** |

A sub-5 player's projection **more than doubles** (1.70 → 4.28) while a 20+
player gains 47%. The view systematically compresses the projection ordering
toward cheap, low-projection, high-variance players.

## Why this matters for your readout

**Any coverage change this view produces is confounded with a punt shift.** The
optimizer maximises projected points under a salary cap; handing it a transform
that roughly doubles sub-5 players and adds 47% to the top will move
construction toward punts regardless of whether alternative beliefs help. You
would measure "the view changed coverage" and not be able to attribute it.

That direction is also not neutral on the existing evidence: sub-8 punts
measured dead in Week 1, while 8–12 punts raised tails. This view's largest
effect is exactly on the sub-5 band.

## Suggestions, in preference order

1. **Mean-preserving normalisation.** Rescale each view so its total (or
   per-position mean) projected points equal `served`. Then only the *relative*
   reweighting is tested, which is the belief question you are actually asking,
   and the punt shift disappears as a level effect.
2. **If you keep it as-is, rename it.** It is a punt-heavier construction arm,
   not an upper-tail belief arm. Naming it accurately stops the readout being
   over-read later — the same discipline as the lever-record rule.
3. **Either way, record per-view per-position mean projection and the sub-5
   share of selected rows** in the receipt. Those two numbers make the
   confound visible instead of invisible.

`served70_mean25_30` is not affected this way — `mean25` is a location estimate,
so that view is a genuine belief perturbation. The issue is specific to blending
a dispersion quantile into a location input.

## One thing your implementation already gets right

`p90 = raw_p90.fillna(served)` with an explicit missingness count, rather than a
silent substitution, is the correct handling and matches the operator's
no-silent-fallbacks rule.
