# Laptop → production: fast enough, not provisioned — what a move would actually require

Companion to `scripts/solver_benchmark.laptop`. The benchmark says the laptop can run the
Saturday build in about six hours instead of ten. **Speed is not the binding constraint;
provisioning is.** This is what is true on this machine right now, checked rather than
assumed, so the operator decides with the whole picture.

## Ready

| item | state |
|---|---|
| single-core solver throughput | **24.4/s vs 14.19/s** — 1.72x, no decay over 300 s sustained |
| `nfl-predictions/.venv` | present, executable |
| `nfl2/.venv` | present, executable |
| gcloud auth + project | active, `espechtsoftware@gmail.com`, `nfl-predictions-503414` |
| production checkout | clean |

## Not ready — each one blocks a Sunday build

| gap | detail | who can close it |
|---|---|---|
| **live clone is the wrong commit** | `.nfl2-worktrees/week3-live-center` here is at **`2dc116c`**, not `69f98a7`. **The Doubtful fix is not on this machine.** | either agent; `git fetch` + checkout, clean |
| **operator inputs absent** | `/home/erich/week3-sunday/contests.json` and `chosen-dose.env` do not exist here | **operator only** — the stake plan, never committed; they are in `gs://…/week-inputs/2026/w03/` per the handover, so retrievable rather than reconstructed |
| **no DK host ingest loop** | no pid file, no process, no `nfl-host-dk-ingest` user unit here | operator arms it; see below |
| **no Week-3 timers** | `systemctl --user list-timers` shows zero `nfl-week3` units | operator, via `arm_week_timers.sh` |
| production checkout branch | on `main`, not the integration branch | either agent |

Only two user services run here: `nfl-production-review-inbox` and
`nfl-shared-handoff-inbox`, both read-only git inboxes. None of the money path.

## The one that would be forgotten

**DK ingest.** The handover is explicit that Cloud Run `ingest-dk` has failed 60+ runs on
a DraftKings 403 and that a **tracked host loop is the sole source of DK salaries**. That
loop runs on the workstation, not here. A build moved to this laptop without also moving
that loop would have **no salary source** — and it would not fail loudly at arm time, it
would fail when the slate could not be built.

The clone commit would fail closed (the runtime preflight checks `clone HEAD ==
EXPECT_SHA`, verified earlier today). The missing contest file would fail closed
(`check_week_runtime.py` requires it). **The DK loop has no equivalent arm-time gate in
the build path** — which makes it the item to put first on any move checklist, not last.

`scripts/pack_host_state_for_migration.sh` exists for exactly this and I have not run it;
it is the operator's tool and a move is the operator's decision.

## Recommendation

**Do not move the Saturday build on the strength of the benchmark alone.** The six-hour
figure is real and the thermal behaviour holds, but the workstation is provisioned and
this machine is not, and the gap that bites hardest is the one with no arm-time gate.
If the operator does want the move, the order is: DK ingest loop first, then the clone
commit, then the operator inputs, then arm — and the runtime preflight will confirm the
middle two on its own.

If the motivation is wall-clock rather than machines, note that the ratio question is
still open at production's end: the laptop curve at N=40/80/150 is recorded, and the same
three runs on the workstation would show whether 1.72x holds at the 2560 overlap cuts the
real build reaches.

## Method note

Checking for the DK loop, I ran `pgrep -af "host_ingest_dk"` and it matched **its own
command line** — the exact trap the project traps list warns about, which caused an
infinite loop here on 2026-09-22. No harm (a `pgrep`, not a `pkill`), but the first result
was wrong and I re-checked via `systemctl --user list-units` and a `ps` filter excluding
this shell's own tree. Recording it because I hit a documented trap while auditing, which
is the most likely way to hit one.
