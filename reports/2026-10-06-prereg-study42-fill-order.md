# Preregistration: study 42, the fill order (his best lineups first, or every shape for each QB?) (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census and re-runs the frozen reader.

## 1. Why
- **The operator (10-06), verbatim:** "at one point this week we changed the way lineups are created so that we start
  with the best lineup for a QB so that others don't use up the available slots. Can you verify that we did that? Are we
  confident that we are putting our best strategy first for a given QB?" And, on the timing: "why is week 6 the
  earliest?"
- **Verified by the laptop: it was NOT done** (study list item 2, his 10-04 "use quality" request, was never run).
  Production's `mix_rows` (and study 28's `mix_book`) fill the shape cells one after another, largest quota first
  (A1 8 → B 7 → C 7 → A2 4 at K 26), each greedy best-first through one shared state, so a capped QB's 5 rows go to the
  EARLIEST cells.
- **Two answers, one study** (the operator's rule, 10-05: when agents disagree, both approaches become arms of one co-run
  study):
  - **The value fill** (the reviewer's first design, built with the laptop): at each step commit the best next row
    across the cells, so a capped QB's rows go to his highest-projecting shapes.
  - **The round-robin** (the outside reviewer's objection, 10-06, `reports/2026-10-06-fill-order-replay-and-winners-shapes.md`):
    in Weeks 2–4 the winning shape followed the game script, not the QB (W2 the top 100 split QB+1 no bring-back 35% /
    QB+2 no bring-back 28%; W3 full stacks with a bring-back 63%; W4 QB+1 with a bring-back 58%), so a capped QB's rows
    should COVER the shapes; the value fill hands the top QB his least-constrained shapes first, and today's order puts
    them in the first cell. One row per cell in turn gives each cell's next row to the best available QB.
- **Disclosed, before this freeze and after the design was committed** (`e551bf8`, `a50796d`): the laptop's fixed-book
  replays of Weeks 2–4 on the real Millionaire fields (production at the armed Week-5 settings, our projections in W2–3,
  FP in W4). Mean entry pct over the three weeks: group5 .497, rr5 .503, group4 .492, rr4 .481, value4 .471, value5 .445;
  P(≥ 1 big seat) is decided each week by one or two rows (the live W2 book holds one 185-point top-1% row). Those weeks
  are not this study's slates; the design did not change after them.
- **The prior, stated before any outcome:** the value fill should not move the book's mean projection (the replays: ±0.1)
  and widens its spread (the bottom rows lower); the round-robin spreads each top QB over the shapes. Studies 35, 40 and
  41, which rearranged the book while keeping its best players, leaned positive or passed; studies 36–37, which pushed
  the best players out, leaned worse.

## 2. Arms (study 40's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- Every arm: the winners' mix (study 28's cells and quotas), the QB cap of 5 rows, production's player / DST caps 13 / 6,
  his live objective (the mean with NO ownership term). A 3 × 2 of the FILL ORDER by the OVERLAP LIMIT (study 41's PASS
  made 4 a candidate; his Week 5 is armed at 5; study 18's `MAX_SHARED` at every solve, book rows and spares, every built
  row checked). The interleave (the book's order for the deal) and the spares are study 28's, unchanged.
  - **group** (the reference, his live book): cells in order (−quota, index), each cell's rows consecutively (study 28's
    `mix_book`, called).
  - **value**: until every quota is filled, the next row of EVERY cell with quota left is solved on the current state
    (then the builder is rolled back), and the single highest-objective row is committed; ties go to the earlier cell.
  - **rr** (round-robin): one row per cell in turn, in the reference's order.
  - In both, a cell that cannot solve passes its remaining quota to A1 (counted), as the reference passes failing rows;
    if A1 cannot solve, its rows are dropped (recorded).
- Arms: MIXT_GROUP4, MIXT_VALUE4, MIXT_RR4, MIXT_GROUP5, MIXT_VALUE5, MIXT_RR5.
- The fill function lives in `experiments/mix_fill.py` (shared with study 38's amendment 2: one implementation, pinned).
  Production's `--mix-fill value` / `--mix-fill rr` (the laptop, `production/mix-fill-value-20261006` @ `abed460a`)
  are parity-pinned to this module's scripted-builder tests (the value commit order and tie, the round-robin order, the
  failing cell's quota to A1).
- **Tested** (`tests/test_s42_fill_order.py`, a scripted builder): the value choices and tie rule, the rollback of every
  peek, the pass to A1, the round-robin order, and that the reference's loop through `mix_fill`'s interleave and spares
  reproduces study 28's `mix_book` exactly (spares included). **On the real smoke slate** the same parity holds (rows,
  ranks and cells).

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `a50796d` clean; `results/s42/CENSUS_s42_binding.txt` `224dd979…`, raw `09daa9c5…`)

| | projection per book row | QBs | QBs at the 5-row cap | cells per QB | capped QBs' rows in A1 | dealt projection vs group |
|---|---|---|---|---|---|---|
| MIXT_GROUP4 (reference at 4) | 127.90 | 8.39 | 3.03 | 2.01 | .352 | — |
| **MIXT_VALUE4** | 127.89 | 8.56 | 2.78 | 1.93 | .185 | +0.08 |
| **MIXT_RR4** | 128.04 | 8.22 | 3.17 | 1.98 | .267 | +0.39 |
| MIXT_GROUP5 (reference at 5) | 128.11 | 7.75 | 3.42 | 1.80 | .380 | — |
| **MIXT_VALUE5** | 128.06 | 7.72 | 3.39 | 1.89 | .217 | +0.08 |
| **MIXT_RR5** | 128.20 | 7.72 | 3.47 | 2.03 | .275 | +0.40 |

- It ASSERTS on every row a 26-row book, production's caps, the QB cap 5, no ownership term, each arm's fill and limit,
  and each book within its limit.
- No passes to A1, nothing dropped, no short books; no arm is identical to its reference on any slate-bank.
- Both fills move the capped QBs' rows out of the first-filled cell (A1: .35–.38 → .19–.22 value, .27–.28 rr). The value
  fill leaves the book's projection where it was; the round-robin raises the dealt projection by 0.4 points per lineup
  (its rows' commit order changes which rows the interleave deals most).

## 4. Endpoint and rule (study 18b's, as studies 35–41; two decisions)
- **TWO DECISIONS**, each against the group fill and each POOLED over the two limits (per slate, the mean of the fill's
  difference at 4 and at 5): **MIXT_VALUE** (value − group) and **MIXT_RR** (rr − group).
- **PRIMARY:** P(≥ 1 big seat) per slate; **two-sided 0.975 for each decision** (Bonferroni over the two). Banks
  1491–1496, scanned clean by the laptop (16:32: no hits in either repo, disk clean) and by the reviewer (the only hits
  are the announcements and study 42's own usage lines, and a number 0.01492 beside bank 930); B 20,000, seed 20261023;
  slates resampled within season.
- **Guards** (per decision, pooled the same way): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2,
  expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show; both
  guards are printed either way.
- **Verdicts per decision:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY (two-sided 0.95):** each fill at each limit against the group fill; rr against value, pooled; GROUP4 −
  GROUP5 (study 41's contrast on fresh banks); per arm, the projection per book row, the QBs, the QBs at the cap, the
  dealt projection.

## 5. What a verdict can do
- **PASS (either decision):** that fill becomes a candidate for Week 5 if it reads in time and he says yes (the switch
  exists and is parity-pinned; Friday's rehearsal), otherwise Week 6. Given the real-week replays, a value PASS would be
  offered with that warning stated.
- **NO DIFFERENCE:** his taste, told plainly what it costs or gains on paper.
- **WORSE or FAIL:** the group fill stays.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path): every arm built 40 rows (26 book + 14 spares), each book's largest
  pairwise overlap equal to its limit; value and rr filled in 26 steps with no passes; the group fill rebuilt through
  `mix_fill` equals study 28's `mix_book` (rows, ranks, cells); the census and the reader exited 0; the reader printed its
  3 headers and its header names STUDY 42 (tested). About 92 s per slate-bank.
- **Code:** nfl2 `production/s42-fill-order-20261006` @ `a50796d` (the census at `0a778b3`):
  - `experiments/mix_fill.py` (the fill; shared), sha256 `dcf6a29997d97369f467377ceb5a69a0ba3bc0edc51fe0c8ec495610a8436fd7`;
  - `experiments/s42_fill_order.py`, `a852045701809f117e9921021e5fe1abf6027b3c1753ce8b834045006cd711c8`;
  - `scripts/s42_drive.py`, `4a4e752af9730c4f7072c5e9053cd75084113a4933878af38fb4b2b310e4342c`;
  - **`scripts/s42_report.py` (the reader), sha256 `75062239cab424558af945d0483ba29d0ed18585ec5692f2393185eb0627167c`**;
  - `scripts/s42_census.py`, `a4484aee472108af688fa7492102f65e047a504ec1dc3297bc4d8c55753c9cc2`;
  - `tests/test_s42_fill_order.py`, `33f7d1a692b9609a51fea413b8560cf0291f99c21654a84edc66f4637217a767` (7 tests).
- **Order:** this freeze → the laptop's ack → the scored run → the confirmatory census, committed before the read → the
  read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field; the
  real-field complement is the laptop's Weeks 2–4 replays and the §6.1 field audit (the reviewer, 10-06/07).
