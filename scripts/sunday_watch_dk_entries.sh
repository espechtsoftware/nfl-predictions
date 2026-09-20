#!/usr/bin/env bash
# Watch for a DraftKings entries export (DKEntries*.csv) in the Windows Downloads folder or in $OUT/ENTER; fill it
# keepers-first from the ENTER files whenever it appears or the ENTER files change (T-70 rebuild).  Runs until 16:58Z.
#   source scripts/week_env.sh && week_env 2; scripts/sunday_watch_dk_entries.sh
set -u
: "${OUT:?source scripts/week_env.sh and call week_env WEEK first}" "${LIVE_DIR:?}" "${PROD_PY:?}" "${TOOLS:?}"
E=$OUT/ENTER; T=$TOOLS/fill_dk_entries.py
if [ -n "${WIN_DOWNLOADS:-}" ]; then
  WIN=$WIN_DOWNLOADS
elif [ -d /mnt/c/Users/erich/Downloads ]; then
  WIN=/mnt/c/Users/erich/Downloads
else
  WIN=/mnt/c/Users/Erich/Downloads
fi
: "${WEEK:?}"
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
last=""
while [ "$(date -u +%H%M)" -lt 1658 ]; do
  tpl=$(ls -t "$WIN"/DKEntries*.csv /mnt/c/Users/Erich/Desktop/DKEntries*.csv "$E"/DKEntries*.csv "$OUT"/DKEntries*.csv 2>/dev/null | grep -v FILLED | head -n 1)
  if [ -n "$tpl" ]; then
    B=$(readlink -f "$E" 2>/dev/null || echo "$E")   # resolve the bundle pointer ONCE per iteration (atomic swap)
    lu=$(ls -t "$B"/ENTER-*-entries-KEEP-first-*.csv 2>/dev/null | head -n 1); sig="$tpl:$(stat -c %Y "$tpl"):$(stat -c %Y "$lu" 2>/dev/null):$B"
    if [ "$sig" != "$last" ]; then
      frame=$(ls -td "$LIVE_DIR"/*/ | while read -r d; do [ -f "$d/frame.parquet" ] && { echo "$d/frame.parquet"; break; }; done)
      log "filling $tpl (lineups from $(basename "$lu"))"
      # 2026-09-17 review findings 1/2/5: bind the output to THIS week's ENTER dir, require the filler to succeed,
      # require the published file to be newer than the template, and publish to Downloads under a week-stamped name
      # as well as the stable one (a stale same-named file from a previous week must never be uploadable by mistake).
      out="$B/DKEntries-FILLED-keepers-first.csv"; rm -f "$out"
      if "$PROD_PY" "$T" "$tpl" --contests "$CONTESTS_JSON" --enter-dir "$B" --out-dir "$B" --frame "$frame" > "$B/fill.log" 2>&1 && [ -s "$out" ] && [ "$out" -nt "$tpl" ]; then
        cat "$B/fill.log"
        stamped="$WIN/DKEntries-FILLED-week${WEEK}-$(date -u +%Y%m%dt%H%Mz).csv"
        if cp "$out" "$stamped" && cp "$out" "$WIN/DKEntries-FILLED-keepers-first.csv"; then
          log "-> $stamped (and the stable name); $(( $(wc -l < "$out") - 1 )) entry rows"
          last="$sig"        # 2026-09-18 (review follow-up): only a complete fill AND copy suppresses the retry
        else
          log "FILL PUBLISHED LOCALLY BUT THE COPY TO WINDOWS FAILED: $out — will retry"
        fi          # 2026-09-18 (review follow-up): bookkeeping advances ONLY on a fully successful publish,
                             # so an unchanged-input retry is not suppressed after a fill or copy failure
      else
        log "FILL FAILED — nothing published; Downloads left untouched"; cat "$B/fill.log"
      fi
    fi
  fi
  sleep 10
done
log "exit"
