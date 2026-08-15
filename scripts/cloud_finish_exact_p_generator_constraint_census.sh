#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260815-exact-p-generator-constraint-census-v1
OUT="$ROOT/reports/exact-p-generator-census-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: exact-P census manifest/execution is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable exact-P census report already exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: exact-P census execution is not successful ($STATE)" >&2; exit 1; }
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json
import math
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
expected = {
    "protocol_sha256": manifest["protocol_sha256"],
    "manifest_sha256": manifest["forensic_manifest_sha256"],
    "prelock_row_hash": manifest["prelock_row_hash"],
    "analysis_code_sha": manifest["code_sha"],
    "analysis_image": manifest["image"],
}
for key, value in expected.items():
    if report.get(key) != value:
        raise SystemExit(f"ABORT: exact-P census {key} differs")
if report.get("protocol_id") != manifest.get("run_id") or \
        report.get("scope") != "phase-s-cbwu-54" or \
        report.get("slates") != 54 or len(report.get("records", [])) != 54:
    raise SystemExit("ABORT: exact-P census identity/scope differs")
if report.get("uses_candidate_or_lineup_scores") is not False or \
        report.get("production_change_licensed") is not False or \
        report.get("historical_arm_licensed") is not False:
    raise SystemExit("ABORT: exact-P census consequence differs")
allowed = {
    "native-generation-search-dominant",
    "fixed-budget-admission-material",
    "specific-family-structural-exclusion-material",
    "mixed",
    "invalid-or-inconclusive",
}
if report.get("disposition") not in allowed:
    raise SystemExit("ABORT: exact-P census disposition differs")
loss = report.get("loss_stage_counts", {})
if set(loss) != {
    "native_generation_search", "fixed_budget_admission", "invalid_retained"
} or sum(int(value) for value in loss.values()) != 54:
    raise SystemExit("ABORT: exact-P census loss counts differ")
families = {"lev", "boom", "epi", "qbvar", "game", "dark"}
shares = report.get("family_primary_budget_share", {})
if set(shares) != families or not math.isclose(
        sum(float(value) for value in shares.values()), 1.0,
        rel_tol=0.0, abs_tol=1e-12,
) or set(report.get("family_statically_incapable_slates", {})) != families:
    raise SystemExit("ABORT: exact-P census family book differs")
keys = {(int(row["season"]), int(row["week"])) for row in report["records"]}
expected_keys = {
    (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
}
if keys != expected_keys or any(
        row.get("exact_p_in_retained_cbwu") for row in report["records"]
):
    raise SystemExit("ABORT: exact-P census slate/retained invariant differs")
print(
    "EXACT_P_CENSUS_VALIDATED",
    report["disposition"],
    json.dumps(loss, sort_keys=True),
)
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" "$MANIFEST" > "$OUT/attestation.sha256"
echo "EXACT_P_CENSUS_HARVESTED $EXEC"
