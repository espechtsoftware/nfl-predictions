#!/usr/bin/env bash
set -euo pipefail

# Reuse-only two-phase transport for the one frozen A7 historical look.
#
# prepare validates every outcome-blind prerequisite and updates an existing
# research job without acquiring the historical-outcome lease.  launch requires
# the immutable prepared receipt plus a byte-verified lease before starting the
# single execution.
#
# Usage:
#   cloud_a7_select_ladder.sh build-command IMAGE_TAG CODE_SHA
#   cloud_a7_select_ladder.sh preflight-prepare IMAGE CODE_SHA BUILD_ID
#   cloud_a7_select_ladder.sh smoke
#   cloud_a7_select_ladder.sh support
#   cloud_a7_select_ladder.sh freeze
#   cloud_a7_select_ladder.sh prepare IMAGE CODE_SHA BUILD_ID FREEZE_URI FREEZE_GENERATION FREEZE_SHA256
#   cloud_a7_select_ladder.sh launch

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260820-a7-select-ladder-phase-s-incumbent-v2
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/a7-select-ladder-runs/$RUN_ID"
PENDING="$ROOT/reports/a7-select-ladder-runs/.$RUN_ID.prepare.pending"
PREFIX="gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/$RUN_ID"
RESULT_URI="$PREFIX/result.json"
SMOKE_URI="$PREFIX/preflight/real-artifact-smoke.json"
SUPPORT_URI="$PREFIX/preflight/support-census.json"
SMOKE_TERMINAL_URI="$PREFIX/preflight/real-artifact-smoke-terminal.json"
SUPPORT_TERMINAL_URI="$PREFIX/preflight/support-census-terminal.json"
JOB_CLAIM_URI="$PREFIX/preflight/job-claim.json"
FREEZE_URI_EXPECTED="$PREFIX/preflight/freeze-manifest.json"
LEASE_URI=gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json
PREFLIGHT_OUT="$ROOT/reports/a7-select-ladder-preflight-runs/$RUN_ID"
A3_RELEASE="$ROOT/reports/stack-relaxation-carve-runs/20260819-stack-relaxation-carve-v1/logical-release.json"
V1_FAILURE_RELEASE="$ROOT/reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/failed-preflight-logical-release.json"
V1_FAILURE_RELEASE_OBJECT="$ROOT/reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/failed-preflight-logical-release-object.json"
FINISHER="$ROOT/scripts/finish_a7_select_ladder.py"
LEASE_TOOL="$ROOT/scripts/historical_outcome_lease.py"
FREEZE_BUILDER="$ROOT/scripts/freeze_a7_select_ladder.py"
PYTHON="$ROOT/.venv/bin/python"
COMMAND=${1:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

for repair_name in A7_FINISHER_REPAIR_SHA256 A7_LAUNCHER_REPAIR_SHA256 \
  A7_WATCHER_REPAIR_SHA256; do
  repair_value=${!repair_name:-}
  [ -z "$repair_value" ] || [[ "$repair_value" =~ ^[0-9a-f]{64}$ ]] || \
    die "$repair_name differs"
done

capture_gcloud_json() {
  local target=$1
  shift
  local raw="$target.gcloud.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$raw" ] || \
    die "A7 external JSON capture path already exists: $target"
  if ! "$@" > "$raw"; then
    die "A7 external JSON command failed; raw response retained: $raw"
  fi
  if ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$raw" --output "$target"; then
    die "A7 external JSON canonicalization failed; raw response retained: $raw"
  fi
  rm -- "$raw"
}

