# "I want to score this week": what can go live before the 17:55 arm, ranked (2026-10-10, afternoon)

**For:** Erich, and the laptop and reviewers who would build, check and arm. Your words after the afternoon page: "I want to score
this week." So this page drops the paper arms and lists only what can be in Sunday's book today, each with what it needs, its
evidence on both sides, its cost on your Week-4 book, and the risk. Your decision on each; the team's judgment on whether it
fits the hours left. The honest frame first: the book's chance of a big win in a normal week is about 1 in 15 to 1 in 30; the
items below move that by a few slates in a hundred at most, and only one of them is free of a bet.

## The three, in order

| # | Change | What it is | Evidence for | Evidence against | On your Week-4 book | What it needs today | My call |
|---|---|---|---|---|---|---|---|
| 1 | **O-60: the late-scratch next-man-up bump** | When a player is ruled out at the 10:30 inactives after Fantasy Points' last update, our model's bump to his teammates reaches the FP-sourced build (today it does not) | Weeks 2–4's winning lineups were built on next-man-up plays (Schultz, Hockenson, Warren, Flowers). FP's own history: a scratched WR → his teammates +15 points when FP knows. Each week 18–28 players flip to OUT at 10:30 (O-59's counts); FP zeroes the player within minutes but his teammates stay at pre-scratch numbers | None on the idea. The risk is operational: a money-path change on arm day | Zero unless a relevant scratch lands after FP's update; then the affected team's rows change | Wire the branch (`review/late-scratch-bump-20261008` @ fbad73be, 15 tests, default off) with a `--dk-status` fed from the 10:47 pull; the Week-4 gates byte for byte with it off; one ON check with a simulated scratch; the reviewer's review; the `--check`. About two hours if nothing surprises | **Do it if the team can finish by 17:00.** It is a repair, not a bet: it only acts when the book is otherwise blind, and that is exactly how the last three winners' players were made |
| 2 | **QB cap 3 (from 5)** | No quarterback in more than 3 of 26 lineups; the top-total game's two QBs then hold at most 6 rows instead of 10 | The Millionaire was won from the 2nd- or 3rd-highest total by a favoured QB in Weeks 1, 3 and 4; the top-total game is the top-scoring game 16–19% of the time; this week's top total (DET–ARI, 54.5) is nine points clear, so FP's ownership and the solver will pile there. Study 100: +1.7 on the big-win chance, better on both opponent sets | Study 101, the fresh draw: −0.4 (A +0.3, B −1.0): a wash in the harness. More QBs means lower-projected rows (the real cost is the Week-4 check's first number) | Not yet measured; a 15-minute check (QB_CAP_ROWS=3 on the LIVE build): rows changed, FP per row, QBs, the top game's rows, FAVHI's four rows still complete | One existing setting; the Week-4 check; study 38 follows the QB cap automatically; the arm-only commit. Under an hour | **Yes, as the hedge**, if you accept a wash in the test model for a book that is not 38% on one game. If the check shows FAVHI or ONECATCH losing rows, no |
| 3 | **HOT_WRTE1: at most one hot WR or TE per lineup** | A WR or TE coming off a game at 2× his average counts as hot; a lineup may hold one | Your real fields: a lineup with a hot WR/TE reached the top 1% at odds 0.37 / 0.70 / 0.40 in Weeks 2–4 and 0.38 in your contests; the Sunday book holds 1.08 per lineup (22 of 26 lineups; 6 with two) | Studies 109 and 115 in the harness: −1.8 (all positions) and −1.6 (WR/TE only), worse on both opponent sets; on 2023–24 slates the hot players carried forward | 6 lineups change (the ones holding two hot WR/TE); FP cost per row small (the check's number) | The study-115 switch (unmerged), the Week-4 gates, the hot file (already produced for the 6z2 paper arm), study 38's classification. About two hours | **Your call; I would not override a twice-negative harness read for a rule the fields support only three weeks.** It stays on paper (6z2) either way, so Monday reads it |

**Everything else stays as armed:** the package, the row rules, ONECATCH, FAVHI, the cheap block (your 12:30 decision), Rev7.
The stars rule and the value cap stay on paper: the stars rule failed its own Week-4 real-field gate and the value cap read
worse in the harness; neither has a fresh-draw pass.

## Why not more

- **No new harness study.** Fifty reads this week; a one-in-three false-pass rate per comparison; no time left for a fresh-draw
  check. A pass this afternoon would be luck wearing a number.
- **No construction rule beyond the three.** The removal study says the eight live rules each help or are a wash; the core
  players are the right kind (volume backs and receivers, a cheap high-target TE). The book's ceiling is set by which game it
  bets on and by late information, which is where items 1 and 2 act.
- **The arm.** Each adopted item is one setting in the 17:55 arm-only commit; the Week-4 gates must pass with the switches off
  (byte for byte) and the canary receipt must show each one applied. If any check fails, that item waits for Week 6 and the
  book stays as armed now.

## Monday

The real-field report scores the live book beside the paper arms; add the hot-player, QB-cap and game-rank columns by lineup so
each of today's choices is read on its own, and the points-by-book-rank line from the dealing review.
