# T230 ordinal-35 verifier bounded platform-replacement amendment

Date: 2026-08-26
Status: **superseded before launch; no execution authority was ever granted**

> The ordinal-6 replacement subsequently failed with a nonzero application
> exit and exhausted Lane A. This draft never passed independent review and
> never authorized or launched verifier attempt 1. Recovery of verifier 35
> can no longer make this T230 panel complete, so the smaller terminal-closure
> law in
> `2026-08-26-t230-current-run-terminal-panel-closure-amendment.md`
> supersedes every prospective execution, boundary, supplemental-acceptance,
> and joint-accepted-panel provision below. The frozen evidence inventory is
> retained as historical input to that outcome-blind closure.

## Purpose and boundary

This amendment addresses one exact Cloud Run platform failure in the
outcome-blind T230 production panel. It applies only to Lane B source ordinal
`35`, slate `2024-w18`, operation `verify-slate`, failed execution
`atlas-cbc-32g-full-2023-w8-v1-sqs7z`, and its already-consumed runtime attempt
`0` request. It does not widen or import-modify the independently reviewed
ordinal-6 replacement implementation.

The objective is one truthful verifier attempt `1`, followed by one explicit
ordinal-36 boundary transition that restores standard attempt-0 artifacts for
the remainder of Lane B. This amendment grants no retry, launch, acceptance,
lane, panel, scoring, corpus-fill, graph, promotion, decision, or production
authority by itself.

All evidence capture for this draft was exact-name and generation-pinned. No
bucket listing, latest alias, lineup-result body, realized outcome, score,
support-rank effect, or comparative result field was read. The existing
ordinal-35 science-result object was inspected by metadata identity only.

## Frozen run and immutable execution surface

- Project: `nfl-predictions-503414`
- Region: `us-central1`
- Run: `20260825-foundry-t230-production-v2`
- Output prefix:
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230/20260825-foundry-t230-production-v2/`
- Lane: `1` / `t230-b`
- Source ordinal: `35`
- Slate: `2024-w18`
- Operation: `verify-slate`
- Reused job: `atlas-cbc-32g-full-2023-w8-v1`
- Service account: `817589974517-compute@developer.gserviceaccount.com`
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ed7da003c80ad47118c3c9242ec2e9047a24f489134bfdc0f534a6769d622fee`
- Envelope: CPU `8`, memory `32Gi`, task count `1`, parallelism `1`,
  timeout `21,600` seconds, `maxRetries=0`, one in-memory `1Mi` evidence
  volume mounted at `/etc/nfl-dfs`.
- Frozen runtime payload: SHA-256
  `1c95fd4312db7baff61e0c25366cc07e515d74fef0741ebbd4f852ccf5c9cc19`,
  `7,688` bytes.

The transport contract identity is generation `1787692605903060`, object
SHA-256
`0ce6aa688ef9ca599f5fbafd8bd3e9d41a6557e1fe0c56c5caf15a2c80e64af9`,
`11,617` bytes, with contract self-hash
`27f46fec15ad474dfec8a02b6513dba337ff77fc1b409f9be7a851c772cbebaa`.

The execution authority identity is generation `1787693122369176`, object
SHA-256
`2bca3aa90c238ed56c9137b0d9bea78384cb7c45df070954557040be9e73d1d8`,
`5,824` bytes, with authority self-hash
`2095519d270cffed1ea4f2429dd9262836fa99f0c90d1ad79073e8530ec60e13`.
It binds the execution manifest at generation `1787693065874622`, object
SHA-256
`b43c105929b96d9b9cab75833edbfed8ee41fdfe14df5a3f6cf46f51077e2488`,
`82,022` bytes. That exact manifest binds ordinal 35 to `2024-w18` and ordinal
36 to `2025-w01`; ordinal 36's exact result URI is therefore not inferred from
a calendar sequence.

The compute-release identity is generation `1787695033977025`, object
SHA-256
`0e1deaf971c83acd0fbf261b25de21df06120ad45469a44ff789c0f9f7afcc0f`,
`3,670` bytes.

## Existing worker and result metadata lineage

