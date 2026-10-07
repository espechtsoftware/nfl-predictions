# Preregistration: study 54, his live book against production's plain optimizer, in the harness, decided out of sample on 2022 (DRAFT 2026-10-07)

**Status: DRAFT 2026-10-07**, committed by the reviewer before any smoke output was examined and before any scored bank.
- The operator approved this study on 10-07, in reply to the reviewer's proposal: "LIVE vs production's plain optimizer, out
  of sample, frozen rule, read by Thursday".
- The design went to the laptop at about 12:27 CT, with 2023–24 as the read and 2022 as a two-way go / no-go. At about
  12:36, before any outcome existed, the reviewer moved the decision to 2022, for the reason in §3. The laptop is told in
  the same message as this DRAFT.
- The smoke scores one 2023–24 slate only. No 2022 outcome is scored before the freeze.
- The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator's approved-plan P3** (`reports/2026-10-07-prereg-p3-simple-baseline.md`, FROZEN `f129bc0b`): on live
  weeks, does his ENTERED book beat production's plain capped optimizer with our layers removed (MEAN_MILP)? Its sign rule
  decides at Week 12 at the earliest.
  - **The operator, 10-07:** "That is way too long for me to wait to adopt anything."
  - **His yes, 10-07:** the laptop's Week 1–4 real-field replay (in-sample for the layers, descriptive) and this harness
    study. P3's weekly record continues as a free monitor.
