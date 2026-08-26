# R6-v2 fixed matchup capture-plan audit

**Date:** 2026-08-26
**Disposition:** implementation-ready design; read-only static audit
**Authority:** no execution, publication, scoring, outcome, fill, retrieval,
promotion, production-policy, graph, IAM, deployment, or T230 authority

## 1. Executive disposition

R6 can become executable without regenerating player catalogs, world
matrices, Fantasy Points exports, or SIS downloads. The shortest trustworthy
path is:

1. finish the fixed-G0 outer adapter for the existing 54 structural catalogs;
2. capture a small number of global immutable source packs once;
3. deterministically derive all 54 matchup bundles and immutable producer
   receipts from those packs;
4. pin the resulting 54-entry producer release in one tracked, reviewed
   capture-plan lock;
5. let the production operator accept only a source-task ordinal, never a
   caller-selected bundle, identity, project, bucket, prefix, or root;
6. perform an outcome-blind all-54 support census and one real task-0
   mechanics smoke; and
7. fan out the already-pinned 54 captures from one image without redeploying
   or querying the warehouse for each slate.

The committed `corpus_r6_matchup_source_v1.py` and
`corpus_r6_matchup_source_operator_v1.py` are valuable semantic and
fail-closed fixtures. They are not yet an honest real execute path. The source
contract requires the legacy catalog, BigQuery-shaped role registrations, and
historical timestamp evidence that the accepted structural catalog and
mutable historical schedule do not actually possess. The operator correctly
keeps execute hard-blocked until an external fixed 54-entry root exists.

This audit was static and read-only. It ran no tests and accessed no cloud,
IAM, outcomes, realized scores, graph, deployment, or T230 state.

## 2. Evidence reviewed

The design follows the current implementations and frozen dispositions in:

- `src/nfl_dfs/research/corpus_r6_matchup_source_v1.py`;
- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py`;
- `src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py`;
- `src/nfl_dfs/research/corpus_batch_retrieval_runner_v2.py`;
- `src/nfl_dfs/research/corpus_r6_player_catalog_v1.py`;
- `src/nfl_dfs/research/receiver_matchup_annotations.py`;
- `src/nfl_dfs/research/rb_qb_matchup_annotations.py`;
- `src/nfl_dfs/research/receiver_matchup_contract.py`;
- `sql/research/017l_receiver_week_role_pit.sql` through
  `sql/research/017r_player_matchup_week_pit.sql`;
- `sql/features/003_player_week_role.sql`;
- `sql/features/017a_defense_week_coverage.sql`;
- `src/nfl_dfs/ingest/fantasy_points_coverage.py`;
- `src/nfl_dfs/ingest/fantasy_points_alignment_l4.py`;
- `src/nfl_dfs/ingest/fantasy_points_route.py`;
- `src/nfl_dfs/ingest/sis_team_run_context.py`;
- `src/nfl_dfs/ingest/sis_receiver_copula.py`;
- `src/nfl_dfs/ingest/nflverse_job.py`;
- `reports/2026-08-24-r6-v2-matchup-pit-lineage-disposition.md`;
- `reports/2026-08-26-r6-player-catalog-spine-audit.md`; and
- `reports/2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md`.

## 3. Fixed 54-entry lattice

The catalog/source task lattice is already deterministic:

```text
source_task_ordinal = (season - 2023) * 18 + (week - 1)

