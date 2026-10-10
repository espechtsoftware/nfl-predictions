# Preregistration: study 105, the upside build's dose-response — how many lineups on upside buys how many 200+ lineups for how many big wins, in the harness (DRAFT 2026-10-10, information only, for Week 6)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the laptop's proposal, agreed by the
lab reviewer as **information only**. The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop
acks and reproduces. **No pick rule and no confirmation study:** there is no production switch for an upside objective, so
nothing from this study can be armed in Week 5. The run must end well before the 10:28 arming.
- **Banks and seed (the laptop's full-set check: CLEAN against every used or reserved bank, studies 90–104; text scan to
  follow):** **3420–3431** (set A 3420–3425, set B 3426–3431; sims bases 3470–3481, fields 4120–4131); the reader's bootstrap
  seed **20261148**.

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
- **The smoke:** (a machine gap the lab reviewer names; filled in when it ends).
- **Code:** (filled in when written).
