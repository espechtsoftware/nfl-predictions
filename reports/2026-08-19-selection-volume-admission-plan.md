# Selection-from-corpus plan: volume × admission × objective

**Date:** 2026-08-19 (operator-directed: "be sure that plan is documented
and followed").
**Evidence basis (all one-shot, outcome-viewed diagnostics on the 54-slate
corpus — decision support; every adoption runs through the standing
prospective discipline):**
- B1 union census: union of 51 panels has mean C 198.10 (above the
  194-mean target), tail doubled at 220+; growth is ~+3.5 per doubling of
  independent books with diversity worth only ~+0.4 — the corpus contains
  the target via VOLUME, not belief variety.
- B2-prime volume-OI admission: at the exact registered budget, selected
  mean S rises monotonically with admitted volume — 178.38 (k=5) →
  181.13 (k=51), S tails 12/4/3 → 14/5/4 at 194/210/220. Fixed-budget
  OI admission converts volume into a better selected book (Addendum
  117's dilution does NOT reassert under admission).
- ATLAS C: world-ranking NEGATIVE (−1.53 mean ΔC) — world choice within
  the law is closed; selection improvement runs through volume,
  admission, and objective, not ranking.
- C−S mean gap 5.01 with near-zero threshold gap: the residual
  selector-side prize is objective alignment, not algorithm quality.

## The plan, in priority order

1. **Seed-volume × OI admission, prospectively.** The production CBWU
   runs 5 seed pairs; B2-prime says 10–20 independent books admitted at
   the fixed budget is the largest measured selection-side gain
   (+2.0–2.75 selected mean, +2 weeks at 194, +1 at 210 and 220).
   Execution: build a `shadow-cbwu-volume` prospective shadow variant
   (the CBWU-OI shadow runner is already variant-parametrized) that
   generates k=20 independent seed books weekly and admits at the
   registered budget; collect alongside the money book from Week 1;
   grade with the paired weekly-max co-primary + McNemar. PRODUCTION
   adoption only through that prospective record — never from B2-prime
   alone. Owner: implementation me, freeze/deploy operator.
2. **All-boom reallocation arm** (operator-directed, in flight): decides
   whether seed-volume compute is better spent on boom depth. Chain
   armed; aggregate expected today. Read against its uncertain prior;
   joint interpretation with the N1b winner census.
3. **Winner-law audit N1/N1b** (frozen, executing): arbitrates
   depth-vs-law for the winners specifically; informs how far
   volume/admission can reach versus what only OT/DST/dependence can.
4. **A3 greedy optimality audit** (score-free, no amendment needed):
   exact CBC max-coverage vs production greedy on the 54 canonical
   books. Closes the selector-ALGORITHM question permanently. Execution:
   cloud job over the cached artifacts (local pilot acceptable at ≤3
   slates); queue after the current lanes settle.
5. **SELECT_LADDER one-shot** (implemented, default-off): the objective-
   alignment test targeting the 5.01-point C−S mean gap. GATED on two
   operator decisions — the utility freeze (mean vs ladder vs
   lexicographic) and the one-shot selector amendment. Runs the moment
   both exist; report with the co-primary block.
6. **Law lanes continue in parallel** (dependence remeasurement in
   flight; S2 OT mixture scorecard-gated; DST D-series; S1 floor decides
   residual-columns vs law priority): B1's own conclusion — the
   194-mean target is IN the corpus but reaching beyond it, and the
   extreme tail, remains law-bound.

## Standing rules for this plan

Every arm: fixed budget, preregistered, one shot, co-primary reporting.
No production change from any historical diagnostic. The 2026 prospective
season is the confirmation instrument for items 1 and 5. This document
does not supersede the operator decision queue; it sequences work between
decisions.

## Update 2026-08-19 (post winner-audit series; operator: "do all of that")

The winner-audit series (N1/N1b → N1c/N1d → anatomy) resolved into
three standing facts: winners are never world optima (median 47.4 below,
overlap 4/9); pool proximity to winners is exactly chance-level
(max-minus-null median 0.00) even for the 8 rule-compliant winners; and
deep-world optima carry ~3× the winners' never-realized draw mass
(median +19.3 vs +5.8). Queue adjustments, in force:

1. All-boom aggregate (chain r2 in flight after the serialization
   repair) — unchanged primary; anatomy C is its mechanistic prior.
2. Stack-relaxation carved-budget arm (draft exists) — freeze after the
   all-boom read; add the anatomy mechanism gate (open solves must beat
   the chance-overlap null, not just the score).
3. NEW law lane target: marginal upper-tail realism (per-player draw
   tails vs realized-max-consistent quantiles); design doc next, runs
   through the standard frozen one-shot discipline.
4. Winner-anatomy protocol executed (report `597787ac…`) — descriptive
   basis for 2 and 3; no further anatomy runs without a new version.
5. LOAD-BEARING data note: `nfl_raw.contest_entries` has never received
   a row; the standings importer already parses ranked lineups. The
   September Mon/Tue standings downloads are the only path to field
   rosters (DK purges ~4 days) — they feed the field model, measured
   N_eff, and a winner set beyond the 51 tracked #1s. Do not skip.
