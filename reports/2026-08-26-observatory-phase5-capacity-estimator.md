# Observatory workstream — Phase 5 capacity estimator and receipt contract (fourth correction)

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-27
**Branch:** `feature/neo4j-react-observatory` (parent `3f656dfd`, accepted Phase 4)
**Supersedes:** `283bd3de`, `66e4575a`, `a4dc08b1`, `f2d049b0` (each rejected
pending the next bounded correction).
**Scope executed:** Phase 5 corrective implementation ONLY — no mode
decision, no merge/rebase, no router mount, no React cutover, no
cloud/outcome access, no Neo4j connection/provisioning, no infrastructure
or deployment change, no active R6/T230/Core path touched.

## Fourth-correction repair

### P1 — the semantic contract is the sole use-time authority

The re-review showed cached module registries (`REQUIRED_IDENTITIES`,
`REQUIRED_HASHES`, `MODES`, closed vocabulary, the out-of-contract
exclusion list) could be rebound to relax validation or contradict the
embedded contract. Now every use-time read goes through
`require_frozen_contract()`: `_normalize_packet()` derives every required
count, identity, release-manifest, version, hash and parameter name from
the contract; the receipt's modes, closed vocabulary and exclusion list
are taken from the contract (the exclusion list moved INTO the contract);
`required_inputs_manifest()` is generated from the contract. The
`REQUIRED_*` tuples and other module-level names remain as read-only
views only. Regressions rebind those cached names and prove validation
still rejects stripped identities/hashes/counts, and that receipts and
the manifest are byte-identical to the genuine ones.

### P1 — cross-binding to the live graph contract

`graph_binding_now()` recomputes, from the live `corpus_graph_vnext_contracts`
module at every call: graph schema version (`corpus-graph-vnext/v1`),
complete-property-rule version (`corpus-graph-vnext/v1+properties-547567d158f06448`),
allowed/offline/closed namespaces, the complete node and relationship
vocabularies (33 kinds / 25 types), the
closed/open splits, forbidden and qualified-inferred relationship laws, and
both namespace schemas. The contract embeds this binding, so the pinned
digest `18a0ddb1cb97fa674ed3cd7ce8a2491d16e373d9e49ef172a39b266916183bee` covers it, and
`require_frozen_contract()` additionally requires exact equality between
the embedded binding and the live module at every build and validation.
Regressions reproduce the review's attacks — adding `UNBOUND_NEW_EDGE` to
the live relationship vocabulary, changing the live graph schema to v2 —
and prove neither can emit a receipt nor replay an existing one; further
cases cover node-kind additions, namespace-schema edits, opening the
realized namespace, dropping the forbidden/qualified laws, and a
property-rule size change.

### P2s

- `inputs_assertion_digest()` now hashes the packet exactly as validation
  normalizes it (release manifests sorted by release id, canonical key
  order), so manifest entry order never changes the digest and validation
  agrees (tested with a two-entry manifest in both orders).
- `fixture_capacity_inputs(scale)` scales only corpus counts; the
  selected/book lattice is fixed (54×12×3) so every supported scale
  validates coherently; scales outside `[1, 1000]` and
  booleans are rejected.
- `_valid_gcs_bucket()` accepts legal dotted names up to 222 chars with
  each component ≤ 63, rejects `goog` prefixes and `google` including
  digit-for-letter misspellings such as `g00gle`/`g0ogle`/`go0g1e`,
  IP-literal names, adjacent separators, and out-of-range lengths.

## Retained from earlier corrections

Deep-frozen `SEMANTIC_CONTRACT` with pinned live-rederived digest embedded
and re-hashed in every receipt; runtime-immutable estimation law
`5d20920d5c5e4a77…`; count-matched release manifests; endpoint
coherence per mode; honest authority labeling (`pending-lead-inputs` /
`estimated-pending-approval`, `approval.status = not-authenticated`);
R6 full-union identity + panel self-hash; closed realized vocabulary
(OutcomeGrade, OutcomeRelease, WinnerObservation, WinnerRelease; DERIVED_FROM_OUTCOME, GRADED_IN_CONTEST, OBSERVED_IN_WINNER_RELEASE);
Phase 4 bundle/book cardinalities with truthful parity; exact registered
relationship counts; selected-lineup coherence; calendar-valid timestamps;
bounded identity bytes.

## Fixture illustration (synthetic — decision PENDING by construction)

| | full-lineup | summary-only |
|---|---|---|
| node kinds modeled | 29 | 29 |
| nodes | 74,909 | 19,229 |
| relationships | 1,101,856 | 155,296 |
| properties | 2,232,485 | 339,365 |
| estimated store | 414 MiB | 62 MiB |
| streamed batches | 2354 | 350 |
| est. load / rebuild (s) | 4708 / 4713 | 700 / 702 |
| feasible under fixture provisioning | True | True |
| full-corpus traversal | True | False |

`decision.state = pending-lead-inputs`, `recommended_mode = None`,
`forced_mode = None`, `approval.status = not-authenticated`.

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
  sole-authority and live-graph cross-binding regressions and every
  earlier law.
- `pytest tests/test_corpus_graph_vnext_contracts.py` — regression.
- `pytest tests/test_corpus_graph_vnext_fixture_adapter.py` — Phase 4
  regression.
- `git diff --check`.

## Stop point

Stopped for lead re-review. No mode was chosen; nothing approves anything.
