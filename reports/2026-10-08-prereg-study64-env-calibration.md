# Preregistration: study 64 (S1), a game-environment calibration on Fantasy Points (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08** by the reviewer, before Sunday 10-11 12:00 CT, so W5's main slate is the first
prospective week (TNF is off the slate). The DRAFT was cc262444. This version supersedes the DRAFT's design after the
outside reviewer's correction (§2a); the frozen files and shas are in §6.

**Units:** DK points, points of team implied total, mph, rates.

## 1. Why
- **The operator 10-08:** "please make sure that the recommended experiments that the outside reviewer suggested in the
  pros briefing are on the agenda before week 6". This is study list 64, from
  `briefings/2026-week-05/2026-10-08-how-the-pros-pick-players.md` §8 S1.
- **The history** is the outside reviewer's analysis C, `reports/2026-10-08-pro-methods/c_history_beyond_market.py`. On
  2023–25, it asked which pre-lock data points predicted DK points BEYOND the betting market, the best historical
  stand-in for FP's projection.
  - Team implied total: +0.33 per sd (z 3.4, the same sign in all 3 seasons, passing Bonferroni over 40 data points).
    It holds in Sunday 1 pm games, where the closing line is the line at lock (+0.37 per sd, z 3.4; the correction).
  - Wind: −0.35 per sd (QB about −1), but see §2a.
- **Why it matters:** FP shows no sign of carrying this, and the regulars don't use it. It would be information the
  field's projections lack.
- **This study adopts nothing.**
  - A paper book can follow from W6, by a study 38 amendment before W6's lock.
  - A reversible trial follows only after the pooled check favours it (§4).
  - The operator decides both.

## 2. The adjustment (`scripts/s64_env_fit.py`, frozen as a coefficients file)

### 2a. The correction (the briefing's correction, merged 0b2207b8), and what changed from the DRAFT
- **Real units.** The DRAFT fitted per-sd effects (z within season × week × position). A live adjustment needs real
  units, so v2 fits DK points per point of team implied total and per mph.
- **Team total alone is the primary.** A team's implied total is half the game total plus or minus half the spread, so
  the three must not be added up. The primary model has the team total alone; it already carries the game total and
  the spread as they bear on the team. The game total's remainder (the opponent's total) is not fitted: the screen did
  not single it out.
- **Wind is a separate, low-confidence term.** Before 2026 the history's wind is the wind MEASURED at the game; no
  forecasts were stored. The market at lock had only the forecast. So the history's wind effect is an upper bound, and
  wind is judged on 2026 forecasts as a separate comparison that never gates (§4).
