#!/usr/bin/env bash
# Read the L01 panel ONCE and write the report with the frozen reader's output verbatim (PREREG-L01).
#   bash l01_write_report.sh [--final]      # without --final it only reports completeness and never reads outcomes
# Banks are included whole: a bank with 54/54 slates is read; an incomplete bank is dropped (PREREG-L01 drop rule, fixed
# before launch: any bank incomplete at Friday 09:00 CT is dropped whole). Without --final, nothing outcome-bearing runs.
set -uo pipefail
L=${L01_DIR:-$HOME/.cache/laptop-agent/l01}
W=${L01_WORKTREE:-/home/erich/projects/.nfl2-worktrees/laptop-max-per-game-20260922}
PROD=${PROD:-/home/erich/projects/.nfl-predictions-worktrees/laptop-agent-intro-20260922}
LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
complete=(); incomplete=()
for b in 1100 1101 1102; do
  n=$( [[ -f "$L/results_bank$b.jsonl" ]] && wc -l < "$L/results_bank$b.jsonl" || echo 0 )
  echo "bank $b: $n/54"
  if [[ "$n" -eq 54 ]]; then complete+=("$b"); else incomplete+=("$b"); fi
done
[[ "${1:-}" == "--final" ]] || { echo "(no --final: completeness only; nothing read)"; exit 0; }
(( ${#complete[@]} )) || { echo "no complete bank; refusing to read"; exit 1; }
[[ -z "$(git -C "$W" status --porcelain)" && "$(git -C "$W" rev-parse --short HEAD)" == "dc66bdb" ]] \
  || { echo "L01 worktree is not clean at the frozen commit dc66bdb; refusing to read"; exit 1; }
BANKS=$(IFS=,; echo "${complete[*]}")
OUT="$PROD/reports/$(date +%F)-laptop-l01-panel-result.md"
READ=$(cd "$W" && PYTHONPATH="$W/src" "$LAB_PY" scripts/l01_report.py --out "$L" --banks "$BANKS" 2>&1) || { echo "$READ"; echo "reader failed"; exit 1; }
CKPT=$("$LAB_PY" "$PROD/reports/lab-handoffs/l01_mechanics_checkpoint.py" "$L" 1100,1101,1102 8 2>&1)
{
  echo "# L01 result: all-boom and max-per-game-4 vs the live generator (PREREG-L01, read once $(date '+%F %H:%M %Z'))"
  echo
  echo "Frozen design: nfl2 \`laptop/l01-panel-20260922\` @ \`dc66bdb0\` (\`PREREG-L01.md\`). Banks read: **$BANKS**."
  [[ ${#incomplete[@]} -gt 0 ]] && echo "Dropped whole under the pre-registered drop rule: **${incomplete[*]}**."
  echo
  echo "## Frozen reader output (verbatim)"
  echo '```'; echo "$READ"; echo '```'
  echo
  echo "## Mechanics (outcome-blind checkpoint)"
  echo '```'; echo "$CKPT"; echo '```'
  echo
  echo "## Interpretation"
  echo "_(written after the read; the verdict lines above are the decision under the frozen rule.)_"
} > "$OUT"
echo "wrote $OUT"; echo "$READ" | grep -E "VERDICT"
