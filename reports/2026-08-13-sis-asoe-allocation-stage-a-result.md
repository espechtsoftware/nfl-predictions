# SIS ASOE conditional allocation Stage A result

Date: 2026-08-13

Protocol: `reports/2026-08-13-sis-asoe-allocation-stage-a-protocol.md`

Cloud Run execution: `sis-asoe-allocation-v1-nxhvc`

Immutable image:
`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:d172587c0a45d8e6ebdcec14c941bde022622551ab3dd7f8f54793038e1cd565`

## Decision

**Pass to final-served exact-80 evaluation.** This is a score-free mechanism
pass, not evidence that lineup scores improved and not production adoption.

The 2022-only fit selected `beta=0.07771181538347656`. On untouched
2023--2025 target groups, treatment reduced aggregate mean
Dirichlet-multinomial NLL by `0.0003686816285036402` per group. All three
evaluation seasons improved:

| season | valid geometry | treatment minus control NLL |
|---|---:|---:|
| 2023 | 93.00% | -0.000452286 |
| 2024 | 88.26% | -0.000532460 |
| 2025 | 84.41% | -0.000118217 |

The fixed clustered bootstrap diagnostic was also favorable, with 95% interval
`[-0.000663052, -0.000077982]`. All registered gates passed. The result used
within-team target counts only and read no fantasy points, candidate or lineup
outcome.

The effect is real but small. Stage B must keep player marginal distributions
fixed and test whether the conditional allocation ranks change exact-80 weekly
tail capture. It must not infer a scoring gain from this likelihood result.

## Implementation issue discovered before Stage B

The season replay passes every target-season week to the simulator at once,
while the finite-K usage path currently groups rows by team abbreviation only.
That pools a team's players across different games/weeks. Live one-week
inference is unaffected, but historical finite-K panels are not faithful to
the intended `(game, team)` allocation unit. Repair the grouping, prove a
same-image corrected control, and compare ASOE only against that corrected
control. Historical panels depending on finite-K require revalidation after
this repair; they cannot serve as the direct ASOE control.

The separately completed seed-variance result is materially sensitive, so the
Stage B design must use paired multi-seed evidence or require an effect larger
than the measured incumbent envelope.
