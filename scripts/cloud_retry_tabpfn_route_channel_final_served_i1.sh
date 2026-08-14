#!/bin/bash
# Retry the frozen Route marginal-channel gate after its verified 16Gi OOM.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-tabpfn-route-channel-final-served-i1-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-route-channel-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
ORIGINAL_FILE="$OUT/execution.txt"
RETRY_FILE="$OUT/retry_execution.txt"

for path in "$MANIFEST" "$ORIGINAL_FILE"; do
  [ -s "$path" ] || { echo "ABORT: Route gate prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/report.json" ] || { echo "ABORT: Route gate report already exists"; exit 2; }
[ ! -e "$RETRY_FILE" ] || { echo "ABORT: Route gate retry already recorded"; exit 2; }

IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
PANEL=$(awk -F= '$1=="panel" {print $2}' "$MANIFEST")
PHASE_S_ARM=$(awk -F= '$1=="phase_s_arm" {print $2}' "$MANIFEST")
DIRICHLET_K=$(awk -F= '$1=="dirichlet_k" {print $2}' "$MANIFEST")
ORIGINAL=$(tr -d '[:space:]' < "$ORIGINAL_FILE")
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image missing"; exit 2;; esac
[ "$PHASE_S_ARM" = treatment ] || {
  echo "ABORT: recorded Route gate did not inherit Phase S treatment"; exit 2; }
[ "$DIRICHLET_K" = 28.154043586960896 ] || {
  echo "ABORT: recorded Route gate finite K differs"; exit 2; }

EXEC_JSON=$(mktemp)
trap 'rm -f "$EXEC_JSON"' EXIT
gcloud run jobs executions describe "$ORIGINAL" --project "$PROJECT" \
  --region "$REGION" --format=json > "$EXEC_JSON"
"$ROOT/.venv/bin/python" - "$EXEC_JSON" "$ORIGINAL" "$IMG" "$PANEL" "$DIRICHLET_K" <<'PY'
import json
import sys

path, name, image, panel, k = sys.argv[1:]
payload = json.load(open(path, encoding="utf-8"))
spec = payload.get("spec", {}).get("template", {}).get("spec", {})
containers = spec.get("containers", [])
failures = []
if payload.get("metadata", {}).get("name") != name:
    failures.append("original execution name differs")
conditions = payload.get("status", {}).get("conditions", [])
completed = next((row for row in conditions if row.get("type") == "Completed"), {})
if completed.get("status") != "False" or \
        "configured memory limit was reached" not in completed.get("message", ""):
    failures.append("original failure is not the verified memory limit")
if len(containers) != 1:
    failures.append("original container count differs")
else:
    container = containers[0]
    env = {row.get("name"): row.get("value") for row in container.get("env", [])}
    expected_env = {
        "GCP_PROJECT": "nfl-predictions-503414",
        "TABPFN_ROUTE_CHANNEL_PANEL_ID": panel,
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
    if container.get("args") != [
            "tabpfn-route-channel-final-served", "--panel", panel]:
        failures.append("original args differ")
    if env != expected_env:
        failures.append("original environment differs")
    if container.get("resources", {}).get("limits") != {
            "cpu": "8", "memory": "16Gi"}:
        failures.append("original resource limit differs")
if spec.get("maxRetries") != 0 or spec.get("timeoutSeconds") != "10800":
    failures.append("original retry/timeout differs")
if failures:
    raise SystemExit("ABORT: " + "; ".join(failures))
print("ROUTE_GATE_OOM_PROVENANCE_VERIFIED", name)
PY

ENVS="GCP_PROJECT=$PROJECT,TABPFN_ROUTE_CHANNEL_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_ROUTE_PHASE_S_ARM=treatment"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,SIS_ASOE_TARGET_ALLOCATION=1,SIS_ASOE_BETA=0.07771181538347656"
JOB=tabpfn-route-channel-final-served-i1-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-route-channel-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: Route gate retry deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: Route gate retry execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$RETRY_FILE"
echo "TABPFN_ROUTE_CHANNEL_FINAL_SERVED_RETRIED $EXEC"
