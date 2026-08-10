# Tail-first adoption review

Revised 2026-08-10 at the operator's explicit direction. This review changes
the operational decision law; it does not rewrite any preregistered scientific
result or make a rejected gate appear to have passed.

## Current decision objective

The primary objective is the best realized score among the submitted weekly
portfolio, normally 80 entries. In a top-heavy large-field tournament, an
additional exceptional week is allowed to outweigh lower mean performance or
declines in other seasons.

Hard requirements remain:

1. point-in-time inputs, complete authoritative labels, legal lineups, and a
   mechanically valid comparison;
2. the same submitted entry count, with exactly 80 unique final lineups for
   the normal portfolio;
3. reproducible code/configuration/provenance and a live path that implements
   the tested mechanism; and
4. no hidden outcome-based parameter, seed, dose, or threshold tuning.

After those requirements pass, compare weekly-maximum counts from the highest
threshold downward: 240, 230, 220, 210, then 200. An arm is a promotion
candidate when it improves at least one 210+ threshold and does not worsen any
higher threshold. Counts at 194/187, mean/median, season signs, and whether a
gain occurred on an already-good or previously-weak slate are diagnostics,
not vetoes. A material loss at a higher threshold than the gain requires an
explicit operator decision rather than automatic promotion.

Candidate-generation work is not an entry-count penalty. If two arms both
submit 80 lineups, extra pre-selection solves are evaluated as runtime/cloud
cost and reliability, separately from scoring. A predeclared arm that failed
an older, misaligned score gate may be adopted by an explicit operator-policy
override, but its original scientific disposition remains recorded.

## Compatible true-80 inventory

The warehouse was re-audited across promoted and staging candidate tables.
Only corrected-universe panels with all 107 slates, 80 selected lineups per
slate, complete actuals, and stable panel provenance appear below. Duplicate
promoted/staging copies are shown once.

| Arm | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 | Mean max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| K1 CE12 + role12 + boom28 union | 39 | 27 | 18 | **12** | **6** | **3** | **2** | **182.57** |
| K1 CE12 + boom28 | **40** | 26 | **18** | 11 | 5 | 2 | 1 | 181.12 |
| K1 CE12 + boom40 union | 39 | 26 | 16 | 11 | 5 | 2 | 1 | 181.32 |
| K1 no salary floor | 37 | 24 | 16 | 8 | 3 | 1 | 1 | 179.11 |
| K1 model-only blend | 33 | 21 | 12 | 7 | 4 | 1 | 1 | 178.33 |
| K1 base | 36 | 22 | 12 | 6 | 3 | 1 | 1 | 179.60 |
| K1 Milly-ownership fade | 33 | 22 | 12 | 6 | 3 | 1 | 1 | 178.60 |
| K3 base | 29 | 19 | 8 | 5 | 1 | 1 | 1 | 177.08 |
| K3 coherent-member worlds | 32 | 20 | 6 | 4 | 1 | 1 | 1 | 177.94 |
| K3 candidate multiple 4 | 30 | 22 | 9 | 2 | 1 | 1 | 1 | 177.27 |

Older 40-entry panels and panels invalidated by the incomplete DST/player
universe are excluded. They cannot be made eligible merely because an old
score looks attractive.

## Role-union override

The role union is the strongest mechanically valid true-80 historical arm
under the revised objective. It improves every 210+ threshold by one and
worsens none. Relative to K1 CE12 + boom28, paired weekly maxima improve on
15 slates, decline on 6, and tie on 86; mean change is +1.448 points. Mean
weekly maximum improves in five of six seasons. The largest gain is +32.52
and the largest loss is -14.34.

The original machine disposition remains `reject`: its frozen first-stage
gate required two new 200-point weeks on slates whose source pool was below
200, and it created zero. That gate tested whether the generator repaired
weak pools. It was contrary to the current tournament objective because it
gave no adoption credit for improving already-high weeks from 212.84 to
241.14 and 265.14 to 279.44.

The operator therefore overrides the operational decision, not the
scientific record. Policy `classic-k1-ce12-role12-boom28-v2` is adopted for
Week 1. It retains the prior candidate pool and adds the exact frozen 12
role-belief candidates before selecting the same 80 entries. Its separate
role registry and live candidate path passed parity/deployment checks on
2026-08-10; the old K1 CE12 + boom28 implementation remains a labeled
runtime fallback.

## Revisited older rejections

- K1's old season-stability rejection was already overridden and led to the
  current baseline. The revised law makes that decision permanent.
- No-floor, model-only, Milly-ownership, coherent-member, and raw
  candidate-scaling arms remain off because the valid true-80 results are
  inferior to both the current CE baseline and the role union at the high
  thresholds. Their rejection is no longer based on season signs.
- The added-budget CE union remains off: it ties the current CE baseline at
  210-240, loses two 200-point weeks, and is dominated by the role union.
- Invalid or incomplete-universe feature/role panels remain ineligible. A
  scoring preference cannot repair a broken comparison.

This exhausts the warehouse's compatible valid true-80 arms. Future arms use
the revised law, while prospective frozen outcomes supersede historical
evidence as they accumulate.
