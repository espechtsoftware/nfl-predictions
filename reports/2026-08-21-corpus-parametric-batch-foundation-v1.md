# Corpus parametric batch foundation v1

Date: 2026-08-21
Status: source-green foundation; no build, launch, outcome read, or deployment authority

## Purpose

The corpus experiment may reuse one immutable image for a bounded series of
parameter settings. It must not expose arbitrary process environment state.
Every task consumes one generation-pinned, create-once batch manifest and a
task index. Every permitted parameter value, source identity, world schedule,
solver law, output namespace, and result binding is fixed before execution.

This foundation does not implement or authorize the science runner. The
authoritative runner and independent finisher must still rebuild each slate
from the exact source-freeze and R0--R4 artifact bytes, emit replayable solver
proofs and canonical policy/result bodies, and pass an adversarial review.

## Frozen scientific surface

The parameter schema SHA-256 is
`d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff`.
Every assignment contains exactly these five typed fields:

- `min_lineup_salary`: integer in `{0, 49000}`;
- `qb_stack_min`: integer in `{0, 2}`;
- `bring_back_min`: integer in `{0, 1}`;
- `forbid_rb_vs_dst`: Boolean;
- `forbid_two_rb_same_team`: Boolean.

The complete batch is exactly:

1. `incumbent`;
2. `remove-salary-floor`;
3. `remove-qb-stack`;
4. `remove-bring-back`;
5. `allow-rb-vs-dst`;
6. `allow-two-rb`;
7. `remove-all-five-shared-constraints`.

The seventh identifier is intentionally neutral. It may be described as
DK-classic-feasibility-only only after a runtime receipt proves every other
house feasibility mechanism nonoperative. It is never whole-system
"rule-free" because the common world allocation, deduplication, and exact-80
selector remain explicit rules.

The registered score-free compute law is 200 visits in each retained
R0--R4 block, 10,000 source worlds per block, at most 1,000 visit outputs per
setting before first-occurrence deduplication, and exactly 80 selected entries.
Each visit has one monotonic 120-second total solver deadline across all solver
stages. The separately retained world-schedule body must contain the exact
outcome-blind top-200 total-slate-ranked world IDs in each block, with stable
world-index ties. Raw indices `0..199` are not the registered schedule.

## Independent rule and input inventory

`effective_policy_rule_inventory.py` regenerates a closed source contract from
11 hash-pinned production/enforcement and independent-validation files. V2
contains 64 distinct DK-hard, house-soft, generation, admission, simulation,
and selector rows.

- inventory SHA-256:
  `7853a701963dd6f734caf13812d44cf7392ffeec82facc46f0ff15d5de047790`;
- rule-universe SHA-256:
  `b9a33d093d258aa844cfef9b1e354175bed56a5d849cbef9682755aadf2f6533`;
- source-set SHA-256:
  `3cbe45d4e0106c867ff4ba9a9443c4fad9a7ffaac7d0492ae488d72c0ae40d4f`;
- classified-input projection SHA-256:
  `f48b2ed9aaac9c3f279134cff09df2ab88a54009c07e8c60c55834817841d30d`.

The AST projection finds 119 input keys at 230 read sites: four typed
parametric environment inputs, 86 frozen mechanism inputs, 11 infrastructure
inputs, and 18 forbidden ambient inputs. The same-team-RB setting is an
explicit request-local `StackRules` field rather than an environment input.
The future runtime must prove all score-relevant ambient seams absent and
must bind this complete projection; an inventory hash alone is insufficient.

## Manifest and result boundary

`corpus_parametric_batch.py` enforces:

- exact types, no Boolean/integer aliases, sparse values, defaults, coercion,
  unknown keys, duplicate JSON keys, or nonfinite JSON;
- one role-keyed common later-source-freeze identity and exactly five
  generation-pinned world-artifact identities per task;
- distinct object SHA/bytes and internal source-freeze manifest SHA;
- exact inventory, rule-universe, inventory-source-set, and classified-input
  projection hashes;
- one immutable image/code/common mechanism law;
- exactly one attempt and zero retries in v1;
- output prefixes ending in the batch ID, deterministic create-once claim and
  manifest paths, and disjoint governance/task/input namespaces;
- exact per-setting effective-policy and result object paths; and
- complete ordered task-by-seven terminal coverage.

The effective-policy and science result identities are intentionally opaque at
this layer. The authoritative runner/finisher must validate their canonical
bodies and transitive evidence before a completion or graph extension can be
decision-bearing.

## Validation and authority

- `tests/test_corpus_parametric_batch.py`: 67 passed;
- `tests/test_effective_policy_rule_inventory.py`: 15 passed;
- contract module SHA-256:
  `55efe37d1a51da3aac8bb98edcf7b85b1fceadab121c45932847654f88bdc753`;
- inventory module SHA-256:
  `086454879e7020590fb1627eb413c4552b1bde9e6f2a45f2161b50e627ca5b62`;
- contract-test SHA-256:
  `27831d30506a5c6bd3288681b1a0fa0258bb782803f4094977e45443bb9f6dc8`;
- inventory-test SHA-256:
  `6ff6265eee59e2af5cd7321972d1b9fdbf47a6a03c41698905a3a9501e34f947`;
- Python compile and `git diff --check`: green.

No CBC solve, simulation, BigQuery, GCS, Cloud Run, historical-outcome lease,
image build, or deployment occurred. No historical or prospective license is
granted. The knowledge graph remains an append-only evidence index, not a
mutable run controller. A future graph v2 must validate all raw policy/result
bodies, the completion matrix, a pre-run endpoint/gate/license contract, and
the independent inventory before materialization.
