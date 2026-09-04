# PREREG-065 redist-only candidate-lineage diagnostic

Date: 2026-09-04 UTC

Scope: read-only descriptive reconstruction from the already opened and
independently reproduced experiment-094 cohort. This diagnostic does not alter
the frozen PREREG-065 verdict, promote an arm, change experiment 095, or create
new adoption authority.

## Question

Experiment 094 increased the aggregate number of candidate roster instances at
or above 200 by 63. Was that increase caused by identifiable newly generated
lineups, and did the incumbent DEMAX retrieval retain them?

## Method

Production loaded the three frozen, validated PREREG-065 runs:

- `094b680r1-20260904T103431Z`;
- `094b681r1-20260904T103705Z`;
- `094b682r1-20260904T121250Z`.

Within every `(season, week, bank)` cell, candidates were joined by the frozen
canonical `roster_sha256` and partitioned as:

- `REDIST_ONLY = PG_REDIST - PG_CTRL`;
- `CTRL_ONLY = PG_CTRL - PG_REDIST`;
- `SHARED = PG_REDIST intersect PG_CTRL`.

The canonical hashes were then joined to the frozen settlement rows and
candidate traces. Selection means inclusion in that arm's exact K80 DEMAX
book. `beneficiary-only` retains PREREG-065's pre-lock definition: a lineup
contains at least one same-team/same-position-group beneficiary and no modeled
questionable/doubtful player.

These are roster instances across 72 slates x three fresh banks. They are not
claimed to be globally unique rosters across weeks or banks.

## Exact results

| Cohort | Candidate instances | Selected K80 | Beneficiary-only |
|---|---:|---:|---:|
| REDIST_ONLY (added) | 38,349 | 3,671 | 25,574 |
| CTRL_ONLY (displaced) | 38,355 | 3,970 | 13,585 |
| Shared | 134,281 | 13,310 | 48,482 |

| Threshold | Added | Added selected | Added beneficiary-only | Added selected beneficiary-only | Displaced | Displaced selected | Net supply |
|---:|---:|---:|---:|---:|---:|---:|---:|
| >=200 | 131 | 18 | 103 | 16 | 68 | 17 | +63 |
| >=210 | 59 | 11 | 48 | 9 | 31 | 6 | +28 |
| >=220 | 21 | 4 | 18 | 4 | 12 | 3 | +9 |
| >=230 | 6 | 2 | 6 | 2 | 5 | 2 | +1 |

## Interpretation

The `+63` is a net difference, not a set of exactly 63 added lineups.
Redistribution created 131 new >=200 candidates while displacing 68 >=200
candidates.

The gain is strongly localized: 103/131 (78.6%) of the added >=200 candidates
are beneficiary-only. The same localization persists at the higher thresholds:
48/59 added >=210, 18/21 added >=220, and all six added >=230 candidates are
beneficiary-only.

Incumbent retrieval converts the new supply poorly. DEMAX selected 18/131
(13.7%) of the added >=200 candidates, versus 17/68 (25.0%) of the displaced
>=200 candidates selected by the control book. This is descriptive hindsight,
but it gives a precise first-loss cohort and confirms that the 094 opportunity
is not merely an aggregate count artifact.

## Consequence for the authorized queue

Experiment 095 already carries the correct next measurement: exact
`redist_only` roster identity, beneficiary status, and per-retrieval-law capture
on the crossed PG_REDIST pool. It should proceed unchanged.

If the generic conditional-novelty selector does not capture the cohort, the
next bounded hypothesis is a beneficiary-conditioned admission/retrieval
sleeve. It must use only pre-lock features, for example beneficiary-only status,
held-out 200/210 coverage, tail quantiles, and marginal redundancy against the
current book. Realized score may define the retrospective target and evaluate a
frozen walk-forward rule, but it must never enter candidate generation or live
selection.

The diagnostic also requires preserving the displaced cohort: a future rule
must report added high-scorer recall, displaced high-scorer loss, and net fixed-
budget retention rather than reporting added candidates alone.
