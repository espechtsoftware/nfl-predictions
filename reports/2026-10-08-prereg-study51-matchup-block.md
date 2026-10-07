# Preregistration: study 51, the matchup bonus as the live 8-row capped block, in the harness, with a 2022 go / no-go (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
- **The design came before study 50's read.** It was sent to the laptop at about 08:27 CT and agreed at about 08:33.
  The DRAFT, with every decision-bearing part (arms, endpoint, the Saturday rule, banks, seed), was committed at 08:36
  (`472434c7`; lab `93e0810`), BEFORE study 50's scored run was read (`e123c7f`). Study 51 uses the same slates.
- **Only §6 and the code shas were added at the freeze.** The smoke and the census are outcome-blind.
- The file carries the date of its scheduled run (10-08), the name the code points to. The laptop acks the census,
  scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator (10-07):** "Please try to tackle the 'matchup bonus' one this week". He wants the outside reviewer's
  matchup bonus LIVE in the Week-5 book as a capped block like the prior-top one.
  - He saw the outside reviewer's caution (weak out of sample; it double-counts what FP's pricing already holds).
  - He also saw the path they gave: "a capped block like the prior-top one: a small host option from the reviewer,
    Friday's rehearsal and a study-38 amendment".
- **His decision is at Saturday's arming, after three tests:**
  - (a) the laptop's fixed-book replay of the live Week-5 book with and without the block, on Weeks 2–4 (in-sample);
  - (b) this study: the block in the harness, out of sample on 2023–24, with a 2022 go / no-go;
  - (c) study 38 amendment 6e: the weekly real-field record.
- **The vehicle** is production's term block (`union_reselect --term-block-rows 8`, the prior-top block's code). Its
  file is `scripts/matchup_block_file.py` (`57d80375`, reviewed and approved): every skill player of the frame, with
  pred_own = b_matchup / 0.20. At tilt 0.20 and cap 2.0 the block adds exactly b_matchup.
- **Study 50** tests the whole-book form (every row on the bonus). The block can differ: only 8 rows carry the bonus, and
  the 18 live rows and the spares do not.
- **The prior, stated before any outcome of study 50 or 51:**
  - Study 49's prior-top block read NO DIFFERENCE, leaning negative (−0.017).
  - The bonus is independent of the projection (study 50's census: Spearman +0.004). The whole-book form costs about 1.8
    projected points per row.
  - Eight rows dilute any effect.
  - So NO DIFFERENCE is the likeliest reading.

## 2. Arms (`experiments/s51_matchup_block.py`)
**The build.** On each slate-bank, his live Week-5 book and production's 15 spares are built: 41 rows through one state,
with the winners' mix, mix_fill's round-robin, limit 4, QB cap 5 and caps 13 / 6. Study 48's harness is used throughout
(`s48_winner_like.py` `c22d2811…`, sha-asserted).
- **LIVE** (reference): mix_fill's round-robin on player_mean. Study 48d's 41 rows.
- **MBLOCK8** (the one DECISION): production's term block (`experiments/term_book.py` `62c2306e…`, the block study 49
  tested; study 38's amendment 6 copies it).
  - One state: the 18-row live block first, on the plain objective. Then the 8-row term block, on the objective plus the
    capped term.
  - The term block sits at ranks 2, 5, 9, 12, 15, 18, 22 and 25 (study 46's `block_positions(26, 8)`). Each block is
    interleaved on its own positions' head weights.
  - The 15 spares follow, on the plain objective.

**The term.**
- It is study 50's MATCHUP, b = clip(1.0 × z, 0, 2), imported from `s50_factor_bonuses.py` (`bf4704a0…`, sha-asserted;
  point in time and tested there). It is computed on the same pool, so the term equals study 50's MATCHUP values.
- **The harness analogue of the block file** lists every skill player of the pool with pred_own = b / 0.20.
- **Production's own_bonus, then the cap:**
  - the term is tilt × pred_own where pred_own > 0, then min(·, 2.0);
  - coverage is the share of the pool's skill players projected ≥ 5 who are named in the file. It is 1.0, because every
    skill player is listed;
  - the gate is 0.5. Below it there is no block, as in production's refusal.
- The module asserts the term equals b to 1e-9.

**Production's constraints** (caps 13 / 6, QB 5, limit 4) are asserted on both arms' 41 rows. The census asserts the
block's positions. Each arm is dealt by the head layout.

**Tested** (`tests/test_s51_matchup_block.py`, 5 tests):
- the frozen shas and constants;
- the term is study 50's MATCHUP through own_bonus and the cap (every skill player listed, coverage, the gate, the cap);
- the build calls and the block's positions;
- the census is outcome-blind;
- the reader: its decision, its printed levels (two-sided 0.95; guard one-sided 0.95), the verdicts, the go / no-go and
  the Saturday rule.

## 3. Endpoint and rule (study 18b's, extended; the reader `scripts/s51_report.py`)
- **THE READ: 2023–24** (36 slates).
- **ONE DECISION:** MBLOCK8 − LIVE, P(≥ 1 big seat) per slate on the calibrated field v2.
  - Two-sided 0.95. B 20,000, seed 20261103; slates resampled within season.
  - Banks 1557–1562. The reviewer's unique-blob scan of both repositories precedes the freeze.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdict:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **THE GO / NO-GO: 2022** (17 k1 slates with real Millionaire ownership, the same banks).
  - The point estimate MBLOCK8 − LIVE, with its two-sided 0.95 interval.
  - CONTRADICTED if the point estimate is < 0.
- **EXPLORATORY** (two-sided 0.95): the decision on l02 (the read and 2022); levels, projection, predicted ownership
  (2023–24) and term points per row.

## 4. THE SATURDAY RULE (frozen; what a verdict can do for Week 5's live block)
- **NOT ENTERED** (the block stays on paper through study 38) if ANY of these holds:
  1. WORSE on the 2023–24 read;
  2. CONTRADICTED on 2022;
  3. the read's expected-big-seats ratio is < 0.80. This is his stated tolerance: at most 20% fewer expected big seats.
- **MOOT** on a DEAD LEVER (the block is dealt identically to LIVE on more than 80% of slate-banks).
- **Otherwise ENTERABLE: his decision at Saturday's arming.**
  - On a PASS: the harness supports the block.
  - Otherwise: no harm shown and no gain shown.
- **Why stricter than study 49's rule (WORSE only):** the bonus's weights were picked in-sample on 2026 Weeks 2–4, and
  the bonus is independent of the projection. The 2022 check is the cheap guard against entering an in-sample fit; it
  has been the rule since 46 → 46c.
- **The operator owns the decision.** This rule is the evidence's recommendation, frozen before the read.
- Study 38's weekly real-field line for the live block (amendment 6e: QA0 − NOTERM) continues either way.

## 5. Production parity
- **The block's code:** study 49 showed that `term_book.py` reproduces production's union book with the block, 26 of 26
  positions, on Week 4.
- **The term's formula:** identical. `make_factor_files.py`'s rule is ported verbatim in study 50, and
  `matchup_block_file.py` imports production's approved `paper_factor_file.py` blend.
- **Two disclosed differences, each source consistent with itself:**
  - the population of z: the harness takes the pool's skill players at or above its projection floor; production takes
    the frame's skill players;
  - the points allowed: the harness uses nflverse weekly stats by the DK formula; production reads the warehouse.

## 6. Smoke and integrity
- **The smoke** (2024 W10 and 2022 W6, bank 1406, the full path, code as committed at `93e0810`, clean):
  - both arms built 41 rows within production's constraints;
  - LIVE equals study 48d's (and study 50's) 41 rows and ranks on both slates;
  - the term applied with coverage 1.0 (157 and 120 players termed);
  - MBLOCK8's block sits at ranks 2, 5, 9, 12, 15, 18, 22 and 25;
  - the census and the reader exited 0, and the reader's header names STUDY 51 (tested).
