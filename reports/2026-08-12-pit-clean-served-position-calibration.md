# PIT-clean served-position calibration retry

Frozen 2026-08-12 before the repaired K3/K1 or role-union outcome was read.
This is the mandatory Tier-1 retry declared in
`reports/2026-08-11-pit-repair-revalidation-scope.md`; it retains the v1
estimator and gate while replacing every stale input mechanically.

## Score-free refit

- Wait for the repaired Tier-1 base and role comparison to write
  `selected_tier1.txt`.
- Use that exact promoted repaired panel as the accepted-row parity source.
- Use K=3 when `selected_base=k3` and K=1 when `selected_base=k1`; role-union
  selection does not alter player draws and therefore adds no calibration
  lever.
- Require `nfl_features.tabpfn_projections_pit_v2` explicitly and the validated
  repaired table/cache lineage. Empirical or old-cache fallback is invalid.
- Retain calibration seasons 2019/2021/2022, untouched evaluation seasons
  2023/2024/2025, 10,000 worlds, seed 0, the 0.750--1.500 by 0.005
  position-factor grid, equal-season normalized q90/q95/q99 pinball objective,
  tie rule, parity checks, and every v1 calibration gate unchanged.

The report must identify its selected panel, ensemble size and canonical-v2
cache. Old factors 0.970/1.005/0.940/1.070 may not be copied or used as a
fallback.

## Licensed exact-80 comparison

Only a clean calibration pass licenses one same-image comparison. Its fixed
IDs are:

- identity control: `20260812-pitclean-e80-selected-position-control-v2`;
- fitted treatment: `20260812-pitclean-e80-selected-position-scales-v2`.

Both run only untouched 2023--2025 slates and exactly reproduce the selected
base/role candidate law, canonical-v2 cache, 80 entries, boom 40 and frozen
seeds. The treatment's sole difference is the unrounded four-factor spec from
the repaired report. Source/control weekly maxima must reproduce exactly;
control/treatment player means and all non-position-scale levers must match.
The 2019/2021/2022 selected-source scores are identical history for both books.

The decision order is `240,230,220,210,200,194,187`; the first nonzero weekly
maximum count difference wins. If all counts tie, mean weekly maximum wins;
an exact tie retains identity. Season signs and average lineup scores are
diagnostic, not vetoes. A passing treatment changes the served position-scale
law but the full repaired source panel remains the downstream player-feature
parity source because mean-invariant scaling does not change those rows.
