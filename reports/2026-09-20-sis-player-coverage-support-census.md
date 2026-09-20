# SIS player-coverage support census

**Execution:** `scripts/sis_coverage_support_census.py`  
**Evidence:** `reports/reviews/evidence/2026-09-20-sis-coverage-support-census.json`  
**Outcome-free:** this census reads only SIS source rows and does not join player outcomes.

The SIS defender history contains 15,477 player-game rows, but one defense/alignment/week cell is sparse:

| alignment | cells | mean defenders | p10/p50/p90 defenders | mean coverage snaps | mean targets | mean top-defender target share | mean target HHI | cells with <3 defenders | cells with <10 targets |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Wide | 2,166 | 3.53 | 3 / 3 / 5 | 21.3 | 5.5 | 0.633 | 0.554 | 171 | 1,943 |
| Slot | 2,174 | 3.60 | 3 / 4 / 5 | 27.5 | 4.6 | 0.617 | 0.543 | 138 | 2,062 |

## Consequence

Raw one-game defender rates are not reliable enough for a receiver matchup feature. Most cells have fewer than ten targets, and the typical cell has only three or four defenders. The high target concentration (top defender receiving about 62–63% of targets; HHI about 0.54–0.55) means the data may still be useful for **coverage responsibility concentration**, but only after pooling multiple prior games and applying shrinkage.

The next SIS test should therefore use an 8-game or longer prior window, minimum aggregate coverage/target support, empirical-Bayes shrinkage toward defense/alignment and league priors, and a separate concentration feature. It should not use raw weekly defender efficiency or claim exact receiver-to-defender assignments without an assignment feed.
