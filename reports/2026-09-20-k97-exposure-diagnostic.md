# K97 exposure and unique-tail diagnostic

This is an outcome-blind diagnostic of the exact regenerated promoted K97
book. It asks which highly exposed players provide unique simulated 220+/230+
worlds when all rows containing that player are removed. It is a portfolio
insurance diagnostic, not a live selection rule.

## Method

The calculation uses the archived identity frame and the frozen incumbent and
corrected-HSIM `429 x 10,000` player-score banks. It reads only identity
columns from the frame and does not read any `actual` column or call a
provider. For each player, the control is the maximum simulated lineup total
across all 97 rows in each of 20,000 equal-mass worlds. The stress book removes
every row containing that player, then recomputes the maximum. `unique_220` and
`unique_230` count worlds in which the full book clears the threshold but the
player-removed book does not.

The exact result is in
`reports/reviews/evidence/2026-09-20-k97-exposure-diagnostic-result.json` and
the reproducible reader is
`reports/reviews/evidence/2026-09-20-k97-exposure-diagnostic.py`.

## Control and leading exposures

The full book has simulated maximum mean **200.577**, P220 **18.70%**, P230
**9.65%**, and P240 **4.765%**. Leading exposures and the effect of removing
each player are:

| player | rows | first 30 | mean-max loss | P220 loss | P230 loss | unique 220 | unique 230 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Justin Jefferson | 55 | 21 | 10.698 | 8.65 pp | 4.665 pp | 1,730 | 933 |
| Bijan Robinson | 45 | 13 | 7.675 | 7.505 pp | 4.225 pp | 1,501 | 845 |
| 49ers DST | 39 | 11 | 5.035 | 4.840 pp | 2.630 pp | 968 | 526 |
| Javonte Williams | 28 | 12 | 3.957 | 3.915 pp | 2.260 pp | 783 | 452 |
| Ladd McConkey | 28 | 2 | 4.405 | 4.430 pp | 2.465 pp | 886 | 493 |
| Drake London | 26 | 9 | 3.549 | 3.980 pp | 2.195 pp | 796 | 439 |
| Patriots DST | 24 | 11 | 2.629 | 3.040 pp | 1.575 pp | 608 | 315 |
| Dalton Schultz | 21 | 6 | 3.209 | 3.215 pp | 1.840 pp | 643 | 368 |

McConkey's `28` and `2` counts are independently reconciled in
`reports/2026-09-20-mcconkey-first30-reconciliation.md`; an older receipt said
the first 30 were clear, but positions 27 and 28 are flagged in the exact
final-vetter and promoted artifacts.

## Interpretation

The stress results show that exposure and simulated tail contribution are
linked. Removing a popular player often destroys many worlds that no other
row can cover. A blanket cap would therefore trade away tail coverage; the
diagnostic does not authorize a swap or a universal cap. McConkey is unusual
because he combines Questionable/no-props risk with material simulated tail
coverage, but this table cannot tell us whether he will be active or limited.

The next useful experiment is a risk-weighted shadow that prices a player's
status uncertainty against the unique-world loss. Compare no cap, a soft
10%/20% Questionable-no-props penalty, and a player-specific cap on the same
frozen book. Report whole-book and contest-prefix mean-max, P220/P230/P240,
unique-tail coverage, and the exact rows displaced. Keep the official-status
swap protocol separate from this prospective insurance experiment.

Result SHA-256: `e869d25be6f8a1b113c9bafb9745924f2c81a1cf44ad526df849f10af6349026`.
