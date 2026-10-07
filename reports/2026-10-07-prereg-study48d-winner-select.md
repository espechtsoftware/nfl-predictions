# Preregistration: study 48d, choose the book by the winner-likeness score (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding census (§5), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator (10-07):** "It seems study 48 was successful. Why not adopt it?" When offered the version that USES the
  signal (selection): "Yes, test it now". He decides Friday.
- **What came before:**
  - **Study 48 (Addendum 152) PASS:** within his book, the more winner-like rows finish better at equal projection
    (+0.082 [+0.029, +0.134]).
  - **Study 48b (Addendum 153) NO DIFFERENCE:** re-dealing the same rows by the score does not help. Ranks 1–22 already
    carry a big entry each, and ordering the whole book breaks the shape balance. The within-cell order leaned positive
    (+0.022 [−0.003, +0.048]).
  - **The laptop's real-field check** (Week 3 and Week 4 replays) showed no support: partial −0.10 and −0.02 at about
    0.2 standard error.
- **What selection changes:** it changes WHICH rows are entered. Spares with higher scores replace book rows with lower
  ones, within each cell, so the shape balance holds.
- **The prior, stated before any outcome:**
  - The census shows the price. SEL_CELL swaps in 7.7 spares per book and gives up 1.68 projected points per row. The
    spares are built after the book, from what the caps leave.
  - Study 48's effect is about 0.08 in rank correlation at equal projection, and selection does not hold the
    projection equal.
  - So NO DIFFERENCE or WORSE is likelier than a PASS.

## 2. Arms (`experiments/s48d_winner_select.py`)
**The book and spares.** On each slate-bank his live Week-5 book is built exactly as in study 48 (the winners' mix,
limit 4, round-robin, QB cap 5, caps 13 / 6, no term), plus production's 15 spares (`--mix-spares 15`). That makes 41
rows through one state. Every row is scored by study 48's frozen walk-forward model (`s48_winner_like.py` `c22d2811…`,
imported and sha-asserted; training table `66272167…`).

**The arms, each choosing 26 of the 41:**
- **LIVE** (reference): the book, rows 0–25, dealt as today.
- **SEL_CELL** (DECISION): per cell, its book count of the most winner-like rows among that cell's book rows and spares.
  Ties go to the book row, then to build order. Within a cell the rows stay in build order, then study 28's
  entry-weighted interleave runs on the head weights, as today.
- **SEL_CELL_ORD** (exploratory): SEL_CELL with each cell's rows in score order (48b's DEAL_CELL on the chosen rows).
- **SEL_ALL** (exploratory): the 26 most winner-like of the 41, with no quotas and ties as above; the interleave on
  their cells.

**Production's constraints hold for any 26 of the 41**, because every row was built under the caps (13 / 6, QB 5)
counted over all built rows, and within the overlap limit 4 of every earlier row. This is asserted on every chosen book.

**Tested** (`tests/test_s48d_winner_select.py`, 6 tests): the per-cell selection keeps the book's cell counts; the tie
rule; the within-cell orders; the global top 26; the interleave; the constraint check; the census is outcome-blind;
the reader's levels.

**On the smoke slate**, the book, its scores and LIVE's dealt ranks equal study 48's for the same slate-bank.

## 3. Endpoint and rule (study 18b's; the reader `scripts/s48d_report.py`)
- **PRIMARY:** P(≥ 1 big seat) per slate on the calibrated field v2, SEL_CELL − LIVE.
  - Banks 1533–1538. The reviewer's unique-blob scan found in production only a draft group id `153428` beside the word
    "bank"; in the lab, only study 48d's own usage lines.
  - B 20,000, seed 20261030; two-sided 0.95; slates resampled within season.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:** SEL_CELL_ORD and SEL_ALL against LIVE; all three on l02; each arm's levels, spares taken in,
  projection and score.

## 4. What a verdict can do
- **PASS:** a Week-5 candidate if four things land by Friday 17:00:
  - production's selection step: after `mix_rows`, per cell from the book plus the spares with the frozen all-53 score
    (`winner_like` is merged), then the re-interleave, behind a switch and pinned to this module;
  - parity;
  - the reviewer's review and Friday's rehearsal;
  - his yes.

  Otherwise it is a Week-6 candidate. The transfer caveat goes with it: this was measured under our projections, and
  his live book uses FP's.
- **NO DIFFERENCE, WORSE or FAIL:** the book stays as built. Study 48's score stays a Monday descriptive line.

## 5. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path):
  - 41 rows were built; parity with study 48 held (book rows, scores and LIVE's ranks identical);
  - SEL_CELL took in 7 spares at the book's cell counts, at 126.62 against 128.00 projected per row;
  - every chosen book was within the caps and the limit;
  - the census and the reader exited 0; the reader printed its 2 headers, and its header names STUDY 48D (tested);
  - about 55 s per slate-bank.
- **The binding census** (outcome-blind; bank 1406; 36/36, code `d746010` clean; `results/s48d/CENSUS_s48d_binding.txt`
  `c445d667…`, raw `9510dd7b…`):
  - SEL_CELL takes in 7.67 spares, with projection per row 126.36 against 128.04 (−1.68) and mean score −4.397 against
    −4.511;
  - SEL_ALL takes in 7.42 spares, at −1.71;
  - every chosen book is within production's constraints, and no arm is identical to LIVE.
- **Code:** nfl2 `production/s48d-winner-select-20261007` @ `d746010` (the census at `3b9e5c7`):
  - `experiments/s48d_winner_select.py`, sha256 `b3e13acd73b8cc7c70305861f72475027d9d309e1f5722db54d33d9de7823709`;
  - `experiments/s48_winner_like.py` (study 48's, frozen), `c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c`;
  - `scripts/s48d_drive.py`, `95f907f534de38c4766debe1d41e0d141dc59bb7106a285373887983a8b626c3`;
  - **`scripts/s48d_report.py` (the reader), sha256 `e786af21fe541bf5ef651e2f68139d108b74d0a9fdf96429a00e4501f04b9c23`**;
  - `scripts/s48d_census.py`, `f185aff047fb8f8f5c912c9f9a4e769cc417078cbbfd707c3cee7099b5d1c4a4`;
  - `tests/test_s48d_winner_select.py`, `79a3ce1ea8a97e90b5fd4b51cc62e6c9538a42f143ad54b92c10242a5bc15afb` (6 tests).
- **Order:** this freeze → the laptop's ack and bank scan → the scored run → the confirmatory census, committed before
  the read → the read → the laptop's re-run → the LEDGER row and an Addendum.