Ordinal 35's worker already succeeded. These objects are immutable inputs to
the replacement verifier and may not be deleted, overwritten, republished, or
regenerated. The replacement verifier's independent in-memory science
recomputation against the exact pinned result remains mandatory; only
regenerating or republishing the existing worker/result artifacts is
forbidden:

| Object | Generation | Object SHA-256 | Bytes | Self-hash |
|---|---:|---|---:|---|
| `transport/stage-starts/run-slate/35/attempt-00.json` | `1787714234063439` | `8769408869bbdfe940033a7f27cf5fa42fc4fc92416ca61e30447438ed87f73b` | 3,600 | `b05bc5726cc3f081e44bcfda4860d8258f4b6084caf26531875d60f6f769d78a` |
| `slates/35/runtime/attempt-00/foundry-t230-worker-runtime-v1.json` | `1787714321300536` | `09dafa50c03f8e6cd60a1cacb9f5b4a889f443fa4c3da8065ce27486e93bab8a` | 13,520 | `388f08db0d0961543958165c9463e444fbacf1fcd287bd22f731aeea5ce757cd` |
| `slates/35-2024-w18/foundry-t230-slate-analysis-v1.json` | `1787715331922729` | `b9e8e344bb3e6043a84654e2a277a0137c406f6c67f76d5911293b3df1d517f6` | 15,352,504 | body deliberately unopened |
| `transport/stages/run-slate/35.json` | `1787715332909235` | `6065524e64d669864b9646e71347b54025a21a9318333095081f1ffcf516d387` | 2,054 | `f14d75ffe59d3f9230fef23179949816ea4c5757080e5751cfb181e7d32727f9` |

The worker execution was
`atlas-cbc-32g-full-2023-w8-v1-bg5kv`. Its start binds the exact ordinal-34
verifier stage as predecessor. Its launch request is generation
`1787714018598741`, SHA-256
`06fd638d09ca5ea1234400f00440c8927cb35ec9e5d9ea5fbba5a8cb0c125778`,
`2,530` bytes. Its publication-journal intent is generation
`1787714018277219`, SHA-256
`a92abf9f80c6b1988d73a5b90950d5232f8f5c81130dac95902bdca13404a66c`,
`704` bytes; its completion is generation `1787714018924440`, SHA-256
`f282b94e2c3cab6c694ee44796c63aa8cac739d1d01969c223b5178b251fb5db`,
`1,244` bytes.

Both worker receipts state `uses_realized_outcomes=false` and
`historical_scoring_licensed=false`. The result identity is known only because
the worker receipt and failed verifier environment bind it; this pre-launch
review did not inspect its content.

## Consumed verifier attempt-0 lineage

The original verifier request is permanently consumed and must never be
reused:

- request URI: `transport/launch-requests/verify-slate/35.json`
- generation: `1787715358516177`
- object SHA-256:
  `8d42167a91afa4d4bcd01f6c8bcc60f5e7a751ea482b6db7c1ae68cb8c360efa`
- bytes: `2,533`
- request self-hash:
  `9562b03d4d2f145f6bf0e934594851c1a08ce901df4e3adf4b05b458e7d875fe`
- `runtime_attempt_ordinal=0`
- `relaunch_allowed=false`
- `request_consumed_even_if_execution_response_is_ambiguous=true`
- predecessor: exact worker-stage identity above.

Its exact publication proof is:

| Proof object | Generation | SHA-256 | Bytes |
|---|---:|---|---:|
| request publication intent | `1787715358194337` | `fd72ec6370567594ada51d2dfd07bad4baaa22f4335354c39dec3f613e895797` | 710 |
| request target | `1787715358516177` | `8d42167a91afa4d4bcd01f6c8bcc60f5e7a751ea482b6db7c1ae68cb8c360efa` | 2,533 |
| request publication completion | `1787715358819303` | `14e8bccc4a88909ed360225a2b41e1e308f2c93c1ed9e06e27eedb08ce3b96c1` | 1,250 |

Verifier attempt 0 published:

