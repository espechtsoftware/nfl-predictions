# Review of the stack-depth payoff study

Reviewed production study commit `81f8250f` (`reports/2026-09-20-stack-depth-payoff-read.md`) and checked its conclusion against the regenerated K97 book. The study is useful for designing next week's experiment. It does not justify changing today's entered lineups.

## What the study establishes

The receiving-concentration read is directionally strong: two receivers or tight ends account for most of the top-five receiving output even when the quarterback scores well. The report also correctly labels its third-receiver rates as upper bounds because it selects the receivers after seeing the game.

The historical candidate panel points in the same direction, but its deep-stack cells are small. Depth 3 has 598 candidates and depth 4 has only 9. The depth-3 mean is lower and its 194+ rate is indistinguishable from depth 2 in this panel; that is evidence against rewarding deep stacks by default, not evidence that every three-player stack should be removed. The Week-1 Millionaire field is one realized slate and is useful context, not a policy test.

For future reads, the selection comparison should report candidate share, selected share, and the selection odds ratio together. “Selected 53% versus 31%” is informative only when the denominators and slate weighting are explicit. A slate-cluster bootstrap is also needed because the depth-4 cell is rare.

## Today's book

The outcome-blind regenerated promoted book contains 97 rows:

| Same-team WR/TE count with the QB | Rows |
|---:|---:|
| 2 | 87 |
| 3 | 8 |
| 4 | 2 |

The Millionaire row is depth 2. Both depth-4 rows are in the $5 Flea Flicker. The four deep rows in the first 30 are two depth-3 and two depth-4 rows, all in the Flea Flicker block; none is the Millionaire row. The depth-3 rows otherwise sit in the small satellite/qualifier contests. This keeps the highest-value entry from carrying the construction pattern the study is questioning.

## Decision for today

Keep the regenerated book unchanged for stack-depth reasons. Do not manually replace the two depth-4 Flea rows immediately before lock. There is no preregistered live authority for that construction intervention, the depth-4 historical cell is nine candidates, and a manual replacement would trade a known, fully vetted row for an untested row while risking the contest-row mapping. Continue using the existing official-out/inactives replacement process only.

## Week-3 experiment

Run a paired, outcome-blind construction shadow on the same frozen candidate pool and compute budget:

1. Control: current construction law.
2. Primary treatment: maximum depth 3 (forbid depth 4).
3. Secondary treatment: maximum depth 2.

Freeze all three books before outcomes. Report mean, P220, P230, max-of-K, and the contest-prefix cost. Make realized max-of-K and 200+/210+ clears the primary read, with slate-cluster intervals and a minimum count for the depth-3/depth-4 cells. Do not promote either treatment from the historical Week-1 field alone. A depth-4-only restriction is the first practical intervention; a blanket depth-2 rule should require a positive realized tail result because depth-3 stacks can pay when a slate's targets concentrate unusually well.

No current-week realized scores, standings, settlement, or entry keys were opened for this review.
