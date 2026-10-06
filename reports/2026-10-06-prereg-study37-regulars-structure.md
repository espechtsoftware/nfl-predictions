# Preregistration: study 37, the regulars' structure on the recommended book (more QB stacks and a steep player curve) (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the support census (§6), before any scored bank. The laptop acks the binding census and re-runs the frozen reader. The reference book is the one he said yes to on 10-06 (the winners' mix + the tilt + the QB cap), identical to studies 35 / 36's MIXT_QA.

## 1. Why
- **The operator (10-06), verbatim:** "I think we need to look into this further. Is it because we aren't choosing
  suitable alternatives or because we suddenly are losing a stack because the QB has changed? Look closely at how the
  winners do it - especially the one that we were tracking closely. Is their pool better only because of their volume?
  WHile I expect that answer, that's not what I want to hear. I want to find a way to reduce my dependency on so many
  players while having suitable alternatives to pivot to."
- **What the data say** (descriptive, construction only, aggregates; users chosen by entry count only; the laptop's
  analysis, reproduced by the reviewer):
  - **Study 36's cost was the alternatives, not the stacks.** Every lineup kept its stack (the mix's cells enforce it).
    A capped player's rows went to the next-best comparable player from anywhere on the slate: 2.0 / 5.3 / 92.7% same
    team / same game / another game, which IS the slate's base rate among comparable alternatives (2.2 / 5.0 / 92.9%),
    about 0.8 projected points lower.
  - The QB cap does unstack our top receivers (with their own QB .271 → .212), but the regulars' top receiver rides
    with his own QB even less (.15; .45 with no game-mate), so that is not a gap.
  - **Not volume.** Random 26-lineup subsets of the 117 max-entry regulars' W1–4 portfolios (468 user-weeks) still
    hold about 11.3 QBs (the most-used at .219), 2.0 / 5.3 / 9.7 non-QB players over 40 / 30 / 20% of the lineups and
    53 distinct non-QB players. Real users with 20–40 entries: 10 QBs, 3 / 6 / 10, 46 distinct. Our MIXT_QA (26 book
    rows): 6.75 QBs (.19), 9.5 / 11.8 / 13.6, 25 distinct.
  - **Their alternatives are other stacks.** When a regular leaves out his most-used player, the same-position
    replacement comes from another game 95.7% of the time (the base rate), 2.4–3.2 projected points (ours) below the
    player. Same-game swaps are not their habit (his doubt about that idea was right), so there is no same-game arm.
  - **Top receiver:** they pair a QB with his team's top receiver (by salary) .60 of the time, our book .58: matched,
    so no arm.
  - The winner he tracked (User15) at 26 lineups: 13.5 QBs (the most-used at .18); 1.0 / 3.4 / 7.9; 63 distinct.
- **Priors:**
  - Study 35: a step toward QB breadth (4.2 → 6.8 QBs) leaned positive on every endpoint (+0.026 [−0.027, +0.083]).
  - Study 36: a flat player cap (0.35) did not move P(≥ 1 big) and cost mean finish (−0.024; lower −0.043) at −1.31
    projected points per dealt lineup.
  - Study 24: a per-GAME QB cap cost −1.8 points (it failed his tolerance).
  - **The harness cannot credit the regulars' pre-lock knowledge.** By OUR projections their replacements look 2.4–3.2
    points worse than the player they leave out, yet they beat the field by +6.1 points per lineup (study 34). The
    harness prices every alternative with our projections, so expect a projection cost and a guard-1 risk.

