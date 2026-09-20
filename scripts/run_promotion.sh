#!/usr/bin/env bash
# run_promotion.sh v2.2 -- Week-2 class E (operator-authorized 2026-09-19): apply the labs' frozen first-delivered promotion
# (MEAN rule) to the FINAL delivered book.  Runs AFTER the cleared after-build chain; touches none of its files.
#   run_promotion.sh AFTER_DIR RUN_DIR OUT_DIR TAG [SEASON WEEK]
#   AFTER_DIR  the chain's after-<tag>/ (paid-vetted-replaced/, replacement-status.txt, qb-flags.csv)
#   RUN_DIR    the lab run dir (frame.parquet, candidates.parquet, receipt.json, the two selection banks)
#   OUT_DIR    the chain's output dir (contests.json, upload-<tag>-paid-vetted-all.csv, TODAY-30-LATEST.md)
#   env TOOLS        dir with the cleared vet_book.py + qb_classify.py + book_sheet.py (default /home/erich/week1-sunday/tools)
#   env PROMO_TOOLS  dir with promote_first.py + first_delivered_promotion.py (default /home/erich/week2-sunday)
# Publication is staged: the upload CSV and the keepers sheet are produced under AFTER_DIR/promotion/stage/ (outside every
# make_page.sh glob), verified against the chain's upload as the recorded permutation, and only then moved atomically into
# OUT_DIR as upload-<tag>-promoted-paid-vetted-all.csv / lineup-sheet-<tag>-promoted-paid-vetted-30.{csv,md}.  Any failure
# leaves nothing discoverable and writes AFTER_DIR/promotion/PROMOTION-FAILED.txt.  Exit 3 = the final-book vetting or the
# replacement receipt found an unavailable player in the book: NO upload is safe (the chain's included) until the replacement
# step is re-run with fresh status; the exact commands are printed.
set -uo pipefail
AFTER=${1:?AFTER_DIR}; RUN=${2:?RUN_DIR}; OUT=${3:?OUT_DIR}; TAG=${4:?TAG}; SEASON=${5:-2026}; WEEK=${6:-2}
# v2.2 (2026-09-20, lab review): every path is environment-driven; defaults resolve to the checkout this script lives in.
PROD=${PROD:-$(cd "$(dirname "$0")/.." && pwd)}
TOOLS=${TOOLS:-$PROD/scripts}; PT=${PROMO_TOOLS:-$PROD/scripts}
PY=${PROD_PY:-${PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}}; LPY=${LAB_PY:-${LPY:-/home/erich/projects/nfl2/.venv/bin/python}}
VET=$AFTER/paid-vetted-replaced; PR=$AFTER/promotion; PROMOTED=$AFTER/paid-vetted-promoted; STAGE=$PR/stage
ORIG=$OUT/upload-$TAG-paid-vetted-all.csv; UP=$OUT/upload-$TAG-promoted-paid-vetted-all.csv; SHEET=$OUT/lineup-sheet-$TAG-promoted-paid-vetted-30
log(){ printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
fail(){ mkdir -p "$PR"; printf '%s PROMOTION FAILED (exit %s): %s\n' "$(date -u +%H:%M:%SZ)" "${2:-2}" "$1" | tee -a "$PR/PROMOTION-FAILED.txt"; rm -rf "$STAGE"; exit "${2:-2}"; }
for f in "$VET/book.csv" "$VET/vetting_final.json" "$VET/replace.json" "$VET/frame.parquet" "$VET/source_receipt.json" "$OUT/contests.json" "$ORIG" "$RUN/candidates.parquet" "$RUN/receipt.json" "$AFTER/replacement-status.txt"; do [ -e "$f" ] || fail "missing $f"; done
[ ! -e "$VET/NOT-PUBLISHABLE-REHEARSAL" ] || fail "rehearsal marker present in $VET"
grep -qE '^OK' "$AFTER/replacement-status.txt" || fail "replacement status not OK: $(cat "$AFTER/replacement-status.txt")"
[ ! -e "$PROMOTED" ] || fail "$PROMOTED exists (create-once; remove it deliberately to re-run)"
[ ! -e "$UP" ] || fail "$UP exists"
for t in vet_book.py qb_classify.py; do [ -e "$TOOLS/$t" ] || fail "missing $TOOLS/$t"; done
for t in promote_first.py first_delivered_promotion.py; do [ -e "$PT/$t" ] || fail "missing $PT/$t"; done
BS=$TOOLS/book_sheet.py; [ -e "$BS" ] || BS=/home/erich/week1-sunday/tools/book_sheet.py
mkdir -p "$PR"; rm -rf "$PR/staging" "$PR/vet-final" "$STAGE"; mkdir -p "$PR/staging" "$STAGE"
cp "$VET/book.csv" "$VET/frame.parquet" "$PR/staging/" && cp "$VET/source_receipt.json" "$PR/staging/receipt.json" || fail "staging copy"
QBF=""; [ -e "$AFTER/qb-flags.csv" ] && QBF=$AFTER/qb-flags.csv
log "final book $(sha256sum "$VET/book.csv" | cut -c1-16): running the cleared vetter ($(sha256sum "$TOOLS/vet_book.py" | cut -c1-16)) on it (frame = the run's own frame, unchanged)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PROD/src:$TOOLS $PY "$TOOLS/vet_book.py" "$PR/staging" --k 30 --season "$SEASON" --week "$WEEK" --output-dir "$PR/vet-final" ${QBF:+--qb-flags "$QBF"} > "$PR/vet-final.log" 2>&1 || fail "final-book vetter failed (see $PR/vet-final.log)"
log "applying the promotion rule (promote_first.py $(sha256sum "$PT/promote_first.py" | cut -c1-16), rule $(sha256sum "$PT/first_delivered_promotion.py" | cut -c1-16))"
PYTHONDONTWRITEBYTECODE=1 $LPY "$PT/promote_first.py" "$VET" "$RUN" "$PROMOTED" --final-vetting "$PR/vet-final" --contests "$OUT/contests.json" > "$PR/promote.log" 2>&1; RC=$?
if [ $RC -eq 3 ]; then
  MSG=$(grep -m1 'PROMOTION STOP' "$PR/promote.log")
  log "$MSG"
  log "NO UPLOAD IS SAFE (the chain's $ORIG included). Re-run the replacement with fresh status, then re-run this script:"
  log "  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PROD/src:$TOOLS $PY $TOOLS/vet_replace_v4.py $AFTER/paid-vetted $RUN $AFTER/paid-vetted-replaced-fresh --qb-flags $AFTER/qb-flags.csv --season $SEASON --week $WEEK --admit-risky"
  log "  then emit + sheet from $AFTER/paid-vetted-replaced-fresh exactly as the chain does, point make_page at them, and re-run run_promotion.sh with that dir as paid-vetted-replaced"
  fail "$MSG" 3
fi
[ $RC -eq 0 ] || fail "promote_first.py refused or failed: $(grep -m1 -E 'REFUSED|Error|error' "$PR/promote.log" || echo "see $PR/promote.log")"
# ---- staged publication ----
SUP=$STAGE/upload.csv
PYTHONPATH=$PROD/src $PY "$PROD/scripts/emit_dk_upload_csv_v1.py" --source run-dir --run-dir "$PROMOTED" --output "$SUP" > "$PROMOTED/emit.json" 2>&1 || fail "emit failed (see $PROMOTED/emit.json)"
mkdir -p "$STAGE/promoted-30" && head -n 31 "$PROMOTED/book.csv" > "$STAGE/promoted-30/book.csv" && cp "$RUN/frame.parquet" "$RUN/receipt.json" "$STAGE/promoted-30/" || fail "sheet staging"
$LPY "$BS" "$STAGE/promoted-30" --banks-from "$RUN" --output "$STAGE/sheet" > "$STAGE/promoted-30/sheet.out" 2>&1 || fail "promoted keepers sheet failed (see $STAGE/promoted-30/sheet.out)"
[ -s "$STAGE/sheet.csv" ] && [ -s "$STAGE/sheet.md" ] || fail "sheet outputs missing"
if ! $LPY - "$ORIG" "$SUP" "$PROMOTED/promotion.json" "$PR/PROMOTION-RECORD.md" "$TAG" "$UP" "$SHEET" "$STAGE/sheet.csv" <<'PYV'
import sys, json, hashlib, csv
a = open(sys.argv[1]).read().splitlines(); b = open(sys.argv[2]).read().splitlines(); p = json.load(open(sys.argv[3]))
perm = p["permutation"]  # index = position after (1-based) -> position before
ok = a[0] == b[0] and len(a) == len(b) == len(perm) + 1 and all(b[i] == a[perm[i - 1]] for i in range(1, len(a))) and sorted(a[1:]) == sorted(b[1:])
if not ok: print("PERMUTATION CHECK FAILED: staged upload is not the recorded permutation of the chain's upload"); sys.exit(2)
sheet = list(csv.reader(open(sys.argv[8])))
if len(sheet) < 31 or sheet[1][0] != "1": print("SHEET CHECK FAILED: promoted keepers sheet malformed"); sys.exit(2)
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
k = p["promotion"]["promoted_from_rank"]
lines = [f"# Promotion record {sys.argv[5]}", "", f"rule: first_delivered_promotion.py sha256 {p['rule_sha256']}", f"tool: {p['tool']}", f"final vetting: {p.get('final_vetting_version')} at {p.get('final_vetted_at_utc')}",
         f"promoted_from_rank: {k}", f"selection_mean: {p['promotion'].get('selection_mean')}", f"eligible_delivered_ranks: {p['promotion'].get('eligible_delivered_ranks')}", f"changed: {p['changed']}",
         f"tier_counts: {p['tier_counts']}", f"fresh_status_raises: {p.get('fresh_status_raises')}", f"moved_rows: {p['moved_rows']}", f"bindings: {p['bindings']}", "",
         f"chain upload (ROLLBACK): {sys.argv[1]}  sha256 {sha(sys.argv[1])}", f"promoted upload (UPLOAD THIS): {sys.argv[6]}  sha256 {sha(sys.argv[2])}  (verified in staging before publication)",
         f"promoted keepers sheet: {sys.argv[7]}.csv  sha256 {sha(sys.argv[8])}",
         f"input book.csv sha256 {p['input_sha256']['book.csv']}", f"promoted book.csv sha256 {p['output_sha256']['book.csv']}", f"final_vetting.json sha256 {p['input_sha256']['final_vetting.json']}", "",
         "rollback: upload the chain upload instead; nothing else was changed."]
open(sys.argv[4], "w").write("\n".join(lines) + "\n"); print("\n".join(lines[2:14]))
PYV
then fail "verification failed (nothing published)"; fi
# ENTER/ re-layout from the STAGED promoted upload (the chain's own layout code, vendored in relayout_enter.sh; verified, then an
# atomic bundle swap) -- the DK-entries watcher refills DKEntries-FILLED-keepers-first.csv from it within a minute.  Runs BEFORE
# the promoted upload/sheet become discoverable, so a failure here leaves ENTER/ and OUT_DIR exactly as the chain left them.
RL=$PT/relayout_enter.sh; [ -x "$RL" ] || fail "missing $RL"
CONTESTS_JSON=$OUT/contests.json PROD=$PROD PY=$PY "$RL" "$SUP" "$OUT" "$TAG-promoted" "$STAGE/sheet.md" > "$PR/relayout.log" 2>&1 || fail "ENTER re-layout failed (see $PR/relayout.log); ENTER/ unchanged, nothing published"
grep -q 'published bundle' "$PR/relayout.log" || fail "ENTER re-layout did not publish (see $PR/relayout.log)"
# atomic publication of the upload + sheet (same filesystem: AFTER_DIR lives under OUT_DIR in the chain layout)
mv -n "$STAGE/sheet.md" "$SHEET.md" && mv -n "$STAGE/sheet.csv" "$SHEET.csv" && mv -n "$SUP" "$UP" || fail "publication move failed"
[ -e "$UP" ] && [ -e "$SHEET.csv" ] || fail "published files missing after move"
K=$($LPY -c "import json;print(json.load(open('$PROMOTED/promotion.json'))['promotion']['promoted_from_rank'])")
printf 'PROMOTION STEP: OK: delivered rank %s -> 1 (mean rule, operator-authorized); upload file %s; rollback %s\n' "$K" "$(basename "$UP")" "$(basename "$ORIG")" >> "$OUT/TODAY-30-LATEST.md"
rm -rf "$STAGE"
log "done: UPLOAD $UP | ENTER -> $(readlink -f "$OUT/ENTER") | rollback $ORIG (and enter-bundles/$TAG) | record $PR/PROMOTION-RECORD.md"
