# Exact-N contest-book score-free protocol

Date frozen: 2026-08-15 14:54 CDT

## Purpose

The adopted 80-entry CBWU selector is prefix-invariant: rerunning its same
194-world-coverage greedy algorithm for a smaller N returns the same first N.
Therefore the independent review's literal rerun cannot improve a 1-, 3-,
20- or 40-entry book. This protocol tests one genuinely cardinality-aware,
tail-first selector without reading realized outcomes.

## Fixed source and control

- Use the same frozen R0--R4 CBWU candidate books and five 10,000-world blocks
  as the incumbent forensic 54-slate corpus.
- Reconstruct the canonical fixed-budget CBWU pool exactly once per slate.
- For each N in `1, 3, 20, 40`, the control is exactly the first N identities
  of the reproduced incumbent 80-entry selection.
- N=80 is a parity-only control and must reproduce all incumbent identities and
  order. It has no treatment.
- No actual score, contest rank, payout, realized ownership or post-lock field
  input may be queried or passed to the selector.

## One frozen treatment

The score-free target line depends only on purchased cardinality:

| Entries | Primary target |
|---:|---:|
| 1 | 230 |
| 3 | 230 |
| 20 | 210 |
| 40 | 200 |

Select exactly N entries greedily from the full canonical pool. At every step,
rank each remaining candidate lexicographically by:

1. minimum marginal primary-target worlds added across R0--R4;
2. total marginal primary-target worlds added across R0--R4;
3. minimum and then mean individual primary-target probability across blocks;
4. minimum and mean individual 210 probability;
5. minimum and mean individual 194 probability;
6. overall simulated mean; and
7. lower canonical candidate index.

This is a fixed robust-tail objective, not a line sweep. It always fills
exactly N even if primary-target coverage saturates. N=1 is thereby a robust
individual-tail choice rather than the accidental first step of an 80-way
194 cover.

## Score-free falsifier

For each N, report exact identities, overlap, per-block and aggregate
194/200/210/230 coverage, individual tail support, and simulated mean. A
treatment may proceed only to a 2026 pre-lock shadow if all are true:

1. exact N, uniqueness and legality pass;
2. aggregate coverage at that N's primary target strictly improves;
3. primary-target coverage strictly improves in at least three of five blocks;
4. aggregate 194 coverage retains at least 90% of control; and
5. the N=80 parity control is exact on every slate.

Failure closes this treatment without trying another target mapping on the
historical corpus. Passage is not money adoption and cannot license a
retrospective lineup-score comparison. Promotion requires books frozen before
2026 locks and the project's distinct-slate tail-first prospective rule.
