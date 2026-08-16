#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/cbwu-oi-selector-stability-runs/20260815-cbwu-oi-selector-stability-v1"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: selector-stability receipt is incomplete" >&2; exit 2; }
for target in report.json execution.json candidate-frequencies.json.gz; do
  [ ! -e "$OUT/$target" ] || {
    echo "ABORT: immutable selector-stability evidence exists: $target" >&2
    exit 2
  }
done
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
FREQUENCY_URI=$(awk -F= '$1=="frequency_uri" {print $2}' "$MANIFEST")
EXEC_TMP=$(mktemp "$OUT/.execution.XXXXXX.json")
REPORT_TMP=$(mktemp "$OUT/.report.XXXXXX.json")
FREQUENCY_TMP=$(mktemp "$OUT/.frequencies.XXXXXX.json.gz")
trap 'rm -f "$EXEC_TMP" "$REPORT_TMP" "$FREQUENCY_TMP"' EXIT

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
    raise SystemExit("ABORT: selector-stability execution name differs")
status = execution.get("status", {})
completed = [
    row for row in status.get("conditions", [])
    if row.get("type") == "Completed"
]
if len(completed) != 1 or completed[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or \
        not status.get("completionTime"):
    raise SystemExit("ABORT: selector-stability execution is not successful")
spec = execution.get("spec", {})
template = spec.get("template", {}).get("spec", {})
containers = template.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: selector-stability execution task shape differs")
container = containers[0]
if container.get("image") != manifest.get("image") or \
        container.get("command") != ["python"] or \
        container.get("args") != [
            "scripts/run_cbwu_oi_selector_stability.py", "--output-uri",
            manifest.get("output_uri"), "--frequency-uri",
            manifest.get("frequency_uri"),
        ]:
    raise SystemExit("ABORT: selector-stability image/command differs")
env = {row.get("name"): str(row.get("value", ""))
       for row in container.get("env", [])}
if env != {
    "CODE_SHA": manifest.get("code_sha"),
    "ANALYSIS_IMAGE": manifest.get("image"),
}:
    raise SystemExit("ABORT: selector-stability environment differs")
if container.get("resources", {}).get("limits") != {
    "cpu": "8", "memory": "32Gi",
} or template.get("maxRetries") != 0 or \
        str(template.get("timeoutSeconds")) != "21600" or \
        template.get("serviceAccountName") != (
            "817589974517-compute@developer.gserviceaccount.com"
        ):
    raise SystemExit("ABORT: selector-stability resources/account differ")
print("CBWU_OI_SELECTOR_STABILITY_EXECUTION_VALIDATED", sys.argv[3])
PY

gcloud storage cp "$OUTPUT_URI" "$REPORT_TMP" --project "$PROJECT" >/dev/null
gcloud storage cp "$FREQUENCY_URI" "$FREQUENCY_TMP" \
  --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$REPORT_TMP" "$MANIFEST" "$FREQUENCY_TMP" <<'PY'
import gzip
import hashlib
import json
import math
import re
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
frequency_bytes = open(sys.argv[3], "rb").read()
frequency = json.loads(gzip.decompress(frequency_bytes))
for key in (
    "version", "protocol_sha256", "cbwu_oi_scorefree_report_sha256",
    "forensic_manifest_sha256",
):
    if str(r.get(key)) != m.get(key):
        raise SystemExit(f"ABORT: selector-stability {key} differs")
if r.get("code_sha") != m.get("code_sha") or r.get("image") != m.get("image"):
    raise SystemExit("ABORT: selector-stability code/image differs")
expected_panels = m.get("source_panels", "").split(",")
sources = r.get("source_artifacts", [])
source_keys = {
    (str(row.get("panel_run_id")), int(row.get("season")), int(row.get("week")))
    for row in sources
}
if r.get("source_panels") != expected_panels or len(sources) != 270 or \
        len(source_keys) != 270:
    raise SystemExit("ABORT: selector-stability source coverage differs")
for panel in expected_panels:
    if len({(season, week) for found, season, week in source_keys
            if found == panel}) != 54:
        raise SystemExit("ABORT: selector-stability per-panel coverage differs")
for row in sources:
    if not str(row.get("uri", "")).startswith("gs://") or \
            re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", ""))) is None or \
            int(row.get("candidate_rows", 0)) <= 0:
        raise SystemExit("ABORT: selector-stability source receipt differs")
preflight = r.get("source_preflight", {})
if preflight.get("panel_ids") != expected_panels or \
        preflight.get("artifact_count") != 270 or \
        preflight.get("slate_count") != 54 or \
        len(preflight.get("slates", [])) != 54:
    raise SystemExit("ABORT: selector-stability source_preflight differs")
if r.get("local_source_receipts") != {
    "protocol": m.get("protocol_sha256"),
    "cbwu_oi_report": m.get("cbwu_oi_scorefree_report_sha256"),
}:
    raise SystemExit("ABORT: selector-stability local receipts differ")
flags = {
    "uses_realized_outcomes": False,
    "candidate_or_lineup_scores_read": False,
    "selector_tuned": False,
    "historical_arm_licensed": False,
    "production_change_licensed": False,
}
if any(r.get(key) is not value for key, value in flags.items()):
    raise SystemExit("ABORT: selector-stability evidence license differs")
world = r.get("world_contract", {})
expected_world = {
    "block_count": 5, "worlds_per_block": 10000, "full_worlds": 50000,
    "bootstrap_resamples": 32, "bootstrap_per_block": 2000,
    "bootstrap_worlds": 10000, "entry_count": 80, "line": 194.0,
}
if world != expected_world:
    raise SystemExit("ABORT: selector-stability world contract differs")
result = r.get("result", {})
if result.get("overall", {}).get("slates") != 54 or \
        len(result.get("slates", [])) != 54 or \
        set(result.get("by_season", {})) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: selector-stability result coverage differs")
keys = set()
for row in result["slates"]:
    keys.add((int(row["season"]), int(row["week"])))
    if row.get("uses_realized_outcomes") is not False or \
            row.get("samples_identical_across_pools") is not True:
        raise SystemExit("ABORT: selector-stability slate contract differs")
    for arm in ("canonical", "cbwu_oi"):
        value = row.get(arm, {})
        if value.get("full_book_reproduced") is not True or \
                int(value.get("entry_count", -1)) != 80 or \
                int(value.get("world_count", -1)) != 50000 or \
                int(value.get("bootstrap", {}).get("resamples", -1)) != 32 or \
                not math.isfinite(float(value.get("full_book_coverage", math.nan))):
            raise SystemExit("ABORT: selector-stability arm contract differs")
        pair = value["bootstrap"]["pairwise_overlap"]
        if int(pair.get("pair_count", -1)) != 496:
            raise SystemExit("ABORT: selector-stability bootstrap count differs")
if len(keys) != 54:
    raise SystemExit("ABORT: selector-stability slate keys repeat")
receipt = r.get("frequency_artifact", {})
digest = hashlib.sha256(frequency_bytes).hexdigest()
if receipt.get("uri") != m.get("frequency_uri") or \
        receipt.get("create_only") is not True or receipt.get("sha256") != digest:
    raise SystemExit("ABORT: selector-stability frequency receipt differs")
if frequency.get("version") != m.get("version") or \
        frequency.get("code_sha") != m.get("code_sha") or \
        frequency.get("image") != m.get("image") or \
        frequency.get("protocol_sha256") != m.get("protocol_sha256") or \
        frequency.get("cbwu_oi_scorefree_report_sha256") != \
        m.get("cbwu_oi_scorefree_report_sha256") or \
        frequency.get("uses_realized_outcomes") is not False:
    raise SystemExit("ABORT: selector-stability frequency identity differs")
frequency_rows = frequency.get("slates", [])
frequency_keys = {
    (int(row.get("season")), int(row.get("week"))) for row in frequency_rows
}
if len(frequency_rows) != 54 or frequency_keys != keys:
    raise SystemExit("ABORT: selector-stability frequency coverage differs")
for row in frequency_rows:
    for arm in ("canonical", "cbwu_oi"):
        values = row.get(arm, [])
        if len(values) < 80 or len({
            tuple(value.get("identity", [])) for value in values
        }) != len(values):
            raise SystemExit("ABORT: selector-stability frequencies differ")
        for value in values:
            count = int(value.get("selected_count", -1))
            rate = float(value.get("selection_frequency", math.nan))
            if not 0 <= count <= 32 or not math.isfinite(rate) or \
                    abs(rate - count / 32.0) > 1e-12 or \
                    len(value.get("identity", [])) != 9:
                raise SystemExit("ABORT: selector-stability frequency value differs")

def walk(value):
    if isinstance(value, dict):
        for child in value.values():
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise SystemExit("ABORT: selector-stability contains nonfinite output")

walk(result)
if "cannot tune, adopt, reject or promote" not in str(r.get("consequence", "")):
    raise SystemExit("ABORT: selector-stability consequence is absent")
overall = result["overall"]
print(
    "CBWU_OI_SELECTOR_STABILITY_VALIDATED",
    f"canonical={overall['canonical']['mean_pairwise_overlap']:.6f}",
    f"oi={overall['cbwu_oi']['mean_pairwise_overlap']:.6f}",
)
PY

mv "$EXEC_TMP" "$OUT/execution.json"
mv "$REPORT_TMP" "$OUT/report.json"
mv "$FREQUENCY_TMP" "$OUT/candidate-frequencies.json.gz"
trap - EXIT
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT/candidate-frequencies.json.gz" \
  > "$OUT/candidate-frequencies.sha256"
echo "CBWU_OI_SELECTOR_STABILITY_HARVESTED $EXEC"
