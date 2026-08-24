# R6-v2 matchup point-in-time lineage disposition

Date: 2026-08-24
Status: **DOCUMENTATION-ONLY LINEAGE DISPOSITION — CURRENT 017r IS NOT PIT**

This report records the outcome-blind lineage audit required before a real
R6-v2 matchup-source smoke. It does not read a realized score, state a matchup
outcome verdict, license an R6-v2 freeze on the current data, or carry fill,
retrieval, promotion, deployment, or production-policy authority.

The disposition is unambiguous:

- the current `player_matchup_week_pit`/017r path is
  **`non-pit-retrospective`**;
- a mechanics-only smoke may consume it only while retaining that exact label
  and while carrying no R6-v2 freeze or scientific authority;
- an R6-v2 freeze requires, at minimum, the corrected
  **`retrospective-prior-period-reconstruction`** class described below;
- no historical 2023--2025 source may be called
  **`contemporaneous-prelock`** unless exact source bytes and their observation
  or retrieval time at the historical lock can actually be reopened and
  verified; and
- create-once publication can make an artifact authoritative as content. It
  cannot retroactively upgrade the temporal evidence class of its inputs.

No cloud command, warehouse query, realized-outcome read, build, deployment,
IAM operation, test, active-run inspection, or existing artifact mutation was
performed for this audit.

## 1. Purpose and decision boundary

R6-v2 proposes to admit lineups using pre-lock receiver, RB, and QB matchup
information. The admission decision is score-free only if all four of these
claims are true and independently replayable:

1. the complete player denominator was knowable at the slate lock;
2. every component value uses only information available before that lock;
3. the exact rows, source roles, transformations, and missingness laws can be
   reopened after mutable warehouse tables are rebuilt; and
4. no caller can turn an unsupported timestamp assertion into a PIT claim.

The current implementation does not satisfy those claims. Most rolling
windows are numerically prior-week, but prior-week arithmetic alone is not an
end-to-end PIT proof. The implementation also uses completed target-season
Fantasy Points data, postgame target-week participation to construct several
target universes, current rebuildable BigQuery tables without immutable row
exports, and caller-supplied maximum-source timestamps.

This is a source-lineage finding, not a result for or against matchup
intelligence. It does not say whether matchup-aware admission helps. It says
that the current feed cannot support that conclusion under a PIT label.

## 2. Evidence-class vocabulary

The implementation and every receipt must use one of the following exact
classes. Similar prose is not a substitute for the registered value.

### 2.1 `non-pit-retrospective`

At least one consumed field or population uses information from the target
week or later, uses a target-season aggregate that includes future weeks, or
cannot distinguish those cases. This class is permitted only for mechanical
integration testing and defect diagnosis. It has no R6-v2 freeze, outcome
verdict, promotion, or production authority.

The current 017r feed is in this class because:

- its Fantasy Points shell component joins completed target-season aggregates;
- its receiver/RB/QB target populations are at least partly anchored by
  target-week postgame row existence; and
- its claimed maximum-source timestamp is not derived from retained source
  evidence.

### 2.2 `retrospective-prior-period-reconstruction`

Every feature and population is constructed using only source periods that
precede the target lock, but the exact vendor/open-data bytes were acquired or
reconstructed after the historical lock. Later vendor corrections therefore
cannot always be excluded.

This is the minimum class allowed for an R6-v2 freeze. R6-v2 must name it
explicitly as preregistered retrospective evidence; it must not relabel it as
a contemporaneously captured historical forecast. Reaching this class
requires all corrective actions and the exact create-once seam in this report.

### 2.3 `contemporaneous-prelock`

Exact source bytes were captured before the slate lock; the capture or
observation time is itself evidenced; all source rows precede the lock; and
the bytes and receipt can be reopened by content identity. This is the target
class for 2026 prospective weekly collection.

Historical source-event dates do not by themselves establish this class. A
file downloaded in 2026 that describes 2023 Week 4 can support a retrospective
prior-period reconstruction, but it does not prove what the system could have
read at the 2023 Week 5 lock.

## 3. Current data path

The all-week modeling feed is built by:

1. `sql/research/017l_receiver_week_role_pit.sql`;
2. `sql/research/017m_defense_receiver_role_concession_pit.sql`;
3. `sql/research/017n_defender_alignment_quality_week_pit.sql`;
4. `sql/research/017o_rb_week_role_pit.sql`;
5. `sql/research/017p_defense_rb_role_concession_pit.sql`;
6. `sql/research/017q_team_defense_context_pit.sql`;
7. `sql/research/017r_player_matchup_week_pit.sql`; and, in the current build
   script, also
8. `sql/research/017s_lineup_matchup_evidence.sql`.

The per-slate Python annotation path separately reads built tables and raw
Fantasy Points tables in:

- `src/nfl_dfs/research/receiver_matchup_annotations.py`;
- `src/nfl_dfs/research/rb_qb_matchup_annotations.py`;
- `scripts/annotate_receiver_matchup_slate.py`; and
- `scripts/annotate_rb_qb_matchup_slate.py`.

R6 runner v2 then accepts already-computed player rows through
`build_matchup_source_snapshot` in
`src/nfl_dfs/research/corpus_batch_retrieval_runner_v2.py`.

