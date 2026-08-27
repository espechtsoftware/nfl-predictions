# Observatory workstream — Phase 5 capacity estimator and receipt contract (fifth correction)

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-27
**Branch:** `feature/neo4j-react-observatory` (parent `3f656dfd`, accepted Phase 4)
**Supersedes:** `283bd3de`, `66e4575a`, `a4dc08b1`, `f2d049b0`, `36c503d8`
(each rejected pending the next bounded correction).
**Scope executed:** Phase 5 corrective implementation ONLY — no mode
decision, no merge/rebase, no router mount, no React cutover, no
cloud/outcome access, no Neo4j connection/provisioning, no infrastructure
or deployment change, no active R6/T230/Core path touched.

## Fifth-correction repair

### P1 — explicit outcome closure sets are bound and exact-live checked

`graph_binding_now()` now embeds the contracts module's explicit
`OUTCOME_NODE_KINDS` and `OUTCOME_RELATIONSHIP_TYPES` — the sets the row
validators consult directly — alongside the namespace-derived closed
vocabulary, and `require_frozen_contract()` additionally requires the two
to agree. The review's reproduced attack (adding `Lineup` to the live
`OUTCOME_NODE_KINDS`, which made the row validator reject modeled `Lineup`
nodes while the old binding stayed byte-identical) now changes the
binding, fails every build, and fails replay of every earlier receipt;
removals and additions on both sets are regression-tested.

### P1 — the production loader contract is bound and enforced

The versioned loader contract (`BATCH_SIZE=500`,
`MAX_NODE_ROWS=100,000`, `MAX_EDGE_ROWS=200,000`,
`MAX_TOTAL_BATCHES=600` — the same limits the Phase 4
adapter enforces) is embedded in the binding and enforced in every
estimate: node rows, relationship rows, and total streamed batches beyond
the contract are named violations, and the batch size used for the
estimate is the contract's (asserted equal to the frozen law's). Under this
contract the synthetic fixture's full-lineup mode is honestly
**infeasible** (1,101,856 relationships > 200,000;
2,354 batches > 600) and summary-only is
forced; a shrunk packet that fits the contract is feasible in full mode
(tested). Claiming full-lineup load feasibility at the previous scale
would require versioning and validating a different loader contract.

### P2 — every remaining global limit is bound

The binding also embeds `MAX_SOURCE_RELEASES`, `MAX_SOURCE_IDENTITY_BYTES`,
`MAX_SOURCE_URI_BYTES`, `MAX_SOURCE_OBJECT_BYTES`, `MAX_PROPERTIES`,
`MAX_PROPERTY_KEY_BYTES`, `MAX_PROPERTY_STRING_BYTES`,
`MAX_PROPERTY_LIST_LENGTH`, `MAX_PROPERTY_LIST_ITEM_BYTES`,
`MAX_PROPERTY_LIST_BYTES`, `MAX_PROPERTY_BYTES`, `LOAD_MANIFEST_SCHEMA`
and `OFFLINE_METRIC_SCOPES`; drift in any of them fails build and replay
(parametrized regressions), and `mean_string_property_bytes` is bounded
by `MAX_PROPERTY_STRING_BYTES`. New pinned contract digest:
`c9f8e7ce1d83e4ba85ae58c2dc80af1046594654ce5c5272b2ac753c5d458674`.

## Retained from earlier corrections

Contract as sole use-time authority; live graph cross-binding (version,
complete vocabularies, namespace schemas, complete-property-rule version
`corpus-graph-vnext/v1+properties-547567d158f06448`); deep-frozen contract embedded and
re-hashed in every receipt; runtime-immutable estimation law
`5d20920d5c5e4a77…`; count-matched release manifests; endpoint
coherence per mode; honest authority labeling; R6 full-union identity +
panel self-hash; closed realized vocabulary; Phase 4 bundle/book
cardinalities with truthful parity; exact registered relationship counts;
selected-lineup coherence; normalized assertion digest; coherent bounded
fixture scale; full GCS bucket grammar; calendar-valid timestamps; bounded
identity bytes.

