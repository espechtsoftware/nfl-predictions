#!/usr/bin/env bash
set -uo pipefail

# Serialize the one A7 historical look behind the A3 logical release and the
# durable historical-outcome lease.  This wrapper polls execution metadata
# only; the Python finisher owns every object-inventory and body read.
#
# Usage: watch_a7_select_ladder_queue.sh IMAGE CODE_SHA BUILD_ID

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260820-a7-select-ladder-phase-s-incumbent-v2
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/a7-select-ladder-runs/$RUN_ID"
PREFLIGHT_OUT="$ROOT/reports/a7-select-ladder-preflight-runs/$RUN_ID"
A3_RELEASE="$ROOT/reports/stack-relaxation-carve-runs/20260819-stack-relaxation-carve-v1/logical-release.json"
V1_FAILURE_RELEASE="$ROOT/reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/failed-preflight-logical-release.json"
V1_FAILURE_RELEASE_OBJECT="$ROOT/reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/failed-preflight-logical-release-object.json"
LAUNCHER="$ROOT/scripts/cloud_a7_select_ladder.sh"
FINISHER="$ROOT/scripts/finish_a7_select_ladder.py"
LEASE_TOOL="$ROOT/scripts/historical_outcome_lease.py"
PYTHON="$ROOT/.venv/bin/python"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}
FREEZE_URI="gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/$RUN_ID/preflight/freeze-manifest.json"

for repair_name in A7_FINISHER_REPAIR_SHA256 A7_LAUNCHER_REPAIR_SHA256 \
  A7_WATCHER_REPAIR_SHA256; do
  repair_value=${!repair_name:-}
  [ -z "$repair_value" ] || [[ "$repair_value" =~ ^[0-9a-f]{64}$ ]] || exit 2
done

[[ "$IMAGE" =~ ^.+@sha256:[0-9a-f]{64}$ ]] || exit 2
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit 2

capture_gcloud_json() {
  local target=$1
  shift
  local raw="$target.gcloud.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$raw" ] || return 2
  if ! "$@" > "$raw"; then
    echo "ERROR: A7 external JSON command failed; raw response retained: $raw" >&2
    return 2
  fi
  if ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$raw" --output "$target"; then
    echo "ERROR: A7 external JSON canonicalization failed; raw response retained: $raw" >&2
    return 2
  fi
  rm -- "$raw"
}

write_failure_closure() {
  "$PYTHON" - "$1" "$2" "$3" "$4" "$5" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

directory = Path(sys.argv[1])
reason, disposition, execution_name, abandon = sys.argv[2:6]
prefix = "HISTORICAL_OUTCOME_LEASE_ABANDONED "
if re.fullmatch(
    prefix
    + r"gs://nfl-predictions-503414-raw/research-governance/archive/"
    + r"historical-outcome-stale-[0-9]{8}-[0-9]{6}-"
    + re.escape(reason)
    + r"\.json",
    abandon,
) is None:
    raise SystemExit("A7 failed-attempt abandon evidence differs")
lease = directory / "lease-receipt.json"
execution = directory / "execution.json"
terminal = execution_name != "none"
if not lease.is_file() or terminal is not execution.is_file():
    raise SystemExit("A7 failed-attempt closure inputs differ")
value = {
    "version": "a7-watcher-failure-closure-v1",
    "run_id": "20260820-a7-select-ladder-phase-s-incumbent-v2",
    "reason": reason,
    "disposition": disposition,
    "execution": execution_name if terminal else None,
    "execution_sha256": (
        sha256(execution.read_bytes()).hexdigest() if terminal else None
    ),
    "lease_receipt_sha256": sha256(lease.read_bytes()).hexdigest(),
    "lease_archive_uri": abandon[len(prefix):],
    "possible_historical_outcome_access": terminal,
    "historical_retry_licensed": False,
    "production_change_licensed": False,
    "production_law_scorefree_transfer_licensed": False,
    "prospective_shadow_licensed": False,
}
raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
with (directory / "abandon.txt").open("x", encoding="utf-8") as handle:
    handle.write(abandon + "\n")
with (directory / "failure-closure.json").open("xb") as handle:
    handle.write(raw)
with (directory / "failure-closure.sha256").open("x", encoding="utf-8") as handle:
    handle.write(
        sha256(raw).hexdigest() + "  failure-closure.json\n"
    )
PY
}

