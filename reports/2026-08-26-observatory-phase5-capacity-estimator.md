# Observatory workstream — Phase 5 capacity estimator and receipt contract

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-26
**Branch:** `feature/neo4j-react-observatory` (parent `3f656dfd`, accepted Phase 4)
**Scope executed:** Phase 5 capacity-estimator implementation ONLY — no mode
decision, no router mount, no React cutover, no governed/outcome access, no
Neo4j connection or provisioning, no infrastructure or deployment change,
no R6/T230/Core path touched, no merge or rebase.

## What was built

`src/nfl_dfs/research/corpus_graph_capacity.py` (pure, offline):

- **Pre-registered estimation law** (`foundry-graph-capacity-estimation-law/v1`, sha256 `5d20920d5c5e4a77…`): frozen per-element
  byte coefficients (estimates, never observations), index/overhead factor,
  disk and page-cache safety fractions, heap floor, streamed-batch load
  model (batch size 500, 2000 ms per batch), index-build rate, catalogued
  query p50/p95 budgets (200 / 2000 ms), and an absolute element ceiling.
  Per-kind property and string counts derive from the contracts module's
  POSITIVE property schema, which the inputs must bind by content hash
  (`property_schema_version`), not by name.
- **Identity-bound input packet** (`foundry-graph-capacity-inputs/v1`): exact integer counts,
  exact `uri/generation/sha256/bytes` release identities, canonical release
  ids, provisioning parameters, authority, and a self-hash. Fixture
  authority may carry only synthetic identities; lead authority may carry
  none — the two cannot be confused. Cross-count coherence laws
  (selected ≤ unique ≤ occurrences, …) fail closed.
- **Both modes estimated every time**: `full-lineup` (one node per accepted
  unique roster, nine CONTAINS_PLAYER edges each, full membership/trait/
  cohort/admission edges) and `summary-only` (selected-lineup detail only,
  admission edges absent, `full_corpus_traversal_available: false`). Each
  estimate carries node/relationship/property/string counts, raw and
  overhead-adjusted store bytes, batch count, load/index/rebuild seconds,
  the ceilings applied, named violations, and `observed: null` placeholders
  that only a later measured live receipt may fill.
- **Forcing and decision law**: full infeasible → `forced_mode =
  summary-only`; both infeasible → `none-feasible`. The DECISION is
  withheld: fixture inputs always yield `pending-lead-inputs`; lead inputs
  yield only a `recommended_mode` that `requires_lead_approval` and is
  never `self_activating`, and only when a `lead_confirmation_sha256`
  accompanies exact terminal counts and identities.
- **Receipt contract** (`foundry-graph-capacity-receipt/v1`): binds law hash, inputs hash, both estimates,
  forcing result, decision state, the required-inputs manifest, the
  explicit exclusion list, and a labels law; `validate_capacity_receipt`
  re-derives the receipt from its bound inputs and rejects any drift.

## Fixture illustration (synthetic — decision PENDING by construction)

| | full-lineup | summary-only |
|---|---|---|
| nodes | 74,471 | 18,791 |
| relationships | 1,220,867 | 214,307 |
| properties | 2,230,509 | 337,389 |
| estimated store | 419 MiB | 64 MiB |
| streamed batches | 2591 | 467 |
| est. load / rebuild (s) | 5182 / 5187 | 934 / 936 |
| feasible under fixture provisioning | True | True |
| full-corpus traversal | True | False |

`decision.state = pending-lead-inputs`, `recommended_mode = None`.

## Required inputs the lead must supply (exact list, from `required_inputs_manifest()`)

