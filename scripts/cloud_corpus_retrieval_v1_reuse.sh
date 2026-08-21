#!/usr/bin/env bash
# Reuse-only configure/launch/recover/watch transport for corpus retrieval v1.
# This file never creates a job, scheduler, service account, bucket, or IAM
# binding. The dedicated runtime principal and UBLA bucket are operator inputs.
set -euo pipefail

PROJECT="nfl-predictions-503414"
REGION="us-central1"
JOB="atlas-minimal-c-s2023-w1-v1"
ENABLE_ENV="CORPUS_RETRIEVAL_RESEARCH_ENABLED"
TRANSPORT="scripts/run_corpus_retrieval_transport.py"
PYTHON="${CORPUS_RETRIEVAL_PYTHON:-.venv/bin/python}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
usage: cloud_corpus_retrieval_v1_reuse.sh --execute MODE

MODE is one of:
  configure  update the existing audited job to the generic parked spec,
             validate it, and publish create-once governance
  launch     consume create-once launch authority, then invoke exactly once
  recover    bind the sole new execution by census; never invokes a job
  watch      poll only the bound execution and run the strict finisher

Required environment for every mode:
  CORPUS_RETRIEVAL_RESEARCH_ENABLED=1
  CORPUS_RETRIEVAL_RUN_DIR=/durable/local/run-directory

configure additionally requires SUITE_FILE, SNAPSHOT_FILE, their URI,
generation, SHA256 and byte variables, OUTPUT_PREFIX, BUILD_ID, CODE_SHA,
IMAGE, SERVICE_ACCOUNT, and RUNTIME_IAM_EVIDENCE_FILE. All variable names use
the CORPUS_RETRIEVAL_ prefix. No unstable live UID/generation/spec is accepted
as input: configure captures it immediately before the sole update.
EOF
}

[[ $# -eq 2 && "$1" == "--execute" ]] || {
  usage >&2
  exit 2
}
MODE="$2"
case "$MODE" in
  configure|launch|recover|watch) ;;
  *) usage >&2; exit 2 ;;
esac

