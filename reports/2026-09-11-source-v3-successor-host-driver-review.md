# Source-v3 successor host-driver review

Date: 2026-09-11
Status: implementation and hermetic validation; independent review of the
second crash-window successor is pending. No Cloud Build, Cloud Run, GCS write,
object read, warehouse query, or production-worktree mutation was performed;
isolated review commits only were pushed.

## Decision

Use `scripts/finish_corpus_r6_matchup_source_v3.py` for the first source-v3
successor after the historical capture-plan compatibility repair, the
generation-exact capture-plan-v3 freeze, and the subsequent pushed release
commit containing the reviewed `a25ef6f0`/`b2465712` source-v3 and shared-lane
repairs. The driver is commit-agnostic: its `--code-sha` must equal both the
clean checkout's `HEAD` and its already-fetched `origin/main`, and the exact
driver and source-v3 controller must exist in that commit.

The driver history is cumulative. Integration must include initial driver
`dbfe5b87a9cf0ed7e09cfe50c3b137230b9537d0`, first crash-window successor
`9bab943843678364efd2d989ddc5f5fe74eb4e24`, and second successor
`eca72045633b193da177f9e980f020b65cf436f8`. The first successor is a delta
whose parent is the HANDOFF-only
`52fa50c7317e75e549f5712d5598e6b2bd5a4a48`, and the second builds on its
provider-attribution validation; neither is a standalone replacement for the
initial driver. The required source controller and shared-lane predecessors remain
`a25ef6f0ecd75830641eec9081dc54ff5dd24e1a` and
`b2465712a0c2fff0f0953814d634a82200e673c1` respectively.

The chain remains **NO-GO** before that ordering is complete. In particular,
do not recapture or relabel sealed seven-pack v4, and do not use the source-v3
driver until the repaired capture-plan freeze has succeeded against that exact
sealed generation and its reviewed lock has reached a distinct pushed Commit
B.

## Audit of the existing source-v3 controller

The exact controller repair at
`a25ef6f0ecd75830641eec9081dc54ff5dd24e1a` is retained. It correctly
normalizes Cloud Run's two exact timeout projections, requires an exact clean
Git checkout, validates one-task/zero-retry provider execution state, and
collects exactly one canonical stdout result whether Cloud Logging exposes it
as `textPayload` or `jsonPayload`.

The controller intentionally remains a one-phase primitive. Before this host
driver it had no durable pre-call intent, returned the provider execution name
without the UID, did not hold the production lane across phases, and had no
safe automatic recovery for an `execute` response lost after provider
creation. Recalling the primitive after an ambiguous return could therefore
create a second execution. The new driver wraps that controller unchanged and
closes those host-level gaps; it does not weaken the in-controller provider or
result gates.

### Crash-window correction after initial review

Independent review found one host-only restart defect in initial driver commit
`dbfe5b87`: after `provider-attribution.json` was created but before
`launch.json` existed, a restart described the same execution at its newer
status and tried to overwrite the create-once attribution with different
canonical bytes. A normal `Completed` transition from missing/unknown to true
was therefore misclassified as a local collision even though name, UID, and
every immutable provider-envelope field still matched.

Pushed successor `9bab943843678364efd2d989ddc5f5fe74eb4e24`
closes that first gap. It adds a create-once structured provider-attribution receipt
which binds the original name, UID, snapshot SHA, attribution method,
request/intent hashes, and optional controller response. On restart it keeps
that original snapshot/SHA/method for launch reconstruction while separately
requiring the current reused-job latest pointer to equal the same name and the
current exact provider envelope to retain the same UID and immutable phase
configuration. Current status may lawfully advance; it never becomes the
historical attribution snapshot.

Independent review then reproduced a deeper two-stage crash window in that
successor. The old launch-recovery receipt retained only the first provider
snapshot's SHA. If that snapshot had `Completed` missing, the process crashed
before raw attribution, Cloud Run advanced to `Completed=True`, and a second
process crashed after writing the later attribution but before its structured
receipt, the next restart correctly detected a recovery/attribution collision
but could never resume the single already-launched execution.

