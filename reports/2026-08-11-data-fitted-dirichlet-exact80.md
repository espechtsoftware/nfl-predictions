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

- Accepted source:
  `20260811-lockfix-e80-k1-role12-position-scales-v1`.
- Same-image control:
  `20260811-lockfix-e80-k1-role12-poscal-usage-control-v1`.
- Same-image treatment:
  `20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1`.
- Generate control and treatment only for the 54 Sunday-main slates in
  2023--2025. Splice unchanged accepted-source 2019/2021/2022 results into
  both books for the registered full 107-slate decision.
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
   the accepted candidate pool. Source/control and control/treatment player
   snapshots must have identical keys, actuals, features, market values,
   marginal summaries and means within registered storage tolerances.
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
