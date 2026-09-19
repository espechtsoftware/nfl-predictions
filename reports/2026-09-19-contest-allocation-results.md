# Same-book contest allocation: one qualifying exchange

The frozen diagnostic found one exchange, **rows 70 and 86**, that improves all six modeled quantities in both affected contest blocks. It preserves all 97 rosters and Millionaire row 1. This nominates the allocation method for independent review and testing on the final book; it is not evidence that this particular exchange belongs in Sunday's different book.

Source was committed before execution at `f7cb5f9c`. [Protocol](2026-09-19-contest-allocation-protocol.md), [executable](reviews/evidence/2026-09-19-contest-allocation.py), and [complete result](reviews/evidence/2026-09-19-contest-allocation.json) retain the exact inputs, hashes and checks. The input is Thursday's D6400 archive with the previously reproduced diagnostic K97 extension, not the armed D12800/K97 build. Neither outcomes nor live entries were read or changed.

## Measured changes

Each row below is the change for a whole disjoint contest block. Emax is expected best lineup score. GLOBAL proxy is the fixed historical smoothed winner-score utility, not a contest-specific payout estimate. P220 changes are **percentage points**.

| Block | Component | Emax change | GLOBAL proxy change | P220 change (pp) |
|---|---|---:|---:|---:|
| 64–79, supersat25a | Incumbent | +0.598001 | +0.00072903 | +0.04 |
| 64–79, supersat25a | Hsim | +0.283360 | +0.00163899 | +0.27 |
| 80–95, supersat25b | Incumbent | +0.339678 | +0.00053460 | +0.01 |
| 80–95, supersat25b | Hsim | +0.285136 | +0.00070600 | +0.08 |

Equal-mixture block Emax gains are +0.440681 and +0.312407 points, summing to +0.753088. Equal-mixture block P220 gains are +0.155 and +0.045 percentage points. These are small changes. The +0.01 pp incumbent improvement in the second block is one additional simulated world out of 10,000.

There were two eligible pairs initially. The prespecified best-gain rule chose 70↔86; the next exhaustive pass found no eligible pair. The five-step budget was not exhausted. This is local termination under the declared pairwise constraints, not a global allocation optimum.

All other blocks are unchanged. The full 97-lineup book's per-world maximum and P220 are exactly unchanged. No additional 220+ lineup was retrieved. This allocation study therefore does not resolve the user's highest-priority supply-to-selection gap.

## Prefix distinction and validation

The K80 diagnostic prefix loses 0.027207 incumbent Emax points and 0.00003630 incumbent proxy, while its incumbent P220 rises 0.03 pp. Hsim K80 Emax rises 0.005914 and P220 rises 0.01 pp. K1/10/20/30/90/97 are unchanged. **Not every prefix improves**: K80 cuts through the actual 80–95 contest block and is a different objective from either affected disjoint contest.

Every input byte hash and generation matched. The fast exchange calculation matched direct recomputation on the synthetic fixture and accepted pair. All final block/component no-decrease checks, roster uniqueness, complete membership and fixed Millionaire row checks passed. Compute after download took 0.904 seconds with one BLAS thread.

## What this supports next

Ask the workstation agent to reproduce the swap and block deltas independently. Then assess the same frozen rule on the actual final pool/book, with complete score-bank identities and an independent evaluation where available. The archived banks were used for selection; searching these banks introduces optimism. Agreement of two components does not establish real-world calibration or profitability. The simulator disagreement documented in the [component-gap report](2026-09-18-week2-component-gap-results.md) remains unresolved.

The operator's contest order and sizes stay fixed in this proposal. No contest-specific payout weighting was invented. No live policy, upload, schedule, dose or entry count has been changed. In parallel, continue the separate search for improvements in which 97 lineups are selected, and trace hsim's mean offsets through calibration and player-role handling.
