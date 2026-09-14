#!/usr/bin/env bash
# PREREG-097 / experiment 117 registered FINISH launcher (banks only) (dose response 800 / 1600 / 3200, nested stream).
# Arm ONLY through production's scripts/launcher_registry.sh run (lane nfl2-lab-jobs), AFTER the
# 111/112 master queue has exited and both jobs carry the prereg09u image (CODE_SHA == HEAD).  Phases:
#   mechanics -> 117m970r1: one outcome-disabled slate (2023 W1) with --verify-prefix, 1 task
#   banks     -> 117b970r1 / 117b971r1 on the first free jobs, 117b972r1 on the first lane that frees;
#                72 tasks each, exact --bank=NNN argv.
# Reuses the two existing jobs (never creates one); never more than 2 non-terminal executions across
# both jobs (counting executions launched by earlier launchers); attach-aware (an existing result prefix
# is never relaunched); completion verified by succeeded count, never by prefix.
set -euo pipefail

cd /home/erich/projects/.nfl2-worktrees/prereg097-dose6400-20260913
ROOT=$PWD
LANE=nfl2-lab-jobs
SELF_REL=/home/erich/week1-sunday/queue_117_finish.sh
COORDINATION_REL=scripts/lab_launch_coordination.sh
PROJECT=nfl-2-506823; REGION=us-central1
EXPERIMENT=experiments/117_dose6400.py
RDIR=117_dose6400
TARGET_PREFIXES=117b970r1,117b971r1,117b972r1
LAB_LAUNCH_COORDINATION_CONTRACT=shared-provider-launch/v1

source "$ROOT/$COORDINATION_REL"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }   # stderr: launch() is command-substituted

HEAD_SHA=$(git rev-parse HEAD)
git diff --quiet -- . || die "tracked working tree is dirty"
git diff --cached --quiet -- . || die "index is dirty"
git branch -r --contains "$HEAD_SHA" | grep -q . || die "HEAD $HEAD_SHA is not on any remote branch (push first)"
[[ -n "${SKIP_REGISTRY_CHECK:-}" ]] || lab_require_launcher_registry "$ROOT" "$LANE" "$SELF_REL" "$TARGET_PREFIXES"
for job in lab-run lab-run-slow; do
  sha=$(gcloud run jobs describe "$job" --project "$PROJECT" --region "$REGION" --format=json \
        | jq -r '.spec.template.spec.template.spec.containers[0].env[] | select(.name == "CODE_SHA") | .value')
  [[ "$sha" == "$HEAD_SHA" ]] || die "$job CODE_SHA ($sha) != HEAD ($HEAD_SHA); update the jobs to the prereg09u image first"
done

active_count() {
  local n=0 job
  for job in lab-run lab-run-slow; do
    n=$((n + $(gcloud run jobs executions list --job "$job" --project "$PROJECT" --region "$REGION" --limit 10 \
        --format='value(status.completionTime)' | awk 'BEGIN{c=0} $0==""{c++} END{print c}')))
  done
  echo "$n"
}
job_busy() {
  gcloud run jobs executions list --job "$1" --project "$PROJECT" --region "$REGION" --limit 5 \
    --format='value(status.completionTime)' | awk 'BEGIN{c=0} $0==""{c++} END{print (c>0)?1:0}'
}
free_job() {
  local j
  for j in lab-run lab-run-slow; do
    [[ "$(job_busy "$j")" == "0" ]] && { echo "$j"; return; }
  done
  echo ""
}
execution_terminal() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" --region "$REGION" --format=json \
    | jq -r 'if (.status.completionTime // "") == "" then "" else
        "\(.status.succeededCount // 0) \(.status.failedCount // 0) \(.status.cancelledCount // 0) \(.status.runningCount // 0)" end'
}
prefix_exists() { gcloud storage ls "gs://nfl-2-506823-lab/results/$RDIR/" 2>/dev/null | grep -q "$1-"; }

launch() {  # $1 run prefix, $2 tasks, $3 args -> prints execution name
  local prefix=$1 tasks=$2 args=$3 rid out name job
  prefix_exists "$prefix" && die "prefix $prefix already has a result namespace; refusing to relaunch"
  while :; do
    job=$(free_job)
    [[ -n "$job" && "$(active_count)" -lt 2 ]] && break
    sleep 60
  done
  rid="${prefix}-$(date -u +%Y%m%dT%H%M%SZ)"
  lab_provider_launch_lock_acquire "$ROOT"
  [[ "$(active_count)" -lt 2 ]] || { lab_provider_launch_lock_release; die "capacity census changed under the lock"; }
  out=$(gcloud run jobs execute "$job" --project "$PROJECT" --region "$REGION" --tasks "$tasks" \
        --update-env-vars "RUN_ID=$rid" --args "^;^${EXPERIMENT};${args}" --format='value(metadata.name)' 2>&1) || {
    lab_provider_launch_lock_release; die "execute failed for $rid: $out"; }
  lab_provider_launch_lock_release
  name=$(printf '%s\n' "$out" | grep -o "${job}-[a-z0-9]\{5\}" | tail -1)
  [[ -n "$name" ]] || die "could not parse execution name from: $out"
  log "launched $rid as $name (job=$job tasks=$tasks args=$args)"
  printf '%s %s %s\n' "$rid" "$name" "$job" >> "$ROOT/results/queue_117_launches.log"
  echo "$name"
}
wait_terminal() {  # $1 execution, $2 expected succeeded
  local name=$1 expect=$2 state
  while :; do state=$(execution_terminal "$name"); [[ -n "$state" ]] && break; sleep 90; done
  read -r s f c r <<<"$state"
  log "terminal $name succeeded=$s failed=$f cancelled=$c running=$r"
  [[ "$s" == "$expect" && "$f" == "0" && "$c" == "0" && "$r" == "0" ]] || die "execution $name did not complete cleanly"
}

mkdir -p "$ROOT/results"
# FINISH variant (2026-09-14): the mechanics gate 117m970r1-20260913T230639Z PASSED (scripts/prereg097_mechanics_gate.py); the original
# launcher died with the workstation shutdown before launching the banks. This launcher skips the gate phase.
log "cohort 117 (finish): gate already PASSED; launching banks"
n1=$(launch 117b970r1 72 "--bank=970")
n2=$(launch 117b971r1 72 "--bank=971")
while :; do s1=$(execution_terminal "$n1"); s2=$(execution_terminal "$n2"); [[ -n "$s1" || -n "$s2" ]] && break; sleep 90; done
n3=$(launch 117b972r1 72 "--bank=972")
wait_terminal "$n1" 72; wait_terminal "$n2" 72; wait_terminal "$n3" 72
log "cohort 117: all three banks terminal -- run scripts/prereg097_report.py"
