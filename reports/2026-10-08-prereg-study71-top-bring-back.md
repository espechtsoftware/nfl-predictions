# Preregistration: study 71, the bring-back is the opponent's top receiver, in the harness (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08 (17:55 CDT)** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
- The DRAFT was `0a22ffa6`. Nothing in §2–§5 changed at the census; §6 records it.
- **Next:** the laptop's ack (the banks and seed already scanned clean), the run, the confirmatory census before the
  read, the frozen reader, the laptop's re-run and the records.
- **Target:** read tonight. If TOPBB_AB is ENTERABLE, the production flag can be reviewed, merged before FRIDAY_HEAD and
  rehearsed on Friday's A3, for his choice at Saturday's arming (default OFF).

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 evening:** "Why can't we test the study 71 today with, and if it's good, use it this week?" This is
  study list 71: the outside reviewer's design from his W4 concern (row 70).
- **The concern** (the outside reviewer; in-sample, outcome-chosen; `briefings/2026-week-05/2026-10-08-necessary-players-and-the-bring-back.md`):
  - The W4 Millionaire's $500+ lineups paired Stroud with Collins AND Dallas's Lamb.
  - Our books' bring-backs are the cheapest opposing player the solver can fit.
  - A per-player bonus cannot steer WHICH bring-back a QB row takes. Study 70's mechanics probe and the outside
    reviewer's both showed that.
- **The descriptive evidence** (2026 Millionaire W1–4, stacked-QB lineups; W4 chose the idea): the opponent's
  top-salaried WR is the bring-back in 18% of the field, 30% of the top 1% and 33% of the top 0.1%. Our W5-settings books
  do it in 1–4 of 26 rows.
- **The prior, stated first: NOT ENTERABLE is more likely.**
  - Study 70's top-receiver blocks showed no fix (Addendum 168).
  - Rules that cluster rows (studies 54 and 57) lost on P(≥ 1 big).
  - Forcing a stack shape (study 63's QBTE_SHARE) leaned against.

## 2. Arms (`experiments/s71_topbb.py`)
**The book:** on each slate-bank, study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted), with LIVE = 48d's
41 rows: mix_fill rr, QB cap 5, caps 13 / 6, overlap limit 4. It includes the cheap +2 block through study 53's
`block_term` / `term_book` (8 rows at ranks 2, 5, 9, 12, 15, 18, 22, 25), dealt on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).

- **LIVE_CB (the reference):** his live book with the cheap +2 block (the Week-5 trial).
- **THE TOP RECEIVER:** study 70's `top_wr` (`s70_topwr.py` `d622a211…`, sha-asserted): each team's highest-salaried WR
  in the pool (ties: the higher projection, then the id). The pool is the optimizer's: skill players at or above the
  minimum projection, and every DST.
