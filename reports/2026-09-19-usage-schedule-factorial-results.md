# Usage and game-line corrections: combined sensitivity

Restoring prior-week usage materially changes selection. Updating the game lines after usage is restored has no clear additional selection benefit in this experiment. Both input defects remain real; their repair should be judged by the input contract and validation, not by choosing whichever simulated probability is largest.

Frozen protocol `79c8c0e8`, executed source `780814b1`, live-input implementation `40a9be9`. [Complete result](reviews/evidence/2026-09-19-usage-schedule-factorial.json), [runner](reviews/evidence/2026-09-19-usage-schedule-factorial.py), [protocol](2026-09-19-usage-schedule-factorial-protocol.md). Runtime 66.67 seconds. All identity, finite-score, fixed-input and unique-roster guards passed; no budget cap. Existing eager division warnings in calibration did not produce nonfinite outputs.

The four cases share projected means, 6,400 candidates, the archived incumbent score bank and canonical game-id ordering. A uses missing usage and benchmark lines; B restores usage; C updates lines; D does both. Each selects 97 lineups under the unchanged equal-mass incumbent/hsim selector. Each hsim audit uses independent final worlds with its selection calibration held fixed.

## Complete whole-book cross-law comparison

Cells report expected maximum / percentage of worlds with at least one 220+ lineup. These are conditional model quantities, not estimated real-world success probabilities.

| Evaluation bank | A book | B book | C book | D book | Original archived book |
|---|---:|---:|---:|---:|---:|
| Incumbent selection worlds | 190.829 / 7.39% | 190.920 / 7.85% | 190.895 / 7.41% | 190.997 / 7.75% | 190.769 / 7.51% |
| A independent hsim | 209.766 / 29.86% | 206.629 / 26.02% | 209.457 / 29.43% | 206.817 / 26.18% | 209.666 / 29.81% |
| B independent hsim | 211.155 / 32.30% | 214.109 / 37.33% | 211.274 / 32.60% | 214.023 / 37.31% | 211.430 / 32.76% |
| C independent hsim | 210.419 / 31.12% | 207.560 / 27.41% | 210.425 / 31.00% | 207.700 / 27.64% | 210.569 / 31.18% |
| D independent hsim | 212.472 / 34.10% | 215.548 / 39.40% | 212.756 / 34.32% | 215.505 / 39.24% | 212.864 / 35.06% |

Under D's independent audit, the preregistered differences are:

| Comparison | Expected-max difference (MC 95% interval) | 220+ coverage difference, percentage points (MC 95%) | GLOBAL proxy difference |
|---|---:|---:|---:|
| D − A: both corrections | +3.0325 [2.8324, 3.2325] | +5.14 [4.5335, 5.7465] | +0.030674 |
| D − B: lines after usage | −0.0432 [−0.1525, 0.0661] | −0.16 [−0.5182, 0.1982] | −0.000570 |
| D − C: usage after lines | +2.7485 [2.5483, 2.9487] | +4.92 [4.3217, 5.5183] | +0.027856 |

The intervals quantify finite-world Monte Carlo uncertainty conditional on these models and inputs. They do not quantify uncertainty about actual football performance. The old-usage laws prefer old-usage books: this disagreement is visible, not suppressed. No independent incumbent audit was retained, so this is not full independent validation of the dual-law selector.

## Membership, order and scope

D changes 44 of A's 97 memberships, 18 of B's, 47 of C's and 45 of the original archived book's. Usage changes the first candidate from 1231 to 1171; line changes alone do not. Under D's audit, D−A improves expected max, P220 and GLOBAL proxy at all declared prefixes 1/10/20/30/40/80/90/97. That is conditional prefix evidence, not a claim that every contest block or model improves: all 12 contest blocks and all cross-law metrics are retained in the result file.

A is a co-run control with canonical game order. It does not reproduce the archived benchmark-order bank, and its selected book overlaps the archived one at 70/97. The preceding exact replay separately established the original simulator's byte-for-byte reproduction. This ordering distinction prevents attributing all differences from the archived book to usage or line values.

The experiment holds production means and TabPFN marginal shapes fixed. A complete repaired-pipeline rehearsal still needs repaired features, refreshed TabPFN cache, regenerated production means, current candidate generation and the explicit live game-input path. The completed small live CLI rehearsal proves execution mechanics with current live inputs; it did not use the repaired scratch features. No live adoption, money allocation, timer change, current lineup outcome read or bank 991 read occurred.
