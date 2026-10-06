# Preregistration: study 43, a row in every high-total game (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after his decisions on the overlap limit and the fill order (the
reference is his live Week-5 book), the smoke and the binding census (§6), before any scored bank. The operator, 10-06
evening: "study 43 sounds the most interesting. I would like to try that first to be considered for this week." The
laptop acks the census and re-runs the frozen reader.

## 1. Why
- **The operator (10-06):** "let's plan on an expedited schedule for testing all of these. I want to try all that we can
  unless there's a valid reason not to before week 5". The item: the outside review's §4.3 and the Week-4 post-mortem's
  "minimum exposure to every high-total game" -- the winning stack can sit in a game the book does not hold at all.
- **The prior, stated before any outcome:** study 26 (Addendum 132), a one-game shootout build, read NO DIFFERENCE with a
  consistent ceiling signal. Studies 35, 40 and 41, which rearranged the book while keeping its best players, leaned
  positive or passed; studies 36–37, which pushed the best players out, leaned worse. Coverage forces a few rows into
  games the projection would not have chosen, so it costs projection; whether more distinct stacks pay for it is open.

## 2. Arms (study 42's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- Every arm: his live book -- the winners' mix (study 28's cells and quotas), the QB cap of 5 rows, production's caps
  13 / 6, the mean with NO ownership term, and his LIVE Week-5 overlap limit 4 and round-robin fill (his 10-06 evening
  decisions: "Use 4", "Use round-robin").
- **MIXT_LIVE** (reference): his live book.
- **MIXT_COVER4** (DECISION): before the book is filled, each of the slate's top-4 games by pre-lock total
  (`game_ranks`; study 26's top-4 convention) gets one A1-shaped row (QB + 2 + a bring-back) whose QB is from that game
  (every other QB banned for that solve), solved FIRST through the shared state and counted toward A1's quota; then the
  cells fill as his live book does. A1's rows are then ordered by projection (stable), so a coverage row takes the deal
  position its projection earns. A game whose coverage row cannot be built is recorded and skipped.
- **MIXT_COVER6** (exploratory): the top-6 games.
- With no cover the fill IS study 42's frozen `mix_fill` for every fill order (tested on a scripted builder).

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `fb72f59` clean; `results/s43/CENSUS_s43_binding.txt` `8773bae8…`, raw `e255c634…`)

| | top-4 games holding an A1 stack | top-6 | coverage rows built (missed) | QBs | games | distinct | projection per dealt lineup vs MIXT_LIVE |
|---|---|---|---|---|---|---|---|
| MIXT_LIVE (reference) | 2.06 of 4 | 2.89 of 6 | — | 8.22 | 9.47 | 31.5 | — |
| **MIXT_COVER4 (DECISION)** | **4.00** | 4.56 | 4.00 (0) | 8.78 | 9.69 | 33.1 | **−0.20** |
| MIXT_COVER6 | 4.00 | 6.00 | 6.00 (0) | 9.42 | 9.83 | 34.9 | −0.29 |

- It ASSERTS on every row a 26-row book, production's caps, the QB cap 5, no ownership term, each arm's coverage and
  every book within the live limit 4.
- No short books; no arm is identical to the reference on any slate-bank. His live book already holds an A1 stack in
  about half of the top-4 games; the coverage completes the other half at 0.20 projected points per lineup.

## 4. Endpoint and rule (study 18b's, as studies 35–42)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_COVER4 − MIXT_LIVE. Banks 1497–1502, scanned clean by the reviewer (production:
  this study's announcement, a 9-digit id containing 1499 and a `chunk=1500` argument; the lab: study 43's own usage
  lines; disk none) and by the laptop (with its ack); B 20,000, seed 20261024; two-sided 0.95.
- **Guards:** guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show; both
  guards are printed either way.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:** MIXT_COVER6 − MIXT_LIVE; per arm, the top-4 / top-6 games holding an A1 stack, the QBs, the games
  covered and the dealt projection.

## 5. What a verdict can do
- **PASS:** a candidate for his book (production needs a coverage option in `mix_rows`, parity-pinned to this harness,
  and a rehearsal); Week 5 if it reads in time and he says yes, otherwise Week 6.
- **NO DIFFERENCE:** his taste, told what it costs on paper.
- **WORSE or FAIL:** his book stays as it is.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path): every arm built 40 rows (26 book + 14 spares) within the limit 4;
  MIXT_COVER4 covered the four top games and MIXT_COVER6 six, none missed (the live book held 3 of the top 4 on that
  slate); the census and the reader exited 0; the reader printed its 2 headers and its header names STUDY 43 (tested).
  The first smoke stopped the census on a missing record field in the reference arm (`covered`), fixed at `fb72f59`
  before the census.
- **Code:** nfl2 `production/s43-game-cover-20261006` @ `fb72f59` (the census at `79d4a4b`):
  - `experiments/s43_game_cover.py`, sha256 `1fd1b6fb9b06fb59c6cb7765f8f54b346f5264492c2c46319279da30f5d9acab`;
  - `experiments/mix_fill.py` (study 42's, frozen), `dcf6a29997d97369f467377ceb5a69a0ba3bc0edc51fe0c8ec495610a8436fd7`;
  - `scripts/s43_drive.py`, `0eac8f6e742469fb16cf90f074d5f932fc070044a9aa090cc916e48cf613cd48`;
  - **`scripts/s43_report.py` (the reader), sha256 `88115e33850b0a489a5e00956350fa2fb90860a2b5c34e777237355d21730588`**;
  - `scripts/s43_census.py`, `156a5e36b0ff32952469a69f69d4c243ee0d52597a79a151d975b936ab8ebaa9`;
  - `tests/test_s43_game_cover.py`, `0078c98eb18040bcda33f4fd0942eff7533817498ec9ad025c5657eb4b2cc99e` (7 tests).
- **Order:** this freeze → the laptop's ack → the scored run → the confirmatory census, committed before the read → the
  read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field.