These paths are not currently one source-authoritative pipeline. They use
different percentile populations, do not retain the same evidence, and the
runner can label arbitrary caller-provided rows as relation 017r.

## 4. Concrete lineage defects

### D1. Completed target-season Fantasy Points data enters c4

`sql/research/017r_player_matchup_week_pit.sql:50-53` computes league Man rate
from `fantasy_points_defense_coverage_prior` by its stored `season`.
Lines 69-78 compute receiver Man/Zone values from
`fantasy_points_receiver_coverage_prior`, also by stored `season`. Lines
109-138 join all three shell inputs with `source.season = target.season`.

The importer preserves the exported source season:

- `src/nfl_dfs/ingest/fantasy_points_coverage.py:116-120` validates the
  export's actual season;
- lines 195-215 write that same season on receiver rows; and
- lines 258-280 do the same for defense rows.

The repository's frozen coverage-fit law says the opposite: target season N
must use source season N-1. See
`reports/2026-08-10-fantasy-points-coverage-fit-experiment.md:37-48`.

Consequently, a 2023 Week 1 c4 value is computed from the completed 2023
season, not the completed 2022 season. The same leak exists for every 2024 and
2025 target week.

The direct per-slate builder repeats the defect at
`src/nfl_dfs/research/receiver_matchup_annotations.py:526-537`, where both
full-season tables are queried with the target `season`.

Required repair: join full-season receiver and defense shell rows on
`source.season = target.season - 1`, retain both source seasons in every
output, and fail if either differs. If that cannot be done under a newly
versioned source contract, c4 must be omitted and remain missing. A silent
semantic substitution under the frozen family identity is forbidden.

### D2. Target-week postgame participation defines receiver and RB roles

`017l` explicitly creates one row for each WR/TE player-week that appears in
`weekly_stats` (`017l:8-13`, `27-47`). Its numerical windows end at one
preceding row (`63-82`), but the target row and within-team percentile
population exist only because the player recorded a target-week postgame row
(`98-130`). Removing a target-week appearance can change:

- whether the player exists;
- `eligible_teammate_count`;
- all role-component percentiles;
- consensus and sensitivity ranks; and
- WR1/WR2/WR3+/TE1/TE2+ role labels.

`017o` repeats the same pattern for RBs (`017o:15-37`, `43-68`, `82-109`).
Thus the values may be computed from prior games, but their denominator and
row existence are not pre-lock.

Required repair: the target spine and the percentile denominator must come
from the accepted, exact slate player catalog joined to the schedule. Prior
`weekly_stats` rows may contribute feature values only after an explicit
source-period filter; target-week `weekly_stats` may not determine existence,
rank, or support.

### D3. QB existence is also postgame-derived

`017r:169-177` derives `qb_players` directly from target-week
`weekly_stats`. The QB matchup row therefore exists only for a QB who recorded
a target-week row. `017r:178-213` then adds target-week depth information and
prior team-defense context.

Required repair: enumerate QBs from the accepted catalog. Treat depth status
as a separate, time-evidenced annotation, never as the QB population spine.

### D4. Defense target rows are partly anchored by completed-game feeds

The same pattern exists below the player level:

- `017m` derives defense-game structure through completed receiver outcome
  rows. Its windows are prior-row, but a target defense week is not present
  until postgame rows exist. A game without a supported receiver can disappear
  rather than contribute the intended zero/missing evidence.
- `017n:70-81` derives target defense weeks from SIS defender-game rows, not
  from the schedule. Prior defenders are joined to those postgame-established
  target rows at `83-116`.
- `017q:24-177` builds SIS, PFR, and QB-defense window rows on each source's
  completed-game spine. Its union spine at `178-184` is therefore a union of
  postgame source presence rather than a pre-lock schedule spine.

Required repair: use one schedule-derived team/opponent/target-week spine for
all defense contexts. Join only source games strictly before the target.
Source absence must remain explicit missingness rather than altering whether
the target row exists.

### D5. Current-week depth is asserted pregame, not evidenced as-of lock

Receiver and RB role SQL joins target-week `depth_charts` without an
observation or retrieval timestamp (`017l:84-104`; `017o:70-86`). QB depth is
handled similarly in `017r:178-182`.

The SQL comments say the depth chart is published before kickoff, but the
warehouse relation is not queried as of a historical observation, and the
rows are not bound to a capture identity. The source ends in 2024
(`017l:24-25`; `017r:25-26`). Therefore 2025 QB depth is null.

Runner v2 excludes a QB only when `qb_depth1 is False`
(`corpus_batch_retrieval_runner_v2.py:777-781`). A null/unknown 2025 QB is
included, so the documented starter gate does not establish that the QB was a
starter.

Required repair: use a contemporaneous or explicitly retrospective pregame
depth snapshot with `observed_at_utc <= lock_time_utc`. If none exists, depth
must be unknown. R6-v2 must freeze whether an unknown-QB lineup is excluded or
the entire slate is matchup-unavailable; unknown may not silently mean
starter.

### D6. The SIS defender window mixes teams after trades

`017n:64-67` partitions the through-eight window by
`defender_player_id, alignment`, not by defense. A defender's old-team snaps
can therefore enter his new team's current quality row. Lines 149-160 then
sum defender-specific cumulative windows to form defense exposure, rather
than measuring all defenders on one common prior-eight defense-game horizon.

