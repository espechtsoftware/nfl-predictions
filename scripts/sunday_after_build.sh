#!/usr/bin/env bash
# Post-build chain for any week (generalised from the Week-1 learned_after_build.sh).  For every NEW live run dir
# under $LIVE_DIR: vet the paid book (HARD/material lineups to the back), write the per-contest ENTER files for the
# reserved entries from $CONTESTS_JSON (ENTER_LAYOUT=top, the Week-2 default: every contest gets the vetted book's
# first N, since contests pay independently; ENTER_LAYOUT=sequential: the Week-1 unique-across-contests layout), the
# single all-entries file, the keepers' sheet, and TODAY-30-LATEST.md.  The learned pool scorer
# (PREREG-096: REVERT) is no longer on the path; it can be run by hand from tools/.
#
#   source scripts/week_env.sh && week_env 2; scripts/sunday_after_build.sh              # poll until 16:50Z
#   scripts/sunday_after_build.sh once RUN_DIR TAG                                        # process one run now
set -u
: "${WEEK:?source scripts/week_env.sh and call week_env WEEK first}"
: "${OUT:?}" "${LIVE_DIR:?}" "${PROD:?}" "${PROD_PY:?}" "${TOOLS:?}" "${CONTESTS_JSON:?}" "${SEASON:?}"
PY=$PROD_PY
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
process_run() {
  local run=$1 tag=$2 entries lo
  entries=$($PY -c "import json; print(json.load(open('$run/receipt.json'))['written'])") || { log "no receipt in $run"; return 1; }
  lo="$OUT/after-$tag"; rm -rf "$lo"; mkdir -p "$lo"
  log "vetting $(basename "$run") (entries=$entries) -> $lo"
  PYTHONPATH=$PROD/src $PY "$TOOLS/vet_book.py" "$run" --k 30 --season "$SEASON" --week "$WEEK" --output-dir "$lo/paid-vetted" > "$lo/paid-vet.log" 2>&1 || { log "paid vet FAILED (see $lo/paid-vet.log)"; return 1; }
  PYTHONPATH=$PROD/src $PY "$PROD/scripts/emit_dk_upload_csv_v1.py" --source run-dir --run-dir "$lo/paid-vetted" --output "$OUT/upload-$tag-paid-vetted-all.csv" > "$lo/paid-vetted/emit.json" 2>&1 || { log "emit FAILED (see $lo/paid-vetted/emit.json)"; return 1; }
  mkdir -p "$lo/paid-vetted-30"; head -n 31 "$lo/paid-vetted/book.csv" > "$lo/paid-vetted-30/book.csv"; cp "$run/frame.parquet" "$run/receipt.json" "$lo/paid-vetted-30/"
  $PY "$TOOLS/book_sheet.py" "$lo/paid-vetted-30" --banks-from "$run" --output "$OUT/lineup-sheet-$tag-paid-vetted-30" > "$lo/paid-vetted-30/sheet.out" 2>&1 || log "  sheet FAILED for the keepers"
  # ENTER/ is overwritten by every newer run: stable paths for the operator
  local E="$OUT/ENTER"; mkdir -p "$E"; rm -f "$E"/*.csv "$E"/*.md
  local all="$OUT/upload-$tag-paid-vetted-all.csv"
  $PY - "$CONTESTS_JSON" "$all" "$E" "$entries" <<'PYEOF' > "$E/ENTER-layout.txt"
import csv, json, sys, pathlib
import os
contests, src, E, entries = json.load(open(sys.argv[1])), sys.argv[2], pathlib.Path(sys.argv[3]), int(sys.argv[4])
rows = list(csv.reader(open(src))); hdr, body = rows[0], rows[1:]
layout = os.environ.get("ENTER_LAYOUT", "top")   # top: every contest gets vetted ranks 1..n (contests pay independently,
                                                 # so each deserves the best lineups; Week-2 default).  sequential: the
                                                 # Week-1 layout (unique lineups across contests, keepers first).
if layout == "top":
    for c in contests:
        n, k = int(c["entries"]), int(c["keep"]); lab = f"{c['name']}-{c['contest_id']}"
        lines = body[:n]
        if len(lines) != n:
            print(f"WARNING {lab}: only {len(lines)} of {n} lineups available from a K{entries} book")
        out = E / f"ENTER-{lab}-{n}-entries-KEEP-first-{k}.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(hdr); w.writerows(lines)
        print(f"{lab}: {n} entries = vetted ranks 1-{n} (top layout; keep {k}) -> {out.name}")
    print(f"top layout: every contest receives the vetted book's first N; {sum(int(c['entries']) for c in contests)} entries in total")
else:
    keep_total = sum(int(c["keep"]) for c in contests); fill_next = keep_total + 1; keep_next = 1
    for c in contests:
        n, k = int(c["entries"]), int(c["keep"]); lab = f"{c['name']}-{c['contest_id']}"
        keepers = body[keep_next - 1: keep_next - 1 + k]; keep_next += k
        fills = body[fill_next - 1: fill_next - 1 + (n - k)]; fill_next += n - k
        if len(keepers) + len(fills) != n:
            print(f"WARNING {lab}: only {len(keepers) + len(fills)} of {n} lineups available from a K{entries} book")
        out = E / f"ENTER-{lab}-{n}-entries-KEEP-first-{k}.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(hdr); w.writerows(keepers + fills)
        print(f"{lab}: {n} entries, keep rows 1-{k} (vetted ranks {keep_next - k}-{keep_next - 1}), fill rows {k + 1}-{n} -> {out.name}")
    print(f"keepers total {keep_total}; fills drawn from vetted ranks {keep_total + 1}-{fill_next - 1}")
PYEOF
  cp "$all" "$E/ENTER-all-rows-1-to-$(( $($PY -c "import json; print(sum(c['keep'] for c in json.load(open('$CONTESTS_JSON'))))") ))-are-the-KEEPERS.csv"
  cp "$OUT/lineup-sheet-$tag-paid-vetted-30.md" "$E/ENTER-sheet-keepers.md" 2>/dev/null
  { echo "TODAY'S ENTRY = the vetted paid book (HARD/material lineups to the back), keepers first. Source run $(basename "$run"), K$entries, built $(date -u +%H:%M:%SZ), week $WEEK group $GROUP"; echo
    echo "PER-CONTEST FILES FOR THE RESERVED ENTRIES (fill the DK entries export with scripts/week1_fill_dk_entries.py or let the watcher do it):"
    sed 's#^#  #' "$E/ENTER-layout.txt"
    echo; echo "Files (Windows path): \\\\wsl.localhost\\Ubuntu$(echo "$E" | sed 's#/#\\#g')\\"; ls "$E"/ENTER-*.csv | xargs -n1 basename | sed 's#^#    #'
    echo; echo "Vetting flags on the keepers (soft = informational):"; $PY -c "
import json; r=json.load(open('$lo/paid-vetted/vetting.json')); order=r['order_source_ranks'][:30]; n=0
for pos, src in enumerate(order, 1):
    lu = r['lineups'][src-1]
    if lu['flags']: n+=1; print(f\"  keeper row {pos}: {'HARD' if lu['hard'] else ('material' if lu['material'] else 'soft')} {lu['flags']}\")
print('  (none)' if n==0 else '')" 2>/dev/null
    echo; echo "Details: vetting $lo/paid-vetted/vetting.json; all-lineups CSV $all"
  } > "$OUT/TODAY-30-LATEST.md"
  log "done $(basename "$run") -> $OUT/TODAY-30-LATEST.md"
}
if [ "${1:-}" = "once" ]; then process_run "$2" "$3"; exit $?; fi
# CHOSEN DOSE (2026-09-17, operator: enter the D12800 book): the poll processes only run dirs whose receipt lev/boom
# equal CHOSEN_LEV/CHOSEN_BOOM (from the environment or $CHOSEN_FILE), so later builds at other doses never overwrite
# ENTER/.  Run dirs that already exist at start (the Saturday-night builds) are processed too, oldest first, so the
# newest matching book ends up in ENTER/.  Fallback: edit the chosen-dose file (e.g. to 1280/5120) and restart this
# script, or run `sunday_after_build.sh once <run dir> <tag>` by hand.  Unset CHOSEN_LEV = process every K90 build.
CHOSEN_FILE=${CHOSEN_FILE:-/home/erich/week${WEEK}-chosen-dose.env}
# shellcheck disable=SC1090
[ -f "$CHOSEN_FILE" ] && source "$CHOSEN_FILE"
matches_chosen() {  # $1 run dir -> 0 if the receipt's lev/boom equal the chosen dose (or no dose is chosen)
  [ -z "${CHOSEN_LEV:-}" ] && return 0
  $PY - "$1" "$CHOSEN_LEV" "$CHOSEN_BOOM" <<'PYEOF'
import json, sys
c = json.load(open(sys.argv[1] + "/receipt.json"))["config"]
sys.exit(0 if (int(c["lev"]), int(c["boom"])) == (int(sys.argv[2]), int(sys.argv[3])) else 1)
PYEOF
}
log "chosen dose: lev ${CHOSEN_LEV:-any} / boom ${CHOSEN_BOOM:-any} (file $CHOSEN_FILE)"
mkdir -p "$LIVE_DIR"; SEEN="$OUT/after_build.seen"; touch "$SEEN"
while [ "$(date -u +%H%M)" -lt 1650 ]; do
  for d in $(ls -1 "$LIVE_DIR" | grep -v LATEST); do
    grep -qx "$d" "$SEEN" && continue
    run="$LIVE_DIR/$d"; [ -f "$run/receipt.json" ] && [ -f "$run/candidates.parquet" ] && [ -f "$run/incumbent_player_scores.npy" ] || continue
    sleep 20; echo "$d" >> "$SEEN"
    matches_chosen "$run" || { log "skip $d (not the chosen dose)"; continue; }
    entries=$($PY -c "import json; print(json.load(open('$run/receipt.json'))['written'])" 2>/dev/null) || { log "unreadable receipt for $d"; continue; }
    [ "$entries" -ge 90 ] || { log "skip $d (K$entries; the ENTER layout needs the K90 nested build)"; continue; }
    process_run "$run" "K${entries}-${d%%-*}"
  done
  sleep 30
done
log "exit (16:50Z)"
