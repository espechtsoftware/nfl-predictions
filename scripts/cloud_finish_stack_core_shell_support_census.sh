#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-control-support-census-v1
OUT="$ROOT/reports/stack-core-shell-support-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
PRIMARY="$OUT/executions.txt"
RETRIES="$OUT/retry-executions.txt"
EXECUTIONS="$OUT/accepted-executions.txt"
CLASSIFICATION="$OUT/primary-attempt-classification.json"
RESOLUTION="$OUT/attempt-resolution.json"
RUNNER="$ROOT/scripts/run_stack_core_shell_support_census.py"
AGGREGATOR="$ROOT/scripts/aggregate_stack_core_shell_support_census.py"
SOURCES="$ROOT/scripts/stack_core_shell_sources.py"
CANARY="$ROOT/scripts/cloud_wait_stack_core_shell_support_canary.sh"
ATTEMPTS="$ROOT/scripts/manage_stack_core_shell_support_attempts.py"

for REQUIRED in "$MANIFEST" "$PRIMARY" "$RETRIES" "$EXECUTIONS" \
  "$CLASSIFICATION" "$RESOLUTION" "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" "$OUT/canary-object-metadata.json" \
  "$OUT/grid-release.txt" "$OUT/build-metadata.json" \
  "$OUT/queue-release.json"; do
  [ -f "$REQUIRED" ] || {
    echo "ABORT: stack-core/shell support receipt is incomplete: $REQUIRED" >&2
    exit 2
  }
done
[ "$(wc -l < "$PRIMARY")" = 54 ] && \
  [ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: stack-core/shell support execution grid differs" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/object-metadata" ] && [ ! -e "$OUT/shards" ] || {
  echo "ABORT: immutable stack-core/shell support harvest already exists" >&2
  exit 3
}

PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" "$ATTEMPTS" validate \
  --output-dir "$OUT"

"$ROOT/.venv/bin/python" - "$MANIFEST" "$OUT/build-metadata.json" \
  "$OUT/queue-release.json" "$RUNNER" "$AGGREGATOR" "$SOURCES" \
  "$CANARY" "$ATTEMPTS" "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" "$OUT/canary-object-metadata.json" \
  "$OUT/grid-release.txt" "$PRIMARY" "$RETRIES" "$EXECUTIONS" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

