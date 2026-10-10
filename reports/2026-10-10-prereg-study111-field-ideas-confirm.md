# Preregistration: study 111, the go / no-go for study 110's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 110 is read)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, committed and pushed **before study
110's READ**. The lab reviewer freezes it after study 110's READ; the laptop acks. **Information for his decision.**

## 1. Why
- Study 110 (`reports/2026-10-10-prereg-study110-field-ideas.md`) picks at most ONE of five rules by his rule. Picking the largest
  of five gains on the same slates flatters the pick (the winner's curse). A fresh draw is the check: studies 98, 101 and 103
  failed it overnight; 99 passed.
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes. Study 111 checks the opponent and simulation
  draw and the winner's curse, **not new outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 110's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s110-field-ideas-20261010`;
  the shas as frozen in study 110); new banks. The reader prints all of study 110's lines; **ONLY the pick's line vs LIVE
  decides.**
- **Banks (the laptop's full-set check: CLEAN; the text scan of both repositories: CLEAN, 10-10):** **3592–3603** (set A 3592–3597, set B 3598–3603; sims
  bases 3642–3653, fields 4292–4303).
- **The reader's seed** is study 110's (20261153): the same bootstrap resamples, so the intervals are correlated with 110's. The
  pass rule below uses point estimates only. (The laptop reserved seed 20261154 for this study; the frozen reader's own seed is
  kept, as in studies 99, 101, 103 and 107.)
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - Pass → the rule "held on a fresh draw": a candidate for his 18:00 final arm if its production switch is built, checked on his
    Week-4 book and classified by study 38 in time; otherwise for Week 6.
  - Fail → "did not hold" (not suggested).
- **If study 110 picks nothing, study 111 is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 110's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
