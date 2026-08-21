# Corpus parametric batch evidence contract v1

Date: 2026-08-21
Status: outcome-blind preregistration implementation; no run, outcome, shadow,
production, or adoption authority

## Purpose and boundary

`src/nfl_dfs/research/corpus_batch_evidence_contract.py` binds one valid
seven-setting corpus batch manifest to a create-once endpoint, gate,
multiplicity, reporting, license-transition, and knowledge-graph topology
contract. It reads no outcome, starts no solver, touches no cloud service, and
cannot mutate the graph or deploy anything.

The contract always records `decision_authority=false`. An outcome-blind batch
completion also has no decision authority. Only a separately governed realized
completion may decide whether zero or one of the six frozen challengers is
eligible to become a fresh default-off 2026 prospective shadow. Historical
evidence never authorizes production, adoption, default-on behavior, money
entries, historical retuning, or a second historical read.

## Frozen comparisons and endpoints

The incumbent is the common control. The six comparisons, in fixed order,
are the five single-rule removals followed by
`remove-all-five-shared-constraints`. Every report must retain all seven rows,
including losers, ties, invalid/ineligible arms, and the incumbent. Favorable
sorting, winner-only output, partial-body inspection, or dropping a failed
comparison invalidates the completion.

The registry contains 20 score-free endpoints and four realized endpoints.
It includes exact visit-optimum receipts, candidate counts, independently
audited DK invalidity, generated and selected violation counts for all five
rules, simulated C/S diagnostics, selected exact-80 cardinality, and exact
generated-unique score-matrix coverage. For every task and arm, the latter
requires one float64 row per frozen generated-unique roster, exactly 50,000
ordered source-world values per row, exact roster-row set equality, and exact
R0..R4-by-0..9999 column identity/order.

Historical score coverage is itself a frozen endpoint and gate. The one-read
source contract must reconstruct one exact micro-DK score for every canonical
lineup identity in every arm's complete generated-unique population. Player,
DST, and roster identities are always keyed by the exact
`(task_index, season, week, slate_id)`; equal-looking IDs on different slates
cannot alias. A lineup shared by visits or arms on the same exact slate may be
queried and reconstructed once, but its score must map back to every population
membership. Missing, extra, partial, winner-only, or exact80-only coverage
invalidates the entire completion.

The historical co-primaries are:

- `endpoint:corpus:realized-candidate-ceiling-c`: for slate `t` and arm `a`,
  `C[t,a]` is the maximum exact actual-score micro-DK value over the complete
  first-occurrence generated-unique population; and
- `endpoint:corpus:realized-exact80-maximum-s`: `S[t,a]` is the maximum exact
  actual-score micro-DK value over the frozen selected exact-80 population.

`C-S` is a mandatory conversion diagnostic but cannot rescue a co-primary
miss. Scores must be finite non-Boolean JSON numbers representable to cents;
Python nearest-even `round(score*100)` produces cents and cents are converted
to integer micro-DK. All maxima, signs, ties, thresholds, and winner/loser
counts use those integers. Both C and S report the complete
187/194/200/210/220/230/240 grid.

## Exact pairing, inference, and multiplicity

Every challenger is paired to the incumbent on the exact manifest task order.
For C and S separately, the retained exact micro-DK vectors feed the registered
paired mean and Wilcoxon signed-rank sign-flip law: zero deltas are ties;
absolute-rank ties receive stable average ranks; up to 20 nonzero pairs use
complete enumeration; larger samples use exactly 200,000 fixed-seed draws from
NumPy in 65,536-row chunks with the add-one correction. For every distinct
`(challenger, endpoint)` report, initialize a fresh
`rng = np.random.default_rng(20260818)` and call exactly
`rng.choice((-1.0, 1.0), size=(take, n_nonzero))` per chunk. The same sign
matrix supplies both the paired-mean and signed-rank hit counts. No shared RNG
stream, alternate sign generator, or challenger/endpoint call order may change
the retained p-values.
The implementation must be generation-pinned and an independently implemented
verifier must recompute the vectors and tests.

For challenger `a`:

```text
p_joint[a] = max(
  p_C_mean_two_sided,
  p_C_signed_rank_two_sided,
  p_S_mean_two_sided,
  p_S_signed_rank_two_sided
)
```

