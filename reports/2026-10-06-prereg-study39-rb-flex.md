# Preregistration: study 39, a running back in the FLEX on his live book (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank. The
laptop acks the census and re-runs the frozen reader.

## 1. Why
- **The operator (10-06), verbatim:** "Do you see anything in what you just said that warrants a test now? I think more
  RBs in flex is a good start."
- **What the data say** (descriptive, aggregates):
  - The 117 regulars use 2.27–2.50 RBs per lineup (W1–4); his entered books 2.12–2.31. Their heavy core is about half RBs
    (the laptop's graph finding), workhorse goal-line backs that fit any QB stack; our books use goal-line backs at least
    as much (goal-line share of the RBs used: ours .31–.59, theirs .32–.42).
  - **The prior leans AGAINST a gain:** in the 2026 W1–4 Millionaires the WINNING lineups held an RB in the FLEX LESS
    often than the field: top 0.1% 29%, top 1% 33%, the field 39%, our entries 30%
    (`reports/2026-10-05-stacking-and-rb-research.md` §2). Stated before any outcome of this study.

## 2. Arms (study 37's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- Every arm: the winners' mix (study 28's `mix_book`, unchanged), the QB cap of 5 rows, production's player / DST caps
  13 / 6, and **his live objective: the mean with NO ownership term** (his 10-06 decision; studies 31–37 carried 0.20).
- **MIXT_QA0** (reference): his live book.
- **MIXT_RBF** (DECISION): every book row holds at least 3 RBs (an RB in the FLEX). One set constraint in the optimizer
  (all pool RBs, ">=", 3), added by a wrapper on study 24's `optimize` for the arm's build only. A book row infeasible
  under the rule is solved without it and recorded (the loud fallback); spare rows never carry it.
- **MIXT_RBF40** (exploratory): the same rule on 2 of every 5 book rows (rows 0, 2, 5, 7, …).

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `fd06a53` clean; `results/s39/CENSUS_s39_binding.txt` `1a6676b4…`, raw `03803fd6…`)

| | RBs per book row | rows with an RB in the FLEX | QBs | projection per dealt lineup vs MIXT_QA0 |
|---|---|---|---|---|
| MIXT_QA0 (reference) | 2.25 | 25% | 6.94 | — |
| **MIXT_RBF (DECISION)** | **3.00** | **100%** | 7.25 | **−0.63** |
| MIXT_RBF40 | 2.51 | 52% | 6.94 | −0.18 |

- It ASSERTS on every row a 26-row book, production's caps, the QB cap 5, the ≥ 3 RB rule and no ownership term.
- No fallback rows, no short books; no arm is identical to the reference on any slate-bank.

## 4. Endpoint and rule (study 18b's)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_RBF − MIXT_QA0. Banks 1473–1478 (scanned clean by both: the laptop's
  unique-blob scan at 15:27, whose one hit is its own announcement; the reviewer's, whose hits are study 39's own usage
  lines); B 20,000, seed 20261020; two-sided 0.95.
- **Guards:** guard 1, mean entry pct, one-sided lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show; both
  guards are printed either way.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:** MIXT_RBF40 − MIXT_QA0; per arm, RBs per lineup, the FLEX-RB share and the dealt projection.

## 5. What a verdict can do
- **PASS:** an RB-in-the-FLEX rule becomes a candidate, offered with its evidence and its projection cost. It needs one
  set constraint in production's `mix_rows` (reviewed, parity-tested against this harness, rehearsed); the earliest
  honest date is Week 6 unless he asks for Week 5 and it fits Friday's rehearsal. It also joins study 38's companion
  paper columns under FP.
- **NO DIFFERENCE:** his taste, told plainly what it costs on paper.
- **WORSE or FAIL:** his book stays as it is.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path): the census and the reader exited 0; the reader printed its 2 headers
  and its header names STUDY 39 (tested).
- **Code:** nfl2 `production/s39-rb-flex-20261006` @ `fd06a53` (the census at `e17e1b1`):
  - `experiments/s39_rb_flex.py`, sha256 `45b0dc67edaadb0052ba8d14f2317d7f5ecf6bc5a9c35b8b60298b1fdb978d52`;
  - `scripts/s39_drive.py`, `c62dbfff67dfdbc7aa38b3564f421fc8759d19da991d1c5bd814b9895bbebb45`;
  - **`scripts/s39_report.py` (the reader), sha256 `af500cc78050ca3c05f4c78049e2915d959b52a504d8bd1b9d50e3b6a3bf69ce`**;
  - `scripts/s39_census.py`, `3024d4a3bb2978bd71da999642ea7fa087f262fe645d3093c3ac886ca171b976`;
  - `tests/test_s39_rb_flex.py`, `7af9ab39a4ff3e80ba711bd08551f72205bf17f3ebf453e48c0b37af793ac372` (5 tests).
- **Order:** this freeze → the laptop's ack → the scored run → the confirmatory census, committed before the read → the
  read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field.
