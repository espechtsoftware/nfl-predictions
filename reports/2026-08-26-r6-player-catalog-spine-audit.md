# R6 player-catalog spine audit

Date: 2026-08-26
Status: read-only implementation audit; no implementation or execution authority
Scope: corrected R6 source pipeline player-population authority only

## Audit boundary

This audit used only local, read-only repository evidence. It did not:

- read any realized outcome, actual score, contest result, rank, ROI, or other
  historical scoring source;
- query BigQuery or any other warehouse;
- access GCS or another cloud service;
- list any bucket or cloud resource;
- perform an IAM census or IAM operation;
- run tests, simulations, builds, deployments, or source operators; or
- edit any implementation file.

The untracked
`src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py` and its untracked
test were changing concurrently during the audit. They were not treated as
stable or authoritative evidence. Conclusions below are anchored to the
tracked source contract, accepted-v12 reconstruction, frozen local receipts,
and retained reports.

## Verdict

The accepted v12 chain already contains the authoritative player population
needed by R6 for all 54 slates. No new structural BigQuery query, matrix
regeneration, or 270-artifact reread is required to construct the R6 player
catalog.

The blocking mismatch is a schema problem. The corrected R6 source currently
reuses `corpus-retrieval-player-catalog/v1`, which requires `name` and `proj`,
although R6 intentionally treats those fields as non-scientific and does not
use them to define its player population or matchup calculations. The correct
repair is a new versioned R6 structural catalog whose player rows contain
exactly:

```text
{id, pos, team, opp, game_id, salary}
```

Names and projections must not be invented merely to satisfy the legacy
retrieval schema. If the UI or later descriptive reporting needs them, they
should live in a separate optional annotation object that cannot add, remove,
reorder, or redefine catalog players.

The fastest trustworthy implementation is one lightweight, outcome-blind
release operation that reopens the frozen G0 panel, accepted task envelopes,
the shared later-source freeze, and the shared artifact-source completion;
derives all 54 structural catalogs; and publishes one immutable catalog
release. It does not need to open the 6.6-GB world-matrix lattice because the
accepted source-authority completion already proved matrix player-set equality.

## 1. Exact frozen authority that already exists

### 1.1 Accepted 54-slate G0 root

The tracked authority lock is:

```text
local file:
  reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/
  g0-authority-lock-v1.json

schema:
  foundry-v12-g0-authority-lock/v2

internal G0 authority-lock SHA-256:
  d3efdb18755dc81b5a5c51964bd308ea346f2a239ad7a4279d62ce127d08dc5b

panel URI:
  gs://nfl-predictions-503414-corpus-parametric/research/
  corpus-parametric-research/panels/20260823-foundry-production-v12/
  foundry-v12-combined-panel-index-v1.json

panel generation:
  1787663639938214

panel object SHA-256:
  4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9

panel bytes:
  209279

panel-index SHA-256:
  479b65bb40fcab6ba6721431718c8e2e95fc0a28a4354f1e7b3b1e205c69b094

panel ID:
  v12:ef445e2b31a7756609b458753dc064318b58ea2912e9277071c08fd0d07392e0

accepted slates:
  54
```

The two exact lane acceptance identities retained by that lock are:

```text
v12a
  generation: 1787656756640443
  SHA-256: a0ed809dc6480c93c301e3022c4adcc173ef285b8673e76174cf81f43b5c4397
  bytes: 1316197

v12b
  generation: 1787663188263409
  SHA-256: 9823eaa9a51062a6a437af22d1f6a5e0444f080191dd7ab6aad37b46f32f1e53
  bytes: 1222287
```

`src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py:1445-1575`
already replays the fixed publication receipt, fixed panel URI and exact panel
bytes, both local lane receipts, both remote lane terminal envelopes, and the
combined panel. Lines 1714-1803 validate the self-hashed G0 lock and require
its local bytes to be tracked, clean, and equal to the current Git blob. The
catalog release should reuse that root replay instead of accepting an
arbitrary caller-supplied panel identity.

