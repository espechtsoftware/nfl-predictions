# ATLAS repair5 bounded platform-retry amendment

Date frozen: 2026-08-16, while the exact 32-GiB full-cell preflight was
nonterminal, before repair5 launch and before any repair5 shard or effect
existed.

Applies to: `20260816-atlas-matched-diversity-mvp-v1-repair5`.

Disposition class: mechanical execution-contract repair only. The image, code,
rendered command, resources, simulator seeds, candidate construction, output
URI, score-free gate and every later historical-scoring rule remain unchanged.

## Reason

Each repair5 cell is a deterministic independent shard with a pinned image and
command and a create-only destination. Requiring all 54 primary Cloud Run
executions to avoid every transient platform failure makes the population
unnecessarily brittle without preventing outcome selection. A replacement for
an execution that wrote no object cannot expose or select a scientific result.

This amendment does not change Cloud Run task retries: every execution retains
`maxRetries=0`. It conditionally permits one separately named replacement
execution under the exact rules below.

## Frozen attempt law

The attempt resolver runs only after all 54 primary identities in
`executions.txt` are terminal. It records all primary metadata before making a
decision and may inspect only execution metadata and URI existence. It must not
download a shard, inspect an effect, lineup, score-free statistic or realized
outcome.

A terminal failed primary is replacement-eligible if and only if all of these
conditions hold:

1. the `Completed` condition has status `False`;
2. `succeededCount=0`, `failedCount=1` and `cancelledCount=0`;
3. the `Completed` message contains the literal platform message
   `Internal error running task`;
4. the message does not contain `configured memory limit`, `timeout`, `signal`,
   `SIGKILL`, `solver`, `CBC`, or `nonzero exit` (case-insensitive); and
5. the exact ledger-declared GCS destination is absent immediately before the
   replacement is launched.

Memory-limit, timeout, cancellation, signal, solver, ordinary nonzero-exit and
ambiguous failures are ineligible. If any ineligible primary failure exists,
the population is already scientifically irrecoverable: no replacements are
launched and the terminal failure census is used. This suppresses compute that
cannot rescue the population.

If, and only if, every failed primary is eligible, the resolver must launch
exactly one new execution of each already-deployed unchanged `-r5` job. It may
not redeploy a job. Every eligible failure is retried; none may be selected or
omitted. The destination must be checked absent again immediately before the
new execution request. There is no second replacement under any reason.

If all primaries succeeded, no replacement is launched. The primary ledger is
the accepted ledger.

## Immutable receipts

The resolver must retain:

- the original 54-row `executions.txt` primary ledger;
- all 54 primary execution metadata documents and their hash ledger;
- the URI-only object inventory observed after all primaries became terminal;
- a machine-readable primary classification with the exact eligibility reason;
- `retry-executions.txt`, which is empty or contains every and only eligible
  replacement identity;
- a 54-row `accepted-executions.txt`, using the primary identity for a primary
  success and the replacement identity for an eligible primary failure; and
- an attempt-resolution receipt binding all of the above and recording
  `max_replacement_executions_per_cell=1` and `task_max_retries=0`.

The accepted ledger may be created only when there are no ineligible failures.
The strict finisher must validate every accepted execution against the same
image, command, environment, resources, service account, cell and object URI as
its primary. It must retain metadata for both identities when a replacement was
used. A failed replacement, a missing object, a changed job specification, an
extra attempt or an incomplete ledger invalidates the whole repair5 population.

## Consequence boundary

A complete accepted 54-cell population has exactly the same scientific meaning
as a clean primary population because neither the computation nor destination
changed. The attempt disposition is mechanical metadata, not an arm feature.
It cannot change the score-free or historical gate, license partial scoring,
mix cells from another run, or authorize production. Historical scoring must
bind the primary, retry and accepted ledgers and all attempt metadata before it
can use repair5.
