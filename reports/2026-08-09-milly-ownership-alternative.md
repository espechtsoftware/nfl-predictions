# Contest-aware Milly ownership alternative

Status: the corrected diagnostic and trained-model smoke passed; the frozen
downstream lineup arm completed but failed the tail-first scoring gate and is
not adopted.

Implementation note (recorded before any downstream lineup panel): the
fade-only treatment is named `OWN_MODEL=milly_fade`. It fits only eligible
earlier-season contest-aware rows from the accepted K=1 snapshots, normalizes
predictions within position to preserve the incumbent penalty scale, and does
not place model ownership into the simulated field. The mechanism comparator
requires all upstream projections/worlds to remain invariant and the frozen
linear fade equation to hold exactly.

## Problem with the old ownership use

The warehouse already holds 103,556 settled ownership rows from 1,258
contests across every week of 2022-2025. The existing ownership model averages
players across all contests in a week. Those contests mix Classic and
Showdown, cash and GPP, and Sunday-main, Thu-Mon, early, afternoon, primetime,
and single-game pools. That target does not match the large-field Sunday-main
portfolio being optimized. The old trained booster beat the naive ownership
rank as a generic player predictor but added nothing to the corrected chalk
fade. Repeating `OWN_MODEL=fade` is therefore prohibited.

The alternative is to use the data more narrowly: model the settled ownership
of the large-field Sunday-main Fantasy Football Millionaire itself, using the
accepted Sunday-main K=1 player snapshots as the exact point-in-time feature
universe. This changes the ownership target and train/serve alignment, not a
penalty dose.

## Frozen data contract

- Ownership truth: one large-field Classic `Fantasy Football Millionaire`
  contest per season/week, excluding any contest name with an explicit
  single-game or alternate-slate parenthetical. Require Classic roster-mass
  checks: total ownership approximately nine roster slots and QB/DST each
  approximately one slot. Resolve accidental duplicates deterministically and
  fail on ambiguous same-week main contests.
- Player universe/features: immutable, research-eligible snapshots from
  `20260808-e80-k1-c616390`; normalize suffixes and punctuation before joining
  names; report match rates and never fill an unmatched ownership target with
  zero.
- Inputs must be available before lock: salary, K=1 projection/value,
  within-position salary/value ranks, position, slate size, implied team
  total, and cold-start/role summaries already in the snapshot. No actual
  score, winner membership, future ownership, player ID memorization, or
  unrestricted team/week identifiers may enter the model.
- Evaluation is walk-forward by season: train only on seasons earlier than
  the held-out season. The scored folds are 2023, 2024, and 2025; 2022 is
  training-only because no earlier ownership season exists.

## Diagnostic gate

Compare the contest-aware model against both (a) the existing all-contest
ownership model and (b) the naive value/salary proxy on the exact held-out
Milly rows. Report Pearson and Spearman correlation, MAE, top-quartile MAE,
position calibration, row counts, and join coverage by season.

The contest-aware model may reach a lineup arm only if it improves aggregate
MAE and Spearman correlation against both comparators, improves or ties both
metrics in at least two of the three held-out seasons, has no Spearman loss
worse than 0.02 in any season, and retains at least 90% of the valid
Sunday-main ownership mass after name/slate joining. A failure leaves the
naive fade unchanged and closes this historical ownership path.

## Downstream arm, frozen before the diagnostic

If and only if the diagnostic gate passes, run one corrected true-80 K=1 arm
that changes the chalk-fade ownership estimate from the default naive proxy to
the walk-forward contest-aware Milly estimate. Keep the fade penalty, K=1,
45/55 blend, $49k floor, `0/0/0/40` generation, candidate multiple 2, 80
entries, line 194, simulation seeds, and all other construction settings
fixed. Require an ownership mechanism audit proving projections and simulated
worlds are invariant, estimates change in the intended direction, and the
candidate/selected books move.

Use the same tail-first scoring gate as other new K=1 arms: at least +2
selected weeks at 200, non-worse selected 210, and non-worse pool-oracle 200,
with the full 187-240 grid and season diagnostics. Also report predicted
lineup ownership product/sum as payout-risk diagnostics; do not claim ROI or
duplication without complete historical entry fields. Do not tune the fade
penalty or reserve an ownership quota after viewing outcomes.

## Diagnostic correction ledger

Runs v1 and v2 failed before model fitting on null names and same-name players
at different positions. V3 completed, but post-run serve review found that it
recomputed salary/value ranks after joining truth rows; its positive metrics
are scientifically superseded and no lineup arm was launched. The corrected
evaluation preserves ranks computed on the complete accepted slate. It also
excludes 2022 Week 16 from the eligible ownership target: Christmas was
Sunday, the replay contains the two Sunday games, while the named Milly was
DraftKings' Saturday main slate. This is a calendar/slate-universe correction,
not a result-based model change. The final diagnostic must cover the remaining
71 contest/slate pairs, retain at least 90% mass in every eligible week, and
pass the original frozen gate above before the scoring runner will start.

