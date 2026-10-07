# Preregistration: study 53, a soft preference for sub-$4,000 players on the objective, in the harness, with a 2022 go / no-go (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding (support) census (§6), before any scored
bank.
- The design was sent to the laptop at about 10:22 CT, and the DRAFT was committed at 10:25 (`960bcb37`; lab `74c6ed0`).
  Only §6 and the code shas were added at the freeze.
- No other read on these slates was pending.
- The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The outside reviewer's graph finding** (`review/outside-fill-order-20261006` @ `0c727116`, relayed by the laptop at
  the operator's request): within the regulars' own portfolios (351 user-weeks with ≥ 20 lineups; 51,729 lineups; 1,075
  top-1%), the top-1% lineups carried more sub-$4,000 non-DST players than the same user's other lineups: +0.43 sd [+0.36,
  +0.49], positive in Weeks 1–4.
  - The whole field shows the same gradient.
  - Our projection does not separate their winners (0.00 sd).
  - Our live-Week-5-settings books put two such players in 1 row of 26.
- **Their in-sample Week 2–4 replay** (whole book, own-term vehicle), P(≥ 1 big): +2 per such player .000 / .319 /
  .641; +4 .655 / .127 / .160; live .041 / .002 / .434. **Dose-unstable.**
- **History:** Addendum 77 (August) deleted the HARD punt mandate and the p90 punt valuation, with no effect (NOPUNT 26/107
  vs 25). A SOFT preference on the live objective was never tested.
- **The prior, stated before any outcome:** the replay is dose-unstable and in-sample, the preference costs projection,
  and the punt valuation added nothing. NO DIFFERENCE is the likeliest reading.

## 2. Arms (`experiments/s53_cheap_pref.py`)
**The build.** On each slate-bank, his live Week-5 book and production's 15 spares are built: 41 rows through one state,
with the winners' mix, mix_fill's round-robin, limit 4, QB cap 5 and caps 13 / 6. Study 48's harness is used throughout
(`s48_winner_like.py` `c22d2811…`, sha-asserted). Four arms:
- **LIVE** (reference): player_mean, study 48d's 41 rows.
- **CHEAP2** (DECISION 1): player_mean + 2.0 for every non-DST player with a DK salary under $4,000, on every row.
- **CHEAP4** (DECISION 2): + 4.0 likewise.
- **CHEAP4_BLOCK8** (exploratory): the same +4 term as production's 8-row term block (`term_book.py` `62c2306e…`;
  pred_own = 4 / 0.20, tilt 0.20, cap 4.0, inside the union's (0, 5]). The block sits at ranks 2, 5, 9, 12, 15, 18, 22
  and 25. Every skill player is listed (coverage 1.0, gate 0.5).

**The salaries** are the slate frame's DK salaries, pre-lock. At DK's floors, the sub-$4,000 non-DST players are WRs and
TEs. A missing salary never counts.

**Production's constraints** are asserted on every arm's 41 rows. Each arm is dealt by the head layout.

**Tested** (`tests/test_s53_cheap_pref.py`, 5 tests):
- the frozen shas and constants;
- the cheap mask;
- the block term through own_bonus and the cap;
- the builds;
- the census is outcome-blind;
- the reader: its two decisions, its printed levels (0.975; 0.95 for 2022 and exploratory; guard one-sided 0.95), the
  verdicts, the go / no-go and the study rule.

## 3. Endpoint and rule (the reader `scripts/s53_report.py`)
- **THE READ: 2023–24** (36 slates).
- **TWO CO-PRIMARY DECISIONS:** CHEAP2 − LIVE and CHEAP4 − LIVE, each P(≥ 1 big seat) per slate on the calibrated field
  v2.
  - Two-sided 0.975 each (Bonferroni). B 20,000, seed 20261105; slates resampled within season.
  - Banks 1569–1574. The reviewer's unique-blob scan of both repositories precedes the freeze.
- **Guards, per decision** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats
  ratio ≥ 0.80. **The guards gate a PASS only.**
- **Verdict, per decision:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **THE GO / NO-GO: 2022** (17 k1 slates with real Millionaire ownership, the same banks). Per decision, CONTRADICTED if
  the point estimate is < 0.
- **STUDY:** a decision is ADOPTABLE only if it PASSes on 2023–24 AND is not contradicted on 2022. If both are, the
  candidate is CHEAP2, the smaller dose.
- **EXPLORATORY** (two-sided 0.95):
  - CHEAP4_BLOCK8 − LIVE, on the read and 2022;
  - both decisions on l02;
  - levels, projection, salary, predicted ownership (2023–24) and cheap players per row.

