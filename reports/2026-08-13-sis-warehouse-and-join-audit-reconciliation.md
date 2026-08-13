# SIS warehouse and join audit reconciliation

Date: 2026-08-13. This reconciles the operator-supplied
`2026-08-13-sis-warehouse-and-join-audit.md` against the current warehouse,
the frozen SIS protocols, the immutable cache reports, and the production
feature path. No model or lineup outcome was recomputed.

## Disposition

The audit's main conclusion is accepted: neither imported SIS table has a
warehouse-grain, schedule-join, opponent-identity, missing-source, or
strict-prior rolling defect. The two completed SIS marginal arms do not need
to be invalidated or rerun because of this review, and the production baseline
does not contain either SIS source.

Two statements need correction:

1. SIS feature support was computed, persisted and mechanically gated. It was
   omitted only from the two concise final-result narratives.
2. `src/nfl_dfs/features/leakage.py` has no SIS-specific check. SIS has strong
   isolated research guards and tests, but those are not a substitute for a
   production-spine feature and centralized leakage-check integration.

The audit's season-boundary, table-naming and missing-production-path concerns
are accepted as prerequisites for any future SIS promotion.

## Independent structural verification

Outcome-free BigQuery checks on 2026-08-13 reproduced the important warehouse
claims:

- both `nfl_raw.sis_team_context_game` and
  `nfl_raw.sis_team_run_context_game` contain 3,230 rows;
- both have zero duplicate `(season, week, team)` keys and zero null
  `team`/`opp`/`game_key` values;
- their `(season, week, team, opp)` row sets are identical;
- all 3,230 `sis_team_context_game` rows join `nfl_features.schedule_long` on
  `(season, week, team)`, and all 3,230 opponents match;
- all report-family source-hash columns are populated;
- the season counts in both tables are 512 / 544 / 542 / 544 / 544 / 544 for
  2019 / 2021 / 2022 / 2023 / 2024 / 2025; and
- the selected line, pass-defense, rushing and run-defense metric columns in
  the source audit have zero null rows.

The rolling implementations also confirm `shift(1)` before a same-season
four-team-game window. The RB run-defense feature reconstructs its rate from
lagged numerator and denominator sums. The QB line feature intentionally uses
an arithmetic mean of the two already-defined weekly rates/value fields, as
frozen in its protocol. Both expose and verify a source week strictly below
the target week.

## Correction: support was measured and gated

The frozen protocols required at least 80% supported active-player rows in
each 2023--2025 fold. Both cache generators emitted per-season
`active_qb_coverage` or `active_rb_coverage`; both validators required the
control/treatment audits to match and enforced the 80% floor. Those checks are
present and passing in the immutable `validation.json` files.

On the exact final-served primary populations, a read-only reconstruction of
the already-frozen strict-prior support mask gives:

| arm population | 2023 | 2024 | 2025 |
|---|---:|---:|---:|
| QB line | 454 / 511 (88.85%) | 442 / 502 (88.05%) | 447 / 507 (88.17%) |
| RB run defense | 1,157 / 1,329 (87.06%) | 1,140 / 1,307 (87.22%) | 1,161 / 1,325 (87.62%) |

No target row was dropped: control and treatment cache keys and final-served
primary rows were required to be identical. Unsupported treatment values stay
null and were passed directly to TabPFN; these two generators do not use the
median-imputation pipeline mentioned in the source audit. Thus early-season
missingness can dilute the feature's aggregate opportunity, but it is a
declared, symmetric, mechanically gated part of each frozen experiment—not an
unreported execution defect that reopens either arm.

The concise result documents should have surfaced the support figures. To
preserve immutable result records, this reconciliation supplies the missing
summary rather than rewriting their decision. A supported-only outcome slice
would now be post-hoc and may be descriptive only; it cannot change either
registered disposition.

## Accepted follow-ups

### Season boundaries

The policies are genuinely inconsistent:

- SIS QB/RB research features restart by `(season, team)`;
- player NGS carries across seasons without a provenance indicator;
- team-QB quality carries across seasons and emits a cross-season indicator;
- Fantasy Points Route Share carries across seasons and emits a cross-season
  indicator.

Uniform behavior is not automatically correct: player skill, team scheme and
roster-dependent line/front quality have different offseason persistence.
Before the next feature in each family is frozen, its protocol must explicitly
choose restart, carry-with-indicator, or shrinkage and state the football
rationale. Closed SIS arms may not be retuned to a cross-season variant after
their outcomes were read.

### Raw-table content map

The table names are a real maintenance trap. Preserve the write-once raw table
names, but document this map in both ingest module docstrings before the next
consumer is implemented:

- `sis_team_context_game`: pass defense, pass rush and blocking;
- `sis_team_run_context_game`: team passing offense, rushing offense and run
  defense.

Renaming the private raw tables is not worth the provenance and backup churn.

### Production prerequisite

No `sql/features/sis_*.sql` table exists, SIS columns are absent from
`player_week_training` and `player_week_inference`, and no live policy reads
them. This confirms that the two negative research arms never affected
production.

If a future SIS arm passes, it is not shippable until a separate implementation
milestone provides all of the following:

1. a schedule/upcoming-row spine at the feature's correct team or player grain;
2. a strict as-of join that serves only completed prior games and persists
   source season/week plus support/cross-season provenance;
3. matching training and upcoming-inference columns with historical parity
   against the research helper;
4. explicit SIS checks registered in `src/nfl_dfs/features/leakage.py`, plus
   target-week mutation, bye, Week 1, opponent-direction and row-count tests;
5. backup coverage for any derived adopted table; and
6. a production-policy change only after the independently frozen scientific
   and lineup gates pass.

## Queue impact

- Do not rerun or reopen the closed QB-line or RB run-defense arms.
- Add support to every future concise SIS result as a mandatory reported
  field; the machine gate already does this.
- Add the content map and boundary rationale as documentation before the next
  SIS consumer.
- Treat production-spine/leakage integration as a hard promotion gate, not as
  prerequisite work for a research arm that has not passed.
- Continue the independently frozen team pass-defense schema feasibility
  sample and incumbent seed-variance panel; neither is altered by this audit.

