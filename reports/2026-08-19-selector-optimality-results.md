# Selector optimality audit (A5): the algorithm is not the problem — CLOSED

**Date:** 2026-08-19. One-shot execution of
`20260818-selector-optimality-gap-v1` over every archived block
(report `reports/winner-law-audit-runs/20260819-selector-optimality-audit.json`).
Score-free — simulated candidate totals only, no realized outcome, no
lease — so it ran alongside the in-flight A3 scored arm.

## Result

255 of 255 blocks solved to **exact CBC optimality** (zero timeouts), at
the production contract (80 entries, line 194).

| Metric | Value |
|---|---|
| Mean greedy coverage | 2,135.3 worlds (of 2,300.9 coverable) |
| Mean gap to exact optimum | **2.84 worlds** |
| Gap as a fraction of greedy coverage | **0.134%** |
| Worst single block | 14 worlds (0.70% of that block's coverage) |
| Blocks where greedy is already exactly optimal | 42 / 255 |

## Reading (preregistered)

"A ~zero gap closes the selector-ALGORITHM family permanently and
redirects all remaining selection attention to the objective and the
pool; a material gap licenses an exact/beam selection upgrade."

A tenth of one percent is ~zero. **The greedy coverage selector is
effectively optimal for the objective it is given.** Replacing it with
exact or beam search would recover, at best, three worlds in ~2,135 —
nothing that could move a book score. The selector-ALGORITHM family is
CLOSED; no exact-selection arm should ever be built.

## Consequence for the selection lane

The boom-S null showed a +9.06 pool ceiling converting to +1.34 in the
book, and the C−S gap widening to 16.7 with pool depth. This audit
eliminates one of the two possible explanations. The selector is not
failing to optimize; therefore the loss is in **what it is asked to
optimize** — line-194 world coverage — which is not the same thing as
maximizing the book's best realized score.

That makes the objective lane the whole prize, and reorders the queue:

1. **SELECT_LADDER (A7) is now the highest-value selection arm** and is
   already implemented and default-off. It is blocked ONLY on the
   operator's utility freeze (mean vs ladder vs lexicographic) plus the
   one-shot selector amendment. This audit is the argument for spending
   that decision now.
2. **Regret-targeted generation (A8)** keeps its motivation: worlds the
   selector can convert, not merely higher ceilings.
3. Any future "better selector" proposal must first show that the
   objective changed — the algorithm question is settled.
