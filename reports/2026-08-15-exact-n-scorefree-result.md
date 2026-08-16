# Exact-N score-free result

**Result date:** 2026-08-15 CDT  
**Evidence class:** outcome-free, cardinality-specific selector falsifier  
**Disposition:** valid; pre-lock shadows licensed for N=1, N=3 and N=20;
N=40 closed

## Executive result

The strict runner reproduced every immutable source and the CBWU-OI exact-80
control on all 54 slates, then evaluated the preregistered robust-tail selector
at N=`1/3/20/40` using 50,000 worlds per slate. It read no realized lineup
score, ownership, rank, payout or post-lock field input.

N=`1`, `3` and `20` pass all five frozen score-free conditions and are licensed
only as separately identified 2026 pre-lock small-book shadows. N=`40` fails
because aggregate 200-point coverage declined and improved in only one of five
blocks. No result changes the 80-entry production book or automatically turns
on a UI selection.

## Frozen-gate results

| N | Primary target | Control primary coverage | Treatment primary coverage | Absolute delta | Relative delta | 194 retention | Improved blocks | Result |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 230 | 0.0005137 | 0.0005319 | +0.0000181 | +3.53% | 91.64% | 3 / 5 | pass; shadow licensed |
| 3 | 230 | 0.0011930 | 0.0012793 | +0.0000863 | +7.23% | 90.07% | 5 / 5 | pass; shadow licensed |
| 20 | 210 | 0.0330511 | 0.0335863 | +0.0005352 | +1.62% | 96.80% | 5 / 5 | pass; shadow licensed |
| 40 | 200 | 0.1145607 | 0.1144978 | -0.0000630 | -0.05% | 98.60% | 1 / 5 | fail; closed |

All four cardinalities passed exact-N, uniqueness, production legality and the
exact N=80 parity control. The only failures were N=40's two primary-target
improvement conditions.

## Descriptive season robustness

These season splits were not additional gates and do not alter the frozen
disposition. They show whether the aggregate signal is concentrated in one
season. `+ / = / -` counts slates with positive, tied or negative primary-
target coverage deltas.

| N | 2023 mean delta (+/=/-) | 2024 mean delta (+/=/-) | 2025 mean delta (+/=/-) | Mean control/treatment identity overlap |
|---:|---:|---:|---:|---:|
| 1 | +0.0000356 (9/7/2) | +0.0000078 (6/10/2) | +0.0000111 (6/8/4) | 0.44 / 1 |
| 3 | +0.0001033 (11/2/5) | +0.0000578 (13/1/4) | +0.0000978 (13/2/3) | 1.37 / 3 |
| 20 | +0.0004589 (16/0/2) | +0.0005256 (15/0/3) | +0.0006211 (14/1/3) | 14.26 / 20 |
| 40 | -0.0000200 (9/0/9) | -0.0001189 (7/0/11) | -0.0000500 (8/0/10) | 32.46 / 40 |

N=3 and N=20 have positive mean deltas in every season. N=40 has negative
mean deltas in every season. The modest identity overlaps confirm that the
cardinality-aware treatment is changing book membership rather than merely
reordering the incumbent prefix.

## Interpretation

- The result supports the user's premise that low-entry contests need a
  cardinality-specific approach rather than merely taking the first N members
  of an 80-entry book.
- N=3 is the clearest score-free signal because its 230-point coverage improves
  in all five independent blocks and has the largest relative lift.
- N=20 also improves in all five blocks while retaining materially more of the
  194-point control coverage.
- N=1 passes at the boundary: three blocks improve, two decline, and 194-point
  retention is 91.64%. It should remain a clearly labeled prospective shadow.
- N=40 should continue using its incumbent prefix/control pending a genuinely
  new, prospectively frozen mechanism. The historical target mapping may not
  be swept after this failure.

This comparison isolates the cardinality-aware selector within the
order-invariant CBWU-OI pool. Its separately reported comparison with current
canonical production is composite context, not selector attribution. Neither
comparison is a historical ROI or realized-score estimate.

## Mechanical receipts

- Cloud Run execution: `exact-n-scorefree-v1-jv7r4`
- Immutable image digest:
  `sha256:ad4604d86f1b1f7938136650f3d3940c9f1d6edd6a3427d618e6f943822602c8`
- Exact image code SHA: `545ddae1b8e1256fde8e345683e0004aa5463b5e`
- Result JSON SHA-256:
  `2af0549c1880529d1c9380f28b8e9565c5ed3833db23f1b2bc128ddccea8b287`
- Execution receipt SHA-256:
  `d501daa6cda79049a81319337a3029e0c53bab528f49a8e518d057e4079d8609`
- Slates: 54
- Source artifacts: 270
- Worlds per slate: 50,000
- Realized outcomes read: no
- Selector tuned after result: no
- Historical arm or production change licensed: no

## Next operational action

Preserve N=`1/3/20` as separate, labeled 2026 pre-lock shadow books in the
small-contest workflow and evaluate them under the project's prospective
distinct-slate tail-first promotion rule. Do not expose them as a default
money choice until that prospective evidence exists. Keep N=`40` on the
incumbent control.
