# Preregistration: study 115b, the go / no-go for study 115's pick — the pick vs LIVE on a fresh draw of the same slates (DRAFT 2026-10-10, committed BEFORE study 115 is read)

**Status: NOT RUN (2026-10-10): its condition failed — study 115 (READ_s115.txt `5ecd46e6`, lab `46236e09`) picked nothing.
Both arms were worse than LIVE on P(≥ 1 big seat) on both draws: HOT_WRTE1 −0.01641 (A −0.00974, B −0.02309; seats 0.951),
FADE2_WRTE −0.01763 (A −0.03431, B −0.00095; seats 0.926; guard 1 fails); "PICK: none -- keep the live book". Its banks stay
unused. Recorded under the design fixed before study 115's READ.** Earlier status: DRAFT 2026-10-10 (the times are this file's
commits) by the outside reviewer, committed and pushed **before study 115's READ**. The lab reviewer freezes it after study 115's READ; the laptop acks. **Information for his decision.**

## 1. Why
- Study 115 (`reports/2026-10-10-prereg-study115-wrte-recency.md`) picks at most ONE of two arms by his rule. Picking the larger
  of two gains on the same slates flatters the pick (the winner's curse); a fresh draw is the check (studies 98, 101 and 103
  failed it overnight; 99 passed).
- **Honest limit, plainly:** fresh banks re-use the SAME 36 slates' real outcomes. Study 115b checks the opponent and simulation
  draw and the winner's curse, **not new outcomes — not out-of-sample.**

## 2. The design (no new code)
- **Code: study 115's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s115-wrte-recency-20261010`;
  the shas as frozen in study 115); new banks. The reader prints all of study 115's lines; **ONLY the pick's line vs LIVE
  decides.**
- **Banks (the laptop's reservation; the full-set check: CLEAN; the text scans of both repositories: CLEAN, 10-10):** **3984–3995** (set A 3984–3989, set B
  3990–3995; sims bases 4034–4045, fields 4684–4695).
- **The reader's seed** is study 115's (20261159): the same bootstrap resamples, so the intervals are correlated with 115's. The
  pass rule below uses point estimates only. (The laptop reserved seed 20261160 for this study; it stays unused, because the
  frozen reader's own seed is kept, as in studies 99, 101, 103, 107, 109b, 111, 113 and 114b.)
- **THE PASS RULE (fixed now):** the pick − LIVE on P(≥ 1 big seat) is **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule again; guard 1 printed).
  - **Pass, HOT_WRTE1** → "held on a fresh draw": a candidate for his 17:55 arm if its default-off switch (the WR / TE hot ids
    into `row_rule_sets`), its tests, the Week-4 check and study 38's classification are done in time; otherwise Week 6.
  - **Pass, FADE2_WRTE** → "held": information for Week 6 (no production path for a projection fade this week).
  - **Fail** → "did not hold" (not suggested).
- **If study 115 picks nothing, study 115b is not run** (recorded).

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census (study 115's census on bank 1406,
  equal by construction); PYTHONHASHSEED=0; one heavy job at a time.
