# Preregistration: study 100, the ceiling sweep — five morning-armable variations of his live book, read on the book's best real lineup, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09** (the times are this file's commits) by the outside reviewer; code done (8 tests), the smoke waiting
for a machine gap. The lab reviewer reviews, runs the binding census and FREEZES; the laptop acks. **Information for his morning
decision; a pick goes to study 101 (committed before this study's READ).**
- **Banks and seed (proposed; the laptop's full-set check and scan decide):** **3260–3271** (set A 3260–3265, set B 3266–3271;
  sims bases 3310–3321, fields 3960–3971) — above every derived seed in use after study 99 (its sims 3248–3259); seed 20261144.

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
- **BBHEAVY** — each no-bring-back cell halved into its bring-back twin: A1 .37 / A2 .07 / B .42 / C .14 (rows 9 / 2 / 11 / 4).

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
- **The smoke:** (a machine gap the lab reviewer names; filled in when it ends).
- **Code:** nfl2 `production/s100-ceiling-20261009` @ `635b64eb` (branched from study 98's `ac7dd400`): `experiments/s100_ceiling.py`
  `854ecfc3…` (pins s95 `46b80611…`); `scripts/s100_drive.py` `1dbccbe3…`; `scripts/s100_census.py` `4b8bdbbc…`;
  **`scripts/s100_report.py` (the reader) `02320e3d…`** (seed 20261144); `tests/test_s100_ceiling.py` `d7d92b17…` (8).
