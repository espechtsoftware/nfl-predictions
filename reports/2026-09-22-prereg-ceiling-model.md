# PREREG — Does modelling P(30+) directly beat modelling the mean, at picking ceiling games?

**Frozen 2026-09-22, before any arm was fitted or any result seen.** Authorised by the
operator the same day. Runs **locally** (operator's standing instruction: historical
tests local, week-build work on Cloud Run).

## Why

A lineup that wins a large-field GPP is, empirically, **five players each scoring 30+**
(the 45 real Week-1 lineups at 250+ average 5.18 such players). Our entire stack targets
**E[points]**. `proj_p90`, `proj_std` and `p_20_plus` exist in `player_projections` but
are **not carried into the frame** the generator consumes, so nothing downstream sees a
ceiling signal. On the two 2026 weeks, DK salary ranked 30+ games at least as well as
anything we produce (AUC 0.942 vs our projection 0.927) — on 15 positives, so not
significant, which is itself the point: **we have no demonstrated ceiling edge over the
price tag.**

## Question

Does a model trained **directly on P(DK points ≥ 30)** rank ceiling games better than
(a) the same features trained on the mean, and (b) DK salary alone?

## Universe and support (outcome-blind census, taken before freezing)

`nfl_features.player_week_training`, seasons **2014–2025**, rows with a salary:
**102,927** rows, **1,807** at 30+ (**1.76%**), 129–190 positives per season.
By position: WR 685, QB 554, RB 468, TE 100. 2026 is **excluded** from fitting and
model selection.

## Arms

| arm | what it is |
|---|---|
| **CEIL** | LightGBM **binary classifier** on `hit30 = y_dk_points >= 30` |
| **MEAN** | LightGBM **regressor** on `y_dk_points`, ranked by prediction — *what we do now* |
| **SALARY** | rank by `salary` alone — the price-tag benchmark |

All three use the **existing** `featureset.NUMERIC_FEATURES` plus position. **No new
data is introduced**, so a win is attributable to the target, not to extra information.
Identical hyperparameters for CEIL and MEAN except the objective.

## Validation

**Walk-forward by season only** (project law; never random splits). For each test season
S in **2018…2025** (8 folds), train on every season < S, predict S. No shuffling, no
leakage across the season boundary.

## Metric

Primary: **AUC for hit30** on the held-out season.
Secondary, reported but not gating: precision@100 (of the 100 highest-ranked
player-weeks in the season, how many scored 30+), and the same split by position.

## Preregistered success criterion

CEIL is adopted as promising **only if all three hold**:

1. CEIL beats **both** MEAN and SALARY on AUC in **≥6 of 8** test seasons;
2. CEIL's mean AUC exceeds each benchmark's by **≥0.005**;
3. no single season where CEIL trails the better benchmark by **>0.01** AUC.

Anything less is a negative result and will be reported as one. A pass makes CEIL
*promising*, not adopted: adoption additionally requires it to survive at the lineup
level, which this experiment does not test.

## Vacuity check (required before reading the result)

Confirm CEIL and MEAN produce genuinely different rankings — Spearman correlation
**< 0.99** on the test seasons. Byte-identical or near-identical arms are a dead lever
and the comparison would be meaningless (project law: vacuity checks, env-name typos and
column-gated levers have both happened here).

## What this does NOT establish

Ranking players is not building lineups. Even a decisive win leaves open whether lineups
built to maximise expected 30+ count actually have a fatter upper tail, which is a
separate, later test. And the ceiling target does not address the simulator regime flip;
it is a different layer.
