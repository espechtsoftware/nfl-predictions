# Score sprint: first realized challenger results

**Date:** 2026-08-29

**Scope:** Sunday-main slates, 2023--2025 Weeks 1--18, 54 slates

**Primary metric:** mean of the realized weekly maximum from one selected book

**Status:** historical development evidence; not yet a production promotion

## Executive result

The replenishing hard-230 population is the first new population mechanism in
this sprint to show a material matched K=80 improvement. Its best paired cell
was the effective-independent-tail-shots DPP selector:

| Population / selector | K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---|---:|---:|---:|---:|---:|---:|
| Hard-230 + DPP | 80 | **179.549** | 13/54 | 11/54 | 3/54 | 1/54 |
| Matched P0 + DPP | 80 | 177.298 | 14/54 | 9/54 | 1/54 | 1/54 |
| Difference | 80 | **+2.251** | -1 | +2 | +2 | 0 |

The result is promising but remains a fixed R1--R4 fit diagnostic. It must be
reproduced under the all-block final-fit production estimand before hard-230
can replace or augment the current R6 population.

The targeted isolated structure profiles F7/F8/F9 did not establish an K=80
improvement over the current all-block R6 benchmark. Their strongest displayed
cell was 178.791, but that is one of five held-out-block coordinates and cannot
be selected after the realized read. Under the canonical R0 view, their best
K=80 rows were 176.169 for F7, 177.387 for F8, and 176.991 for F9. These arms
should not become standalone production defaults. Their retained value is as
potentially complementary contributors to a combined corpus, which is a
distinct test.

## Frozen references

| Reference | K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy A7 ladder | 80 | 176.113 | 8/54 | 6/54 | 2/54 | 1/54 |
| Current R6 tail ladder / supported ladder | 80 | **178.435** | 8/54 | 6/54 | 4/54 | 2/54 |

The current R6 row is the decision-bearing all-block final-fit benchmark. The
hard-230 and crossed-profile rows below are deliberately labeled diagnostics
because their fit scopes differ.

## Hard-230 matched K=80 comparison

| Selector | P0 control | Hard-230 | Hard minus P0 | Hard >=200 | Hard >=220 | Hard >=230 |
|---|---:|---:|---:|---:|---:|---:|
| Convex excess | 178.594 | 179.358 | +0.764 | 10/54 | 3/54 | 1/54 |
| Correlation aware | 179.456 | 178.603 | -0.853 | 8/54 | 3/54 | 1/54 |
| Support switched | 178.221 | 179.523 | +1.301 | 8/54 | 4/54 | **3/54** |
| Effective independent shots / DPP | 177.298 | **179.549** | **+2.251** | **11/54** | 3/54 | 1/54 |

This interaction matters. Hard-230 is not uniformly better under every
selector, so the production test must cross the population with the selector
rather than promote the population in isolation.

The population ceilings were nearly equal in this particular 250-lineup
score-blind bridge: 196.134 for hard-230 and 196.079 for P0. The improvement
therefore came primarily from placing more of the available realized tail in
the selected book, not from a large increase in this bridge's oracle ceiling.

## Entry-count curve already visible

Hard-230's best observed weekly-max rows increased materially with book size:

| K | Best hard-230 mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---:|---:|---:|---:|---:|---:|
| 80 | 179.549 (DPP) | 13/54 | 11/54 | 3/54 | 1/54 |
| 100 | 182.177 (support switched) | 17/54 | 10/54 | 4/54 | 3/54 |
| 150 | **185.517** (support switched) | **20/54** | **15/54** | 4/54 | 3/54 |

The non-monotone selector identities across K are diagnostic choices, not one
nested production book. Even so, the magnitude confirms that testing and
supporting 150-entry operation is one of the largest available scoring levers.

## F7/F8/F9 crossed-profile result

The immutable grade contains 315 cells: three profiles, five held-out world
blocks, seven selector coordinates, and the relevant 4/14/80/100/150 budgets.
No isolated profile produced a realized 230+ selected lineup in any K=80 cell.

At K=80, averaging each selector/profile result over the five block-specific
fits (a stability diagnostic, not a deployable consensus), the strongest rows
were:

| Profile / selector | Mean over five block fits | Block range |
|---|---:|---:|
| F7 QB/bring-back relaxed + correlation aware | 176.426 | 174.263--178.791 |
| F8 game cap 3 + correlation aware | 176.360 | 174.968--177.865 |
| F9 single QB partner + convex excess | 175.453 | 173.659--176.991 |

The result argues against any of these profiles as a standalone default under
the current belief law. It does not answer whether their union adds unique
tail lineups to the incumbent/hard-230 corpus, nor whether a different belief
law would make the structures valuable.

## Exact immutable evidence

- Catalog-wide outcome snapshot: generation `1787987566557209`, byte SHA-256
  `96c88d27cfa356794e250431dbcaa638fe7df2ec8dc1a9ead8538f0608c32f88`,
  3,547,704 bytes.
- Hard-230 grade: generation `1787987773846917`, byte SHA-256
  `a0fd3dc7b2ffae28b7dec97048da4fe99fedaf717b481b239c52c65819f01ef5`,
  15,126,123 bytes; internal grade SHA-256
  `fa6fe6f87b70736221d0696f781f5fc5e331ddefeb690e2f0fc281f146ccdea5`.
- F7/F8/F9 grade: generation `1787988278722136`, byte SHA-256
  `f62d4250773957cb8a7d8274d9cbb1030d3339adc970a0f234232d34a7cde438`,
  58,937,259 bytes; internal grade SHA-256
  `1cf54b0b86efac123ae4c3a45c209517601547c3fe39f4e4ea16b71034977fab`.
- Both challenger terminals existed before the first outcome read, and both
  grades cover all 54 slates.

## Immediate decision schedule

1. Run the 300-cell L2b/diversity panel: incumbent selectors plus gamma-4,
   gamma-5, and strict-200 evil-twin books at 80/100/150.
2. Produce the all-block final-fit hard-230 K=80 confirmation and the
   incumbent-plus-F7/F8/F9/hard-230 union test without regenerating completed
   populations.
3. Reproduce the external agent's strongest finalists through this same
   immutable 54-slate score surface.
4. Select the best exact-K80 production configuration by September 4. Keep
   K=100/150 as an explicit contest-entry-volume decision rather than mixing
   it into the K=80 promotion claim.
5. From September 5 onward, allow only rehearsal and critical correctness
   fixes before Week 1.
