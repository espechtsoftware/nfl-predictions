# The ownership term in the main book's objective: arming it for Week 4

Reviewer, 2026-09-29 17:59 CDT. Branch `review/ownership-term-20260929`, based on integration `7231db6b`.
Follows `reports/2026-09-29-winners-study-and-consistency.md` (branch `review/winners-study-20260929` @ `2944c250`),
whose §5.3 row 1 said "paper Week 4, entry Week 5". **The operator decided on 2026-09-29 to arm it for Week 4 if
possible.** This file is the specification, the evidence as it stands after four more checks, and a reference patch.

## 0. Summary

| Question | Answer |
|---|---|
| What changes | The capped optimizer's objective for the **main book only**: `mean_projection + 0.20 × predicted ownership %`, skill players only. Caps, house rules, K, the tail sleeve and every other lever are unchanged. |
| Which ownership | **The lag model blended with LineStar** (the rule L15 froze as BLEND_PCT). The file the chain builds today has no lag inputs and is not a substitute (§2.2). |
| Which entries it touches | The main-track rows: in the Week-4 plan, the satellite entries whose line is below the field's p98. The Millionaire and the deep-line contests draw from the sleeve, which is row for row the sleeve of the build without the term. |
| Size of the effect | On 36 slates of 2023–24, two banks: **+0.16 and +0.19 sd** per lineup against the field, both seasons, 25–11 and 26–10 slates. Under Week 4's dealing the ticket gain is smaller and not distinguishable from zero (§2.3). |
| What the 2026 weeks say | Three weeks, real fields: **−0.11 sd** against the plain book, all of it Week 1. Too few weeks to judge (§2.4). |
| Operational cost | One more Saturday command, one capture and one blend before each Sunday union, and 10 to 20 seconds of solves. A refusal at any step builds the book as armed today. |
| Rollback | `UNION_MAIN_OWN_TILT=0`. |

## 1. The change, exactly

1. **Saturday, after the projection refresh:** the lag model's file, beside the existing sets file (which stays as it is,
   because the preflight, the `fewest-low` order and O1's LAG arm read it):

   ```bash
   PYTHONPATH=$PROD/src $PROD_PY scripts/ownership_sets.py sets --season 2026 --week 4 --group 154078 \
       --lag-features --out ~/week4-sunday/ownership_lag.csv
   ```

