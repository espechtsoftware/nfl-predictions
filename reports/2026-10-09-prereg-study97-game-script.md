# Preregistration: study 97, the shapes by game script — the RB mate on the expected winner, and the QB + 2 stacks in shootouts and on their trailing side, on his live Week-5 book, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (20:05 CDT; smoke done 20:22)** by the outside reviewer; code and smoke done (§5). The
reviewer reviews, runs the binding census and FREEZES; the laptop acks. **Information for his morning decision; nothing changes
overnight.**
- **Banks and seed:** **3124–3135** (set A 3124–3129, set B 3130–3135; sims bases 3174–3185, fields 3824–3835), seed 20261142 —
  the laptop's full-set check is clean against 710 used banks (90–96 included); its text-scan tally follows.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09 evening, in the outside reviewer's session (HANDOFF `543f2695`, verbatim; study-list row 87):** "I want
  to discuss the RB stack in the works. That seems like something we'll want to apply to games where the RB we select is on the
  team expected to be blowing out the other team or on the winning side of a shootout. Since in those cases I believe the RB gets
  more carries and perhaps more goal line action (research that). Similarly, stacks with a WR and QB make sense both in games
  expected to be shootouts and shootouts where the team is expected to be trailing since they'll have to be throwing to catch up.
  Please research all of that and after testing the shapes in general like you're doing, test them in those scenarios. My hope
  is that by morning you'll have suggestions on which of the tested arms should be used in which situations and in what
  percentages."
- **His two additions, the same evening, while this design was being built (HANDOFF `63a821d4`, verbatim; the clock 20:12):** "Im open to the RB being
  naked if the qb underperforms when favored. Ill trust your opinion on that", then "Or the qb from the trailing team etc" and
  "Do as you suggest". The outside reviewer's answer to him: a favored QB does NOT underperform (the research: 21.1 DK points for
  a 7+ favorite's QB vs 14.4 for a 7+ underdog's; 25+ in 31.7% vs 11.2%), but he barely moves with his own RB (correlation ≈ 0),
  so whether the favored RB should sit with his QB, without him, or with the trailing team's QB is a fair question for the
  harness — hence FAVRB_NAKED4 and FAVRB_OPPQB4 (§2). (The favorite's RB and the opposing QB: correlation +.076, Addendum 27.)
- **Study 96, read tonight (lab READ `9d479980`):** the unconditional RBMATE4 on top of ONECATCH is **PAPER ONLY** by his rule
  (−0.00455; A −0.00697, B −0.00213; seats 0.966), every floor held.
- **The research (before this design; seasons 2018–22 and 2025 only, NO 2023–24 outcome used; `reports/lab-handoffs/
  2026-10-09-game-script-research/`):** the expected winner's RB1 gets about the same carries but about 50% more goal-line
  carries, nearly twice the rushing TDs and 2.5× the chance of a 25-point game; the best case is the favorite in a high-total
  game (25+ in 22.7%). The QB and his own RB barely move together on a favorite (correlation ≈ 0), but on the favorite in a
  high-total game the QB + RB1 pair reaches 45 points more often (33.8%) than QB + WR1 (30.9%). Trailing teams in high-total
  games have the highest pass rate and a higher QB–WR1 correlation (0.36 vs 0.28), but the favorite there has the higher ceiling.
- **The stricter cut (≥ 7, his "blowing out"), from the same research:** the RB1 of a 7+ favorite vs a 3–7 favorite — goal-line
  carries 0.84 vs 0.79, rushing TDs 0.58 vs 0.53, P(≥ 25 DK) 19.2% vs 17.8% — a little more, not a different picture; for a 7+
  favorite OUTSIDE a high-total game the QB + RB1 pair reached 45 points less often than QB + WR1 (20.9% vs 25.3%), the reverse
  of the high-total case.
- **The prior (both ledgers):** QB + 1 only in the top-2-total games (study 15) NO DIFFERENCE; a one-game shootout book
  (study 26) NO DIFFERENCE with a ceiling signal; a stack from each top-4 game (study 43); the underdog's QB in a top-4 game (study
  80) NO DIFFERENCE, leaning worse; the lead RB + his DST on a 6-point favorite (study 16, the thesis portfolio) NO DIFFERENCE,
  closed; RBMATE4 +2.0 (study 94, without ONECATCH; study 96 with it, read tonight). **Prior: NO DIFFERENCE for every arm.**

