# R6 L2b task0-to-full54 operational runbook

Date: 2026-08-28
Scope: generate the fixed 54-slate 2023--2025 L2b challenger bank, first with a real task-0 smoke and then one full 54-task fan-out. This runbook does not read realized outcomes and does not launch the downstream selector/evaluator.

## Ready inputs and fixed execution identity

The following two scientific inputs are already immutable GCS objects and can be used directly in the preparation request:

```json
{"later_source_freeze_identity":{"bytes":4566802,"generation":"1787367678830738","sha256":"c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a","uri":"gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/source/later-source-freeze.json"},"pit_target_panel_identity":{"bytes":2525733,"generation":"1787958077769438","sha256":"482ac35706514b0c5bb9a79d23756e8336de84655b6412a7cee3723ff1d48446","uri":"gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-l2b/20260828-score-sprint-5aabe2c8/inputs/pit-target-panel.json"}}
```

The target panel is the catalog-spined 54-slate artifact with `target_panel_sha256=d53114288dd898ae73bc9246761050e08fd01d3790c00c33b9ac94f824318e53`. Its score-free source frame is generation `1787958037039226`, SHA-256 `fd5c49bcbcf4b9e714e7e03a0c8e1791759945e18e4aeb629eaff4d2e1c2434b`, 74,160 bytes. The source frame is embedded by identity in the target panel; it is not a separate preparation-request field.

The only allowed Cloud Run carrier for this lane is:

- project: `nfl-predictions-503414`
- region: `us-central1`
- job: `atlas-minimal-c-s2023-w3-v1`
- required job UID: `064df315-0fb5-4b86-a5f9-6c73ac1c5eb3`
- task-0 scope: one task, index 0, no retries
- full scope: exactly 54 tasks, no retries

Do not use the older L2b job/UID mentioned in an earlier handoff entry. The current code and this runbook deliberately use the idle W3 job above.

## Launch blockers that must be closed first

1. **Commit/package boundary.** `HEAD` is currently `5aabe2c85ef6808fbe5a65aabc7b5d0013d84f7f`, but the task0/full54 operator and W3 job binding are still working-tree changes. Commit the intended L2b files, obtain the new clean 40-hex commit, and build the consolidated image from exactly that commit. Do not use `5aabe2c8` as the runtime code identity unless the current operator changes have first been committed into a descendant build.
2. **Calibration release identity.** The available release at `/tmp/r6-belief-l2-20260828-b2781025-r2/l2b-base-rate-calibration-release-4835d104.json` passes the scientific gates, but its `code_sha` is `4835d104469216faf0a4fd2298ece42d0349a8ca` and it has no generation-pinned GCS identity. Regenerate the identical fixed 2018--2022 fit with the final committed SHA, then publish the canonical JSON create-once and retain `{uri,generation,sha256,bytes}`. The preparation code validates the release and exact-opens its identity, but does not itself compare `release.code_sha` to `source_commit_sha`; that equality is therefore a mandatory operator preflight.
3. **Terminal build receipt.** No terminal receipt yet exists for the final commit/image. Create and publish a receipt containing exactly `build_id`, `finish_time`, `image_digest`, `image_tag`, `project_id`, `region`, `source_commit`, `start_time`, and `status`. It must bind `status=SUCCESS`, the final commit, the immutable `sha256:...` image digest, project `nfl-predictions-503414`, region `us-central1`, and an Artifact Registry tag under `us-central1-docker.pkg.dev/nfl-predictions-503414/`.
4. **Carrier idle/UID check.** Before configuration, confirm the W3 job still has UID `064df315-0fb5-4b86-a5f9-6c73ac1c5eb3` and no active latest execution. The operator repeats both checks and refuses to update or launch if either differs.
5. **New output namespace.** Choose one unused prefix below `gs://nfl-predictions-503414-corpus-retrieval/research/`, ending in `/`. Preparation, task outputs, and finalization are create-once. Never point a scientifically different run at an existing prefix.

The PIT frame is complete and admissible, but all 8,293 2025 rows intentionally use `previous_state=unknown` and `injury_status=null`. That is a declared score-free fallback, not hidden future information; it does make the 2025 treatment less informed than 2023--2024.

## 0. Finalize calibration and image identities

Use a clean worktree materialized from the final commit and a new local run directory. The shared development worktree may remain dirty with unrelated agent work; it must not be used as the image build context. Every CLI output below must be a previously absent absolute path in an existing directory.