Required repair: separate career-quality estimation from same-defense
workload. The exposure denominator must use one shared prior defense-game
horizon. Team membership, current roster state, and any lock-time injury state
must be explicit inputs rather than inferred from target-week postgame SIS
presence.

### D7. Source-role identity is false in the receiver publisher

The receiver family declares both Fantasy Points shell fit and PFR secondary
roles at `receiver_matchup_contract.py:488-495`. But
`fetch_slate_inputs` reads Fantasy Points receiver and defense shell rows and
does not read PFR secondary rows (`receiver_matchup_annotations.py:526-537`).

`scripts/annotate_receiver_matchup_slate.py:130-152` then:

- names `defense_week_coverage` as the `pfr-secondary` table; but
- hashes `inputs.shell_defense_rows`, which are Fantasy Points defense rows,
  under that role.

The URI/table metadata and hashed row content therefore describe different
sources. The Fantasy Points defense shell has no honest source role, and PFR
secondary data does not enter the receiver calculation.

Required repair: register separate Fantasy Points receiver-shell and
defense-shell roles. Either consume the exact PFR rows represented by the PFR
role or remove that role in a new family version.

### D8. The maximum source time is a caller assertion

`receiver_matchup_contract.py:277-312` validates only that a caller-provided
`maximum_source_time_utc` is lexically before the lock and that source
identity objects have the expected shape. It does not exact-read the sources
or derive the maximum observation time.

Runner v2 repeats this at
`corpus_batch_retrieval_runner_v2.py:554-584`. When the caller's timestamp is
before lock, it writes `point_in_time_at_lock: true` at lines 653-675. Its
validator reconstructs the same caller claims rather than independently
establishing them (`678-754`).

Required repair: remove the public timestamp argument from authoritative
construction. Compute source-event and observation maxima from reopened
component evidence. A missing observation time must produce the retrospective
class or a refusal; it must not be replaced with a convenient pre-lock value.

### D9. Current BigQuery “generation” values are not immutable row objects

The annotation scripts compute source identities by:

1. hashing the in-memory result rows;
2. attaching a `bq://table?season=&week=` URI; and
3. using `table.modified` milliseconds as a field named `generation`.

See `annotate_receiver_matchup_slate.py:154-168` and
`annotate_rb_qb_matchup_slate.py:113-151`.

A BigQuery table-modified timestamp is not an exact-readable object
generation. The result rows are not retained. Once a `CREATE OR REPLACE`
rebuild occurs, an independent verifier cannot recover the hashed row body.
The query SQL, job ID, parameter values, source table versions, and source
observation maxima are also absent.

Required repair: publish exact canonical query-result/source-extract bytes to
create-once object storage and bind them from a separate query receipt.

### D10. Sequential `CREATE OR REPLACE` has no common snapshot

`scripts/build_receiver_matchup_features.py:36-45` lists 017l through 017s,
and lines 301-306 execute them sequentially. Each SQL file creates or replaces
a table. There is no transaction, single as-of timestamp, snapshot-table
identity, or source bundle retained across the chain. A raw or intermediate
table can change between steps.

The build receipt printed at lines 345-354 contains row counts, checks, and a
boolean policy claim. It does not contain rendered SQL hashes, query job IDs,
source table schemas/etags, exact output row hashes, component periods,
retrieval times, or immutable output identities.

Required repair: the R6 source capture must use a single parameterized slate
query over already pinned/exact source extracts, or one explicitly recorded
common BigQuery snapshot time. The result must be exported immediately and
reopened by content identity.

### D11. The existing build command reads realized outcomes through 017s

`scripts/build_receiver_matchup_features.py` executes
`017s_lineup_matchup_evidence.sql`. Its validation at lines 247-266 reads
`lineup_matchup_evidence.actual_gt_200` and
`replay_candidates.actual_score`.

The script-level statement that no realized target-week outcome is used “as a
feature” does not make it an outcome-blind R6 smoke path. R6-v2's pre-freeze
boundary prohibits the read, not merely use in a model feature.

Required repair: create a new source-export command that runs only the
corrected source/annotation path. It must not dispatch 017s or import an
outcome-bearing module.

### D12. 017r output loses the provenance required to prove its name

The 017l--017q tables retain some `max_source_season_week` fields, but
`017r:237-260` emits the raw/percentile components and composite edge without
component source periods, retrieval/observation times, raw object identities,
or a computed overall bound. A row in `player_matchup_week_pit` cannot by
itself prove why it is PIT.

Further, `017r:9-15` explicitly uses the weekly position group as its
percentile universe. That group is a postgame-derived population under the
current spines. The Python per-slate annotator instead ranks over all eligible
WR/TE, RB, or QB rows in its supplied catalog. Those are different algorithms
unless equality is demonstrated for the exact slate.

Required repair: retain the named percentile universe and its ordered player
ID hash, source bounds per component, component support, and exact catalog
binding in the exported row object.

### D13. Contract descriptions do not exactly match calculations

Two non-temporal mismatches undermine replayability:

- `opponent_role_concession_l8` is described as shrunk at
  `receiver_matchup_contract.py:470`, but the builder consumes raw
  `receiving_dk_allowed_per_game_l8`.
