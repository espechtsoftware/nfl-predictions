# D12800 candidate-tail diagnostic: high 220+ supply is reaching selection

This is an outcome-blind diagnostic of the archived D12800 run. It asks whether the selector is discarding candidates with the strongest simulated 220+ and 230+ tails before they reach the delivered K97 book. It reads only the archived frame identity/name/DK-id columns, candidate roster and selection metadata, the two 10,000-world selection banks, the archived book, and the receipt. It does not read realized outcomes or provider values.

The archive is `20260919T153008787414Z-2dc116c`, D12800 (2,560 leverage / 10,240 boom), with 12,555 candidates and 97 delivered rows. Both equal-mass banks were evaluated together (20,000 worlds). The manifest and input hashes are recorded in the evidence result.

## What is getting selected

The current book is substantially enriched for simulated high scores:

| population | mean simulated points | P(220+) | P(230+) |
| --- | ---: | ---: | ---: |
| all 12,555 candidates, average | 125.697 | 0.134% | 0.052% |
| selected K97, average | 137.183 | 0.550% | 0.247% |
| selected / pool ratio | 1.09x | 4.09x | 4.71x |

The selected book's maximum is the same head candidate as the pool maximum: candidate 2207 (the first delivered row), with mean 150.334, P(220+) 1.28%, and P(230+) 0.61%. The selector therefore is not failing to identify the strongest raw high-tail candidate.

The high-tail objective is also represented more faithfully than a mean-only ranking. Among the top candidates by each metric, the delivered K97 overlaps as follows:

| candidate ranking | mean | P(220+) | P(230+) |
| --- | ---: | ---: | ---: |
| top 97 | 18 | 35 | 33 |
| top 500 | 46 | 68 | 69 |
| top 1,000 | 59 | 77 | 78 |

This pattern is consistent with a selector that values high-tail potential and portfolio coverage rather than simply copying the top 97 by average points. The selected rows' archived selection metadata is enriched as well: `sel_mean` averages 132.830 versus 125.039 for the full candidate pool, and `sel_p194` averages 2.637% versus 1.227%.

## The high-tail candidate that is omitted

Candidate **848** is the strongest unselected candidate under all three simple orderings in this archive. It ranks 3rd by simulated mean (147.359), 4th by P(220+) (1.06%), and 3rd by P(230+) (0.50%). Its upstream selection metadata is also strong (`sel_mean` 140.683; `sel_p194` 3.09%).

Candidate 848 is not an isolated missed opportunity. It shares seven of nine roster players with each of the selected candidates at delivered ranks 8, 46, and 97. Those selected rows are:

* rank 8, candidate 1569;
* rank 46, candidate 1819; and
* rank 97, candidate 322.

That overlap makes the omission consistent with the selector's portfolio objective: candidate 848 is a very strong version of a scenario already represented several times. This is evidence for a diversification tradeoff, not evidence that the 220+ tail is being ignored. It does not prove that the tradeoff is optimal; the three near-duplicate selected rows leave a useful test case.

## What this means for the current production question

The archived book does not support replacing the selector with a raw P(220+) sort. The delivered book already multiplies the candidate-pool P(220+) and P(230+) rates by roughly 4x–5x, and it retains more of the high-tail top 500 than of the mean top 500. A raw tail sort would likely spend several rows on correlated versions of the same high-scoring scenario and reduce coverage of other winning paths.

The evidence does support testing the **strength of the diversity penalty**. Candidate 848 is a concrete audit case where a high-tail row is rejected while several highly overlapping rows remain. The right question is whether swapping one of those near-duplicates for 848 raises the portfolio's max-of-97 simulated distribution without reducing the chance of a 220+ row elsewhere in the book.

## Next experiment

Run a frozen, outcome-blind selector shadow on this same candidate pool and banks:

1. Keep the current objective and constraints as the control.
2. Add a tail-aware candidate score using pooled P(220+) (and a second arm using P(230+)); do not use actual scores or provider data.
3. Add a roster-overlap penalty or cap only after a candidate is already in the high-tail shortlist. This avoids replacing a strong candidate with a low-quality but novel row.
4. Evaluate the control and each shadow book with the same 20,000 worlds: average row P(220+)/P(230+), max-of-K97 mean and tail, number of rows above the high-tail thresholds, pairwise roster overlap, and the displaced-row cost.
5. Specifically force candidate 848 into a single shadow slot in place of ranks 8, 46, and 97 one at a time. This isolates whether the diversity tradeoff is helping or merely hiding an obvious upgrade.

The shadow should be judged by the portfolio distribution, not by whether it contains every top-ranked individual row. If a tail-aware arm improves max-of-K97 P(220+) and P(230+) while holding overlap and mean steady, it is a candidate for next week's selector experiment. No production code or live book should be changed from this diagnostic alone.

Evidence: [diagnostic reader](reviews/evidence/2026-09-20-d12800-candidate-tail-diagnostic.py), [result JSON](reviews/evidence/2026-09-20-d12800-candidate-tail-diagnostic-result.json). The result SHA256 is `0a32c65db31e56e2d8fe3303843dc69c79c3cdabfe4f836562f4326178caf2d7`.
