# Preregistration: study 113, the go / no-go for study 112's usage floor — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 112 is read)

**Status: NOT RUN (2026-10-10): its condition failed — study 112 (READ_s112.txt `2525ef14`, lab `a4fd70e9`) picked nothing.
Every floor was worse than LIVE on P(≥ 1 big seat) on both draws: RUSH 13 −0.04576 [−0.09343, −0.00360] (A −0.05152, B
−0.04001; seats 0.890; guard 1 fails), PASS 32 −0.02741 (A −0.04098, B −0.01383; seats 0.888; guard 1 fails), TGT 4.5
−0.02753 (A −0.04497, B −0.01009; seats 0.931; guard 1 fails); "PICK: none -- keep the live book". Its banks stay unused.
Recorded under the design fixed before study 112's READ.** Earlier status: DRAFT 2026-10-10 (the times are this file's
commits) by the outside reviewer, committed and pushed **before study 112's READ**. The lab reviewer freezes it after study 112's READ; the laptop acks. **Information for his decision.**

## 1. Why
- Study 112 (`reports/2026-10-10-prereg-study112-usage-floors.md`) picks at most ONE of three usage floors by his rule (TD and
  RZ were dropped before its freeze). Picking the largest of three gains on the same slates flatters the pick (the winner's curse); a fresh draw is the check (studies 98, 101
  and 103 failed it overnight; 99 passed).
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes. Study 113 checks the opponent and simulation
  draw and the winner's curse, **not new outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 112's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s112-usage-floors-20261010`;
  the shas and thresholds as frozen in study 112); new banks. The reader prints all of study 112's lines; **ONLY the pick's line
  vs LIVE decides.**
- **Banks (the laptop's reservation, full-set clean):** **3616–3627** (set A 3616–3621, set B 3622–3627; sims bases 3666–3677,
  fields 4316–4327).
- **The reader's seed** is study 112's (20261155): the same bootstrap resamples, so the intervals are correlated with 112's. The
  pass rule below uses point estimates only. (The laptop reserved 20261156; the frozen reader's own seed is kept, as in studies
  99, 101, 103, 107 and 111.)
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - Pass → the floor "held on a fresh draw": information for Week 6, with the production pool filter named in study 112 §5.
  - Fail → "did not hold" (not suggested).
- **If study 112 picks nothing, study 113 is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 112's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
