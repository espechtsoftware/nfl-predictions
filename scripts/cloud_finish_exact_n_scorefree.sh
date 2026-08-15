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
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable exact-N report exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: exact-N execution is not successful ($STATE)" >&2; exit 1; }
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
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
if r.get("source_panels") != m.get("source_panels", "").split(",") or \
        len(r.get("source_artifacts", [])) != 270:
    raise SystemExit("ABORT: exact-N source coverage differs")
preflight = r.get("source_preflight", {})
if preflight.get("artifact_count") != 270 or \
        preflight.get("slate_count") != 54 or \
        len(preflight.get("slates", [])) != 54:
    raise SystemExit("ABORT: exact-N shared preflight differs")
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
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "EXACT_N_SCOREFREE_HARVESTED $EXEC"
