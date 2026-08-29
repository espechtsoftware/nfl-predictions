# R6 F7/F8/F9 full-54 task-0 composite-collection recovery amendment

Status: **pre-result amendment; outcome-blind; no replacement execution**
Frozen at: **2026-08-29T05:34:57Z**, before any recovery open of the 53
full-panel task-result bodies
Scientific worker/image/input: **unchanged**

## 1. Purpose

The F7/F8/F9 population execution
`atlas-minimal-c-s2023-w1-v1-fxhl8` (execution UID
`9c941a48-7817-4748-8696-2bdcb0580eb7`) is terminal with 53 successful tasks,
one failed task and zero cancellations. Administrative Cloud Run task
metadata identifies the only failure as task index 0. A preceding task-0
reality smoke completed successfully under the exact same scientific
request, code, image, job and output topology.

This amendment permits one narrow composition:

- ordinal 0 comes from the already-successful task-0 smoke;
- ordinals 1 through 53 come from the successful complement of the full-54
  execution;
- no task is recomputed and no Cloud Run execution is launched;
- every deterministic result is generation-exact opened and replayed through
  the existing result/schema/request validators;
- a create-once recovery intent must exist before any recovery open of
  ordinals 1 through 53.

The amendment changes transport provenance only. It does not alter a lineup,
profile, constraint, world, objective, solver call, selection law or outcome
rule.

## 2. Frozen administrative evidence

Canonical full-54 status:

- local receipt:
  `/tmp/r6-score-sprint-c9f12ed7-v1/population/full54-status-terminal-audit-001.json`;
- status self-SHA-256:
  `d16b53de642268f08bc7e9d5f72e622d1d473a7bf015799133c87de70a86e105`;
- expected/succeeded/failed/cancelled: `54 / 53 / 1 / 0`;
- terminal state: `FAILED`;
- logs, scientific outputs and outcomes read by the status operation: false.

Failed task administrative description:

- task: `atlas-minimal-c-s2023-w1-v1-fxhl8-task0`;
- task index/source ordinal: `0` / `0` (`slates/00`);
- start: `2026-08-29T03:18:52.854487Z`;
- completion: `2026-08-29T05:18:34.184120Z`;
- elapsed: approximately 7,181.33 seconds;
- provider reason: `NonZeroExitCode`;
- exit code/provider status code: `1 / 10`;
- the task started its container; this was not a pre-start failure;
- Cloud Run task timeout: 21,600 seconds; this was not the provider task
  timeout.

Successful smoke:

- execution: `atlas-minimal-c-s2023-w1-v1-45lcm`;
- execution UID: `da5adb5c-84da-4892-98fe-7a9b207c4814`;
- status self-SHA-256:
  `ada6fa1f68c0fa43bcf8a4256211de5e0403a9876d94d520071d17694b9ae1d7`;
- expected/succeeded/failed/cancelled: `1 / 1 / 0 / 0`;
- start: `2026-08-29T01:04:59.106235Z`;
- completion: `2026-08-29T03:06:04.223542Z`;
- elapsed: approximately 7,265.12 seconds.

The smoke and failed full-panel task descriptions bind the same:

- command:
  `/usr/local/bin/python3.11 -I /app/scripts/run_corpus_r6_population_challenger_v1.py task`;
- original science commit:
  `c9f12ed7028f8d8ef76950a12bc9208f67a4023d`;
- immutable image digest:
  `sha256:a34b4c2e8bf156452d8461e7d3ee6d42adc428d514f79c924ac74dfa3c58a4c3`;
- fixed job UID:
  `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2`;
- manifest generation/content identity:
  generation `1787965215675864`, SHA-256
  `2456bcfe069318cb8ad06396fe662dd5540f36b76a483a9b48dfe8f1c00ee714`,
  275,290 bytes;
- 8 CPU, 32 GiB, zero retries and a 21,600-second task timeout.

The only execution-context difference is Cloud Run task count: one for the
smoke and 54 for the panel. The frozen dispatcher admits only counts 1 or 54,
then selects scientific work solely by task index. In either context task
index 0 selects the identical manifest request:

- request SHA-256:
  `20cfe04355928430dbc46c046b976268841faaa103ab33f4f1da8a18645d67c5`;
- projection identity: generation `1787947997627724`, SHA-256
  `01a74384b7b8255d42e059f110a8b64adc0a1efcb4a7a3908d003b280abfbcc3`,
  7,929,526 bytes;
