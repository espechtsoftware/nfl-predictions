# Preregistration: study 109b, the go / no-go for study 109's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 109 is read)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, at the lab reviewer's request, committed
and pushed **before study 109's READ**. The lab reviewer freezes it after study 109's READ; the laptop acks. **Information for
his decision.**

## 1. Why
- Study 109 (`reports/2026-10-10-prereg-study109-recency-fade.md`) picks at most ONE of three arms (FADE2, FADE2_16, HOT1) by his
  rule. Picking the largest of three gains on the same slates flatters the pick (the winner's curse). A fresh draw is the check:
  studies 98, 101 and 103 failed it overnight; 99 passed.
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes. Study 109b checks the opponent and simulation
  draw and the winner's curse, **not new outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 109's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s109-recency-fade-20261010`;
  the shas as frozen in study 109); new banks. The reader prints all of study 109's lines; **ONLY the pick's line vs LIVE
  decides.**
- **Banks:** the laptop's reservation, with its full-set check and text scan, recorded here before the freeze.
- **The reader's seed** is study 109's (20261151): the same bootstrap resamples, so the intervals are correlated with 109's. The
  pass rule below uses point estimates only (the frozen reader's own seed is kept, as in studies 99, 101, 103, 107, 111 and
  113).
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - **Pass, HOT1** → "held on a fresh draw". HOT1 has a production path: one more entry in `row_rule_sets`, carried into the
    solver's member bounds like te1 / low1. Before any arming it needs that default-off switch to the study's definition, tests,
    the Week-4 check and study 38's classification. If all of that is done before his 18:00 final arm, it is a candidate for it;
    otherwise for Week 6.
  - **Pass, FADE2 or FADE2_16** → "held on a fresh draw": information for Week 6. There is no production switch for a projection
    fade (the term-block vehicle keeps only positive terms), so it needs that change first.
  - **Fail** → "did not hold" (not suggested).
- **If study 109 picks nothing, study 109b is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 109's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
