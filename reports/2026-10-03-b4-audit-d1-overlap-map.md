# B4 outcome-blind audit and D1 overlap map (2026-10-03)

**Scope.** This covers the plan's B4 audit (§2 B4, items 1–2) and D1 overlap map (§2 D1) in
`reports/2026-10-02-experiment-plan-new-data.md`. The work was read-only:
- light BigQuery SELECTs against `nfl-predictions-503414`;
- `gcloud storage ls` and `cat` against the licensed archive;
- code reading at the integration tip `61cd4962`.

**Outcome-blind.** No outcomes, scores, lift or proper scores were read. The only "actual" columns touched were
pre-game feature values, vendor captures and pre-lock projections.

**Licensing.** No licensed raw values appear here. Only counts, shares and correlations.

**Files next to this report:**
- B4 coverage: `b4_coverage_counts.csv`, `b4_coverage_by_position.csv`, `b4_panel_weeks1to4_by_season.csv`
- B4 lag check: `b4_xfp_live_vs_training_definition.csv`
- Revision checks: `revision_route_share_2026w2.csv`, `revision_sis_2026w1_summary.csv`,
  `revision_sis_2026w1_by_field.csv`
- D1 correlations: `d1_overlap_correlations.csv`
- The scripts that made them: `b4_cov.py`, `b4_byweek.py`, `b4_xfplag.py`, `rev.py`, `sis_rev.py`, `d1_corr.py`,
  `d1_xfp.py`, and the helper `bq.py`

## Summary

1. **The model's "XFP" and the FP Data Suite's XFP are different things.**
   - `xfp_l4` is home-built from free nflverse pbp, using 2014–18 bucket rates (`sql/features/017j_xfp_schedule.sql`).
     Separation (`separation_l4`) is NGS. PROE (`proe_l4`) is nflverse.
   - The only FP Data Suite data in `player_week_inference` and `player_week_training` is Route Share
     (`fp_route_share_*`).
   - FP's own XFP, Bell Cow share, weighted opportunity and FP PROE have **no column** in either table. Their B4
     coverage is 0 by construction until feature SQL is written.
   - FP's XFP history (`fantasy_points_advanced_receiving_windows`) starts at target week 5 (cumulative) or 6 (last
     four) in every season 2022–25.
2. **`xfp_l4` still differs between live and training (train/serve skew)**, in two ways:
   - **Weeks 1–2:** structurally NULL live (0% in W1 and W2), while training rows have about 32% at week 2.
   - **Weeks 3–4:** where it is present live, it is one game stale. The as-of join takes the latest row's
     `1 PRECEDING` window, so it leaves out the most recent game.
     - In W3 and W4, 211 of 222 and 267 of 281 non-NULL live values differ from the training definition.
     - The mean absolute gap is 1.96 and 1.35 xFP, on a mean of about 7.
     - The live-to-training correlation is 0.89 and 0.93.
     - Another 115 and 88 live rows are NULL although the player has 2026 history.
3. **In training, `xfp_l4` missingness encodes the same week's outcome** (found by reading the code; not measured,
   to stay outcome-blind).
   - `player_week_xfp` has a row only for weeks in which the player had a target or a carry.
   - Training joins that table on the exact week.
   - So a training row is NULL exactly when the player had no opportunity in the labelled week.
   - The August "XFP positive alone" result (Addendum 49) may partly reflect this. **The reviewer should check this
     before any B4 preregistration.**
4. **FP Route Share coverage is fine, but RB and QB values are stale.**
   - Live coverage on the projected pool is 82–91% in W1–W4, against 59–82% in the panel's weeks 1–4.
   - The 2026 weekly captures contain **only WR and TE rows**, while the 2022–25 history includes QB and RB.
   - So every live RB and QB value is a 2025 cross-season carry: 85 of 85 RB and 60 of 60 QB rows in W4. In the
     2025 panel's weeks 3–4, 224 of 315 RB rows had in-season values.
5. **Revisions: what can and cannot be tested.**
   - **Can't test FP history:** the 2022–25 Data Suite history was downloaded once (08-10 and 08-11-2026), with no
     contemporaneous capture to compare against. Its BigQuery copy is unchanged since 09-04 (identical
     fingerprints).
   - **The one FP double capture (2026 W2 Route Share) was not a vendor revision.** It was an unfinished export,
     already logged in README on 09-23.
     - 67 keys were added and 174 of the 200 shared keys changed.
     - The two captures correlate at 0.18.
   - **SIS week-1 re-capture, 3 days apart:** the counting stats are identical, but the four value metrics (Points
     Saved, PAA, and their per-play forms) changed in all 32 rows.
