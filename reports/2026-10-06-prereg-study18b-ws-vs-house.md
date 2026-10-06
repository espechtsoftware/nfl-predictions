# Preregistration: study 18b, WS against the house shape on the operator's goal (his real Week-5 plan, production's caps, P(≥ 1 big seat)) (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** (early morning CDT), after the one-slate smoke (§2a) and the laptop's design review, and
before the binding census and any scored bank. The operator (10-06, through the laptop, verbatim): "let's not waste any
time. I would like you to proceed with testing unless there is a valid reason for waiting". Later changes are dated
deviation notes at the end. The reviewer froze it and reads first; the laptop acks the census and re-runs the frozen
reader before the LEDGER row.

**Why this study.**
- Friday's biggest decision is the lineup SHAPE (the decision sheet's item 1: WS recommended).
- That recommendation rests on study 18 (Addendum 129: WS PASS, +42% tickets). Study 18 was measured:
  - in TICKETS (a $20 Milly ticket counts like a $333 seat);
  - at draft A's SHALLOW lines (p79–p91);
  - under the lab's loose caps (a player at 52 of 105 rows, which never binds in a 24-entry book).
- Study 24 (Addendum 130) built WS on the operator's real plan, under production's caps and on his goal, but compared
  WS only with variations of itself.
- So no test has yet asked: **does WS beat the house shape on HIS goal, on HIS plan, under PRODUCTION's caps?**
- The operator (10-05): "If i could win one 333, 555 or 4444 or $500 in the milly, the week is a success". Big = "any
  one except a $20 milly ticket". His tolerance: "Ill trust your opinion on accepting 20% fewer" expected big seats.

## 1. What is known (descriptive)
- **Study 18:** WS +5.849 tickets per slate [+1.613, +10.481]; mean finish +3.3 points. Its cost was a wider spread
  (zero-ticket slates 10% → 15%; worst-decile slate 0.281 → 0.216).
- **Study 24:** WS under production's caps on the Rev1 plan:
  - P(≥ 1 big seat) per slate 0.257;
  - expected big seats 0.538;
  - P < 1% on 51% of slates;
  - busiest QB game 12.8 of 24 entries.

  There was no house-shape arm.
- **Prior from L13:** at a p89 line the plain mean beat the alternatives. **Plan's lines:** p95.7–p99.94 (deep).
- The test is built to come out either way. A deep-line, top-1 goal could favour the house shape's correlation (study
  18's DS and the winners' correlation at the very top: the reviewer's 10-05 read) or WS's better average.

## 2. Arms (one co-run per slate-bank)
Common to every arm, study 24's machinery:
- the plain simulated mean over the dual-law selection worlds; no ownership term;
- ≤ 7 players shared with every earlier row; MAX_PER_GAME 4; a $49k floor; skill players with simulated mean < 1.0
  dropped;
- **production's main caps for the layout's K:** a player at int(0.5 × K) rows, a DST at int(0.25 × K); head K 20 →
  10 / 5, sequential K 24 → 12 / 6;
- build depth 40; the small-contest overlap limit M 5 / ceiling 10.

The arms:
- **C (reference):** the house shape (QB + 2 WR/TE, ≥ 1 bring-back), head layout. Today's main construction, without
  the ownership term.
- **WS (DECISION, vs C):** study 18's WS shape (QB + ≥ 1 WR/TE, bring-back optional, ≤ 3 from the QB's game, a
  second-game pair from any game), head layout.
- **CQ (EXPLORATORY, vs C):** the house shape under production's sequential deal.
- **WSQ (EXPLORATORY, vs CQ):** WS under production's sequential deal (the operator's no-code "more distinct" option).

## 2a. Smoke observations before the freeze
One slate, 2023 W9, throwaway bank 1406. The mechanics and full paths ran (about 29 s each) and were identical; the
census exited 0; the reader exited 0 with 3 comparison blocks, its output unread. Shares are of the 24 DEALT entries.
Outcomes were not read.

| arm | caps (player, DST) | distinct lineups | QB + 2 | bring-back | second-game pair | busiest QB game | top player |
|---|---|---|---|---|---|---|---|
| C | 10 / 5 | 19 | 1.00 | 1.00 | 0.00 | 9 of 24 | 0.58 |
| WS | 10 / 5 | 18 | 0.00 | 0.04 | 1.00 | **14 of 24** | 0.58 |
| CQ | 12 / 6 | 21 | 1.00 | 1.00 | 0.00 | 8 of 24 | 0.54 |
| WSQ | 12 / 6 | 22 | 0.04 | 0.04 | 1.00 | 12 of 24 | 0.54 |

- **The shapes are realized as defined.**
- **On this slate the house shape spread its QBs over the games MORE evenly than WS did.** QB + 2 + a bring-back puts
  4 players in the QB's game, and the per-player cap then forces different QBs. WS, with ≤ 3 from the QB's game, can
  reuse one game's QB pair more often. The binding census reports this over all 53 slates.
- No design change.

