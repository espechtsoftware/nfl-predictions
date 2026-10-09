# Preregistration: study 91, at most one TE and at most one player under 3% projected ownership per lineup, on his armed Week-5 package, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (13:29 CDT)** by the outside reviewer; the code and smoke are done (§6). The reviewer reviews, runs the
binding census and FREEZES; the laptop acks. **Runs BEFORE study 90** (his order: a Week-5 decision with a Sunday deadline).
- **Banks and seed:** **3000–3011** (set A 3000–3005, set B 3006–3011; sims bases 3050–3061, fields 3700–3711), seed 20261136 —
  the reviewer's block, clean against the full used set by construction; the laptop scans it.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request and his rule
- **The operator, 10-09 (in the outside reviewer's session; the laptop records it verbatim, HANDOFF f8b1dc30 and after):** after the
  limited-entry winners scan, "Yes do that"; then **"for test 2 - I would like to test it today and if it improves things, use it
  in week 5 as we obviously need to do something"**. Asked what "improves" means, he chose **"Better on both draws
  (Recommended)"**: "Live in W5 only if 'at most one TE + at most one player under 3% owned' beats your armed package on BOTH
  draws and doesn't cost more than 20% of expected big wins. Otherwise paper only."
- **The scan behind it** (the outside reviewer's, his W1–4 limited-entry contests — the 4444 / 555 / 333 satellites, FFWC, the
  $20-Millionaire satellites; real rosters, real points; aggregates in
  `reports/lab-handoffs/2026-10-09-limited-entry-winners/`): a TE in the flex in 54–100% of our lineups against the top 3's
  11–50%; about 1.0 player under 3% *contest* ownership per lineup in ours against 0.4–0.5 in the top 3. Hindsight caveats apply
  (winners hold the week's booms).
- **What was tested before (the prior):** the TE half was read twice in the harness, both flat — study 85's no-TE-in-the-flex
  rule +0.2 (2022 +3.4; Addendum 183); study 88's TE-flex rule against study 87's book +0.2 (2022 +0.1; Addendum 187). The
  low-ownership half is new. **Prior: NO DIFFERENCE.**
- **THE TRANSFER CAVEAT (the reviewer's 6p smoke on his real W4 package book, FP's means and FP's projected ownership):** the TE
  rule changes 21 of 26 rows (FP −0.61 per lineup); **the low-ownership rule barely binds there** — by FP's projections his book
  holds only 0.1–0.3 players under 3% per lineup, so "at most one" almost never triggers. The scan's excess was in REALIZED
  contest ownership (players projected above 3% who ended under it in small fields), which a projected-ownership rule cannot
  see. In the harness the blend's predictions put about 171 of 247 skill players under 3%, so the low rule binds there (0.91 →
  0.62 low-owned per row on the smoke) — **more than it would on his real book.**

## 2. Arms (`experiments/s91_row_rules.py`)
**Study 89's harness exactly** (its frozen module `s89_own_cap.py` `92b09345…`, sha-asserted; `pred_blend`, `own_cap_rows`, `own_caps`
imported); **every arm is his ARMED W5 package**: the player cap 0.35 (9 of 26 rows) + every skill player at floor(26 × (pred /
100 + 0.15)) book rows (pred = the l20 `blend_pct` rescaled to 800%); the QB cap 5, the DST cap 6, the overlap limit 4, the cheap
+2 block, the 15 spares, Rev6.
- **CAP35_OWN15** — the package (the reference).
- **OWN15_TE1** — + at most ONE TE per book row (no TE in the flex).
- **OWN15_LOW1** — + at most ONE skill player with pred < 3.0 per book row (no prediction = 0%, low; DSTs never counted).
- **OWN15_TE1_LOW1** — both (**THE DECISION**).
- **Mechanics:** the rules ride as set_constraints on every BOOK solve (j < 26, build order, any cell; spares never), in ONE
  solve with the ownership-cap bans, through **study 38 amendment 6p's `row_rules` pasted byte for byte** (nfl2 `b03ddaac`;
  text sha `47727594…`; the W5 paper arm's identical mechanics), entered before study 89's `own_caps`: an infeasible solve is
  re-solved without the rules (the ownership cap kept), recorded; still infeasible → `own_caps`' own fallback, recorded.

## 3. The read (the reader `scripts/s91_report.py`)
- 2023–24 only (36 slates); twelve banks as **two disjoint draws** (A, B) and pooled; study 63's frozen statistics (`load`,
  `mean_contests`, `boot`, `verdict` identical; a test asserts it); two-sided 0.95, B 20,000; the guards gate a PASS only.
