# Week 3 (2026) post-mortem: did the Fantasy Points / SIS data point to better picks?

Slate: DraftKings main Sunday, draft group 153769, games 2026-09-27, lock 17:00 UTC.
Ground truth: `players.csv` (671 DK rows; `fpts` known for 394; 161 skill players with
`fpts` known and `proj > 5`: 68 WR, 41 RB, 26 QB, 26 TE). Everything below is read-only
warehouse evidence (project `nfl-predictions-503414`) joined to that file. No code, tables
or commits were changed. Supporting files written next to this report:
`vendor_signals_merged.csv` (the joined frame) and `vendor_signals_spearman.csv` (every
correlation computed).

## Short answer

1. **The served projection used none of the vendor data.** The only vendor column that
   reaches the feature tables is Fantasy Points route share (`fp_route_share_last/l4/jump/
   cross_season`), and those four are `CANDIDATE_FEATURES` that enter the model only when
   `EXTRA_FEATURES` names them. The production jobs (`train-weekly`, `train-weekly-k1`,
   `project-slate` = `MODEL_REGISTRY_VARIANT=tail_k1`, `BLEND_MODEL_WEIGHT=0.45`) set no
   `EXTRA_FEATURES`. No SIS table is referenced anywhere in `sql/features` or
   `sql/predictions`. The FP weekly matchup reports and defense-PROE feed only
   `sql/research/017l-017s` and shadow tables. So "hardly used" is exact: not used.
2. **Most of the vendor warehouse has no 2026 data at all.** 14 of the 22 `fantasy_points_*`
   / `sis_*` tables hold 2022-2025 rows only and were last written in mid-August. Seven tables
   carry 2026 rows, all captured 3-6 days before lock (no post-lock leakage). Even the three
   "Week 3 matchup" tables are built on the vendor's **2025 full-season** player stats
   (`source_season=2025`, `source_regime=vendor-prior-season-early`, `games=17` for veterans);
   the only genuinely in-season 2026 vendor numbers are route share (weeks 1-2), defense PROE
   (weeks 1-2) and the two SIS team-game context tables (weeks 1-2).
