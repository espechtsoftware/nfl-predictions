# Preregistration: study 117b, the go / no-go for study 117's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 117 is read)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, committed and pushed **before study
117's READ**. The lab reviewer freezes it after study 117's READ; the laptop acks. **Information for his decision (Week 6).**

## 1. Why
- Study 117 (`reports/2026-10-10-prereg-study117-two-stars.md`) picks at most ONE of two arms by his rule. Picking the larger
  of two gains on the same slates flatters the pick (the winner's curse); a fresh draw is the check.
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes. Study 117b checks the opponent and simulation
  draw and the winner's curse, **not new outcomes — not out-of-sample.** Study 38's paper arms on Week 5's real results
  (STAR2_8, and STAR2 where it fits) are the out-of-sample read.

## 2. The design (no new code)
- **Code: study 117's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s117-two-stars-20261010`;
  the shas as frozen in study 117); new banks. The reader prints all of study 117's lines; **ONLY the pick's line vs LIVE
  decides.**
- **Banks (the laptop's reservation; the full-set check: CLEAN):** **4352–4363** (set A 4352–4357, set B 4358–4363; sims bases
  4402–4413, fields 5052–5063).
- **The reader's seed** is study 117's (20261165): the same bootstrap resamples, so the intervals are correlated with 117's.
  The pass rule below uses point estimates only.
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - **Pass** → "held on a fresh draw of the same slates": a candidate for his Week-6 arm with the default-off switch, its tests,
    the Week-4 check and study 38's classification; read beside Week 5's paper arms. His decision.
  - **Fail** → "did not hold" (not suggested).
- **If study 117 picks nothing, study 117b is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 117's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
