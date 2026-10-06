# Preregistration: study 29, the live ownership term on the winners' mix, at the operator's first-place-only lines (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06**, after the smoke (§2a), before the binding census and any scored bank. The reviewer
froze it and reads first. The laptop acks the census and re-runs the frozen reader.

## 1. Why
- **The live main adds an ownership term:** tilt × predicted ownership, in percentage points, for skill players only,
  with negatives clipped and fractions refused (`union_reselect.own_bonus`; the laptop, 10-06).
  - Week 5: tilt 0.20 on FP's T-70 ownership projection.
  - Live fallback: the LAG file at 0.10.
  - LineStar is retired, so the chain is FP → LAG 0.10 → none.
- **It tilts toward chalk.** L24 found such a term NEUTRAL at shallow lines but −14% tickets at p99.
- **His satellites pay first place only**, where overlapping the field may cost, so the term is tested on his goal.
- **On the winners' mix:** study 28 makes MIX his likely Friday choice.

## 2. Arms (one co-run per slate-bank)
Study 28's MIX unchanged: production's `mix_rows` mechanics; pin-aware weights; caps 11 / 5; head; his Rev2 pins. Only
the objective differs.
- **MIX (reference):** the simulated mean, no term.
- **MIXT (DECISION, vs MIX):** mean + 0.20 × TABPFN_LS predicted ownership %. These are L24's stage-1 walk-forward
  predictions (sha `5c8384d6…`), the vendor-informed predictor nearest FP's projection.
- **MIXL (EXPLORATORY, vs MIX):** mean + 0.10 × the LAG predicted ownership % (study 1b's LAG files): the live fallback.

**Stand-in caveat (the laptop, 10-06):** TABPFN_LS was trained and scored on LineStar's LOCK-time history, so it is
slightly better informed than a T-70 predictor. Any benefit of MIXT is therefore a little OPTIMISTIC as an estimate of
the live FP term. LAG has no such issue.

## 2a. Smoke observations before the freeze (2023 W9, throwaway bank 1406; mechanics; the reader checked by exit code and header count only)
- Caps 11 / 5; k_book 22. Both term arms change the book (identical to MIX: no).
- The dealt cell shares stay near quota:
  - MIXT: A1 .302 / A2 .151 / B .226 / C .321;
  - MIXL: A1 .283 / A2 .151 / B .245 / C .321.
- The dealt entries' predicted-ownership sum (LAG yardstick): MIX 42.0, MIXT 42.8, MIXL 50.7.
- The reader exited 0 with 2 comparison blocks. No design change.

## 3. Panel and plan
- **Slates:** the **36** `k1` slates of 2023–24 with Millionaire ownership and the predictions. No predictions exist
  for 2022, so the panel is two seasons.
- **Banks:** fresh 1427/1428 (scanned 10-06). The census is on 1406.
- **Plan:** his FINAL Rev2 plan (`00c66004…`).
- **Field caveat:** as before; the differences decide.

## 4. Endpoints and decision rule (study 18b's, unchanged)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT − MIX. Bootstrap within season, B 20,000, seed 20261011. Two-sided
  0.95.
- **GUARD 1:** mean finish; the one-sided 0.95 lower bound > −0.015.
- **GUARD 2:** expected big seats ratio ≥ 0.80.
- **Verdicts:** PASS / WORSE / FAIL (guard) / DEAD LEVER / NO DIFFERENCE as in 18b. "At most one negative season" now
  reads over two seasons.
- **Secondaries:** as in study 28, plus the dealt entries' predicted-ownership sum (measured by the LAG predictor for
  every arm, as one common yardstick).

## 5. What a verdict can do
- **MIXT PASS:** the term stays as armed (FP 0.20).
- **WORSE:** a reason to offer the term OFF for Week 5 (`UNION_MAIN_OWN_TILT` unset), a reversible class-S change.
  The operator decides.
- **NO DIFFERENCE:** the term is neither shown to help nor to hurt at his lines. The operator chooses, told plainly that
  it tilts toward chalk.
- **MIXL** is information on the fallback.

## 6. Integrity
- **Code:** nfl2 `production/s29-ownership-term-20261006` @ `2fbeedf`:
  - `experiments/s29_ownership_term.py`, sha256 `07abafc367d7fff2a0ba49ae3c21cbeebfe1523cccf922581c41143b755f7596`;
  - `scripts/s29_drive.py`, `00851984d782b28de96993b08604db78b297de73449a81142bb495a533f418c9`;
  - **`scripts/s29_report.py` (the reader), sha256 `3cd9fc73396414674a20d728f12ec2bc0d1a1da7849708e27a3888b06485ac3e`**;
  - `scripts/s29_census.py`, `de9c1d67cd83fb39ce0b537018348171b9cd1d6391cbc57cff55cd75850636ae`;
  - `tests/test_s29_ownership_term.py`, `725f7f9a895819d048a9a0688c5cff7d7448df20dc3199157283eaa103326364` (5 tests).
- **Order:** this freeze → the binding census → the laptop's ack → the scored run → the confirmatory census → the read
  → the laptop's re-run → LEDGER and Addendum 134.
- **Transfer:** our projections (the live term sits on FP's); no FP ownership history.
