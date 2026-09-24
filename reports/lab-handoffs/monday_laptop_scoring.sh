#!/usr/bin/env bash
# Monday scoring of the laptop's Week-N paper artifacts (run only after the week's outcomes are released and the
# Millionaire standings are imported into nfl_raw.contest_entries). Read-only against BigQuery; writes a log only.
#   [ENTERED_BOOK=<entered lineups csv>] bash monday_laptop_scoring.sh [week=3]
# Scores, with production's scripts/book_vs_field_scoreboard.py, each chalk-sleeve paper-triple run dir listed in
# ~/.cache/laptop-agent/paper-triple-wNN/run_dirs.txt (a control, b low-max 1, c low-max 2 = L02 SLEEVE_L2), and, if the paper cash
# shadow's out dir is on this host (CASH_DIR, default ~/.cache/laptop-agent/cash-shadow-wNN), scores it too.
set -uo pipefail
WEEK=${1:-3}; WW=$(printf %02d "$WEEK")
PROD=${PROD:-/home/erich/projects/.nfl-predictions-worktrees/laptop-agent-intro-20260922}
PY=${PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
T=${TRIPLE_DIR:-$HOME/.cache/laptop-agent/paper-triple-w$WW}; CASH_DIR=${CASH_DIR:-$HOME/.cache/laptop-agent/cash-shadow-w$WW}
LOG=$HOME/.cache/laptop-agent/monday-w$WW.log; exec > >(tee -a "$LOG") 2>&1
echo "=== Monday scoring week $WEEK $(date -u +%FT%TZ)"
MID=$(bq query --use_legacy_sql=false --format=csv "SELECT contest_id FROM \`nfl-predictions-503414.nfl_raw.contest_entries\`
      WHERE season=2026 AND week=$WEEK AND contest_name LIKE '%Millionaire%' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1" | tail -1)
[[ "$MID" =~ ^[0-9]+$ ]] || { echo "no Week-$WEEK Millionaire in contest_entries yet; import the standings first"; exit 2; }
echo "Millionaire contest $MID"
if [[ -f "$T/run_dirs.txt" ]]; then
  while read -r label dir; do
    echo "--- paper triple ($label): $dir"
    PYTHONPATH="$PROD/src" "$PY" "$PROD/scripts/book_vs_field_scoreboard.py" "$dir" 2026 "$WEEK" "$MID" || echo "FAIL: scoreboard ($label)"
  done < "$T/run_dirs.txt"
  # operator 155ff97b: finish share above best, 194+ clears and book best per arm, beside the entered book when
  # ENTERED_BOOK names its lineup CSV (DK ids only, never entry keys; mapped through arm (a)'s Saturday frame).
  specs=(); while read -r label dir; do specs+=("$label=$dir"); done < "$T/run_dirs.txt"
  ctrl=$(awk '$1=="a_control"{print $2}' "$T/run_dirs.txt")
  [[ -n "${ENTERED_BOOK:-}" && -n "$ctrl" ]] && specs+=("entered=$ctrl@$ENTERED_BOOK")
  echo "--- paper arms: outcome line (c_low2 = L02 SLEEVE_L2)"
  PYTHONPATH="$PROD/src" "$PY" "$PROD/reports/lab-handoffs/paper_arm_outcomes.py" 2026 "$WEEK" "$MID" "${specs[@]}" \
    || echo "FAIL: paper arm outcomes"
else
  echo "no paper-triple run dirs at $T/run_dirs.txt"
fi
if [[ -f "$CASH_DIR/receipt.json" ]]; then
  echo "--- paper cash shadow: $CASH_DIR"
  PYTHONPATH="$PROD/src" "$PY" "$PROD/reports/lab-handoffs/cash_shadow_paper.py" score "$CASH_DIR" 2026 "$WEEK" || echo "FAIL: cash shadow"
else
  echo "paper cash shadow out dir not on this host ($CASH_DIR); production scores it on the build host"
fi
echo "=== done; log $LOG"
