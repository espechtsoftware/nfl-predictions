# Preregistration: study 65 (S2 + S3), tail-aware tilts and a recency fade as 8-row blocks, in the harness (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08 (14:59 CDT)** by the reviewer, after the smoke, the binding census (§6) and the bank scan, before any
scored bank.
- The DRAFT was `63bec096`. Nothing in §2–§5 changed at the census; §6 records it, and §3's banks are confirmed.
- **Next:** the laptop's ack and scan, the run, the confirmatory census before the read, the frozen reader, the laptop's
  re-run and the records.
- **Target:** read before the Week-6 decisions (Tue 10-13; W6 arming Sat 10-17).

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator 10-08:** "please make sure that the recommended experiments that the outside reviewer suggested in the
  pros briefing are on the agenda before week 6". This is study list 65, the briefing's S2 and S3
  (`briefings/2026-week-05/2026-10-08-how-the-pros-pick-players.md` §7–§9). S1 is study 64, frozen and acked.
- **The history** (the briefing's §7; 2023–25; 6,791 played QB / RB / WR / TE player-games with a props number; each data
  point fitted alone, within season × week × position; "big game" ≥ 1.6× the player's projection, "bust" ≤ 0.5×). At equal
  projection, beyond the market:
  - big-game chance per sd: team implied total +1.9 pp (3/3 seasons), favoured −1.8 (underdogs boom more, 3/3), wind
    −1.8 (3/3), top opposing cornerback out +2.2 (3/3);
  - bust chance per sd: end-zone targets +2.0 (3/3), "beat the market last game" +1.8 (3/3), with −1.8 on big games.
  - Base rates: 21% big games, 22% busts.
- **The briefing's S2:** small bonuses for higher team totals, underdogs and a missing top opposing cornerback;
  penalties for wind and for touchdown-dependent receivers. In the term-block format, the cheap block's vehicle.
- **The briefing's S3:** among near-equal projections, prefer the player who did NOT just have a big game or a salary
  rise. The crowd's ownership rises with last week's points, and history says those points carry no information beyond
  the market on average.
- **The prior, stated first: NO DIFFERENCE is the likely result.**
  - Every block arm read so far against the cheap block was NO DIFFERENCE: study 63's four TE forms (Addendum 166).
  - Study 50's additive factor bonuses (matchup, vacated opportunity) were NO DIFFERENCE (Addendum 158).
  - Study 34's tilt toward the regulars' habits, which included fading last game's points, was NO DIFFERENCE (Addendum
    139). S3 differs from it in three ways: a block, a big-game flag rather than a linear tilt, and salary rises.
  - The real-field "dark game" finding cuts against the team-total bonus: most Millionaire winners came from games ranked
    11th or lower by implied total. The harness's fields price the chalk cost that finding reflects.
- **What the study can show:** whether either signal, in the 8-row block, changes his chance of a big win against the
  live cheap block, with no harm. A null leaves the cheap block, and the live paper arms, as they are.

