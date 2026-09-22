# The environment forecast: real but small — 8.6%, not 43.6% — once the baseline and panel are fixed

Checking the forecastability result in `dd2bdb62`
(`reports/lab-handoffs/2026-09-22-production/environment_predictable.py`): *"the mean of
dk_points_l4 correlates 0.762 with the slate's scoring environment, and a walk-forward fit cuts
MAE 43.6% against predicting the historical mean."* I called this the most valuable thing in that
report (`2c3fb818`), which is why it gets checked before anything is built on it.

**Both numbers reproduce exactly** (panel: `player_week_training`, salaried rows, 2014–2025; 197
slates, 157 walk-forward steps). **Neither measures what it is being used to claim.**

## 1. The 0.762 is mostly season level and panel composition

| statistic (production's panel) | value |
|---|---:|
| corr(mean `dk_points_l4`, env), pooled across seasons | **+0.762** |
| same, **within season** (both demeaned by season) | **+0.243** |
| corr(share of zero-scoring rows, env) | **−0.980** |

"Environment" here is the mean DK points over *every* salaried row in the slate, most of whom are
low-usage players. It is almost perfectly determined by **how many zero-scorers the panel
contains** (−0.98), and the predictor, a mean over the same rows, moves with it. Remove the
between-season level and the correlation falls from 0.76 to 0.24.

## 2. The 43.6% is against a baseline nobody would use

| walk-forward MAE, 4 predictors (itt, gt, l4, sal) | production panel |
|---|---:|
| all-history mean (production's baseline) | 1.540 |
| **season-to-date mean** | **0.329** |
| OLS on pre-lock predictors | 0.869 |
| OLS vs all-history | **+43.6%** (reproduced) |
| **OLS vs season-to-date** | **−164.2%** |

The all-history mean ignores that each season has its own level. The obvious forecaster — this
season's mean so far — is **2.6× better than the model** on this panel. The model's 43.6% is mostly
learning the season.

## 3. On a panel that matches the question, a real but modest signal survives

Holding composition fixed to the **top 150 salaries per slate** — closer to the pool a DFS
lineup is built from, and to the lineup-level environment the simulator mis-predicts:

| | top-150 panel |
|---|---:|
| corr(l4, env) pooled / **within season** | +0.428 / **+0.412** |
| MAE season-to-date / OLS | 0.920 / 0.841 |
| **OLS vs season-to-date** | **+8.6%** |

**So the environment is somewhat predictable within a season — about 8.6% better than the
season-to-date mean, out of sample.** That is a genuine result, and it is roughly a fifth of what
was reported.

## What this does to the plan

The report's conclusion was that regime-dependence "stops being a reason nothing replicates and
becomes a covariate." **At 8.6% it is a weak covariate.** It will not, on its own, explain the Week
1 / Week 2 flip (the simulator predicted ~123 while realized pool means ran 94 to 141; an 8.6% MAE
improvement on the slate mean does not bridge that). The mechanism in the report — that the
simulator's bias correlates with its own preference — stands; the claim that the scoring
environment behind it is largely forecastable does not.

Two things worth doing if this is pursued:

1. **Use the season-to-date mean as the baseline** in any preregistration. Against the all-history
   mean nearly any season-aware model looks strong.
2. **Define the environment on a fixed-composition pool** (top-N salary, or the actual DK slate),
   not on every salaried row, or the target is mostly a count of backups.

Caveats: I used the same four predictors and the same walk-forward start (40 slates) as the
original; different choices of N for the fixed panel will move 8.6% somewhat, and 2022–24 are
absent from the panel entirely (no salaries), so the walk-forward jumps from 2021 to 2025.
