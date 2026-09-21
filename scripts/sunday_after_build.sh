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
  # 2026-09-19 (operator directive, Rung 1c v4 after lab review): one ID-keyed QB classifier feeds the vetter
  # (demotion) and the replacement step (confirmed-unavailable rows -> best live pool candidates under the build's own
  # saved worlds). If the flag table fails, the vetter runs without it (its own starter query) and no replacement is
  # attempted; if the replacement fails, the vetted book is published with REPLACEMENT FAILED written into the
  # TODAY file and the page -- never as an ordinary success. The previous validated bundle stays under enter-bundles/.
  local QBF=""
  if PYTHONPATH="$TOOLS" $PY "$TOOLS/qb_flags.py" "$lo/qb-flags.csv" --season "$SEASON" --week "$WEEK" --group "$GROUP" > "$lo/qb-flags.log" 2>&1; then QBF="$lo/qb-flags.csv"; else log "  qb_flags FAILED (see $lo/qb-flags.log) -- vetting without the shared classifier, no replacement"; fi
  PYTHONPATH=$PROD/src:$TOOLS $PY "$TOOLS/vet_book.py" "$run" --k 30 --season "$SEASON" --week "$WEEK" --output-dir "$lo/paid-vetted" ${QBF:+--qb-flags "$QBF"} > "$lo/paid-vet.log" 2>&1 || { log "paid vet FAILED (see $lo/paid-vet.log)"; return 1; }
  local VET="$lo/paid-vetted" REPL_STATUS="NOT ATTEMPTED (no flag table)"
  if [ -n "$QBF" ]; then
    if PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PROD/src:$TOOLS $PY "$TOOLS/vet_replace_v4.py" "$lo/paid-vetted" "$run" "$lo/paid-vetted-replaced" --lab-src "$CLONE/src" --qb-flags "$QBF" --season "$SEASON" --week "$WEEK" --admit-risky > "$lo/paid-replace.log" 2>&1 \
       && [ ! -e "$lo/paid-vetted-replaced/NOT-PUBLISHABLE-REHEARSAL" ]; then
      VET="$lo/paid-vetted-replaced"; REPL_STATUS="OK: $(grep -m1 -E '^replaced' "$lo/paid-replace.log" || echo 'ran')"
    else
      REPL_STATUS="REPLACEMENT FAILED: $(grep -m1 'REPLACEMENT FAILED' "$lo/paid-replace.log" | cut -c1-300 || echo "see $lo/paid-replace.log") -- the vetted book was published with its unavailable rows still in place"
    fi
  fi
  log "  replacement: $REPL_STATUS"; printf '%s\n' "$REPL_STATUS" > "$lo/replacement-status.txt"
  PYTHONPATH=$PROD/src $PY "$PROD/scripts/emit_dk_upload_csv_v1.py" --source run-dir --run-dir "$VET" --output "$OUT/upload-$tag-paid-vetted-all.csv" > "$VET/emit.json" 2>&1 || { log "emit FAILED (see $VET/emit.json)"; return 1; }
  local all="$OUT/upload-$tag-paid-vetted-all.csv"
  mkdir -p "$lo/paid-vetted-30"; head -n 31 "$VET/book.csv" > "$lo/paid-vetted-30/book.csv"; cp "$run/frame.parquet" "$run/receipt.json" "$lo/paid-vetted-30/"
  $PY "$TOOLS/book_sheet.py" "$lo/paid-vetted-30" --banks-from "$run" --output "$OUT/lineup-sheet-$tag-paid-vetted-30" > "$lo/paid-vetted-30/sheet.out" 2>&1 || log "  sheet FAILED for the keepers"
  local PROMOTION_STATUS="NOT REQUESTED" PROMOTION_PUBLISHED=0 E="$OUT/ENTER"
  # The reviewed MEAN first-entry promotion must run before a new ENTER bundle becomes visible to the entries watcher.
  # It is opt-in until the production branch has been reconciled and the operator has selected the approved path.
  # PROMOTE_FIRST_ENTRY is the documented name; RUN_FIRST_PROMOTION remains a compatibility alias for the rehearsal.
  if [[ "${PROMOTE_FIRST_ENTRY:-${RUN_FIRST_PROMOTION:-0}}" == "1" ]]; then
    if PROD="$PROD" PROD_PY="$PROD_PY" LAB_PY="$LAB_PY" PY="$PROD_PY" LPY="$LAB_PY" TOOLS="$TOOLS" \
       PROMO_TOOLS="$PROD/scripts" CONTESTS_JSON="$CONTESTS_JSON" ENTER_LAYOUT="${ENTER_LAYOUT:-sequential}" \
       "$PROD/scripts/run_promotion.sh" "$lo" "$run" "$OUT" "$tag" "$SEASON" "$WEEK" > "$lo/promotion.log" 2>&1; then
      PROMOTION_STATUS="OK: first-entry MEAN promotion and atomic relayout published"
      PROMOTION_PUBLISHED=1
      log "  $PROMOTION_STATUS"
    else
      PROMOTION_STATUS="FAILED: see $lo/promotion.log; publishing the ordinary vetted bundle"
      log "  $PROMOTION_STATUS"
    fi
  fi
  # 2026-09-21 (Week-2 post-mortem; operator directive: no silent fallbacks). Two monitors run on the FINAL book before
  # the operator is told what to upload. (1) Regeneration lineage: every row changed by the replacement step must have
  # a receipted reason, the receipts' hashes must bind the books, the promotion must be exactly its recorded
  # permutation, and the promoted upload CSV must carry the promoted book in order; a failure is written into the
  # TODAY file as DO NOT UPLOAD and the chain returns non-zero (the promoted bundle is already published by the
  # promotion step, so the stop is surfaced, not hidden). (2) Exposure sheet: shares, majors shares, market source from
  # market_source_log (or a plain 'monitor not deployed' line), DK status, and the flags that need a stated reason;
  # a sheet that cannot be produced is written into the TODAY file as EXPOSURE SHEET FAILED, never skipped quietly.
  local FINAL="$VET" LINEAGE_STATUS="NOT APPLICABLE (no promotion)" SHEET_STATUS=""
  if (( PROMOTION_PUBLISHED == 1 )); then
    FINAL="$lo/paid-vetted-promoted"
    if [ -d "$lo/paid-vetted-replaced" ]; then
      rm -f "$lo/lineage.json"
      if PYTHONPATH=$PROD/src $PY "$PROD/scripts/regeneration_lineage.py" --vetted-dir "$lo/paid-vetted" --replaced-dir "$lo/paid-vetted-replaced" \
           --promoted-dir "$lo/paid-vetted-promoted" --upload-csv "$OUT/upload-$tag-promoted-paid-vetted-all.csv" --contests "$CONTESTS_JSON" --out "$lo/lineage.json" > "$lo/lineage.log" 2>&1; then
        LINEAGE_STATUS="OK: $(grep -m1 '^lineage OK' "$lo/lineage.log" | cut -c1-200)"
      else
        LINEAGE_STATUS="LINEAGE FAILED -- DO NOT UPLOAD: $(grep -m1 -E 'LINEAGE FAILED|problem:' "$lo/lineage.log" | cut -c1-300 || echo "see $lo/lineage.log")"
      fi
    else
      LINEAGE_STATUS="NOT APPLICABLE (no replacement step ran)"
    fi
    log "  lineage: $LINEAGE_STATUS"
  fi
  if PYTHONPATH=$PROD/src $PY "$PROD/scripts/exposure_sheet.py" --book "$FINAL/book.csv" --frame "$run/frame.parquet" --contests "$CONTESTS_JSON" \
       --season "$SEASON" --week "$WEEK" --draft-group "$GROUP" --out "$lo/exposure" > "$lo/exposure.log" 2>&1; then
    cp "$lo/exposure/exposure-sheet.md" "$OUT/exposure-sheet-$tag.md"; cp "$lo/exposure/exposure-sheet.csv" "$OUT/exposure-sheet-$tag.csv"
    SHEET_STATUS="$(head -n 1 "$lo/exposure/exposure-sheet.md" | cut -c1-200) -- full sheet $OUT/exposure-sheet-$tag.md"
  else
    SHEET_STATUS="EXPOSURE SHEET FAILED: $(grep -m1 -E 'Error|error|Traceback' "$lo/exposure.log" | cut -c1-200 || echo "see $lo/exposure.log") -- read $lo/exposure.log before uploading"
  fi
  log "  exposure sheet: $SHEET_STATUS"
  # ENTER/ is overwritten by every newer run: stable paths for the operator
  # 2026-09-17 review finding 5: stage the whole bundle, verify it, then swap it in -- the entries watcher polls this
  # directory continuously and must never see a half-written set, nor lose the previous good one on a failure.
  local STAGE="$OUT/.ENTER-staging-$tag"
  if (( PROMOTION_PUBLISHED == 0 )); then
    rm -rf "$STAGE"; mkdir -p "$STAGE" "$E"
  $PY - "$CONTESTS_JSON" "$all" "$STAGE" "$entries" <<'PYEOF' > "$STAGE/ENTER-layout.txt"
