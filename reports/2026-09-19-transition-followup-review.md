# Transition follow-up: cache identity and vetting evidence

Two additional review findings need correction in the next development cycle.
Neither changes the three authorized input repairs now being released.

## P1 — the cited historical vetting study did not reproduce the shipped rule

Lab `PREREG-100.md` calls its book-level comparison "the rule as shipped" and
uses its NULL result to justify keeping `vet_book.py` as shipped. The actual
frozen runner is recoverable at lab commit`395ab44`, path
`scripts/prereg100_practice_status.py` (the documentation-only consolidation
`60b7109` did not copy that runner onto the current main-derived checkout).
Source inspection confirms it implements the documented proxy:

| Operation | PREREG-100 runner | Installed live helper |
|---|---|---|
| Aggregate player risks | maximum | sum |
| Main demotion threshold | 0.5 | 1.0 |
| Flagged-lineup ordering | ascending risk, then original rank | original rank within hard/material tiers |
| Inputs | report designation and weekly practice level | DK status, latest injury text/status, practice, market presence/disappearance, depth/missed games |

The live helper is SHA256
`aa7d35f808d2a5db4faea6471b95c0c89b765ad1bc3c1e0c310ff5a428d6e89e`,
independently matched to installed workstation bytes in lab`181592b`. Its
sum/tier ordering is visible at production`scripts/week1_vet_book.py`, lines102–107. This implementation
already existed in September13history, before the September16study.

For a simple consequence, one0.5-risk player moves a lineup in the study'sV1
but leaves it in the live soft/clean tier; two0.5-risk players become material
live. Among material lineups, the historical risk sort can change order that
the installed stable-tier sort preserves. Real delivery impact is established
separately by the [current-book identity trace](2026-09-19-delivered-order-trace.md).

**Fix the claim, preserve the experiment.** Retain the frozen runner/results and
append a correction naming it a historical proxy. Do not relabel it as an exact
consumer replay. A new comparison of the installed rule first needs a point-in-time
support inventory for every live input, including market disappearance and DK
status; unavailable inputs must not be silently zero-filled. A limited historical
proxy can still be informative if explicitly named and frozen as such. No claim
that the current live rule helps or hurts follows solely from this mismatch.

There is a second implementation concern in that runner: `--mechanics-only`
still calls `frames()`, which reads/coerces `actual`, and `book_level()` coerces
book actuals before the mechanics branch returns. It avoids printing realized
metrics but is not a code path that forbids outcome reads. Any reuse should add
an actual outcome-disabled path and disclose the original mechanics behavior;
this observation alone does not prove that the author saw outcome values or tuned
the experiment to them. The earlier practice-level "Wed/Thu/Fri average" prose
was already corrected by the [source support audit](2026-09-19-opportunity-input-support.md).

The workstation independently verified the three ordering differences and the
mechanics-only control flow in lab `417cd96`. Both reviews agree on the
correction; no live vetting change is included in this release.

The correction is now appended to both `PREREG-100.md` and `LEDGER.md` on
lab documentation branch `docs/prereg100-consumer-mismatch-correction-20260919`,
commit `ec1756d`. Independent diff review confirms only those two documents
changed; original source, numbers and ledger row remain intact.

## P2 — the local live-training cache has no source identity or invalidation

`nfl2.live.training_panel_through()` reads
`$NFL2_CACHE/live/training_through_2025.parquet` whenever the file exists. It checks
neither schema/source identity nor freshness. Workstation`af5510c` confirms its
102,927row/122column file datesAugust29 and has SHA256
`8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7`.
The candidate checkout will reuse it. This is distinct from the shared TabPFN
cache being refreshed by the authorized release.

The host file differs from the refreshed warehouse on at least three known
historical activity records; broader equality is not established by equal row
counts or column means. We requested its exact bytes for a full keyed comparison
and an additional CLI proof that uses the actual host artifact. Leave the host
file intact during this inspection. The current-source repair affects upcoming
features and does not require replacing this historical cache merely to make the
laptop's test representative.

For the durable fix, receipt the table identity/query boundary, ordered schema,
content digest and creation/source version beside the cache. On mismatch, either
fail with a precise rebuild instruction or populate a new immutable cache and
switch explicitly. Preserve the prior cache for reproducibility. Add behavior
checks covering a same-row-count content revision and missing/incompatible fields;
a path/existence check is insufficient. Source revisions should remain distinct
from decisions to adopt a changed model or selector.

These are source-level findings. No new football outcome efficacy read or live
vetting/cache policy change was made for this review. Independent review has
been requested through the normal committed handoff channel.

## Measured host-cache difference, 06:17UTC

Both agents now compared the complete keyed panels. Exactly37,763of102,927rows
differ across37columns/1,864players; most differences are floating roundoff.
Using the explicit descriptive threshold absolute numeric difference>1e-6,
any null change or any nonnumeric change,3,531rows differ and3,472rows differ
in baseline model inputs or activity eligibility. That is about3.37%of rows,
not a claim that36.7%of model inputs are meaningfully wrong. Baseline inputs
include nontrivial revisions to separation_l4, stacked_box_l4 and qb_cpoe_l6.
Salary and salary_delta_wow are rowwise identical. [Exact comparison](reviews/evidence/2026-09-19-host-cache-comparison.json).

This broader drift is additional to the3activity corrections between the
September17feature build and today's feature refresh; the host cache is from
August29. The two time intervals must not be conflated. A representative release
proof now uses an authenticated copy of the existing host cache; a separate fresh
cache rehearsal can characterize that additional input change. The host file
and configuration remain intact. No claim of better NFL outcomes follows from
input freshness or these counts alone.
