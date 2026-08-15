# CBWU seed-order result and order-invariant repair protocol

Date: 2026-08-15 15:10 CDT

Status: score-free result harvested; repair frozen before implementation

Source run: `20260815-cbwu-seed-order-scorefree-v1`

## Result

The strict create-only harvest passed every identity, source, coverage and
outcome-denial check. The audit used all five immutable R0--R4 native books on
54 slates, held the canonical R0 candidate budget fixed, and evaluated all 216
noncanonical cyclic order comparisons without querying realized score, rank,
ownership or payout.

The mechanism is materially order-sensitive:

- all 216 comparisons changed candidate identities;
- all 216 comparisons changed selected exact-80 identities;
- candidate Jaccard versus canonical had mean `0.5069092682` and minimum
  `0.2636815920`;
- selected Jaccard had mean `0.3672573525` and minimum `0.0884353741`; and
- simulated selected-world coverage moved between `-0.06422` and `+0.04312`
  versus canonical, with mean `-0.0003603704`.

The terminal disposition is `cbwu-order-sensitive-requires-repair`. This does
not license choosing the historically or simulationally favorable cyclic
order. It also does not invalidate the deterministic production receipt: the
money path always uses the registered R0--R4 order. It does show that the
candidate-admission mechanism depends strongly on an otherwise arbitrary
first-supplier/quota ordering and must not be inherited unquestioned by ATLAS
or exact-N.

Machine report:
`reports/cbwu-seed-order-runs/20260815-cbwu-seed-order-scorefree-v1/report.json`
with SHA-256
`746f745a0f92e2123eb6cb555d4a381b1bc44c7561249e5ea29db458a155c7f6`.

## Frozen repair: CBWU-OI-v1

The sole first repair is a complete-union, order-invariant admission rule. It
uses the same five native books, the same 10,000 worlds per seed, the same
canonical R0 candidate-count budget, the same 194 simulated support line, and
the unchanged exact-80 selector.

1. Validate all five native books and align their player rows exactly.
2. Form the complete set of distinct nine-player rosters across R0--R4.
   Canonical roster identity is the lexicographically sorted player-ID tuple.
   Input iteration order and first-supplier attribution are forbidden from the
   identity or ranking rule. Tags are the sorted union of all native tags and
   all supplying seed labels.
3. Cross-score every distinct roster in all five world blocks.
4. Apply the existing deterministic `select_tail_entries` law at line 194 to
   the complete union, requesting exactly the canonical R0 candidate budget.
   This is candidate admission, not a realized-score selector. Ties inherit
   the canonical roster-key order fixed in step 2.
5. Apply the unchanged exact-80 selector to the retained fixed-budget book.

No actual score, rank, selected historical membership, ownership or payout may
be loaded. No alternative support line, source quota, seed weight, candidate
budget or tiebreak may be tried after this result.

## Score-free gate

Run the canonical order and all four cyclic rotations on all 54 slates. The
repair is mechanically valid only if candidate and selected identities are
exact across every rotation. It survives the score-free admission gate only
if, against canonical CBWU:

1. aggregate selected-world coverage at 194 strictly improves;
2. selected-world coverage improves in at least three of five seed blocks;
3. mean selected pair coverage is at least 90% of control;
4. mean selected triple coverage is at least 90% of control; and
5. every slate returns the exact frozen candidate budget and exactly 80 legal,
   unique selected rosters.

A failed invariant kills this repair. A valid but non-improving result closes
CBWU-OI-v1 without changing production. A passing result licenses a separately
identified pre-lock 2026 shadow and allows ATLAS/exact-N to consume the
order-invariant book; it does not by itself authorize retrospective selection
of an order or silently replace the money policy.
