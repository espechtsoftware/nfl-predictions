#!/usr/bin/env bash
# Sunday: build the late-swap page inputs from the newest after-build outputs (read-only on the build files).
#   make_page.sh OUT_HTML "STATUS LABEL"
# 1. refreshes the ID-keyed QB flag table (shared classifier) from the latest projection batch
# 2. finds the newest lineup-sheet-*-paid-vetted-30.csv, upload-*-paid-vetted-all.csv and TODAY-30-LATEST.md
# 3. computes cap-feasible swap suggestions for flagged rows against the FINAL delivered book (the after-build's
#    replaced dir when present, else the source run dir); skipped if neither is found
# 4. renders the page with gen_sheet.py (shows the REPLACEMENT STEP status line from TODAY-30-LATEST.md)
# The page is then published with the Artifact tool by the agent (same file path -> same link).
set -euo pipefail
OUT=${1:?OUT_HTML}; STATUS=${2:?STATUS_LABEL}
TOOLS=${TOOLS:-/home/erich/week1-sunday/tools}
PY=/home/erich/projects/nfl-predictions/.venv/bin/python
cd /home/erich/week2-sunday
PYTHONPATH="$TOOLS" $PY "$TOOLS/qb_flags.py" qb-flags-week2.csv --season 2026 --week 2 --group 153428
SHEET=$(ls -t lineup-sheet-*-paid-vetted-30.csv 2>/dev/null | head -n 1)
UPLOAD=$(ls -t upload-*-paid-vetted-all.csv 2>/dev/null | head -n 1)
[[ -n "$SHEET" && -n "$UPLOAD" && -f TODAY-30-LATEST.md ]] || { echo "after-build outputs not present yet (sheet='$SHEET' upload='$UPLOAD')" >&2; exit 2; }
echo "sheet:  $SHEET"; echo "upload: $UPLOAD"; head -n 1 TODAY-30-LATEST.md
TAG=$(head -n 1 TODAY-30-LATEST.md | sed -nE 's/.*Source run (\S+),.*/\1/p' | tr -d ',')
AFTER=$(ls -td after-K*-* 2>/dev/null | head -n 1 || true)
BOOKDIR=""
if [[ -n "$AFTER" && -f "$AFTER/paid-vetted-replaced/book.csv" ]]; then BOOKDIR="$AFTER/paid-vetted-replaced";
elif [[ -n "$AFTER" && -f "$AFTER/paid-vetted/book.csv" ]]; then BOOKDIR="$AFTER/paid-vetted"; fi
RUNDIR=$(ls -d /home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/results/live/2026-w02/*${TAG}* 2>/dev/null | head -n 1 || true)
SWAPS=""
if [[ -n "$BOOKDIR" && -n "$RUNDIR" ]]; then
  # swap_suggest reads book.csv + frame.parquet from one dir: stage the final book beside the run's frame
  mkdir -p .swapstage && cp "$BOOKDIR/book.csv" .swapstage/book.csv && cp "$RUNDIR/frame.parquet" .swapstage/frame.parquet
  /home/erich/projects/nfl2/.venv/bin/python swap_suggest.py .swapstage qb-flags-week2.csv qb-flags-week2.csv swaps-week2.csv && SWAPS=swaps-week2.csv
else
  echo "final book dir or source run dir not found (after='$AFTER', run='$RUNDIR'); page will carry flags without swap suggestions" >&2
fi
python3 gen_sheet.py "$SHEET" "$UPLOAD" TODAY-30-LATEST.md "$OUT" "$STATUS" qb-flags-week2.csv "$SWAPS"
