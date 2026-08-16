#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: ATLAS manifest/execution is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable ATLAS report already exists" >&2; exit 2; }
[ ! -e "$OUT/execution.json" ] || {
  echo "ABORT: immutable ATLAS execution receipt already exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
EXEC_TMP=$(mktemp "$OUT/.execution.XXXXXX.json")
REPORT_TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$EXEC_TMP" "$REPORT_TMP"' EXIT
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
    raise SystemExit("ABORT: ATLAS execution name differs")
status = execution.get("status", {})
completed = [
    row for row in status.get("conditions", [])
    if row.get("type") == "Completed"
]
if len(completed) != 1 or completed[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or \
        not status.get("completionTime"):
    raise SystemExit("ABORT: ATLAS execution is not terminal successful")
spec = execution.get("spec", {})
template = spec.get("template", {}).get("spec", {})
containers = template.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: ATLAS execution task shape differs")
container = containers[0]
if container.get("image") != manifest.get("image") or \
        container.get("command") != ["python"] or \
        container.get("args") != [
            "scripts/run_atlas_world_ranking.py", "--output-uri",
            manifest.get("output_uri"),
        ]:
    raise SystemExit("ABORT: ATLAS execution image/command differs")
env = {row.get("name"): row.get("value") for row in container.get("env", [])}
if env != {
    "CODE_SHA": manifest.get("code_sha"),
    "ANALYSIS_IMAGE": manifest.get("image"),
}:
    raise SystemExit("ABORT: ATLAS execution environment differs")
if container.get("resources", {}).get("limits") != {
    "cpu": "8", "memory": "32Gi",
} or template.get("maxRetries") != 0 or \
        str(template.get("timeoutSeconds")) != "21600" or \
        template.get("serviceAccountName") != (
            "817589974517-compute@developer.gserviceaccount.com"
        ):
    raise SystemExit("ABORT: ATLAS execution resources/account differ")
print("ATLAS_EXECUTION_METADATA_VALIDATED", sys.argv[3])
PY
gcloud storage cp "$OUTPUT_URI" "$REPORT_TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$REPORT_TMP" "$MANIFEST" <<'PY'
import json
import math
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
if report.get("version") != manifest.get("version") or \
        report.get("code_sha") != manifest.get("code_sha") or \
        report.get("image") != manifest.get("image"):
    raise SystemExit("ABORT: ATLAS report identity differs")
if report.get("uses_realized_outcomes") is not False or \
        manifest.get("uses_realized_outcomes") != "false":
    raise SystemExit("ABORT: ATLAS report is not outcome-free")
expected_panels = manifest.get("source_panels", "").split(",")
if report.get("source_panels") != expected_panels or \
        report.get("forensic_manifest_sha256") != \
        manifest.get("forensic_manifest_sha256"):
    raise SystemExit("ABORT: ATLAS source identity differs")
if report.get("production_constraints") != {
    "salary_floor": 49000,
    "salary_cap": 50000,
    "qb_stack_min": 2,
    "bring_back_min": 1,
    "forbid_rb_vs_dst": True,
    "forbid_two_rb_same_team": True,
}:
    raise SystemExit("ABORT: ATLAS production constraints differ")
sources = report.get("source_artifacts", [])
diagnostics = report.get("diagnostics", [])
if len(sources) != 270 or len(diagnostics) != 270:
    raise SystemExit("ABORT: ATLAS source/diagnostic coverage differs")
source_keys = {
    (int(row["seed"]), str(row["panel_run_id"]),
     int(row["season"]), int(row["week"]))
    for row in sources
}
diagnostic_keys = {
    (int(row["seed"]), str(row["panel_run_id"]),
     int(row["season"]), int(row["week"]))
    for row in diagnostics
}
if len(source_keys) != 270 or source_keys != diagnostic_keys:
    raise SystemExit("ABORT: ATLAS source/diagnostic keys differ")
for seed in range(5):
    if len({(season, week) for found, _, season, week in source_keys
            if found == seed}) != 54:
        raise SystemExit("ABORT: ATLAS per-seed slate coverage differs")
expected_relaxed = [
    "salary", "team", "minimum-games", "stack", "rb-anticorrelation",
]
for diagnostic in diagnostics:
    if diagnostic.get("uses_realized_outcomes") is not False:
        raise SystemExit("ABORT: ATLAS diagnostic is outcome-facing")
    if diagnostic.get("proxy") != "classic-roster-slot-upper-bound" or \
            diagnostic.get("worlds") != 10000 or \
            diagnostic.get("selected_worlds") != 40 or \
            diagnostic.get("relaxed_constraints") != expected_relaxed:
        raise SystemExit("ABORT: ATLAS diagnostic contract differs")
    union = diagnostic.get("exact_union_worlds")
    exact = diagnostic.get("exact_world_results", {})
    if not isinstance(union, int) or not 40 <= union <= 80 or len(exact) != union:
        raise SystemExit("ABORT: ATLAS exact-world union differs")
gate = report.get("gate", {})
conditions = gate.get("conditions", {})
expected_conditions = {
    "aggregate_mean_improves",
    "at_least_three_seed_means_improve",
    "aggregate_q25_nonworse",
    "roster_diversity_at_least_80pct",
    "stack_core_diversity_at_least_80pct",
    "dominant_game_diversity_at_least_80pct",
}
if gate.get("version") != "atlas-world-ranking-scorefree-gate-v1" or \
        gate.get("uses_realized_outcomes") is not False or \
        gate.get("rows") != 270 or gate.get("slates") != 54 or \
        set(conditions) != expected_conditions:
    raise SystemExit("ABORT: ATLAS score-free gate contract differs")
numeric = [gate.get("aggregate_mean_delta"), gate.get("aggregate_q25_delta")]
numeric.extend(gate.get("per_seed_mean_delta", {}).values())
numeric.extend(gate.get("mean_diversity_ratios", {}).values())
if len(gate.get("per_seed_mean_delta", {})) != 5 or \
        not all(math.isfinite(float(value)) for value in numeric):
    raise SystemExit("ABORT: ATLAS aggregate metrics are invalid")
if bool(gate.get("passes_scorefree_falsifier")) != all(conditions.values()):
    raise SystemExit("ABORT: ATLAS gate disposition is inconsistent")
if "cannot promote" not in str(report.get("consequence", "")).lower():
    raise SystemExit("ABORT: ATLAS consequence restriction is missing")
print(
    "ATLAS_WORLD_RANKING_VALIDATED",
    f"passes={gate['passes_scorefree_falsifier']}",
    f"mean_delta={gate['aggregate_mean_delta']:.6f}",
)
PY
mv "$EXEC_TMP" "$OUT/execution.json"
mv "$REPORT_TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "ATLAS_WORLD_RANKING_HARVESTED $EXEC"
