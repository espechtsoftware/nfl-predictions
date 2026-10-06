# Preregistration: the weekly paired check of Fantasy Points vs 0.5 FP + 0.5 props on prop-covered players (class C)

**FROZEN 2026-10-06, before any Week-5 outcome.** The laptop drafted it; the reviewer asked for it (10-06). The reader is
`scripts/weekly_fp_props_check.py` (sha256 at the freeze commit); its tests are `tests/test_weekly_fp_props_check.py`.
It reuses the frozen weekly accuracy reader's cutoff and capture functions (`scripts/weekly_projection_accuracy.py`).

## Why
The props report (`reports/2026-10-06-props-and-winners.md`) found, on 2026 Weeks 1–4:
- on players with prop lines, props alone beat our model and our served blend; the best model weight is 0;
- from Week 5, Fantasy Points' projections pick the lineups (the operator's decision), so the live question is FP vs
  FP + props;
- Week 4 (the only FP week): on the 183 prop-covered players, 0.5 FP + 0.5 props missed by 5.76 against FP's 5.85
  (+0.09 points, better in 98% of game resamples).

**Week 4 was seen before this freeze and is NEVER counted.** The reader refuses to pool it.

## Population (fixed)
QB / RB / WR / TE in the week's T-70 frame with:
- a REAL prop number: the T-70 frame's `market_points` (the props the build itself had at T-70), present and not
  equal to DraftKings' points-per-game (the old fallback);
- an FP projection from the newest DraftKings Main capture retrieved before the T-70 build (the run's receipt
  `built_utc`), joined exactly on the draftable id;
- the week's Millionaire fpts (normalised name; slate-wide collisions dropped);
- game-day status ACT (O-32).

Both arms are scored on the same rows.

## Arms and endpoint (fixed)
- **FP:** Fantasy Points' projection.
- **BLEND:** 0.5 × FP + 0.5 × props.
- **Endpoint:** mean absolute error against the Millionaire's DraftKings points, pooled over every week from Week 5 on.
- **Uncertainty:** the game-cluster bootstrap within week, B 2000, seed 1 (the frozen weekly reader's).

## Rule (fixed)
**The blend is OFFERED when its pooled MAE (Weeks ≥ 5) is lower than FP's AND at least 95% of the resamples are
better.** This mirrors the revisit rule of the weekly accuracy reader. An offer is a class-C trial under adoption track
v2: reversible, with the frozen weekly check as its monitoring. The operator decides. Nothing here changes production.

## Power, said plainly
About 180 prop-covered players a week. Week 4's +0.09 would need several weeks to clear 95% if it is real. "Not
offered" is the expected answer for a while and is not evidence against the blend.

## Week 5
The operator chooses, with one week of evidence:
1. FP as he decided, with FP + props as a paired paper shadow scored Monday (this check); or
2. FP + props on prop-covered players now, as a reversible trial. That needs a small reviewed change to
   `fp_projection_override` (a blend with the T-70 frame's `market_points` where real props exist, gated like FP), with
   a test, by Friday.

The reviewer recommends (1); one week is thin for changing the projection source four days before lock.

## Every Monday from 10-12
`python scripts/weekly_fp_props_check.py week --season 2026 --week W --frame <T-70 run>/frame.parquet --lock-utc <lock>
--contest <Milly id> --out-dir ~/private/fp-props-check`, then `... pool --out-dir ~/private/fp-props-check`.

Smoke (10-06, Week 4, mechanics; already-seen data): it reproduces the props report (183 players, FP 5.852, blend 5.760,
+0.092, 0.980 of resamples), and the pool refuses Week 4.
