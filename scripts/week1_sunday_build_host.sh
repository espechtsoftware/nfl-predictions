#!/usr/bin/env bash
# Sunday 2026-09-13 autonomous pre-lock build (armed by nfl-week1-sunday-build.timer at 09:10 CT).
# Builds the corrected D800/D400 pair through the tracked runbook (publisher PREFLIGHT only), then
# builds a K90 book and emits draftable-ID upload CSVs for BOTH entry layouts from the run dirs.
# It does NOT publish (operator step 4a) and does NOT upload (DK UI).  Everything it writes is under
# /home/erich/week1-sunday/.  Idempotent per run id; re-run with a new RUN_TAG if needed.
set -uo pipefail
OUT=/home/erich/week1-sunday; mkdir -p "$OUT"
LOG="$OUT/build-$(date -u +%Y%m%dT%H%M%SZ).log"; exec > >(tee -a "$LOG") 2>&1
RUN_TAG=${RUN_TAG:-$(date -u +%Y%m%dt%H%Mz)-e7255e9}
RUNBOOK_TREE=/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912
CLONE=/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9
EMIT_TREE=/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912
PROD_PY=/home/erich/projects/nfl-predictions/.venv/bin/python
LAB_PY=/home/erich/projects/nfl2/.venv/bin/python
DOSE_FILE=/home/erich/week1-dose.env   # optional: PAID_LEV=320 PAID_BOOM=1280 (PREREG-090 consequence 1)
echo "== $(date -u) run tag $RUN_TAG"

# 1. the governed pair + preflight (D800 paid / D400 shadow), exactly as the tracked runbook does
WEEK1_UPLOAD_DIR="$OUT" "$RUNBOOK_TREE/scripts/week1_sunday_runbook.sh" --run-id "$RUN_TAG" | tee "$OUT/runbook-$RUN_TAG.txt"
PAID_DIR=$(grep -o '/home/erich[^ ]*results/live/2026-w01/[0-9TZ]*-e7255e9' "$OUT/runbook-$RUN_TAG.txt" | sed -n 1p)
SHADOW_DIR=$(grep -o '/home/erich[^ ]*results/live/2026-w01/[0-9TZ]*-e7255e9' "$OUT/runbook-$RUN_TAG.txt" | sed -n 2p)
echo "paid=$PAID_DIR shadow=$SHADOW_DIR"

# 2. K90 build for the unique-entry layout (nested: ranks 1-80 equal the paid K80 book)
( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
    --season 2026 --week 1 --group 151307 --selector dual_emax --lev 160 --boom 640 --sims 10000 --k 1 \
    --seed 2026 --entries 90 --emit-a5-sidecars > /dev/null 2> "$OUT/k90-$RUN_TAG.err" )
K90_DIR="$CLONE/results/live/2026-w01/$(cat "$CLONE/results/live/2026-w01/LATEST")"
echo "k90=$K90_DIR"
# 2b. frozen within-book ORDERING shadows (outcome-blind; graded Monday against the entered 30): top-30 sets under
#     greedy / sim-mean / q99 / P>=line / novelty ladder / broad phenotype / random, from the K90's own banks
( cd "$CLONE" && PYTHONPATH="/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/src" "$LAB_PY" \
    /home/erich/week1-sunday/tools/ordering_shadows.py "$K90_DIR" --k 30 --output "$OUT/ordering_shadows-$RUN_TAG-k30.json" \
    > "$OUT/ordering_shadows-$RUN_TAG-k30.txt" 2>&1 ) && echo "ordering shadows -> $OUT/ordering_shadows-$RUN_TAG-k30.json" || echo "ORDERING SHADOWS FAILED (see $OUT/ordering_shadows-$RUN_TAG-k30.txt)"

