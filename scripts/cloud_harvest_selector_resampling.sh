#!/bin/bash
# Harvest the frozen score-free selector world-resampling diagnostic.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/selector-resampling-runs/20260814-selector-resampling-v1"
MANIFEST="$OUT/manifest.txt"
EXEC_FILE="$OUT/analyzer_execution.txt"
[ -s "$MANIFEST" ] && [ -s "$EXEC_FILE" ] || {
  echo "ABORT: selector-resampling provenance is incomplete"; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/candidate-frequencies.json.gz" ] || {
  echo "ABORT: immutable selector-resampling output already exists"; exit 2; }

EXEC=$(tr -d '[:space:]' < "$EXEC_FILE")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: analyzer is not successful ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SELECTOR_RESAMPLING_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 20 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
LINE=$(grep '^SELECTOR_RESAMPLING_JSON=' "$OUT/raw_log.txt" | tail -1)
[ -n "$LINE" ] || { echo "ABORT: selector-resampling JSON marker absent"; exit 1; }
TMP_REPORT=$(mktemp "$OUT/.report.XXXXXX.json")
TMP=$(mktemp "$OUT/.candidate-frequencies.XXXXXX.gz")
trap 'rm -f "$TMP_REPORT" "$TMP"' EXIT
printf '%s' "${LINE#SELECTOR_RESAMPLING_JSON=}" \
  | "$ROOT/.venv/bin/python" -m json.tool > "$TMP_REPORT"

URI=$(awk -F= '$1=="frequency_artifact_uri" {print $2}' "$MANIFEST")
gcloud storage cp "$URI" "$TMP" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP_REPORT" "$MANIFEST" "$TMP" <<'PY'
import gzip
import hashlib
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
if not report.get("mechanical_passes") or report.get("failures"):
    raise SystemExit("ABORT: selector-resampling mechanical audit failed")
checks = {
    "source_panel": manifest.get("source_panel"),
    "expected_code_sha": manifest.get("source_code_sha"),
}
for field, expected in checks.items():
    if report.get(field) != expected:
        raise SystemExit(f"ABORT: report {field} differs from manifest")
if report.get("reads_realized_outcomes") is not False:
    raise SystemExit("ABORT: selector diagnostic is not outcome-blind")
artifact = report.get("frequency_artifact", {})
payload = open(sys.argv[3], "rb").read()
if artifact.get("uri") != manifest.get("frequency_artifact_uri") or \
        hashlib.sha256(payload).hexdigest() != artifact.get("sha256") or \
        len(payload) != artifact.get("compressed_bytes"):
    raise SystemExit("ABORT: frequency artifact identity differs")
decoded = json.loads(gzip.decompress(payload))
if decoded.get("source_panel") != manifest.get("source_panel") or \
        decoded.get("reads_realized_outcomes") is not False or \
        len(decoded.get("slates", [])) != 54:
    raise SystemExit("ABORT: frequency artifact contract differs")
if any(len(slate.get("candidate_frequencies", [])) !=
       int(slate.get("candidate_count", -1)) for slate in decoded["slates"]):
    raise SystemExit("ABORT: frequency artifact candidate rows differ")
result = report.get("result", {})
if result.get("overall", {}).get("slates") != 54 or \
        set(result.get("by_season", {})) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: selector summary slate coverage differs")
print(
    "SELECTOR_RESAMPLING_VALIDATED",
    f"band={result['overall']['stability_band']}",
    f"overlap={result['overall']['mean_pairwise_overlap']:.3f}",
)
PY
mv "$TMP_REPORT" "$OUT/report.json"
mv "$TMP" "$OUT/candidate-frequencies.json.gz"
trap - EXIT
echo "SELECTOR_RESAMPLING_HARVESTED $EXEC"
