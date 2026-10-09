# Preregistration: study 73, his two QB-stack ideas (a QB + top pass catcher in each top-5 game; fewer QB + 2 rows), in the harness (DRAFT 2026-10-08)

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
- **Decision 1 (TOPG5_QB1) is his literal request:** five lineups, each a QB and his top pass catcher from one of the
  five highest-total games. It does NOT reduce the QB + 2 rows: the cell quotas fix those (12 of 26 in that arm).
- **Decision 2 (QB1HALF) is the quota version, FEWER QB + 2 rows.** Asked whether he wanted it considered too, he said
  "Yes". That direction was never tested.
  - **A correction, disclosed:** the reviewer first told him "fewer QB + 2 rows is study 56's QB2HALF". That was wrong.
    QB2HALF moved quota INTO the QB + 2 cells (study 56 is "fewer QB+1 rows"; Addendum 163: +0.018, NO DIFFERENCE, not
    taken).
  - The laptop caught it and corrected it to him. QB1HALF is its exact mirror.
- **The prior, stated first:**
  - TOPG5_QB1: NO DIFFERENCE or leaning negative (study 43).
  - QB1HALF: NO DIFFERENCE or leaning negative. QB2HALF leaned positive, and the W1–4 satellite finding has QB + 1
    lineups at odds 0.83 [0.74, 0.93] of a top-10% finish against QB + 2.

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
- **TOPG5_QB1 (DECISION 1):** G = 5.
- **QB1HALF (DECISION 2):** LIVE_CB at the cell quotas A1 0.15 / A2 0.07 / B 0.43 / C 0.35.
  - Half of each QB + 2 cell's quota goes to its QB + 1 counterpart with the same bring-back rule (A1 → B, A2 → C), the
    exact mirror of QB2HALF.
  - It is built through study 56's `quotas()` (`s56_fewer_qb1.py` `1a1bbe0b…`, sha-asserted), with the cheap block
    kept. The term block's rows also allocate by the arm's quotas, as production's `--mix-cell-quotas` does.
  - At K 26: A1 4 / A2 2 / B 11 / C 9, so 6 QB + 2 rows of 26 against 12. Production's `mix_shapes.allocate` gives the
    same.
  - Production needs no new code: `union_reselect --mix-cell-quotas A1=0.15,A2=0.07,B=0.43,C=0.35` (the laptop checked
    the parse and the arm's MIX_QUOTAS).
- **EXPLORATORY TOPG3_QB1:** G = 3.
- **DEALING (tonight's lesson from study 72):** the first-built B / C rows take B's and C's earliest dealt positions. The
  census reports each forced row's book position and whether a big contest reads it (Rev6: indices 0–21). The smoke put
  all five at positions 2, 3, 6, 7 and 12, all read by big contests.

## 3. Endpoint and rule (the reader `scripts/s73_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. The names, the seed, the docstring, the secondaries and the forced-solve lines differ.
- **THE READ: 2023–24** (36 slates). Each decision arm − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field
  v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1635–1640, seed 20261118** (scanned clean by the laptop: 18,103 production and 8,134 lab blobs; one hex false
    positive; no result file).
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's), per arm.
- **Multiplicity, disclosed:** two decision arms, each its own read. Under no effect, a false PASS somewhere has roughly
  a 5% chance.
- **One construction change a week:** if both are ENTERABLE, he picks one. The laptop's arm guard allows at most one of
  BRING_BACK_TOP_WR / TOP_GAME_QB1 / MIX_QUOTAS / a non-default TERM_FILE.
- **EXPLORATORY:** TOPG3_QB1 − LIVE_CB; each arm on l02; P(≥ 2); the QB + 2 rows; the top-5 pairs held; the plain
  solves.

## 4. What the harness can and cannot say
- **Path dependence:** the forced rows are built early, so the rest of the book re-draws. The smoke shared 1.7 of 26 rows
  with LIVE_CB. The effect is measured on the whole book.
- **Vacuity:** LIVE_CB already holds 2.7 of the 5 top-game pairs somewhere in the book (the smoke). The census reports
  it.
- **The base is our simulator's mean, not FP's.** The lines are closing lines.

## 5. What a verdict can do (the laptop's cut-off)
- **TOPG5_QB1 ENTERABLE:** a production option (`--mix-top-game-qb1 G`, the outside reviewer's, parity-tested against
  this harness's frozen functions) mirroring §2 exactly; the laptop's review; merged before FRIDAY_HEAD (default OFF);
  Friday's A3 ON run; his choice at Saturday's arming.
- **QB1HALF ENTERABLE:** the existing `--mix-cell-quotas`, wired and rehearsed on Friday's A3; his choice at Saturday's
  arming.
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
- **The second smoke, with QB1HALF** (the same slates; `~/s73-panel/smoke/mech2`):
  - QB1HALF has QB + 2 rows 6 of 26 (cells 4 / 2 / 11 / 9), projection +0.23 per row, rows shared with LIVE_CB 0.3;
  - the other arms are unchanged.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406; first with 3 arms, then with 4): the reader exited 0
  with its 3, then 4, sections. Only the exit code, the line count and the section count were read.
- **The binding census:** to follow.
- **Code:** nfl2 `production/s73-topg-qb1-20261008` @ `ffb5bd0` (QB1HALF added after `b402cdd`):
  - `experiments/s73_topg_qb1.py` `3f76c629…`;
  - `scripts/s73_drive.py` `5bc691db…`;
  - `scripts/s73_census.py` `5972ec13…`;
  - **`scripts/s73_report.py` (the reader) `d402dc6c…`**;
  - `tests/test_s73_topg_qb1.py` `c55acbb2…` (7 tests);
  - unchanged and sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`, `s56_fewer_qb1.py`
    `1a1bbe0b…`, `term_book.py`
    `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `ac10ddf6…`.