# 3. optional D1600 paid arm (only if PREREG-090 consequence 1 fired; recorded in $DOSE_FILE)
if [[ -f "$DOSE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$DOSE_FILE"
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
      --season 2026 --week 1 --group 151307 --selector dual_emax --lev "${PAID_LEV:-320}" --boom "${PAID_BOOM:-1280}" \
      --sims 10000 --k 1 --seed 2026 --entries 90 --emit-a5-sidecars > /dev/null 2> "$OUT/d1600-$RUN_TAG.err" )
  D1600_DIR="$CLONE/results/live/2026-w01/$(cat "$CLONE/results/live/2026-w01/LATEST")"
  ( cd "$CLONE" && PYTHONPATH="/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/src" "$LAB_PY" \
      /home/erich/week1-sunday/tools/ordering_shadows.py "$D1600_DIR" --k 30 --output "$OUT/ordering_shadows-$RUN_TAG-dose-k30.json" \
      > "$OUT/ordering_shadows-$RUN_TAG-dose-k30.txt" 2>&1 ) && echo "dose ordering shadows -> $OUT/ordering_shadows-$RUN_TAG-dose-k30.json" || echo "DOSE ORDERING SHADOWS FAILED"
  echo "d1600=$D1600_DIR"
fi

# 3b. optional D1600_NOV live arm (operator opt-in: touch /home/erich/week1-nov.env): D1600 K80 with sidecars, then
#     PREREG-060's frozen novelty-ladder selector over that pool (tools/nov_book.py); CSVs for ranks 1-11 and 1-30
if [[ -f /home/erich/week1-nov.env ]]; then
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
      --season 2026 --week 1 --group 151307 --selector dual_emax --lev 320 --boom 1280 --sims 10000 --k 1 \
      --seed 2026 --entries 80 --emit-a5-sidecars > /dev/null 2> "$OUT/nov-d1600-$RUN_TAG.err" )
  NOV_SRC_DIR="$CLONE/results/live/2026-w01/$(cat "$CLONE/results/live/2026-w01/LATEST")"
  NOV_DIR="$OUT/nov-D1600-$RUN_TAG"
  ( cd "$CLONE" && PYTHONPATH="/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/src" "$LAB_PY" \
      /home/erich/week1-sunday/tools/nov_book.py "$NOV_SRC_DIR" --k 80 --output-dir "$NOV_DIR" > "$OUT/nov-book-$RUN_TAG.txt" 2>&1 ) \
    && echo "nov book -> $NOV_DIR (source $NOV_SRC_DIR)" || echo "NOV BOOK FAILED (see $OUT/nov-book-$RUN_TAG.txt)"
fi

# 4. upload CSVs (draftable ids) from run dirs: P_CTRL-equivalent for both layouts
emit() {  # $1 run dir, $2 label, $3 ranks
  ( cd "$EMIT_TREE" && PYTHONPATH="$EMIT_TREE/src" "$PROD_PY" scripts/emit_dk_upload_csv_v1.py --source run-dir \
      --run-dir "$1" --ranks "$3" --output "$OUT/upload-$RUN_TAG-$2-ranks-$3.csv" > "$OUT/upload-$RUN_TAG-$2-ranks-$3.receipt.json" 2>&1 ) \
    && echo "emitted $2 $3" || echo "EMIT FAILED $2 $3"
}
emit "$PAID_DIR" k80-milly-193028206 1-57;    emit "$PAID_DIR" k80-playaction-193028208 1-20
emit "$PAID_DIR" k80-ffwc-q6-194478066 1-3;   emit "$PAID_DIR" k80-ffwc-q5-194478065 1-10
emit "$K90_DIR"  k90-milly-193028206 1-57;    emit "$K90_DIR"  k90-playaction-193028208 58-77
emit "$K90_DIR"  k90-ffwc-q6-194478066 78-80; emit "$K90_DIR"  k90-ffwc-q5-194478065 81-90
# 30-entry layout (operator decision 2026-09-13): ranks 1-30 of the same nested book, one lineup per entry
emit "$K90_DIR"  k30-milly-193028206 1-19;    emit "$K90_DIR"  k30-playaction-193028208 20-26
emit "$K90_DIR"  k30-ffwc-q6-194478066 27-27; emit "$K90_DIR"  k30-ffwc-q5-194478065 28-30
# 2c. post-selection VETTING pass (operator request 2026-09-13): every player in every lineup is checked against live
#     availability signals (DK status, injury report, practice, depth, prop-line presence/vanishing, placeholder salary);
#     hard flags are vetoed to the back, material risk (Q/D, silent-market DNP, no props) is demoted behind clean
#     lineups, soft flags are reported; the vetted book keeps the selector's order otherwise.  Report + vetted CSVs.
VET_DIR="$OUT/vetted-$RUN_TAG"
( cd "$EMIT_TREE" && PYTHONPATH="$EMIT_TREE/src" "$PROD_PY" /home/erich/week1-sunday/tools/vet_book.py "$K90_DIR" --k 30 --output-dir "$VET_DIR" > "$OUT/vetting-$RUN_TAG.txt" 2>&1 ) \
  && { echo "vetted book -> $VET_DIR (report $VET_DIR/vetting_report.md)"; grep -A0 "demoted_out_of_top_k" "$OUT/vetting-$RUN_TAG.txt" | head -1
       emit "$VET_DIR" vetted-milly-193028206 1-19; emit "$VET_DIR" vetted-playaction-193028208 20-26
       emit "$VET_DIR" vetted-ffwc-q6-194478066 27-27; emit "$VET_DIR" vetted-ffwc-q5-194478065 28-30; emit "$VET_DIR" vetted-all30 1-30; emit "$VET_DIR" vetted-all90 1-90; } \
  || echo "VETTING FAILED (see $OUT/vetting-$RUN_TAG.txt)"