- **The stadium rule (O-61).** In 2023–25 the schedule's wind is NULL at every dome and retractable-roof stadium, open
  or closed. The live frame's is_dome is wrong for retractable roofs (O-61). So both the fit and the application use the
  home team (game_id's last token): wind counts only when the home team is NOT one of ARI, ATL, DAL, DET, HOU, IND, LA,
  LAC, LV, MIN, NO. SF is open-air.
  - The 2023–25 audit, by game: 263 roofed-home games have no wind and is_dome true; 11 roofed-home games have no wind
    and is_dome false (the retractables); 2 roofed-home games carry a wind (international games: 2024 W5 NYJ–MIN in
    London, 2025 W10 ATL–IND in Berlin). The rule zeroes those 2.
  - 39 open-air games have no wind reading (mostly 2023 W1–2, plus several international games). Their rows are KEPT
    with wind 0. The DRAFT's v1 fit dropped them, and the 11 retractable-roof games' rows too (is_dome false, no wind):
    488 rows in all.
  - An international game is treated by its listed home team, in the fit and live.

### 2b. The fit
- **Fit rows:** 2023–25 played QB / RB / WR / TE player-weeks with a props number (`market_points`, at least 2 scoring
  markets) and an implied total: **6,791 rows**, 4,452 of them open-air with a wind reading.
- **The residual:** y_dk_points − market_points, demeaned within season × week × position.
- **itt_d:** implied_team_total minus its season × week × position mean.
- **wind_d:** for open-air rows, wind minus the open-air mean of the season × week × position; 0 for every other row.
  The wind term is therefore the within-outdoor gradient; a roofed player gets no wind adjustment at all.
- **Two models per position, least squares:**
  - **ITT (THE PRIMARY):** resid_d ~ b_itt · itt_d.
  - **ENV (the wind increment):** resid_d ~ b_itt · itt_d + b_wind · wind_d.
- **Uncertainty:** a whole-week bootstrap (season-weeks resampled, 300 reps, seed 3), with per-season coefficients.
- **The coefficients are applied as fitted.** There is no shrinkage. The screen that found the effect used the same
  2023–25 data, so the in-sample size is optimistic; the prospective weeks are the test.

### 2c. The coefficients (`reports/2026-10-09-s64-env/s64_env_coefficients_v2.json`)

| Position | ITT b_itt per point (se) | 2023 / 2024 / 2025 | ENV b_itt | ENV b_wind per mph (se) | wind 2023 / 2024 / 2025 |
|---|---|---|---|---|---|
| QB | +0.156 (0.079) | +0.236 / +0.128 / +0.110 | +0.141 | −0.247 (0.079) | −0.399 / −0.099 / −0.291 |
| RB | +0.136 (0.052) | +0.044 / +0.234 / +0.127 | +0.135 | −0.020 (0.053) | −0.247 / +0.044 / +0.054 |
| WR | +0.098 (0.032) | +0.156 / +0.082 / +0.057 | +0.094 | −0.076 (0.040) | −0.113 / −0.003 / −0.128 |
| TE | −0.000 (0.044) | −0.018 / −0.071 / +0.075 | −0.002 | −0.014 (0.077) | +0.068 / +0.046 / −0.097 |

- Rows: QB 951, RB 1,666, WR 2,887, TE 1,287.
- The team total's sign is positive in all 3 seasons for QB, RB and WR. TE is about 0, so TE is effectively unadjusted.
- For scale: a QB on a team 5 points above the slate's QB average gets +0.78 points (ITT).
- **v1 (`s64_env_coefficients.json`, z-based, 6,303 rows) is superseded** before the freeze and kept as a record. Its
  apply refuses it (version ≠ 2).

## 3. Applying it (`scripts/s64_env_apply.py`)
- **On a week's T-70 frame, per skill player with an FP projection** (the union's proj_source.csv `fp`):
  - itt_d = the implied total minus the mean of the same position over those players.
  - wind_d = for open-air players (the stadium rule), wind minus the open-air mean of the same position; else 0.
  - A missing value, or a group with fewer than 3 values, contributes 0.
  - itt_adj = b_itt · itt_d (the ITT model); env_adj = b_itt · itt_d + b_wind · wind_d (the ENV model's own
    coefficients). Each is capped at ±2.0 points.
  - fp_itt = max(fp + itt_adj, 0); fp_env = max(fp + env_adj, 0).
- **The slate is the demeaning group** where the fit used the whole week. That is disclosed; the main slate is most of
  the week.
- **The output:** a private CSV with id, dk_draftable_id, pos, open_air, fp, itt_adj, env_adj, fp_itt and fp_env.