0..17   = 2023 W1..W18
18..35  = 2024 W1..W18
36..53  = 2025 W1..W18
```

The canonical task ID is `slate-{season}-w{week}`. The slate ID, lane ID,
lane ordinal, task ordinal, accepted membership hash, and catalog identity
must be copied from the exact structural catalog release entry. A producer or
operator must not independently mint those values even when it can reproduce
the same season/week formula.

Every release and plan validator must require:

- exactly 54 entries in source-task order `0..53`;
- exact ordinal-to-season/week/task/slate agreement;
- exact v12 lane/task agreement;
- no duplicate task, catalog, receipt, bundle, or output URI;
- one common fixed-G0/catalog root;
- one fixed family, role, and code registry; and
- a canonical entry-manifest hash.

## 4. Exact source roles per slate

Every slate should carry exactly 12 roles. The ten component roles are
deliberately one-to-one with ten final components. The current corrected
source reducer averages values when multiple roles are assigned to one
component, so registering raw inputs as independent component roles would
silently implement the wrong science. Raw upstream dependencies instead
belong in the producer receipt for the one derived component role.

| Role | Population/component | Exact upstream inputs | Fixed horizon |
|---|---|---|---|
| `schedule-spine` | target-spine infrastructure | accepted catalog and schedules | exact target slate |
| `qb-depth-evidence` | QB-gate infrastructure | legacy depth or 2025 snapshot depth | target pregame reconstruction |
| `receiver-role-concession` | receiver `role_concession` | weekly stats, FP route, skill depth, schedule, catalog salary tie-break | cross-season prior role windows and prior eight defense games |
| `receiver-alignment-vulnerability` | receiver `alignment_vulnerability` | FP W-4..W-1 alignment and SIS defender rows | prior window; unavailable W1-W4 |
| `receiver-defender-workload-quality` | receiver `defender_workload_quality` | FP alignment and SIS defender workload | common prior eight defense-game horizon |
| `receiver-prior-season-shell-fit` | receiver `shell_fit` | FP receiver and defense coverage | source season exactly N-1 |
| `rb-rushing-concession` | RB `rushing_concession` | weekly stats, FP route, skill depth, schedule | cross-season prior role and defense windows |
| `rb-receiving-concession` | RB `receiving_concession` | weekly stats, FP route, skill depth, schedule | cross-season prior role and defense windows |
| `rb-run-context` | RB `run_context` | SIS team run context and schedule | prior eight games |
| `qb-concession` | QB `qb_concession` | weekly stats and schedule | prior eight games |
| `qb-pressure-inverted` | QB `pressure_inverted` | PFR pass-rush rows and schedule | prior eight games; lower pressure is offense-favorable |
| `qb-secondary` | QB `secondary` | PFR defense rows, snap counts, and schedule | prior six games |

For every non-infrastructure role, the preferred retained shape is exactly
one `(gsis_id, component)` cell per eligible catalog player in that family,
sorted canonically. Unsupported cells are null with a registered reason,
never zero. A wholly unavailable role can retain the existing zero-row
`unavailable` shape, provided its missingness reason is fixed and the producer
receipt still records its expected family population.

The corrected family registry should expose only the component percentile
fields:

```text
receiver: role_concession, alignment_vulnerability,
          defender_workload_quality, shell_fit