| Object | Generation | Object SHA-256 | Bytes | Self-hash |
|---|---:|---|---:|---|
| `transport/stage-starts/verify-slate/35/attempt-00.json` | `1787715526710581` | `2bd29614608c18a0d5f5bd6e8d9c814c03ed080da9288ee8c1bb0e64d6c75f0d` | 3,611 | `04634a21e98123736ee522eede9bfac2b97b8f762c8e6da6c69d6a755bb9a232` |
| `slates/35/runtime/attempt-00/foundry-t230-verifier-runtime-v1.json` | `1787715612475399` | `bb477a4a2b8be8aaf211bf4ab6c3b60166eacd9b3f96af3ce92f03741c3aa03a` | 13,647 | `9c3954a6213f602bf2efdb00c384ab6d493dab2a46f06fc61aff067557938bf9` |

The runtime receipt binds role `verifier`, attempt `0`, frozen D2,
`release_runtime_verified=true`, `uses_realized_outcomes=false`, and
`historical_scoring_licensed=false`.

## Exact terminal signature

The execution was read only with exactly:

```text
gcloud run jobs executions describe atlas-cbc-32g-full-2023-w8-v1-sqs7z --project nfl-predictions-503414 --region us-central1 --format=json
```

The raw stdout is `20,576` bytes with SHA-256
`66f83ec7f96c252a5e39869243ef2460e40651bb11aa97e6e8093b9fba034b04`.
It contains exactly one `Completed` condition with status `False` and message:

```text
Task atlas-cbc-32g-full-2023-w8-v1-sqs7z-task0 failed with exit code: 0 and message: Internal error.
```

It records `failedCount=1`; `succeededCount` and `cancelledCount` are absent and
normalize to zero. It binds task count `1`, parallelism `1`, `maxRetries=0`,
timeout `21600`, frozen service account/image/CPU/memory/volume, runtime payload
SHA/bytes above, start time `2026-08-26T03:36:09.660912Z`, and completion time
`2026-08-26T03:42:49.772289Z`.

The one exact execution-scoped task read was:

```text
gcloud beta run jobs executions tasks list --execution=atlas-cbc-32g-full-2023-w8-v1-sqs7z --project=nfl-predictions-503414 --region=us-central1 --limit=2 --format=json
```

The raw stdout is `1,352` bytes with SHA-256
`e02cd53c9b8a687aea20053260c4bb3ebc9316d9c817e16061f61872026964c8`.
The JSON list length is exactly one. Its task name is
`atlas-cbc-32g-full-2023-w8-v1-sqs7z-task0`; its execution, job, and location
labels are exact; its `Completed` status is `False` with exact message
`Internal error.`; and its last-attempt status is exactly
`{"code":13,"message":"Internal error."}`. Both `retried` and task-status
`index` are absent, and the task has exact `spec={}`. Retry count is established
by the exact job/execution `maxRetries=0` envelope rather than by fabricating a
task field; task identity is fixed by the exact `task0` name. The validator
must require the exact permitted task metadata/spec/status key sets and reject
every extra field. The intent and eventual lock must bind the exact execution
and task argv, raw stdout SHA-256, and raw byte counts above.

Critically, the task's `lastAttemptResult` has no `exitCode` field. A future
validator must require `task_reported_exit_code_present=false`; it must not
invent task exit code zero. Exit code zero appears only inside the exact
execution-level condition message. The corrected ordinal-6 evidence now
matches these exact task-absence facts (`spec={}` and absent
`index`/`retried`/task `exitCode`), but its lineage, configured environment,
operation, result state, bridge, and downstream obligations remain distinct.

Only this complete contradictory platform signature is replacement eligible:
Cloud status code `13`, exact `Internal error.` literals, execution-level exit
code-zero message, failed count one, no retries, frozen envelope, exact
attempt-0 lineage, present start/runtime receipts, absent acceptance, and
absent verifier stage. Timeout, OOM, cancellation, signal, nonzero application
exit, solver rejection, verifier rejection receipt, ambiguous task list, or
any near-miss literal is ineligible.

## Job-B and configured-environment evidence

