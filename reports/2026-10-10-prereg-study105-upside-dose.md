# Preregistration: study 105, the upside build's dose-response — how many lineups on upside buys how many 200+ lineups for how many big wins, in the harness (DRAFT 2026-10-10; FROZEN 2026-10-10; information only, for Week 6)

**Status: FROZEN 2026-10-10 (04:34 CDT)** by the lab reviewer, after the outside reviewer's DRAFT and code, the smoke and the
binding census, before any scored bank. The text changed at the freeze in this status block and §4 (the binding census) only.
The laptop acks. **Information only:** no pick rule and no confirmation study; nothing from this study can be armed in Week 5
(no production switch for an upside objective). The run must end well before the 10:28 arming.
- **Banks 3420–3431** (set A 3420–3425, set B 3426–3431; sims bases 3470–3481, fields 4120–4131), the reader's bootstrap seed
  **20261148**. The laptop's scan was clean: the full set against every used or reserved bank's {b, b + 50, b + 700} (studies 90–104
  included), no results file; the text scans found only the 09-19 evidence files' letter-labelled "bank" fields with
  inactive-player counts and shas in old 08-xx manifests or reports (incidental); this study's own files were not yet pushed
  at the scan.
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run, recorded in `RUN_ENV_s105.txt` committed with the
  confirmatory census. The run starts from lab `7e3877cf` on production/s105-upside-dose-20261010 (results/s105/).

## 1. Why
- Studies 102 and 103 read building **every** lineup on each player's simulated 85th-percentile score (CEIL_ALL) against his
  live book, on four opponent sets. P(best ≥ 200) was higher on all four (+3.2 / +3.2, then +1.9 / +2.8 points). P(≥ 1 big
  seat) was lower on all four, with expected big seats ×0.86 / ×0.88 and guard 1 failing both times. The 8 cheap-block rows
  alone on upside (CEIL_BLOCK8) did not hold (study 103).
- The operator's goal includes "scores over 200 fairly regularly"; his decision rule counts big wins. **This study measures the
  trade between them as a curve**: how much 200+ rate each step of "more lineups on upside" buys, and what it costs in big
  wins. It is a description for a Week-6 decision, not a decision.

## 2. Arms (`experiments/s105_upside_dose.py`)
**Study 102's harness exactly** (its frozen module `s102_ceiling_build.py` `ca7f4399…`, sha-asserted, which pins study 95's;
`run()` = 102's `run()` with listed edits, a test asserts it); every arm his live Week-5 construction (the package + te1 / low1 +
ONECATCH through 93's `lead_rules`, 89's `own_caps`; QB cap 5, overlap 4, the cheap +2 block on 8 rows, the ownership cap + 15,
A1 .30 / A2 .14 / B .28 / C .28). **The arms nest:**
- **LIVE** — every row on each player's simulated mean (the block on the mean + the cheap +2 term).
- **CEIL_ROWS13** — 13 of the 26 book rows on upside: the 8 cheap-block rows on p85 + the cheap term (study 102's
  CEIL_BLOCK8), plus **the first 5 live-block rows in build order** on p85. The live block is solved first in the harness's
  `term_book`, so these are the book solves j = 0–4. The other 13 rows and the spares stay on the mean.
