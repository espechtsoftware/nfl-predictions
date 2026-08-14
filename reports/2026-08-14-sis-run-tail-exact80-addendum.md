# SIS RB run-tail five-seed exact-80 addendum

Frozen 2026-08-14 CDT while both exact-commit cache/audit images were still
building, before either new cache existed and before any final-served or lineup
result was available. This makes the conditional license in
`2026-08-14-sis-run-tail-marginal-protocol.md` executable without a post-result
choice.

## Conditional license

Run this comparison only if:

1. cache validation disposition is
   `tabpfn-sis-rb-runtail-caches-valid`, including exact control reproduction;
2. final-served disposition is
   `tabpfn-sis-rb-runtail-final-served-passes`; and
3. all mechanical, PIT, mean-preservation and primary q95/q99 gates pass.

Otherwise this addendum expires without reading a new lineup score.

## One experiment across fixed seed books

This is one paired exact-80 experiment evaluated over the five seed books
already frozen for the incumbent seed-variance audit:

| book | baseline/simulator seed | role-belief seed |
|---|---:|---:|
| R0 | 0 | 7,331 |
| R1 | 1,137,260,708 | 2,690,847,602 |
| R2 | 2,875,959,182 | 1,630,284,992 |
| R3 | 253,722,715 | 3,374,646,876 |
| R4 | 1,643,280,042 | 3,977,633,467 |

Five paired books are required because the accepted simulator/selector was
found materially seed-sensitive. They are repeated algorithmic searches on
the same 54 slates, not 270 independent NFL outcomes. No seed may be replaced,
added, dropped or selected based on its result.

Panel IDs are `20260814-sis-runtail-control-r{0..4}-v1` and
`20260814-sis-runtail-treatment-r{0..4}-v1`.

## Frozen common stack and sole arm difference

Both arms use seasons 2023--2025, all 54 main slates, 10,000 worlds, finite
Dirichlet `K=28.154043586960896`, the possession simulator, 45/55 model/market
blend, active-only labels, one ensemble member, 12 direct role-belief
candidates, 40 boom candidates, no CE/Gumbel candidates, 194-world coverage,
a $49,000 salary floor and exactly 80 selected lineups per slate.

Both arms use the same seed pair, point-in-time inputs, solver, generation
budgets, role features, selector and labels. Do not enable SIS ASOE, SIS
pass-tail, Points Saved, Route, PFR-secondary, TD-ledger/rank coupling, G2/G3,
K=1 or another new feature/dependence mechanism.

Control uses cache `tabpfn_sis_rb_runtail_control_v1`; treatment uses
`tabpfn_sis_rb_runtail_treatment_v1`. Each arm uses exactly its own
strict-prior served-position schedule serialized in the passing final-served
report. Those schedules are a preregistered deterministic consequence of the
cache arm, may differ between arms, and may not be refit, rounded, pooled or
changed after that score-free report. The launch manifest pins the cache
validation and final-served report hashes plus the exact serialized schedules.

## Mechanical gate before scoring

Require exact image/code/panel/slate/seed identities, 18 slates per season,
80 distinct selected rosters per slate, complete labels and checksummed
10,000-world artifacts. Exhaustively compare player snapshots after excluding
only the registered distribution-derived prediction fields. Shared rosters
must have identical actual scores. Cache/schedule changes must reach player
distributions and candidate generation/scoring; otherwise the experiment is
vacuous and invalid.

The generation image must be a full-test immutable digest from the committed
replay-capable implementation. Cloud release is capped at ten nonterminal
cells. An infrastructure retry is allowed only byte-identically after proving
zero destination candidate, feature and artifact rows.

## Frozen tail-first decision

For each arm and seed book, take the maximum realized score among that slate's
80 selected lineups. Sum threshold counts over all five books in order
`240,230,220,210,200,194,187`. The first nonzero treatment-minus-control
difference decides. A positive difference selects treatment; a negative
difference retains control. If every threshold count ties, compare the mean of
all 270 seed-slate maxima; an exact tie retains control.

Report every seed book, aggregate and per-season tail grids, mean/median,
paired better/worse/tied slates, selected and candidate overlap, every absolute
weekly delta of at least 10 points, and a 2,000-resample whole-slate clustered
bootstrap with seed `8,142,028` that averages the five seed books within each
slate. These diagnostics do not override the registered decision.

A treatment win selects this adaptive historical law for the research
baseline and licenses a labeled 2026 prospective shadow. It does not silently
change production, K=1 or the UI.