The frozen job-config object is generation `1787692866709710`, object SHA-256
`8ba18e69327913a88e63935c86d413fb6e86bd287a3be3fb38e4e9285dd7d864`,
`1,908` bytes, with config self-hash
`143cfe56b0a5e8b88b8f549e9bcb199c13799e7c823b87daa0c72150c2d2c684`
and observed-config hash
`8da37f747fb0385566b5cb23a5bb327534eed8e85743f20a63139f311e37cde3`.

The live job was read only with exactly:

```text
gcloud run jobs describe atlas-cbc-32g-full-2023-w8-v1 --project nfl-predictions-503414 --region us-central1 --format=json
```

Its raw stdout is `3,154` bytes with SHA-256
`6c04700281d64e5476783fd5c5a50927df96a0fd31585b6ae7ecaa3e7523b63e`.
It exactly matches the frozen envelope. Its base command is `bash`, base args
are `-ceu` and
`python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked`, and its
configured environment is exactly `{}`: canonical SHA-256
`44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`,
two bytes, zero entries.

The failed execution contains 55 configured launch variables. After exact
Cloud-JSON normalization of the 12 known empty-string `PRED1`, `LANE0`, and
`LANE1` quartet fields from name-only rows to empty strings, the sorted
canonical environment is `4,101` bytes with SHA-256
`79b1b21ccd485b83b3ef179519ab4a597538312cf04031a5f9d0e52e6af38146`.
It binds the operation, ordinal, attempt, image, predecessor, result identity,
transport, evidence, authority, compute release, request, and both publication
proof identities above. A replacement observer may normalize name-only rows
only for the exact expected-empty key set; an unknown name-only row, a missing
nonempty value, `valueFrom`, duplicate name, or extra field is terminal.

## Exact-name absence census

On 2026-08-26 UTC, each URI below returned exact `404 not found` from an
individual `gcloud storage objects describe` call. No prefix or bucket list
was used.

Ordinal-35 effect and attempt-1 surfaces:

- `slates/35-2024-w18/foundry-t230-slate-acceptance-v1.json`
- `transport/stages/verify-slate/35.json`
- `transport/stage-starts/verify-slate/35/attempt-01.json`
- `slates/35/runtime/attempt-01/foundry-t230-verifier-runtime-v1.json`
- `transport/platform-replacements/verify-slate/35/attempt-01/launch-request-v1.json`
- `transport/platform-replacements/verify-slate/35/attempt-01/launch-intent-v1.json`
- `transport/platform-replacements/verify-slate/35/attempt-01/launch-ownership-v1.json`
- `transport/platform-replacements/verify-slate/35/attempt-01/execution-terminal-v1.json`
- `transport/platform-replacements/verify-slate/35/attempt-01/success-completion-v1.json`
- `transport/platform-replacements/verify-slate/35/attempt-01/verifier-stage-amendment-v1.json`

Untouched ordinal-36 canonical surfaces:

- `transport/launch-requests/run-slate/36.json`
- `transport/stage-starts/run-slate/36/attempt-00.json`
- `slates/36/runtime/attempt-00/foundry-t230-worker-runtime-v1.json`
- `slates/36-2025-w01/foundry-t230-slate-analysis-v1.json`
- `transport/stages/run-slate/36.json`
- `slates/36-2025-w01/foundry-t230-slate-acceptance-v1.json`
- `transport/launch-requests/verify-slate/36.json`
- `transport/stage-starts/verify-slate/36/attempt-00.json`
- `slates/36/runtime/attempt-00/foundry-t230-verifier-runtime-v1.json`
- `transport/stages/verify-slate/36.json`

New ordinal-36 boundary namespace:

- `transport/platform-replacements/run-slate/36/boundary-after-verifier-35-v1/launch-intent-v1.json`
- `transport/platform-replacements/run-slate/36/boundary-after-verifier-35-v1/launch-ownership-v1.json`
- `transport/platform-replacements/run-slate/36/boundary-after-verifier-35-v1/execution-terminal-v1.json`
- `transport/platform-replacements/run-slate/36/boundary-after-verifier-35-v1/success-completion-v1.json`
- `transport/platform-replacements/run-slate/36/boundary-after-verifier-35-v1/worker-stage-amendment-v1.json`

