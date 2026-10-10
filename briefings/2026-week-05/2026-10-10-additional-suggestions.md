# Additional suggestions after a second screen of the fields (2026-10-10, Saturday morning)

**For:** Erich, and the laptop and reviewers who run the studies. Written by the outside model, after your "do a little more
research". Three new looks at the Weeks 1–4 real fields, each on something the earlier screens could not read: ownership
(the join fixed, so chalk, low-owned players and duplication are measurable), hot players by position and by ownership, and how
the regulars choose which of their lineups goes into a one-seat satellite; plus a check of the ledgers for per-row
randomization. The Sunday book (the armed construction rebuilt on Week 4) is measured on each. Code and tables:
`reports/2026-10-10-winner-patterns/winner_patterns2.py`, `winner_patterns2.txt`, `hot_definition_check.*`. Aggregates only.

## In one page

| # | What the fields say | What it means for the book | Suggestion |
|---|---|---|---|
| 1 | **Hot players hurt at WR and TE, not at RB or QB.** A lineup holding a WR or TE coming off a 2× game was less likely to reach the top 1% than its own user's other lineups in every readable week (odds 0.37 / 0.70 / 0.40, Weeks 2–4; your contests 0.38). Hot RBs and QBs were mixed (RB 0.73 / 2.7 / 0.38; QB 2.5 / — / 0.08) | The Sunday book holds 1.08 hot WR/TE per lineup: 22 of 26 lineups have one, 6 have two. Study 109 faded every position and read worse (−4.7), which the fields also say for RBs and QBs | **TEST: the recency rule on WR/TE only** — HOT_WRTE1 (at most one hot WR or TE per lineup) and FADE2_WRTE, a follow-up to 109 with a position mask, two draws, your rule; a paper arm beside 6y's HOT1 |
| 2 | **Low-owned players: the winners carry fewer, every week, both contest types.** Top 1%: 1.1–1.4 players under 5% owned vs the field's 1.5–1.9; three or more such players cut the odds of a top-1% finish to 0.28–0.48 in all four weeks; your contests' top 3: 0.95 vs the field's 1.61 | Our Weeks 1–3 entered books were on the wrong side (2.2–4.0 per lineup). **The Sunday book is already right:** 0.69 per lineup under Fantasy Points' ownership, one lineup with three. The package plus the one-low-owned rule did this | **No change.** Study 110's LOW0 tests the stronger form; a "two under 5%" cap would touch one lineup |
| 3 | **Chalk flips with the week.** The top 1% were chalkier than the field in Weeks 1–3 (ownership sum 124–133 vs 112–117; two or more players at 20%+: odds 1.4 / 2.9 / 5.7) and much less chalky in Week 4 (100 vs 110; odds 0.15; no-chalk lineups 4.4×) | The Sunday book sits at the Weeks 1–3 winners' level (ownership sum 129, 2.4 players at 20%+, 7 lineups with none) | **No chalk floor** (a weekly bet; Week 4 would have punished it). The strongest case yet for your week-type idea (row 94; "row 93" in the draft, corrected at the laptop's merge) |
| 4 | **Duplication is not our problem.** Exact copies: the field 8.5%, the top 1% 12.6% (chalkier lineups get copied), ours 3.3%; your contests: the field 2.1%, the top 3 4.7%, ours 0% | — | Dupe-aware dealing (row 50) has little to gain here |
| 5 | **The regulars do not send their best-projected lineup to the one-seat satellite.** Among 8,170 satellite lineups by 172 multi-entry Millionaire users, the satellite lineup sits at the median of the user's own book by projection (spread evenly across it), 74% are not a copy of any of his Millionaire lineups, and they are his most unique lineups | Our head layout gives the priority contests rows 1–2, the highest-projected. The harness says the deal does not matter (studies 24, 32, 59) | Information: the premise that rows 1–2 are the best rows is not one the pros share |
| 6 | **My QB-rank cap: withdrawn.** Finer bands show no rule: QBs ranked 9+ vs the top 3 read 3.4 / 0.36 / 1.6 / 1.0 by week, and the 4–8 band was the worst in Weeks 1–3 | — | Drop it |
| 7 | Hot and chalky vs hot and quiet: both bad (0.44 / 0.72 / 0.32 vs 1.1 / 0.49 / 0.37) | — | The fade need not be ownership-conditioned; drop that arm |
| 8 | **Per-row randomization** (the commercial optimizers' "randomness": each lineup solved on projections drawn around the base, 10–20% sd) has not been tried on the MIX book; the old Gumbel perturb-and-MAP candidate generator read null (Addendum 90) in the pre-MIX pipeline | The caps and the overlap already force diversity; the curse lives in which players, not how many | Low priority: one harness read (JIT10 / JIT15, seeded per row) if the queue ever has room |

**Already covered by the team this morning:** HOT1 is on paper in study 38 (amendment 6y) so Week 5's real fields score it;
LOW0 and VAL4 are in study 110 (running).

## 1. Ownership, with the join fixed

**Method.** As the first screen (every Millionaire lineup of Weeks 1–4 and the 12,219 lineups in the 4444 / 555 / 333 / FFWC
contests; within-user Mantel–Haenszel odds for users with 20+ Millionaire entries; by-contest odds for your contests), with
realized ownership summed over a player's roster-position rows (the earlier run took one row per player, which was wrong).
Chalk and low-owned counts are over the 8 skill players. The Sunday book is measured on Fantasy Points' projected ownership
(the column the live rule reads); its sum over the slate is 890, the same scale as realized ownership.

**The Millionaire, by week (field / top 1%):**

| | W1 | W2 | W3 | W4 | Sunday book (FP) |
|---|---|---|---|---|---|
| Ownership sum | 112 / **124** | 117 / **126** | 116 / **133** | 110 / **100** | 129 (quartiles 98 / 141 / 155) |
| Players at 20%+ | 1.47 / 1.67 | 1.52 / 2.22 | 1.53 / 2.56 | 1.73 / **0.88** | 2.42 (7 lineups with none) |
| Players under 5% | 1.87 / **1.20** | 1.93 / **1.38** | 1.75 / **1.19** | 1.55 / **1.13** | 0.69 (1 lineup with 3+) |
| Players under 3% | 1.01 / 0.45 | 0.96 / 0.59 | 0.98 / 0.66 | 0.88 / 0.72 | 0.15 |
| Share with an exact copy in the contest | 10% / 15% | 6% / 9% | 6% / 13% | 5% / 4% | — |

Our entered Week-1 book (57 lineups): ownership sum 102, 0.86 players at 20%+, 2.25 under 5%, 1.23 under 3%, 0.25 stars — the
opposite of that week's top 1% on every line.

**Within-user odds of a top-1% finish, by week:**

| Feature (vs reference) | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| 3+ players under 5% vs ≤ 1 | **0.40** | **0.45** | **0.48** | **0.28** |
| 2+ players under 3% vs 0 | 0.20 | 0.37 | 0.68 | 0.61 |
| 0 players under 3% vs 1 | 2.38 | 1.35 | 1.09 | 0.97 |
| 2+ players at 20%+ vs ≤ 1 | 1.37 | 2.85 | 5.65 | **0.15** |
| 0 players at 20%+ vs 1+ | 0.56 | 0.20 | 0.04 | **4.42** |
| Ownership sum 130+ vs under 100 | 2.56 | 1.40 | 3.74 | **0.16** |
| An exact copy exists vs unique | 1.52 | 1.11 | 1.44 | 0.73 |

**Your contests (by contest, top 2%):** 3+ under 5% vs ≤ 1: 0.42; 0 under 3% vs 1: 2.13; 2+ at 20%+ vs ≤ 1: 2.74 (W1 1.2, W3 9.6,
W4 0.48); 0 at 20%+ vs 1+: 0.16 (no chalk-free lineup finished top 2% in Weeks 2–4); ownership sum 130+ vs under 100: 3.06.
Group means (field / top 2% / top 3 / ours): ownership sum 118 / 126 / 130 / 117; players under 5%: 1.61 / 1.11 / 0.95 / 1.82;
at 20%+: 1.71 / 2.11 / 2.28 / 1.44; stars 0.65 / 1.01 / 0.86 / 0.44.

**Reading.** The low-owned result is the robust one: lineups built around three or more players nobody owns almost never win,
in any week, in either contest type — and that is what our Weeks 1–3 books were. The current book is not. The chalk result is a
weekly bet: the same chalk-heavy build that won Weeks 1–3 lost Week 4 badly. Duplication rises with chalk and did not stop
the top 1% from being the top 1%; in your one-seat contests copies are rare for everyone.

## 2. Hot players by position

| Within-user odds of a top-1% finish (Millionaire) | W2 | W3 | W4 | Your contests (by contest) |
|---|---|---|---|---|
| 1+ hot WR or TE vs none | **0.37** | **0.70** | **0.40** | **0.38** (W3 0.41, W4 0.26) |
| 1+ hot RB vs none | 0.73 | 2.74 (thin) | 0.38 | 0.69 |
| 1+ hot QB vs none | 2.47 | — | 0.08 | — |
| Hot and 10%+ owned vs no hot player | 0.44 | 0.72 | 0.32 | 0.38 |
| Hot and under 10% owned vs no hot player | 1.09 | 0.49 | 0.37 | 0.46 |

Top 1% vs field, hot players per lineup: WR 0.36 / 0.88, 0.56 / 0.65, 0.38 / 0.81 (W2–4); TE 0.02 / 0.10, 0.20 / 0.58,
0.19 / 0.27; RB 0.56 / 0.75, 0.01 / 0.02, 0.22 / 0.42; QB 0.14 / 0.07, 0 / 0, 0.02 / 0.10.

**The Sunday book on Week 4, under study 109's exact flag:** 1.50 hot players per lineup (24 of 26 lineups hold one, 14 hold
two), of which 1.08 are WR or TE (22 lineups; 6 with two), 0.42 RB (10 lineups), 0 QB. The slate had 12 hot WRs, 6 RBs, 4 TEs,
2 QBs.

