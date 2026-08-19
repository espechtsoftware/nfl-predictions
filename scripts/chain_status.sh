#!/usr/bin/env bash
set -uo pipefail

# One-shot, operator-runnable status of every research chain: live
# processes, the last meaningful line of every chain log, cloud build
# states, grid completeness, and the outcome-lease governance state.
# Run it yourself anytime:  bash scripts/chain_status.sh
# Stream any chain live:    tail -f ~/nfl-panels/<log>

PROJECT=nfl-predictions-503414
BOLD=$(tput bold 2>/dev/null || true); NORM=$(tput sgr0 2>/dev/null || true)

echo "${BOLD}== chain processes ==${NORM}"
ps -eo pid,etime,args --no-headers 2>/dev/null \
  | grep -E "watch_[a-z_]+\.sh|drive_[a-z_]+\.sh|repair_[a-z0-9_]+\.sh|tally_[a-z_]+\.sh|cloud_[a-z0-9_]+chain\.sh|finish-driver" \
  | grep -v grep \
  | awk '{printf "  pid %-8s up %-12s %s\n", $1, $2, $4}' \
  | sed 's|/tmp/nfl-[a-z0-9-]*/||; s|scripts/||' || true
[ -z "$(ps -eo args --no-headers | grep -E '[w]atch_|[d]rive_|[r]epair_atlas|[t]ally_')" ] \
  && echo "  (none running)"

echo "${BOLD}== chain logs (newest first, last meaningful line) ==${NORM}"
ls -t "$HOME"/nfl-panels/*.log 2>/dev/null | head -10 | while read -r log; do
  line=$(grep -avE "status=WORKING|status=QUEUED|state=Unknown|WAITS_FOR" \
    "$log" 2>/dev/null | tail -1)
  [ -z "$line" ] && line=$(tail -1 "$log" 2>/dev/null)
  printf "  %-42s %s\n" "$(basename "$log")" "${line:0:110}"
done

echo "${BOLD}== cloud builds (last 5) ==${NORM}"
gcloud builds list --project "$PROJECT" --limit 5 \
  --format="value(id,status,substitutions._IMAGE,createTime)" 2>/dev/null \
  | awk -F'\t' '{n=split($3,a,":"); printf "  %-38s %-9s %s\n", $1, $2, a[n]}'

echo "${BOLD}== ATLAS C attempt-2 grid ==${NORM}"
P=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/20260818-atlas-minimal-world-selection-c-v1/attempt-2
COUNT=$(gsutil ls "$P/slate-*.json" 2>/dev/null | wc -l)
AGG=$(gsutil -q stat "$P/../aggregate-report.json" 2>/dev/null && echo yes || echo no)
echo "  objects: $COUNT/54   local aggregate: $( [ -f "$HOME/projects/nfl-predictions/reports/atlas-minimal-c-runs/20260818-atlas-minimal-world-selection-c-v1-attempt-2/aggregate-report.json" ] && echo PRESENT || echo pending )"

echo "${BOLD}== outcome lease ==${NORM}"
gsutil -q stat gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json 2>/dev/null \
  && echo "  HELD (historical-outcome-active-v1.json exists)" \
  || echo "  free"

echo "${BOLD}== recent handoff commits ==${NORM}"
git -C "$HOME/projects/nfl-predictions" log --oneline -5 2>/dev/null | sed 's/^/  /'
