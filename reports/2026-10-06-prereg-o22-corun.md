# Preregistration: the O-22 six-season co-run, the retrain on the as-of features with two feature re-tests (DRAFT 2026-10-06)

**Status: DRAFT.** It is frozen, with the comparator's sha256 and the launch recipe's identity recorded here, before any
task of the panel runs. The laptop drafts the local launch recipe from `scripts/baseline_panel.sh`, and the reviewer
reviews it. The operator (10-06, through the laptop): "let's not waste any time. I would like you to proceed with
testing unless there is a valid reason for waiting".

**Why** (OPEN-DEFECTS O-22, "Resolved means"):
- Two production features (`qb_cpoe_l6`, `neutral_pass_rate_l6`) leaked week-W information through NULL presence in
  training. Both were adopted on six-season panels in August (Addendum 32: tail weeks 18 → 23; neutral pass rate on
  08-01).
- The fix (as-of construction, `production/o22-leak-fixes-20261005` through `0bc6b6bc`, reviewer- and laptop-approved)
  changes their training values and the defence-allowed table.
- The register requires:
  - a retrain validated with a six-season co-run control on the same image;
  - the Addendum-32 decision re-run on the fixed features;
  - any verdict that relied on these features re-read.
- Study 22a (frozen, `reports/2026-10-05-prereg-study22a-residual-calibration.md`) consumes the control arm's rows.

## 1. Arms (one image, one co-run)
The image is built from integration + `production/o22-leak-fixes-20261005` @ `0bc6b6bc` (O-26 included), with the feature
tables built into RESEARCH datasets (`nfl_features_o22`, `nfl_predictions_o22`). The build-features leakage suite must
pass on the real tables before any task; never weakened. Every arm uses the identical image, seasons, cuts, seeds and
harness settings; only the feature list differs (`build_X` sorts columns, Addendum 34).
- **C (control, the retrain):** today's `NUMERIC_FEATURES` exactly, on the as-of tables.
  - It persists its rows (`CAND_LOG_TABLE` set, `cand_log_required=True`) and is promoted by `scripts/harvest_accept.py`
    (`research_eligible`).
  - Its `panel_run_id` is recorded in the co-run manifest and in study 22a.
- **B (the Addendum-32 / 08-01 re-run):** `DROP_FEATURES=qb_cpoe_l6,neutral_pass_rate_l6`.
- **D (the defence re-test):** `EXTRA_FEATURES` = the seven as-of `017_defense_week_allowed` columns not in
  `NUMERIC_FEATURES`:
  - `epa_per_dropback_allowed_l6`, `epa_per_rush_allowed_l6`, `rz_td_rate_allowed_l6`;
  - `qb_fp_allowed_adj_l6`, `rb_fp_allowed_adj_l6`, `wr_fp_allowed_adj_l6`, `te_fp_allowed_adj_l6`.
  - The July ablation measured "minus defense" at +0.008 MAE, on the leaky table.

## 2. Panel
- **The standing six-season panel:** seasons 2019, 2021, 2022, 2023, 2024, 2025 (`baseline_panel.sh`'s `SEASONS`). The
  replay is walk-forward by season (`nfl-dfs replay --season S --contest gpp --entries 40`), with the harness's canonical
  settings (`GAME_SIM_MODE=possession`, `N_BOOM` 40, `N_CE` / `N_EPISTEMIC` / `N_GUMBEL` 0), as the panel script
  defines them.
- **Run locally** (operator constraint: no heavy Cloud Run), one heavy job at a time, under the launcher registry's
  lane rules. The recipe is frozen at §5.
- **Vacuity:** an arm whose served projections are byte-identical to C's on every slate is a DEAD LEVER (D must change
  the model; B must remove two columns).

## 3. Endpoints and decision rules (frozen, the standing law)
The comparator is `scripts/compare_adoption_panel.py` / `nfl_dfs.research.panel_compare.directional_gate`, the
canonical 40-entry adoption contract:
- the 107 slates aligned;
- clear-194 lift ≥ 2;
- positive in ≥ 4 seasons;
- ≤ 1 negative season;
- mean not worse by more than 0.5;
- oracle-194 not worse.

- **B vs C, read as "do the two features still earn their place".** C is the challenger, with B as the incumbent.
  - If C passes `directional_gate` against B, the features STAY.
  - If it does not, their August adoption is not reproduced on the fixed features. Removing them (B) is then offered as
    a class-R repair under adoption track v2. The operator decides; the paper shadow B (weekly since Week 5) is the
    in-season evidence beside it.
- **D vs C:** D is adopted only if it passes `directional_gate` against C. Otherwise the defence features stay out.
- **Secondaries (no verdict):**
  - served MAE per arm and per position (the July ablation's measure);
  - the high-tail and tail-first gates;
  - the per-season table;
  - the QB over-projection (O-22's +2.47 → +0.07 serve-path finding) per arm.
- **The post-ensemble law:** each verdict holds for this image's served projection and the panel's downstream (the
  replay's generation and selection). It does NOT transfer to the live union / WS / FP book without its own check.
  This is stated beside every verdict.

## 4. Study 22a
22a reads C's promoted rows: `WHERE panel_run_id = <C's id> AND research_eligible`. If C does not persist and promote,
22a is NOT run on it (its frozen rule). 22a's census mode runs outcome-blind on C before its read.

## 5. Integrity and order
1. This freeze, after the launch recipe is reviewed. The recipe's identity, the image or commit identity and the
   comparator's sha256 are recorded here.
2. The feature build into the research datasets, with the leakage suite passing.
3. A smoke: one season, one week, nothing promoted, outcome-blind, on the real artifacts (frozen-chain rule 1).
4. The panel, C / B / D.
5. C's promotion; 22a's census.
6. The reviewer's read of B vs C and D vs C. The laptop re-runs the comparator byte-identically.
7. Addendum, LEDGER, and 22a's read.

Nothing here changes production until the operator decides on a verdict.
