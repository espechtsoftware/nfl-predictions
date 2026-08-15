#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_finish_exact_p_generator_census_source1.sh <preflight-2023|full>

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260815-exact-p-generator-constraint-census-v1-source1
MODE=${1:-}
case "$MODE" in
  preflight-2023) STAGE=preflight-2023 ;;
  full) STAGE=full-source1 ;;
  *) echo "ABORT: mode must be preflight-2023 or full" >&2; exit 2 ;;
esac
OUT="$ROOT/reports/exact-p-generator-census-runs/$RUN_ID/$STAGE"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: exact-P census source1 receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable exact-P census source1 report exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: exact-P census source1 execution is not successful ($STATE)" >&2; exit 1; }
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
for key in ("mode", "protocol_sha256", "repair_protocol_sha256", "manifest_sha256"):
    if str(r.get(key)) != m.get(key):
        raise SystemExit(f"ABORT: source1 {key} differs")
for key, mkey in (("analysis_code_sha", "code_sha"), ("analysis_image", "image")):
    if str(r.get(key)) != m.get(mkey):
        raise SystemExit(f"ABORT: source1 {key} differs")
source = r.get("corrected_identity_source", {})
if (
    source.get("uri") != m.get("identity_uri")
    or str(source.get("generation")) != m.get("identity_generation")
    or source.get("sha256") != m.get("identity_sha256")
):
    raise SystemExit("ABORT: source1 identity receipt differs")
if r.get("mode") == "preflight-2023":
    required = (
        "exact_p_source_resolved", "all_exact_p_rosters_legal",
        "native_books_validated", "family_labels_validated",
        "retained_cbwu_reproduced", "outcome_columns_denied",
    )
    denied = (
        "membership_or_distance_values_persisted", "candidate_yield_persisted",
        "loss_stage_or_disposition_persisted", "scientific_result_licensed",
        "production_change_licensed",
    )
    if (
        r.get("slates") != 18
        or any(r.get(key) is not True for key in required)
        or any(r.get(key) is not False for key in denied)
        or "records" in r
        or "disposition" in r
    ):
        raise SystemExit("ABORT: source1 preflight contract differs")
else:
    if (
        r.get("slates") != 54
        or r.get("uses_candidate_or_lineup_scores") is not False
        or r.get("production_change_licensed") is not False
    ):
        raise SystemExit("ABORT: source1 full score denial differs")
    loss = r.get("loss_stage_counts", {})
    if (
        set(loss) != {
            "native_generation_search", "fixed_budget_admission", "invalid_retained",
        }
        or sum(int(value) for value in loss.values()) != 54
        or len(r.get("records", [])) != 54
    ):
        raise SystemExit("ABORT: source1 full loss partition differs")
    allowed = {
        "native-generation-search-dominant", "fixed-budget-admission-material",
        "specific-family-structural-exclusion-material", "mixed",
        "invalid-or-inconclusive",
    }
    if r.get("disposition") not in allowed or any(
        row.get("exact_p_in_retained_cbwu") for row in r["records"]
    ):
        raise SystemExit("ABORT: source1 full disposition differs")
print("EXACT_P_GENERATOR_CENSUS_SOURCE1_VALIDATED", r["mode"], r["slates"])
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "EXACT_P_GENERATOR_CENSUS_SOURCE1_HARVESTED $EXEC"
