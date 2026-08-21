# Research evidence knowledge graph v1

**Date:** 2026-08-21
**Status:** read-only historical-index implementation and parametric design;
no parametric runner or deployment authority
**Scope:** generated-corpus tail decisions, Millionaire-winner characteristics,
construction rules, selectors, arms, endpoints, gates, and licenses

## Purpose

The project needs a durable answer to questions such as:

- What population and baseline did an arm actually use?
- Which rule did it retain, remove, relax, add, or leave nonoperative?
- At which pipeline stage and on what fraction of candidate paths did that
  change apply?
- Did the intervention move candidate ceiling `C`, selected exact-80 maximum
  `S`, calibration, winner overlap, or only an intermediate mechanism?
- Which conclusions are outcome-blind, outcome-viewed, or prospective?
- Which downstream actions are explicitly licensed or forbidden?

This graph is an evidence index, not a replacement source of truth. Frozen
protocols, canonical result bodies, finish ledgers, and immutable object
receipts remain authoritative. The graph points to and validates those bytes.

## Storage and identity

The v1 graph is a small, repository-native property graph. Its curated input
and materialized artifacts live under:

```text
reports/evidence-graph/20260821-v1/
```

The input is manually curated from canonical tracked sources. It is never
inferred by parsing `HANDOFF.md` or by an unconstrained language model. A
deterministic builder emits canonical JSON Lines for artifacts, nodes, and
edges plus a manifest binding their hashes, the exact curated-registry SHA,
and the builder SHA. Validation rebuilds from the pinned registry and retained
source bytes and requires exact graph equality; a self-receipted materialized
directory is insufficient. Equality is canonical-byte equality, so JSON
Boolean, integer, and floating-point values cannot alias. Stable semantic IDs
are used instead of array positions.

V1 mechanically derives every measurement property and both the control and
treatment side of every `SETS_PARAMETER` edge from pinned source bytes. Text
parameters use unique typed capture expressions; zero or multiple matches are
fatal. Other node properties are curated descriptive metadata, so the
materialized manifest states
`property_binding_scope=measurement_properties_and_parameter_assignments` and
`decision_authority=false`. They may organize evidence, but cannot themselves
authorize a scientific or operational decision.

Corrections append a new graph version and explicit `SUPERSEDES` or
`INVALIDATES` relationships. A historical assertion is never silently edited
in place after its decision use.

## Node model

The bootstrap uses these node kinds:

- `corpus`: exact slate/population context and outcome-visibility boundary;
- `population`: winner cohort, candidate pool, or selected-book cohort;
- `policy`: exact policy/control context;
- `rule`: DK hard legality, house-soft feasibility, generation/admission, or
  selector law;
- `parameter`: a named controllable setting and its unit/domain;
- `parameter_set`: one canonical, self-hashed assignment of allowed scientific
  parameters;
- `batch`: a frozen matrix of parameter sets, common sources, worlds, and
  decision law;
- `arm`: one protocol arm or fixed-pool selection treatment;
- `endpoint`: normalized measurement definition;
- `measurement`: observed value(s), comparator, inference, and interpretation;
- `gate`: registered decision condition and result;
- `license`: explicit downstream capability and Boolean disposition;
- `execution`: immutable image/code/job identity and one terminal run receipt;
- `claim`: a bounded human-readable interpretation with epistemic class.

Every outcome-bearing node declares one of `outcome_blind`, `outcome_viewed`,
or `prospective`. Descriptive winner facts and retrospective arm results cannot
silently acquire adoption authority.

## Edge model

Core relationships are:

- `USES_CORPUS`, `USES_POPULATION`, `COMPARES_WITH`;
- `INHERITS_POLICY`, `USES_SELECTOR`, `SHARES_POOL_WITH`;
- `RULE_APPLICATION`, `SETS_PARAMETER`;
- `USES_PARAMETER_SET`, `PART_OF_BATCH`, `BOUND_TO_EXECUTION`, `PRODUCES`;
- `MEASURES`, `OBSERVED_ON`, `EVALUATES_GATE`;
- `DECIDES_LICENSE`, `SUPPORTED_BY`, `MOTIVATED_BY`;
- `SUPERSEDES`, `INVALIDATES`, and `DEPLOYED_AS`.

