# Fantasy Points true Route Share experiment

Status: preregistered and implemented before any paid Route Share value was
joined to a realized player outcome. Acquisition/schema/identity availability
only has been inspected. No player-tail metric or lineup score from this
treatment has been queried.

## Question

Does strictly lagged true team Route Share add held-out 30-point player-tail
signal beyond the corrected pre-lock projection and the target/snap/vacancy
features already in the model?

This is the first paid-data test because the no-cost pass-play participation
proxy passed its purchase gate, and the paid source covers 93--96% of
offensive candidate-roster appearances in each 2022--2025 season. It is not a
license to add every Data Suite field or to treat postgame Week N data as
available for a Week N lineup.

## Immutable sources

Use corrected accepted K1 player snapshots from panel
`20260810-lockfix-e80-k1-8677d21` and only these untouched vendor files:

| Season | SHA-256 |
|---:|---|
| 2022 | `68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637` |
| 2023 | `c4940b8d7163b2baf0734b0b70d5c5c9bee456c1c004c61341ebcc5aa97a81d0` |
| 2024 | `45b68bb3fef0cd74c96ad88943141f37865647ef699f1e41553fca895f5408f7` |
| 2025 | `305b5ff5523e09645ef41bd7f3c1f290b035e3d97b5f1d0c942815feebc43717` |

Licensed source rows remain under ignored `fantasy-points/` and must not be
committed. Any private warehouse load records source filename/hash on every
row and excludes Windows `Zone.Identifier` sidecars.

## Frozen normalization

1. Decode UTF-8 with BOM and require the exact 25-column Route Share schema.
2. Unpivot `W1`--`W18`; never use rank, games, or season `TM RTE %` as a
   predictive feature.
3. Map `FB` to `RB`; apply the existing explicit team bridge (`ARZ→ARI`,
   `BLT→BAL`, `CLV→CLE`, `HST→HOU`, and historical relocations).
4. Resolve GSIS IDs using normalized name plus position, with team as a
   disambiguator. Persist every unresolved or ambiguous row; do not choose one
   by input order or consult fantasy outcomes.
5. Coalesce duplicate player rows only when their populated weeks do not
   conflict. The known 2022 Brock Wright split is valid under this rule; any
   conflicting player-week fails the import.
6. Store percentage values as fractions in `[0, 1]`, retaining the original
   percentage and source provenance for audit.

The outcome-blind dry run resolves 902 players and finds 56 unresolved and two
ambiguous vendor season rows across all four files. Those exceptions must be
reported explicitly by the importer. They do not currently prevent the
coverage gate below.

## Point-in-time feature construction

Order observations by `(season, week)` and expose only rows strictly earlier
than the target slate. A prior-season observation may predict a new season;
the model receives an explicit cross-season indicator. A missing route share
is missing, never zero. For each target player freeze exactly four added
inputs:

- `fp_route_share_last`;
- `fp_route_share_l4` (unweighted mean of up to four prior observations);
- `fp_route_share_jump` (latest minus the preceding observation); and
- `fp_route_cross_season` (latest observation precedes the target season).

Persist source season/week and prior-observation count for leakage auditing,
but do not add them to the model. Assert source `(season, week)` is less than
target `(season, week)` on every non-null row.

An outcome-blind dry run found a strictly prior route observation for 82.07%
of corrected 2024 RB/WR/TE snapshot rows and 82.95% in 2025. In those folds,
1,504 and 1,462 latest observations respectively come from a prior season,
which is why the cross-season indicator is frozen rather than silently
mixing them.

## Frozen player-level comparison

Evaluation rows are corrected K1 RB/WR/TE snapshots with authoritative actuals,
a non-null pre-lock `mean_projection`, and at least one prior true-route
observation. Both arms use identical rows.

- Held-out 2024 trains on eligible 2022--2023 rows.
- Held-out 2025 trains on eligible 2022--2024 rows.
- Regression target is `actual - mean_projection`; model is
  `Ridge(alpha=10.0)` and score is residual MAE.