## Corrected diagnostic outcome

The leakage-free v4 diagnostic completed as Cloud Run execution
`evaluate-milly-ownership-wd4ll` on immutable digest
`sha256:1530d8d9f9bd67a4928b40c7c42edcc740a8ab2887ddfcda1a6ca5dcb7852959`.
The report is tracked under
`reports/ownership-runs/20260809-milly-k1-c616390-v4/`.

The contest-aware model passed every frozen condition. Across 9,010 held-out
player rows, its aggregate MAE/Spearman were `2.8666/0.7865`, versus
`3.6142/0.5657` for the old all-contest model and `4.6548/0.2589` for the
naive proxy. Top-quartile MAE was `7.7347`, versus `9.8483/11.5424`. It beat
both comparators on MAE and Spearman in each held-out season (2023, 2024, and
2025), with no adverse-season exception. The 71 eligible contest/slate pairs
retained `98.90%` of ownership mass overall and at least `93.74%` in every
eligible week.

This result licenses only the already-frozen true-80 K=1 fade arm. It is not
evidence that the arm improves lineup tails. Its preflight uses 2023, not the
2022 training-only season, so the smoke test must actually fit and serve the
walk-forward model before the six-season panel can launch.

The first downstream preflight, `replay-e80k1milly-smoke-tt2g5`, did fit on
3,146 earlier-season rows but failed before candidate generation because DST
concatenation promoted the nullable `is_cold_start` serve feature to pandas
`object`, which LightGBM rejects. No season panel launched and no lineup
outcome was viewed. The repair coerces every declared model feature to a
numeric matrix in `build_features` and adds a serve-dtype regression. That
attempt's manifest also contained an incorrect full code SHA with the correct
seven-character prefix; the runner now requires the supplied SHA to equal the
local repository HEAD. Preserve the failed attempt as provenance and use a
new commit, image digest, and panel ID for the corrected retry.

Repair build `59f7cbd2-09f5-4cd1-819a-fe1bba0c6d8f` passed 701 tests with 2
skipped and produced immutable digest
`sha256:24d1b2b778c3e5ca905270d8836b7ee4b1e9632912ff6aa0609c77516813e7aa`.
Corrected preflight `replay-e80k1milly-smoke-7zvnq` fit the same 3,146 rows,
served model predictions, and completed the one-week replay. Panel
`20260809-e80-k1-millyown-6d4a549` then launched all six seasons; its exact
execution IDs and manifest are tracked under `reports/panel-runs/`. Do not
compare partial season outcomes.

## Downstream scoring outcome

All six exact season executions completed successfully and produced the full
107-slate, 80-entry panel. Comparator v1 execution
`compare-k1-milly-ownership-wcqqj` found the treatment failed the scoring gate:

| Weekly maximum metric | Source | Milly fade |
|---|---:|---:|
| >=187 | 36 | 33 |
| >=194 | 22 | 22 |
| >=200 | 12 | 12 |
| >=210 | 6 | 6 |
| >=220 | 3 | 3 |
| >=230 | 1 | 1 |
| >=240 | 1 | 1 |
| Mean | 179.60 | 178.60 |
| Median | 178.82 | 177.14 |

Candidate-pool oracle counts at 187/194/200/210/220/230/240 moved
`44/30/19/9/3/1/1` to `41/29/18/8/3/1/1`. Thus the arm produces no selected
200+ lift and worsens the required oracle-200 safeguard. The valid scientific
disposition is rejection regardless of season signs or average score.

The intended ownership mechanism is active: estimates changed on all 54
eligible 2023-2025 slates, 2,292 selected slots moved in each direction, and
the selected portfolio became *more* popular by its own modeled estimate
(mean ownership sum `0.3562 -> 0.3782`, mean log product
`-43.59 -> -36.08`). Shared candidates retained exact actual scores, p-line,
simulated means, and support masks.

V1 initially labeled the result mechanically invalid because 330 upstream
feature payloads were not bit-exact. The same column-aware audit used for CE
found zero material or categorical mismatches; the maximum numeric difference
is `3.5527e-15`, and the frozen fade equation error is `3.9968e-15`. The
comparator now preserves the bit-exact count as a diagnostic and fails only
numeric differences above `1e-12`, null mismatches, or exact nonnumeric
differences. No scoring gate, arm setting, or outcome is changed. Run a
labeled immutable v2 comparator to durably record `reject`, then close this
historical ownership arm; do not tune the fade dose or ownership variant on
these outcomes.
