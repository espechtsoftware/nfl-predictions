#!/usr/bin/env bash
# Autonomous pre-lock Sunday build for any regular-season week (generalised from the Week-1 host driver, which is
# kept as scripts/week1_sunday_build_host.sh).  Armed by a one-shot user timer at 09:10 CT and again at 10:50 CT
# (T-70, after the 10:30 CT inactives; see scripts/arm_week_timers.sh).  Builds the D800/D400 pair through
# scripts/sunday_runbook.sh, then the K90 nested book, ordering shadows, vetting, composite, hybrid15, and emits
# draftable-ID upload CSVs per contest from $CONTESTS_JSON.  It never publishes and never uploads.
#
#   source scripts/week_env.sh && week_env 2 [GROUP]; scripts/sunday_build_host.sh          # RUN_TAG defaults to now
#   RUN_TAG=20260920t1550z-e7255e9 scripts/sunday_build_host.sh                             # T-70 rebuild
set -uo pipefail
: "${WEEK:?source scripts/week_env.sh and call week_env WEEK first}"
: "${GROUP:?}" "${OUT:?}" "${CLONE:?}" "${PROD:?}" "${PROD_PY:?}" "${LAB_PY:?}" "${TOOLS:?}" "${CONTESTS_JSON:?}" "${WEEKDIR:?}" "${RUN_SUFFIX:?}"
mkdir -p "$OUT"
LOG="$OUT/build-$(date -u +%Y%m%dT%H%M%SZ).log"; exec > >(tee -a "$LOG") 2>&1
RUN_TAG=${RUN_TAG:-$(date -u +%Y%m%dt%H%Mz)-$RUN_SUFFIX}
DOSE_FILE=${DOSE_FILE:-/home/erich/week${WEEK}-dose.env}   # optional: PAID_LEV=320 PAID_BOOM=1280
LIVE="$CLONE/results/live/$WEEKDIR"
echo "== $(date -u) week $WEEK group $GROUP run tag $RUN_TAG"
[[ -f "$CONTESTS_JSON" ]] || { echo "contests file missing: $CONTESTS_JSON (copy scripts/contests.template.json and fill the week's contest ids)"; exit 2; }
"$PROD_PY" - "$CONTESTS_JSON" <<'PYEOF' || exit 2
import json, sys
c = json.load(open(sys.argv[1]))
assert isinstance(c, list) and c, "contests.json must be a non-empty list"
for x in c:
    assert set(x) >= {"name", "contest_id", "entries", "keep"} and str(x["contest_id"]).isdigit() and x["entries"] >= x["keep"] >= 0, x
    assert "REPLACE" not in json.dumps(x), f"contests.json still holds a template entry: {x}"
tot = sum(x["entries"] for x in c); keep = sum(x["keep"] for x in c)
print(f"contests: {[(x['name'], x['contest_id'], x['entries'], x['keep']) for x in c]} total entries {tot} keepers {keep}")
assert tot <= 90, "the nested K90 build covers at most 90 reserved entries"
PYEOF

# 1. the governed pair (D800 paid / D400 shadow) with receipt checks.  REUSE_PAID_DIR/REUSE_SHADOW_DIR (and
#    REUSE_K90_DIR below) let a rehearsal exercise everything downstream of the builds on existing run dirs.
"$PROD/scripts/sunday_runbook.sh" --run-id "$RUN_TAG" ${REUSE_PAID_DIR:+--paid-dir "$REUSE_PAID_DIR"} ${REUSE_SHADOW_DIR:+--shadow-dir "$REUSE_SHADOW_DIR"} | tee "$OUT/runbook-$RUN_TAG.txt"
PAID_DIR=$(grep -o '^paid=.*' "$OUT/runbook-$RUN_TAG.txt" | cut -d= -f2-)
SHADOW_DIR=$(grep -o '^shadow=.*' "$OUT/runbook-$RUN_TAG.txt" | cut -d= -f2-)
[[ -d "$PAID_DIR" && -d "$SHADOW_DIR" ]] || { echo "runbook did not produce the pair"; exit 1; }
echo "paid=$PAID_DIR shadow=$SHADOW_DIR"

# 2. K90 nested build (ranks 1-80 equal the paid K80 book)
if [[ -n "${REUSE_K90_DIR:-}" ]]; then
  K90_DIR=$REUSE_K90_DIR; echo "reusing K90 run dir (rehearsal)"
else
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
      --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector dual_emax --lev "${PAID_LEV:-160}" --boom "${PAID_BOOM:-640}" --sims 10000 --k 1 \
      --seed 2026 --entries 90 --emit-a5-sidecars > /dev/null 2> "$OUT/k90-$RUN_TAG.err" )
  K90_DIR="$LIVE/$(cat "$LIVE/LATEST")"
