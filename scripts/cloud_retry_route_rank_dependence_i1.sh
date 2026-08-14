#!/bin/bash
# Retry I1-R after the verified NumPy report-serialization failure.
# Usage: cloud_retry_route_rank_dependence_i1.sh <NEW_IMAGE@sha256:...> <NEW_CODE_SHA>
set -euo pipefail

NEW_IMG=${1:-}
NEW_CODE=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-route-rank-dependence-i1-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/route-rank-dependence-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
ORIGINAL_FILE="$OUT/execution.txt"
RETRY_FILE="$OUT/retry_execution.txt"
RETRY_MANIFEST="$OUT/transport_retry.txt"
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/report.json"
G0="$ROOT/reports/g0-dependence-runs/20260812-g0-final-served-dependence-v2/report.json"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$NEW_IMG" in *@sha256:*) ;; *) echo "ABORT: immutable retry image required"; exit 2;; esac
case "$NEW_CODE" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable retry code SHA required"; exit 2;;
esac
for path in "$MANIFEST" "$ORIGINAL_FILE" "$PHASE_S" "$G0" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: Route rank prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/report.json" ] || { echo "ABORT: Route rank report already exists"; exit 2; }
[ ! -e "$RETRY_FILE" ] && [ ! -e "$RETRY_MANIFEST" ] || {
  echo "ABORT: Route rank retry already recorded"; exit 2; }

OLD_IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
PANEL=$(awk -F= '$1=="panel" {print $2}' "$MANIFEST")
DIRICHLET_K=$(awk -F= '$1=="dirichlet_k" {print $2}' "$MANIFEST")
PHASE_S_ARM=$(awk -F= '$1=="phase_s_arm" {print $2}' "$MANIFEST")
ORIGINAL=$(tr -d '[:space:]' < "$ORIGINAL_FILE")
case "$OLD_IMG" in *@sha256:*) ;; *) echo "ABORT: original immutable image missing"; exit 2;; esac
[ "$PHASE_S_ARM" = treatment ] || {
  echo "ABORT: Route rank did not inherit Phase S treatment"; exit 2; }
[ "$DIRICHLET_K" = 28.154043586960896 ] || {
  echo "ABORT: Route rank finite K differs"; exit 2; }

SCHEDULE_B64=$("$ROOT/.venv/bin/python" - "$PHASE_S" "$G0" "$ACTIVE" "$USAGE" "$PANEL" "$DIRICHLET_K" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

phase = json.load(open(sys.argv[1], encoding="utf-8"))
g0 = json.load(open(sys.argv[2], encoding="utf-8"))
active = selection(sys.argv[3])
usage = selection(sys.argv[4])
panel, expected_k = sys.argv[5:]
if not phase.get("mechanical_passes") or phase.get("failures") or \
        phase.get("result", {}).get("decision", {}).get("selected_arm") != "treatment":
    raise SystemExit("ABORT: selected Phase S treatment differs")
if not g0.get("invariants", {}).get("passes") or \
        g0.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: accepted G0 terminal contract differs")
schedule = g0.get("position_schedule", {})
if set(schedule) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: accepted G0 position schedule differs")
if active.get("historical_source") != panel or \
        active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: active-label selection differs")
if usage.get("allocation") != "dirichlet" or usage.get("selected_k") != expected_k:
    raise SystemExit("ABORT: accepted usage law differs")
if not math.isfinite(float(expected_k)) or float(expected_k) <= 0:
    raise SystemExit("ABORT: fitted K is invalid")
payload = json.dumps(schedule, separators=(",", ":"), sort_keys=True).encode()
print(base64.b64encode(payload).decode().rstrip("="))
PY
)

ERROR_LINE=$(gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$ORIGINAL\" AND textPayload:\"TypeError: Object of type bool is not JSON serializable\"" \
  --project "$PROJECT" --limit 1 --format='value(textPayload)')
case "$ERROR_LINE" in
  *'TypeError: Object of type bool is not JSON serializable'*) ;;
  *) echo "ABORT: original Route rank serialization failure differs"; exit 2;;
