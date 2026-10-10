# Preregistration: study 103, the go / no-go for study 102's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-09, committed BEFORE study 102 is read)

**Status: DRAFT 2026-10-09** (the times are this file's commits) by the outside reviewer, committed and pushed **before study
102's READ** (the lab reviewer's condition). The lab reviewer freezes it after study 102's READ; the laptop acks. **Information
for his morning decision.**

## 1. Why
- Study 102 (`reports/2026-10-09-prereg-study102-ceiling-build.md`) picks at most ONE of three ceiling constructions by a
  pre-stated rule on the book's best real lineup. Picking the largest of three gains on the same slates flatters the pick (the
  winner's curse); a fresh draw is the check.
- **Honest limit, plainly:** the armed construction needs 2023–24's ownership predictions, so no other slates exist; fresh banks
  re-use the SAME 36 slates' real outcomes. Study 103 checks the opponent and simulation draw and the winner's curse, **not new
  outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 102's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s102-ceiling-build-20261009`;
  the shas as frozen in study 102); new banks. The reader prints all of study 102's lines; ONLY the pick's line decides.
- **Banks (the laptop's full-set check: clean against every used bank, studies 100–102 included):** **3396–3407** (set A
  3396–3401, set B 3402–3407; sims bases 3446–3457, fields 4096–4107). The reader's bootstrap seed is study 102's (20261146):
  the same resamples, so the intervals are correlated with 102's; the pass rule below uses point estimates only.
- **THE PASS RULE (fixed now; the lab reviewer's guarded rule):** the pick − LIVE is
  - **> 0 on both draws for the mean best real lineup points**, AND
  - **P(≥ 1 big seat) not worse on both draws**, AND
  - **the pooled expected big seats ratio ≥ 0.80**

  — i.e. the frozen reader's pick-rule line prints the pick ELIGIBLE again on the new banks. Pass → the morning page suggests the
  pick as "held on a fresh draw"; fail → "did not hold" (not suggested). Every other line is information only.
- **If study 102 picks nothing, study 103 is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 102's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