canonical_job_is_idle() {
  local target=$1
  local ledger=$2
  capture_gcloud_json "$ledger" gcloud run jobs executions list \
    --job "$target" --project "$PROJECT" --region "$REGION" --format=json
  "$PYTHON" - "$ledger" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if not isinstance(rows, list):
    raise SystemExit("ERROR: A7 reused-job execution census differs")
for row in rows:
    completed = [
        value for value in row.get("status", {}).get("conditions", [])
        if value.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"}:
        raise SystemExit("ERROR: A7 reused job is not idle")
PY
}

validate_prefix_inventory() {
  local phase=$1
  local inventory=$2
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - "$PREFIX/preflight/" \
    "$inventory" <<'PY'
from pathlib import Path
import sys

from finish_a7_select_ladder import _StorageReader

values = _StorageReader().inventory(sys.argv[1])
Path(sys.argv[2]).write_text("".join(f"{uri}\n" for uri in sorted(values)))
PY
  "$PYTHON" - "$inventory" "$phase" "$JOB_CLAIM_URI" "$SMOKE_URI" \
    "$SMOKE_TERMINAL_URI" "$SUPPORT_URI" "$SUPPORT_TERMINAL_URI" \
    "$FREEZE_URI_EXPECTED" <<'PY'
import sys

path, phase, claim, smoke, smoke_terminal, support, support_terminal, freeze = sys.argv[1:]
rows = [line.strip() for line in open(path, encoding="utf-8") if line.strip()]
phases = {
    "empty": set(),
    "claimed": {claim},
    "smoke-complete": {claim, smoke, smoke_terminal},
    "support-complete": {claim, smoke, smoke_terminal, support, support_terminal},
    "frozen": {claim, smoke, smoke_terminal, support, support_terminal, freeze},
}

if phase not in phases:
    raise SystemExit("ERROR: A7 inventory phase differs")
expected = phases[phase]
if len(rows) != len(set(rows)) or set(rows) != expected:
    raise SystemExit(
        f"ERROR: A7 immutable {phase} prefix differs: "
        f"missing={sorted(expected-set(rows))} extra={sorted(set(rows)-expected)}"
    )
PY
}

strict_object_absent() {
  local uri=$1
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - "$uri" <<'PY'
import sys

from google.api_core.exceptions import NotFound
from google.cloud import storage
from finish_a7_select_ladder import PROJECT, _gcs_parts

uri = sys.argv[1]
bucket, name = _gcs_parts(uri)
blob = storage.Client(project=PROJECT).bucket(bucket).blob(name)
try:
    blob.reload()
except NotFound:
    raise SystemExit(0)
raise SystemExit(f"ERROR: immutable A7 object already exists: {uri}")
PY
}

validate_job_chain_before() {
  local phase=$1
  local before=$2
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - \
    "$phase" "$before" "$PREFLIGHT_OUT" <<'PY'
import json
from pathlib import Path
import sys

from finish_a7_select_ladder import (
    _validate_preflight_complete, _validate_prior_job_state,
)

phase, before_path, base = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
claim = json.loads((base / "job-claim-receipt.json").read_text(encoding="utf-8"))
if phase == "smoke":
    prior = claim["claim"]
elif phase in {"support", "historical"}:
    prior_name = "smoke" if phase == "support" else "support"
    prior_mode = "real-artifact-smoke" if phase == "support" else "support-census"
    prior_out = base / prior_name
    _validate_preflight_complete(prior_out, mode=prior_mode)
    terminal = json.loads(
        (prior_out / "terminal-receipt.json").read_text(encoding="utf-8")
    )
    prior = terminal["execution"]
else:
    raise SystemExit("ERROR: A7 job-chain phase differs")
_validate_prior_job_state(
    json.loads(before_path.read_text(encoding="utf-8")),
    job_uid=claim["claim"]["job_uid"],
    job_generation=str(prior["job_generation"]),
    job_spec_sha256=str(prior["job_spec_sha256"]),
)
PY
}

validate_preflight_base() {
  [ -d "$PREFLIGHT_OUT" ] || die "A7 preflight preparation is absent"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - "$PREFLIGHT_OUT" <<'PY'
from pathlib import Path
import sys

from finish_a7_select_ladder import _validate_hash_ledger

out = Path(sys.argv[1])
_validate_hash_ledger(
    out / "prepared.sha256", base=out,
    expected={
        "build-metadata.json", "a3-logical-release.json",
        "job-at-claim.json", "job-claim-receipt.json",
    },
)
PY
}

prepare_preflight_run() {
  local short_mode=$1
  local mode flag target prior_phase mode_out
  if [ "$short_mode" = smoke ]; then
    mode=real-artifact-smoke
    flag=--smoke
    target=$SMOKE_URI
    prior_phase=claimed
  elif [ "$short_mode" = support ]; then
    mode=support-census
    flag=--support-census
    target=$SUPPORT_URI
    prior_phase=smoke-complete
    [ -s "$PREFLIGHT_OUT/smoke/completion.txt" ] || \
      die "strict smoke completion is absent"
  else
    die "A7 preflight mode differs"
  fi
  mode_out="$PREFLIGHT_OUT/$short_mode"
  [ ! -e "$mode_out" ] || die "immutable A7 $short_mode run exists"
  validate_preflight_base
  validate_prefix_inventory "$prior_phase" "$PREFLIGHT_OUT/.$short_mode.inventory-before"
  mkdir "$mode_out"
  cp --no-clobber "$PREFLIGHT_OUT/build-metadata.json" \
    "$mode_out/build-metadata.json"
  cp --no-clobber "$PREFLIGHT_OUT/a3-logical-release.json" \
    "$mode_out/a3-logical-release.json"
  cp --no-clobber "$PREFLIGHT_OUT/job-claim-receipt.json" \
    "$mode_out/job-claim-receipt.json"
  capture_gcloud_json "$mode_out/job-before.json" gcloud run jobs describe \
    "$JOB" --project "$PROJECT" --region "$REGION" --format=json
  canonical_job_is_idle "$JOB" "$mode_out/.job-executions-before.json"
  validate_job_chain_before "$short_mode" "$mode_out/job-before.json"
  IMAGE=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["claim"]["image"])' \
    "$PREFLIGHT_OUT/job-claim-receipt.json")
  CODE_SHA=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["claim"]["code_sha"])' \
    "$PREFLIGHT_OUT/job-claim-receipt.json")
  BUILD_ID=$("$PYTHON" -c 'import json,sys; v=json.load(open(sys.argv[1])); print(v.get("id") or v.get("metadata",{}).get("build",{}).get("id"))' \
    "$PREFLIGHT_OUT/build-metadata.json")
  # --set-env-vars replaces the complete environment; it is not an update.
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
      --max-retries 0 --task-timeout 2h \
      --clear-volumes --clear-volume-mounts --workdir="" --startup-probe="" \
    --clear-secrets \
    --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
    --command python \
    --args "scripts/run_a7_select_ladder.py,$flag,--preflight-receipt-uri,$target" \
    --quiet >/dev/null
  capture_gcloud_json "$mode_out/job-after.json" gcloud run jobs describe \
    "$JOB" --project "$PROJECT" --region "$REGION" --format=json
  canonical_job_is_idle "$JOB" "$mode_out/.job-executions-after.json"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - \
    "$mode_out" "$mode" "$CODE_SHA" "$IMAGE" "$BUILD_ID" "$target" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

