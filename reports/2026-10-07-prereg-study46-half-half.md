# Preregistration: study 46, half and half — his live book and the regulars' structure in one book (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator's standing directive (10-06 evening, through the laptop), verbatim:** "keep working on this until you
  figure out a strategy like that person's strategy that works". The person is a max-entry regular (150 entries a
  week; name private) who won the Week-2 Millionaire.
- **The laptop's per-lineup benchmark on the REAL Weeks 1–4 Millionaire fields** (private inputs, aggregates;
  disclosed before this freeze; not this study's slates). Mean finish percentile, W1 / W2 / W3 / W4:

  | Book | W1 | W2 | W3 | W4 | W2–4 |
  |---|---|---|---|---|---|
  | the regular (150 entries) | 52.2 | 51.0 | 57.0 | 53.6 | 53.9 |
  | the regulars' structure (study 38's RS0) | 59.5 | 42.1 | 52.9 | 58.5 | 51.2 |
  | our concentrated book (QA0) | 72.6 | 44.0 | 51.1 | 49.6 | 48.2 |
  | the Week-5 settings (limit 4, round-robin) | — | 46.2 | 48.7 | 50.2 | 48.4 |

  - The difference is construction, not players: in W4 (the FP week) every player we used, he used too.
  - Our books hold 7–10 players over 40% of rows (his 0–1). They play about 9 QBs per 26 rows (his about 14). Their
    projected ownership is 122–143% (his 104–111%).
  - But the concentrated book had the only top-1% week of ours (W1, 2 of 26 rows).
- **Big wins are rare even for him.** His only big week in W1–4 was the W2 win. In the other three weeks his best
  lineup finished in the top 0.3–1.6%, short of the Millionaire's big seats (about the top 95 of 160,000). We expect
  to lose most weeks; the strategy targets the chance of the occasional big win.
- **Study 37** put the regulars' structure on the WHOLE book. It read NO DIFFERENCE, −0.051 [−0.136, +0.037], with
  both guards breached. QB breadth alone was neutral; the player curve carried the cost under our ratings (−2.17
  projected points per dealt lineup).
- **The strategy-mix idea** (the operator 10-05: construction as a portfolio of shapes at winner-like rates, never one
  rule for the whole book): half the book each way. The aim is the regulars' steadier average finish plus the
  concentrated book's big weeks.
- **The field.** Item 40 (production `reports/2026-10-06-field-calibration-v2.md`) built a calibrated field sampler (v2)
  that matches the real Millionaire lineups' structure (stacks, bring-backs, salary). It closes about a third of the
  sampled field's top-line gap. This is the first study decided on v2, as agreed with the laptop before the design
  (10-06 18:24). Spread against concentration is decided at the very top of the field, where l02 was easiest.
- **The prior, stated before any outcome:**
  - The half costs 0.66 projected points per dealt lineup (the census), against study 37's 2.17.
  - The question is whether 13 spread rows add more chances at a big seat than the 13 concentrated rows they replace.
  - NO DIFFERENCE is the likeliest reading. WORSE is plausible, because the spread rows project lower. A PASS needs the
    spread rows' independence to outweigh their projection.

## 2. Arms (study 43's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- **Every arm** is built like his live Week-5 book:
  - the winners' mix (study 28's cells and quotas);
  - the QB cap of 5 rows;
  - production's player / DST caps 13 / 6;
  - the mean with NO ownership term;
  - his overlap limit 4 and the round-robin fill (his 10-06 evening decisions: "Use 4", "Use round-robin").
- **MIXT_LIVE** (reference): his live book. This is study 43's MIXT_LIVE (`mix_fill`'s round-robin, called).
- **MIXT_HALF** (DECISION): 13 live rows plus 13 rows under the regulars' tiers at 13 lineups.
- **MIXT_THIRD** (exploratory): 17 live rows plus 9 regulars' rows.
- **MIXT_TWOTHIRDS** (exploratory): 9 live rows plus 17 regulars' rows.

**THE RULES.** They are in the module docstring as well. Production's block mechanism mirrors them with a parity test
against this module's scripted builder.
1. **One builder state for the whole book.** Production's player cap 13 and DST cap 6, the QB cap 5 and the overlap
   limit 4 count EVERY row: both blocks and the spares.
2. **The live block fills FIRST**, by study 42's round-robin on the winners' quotas at the block's own size
   (`S18.allocate(QUOTAS, n_live)`; at 13: A1 4 / A2 2 / B 4 / C 3). A cell that cannot solve passes its quota to A1;
   an A1 failure drops the rest.
3. **Then the RS block** fills by the same round-robin on the quotas at its own size. The regulars' tiers count the RS
   block's OWN rows only (a counter of the committed RS rows).
   - A block QB cap and a block non-QB (non-DST) cap. They are hard: never relaxed.
   - The tiers (r, m): once m players of the group hold ≥ r RS rows, every other player of the group at r − 1 RS rows
     is banned.
   - An RS row that is infeasible under the tiers is solved with the fewest tiers dropped, in study 37's loud-fallback
     order: the non-QB tiers from the lowest r up, then the QB tiers. Each relaxation is recorded.
