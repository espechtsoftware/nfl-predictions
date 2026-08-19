# Winner anatomy results: proximity is pure chance, shape is chalk-core-plus-leverage, and deep optima lean on never-realized draws

**Date:** 2026-08-19. One-shot execution of frozen
`20260819-winner-anatomy-v1` (report SHA `597787ac…`,
`reports/winner-law-audit-runs/20260819-winner-anatomy-v1-report.json`).
Descriptive; licenses nothing. Read together with
`2026-08-19-winner-world-optima-and-field-null-results.md`.

## A. Roster distance — the generator has NO winner signal in combination space

Against the full registered pool (~1,242 candidates per slate across
the five money-worlds books):

- Median best overlap with any candidate ever registered: **4 of 9**
  players; minimum 3; **no winner in three seasons has any candidate
  sharing 7+ players**; none is in the pool exactly. 12 winner players
  never appear in any candidate on their slate.
- The null calibration is the sharp part: max-minus-null quartiles are
  **[−0.41, 0.00, +0.77]** — our best-overlap candidate is exactly what
  exposure-preserving CHANCE predicts. Conditional on which players we
  use at all, the generator combines them toward winners no better than
  random.
- The 8 production-constructible winners: median 4.5, minimum 4, still
  never ≥7. **Even where the rules permit the winner, the pool never
  approaches it.** Stack relaxation is necessary (43/51 are illegal to
  emit at all) but measurably NOT sufficient.

## B. Ownership — winners are a chalk core plus ~4 leverage pieces

From actual Millionaire-contest ownership (51/51 profiled, 40 fully
matched 9/9):

- Median cumulative ownership **104.5%** (q25 79.4, q75 135.0) — about
  11.6% per player on average, i.e., winners are NOT ownership-extreme
  in aggregate.
- Median **4 players under 10%** owned; the distribution spans nearly
  pure-chalk (181% total) to nearly pure-leverage (2.7% total — one
  winner's entire roster summed under 3%).
- Template: a recognizable chalk core carrying ~3-5 sub-10% pieces.
  Our pool has chalk and has leverage; per finding A, it combines them
  into the wrong rosters.

## C. Optimum realism — deep-world optima are one-third mirage

In each winner's best generating world, comparing every player's
simulated score against his maximum realized score anywhere in the
54-slate corpus:

- **49/51 of the N1c world optima contain at least one player above his
  three-season realized maximum** — median 3 such players and **+19.3
  points of never-realized excess** per optimum.
- Control (the winners' own rosters in the same worlds): 43/51 have at
  least one, but median 1 player and **+5.8** excess — the optima carry
  roughly **3× the beyond-reality mass** of the winning rosters in the
  very same worlds.
- Reading: the law's deep-world optima are substantially built from
  single-player spikes that have never happened, while actual winners
  win on plausible co-booms. Depth-harvesting therefore chases partial
  mirages — the mechanistic prior for the all-boom read — and the
  law lane acquires a NAMED target: per-player marginal upper-tail
  allocation (too much mass on individual impossible spikes, too little
  on joint plausible booms — consistent with the book-tail
  factor-of-two).

## Consequences for the queue

1. **All-boom read (in flight):** prior sharpened toward skepticism —
   if depth converts poorly, C explains why mechanistically.
2. **Stack-relaxation arm:** still necessary, expectations tempered —
   A shows rule-legality alone doesn't produce proximity. Its freeze
   should add a mechanism gate: do open solves RAISE winner overlap
   above the chance null, not just scores?
3. **NEW law target (named by C): marginal upper-tail realism.** A
   candidate frozen experiment: cap or recalibrate per-player draw
   tails against realized-max-consistent quantiles and remeasure
   book-tail calibration plus the same optimum-realism metric. Connects
   directly to the existing draw-shaping/TabPFN marginal machinery.
4. **Field data (persistent gap):** `contest_entries` remains empty —
   the standings importer parses ranked lineups but no import has ever
   run with the entry block. The September Mon/Tue standings cadence is
   hereby load-bearing for the field model AND for growing the winner
   set (top-N rosters, not just #1) — DK purges in ~4 days;
   missed downloads are unrecoverable.