from finish_a7_select_ladder import (
    JOB, PROTOCOL_ID, RUN_ID, SERVICE_ACCOUNT, CPU, MEMORY, TIMEOUT_SECONDS,
    _canonical_json, _validate_job_claim_receipt, _validate_updated_job_spec,
)

out = Path(sys.argv[1])
mode, code, image, build, target = sys.argv[2:]
after = json.loads((out / "job-after.json").read_text())
meta = after.get("metadata", {})
uid, generation = str(meta.get("uid", "")), str(meta.get("generation", ""))
claim = json.loads((out / "job-claim-receipt.json").read_text())
protocol_sha = claim["claim"]["protocol_sha256"]
a3_sha = sha256((out / "a3-logical-release.json").read_bytes()).hexdigest()
_validate_job_claim_receipt(
    claim, code_sha=code, image=image, protocol_sha256=protocol_sha,
    a3_logical_release_sha256=a3_sha, job_uid=uid,
)
job_spec_sha = _validate_updated_job_spec(
    after, code_sha=code, image=image, mode=mode,
)
if mode == "real-artifact-smoke":
    prior = claim["claim"]
else:
    prior = json.loads(
        (out.parent / "smoke" / "terminal-receipt.json").read_text(
            encoding="utf-8"
        )
    )["execution"]
value = {
    "version": "a7-select-ladder-preflight-launch-manifest-v1",
    "run_id": RUN_ID, "protocol_id": PROTOCOL_ID, "mode": mode,
    "code_sha": code, "image": image, "build_id": build,
    "protocol_sha256": protocol_sha,
    "a3_logical_release_sha256": a3_sha,
    "job_claim": claim,
    "job_claim_receipt_sha256": sha256(
        (out / "job-claim-receipt.json").read_bytes()
    ).hexdigest(),
    "job": JOB, "job_uid": uid, "job_generation": generation,
    "job_spec_sha256": job_spec_sha,
    "prior_job_generation": str(prior["job_generation"]),
    "prior_job_spec_sha256": str(prior["job_spec_sha256"]),
    "service_account": SERVICE_ACCOUNT, "output_uri": target,
    "tasks": 1, "parallelism": 1, "cpu": CPU, "memory": MEMORY,
    "timeout_seconds": int(TIMEOUT_SECONDS), "max_retries": 0,
    "uses_realized_outcomes": False,
    "actual_score_query_executed": False,
    "production_change_licensed": False,
    "production_law_scorefree_transfer_licensed": False,
    "prospective_shadow_licensed": False,
    "job_update_mode": "reuse-only-update-existing",
}
(out / "manifest.json").write_bytes(_canonical_json(value))
PY
  (
    cd "$mode_out"
    sha256sum manifest.json build-metadata.json a3-logical-release.json \
      job-claim-receipt.json job-before.json job-after.json > prepared.sha256
  )
  rm "$mode_out/.job-executions-before.json" \
    "$mode_out/.job-executions-after.json" \
    "$PREFLIGHT_OUT/.$short_mode.inventory-before"
  EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [[ "$EXECUTION" == "$JOB-"* ]] || die "A7 $short_mode execution identity missing"
  printf '%s %s %s\n' "$JOB" "$EXECUTION" "$target" > "$mode_out/executions.txt"
  (
    cd "$mode_out"
    sha256sum manifest.json prepared.sha256 executions.txt > launch.sha256
  )
  while :; do
    capture_gcloud_json "$mode_out/.execution-poll.json" gcloud run jobs \
      executions describe "$EXECUTION" --project "$PROJECT" \
      --region "$REGION" --format=json
    STATE=$("$PYTHON" - "$mode_out/.execution-poll.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
rows = [row for row in value.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"]
if not rows:
    print("Unknown")
elif len(rows) == 1 and rows[0].get("status") in {"Unknown", "True", "False"}:
    print(rows[0]["status"])
else:
    print("Malformed")
PY
    )
    case "$STATE" in
      True) rm "$mode_out/.execution-poll.json"; break ;;
      False) die "A7 $short_mode preflight failed terminally" ;;
      Unknown|"") rm "$mode_out/.execution-poll.json"; sleep 60 ;;
      *) die "A7 $short_mode execution metadata malformed" ;;
    esac
  done
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    finish-preflight --mode "$short_mode" --output-dir "$mode_out"
}