manifest_path, build_path, queue_path = map(Path, sys.argv[1:4])
runner, aggregator, sources, canary, attempts = map(Path, sys.argv[4:9])
canary_completion, canary_execution, canary_object, release = map(
    Path, sys.argv[9:13]
)
primary_path, retry_path, accepted_path = map(Path, sys.argv[13:16])
m = dict(
    line.split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
fixed = {
    "run_id": "20260816-stack-core-shell-control-support-census-v1",
    "output_prefix": (
        "gs://nfl-predictions-503414-raw/research/"
        "stack-core-shell-support-runs/"
        "20260816-stack-core-shell-control-support-census-v1"
    ),
    "protocol_sha256": (
        "edd13697fd3d7fc787d159c74d6e8280bf1b51517dcdbacc8337011a01cd5d46"
    ),
    "execution_protocol_sha256": (
        "d2e902611e070ef67c191dffd35d86fd0c81365126eb86dcae7b9640aede1cc3"
    ),
    "transfer_report_sha256": (
        "8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446"
    ),
    "cbwu_report_sha256": (
        "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
    ),
    "source_panels": (
        "20260815-atlas-money-worlds-r0-v1,"
        "20260815-atlas-money-worlds-r1-v1,"
        "20260815-atlas-money-worlds-r2-v1,"
        "20260815-atlas-money-worlds-r3-v1,"
        "20260815-atlas-money-worlds-r4-v1"
    ),
    "seasons": "2023,2024,2025", "weeks": "1-18", "slates": "54",
    "folds": "270", "cpu": "4", "memory": "16Gi",
    "timeout_seconds": "7200", "max_retries": "0",
    "aggregate_events_minimum_per_block": "540",
    "positive_slates_minimum_per_block": "41",
    "anchor_order": "230,220,210",
    "support_layers": "candidate,selected",
    "uses_realized_outcomes": "false", "effect_fields_inspected": "false",
    "treatment_constructed": "false", "production_change_licensed": "false",
    "historical_scoring_licensed": "false",
}
if any(m.get(key) != value for key, value in fixed.items()) or \
        not re.fullmatch(r"[0-9a-f]{40}", m.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", m.get("image", "")):
    raise SystemExit("ABORT: stack-core/shell manifest differs")
for key, path in (
    ("runner_sha256", runner), ("aggregator_sha256", aggregator),
    ("source_loader_sha256", sources), ("canary_validator_sha256", canary),
    ("attempt_manager_sha256", attempts),
):
    if m.get(key) != sha256(path.read_bytes()).hexdigest():
        raise SystemExit(f"ABORT: stack-core/shell implementation differs: {key}")

b = json.loads(build_path.read_text(encoding="utf-8"))
digest = m["image"].rsplit("@", 1)[1]
tag = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:"
    f"stack-shell-support-{m['code_sha'][:7]}"
)
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
required_steps = {
    "full-test-suite", "smoke-stack-core-shell-source-loader",
    "smoke-stack-core-shell-support-runner",
    "smoke-stack-core-shell-support-aggregator",
}
if m.get("build_metadata_sha256") != sha256(build_path.read_bytes()).hexdigest() or \
        b.get("id") != m.get("build_id") or b.get("status") != "SUCCESS" or \
        b.get("substitutions", {}).get("_IMAGE") != tag or \
        not any(
            row.get("name") == tag and row.get("digest") == digest
            for row in b.get("results", {}).get("images", [])
        ) or any(steps.get(name) != "SUCCESS" for name in required_steps):
    raise SystemExit("ABORT: stack-core/shell build receipt differs")

queue = json.loads(queue_path.read_text(encoding="utf-8"))
if m.get("queue_release_sha256") != sha256(queue_path.read_bytes()).hexdigest() or \
        queue.get("version") != "stack-core-shell-support-queue-release-v1" or \
        queue.get("branch") != m.get("queue_release_branch") or \
        queue.get("branch") not in {
            "preflight-failed-parity-closed", "repair5-valid-historical-closed",
            "repair5-failed-parity-closed",
        }:
    raise SystemExit("ABORT: stack-core/shell queue release differs")
for raw_path, digest_value in queue.get("bindings", {}).items():
    path = Path(raw_path)
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != digest_value:
        raise SystemExit("ABORT: stack-core/shell queue binding differs")

c = dict(
    line.split("=", 1)
    for line in canary_completion.read_text().splitlines() if "=" in line
)
r = dict(line.split("=", 1) for line in release.read_text().splitlines() if "=" in line)
if c.get("status") != "True" or c.get("disposition") != "real-path-canary-passes" or \
        c.get("cell") != "2023-1" or c.get("remaining_cells_released") != "false" or \
        c.get("object_content_inspected") != "false" or \
        c.get("effect_fields_inspected") != "false" or \
        c.get("treatment_constructed") != "false" or \
        c.get("execution_metadata_sha256") != sha256(canary_execution.read_bytes()).hexdigest() or \
        c.get("object_metadata_sha256") != sha256(canary_object.read_bytes()).hexdigest() or \
        r.get("primary_executions") != "54" or r.get("released_after_canary") != "53" or \
        r.get("canary_completion_sha256") != sha256(canary_completion.read_bytes()).hexdigest():
    raise SystemExit("ABORT: stack-core/shell canary/grid release differs")

def ledger(path, fields):
    rows = [line.split() for line in path.read_text().splitlines()]
    if any(len(row) != fields for row in rows):
        raise SystemExit("ABORT: stack-core/shell execution ledger differs")
    return rows
primary, retries, accepted = (
    ledger(primary_path, 5), ledger(retry_path, 6), ledger(accepted_path, 5)
)
grid = {(str(s), str(w)) for s in (2023, 2024, 2025) for w in range(1, 19)}
if len(primary) != 54 or len(accepted) != 54 or \
        {(row[0], row[1]) for row in primary} != grid or \
        {(row[0], row[1]) for row in accepted} != grid or \
        len({row[3] for row in accepted}) != 54:
    raise SystemExit("ABORT: stack-core/shell accepted population differs")
PY

mkdir -p "$OUT/execution-metadata.pending" \
  "$OUT/object-metadata.pending" "$OUT/shards.pending"
while read -r SEASON WEEK JOB EXEC URI; do
  LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
    --region "$REGION" --format='value(metadata.name)' | sort)
  EXPECTED=$({
    awk -v job="$JOB" '$3==job {print $4}' "$PRIMARY"
    awk -v job="$JOB" '$3==job {print $5}' "$RETRIES"
  } | sort)
  [ "$LISTED" = "$EXPECTED" ] || {
    echo "ABORT: stack-core/shell job attempt population differs: $JOB" >&2
    exit 2
  }
  META="$OUT/execution-metadata.pending/${EXEC}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  OBJECT="$OUT/object-metadata.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
    > "$OBJECT"
  "$ROOT/.venv/bin/python" - "$META" "$OBJECT" "$MANIFEST" \
    "$EXEC" "$SEASON" "$WEEK" "$JOB" "$URI" <<'PY'
