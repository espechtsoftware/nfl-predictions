# The defect is calibration, not dependence — and the regime flip now has a mechanism

Operator asked to proceed with the dependence direction. The first step was to find the
reason the three rejected dependence arms lacked. That reason exists, the diagnostic it
licensed was run — and it says **the dependence hypothesis is not supported.** The defect
is in the simulator's level and scale, and it is both larger and more tractable.

## The reason the earlier arms lacked

Schaake (within-game rank templates on calibrated marginals), parametric TD coupling and
hierarchical Gumbel were all **generation-side** and all judged on variogram, tail-Brier
or replay-panel metrics computed against **our own simulator**. None had external ground
truth for what lineup scores actually look like. `nfl_raw.contest_entries` was first
loaded **2026-09-14** ("first entry-level field ever loaded"); those arms are all from
August. We now hold **1.3M real lineups with realized scores** that did not exist then.

## The diagnostic: PIT on real outcomes

A lineup score is the sum of nine dependent player outcomes, so the lineup-total
distribution is the joint's signature. For each candidate, the quantile of its own
simulated distribution that its realized score landed in. Calibrated → uniform.

| | simulated mean | realized mean | mean PIT |
|---|---:|---:|---:|
| Week 1 | 121.37 | **141.06** | 0.710 (sim runs LOW) |
| Week 2 | 125.70 | **93.67** | 0.203 (sim runs HIGH) |

**The simulator predicts ~123 every week while reality swings 94 → 141.** Its absolute
tail probabilities are consequently meaningless in both directions:

| P(score ≥ 194) | simulated | realized | error |
|---|---:|---:|---:|
| Week 1 | 0.588% | 3.250% | 5.5× **under** |
| Week 2 | 1.171% | 0.008% | 146× **over** |

*(A note on my own instrument: the script's "under-disperses" verdict line is wrong — a
mean PIT of 0.71/0.20 is a **shift**, and the heuristic conflated shift with dispersion.
The decile tables below are the honest read.)*

## The error is COMPOSITIONAL — and that is the regime flip

A uniform level shift is harmless to expected-max selection: it moves every lineup
equally. This is not uniform. Bias by decile of the simulator's **own** prediction:

| decile of sim_mean | W1 sim → realized | W1 bias | W2 sim → realized | W2 bias |
|---:|---|---:|---|---:|
| 1 | 109.98 → 130.02 | +20.04 | 112.64 → 105.05 | −7.58 |
| 5 | 120.58 → 134.89 | +14.31 | 124.88 → 97.30 | −27.58 |
| 10 | 132.67 → 165.74 | **+33.07** | 137.82 → 79.57 | **−58.25** |
| **spread** | | **+13.03** | | **−50.67** |
| **corr(sim_mean, error)** | | **+0.138** | | **−0.554** |

**The lineups the simulator likes most are the ones it misprices most, and the sign
flips between weeks.** In Week 1 its favourites were under-projected (ranking preserved,
even enhanced); in Week 2 over-projected by 58 points against 8 for its least-favourites
(ranking inverted). That is precisely the measured `corr(sim_mean, realized)` of +0.28
and −0.33, now with a mechanism rather than an observation.

It also explains what survived and what did not: **expected-max is threshold-free**, so a
level error moves every candidate together and it degrades gracefully. Every
threshold-keyed objective inherits the full error — which is why the cash objective
claimed 56.9% and delivered 0 of 97.

Week 1's ratios are near-constant (1.18–1.25), i.e. roughly multiplicative. Week 2's are
not (0.93 → 0.58), so Week 2 carries something beyond scaling — consistent with its known
high-projection busts (Bijan at 37.2% exposure, 21.7 → 11.1; Jefferson 25.3 → 8.5).

## The environment is predictable, and we already hold the inputs

Slate scoring environment across **209 historical slates** (2014–2025), mean DK points
per salaried player: mean 6.06, sd 1.85, range 2.8–9.0 — a 30% coefficient of variation
the simulator does not track.

| pre-lock predictor | corr with environment | Spearman |
|---|---:|---:|
| mean `dk_points_l4` | **0.762** | 0.770 |
| mean `salary` | 0.639 | 0.602 |
| mean `implied_team_total` | 0.576 | 0.595 |
| mean `game_total` | 0.562 | 0.581 |

