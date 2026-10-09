# Preregistration: study 90, the ownership cap at + 10 points against the armed + 15, and a second read of the armed package, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (12:56 CDT)** by the outside reviewer — **THE DESIGN IS COMMITTED BEFORE ANY CODE RUNS** (study 89
read the same slates). The code follows; the reviewer reviews, runs the binding census and FREEZES; the laptop acks.
- **Banks and seed:** proposed **1755–1766** (twelve: set A 1755–1760, set B 1761–1766), seed 20261135; the laptop scans them
  and the derived bases (b+50 1805–1816, b+700 2455–2466) first.
- **Target:** tonight, after study 88. **Nothing changes for Week 5.**

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09 (in the outside reviewer's session; the laptop records it verbatim):** asked "Test 'stay even closer
  to the field' (each player at most projected ownership + 10 points, vs the +15 you just armed) tonight as a Week-6
  candidate?", he chose **"Yes, test tonight (Recommended)"**. Before it: "I don't want to enter softer fields. I want to get
  better with what we enter. ... I'm still open to other ideas - not convinced that we have lineup selection down".
- **Study 89 (Addendum 186, READ c3f5a7ee):** CAP35_OWN15 − LIVE_CB +1.2 (A +0.5, B +1.9); CAP35_OWN15 − CAP35 +3.2 (both
  draws); the real-ownership version +2.5 against LIVE_CB. His W5 package is CAP35_OWN15 (armed, integration 2c8dd0f6).
- **Hindsight on W1–4 (the same weeks that showed the problem; NOT evidence):** a cap at the field's ownership + 10 would have
  moved the real edge by +0.2 / +6.3 / +3.6 / +6.5 per lineup, + 15 by +0.1 / +5.2 / +1.3 / +5.2 (the decomposition script,
  `reports/lab-handoffs/2026-10-09-selection-decomposition/`).
- **The prior:** NO DIFFERENCE between + 10 and + 15.
- **DISCLOSED — THE TUNING (the reviewer's condition 1):** + 10 against + 15 is chosen AFTER study 89 was read, on the same
  36 slates and the same real outcomes; new banks redraw the simulations and the fields, not the outcomes. By our validation
  law this is retrospective tuning on examined slates: **this read cannot by itself justify the change; the out-of-sample
  test is real weeks.** The reviewer suggests a study 38 paper arm (the live package at + 10, production's `own_cap_rows`
  with delta_pts 10) — his choice; it needs its own amendment, smoke and ack (before Sunday's snapshot, or from Week 6).

## 2. Arms (`experiments/s90_own_cap_10.py`)
**Study 89's harness exactly:** its frozen module (`s89_own_cap.py` `92b09345…`, sha-asserted; its `pred_blend`, `own_cap_rows`
and `own_caps` imported, never copied); his live book with the cheap +2 block and production's 15 spares (41 rows), Rev6, the
QB cap 5, the DST cap 6, the overlap limit 4; the ownership prediction = the l20 `blend_pct` rescaled to 800% (89's); DSTs keep
the DST cap; book solves only (j < 26), spares never; infeasible → re-solved without the ownership bans, recorded.
- **LIVE_CB** — the player cap 0.5, no ownership cap (the reference; the book on paper in Week 5).
- **CAP35_OWN15** — the player cap 0.35 + the ownership cap at + 15 points (**his armed W5 package**).
- **CAP35_OWN10** — the player cap 0.35 + the ownership cap at **+ 10 points** (floor(26 × (pred / 100 + 0.10)) rows; the W6
  candidate).
- **CAP35_OWN10_REAL** — + 10 on the REAL Millionaire ownership: **EXPLORATORY ONLY** (an upper bound; it leaks late news).

## 3. The read (the reader `scripts/s90_report.py`)
- 2023–24 only (36 slates; no 2022: the predictions exist for 2023–24); twelve banks read as **two disjoint draws** (A, B) and
  pooled; study 63's frozen statistics (`load`, `mean_contests`, `boot`, `verdict` identical; a test asserts it).
- **DECISION: CAP35_OWN10 − CAP35_OWN15** on P(≥ 1 big seat) per slate, pooled (two-sided 0.95, B 20,000), the guards (gate a
  PASS only), study 63's verdict, and **the two-draw rule for his W6 decision**: NOT NEGATIVE ON BOTH DRAWS iff set A's and set
  B's points are both ≥ 0 AND the pooled expected big seats ratio ≥ 0.80 — information for his decision, no automatic switch.
  **Under no true effect it passes about one time in three** (the two draws share slates and outcomes, so they are positively
  correlated: between one in four and one in two; the reviewer's condition 2). **Guard 1 (the mean entry percentile) is printed
  beside the rule line** (it failed for + 15 against LIVE_CB in study 89; the reviewer's condition 3).
- **THE SECOND READ OF THE ARMED PACKAGE: CAP35_OWN15 − LIVE_CB** on these fresh banks (study 89's +1.2 read once, on 1743–1754),
  printed in study 89's form, with both reads' difference stated in the Addendum.
- CAP35_OWN10 − LIVE_CB; exploratory: CAP35_OWN10_REAL against CAP35_OWN10 and LIVE_CB; secondaries (expected big seats, P(≥ 2),
  l02, projection per row, concentration, deviation from the predicted field).
- Plainly: the slates are the ones studies 78–89 read; under no true effect a version is "not negative" on both draws about one
  time in four; study 84's bank-set finding is why two draws are read.

## 4. What the harness can and cannot say
- **The real-book check of + 10 on W4 BEFORE THE FREEZE** (the reviewer's condition 5; the laptop's outcome-blind W4 package
  check re-run with `--main-own-cap-delta 10`): FP per row against the + 15 book, rows changed, concentration, players over
  their cap, re-solves.
- **Feasibility at + 10 (the reviewer's condition 4):** every unnamed or 0% player gets floor(26 × 0.10) = 2 rows; the census
  reports infeasible / re-solved solves per arm, the cap-rows histograms at + 10 and + 15, the players banned per solve, and the
  VACUITY of the change: CAP35_OWN10's rows shared with CAP35_OWN15 and its dealt-identical share (above 0.80 = a dead change).
- The harness's ownership prediction (the blend) approximates FP's; the field is easier than the real one; the exposure is book
  rows, the real one dealt entries.

## 5. Production
- A switch to + 10 is one arm value (UNION_MAIN_OWN_CAP_DELTA 10) plus the pair rule in check_week_runtime / the arm (today
  (0.35, 15) only) — his decision, for Week 6 at the earliest.

## 6. Smoke, census and integrity
- BLAS threads pinned to 1 (89's driver); bank 1406 only for the smoke: the unit tests, the mechanics smoke, the binding
  census, the full-path smoke (reader exit and line count only).
- **The smoke (DONE; bank 1406; 2023 W3, 2023 W11, 2024 W10; `results_bank1406.jsonl` `f17b0f87…`):** 7 unit tests pass; every arm
  41 rows within its caps, 8 term rows, in the pool; **0 infeasible solves** in every ownership arm (78 of 78); players banned per
  book solve: + 15 7.8 (max 23), **+ 10 13.4 (max 37)**; cap rows at + 10 mostly 2 (152 of ~247 skill players per slate-bank);
  VACUITY: CAP35_OWN10 shares 6.0 of 26 rows with CAP35_OWN15, dealt identical 0.000 (not a dead change); players over 30%:
  LIVE_CB 10.0, + 15 4.3, + 10 2.0; non-DST players 43.3 / 51.7 / 58.0; projection per row vs LIVE_CB: + 15 −2.44, + 10 −3.71;
  the full path: the reader exited 0 (62 lines; 80 with the two-draw path on a copy); only those were read.
- **Code:** nfl2 `production/s90-own-cap-10-20261009` @ `5a1a1c0e` (branched from study 89's frozen branch `2fe958eb`):
  `experiments/s90_own_cap_10.py` `c4be23f9…` (pins s89 `92b09345…`); `scripts/s90_drive.py` `53acf709…`; `scripts/s90_census.py`
  `f85b4b22…`; **`scripts/s90_report.py` (the reader) `62bce622…`** (seed 20261135); `tests/test_s90_own_cap_10.py` `bbba173e…` (7).
