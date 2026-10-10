# Preregistration: study 100, the ceiling sweep — five morning-armable variations of his live book, read on the book's best real lineup, in the harness (DRAFT 2026-10-09; FROZEN 2026-10-10)

**Status: FROZEN 2026-10-10 (00:40 CDT)** by the reviewer, after the outside reviewer's DRAFT, the smoke and the binding census,
before any scored bank. The text changed at the freeze in this status block and §5 (the binding census) only. The laptop acks.
**Information for his morning decision; a pick goes to study 101 (its preregistration committed before this READ).**
- **Banks 3260–3271** (set A 3260–3265, set B 3266–3271; sims bases 3310–3321, fields 3960–3971), **seed 20261144**. The laptop's scan was clean: the full set against every used bank's {b, b + 50, b + 700} (studies 90–99 included), no season
  years, no results file; the repository text scans found only this study's and study 101's own preregs, shas and timings.
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run (O-63), recorded in `RUN_ENV_s100.txt` committed with
  the confirmatory census.

## 1. Why
- **The operator, 10-09 evening, in the laptop's session (HANDOFF `f68ebf50`, verbatim):** "...if you're not seeing really good
  scores when you run your mix, keep trying different variations of it. You know, my hope is that we can get to a point where
  you're, you're seeing scores, you know, over 200 fairly regularly. So do what you can."
- **The context (HANDOFF `3ac3bfd7`):** in his real Week 2–4 fields 200 is a top-0.1–0.25% score; his live book's best lineup
  reaches it on about 13% of harness slate-banks (study 95's LIVE); no arm read so far moved that by more than about +0.03 (one
  +0.08, not repeated).
- **The design (the lab reviewer's final call, reconciled with the outside reviewer's draft):** the laptop's list of
  morning-armable switches, one setting changed per arm, read on the book's CEILING.
- **The prior:** NO DIFFERENCE (studies 90 for + 10; the QB-cap, overlap and cheap-block studies of 10-06 to 10-08; study 56 for
  the cell quotas).

