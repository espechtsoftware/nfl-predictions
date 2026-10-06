# Preregistration: study 34, the regulars' player habits as a selection tilt, on the operator's goal (FROZEN 2026-10-06)

**Transfer, said first:** the panel's projections are OURS (no FP history). A PASS says the habits add to a
projection-based book. It cannot prove they add on top of FP, which picks the lineups from Week 5. The weekly Monday
"picks vs the field" score (requested 10-06) is the live check.

**Status: FROZEN 2026-10-06** by the reviewer, after the laptop's comments (the GAP design, value excluded, the owned-set units, the landing rules), the calibration census and the smoke (§6), before any scored bank. The laptop acks the binding census and re-runs the frozen reader.

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
- **GAP (the DECISION arm)** tilts along (their tilt − ours) on the BEHAVIOURAL features where at least 84% of them
  agree and we differ:
  - the last PLAYED game's DK points: −0.09;
  - last week's opportunity share (target share for WR / TE, carry share for RB, none for QB): −0.06;
  - the Questionable tag: +0.05.
- **Value per $1k (−0.19) is EXCLUDED** (agreed with the laptop at the first calibration point, outcome-blind).
  - It is computed on OUR projection, so their lower value tilt is their different projections showing through. In
    Week 4 they sided with FP; FP closes that live.
  - At β_gap 0.2, a mean tilt moved the book's value −0.02 against a −0.19 target, while last game's points
    overshot 2.4×.
- **SHR (exploratory)** tilts along the three shared habits:
  - h_shr = −z(the last played game's DK points) − z(salary change) − [weeks 2–5] z(the opponent's season-to-date DK
    points allowed per game to the position).
- **Units (both arms):** every z is in the report's units. It is standardised within slate × position over the pool
  players with PREDICTED (TABPFN_LS, pre-lock) ownership ≥ 0.2%, then applied to every pool player; missing = 0. "Last
  week" is the last PLAYED game (study 22a's H3).

## 3. Arms (study 31's harness; Rev3, K 26, caps 13 / 6, head, `enter_layout` `3cb051ac…`; all with the 0.20 term)
- CT / GAP_CT / SHR_CT: the house shape on the mean, mean × (1 + β_gap·h_gap) and mean × (1 + β_shr·h_shr).
- MIXT / GAP_MIXT / SHR_MIXT: the winners' mix, the same.
- **The calibration (outcome-blind, bank 1406; fixed before it ran):**
  - **Round 0:** GAP weights = the gaps, β_gap 0.2, giving each feature's achieved shift a_f.
  - **One reweighting:** w_f = g_f × g_f / a_f (one round only).
  - **The grid** on those weights, in paired runs:
    - β_shr ∈ {0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02};
    - β_gap ∈ {0.1, 0.15, 0.2, 0.25, 0.3, 0.4}.
  - **β_gap** is the grid value whose per-feature shifts all lie within ±30% of their gaps; if several, the smallest
    worst ratio; if none, the minimiser of max_f |a_f / g_f − 1|.
  - **β_shr** is the minimiser of |Δh_shr / 0.36 − 1|, i.e. their habits at THEIR size; the coarse first grid had
    overshot to 1.9×.
  - The census lines are printed in §6 at the freeze.

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

## 6. Calibration, smoke and integrity
- **The calibration census** (bank 1406, outcome-blind; `results/s34/CALIB_s34.txt`):
  - Round 0 (weights = the gaps, β_gap 0.2) overshot: last game 2.27×, share 1.59×, Q 1.24×.
  - The one-round weights are last_pts −0.03960, share_last −0.03783, q_tag +0.04029.
  - On the grid, **β_gap 0.2 is the only value with every feature within 30%** (ratios 1.02 / 0.88 / 0.89). At 0.15
    the worst miss was 0.36, at 0.25 it was 0.32.
  - **β_shr 0.0125** gives a ratio of 1.12, the closest to 1 (0.01: 0.86; 0.015: 1.34).
  - The superseded first point (value included, pool-z units) is appended to that file.
- **The binding census at the frozen values** (1406, 36/36, code `df9429f`; `CENSUS_s34_binding.txt`, `c41b32d4…`):
  - It reproduces those ratios exactly.
  - No arm is identical to its reference (GAP .000, SHR .056), so neither is a dead lever.
  - No short books.
  - The habit inputs cover .90 (last game), .94 (salary change, opponent allowed).
- **The smoke** (2023 W1, 1406, the full path) found one reader defect, fixed before the freeze. The weeks-2–5 subset is
  empty on a one-slate smoke, so the bootstrap crashed. It now prints "no slates" (only the traceback was read). The
  census and reader then exited 0 with their 2 headers, and the reader REFUSED mechanics-only rows.
- **Code:** nfl2 `production/s34-regulars-habits-20261006` @ `6160a02`:
  - `experiments/s34_regulars.py`, sha256 `c3c5a57beb01017334e697162031f74d6c88d082f3ced43dd1076ce50d5421df` (β and
    weights frozen in code, with no environment override);
  - `scripts/s34_drive.py`, `cd410d45bbb6e4c7ca7d3d3817dd19f086eb668e3aa5073e1998ec7e6594fd43`;
  - **`scripts/s34_report.py` (the reader), sha256 `2da832bf677315b166c5ed5941896ba466a600c697580e78c561c2faade6ca14`**;
  - `scripts/s34_census.py`, `0cefa46347d39e236e520f1649fcdd3c14514a6ac8646d3b7a8ee7f7f87a1f15`;
  - `tests/test_s34_regulars.py`, `f6393bb753077ca81716a3740413c30336fcdf4e034c91276f0122fddda2dc9b` (8 tests).
- **Production `enter_layout`:** `3cb051ac…` (`da399bdb`). **Banks:** 1449–1454 (scanned clean by the laptop). **Seed:**
  20261016.
- **Order:**
  1. this freeze;
  2. the laptop's ack;
  3. the scored run;
  4. the confirmatory census;
  5. the read;
  6. the laptop's re-run;
  7. the LEDGER row and an Addendum.
