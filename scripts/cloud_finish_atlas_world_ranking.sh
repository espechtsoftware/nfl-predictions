#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: ATLAS manifest/execution is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable ATLAS report already exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: ATLAS execution is not successful ($STATE)" >&2; exit 1; }
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json
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
if len(report.get("source_artifacts", [])) != 270 or \
        len(report.get("diagnostics", [])) != 270:
    raise SystemExit("ABORT: ATLAS source/diagnostic coverage differs")
for diagnostic in report["diagnostics"]:
    if diagnostic.get("uses_realized_outcomes") is not False:
        raise SystemExit("ABORT: ATLAS diagnostic is outcome-facing")
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
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "ATLAS_WORLD_RANKING_HARVESTED $EXEC"
