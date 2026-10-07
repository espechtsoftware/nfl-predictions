# Preregistration: study 50, the outside reviewer's factor bonuses in the harness, with a 2022 go / no-go (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding census (§6), before any scored bank. The
file carries the date of its scheduled run (10-08), the name the frozen code points to. The laptop acks the census,
scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator (10-07), on the outside reviewer's "why we missed the winners' players"**
  (`review/outside-fill-order-20261006` @ `0ad813b2`): "review this and schedule any necessary experiments this week".
  The laptop proposed this study; the reviewer amended the design.
- **The bonuses** (`make_factor_files.py`) add points to the build's objective. Their weights were fixed before the
  reviewer's replay but chosen from the same weeks' factor analysis, so they are in-sample on 2026 Weeks 2–4:
  - **MATCHUP:** clip(1.0 × z, 0, 2), z the opponent's DK points allowed to the position, shrunk to the prior season;
  - **VACATED:** clip(10 × the own-type vacated share, 0, 3);
  - **MARKET:** clip(0.5 × (props-implied − the projection played), 0, 2);
  - **COMBINED:** clip(the sum, 0, 3).
- **Its fixed-book replay** of the live Week-5 book on Weeks 2–4, P(≥ 1 big) by week:
  - live .041 / .002 / .434;
  - matchup .001 / .296 / .503;
  - combined .007 / .921 / .308;
  - vacated .000 / .025 / .056.
  - Market equals live in Week 4 (byte-identical under FP: a dead lever).
- **Its out-of-sample note:** matchup to explosion has an odds ratio of 1.07 per sd in 2023–25, and nothing in Weeks 1–4
  (1.01). Our O-40 screen agrees: matchup columns add ≈ 0 to the projection model.
- **The prior, stated before any outcome:**
  - The census (§6) shows the bonuses rebuild nearly the whole book (under 1 of 26 rows shared with LIVE), at a cost of
    1.8 (MATCHUP) and 2.4 (COMBINED) projected points per row.
  - The matchup bonus is independent of the harness's projection (Spearman +0.004), so it is not double-counting.
  - A small explosion edge (odds ratio 1.07) is unlikely to repay that projection.
  - So NO DIFFERENCE or WORSE is the likeliest reading.

## 2. Arms (`experiments/s50_factor_bonuses.py`)
**The build.** On each slate-bank, his live Week-5 book and production's 15 spares are built: 41 rows through one
state, with the winners' mix, mix_fill's round-robin, limit 4, QB cap 5 and caps 13 / 6. Study 48's harness is used
throughout (`s48_winner_like.py` `c22d2811…`, sha-asserted). It is built three ways:
- **LIVE** (reference): on player_mean. On the smoke slate its 41 rows and ranks equal study 48d's exactly.
- **MATCHUP** (DECISION 1): player_mean + MATCHUP.
- **COMBINED_NOMKT** (DECISION 2): player_mean + clip(MATCHUP + VACATED, 0, 3). Market is excluded: there are no props in
  the history, and it is a dead lever under FP.

**The bonuses, ported exactly from `make_factor_files.py`** (QB / RB / WR / TE only):
- **MATCHUP:**
  - Each defense's per-game DK points allowed to the position: (6 × the PRIOR season's per-game mean + the CURRENT
    season's sum before the slate's week) / (6 + the current season's games before the week).
  - A defense missing from the prior season gets the position's mean there.
  - z within position across the slate's skill players (ddof 1, + 1e-9; a missing value counts 0); clip(1.0 × z, 0, 2).
  - The points come from ONE source for every season: nflverse weekly stats (regular season, the player's listed
    position), DK points by the DK formula (`dk_points`; tested). The prior season is s − 1 for each harness season.
  - Production's live writer reads the warehouse instead; each source is consistent with itself.
- **VACATED:** RB uses the frame's `team_vacated_carry_share`, WR / TE `team_vacated_target_share`, QB 0; clip(10 ×
  share, 0, 3). These are the frame's pre-lock columns, present for 96% of rows (a missing share counts 0).

**Production's constraints** (caps 13 / 6, QB 5, limit 4) are asserted on every arm's 41 rows. Each arm is dealt by
the head layout.

**Tested** (`tests/test_s50_factor_bonuses.py`, 6 tests):
- the DK formula;
- MATCHUP point in time: never the slate's week or later, never a season before s − 1; a missing defense at the
  position's mean; z with ddof 1; the clip;
- VACATED by position type, and the clips;
- the arms' objectives through mix_fill;
- the census is outcome-blind;
- the reader: its two decisions, its printed levels (0.975; 0.95 for 2022 and exploratory; guard one-sided 0.95), the
  verdicts, the go / no-go and the study rule.

## 3. Endpoint and rule (study 18b's, extended; the reader `scripts/s50_report.py`)
- **THE READ: 2023–24** (36 slates).
- **TWO CO-PRIMARY DECISIONS:** MATCHUP − LIVE and COMBINED_NOMKT − LIVE, each P(≥ 1 big seat) per slate on the
  calibrated field v2.
  - Two-sided 0.975 each (Bonferroni). B 20,000, seed 20261102; slates resampled within season.
  - Banks 1551–1556. The reviewer's unique-blob scan of both repositories found these numbers as banks or seeds only
    in study 50's own usage lines. That covers every blob up to 5 MB; the 8 larger blobs per repository were not
    searched.