- **The binding census** (outcome-blind; bank 1406; 53/53 (2022: 17; 2023–24: 36), code `93e0810` clean;
  `results/s51/CENSUS_s51_binding.txt` `ca409dd3…`, raw `cd940dd3…`; lab `d7d287e`):

  | | 2023–24 LIVE | 2023–24 MBLOCK8 | 2022 MBLOCK8 |
  |---|---|---|---|
  | projection per row (change) | 128.04 | 127.35 (−0.69) | −0.66 |
  | predicted ownership per row (change) | 78.56% | +0.24 | n/a |
  | book rows shared with LIVE | — | 16.2 of 26 | 16.3 |
  | the block's 8 rows: projection, term points per row | — | 123.24, 8.88 | 127.02, 8.90 |
  | identical to LIVE | — | 0.000 | 0.000 |

  - **The term:** applied on every slate-bank, coverage 1.000. About 119 players termed a slate in 2023–24 (mean where
    termed 0.84, max 2); Spearman with player_mean +0.004.
  - No quota passed to A1. About 50 s per slate-bank for the two arms.
- **Banks:** 1557–1562 and seed 20261103. The reviewer's unique-blob scan of both repositories found them only in study
  51's own files (this prereg's DRAFT, `s51_report.py`, `s51_drive.py`, the tests). That covers every blob up to 5 MB;
  the 8 larger blobs per repository were not searched.
- **Code:** nfl2 `production/s51-matchup-block-20261007` @ `93e0810` (the census at `d7d287e`):
  - `experiments/s51_matchup_block.py`, sha256 `c766a12e4b8f8c0285bb4bf0f2a7c37b57640a1631af25f6a047d25372ed4a15`;
  - `scripts/s51_drive.py`, `5f903bf3de4be2b21520900f61c49da52dab4e59a94e740a1ad0a23058653d0e`;
  - **`scripts/s51_report.py` (the reader), sha256 `2cba71638ed1ba9e0faa64ef1fb629f7a42176adcb674279bd19cdad8295df63`**;
  - `scripts/s51_census.py`, `c49dae77fbd4c09bef0506950fecb6911db93f0b99f8840d3c792610ecd48028`;
  - `tests/test_s51_matchup_block.py`, `caeee4fe50fcea1ca4801d1084727b2a7460a127b954ee4cc6b4f811c68673cb` (5 tests);
  - unchanged, sha-asserted: study 48's `s48_winner_like.py` `c22d2811…`, study 50's `s50_factor_bonuses.py`
    `bf4704a0…`, `term_book.py` `62c2306e…`.

## 7. Order
1. This DRAFT, committed before study 50 is read.
2. The smoke, then the binding census, after the laptop's replay (a) frees the machine.
3. The freeze, with the shas.
4. The laptop's ack and bank scan.
5. The scored run, tonight or Thursday 06:00.
6. The confirmatory census, committed before the read.
7. The read.
8. The laptop's re-run.
9. The LEDGER row and an Addendum, before Saturday's arming.
