# CFB: two independent silences are about to stack

Cross-referencing the lab's `handoffs/2026-09-21-ingest-cfb-alert-investigation.md`
(nfl2 `5661f41`) against a change made on this side earlier the same day.

## We each silenced a different alarm, neither knowing about the other

| | alarm | action | who |
|---|---|---|---|
| **A** | `check-freshness` reporting `raw.cfb_dk_salaries` STALE | set `alert=False` in `src/nfl_dfs/status.py` | production, 2026-09-21 AM |
| **B** | Cloud Run `ingest-cfb` repeated job failure (403) | proposed: pause `s-cfb` and `s-cfb-sat` | lab, 2026-09-21 PM |

Both are correct in isolation and both have the same root cause — the DK 403.
Silencing A was necessary: a permanently red freshness check made a *real*
`dk_salaries` staleness invisible, which mattered today because the DK ingest
loop was being swapped.

## The trap

The `alert=False` note reads:

> collection-only scaffold; DK 403 since 2026-09-19, **non-alerting until the
> pull succeeds** (see 2026-09-21 deficiency-log row)

That condition assumes the pull keeps being *attempted*. **If `s-cfb` and
`s-cfb-sat` are paused, the pull never runs, so it never succeeds, so the feed
never re-alerts.** CFB then becomes permanently uncollected *and* permanently
silent — and the stated re-arm condition can never fire.

Nothing breaks. That is the point: it is exactly the class of thing that is
discovered a season later.

## Independent confirmation of the lab's scope claim

Their claim that no NFL path reads the table checks out. Every reference to
`cfb_dk_salaries` in the production tree is either the DDL
(`sql/raw/006_cfb_dk_salaries.sql`) or one comment in
`sql/raw/005_dk_contests.sql`. Zero references under `features/`, `models/`,
`inference/` or `optimizer/`. So pausing is safe for the money path, and the
alert carries no NFL Week-3 information.

## Recommendation

Pausing is the right call — retrying a deterministic 403 three times a day is
pure noise. But pair it with one of:

1. **If paused:** amend the `status.py` note to record the pause as the reason
   and the date, so the re-arm condition is "after `s-cfb` is resumed AND the
   pull succeeds" rather than a condition that cannot fire. One line, and it
   keeps the feed honest.
2. **If left running:** leave the note as-is; it is already accurate.

Either way, add a Data deficiency log row in README.md, which is the standing
rule for a source-data gap and gives this a durable home outside two handoffs
that both assume the other alarm is still live.

This is an operator decision, as the lab says — it stops collection of a
scaffold. We have changed no scheduler.
