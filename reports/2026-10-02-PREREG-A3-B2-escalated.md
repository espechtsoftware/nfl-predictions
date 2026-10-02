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
- **A second count, M_DFS** (the reviewer, 10-02): the matchup pieces (WR/CB, OL/DL, the Everything Report) name
  nearly every starter, so M saturates for starters. M_DFS = the same count over the DFS articles only (`DFS Main Slate
  Early Look`, `DFS Slate Breakdown`).
- **Arms:** two forms × two counts, per base (LAG and FP), so **8 arms**:
  - **multiplicative:** base × (1 + 0.25·C);
  - **additive:** base + 2.0·C percentage points (the reviewer: the multiplicative form cannot lift a player the base
    puts near zero, the article-hyped cheap breakout);
  - **C** = M or M_DFS.
  - The constants 0.25 and 2.0 are fixed now, blind, and never fitted.
- **Multiplicity:** 8 arms against two baselines. A pass is reported and flagged to the operator; it adopts nothing by
  itself.
- **Baselines:** LAG for LAG_M; FP for FP_M. The same population, target and metric as PREREG-O1 (realized Millionaire
  ownership counted from `contest_entries`; Spearman).
- **Rule:** an arm passes if its mean Spearman gain over its baseline across **Weeks 4–7** is **>= 0.03** and it is
  better in **>= 3 of 4** weeks.
  - **Interim (one look, after Week 5):** a gain >= 0.06 in both weeks, as O1 amendment 2.
- **Co-reported:** the coverage of M and M_DFS (the share of the realized top 20 with C >= 1) and the match rate.
  Full-name matching counts articles, not mentions, so a last-name-only mention after the first does not matter.

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
  This hides availability errors (a player who did not play); B3 (the disagreement report) covers those.
- **Metric:** MAE of the projection against actual DK points, overall and by position (QB/RB/WR/TE/DST).
- **Rule:** an arm passes if its overall MAE is **lower than OURS in >= 3 of Weeks 4–7** and on the 4-week mean.
  - **Interim (one look, after Week 5):** lower in both weeks by >= 0.10 points.
  - A pass makes the arm eligible for a paper-book test (the post-ensemble law: a projection gain must survive
    selection). It adopts nothing by itself.
  - **On purpose, the final has no magnitude bar.** A no-better arm passes it ~25–30% of the time (the reviewer). That
    is acceptable only because a pass is mere eligibility for the paper test, never an adoption.
- **Co-reported:** bias by position; the correlation; the B3 disagreement cases.

## Amendment (2026-10-02, the same day, BEFORE the Week-4 lock): the reviewer's review of 33aeb204

The changes above, all made before any Week-4 outcome exists:
- A3: the additive form, the M_DFS count, 8 arms and the multiplicity.
- B2: why the final has no magnitude bar; what the population hides.
- O1 amendment 2: the scale rule.

The A3 matcher and the B2 blend code go to the reviewer as soon as they are written, before Monday's run. Their numbers
count only after review.

## Amendment B2-1 (2026-10-02 ~14:45 CDT, BEFORE the Week-4 lock): our components carry our own gates

Found by the B2 reader's dry run on the Week-4 pre-lock data, before any outcome. `market_source_log` records the model
and market components BEFORE the availability and backup-QB gates. For example, Caleb Williams (ruled out) is logged
at 18.2, and backup QBs at 9–14; the served projection zeroes them. Blending the raw components would hand ruled-out
players points our served projection does not.
- **OURS is the SERVED projection:** `player_projections.proj_points`, the newest pre-lock batch.
- **The model and market components are scaled** by r = served / logged `proj_points` (r = 0 when the served value is 0).
  So our own gates apply to our components; FP's number stays FP's.
- The weights, the population (now restricted to the main slate's DraftKings player list, and DSTs included from the
  projection table), the metric and the rule are unchanged.

## Clarification B2 (2026-10-02 14:31 CDT, before the lock): which run B2 reads

B2 reads the **newest pre-lock project-slate run**. For Week 4 that is the T-70 run (~10:36 CT Sunday). The T-70 path
writes market_source_log in the same run as player_projections. This was verified on the operator's 10-02 rehearsal
execution with the T-70 rules on (`project-slate-fvzzj`): player_projections 09:20:08Z, market_source_log 09:19:52Z.
The one-run pairing (<= 300 s) therefore holds. If it refuses on Monday, B2 is not graded for that week, and the miss is
disclosed; no fallback run is substituted.

**Known limit (reader, 10-02):** `market_source_log` carries no team. B2 therefore drops a name that occurs twice on the
main slate's DraftKings list (any position), and a name whose log rows differ in position; both are printed. Two
same-name players of whom only one is on the slate are matched by name to the slate's one.
