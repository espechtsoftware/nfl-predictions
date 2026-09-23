#!/usr/bin/env bash
# Wait for the first project-slate execution that SUCCEEDS with `market blend source: props`, then check it once:
#   1. resolve the deployed code commit from the execution image's Cloud Build (_CODE_SHA);
#   2. re-run week3_availability_dry_run.py at that commit (expected gate / haircut / cascade counts);
#   3. week3_proof_lines.py --execution <it> --expected <dry run> --digest <its image digest>;
#   4. week3_phantom_scan.py on that batch, watching Justin Jefferson's market source (must be props).
# Writes ~/.cache/laptop-agent/props-run-check-<execution>.txt, prints a one-line summary and exits (one event).
#   bash props_run_watcher.sh [week=3] [group=153769]
set -uo pipefail
WEEK=${1:-3}; GROUP=${2:-153769}; P=nfl-predictions-503414; R=us-central1
HERE=$(cd "$(dirname "$0")" && pwd); PROD=$(cd "$HERE/../.." && pwd)
PY=${PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
DEPLOYED_WT=${DEPLOYED_WT:-/home/erich/projects/.nfl-predictions-worktrees/deployed-8745ab00}
SEEN=$HOME/.cache/laptop-agent/props-watcher-seen.txt; touch "$SEEN"
while true; do
  # FORCE_EX=<execution> (testing only): check that one execution now, whatever its outcome, and exit
  for ex in ${FORCE_EX:-$(gcloud run jobs executions list --job project-slate --region $R --project $P --limit 5 --format="value(name)" 2>/dev/null)}; do
    [[ -z "${FORCE_EX:-}" ]] && grep -qx "$ex" "$SEEN" && continue
    st=$(gcloud run jobs executions describe "$ex" --region $R --project $P --format="value(status.completionTime,status.succeededCount)" 2>/dev/null)
    [[ -z "$(echo "$st" | cut -f1)" ]] && continue                       # still running
    [[ -z "${FORCE_EX:-}" ]] && echo "$ex" >> "$SEEN"
    [[ "$(echo "$st" | cut -f2)" == "1" ]] || [[ -n "${FORCE_EX:-}" ]] || continue   # failed (e.g. coverage floor): keep waiting
    src=$(gcloud logging read "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$ex\" AND textPayload:\"market blend source\"" \
          --project $P --freshness 3d --limit 1 --format="value(textPayload)" 2>/dev/null)
    [[ "$src" == *"market blend source: props"* ]] || [[ -n "${FORCE_EX:-}" ]] || continue   # model_only success: keep waiting
    OUT=$HOME/.cache/laptop-agent/props-run-check-$ex.txt
    img=$(gcloud run jobs executions describe "$ex" --region $R --project $P --format="value(spec.template.spec.containers[0].image)")
    digest=${img##*@}
    sha=$(gcloud builds list --project $P --limit 40 --format="value(substitutions._CODE_SHA,results.images[0].digest)" 2>/dev/null | awk -v d="$digest" '$2==d{print $1; exit}')
    {
      echo "execution $ex  image $digest  code $sha  $(date '+%F %T %Z')"
      echo "$src"
      if [[ -n "$sha" ]] && { git -C "$DEPLOYED_WT" fetch -q origin 2>/dev/null || true; } && git -C "$DEPLOYED_WT" checkout -q --detach "$sha" 2>/dev/null; then
        PYTHONPATH="$DEPLOYED_WT/src" "$PY" "$HERE/week3_availability_dry_run.py" --season 2026 --week "$WEEK" > "$OUT.dryrun" 2>&1
        echo "--- dry run at $sha: $(grep -E 'backup-QB gate:|questionable haircut:|cascade: adjusted' "$OUT.dryrun" | tr '\n' ' ')"
        EXP=(--expected "$OUT.dryrun")
      else
        echo "--- could not resolve/check out the deployed commit; proof lines run without --expected"; EXP=()
      fi
      echo "--- proof lines"; "$PY" "$HERE/week3_proof_lines.py" --execution "$ex" --digest "$digest" "${EXP[@]}" 2>&1
      echo "--- phantom scan"; PYTHONPATH="$PROD/src" "$PY" "$HERE/week3_phantom_scan.py" --week "$WEEK" --group "$GROUP" --watch "Justin Jefferson" 2>&1 | grep -v -i warn
      echo "--- name resolution"; gcloud logging read "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$ex\" AND (textPayload:\"prop market names\" OR textPayload:\"live market sources\")" \
          --project $P --freshness 3d --limit 4 --format="value(textPayload)" | cut -c1-400
    } > "$OUT" 2>&1
    echo "PROPS RUN CHECKED: $ex -> $OUT :: proof $(grep -E '^(PASS|FAIL)$' "$OUT" | tail -1) / phantom $(grep -E '^(CLEAN|FLAGGED)$' "$OUT" | tail -1)"
    exit 0
  done
  sleep 600
done
