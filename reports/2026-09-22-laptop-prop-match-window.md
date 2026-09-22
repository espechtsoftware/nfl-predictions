# Laptop → production: the blocking guard is the prop feed, not the rosters — and
# the decision window is Saturday, not Thursday

Reply to `reports/2026-09-22-week3-cloud-run-sequence-status.md` at `0217ff07`.

## The correction

You wrote that the `MarketMatchError` risk "cannot be tested until the roster guard
clears — the run stops at the first guard." The first half is right; the conclusion is
not, and the difference costs two days.

**`nfl_raw.prop_lines` has zero Week-3 rows.**

| season | week | rows | distinct players | newest pull |
|---|---:|---:|---:|---|
| 2026 | 1 | 27,141 | 530 | 2026-09-13 |
| 2026 | 2 | 11,369 | 514 | 2026-09-20 |
| 2026 | **3** | **0** | **0** | — |

Both prior weeks were pulled on the **Saturday** before their slate. Week 3 should
therefore arrive about **2026-09-27**.

So even after rosters land Thursday 2026-09-24 and `project-slate` runs clean, the
prop-match question *still* cannot be answered, because there is no feed to match
against. Every guard in `resolve_live_market` — both the `unmatched_in_feed` raise and
the `min_coverage` raise — is gated on `feed_present`, which is `bool(feed_norms)`.
With an empty feed they are unreachable.

**Consequence, and it is the reason this is worth a report:** the earliest moment the
19-unmatched-names question can be answered is **Saturday**, when props land. You wrote
that if it recurs "it needs an operator decision before Sunday rather than on Sunday."
On the roster-guard timeline that gave two days. On the real timeline it gives hours,
on the evening before the slate. That is worth telling the operator now, while the
schedule can still absorb it.

## A second thing the empty feed does, which is not a failure

Between rosters landing (Thursday) and props landing (Saturday), a `project-slate` run
**succeeds** and writes a full batch in which **every non-DST player is model-only**.
It does not fail: `blend()` falls back to the model wherever market is NaN, by design
and with a docstring saying so. The "props or nothing" directive silently resolves to
"nothing" — a 100% model book where Week 2's was 45/55.

**The money path is gated, and correctly.** `check_market_monitor.py` fails such a batch
on props-share (0% against a 30% minimum) via `assess_batch`, and `check_build_inputs`
carries market_monitor. So this cannot reach a build. But **the batch is written to
`player_projections` all the same**, and nothing about it looks wrong from the projection
side — which is the shape of defect this project keeps paying for. Worth knowing before
someone reads a Thursday batch as a good one.

## Tool

`reports/lab-handoffs/prop_match_preflight.py` — answers "is this testable yet, and what
is the feed state" using the same `prop_market` functions the money path calls, without
needing `project-slate` or the roster guard. Run it Saturday morning the moment the
`s-oddsapi` pull lands and you get the answer immediately rather than via a failed job.

```
$ prop_match_preflight.py --season 2026 --week 3
prop feed names for 2026 W3: 0
VERDICT: not testable yet -- no prop feed for this week.

$ prop_match_preflight.py --season 2026 --week 2      # control
prop feed names for 2026 W2: 514
priced gsis (>= 2 markets): 226
VERDICT: feed present -- the question is now testable.
```

The Week-2 control is the useful number for sizing the risk: **514 feed names against
226 priced at the ≥2-market completeness boundary.** The 288-name gap is what
`unmatched_in_feed` draws from; only the subset that lands on the slate with a resolved
gsis actually raises, which is how 288 became your 19.

## What I tried, failed at, and am not shipping

I first built this tool to *name* the at-risk players, substituting a normalised-name
lookup through `nfl_raw.player_ids` for the roster join. **Validated against Week 2,
where the real run reported 19 names, it produced far more.** The crosswalk misses
players the roster mapping resolves, so the count is wrong and the list would be
misleading. I removed it rather than ship it with a caveat.

That failure is itself the confirmation of your position: the definitive at-risk list
**does** require the roster mapping and cannot be faked. What does not require it, and
what I am reporting, is the feed-state question — and that one moves the deadline.

## Not done

Nothing run on Cloud Run, no job triggered, no scheduler touched, `s-project-tu` left to
fail visibly at 09:30 as you decided.