## 2. Arms (`experiments/s100_ceiling.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with eight
listed edits, a test asserts it); every arm his live Week-5 construction (the package + te1 / low1 + ONECATCH through 93's
`lead_rules`, 89's `own_caps`), **one setting changed** (a test asserts exactly one):
- **LIVE** — QB cap 5, overlap 4, the cheap +2 block (8 rows), the ownership cap + 15, A1 .30 / A2 .14 / B .28 / C .28.
- **QBCAP3** — the QB cap at 3 rows.
- **OVERLAP3** — at most 3 players shared between any two rows.
- **NOCHEAP** — no cheap +2 block (study 42's live fill over 26 rows, `mix_fill.mix_book_fill`, the same patched builder).
- **OWN10** — the ownership cap at + 10 (study 90's).
- **BBHEAVY** — each no-bring-back cell halved into its bring-back twin: A1 .37 / A2 .07 / B .42 / C .14. **Book rows 10 / 2 /
  11 / 3** (each block is allocated at its own size, as the live book: the 18 live rows 7 / 1 / 8 / 2, the 8 cheap-block rows
  3 / 1 / 3 / 1). **Correction before the freeze (the smoke's census):** this file first said 9 / 2 / 11 / 4, the allocation
  over 26 rows at once, which the book never uses; the quotas, the code and the design are unchanged.

## 3. The read (the reader `scripts/s100_report.py`)
- Study 95's statistics (63's, a test asserts them); two draws and pooled; two-sided 0.95, B 20,000.
- **THE PICK STATISTIC:** the mean, per slate, of the **book's best real lineup points** (the max of its 26 rows' real DK points),
  each arm − LIVE, pooled with its interval and on both draws. **P(best ≥ 200)** is printed beside it with both draws (the
  operator's "200+"; a 13% base rate, so the continuous statistic has far more power). P(≥ 1 big seat), its guards and verdict
  as before.
- **THE PICK RULE (pre-stated; a tested function `pick_rule`):** among the five arms, the **largest pooled gain in mean best
  points** that is ALSO **> 0 on both draws** (mean best points), AND **P(≥ 1 big seat) not worse on both draws**, AND the pooled
  **seats ratio ≥ 0.80**. None → **"keep the live book"**.
- **MULTIPLICITY, plainly:** five arms on the same 36 slates as studies 89–99; about one to two pass by chance. A pick is a
  candidate for study 101, never proof.

## 4. What the harness can and cannot say
- The census reports per arm: the book rows per cell, the distinct QBs and the most rows on one QB (cap 3 or 5), the most
  players shared by two rows (limit 3 or 4), the cheap-block rows (0 or 8), the re-solves, ONECATCH's ruled / dropped, the
  vacuity vs LIVE.
- The transfer caveat: the harness builds on simulator means; his book on Fantasy Points' projections.
- Every arm is one existing switch: QB cap / overlap / term block / ownership-cap delta / MIX_QUOTAS.

## 5. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The smoke (DONE in the gap the lab reviewer named, after study 99's run; bank 1406; 2023 W3, 2023 W11, 2024 W10;
  PYTHONHASHSEED=0; `results_bank1406.jsonl` `fb522637…`; code `635b64eb`):** 8 unit tests pass; every arm 41 rows within the
  package's caps (9 / 6, QB 5 — QBCAP3 3 — overlap 4 — OVERLAP3 3), in the pool; the cheap-block rows 8 (NOCHEAP 0); 0 row-rule
  and 0 ownership-cap fallbacks (78 of 78 each); ONECATCH ruled 42 of 42 B / C book solves, none dropped, every arm; the most
  rows on one QB 5.0 (QBCAP3 3.0), the most shared 4.0 (OVERLAP3 3.0); book rows LIVE 8 / 4 / 7 / 7, BBHEAVY 10 / 2 / 11 / 3;
  rows shared with LIVE QBCAP3 9.00, OVERLAP3 1.67, NOCHEAP 15.67, OWN10 7.33, BBHEAVY 4.67 of 26 (dealt identical 0.000
  each); projection per row vs LIVE QBCAP3 −0.45, OVERLAP3 +0.01, NOCHEAP +0.38, OWN10 −1.03, BBHEAVY −0.06; the full path:
  the drive exited 0 (2 slates), the reader exited 0 (85 lines; 106 with the two-draw path on a copy, the pick-rule block
  printed once); only the census, the exit codes and the line counts were read.
- **The binding census** (the reviewer's; outcome-blind; bank 1406; 36 slate-banks of 2023–24; code `635b64eb` clean;
  PYTHONHASHSEED=0; 8 tests pass; lab `aae6236b`: `CENSUS_s100_binding.txt` `309dff13…`, `census_mechanics_bank1406.jsonl`
  `7e0208ce…`): **0 row-rule and ownership-cap fallbacks in all 6 arms** (936 of 936); **ONECATCH 504 of 504 B / C solves ruled in
  every arm**; **each arm's one setting binds:** QBCAP3 most rows on one QB 3 (distinct QBs 10.7 vs LIVE 8.0), OVERLAP3 most shared
  3, NOCHEAP no block rows, OWN10 non-DST players 58.7 vs 50.1 (over 30% 3.0 vs 5.4), BBHEAVY book rows 10 / 2 / 11 / 3; **no arm
  dealt identical to LIVE** (rows shared: QBCAP3 10.3, OVERLAP3 1.6, NOCHEAP 15.4, OWN10 6.4, BBHEAVY 3.3 of 26); projection per row
  vs LIVE: QBCAP3 −0.36, OVERLAP3 −0.07, NOCHEAP +0.37, OWN10 −1.19, BBHEAVY −0.11; build 85 s per slate-bank.
- **Code:** nfl2 `production/s100-ceiling-20261009` @ `635b64eb` (branched from study 98's `ac7dd400`): `experiments/s100_ceiling.py`
  `854ecfc3…` (pins s95 `46b80611…`); `scripts/s100_drive.py` `1dbccbe3…`; `scripts/s100_census.py` `4b8bdbbc…`;
  **`scripts/s100_report.py` (the reader) `02320e3d…`** (seed 20261144); `tests/test_s100_ceiling.py` `d7d92b17…` (8).