case "$COMMAND" in
  build-command)
    IMAGE_TAG=${2:-}
    CODE_SHA=${3:-}
    [[ "$IMAGE_TAG" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:[A-Za-z0-9._-]+$ ]] || \
      die "A7 build image tag differs"
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || \
      die "full A7 source commit is required"
    printf 'gcloud builds submit %q --git-source-revision=%q --config=%q --substitutions=%q --project=%q --format=%q\n' \
      'https://github.com/espechtsoftware/nfl-predictions.git' \
      "$CODE_SHA" "$ROOT/cloudbuild.yaml" "_IMAGE=$IMAGE_TAG" "$PROJECT" \
      'value(id)'
    ;;

  preflight-prepare)
    IMAGE=${2:-}
    CODE_SHA=${3:-}
    BUILD_ID=${4:-}
    [[ "$IMAGE" =~ ^.+@sha256:[0-9a-f]{64}$ ]] || \
      die "immutable A7 image is required"
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || \
      die "full A7 source commit is required"
    [[ "$BUILD_ID" =~ ^[0-9A-Za-z-]{8,80}$ ]] || \
      die "A7 build ID differs"
    [ ! -e "$PREFLIGHT_OUT" ] || die "immutable A7 preflight already exists"
    [ -s "$A3_RELEASE" ] || die "A3 logical release is absent"
    [ -s "$V1_FAILURE_RELEASE" ] || \
      die "A7-v1 failed-preflight logical release is absent"
    [ -s "$V1_FAILURE_RELEASE_OBJECT" ] || \
      die "A7-v1 failed-preflight object receipt is absent"
    strict_object_absent "$LEASE_URI"
    mkdir -p "$(dirname "$PREFLIGHT_OUT")"
    mkdir "$PREFLIGHT_OUT"
    trap 'echo "ERROR: A7 preflight preparation stopped; immutable directory retained" >&2' ERR
    validate_prefix_inventory empty "$PREFLIGHT_OUT/.inventory-empty"
    capture_gcloud_json "$PREFLIGHT_OUT/build-metadata.json" gcloud builds \
      describe "$BUILD_ID" --project "$PROJECT" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - \
      "$PREFLIGHT_OUT/build-metadata.json" "$BUILD_ID" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
