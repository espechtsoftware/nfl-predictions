# Frozen protocol: B1 corpus-tail model and exact-80 prospective challenger

**Protocol ID:** `20260820-b1-corpus-tail-model-v1`
**Status:** FROZEN 2026-08-20 after the real-artifact outcome-blind smoke
**Class:** one historical one-shot followed, only on a full pass, by a
default-off six-week 2026 prospective shadow. Production remains unchanged.

## Question and boundary

Can one fixed, simple model using only information known before lock identify
the genuinely high-scoring lineups already emitted by the valid B1 corpus, and
can its deterministic exact-80 portfolio improve the current selector's weekly
maximum and 200+/210+ conversion without losing 194 coverage?

The training target is our own generated roster's absolute DK score. A Milly
winner's identity, score, roster, ownership, distance or world is never a
feature or target. Winner comparison is not an endpoint. The experiment does
not infer construction quotas from winning rosters and does not rewrite a
generator, simulator, world law or production selector.

This is one fixed attempt. There is no feature search, coefficient sweep,
threshold sweep, hyperparameter grid, alternate overlap cap, alternate target
or post-result repair. A historical failure closes this exact model and
selector contract on B1; it does not license another fit on these outcomes.

## Frozen population

- Exact B1 source: the 51 panels in `ALL_PANELS` in
  `scripts/run_b1_union_c_census.py`.
- Expected source facts: 698,172 candidate appearances, 54 slates and 127,778
  distinct DK-legal `(season, week, roster)` rows after deduplication.
- Seasons: 2023, 2024 and 2025 only.
- Canonical current-selector control and challenger candidate budget:
  `20260815-atlas-money-worlds-r0-v1`.
- The current control is that canonical panel's exact stored ranks 0--79. The
  challenger sees exactly the same canonical candidate roster set and also
  submits exactly 80 lineups. Training may use the full deduplicated B1 union;
  candidate or entry budget may not be enlarged for the challenger.

Repeated appearances of the same slate/roster collapse to one row. Actual
score must agree across every appearance to `1e-6` or execution aborts.
Pre-lock panel signals collapse by the fixed mean/max summaries in code;
panel count is retained as `log1p(appearances)`. Panel identity, family/tag,
old selected flag, selected rank and realized ownership are audit fields, not
model inputs. The canonical player catalog independently reconstructs salary,
DK position shape, game/team spread, stack/bring-back shape and position spend.

## Frozen model

The only estimator is uncalibrated-by-addon, L2 logistic regression for
`actual_score >= 200`:

- `sklearn.linear_model.LogisticRegression`;
- `C=1.0`, `solver=lbfgs`, `class_weight=None`, `max_iter=2000`;
- median imputation and z-standardization fitted inside each training fold;
- every season-week receives equal total sample weight;
- no hyperparameter grid and no fitted probability calibrator.

The feature vector, in exact order, is:

1. salary;
2. mean/max simulated probability of 194 (`p_line`);
3. mean/max simulated mean;
4. mean simulated standard deviation and q50;
5. mean/max q90 and q99;
6. mean/max within-panel simulated-tail-rank percentile;
7. log appearance count;
8. games and teams represented;
9. maximum same-team and same-game blocks;
10. QB teammate and bring-back counts;
11. QB/RB/WR/TE/DST salary spend; and
12. WR/TE FLEX indicators.

The score is a probability of 200+. The same single score is evaluated against
the sparse 210+ label and as a continuous/ranking companion against actual DK
score; no second model is fit.

## Frozen validation

### Candidate-level generalization

Primary out-of-fold predictions are leave-one-season-out: fit two whole
seasons, score the untouched third, and concatenate the three holdouts. This
tests season transport while making every prediction outcome-unseen to its
fit. A chronological companion separately fits 2023 -> scores 2024, then fits
2023--24 -> scores 2025. It is report-only; no disagreement permits choosing a
different scheme.

The naive comparator is pre-lock `p_line_max`. The fold-training prevalence is
the calibration baseline. Candidate-level gates are all required:

1. 200+ average precision exceeds realized 200+ prevalence;
2. 200+ average precision exceeds `p_line_max` average precision;
3. 210+ average precision exceeds realized 210+ prevalence; and
4. 200+ Brier score beats the fold-training-prevalence Brier score.

Also report 210+ `p_line` average precision, predicted versus realized 200+
rate, Spearman correlation with continuous score and all chronological
companion metrics. These do not replace a failed primary gate.

### Exact-80 challenger

Within each held-out canonical candidate pool, order by model score, then
`p_line_max`, `sim_q99_max`, `sim_mean_max`, then ascending canonical roster
key. Greedily admit a roster only when it shares at most seven players with
every already admitted roster. If this pass cannot fill 80, deterministically
backfill the highest remaining rows in the same order and report the exact
backfill count. The overlap cap and fallback are frozen; there is no alternate
redundancy penalty.

The stored current selector is the control. A naive `p_line_max` exact-80 book
using the identical redundancy rule is report-only. Every historical challenger
gate is required:

1. exact candidate budgets and exact 80-entry budgets match;
2. mean weekly maximum strictly improves;
3. number of 200+ weekly maxima strictly improves;
4. number of 210+ weekly maxima is no worse; and
5. number of 194+ weekly maxima is no worse.

No winner-relative endpoint, fitted cutoff or statistical multiplicity choice
may be substituted.

## One historical look and license table

Historical mode must hash-match this frozen protocol and validate a live,
generation-pinned shared historical-outcome lease for this exact run ID. The
lease generation must still be the current live object. Before issuing the
query that selects `actual_score`, the runner must create exactly one remote
object at
`gs://nfl-predictions-503414-raw/research/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1/historical-attempt.json`
with `if_generation_match=0`, then retain its generation/hash locally. An
existing attempt, including one left by a crash before or during the query,
closes the one-shot and forbids retry. Source-row, deduplicated-row, panel and
slate counts must exactly reproduce B1. Outputs are create-only and
source/hash bound.

