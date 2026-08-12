#!/bin/bash
# Harvest the frozen team-QB side-table build after clean completion.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-team-qb-quality-side-table-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-team-qb-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: side-table execution id missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable side-table report already exists"; exit 2; }

STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: side-table execution $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 200 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
grep -q '^TEAM_QB_QUALITY_SIDE_TABLE_VALIDATED$' "$OUT/raw_log.txt" || {
  echo "ABORT: side-table validation marker missing"; exit 1; }

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$EXEC" <<'PY'
import json
import sys

from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

table = f"{settings.features}.team_week_qb_quality"
summary = query_df(f"""
SELECT COUNT(*) AS rows,
       COUNT(DISTINCT CONCAT(team, '|', CAST(season AS STRING), '|', CAST(week AS STRING))) AS unique_keys,
       COUNTIF(team_qb_cpoe_l6 IS NOT NULL) AS supported_rows,
       BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS content_checksum
FROM `{table}` t
""").iloc[0]
coverage = query_df(f"""
SELECT season, COUNT(*) AS rows,
       COUNTIF(team_qb_cpoe_l6 IS NOT NULL) AS supported_rows
FROM `{table}` GROUP BY season ORDER BY season
""")
report = {
    "disposition": "team-qb-quality-side-table-valid",
    "execution": sys.argv[2],
    "table": table,
    "rows": int(summary.rows),
    "unique_keys": int(summary.unique_keys),
    "supported_rows": int(summary.supported_rows),
    "content_checksum": int(summary.content_checksum),
    "coverage": coverage.to_dict(orient="records"),
}
if report["rows"] <= 0 or report["rows"] != report["unique_keys"]:
    raise SystemExit("ABORT: team-QB side table is empty or has duplicate keys")
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TEAM_QB_QUALITY_SIDE_TABLE_COMPLETE $OUT/report.json"
