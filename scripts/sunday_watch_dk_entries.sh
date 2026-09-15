#!/usr/bin/env bash
# Watch for a DraftKings entries export (DKEntries*.csv) in the Windows Downloads folder or in $OUT/ENTER; fill it
# keepers-first from the ENTER files whenever it appears or the ENTER files change (T-70 rebuild).  Runs until 16:58Z.
#   source scripts/week_env.sh && week_env 2; scripts/sunday_watch_dk_entries.sh
set -u
: "${OUT:?source scripts/week_env.sh and call week_env WEEK first}" "${LIVE_DIR:?}" "${PROD_PY:?}" "${TOOLS:?}"
E=$OUT/ENTER; T=$TOOLS/fill_dk_entries.py; WIN=${WIN_DOWNLOADS:-/mnt/c/Users/Erich/Downloads}
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
last=""
while [ "$(date -u +%H%M)" -lt 1658 ]; do
  tpl=$(ls -t "$WIN"/DKEntries*.csv /mnt/c/Users/Erich/Desktop/DKEntries*.csv "$E"/DKEntries*.csv "$OUT"/DKEntries*.csv 2>/dev/null | grep -v FILLED | head -n 1)
  if [ -n "$tpl" ]; then
    lu=$(ls -t "$E"/ENTER-*-entries-KEEP-first-*.csv 2>/dev/null | head -n 1); sig="$tpl:$(stat -c %Y "$tpl"):$(stat -c %Y "$lu" 2>/dev/null)"
    if [ "$sig" != "$last" ]; then
      frame=$(ls -td "$LIVE_DIR"/*/ | while read -r d; do [ -f "$d/frame.parquet" ] && { echo "$d/frame.parquet"; break; }; done)
      log "filling $tpl (lineups from $(basename "$lu"))"
      "$PROD_PY" "$T" "$tpl" --enter-dir "$E" --frame "$frame" > "$E/fill.log" 2>&1 && { cat "$E/fill.log"; cp "$E/DKEntries-FILLED-keepers-first.csv" "$WIN/DKEntries-FILLED-keepers-first.csv" 2>/dev/null && log "-> $WIN/DKEntries-FILLED-keepers-first.csv"; } || { log "FILL FAILED"; cat "$E/fill.log"; }
      last="$sig"
    fi
  fi
  sleep 10
done
log "exit"