## 2. Arms (`experiments/s97_game_script.py`)
**Study 96's harness exactly** (its frozen module `s96_onecatch_rbmate.py` `0363a84f…`, sha-asserted; `run()` = 96's `run()` with
eight listed edits, a test asserts it); **every arm is his live Week-5 construction** (the player cap 0.35, the ownership cap +
15, te1 / low1, ONECATCH, the QB cap 5, the DST cap 6, overlap 4, the cheap +2 block, 15 spares, Rev6, his cell quotas).
- **LIVE** — 93's `lead_rules(0, True, 0, …)` (= study 95's LIVE and study 96's ONECATCH; a test asserts call-for-call identity).
- **RBMATE4** — study 96's `combo_rules` with every (QB, own RB) pair (= 96's ONECATCH_RBMATE4; a second read on new banks).
- **RBMATE4_FAV** — the same, the floor's pairs only for QBs of **the expected winner (margin ≥ 3)** — an expected winner, not
  necessarily a blowout: the research's goal-line and TD gains already appear at 3–7 points (below), so the wider cut keeps
  support; no stricter arm is added tonight (multiplicity and run time).
- **RBMATE4_FAVHI** — only for the **expected winner of a high-total game** (margin ≥ 3 and the game in the slate's top third).
- **FAVRB_NAKED4** — on the same 4 C-cell slots, an expected winner's RB **without his own QB**: the floor over (QB of another
  team, RB of a FAV team) pairs (a lineup holds one QB, so the floor means exactly that).
- **FAVRB_OPPQB4** — on the first 4 **B**-cell slots (QB + 1 + a bring-back), an expected winner's RB **with the trailing team's
  QB**: the floor over (QB of the FAV team's opponent, RB of the FAV team) pairs, the RB being the row's bring-back (the C cell
  allows no bring-back). Built by `cell_floor_rules("B", …)`, study 96's `combo_rules` with the slot cell as a parameter (a test
  asserts that on C it is call-for-call `combo_rules`).
- **QB2_SHOOT** — on the QB + 2 rows (A1, A2), the QB only from a **high-total game** (either side).
- **QB2_DOGHI** — on the QB + 2 rows, the QB only from the **trailing side of a high-total game** (margin < 0).
- **THE SCENARIOS, pre-lock lines only:** each team's implied total and game total = the median of the frame's
  `implied_team_total` / `game_total` over the pool's rows; **margin = 2 × implied total − game total**; a **high-total game** =
  its total ≥ the slate's upper-third cut (numpy quantile 2/3 over the slate's games). A team without both lines is in no
  scenario.
- **Mechanics:** the RBMATE arms are 96's `combo_rules` with the arm's pair set (an empty set: the slot is taken without a floor,
  as 96). The QB2 arms add the scenario's other QBs as bans on A1 / A2 book solves (`qb2_rules`, entered BEFORE 93's
  `lead_rules`, so a failing solve drops the scenario first: [row + ban] → [row] → [ban] → [none]); none qualifying on a slate →
  no ban there (recorded). All inside the ownership cap; spares never.

## 3. The read (the reader `scripts/s97_report.py`)
- 2023–24 (36 slates); twelve banks as two disjoint draws (the same past slates, two random opponent sets) and pooled; study 63's
  frozen statistics (a test asserts them); two-sided 0.95, B 20,000; the guards gate a PASS only.
- **Eleven comparisons**, his rule printed for each (better on both draws AND the pooled expected big seats ratio ≥ 0.80):
  RBMATE4 − LIVE; RBMATE4_FAV − LIVE; RBMATE4_FAVHI − LIVE; RBMATE4_FAV − RBMATE4; RBMATE4_FAVHI − RBMATE4; FAVRB_NAKED4 − LIVE;
  FAVRB_NAKED4 − RBMATE4_FAV; FAVRB_OPPQB4 − LIVE; FAVRB_OPPQB4 − RBMATE4_FAV; QB2_SHOOT − LIVE; QB2_DOGHI − LIVE.
- **THE SITUATION RULE (fixed now, for the morning suggestion):**
  - **The favored RB:** RBMATE4_FAV / RBMATE4_FAVHI (with his own QB) are suggested only if each beats BOTH LIVE and the
    unconditional RBMATE4 by his rule; FAVRB_NAKED4 / FAVRB_OPPQB4 only if each beats LIVE by his rule. Study 96 read PAPER ONLY,
    so the unconditional RBMATE4 is not suggested whatever it reads here. If more than one qualifies, the one with the higher
    pooled point vs LIVE; the NAKED / OPPQB − RBMATE4_FAV comparisons are reported as information on the pairing.
  - **QB + 2 stacks:** QB2_SHOOT or QB2_DOGHI is suggested only if it beats LIVE by his rule; if both, the higher pooled point.
  - The percentages of the four shapes come from study 95's rule (`92108ea0`), never from this study.
