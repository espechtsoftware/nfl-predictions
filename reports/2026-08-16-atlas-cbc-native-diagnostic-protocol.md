# ATLAS packaged-CBC native diagnostic protocol

Date frozen: 2026-08-16, before any diagnostic launch
Protocol ID: `20260816-atlas-cbc-native-diagnostic-v1`

## Question

Why did the packaged PuLP CBC child process return nonzero before the first
seed completed on repair2 cells 2024 Week 15 and Week 16?

## Fixed source and population

Run exactly those two cells from the immutable repair2 image
`sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`
and repair2 source code
`60f296fdad769b30c0bb7334118698f156e462b9`. Load the identical five native
books and identical player catalog. Execute only the exact R0 construction
prefix that failed: native interaction pricing, exact top-40 worlds,
structural clustering and the 40-lineup matched-diversity enumeration with an
empty prior-ATLAS set. All objective, floor, stack, ordering, tolerance,
interaction and tie-break rules remain unchanged.

## Sole permitted changes

- execute the diagnostic source through `python -c` in the unchanged image;
- replace `PULP_CBC_CMD(msg=0)` with a subclass that still invokes the same
  packaged binary and defaults, but sets `keepFiles=True` and `logPath`;
- count solver invocations;
- on CBC failure, persist the final native log, final MPS problem and a
  mechanical receipt to the diagnostic-only prefix;
- on successful R0 completion, persist only a mechanical success receipt;
- discard all returned lineups in memory and replace the normal uploader with
  a no-op. Never address a normal ATLAS output URI.

Both tasks retain one CPU, 4 GiB, zero retries, one task, parallelism one, the
same service account and a 12-hour timeout. This diagnostic is evidence-only.

## Firewall

The diagnostic source and SQL may not reference realized outcomes. No lineup,
candidate summary, selector output, tail probability, gate, effect or
historical score may be printed or persisted. Permitted receipts contain only
protocol/source/image/code/execution/cell identities, terminal status, solver
invocation count, exception type/message, and diagnostic artifact names,
sizes, generations and SHA-256 values. Native CBC text and its MPS input are
permitted even though they contain score-free objective coefficients.

Do not inspect either task until both are terminal. Then invoke only the
strict finisher. The diagnostic cannot license an ATLAS result or a production
change.

## Decision rule

- If the native log identifies a deterministic model/parser/numerical failure,
  freeze a repair3 that changes only the proven solver-transport defect and
  validate exact roster parity where the old solver completes.
- If both diagnostics complete R0 successfully, classify repair2 as a
  transient child-process reliability failure and freeze repair3 with one
  predeclared mechanical retry per cell, still under new full-grid identities.
- If evidence is missing or inconsistent, the diagnostic is inconclusive;
  do not relaunch the effect grid until observability is improved prospectively.

In every case repair3 must rerun all 54 slates. Repair2 objects may not be
reused, and the historical scorer must be rebound and rebuilt to repair3.