Every assertion carries source evidence. JSON evidence uses an exact JSON
pointer and expected value. Text/code evidence uses an exact retained excerpt.
Every source is bound by its full SHA-256.

## Complete rule-dose law

`RULE_APPLICATION` is never a Boolean. Each edge records:

```json
{
  "effect": "retained|removed|relaxed|replaced|tightened|added|nonoperative",
  "stage": "simulation|generation|admission|selection",
  "application": "direct|upstream_inherited|not_applicable",
  "scope": {
    "candidate_path": "boom|all|fixed_pool|...",
    "numerator": 8,
    "denominator": 40,
    "unit": "solve_attempts_per_seed",
    "fraction": 0.2
  }
}
```

Every tracked arm must materialize exactly one canonical edge for every rule in
the v1 curated universe and bind the universe hash. Missing or duplicate
coverage is fatal and means unknown, never removed. Inheritance is allowed in
the curated input, but the materialized graph expands it to one explicit edge
per rule.

The curated universe is not an independent effective-policy inventory. It is
useful for negative findings, but it cannot prove that no rule was omitted.
Therefore v1's `full_soft_removal` predicate is hard-false. A future positive
requires a separately generated and frozen inventory containing every rule's
ID, class, stage, baseline state, default dose, normalized path set, and source
locator. The runtime effective-policy receipt must equal that inventory
row-for-row.

Once that independent inventory exists, `full_soft_removal` may become a
closed-world derived predicate. It can be true only when:

1. every baseline-active house-soft generation/admission rule is removed at
   100% scope;
2. every candidate path uses the treatment rule set;
3. no incumbent-law candidate family or injected sleeve remains;
4. no structural post-generation admission quota remains; and
5. the rule matrix is complete and source-bound.

The predicate applies to candidate generation only. Selecting 80 entries is
itself a separate rule, so any downstream book must be labelled, for example,
"legal-only generation under shared incumbent selection," never "rule-free."

## Bootstrap scope

The first graph binds:

- the valid 54-slate 2023--2025 Sunday-main corpus;
- the 51-winner structure, anatomy, simulated-percentile, and legal-optimum
  reports;
- the incumbent candidate and selected-book structure populations;
- all-boom candidate-ceiling and exact-80 follow-up;
- the A3 partial stack/bring-back carve;
- A7 fixed-pool selector ladder;
- B1 fixed-pool tail model;
- A2a dependence-law remeasurement as a simulation-only diagnostic, with
  lineup construction and selection marked not applicable; and
- the current production and arm-comparator baseline contexts.

The bootstrap is deliberately bounded. It records the highest-decision-value
tail program first, then future protocols add compact graph sidecars before
execution. A graph version must report its coverage scope; absence from v1 is
not evidence that an older arm did not exist.

## Required decision queries

The CLI must answer, deterministically:

1. `arm-rules`: complete retained/removed/relaxed/added matrix and dose;
2. `full-soft-removal`: whether an arm truly removed every house rule and the
   exact blockers when false;
3. `winner-corpus-gap`: winner versus pool versus selected-book structure;
4. `arm-effects`: registered parameter changes, attribution scope, `C`/`S`
   effects, and any materialized gates/licenses (empty when none exist);
5. `baseline-compatibility`: whether two headline numbers share corpus,
   slate count, exact comparator, endpoint, entry count, policy, and selector
   law (treatment populations are reported separately); and
6. `decision-brief`: the current evidence path without converting descriptive
   evidence into causal or deployment claims.

The all-boom/A3 misconception is a required known-answer test:

- all-boom changed family allocation and volume but removed zero feasibility
  rules;
- A3 relaxed only QB-stack and bring-back, on 8 of 40 boom visits per seed;
- A7 and B1 changed selection on pools generated under inherited house rules;
- therefore no completed tracked arm satisfies `full_soft_removal`.

## Governance boundary

Building or querying this graph reads only already retained local evidence. It
does not query outcomes, BigQuery, GCS, or Cloud Run. Graph observations never
license a retry, retune, production change, or shadow unless the referenced
authoritative result independently grants that exact capability.

Before the next legal-only corpus comparison may score, its frozen protocol
must add a graph sidecar with the complete rule matrix, source/world schedule,
candidate paths, selector, endpoints, gates, and literal license matrix. The
graph validator must pass before any historical-outcome lease is acquired.

