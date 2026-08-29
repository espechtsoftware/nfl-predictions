# Recourse-aware initial-book kickoff-population amendment

Date frozen: 2026-08-29, before the replacement canary or any replacement
score-free result exists.

Replacement execution ID:
`20260829-recourse-aware-initial-book-scorefree-kickoff-v2`.

The failed execution
`20260817-recourse-aware-initial-book-scorefree-v1` is terminal. Nothing in
this amendment authorizes resuming, validating, releasing, harvesting, or
relaunching that execution or writing beneath its output prefix.

## Bounded correction

The kickoff lookup is restricted with a parameterized
`player_id IN UNNEST(@player_ids)` predicate, where `player_ids` is the exact
sorted player-ID population already loaded from the frozen R0 slate book.
The existing post-query checks remain authoritative and must reject an empty,
missing, extra, duplicate, wrong-manifest, invalid-time, multi-local-date, or
early/late-unsplittable population.

This correction narrows metadata access. It does not add a table, field,
source panel, slate, outcome, realized value, treatment effect, scientific
arm, fold, candidate, world, resource allowance, retry, or disclosure.

## Replacement authority

The replacement uses a fresh output prefix:

`gs://nfl-predictions-503414-raw/research/recourse-aware-initial-book-runs/20260829-recourse-aware-initial-book-scorefree-kickoff-v2`

All scientific, score-free, source, canary, retry, failure, harvest, and
create-once laws in the 2026-08-17 science and execution protocols remain
unchanged. The existing single-job transport and terminal-root amendments
remain unchanged except that every replacement manifest, validator, shard,
receipt, local path, and cloud path must bind the replacement execution ID.
The replacement canary requires a newly built immutable code/image identity
containing this amendment and the bounded query correction; the prior image
cannot authorize it.
