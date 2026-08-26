# Observatory workstream — Phase 5 capacity estimator and receipt contract (second correction)

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-26
**Branch:** `feature/neo4j-react-observatory` (parent `3f656dfd`, accepted Phase 4)
**Supersedes:** rejected `283bd3de` and rejected-on-re-review `66e4575a`.
**Scope executed:** Phase 5 corrective implementation ONLY — no mode
decision, no merge/rebase, no router mount, no React cutover, no
cloud/outcome access, no Neo4j connection/provisioning, no infrastructure
or deployment change, no active R6/T230/Core path touched.

## Second-correction P1s (this commit)

1. **Runtime-immutable, live-verified law.** `ESTIMATION_LAW` is a
   `MappingProxyType` (item assignment raises `TypeError`), and the frozen
   literal digest `5d20920d5c5e4a779230a966f29322c46e21a05a5c442422f0f9ad3884dc5fdc` is re-derived from the LIVE
   law object at import and at every build/validate (`law_digest_now()`,
   `require_frozen_law()`). A substituted law object cannot emit a receipt;
   an existing receipt fails validation under a substituted law; and a
   receipt whose embedded law body was altered while keeping the frozen
   digest string is rejected because the validator re-hashes the embedded
   body. All three are regression-tested.
2. **Release/attestation counts bound to count-matched immutable
   identities.** `release_manifests` supplies `world_releases`,
   `science_releases`, `verifier_releases`, `deployment_attestations` as
   lists of `{release_id, identity}`; each list length MUST equal its
   count input, entries may not repeat an id or object identity, and each
   identity is validated under the packet's authority class. The old
   singleton `*_release_id` versions and `world_release_identity` are
   removed.
3. **Endpoint coherence.** `RELATIONSHIP_ENDPOINTS` registers required
   source/target kinds for every open relationship type; a positive
   relationship count with an empty required endpoint population fails
   closed, per mode (summary-only evaluates against selected-lineup
   populations). The Phase 4 parity test checks every adapter edge's
   (source kind, target kind) against this schema.
4. **Honest authority labeling.** `lead_confirmation_for()` is gone.
   `inputs_assertion_digest()` / `inputs_assertion_sha256` bind content
   only and are documented as authenticating nobody. Decision states are
   `pending-lead-inputs` or `estimated-pending-approval` (never
   "decidable"); every decision carries
   `approval.status = "not-authenticated"` with a null
   `receipt_identity`; the reserved `lead_approval_receipt_identity` slot
   is rejected if non-null in this offline phase.

P2 cleanup: Phase 4 parity is described truthfully (the synthetic fixture
carries one `CONTAINS_PLAYER` per lineup and the test asserts exactly
that; nine per lineup is the separate production Phase 5 law);
`MEMBER_OF_BOOK` is a supplied count, not derived (derived set is
`ADMITTED_BY, CONTAINS_PLAYER, SELECTED_BY`); unknown direct modes are
rejected; identities require a real `gs://bucket/object` (bucket-name
grammar, non-empty object, no trailing slash or empty segment); timestamps
must be calendar-valid; identity byte counts are bounded to
268,435,456.

## Retained from the first correction

R6 full-union panel-freeze identity + panel self-hash inputs; closed
realized vocabulary derived from the contracts (OutcomeGrade, OutcomeRelease, WinnerObservation, WinnerRelease;
DERIVED_FROM_OUTCOME, GRADED_IN_CONTEST, OBSERVED_IN_WINNER_RELEASE); Phase 4 bundle/book
cardinalities; exact registered relationship counts; the seven previously
omitted node kinds; complete PropertyRule-content hashing
(`corpus-graph-vnext/v1+properties-547567d158f06448`); selected-lineup coherence.

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
| `selected_unique_lineup_count` | count | full-lineup, summary-only | [Lineup] distinct lineups appearing in any selected book |
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

## Excluded from Neo4j in BOTH modes

- world score matrices
- per-world nodes or relationships
- dense pairwise player/lineup networks (quadratic)
- raw licensed Fantasy Points or SIS rows
- raw contest standings and contestant identifiers
- credentials or secrets
- mutable active-policy pointers
- realized namespace (closed in v1): winner and outcome node kinds and relationships

## Validation (serial; exact results in the branch HANDOFF)

- `pytest tests/test_corpus_graph_capacity.py` — adversarial: runtime law
  immutability and substitution (emit, validate, altered-embedded-body);
  count-matched release manifests (short, long, duplicate, malformed,
  missing); endpoint coherence per relationship and per mode; Phase 4
  parity stated truthfully with endpoint-pair checks; honest authority
  labeling (assertion is not approval; reserved approval slot rejected);
  real-bucket/object URIs, calendar-valid timestamps, bounded identity
  bytes; unknown modes; all earlier coherence, forcing, ceiling,
  arithmetic-replay, tamper/forge, and manifest-coverage laws.
- `pytest tests/test_corpus_graph_vnext_contracts.py` — regression.
- `pytest tests/test_corpus_graph_vnext_fixture_adapter.py` — Phase 4
  regression.
- `git diff --check`.

## Stop point

Stopped for lead re-review. No mode was chosen; nothing approves anything.