import json
import sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
o = json.load(open(sys.argv[2], encoding="utf-8"))
m = dict(
    line.split("=", 1) for line in open(sys.argv[3], encoding="utf-8") if "=" in line
)
execution, season, week, job, uri = sys.argv[4:]
if x.get("metadata", {}).get("name") != execution:
    raise SystemExit("ABORT: stack-core/shell execution name differs")
status = x.get("status", {})
done = [row for row in status.get("conditions", []) if row.get("type") == "Completed"]
if len(done) != 1 or done[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or not status.get("completionTime"):
    raise SystemExit("ABORT: stack-core/shell accepted execution is not successful")
spec = x.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
expected_args = [
    "scripts/run_stack_core_shell_support_census.py", "--season", season,
    "--week", week, "--output-uri", uri,
]
env = {
    row.get("name"): str(row.get("value", ""))
    for row in containers[0].get("env", [])
} if len(containers) == 1 else {}
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1 or containers[0].get("image") != m["image"] or \
        containers[0].get("command") != ["python"] or \
        containers[0].get("args") != expected_args or env != {
            "CODE_SHA": m["code_sha"], "ANALYSIS_IMAGE": m["image"],
        } or containers[0].get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi",
        } or task.get("maxRetries") != 0 or \
        str(task.get("timeoutSeconds")) != "7200" or \
        task.get("serviceAccountName") != \
        "817589974517-compute@developer.gserviceaccount.com":
    raise SystemExit("ABORT: stack-core/shell accepted execution contract differs")
if not str(o.get("generation", "")).isdigit() or int(o.get("size", 0)) <= 0:
    raise SystemExit("ABORT: stack-core/shell output metadata differs")
PY
done < "$EXECUTIONS"

# Only after every accepted execution and object has passed do shard bytes move.
while read -r SEASON WEEK _JOB _EXEC URI; do
  SHARD="$OUT/shards.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - \
    "$OUT/object-metadata.pending/slate-${SEASON}-${WEEK}.json" "$SHARD" <<'PY'
import json
import sys
metadata = json.load(open(sys.argv[1], encoding="utf-8"))
raw = open(sys.argv[2], "rb").read()
if int(metadata.get("size", -1)) != len(raw):
    raise SystemExit("ABORT: stack-core/shell shard byte size differs")
json.loads(raw)
PY
done < "$EXECUTIONS"

mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/object-metadata.pending" "$OUT/object-metadata"
mv "$OUT/shards.pending" "$OUT/shards"
ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do
  ARGS+=(--shard-report "$SHARD")
done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$AGGREGATOR" \
  "${ARGS[@]}" --output-dir "$OUT"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(
    line.split("=", 1) for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
if r.get("version") != "stack-core-shell-control-support-report-v1" or \
        r.get("run_id") != m["run_id"] or r.get("uses_realized_outcomes") is not False or \
        r.get("effect_fields_inspected") is not False or \
        r.get("treatment_constructed") is not False or \
        r.get("production_change_licensed") is not False or \
        r.get("historical_scoring_licensed") is not False or \
        r.get("code_sha") != m["code_sha"] or r.get("analysis_image") != m["image"]:
    raise SystemExit("ABORT: stack-core/shell support report identity differs")
if r.get("mechanical") != {
    "seasons": [2023, 2024, 2025], "slates": 54, "heldout_folds": 270,
    "worlds_per_fold": 10000, "source_artifacts": 270, "all_valid": True,
}:
    raise SystemExit("ABORT: stack-core/shell support mechanics differ")