if [ -s "$OUT/lease-release.txt" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" validate-closed \
    --output-dir "$OUT" || exit $?
  echo "A7_SELECT_LADDER_ALREADY_RELEASED"
  exit 0
fi
[ ! -e "$OUT/lease-release.txt" ] || exit 2
shopt -s nullglob
FAILURE_CLOSURES=()
[ ! -e "$OUT/failed-prelaunch" ] || FAILURE_CLOSURES+=(
  "$OUT/failed-prelaunch"
)
FAILURE_CLOSURES+=("$OUT"/failed-terminal-*)
shopt -u nullglob
if [ "${#FAILURE_CLOSURES[@]}" -ne 0 ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    validate-failure-closure --output-dir "$OUT" || exit $?
  echo "ERROR: A7 prior failure closure forbids retry" >&2
  exit 2
fi
if [ -s "$OUT/finish.sha256" ] && [ ! -e "$OUT/lease-release.txt" ]; then
  FINISHED_USES_REALIZED=$(
    "$PYTHON" - "$OUT/completion.txt" <<'PY'
import sys
value = dict(
    line.split("=", 1)
    for line in open(sys.argv[1], encoding="utf-8") if "=" in line
)
print(value.get("uses_realized_outcomes", ""))
PY
  ) || exit $?
  if [ "$FINISHED_USES_REALIZED" = true ]; then
    # A durable result harvest must resume only its already-registered release;
    # it may never fall through to a new lease acquisition.
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      close-realized-lease --output-dir "$OUT" || exit $?
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-closed --output-dir "$OUT" || exit $?
    echo "A7_SELECT_LADDER_RESUMED_REALIZED_LEASE_CLOSE"
    exit 0
  elif [ "$FINISHED_USES_REALIZED" != false ]; then
    echo "ERROR: A7 completed outcome state differs; lease held" >&2
    exit 2
  fi
fi

while [ ! -s "$A3_RELEASE" ]; do
  printf '%s A7_WAITS_FOR_A3_LOGICAL_RELEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

while [ ! -s "$V1_FAILURE_RELEASE" ] || \
    [ ! -s "$V1_FAILURE_RELEASE_OBJECT" ]; do
  printf '%s A7_WAITS_FOR_V1_FAILED_PREFLIGHT_LOGICAL_RELEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ ! -d "$PREFLIGHT_OUT" ]; then
  bash "$LAUNCHER" preflight-prepare "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
fi
if [ ! -s "$PREFLIGHT_OUT/smoke/finish.sha256" ]; then
  bash "$LAUNCHER" smoke || exit $?
fi
if [ ! -s "$PREFLIGHT_OUT/support/finish.sha256" ]; then
  bash "$LAUNCHER" support || exit $?
fi
SUPPORT_DISPOSITION=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$PREFLIGHT_OUT/support/terminal-receipt.json") || exit $?
if [ "$SUPPORT_DISPOSITION" = invalid-unsupported ]; then
  echo "A7_SELECT_LADDER_CLOSED_UNSUPPORTED no_historical_look=true"
  exit 0
fi
[ "$SUPPORT_DISPOSITION" = support-passed ] || exit 2
if [ ! -s "$PREFLIGHT_OUT/freeze-upload-receipt.json" ]; then
  bash "$LAUNCHER" freeze || exit $?
fi
read -r FREEZE_GENERATION FREEZE_SHA256 < <("$PYTHON" - \
  "$PREFLIGHT_OUT/freeze-upload-receipt.json" "$FREEZE_URI" <<'PY'
import json, re, sys
value = json.load(open(sys.argv[1]))
obj = value.get("object", {})
if obj.get("uri") != sys.argv[2] or re.fullmatch(
    r"[1-9][0-9]*", str(obj.get("generation", ""))
) is None or re.fullmatch(r"[0-9a-f]{64}", str(obj.get("sha256", ""))) is None:
    raise SystemExit("A7 freeze upload receipt differs")
print(obj["generation"], obj["sha256"])
PY
) || exit $?

if [ ! -d "$OUT" ]; then
  bash "$LAUNCHER" prepare "$IMAGE" "$CODE_SHA" "$BUILD_ID" \
    "$FREEZE_URI" "$FREEZE_GENERATION" "$FREEZE_SHA256" || exit $?
fi

LEASE="$OUT/lease-receipt.json"
while [ ! -s "$LEASE" ]; do
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" acquire \
    --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$LEASE"
  RC=$?
  if [ "$RC" -eq 0 ]; then
    break
  fi
  [ ! -e "$LEASE" ] || exit 2
  printf '%s A7_WAITS_FOR_HISTORICAL_OUTCOME_LEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ ! -s "$OUT/executions.txt" ]; then
  bash "$LAUNCHER" launch
  RC=$?
  if [ "$RC" -ne 0 ]; then
    if [ ! -e "$OUT/launch-intent.json" ]; then
      ABANDON_OUTPUT=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" \
        "$PYTHON" "$LEASE_TOOL" abandon \
        --receipt "$LEASE" --reason a7-prelaunch-failed \
        --preserve-dir "$OUT/failed-prelaunch") || exit $?
      write_failure_closure "$OUT/failed-prelaunch" a7-prelaunch-failed \
        closed-prelaunch-no-retry none "$ABANDON_OUTPUT" || exit $?
    else
      echo "ERROR: A7 launch is ambiguous; lease held for operator review" >&2
    fi
    exit "$RC"
  fi
fi

read -r LEDGER_JOB EXECUTION LEDGER_URI < "$OUT/executions.txt" || exit 2
[ "$LEDGER_JOB" = "$JOB" ] && [[ "$EXECUTION" == "$JOB-"* ]] || exit 2
[ "$LEDGER_URI" = \
  "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/$RUN_ID/result.json" ] || exit 2

while :; do
  POLL="$OUT/.execution-poll.json"
  if ! capture_gcloud_json "$POLL" gcloud run jobs executions describe \
    "$EXECUTION" --project "$PROJECT" --region "$REGION" --format=json; then
    echo "ERROR: A7 execution poll failed; lease held for operator review" >&2
    exit 2
  fi
  STATE=$("$PYTHON" - "$POLL" <<'PY'
import json
import sys

value = json.load(open(sys.argv[1], encoding="utf-8"))
rows = [
    row for row in value.get("status", {}).get("conditions", [])
    if row.get("type") == "Completed"
]
if not rows:
    print("Unknown")
elif len(rows) == 1 and rows[0].get("status") in {"Unknown", "True", "False"}:
    print(rows[0]["status"])
else:
    print("Malformed")
PY
  ) || exit $?
  printf '%s A7_EXECUTION state=%s execution=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATE" "$EXECUTION"
  case "$STATE" in
    True)
      rm "$POLL"
      break
      ;;
    False)
      FAILED="$OUT/failed-terminal-$EXECUTION"
      mkdir "$FAILED" || exit $?
      mv "$POLL" "$FAILED/execution.json" || exit $?
      ABANDON_OUTPUT=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" \
        "$PYTHON" "$LEASE_TOOL" abandon \
        --receipt "$LEASE" --reason a7-terminal-failed \
        --preserve-dir "$FAILED") || exit $?
      write_failure_closure "$FAILED" a7-terminal-failed \
        closed-terminal-failed-no-retry "$EXECUTION" "$ABANDON_OUTPUT" || exit $?
      echo "ERROR: A7 execution failed terminally; own lease abandoned" >&2
      exit 2
      ;;
    Unknown|"")
      rm "$POLL"
      sleep 60
      ;;
    *)
      echo "ERROR: A7 execution metadata malformed; lease held" >&2
      exit 2
      ;;
  esac
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" finish \
  --output-dir "$OUT" || {
    echo "ERROR: A7 strict harvest failed; lease held for operator review" >&2
    exit 2
  }

