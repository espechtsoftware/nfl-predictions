# Preregistration: study 89, a per-player cap at the predicted field ownership + 15 points, and the 35% player cap, in the harness (FROZEN 2026-10-09)

**Status: FROZEN 2026-10-09 (10:55 CDT)** by the reviewer, after the outside reviewer's DRAFT, the smoke and the binding
census (§6), before any scored bank. The text changed at the freeze in this status block and §6 only. The laptop acks.
**Runs BEFORE study 88** (his decision).
- **Banks 1743–1754** (set A 1743–1748, set B 1749–1754), **seed 20261134**. The laptop's scan of both repositories (whole
  repos; 8 larger blobs in each not searched) found no shared draw: this harness seeds sims from slate_seed(bank + 50) and
  fields from slate_seed(bank + 700), so it draws 1793–1804 / 2443–2454; 1743–1750 sit inside studies 81's / 82's sims
  bases as labels only; the l-series matches are timing fields. **The L01 question it raised is closed:** L01's runner
  (nfl2 `dc66bdb0`, `experiments/l01_allboom_maxgame.py` lines 63–65) seeds from slate_seed(bank) and slate_seed(bank + 50)
  with banks 1100–1102 (1100–1102 / 1150–1152), with no + 700 field seed, so it shares no seed with 89. The reader seed
  appears only in 89's own files.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request and what the real weeks show
- **The operator, 10-09 (in the outside reviewer's session; the laptop records it verbatim, HANDOFF `8a5fdf09`):** "WIth that
  info, it seems we are very bad at selecting lineups. Use whatever tools you have to make suggestions of what we need to fix
  immediately. If it is salary rules causing the problems, let's try changing them. Everything can change today because we
  need to get better immediately". Asked, he chose: the per-player cap **50% → 35% live in Week 5** (a reversible trial; the
  50% book kept on paper), **this test before study 88**, and the calibration on FP's Week-4 means.