import csv, json, sys, pathlib
import os
contests, src, E, entries = json.load(open(sys.argv[1])), sys.argv[2], pathlib.Path(sys.argv[3]), int(sys.argv[4])
rows = list(csv.reader(open(src))); hdr, body = rows[0], rows[1:]
layout = os.environ.get("ENTER_LAYOUT", "top")   # top: every contest gets vetted ranks 1..n (contests pay independently,
                                                 # so each deserves the best lineups; Week-2 default).  sequential: the
                                                 # Week-1 layout (unique lineups across contests, keepers first).
if layout == "top":
    # A contest may set "block": true to take its own consecutive block of the book instead of ranks 1..n
    # (2026-09-18 operator decision, measured on the corrected Week-2 book's own worlds: for five satellite contests,
    # repeating the top block gives more EXPECTED seats but all-or-nothing; distinct blocks raise P(at least one seat)
    # from 35% to 58% at a 190-point cutoff, costing ~15% of expected seats. Fixed-value seats favour reliability.)
    cursor = 0
    for c in contests:
        n, k = int(c["entries"]), int(c["keep"]); lab = f"{c['name']}-{c['contest_id']}"
        if c.get("block"):
            lines = body[cursor:cursor + n]; lo, hi = cursor + 1, cursor + n; cursor += n; kind = "own block"
        else:
            lines = body[:n]; lo, hi = 1, n; kind = "top"
        if len(lines) != n:
            print(f"WARNING {lab}: only {len(lines)} of {n} lineups available from a K{entries} book (ranks {lo}-{hi})")
        out = E / f"ENTER-{lab}-{n}-entries-KEEP-first-{k}.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(hdr); w.writerows(lines)
        print(f"{lab}: {n} entries = vetted ranks {lo}-{hi} ({kind}; keep {k}) -> {out.name}")
    if cursor > entries:
        print(f"WARNING: blocked contests need ranks up to {cursor} but the book holds {entries}")
    print(f"top layout: {sum(int(c['entries']) for c in contests)} entries; blocked contests consumed ranks 1-{cursor}" if cursor else
          f"top layout: every contest receives the vetted book's first N; {sum(int(c['entries']) for c in contests)} entries in total")
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
  cp "$all" "$STAGE/ENTER-all-rows-1-to-$(( $($PY -c "import json; print(sum(c['keep'] for c in json.load(open('$CONTESTS_JSON'))))") ))-are-the-KEEPERS.csv"
  cp "$OUT/lineup-sheet-$tag-paid-vetted-30.md" "$STAGE/ENTER-sheet-keepers.md" 2>/dev/null
  # verify the staged bundle before it becomes visible: one file per contest, each with its configured entry count
  local want got
  want=$($PY -c "import json; print(len(json.load(open('$CONTESTS_JSON'))))")
  got=$(ls "$STAGE"/ENTER-*-entries-KEEP-first-*.csv 2>/dev/null | wc -l)
  if [ "$want" != "$got" ]; then log "staged bundle has $got per-contest files, expected $want -- NOT published, previous ENTER/ kept"; return 1; fi
  if ! $PY "$PROD/scripts/verify_enter_bundle.py" "$CONTESTS_JSON" "$STAGE"; then
    log "staged bundle failed verification -- NOT published, previous ENTER/ kept"; return 1
  fi
  # 2026-09-18 (review follow-up): the previous `rm` + per-file `mv` still exposed a partially populated directory to
  # the polling filler. Publish as an immutable versioned bundle and swap ONE symlink with rename(2), which is atomic:
  # the consumer either sees the whole previous bundle or the whole new one, and a failure leaves the old one in place.
  local BUNDLES VER
  BUNDLES="$OUT/enter-bundles"; VER="$BUNDLES/$tag"   # `local A=.. B=$A/..` does not see A yet under set -u
  mkdir -p "$BUNDLES"; rm -rf "$VER"; mv "$STAGE" "$VER"
  if [ -e "$E" ] && [ ! -L "$E" ]; then                 # first run after the upgrade: retire the real directory once
    rm -rf "$BUNDLES/legacy-$tag"; mv "$E" "$BUNDLES/legacy-$tag"
  fi
  ln -sfn "$VER" "$E.new" && mv -T "$E.new" "$E"
  log "published bundle $tag atomically: $E -> $(readlink -f "$E")"
  else
    log "promotion already published the new ENTER bundle: $E -> $(readlink -f "$E")"
  fi
  { echo "TODAY'S ENTRY = the vetted paid book (HARD/material lineups to the back), keepers first. Source run $(basename "$run"), K$entries, built $(date -u +%H:%M:%SZ), week $WEEK group $GROUP"; echo
    echo "REPLACEMENT STEP: $REPL_STATUS"; echo
    echo "FIRST-ENTRY PROMOTION: $PROMOTION_STATUS"; echo
    echo "REGENERATION LINEAGE: $LINEAGE_STATUS"; echo
    echo "EXPOSURE SHEET: $SHEET_STATUS"; echo
    if [ -f "$lo/exposure/exposure-sheet.md" ]; then echo "FLAGGED PLAYERS (each flag needs a stated reason before upload):"; grep -E '^\| ' "$lo/exposure/exposure-sheet.md" | awk -F'|' 'NR<=2 || $(NF-1) ~ /[a-z]/' | head -n 25 | sed 's#^#  #'; echo; fi
    echo "PER-CONTEST FILES FOR THE RESERVED ENTRIES (fill the DK entries export with scripts/fill_dk_entries.py or let the watcher do it):"
    sed 's#^#  #' "$E/ENTER-layout.txt"
    echo; echo "Files (Windows path): \\\\wsl.localhost\\Ubuntu$(echo "$E" | sed 's#/#\\#g')\\"; ls "$E"/ENTER-*.csv | xargs -n1 basename | sed 's#^#    #'
    echo; echo "Vetting flags on the keepers (from the FINAL book; replacement rows re-vetted):"; $PY - "$VET" <<'PYF' 2>/dev/null
import json, pathlib, sys
d = pathlib.Path(sys.argv[1]); n = 0
if (d / "vetting_final.json").exists():
    for lu in json.load(open(d / "vetting_final.json"))["lineups"][:30]:
        if lu["flags"]: n += 1; print(f"  keeper row {lu['position']} ({lu['source']}): {lu['flags']}")
else:
    r = json.load(open(d / "vetting.json")); order = r["order_source_ranks"][:30]
    for pos, src in enumerate(order, 1):
        lu = r["lineups"][src - 1]
        if lu["flags"]: n += 1; print(f"  keeper row {pos}: {'HARD' if lu['hard'] else ('material' if lu['material'] else 'soft')} {lu['flags']}")
print("  (none)" if n == 0 else "")
PYF
    echo; echo "Details: vetting $lo/paid-vetted/vetting.json; replacement $lo/paid-vetted-replaced/replace.json and vetting_final.json (if present); status $lo/replacement-status.txt; all-lineups CSV $all"
    if (( PROMOTION_PUBLISHED == 1 )); then
      echo; echo "UPLOAD THIS PROMOTED CSV: $OUT/upload-$tag-promoted-paid-vetted-all.csv"
      echo "PROMOTED KEEPERS SHEET: $OUT/lineup-sheet-$tag-promoted-paid-vetted-30.csv"
      echo "PROMOTION RECORD: $lo/promotion/PROMOTION-RECORD.md"
      echo "ROLLBACK CSV (ordinary vetted order): $all"
    fi
  } > "$OUT/TODAY-30-LATEST.md"
  if [[ "$LINEAGE_STATUS" == LINEAGE\ FAILED* ]]; then log "LINEAGE FAILED -- the TODAY file says DO NOT UPLOAD"; return 1; fi
  if [[ "$PROMOTION_STATUS" != "NOT REQUESTED" ]]; then
    echo "PROMOTION STEP: $PROMOTION_STATUS" >> "$OUT/TODAY-30-LATEST.md"
  fi
  # Input-freshness sweep. On 2026-09-20 every composite ordering read the last
  # WEEK-1 projection batch and Week-1 props, and nothing failed: the join is by
  # player, so it returned last week's numbers and coverage looked healthy. The
  # only trace was a timestamp in a receipt, so check that trace mechanically.
  # Reported, not fatal: it is a date heuristic, and blocking an entered book at
  # 11:15 CT on a heuristic is worse than a loud line the operator reads. A hit
  # means STOP and check which slice the tool selected.
  local WINDOW_START; WINDOW_START=$(date -u -d "$SUNDAY - 5 days" +%F 2>/dev/null || echo "")
  if [ -n "$WINDOW_START" ] && [ -f "$PROD/scripts/receipt_freshness_sweep.py" ]; then
    if $PY "$PROD/scripts/receipt_freshness_sweep.py" --dir "$OUT" --after "$WINDOW_START" \
         > "$OUT/input-freshness-$tag.txt" 2>&1; then
      echo "INPUT FRESHNESS: OK (no artifact read data from before $WINDOW_START)" >> "$OUT/TODAY-30-LATEST.md"
    else
      log "STALE INPUTS DETECTED -- see $OUT/input-freshness-$tag.txt"
      { echo
        echo "*** STALE INPUTS DETECTED -- DO NOT UPLOAD UNTIL CHECKED ***"
        echo "One or more artifacts recorded reading data from before $WINDOW_START,"
        echo "which is the Week-2 defect class: a tool silently selected another"
        echo "week's slice. Full list: $OUT/input-freshness-$tag.txt"
        grep -E "^  STALE" "$OUT/input-freshness-$tag.txt" | head -20
      } >> "$OUT/TODAY-30-LATEST.md"
    fi
  fi
  log "done $(basename "$run") -> $OUT/TODAY-30-LATEST.md"

}
if [ "${1:-}" = "once" ]; then
  if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
    echo "usage: $0 once <run dir> <tag>   (e.g. $0 once /path/to/20260920T...Z-<sha> sun-d12800)" >&2; exit 2
  fi
  [ -d "$2" ] || { echo "not a run dir: $2" >&2; exit 2; }
  process_run "$2" "$3"; exit $?