- `defender_workload_quality_l8` is described as workload-weighted at
  `receiver_matchup_contract.py:476`, but
  `receiver_matchup_annotations.py:159-162` takes an unweighted mean of the
  top-two supported defender rates.

`opponent_role_concession_over_expectation_l8` and
`top_workload_defender_out` are also always null in the current builder
(`receiver_matchup_annotations.py:351-352`, `399-400`).

Required repair: choose and version exact semantics before the corrected
smoke. The receipt must bind the new family-definition hash. Do not keep an
old label while changing its calculation.

### D14. Runner v2 does not reopen what it claims to bind

`build_matchup_source_snapshot` accepts raw lists plus two identity-shaped
dictionaries. It does not read either object, verify catalog contents, verify
query-receipt schema, bind query output to the rows, or prove that the rows
came from 017r. It also accepts any finite edge value rather than enforcing
the registered `[0,1]` percentile interval
(`corpus_batch_retrieval_runner_v2.py:624-647`).

Required repair: authoritative runner input must be object identities plus an
exact-reader callback. Raw eligible/annotation lists and a caller timestamp
may remain fixture-only helpers, but they cannot construct an authoritative
snapshot.

## 5. Field-level temporal assessment

| Family/component | Current source law | Current evidence class | Corrected minimum |
|---|---|---|---|
| Receiver role target/air share | Last 1/4 prior `weekly_stats` rows, but target player and teammate denominator come from target-week rows | `non-pit-retrospective` | Catalog/schedule spine; explicit source rows before target |
| Receiver route share | Prior route rows; full-season weekly export acquired retrospectively | `retrospective-prior-period-reconstruction` for the value, but contaminated by the current target spine | Exact source file/hash and prior weeks; catalog denominator |
| Receiver current depth | Target-week depth row, no historical observed-at proof | Retrospective/unknown; not proven pre-lock | Captured-at evidence or explicit missing |
| Receiver role concession | Prior defense-game receiver outcomes, but defense target spine comes from completed rows | `non-pit-retrospective` as an end-to-end feed | Schedule spine and strictly prior source games |
| FP alignment c2/c3 input | Manifest-locked W-4..W-1, target Weeks 5--18 only | `retrospective-prior-period-reconstruction` | Retain exact artifact identity and source weeks; missing in Weeks 1--4 |
| SIS defender c2/c3 input | Prior SIS games, retrospectively acquired; current target spine; trade-window defect | `non-pit-retrospective` end to end | Schedule spine, corrected team horizon, exact artifact evidence |
| FP shell c4 | Completed full target season | `non-pit-retrospective` | Source season N-1 or missing |
| RB role | Prior carry/target/route windows; target-week participant/depth denominator | `non-pit-retrospective` | Catalog/schedule spine; explicit prior sources; evidenced depth |
| RB concessions | Prior defense games on a postgame-derived target spine | `non-pit-retrospective` | Schedule spine and retained prior-game bounds |
| SIS run context | Prior eight source games, artifact-manifested but retrospectively acquired | `retrospective-prior-period-reconstruction` for values after spine repair | Exact artifact/source rows and prior-period proof |
| QB concession | Prior eight QB outcome rows; target defense/source spine is completed-game-derived | `non-pit-retrospective` end to end | Schedule spine; strictly prior source rows |
| PFR pressure | Prior eight PFR games, current mutable table | Retrospective value; no immutable row authority | Exact source extract/object and source periods |
| PFR secondary YPT | Prior six games in `defense_week_coverage`; current mutable table | Retrospective value; no immutable row authority | Exact source extract/object and source periods |
| QB depth gate | Target-week legacy depth; 2025 absent; null admitted | Not a proven starter gate | Evidenced status or fail-closed missing law |

## 6. Exact evidence that already exists

Existing evidence should be reused where it is honest. None of the following
needs an IAM census to become an input to a new content receipt.

### 6.1 Task-0 player catalog

The task-0 catalog has this exact GCS identity:

```text
uri: gs://nfl-predictions-503414-corpus-retrieval/research/corpus-retrieval-inputs/20260821-corpus-retrieval-engine-v1/tasks/0000/player-catalog.json
generation: 1787351685685892
sha256: 55c7f6efcbee49ad1b8c58b8be7a0446c564fc9796acb7137e637a178992264d
bytes: 105469
```

The checked-in local equivalent is
`reports/corpus-retrieval-runs/20260821-corpus-retrieval-engine-v1/task0/live-bfe2e48/player-catalog.json`.
It contains 773 players and has a self-hashed catalog schema.

Its source SQL is retained at
`reports/corpus-retrieval-runs/20260821-corpus-retrieval-engine-v1/governance/player-catalog.sql`.
That SQL uses:

```text
FOR SYSTEM_TIME AS OF TIMESTAMP('2026-08-21T17:42:00Z')
```

against
`nfl_forensic_review.final_forensic_20260814_player_corpus_repair4`, filtered
to 2023 Week 1. It selects ID, name, position, team, opponent, game, salary,
and projection; it does not select an actual outcome.

The exact query authority is retained at
`reports/corpus-retrieval-runs/20260821-corpus-retrieval-engine-v1/task0/input-capture/query-authority.json`:

