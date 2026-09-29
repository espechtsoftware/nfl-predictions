# Winners study and consistency scripts (2026-09-29)

Evidence behind `reports/2026-09-29-winners-study-and-consistency.md`. Read-only against the warehouse, DraftKings'
public contest API (payout ladders; no login) and the lab's code and artifacts. All data stays outside the repo: the
standings carry user names, and the week's entry counts are private.

Run everything from one data directory outside the repo. Scripts are numbered in run order.

```bash
PY=~/projects/nfl-predictions/.venv/bin/python; LPY=~/projects/nfl2/.venv/bin/python
S=<checkout>/reports/lab-handoffs/2026-09-29-winners-study
export LAB_WT=<a clean, read-only checkout of nfl2 at production/prereg-l18-results-20260929>
export FIELD_INPUT=<field_model_input.parquet from the 09-28 review's w3_class_model.py>
export ACCT_FILE=<private one-line file with our user name>      # optional; only 12_ uses it, and never prints it
export MIX_FILE=<private JSON of contest mixes>                  # only 33_ uses it
mkdir -p pct pct2022 band tilt tilt2 tilt2022 lagsets blendsets

# Part 1-2: the real fields
$PY $S/01_pull_entries.py
for w in 1 2 3; do $PY $S/02_fetch_ladders.py $w contest-details-2026-w0$w.json; done   # 03_ reads the three file names it lists
$PY $S/03_payouts.py                      # every entry's prize; totals must equal the stated pools
$PY $S/04_top_placers.py                  # §1.1-1.2
$PY $S/05_heavy_players_and_skill.py      # §1.3, §2 persistence
$PY $S/06_other_contests.py               # §1.2 (other large contests), §1.4
$PY $S/07_pull_lineups.py && $PY $S/08_skilled_traits.py        # §2 traits
$PY $S/09_pull_projection_batches.py && $PY $S/10_sharp_tilt.py # §2 information in the skilled players' choices
$PY $S/11_saturday_vs_sunday.py           # §6
$PY $S/12_depth_ceiling_ours_fields.py    # §2 depth table, §3.1, §6 field strength
$PY $S/13_who_holds_the_top.py            # §1.2 winners, §1.4
$PY $S/37_projection_worth_2026.py        # §2 projection bands

# Part 3-5: the historical panel (lab code imported read-only; 9 worker processes each, 10-25 minutes)
$LPY $S/20_panel_rows.py && $PY $S/34_validate_against_l18.py
$LPY $S/21_panel_rows_2022.py             # needs slates_2022.json: [[2022, week], ...] from the lab's ownership record
$LPY $S/22_panel_projection_bands.py && $PY $S/38_panel_band_read.py
git -C $LAB_WT show origin/production/prereg-l15-20260929:results/l05_sets/lag/2023-w01.csv > lagsets/2023-w01.csv       # and the other 35; blendsets/ from results/l15_sets/blend_pct/
$LPY $S/23_tilt_lag_oracle.py && $LPY $S/24_tilt_blend.py && $LPY $S/25_tilt_oracle_2022.py
$PY $S/30_profile.py                      # §3.2
$PY $S/35_rows_top_vs_late_and_spread.py  # §4.2, §4.3
$PY $S/36_tilt_read.py                    # §4.1
$PY $S/31_expect_by_contest.py && $PY $S/32_expect_with_ownership_term.py   # §5.1
$PY $S/33_weekly_outcomes_by_mix.py       # §5.2
```

Notes:
- `20_`–`25_` import the lab's `plain_mean_book`, laws and field sampler from `$LAB_WT` and write only to the data
  directory. `34_` checks that the reproduction equals the lab's L18 X50 arm (bank 1240) on every slate.
- The three contest ids inside the scripts are the Millionaires', which `reports/lab-handoffs/milly_shape_lift.py`
  already carries. Every other id is read from the warehouse at run time.
- Field-strength offsets in `31_` are the measured differences in §6 of the report, from one to three contests each.