Lane and panel surfaces:

- `transport/lanes/lane-1.json`
- `transport/platform-replacements/lanes/lane-1-verifier-35-amendment-v1.json`
- `transport/platform-replacements/panel/verifier-35-amendment-v1.json`
- `transport/platform-replacements/panel/ordinal-06-and-verifier-35-amendment-v1.json`
- `transport/launch-requests/finish-panel/panel.json`
- `transport/stage-starts/finish-panel/panel/attempt-00.json`
- `runtime/finalizer/attempt-00/foundry-t230-finalizer-runtime-v1.json`
- `transport/stages/finish-panel.json`
- `foundry-t230-panel-release-v1.json`

Every URI must still be absent in two exact-name metadata-only passes before
first-creator intent publication. Any presence, permission ambiguity, network
ambiguity, unequal object, or unexpected generation is terminal. The existing
ordinal-35 result is expressly excluded from absence checks: its exact pinned
presence is required, but its content remains unread before replacement
authorization.

## One-verifier attempt-1 law

After a separately implemented, tested, and independently reviewed controller
reopens every frozen identity and terminal fact above, it may create one
verifier-specific intent at:

```text
transport/platform-replacements/verify-slate/35/attempt-01/launch-intent-v1.json
```

The intent must bind this amendment's exact path/hash/bytes, the reviewed
implementation and tests, a post-test tracked-clean review lock, all terminal
raw-command hashes, the original request and proof, worker/result metadata
lineage, job/environment projections, complete absence census, runtime attempt
`1`, and `max_replacement_verifier_executions=1`. It must state
`second_replacement_allowed=false`.

Only the invocation proving it created the intent may make one async Cloud Run
submission. Equal-existing and racing intent paths are resolve-only and make
zero submission calls. Ambiguous, malformed, nonzero, or known-but-unverified
submission responses consume the sole attempt and require a create-once
execution-terminal receipt; they never license resubmission.

The replacement must use a new launch request in the verifier-specific
namespace with schema
`foundry-t230-ordinal-35-replacement-verifier-launch-request/v1`, a
create-once launch-ownership receipt, the exact unchanged Job-B envelope,
frozen D2, and the frozen result identity. The request is not the canonical v1
request and may never be passed to the frozen v1 request validator. The
first-creator sequence is strictly intent, one async submission, directly
known execution projection, launch ownership, then a verifier-specific
attempt-1 start at the deterministic attempt-01 URI with schema
`foundry-t230-ordinal-35-replacement-verifier-stage-start/v1`. That start must
bind this amendment, intent, ownership, exact worker-stage/result predecessor,
new execution, and frozen envelope before the verifier core begins. It is not
a v1 stage start and must never pass `validate_stage_start_v1`.

The frozen verifier core must then create the exact attempt-1 runtime
measurement and downstream acceptance/stage evidence at their frozen URIs.
The canonical verifier stage receipt may truthfully reference the separate
attempt-1 start because the stage-receipt format admits bounded runtime
attempts, but only the exception completion and supplemental-root validators
may reopen that start. The original attempt-0 request, start, runtime receipt,
and execution name are immutable and may not be reused.

Success requires all of the following, exact and create-once:

1. the frozen verifier core validates the generation-pinned ordinal-35 result;
2. the canonical ordinal-35 acceptance is created;
3. the attempt-1 verifier runtime measurement is created;
4. a truthful canonical verifier-35 stage receipt references the attempt-1
   start and runtime identities;
5. `verifier-stage-amendment-v1.json` binds the exception chain;
6. `success-completion-v1.json` exact-reopens all preceding identities; and
7. every authority field remains false without exception; the acceptance is
   recorded only as a generation-pinned factual identity.

Verifier failure, rejection, changed result identity, changed envelope,
unequal publication, or missing completion makes ordinal 35 and the panel
terminal-invalid. There is no second verifier replacement.

## Ordinal-36 boundary restoration

