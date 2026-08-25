"""Pure companion manifest for the two pre-Week-1 generation additions.

This module does not generate lineups, invoke an optimizer, read cloud objects,
score historical outcomes, or publish an experiment.  It validates the frozen
53-slate factorial manifest and registers two separately implemented candidate-
generation experiments, their matched controls, shared ordinary-R lineage, and
their mandatory pre-grade catalog fragment.

The eight primary factorial cells and the 18-row retrieval registry remain
owned by :mod:`corpus_extreme_tail_factorial_manifest`; this companion only
refers to their exact hashes.  A retained manifest is accepted only by replay
from the authoritative 54-slate source catalog and the complete factorial
inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_factorial_manifest as factorial
from nfl_dfs.research import corpus_extreme_tail_generation_additions as additions
from nfl_dfs.research import corpus_parametric_batch as batch


GENERATION_COMPANION_MANIFEST_SCHEMA: Final = (
    "foundry-extreme-tail-generation-companion-manifest/v1"
)
GENERATION_REGISTRY_SCHEMA: Final = (
    "foundry-extreme-tail-generation-companion-registry/v1"
)
PAIRED_CONTROL_REGISTRY_SCHEMA: Final = (
    "foundry-extreme-tail-generation-paired-controls/v1"
)
CONTROL_IMPLEMENTATION_SCHEMA: Final = (
    "foundry-extreme-tail-generation-control-implementation/v1"
)
HARD230_CONTROL_RECEIPT_SCHEMA: Final = (
    "hard-230-score-blind-stream-prefix-control-receipt/v1"
)
HARD230_CONTROL_STREAM_SCHEMA: Final = (
    "hard-230-score-blind-complete-generator-stream/v1"
)
DISCOVERY_CONTROL_RECEIPT_SCHEMA: Final = (
    "incumbent-equal-visit-control-receipt/v1"
)
PROSPECTIVE_SHADOW_BINDING_SCHEMA: Final = (
    "foundry-prospective-k20-oi-shadow-binding/v1"
)
PRE_GRADE_CATALOG_SCHEMA: Final = (
    "foundry-extreme-tail-aggregate-pre-grade-catalog-contract/v1"
)
PUBLICATION_MODE: Final = "create_once"

PROTOCOL_DOCUMENT: Final = (
    "reports/2026-08-25-pre-week1-historical-experiment-matrix.md"
)
PROTOCOL_SHA256: Final = (
    "b7d6c8f4f0ed2f6db667933717f5446545a06f1f2cda2c8ecd56ca26b45d34bc"
)
CENSUS_DOCUMENT: Final = (
    "reports/2026-08-25-complete-pre-week1-foundry-strategy-census.md"
)
CENSUS_SHA256: Final = (
    "bb05e1ec5fa7a7d836282b41a2ed864aa7828a939257e674cf0625511862950f"
)

CORE_PROTOCOL_SHA256: Final = (
    "4cd61f51617322bcafb3e2a867332ed4e35484073aa47c3d9891339fd493f338"
)
CORE_RETRIEVAL_CONTRACT_SHA256: Final = (
    "e2eeb254d9cfd1a34c2d0a1493beba1a74c1b35eb2b82f30965f207cba051fd2"
)
CORE_EVALUATION_CONTRACT_SHA256: Final = (
    "9a696ec0af071efb88b04ac7f843c0cac02ea84bc81ca2de50741609552d748e"
)
CORE_CROSS_FIT_CONTRACT_SHA256: Final = (
    "e6ba434de3f24238d5045f228106fb3ad825d52493d4bd8f35369cdd6046950e"
)
CORE_SHARED_ARTIFACT_CONTRACT_SHA256: Final = (
    "a6d65ed2c6f50db50e3ae0d58454e9410f1095e11fff36cd8dfe389d7e171393"
)
CORE_CONTROLLED_GRADE_BOUNDARY_SHA256: Final = (
    "c28750689b314f02c39ebad2b0ca1c685052e9457104e34d7efe99f08c7b1a21"
)
CORE_FACTORIAL_CELL_REGISTRY_SHA256: Final = (
    "ac462b7665c6d0072238cb827421bbb71a6b09fef14bf3ef14eb81b0af06c1c4"
)
CORE_CANDIDATE_ORIGIN_REGISTRY_SHA256: Final = (
    "114f5477c2826b7a913cf23ff95f853e9db2d84d5eb797c7b3552b86795b8191"
)
CORE_CANDIDATE_ORIGIN_MASKS_SHA256: Final = (
    "aea7ee5b2e75829c2a6b4884da702eb2b681b982a53b31963f1196c4794028be"
)

FACTORIAL_SLATE_COUNT: Final = 53
EVALUATION_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
RANKING_PREFIX_LAW: Final = "exact-prefix-of-one-deterministic-rank-80"
K5_ORIGINS: Final = EVALUATION_BLOCKS
RELEASE_EXECUTION_MODE: Final = "release"
FIXTURE_EXECUTION_MODE: Final = "test-fixture"
HARD230_MINIMUM_SOLVER_CALL_CEILING: Final = 200
HARD230_SOLVER_CALLS_PER_TARGET: Final = 20
HARD230_MAXIMUM_SOLVER_CALL_CEILING: Final = 10_000

HARD230_CONTROL_ID: Final = "hard-230-score-blind-stream-prefix-control-v1"
DISCOVERY_CONTROL_ID: Final = "incumbent-equal-visit-control-v1"
CONTROL_IMPLEMENTATION_ID: Final = (
    "canonical-score-blind-prefix-and-equal-visit-controls-v1"
)
PROSPECTIVE_K20_OI_SHADOW_ID: Final = "2026-cbwu-oi-v1"
HARD230_POPULATION_ID: Final = "G-hard230-generate-replenish"
DISCOVERY_POPULATION_ID: Final = "G-game-regime-tail-discovery"
DISCOVERY_CONTROL_POPULATION_ID: Final = "G-incumbent-equal-visit-control"
R194_ID: Final = "coverage-194-v1"
T230_ID: Final = "frozen-census-support-switch-ge-230/v1"

HARD230_STRATEGY_SHA256: Final = (
    "524aa7cb737f325cafccda857ce68ac8f5801967f2d157aa06de85fd057da594"
)
HARD230_IMPLEMENTATION_SHA256: Final = (
    "2700a83440e05056c99d429e0f910074c492fac10e55a860891964f4ae6b3da1"
)
HARD230_PUBLIC_CONTRACT_SHA256: Final = (
    "8454f3993c320d5f0b9689a37f25a42b06e56d6ec6eb7fbd3b680e9f77954ec1"
)
DISCOVERY_STRATEGY_SHA256: Final = (
    "4389ad29e21340fee2bef6e2e76bb5cb773a39f78e580bb7c77acd8fcde41f30"
)
DISCOVERY_IMPLEMENTATION_SHA256: Final = (
    "3e0a849e9cf57ad8edbdd903f1e0e06d785f19832ac1c1fd39d935224f634bd2"
)
DISCOVERY_PUBLIC_CONTRACT_SHA256: Final = (
    "94eeba2d806516c4ce22c5ef3480dd343a440618395bad93cec009a2303ebf3c"
)

R194_STRATEGY_SHA256: Final = (
    "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f"
)
R194_IMPLEMENTATION_SHA256: Final = (
    "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f"
)
T230_STRATEGY_SHA256: Final = (
    "e44525130cdd119d441178da9f2a003876f63d328b44f1730b48064ef61d56ab"
)
T230_IMPLEMENTATION_SHA256: Final = (
    "73f53f8b3e7b8d9ec6c661de16e5c171917526858bc1a358a555fcc78085bd30"
)

# Filled from the literal bodies below.  These are independent expectations,
# not hashes copied from a retained manifest.
EXPECTED_HARD230_CONTROL_SHA256: Final = (
    "c819c6827e0a488d942fcaa6387a626abe9fe4c37488fec674b341095f3e92af"
)
EXPECTED_DISCOVERY_CONTROL_SHA256: Final = (
    "a879170e6174cd553a89708f1c9871efb5d3ea70a6d6feb0d64c973fa2cb0800"
)
EXPECTED_CONTROL_IMPLEMENTATION_SHA256: Final = (
    "f55f43ac4f8594ac3d3f8400b21aae863f27f3739aa0578bfac162aa5b90c5b7"
)
EXPECTED_PAIRED_CONTROL_REGISTRY_SHA256: Final = (
    "725f59b66c2336799bb243f61505e59e434e0937146c638f8edd7609f8a7e871"
)
EXPECTED_ORDINARY_R_MATRIX_LAW_SHA256: Final = (
    "e5034012a3009defa19629c39f6b7a8ecdce6f4b902b859614099fdc7329b9da"
)
EXPECTED_GENERATION_CROSS_FIT_LAW_SHA256: Final = (
    "813ab71200eca50ecfe38c0d8827d79028bd9d8d05466bdc9c8a2a89dca65a82"
)
EXPECTED_GENERATION_REGISTRY_SHA256: Final = (
    "a698cc9c717974155e5ab417e1f8b2284b185be512a7b8d3bffe85c439927913"
)
EXPECTED_RETRIEVAL_DEPENDENCY_REGISTRY_SHA256: Final = (
    "93fa6b8f643c46a4dc26580140ff184ce34588b6c0c505e9c321ec379b550318"
)
EXPECTED_STAGE_B_CATALOG_REGISTRY_SHA256: Final = (
    "b1c46dfb4f4a20989ebcd90453c8401d402272ee37f24dd963cca317287329e0"
)
EXPECTED_AGGREGATE_PRE_GRADE_LAW_SHA256: Final = (
    "86c3c6fa152cc9b3673632eb50284f7c4f5cba78401b2bc1270b6bde567c3b5e"
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "realized_grade_open_authority",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
    "publication_authority",
    "acceptance_authority",
    "evaluation_authority",
    "aggregate_catalog_completion_authority",
    "outcome_access_authority",
    "grade_authority",
)
_PUBLIC_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "realized_grade_open_authority",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
    "publication_authority",
    "source_replay_authority",
    "solver_proof_authority",
    "acceptance_authority",
    "evaluation_authority",
)

_MANIFEST_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "manifest_id",
    "protocol_document",
    "protocol_sha256",
    "census_document",
    "census_sha256",
    "core_factorial_manifest_id",
    "core_factorial_manifest_sha256",
    "core_protocol_sha256",
    "source_catalog_identity",
    "source_catalog_id",
    "source_catalog_sha256",
    "source_membership_sha256",
    "source_membership_acceptance_sha256",
    "source_lineage_contract",
    "factorial_slate_count",
    "factorial_slates",
    "factorial_slates_sha256",
    "ordinary_r_matrix_law",
    "generation_cross_fit_law",
    "control_implementation_contract",
    "control_implementation_sha256",
    "paired_control_registry",
    "paired_control_registry_sha256",
    "generation_registry",
    "generation_registry_sha256",
    "retrieval_dependency_registry",
    "retrieval_dependency_registry_sha256",
    "stage_b_catalog_registry",
    "stage_b_catalog_registry_sha256",
    "aggregate_pre_grade_catalog_contract",
    "prospective_k20_oi_shadow_binding",
    "prospective_k20_oi_shadow_binding_sha256",
    "entry_budgets",
    "ranking_depth",
    "ranking_prefix_law",
    "source_commit_sha",
    "immutable_image",
    "core_output_prefix",
    "companion_output_prefix",
    *_FALSE_AUTHORITY_FIELDS,
    "generation_companion_manifest_sha256",
})


class CorpusExtremeTailGenerationCompanionManifestError(ValueError):
    """A companion manifest or dependency differs from the frozen law."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailGenerationCompanionManifestError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _nonempty_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailGenerationCompanionManifestError(
            f"{label} must be one generation/content/bytes-bound object identity"
        ) from exc


def _canonical_roster_identity(
    value: object, supplied_sha256: object, *, label: str
) -> tuple[list[str], str]:
    raw = _sequence(value, label=f"{label}.roster_player_ids")
    roster = [
        _nonempty_string(player_id, label=f"{label}.roster_player_id")
        for player_id in raw
    ]
    if len(roster) != 9 or roster != sorted(set(roster)):
        _fail(f"{label} roster must be nine sorted unique player IDs")
    digest = batch.canonical_sha256({
        "schema_version": "canonical-dk-roster-identity/v1",
        "player_ids": roster,
    })
    if _sha256(supplied_sha256, label=f"{label}.roster_sha256") != digest:
        _fail(f"{label} roster hash differs from canonical roster identity")
    return roster, digest


