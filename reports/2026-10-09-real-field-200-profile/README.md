# What the real 200+ lineups look like (his W1–4 fields), against ours (2026-10-09, 23:03 CDT)

**Why:** the operator, 10-09 late evening: "my hope is that we can get to a point where you're, you're seeing scores, you know,
over 200 fairly regularly", and then "It sounds like you're giving up on the high scores. That's not what I want." (HANDOFF
`f68ebf50`, `f07f4c13`).

**Data:** the money gate's private field cache, all entries of his W1–4 contests (1.65M lineups). Players are mapped to
position / team / game by each week's T-70 frame (0.7% unmapped, dropped). **Aggregates only:** no usernames, no dollars, no
rows. Script: `winners_shape.py` (beside this file; it reads ~/private, so it runs only on the laptop).

| | All field | Field top 1% | Field 200+ (23,610) | Our real entries (535) |
|---|---|---|---|---|
| QB + 0 own receivers | 17.8% | 9.3% | 11.0% | 0.4% |
| QB + 1 | 53.3% | 47.0% | 45.0% | 3.4% |
| QB + 2 | 27.2% | 38.3% | 38.3% | 93.3% |
| QB + 3+ | 1.7% | 5.4% | 5.7% | 3.0% |
| Bring-back ≥ 1 (a player from the QB's opponent) | 44.0% | 60.6% | 62.5% | 98.1% |
| **Bring-back ≥ 2** | 7.7% | 15.4% | **18.5%** | **1.9%** |
| **5+ players from one game** | 7.1% | 15.7% | **19.0%** | 15.9% |
| Mean most players from one game | 3.00 | 3.41 | 3.50 | 4.16 |
| The QB's own RB | 19.3% | 13.5% | **14.0%** | 16.1% |
| Distinct games | 5.21 | 4.81 | 4.71 | 4.10 |

**Per week** (the 200+ lineups are mostly W1, a high-scoring week: 22,520 of 23,610):
- **Bring-back ≥ 2 among the top 1%:** W1 19.7%, W2 3.7%, W3 19.8%, W4 7.2% (the field 6.9–8.1%).
- **5+ from one game among the top 1%:** W1 20.2%, W2 3.6%, W3 23.5%, W4 3.5%.

**Reading:**
- The highest-scoring lineups concentrate on one game. Nearly 1 in 5 has two or more players from the QB's OPPONENT (the
  3+2 / 4+2 game stack). Our real books almost never built that (1.9%), although they stacked the QB's side heavily.
- The QB's own RB is rarer among the 200+ lineups than in the field, consistent with study 96 (the RB mate adds nothing).
- In the low-scoring weeks (W2, W4) the pattern is weak, so this supports a game-stack SLEEVE, not a whole-book change.
- Study 102's TAIL_STACK8 (the A1 rows as full game stacks, QB + ≥ 2 own + ≥ 2 opponents, in the top-total games) tests it
  on the harness.
- Descriptive; outside the harness's 2023–24 slates; no selection is made on it.
- **It conditions on the outcome** (the reviewer's caveat): 200+ lineups concentrate in the games that went off, so this is what a
  200+ lineup looks like AFTER the fact. It does not show that BUILDING the shape raises P(200+) before the fact; that is what
  TAIL_STACK8 tests. The older game-stack reads (studies 26 / 74, older construction) were NO DIFFERENCE.