- Classification targets are `actual >= 20` and `actual >= 30`; each uses
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` and Brier loss.
- Numeric inputs use training-fold median imputation and standardization;
  position uses most-frequent imputation and one-hot encoding with unknown
  values ignored.

Frozen control inputs are `mean_projection`, salary, position,
`target_share_last`, `target_share_jump`, `snap_share_last`,
`snap_share_jump`, `team_vacated_target_share`, `depth_rank`, and
`games_played_prior`. The treatment adds only the four fields above. Report
row/missingness counts, MAE, 20- and 30-point Brier, WR/TE-only Brier,
calibration deciles, and both season folds plus aggregate.

## Frozen gate

The Route Share player-tail mechanism passes only if:

1. strictly prior coverage is at least 80% of eligible corrected RB/WR/TE
   snapshot rows in both 2024 and 2025;
2. aggregate 30-point Brier is lower for treatment;
3. aggregate WR/TE-only 30-point Brier is lower for treatment; and
4. treatment 30-point Brier is no more than 1% worse in either held-out
   season.

20-point Brier and residual MAE are mandatory diagnostics, not vetoes, because
the operator's utility explicitly prioritizes exceptional scores. Passing
licenses one separately preregistered route-tail candidate-union test. It does
not alter production projections, the accepted lineup policy, or authorize a
feature/window/regularization retry. Failure closes Route Share as a 2026
lineup input; Target Share or Advanced Receiving fields remain separate
hypotheses rather than retries of this test.

## Pre-outcome implementation and import audit

The narrow importer is `ingest/fantasy_points_route.py`; CLI command
`import-fantasy-points-route` is audit-only unless passed `--write`. It verifies
all four hashes and exact schemas, preserves unresolved rows, and creates the
private raw table only with `WRITE_EMPTY`. An existing byte/provenance-equivalent
table is an idempotent no-op; a non-identical table aborts rather than being
overwritten.

The four local files normalized to 27,305 player-week rows. Private table
`nfl_raw.fantasy_points_route_share` was created once with 26,881 resolved
weekly rows, 1,029 resolved players, all four source hashes, and Route Share
range `[0,1]`. At the vendor season-row level, 2,472 resolve, 57 remain
unresolved, and one is ambiguous. A repeated `--write` audit returned
`already-identical` and performed no write.

The diagnostic implementation is
`analysis/fantasy_points_route_share.py`, CLI command
`fantasy-points-route-diagnostic`, and guarded Cloud runner
`scripts/cloud_fantasy_points_route_diagnostic.sh`. Four focused tests pass,
including source provenance/identity normalization, conflicting player-week
rejection, exact earlier-week/cross-season construction, and the 30-point gate.
Python compilation, shell parsing and whitespace validation are clean.
Exact-tree Cloud Build `24d0a97b-b51e-43c0-a733-332f24064d25` passed 749 tests
with 2 skipped and produced immutable digest
`sha256:a08ae363d937a428849f62b3bd07ea7527d8dd4ab487496d0408fa3da9e49d42`.
The one licensed outcome query is running as Cloud Run execution
`fantasy-points-route-diagnostic-rthzs`. No intermediate result, alternate
model, window or retry may be used.

## Result

Execution `fantasy-points-route-diagnostic-rthzs` completed successfully in
2m17s and the frozen mechanism **passed every gate**. Strictly prior coverage
was 82.35% in 2024 and 83.02% in 2025. Across 13,288 held-out player-weeks,
the primary 30-point Brier loss improved from `0.00968358` to `0.00965675`,
and WR/TE-only 30-point Brier improved from `0.00763166` to `0.00760188`.
The treatment also improved 20-point Brier, while residual MAE worsened
slightly (`2.88299` to `2.89248`); MAE was a preregistered diagnostic rather
than a veto because this experiment targets exceptional scores. Neither
season's 30-point Brier worsened, so the per-fold safeguard passed.

The machine disposition is `route-share-player-tail-passes`. This licenses
exactly one separately preregistered route-tail candidate-union experiment;
it does not yet adopt Route Share in production. The immutable report and raw
log are tracked under
`reports/fantasy-points-route-runs/20260810-fp-route-share-v1/`.
