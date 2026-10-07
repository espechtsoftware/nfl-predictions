# Priority-first dealing: the W2–4 harm screen's result (2026-10-07)

**The frozen screen:** `reports/2026-10-07-priority-deal-harm-screen.md`, frozen at `27a1957b`, with amendment 1 at
`7ee09fe1` (Rev6, the pairs); both were committed before any number.

**The run:** `~/rehearsals/prioritydeal-20261007T193507Z` (private scratch).
- Built through production's switch at `7ee09fe1` (`priority_deal.py` `fa47594d`), lab pin `f69598b`.
- Plans: Rev3 `8625de0e` and Rev6 `5f8352ee`.
- Scorer: `s24_qb_game_cap.big_seat_stats` `ce2cddc1` on `plan-week5-rev3-s24.json` `3dd19d6c`; `moneygate_score` `dd8ff1f7`.

**Integrity: OK in all three weeks.**
- The same 26 rows (as a multiset), the block rows at the block positions (0-based 1, 4, 8, 11, 14, 17, 21, 24), and the
  same 15 spares.
- The switch's order equals `priority_order` recomputed from the frame.
- The receipt records the order only on CB_PRI.

## The arms (P(≥ 1 big) and expected big seats, per week; every big contest is a priority contest on Rev6)

| week | CB (Rev3, book order) | CB_REV6 (Rev6, book order) | CB_PRI (Rev6, the sort) | CB_ALL (all 26 sorted; exploratory) |
|---|---|---|---|---|
| W2 | .0578 / .0586 | .1120 / .1149 | .0907 / .0917 | .0972 / .0988 |
| W3 | .0179 / .0179 | .0178 / .0178 | .0262 / .0264 | .0004 / .0004 |
| W4 | .5347 / .6236 | .6597 / .8935 | .4264 / .4846 | .4071 / .4583 |

## The frozen rule's verdicts

- **(i) THE SORT, CB_PRI vs CB_REV6: NOT ENTERED.** P(≥ 1 big) is lower in 2 of 3 weeks (W2 and W4), and the pooled
  expected-big-seats ratio is 0.587, below 0.80.
  - Either criterion alone stops it.
  - `--priority-order` stays off for Week 5 (`PRIORITY_ORDER=0`).
- **(ii) THE PLAN RE-ORDER, CB_REV6 vs CB: passed this screen.** P(≥ 1 big) is lower in 1 of 3 weeks (W3, by 0.0001), and
  the pooled ratio is 1.466.
  - Rev6 is installed (10-07 14:38; the arm's PLAN_SHA is `5f8352ee`, commit `5766b799`).
- **Descriptive:**
  - CB_PRI vs CB, the whole change: lower in 1 of 3 weeks; ratio 0.861.
  - CB_ALL vs CB_REV6, the outside reviewer's original all-row form: lower in all 3 weeks; ratio 0.543.
- **What the sort did to the priority entries:** fewer QB + 1 rows, more bring-backs, more cheap players, but a lower mean
  finish. In W4: QB + 1 .375 → .292, bring-back .625 → .708, 2+ cheap .292 → .333, mean finish percentile .614 → .557.
  - The score's elements are real associations across the field's lineups, but ranking our own built rows by them did not
    carry over.
  - That is the same lesson as study 48b, and the outside reviewer concurs.

**Disclosure, in the screen's words:** *"in-sample (weeks already seen; the score's evidence comes from the same W1–4
real fields); no out-of-sample evidence from this check."*

**A defect in the replay's own check, found and fixed before any verdict was reported:**
- The first scoring pass printed "integrity VOID: rows differ" in every week. It had compared `sorted()` lists of
  frozensets, and Python orders sets by subset, which is not a total order.
- Every other integrity check passed, including "the switch's order equals `priority_order` recomputed", which by itself
  proves the same rows.
- The check now compares a Counter multiset. The SAME outputs were re-scored with no rebuild, so the numbers are
  unchanged.
- The reviewer accepted the fix.

**Study 59**, the reviewer's harness test of the same sort on 2023–24 with the 2022 go / no-go, becomes a Week-6 read.
