# Preregistration: study 107, the go / no-go for study 106's floor — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 106 is read)

**Status: NOT RUN (2026-10-10): its condition failed — study 106 (READ_s106.txt `0a75e37c`, lab `960c320c`) picked nothing:
MINPROJ8 − LIVE on P(≥ 1 big seat) −0.02684 [−0.07677, +0.02040], worse on both draws (A −0.02652, B −0.02716), expected big
seats ×0.882, guard 1 fails (lower −0.01639); "PICK: none -- keep the live book". Its banks stay unused. Study 108 (his
per-position floors, study-list row 89's second step) was conditional on a floor holding here, so it is NOT RUN either and
was never drafted. Recorded under the design fixed before study 106's READ.** Earlier status: DRAFT 2026-10-10 (the times are
this file's commits) by the outside reviewer, committed and pushed **before study 106's READ**. The lab reviewer freezes it after study 106's READ; the laptop acks. **Information for his decision.**

## 1. Why
- Study 106 (`reports/2026-10-10-prereg-study106-min-proj.md`) reads ONE projection floor (MINPROJ8; study 106's pre-freeze
  changes 2 and 3) against LIVE by his rule: one comparison, not the largest of three. A single pass on the same slates still
  needs the draw check (studies 98, 101 and 103 failed it overnight; 99 passed).
- **Correction (2026-10-10, before study 106's READ):** this paragraph first said "picks at most ONE of three projection floors";
  study 106 was cut to one floor before its freeze.
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes; study 107 checks the opponent and
  simulation draw and the winner's curse, **not new outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 106's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s106-min-proj-20261010`; the
  shas as frozen in study 106); new banks. The reader prints all of study 106's lines; **ONLY the pick's line vs LIVE decides.**
- **Banks (the laptop's full-set check and text scan: CLEAN; the only real mention this file):** **3494–3505** (set A 3494–3499, set B 3500–3505; sims
  bases 3544–3555, fields 4194–4205). The reader's bootstrap seed is study 106's (20261149), the same resamples, so the intervals
  are correlated with 106's; the pass rule below uses point estimates only.
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed). Pass → the floor "held on a fresh draw": one existing setting
  (`LIVE_MIN_PROJ`, which floors Fantasy Points' projection in Week 5; study 106 §4). Fail → "did not hold" (not suggested).
  (Corrected before study 106's READ: this line first named a production change; none is needed.)
- **If study 106 picks nothing, study 107 is not run** (recorded).
- **Disclosure (2026-10-10, still before study 106's READ):** study 106's arms were changed before its freeze to carry the
  operator's adopted RBMATE4_FAVHI in every arm (study 106 §2); study 107 re-runs study 106's frozen code, so it inherits that
  book: the pick vs LIVE is read on his armed Week-5 book.
- **His per-position floors** ("try different min projections per position") are study 108: only if study 106 picks and study
  107 holds, its levels from study 106's outcome-blind census so that each binds, its design committed before it runs.

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 106's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
