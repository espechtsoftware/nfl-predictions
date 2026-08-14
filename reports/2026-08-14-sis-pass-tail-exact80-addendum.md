# SIS pass-tail five-seed exact-80 implementation addendum

Frozen 2026-08-14 before Phase S is harvested and before any pass-tail
candidate, simulated lineup score or realized lineup score exists. This makes
the conditional exact-80 license in
`2026-08-13-sis-pass-tail-marginal-protocol.md` executable without a post-hoc
choice.

## Conditional terminal context

Run only if the pass-tail cache validation and final-served reports retain
their registered passing dispositions and Phase S passes its complete
mechanical audit. Both pass-tail arms inherit the Phase S-selected allocation
branch:

- Phase S control: finite Dirichlet K without SIS ASOE;
- Phase S treatment: the same finite K plus the frozen SIS ASOE law and beta.

The Phase R-selected K is `28.154043586960896`. The Phase S branch is common
to both pass-tail arms and may not interact with arm identity.

## Registered panels and schedules

For each `R0` through `R4`, use panels
`20260814-sis-pass-tail-control-r{seed}-v1` and
`20260814-sis-pass-tail-treatment-r{seed}-v1`. Evaluation seasons are
2023--2025, all 54 main slates, 10,000 worlds and exactly 80 selected lineups
per slate. Seed pairs, role-draw law, generator budgets, possession simulator,
market blend, candidate-world artifact law and selector are identical to
Phase S.

Generation is frozen to replay-capable commit `f92ce05` and immutable image
`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:018f0def471ba3f0a304cafb77e301c35e43d51658798f64a9ec85c95751d358`.
The later audit image may differ only to carry the already-frozen analyzer;
the analyzer records both identities and requires every candidate row to name
the frozen generation commit.

The only control/treatment differences are cache and the independently fitted
score-free schedule caused by that cache:

| arm | season | schedule |
|---|---:|---|
| control | 2023 | `QB:0.76,RB:0.83,TE:0.99,WR:1.05` |
| control | 2024 | `QB:0.81,RB:0.88,TE:0.97,WR:1.07` |
| control | 2025 | `QB:0.85,RB:0.895,TE:0.96,WR:1.04` |
| treatment | 2023 | `QB:0.975,RB:0.99,TE:0.975,WR:1.04` |
| treatment | 2024 | `QB:0.92,RB:0.97,TE:0.95,WR:1.055` |
| treatment | 2025 | `QB:0.92,RB:0.965,TE:0.945,WR:1.04` |

Control uses `tabpfn_sis_pass_tail_control_v1`; treatment uses
`tabpfn_sis_pass_tail_treatment_v1`. No schedule refit, subset, interaction,
threshold or seed change is permitted.

## Mechanical gate

Require exact panel/slate/seed/code identities, exact-80 ranks, complete
labels, 10,000-world checksummed artifacts, the common Phase S allocation
branch, and exhaustive player-snapshot equality after excluding exactly the
ten registered distribution-derived prediction fields. Shared roster actuals
must agree. Cache/schedule changes must reach player distributions and
candidate scoring. Any mismatch invalidates the experiment before scoring.

Cloud release is capped at ten nonterminal cells. Infrastructure retries are
allowed only byte-identically after proving zero candidate rows, feature rows
and artifacts.

## Frozen decision

For each arm and seed, take the maximum realized score among that slate's 80
selected lineups. Sum threshold counts over all five seed books (270
seed-slate maxima) in order `240,230,220,210,200,194,187`. The first nonzero
treatment-minus-control difference decides. If all counts tie, compare the
mean of all 270 maxima; an exact tie retains control.

Report every seed book, aggregate and per-season tails, mean/median, paired
better/worse/tied weeks, selected overlap, all absolute weekly deltas at least
10 points, and a 2,000-resample slate-cluster bootstrap (seed `8,142,026`)
that averages seeds within each slate. These diagnostics do not override the
frozen decision. A treatment win selects this cache/schedule law as the
historical research baseline and licenses later live/UI integration; it does
not silently mutate production.
