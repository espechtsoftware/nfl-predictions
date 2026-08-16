# ATLAS MVP CBC single-shard retry repair

Date frozen: 2026-08-16, after the mechanical failure below and before any
repair2 slate object or effect was opened

Amends:
`reports/2026-08-16-atlas-mvp-slate-sharding-repair.md`

Scope: one exact execution replacement for a solver-process crash

## Mechanical failure

Repair2 execution `atlas-md-s2024-w7-r2-r9gnq` failed at
`2026-08-16T13:15:08.176883Z` with one failed task and container exit code 1.
The Python traceback ends in `pulp.apis.core.PulpSolverError` while PuLP was
attempting to execute the packaged CBC binary from the unchanged shared
optimizer. It emitted no `ATLAS_MVP_SEED_COMPLETE` or
`ATLAS_MVP_SLATE_COMPLETE` marker. Its exact create-only target

`gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair2/slate-2024-7.json`

is absent. No shard object, candidate identity, effect metric or aggregate was
opened. The other repair2 tasks remain sealed.

This is a mechanical non-result. It neither passes nor fails the score-free
ATLAS gate.

## Licensed one-time replacement

Exactly one new execution of the already deployed
`atlas-md-s2024-w7-r2` Cloud Run job is permitted. The replacement must retain
byte-for-byte/equality identity for:

- immutable image digest and full `CODE_SHA`;
- runner command and exact `--season 2024 --week 7` arguments;
- the same absent create-only output URI;
- source panels, artifacts, repair receipts and all source hashes;
- `_run_slate`, seed order, solver objectives, constraints and tie breaks;
- one CPU, 4 GiB memory, one task, one parallelism, zero configured retries,
  12-hour timeout and service account; and
- every P0/P1/P2 construction, count, selector, summary and gate rule.

No code, image, environment, solver option, logging mode, resource, timeout or
scientific choice may change. This is a new execution of the exact immutable
job, not a parameter retry. If the output appears before launch, the job spec
differs, the replacement fails, or a second replacement would be required,
this repair is invalid and a new pre-effect diagnostic protocol is required.

## Receipt and strict harvest

The original 54-row launch ledger remains immutable evidence and may not be
edited. The repair launcher must preserve:

1. the original failed execution metadata and SHA-256;
2. the exact mechanical traceback log and SHA-256;
3. the new replacement execution identity; and
4. a new 54-row effective execution ledger that differs from the original at
   exactly `(2024, 7)` and only in execution name.

The strict repair2 finisher must validate the failed original receipt, the
single replacement receipt and both ledgers. It may use the replacement only
for `(2024, 7)`. All other 53 execution identities remain those in the original
ledger. The downstream historical scorer must bind the same original-failure,
replacement and effective-ledger receipts before reading assembled output.

## Consequence

This repair changes no scientific value and creates no license to tune from a
successful or failed result. Only a terminal-success replacement plus all 53
original terminal-success executions can restore a mechanically valid 54-cell
repair2 harvest. Realized historical scoring remains downstream and mandatory
after strict harvest regardless of the score-free gate disposition.