## 2. Arms (`experiments/s65_tailtilt.py`)
**The book:** on each slate-bank, study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted), with LIVE = 48d's
41 rows: mix_fill rr, QB cap 5, caps 13 / 6, overlap limit 4. It is dealt on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`), as in studies 54–63. Every block is study 53's `block_term` through `term_book`'s 8 rows at ranks 2, 5, 9,
12, 15, 18, 22, 25.

- **LIVE_CB (the reference):** his live book with the cheap +2 block (study 53's CHEAP2_BLOCK8; the Week-5 trial).
- **S2's flags** (each 0 / 1, pre-lock facts on the harness frame; skill players only):
  - **HIGH_ITT (+1):** the player's team's implied total is in the slate's top third of teams. Teams are ranked by their
    median implied total; ties take the better rank.
  - **UNDERDOG (+1):** spread > 0. The census checks the sign on every slate-bank: favourites are negative.
  - **CB_OUT (+1):** a QB, WR or TE whose top opposing cornerback is out (the frame's `top_cb_out`). The cornerback's
    mechanism is the passing game, so RBs are left out.
  - **TD_DEP (−1):** a WR or TE with at least 0.5 end-zone targets per game over the last 4 (`ez_targets_l4`), about the
    WRs and TEs that are the most end-zone-dependent (the census reports the share).
  - **WINDY (−1, exploratory only):** a QB, WR or TE in an open-air game with wind of at least 15 mph. Open-air uses study
    64's stadium rule: the home team (game_id's last token) is not one of ARI, ATL, DAL, DET, HOU, IND, LA, LAC, LV, MIN,
    NO.
- **S3's flags** (each 0 / 1; skill players only):
  - **BIG_LAST (−1):** the player's LAST regular-season game this season before the slate's week, in any time slot,
    scored at least 1.6× max(the mean of his up to 4 games before it, 5 points). It needs at least 2 such games, which
    may come from the previous season.
    - Points are nflverse weekly stats under study 50's frozen DK formula (`s50_factor_bonuses.dk_points`, sha
      `bf4704a0…`, asserted).
    - **This is the stand-in, in every season, for "beat his projection last game".** 2022 has no props. The harness
      frames hold only the main slate, so a primetime game has no harness projection. One definition serves all three
      seasons, and it is computable live from last week's results.
  - **SALARY_RISE (−1):** this week's DK salary rose by at least $300 (`salary_delta_wow`), about 15% of the skill players in the smoke.
- **The arms' scores** are the signed sum of one point per flag, clipped to ±2 per skill player:
  - **TAIL_B8:** HIGH_ITT + UNDERDOG + CB_OUT − TD_DEP, the block INSTEAD of the cheap block.
  - **RECENCY_B8:** −BIG_LAST − SALARY_RISE, the block INSTEAD of the cheap block.
  - **CHEAPTAIL_B8:** the cheap +2 (every non-DST player under $4,000) plus S2's flags, one block and one clip.
  - **CHEAPREC_B8:** the cheap +2 plus S3's flags.
  - **EXPLORATORY TAILWIND_B8:** TAIL_B8 − WINDY. The harness's wind is the MEASURED game wind (no forecasts were stored
    before 2026), so this arm is an upper bound for anything a forecast can do. It never decides.
- **A penalty in the block format.** The block file carries non-negative bonuses. So each score is written as production
  would write it: bonus = score + 2 for every skill player of the pool, cap 4.
  - Every lineup holds exactly 8 skill players. The shift adds 16 points to every lineup of the block, so each solve's
    choice is unchanged.
  - The code asserts that the term reproduces the signed score.
  - Production: `--term-block-cap-points 4`.
- **A block whose score is 0 for every skill player** falls back to LIVE_CB's book there, recorded, so its difference on
  that slate-bank is 0. The smoke found none.

## 3. Endpoint and rule (the reader `scripts/s65_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. Only the names, the seed, the docstring and the secondaries differ.
- **THE READ: 2023–24** (36 slates). For each of the four decision arms, the arm − LIVE_CB on P(≥ 1 big seat), per slate,
  on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1605–1610**, seed **20261113** (the bank scan, §6). Each slate's value is the mean over its six banks.
