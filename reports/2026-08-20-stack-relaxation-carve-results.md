# A3 stack-relaxation carve: the mandates that exclude 84% of winners are HELPING us — closed at this dose

**Date:** 2026-08-20. One-shot execution of frozen
`20260819-stack-relaxation-carve-v1`, 54/54 cells, aggregate SHA
`2e08a551…`. Every cell passed the cross-run reproduction gates against
the ATLAS receipts (1e-6). The grid completed in GCS; the chain process
died before its aggregate step (machine sleep), and aggregation was
completed afterward from the immutable create-only receipts using the
chain's own aggregate code, unmodified.

## Result: negative

| Endpoint | Control | Treatment (k=8 open solves) |
|---|---|---|
| Mean selected S | 178.57 | **177.59 (−0.98)** |
| Slates better / worse / tied | — | **6 / 11 / 36** |
| ≥194 | 9 | 8 |
| ≥200 | 7 | 6 |
| ≥187 | 16 | 17 |
| Winner overlap vs chance null | +0.242 | +0.189 |

Co-primary: p_mean 0.367, p_signed_rank 0.459 — the decline is not
statistically significant, but the direction is consistently unfavorable
and the tail thresholds that matter (194, 200) both regress.

## The mechanism gate is what makes this decisive

This was emphatically NOT a vacuous arm. 2,152 open candidates were
generated across the grid, and the unchanged production selector
admitted **530 of them into the books — open lineups reached the book on
all 53 slates.** The preregistered branch is therefore unambiguous:

> "ΔS null with open candidates admitted: the mandate is not the binding
> constraint at this dose." — and here it is worse than null: negative.

Combined with the smoke (11/80 book slots on the canary slate), the
finding is that the selector *wanted* the un-mandated shapes, took them
in quantity, and the books got slightly worse for it.

## Interpretation — the uncomfortable, important part

The structure census established that production's stack/bring-back
mandates confine 100% of our generated volume to a region containing
only 16% of real Millionaire winners. The intuitive inference — which
the operator and I both drew — was that the mandates were excluding the
winning shapes and should be relaxed.

**This arm falsifies that inference at this dose.** Removing the mandates
on a fifth of the boom solves produced shapes closer to the winners'
region and made our own book score slightly worse. Both things are true
simultaneously:

1. The mandates DO exclude most winners' structures (census, verified).
2. The mandates ARE, at this dose, helping our books score (this arm).

The reconciliation is the dependence defect: our simulator
under-couples QB→WR, so within the law, stacks are underrewarded
relative to reality. The mandates have been acting as a *hand-applied
correction for a known law defect* — forcing correlation the law fails
to value. Relaxing the mandate while the law is still mis-specified
removes the correction and leaves the defect exposed. That also predicts
why the winner-overlap instrument moved the wrong way (+0.189 vs
+0.242): the open shapes were selected on a law that misprices them.

## Disposition (preregistered)

- **Closed at this dose.** No rerun, no dose sweep, no k variation on
  this corpus — the protocol forbids it and the ledger's wholesale-
  deletion precedent now has a bounded-carve companion.
- **`OPEN_BOOM_SOLVES` stays default-off** and remains registered as a
  research lever. Production construction is unchanged.
- **The relaxation question is not permanently closed — it is
  RESEQUENCED behind the law.** The honest re-test is: repair the QB→WR
  under-coupling (A2), then re-freeze a carve on the repaired law. If
  the mandates are a correction for a law defect, they should become
  *unnecessary* once the defect is fixed, and only then should relaxing
  them help.

## Consequence for the queue

This strengthens the dependence repair (A2) from "next law lane" to the
**prerequisite for the entire construction-shape question**. It also
sharpens the review note filed against the strategy plan: sequencing
selection/construction work ahead of the law repair risks optimizing
against a known-misspecified objective, and this arm is the first direct
evidence of that cost.
