# Handoff from the outside reviewer to the laptop (production), 2026-10-07 10:30 CT

Sent at the operator's request (10-07: "I would like you to be able to share your results directly with the laptop
production. Please commit that as a handoff to them."). Branch `review/outside-fill-order-20261006`; GitHub's Git
operations are in a major outage (10:15 CT), so the newest commits are local until it recovers. Every file below is on
this machine at `~/projects/.nfl-predictions-worktrees/review/outside-fill-order-20261006/`.

## 1. New since your 09:47 entry: the first pre-lock fact that sorts lineups inside good portfolios (actionable)

`reports/2026-10-07-graph-cheap-players-finding.md` (scripts `reports/2026-10-07-winners-strategy-study/graph/`,
`cheap_count_check.py`, `run/experiments/replay_cheap.sh`).
- **Within the regulars' own portfolios** (the local graph: 351 user-weeks with ≥ 20 lineups, 51,729 lineups, 1,075 in
  the real top 1%), the top-1% lineups carried more **sub-$4,000 non-DST players** than the same user's other lineups:
  +0.43 sd [+0.36, +0.49], positive in all four weeks. Their top-1% rate: none .74/.16/.79/.22%, one 1.3–2.0%, two
  2.4–3.8%. Also every week: lower prior snap share (−0.35 sd), cheaper TE (−0.29), props-implied above our projection
  (+0.18). Our projection does not separate them (0.00).
- **The whole real field** shows the same gradient every week (none .75/.08/.31/.38%; two 1.61/1.82/2.45/1.50%). **Our
  pool** only weakly. **Our books** carry few: the live W5 settings on W3/W4 put two sub-$4k players in 1 of 26 rows.
- **Replay** (the factor-tilt harness, live W5 settings: ms4, rr, QB cap 5, no term; W2–4 real fields), a bonus per
  sub-$4k non-DST player through the union's own-term vehicle:

  | Arm | P(≥1 big) W2 / W3 / W4 | mean entry pct W2 / W3 / W4 |
  |---|---|---|
  | live | .041 / .002 / .434 | .424 / .516 / .502 |
  | +2 | .000 / .319 / .641 | .419 / .506 / .573 |
  | +4 | .655 / .127 / .160 | .471 / .569 / .665 |

  In-sample; the populations that found it (the regulars, the field) are independent of our build. The hard punt
  mandate was removed in August (Addendum 77) on the old panel; the live book (FP means in the union MILP) has neither
  the mandate nor the old p90 punt valuation.
- **Requests:** (a) a preregistered harness study of the +2/+4 preference with the 2022 go/no-go (the reviewer's
  design, the usual process); (b) if cheap, a Sunday paper arm in study 38 (CHEAP4 on FP means) so W5 grades it out of
  sample; (c) it is not a Week-5 entry on this evidence unless he chooses it with the in-sample caveat.

## 2. Already in your queue from this morning (for completeness)

- Sorting research and the nine-key real-field screen: `reports/2026-10-07-how-professionals-sort-lineups.md`. No key
  beats random picks from our pool at the top end; touchdowns help the average finish only. Consistent with your TD-deal
  screen (NOT ENTERED). Duplication used for dealing is the one sort with a mechanism (your study list 50).
- Why we missed the winners' players, the matchup out-of-sample check (odds ratio 1.07/sd, nothing in weeks 1–4), the
  factor bonuses, the environment-forms negatives: `reports/2026-10-07-why-we-missed-the-winners-players.md`.

## 3. Housekeeping

- **Licensed vendor values:** the three per-player files that carried FP W4 projections/ownership
  (`run/player_factors.csv`, `run/player_factors.log`, `run/missing_players.txt`) are removed at the branch tip
  (806664db). They remain in history; a rewrite is the operator's call. I will not commit per-player vendor values again.
- **Worktrees:** I remove only worktrees I created, by exact path (the 04:51 lesson).
- **Machine:** my jobs run at nice 15 and yield to yours; the TD-upside replay queued this morning did not run (the
  session ended); it is superseded by the cheap-player replay above.

## 4. How to reach me

The operator asked that results go to you directly: I will message this session (`nfl-predictions-7d`) with each
committed finding. Replies that need the operator still go through him.

## 5. End of day (2026-10-07 16:16 CDT): what was done after 10:30, what is open, and Monday's plan

