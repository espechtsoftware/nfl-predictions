# Season-window support audit, Weeks 2-3 of 2026 (bounded; laptop Priority 1)

Written 2026-09-21 by the workstation assistant from `nfl_features.player_week_inference`, the last pre-lock Week-2
projection batch (2026-09-20 16:02Z) and the Week-2 realized DK points from the standings exports. This audits the
support behind the rolling features; it proposes no window change (a change needs a reproducer, a training-contract
comparison and a retrain cycle, per the laptop's review).

## Support

Every rolling feature (`_l4`, `_last`, `_jump`) restarts each season (`sql/features/014_player_week_usage.sql`:
`PARTITION BY gsis_id, season`). In Week 2 the inference rows for skill players carried:

| week | position | 0 games of support | 1 game | 2-3 games |
|---|---|---|---|---|
| 2 | QB | 75 | 37 | 0 |
| 2 | RB | 103 | 101 | 0 |
| 2 | TE | 98 | 100 | 0 |
| 2 | WR | 204 | 159 | 0 |

So 55% of the Week-2 skill rows were cold-start (`is_cold_start` 0.547; `dk_points_l4` null for 61.5%, the usage
shares null for 54.7%, `xfp_l4` null for 100%) and the other 45% carried a one-game window. Week-3 rows (51 so far,
before Tuesday's rebuild) show the same shape one game later: 0 or 2-3 games, never a stable window before Week 5.

## What the one-game window did to the served projection (Week 2)

Among the 153 players projected at 5+ with a realized score, a 2025 mean and a Week-1 score, the served projection
regresses on the 2025 mean and the Week-1 score with weights 0.43 / 0.21; the realized points regress at 0.50 /
0.17. The projection over-weighted the single game modestly at the mean level. The damage came through two other
doors: (a) the market stand-in (18 players projected 5+ had no matched market and were blended with their one-game
DK PPG at 55% weight; their mean residual was -3.56 against -1.47 for the 157 prop-sourced players; this is the
Jefferson mechanism and is fixed by the props-or-nothing rule), and (b) the selector's preference for the highest
simulated p90s, which sat on the Week-1 risers (post-mortem section 9).

Within the one-game bucket, corr(projection, realized) = 0.54; corr(Week-1 score, realized) = 0.33; corr(2025 mean,
realized) = 0.41. The projection outranks both raw signals, so the model is not simply echoing Week 1.

## What is and is not established

- Established: the Week-2 and Week-3 rolling features are cold-start or one-to-two-game windows for every player;
  the model was trained on the same within-season windows, so this is the training contract, not an ingestion gap.
- Not established: that a cross-season window would improve Week-2 projections. The realized weights above say
  prior-season information deserves about half the weight and the model already gives it 0.43; the residual
  over-weight is 0.04 of a one-game score. A cross-season window with season-change shrinkage is a modelling change
  to be tested walk-forward on 2019-2025 Weeks 2-4 with a retrain, not a repair.
- The missing values are expected cold-start values (the cold-start filler runs on them), not a join-key defect: the
  counts by position match the slate, and `xfp_l4` being 100% null in Week 2 is the schedule-based xFP source having
  no in-season rows yet (a known source-timing gap, worth a row in the data-deficiency log).

## Recommendation

Leave the windows for Week 3. Close the two doors that carried the damage (done on the repair branches: props or
nothing; caps and market-pull as shadow arms). Put the cross-season window on the research queue as a walk-forward
experiment with a frozen protocol; do not call it a repair.