rb:       rushing_concession, receiving_concession, run_context
qb:       qb_concession, pressure_inverted, secondary
```

Each `component_source_roles` entry contains exactly its corresponding single
derived role.

## 5. Accepted inputs that should be reused

### 5.1 Accepted v12 structural universe

The accepted v12 chain already carries all 54 structural populations. No new
player query and no world-matrix regeneration is needed.

Shared later-source freeze:

```text
uri: gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/source/later-source-freeze.json
generation: 1787367678830738
sha256: c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a
bytes: 4566802
schema: lr8-later-period-source-freeze-v1
catalog rows: 54
catalog players: 29605
```

Artifact-source completion:

```text
generation: 1787367915631771
sha256: 2d3a97e524fb0f592f0c57ed67643a84281fc97203e348f01031e3c356bded6c
bytes: 383554
```

The R6 catalog is the six-field structural projection
`{id,pos,team,opp,game_id,salary}` in strict ascending player-ID order. Names
and projections are neither population nor matchup authority and must not be
fabricated to satisfy the legacy schema.

### 5.2 Fantasy Points

Reuse without acquisition or regeneration:

- frozen receiver Man/Zone, separation, and defense coverage hashes for
  2022-2025;
- prior-season coverage source seasons 2022-2024 for R6 target seasons
  2023-2025;
- the complete 56-export alignment manifest for 2022-2025 W5-W18, of which
  the 42 target exports for 2023-2025 are used by R6;
- explicit W1-W4 alignment unavailability;
- frozen 2022-2025 route-share files, row counts, source hashes, and retained
  source rows.

Existing normalized GSIS-resolved rows should be captured exactly and reused.
This avoids adding names to the catalog or rerunning identity resolution
against later rosters.

### 5.3 SIS

Reuse without acquisition or regeneration:

- SIS team run-context original/recovery manifests and accepted run states;
- the quarantining of the known bad Passing Value family;
- exact retained source plan/state hashes;
- the receiver-copula 144-artifact grid across 2022-2025, W1-W18, and
  Wide/Slot;
- its stable defender, defense, alignment, coverage-snap, target,
  completion, yard, and touchdown rows.

The old 017n reduction is not reusable because it mixes a defender's teams
and does not use one shared defense-game workload horizon. The raw frozen SIS
evidence is reusable and should be reduced correctly.

### 5.4 Existing open-data machinery

Reuse the source semantics and parsing code for schedules, weekly stats,
legacy depth, 2025 snapshot depth, PFR advanced defense, and snap counts.
Reuse the current formulas from 017l-017q where their inputs and labels match.
Do not reuse the current materialized 017l-017r tables as R6 authority because
their target spines, FP shell season, SIS defender horizon, and lineage are
defective.

The prior assertion that 2025 QB depth is inherently unavailable is too
pessimistic. `nfl_raw.depth_charts_snapshots` exists for 2025 onward, and
`sql/features/003_player_week_role.sql` already maps the latest dated
snapshot on or before a team game day. The genuinely missing item is an exact
immutable extract and producer receipt, not a new download.

### 5.5 Existing v12 candidates

The outcome-blind admission-support census may exact-reopen existing accepted
v12 candidate/world artifacts. It needs roster identities and simulated
research provenance, not regenerated matrices and not realized contest
outcomes.

## 6. Captures genuinely missing

Capture the following once as global source packs, then derive 54 immutable
per-slate slices offline:

1. `nfl_raw.schedules`, 2022-2025, with only the fixed game/time/team fields;
2. `nfl_raw.weekly_stats`, 2022-2025 regular season, with only the role,
   concession, and QB-DK input fields;
3. `nfl_raw.depth_charts`, 2022-2024, for QB and skill-position role evidence;
4. `nfl_raw.depth_charts_snapshots`, 2025, for QB and skill-position role
   evidence;
5. `nfl_raw.pfr_advstats_def` plus `nfl_raw.snap_counts`, 2022-2025;
6. exact normalized FP rows from
   `fantasy_points_receiver_coverage_prior`,
   `fantasy_points_defense_coverage_prior`,
   `fantasy_points_alignment_player_l4`, and
   `fantasy_points_route_share`; and
7. exact normalized SIS rows from `sis_receiver_copula_player_game` and
   `sis_team_run_context_game`.

Items 6 and 7 are immutable projections of already-acquired artifacts, not
data reacquisition. Approximately five warehouse queries plus two
artifact-backed projections are sufficient; 54 times 12 source queries are
unnecessary.

For each mutable warehouse capture, immediately publish canonical normalized
rows to a create-once GCS object and retain:

- exact rendered SQL bytes and SHA-256;
- named parameters;
- project, location, job ID, chronology, cache flag, error result, and bytes
  processed;
- every input relation's schema and observed table metadata;
- retained positive row schema;
- row count and canonical row SHA-256; and
- the exact output object URI, generation, SHA-256, and byte count.

The query snapshot and table modified time are 2026 observation evidence.
They are not historical pre-lock timestamps.

## 7. Target-spine and lock law

For each catalog entry:

1. normalize each catalog `game_id` as its unordered canonical team pair;
2. match it to exactly one target schedule game;
3. require one reciprocal schedule row per team and exact catalog-team
   coverage;
4. require regular-season Sunday-afternoon games unless the accepted catalog
   itself proves a different slate;
5. parse `gameday + gametime` in `America/New_York`, following the existing
   schedule/DST law;
6. define `lock_time_utc` as the minimum kickoff among the catalog's exact
   game set; and
7. require every retained target game kickoff at or after that lock, with at
   least one game exactly at lock.

The catalog defines every target player and every component percentile
denominator. Target-week `weekly_stats`, SIS, or PFR participation cannot add
or remove a player, team, defense, role peer, or QB.

Source-game ordering must use the exact schedule and source-game kickoff, not
lexical week alone. The initial registry should use regular-season games only
so FP, SIS, PFR, and nflverse horizons do not inconsistently admit postseason
games.

## 8. Temporal-provenance correction

The current source v1 cannot honestly capture the real catalog and schedule
unchanged:

- `_normalize_catalog_evidence` requires a non-null
  `maximum_source_event_time_utc` strictly before historical lock;
- every row of a nonempty schedule, depth, or component extract requires a
  timestamp-shaped `source_event_time_utc` and `observed_at_utc`;
- schedule kickoff is a target event at or after lock, not a pre-lock source
  event;
- the accepted historical catalog has exact content and source-period
  authority but no proven historical observation timestamp; and
- legacy depth has target season/week semantics but no historical captured-at
  time.

The tests currently satisfy this surface with convenient synthetic
hour-before-lock timestamps. Production must not copy that fixture behavior.

A successor source schema must:

- permit nullable source-event and observation timestamps when the evidence
  basis is `historical-source-period-only`;
- retain exact source season/week/date periods and exact object identities;
- distinguish target-event timestamps, such as kickoff, from source
  observation timestamps;
- allow a component to cite multiple upstream period kinds while retaining
  one final derived-component role;
- derive the weakest evidence class from its upstream inputs;
- label all historical R6 outputs
  `retrospective-prior-period-reconstruction`;
- keep `authoritative_pit=false`; and
- never replace absent historical time evidence with a caller-selected
  timestamp.

For prior-game sources, source-game kickoff can be derived by exact schedule
join and must be before target lock. FP full-season inputs retain source season
N-1 even where an exact row event time is unavailable. `observed_at_utc`, when
present, is the actual 2026 capture/object time and therefore supports only a
retrospective evidence class.

For 2025 depth, use an exact timestamp only when `dt` provides one. If `dt` is
date-only, a same-gameday snapshot cannot prove it preceded lock. Prefer the
latest snapshot strictly before game day; otherwise materialize unknown rather
than silently promoting the QB. This stricter rule must be evaluated in the
all-54 support census.

## 9. Successor object schemas

### 9.1 `corpus-r6-matchup-upstream-release/v1`

Each ordered pack entry contains:

```text
pack_id
source_kind
positive_row_schema
row_schema_sha256
exact_rows_identity
row_count
rows_sha256
source_period_min
source_period_max
warehouse_query_receipt_identity | frozen_artifact_manifest_identities
projection_code_identity
```

The release contains a fixed namespace, ordered pack manifest and hash,
source-code identity, empty contest/lineup outcome-column reads, false
downstream authorities, and a self-hash.

### 9.2 `corpus-r6-matchup-component-producer-receipt/v1`

Each per-slate receipt contains exactly:

```text
schema_version
producer_id
source_task_ordinal
task_binding
slate
lock_time_utc
catalog_release_identity
catalog_identity
upstream_source_release_identity
family_definition_identities
family_registry_sha256
role_registry_sha256
producer_code_identity
role_entries
role_entry_manifest_sha256
annotation_row_count
annotation_rows_sha256
input_bundle_identity
input_bundle_sha256
target_or_later_deletion_proof
qb_depth_census
component_support_census
outcome_columns_read
uses_realized_outcomes
all false downstream authority fields
producer_receipt_sha256
```

There are exactly 12 role entries. Each role entry contains:

```text
role
population_role
family
component
source_role_schema_sha256
upstream_pack_identities
upstream_slice_row_counts
upstream_slice_rows_sha256
source_period_kinds
source_period_min/max
maximum_source_event_time_utc  # nullable
observed_at_utc                # nullable
observed_at_basis
evidence_class
expected_population_count
retained_row_count
retained_rows_sha256
supported_cell_count
missingness_counts
```

The receipt must cross-bind its exact bundle identity. A self-hash alone is
not authority.

### 9.3 `corpus-r6-matchup-producer-release/v1`

The producer release contains fixed catalog/upstream roots, namespace, code
and family registries, exactly 54 ordered entries, an entry-manifest hash,
false downstream authorities, and a self-hash. Each entry binds:

```text
source_task_ordinal
task_binding
slate
lock_time_utc
catalog_identity
producer_receipt_identity
input_bundle_identity
role_entry_manifest_sha256
capture_output_prefix
```

The finalizer exact-reopens every source pack, receipt, bundle, and catalog,
replays every derivation, and preflights all 54 before publishing the release.
There must be no partial producer release.

### 9.4 `corpus-r6-matchup-capture-plan/v1`

Use one literal repository-relative path, for example:

```text
reports/corpus-r6-matchup-runs/20260826-r6-matchup-source-v2/capture-plan-lock.json
```

The tracked lock pins:

- authoritative structural catalog release identity and internal SHA;
- upstream source release identity and internal SHA;
- producer release identity and internal SHA;
- family, role, and implementation registries;
- one allowed project, bucket, and namespace;
- all 54 ordered entry projections;
- entry-manifest SHA;
- `capture_mechanics_authority=true`; and
- scoring, outcome, graph, fill, retrieval, promotion, publication-policy,
  and production authorities false.

Runtime must secure-read this constant path, require canonical JSON plus one
newline, prove exact equality to the Git blob at HEAD, require a clean scoped
Git status, validate its self-hash, and exact-reopen/rebuild every pinned
release.

Avoid a circular commit hash through a two-commit pin:

1. Commit A contains all producer, source, plan-validator, and operator code.
2. Publish the immutable upstream and producer releases with Commit A's code
   hashes.
3. Generate and review the capture-plan lock.
4. Commit B adds only the lock and associated durable handoff.
5. Runtime binds lock cleanliness to B and code bytes to the Commit A hashes,
   while also proving those code files did not drift at B.

### 9.5 `corpus-r6-matchup-source-release/v1`

After capture, publish one terminal release with exactly 54 ordered entries.
Each binds the source export, source/capture receipt, operator result, producer
receipt, input bundle, and player catalog identities. This release grants
matchup-source mechanics authority only and retains every downstream
authority as false.

## 10. Recommended code and function boundaries

Add versioned successors rather than silently changing the meaning of the
accepted v1 schemas:

- `src/nfl_dfs/research/corpus_r6_matchup_family_v2.py`
  - `frozen_family_registry_v2()`
  - `validate_family_registry_v2()`
  - `frozen_role_registry_v2()`
- `src/nfl_dfs/research/corpus_r6_matchup_upstream_v1.py`
  - positive source-pack schemas;
  - `build_upstream_release_v1()`;
  - `validate_upstream_release_v1()`;
  - `reopen_upstream_release_v1()`;
- `src/nfl_dfs/research/corpus_r6_matchup_component_producer_v1.py`
  - `derive_target_spine_v1()`;
  - family component reducers;
  - actual target-or-later deletion replay;
  - `build_producer_receipt_v1()`;
  - `validate_producer_receipt_v1()`;
  - `build_producer_release_v1()`;
  - `reopen_producer_entry_v1()`;
- `src/nfl_dfs/research/corpus_r6_matchup_source_v2.py`
  - six-field catalog support;
  - honest retrospective temporal schema;
  - exact bundle/producer-receipt source binding;
  - source export/receipt capture and exact reopen;
- `src/nfl_dfs/research/corpus_r6_matchup_capture_plan_v1.py`
  - plan builder and validator;
  - secure tracked-lock replay;
  - fixed ordinal selection;
- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py`
  - ordinal-only execute;
  - create-once publication and exact reopen;
  - operator result receipt;
