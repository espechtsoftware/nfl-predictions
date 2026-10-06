# Expedited test plan: everything planned and not done, tested before Week 5 where it can be (Tue 10-06 → Sat 10-10)

**Your instruction (Tue 10-06, 16:40 CT):** "let's plan on an expedited schedule for testing all of these. I want to try
all that we can unless there's a valid reason not to before week 5 since it's only tuesday."

"These" are the items the 10-06 audit found planned and not done, plus the ones due this week that no checklist carried.
The audit and the checklist lines are on integration (`59239aec`).

## Two limits that set the schedule

1. **Friday 17:00 CT is the last moment to change Sunday's book.** Friday evening's rehearsal runs on the final code
   and the Saturday arm refuses anything else. A change that reads after Friday can still run on paper beside the
   real entries in Week 5 and be adopted for Week 6.
2. **One heavy job at a time on the laptop** (and no heavy Cloud Run). Heavy means the reviewer's studies (about an hour
   each), the three live-build rehearsals (Wednesday; they protect Sunday and come first) and the fixed-book replays.
   Queries and reads are light and run alongside.

## What can change Sunday's book (each needs: a study on the 36 slates, the Week 2–4 replay, then your yes)

| Item | Owner | Study run | Replay on Weeks 2–4 | Your decision |
|---|---|---|---|---|
| **Overlap limit 4 instead of 5** (study 41, read 10-06 17:00: PASS, +5.9 points of big-win chance per slate [+1.1, +11.2] on 36 past slates, both guards held; reproduced exactly) | reviewer / laptop | done | **done 10-06 17:00: mixed.** Average finish the same as the study predicted (−0.005 vs −0.004); big-finish chance lower in all three weeks, but each week turns on one lineup (the live Week-2 book holds one 185-point top-1% lineup) | **held until the reviewer's field check tonight** (does the study's simulated field rank 4 and 5 as the real fields do?); Thursday at the latest, with no cost to Week 5 |
| **Fill order** (study 42; the outside reviewer's objection 10-06: the winners' shape follows the game script, not the QB, so a capped QB's lineups should cover several shapes): today's order vs **best-first** vs **round-robin** (each cell in turn) | reviewer / laptop | tonight | **done 10-06 17:00.** Best-first did not raise the book's projection and finished worse on average in Weeks 2–4 (−0.03 to −0.05); round-robin finished level to slightly better on average; on big finishes the live book's one lucky lineup beats both | Wednesday. **Best-first is not armed for Week 5 on any study read unless the real-week gap is explained** (the outside reviewer and the laptop agree) |
| Rows in every high-total game (study 43; your first choice) | reviewer / laptop | **done 10-06 18:00: no difference, leaning worse** (−2.8 points of big-win chance [−6.5, +0.7], both seasons negative, about 11% fewer expected big seats); reproduced exactly | — | **Not used** (the switch stays off): forcing a stack into each top game spends lineups on weaker builds |
| ~~Lineup shape by contest type~~ (item 23) | — | **dropped 10-06 (your decision)** | — | The winners' mix stays for every contest: the WS half already tied it (study 28), and putting both Millionaire entries in one shape goes against the week-to-week finding |
| **One contrarian lineup** (your 10-06 evening yes) | reviewer / laptop | **done 10-06 19:00: worse** — the contrarian lineup won its satellite about a quarter as often as the normal lineup it replaced (0.28% vs 1.29%); reproduced exactly | — | **Not used for Week 5.** The reviewer re-checks it once the simulated fields are calibrated to the real ones |

Your Week-5 settings are already decided (the winners' mix, FP projections, no ownership tilt, QB cap 5, overlap 5).
Each of these is tested as one change on top of them. If a study reads "no difference" with the guards
intact, it is offered as a preference, as studies 35 and 40 were.

## Checks that inform Week 5 without a study (laptop; light; results to you as they land)

| Item | When | What it tells you |
|---|---|---|
| Favorite-RB check (study list 19) | **done 10-06** | In 2023–25, lead RBs of 7+-point favourites were under-projected by about 2 points (big underdogs' were right); not seen in 2019–22, not detectable in 2026's four weeks, and FP has only Week 4. No change for Week 5; re-checked as weeks accrue |
| DraftKings opponent ranks (OPRK, item 8) | **checked 10-06 17:00: cannot be tested on past weeks** | DraftKings still serves Weeks 1–4, but revised the numbers after the games: in Weeks 2–4 about half the players' points-per-game in the same feed differ from our pre-lock copy (e.g. one RB's Week-2 figure 31.3 before lock, 21.2 now); only Week 1 is unchanged. Past ranks would carry the week's own result. Saving them before lock starts Saturday; a test needs a few captured weeks |
| C3: how well the field model predicted each contest's payout lines, LAG vs FP ownership | Wednesday | which ownership source to trust for satellite and cash lines |
| Regulars' share of each contest you enter (study list 21) | **done 10-06** | The toughest Week-5 fields are the two $4,444 MEGA satellites (about 28–31% of entries from the regulars), then the $333 Wildcat and the $555 super-satellite (15–17%); the Millionaire about 11%; the $20 super-satellites 0–8.5%. Descriptive; your plan stays as decided |
| Dollar figure of the final Week-5 setup on Weeks 2–4 (the money gate) | **done 10-06 evening (descriptive)** | Your Week-5 setup (overlap 4, round-robin), rebuilt for each past week's real contests, would have returned 23¢, 0¢ and 17¢ per $1 (what was entered: 11¢, 8¢, 44¢). No book, ours or any test version, won anything big in those weeks, so these are a few small cashes, i.e. luck. Caveats: those weeks' contests and book sizes differ from this week's, and the QB cap was scaled to them. Nothing decides on it |
| Simple-baseline benchmark (P3) on Weeks 2–4 | **done 10-06** | Our package (at the afternoon settings) against a plain best-projected book and a betting-market (props) book: big-win chance .52 vs .20 and .10 (three-week average; one-week luck applies), average finish .497 vs .478 and .486. The layers earn their place on these weeks |
| Outside review §6.1: how much the study results depend on the simulated field, checked against the real fields | **reviewer, moved up to tonight** (on the Weeks 2–4 replay books: limit 4 vs 5, all three fill orders) | how far to trust the 36-slate verdicts; it decides whether the limit-4 result stands |
| Outside review §6.2: realized points against FP projection and FP ownership | **done 10-06 (Week 4 only: FP has no earlier week)** | At the same FP projection, higher-owned players scored slightly LESS: −1.2 points per 10 ownership points [−4.2, +1.7], not different from zero; on our projection, zero. Consistent with your Week-5 tilt of 0. Re-fitted every week and pooled |
| "Where did the points go" (12b) and frequent winning combinations (X5) | laptop, Thursday (descriptive, Neo4j and queries) | patterns only; any lever they suggest needs a study, so Week 6 |
| Overlay monitor dry run | Thursday's slate, then Sunday live | whether any contest is short of its guarantee (read-only) |

## Started for Week 5 even though they cannot be graded before it

| Item | What happens | Why it cannot be graded earlier |
|---|---|---|
| Opponent-rank capture | DraftKings' player list saved before lock Saturday and Sunday (kept private) | the history starts at the first capture |
| Paper shadow B (our model without the two leaky QB features) | built Sunday, scored Monday beside ours and FP | needs Week 5's results; on Weeks 1–3 it already measured even (10-03) |
| R14 fact log | the agent logs structured, timestamped facts from the FP articles before lock; nothing uses them | graded after 4–6 weeks by design. The case for it: it costs nothing |
| Dashboard fixes merged + the "≥ Millionaire cash line" label | Wednesday, redeployed outside the weekend window | not a test |

## Not before Week 5, and the reason

| Item | Reason |
|---|---|
| Monday's early checkpoint (O1, A3, B2) | it is defined as the read after Week 5's results |
| B4 (FP Data Suite features in our player model) | our model does not pick Week 5's lineups (FP's projections do); its main input is still skewed (O-21, unfixed); the panel needs hours of the one heavy slot the rehearsals and studies need. Recommended date: with the O-22 fix after Week 5 |
| Field-behaviour model (10) and the method portfolio with online allocation (X3) | weeks of building and of results; nothing usable by Sunday |
| A player's bad-game signature (9b) and the field-softness index (X2) | descriptive builds of a day or more each; they come after the three studies above in the heavy slot, so Week 6 |
| The 2022–25 "untainted" money check | that history has no FP, SIS or props data, so it cannot test this package (your 10-06 rule: six-season panels never gate) |

## Day by day

- **Tue evening (done by 17:00):** study 41 read and reproduced; the Weeks 2–4 replay of the limit and all three fill
  orders; round-robin added to production; the OPRK check. **Running:** study 42 (three fill orders), the field check,
  the favorite-RB check.
- **Tue night:** study 42 read → my re-run; the field check → the limit-4 decision to you (or Thursday).
- **Wed:** SIS and the weekly vendor run → rehearsals A1, A2, A3 (heavy, in order) → the fill-order decision to you → the
  high-total-game study (reviewer) → its replay overnight. C3, the regulars' share, the money figure, the P3 code, the
  dashboard merge, the shadow-B and fact-log setup.
- **Thu:** the high-total-game decision to you → the shape-by-contest study (reviewer) → its replay; P3 replay; §6.1
  audit (reviewer); §6.2, 12b, X5; overlay dry run; O-25 and O-27 dry runs; the prospective-gate check.
- **Fallback when both Sunday FP captures are stale** (the outside reviewer): ours for everyone today; stale FP plus our
  inactive-teammate bumps is better. Recorded as OPEN-DEFECTS O-38 for Week 6; a double failure is unlikely this Sunday.
- **Fri:** the decision sheet with every result → your yes/no on each → merges → the final rehearsal on the merged code →
  `--check`.
- **Sat:** arm; opponent-rank capture; the 10:30 canary.