2. **Saturday (for O1, and as Sunday's fallback), then before each Sunday union (09:10's and T-70's):** a LineStar
   capture, then the blend.

   ```bash
   $PROD_PY scripts/linestar_ownership_capture.py --season 2026 --week 4 --out ~/week4-sunday/linestar --label t70
   $PROD_PY scripts/ownership_blend.py --sets ~/week4-sunday/ownership_lag.csv --linestar-dir ~/week4-sunday/linestar \
       --season 2026 --week 4 --out ~/week4-sunday/ownership_blend.csv
   ```

   `ownership_blend.py` (new, this branch) takes the newest capture that has a receipt. So a failed T-70 capture
   leaves Saturday's capture in use, and the blend's receipt names which one it used.

3. **The union step:** two new flags on `scripts/union_reselect.py`.

   ```bash
   --main pmo_x50 --main-own-tilt 0.20 --main-own-source ~/week4-sunday/ownership_blend.csv
   ```

   - The plain-mean rows are solved first, as today. They stay the sleeve's supply, so the sleeve is unchanged, and
     they are written as `book_main_control.csv`, which is Monday's paper comparison.
   - The term's rows are solved second and are the main book, in solve order.
   - The receipt's `config.union.pmo_x50.own_term` records the tilt, the file's sha256, the coverage, the largest
     terms, the rows shared with the plain main, and both books' projected and predicted-ownership sums.

4. **Refusals.** Each is named, exits 2, and happens before any solve:

   | Step | Refuses when | What is built then |
   |---|---|---|
   | capture | no period, no Main slate, fewer than 100 projected players | the blend uses the newest earlier capture |
   | blend | no capture with a receipt; a capture for another week; a capture older than 30 h; a capture that does not match its receipt; fewer than 100 players joined; values that are not percentages | no blended file for this build |
   | union (`OWN TERM REFUSED`) | the file is missing or unreadable; a value is not a number, below −0.5, or a fraction; fewer than 90% of the pool's skill players projected ≥ 5 are named; the tilt is outside (0, 0.5]; the term's solves do not reach K rows | the chain re-runs the union without the two flags: **the book as armed today** |

## 2. Evidence

All panel rows use L13/L18's harness: K = 36, exposure cap 18, DST cap 9, per-game cap 4, salary ≥ $49,000, ≤ 7
shared, a 200,000-lineup field sampled from realized ownership. Each arm is paired with the plain book of the same
bank. Intervals are 90%, from a slate bootstrap stratified by season. This is descriptive work on slates already
examined, and the tilt was chosen on them. A frozen panel on fresh banks is still owed (§5).

### 2.1 The term with the lag + LineStar blend, two banks

| Objective | Bank | Points vs field | Rows over p80 | p89 | p95 | p99 | Paired gain (sd) | 90% interval | Slates up–down | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| plain (as armed) | 1240 | +2.1 | 1.10× | 1.20× | 1.33× | 1.77× | | | | | |
| plain (as armed) | 1241 | +1.3 | 1.08× | 1.12× | 1.34× | 2.01× | | | | | |
| tilt 0.10 | 1240 | +5.0 | 1.27× | 1.35× | 1.40× | 2.01× | +0.131 | [+0.044, +0.217] | 23–13 | +0.171 | +0.091 |
| tilt 0.10 | 1241 | +3.9 | 1.26× | 1.36× | 1.56× | 2.31× | +0.123 | [+0.018, +0.227] | 23–13 | +0.182 | +0.064 |
| **tilt 0.20** | 1240 | +6.1 | 1.42× | 1.48× | 1.53× | 2.16× | **+0.189** | [+0.068, +0.307] | 26–10 | +0.239 | +0.138 |
| **tilt 0.20** | 1241 | +4.9 | 1.28× | 1.34× | 1.50× | 2.16× | **+0.161** | [+0.017, +0.304] | 25–11 | +0.250 | +0.072 |
| tilt 0.30 | 1240 | +6.9 | 1.48× | 1.56× | 1.56× | 2.16× | +0.222 | [+0.081, +0.363] | 26–10 | +0.295 | +0.149 |
| tilt 0.30 | 1241 | +6.2 | 1.39× | 1.45× | 1.57× | 2.16× | +0.219 | [+0.059, +0.377] | 23–13 | +0.335 | +0.103 |
| tilt 0.40 | 1240 | +7.1 | 1.50× | 1.53× | 1.57× | 1.77× | +0.231 | [+0.075, +0.385] | 26–10 | +0.297 | +0.165 |

- Multiples are the book's rate of rows over the line divided by the field's rate.
- The gain rises to 0.20 and is nearly flat from 0.20 to 0.40. 0.20 was the value nominated before these runs and stays
  the recommendation.
- At 0.20 the book gives up 1.5 projected points per row (128.1 → 126.6) and its rows hold 127 points of realized
  ownership against 106.
- The 2024 gain is about half the 2023 gain in both banks.

### 2.2 The recipe matters

| Predictor in the term (tilt 0.20 unless noted) | Bank 1240 | Bank 1241 |
|---|---|---|
| lag model + LineStar (the blend) | +0.189 [+0.068, +0.307] | +0.161 [+0.017, +0.304] |
| base model + LineStar | +0.090 [−0.023, +0.199] | +0.090 [−0.042, +0.221] |
| lag model alone, tilt 0.10 | +0.061 [−0.021, +0.139] | +0.075 [−0.007, +0.161] |
| lag model alone | | +0.070 [−0.056, +0.205] |
| base model alone | +0.008 [−0.071, +0.093] | |
| realized ownership, tilt 0.10 (not available before lock) | +0.286 [+0.187, +0.388] | |

- **The live chain builds the base model** (`arm_week_timers.sh` calls `ownership_sets.py sets` without
  `--lag-features`). With that file the blend gives half the effect, and the interval includes zero.
- The base model alone gives nothing. It is a function of projection, salary and value, which the optimizer already
  uses. The gain comes from what the crowd did last week and from LineStar's independent projection.
- `--lag-features` is not part of the live chain today. Its code path (`live_lag_features`) reads the prior weeks'
  Millionaire ownership from `contest_ownership`; Weeks 1–3 are there.

### 2.3 Under Week 4's dealing

The head layout puts almost half of the main-track entries on the first four rows. Here each contest of the week's
plan is scored at its own line on its own rows, and the result is a multiple of what the field would expect from the
same entries. The plan's counts and lines are private and are not printed.

| Objective | Bank | Tickets, × the field's | Gain, × the field's | 90% interval | Slates up–down | Slates with no ticket |
|---|---:|---:|---:|---|---:|---:|
| plain | 1240 | 1.12× | | | | 25% |
| plain | 1241 | 1.19× | | | | 36% |
| blend, tilt 0.20 | 1240 | 1.44× | +0.32 | [−0.07, +0.71] | 19–11 | 19% |
| blend, tilt 0.20 | 1241 | 1.15× | −0.04 | [−0.36, +0.29] | 14–14 | 25% |
| blend, tilt 0.30 | 1240 | 1.42× | +0.30 | [−0.09, +0.71] | 17–11 | 17% |
| blend, tilt 0.30 | 1241 | 1.34× | +0.15 | [−0.22, +0.53] | 21–10 | 17% |

- Pooled over the banks, tilt 0.20 adds about 12% to the tickets. No interval excludes zero.
- By position in the book, both banks pooled, the average score rises in every block: rows 1–4 from +0.12 to
  +0.30 sd, rows 5–12 from +0.08 to +0.26, rows 13–24 from +0.08 to +0.22, rows 25–36 from +0.03 to +0.24.
- At p95 and p99 the first four rows show no gain (p95 0.97× → 1.11×; p99 1.74× → 1.04×, about five rows against
  three).

### 2.4 The three 2026 weeks

This is a fixed-book replay with the patched tool's own functions, the Week-4 pinned lab clone (`826d8de`), the
archived frames, DraftKings' points and the real Millionaire field.

- The model's ownership is rebuilt from pre-lock inputs.
- LineStar's is its recorded projection, **fetched after the fact and not provably pre-lock**. So the blend rows are an
  upper bound, and the model-only rows are the clean ones.

| Arm (K = 36) | W1 | W2 | W3 | Mean (sd vs field) | Rows ≥ p80 | ≥ p89 | ≥ p95 | ≥ p99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| plain (as armed) | +0.854 | −0.423 | +0.241 | **+0.224** | 37 | 21 | 9 | 0 |
| lag + LineStar, 0.20 | +0.515 | −0.431 | +0.243 | **+0.109** | 26 | 15 | 5 | 3 |
| base + LineStar, 0.10 | +0.639 | −0.342 | +0.354 | +0.217 | 35 | 16 | 7 | 3 |
| base + LineStar, 0.20 | +0.476 | −0.500 | +0.268 | +0.081 | 23 | 13 | 3 | 2 |
| base + LineStar, 0.30 | +0.536 | −0.192 | +0.229 | +0.191 | 26 | 16 | 3 | 1 |
| lag model alone, 0.20 | +0.958 | −0.641 | +0.382 | +0.233 | 34 | 26 | 15 | 6 |
| base model alone, 0.20 | +1.005 | −0.478 | +0.351 | +0.293 | 34 | 25 | 14 | 6 |
| realized ownership, 0.20 (ceiling) | +0.488 | −0.109 | +0.565 | +0.315 | 38 | 22 | 6 | 1 |

- The blend at 0.20 is 0.11 sd below the plain book, all of it in Week 1. Weeks 2 and 3 are level.
- One slate's paired difference has a standard deviation of about 0.44 on the panel, so three weeks carry a standard
  error near 0.25. This neither confirms nor refutes §2.1. It does show that a single week can go against the term:
  even realized ownership trails the plain book in Week 1.
- The plain capped book itself averages +0.22 sd on these weeks. The entered books were +0.09, −0.47 and −0.46.
- Mechanics: every arm solved 36 legal rows in 4 to 10 seconds, so the second sequence adds that much to the union.
  Coverage of the ownership file was 99.5% to 100%.

### 2.5 The predictors on the 2026 weeks

Skill players projected ≥ 5, against realized Millionaire ownership, mean of Weeks 1–3:

| Predictor | Spearman | Top-15 overlap | Mean absolute error (points) |
|---|---:|---:|---:|
| base model | 0.824 | 6.7 | 2.45 |
| lag model | 0.827 | 6.0 | 2.53 |
| LineStar, recorded (covered players) | 0.815 | 8.7 | 2.57 |
| base + LineStar | 0.883 | 9.0 | 2.02 |
| lag + LineStar | 0.879 | 9.0 | 2.05 |

The blend's advantage in L15 shows on the 2026 weeks too, with the same caveat about LineStar's recorded values.

## 3. What these checks changed since the winners study

| Statement in the winners study | Now |
|---|---|
| +0.19 sd [+0.06, +0.31], both seasons | Holds. The second bank gives +0.16 [+0.02, +0.30]. |
| Rows over the cash line +2.4 of 36; weeks with no top-11% row 19% → 8% | Counted over all 36 rows equally. Under the head dealing the ticket gain is +1.5 in one bank and −0.2 in the other. |
| "The lag model alone is never harmful" | Holds (+0.06, +0.07), and it is not established as a gain. |
| Predictor named as "the lag + LineStar blend" | The lag part is required. The chain's existing file is the base model. |
| No 2026 replay | Three weeks: −0.11 sd, not decisive. |

## 4. Known limits

1. **LineStar's recorded projections cannot be proven pre-lock.** The live effect may be smaller than the panel's. O1
   grades the live captures from Week 4.
2. **Timing.** Inactives are announced at 10:30 CT. A capture at 10:36 may precede LineStar's update. Take the T-70
   capture as late as the chain allows, immediately before the union step; the capture and the blend take seconds.
3. **The term reaches the main track only.** The operator's first priorities (the Millionaire, the FFWC, the deep-line
   satellites) draw from the sleeve. At p99 the term shows no measurable effect either way.