## 4. The weekly record and the rule (`scripts/s64_env_line.py`)
- **Per week from W5:**
  - It reads `scripts/weekly_projection_accuracy.py`'s own private player rows: the same population (QB / RB / WR / TE,
    FP ≥ 3 or ours ≥ 3, game-day active, an actual) and the same actuals.
  - The frame is the one the reader itself used (its json's `frame`); the projections are the entered union's
    proj_source.csv.
  - **THE IDENTITY GATE:** on the joined ids, apply's fp must equal the reader's fp (|difference| ≤ 1e-6), or the
    line refuses. A reader row outside apply's population gets adjustment 0 (counted).
  - It scores with the reader's own metrics (MAE, bias, Spearman) and game-cluster bootstrap (B 2000, seed 1),
    imported and sha-pinned (dadc647d…). The challenger sits in the reader's "ours" slot and the incumbent in its "fp"
    slot.
  - Single weeks are descriptive.
- **PRIMARY: FP + ITT vs FP.** THE POOLED CHECK is the frozen reader's own rule: "FP + ITT beats FP" when the pooled MAE
  is lower AND at least 95% of the pooled resamples are better.
  - It is read each week from W8, once at least 4 weeks are pooled. The first week it passes makes the adjustment
    trial-eligible. That is his decision.
  - Before W8 it is descriptive only.
- **WIND: FP + ENV vs FP + ITT.** Reported each week, low confidence (fitted on measured wind, applied to a forecast).
  It never gates and never makes anything eligible.
- **The pool** holds weeks from W5 only. Earlier rows (the W4 smoke) are left out and named.
- **Honest power note.**
  - The adjustment is small: its sd is about 0.3–0.6 points against an MAE of about 5.5.
  - A correct shift of that size should improve MAE by only a few hundredths of a point.
  - One week's 5–95% band is about ±0.05 (W4: −0.06 to +0.03).
  - So "does not beat FP" at W8 means "not shown yet", not "no effect", and the line continues.
  - Reading the check weekly from W8 to W18 is up to 11 looks, so the chance of a false pass is above the nominal 5%.
    That is accepted for a reversible trial gate under the adoption track v2. It is not a scientific verdict.

## 5. The W4 smoke (disclosed; not part of any pool)
- **Run after the code and coefficients were committed (506c1902)**, on W4's reader rows
  (`accuracy-2026-w04.csv`, rows sha 760c22ed…), its frame (run 20261004T155026918221Z-32cdb61) and the W4 union's
  proj_source.csv.
- **Outcome-blind application:** 292 players, 216 open-air. ITT mean |adj| 0.256 (none capped); ENV mean |adj| 0.293
  (1 capped). By position, the ITT adjustment's sd is QB 0.58, RB 0.52, WR 0.35, TE 0.00.
- **The full path (outcomes):**
  - The identity gate passed: 195 of 195 rows joined, maximum fp gap 0.0.
  - Verbatim: `W04 (descriptive) PRIMARY: MAE FP 5.539 vs FP + ITT 5.549 (bias +0.011 / +0.029; Spearman 0.617 /
    0.620); improvement -0.0119 [5-95% -0.0615, +0.0309], share of resamples better 0.361`.
  - Verbatim: `W04 (descriptive) WIND (low confidence, never a rule): MAE FP + ITT 5.549 vs FP + ENV 5.552 (bias +0.029
    / +0.029; Spearman 0.620 / 0.618); improvement -0.0021 [5-95% -0.0355, +0.0324], share of resamples better 0.456`.
  - The pool subcommand left W4 out, as designed.
- **Nothing was changed after the smoke.**

## 6. The frozen files (branch review/s64-env-20261009)

| File | sha256 |
|---|---|
| scripts/s64_env_fit.py | f479c5b80254a6056f07c6cad60f1717c11c6433817f8d5b1411024a026e598a |
| scripts/s64_env_apply.py | 60cde9795a0581abcf387ff8cb6728b64853f02ba1595e123bd63100859bb26d |
| scripts/s64_env_line.py | 11a2b539813db59f0de99ad5ba3f153f5fff925644d8299d19e8b2f9caa6701e |
| tests/test_s64_env.py | 7677821a9fef71d457958ec72c042b7508f602db3edee1f74bbc688193bb2170 |
| reports/2026-10-09-s64-env/s64_env_coefficients_v2.json | 1c54a3ccfb4bb7c7d1c3686edf7cc2fe94d94a4ad17387328c55af3fea9daa65 |
| scripts/weekly_projection_accuracy.py (the reader, imported) | dadc647dd3bdeffade8526774f2b9849027962fe91df00f7e47268b866c0890d |

- The coefficients file records the fitter's sha (f479c5b8…, the committed fitter) and the input content sha
  (de00025e…).
- **The laptop's re-run:** fit into its own path and compare everything but `written_utc`:
  `PYTHONPATH=src python scripts/s64_env_fit.py --out <own path>`, then
  `python -c "import json,sys; a,b=(json.load(open(p)) for p in sys.argv[1:]); [d['fit'].pop('written_utc') for d in (a,b)]; print('IDENTICAL' if a==b else 'DIFFERENT')" reports/2026-10-09-s64-env/s64_env_coefficients_v2.json <own path>`.

## 7. Order
1. The DRAFT (cc262444). 2. v1 fit (5ca8b3f5), superseded. 3. v2 code and coefficients (506c1902). 4. The W4 smoke.
5. This freeze. 6. The laptop's ack and re-run. 7. Monday 10-12: the first line (W5), by the reviewer, re-run by the
laptop.