- **The W1–4 decomposition** (the outside reviewer's, 10-09; our real entries against the other entries of the SAME contests;
  exact: real edge − model edge = Σ_players (our exposure − the field's) × (real − T-70 projection); aggregates only, the script
  in `reports/lab-handoffs/2026-10-09-selection-decomposition/`):

| Week | Model's edge per lineup | Real edge | The market's edge (props) | Players in ≥ 40% of our entries (field) |
|---|---|---|---|---|
| 1 | +1.8 | +2.6 | −0.5 | 1 (1) |
| 2 | +5.0 | −12.7 | −0.6 | 3 (1) |
| 3 | +2.3 | −11.7 | −0.8 | 0 (1) |
| 4 | +10.6 | −4.0 | +8.6 (FP +8.2) | **9 (0)** |

  - **Not the salary rules:** the shortfall sits in WRs priced $5,500+ and the QB (W2 WR −15.3, W4 WR −17.0 per lineup); the
    players under $4,000 were +9.1 in W4 (the cheap TEs).
  - **Where we deviated from the field, the field was right (W2–4):** the players we held 10+ points above the field fell
    short of the market's projection (−5.7 / −2.4 / −0.9 per player, **n = 2 / 10 / 14 players with a market line — small**);
    those we held 5+ below it beat it (+4.2 / +1.0 / +2.7; n = 15 / 19 / 29);
    the slope of (real − market) on our over-exposure: WR −26, QB −15, RB −4, TE +11 points per +100%.
  - **Concentration:** W4 put Lawrence in 60% of our entries (field 17%), P. Washington 62% (27%), G. Wilson 54% (16%); the
    W5-settings book on W4's data has 7 players at the 13-of-26 cap.
  - **Hindsight (the same weeks, NOT evidence; the reason for this test):** a cap at the field's ownership + 15 points would have
    moved the real edge by +0.1 / +5.2 / +1.3 / +5.2 per lineup (W1–4); a flat 35% cap by −0.2 / +4.7 / +0.2 / +5.3.
- **The prior:** study 36 (Addendum 141) read the 35% cap on the winners' mix: NO DIFFERENCE on P(≥ 1 big) (−0.0004), expected
  big seats ×1.068, the mean-finish guard failed (−0.024). No ownership-relative cap was tested before. **Prior: NO
  DIFFERENCE.**

## 2. Arms (`experiments/s89_own_cap.py`)
**The book:** study 87's frozen module (`s87_qb_price_book.py` `85adf47b…`, sha-asserted; the chain s85 / s84 / s81 / s83 / s80 /
s73 / s48 / s53 under it), his live book with the cheap +2 block and production's 15 spares (41 rows), Rev6, the QB cap 5, the
DST cap 6, the overlap limit 4.
- **LIVE_CB** — the reference: production's player cap 0.5 (13 of 26 rows).
- **CAP35** — the player cap 0.35 (9 rows): **W5's new live setting** (a fresh read of study 36's lever on this book).
- **CAP35_OWN15** — CAP35 + **on every BOOK solve (j < 26, build order, any cell; spares never) every SKILL player (QB / RB /
  WR / TE) already in floor(26 × (pred / 100 + 0.15)) book rows is banned** (the W5 candidate). One solve with the bans; an
  infeasible one is re-solved without the ownership bans and recorded once. **DSTs keep production's DST cap** (no prediction).
  - **pred = the l20 sets' `blend_pct`** (the lag model + LineStar; sha-pinned through L24's manifest, `l24_tabpfn_term.py`
    `ca8e0d03…`), **rescaled so the frame's skill players sum to 800%** (8 skill slots).
  - **Why this source (the smoke's finding, before any outcome):** the first smoke used study 29's LAG predictions. They are
    compressed: skill sums about 480–500% against the real 775–790%, the top prediction 16–25% against the real 31–50%,
    correlation 0.69–0.71. Under them every cap fell below 9 rows, so the 35% cap never bound and the ownership arms were the
    same book. `blend_pct` correlates 0.85–0.91 with the real ownership on four checked slates (sums about 85% of the real),
    the closest analogue here of FP's projected ownership; the rescale puts "+15 points" on the real scale.
  - **Caveat, disclosed:** the blend's LineStar component is **likely pre-lock** (our 10-06 revision check found LineStar's
    post-week archived values equal to its final pre-lock values), **not proven per slate** for 2022–24.
  - **The cap is per-player rows ≤ min(9, floor(26 × (pred / 100 + 0.15)))**: the 35% cap and the ownership cap both bind.
    **Skill players only; DSTs keep production's DST cap of 6** (the census prints DST usage per arm).
  - The reviewer's TABPFN_LS stage-1 file (`~/l24-panel/preds_stage1.parquet`) is not on this machine.