The ordinary v1 wrapper cannot honestly run ordinal 36 directly after an
attempt-1 verifier predecessor. Its predecessor validation reopens the
verifier-35 start through the original v1 stage-start constructor, which
requires runtime attempt `0`. Relabeling the attempt-1 verifier as attempt 0,
reusing its consumed request, or weakening that validator is forbidden.

After and only after the exact ordinal-35 acceptance and replacement
completion exist, one separate boundary controller may create the new
ordinal-36 boundary intent listed above. It may run the frozen ordinal-36
worker core once at its still-unused runtime attempt `0`, using frozen D2 and
the exact execution-manifest member for `2025-w01`. It must create the
standard-form canonical ordinal-36 launch request, attempt-0 start, runtime
measurement, result, and worker stage, while the separate boundary amendment
binds the truthful verifier-35 exception.

The boundary controller may bypass only the original wrapper's recursive
attempt-0 predecessor reopen. It may not bypass the core worker, manifest,
source authority, job envelope, launch ownership, start-before-core,
create-once, or no-outcome rules. A changed or ambiguous submission consumes
its sole boundary attempt.

Immediately before any boundary intent, a separately reviewed outcome-blind
boundary preflight must exact-reopen verifier-35 acceptance, stage amendment,
and success completion; re-observe the exact live Job-B envelope; and perform
two exact-name metadata-only absence passes over every ordinal-36 canonical
and boundary URI. The second pass occurs after the candidate and launch plan
are built and before intent creation. Permission, network, or metadata
ambiguity is terminal. The preflight writes only one fixed local tracked
receipt, performs no GCS publication or Cloud Run submission, and grants no
authority until a final tracked-clean boundary lock is independently reviewed.

Only the invocation proving it created the boundary intent may make the sole
ordinal-36 worker submission. An equal pre-existing or racing intent is
resolve-only and makes zero submission calls. Ambiguous, malformed, nonzero,
or known-but-unverified responses consume the boundary attempt and require a
create-once terminal receipt; none permits resubmission. The standard-form
ordinal-36 request publication proof, launch ownership, attempt-0 start,
runtime, result, worker stage, boundary stage amendment, and boundary success
completion must all exact-reopen before verifier 36 is licensed.

Once the canonical ordinal-36 worker stage, boundary stage amendment, and
boundary success completion all exist in standard attempt-0 form, the ordinary
distinct verifier for ordinal 36 can resume. After a standard ordinal-36
verifier stage exists, members 37 through 53 may proceed in the ordinary
sequential Lane-B form. The original full Lane-B controller must not restart
from ordinal 28 and no consumed request may be replayed.

## Supplemental Lane-B and panel obligations

The canonical v1 Lane-B ledger cannot validate verifier 35's truthful
attempt-1 start. It must not be fabricated or weakened. Instead, after
ordinals 28 through 53 each have exact acceptance and stage identities, a
separate supplemental Lane-B root must be published at:

```text
transport/platform-replacements/lanes/lane-1-verifier-35-amendment-v1.json
```

It must bind all 26 Lane-B worker/verifier stage and acceptance identities,
the original failed verifier lineage, the replacement completion, the
ordinal-36 boundary chain, and explicit proof that no member was skipped or
run twice. Concretely it binds exactly 52 ordered stage identities and 26
ordered acceptance identities, derived only from exact verifier-stage
receipts, plus globally unique Cloud Run execution identities across every
ordinary and exceptional Lane-B attempt. It may not open any result or
acceptance body. It must set
`support_rank_book_effect_fields_withheld=true`,
`uses_realized_outcomes=false`, and `historical_scoring_licensed=false`, with
every authority field false.

The original v1 finalizer also cannot honestly consume the canonical lane
roots because Lane A has the separate ordinal-6 attempt-1 exception and Lane B
has this verifier-35 exception. This amendment expressly supersedes only the
original ordinal-6 amendment's former terminal-panel assumption that an
ordinal-6 panel artifact could require an unchanged canonical Lane-B ledger
and core panel release. It does not supersede any ordinal-6 worker, bridge,
lineage, or no-outcome rule. A verifier-35 panel-obligation receipt must be
created at:

```text
transport/platform-replacements/panel/verifier-35-amendment-v1.json
```

The final supplemental panel root must be distinct and joint:

```text
transport/platform-replacements/panel/ordinal-06-and-verifier-35-amendment-v1.json
```

It must bind the ordinal-6 supplemental Lane-A root, this supplemental Lane-B
root and panel obligation, all 54 exact acceptance identities, both exception
chains, and false authority closure. To avoid a cyclic/impossible dependency,
the joint root binds the ordinal-6 amendment measurement, ordinal-6 worker-
recovery completion, ordinal-6 bridge completion, and supplemental Lane-A
root directly; it must not require or consume the old ordinal-6 full-panel
artifact, canonical Lane-B ledger, or core panel release. It derives all 54
acceptance identities only from the two supplemental lane roots and never
opens an acceptance/result/effect body. It sets
`support_rank_book_effect_fields_withheld=true`,
`uses_realized_outcomes=false`, `historical_scoring_licensed=false`, and every
authority field false without exception. The ordinary canonical finish
request/start/runtime/stage and canonical panel release must remain absent
unless a later independently frozen law proves they can be truthfully
reconstructed without hiding either exception.

No realized historical scoring may start merely because 54 acceptances
exist. Scoring requires the separately reviewed joint supplemental panel root
and the project's later explicit scoring authorization.

## Required implementation and review sequence

This draft authorizes no implementation reuse by assumption. The smallest
safe implementation is a verifier-35-specific contract/operator and focused
tests that reuse reviewed mechanical helpers without changing the frozen
ordinal-6 module. It must include:

1. exact terminal/task/environment validators for the verifier-35 evidence
   shape, including absent task `exitCode` and exact name-only empty variables;
2. generation-pinned request/proof/start/runtime/worker-lineage reopen;
3. metadata-only two-pass absence probes for every URI above;
4. a same-process first-creator verifier controller with mechanical terminal
   receipts for every submission outcome;
5. a distinct ordinal-36 boundary controller and adversarial tests;
6. success-completion, stage-amendment, supplemental Lane-B, panel-obligation,
   and joint-panel schemas; and
7. one outcome-blind real-artifact preflight followed by a tracked-clean
   review lock before any intent or submission.

The focused suite must cover punctuation/case/whitespace near misses, task
list length zero/two, task `exitCode` present, wrong result identity, present
effect surfaces, request reuse, attempt-0 reuse, envelope mutation, unknown
name-only environment rows, unequal intent races, ambiguous submission,
second submission, ordinal-36-before-acceptance, boundary worker attempt 1,
canonical Lane-B ledger fabrication, and panel release without both
supplemental lane roots.

## Current disposition and concerns

- **P0:** never normalize the absent task-level `exitCode` to zero. Its absence
  is part of the exact eligible signature.
- **P0:** never inspect the ordinal-35 result body during eligibility or
  preflight. Only the authorized replacement verifier may read its exact
  generation-pinned body.
- **P0:** never disguise verifier attempt 1 as attempt 0 to let ordinal 36 pass
  the old predecessor validator.
- **P0:** never build a canonical Lane-B ledger or panel release that omits
  either exception chain.
- **P1:** normalize Cloud name-only environment rows to empty strings only for
  the frozen expected-empty names; reject all other shapes.
- **P1:** ordinal 36 needs its own first-creator/ambiguous-submit boundary law;
  accepting verifier 35 alone does not license ordinal 36.
- **P1:** the final panel root must combine both ordinal-6 and verifier-35
  supplemental roots; two unrelated panel claims are insufficient.
- **P2:** helper reuse is desirable, but parameterizing the ordinal-6 module in
  place would blur two different task evidence shapes and two different
  downstream bridges. Keep the public contracts separate.

Current result: technical recovery is feasible with frozen D2 and no image
rebuild, but no verifier replacement, boundary execution, GCS publication,
test, or launch is authorized by this draft. The next action is independent
static review of this amendment and its evidence identities, followed by a
separate implementation plan—not a cloud submission.
