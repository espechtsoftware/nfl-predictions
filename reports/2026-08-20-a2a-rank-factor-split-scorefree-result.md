# A2a Rank-Factor Split Score-Free Census Result

**Date:** 2026-08-20  
**Run:** `20260820-a2a-rank-factor-split-scorefree-v2`  
**Disposition:** `a2a-scorefree-mechanism-passes`

## Frozen identity

- Protocol SHA-256:
  `329379ebd7be5e4a92ee34f8a8dd9ae2f6dca90517a81627800f5756852eeab7`
- Code commit: `afdfe58d10b07f5ae0cc61373ee8586b272c4d4b`
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:765db76cc65f74edfa28915f7b390aafc23a763010768bbff08a8553d50525af`
- Source lock SHA-256:
  `7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c`
- Source catalog SHA-256:
  `f18abb6302730f233665c06b353eb71b6997f3ced3bc91d12a9562a2815f96bc`
- Execution: `atlas-minimal-c-s2023-w1-v1-wn9tq`
- Result object generation: `1787248289501941`
- Result SHA-256:
  `86f72b40b714dd186dd81e698b390eb9e0d5dd3d7b5c96eb42c92f5d213c6774`

The execution completed once with one success and zero failures,
cancellations, or retries. The generation-pinned local result is 884,522
bytes and covers the exact 54-slate by five-block grid: 270 retained source
artifacts with 10,000 worlds each.

## Registered result

Every mechanical invariant passed:

- exact source identities and canonical 54x5 order;
- exact sorted marginal multiset and q90 boom-count preservation for every
  transformed row;
- bit-exact deterministic replay;
- bit-exact QB and unsupported-row preservation;
- unchanged row/world budgets; and
- exactly 52,050,000 one-hot QB-to-WR assignments.

Every directional condition also passed:

- aggregate QB-WR conditional lift increased from `2.571824827` to
  `3.285500472`, with an increase in all five blocks;
- team multiplicity `>=3` fell from `5,048,883` to `2,493,589` events, with a
  decrease in all five blocks; and
- multiplicity `>=2` and `>=4`, QB-RB, QB-TE, WR-WR, RB-RB, and TE-TE were
  each no greater than control under their registered exact-integer tests.

This is a strong score-free mechanism result: the fixed transform moved the
two intended simulated directions without changing player marginals or
worsening any protected dependence cell.

## Licensing boundary

The result used no realized outcomes, candidate scores, lineup scores, or
historical-outcome lease. It sets only
`historical_remeasurement_licensed=true`. It does **not** license exact-80
scoring, the exact-one stack arm, a prospective shadow, or a production
change.

The next permitted step is one separately frozen outcome-bearing dependence
remeasurement under the identical transform and dose. That remeasurement must
report exact skipped-group counts/reasons and coverage, treat QB-WR overshoot
beyond the registered realized equivalence target as a failure, and state
that RB and TE receive attenuation only. Those are accounting and decision
clarifications; they do not alter this frozen mechanism.

If the realized law-shape remeasurement passes, it may license preparation of
the already isolated exact-one-QB-partner construction arm. If it fails, this
exact A2a dose closes without a coefficient sweep or same-corpus dose bump.

