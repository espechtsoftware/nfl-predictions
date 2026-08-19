# Marginal upper-tail realism — design v1 (C lane)

**Status:** design document, 2026-08-19. The mechanical half is
implemented and unit-tested (`src/nfl_dfs/research/marginal_tail_realism.py`);
the scored experiment is NOT frozen and does not run until (a) the
all-boom aggregate is read and (b) a one-page run protocol pins this
design with SHAs. Operator direction: "begin implementing everything you
can" (2026-08-19).

## Evidence this addresses

- Winner anatomy C (report `597787ac…`): 49/51 deep-world optima carry
  players above their realized corpus maxima (median 3 players, +19.3
  points); winners' own rosters in the same worlds carry a third of
  that (median 1, +5.8). Deep optima are ~1/3 mirage.
- Book-tail calibration: realized 6 vs expected 2.76 at 210 — the
  BOOK-level tail is ~2× too thin.
- Joint reading: the law misallocates tail mass — too much on
  independent single-player spikes that never realize, too little on
  joint co-booms that do. This lane fixes the first half; the
  dependence lane owns the second.

## Intervention (implemented)

Per player, a monotone piecewise-linear shrink above a high anchor:
draws below quantile 0.95 are bitwise unchanged; excess above it is
scaled by `s = (ceiling − anchor)/(q999_sim − anchor)`, clipped to
[0, 1] — the transform only shrinks toward realism, never inflates
(inflation is the dependence lane's job). Strict monotonicity per player
means every world ordering — and therefore the entire copula — is
untouched; `assert_ranks_preserved` enforces it fail-closed.

**Ceiling estimator (walk-forward, the leakage-critical piece):** for
week W, only realized rows strictly before (season, W) enter:
`ceiling = 1.10 × max(own realized max so far, position-level realized
q999 so far)`. The 10% headroom is frozen (realized history
under-samples the realizable ceiling). Players with no prior history use
the position component. Fitting ceilings on weeks later scored would be
outcome leakage dressed as a law repair; the boundary lives in ONE
audited function (`point_in_time_ceiling`).

## Staged measurement plan

**Stage 1 — outcome-blind (runs any time, no lease):** transform the 54
archived slate world-blocks with walk-forward ceilings; publish the
effect census only (fraction of draws changed, shrink distribution,
players collapsed). Sanity gates: ranks preserved on every block;
fraction of draws changed consistent with the 5% tail (roughly ≤ 6%).

**Stage 2 — outcome-aware diagnostics (queued behind the all-boom read
under the one-active law):** on transformed draws, recompute (a) the
optimum-realism metric — do deep-world optima stop being mirages? —
and (b) the book-tail expected-exceedance calibration against the same
realized book series (does expected 2.76 at 210 move TOWARD realized
6, i.e., does removing mirage mass make the remaining tail
better-calibrated, or does it thin an already-thin tail?). (b) is the
kill test: if shrinkage worsens book-tail calibration, the lane stops
here and the mass misallocation must be fixed jointly with dependence,
not marginally.

**Stage 3 — fixed-budget candidate arm (only if Stage 2 passes):** the
all-boom chain pattern verbatim — same seeds, same budget, same worlds,
generation solves run on transformed draws; exact-paired C/S scoring
with the co-primary block, plus the anatomy mechanism gate (does winner
overlap beat the chance null?). One shot, frozen before launch.

## Open decisions for the freeze

1. Anchor/target quantiles (0.95/0.999 implemented) — confirm or amend
   once the Stage-1 census is visible; amendment before Stage 2, never
   after.
2. Ceiling scope: prior-week walk-forward (implemented) vs
   prior-seasons-only (stricter). Recommendation: implemented version —
   in-season history is point-in-time legal and materially better for
   rookies.
3. Whether Stage 3 replaces or accompanies the stack-relaxation arm in
   the queue — operator sequencing call after the all-boom read.

## Stage 1 result (2026-08-19, outcome-blind, census SHA `06b52214…`)

With the v1 ceiling (1.1 × max(own realized max, position q999 over
2014+)), the transform is a NO-OP across all 255 blocks: essentially no
draws move (fraction changed ~0; shrink median 1.0; the single largest
movement anywhere is 0.89 points). The law's marginal tails are NOT fat
in absolute position terms — simulated per-player q999s sit below what
the position has actually produced since 2014.

Reconciliation with anatomy C: the mirage signal is PER-PLAYER-RELATIVE
— optima put big draws on players who have never demonstrated them
(beyond own-max), not draws beyond what the position can do. A
position-dominant ceiling cannot bind on that, and a per-player own-max
ceiling would be WRONG to freeze: winners' own rosters exceed their own
maxima in 43/51 best worlds (median 1 player) — breakout mass is
exactly what wins; the defect is who gets it and with whom (3 players
per optimum vs the winners' 1).

**Design consequence:** anatomy C is an ALLOCATION defect, not a
marginal-level defect. Marginal truncation is the wrong tool; the
signal routes to the dependence/co-movement lane (remeasurement in
flight) and to generation-side realism weighting (e.g., penalizing
solve objectives on never-demonstrated mass rather than truncating the
law). Stage 2/3 of THIS design are PARKED — not run — pending the
dependence read; the machinery, census, and this record stay as the
audit trail. Recommendation to the operator queue: no marginal-tail
experiment; revisit after dependence lands.
