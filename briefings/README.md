# Briefings: the documents to read each week

The operator asked (2026-10-05) for the important documents to live in one easy-to-find folder. Each week's folder
holds the reports written for the operator, newest week first. Everything else (protocols, preregistrations,
evidence, tooling notes) stays in `reports/`.

This repository is public. Briefings carry no user names, entry ids or dollar amounts; dollars are kept privately on
the laptop.

## 2026 Week 5 (Sunday 10-11): the decisions → `2026-week-05/`

| Read | What it answers |
|---|---|
| [Week-5 decision sheet (draft for Friday)](2026-week-05/2026-10-05-week5-decision-sheet.md) | Judged by your goal (one big win): the lineup shape (study 28: the winners' mix is the closest result, better in every season, not yet a proven gain; recommended as your preference; WS tied), Fantasy Points' projections, the lab-code update, your revised plan (19 contests, 24 entries), study 24: strictly distinct no gain, the per-game cap not offered, sequential dealing the no-code middle option; about 1 week in 4 with a big win (optimistic); the Week-4 replay; what is untested; how to undo |
| [What you would be entering (pre-mortem)](2026-week-05/2026-10-06-week5-premortem-what-you-would-enter.md) | The two Friday books on Week 4's real slate: the winners' mix builds lineups like the regulars (45% full stacks vs their 42%; ours was 94%); both books are far more concentrated than the regulars on QBs and one game (91% / 60% of entries with the top-total game's QB vs about 20% in the field); descriptive, no verdict |
| [Expedited test plan (Tue → Sat)](2026-week-05/2026-10-06-expedited-test-plan.md) | Your 10-06 instruction to test everything planned and not done before Week 5: what can still change Sunday's book (overlap 4, the fill order, rows in every high-total game, shape by contest type), the checks that only inform, what starts this week for later grading, what cannot be done before Week 5 and why; day by day |
| [P1 and P3, built: are we +EV anywhere, and do our layers earn their place?](2026-week-05/2026-10-07-p1-p3-first-reads.md) | Your approved-plan P1 and P3, frozen today: P1 tracks where our lineups finish against break-even per contest type (a stake flag only from Week 8, and only with a large real improvement); P3 compares your construction with a plain optimizer on big seats every week. Answered this week two ways: the Weeks 2–4 real-field replay (in-sample; big seats tied 0–0 in Weeks 2, 3 and 4) and study 54 on the historical 2022 slates (done: no clear difference, every estimate favouring your construction; nothing says to simplify) |
| [How the pros pick players: Fantasy Points, the market, and what else](2026-week-05/2026-10-08-how-the-pros-pick-players.md) | Your 10-08 question: the pros follow a market-style projection (Fantasy Points and the props agree at 0.85; no pro can be pinned to Fantasy Points itself); they lean on it at RB, TE, studs and chalk, hardly at QB/WR; their other habits (sell recency and salary risers, ignore 1-3-game matchups, steady routes, fade the crowd) are leverage, not better projections; their edge is half market-following (every week) and half beyond the market (TE, QB); three seasons show the props under-price team totals, underdogs and wind, which neither the pros nor Fantasy Points use; suggestions S1-S5 (all tests first) |
| [Week 4's "necessary" players, and why today's system would still miss them](2026-week-05/2026-10-08-necessary-players-and-the-bring-back.md) | Your 10-08 questions ("Would our system today have picked them?", "Is there a test we can do immediately?"): today's settings rebuilt on Week 4 still miss Lamb + Collins; a top-receiver block cannot fix the pairing (the solver chooses the bring-back), so study 70 tests the block tonight and study 71 (bring-back = the opponent's top receiver) is for Week 6 (the outside reviewer) |
| [How the winners spread their players](2026-week-05/2026-10-06-how-the-winners-spread.md) | Your 10-06 question: their spread is how they build, not their volume (cut to our 26 lineups they still have about 2 players over 40%, we have about 10); nobody swaps within the same game (replacements come from other games, as the slate dictates; theirs are about 3 points cheaper); the top receiver is their usual but not fixed partner (about 60%); Neo4j for looking, loaded Wednesday |

## 2026 Week 4 (Sunday 10-04): post-mortem and the Week-5 decision → `2026-week-04/`

| Read | What it answers |
|---|---|
| [Week-4 post-mortem](2026-week-04/2026-10-05-week4-post-mortem.md) | What happened, where the points went, whether our selection helps, the winners' structure, usage, corrections |
| [Week-5 money test](2026-week-04/2026-10-05-week5-money-gate-result.md) | Would today's system have made money over Weeks 1–4? (No: about 0.48× of fees.) Does any tested change do better? (No) |
| [Contest-type edge (P1)](2026-week-04/2026-10-05-p1-contest-type-edge.md) | Where we are +EV (nowhere measurable), and how long money results take to show an edge (hundreds of weeks) |
| [Path to winning](2026-week-04/2026-10-05-path-to-winning-plan.md) | A ranked plan from the evidence |
| [Contrarian games (X1, steps 1–2)](2026-week-04/2026-10-05-x1-steps-1-2-shootouts-and-field-allocation.md) | Shootouts are hard to call; the field is flatter than the odds; our error is concentration |
| [Overlay back-test](2026-week-04/2026-10-05-overlay-backtest-week4.md) | No usable overlays on the classic slate |
| [Studies 15 & 16: stack rule and thesis portfolio](2026-week-04/2026-10-05-studies-15-16-stack-and-thesis.md) | Should a lineup need only QB + 1 + bring-back? (No measurable difference; your call.) Does the thesis portfolio do better, whole or as a sleeve? (No; it is a heavier bet on the expected shootouts; the sleeve follow-up is tabled) |
| [Study 1b: player cap](2026-week-04/2026-10-05-study1b-player-cap-result.md) | Should any one player be held under about 30% of entries? (Not at the cost: it halves the bust damage but costs about 3.5 points of average finish; a lead on more cashes, to be tested) |
| [Study 1: de-concentration](2026-week-04/2026-10-05-study1-deconcentration-result.md) | Does capping how much of the book one game takes help? (No: steadier on paper, not more money; not offered) |

**Week 4 Monday reads:** `reports/2026-10-05-week4-monday-reads.md`. **Next:** the projection retrain with the O-22 data-leak fix (Thu–Fri).

## Earlier weeks (in `reports/`)
- Week 3: `reports/2026-09-27-week3-post-mortem.md`
- Week 2: `reports/2026-09-21-week2-post-mortem.md`
- Week 1: `reports/2026-09-13-week1-postmortem-and-220-program.md`