## Fixture illustration (synthetic — decision PENDING by construction)

| | full-lineup | summary-only |
|---|---|---|
| node kinds modeled | 29 | 29 |
| nodes | 74,909 | 19,229 |
| relationships | 1,101,856 | 155,296 |
| properties | 2,232,485 | 339,365 |
| estimated store | 414 MiB | 62 MiB |
| streamed batches (contract cap 600) | 2354 | 350 |
| est. load / rebuild (s) | 4708 / 4713 | 700 / 702 |
| feasible under fixture provisioning AND the v1 loader contract | False | True |
| full-corpus traversal | True | False |

Full-lineup violations: relationship_count exceeds the loader contract max_edge_rows (200000); batch_count exceeds the loader contract max_total_batches (600).

`decision.state = pending-lead-inputs`, `recommended_mode = None`,
`forced_mode = summary-only`, `approval.status = not-authenticated`.

## Required inputs the lead must supply (exact list, from `required_inputs_manifest()`)

| name | kind | needed by | description |
|---|---|---|---|
| `accepted_slate_count` | count | full-lineup, summary-only | [Slate] terminal accepted slates in the panel |
| `slate_snapshot_count` | count | full-lineup, summary-only | [SlateSnapshot] slate snapshots (source/pricing snapshots) bound to accepted slates |
| `contest_count` | count | full-lineup, summary-only | [Contest] registered contests bound to accepted slates |
| `game_count` | count | full-lineup, summary-only | [Game] games across accepted slates |
| `team_slate_count` | count | full-lineup, summary-only | [TeamSlate] team-slate rows across accepted slates |
| `player_slate_count` | count | full-lineup, summary-only | [PlayerSlate] player-slate rows across accepted slates |
| `world_release_count` | count | full-lineup, summary-only | [WorldRelease] world releases (identity pointers; matrices never load) |
| `corpus_snapshot_count` | count | full-lineup, summary-only | [CorpusSnapshot] corpus snapshots |
| `candidate_snapshot_count` | count | full-lineup, summary-only | [CandidateSnapshot] candidate (admitted) snapshots |
| `unique_lineup_count` | count | full-lineup | [Lineup] distinct roster_ids across the accepted corpus |
| `selected_unique_lineup_count` | count | summary-only | [Lineup] distinct lineups appearing in any selected book |
| `selected_book_count` | count | full-lineup, summary-only | [SelectedBook] exact selected books (bundle x slate x budget) |
| `science_release_count` | count | full-lineup, summary-only | [ScienceRelease] science releases |
| `verifier_release_count` | count | full-lineup, summary-only | [VerifierRelease] verifier releases |
| `deployment_attestation_count` | count | full-lineup, summary-only | [DeploymentAttestation] deployment attestations |
| `fill_preset_count` | count | full-lineup, summary-only | [FillPreset] registered fill presets |
| `admission_preset_count` | count | full-lineup, summary-only | [AdmissionPreset] registered admission presets |
| `retrieval_preset_count` | count | full-lineup, summary-only | [RetrievalPreset] registered retrieval presets |
| `strategy_bundle_count` | count | full-lineup, summary-only | [StrategyBundle] registered strategy bundles |
| `experiment_run_count` | count | full-lineup, summary-only | [ExperimentRun] experiment runs bound to the release |
| `experiment_cell_count` | count | full-lineup, summary-only | [ExperimentCell] experiment cells |
| `evaluation_count` | count | full-lineup, summary-only | [Evaluation] evaluations (books-frozen or later) |
| `fold_count` | count | full-lineup, summary-only | [Fold] fold definitions |
| `metric_set_count` | count | full-lineup, summary-only | [MetricSet] metric-set nodes |
| `trait_definition_count` | count | full-lineup, summary-only | [Trait] versioned trait definitions |
| `cohort_count` | count | full-lineup, summary-only | [Cohort] cohort definitions |
| `source_artifact_count` | count | full-lineup, summary-only | [SourceArtifact] source artifact identities |
| `verification_receipt_count` | count | full-lineup, summary-only | [VerificationReceipt] verification receipts |
| `attempt_count` | count | full-lineup, summary-only | [Attempt] attempt records |
| `promotion_decision_count` | count | full-lineup, summary-only | [PromotionDecision] promotion decisions |
| `lineup_occurrence_count` | count | full-lineup | [MEMBER_OF_CORPUS] corpus memberships incl. cross-arm duplicates |
| `lineup_arm_supply_count` | count | full-lineup | [SUPPLIED_BY_ARM] (lineup, source arm) supply pairs |
| `trait_membership_count` | count | full-lineup | [HAS_TRAIT] (lineup, trait) memberships, sparse |
| `cohort_membership_count` | count | full-lineup | [MEMBER_OF_COHORT] (lineup, cohort) memberships |
| `selected_lineup_occurrence_count` | count | summary-only | [MEMBER_OF_CORPUS] corpus memberships of selected lineups only |
| `selected_lineup_arm_supply_count` | count | summary-only | [SUPPLIED_BY_ARM] (selected lineup, source arm) supply pairs |
| `selected_trait_membership_count` | count | summary-only | [HAS_TRAIT] (selected lineup, trait) memberships |
| `selected_cohort_membership_count` | count | summary-only | [MEMBER_OF_COHORT] (selected lineup, cohort) memberships |
| `selected_book_membership_count` | count | full-lineup, summary-only | [MEMBER_OF_BOOK] (book, lineup) memberships across all books |
| `plays_for_edge_count` | count | full-lineup, summary-only | [PLAYS_FOR] PLAYS_FOR relationships (player-slate -> team-slate) |
| `in_game_edge_count` | count | full-lineup, summary-only | [IN_GAME] IN_GAME relationships (team-slate -> game) |
| `derived_from_edge_count` | count | full-lineup, summary-only | [DERIVED_FROM] DERIVED_FROM lineage relationships |
| `uses_source_edge_count` | count | full-lineup, summary-only | [USES_SOURCE] USES_SOURCE lineage relationships |
| `uses_world_release_edge_count` | count | full-lineup, summary-only | [USES_WORLD_RELEASE] USES_WORLD_RELEASE lineage relationships |
| `generated_by_edge_count` | count | full-lineup, summary-only | [GENERATED_BY] GENERATED_BY relationships (book -> bundle, ...) |
| `verified_by_edge_count` | count | full-lineup, summary-only | [VERIFIED_BY] VERIFIED_BY relationships |
| `retried_as_edge_count` | count | full-lineup, summary-only | [RETRIED_AS] RETRIED_AS relationships |
| `evaluated_in_edge_count` | count | full-lineup, summary-only | [EVALUATED_IN] EVALUATED_IN relationships |
| `evaluates_bundle_edge_count` | count | full-lineup, summary-only | [EVALUATES_BUNDLE] EVALUATES_BUNDLE relationships |
| `has_metric_edge_count` | count | full-lineup, summary-only | [HAS_METRIC] HAS_METRIC relationships |
| `paired_against_edge_count` | count | full-lineup, summary-only | [PAIRED_AGAINST] PAIRED_AGAINST relationships |
| `decides_on_bundle_edge_count` | count | full-lineup, summary-only | [DECIDES_ON_BUNDLE] DECIDES_ON_BUNDLE relationships |
| `inferred_defender_exposure_edge_count` | count | full-lineup, summary-only | [HAS_INFERRED_DEFENDER_EXPOSURE] HAS_INFERRED_DEFENDER_EXPOSURE relationships (qualified) |
| `mean_string_property_bytes` | count | full-lineup, summary-only | measured mean UTF-8 bytes of string properties in the release |
| `combined_panel_index_identity` | identity | full-lineup, summary-only | foundry-v12-combined-panel-index/v1 object identity |
| `r6_full_union_panel_freeze_identity` | identity | full-lineup, summary-only | accepted R6 full-union panel-freeze/release object identity (corpus-r6-full-union-freezes/<freeze>/panel-freeze.json; outcome-blind, complete=true; 54 slates / 2,592 books / 7,776 prefixes census) |
| `source_universe_release_identity` | identity | full-lineup, summary-only | artifact-supported source-universe release identity |
| `world_releases` | release_manifest | full-lineup, summary-only | [WorldRelease] list of {release_id, identity} whose length equals world_release_count |
| `science_releases` | release_manifest | full-lineup, summary-only | [ScienceRelease] list of {release_id, identity} whose length equals science_release_count |
| `verifier_releases` | release_manifest | full-lineup, summary-only | [VerifierRelease] list of {release_id, identity} whose length equals verifier_release_count |
| `deployment_attestations` | release_manifest | full-lineup, summary-only | [DeploymentAttestation] list of {release_id, identity} whose length equals deployment_attestation_count |
| `predecessor_graph_release_id` | version | full-lineup, summary-only | predecessor graph release id or null |
| `graph_schema_version` | version | full-lineup, summary-only | must equal corpus-graph-vnext/v1 |
| `property_schema_version` | version | full-lineup, summary-only | must equal the content hash of the complete positive property schema |
| `r6_full_union_panel_self_sha256` | hash | full-lineup, summary-only | panel self-hash recorded inside the accepted R6 full-union panel-freeze root |
| `provisioned_disk_bytes` | parameter | full-lineup, summary-only | disk available to the graph store |
| `provisioned_heap_bytes` | parameter | full-lineup, summary-only | JVM heap for the graph service |
| `provisioned_page_cache_bytes` | parameter | full-lineup, summary-only | page cache for the graph store |
| `load_deadline_seconds` | parameter | full-lineup, summary-only | zero-state streamed load deadline |
| `rebuild_deadline_seconds` | parameter | full-lineup, summary-only | zero-state rebuild deadline incl. indexes |

