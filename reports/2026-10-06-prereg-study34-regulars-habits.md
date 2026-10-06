# Preregistration: study 34, the regulars' player habits as a selection tilt, on the operator's goal (DRAFT 2026-10-06)

**Transfer, said first:** the panel's projections are OURS (no FP history). A PASS says the habits add to a
projection-based book. It cannot prove they add on top of FP, which picks the lineups from Week 5. The weekly Monday
"picks vs the field" score (requested 10-06) is the live check.

**Status: DRAFT 2026-10-06.** The reviewer drafts it and freezes it after the calibration census and the smoke; the
laptop comments, acks the binding census and re-runs the frozen reader.

## 1. Why
- **The operator (10-06):** "do we feel that our ability to choose players - both stacks as well as boom players - is
  at a level comparable to the winners?", then "Do we have to wait until Thursday to test that?"
- **The evidence** (`reports/2026-10-05-regulars-player-choices.md`):
  - The 117 max-entry regulars beat the rest of the Millionaire field by +6.1 points per lineup in 2026 Weeks 1–4
    (null p 0.002). About 17 of their 24 points came from picking better players at the same price.
  - Our book was −3.8 per lineup (p 0.14).
- **Study 22a** tests whether OUR projection misses in the habits' directions. It waits on the parked six-season
  co-run, and tests a projection that no longer picks the lineups.
- **This study asks the decision question directly:** does tilting the book toward the regulars' habits raise his
  chance of a big win?

## 2. The habits (pre-lock; the regulars' three most widely shared tilts, 89–95% of users)
- **Last played game's DK points** (season s, before week W; nflverse weekly stats, DK scoring): they SELL last week's
  big game (tilt −0.08; −0.12 vs projection).
- **Salary change since last week** (`salary_delta_wow`): they SELL salary rises (−0.11).
- **The opponent's season-to-date DK points allowed per game to the position** (weeks < W): they DISTRUST tiny early
  samples (−0.13). Used in weeks 2–5 only, where the samples are 1–4 games.
- **The habit score:** h = −z(last) − z(salary change) − [W in 2–5] z(opponent allowed). Each z is within slate ×
  position over the skill pool, and missing = 0.

## 3. Arms (study 31's harness; Rev3, K 26, caps 13 / 6, head, `enter_layout` `3cb051ac…`; both with the 0.20 term)
- **CT** and **REG_CT**: the house shape + term, on the mean / on mean × (1 + β·h).
- **MIXT** and **REG_MIXT**: the winners' mix + term, the same.
- **β is fixed by an outcome-blind calibration census on bank 1406.** It is the smallest of {0.02, 0.04, 0.06, 0.08,
  0.10} for which the dealt entries' mean habit score, REG − reference pooled over shapes, is ≥ +0.36. That is the
  regulars' combined tilt across the three habits (0.11 + 0.12 + 0.13 sd), so the book leans the way they do, by about
  as much.

## 4. Endpoint and rule (studies 31 / 33)
- **PRIMARY:** P(≥ 1 big seat) per slate, REG − reference pooled over the two shapes.
  - 36 slates (2023–24), six fresh banks 1449–1454 (to be scanned by both); B 20,000, seed 20261016; two-sided 0.95.
- **Guards:**
  - guard 1, mean entry pct, one-sided lower > −0.015;
  - guard 2, expected big seats ratio ≥ 0.80.
- **Verdicts:**
  - DEAD LEVER: REG identical to its reference on > 80% of slate-banks;
  - WORSE: upper < 0;
  - PASS: lower > 0, at most one negative season, guards hold;
  - FAIL (guard);
  - NO DIFFERENCE.
- **EXPLORATORY:** each shape; weeks 2–5 vs 6+; the dealt entries' mean habit score per arm.

## 5. What a verdict can do (to be frozen)
- **PASS:** the habits become a candidate class-S tilt on the live (FP) means, offered to the operator with its
  transfer caveat, and armed only after a paired shadow on a 2026 week.
- **NO DIFFERENCE / WORSE:** the habits are recorded as the field's habits, not as a lever for us. The weekly
  player-choice score stays the monitor.

## 6. Integrity (filled at the freeze)
Code (nfl2 `production/s34-regulars-habits-20261006`), reader sha, β and the calibration census, the binding census,
the banks scan. Order:
1. this draft;
2. the laptop's comments;
3. the calibration census;
4. the smoke;
5. the freeze;
6. the binding census;
7. the laptop's ack;
8. the scored run;
9. the confirmatory census;
10. the read;
11. the laptop's re-run;
12. the LEDGER row and an Addendum.
