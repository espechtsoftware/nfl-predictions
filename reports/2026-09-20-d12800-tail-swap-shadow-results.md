# D12800 tail-candidate swap shadow: candidate 848 does not improve the portfolio

This is a frozen, outcome-blind follow-up to the candidate-tail diagnostic. It keeps the archived K97 book unchanged except for one row, substitutes candidate 848 into delivered ranks 8, 46, and 97, and evaluates each book across the same 20,000 pooled simulation worlds. It reads only the archived frame identity/name/DK-id columns, candidate rosters, the book, the receipt, and the two selection banks. No realized outcomes or provider data were read, and no live book was changed.

Candidate 848 is the strongest unselected candidate under the simple pooled mean, P(220+), and P(230+) rankings. It shares seven of nine players with the displaced row in every tested swap. The control book's max-of-K97 metrics are:

* mean of the per-world book maximum: **203.4508**;
* P(max-of-K97 ≥ 220): **22.255%**;
* P(max-of-K97 ≥ 230): **12.120%**.

| replacement | max mean | Δ max mean | P(max ≥220) | Δ | P(max ≥230) | Δ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 203.4508 | — | 22.255% | — | 12.120% | — |
| candidate 848 for rank 8 | 203.4299 | −0.0208 | 22.260% | +0.005 pp | 12.115% | −0.005 pp |
| candidate 848 for rank 46 | 203.4175 | −0.0333 | 22.255% | 0.000 pp | 12.075% | −0.045 pp |
| candidate 848 for rank 97 | 203.4288 | −0.0220 | 22.225% | −0.030 pp | 12.105% | −0.015 pp |

The swaps raise the average individual-row P(220+) slightly, but they do not raise the portfolio's max-of-97 distribution. Two of the three swaps lower P(230+), and all three lower max-mean. This is the expected signature of a highly correlated candidate: its individual tail is strong, but it adds little new high-score coverage after the existing book is present.

This result supports keeping the current diversity mechanism while testing it more precisely. The earlier diagnostic showed that high-tail candidates are reaching the book: selected rows average P(220+) 0.550% versus 0.134% for the full pool, and P(230+) 0.247% versus 0.052%. Candidate 848's omission is not by itself a defect. A better next arm should score **marginal portfolio tail coverage**—the additional worlds in which a candidate raises the current book maximum—rather than individual P(220+) alone.

The next shadow should therefore compare the current selector with a tail-aware marginal utility that rewards `max(current_book, candidate)` at 220, 230, and 240 thresholds, while retaining a mean term and the existing exposure constraints. Report both the individual-row and max-of-K97 metrics so a high individual score cannot masquerade as a portfolio improvement. Keep the run frozen and outcome-blind; do not promote a selector change from this single archive.

Evidence: [shadow reader](reviews/evidence/2026-09-20-d12800-tail-swap-shadow.py), [result JSON](reviews/evidence/2026-09-20-d12800-tail-swap-shadow-result.json). Result SHA256: `ca10f94efd0526745c12135058a4965de39e338a74503ba0b4a5bf080e4f31a9`.
