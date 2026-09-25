# 2026-09-25 outside-the-box review: reproduction scripts

Scripts behind `reports/2026-09-25-outside-the-box-strategy-research.md` §2. Inputs are public (nflverse releases,
Fantasy Football Calculator ADP) plus LineStar's public `GetSalariesV5` endpoint, fetched with the same politeness rules
as `src/nfl_dfs/ingest/linestar_backfill.py`. **LineStar data is third-party: keep it outside this public repository.**
Nothing here reads BigQuery, touches the money path, or opens any 2026 outcome beyond public box scores.

```bash
OUT=~/.cache/nfl-dfs-outside-the-box            # outside the repo
PY=python3                                       # needs pandas, numpy, scipy, pyarrow, requests
$PY fetch_public_inputs.py $OUT                  # ~2 min; 74 LineStar calls at 1.2 s
cd $OUT
$PY <repo>/reports/lab-handoffs/2026-09-25-outside-the-box/a_slate_factor.py              # §2.1 slate factor, wind
$PY <repo>/.../b_cross_team_fantasy_coupling.py   # §2.2 opponents' fantasy coupling given the market
$PY <repo>/.../c1_build_linestar_panel.py         # builds ls_main.parquet (74 main slates)
$PY <repo>/.../c2_crowd_information_vs_recency.py # §2.4 T1-T6; writes ls_skill_analysis.parquet
$PY <repo>/.../c3_windows_seasons_magnitudes.py   # early/late, per season, elasticity, quintiles
$PY <repo>/.../c4_prelock_decomposition.py        # pre-lock usable part; boom/bust bands
$PY <repo>/.../c5_recency_ownership_walkforward.py# ownership model + recency, walk-forward 2023-25
$PY <repo>/.../c6_crowd_mean_fusion_walkforward.py# crowd signal as a mean input (small)
$PY <repo>/.../c7_recency_vs_informed_chalk.py    # top-15 chalk split
$PY <repo>/.../d_residual_correlation_card.py     # §2.3 residual correlation card
$PY <repo>/.../e_ingame_lead_collapse.py          # §2.6 in-game lead collapse
$PY <repo>/.../f_preseason_adp.py                 # §2.7 preseason ADP
$PY <repo>/.../g_eruptions.py                     # §2.5 eruption frequencies
```
Caveat carried from HANDOFF (2026-09-22): LineStar historical periods were last updated the Monday after each slate,
so their pre-lock status cannot be proven. The definitive version of §2.4 re-runs the decomposition on the team's own
point-in-time replay projections and `contest_ownership` in BigQuery.