```text
player job: corpus_retrieval_v1_players_20260821t174200z
project/location: nfl-predictions-503414 / US
row_count: 773
cache_hit: false
sql_sha256: d6e2dff351a4a8d2a7f10db917edd33574453272dc86b33bdf43dda1a29e2996
normalized_rows_sha256: 16e45cfef9954e1c3afc3960416450b962ddb6ede8f19a413d92c40373272b76
query_authority_sha256: 483b4c52d5595c7403a552bbc12f32faa3b42ca5616b2211eee6a5c74a00c9e2
snapshot_at_utc: 2026-08-21T17:42:00Z
uses_realized_outcomes: false
```

The companion validation at
`task0/input-capture/validation.json` binds the catalog to the five world
artifacts, reports 250 catalog players used by candidates, and has validation
SHA-256
`ad192f0102ec299c66e767f671f3bdead623b6d26aa180961a0de4191546b9af`.

This proves exact, outcome-free capture in 2026 and consistency with the
task-0 corpus artifacts. It does not prove that all 773 rows were a
contemporaneously captured eligible population at the 2023 lock. No
equivalent checked-in per-slate player-catalog/query receipt was found for the
other v12 slates. The corrected adapter must either reopen an exact accepted
catalog carried by each slate or create and bind one without reading an
outcome.

### 6.2 Fantasy Points full-season coverage files

`src/nfl_dfs/ingest/fantasy_points_coverage.py:27-44` contains exact hashes
for the 2022--2025 receiver Man/Zone, receiver separation, and defense matrix
exports. It verifies source season, schema, row counts, identities, row
numbers, and source hashes. The importer writes only to an empty table or
accepts an already-identical table (`303-321`, `335-364`).

Those hashes are strong content evidence. They do not make same-season use
valid. Corrected c4 must bind a prior-season file identity and retain the
source season used for both receiver and defense.

### 6.3 Fantasy Points alignment and route evidence

`src/nfl_dfs/ingest/fantasy_points_alignment_l4.py:33-81` verifies a complete
56-export grid for 2022--2025 target Weeks 5--18, exact W-4..W-1 source-week
lists, path/hash/bytes/shape, and one export per target. Lines 170-197 retain
source weeks, file, hash, and source rows; lines 218-219 assert source week is
before target week.

`src/nfl_dfs/ingest/fantasy_points_route.py:16-22` freezes exact 2022--2025
file hashes and row counts, while lines 133-158 retain per-week source rows
and identities. These are usable retrospective source-content authorities,
but their historical capture times are not pre-lock authorities.

### 6.4 SIS evidence

The SIS run-context importer binds the original/recovery plans and run states,
validates all accepted artifact manifests and hashes, quarantines the known
bad Passing Value family, records source plan/state hashes on every row, and
writes the raw table once:

- `src/nfl_dfs/ingest/sis_team_run_context.py:34-52`;
- `54-100`;
- `103-251`; and
- `255-282`.

The defender-grain SIS receiver-copula acquisition similarly retains exact
artifact manifests and stable SIS identities. These are strong retrospective
content records. They were acquired in August 2026 and do not establish what
bytes were visible at each 2023--2025 slate lock.

### 6.5 PFR, nflverse, schedule, and depth evidence

The current SQL reads mutable BigQuery relations such as `weekly_stats`,
`pfr_advstats_def`, `snap_counts`, `schedules`, `depth_charts`, and derived
`defense_week_coverage`. The queried rows are not retained in a create-once
per-slate source export, and the R6 path carries no exact source query receipt
for them. Their values may support a retrospective reconstruction after
strict period filters, but the current relations are not exact source
authorities for R6.

### 6.6 Existing matchup smoke and freeze receipts

The task-0 receiver smoke receipt is:

```text
reports/receiver-matchup-runs/20260822-task0-annotation-smoke-v1/smoke-receipt.json
smoke_receipt_sha256: 7d46c49471dad0ea1d0d92f80d53e0449a2e50979a11e2d00181b1ae342e48c7
analysis_grade: false
```

Its family-freeze receipt has SHA-256
`24b9ba0583a217c4ae9453fd005ac17e33f32fd071e705e29fd45e51a28dcdb3`.
It claims maximum source time `2023-09-10T16:00:00Z` from prose asserting
that shell data was prior-season. The implementation actually read completed
target-season shell data, so that derivation is false.

The RB/QB smoke receipt is:

```text
reports/receiver-matchup-runs/20260822-task0-rb-qb-smoke-v1/rb-qb-smoke-receipt.json
smoke_receipt_sha256: 26abfe313aa9a1aa4e604e3e566259ebdd285bf2d3eb93ca9c70e65da747f89f
family_provisional: true
```

Its family-freeze receipt has SHA-256
`67bc5181e420b076d8d6e0d5b9bf5ff7ea17f49501a20caf66a94e2f369fff5e`.

These objects are useful defect and algorithm fixtures. They do not prove PIT
lineage and must not be used to upgrade current 017r to analysis-grade or
R6-v2-authoritative status.

## 7. Why current 017r cannot be called PIT

The name `player_matchup_week_pit` and the presence of several
`1 PRECEDING` windows are insufficient. A PIT claim belongs to the complete
transformation, not to one window clause.

