#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/exact-n-scorefree-runs/20260815-exact-n-scorefree-v1"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: exact-N receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution.json" ] || {
  echo "ABORT: immutable exact-N evidence exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
EXEC_TMP=$(mktemp "$OUT/.execution.XXXXXX.json")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$EXEC_TMP" "$TMP"' EXIT
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$EXEC_TMP"
"$ROOT/.venv/bin/python" - "$EXEC_TMP" "$MANIFEST" "$EXEC" <<'PY'
import json
import sys

execution = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
if execution.get("metadata", {}).get("name") != sys.argv[3]:
    raise SystemExit("ABORT: exact-N execution name differs")
status = execution.get("status", {})
completed = [
    row for row in status.get("conditions", [])
    if row.get("type") == "Completed"
]
if len(completed) != 1 or completed[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or \
        not status.get("completionTime"):
    raise SystemExit("ABORT: exact-N execution is not terminal successful")
spec = execution.get("spec", {})
template = spec.get("template", {}).get("spec", {})
containers = template.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: exact-N execution task shape differs")
container = containers[0]
if container.get("image") != manifest.get("image") or \
        container.get("command") != ["python"] or \
        container.get("args") != [
            "scripts/run_exact_n_scorefree.py", "--output-uri",
            manifest.get("output_uri"),
        ]:
    raise SystemExit("ABORT: exact-N execution image/command differs")
env = {row.get("name"): str(row.get("value", ""))
       for row in container.get("env", [])}
if env != {
    "CODE_SHA": manifest.get("code_sha"),
    "ANALYSIS_IMAGE": manifest.get("image"),
}:
    raise SystemExit("ABORT: exact-N execution environment differs")
if container.get("resources", {}).get("limits") != {
    "cpu": "8", "memory": "16Gi",
} or template.get("maxRetries") != 0 or \
        str(template.get("timeoutSeconds")) != "14400" or \
        template.get("serviceAccountName") != (
            "817589974517-compute@developer.gserviceaccount.com"
        ):
    raise SystemExit("ABORT: exact-N resources/account differ")
print("EXACT_N_EXECUTION_METADATA_VALIDATED", sys.argv[3])
PY
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json
import math
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
for key in (
    "version", "protocol_sha256", "source_amendment_sha256",
    "cbwu_oi_scorefree_report_sha256", "forensic_manifest_sha256",
):
    if str(r.get(key)) != m.get(key):
        raise SystemExit(f"ABORT: exact-N {key} differs")
if r.get("code_sha") != m.get("code_sha") or r.get("image") != m.get("image"):
    raise SystemExit("ABORT: exact-N code/image differs")
expected_panels = m.get("source_panels", "").split(",")
sources = r.get("source_artifacts", [])
source_keys = {
    (str(row.get("panel_run_id")), int(row.get("season")), int(row.get("week")))
    for row in sources
}
if r.get("source_panels") != expected_panels or len(sources) != 270 or \
        len(source_keys) != 270:
    raise SystemExit("ABORT: exact-N source coverage differs")
for panel in expected_panels:
    if len({(season, week) for found, season, week in source_keys
            if found == panel}) != 54:
        raise SystemExit("ABORT: exact-N per-panel coverage differs")
preflight = r.get("source_preflight", {})
if preflight.get("panel_ids") != expected_panels or \
        preflight.get("artifact_count") != 270 or \
        preflight.get("slate_count") != 54 or \
        len(preflight.get("slates", [])) != 54:
    raise SystemExit("ABORT: exact-N shared preflight differs")
if r.get("local_source_receipts") != {
    "parent_protocol": m.get("protocol_sha256"),
    "source_amendment": m.get("source_amendment_sha256"),
    "cbwu_oi_report": m.get("cbwu_oi_scorefree_report_sha256"),
}:
    raise SystemExit("ABORT: exact-N local source receipts differ")
flags = {
    "uses_realized_outcomes": False,
    "candidate_or_lineup_scores_read": False,
    "selector_tuned": False,
    "historical_arm_licensed": False,
    "production_change_licensed": False,
}
if any(r.get(key) is not value for key, value in flags.items()):
    raise SystemExit("ABORT: exact-N evidence license differs")
rows = r.get("slates", [])
if len(rows) != 54 or len({
    (int(row["season"]), int(row["week"])) for row in rows
}) != 54:
    raise SystemExit("ABORT: exact-N slate population differs")
for row in rows:
    if row.get("uses_realized_outcomes") is not False or \
            row.get("n80_parity") is not True or \
            row.get("n80_legal") is not True or \
            len(row.get("n80_identities", [])) != 80 or \
            set(row.get("books", {})) != {"1", "3", "20", "40"}:
        raise SystemExit("ABORT: exact-N slate contract differs")
    for name, diagnostic in row["books"].items():
        n = int(name)
        if diagnostic.get("uses_realized_outcomes") is not False or \
                diagnostic.get("n_entries") != n or \
                diagnostic.get("treatment_legal") is not True or \
                len(diagnostic.get("treatment_identities", [])) != n or \
                diagnostic.get("production_context", {}).get("gating") is not False:
            raise SystemExit("ABORT: exact-N book contract differs")
result = r.get("result", {})
if result.get("version") != "exact-n-scorefree-panel-v1" or \
        result.get("uses_realized_outcomes") is not False or \
        result.get("slates") != 54 or \
        set(result.get("cardinalities", {})) != {"1", "3", "20", "40"}:
    raise SystemExit("ABORT: exact-N aggregate contract differs")
licensed = result.get("licensed_shadow_cardinalities", [])
if any(value not in (1, 3, 20, 40) for value in licensed):
    raise SystemExit("ABORT: exact-N licensed cardinality differs")
for name, row in result["cardinalities"].items():
    if row.get("entries") != int(name) or \
            set(row.get("conditions", {})) != {
                "exact_n_unique_and_legal", "primary_aggregate_improves",
                "primary_improves_at_least_three_blocks",
                "p194_retains_at_least_90pct", "n80_parity_all_slates",
            } or not all(math.isfinite(float(row[key])) for key in (
                "mean_control_primary_coverage",
                "mean_treatment_primary_coverage",
                "mean_primary_coverage_delta",
                "mean_control_p194_coverage",
                "mean_treatment_p194_coverage",
            )):
        raise SystemExit("ABORT: exact-N cardinality result differs")
    if bool(row.get("passes_scorefree_falsifier")) != all(
        row["conditions"].values()
    ):
        raise SystemExit("ABORT: exact-N disposition is inconsistent")
if "cannot score historical lineups" not in str(r.get("consequence", "")):
    raise SystemExit("ABORT: exact-N consequence is absent")
print("EXACT_N_SCOREFREE_VALIDATED", f"licensed={licensed}")
PY
mv "$EXEC_TMP" "$OUT/execution.json"
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "EXACT_N_SCOREFREE_HARVESTED $EXEC"