- `scripts/run_corpus_r6_matchup_source_v2.py`
  - `capture-upstream`;
  - `produce-all`;
  - `support-census`;
  - `freeze-plan`;
  - `capture-one --source-task-ordinal N`;
  - `finalize-source-release`; and
- a successor one-slate/release binding that selects a source-release entry by
  fixed ordinal rather than accepting source identities from a caller.

The current source's rendered SQL is only a union of role/timestamp
projections and does not causally produce the component rows. Source v2 should
bind the exact producer receipt and bundle instead of manufacturing a
BigQuery query-job narrative for an offline multi-source reduction.

## 11. Operator v2 API and trust boundary

The production execute API should be effectively:

```python
run_matchup_source_operator_v2(
    *,
    source_task_ordinal: int,
    repository_root: Path,
) -> dict[str, object]
```

The production call must not accept:

- input-bundle bytes or identity;
- producer receipt or release identity;
- player-catalog identity;
- family definitions or code identity;
- project, bucket, output prefix, or environment;
- a capture carrier or source root; or
- caller storage authority.

The production operator must:

1. replay the tracked capture-plan lock;
2. select exactly one entry by ordinal;
3. exact-open the producer release, receipt, bundle, structural catalog, and
   required source roots;
4. cross-bind task, slate, lock, role, catalog, code, family, source, and
   namespace identities;
