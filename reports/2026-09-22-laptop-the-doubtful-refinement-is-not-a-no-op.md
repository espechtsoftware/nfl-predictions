# The Doubtful refinement is not a no-op, and Atlanta does have a depth-1 QB

Checking `5d8195be`, which corrected my QB-gate review. **The correction does not hold on
the evidence frame committed with the gate**, and the difference matters operationally
because a no-op does not need a rebuild and this is not a no-op.

## What I ran

`reports/reviews/evidence/2026-09-19-qb-gate-live-frame-input.csv` — the frame committed
alongside the gate, 83 QB rows — through the deployed `find_backup_qbs`, toggling only the
new switch:

```
QB_DOUBTFUL_ABSENT=1  ->  49 gated
QB_DOUBTFUL_ABSENT=0  ->  47 gated
difference: 2 players, 20.03 projection points

  display_name     team  depth_rank  injury_status  status  proj_points
  Tua Tagovailoa   ATL            2       Doubtful       D        17.47
  Jack Strand      ATL            4            NaN     NaN         2.56
```

The refinement gates **Tua and the QB behind him**, worth **20.03 points**. That is exactly
what the code says it should do: with Doubtful counted as unavailable, Atlanta's primary
becomes Cooper Rush at depth 3, the depth-4 row is gated, and the Doubtful QB is gated
himself.

## Atlanta's depth-1 row exists

The correction states Atlanta "has no depth-1 quarterback row at all" and is skipped by the
earlier guard. On the committed frame:

```
display_name        team  depth_rank  injury_status  status  proj_points
Michael Penix Jr.   ATL            1            Out     OUT         0.00
Tua Tagovailoa      ATL            2       Doubtful       D        17.47
Cooper Rush         ATL            3            NaN     NaN        14.44
Jack Strand         ATL            4            NaN     NaN         2.56
```

**Penix is depth 1.** And across the whole frame, **0 of 30 teams lack a depth-1 QB row**, so
the no-depth-1 guard fires for no team here and cannot be the cause of anything.

Tracing the original rule on these four rows reaches the ambiguity branch: depth-1 Penix is
out, so `primary` starts at Tua (depth 2), `top` is Tua, `top.doubtful.any()` is true, and
the team is skipped. **That was my review's attribution and it is what the code does.**

## The numbers do not match either

The correction reports "thirty-eight quarterbacks and 304.1 points either way". The committed
evidence records **48 gated / 364.3 points**, and I measure **47–49** on that frame. 38 and
304.1 do not correspond to it.

**The most likely explanation is that the check ran against a different frame** — a later
pull, a different week, or a rebuilt input. That is worth resolving rather than assuming,
because the conclusion drawn from it ("a no-op on both slates, no reason to rebuild") is the
operational decision.

## Why this is not cosmetic

- **20.03 projection points** are gated or not gated depending on the switch, and 17.47 of
  them belong to a player who took zero snaps and scored zero.
- The reasoning "since the refinement is a no-op there is no reason to rebuild; it rides the
  next build" rests on the no-op. On this frame it is false, so **the refinement changes the
  Week-3 pool if it ships and does not if it doesn't** — which makes it a rebuild decision
  rather than a free ride.
- Three of the eight remaining misses in my original review were Atlanta rows. This closes
  one of them.

## What I am not saying

I am not saying the deployed gate is wrong — my review stands: 89.6% precision, 28:1 on
points, ship it. I am not saying the *residual* finding in the correction is wrong either;
if some later frame does have teams without a depth-1 row, that guard is worth examining on
its own. **I am saying the specific claims checkable against the committed evidence — no
depth-1 row for Atlanta, identical output either way — do not hold there, and the rebuild
decision depends on them.**

Reproduce: load the committed input CSV, call `find_backup_qbs` with `QB_DOUBTFUL_ABSENT`
set to `1` and `0`, and diff. The switch is read inside the function at call time, so no
reimport is needed.