from finish_a7_select_ladder import _validate_build_metadata
_validate_build_metadata(
    json.load(open(sys.argv[1])), build_id=sys.argv[2], image=sys.argv[3],
    code_sha=sys.argv[4],
)
PY
    cp --no-clobber "$A3_RELEASE" "$PREFLIGHT_OUT/a3-logical-release.json"
    capture_gcloud_json "$PREFLIGHT_OUT/job-at-claim.json" gcloud run jobs \
      describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json
    canonical_job_is_idle "$JOB" "$PREFLIGHT_OUT/.job-executions-at-claim.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" claim-job \
      --code-sha "$CODE_SHA" --image "$IMAGE" \
      --job-metadata "$PREFLIGHT_OUT/job-at-claim.json" \
      --a3-logical-release "$PREFLIGHT_OUT/a3-logical-release.json" \
      --v1-failed-preflight-release "$V1_FAILURE_RELEASE" \
      --v1-failed-preflight-release-object "$V1_FAILURE_RELEASE_OBJECT" \
      --receipt "$PREFLIGHT_OUT/job-claim-receipt.json"
    validate_prefix_inventory claimed "$PREFLIGHT_OUT/.inventory-claimed"
    (
      cd "$PREFLIGHT_OUT"
      sha256sum build-metadata.json a3-logical-release.json job-at-claim.json \
        job-claim-receipt.json > prepared.sha256
    )
    rm "$PREFLIGHT_OUT/.inventory-empty" \
      "$PREFLIGHT_OUT/.inventory-claimed" \
      "$PREFLIGHT_OUT/.job-executions-at-claim.json"
    trap - ERR
    echo "A7_PREFLIGHT_JOB_CLAIMED $JOB_CLAIM_URI"
    ;;

  smoke)
    prepare_preflight_run smoke
    validate_prefix_inventory smoke-complete "$PREFLIGHT_OUT/.smoke.inventory-final"
    rm "$PREFLIGHT_OUT/.smoke.inventory-final"
    ;;

  support)
    prepare_preflight_run support
    validate_prefix_inventory support-complete "$PREFLIGHT_OUT/.support.inventory-final"
    rm "$PREFLIGHT_OUT/.support.inventory-final"
    DISPOSITION=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
      "$PREFLIGHT_OUT/support/terminal-receipt.json")
    if [ "$DISPOSITION" = invalid-unsupported ]; then
      echo "A7_SUPPORT_INVALID_UNSUPPORTED no_freeze=true no_historical_look=true"
    elif [ "$DISPOSITION" != support-passed ]; then
      die "A7 support terminal disposition differs"
    fi
    ;;

  freeze)
    validate_preflight_base
    [ -s "$PREFLIGHT_OUT/smoke/finish.sha256" ] && \
      [ -s "$PREFLIGHT_OUT/support/finish.sha256" ] || \
      die "strict smoke/support harvests are absent"
    [ ! -e "$PREFLIGHT_OUT/freeze-upload-receipt.json" ] || \
      die "immutable A7 freeze receipt exists"
    DISPOSITION=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
      "$PREFLIGHT_OUT/support/terminal-receipt.json")
    [ "$DISPOSITION" = support-passed ] || \
      die "unsupported A7 census forbids freeze"
    validate_prefix_inventory support-complete "$PREFLIGHT_OUT/.freeze.inventory-before"
    CODE_SHA=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["claim"]["code_sha"])' \
      "$PREFLIGHT_OUT/job-claim-receipt.json")
    ARCHIVE_SHA=$(git -C "$ROOT" archive --format=tar "$CODE_SHA" | sha256sum | awk '{print $1}')
    mapfile -t IDENTITIES < <("$PYTHON" - \
      "$PREFLIGHT_OUT/job-claim-receipt.json" \
      "$PREFLIGHT_OUT/smoke/object-metadata.json" \
      "$PREFLIGHT_OUT/smoke/terminal-object-metadata.json" \
      "$PREFLIGHT_OUT/support/object-metadata.json" \
      "$PREFLIGHT_OUT/support/terminal-object-metadata.json" <<'PY'
import json, sys
claim = json.load(open(sys.argv[1]))["object"]
values = [claim, *(json.load(open(path)) for path in sys.argv[2:])]
for value in values:
    print("\t".join(str(value[key]) for key in ("uri", "generation", "sha256", "bytes")))
PY
    )
    [ "${#IDENTITIES[@]}" -eq 5 ] || die "A7 preflight identity population differs"
    IFS=$'\t' read -r CLAIM_URI CLAIM_GEN CLAIM_SHA CLAIM_BYTES <<< "${IDENTITIES[0]}"
    IFS=$'\t' read -r SMOKE_OBJECT_URI SMOKE_GEN SMOKE_SHA SMOKE_BYTES <<< "${IDENTITIES[1]}"
    IFS=$'\t' read -r SMOKE_TERM_URI SMOKE_TERM_GEN SMOKE_TERM_SHA SMOKE_TERM_BYTES <<< "${IDENTITIES[2]}"
    IFS=$'\t' read -r SUPPORT_OBJECT_URI SUPPORT_GEN SUPPORT_SHA SUPPORT_BYTES <<< "${IDENTITIES[3]}"
    IFS=$'\t' read -r SUPPORT_TERM_URI SUPPORT_TERM_GEN SUPPORT_TERM_SHA SUPPORT_TERM_BYTES <<< "${IDENTITIES[4]}"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FREEZE_BUILDER" \
      --job-claim-uri "$CLAIM_URI" --job-claim-generation "$CLAIM_GEN" \
      --job-claim-sha256 "$CLAIM_SHA" --job-claim-bytes "$CLAIM_BYTES" \
      --smoke-uri "$SMOKE_OBJECT_URI" --smoke-generation "$SMOKE_GEN" \
      --smoke-sha256 "$SMOKE_SHA" --smoke-bytes "$SMOKE_BYTES" \
      --smoke-terminal-uri "$SMOKE_TERM_URI" \
      --smoke-terminal-generation "$SMOKE_TERM_GEN" \
      --smoke-terminal-sha256 "$SMOKE_TERM_SHA" \
      --smoke-terminal-bytes "$SMOKE_TERM_BYTES" \
      --support-uri "$SUPPORT_OBJECT_URI" --support-generation "$SUPPORT_GEN" \
      --support-sha256 "$SUPPORT_SHA" --support-bytes "$SUPPORT_BYTES" \
      --support-terminal-uri "$SUPPORT_TERM_URI" \
      --support-terminal-generation "$SUPPORT_TERM_GEN" \
      --support-terminal-sha256 "$SUPPORT_TERM_SHA" \
      --support-terminal-bytes "$SUPPORT_TERM_BYTES" \
      --a3-logical-release "$PREFLIGHT_OUT/a3-logical-release.json" \
      --output-uri "$FREEZE_URI_EXPECTED" --archive-sha256 "$ARCHIVE_SHA" \
      > "$PREFLIGHT_OUT/freeze-upload-receipt.json"
    validate_prefix_inventory frozen "$PREFLIGHT_OUT/.freeze.inventory-final"
    rm "$PREFLIGHT_OUT/.freeze.inventory-before" \
      "$PREFLIGHT_OUT/.freeze.inventory-final"
    echo "A7_FREEZE_CREATED $FREEZE_URI_EXPECTED"
    ;;

  prepare)
    IMAGE=${2:-}
    CODE_SHA=${3:-}
    BUILD_ID=${4:-}
    FREEZE_URI=${5:-}
    FREEZE_GENERATION=${6:-}
    FREEZE_SHA256=${7:-}
    [[ "$IMAGE" =~ ^.+@sha256:[0-9a-f]{64}$ ]] || \
      die "immutable A7 image is required"
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || \
      die "full A7 source commit is required"
    [[ "$BUILD_ID" =~ ^[0-9A-Za-z-]{8,80}$ ]] || \
      die "A7 build ID differs"
    [ "$FREEZE_URI" = "$FREEZE_URI_EXPECTED" ] || \
      die "A7 freeze-manifest URI differs"
    [[ "$FREEZE_GENERATION" =~ ^[1-9][0-9]*$ ]] || \
      die "A7 freeze-manifest generation differs"
    [[ "$FREEZE_SHA256" =~ ^[0-9a-f]{64}$ ]] || \
      die "A7 freeze-manifest SHA differs"
    [ ! -e "$OUT" ] && [ ! -e "$PENDING" ] || \
      die "immutable A7 local run already exists"
    [ -s "$A3_RELEASE" ] || die "A3 logical release is absent"
    validate_preflight_base
    strict_object_absent "$RESULT_URI"
    strict_object_absent "$LEASE_URI"

    mkdir -p "$(dirname "$PENDING")"
    mkdir "$PENDING"
    trap 'echo "ERROR: A7 prepare stopped; immutable pending directory retained" >&2' ERR
    capture_gcloud_json "$PENDING/build-metadata.json" gcloud builds \
      describe "$BUILD_ID" --project "$PROJECT" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - \
      "$PENDING/build-metadata.json" "$BUILD_ID" "$IMAGE" "$CODE_SHA" <<'PY'
