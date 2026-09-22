# RESULT — Targeting P(30+) directly is WORSE than targeting the mean. Negative, 0 of 8.

Result for `reports/2026-09-22-prereg-ceiling-model.md`, frozen at `6e6aef91` before any
arm was fitted. My hypothesis. It failed all three preregistered criteria, and it failed
in the same direction every season, so it is reported as a clean negative.

## Result

Walk-forward by season, 102,927 salaried rows 2014–2025, 1,807 ceiling games (1.76%),
36 features — the existing featureset, no new data.

| test season | positives | **CEIL** | **MEAN** | **SALARY** |
|---|---:|---:|---:|---:|
| 2018 | 190 | 0.8523 | **0.8792** | 0.8764 |
| 2019 | 168 | 0.8524 | 0.8734 | **0.8778** |
| 2020 | 181 | 0.8641 | **0.8765** | 0.8723 |
| 2021 | 155 | 0.8813 | 0.8913 | **0.8929** |
| 2022 | 151 | 0.9247 | **0.9391** | 0.9267 |
| 2023 | 129 | 0.9311 | **0.9401** | 0.9355 |
| 2024 | 131 | 0.9291 | **0.9390** | 0.9229 |
| 2025 | 133 | 0.9299 | **0.9368** | 0.9254 |
| **mean AUC** | | **0.8956** | **0.9094** | **0.9037** |
| **precision@100** | | 0.208 | **0.232** | 0.208 |

**Criteria, all failed:** beats both in **0 of 8** (needed ≥6); mean margin **−0.0138**
vs MEAN and **−0.0081** vs SALARY (needed ≥+0.005 each); worst season **−0.0269**
(needed > −0.01).

**Vacuity check PASSED** — Spearman(CEIL, MEAN) ranged 0.7604–0.9315, well below the
0.99 bar. The arms genuinely differ, so this is a measured loss rather than a dead lever.

## Why, most likely

Thresholding a continuous outcome throws information away. A player who scored 28 and
one who scored 4 are identical to the classifier and very different to the regressor,
and with positives at 1.76% the classifier is fitting a sparse target while the
regressor uses the full signal and is thresholded afterwards. That the loss is uniform
across all eight seasons — never a single win — is what a structural disadvantage looks
like rather than noise.

## The correction this forces on my earlier claim

I told the operator that DK salary ranks ceiling games at least as well as anything we
produce, and that we therefore had **no demonstrated ceiling edge over the price tag**.
That was based on **15** positives from the two 2026 weeks. On **1,807** positives across
twelve seasons it is **wrong**:

> **The mean model beats salary at ranking ceiling games in 6 of 8 seasons, mean AUC
> 0.9094 vs 0.9037 (+0.0057), and at precision@100 by 0.232 vs 0.208 — a 12%
> improvement on the market's own price, at a 1.76% base rate.**

We do have a ceiling edge over the price tag. It is modest, but it is real and it
replicates.

## What survives, and what this closes

**Closed:** player-level ceiling prediction as a lever. The mean model already ranks
ceiling better than a direct classifier on the same features *and* better than the
market. There is no cheap win here, and I would not spend more on this target without a
new feature source rather than a new loss function.

**Still open and unchanged:** the ceiling columns genuinely do not reach the money path.
`scripts/live_week.py` selects **only `proj_points`** from `player_projections` —
`proj_p90`, `proj_std`, `proj_p50` and `p_20_plus` are never pulled. (They *are* read by
`nfl2/anchor.py` for the frozen PREREG-028 anchor rule, which is not in the live path;
my earlier "never reaches construction" was right for the money path and should have
said so precisely.) Whether construction can use a ceiling column it currently cannot
see is untested — but this result lowers the prior, since `proj_p90` is a monotone
transform of much the same signal that `proj_points` already carries.

**Where this redirects.** If marginal ceiling ranking is near its limit on these
features, the remaining gap to a 274 lineup is in the **joint** distribution — five
players at 30+ *together* — which is the dependence model, not the marginals. That is
consistent with the regime flip, since a mis-specified dependence model would produce
exactly the unstable tail ranking measured. It is not a recommendation: the ledger
already records TD-coupling, Schaake and hierarchical-Gumbel dependence arms as
rejected, so any new attempt needs a reason the earlier ones did not have.
