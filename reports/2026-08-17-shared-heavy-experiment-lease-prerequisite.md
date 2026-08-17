# Shared heavy-experiment lease prerequisite

Date: 2026-08-17
Status: implemented and offline-tested; not integrated into any launcher or
watcher; no Cloud Run job, GCS lease object, or experiment was created.

## Scope and binding

This implements the shared heavy-compute serialization prerequisite frozen in
`reports/2026-08-17-residual-world-portfolio-column-generation-prospective-protocol.md`
at SHA-256
`db02c7bb7994ea887ad32a935f3188bc78384c3c4b97a3dc712f3ffd2a8fc02a`.

The standalone tool is `scripts/heavy_experiment_lease.py`. It is deliberately
not wired into the currently running ATLAS or constraint-lattice watchers in
this milestone. The residual-world launcher remains prohibited until every
earlier/later heavy watcher is either durably terminal, durably disabled, or
uses this same object:

`gs://nfl-predictions-503414-raw/research-governance/heavy-experiment-active-v1.json`

This work changes transport/governance only. It reads no experiment output,
simulation effect, historical score, outcome, rank, ownership, or payout and
licenses no cloud launch or scientific conclusion.

## State machine

### Atomic acquisition

`acquire` validates and stores exactly:

- version `heavy-experiment-active-v1`;
- run ID;
- job family;
- exact 40-hex code SHA;
- immutable image digest ending in `@sha256:<64 hex>`;
- exact protocol SHA-256; and
- timezone-aware acquisition time.

The active GCS object is written with `if_generation_match=0`. The tool then
downloads the newly created exact generation, verifies its bytes and SHA-256,
and writes a create-only local acquisition receipt containing generation,
SHA-256, byte count, MD5, CRC32C, and create-only provenance. An occupied
object fails closed. Acquisition time is informational and is never used to
expire or replace a lease.

### Non-destructive audit

`audit` reports one of `absent`, `occupied-valid`, `occupied-invalid`, or
`indeterminate`. It pins the observed generation, records the raw content
hash, validates the payload when possible, and can compare it to a supplied
acquisition receipt. Current-object discovery is retried when a generation
changes between reload and pinned download; repeated churn becomes
`indeterminate`, never `absent`.
Every audit states:

- `age_evaluated=false`;
- `automatic_expiry_permitted=false`; and
- `delete_attempted=false`.

Malformed or unverifiable content remains occupied. Audit never deletes,
renews, rewrites, or guesses ownership.

### Normal release

Normal `release` requires a local reference to a separately uploaded,
generation-pinned GCS terminal-completion object. Its payload must use version
`heavy-experiment-terminal-completion-v1` and bind the exact lease run ID, job
family, code SHA, image digest, protocol SHA, lease generation, and lease
content SHA. A reference's `create_only=true` is a required uploader claim;
exact generation and content hash are independently checked. The integration
gate below requires that claim to originate from the narrowly permissioned
strict finisher rather than an arbitrary caller.

The completion is not accepted as a self-declared count envelope. It must
carry exact-generation/size/checksum/SHA references to three separately
immutable evidence objects, all of which are downloaded and reconciled before
any release intent exists:

1. `heavy-experiment-registered-population-v1`: the exact ordered unique
   `(job, execution)` population, expected count, protocol/lease identity, and
   registration time;
2. `heavy-experiment-terminal-census-v1`: the same ordered population with a
   terminal state, completion time, and exact object reference for every
   execution receipt; and
3. `heavy-experiment-strict-harvest-v1`: exact population/census bindings,
   strict disposition, artifact-receipt aggregate, outcome scope, and release
   class.

Every per-execution receipt is independently downloaded and must be
`heavy-experiment-terminal-execution-v1`. The tool checks its lease/protocol
identity and embedded Cloud Run execution document: exact execution name,
one non-`Unknown` `Completed` condition, completion time, state-consistent
succeeded/failed/cancelled counts, and task-count closure when `taskCount` is
present. The envelope, population, census, execution receipts, and strict
harvest must then agree on:

- the full registered execution population is terminal;
- strict harvest/closure is complete;
- expected and terminal execution counts are equal and positive;
- successful + failed + cancelled equals the expected population;
- nonterminal count is zero;
- the recomputed ordered execution-receipt aggregate and exact strict-harvest
  object SHA-256;
- outcome use is explicitly declared; and
- disposition is either:
  - `terminal-success`, with every execution successful; or
  - `terminal-fail-closed`, with a nonempty closure reason.

A local watcher ending, an execution merely disappearing, an old acquisition
time, a partial population, or a non-strict completion cannot release the
lease.

Before deletion, the tool writes a deterministic create-only durable release
intent binding the lease and completion generations/hashes. It then deletes
only the exact active generation with `if_generation_match=<generation>`.
Immediately before the intent and again before deletion it proves the target
is still the current object, not merely a retained older generation. It writes
a separate create-only durable release-completion record and reports whether
the lease is globally absent or a successor generation is active. A retry
after an interrupted delete can resume only from a pre-existing,
byte-compatible intent. Absence of both the active generation and such an
intent fails closed.

### Explicit operator recovery

There is no `--force`, TTL, timeout, stale-age, process-signal, or automatic
cleanup path. `recover` requires all of:

1. a create-only/non-destructive audit file for the exact occupied generation
   and content SHA;
2. a strict operator authorization JSON whose SHA binds that audit;
3. operator identity and a nonempty reason;
4. affirmative declarations that the run is abandoned, no live cloud
   execution remains, and no live local launcher remains;
5. at least one durable-evidence description;
6. affirmative permission for the exact-generation delete; and
7. the generation, SHA-256, and run ID typed again as independent CLI
   confirmations.

