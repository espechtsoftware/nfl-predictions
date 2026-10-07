# The prior-top term: a player's past top-1% frequency from the prior weeks' REAL Millionaire fields, as a Week-5 input (2026-10-07, 04:45 CT)

The operator (10-07, 04:35): "Try it this week instead: a player's past top-1 percent frequency from the prior weeks'
real fields." This file is the money-path rule's test (a fixed-book replay on Weeks 2–4) plus the Week-5 input file and
the exact arguments, so the operator can decide and the laptop can enter or paper it. By the outside reviewing agent.

## 1. The input

For each player (DraftKings id), the mean over the prior 2026 weeks of his share of the real Millionaire top-1% lineups
(`make_priortop_files.py`, from the settlement fields). Turned into a bonus in the union's existing ownership-term
format: `pred_own = 5 × z(prior_top within position)`, negatives set to 0, so `--main-own-tilt 0.20` adds about one
projected point per standard deviation, the size the player-level attribution measured (`reports/2026-10-07-winners-strategy-study.md`
§5: beyond projection, salary and ownership, +0.11 on log lift, t 1.1 pooled, positive in all three weeks; +1.0 points
per z on beating the projection, t 1.3). Files: `priortop-w2.csv` (from W1), `-w3` (W1–2), `-w4` (W1–3), **`priortop-w5.csv`
(W1–4; 574 players, 114 with a positive bonus; the five largest: Gibbs 42.4, Lamb 38.6, Schultz 32.4, Collins 27.8,
Prescott 27.1 — in bonus units, i.e. ×0.20 points).** The union matches on `dk_player_id`; players new to the slate get
no bonus; the coverage gate was passed at 0.5 in every replay week.

## 2. The replay (Weeks 2–4 real fields; the live Week-5 settings: overlap 4, round-robin, QB cap 5, no ownership term;
FP projections in W4, ours in W2–3; integration `fc27f3aa`; `replay_priortop.sh`)

| Week | Arm | P(≥1 big) | E[big] | mean entry pct | projected / row | best row | distinct players | rows shared with live |
|---|---|---|---|---|---|---|---|---|
| 2 | live | .041 | .041 | .424 | 136.95 | 163.0 | 53 | — |
| 2 | + prior-top | .014 | .014 | .417 | 132.43 | 140.5 | 53 | 0 |
| 3 | live | .002 | .002 | .516 | 133.11 | 164.6 | 48 | — |
| 3 | + prior-top | **.303** | .333 | **.746** | 129.64 | 174.9 | 54 | 0 |
| 4 | live | .434 | .434 | .502 | 144.00 | 181.1 | 49 | — |
| 4 | + prior-top | **.764** | .764 | .485 | 138.23 | 180.6 | 48 | 0 |

Study 38's guards over the three weeks: guard 1 (mean entry pct) −.007 / +.230 / −.018 → mean **+.068** (holds, carried
by Week 3); guard 2 (expected big seats) 1.11 vs 0.48, ratio **2.3** (holds). Ahead on P(≥1 big) in 2 of 3 weeks.

## 3. Reading

- It is the same shape of evidence as the shared-player lever (ahead in two of three real weeks, guards held pooled),
  with two differences that matter: the cost is large (4–6 projected points per row, against ~0 for the overlap limit),
  and it changes every row, so a Week-2 kind of week is paid in full. The W2 file is built from one prior week; the
  feature gets more stable each week.
- Mechanism: ride the players who have already been in winning lineups. The regulars do the opposite (the graph:
  they fade recent big scorers, ρ ≈ −0.20), and Week 2, the week the regular we model won, is the week this term lost.
  Weeks 3 and 4 rewarded it heavily. Three weeks cannot separate "the signal is real" from "the same few players kept
  hitting"; the player-level test says the signal is weakly positive, not strong.
- If entered, a sleeve (say 8–13 rows carrying the term, the rest the live book) limits the cost in a Week-2 week while
  keeping most of the Week-3/4 gain; the replay above is whole-book and should be re-run on the sleeve form before that
  form is entered.

## 4. What entering it in Week 5 takes

The union needs no new code: `--main-own-tilt 0.20 --main-own-source <priortop-w5.csv> --main-own-min-coverage 0.5`.
The host (`scripts/sunday_build_host.sh`) derives the ownership source from the FP capture when `UNION_MAIN_OWN_TILT`
is non-zero, so a different source needs a small, reviewed change (an override env naming the file) plus the Friday
rehearsal, or the file placed where the host reads the source, which the laptop and reviewer should decide. Study 38's
frozen parity means an entered term also needs the reviewer's amendment before the lock. The no-code route is a study-38
context column on Sunday (the same union arguments, paper only), graded Monday on the real field.