Walk-forward one-step-ahead MAE over **157 slates**:

| | MAE |
|---|---:|
| constant — predict the historical mean (≈ what the simulator does) | 1.540 |
| OLS on pre-lock predictors | **0.869** |
| | **−43.6%** |

All four predictors are **already in the feature set**. This is unused information, not
missing information.

## What I would and would not claim

**Would:** the simulator's calibration is a measured, mechanistically-understood defect
with quantified headroom, and it is the first explanation offered for the regime flip
rather than another description of it. It is better founded than the dependence arms
because it rests on external ground truth they did not have.

**Would not:** claim the fix is easy or that it lands this week. A slate-level
environment correction addresses the *level*; the compositional part is what distorts
ranking, and correcting that needs a recalibration map fitted on lineup-level
simulated-versus-realized pairs. **We hold two weeks of those.** The replay corpus could
supply more, but that is a build, and its candidates are quarantined research data.

**Explicitly not proposed:** any change to the Week-3 money path. This is a research
finding; the Sunday path is unchanged.


---

## RETRACTION (same day): the environment is NOT predictable — the 43.6% was an artifact

The "−43.6% MAE, environment is predictable" result above is **withdrawn**. The training
panel's inactive share jumps from **0.3% to 46.6% in 2022**, when listed-inactive players
were added with zero labels. The environment was measured over all rows, so the walk-forward
fit was learning that data break; against the honest baseline — a **same-era** trailing
mean — it is **163% worse**, not 43.6% better (`env_robust.py`).

Measured properly:

| environment | CV across slates | OLS gain over same-era mean |
|---|---:|---:|
| mean DK points, **active** players | **7.7%** (not 30%) | +4.5% (+7.0% with an era dummy) |
| **top-50 active** players — what lineups sample | **7.2%** | **+0.5%** |

**The top-end scoring environment is not forecastable from pre-lock Vegas totals, recent
form or salary.** So the regime flip cannot be converted into a covariate by this route, and
the laptop's observation that it could — which rested on this number — does not survive.
The PIT and compositional-bias findings are unaffected; only the forecastability claim falls.
Practical consequence for Week 3: no environment-conditioned rule; keep the threshold-free
expected-max selector.

## Addendum 2 (2026-09-22, late) — the compositional finding is also withdrawn

The external review (`review/external-suggestions-20260922`, Finding A) showed the Week-2
compositional error is the availability defects, not the simulator. Production reproduced its
incumbent-bank numbers exactly with an independent mean-shift script:

| Week 2, incumbent bank | raw | 31 non-players zeroed | + 4 DK-PPG stand-ins restored |
|---|---:|---:|---:|
| simulated pool mean (realized 93.7) | 125.0 | 114.1 | 109.9 |
| corr(sim mean, error) | −0.690 | −0.280 | **−0.087** |
| corr(sim mean, realized) | −0.488 | +0.152 | **+0.340** |
| top − bottom decile error | −67.7 | −29.1 | **−7.3** |

"Non-players" are skill players projected ≥ 5 with no `weekly_stats` row (backup QBs, Tua,
Flowers, Bowers, Pittman, …); the stand-ins are Jefferson 25.3→17.3, Flowers 22.6→14.7,
McConkey 17.2→14.8, Bech 9.4→7.1. Both defects are fixed in the Week-3 path.

Week 1 against its own worlds: corr(sim mean, error) +0.201 sits at world-rank 0.685
(incumbent) / 0.500 (hsim) — ordinary. Its realized pool mean 141.1 sits at world-rank 0.983 /
0.948; Week 2's is at 0.0003 raw (≈0.05 after the corrections, per the review).

**What stands:** a slate-wide scoring LEVEL the simulator under-disperses (two slates at
opposite ends of its world range). Expected-max and field-relative objectives are nearly
immune to it; absolute thresholds (cash line, P(≥194)) are not. **What falls:** "error is
compositional", "the simulator's ranking flips between weeks", and any recommendation to
recalibrate composition from Week 2. Week-2 post-mortem lever reads (caps, fade A/B, cash
objective, sort-key correlation) were measured on a defect-dominated book and are not
evidence of a regime.