6. **Overlap (D1): FP mostly duplicates what the system already gets.**
   - FP DK projection vs our served projection, W4 main slate: n=335, Pearson 0.979, Spearman 0.950.
   - FP vs the Odds-API market-only points: n=179, 0.974 / 0.974.
   - FP Route Share vs free nflverse snap share: WR 0.97, TE 0.88–0.90, RB 0.90.
   - FP defense PROE vs nflverse `pass_oe` allowed: about 0.91.
   - FP XFP vs our pbp `xfp_l4`: about 0.95.
   - FP pressure vs SIS pressure: 0.60–0.83.
7. **Only two paid inputs reach the money path directly.**
   - Odds API `prop_lines` is 55% of every projection, the build audit's coverage gate and the vetter's flag for a
     vanished market.
   - FP `projected_ownership_pct` drives the Week-4 ownership-term trial.
   - LineStar reaches it only indirectly: the 2022–25 realized ownership it backfilled trains the lag model. Its
     live file is a fallback, dead this week.
   - SIS and every FP Data Suite table are shadow or research only.

## 1. B4 audit

### 1.1 Method: which rows count as "the live build"

`nfl_features.player_week_inference` is `CREATE OR REPLACE`d on every build and holds only the upcoming week
(`u.is_upcoming`). Past weeks' live rows are therefore not kept in the table. I identified each week's live rows as
follows:
- **The build the projection read.** From `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` (destination table
  `player_week_inference`, successful CTAS jobs), the last build before each week's final pre-lock projection run
  in `nfl_predictions.player_projections`:

  | Week | Last inference build (UTC) | Final projection run it fed (UTC) |
  |---|---|---|
  | W1 | 09-13 15:37 | 09-13 16:03 |
  | W2 | 09-20 15:34 | 09-20 16:02 |
  | W3 | 09-27 15:34 | 09-27 16:03 |
  | W4 | 10-03 14:52 | 10-03 15:12 (the latest so far; Sunday's T-70 builds are still to come) |

- **W3: exact.** BigQuery time travel (`FOR SYSTEM_TIME AS OF '2026-09-27 16:00 UTC'`) returns the 09-27 15:34
  table.
- **W4: exact.** The current table, built 10-03 14:52.
- **W1 and W2: reconstructed.** They are outside the 7-day time-travel window, and no snapshot exists:
  - no `player_week_inference` copy in `nfl_backups`;
  - the `_control` and `_salaryfix` copies are other pipelines;
  - `slate_player_features` has only fp_route fields, and only for W1.

  The reconstruction re-applies `023`'s exact join logic to the current feature tables:
  - `xfp_l4`: the latest 2026 `player_week_xfp` row with week < W;
  - `separation_l4`: `player_week_advanced` at (2026, W);
  - `proe_l4`: `team_week_context` at (2026, W);
  - fp_route: `017k` re-run against `fantasy_points_route_share` rows with `ingested_at` ≤ the build time.

  **Validation:** on W3 and W4 the reconstruction reproduces the time-travel and current snapshots exactly for every
  audited feature (same non-NULL counts). For W1 and W2 it assumes the pbp and NGS rows for the earlier weeks had
  loaded by the build. For W1 that is moot, because every in-season window is structurally empty.
- **Populations:**
  - **projected:** the skill-position `gsis_id`s in the final pre-lock projection run, i.e. the rows the live
    projection actually priced. All of them have an inference row: 0 missing in W3 and W4.
  - **inference_all:** every skill row in the table, roster-wide, about 880 per week.
- **Panel:** `nfl_features.player_week_training`, the table the six-season panel trains and replays on. Seasons
  2023, 2024 and 2025 are reported here; 2019, 2021 and 2022 are in the CSV. Skill positions only.
  - Since 2022 the panel also keeps listed-inactive players (about 750 per week, against about 380 in 2019 and
    2021). Its denominators are therefore wider than the live projected pool's. `target_share_l4` is included as a
    reference column for that difference.

### 1.2 Coverage table (share non-NULL; n in brackets)

Live columns are the **projected** pool. The panel columns use the same weeks 1–4, or all weeks, as stated.

| Feature (source; in model?) | W1 live [433]* | W2 live [481]* | W3 live [487] | W4 live [434] | Panel 2023 W1–4 [3142] | Panel 2024 W1–4 [3156] | Panel 2025 W1–4 [3032] | Panel 2023 / 2024 / 2025, all weeks [13084 / 13132 / 12845] |
|---|---|---|---|---|---|---|---|---|
| `target_share_l4` (nflverse; model) — reference | 0.000 | 0.796 | 0.836 | 0.885 | 0.426 | 0.422 | 0.441 | 0.604 / 0.599 / 0.599 |
| `xfp_l4` (home-built pbp; candidate) | **0.000** | **0.000** | 0.446 | 0.576 | 0.245 | 0.240 | 0.255 | 0.344 / 0.337 / 0.336 |
| `separation_l4` (NGS; model) | 0.000 | 0.141 | 0.193 | 0.240 | 0.101 | 0.086 | 0.094 | 0.151 / 0.148 / 0.147 |
| `proe_l4` (nflverse team; table only) | 0.000 | 1.000 | 1.000 | 1.000 | 0.712 | 0.715 | 0.753 | 0.931 / 0.932 / 0.942 |
| `fp_route_share_last` (**FP**; candidate) | 0.822 | 0.892 | 0.893 | 0.910 | 0.718 | 0.751 | 0.785 | 0.795 / 0.824 / 0.833 |
| `fp_route_share_l4` (**FP**; candidate) | 0.822 | 0.892 | 0.893 | 0.910 | 0.718 | 0.751 | 0.785 | 0.795 / 0.824 / 0.833 |
| `fp_route_share_jump` (**FP**; candidate) | 0.820 | 0.811 | 0.877 | 0.887 | 0.662 | 0.706 | 0.743 | 0.754 / 0.789 / 0.808 |
| FP XFP, Bell Cow share, weighted opportunity, FP PROE | no column | no column | no column | no column | no column | no column | no column | no column |

\* Reconstructed (see 1.1).

**The roster-wide live population** (`inference_all`):

| | n | `xfp_l4` | `separation_l4` | `proe_l4` | fp_route last / l4 | fp_route jump |
|---|---|---|---|---|---|---|
| W3 | 880 | 0.252 | 0.109 | 1.0 | 0.709 | 0.681 |
| W4 | 881 | 0.319 | 0.128 | 1.0 | 0.717 | 0.689 |

**The panel by week**, 2023–25 (`b4_panel_weeks1to4_by_season.csv`):
- Week 1 is NULL for every in-season feature in every season: `xfp_l4`, `separation_l4`, `proe_l4` and
  `target_share_l4` are all partitioned by season.
- `xfp_l4` by week: W2 0.31–0.33, W3 0.34–0.35, W4 0.35–0.37.
- **The live-vs-panel mismatch is therefore at W2:** 0.000 live against about 0.32 in training.

**Like-for-like:** `xfp_l4` coverage among rows that have usage history (`xfp` / `target_share_l4`):

| Population | Share |
|---|---|
| Live W3 | 217 / 407 = 0.53 |
| Live W4 | 250 / 384 = 0.65 |
| Panel weeks 3–4, 2023–25 | about 0.57 (1582 / 2763 pooled) |

So beyond W2, the share present live is close to the panel's, and **the content is the problem (1.3)**, not the
count.

**By position** (`b4_coverage_by_position.csv`):
- `separation_l4` is WR/TE only. Live WR 0.40 (W3) and 0.48 (W4), against 0.28 in the panel's weeks 3–4. Live TE
  0.20 and 0.28, against 0.16.
- `xfp_l4` for QBs is low everywhere: live 0.13–0.24, panel 0.16.

### 1.3 Two `xfp_l4` defects (code reading, plus one feature-only measurement)

1. **The live value is one game stale.**
   - `023`'s `xfp_asof` takes the player's latest `player_week_xfp` row. That row's `xfp_l4` is
     `AVG … ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING`, so it excludes the latest game itself.
   - The training row at week W averages the 4 game-rows before W, **including** W−1.
   - Measured against the training definition, rebuilt from 2026 pbp with 017j's exact bucket logic
     (`b4_xfp_live_vs_training_definition.csv`):

     | Week | Live non-NULL | Differ | Mean absolute gap (xFP) | Correlation | NULL live but history exists |
     |---|---|---|---|---|---|
     | W3 | 222 | 211 | 1.96 | 0.888 | 115 |
     | W4 | 281 | 267 | 1.35 | 0.933 | 88 |

   - W1 and W2 are NULL for everyone, because the latest 2026 row's lagged window is empty.
   - The 08-04 audit comment in `023` ("the same information a played-week row would carry") is not correct.
2. **In training, missingness depends on the same week's outcome.**
   - `player_week_xfp` rows come from `tgt_xfp`/`carry_xfp` grouped by (player, week). They exist only for weeks
     with at least one target (with air yards) or one carry.
   - `021` joins on the exact week. So `xfp_l4` is NULL in a training row whenever the player had no opportunity
     in the labelled week (and in week 1).
   - That is post-game information carried by missingness, and LightGBM can use it.
   - Not quantified here, because counting those rows means reading same-week opportunity. The reviewer should
     measure it and fix it with a calendar-week spine (as `015a` does with `player_week_usage`) before B4 freezes
     anything that uses `xfp_l4`.
   - It also means the August XFP replay result (+2 tails, "positive alone") is not clean evidence.

### 1.4 Revisions check

**Where the archive is:**
- The licensed captures sit at `gs://nfl-predictions-503414-raw/licensed/fantasy-points/<report>/season=…/…/sha256=…/`.
  Each raw row records `archive_uri` and `source_sha256`.
- Daily BigQuery snapshots of every FP raw table are in `nfl_backups.<table>_YYYYMMDD`, 09-04 → 10-03.
- SIS has a dedicated revision baseline at `gs://…-raw/licensed/sis-revision-baseline/2026-w01-20260918T201025Z/`
  (README: "diff the protocol's fetch of week 1 against SHA256SUMS", OPEN-DEFECTS O-3b).

**What could be compared:**

| Check | Original | Compared with | Result |
|---|---|---|---|
| FP Route Share 2026 W2 (`revision_route_share_2026w2.csv`) | 09-21 02:53Z capture, sha `46b22b…`; BigQuery `nfl_raw.fantasy_points_route_share_bak_2026w2_20260923` | Current rows, 09-23 20:52Z capture, sha `1e5708…` | **Not a vendor revision.** The first capture was an unfinished vendor export (Sunday night), already in README (2026-09-23). Rows: 200 → 267; 0 keys dropped and 67 added (34 of them on 4 teams absent from the original). Of the 200 shared keys, 174 changed `route_share`; mean absolute change 0.49 on a 0–1 scale; correlation 0.18. 1 `gsis_id` resolution changed; no names, teams or positions changed. |
| FP Route Share and defense PROE history, 2022–25 | `nfl_backups.*_20260904` | Current `nfl_raw` | Row counts and per-season fingerprints are identical. Our copy is stable, but this cannot detect vendor revisions, because every pre-2026 row is one download (08-10 and 08-11-2026). |
| FP cumulative reports (advanced, coverage, alignment, route-shape, QB-shell) | — | — | Only one capture exists (target week 4, 09-30). Nothing to compare. |
| SIS 2026 W1, three team views (`revision_sis_2026w1_*.csv`) | 09-18 20:10Z baseline | BigQuery W1 rows (from the 09-21 03:07Z weeks 1–2 capture) | 32 / 32 rows, same keys. 35 fields, 1120 cells: 128 changed, all in 4 fields: `pdef_points_saved`, `_per_play`, `pdef_points_above_average`, `pdef_paa_per_play` (32 of 32 each). All counting totals and `pdef_boom_rate`/`bust_rate` (the SIS shadow's inputs) are unchanged. |

**A precise FP Data Suite revision test is not possible from what is stored:**
- No pre-2026 Data Suite week has a contemporaneous capture.
- No finished 2026 week has been captured twice.

**What would be needed:**
- Re-download, through the existing collectors with their archive step, **2026 W1 Route Share** (archived 09-17,
  sha `07642a…`) and **2026 W1–W2 defense PROE** (archived 09-23).
- Diff them by key and field against the archived objects.
- Do the same for **one 2025 season Route Share CSV**, against the hash-locked August export. README says those are
  kept under the ignored `fantasy-points/` directory of the production checkout, which this audit did not touch.
- The SIS pattern (a dated baseline plus SHA256SUMS) is the template.
- **For B4 itself:**
  - the 2026 W1 Route Share recapture tests in-season revisions;
  - the 2025 recapture tests whether the August history the panel trains on matches what FP serves now.

  Neither can show what FP served in real time in 2022–24. That limit should be stated in the preregistration.

## 2. D1 overlap map

### 2.1 Which fields each paid source actually feeds

The source is the subagent's code map plus my own spot checks:
- `deploy/deploy_jobs.sh:84`: `project-slate` sets no `EXTRA_FEATURES`.
- `scripts/ownership_fp.py:107-110`.
- `scripts/sunday_build_host.sh:294-344`.

| Source | Table / field read | Reader | Class | FP field that could replace it |
|---|---|---|---|---|
| Odds API | `nfl_raw.prop_lines` (6 markets: pass_yds, pass_tds, rush_yds, reception_yds, receptions, anytime_td; point, price, snapshot) → `market_points` | `models/prop_market.py:market_points`; `inference/run_projections.py` (0.55 market weight) | **Money path**: 55% of every projection | `fantasy_points_dfs_projections.fantasy_points` (DK slate) or `fantasy_points_weekly_projections.fantasy_points_draftkings`. FP serves **no stat-level lines or prices**: the weekly projection JSON has only fantasy-point totals by scoring system. |
| Odds API | `prop_lines` → frame `market_points`, the build audit's ≥0.30 coverage gate, unmatched fallback | lab `live_week.py`; `sunday_build_host.sh` `AUDIT_SOURCES` | **Money path** (gate) | the same FP DK projection |
| Odds API | `prop_lines` (player, market, AVG point/price by pull date) | `scripts/vet_book.py:76`, `player_score.py:126` | **Money path** (vetting flag: market vanished) | none clean; nearest is a player dropping out of FP dfs_projections between captures |
| Odds API | `odds_snapshots` (spreads/totals) | app, `status.py` | dashboard only. Model lines come from free nflverse `schedules`. | — |
| Odds API | `prop_lines_shadow`, `prop_lines_us_dfs` | writer only | **captured-only** | — |
| FP DFS | `fantasy_points_projected_ownership.projected_ownership_pct` (newest DK capture, ≤30 h old) | `scripts/ownership_fp.py`, `sunday_build_host.sh:305-314` (`UNION_MAIN_OWN_PREDICTOR=fp`, tilt 0.20) | **Money path** (Week-4 trial) | itself; also `dfs_projections.projected_ownership_pct` |
| FP DFS | `dfs_projections.fantasy_points`, `articles`, ownership | `score_o1.py`, `score_ownership_sources.py`, `score_article_mentions.py`, `score_projection_blend.py` | paper arms (A1, A3, B1/B2) | — |
| FP DFS | `weekly_projections`, `rankings_weekly`, `rankings_ros` | collector only | **captured-only** | — |
| FP Data Suite | `fantasy_points_route_share.route_share` → `fp_route_share_*` | `017k` → `023`/`021`; registries `tail_k1_route*` | **shadow gate** (`fp-route-share-2026`); not in `NUMERIC_FEATURES` | itself |
| FP Data Suite | defense_proe, advanced_*, alignment_*, coverage_*, qb_shell_*, route_shape_*, `*_matchup_weekly` | `analysis/*`, `research/*`, annotation scripts | research only; none reaches `023` | itself |
| SIS | `sis_team_context_game`, `sis_team_run_context_game` (pdef boom/bust, pressures, sacks → `sis_pass_*_l4`), copula and alignment tables | `inference/sis_pass_tail_shadow.py`, `tabpfn_sis_*` generators | **shadow gate** `sis-pass-tail-2026` (weeks 5–18; registry says it "decides the SIS renewal, not 2026 lineups"); never on the money path | Partial only: FP `line_matchup_weekly` (press %, sack-related, PRROE), `qb_coverage_matchup_weekly` (man %, FP/DB, coverage grade). FP has no boom/bust rate, no Points Saved or PAA, and no defender-level alignment coverage. |
| LineStar | local `~/weekN-sunday/linestar/linestar-own-*.csv` (own_proj) | `ownership_blend.py`, `ownership_tabpfn.py` | **Money-path fallback**, dead in Week 4 (the free feed caps at 60 rows; the capture refuses below 100) | `fantasy_points_projected_ownership.projected_ownership_pct` (already primary) |
| LineStar (backfill) | `nfl_raw.contest_ownership` 2022–25 realized `pct_drafted` | `scripts/ownership_sets.py` → `ownership_lag.csv` (the lag model; the FP scale reference; the 0.10 fallback; the sleeve source) | **Money path, indirectly** (training data) | **none.** FP ownership is a projection and starts in 2026 W4. DK standings imports supply 2026 realized ownership. |

### 2.2 Correlations where both sources exist

All figures are from `d1_overlap_correlations.csv`.
- **Join keys:**
  - for projections, the shared name normaliser (`ownership_blend.norm`) plus team;
  - otherwise `gsis_id`, through `player_ids.pfr_id` for snap counts, or team-week keys.
- **Pre-lock inputs only:** FP's W4 capture (newest), our W4 run at 10-03 15:12, and market points from
  `prop_market.market_points` (the newest pre-lock lines).

| Pair | Group | n | Pearson | Spearman |
|---|---|---|---|---|
| FP DK projection vs our served projection (45/55) | W4 main slate, skill | 335 | 0.979 | 0.950 |
| | QB / RB / WR / TE | 29 / 85 / 131 / 90 | 0.983 / 0.975 / 0.979 / 0.975 | 0.930 / 0.933 / 0.960 / 0.913 |
| | DST | 24 | 0.847 | 0.843 |
| FP DK projection vs Odds-API market-only DK points | skill with ≥2 prop markets | 179 | 0.974 | 0.974 |
| | QB / RB / WR / TE | 24 / 47 / 75 / 33 | 0.977 / 0.938 / 0.987 / 0.991 | 0.953 / 0.921 / 0.984 / 0.978 |
| Our served projection vs market-only (reference) | skill | 179 | 0.975 | 0.976 |
| FP Route Share vs nflverse offensive snap share (free) | 2026 WR / TE | 488 / 308 | 0.971 / 0.884 | 0.963 / 0.896 |
| | 2025 WR / TE / RB | 2736 / 1635 / 1753 | 0.969 / 0.902 / 0.896 | 0.965 / 0.911 / 0.904 |
| FP defense PROE vs nflverse `pass_oe` allowed (all plays) | team-week 2026 W1–3 / 2025 | 96 / 544 | 0.906 / 0.920 | 0.890 / 0.908 |
| … (neutral: downs 1–3, wp 0.2–0.8, >2 min left in half) | 2026 / 2025 | 96 / 544 | 0.775 / 0.696 | 0.754 / 0.713 |
| FP XFP per game (last four; receiving) vs our pbp `xfp_l4` | 2023–25 WR | 1348–1482 per season | 0.941–0.961 | 0.942–0.951 |
| | 2023–25 TE | 731–732 per season | 0.949–0.953 | 0.920–0.926 |
| FP defense pressure % vs SIS pressures / opponent dropbacks | team, 2026 W1–3 / 2025 season | 32 / 32 | 0.693 / 0.826 | 0.608 / 0.803 |
| FP offense pressure % allowed vs SIS pressures allowed / dropbacks | team, 2026 W1–3 / 2025 season | 32 / 32 | 0.596 / 0.813 | 0.649 / 0.786 |

**Reading the table:**
- **Projections:** at the DK-points level, FP is nearly collinear with both our projection and the market. Whether
  it adds anything is B1/B2's question (graded on outcomes), not D1's.
- **Route Share, PROE and XFP:** each has a free or home-built near-substitute at r ≥ 0.9. RB route share against
  snap share is the weakest at 0.90; TE is 0.88–0.90.
- **SIS vs FP pressure:** agreement is moderate. Over three 2026 weeks (about 3 games per team) it falls to
  0.60–0.69, which is expected from small samples.

**Not computable:**
- **SIS vs FP route participation and coverage:** SIS's BigQuery tables carry no player route or participation
  field and no man/zone rates. The overlapping SIS content is team-level pass defense, pass rush and blocking, plus
  defender-by-alignment coverage.
- **FP ownership vs LineStar or LAG:**
  - FP ownership starts in W4.
  - LineStar W4 is 60 rows, stored only under `~/week4-sunday`, which was out of bounds.
  - The LAG output lives in the week directories.
  - `nfl_predictions.own_shadow` has 2026 W1 only.
  - A1 covers this pairing from Monday.

## 3. Caveats and unknowns

- **W1/W2 live shares are reconstructions.** They are validated exactly on W3 and W4. If pbp or NGS for week 1 had
  not loaded by the 09-20 build, the W2 `separation_l4` and `proe_l4` would be lower than shown. W1 is structural.
- **W4 "live" is the 10-03 14:52 build.** Sunday's T-70 builds will replace it. Coverage could move slightly (for
  example, injury-driven pool changes).
- **The panel population is wider than the live projected pool**, because it includes listed-inactive rows since
  2022. Compare the shares through the `target_share_l4` reference row or the conditional ratios in 1.2.
- **Why the 2026 Route Share captures are WR/TE-only was not determined.** Possibly a filter on the vendor page or
  the download. The 2025 history has all four positions.
- **The D1 correlations are pre-lock agreement between sources, not accuracy.** They say nothing about which source
  is right.
- **D1 projection correlations are one week (W4) and one slate.** Market-only points cover the 179 skill players
  with at least two prop markets.
- **Our offense and defense mapping for the FP line-matchup table follows the ingest code:** "Defense Stats" columns
  describe the opponent's defense. Joining them to the team itself instead gives r = 0.18 / −0.06, a reminder for
  anyone who uses that table.
- **FP DK projections cover only W4.** They were first captured 10-02.
- **Not determined:** the `fantasy_points_betting_projections` collector target (no BigQuery table exists); any FP
  Bell Cow or weighted-opportunity export (none in BigQuery or in the GCS archive listing).

## 4. Query logic

- **Live build times:** from `INFORMATION_SCHEMA.JOBS_BY_PROJECT`, successful CTAS jobs whose destination is
  `nfl_features.player_week_inference`. These are matched to the final `player_projections.generated_at` per week.
- **Coverage:** `COUNTIF(col IS NOT NULL)/COUNT(*)` over skill positions.
  - **W3 live:** the table `FOR SYSTEM_TIME AS OF 2026-09-27 16:00 UTC`.
  - **W4 live:** the current table.
  - **Projected pool:** `gsis_id IN` the final run's ids.
  - **Panel:** `player_week_training`, seasons 2019 and 2021–25, grouped by season (all weeks, weeks 1–4, weeks
    3–4) and by season-week for weeks 1–4.
- **W1/W2 reconstruction:** the as-of joins described in 1.1, applied to the projected pool.
  - The fp_route rebuild reproduces `017k` (latest 4 strictly prior player-weeks, any season; last, mean, and
    last-minus-previous), restricted to raw rows with `ingested_at` ≤ the build timestamp.
- **xfp lag check:**
  - Recompute per-game xfp for 2026 from `nfl_raw.pbp`, with 017j's 2014–18 bucket rates.
  - The training definition = the mean of the player's latest ≤4 game-rows with week < W.
  - Compare it with the live `xfp_l4` (counts, mean absolute gap, correlation).
- **Route Share revision:** full outer join of the backup table and current W2 rows on
  (normalized_name, vendor_team, vendor_pos) — no duplicate keys on either side — then per-field inequality counts.
- **History stability:** per-season `BIT_XOR(FARM_FINGERPRINT(key|week|value))` and row counts, `nfl_backups.*_20260904`
  vs `nfl_raw`.
- **SIS revision:**
  - Parse the baseline CSVs with the ingest's own `SCHEMAS` and `_number`.
  - Join to BigQuery W1 on (team_name, opp_name, season, week).
  - Count cells differing beyond 1e-6.
  - The CSVs were copied to scratch and deleted after the comparison.
- **D1 correlations:** pandas Pearson and Spearman on complete pairs.
  - FP DK projection: main slate 154078, DraftKings, newest `retrieved_at`.
  - Ours: `player_projections` at 2026-10-03 15:12:36.
  - Market: `prop_market.market_points(seasons=(2026,), minimum_markets=2)`, imported from the repo at
    `61cd4962`.
  - Snap share: `snap_counts.offense_pct`, joined through `player_ids.pfr_id`.
  - FP defense PROE vs mean `pbp.pass_oe` by (season, week, defteam), regular season.
  - FP line-matchup press % at target week 1 (source: 2025 season) and target week 4 (source: 2026 W1–3), against
    SIS sums over the same window: defense pressures / the opponent's dropbacks, and offense pressures allowed /
    own dropbacks.
  - FP XFP per game = `fp_adv_rec_xfp_per_route × routes / games` (window `last_four`), joined to the training rows
    at (season, target_week).
