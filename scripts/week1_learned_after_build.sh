#!/bin/bash
# Poll the live results LATEST marker; for every NEW run dir (K80 D800 or K90 nested), apply the learned scorer over the
# whole candidate pool, emit DK upload CSVs for the four shadow books, and build lineup sheets. Runs until 16:50Z.
set -u
LIVE=/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01
PROD=/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912
PY=/home/erich/projects/nfl-predictions/.venv/bin/python
OUT=/home/erich/week1-sunday
SEEN="$OUT/learned_after_build.seen"; touch "$SEEN"; ls -1 "$LIVE" | grep -v LATEST >> "$SEEN"   # everything existing now is old
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
while [ "$(date -u +%H%M)" -lt 1650 ]; do
  for d in $(ls -1 "$LIVE" | grep -v LATEST); do
    grep -qx "$d" "$SEEN" && continue
    run="$LIVE/$d"
    [ -f "$run/receipt.json" ] && [ -f "$run/candidates.parquet" ] && [ -f "$run/incumbent_player_scores.npy" ] || continue
    sleep 20   # let the writer finish
    entries=$($PY -c "import json,sys; print(json.load(open('$run/receipt.json'))['written'])" 2>/dev/null) || { log "no receipt for $d yet"; continue; }
    echo "$d" >> "$SEEN"; tag="K${entries}-${d%%-*}"; lo="$OUT/learned-$tag"
    log "scoring $d (entries=$entries) -> $lo"
    $PY "$OUT/tools/learned_score_live.py" "$run" --entries "$entries" --k 30 --out-root "$lo" > "$lo.log" 2>&1 || { log "scorer FAILED for $d (see $lo.log)"; continue; }
    for b in learned-book learned-pool learned-div5 blend-q99 blend-div5 union; do
      PYTHONPATH=$PROD/src $PY "$PROD/scripts/emit_dk_upload_csv_v1.py" --source run-dir --run-dir "$lo/$b" --output "$OUT/upload-$tag-$b.csv" > "$lo/$b/emit.json" 2>&1 && log "  upload-$tag-$b.csv written" || log "  emit FAILED for $b"
      $PY "$OUT/tools/book_sheet.py" "$lo/$b" --banks-from "$run" --output "$OUT/lineup-sheet-$tag-$b" > "$lo/$b/sheet.out" 2>&1 && log "  lineup-sheet-$tag-$b.md written" || log "  sheet FAILED for $b"
    done
    shadows=$($PY - "$run" <<'PYEOF'
import glob, json, pathlib, sys
run = pathlib.Path(sys.argv[1]).resolve()
for j in sorted(glob.glob("/home/erich/week1-sunday/ordering_shadows_*.json"), key=lambda x: -pathlib.Path(x).stat().st_mtime):
    try:
        d = json.load(open(j))
        if pathlib.Path(d.get("run", d.get("source_run", ""))).resolve() == run: print(j); break
    except Exception: pass
PYEOF
)
    if [ -n "$shadows" ]; then sarg="--shadows $shadows"; else sarg=""; fi
    $PY "$OUT/tools/book_sheet.py" "$run" $sarg --output "$OUT/lineup-sheet-$tag-paid-with-learned" >> "$lo.log" 2>&1 && log "  paid sheet with learned columns written (shadows: ${shadows:-none})" || log "  paid sheet FAILED"
    log "done $d"
  done
  sleep 30
done
log "exit (16:50Z)"
