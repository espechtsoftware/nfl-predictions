# Preregistration: study 26, ceiling by correlation (a one-game shootout build) against the house shape, on the operator's goal (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** (morning CDT), after the smokes (§2a) and the laptop's design review, before the binding
census and any scored bank. The reviewer froze it and reads first. The laptop acks the census and re-runs the frozen
reader before the LEDGER row.

**The operator (10-06, verbatim):** "I would rather see around the clock efforts to try different strategies of
selecting boom players, sorting, testing usage of route share data etc with the intent to use the best system available
this week".

## 1. Why this, and not the other "boom" ideas
The ledger sweep (10-06) found the player-upside routes tested and closed at deep lines:
- a p90 lineup objective was REJECTED (system study Addendum 2);
- q97 and q98.75 objectives were HARMFUL (PREREG-006 / 010);
- the finish objective was NEGATIVE, decisively (PREREG-098);
- simulated P(≥ line) selection was negative (L14);
- the P(30+) ceiling model was negative (09-22);
- sorting by simulated tail never beat random (09-22 sort-key study; Addendum 62/65).

Our simulations overstate the far tail (studies 24 / 18b: simulated P(≥ 1 big) ≈ 0.50 vs realized ≈ 0.26), which
explains why tail-sorted selection fails.

Never tested at deep lines: building MORE correlation.
- **Studies 24 and 18b both pointed this way:** spreading the QB games lowered the ceiling, and the house shape kept the
  higher ceiling against WS.
