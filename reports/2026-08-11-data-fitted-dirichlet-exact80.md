# Data-fitted K exact-80 lineup protocol

Frozen on 2026-08-11 CDT after the outcome-blind usage-likelihood pass and
before generating any finite-K candidate or lineup score.

## Licensed question

Does the single usage-fitted concentration `K=28.246898139750336` improve the
maximum weekly score in the adopted exact-80 book when it is the only
simulation difference?

The K value and authorization come only from immutable report
`reports/usage-dirichlet-calibration-runs/20260811-data-fitted-usage-k-v1/report.json`
(SHA-256 `7fd2a735d22294a9f75469eda4ce5230c9e20b52620bbb0bb0d01e5a478a6996`).
The report disposition and every frozen likelihood gate must be rechecked by
the launcher. K=8/K=20 scores and all other known lineup outcomes are excluded
from the treatment definition.

## Books and evaluation universe

- Accepted evaluation source:
  `20260811-lockfix-e80-k1-role12-position-scales-v1`.
- Unchanged historical splice source:
  `20260810-lockfix-e80-k1-role12union-8677d21`.
- Same-image control:
  `20260811-lockfix-e80-k1-role12-poscal-usage-control-v1`.
- Same-image treatment:
  `20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1`.
- Generate control and treatment only for the 54 Sunday-main slates in
  2023--2025. Reproduce the accepted position-scale evaluation source and
  splice the unchanged direct-role source's 2019/2021/2022 results into both
  books for the registered full 107-slate decision.
- Each arm must pass a one-week 2024 Cloud preflight before its three immutable
  full-season executions launch. All generation and comparison use one exact
  immutable image built after this protocol and the K lever-identity guard are
  committed.

## Identical configuration

Both arms use exactly:

- K=1 component ensemble, 400-round walk-forward models, possession game
  simulation and the existing team factors;
- 10,000 replay worlds and all existing fixed seeds;
- the adopted final-served factors
  `QB:0.970,RB:1.005,TE:0.940,WR:1.070`;
- CE 0, direct role-belief 12, boom 40, Gumbel 0, replacement slots 12;
- `EPISTEMIC_FAMILY=role_draws`, role seed 7331, and exactly the six role
  fields `target_share_last,carry_share_last,snap_share_last,` plus
  `target_share_jump,carry_share_jump,snap_share_jump`;
- exact 80 distinct legal lineups, default candidate multiple 2, salary/stack
  rules, chalk fade, line 194 selection, market blend, TabPFN marginals and
  empirical fallback from the accepted production path.

Control leaves `GAME_SIM_USAGE` and `DIRICHLET_K` unset. Treatment adds only:

`GAME_SIM_USAGE=dirichlet`

`DIRICHLET_K=28.246898139750336`

`DIRICHLET_K` must be added to the immutable candidate `lever_env` allow-list
before launch. Comparator validity requires the exact K string above, the
Dirichlet mode only in treatment, and equality of every other persisted lever.

## Mechanical gates

1. Revalidate the immutable K report hash, passing disposition/gate, selected
   unrounded value, and 100% population coverage before deployment.
2. Both arms must run the same image and code SHA and complete exactly three
   season books of 80 selected lineups per slate. Candidate acceptance is
   check-only before comparison.
3. Control must reproduce all 54 accepted-source evaluation weekly maxima and
   the accepted candidate pool. Source/control player snapshots must be fully
   identical. Control/treatment snapshots must have identical keys, actuals,
   point-in-time inputs, market/model values, ensemble points and
   pre-simulation means within registered storage tolerances. The following
   seven distribution-derived fields are expected treatment outputs and are
   excluded from that invariance comparison only: `proj`, `proj_tourney`,
   `own_est`, `proj_p10`, `proj_p50`, `proj_p90`, and `proj_std`.
4. Shared candidate actuals must be exact and shared simulated means must be
   within the existing `1e-4` tolerance. Seeds must be identical.
5. Treatment must change candidate membership on at least one slate, proving
   that the fitted within-team allocation affected joint worlds rather than
   silently no-oping. Report common/arm-only candidates, pool oracle, selected
   changes, position contributions and every changed week.

Any pre-score mechanical or packaging failure licenses only a repair that
leaves the panels, K, source, seasons, generator, selector and decision law
unchanged.

## Frozen tail-first decision

For each full 107-slate book, count selected weekly maxima clearing 240, 230,
220, 210 and 200. Inspect thresholds in that order. The first nonzero
treatment-minus-control count decides:

- positive: pass and promote/adopt the treatment;
- negative: reject and retain production control;
- all five tied: neutral and retain production control.

Also report 187/194 counts, mean and median weekly best, pool-oracle counts,
season splits, and paired changed weeks. They are mandatory diagnostics but do
not veto or rescue the tail-first decision. In particular, a lower average is
accepted when the first extreme-threshold difference is positive, matching the
operator's standing objective.

No K adjustment, target/carry-specific concentration, selector line, candidate
budget, seed, season exclusion, or second historical retry may follow this
result.

## Comparator-only repair before a score decision

First comparator execution `compare-usage-dirichlet-exact80-cfvdb` exited
invalid before creating any threshold, weekly-score or position-contribution
report. Its guard had inherited the position-scale experiment's requirement
that marginal summaries remain identical. That requirement is inapplicable to
this mechanism: changing target/carry allocation is intended to change player
marginal widths and tails; p90 punt valuation then changes `proj`, and the
naive ownership proxy and tournament objective change downstream.

The invalid execution proved that every upstream field is invariant: keys,
actuals, salaries, point-in-time features, market/model values, ensemble
points and `mean_projection` match, while differences are confined to the
seven fields registered in gate 3. The invalid report and execution are
preserved under filenames containing `invalid_feature_gate`. The repair only
excludes those seven outputs from the control/treatment input-invariance
check, requires that exact exclusion set mechanically, and leaves the existing
books, K, sources, candidate and score gates unchanged. A new immutable image
and comparator execution are required; the failed report is not a scientific
result.

## Terminal result

Comparator repair commit `079de22` passed regional Cloud Build
`2050f11d-4a5c-41f9-be68-265d6a02eb39` with 923 tests and two expected skips,
publishing immutable digest
`sha256:f92acc32c07f8118511366c321781d448ea219ed649ac647f063184bcadee38b`.
Valid execution `compare-usage-dirichlet-exact80-hz9j2` passed every mechanical
gate and returned `reject`: 240 ties at 2--2, then fitted K loses the first
nonzero comparison at 230 by 2--3. It also loses 220/210/200 by one each.
Production retains multinomial allocation (`K -> infinity`); no retry or
finite-K adjustment is licensed. Full result:
`reports/2026-08-11-data-fitted-dirichlet-exact80-result.md`.
