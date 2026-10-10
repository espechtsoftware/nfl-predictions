# Preregistration: study 98, study 95's suggested shape mix against his live mix, on a fresh draw of the same slates (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09** (the times are this file's commits) by the outside reviewer; code and smoke done (§4). The lab reviewer reviews, runs the binding census and FREEZES; the laptop acks. **Information for his morning
decision.**
- **Banks and seed (the laptop scans):** **3136–3147** (set A 3136–3141, set B 3142–3147; sims bases 3186–3197, fields 3836–3847),
  seed 20261143.

## 1. Why
- **Study 95** (READ `976a7558`, lab `8735c6de`; reproduced byte for byte by the laptop): no arm passed his rule; removing A1, B or
  C was worse on both draws; removing A2 changed nothing. **Its translation rule, fixed before the run** (production
  review/s95-prereg-20261009 @ `92108ea0`), gives the **suggested mix A1 39.1% / A2 12.2% / B 24.3% / C 24.3%** (A1 × 1.5, the rest
  kept, re-scaled; the book's rows 10 / 3 / 7 / 6 against today's 8 / 4 / 7 / 7). **The mix itself was never built in 95.**
- **The laptop's proposal (10-09 evening):** read the suggested mix against the live mix before the morning.
- **Honesty, plainly (the lab reviewer's wording):** fresh banks re-use the SAME 36 slates' real outcomes; this checks robustness
  to the opponent and simulation draw (the kind of flip that turned study 81's +4.7 into study 84's −1.2), **not new outcomes —
  not out-of-sample.** The mix was derived from study 95's read of these slates, so a pass is still weak support.
- **The prior:** NO DIFFERENCE (studies 18 / 28 / 56: no shape mix has beaten another on both draws).

## 2. Arms (`experiments/s98_suggested_mix.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with three
listed edits, a test asserts it); both arms his live Week-5 construction (the package + te1 / low1 + ONECATCH through 93's
`lead_rules`), at their quotas through 95's `quotas()`:
- **LIVE** — 0.30 / 0.14 / 0.28 / 0.28 (identical to study 95's LIVE; the census compares the rows on bank 1406).
- **SUGGESTED** — (0.45, 0.14, 0.28, 0.28) / 1.15, the floats production arms through MIX_QUOTAS; rows 10 / 3 / 7 / 6 of 26 (the live
  block 7 / 2 / 5 / 4, the cheap block 3 / 1 / 2 / 2; a test asserts them).

## 3. The read (the reader `scripts/s98_report.py`)
- Study 95's statistics (63's, a test asserts them); two draws and pooled; two-sided 0.95, B 20,000; the guards gate a PASS only.
- **SUGGESTED − LIVE** on P(≥ 1 big seat) per slate; **his rule printed**: better on both draws AND the pooled expected big seats
  ratio ≥ 0.80 — a candidate; **otherwise "keep the live mix"** (the laptop's framing). Under no true effect it passes about one
  time in four to one in three.

## 4. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census with `--ref95`, the full path: reader exit and line count only).
- **The smoke (DONE in the gap after study 97's run; bank 1406; 2023 W3, 2023 W11, 2024 W10; PYTHONHASHSEED=0;
  `results_bank1406.jsonl` `c917a5af…`; code `ac7dd400`):** 7 unit tests pass; both arms 41 rows within the armed caps, 8 term rows,
  in the pool; 0 row-rule and ownership-cap fallbacks (78 of 78 each); ONECATCH ruled on every B / C book solve, none dropped (LIVE
  42, SUGGESTED 39: one fewer C row per slate-bank); **the book rows A1 / A2 / B / C: LIVE 8 / 4 / 7 / 7, SUGGESTED 10 / 3 / 7 / 6**;
  rows shared with LIVE 12.33 of 26, dealt identical 0.000; projection per row vs LIVE −0.05; **LIVE identical to study 95's LIVE
  (the outside reviewer's 95 smoke) on 3 of 3 slate-banks**; the full path: the reader exited 0 (24 lines; 28 with the two-draw
  path on a copy); only the census, the exit codes and the line counts were read.
- **Code:** nfl2 `production/s98-suggested-mix-20261009` @ `ac7dd400` (branched from study 95's READ `8735c6de`):
  `experiments/s98_suggested_mix.py` `328c1255…` (pins s95 `46b80611…`); `scripts/s98_drive.py` `aaf3fd31…`; `scripts/s98_census.py`
  `0bc611ba…`; **`scripts/s98_report.py` (the reader) `60d01b13…`** (seed 20261143); `tests/test_s98_suggested_mix.py` `8e3b1d63…` (7).
