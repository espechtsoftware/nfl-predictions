# Limited-entry contest winners vs our lineups (Weeks 1–4, 2026) — the outside reviewer, 10-09

**For:** the study-91 / study-38 6p preregistrations (the operator's request, 10-09: "Look at the winners, the you know top three
finishers for each. What did they do in their selections? How were their selections better than ours?"). Aggregates and public
NFL names only; the per-lineup rows stay in `~/private/limited-entry-winners/`. Inputs: the money gate's W1–4 real fields and
real points, the T-70 frames (salary, projection, game), contest ownership = the share of that contest's lineups holding the
player. `analyze.py` and `select_by_p1.py` reproduce every number (run with the production venv; they write only under
`~/private/`).

## 1. The top 3 against ours and the field (per lineup, averaged)

| Group (contests) | | Top 3 | Ours | Field |
|---|---|---|---|---|
| $20-Millionaire satellites (63) | real points / projected | 180.7 / 127.0 | 116.5 / 130.0 | 123.1 / 124.1 |
| | players < 3% contest ownership | 0.35 | 1.01 | 1.04 |
| | TE in the flex | 0.42 | 0.54 | 0.36 |
| | QB salary / DST salary | 5,594 / 2,763 | 5,788 / 3,012 | 5,964 / 2,908 |
| 4444 satellites (4) | real / projected | 199.0 / 128.0 | 125.5 / 131.6 | 134.1 / 124.9 |
| | < 3% owned; TE flex | 0.42; 0.42 | 1.00; 1.00 | 1.00; 0.43 |
| 555 satellites (3) | real / projected | 181.1 / 123.0 | 110.7 / 134.6 | 121.2 / 126.2 |
| | < 3% owned; TE flex | 1.00; 0.11 | 1.00; 0.67 | 0.84; 0.32 |
| 333 satellites (2) | real / projected | 183.6 / 126.8 | 123.8 / 129.9 | 134.2 / 125.0 |
| | < 3% owned; TE flex | 0.50; 0.50 | 0.50; 0.75 | 0.72; 0.42 |
| FFWC (5) | real / projected | 198.4 / 126.7 | 123.3 / 127.0 | 140.7 / 124.4 |
| | < 3% owned; TE flex | 0.50; 0.62 | 1.00; 0.38 | 0.99; 0.42 |

Our lineups were the highest-projected and the lowest-scoring in every group. Hindsight caveat: the top 3 hold the week's booms.

## 2. Selecting from our own pool by the model's chance of 1st (against each contest's real field) vs by projection

Mean finish percentile (the share of the real field beaten), the same number of lineups as he entered per contest:

| Group | Entered | By projection | By P(1st) | By P(top 3) | Pool's best (hindsight) |
|---|---|---|---|---|---|
| $20-Millionaire satellites | 39.4 | 50.0 | 43.9 | 50.9 | 99.8 |
| 4444 satellites | 27.8 | 53.2 | 32.4 | 56.2 | 99.9 |
| 555 satellites | 37.1 | 43.8 | 52.4 | 53.5 | 99.5 |
| 333 satellites | 32.8 | 58.1 | 41.9 | 40.3 | 100.0 |
| FFWC | 36.1 | 55.8 | 48.9 | 41.4 | 99.8 |

- P(1st) did not beat projection in 4 of 5 groups (by week: 52 / 18 / 38 / 61 against 72 / 32 / 54 / 49): the overconfident
  sims hurt a win-probability ranking.
- The plain top-projection picks from the same T-70 pool beat the entered lineups in every group (W1–3 entered Saturday books:
  a timing confound; W4 alone 48.8 vs 43.4).
- The pool held a would-be winner in most contests (51 of 63, 2 / 2, 3 / 4, 2 / 3, 2 / 5): selection, not generation, is the
  bottleneck.
- Disclosed: P(1st) used the contests' REAL field rosters (a best case for any field model).
