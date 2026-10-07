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