# 2d. post-selection PLAYER-SCORING RESORT (operator request 2026-09-13): independent per-player projected score
#     (production proj/p90/P20+, market-implied points and movement, both laws' player tails, prior-season DK ppg,
#     vetting penalty), lineup = sum, book re-sorted; frozen weights v1.  Report + composite CSVs.
COMP_DIR="$OUT/composite-$RUN_TAG"
( cd "$EMIT_TREE" && PYTHONPATH="$EMIT_TREE/src" "$PROD_PY" /home/erich/week1-sunday/tools/player_score.py "$K90_DIR" --k 30 --vetting "$VET_DIR/vetting.json" --output-dir "$COMP_DIR" > "$OUT/composite-$RUN_TAG.txt" 2>&1 ) \
  && { echo "composite book -> $COMP_DIR"; grep -m1 "overlap_top_k_with_greedy" "$OUT/composite-$RUN_TAG.txt"
       emit "$COMP_DIR" composite-milly-193028206 1-19; emit "$COMP_DIR" composite-playaction-193028208 20-26
       emit "$COMP_DIR" composite-ffwc-q6-194478066 27-27; emit "$COMP_DIR" composite-ffwc-q5-194478065 28-30; emit "$COMP_DIR" composite-all30 1-30; emit "$COMP_DIR" composite-all90 1-90; } \
  || echo "COMPOSITE FAILED (see $OUT/composite-$RUN_TAG.txt)"

# 30-entry HYBRID (greedy core 15 + the 15 broadest of ranks 16-90; replicated +1.4/+2.4 on two opened samples)
HYB_DIR="$OUT/hybrid15-$RUN_TAG"
( cd "$CLONE" && "$LAB_PY" /home/erich/week1-sunday/tools/hybrid30.py "$K90_DIR" --core 15 --k 30 --output-dir "$HYB_DIR" > "$OUT/hybrid15-$RUN_TAG.txt" 2>&1 ) \
  && { echo "hybrid15 -> $HYB_DIR"; emit "$HYB_DIR" hybrid15-milly-193028206 1-19; emit "$HYB_DIR" hybrid15-playaction-193028208 20-26
       emit "$HYB_DIR" hybrid15-ffwc-q6-194478066 27-27; emit "$HYB_DIR" hybrid15-ffwc-q5-194478065 28-30; emit "$HYB_DIR" hybrid15-all30 1-30; } \
  || echo "HYBRID15 FAILED (see $OUT/hybrid15-$RUN_TAG.txt)"
if [[ -n "${NOV_DIR:-}" && -f "$NOV_DIR/book.csv" ]]; then
  emit "$NOV_DIR" nov-d1600-playaction-193028208 1-7; emit "$NOV_DIR" nov-d1600-ffwc-q6-194478066 8-8; emit "$NOV_DIR" nov-d1600-ffwc-q5-194478065 9-11
  emit "$NOV_DIR" nov-d1600-all30 1-30; emit "$NOV_DIR" nov-d1600-milly-193028206 1-19
fi
if [[ -n "${D1600_DIR:-}" ]]; then
  emit "$D1600_DIR" d1600-milly-193028206 1-57;    emit "$D1600_DIR" d1600-playaction-193028208 58-77
  emit "$D1600_DIR" d1600-ffwc-q6-194478066 78-80; emit "$D1600_DIR" d1600-ffwc-q5-194478065 81-90
  emit "$D1600_DIR" dose-k30-milly-193028206 1-19;    emit "$D1600_DIR" dose-k30-playaction-193028208 20-26
  emit "$D1600_DIR" dose-k30-ffwc-q6-194478066 27-27; emit "$D1600_DIR" dose-k30-ffwc-q5-194478065 28-30
fi
echo "== done $(date -u). Operator steps remaining: publish (runbook 4a, run id $RUN_TAG) -> emit P_MIX from the published books (4b) -> upload in the DK UI by 11:15 CT."