## 4. What a verdict can do
- **ADOPTABLE:** a Week-6 candidate for his decision. Week 5's one construction change is the matchup block.
  - Production's vehicle: the whole-book form through the union's ownership-term route, or the block form through the
    term-block slot. The exploratory block arm says which form carries it.
  - Study 38's paper arms (amendment 6f: MIXT_QA0_CHEAP2 / MIXT_QA0_CHEAP4, on FP from Week 5) give the real-field record
    beside it.
- **Otherwise:** the preference stays off, and the paper arms continue as the weekly real-field record.

## 5. Production parity
- The salaries are DK's pre-lock salaries: the frame's in the harness, the T-70 frame's in production. A bonus needs no
  writer and no model.
- The block form is production's term block (study 49's parity).

## 6. Smoke and integrity
- **The smoke** (2024 W10 and 2022 W6, bank 1406, the full path, code as committed at `74c6ed0`, clean):
  - every arm built 41 rows within production's constraints;
  - LIVE equals study 48d's (and study 50's) rows and ranks on both slates;
  - the block sits at ranks 2, 5, 9, 12, 15, 18, 22 and 25;
  - the census and the reader exited 0, and the reader's header names STUDY 53 (tested).
- **The binding (support) census** (outcome-blind; bank 1406; 53/53 (2022: 17; 2023–24: 36), code `74c6ed0` clean;
  `results/s53/CENSUS_s53_binding.txt` `de0b66e6…`, raw `ac38323b…`; lab `bfc7247`):

  | 2023–24 | LIVE | CHEAP2 | CHEAP4 | CHEAP4_BLOCK8 |
  |---|---|---|---|---|
  | sub-$4,000 players per row | 1.10 | 2.31 | 2.96 | 1.79 |
  | book rows with 0 / 1 / 2+ of them (of 26) | 5.5 / 13.1 / 7.4 | 0.1 / 3.0 / 22.9 | 0.0 / 0.2 / 25.8 | 3.7 / 9.0 / 13.3 |
  | projection per row (change) | 128.04 | −1.16 | −3.03 | −0.91 |
  | predicted ownership per row (change) | 78.56% | −4.90 | −9.48 | −3.04 |
  | book rows shared with LIVE | — | 0.3 | 0.0 | 16.2 |
  | identical to LIVE | — | 0.000 | 0.000 | 0.000 |

  - **The pool:** about 88 such players a slate (WR / TE; mean projection 3.7). The block applies on every slate-bank.
    2022 is alike (the pool 140; −1.26 / −3.33 / −1.04).
  - **Disclosed:** the harness's LIVE carries more of these players (1.10 a row) than production's Week-5 book under FP's
    means (2 in 1 row of 26, the outside reviewer's count). The two projections price them differently, and each is
    consistent with itself.
- **Banks:** 1569–1574 and seed 20261105. The reviewer's unique-blob scan of both repositories found them only in study
  53's own records (this prereg's DRAFT, the laptop's HANDOFF entry naming them, `s53_drive.py`, `s53_report.py`, the tests). That covers every blob up to 5 MB; the 8 larger blobs per repository were not searched.
- **Code:** nfl2 `production/s53-cheap-pref-20261007` @ `74c6ed0` (the census at `bfc7247`):
  - `experiments/s53_cheap_pref.py`, sha256 `996fab81c36022d392c568f0c91da92099737bf8527b12baae085808d696e5d6`;
  - `scripts/s53_drive.py`, `9bf5c43ce3b8b48692802383398b30bd47bc124c1521f25e81c0163f99e0e03e`;
  - **`scripts/s53_report.py` (the reader), sha256 `c612025afdb853c269c6aa1b0bc04b2856eebca8b8a7b851581ca3013dd89766`**;
  - `scripts/s53_census.py`, `77236949fb246f765f3898e67565c8bb6c831df82899e5e3e473017968d3ce7c`;
  - `tests/test_s53_cheap_pref.py`, `737f2d268395a5e08b7c348a4daf64bae4931913354422498532e5ff244efcb2` (5 tests);
  - unchanged, sha-asserted: study 48's `s48_winner_like.py` `c22d2811…`, `term_book.py` `62c2306e…`.

## 7. Order
1. This DRAFT.
2. The smoke, then the binding census.
3. The freeze.
4. The laptop's ack and bank scan.
5. The scored run.
6. The confirmatory census, committed before the read.
7. The read.
8. The laptop's re-run.
9. The LEDGER row (after merging study 52's branch) and an Addendum.
