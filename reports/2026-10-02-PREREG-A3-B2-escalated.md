# PREREG-A3 and PREREG-B2: frozen before the Week-4 lock (laptop, 2026-10-02; operator: "I will want those timelines escalated")

**Status: FROZEN at the commit that adds this file.** It is written before the Week-4 Sunday slate is played: no
Week-4 ownership or points outcome exists. Both tests start grading with **Week 4**, one week earlier than the 10-02
plan (`reports/2026-10-02-experiment-plan-new-data.md`).
- Their inputs are all captured before lock, Saturday 10:07 and Sunday 10:38 CT. The code that computes them (the
  article matcher; the blend) is written and reviewed after this freeze. It may only implement what is fixed here.
- Neither adopts anything. A pass is reported to the operator, who decides.

## PREREG-A3: article mentions as an ownership input

- **Question:** does a per-player count of mentions in the week's widely read DFS articles raise the accuracy of the
  pre-lock ownership predictor?
- **Articles counted** (fixed now; decided by the title, from `nfl_raw.fantasy_points_articles`, the newest capture
  before the Sunday lock, paywalled previews excluded). Titles matching, case-insensitively, any of:
  - `DFS Main Slate Early Look`
  - `DFS Slate Breakdown`
  - `Advanced Matchups`
  - `The Everything Report`
  - `WR/CB .* Matchups`
  - `OL/DL Matchups`

  Showdown, betting, dynasty, waiver, trade, IDP and season-long articles are NOT counted.
- **Feature:** M(player) = the number of distinct counted articles whose text names the player.
  - Names are matched on `ownership_blend.norm` (Jr/Sr/II/III/IV/V dropped, punctuation removed), full name only.
  - DSTs are matched by team nickname followed by "D/ST", "DST" or "defense".
- **Arms** (the ownership percent, then ranked):
  - **LAG_M:** LAG × (1 + 0.25·M);
  - **FP_M:** FP × (1 + 0.25·M), on FP's covered players.
  - The 0.25 factor is fixed now and is never fitted.
- **Baselines:** LAG for LAG_M; FP for FP_M. The same population, target and metric as PREREG-O1 (realized Millionaire
  ownership counted from `contest_entries`; Spearman).
- **Rule:** an arm passes if its mean Spearman gain over its baseline across **Weeks 4–7** is **>= 0.03** and it is
  better in **>= 3 of 4** weeks.
  - **Interim (one look, after Week 5):** a gain >= 0.06 in both weeks, as O1 amendment 2.
- **Co-reported:** M's coverage (the share of the realized top 20 with M >= 1) and the match rate.

## PREREG-B2: Fantasy Points in the projection blend

- **Question:** does adding FP's DraftKings projection to our served mean lower the error on actual DK points?
- **Arms** (fixed weights, never fitted):
  - **OURS:** the served `proj_points` (0.45 model / 0.55 market);
  - **B2_EQ:** 1/3 model, 1/3 market, 1/3 FP;
  - **B2_45:** 0.45 model, 0.275 market, 0.275 FP.
  - Model = `model_points_pre`, market = the market mean, FP = `fantasy_points_dfs_projections.fantasy_points` on the
    week's main DraftKings slate (newest pre-lock capture).
  - **Coverage:** where FP or the market is missing for a player, the weights renormalise over the sources present.
    Coverage is reported by position.
- **Population:** main-slate skill players and DSTs projected >= 3 points by OURS, who played (DK points recorded).
- **Metric:** MAE of the projection against actual DK points, overall and by position (QB/RB/WR/TE/DST).
- **Rule:** an arm passes if its overall MAE is **lower than OURS in >= 3 of Weeks 4–7** and on the 4-week mean.
  - **Interim (one look, after Week 5):** lower in both weeks by >= 0.10 points.
  - A pass makes the arm eligible for a paper-book test (the post-ensemble law: a projection gain must survive
    selection). It adopts nothing by itself.
- **Co-reported:** bias by position; the correlation; the B3 disagreement cases.
