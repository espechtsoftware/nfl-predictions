# Observatory workstream — Phase 5 capacity estimator and receipt contract (corrected)

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-26
**Branch:** `feature/neo4j-react-observatory` (parent `3f656dfd`, accepted Phase 4)
**Supersedes:** the rejected first Phase 5 commit `283bd3de`; this report
describes the corrective commit that answers every P1 in the lead's review.
**Scope executed:** Phase 5 corrective implementation ONLY — no mode
decision, no merge/rebase, no router mount, no React cutover, no
cloud/outcome access, no Neo4j connection/provisioning, no infrastructure
or deployment change, no active R6/T230/Core path touched.

## Corrections landed (mapped to the review)

1. **R6 full-union identity replaces the standalone T230 input.** The
   required identity is now `r6_full_union_panel_freeze_identity` — the
   accepted `corpus-r6-full-union-freezes/<freeze>/panel-freeze.json`
   object identity (outcome-blind, `complete=true`, 54 / 2,592 / 7,776
   census) — plus the hash input `r6_full_union_panel_self_sha256` binding
   the panel self-hash recorded inside that root. `t230_panel_release_identity`
   is rejected as an unregistered identity.
2. **Winner/outcome vocabulary stays out of the closed v1 realized
   namespace.** Closed kinds and relationship types are DERIVED from the
   contracts module (`ALLOWED − OFFLINE_ALLOWED` namespaces):
   `OutcomeGrade, OutcomeRelease, WinnerObservation, WinnerRelease` and
   `DERIVED_FROM_OUTCOME, GRADED_IN_CONTEST, OBSERVED_IN_WINNER_RELEASE`. They contribute no
   elements, carry no count inputs (`winner_*` counts are rejected as
   unregistered), and are listed in the receipt's `closed_vocabulary`.
3. **Phase 4 endpoint cardinalities.** `ADMITTED_BY` = one per
   StrategyBundle; `SELECTED_BY` = one per StrategyBundle + one per
   SelectedBook; `MEMBER_OF_BOOK` = one per book membership;
   `CONTAINS_PLAYER` = nine per loaded lineup. A parity test censuses the
   Phase 4 fixture adapter's own projected rows and asserts these laws hold
   there before asserting the estimator applies them.
4. **`LINEAGE_COMBINED` removed.** Every open registered relationship type
   is either derived (the four above) or an exact supplied count; a test
   proves `exact ∪ derived == RELATIONSHIP_TYPES − closed` and that no
   unregistered type can appear.
5. **Omitted node kinds added:** SlateSnapshot, WorldRelease,
   CorpusSnapshot, CandidateSnapshot, ScienceRelease, VerifierRelease,
   DeploymentAttestation. A test proves the counted kinds equal
   `NODE_KINDS − closed` (29 kinds).
6. **Lead confirmation binds its canonical subject.**
   `lead_confirmation_sha256 == sha256(canonical {"subject":
   "foundry-graph-capacity-inputs/v1#lead-confirmation", "inputs_sha256": <digest of the
   packet body>})`; any other well-formed hash, or a confirmation over
   different counts, is rejected. Fixture-authority packets may not carry
   one.
7. **Literal law digest frozen:** `ESTIMATION_LAW_SHA256 =
   5d20920d5c5e4a779230a966f29322c46e21a05a5c442422f0f9ad3884dc5fdc`; the module refuses to import if the law's
   content drifts from it.
8. **Complete PropertyRule content hashed.** `property_schema_version()`
   now hashes value type, max string bytes, max list items, allowed
   strings, and both namespace schemas — a size-only rule change changes
   the version (tested). Current value:
   `corpus-graph-vnext/v1+properties-547567d158f06448`.
9. **Selected-lineup coherence completed:** selected ≤ full for every
   selected/full pair; selected occurrences and arm supplies ≥ selected
   unique lineups; books and book memberships jointly zero or positive;
   memberships ≥ books ≥ 0; books imply selected lineups and a bundle;
   `GENERATED_BY` ≥ books; full arm supply ≥ unique lineups.

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

`decision.state = pending-lead-inputs`, `recommended_mode = None`, `forced_mode = None`.

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
| `world_release_identity` | identity | full-lineup, summary-only | world release identity (matrices never load; pointer only) |
| `science_release_id` | version | full-lineup, summary-only | science release canonical id |
| `verifier_release_id` | version | full-lineup, summary-only | verifier release canonical id |
| `deployment_attestation_id` | version | full-lineup, summary-only | deployment attestation canonical id |
| `predecessor_graph_release_id` | version | full-lineup, summary-only | predecessor graph release id or null |
| `graph_schema_version` | version | full-lineup, summary-only | must equal corpus-graph-vnext/v1 |
| `property_schema_version` | version | full-lineup, summary-only | must equal the content hash of the complete positive property schema |
| `r6_full_union_panel_self_sha256` | hash | full-lineup, summary-only | panel self-hash recorded inside the accepted R6 full-union panel-freeze root |
| `provisioned_disk_bytes` | parameter | full-lineup, summary-only | disk available to the graph store |
| `provisioned_heap_bytes` | parameter | full-lineup, summary-only | JVM heap for the graph service |
| `provisioned_page_cache_bytes` | parameter | full-lineup, summary-only | page cache for the graph store |
| `load_deadline_seconds` | parameter | full-lineup, summary-only | zero-state streamed load deadline |
| `rebuild_deadline_seconds` | parameter | full-lineup, summary-only | zero-state rebuild deadline incl. indexes |

Plus, to make a decision at all: `authority = lead-supplied-terminal`, every
identity non-synthetic (real `gs://` object identities with generation,
sha256, bytes), and a `lead_confirmation_sha256` computed by
`lead_confirmation_for(packet)` over that exact packet. Without these the
receipt stays `pending-lead-inputs` regardless of the numbers; with them it
yields a recommendation that still requires the lead's approval receipt.

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

## Validation (serial, exact results recorded in the branch HANDOFF)

- `pytest tests/test_corpus_graph_capacity.py` — 40 adversarial tests:
  literal law digest; complete-rule property-schema hashing sensitivity;
  vocabulary registration and closed-namespace firewall; Phase 4
  endpoint-cardinality parity against the adapter's projected rows;
  R6 identity replacement; lead-confirmation subject binding (unbound,
  transferred, and fixture-carried confirmations rejected); identity-class
  separation; coherence laws; forcing and none-feasible; ceilings and
  deadlines; exact arithmetic replay; receipt tamper/forge/re-law rejection;
  manifest coverage of every consumed input and of every open kind and
  relationship type.
- `pytest tests/test_corpus_graph_vnext_contracts.py` — regression.
- `pytest tests/test_corpus_graph_vnext_fixture_adapter.py` — Phase 4
  regression.
- `git diff --check`.

## Stop point

Stopped for lead re-review. No mode was chosen.