Holm step-down adjustment covers exactly the six frozen challengers. Sort
`(p_joint, fixed_challenger_ordinal)`; at zero-based position `j`, compute
`min(1, (6-j)*p_joint)`, take the capped running maximum, and map back to the
fixed arm order. Missing comparisons invalidate the whole family. Full,
unrounded values decide.

An arm is historically passing only if every pre-outcome gate passes, C and S
mean deltas are strictly positive, C and S signed-rank directions are
positive, its Holm-adjusted joint p-value is at most 0.05, and selected-S
194/200 count deltas are each at least -1 slate.

If multiple arms pass, nominate exactly one using:

1. smallest Holm-adjusted joint p-value;
2. largest mean S delta;
3. largest mean C delta;
4. largest selected-S 200-count delta; and
5. smallest fixed parameter-set ordinal.

No pass means no nominee.

## Score-free gates

The outcome firewall requires all registered gates, including:

- exact batch, source, world-schedule, common-law, and inventory identities;
- regenerated inventory-v2 rows, classified-input projection, and ambient
  absence proof for every arm;
- one terminal proven-optimal, zero-retry solve per task/arm/visit;
- exact paired relaxation monotonicity: on every matched visit, each relaxed
  arm's integer primary optimum is at least the incumbent optimum;
- outside-incumbent-law nonvacuity: the incumbent produces none, each
  single-rule arm produces at least one unique roster violating its removed
  rule while satisfying the other four, and the all-five arm produces at
  least one roster violating at least one of the five;
- direct DK legality and exact-80 membership/cardinality replay;
- complete score-free cross-score coverage: every generated-unique roster has
  exactly one float64 row over all 50,000 ordered source worlds, with exact
  roster-row and world-column identity equality and no selected-only subset;
- complete task-by-seven policy/result bodies, including losing arms; and
- an independent reload from raw authorities that reproduces schedule,
  policy, attempts, first occurrence, matrices, selector, and endpoints.

Only after all score-free gates and every historical authority pass can one
complete seven-arm historical read be licensed. It is consumed on launch and
cannot be retried under this identity.

## Fail-closed missing authorities

The current score-free batch foundation does not make a historical run ready.
Before any outcome lease, an outer immutable freeze must add direct,
generation-pinned identities for:

1. the paired C/S statistics implementation;
2. an independent exact-vector paired-statistics verifier;
3. the one-read actual-score source/query/order/precision contract;
4. the canonical realized seven-row completion schema; and
5. the separately frozen unseen-2026 shadow gate and default-off firewall.

Their absence is a named gate failure, not permission to improvise a test,
threshold, query, verifier, or prospective gate after results exist.

## License transitions

All licenses begin false. A complete pre-outcome gate receipt may enable
exactly one full historical read. Launch consumes it and historical retry
remains false. A separately verified realized completion with no passing arm
grants nothing. A completion with one deterministic nominee may license
creating, freezing, and deploying that exact parameter set as one default-off
2026 shadow.

Such a deployed shadow remains `prospective_shadow_passed=false`. Only its own
separately frozen unseen-2026 grading gate can change that prospective claim.
This historical contract contains no transition to production, adoption,
default-on behavior, or money entry.

## Knowledge-graph extension

The graph plan is an append-only child of the immutable v1 materialization.
It is a dedicated research evidence plane and must not share the application's
operational datastore or logical database. Canonical create-once JSON/GCS
objects remain authoritative. A dedicated Neo4j database or equivalent may
serve as the query projection, but it must be fully rebuildable, append-only,
and incapable of authorizing executions or policy changes. Store identities,
relations, rule states, measurements, and generation-pinned object pointers in
the graph; never store the 50,000-world matrices or raw outcome bodies there.

It freezes node and edge families for the batch, five parameters, seven
parameter sets, task executions, one independent finisher, and three truthful
populations per exact task and arm: visit outputs, the first-occurrence
generated-unique union, and selected exact-80. Every task-grain population,
measurement, execution, and edge identity includes `task_index`; no two slates
can collapse into one graph node. Measurement cardinalities follow their
literal endpoint grains: task-by-arm, task-by-arm-by-visit, or
task-by-challenger-by-visit. The graph does not mislabel the dedicated union as
CBWU admission.

Score-free measurements may materialize only after score-free completion and
remain `decision_authority=false`. Realized measurement nodes do not exist
until the separately governed realized completion. Workers never write the
graph; an independent adapter must validate every raw authority and append a
new version.

No build, cloud call, outcome read, lease, deployment, graph append, or
production mutation is authorized by this document or module.