4. **Positions.** The smaller block (the RS block on a tie) takes book positions ⌊(2i + 1) × 26 / (2n)⌋, i = 0 … n − 1.
   The other block takes the remaining positions in order.
   - HALF: RS at 1, 3, …, 25 (0-based), so a live row keeps rank 1.
   - THIRD: RS at 1, 4, 7, 10, 13, 15, 18, 21, 24.
   - TWOTHIRDS: the mirror of THIRD; the live rows take those positions.
5. **Book order within each block.** Each block's rows are ordered by study 18's entry-weighted interleave, on the head
   weights of ITS positions.
6. **Spares.** Study 28's spares come after the book: the live construction, with no tiers, through the same state.

With no RS rows, the builder IS `mix_fill`'s round-robin.

**The tiers** come from the regulars' cohort medians at n lineups:
- Source: `scripts/s46_regulars_tiers.py`, study 37's method. It covers the 117-user W1–4 cohort, users chosen by entry
  count only, 468 user-weeks, with 30 random n-lineup subsets per portfolio.
- Its 26-row run reproduces study 37's medians exactly.
- Rule (`tiers_from_medians`, tested): each median is rounded half up. The first r that rounds to 0 makes the block cap
  r − 1. Applied to study 37's 26-row medians, the same rule gives study 37's frozen tiers.

| RS rows | QBs with ≥ r rows (r = 2, 3, …) | non-QB with ≥ r rows (r = 2, 3, …) | block QB cap | QB tiers (r, m) | block non-QB cap | non-QB tiers (r, m) |
|---|---|---|---|---|---|---|
| 13 (HALF) | 3.10 / 1.17 / 0.37 | 21.87 / 12.23 / 7.00 / 4.02 / 2.17 / 1.13 / 0.48 | 3 | (3,1) (2,3) | 7 | (7,1) (6,2) (5,4) (4,7) (3,12) (2,22) |
| 9 (THIRD) | 1.90 / 0.52 / 0.10 | 15.43 / 7.28 / 3.37 / 1.42 / 0.53 / 0.13 | 3 | (3,1) (2,2) | 6 | (6,1) (5,1) (4,3) (3,7) (2,15) |
| 17 (TWOTHIRDS) | 4.23 / 1.90 / 0.82 / 0.30 | 27.13 / 16.80 / 10.73 / 6.80 / 4.30 / 2.73 / 1.63 / 0.93 / 0.47 | 4 | (4,1) (3,2) (2,4) | 9 | (9,1) (8,2) (7,3) (6,4) (5,7) (4,11) (3,17) (2,27) |

**Tested** (`tests/test_s46_half_half.py`, 10 tests on a scripted builder):
- with no RS rows, the book equals `mix_fill`'s round-robin;
- the live block's 13 commits equal his book built at 13 rows;
- the tiers count only RS rows: a QB holding 3 live rows still takes 2 RS rows, stopped by the global cap 5;
- the block caps hold, and the QB tiers bind exactly;
- the position formula;
- each block's interleave on its positions' weights;
- the spares carry no tiers;
- the loud fallback: all non-QB tiers, then the lowest QB tier;
- the frozen tiers follow from the medians by the rule;
- the census is outcome-blind;
- the reader: its levels, and the guards gate a PASS only.

**On the real smoke slate**, the builder with no RS rows equals `mix_fill`'s round-robin: rows, cells and spares, 40 of
40.

**Scoring.** Every book is scored on TWO fields drawn from the slate's real Millionaire ownership with one seed: v2
(`l02b_field_sampler.sample_field_v2`, the DECISION field) and l02 (studies 24–45's field, exploratory continuity).

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `52149df` clean; `results/s46/CENSUS_s46_binding.txt` `faf4d76c…`, raw `5b182594…`)

| | projection per book row (live rows / RS rows) | QBs | distinct players | players over 40% of rows | games | projection per dealt lineup vs MIXT_LIVE |
|---|---|---|---|---|---|---|
| MIXT_LIVE (reference) | 128.04 | 8.22 | 31.5 | 7.50 | 9.47 | — |
| **MIXT_HALF (DECISION)** | 127.33 (129.60 / 125.05) | 10.33 | 41.1 | 5.97 | 10.44 | **−0.66** |
| MIXT_THIRD | 127.64 (129.27 / 124.56) | 8.89 | 38.1 | 6.39 | 10.25 | −0.52 |
| MIXT_TWOTHIRDS | 127.04 (129.92 / 125.52) | 10.78 | 43.9 | 5.03 | 10.75 | −0.79 |

- **What the census asserts** (it stops on any failure):
  - every row has a 26-row book, production's caps, the QB cap 5, no ownership term, the limit 4 and round-robin;
  - on every built row, the QB cap 5, the player cap 13, the DST cap 6 and the limit 4 hold;
  - the RS block caps are never exceeded;
  - a full book's RS rows sit at the formula's positions.