- **L10** (CAP5, QB+3 buildable) was read only at the p89 ticket line: −1.6%, no gain.
- **The field data:** in the 2026 W1–3 Millionaires, QB+3 and 5-from-one-game lineups reached the top 10% more often
  than QB+2 / 4-per-game ones (the laptop's 09-27 critique, §3d):
  - QB+3 lift 2.23 / 1.44 / 2.46, against QB+2 1.32 / 1.30 / 1.51;
  - 5-from-one-game 1.91 / 1.08 / 2.10, against 4-per-game 1.21 / 1.18 / 1.26.

  This is a descriptive FIELD lift: who builds QB+3 is not random, so it is not a causal estimate.
- **L10's exact scope** (`reports/2026-09-28-laptop-l10-result.md`): CAP5 = QB+3 ALLOWED, not required. tickets89 1,035
  vs CAP4 1,052 (−1.6%); tickets95 499 vs 507; only 2.1% of its rows were QB+3 (35.6% five-from-one-game). So C5 may be
  near a dead lever. SH, QB+3 REQUIRED, is untested.

## 2. Arms (one co-run per slate-bank)
Study 18b's harness unchanged:
- the plain simulated mean over the dual-law worlds (unless an arm says otherwise); no ownership term;
- ≤ 7 shared with every earlier row; a $49k floor; skill players with simulated mean < 1.0 dropped;
- production's main caps for the head layout's K (Rev2: K 22, so a player 11 rows and a DST 5);
- build depth 40; the head layout; the small-contest overlap limit M 5 / ceiling 10.

The arms:
- **C (reference):** `PRODUCTION_STACK` (QB + 2 WR/TE, ≥ 1 bring-back), MAX_PER_GAME 4. Today's main construction.
  Production's caps for the FINAL plan's head K = 22: a player 11 rows, a DST 5.
- **SH (DECISION, vs C): the shootout.** QB + ≥ 3 WR/TE, ≥ 1 bring-back, MAX_PER_GAME 5: five from the QB's game.
- **C5 (EXPLORATORY, vs C):** the house rules with MAX_PER_GAME 5 (L10's CAP5: the shootout allowed, not required).
- **P90 (EXPLORATORY, vs C):** the house shape with each player's simulated 90th percentile as the objective. This is
  the operator's "boom players", tested because he asked; **the prior is negative** (§1).

## 2a. Smoke observations before the freeze (2023 W9, throwaway bank 1406)
- **Smoke 1 (the Rev1 plan, mechanics plus the full path, reader exit-checked).**
  - SH: QB+3 and five from one game on every entry.
  - C5: identical to C (the mean optimum never takes the fifth player).
  - P90: house-shaped.
- **Smoke 2 (the FINAL Rev2 plan, with pins).**
  - Caps 11 / 5.
  - SH: QB+3 1.000, five from one game 1.000, exactly 5 in the QB's game on every entry.
  - The pins hold: the 27 pinned entries reuse rows 1–5, so the top player's entry share is 0.79 in every arm, by the
    operator's rule.
- **DISCLOSURE (a procedural slip, recorded in full).** Smoke 2's exit-code check used a grep pattern ("slates") that
  also matched the reader's secondaries lines. It therefore printed the realized secondaries of the ONE smoke slate
  (2023 W9) on the throwaway bank 1406 to the reviewer.
  - On that slate SH's finishes were higher than C's.
  - The design (SH as the decision arm, C5 and P90 exploratory, the rule of §4) was fixed in the draft BEFORE it
    (`216a1e8e`, `b1469a7`) and is unchanged by it. The only edits after it are this disclosure, the citations the
    laptop's review asked for, and the caps and checks below.
  - The scored banks 1421/1422 use other simulation and field seeds over all 53 slates. One slate of 53 is not the
    read.
- **Binding-census checks before the scored run** (the laptop's review):
  - SH's QB+3 share and five-from-one-game share = 1.000 on every slate-bank, and exactly 5 in the QB's game;
  - no short books in any arm (the SH trios burn the 11-row player cap fast);
  - SH's top player's entry share reported;
  - C5's QB+3 and five-from-one-game shares and its identical-to-C rate reported (C5 > 80% identical = DEAD LEVER, no
    verdict).

## 3. Panel and plan
- **Slates:** the 53 `k1` slates of 2022–24 with Millionaire ownership.
- **Banks:** **fresh 1421/1422** (no use in either repository's branch scan, 10-06). The smoke and the binding census
  are on 1406.
- **Plan:** the operator's FINAL Rev2 Week-5 plan (`~/s24-panel/plan-week5-rev2-s24.json`, sha256
  `00c660045e2917082d4e6515da7cd4388730c13e96e6d49cd42e647ae0ce7d08`; 29 contests, 53 entries).
  - The 26 Milly super-satellite entries and the $125 FFWC satellite are PINNED to his top lineups (rows 1–5), by his
    rule (10-06, verbatim): "For those, I only want to reuse my top lineups that I'm using elsewhere"; "the 125 WFFC one
    doesn't [count] and it should reuse an entry".
  - 26 entries in big contests, including the three Midseason Warm Up satellites ("the midseason ones count as big
    wins").
  - The head layout needs 22 rows.
- **Field caveat (as in studies 24 / 18b):** the opponents are modelled Millionaire-style draws, so absolute
  probabilities are optimistic. The differences decide.

## 4. Endpoints and decision rule (study 18b's, unchanged)
- **PRIMARY:** P(≥ 1 big seat) per slate, SH − C, paired. Season-clustered bootstrap, B 20,000, seed 20261008.
  **Two-sided 0.95.**
- **GUARD 1:** mean entry finish; the one-sided 0.95 lower bound > −0.015.
- **GUARD 2:** expected big seats ratio ≥ 0.80 (the operator's tolerance).
- **Verdicts:**
  - **PASS** = lower bound > 0, at most one season mean < 0, and both guards hold;
  - **WORSE** = upper bound < 0;
  - **FAIL (guard)** = the primary would pass but a guard fails;
  - **DEAD LEVER** = identical to C on > 80% of slate-banks;
  - **NO DIFFERENCE** otherwise.
- **Secondaries:** as study 18b's, plus the share of dealt entries with five from one game and with QB+3. For P90 (the
  operator's "boom" question), its best ≥ 200 is printed beside C's.

## 5. What a verdict can do
- **SH PASS:** a reason to offer the shootout this week. The production port (the laptop's notes, only if it passes):
  - MAX_PER_GAME 5 for the MAIN book only. The union's `--max-per-game` also filters the candidate pool, and the audit
    expects 4 on every candidate, so it needs a main-only cap or a per-row-type audit;
  - an SH cell in `mix_shapes`, with in-shape Sunday spares as for WS, or a stated acceptance of QB+2 replacements.

  The operator decides.
- **NO DIFFERENCE:** today's shape stands. Stated plainly.
- **WORSE:** the shootout is not offered.

## 6. Integrity
- **Code:** nfl2 `production/s26-boom-objective-20261006` @ `85d9f40`:
  - `experiments/s26_shootout.py`, sha256 `c2c7d5d829eb4f56eb4509377692f70050df1292bd0540ee58353ff370aee09e`;
  - `scripts/s26_drive.py`, `cdbd186e7487b098ca868bebbecabfe13687aefd01930286fef1136abb64b861`;
  - **`scripts/s26_report.py` (the reader), sha256
    `86b3abb2c59a6ac5c88a894541af6e82e6174b445d43bad08b18d54a0c57e8c8`**;
  - `scripts/s26_census.py`, `90db502d8374dfe5d854f26634611bac54940b0449a7657bfddb21898d3ff93f`;
  - `tests/test_s26_shootout.py`, `eb272b548da0b68618970f99d28ede383111459023cc568488b348ecaf88df77` (7 tests; 32 green
    with studies 18b and 24).
- **Order:** this freeze → the binding census on 1406 (the laptop's ack) → the scored run on **1421/1422** → a
  confirmatory census before the reader → the reviewer's read → the laptop's byte-identical re-run → LEDGER and
  Addendum.

## Deviation note 1 (2026-10-06, after the scored run on 1421/1422 STARTED and BEFORE any of its outcome is read)
**The operator, through the laptop (verbatim):** "I'm not wild about the bigger one-game stack. If that is adopted, I
would only want to use it a very small percentage. We know that milly winners use fewer players than that".
- **The record agrees with him:**
  - stack depth 3+ appeared in 2% of 69 historical winners
    (`reports/2026-09-22-production-response-to-winner-anatomy-review.md`, which dropped QB+3);
  - the regulars build QB+2 about 42% of the time.

  The 09-27 field lift (QB+3 reaching the top 10% 1.4–2.5× as often) is a descriptive top-10% lift, not a winners'
  rate.
- **What changes:** NOTHING in the frozen design, reader or rule. The scored run was already under way, so adding a
  sleeve arm now is not clean.
- **What the verdict can do (replacing §5's SH PASS line):**
  - SH as a WHOLE BOOK is OFF the table by the operator's choice, whatever the read. The read answers only whether the
    shootout SHAPE helps or hurts his chance of a big win on his plan.
  - A PASS or NO DIFFERENCE does NOT license a small-share sleeve (the post-selection law: a verdict does not transfer
    to a changed downstream mix). Any sleeve use needs its own study, e.g. about 10% of rows as SH and the rest house.
    That study is offered only if SH is not WORSE.
  - WORSE closes the shootout for Week 5.
- **Power note for any sleeve study:** a 2-of-22-row sleeve moves P(≥ 1 big seat) very little. On 53 slates it would
  likely read NO DIFFERENCE, and that would be said in advance.
