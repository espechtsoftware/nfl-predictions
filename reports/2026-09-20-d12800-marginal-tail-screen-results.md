# D12800 marginal-tail screen: candidate 848 was the wrong replacement target

This is an outcome-blind diagnostic of the archived D12800 K97 book. For each of the 12,555 candidates, it counts the additional simulation worlds in which that candidate would make the current book maximum clear 220, 230, or 240 points. It then tests one-row replacements for the strongest marginal-tail candidates. The reader uses only the archived frame identity/name/DK-id columns, candidate rosters, the K97 book, the receipt, and the two 10,000-world selection banks. It does not read current outcomes or provider data and cannot alter a live book.

The control book's max-of-K97 distribution in the pooled 20,000 worlds is:

* mean of the per-world maximum: **203.4508**;
* P(max-of-K97 ≥ 220): **22.255%**;
* P(max-of-K97 ≥ 230): **12.120%**;
* P(max-of-K97 ≥ 240): **6.280%**.

## Marginal candidates differ from individual-score candidates

The earlier candidate-tail screen found candidate 848 near the top by individual mean/P220/P230, but its one-row swaps did not improve the portfolio maximum. This screen finds candidates that add new high-score worlds after the existing book is already present. The tail-ladder ranking is `new-220-worlds + 2 × new-230-worlds + 4 × new-240-worlds`.

| candidate | roster | new 220 worlds | new 230 worlds | new 240 worlds | individual mean | individual P220/P230/P240 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1334 | Chargers / Chris Moore / Dalton Schultz / Lamar Jackson / Juwan Johnson / Justin Jefferson / Javonte Williams / Zay Flowers / Bijan Robinson | 24 | 16 | 13 | 144.877 | 0.840% / 0.365% / 0.180% |
| 2765 | Broncos / Terry McLaurin / Saquon Barkley / John Bates / CeeDee Lamb / D'Andre Swift / Jayden Daniels / Drake London / Ladd McConkey | 23 | 15 | 11 | 132.550 | 0.285% / 0.135% / 0.065% |
| 5211 | 49ers / Mark Andrews / Lamar Jackson / Devaughn Vele / Zay Flowers / Drake London / Bijan Robinson / Bucky Irving / Ted Hurst III | 16 | 17 | 11 | 139.390 | 0.790% / 0.385% / 0.155% |
| 2396 | Ravens / David Njoku / Justin Herbert / Justin Jefferson / Zay Flowers / Tre' Harris / Bijan Robinson / Adonai Mitchell / Ashton Jeanty | 18 | 17 | 10 | 143.482 | 0.670% / 0.315% / 0.130% |
| 2148 | Patriots / Kalif Raymond / Derrick Henry / Dalton Schultz / Justin Jefferson / Ja'Marr Chase / Xavier Hutchinson / C.J. Stroud / Bijan Robinson | 19 | 10 | 13 | 141.483 | 0.580% / 0.240% / 0.115% |

Candidate 7399 is the strongest individual marginal-P220 candidate (29 new 220 worlds), while candidate 1334 is the strongest high-threshold ladder candidate. This is why sorting candidates by individual P220 alone is insufficient: the relevant quantity is the candidate's incremental coverage after the book's existing correlated rows are accounted for.

## One-row shadow results

For each candidate, the experiment tried replacing every one of the 97 delivered rows and kept the best replacement for each portfolio metric. The best pooled improvements were:

| candidate | best Δ max mean | best Δ P(max ≥220) | best Δ P(max ≥230) | best Δ P(max ≥240) |
| ---: | ---: | ---: | ---: | ---: |
| 1334 | +0.0024 | +0.080 pp | +0.060 pp | +0.060 pp |
| 2765 | +0.0031 | +0.075 pp | +0.055 pp | +0.050 pp |
| 5211 | −0.0130 | +0.040 pp | +0.065 pp | +0.050 pp |
| 2396 | −0.0034 | +0.050 pp | +0.065 pp | +0.045 pp |
| 2148 | +0.0003 | +0.055 pp | +0.030 pp | +0.060 pp |
| 7399 | −0.0028 | **+0.105 pp** | +0.025 pp | +0.045 pp |

These are descriptive maxima over replacement positions in the same selection worlds, so they are a search result rather than an unbiased estimate. Candidate 1334 is the cleanest pooled compromise: it improves every max metric in its best row swap. Candidate 7399 is the strongest 220-only arm but gives back max mean and most of the 230 advantage. The displaced rank depends on the objective (for candidate 1334, rank 80 gives the best P220, rank 72 P230, rank 41 P240, and rank 8 max mean).

## Bank-component stability

The equal-mass pooled result should not be treated as settled. The component shadows disagree in magnitude:

* Candidate 1334's best max-mean change is +0.0089 in the incumbent component and +0.1086 in corrected hsim. Its P220 change is 0.000 pp in incumbent versus +0.230 pp in corrected hsim.
* Candidate 2765's best max-mean change is −0.0070 in incumbent versus +0.1229 in corrected hsim.
* Candidate 5211 is the reverse-shaped case: +0.0352 incumbent max mean versus +0.0445 corrected hsim, with P220 gains of +0.070 pp and +0.080 pp respectively.

The bank split is a useful finding. A candidate that wins only in one component is a model-specific lever, while a candidate that improves both components and an independent audit bank is a stronger selector candidate. The component results do not authorize changing the live law.

## Next experiment

Use fresh, independently generated selection/audit worlds and freeze the candidate identities before opening any outcome data. Compare the current book with one-row shadows for candidates 1334, 2765, 7399, 5211, and 2396 at their objective-specific displaced ranks. Preserve both bank components and report max mean, P220, P230, P240, row-level rates, roster overlap, and a world-bootstrap interval. If the gain persists in both components and the fresh audit, run a full tail-ladder selector shadow on the complete eligible candidate pool with the existing exposure constraints. Keep candidate generation, selection, and first-row contest ordering separate until that shadow is complete.

Evidence: [marginal-tail reader](reviews/evidence/2026-09-20-d12800-marginal-tail-screen.py), [result JSON](reviews/evidence/2026-09-20-d12800-marginal-tail-screen-result.json). Result SHA256: `f995aa77495cb2858ce855df5512d30161a61e2eeb155d9c479fc8b556b92712`.