Pushed successor `eca72045633b193da177f9e980f020b65cf436f8`
closes the deeper window by making launch-recovery/v2 the atomic first
attribution authority. It embeds the complete validated provider snapshot,
its SHA, exact name/UID, request and intent hashes, recovery method, and null
controller context in one create-once file. If raw attribution is absent, a
restart revalidates the current exact provider latest name, UID, and immutable
phase configuration but discards its later status representation and creates
raw attribution from the frozen recovery body only. If recovery and
attribution both exist, they must be exactly equal; completed-launch loading
enforces the same equality. A wrong current latest name, UID, or configuration
fails before any attribution or launch authority is created and never recalls
the launcher. Any post-intent artifact without its required intent remains
refused before the controller launch action can run.

## Implemented invariants pending final independent review

The host driver:

- validates a successful Cloud Build whose requested `source.gitSource` and
  provider-resolved Git source are both exactly the pushed commit, whose
  `_CODE_SHA` and `_BUILD_IMAGE` substitutions are exact, and whose sole
  matching result image supplies the immutable digest;
- recomputes the clean-commit dependency closure and secure-reads the tracked
  capture-plan-v3 blob before it creates any launch intent;
- freezes the exact 54 task-0 output URIs and 2,811 full-batch output URIs,
  proves the namespaces are disjoint, and performs 2,865 direct object
  metadata reads with no object listing; any existing object consumes and
  rejects the run ID;
- runs only beneath the canonical production `launcher_registry.sh` owner and
  the exact reused-job lane. It validates receipt bytes, wrapper PID/start
  ticks, ancestor relationship, canonical external state root, and the held
  lane flock. One wrapper process owns that lease across worker, verifier,
  publisher, result collection, and the independent reopener;
- writes create-once local request, exact payload, provider-before, launch
  intent, raw launcher return, provider attribution, structured attribution
  receipt, launch, poll, terminal, result-attempt, controller-result,
  provider-receipt and failure evidence;
- consumes the launch intent before calling the phase controller. Once an
  intent exists, no code path calls that phase's launch action again;
- treats controller output as a hint. It accepts a launch only when the reused
  job's latest name changed from the pre-launch snapshot, the exact execution
  UID is captured, and the immutable provider execution matches job/job UID,
  image, code, build, run, phase, deterministic payload, one task, one-way
  parallelism, zero retries, resources, timeout, service account and all
  predecessor execution bindings;
- tolerates a temporarily absent job latest pointer or execution describe and
  a missing/`Unknown` `Completed` condition. Such execution state remains a
  read-only observation when failed/cancelled/retried counts are zero and the
  one-task succeeded/running counts are internally consistent. It also admits
  a valid completion time appearing just before `Completed=True`, but never
  declares success until the exact `Completed=True` terminal envelope exists;
- never relaunches after an ambiguous return. If provider latest cannot
  resolve the consumed intent, recovery requires an operator-supplied exact
  execution name **and** UID, followed by the same full provider-envelope
  validation;
- after either provider attribution or atomic launch recovery but before the
  launch receipt, retains the original attribution bytes, SHA and method
  across provider status drift, while separately revalidating exact current
  latest name, UID and immutable envelope;
- requires four distinct execution names and accepts the release only after
  the later write-disabled reopener's provider receipt independently names
  and matches the publisher, verifier and worker; and
- extracts `source_release_v3_identity` from that independent reopener (not
  `batch_release_identity`), then requires it to equal the publisher's source
  identity. Both identities are retained separately.

All local state is outside Git at:

`/home/erich/.local/state/nfl-dfs/corpus-r6-matchup-source-v3/<RUN_ID>/`

## Exact production recipe after the blockers clear

Use a dedicated clean release worktree already fast-forwarded to the final
pushed source-v3 commit. Do not fetch, checkout, edit, or create untracked
files in that worktree after freezing `CODE`.