## Parametric execution law

One immutable experiment image may run many parameter sets without a rebuild,
provided the parameter surface is itself frozen and bounded. This section is a
design contract only: v1 contains no `parameter_set`, `batch`, `execution`,
`gate`, or `license` instances and does not authorize a run.

The first scientific surface is exactly five mandatory fields:

| Parameter | Frozen domain |
|---|---|
| `min_lineup_salary` | integer `{0, 49000}` |
| `qb_stack_min` | integer `{0, 2}` |
| `bring_back_min` | integer `{0, 1}` |
| `forbid_rb_vs_dst` | Boolean `{false, true}` |
| `forbid_two_rb_same_team` | Boolean `{false, true}` |

The first batch contains exactly seven complete assignments: incumbent, five
single-rule removals, and one all-five-removal/DK-classic-only assignment.
Sparse assignments, type coercion, unknown keys, arbitrary ranges, and an
"expose every environment variable" surface are forbidden. Exact-one stacking
is an added maximum constraint, not a removal, and is outside this batch.

| Set | Salary | QB stack | Bring-back | RB vs DST | Two same-team RBs |
|---|---:|---:|---:|---|---|
| incumbent | 49000 | 2 | 1 | forbidden | forbidden |
| remove-salary-floor | 0 | 2 | 1 | forbidden | forbidden |
| remove-qb-stack | 49000 | 0 | 1 | forbidden | forbidden |
| remove-bring-back | 49000 | 2 | 0 | forbidden | forbidden |
| allow-rb-vs-dst | 49000 | 2 | 1 | allowed | forbidden |
| allow-two-rb | 49000 | 2 | 1 | forbidden | allowed |
| dk-classic-only | 0 | 0 | 0 | allowed | allowed |

For that bounded surface:

1. Only scientific parameters in a versioned allowlist are configurable.
   Project, source, image, service account, lease, output prefix, retry policy,
   and evidence controls are not scientific parameters and cannot be supplied
   by a variant.
2. A create-once batch manifest binds the exact parameter-spec hash, every
   complete variant ID, typed value, allowed category, source receipt, world
   schedule, seed, solve budget, output URI, and parameter-schema hash before
   any task starts.
3. Workers receive only the generation-pinned manifest identity and their task
   index. Arbitrary environment inheritance is forbidden.
4. Every result binds its `parameter_set`, batch, code, immutable image, source,
   execution, task index, and create-once result receipt. A strict terminal
   finisher emits the graph sidecar; workers never mutate the graph directly.
5. Prefer one task per slate that evaluates all seven sets in fixed order from
   fresh model state while reusing only immutable loaded data. Worlds,
   objective, attempt budget, generator families, unique-fill, deduplication,
   admission, CBWU, selector, line 194, exact-80 budget, solver, source, and
   retry law remain common and frozen.
6. Many outcome-blind construction/mechanism variants may share the build. A
   sequence of score-inspect-adjust-score runs is forbidden. If historical
   outcomes are used, the complete variant batch is frozen first, evaluated in
   one jointly governed read, fully reported, and subject to its registered
   multiplicity and license law.
7. Prospective variants remain default-off shadows. Their parameters cannot be
   changed after the slate lock or in response to intermediate outcomes.

Thus an image rebuild is required only for implementation or parameter-schema
changes, not for a value change inside the frozen schema. The existing engine
does not yet satisfy this contract: some paths read process-global environment
state and `forbid_two_rb_same_team` has no environment seam. The runner must
construct typed request-local policy objects, reject unregistered active
levers, and emit terminal execution receipts before this architecture is safe.

The knowledge graph is the terminal index, not the mutable run controller.
Workers publish create-once result sidecars; an independent finisher validates
the complete task/parameter-set matrix and only then appends a new graph
version. No worker may rewrite an existing graph node or infer a missing
parameter from a default.

The registered estimand must be named "matched-world legal-feasibility
generation under frozen admission/selector." It is not proof that the whole
system is rule-free. Historical arms with bundled changes remain joint-bundle
effects; the graph must not attribute their outcomes to an individual
parameter unless the contrast isolated that parameter.
