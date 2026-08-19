# Winner-law audit result: the winners live one world past the solve horizon

**Date:** 2026-08-19. One-shot execution of the frozen protocol
(`20260818-winner-law-audit-v1`, SHA `daa9865f…`; manifest `514b46b9…`,
51 slates × 5 verified artifacts). Canonical report:
`reports/winner-law-audit-runs/20260818-winner-law-audit-v1-report.json`
(SHA `c715cd78…`). Diagnostic only; licenses nothing.

## N1 — the law cannot produce the winners' SCORES

Across all 51 tracked 2023–25 Milly winners, the realized winning score
sits at **median percentile 1.0** of that roster's own 50,000-world
simulated distribution: 51/51 at or beyond p95, 50/51 beyond p99,
**47/51 beyond p999**, and at least one winner above every single
simulated world (`min Pr_sim = 0.0`). Identical in every season
(17/16/17 beyond p99). Under the protocol's frozen reading, this is the
unambiguous case: **missing joint co-boom mass**, dollars-weighted, on
exactly the lineups the program wants to build. The law lanes (OT
mixture, DST events, dependence) are not optional garnish — the law
cannot currently even *imagine* the scores that win.

## N1b — but their COMBINATIONS sit just past the boom horizon

Every winner (51/51) has "generating worlds" — worlds where its roster
outscores every candidate ever registered: median **448** of 50,000 per
winner (max 1,364), with a median winner-over-pool margin of **44
points** in its best world. Their positions in the incumbent boom visit
order:

- best rank: minimum 41, **median 57**, maximum 511;
- 48/51 winners have a generating world inside the **top 200**;
- 0/51 inside the top 40 — which is PARTLY STRUCTURAL: solved worlds'
  optima are already candidates, so a solved world can never be
  "generating." The honest statement is: no winner was the optimum of
  any world production solved, and winners dominate our pool in worlds
  beginning immediately below the solve line.

Production's boom family solves the top 40. The winners' worlds start at
41 and cluster at ~57. **The generator has been stopping almost exactly
one world short of the winners' territory, every week, for three
seasons.**

## Joint reading (with today's other verdicts)

1. The operator-directed **all-boom arm (N_BOOM=200, in flight)** is now
   precisely aimed: it solves the 41–200 band where 48/51 winners'
   generating worlds live (median 8 such worlds per winner in that
   band). Caveat, stated before its result: a generating world proves
   the winner beats OUR pool there, not that it is that world's optimum
   — the MILP may return a different roster. The margins (median +44
   over the pool) say the band is rich regardless.
2. **N1c follow-up (proposed):** exactly 51 MILP solves — each winner's
   best generating world, solved to optimality — settles whether the
   winners ARE the optima of their worlds (boom-depth suffices to build
   them) or sit below other rosters the law prefers (depth finds
   winner-adjacent builds, law repair required for the winners
   themselves). One small cloud job; freeze a one-page protocol first.
3. ATLAS's closure is unaffected: ranking within the top of the order
   was the wrong lever; DEPTH past rank 40 is where the winners are.
4. B1/B2-prime's volume×admission plan is complementary: volume adds
   independent draws (more worlds, more chances the winners' patterns
   arise); depth solves the drawn worlds further down; the law lanes
   make the simulated scores of those patterns realistic.

## Addendum (same day): the field-max confound, stated honestly

The N1 headline overclaims as written. Winners are the maximum over a
~150,000-entry field: under a PERFECTLY correct law, the field-max
roster's realized score would still sit at an extreme percentile of its
own simulated distribution (roughly 1 − 1/N_effective). With effective
independent field size plausibly above 50,000, percentiles near 1.0 —
and even occasional scores above all 50k sim draws — are consistent
with a correct law. Only a computed null calibrates "how high is too
high": **N1d (proposed)** — under our own law, simulate field-max
selection at candidate effective sizes, and compare the null percentile
distribution against the observed 51. The book-tail calibration's
modest miss (realized 6 vs expected 2.76 at 210 — a factor of ~2, not
many sigma) independently suggests the score-level deficit is real but
FAR smaller than the naive N1 reading. N1b's geometry (generating
worlds at ranks 41–511, margins +44 over the pool) is unaffected by
this confound: it compares rosters within the same worlds.

## Addendum 2 (2026-08-19, post N1c/N1d): both headline readings superseded

The frozen follow-ups settle the questions this document raised, in
opposite directions from its narrative. N1d: the score-percentile
extremity is what a CORRECT law produces under field-max selection at
plausible field sizes (~9.5k rosters); the N1 "missing co-boom mass"
reading is dead, and the book-tail factor-of-two is the only surviving
law-deficit evidence at winner scale. N1c: no winner is the optimum of
any archived world (0/51, median 47.4 points below, 4/9 overlap), so
"the generator stops one world short of the winners' territory" is also
dead — deeper solving harvests different rosters, not winners. The
N1b geometry itself (winners dominate the pool in worlds at ranks
41–511) remains valid; its actionable content moved to the stacking
finding: 43/51 winners violate the production stack/bring-back rules
and are unbuildable at ANY depth. See
reports/2026-08-19-winner-world-optima-and-field-null-results.md.
