# Exact-N order-invariant source amendment

Date frozen: 2026-08-15 17:07 CDT  
Parent protocol: `reports/2026-08-15-exact-n-scorefree-protocol.md`  
Evidence available while freezing: score-free CBWU order audit and repair only;
no realized lineup score, rank, ownership or payout value

## Why this amendment is required

The exact-N protocol was frozen before the canonical CBWU pool was shown to be
materially seed-order-sensitive. The subsequently frozen CBWU-OI repair passed
its score-free gate and returns exact candidate and selected identities under
all five input rotations. Exact-N therefore needs an explicit source rule
before it is wired; otherwise a later implementation could choose whichever
of the order-sensitive production pool or the order-invariant repair is more
convenient.

This amendment changes no exact-N target line, selector ranking, threshold or
admission gate. It only identifies the candidate/control source and separates
selector attribution from production context.

## Frozen attribution comparison

For each of the same 54 slates:

1. Reconstruct the five immutable R0--R4 books and score blocks used by the
   CBWU audit.
2. Reconstruct canonical production CBWU in the registered R0--R4 order and
   prove its exact-80 selected identities.
3. Reconstruct CBWU-OI from the complete distinct union at the fixed canonical
   candidate budget. Prove its candidate and exact-80 selected identities are
   byte-identical under all five cyclic input rotations.
4. The exact-N **attribution control** is the first N entries of the CBWU-OI
   exact-80 selected order.
5. The exact-N treatment is the unchanged cardinality-aware selector from the
   parent protocol applied to the same CBWU-OI candidate totals.
6. N=80 is parity-only and must exactly reproduce the complete CBWU-OI
   selected order; it is not a treatment.

The parent protocol's score-free falsifier is evaluated only for treatment
versus attribution control. This isolates the cardinality-aware selector from
the already-observed CBWU construction change.

## Production-context comparison

Also report, but never gate or tune on, the treatment versus the first N
entries of canonical production CBWU. This is explicitly labeled a composite
construction-plus-selector contrast. It exists so the operator can understand
what a prospective small-book shadow would change relative to the current
money path; it is not evidence attributing the difference to exact-N alone.

For both controls, report only the score-free metrics already registered in
the parent protocol: identities, overlap, per-block and aggregate
194/200/210/230 simulated coverage, individual tail support and simulated
mean. Do not query or join realized results.

## Consequence and order

A pass licenses only a separately identified 2026 pre-lock small-book shadow.
It does not change the 80-entry production book or the UI default. The
score-free ATLAS attainable-world diagnostic remains ahead of exact-N in the
frozen execution order. This amendment may be implemented while ATLAS is
pending, but exact-N must not be launched first.