fi
# CHOSEN DOSE: the poll processes only run dirs whose receipt lev/boom
# equal CHOSEN_LEV/CHOSEN_BOOM (from the environment or $CHOSEN_FILE), so later builds at other doses never overwrite
# ENTER/.  Run dirs that already exist at start (the Saturday-night builds) are processed too, oldest first, so the
# newest matching book ends up in ENTER/.  Fallback: edit the chosen-dose file (e.g. to 1280/5120) and restart this
# script, or run `sunday_after_build.sh once <run dir> <tag>` by hand.  The polling path fails closed when no chosen
# dose is configured; set REQUIRE_CHOSEN_DOSE=0 only for an explicit all-dose rehearsal.
CHOSEN_FILE=${CHOSEN_FILE:-$OUT/chosen-dose.env}
# shellcheck disable=SC1090
[ -f "$CHOSEN_FILE" ] && source "$CHOSEN_FILE"
if [[ "${REQUIRE_CHOSEN_DOSE:-1}" == "1" && ( -z "${CHOSEN_LEV:-}" || -z "${CHOSEN_BOOM:-}" ) ]]; then
  log "no chosen dose configured; create $CHOSEN_FILE with CHOSEN_LEV=... and CHOSEN_BOOM=... (or set REQUIRE_CHOSEN_DOSE=0 for a rehearsal)"
  exit 2
fi
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
    sleep 20
    # 2026-09-17 review finding 4: a run is recorded as seen ONLY after it is published, and a run skipped for the
    # wrong dose is never recorded at all, so changing the chosen dose and restarting really does re-evaluate it.
    matches_chosen "$run" || { log "skip $d (not the chosen dose; still eligible if the chosen dose changes)"; continue; }
    entries=$($PY -c "import json; print(json.load(open('$run/receipt.json'))['written'])" 2>/dev/null) || { log "unreadable receipt for $d"; continue; }
    [ "$entries" -ge "${BOOK_ENTRIES:-90}" ] || { log "skip $d (K$entries; the ENTER layout needs at least ${BOOK_ENTRIES:-90})"; echo "$d" >> "$SEEN"; continue; }
    if process_run "$run" "K${entries}-${d%%-*}"; then echo "$d" >> "$SEEN"; else log "process_run FAILED for $d -- left eligible for retry"; fi
  done
  sleep 30
done
log "exit (16:50Z)"
