# All-boom S result: the selector cannot harvest the deeper pool — NULL

**Date:** 2026-08-20 (UTC). One-shot execution of frozen
`20260819-all-boom-selection-s-v1`, 54/54 cells, aggregate SHA
`dfbfb48d…`. Every cell passed all three cross-run reproduction gates
(control C and S vs the ATLAS receipts, treatment C vs the all-boom v1
receipts, identity-capture vs canonical S — 1e-6), so this number and
the +9.06 C number are measured on provably identical books.

## The numbers (53 paired slates; recovery slate has no S by design)

| Endpoint | Control | Treatment | Verdict |
|---|---|---|---|
| Mean selected S | 178.57 | 179.91 (+1.34) | p_mean 0.49, p_signed_rank 0.78 — **NULL** |
| Slates better/worse/tied | — | **19 / 18 / 16** | coin flip |
| ≥194 | 9 | 12 | McNemar p 0.45 |
| ≥210 / ≥220 | 2 / 1 | 4 / 3 | p 0.50 / n.s. |
| Winner overlap vs chance null | **+0.24** | **+0.11** | treatment is FARTHER from winners |
| Book intersection | — | 37.6/80 | half the book changed, for nothing |

The pool ceiling rose +9.06; the selected book captured +1.34 of it and
that capture is statistically indistinguishable from zero. The C−S gap
widened from ~9 (control) to ~16.7 (treatment): the deeper the pool,
the more the line-194 coverage selector leaves on the table. And the
anatomy instrument confirms the recorded prior — boom depth is **volume,
not aim**: the treatment book sits closer to chance than the control
does on winner overlap.

## Preregistered consequence (frozen before the outcome)

"ΔS null while ΔC stands: the selector cannot harvest boom depth; the
next lever is selection-side, and the reallocation is closed at this
dose for the money path." Applied:

1. **All-boom reallocation: CLOSED for the money path at this dose.**
   The boom-deep pool is shelved, revisitable only through a fresh
   frozen arm AFTER a selector change proves it can harvest ceilings.
2. **A3 stack-relaxation comparator: the INCUMBENT** (boom-40
   production config). A3 is fully staged (lever tested, k=8 decided,
   census gates attached) — it freezes and launches next.
3. **Selection-side lane elevated:** the 5-to-17-point C−S gap is now
   the program's largest measured, unharvested prize. In order:
   SELECT_LADDER one-shot (A7), regret-targeted generation (A8, its
   motivation now sharpened: the selector needs worlds it can convert,
   not just higher ceilings), S1 null-gap floor (A6).
4. Baseline note: the arm's independent control reconstruction
   (178.567) matches the baseline file's comparator entry exactly.