### 1.2 All-54 structural player catalog

The generation-pinned later-source freeze is:

```text
URI:
  gs://nfl-predictions-503414-corpus-source/research/source/
  20260821-corpus-artifact-source-authority-v3/source/later-source-freeze.json

generation:
  1787367678830738

object SHA-256:
  c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a

bytes:
  4566802

schema:
  lr8-later-period-source-freeze-v1
```

The exact body is not checked into the repository, but this exact object
identity is retained in the accepted v12 foundation and one-slate support
smoke receipts. Its 54 ordered slate rows each contain:

- `season`, `week`, and `slate_id`;
- one ID-sorted structural `catalog`;
- `catalog_sha256`;
- the canonical R0 incumbent population and hash; and
- five exact R0--R4 artifact identities and their set hash.

The source SQL in
`src/nfl_dfs/research/lr8_later_period_source.py:62-68` selected only:

```text
season, week, id, pos, team, opp, game_id, salary
```

It selected no name, projection, or realized outcome. The exact structural
normalizer is at lines 382-395, canonical payload construction at 398-406,
and per-slate ID ordering and hashing at 500-562. The freeze validator at
609-777 enforces the exact 54-slate order, structural row schema, ID ordering,
catalog hash, query identity, selected-column boundary, and all false outcome
and downstream authority fields.

The source query was preregistered at snapshot
`2026-08-21T23:53:22Z` against
`nfl-predictions-503414.nfl_predictions.slate_player_features`. The retained
registration in
`reports/corpus-parametric-runs/20260821-corpus-artifact-source-authority-v3/
governance-live/publication-plan-12ee7ce.json` binds:

```text
job ID:
  20260821-corpus-artifact-source-authority-v3-full-catalog

SQL SHA-256:
  6c0240866a98fe12f01b23926e70f6368a359cebab15cf2a6f036229d26d59df

parameters SHA-256:
  e100891b1d8840af3daf2c3f72c87b9ac5f738e18d1524177ce747e0745e1ecf

selected structural rows across the 54 slates:
  29605

realized columns selected:
  []
```

### 1.3 Independently accepted artifact-supported completion

The exact source-authority completion is:

```text
URI:
  gs://nfl-predictions-503414-corpus-source/research/source/
  20260821-corpus-artifact-source-authority-v3/source/
  artifact-source-authority-completion.json

generation:
  1787367915631771

object SHA-256:
  2d3a97e524fb0f592f0c57ed67643a84281fc97203e348f01031e3c356bded6c

bytes:
  383554
```

The source publication completion is generation `1787367916927834`, SHA-256
`c6d16f40c3b35e6bff736a0bb1926e1a1de973dbc323c7a910a2d36080fc7ada`,
and 87,476 bytes. The create-once terminal acceptance is generation
`1787369428935595`, SHA-256
`b481b807cd1cdb51f3d5bdb329aaa7a3045b908ce8076548ff97f01829bdc4fc`,
and 92,347 bytes. These identities are retained locally in
`reports/corpus-parametric-runs/20260821-corpus-artifact-source-authority-v3/
transport-live/terminal-accepted.json`.

`src/nfl_dfs/research/corpus_artifact_source_authority.py:742-1057`
independently reopened all 270 R0--R4 artifact bodies. Lines 799-840 align the
54 source tasks, 899-936 bind and validate each artifact body and require its
player IDs to equal the structural catalog, and 950-974 bind the per-task
catalog hash, player count, ordered-player-ID hash, artifact identities, and
`task_source_authority_sha256`.

Its truthful population scope is:

```text
exact-artifact-supported-r0-r4-player-universe
```

It explicitly does not claim an independently proven complete DraftKings
salary universe. This boundary is documented in
`reports/2026-08-21-corpus-artifact-supported-source-authority-v1.md:9-31`.
That distinction must remain on the R6 catalog and its release manifest.

### 1.4 Accepted-v12 task binding

Every accepted v12 task carrier retains:

