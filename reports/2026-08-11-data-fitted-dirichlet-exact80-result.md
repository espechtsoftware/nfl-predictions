# Data-fitted Dirichlet K exact-80 result

Date: 2026-08-11. Frozen protocol:
`reports/2026-08-11-data-fitted-dirichlet-exact80.md`.

## Result

The treatment is mechanically valid and **rejected**. Production retains the
multinomial within-team usage allocation (`K -> infinity`). The fitted
`K=28.246898139750336` is not adopted and this historical mechanism receives
no parameter adjustment or retry.

The full 107-slate selected weekly-max grid is:

| arm | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 | mean | median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| production control | 34 | 24 | 13 | 7 | 5 | 3 | 2 | 179.836 | 177.52 |
| fitted K | 37 | 21 | 12 | 6 | 4 | 2 | 2 | 179.861 | 178.52 |
| treatment minus control | +3 | -3 | -1 | -1 | -1 | -1 | 0 | +0.025 | +1.00 |

The frozen decision examines 240, 230, 220, 210 and 200 in that order. The
arms tie at 240; the first nonzero difference is `-1` at 230, so the treatment
fails. Its extra 187-point weeks and effectively tied mean cannot veto or
rescue that extreme-tail decision.

The candidate-pool oracle also moves in the wrong high-tail direction:
control clears 43/31/19/9/5/3/2 versus treatment
43/27/18/9/4/2/2 at 187/194/200/210/220/230/240.

## Mechanical validity

- Control exactly reproduces the accepted 54-slate 2023--2025 source: no
  weekly-max mismatch and no candidate difference.
- Control/treatment player snapshots have the exact same 29,285 keys and no
  upstream mismatch. Maximum invariant numeric delta is
  `3.55e-15`; only the seven preregistered distribution-derived outputs are
  excluded.
- Candidate membership changes materially: 3,470 common candidates,
  10,177 control-only and 10,278 treatment-only rows across all 54 paired
  slates.
- Common candidate actuals match exactly. Common simulated means have no
  tolerance violation; maximum absolute delta is `3.0517578125e-05` against
  the registered `1e-4` bound.
- All books contain exactly 80 selected legal lineups per slate and the report
  contains no mechanical failures.

The likelihood result remains scientifically useful: finite K predicted held-
out target/carry allocation better. This exact-80 result shows that the better
conditional usage likelihood did not translate into better extreme portfolio
scores under the production simulator/generator/selector. That distinction is
why the score-free mechanism gate and lineup gate were separate.

## Provenance and next action

- Comparator repair commit: `079de22`.
- Cloud Build: `2050f11d-4a5c-41f9-be68-265d6a02eb39`, 923 tests passed and
  two expected skips.
- Immutable comparator image digest:
  `sha256:f92acc32c07f8118511366c321781d448ea219ed649ac647f063184bcadee38b`.
- Valid execution: `compare-usage-dirichlet-exact80-hz9j2`.
- Machine report:
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1/usage_dirichlet_exact80_comparison.json`.

The retained multinomial law now fixes the common simulator for the already-
frozen active-only TabPFN final-served gate. No production deployment is needed
for this reject decision.
