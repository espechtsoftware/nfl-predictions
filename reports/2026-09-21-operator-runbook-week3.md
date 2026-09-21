# Operator runbook — the four Week-3 items

Written 2026-09-21. Every command below was **run** against the live system on
this host, not written from memory. Two errors were caught that way and are
noted where they occurred, so if something here looks over-explained, that is
why. Do the items in this order. Items 1 and 2 both feed the build gate; item 4
is the one to do at a quiet moment.

**One path caveat.** Steps 2 and 4 refer to

    /home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921

which is a working checkout of `production/week3-integration-20260921` created
during the 2026-09-21 session. If it is gone, recreate it anywhere convenient
and substitute that path throughout:

    git -C /home/erich/projects/nfl-predictions worktree add \
      /home/erich/projects/nfl-predictions-week3 \
      production/week3-integration-20260921

The Week-3 build needs a checkout of that branch regardless — the preflight
resolves its tools directory from `$PROD`, so the repaired host scripts reach the
money path through the checkout, not through the container image.

---

## 1. Repoint `project-slate` at the repaired image

**Why:** the build-input gate fails closed while
`nfl_predictions.market_source_log` is absent, and only the repaired image
writes it. Until that table exists the Week-3 build will not start.

> **STATUS 2026-09-21: the repoint is DONE.** The operator ran it and it was
> confirmed — `project-slate` now serves
> `…/nfl-dfs/nfl-dfs:week3-market-source-cf630a68`
> (`sha256:efffac0a623e891813b2387f84ea725622cd32264b0c467d884e669ed47c5188`),
> replacing `sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758`.
>
> **What is still outstanding is the second half: a batch has not run yet, so
> `market_source_log` is still absent and the gate is still red on the market
> check.** Skip to "Then produce a batch" below.
>
> Minor, for later: the job is now pinned by TAG rather than by digest. The
> previous setting was digest-pinned, which is more reproducible because a tag
> can be moved. Worth switching back once Week 3 is settled.

**The update command, for reference or a repeat:**

    gcloud run jobs update project-slate \
      --project nfl-predictions-503414 --region us-central1 \
      --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week3-market-source-cf630a68

**Then produce a batch.** Either wait for `s-project-tu` (Tuesday 09:30 CT) or
force one now:

    gcloud run jobs execute project-slate \
      --project nfl-predictions-503414 --region us-central1 --wait

**Verify by the JOB LOG, not by the table — and on the RIGHT line.**

**Corrected 2026-09-21 after testing this against the live logs.** An earlier
draft of this runbook said to check for `market blend source: props`. **That is
not a valid check**: the OLD image already logs it. Across the last 400
`project-slate` log entries, on the current image:

    "market blend source"  : 3 occurrences   <- old image logs this too, USELESS as a check
    "market-source log:"   : 0 occurrences   <- only the repaired image writes this

So the one line that proves the repoint took is:

    market-source log: N rows (props=…, …)

    gcloud logging read \
      'resource.type="cloud_run_job" AND resource.labels.job_name="project-slate"' \
      --project nfl-predictions-503414 --limit 200 --format='value(textPayload)' \
      | grep -E "market-source log:"

If that returns nothing, the repaired image did not run, whatever else the log
says. For context while reading: the old image logs
`market blend source: props (388/481 rows)`, i.e. it blends props for 388 of 481
players and silently falls back for the other 93. That silent fallback is the
Week-2 defect; under the repair every row's source is recorded instead.

**If the gate is still red afterwards**, read the log for this line before
suspecting the image — the write is deliberately best-effort and swallows its
own failure:

    market-source log write failed; projections unaffected but the monitor is blind for this batch

**Rollback** if no `market-source log:` line appears after a completed run:

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
      {"name": "milly",      "contest_id": "…", "entries":  1, "keep":  1, "fee": 20,   "note": "…"},
      {"name": "supersat25", "contest_id": "…", "entries": 16, "keep": 16, "fee": 0.25, "note": "…"}
    ]

`contest_id` and `name` are strings; `entries` and `keep` are integers; **`fee`
is money and may be fractional** — the quarter satellites carry `0.25`. An
earlier draft of this runbook called fee an integer, which was wrong: validating
it that way truncated those contests to zero and made Week 2 total $238 against
the $246 actually settled.

Week 2 had 12 contests totalling 97 entries. `/home/erich/week2-sunday/contests.json`
is the working example to copy the shape from; `config/week-inputs-schema.md`
is the field-by-field reference.

**Then put them where a lost machine cannot take them with it.** The repository
is PUBLIC, so these must not be committed — `contests.json` is the week's stake
plan. They go in the project's private bucket instead (no `allUsers` binding,
object generations give versioning):

    cd <integration checkout>
    /home/erich/projects/nfl-predictions/.venv/bin/python scripts/week_inputs.py \
      push --season 2026 --week 3 \
      --contests /home/erich/week3-sunday/contests.json \
      --dose /home/erich/week3-sunday/chosen-dose.env

It validates before uploading and refuses to publish an invalid pair. To install
them on any machine afterwards:

    … scripts/week_inputs.py pull --season 2026 --week 3 --out /home/erich/week3-sunday

`pull` validates before writing and leaves `week-inputs-receipt.json` pinning
each object by uri, generation and sha256. That receipt carries no contest ids
and no per-contest figures, so it is safe to commit as the record of which
inputs a build used. Shape is documented in `config/week-inputs-schema.md`.

**Verify both.** Quickest check first — it needs no network and reports every
problem at once:

    … scripts/week_inputs.py validate \
      --contests /home/erich/week3-sunday/contests.json \
      --dose /home/erich/week3-sunday/chosen-dose.env

On the real Week-2 pair that prints
`OK: 12 contests, 97 entries, $246.00 total fee; dose lev 2560 boom 10240`.
Then the gate's own view:

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

    SELECT week, COUNT(*) AS n, COUNTIF(team IS NULL) AS null_team
    FROM `nfl-predictions-503414.nfl_raw.sis_team_context_game`
    WHERE season = 2026 GROUP BY week ORDER BY week

(`nulls` is a BigQuery reserved word — an earlier draft used it as an alias and
the query failed outright with `Syntax error: … got keyword NULLS`. Tested as
written above.)

Before the delete it returns:

    week 1: 64 rows, 32 with a null team
    week 2:  2 rows,  0 with a null team

After, expect week 1 → 32 rows, 0 with a null team. Week 2 staying at 2 rows is
correct: that is the Thursday game, loaded mid-week, not a fault.

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

**This is now enforced, not just advised.** The unit carries
`ExecStartPre=/usr/bin/test -x …`, so it refuses to start without the script,
and `StartLimitIntervalSec=1h` with `StartLimitBurst=3` caps it at three
attempts an hour instead of the unbounded 60-second loop an earlier draft would
have produced. Doing step (b) first is still the point; the guard is the
backstop.

**The consequence to be aware of.** Ordinary failed pulls do NOT restart the
service — the loop logs `host DK ingest pair failed`, sleeps, and carries on, so
a bad hour costs nothing. `Restart=on-failure` only fires on something fatal.
But with the cap, three fatal failures in an hour leave the service **dead and
quiet**. That is the right trade against an infinite loop, and it is why the
freshness item below matters: a stopped DK ingest should be caught by
`check-freshness` going red on stale `dk_salaries`, and right now that check is
already red for an unrelated reason, so it would tell you nothing.

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
