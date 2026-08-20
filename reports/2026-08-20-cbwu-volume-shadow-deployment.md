# CBWU volume shadow deployment

Date: 2026-08-20 13:43 CDT.

The already-frozen `2026-cbwu-volume-v1` prospective shadow is deployed but
not running. No lineup was generated and no prospective result was read.

## Source and image

- Source commit: `afdfe58d10b07f5ae0cc61373ee8586b272c4d4b`.
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:765db76cc65f74edfa28915f7b390aafc23a763010768bbff08a8553d50525af`.
- Exact frozen grading law:
  `reports/2026-08-19-cbwu-volume-prospective-shadow-spec.md`.
- Focused predeployment validation: 21/21 tests green across the CBWU-volume
  combiner, paired-shadow dispatch, and production-policy firewall. The money
  policy remains `MULTISEED_PORTFOLIO=CBWU`; only the explicit
  `shadow-cbwu-volume` command activates treatment.

## Quota-safe Cloud Run resource

Creating a new `shadow-cbwu-volume` resource failed before creation with
`JobsPerProject current use of 1000 ... would exceed limit of 1000`. No partial
job or scheduler resulted. Repository rule 5 forbids deleting old jobs because
that erases their execution history.

The closed, idle, unscheduled legacy resource
`fantasy-points-route-tail-union` was therefore updated in place:

- UID: `c3892b0e-568e-4e20-8be3-06532c117c6c` (unchanged);
- generation: `1 -> 2`;
- command/args: `nfl-dfs shadow-cbwu-volume`;
- environment: exact `GCP_PROJECT=nfl-predictions-503414` and
  `CODE_SHA=afdfe58d10b07f5ae0cc61373ee8586b272c4d4b`;
- one task, 4 CPU, 16 GiB, 14,400-second timeout, maximum one retry;
- service account:
  `817589974517-compute@developer.gserviceaccount.com`.

Its earlier route-tail executions remain retained under their original names.
No execution was launched during this deployment.

## Scheduler

`s-shadow-cbwu-volume` now targets that reused job at `30 8 * * 7` in
`America/Chicago`. It is deliberately **PAUSED** until the regular-season
shadow fleet is resumed. The first valid 2026 Sunday-main run remains unseen;
the frozen six-slate adoption bar is unchanged.

The operator may request an increase of the adjustable Cloud Run
Jobs-per-project-and-region quota for clearer dedicated resource names later.
That is operational convenience only and does not change this shadow's law.
