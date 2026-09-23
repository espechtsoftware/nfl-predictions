# Audit: the returning-teammate study behind the live `RETURNING_TEAMMATE_ADJ=1` (verdict: no defect, keep it on)

Requested by production in HANDOFF `880c28f5`. Inputs rebuilt independently on the laptop: `ceiling_panel.parquet` =
`player_week_training` 2014–2025 with salary (102,927 rows), and `q_resid.parquet` from production's builder unchanged (7
walk-forward LightGBM fits). Scripts: `reports/lab-handoffs/2026-09-23-returning-teammate-audit-{a,cd}.py`.

## Reproduction
Production reported −0.41 (se 0.18) for all teammates and −1.20 (se 0.40) for spiked teammates. Rebuilt: **−0.40 (0.18)** and **−1.23 (0.40)**, both negative in 6/7 seasons.

## (a) Returner definition, pre-2022 (no inactive rows)
The risk was that a missing panel row means "not on DK's salary list", not "absent", producing false returners. Each of the 213
study returners was checked against **box scores (`weekly_stats`) and snap counts (`snap_counts`) at W−1**:
**0 of 213 played at W−1** (144 in 2014–21 with no row at W−1; 69 in 2022–25 with an inactive row). Positive control: the
same lookups hit at the return week W for 99.5% (box) and 100% (snaps) of returners, so the zero is real.
```
returners: 213
                    n  false_returner
era     row_prev                     
2014-21 False     144               0
2022-25 True       69               0

false returners by season (played W-1 per box score/snaps but counted absent):
         n  false  share
season                  
2014    16      0    0.0
2015    19      0    0.0
2016    19      0    0.0
2017    17      0    0.0
2018    10      0    0.0
2019    13      0    0.0
2020    21      0    0.0
2021    29      0    0.0
2022    16      0    0.0
2023    20      0    0.0
2024    19      0    0.0
2025    14      0    0.0


positive control at W: box-score hit 0.995, snaps hit 1.000
at W-2 (was_in_before): box hit 0.728
```

## (b) Point-in-time
Both features come from `014_player_week_usage.sql` windows `ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING` (by player-season).
`target_share_l4` is the average over the previous four rows. `target_share_jump` = the last non-null share in that window
minus the mean of the others. Neither sees week W. The q_resid builder is walk-forward by season (fit on seasons < S, active rows).

## (c) Placebo and (d) 2022–24 alone (verbatim)
Placebo = the top receiver returned one week EARLIER (absent W−2, back W−1, active W); same teammate definitions.
```

RETURN at W (production): 213 returner-weeks
  all teammates 2018-24                            n_ret  1147  diff -0.40 (se 0.18)  negative 6/7 seasons
  all teammates 2022-24 only                       n_ret   508  diff -0.38 (se 0.25)  negative 3/3 seasons
  all teammates 2018-21 only                       n_ret   639  diff -0.41 (se 0.25)  negative 3/4 seasons
  spiked teammates 2018-24                         n_ret   289  diff -1.23 (se 0.40)  negative 6/7 seasons
  spiked teammates 2022-24 only                    n_ret   132  diff -1.20 (se 0.56)  negative 3/3 seasons
  spiked teammates 2018-21 only                    n_ret   157  diff -1.26 (se 0.57)  negative 3/4 seasons
  spiked WRs 2018-24                               n_ret   171  diff -1.51 (se 0.54)  negative 6/7 seasons
  spiked WRs 2022-24 only                          n_ret    78  diff -1.43 (se 0.77)  negative 3/3 seasons
  spiked WRs 2018-21 only                          n_ret    93  diff -1.57 (se 0.76)  negative 3/4 seasons

PLACEBO: returned at W-1 instead: 151 returner-weeks
  all teammates 2018-24                            n_ret   840  diff -0.16 (se 0.22)  negative 4/7 seasons
  all teammates 2022-24 only                       n_ret   381  diff -0.26 (se 0.31)  negative 2/3 seasons
  all teammates 2018-21 only                       n_ret   459  diff -0.09 (se 0.31)  negative 2/4 seasons
  spiked teammates 2018-24                         n_ret   106  diff -0.07 (se 0.79)  negative 3/7 seasons
  spiked teammates 2022-24 only                    n_ret    47  diff -0.77 (se 1.01)  negative 2/3 seasons
  spiked teammates 2018-21 only                    n_ret    59  diff +0.50 (se 1.17)  negative 1/4 seasons
  spiked WRs 2018-24                               n_ret    34  diff -0.19 (se 1.42)  negative 4/6 seasons
  spiked WRs 2022-24 only                          n_ret    16  diff +0.75 (se 1.87)  negative 2/3 seasons
  spiked WRs 2018-21 only                          n_ret    18  diff -1.03 (se 2.13)  negative 2/3 seasons

LIVE definition: 270 returner-weeks; of which 57 are long absences the study excluded
  LIVE def: all teammates 2018-24                  n_ret  1532  diff -0.59 (se 0.15)  negative 6/7 seasons
  EXTRA (long absence only): all teammates         n_ret   392  diff -1.09 (se 0.29)  negative 6/7 seasons
  LIVE def: spiked teammates 2018-24               n_ret   360  diff -1.34 (se 0.37)  negative 6/7 seasons
  EXTRA (long absence only): spiked teammates      n_ret    73  diff -1.66 (se 0.84)  negative 4/7 seasons
```

## Reading
- **(d) holds:** 2022–24 alone gives −0.38 (all) and −1.20 (spiked), negative in 3/3; 2018–21 gives −0.41 and −1.26. Both eras
  match; it is not a pre-2022 artefact.
- **(c) the placebo is null:** all −0.16 (se 0.22), spiked −0.07 (se 0.79), mixed signs by season. The effect is specific to the
  return week, as the mechanism predicts.
- **Live vs study definition:** `returning_teammate_deltas` omits the study's "active W−2 or W−3" condition. It adds 57 long-absence
  returners (270 vs 213), whose teammates show a **larger** over-projection (−1.09, se 0.29). So the live deltas (0.41 /
  1.20) are, if anything, conservative. Not a defect; worth a line in the code comment.
- **Verdict: no defect. Keep `RETURNING_TEAMMATE_ADJ=1` for Saturday's build.**
