# Preregistration: study 41, even fewer shared players between rows? (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census and re-runs the frozen reader.

## 1. Why
- **From Week 5 his live book runs the union overlap limit 5** (his 10-06 yes on the outside review's Weeks 2–4
  fixed-book screen): every row shares at most 5 of 9 players with every earlier row.
- **Study 40** (Addendum 144) read the 5 against the old 7 on this harness: NO DIFFERENCE, leaning positive on every
  endpoint at no measured cost (+0.028 [−0.012, +0.067] on P(≥ 1 big seat); the mean finish up; expected big seats
  ratio 1.027). The 6 read about as well (+0.024).
- **The question:** does a tighter limit add more, or has the gain plateaued? The operator, 10-06: "Please next proceed
  with anything you feel has a chance of helping"; "I want to exhaust all reasonable options".
- **The prior, stated before any outcome:** a plateau is likely. The 6 read about as well as the 5. The lab's cap-4
  prefix (044) was null on another objective and population. A tighter limit forces more of the book away from its
  best combinations, so the projection cost should grow.

## 2. Arms (study 40's harness unchanged: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- Every arm: the winners' mix (study 28's `mix_book`), the QB cap of 5 rows, production's player / DST caps 13 / 6,
  his live objective (the mean with NO ownership term). The arms differ ONLY in the overlap limit: study 18's
  `MAX_SHARED`, read by the cap builder at every solve (book rows and spares, as production's `--mean-max-shared`), set
  for the arm's build and restored to the harness default 7; every built row is checked against it.
- **MIXT_MS5** (reference): his live book from Week 5, at most 5 shared.
- **MIXT_MS4** (DECISION): at most 4 shared.
- **MIXT_MS3** (exploratory): at most 3 shared.

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `0a1cbc9` clean; `results/s41/CENSUS_s41_binding.txt` `ac618d87…`, raw `42f3ac5d…`)

| | shared players per pair of book rows (max) | QBs | games | distinct players | projection per dealt lineup vs MIXT_MS5 |
|---|---|---|---|---|---|
| MIXT_MS5 (reference, his live 5) | 2.75 (5) | 7.75 | 9.19 | 30.3 | — |
| **MIXT_MS4 (DECISION)** | **2.59 (4)** | 8.39 | 9.50 | 33.2 | **−0.20** |
| MIXT_MS3 | 2.22 (3) | 9.64 | 9.94 | 38.3 | −0.77 |

- It ASSERTS on every row a 26-row book, production's caps, the QB cap 5, no ownership term, and each book's limit.
- No short books; no arm is identical to the reference on any slate-bank. The reference reproduces study 40's MIXT_MS5
  census on the same bank exactly (2.75 / 7.75 / 9.19 / 30.3).
- The paper cost grows as the limit tightens: −0.20 projected points per lineup at 4, −0.77 at 3 (study 40: −0.06 for
  7 → 5).

## 4. Endpoint and rule (study 18b's, as studies 35–40)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_MS4 − MIXT_MS5. Banks 1485–1490, scanned clean by the laptop (production 0 hits;
  the lab's only hits study 41's own `s41_drive.py` / `s41_report.py`; disk none); B 20,000, seed 20261022; two-sided
  0.95.
- **Guards:** guard 1, mean entry pct, one-sided lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show; both
  guards are printed either way.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:** MIXT_MS3 − MIXT_MS5; per arm, the shared players per pair of book rows, the QBs, the games covered
  and the dealt projection.

## 5. What a verdict can do
- **PASS:** the 4 becomes a candidate for Week 6 (Week 5 stays at 5: Friday's rehearsal is at 5). It needs only the
  existing switch (`UNION_MEAN_MAX_SHARED=4`, accepted 3..8), a rehearsal at 4, and his yes. Study 38 accepts only 5–7
  (amendment 1), so a live 4 would need study 38 amended before that week's lock.
- **NO DIFFERENCE:** the 5 stays; the curve is flat from 6 to 4 on this harness.
- **WORSE or FAIL:** the 5 stays, confirmed as the right side of the curve.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path): every arm built 40 rows (26 book + 14 spares), each book's largest
  pairwise overlap equal to its limit (5 / 4 / 3); the census and the reader exited 0; the reader printed its 2 headers
  and its header names STUDY 41 (tested).
- **Code:** nfl2 `production/s41-max-shared4-20261006` @ `0a1cbc9` (the census at `690ffe5`):
  - `experiments/s41_max_shared4.py`, sha256 `904d9ccc1ee873635d32448c8343044733e3f2cf14e3cb0991cc6a6e7601b24c`;
  - `scripts/s41_drive.py`, `6b81f81a7dc0de4095d2e6a9908c7202a4924f1f55c672d161696ba9e3ded776`;
  - **`scripts/s41_report.py` (the reader), sha256 `a5dc8be7b6d46dd5098039bedb33f5da1a6e065e81fdea44d98d4745297c7c42`**;
  - `scripts/s41_census.py`, `bffd1ede78f85f9039ffcccce8d183fe3648302d76c8061abe79b5e65d282a79`;
  - `tests/test_s41_max_shared4.py`, `1925ac8d40a6b4a2e550987ccc74c188bb9b0c97ed1c960f0ae152b028db7811` (5 tests).
- **Order:** this freeze → the laptop's ack → the scored run → the confirmatory census, committed before the read → the
  read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field.
