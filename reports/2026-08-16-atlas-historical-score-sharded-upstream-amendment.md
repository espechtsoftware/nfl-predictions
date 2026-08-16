# ATLAS historical score sharded-upstream amendment

Date frozen: 2026-08-16, after all 54 repair2 shard executions were launched
but before any shard reached terminal state, any shard output was opened, or
any score-free or realized-score effect was observed

Amends:
`reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md`

Scope: immutable upstream execution and receipt transport only

## Mechanical reason

The three season-serial repair1 executions named by the original historical
score protocol were cancelled as mechanical non-results. After approximately
3 hours 44 minutes, none had completed its first of 18 serial slates. CBC was
single-threaded, so the eight allocated CPUs did not accelerate the serial
interaction solves enough to fit the eight-hour task timeout. No season or
aggregate object was created and no partial effect was opened.

The score-free MVP calculation was therefore moved, without scientific
change, to the compute-only sharding repair frozen at
`reports/2026-08-16-atlas-mvp-slate-sharding-repair.md`. The identical
`_run_slate` function now runs in 54 independent season/week tasks. The strict
finisher may assemble the same three season reports and aggregate report only
after all 54 executions are terminal successful and every shard passes its
execution, source, count and outcome-free validation.

## Superseding upstream identity

- Run ID: `20260816-atlas-matched-diversity-mvp-v1-repair2`.
- Code SHA: `60f296fdad769b30c0bb7334118698f156e462b9`.
- Image digest:
  `sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`.
- Upstream prefix:
  `gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair2`.
- Launch manifest SHA-256:
  `080c85700219ac246b093f2556c474f4bd79257809cf0e006766a1ed48e95d24`.
- Complete 54-row execution ledger SHA-256:
  `6794f8e608497613aec2f06f2bd13e57cf08b945d7ac20e2d4d00eb1ee3d5ea5`.
- Each execution runs exactly one registered `(season, week)` with one CPU,
  4 GiB memory, zero retries and a 12-hour timeout. The exact execution names,
  jobs, arguments and create-only object URIs are those in the hashed ledger.

## Scorer binding repair

The historical scorer must bind the strict repair2 harvest rather than the
cancelled repair1 run. Its upstream receipt must include and independently
validate:

1. all 54 terminal-success execution metadata objects against the exact
   hashed launch ledger;
2. the repair2 code, image, command, season/week, output URI, environment,
   resources, service account, retry and timeout identity for every shard;
3. all 54 local/GCS shard hashes through the strict repair2 harvest;
4. the three strictly assembled season objects and aggregate object, including
   their immutable generations and SHA-256 values; and
5. the strict completion, report, launch-manifest and execution-ledger hashes.

The scorer continues to consume only the three assembled season reports and
aggregate report. It does not read partial shard effects and may not run until
the strict repair2 finisher has validated and assembled all 54 shards.

## Invariants and consequence

This amendment changes no slate, source candidate, ATLAS roster, P1/P2
candidate budget, exact-80 identity, realized player score, selector,
threshold, signal rule or consequence. It does not select whether the
historical diagnostic runs: after a mechanically valid repair2 harvest, the
diagnostic runs regardless of the score-free gate disposition. The historical
result remains retrospective diagnostic evidence only and cannot change
production or the UI.