read -r RELEASE_LICENSE USES_REALIZED DISPOSITION < <("$PYTHON" - \
  "$OUT/completion.txt" <<'PY'
import sys
value = dict(
    line.split("=", 1) for line in open(sys.argv[1], encoding="utf-8") if "=" in line
)
print(
    value.get("historical_outcome_lease_release_licensed", ""),
    value.get("uses_realized_outcomes", ""),
    value.get("disposition", ""),
)
PY
) || exit $?
[ "$RELEASE_LICENSE" = true ] || {
  echo "ERROR: A7 completion does not license lease release" >&2
  exit 2
}

LEASE_ACTION=
LEASE_RECEIPT_FOR_HASH=$LEASE
LEASE_ARCHIVE_URI=none
if [ "$USES_REALIZED" = true ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    close-realized-lease --output-dir "$OUT" || exit $?
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    validate-closed --output-dir "$OUT" || exit $?
  echo "A7_SELECT_LADDER_FINISHED_AND_LEASE_CLOSED $EXECUTION released-after-realized-outcome"
  exit 0
elif [ "$USES_REALIZED" = false ] && \
    [ "$DISPOSITION" = tail-artifact-risk-phase-s ]; then
  TAIL_CLOSURE="$OUT/tail-outcome-blind-closure"
  TAIL_STAGE="$OUT/.tail-lease-abandon"
  TAIL_STAGED_RECEIPT="$TAIL_STAGE/lease-receipt.json"
  TAIL_ABANDON_EVIDENCE="$TAIL_CLOSURE/abandon.txt"
  if [ ! -e "$TAIL_CLOSURE" ]; then
    [ ! -e "$TAIL_STAGE" ] || exit 2
    "$PYTHON" - "$LEASE" "$TAIL_STAGED_RECEIPT" <<'PY'
from pathlib import Path
import sys

source, target = map(Path, sys.argv[1:])
target.parent.mkdir()
with target.open("xb") as handle:
    handle.write(source.read_bytes())
if target.read_bytes() != source.read_bytes():
    raise SystemExit("A7 staged tail lease receipt differs")
PY
    ABANDON_OUTPUT=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" \
      "$PYTHON" "$LEASE_TOOL" abandon --receipt "$TAIL_STAGED_RECEIPT" \
      --reason a7-tail-artifact-no-outcome \
      --preserve-dir "$TAIL_CLOSURE") || exit $?
    rmdir "$TAIL_STAGE" || exit $?
    "$PYTHON" - "$TAIL_ABANDON_EVIDENCE" "$ABANDON_OUTPUT" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
value = sys.argv[2]
if re.fullmatch(
    r"HISTORICAL_OUTCOME_LEASE_ABANDONED "
    r"gs://nfl-predictions-503414-raw/research-governance/archive/"
    r"historical-outcome-stale-[0-9]{8}-[0-9]{6}-"
    r"a7-tail-artifact-no-outcome\.json",
    value,
) is None:
    raise SystemExit("A7 tail abandon evidence differs")
with path.open("x", encoding="utf-8") as handle:
    handle.write(value + "\n")
PY
  fi
  LEASE_RECEIPT_FOR_HASH="$TAIL_CLOSURE/lease-receipt.json"
  read -r ABANDON_MARKER LEASE_ARCHIVE_URI EXTRA < \
    "$TAIL_ABANDON_EVIDENCE" || exit 2
  [ "$ABANDON_MARKER" = HISTORICAL_OUTCOME_LEASE_ABANDONED ] && \
    [ -z "${EXTRA:-}" ] && [ -s "$LEASE_RECEIPT_FOR_HASH" ] && \
    cmp -s "$LEASE" "$LEASE_RECEIPT_FOR_HASH" || exit 2
  LEASE_ACTION=abandoned-after-proven-no-outcome-tail-closure
else
  echo "ERROR: A7 completion outcome/release branch differs; lease held" >&2
  exit 2
fi
"$PYTHON" - "$OUT/lease-release.txt" "$LEASE_RECEIPT_FOR_HASH" \
  "$OUT/completion.txt" "$LEASE_ACTION" "$LEASE_ARCHIVE_URI" <<'PY'
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys

path, lease, completion = map(Path, sys.argv[1:4])
action = sys.argv[4]
archive_uri = sys.argv[5]
raw = (
    f"released_at={datetime.now(timezone.utc).isoformat()}\n"
    "run_id=20260820-a7-select-ladder-phase-s-incumbent-v2\n"
    f"lease_receipt_sha256={sha256(lease.read_bytes()).hexdigest()}\n"
    f"completion_sha256={sha256(completion.read_bytes()).hexdigest()}\n"
    f"lease_action={action}\n"
    f"lease_archive_uri={archive_uri}\n"
    "lease_release_intent_uri=none\n"
    "lease_release_intent_generation=none\n"
    "lease_release_intent_sha256=none\n"
    "lease_release_intent_object_sha256=none\n"
)
with path.open("x", encoding="utf-8") as handle:
    handle.write(raw)
PY
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" validate-closed \
  --output-dir "$OUT" || exit $?
echo "A7_SELECT_LADDER_FINISHED_AND_LEASE_CLOSED $EXECUTION $LEASE_ACTION"