fi
[[ -f "$K90_DIR/receipt.json" ]] || { echo "K90 build failed (see $OUT/k90-$RUN_TAG.err)"; exit 1; }
echo "k90=$K90_DIR"
# 2b. within-book ordering shadows (outcome-blind; graded after settlement)
( cd "$CLONE" && PYTHONPATH="/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/src" "$LAB_PY" \
    "$TOOLS/ordering_shadows.py" "$K90_DIR" --k 30 --output "$OUT/ordering_shadows-$RUN_TAG-k30.json" \
    > "$OUT/ordering_shadows-$RUN_TAG-k30.txt" 2>&1 ) && echo "ordering shadows -> $OUT/ordering_shadows-$RUN_TAG-k30.json" || echo "ORDERING SHADOWS FAILED (see $OUT/ordering_shadows-$RUN_TAG-k30.txt)"

# 3. optional dose arm (only if the operator wrote $DOSE_FILE)
if [[ -f "$DOSE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$DOSE_FILE"
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
      --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector dual_emax --lev "${PAID_LEV:-320}" --boom "${PAID_BOOM:-1280}" \
      --sims 10000 --k 1 --seed 2026 --entries 90 --emit-a5-sidecars > /dev/null 2> "$OUT/dose-$RUN_TAG.err" )
  DOSE_DIR="$LIVE/$(cat "$LIVE/LATEST")"; echo "dose=$DOSE_DIR"
fi

# 4. per-contest upload CSVs (draftable ids) from run dirs
emit() {  # $1 run dir, $2 label, $3 ranks
  ( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" scripts/emit_dk_upload_csv_v1.py --source run-dir \
      --run-dir "$1" --ranks "$3" --output "$OUT/upload-$RUN_TAG-$2-ranks-$3.csv" > "$OUT/upload-$RUN_TAG-$2-ranks-$3.receipt.json" 2>&1 ) \
    && echo "emitted $2 $3" || echo "EMIT FAILED $2 $3"
}
# layouts: k80 = the paid book's first N per contest (same lineups in every contest); k90 = one unique lineup per
# reserved entry (sequential ranks); k30 = the keepers only (sequential ranks over the keep counts)
layouts=$("$PROD_PY" - "$CONTESTS_JSON" <<'PYEOF'
import json, sys
c = json.load(open(sys.argv[1])); p = 1; q = 1
for x in c:
    n, k = int(x["entries"]), int(x["keep"]); lab = f"{x['name']}-{x['contest_id']}"
    print(f"k80 {lab} 1-{n}"); print(f"k90 {lab} {p}-{p+n-1}"); p += n
    if k: print(f"k30 {lab} {q}-{q+k-1}"); q += k
PYEOF
)
while read -r layout lab ranks; do
  case "$layout" in
    k80) emit "$PAID_DIR" "k80-$lab" "$ranks" ;;
    k90) emit "$K90_DIR" "k90-$lab" "$ranks" ;;
    k30) emit "$K90_DIR" "k30-$lab" "$ranks" ;;
  esac
done <<< "$layouts"

# 5. vetting (HARD to the back, material demoted), composite resort, hybrid15 — all reported, none entered automatically
VET_DIR="$OUT/vetted-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/vet_book.py" "$K90_DIR" --k 30 --season "$SEASON" --week "$WEEK" --output-dir "$VET_DIR" > "$OUT/vetting-$RUN_TAG.txt" 2>&1 ) \
  && { echo "vetted book -> $VET_DIR (report $VET_DIR/vetting_report.md)"; grep -m1 "demoted_out_of_top_k" "$OUT/vetting-$RUN_TAG.txt"
       while read -r layout lab ranks; do [[ "$layout" == k30 ]] && emit "$VET_DIR" "vetted-$lab" "$ranks"; done <<< "$layouts"
       emit "$VET_DIR" vetted-all30 1-30; emit "$VET_DIR" vetted-all90 1-90; } \
  || echo "VETTING FAILED (see $OUT/vetting-$RUN_TAG.txt)"
COMP_DIR="$OUT/composite-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/player_score.py" "$K90_DIR" --k 30 --vetting "$VET_DIR/vetting.json" --output-dir "$COMP_DIR" > "$OUT/composite-$RUN_TAG.txt" 2>&1 ) \
  && { echo "composite book -> $COMP_DIR"; emit "$COMP_DIR" composite-all30 1-30; } || echo "COMPOSITE FAILED (see $OUT/composite-$RUN_TAG.txt)"
HYB_DIR="$OUT/hybrid15-$RUN_TAG"
( cd "$CLONE" && "$LAB_PY" "$TOOLS/hybrid30.py" "$K90_DIR" --core 15 --k 30 --output-dir "$HYB_DIR" > "$OUT/hybrid15-$RUN_TAG.txt" 2>&1 ) \
  && { echo "hybrid15 -> $HYB_DIR"; emit "$HYB_DIR" hybrid15-all30 1-30; } || echo "HYBRID15 FAILED (see $OUT/hybrid15-$RUN_TAG.txt)"
echo "== done $(date -u). The after-build chain (scripts/sunday_after_build.sh) writes ENTER/ and TODAY-30-LATEST.md from the vetted book; the operator uploads in the DK UI by 11:15 CT."