- its source-task authority SHA;
- the later-source freeze exact identity and internal manifest SHA;
- the artifact-source completion exact identity and internal completion SHA;
- the exact five world artifact identities; and
- its accepted task/slate identity.

The carrier construction is visible at
`src/nfl_dfs/research/corpus_parametric_batch.py:1375-1405`.

The accepted reconstruction path exact-reads the panel, task acceptance,
carrier, later-source freeze, and five world objects at
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution.py:292-524`.
The v12 importer passes the freeze catalog directly through
`prepare_later_slate` at
`src/nfl_dfs/research/corpus_v12_import.py:991-1017`.

The corrected R6 executor then derives exactly
`{id,pos,team,opp,game_id,salary}` from the accepted prepared players at
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py:97-172`.
It exact-reads the matchup catalog, projects those same fields at lines
175-220, and rejects any population, ordering, context, or salary difference
at lines 319-359.

This establishes that the structural catalog is already part of the accepted
v12 science chain. The catalog publisher must expose that authority; it must
not create a new population authority.

## 2. Existing local artifacts and their limits

### 2.1 One full legacy retrieval catalog

Only one checked-in `corpus-retrieval-player-catalog/v1` object was found:

```text
slate:
  2023 Week 1 / task 0

local path:
  reports/corpus-retrieval-runs/20260821-corpus-retrieval-engine-v1/
  task0/live-bfe2e48/player-catalog.json

URI:
  gs://nfl-predictions-503414-corpus-retrieval/research/
  corpus-retrieval-inputs/20260821-corpus-retrieval-engine-v1/
  tasks/0000/player-catalog.json

generation:
  1787351685685892

object SHA-256:
  55c7f6efcbee49ad1b8c58b8be7a0446c564fc9796acb7137e637a178992264d

bytes:
  105469

rows:
  773
```

Its exact SQL is retained at
`reports/corpus-retrieval-runs/20260821-corpus-retrieval-engine-v1/
governance/player-catalog.sql`. It queried
`nfl_forensic_review.final_forensic_20260814_player_corpus_repair4` at
`2026-08-21T17:42:00Z` and selected all eight legacy catalog fields, including
`name` and `mean_projection AS proj`. It did not select an actual outcome.

This is a different table and snapshot from the later-source structural query.
No retained proof currently requires its structural projection to equal the
accepted later-source catalog. It therefore cannot serve as the R6 population
authority without a new exact equality check. If equality passes, its
`name`/`proj` values may be used only as optional task-0 annotations.

No equivalent checked-in full catalog/query receipt exists for the remaining
53 accepted slates.

### 2.2 Older 54-slate projection catalog

The exact local source lock is:

```text
local path:
  reports/production-law-dependence-runs/
  20260817-production-law-dependence-source-lock-v1/source-lock.json

URI:
  gs://nfl-predictions-503414-raw/research/
  production-law-dependence-runs/
  20260817-production-law-dependence-source-lock-v1/source-lock.json

generation:
  1786950155692968

object SHA-256:
  7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c

bytes:
  1341911

catalog rows:
  10729
```

Its rows contain only
`{season,week,player_id,position,team,mean_projection}`. The source-population
amendment at
`reports/2026-08-17-production-law-dependence-source-population-amendment.md:
21-53` defines this as the union of players used by native candidates, not the
broader 29,605-row acquisition catalog. The later-source implementation also
states at `src/nfl_dfs/research/lr8_later_period_source.py:8-11` that the old
catalog must not be silently upgraded and that a fresh exact structural
catalog is mandatory.

Consequently, the old source lock may provide an optional projection
annotation for its supported subset. It cannot define the R6 denominator and
must never cause an accepted structural row to be added or removed.

Its exact candidate-union counts by week are:

```text
2023: 250,206,212,215,177,182,188,214,180,183,186,176,194,201,193,172,238,228
2024: 235,218,215,209,175,181,210,231,210,195,203,163,181,177,214,189,147,225
2025: 230,194,206,187,161,181,187,192,201,181,213,199,187,209,226,206,160,236
```