# This gate deliberately precedes mkdir and every gcloud/GCS client call.
[[ "${CORPUS_RETRIEVAL_RESEARCH_ENABLED:-}" == "1" ]] || die "$ENABLE_ENV=1 is required"
RUN_DIR="${CORPUS_RETRIEVAL_RUN_DIR:?CORPUS_RETRIEVAL_RUN_DIR is required}"
[[ "$RUN_DIR" == /* && "$RUN_DIR" != "/" ]] || die "RUN_DIR must be an absolute narrow path"
mkdir -p "$RUN_DIR"

timestamp_once() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    date -u +%Y-%m-%dT%H:%M:%SZ >"$path"
  fi
  [[ -f "$path" && ! -L "$path" ]] || die "timestamp receipt is unsafe: $path"
  tr -d '\n' <"$path"
}

capture_json() {
  local output="$1"
  shift
  local raw="${output}.raw.pending"
  local canonical="${output}.pending"
  [[ ! -e "$raw" && ! -e "$canonical" ]] || die "pending capture already exists: $output"
  "$@" >"$raw"
  "$PYTHON" "$TRANSPORT" canonicalize-external-json \
    --raw "$raw" --output "$canonical"
  mv "$canonical" "$output"
  rm -f "$raw"
}

refresh_json() {
  local output="$1"
  shift
  local next="${output}.next"
  [[ ! -e "$next" && ! -e "${next}.raw.pending" ]] || die "stale refresh file: $next"
  capture_json "$next" "$@"
  mv "$next" "$output"
}

identity_args_from_governance() {
  local receipt="$1"
  "$PYTHON" - "$receipt" <<'PY'
import json
import pathlib
import sys

value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
identity = value["execution_contract"]
for key in ("uri", "generation", "sha256", "bytes"):
    print(identity[key])
PY
}

bound_execution_name() {
  "$PYTHON" - "$RUN_DIR/execution-bound.json" <<'PY'
import json
import pathlib
import sys

value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value["execution_name"])
PY
}

new_execution_id() {
  "$PYTHON" - "$RUN_DIR/execution-contract.json" "$RUN_DIR/executions-current.json" <<'PY'
import json
import pathlib
import sys

contract = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
before = set(contract["execution_names_before"])
after = {
    row["metadata"]["name"].rsplit("/", 1)[-1]
    for row in rows
}
new = sorted(after - before)
if before - after or len(new) != 1:
    raise SystemExit("launch outcome ambiguous; never relaunch; repeat recover")
print(new[0])
PY
}

terminal_state() {
  "$PYTHON" - "$1" <<'PY'
import json
import pathlib
import sys

value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = [
    row for row in value.get("status", {}).get("conditions", [])
    if row.get("type") == "Completed"
]
print(rows[0].get("status", "Unknown") if len(rows) == 1 else "Unknown")
PY
}

load_contract_identity() {
  mapfile -t CONTRACT_IDENTITY < <(
    identity_args_from_governance "$RUN_DIR/governance.json"
  )
  [[ ${#CONTRACT_IDENTITY[@]} -eq 4 ]] || die "contract identity receipt differs"
  CONTRACT_ARGS=(
    --execution-contract-uri "${CONTRACT_IDENTITY[0]}"
    --execution-contract-generation "${CONTRACT_IDENTITY[1]}"
    --execution-contract-sha256 "${CONTRACT_IDENTITY[2]}"
    --execution-contract-bytes "${CONTRACT_IDENTITY[3]}"
  )
}

capture_live_census() {
  refresh_json "$RUN_DIR/job-current.json" \
    gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" --format=json
  refresh_json "$RUN_DIR/executions-current.json" \
    gcloud run jobs executions list --job="$JOB" --project="$PROJECT" --region="$REGION" --format=json
  refresh_json "$RUN_DIR/schedulers-current.json" \
    gcloud scheduler jobs list --project="$PROJECT" --location="$REGION" --format=json
}

configure_parked() {
  local suite_file="${CORPUS_RETRIEVAL_SUITE_FILE:?suite file required}"
  local snapshot_file="${CORPUS_RETRIEVAL_SNAPSHOT_FILE:?snapshot file required}"
  local candidate_file="${CORPUS_RETRIEVAL_CANDIDATE_ROWS_FILE:?candidate rows file required}"
  local player_file="${CORPUS_RETRIEVAL_PLAYER_CATALOG_FILE:?player catalog file required}"
  local iam_file="${CORPUS_RETRIEVAL_RUNTIME_IAM_EVIDENCE_FILE:?IAM evidence required}"
  local output_prefix="${CORPUS_RETRIEVAL_OUTPUT_PREFIX:?output prefix required}"
  local build_id="${CORPUS_RETRIEVAL_BUILD_ID:?build ID required}"
  local code_sha="${CORPUS_RETRIEVAL_CODE_SHA:?code SHA required}"
  local image="${CORPUS_RETRIEVAL_IMAGE:?image digest URI required}"
  local service_account="${CORPUS_RETRIEVAL_SERVICE_ACCOUNT:?runtime SA required}"
  local updated=0
  local accepted=0

  [[ -f "$suite_file" && ! -L "$suite_file" ]] || die "suite file is unsafe"
  [[ -f "$snapshot_file" && ! -L "$snapshot_file" ]] || die "snapshot file is unsafe"
  [[ -f "$candidate_file" && ! -L "$candidate_file" ]] || die "candidate rows file is unsafe"
  [[ -f "$player_file" && ! -L "$player_file" ]] || die "player catalog file is unsafe"
  [[ -f "$iam_file" && ! -L "$iam_file" ]] || die "IAM evidence file is unsafe"
  [[ ! -e "$RUN_DIR/governance.json" ]] || die "governance is already accepted"

  capture_json "$RUN_DIR/job-before.json" \
    gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" --format=json
  [[ ! -e "$RUN_DIR/job-before-export.yaml" ]] || die "prior export already exists"
  gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" \
    --format=export >"$RUN_DIR/job-before-export.yaml"
  capture_json "$RUN_DIR/executions-before.json" \
    gcloud run jobs executions list --job="$JOB" --project="$PROJECT" --region="$REGION" --format=json
  capture_json "$RUN_DIR/schedulers-before.json" \
    gcloud scheduler jobs list --project="$PROJECT" --location="$REGION" --format=json
  capture_json "$RUN_DIR/build.json" \
    gcloud builds describe "$build_id" --project="$PROJECT" --format=json

  "$PYTHON" "$TRANSPORT" validate-build \
    --metadata "$RUN_DIR/build.json" --build-id "$build_id" \
    --code-repository "https://github.com/espechtsoftware/nfl-predictions.git" \
    --code-sha "$code_sha" --image "$image" \
    --output "$RUN_DIR/build-validated.json"
  "$PYTHON" "$TRANSPORT" inventory --prefix "$output_prefix" \
    --output "$RUN_DIR/inventory-before.json" --execute

  local preflight_at
  preflight_at="$(timestamp_once "$RUN_DIR/preflight-at.txt")"
  "$PYTHON" "$TRANSPORT" create-preflight \
    --suite "$suite_file" \
    --suite-uri "${CORPUS_RETRIEVAL_SUITE_URI:?suite URI required}" \
    --suite-generation "${CORPUS_RETRIEVAL_SUITE_GENERATION:?suite generation required}" \
    --suite-sha256 "${CORPUS_RETRIEVAL_SUITE_SHA256:?suite SHA required}" \
    --suite-bytes "${CORPUS_RETRIEVAL_SUITE_BYTES:?suite bytes required}" \
    --snapshot "$snapshot_file" \
    --snapshot-uri "${CORPUS_RETRIEVAL_SNAPSHOT_URI:?snapshot URI required}" \
    --snapshot-generation "${CORPUS_RETRIEVAL_SNAPSHOT_GENERATION:?snapshot generation required}" \
    --snapshot-sha256 "${CORPUS_RETRIEVAL_SNAPSHOT_SHA256:?snapshot SHA required}" \
    --snapshot-bytes "${CORPUS_RETRIEVAL_SNAPSHOT_BYTES:?snapshot bytes required}" \
    --candidate-rows "$candidate_file" --player-catalog "$player_file" \
    --task-index 0 --build-metadata "$RUN_DIR/build.json" \
    --build-id "$build_id" --code-sha "$code_sha" --image "$image" \
    --service-account "$service_account" --runtime-iam-evidence "$iam_file" \
    --job-before "$RUN_DIR/job-before.json" \
    --job-before-export "$RUN_DIR/job-before-export.yaml" \
    --executions "$RUN_DIR/executions-before.json" \
    --schedulers "$RUN_DIR/schedulers-before.json" \
    --inventory "$RUN_DIR/inventory-before.json" \
    --created-at-utc "$preflight_at" --output "$RUN_DIR/preflight.json"

  rollback_unaccepted() {
    local status=$?
    trap - EXIT
    if [[ $status -ne 0 && $updated -eq 1 && $accepted -eq 0 ]]; then
      capture_json "$RUN_DIR/job-before-rollback.json" \
        gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" --format=json
      "$PYTHON" - "$RUN_DIR/job-before.json" "$RUN_DIR/job-before-rollback.json" <<'PY'
import json
import pathlib
import sys

before = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
current = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
for key in ("name", "uid"):
    if before["metadata"][key] != current["metadata"][key]:
        raise SystemExit("refusing rollback: reused job identity changed")
PY
      gcloud run jobs replace "$RUN_DIR/job-before-export.yaml" \
        --project="$PROJECT" --region="$REGION" --quiet
      capture_json "$RUN_DIR/job-rolled-back.json" \
        gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" --format=json
      "$PYTHON" "$TRANSPORT" validate-preacceptance-rollback \
        --before "$RUN_DIR/job-before.json" \
        --rolled-back "$RUN_DIR/job-rolled-back.json" \
        --output "$RUN_DIR/rollback-validated.json"
    fi
    exit "$status"
  }
  trap rollback_unaccepted EXIT

  updated=1
  gcloud run jobs update "$JOB" --project="$PROJECT" --region="$REGION" \
    --image="$image" --command=python \
    --args="$TRANSPORT,parked" --tasks=1 --parallelism=1 --max-retries=0 \
    --cpu=4 --memory=16Gi --task-timeout=21600s \
    --service-account="$service_account" --clear-secrets --clear-volumes \
    --clear-volume-mounts \
    --set-env-vars="$ENABLE_ENV=1,CORPUS_RETRIEVAL_IMAGE=$image,CORPUS_RETRIEVAL_BUILD_ID=$build_id,CODE_SHA=$code_sha" \
    --quiet

  capture_live_census
  "$PYTHON" "$TRANSPORT" validate-reuse \
    --job "$RUN_DIR/job-current.json" \
    --executions "$RUN_DIR/executions-current.json" \
    --schedulers "$RUN_DIR/schedulers-current.json" \
    --output "$RUN_DIR/post-update-census.json"
  local contract_at
  contract_at="$(timestamp_once "$RUN_DIR/contract-at.txt")"
  "$PYTHON" "$TRANSPORT" create-execution-contract \
    --preflight "$RUN_DIR/preflight.json" \
    --updated-job "$RUN_DIR/job-current.json" \
    --created-at-utc "$contract_at" --output "$RUN_DIR/execution-contract.json"
  local governance_at
  governance_at="$(timestamp_once "$RUN_DIR/governance-at.txt")"
  "$PYTHON" "$TRANSPORT" publish-governance \
    --preflight "$RUN_DIR/preflight.json" \
    --execution-contract "$RUN_DIR/execution-contract.json" \
    --runtime-iam-evidence "$iam_file" \
    --published-at-utc "$governance_at" \
    --output "$RUN_DIR/governance.json" --execute
  accepted=1
  trap - EXIT
  echo "generic parked deployment accepted; prior A7 export is rollback-only and will not be restored"
}

consume_and_launch() {
  [[ -f "$RUN_DIR/governance.json" ]] || die "accepted governance receipt is absent"
  [[ ! -e "$RUN_DIR/launch-ready.json" ]] || die "launch already consumed; run recover, never launch"
  load_contract_identity
  capture_live_census
  local launch_at
  launch_at="$(timestamp_once "$RUN_DIR/launch-at.txt")"
  "$PYTHON" "$TRANSPORT" consume-launch "${CONTRACT_ARGS[@]}" \
    --job "$RUN_DIR/job-current.json" \
    --executions "$RUN_DIR/executions-current.json" \
    --schedulers "$RUN_DIR/schedulers-current.json" \
    --created-at-utc "$launch_at" --output "$RUN_DIR/launch-ready.json" \
    --execute
  local permitted
  permitted="$($PYTHON - "$RUN_DIR/launch-ready.json" <<'PY'
import json
import pathlib
import sys
print("true" if json.loads(pathlib.Path(sys.argv[1]).read_text())["launch_permitted"] else "false")
PY
)"
  [[ "$permitted" == "true" ]] || die "launch authority was already/ambiguously consumed; census only"
  local worker_args
  worker_args="$($PYTHON "$TRANSPORT" worker-args \
    --execution-contract "$RUN_DIR/execution-contract.json" \
    "${CONTRACT_ARGS[@]}" --format csv)"
  # No command in this file can return here twice: launch-ready.json is local
  # durable evidence and the create-once cloud ledger is authoritative.
  if ! gcloud run jobs execute "$JOB" --project="$PROJECT" --region="$REGION" \
    --tasks=1 --task-timeout=21600s --args="$worker_args" --async \
    --format=json >"$RUN_DIR/execute-response.raw.json"; then
    echo "execute response was ambiguous; recovering only by census" >&2
  fi
  local visible=0 ignored_execution_id
  for _attempt in $(seq 1 60); do
    capture_live_census
    if ignored_execution_id="$(new_execution_id 2>/dev/null)"; then
      visible=1
      break
    fi
    sleep 5
  done
  [[ $visible -eq 1 ]] || die "no sole execution became visible; never relaunch"
  recover_name
}

recover_name() {
  [[ -f "$RUN_DIR/governance.json" ]] || die "accepted governance receipt is absent"
  [[ -f "$RUN_DIR/launch-ready.json" ]] || die "launch ledger receipt is absent"
  if [[ -e "$RUN_DIR/execution-bound.json" ]]; then
    echo "execution is already bound; never relaunch"
    return 0
  fi
  load_contract_identity
  capture_live_census
  local execution_id
  execution_id="$(new_execution_id)"
  capture_json "$RUN_DIR/execution-metadata.json" \
    gcloud run jobs executions describe "$execution_id" \
      --project="$PROJECT" --region="$REGION" --format=json
  local bound_at
  bound_at="$(timestamp_once "$RUN_DIR/execution-bound-at.txt")"
  "$PYTHON" "$TRANSPORT" bind-execution-name "${CONTRACT_ARGS[@]}" \
    --execution-metadata "$RUN_DIR/execution-metadata.json" \
    --job "$RUN_DIR/job-current.json" \
    --executions "$RUN_DIR/executions-current.json" \
    --schedulers "$RUN_DIR/schedulers-current.json" \
    --created-at-utc "$bound_at" --output "$RUN_DIR/execution-bound.json" \
    --execute
  echo "sole new execution bound: $(bound_execution_name)"
}

watch_bound() {
  [[ -f "$RUN_DIR/execution-bound.json" ]] || die "run recover first"
  load_contract_identity
  local execution_name state
  execution_name="$(bound_execution_name)"
  while true; do
    refresh_json "$RUN_DIR/terminal-metadata.json" \
      gcloud run jobs executions describe "$execution_name" \
        --project="$PROJECT" --region="$REGION" --format=json
    state="$(terminal_state "$RUN_DIR/terminal-metadata.json")"
    case "$state" in
      True) break ;;
      False) die "bound execution failed; retry/relaunch is forbidden" ;;
      Unknown) sleep 30 ;;
      *) die "execution terminal state differs" ;;
    esac
  done
  refresh_json "$RUN_DIR/job-post-terminal.json" \
    gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" --format=json
  refresh_json "$RUN_DIR/executions-post-terminal.json" \
    gcloud run jobs executions list --job="$JOB" --project="$PROJECT" --region="$REGION" --format=json
  refresh_json "$RUN_DIR/schedulers-post-terminal.json" \
    gcloud scheduler jobs list --project="$PROJECT" --location="$REGION" --format=json
  local finished_at
  finished_at="$(timestamp_once "$RUN_DIR/finished-at.txt")"
  "$PYTHON" "$TRANSPORT" finish-task "${CONTRACT_ARGS[@]}" \
    --execution "$execution_name" \
    --terminal-metadata "$RUN_DIR/terminal-metadata.json" \
    --deployed-job "$RUN_DIR/job-current.json" \
    --post-terminal-job "$RUN_DIR/job-post-terminal.json" \
    --executions-after "$RUN_DIR/executions-post-terminal.json" \
    --schedulers-after "$RUN_DIR/schedulers-post-terminal.json" \
    --finished-at-utc "$finished_at" --output "$RUN_DIR/finish.json" \
    --execute
  echo "strict terminal receipt published; generic job remains permanently parked"
}

case "$MODE" in
  configure) configure_parked ;;
  launch) consume_and_launch ;;
  recover) recover_name ;;
  watch) watch_bound ;;
esac
