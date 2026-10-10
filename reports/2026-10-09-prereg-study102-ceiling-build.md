# Preregistration: study 102, ceiling construction — three ways of building his live book for a higher best lineup, read on the book's best real lineup, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09** (the times are this file's commits) by the outside reviewer. **Version (b): the outside reviewer's
mechanics** (the lab reviewer, 10-09: "Build WHICHEVER version you have already started ... Just state in the prereg which one
it is"): p85 + the cheap term; the top-4 games; MAX_PER_GAME 5 on the A1 full-stack solves only (approved by the lab reviewer).
The code is done (12 tests); the tests and the smoke wait for a machine gap. The lab reviewer reviews, runs the binding census and
FREEZES; the laptop acks. **Information for his morning decision; a pick goes to study 103, whose preregistration is committed
before this study's READ.**
- **Banks and seed (the laptop's full-set check: clean against every used bank, studies 100 / 101 included):** **3384–3395**
  (set A 3384–3389, set B 3390–3395; sims bases 3434–3445, fields 4084–4095); the reader's bootstrap seed 20261146.
  **The laptop's text scan: CLEAN** (every context hit is this study's own files, shas, an l03 timing, or the 09-19 evidence
  files' "inactive" counts under letter-labelled banks).

## 1. Why
- **The operator, 10-09 evening, in the laptop's session (HANDOFF `f68ebf50`, verbatim):** "...if you're not seeing really good
  scores when you run your mix, keep trying different variations of it. You know, my hope is that we can get to a point where
  you're, you're seeing scores, you know, over 200 fairly regularly. So do what you can." **And later (HANDOFF `f07f4c13`):**
  "It sounds like you're giving up on the high scores. That's not what I want."
- **Study 100** (`reports/2026-10-09-prereg-study100-ceiling.md`) tests five existing switches on the ceiling. **Study 102 tests
  new constructions aimed at the ceiling itself**: the objective (a player's upside, not his mean) and the shape (the full game
  stack).
- **What the real 200+ lineups look like** (the laptop, `reports/2026-10-09-real-field-200-profile/`, `76f42798`; his W1–4
  fields, aggregates only): two or more players from the QB's OPPONENT in **18.5%** of the 23,610 lineups that scored 200+ (the
  field 7.7%); 5+ from one game in 19.0% (the field 7.1%); **his real entries had two or more opponents in 1.9%.**
  - **Its caveats, plainly:** it conditions on the outcome (200+ lineups concentrate in the games that went off, so this is
    what a 200+ lineup looks like AFTER the fact); W1, a high-scoring week, supplies 22,520 of the 23,610; in the low-scoring
    W2 / W4 the top 1% had two or more opponents in only 3.7% / 7.2%. It suggests a sleeve, not a whole book, and only a
    build-before-the-fact test (TAIL_STACK8 here) can say whether building the shape helps.
- **The prior, stated first:**
  - **The p85 arms: NEGATIVE.** Every player-upside objective read so far was negative: Addendum 2's p90; PREREG-006 / 010's
    q97 / q98.75; study 26's P90 (Addendum 132: −2.7 points on P(≥ 1 big seat), expected seats 0.82×). The differences here:
    p85, not p90; his live construction (ONECATCH, the cheap block, the ownership cap); read on the ceiling.
  - **TAIL_STACK8: NO DIFFERENCE.** Study 26's whole-book shootout (QB + 3 + a bring-back, MAX_PER_GAME 5) read NO DIFFERENCE
    with a ceiling signal (weeks with a 200+ lineup 7.5% → 10.4%, expected seats +15%); study 74's full game stack (QB + his
    top catcher + the opponent's top receiver, the top-4 games; Addendum 172) read NO DIFFERENCE, leaning −2.9. Here: the A1
    rows only (8 of 26) and two opponents.

## 2. Arms (`experiments/s102_ceiling_build.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with nine
listed edits, a test asserts it); every arm his live Week-5 construction (the package + te1 / low1 + ONECATCH through 93's
`lead_rules`, 89's `own_caps`; QB cap 5, overlap 4, the cheap +2 block on 8 rows, the ownership cap + 15, A1 .30 / A2 .14 /
B .28 / C .28), **one setting changed** (a test asserts exactly one):
- **LIVE** — as live: every row on each player's simulated mean; the 8 cheap-block rows on the mean + the cheap +2 term.
- **CEIL_BLOCK8** — the 8 cheap-block rows on each player's simulated **p85** (the 85th percentile of the SAME 20,000 draws
  whose mean LIVE uses) + the cheap +2 term; the other 18 rows and the spares unchanged.
