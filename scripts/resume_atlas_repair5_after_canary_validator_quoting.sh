#!/usr/bin/env bash
set -euo pipefail

# Resume the already-successful repair5 canary after the frozen validator's
# local awk quoting defect. The canary is not rerun and no object is opened.

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
VALIDATOR="$ROOT/scripts/cloud_wait_atlas_repair5_canary.sh"
VALIDATOR_SHA=e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411
LAUNCHER="$ROOT/scripts/cloud_atlas_matched_diversity_repair5.sh"
LAUNCHER_SHA=3c8092c2bc3e40840a16867621f2f3ffe231f571d3f621818feab61dbefbe330
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
PROTOCOL="$ROOT/reports/2026-08-17-atlas-repair5-canary-validator-quoting-repair.md"
PROTOCOL_SHA=3929c805db67b0d9d66500f6b4d14c6ea4011d8c3723dd2b86535ea9a4e69d94
WRAPPER_DIR="$ROOT/scripts/atlas_repair5_validator_bin"
WRAPPER="$WRAPPER_DIR/awk"
WRAPPER_SHA=42e0c74654f5e7ecb70e164aa1b28bc188f6279bde1273aa45093c51e5871b7a
ATTEMPT0="$OUT/canary-validator-attempt0"
CANARY_EXEC=atlas-md-s2023-w1-r5-45nvf
CANARY_URI=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5/slate-2023-1.json

for SPEC in "$VALIDATOR:$VALIDATOR_SHA" "$LAUNCHER:$LAUNCHER_SHA" \
  "$PROTOCOL:$PROTOCOL_SHA" "$WRAPPER:$WRAPPER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | /usr/bin/awk '{print $1}')" = "$DIGEST" ] || {
    echo "ABORT: ATLAS canary-validator repair dependency differs: $FILE" >&2
    exit 2
  }
done
[ -x "$WRAPPER" ] || {
  echo "ABORT: ATLAS canary-validator awk wrapper is not executable" >&2; exit 2; }