- **Guards, per decision** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats
  ratio ≥ 0.80. **The guards gate a PASS only.**
- **Verdict, per decision:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **THE GO / NO-GO: 2022** (17 k1 slates with real Millionaire ownership, the same banks; never read on this question).
  - Per decision: the point estimate ARM − LIVE with its two-sided 0.95 interval.
  - CONTRADICTED if the point estimate is < 0.
- **STUDY:** a decision is ADOPTABLE only if it PASSes on 2023–24 AND is not contradicted on 2022. If both are, the
  candidate is MATCHUP, the simpler one-factor form.
- **EXPLORATORY** (two-sided 0.95): both arms on l02 (the read and 2022); levels, projection, predicted ownership
  (2023–24) and bonus points per row.

## 4. What a verdict can do
- **ADOPTABLE:** a Week-6 candidate for his decision, with the transfer caveat that our projections become FP's.
  - Production's vehicle exists: the union's bonus through the ownership-term route, or a block.
  - Study 38's paper arms (amendment 6d: MIXT_QA0_MATCHUPX, MIXT_QA0_COMBINED, on FP from Week 5) give the real-field
    record beside it.
- **Otherwise:** the bonuses stay off. The paper arms continue as the weekly real-field record, so the in-sample replay
  is checked out of sample in both the harness and the field.

## 5. Production parity
- The bonus formulas are ported verbatim from `make_factor_files.py`; production's writer (`scripts/paper_factor_file.py`)
  reproduces the outside reviewer's own Week-4 bonus files exactly (all four bonuses, 270 rows, max difference 0).
- The vehicle (objective + bonus) is the one the reviewer's replay used: the ownership-term route at tilt 0.20 adds
  exactly the bonus.

## 6. Smoke and integrity
- **The smoke** (2024 W10 and 2022 W6, bank 1406, the full path; code as committed):
  - every arm built 41 rows within production's constraints;
  - LIVE equals study 48d's 41 rows and ranks on 2024 W10;
  - matchup values were found for every skill player;
  - the census and the reader exited 0. The reader printed its 2 headers, and its header names STUDY 50 (tested).
- **The binding census** (outcome-blind; bank 1406; 53/53 (2022: 17; 2023–24: 36), code `3281bd2` clean;
  `results/s50/CENSUS_s50_binding.txt` `b321cf7d…`, raw `f367683a…`; lab `1a6f613`):

  | | 2023–24 LIVE | 2023–24 MATCHUP | 2023–24 COMBINED_NOMKT | 2022 MATCHUP | 2022 COMBINED_NOMKT |
  |---|---|---|---|---|---|
  | projection per row (change) | 128.04 | 126.28 (−1.76) | 125.68 (−2.36) | −1.84 | −2.58 |
  | predicted ownership per row (change) | 78.56% | +0.36 | −2.18 | n/a | n/a |
  | book rows shared with LIVE | — | 0.3 of 26 | 0.2 of 26 | 0.2 | 0.1 |
  | identical to LIVE | — | 0.000 | 0.000 | 0.000 | 0.000 |

  - **The bonuses, 2023–24:** MATCHUP reaches about 119 players a slate (mean +0.40 over skill players, max 2), with a
    Spearman of +0.004 with player_mean. VACATED reaches about 54 (Spearman −0.04). Combined: about 147.
  - No quota passed to A1. About 63 s per slate-bank for the three arms.
- **Code:** nfl2 `production/s50-factor-bonuses-20261007` @ `3281bd2` (the census at `1a6f613`):
  - `experiments/s50_factor_bonuses.py`, sha256 `bf4704a0d94ad87938fc29bf94d20fc9deb86f857f454e671f5cd195c1e74265`;
  - `scripts/s50_drive.py`, `2455f051512d4f8daa770847130f01812929e85150ecb30def4b25ef83220c99`;
  - **`scripts/s50_report.py` (the reader), sha256 `76366b131f7223890b1442f80d5e70050a7e259f7144cbc2557db45d543acb16`**;
  - `scripts/s50_census.py`, `f7446810d851e103529fef141dcd4cd718433378a1a871597b5c36fa2995e678`;
  - `tests/test_s50_factor_bonuses.py`, `b6f9b7496be8bb1b27109ef6d14b1ecc515378a7e07de68077c2cb1ac50e114c` (6 tests);
  - study 48's `s48_winner_like.py` `c22d2811…`, `mix_fill.py` `dcf6a299…`, `l02b_field_sampler.py` `fadf9cfe…`,
    unchanged.
- **Order:** this freeze → the laptop's ack and bank scan → the scored run (Thursday, after the outside reviewer's
  Experiment B frees the machine) → the confirmatory census, committed before the read → the read → the laptop's re-run
  → the LEDGER row and an Addendum.