5. replay the corrected source semantics;
6. publish only at the entry's fixed output prefix using create-once
   semantics;
7. exact-reopen the source export and source/capture receipt;
8. publish and exact-reopen the operator result; and
9. retain all non-mechanics authorities as false.

Pure tests may use a private injected exact store, but the test store must not
make the root caller-selectable. The tracked plan still chooses every expected
identity.

## 12. Semantic registry that must freeze before publication

The corrected family and producer registry must fix these laws before any
outcome read:

1. **Target population:** the exact catalog family population only.
2. **Source games:** regular season, exact kickoff strictly before target
   lock, ordered cross-season.
3. **Percentiles:** supported values only; strictly-less count divided by
   `n-1`; tied values share rank; one supported value maps to zero.
4. **Orientation:** all final percentiles are offense-favorable; PFR pressure
   is negated before ranking.
5. **Receiver/RB roles:** cross-season last-one/last-four opportunity and FP
   route components, current depth when evidenced, catalog salary only as a
   final deterministic tie-break.
6. **Role support:** at least two role components and the frozen minimum peer
   count.
7. **Defense concessions:** one schedule-derived target-defense spine,
   strictly prior source games, and at least four prior defense games.
8. **FP alignment:** exact W-4..W-1 exports; unavailable W1-W4.
9. **FP shell:** receiver and defense source seasons both exactly target N-1.
10. **SIS alignment vulnerability:** all supported defenders on one shared
    prior-eight target-defense-game horizon, exposure-weighted.