- **DECISION: OWN15_TE1_LOW1 − CAP35_OWN15** on P(≥ 1 big seat) per slate.
- **HIS W5 RULE, printed as one line:** **GO LIVE iff the point estimate is > 0 on BOTH draw A and draw B AND the pooled expected
  big seats ratio ≥ 0.80; otherwise PAPER ONLY** (study 38 6p). Guard 1 (the mean entry percentile) printed beside it, outside
  his rule. Under no true effect it passes about one time in four to one in three (the draws share slates and outcomes).
- Also: each half against the package (OWN15_TE1, OWN15_LOW1) and the low half on top of the TE rule (OWN15_TE1_LOW1 −
  OWN15_TE1); the l02 field; secondaries (expected big seats, P(≥ 2), projection, TEs and low-owned per row, concentration).
- Plainly: the slates are the ones studies 78–90 read; study 84's bank-set finding is why two draws are read; the harness scores
  books on real points against a field drawn from real ownership, easier than his real fields.

## 4. What the harness can and cannot say
- **The W4 real-book check** = the reviewer's 6p smoke (above): TE1 and TE1_LOW1 −0.61 FP per lineup, 21 of 26 rows changed;
  the low half nearly vacuous on his real book.
- The census reports the VACUITY of each half against the package and of the low half on top of the TE rule (rows shared,
  dealt identical).

## 5. Production — only if his rule says GO LIVE
- A union_reselect flag, default off (the laptop's agreed format): `--mix-max-te 1`, `--mix-max-low-own 1`, `--mix-low-own-pct 3`,
  reading `--main-own-cap-source`'s `fp_own_raw` (raw %, blank = 0%, skill only), per book row (j < K), spares never; infeasible →
  re-solved without the rules, the ownership cap kept; the rules OFF (recorded, alerted) whenever the ownership cap is not
  applied; receipt `config.union.mix.mix.row_rules`; parity against 6p's `row_rules` + `low_owned` byte for byte (sha-pinned).
  The outside reviewer writes it during this study's run; the laptop wires and checks it; it merges only on GO LIVE.
- Study 38: 6q (the reviewer's) — the live rule classified "checked", QA0 follows it, the package without the rule paired on paper.

## 6. Smoke, census and integrity
- **The smoke (DONE; bank 1406; 2023 W3, 2023 W11, 2024 W10; `results_bank1406.jsonl` `1a0f9fda…`; code `41d2430f`):** 8 unit tests
  pass; every arm 41 rows within the package's caps, 8 term rows, in the pool; **0 infeasible** row-rule and ownership-cap solves
  (78 of 78 each); the pool per slate-bank: TEs 48.3 (min 45), skill players predicted < 3% 170.7 (min 162) of 246.7;
  rows with 2+ TEs: package 18.0 → 0 under the TE rule; low-owned per row 0.91 (package) → 0.62 (LOW1, TE1_LOW1); rows shared
  with the package: TE1 0.33, LOW1 14.0, TE1_LOW1 0.33 (none identical); the low half on top of the TE rule: 4.67 rows shared,
  identical 0.000; projection per row vs the package: TE1 −0.84, LOW1 +0.04, TE1_LOW1 −0.86; the full path: the reader exited 0
  (51 lines; 66 with the two-draw path on a copy); only those were read.
- BLAS threads pinned to 1 (89's driver).
- **Code:** nfl2 `production/s91-row-rules-20261009` @ `41d2430f` (branched from study 89's frozen branch `2fe958eb`):
  `experiments/s91_row_rules.py` `9cde18bd…`; `scripts/s91_drive.py` `1aed4f32…`; `scripts/s91_census.py` `ee9d2d84…`;
  **`scripts/s91_report.py` (the reader) `518067b8…`** (seed 20261136); `tests/test_s91_row_rules.py` `a0119b0b…` (8).
