# Expediting changes: what the rules already allow, and a faster calendar (2026-10-07)

The operator, 10-07: *"As I've mentioned to the other agent, waiting til after week 8 to make changes isn't an option.
We need to consider ways to expedite things."* (To the reviewer the same day: *"That is way too long for me to wait to
adopt anything."*)

Outside reviewer. This is a proposal for the operator and production; every decision below is his.

## 0. In plain words

1. **The rules already let us move this week.** His own in-season adoption track (`reports/2026-09-19-in-season-
   adoption-track.md`, §1) says:
   > a **reversible in-season trial** may be recommended as soon as its candidate-specific evidence package is ready —
   > not after a fixed number of weeks … elapsed weeks, an old experiment's endpoint, and a method-family closure do not
   > independently prohibit a reversible trial … The operator decides adoption. Scientific verdicts retain their frozen
   > rules and are reported separately from that decision.

   A frozen "NOT ENTERED" is a scientific verdict. It stays on the record, and it does not stop him from running a
   reversible trial with a rollback.
2. **The cheap +2 block's trial package is ready now** (§1 below). He could run it in Week 5 as a reversible trial
   instead of the matchup block, with matchup kept on paper. This is my recommendation for this week.
3. **Next week's changes should be decided on Tuesday 10-13, not after Week 8:**
   - put every Week-6 candidate on paper this Sunday;
   - read them on Week 5's real fields on Monday;
   - add the regime test to Monday–Tuesday's compute;
   - allow more than one reversible trial a week when each has its own paper comparison (§2).

## 1. The cheap +2 block as a Week-5 reversible trial (class S package)

| Item | Content |
|---|---|
| Mechanism | In the real fields, lineups with 2+ sub-$4,000 players finish in the top 1–20% about twice as often within the same user's lineups, every week; in his priority contests too (top 5%: 2.03 by contest, 1.93 within user). The build under-uses cheap players, because mean-maximizing rows don't value the salary they free. |
| Exact change | `--term-block-rows 8 --term-block-source cheap2-w5.csv --term-block-tilt 0.20 --term-block-cap-points 2.0`. The file is written Thursday from A3's frame by the adopted writer (`scripts/cheap_block_file.py`) and checked by the arm's TERM_CAP and file check. It replaces the matchup file in the same slot. |
| Primary utility | P(≥ 1 big win), his definition. |
| Evidence and costs | **For:** the W2–4 fixed-book replay ran ahead every week (P(≥ 1 big) .058 / .018 / .535 vs live .041 / .002 / .434). **History (study 53, frozen):** 2023–24 +0.004 [−0.031, +0.043]; 2022 −0.0016 (CONTRADICTED, so NOT ENTERED); expected big seats −6%, inside his 20% tolerance. **Regime:** 2022–24 are the three weakest seasons since 2018 for cheap starters, and 2026 has the best value; early value persists (r 0.68), booms less so (r 0.21). **Against:** the in-season case uses the same weeks that suggested the idea. |
| Earliest week | Week 5 (Sunday 10-11). |
| Operational proof | Thursday's file and its check, then Friday's A3 rehearsal armed with cheap instead of matchup. The binding 6e snapshot gate is taken from that run. |
| Unchanged comparison | Study 38's paper arms already score the live book without a block (NOTERM / QA0), matchup and CHEAP2, on every real field. |
| Monitoring | The priority-contest monitor (Monday step 6) and the field monitor (step 5); the paper arms' paired P(≥ 1 big). |
| Material-harm criteria (to fix before lock) | A proposal for him and the reviewer: stop after the review date if the paired paper comparison over the trial weeks is clearly worse on P(≥ 1 big), or expected big seats fall more than his 20% tolerance below the unblocked book. Not a loss count. |
| Rollback | Arm without the block file: the matchup file or none. The union arguments are otherwise unchanged. |
| Review date | Monday after each week; the first full review on Monday 10-19 (after W6). |

Choosing cheap **instead of** matchup keeps one construction change per week. Matchup's evidence (study 51:
enterable, neutral on history) stays on paper. Both blocks together would be an untested combination; it would need
its own check first.

## 2. A faster calendar for Week 6 (decide Tuesday 10-13)

| When | What | Owner |
|---|---|---|
| Before Sunday's lock | Put the Week-6 candidates on paper in study 38: the shape tilt (fewer QB + 1 rows in favour of QB + 2; study list 56), duplicate-aware dealing (50) and R4 for the 2-entry contests (57). Dealing and R4 are re-deals of the same book, so they cost no new build. | reviewer (amendment), laptop (build) |
| Monday 10-12 | Week 5's real fields: the paper arms, the field monitor, the priority monitor and the graph's game results. | laptop / reviewer |
| Monday–Tuesday | If the six-season co-run can carry extra arms: CHEAP2_BLOCK8 and the shape tilt on 2019–2021, the strong-cheap seasons. That is the regime test, in days rather than study 58's weeks. Study 54 (a plain projection book vs the live one) reads this week. | reviewer |
| Tuesday 10-13 | Decision records for Week 6, each as a reversible trial with its paper comparison. | operator |

Two process changes would speed every week after this:
- **More than one reversible trial a week**, when each has its own paired paper arm. The paper arms isolate each
  change's effect, so attribution survives. Today's rule of one construction change a week is a review convention, not
  part of the adoption track.
- **Compute.** All studies share one machine (one heavy job at a time). If a study can't fit before a decision date, a
  bounded Cloud Run budget for that study would buy days. That is a cost decision for him, against the standing "no
  heavy Cloud Run".

## 3. What does not change

- Frozen scientific verdicts stay as read and are reported beside any trial.
- Integrity failures still stop release.
- Never enter an untested rule: every change above has been tested on replays and history, or would be.
- Never select lineups on raw expected payout.
- His big-win definition sets the utility.
