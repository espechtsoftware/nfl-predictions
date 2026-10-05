# PREREGISTRATION (DRAFT for review) — Study 22a: does the served projection miss in five pre-declared directions?

2026-10-05.
- **Class C:** calibration, under `reports/2026-09-19-in-season-adoption-track.md`.
- **Origin:** study-list item 22(a). The hypotheses came from the regulars' player-choice report
  (`reports/2026-10-05-regulars-player-choices.md`, §3).
- **Design:** the reviewer's (2026-10-05). It is a SEPARATE study, not endpoints inside the defence re-test arm of the
  six-season co-run. That arm is a feature test with its own frozen adoption rule, and extra endpoints would inflate its
  multiplicity.

**Status: DESIGN FROZEN** after the reviewer's review (2026-10-05, fixes A–C applied; the commit that adds this line is
the freezing commit). It must be in force before any outcome of the Thursday 10-08 co-run is seen.
Two things are filled in at freezing, without looking at outcomes:
- the co-run panel's identity;
- the outcome-blind support census (§6).

## 1. Question

The question is whether the served projection's miss, realized DK points minus `mean_projection`, depends on five
pre-lock quantities in the directions the 2026 Weeks 2–4 exploration suggested. That exploration was post hoc: 14
features were examined, about 390 player-weeks, and no feature survived a correction. The study does not ask whether a
feature improves the model's MAE; the July ablation asked that for defence features (+0.008 MAE) and the co-run's
defence arm asks it again. Here the question is whether the projection we SELECT on is biased along these
directions.

## 2. Data (point-in-time)

- **Projection and outcome.** The co-run CONTROL arm's walk-forward out-of-sample served projection, for seasons
  2022–2025.
  - It is `mean_projection` in `nfl_predictions.slate_player_features`: the served post-market mean, set at
    `replay.py:954` before the p90 punt valuation overwrites `proj`.
  - The rows are the ones `backtest/engine.py` appends per replayed slate, selected `WHERE panel_run_id = <the control
    panel's id> AND research_eligible`. The id is taken from the co-run manifest at freezing.
    `research_eligible` is set only by a passing promotion (`scripts/harvest_accept.py`).
  - The outcome is that row's `actual` (DK points).
  - `model_points_pre` (the model-only number) is read for one printed secondary (H5, §4).
  - One row per (season, week, gsis_id). A duplicate identity is a fail-closed error.
- **Persistence is required, decided now.** The engine writes these rows to BigQuery only, and best-effort unless
  `cand_log_required` is set; there is no local snapshot to fall back on.
  - The co-run control must therefore run with `CAND_LOG_TABLE` set and `cand_log_required=True`, and be promoted by
    `harvest_accept.py`.
  - **If the co-run does not persist and promote its control rows, study 22a is NOT run on it.** It waits for the
    next persisted, promoted panel built on the same image, and the reason is recorded. It is never redirected after
    outcomes are seen to an older panel or to a hand-built substitute.
- **Market caveat.** 2022 rows are model-only (no market). 2023–25 carry `market_points` built under the live
  ≥ 2-market rule if the co-run rebuilds markets; if it reuses the older panel's one-market blend (Data deficiency log
  2026-09-23), that is disclosed and the study runs on whatever the co-run serves.
- **Excluded:** every 2026 week, because Weeks 2–4 generated the hypotheses.
- **Eligible rows.** Within each (season, week, position), the top N by `mean_projection` (QB 24, RB 48, WR 72, TE 24),
  with a salary and a non-null `actual`. DST is out. This is the DFS-relevant pool. It is fixed by projection rank,
  never by outcome.

## 3. Hypotheses and predictors

All predictors are known before week W's lock. H1–H4 are standardised within (season, position) before pooling.

| | Predictor | Point-in-time definition | Predicted sign of the miss |
|---|---|---|---|
| H1 | Last season's defence vs position | DK points per game the opponent allowed to the player's position over season s−1 (REG weeks), from `nfl_raw.weekly_stats` with the DK scoring of `regulars_players.py` | **+** (weak last-season defences beat the projection) |
| H2 | Early-season defence vs position | The same quantity over season s weeks < W. Defined for W = 2–5 only (one to four games); otherwise excluded. Widened from 2–4 before freezing and outcome-blind (reviewer fix A): 168 eligible rows a week gives about 504 per season for weeks 2–4 before nulls, under the 500 floor by construction; weeks 2–5 give about 670 | **−** (small-sample "soft" matchups fall short) |
| H3 | Most recent game's DK points | The player's DK points in his most recent PLAYED game of season s before week W (NULL in his first game of the season), so byes do not drop rows (reviewer fix C) | **−** |
| H4 | Salary change | `nfl_features.dk_salary_week.salary_delta_wow` (week W salary minus W−1) | **−** |
| H5 | Value calibration | Top decile of `mean_projection / (salary / 1000)` within (season, week, position) | **−** (we over-project our best value plays: regression toward the market) |