11. **SIS defender workload quality:** top two defenders by prior coverage
    workload for the receiver's dominant alignment, workload-weighted rather
    than an unweighted mean; ties break by stable defender ID.
12. **Trade handling:** only rows whose defense equals the target defense
    enter its workload; a defender's old-team rows cannot enter a new-team
    horizon.
13. **RB run context:** attempt-weighted prior-eight SIS EPA allowed.
14. **QB secondary:** ratio-of-sums PFR DB yards per target, then prior-six
    game aggregation under a frozen support threshold.
15. **Player edge:** unweighted mean of at least two supported component
    percentiles; otherwise null.
16. **Missingness:** explicit registered reason, never zero or implicit
    average.
17. **QB gate:** literal `qb_depth1 is True`; false or unknown is ineligible.
18. **Evidence:** historical R6 is retrospective reconstruction and not
    contemporaneous PIT.

Two current labels do not match their calculations:

- receiver role concession is described as shrunk while the builder uses raw
  DK allowed per game; and
- defender workload quality is described as workload-weighted while the
  builder takes an unweighted top-two mean.

For the shortest initial R6, either retain the current raw per-game
receiver/RB concession calculation under an accurately named new family
field, or freeze a newly versioned shrunk calculation. Do not keep the old
description while changing or retaining a different calculation. Richer raw,
adjusted, and shrunk variants should remain in the source packs for later
Foundry arms without changing the frozen initial R6 registry.