import json
import sys
from finish_a7_select_ladder import _validate_build_metadata

_validate_build_metadata(
    json.load(open(sys.argv[1], encoding="utf-8")),
    build_id=sys.argv[2], image=sys.argv[3], code_sha=sys.argv[4],
)
PY
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-freeze \
      --freeze-manifest-uri "$FREEZE_URI" \
      --freeze-manifest-generation "$FREEZE_GENERATION" \
      --freeze-manifest-sha256 "$FREEZE_SHA256" \
      --code-sha "$CODE_SHA" --image "$IMAGE" \
      --a3-logical-release "$A3_RELEASE" \
      --receipt "$PENDING/freeze-validation.json"
    cp --no-clobber "$A3_RELEASE" "$PENDING/a3-logical-release.json"
    cp --no-clobber "$PREFLIGHT_OUT/job-claim-receipt.json" \
      "$PENDING/job-claim-receipt.json"
    cp --no-clobber "$PREFLIGHT_OUT/support/terminal-receipt.json" \
      "$PENDING/support-terminal-receipt.json"
    validate_prefix_inventory frozen "$PENDING/prelaunch-inventory.txt"

    capture_gcloud_json "$PENDING/job-before.json" gcloud run jobs describe \
      "$JOB" --project "$PROJECT" --region "$REGION" --format=json
    canonical_job_is_idle "$JOB" "$PENDING/job-executions-before.json"
    validate_job_chain_before historical "$PENDING/job-before.json"
    # --set-env-vars replaces the complete environment; it is not an update.
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
      --max-retries 0 --task-timeout 2h \
      --clear-volumes --clear-volume-mounts --workdir="" --startup-probe="" \
      --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE,A7_FREEZE_MANIFEST_URI=$FREEZE_URI,A7_FREEZE_MANIFEST_GENERATION=$FREEZE_GENERATION,A7_FREEZE_MANIFEST_SHA256=$FREEZE_SHA256" \
      --command python \
      --args "scripts/run_a7_select_ladder.py,--output-uri,$RESULT_URI,--freeze-manifest-uri,$FREEZE_URI,--freeze-manifest-generation,$FREEZE_GENERATION,--freeze-manifest-sha256,$FREEZE_SHA256" \
      --quiet >/dev/null
    capture_gcloud_json "$PENDING/job-after.json" gcloud run jobs describe \
      "$JOB" --project "$PROJECT" --region "$REGION" --format=json
    canonical_job_is_idle "$JOB" "$PENDING/job-executions-after.json"

    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - \
      "$PENDING" "$IMAGE" "$CODE_SHA" "$BUILD_ID" "$FREEZE_URI" \
      "$FREEZE_GENERATION" "$FREEZE_SHA256" "$RESULT_URI" \
      "$JOB" "$SERVICE_ACCOUNT" "$PENDING/job-claim-receipt.json" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

from finish_a7_select_ladder import (
    RUN_ID, _canonical_json, _validate_reused_job_receipts,
    _validate_updated_job_spec,
)