Current 017r fails at four distinct layers:

1. **Value time:** c4 contains future target-season games.
2. **Population time:** target-week postgame participation determines player,
   teammate, QB, and some defense populations.
3. **Observation time:** retrospective source tables do not establish when
   their exact bytes were observed relative to historical lock.
4. **Evidence persistence:** replaceable BigQuery rows and a claimed timestamp
   cannot be independently reopened.

Therefore:

```text
current relation name: player_matchup_week_pit
honest evidence class: non-pit-retrospective
mechanics-only smoke: permitted with that label
R6-v2 freeze: prohibited
promotion authority: false
```

## 8. Minimum non-IAM create-once seam

The minimum durable seam is two new objects per slate, plus exact reopening of
the existing player catalog. It deliberately excludes an IAM census,
effective-policy analysis, role creation, bucket-policy mutation, and a new
deployment cycle.

Publication uses the already authorized operator or workload identity, a
dedicated bounded prefix, and create-if-absent semantics. If create or exact
GET is not already allowed, the capture fails closed and reports that
operational blocker; it does not start an IAM project.

### 8.1 Object 1 — `matchup-source-export.json`

Schema: `corpus-r6-matchup-source-export/v1`.

Required fields:

```text
schema_version
publication_mode = create_once
slate = {season, week, slate_id, task_id}
lock_time_utc
created_at_utc
evidence_class
family_definition_identities
player_catalog_identity
player_catalog_content_sha256
percentile_universe = {name, ordered_player_ids_sha256, row_count}
source_extracts[]
eligible_player_count
eligible_players_sha256
rows[]
rows_sha256
outcome_columns_read = []
uses_realized_outcomes = false
fill_authority = false
retrieval_authority = false
promotion_authority = false
production_policy_authority = false
matchup_source_export_sha256
```

Each `source_extracts[]` entry must contain:

```text
role
relation_or_object
source_identity_or_extract_sha256
rows and rows_sha256, or an exact-readable object identity
row_count
source_season_week_min
source_season_week_max
maximum_source_event_time_utc
observed_at_utc
observed_at_basis
evidence_class
missingness_reason, when unavailable
```

`observed_at_basis` is an enum, not prose:

- `vendor-retrieved-at`;
- `raw-object-created-at`;
- `warehouse-ingested-at`;
- `warehouse-table-modified-at`;
- `historical-source-period-only`; or
- `unknown`.

Each final `rows[]` entry is sorted by `gsis_id` and contains exactly:

```text
gsis_id
family                         # receiver | rb | qb
position                       # WR | TE | RB | QB
qb_depth1                      # true | false | null
qb_depth_evidence_class
component_values
component_support
component_source_bounds
matchup_component_count
matchup_edge_score             # null or finite in [0, 1]
annotation_row_present
```

There must be exactly one row for every eligible skill player in the bound
catalog. A missing annotation is represented by null component/edge values and
`annotation_row_present=false`; it is never dropped or changed to zero.

The export may embed exact component rows or bind separate exact-readable
component objects. Merely recording a hash of rows that are then discarded is
not sufficient.

### 8.2 Object 2 — `matchup-query-receipt.json`

Schema: `corpus-r6-matchup-query-receipt/v1`.

This object is published after Object 1, so it can bind Object 1's complete
`uri/generation/sha256/bytes` identity. Required fields:

```text
schema_version
slate
lock_time_utc
created_at_utc
rendered_sql_sha256
rendered_sql_identity or rendered_sql_bytes
query_parameters
query_snapshot_at_utc
query_job = {
  project, location, job_id, created, started, ended,
  cache_hit, error_result, total_bytes_processed
}
code_identity
player_catalog_identity
source_export_identity
source_relations[] = {
  role, table_or_object, schema_sha256, etag_or_generation,
  modified_or_created_at_utc, exact_extract_sha256, row_count
}
component_temporal_evidence[]
maximum_source_event_time_utc
maximum_observed_at_utc
full_season_same_target_year_used
target_week_participation_universe_used
outcome_columns_read = []
uses_realized_outcomes = false
evidence_class
authoritative_for_mechanics
authoritative_pit
fill_authority = false
retrieval_authority = false
promotion_authority = false
production_policy_authority = false
matchup_query_receipt_sha256
```

`authoritative_pit` is derived, never supplied:

- it is false for `non-pit-retrospective`;
- it is false under the strict contemporaneous definition for
  `retrospective-prior-period-reconstruction`, although the artifact may be
  authoritative for a preregistered retrospective R6-v2 analysis; and
- it is true only when every consumed component and the player universe are
  `contemporaneous-prelock`, every observation is before lock, and all objects
  reopen exactly.

The receipt must set
`full_season_same_target_year_used=false` and
`target_week_participation_universe_used=false` for any corrected R6-v2
source. These are computed checks, not operator declarations.

### 8.3 Construction API

The score-free capture interface should be:

```python
def capture_matchup_source_v1(
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    player_catalog_identity: Mapping[str, object],
    player_catalog_raw: bytes,
    rendered_sql_raw: bytes,
    query_job_receipt: Mapping[str, object],
    component_extracts: Sequence[Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    family_definition_identities: Mapping[str, Mapping[str, object]],
    code_identity: Mapping[str, object],
    publish_create_once: Callable[[str, bytes], Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
    output_prefix: str,
) -> dict[str, Mapping[str, object]]:
    """Publish export then query receipt, reopen both, and return identities."""
```

