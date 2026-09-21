# Operator runbook — the four Week-3 items

Written 2026-09-21. Every command below was checked against the live system on
this host; the digests, paths, pids and log strings are real, not examples.
Do them in this order. Items 1 and 2 both feed the build gate; item 4 is the one
to do at a quiet moment.

---

## 1. Repoint `project-slate` at the repaired image

**Why:** the build-input gate fails closed while
`nfl_predictions.market_source_log` is absent, and only the repaired image
writes it. Until this is done the Week-3 build will not start.

**Current state, verified:**

    current: …/nfl-dfs/nfl-dfs@sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758
    target:  …/nfl-dfs/nfl-dfs:week3-market-source-cf630a68
             = sha256:efffac0a623e891813b2387f84ea725622cd32264b0c467d884e669ed47c5188

**Run:**

    gcloud run jobs update project-slate \
      --project nfl-predictions-503414 --region us-central1 \
      --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week3-market-source-cf630a68

**Then produce a batch.** Either wait for `s-project-tu` (Tuesday 09:30 CT) or
force one now:

    gcloud run jobs execute project-slate \
      --project nfl-predictions-503414 --region us-central1 --wait

**Verify by the JOB LOG, not by the table.** Two lines to look for:

    market blend source: props (N/M rows)      <- the repair working
    market-source log: N rows (props=…)        <- the monitor row write

    gcloud logging read \
      'resource.type="cloud_run_job" AND resource.labels.job_name="project-slate"' \
      --project nfl-predictions-503414 --limit 200 --format='value(textPayload)' \
      | grep -E "market blend source|market-source log"

**If the gate is still red afterwards**, read the log for this line before
suspecting the image — the write is deliberately best-effort and swallows its
own failure:

    market-source log write failed; projections unaffected but the monitor is blind for this batch

**Rollback** if `market blend source` does not say `props`:

    gcloud run jobs update project-slate \
      --project nfl-predictions-503414 --region us-central1 \
      --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758

---

## 2. Create the two Week-3 input files

`/home/erich/week3-sunday` does not exist yet.

    mkdir -p /home/erich/week3-sunday

**`/home/erich/week3-sunday/chosen-dose.env`** — two positive integers, exactly
these key names. Week 2 used 2560 / 10240:

    CHOSEN_LEV=2560
    CHOSEN_BOOM=10240

**`/home/erich/week3-sunday/contests.json`** — a JSON **list**, one object per
contest, with these six keys. `entries` must total **at least 90** across the
file or the gate refuses:

    [
      {"name": "…", "contest_id": "…", "entries": 1, "keep": 1, "fee": 20, "note": "…"}
    ]

`contest_id` and `name` are strings; `entries`, `keep`, `fee` are integers.
Week 2 had 12 contests totalling 97 entries. `/home/erich/week2-sunday/contests.json`
is the working example to copy the shape from.

**Verify both:**

    cd /home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921
    /home/erich/projects/nfl-predictions/.venv/bin/python scripts/check_build_inputs.py \
      --season 2026 --week 3 \
      --chosen-dose /home/erich/week3-sunday/chosen-dose.env \
      --contests /home/erich/week3-sunday/contests.json

Expect the `files` line to stop complaining. Projections and the TabPFN cache
will still fail until the Tuesday chain and Wednesday `tabpfn-gen` have run;
that is normal this early.

---

## 3. Delete the 32 orphan SIS rows

**Why:** 2026 Week 1 holds 64 rows where every other season-week holds 32. The
32 with a null team are unresolved duplicates from a loader defect that is now
fixed. Nothing on the money path reads this table.

**Run:**

    DELETE FROM `nfl-predictions-503414.nfl_raw.sis_team_context_game`
    WHERE season = 2026 AND week = 1 AND team IS NULL

**Expect:** 32 rows deleted.

**Verify:**

    SELECT week, COUNT(*) n, COUNTIF(team IS NULL) nulls
    FROM `nfl-predictions-503414.nfl_raw.sis_team_context_game`
    WHERE season = 2026 GROUP BY 1 ORDER BY 1

Expect week 1 → 32 rows, 0 nulls. Week 2 → 2 rows, 0 nulls (that is the
Thursday game, loaded mid-week; not a fault).

---

## 4. Swap the DraftKings host loop

**Why:** Cloud Run `ingest-dk` has failed 60+ consecutive runs on the DraftKings
403 egress block. Salaries stay current only because an unsupervised five-day-old
prototype is pulling them. If it dies, salaries stop silently and there is no
fallback.

**Do this at a quiet moment, not Saturday.** The ordering below matters and the
guard now enforces it.

**a. See what is running:**

    ps -p 4129 -o pid,etime,cmd
    cat /home/erich/week1-sunday/host_ingest_dk_loop.pid

**b. Make the unit's `ExecStart` resolvable.** It points at
`~/projects/nfl-predictions/scripts/host_ingest_dk_loop.sh`, which is not on the
branch that checkout currently holds. Bring just that one file across without
switching branches:

    git -C /home/erich/projects/nfl-predictions checkout \
      production/week3-integration-20260921 -- scripts/host_ingest_dk_loop.sh
    ls -l /home/erich/projects/nfl-predictions/scripts/host_ingest_dk_loop.sh

**Do not enable the unit before this file exists.** With
`StartLimitIntervalSec=0` and `RestartSec=60s` there is no rate limiter, so it
would restart forever every 60 seconds.

**c. Validate without touching the running loop** (`--check` exits before any
locking):

    PROD=/home/erich/projects/nfl-predictions \
      bash /home/erich/projects/nfl-predictions/scripts/host_ingest_dk_loop.sh --check

**d. Install the unit:**

    mkdir -p ~/.config/systemd/user
    cp /home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/deploy/systemd/nfl-host-dk-ingest.service \
       ~/.config/systemd/user/
    systemctl --user daemon-reload

**e. Stop the prototype and confirm it is gone:**

    kill 4129
    sleep 3
    ps -p 4129 || echo "prototype stopped"
    rm -f /home/erich/week1-sunday/host_ingest_dk_loop.pid

**f. Start the supervised loop:**

    systemctl --user enable --now nfl-host-dk-ingest.service
    systemctl --user status nfl-host-dk-ingest.service --no-pager

**Verify a pull within the hour:**

    journalctl --user -u nfl-host-dk-ingest -n 40 --no-pager

Look for `starting ingest-dk`, then `ingest-dk exit=0`, then
`host DK ingest pair succeeded`.

**Confirm salaries are still landing:**

    SELECT MAX(pulled_at) FROM `nfl-predictions-503414.nfl_raw.dk_salaries`

**If the unit refuses to start** saying a pid is still running, the prototype is
alive — that is the guard working. Finish step (e) first.

**Rollback:**

    systemctl --user disable --now nfl-host-dk-ingest.service
    setsid nohup bash /home/erich/week1-sunday/host_ingest_dk_loop.sh \
      > /home/erich/week1-sunday/host_dk_loop.log 2>&1 < /dev/null &

---

## Separately, and not urgent

`check-freshness` has exited 1 every day for about six days on exactly one feed:
`raw.cfb_dk_salaries`, stale 138h against a 36h limit, because `ingest-cfb` hits
the same DraftKings 403 with no host fallback. **Every NFL feed it checks is
fresh.** Until CFB is either restored or scoped out of the gate, a red freshness
check tells you nothing, and a genuine NFL staleness would arrive as one more
line in an already-failing check.