- **CEIL_ROWS18** — the same with the first **10** live-block rows (j = 0–9) on p85: 18 rows on upside.
- **CEIL_ALL** — every row and the spares on p85, the block on p85 + the cheap term (study 102's CEIL_ALL exactly). It anchors the
  curve's end on this draw.
- **p85** — the 85th percentile of the same 20,000 draws whose mean LIVE uses (study 102's).
- **Mechanics of the first-rows switch:** a wrapper beneath every rule tier (entered before 93's `lead_rules`). On a book solve
  with j = len(prev) < n, it sets every player's objective to his p85 for that solve and restores the objective `term_book` set
  afterwards. The row rules, ONECATCH and the ownership cap are unchanged; each re-solve at the same j uses p85 too. Spares and
  the cheap block are untouched by it.
- 102 and 103 already give the 8-row point (CEIL_BLOCK8).

## 3. The read (the reader `scripts/s105_report.py`), all information
- Study 102's reader with listed edits; study 63's statistics; two draws and pooled; two-sided 0.95, B 20,000.
- **Per arm − LIVE, two draws and pooled:**
  - **P(best ≥ 200)** (the operator's 200+);
  - the mean best real lineup points;
  - **P(≥ 1 big seat)**;
  - the expected big seats ratio (guard 2);
  - guard 1 (mean entry percentile, one-sided lower).
- **THE TRADE RATIO per arm:** ΔP(best ≥ 200) / −ΔP(≥ 1 big seat), pooled. It reads as "extra 200+ slates per big-win slate
  given up"; it is printed only when −ΔP(≥ 1 big seat) > 0, else "no big-win cost".
- **The curve** is printed in row order: 0 (LIVE), 8 (102 / 103, quoted, not re-run), 13, 18, 26.
- **No pick, no verdict for arming**; his rule's line is printed as information.
- **Honest limits:** the same 36 slates of 2023–24 as studies 89–104, a fresh opponent and simulation draw; the harness builds
  on simulator means and percentiles, while his book builds on Fantasy Points' projections. A production upside objective would
  need a distribution around FP's projection, a different number.

## 4. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The census shows the dose binding:** per arm, the book solves run on p85 (distinct j: 0 / 5 / 10, and CEIL_ALL every row);
  the rows shared with LIVE; the projection per row on the mean. **CEIL_ALL equals study 102's CEIL_ALL, row for row, on bank
  1406** (`--ref102`).
- **Per-slate fields stay outside the blocks the reader compares across rows** (study 102's smoke lesson).
- **The smoke (DONE in the gap the lab reviewer named after its 6x smoke; bank 1406; 2024 W10, 2023 W11, 2023 W3;
  PYTHONHASHSEED=0; `results_bank1406.jsonl` `155644ba…`; code `2d03ee58`):** 9 unit tests pass; every arm 41 rows within the
  package's caps (9 / 6, QB 5, overlap 4), 8 term rows, in the pool; ONECATCH ruled 42 of 42 B / C book solves, none dropped,
  every arm; **the dose binds as designed:** the first-rows switch put exactly 0 / 5 / 10 / 0 distinct book solves on p85 per
  slate-bank (min = max on every slate-bank; CEIL_ALL's 26 rows on p85 by the objective); p85 − mean 5.77 points per skill
  player; **LIVE and CEIL_ALL identical to study 102's, rows and dealing, on 3 of 3 slate-banks**; the full path: the drive
  exited 0 (2 slates), the reader exited 0 (59 lines; 71 with the two-draw path on a copy, the dose curve printed once); only
  the census, the exit codes, the line counts and one test failure line were read.
  - **Fixed before the freeze (the first unit step, code `789d83b3`):** one test asserted the text "PICK:" absent from the
    reader, which the variable declaration `_PICK: dict` contains; it now asserts the printed PICK line is absent (`c341d94d`).
    No module, reader or census change.
- **The binding census at the freeze** (the lab reviewer's; outcome-blind; bank 1406; 36 slate-banks of 2023-24; PYTHONHASHSEED=0;
  9 tests pass; lab `7e3877cf` on production/s105-upside-dose-20261010: `CENSUS_s105_binding.txt` `bdef1c2f…`,
  `census_mechanics_bank1406.jsonl` `69fb0fc1…`): 0 row-rule / ownership-cap fallbacks in all 4 arms; ONECATCH 504 of 504 in
  every arm; **the dose binds as designed:** 0 / 5 / 10 / 0 distinct book solves on p85 by the first-rows switch per slate-bank
  (min = max; CEIL_ALL's 26 rows on p85 by the objective); **LIVE and CEIL_ALL identical to study 102's, rows and dealing, on
  36 of 36 slate-banks**; p85 − mean 5.68 points per skill player; flex WR / RB per book 15.2 / 10.8 (LIVE), 18.5 / 7.5
  (ROWS13), 19.3 / 6.7 (ROWS18), 22.9 / 3.1 (ALL); rows shared with LIVE 1.06 / 0.94 / 0.69 of 26; projection per row vs LIVE
  +0.00 / −0.05 / −0.24; none dealt identical.
- **Code:** nfl2 `production/s105-upside-dose-20261010` @ `2d03ee58` (off study 102's frozen `969f4d3d`):
  `experiments/s105_upside_dose.py` `21412869…` (pins s102 `ca7f4399…`); `scripts/s105_drive.py` `4d7320a2…`;
  `scripts/s105_census.py` `ffe023c2…`; **`scripts/s105_report.py` (the reader) `a3633451…`** (seed 20261148);
  `tests/test_s105_upside_dose.py` `c341d94d…` (9).
