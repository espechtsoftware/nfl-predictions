# Dealing the book by the lineups' season-to-date touchdowns: the W2–4 harm screen's result (2026-10-07)

**The frozen screen:** `reports/2026-10-07-tdytd-deal-harm-screen.md`, frozen at `8eed3bf4` (sha256 `e3a4167c…`) and
committed before any number.

**The run:** `~/rehearsals/tdytddeal-20261008T040126Z` (private scratch), script
`~/.cache/laptop-agent/rehearsal/tdytd_deal_replay.sh`.
- **No new builds.** The books are the priority-deal run's CB books (`~/rehearsals/prioritydeal-20261007T193507Z`, production
  `7ee09fe1`): his Week-5 construction on the W2–4 real fields with the cheap +2 block.
- **Inputs:** plan Rev6 `5f8352ee`; scorer `s24_qb_game_cap.big_seat_stats` `ce2cddc1` on `plan-week5-rev3-s24.json`
  `3dd19d6c`; `moneygate_score` `dd8ff1f7`.
- **The key** came from `nfl_features.player_week_actuals` and `nfl_features.team_defense_week`, 2026 weeks before the
  slate. The source pulls are saved in the run dir.

**Integrity: OK in all three weeks.**
- Every sorted arm holds CB's 26 rows (as a multiset). Every arm except CB_TDY_ALL keeps the block rows at the block
  positions (0-based 1, 4, 8, 11, 14, 17, 21, 24). Each written order equals the key sort recomputed.
- CB_REV6, laid out again here, reproduces the priority-deal run's rowmap byte for byte and its scores exactly.

## The arms (P(≥ 1 big) / expected big seats, per week; every big contest is a priority contest on Rev6)

| week | CB_REV6 (today's deal) | CB_TDY (decision) | CB_TDY_ALL | CB_TDY_SCORED | CB_PROJ18 (control) |
|---|---|---|---|---|---|
| W2 | .1120 / .1149 | .1119 / .1149 | .0280 / .0282 | .1119 / .1149 | .0907 / .0917 |
| W3 | .0178 / .0178 | .0032 / .0032 | .0183 / .0183 | .0021 / .0021 | .0062 / .0062 |
| W4 | .6597 / .8935 | .4265 / .4847 | .2024 / .2114 | .5173 / .6478 | .5961 / .7854 |

## The frozen rule's verdict

**CB_TDY vs CB_REV6: NOT ENTERED.**
- P(≥ 1 big) is lower in all 3 weeks.
  - W2 is lower by 0.0001, a tie in practice. W3 and W4 alone reach the rule's 2 of 3.
- The pooled expected-big-seats ratio is 0.587, below 0.80.
- Either criterion alone stops it.

**Exploratory (descriptive; every re-sort trails the book's own order, as in study 52):**
- CB_TDY_ALL (all 26 sorted, no block kept): lower in 2 of 3 weeks; ratio 0.251.
- CB_TDY_SCORED (no passing TDs): lower in 3 of 3; ratio 0.745.
- CB_PROJ18 (the projection-order control): lower in 3 of 3; ratio 0.861.

**Disclosure, in the screen's words:** *"in-sample (the operator's idea, tested on weeks already seen); no out-of-sample
evidence from this check; the harness study carries the decision."*

## Descriptive

**The key** (the lineup's 2026 touchdowns before the slate):

| | W2 | W3 | W4 |
|---|---|---|---|
| range | 4–13 | 12–22 | 11–24 |
| mean | 7.4 | 15.7 | 16.9 |
| the QBs' share | 0.28 | 0.36 | 0.35 |
| correlation with the lineup's projection | +0.31 | −0.26 | +0.05 |

- CB_TDY moved 17–18 of the 18 sortable positions each week.
- The sort is not projection order.

**The mechanism** (W4 carries the pooled ratio):
- W4's best row scored 181.08 DK points, the 98.8th percentile of the real Millionaire field.
- In today's deal it sits at rank 14, read by a $333 satellite, which is a big contest.
- Its players had scored few touchdowns before Week 4, so the TD sort moved it to rank 26. There only the $20 supersats
  read it, and those are not a big win.
- This morning's priority sort moved the same row to rank 23. That is why the two sorts' W4 numbers nearly coincide
  (.4265 / .4847 vs .4264 / .4846).
- The second-best row (174.28 points) is a block row and stays at rank 5 under both.

## What it means

**No re-deal of the same book has yet beaten the book's own order:**
- study 48b (winner-likeness);
- study 52 (projected TDs);
- the market-TD re-deal;
- this morning's priority sort;
- the projection-order controls inside each of these tests;
- this one (season-to-date TDs).

A re-deal moves the book's few winning rows between contests and cannot create them. On these weeks, every key tried
moved them away from the big contests more often than toward them.

**The out-of-sample harness test** (study 52's shape: DEAL_TDY vs DEAL_LIVE, the 2023–24 read and the 2022 go / no-go)
is possible, because season-to-date TDs exist in every historical season. It is offered to the operator. The laptop
recommends not spending it, given the null-or-negative re-deals above and this screen's clear stop. The operator
decides.
