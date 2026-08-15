#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_finish_exact_p_corrected_identity_source.sh <preflight-2023|full>

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260815-exact-p-corrected-identities-v1
MODE=${1:-}
case "$MODE" in
  preflight-2023) STAGE=preflight-2023 ;;
  full) STAGE=full ;;
  *) echo "ABORT: mode must be preflight-2023 or full" >&2; exit 2 ;;
esac
OUT="$ROOT/reports/exact-p-corrected-identity-runs/$RUN_ID/$STAGE"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: corrected-identity manifest/execution incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable corrected-identity report exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: corrected-identity execution is not successful ($STATE)" >&2; exit 1; }
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json, sys
r=json.load(open(sys.argv[1], encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
for key in ("version","mode","analysis_code_sha","analysis_image",
            "repair_protocol_sha256","manifest_sha256",
            "exact_stack_parent_generation","exact_stack_parent_sha256"):
    observed = r.get(key)
    expected = m.get({"analysis_code_sha":"code_sha","analysis_image":"image"}.get(key,key))
    if str(observed) != expected:
        raise SystemExit(f"ABORT: corrected-identity {key} differs")
for key in ("identity_source_is_outcome_derived","exact_stack_scores_reproduced",
            "exact_stack_tail_counts_reproduced","all_rosters_independently_legal"):
    if r.get(key) is not True:
        raise SystemExit(f"ABORT: corrected-identity {key} failed")
for key in ("persisted_outcome_values","persisted_candidate_scores_or_membership",
            "scientific_result_licensed","production_change_licensed"):
    if r.get(key) is not False:
        raise SystemExit(f"ABORT: corrected-identity {key} differs")
if r.get("mode") == "preflight-2023":
    if r.get("slates") != 18 or r.get("roster_slots") != 162 or \
            r.get("identities_persisted") is not False or "records" in r:
        raise SystemExit("ABORT: corrected-identity preflight disclosure differs")
else:
    rows=r.get("records",[])
    keys={(int(x["season"]),int(x["week"])) for x in rows}
    if r.get("slates") != 54 or r.get("roster_slots") != 486 or \
            len(rows) != 54 or len(keys) != 54 or \
            any(len(x.get("players",[])) != 9 or len(set(x["players"])) != 9 for x in rows):
        raise SystemExit("ABORT: corrected-identity full population differs")
    forbidden={"actual","actual_score","rank","selected","selected_rank",
               "actual_ownership","payout","winnings","tag","all_tags"}
    if any(forbidden & set(x) for x in rows):
        raise SystemExit("ABORT: corrected-identity record leaks forbidden fields")
print("EXACT_P_CORRECTED_IDENTITIES_VALIDATED",r["mode"],r["slates"])
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "EXACT_P_CORRECTED_IDENTITIES_HARVESTED $EXEC"
