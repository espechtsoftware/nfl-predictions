# TabPFN active-label PIT-clean cache addendum

Frozen 2026-08-11 before generating either repaired cache and before querying
any repaired active-label lineup outcome.

This is the mechanism-preserving repair authorized by
`reports/2026-08-11-tabpfn-active-label-exact80-protocol.md` and the scoped
rerun plan. It changes the common upstream feature build only; it does not
change the active-label question, context law, model, hyperparameters, target
seasons, score-free gate or eventual lineup decision.

## Immutable v2 cache identities

- run: `20260811-tabpfn-active-label-v2-pit-clean`;
- control: `nfl_features.tabpfn_active_label_control_v2`;
- treatment: `nfl_features.tabpfn_active_label_treatment_v2`;
- target seasons: 2022--2025;
- training context: all strictly earlier seasons with non-null labels;
- treatment-only filter: `was_active = TRUE` before sampling;
- context maximum 28,000, seed 7, four TabPFN estimators, TabPFN 2.2.1;
- exact tracked feature contract, unchanged from v1; and
- same immutable GPU image/code SHA for both arms.

Both destinations are write-once. Cache generation uses `WRITE_EMPTY`, never
truncate/replace. The report records training-table modified time, schema hash,
complete-table checksum, row/activity counts and feature-contract hash. Both
arms must match those source identities exactly.

## Mechanical gate

The existing v1 cache validator is parameterized only for the registered v2
pair. It still requires exact 52,307 unique target keys, identical sources,
features/hyperparameters/device, finite ordered quantiles, zero sampled
inactive labels in treatment, positive sampled inactive labels in every
control fold and at least one changed prediction. A changed target row count or
key set is invalid rather than silently accepted.

## Downstream gate

After mechanical validation, repeat the identical final-served comparison:
walk-forward arm-specific position-factor schedules, common terminal usage
law, active RB/WR/TE aggregate 30-point Brier primary gate and mean-preserving
world scaling. The v2 report must be frozen before any exact-80 launch. A v2
fail closes active-only labels; a v2 pass mechanically substitutes only the
new cache/report ids and generated schedules into the already-frozen exact-80
protocol.

The repaired runner is separately identified as
`scripts/cloud_tabpfn_active_label_final_served_v2.sh`. It requires the
validated v2 cache report, repaired production-lineage panel and repaired
fitted-K comparison as explicit immutable inputs. It parses the comparison's
machine disposition before launch: a valid pass supplies that report's exact
positive `fitted_k`; a neutral/reject supplies production multinomial. The
Python gate independently requires the same selected branch and exact K. The
old hardcoded v1 K and old panel cannot enter this execution.
