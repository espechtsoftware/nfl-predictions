# Recourse-aware initial-book single-job transport amendment

Date frozen: 2026-08-28, before any recourse-aware initial-book cloud
execution, shard, aggregate, or result existed.

Applies to execution ID
`20260817-recourse-aware-initial-book-scorefree-v1` and only replaces its
Cloud Run transport. The scientific protocol, score-free runner, candidate
population, five-fold evaluation, six-condition gate, run ID, and create-only
GCS prefix are unchanged.

## Why this amendment is necessary

The original transport creates one Cloud Run Job resource for each of the 54
slates. The project is at the `JobsPerProject=1000` limit, so that transport
cannot create even its canary job. Deleting old jobs would erase useful cloud
execution history and is outside this experiment's authority.

The active V6 build is source-compatible but its deliberately narrow
`Dockerfile.r6-current-bank-crossed-screen` does **not** copy the recourse
runner, aggregator, protocols, or CBWU receipt. Digest `sha256:c491ad...` is
therefore explicitly ineligible for this transport.

An earlier full-runtime image contains the exact recourse dependency closure.
Every admitted recourse source and transitive source listed by the operator is
byte-identical between its commit and current frozen sources. Its successful
build ran the full repository suite and explicitly smoke-tested both the
recourse runner and aggregator inside the resulting container:

- source commit: `96f4487bdefa297f66d03e4aca896728581540b2`;
- Cloud Build: `3503c493-60d5-4fe6-a853-583679c8e33d`;
- image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:9956f2b4444bc60255c29a1844c23a1f772d6b0c85ae1a532e032ece975e86ed`.

A second image build would reproduce an already validated runtime without
changing the experiment. This amendment therefore binds the existing build,
Git revision, image digest, successful validation steps, registry identity,
and exact runtime-file hashes instead.

## Replacement transport

After every V6 execution using it is terminal, reuse only Cloud Run Job
`atlas-cbc-32g-full-2023-w8-v1`, immutable UID
`1f4bcf0a-2300-4afa-9fc1-9981844c8275`.

1. Capture the job's pre-update JSON, exportable configuration, and complete
   execution inventory. Refuse to continue if an execution is nonterminal.
2. Reject the narrow V6 runtime and validate the exact full-runtime build,
   image digest, Git revision, frozen protocols, CBWU receipt, terminal ATLAS
   queue branch, absent local run directory, and empty create-only cloud
   prefix.
3. Update that existing UID once to the frozen one-task envelope: 4 CPU,
   16 GiB, four-hour timeout, zero retries, the frozen service account,
   `python` command, exact image, and exact code/image environment.
4. Launch only 2023 Week 1 using a per-execution argument override. No other
   slate may be submitted by the prepare command.
5. A separate validation command must prove terminal success, an exact
   one-execution post-inventory delta, the exact execution snapshot, one
   create-only canary object, all five R0--R4 folds, and the absence of
   realized-outcome or aggregate-disposition fields.
6. Only an explicit `release` command accepting that create-only validation
   receipt may submit the other 53 season/week overrides. It records each
   returned execution identity with an immediate local `fsync`. Every
   execution also carries a deterministic cell token in its immutable
   execution-only environment. If the operator process stops after Cloud Run
   accepts a launch but before the ledger append, a later explicit invocation
   reconciles at most one exact token/argument-bound provider execution and
   appends it rather than launching a duplicate.
7. The `harvest` command requires the complete 54-row ledger, an exact
   before/after provider-inventory delta, and terminal success for all 54
   immutable execution snapshots. It downloads all 54 distinct create-only
   shards, validates unique-key JSON and object identities, checks the
   retained canary bytes, invokes the unchanged strict score-free aggregator,
   uploads the report create-only, and writes a durable harvest receipt.
8. After that full harvest, the operator restores the captured export with
   `gcloud run jobs replace`, then proves the same immutable UID, stable
   metadata, and exact prior spec before writing terminal completion. A
   definitive canary/grid/validation failure follows the same restoration
   path. A merely nonterminal execution or an ambiguous launch response is a
   resumable pending state and does not consume or mutate another cell.

The reused job name may repeat in the 54-row execution ledger. The 54
execution identities, season/week arguments, output URIs, and object
generations remain distinct. Validation is against the captured inventory
delta and each immutable execution snapshot, not against a false assumption
that a job has only one lifetime execution.

The job update clears inherited secrets, volumes, volume mounts, Cloud SQL,
VPC connector, and network attachments. Runtime validation rejects duplicate
or secret-backed environment entries, inherited attachments, a mismatched
job UID label/owner reference, or an execution whose deterministic cell token
does not match its arguments and output URI.

## Prohibitions and failure behavior

- Never create, deploy, delete, or rename a Cloud Run Job.
- Never run this transport while the V6 chain still owns the reused job.
- Never launch the remaining 53 from the prepare or validation command.
- Never read Cloud Logging, BigQuery outcomes, realized scores, ownership,
  rank, payout, ROI, or another experiment's effect.
- Never infer a missing execution or shard from logs.
- A mismatched UID, image, build, source, queue receipt, inventory delta,
  execution snapshot, object inventory, or canary payload fails closed.
- A partial grid submission is not automatically retried. Preserve its local
  intents, ledger and returned cloud execution identities for explicit
  review. Re-running `release` is the explicit resume action: it may recover
  only one exact next-cell execution from the provider inventory and never
  skips, reorders, or duplicates a cell.
- The captured job export is immutable run state. Restoration refuses a
  changed UID or a live job contract that is neither the admitted recourse
  envelope nor the already-restored original contract. A failed restoration
  prevents terminal completion and requires manual recovery.

This amendment changes transport mechanics only. It does not license a
historical outcome read, production adoption, UI change, or money entry.