```bash
set -euo pipefail

REPO=/absolute/path/to/clean/source-v3-release-worktree
cd "$REPO"
CODE=$(git rev-parse HEAD)
test "$CODE" = "$(git rev-parse --verify 'refs/remotes/origin/main^{commit}')"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git remote get-url origin)" = \
  https://github.com/espechtsoftware/nfl-predictions.git

RUN_ID="20260911-r6-matchup-source-v3-${CODE:0:12}-v1"
IMAGE_TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:matchup-source-v3-${CODE}"

gcloud builds submit \
  https://github.com/espechtsoftware/nfl-predictions.git \
  --git-source-revision="$CODE" \
  --config="$REPO/cloudbuild.corpus-r6-matchup-source-v3.yaml" \
  --substitutions="_CODE_SHA=$CODE,_BUILD_IMAGE=$IMAGE_TAG" \
  --project=nfl-predictions-503414 \
  --format='value(id)' --quiet
```

Capture the one returned build UUID as `BUILD_ID`. This submission is itself
create-once operational authority: if the command return is missing or
ambiguous, **do not submit again**. Reconcile the sole provider build created
after the recorded submission time by exact requested/resolved Git source,
`_CODE_SHA`, `_BUILD_IMAGE`, and result-image tag. Stop for adjudication if
zero or more than one build matches.

After success, describe that exact `BUILD_ID` and extract the digest only from
the single result-image row whose name equals `IMAGE_TAG`:

```bash
BUILD_JSON=$(mktemp)
gcloud builds describe "$BUILD_ID" \
  --project=nfl-predictions-503414 --format=json >"$BUILD_JSON"
DIGEST=$(jq -er \
  --arg id "$BUILD_ID" --arg code "$CODE" --arg tag "$IMAGE_TAG" \
  --arg repo https://github.com/espechtsoftware/nfl-predictions.git '
    select(.id == $id and .status == "SUCCESS" and
      .source.gitSource == {url:$repo,revision:$code} and
      .sourceProvenance.resolvedGitSource == {url:$repo,revision:$code} and
      .substitutions._CODE_SHA == $code and
      .substitutions._BUILD_IMAGE == $tag) |
    [.results.images[]? | select(.name == $tag) | .digest] |
    if length == 1 then .[0] else error("image digest differs") end
  ' "$BUILD_JSON")
IMAGE="${IMAGE_TAG%:*}@${DIGEST}"
```

Before continuing, prove `RUN_ID` has never had a source-v3 intent and was not
consumed by a prior failed preflight. The driver then freezes the current
tracked plan and performs all 2,865 exact no-listing absence checks itself.
Run the entire chain under one canonical production lane lease:

```bash
exec "$REPO/scripts/launcher_registry.sh" run \
  --root "$REPO" \
  --state-root /home/erich/.local/state/nfl-dfs/production-launcher-registry \
  --lane atlas-cbc-32g-full-2023-w8-v1 \
  --owner production \
  --target-prefixes "$RUN_ID" \
  -- "$REPO/scripts/finish_corpus_r6_matchup_source_v3.py" \
  --run-id "$RUN_ID" \
  --code-sha "$CODE" \
  --build-id "$BUILD_ID" \
  --image "$IMAGE" \
  --execute \
  --confirmation I_UNDERSTAND_SOURCE_V3_COMPLETE_CHAIN
```

The expected terminal file is
`.../<RUN_ID>/terminal.json`. It is not sufficient by itself: retain the
separate `source-release-v3-identity.json`, `batch-release-v3-identity.json`,
all four exact execution UIDs, four provider receipts, and canonical launcher
completion.

## Ambiguous-return recovery

Do not delete or edit the run directory. Reacquire the same production lane
for the same `RUN_ID` and run the identical command. If provider latest alone
cannot resolve the consumed intent but an independently reviewed exact
execution exists, add only the blocked phase's pair, for example:

```text
--publish-execution atlas-cbc-32g-full-2023-w8-v1-abc12
--publish-execution-uid 00000000-0000-4000-8000-000000000000
```

Supplying only a name or only a UID is refused. The execution is still refused
unless its complete provider envelope matches the frozen phase request. A
terminal provider failure consumes the run namespace; it is evidence, never
retry authority.

## Validation

- New driver tests: 21 passed.
- Existing source-v3 core/CLI/controller plus new driver: 42 passed.
- Exact Cloud Build focus including the one-task component reducer: 43 passed.
- Python compilation and driver `--help`: passed.
- Cloud execution: intentionally not performed.
