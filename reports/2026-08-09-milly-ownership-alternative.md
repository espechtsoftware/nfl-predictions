# Contest-aware Milly ownership alternative

Status: diagnostic and downstream arm preregistered before viewing any new
ownership-model or lineup-score comparison.

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