## 13. Producer-level contamination proof

The current corrected source builds synthetic target-week participation
probes after component extracts already exist. That proves the final reducer
ignores the synthetic carrier; it does not prove the upstream component
producer excluded actual target/future source rows.

For each of 54 slates, the producer must run the actual captured inputs twice:

1. with the complete global source packs; and
2. after physically deleting every target-or-later weekly-stats, SIS, and PFR
   source row for that target.

The resulting target population, role labels, component support, component
values, percentiles, and annotation rows must be byte-identical. The receipt
retains full/deleted input hashes, deleted-row counts/hashes, both output
hashes, and `target_or_later_deletion_invariant=true`.

Target schedule rows and evidenced target-week depth are legitimate target
spine/pregame inputs and are not part of this deletion set.

## 14. P0 blockers

1. The six-field catalog implementation remains projection-only until its
   separate fixed-G0 outer adapter and authoritative release are pinned.
2. Matchup source v1 cannot honestly represent the structural catalog and
   schedule temporal evidence without fabricated timestamps.
3. Matchup source v1 hardcodes the legacy eight-field catalog.
4. Source operator v1 execute is intentionally unavailable.
5. No corrected v2 family/role registry is frozen.
6. No immutable schedule, weekly-stats, depth, PFR, normalized FP, or
   normalized SIS source-pack release exists.
7. No 54-member producer release or tracked capture-plan lock exists.
8. The raw-versus-shrunk concession and workload-weighting semantics remain
   unresolved under a corrected family identity.
9. Full-54 admission support is unproven.

The ninth blocker is material. The frozen runner requires:

- the lineup QB's `qb_depth1 is True`;
- at least two supported matchup players;
- lineup annotation completeness of at least `0.5`; and
- at least 80 qualifying candidates, because the entry budget is 80.

W1-W4 FP alignment is legitimately unavailable. Cross-season role,
concession, SIS, PFR, and prior-season shell evidence may still support enough
lineups, but this must be measured outcome-blind before the capture plan is
frozen. No source receipt should assert that support.

## 15. P1 issues

1. Replace the BQ-only role registration with exact bundle/component-object
   identities and producer receipts.
2. Consolidate global source queries instead of issuing per-slate/per-role
   jobs.
3. Replace the synthetic-only deletion proof with the actual producer-level
   deletion replay.
4. Add a terminal exact 54-entry source release rather than leaving 54
   unrelated output pairs.
5. Preserve current 017l-017r tables and task-0 freezes as defect/mechanics
   fixtures only; do not rewrite their histories.
6. Make same-day date-only 2025 depth unknown unless a pre-lock time can be
   proved.
7. Use positive exact schemas and import boundaries rather than depending on
   semantic denylists alone.
8. Require identical-byte create-once collisions to resume and
   different-byte collisions to fail without overwrite.
9. Record per-role upstream slice identities so an immutable component hash
   cannot conceal an alternate upstream reduction.
10. Keep injury/top-defender-out, player names, projections, Neo4j, and richer
    display annotations outside this minimal R6 producer. They can be added as
    later experimental data, but they are not prerequisites for the ten fixed
    component percentiles.

## 16. Required offline tests

No test was run for this audit. Implementation should add focused tests for:

1. exact ordinal `0..53`, season/week, lane/task, task ID, and slate coverage;
2. missing, duplicate, extra, or reordered release entries;
3. a coherent alternate G0, catalog, source-pack, or producer root rejected
   by the tracked plan;