law = r.get("support_law", {})
if law != {
    "layers_required": ["candidate", "selected"],
    "aggregate_events_minimum_per_block": 540,
    "positive_slates_minimum_per_block": 41,
    "anchor_order": [230, 220, 210],
} or len(r.get("cells", [])) != 270:
    raise SystemExit("ABORT: stack-core/shell support law differs")
counts = r.get("counts_by_layer_and_block", {})
correlations = r.get("fold_correlation_by_layer_and_threshold", {})
required_distribution = {
    "events", "worlds", "positive_slates", "slates", "top_1_event_share",
    "top_3_event_share", "top_5_event_share", "top_10_event_share",
    "herfindahl", "effective_slates", "median_positive_events",
    "max_slate_events", "slate_counts",
}
for layer in ("candidate", "selected"):
    if set(counts.get(layer, {})) != {"R0", "R1", "R2", "R3", "R4"} or \
            set(correlations.get(layer, {})) != {"194", "210", "220", "230"}:
        raise SystemExit("ABORT: stack-core/shell support layer grid differs")
    for block in ("R0", "R1", "R2", "R3", "R4"):
        if set(counts[layer][block]) != {"194", "210", "220", "230"}:
            raise SystemExit("ABORT: stack-core/shell support threshold grid differs")
        for value in counts[layer][block].values():
            if set(value) != required_distribution or len(value["slate_counts"]) != 54:
                raise SystemExit("ABORT: stack-core/shell distribution fields differ")
    for value in correlations[layer].values():
        if len(value.get("pairs", [])) != 10 or \
                value.get("diagnostic_only") is not True or \
                value.get("folds_are_independent") is not False:
            raise SystemExit("ABORT: stack-core/shell correlation fields differ")
adequate = r.get("adequate_by_threshold", {})
anchor = r.get("selected_anchor")
expected = {
    230: "p230-supported-stack-core-shell-treatment-licensed",
    220: "p220-supported-stack-core-shell-treatment-licensed",
    210: "p210-supported-stack-core-shell-treatment-licensed",
    None: "terminal-insufficient-stack-core-shell-support",
}
if set(adequate) != {"230", "220", "210"} or \
        any(not isinstance(value, bool) for value in adequate.values()) or \
        anchor not in expected or r.get("disposition") != expected[anchor]:
    raise SystemExit("ABORT: stack-core/shell support disposition differs")
print("STACK_CORE_SHELL_SUPPORT_STRICTLY_VALIDATED", r["disposition"])
PY

PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" - "$OUT/report.json" \
  "$PREFIX/report.json" "$OUT/report-upload.json" <<'PY'
import json
import sys
from google.cloud import storage
from run_cbwu_seed_order_audit import _upload_create_only
raw = open(sys.argv[1], "rb").read()
receipt = _upload_create_only(
    storage.Client(project="nfl-predictions-503414"), sys.argv[2], raw,
)
open(sys.argv[3], "w", encoding="utf-8").write(
    json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
)
PY

sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT/report-upload.json" > "$OUT/report-upload.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort \
  > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/object-metadata/*.json | sort \
  > "$OUT/object-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$OUT/report.json")
ANCHOR=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; v=json.load(open(sys.argv[1]))["selected_anchor"]; print("none" if v is None else v)' \
  "$OUT/report.json")
ATTEMPT_DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$RESOLUTION")
printf '%s\n' \
  "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'slates=54' 'folds=270' 'source_artifacts=270' \
  "attempt_disposition=$ATTEMPT_DISPOSITION" \
  "primary_executions_sha256=$(sha256sum "$PRIMARY" | awk '{print $1}')" \
  "retry_executions_sha256=$(sha256sum "$RETRIES" | awk '{print $1}')" \
  "accepted_executions_sha256=$(sha256sum "$EXECUTIONS" | awk '{print $1}')" \
  "attempt_resolution_sha256=$(sha256sum "$RESOLUTION" | awk '{print $1}')" \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | awk '{print $1}')" \
  "grid_release_sha256=$(sha256sum "$OUT/grid-release.txt" | awk '{print $1}')" \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'treatment_constructed=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' "selected_anchor=$ANCHOR" \
  "disposition=$DISPOSITION" > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "STACK_CORE_SHELL_SUPPORT_HARVESTED $RUN_ID $DISPOSITION"