out = Path(sys.argv[1])
image, code, build, freeze_uri, freeze_generation, freeze_sha = sys.argv[2:8]
result_uri, job, service_account, claim_path = sys.argv[8:]
before = json.loads((out / "job-before.json").read_text(encoding="utf-8"))
after = json.loads((out / "job-after.json").read_text(encoding="utf-8"))
uid = str(after.get("metadata", {}).get("uid", ""))
generation = str(after.get("metadata", {}).get("generation", ""))
if not uid or not generation.isdigit():
    raise SystemExit("ERROR: A7 post-update job identity differs")
from finish_a7_select_ladder import FrozenRun
freeze = json.loads(
    (out / "freeze-validation.json").read_text(encoding="utf-8")
)
frozen = FrozenRun(
    run_id=RUN_ID, code_sha=code, image=image, build_id=build,
    protocol_sha256=freeze["protocol_sha256"],
    freeze_manifest_uri=freeze_uri,
    freeze_manifest_generation=freeze_generation,
    freeze_manifest_sha256=freeze_sha,
    freeze_validation_sha256=sha256(
        (out / "freeze-validation.json").read_bytes()
    ).hexdigest(),
    a3_logical_release_sha256=sha256(
        (out / "a3-logical-release.json").read_bytes()
    ).hexdigest(),
    job=job, job_uid=uid, job_generation=generation,
)
support_terminal = json.loads(
    (out / "support-terminal-receipt.json").read_text(encoding="utf-8")
)
support_terminal_raw = (out / "support-terminal-receipt.json").read_bytes()
if support_terminal.get("build_id") != build or sha256(
    support_terminal_raw
).hexdigest() != freeze["preflights"]["support"]["terminal"]["sha256"]:
    raise SystemExit("ERROR: A7 historical/preflight build identity differs")
_validate_reused_job_receipts(
    before, after, frozen,
    expected_before_generation=str(
        support_terminal["execution"]["job_generation"]
    ),
    expected_before_spec_sha256=str(
        support_terminal["execution"]["job_spec_sha256"]
    ),
)
claim_raw = Path(claim_path).read_bytes()
claim = json.loads(claim_raw)
if freeze.get("job_claim") != claim:
    raise SystemExit("ERROR: A7 freeze/job-claim binding differs")
job_spec_sha = _validate_updated_job_spec(
    after, code_sha=code, image=image, mode="historical",
    freeze_manifest_uri=freeze_uri,
    freeze_manifest_generation=freeze_generation,
    freeze_manifest_sha256=freeze_sha,
)
manifest = {
    "version": "a7-select-ladder-launch-manifest-v1",
    "run_id": RUN_ID,
    "code_sha": code,
    "image": image,
    "build_id": build,
    "protocol_sha256": freeze["protocol_sha256"],
    "freeze_manifest_uri": freeze_uri,
    "freeze_manifest_generation": freeze_generation,
    "freeze_manifest_sha256": freeze_sha,
    "freeze_validation_sha256": frozen.freeze_validation_sha256,
    "transport_repair_sha256": freeze["transport_repair_sha256"],
    "a3_logical_release_sha256": frozen.a3_logical_release_sha256,
    "job_claim": claim,
    "job_claim_receipt_sha256": sha256(claim_raw).hexdigest(),
    "job": job,
    "job_uid": uid,
    "job_generation": generation,
    "job_spec_sha256": job_spec_sha,
    "service_account": service_account,
    "output_uri": result_uri,
    "tasks": 1, "parallelism": 1, "cpu": "4", "memory": "16Gi",
    "timeout_seconds": 7200, "max_retries": 0,
    "uses_realized_outcomes": True,
    "production_change_licensed": False,
    "production_law_scorefree_transfer_licensed": False,
    "prospective_shadow_licensed": False,
    "job_update_mode": "reuse-only-update-existing",
}
(out / "manifest.json").write_bytes(_canonical_json(manifest))
PY
    # The freeze validator receipts protocol SHA through the manifest body.
    "$PYTHON" - "$PENDING/manifest.json" "$FREEZE_URI" "$FREEZE_GENERATION" <<'PY'
import json
import sys

path, uri, generation = sys.argv[1:]
value = json.load(open(path, encoding="utf-8"))
if value["freeze_manifest_uri"] != uri or value["freeze_manifest_generation"] != generation:
    raise SystemExit("ERROR: A7 launch manifest freeze binding differs")
if not value.get("protocol_sha256"):
    raise SystemExit("ERROR: A7 launch manifest lacks protocol SHA")
PY
    (
      cd "$PENDING"
      sha256sum manifest.json build-metadata.json freeze-validation.json \
        a3-logical-release.json job-claim-receipt.json \
        support-terminal-receipt.json job-before.json job-after.json \
        > prepared.sha256
    )
    rm "$PENDING/prelaunch-inventory.txt" \
      "$PENDING/job-executions-before.json" \
      "$PENDING/job-executions-after.json"
    mv "$PENDING" "$OUT"
    trap - ERR
    echo "A7_REUSE_JOB_PREPARED $JOB"
    ;;

  launch)
    [ -d "$OUT" ] || die "A7 prepared run is absent"
    [ -s "$OUT/lease-receipt.json" ] || die "A7 lease receipt is absent"
    [ ! -e "$OUT/executions.txt" ] && [ ! -e "$OUT/launch-intent.json" ] && \
      [ ! -e "$OUT/launch.sha256" ] || \
      die "A7 execution ledger already exists"
    strict_object_absent "$RESULT_URI"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - "$OUT" <<'PY'
