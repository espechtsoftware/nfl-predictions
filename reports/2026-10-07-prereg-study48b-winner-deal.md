# Preregistration: study 48b, deal his book by the winner-likeness score (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§5), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **Study 48** (lab READ `477e0eea`) read PASS: within his live book, rows that look more like recent winners finish
  better at equal projection. The partial rank correlation was +0.082 [+0.029, +0.134], positive in both seasons. The
  5 most winner-like rows of a book reached the top 1% 2.7% of the time; the 5 least, 0.6%.
- **Study 48's frozen §5:** a use needs its own book-level test, and the operator's goal is P(≥ 1 big).
- **The use with no new lineups:** the same 26 rows, dealt so the most winner-like rows sit on the ranks that carry
  the big entries. In the Rev3 head layout, ranks 1–22 each carry one big entry and ranks 1–2 also carry the
  Millionaire; ranks 23–26 carry only $20 supersats.
- **The operator (10-06 night):** "I want to do it right away."
- **The prior, stated before any outcome:**
  - The book does not change, only which rows meet which contests. So the effect is bounded by how much the score
    separates the rows: the census's mean score on the big ranks rises from −4.52 to −4.42.
  - Study 48's top-1% contrast suggests a positive effect. Its size on P(≥ 1 big) is open.
  - The live order is study 28's entry-weighted shape interleave. Re-ordering by score gives up the shape quotas by
    entries; DEAL_CELL keeps them.

## 2. Arms (`experiments/s48b_winner_deal.py`)
- **The book and score.** Each slate-bank's book is built and scored exactly as in study 48: his live Week-5 book (the
  winners' mix, QB cap 5, caps 13 / 6, no term, limit 4, round-robin), and study 48's frozen score
  (`s48_winner_like.py` `c22d2811…`, imported and sha-asserted; training table `66272167…`).
- **The deal.** Production's head layout deals the same 26 rows three ways (study 1b's deal: the head ranks, then the
  small-contest overlap limit). The spares follow the book, as in production.
  - **DEAL_LIVE** (reference): the book's own order, study 28's interleave. This is today's deal.
  - **DEAL_SCORE** (DECISION): positions by the score, highest first, with ties keeping the book's order.
  - **DEAL_CELL** (exploratory): each position keeps its cell, so the shape quotas by entries hold. Within each cell the
    rows go in score order: a cell's most winner-like row takes that cell's earliest position.
- **Tested** (`tests/test_s48b_winner_deal.py`, 4 tests):
  - the three orders (score order, tie rule, cell-preserving order) and that each is a permutation;
  - study 48's frozen sha;
  - the census is outcome-blind;
  - the reader: its levels, and the guards gate a PASS only.
- **On the smoke slate** the build, the scores and DEAL_LIVE's dealt ranks equal study 48's for the same slate-bank.

## 3. Endpoint and rule (study 18b's, as studies 35–47; the reader `scripts/s48b_report.py`)
- **PRIMARY:** P(≥ 1 big seat) per slate on the calibrated field v2, DEAL_SCORE − DEAL_LIVE.
  - Banks 1527–1532. The reviewer's unique-blob scan found nothing in production; in the lab, only study 48b's own
    usage lines and three decimals containing 1530.
  - B 20,000, seed 20261029; two-sided 0.95; slates resampled within season.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:**
  - DEAL_CELL − DEAL_LIVE on v2;
  - both contrasts on l02;
  - each arm's levels;
  - the mean score on ranks 1–22 and on ranks 23–26.

## 4. What a verdict can do
- **PASS:** a Week-5 candidate only if production can score and re-order his book by Friday 17:00. That needs:
  - the 24 features from production's T-70 frame, FP's projected ownership for the ownership rank, and the lagged TDs
    from `player_week_actuals`;
  - the player-history feature dropped, or taken from the real 2026 top 1% (its coefficient is −0.03);
  - the model's coefficients frozen from the lab;
  - the re-order step before `enter_layout`;
  - parity with this module, the reviewer's review, Friday's rehearsal and his yes.

  Otherwise it is a Week-6 candidate.
- **The transfer caveat** goes with any PASS: this was measured under our projections, while his live book uses FP's.
- **NO DIFFERENCE, WORSE or FAIL:** the live deal stays. Study 48's score becomes a Monday descriptive line.

## 5. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path):
  - parity with study 48: rows, scores and DEAL_LIVE's ranks identical;
  - DEAL_SCORE moved 92% of positions;
  - 53 entries dealt in every arm, with no spare;
  - the census and the reader exited 0; the reader printed its 2 headers, and its header names STUDY 48B (tested);
  - about 56 s per slate-bank.
- **The binding census** (outcome-blind; bank 1406; 36/36, code `6367034` clean; `results/s48b/CENSUS_s48b_binding.txt`
  `7d3f47b7…`, raw `0a977606…`):
  - DEAL_SCORE moves 96% of positions. Its mean score is −4.420 on the big ranks (live −4.517) and −5.008 on ranks
    23–26 (live −4.475).
  - DEAL_CELL keeps every cell and moves 83% of positions.
  - No spare is dealt, and no arm is identical to the reference.
- **Code:** nfl2 `production/s48-winner-like-20261006` @ `6367034` (the census at `0c1d635`):
  - `experiments/s48b_winner_deal.py`, sha256 `507208266b9675a0ca29dad0de433722959c86667c4213f9f15c9f7a425569b9`;
  - `experiments/s48_winner_like.py` (study 48's, frozen), `c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c`;
  - `scripts/s48b_drive.py`, `e0a8b2149f1472d6fa3f5769bb35a2307cff6d5314a23663a97f636cf9429390`;
  - **`scripts/s48b_report.py` (the reader), sha256 `604794ccb8816f9526df9a8198b96456cf03951082829941b7a8a2d8715205e3`**;
  - `scripts/s48b_census.py`, `6aaeaea050367881e1dcf26f7d76b606ad0f2bbdc18f7c8779f01d8ed8d11cb3`;
  - `tests/test_s48b_winner_deal.py`, `cf2179c140354ffdeaf5934353605476bc8ef9fd6d0bf65bf89f1045c07207fd` (4 tests).
- **Order:** this freeze → the laptop's ack and bank scan → the scored run → the confirmatory census, committed before
  the read → the read → the laptop's re-run → the LEDGER row and an Addendum.