To reach `estimated-pending-approval`: `authority = lead-supplied-terminal`,
every identity a real non-synthetic `gs://bucket/object` with generation,
sha256, bytes; every release manifest count-matched; and
`inputs_assertion_sha256 = inputs_assertion_digest(packet)`. That state is
still NOT an approval: selecting a mode requires a detached immutable lead
approval receipt identity, which this offline phase does not accept.

## Closed in v1 (contribute nothing; no inputs accepted)

- node kinds: OutcomeGrade, OutcomeRelease, WinnerObservation, WinnerRelease
- relationship types: DERIVED_FROM_OUTCOME, GRADED_IN_CONTEST, OBSERVED_IN_WINNER_RELEASE

## Excluded from Neo4j in BOTH modes (from the contract)

- world score matrices
- per-world nodes or relationships
- dense pairwise player/lineup networks (quadratic)
- raw licensed Fantasy Points or SIS rows
- raw contest standings and contestant identifiers
- credentials or secrets
- mutable active-policy pointers
- realized namespace (closed in v1): winner and outcome node kinds and relationships

## Validation (serial; exact results in the branch HANDOFF)

- `pytest tests/test_corpus_graph_capacity.py` — adversarial suite incl.
  closure-set and limit drift, loader-contract ceilings, and every
  earlier law.
- `pytest tests/test_corpus_graph_vnext_contracts.py` — regression.
- `pytest tests/test_corpus_graph_vnext_fixture_adapter.py` — Phase 4
  regression.
- `git diff --check`.

## Stop point

Stopped for lead re-review. No mode was chosen; nothing approves anything.
