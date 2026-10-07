# Preregistration: study 52, deal the book by the lineups' projected touchdowns, in the harness, with a 2022 go / no-go (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
- **The design came first.** It was sent to the laptop at about 09:29 CT, and the DRAFT was committed at 09:34 (`3641979b`;
  lab `8085c9a`). That was BEFORE study 51's scored run was read (same slates) and BEFORE any number of the laptop's Week
  2–4 re-deal existed.
- **Only §6 and the code shas were added at the freeze.**
- **Disclosed:** the laptop's in-sample re-deal (market TDs, its frozen screen `28e28ab9`) has since read NOT ENTERED
  (ratio 0.101, carried by Week 4's single hit). This study's design, rule and banks were fixed before that number.
- The file carries the date of its scheduled run (10-08). The laptop acks the census, scans the banks and re-runs the
  frozen reader.

## 1. Why
- **The operator (10-07):** "if we haven't already, I'd like to try sorting our lineups by projected touchdowns for the
  lineup".
- **Not tried before** (both ledgers checked). The nearest is study 48b (Addendum 153): the same 26 rows re-dealt by
  study 48's winner-likeness score, so the top-scored rows take the big-entry ranks. It read NO DIFFERENCE (+0.008
  [−0.030, +0.044]; expected big seats ratio 0.899).
- **The use, with no new lineups:** the same 26 rows, dealt so the rows with the most projected touchdowns sit on the ranks
  that carry the big entries. Rev3 head: ranks 1–22 each carry one big entry, and ranks 1–2 also the Millionaire; ranks
  23–26 hold only $20 supersats.
- **The tests:**
  - (a) this study: out of sample, on the simulator's touchdown projection;
  - (b) the laptop's Week 2–4 fixed-book re-deal by the market's summed anytime-TD probability (in-sample; its harm
    screen frozen at production `c9028505`);
  - (c) a production switch only if both are clean.
- **The prior, stated before any outcome:**
  - A re-deal moves wins between contests; it does not make them. Study 48b's re-deal by a score that did predict at the
    row level read NO DIFFERENCE.
  - The outside reviewer's real-field screen of sort keys (Weeks 1–4, `review/outside-fill-order-20261006` @ `b335d1fd`):
    SELECTING the top 26 of our pool by the summed anytime-TD probability improved the average finish (0.80 vs random
    books), but was level with random at the top (0.51).
  - So NO DIFFERENCE on P(≥ 1 big) is the likeliest reading.

## 2. Arms (`experiments/s52_td_deal.py`)
**The book.** On each slate-bank, his live Week-5 book and production's 15 spares are built: 41 rows through one state,
with the winners' mix, mix_fill's round-robin, limit 4, QB cap 5 and caps 13 / 6. This is study 48d's build. Study 48's
harness is used throughout (`s48_winner_like.py` `c22d2811…`, sha-asserted).

**The same rows, dealt three ways** by production's head layout; the spares follow the book, as in production:
- **DEAL_LIVE** (reference): the book's own order.
- **DEAL_TD** (the one DECISION): positions by the lineup's projected touchdowns, most first; ties keep the book's order.
- **DEAL_PROJ** (exploratory CONTROL): positions by the lineup's projection, highest first. It separates touchdowns from
  points: if DEAL_TD ≈ DEAL_PROJ, the idea is projection order.

**The touchdown projection** (pre-lock):
- It comes from the hierarchical simulator's worlds, which the harness already draws for player_mean (`simulate_hsim`,
  the same call and seed). The call adds its `capture`, which records every intermediate and never changes a draw
  (pinned by the lab's `tests/test_hsim_participation.py`; asserted once in the smoke).
- Per player: the mean over worlds of rushing + receiving touchdowns.
- A QB's passing touchdowns are excluded. Production's input, the market's anytime-TD price, covers rushing and
  receiving only.
- A lineup's projected touchdowns are the sum over its 9 players.

**Tested** (`tests/test_s52_td_deal.py`, 6 tests):
- the frozen sha and constants;
- the touchdown projection: rushing + receiving, passing never read, shapes checked;
- the three orders, with ties;
- each deal's scores read in its own dealt order (the book, then the spares);
- the mechanism line;
- the census is outcome-blind;
- the reader: the decision, its printed levels, the go / no-go and the study rule.

## 3. Endpoint and rule (the reader `scripts/s52_report.py`)
- **THE READ: 2023–24** (36 slates).
- **ONE DECISION:** DEAL_TD − DEAL_LIVE, P(≥ 1 big seat) per slate on the calibrated field v2.
  - Two-sided 0.95. B 20,000, seed 20261104; slates resampled within season.
  - Banks 1563–1568. The reviewer's unique-blob scan of both repositories precedes the freeze.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdict:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **THE GO / NO-GO: 2022** (17 k1 slates with real Millionaire ownership, the same banks). CONTRADICTED if the point
  estimate is < 0.
- **STUDY:** SUPPORTED (a candidate for his decision) only if the read PASSes AND 2022 is not contradicted; otherwise
  NOT SUPPORTED.
- **EXPLORATORY** (two-sided 0.95):
  - DEAL_PROJ − DEAL_LIVE, and DEAL_TD − DEAL_PROJ (the touchdowns beyond the projection), on the read and 2022;
  - the decision on l02;
  - the mechanism: the top-1% share of each book's 5 most-TD rows vs its 5 fewest-TD rows (2023–24).

## 4. What a verdict can do
- **SUPPORTED:** a candidate for his decision, with a transfer caveat. The harness deals by SIMULATED touchdowns;
  production would deal by the market's summed anytime-TD probability (`td_value_block_file.py`'s td_prob, every
  rostered skill player). The laptop's Week 2–4 replay is the in-sample check of that exact input.
  - **One construction change per week:** if a term block is armed for Week 5, a supported deal is a Week-6 candidate.
  - If both are ever armed together, the re-deal applies only to the 18 non-block rows over their own positions; the
    block keeps ranks 2, 5, 9, 12, 15, 18, 22 and 25. That form is tested first.
