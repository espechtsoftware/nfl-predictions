# Preregistration: study 46c, the half-and-half book on the 2022 slates — the out-of-sample check (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§5), before any 2022 outcome of
this question was computed. The laptop acks the census, checks the banks and re-runs the frozen reader.

## 1. Why
- **Study 46** (Addendum 149) read MIXT_HALF against MIXT_LIVE on the 36 2023–24 slates. The rule calls it NO
  DIFFERENCE, but it leans positive in both seasons: P(≥ 1 big seat) +0.0317 [−0.0063, +0.0687], expected big seats
  +6%, mean finish about 1 point lower.
- **His decision (10-06, through the laptop): "Yes, pending 2022 check".** This study is that check (§3). The
  laptop's real-field replay of Weeks 2–4 at `--mix-rs-rows 13` is already in: P(≥ 1 big) was higher in all three
  weeks, and the mean finish was level.
- **The 2022 slates.** The 17 2022 k1 slates with real Millionaire ownership have not been read by studies 37–46. Their
  2023–24 panel exists because the ownership-PREDICTION arms need it, and study 46's arms use no ownership prediction.
- **Disclosed:** this check was proposed AFTER study 46's read, as a confirmation. It does not change study 46's
  verdict. Its own rule is below.
- **The prior, stated before any 2022 outcome:**
  - 17 slates give an interval about 1.5 times as wide as study 46's. Even if the effect is the +0.03 study 46 saw, NO
    DIFFERENCE is the likeliest reading.
  - The information is the direction and the size, and the 53-slate pool.

## 2. Arms, rules and fields: study 46's, unchanged
- **The experiment.** `experiments/s46c_half_half_2022.py` IS study 46's frozen experiment (`s46_half_half.py`
  `30647fef…`, imported, its sha asserted). The only change is that the season guard is opened to 2022 for the call and
  restored afterwards.
- **Unchanged from study 46:** MIXT_LIVE (reference), MIXT_HALF (DECISION), MIXT_THIRD and MIXT_TWOTHIRDS
  (exploratory), the tiers, THE RULES 1–6, the calibrated field v2 (decision) and l02, one seed per slate-bank.
- **The census and the reader are study 46's, unchanged.** That is `scripts/s46_census.py` `bcb89647…`, and the reader
  `scripts/s46_report.py` `8fb926b1…`.

## 3. Endpoint and rule
- **PRIMARY:** P(≥ 1 big seat) per slate on the v2 field, MIXT_HALF − MIXT_LIVE, on the 17 2022 slates.
  - The rule is study 46's frozen reader and verdicts: DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE,
    two-sided 0.95, with the guards gating a PASS only.
  - Banks 1509–1514 on the 2022 slates. They were never computed: a bank seeds each slate's simulation, and study 46
    ran them on 2023–24 only. The scan for these numbers (production nothing; the lab only study 46's own lines) stands.
  - B 20,000, seed 20261026 (the reader's).
- **THE GO / NO-GO for Week 5** (the operator, 10-06, on study 46's half book: "Yes, pending 2022 check"; frozen here,
  before the read):
  - **CONTRADICTS** if the 2022 read is WORSE at the frozen rule, OR the 2022 point estimate of MIXT_HALF − MIXT_LIVE
    (P(≥ 1 big seat) on v2) is below 0. Then the half book does not go into Week 5 (`MIX_RS` stays 0), and the reviewer
    recommends against it.
  - **DOES NOT CONTRADICT** in every other case. Then `MIX_RS=13` goes in, with study 38's amendment 5, the arm script
    and Friday's rehearsal at 13.
  - A PASS on 2022 alone is reported as such.
  - For reference: if the true effect is study 46's +0.03, a negative 2022 estimate happens about 1 time in 7. If there
    is no effect, it happens 1 time in 2.
- **EXPLORATORY: the 53-slate pool** (2022 + 2023–24, banks 1509–1514). This is the same frozen reader on the per-bank
  files concatenated, with slates resampled within season. Because it includes study 46's 36 slates, it is not a
  fresh test.

## 4. What a reading can do
- **His Week-5 decision is already made, conditional on this read** (above): it is the go / no-go.
- Beside it stand study 46 and the laptop's Weeks 2–4 real-field replay at 13. That replay found P(≥ 1 big) higher in
  all three weeks (.083 / .010 / .530 against .041 / .002 / .434) and the mean finish level (48.8 against 48.4).

## 5. Smoke and integrity
- **The smoke** (2022 W1, bank 1406, the full path):
  - every arm built 40 rows (26 book + 14 spares) within the limit 4, the QB cap 5, the player cap 13 and the DST cap 6;
  - no relaxations, passes or drops;
  - the blocks sat at the formula's positions;
  - study 46's census and reader exited 0; the reader printed its 2 headers;
  - about 87 s per slate-bank.
- **The binding census** (outcome-blind; bank 1406; 17/17, code `048235e` clean; `results/s46c/CENSUS_s46c_binding.txt`
  `1b0a627d…`, raw `24bd228b…`). It shows the same mechanics as study 46's 2023–24 census:
  - HALF has 10.18 QBs against 7.53, and 42.7 distinct players against 33.2;
  - 5.24 players sit over 40% of rows, against 7.06;
  - the live rows project 134.39 and the RS rows 128.81 per row (the live book: 132.27);
  - the projection cost is −0.71 per dealt lineup (THIRD −0.53, TWOTHIRDS −0.72);
  - there were no relaxed rows, passes, drops or short books, and no arm is identical to its reference.
- **Code:** nfl2 `production/s46c-half-half-2022-20261006` @ `048235e` (the census at `c4dd082`):
  - `experiments/s46c_half_half_2022.py`, sha256 `ea552c46bef2e9c99573acd37331493d53ffbc4f7f74105f58969bf5e3613e49`;
  - `scripts/s46c_drive.py`, `abc38b30ab643d1cab53a9b1ec419fc851d0c3f7e4482fadca97e8b339578e64`;
  - `tests/test_s46c_half_half_2022.py`, `25a60c888a93cdc0f4367d752b254af8200c0037b1bb090846c1c0b63266c170` (3 tests);
  - study 46's, unchanged:
    - `experiments/s46_half_half.py` `30647fef4175770e8f809cb704f282788f8b4d079319ba282768ad907433ec7a`;
    - **the reader `scripts/s46_report.py` `8fb926b198bff9fb8c7775e78f8863bb82f61bcf744677a163809fd843249b50`**;
    - `scripts/s46_census.py` `bcb8964766bc7500d562a5f09216519861ec41e7cb1e7ea280dc5f526f167637`.
- **The reads, both with the frozen reader:**
  - the PRIMARY reads `--dir <2022 run> --banks 1509,…,1514`;
  - the 53-slate pool reads a directory whose per-bank files are study 46's run files followed by this run's.
- **Order:** this freeze → the laptop's ack (the census re-run) → the scored run → the confirmatory census, committed
  before the read → the read and the pool → the laptop's re-run → the LEDGER row and an Addendum, and the go / no-go
  to him.
