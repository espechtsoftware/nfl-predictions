# Preregistration: study 36, player depth on the recommended book (a stricter general player cap) (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the calibration census and the smoke (§6), before any scored bank. The laptop acks the binding census and re-runs the frozen reader. The reference book is the one he said yes to on 10-06 (the winners' mix + the tilt + the QB cap).

## 1. Why
- **The operator (10-06), after agreeing to the recommended book** (the winners' mix + the ownership tilt + study 35's
  per-QB cap): "let's consider if we need to change the way it's still including the other most used player."
- **What the data say** (descriptive; aggregates only):
  - The regulars' 468 weekly portfolios (median 150 entries) have a TOP non-QB player at .525 (median .487), much as
    ours (.549).
  - The difference is DEPTH. Their 2nd / 3rd / 5th / 10th sit at .431 / .370 / .296 / .205, with about 1.8 players
    over 40% of entries, 4.0 over 30%, 9.1 over 20%, and 77 distinct non-QB players.
  - Our recommended book (MIXT_QA, on study 35's census bank) has .537 / .526 / .510 / .402, with about 9.4 players
    over 40% and 26 distinct.
  - The production player cap (0.5 × K = 13 of 26 rows) binds for about ten players. Part of it is arithmetic: 26 rows
    cannot hold 77 players.
- **The production lever already exists:** `UNION_MAIN_CAP` → `union_reselect --main-cap-share` (default 0.5),
  int(share × K) rows, applied to every player in both mains, the QB and DST caps on top. No new code is needed.
- **Priors:**
  - Study 1b, K 105: an entry-weighted ~30% player cap halved the worst single-bust swing but cost mean finish
    (−0.035, both seasons); its ticket secondaries went the other way.
  - L17 (PREREG-L17, `0272209`; K 36, tickets at p89, the house shape): LOOSER caps than 50% cost tickets
    monotonically. This study tests the stricter side of that curve.
  - Guard 1 (finish) is the likely binder, and is reported prominently.

## 2. Arms (study 31's harness: 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`, the 0.20 term, study 35's QB cap of 5 rows in every arm)
- **MIXT_QA** (reference): production's player cap (0.5 → 13 rows); the book recommended after study 35.
- **MIXT_QAP** (DECISION): the general player cap at share A, int(A × 26) rows.
- **MIXT_QAP2** (exploratory): a milder share B.
- The DST cap (6 rows) and the QB cap (5 rows) are unchanged everywhere.

## 3. The calibration (outcome-blind; bank 1406; the rule stated to the laptop before it ran)
- Grid: shares {0.25, 0.30, 0.35, 0.40, 0.45} → 6 / 7 / 9 / 10 / 11 rows.
- **A is the loosest share whose mean non-QB "players over 40% of the dealt entries" is ≤ 3** (the regulars' 75th
  percentile). **B is the loosest with ≤ 6.**
- **Disclosed before the remaining grid points were read:** this count is not monotone near the cap.
  - A player at the row cap sits just above or below 40% of the ENTRIES depending on which rows the head layout deals
    more.
  - At 0.45 (11 rows ≈ 42% of rows) the first pair showed 9.7 players over 40%, more than the 13-row reference's 9.4.
  - The rule is applied as written. The census prints the full depth profile and each share's projection cost, so the
    choice is visible.

## 4. Endpoint and rule (study 18b's)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_QAP − MIXT_QA.
  - Banks 1461–1466 (scanned clean by the laptop); B 20,000, seed 20261018; two-sided 0.95.
- **Guards:**
  - guard 1, mean entry pct, one-sided lower > −0.015;
  - guard 2, expected big seats ratio ≥ 0.80.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:** MIXT_QAP2 − MIXT_QA; per arm, the dealt non-QB depth profile and the top QB.

## 5. What a verdict can do (to be frozen)
- **PASS:** the stricter share becomes a candidate setting (`UNION_MAIN_CAP=<A>`, an existing lever), offered with its
  evidence and its projection cost, and rehearsed Friday.
- **NO DIFFERENCE:** depth is a matter of taste, without a measured cost or benefit. He may choose it, told plainly
  what it costs on paper.
- **WORSE or FAIL:** the recommended book keeps production's 0.5 cap.

## 6. Calibration, smoke and integrity
- **The calibration census** (bank 1406, outcome-blind; `results/s36/CALIB_s36.txt`; dealt non-QB depth):

  | share (rows of 26) | top player | 2nd / 5th / 10th | over 40% | over 30% | distinct | projection per lineup |
  |---|---|---|---|---|---|---|
  | 0.50 (13), the reference | .549 | .537 / .510 / .402 | 9.42 | 11.47 | 26.0 | — |
  | 0.45 (11) | .474 | .461 / .439 / .402 | 9.72 | 12.86 | 27.3 | −0.57 |
  | **0.40 (10)** | **.432** | .422 / .403 / .379 | **3.67** | 13.83 | 28.5 | **−0.95** |
  | **0.35 (9)** | **.390** | .383 / .363 / .347 | **0.11** | 14.81 | 30.0 | **−1.33** |
  | 0.30 (7) | .317 | .309 / .286 / .280 | 0.00 | 3.58 | 35.1 | −2.32 |
  | 0.25 (6) | .278 | .270 / .258 / .244 | 0.00 | 0.06 | 38.5 | −2.94 |

  - At every level: no passes to A1, no short books, cells within 3 points.
  - **By the rule: A = 0.35** (the loosest with ≤ 3 players over 40%; 0.40 has 3.67) and **B = 0.40** (the loosest
    with ≤ 6; 0.45 has 9.72).
- **Disclosed, in plain words: a flat cap does not reproduce the regulars' SHAPE.** Theirs falls steeply from one
  heavy player (.525 → .205 by the 10th). A flat cap chops the top and makes a PLATEAU: at 0.35 the top fifteen players
  all sit near 35–39%, and the count over 30% RISES (11.5 → 14.8). The study therefore answers "less exposure to our
  most-used players", not "copy the regulars' curve"; a 26-row book cannot hold their 77 players.
- **The binding census at the frozen shares** (1406, 36/36, code `56a3019`; `CENSUS_s36_binding.txt` `c5507002…`, raw
  `df52b20d…`):
  - It reproduces the calibration exactly. It ASSERTS each row's player / DST / QB caps equal production's floors
    (13 / 9 / 10 rows; DST 6; QB 5).
  - It prints the projection cost: −1.33 and −0.95 per lineup, against study 35's QB cap at −0.31.
  - Neither arm is identical to the reference on any slate-bank.
- **The smoke** (2023 W1, 1406, the full path): the census and reader exited 0; the reader printed its 2 headers and
  its header names STUDY 36 (tested), and it REFUSED mechanics-only rows.
- **Code:** nfl2 `production/s36-player-cap-20261006` @ `b052a0e`:
  - `experiments/s36_player_cap.py`, sha256 `9e940c8c4a32d624135fb4bddac418c32235be5340d9c6666622c9aafe7388a7`;
  - `scripts/s36_drive.py`, `955559e9816d3bfa44b6e16dc8e3dc4c2fb4b695b15052fcef8dd19f68edcefd`;
  - **`scripts/s36_report.py` (the reader), sha256 `f915e9504121c18b455a936fb0830b7f9dc10db7f929cfb469ac033956420381`**;
  - `scripts/s36_census.py`, `1aa0baf9cf42bde1aa7333d73b4fc68177a76391151872c59ae18f44b227bedb`;
  - `tests/test_s36_player_cap.py`, `7056c9f2ed3e3887c981bb0cad144f4c99c26a7640e48bf2cbc5880a60466fc5` (5 tests).
- **Production lever if adopted:** `UNION_MAIN_CAP=0.35` (`--main-cap-share`, default 0.5; no new code).
  **Banks:** 1461–1466 (scanned clean by the laptop). **Seed:** 20261018.
- **Order:**
  1. this freeze;
  2. the laptop's ack;
  3. the scored run;
  4. the confirmatory census;
  5. the read;
  6. the laptop's re-run;
  7. the LEDGER row and an Addendum.