## 3. Panel and plan
- **Slates and banks:**
  - the 53 `k1` slates of 2022–24 with Millionaire ownership;
  - **fresh banks 1419/1420** (no bank-label use in either repository's branch scan, 10-05; the scan finds 1415 and
    1406);
  - the smoke and the binding census on throwaway bank 1406.
- **Plan:** the operator's Rev1 Week-5 plan, study 24's copy: `~/s24-panel/plan-week5-rev1-s24.json`, sha256
  `f34f3a0023a649f2270a4c7c0d592ced54ed03d73ec3458cae6d04a3d32982bc`. It has 19 contests and 24 entries, 23 of them
  in 18 big contests, with the Milly judged at its $500+ line.
  - Production's contests.json (94e6ce75) matches it on ids, order and entries; only the Milly line differs, by
    design.
  - If he changes his plan before Friday, the result reads as plan-specific.
- **Field caveat (as study 24):** opponents are Millionaire-style draws, so the absolute probabilities are
  optimistic. The ARM − reference differences decide.

## 4. Endpoints and decision rule
- **PRIMARY = P(≥ 1 big seat) per slate**, WS − C, paired. It is computed exactly per contest as in study 24.
- **Bootstrap:** season-clustered, B 20,000, seed 20261007. **Two-sided 0.95** (one decision arm).
- **GUARD 1:** mean dealt-entry finish, one-sided 0.95 lower bound > −0.015.
- **GUARD 2:** expected big seats ratio ≥ 0.80 (the operator's tolerance; point estimate).
- **Verdicts:**
  - **PASS** = lower bound > 0, at most one season mean < 0, and both guards hold;
  - **WORSE** = upper bound < 0;
  - **FAIL (guard)** = the primary would pass but a guard fails (each failing guard named);
  - **DEAD LEVER** = dealt identically to C on > 80% of slate-banks;
  - **NO DIFFERENCE** otherwise.
- **Secondaries:** as study 24's (expected big seats, P(≥ 2 contests), tickets, slates with P < 1%, best ≥ 200, the
  worst-decile slate, simulated P(≥ 1 big seat) in-sample, the shape and QB-game spread).

## 5. What a verdict can do
- **WS PASS:** the Friday recommendation (WS) stands on his goal, not only on tickets.
- **NO DIFFERENCE:** WS's recommendation rests on study 18 (tickets, shallow lines) alone. Say so plainly, together
  with the shape's other merits and costs. The operator chooses.
- **WORSE:** the recommendation changes. Today's house shape is better for his goal on his plan, and the decision
  sheet says so.
- WSQ vs CQ (exploratory) shows whether the shape result holds under the sequential deal.
- No production change follows without his yes.

## 6. Integrity
- **Code:** nfl2 `production/s18b-ws-vs-house-20261006` @ `9fd014e` (cut from study 24's `6472c5d`):
  - `experiments/s18b_ws_vs_house.py`, sha256 `0e2597e507bab5447a4b74725fa5ab2089711e170d78055b9fe8f1be8aabe056`;
  - `scripts/s18b_drive.py`, `e76221a170434120044bce4760ffb498a15bd68bc99f9072f357f61f7b533925`;
  - **`scripts/s18b_report.py` (the reader), sha256
    `5fb03df3f57124afc0d955bdd18321b669447ed75cb5705f5bbb19067e0d9bc0`**;
  - `scripts/s18b_census.py`, `48e2e93b591dce0f87875e11cb66790658b02662980e4528ba1369de96474f0a`;
  - `tests/test_s18b_ws_vs_house.py`, `cee1e2a97b342f4dd31eea82209331172e6bc48688a7469abdc4f88da6cef1ce` (7 tests;
    green with study 24's 18);
  - the shared module `experiments/s24_qb_game_cap.py`, `ce2cddc1…` (study 24's, unchanged).
- **Order:**
  1. this freeze;
  2. the BINDING census on 1406 (all 53 slates, mechanics only: shape marginals per arm, the realized caps, short
     books, identical-to-reference), acked by the laptop;
  3. the scored run on 1419/1420;
  4. a confirmatory census committed before the reader;
  5. the reviewer's read;
  6. the laptop's byte-identical re-run;
  7. the LEDGER row and Addendum 131.
- **C is production's own constant.** C's stack IS `nfl2.pipeline.PRODUCTION_STACK` (an identity, tested), equal to
  study 18's HOUSE. The live pin `f69598b` defines it identically. The laptop confirmed (10-05) that today's house main
  = PRODUCTION_STACK + head + int(0.5K) / int(0.25K) + MAX_PER_GAME 4 + $49k + max shared 7 + min proj 1.0. There is
  no sleeve on Rev1 (every contest is main track), and the study-1 game cap is off.
- **Transfer caveat.** Production applies the ownership term (tilt 0.20, the FP predictor) to BOTH mains, and with
  `UNION_PROJ_SOURCE=fp` both shapes optimize FP's means. The panel has neither (no FP history for 2022–24), so both
  arms leave them out, symmetrically, as studies 18 and 24 did.
- **Schedule:** freeze and census Tuesday 10-06 morning; read Tuesday; the operator decides Friday 10-09.
