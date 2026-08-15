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
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable selector-stability report exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: selector-stability execution is not successful ($STATE)" >&2
  exit 1
}
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
    "version", "protocol_sha256", "cbwu_oi_scorefree_report_sha256",
    "forensic_manifest_sha256",
):
    if str(r.get(key)) != m.get(key):
        raise SystemExit(f"ABORT: selector-stability {key} differs")
if r.get("code_sha") != m.get("code_sha") or r.get("image") != m.get("image"):
    raise SystemExit("ABORT: selector-stability code/image differs")
if r.get("source_panels") != m.get("source_panels", "").split(",") or \
        len(r.get("source_artifacts", [])) != 270:
    raise SystemExit("ABORT: selector-stability source coverage differs")
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
frequency = r.get("frequency_artifact", {})
if frequency.get("uri") != m.get("frequency_uri") or \
        frequency.get("create_only") is not True or \
        len(str(frequency.get("sha256", ""))) != 64:
    raise SystemExit("ABORT: selector-stability frequency receipt differs")
if "cannot tune, adopt, reject or promote" not in str(r.get("consequence", "")):
    raise SystemExit("ABORT: selector-stability consequence is absent")
overall = result["overall"]
print(
    "CBWU_OI_SELECTOR_STABILITY_VALIDATED",
    f"canonical={overall['canonical']['mean_pairwise_overlap']:.6f}",
    f"oi={overall['cbwu_oi']['mean_pairwise_overlap']:.6f}",
)
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "CBWU_OI_SELECTOR_STABILITY_HARVESTED $EXEC"
