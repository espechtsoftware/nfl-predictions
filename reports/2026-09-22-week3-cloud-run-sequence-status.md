# Week-3 Cloud Run sequence: two of three done, `project-slate` blocked on two stacked guards

Operator granted standing Cloud Run authorization for the week's build on 2026-09-22.
This is what ran, what it proved, and what is in the way.

## Done and verified by data, not by exit status

| step | execution | result |
|---|---|---|
| `build-features` | `build-features-csdh6` | **already run at 06:36 CDT by the `s-features` scheduler**, not by me. Verified: **928 Week-3 skill rows** in `nfl_features.player_week_inference` |
| `tabpfn-gen` | `tabpfn-gen-glvdl` | succeeded in 14m36s. **928 rows for week 3, up from 51**, clearing the derived floor of 506 — and matching the 928 inference rows **one-for-one** |

That one-to-one match is the part worth trusting: a truncated cache cannot fake it, and it
is precisely what the old presence-only gate could not see.

**An ordering race was live and close.** `s-project-tu` is ENABLED at **09:30 CDT**. Had
`tabpfn-gen` not been re-run first, the scheduler would have produced this week's batch on
the 51-row cache — last week's failure arriving automatically rather than by anyone's
mistake. `tabpfn-gen` finished 07:44.

## `project-slate-4xqx5` FAILED — and the failure is the system working

```
RuntimeError: target-week roster eligibility receipt is stale or incomplete;
refusing to project a partially classified DK pool
```

Not a crash. A fail-closed guard in `upcoming_slate_features`. It requires, for the target
week in `nfl_raw.rosters_weekly`: **32 distinct teams, ≥1000 distinct players, pulled within
72 hours.**

Measured against the live table:

| week | teams | players | last pull | age | receipt valid |
|---:|---:|---:|---|---:|---|
| 1 | 32 | 2,962 | 2026-09-22 10:02 UTC | 2h | True |
| 2 | 32 | 2,527 | 2026-09-22 10:02 UTC | 2h | True |
| **3** | — | — | — | — | **no rows at all** |

**nflverse has not published Week-3 rosters yet.** `s-nflverse` runs daily at 05:00 and ran
this morning (pull stamped 10:02 UTC) — it produced weeks 1–2 only, so the data is not
upstream, and nothing on this host is misconfigured. Week 3 opens Thursday 2026-09-24.

**Consequence: `s-project-tu` at 09:30 today will fail identically.** That is harmless —
it writes nothing and substitutes nothing — but it will surface as a job failure. It is
expected, not a new defect.

## The second guard behind it, which is the real Sunday risk

The **previous** `project-slate` execution (`pgvjz`, 2026-09-21 18:11 UTC) failed for a
*different* reason:

```
MarketMatchError: prop lines exist in the feed for 19 slate player(s) but did not
match a projection row: ... Najee Harris, Darnell Mooney, Tyler Higbee, Tutu Atwell,
Tyrone Tracy Jr., Theo Johnson, Devin Singletary ...
```

That is the deliberate fail-closed replacement for the Week-2 Jefferson defect — a player
whose spelling **is** in the prop feed but does not match a projection row stops the run
rather than silently taking a one-game DK-PPG stand-in at 55% weight.

**It is working as designed, and it is also a hard gate on the money path.** Any week with
unmatched prop names blocks `project-slate` completely, and with it every projection Sunday
depends on.

**Unknown, and the thing to watch:** whether Week 3 reproduces it. Those 19 were resolved
against a week-2 slate; Week 3 now has 928 fresh inference rows, so the match set is
different and may well be clean. **It cannot be tested until the roster guard clears** —
the run stops at the first guard.

## What I am doing, and what I am not

- **Not** forcing past either guard. Both exist because of specific Week-2 losses.
- **Not** pausing `s-project-tu`; letting it fail visibly at 09:30 is more honest than
  hiding an expected failure, and it writes nothing.
- **Will** re-run `project-slate` as soon as Week-3 rosters land, and report immediately
  whether `MarketMatchError` recurs — because if it does, it needs an operator decision
  before Sunday rather than on Sunday.

## Gate state right now

```
FAIL build inputs for 2026 week 3: projections 0 rows; market_monitor not deployed;
tabpfn rows 928 (weeks [3], slate 633, floor 506); files ok
```

TabPFN has left the failure list. The remaining two are both produced by `project-slate`.
