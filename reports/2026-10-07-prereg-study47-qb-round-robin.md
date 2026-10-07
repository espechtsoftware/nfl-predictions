# Preregistration: study 47, the QB-by-QB round-robin — each QB his best row in every shape (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator (10-06 evening) queued** the outside reviewer's wording (study list item 41): "for each QB in turn,
  build his best row under each shape".
- **What his Week-5 book does.** It uses study 42's round-robin over the CELLS: each shape in turn, with the solver
  picking the QB. A top QB's 5 rows can still sit in two or three shapes. Study 42's census: at limit 4 about 3 QBs reach
  the 5-row cap, in about 2 cells each.
- **What the QB-major fill does.** It takes the QBs in turn and gives each one his best row in every shape while the
  quotas last. The top QBs each get one row of every shape (at most 4 in the first pass), and more QBs get rows.
- **The prior, stated before any outcome.** Study 42 read both of its fill orders NO DIFFERENCE: "the order the book is
  filled in is not where the big-win chance is". This fill changes more than the order. It caps a QB at one row per
  shape in the first pass, and it forces his row in a shape the projection may not want (e.g. a bring-back in a
  low-total game). So it should cost some projection and spread the book over more QBs. NO DIFFERENCE is the likeliest
  reading.

## 2. Arms (study 46's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- **Every arm** uses:
  - the winners' mix quotas (study 28's cells: A1 8 / A2 4 / B 7 / C 7 at 26 rows);
  - the QB cap of 5 rows;
  - production's player / DST caps 13 / 6;
  - the mean with NO ownership term;
  - his overlap limit 4 on every built row;
  - study 28's entry-weighted interleave and spares.
- **MIXT_LIVE** (reference): his live Week-5 book (`mix_fill`'s round-robin over the cells, called).
- **MIXT_QBRR_ROW** (DECISION): the QB-major fill, with QBs ordered by their best A1 row (QB + 2 + a bring-back).
- **MIXT_QBRR** (exploratory): the same fill, QBs in order of their own projection.
- **Disclosed: the binding census set the decision arm, before this freeze and outcome-blind.** The draft named
  MIXT_QBRR.
  - Ordering by the QB's own projection also changes WHICH QBs fill the book. It costs 1.85 projected points per dealt
    lineup, against 0.64 for the row order, at the same QB count (8.0) and cells per QB (3.24–3.25).
  - The row order therefore isolates the operator's question: every shape for each QB.
  - The census was re-run on the changed code, and its output is byte-identical (the census does not depend on which
    arm decides).

**THE RULES** (module docstring; scripted-builder tests):
1. **One builder state** for the whole book: the caps, the QB cap 5 and the limit 4 count every row, spares included.
2. **The QB order.**
   - MIXT_QBRR orders by the QB's own objective (his projected mean), ties by id.
   - MIXT_QBRR_ROW orders by the objective of each QB's best A1 row. That row is solved on the empty state and rolled
     back, for the 16 QBs with the highest projection. The rest follow by projection, and a QB with no A1 row follows
     the ranked ones.
3. **The fill.**
   - For each QB in order, and each cell in the reference order (−quota, index: A1, B, C, A2) that still has quota, the
     builder solves his best row in that cell on the current state, with every other QB banned for that solve.
   - A row that cannot be built is skipped and counted.
   - One pass gives a QB at most one row per cell. If quota is left after the last QB, another pass runs, still under
     the QB cap 5.
   - A pass that commits nothing ends the fill, and the rest is dropped and counted.
4. **Then study 28's interleave and spares, unchanged.**

**Tested** (`tests/test_s47_qb_round_robin.py`, 8 tests on a scripted builder):
- the commit order: q00 4 rows (one per cell), q01 4, q02 4, q03 4, q04 3, q05 3, q06 3, q07 1 at the 26-row quotas;
- the row order and its rolled-back peeks;
- skipped rows;
- the second pass under the cap;
- the interleave and spares;
- the census is outcome-blind;
- the reader.

**Scoring.** Every book is scored on the CALIBRATED field v2 (decision) and l02 (continuity), drawn with one seed, as
in study 46.

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `699bf2e` clean; `results/s47/CENSUS_s47_binding.txt` `8b64a043…`, raw `884a3932…`)