4. dirty, untracked, symlinked, noncanonical, or Git-blob-drifted plan lock;
5. six-field catalog success and legacy/name/projection substitution failure;
6. schedule/catalog game/team reciprocity and exact lock derivation;
7. missing, extra, duplicated, night, or off-slate schedule games;
8. actual target/future weekly-stats deletion invariance;
9. actual target/future SIS/PFR deletion invariance;
10. same-target-season FP receiver or defense shell rejection;
11. exact N-1 FP shell success with both source seasons retained;
12. W1-W4 FP alignment missing rather than fabricated zero;
13. W5-W18 exact W-4..W-1 FP alignment bounds;
14. legacy depth and 2025 snapshot-depth positive paths;
15. future or unevidenced same-day snapshot rejection/unknown handling;
16. one depth row per catalog QB, including explicit false and unknown rows;
17. traded-defender old-team rows excluded from new-team workload;
18. common defense-game horizon and workload-weighted top-two replay;
19. one exact derived role per component and rejection of raw-role averaging;
20. percentile orientation, ties, one-value law, and supported denominator;
21. minimum support and missing-not-zero behavior;
22. source pack, slice, bundle, producer receipt, or code-byte tampering;
23. swapped FP, SIS, PFR, schedule, or depth role identities;
24. player/catalog duplication, omission, or extra rows;
25. alternate output prefix, project, bucket, bundle, or caller carrier
    rejected by execute;
26. ordinal outside `0..53` rejected before external reads or writes;
27. positive source schemas reject contest score, rank, payout, winner, or
    realized-result fields/imports;
28. create-once identical collision resumes and different collision fails;
29. exact source export/receipt/operator-result reopen;
30. terminal release exact 54-entry coverage; and
31. all-54 support census showing the exact QB and admission counts for every
    slate.

## 17. Minimal real census and smoke

### 17.1 Before capture-plan freeze

Run one outcome-blind all-54 producer/support preflight. It should exact-open
the accepted structural catalogs, global source packs, and existing v12
candidate provenance and report for every slate:

- catalog and eligible counts by position/family;
- support count/rate per component;
- receiver W1-W4 alignment unavailability;
- QB counts split into depth true, false, and unknown;
- candidate lineup supported-player and completeness distributions;
- number of qualifying candidates;
- whether the exact 80-entry budget can be satisfied; and
- actual target-or-later deletion invariance.

This census reads no realized lineup score or contest outcome and does not
regenerate matrices. Any slate below 80 remains a blocker. Do not weaken the
gate after outcome inspection; either repair genuine source/depth coverage or
freeze a new outcome-blind missingness policy before any realized read.

### 17.2 After the lock is reviewed and committed

The minimum real mechanics smoke is:

1. execute source-task ordinal 0 only through the tracked plan;
2. exact-reopen its catalog, producer receipt, input bundle, source export,
   source/capture receipt, and operator result;
3. prove structural catalog equality and all role/source hashes;
4. run the corrected one-slate R6 mechanics at the frozen dose without
   outcomes;
5. require source evidence at least
   `retrospective-prior-period-reconstruction`, with
   `authoritative_pit=false`; and
6. require exact 80-entry books/traces and all downstream authorities false.

The all-54 preflight already exercises 2025 snapshot depth, so a second full
book smoke is not necessary merely to test that path. After task 0 passes,
fan out the other 53 ordinal-only captures from the same image and fixed plan,
then publish the terminal source release.

## 18. Shortest honest implementation sequence

1. Accept and pin the structural catalog outer adapter/release.
2. In one code commit, add the v2 family/role registry, source-pack contract,
   deterministic component producer, honest source v2, capture-plan
   validator, ordinal-only operator v2, CLI, and focused offline tests.
3. Capture the global open-data and normalized vendor source packs once.
4. Produce all 54 bundles/receipts and run the all-54 outcome-blind support
   census before any plan publication.
5. Fail closed and repair only genuine data/semantic defects if any slate has
   unknown QB coverage or fewer than 80 qualifying candidates.
6. Publish and exact-reopen one complete 54-entry producer release.
7. Generate the capture-plan lock, review it independently, and commit it in
   the second pin commit.
8. Build/deploy the one fixed image containing that tracked lock.
9. Run the ordinal-0 real mechanics smoke.
10. Fan out ordinals 1-53 without redeployment or new warehouse queries.
11. Finalize the exact 54-entry source release.
12. Only after R6 books and traces freeze may the separately governed outcome
    path open realized contest results.

This sequence distinguishes true capture from unnecessary regeneration,
removes per-slate deployment/query overhead, and provides the operator one
reviewable non-caller-selectable authority root.
