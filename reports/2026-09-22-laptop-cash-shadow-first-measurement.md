# The cash/double-up shadow: our current book would not have cashed in Week 2

Operator asked for a cash/double-up shadow, **additive** — running on paper beside the
tournament book, replacing nothing. This is the first measurement, and it changes what the
shadow has to be.

## The measurement

Our 97 entered Week-2 lineups against the **real** Week-2 field, from
`nfl_raw.contest_entries` (311,664 entries across 12 contests — the table my research audit
wrongly reported as never having received a row; see the correction at the end).

Our book: **mean 98.40, median 96.48, best 157.96.**

| contest | entries | field median | our % above median | double-up line (~top 45%) | **our % cashing** |
|---|---:|---:|---:|---:|---:|
| $3M Millionaire | 172,692 | 113.82 | 24.7% | 117.30 | **19.6%** |
| $350K Flea Flicker | 83,200 | 117.22 | 20.6% | 120.76 | **16.5%** |
| $100K Huddle (SE) | 23,758 | 111.82 | 26.8% | 115.20 | **23.7%** |
| $40K Pylon (SE) | 15,838 | 113.02 | 25.8% | 116.52 | **20.6%** |
| $40K Nickel (5E) | 9,512 | 118.78 | 19.6% | 122.20 | **15.5%** |

**A double-up needs roughly 50% to break even. We are at 11–24%.** On Week 2 a cash
strategy built from this book would not have been marginal; it would have been a rout.

## This contradicts the number the proposal rests on

The synthesis that proposed the shadow describes the calibrated mean as the system's real
strength: *"61% of entries above the Millionaire median, 25% above the cash line."*

**Week 2 is 24.7% above the Millionaire median and 19.6% above the cash line.** Not 61%.
Those figures must be Week-1 numbers, and **they do not replicate on Week 2** — which is the
same slate production has just shown was lost at the floor (book mean 98.40 against a field
median of 113.82). The two findings are the same fact seen from two sides.

## But this does *not* kill the idea, and the reason matters

**I measured the wrong book.** These 97 lineups were selected by dual expected-max for a
tournament — chosen to maximise the *best* lineup, which necessarily accepts a weak floor.
Scoring a max-seeking book against a cash line measures the mismatch, not the opportunity.

So the honest statement is narrow: **our tournament book would not cash. Whether a
cash-selected book would cash is untested**, and nothing here answers it.

That is exactly why the shadow has to select differently, and why it is a real design rather
than a relabelling of the existing output.

## What the shadow should actually be

Additive, paper-only, and sharing everything upstream of selection so the comparison is clean:

- **Same pool.** Same frame, same candidates, same draws as the tournament build. Only the
  selector changes — otherwise we are testing two things at once, which is how the cap and
  the fade both produced crossed signs.
- **Different objective.** Not expected-max. Maximise **P(score > line)** for a stated line,
  where the line is the contest's cash threshold rather than a simulated tail. This is the
  one objective family the ledger has *not* closed: PREREG-098 closed finish-objective
  selection on simulated **top-N**, which is a tail quantity. A cash line sits near the
  field median, where the simulator is calibrated — the synthesis's own §2.3 says the
  further an objective reaches into the tail, the worse the realized book. **A cash
  objective reaches the other way.**
- **Small K.** Cash books do not need 97 rows. K=5–20 is the realistic entry count and it
  makes the paper cost trivial.
- **Scored against the real field**, not a simulated one — `contest_entries` now carries
  the entry-level points to do it, so the line is observed rather than modelled.

## What I need to run it, and what I can do now

**Now, without anything:** the Week-2 half — select a cash book from the archived Week-2
pool by P(> line) and score it against the real Week-2 field. One run here, no money-path
contact. That is the first real test and I will do it next unless redirected.

**To make it two slates:** the Week-1 archived pool, which I asked for at `7c9de246` and
which production has since used for their own Week-1 work — so it is reachable on their side.

## Correction to my research audit

My audit's §F stated, quoting README *Known gaps*, that **"`contest_entries` has never
received a row."** That is **stale**: the table holds **994,328 Week-1 entries across 3
contests and 311,664 Week-2 entries across 12**, all with `points`. The gap closed when the
2026 standings capture started working.

**The other half of that note stands and is the real gap:** `payout` is NULL on **every one
of those 1,305,992 rows**, so contest *placement* is measurable and contest *money* is not.
For a programme that has reframed itself around dollars, the dollars are still absent.