| | projection per book row | QBs | QBs at the 5-row cap | the most rows of one QB | cells per QB | distinct players | players over 40% of rows | projection per dealt lineup vs MIXT_LIVE |
|---|---|---|---|---|---|---|---|---|
| MIXT_LIVE (reference) | 128.04 | 8.22 | 3.17 | 5 | 1.98 | 31.5 | 7.50 | — |
| **MIXT_QBRR_ROW (DECISION)** | 127.39 | 8.00 | 0 | 4 | 3.25 | 35.6 | 6.97 | **−0.64** |
| MIXT_QBRR | 126.39 | 8.03 | 0 | 4 | 3.24 | 40.4 | 6.69 | −1.85 |

- **What the census asserts:**
  - every row has a 26-row book, production's caps, no ownership term and each arm's QB order;
  - the QB cap 5 and the limit 4 hold on every built row.
- **Both fills behave as designed.** They take one pass over the QBs, each QB gets at most one row per shape (no QB
  over 4 rows), and nobody reaches the 5-row cap. Skipped rows: 0.03 per book (QBRR).
- There are no drops or short books, and no arm is identical to the reference.
- **The cost.** The live book puts its best QBs at the cap in about two shapes each. The QB-major fill gives the top 8
  QBs every shape, which costs 0.64 projected points per dealt lineup in the row order.

## 4. Endpoint and rule (study 18b's, as studies 35–46)
- **PRIMARY:** P(≥ 1 big seat) per slate on the v2 field, MIXT_QBRR_ROW − MIXT_LIVE.
  - Banks 1515–1520. The reviewer's unique-blob scan of both repositories and the disk:
    - the only hits are study 47's own usage lines;
    - plus two numbers that are not banks: a sha ending `…1518a123513875` beside `results_bank1141.jsonl`, and a
      process id `1520206` in HANDOFF.
    - The laptop scans with its ack.
  - B 20,000, seed 20261027; two-sided 0.95; slates resampled within season.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show. Both
  guards are printed either way.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY (never decision-bearing):**
  - MIXT_QBRR − MIXT_LIVE on v2;
  - both contrasts on l02;
  - each arm's levels on both fields;
  - the fields' top lines;
  - per arm, the QBs, the cells per QB, distinct players and the dealt projection.

## 5. What a verdict can do
- **PASS:** a Week-6 candidate. Production needs a QB-major fill in `mix_rows` (a `--mix-fill qb` option),
  parity-pinned to this module's scripted builder, plus a rehearsal and his yes. Study 38 would need an amendment before
  that week's lock (its paper arms follow the live fill; an unknown fill is refused).
- **NO DIFFERENCE:** his taste, told plainly what it costs on paper.
- **WORSE or FAIL:** the round-robin over the cells stays.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path):
  - every arm built 40 rows within the limit 4 and the QB cap 5;
  - both QB-major arms gave 8 QBs, none at the cap, 3.25 cells per QB;
  - the census and the reader exited 0; the reader printed its 2 headers, and its header names STUDY 47 (tested);
  - about 67 s per slate-bank.
- **Code:** nfl2 `production/s47-qb-round-robin-20261006` @ `699bf2e` (the census at `be4ca05`):
  - `experiments/s47_qb_round_robin.py`, sha256 `9dc350ab8ecb111097718e0fec45dc9a4f6dac0eb7b306f962255108cc8f8d12`;
  - `experiments/mix_fill.py` (study 42's, frozen), `dcf6a29997d97369f467377ceb5a69a0ba3bc0edc51fe0c8ec495610a8436fd7`;
  - `scripts/s47_drive.py`, `d8d76a22a6e33b1bea02beadc87ff2bc23fd32225a27d4b9e1754a68819dc757`;
  - **`scripts/s47_report.py` (the reader), sha256 `6ba9898f364f9382da4de56e6ff27a8701efbfe6e1fc81a69bfa14291bbaa004`**;
  - `scripts/s47_census.py`, `1462b95704174c23c6031a0698038c0214b7326887a4f20f1b2e0d996f60591d`;
  - `tests/test_s47_qb_round_robin.py`, `38a0cad882ae986592eaf3bf8733f2e5c0e8e6c31993d617c8e14af28793ff0d` (8 tests).
- **Order:** this freeze → the laptop's ack and bank scan → the scored run → the confirmatory census, committed before
  the read → the read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:** our projections (the live book uses FP's); realized 2023–24 outcomes against the calibrated field v2,
  with l02 beside it.
