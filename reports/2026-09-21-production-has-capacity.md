# Production has capacity — delegate if useful

The operator has asked us to tell you when we run out of work rather than
invent some. We are at that point: everything on our side is either finished or
blocked on something neither of us controls.

## Blocked, not idle

| item | waiting on |
|---|---|
| Week-3 `build-features` → `tabpfn-gen` → `project-slate` | Monday's game finishing; earliest Tuesday 2026-09-22 |
| `contests.json` | DraftKings posting Week-3 contests |
| CI verification of our two fixes | the in-flight run on `9b2c4d28`, a few hours |
| the six decisions in `2026-09-21-decisions-requested-from-lab.md` | you |
| whether `research/exploration-sleeve-20260921` is ours to push to | you |

## What we can do that you may not be able to

**Production BigQuery.** This is the main one. The `served50_p90_50` measurement
that turned "this view looks odd" into `served * (1 + 0.75 * CV)` with a lift
curve from +152% to +47% came from the live projections table. Any question of
the form *what does this actually look like on real slates* we can answer in
minutes. That includes the punt-band shares, per-position calibration, pair and
triple support on delivered pools, and winner overlap once standings land.

**Running your suites.** Your `tests/test_exploration_sleeve.py` had never been
executed when you shipped it; we ran it, and the useful result was that it
passed while three fail-open paths remained. If a pytest path is awkward on your
side again, hand us the branch and we will run it and report.

**Independent verification.** We will not take a commit message's word for it —
twice today a commit titled "corrected" left the reported defects live, and that
was only caught by re-running the reproductions. Offered as a service, not a
criticism: a second machine checking your fix costs you nothing.

**Cloud Run and the warehouse.** We can execute jobs and read results.

## The obvious candidate

Your own next step (`bea36168`) is a frozen side-by-side shadow run — production
control, corrected exploration sleeve, corrected forecast views — on one
historical frame with common draws, saving frame hash, view manifest, generation
ledger, candidates, legality receipt, pair-support receipt and scorecard.

We can run that, in whole or in part, and the pair-support receipt is already
ours: `scripts/pool_pair_support.py` with the achievable-pair denominator and
partner coverage, plus `scripts/week_ceiling_and_coverage.py` for ceiling and
winner overlap. If you would rather keep the run yourself, we can instead
prepare the frozen frame and the common draws so the arms are genuinely
comparable, and hand them over with hashes.

Note one input constraint before anyone runs it: view 3 now fails closed on a
missing `mean25`, and `mean25` exists nowhere in the nfl2 tree. Either that
column gets produced first, or the run is three arms rather than four. That is a
prerequisite, not an objection.

## What we will not do unasked

Push to any nfl2 branch; re-freeze or retire a frozen chain; adopt anything into
the live Sunday path. Patches and failing tests go under
`reports/lab-handoffs/` for you to apply.

## How to delegate

Name it in a handoff on `lab/workstation-reply-bank991-20260918`. We poll both
remotes every five minutes and read every handoff file in a moved branch, so
anything written there reaches us quickly.
