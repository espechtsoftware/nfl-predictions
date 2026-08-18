# DK contest-fills collector deployment

Date: 2026-08-18. **No realized DFS outcome was read. No production policy, money
book, selector or UI behavior changed.**

## Why

`nfl_raw.dk_contest_fills` was implemented but **empty, with no Cloud Run job and
no scheduler**. The `nfl-dfs ingest-contests` subcommand and `contest_job.run()`
existed; nothing invoked them.

The captured fields — `entries`, `fill_rate`, `prize_pool`, `overlay_dollars`,
`is_guaranteed`, `max_entries`, `entry_fee`, `pulled_at` — are **live-only**.
Once a contest locks and settles, its pre-lock fill trajectory is gone and
cannot be reconstructed from any retrospective source. Week 1 is roughly three
weeks out, so every week without a deployed collector is a permanent data loss.

This is acquisition infrastructure. It licenses no arm, no adoption and no
money-objective work; it only makes a currently-unobtainable dataset start
existing.

## What was deployed

**Cloud Run job `ingest-contests`** (us-central1)

- image `sha256:0a55920d638951aaa6516b059f7ae3d1218cc6ee0d89a332805ca611fefc052d`
  (the digest already serving `ingest-odds` and `ingest-props`)
- `command: ['nfl-dfs']`, `args: ['ingest-contests']`
- 1 CPU / 2 GiB, task timeout 900s, max retries 1, 1 task
- service account `817589974517-compute@developer.gserviceaccount.com`
- env `GCP_PROJECT=nfl-predictions-503414`, `INGEST_CONTESTS_ENABLED=1`

**Schedulers** (America/Chicago, both `ENABLED`)

| name | schedule | purpose |
|---|---|---|
| `s-contests` | `0 10 * * 3-6` | Wed-Sat fill trajectory (mirrors `s-dk`) |
| `s-contests-sun` | `0 6-11 * * 7` | Sunday hourly through main lock (mirrors `s-project-su`) |

Retry config matches the existing ingest schedulers: min backoff 5s, max backoff
3600s, max doublings 5.

## Verification

| step | result |
|---|---|
| first execution `ingest-contests-jcvn5` | **failed** — `command` was unset, so Cloud Run used the image default entrypoint and exec failed |
| repaired with `--command nfl-dfs` | container spec now matches `ingest-odds` exactly |
| execution `ingest-contests-hst6x` | `Completed=True`, `succeededCount=1`, `exit(0)` |
| forced `s-contests` run | scheduler attempt succeeded at `2026-08-18T12:20:01Z` |
| scheduler-triggered `ingest-contests-dsnx9` | `Completed=True`, `exit(0)` |
| table row count | `0` — **correct** |

The collector logs `No upcoming NFL draft groups; nothing to match contests to`
and exits zero. That is the designed preseason behaviour: DraftKings does not
publish NFL Classic draft groups until close to Week 1. The job is a safe no-op
until they appear, then begins appending automatically with no further action.

## Note for the season

`src/nfl_dfs/status.py:90` already registers this feed with a 48-hour freshness
window and **`alert=False`**. That was reasonable while the table was empty. Once
rows start arriving, a silent collector failure would again produce
unrecoverable gaps without paging anyone. Consider flipping `alert=True` at the
first successful populated run. Not changed here — alerting policy is an
operator decision.
