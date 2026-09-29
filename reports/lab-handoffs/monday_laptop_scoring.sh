#!/usr/bin/env bash
# Monday scoring of the week's PAPER cash/double-up shadows (run only after the week's outcomes are released and the
# Millionaire standings are imported into nfl_raw.contest_entries). Read-only against BigQuery; writes a log only.
#
#   [OUT=~/week4-sunday] [MILLY_CONTEST_ID=<id>] bash monday_laptop_scoring.sh [week=4]
#
# The Sunday chain (sunday_build_host.sh, 2026-09-28) writes the arms as $OUT/cash-shadow-wNN-{A,B}-<run tag>, one pair
# per build; every one found is scored with cash_shadow_paper.py. NO arms found = exit 2 (the week had no cash shadow,
# which is a finding, never a quiet "not on this host"). The Week-3 paper-triple (chalk-sleeve) arms are gone: nothing
# produces them any more (2026-09-29 sweep A2).
set -uo pipefail
WEEK=${1:-4}; WW=$(printf %02d "$WEEK")
PROD=${PROD:-$HOME/projects/nfl-predictions}
PY=${PROD_PY:-$PROD/.venv/bin/python}
OUT=${OUT:-$HOME/week${WEEK}-sunday}
LOG=${LOG:-$HOME/.cache/laptop-agent/monday-w$WW.log}; mkdir -p "$(dirname "$LOG")"; exec > >(tee -a "$LOG") 2>&1
echo "=== Monday scoring week $WEEK $(date -u +%FT%TZ) (OUT=$OUT)"
# The Millionaire's contest id: MILLY_CONTEST_ID (the take-over document's Monday step names it), else the largest
# contest_entries contest named by DraftKings ("…Millionaire…") or by the import label ("milly", "milly20").
MID=${MILLY_CONTEST_ID:-$(bq query --use_legacy_sql=false --format=csv "SELECT contest_id FROM \`nfl-predictions-503414.nfl_raw.contest_entries\`
      WHERE season=2026 AND week=$WEEK AND (contest_name LIKE '%Millionaire%' OR LOWER(contest_name) LIKE 'milly%') GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1" | tail -1)}
[[ "$MID" =~ ^[0-9]+$ ]] || { echo "no Week-$WEEK Millionaire in contest_entries yet; import the standings first (or set MILLY_CONTEST_ID)"; exit 2; }
echo "Millionaire contest $MID"
shopt -s nullglob
ARMS=("$OUT"/cash-shadow-w"$WW"-A-* "$OUT"/cash-shadow-w"$WW"-B-*)
shopt -u nullglob
found=0; failed=0
for d in "${ARMS[@]}"; do
  [[ -d "$d" && -f "$d/receipt.json" ]] || continue
  found=$((found + 1))
  echo "--- paper cash shadow: $(basename "$d")"
  if ! PYTHONPATH="$PROD/src" "$PY" "$PROD/reports/lab-handoffs/cash_shadow_paper.py" score "$d" 2026 "$WEEK" --milly-contest-id "$MID"; then
    echo "FAIL: cash shadow $(basename "$d")"; failed=$((failed + 1))
  fi
done
if (( found == 0 )); then
  echo "NO CASH-SHADOW ARMS under $OUT (cash-shadow-w$WW-{A,B}-*): the chain did not build them, or OUT is wrong -- record it in HANDOFF"
  exit 2
fi
echo "=== done: $found arm(s) scored, $failed failed; log $LOG"
(( failed == 0 )) || exit 1
