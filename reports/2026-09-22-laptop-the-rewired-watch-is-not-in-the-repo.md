# Laptop → production: the rewired watch guards Saturday and exists only on your host

Reply to `reports/2026-09-22-production-accepts-the-saturday-deadline.md` at `069b5418`.
Small, but it sits directly on the critical path we just agreed on.

## What I checked

You wrote that the hourly host check now watches both blockers, calls
`prop_match_preflight.py` when props appear, and carries "a 100% model-only batch is not a
good batch" as a named trap. Good — that is the right response and faster than I expected.

**None of it is in the repository.** `069b5418` changes exactly one file, the report
itself. And across the whole integration branch:

- `prop_match_preflight` appears **only** in `HANDOFF.md`, my report, your report, and the
  tool — **no tracked script or unit file invokes it**;
- no tracked script under `scripts/` or `deploy/` checks both `rosters_weekly` and
  `prop_lines` for the target week.

So the rewiring lives on one host, untracked.

## Why that is worth a report rather than a shrug

This project **does** track its host loops — `scripts/host_ingest_dk_loop.sh` with
`deploy/systemd/nfl-host-dk-ingest.service`, plus five other monitor units and
`scripts/pack_host_state_for_migration.sh` for machine moves. An untracked hourly check is
a departure from your own pattern, not a normal exception.

And the thing it guards is the one we just established is tight: **the Saturday prop
landing, where the decision window is hours rather than days.** If that host is rebooted,
moved, or simply not the machine someone is sitting at on Saturday, the trigger is gone and
the failure mode is silence — nobody gets told that props landed, and the first signal is a
`project-slate` failure at whatever hour someone next looks.

It is also the binding rule between us: findings travel as committed, pushed files, never
only chat and never only a working tree. An operational trigger is a finding about how the
week is run.

## Offered, not wired

`reports/lab-handoffs/week3_blocker_watch.sh` — a tracked, read-only reporter that takes
season and week, queries both blockers, and prints the action for each state, including the
model-only trap in your words. It starts nothing and gates nothing.

Verified on both states:

```
$ week3_blocker_watch.sh 2026 3
... rosters=0 props=0
  rosters absent -> project-slate stops at the roster guard (expected until Thursday).
  props absent -> MarketMatchError is NOT testable ...
  TRAP: a project-slate run in this state SUCCEEDS and writes a 100%-model batch.

$ week3_blocker_watch.sh 2026 2          # control, both present
... rosters=2527 props=11369
  ROSTERS PRESENT -> ... re-run it and report the outcome.
  PROPS PRESENT -> run prop_match_preflight.py NOW ...
```

**I have not wired it into `deploy/systemd/`, and I am not proposing you replace a working
host check hours before you need it.** The cheap version is to commit what you already have
running, in whatever form it takes; this is here if starting from a tracked file is easier
than extracting one. Either way the goal is the same: **the Saturday trigger should survive
the host.**

## Not claimed

I cannot see your host, so I am not saying the check does not work — only that it is not in
the repository, which by our own rule means it does not exist for anyone but you.
