# Preregistration: study 73, one QB + top pass-catcher lineup for each of the top-5 games, in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08** by the reviewer, written after the code's smoke and before the binding census and any
scored bank.
- **Next:** the binding census (§6), the freeze, the laptop's ack (the banks and seed already scanned clean), the run,
  the confirmatory census before the read, the frozen reader, the laptop's re-run and the records.
- **Target:** read tonight. If TOPG5_QB1 is ENTERABLE, a production option can be reviewed, merged before FRIDAY_HEAD and
  rehearsed on Friday's A3, for his choice at Saturday's arming (default OFF).

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "In my opinion, the two pass catchers from the same team that we're doing in so many of
  our lineups seems like too much. Have we tried something like for each of the five highest projected games doing
  requiring the quarterback and his top pass catcher". Offered W6 or tonight, he chose "Test tonight for Week 5".
- **What he was shown first:**
  - 12 of 26 rows are QB + 2 (cells A1 / A2), matching the W1–4 top 1% (44% QB + 2 or more).
  - Study 43 (Addendum 147: an A1 stack in each top-4 game) was −2.8, both seasons negative.
  - Studies 15 and 56 were NO DIFFERENCE.
- **This study is his literal request:** five lineups, each a QB and his top pass catcher from one of the five
  highest-total games.
  - It does NOT reduce the QB + 2 rows: the cell quotas fix those, and the census shows 12 of 26 in every arm.
  - Fewer QB + 2 rows is the quota question, study 56's QB2HALF: NO DIFFERENCE, and on paper in W5.
- **The prior, stated first: NO DIFFERENCE or leaning negative** (study 43).

## 2. Arms (`experiments/s73_topg_qb1.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted). LIVE = 48d's 41 rows with the cheap +2
block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json` `ac10ddf6…`).

- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE GAMES:** game_total descending, then game_id ascending, over the games with a QB in the pool. The top G are the
  first G.
- **THE QB of a game:** the side with the higher team implied total (ties: the higher top-QB projection, then the team),
  and that side's highest-projected QB (ties: the id).
- **HIS TOP PASS CATCHER:** the highest-projected WR or TE of that team in the pool (ties: the higher salary, then the id).
  "Projection" is the build's objective base (player_mean).
- **THE ROWS:** the first G BOOK solves of the QB + 1 cells (B and C: `qb_stack_min` 1, `qb_stack_max` 1), in BUILD
  ORDER. The k-th carries game k's pair as the pinned optimizer's interaction floor ({(QB_k, PC_k): 1.0}, floor 1.0;
  study 71's mechanism).
  - The QB + 1 shape means the QB's one stacked pass catcher IS PC_k. The bring-back is the cell's (B one, C none).
  - "Book" means j < K_book. Spares are never forced.
  - Each designated book solve, while games remain, consumes the next game. An infeasible floored solve is re-solved
    plain, recorded, and that game is dropped (not retried).
- **TOPG5_QB1 (the single DECISION):** G = 5.
- **EXPLORATORY TOPG3_QB1:** G = 3.
- **DEALING (tonight's lesson from study 72):** the first-built B / C rows take B's and C's earliest dealt positions. The
  census reports each forced row's book position and whether a big contest reads it (Rev6: indices 0–21). The smoke put
  all five at positions 2, 3, 6, 7 and 12, all read by big contests.

## 3. Endpoint and rule (the reader `scripts/s73_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. The names, the seed, the docstring, the secondaries and the forced-solve lines differ.
- **THE READ: 2023–24** (36 slates). TOPG5_QB1 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1635–1640, seed 20261118** (scanned clean by the laptop: 18,103 production and 8,134 lab blobs; one hex false
    positive; no result file).
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's), with one decision arm and no multiplicity.
- **EXPLORATORY:** TOPG3_QB1 − LIVE_CB; each arm on l02; P(≥ 2); the QB + 2 rows; the top-5 pairs held; the plain
  solves.

## 4. What the harness can and cannot say
- **Path dependence:** the forced rows are built early, so the rest of the book re-draws. The smoke shared 1.7 of 26 rows
  with LIVE_CB. The effect is measured on the whole book.
- **Vacuity:** LIVE_CB already holds 2.7 of the 5 top-game pairs somewhere in the book (the smoke). The census reports
  it.
- **The base is our simulator's mean, not FP's.** The lines are closing lines.

## 5. What a verdict can do (the laptop's cut-off)
- **TOPG5_QB1 ENTERABLE:** a production option mirroring §2 exactly; the laptop's review; merged before FRIDAY_HEAD
  (default OFF); Friday's A3 ON run; his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s73-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - 5 of 5 (TOPG5) and 3 of 3 (TOPG3) forced, with 0 infeasible;
  - forced rows at book positions 2, 3, 6, 7, 12, all read by big contests;
  - QB + 2 rows 12.0 of 26 in every arm;
  - top-5 pairs held: LIVE_CB 2.7, TOPG5 5.0;
  - projection cost −0.17 / −0.13 per row;
  - rows shared with LIVE_CB 1.7 / 1.3.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with its 3 sections. Only the exit
  code, the line count and the section count were read.
- **The binding census:** to follow.
- **Code:** nfl2 `production/s73-topg-qb1-20261008` @ `b402cdd`:
  - `experiments/s73_topg_qb1.py` `d1a9dea0…`;
  - `scripts/s73_drive.py` `5bc691db…`;
  - `scripts/s73_census.py` `a9632672…`;
  - **`scripts/s73_report.py` (the reader) `3bfc0428…`**;
  - `tests/test_s73_topg_qb1.py` `7174830e…` (7 tests);
  - unchanged and sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`, `term_book.py`
    `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `ac10ddf6…`.