- **The layers in his live book, and where each was measured:**

  | layer | study | slates | read |
  |---|---|---|---|
  | the winners' shape mix (vs the house shape) | 28 | 2022–24, another harness (caps 10 / 5, K 22) | NO DIFFERENCE, every season positive: +0.061 [−0.012, +0.138]; 2022 +0.029 |
  | the QB cap 5 | 35 | 2023–24 | NO DIFFERENCE, leaning positive: +0.026 [−0.027, +0.083] |
  | the overlap limit 5 (vs 7) | 40 | 2023–24 | NO DIFFERENCE, leaning positive: +0.028 |
  | the overlap limit 4 (vs 5) | 41, replicated in 42 | 2023–24 | PASS: +0.059 [+0.011, +0.112]; 42: +0.048 [+0.018, +0.079] |
  | the round-robin fill | 42 | 2023–24 | NO DIFFERENCE: +0.008 [−0.040, +0.056] |

  - No study has measured the whole of his live book against the plain optimizer it replaced.
  - Study 30 (the Week-5 package vs Week 4's status quo with the 0.20 ownership term) read NO DIFFERENCE, both seasons
    negative (−0.071), on an older harness.
  - The 2023–24 slates are IN-SAMPLE for three of the four layers.
- **The prior, stated before any outcome:**
  - If the in-sample gains add up, LIVE leads PLAIN on 2023–24 by about +0.15 in P(≥ 1 big seat).
  - Out of sample the lead should be smaller.
  - With 17 slates (an interval half-width of about 0.07, from study 46c's 2022 read), NO DIFFERENCE on 2022 is plausible.

## 2. Arms (`experiments/s54_plain_baseline.py`)
**One pool and one objective per slate-bank:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted),
player_mean over both simulators, skill players under 1.0 dropped. Four arms:
- **LIVE** (the reference): his live Week-5 book and production's 15 spares, study 48d's 41 rows (the winners' mix,
  mix_fill's round-robin, overlap limit 4, QB cap 5, caps 13 / 6). Studies 50–53 used the same reference.
- **PLAIN** (THE DECISION): production's plain capped optimizer, exactly P3's MEAN_MILP.
  - The code: union_reselect's `frame_players` / `heavy_games` / `pmo_rows`, copied verbatim into
    `experiments/pmo_plain.py`. Production's file sha256 is `82ef245e…` (integration `26fb8d40`, unchanged through
    `4217b4df`); the copied text's sha256 `bc3c0f74…` is asserted at import and in the tests.
  - The settings: 26 rows in solve order; PRODUCTION_STACK (QB + 2 + one bring-back); the overlap limit 7 (the union's
    default, which MEAN_MILP keeps); no QB cap; exposure cap 13 = main_exposure_cap(0.5, 26); DST cap 6 = int(0.25 × 26);
    per-game 4; the $49,000 floor.
  - No spares: the union's `--main pmo_x50` has none.
- **PLAIN_O4** (exploratory): PLAIN with the overlap limit 4.
- **PLAIN_O4Q5** (exploratory): PLAIN with the overlap limit 4 and the QB cap 5. What remains between it and LIVE is the
  shape mix and the fill.

**Dealing.** Every arm is dealt by the head layout over its own rows: ranks 0–25, with the small-contest overlap limit 5.
LIVE's 15 spares are never dealt.

**Production's constraints** are asserted on every arm's rows: player, DST and QB caps, and the pairwise overlap limit.

**Not in either arm:**
- the Week-5 matchup block (study 51 measured it against this same LIVE);
- FP's projections (both arms share the harness projection; P3's live record runs on FP's).

**Tested** (`tests/test_s54_plain_baseline.py`, 7 tests):
- the frozen shas and constants, including the copied text's sha;
- production's caps at K (26 → 13 / 6; 105 → 52 / 26; 110 → 55 / 27);
- the plain frame's columns;
- the copied pmo_rows on a synthetic slate: the exposure, DST and QB caps and the overlap limit hold, and the QB cap binds;
- the builds;
- the census is outcome-blind;
- the reader: its decision, its printed levels (0.95; guard one-sided 0.95), the verdicts and the study rule.

## 3. Endpoint and rule (the reader `scripts/s54_report.py`)
- **THE DECISION (out of sample): 2022**, the 17 k1 slates with real Millionaire ownership.
  - PLAIN − LIVE, P(≥ 1 big seat) per slate on the calibrated field v2. Positive = the plain optimizer is ahead.
  - Two-sided 0.95. B 20,000, seed 20261106; slates resampled within season.
  - Banks 1575–1580. The unique-blob scan precedes the freeze.
- **Guards** (v2, 2022): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio
  PLAIN / LIVE ≥ 0.80. **The guards gate a PASS only.**
- **Verdict:** DEAD LEVER (identical to LIVE on > 80% of slate-banks) / WORSE (upper < 0: LIVE ahead) / PASS (lower > 0,
  both guards) / FAIL (guard) / NO DIFFERENCE.
- **STUDY:**
  - PASS: **THE LAYERS DO NOT EARN THEIR PLACE** out of sample — a simplification candidate, his decision.
  - WORSE: **THE LAYERS EARN THEIR PLACE** out of sample.
  - FAIL (guard), NO DIFFERENCE or DEAD LEVER: no evidence either way out of sample. His live book stands, and P3's weekly
    record continues.
- **IN-SAMPLE** (never decision-bearing): PLAIN − LIVE on 2023–24 (36 slates), two-sided 0.95, printed beside the
  decision.
- **EXPLORATORY** (two-sided 0.95):
  - the steps PLAIN_O4 − PLAIN (the overlap limit 4), PLAIN_O4Q5 − PLAIN_O4 (the QB cap 5) and LIVE − PLAIN_O4Q5 (the
    shape mix and the fill), on 2022 and on 2023–24;
  - the decision on l02;
  - the 53-slate pool;
  - levels, projection, salary, predicted ownership (2023–24), distinct QBs and players.
- **Why 2022 decides:**
  - Studies 35, 40, 41 and 42 chose the QB cap, the overlap limit and the fill on 2023–24. A LIVE lead there is partly
    that selection.
  - No study has read any of those layers on 2022.
  - The 2022 slates were read for other contrasts: study 46c, and studies 48–53's go / no-go, each comparing its own arm
    with LIVE. None of those reads changed LIVE.
  - **Disclosed:** study 28 read the mix against the house shape on 2022 (+0.029), on another harness, and the mix was
    adopted on that study's pooled read.

## 4. What a verdict can do
- **THE LAYERS DO NOT EARN THEIR PLACE:** production's plain path is a candidate from Week 5 or Week 6, his decision
  under the adoption track (`reports/2026-09-19-in-season-adoption-track.md`).
  - The plain path is `--main pmo_x50`: entered in Week 4, and built weekly as P3's MEAN_MILP.
  - The rollback is the current union arguments.
  - The Week-5 matchup block rides the mix path's term-block slot. A Week-5 switch to the plain path would therefore enter
    without the block, unless that pairing is checked first.
- **THE LAYERS EARN THEIR PLACE:** the live construction stays, and P3's weekly record is the live check.
- **No evidence either way:** the live construction stays, and P3 continues.
- **The post-selection law:** both arms share the harness projection and the dealing. The verdict is about construction
  on that projection. P3's live record covers FP's projections.

## 5. Production parity
- PLAIN is production's own code with production's caps at K (asserted equal to the harness's), the union's defaults and
  PRODUCTION_STACK, solved by the lab's `optimize`.
- **The smoke checks** that the Week-5 lab pin (`week5-live-center` `f69598b`) solves the same plain rows from the same
  frame. It also checks the copied text against production's file at integration.
- LIVE is the harness's emulation of his live book (the reference for studies 48–53).
- **What both arms share, unlike production:** the harness projection (not FP's), the harness slate frame, and a field
  sampled from real ownership.

## 6. Smoke and integrity
(Added at the freeze: the smoke, the binding census, the bank scan, the code shas.)

## 7. Order
1. This DRAFT.
2. The smoke, then the binding census.
3. The freeze.
4. The laptop's ack and bank scan.
5. The scored run: as soon as the machine is free, read by Thursday morning.
6. The confirmatory census, committed before the read.
7. The read.
8. The laptop's re-run.
9. The LEDGER row (after merging study 53's branch) and an Addendum.