- **NOT SUPPORTED:** the book keeps its own order, and the idea is recorded with this read.

## 5. Production parity
- The book is study 48d's build; LIVE equals its rows and ranks (smoke).
- The deal is production's head layout (`S24.deal_layout`, the same as study 48b) on the re-ordered rows, with the
  spares after.

## 6. Smoke and integrity
- **The smoke** (2024 W10 and 2022 W6, bank 1406, the full path, code as committed at `8085c9a`, clean):
  - the simulator's draws are identical with and without `capture` (2024 W10, 2,000 worlds);
  - the book equals study 48d's LIVE rows, and DEAL_LIVE equals its ranks, on both slates;
  - every deal is a permutation of the book;
  - the census and the reader exited 0, and the reader's header names STUDY 52 (tested).
- **The binding census** (outcome-blind; bank 1406; 53/53 (2022: 17; 2023–24: 36), code `8085c9a` clean;
  `results/s52/CENSUS_s52_binding.txt` `4181eb5a…`, raw `255a7d77…`; lab `bdb8167`):

  | 2023–24 | DEAL_LIVE | DEAL_TD | DEAL_PROJ |
  |---|---|---|---|
  | projected TDs on positions 1–22 | 3.939 | 3.991 | 3.947 |
  | projected TDs on positions 23–26 | 3.674 | 3.391 | 3.631 |
  | projected TDs on positions 1–2 (the Millionaire) | 4.072 | 4.468 | 4.108 |
  | projection on positions 1–22 | 128.55 | 128.31 | 128.69 |
  | rows moved from the book's order | 0 | 24.3 of 26 | 23.4 of 26 |
  | dealt identical to DEAL_LIVE | — | 0.000 | 0.000 |

  - **The projection:** a book row carries 3.90 projected TDs (max − min 1.28 within a book). The rows' TDs correlate
    with their projection at Spearman +0.386. 2022 is alike.
  - About 43 s per slate-bank.
- **Banks:** 1563–1568 and seed 20261104. The reviewer's unique-blob scan of both repositories found them only in study
  52's own files (this prereg's DRAFT, `s52_drive.py`, `s52_report.py`, the tests). That covers every blob up to 5 MB;
  the 8 larger blobs per repository were not searched.
- **Code:** nfl2 `production/s52-td-deal-20261007` @ `8085c9a` (the census at `bdb8167`):
  - `experiments/s52_td_deal.py`, sha256 `38e46b5011f225b3c3a6fec4832563022501f1c1e2dcefb6f4a9ca7531da17c2`;
  - `scripts/s52_drive.py`, `b107c2a0ef3d434adf501cab71bc0290c69409c885c424bad8b91905692dd73e`;
  - **`scripts/s52_report.py` (the reader), sha256 `040794f1a1d8a0b99d2cb11bc90c1edb0f2a08a62f27002c59b04bf828f52a5f`**;
  - `scripts/s52_census.py`, `3afa7b62959d0942ecc4d2edc6353984f296b0eecb2840c547385bb65e9dffc3`;
  - `tests/test_s52_td_deal.py`, `6bea50f6031434d5af64909fb57b8c22c49eb55f6ed04e1610b2ad83ab0d7514` (6 tests);
  - study 48's `s48_winner_like.py` `c22d2811…`, sha-asserted and unchanged.

## 7. Order
1. This DRAFT, committed before study 51 is read.
2. The smoke, then the binding census, after the laptop's replays free the machine.
3. The freeze.
4. The laptop's ack and bank scan.
5. The scored run.
6. The confirmatory census, committed before the read.
7. The read.
8. The laptop's re-run.
9. The LEDGER row and an Addendum.