- **THE GO / NO-GO: 2022** (study 51's frozen rule): the point estimate of P(≥ 1 big) ARM − LIVE_CB on 2022, with its
  two-sided 0.95 interval. CONTRADICTED if the point estimate is < 0.
- **Guards** as in studies 54–63. They gate a PASS only: the mean entry percentile (one-sided 0.95 lower bound above
  −0.015) and the expected-big-seats ratio (≥ 0.80).
- **Verdict per arm:** DEAD LEVER (the arm's dealt book is identical to LIVE_CB's on more than 80% of slate-banks) /
  WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **THE TRIAL RULE** (study 51's), per arm:
  - NOT ENTERED if WORSE, if CONTRADICTED, or if the expected-big-seats ratio is below 0.80;
  - MOOT on a dead lever;
  - otherwise ENTERABLE, his decision.
- **Multiplicity, disclosed:** four decision arms, each its own read for its own Week-6 choice, with no adjustment.
  Under no effect, a false PASS somewhere among the four has roughly a 10% chance.
- **EXPLORATORY:** TAILWIND_B8 − LIVE_CB; each arm on the l02 field; P(≥ 2 big seats); the flagged players per book row.

## 4. What the harness can and cannot say (disclosed before the census)
- **The harness's base is our simulator's mean, not FP.**
  - Our simulator already uses the implied total and the spread. So TAIL_B8's team-total and underdog parts partly
    repeat what the harness base carries, and the harness may understate them.
  - Live, the base is FP's projection, which in W4 showed no relation to team total, game total, spread or wind (the
    briefing §7).
  - A null here therefore does not close S2 for an FP base. The live paper arm (§5) is the fair test there.
- **The harness's lines are closing lines.** A late game's line can include news from after the 1 pm lock. This is a
  standing property of every harness study. The briefing's correction found the team-total effect just as strong in
  1 pm games.
- **CB_OUT's support may be thin.** The smoke's frames show it on 8% of 2022 W9's skill players and on none of 2024
  W10's. The census reports it by season. Where it is absent, TAIL_B8 is HIGH_ITT + UNDERDOG − TD_DEP.
- **No market data enters any arm.** Every S2 field exists in all three seasons, and S3 uses its stand-in throughout.
  The 2022 go / no-go therefore tests the same rule as the read.

## 5. What a verdict can do
- **A block ENTERABLE:** his Week-6 choice is that block, instead of the cheap block or combined with it, as the arm
  says. There is one construction change per week.
  - Production would write the block file from the T-70 frame: score + 2 per skill player, `--term-block-cap-points
    4`. S3 needs last week's results (nflverse weekly) and the frame's `salary_delta_wow`.
  - A writer, its tests and Friday's rehearsal come before any entry.
- **Otherwise:** the live book stands.
- **Either way,** S2 and S3 can become study 38 paper arms from W6 (an amendment before W6's lock), judged on the real
  fields with FP as the base.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s65-panel/smoke/`):
  - **First pass (2022 W9, 2024 W10)** found one defect, fixed before the DRAFT. S3's last game was read from the
    harness frames, which hold the main slate only, so a player whose last game was in prime time got an older game.
    The rule now reads nflverse weekly stats (§2).
  - **Second pass (2022 W9, 2023 W3, 2024 W10):**
    - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
    - every block applied;
    - each moves its 8 rows and shares the 18 live rows with LIVE_CB;
    - the spread's sign is negative for favourites on all three (correlation with team total −0.82 or lower).
    - Flag support (share of the pool's skill players): HIGH_ITT .33, UNDERDOG .51, CB_OUT .04, TD_DEP .19, WINDY .05,
      BIG_LAST .13, SALARY_RISE .15.
- **The full-path smoke** (2024 W10 and 2022 W6 scored on bank 1406):
  - the reader exited 0 and printed every section;
  - its output was read with numbers and verdict words masked.
  - Disclosed: the masked TRIAL SUMMARY line still showed one arm's name. Bank 1406 and one read slate carry no
    information on the decision banks.
- **The binding (support) census** (outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code `a5cab7b` clean; lab
  `results/s65/CENSUS_s65_binding.txt` `ff692e48…`, the raw mechanics rows `census_mechanics_bank1406.jsonl`
  `cb6babc4…` with no outcome field, committed whole at `6214e4a`):
  - every arm is 41 rows within production's caps, QB cap and overlap limit, with 8 term rows and every row in the pool
    (asserted);
  - the spread's sign: team implied total vs spread is negative on every slate-bank (at most −0.627), so spread > 0 is
    the underdog;
  - flag support (share of the pool's skill players; 2022 / 2023 / 2024):
    - HIGH_ITT .319 (.314 / .325 / .317);
    - UNDERDOG .502;
    - CB_OUT .029 (.035 / .029 / .023), with none on .472 of slate-banks;
    - TD_DEP .161 (.121 / .173 / .187);
    - WINDY .041, with none on .623 of slate-banks;
    - BIG_LAST .125 (.096 / .141 / .136);
    - SALARY_RISE .135.
    - The three Week-1 slate-banks have no BIG_LAST or SALARY_RISE.
  - the recency audit (per slate-bank, of 293 skill players): 235 with a last game this season, 174 of those in the
    previous week, and 224 with at least 2 games before it.
  - Blocks applied: TAIL_B8, CHEAPTAIL_B8, CHEAPREC_B8 and TAILWIND_B8 on 1.000; RECENCY_B8 on .943, falling back to
    LIVE_CB's book on the Week-1 slates.
    - There CHEAPREC_B8 (the cheap +2 alone, shifted) came out dealt identical to LIVE_CB. That is an empirical check that
      the shift changes no solve.
  - Flagged players per book row (26 rows; the 8 block rows carry the whole difference):
    - TAIL_B8 vs LIVE_CB: HIGH_ITT 4.48 vs 4.21, UNDERDOG 3.38 vs 3.14, CB_OUT 0.39 vs 0.21, TD_DEP 2.05 vs 2.47;
    - RECENCY_B8: BIG_LAST 1.33 vs 1.81, SALARY_RISE 1.86 vs 2.34;
    - TAILWIND_B8: WINDY 0.13 vs 0.22.
  - Rows shared with LIVE_CB: 18.0 / 18.5 / 18.3 / 18.8 / 18.0. Dealt identical on 0.000 / 0.057 / 0.000 / 0.057 / 0.000,
    so no arm is near the 0.80 dead-lever line.
  - Build time: about 93 s per slate-bank with 16 workers.
- **The bank scan** (the reviewer's unique-blob scan, `bank_scan.py`; blobs up to 5 MB) covered 17,991 production blobs
  and 8,087 lab blobs.
  - Filtered to bank contexts, banks 1605–1610 appear only in this preregistration, and the seed 20261113 only in this
    study's reader and test.
  - No `results_bank1605`–`1610` file exists on disk.
- **Code:** nfl2 `production/s65-tailtilt-20261009` @ `a5cab7b` (the census at `6214e4a`):
  - `experiments/s65_tailtilt.py` `7667c963…`;
  - `scripts/s65_drive.py` `2694b234…`;
  - `scripts/s65_census.py` `5d91fbbb…`;
  - **`scripts/s65_report.py` (the reader) `880c76c8…`**;
  - `tests/test_s65_tailtilt.py` `b2a57070…` (9 tests);
  - unchanged and sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`,
    `s50_factor_bonuses.py` `bf4704a0…`, `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `plan-week5-rev6-s24.json` `ac10ddf6…`.

## 7. Order
1. The code and the smoke. Done.
2. The DRAFT (`63bec096`). Done.
3. The binding census. Done (§6).
4. The bank scan. Done (§6).
5. The freeze. Done (this text).
6. The laptop's ack and scan.
7. The run, outside the build windows.
8. The confirmatory census before the read.
9. The read.
10. The laptop's re-run.
11. The records: the Addendum and the lab LEDGER row.