- **The null rate and MULTIPLICITY, plainly:** each comparison passes about one time in four to one in three under no true
  effect; eleven comparisons, so about three false passes are expected; these slates have been read by studies 89–96. A pass is a
  candidate for his decision and the real-week paper arms, never proof.

## 4. What the harness can and cannot say
- The census reports per slate-bank the scenario teams (FAV / FAVHI / HIGH / DOGHI), each arm's floor pairs and banned QBs (and
  the slates where none qualify), the RBMATE slots / floors ruled / dropped, the QB + 2 bans ruled / dropped, ONECATCH ruled /
  dropped, THE BINDING (the book rows whose QB is in each scenario, overall / on the QB + 2 rows / on the C rows), the vacuity vs
  LIVE, and LIVE vs study 95's LIVE; **THE VACUITY LINES:** the slate-banks where RBMATE4_FAV / FAVHI's pair set is empty (the
  slot is taken without a floor, so the arm builds as LIVE there), and where QB2_SHOOT / DOGHI has no eligible QB (no ban) or
  fewer than 3 (the QB cap of 5 cannot fill the QB + 2 rows from them alone, so drops are expected and recorded).
- The transfer caveat: the harness builds on simulator means; his book on Fantasy Points' projections.
- **Production:** each arm is a small filter on tonight's flags (the laptop's request): RBMATE4_FAV / FAVHI = `--mix-rb-mate-c 4`
  with its pair set filtered by the frame's lines; QB2_SHOOT / DOGHI = A1 / A2 QB bans by the same lines. Built only on his word.

## 5. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke: the unit tests, the mechanics smoke (2023 W3, 2023 W11,
  2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **The smoke (DONE 20:22 CDT in the gap the reviewer named, before study 95's run; bank 1406; 2023 W3, 2023 W11, 2024 W10;
  PYTHONHASHSEED=0; `results_bank1406.jsonl` `e0f6620c…`; code `af07583e`):** 17 unit tests pass; every arm 41 rows within the
  armed caps, 8 term rows, in the pool; **0 row-rule and ownership-cap fallbacks in every arm** (78 of 78); **ONECATCH ruled 42 of
  42 B / C solves in every arm**; **every RBMATE-type arm 12 slots used, 12 floors ruled, 0 dropped** (FAVRB_OPPQB4 on B slots);
  the scenarios per slate-bank: FAV 8.7 teams, FAVHI 3.0, HIGH 8.0, DOGHI 4.0; floor pairs RBMATE4 126.0, FAV 50.0, FAVHI 20.0,
  NAKED 1167.3, OPPQB 40.0; no empty pair set and no slate without an eligible QB; **QB2_SHOOT's bans ruled 36 of 36; QB2_DOGHI's
  ruled 31 of 36, dropped 5 (13.9%; flagged by the census: the trailing sides of high-total games hold about 4 starting QBs, so
  under the QB cap of 5 and the ownership cap some QB + 2 rows fall back to the unrestricted QB, by design, recorded)**; THE
  BINDING: QB + 2 rows from a high-total game LIVE 7.0 → QB2_SHOOT 12.0 of 12; from its trailing side LIVE 1.7 → QB2_DOGHI 10.3;
  C rows with the FAVHI QB LIVE 0.3 → RBMATE4_FAVHI 4.0; QB + own-RB rows LIVE 3.3 → RBMATE4_FAV 7.3; rows shared with LIVE:
  RBMATE4 5.67, FAV 5.00, FAVHI 6.00, NAKED 13.67 (LIVE already holds about 22 rows with a FAV RB away from his QB, so NAKED's
  floor binds less), OPPQB 2.00, SHOOT 6.00, DOGHI 3.33 (none dealt identical); projection per row vs LIVE −0.08 to +0.07 except
  QB2_DOGHI −0.91; **LIVE identical to study 95's LIVE (the outside reviewer's 95 smoke) on 3 of 3 slate-banks**; the full path:
  the reader exited 0 (122 lines; 166 with the two-draw path on a copy); only the census, the exit codes and the line counts were
  read.
- **Code:** nfl2 `production/s97-game-script-20261009` @ `af07583e` (branched from study 96's census `0a09750a`):
  `experiments/s97_game_script.py` `7df6f324…` (pins s96 `0363a84f…`); `scripts/s97_drive.py` `5dff66b7…`; `scripts/s97_census.py`
  `346b403f…`; **`scripts/s97_report.py` (the reader) `e5827c73…`** (seed 20261142); `tests/test_s97_game_script.py` `61f20b91…` (17).
