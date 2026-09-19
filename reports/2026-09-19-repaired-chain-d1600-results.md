# Expanded full-chain comparison: 1,600 candidates

Both complete CLI runs pass with 97 legal entries, 320 leverage plus 1,280 boom candidates, and 10,000 worlds. Restoring current-season inputs changes almost the whole selected book. Under the repaired models, its simulated chance of at least one 220+ lineup rises **13.500% to 17.195%**. The old-input models prefer the old book. These are conditional model comparisons, not demonstrated NFL improvement.

| Independent evaluation law | Repair minus control expected maximum | P220 change (percentage points) | GLOBAL proxy change |
|---|---:|---:|---:|
| control_I_audit | -1.111 | -0.720 | -0.006236 |
| control_H_audit | -3.958 | -4.000 | -0.025661 |
| salaryfix_I_audit | +1.301 | +1.340 | +0.008290 |
| salaryfix_H_audit | +4.299 | +6.050 | +0.033300 |
| control_equal_mixture | -2.534 | -2.360 | -0.015949 |
| salaryfix_equal_mixture | +2.800 | +3.695 | +0.020795 |

Under the repaired equal mixture, expected maximum rises **197.100 to 199.900**. Paired Monte Carlo 95% intervals are **[2.596, 3.004] points** and **[3.195, 4.195] percentage points** for P220. Under the control mixture, expected maximum falls 2.534 and P220 falls 2.360 percentage points; both corresponding intervals exclude zero. These intervals describe finite-world precision conditional on fitted laws, not uncertainty about model correctness. The repaired versus old-law disagreement grows at this pool size and must remain visible.

Only 37 of 1,600 candidates overlap between arms, and only **one of 97 ordinary selected lineups** overlaps. The first lineup changes. Every saved book is fully scoreable under every component audit: none uses the one extra player found only in the repaired frame. No missing score is imputed.

All eight declared prefixes improve all three metrics under the repaired mixture. Its first lineup improves 2.004 expected points and 0.150 percentage points P220; the control mixture instead penalizes that first lineup by 4.987 points and 0.485 percentage points. Eleven of the 12 repaired contest blocks improve all three metrics. The final two-row block gains P220 and proxy but loses 0.616 expected maximum. These comparisons concern fixed assignments, not a claim that greedy portfolio order optimizes each contest.

The WEMAX shadow does not establish an improvement: on the repaired pool, versus ordinary EMAX under the repaired mixture, it loses 0.126 expected maximum, changes P220 by +0.050 percentage points (interval spans zero), and changes proxy by -0.000231 (interval spans zero). Its new first lineup loses 2.516 expected points. The first lineup also loses under the old mixture. This is no basis for promoting the WEMAX shadow this weekend.

## Verification and scope

Control run `20260919T025751385273Z-2dc116c` took 462.72 seconds. Repair run `20260919T030727287666Z-2dc116c` took 420.13 seconds. Both completed inside the frozen 600-second cap on one CPU. Source is lab `2dc116c`; adapter/reader/protocol were frozen at production `170c3b46`. This is not a production-dose runtime estimate.

All input queries replay immutable saved results and refuse a cache miss. Each arm's complete frame and all five player banks are exactly identical to its corresponding D160 run. Candidate generation and selection therefore account for the difference between doses; forecasts did not drift. Original roster order is retained, candidate-index alignment is asserted, and original incumbent audit means are reproduced exactly. Independent hsim audit worlds reuse the CLI's exactly replayed calibration. GLOBAL proxy uses the same 48 historical constants and bandwidth 8.

The D160 result remains a separate study. Its small-pool gain must not be conflated with the D1600 gain or the archived D6400 usage-only factorial. Both equal-budget books are frozen before Sunday-main outcomes and can be settled regardless of entry. The historical target-prior changes are separately tested on this same expanded repaired pool.

[Protocol](2026-09-19-repaired-chain-d1600-protocol.md). [Full source, bank, book, cross-law, prefix and contest results](reviews/evidence/2026-09-19-repaired-chain-d1600-read.json). No live deployment, entry-policy change or Sunday-main outcomes are involved.
