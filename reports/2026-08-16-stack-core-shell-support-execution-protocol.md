# Stack-core x shell support-census execution protocol

Date frozen: 2026-08-16, before any support-census Cloud execution and before
any stack-core/shell treatment was constructed.

Protocol ID: `20260816-stack-core-shell-support-execution-v1`.

## Purpose and queue

This protocol executes only the control support census required by
`20260816-stack-core-shell-scorefree-v1`. It does not construct a core, shell,
proposal or treatment and cannot inspect an effect or realized outcome.

The population may start only after the running ATLAS branch has a strict
terminal closure, so the support jobs do not contend with its resource test.
The exact immutable image must pass the complete repository suite plus
real-container `--help` smokes for the source loader, shard runner and
aggregator.

## Population and real-path canary

The primary population is the fixed 54 Sunday-main slate grid, 2023--2025
Weeks 1--18. Every job has one task, four CPUs, 16 GiB memory, a two-hour
timeout and Cloud Run `max-retries=0`. The actual 2023 Week 1 primary job,
command and create-only output URI launch first. The other 53 primaries may
launch only after a strict validator confirms:

- it is the job's only execution;
- the immutable image, code, command, environment, resources, account and
  timeout equal the launch manifest;
- it completed successfully; and
- its exact object has positive byte size and generation.

The canary validator reads only execution/object metadata. It never downloads
the object. A failed canary closes this execution version and cannot be
replaced.

## Bounded platform replacement

After all 54 primaries are terminal, every primary is classified from its
exact Cloud Run metadata and exact object existence. A failed primary is
replacement-eligible only when all of the following hold:

1. the task is terminal with the literal platform message
   `Internal error running task`;
2. application exit code is zero or absent and no memory, timeout, signal,
   solver, cancellation or nonzero-exit evidence appears;
3. the exact create-only output object is absent by an unambiguous 404; and
4. no other primary has an ineligible or ambiguous failure.

All eligible identities are determined together before any replacement. Each
may receive exactly one separately receipted execution of its unchanged
deployed job. No second replacement is permitted. Any substantive/ambiguous
failure, failed replacement, extra execution, object-bearing failure or
population mismatch closes the version as mechanically invalid/inconclusive.

## Strict harvest

The finisher validates the canary, the exact primary/replacement/accepted
ledgers, every execution specification and successful terminal status, and
every positive object metadata receipt before downloading any shard. It then
requires exactly 54 unique shards and invokes the frozen strict aggregator.
The report and completion receipt are uploaded create-only and bind all source,
build, execution, object and aggregate hashes.

Only the report's prospectively fixed 230/220/210 support disposition may
license later treatment construction. Support failure closes the mechanism;
support success does not license production or historical-score inspection.
