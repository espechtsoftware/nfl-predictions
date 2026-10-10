# Preregistration: study 114b, the go / no-go for study 114's suggested removal — the removal vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 114 is read)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, committed and pushed **before study
114's READ**. The lab reviewer freezes it after study 114's READ; the laptop acks. **Information for his decision.**

## 1. Why
- Study 114 (`reports/2026-10-10-prereg-study114-remove-one-rule.md`) suggests at most ONE of six removals by his rule. With six,
  one or two false passes are expected, and the largest gain is flattered by the choice (the winner's curse). A fresh draw is the
  check: studies 98, 101 and 103 failed it overnight; 99 passed.
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes. Study 114b checks the opponent and simulation
  draw and the winner's curse, **not new outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 114's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s114-remove-one-20261010`;
  the shas as frozen in study 114); new banks. The reader prints all of study 114's lines; **ONLY the suggested removal's line
  vs LIVE decides.**
- **Banks:** the laptop's reservation, with its full-set check and text scan, recorded here before the freeze.
- **The reader's seed** is study 114's (20261157): the same bootstrap resamples, so the intervals are correlated with 114's. The
  pass rule below uses point estimates only (the frozen reader's own seed is kept, as in studies 99, 101, 103, 107, 109b, 111 and
  113).
- **THE PASS RULE (fixed now):** NO_x − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - **Pass, NO_CHEAP or NO_FAVHI** → "the removal held on a fresh draw": a candidate for his 18:00 final arm (`TERM_ROWS=0` or
    `RB_MATE_C=0`; both armable as they stand), after the Week-4 check and study 38's classification.
  - **Pass, any other removal** → "held": information for Week 6. It needs decoupled wiring in the arm script first (study 114
    §5).
  - **Fail** → "did not hold": every live rule stays.
- **If study 114 suggests nothing, study 114b is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 114's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
