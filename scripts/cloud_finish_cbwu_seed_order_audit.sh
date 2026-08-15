#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/cbwu-seed-order-runs/20260815-cbwu-seed-order-scorefree-v1"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: CBWU manifest/execution is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable CBWU report already exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: CBWU execution is not successful ($STATE)" >&2; exit 1; }
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
    raise SystemExit("ABORT: CBWU report identity differs")
if report.get("uses_realized_outcomes") is not False or \
        manifest.get("uses_realized_outcomes") != "false":
    raise SystemExit("ABORT: CBWU report is not outcome-free")
expected_panels = manifest.get("source_panels", "").split(",")
if report.get("source_panels") != expected_panels or \
        report.get("forensic_manifest_sha256") != \
        manifest.get("forensic_manifest_sha256"):
    raise SystemExit("ABORT: CBWU source identity differs")
if len(report.get("source_artifacts", [])) != 270 or \
        len(report.get("slates", [])) != 54:
    raise SystemExit("ABORT: CBWU source/slate coverage differs")
for slate in report["slates"]:
    if slate.get("uses_realized_outcomes") is not False or \
            len(slate.get("rotations", [])) != 5:
        raise SystemExit("ABORT: CBWU slate rotation contract differs")
    budgets = {row.get("candidate_budget") for row in slate["rotations"]}
    if len(budgets) != 1 or next(iter(budgets), 0) <= 0:
        raise SystemExit("ABORT: CBWU fixed candidate budget differs")
aggregate = report.get("aggregate", {})
allowed = {
    "cbwu-order-invariant", "cbwu-order-sensitive-requires-repair",
}
if aggregate.get("slates") != 54 or \
        aggregate.get("cyclic_comparisons") != 216 or \
        aggregate.get("disposition") not in allowed:
    raise SystemExit("ABORT: CBWU aggregate contract differs")
if bool(aggregate.get("order_invariant")) != (
    aggregate.get("disposition") == "cbwu-order-invariant"
):
    raise SystemExit("ABORT: CBWU disposition is inconsistent")
if "historically best" in str(report.get("consequence", "")).lower():
    pass
elif "historically favorable" not in str(report.get("consequence", "")).lower():
    raise SystemExit("ABORT: CBWU consequence restriction is missing")
print(
    "CBWU_SEED_ORDER_VALIDATED",
    aggregate["disposition"],
    f"selected_jaccard_min={aggregate['selected_jaccard']['minimum']:.6f}",
)
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "CBWU_SEED_ORDER_HARVESTED $EXEC"