3. **Within this slate the vendor signals carried weak, borderline signal against our
   projection error, nothing that would have changed the heavy picks.** Of 110 vendor
   columns tested on all 161 players, 14 have a partial correlation with `fpts` (controlling
   for `proj`) at p < 0.05 (5.5 expected by chance) and **none survives a multiplicity
   correction**. The best individual signals reach partial rho ~ +0.29 (n = 86 WR/TE): the
   vendor's *2025* per-route production (`matchup__exp_fp_per_rte`, `matchup__fp_per_rr`,
   `cover_6__yprr`) and a route-share regression term (`fprs_delta`, rho -0.28: receivers
   whose route share **rose** most from W1 to W2 under-shot projection by 1.3 points; those
   whose share fell most beat it by +4.5). SIS's opponent pass-defence bust rate (`sis_opp_
   pdef_bust_rate`) is the one team-level signal with a consistent sign (ALL +0.21, WR/TE
   +0.26, QB +0.48 at n = 26).
4. **On the specific busts and misses the vendor data was not a guide.** It was *favourable*
   on Amon-Ra St. Brown (8 of 16 signals in the top quintile, 1 warning; he scored 11.9),
   Jameson Williams (6 green / 1 warning; 8.9) and Jonathan Taylor (2 green / 2 warnings;
   9.2). It was *against* two of the biggest scorers we did not roster: Jordan Addison (5
   warnings, 0 green; 20.0) and Jeremiyah Love (6 warnings; 21.9). It did carry negative
   readings on De'Von Achane (5 warnings: SIS 2026 has Miami's blocking PAA worst on the
   slate; he scored 1.7), Breece Hall (6 warnings; 8.5), Ashton Jeanty (6 warnings; 12.3)
   and Hunter Henry (4 warnings; 1.5), and it was favourable on Sam Darnold (3 green, 0
   warnings; 32.7) and Joe Burrow (5 green; 23.6). Across all 161 players the share of
   warning signals is the same for busts as for everyone else (0.214 vs 0.206).
   Side finding: the frame's own opponent-defence columns `wr/rb/te/qb_fp_allowed_adj_l6`
   are NULL for every one of the 161 skill players in `players.csv` this week (they are not
   model inputs, so no projection impact, but the operator's requested baseline comparison
   against them is impossible).
5. **The market was a better pointer than the vendor tables on the two outright misses**,
   and no worse than us elsewhere: props had Darnold 2.0 points above us and Brock Bowers
   3.0 above us; on the 47 busts we were above the market by only +0.31 on average
   (population +0.25), so "we were high versus the market" does not explain the busts
   (Spearman(proj - market, residual) = -0.08, p = 0.32). Prop-line movement between
   Wednesday and Sunday was tiny (|move| < 1 DK point for almost everyone) and uncorrelated
   with outcomes (rho = 0.01).

## 1. Inventory (what exists, what has Week-3 rows, when it was captured)

Lock was 2026-09-27 17:00 UTC. "W3-usable" means rows that existed before lock and describe
weeks < 3 or the Week-3 matchup.

### 1a. Tables WITH 2026 rows (all captured pre-lock)

| table | 2026 rows | keyed by | W3-usable content | captured (UTC) |
|---|---|---|---|---|
| `fantasy_points_wr_coverage_matchup_weekly` | target_week 1/2/3, 284 rows each (W3: 187 WR + 97 TE; 258 resolved to gsis_id, 26 unresolved) | gsis_id / vendor_name / normalized_name + team, opponent | per-route stats vs this week's opponent coverage mix: `matchup__rte`, `rte_per_g`, `fp_per_rr`, `exp_fp_per_rte`, `cov_grade`, `yprr`; man / cover-2/3/4/6 splits. **All from 2025 (`source_season=2025`, regime `vendor-prior-season-early`)** | 09-23 23:08 (source_retrieved_at), ingested 23:09; `first_kickoff_utc` 09-25 00:15 |
| `fantasy_points_qb_coverage_matchup_weekly` | 61 rows per target week (W3: 58 resolved) | gsis_id / name + team, opponent | `matchup__db`, `fp_per_db`, `exp_fp_per_db`, `cov_grade`, coverage splits. 2025-based | 09-23 23:08 |
| `fantasy_points_line_matchup_weekly` | 32 team rows per target week | team, opponent | own OL `offense__rush_grade/pass_grade/adj_ybc_per_att/press_pct/prroe`, own DL `defense__press_pct/prroe/adj_ybc_per_att/ybco`. 2025-based (`games=17`) | 09-23 23:08 |
| `fantasy_points_route_share` | week 1: 265 rows (file `target-week-02`, retrieved 09-17 17:29); week 2: 267 rows (file `target-week-03`, retrieved 09-23 20:52) | gsis_id (531/532 resolved), normalized_name, canonical_teams; WR/TE only | `route_share` in [0,1] per player-week. **True 2026 data** | 09-17 and 09-23 |
| `fantasy_points_defense_proe` | weeks 1-2, 32 rows each | team, week | `defense_proe` = pass rate over expected faced by that defence. True 2026 | run ids 09-23 23:02 / 23:04 (`ingested_at` NULL) |
| `sis_team_context_game` | weeks 1-2, 32 rows each | team, opp, week (game_key) | pass defence `pdef_*` (EPA, PAA, positive/boom/bust rates), pass rush `prush_*`, blocking `block_*`. True 2026 | 09-21 03:07 (34 rows) and 09-23 21:48 (30 rows) |
| `sis_team_run_context_game` | weeks 1-2, 32 rows each | team, opp, week | passing totals, rushing `rush_*` (PAA, EPA, YAC, boom/bust, stuffs), run defence `rdef_*`. True 2026 | same as above |

`fantasy_points_route_share_bak_2026w2_20260923` (200 rows, 09-21) is a superseded backup of
the first W2 load.

### 1b. Tables with NO 2026 rows (nothing collected this season; finding, not failure)

All last modified 2026-08-10 to 08-15; seasons 2022-2025 only:
`fantasy_points_advanced_passing_l4` (2,879), `fantasy_points_advanced_prior` (3,771),
`fantasy_points_advanced_receiving_windows` (34,227), `fantasy_points_alignment_player_l4`
(16,482), `fantasy_points_alignment_team_l4` (1,792), `fantasy_points_defense_coverage_l4`
(1,792), `fantasy_points_defense_coverage_prior` (128), `fantasy_points_qb_shell_l4` (1,792),
`fantasy_points_receiver_coverage_l4` (16,482), `fantasy_points_receiver_coverage_prior`
(2,093), `fantasy_points_route_shape_l4` (16,482), `sis_alignment_attempt_game` (4,077),
`sis_receiver_copula_defense_prior` (3,324), `sis_receiver_copula_player_game` (15,477).

The SIS research caches in `nfl_features` (`tabpfn_sis_pass_tail_*`, `sis_qb_line_*`,
`sis_rb_rdef_*`, `sis_rb_runtail_*`, 52,307 rows each) were last written 2026-08-13/14 and
therefore hold no 2026 rows; the "live" tables named in `sis_pass_tail_shadow.py`
(`tabpfn_sis_pass_tail_live_control_v1` / `_treatment_v1`) exist in no dataset.

### 1c. Market tables

| table | W3 content | timing |
|---|---|---|
| `prop_lines` | 2 books (DraftKings, FanDuel), 6 markets: anytime TD (519 players), reception yds (189), receptions (187), rush yds (94), pass yds (32), pass TDs (32); keyed by player **name string**, no gsis_id | 5 daily pulls 09-23 14:32 to 09-27 14:33 UTC; last pre-lock pull ~2.5 h before lock |
| `prop_lines_shadow` | extra markets (rush attempts, rush+rec yds, completions, attempts, INTs, pass+rush yds), 30-55 players each | same cadence |
| `prop_lines_us_dfs` | PrizePicks / Underdog / Pick6 lines (rec yds ~175 players, receptions, rush yds, pass yds, pass TDs) | 09-23 15:34 to 09-27 16:32 UTC (28 min before lock) |
| `odds_snapshots` | Total / Spread / Moneyline, 32 events (W3 + W4), 10 pulls | 09-23 14:04 to 09-27 20:02; last pre-lock 14:02 |
| `odds_movement` | a VIEW over `odds_snapshots` (metadata `numRows=0` is not a finding) | - |

DST: no vendor table has defence-scoring rows. Three of our five heaviest exposures were DSTs
that busted (Titans 51 rows -> 7.0, Bengals 47 -> 3.0, Seahawks 17 -> 2.0); nothing in FP/SIS
speaks to them.

## 2. Join and correlation results

Join rates (players with `proj > 5`): WR-coverage matchup 86/94 WR+TE (unmatched: Joshua
Palmer, Malachi Fields, Denzel Boston, Germie Bernard, KC Concepcion Jr., Carnell Tate, Kenyon
Sadiq, Ted Hurst III - mostly 2026 rookies absent from a 2025-based report); QB matchup 25/26
(Deshaun Watson unmatched); route share 91/94 (Palmer, Jalen Tolbert, **Brock Bowers**
absent, i.e. no W1-W2 routes); line / SIS team tables 100% by team and opponent; props
161/161 (my props-implied points correlate 0.989 with the frame's `market_points`).

Population: 161 skill players with `fpts` known and `proj > 5`. `residual = fpts - proj`.
Partial rho = Spearman of signal with `fpts` after removing `proj` from both (rank-based).

### 2a. Baselines (what the model / market already had)

| group | signal | n | rho vs fpts | rho vs residual | partial rho (ctrl proj) | p |
|---|---|---|---|---|---|---|
| ALL | **proj** | 161 | **0.575** | - | - | - |
| ALL | market_points | 152 | 0.544 | -0.020 | 0.114 | 0.16 |
| ALL | props_pts_close (my rebuild) | 161 | 0.579 | 0.015 | 0.105 | 0.19 |
| ALL | dk_salary | 161 | 0.470 | 0.019 | 0.023 | 0.77 |
| ALL | dk_ppg | 159 | 0.400 | -0.051 | -0.049 | 0.54 |
| ALL | snap_share_l4 | 159 | 0.359 | 0.007 | 0.040 | 0.61 |
| ALL | xfp_l4 | 133 | 0.186 | -0.062 | -0.085 | 0.33 |
| ALL | target_share_l4 | 159 | -0.075 | -0.070 | -0.106 | 0.18 |
| ALL | oprk_n (DK opp rank; low = tough) | 161 | -0.088 | -0.100 | -0.077 | 0.33 |
| ALL | props_pts_move (Wed->Sun) | 161 | 0.012 | 0.007 | -0.014 | 0.87 |
| WR/TE | proj | 94 | 0.403 | - | - | - |
| WR/TE | fp_route_share_l4 (in frame, not in model) | 94 | 0.361 | 0.091 | 0.163 | 0.12 |
| WR/TE | target_share_l4 | 92 | 0.187 | -0.157 | -0.194 | 0.06 |
| any | `wr/rb/te/qb_fp_allowed_adj_l6` (DK-points-allowed by opponent defence) | 0 | **NULL for all 161 skill rows in players.csv** - not comparable; these columns are built in `sql/features/017_defense_week_allowed.sql`, are not in `NUMERIC_FEATURES`, and carried nothing this week | | | |
| RB | proj | 41 | 0.676 | - | - | - |
| RB | market_points | 38 | 0.691 | 0.099 | 0.169 | 0.31 |
| QB | proj | 26 | 0.172 | - | - | - |
| QB | props_pts_move | 26 | 0.337 | 0.311 | 0.317 | 0.11 |

(Full table for every baseline and vendor column with at least 10 non-null values:
`vendor_signals_spearman.csv`; the all-null `*_fp_allowed_adj_l6` columns are absent from it.)
Note the QB projection ordered this week's 26 QBs at rho 0.17 only; every downstream QB
result below has n = 26 and a noise floor of about +/-0.20 per correlation.

### 2b. Vendor signals: how many "hits" and how many are expected

| group | vendor columns tested | partial p < 0.05 | expected by chance | p < 0.01 | survive Bonferroni |
|---|---|---|---|---|---|
| ALL | 110 | 14 | 5.5 | 5 | 0 |
| WR/TE | 85 | 11 | 4.2 | 4 | 0 |
| RB | 50 | 0 | 2.5 | 0 | 0 |
| QB | 75 | 4 | 3.8 | 0 | 0 |

Because the vendor columns are heavily inter-correlated (five WR/TE columns are the same
2025 per-route efficiency under different coverage labels), the naive 5% expectation
understates the null spread. A permutation null (residuals shuffled across players within
group, `proj` kept attached, 400 replicates) gives: ALL - null mean 6.0 hits, sd 3.6, 95th
percentile 13, observed 14, **P(null >= observed) = 0.048**; WR/TE - null mean 4.7, sd 3.0,
95th pct 11, observed 12 (this script counts p <= 0.05; the table above counts p < 0.05 and
gets 11 - the `fpol_offense__prroe` row sits at exactly 0.050), **P = 0.037**; RB -
observed 0 vs null mean 2.4; QB - observed 5 vs null mean 4.0, P = 0.36. So the hit count is
marginally above chance, and the excess is entirely the WR/TE per-route-efficiency cluster.

### 2c. The strongest vendor signals (partial p < 0.05; |rho| > 0.15 vs residual)

| group | signal | n | rho vs fpts | rho vs residual | partial rho | p |
|---|---|---|---|---|---|---|
| WR/TE | `fpwr_cover_6__yprr` (2025 YPRR vs cover-6) | 82 | 0.347 | 0.253 | 0.304 | 0.006 |
| WR/TE | `fpwr_matchup__exp_fp_per_rte` (2025 FP/route x this week's coverage mix) | 86 | 0.431 | 0.224 | 0.288 | 0.007 |
| WR/TE | `fpwr_matchup__fp_per_rr` (2025 FP per route) | 86 | 0.431 | 0.218 | 0.283 | 0.008 |
| WR/TE | `fprs_delta` (route share W2 minus W1) | 89 | -0.303 | -0.260 | -0.277 | 0.008 |
| WR/TE | `sis_opp_pdef_bust_rate` (opp pass-D bust rate, W1-2) | 94 | 0.250 | 0.250 | 0.260 | 0.011 |
| WR/TE | `fpwr_matchup__rte_per_g` (2025 routes per game) | 86 | 0.411 | 0.155 | 0.242 | 0.025 |
| WR/TE | `fpwr_cover_4__rte_pct`, `cover_4__fp_per_rte`, `cover_6__fp_per_rte`, `matchup__yprr` | 86 | 0.20-0.38 | 0.14-0.24 | 0.21-0.22 | 0.04-0.05 |
| WR/TE | `sis_opp_prush_paa_per_play` (opp pass-rush PAA) | 94 | 0.217 | 0.201 | 0.206 | 0.046 |
| ALL | `sis_opp_pdef_bust_rate` | 161 | 0.167 | 0.239 | 0.214 | 0.006 |
| ALL | `fpol_offense__pass_grade` (own OL pass grade, 2025) | 161 | 0.168 | 0.216 | 0.188 | 0.017 |
| ALL | `fpol_offense__prroe` (own OL pressure rate over expected, 2025) | 161 | -0.147 | -0.189 | -0.169 | 0.032 |
| ALL | `sis_own_rush_bust_rate` (own rushing bust rate, W1-2) | 161 | -0.192 | -0.172 | -0.162 | 0.040 |
| ALL | `fpdl_opp_defense__press_pct` (opp DL pressure %, 2025) | 161 | -0.109 | -0.161 | -0.158 | 0.045 |
| QB | `sis_opp_pdef_bust_rate` | 26 | 0.477 | 0.468 | 0.483 | 0.012 |
| QB | `fpdl_opp_defense__press_pct` | 26 | -0.439 | -0.382 | -0.463 | 0.017 |
| QB | `fpdl_opp_defense__ybco` | 26 | 0.371 | 0.469 | 0.433 | 0.027 |
| QB | `sis_opp_prush_pressures` (sign is the *wrong* way: more pressures faced, more points) | 26 | 0.381 | 0.325 | 0.393 | 0.047 |
| RB | (nothing at p < 0.05; best: `sis_opp_rdef_boom_rate` -0.32 vs residual, p = 0.052; `sis_own_rush_bust_rate` -0.33, p = 0.17) | 41 | | | | |

Reading: the WR/TE hits are almost all the same thing measured five ways - the vendor's
**2025 per-route production** (`fp_per_rr`, `exp_fp_per_rte`, `yprr` by coverage). Within
this slate, receivers who were efficient per route last season beat our projection more
often than those who were not; the model's own `fp_route_share_l4` (partial 0.16) and
`target_share_l4` (partial -0.19) point the other way, i.e. it is volume, not efficiency,
that the frame carries. The `fprs_delta` result is a regression-to-the-mean pattern in the
vendor's own 2026 route share:

| W1->W2 route-share change quartile (WR/TE, n=89) | mean delta | mean proj | mean fpts | mean residual |
|---|---|---|---|---|
| fell most | -0.17 | 9.27 | 13.75 | **+4.48** |
| fell | -0.03 | 11.68 | 10.49 | -1.19 |
| rose | +0.05 | 10.18 | 11.27 | +1.09 |
| rose most | +0.23 | 8.29 | 6.97 | **-1.33** |

The candidate feature `fp_route_share_jump` is exactly this quantity; it is registered but not
in the live model. One week, one slate: this is a hypothesis for a preregistered test, not a
finding.

### 2d. In-sample upper bound (fit on this week's outcomes - NOT a forecast test)

Refitting `fpts ~ proj + signal` on the same 86-94 receivers raises Spearman(adjusted, fpts)
from 0.41 to 0.45-0.48 (R^2 0.19 -> 0.24). Even with that hindsight fit the re-ranking of our
actual decisions is small: St. Brown stays #1-2 of 94 under every signal; Jefferson moves
7 -> 12, McMillan 12 -> 18, Schultz 18 -> 26; Bowers 58 -> 44 (still nowhere near
rosterable); Addison gets *worse* (44 -> 71) under `exp_fp_per_rte` and better only under the
cover-6 YPRR fit (42 -> 8). The QB fit on `sis_opp_pdef_bust_rate` (n = 26) promotes Darnold
23 -> 10 and Burrow 11 -> 1 but also promotes Drake Maye (scored 6.8) to #8.

## 3. Heavily rostered busts and un-rostered top scorers, signal by signal

Percentiles are of the signal within the same position family on the slate (proj > 5),
oriented so that **low = unfavourable for the player**; "warn" = at or below the 20th
percentile, "green" = at or above the 80th. Full per-signal values for all 47 busts, 2 misses
and 7 near-misses: `vendor_signals_merged.csv` (columns `fpwr_*`, `fpqb_*`, `fpol_*`,
`fpdl_opp_*`, `fprs_*`, `fp_opp_def_proe_*`, `sis_own_*`, `sis_opp_*`).

Base rates across all 161: mean warning share 0.206 (median 0.188), green share 0.180.
Busts: warning share 0.214, green share 0.145. Misses (n = 2): 0.000 / 0.143.
Spearman(warning share, residual) = -0.10; Spearman(green share, residual) = +0.21 (n = 161).
The direction map was set from the signal definitions, but after the individual
correlations had already been seen, so that composite is not a clean test.

### 3a. Busts (our_rows >= 5 and fpts < 15; 47 skill players + 3 DSTs)

| player | rows | proj / market / props | fpts | vendor read (warn / green of n) | what it said |
|---|---|---|---|---|---|
| Jonathan Taylor RB IND @HOU | 31 | 18.6 / 17.1 / 16.9 (props moved +0.6) | 9.2 | 2 / 2 of 17 | IND run-block blown rate 18th pct and HOU YAC allowed 16th (warn); IND block PAA 82nd, HOU run-D positive rate favourable 96th. No verdict. We were +1.5 over the market. |
| Amon-Ra St. Brown WR DET @NYJ | 31 | 20.6 / 19.2 / 18.5 | 11.9 | 1 / 8 of 16 | Route share 95.5% (91st), 2025 exp FP/route 0.59 (87th), YPRR 2.69 (88th), NYJ pass-D bust rate 95th, DET OL pass grade 89th. **Vendor said play him.** Only warning: NYJ pass-D EPA/play had been good (14th). We were +2.1 over props. |
| Parker Washington WR JAX vs NE | 30 | 14.8 / 13.2 / 14.1 (props +1.1, biggest up-move among busts) | 13.0 | 1 / 3 | Route share 87% (81st) and rising (+0.25, 89th). Scored near projection; not a signal failure. |
| Ashton Jeanty RB LV @NO | 25 | 17.5 / 16.6 / 15.9 | 12.3 | 6 / 5 of 17 | LV OL 2025 rush grade 0.94 = worst on slate (1st pct), adj YBC 4th; LV 2026 rushing EPA/att 11th; NO run-D positive rate 1st. But NO run-D PAA/EPA allowed 99th/89th. Internally contradictory; we were +1.6 over props. |
| Travis Kelce TE KC @MIA | 24 | 11.7 / 12.6 / 12.2 | 13.9 | 3 / 4 | Beat projection (+2.2); listed only because < 15. |
| De'Von Achane RB MIA vs KC | 23 | 15.7 / 15.5 / 15.1 | 1.7 | 5 / 2 of 17 | **SIS 2026: MIA blocking PAA/play -0.065 = worst on slate (1st pct), MIA rushing PAA 13th, rush bust rate 18th; KC run-D bust rate 0 (5th), missed-tackle rate 0 (4th).** 2025 FP line data said the opposite (MIA OL adj YBC 82nd). The 2026 SIS team numbers were a real warning; market and projection agreed with each other. |
| Dalton Schultz TE HOU @IND | 22 (27% owned) | 12.3 / 12.4 / 12.4 | 6.0 | 3 / 1 | IND pass-D bust rate 9th, positive rate 9th, IND DL pressure 14th (warn); IND EPA/play allowed 91st (green). Mixed. |
| Jameson Williams WR DET @NYJ | 22 | 13.9 / 11.6 / 11.4 (props -0.4) | 8.9 | 1 / 6 | Route share 93% (89th), routes/g 83rd, NYJ bust rate 95th, DET OL 89th. **Vendor said play; the market said we were +2.3 too high** (largest proj-over-market among the heavy busts). |
| Tetairoa McMillan WR CAR @CLE | 21 | 13.5 / 13.0 / 12.9 | 3.7 | 1 / 2 | CAR OL 2025 pass grade -1.54 = 5th pct (warn); CLE DL pressure low (95th, green); route share 90% (86th). No verdict. |
| Hunter Henry TE NE @JAX | 20 | 9.7 / 9.6 / 9.5 | 1.5 | 4 / 2 | FP coverage grade -7.9 (9th), JAX PROE faced 10th (teams throw less than expected vs JAX), NE OL pressure allowed 6th, NE pressure rate 12th. Mild warning; route-share delta +0.25 (90th) said the opposite. |
| Justin Jefferson WR MIN @TB | 14 | 16.4 / 15.1 / 15.2 | 5.2 | 2 / 1 | TB DL pressure 44.3% = highest on slate (2nd pct), TB pass-D positive rate 19th (warn); route share 95.8% (93rd). We were +1.3 over market. |
| Breece Hall RB NYJ @DET | 13 | 15.2 / 15.3 / 14.7 | 8.5 | 6 / 4 of 17 | SIS 2026: NYJ rush bust rate 7th, EPA/att 7th, run-block blown rate 2nd; DET run-D boom rate 2nd, YAC allowed 2nd. 2025 FP line said NYJ OL 85th-88th. **2026 SIS was a warning; 2025 FP was not.** |
| Drake Maye QB NE @JAX | 6 | 18.2 / 18.9 / 19.0 | 6.8 | 4 / 3 of 14 | Coverage grade -6.9 (13th), JAX PROE 10th, NE OL pressure 6th, NE pressure rate 13th; 2025 FP/dropback 90th. Market was above us. |
| Others (35) | 5-18 | | | | see csv; none has more than 8 of 16 warnings, none has zero warnings and zero greens |

DST busts (Titans 51 rows -> 7.0, Bengals 47 -> 3.0, Seahawks 17 -> 2.0): no vendor coverage.

### 3b. Misses (fpts >= 25 and our_rows == 0) and near-misses (fpts >= 20, our_rows <= 2)

| player | rows | proj / market / props | fpts | vendor read | what it said |
|---|---|---|---|---|---|
| Sam Darnold QB SEA @WAS | 0 (2.2% owned) | 14.2 / 15.5 / 16.2 | 32.7 | 0 warn / 3 green of 14 | WAS PROE faced +0.112 = 98th (teams throw far more than expected vs WAS), WAS pass-D bust rate 87th, SEA OL pressure allowed 31.6% (94th). 2025 FP coverage grade neutral (-2.2, 29th). Spread moved SEA -7 -> -8.5. **Vendor and market both leaned his way; the market had him 2.0 above us.** Rank by proj 44 of 161, by market 36, actual 3. |
| Brock Bowers TE LV @NO | 0 (0.7%) | 8.1 / 11.1 / 11.1 | 30.6 | 0 / 1 of 14 | Absent from the 2026 route-share table (no W1-W2 routes recorded); all matchup values are 2025 and mid-pack (exp FP/route 52nd, coverage grade 43rd). **Nothing in the vendor data flagged him; the market had him 3.0 above us** (proj 8.1 on a $6,600 TE is an availability/usage-history artefact, not a matchup read). |
| Joe Burrow QB CIN @PIT | 2 | 18.1 / 17.4 / 17.4 | 23.6 | 2 / 5 | Coverage grade 9.9 (87th), PIT pass-D bust rate 98th, CIN OL 83rd, CIN pressure rate 90th; PIT EPA/play allowed 2nd and PROE faced 6th (warn). Favourable on balance. |
| Kirk Cousins QB LV @NO | 1 | 14.3 / 14.7 / 14.9 | 22.2 | 2 / 1 | 2025 FP/dropback 10th and exp 6th (warn); NO PROE 87th (green). Against. |
| Jeremiyah Love RB ARI @SF | 2 | 10.1 / 10.4 / 10.2 | 21.9 | 6 / 2 of 17 | ARI rushing PAA 17th, blocking PAA 7th, run-block blown 10th, SF YAC allowed 12th, SF missed tackles 10th, SF PROE 2nd. **Vendor was against him.** |
| Marcus Mariota QB WAS vs SEA | 1 | 12.9 / 11.9 / 12.2 | 20.4 | 3 / 2 | Mixed. |
| Jordan Addison WR MIN @TB | 0 | 9.1 / 8.4 / 8.3 | 20.0 | 5 / 1 of 16 | FP coverage grade -17.7 = 3rd pct, 2025 exp FP/route 8th, FP/route 16th, TB DL pressure 2nd, TB pass-D positive rate 19th. **Vendor was against him**; only route share (87.5%, 85th) was green. |

## 4. Market check on the same players

- Population (n = 152 with `market_points`): mean `proj - market_points` = +0.25 (median
  +0.27); 55% of players above market. Busts (n = 47): +0.31 / +0.39; 60% above market.
  Misses (n = 2): -2.16, both below market. Spearman(`proj - market`, residual) = -0.08
  (p = 0.32): being above the market did not predict busting this week.
- `market_points` and `proj` rank actuals equally (0.544 vs 0.537 on the same 152).
  Ranking by market instead of proj would have moved Darnold 44 -> 36 and Bowers 115 -> 73
  of 161 - both still far outside roster range - while moving Jameson Williams 47 -> 68,
  Jefferson 29 -> 42, Taylor 15 -> 22 and Egbuka 50 -> 71 (busts) but also Chase Brown
  41 -> 31 and Jalen Coker 84 -> 48 (busts we would have liked more).
- Where we were clearly above props on a heavy bust: Jameson Williams +2.5, St. Brown +2.1,
  Taylor +1.7, Jeanty +1.6, Jefferson +1.2. Where the market was above us on a miss:
  Bowers +3.0, Darnold +2.0.
- Prop-line movement Wednesday -> Sunday (DK/FD median): almost nothing moved by a full DK
  point; the largest among busts was Parker Washington +1.1 (toward us) and Jameson
  Williams -0.4 (away). Spearman(move, residual) = 0.01 overall, 0.32 among QBs (n = 26,
  p = 0.11). Game lines: KC -11.5 -> -9.5 at MIA (total 46.5 -> 45.5), HOU -3 -> -1.5 at IND,
  SEA -7 -> -8.5 at WAS, TEN-NYG total 39.5 -> 37.5, NYJ-DET total 47.5 -> 48.5. None is
  large enough to have changed a roster.
- Cross-book dispersion (largest DK-vs-FD closing-line gap per player, yards or receptions):
  population median 1.0 (mean 1.21), busts median 1.0 (1.17), the two misses median 2.0
  (1.86). Spearman(gap, residual) = 0.04 (p = 0.63). Spearman(|line move|, |residual|) =
  -0.14 (p = 0.08) - if anything, players whose lines moved more were projected *better*.
  Neither the dispersion nor the movement captured this week carried a usable read.
  PrizePicks / Underdog / Pick6 lines (`prop_lines_us_dfs`, last pull 28 min before lock)
  were captured but not tested here.

## 5. Code trace: which vendor columns reach the live projection

Worktree `/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921`
(HEAD 8a545d64, branch `production/week3-integration-20260921`).

- **Feature SQL.** The only `${raw}.fantasy_points_*` / `sis_*` reference in `sql/features`
  is `sql/features/017k_fantasy_points_route.sql` -> `${features}.player_week_fp_route`
  (`fp_route_share_last`, `fp_route_share_l4`, `fp_route_share_jump`, `fp_route_cross_
  season`, `fp_route_prior_observations`, `fp_route_fallback`; strictly prior weeks only).
  It is LEFT JOINed into `021_player_week_training.sql` (line 196) and
  `023_player_week_inference.sql` (line 205). No SIS table is referenced in `sql/features`
  or `sql/predictions`; outside `sql/research` the only `sis_` SQL is
  `sql/audits/sis_run_tail_prerequisite.sql`. The FP weekly matchup tables and
  `fantasy_points_defense_proe` are loaded by `sql/raw/010_fantasy_points_matchups_weekly.sql`
  and consumed only by `sql/research/017l-017s_*_pit.sql` and
  `sql/research/fp_matchup_shadow_tables.sql`.
- **Model feature list** (`src/nfl_dfs/models/featureset.py`): `NUMERIC_FEATURES` contains no
  vendor column. The four `fp_route_share_*` columns sit in `CANDIDATE_FEATURES` and enter
  `build_X` only when named in `EXTRA_FEATURES` ("Research-only unless the exact four-feature
  component protocol passes"). `xfp_l4` ("FantasyPoints lineage" in the comment) is computed
  from nflverse play-by-play bucket rates, not from a vendor table, and is also a candidate,
  not live.
- **Production jobs** (`deploy/deploy_jobs.sh`): `train-weekly` (no env), `train-weekly-k1`
  (`MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1`), `project-slate`
  (`GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1|
  BLEND_MODEL_WEIGHT=0.45`). None sets `EXTRA_FEATURES`. Only the research registries
  `train-weekly-k1-route` / `-route-role` set `EXTRA_FEATURES=fp_route_share_*` and the
  script says they "never replace the incumbent K=1 registries". No run manifest under
  `/home/erich/week3-sunday/` (outside the vendored repo copy in `props-precheck/`) records
  a different variant.
- **Inference code.** `live_lineups.py` (lines 424-431) copies the `fp_route_*` columns from
  the feature frame into the output frame as pass-through metadata for the route-share
  shadow; they do not touch the draws. `route_share_shadow.py`, `sis_pass_tail_shadow.py`,
  `sis_pass_tail_portfolio.py`, `tail_shadow.py`, `latent_role_shadow.py` are isolated
  shadow/research paths. Apparent vendor hits in `run_projections.py`, `market_source.py`,
  `ownership.py`, `prospective_all_boom_ceiling.py` are `gsis_id` / `fantasy_points_ppr`
  (nflverse) false positives.
- **Net:** vendor-derived columns reaching the served Week-3 projection: **none**.
  `fp_route_share_l4` rides along in the frame (157 of 161 rows non-null) but is not a
  model input. SIS: nothing, in the model or the frame.

## 6. What this does and does not support

Supported by the numbers:
- The vendor data was not used and, for 14 of 22 tables, not even collected in 2026.
- On this slate the vendor tables did not contain a clear warning on the players that sank
  the book (St. Brown, Jameson Williams, Taylor, McMillan: 1-2 warnings out of 16-17 each,
  several greens) and were negative on two of the biggest un-rostered scorers (Addison,
  Love). They were negative on Achane, Hall, Jeanty and Henry and positive on Darnold and
  Burrow. Net across 161 players: the warning share of busts equals the population's.
- The market was above us on both outright misses and only marginally below us on the busts.

Not supported (do not over-read):
- The borderline WR/TE partial correlations (+0.29 for 2025 per-route efficiency, -0.28 for
  the route-share jump, +0.26 for SIS opponent pass-D bust rate) are one slate, 14 hits
  from 110 tests, zero after correction, and in-sample refits of them move our actual
  heavy picks by a handful of ranks. If anything is worth a preregistered *prospective*
  shadow it is (a) a prior-season per-route efficiency prior for WR/TE and (b) the
  already-registered `fp_route_share_jump` with a *negative* expected sign - both as
  candidates for the frozen route-channel protocol, not as adoptions and not as
  retrospective tuning on this slate.
- QB-level results (n = 26, proj itself at rho 0.17 this week) are inside the noise floor.
