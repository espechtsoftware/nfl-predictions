#!/bin/bash
# Validate, compare and mechanically select the PIT-clean position-scale arm.
# Usage: cloud_finish_served_position_stage_b_v2.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONTROL=20260812-pitclean-e80-selected-position-control-v2
TREATMENT=20260812-pitclean-e80-selected-position-scales-v2
SELECTION="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
CALIBRATION="$ROOT/reports/served-position-calibration-runs/20260812-served-position-calibration-v2-pit-clean/report.json"
OUT="$ROOT/reports/served-position-calibration-runs/20260812-served-position-stage-b-v2-pit-clean"
REPORT="$OUT/comparison.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
for path in "$SELECTION" "$CALIBRATION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_position.txt" ] || { echo "ABORT: immutable position selection exists"; exit 2; }
BASE=$(awk -F= '$1=="selected_base" {print $2}' "$SELECTION")
SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$SELECTION")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$SELECTION")
case "$BASE" in k1|k3) ;; *) echo "ABORT: invalid selected base"; exit 2;; esac
case "$ROLE_SELECTED" in true|false) ;; *) echo "ABORT: invalid role selection"; exit 2;; esac

POSITION_SPEC=$("$ROOT/.venv/bin/python" - "$CALIBRATION" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "served-position-calibration-passes" or not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: repaired position calibration did not pass")
factors = report.get("r2_final_served_fit", {}).get("factors", {})
if set(factors) != {"QB", "RB", "TE", "WR"}:
    raise SystemExit("ABORT: repaired position factors are incomplete")
print(",".join(f"{pos}:{float(factors[pos])!r}" for pos in ("QB", "RB", "TE", "WR")))
PY
)
POSITION_B64=$(printf '%s' "$POSITION_SPEC" | base64 -w0)

bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$CONTROL" check 80 2 "2023 2024 2025"
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" check 80 2 "2023 2024 2025"

mkdir -p "$OUT"
JOB=compare-served-position-stage-b-v2
ARGS="scripts/compare_served_position_lineup_v2.py,--source,$SOURCE,--control,$CONTROL,--treatment,$TREATMENT,--code-sha,a12ab31,--position-spec-b64,$POSITION_B64,--base,$BASE,--role-selected,$ROLE_SELECTED"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: deployed image mismatch"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/comparison_execution.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SERVED_POSITION_STAGE_B_V2_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/comparison_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/comparison_raw.txt" "$REPORT" <<'PY'
import json
import sys
prefix = "SERVED_POSITION_STAGE_B_V2_JSON="
payloads = [json.loads(line.split(prefix, 1)[1]) for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one position comparison, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: repaired position comparison is invalid")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: comparator execution failed"; exit 1; }

SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$CONTROL" "$TREATMENT" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
selected = report.get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: position selection is not a registered panel")
print(selected)
PY
)
if [ "$SELECTED" = "$TREATMENT" ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" promote 80 2 "2023 2024 2025"
  POSITION_SELECTED=true
  SERVED_SCALES=$POSITION_SPEC
else
  POSITION_SELECTED=false
  SERVED_SCALES=identity
fi
printf '%s\n' \
  "selected_base=$BASE" "source_panel=$SOURCE" \
  "role_selected=$ROLE_SELECTED" "position_selected=$POSITION_SELECTED" \
  "selected_eval_panel=$SELECTED" "served_position_scales=$SERVED_SCALES" \
  "comparison_execution=$EXEC" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_position.txt"
echo "PIT_POSITION_STAGE_B_SELECTED $SELECTED"