## 2. Arms (study 31's harness: 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`, the 0.20 term; study 28's `mix_book` unchanged, with the builder swapped in)
- **MIXT_QA** (reference): study 35's QB cap (5 rows) and production's player / DST caps (13 / 6 rows): his yes-book.
- **MIXT_RS** (DECISION): **the regulars' structure** = the QB tiers + the non-QB tiers.
- **MIXT_QBB** (exploratory): the QB tiers only (non-QB players at production's 13-row cap).
- **MIXT_NQC** (exploratory): the non-QB tiers only (the QB cap of 5 rows, as the reference).
- **A tier (r, m)** lets at most m players of its group reach r rows of the 26-row book. Once m have, every other
  player of the group at r − 1 rows is banned for the next solve. A QB is one per row, so the QB tiers bind exactly;
  several non-QB players can cross a threshold in the same row, so a non-QB tier can be overshot (the census reports
  it). Production's player (13) and DST (6) caps stay outside every arm.
- **The tiers are the regulars' cohort medians at 26 rows, rounded half up. There is no calibration grid.** Medians of
  the number of QBs / non-QB (non-DST) players holding ≥ r of 26 lineups (468 user-weeks, 30 random subsets each;
  `scripts/s37_regulars_tiers.py`, which reads the private lineups at run time):

  | r (rows of 26) | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | QBs ≥ r (median) | 6.50 | 3.60 | 1.97 | 1.07 | 0.55 | 0.25 | 0.10 | | | | | |
  | **QB tier m** | **7** | **4** | **2** | **1** | **1** | 0 → cap 6 | | | | | | |
  | non-QB ≥ r (median) | 35.53 | 25.08 | 18.07 | 13.23 | 9.67 | 7.10 | 5.27 | 3.83 | 2.77 | 1.98 | 1.40 | 0.93 |
  | **non-QB tier m** | **36** | **25** | **18** | **13** | **10** | **7** | **5** | **4** | **3** | **2** | **1** | **1** |

  - QB: a 6-row cap (no QB reaches 7 rows) and tiers (6, 1), (5, 1), (4, 2), (3, 4), (2, 7): at least 11 QBs, the
    most-used at 6 rows (.23).
  - **Disclosed: QB r2 is exactly 6.50.** Half up gives 7 (at least 11 QBs); half-even would give 6 (at least 12).
    "Rounded half up" is in the harness committed before any census ran (`18dfab9`'s module and commit message).
  - Users with 26–40 entries give nearly the same profile (QBs 10.9 / 6.3 / 3.6 / 2.0 / 1.0 / 0.6; non-QB 33.0 / 23.8 /
    17.3 / 13.0 / 10.0 / 8.0 / 6.2 / 4.9 / 3.8 / 2.9 / 2.0 / 1.6).

## 3. The support census (outcome-blind; bank 1406)
- **The binding census** (bank 1406, mechanics only, 36/36 slate-banks, code `35aea10` clean;
  `results/s37/CENSUS_s37_binding.txt` `57aa1f1f…`, raw `a745be10…`). It ASSERTS on every row a 26-row book,
  production's player / DST caps (13 / 6) and the frozen QB caps and tiers. Book rows (like-for-like with the regulars'
  26-lineup subsets):

  | | QBs | most-used QB | non-QB over 40 / 30 / 20% | distinct non-QB | projection per dealt lineup vs MIXT_QA |
  |---|---|---|---|---|---|
  | the regulars (medians) | 11.3 | .219 | 1.98 / 5.27 / 9.67 | 53.3 | — |
  | MIXT_QA (reference) | 6.72 | .192 | 9.67 / 11.78 / 13.50 | 26.0 | — |
  | **MIXT_RS (DECISION)** | **11.00** | **.231** | **2.31 / 5.14 / 10.42** | **50.8** | **−2.18** |
  | MIXT_QBB | 11.00 | .231 | 9.69 / 11.58 / 13.25 | 29.3 | −0.22 |
  | MIXT_NQC | 7.94 | .192 | 2.28 / 5.25 / 10.28 | 51.5 | −2.07 |

  - **MIXT_RS reproduces the regulars' structure at our size.** The QB tiers bind exactly. The non-QB tiers overshoot
    slightly where several players cross a threshold in one row (mean +0.1 to +1.3 players per tier, at most +5 at
    r2).
  - **Dealt entries** (the head layout deals top rows more): MIXT_RS's most-used QB .253, players over 40% 2.67,
    distinct 50.8. MIXT_QA's: .223, 9.42, 26.0.
  - **The paper cost is larger than study 36's** (−2.18 per dealt lineup against −1.31). The QB tiers alone cost
    −0.22; the player curve carries the cost.
  - The QB tiers alone leave the players as concentrated as the reference (9.69 over 40%). The player curve alone
    raises the QBs from 6.7 to 7.9.
  - **Support:** no short books; cells as the reference; no passes to A1. **The loud fallback fired once**: MIXT_RS
    on 2024 W17, one book row, the lowest non-QB tier (r2) dropped. No arm is identical to the reference on any
    slate-bank.
- **The regression check** (`CENSUS_s37_regression.txt`): the 35 slate-banks the first support census completed are
  byte-identical (book rows and deal) under the fixed code in every arm. Only 2024 W17 is new.

## 4. Endpoint and rule (study 18b's)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_RS − MIXT_QA.
  - Banks 1467–1472 (scanned clean by both: the laptop's unique-blob scan of every ref at 12:45; the reviewer's
    unique-blob scan of both repositories, whose only matches are today's reservation lines and a sha fragment; no
    files on disk). B 20,000, seed 20261019, two-sided 0.95.
- **Guards:**
  - guard 1, mean entry pct, one-sided lower > −0.015;
  - guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** They are evaluated only when the primary passes (lower bound > 0, at most one
  negative season). A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show; both guards are
  printed either way (the rule study 36's audit asked to be stated in words).
- **Verdicts:** DEAD LEVER (MIXT_RS identical to MIXT_QA on > 80% of slate-banks) / WORSE (upper < 0) / PASS / FAIL
  (guard) / NO DIFFERENCE.
- **EXPLORATORY:** MIXT_QBB − MIXT_QA and MIXT_NQC − MIXT_QA; per arm, the book rows' and dealt entries' QB and player
  concentration, and the dealt projection.

## 5. What a verdict can do
- **PASS:** the regulars' structure becomes a candidate, offered with its evidence and its projection cost. It needs
  new production code (QB and non-QB tier caps in `union_reselect`, with a parity test against this harness) and a
  rehearsal. The earliest honest date is Week 6; Week 5 only if he asks and the code plus a rehearsal fit by Friday.
- **NO DIFFERENCE:** the structure is his taste, told plainly what it costs on paper and in average finish (it would
  still need the production code).
- **WORSE or FAIL:** the recommended book stays the yes-book (QB cap 5, player cap 0.5).

## 6. Smoke and integrity
- **Two findings before freezing, both fixed and disclosed** (the reason the smoke and the support census run first):
  1. **The smoke:** the row profile had counted every row the builder made (the reference builds 40), not the book.
     The head deal and its overlap limit use ranks 0..25 only (the pinned `limit_small_overlap` wraps within the mean
     ranks), so later rows are unused spares. The row profile and the row projection now use the first 26 rows.
  2. **The first support census:** on 2024 W17 MIXT_RS built 25 rows and the deal (which needs 26) refused. Late in a
     tiered book the low tiers ban every once-used player and the rest sit at their tiers. **The loud fallback**, as
     production's overlap limit never refuses: a BOOK row infeasible under the tiers is solved with the fewest tiers
     dropped (non-QB from the lowest r upward, then QB), recorded per row and reported by the census. Spare rows never
     relax. The reference (no tiers) is one plain solve, unchanged.
- **The smoke** (2023 W1, 1406, the full path, at the frozen code): the census and the reader exited 0; the reader
  printed its 2 headers and its header names STUDY 37 (tested). It REFUSES mechanics-only rows (exit 1, "a non-scored
  (mechanics) row is in the scored file").
- **Code:** nfl2 `production/s37-structure-20261006` @ `35aea10` (the records at `7394b32`):
  - `experiments/s37_regulars_structure.py`, sha256 `29a2c2c72b86f1b5eec6072119482cafa462218272c6c90f2e9aa2c95778acbf`;
  - `scripts/s37_drive.py`, `a39fd472a806686767d1c08e63c86cfcf09488c901837036cf1c002d57458e1c`;
  - **`scripts/s37_report.py` (the reader), sha256 `2b1058dee6e648e48a1af034403705174c6460ca6b067ad2a32f385f0d9f9192`**;
  - `scripts/s37_census.py`, `9499ea9b9647a6b2469362c94d62d10ec1fafdc8f078e54bc81322936bc2e656`;
  - `scripts/s37_regulars_tiers.py` (the design input), `a03d57049d93f2980d0fb5876c60cc5e67c100f6caf815aa4bf8116f55bb4fa3`;
  - `tests/test_s37_regulars_structure.py`, `d133e093c1d91082bb839461a1ffdd2c703a177748838c7a99170805d76c7f09` (7 tests).
- **Production lever if adopted:** none exists. QB and non-QB tier caps (with the loud fallback) need new
  `union_reselect` code, a parity test against this harness, and a rehearsal.
- **Banks:** 1467–1472. **Seed:** 20261019.
- **Order:**
  1. this freeze;
  2. the laptop's ack of the binding census;
  3. the scored run;
  4. the confirmatory census, committed before the read;
  5. the read;
  6. the laptop's re-run;
  7. the LEDGER row and Addendum 142.
- **Transfer:** our projections (the live build uses FP's), the term's stand-in, the Millionaire ownership field, and
  the regulars' tiers measured on four 2026 weeks.