```bash
export REPO=/absolute/path/to/clean-final-commit-worktree
export PYTHON="$REPO/.venv/bin/python"
export CLI="$REPO/scripts/run_corpus_r6_l2b_panel_cloud_v1.py"
export CODE_SHA="$(git -C "$REPO" rev-parse HEAD)"
export RUN_ID="20260828-r6-l2b-${CODE_SHA:0:12}-v1"
export RUN_DIR="$REPO/reports/r6-l2b-panel-runs/$RUN_ID"
mkdir -p "$RUN_DIR"
test -z "$(git -C "$REPO" status --porcelain)"
```

Regenerate the passing release from the frozen evidence after the final commit exists:

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" \
  "$REPO/scripts/run_corpus_r6_l2_base_rate_v1.py" \
  --evidence-dir /tmp/r6-belief-l2-20260828-b2781025-r2 \
  --code-sha "$CODE_SHA" \
  --output-file "$RUN_DIR/l2b-calibration-release.json" \
  > "$RUN_DIR/l2b-calibration-summary.json"

test "$(jq -r .code_sha "$RUN_DIR/l2b-calibration-release.json")" = "$CODE_SHA"
jq -e '.gate.passes == true and .final_fit_seasons == [2018,2019,2020,2021,2022] and .final_fit_scope == "prospective-2023-plus-only" and .uses_lineup_outcomes == false' \
  "$RUN_DIR/l2b-calibration-release.json"
```

Publish that release create-once, exact-reopen it, and save its canonical identity as:

```text
$RUN_DIR/l2b-calibration-release.identity.json
```

Build the one consolidated image from `CODE_SHA`, record its immutable digest in `IMAGE_DIGEST`, construct the terminal receipt described above, publish it create-once, and save its identity as:

```text
$RUN_DIR/terminal-build-receipt.identity.json
```

Before continuing, these checks must pass:

```bash
export IMAGE_DIGEST="sha256:<64-lowercase-hex>"
test "$(jq -r .uri "$RUN_DIR/l2b-calibration-release.identity.json")" != null
test "$(jq -r .uri "$RUN_DIR/terminal-build-receipt.identity.json")" != null
test "$(jq -r .code_sha "$RUN_DIR/l2b-calibration-release.json")" = "$CODE_SHA"
```

## 1. Create the canonical preparation request and manifest

Choose a fresh output prefix:

```bash
export OUTPUT_PREFIX="gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-l2b/$RUN_ID/"
export PREP_REQUEST="$RUN_DIR/preparation-request.json"
```

Create the request without a trailing newline; the CLI requires canonical JSON bytes:

```bash
"$PYTHON" - "$PREP_REQUEST" \
  "$RUN_DIR/l2b-calibration-release.identity.json" \
  "$RUN_DIR/terminal-build-receipt.identity.json" <<'PY'
import json, os, pathlib, sys

out, calibration_path, build_path = map(pathlib.Path, sys.argv[1:])
load = lambda path: json.loads(path.read_bytes())
request = {
    "later_source_freeze_identity": {
        "bytes": 4566802,
        "generation": "1787367678830738",
        "sha256": "c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a",
        "uri": "gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/source/later-source-freeze.json",
    },
    "calibration_release_identity": load(calibration_path),
    "pit_target_panel_identity": {
        "bytes": 2525733,
        "generation": "1787958077769438",
        "sha256": "482ac35706514b0c5bb9a79d23756e8336de84655b6412a7cee3723ff1d48446",
        "uri": "gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-l2b/20260828-score-sprint-5aabe2c8/inputs/pit-target-panel.json",
    },
    "terminal_build_receipt_identity": load(build_path),
    "output_prefix": os.environ["OUTPUT_PREFIX"],
    "source_commit_sha": os.environ["CODE_SHA"],
    "immutable_image_digest": os.environ["IMAGE_DIGEST"],
    "reused_job_name": "atlas-minimal-c-s2023-w3-v1",
    "reused_job_uid": "064df315-0fb5-4b86-a5f9-6c73ac1c5eb3",
}
out.write_bytes(json.dumps(request, sort_keys=True, separators=(",", ":")).encode())
PY

env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" prepare \
  --request-file "$PREP_REQUEST" \
  --output-file "$RUN_DIR/preparation.json"
```

`prepare` exact-opens all four authorities, validates the 54 source/target slate alignment, validates the passing fixed fit and terminal build, then create-once publishes `task-manifest.json`. Stop unless:

```bash
jq -e '.task_count == 54 and .real_artifact_smoke_required_before_fanout == true and .fanout_launched == false' \
  "$RUN_DIR/preparation.json"
```

## 2. Configure, launch, and collect task 0

Configuration changes the existing UID-pinned job to one task and binds the scope environment to `task0`:

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" configure \
  --preparation-file "$RUN_DIR/preparation.json" \
  --scope task0 \
  --output-file "$RUN_DIR/task0-configure.json"

env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" launch \
  --preparation-file "$RUN_DIR/preparation.json" \
  --scope task0 \
  --output-file "$RUN_DIR/task0-launch.json"
```