| name | kind | needed by | description |
|---|---|---|---|
| `accepted_slate_count` | count | full-lineup, summary-only | terminal accepted slates in the panel |
| `contest_count` | count | full-lineup, summary-only | registered contests bound to accepted slates |
| `game_count` | count | full-lineup, summary-only | games across accepted slates |
| `team_slate_count` | count | full-lineup, summary-only | team-slate rows across accepted slates |
| `player_slate_count` | count | full-lineup, summary-only | player-slate rows across accepted slates |
| `unique_lineup_count` | count | full-lineup | distinct roster_ids across the accepted corpus |
| `lineup_occurrence_count` | count | full-lineup | corpus memberships incl. cross-arm duplicates |
| `lineup_arm_supply_count` | count | full-lineup | (lineup, source arm) supply pairs |
| `admitted_membership_count` | count | full-lineup | (lineup, admission) admitted pairs |
| `trait_membership_count` | count | full-lineup | (lineup, trait) memberships, sparse |
| `cohort_membership_count` | count | full-lineup | (lineup, cohort) memberships |
| `selected_unique_lineup_count` | count | full-lineup, summary-only | distinct lineups appearing in any selected book |
| `selected_lineup_occurrence_count` | count | summary-only | corpus memberships of selected lineups only |
| `selected_lineup_arm_supply_count` | count | summary-only | (selected lineup, source arm) supply pairs |
| `selected_trait_membership_count` | count | summary-only | (selected lineup, trait) memberships |
| `selected_cohort_membership_count` | count | summary-only | (selected lineup, cohort) memberships |
| `selected_book_count` | count | full-lineup, summary-only | exact selected books (bundle x slate x budget) |
| `selected_book_membership_count` | count | full-lineup, summary-only | (book, lineup) memberships across all books |
| `fill_preset_count` | count | full-lineup, summary-only | registered fill presets |
| `admission_preset_count` | count | full-lineup, summary-only | registered admission presets |
| `retrieval_preset_count` | count | full-lineup, summary-only | registered retrieval presets |
| `strategy_bundle_count` | count | full-lineup, summary-only | registered strategy bundles |
| `experiment_run_count` | count | full-lineup, summary-only | experiment runs bound to the release |
| `experiment_cell_count` | count | full-lineup, summary-only | experiment cells |
| `evaluation_count` | count | full-lineup, summary-only | evaluations (books-frozen or later) |
| `fold_count` | count | full-lineup, summary-only | fold definitions |
| `metric_set_count` | count | full-lineup, summary-only | metric-set nodes |
| `metric_edge_count` | count | full-lineup, summary-only | HAS_METRIC relationships |
| `trait_definition_count` | count | full-lineup, summary-only | versioned trait definitions |
| `cohort_count` | count | full-lineup, summary-only | cohort definitions |
| `winner_release_count` | count | full-lineup, summary-only | winner releases (governed) |
| `winner_observation_count` | count | full-lineup, summary-only | winner observations in the bound release |
| `winner_observation_edge_count` | count | full-lineup, summary-only | OBSERVED_IN_WINNER_RELEASE relationships |
| `source_artifact_count` | count | full-lineup, summary-only | source artifact identities |
| `verification_receipt_count` | count | full-lineup, summary-only | verification receipts |
| `attempt_count` | count | full-lineup, summary-only | attempt records |
| `promotion_decision_count` | count | full-lineup, summary-only | promotion decisions |
| `lineage_edge_count` | count | full-lineup, summary-only | DERIVED_FROM/USES_*/GENERATED_BY/VERIFIED_BY/RETRIED_AS/EVALUATED_IN/PAIRED_AGAINST/EVALUATES_BUNDLE/DECIDES_ON_BUNDLE relationships combined |
| `inferred_defender_exposure_edge_count` | count | full-lineup, summary-only | HAS_INFERRED_DEFENDER_EXPOSURE relationships (qualified) |
| `mean_string_property_bytes` | count | full-lineup, summary-only | measured mean UTF-8 bytes of string properties in the release |
| `combined_panel_index_identity` | identity | full-lineup, summary-only | foundry-v12-combined-panel-index/v1 object identity |
| `t230_panel_release_identity` | identity | full-lineup, summary-only | foundry-t230-panel-release/v1 object identity |
| `source_universe_release_identity` | identity | full-lineup, summary-only | artifact-supported source-universe release identity |
| `world_release_identity` | identity | full-lineup, summary-only | world release identity (matrices never load; pointer only) |
| `winner_release_identity` | identity | full-lineup, summary-only | governed winner release identity (required when cohort/trait namespaces load) |
| `science_release_id` | version | full-lineup, summary-only | science release canonical id |
| `verifier_release_id` | version | full-lineup, summary-only | verifier release canonical id |
| `deployment_attestation_id` | version | full-lineup, summary-only | deployment attestation canonical id |
| `predecessor_graph_release_id` | version | full-lineup, summary-only | predecessor graph release id or null |
| `graph_schema_version` | version | full-lineup, summary-only | must equal corpus-graph-vnext/v1 |
| `property_schema_version` | version | full-lineup, summary-only | must equal the contracts' positive property schema version |
| `provisioned_disk_bytes` | parameter | full-lineup, summary-only | disk available to the graph store |
| `provisioned_heap_bytes` | parameter | full-lineup, summary-only | JVM heap for the graph service |
| `provisioned_page_cache_bytes` | parameter | full-lineup, summary-only | page cache for the graph store |
| `load_deadline_seconds` | parameter | full-lineup, summary-only | zero-state streamed load deadline |
| `rebuild_deadline_seconds` | parameter | full-lineup, summary-only | zero-state rebuild deadline incl. indexes |

Plus, to make a decision at all: `authority = lead-supplied-terminal`, every
identity non-synthetic (real `gs://` object identities with generation,
sha256, bytes), and a `lead_confirmation_sha256` over the packet. Without
these the receipt stays `pending-lead-inputs` regardless of the numbers.

## Excluded from Neo4j in BOTH modes

- world score matrices
- per-world nodes or relationships
- dense pairwise player/lineup networks (quadratic)
- raw licensed Fantasy Points or SIS rows
- raw contest standings and contestant identifiers
- credentials or secrets
- mutable active-policy pointers
- realized namespace (closed offline)

## Validation (serial)

- `pytest tests/test_corpus_graph_capacity.py` — **30 passed** (adversarial:
  determinism/order independence; fixture vs lead authority separation and
  identity-class enforcement; malformed/missing/extra/out-of-range/boolean/
  float counts; identity malformations; schema/property-version binding;
  coherence laws; forcing to summary-only; none-feasible; element ceiling
  and deadline enforcement; exact integer arithmetic replay; property counts
  derived from the positive schema; law-hash freeze; receipt tamper, forge,
  and re-law rejection; manifest coverage of every consumed input;
  exclusions; fixture scale bounds).
- `pytest tests/test_corpus_graph_vnext_contracts.py` — regression green.
- `git diff --check` — clean.

## Stop point

Stopped for lead review. Next action on approval: the lead supplies the
exact terminal counts and identities listed above with a confirmation hash;
the estimator then produces a decidable receipt whose recommendation still
requires the lead's explicit approval receipt before any provisioning.