These counts are useful for proving that the object is a subset, not for
constructing the complete accepted structural catalog.

## 3. `name` and `proj` schema mismatch

`src/nfl_dfs/research/corpus_r6_matchup_source_v1.py:36` currently declares:

```text
PLAYER_CATALOG_SCHEMA = "corpus-retrieval-player-catalog/v1"
```

Its `_normalize_catalog` implementation at lines 1032-1104 requires every
player row to have exact keys:

```text
id, name, pos, team, opp, game_id, salary, proj
```

But it validates and consumes only:

- `id`;
- `pos`;
- `team`;
- `opp`; and
- `game_id`.

It does not validate `name`, `salary`, or `proj` values or types. The one-slate
executor later catches structural salary differences, but the standalone
source contract can accept malformed unused values. It also only normalizes
the catalog's `source_authority` as an object identity; it does not reopen that
authority or prove its relationship to accepted v12.

By comparison, the original retrieval catalog validator at
`src/nfl_dfs/research/corpus_retrieval_engine.py:498-560` validates nonempty
names, exact nonnegative integer salary, and finite numeric projection and
canonically rebuilds the complete object.

The corrected executor intentionally treats name and projection as
non-scientific. The regression test at
`tests/test_corpus_r6_v2_one_slate_execution_v2.py:1153-1172` changes every
name and adds 99 points to every projection while requiring the structural
catalog hashes and R6 result to remain unchanged.

Therefore the eight-field retrieval schema is the wrong R6 source contract.
There are three possible treatments, only one of which should be adopted:

1. **Recommended:** introduce a six-field accepted structural catalog schema.
2. Optional: publish a separate display annotation object keyed to the exact
   structural catalog identity.
3. Rejected: populate `name=id`, a zero projection, or a world-derived mean in
   the legacy schema and imply those values were the accepted source fields.

World-matrix means could technically be derived outcome-blind, but doing so
would require reopening and reducing the full matrix lattice, would introduce
a new floating-point derivation contract, and would still not produce player
names. It provides no R6 scientific value and would restore the deployment
bottleneck this work is meant to remove.

## 4. Implementation-ready authority design

### 4.1 Structural catalog schema

Introduce `corpus-r6-accepted-player-catalog/v1`:

```json
{
  "schema_version": "corpus-r6-accepted-player-catalog/v1",
  "task_id": "slate-2023-w1",
  "slate": {
    "season": 2023,
    "week": 1,
    "slate_id": "2023-w01"
  },
  "task_ordinal": 0,
  "source_task_ordinal": 0,
  "universe_scope": "exact-artifact-supported-r0-r4-player-universe",
  "source_authority": {
    "uri": "gs://.../catalog-derivation-receipt.json",
    "generation": "...",
    "sha256": "...",
    "bytes": 123
  },
  "players": [
    {
      "id": "00-0000000",
      "pos": "WR",
      "team": "AAA",
      "opp": "BBB",
      "game_id": "AAA|BBB",
      "salary": 5000
    }
  ],
  "player_count": 773,
  "ordered_player_ids_sha256": "...",
  "source_catalog_sha256": "...",
  "outcome_columns_read": [],
  "uses_realized_outcomes": false,
  "fill_authority": false,
  "retrieval_authority": false,
  "historical_scoring_authority": false,
  "promotion_authority": false,
  "production_policy_authority": false,
  "player_catalog_sha256": "..."
}
```

Catalog invariants:

- exact top-level and player-row keys;
- `source_task_ordinal` in `0..53`;
- exact slate mapping and task ID;
- nonempty strings for all five structural string fields;
- supported position in `QB,RB,WR,TE,DST`;
- exact nonnegative integer salary;
- IDs strictly ascending and unique;
- `player_count == len(players)`;
- ordered-ID and structural projection hashes replay exactly;
- `source_catalog_sha256` equals the corresponding later-source row;
- canonical JSON and a non-conflated internal self-hash; and
- all outcome and downstream authority fields false.

### 4.2 Per-slate derivation receipt

Introduce `corpus-r6-player-catalog-derivation/v1`. Each receipt should bind:

```text
G0 root
  tracked G0 authority-lock internal SHA
  G0 lock file/Git binding or immutable release-code equivalent
  exact panel object identity
  panel-index SHA

accepted task
  accepted-slate membership and membership SHA
  lane ordinal and task ordinal
  source task ordinal
  task acceptance identity
  task carrier identity

accepted source
  later-source freeze identity
  later-source internal freeze SHA
  artifact-source completion identity
  artifact-source internal completion SHA
  completion task_source_authority_sha256
  source catalog SHA
  source catalog player count
  ordered source catalog player-ID SHA

derivation
  code identity
  algorithm ID: accepted-v12-structural-catalog-projection-v1
  exact field list
  order law: ascending-player-id
  derived structural projection SHA

boundary
  outcome_columns_read=[]
  uses_realized_outcomes=false
  all downstream authorities=false
```

The receipt should bind the structural projection SHA, not the eventual
catalog object identity. That breaks the otherwise circular dependency:

1. derive and publish the receipt;
2. build the catalog containing the receipt's exact identity; and
3. publish a release manifest containing both exact object identities.

### 4.3 All-54 release manifest

Introduce `corpus-r6-player-catalog-release/v1` with:

- the exact G0 root and panel identity;
- the exact later-source and artifact-completion identities;
- `task_count=54`;
- one ordered entry for every source ordinal `0..53`;
- each task/slate identity;
- catalog and derivation-receipt object identities;
- catalog structural SHA, count, and ordered-ID hash;
- an exact entry-manifest SHA;
- create-once/idempotent publication semantics;
- no outcome or downstream authority; and
- a canonical release self-hash.

The corrected matchup-source capture plan must pin this exact release-manifest
identity. Merely accepting a catalog identity and verifying its internal
coherence is not enough: a caller could publish a coherently rehashed alternate
receipt, catalog, and manifest. A separately frozen capture plan that names the
one accepted release identity prevents that substitution.

### 4.4 Deterministic builder algorithm

The builder must not accept caller-supplied player rows. Its science-relevant
inputs are only the frozen root and a requested source-task ordinal.

Recommended all-54 flow:

1. Replay the tracked G0 authority lock and fixed published panel once using
   the existing panel replay.
2. Require exactly 54 accepted memberships and source-task ordinals exactly
   `0..53`, with no duplicate, omitted, or reordered source slate.
3. Exact-read every task acceptance and carrier, but do not open the world NPZ
   bodies.
4. Require each acceptance and carrier identity to equal its panel membership.
5. Require the carrier's task/slate/order and source-task-authority SHA to equal
   the accepted membership.
6. Require all carriers to bind one identical later-source identity and one
   identical artifact-source completion identity/internal SHA.
7. Exact-read and validate those two shared JSON objects once.
8. For each source ordinal, align the panel membership, carrier, completion
   task, and later-source slate.
9. Require exact equality of season, week, slate ID, source-task-authority SHA,
   catalog SHA, catalog count, and ordered-player-ID hash.
10. Validate and project the later-source row to the exact six structural
    fields in ascending ID order.
11. Build and create-once publish the derivation receipt.
12. Build and create-once publish the catalog containing that receipt identity.
13. Publish all 54 exact pairs in one create-once release manifest.
14. Exact-reopen the release, every receipt, and every catalog and replay all
    hashes and root bindings before accepting the release.

The previously accepted source completion already performed the expensive
270-body proof. Reopening the world lattice here would repeat established work
without adding catalog authority.

### 4.5 Functions and files

Add a separate module rather than silently changing the retrieval catalog:

```text
src/nfl_dfs/research/corpus_r6_player_catalog_v1.py
```

Recommended pure functions:

