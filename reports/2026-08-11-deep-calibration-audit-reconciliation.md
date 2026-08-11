# Deep calibration audit reconciliation

Date: 2026-08-11

This tracked note reconciles the operator-supplied, untracked
`2026-08-11-deep-analysis-calibration-and-data-audit.md` with the actual
served-path code before running its proposed calibration work. The outside
review remains unmodified.

## Verified findings

- `calibration.fit_widen_factors` is defined and tested but has no production
  or research call site.
- `DEFAULT_WIDEN` still contains the factors documented as fitted on pooled
  2019+2021 data, despite multiple later simulator changes.
- The accepted served-tail report's positional q99 exceedance split is indeed
  WR 1.8806%, RB 1.5653% and TE 0.7368% versus 1% nominal.
- Several materialized candidate features remain outside the canonical model.
  They must not be swept until the calibration question is resolved.

## Material mechanism correction

The review treats `DEFAULT_WIDEN` as though it directly controls every final
served distribution. In the current lineup path it is applied before TabPFN
marginal shaping. `_tabpfn_marginals` uses only each row's stable ordinal
ranks and replaces its values with cached TabPFN quantiles. Positive
mean-centred widening preserves those ranks and is erased for covered rows.

The immutable served-tail report records `tabpfn_coverage = 1.0` overall and
within every evaluated position on all 13,876 accepted 2023--2025 RB/WR/TE
rows. Therefore stale `DEFAULT_WIDEN` factors are a real maintenance defect
for summary projections and uncovered fallback rows, but they cannot be the
cause of the measured final-path positional imbalance or a shared confounder
for those fully covered final draws.

This does not close the useful recommendation. A position-specific scale
applied **after** TabPFN shaping and market blending can change the actual
worlds used for candidate generation and selection. That is the correct layer
for the proposed test.

## Action frozen before a new replay

`reports/2026-08-11-served-position-calibration-refit.md` preregisters one
combined diagnostic:

1. invoke the existing `fit_widen_factors` unchanged on the current summary
   layer and report its held-out coverage; and
2. fit independent QB/RB/WR/TE, mean-invariant final-served factors on
   2019/2021/2022, then gate them once on untouched 2023--2025 calibration,
   pinball, CRPS and Brier metrics.

The final-served fit permits narrowing as well as widening and freezes the
outside review's WR-up/TE-down directional prediction. It cannot generate or
score a lineup. A passing gate licenses one separately preregistered exact-80
lineup comparison; a failure closes this calibration hypothesis.

The data-fitted allocation-concentration claim and free unused-feature blocks
remain lower-priority hypotheses. Neither is authorized until this R1/R2
diagnostic resolves, and neither may be tuned on the 107 known lineup
outcomes.

## Corrected-review follow-up and result

The outside audit was revised after this code audit and now explicitly agrees
that upstream widening is erased on TabPFN-covered rows. Its replacement
R1-prime stage decomposition was run descriptively and is tracked in
`reports/2026-08-11-tabpfn-stage-calibration-audit.md`. The imbalance is
already present in cached TabPFN q99 values (QB/RB/TE/WR
1.184%/1.439%/0.711%/1.635%); the later market shift raises final RB/WR to
1.565%/1.881% and leaves TE at 0.737%.

The independently frozen final-served fit then passed every held-out gate at
factors QB 0.970, RB 1.005, TE 0.940 and WR 1.070. This is positive
distribution evidence, not yet a scoring result. Its sole licensed next step
is the separately preregistered exact-80 lineup comparison.

## Remaining recommendation corrections

Two lower-priority items in the revised outside audit survive, with precise
constraints:

- Its R3 route-share retry cannot refit `DEFAULT_WIDEN`, because that remains
  upstream of and erased by TabPFN on covered rows. A valid new route
  comparison would fit **each arm's final-served position factors** on the
  calibration seasons, gate both on untouched distribution metrics, and only
  then compare lineups. Whether that work should use identity or the passing
  position-scale book as control depends on the active lineup experiment, so
  it is not frozen prematurely here.
- Its R4 allocation recommendation is genuinely different from selecting
  another K on known lineup scores. The repository's SBI work established
  only synthetic identifiability of `usage_dirichlet_k`; it did not fit K to
  real usage. A valid diagnostic would train the existing component model
  strictly leave-season-out, normalize its fitted target/carry means within
  team-week, and estimate K from the conditional realized allocation
  likelihood. This is lineup-outcome-blind. It must freeze one global value
  and pass an untouched usage-calibration/likelihood gate before any lineup
  replay; K=8/K=20 lineup results cannot participate in the fit.

These are queued scientific diagnostics, not authorizations to run score-
selected grids. The active position-scale exact-80 result remains first.