- **CEIL_ALL** — every row on p85: the 18 live rows and the spares on p85, the block on p85 + the cheap term.
- **TAIL_STACK8** — every A1 book solve (the QB + 2 + a bring-back cell; 8 of the 26 rows, the cheap block's A1 rows included)
  is a **FULL GAME STACK**: the QB + ≥ 2 of his WR / TE + **≥ 2 opponent RB / WR / TE** (`bring_back_min` 2), **MAX_PER_GAME 5
  on those solves only** (study 26's; the other cells keep 4), and **the QB's game among the slate's top-4 pre-lock game totals**
  (study 73's `game_order`; the other QBs banned on those solves). It is entered before 93's `lead_rules`, so a solve that cannot
  be built drops the full stack first: [row rules + full stack] → [row rules] → [full stack] → neither. The full stack, the
  5-per-game allowance and the game bans drop together, and the solve is recorded as ruled or plain. Spares never.
- **Earliest use:** none of the three is an existing production switch. A pick that holds in study 103 needs a production flag
  with a byte-for-byte parity test before it can be armed. **Week 5 only if that is built, tested and he says yes on Saturday;
  otherwise Week 6.**

## 3. The read (the reader `scripts/s102_report.py`)
- **Study 100's reader** with the arms, the seed and the labels changed (a test asserts the exact edits); study 95's statistics
  (63's, a test asserts them); two draws and pooled; two-sided 0.95, B 20,000.
- **THE PICK STATISTIC (unchanged from study 100):** the mean, per slate, of the **book's best real lineup points** (the max of
  its 26 rows' real DK points), each arm − LIVE, pooled with its interval and on both draws; **P(best ≥ 200)** printed beside it.
  P(≥ 1 big seat), its guards and verdict as before.
- **THE PICK RULE (unchanged from study 100; the same tested function `pick_rule`, a test asserts it is byte-identical):** among
  the three arms, the **largest pooled gain in mean best points** that is ALSO **> 0 on both draws**, AND **P(≥ 1 big seat) not
  worse on both draws**, AND the pooled **seats ratio ≥ 0.80**. None → **"keep the live book"**.
- **MULTIPLICITY, plainly:** three arms on the same 36 slates as studies 89–101; about one passes by chance. A pick is a candidate
  for study 103, never proof.

## 4. What the harness can and cannot say
- **The census reports, per arm,** the book rows per cell, the QB cap / overlap / cheap-block checks, the re-solves,
  ONECATCH's ruled / dropped and the vacuity against LIVE. **The binding lines:**
  - the size of the change: p85 − mean per skill player (points);
  - the A1 book rows that are full game stacks, and those whose QB's game is in the top 4;
  - the book rows with 5+ players from one game;
  - TAIL_STACK8's full-stack solves ruled vs re-solved plain (more than 5% plain is reported to the lab reviewer before the
    freeze).
- **The transfer caveat:** the harness builds on simulator means and percentiles; his book builds on Fantasy Points'
  projections. A p85 in production needs a distribution around FP's projection (production's own simulations or FP's ceiling),
  a different number, decided before any arming. TAIL_STACK8's shape transfers directly; the top-4 games use the pre-lock
  totals production already has.

## 5. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The smoke:** (a machine gap the lab reviewer names; filled in when it ends).
- **Code:** nfl2 `production/s102-ceiling-build-20261009` @ `4bdfafd4` (branched from study 100's `635b64eb`):
  `experiments/s102_ceiling_build.py` `71474b60…` (pins s95 `46b80611…`); `scripts/s102_drive.py` `7ac2fefc…`;
  `scripts/s102_census.py` `78c62d88…`; **`scripts/s102_report.py` (the reader) `581dabd9…`** (seed 20261146);
  `tests/test_s102_ceiling_build.py` `85811965…` (12).