The function must:

1. exact-read and validate the catalog identity before computing rows;
2. derive the eligible player denominator from that catalog;
3. validate exact component source roles and periods;
4. derive temporal maxima and evidence class;
5. reject outcome-bearing field names and imports;
6. canonicalize and self-hash Object 1;
7. publish Object 1 with generation-match zero;
8. exact-read Object 1 by its returned identity;
9. build/self-hash Object 2 with Object 1's identity;
10. publish Object 2 with generation-match zero;
11. exact-read Object 2 and verify all bindings; and
12. return only the two normalized object identities.

There is no public `maximum_source_time_utc` argument. The function derives
both maxima from component evidence.

### 8.4 Runner reopening API

Authoritative runner input becomes:

```python
def reopen_matchup_source_snapshot(
    *,
    source_export_identity: Mapping[str, object],
    query_receipt_identity: Mapping[str, object],
    player_catalog_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
    expected_slate: Mapping[str, object],
    required_evidence_class: str,
) -> dict[str, object]:
    """Exact-read, bind, and normalize one matchup source snapshot."""
```

It must fail unless:

- all three objects exact-read by `uri/generation/sha256/bytes`;
- both new objects are canonical and self-hash correctly;
- receipt output identity equals the supplied export identity;
- export and receipt bind the supplied catalog identity;
- task/slate/season/week/lock agree everywhere;
- every catalog skill player appears exactly once;
- every annotation family/position mapping is valid;
- component source roles equal the frozen family dictionaries;
- all edge values are null or finite in `[0,1]`;
- row/order/universe hashes replay;
- no outcome field or outcome-bearing import is present;
- the derived evidence class meets `required_evidence_class`; and
- corrected R6 use has neither same-target-season full-season data nor a
  target-week participation spine.

The current raw-list builder can remain private fixture support. It must not
set `point_in_time_at_lock=true` or construct an authoritative object.

## 9. Corrected source construction

The fastest honest implementation is a new, slate-parameterized source query
or offline reducer, not another execution of the all-table build script.

### 9.1 Pre-lock target spine

Build one canonical target spine from:

- the exact accepted player catalog;
- the exact schedule/slate definition;
- deterministic position-to-family mapping; and
- a separately evidenced QB/depth status source.

The spine defines all percentile populations. `weekly_stats`, SIS, or PFR
target-week row existence may not add or remove target players or defenses.

### 9.2 Source-period filters

Every outcome-derived input must have an explicit source period before target:

- prior player target/air/carry/route windows: source game before target;
- receiver/RB/QB defense concessions: source game before target;
- SIS defender and run-defense windows: source game before target;
- PFR pressure/secondary windows: source game before target;
- FP alignment: exactly W-4..W-1 and unavailable in Weeks 1--4; and
- FP full-season shell: source season exactly target season minus one.

Each component carries its own maximum source period and evidence class. An
overall maximum alone cannot explain mixed sources.

### 9.3 Source identity and query consistency

Prefer an exact source bundle as the query input. If BigQuery is used directly:

- render one exact query with named parameters;
- bind a common `query_snapshot_at_utc` wherever source time travel is
  available;
- record the exact job metadata and every source table's observed metadata;
- immediately publish the exact consumed extracts and final rows; and
- treat a current table's modified time as observation evidence, not as an
  immutable object generation or historical lock time.

### 9.4 Versioning

The corrections change population and component semantics. They require new
versioned source/family identities and a new R6-v2 binding. Do not edit the
existing family-freeze receipts to appear correct, and do not silently rewrite
017r while retaining an old content/family identity.

## 10. Sequenced corrective actions

### Phase 0 — preserve and disposition current evidence

1. Preserve current SQL, annotation objects, smoke receipts, and family-freeze
   receipts as defect/replay evidence.
2. Mark current receiver/RB/QB freeze receipts non-authoritative for PIT/R6
   use in the new R6-v2 disposition; do not delete or rewrite them.
3. Register the exact evidence classes from Section 2.
4. Keep all outcome reads and promotion actions blocked.

Exit: no consumer can mistake current 017r or the task-0 family freezes for a
PIT-authoritative R6 source.

### Phase 1 — correct temporal and population semantics

1. Introduce the catalog-plus-schedule target spine for receiver, RB, QB, and
   defenses.
2. Add explicit source-period filters and retained component maxima.
3. Change FP shell joins to source season N-1 or make c4 unavailable.
4. Split FP receiver-shell and defense-shell source roles; consume or remove
   the falsely bound PFR role.
5. Correct SIS defender team/workload windows.
6. Freeze an explicit unknown-depth/QB gate, including 2025 behavior.
7. Reconcile labels with calculations: raw versus shrunk concession and
   weighted versus unweighted defender quality.
8. Version the family/source contracts.

Exit: deleting every target-week postgame row leaves the complete target
population and every feature value unchanged.

### Phase 2 — implement the two-object seam

1. Add the canonical export and receipt schemas.
2. Implement `capture_matchup_source_v1` with injected create-once publisher
   and exact reader.
