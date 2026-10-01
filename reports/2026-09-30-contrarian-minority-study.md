# Do the pros run a contrarian minority, and do wins come from it?

Production (workstation), 2026-09-30. The operator's question via the laptop (`7a3a5764`): "a small percentage of the
professional players' lineups each week go against the grain and pick a game that isn't expected to be a shootout and
hit it heavily, and perhaps just pick players that aren't expected to perform well". **Descriptive; changes nothing in
Week 4.** No user names here.

**Answer: contrarian lineups exist, but they do not carry wins, and the top users show no deliberate contrarian sleeve.**
- Lineups stacking a low-total game are 13–15% of every week's Millionaire field: of the top users' portfolios, of the
  mid-field's, of everyone's.
- They reach the top 1% at **0.33–0.73×** the rate of other lineups (all three weeks; intervals exclude parity).
- **None of the three 2026 winners and 1 of 17 2025 winners** was built on a bottom-third-total game.
- The contrarian element in winners is **individual low-owned pieces around a chalk core**, not a fade of whole games.

## Definitions and information time

Each lineup is matched by DK name to the week's **pre-lock** T-70 frame. Less than 0.8% of W1 lineups and 0.2% of W2/W3
lineups were unmatched and dropped.
- **Primary stack:** the QB plus at least one same-team RB/WR/TE (85–88% of lineups have one).
- **Its game's total:** the frame's pre-lock `game_total`, ranked among the slate's 12–13 games into thirds.
- **Contrarian (a):** the primary stack in a bottom-third-total game.
- **Contrarian (b):** ≥ 3 players outside their position's top 24 by our pre-lock projection, or ≥ 4 players under 5%
  owned.

Ownership is the realized Millionaire ownership. It is fixed at lock but not known before it, so (b) is descriptive
only.

Scripts: `reports/lab-handoffs/2026-09-30-contrarian/contrarian_study.py`. Inputs are private (`~/q11-study`).

## 1. The field, the top 1% and the winners (2026)

| Week (games) | Lineups | (a) share: field → top 1% → top 0.1% | Top-1% rate (a) vs other (95%) | (b) share: field → top 1% | Top-1% rate (b) vs other | Winner's stack game | Top-10 rows with (a) |
|---|---:|---|---|---|---|---|---:|
| W1 (12) | 824,476 | 13.3% → 4.8% → 2.2% | 0.37% [0.33, 0.40] vs 1.11% [1.08, 1.13] → **0.33×** | 21.0% → 8.0% | 0.33× | middle third | 0 of 10 |
| W2 (13) | 172,330 | 13.4% → 10.1% → 12.8% | 0.76% [0.65, 0.88] vs 1.04% [0.99, 1.09] → **0.73×** | 24.7% → 14.2% | 0.51× | middle third | 1 of 10 |
| W3 (13) | 161,502 | 14.9% → 10.1% → 9.9% | 0.68% [0.58, 0.79] vs 1.06% [1.01, 1.12] → **0.64×** | 22.5% → 7.4% | 0.27× | top third | 0 of 10 |

- **Where the top 1% stacked:** top-third games 68–80%, middle 15–21%, bottom third 5–11%, against a field of 49–60% /
  25–34% / 15–17%. The winners concentrate in the expected shootouts, and the field already over-plays them.
- **Lineups loaded with low-projected or low-owned players (b) do worse still:** 0.27–0.51× the top-1% rate.

## 2. Inside heavy portfolios (≥ 20 entries)

| Group | User-weeks | (a) share of a portfolio: mean / median / users at 5–15% | (b) share: mean / median |
|---|---:|---|---|
| Top-100 users (best rank ≤ 100) | 149 | 13.0% / 11.3% / 46% | 17.0% / 14.0% |
| Matched mid-field (as F2) | 149 | 15.1% / 11.3% / 45% | 23.1% / 16.7% |
| All heavy users | 8,255 | 14.7% / 13.0% / 37% | 20.0% / 14.3% |

- **The top users are not more contrarian than the mid-field.** They hold the field's own rate of low-total stacks, and
  fewer (b) rows.
- **Not a deliberate, stable sleeve.** For users heavy in two weeks, the (a) share correlates only 0.19–0.24 from one
  week to the next (Spearman; 605–720 users), and only 15–18% sit at 5–15% in both weeks. The (b) style is a stable trait
  (0.46–0.53): some users always play more low-owned pieces.
- **Do their wins come from those rows?** Top-1% rows that are contrarian, observed vs expected from each portfolio's
  share:

| Users | Top-1% rows | (a): observed / expected (ratio, 90% CI) | (b): observed / expected (ratio, 90% CI) |
|---|---:|---|---|
| Top-100 users | 594 | 73 / 75.6 (**0.97**, 0.71–1.26) | 54 / 93.0 (**0.58**, 0.41–0.72) |
| All heavy users | 6,293 | 454 / 834.8 (0.54, 0.50–0.59) | 572 / 970.9 (0.59, 0.55–0.63) |

  For the users who finished top 100, their low-total stacks hit at par with their other rows, not above. Across all
  heavy users they hit at half.

## 3. The 2025 winners (17 weeks; the summary table `reports/2025-milly-winners.csv`)

The winner's QB game, ranked by total on that week's Sunday main slate (9–13 games; nflverse `total_line`, the closing
line, a close proxy for pre-lock):

| Third | Winners |
|---|---:|
| Top | 12 |
| Middle | 4 |
| Bottom | **1** (Week 1: a 37.5 total, the QB at 1.8% owned, 4 sub-10% players) |

- All 17 winners stacked: 2–5 pass-catchers with the QB, 3–5 in nine of them.
- **10 of 17 carried ≥ 4 players under 10% owned:** low-owned pieces, not low-total games.

## Readout and caveats

**"Exists but does not carry wins."** About one lineup in seven, for pros and everyone else, stacks a low-total game.
It reaches the top 1% at a third to three-quarters of the rate of other lineups. One winner in twenty (1 of 20 across
2025–26) came from one. What winners share is a stacked expected shootout plus several low-owned pieces, which is what
the earlier winner-anatomy work found.

Caveats:
- Three 2026 weeks and 17 summarized 2025 winners. A contrarian sleeve's case rests on rare weeks where the low-total
  game explodes (2025 Week 1 was one), so it cannot be ruled out as a small high-variance sleeve for a very large book.
  It is not what the winners do, and not what the top users do.
- (b) uses realized ownership. (a) and the projection part of (b) are pre-lock.
- 2025's totals are closing lines.

As the operator said, nothing here argues for a contrarian sleeve at our volume. A positive finding would have become a
Week-5+ panel candidate; this one does not.