- 1,000 solves per profile and 3,000 solves total;
- the same three deterministic profile-output URIs and task-result URI under
  `slates/00/`.

## 3. Existing task-0 result authority

The frozen task-0 collection has collection self-SHA-256
`590d78ddbc23e6e01a0958ec4b6583f3e4b022d5b6943b21fa19062be12c9af1`.
It binds:

- result URI ending `slates/00/task-result.json`;
- generation `1787972761075354`;
- content SHA-256
  `345f306c875c2a752ce01a74c8d3d6a9750df80b9a266feec68c9d4891639b08`;
- 6,172 bytes;
- result self-SHA-256
  `01ea7cf40737ccf2d3173497982b4037c5a49787c57a40345b5c65a1c8455d00`.

That collection could exist only after the frozen collector generation-exact
opened the task result and validated its schema/self-hash, task/source
ordinal, request SHA, projection identity, profile order and expected profile
URIs. The recovery must require this exact generation/content identity for
ordinal 0; resolving a newer task-0 generation is forbidden.

## 4. Why the ordinary collector cannot finish

`collect_task_results_v1` requires one full-54 launch/status with terminal
`SUCCEEDED`, succeeded count 54, failure count zero and cancellation count
zero before opening any task result. It correctly rejects the observed
53/1/0 execution. Forging a 54/54 status or relabeling the failed execution is
forbidden.

A fresh task-0 execution is unnecessary and would add time without adding a
new scientific request. The already-successful task-0 smoke is the exact
one-cell, same-image, same-input, create-once authority needed to complete the
logical panel.

## 5. Fixed recovery protocol

The recovery has two commands and fixed publication order.

### Phase A: `prepare`

Before opening any new population result body, the operator must:

1. validate the frozen preparation and exact manifest authority;
2. validate the smoke launch/status/collection;
3. validate the full-54 launch/status at exactly 53/1/0;
4. project the two Cloud Run task descriptions into log-free administrative
   envelopes;
5. prove task index 0, exact job/execution UIDs, identical task specs and the
   fixed `NonZeroExitCode` failure;
6. bind the amendment, recovery source hashes and recovery commit;
7. publish the recovery intent create-once and exact reopen it.

No result URI may be opened in Phase A.

### Phase B: `collect`

The operator must first generation-exact reopen the published intent. It then:

1. exact reopens and validates the population manifest;
2. exact opens ordinal 0 only by the smoke result's pinned generation;
3. opens ordinals 1 through 53 only by their deterministic manifest names,
   never by listing;
4. validates every result with the existing task-result schema, self-hash,
   body/content identity and manifest-request checks;
5. requires ordinal 0 to equal the smoke collection identity and self-hash;
6. emits ordered per-task provenance, with ordinal 0 assigned to the smoke
   and ordinals 1--53 assigned to the full execution;
7. publishes create-once the composite collection and ordinary six-field
   population-crossed prepare request;
8. publishes create-once a terminal recovery receipt binding the intent,
   collection and crossed request.

The fixed output topology is:

```text
<population-prefix>/authorities/full54-task0-composite-recovery-v1/
  intent.json
  collection.json
  crossed-prepare-request.json
  recovery-receipt.json
```

The ordinary crossed request stays byte-compatible with the existing crossed
operator. Its immutable identity and canonical SHA are bound by the recovery
receipt, which carries the explicit composite provenance.

## 6. Fail-closed conditions

The recovery must reject:

- any failed task other than index 0;
- anything other than smoke 1/0/0 and full panel 53/1/0;
- pre-start, timeout, cancellation, retry or non-`NonZeroExitCode` evidence;
- any command, environment, image, resource, service-account, retry or task-
  timeout drift between the two task descriptions;
- any manifest, source binding, request, projection or output-URI drift;
- any task-0 identity/self-hash other than the accepted smoke result;
- any missing, duplicated, out-of-order or request-mismatched result;
- any create-once collision with differing bytes;
- any result read before the exact intent exists;
- any bucket listing, Cloud Logging access or outcome access;
- any attempt to launch or recompute a task.

## 7. Decision and downstream status

This amendment is transport-only and outcome-blind. A successful composite
receipt authorizes the existing population-crossed selection/evaluation chain
to consume the ordinary prepare request. It does not itself authorize
historical outcome access, scoring, promotion or a production change.