3. Implement `reopen_matchup_source_snapshot` in the R6-v2 path.
4. Remove authoritative dependence on a caller-provided maximum-source time.
5. Bind one exact accepted v12 catalog and exact corrected component source
   export without importing any score/outcome module.
6. Publish to a bounded existing prefix with create-if-absent and immediately
   reopen both identities. Do not add IAM discovery or mutation to this path.

Exit: an offline independent verifier can reproduce the final player rows and
their evidence class from the three exact identities alone.

### Phase 3 — mechanics-only smoke, if needed before repairs complete

Current data may be used to exercise serialization, exact-read, candidate
coverage, missingness, and runner wiring only if every artifact and report
states:

```text
evidence_class = non-pit-retrospective
authoritative_for_mechanics = true
authoritative_pit = false
r6_v2_freeze_authority = false
outcome_verdict_authority = false
promotion_authority = false
```

It may not freeze R6-v2 books, choose an admission law, read actual scores, or
be cited as evidence that matchup admission works.

### Phase 4 — corrected real-artifact smoke and R6-v2 freeze

1. Run the corrected source capture against one accepted real v12 slate.
2. Require evidence class at least
   `retrospective-prior-period-reconstruction`.
3. Exact-read the v12 task/carrier, catalog, matchup export, and query receipt.
4. Prove complete skill-player denominator, stable percentile universe,
   missing-not-zero behavior, QB gate behavior, and exact lineup summaries.
5. Run all registered R6-v2 selector/admission/neutral-control mechanics
   without importing or reading an actual-score source.
6. Freeze R6-v2 only after every required book and trace is create-once and
   the protocol binds the retrospective evidence class.

Exit: the R6-v2 source and books are content-authoritative, outcome-blind, and
honestly labeled retrospective. This still grants no outcome verdict or
promotion authority; those require the separately governed realized grade and
the plan's later prospective promotion gates.

### Phase 5 — 2026 prospective capture

For each live slate, capture vendor/open-data source bytes and player/depth
universe before lock, publish exact source objects, retain observed/retrieved
times, and run the same export/receipt verifier. Only this path can produce
`contemporaneous-prelock` evidence.

## 11. Required acceptance tests for implementation

No tests were run for this documentation audit. The implementation must add
focused offline tests for:

1. target-season FP receiver or defense shell data is rejected;
2. source season N-1 succeeds and both source seasons are retained;
3. removing all target-week `weekly_stats` rows does not change target
   population, role, component, or percentile output;
4. target-week SIS/PFR row absence does not remove a scheduled defense row;
5. Weeks 1--4 carry missing FP alignment rather than fabricated zero;
6. 2025 unknown QB depth follows the frozen fail-closed law;
7. traded-defender old-team workload does not enter new-team exposure;
8. swapped FP/PFR source roles fail identity validation;
9. a false caller maximum timestamp cannot enter the API;
10. source export or receipt byte tampering fails;
11. export/receipt/catalog misbinding fails;
12. duplicate, missing, or extra catalog skill-player rows fail;
13. edge values outside `[0,1]` fail;
14. target-outcome field names or imports fail;
15. `017s` cannot be reached from the source capture command;
16. create-once publication collision fails without overwrite;
17. exact reopen reproduces canonical bytes and row/universe hashes; and
18. an evidence class below the caller's required minimum fails closed.

The real-artifact smoke must follow these tests and precede the R6-v2 freeze.
It must use the exact objects and schemas the panel fan-out will consume.

## 12. Likely implementation touchpoints

The correction is expected to touch, in one separately reviewed change:

- new versioned matchup source/export module under
  `src/nfl_dfs/research/`;
- `src/nfl_dfs/research/corpus_batch_retrieval_runner_v2.py` or its successor
  to replace raw-list authoritative construction with exact reopen;
- a new outcome-blind source-export script under `scripts/`;
- new versioned SQL or offline reducers replacing the current target spines;
- `receiver_matchup_annotations.py` and `rb_qb_matchup_annotations.py` only if
  they remain the canonical component builders;
- the receiver/RB/QB family definitions and their versioned receipts;
- focused source/export/runner tests; and
- the R6-v2 protocol, which must bind the exact evidence class and identities.

Do not use `scripts/build_receiver_matchup_features.py execute` as the R6-v2
source command because it includes 017s and its outcome consistency query.

## 13. Freeze gate

R6-v2 may freeze only when all of the following are true:

- current 017r is not represented as PIT authority;
- the corrected source uses the exact accepted catalog and schedule spine;
- same-target-season full-season FP use is absent;
- target-week participation does not define any target population;
- depth/QB unknown behavior is frozen and explicit;
- every component has exact source-period and evidence-class metadata;
- the two create-once objects exact-reopen and bind each other and the catalog;
- the source class is at least
  `retrospective-prior-period-reconstruction`;
- the complete outcome-blind real-artifact smoke passes; and
- no realized-score source has been accessed for R6-v2 before all required
  books and traces are frozen.

Meeting this gate licenses only the R6-v2 retrospective evaluation. It does
not establish that matchup admission is beneficial, does not change the
production selector, and does not authorize promotion. A result verdict and
any later adoption remain separate governed decisions.
