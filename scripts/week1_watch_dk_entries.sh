#!/bin/bash
# Watch for a DraftKings entries export (DKEntries*.csv) in the Windows Downloads folder or in ENTER/; fill it with the
# keepers-first lineups whenever it appears or whenever the ENTER lineup files change (T-70 rebuild). Runs until 16:58Z.
PY=/home/erich/projects/nfl-predictions/.venv/bin/python; E=/home/erich/week1-sunday/ENTER; T=/home/erich/week1-sunday/tools/fill_dk_entries.py
CLONE=/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
last=""
while [ "$(date -u +%H%M)" -lt 1658 ]; do
  tpl=$(ls -t /mnt/c/Users/Erich/Downloads/DKEntries*.csv /mnt/c/Users/Erich/Desktop/DKEntries*.csv "$E"/DKEntries*.csv /home/erich/week1-sunday/DKEntries*.csv 2>/dev/null | grep -v FILLED | head -n 1)
  if [ -n "$tpl" ]; then
    lu=$(ls -t "$E"/ENTER-*-entries-KEEP-first-*.csv 2>/dev/null | head -n 1); sig="$tpl:$(stat -c %Y "$tpl"):$(stat -c %Y "$lu" 2>/dev/null)"
    if [ "$sig" != "$last" ]; then
      frame=$(ls -td "$CLONE"/results/live/2026-w01/*/ | while read -r d; do [ -f "$d/frame.parquet" ] && { echo "$d/frame.parquet"; break; }; done)
      log "filling $tpl (lineups from $(basename "$lu"))"; $PY "$T" "$tpl" --frame "$frame" > "$E/fill.log" 2>&1 && { cat "$E/fill.log"; cp "$E/DKEntries-FILLED-keepers-first.csv" /mnt/c/Users/Erich/Downloads/DKEntries-FILLED-keepers-first.csv 2>/dev/null && cp "$E"/WITHDRAW-these-entry-ids.txt "$E"/KEEP-these-entry-ids.txt /mnt/c/Users/Erich/Downloads/ 2>/dev/null && log "copy -> C:\\Users\\Erich\\Downloads\\DKEntries-FILLED-keepers-first.csv (+ KEEP/WITHDRAW lists)"; } || { log "FILL FAILED"; cat "$E/fill.log"; sig=""; }
      last="$sig"
    fi
  fi
  sleep 10
done
log "exit"