```python
def derive_catalog_authority_receipt_v1(...) -> dict[str, object]: ...

def validate_catalog_authority_receipt_v1(
    value: object,
    *,
    expected_root: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]: ...

def build_r6_player_catalog_v1(
    *,
    authority_receipt_identity: Mapping[str, object],
    structural_players: Sequence[Mapping[str, object]],
) -> dict[str, object]: ...

def validate_r6_player_catalog_v1(value: object) -> dict[str, object]: ...

def build_r6_player_catalog_release_v1(...) -> dict[str, object]: ...

def reopen_r6_player_catalog_from_release_v1(
    *,
    expected_release_identity: Mapping[str, object],
    task_id: str,
    read_exact: ReadExact,
) -> dict[str, object]: ...
```

The transport/operator should be a separate thin create-once publisher. Source
capture must call `reopen_r6_player_catalog_from_release_v1`; it must not accept
an arbitrary catalog as its population root.

Update the successor of `corpus_r6_matchup_source_v1.py` to accept the new
structural schema and exact-reopen its derivation authority. Do not mutate the
meaning of the already-named retrieval schema. Update the corrected one-slate
executor to require both structural equality and the expected catalog-release
root.

If display data is desired, introduce a separate optional schema such as
`corpus-r6-player-display-annotations/v1` with catalog identity, annotation
source identities, coverage diagnostics, and explicit false population and
science authority.

## 5. Exact per-slate gap disposition

The canonical source order is season-major, then Week 1 through Week 18:

```text
source ordinals  0-17: 2023 Weeks 1-18
source ordinals 18-35: 2024 Weeks 1-18
source ordinals 36-53: 2025 Weeks 1-18
```

| Slates | Source ordinals | Accepted structural catalog | Legacy full `name`/`proj` object | Remaining corrected-source inputs |
|---|---:|---|---|---|
| 2023 W1 | 0 | Frozen in later-source and artifact completion | Separate 773-row auxiliary object; structural equality not yet bound | Catalog derivation/release, schedule/lock, depth, corrected component extracts |
| 2023 W2-W4 | 1-3 | Frozen | None | Same; FP alignment must be explicit missingness |
| 2023 W5-W18 | 4-17 | Frozen | None | Catalog release, schedule/lock, evidenced depth, corrected component extracts |
| 2024 W1-W4 | 18-21 | Frozen | None | Same; FP alignment must be explicit missingness |
| 2024 W5-W18 | 22-35 | Frozen | None | Catalog release, schedule/lock, evidenced depth, corrected component extracts |
| 2025 W1-W4 | 36-39 | Frozen | None | Same; FP alignment missing and QB depth unknown/fail-closed |
| 2025 W5-W18 | 40-53 | Frozen | None | Catalog release, schedule/lock, corrected component extracts, QB depth unknown/fail-closed |

The exact gap summary is therefore:

- Structural population query: no gap for any of the 54 slates.
- Exact structural catalog bytes: frozen remotely for every slate, but not
  checked into the repository as a standalone per-slate object.
- R6 catalog object: missing for all 54 slates.
- R6 derivation receipt: missing for all 54 slates.
- All-54 R6 catalog release manifest: missing.
- Accepted structural names: absent for all 54 slates.
- Full legacy name/projection catalog: task 0 has one separate auxiliary
  object; the other 53 have none.
- Canonical accepted reconstruction receipt object: not published per slate;
  reconstruction currently exists in memory. The new lightweight receipt
  should bind the accepted envelope without rereading matrices.
- Catalog schedule/lock spine: missing as a frozen corrected-source input for
  all 54 slates. `team`, `opp`, and `game_id` are present, but kickoff and lock
  evidence are not.
- Corrected component extracts/query receipts: missing for all 54 slates.
- FP alignment: required missingness for Weeks 1-4 in each season, exactly
  source ordinals `0-3`, `18-21`, and `36-39`.
- FP prior-season shell: 2023 must use 2022, 2024 must use 2023, and 2025 must
  use 2024; same-target-season full-season files are forbidden.
- Historical QB-depth evidence: 2025 remains unknown and must follow the
  frozen fail-closed law.

The schedule/depth/component requirements and evidence-class boundary are
specified in
`reports/2026-08-24-r6-v2-matchup-pit-lineage-disposition.md:818-866`.