esac

EXEC_JSON=$(mktemp)
trap 'rm -f "$EXEC_JSON"' EXIT
gcloud run jobs executions describe "$ORIGINAL" --project "$PROJECT" \
  --region "$REGION" --format=json > "$EXEC_JSON"
"$ROOT/.venv/bin/python" - "$EXEC_JSON" "$ORIGINAL" "$OLD_IMG" "$PANEL" \
  "$DIRICHLET_K" "$SCHEDULE_B64" <<'PY'
import json
import sys

path, name, image, panel, k, schedule = sys.argv[1:]
payload = json.load(open(path, encoding="utf-8"))
spec = payload.get("spec", {}).get("template", {}).get("spec", {})
containers = spec.get("containers", [])
failures = []
if payload.get("metadata", {}).get("name") != name:
    failures.append("original execution name differs")
conditions = payload.get("status", {}).get("conditions", [])
completed = next((row for row in conditions if row.get("type") == "Completed"), {})
if completed.get("status") != "False" or \
        completed.get("reason") != "NonZeroExitCode":
    failures.append("original failure condition differs")
if len(containers) != 1:
    failures.append("original container count differs")
else:
    container = containers[0]
    env = {row.get("name"): row.get("value") for row in container.get("env", [])}
    expected_env = {
        "GCP_PROJECT": "nfl-predictions-503414",
        "ROUTE_RANK_I1_PANEL_ID": panel,
        "ROUTE_RANK_I1_POSITION_SCHEDULE_B64": schedule,
        "TABPFN_ROUTE_PHASE_S_ARM": "treatment",
        "TABPFN_ACCEPTED_USAGE_LAW": "dirichlet",
        "TABPFN_ACCEPTED_DIRICHLET_K": k,
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": k,
        "SIS_ASOE_TARGET_ALLOCATION": "1",
        "SIS_ASOE_BETA": "0.07771181538347656",
    }
    if container.get("image") != image:
        failures.append("original image differs")
    if container.get("command") != ["nfl-dfs"]:
        failures.append("original command differs")
    if container.get("args") != ["route-rank-dependence-i1", "--panel", panel]:
        failures.append("original args differ")
    if env != expected_env:
        failures.append("original environment differs")
    if container.get("resources", {}).get("limits") != {
            "cpu": "8", "memory": "32Gi"}:
        failures.append("original resource limit differs")
if spec.get("maxRetries") != 0 or spec.get("timeoutSeconds") != "14400":
    failures.append("original retry/timeout differs")
if failures:
    raise SystemExit("ABORT: " + "; ".join(failures))
print("ROUTE_RANK_TRANSPORT_FAILURE_PROVENANCE_VERIFIED", name)
PY

ENVS="GCP_PROJECT=$PROJECT,ROUTE_RANK_I1_PANEL_ID=$PANEL"
ENVS="$ENVS,ROUTE_RANK_I1_POSITION_SCHEDULE_B64=$SCHEDULE_B64"
ENVS="$ENVS,TABPFN_ROUTE_PHASE_S_ARM=treatment"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,SIS_ASOE_TARGET_ALLOCATION=1,SIS_ASOE_BETA=0.07771181538347656"
JOB=route-rank-dependence-i1-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$NEW_IMG" --command nfl-dfs \
  --args "route-rank-dependence-i1,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 14400 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$NEW_IMG" ] || {
  echo "ABORT: Route rank retry deployed $DEPLOYED, expected $NEW_IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: Route rank retry execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$RETRY_FILE"
printf '%s\n' \
  "reason=numpy-json-transport-only" "original_execution=$ORIGINAL" \
  "original_image=$OLD_IMG" "retry_image=$NEW_IMG" \
  "retry_code_sha=$NEW_CODE" "retry_execution=$EXEC" > "$RETRY_MANIFEST"
echo "ROUTE_RANK_DEPENDENCE_I1_RETRIED $EXEC"
