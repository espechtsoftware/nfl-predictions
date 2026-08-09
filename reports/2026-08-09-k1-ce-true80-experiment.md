# K=1 cross-entropy true-80 experiment

Status: preregistered before querying any new CE candidate or portfolio
outcome on the corrected Sunday-main universe.

## Why this arm is still eligible

The earlier cross-entropy (CE) rare-world result was measured before the
historical-universe, salary, DST-scoring, and deterministic-rank repairs. Its
production conclusion was explicitly superseded by Addendum 101. CE has never
been evaluated against the accepted true-80 K=1 panel
`20260808-e80-k1-c616390`. The later priority order allowed one corrected K=1
CE confirmation after the K=1 model-only and salary-floor deletions; both are
now complete and closed.

This is a mechanism confirmation, not a CE parameter search. Do not change
the CE allocation, rounds, elite fraction, game count, seed, K, entry count,
salary floor, blend, selector line, or candidate multiple after results are
seen.

## Frozen source and treatments

All arms use immutable generation image
`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`,
code identity `c616390`, possession simulation, K=1, 45/55 model/market blend,
$49,000 salary floor, candidate multiple 2, 80 entries, selection line 194,
and the existing fixed simulation/generator seeds.

| Arm | Panel ID | Generation budget | Purpose |
|---|---|---|---|
| Accepted source | `20260808-e80-k1-c616390` | `N_CE=0,N_BOOM=40` | promoted K=1 control |
| Union diagnostic | `20260809-e80-k1-ceunion-c616390` | `N_CE=12,N_BOOM=40,CE_SEED=1701` | test whether CE adds actual candidate opportunities |
| Fixed replacement | `20260809-e80-k1-ce12-c616390` | `N_CE=12,N_BOOM=28,CE_SEED=1701` | equal-generator-budget scoring arm |

The union diagnostic is not adoptable because it adds generator budget. It
must preserve all source upstream player features and produce active, unique
`ce`-tagged candidates. The fixed replacement must change only the declared
12-for-12 generator allocation. Its final per-slate candidate caps are frozen
from source pool sizes before treatment outcomes and must match the source on
all 107 slates.

## Frozen staged gates

Do not launch the fixed replacement unless the union mechanism is valid and
adds at least two candidate-pool oracle weeks at 200, with non-worsening pool
oracle counts at 210/220/230/240. Report the complete
187/194/200/210/220/230/240 oracle grid and season attribution. This gate is
allowed to inspect union candidate outcomes because the fixed replacement
rule, seed, budget, and acceptance thresholds are frozen here first.

If the union gate passes, the fixed replacement is adopted historically only
if:

- the panel and CE mechanism audits have zero failures;
- selected weekly maxima gain at least two weeks at 200;
- selected weekly maxima do not worsen at 210;
- candidate-pool oracle weeks at 200 do not worsen; and
- the full extreme-tail grid is reported without concealing a 220/230/240
  tradeoff.

Season signs and mean weekly maximum are diagnostics under the operator's
tail-first utility, not automatic vetoes. A failure closes this exact CE arm.
Do not tune a CE dose or seed on these 107 outcomes.

