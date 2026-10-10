# Preregistration: study 103, the go / no-go for study 102's pick — the pick vs LIVE on a fresh draw of the same slates (FROZEN 2026-10-10; the DRAFT committed BEFORE study 102 was read)

**Status: FROZEN 2026-10-10 (03:31 CDT)** by the lab reviewer, after study 102's READ (the DRAFT, committed before that READ, fixed
the design, the banks and the pass rule; the freeze adds the pick and the census), before any scored bank of study 103. The text
changed at the freeze in this status block and §3 (the census) only. The laptop acks. **Information for his morning decision.**
- **Study 102's pick rule picked CEIL_BLOCK8** (READ `3a992f7f`, lab `2ec19654`; the confirmatory census `a5ac454c` committed before it):
  mean best real lineup points +0.195 (set A +0.359, set B +0.031); P(≥ 1 big seat) A +0.00110, B −0.00961 (not worse on both);
  seats 0.967. **The deciding line of study 103 is CEIL_BLOCK8 − LIVE; PASS iff the frozen reader's pick-rule line prints
  CEIL_BLOCK8 ELIGIBLE again on the new banks** (the mean best points > 0 on both draws, AND P(≥ 1 big seat) not worse on both
  draws, AND the pooled seats ratio ≥ 0.80), as §2 fixed; the reader's own "PICK:" line and every other line are information.
- **Banks 3396–3407** (set A 3396–3401, set B 3402–3407; sims bases 3446–3457, fields 4096–4107), as §2 fixed; study 102's
  reader, seed 20261146 (the disclosure in §2). The laptop's scan was clean: the full set against every used bank's {b, b + 50, b + 700} (studies 90–102 included), no season
  years, no results file; the text scans found only study 102's and this study's own preregs and tests, shas, timings, and
  letter-labelled "bank" fields with inactive-player counts in 09-19 review evidence (incidental).
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run, recorded in `RUN_ENV_s103.txt` committed with the
  confirmatory census. The run starts from lab `13eb1323` (study 102's READ commit `2ec19654` plus this census; the code is
  102's `969f4d3d`, unchanged), on lab branch production/s103-confirm-102-20261010 (results/s103/).

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
  **The laptop's text scan: CLEAN** (the same context hits as study 102's).
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
- **The mechanics census at the freeze** (the lab reviewer's; outcome-blind; bank 1406; study 102's frozen code at its READ commit
  `2ec19654`; PYTHONHASHSEED=0; 12 tests pass; lab `13eb1323` on production/s103-confirm-102-20261010: `CENSUS_s103_binding.txt`
  `41cc2daa…`, `census_mechanics_bank1406.jsonl` `a1590beb…`): **identical to study 102's binding census** (lab `7b65f1c8`) -- the
  census text with the build time masked, and all 36 mechanics rows apart from the timing fields and the code-sha field.