- **MIXT_LIVE** reproduces study 43's MIXT_LIVE census on the same bank exactly (128.04, 8.22, 9.47, 31.5).
- **The RS block (HALF):**
  - 9.14 QBs (the regulars' median at 13 lineups is 8.10) and 38.8 distinct players;
  - the QB tiers are never exceeded;
  - the non-QB tiers are overshot 2.75 times per book, because several players cross a threshold in the same row
    (study 37's known property);
  - no relaxed rows, passes, drops or short books;
  - no arm is identical to its reference on any slate-bank.
- **The live block's rows project higher than the live book's average** (129.60 against 128.04). They are the 13 best
  rows of a 13-row fill, and the 13-row player cap lets the best players into every one of them.

## 4. Endpoint and rule (study 18b's, as studies 35–45)
- **PRIMARY:** P(≥ 1 big seat) per slate on the CALIBRATED field (v2), MIXT_HALF − MIXT_LIVE.
  - Banks 1509–1514. The reviewer's unique-blob scan found nothing in production; in the lab, only study 46's own usage
    lines and three decimals whose digits contain 1509; nothing on disk. The laptop scans with its ack.
  - B 20,000, seed 20261026; two-sided 0.95; slates resampled within season.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show. Both
  guards are printed either way.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY (never decision-bearing):**
  - MIXT_THIRD − MIXT_LIVE and MIXT_TWOTHIRDS − MIXT_LIVE on v2;
  - all three contrasts on l02 (continuity with studies 24–45);
  - each arm's levels on both fields. These show how far the calibrated field moves the levels: v2 should read lower,
    closer to the real fields, and that is not a regression;
  - the dealt entries' mean pct by block (live rows, regulars' rows);
  - the fields' top lines;
  - per arm, the QBs, distinct players and the dealt projection.

## 5. What a verdict can do
- **PASS:** MIXT_HALF becomes a Week-5 candidate only if four things land in time:
  - the read lands by Wednesday midday;
  - production's block mechanism passes its parity test against this module's scripted builder (the laptop builds it
    from Wednesday morning, behind a switch that defaults to off). It needs:
    - per-player tier caps on a block's own rows;
    - two blocks through one state;
    - the position formula;
    - each block's interleave on its positions' weights;
  - the reviewer's review;
  - Friday's rehearsal.

  Otherwise it is a Week-6 candidate. Entering it is his call. Study 38 would need an amendment before that week's lock,
  because its paper arms follow the live book.
- **NO DIFFERENCE:** his taste, told plainly what it costs on paper (0.66 projected points per dealt lineup) and what it
  changes (about 2 more QBs, 10 more distinct players, 1.5 fewer players over 40% of rows).
- **WORSE or FAIL:** the live book stays.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path):
  - every arm built 40 rows (26 book + 14 spares) within every cap and the limit 4;
  - no relaxations, passes or drops;
  - the blocks sat at the formula's positions;
  - the census and the reader exited 0; the reader printed its 2 headers, and its header names STUDY 46 (tested);
  - about 75 s per slate-bank (the v2 field adds about 17 s).
- **Code:** nfl2 `production/s46-half-half-20261006` @ `52149df` (the census at `ee6624d`, the raw manifest at `d8d819c`):
  - `experiments/s46_half_half.py`, sha256 `30647fef4175770e8f809cb704f282788f8b4d079319ba282768ad907433ec7a`;
  - `experiments/mix_fill.py` (study 42's, frozen), `dcf6a29997d97369f467377ceb5a69a0ba3bc0edc51fe0c8ec495610a8436fd7`;
  - `experiments/l02b_field_sampler.py` (item 40's, unchanged), `fadf9cfe3269ed746e8bd82d109b2cd35797ff934c93861cac56c5893f1241b5`;
  - `scripts/s46_drive.py`, `b38d9bf745864b845896eab8d5b8a50b8131cb89244ebc65dd8216330c7af3b4`;
  - **`scripts/s46_report.py` (the reader), sha256 `8fb926b198bff9fb8c7775e78f8863bb82f61bcf744677a163809fd843249b50`**;
  - `scripts/s46_census.py`, `bcb8964766bc7500d562a5f09216519861ec41e7cb1e7ea280dc5f526f167637`;
  - `scripts/s46_regulars_tiers.py`, `15182b48c60e0665d0da764f889c19db1a140d3ff36ecd91ab4efc45458c7c1f`;
  - `tests/test_s46_half_half.py`, `60a947d617a603df3c78316b3699328163192797a08e5a20c658d67551a6c85d` (10 tests).
- **Order:** this freeze → the laptop's ack and bank scan → the scored run → the confirmatory census, committed before
  the read → the read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:**
  - Our projections are used here (the live book uses FP's).
  - Outcomes are realized 2023–24 results against a sampled field. The field is now calibrated in structure, but still
    about 2–3 points easy at the very top.
  - The real-field complements are the laptop's per-lineup benchmark (a weekly Monday line from Week 5) and study 38's
    RS0 against QA0 on live FP weeks.