import json
from pathlib import Path
import sys

from finish_a7_select_ladder import (
    _load_json, _validate_hash_ledger, _validate_lease_receipt, FrozenRun,
)
from historical_outcome_lease import _verified_lease_blob

out = Path(sys.argv[1])
_validate_hash_ledger(
    out / "prepared.sha256", base=out,
    expected={"manifest.json", "build-metadata.json", "freeze-validation.json",
              "a3-logical-release.json", "job-claim-receipt.json",
              "support-terminal-receipt.json", "job-before.json",
              "job-after.json"},
)
m = _load_json(out / "manifest.json", label="launch manifest")
frozen = FrozenRun(
    run_id=m["run_id"], code_sha=m["code_sha"], image=m["image"],
    build_id=m["build_id"], protocol_sha256=m["protocol_sha256"],
    freeze_manifest_uri=m["freeze_manifest_uri"],
    freeze_manifest_generation=m["freeze_manifest_generation"],
    freeze_manifest_sha256=m["freeze_manifest_sha256"],
    freeze_validation_sha256=m["freeze_validation_sha256"],
    a3_logical_release_sha256=m["a3_logical_release_sha256"],
    job=m["job"], job_uid=m["job_uid"], job_generation=m["job_generation"],
    job_spec_sha256=m["job_spec_sha256"],
    job_claim_receipt_sha256=m["job_claim_receipt_sha256"],
)
lease = _load_json(out / "lease-receipt.json", label="lease receipt")
_validate_lease_receipt(lease, frozen=frozen)
_verified_lease_blob(lease)
PY
    IMAGE=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$OUT/manifest.json")
    CODE_SHA=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["code_sha"])' "$OUT/manifest.json")
    capture_gcloud_json "$OUT/.job-launch-check.json" gcloud run jobs \
      describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json
    canonical_job_is_idle "$JOB" "$OUT/.job-executions-launch-check.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - \
      "$OUT/manifest.json" "$OUT/.job-launch-check.json" <<'PY'
import json
import sys
from finish_a7_select_ladder import _validate_updated_job_spec
m = json.load(open(sys.argv[1], encoding="utf-8"))
j = json.load(open(sys.argv[2], encoding="utf-8"))
meta = j.get("metadata", {})
if meta.get("name") != m["job"] or meta.get("uid") != m["job_uid"] or \
        str(meta.get("generation")) != m["job_generation"]:
    raise SystemExit("ERROR: A7 reused job changed after preparation")
if _validate_updated_job_spec(
    j, code_sha=m["code_sha"], image=m["image"], mode="historical",
    freeze_manifest_uri=m["freeze_manifest_uri"],
    freeze_manifest_generation=m["freeze_manifest_generation"],
    freeze_manifest_sha256=m["freeze_manifest_sha256"],
) != m["job_spec_sha256"]:
    raise SystemExit("ERROR: A7 reused job spec changed after preparation")
PY
    rm "$OUT/.job-launch-check.json" "$OUT/.job-executions-launch-check.json"
    strict_object_absent "$RESULT_URI"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" - "$OUT/lease-receipt.json" <<'PY'
import json
import sys
from historical_outcome_lease import _verified_lease_blob
_verified_lease_blob(json.load(open(sys.argv[1], encoding="utf-8")))
PY
    "$PYTHON" - "$OUT/launch-intent.json" "$JOB" "$RESULT_URI" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

path, job, uri = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
payload = {
    "version": "a7-select-ladder-launch-intent-v1",
    "run_id": "20260820-a7-select-ladder-phase-s-incumbent-v2",
    "job": job,
    "output_uri": uri,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "execution_started": "unknown-until-ledger-created",
}
with path.open("xb") as handle:
    handle.write((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode())
PY
    EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [[ "$EXECUTION" == "$JOB-"* ]] || die "A7 execution identity missing"
    printf '%s %s %s\n' "$JOB" "$EXECUTION" "$RESULT_URI" \
      > "$OUT/executions.txt"
    (
      cd "$OUT"
      sha256sum manifest.json prepared.sha256 launch-intent.json executions.txt lease-receipt.json \
        > launch.sha256
    )
    echo "A7_SELECT_LADDER_LAUNCHED $EXECUTION"
    ;;

  *)
    die "usage: $0 preflight-prepare IMAGE CODE_SHA BUILD_ID | smoke | support | freeze | prepare IMAGE CODE_SHA BUILD_ID FREEZE_URI FREEZE_GENERATION FREEZE_SHA256 | launch"
    ;;
esac
