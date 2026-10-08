# Preregistration: study 64 (S1), a game-environment calibration on Fantasy Points (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08** by the reviewer.
- Written before the 2023–25 joint fit is run, so the model's form is fixed before its coefficients are seen.
- It freezes before Sunday 10-11 12:00 CT, so W5's main slate is the first prospective week. TNF is off the slate.

**Units:** DK points, z-scores and rates only.

## 1. Why
- **The operator 10-08:** "please make sure that the recommended experiments that the outside reviewer suggested in the
  pros briefing are on the agenda before week 6". This is study list 64, from
  `briefings/2026-week-05/2026-10-08-how-the-pros-pick-players.md` §8 S1.
- **The history** is the outside reviewer's analysis C, `reports/2026-10-08-pro-methods/c_history_beyond_market.py`. On
  2023–25, it asked which pre-lock data points predicted DK points BEYOND the betting market, the best historical
  stand-in for FP's projection.
  - Team implied total: +0.33 per sd (z 3.4, the same sign in all 3 seasons, passing Bonferroni over 40 data points).
  - Wind: −0.35 per sd (QB about −1).
  - Game total and expected plays: about +0.24 each.
- **Why it matters:** FP shows no sign of carrying this, and the regulars don't use it. It would be information the
  field's projections lack.
- **This study adopts nothing.**
  - A paper book follows from W6, by a study 38 amendment before W6's lock.
  - A reversible trial follows only after the pooled check favours it.
  - The operator decides both.

## 2. The adjustment (`scripts/s64_env_fit.py`, frozen as a coefficients file)
- **Fit rows:** 2023–25 played QB / RB / WR / TE player-weeks with a props number (`market_points`, at least 2 scoring
  markets).
- **The residual:** y_dk_points − market_points, demeaned within season × week × position.
- **The model, per position:** the demeaned residual ~ b_itt · z(implied_team_total) + b_wind · z(wind), least squares.
  - Each z is taken within season × week × position.
  - **The two variables are fitted JOINTLY.** They are the only two that pass Bonferroni with 3-of-3 seasons. Game
    total, spread and expected plays overlap the implied total, and adding their solo coefficients would double-count.
- **Wind under a roof is 0.** Training's wind is NULL for every dome player-week in 2023–25, because it comes from the
  schedule. The live frame gives domes Open-Meteo's outdoor wind. Applying it there would invent wind that training
  never saw.
- **Uncertainty:** a whole-week bootstrap (300 reps, seed 3), with per-season coefficients.
- **The file:** `reports/2026-10-09-s64-env/s64_env_coefficients.json`, create-once and tracked, with the rows, the input
  content sha and the fitter's sha.

## 3. Applying it (`scripts/s64_env_apply.py`)
- **On a week's T-70 frame:**
  - Each skill player's z(implied_team_total) and z(wind) are taken within the frame by position, over the players
    with an FP projection, with dome wind 0.
  - A missing value contributes 0.
  - env_adj = b_itt · z_itt + b_wind · z_wind, capped at ±2.0 points.
  - fp_env = max(fp + env_adj, 0).
- **The output:** a private CSV with id, dk_draftable_id, pos, fp, env_adj and fp_env.

## 4. The weekly record and the rule (`scripts/s64_env_line.py`)
- **Per week from W5:**
  - It reads `scripts/weekly_projection_accuracy.py`'s own private player rows: the same population (QB / RB / WR / TE,
    FP ≥ 3 or ours ≥ 3, game-day active, an actual) and the same actuals.
  - It adds FP + ENV as a source.
  - It prints the reader's metrics (MAE, bias, Spearman) with its game-cluster bootstrap (B 2000, seed 1).
  - Single weeks are descriptive.
- **THE POOLED CHECK** is the frozen reader's own rule, so the comparison cannot drift. It reads "FP + ENV beats FP" when
  the pooled MAE is lower AND at least 95% of the pooled resamples are better.
  - From W8, with at least 4 weeks, that reading makes the adjustment trial-eligible. That is his decision.
  - Before that it is descriptive only.

## 5. Order
1. This DRAFT.
2. The fit; the coefficients file, with its numbers recorded here.
3. The application and the weekly line, with their tests.
4. The freeze, before Sunday 10-11 12:00 CT.
5. The laptop's ack and re-run of the fit.
6. Monday 10-12: the first line (W5).