| Result | Allowed | Forbidden |
|---|---|---|
| Any historical gate fails | record failure and close this contract | model artifact, retry, retune, shadow, production |
| Every historical gate passes | write the portable frozen model artifact; deploy/collect the default-off 2026 shadow | production or historical refit |
| Historical plus prospective gate pass | production review is licensed | automatic production mutation |

Production remains off even on a historical pass. The portable JSON artifact
contains imputation, scaling, coefficients, intercept, exact feature order and
its content hash; it contains no pickle or winner value.

## Default-off 2026 shadow

`CORPUS_TAIL_SHADOW_ENABLED=1` is required explicitly. A shadow invocation
must use an unseen 2026-or-later slate, only rows with
`labels_complete=false`, one named canonical current-selector panel, and all
named companion panels available at the same pre-lock snapshot. It freezes:

- the exact source/query/content identities and snapshot time;
- identical control/challenger candidate counts;
- the ranked current exact-80 control;
- the ranked model exact-80 challenger and pre-lock model scores;
- overlap rejections/backfills; and
- literal false flags for outcomes, winner use and production license.

The snapshot ID must be a nonempty string and its timestamp must be a
timezone-aware ISO-8601 string. The runner derives that timestamp as the later
of the two retained BigQuery candidate/catalog completion timestamps, requires
the returned panel set to equal the requested set exactly, and requires both
queries to finish before the explicit timezone-aware contest lock timestamp.
The receipt binds all query jobs, source content hashes, panels and lock time.
Boolean source and grading fields are exact JSON/pandas booleans; integers and
strings such as `0`, `1`, `"false"` or `"true"` are invalid rather than
coerced.

The receipt writer is create-only with a SHA-256 sidecar. A historical model
without literal `historical_gate_passed=true` is rejected. Grading occurs only
after outcomes land and never changes a frozen roster.

## Frozen six-week prospective adoption gate

Use exactly Weeks 1 through 6 of one 2026-or-later season. There is no best-six
choice, later starting point or automatic extension. The adoption command
accepts only a canonical grade manifest whose six week rows hash-pin the
create-once shadow receipt and a canonical settled-score file. It validates
both exact-80 ordered roster lists, requires the score file to cover exactly
their union, validates its retained `replay_candidates_staging.actual_score`
query identity, and derives both weekly maxima itself. It does not accept
caller-supplied maxima, budgets, Boolean validity claims, CSV rows or a
best-six selection. All six must have valid pre-lock receipts, complete
labels, identical candidate budgets and exact 80-entry books. Every condition
is required:

1. challenger mean weekly maximum strictly exceeds control;
2. challenger produces at least one additional 200+ week;
3. challenger 210+ week count is no worse;
4. challenger 194+ week count is no worse; and
5. challenger wins at least three of six paired weekly maxima.

A pass licenses a reviewed production-promotion decision, not an automatic
mutation. A null/fail leaves production unchanged and closes this artifact.
Winner score and identity remain absent even from this gate.

## Outcome-blind real-artifact smoke

The exact final runner completed one source smoke on 2023 Week 1 before this
freeze. Its SQL selected identities, pre-lock simulation fields, salary,
structure and stored selection metadata only; it did not select
`actual_score`, player actuals, winner data, payouts or ownership outcomes.

- Result: `OUTCOME_BLIND_REALITY_SMOKE_OK`
- Candidate query job: `308dc620-9ca8-4745-bc07-4a552f39a4f4`
- Player query job: `fd92c1d5-a9a5-4909-aab3-806e8d3a0404`
- 51 panels; 13,008 candidate rows; 773 catalog rows
- 2,277 deduplicated rosters
- canonical pool 255 candidates; canonical selected 80
- Receipt:
  `reports/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1/outcome-blind-smoke-locked.json`
- Receipt SHA-256:
  `7b5a7c35f05d10c14f0394f400e41b72fbecfa5278dfb9053892e5bdb1990e00`
- `realized_outcome_columns_read=[]`; `winner_fields_read=[]`

No historical outcome, model fit, cloud execution, build, job update or lease
occurred during this smoke.

The earlier smoke receipts remain preserved as nonlicensing evidence. The
receipt above is the final locked smoke, repeated after the current-lease,
one-shot-attempt, exact source/lock and receipt-derived grading repairs and
before any historical read.

## Exact implementation pins

- B1 protocol:
  `2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789`
- B1 report:
  `4e654a58563391ed3020b0b221756070cd07fb10e962fc80e4bbedfd5f2631b6`
- B1 runner:
  `fc12e2871d638995603258f16d9e1beeee68f8a885ba3a53f9f32790d62c608f`
- Science module `src/nfl_dfs/research/b1_corpus_tail.py`:
  `44a81cda46301f12abbc23a31f2848dfe33d8ab964418be0ba32983289d31a04`
- Runner `scripts/run_b1_corpus_tail_model.py`:
  `5e3eefd42adf8d62cc23832f8581c68c5890ec5265d85c69d88b4efb2c0c7223`
- Science tests `tests/test_b1_corpus_tail.py`:
  `445a3651c25566cb3d30210e0c1ddba85b9fa48bbc6149a1c8ea54f94e023d0e`
- Runner tests `tests/test_b1_corpus_tail_runner.py`:
  `d1168387bd13332286ef839bff52212ad3c680a98396b5b6266da13c208fcfb9`

Focused validation before freeze: 14/14 tests green; both implementation files
compile. The historical command must receive this protocol file's exact
external SHA-256; the runner does not pin its own mutable hash.
