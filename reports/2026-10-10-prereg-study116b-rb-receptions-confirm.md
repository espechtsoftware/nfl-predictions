# Preregistration: study 116b, the go / no-go for study 116's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 116 is read)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, committed and pushed **before study
116's READ**. The lab reviewer freezes it after study 116's READ; the laptop acks. **Information for his decision.**

## 1. Why
- Study 116 (`reports/2026-10-10-prereg-study116-rb-receptions.md`) picks at most ONE of two doses by his rule. Picking the
  larger of two gains on the same slates flatters the pick (the winner's curse); a fresh draw is the check.
- **Honest limit, plainly, twice over:** fresh banks re-use the SAME 36 slates' real outcomes, so study 116b checks the
  opponent and simulation draw and the winner's curse, **not new outcomes**. And study 116's idea came from those same slates'
  outcomes (study 116 §1), so **even a pass here is "consistent with the idea on the same slates", not out-of-sample.**

## 2. The design (no new code)
- **Code: study 116's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s116-rec-floor-20261010`;
  the shas and thresholds as frozen in study 116); new banks. The reader prints all of study 116's lines; **ONLY the pick's line
  vs LIVE decides.**
- **Banks (the laptop's reservation; the full-set check: CLEAN):** **4108–4119** (set A 4108–4113, set B 4114–4119; sims bases
  4158–4169, fields 4808–4819).
- **The reader's seed** is study 116's (20261161): the same bootstrap resamples, so the intervals are correlated with 116's. The
  pass rule below uses point estimates only. (The laptop reserved seed 20261163 for this study; it stays unused, because the
  frozen reader's own seed is kept, as in studies 99, 101, 103, 107, 109b, 111, 113, 114b and 115b.)
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - **Pass** → "held on a fresh draw of the same slates": put to him as in-sample harness evidence, with the study 38 paper arm
    on Week 5's real results as the recommended route. Production has no receptions floor (a default-off switch, its tests,
    the Week-4 check and study 38's classification would be needed); arming is his decision.
  - **Fail** → "did not hold" (not suggested).
- **If study 116 picks nothing, study 116b is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 116's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
