# Preregistration: study 101, the go / no-go for study 100's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-09, committed BEFORE study 100 is read)

**Status: DRAFT 2026-10-09** (the times are this file's commits) by the outside reviewer, committed and pushed **before study
100's READ** (the lab reviewer's condition). The lab reviewer freezes it (banks and seed) after study 100's READ; the laptop acks.
**Information for his morning decision.**

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
