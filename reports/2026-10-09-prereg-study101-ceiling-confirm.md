# Preregistration: study 101, the go / no-go for study 100's pick — the pick vs LIVE on a fresh draw of the same slates (FROZEN 2026-10-10; the DRAFT committed BEFORE study 100 was read)

**Status: FROZEN 2026-10-10 (01:55 CDT)** by the lab reviewer, after study 100's READ (the DRAFT, committed before that READ, fixed
the design and the pass rule; the freeze adds the pick, the banks and the census), before any scored bank of study 101. The text
changed at the freeze in this status block and §3 (the census) only. The laptop acks. **Information for his morning decision.**
- **Study 100's pick rule picked OVERLAP3** (READ `40cec728`, lab `fd990ddf`): mean best real lineup points +0.719 (set A +0.982,
  set B +0.456); P(≥ 1 big seat) A +0.03680, B −0.01809 (not worse on both); seats 0.961. **The deciding line of study 101 is
  OVERLAP3 − LIVE; PASS iff the mean best points are > 0 on both draws AND his rule holds on P(≥ 1 big seat)** (better on both
  draws AND the pooled seats ratio ≥ 0.80), as §2 fixed; every other line is information.
- **Banks 3322–3333** (set A 3322–3327, set B 3328–3333; sims bases 3372–3383, fields 4022–4033); study 100's reader, seed 20261144
  (the disclosure in §2). The laptop's scan was clean: the full set against every used bank's {b, b + 50, b + 700} (studies 90–100 included), no season
  years, no results file; the text scans found only the two studies' own preregs, shas, counts and timings. **Disclosed:**
  production's 09-19 hsim pilot evidence file (reports/reviews/evidence/2026-09-19-refreshed-hsim-trace-results.json) lists raw
  pilot seeds 3326 / 3327 / 3328 / 3330, inside this block; not a collision, because the lab never seeds with the bank itself
  (slate_seed_law = bank × 1,000,003 + season × 100 + week, nfl2 ctxcore/d800.py:99).
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run, recorded in `RUN_ENV_s101.txt` committed with the
  confirmatory census. The run starts from lab `b13a5c71` (study 100's READ commit `fd990ddf` plus this census; the code is 100's
  `635b64eb`, unchanged), on lab branch production/s101-confirm-100-20261010 (results/s101/).

## 1. Why
- Study 100 (`reports/2026-10-09-prereg-study100-ceiling.md`) picks at most ONE of five variations by a pre-stated rule on the
  book's best real lineup. Picking the largest of five gains on the same slates flatters the pick (the winner's curse); a fresh
  draw is the check.
- **Honest limit, plainly:** the armed construction needs 2023–24's ownership predictions, so no other slates exist; fresh banks
  re-use the SAME 36 slates' real outcomes. Study 101 checks the opponent and simulation draw and the winner's curse, **not new
  outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 100's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s100-ceiling-20261009`; the
  shas as frozen in study 100); new banks. The reader prints all of study 100's lines; ONLY the pick's line decides.
- **Banks (proposed; the laptop's full-set check and scan decide):** **3322–3333** (set A 3322–3327, set B 3328–3333; sims bases
  3372–3383, fields 4022–4033). The reader's bootstrap seed is study 100's (20261144): the same resamples, so the intervals are
  correlated with 100's; the pass rule below uses point estimates only.
- **THE PASS RULE (fixed now):** the pick − LIVE is **> 0 on both draws for the mean best real lineup points**, AND **his rule on
  P(≥ 1 big seat)** — better on both draws AND the pooled expected big seats ratio ≥ 0.80. Pass → the morning page suggests the
  pick as "held on a fresh draw"; fail → "did not hold" (not suggested).
- **If study 100 picks nothing, study 101 is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 100's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
- **Disclosure (the laptop's text scan, 10-09):** the 09-19 production evidence file
  `reports/reviews/evidence/2026-09-19-refreshed-hsim-trace-results.json` (in history) used production hsim pilot seeds 3326 /
  3327 / 3328 / 3330, inside this study's block 3322–3333. **Not a collision:** the harness seeds every stream through
  `nfl2.pipeline.slate_seed` = bank × 1,000,003 + season × 100 + week (the same law as `ctxcore/d800.py`'s `slate_seed_law`), so
  no lab stream is seeded with the bare bank number. Every other hit of the scan is this study's own files (preregistrations,
  reader, shas, timings).
- **The mechanics census at the freeze** (the lab reviewer's; outcome-blind; bank 1406; study 100's frozen code at its READ commit
  `fd990ddf`; PYTHONHASHSEED=0; 8 tests pass; lab `b13a5c71` on production/s101-confirm-100-20261010: `CENSUS_s101_binding.txt`
  `d0ba6ba1…`, `census_mechanics_bank1406.jsonl` `a4420afd…`): **identical to study 100's binding census** (lab `aae6236b`) -- the
  census text with the build time masked, and all 36 mechanics rows apart from the timing fields and the code-sha field.