- **THE RULE:** on a solve of a cell that REQUIRES a bring-back (A1: QB + 2 with a bring-back; B: QB + 1 with a
  bring-back, at most 3 from the QB's game), the lineup must hold its QB's opponent's top receiver.
  - It is the pinned optimizer's interaction floor: `nfl2.core.lineup.optimize`'s `interaction_floor_weights` (weight 1
    on every (QB, his opponent's top receiver) pair), floor 1.0. This is the same mechanism as study 63's QBTE_SHARE.
  - A lineup holds one QB, so the floor holds exactly when the chosen QB's opponent's top receiver is in it.
  - It applies to every solve of those cells, book rows and spares alike. The cell is identified by its StackRules
    object, the one `term_book` passes.
  - A solve the rule makes infeasible is re-solved without it, counted and recorded. The smoke found 0 of 72.
  - A QB whose opponent has no WR in the pool has no pair. The census reports that count; the smoke found none.
- **TOPBB_AB (the single DECISION):** LIVE_CB with the rule on A1 and B. Everything else is LIVE_CB's, including the
  cheap block.
- **EXPLORATORY TOPBB_A1:** the rule on A1 only.
- **No lab change and no re-pin.** The live union calls the same pinned `optimize` (union_reselect's mix solve). The
  production flag (`--mix-bring-back-top-wr A1,B`, default off) passes the same pairs on those cells' solves.

## 3. Endpoint and rule (the reader `scripts/s71_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. The names, the seed, the docstring, the decision count, the secondaries and one
  exploratory line (the rule's infeasible solves) differ.
- **THE READ: 2023–24** (36 slates). TOPBB_AB − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1617–1622, seed 20261115** (scanned clean by the laptop: 18,053 production and 8,106 lab blobs; no result
    file). Each slate's value is the mean over its six banks.
- **THE GO / NO-GO: 2022** (study 51's frozen rule): the point estimate of P(≥ 1 big) TOPBB_AB − LIVE_CB on 2022, with
  its two-sided 0.95 interval. CONTRADICTED if the point estimate is < 0.
- **Guards** as in studies 54–70. They gate a PASS only: the mean entry percentile (one-sided 0.95 lower bound above
  −0.015) and the expected-big-seats ratio (≥ 0.80).
- **Verdict:** DEAD LEVER (the dealt book identical to LIVE_CB's on more than 80% of slate-banks) / WORSE / PASS / FAIL
  (guard) / NO DIFFERENCE.
- **THE TRIAL RULE** (study 51's):
  - NOT ENTERED if WORSE, if CONTRADICTED, or if the expected-big-seats ratio is below 0.80;
  - MOOT on a dead lever;
  - otherwise ENTERABLE, his decision.
- **One decision arm:** no multiplicity.
- **EXPLORATORY:** TOPBB_A1 − LIVE_CB; each arm on the l02 field; P(≥ 2 big seats); the rows with the top bring-back
  (all, and of the A1 / B rows); the QB games; the rule's infeasible solves.

## 4. What the harness can and cannot say (disclosed before the census)
- **The base is our simulator's mean, not FP's.** Here that matters less than in study 70: the rule changes WHICH
  bring-back a stacked row takes, not the player values. The projection cost is reported (the smoke: −0.36 points per
  row).
- **The rule changes almost every row.** The smoke shared 0.7 of 26 rows with LIVE_CB. Every A1 / B row changes, and
  the caps and the overlap limit carry the change into the A2 / C rows. So TOPBB_AB is a different book, not a
  different 8-row block.
- **The harness cannot reproduce W4 itself.** The descriptive real-field rates in §1 are W1–4, and W4 chose the idea.
- **The harness's lines are closing lines,** as in every harness study.

## 5. What a verdict can do (the laptop's plan, a hard cut-off)
- **TOPBB_AB ENTERABLE:**
  - the outside reviewer's production flag is ready for the laptop's review by Friday 09:00;
  - every test module that reads the changed files, plus the 73-module money-path set;
  - merged before FRIDAY_HEAD, with the week_env / sunday_build_host / arm wiring, default OFF;
  - Friday's A3 re-run of the T-70 union with the flag ON (rows, fallbacks, the shape check, a vet_replace);
  - his choice at Saturday's arming.
  - vet_replace's house fallback stays lenient (an A1 row is validated WITHOUT the rule), so a Sunday replacement never
    fails because of it.
- **If any step is not clean by Friday evening, or TOPBB_AB is not ENTERABLE:** it waits for W6. Never an untested rule.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s71-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10):
  - every arm is 41 rows within production's constraints, with 8 term rows (the cheap block) and every row in the pool;
  - every QB had an opponent's top receiver (49 of 49);
  - rule solves 72 (TOPBB_AB) / 39 (TOPBB_A1), 0 infeasible.
  - Rows holding the QB's opponent's top receiver: LIVE_CB 3.7 of 26 (3.7 of the 15.0 A1 / B rows), TOPBB_AB 15.0
    (15.0 of 15.0), TOPBB_A1 8.7.
  - Projection per row: 127.86 / 127.50 / 127.70 (cost −0.36 / −0.17).
  - QB games 6.3 / 6.7 / 6.3.
  - Rows shared with LIVE_CB: 0.7 / 1.0.
- **The full-path smoke** (2024 W10 and 2022 W6 scored on bank 1406):
  - the reader exited 0 with its 3 sections and both infeasible-solve lines;
  - only the exit code, the line count and the section count were read.
- **The binding (support) census** (outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code `b512093` clean; lab
  `results/s71/CENSUS_s71_binding.txt` `dfc89127…`, the raw mechanics rows `census_mechanics_bank1406.jsonl` `178b477f…` with no
  outcome field, committed at `8363072`):
  - every arm is 41 rows within production's caps, QB cap and overlap limit, with 8 term rows and every row in the pool;
  - every QB had an opponent's top receiver (52.5 of 52.5 per slate-bank);
  - rule solves 1,272 (TOPBB_AB) / 689 (TOPBB_A1), with 0 infeasible.
  - Rows holding the QB's opponent's top receiver: LIVE_CB 3.4 of 26 (3.4 of the 15.0 A1 / B rows), TOPBB_AB 15.0 (15.0
    of 15.0), TOPBB_A1 8.6.
  - Projection per row: 128.98 / 128.64 / 128.82 (cost −0.34 / −0.15).
  - QB games 6.4 / 6.5 / 6.4.
  - Rows shared with LIVE_CB: 1.5 / 3.7; dealt identical 0.000 (no dead lever).
  - Build time: about 70 s per slate-bank with 16 workers.
  - Disclosed: the census was started a few minutes before this DRAFT's text was committed. It ran on the committed
    code `b512093`, where the design is fixed, and it is outcome-blind.
- **Code:** nfl2 `production/s71-topbb-20261008` @ `b512093`:
  - `experiments/s71_topbb.py` `2d287cf4…`;
  - `scripts/s71_drive.py` `6abda73c…`;
  - `scripts/s71_census.py` `d3a5b577…`;
  - **`scripts/s71_report.py` (the reader) `7a77ce5b…`**;
  - `tests/test_s71_topbb.py` `1babcec4…` (7 tests);
  - unchanged and sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`, `s70_topwr.py`
    `d622a211…`, `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `plan-week5-rev6-s24.json` `ac10ddf6…`.

## 7. Order
1. The code and the smoke. Done.
2. The DRAFT (`0a22ffa6`). Done.
3. The binding census. Done (§6).
4. The freeze. Done (this text).
5. The laptop's ack (the banks and seed already scanned).
6. The run.
7. The confirmatory census before the read.
8. The read.
9. The laptop's re-run.
10. The records.