## 6. Required tests before a real catalog release

### 6.1 Structural schema and derivation

1. Exact 54-task coverage succeeds with source ordinals exactly `0..53`.
2. Missing, duplicate, swapped, or reordered task/source ordinals fail.
3. Player addition fails.
4. Player removal fails.
5. Player reordering fails.
6. ID, position, team, opponent, game, or salary mutation fails.
7. Empty strings, unsupported positions, boolean salaries, negative salaries,
   and duplicate IDs fail.
8. `name` or `proj` in a structural row fails the exact-key law.
9. Catalog count, ordered-ID hash, structural hash, or self-hash drift fails.
10. Object SHA and internal self-hash conflation fails.

### 6.2 Transitive source authority

11. Panel membership/task acceptance/carrier misbinding fails.
12. Task ordinal or source-task ordinal substitution fails.
13. Carrier source-task-authority SHA differing from membership fails.
14. Completion task SHA differing from carrier or membership fails.
15. Completion catalog SHA/count/ID hash differing from later-source fails.
16. A different later-source identity fails even when its contents are
    internally coherent.
17. A different artifact-source completion fails even when coherently rehashed.
18. A coherently substituted alternate same-slate panel chain fails against
    the tracked G0 root.
19. A naked catalog `source_authority` identity that is not exact-reopened
    fails.
20. A derivation authority receipt rooted in caller assertions rather than the
    frozen G0 panel fails.

### 6.3 Release and capture binding

21. The release requires exactly 54 unique ordered entries.
22. Every manifest catalog/receipt identity exact-reopens and replays.
23. Catalog and receipt create-once collisions fail without overwrite.
24. A coherent alternate receipt/catalog/release is rejected when the capture
    plan pins the original release identity.
25. A catalog from the right slate but wrong accepted task fails.
26. Source capture cannot bypass the release root with an arbitrary catalog
    identity.

### 6.4 Optional annotations and source rules

27. The 2023 W1 legacy catalog may annotate only after exact structural
    equality; a missing, extra, or changed structural row fails annotation
    admission but does not change the accepted catalog.
28. The old 10,729-row projection catalog cannot add or remove structural
    players.
29. Missing optional annotations remain missing; they do not become zero or a
    fabricated name.
30. Target-week source-row deletion cannot change the accepted target
    population.
31. Weeks 1-4 carry explicit missing FP alignment, never fabricated zero.
32. 2025 unknown QB depth follows the frozen fail-closed law.

### 6.5 Outcome and authority boundary

33. Every catalog, receipt, release, and capture object requires
    `outcome_columns_read=[]` and `uses_realized_outcomes=false`.
34. Actual-score, contest-rank, ROI, outcome-bearing source names, and forbidden
    imports fail.
35. Fill, retrieval, historical-scoring, graph, promotion, production-change,
    and live-strategy authorities remain false.
36. The catalog release command has no outcome reader, outcome lease, scoring
    callback, or promotion path.

After offline tests, one real outcome-blind task-0 catalog derivation/reopen
smoke should precede the 54-slate release. That smoke should read only the exact
frozen authority chain described above. It should not reopen matrices or any
realized-score source.

## 7. Implementation order

1. Land and independently review the structural schema and pure validators.
2. Add the lightweight accepted-task envelope resolver that does not open NPZs.
3. Add derivation receipt and all-54 release builders.
4. Add the transitive exact-reopen validator rooted in the tracked G0 lock.
5. Add the focused offline poison tests above.
6. Run one outcome-blind task-0 catalog smoke.
7. Publish/reopen the 54 catalog/receipt pairs and release manifest in one
   create-once operation.
8. Freeze the exact release identity into the corrected matchup-source capture
   plan.
9. Build corrected schedule/depth/component source extracts independently of
   player-population construction.
10. Run the corrected outcome-blind R6 source smoke only after the catalog and
    source identities are both frozen.

This sequence makes the accepted catalog available quickly while preserving a
strict separation between player-population authority, matchup annotations,
historical scoring, and any later strategy decision.