**Week 5 as armed (the operator's decisions, recorded by the laptop on decision sheet row 21):**
- **The cheap +2 block** runs as a reversible trial in place of the matchup block (his words: "Consider that
  approved"). Matchup stays on paper.
  - Stop rule: behind the unblocked book on paired P(≥ 1 big) in every live week, or summed expected big seats
    < 0.80×.
  - The first full review is Monday 10-19.
  - Three practice-week side reads average about zero (2023–24 +0.4 / −3.5 / +1.7; 2022 −0.2 / −0.2 / −3.3).
- **His contest order, private plan Rev6:** $4,444 → $555 → WFFC → $333 → Millionaire → Warm Up → the rest. It is
  installed after its harm screen passed (1.466).
- **Priority-first SORT of our rows:**
  - NOT ENTERED: the W2–4 screen read 0.587.
  - Study 59 on practice weeks: +0.7 / +1.5, within noise.
  - Closed, except as a possible no-cost paper deal if he wants it watched.

**Committed today on `review/outside-fill-order-20261006`** (all aggregates; the scripts beside their outputs in
`reports/2026-10-07-brainstorm/`):

| What | Where |
|---|---|
| Brainstorm: Neo4j data, models, nine quick tests | `reports/2026-10-07-brainstorm-data-and-models.md` (study list 52–55; 52 later DROPPED) |
| Week-5 options, priority contests, satellites, the Rev6 log, the harm screen, big-contest entries | `reports/2026-10-07-week5-options-this-week.md` §0–§5 |
| Expediting under the adoption track | `reports/2026-10-07-expedite-options.md` |
| Weekly monitors, adopted by production (steps 5 and 6) | `scripts/field_pattern_monitor.py` (881ad086); `scripts/priority_field_monitor.py` (849adde2, the Warm Up update) |
| Neo4j result facts (built by production) | definitions and W1–4 references in `graph_result_facts_reference.py` |
| Graph-query hardening and production's fix | `within_portfolio.py` / `cheap_tier.py` (DISTINCT); `cheap_count_check.py` = production 02eb0b0e |

**Open, owned elsewhere:**
- Study list 58 (the 2025 regime study, W6+; needs 2025 inputs).
- The 2022–25 DK-points join (README log).
- The cash-line test for big-contest entries (§5 of the options note; the reviewer's harness at the target contests'
  real lines, m = 1 and 2: LIVE vs FP-plain vs props-plain).
- Study 56 (fewer QB + 1) as a possible W6 trial.

**Withdrawn by me:**
- Joint-coverage pairs for big-contest entries, after study 57 read −1.6.
- Row-ranking deals built from field odds ratios. The lesson in §4b: field associations say how to build a book, not
  how to deal our rows.

**Monday 10-12 (my plan):** read Week 5's real fields and report to the operator in plain words:
1. The paper arms: the cheap trial vs the unblocked book, plus matchup and QB2HALF.
2. Both monitors.
3. The graph's game results: did our rows cover the best-stack game?
4. The FP-#1 vs props-#1 lineup on the real field, from P3's W5 books, extending `cash_line_books.py`.
Then a short note for the Tuesday 10-13 Week-6 decisions.

**Housekeeping:**
- Neo4j is stopped.
- No jobs of mine are running.
- My last scratch worktree (the cheap-block replay checkout) was removed by exact path; its results stay in
  `~/rehearsals/outside-cblocks-20261007T153309Z`.

## 6. Thursday morning (2026-10-08 09:39 CDT): the operator's questions, and the decision to keep the Week-5 plan

- **"Anything more to try today for Week 5?"** No more lineup changes: nothing else passed its tests. The remaining value
  is execution (Friday's A3 with the cheap block, Saturday's arming, the Sunday 10:30 inactives and stop checks). The
  weather table has no Sunday forecasts yet; that is the schedule (`s-weather` runs Friday to Sunday at 08:00 CT).
- **"Are we double counting weather?" No.**
  - Our model has no forecast inputs: `featureset.py` holds `is_dome` and the Vegas lines only, and
    `EXTRA_FEATURES` admits only registered candidates, none of them weather.
  - `--proj-source` REPLACES `mean_projection` (ours is kept beside it as `mean_projection_ours`).
  - No weather rule exists in the money-path scripts, `inference/`, `optimizer/` or nfl2.
  - I had told the operator that FP "already accounts for weather"; corrected: FP's method is not visible to us.
  - Weeks 1–4 had no strong wind (the highest forecast was 16.6 mph, NE at BUF in Week 4, played at 11 mph).
  - Monday: if a Week-5 game had a forecast of 20 mph or more, I compare FP with `mean_projection_ours` for its passers
    and receivers.
- **"Why haven't the plain book and the props book been tested?"** Both had been; I had wrongly said P3's comparison
  "starts this week".
  - The plain book: study 54 (Addendum 162), and the laptop's Week 2–4 replay.
  - The props book: the same replay (`~/rehearsals/p3-replay-20261007T172856Z`). No book won a big seat. Small hits
    were props 13, plain 10, entered 7.
  - The props report of 10-06 has Week 4 only, on prop-covered players. The average miss was props 5.71, a 50/50
    FP + props mix 5.76, and FP 5.85.
  - Nothing more can be tested before Monday: FP exists from Week 4 only, and history has props but no FP.
- **The operator's decision (verbatim): "let's stick with the current plan".** FP alone for Week 5; the FP + props mix
  is not armed.
- **Monday 10-12, item 5 added to my plan:** the Week-5 row of the frozen weekly FP vs 50/50 FP + props check
  (`scripts/weekly_fp_props_check.py`, `reports/2026-10-06-prereg-fp-props-weekly-check.md`). If its rule offers the
  mix, I recommend it for Week 6 (class C; the operator decides).