- **CAP35_OWN15_REAL** — the same rule on the **REAL Millionaire ownership** (the field's input). **EXPLORATORY ONLY**: an upper
  bound for a perfect ownership projection; it leaks late news; never decision-bearing.
- **Dropped after the first smoke:** OWN15 on the 50% cap (W5 runs at 35%, his decision; under any compressed predictions it is
  the same book as the 35% version).

## 3. The read (the reader `scripts/s89_report.py`)
- **2023–24 only (36 slates):** the pre-lock predictions exist for those seasons; **there is no 2022 check.**
- **Twelve banks read as TWO DISJOINT DRAWS** (set A = 1743–1748, set B = 1749–1754) **and pooled** — the forward rule's two
  reads in one run, in place of the 2022 check.
- Study 63's frozen statistics (`load`, `mean_contests`, `boot`, `verdict` identical; a test asserts it): the pooled ARM −
  LIVE_CB on P(≥ 1 big seat) per slate (two-sided 0.95, B 20,000), the guards (gate a PASS only), study 63's verdict:
  **CAP35 − LIVE_CB**, **CAP35_OWN15 − LIVE_CB** and **CAP35_OWN15 − CAP35** (the ownership cap on top of W5's 35% cap);
  exploratory: CAP35_OWN15_REAL against CAP35 and LIVE_CB.
- **THE TWO-DRAW RULE (printed for his decision, no automatic entry):** NOT NEGATIVE ON BOTH DRAWS iff set A's and set B's point
  estimates are both ≥ 0 AND the pooled expected big seats ratio ≥ 0.80.
- **HIS W5 ARMING RULE (the operator, 10-09, in the laptop's session, verbatim in production HANDOFF: "the independent check is
  whether study 89 shows the 35% cap underperforming 50% on both draws, since that's the real test — not the Weeks 2-4 replay,
  which would pass by construction"):** **DO NOT ARM** the 35% cap iff CAP35 − LIVE_CB's point estimate on P(≥ 1 big seat)
  (2023–24, the calibrated field) is **below 0 on BOTH draw A and draw B**; otherwise **ARM 0.35** with the 50% book on paper.
  The reader prints it as one line (`== W5 ARMING RULE`).
- Secondaries: expected big seats, P(≥ 2), l02, the projection per row, the most-used skill player, players over 30% / 40%,
  the deviation from the predicted field, predicted ownership per row.
- Plainly: this is a harness on 2023–24 with a simulated field drawn from real ownership; it scores books on REAL points; the
  study 84 bank-set finding is why two draws are read.

## 4. What the harness can and cannot say
- **The real-book check of the 35% cap** (the laptop's, outcome-blind, W4 inputs with W5 arming, OFF `a4ab2839`,
  `~/rehearsals/flagcheck-cap035-20261009T152537Z`): FP per row 143.70 → 141.39 (−2.31); 17 of 26 rows change; the most rows
  for one player 13 → 9; players ≥ 40% 7 → 0, ≥ 30% 10 → 14.
- **The real-book check of CAP35_OWN15** needs FP's projected ownership on W4 (the laptop's, before any live use).
- The harness's ownership prediction (the blend, rescaled) approximates FP's; the harness field is easier than the real one; the builder's
  exposure is book ROWS, the real exposure is dealt ENTRIES (the head rows carry more).

## 5. Production
- **The 35% cap is already his W5 decision** (UNION_MAIN_CAP 0.35 in arm_env; the laptop arms it). This study adds a second
  read of it and tests the ownership cap on top.
- **OWN15 live:** a new flag in union_reselect (per skill player rows ≤ floor(K × (FP projected ownership / 100 + 0.15)) on the
  main book), parity against this study's `own_caps` wrapper, the format agreed with the laptop first; only on his decision.

## 6. Smoke, census and integrity
- **The BLAS threads are pinned to 1 in every worker** (the reviewer's request after study 88's load-dependent census
  difference): the driver sets OMP / OPENBLAS / MKL_NUM_THREADS before any import, and each worker asserts it.
- Bank 1406 only: the unit tests, the mechanics smoke (2023 W3, 2023 W11, 2024 W10), the binding census, the full-path smoke
  (reader exit and line count only).
- **The second smoke (the blend; DONE; `~/s89-panel/smoke/results_bank1406.jsonl` `933c5eea…`; code `f7569c41`):**
  - 9 unit tests pass; every arm 41 rows within its caps (13 or 9 / DST 6, QB 5, overlap 4), 8 term rows, in the pool;
  - **0 infeasible solves** in both ownership arms (78 of 78); the rule bans 7.8 players per book solve (max 23);
  - cap rows per skill player (mean count per slate-bank), the blend: 3 rows 99, 4 rows 83, 5 rows 26, 6 rows 18, 7 rows 12,
    8 rows 5, ≥ 9 rows 4 (never binding under the 35% cap); the minimum is 3 rows;
  - VACUITY: skill players above their ownership cap: LIVE_CB 11.0, CAP35 12.7, CAP35_OWN15 0;
  - players over 30% of the book: LIVE_CB 10.0, CAP35 13.7, CAP35_OWN15 4.3, REAL 6.7; over 40%: 7.3 / 0 / 0 / 0;
  - non-DST players: 43.3 / 46.7 / 51.7 / 52.0; the most-used DST 6 rows in every arm;
  - projection per row vs LIVE_CB: CAP35 −1.21, CAP35_OWN15 −2.44, REAL −2.50; rows shared with LIVE_CB 11.0 / 8.7 / 8.0;
    none identical to LIVE_CB or to CAP35;
  - **the full-path smoke** (2024 W10, 2023 W6): the reader exited 0 with 60 lines (one bank) and 75 lines (the two-draw path
    exercised on a copy); only those were read.
- **The first smoke (LAG, before any outcome):** 8 unit tests pass; 0 infeasible solves; the ownership arms banned 11.9
  players per book solve; OWN15 and CAP35_OWN15 the same book (every cap < 9 rows) → the design change in §2.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all **36 slate-banks of 2023–24** (89 reads
  no 2022); code `4d0daa47` clean; 10 tests pass; lab `results/s89/CENSUS_s89_binding.txt` `d41c1320…`, the raw mechanics rows
  `census_mechanics_bank1406.jsonl` `4af7afbf…` with no outcome field, committed at `1154b5cc`):
  - every arm is 41 rows within its caps (LIVE_CB 13 / DST 6; the three 35% arms 9 / DST 6), QB 5, overlap 4, 8 term rows,
    every row in the pool (asserted);
  - **0 of 936 ruled solves infeasible** in both ownership arms; the rule bans 7.4 players per book solve (max 27; REAL 7.9 /
    30);
  - cap rows per skill player (mean count per slate-bank), the blend: 3 rows 95.2, 4 rows 93.4, 5 rows 28.3, 6 rows 16.2,
    7 rows 7.8, 8 rows 4.7, ≥ 9 rows 5.1 (never binding under the 35% cap); the blend predicts > 0 for 246.9 of 250.9 skill
    players (min 170), the top prediction 27.8%;
  - **VACUITY: skill players above their ownership cap: LIVE_CB 11.7, CAP35 12.2, CAP35_OWN15 0.0, REAL 5.2** (on the blend's
    caps);
  - the most-used skill player 13.0 / 9.0 / 9.0 / 9.0 rows; players over 30% of the book 9.9 / 13.3 / 5.4 / 5.7; over 40%
    7.1 / 0 / 0 / 0; non-DST players 42.3 / 44.8 / 50.9 / 51.5; the most-used DST 6 rows in every arm;
  - deviation from the predicted field 5.10 / 4.81 / 4.26 / 4.22; predicted ownership per row 97.3% / 91.9% / 93.4% / 91.6%;
  - projection per row vs LIVE_CB: CAP35 −1.29, CAP35_OWN15 −2.59, REAL −2.76; rows shared with LIVE_CB 11.1 / 7.9 / 7.3;
    **none dealt identical** to LIVE_CB or to CAP35 on any slate-bank (no dead arm);
  - all three match the smoke's pattern (§6 above) on more slates.
- **Code:** nfl2 `production/s89-own-cap-20261009` @ `4d0daa47` (`f7569c41` + the reader's W5 arming line; branched from study 88's branch `63f6a2e4`):
  - `experiments/s89_own_cap.py` `92b09345…` (pins s87 `85adf47b…`, s29 `07abafc3…`, l24 `ca8e0d03…`);
  - `scripts/s89_drive.py` `ab2ed796…`; `scripts/s89_census.py` `34ee3958…`;
  - **`scripts/s89_report.py` (the reader) `2aa22e70…`** (seed 20261134; + his W5 arming line at `4d0daa47`);
    `tests/test_s89_own_cap.py` `b76b09e7…` (10 tests).
- **The decomposition script** (§1): `reports/lab-handoffs/2026-10-09-selection-decomposition/selection_decomposition.py`.