## 4. Endpoints and decision rule (frozen)

- **H1–H4: Spearman ρ** between the miss and the predictor, pooled over eligible player-weeks of 2022–2025. **Both**
  the miss and the predictor are standardised within (season, position) before pooling, so the high-variance
  positions do not dominate the ranks (reviewer fix B). The per-position ρ is printed beside it, so a pooled verdict
  cannot hide a sign flip by position.
- **H5:** the mean miss in the top value decile minus the mean miss of the other eligible rows, in DK points. A printed
  secondary with no verdict repeats it with `model_points_pre` in place of `mean_projection`, as both the value base and
  the miss. It separates "the model over-projects value" from "the blend does".
- **Interval:** a bootstrap over (season, week) clusters (about 68), B = 20,000, seed 20261005, two-sided level
  1 − 0.05/5, i.e. a **99% interval**. Four season clusters are too few to bootstrap; week clusters absorb the within-week
  game and team correlation, and the LOSO sign rule covers season-level instability (reviewer, agreed). The reader's test asserts the PRINTED level against this sentence.
- **Verdict per hypothesis:**
  - **CONFIRMED** if the 99% interval excludes 0 in the predicted sign AND the point estimate has the predicted sign
    in at least 3 of the 4 seasons (at most one negative, the standing LOSO law);
  - **OPPOSITE** if the interval excludes 0 in the other sign;
  - otherwise **NOT CONFIRMED**.
- **Also printed, with no verdict:** each hypothesis by position and by season, and the decile curve (mean miss by
  predictor decile).

## 5. What a verdict can and cannot do

- **CONFIRMED does not change production.** It qualifies a class-C trial package: a residual adjustment term fitted
  walk-forward on seasons < S (H1–H4), or a shrink toward the market in the top value decile (H5). It is tested with
  its own comparison, monitoring and rollback, and the operator decides.
- **NOT CONFIRMED closes the hypothesis** for the in-season track. The 2026 tilt is then described as the field's
  habit, not as our projection's error.
- **The post-ensemble law:** the verdict holds for the served projection of the co-run's control image. A later model
  change re-opens it only through a new preregistration.

## 6. Support census (outcome-blind, before freezing)

Printed by the reader's `--census` mode: eligible rows, and non-null rows per predictor, per season × position. It
reads identities, predictors and eligibility only, never `actual`. Each hypothesis needs at least 500 eligible non-null
rows in each season; a hypothesis below that is reported UNSUPPORTED, never tested on fewer rows. Expected support:
- H2 covers 4 of 17 weeks (weeks 2–5);
- H3 loses only each player's first game of the season;
- H4 needs both weeks' salaries (`dk_salary_week` holds 12,845–13,933 rows per season for 2022–25).

## 7. Mechanics

- **Reader:** `scripts/study22a_report.py`, frozen by sha at the freezing commit, with the `<NAME>_REPAIR_SHA256`
  override pattern from day one (frozen-chain rule 3).
- **Smokes before freezing** (rule 1): one on a synthetic panel with planted effects (the verdict must recover them,
  and a null panel must give NOT CONFIRMED), and one in census mode on the real co-run panel (outcome-blind). There is
  no run on real outcomes before the freeze.
- **Byte-identical cross-party re-run:** the party that froze it reads first; the other re-runs the frozen reader, and
  the outputs must match byte for byte before the system-study row is written.
- **Compute:** no extra compute; it consumes the co-run's rows. It runs on the laptop after the co-run writes them, and
  never in a build window.

## 8. Disclosure

- The five hypotheses were chosen after looking at 2026 Weeks 2–4, which are excluded.
- On those weeks only H1 (z = 2.8) and the value relation (z = −2.7) came near a 14-feature Bonferroni line (|z| ≥ 2.9);
  none reached it.
- A July addendum (system study Addendum 6) named "the field's recency bias" from outcome-selected winner lineups. It
  was never tested this way, and has not been re-verified since the July audits.
