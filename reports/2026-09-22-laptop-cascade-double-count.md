# The cascade double-counts report-Out starters on the carry side, not the target side — a default-off fix is on a branch

Assignment (1) from `6b209a2f`. Script: `reports/lab-handoffs/2026-09-22-cascade-double-count.py`.
Fix: branch `laptop/cascade-priced-carries-20260922` @ `85824fd0` (default off; live path untouched).

## The structure

`find_out_players` returns every O/IR/report-Out slate player, but the injury report's Out players
already reach the model through `team_vacated_target_share` / `team_vacated_carry_share` and
`vacated_capture_*` (`sql/features/023`, lines 108–135). For them the cascade *also* raises teammates'
`target_share_l4`, `wopr_l4`, `rz20_targets_smoothed`, `carry_share_l4` and `gl3_carries_smoothed`.
That combination never occurs in training: when a starter sat historically, teammates' trailing
shares were pre-absence values.

**Live, Week-2 Sunday rebuild** (`project-slate`, 16:01 UTC 09-20): the cascade handled 30 players;
**9** were report-Out, so their teammates were adjusted twice. Those 9 generated **39** teammate
bumps, up to **+0.164 carry share** and **+0.111 target share**.

## The measurement

Walk-forward by season (fit on prior seasons' active rows with the production LightGBM params
from `2026-09-22-next-man-up-walkforward.py`). Every week, every report-Out skill player is fed to
the **real** `adjust_for_inactives`, with usage history from the prior and current season strictly
before the week. The table gives the mean residual (realized − predicted) of the teammates the full
cascade bumps; negative means over-projected:

| | n | model only | full cascade | carry side skipped |
|---|---:|---:|---:|---:|
| **RB, 2022–24** | 498 | −0.14 [−0.57, +0.29] | **−0.68 [−1.10, −0.26]** | −0.19 [−0.62, +0.24] |
| RB per season 22/23/24 | | −0.68 / +0.06 / +0.08 | −1.29 / −0.62 / −0.31 | −0.66 / −0.01 / −0.01 |
| WR+TE, 2022–24 | 1,972 | +0.18 [−0.03, +0.38] | −0.15 [−0.36, +0.07] | −0.08 [−0.29, +0.13] |
| QB (bumped only via carries) | 93 | −0.53 | −1.10 | −0.55 |

The intervals are 90% week-cluster bootstraps. Overall MAE on all active rows is slightly worse with
any cascade in every season (model / full / carry-skipped: 4.157 / 4.169 / 4.164, 3.932 / 3.943 /
3.938, 4.066 / 4.071 / 4.069).

**Reading:**
- **Carry side = double count.** The model alone is calibrated for these RBs. The carry bump
  over-projects them by ~0.5 points of model output, the same sign in all three seasons, and the
  interval excludes 0. Skipping it restores calibration. It also stops QBs inheriting RB carry
  share (−0.53 → −1.10).
- **Target side = not a harmful double count.** WR+TE move from a slight under-projection to a
  slight over-projection, both intervals covering 0. I leave it alone, which is the narrowest fix.
- **Live scale:** the model is 45% of the blend, so the carry double count is ≈ **0.2–0.3 DK points**
  of over-projection on each affected RB (and a few QBs), on the order of 15 carry bumps a week.
  It is small, but it is a bias pointing one way on exactly the players a cascade promotes into
  lineups.
- This differs from production's −0.02 "past an Out starter" figure because the population differs:
  that figure covers depth-promoted backups; this one covers every teammate the cascade bumps.

## Doubtful under `CASCADE_DOUBTFUL=1`: no double count — confirmed

Every `team_vacated_*` and `vacated_capture_*` expression in 023 (and 021) tests
`injury_status = 'Out'` only. A Doubtful source is invisible to the features, so the cascade is its
only adjustment. The fix keys on report-**Out**, so Doubtful sources and DK-only late flips (O/IR on
DraftKings but not Out on the report) keep the full cascade.

## The fix (branch, default off)

`CASCADE_SKIP_PRICED_CARRIES=1` makes `adjust_for_inactives` skip the carry-side `_redistribute` for
sources whose `injury_status` is Out, and logs
`cascade: <id> carries already priced by team_vacated_carry_share; carry side skipped`. The target
side is unchanged. Two new tests (default off; on → report-Out skips carries but keeps targets, while
a DK-only flip keeps carries); `tests/test_cascade_adjust.py` 24/24 pass. Inventory is unaffected
(inference only), so it can deploy the same way as `CASCADE_DOUBTFUL`: rebase on the shipping
branch, build, env flag.

**Recommendation:** production review, then enable for Week 3. Limits: three seasons (inactive rows
exist only from 2022, and 2025 has no injury data), a single seed, and model output only (not the
blended projection or lineups). The six-season law cannot be met here; the effect's sign is
consistent in 3/3 seasons.
