# Preregistration: study 99, the confirmation of study 97's picks — study 97's frozen code on a fresh draw of the same slates (FROZEN 2026-10-09; the DRAFT committed BEFORE study 97 was read)

**Status: FROZEN 2026-10-09 (22:47 CDT)** by the lab reviewer, after study 97's READ (the DRAFT, committed at 21:44 by the commit's
clock, before that READ, fixed the design; the freeze adds the picks, the banks and the census), before any scored bank of study
99. The text changed at the freeze in this status block and §3 (the census) only. The laptop acks. **Information for his morning
decision.**
- **Study 97's §3 rule picked** (READ `53c1614f`, lab `8b9b3a9d`): **RBMATE4_FAVHI** (the RB version; it beat LIVE, A +0.00541 /
  B +0.01254, seats 1.097, and RBMATE4, A +0.04243 / B +0.00375, seats 1.152); **no QB + 2 version** (QB2_SHOOT failed; QB2_DOGHI
  read WORSE). **So the deciding lines of study 99 are RBMATE4_FAVHI vs LIVE and RBMATE4_FAVHI vs RBMATE4: CONFIRMED iff both
  pass his rule again** (better on both draws AND seats ≥ 0.80); every other line is information.
- **Banks 3198–3209** (set A 3198–3203, set B 3204–3209; sims bases 3248–3259, fields 3898–3909); study 97's reader, seed
  20261142 (the disclosure in §2). The laptop's scan was clean: the full set against 734 used banks' {b, b + 50, b + 700} (studies 90–98 included), no season years,
  no results file; the text scans found only this study's own prereg, dose names, shas, timings and study 97's reader seed (reused by
  design).
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run, recorded in `RUN_ENV_s99.txt` committed with the
  confirmatory census. The run starts from lab `0e692e2c` (study 97's READ commit `8b9b3a9d` plus this census; the code is
  97's `af07583e`, unchanged), on lab branch production/s99-confirm-97-20261009 (results/s99/).

## 1. Why
- Study 97 (frozen `88738a69`) makes eleven comparisons on the 36 slates of 2023–24; under no true effect about three pass his
  rule by chance. Its §3 situation rule picks **at most one RB version and at most one QB + 2 version** for the morning page.
- Study 81 → 84 showed the same rule on the same slates moving from +4.7 to −1.2 across bank sets (the bank-set variance
  finding). **A pick is suggested more credibly if it holds on a fresh draw.** Fresh banks re-use the SAME 36 slates' real
  outcomes: this is a check of robustness to the opponent and simulation draw, **not new outcomes, not out-of-sample**; a pass is
  still weak support (the picks were chosen on these slates).

## 2. The design (no new code)
- **Code: study 97's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s97-game-script-20261009`,
  module `7df6f324…`, reader `e5827c73…`, census `346b403f…`, driver `5dff66b7…`; the reader's bootstrap seed 20261142 kept, as the
  frozen reader prints it). Nothing is edited; study 99 is the same run on new banks.
- **Banks (the laptop's clean block):** **3198–3209** (set A 3198–3203, set B 3204–3209; sims bases 3248–3259, fields 3898–3909)
  — clean against 734 used banks (90–98 included), no season years. **Moved from the first proposal 3148–3159**, which collided:
  3150–3159 are study 95's sims bases (95's banks 3100–3111 + 50), and every bank from 3150 to 3197 is a sims base of studies
  95–98 (the cross-use class of 10-09: the {b, b + 50, b + 700} sets of every used bank). The design does not depend on the bank
  numbers; this is a bank fix before anything ran, recorded here.
- **Which lines decide:** ONLY the comparisons of the arms study 97's §3 rule picks, by the same §3 rule:
  - a picked RB-with-his-QB version (RBMATE4_FAV / RBMATE4_FAVHI) is CONFIRMED iff it again beats BOTH LIVE and RBMATE4 by his
    rule;
  - a picked FAVRB_NAKED4 / FAVRB_OPPQB4 / QB2_SHOOT / QB2_DOGHI is CONFIRMED iff it again beats LIVE by his rule.
  - Every other line is printed by the frozen reader and is information only.
- **If study 97's §3 rule picks nothing, study 99 is not run** (recorded).
- **Disclosure (the laptop's scan note):** study 99 re-uses study 97's frozen reader, so its bootstrap seed (20261142) is 97's:
  the same bootstrap resamples of the same 36 slates. 99's intervals and its guard-1 bound are therefore correlated with 97's
  beyond the shared slates. **His rule's decision does not use them** — it reads each draw's point estimate and the pooled seats
  ratio, which depend on the new banks only — but any interval on the morning page is not an independent second interval.
- **The morning page:** a pick is suggested as "held on a fresh draw" only if CONFIRMED; a pick that fails here is reported as
  "did not hold on a fresh draw" and is not suggested; if study 99 cannot be read before the morning, the page says so.

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's binding census (the frozen census on bank
  1406 = study 97's own census, so its numbers equal 97's binding census by construction; it is re-run as the mechanics check);
  PYTHONHASHSEED=0; one heavy job at a time.
- **The mechanics census at the freeze** (the lab reviewer's; outcome-blind; bank 1406; study 97's frozen code at its READ commit
  `8b9b3a9d`; PYTHONHASHSEED=0; 17 tests pass; lab `0e692e2c` on production/s99-confirm-97-20261009: `CENSUS_s99_binding.txt`
  `0e12e7da…`, `census_mechanics_bank1406.jsonl` `8a11b646…`): **identical to study 97's binding census** (lab `707f60ea`) -- the
  census text with the build time masked, and all 36 mechanics rows apart from the timing fields and the code-sha field (the
  laptop already reproduced 97's census for its ack).