[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: ATLAS repair5 launch evidence is incomplete" >&2; exit 2; }
[ "$(sha256sum "$MANIFEST" | /usr/bin/awk '{print $1}')" = \
    a2812964c3bec8779c7ed8ce4aac8e74d84ea74548f611b87658d4f13371e400 ] || {
  echo "ABORT: ATLAS repair5 manifest differs" >&2; exit 2; }

LEDGER_COUNT=$(wc -l < "$EXECUTIONS")
CANARY_ROW=$(/usr/bin/awk '$1==2023 && $2==1 {print}' "$EXECUTIONS")
[ "$LEDGER_COUNT" -ge 1 ] && [ "$LEDGER_COUNT" -le 54 ] && \
  [ "$(printf '%s\n' "$CANARY_ROW" | wc -l)" = 1 ] || {
  echo "ABORT: ATLAS repair5 pre-resume canary ledger differs" >&2; exit 2; }
read -r SEASON WEEK JOB EXEC URI <<< "$CANARY_ROW"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && \
  [ "$JOB" = atlas-md-s2023-w1-r5 ] && [ "$EXEC" = "$CANARY_EXEC" ] && \
  [ "$URI" = "$CANARY_URI" ] || {
  echo "ABORT: ATLAS repair5 canary identity differs" >&2; exit 2; }
[ ! -e "$OUT/grid-release.txt" ] || {
  echo "ABORT: ATLAS repair5 grid release already exists" >&2; exit 3; }

if [ ! -e "$OUT/canary-completion.txt" ]; then
  [ "$LEDGER_COUNT" = 1 ] && [ ! -e "$OUT/canary.sha256" ] || {
    echo "ABORT: ATLAS repair5 pre-validator state differs" >&2; exit 2; }
  if [ ! -e "$ATTEMPT0" ]; then
    [ -s "$OUT/canary-execution-metadata.json" ] && \
      [ -s "$OUT/canary-object-metadata.json" ] || {
      echo "ABORT: ATLAS repair5 failed-validator evidence differs" >&2; exit 2; }
    mkdir "$ATTEMPT0"
    mv "$OUT/canary-execution-metadata.json" \
      "$ATTEMPT0/canary-execution-metadata.json"
    mv "$OUT/canary-object-metadata.json" \
      "$ATTEMPT0/canary-object-metadata.json"
    sha256sum "$ATTEMPT0/canary-execution-metadata.json" \
      "$ATTEMPT0/canary-object-metadata.json" > "$ATTEMPT0/metadata.sha256"
    printf '%s\n' \
      'disposition=local-validator-awk-quoting-failure' \
      "execution=$CANARY_EXEC" \
      'canary_rerun=false' \
      'cloud_execution_terminal_success=true' \
      'object_present=true' \
      'object_content_inspected=false' \
      'effect_fields_inspected=false' \
      "original_validator_sha256=$VALIDATOR_SHA" \
      "repair_protocol_sha256=$PROTOCOL_SHA" \
      "awk_wrapper_sha256=$WRAPPER_SHA" \
      > "$ATTEMPT0/receipt.txt"
    sha256sum "$ATTEMPT0/metadata.sha256" "$ATTEMPT0/receipt.txt" \
      > "$ATTEMPT0/attempt.sha256"
  else
    [ -s "$ATTEMPT0/receipt.txt" ] && [ -s "$ATTEMPT0/attempt.sha256" ] && \
      [ ! -e "$OUT/canary-execution-metadata.json" ] && \
      [ ! -e "$OUT/canary-object-metadata.json" ] || {
      echo "ABORT: ATLAS repair5 archived validator attempt differs" >&2; exit 2; }
  fi
  PATH="$WRAPPER_DIR:$PATH" bash "$VALIDATOR"
else
  [ -s "$OUT/canary-completion.txt" ] && [ -s "$OUT/canary.sha256" ] && \
    [ -s "$OUT/canary-execution-metadata.json" ] && \
    [ -s "$OUT/canary-object-metadata.json" ] && \
    [ -s "$ATTEMPT0/receipt.txt" ] && [ -s "$ATTEMPT0/attempt.sha256" ] || {
    echo "ABORT: ATLAS repair5 resumed validator state differs" >&2; exit 2; }
fi

"$ROOT/.venv/bin/python" - "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" "$OUT/canary-object-metadata.json" \
  "$CANARY_EXEC" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

completion_path, execution_path, object_path = map(Path, sys.argv[1:4])
expected_execution = sys.argv[4]
completion = dict(
    line.split("=", 1)
    for line in completion_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
execution = json.loads(execution_path.read_text(encoding="utf-8"))
obj = json.loads(object_path.read_text(encoding="utf-8"))
if completion.get("status") != "True" or \
        completion.get("disposition") != "real-path-canary-passes" or \
        completion.get("execution") != expected_execution or \
        completion.get("cell") != "2023-1" or \
        completion.get("remaining_cells_released") != "false" or \
        completion.get("object_content_inspected") != "false" or \
        completion.get("effect_fields_inspected") != "false":
    raise SystemExit("ABORT: repaired ATLAS canary receipt differs")
status = execution.get("status", {})
completed = [
    value for value in status.get("conditions", [])
    if value.get("type") == "Completed"
]
if execution.get("metadata", {}).get("name") != expected_execution or \
        len(completed) != 1 or completed[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or \
        not str(obj.get("generation", "")).isdigit() or int(obj.get("size", 0)) <= 0:
    raise SystemExit("ABORT: repaired ATLAS canary metadata differs")
if completion.get("execution_metadata_sha256") != \
        sha256(execution_path.read_bytes()).hexdigest() or \
        completion.get("object_metadata_sha256") != \
        sha256(object_path.read_bytes()).hexdigest():
    raise SystemExit("ABORT: repaired ATLAS canary hashes differ")
PY

PREFIX=$(/usr/bin/awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
IMAGE=$(/usr/bin/awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(/usr/bin/awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")
GRID_COMMAND_SHA=$(printf '%s' "$GRID_COMMAND" | sha256sum | /usr/bin/awk '{print $1}')
[ "$GRID_COMMAND_SHA" = \
    "$(/usr/bin/awk -F= '$1=="grid_command_sha256" {print $2}' "$MANIFEST")" ] || {
  echo "ABORT: ATLAS repair5 rendered grid command differs" >&2; exit 2; }
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    JOB="atlas-md-s${SEASON}-w${WEEK}-r5"
    URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
    EXISTING_ROW=$(/usr/bin/awk -v s="$SEASON" -v w="$WEEK" \
      '$1==s && $2==w {print}' "$EXECUTIONS")
    if [ -n "$EXISTING_ROW" ]; then
      [ "$(printf '%s\n' "$EXISTING_ROW" | wc -l)" = 1 ] || {
        echo "ABORT: duplicate ATLAS repair5 ledger cell $SEASON-$WEEK" >&2; exit 2; }
      read -r _ _ LEDGER_JOB EXEC LEDGER_URI <<< "$EXISTING_ROW"
      [ "$LEDGER_JOB" = "$JOB" ] && [ "$LEDGER_URI" = "$URI" ] || {
        echo "ABORT: resumed ATLAS repair5 ledger identity differs" >&2; exit 2; }
      continue
    fi

    EXISTING=$(gcloud run jobs executions list --job "$JOB" \
      --project "$PROJECT" --region "$REGION" \
      --format='value(metadata.name)' 2>/dev/null || true)
    if [ -z "$EXISTING" ]; then
      gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
        --image "$IMAGE" --command python \
        --args=-c,"$GRID_COMMAND",--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
        --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
        --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
        --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
      EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --format='value(metadata.name)')
    else
      [ "$(printf '%s\n' "$EXISTING" | wc -l)" = 1 ] || {
        echo "ABORT: ATLAS repair5 job has multiple executions: $JOB" >&2; exit 2; }
      EXEC=$EXISTING
      TMP_META=$(mktemp "$OUT/.resume-execution-${SEASON}-${WEEK}.XXXXXX.json")
      gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
        --region "$REGION" --format=json > "$TMP_META"
      "$ROOT/.venv/bin/python" - "$TMP_META" "$EXEC" "$JOB" "$URI" \
        "$SEASON" "$WEEK" "$IMAGE" "$CODE_SHA" "$GRID_COMMAND" \
        "$SERVICE_ACCOUNT" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
execution, job, uri, season, week, image, code_sha, command, account = sys.argv[2:]
value = json.loads(path.read_text(encoding="utf-8"))
spec = value.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if value.get("metadata", {}).get("name") != execution or \
        not execution.startswith(job + "-") or spec.get("parallelism") != 1 or \
        spec.get("taskCount") != 1 or len(containers) != 1:
    raise SystemExit("ABORT: pre-existing ATLAS repair5 execution identity differs")
container = containers[0]
env = {row.get("name"): str(row.get("value", "")) for row in container.get("env", [])}
expected_args = [
    "-c", command, "--season", season, "--week", week, "--output-uri", uri,
]
if container.get("image") != image or container.get("command") != ["python"] or \
        container.get("args") != expected_args or \
        env != {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image} or \
        container.get("resources", {}).get("limits") != {"cpu": "8", "memory": "32Gi"} or \
        task.get("maxRetries") != 0 or str(task.get("timeoutSeconds")) != "43200" or \
        task.get("serviceAccountName") != account:
    raise SystemExit("ABORT: pre-existing ATLAS repair5 execution contract differs")
PY
      mv "$TMP_META" "$OUT/resumed-execution-${SEASON}-${WEEK}-metadata.json"
    fi
    [ -n "$EXEC" ] || {
      echo "ABORT: ATLAS repair5 execution identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
      | tee -a "$EXECUTIONS"
  done
done

"$ROOT/.venv/bin/python" - "$EXECUTIONS" "$PREFIX" <<'PY'
from pathlib import Path
import sys

rows = [line.split() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()]
prefix = sys.argv[2]
expected = {(str(s), str(w)) for s in (2023, 2024, 2025) for w in range(1, 19)}
if len(rows) != 54 or any(len(row) != 5 for row in rows) or \
        {(row[0], row[1]) for row in rows} != expected or \
        len({row[3] for row in rows}) != 54:
    raise SystemExit("ABORT: resumed ATLAS repair5 grid is not exact 54")
for season, week, job, execution, uri in rows:
    if job != f"atlas-md-s{season}-w{week}-r5" or \
            not execution.startswith(job + "-") or \
            uri != f"{prefix}/slate-{season}-{week}.json":
        raise SystemExit("ABORT: resumed ATLAS repair5 grid identity differs")
PY

RESUME_SHA=$(sha256sum "$ROOT/scripts/resume_atlas_repair5_after_canary_validator_quoting.sh" \
  | /usr/bin/awk '{print $1}')
ATTEMPT0_RECEIPT_SHA=$(sha256sum "$ATTEMPT0/receipt.txt" | /usr/bin/awk '{print $1}')
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' 'released_after_canary=53' \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | /usr/bin/awk '{print $1}')" \
  "original_canary_validator_sha256=$VALIDATOR_SHA" \
  "canary_validator_repair_protocol_sha256=$PROTOCOL_SHA" \
  "canary_validator_awk_wrapper_sha256=$WRAPPER_SHA" \
  "canary_validator_resume_sha256=$RESUME_SHA" \
  "canary_validator_attempt0_receipt_sha256=$ATTEMPT0_RECEIPT_SHA" \
  'canary_rerun=false' 'object_content_inspected=false' \
  'effect_fields_inspected=false' > "$OUT/grid-release.pending.txt"
mv "$OUT/grid-release.pending.txt" "$OUT/grid-release.txt"
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"
sha256sum "$PROTOCOL" "$WRAPPER" \
  "$ROOT/scripts/resume_atlas_repair5_after_canary_validator_quoting.sh" \
  "$ATTEMPT0/attempt.sha256" "$OUT/canary-completion.txt" \
  "$OUT/grid-release.txt" > "$OUT/validator-repair.sha256"
echo "ATLAS_MATCHED_DIVERSITY_REPAIR5_GRID_RESUMED $RUN_ID"
