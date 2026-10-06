# Preregistration: study 34, the regulars' player habits as a selection tilt, on the operator's goal (DRAFT 2026-10-06)

**Transfer, said first:** the panel's projections are OURS (no FP history). A PASS says the habits add to a
projection-based book. It cannot prove they add on top of FP, which picks the lineups from Week 5. The weekly Monday
"picks vs the field" score (requested 10-06) is the live check.

**Status: DRAFT 2026-10-06.** The reviewer drafts it and freezes it after the calibration census and the smoke; the
laptop comments, acks the binding census and re-runs the frozen reader.

**The prior, said second:** the regulars' report already tested copying their visible habits (§6 Test 1). A model of
their tilt predicted their picks well, but the predicted picks' gain was indistinguishable from the null (p 0.55 /
0.44 / 0.93): their edge looks like pre-lock knowledge we lacked, most likely better projections (in Week 4 they sided
with FP). **The expected verdict is NO DIFFERENCE.** It is run because the operator asked for the direct test now and
it is cheap.

## 1. Why
- **The operator (10-06):** "do we feel that our ability to choose players - both stacks as well as boom players - is
  at a level comparable to the winners?", then "Do we have to wait until Thursday to test that?"
- **The evidence** (`reports/2026-10-05-regulars-player-choices.md`):
  - The 117 max-entry regulars beat the rest of the Millionaire field by +6.1 points per lineup in 2026 Weeks 1–4
    (null p 0.002).
  - Our book was −3.8 (p 0.14).
- **Study 22a** tests OUR projection's bias. It waits on the parked six-season co-run, and tests a projection that no
  longer picks the lineups.

## 2. The tilts (pre-lock; the laptop's design concern, adopted 10-06)
- **Our book already shares the three most common habits at about their size** (the report's §2):
  - salary rise: theirs −0.11, ours −0.07;
  - opponent allowed: −0.13 vs −0.12;
  - last game above projection: −0.12 vs −0.13.
  So tilting further along them overshoots.
- **GAP (the DECISION arm)** tilts along (their tilt − ours) on the features where at least 84% of them agree and we
  differ:
  - h_gap = −0.19·z(value per $1k: our mean / salary) − 0.09·z(the last PLAYED game's DK points) − 0.06·z(last week's
    opportunity share: target share for WR / TE, carry share for RB, none for QB) + 0.05·z(the Questionable tag).
  - FP above ours (+0.13 vs −0.15) is the largest gap, but history has no FP, and FP closes it live.
- **SHR (exploratory)** tilts along the three shared habits:
  - h_shr = −z(the last played game's DK points) − z(salary change) − [weeks 2–5] z(the opponent's season-to-date DK
    points allowed per game to the position).
- **Common to both:** each z is within slate × position over the skill pool, and missing = 0. "Last week" is
  implemented as the last PLAYED game (study 22a's H3), so byes do not drop rows.

## 3. Arms (study 31's harness; Rev3, K 26, caps 13 / 6, head, `enter_layout` `3cb051ac…`; all with the 0.20 term)
- CT / GAP_CT / SHR_CT: the house shape on the mean, mean × (1 + β_gap·h_gap) and mean × (1 + β_shr·h_shr).
- MIXT / GAP_MIXT / SHR_MIXT: the winners' mix, the same.
- **β, from one outcome-blind calibration census on 1406 (five runs):**
  - **β_gap:** the smallest of {0.2, 0.4, 0.6, 0.8, 1.0} whose dealt entries' mean h_gap moves (GAP − reference,
    pooled over shapes) by ≥ ‖gap‖² = 0.0503. That is the move that closes each feature's gap, were the features
    uncorrelated. The census also prints each feature's achieved mean-z shift beside its gap target (the laptop).
  - **β_shr:** the smallest of {0.02, 0.04, 0.06, 0.08, 0.10} with Δh_shr ≥ +0.36.

## 4. Endpoint and rule (studies 31 / 33)
- **PRIMARY (one decision arm):** P(≥ 1 big seat) per slate, GAP − reference pooled over the two shapes.
  - 36 slates (2023–24), banks 1449–1454 (scanned clean by the laptop, wide pattern); B 20,000, seed 20261016;
    two-sided 0.95.
- **Guards:**
  - guard 1, mean entry pct, one-sided lower > −0.015;
  - guard 2, expected big seats ratio ≥ 0.80.
- **Verdicts:**
  - DEAD LEVER: GAP identical to its reference on > 80% of slate-banks;
  - WORSE;
  - PASS: lower > 0, at most one negative season, guards hold;
  - FAIL (guard);
  - NO DIFFERENCE.
- **EXPLORATORY:** SHR − reference, pooled and per shape; GAP per shape; GAP in weeks 2–5 vs 6+; the dealt entries' mean
  h_gap and h_shr per arm.

## 5. What a verdict can do (to be frozen)
- **PASS:** the gap tilt becomes a candidate class-S tilt on the live (FP) means, offered to the operator with its
  transfer caveat. It is armed only after a paired shadow on a 2026 week, and the weekly picks-vs-field line watches it.
- **NO DIFFERENCE / WORSE:** the habits are recorded as the field's habits, not a lever. The weekly line stays the
  monitor of whether FP closed the gap.

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
