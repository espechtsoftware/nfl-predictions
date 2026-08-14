# SIS opponent run-tail prerequisite audit

Date: 2026-08-14. This is an adaptive, outcome-blind support and redundancy
audit prompted by the amended pre-forensic exhaustion review. It read no
player actual, projection residual, candidate, selected lineup, or lineup
score. It did not rebuild a feature table or compute a model output.

## Bound inputs and PIT construction

- Exact pre-lock salary universe: panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`, RB rows only.
- Write-once SIS source: `nfl_raw.sis_team_run_context_game`, source run
  `sis-team-run-context-tranche-2-v1` (3,230 rows at audit time).
- Existing comparators: only strictly-prior fields from
  `nfl_features.player_week_training`.
- Reproduction SQL: `sql/audits/sis_run_tail_prerequisite.sql`.
- BigQuery job:
  `bqjob_r7410ee58c589ee60_000001a001818c04_1`.

For each opponent and target week, Boom and Bust events are reconstructed as
the vendor rate times attempts. Numerators and attempts are summed over the
last four rows after excluding the target row (`4 PRECEDING` through
`1 PRECEDING`), with at least two prior games. Every supported source-week end
is strictly below the target week. No current-week, cross-season, average, zero,
or outcome-derived fallback is used.

## Support

| fold | opponent team-weeks | supported | salary RB rows | supported | row support |
|---|---:|---:|---:|---:|---:|
| 2023 | 400 | 350 | 2,287 | 1,970 | 86.14% |
| 2024 | 398 | 348 | 2,136 | 1,838 | 86.05% |
| 2025 | 396 | 348 | 2,308 | 2,034 | 88.13% |
| all | 1,194 | 1,046 | 6,731 | 5,842 | 86.79% |

The registered 80% minimum is met in every season. Unsupported rows are the
expected early-season boundary and must stay null in a treatment.

## Redundancy

| fold | Boom vs RB FP allowed | Bust vs RB FP allowed | Boom vs rush EPA | Bust vs rush EPA | Boom vs Bust |
|---|---:|---:|---:|---:|---:|
| 2023 | +0.2126 | -0.2849 | +0.4993 | -0.6048 | -0.2665 |
| 2024 | +0.1434 | -0.0038 | +0.4795 | -0.4236 | -0.1268 |
| 2025 | +0.2988 | -0.1209 | +0.4870 | -0.5033 | -0.0480 |
| all | +0.1906 | -0.0829 | +0.4820 | -0.2726 | +0.3115 |

Aggregate Boom versus existing dropback EPA is `+0.1579`. Both vendor fields
are much less redundant with the current fantasy-points-allowed feature than
the previously rejected SIS pass-defense EPA (`r=0.8803`). Boom has moderate,
stable overlap with existing rush EPA but retains roughly 77% unexplained
variance in aggregate. Bust is nearly orthogonal to RB fantasy points allowed
in aggregate; its relationship with rush EPA changes materially by season but
does not make it a duplicate.

## Disposition

The prerequisite **passes**. Support is adequate and season-stable, the two
features are not duplicates of each other, and neither is redundant with the
nearest existing tail proxy. This licenses freezing one explicitly adaptive
RB-only run-tail marginal protocol before any model output.

It does not erase the earlier RB Points-Saved protocol's prohibition on adding
Boom/Bust after that result. The new test must disclose that boundary and use
`adaptive_retrospective=true`. It also does not license a feature rebuild,
lineup-score query, production adoption, alternate window, offense Boom/Bust,
or a larger run-defense bundle.
