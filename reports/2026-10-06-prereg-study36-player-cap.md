# Preregistration: study 36, player depth on the recommended book (a stricter general player cap) (DRAFT 2026-10-06)

**Status: DRAFT 2026-10-06.** The reviewer drafts it and freezes it after the calibration census and the smoke. The
laptop acks the binding census and re-runs the frozen reader.

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

## 6. Integrity (filled at the freeze)
Code (nfl2 `production/s36-player-cap-20261006`), the reader sha, the shares, the calibration census and the binding
census. The census asserts each arm's player cap equals production's int(share × K) floor at K 26.