4. **A trap for any rebuild of a past week.** `ownership_sets.py sets` for a week that is not the current one finds no
   rows in `player_week_inference`, so `implied_team_total` is empty for every player and the predictions collapse
   (Week 3's top player 5.9% against 28.1% in Saturday's file). O1's LAG and this term must use the file written on
   Saturday, never one rebuilt later. This belongs in `reports/OPEN-DEFECTS.md`.

## 5. Gates before Thursday's freeze, and what runs beside the entry

| Gate | Owner | Pass condition |
|---|---|---|
| Wednesday's smoke runs the three steps of §1 and the union with the two flags | laptop | The receipt carries `own_term`; `book_main_control.csv` exists; the sleeve rows equal those of a run without the flags. |
| The refusal path | laptop | With the blended file removed, the chain prints `OWN TERM REFUSED` and publishes the book as armed today. |
| The build audit | laptop | A check `main_own_term`: a declared tilt has its receipt block, the file's sha256 matches, and the book differs from the control. |
| The lag file on Week 4's slate | laptop, Saturday | Its `pred_own` values sum to at least 280. The 36 panel files sum to 297–621 and top out at 11–26%; the collapsed rebuilds of §4 item 4 summed to 106–223. Below 280, stop and set the tilt to 0. |

Beside the entry, and deciding Week 5:

- **Monday:** score `book.csv` rows 1..K against `book_main_control.csv` at the exact ladders.
- **A frozen lab panel on fresh banks:** control, blend 0.10 and 0.20, lag 0.10, realized as the diagnostic, with the
  head-layout tickets co-reported.
- **O1:** grades the live LineStar captures and the blend against LAG.

## 6. The reference patch on this branch

| File | What |
|---|---|
| `scripts/union_reselect.py` | `--main-own-tilt`, `--main-own-source`, `--main-own-min-coverage`; `own_bonus()`; `pmo_rows(..., bonus=)`; the control rows and `book_main_control.csv`; the receipt block. Without the flags the optimizer call is the one entered in Week 4. |
| `scripts/ownership_blend.py` | The blend builder and its receipt. |
| `tests/test_union_reselect.py` | Six new tests: the term's values, the id matching, every refusal, and the objective with and without the term. |
| `tests/test_ownership_blend.py` | Five tests: the name key, the rule, the refusals, the newest-capture choice. |

Not in the patch, because the chain files are the laptop's and are protected until the smoke:

```bash
# scripts/week_env.sh
export UNION_MAIN_OWN_TILT=${UNION_MAIN_OWN_TILT-0}                       # 0.20 arms the term (operator 2026-09-29)
export OWNERSHIP_LAG=${OWNERSHIP_LAG:-$OUT/ownership_lag.csv} LINESTAR_DIR=${LINESTAR_DIR:-$OUT/linestar}

# scripts/sunday_build_host.sh, before run_union
if [[ "${UNION_MAIN:-mean}" == "pmo_x50" && "${UNION_MAIN_OWN_TILT:-0}" != "0" ]]; then
  ( cd "$PROD" && "$PROD_PY" scripts/linestar_ownership_capture.py --season "$SEASON" --week "$WEEK" --out "$LINESTAR_DIR" --label "$RUN_TAG" ) \
    || echo "LINESTAR CAPTURE FAILED for $RUN_TAG; the newest earlier capture stands"
  ( cd "$PROD" && "$PROD_PY" scripts/ownership_blend.py --sets "$OWNERSHIP_LAG" --linestar-dir "$LINESTAR_DIR" --season "$SEASON" --week "$WEEK" \
      --out "$OUT/ownership_blend-$RUN_TAG.csv" ) || echo "OWNERSHIP BLEND REFUSED for $RUN_TAG"
  UNION_ARGS+=(--main-own-tilt "$UNION_MAIN_OWN_TILT" --main-own-source "$OUT/ownership_blend-$RUN_TAG.csv")
fi
# and in the failure branch, beside the PMO_X50 MAIN REFUSED case:
#   grep -q 'OWN TERM REFUSED' -> drop the two flags from UNION_ARGS, run_union again, copy the refusal into the union dir
```

Tests run on this branch: `tests/test_union_reselect.py`, `tests/test_ownership_blend.py`,
`tests/test_linestar_ownership_capture.py`, `tests/test_audit_build_levers.py` and `tests/test_week_env_defaults.py`
pass, with and without the lab clone on the path.

The whole patched script was also run on two archived Week-3 run dirs (`--rehearsal`, K 36 + sleeve 85, the Week-4
pinned clone), once without the flags and once with tilt 0.20 on a blend built by `ownership_blend.py`:

| Check | Result |
|---|---|
| Sleeve rows 37–121, with the term against without | identical, in order |
| `book_main_control.csv` against the main of the run without the flags | identical, in order |
| Main rows with the term | 36 distinct, 8 shared with the plain main |
| Time for the whole union step | 11 s without the term, 16 s with it |
| The existing audit on the book with the term | `union_main`, `book_rows_legal` and `selector_and_tracks` pass |
| The file named by `--main-own-source` absent | `OWN TERM REFUSED`, no run dir written |

## 7. Reproduction

`reports/lab-handoffs/2026-09-29-ownership-term/` holds the five scripts and a README. All data stays outside the
repository: the standings carry user names, the plan file is private, and the LineStar values are third-party.
