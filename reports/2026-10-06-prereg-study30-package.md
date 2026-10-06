# Preregistration: study 30, the Week-5 package against the status quo, on the operator's goal (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06**, after the one-slate smoke (§2a), before the binding census and any scored bank. The
reviewer froze it and reads first. The laptop acks the census (it may object to the design there) and re-runs the
frozen reader.

## 1. Why
- **Studies 28 and 29 each changed ONE stage:** the shape (MIX vs house, no term) and the term (on MIX).
- **The post-selection law:** a verdict does not transfer across a changed downstream stage. The recommended package
  (MIX, no term) is untested as a whole against what was entered in Week 4 (the house shape + the 0.20 term).
- **This study compares the two complete constructions directly.**

## 2. Arms (study 29's harness, unchanged)
- **SQ (reference), the status quo:** `PRODUCTION_STACK` on every row, plus 0.20 × TABPFN_LS predicted ownership %.
  This is the live term's stand-in; skill players only.
- **PKG (DECISION, vs SQ), the package:** study 18's MIX built as production's `mix_rows` (pin-aware weights), with NO
  ownership term.

Common: our simulated means (FP is not in history; the live package adds FP); caps 11 / 5; head; his Rev2 pins.

## 2a. Smoke (2023 W9, bank 1406; mechanics; the reader checked by exit code and header count only)
- Caps 11 / 5; k_book 22. PKG is not identical to SQ.
- PKG's dealt cells: A1 .302 / A2 .151 / B .245 / C .302, with 0 passes.
- Predicted-ownership sum (LAG yardstick): SQ 46.2, PKG 42.0.
- Top-player entry share: SQ .79, PKG .70.
- The reader exited 0.

## 3. Panel and plan
- **Slates:** the **36** `k1` slates of 2023–24 (the predictions exist only there).
- **Banks:** fresh **1429/1430** (scanned 10-06). The census is on 1406.
- **Plan:** his FINAL Rev2 plan (`00c66004…`).

## 4. Endpoints and decision rule (study 18b's)
- **PRIMARY:** P(≥ 1 big seat) per slate, PKG − SQ. Bootstrap within season, B 20,000, seed 20261012. Two-sided 0.95.
- **GUARD 1:** mean finish; the one-sided 0.95 lower bound > −0.015.
- **GUARD 2:** expected big seats ratio ≥ 0.80.
- **Verdicts:** PASS / WORSE / FAIL (guard) / DEAD LEVER / NO DIFFERENCE.
- **Binding-census checks:** PKG's dealt cells within 10 points of the quotas; no short books; PKG never identical to SQ.

## 5. What a verdict can do
- **PASS:** the package is a tested gain over the status quo on his goal. Arm it Friday on his yes.
- **NO DIFFERENCE:** the package rests on studies 28 and 29 (each NO DIFFERENCE, each pointing the same way), offered as
  his preference.
- **WORSE:** the package is not offered as a whole. The status quo stays, and the reasons are examined.

## 6. Integrity
- **Code:** nfl2 `production/s30-package-vs-status-quo-20261006` @ `6d879e9`:
  - `experiments/s30_package.py`, sha256 `6a6e3635c12f97a555cb0f6cfa6c4c99e46656f1cf453d437c86f3f07969221a`;
  - `scripts/s30_drive.py`, `680f5fc8e6481c4844668331fd347540de103a2d88836fd67caeafbf135c520c`;
  - **`scripts/s30_report.py` (the reader), sha256 `2410852812c747fbad1e5e6a10d138d8fc56c58eeb528865a85eda309b0eb8d5`**;
  - `scripts/s30_census.py`, `fc07ed876a558894f7c97befe42a2295b91dde7825c3ad08924a45498e206614`;
  - `tests/test_s30_package.py`, `05ea3e35c6588548ba4c37926cf4ad4bcbd4ebd60e29d9afecf27628df0c9d3f` (4 tests).
- **Order:** this freeze → the binding census → the laptop's ack → the scored run → the confirmatory census → the read
  → the laptop's re-run → LEDGER and Addendum 135.
- **Transfer:** our projections; the term's predictor is a stand-in; the live package adds FP.
