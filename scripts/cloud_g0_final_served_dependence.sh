#!/bin/bash
# Launch the sole frozen G0 dependence premise diagnostic.
# Usage: cloud_g0_final_served_dependence.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-g0-final-served-dependence-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g0-dependence-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-12-g0-final-served-dependence-protocol.md"
SELECTED="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean/selected_team_qb.txt"
FINAL="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-final-served-v1-pit-clean/report.json"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
SCHED="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable G0 image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$SELECTED" "$FINAL" "$USAGE" "$ACTIVE" "$SCHED"; do
  [ -s "$path" ] || { echo "ABORT: G0 prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable G0 execution already recorded"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$SELECTED" "$FINAL" "$USAGE" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(
        line.rstrip("\n").split("=", 1)
        for line in open(path, encoding="utf-8") if "=" in line)

selected = selection(sys.argv[1])
report = json.load(open(sys.argv[2], encoding="utf-8"))
usage = selection(sys.argv[3])
panel = selected.get("historical_source", "")
cache = selected.get("cache_table", "")
selected_eval = selected.get("selected_eval_panel", "")
is_treatment = selected.get("team_qb_selected") == "true"
arm = "treatment" if is_treatment else "control"
allowed = {
    "tabpfn_projections_pit_v2",
    "tabpfn_active_label_treatment_v2",
    "tabpfn_sched_treatment_v1",
    "tabpfn_team_qb_treatment_v1",
}
if (not panel or not selected_eval or report.get("panel") != panel
        or cache not in allowed):
    raise SystemExit("ABORT: G0 terminal identity is invalid")
if is_treatment:
    if not report.get("gate", {}).get("passes") or \
            cache != "tabpfn_team_qb_treatment_v1":
        raise SystemExit("ABORT: G0 treatment selection lacks a passing gate")
elif cache == "tabpfn_team_qb_treatment_v1":
    raise SystemExit("ABORT: G0 incumbent selection points at team-QB treatment")
schedule = report.get(f"{arm}_schedule", {})
compact = {
    str(season): {"factors": value.get("factors", {})}
    for season, value in schedule.items()
}
if set(compact) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: G0 selected served schedule is incomplete")
schedule_json = json.dumps(compact, sort_keys=True, separators=(",", ":"))
schedule_b64 = base64.b64encode(schedule_json.encode()).decode()
allocation = usage.get("allocation", "")
k = usage.get("selected_k", "")
if allocation == "multinomial" and k == "infinity":
    accepted_usage, accepted_k = "multinomial", "-"
elif allocation == "dirichlet":
    try:
        valid = math.isfinite(float(k)) and float(k) > 0
    except ValueError:
        valid = False
    if not valid:
        raise SystemExit("ABORT: G0 selected fitted K is invalid")
    accepted_usage, accepted_k = "dirichlet", k
else:
    raise SystemExit("ABORT: G0 selected usage law is invalid")
print(f"panel={panel}")
print(f"cache={cache}")
print(f"selected_eval_panel={selected_eval}")
print(f"schedule_arm={arm}")
print(f"schedule_b64={schedule_b64}")
print(f"accepted_usage={accepted_usage}")
print(f"accepted_k={accepted_k}")
PY
)

mkdir -p "$OUT"
"$ROOT/.venv/bin/python" - "${resolved[cache]}" "$OUT/cache_preflight.json" <<'PY'
import hashlib
import json
import sys

from nfl_dfs.bq import client, query_df
from nfl_dfs.config import settings

name = f"{settings.features}.{sys.argv[1]}"
table = client().get_table(name)
summary = query_df(f"""
SELECT COUNT(*) AS row_count,
       COUNT(DISTINCT CONCAT(CAST(season AS STRING), '|', CAST(week AS STRING), '|', gsis_id)) AS unique_keys,
       BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS content_checksum
FROM `{name}` t
""").iloc[0]
schema = [{"name": field.name, "type": field.field_type, "mode": field.mode}
          for field in table.schema]
report = {
    "table": name,
    "rows": int(summary.row_count),
    "unique_keys": int(summary.unique_keys),
    "content_checksum": int(summary.content_checksum),
    "last_modified": table.modified.isoformat(),
    "schema_sha256": hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest(),
}
if report["rows"] != 52307 or report["unique_keys"] != 52307:
    raise SystemExit("ABORT: G0 selected cache key contract differs")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

SCHEDULE_SHA=$(printf '%s' "${resolved[schedule_b64]}" | base64 -d | sha256sum | awk '{print $1}')
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=${resolved[panel]}" "cache_table=${resolved[cache]}" \
  "selected_eval_panel=${resolved[selected_eval_panel]}" \
  "schedule_arm=${resolved[schedule_arm]}" "schedule_sha256=$SCHEDULE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "terminal_selection_sha256=$(sha256sum "$SELECTED" | awk '{print $1}')" \
  "team_qb_final_served_sha256=$(sha256sum "$FINAL" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "sched_selection_sha256=$(sha256sum "$SCHED" | awk '{print $1}')" \
  "cache_preflight_sha256=$(sha256sum "$OUT/cache_preflight.json" | awk '{print $1}')" \
  "accepted_usage_law=${resolved[accepted_usage]}" \
  "dirichlet_k=${resolved[accepted_k]}" \
  'evaluation_seasons=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'bootstrap_replicates=2000' 'bootstrap_seed=1701' \
  'mean_projection_minimum=4.0' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,G0_PANEL_ID=${resolved[panel]}"
ENVS="$ENVS,G0_CACHE_TABLE=${resolved[cache]}"
ENVS="$ENVS,G0_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=${resolved[accepted_usage]}"
if [ "${resolved[accepted_usage]}" = dirichlet ]; then
  ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=${resolved[accepted_k]}"
  ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=${resolved[accepted_k]}"
fi
JOB=g0-final-served-dependence-v2
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "g0-final-served-dependence,--panel,${resolved[panel]}" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: G0 job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: G0 execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "G0_FINAL_SERVED_DEPENDENCE_LAUNCHED $EXEC"