**The definition check** (`hot_definition_check.txt`): under study 109's flag (this season's last game, up to four prior games,
floor 5) the Weeks 2–4 pattern is the same as under the screen's flag: within-user odds 0.51 / 0.70 / 0.33, the top 1% at
1.08 / 0.77 / 0.81 hot players vs the field's 1.80 / 1.24 / 1.59. So the harness's negative read of the fade is a real
disagreement between the 2023–24 slates on the lab's projections and the 2026 fields, not a coding difference.

**Why a WR/TE-only rule is a fair follow-up.** The mechanism of a fade is regression: a receiving boom is made of touchdowns and
long plays and does not persist; a running back's big game is usually volume, which does. The fields show exactly that split,
and the harness's all-position fade spent most of its cost on RBs and QBs whose hot games carried forward. Arms: HOT_WRTE1 (the
row-rule vehicle, hot WR/TE ids, ≤ 1) and FADE2_WRTE (−2 on hot WR/TE only), study 109's module with a position mask, two
draws, your rule; and a paper arm beside 6y's HOT1 so Week 5 scores both. Prior: 109 negative on all positions; the split
untested. Production path: the same `row_rule_sets` vehicle with the hot ids restricted to WR/TE (a hot-flag file is already
part of 6y's snapshot step).

## 3. How the regulars deal into the one-seat satellites

Users with 20+ Millionaire entries who also entered a 4444 / 555 / 333 / FFWC contest the same week: 172 users, 8,170
satellite lineups. For each satellite lineup, where it sits inside that user's own Millionaire book:

| | All 8,170 | The 16 that finished top 3 | The 10% that finished top 10% |
|---|---|---|---|
| Projection percentile within his book | 0.50 (evenly spread: 1,866 / 1,530 / 1,410 / 1,550 / 1,814 across fifths) | 0.57 | 0.54 |
| Ownership-sum percentile within his book | 0.50 | 0.58 | 0.55 |
| Expected-copies percentile within his book | **0.11** | 0.07 | 0.13 |
| An exact copy of one of his Millionaire lineups | 26% | 21% | 25% |
| Stars per lineup | 0.66 | 0.79 | — |

The pros build separate lineups for the satellites, pick them from anywhere in their book by projection, and make them their
most unique. Nothing here says that choice wins (the top-3 group is 16 lineups), and the harness says the deal does not move
the big-win chance (studies 24, 32, 59). It does say the pros do not treat their highest-projected rows as their best rows,
which is the premise of our head layout.

## 4. Randomization, checked in the ledgers

Per-row randomization of the objective (each lineup solved on projections drawn around the base; the commercial "randomness"
setting samples each player's projection from a normal with a standard deviation of 10–25% of the projection) has not been run
on the MIX book. The nearest ancestor, the Gumbel perturb-and-MAP candidate generator of the pre-MIX pipeline, read null
(Addendum 90) and stays off. The MIX book already gets its diversity from the 35% cap, the ownership cap, the overlap limit and
the row rules; what randomization would add is robustness to which players Fantasy Points overrates, the same aim as the shrink
(−4.4) and the value cap (study 110). Low priority; one harness read (JIT10 / JIT15, seeded per row, the receipt recording the
seed) if the queue ever has room.

## 5. Limits

Realized ownership is the chalk measure for the fields; the book's column is Fantasy Points' projection. Four weeks (three for
recency); the within-user odds hold the user fixed, not the week's outcomes, so the by-week columns carry the weight; the
Week-2 cells of your contests are two contests (126 lineups). The top-3 satellite group is 16 lineups.

## 6. Sources

`reports/2026-10-10-winner-patterns/winner_patterns2.py` and `winner_patterns2.txt` (BigQuery `nfl_raw.contest_entries`,
`nfl_raw.contest_ownership` summed per player, the T-70 frames, `nfl_features.player_week_actuals`), `hot_definition_check.py`
/ `.txt`; the Sunday book from `~/rehearsals/minprojcheck-live-20261010T102003Z/LIVE` with `~/moneygate/inputs/own/w4_ownership_fp.csv`;
`reports/2026-07-25-system-study.md` Addendum 90 (Gumbel) and Addendum 204 (study 109); HANDOFF 2026-10-10 07:08 and 07:36; the
Establish The Run Milly Maker trends (product ownership: the top 100 use more 5–15%-owned players and fewer at 40%+).