def _validate_json_identity(
    value: object, identity: object, *, label: str
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except Exception as exc:
        raise CorpusExtremeTailGenerationCompanionManifestError(
            f"{label} differs from exact canonical JSON bytes"
        ) from exc


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _public_false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _PUBLIC_FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = _sha256(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


_FROZEN_SEED_PAIRS: Final = (
    (0, 7331),
    (1137260708, 2690847602),
    (2875959182, 1630284992),
    (253722715, 3374646876),
    (1643280042, 3977633467),
    (2786141412, 2801677210),
    (1461353386, 1586091810),
    (137204844, 2046775861),
    (2184743543, 3320854134),
    (651833611, 3089304063),
    (1935613362, 3432329768),
    (31867868, 2977492966),
    (1988904477, 4192316077),
    (1852762881, 2368290637),
    (4006641982, 2226041783),
    (1093906274, 1859951038),
    (135109598, 3661127064),
    (3815695926, 1138144331),
    (3020163036, 3089093104),
    (186549143, 564317351),
)


def _expected_public_origin_registry() -> list[dict[str, object]]:
    return [
        {
            "origin_ordinal": ordinal,
            "origin_id": f"R{ordinal}",
            "projection_seed": projection_seed,
            "role_seed": role_seed,
            "evaluation_block": f"R{ordinal}" if ordinal < 5 else None,
            "candidate_discovery_only": ordinal >= 5,
        }
        for ordinal, (projection_seed, role_seed) in enumerate(_FROZEN_SEED_PAIRS)
    ]


def _expected_hard230_strategy_body() -> dict[str, object]:
    return {
        "strategy_id": additions.HARD230_STRATEGY_ID,
        "generator_law_id": additions.HARD230_GENERATOR_LAW_ID,
        "retention_threshold_milli_dk": 230_000,
        "retention_operator": ">=",
        "paired_target_law": "exact-same-scope-control-retained-count",
        "cross_fit_law": "R0..R4-minus-heldout; no-heldout-origin-or-score-column",
        "stream_law": "contiguous-ordered-world-permutation-until-target-or-cap",
        "shortfall_law": "fail-never-lower-230-never-borrow-never-overrun-cap",
    }


def _expected_hard230_implementation_body() -> dict[str, object]:
    return {
        "schemas": [
            additions.HARD230_CONTRACT_SCHEMA,
            additions.HARD230_RECEIPT_SCHEMA,
            additions.HARD230_OCCURRENCE_SCHEMA,
        ],
        "matrix_encoding": "row-major-little-endian-int64-milli-dk/v1",
        "matrix_hash_row_chunk_size": 32,
        "legality_audit_law_id": "residual-world-audit-legal-identity-v1",
        "legality_audit_implementation_sha256": (
            "e807818c584df7a35a3c1f6a0c1e4e028081d6354425209b362d31712ab84daa"
        ),
        "score_derivation": (
            "sequential-int64-roster-sum-over-exact-permitted-block-columns"
        ),
        "proof_lineage": (
            "generation-pinned-solver-legality-and-matrix-derivation-artifacts"
        ),
        "solver_optimality_role": "outer-replay-required-not-locally-proven",
        "player_count_bounds": [9, 512],
        "game_count_bounds": [2, 64],
        "world_column_maximum": 60_000,
        "player_score_abs_maximum_milli_dk": 1_000_000,
    }


def _expected_discovery_strategy_body() -> dict[str, object]:
    return {
        "strategy_id": additions.DISCOVERY_STRATEGY_ID,
        "world_source": "existing-historical-ordinary-unweighted-R-worlds",
        "feature_law": "per-world-game-level-simulated-player-score-sums",
        "regime_order": [
            "single-game-spike",
            "dominant-game",
            "distributed-games",
        ],
        "spike_ratio": [2, 1],
        "dominant_ratio": [5, 4],
        "zero_top_law": "distributed-games",
        "schedule_law": "regime-then-game-round-robin-with-canonical-ties",
        "budget_law": "exact-same-scope-control-visit-and-solve-count",
        "candidate_law": "one-reported-incumbent-legal-optimum-per-visit",
        "evaluation_law": "separate-heldout-ordinary-R-block-only",
        "atlas_and_realized_forbidden": True,
    }


def _expected_discovery_implementation_body() -> dict[str, object]:
    return {
        "schemas": [
            additions.DISCOVERY_CONTRACT_SCHEMA,
            additions.DISCOVERY_SCHEDULE_SCHEMA,
            additions.DISCOVERY_ACCOUNTING_SCHEMA,
            additions.DISCOVERY_OCCURRENCE_SCHEMA,
            additions.DISCOVERY_EVALUATION_SCHEMA,
        ],
        "matrix_encoding": "row-major-little-endian-int64-milli-dk/v1",
        "matrix_hash_row_chunk_size": 32,
        "world_aggregate_chunk_size": 256,
        "aggregate_memory_law": "game-count-by-at-most-chunk-width-int64-buffer",
        "legality_audit_law_id": "residual-world-audit-legal-identity-v1",
        "legality_audit_implementation_sha256": (
            "e807818c584df7a35a3c1f6a0c1e4e028081d6354425209b362d31712ab84daa"
        ),
        "schedule_replay_law": "rebuild-from-bound-matrix-and-membership",
        "accounting_replay_law": "rebuild-entire-source-derived-schedule",
        "evaluation_derivation": "one-roster-vector-at-a-time-heldout-slice-only",
        "solver_optimality_role": "outer-replay-required-not-locally-proven",
        "player_count_bounds": [9, 512],
        "game_count_bounds": [2, 64],
        "world_column_maximum": 60_000,
        "player_score_abs_maximum_milli_dk": 1_000_000,
    }


def _expected_hard230_public_contract() -> dict[str, object]:
    origins = _expected_public_origin_registry()
    body: dict[str, object] = {
        "schema_version": additions.HARD230_CONTRACT_SCHEMA,
        "strategy_id": additions.HARD230_STRATEGY_ID,
        "strategy_sha256": HARD230_STRATEGY_SHA256,
        "implementation_sha256": HARD230_IMPLEMENTATION_SHA256,
        "strategy_body": _expected_hard230_strategy_body(),
        "implementation_body": _expected_hard230_implementation_body(),
        "candidate_origin_registry": origins,
        "candidate_origin_registry_sha256": batch.canonical_sha256(origins),
        "world_block_registry": list(EVALUATION_BLOCKS),
        "worlds_per_source_stream": WORLDS_PER_BLOCK,
        "minimum_solver_call_ceiling": HARD230_MINIMUM_SOLVER_CALL_CEILING,
        "solver_calls_per_target": HARD230_SOLVER_CALLS_PER_TARGET,
        "maximum_solver_call_ceiling": HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        "every_occurrence_and_decision_bound": True,
        "optimizer_cloud_adapter_status": "pending",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_and_solver_replay_required": True,
        **{field: False for field in _PUBLIC_FALSE_AUTHORITY_FIELDS},
    }
    body["hard230_contract_sha256"] = HARD230_PUBLIC_CONTRACT_SHA256
    return body


def _expected_discovery_public_contract() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": additions.DISCOVERY_CONTRACT_SCHEMA,
        "strategy_id": additions.DISCOVERY_STRATEGY_ID,
        "strategy_sha256": DISCOVERY_STRATEGY_SHA256,
        "implementation_sha256": DISCOVERY_IMPLEMENTATION_SHA256,
        "strategy_body": _expected_discovery_strategy_body(),
        "implementation_body": _expected_discovery_implementation_body(),
        "world_block_registry": list(EVALUATION_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "fit_scope": "four-training-blocks-minus-one-exact-heldout-block",
        "atlas_world_score_forbidden": True,
        "achievable_lineup_optimum_for_scheduling_forbidden": True,
        "realized_outcomes_forbidden": True,
        "optimizer_cloud_adapter_status": "pending",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_and_solver_replay_required": True,
        **{field: False for field in _PUBLIC_FALSE_AUTHORITY_FIELDS},
    }
    body["discovery_contract_sha256"] = DISCOVERY_PUBLIC_CONTRACT_SHA256
    return body


def _public_generation_contracts() -> tuple[dict[str, object], dict[str, object]]:
    hard = additions.frozen_hard230_generation_replenishment_contract_v1()
    discovery = additions.frozen_game_regime_tail_discovery_contract_v1()
    expected_hard = _expected_hard230_public_contract()
    expected_discovery = _expected_discovery_public_contract()
    if batch.canonical_json_bytes(hard) != batch.canonical_json_bytes(expected_hard):
        _fail("hard-230 public strategy/implementation contract drifted")
    if batch.canonical_json_bytes(discovery) != batch.canonical_json_bytes(
        expected_discovery
    ):
        _fail("game-regime public strategy/implementation contract drifted")
    for contract, field, expected_hash, label in (
        (hard, "hard230_contract_sha256", HARD230_PUBLIC_CONTRACT_SHA256, "hard-230"),
        (
            discovery,
            "discovery_contract_sha256",
            DISCOVERY_PUBLIC_CONTRACT_SHA256,
            "game-regime",
        ),
    ):
        _public_false_authorities(contract, label=f"{label} public contract")
        if contract.get(field) != expected_hash:
            _fail(f"{label} public contract hash differs")
        _validate_self_hash(contract, field=field, label=f"{label} public contract")
    return hard, discovery


def _execution_mode(value: object) -> str:
    if value not in {RELEASE_EXECUTION_MODE, FIXTURE_EXECUTION_MODE}:
        _fail(
            "execution_mode must be exactly 'release' or the explicit "
            "non-release 'test-fixture' mode"
        )
    return str(value)


def _hard230_ceiling_law(
    *, target_retained_count: int, source_stream_world_count: int, execution_mode: str
) -> tuple[int, int]:
    hard_contract, _discovery_contract = _public_generation_contracts()
    if (
        hard_contract.get("minimum_solver_call_ceiling")
        != HARD230_MINIMUM_SOLVER_CALL_CEILING
        or hard_contract.get("solver_calls_per_target")
        != HARD230_SOLVER_CALLS_PER_TARGET
        or hard_contract.get("maximum_solver_call_ceiling")
        != HARD230_MAXIMUM_SOLVER_CALL_CEILING
        or hard_contract.get("worlds_per_source_stream") != WORLDS_PER_BLOCK
    ):
        _fail("public hard-230 ceiling contract differs")
    target = _exact_int(
        target_retained_count, label="target_retained_count", minimum=1
    )
    source_worlds = _exact_int(
        source_stream_world_count, label="source_stream_world_count", minimum=1
    )
    if source_worlds > WORLDS_PER_BLOCK:
        _fail("source_stream_world_count exceeds the frozen public stream width")
    mode = _execution_mode(execution_mode)
    if mode == RELEASE_EXECUTION_MODE and source_worlds != WORLDS_PER_BLOCK:
        _fail("release hard control requires exactly 10,000 source-stream worlds")
    computed = min(
        HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        max(
            HARD230_MINIMUM_SOLVER_CALL_CEILING,
            HARD230_SOLVER_CALLS_PER_TARGET * target,
        ),
    )
    effective = min(source_worlds, computed)
    if target > effective:
        _fail("paired target exceeds the frozen effective solver-call ceiling")
    return computed, effective


def _control_implementation_body() -> dict[str, object]:
    return {
        "schema_version": CONTROL_IMPLEMENTATION_SCHEMA,
        "implementation_id": CONTROL_IMPLEMENTATION_ID,
        "hard230_builder": "build_hard230_score_blind_control_receipt_v1",
        "hard230_validator": "validate_hard230_score_blind_control_receipt_v1",
        "hard230_algorithm": (
            "consume-exact-ordered-stream;retain-first-optimal-legal-unique-"
            "canonical-roster-identities;stop-exactly-at-paired-target-or-"
            "public-contract-derived-effective-ceiling"
        ),
        "hard230_stream_schema": HARD230_CONTROL_STREAM_SCHEMA,
        "hard230_stream_builder": "build_hard230_control_stream_manifest_v1",
        "hard230_complete_stream_identity_required": True,
        "hard230_early_prefix_may_not_claim_exhaustion": True,
        "hard230_generator_exhaustion_before_ceiling_supported": False,
        "hard230_minimum_solver_call_ceiling": (
            HARD230_MINIMUM_SOLVER_CALL_CEILING
        ),
        "hard230_solver_calls_per_target": HARD230_SOLVER_CALLS_PER_TARGET,
        "hard230_maximum_solver_call_ceiling": (
            HARD230_MAXIMUM_SOLVER_CALL_CEILING
        ),
        "hard230_effective_ceiling_law": (
            "min(source-stream-world-count,min(10000,max(200,20*target)))"
        ),
        "release_hard230_source_stream_world_count": WORLDS_PER_BLOCK,
        "hard230_score_or_value_fields_forbidden": True,
        "discovery_builder": "build_incumbent_equal_visit_control_receipt_v1",
        "discovery_validator": (
            "validate_incumbent_equal_visit_control_receipt_v1"
        ),
        "discovery_algorithm": (
            "for-each-canonical-fit-block-sum-player-int64-milli-dk-by-world;"
            "rank-descending-total-with-world-index-ascending-tie;take-exact-"
            "visit-prefix;consume-one-bound-solver-result-per-visit"
        ),
        "discovery_matrix_encoding": additions.SCORE_MATRIX_ENCODING,
        "discovery_matrix_hash_function": (
            "corpus_extreme_tail_generation_additions."
            "canonical_score_matrix_sha256_v1"
        ),
        "discovery_matrix_block_ids": list(EVALUATION_BLOCKS),
        "release_discovery_worlds_per_block": WORLDS_PER_BLOCK,
        "nonrelease_fixture_mode": FIXTURE_EXECUTION_MODE,
        "discovery_matrix_fit_slicing": (
            "derive-canonical-four-training-block-slices-from-bound-all-five-"
            "ordinary-r-int64-milli-dk-matrix"
        ),
        "discovery_challenger_implementation_sha256": (
            DISCOVERY_IMPLEMENTATION_SHA256
        ),
        "discovery_schedule_tie_law": (
            "numpy-lexsort-world-index-ascending-after-negative-int64-total"
        ),
        "canonical_roster_identity_law": (
            "sha256-canonical-json-of-canonical-dk-roster-identity-v1-and-"
            "nine-sorted-unique-player-ids"
        ),
        "control_receipts_are_pure_canonical_json": True,
        "cloud_reads_or_optimizer_invocation": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def frozen_generation_companion_control_implementation_v1() -> dict[str, object]:
    """Return the literal implementation authority for both paired controls."""
    retained = _self_hash(_control_implementation_body(), "implementation_sha256")
    if retained["implementation_sha256"] != EXPECTED_CONTROL_IMPLEMENTATION_SHA256:
        _fail("literal paired-control implementation hash differs")
    _false_authorities(retained, label="paired-control implementation")
    _validate_self_hash(
        retained,
        field="implementation_sha256",
        label="paired-control implementation",
    )
    return retained


_HARD_CONTROL_OCCURRENCE_KEYS: Final = frozenset({
    "occurrence_ordinal",
    "solver_status",
    "lineup_id",
    "roster_player_ids",
    "roster_sha256",
    "legality_passed",
    "solver_proof_identity",
    "legality_proof_identity",
})
_HARD_CONTROL_RECEIPT_KEYS: Final = frozenset({
    "schema_version",
    "control_id",
    "implementation_id",
    "implementation_sha256",
    "slate_id",
    "candidate_origin_id",
    "fit_scope_id",
    "heldout_block_id",
    "training_block_ids",
    "execution_mode",
    "hard230_public_contract_sha256",
    "source_member_sha256",
    "score_block_ids",
    "score_block_identities_sha256",
    "player_registry_sha256",
    "player_score_matrix_sha256",
    "ordered_generator_stream_manifest",
    "ordered_generator_stream_manifest_identity",
    "target_retained_count",
    "source_stream_world_count",
    "computed_solver_call_ceiling",
    "effective_solver_call_ceiling",
    "stream_termination_reason",
    "stream_exhaustion_proof_identity",
    "generator_configuration_sha256",
    "solver_implementation_sha256",
    "paired_target_identity",
    "occurrences",
    "occurrence_ledger_sha256",
    "consumed_occurrence_count",
    "retained_rosters",
    "retained_rosters_sha256",
    "retained_count",
    "shortfall_count",
    "completion_status",
    "score_or_value_read",
    *_FALSE_AUTHORITY_FIELDS,
    "control_receipt_sha256",
})


def _canonical_fold_scope(
    *, heldout_block_id: object, training_block_ids: object
) -> tuple[str, list[str]]:
    heldout = _nonempty_string(heldout_block_id, label="heldout_block_id")
    if heldout not in EVALUATION_BLOCKS:
        _fail("heldout_block_id must be one canonical R0..R4 block")
    raw = _sequence(training_block_ids, label="training_block_ids")
    training = [
        _nonempty_string(value, label="training_block_id") for value in raw
    ]
    expected = [block for block in EVALUATION_BLOCKS if block != heldout]
    if training != expected:
        _fail("training_block_ids must be canonical R0..R4 minus heldout")
    return heldout, training


_HARD_CONTROL_STREAM_KEYS: Final = frozenset({
    "schema_version",
    "stream_id",
    "candidate_origin_id",
    "fit_scope_id",
    "execution_mode",
    "hard230_public_contract_sha256",
    "generator_configuration_sha256",
    "solver_implementation_sha256",
    "target_retained_count",
    "source_stream_world_count",
    "minimum_solver_call_ceiling",
    "solver_calls_per_target",
    "maximum_solver_call_ceiling",
    "computed_solver_call_ceiling",
    "effective_solver_call_ceiling",
    "occurrence_count",
    "stream_positions",
    "occurrence_membership_sha256",
    "termination_reason",
    "generator_exhausted",
    "exhaustion_proof_identity",
})


def _normalize_hard_control_occurrences(
    occurrences: object,
) -> list[dict[str, object]]:
    raw_occurrences = _sequence(occurrences, label="occurrences")
    if len(raw_occurrences) > 10_000:
        _fail("hard-control occurrence ledger exceeds the frozen ceiling")
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(raw_occurrences):
        row = _mapping(raw, label=f"occurrence[{ordinal}]")
        _exact_keys(row, _HARD_CONTROL_OCCURRENCE_KEYS, label=f"occurrence[{ordinal}]")
        if row.get("occurrence_ordinal") != ordinal:
            _fail("hard-control occurrence order differs")
        status = _nonempty_string(row.get("solver_status"), label="solver_status")
        if status not in {"optimal", "infeasible", "error"}:
            _fail("hard-control solver_status differs")
        solver_proof = _object_identity(
            row.get("solver_proof_identity"), label="solver_proof_identity"
        )
        if status == "optimal":
            lineup_id = _nonempty_string(row.get("lineup_id"), label="lineup_id")
            roster, roster_hash = _canonical_roster_identity(
                row.get("roster_player_ids"),
                row.get("roster_sha256"),
                label=f"occurrence[{ordinal}]",
            )
            if row.get("legality_passed") is not True:
                _fail("optimal hard-control occurrence must independently pass legality")
            legality_proof: dict[str, object] | None = _object_identity(
                row.get("legality_proof_identity"), label="legality_proof_identity"
            )
        else:
            if any(
                row.get(field) is not None
                for field in (
                    "lineup_id",
                    "roster_player_ids",
                    "roster_sha256",
                    "legality_passed",
                    "legality_proof_identity",
                )
            ):
                _fail("non-optimal hard-control occurrence must have null lineup fields")
            lineup_id = None
            roster = None
            roster_hash = None
            legality_proof = None
        normalized.append({
            "occurrence_ordinal": ordinal,
            "solver_status": status,
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "roster_sha256": roster_hash,
            "legality_passed": True if status == "optimal" else None,
            "solver_proof_identity": solver_proof,
            "legality_proof_identity": legality_proof,
        })
    return normalized


def build_hard230_control_stream_manifest_v1(
    *,
    stream_id: str,
    candidate_origin_id: str,
    fit_scope_id: str,
    generator_configuration_sha256: str,
    solver_implementation_sha256: str,
    target_retained_count: int,
    source_stream_world_count: int,
    execution_mode: str = RELEASE_EXECUTION_MODE,
    termination_reason: str,
    exhaustion_proof_identity: Mapping[str, object] | None,
    occurrences: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the complete, position- and termination-bound generator stream."""
    normalized = _normalize_hard_control_occurrences(occurrences)
    target = _exact_int(
        target_retained_count, label="target_retained_count", minimum=1
    )
    source_worlds = _exact_int(
        source_stream_world_count, label="source_stream_world_count", minimum=1
    )
    mode = _execution_mode(execution_mode)
    computed_ceiling, ceiling = _hard230_ceiling_law(
        target_retained_count=target,
        source_stream_world_count=source_worlds,
        execution_mode=mode,
    )
    if len(normalized) > ceiling:
        _fail("complete generator stream exceeds its frozen effective ceiling")
    reason = _nonempty_string(termination_reason, label="termination_reason")
    occurrence_hash = batch.canonical_sha256(normalized)
    seen_rosters: set[str] = set()
    target_position: int | None = None
    for position, row in enumerate(normalized):
        roster_hash = row["roster_sha256"]
        if roster_hash is not None:
            seen_rosters.add(str(roster_hash))
            if len(seen_rosters) == target:
                target_position = position + 1
                break
    if reason == "effective-ceiling-reached":
        if (
            len(normalized) != ceiling
            or target_position is not None
            or exhaustion_proof_identity is not None
        ):
            _fail(
                "ceiling termination requires exact public ceiling count, an "
                "unreached paired target, and no exhaustion proof"
            )
    elif reason == "paired-target-reached":
        if (
            target_position != len(normalized)
            or exhaustion_proof_identity is not None
        ):
            _fail(
                "paired-target stream must stop exactly at the first unique-roster "
                "target and may not claim exhaustion"
            )
    elif reason == "generator-exhausted-before-ceiling":
        _fail(
            "generator exhaustion before the frozen ceiling is unsupported by the "
            "public v1 contiguous-world-stream law"
        )
    else:
        _fail("complete generator stream termination reason differs")
    body = {
        "schema_version": HARD230_CONTROL_STREAM_SCHEMA,
        "stream_id": _nonempty_string(stream_id, label="stream_id"),
        "candidate_origin_id": _nonempty_string(
            candidate_origin_id, label="candidate_origin_id"
        ),
        "fit_scope_id": _nonempty_string(fit_scope_id, label="fit_scope_id"),
        "execution_mode": mode,
        "hard230_public_contract_sha256": HARD230_PUBLIC_CONTRACT_SHA256,
        "generator_configuration_sha256": _sha256(
            generator_configuration_sha256, label="generator_configuration_sha256"
        ),
        "solver_implementation_sha256": _sha256(
            solver_implementation_sha256, label="solver_implementation_sha256"
        ),
        "target_retained_count": target,
        "source_stream_world_count": source_worlds,
        "minimum_solver_call_ceiling": HARD230_MINIMUM_SOLVER_CALL_CEILING,
        "solver_calls_per_target": HARD230_SOLVER_CALLS_PER_TARGET,
        "maximum_solver_call_ceiling": HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        "computed_solver_call_ceiling": computed_ceiling,
        "effective_solver_call_ceiling": ceiling,
        "occurrence_count": len(normalized),
        "stream_positions": list(range(len(normalized))),
        "occurrence_membership_sha256": occurrence_hash,
        "termination_reason": reason,
        "generator_exhausted": False,
        "exhaustion_proof_identity": None,
    }
    _exact_keys(body, _HARD_CONTROL_STREAM_KEYS, label="hard-control stream manifest")
    return body


def build_hard230_score_blind_control_receipt_v1(
    *,
    slate_id: str,
    candidate_origin_id: str,
    fit_scope_id: str,
    heldout_block_id: str,
    training_block_ids: Sequence[str],
    source_member_sha256: str,
    score_block_ids: Sequence[str],
    score_block_identities_sha256: str,
    player_registry_sha256: str,
    player_score_matrix_sha256: str,
    ordered_generator_stream_manifest: Mapping[str, object],
    ordered_generator_stream_manifest_identity: Mapping[str, object],
    generator_configuration_sha256: str,
    solver_implementation_sha256: str,
    paired_target_identity: Mapping[str, object],
    target_retained_count: int,
    source_stream_world_count: int,
    execution_mode: str = RELEASE_EXECUTION_MODE,
    occurrences: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Replay the exact score-blind stream prefix used as the hard-230 control."""
    implementation = frozen_generation_companion_control_implementation_v1()
    heldout, training = _canonical_fold_scope(
        heldout_block_id=heldout_block_id,
        training_block_ids=training_block_ids,
    )
    origin = _nonempty_string(candidate_origin_id, label="candidate_origin_id")
    if origin not in K5_ORIGINS or origin == heldout:
        _fail("hard-control candidate origin must be a non-heldout K5 origin")
    raw_score_blocks = _sequence(score_block_ids, label="score_block_ids")
    canonical_score_blocks = [
        _nonempty_string(value, label="score_block_id")
        for value in raw_score_blocks
    ]
    if canonical_score_blocks != training:
        _fail("score_block_ids must equal the exact fit-block order")
    target = _exact_int(
        target_retained_count, label="target_retained_count", minimum=1
    )
    if target > 10_000:
        _fail("target_retained_count exceeds the frozen solver-call ceiling")
    mode = _execution_mode(execution_mode)
    source_worlds = _exact_int(
        source_stream_world_count, label="source_stream_world_count", minimum=1
    )
    computed_ceiling, effective_ceiling = _hard230_ceiling_law(
        target_retained_count=target,
        source_stream_world_count=source_worlds,
        execution_mode=mode,
    )
    normalized_occurrences = _normalize_hard_control_occurrences(occurrences)
    stream = dict(_mapping(
        ordered_generator_stream_manifest,
        label="ordered_generator_stream_manifest",
    ))
    _exact_keys(stream, _HARD_CONTROL_STREAM_KEYS, label="hard-control stream manifest")
    expected_stream = build_hard230_control_stream_manifest_v1(
        stream_id=str(stream.get("stream_id")),
        candidate_origin_id=origin,
        fit_scope_id=str(fit_scope_id),
        generator_configuration_sha256=generator_configuration_sha256,
        solver_implementation_sha256=solver_implementation_sha256,
        target_retained_count=target,
        source_stream_world_count=source_worlds,
        execution_mode=mode,
        termination_reason=str(stream.get("termination_reason")),
        exhaustion_proof_identity=stream.get("exhaustion_proof_identity"),  # type: ignore[arg-type]
        occurrences=occurrences,
    )
    if batch.canonical_json_bytes(stream) != batch.canonical_json_bytes(expected_stream):
        _fail("complete ordered generator stream manifest differs")
    if stream["effective_solver_call_ceiling"] != effective_ceiling:
        _fail("stream effective ceiling differs from the public hard-230 law")
    stream_identity = _validate_json_identity(
        stream,
        ordered_generator_stream_manifest_identity,
        label="ordered generator stream manifest identity",
    )
    retained_rosters: list[dict[str, object]] = []
    seen_rosters: set[str] = set()
    consumed_count = len(normalized_occurrences)
    for ordinal, row in enumerate(normalized_occurrences):
        roster_hash = row["roster_sha256"]
        if roster_hash is not None and roster_hash not in seen_rosters:
            seen_rosters.add(str(roster_hash))
            retained_rosters.append({
                "lineup_id": row["lineup_id"],
                "roster_player_ids": row["roster_player_ids"],
                "roster_sha256": roster_hash,
            })
            if len(retained_rosters) == target:
                consumed_count = ordinal + 1
                break
    retained_count = len(retained_rosters)
    termination_reason_value = str(stream["termination_reason"])
    if retained_count == target:
        completion_status = "complete"
        if termination_reason_value != "paired-target-reached":
            _fail("completed control must use exact paired-target termination")
    elif termination_reason_value == "effective-ceiling-reached":
        completion_status = "mechanical-infeasibility-effective-ceiling-reached"
    else:
        _fail("under-target control must consume the exact public effective ceiling")
    body: dict[str, object] = {
        "schema_version": HARD230_CONTROL_RECEIPT_SCHEMA,
        "control_id": HARD230_CONTROL_ID,
        "implementation_id": CONTROL_IMPLEMENTATION_ID,
        "implementation_sha256": implementation["implementation_sha256"],
        "slate_id": _nonempty_string(slate_id, label="slate_id"),
        "candidate_origin_id": origin,
        "fit_scope_id": _nonempty_string(fit_scope_id, label="fit_scope_id"),
        "heldout_block_id": heldout,
        "training_block_ids": training,
        "execution_mode": mode,
        "hard230_public_contract_sha256": HARD230_PUBLIC_CONTRACT_SHA256,
        "source_member_sha256": _sha256(source_member_sha256, label="source_member_sha256"),
        "score_block_ids": canonical_score_blocks,
        "score_block_identities_sha256": _sha256(
            score_block_identities_sha256, label="score_block_identities_sha256"
        ),
        "player_registry_sha256": _sha256(player_registry_sha256, label="player_registry_sha256"),
        "player_score_matrix_sha256": _sha256(
            player_score_matrix_sha256, label="player_score_matrix_sha256"
        ),
        "ordered_generator_stream_manifest": stream,
        "ordered_generator_stream_manifest_identity": stream_identity,
        "target_retained_count": target,
        "source_stream_world_count": source_worlds,
        "computed_solver_call_ceiling": computed_ceiling,
        "effective_solver_call_ceiling": stream["effective_solver_call_ceiling"],
        "stream_termination_reason": termination_reason_value,
        "stream_exhaustion_proof_identity": stream["exhaustion_proof_identity"],
        "generator_configuration_sha256": _sha256(
            generator_configuration_sha256, label="generator_configuration_sha256"
        ),
        "solver_implementation_sha256": _sha256(
            solver_implementation_sha256, label="solver_implementation_sha256"
        ),
        "paired_target_identity": _object_identity(
            paired_target_identity, label="paired_target_identity"
        ),
        "occurrences": normalized_occurrences,
        "occurrence_ledger_sha256": batch.canonical_sha256(normalized_occurrences),
        "consumed_occurrence_count": consumed_count,
        "retained_rosters": retained_rosters,
        "retained_rosters_sha256": batch.canonical_sha256(retained_rosters),
        "retained_count": retained_count,
        "shortfall_count": target - retained_count,
        "completion_status": completion_status,
        "score_or_value_read": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "control_receipt_sha256")


def validate_hard230_score_blind_control_receipt_v1(
    value: object, **replay_inputs: object
) -> dict[str, object]:
    item = dict(_mapping(value, label="hard-control receipt"))
    _exact_keys(item, _HARD_CONTROL_RECEIPT_KEYS, label="hard-control receipt")
    _false_authorities(item, label="hard-control receipt")
    _validate_self_hash(
        item, field="control_receipt_sha256", label="hard-control receipt"
    )
    expected = build_hard230_score_blind_control_receipt_v1(  # type: ignore[arg-type]
        **replay_inputs
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("hard-control receipt differs from canonical replay")
    return expected


_DISCOVERY_CONTROL_SOLVE_KEYS: Final = frozenset({
    "schedule_position",
    "block_id",
    "world_index",
    "solver_status",
    "lineup_id",
    "roster_player_ids",
    "roster_sha256",
    "legality_passed",
    "solver_proof_identity",
    "legality_proof_identity",
})
_DISCOVERY_CONTROL_RECEIPT_KEYS: Final = frozenset({
    "schema_version",
    "control_id",
    "implementation_id",
    "implementation_sha256",
    "slate_id",
    "fit_scope_id",
    "heldout_block_id",
    "training_block_ids",
    "execution_mode",
    "source_member_identity",
    "ordinary_r_block_identities",
    "ordinary_r_block_identities_sha256",
    "player_registry",
    "player_registry_sha256",
    "ordinary_r_score_matrix_identity",
    "ordinary_r_score_matrix_sha256",
    "ordinary_r_matrix_encoding",
    "worlds_per_block",
    "visits_per_block",
    "solver_implementation_sha256",
    "visit_schedule",
    "visit_schedule_sha256",
    "solve_results",
    "solve_results_sha256",
    "visit_count",
    "solve_count",
    "status_counts",
    "unique_rosters",
    "unique_rosters_sha256",
    "unique_yield_count",
    "duplicate_optimal_count",
    "uses_heldout_scores",
    "uses_atlas_or_realized_values",
    *_FALSE_AUTHORITY_FIELDS,
    "control_receipt_sha256",
})


def build_incumbent_equal_visit_control_receipt_v1(
    *,
    slate_id: str,
    fit_scope_id: str,
    heldout_block_id: str,
    training_block_ids: Sequence[str],
    source_member_identity: Mapping[str, object],
    ordinary_r_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    ordinary_r_player_score_matrix: np.ndarray,
    ordinary_r_score_matrix_identity: Mapping[str, object],
    worlds_per_block: int,
    visits_per_block: int,
    solver_implementation_sha256: str,
    solve_results: Sequence[Mapping[str, object]],
    execution_mode: str = RELEASE_EXECUTION_MODE,
) -> dict[str, object]:
    """Replay the incumbent blockwise top-total equal-visit control schedule."""
    implementation = frozen_generation_companion_control_implementation_v1()
    heldout, training = _canonical_fold_scope(
        heldout_block_id=heldout_block_id,
        training_block_ids=training_block_ids,
    )
    mode = _execution_mode(execution_mode)
    worlds = _exact_int(worlds_per_block, label="worlds_per_block", minimum=1)
    if worlds > WORLDS_PER_BLOCK:
        _fail("worlds_per_block exceeds the frozen ordinary-R block width")
    if mode == RELEASE_EXECUTION_MODE and worlds != WORLDS_PER_BLOCK:
        _fail("release discovery control requires exactly 10,000 worlds per block")
    visits = _exact_int(visits_per_block, label="visits_per_block", minimum=1)
    if visits > worlds:
        _fail("visits_per_block exceeds the retained block width")
    try:
        context = additions._prepare_score_context(  # noqa: SLF001
            source_member_identity=source_member_identity,
            score_block_identities=ordinary_r_block_identities,
            player_registry=player_registry,
            score_matrix=ordinary_r_player_score_matrix,
            score_matrix_identity=ordinary_r_score_matrix_identity,
            expected_block_ids=EVALUATION_BLOCKS,
            worlds_per_block=worlds,
        )
    except Exception as exc:
        raise CorpusExtremeTailGenerationCompanionManifestError(
            "ordinary-R matrix/source identity differs from the shared all-five "
            "little-endian int64 milli-DK law"
        ) from exc
    matrix = context["matrix"]
    canonical_players = list(context["player_registry"])
    canonical_player_ids = [str(row["id"]) for row in canonical_players]
    player_id_set = set(canonical_player_ids)
    schedule: list[dict[str, object]] = []
    for block_id in training:
        block_ordinal = EVALUATION_BLOCKS.index(block_id)
        start = block_ordinal * worlds
        stop = start + worlds
        totals = matrix[:, start:stop].sum(axis=0, dtype=np.int64)
        indices = np.arange(worlds, dtype=np.int64)
        ranked = np.lexsort((indices, -totals))[:visits]
        schedule.extend({
            "schedule_position": len(schedule),
            "block_id": block_id,
            "world_index": int(world_index),
        } for world_index in ranked)
    raw_solves = _sequence(solve_results, label="solve_results")
    if len(raw_solves) != len(schedule):
        _fail("solve_results must contain exactly one result per scheduled visit")
    normalized_solves: list[dict[str, object]] = []
    unique_rosters: list[dict[str, object]] = []
    seen_rosters: set[str] = set()
    duplicate_count = 0
    status_counts = {"optimal": 0, "infeasible": 0, "error": 0}
    for position, (scheduled, raw) in enumerate(zip(schedule, raw_solves, strict=True)):
        row = _mapping(raw, label=f"solve_result[{position}]")
        _exact_keys(row, _DISCOVERY_CONTROL_SOLVE_KEYS, label=f"solve_result[{position}]")
        if any(row.get(key) != scheduled[key] for key in scheduled):
            _fail("solve result does not match the derived visit schedule")
        status = _nonempty_string(row.get("solver_status"), label="solver_status")
        if status not in status_counts:
            _fail("discovery-control solver_status differs")
        status_counts[status] += 1
        solver_proof = _object_identity(
            row.get("solver_proof_identity"), label="solver_proof_identity"
        )
        if status == "optimal":
            lineup_id = _nonempty_string(row.get("lineup_id"), label="lineup_id")
            roster, roster_hash = _canonical_roster_identity(
                row.get("roster_player_ids"),
                row.get("roster_sha256"),
                label=f"solve_result[{position}]",
            )
            if not set(roster).issubset(player_id_set):
                _fail("discovery-control roster contains an unregistered player")
            if row.get("legality_passed") is not True:
                _fail("optimal discovery-control result must pass legality")
            legality_proof: dict[str, object] | None = _object_identity(
                row.get("legality_proof_identity"), label="legality_proof_identity"
            )
            if roster_hash in seen_rosters:
                duplicate_count += 1
            else:
                seen_rosters.add(roster_hash)
                unique_rosters.append({
                    "lineup_id": lineup_id,
                    "roster_player_ids": roster,
                    "roster_sha256": roster_hash,
                })
        else:
            if any(
                row.get(field) is not None
                for field in (
                    "lineup_id",
                    "roster_player_ids",
                    "roster_sha256",
                    "legality_passed",
                    "legality_proof_identity",
                )
            ):
                _fail("non-optimal discovery-control result must have null lineup fields")
            lineup_id = None
            roster = None
            roster_hash = None
            legality_proof = None
        normalized_solves.append({
            **scheduled,
            "solver_status": status,
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "roster_sha256": roster_hash,
            "legality_passed": True if status == "optimal" else None,
            "solver_proof_identity": solver_proof,
            "legality_proof_identity": legality_proof,
        })
    body: dict[str, object] = {
        "schema_version": DISCOVERY_CONTROL_RECEIPT_SCHEMA,
        "control_id": DISCOVERY_CONTROL_ID,
        "implementation_id": CONTROL_IMPLEMENTATION_ID,
        "implementation_sha256": implementation["implementation_sha256"],
        "slate_id": _nonempty_string(slate_id, label="slate_id"),
        "fit_scope_id": _nonempty_string(fit_scope_id, label="fit_scope_id"),
        "heldout_block_id": heldout,
        "training_block_ids": training,
        "execution_mode": mode,
        "source_member_identity": context["source_member"],
        "ordinary_r_block_identities": list(context["block_identities"]),
        "ordinary_r_block_identities_sha256": context[
            "block_identities_sha256"
        ],
        "player_registry": canonical_players,
        "player_registry_sha256": context["player_registry_sha256"],
        "ordinary_r_score_matrix_identity": context["matrix_identity"],
        "ordinary_r_score_matrix_sha256": context["matrix_sha256"],
        "ordinary_r_matrix_encoding": additions.SCORE_MATRIX_ENCODING,
        "worlds_per_block": worlds,
        "visits_per_block": visits,
        "solver_implementation_sha256": _sha256(
            solver_implementation_sha256, label="solver_implementation_sha256"
        ),
        "visit_schedule": schedule,
        "visit_schedule_sha256": batch.canonical_sha256(schedule),
        "solve_results": normalized_solves,
        "solve_results_sha256": batch.canonical_sha256(normalized_solves),
        "visit_count": len(schedule),
        "solve_count": len(normalized_solves),
        "status_counts": status_counts,
        "unique_rosters": unique_rosters,
        "unique_rosters_sha256": batch.canonical_sha256(unique_rosters),
        "unique_yield_count": len(unique_rosters),
        "duplicate_optimal_count": duplicate_count,
        "uses_heldout_scores": False,
        "uses_atlas_or_realized_values": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "control_receipt_sha256")


def validate_incumbent_equal_visit_control_receipt_v1(
    value: object, **replay_inputs: object
) -> dict[str, object]:
    item = dict(_mapping(value, label="discovery-control receipt"))
    _exact_keys(
        item, _DISCOVERY_CONTROL_RECEIPT_KEYS, label="discovery-control receipt"
    )
    _false_authorities(item, label="discovery-control receipt")
    _validate_self_hash(
        item, field="control_receipt_sha256", label="discovery-control receipt"
    )
    expected = build_incumbent_equal_visit_control_receipt_v1(  # type: ignore[arg-type]
        **replay_inputs
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("discovery-control receipt differs from canonical replay")
    return expected


def _hard230_control_body() -> dict[str, object]:
    return {
        "schema_version": "hard-230-score-blind-paired-control/v1",
        "control_id": HARD230_CONTROL_ID,
        "challenger_strategy_id": additions.HARD230_STRATEGY_ID,
        "control_population_id": "P0-incumbent-native",
        "implementation_id": CONTROL_IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_CONTROL_IMPLEMENTATION_SHA256,
        "canonical_builder": "build_hard230_score_blind_control_receipt_v1",
        "canonical_validator": (
            "validate_hard230_score_blind_control_receipt_v1"
        ),
        "receipt_schema": HARD230_CONTROL_RECEIPT_SCHEMA,
        "complete_stream_schema": HARD230_CONTROL_STREAM_SCHEMA,
        "complete_stream_builder": "build_hard230_control_stream_manifest_v1",
        "candidate_origin_mask_id": "K5",
        "candidate_origin_ids": list(K5_ORIGINS),
        "generator_law_id": additions.HARD230_GENERATOR_LAW_ID,
        "stream_pairing_law": (
            "same-generation-pinned-complete-ordered-generator-stream-source-"
            "scope-public-contract-derived-effective-ceiling-and-termination"
        ),
        "admission_law": (
            "retain-first-new-legal-unique-rosters-without-score-or-value-read"
        ),
        "target_law": (
            "exact-registered-p0-native-retained-count-for-slate-origin-fit-scope"
        ),
        "matching_dimensions": [
            "slate",
            "candidate-origin",
            "heldout-and-training-block-scope",
            "source-member",
            "score-block-identities",
            "player-registry",
            "score-matrix",
            "retained-count",
            "release-or-test-fixture-execution-mode",
            "source-stream-world-count",
        ],
        "control_receipt_requires_generation_pinned_identity": True,
        "control_receipt_content_hash_must_equal_object_hash": True,
        "entire_occurrence_ledger_and_every-proof-identity-bound": True,
        "early-prefix-exhaustion-claim-forbidden": True,
        "under-target-termination-law": (
            "exact-public-contract-derived-effective-ceiling-count-only"
        ),
        "public_ceiling_law": {
            "minimum_solver_call_ceiling": HARD230_MINIMUM_SOLVER_CALL_CEILING,
            "solver_calls_per_target": HARD230_SOLVER_CALLS_PER_TARGET,
            "maximum_solver_call_ceiling": HARD230_MAXIMUM_SOLVER_CALL_CEILING,
            "effective_solver_call_ceiling": (
                "min(source-stream-world-count,min(10000,max(200,20*target)))"
            ),
        },
        "release_source_stream_world_count": WORLDS_PER_BLOCK,
        "fixture_mode": FIXTURE_EXECUTION_MODE,
        "fixture_receipt_has_release_authority": False,
        "generator_exhaustion_before_ceiling_supported": False,
        "uniqueness_identity": "canonical-nine-player-roster-sha256-not-lineup-id",
        "canonical_replay_required_from_exact_builder_inputs": True,
        "admission_reads_simulated_score_or_value": False,
        "uses_realized_outcomes": False,
        "exact_shortfall_is_a_mechanical_failure": True,
    }


def _discovery_control_body() -> dict[str, object]:
    return {
        "schema_version": "game-regime-incumbent-paired-control/v1",
        "control_id": DISCOVERY_CONTROL_ID,
        "challenger_strategy_id": additions.DISCOVERY_STRATEGY_ID,
        "control_population_id": DISCOVERY_CONTROL_POPULATION_ID,
        "implementation_id": CONTROL_IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_CONTROL_IMPLEMENTATION_SHA256,
        "canonical_builder": (
            "build_incumbent_equal_visit_control_receipt_v1"
        ),
        "canonical_validator": (
            "validate_incumbent_equal_visit_control_receipt_v1"
        ),
        "receipt_schema": DISCOVERY_CONTROL_RECEIPT_SCHEMA,
        "candidate_origin_mask_id": "K5",
        "candidate_origin_ids": list(K5_ORIGINS),
        "schedule_law": "existing-incumbent-top-total-world-schedule-v1",
        "neutrality_law": (
            "no-game-regime-label-anchor-game-queue-or-lineup-ceiling-ranking"
        ),
        "budget_law": "exact-same-scope-visit-and-solve-count",
        "candidate_law": "one-reported-incumbent-legal-optimum-per-visit",
        "matching_dimensions": [
            "slate",
            "heldout-and-training-block-scope",
            "source-member",
            "ordinary-r-block-identities",
            "player-registry",
            "score-matrix",
            "solver-implementation",
            "visit-count",
            "solve-count",
            "release-or-test-fixture-execution-mode",
        ],
        "unique_yield_is_reported_not_force-matched": True,
        "control_receipt_requires_generation_pinned_identity": True,
        "control_receipt_content_hash_must_equal_object_hash": True,
        "ordinary_r_matrix_scope": "one-shared-all-five-R0-through-R4-matrix",
        "release_worlds_per_block": WORLDS_PER_BLOCK,
        "fixture_mode": FIXTURE_EXECUTION_MODE,
        "fixture_receipt_has_release_authority": False,
        "ordinary_r_matrix_encoding": additions.SCORE_MATRIX_ENCODING,
        "ordinary_r_matrix_hash_function": (
            "corpus_extreme_tail_generation_additions."
            "canonical_score_matrix_sha256_v1"
        ),
        "fit_matrix_law": (
            "slice-four-canonical-training-blocks-from-the-bound-all-five-matrix"
        ),
        "matrix_artifact_and_derivation-proof-identities-bound": True,
        "derived_schedule_and-every-solver-proof-identity-bound": True,
        "uniqueness_identity": "canonical-nine-player-roster-sha256-not-lineup-id",
        "canonical_replay_required_from_exact-builder-inputs": True,
        "uses_atlas_world_ranking": False,
        "uses_realized_outcomes": False,
    }


def _paired_control_registry() -> list[dict[str, object]]:
    implementation = frozen_generation_companion_control_implementation_v1()
    hard = _hard230_control_body()
    discovery = _discovery_control_body()
    return [
        {
            "control_ordinal": 0,
            "control_id": HARD230_CONTROL_ID,
            "challenger_strategy_id": additions.HARD230_STRATEGY_ID,
            "implementation_contract": implementation,
            "implementation_sha256": implementation["implementation_sha256"],
            "control_contract": hard,
            "control_contract_sha256": batch.canonical_sha256(hard),
        },
        {
            "control_ordinal": 1,
            "control_id": DISCOVERY_CONTROL_ID,
            "challenger_strategy_id": additions.DISCOVERY_STRATEGY_ID,
            "implementation_contract": implementation,
            "implementation_sha256": implementation["implementation_sha256"],
            "control_contract": discovery,
            "control_contract_sha256": batch.canonical_sha256(discovery),
        },
    ]


def _ordinary_r_matrix_law() -> dict[str, object]:
    body = {
        "law_id": "generation-companion-ordinary-r-matrix-lineage/v1",
        "evaluation_blocks": list(EVALUATION_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "world_count_per_slate": len(EVALUATION_BLOCKS) * WORLDS_PER_BLOCK,
        "world_order_law": "five-complete-block-major-ordinary-r-worlds",
        "ordinary_unweighted_r_worlds": True,
        "source_blocks_are_exact_factorial_source_catalog_members": True,
        "player_matrix_schema": "generation-ordinary-r-player-matrix/v1",
        "player_matrix_encoding": (
            "row-major-little-endian-int64-milli-dk/v1"
        ),
        "player_matrix_role": (
            "generation-feature-and-permitted-training-score-derivation"
        ),
        "companion_roster_matrix_schema": (
            "generation-companion-global-roster-ordinary-r-matrix/v1"
        ),
        "companion_union_law": (
            "every-unique-paired-control-or-challenger-generated-roster"
        ),
        "score_each_companion_union_roster_once": True,
        "candidate_generation_shared_across_r194_and_t230": True,
        "selector_fit_uses_only_four-training-block-columns": True,
        "heldout_evaluation_uses_only_exact-heldout-block": True,
        "final_selector_fit_uses_all-five-blocks": True,
        "hard230_retention_uses_only-public-contract-permitted-blocks": True,
        "discovery_features_use_only-fold-training-blocks": True,
        "separately_recomputed_retrieval_matrices_forbidden": True,
        "tail_biased_frequency_is_not_target_probability": True,
        "heldout_or_realized_generation_input_forbidden": True,
        "core_evaluation_contract_sha256": CORE_EVALUATION_CONTRACT_SHA256,
        "core_shared_artifact_contract_sha256": (
            CORE_SHARED_ARTIFACT_CONTRACT_SHA256
        ),
    }
    body["ordinary_r_matrix_law_sha256"] = batch.canonical_sha256(body)
    return body


def _generation_cross_fit_law() -> dict[str, object]:
    folds = []
    for heldout in EVALUATION_BLOCKS:
        training = [block for block in EVALUATION_BLOCKS if block != heldout]
        folds.append({
            "heldout_block_id": heldout,
            "training_block_ids": training,
            "hard230_eligible_candidate_origin_ids": [
                origin for origin in K5_ORIGINS if origin != heldout
            ],
            "hard230_permitted_score_block_ids_by_origin": {
                origin: training
                for origin in K5_ORIGINS
                if origin != heldout
            },
            "discovery_schedule_scope_id": f"holdout-{heldout}",
            "discovery_schedule_uses_training_blocks_only": True,
        })
    body = {
        "law_id": "generation-companion-k5-candidate-cross-fit/v1",
        "candidate_origin_mask_id": "K5",
        "candidate_origin_ids": list(K5_ORIGINS),
        "folds": folds,
        "fold_count_per_slate": 5,
        "hard230_fold_origin_receipt_count_per_slate": 20,
        "hard230_final_fit_origin_ids": list(K5_ORIGINS),
        "hard230_final_fit_origin_receipt_count_per_slate": 5,
        "hard230_total_receipt_count_per_slate": 25,
        "discovery_fold_schedule_count_per_slate": 5,
        "discovery_final_population_law": (
            "canonical-roster-union-of-all-five-cross-fit-schedule-populations"
        ),
        "additional_unregistered_discovery_final_schedule_forbidden": True,
        "fold_population_excludes_heldout_schedule-and-origin": True,
        "final_selector_fit_uses_all-five-ordinary-r-blocks": True,
        "heldout_origin_occurrences_and_scores_forbidden": True,
        "realized_outcomes_forbidden": True,
        "core_candidate_cross_fit_contract_sha256": (
            CORE_CROSS_FIT_CONTRACT_SHA256
        ),
    }
    body["generation_cross_fit_law_sha256"] = batch.canonical_sha256(body)
    return body


def _generation_registry(
    *, hard_contract: Mapping[str, object], discovery_contract: Mapping[str, object]
) -> list[dict[str, object]]:
    controls = {row["control_id"]: row for row in _paired_control_registry()}
    return [
        {
            "generation_ordinal": 0,
            "strategy_id": additions.HARD230_STRATEGY_ID,
            "population_id": HARD230_POPULATION_ID,
            "strategy_sha256": HARD230_STRATEGY_SHA256,
            "implementation_sha256": HARD230_IMPLEMENTATION_SHA256,
            "public_contract_sha256": HARD230_PUBLIC_CONTRACT_SHA256,
            "public_contract": dict(hard_contract),
            "paired_control_id": HARD230_CONTROL_ID,
            "paired_control_contract_sha256": controls[HARD230_CONTROL_ID][
                "control_contract_sha256"
            ],
            "paired_control_implementation_sha256": controls[HARD230_CONTROL_ID][
                "implementation_sha256"
            ],
            "required_control_builder": (
                "build_hard230_score_blind_control_receipt_v1"
            ),
            "required_control_validator": (
                "validate_hard230_score_blind_control_receipt_v1"
            ),
            "candidate_origin_mask_id": "K5",
            "execution_scope": (
                "every-53-slate-cross-fit-fold-origin-and-all-block-final-fit"
            ),
            "completion_law": (
                "exact-paired-retained-count-or-mechanical-infeasibility-receipt"
            ),
            "required_public_builder": (
                "build_hard230_generation_replenishment_v1"
            ),
            "required_public_validator": (
                "validate_hard230_generation_replenishment_v1"
            ),
            "required_execution_lineage_fields": [
                "source-member-object-identity",
                "score-block-object-identities",
                "player-registry-sha256",
                "player-score-matrix-object-and-derivation-proof-identities",
                "generator-configuration-sha256",
                "solver-implementation-sha256",
                "release-execution-mode-and-exact-10000-world-source-stream",
                "public-minimum-200-20x-target-maximum-10000-ceiling",
                "ordered-stream-manifest-object-identity",
                "every-solver-and-legality-proof-object-identity",
                "paired-control-receipt-object-identity",
            ],
            "standalone_evidence_role": "diagnostic-nonpublication-only",
        },
        {
            "generation_ordinal": 1,
            "strategy_id": additions.DISCOVERY_STRATEGY_ID,
            "population_id": DISCOVERY_POPULATION_ID,
            "strategy_sha256": DISCOVERY_STRATEGY_SHA256,
            "implementation_sha256": DISCOVERY_IMPLEMENTATION_SHA256,
            "public_contract_sha256": DISCOVERY_PUBLIC_CONTRACT_SHA256,
            "public_contract": dict(discovery_contract),
            "paired_control_id": DISCOVERY_CONTROL_ID,
            "paired_control_contract_sha256": controls[DISCOVERY_CONTROL_ID][
                "control_contract_sha256"
            ],
            "paired_control_implementation_sha256": controls[DISCOVERY_CONTROL_ID][
                "implementation_sha256"
            ],
            "required_control_builder": (
                "build_incumbent_equal_visit_control_receipt_v1"
            ),
            "required_control_validator": (
                "validate_incumbent_equal_visit_control_receipt_v1"
            ),
            "candidate_origin_mask_id": "K5",
            "execution_scope": "every-53-slate-five-fold-ordinary-r-schedule",
            "completion_law": (
                "exact-control-visit-solve-budget-or-mechanical-infeasibility-receipt"
            ),
            "required_public_builder": (
                "build_game_regime_tail_discovery_accounting_v1"
            ),
            "required_public_validator": (
                "validate_game_regime_tail_discovery_accounting_v1"
            ),
            "required_execution_lineage_fields": [
                "source-member-object-identity",
                "ordinary-r-block-object-identities",
                "player-registry-sha256",
                "player-score-matrix-object-and-derivation-proof-identities",
                "release-execution-mode-and-exact-10000-worlds-per-block",
                "paired-control-budget-receipt-object-identity",
                "solver-implementation-sha256",
                "every-schedule-item-and-solver-proof-object-identity",
                "complete-accounting-and-heldout-evaluation-receipts",
            ],
            "standalone_evidence_role": "diagnostic-nonpublication-only",
        },
    ]


def _retrieval_dependency_registry(
    core_manifest: Mapping[str, object],
) -> list[dict[str, object]]:
    retrieval_contract = _mapping(
        core_manifest.get("retrieval_contract"), label="core retrieval contract"
    )
    catalog = _sequence(
        retrieval_contract.get("catalog"), label="core retrieval catalog"
    )
    by_id = {
        str(_mapping(row, label="core retrieval row").get("retrieval_id")): row
        for row in catalog
    }
    expected = (
        (R194_ID, 0, R194_STRATEGY_SHA256, R194_IMPLEMENTATION_SHA256),
        (T230_ID, 5, T230_STRATEGY_SHA256, T230_IMPLEMENTATION_SHA256),
    )
    rows: list[dict[str, object]] = []
    for dependency_ordinal, (
        retrieval_id,
        core_ordinal,
        strategy_hash,
        implementation_hash,
    ) in enumerate(expected):
        raw = _mapping(by_id.get(retrieval_id), label=f"core {retrieval_id} row")
        if (
            raw.get("retrieval_ordinal") != core_ordinal
            or raw.get("execution_kind") != "selector"
            or raw.get("strategy_contract_sha256") != strategy_hash
            or raw.get("implementation_contract_sha256") != implementation_hash
        ):
            _fail(f"core {retrieval_id} dependency contract differs")
        rows.append({
            "dependency_ordinal": dependency_ordinal,
            "retrieval_id": retrieval_id,
            "core_retrieval_ordinal": core_ordinal,
            "strategy_contract_sha256": strategy_hash,
            "implementation_contract_sha256": implementation_hash,
            "core_retrieval_row": dict(raw),
        })
    return rows


def _stage_b_catalog_registry(
    *,
    core_manifest: Mapping[str, object],
    generation_registry: Sequence[Mapping[str, object]],
    controls: Sequence[Mapping[str, object]],
    retrievals: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    generation_by_id = {str(row["strategy_id"]): row for row in generation_registry}
    controls_by_id = {str(row["control_id"]): row for row in controls}
    retrieval_by_id = {str(row["retrieval_id"]): row for row in retrievals}
    core_cells = {
        str(_mapping(row, label="core factorial cell").get("cell_id")): dict(row)
        for row in _sequence(
            core_manifest.get("factorial_cell_registry"),
            label="core factorial cell registry",
        )
    }
    core_populations = {
        str(_mapping(row, label="core population").get("population_id")): dict(row)
        for row in _sequence(
            core_manifest.get("population_registry"),
            label="core population registry",
        )
    }
    p0_population = core_populations.get("P0-incumbent-native")
    if p0_population is None:
        _fail("core P0 population reference is absent")
    experiment_rows = (
        (
            "hard230",
            additions.HARD230_STRATEGY_ID,
            HARD230_CONTROL_ID,
            "P0-incumbent-native",
            HARD230_POPULATION_ID,
        ),
        (
            "game-regime",
            additions.DISCOVERY_STRATEGY_ID,
            DISCOVERY_CONTROL_ID,
            DISCOVERY_CONTROL_POPULATION_ID,
            DISCOVERY_POPULATION_ID,
        ),
    )
    rows: list[dict[str, object]] = []
    for experiment_ordinal, (
        short_id,
        strategy_id,
        control_id,
        control_population_id,
        challenger_population_id,
    ) in enumerate(experiment_rows):
        generation = generation_by_id[strategy_id]
        control = controls_by_id[control_id]
        for local_ordinal, (stage_cell, arm, retrieval_id) in enumerate((
            ("A", "control", R194_ID),
            ("B", "challenger", R194_ID),
            ("C", "control", T230_ID),
            ("D", "challenger", T230_ID),
        )):
            retrieval = retrieval_by_id[retrieval_id]
            population_id = (
                control_population_id if arm == "control" else challenger_population_id
            )
            contract_hash = (
                control["control_contract_sha256"]
                if arm == "control"
                else generation["public_contract_sha256"]
            )
            ordinal = experiment_ordinal * 4 + local_ordinal
            is_hard_core_reference = experiment_ordinal == 0 and arm == "control"
            core_cell_id = None
            core_cell = None
            core_cell_hash = None
            core_population_hash = None
            if is_hard_core_reference:
                core_cell_id = (
                    "H01-P0-K5-R194" if retrieval_id == R194_ID
                    else "H02-P0-K5-T230"
                )
                core_cell = core_cells.get(core_cell_id)
                if (
                    core_cell is None
                    or core_cell.get("population_id") != "P0-incumbent-native"
                    or core_cell.get("candidate_origin_mask_id") != "K5"
                    or core_cell.get("retrieval_id") != retrieval_id
                    or core_cell.get("entry_budgets") != list(ENTRY_BUDGETS)
                ):
                    _fail("hard-control core factorial reference differs")
                core_cell_hash = batch.canonical_sha256(core_cell)
                core_population_hash = batch.canonical_sha256(p0_population)
                contract_hash = core_population_hash
            rows.append({
                "catalog_entry_ordinal": ordinal,
                "catalog_entry_id": (
                    f"G{ordinal + 1:02d}-{short_id}-{stage_cell}-{retrieval_id}"
                ),
                "experiment_ordinal": experiment_ordinal,
                "generation_strategy_id": strategy_id,
                "stage_b_cell": stage_cell,
                "generation_arm": arm,
                "population_id": population_id,
                "generation_or_control_contract_sha256": contract_hash,
                "paired_control_id": control_id,
                "paired_control_contract_sha256": control[
                    "control_contract_sha256"
                ],
                "catalog_entry_kind": (
                    "core-factorial-reference"
                    if is_hard_core_reference
                    else "new-generation-selector-rank"
                ),
                "counts_as_new_rank": not is_hard_core_reference,
                "core_factorial_protocol_sha256": (
                    CORE_PROTOCOL_SHA256
                    if is_hard_core_reference else None
                ),
                "core_factorial_manifest_binding_law": (
                    "resolve-through-top-level-exact-core-factorial-manifest-"
                    "sha256-and-never-a-free-or-latest-alias"
                    if is_hard_core_reference else None
                ),
                "core_factorial_cell_registry_sha256": (
                    CORE_FACTORIAL_CELL_REGISTRY_SHA256
                    if is_hard_core_reference else None
                ),
                "core_factorial_cell_id": core_cell_id,
                "core_factorial_cell": core_cell,
                "core_factorial_cell_sha256": core_cell_hash,
                "core_population_contract_sha256": core_population_hash,
                "core_reference_reuse_law": (
                    "reuse-exact-preexisting-core-rank-and-4-14-80-prefix-books;"
                    "do-not-regenerate-do-not-recount"
                    if is_hard_core_reference else None
                ),
                "candidate_origin_mask_id": "K5",
                "retrieval_id": retrieval_id,
                "retrieval_strategy_contract_sha256": retrieval[
                    "strategy_contract_sha256"
                ],
                "retrieval_implementation_contract_sha256": retrieval[
                    "implementation_contract_sha256"
                ],
                "entry_budgets": list(ENTRY_BUDGETS),
                "ranking_depth": RANKING_DEPTH,
                "ranking_prefix_law": RANKING_PREFIX_LAW,
                "candidate_population_shared_between_retrieval_columns": True,
                "completion_law": (
                    "exact-core-cell-rank-and-books-already-complete"
                    if is_hard_core_reference
                    else "exact-4-14-80-final-books-or-one-bound-mechanical-"
                    "infeasibility-receipt"
                ),
                "simulated_effect_screening_forbidden": True,
                "pre_grade_inclusion_required": True,
            })
    return rows


def _aggregate_pre_grade_law() -> dict[str, object]:
    body = {
        "schema_version": PRE_GRADE_CATALOG_SCHEMA,
        "law_id": "one-immutable-aggregate-catalog-before-outcome-access/v1",
        "core_factorial_registry_remains_exactly_18_rows": True,
        "core_eight_primary_cells_remain_byte_unchanged": True,
        "generation_companion_stage_b_entry_count_per_slate": 8,
        "generation_companion_new_rank_count_if_all-feasible": (
            FACTORIAL_SLATE_COUNT * 6
        ),
        "generation_companion_new_exact_book_count_if_all-feasible": (
            FACTORIAL_SLATE_COUNT * 6 * len(ENTRY_BUDGETS)
        ),
        "core_reused_rank_count": FACTORIAL_SLATE_COUNT * 2,
        "core_reused_exact_book_count": (
            FACTORIAL_SLATE_COUNT * 2 * len(ENTRY_BUDGETS)
        ),
        "total_referenced_rank_count": FACTORIAL_SLATE_COUNT * 8,
        "total_referenced_exact_book_count": (
            FACTORIAL_SLATE_COUNT * 8 * len(ENTRY_BUDGETS)
        ),
        "core_references_must_not_be_executed_or_counted_as_new": True,
        "entry_budgets": list(ENTRY_BUDGETS),
        "feasible_entry_requires_all_exact_books": True,
        "mechanically_infeasible_entry_requires_bound_receipt": True,
        "missing_or_unaccepted_entry_may_not_be_silently_omitted": True,
        "simulated_effect_screening_before_inclusion_forbidden": True,
        "all_output_object_identities_freeze_before_grade_manifest": True,
        "other_complete_census_companion_fragments_still_required": True,
        "this_companion_is_not_the_final_complete_census_catalog": True,
        "separate_final_grade_manifest_required": True,
        "this_contract_opens_outcome_access": False,
        "this_contract_grants_publication_or_promotion_authority": False,
    }
    body["aggregate_pre_grade_law_sha256"] = batch.canonical_sha256(body)
    return body


def _prospective_k20_oi_shadow_binding(
    identity: Mapping[str, object],
) -> dict[str, object]:
    retained_identity = _object_identity(
        identity, label="prospective_k20_oi_shadow_identity"
    )
    body = {
        "schema_version": PROSPECTIVE_SHADOW_BINDING_SCHEMA,
        "shadow_id": PROSPECTIVE_K20_OI_SHADOW_ID,
        "frozen_spec_document": (
            "reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md"
        ),
        "treatment_entry_budget": 20,
        "portfolio_law": "frozen-CBWU-OI-v1-union-on-identical-R0-R4-books",
        "shadow_manifest_identity": retained_identity,
        "identity_dimensions": ["uri", "generation", "sha256", "bytes"],
        "historical_companion_may_modify_or_replace_shadow": False,
        "historical_k20_factorial_is_a_separate_identity": True,
        "latest-or-unversioned-object-read-forbidden": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "prospective_k20_oi_shadow_binding_sha256")


_OUTPUT_KEYS: Final = frozenset({
    "source_member_manifest_uri",
    "player_ordinary_r_matrix_uri",
    "companion_global_rosters_uri",
    "companion_occurrence_provenance_uri",
    "companion_ordinary_r_lineup_score_matrix_uri",
    "hard230_control_receipts_uri",
    "hard230_generation_receipts_uri",
    "discovery_control_receipts_uri",
    "discovery_schedule_accounting_uri",
    "selector_books_uri",
    "pre_grade_catalog_fragment_uri",
    "companion_acceptance_uri",
})


def _companion_output_prefix(core_output_prefix: str) -> str:
    return core_output_prefix + "generation-companion-v1/"


def _output_uris(
    *, companion_prefix: str, ordinal: int, slate_id: str
) -> dict[str, str]:
    prefix = f"{companion_prefix}slates/{ordinal:02d}-{slate_id}/"
    return {
        "source_member_manifest_uri": prefix + "source-member-v1.json",
        "player_ordinary_r_matrix_uri": prefix + "ordinary-r-player-matrix-v1.npz",
        "companion_global_rosters_uri": prefix + "global-rosters-v1.json",
        "companion_occurrence_provenance_uri": (
            prefix + "occurrence-provenance-v1.json"
        ),
        "companion_ordinary_r_lineup_score_matrix_uri": (
            prefix + "ordinary-r-lineup-score-matrix-v1.npz"
        ),
        "hard230_control_receipts_uri": prefix + "hard230-controls-v1.json",
        "hard230_generation_receipts_uri": prefix + "hard230-receipts-v1.json",
        "discovery_control_receipts_uri": prefix + "discovery-controls-v1.json",
        "discovery_schedule_accounting_uri": (
            prefix + "discovery-schedule-accounting-v1.json"
        ),
        "selector_books_uri": prefix + "stage-b-selector-books-v1.json",
        "pre_grade_catalog_fragment_uri": (
            prefix + "pre-grade-catalog-fragment-v1.json"
        ),
        "companion_acceptance_uri": prefix + "companion-acceptance-v1.json",
    }


def _factorial_slates(
    core_manifest: Mapping[str, object], *, companion_prefix: str
) -> list[dict[str, object]]:
    rows = _sequence(core_manifest.get("factorial_slates"), label="core slates")
    if len(rows) != FACTORIAL_SLATE_COUNT:
        _fail("core factorial manifest does not contain exactly 53 slates")
    retained: list[dict[str, object]] = []
    output_uris: set[str] = set()
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"core factorial slate[{ordinal}]")
        if row.get("factorial_slate_ordinal") != ordinal:
            _fail("core factorial slate order differs")
        blocks = _sequence(
            row.get("ordinary_r_blocks"), label=f"slate[{ordinal}] blocks"
        )
        if [
            _mapping(block, label=f"slate[{ordinal}] block").get("block_id")
            for block in blocks
        ] != list(EVALUATION_BLOCKS):
            _fail("generation companion requires complete ordered R0..R4 blocks")
        if any(
            _mapping(block, label=f"slate[{ordinal}] block").get("world_count")
            != WORLDS_PER_BLOCK
            for block in blocks
        ):
            _fail("generation companion requires exactly 10,000 worlds per block")
        slate_id = str(row.get("slate_id"))
        outputs = _output_uris(
            companion_prefix=companion_prefix,
            ordinal=ordinal,
            slate_id=slate_id,
        )
        _exact_keys(outputs, _OUTPUT_KEYS, label="companion output URIs")
        if any(uri in output_uris for uri in outputs.values()):
            _fail("companion output URI repeats")
        output_uris.update(outputs.values())
        core_outputs = _mapping(
            row.get("shared_output_uris"), label=f"slate[{ordinal}] core outputs"
        )
        source_lineage = {
            "source_member_sha256": row.get("source_member_sha256"),
            "reconstruction_source_identity": row.get(
                "reconstruction_source_identity"
            ),
            "ordinary_r_blocks": list(blocks),
        }
        retained.append({
            "factorial_slate_ordinal": ordinal,
            "source_ordinal": row.get("source_ordinal"),
            "slate_id": slate_id,
            "season": row.get("season"),
            "week": row.get("week"),
            "source_member_sha256": row.get("source_member_sha256"),
            "source_lineage": source_lineage,
            "source_lineage_sha256": batch.canonical_sha256(source_lineage),
            "core_ordinary_r_score_matrix_uri": core_outputs.get(
                "ordinary_r_score_matrix_uri"
            ),
            "companion_output_uris": outputs,
        })
    if {str(row["slate_id"]) for row in retained}.__contains__("2025-w01"):
        _fail("mechanically excluded 2025 Week 1 reappeared")
    return retained


def _source_lineage_contract(core_manifest: Mapping[str, object]) -> dict[str, object]:
    body = {
        "law_id": "generation-companion-source-lineage-from-factorial/v1",
        "source_catalog_id": core_manifest.get("source_catalog_id"),
        "source_catalog_identity": core_manifest.get("source_catalog_identity"),
        "source_catalog_sha256": core_manifest.get("source_catalog_sha256"),
        "source_membership_sha256": core_manifest.get("source_membership_sha256"),
        "source_membership_acceptance_sha256": core_manifest.get(
            "source_membership_acceptance_sha256"
        ),
        "ordered_source_grid_count": 54,
        "mechanically_excluded_source_ordinal": 36,
        "mechanically_excluded_slate_id": "2025-w01",
        "retained_slate_count": FACTORIAL_SLATE_COUNT,
        "factorial_slates_sha256": core_manifest.get("factorial_slates_sha256"),
        "all_source_objects_are_generation_pinned": True,
        "per_slate_source_member_manifest_law": (
            "canonical-source-catalog-member-bytes-at-deterministic-uri"
        ),
        "public_source_member_object_hash_must_equal_source_member_sha256": True,
        "player_matrix_and_derivation_proof_must_bind_exact_source_blocks": True,
        "free_or_latest_source_aliases_forbidden": True,
        "source_membership_may_not_be_redeclared_by_this_companion": True,
        "uses_realized_outcomes": False,
    }
    body["source_lineage_contract_sha256"] = batch.canonical_sha256(body)
    return body


def _validate_core_manifest(
    value: object,
    *,
    source_catalog: Mapping[str, object],
    source_catalog_identity: Mapping[str, object],
    p0_generation_environment: Mapping[str, object],
    p0_generation_environment_sha256: str,
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
) -> dict[str, object]:
    try:
        return factorial.validate_extreme_tail_factorial_execution_manifest_v1(
            value,
            source_catalog=source_catalog,
            source_catalog_identity=source_catalog_identity,
            p0_generation_environment=p0_generation_environment,
            p0_generation_environment_sha256=p0_generation_environment_sha256,
            source_commit_sha=source_commit_sha,
            immutable_image=immutable_image,
            output_prefix=output_prefix,
        )
    except Exception as exc:
        raise CorpusExtremeTailGenerationCompanionManifestError(
            "core factorial manifest or authoritative source replay differs"
        ) from exc


def _guard_core_contract(core_manifest: Mapping[str, object]) -> None:
    retrieval = _mapping(
        core_manifest.get("retrieval_contract"), label="core retrieval contract"
    )
    if (
        PROTOCOL_SHA256
        != "b7d6c8f4f0ed2f6db667933717f5446545a06f1f2cda2c8ecd56ca26b45d34bc"
        or CENSUS_SHA256
        != "bb05e1ec5fa7a7d836282b41a2ed864aa7828a939257e674cf0625511862950f"
        or HARD230_CONTROL_ID
        != "hard-230-score-blind-stream-prefix-control-v1"
        or DISCOVERY_CONTROL_ID != "incumbent-equal-visit-control-v1"
        or CONTROL_IMPLEMENTATION_ID
        != "canonical-score-blind-prefix-and-equal-visit-controls-v1"
        or RELEASE_EXECUTION_MODE != "release"
        or FIXTURE_EXECUTION_MODE != "test-fixture"
        or HARD230_MINIMUM_SOLVER_CALL_CEILING != 200
        or HARD230_SOLVER_CALLS_PER_TARGET != 20
        or HARD230_MAXIMUM_SOLVER_CALL_CEILING != 10_000
        or PROSPECTIVE_K20_OI_SHADOW_ID != "2026-cbwu-oi-v1"
        or additions.HARD230_STRATEGY_ID
        != "hard-230-generate-replenish-v1"
        or additions.DISCOVERY_STRATEGY_ID
        != "game-regime-stratified-tail-discovery-v1"
        or additions.EXPECTED_HARD230_STRATEGY_SHA256
        != HARD230_STRATEGY_SHA256
        or additions.EXPECTED_HARD230_IMPLEMENTATION_SHA256
        != HARD230_IMPLEMENTATION_SHA256
        or additions.EXPECTED_HARD230_CONTRACT_BODY_SHA256
        != HARD230_PUBLIC_CONTRACT_SHA256
        or additions.EXPECTED_DISCOVERY_STRATEGY_SHA256
        != DISCOVERY_STRATEGY_SHA256
        or additions.EXPECTED_DISCOVERY_IMPLEMENTATION_SHA256
        != DISCOVERY_IMPLEMENTATION_SHA256
        or additions.EXPECTED_DISCOVERY_CONTRACT_BODY_SHA256
        != DISCOVERY_PUBLIC_CONTRACT_SHA256
        or factorial.FACTORIAL_EXECUTION_MANIFEST_SCHEMA
        != "foundry-extreme-tail-factorial-execution-manifest/v1"
        or factorial.PROTOCOL_SHA256 != CORE_PROTOCOL_SHA256
        or factorial.FACTORIAL_SLATE_COUNT != FACTORIAL_SLATE_COUNT
        or tuple(factorial.EVALUATION_BLOCKS) != EVALUATION_BLOCKS
        or factorial.WORLDS_PER_BLOCK != WORLDS_PER_BLOCK
        or tuple(factorial.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or factorial.RANKING_DEPTH != RANKING_DEPTH
        or tuple(factorial.RETRIEVAL_IDS).__len__() != 18
        or core_manifest.get("protocol_sha256") != CORE_PROTOCOL_SHA256
        or retrieval.get("retrieval_contract_sha256")
        != CORE_RETRIEVAL_CONTRACT_SHA256
        or core_manifest.get("factorial_cell_registry_sha256")
        != CORE_FACTORIAL_CELL_REGISTRY_SHA256
        or core_manifest.get("candidate_origin_registry_sha256")
        != CORE_CANDIDATE_ORIGIN_REGISTRY_SHA256
        or core_manifest.get("candidate_origin_masks_sha256")
        != CORE_CANDIDATE_ORIGIN_MASKS_SHA256
        or _mapping(
            core_manifest.get("ordinary_r_evaluation_contract"),
            label="core evaluation contract",
        ).get("evaluation_contract_sha256")
        != CORE_EVALUATION_CONTRACT_SHA256
        or _mapping(
            core_manifest.get("candidate_origin_cross_fit_contract"),
            label="core cross-fit contract",
        ).get("cross_fit_contract_sha256")
        != CORE_CROSS_FIT_CONTRACT_SHA256
        or _mapping(
            core_manifest.get("shared_artifact_contract"),
            label="core shared artifact contract",
        ).get("shared_artifact_contract_sha256")
        != CORE_SHARED_ARTIFACT_CONTRACT_SHA256
        or _mapping(
            core_manifest.get("controlled_grade_boundary"),
            label="core grade boundary",
        ).get("controlled_grade_boundary_sha256")
        != CORE_CONTROLLED_GRADE_BOUNDARY_SHA256
    ):
        _fail("frozen 18-row core factorial dependency differs")


def _guard_literal_contracts(
    *,
    control_implementation: Mapping[str, object],
    controls: Sequence[Mapping[str, object]],
    ordinary_r_law: Mapping[str, object],
    cross_fit_law: Mapping[str, object],
    generation_registry: Sequence[Mapping[str, object]],
    retrievals: Sequence[Mapping[str, object]],
    stage_b: Sequence[Mapping[str, object]],
    aggregate_law: Mapping[str, object],
) -> None:
    actual = {
        "control_implementation": control_implementation.get(
            "implementation_sha256"
        ),
        "hard_control": batch.canonical_sha256(_hard230_control_body()),
        "discovery_control": batch.canonical_sha256(_discovery_control_body()),
        "control_registry": batch.canonical_sha256(controls),
        "ordinary_r": ordinary_r_law.get("ordinary_r_matrix_law_sha256"),
        "cross_fit": cross_fit_law.get("generation_cross_fit_law_sha256"),
        "generation_registry": batch.canonical_sha256(generation_registry),
        "retrievals": batch.canonical_sha256(retrievals),
        "stage_b": batch.canonical_sha256(stage_b),
        "aggregate": aggregate_law.get("aggregate_pre_grade_law_sha256"),
    }
    expected = {
        "control_implementation": EXPECTED_CONTROL_IMPLEMENTATION_SHA256,
        "hard_control": EXPECTED_HARD230_CONTROL_SHA256,
        "discovery_control": EXPECTED_DISCOVERY_CONTROL_SHA256,
        "control_registry": EXPECTED_PAIRED_CONTROL_REGISTRY_SHA256,
        "ordinary_r": EXPECTED_ORDINARY_R_MATRIX_LAW_SHA256,
        "cross_fit": EXPECTED_GENERATION_CROSS_FIT_LAW_SHA256,
        "generation_registry": EXPECTED_GENERATION_REGISTRY_SHA256,
        "retrievals": EXPECTED_RETRIEVAL_DEPENDENCY_REGISTRY_SHA256,
        "stage_b": EXPECTED_STAGE_B_CATALOG_REGISTRY_SHA256,
        "aggregate": EXPECTED_AGGREGATE_PRE_GRADE_LAW_SHA256,
    }
    if actual != expected:
        differing = [key for key in expected if actual[key] != expected[key]]
        _fail(f"literal companion contract hashes differ: {differing}")


def build_extreme_tail_generation_companion_manifest_v1(
    *,
    factorial_manifest: Mapping[str, object],
    source_catalog: Mapping[str, object],
    source_catalog_identity: Mapping[str, object],
    p0_generation_environment: Mapping[str, object],
    p0_generation_environment_sha256: str,
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
    prospective_k20_oi_shadow_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build the pure 53-slate generation-companion registration manifest."""
    core = _validate_core_manifest(
        factorial_manifest,
        source_catalog=source_catalog,
        source_catalog_identity=source_catalog_identity,
        p0_generation_environment=p0_generation_environment,
        p0_generation_environment_sha256=p0_generation_environment_sha256,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
    )
    _guard_core_contract(core)
    hard_contract, discovery_contract = _public_generation_contracts()
    control_implementation = (
        frozen_generation_companion_control_implementation_v1()
    )
    controls = _paired_control_registry()
    ordinary_r_law = _ordinary_r_matrix_law()
    cross_fit_law = _generation_cross_fit_law()
    generation_registry = _generation_registry(
        hard_contract=hard_contract, discovery_contract=discovery_contract
    )
    retrievals = _retrieval_dependency_registry(core)
    stage_b = _stage_b_catalog_registry(
        core_manifest=core,
        generation_registry=generation_registry,
        controls=controls,
        retrievals=retrievals,
    )
    aggregate_law = _aggregate_pre_grade_law()
    shadow_binding = _prospective_k20_oi_shadow_binding(
        prospective_k20_oi_shadow_identity
    )
    _guard_literal_contracts(
        control_implementation=control_implementation,
        controls=controls,
        ordinary_r_law=ordinary_r_law,
        cross_fit_law=cross_fit_law,
        generation_registry=generation_registry,
        retrievals=retrievals,
        stage_b=stage_b,
        aggregate_law=aggregate_law,
    )
    companion_prefix = _companion_output_prefix(str(core["output_prefix"]))
    slates = _factorial_slates(core, companion_prefix=companion_prefix)
    slate_hash = batch.canonical_sha256(slates)
    controls_hash = batch.canonical_sha256(controls)
    generation_hash = batch.canonical_sha256(generation_registry)
    retrieval_hash = batch.canonical_sha256(retrievals)
    stage_b_hash = batch.canonical_sha256(stage_b)
    source_lineage = _source_lineage_contract(core)
    aggregate_catalog = {
        **aggregate_law,
        "registered_fragment_count": 2,
        "registered_fragments": [
            {
                "fragment_ordinal": 0,
                "fragment_id": "frozen-53-slate-factorial-core-v1",
                "manifest_id": core["manifest_id"],
                "manifest_sha256": core["execution_manifest_sha256"],
                "registry_sha256": CORE_RETRIEVAL_CONTRACT_SHA256,
                "primary_cell_registry_sha256": (
                    CORE_FACTORIAL_CELL_REGISTRY_SHA256
                ),
                "registry_row_count": 18,
                "scope_role": "unchanged-core-factorial-and-secondary-selectors",
            },
            {
                "fragment_ordinal": 1,
                "fragment_id": "generation-additions-stage-b-v1",
                "generation_registry_sha256": generation_hash,
                "control_implementation_sha256": control_implementation[
                    "implementation_sha256"
                ],
                "paired_control_registry_sha256": controls_hash,
                "stage_b_catalog_registry_sha256": stage_b_hash,
                "registry_row_count": len(stage_b),
                "new_registry_row_count": sum(
                    1 for row in stage_b if row["counts_as_new_rank"]
                ),
                "core_reference_row_count": sum(
                    1 for row in stage_b if not row["counts_as_new_rank"]
                ),
                "scope_role": "two-generation-challengers-and-paired-controls",
            },
        ],
        "factorial_slates_sha256": slate_hash,
        "source_lineage_contract_sha256": source_lineage[
            "source_lineage_contract_sha256"
        ],
        "catalog_status": (
            "outcome-blind-registration-incomplete-until-all-census-fragments-join"
        ),
        "this_instance_opens_outcome_access": False,
    }
    aggregate_catalog["aggregate_pre_grade_catalog_contract_sha256"] = (
        batch.canonical_sha256(aggregate_catalog)
    )
    manifest_seed = {
        "schema_version": GENERATION_COMPANION_MANIFEST_SCHEMA,
        "core_factorial_manifest_sha256": core["execution_manifest_sha256"],
        "source_catalog_identity": core["source_catalog_identity"],
        "source_catalog_sha256": core["source_catalog_sha256"],
        "factorial_slates_sha256": slate_hash,
        "generation_registry_sha256": generation_hash,
        "control_implementation_sha256": control_implementation[
            "implementation_sha256"
        ],
        "paired_control_registry_sha256": controls_hash,
        "stage_b_catalog_registry_sha256": stage_b_hash,
        "prospective_k20_oi_shadow_binding_sha256": shadow_binding[
            "prospective_k20_oi_shadow_binding_sha256"
        ],
        "source_commit_sha": core["source_commit_sha"],
        "immutable_image": core["immutable_image"],
        "companion_output_prefix": companion_prefix,
    }
    body: dict[str, object] = {
        "schema_version": GENERATION_COMPANION_MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_id": "foundry-generation-companion:" + batch.canonical_sha256(
            manifest_seed
        ),
        "protocol_document": PROTOCOL_DOCUMENT,
        "protocol_sha256": PROTOCOL_SHA256,
        "census_document": CENSUS_DOCUMENT,
        "census_sha256": CENSUS_SHA256,
        "core_factorial_manifest_id": core["manifest_id"],
        "core_factorial_manifest_sha256": core["execution_manifest_sha256"],
        "core_protocol_sha256": core["protocol_sha256"],
        "source_catalog_identity": core["source_catalog_identity"],
        "source_catalog_id": core["source_catalog_id"],
        "source_catalog_sha256": core["source_catalog_sha256"],
        "source_membership_sha256": core["source_membership_sha256"],
        "source_membership_acceptance_sha256": core[
            "source_membership_acceptance_sha256"
        ],
        "source_lineage_contract": source_lineage,
        "factorial_slate_count": FACTORIAL_SLATE_COUNT,
        "factorial_slates": slates,
        "factorial_slates_sha256": slate_hash,
        "ordinary_r_matrix_law": ordinary_r_law,
        "generation_cross_fit_law": cross_fit_law,
        "control_implementation_contract": control_implementation,
        "control_implementation_sha256": control_implementation[
            "implementation_sha256"
        ],
        "paired_control_registry": controls,
        "paired_control_registry_sha256": controls_hash,
        "generation_registry": generation_registry,
        "generation_registry_sha256": generation_hash,
        "retrieval_dependency_registry": retrievals,
        "retrieval_dependency_registry_sha256": retrieval_hash,
        "stage_b_catalog_registry": stage_b,
        "stage_b_catalog_registry_sha256": stage_b_hash,
        "aggregate_pre_grade_catalog_contract": aggregate_catalog,
        "prospective_k20_oi_shadow_binding": shadow_binding,
        "prospective_k20_oi_shadow_binding_sha256": shadow_binding[
            "prospective_k20_oi_shadow_binding_sha256"
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "ranking_prefix_law": RANKING_PREFIX_LAW,
        "source_commit_sha": core["source_commit_sha"],
        "immutable_image": core["immutable_image"],
        "core_output_prefix": core["output_prefix"],
        "companion_output_prefix": companion_prefix,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["generation_companion_manifest_sha256"] = batch.canonical_sha256(body)
    return body


def validate_extreme_tail_generation_companion_manifest_v1(
    value: object,
    *,
    factorial_manifest: Mapping[str, object],
    source_catalog: Mapping[str, object],
    source_catalog_identity: Mapping[str, object],
    p0_generation_environment: Mapping[str, object],
    p0_generation_environment_sha256: str,
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
    prospective_k20_oi_shadow_identity: Mapping[str, object],
) -> dict[str, object]:
    """Validate exact keys/self-hash and replay every authoritative input."""
    item = dict(_mapping(value, label="generation companion manifest"))
    _exact_keys(item, _MANIFEST_KEYS, label="generation companion manifest")
    if (
        item.get("schema_version") != GENERATION_COMPANION_MANIFEST_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
    ):
        _fail("generation companion schema or publication mode differs")
    _false_authorities(item, label="generation companion manifest")
    _validate_self_hash(
        item,
        field="generation_companion_manifest_sha256",
        label="generation companion manifest",
    )
    expected = build_extreme_tail_generation_companion_manifest_v1(
        factorial_manifest=factorial_manifest,
        source_catalog=source_catalog,
        source_catalog_identity=source_catalog_identity,
        p0_generation_environment=p0_generation_environment,
        p0_generation_environment_sha256=p0_generation_environment_sha256,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
        prospective_k20_oi_shadow_identity=prospective_k20_oi_shadow_identity,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("generation companion differs from frozen-input canonical replay")
    return expected


__all__ = [
    "CENSUS_DOCUMENT",
    "CENSUS_SHA256",
    "CorpusExtremeTailGenerationCompanionManifestError",
    "CONTROL_IMPLEMENTATION_SCHEMA",
    "DISCOVERY_CONTROL_RECEIPT_SCHEMA",
    "GENERATION_COMPANION_MANIFEST_SCHEMA",
    "HARD230_CONTROL_RECEIPT_SCHEMA",
    "HARD230_CONTROL_STREAM_SCHEMA",
    "PRE_GRADE_CATALOG_SCHEMA",
    "PROTOCOL_DOCUMENT",
    "PROTOCOL_SHA256",
    "build_hard230_score_blind_control_receipt_v1",
    "build_hard230_control_stream_manifest_v1",
    "build_incumbent_equal_visit_control_receipt_v1",
    "build_extreme_tail_generation_companion_manifest_v1",
    "frozen_generation_companion_control_implementation_v1",
    "validate_hard230_score_blind_control_receipt_v1",
    "validate_incumbent_equal_visit_control_receipt_v1",
    "validate_extreme_tail_generation_companion_manifest_v1",
]
