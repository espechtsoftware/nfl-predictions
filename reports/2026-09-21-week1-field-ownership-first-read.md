# Week-1 Millionaire field vs our pre-lock ownership inputs: first descriptive read

Written 2026-09-20 22:55Z. Backlog item 7 of the labs' outstanding experiment plan (rerun contest-entry calibration
and the ownership booster on the complete Week-1 field). One contest, one week: descriptive, not inference; no
current-week data touched.

## Data

* Realized: `nfl_raw.contest_ownership`, 2026 Week 1, contest 193028206 (Millionaire, 831,028 entries): 1,088 rows for
  665 players. DraftKings lists a player once per roster slot (e.g. Gibbs RB 38.58% + FLEX 4.17%), so realized
  ownership per player is the SUM across slots (total 898%, i.e. nine slots).
* Predicted: `nfl_predictions.own_shadow`, 2026 Week 1, latest pre-lock batch 2026-09-10 16:57Z, source `naive`
  (the value-rank input the production chalk fade consumes) with the `booster_own` column beside it (the LineStar-
  trained booster, not in the production path). Both are stored as within-position shares that sum to 100% per
  position (500% total), so level calibration is only meaningful after rescaling each source to the realized position
  totals (QB 100, DST 100, RB 242, WR 335, TE 121). 395 players predicted; 387 matched by name (98%); the matched set
  covers all realized ownership (the 278 unmatched field rows carry 0%).

## Within-position agreement with the field

| position | n | naive Pearson | booster Pearson | booster Spearman |
|---|---:|---:|---:|---:|
| QB | 56 | -0.15 | 0.71 | 0.72 |
| RB | 82 | 0.10 | 0.75 | 0.76 |
| WR | 136 | -0.24 | 0.52 | 0.79 |
| TE | 89 | 0.00 | 0.38 | 0.76 |
| DST | 24 | 0.65 | 0.58 | 0.66 |

After rescaling to the realized position totals: mean absolute error 3.38 pp (naive) vs 2.25 pp (booster).

## Level calibration (booster deciles after rescaling, pct)

Deciles 1-6 predicted 0.35-1.92 vs realized 0.00-1.09; decile 10 predicted 6.68 vs realized 9.20. Both sources are far
too flat at the top: the field concentrated on Gibbs 42.8%, Chase 30.1%, Mayer 27.5%, Olave 24.8%, Barkley 21.0%,
Hampton 19.9%, Achane 18.4%, St. Brown 17.8%, Jaguars 17.8%, G. Wilson 15.8%, McConkey 15.0%, Bijan 14.5%, while the
booster gave those players 0.9-9.0% (the naive input 0.7-6.8%, and 24.1% to the Jaguars). The naive input's largest
misses are cheap quarterbacks it ranked as value plays (Wentz 17.8% predicted, 0.01% realized; Taylor, Rattler, Knight,
Estime near 7-10% predicted, 0% realized) and the real chalk quarterbacks it missed (Burrow 0.8% vs 11.3%, Herbert 1.0%
vs 10.2%).

## Reading and next step

The production fade's input (naive) carried no rank information on this field outside DST; the booster ranks players
well within position but under-calls concentration by a factor of three to five at the top. The six-season verdict that
"the booster added nothing" was a realized-tail result on LineStar ownership; this is a live-field calibration read and
does not overturn it. What it supports: (1) accumulate the field calibration weekly (this table per week, per contest
type) as the in-season track prescribes; (2) a class-C paired shadow for Week 3, `fade input = naive` (control) vs
`fade input = booster rescaled to slot totals`, same pool and K, realized max and 200+/210+ clears primary, entered-
field ownership of the selected rows as the mechanism read; (3) a concentration-aware ownership model (top-of-field
mass) as a later candidate. Nothing changes in production from this read.