Poll with a new create-once filename on every call; never reuse a prior status path:

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" status \
  --launch-file "$RUN_DIR/task0-launch.json" \
  --output-file "$RUN_DIR/task0-status-001.json"
jq '{execution_name,terminal_state,succeeded_count,failed_count,cancelled_count}' \
  "$RUN_DIR/task0-status-001.json"
```

Repeat as `task0-status-002.json`, and so on, until `terminal_state` is `SUCCEEDED`. On `FAILED`, stop; do not automatically fan out or relaunch.

After success, exact-open and validate the known task-0 result and all ten world artifacts/receipts:

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" collect \
  --preparation-file "$RUN_DIR/preparation.json" \
  --launch-file "$RUN_DIR/task0-launch.json" \
  --output-file "$RUN_DIR/task0-collection.json"

jq -e '.scope == "task0" and .task_result_count == 1 and .real_artifact_smoke_complete == true and .panel_finalization_ready == false' \
  "$RUN_DIR/task0-collection.json"
```

This collection is the fan-out gate. Cloud Run success alone is insufficient.

## 3. Configure, launch, and collect all 54 slates

The full execution deliberately includes task index 0 again. Its deterministic create-once outputs must exactly equal the smoke outputs; unequal collisions fail closed.

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" configure \
  --preparation-file "$RUN_DIR/preparation.json" \
  --scope full54 \
  --output-file "$RUN_DIR/full54-configure.json"

env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" launch \
  --preparation-file "$RUN_DIR/preparation.json" \
  --scope full54 \
  --output-file "$RUN_DIR/full54-launch.json"
```

Poll using fresh names:

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" status \
  --launch-file "$RUN_DIR/full54-launch.json" \
  --output-file "$RUN_DIR/full54-status-001.json"
jq '{execution_name,terminal_state,succeeded_count,failed_count,cancelled_count}' \
  "$RUN_DIR/full54-status-001.json"
```

Repeat with increasing suffixes until exactly 54 succeeded and zero failed/cancelled. Then collect all known-name results and atomically materialize the finalization request:

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" collect \
  --preparation-file "$RUN_DIR/preparation.json" \
  --launch-file "$RUN_DIR/full54-launch.json" \
  --output-file "$RUN_DIR/full54-collection.json" \
  --finalization-request-file "$RUN_DIR/finalization-request.json"

jq -e '.scope == "full54" and .task_result_count == 54 and .panel_finalization_ready == true and .bucket_listing_performed == false' \
  "$RUN_DIR/full54-collection.json"
jq -e '.task_result_identities | length == 54' \
  "$RUN_DIR/finalization-request.json"
```

## 4. Finalize the immutable panel root

```bash
env PYTHONPATH="$REPO/src" "$PYTHON" "$CLI" finalize \
  --request-file "$RUN_DIR/finalization-request.json" \
  --output-file "$RUN_DIR/panel-finalization.json"

jq -e '.complete == true and .task_count == 54 and .cell_count == 540' \
  "$RUN_DIR/panel-finalization.json"
jq '.panel_root_identity' "$RUN_DIR/panel-finalization.json"
```

Finalization exact-opens all 54 task results and 540 world receipts and publishes `${OUTPUT_PREFIX}panel-root.json` last. That identity is the only L2b panel authority to pass to the downstream selector/evaluator chain.

## What this run does and does not produce

The finalized root contains two prespecified challenger mechanisms for every R0--R4 block on every slate:

- `l2b-quarter-world-mixture`: fixed 25% L2b world-column replacement;
- `l2b-native`: 100% calibrated L2b target law.

The incumbent zero-fraction control is referenced from the frozen later source and is not recopied. The run produces selector-ready `ScoringWorldBlockV1` artifacts through `load_l2b_world_artifact_v1`; it does **not** itself select lineups or produce historical realized scores. A separate downstream launch must cross-score the accepted candidate union with these banks, run the frozen selectors/budgets, and then use the terminal-only realized grader.

## Stop conditions

Stop without fan-out or finalization if any of the following occurs:

- final worktree/commit/image/build receipt do not bind one another;
- regenerated release `code_sha` differs from `CODE_SHA` or its gate does not pass;
- the W3 job UID differs or any execution is active at configure/launch time;
- task0 is terminal-failed, or task0 collection cannot exact-open all ten artifacts;
- any full54 task fails/cancels, fewer than 54 validated results collect, or a create-once collision has unequal bytes;
- any command would reuse a local output file or remote output prefix for different bytes.