Recovery re-downloads and re-hashes the exact generation. Before any intent or
delete, it uploads the exact audit and authorization bytes to deterministic
create-only GCS objects. It writes a durable create-only recovery intent
containing their exact object identities plus the operator, reason, and
evidence, proves the target is still current, performs only the
exact-generation delete, then writes a durable recovery-completion record. If
the audited generation has been replaced, a newer lease is never deleted. An
interrupted recovery can resume only from its matching pre-existing durable
intent.

## Generic terminal-completion contract

Strict finishers that will use this tool must create a payload of this shape
under a unique create-only GCS URI and then provide a generation/hash reference
to `release`:

```json
{
  "version": "heavy-experiment-terminal-completion-v1",
  "run_id": "registered-run-id",
  "job_family": "registered-job-family",
  "code_sha": "<40 hex>",
  "image": "<immutable image>@sha256:<64 hex>",
  "protocol_sha256": "<64 hex>",
  "lease": {
    "uri": "gs://nfl-predictions-503414-raw/research-governance/heavy-experiment-active-v1.json",
    "generation": "<exact generation>",
    "sha256": "<exact active-object SHA-256>"
  },
  "registered_population_object": {
    "uri": "gs://.../population.json",
    "generation": "<exact generation>",
    "sha256": "<64 hex>",
    "bytes": 123,
    "md5_hash": "<GCS MD5>",
    "crc32c": "<GCS CRC32C>",
    "create_only": true
  },
  "terminal_census_object": {"...": "same exact object contract"},
  "strict_harvest_object": {"...": "same exact object contract"},
  "release_class": "terminal-success",
  "full_population_terminal": true,
  "strict_harvest_complete": true,
  "expected_executions": 54,
  "terminal_executions": 54,
  "succeeded_executions": 54,
  "failed_executions": 0,
  "cancelled_executions": 0,
  "nonterminal_executions": 0,
  "terminal_execution_receipts_sha256": "<64 hex>",
  "strict_harvest_sha256": "<64 hex>",
  "uses_realized_outcomes": false,
  "completed_at": "<timezone-aware ISO-8601>"
}
```

Mechanism-specific fields may be added. The generic required fields above do
not replace the mechanism's own frozen strict-finisher checks.

## Validation

`tests/test_heavy_experiment_lease.py` uses a completely offline fake GCS
implementation with object generations and preconditions. Thirty tests
pass and cover:

- generation-match-zero acquisition and exact post-upload verification;
- occupied acquisition without overwrite or delete;
- ancient acquisition time without expiry;
- malformed occupied-object audit without delete;
- generation-change audit retry rather than a false `absent` result;
- create-only local receipts;
- rejection of a self-declared completion envelope without its immutable
  population/census/harvest evidence;
- exact per-execution receipt downloads and rejection of a Cloud Run
  `Completed=Unknown` execution;
- strict/full-population success release;
- valid terminal fail-closed release;
- rejection of partial, nonterminal, non-strict, miscounted, or hash-mismatched
  completions before any intent/delete;
- re-hashing of the active exact generation immediately before deletion;
- rejection of a retained old generation when a successor is current;
- durable-intent-before-delete and completion-after-delete ordering;
- exact generation-match deletion;
- interrupted deletion and idempotent intent verification;
- resume after deletion succeeded but durable completion creation was
  interrupted;
- refusal to manufacture an intent after an unexplained missing active object;
- explicit operator recovery confirmations and audit binding;
- durable exact audit and authorization objects before operator deletion;
- independent CLI re-entry of the exact recovery generation, SHA, and run ID;
- rejection of missing recovery confirmations;
- protection of a newly reacquired generation;
- interrupted operator-recovery completion resumption; and
- duplicate-key JSON rejection before deletion.

Commands run:

```text
.venv/bin/python -m py_compile scripts/heavy_experiment_lease.py \
  tests/test_heavy_experiment_lease.py
.venv/bin/pytest -q tests/test_heavy_experiment_lease.py
# 30 passed
git diff --no-index --check /dev/null <each-new-file>
# expected diff exit 1; zero whitespace diagnostics
```

Implementation SHA-256 before this report was written:

- `scripts/heavy_experiment_lease.py`:
  `53a653d27e13afb5d708d8e076f220e328273290d669729fea12001b34497946`
- `tests/test_heavy_experiment_lease.py`:
  `dbb0a49322f27cff893073ab761f349ba974d95c8875fd00646442260059ee1e`

## Remaining integration gate

This standalone prerequisite is not sufficient by itself. The tool enforces
structural and content integrity, not adversarial authentication against a
principal that already has unrestricted write/delete access to the governance
prefix. Before the first heavy experiment uses it:

1. package and smoke the tool from the exact immutable clean-archive image;
2. add the registered-population, per-execution terminal receipt, census,
   strict-harvest and completion payloads to that mechanism's strict finisher;
3. acquire only after all queue/source/build preflights and immediately before
   the first job creation;
4. release only from the durable terminal completion reference;
5. prove every potentially concurrent heavy watcher participates in this same
   lease or is durably terminal/disabled; and
6. give ordinary launchers create access to the active object but reserve
   operator recovery and governance-record deletion to a distinct operator
   IAM principal (or add a separately verified signed/KMS authorization);
7. verify bucket lifecycle, retention, soft-delete/versioning, and IAM policy
   cannot silently expire or remove the active lease or evidence objects;
8. add real-GCS/emulator concurrency/API tests plus integration tests to each
   launcher/watcher without changing its frozen scientific law; and
9. treat external completion references' `create_only` flag as trusted only
   when it came from that narrowly permissioned, generation-zero uploader.

Until those conditions hold, an absent active lease does not license the
residual-world pilot or any other queued cloud job.
