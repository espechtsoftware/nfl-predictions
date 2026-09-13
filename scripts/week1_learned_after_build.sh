#!/bin/bash
# For every NEW live run dir (K80 D800 or K90 nested): learned scorer over the whole candidate pool -> vet today-30 ->
# exclude HARD players and re-score (max 2 passes) -> DK upload CSVs + lineup sheets for every shadow book -> TODAY-30-LATEST.md.
# Usage: learned_after_build.sh            (poll until 16:50Z)   |   learned_after_build.sh once RUN_DIR TAG   (process one run now)
set -u
LIVE=/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01
PROD=/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912
PY=/home/erich/projects/nfl-predictions/.venv/bin/python
OUT=/home/erich/week1-sunday
BOOKS="today-30 today-90 learned-div5-exp40 learned-book learned-pool learned-div5 blend-q99 blend-div5 union"
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
process_run() {
  local run=$1 tag=$2 entries lo excl hard pass
  entries=$($PY -c "import json; print(json.load(open('$run/receipt.json'))['written'])") || { log "no receipt in $run"; return 1; }
  lo="$OUT/learned-$tag"; rm -rf "$lo"; excl=""
  log "scoring $(basename "$run") (entries=$entries) -> $lo"
  for pass in 1 2 3; do
    $PY "$OUT/tools/learned_score_live.py" "$run" --entries "$entries" --k 30 --out-root "$lo" ${excl:+--exclude-players "$excl"} > "$lo.log" 2>&1 || { log "scorer FAILED (see $lo.log)"; return 1; }
    $PY "$OUT/tools/vet_book.py" "$lo/today-30" --k 30 --output-dir "$lo/today-30-vetted" > "$lo/today-30-vet.log" 2>&1 || { log "vet FAILED (see $lo/today-30-vet.log); today-30 is UNVETTED"; break; }
    hard=$($PY -c "import json; r=json.load(open('$lo/today-30-vetted/vetting.json')); print(','.join(sorted({v['dk'] for v in r['player_flags'].values() if v['weight']>=100 and v.get('dk')})))")
    [ -z "$hard" ] && { log "  pass $pass: no HARD players in today-30"; break; }
    log "  pass $pass: HARD players [$hard] -> re-scoring with exclusions"; excl="${excl:+$excl,}$hard"
  done
  for b in $BOOKS; do
    PYTHONPATH=$PROD/src $PY "$PROD/scripts/emit_dk_upload_csv_v1.py" --source run-dir --run-dir "$lo/$b" --output "$OUT/upload-$tag-$b.csv" > "$lo/$b/emit.json" 2>&1 && log "  upload-$tag-$b.csv" || log "  emit FAILED for $b"
    $PY "$OUT/tools/book_sheet.py" "$lo/$b" --banks-from "$run" --output "$OUT/lineup-sheet-$tag-$b" > "$lo/$b/sheet.out" 2>&1 || log "  sheet FAILED for $b"
  done
  local shadows; shadows=$($PY - "$run" <<'PYEOF'
import glob, json, pathlib, sys
run = pathlib.Path(sys.argv[1]).resolve()
for j in sorted(glob.glob("/home/erich/week1-sunday/ordering_shadows_*.json"), key=lambda x: -pathlib.Path(x).stat().st_mtime):
    try:
        d = json.load(open(j))
        if pathlib.Path(d.get("run", d.get("source_run", ""))).resolve() == run: print(j); break
    except Exception: pass
PYEOF
)
  $PY "$OUT/tools/book_sheet.py" "$run" ${shadows:+--shadows "$shadows"} --output "$OUT/lineup-sheet-$tag-paid-with-learned" >> "$lo.log" 2>&1 || log "  paid sheet FAILED"
  { echo "# TODAY-30 — source run $(basename "$run") (K$entries pool), built $(date -u +%H:%M:%SZ)"; echo
    echo "- Upload CSV, 30 rows (the lineups to enter): $OUT/upload-$tag-today-30.csv"
    echo "- Upload CSV, 90 rows (the same 30 first, then the paid book remainder): $OUT/upload-$tag-today-90.csv"
    echo "- Sheet (names, salary, both laws' sim stats, learned score, pool ranks): $OUT/lineup-sheet-$tag-today-30.md"
    echo "- Vetting: $lo/today-30-vetted/vetting.json — HARD players excluded before selection: ${excl:-none}"
    echo "- Rule: greedy by learned pool score over all candidates, pairwise overlap <= 5, single-player exposure <= 40% (historical K=30 +6.07 vs expected-max, out of season)"; echo
    cat "$lo/today-30/exposure.md" 2>/dev/null; echo; echo "## flags on the 30 (from vetting)"; $PY -c "
import json; r=json.load(open('$lo/today-30-vetted/vetting.json'))
for lu in r['lineups']:
    if lu['flags']: print(f\"- lineup {lu['rank']} risk {lu['risk']} {'HARD' if lu['hard'] else ('material' if lu['material'] else 'soft')}: {lu['flags']}\")
print('(no flags)' if not any(lu['flags'] for lu in r['lineups']) else '')" 2>/dev/null
  } > "$OUT/TODAY-30-LATEST.md"
  log "done $(basename "$run") -> $OUT/TODAY-30-LATEST.md"
}
if [ "${1:-}" = "once" ]; then process_run "$2" "$3"; exit $?; fi
SEEN="$OUT/learned_after_build.seen"; touch "$SEEN"; ls -1 "$LIVE" | grep -v LATEST >> "$SEEN"
while [ "$(date -u +%H%M)" -lt 1650 ]; do
  for d in $(ls -1 "$LIVE" | grep -v LATEST); do
    grep -qx "$d" "$SEEN" && continue
    run="$LIVE/$d"; [ -f "$run/receipt.json" ] && [ -f "$run/candidates.parquet" ] && [ -f "$run/incumbent_player_scores.npy" ] || continue
    sleep 20; echo "$d" >> "$SEEN"
    entries=$($PY -c "import json; print(json.load(open('$run/receipt.json'))['written'])" 2>/dev/null) || { log "unreadable receipt for $d"; continue; }
    process_run "$run" "K${entries}-${d%%-*}"
  done
  sleep 30
done
log "exit (16:50Z)"
