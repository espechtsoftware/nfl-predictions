"""Outcome-blind generation additions for the pre-Week-1 experiment catalog.

The two mechanisms in this module are deliberately isolated from production:

* ``hard-230-generate-replenish-v1`` consumes an ordered generator stream and
  retains only new, independently legal rosters whose scores reach 230 in an
  allowed source/training world; and
* ``game-regime-stratified-tail-discovery-v1`` derives game-level regimes from
  an ordinary-R player score matrix, spends exactly a paired control budget,
  and evaluates generated candidates on the separate heldout R block.

This is a pure receipt/replay seam.  It never invokes an optimizer, reads a
cloud object, consumes realized outcomes, publishes evidence, or changes a
policy.  Solver artifacts are generation-pinned and exactly bound, but their
optimality still requires an outer adapter replay.  Consequently every result
is diagnostic and carries false authority.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.inference import production_policy as production
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
CANDIDATE_ORIGINS: Final = tuple(f"R{ordinal}" for ordinal in range(20))
PRODUCTION_WORLDS_PER_BLOCK: Final = 10_000
ROSTER_SIZE: Final = 9

HARD230_CONTRACT_SCHEMA: Final = "hard-230-generate-replenish-contract/v1"
HARD230_RECEIPT_SCHEMA: Final = "hard-230-generate-replenish-receipt/v1"
HARD230_OCCURRENCE_SCHEMA: Final = "hard-230-generate-occurrence/v1"
HARD230_STRATEGY_ID: Final = "hard-230-generate-replenish-v1"
HARD230_GENERATOR_LAW_ID: Final = (
    "incumbent-legal-world-optimum-generator-stream-v1"
)
HARD230_THRESHOLD_MILLI: Final = 230_000
HARD230_MINIMUM_SOLVER_CALL_CEILING: Final = 200
HARD230_SOLVER_CALLS_PER_TARGET: Final = 20
HARD230_MAXIMUM_SOLVER_CALL_CEILING: Final = 10_000

DISCOVERY_CONTRACT_SCHEMA: Final = (
    "game-regime-stratified-tail-discovery-contract/v1"
)
DISCOVERY_SCHEDULE_SCHEMA: Final = (
    "game-regime-stratified-tail-discovery-schedule/v1"
)
DISCOVERY_ACCOUNTING_SCHEMA: Final = (
    "game-regime-stratified-tail-discovery-accounting/v1"
)
DISCOVERY_OCCURRENCE_SCHEMA: Final = (
    "game-regime-stratified-tail-discovery-occurrence/v1"
)
DISCOVERY_EVALUATION_SCHEMA: Final = (
    "game-regime-stratified-tail-discovery-heldout-evaluation/v1"
)
DISCOVERY_STRATEGY_ID: Final = (
    "game-regime-stratified-tail-discovery-v1"
)
DISCOVERY_REGIMES: Final = (
    "single-game-spike",
    "dominant-game",
    "distributed-games",
)

SINGLE_GAME_SPIKE_NUMERATOR: Final = 2
SINGLE_GAME_SPIKE_DENOMINATOR: Final = 1
DOMINANT_GAME_NUMERATOR: Final = 5
DOMINANT_GAME_DENOMINATOR: Final = 4

MIN_PLAYER_COUNT: Final = 9
MAX_PLAYER_COUNT: Final = 512
MIN_GAME_COUNT: Final = 2
MAX_GAME_COUNT: Final = 64
MAX_SCORE_BLOCK_COUNT: Final = 6
MAX_WORLD_COLUMN_COUNT: Final = 60_000
MAX_ABS_PLAYER_SCORE_MILLI: Final = 1_000_000
WORLD_AGGREGATE_CHUNK_SIZE: Final = 256
MATRIX_HASH_ROW_CHUNK_SIZE: Final = 32
SCORE_MATRIX_ENCODING: Final = "row-major-little-endian-int64-milli-dk/v1"
LEGALITY_AUDIT_LAW_ID: Final = "residual-world-audit-legal-identity-v1"
LEGALITY_AUDIT_IMPLEMENTATION_SHA256: Final = (
    "e807818c584df7a35a3c1f6a0c1e4e028081d6354425209b362d31712ab84daa"
)

# Filled from the literal bodies below.  They are intentionally independent of
# receipt self-hashes: coherent changes to a body cannot authorize themselves.
EXPECTED_HARD230_STRATEGY_SHA256: Final = (
    "524aa7cb737f325cafccda857ce68ac8f5801967f2d157aa06de85fd057da594"
)
EXPECTED_HARD230_IMPLEMENTATION_SHA256: Final = (
    "2700a83440e05056c99d429e0f910074c492fac10e55a860891964f4ae6b3da1"
)
EXPECTED_HARD230_CONTRACT_BODY_SHA256: Final = (
    "8454f3993c320d5f0b9689a37f25a42b06e56d6ec6eb7fbd3b680e9f77954ec1"
)
EXPECTED_DISCOVERY_STRATEGY_SHA256: Final = (
    "4389ad29e21340fee2bef6e2e76bb5cb773a39f78e580bb7c77acd8fcde41f30"
)
EXPECTED_DISCOVERY_IMPLEMENTATION_SHA256: Final = (
    "3e0a849e9cf57ad8edbdd903f1e0e06d785f19832ac1c1fd39d935224f634bd2"
)
EXPECTED_DISCOVERY_CONTRACT_BODY_SHA256: Final = (
    "94eeba2d806516c4ce22c5ef3480dd343a440618395bad93cec009a2303ebf3c"
)

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
    "promotion_authority",
    "decision_authority",
    "publication_authority",
    "source_replay_authority",
    "solver_proof_authority",
    "acceptance_authority",
    "evaluation_authority",
)


class CorpusExtremeTailGenerationAdditionsError(ValueError):
    """An input or retained artifact differs from the frozen pure contract."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailGenerationAdditionsError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _nonempty_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be one exact integer")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    result = _integer(value, label=label)
    if result < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return result


def _require_sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailGenerationAdditionsError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailGenerationAdditionsError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = _sha(result, label=field)
    return result


def _ordered_records_sha256(
    rows: Iterable[object], *, label: str
) -> str:
    """Hash ordered canonical records without materializing their union."""
    digest = hashlib.sha256()
    header = _canonical(
        {"encoding": "length-prefixed-canonical-json-records/v1", "label": label},
        label=f"{label} hash header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    count = 0
    for row in rows:
        encoded = _canonical(row, label=f"{label} record")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    digest.update(count.to_bytes(8, "big"))
    return digest.hexdigest()


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, {"uri", "generation", "sha256", "bytes"}, label=label)
    uri = _nonempty_string(item.get("uri"), label=f"{label} URI")
    generation = _nonempty_string(item.get("generation"), label=f"{label} generation")
    byte_count = _exact_int(item.get("bytes"), label=f"{label} bytes", minimum=1)
    if not uri.startswith("gs://") or not generation.isdigit():
        _fail(f"{label} must be one generation-pinned GCS content identity")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _require_sha256(item.get("sha256"), label=f"{label} hash"),
        "bytes": byte_count,
    }


def _proof_identity(
    value: object,
    *,
    label: str,
    expected_kind: str,
    expected_input_sha256: str,
    expected_output_sha256: str,
    expected_implementation_sha256: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(
        item,
        {
            "proof_id",
            "proof_kind",
            "implementation_sha256",
            "input_sha256",
            "output_sha256",
            "proof_object_identity",
        },
        label=label,
    )
    implementation = _require_sha256(
        item.get("implementation_sha256"), label=f"{label} implementation hash"
    )
    if (
        item.get("proof_kind") != expected_kind
        or item.get("input_sha256") != expected_input_sha256
        or item.get("output_sha256") != expected_output_sha256
        or (
            expected_implementation_sha256 is not None
            and implementation != expected_implementation_sha256
        )
    ):
        _fail(f"{label} lineage differs from its exact input/output")
    return {
        "proof_id": _nonempty_string(item.get("proof_id"), label=f"{label} ID"),
        "proof_kind": expected_kind,
        "implementation_sha256": implementation,
        "input_sha256": expected_input_sha256,
        "output_sha256": expected_output_sha256,
        "proof_object_identity": _object_identity(
            item.get("proof_object_identity"), label=f"{label} object"
        ),
    }


def _origin_registry() -> list[dict[str, object]]:
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


def _hard230_strategy_body() -> dict[str, object]:
    return {
        "strategy_id": HARD230_STRATEGY_ID,
        "generator_law_id": HARD230_GENERATOR_LAW_ID,
        "retention_threshold_milli_dk": HARD230_THRESHOLD_MILLI,
        "retention_operator": ">=",
        "paired_target_law": "exact-same-scope-control-retained-count",
        "cross_fit_law": "R0..R4-minus-heldout; no-heldout-origin-or-score-column",
        "stream_law": "contiguous-ordered-world-permutation-until-target-or-cap",
        "shortfall_law": "fail-never-lower-230-never-borrow-never-overrun-cap",
    }


def _hard230_implementation_body() -> dict[str, object]:
    return {
        "schemas": [
            HARD230_CONTRACT_SCHEMA,
            HARD230_RECEIPT_SCHEMA,
            HARD230_OCCURRENCE_SCHEMA,
        ],
        "matrix_encoding": SCORE_MATRIX_ENCODING,
        "matrix_hash_row_chunk_size": MATRIX_HASH_ROW_CHUNK_SIZE,
        "legality_audit_law_id": LEGALITY_AUDIT_LAW_ID,
        "legality_audit_implementation_sha256": (
            LEGALITY_AUDIT_IMPLEMENTATION_SHA256
        ),
        "score_derivation": (
            "sequential-int64-roster-sum-over-exact-permitted-block-columns"
        ),
        "proof_lineage": (
            "generation-pinned-solver-legality-and-matrix-derivation-artifacts"
        ),
        "solver_optimality_role": "outer-replay-required-not-locally-proven",
        "player_count_bounds": [MIN_PLAYER_COUNT, MAX_PLAYER_COUNT],
        "game_count_bounds": [MIN_GAME_COUNT, MAX_GAME_COUNT],
        "world_column_maximum": MAX_WORLD_COLUMN_COUNT,
        "player_score_abs_maximum_milli_dk": MAX_ABS_PLAYER_SCORE_MILLI,
    }


def _discovery_strategy_body() -> dict[str, object]:
    return {
        "strategy_id": DISCOVERY_STRATEGY_ID,
        "world_source": "existing-historical-ordinary-unweighted-R-worlds",
        "feature_law": "per-world-game-level-simulated-player-score-sums",
        "regime_order": list(DISCOVERY_REGIMES),
        "spike_ratio": [2, 1],
        "dominant_ratio": [5, 4],
        "zero_top_law": "distributed-games",
        "schedule_law": "regime-then-game-round-robin-with-canonical-ties",
        "budget_law": "exact-same-scope-control-visit-and-solve-count",
        "candidate_law": "one-reported-incumbent-legal-optimum-per-visit",
        "evaluation_law": "separate-heldout-ordinary-R-block-only",
        "atlas_and_realized_forbidden": True,
    }


def _discovery_implementation_body() -> dict[str, object]:
    return {
        "schemas": [
            DISCOVERY_CONTRACT_SCHEMA,
            DISCOVERY_SCHEDULE_SCHEMA,
            DISCOVERY_ACCOUNTING_SCHEMA,
            DISCOVERY_OCCURRENCE_SCHEMA,
            DISCOVERY_EVALUATION_SCHEMA,
        ],
        "matrix_encoding": SCORE_MATRIX_ENCODING,
        "matrix_hash_row_chunk_size": MATRIX_HASH_ROW_CHUNK_SIZE,
        "world_aggregate_chunk_size": WORLD_AGGREGATE_CHUNK_SIZE,
        "aggregate_memory_law": "game-count-by-at-most-chunk-width-int64-buffer",
        "legality_audit_law_id": LEGALITY_AUDIT_LAW_ID,
        "legality_audit_implementation_sha256": (
            LEGALITY_AUDIT_IMPLEMENTATION_SHA256
        ),
        "schedule_replay_law": "rebuild-from-bound-matrix-and-membership",
        "accounting_replay_law": "rebuild-entire-source-derived-schedule",
        "evaluation_derivation": "one-roster-vector-at-a-time-heldout-slice-only",
        "solver_optimality_role": "outer-replay-required-not-locally-proven",
        "player_count_bounds": [MIN_PLAYER_COUNT, MAX_PLAYER_COUNT],
        "game_count_bounds": [MIN_GAME_COUNT, MAX_GAME_COUNT],
        "world_column_maximum": MAX_WORLD_COLUMN_COUNT,
        "player_score_abs_maximum_milli_dk": MAX_ABS_PLAYER_SCORE_MILLI,
    }


def _hard230_contract_body() -> dict[str, object]:
    origins = _origin_registry()
    return {
        "schema_version": HARD230_CONTRACT_SCHEMA,
        "strategy_id": HARD230_STRATEGY_ID,
        "strategy_sha256": EXPECTED_HARD230_STRATEGY_SHA256,
        "implementation_sha256": EXPECTED_HARD230_IMPLEMENTATION_SHA256,
        "strategy_body": _hard230_strategy_body(),
        "implementation_body": _hard230_implementation_body(),
        "candidate_origin_registry": origins,
        "candidate_origin_registry_sha256": _sha(origins, label="origin registry"),
        "world_block_registry": list(WORLD_BLOCKS),
        "worlds_per_source_stream": PRODUCTION_WORLDS_PER_BLOCK,
        "minimum_solver_call_ceiling": HARD230_MINIMUM_SOLVER_CALL_CEILING,
        "solver_calls_per_target": HARD230_SOLVER_CALLS_PER_TARGET,
        "maximum_solver_call_ceiling": HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        "every_occurrence_and_decision_bound": True,
        "optimizer_cloud_adapter_status": "pending",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_and_solver_replay_required": True,
        **_false_authorities(),
    }


def _discovery_contract_body() -> dict[str, object]:
    return {
        "schema_version": DISCOVERY_CONTRACT_SCHEMA,
        "strategy_id": DISCOVERY_STRATEGY_ID,
        "strategy_sha256": EXPECTED_DISCOVERY_STRATEGY_SHA256,
        "implementation_sha256": EXPECTED_DISCOVERY_IMPLEMENTATION_SHA256,
        "strategy_body": _discovery_strategy_body(),
        "implementation_body": _discovery_implementation_body(),
        "world_block_registry": list(WORLD_BLOCKS),
        "worlds_per_block": PRODUCTION_WORLDS_PER_BLOCK,
        "fit_scope": "four-training-blocks-minus-one-exact-heldout-block",
        "atlas_world_score_forbidden": True,
        "achievable_lineup_optimum_for_scheduling_forbidden": True,
        "realized_outcomes_forbidden": True,
        "optimizer_cloud_adapter_status": "pending",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_and_solver_replay_required": True,
        **_false_authorities(),
    }


def _guard_frozen_dependencies() -> None:
    policy = production.ClassicProductionPolicy()
    imported_pairs = (
        tuple(policy.multiseed_seed_pairs)
        + tuple(policy.multiseed_volume_extra_seed_pairs)
    )
    if (
        tuple(rw.WORLD_BLOCKS) != WORLD_BLOCKS
        or rw.WORLDS_PER_BLOCK != PRODUCTION_WORLDS_PER_BLOCK
        or rw.ROSTER_SIZE != ROSTER_SIZE
        or rw.MIN_SALARY != 49_000
        or rw.SALARY_CAP != 50_000
        or rw.MAX_FROM_TEAM != 8
        or rw.MIN_GAMES != 2
        or imported_pairs != _FROZEN_SEED_PAIRS
        or len(_FROZEN_SEED_PAIRS) != 20
        or HARD230_STRATEGY_ID != "hard-230-generate-replenish-v1"
        or DISCOVERY_STRATEGY_ID
        != "game-regime-stratified-tail-discovery-v1"
        or HARD230_THRESHOLD_MILLI != 230_000
        or (
            HARD230_MINIMUM_SOLVER_CALL_CEILING,
            HARD230_SOLVER_CALLS_PER_TARGET,
            HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        )
        != (200, 20, 10_000)
        or DISCOVERY_REGIMES
        != ("single-game-spike", "dominant-game", "distributed-games")
        or (
            SINGLE_GAME_SPIKE_NUMERATOR,
            SINGLE_GAME_SPIKE_DENOMINATOR,
            DOMINANT_GAME_NUMERATOR,
            DOMINANT_GAME_DENOMINATOR,
        )
        != (2, 1, 5, 4)
        or (MIN_PLAYER_COUNT, MAX_PLAYER_COUNT) != (9, 512)
        or (MIN_GAME_COUNT, MAX_GAME_COUNT) != (2, 64)
        or WORLD_AGGREGATE_CHUNK_SIZE != 256
        or MATRIX_HASH_ROW_CHUNK_SIZE != 32
        or MAX_ABS_PLAYER_SCORE_MILLI != 1_000_000
    ):
        _fail("frozen generation-addition dependency contract differs")


def _guard_literal_contracts() -> None:
    checks = (
        (
            _sha(_hard230_strategy_body(), label="hard-230 strategy body"),
            EXPECTED_HARD230_STRATEGY_SHA256,
        ),
        (
            _sha(_hard230_implementation_body(), label="hard-230 implementation body"),
            EXPECTED_HARD230_IMPLEMENTATION_SHA256,
        ),
        (
            _sha(_hard230_contract_body(), label="hard-230 contract body"),
            EXPECTED_HARD230_CONTRACT_BODY_SHA256,
        ),
        (
            _sha(_discovery_strategy_body(), label="discovery strategy body"),
            EXPECTED_DISCOVERY_STRATEGY_SHA256,
        ),
        (
            _sha(
                _discovery_implementation_body(),
                label="discovery implementation body",
            ),
            EXPECTED_DISCOVERY_IMPLEMENTATION_SHA256,
        ),
        (
            _sha(_discovery_contract_body(), label="discovery contract body"),
            EXPECTED_DISCOVERY_CONTRACT_BODY_SHA256,
        ),
    )
    if any(actual != expected for actual, expected in checks):
        _fail("literal generation-addition strategy/implementation contract differs")


def _guard_contracts() -> None:
    _guard_frozen_dependencies()
    _guard_literal_contracts()


def frozen_hard230_generation_replenishment_contract_v1() -> dict[str, object]:
    """Return the literal-hash-pinned hard-230 generation contract."""
    _guard_contracts()
    body = _hard230_contract_body()
    body["hard230_contract_sha256"] = EXPECTED_HARD230_CONTRACT_BODY_SHA256
    return body


def frozen_game_regime_tail_discovery_contract_v1() -> dict[str, object]:
    """Return the literal-hash-pinned game-regime discovery contract."""
    _guard_contracts()
    body = _discovery_contract_body()
    body["discovery_contract_sha256"] = EXPECTED_DISCOVERY_CONTRACT_BODY_SHA256
    return body


def _validated_world_count(
    worlds_per_block: int, *, require_production_width: bool
) -> int:
    if type(require_production_width) is not bool:
        _fail("require_production_width must be an exact boolean")
    width = _exact_int(worlds_per_block, label="worlds per block", minimum=1)
    if width > PRODUCTION_WORLDS_PER_BLOCK:
        _fail("world width exceeds the frozen production width")
    if require_production_width and width != PRODUCTION_WORLDS_PER_BLOCK:
        _fail("production generation additions require exactly 10,000 worlds")
    return width


def _scope(heldout_block: str | None) -> tuple[str, str, tuple[str, ...]]:
    if heldout_block is None:
        return "final-fit", "all-block-final-fit", WORLD_BLOCKS
    if type(heldout_block) is not str or heldout_block not in WORLD_BLOCKS:
        _fail("heldout block must be null or one literal R0..R4 block")
    training = tuple(block for block in WORLD_BLOCKS if block != heldout_block)
    if len(training) != 4:
        _fail("heldout arithmetic did not produce exactly four training blocks")
    return "cross-fit", f"holdout-{heldout_block}", training


def _validated_origin(value: object, *, heldout_block: str | None) -> tuple[str, int]:
    origin = _nonempty_string(value, label="candidate origin ID")
    if origin not in CANDIDATE_ORIGINS:
        _fail("candidate origin must be one literal R0..R19 ID")
    if heldout_block is not None and origin == heldout_block:
        _fail("heldout candidate origin may not supply a generation stream")
    return origin, int(origin[1:])


def _permitted_score_blocks(
    *, origin_id: str, training_blocks: Sequence[str]
) -> tuple[str, ...]:
    blocks = list(training_blocks)
    if origin_id not in WORLD_BLOCKS:
        blocks.append(origin_id)
    if len(blocks) > MAX_SCORE_BLOCK_COUNT or len(set(blocks)) != len(blocks):
        _fail("permitted score-block arithmetic differs")
    return tuple(blocks)


def _source_member_identity(value: object) -> dict[str, object]:
    item = _mapping(value, label="source member identity")
    _exact_keys(
        item,
        {"member_id", "slate_id", "member_sha256", "object_identity"},
        label="source member identity",
    )
    identity = _object_identity(
        item.get("object_identity"), label="source member object"
    )
    member_sha = _require_sha256(
        item.get("member_sha256"), label="source member hash"
    )
    if identity["sha256"] != member_sha:
        _fail("source member object/content hash differs")
    return {
        "member_id": _nonempty_string(item.get("member_id"), label="member ID"),
        "slate_id": _nonempty_string(item.get("slate_id"), label="slate ID"),
        "member_sha256": member_sha,
        "object_identity": identity,
    }


def _score_block_identities(
    value: object,
    *,
    expected_block_ids: Sequence[str],
    worlds_per_block: int,
    source_member_sha256: str,
) -> list[dict[str, object]]:
    rows = list(_sequence(value, label="score block identities"))
    if len(rows) != len(expected_block_ids):
        _fail("score source does not bind the exact permitted block count")
    normalized: list[dict[str, object]] = []
    object_keys: list[tuple[object, ...]] = []
    for ordinal, (raw_row, block_id) in enumerate(
        zip(rows, expected_block_ids, strict=True)
    ):
        row = _mapping(raw_row, label=f"score block identity[{ordinal}]")
        _exact_keys(
            row,
            {"block_id", "world_count", "source_member_sha256", "object_identity"},
            label=f"score block identity[{ordinal}]",
        )
        if (
            row.get("block_id") != block_id
            or row.get("world_count") != worlds_per_block
            or row.get("source_member_sha256") != source_member_sha256
        ):
            _fail("score block identity/order/member/world count differs")
        identity = _object_identity(
            row.get("object_identity"), label=f"score block {block_id} object"
        )
        object_keys.append(
            (
                identity["uri"],
                identity["generation"],
                identity["sha256"],
                identity["bytes"],
            )
        )
        normalized.append(
            {
                "block_id": block_id,
                "world_count": worlds_per_block,
                "source_member_sha256": source_member_sha256,
                "object_identity": identity,
            }
        )
    if len(set(object_keys)) != len(object_keys):
        _fail("score block object identities repeat")
    return normalized


def _player_registry(value: object) -> tuple[list[dict[str, object]], list[str]]:
    rows = list(_sequence(value, label="player registry"))
    if not MIN_PLAYER_COUNT <= len(rows) <= MAX_PLAYER_COUNT:
        _fail("player registry count is outside the frozen bounds")
    normalized: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"player registry[{ordinal}]")
        _exact_keys(
            row,
            {"id", "pos", "team", "opp", "game_id", "salary"},
            label=f"player registry[{ordinal}]",
        )
        try:
            player = rw.PlayerSpec.from_mapping(row)
        except (KeyError, TypeError, ValueError, rw.ResidualWorldError) as exc:
            raise CorpusExtremeTailGenerationAdditionsError(
                f"player registry[{ordinal}] is malformed"
            ) from exc
        normalized.append(
            {
                "id": player.player_id,
                "pos": player.position,
                "team": player.team,
                "opp": player.opponent,
                "game_id": player.game_id,
                "salary": player.salary,
            }
        )
    player_ids = [str(row["id"]) for row in normalized]
    if player_ids != sorted(player_ids) or len(set(player_ids)) != len(player_ids):
        _fail("player registry must contain unique IDs in ascending order")
    games = sorted({str(row["game_id"]) for row in normalized})
    if not MIN_GAME_COUNT <= len(games) <= MAX_GAME_COUNT:
        _fail("player-to-game membership is outside the frozen dimensions")
    return normalized, games


def _validate_matrix_primitive(
    matrix: object, *, expected_rows: int, expected_columns: int
) -> np.ndarray:
    # Shape and dtype checks precede hashes, extrema, or aggregate allocations.
    if type(matrix) is not np.ndarray:
        _fail("score matrix must be one exact numpy ndarray without coercion")
    if matrix.ndim != 2 or matrix.shape != (expected_rows, expected_columns):
        _fail("score matrix dimensions differ from player/block/world membership")
    if expected_columns > MAX_WORLD_COLUMN_COUNT:
        _fail("score matrix world dimension exceeds the frozen bound")
    if matrix.dtype != np.dtype("<i8") or not matrix.flags.c_contiguous:
        _fail("score matrix must be C-contiguous little-endian int64")
    minimum = int(matrix.min())
    maximum = int(matrix.max())
    if (
        minimum < -MAX_ABS_PLAYER_SCORE_MILLI
        or maximum > MAX_ABS_PLAYER_SCORE_MILLI
    ):
        _fail("score matrix value exceeds bounded int64 aggregation limits")
    return matrix


def canonical_score_matrix_sha256_v1(matrix: np.ndarray) -> str:
    """Hash one bounded int64 score matrix without copying the full matrix."""
    if type(matrix) is not np.ndarray or matrix.ndim != 2:
        _fail("score matrix hash input must be one exact two-dimensional ndarray")
    rows, columns = matrix.shape
    validated = _validate_matrix_primitive(
        matrix, expected_rows=rows, expected_columns=columns
    )
    digest = hashlib.sha256()
    header = _canonical(
        {
            "encoding": SCORE_MATRIX_ENCODING,
            "shape": [rows, columns],
            "hash_row_chunk_size": MATRIX_HASH_ROW_CHUNK_SIZE,
        },
        label="score matrix hash header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    for start in range(0, rows, MATRIX_HASH_ROW_CHUNK_SIZE):
        stop = min(rows, start + MATRIX_HASH_ROW_CHUNK_SIZE)
        digest.update(memoryview(validated[start:stop]).cast("B"))
    return digest.hexdigest()


def _score_matrix_identity(
    value: object,
    *,
    matrix: np.ndarray,
    source_member: Mapping[str, object],
    block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    item = _mapping(value, label="score matrix identity")
    _exact_keys(
        item,
        {
            "matrix_id",
            "score_unit",
            "matrix_shape",
            "canonical_score_matrix_sha256",
            "artifact_identity",
            "source_member_sha256",
            "score_block_identities_sha256",
            "player_registry_sha256",
            "derivation_proof_identity",
        },
        label="score matrix identity",
    )
    matrix_hash = canonical_score_matrix_sha256_v1(matrix)
    block_hash = _sha(block_identities, label="score block identities")
    player_hash = _sha(player_registry, label="player registry")
    shape = [int(matrix.shape[0]), int(matrix.shape[1])]
    if (
        item.get("score_unit") != "milli-DraftKings-points"
        or item.get("matrix_shape") != shape
        or item.get("canonical_score_matrix_sha256") != matrix_hash
        or item.get("source_member_sha256") != source_member["member_sha256"]
        or item.get("score_block_identities_sha256") != block_hash
        or item.get("player_registry_sha256") != player_hash
    ):
        _fail("score matrix identity differs from exact source content/membership")
    artifact = _object_identity(
        item.get("artifact_identity"), label="score matrix artifact"
    )
    derivation_input = {
        "matrix_id": item.get("matrix_id"),
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": shape,
        "artifact_identity": artifact,
        "source_member_sha256": source_member["member_sha256"],
        "score_block_identities_sha256": block_hash,
        "player_registry_sha256": player_hash,
    }
    proof = _proof_identity(
        item.get("derivation_proof_identity"),
        label="score matrix derivation proof",
        expected_kind="score-matrix-derivation-v1",
        expected_input_sha256=_sha(
            derivation_input, label="score matrix derivation input"
        ),
        expected_output_sha256=_sha(
            {"canonical_score_matrix_sha256": matrix_hash},
            label="score matrix derivation output",
        ),
    )
    return {
        "matrix_id": _nonempty_string(item.get("matrix_id"), label="matrix ID"),
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": shape,
        "canonical_score_matrix_sha256": matrix_hash,
        "artifact_identity": artifact,
        "source_member_sha256": source_member["member_sha256"],
        "score_block_identities_sha256": block_hash,
        "player_registry_sha256": player_hash,
        "derivation_proof_identity": proof,
    }


def _prepare_score_context(
    *,
    source_member_identity: Mapping[str, object],
    score_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    score_matrix: np.ndarray,
    score_matrix_identity: Mapping[str, object],
    expected_block_ids: Sequence[str],
    worlds_per_block: int,
) -> dict[str, object]:
    source = _source_member_identity(source_member_identity)
    blocks = _score_block_identities(
        score_block_identities,
        expected_block_ids=expected_block_ids,
        worlds_per_block=worlds_per_block,
        source_member_sha256=str(source["member_sha256"]),
    )
    players, games = _player_registry(player_registry)
    expected_columns = len(expected_block_ids) * worlds_per_block
    matrix = _validate_matrix_primitive(
        score_matrix,
        expected_rows=len(players),
        expected_columns=expected_columns,
    )
    matrix_identity = _score_matrix_identity(
        score_matrix_identity,
        matrix=matrix,
        source_member=source,
        block_identities=blocks,
        player_registry=players,
    )
    player_index = {str(row["id"]): ordinal for ordinal, row in enumerate(players)}
    game_index = {game_id: ordinal for ordinal, game_id in enumerate(games)}
    return {
        "source_member": source,
        "block_ids": tuple(expected_block_ids),
        "block_identities": blocks,
        "block_identities_sha256": _sha(blocks, label="score block identities"),
        "player_registry": players,
        "player_registry_sha256": _sha(players, label="player registry"),
        "game_registry": games,
        "player_index": player_index,
        "game_index": game_index,
        "matrix": matrix,
        "matrix_identity": matrix_identity,
        "matrix_sha256": matrix_identity["canonical_score_matrix_sha256"],
        "matrix_derivation_proof_identity_sha256": _sha(
            matrix_identity["derivation_proof_identity"],
            label="matrix derivation proof identity",
        ),
    }


def _source_lineage(context: Mapping[str, object]) -> dict[str, object]:
    return {
        "source_member_sha256": context["source_member"]["member_sha256"],
        "score_block_ids": list(context["block_ids"]),
        "score_block_identities_sha256": context["block_identities_sha256"],
        "player_registry_sha256": context["player_registry_sha256"],
        "score_matrix_sha256": context["matrix_sha256"],
        "matrix_derivation_proof_identity_sha256": context[
            "matrix_derivation_proof_identity_sha256"
        ],
    }


def _roster(value: object, *, label: str) -> list[str]:
    rows = list(_sequence(value, label=label))
    if (
        len(rows) != ROSTER_SIZE
        or any(type(player_id) is not str or not player_id for player_id in rows)
        or len(set(rows)) != ROSTER_SIZE
        or rows != sorted(rows)
    ):
        _fail(f"{label} must be nine unique player IDs in ascending order")
    return rows


def _local_legality(
    roster: Sequence[str], *, context: Mapping[str, object]
) -> bool:
    try:
        identity = rw.audit_legal_identity(context["player_registry"], roster)
    except (KeyError, TypeError, ValueError, rw.ResidualWorldError):
        return False
    return tuple(identity) == tuple(roster)


def _legality_proof(
    value: object,
    *,
    roster: Sequence[str],
    context: Mapping[str, object],
    legality_passed: bool,
    label: str,
) -> dict[str, object]:
    proof_input = {
        "legality_audit_law_id": LEGALITY_AUDIT_LAW_ID,
        "roster_player_ids": list(roster),
        "player_registry_sha256": context["player_registry_sha256"],
    }
    return _proof_identity(
        value,
        label=label,
        expected_kind="independent-classic-legality-audit-v1",
        expected_input_sha256=_sha(proof_input, label=f"{label} input"),
        expected_output_sha256=_sha(
            {"legality_passed": legality_passed}, label=f"{label} output"
        ),
        expected_implementation_sha256=LEGALITY_AUDIT_IMPLEMENTATION_SHA256,
    )


def _score_roster_columns(
    roster: Sequence[str],
    *,
    context: Mapping[str, object],
    start: int,
    stop: int,
) -> np.ndarray:
    width = stop - start
    scores = np.zeros(width, dtype=np.int64)
    player_index = context["player_index"]
    matrix = context["matrix"]
    for player_id in roster:
        if player_id not in player_index:
            _fail("roster references a player outside the exact player registry")
        scores += matrix[player_index[player_id], start:stop]
    return scores


def _score_vector_sha256(vector: np.ndarray, *, label: str) -> str:
    digest = hashlib.sha256()
    header = _canonical(
        {
            "encoding": "little-endian-int64-vector/v1",
            "length": int(vector.shape[0]),
            "label": label,
        },
        label=f"{label} header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    digest.update(memoryview(vector).cast("B"))
    return digest.hexdigest()


def _score_scan(
    roster: Sequence[str], *, context: Mapping[str, object], worlds_per_block: int
) -> dict[str, object]:
    column_count = len(context["block_ids"]) * worlds_per_block
    scores = _score_roster_columns(
        roster, context=context, start=0, stop=column_count
    )
    maximum_flat = int(np.argmax(scores))
    maximum = int(scores[maximum_flat])
    hit_positions = np.flatnonzero(scores >= HARD230_THRESHOLD_MILLI).astype(
        np.dtype("<i8"), copy=False
    )
    maximum_block_ordinal, maximum_world = divmod(
        maximum_flat, worlds_per_block
    )
    return {
        "score_block_ids": list(context["block_ids"]),
        "scored_world_count": column_count,
        "score_matrix_sha256": context["matrix_sha256"],
        "score_derivation_proof_identity_sha256": context[
            "matrix_derivation_proof_identity_sha256"
        ],
        "score_vector_sha256": _score_vector_sha256(
            scores, label="hard-230 permitted-world score vector"
        ),
        "maximum_score_milli_dk": maximum,
        "maximum_world": {
            "block_id": context["block_ids"][maximum_block_ordinal],
            "world_index": maximum_world,
        },
        "inclusive_230_hit_world_count": int(hit_positions.shape[0]),
        "inclusive_230_hit_flat_indices_sha256": _score_vector_sha256(
            hit_positions, label="hard-230 hit flat indices"
        ),
        "score_derivation_replayed_locally": True,
    }


def _paired_control(
    value: object,
    *,
    origin_id: str,
    fit_scope_id: str,
    heldout_block: str | None,
    training_blocks: Sequence[str],
    context: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="paired control")
    _exact_keys(
        item,
        {
            "control_population_id",
            "candidate_origin_id",
            "fit_scope_id",
            "heldout_block",
            "training_blocks",
            "source_member_sha256",
            "score_block_ids",
            "score_block_identities_sha256",
            "player_registry_sha256",
            "score_matrix_sha256",
            "retained_count",
            "retained_roster_ids_sha256",
            "control_receipt_sha256",
            "receipt_identity",
        },
        label="paired control",
    )
    receipt = _object_identity(
        item.get("receipt_identity"), label="paired control receipt"
    )
    if (
        item.get("candidate_origin_id") != origin_id
        or item.get("fit_scope_id") != fit_scope_id
        or item.get("heldout_block") != heldout_block
        or item.get("training_blocks") != list(training_blocks)
        or item.get("source_member_sha256")
        != context["source_member"]["member_sha256"]
        or item.get("score_block_ids") != list(context["block_ids"])
        or item.get("score_block_identities_sha256")
        != context["block_identities_sha256"]
        or item.get("player_registry_sha256")
        != context["player_registry_sha256"]
        or item.get("score_matrix_sha256") != context["matrix_sha256"]
    ):
        _fail("paired control differs from exact origin/fit/source scope")
    control_receipt_sha = _require_sha256(
        item.get("control_receipt_sha256"), label="paired control receipt hash"
    )
    if receipt["sha256"] != control_receipt_sha:
        _fail("paired control receipt object/content hash differs")
    return {
        "control_population_id": _nonempty_string(
            item.get("control_population_id"), label="control population ID"
        ),
        "candidate_origin_id": origin_id,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "source_member_sha256": context["source_member"]["member_sha256"],
        "score_block_ids": list(context["block_ids"]),
        "score_block_identities_sha256": context[
            "block_identities_sha256"
        ],
        "player_registry_sha256": context["player_registry_sha256"],
        "score_matrix_sha256": context["matrix_sha256"],
        "retained_count": _exact_int(
            item.get("retained_count"), label="paired retained count", minimum=1
        ),
        "retained_roster_ids_sha256": _require_sha256(
            item.get("retained_roster_ids_sha256"),
            label="paired retained roster IDs hash",
        ),
        "control_receipt_sha256": control_receipt_sha,
        "receipt_identity": receipt,
    }


def _ordered_generator_world_indices(
    value: object, *, worlds_per_block: int
) -> list[int]:
    rows = list(_sequence(value, label="ordered generator world indices"))
    if (
        len(rows) != worlds_per_block
        or any(type(index) is not int for index in rows)
        or set(rows) != set(range(worlds_per_block))
    ):
        _fail("generator world stream must be one exact permutation of its source")
    return rows


def _generator_stream_identity(
    value: object,
    *,
    origin_id: str,
    world_order: Sequence[int],
    raw_occurrences: Sequence[Mapping[str, object]],
    context: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="generator stream identity")
    _exact_keys(
        item,
        {
            "stream_id",
            "candidate_origin_id",
            "generator_law_id",
            "generator_configuration_sha256",
            "solver_implementation_sha256",
            "source_member_sha256",
            "score_block_identities_sha256",
            "player_registry_sha256",
            "score_matrix_sha256",
            "ordered_world_indices_sha256",
            "ordered_occurrence_inputs_sha256",
            "occurrence_count",
            "stream_manifest_identity",
        },
        label="generator stream identity",
    )
    world_hash = _sha(list(world_order), label="generator world order")
    occurrence_hash = _ordered_records_sha256(
        raw_occurrences, label="generator occurrence inputs"
    )
    if (
        item.get("candidate_origin_id") != origin_id
        or item.get("generator_law_id") != HARD230_GENERATOR_LAW_ID
        or item.get("source_member_sha256")
        != context["source_member"]["member_sha256"]
        or item.get("score_block_identities_sha256")
        != context["block_identities_sha256"]
        or item.get("player_registry_sha256")
        != context["player_registry_sha256"]
        or item.get("score_matrix_sha256") != context["matrix_sha256"]
        or item.get("ordered_world_indices_sha256") != world_hash
        or item.get("ordered_occurrence_inputs_sha256") != occurrence_hash
        or item.get("occurrence_count") != len(raw_occurrences)
    ):
        _fail("generator stream identity differs from ordered source/occurrences")
    return {
        "stream_id": _nonempty_string(item.get("stream_id"), label="stream ID"),
        "candidate_origin_id": origin_id,
        "generator_law_id": HARD230_GENERATOR_LAW_ID,
        "generator_configuration_sha256": _require_sha256(
            item.get("generator_configuration_sha256"),
            label="generator configuration hash",
        ),
        "solver_implementation_sha256": _require_sha256(
            item.get("solver_implementation_sha256"),
            label="generator solver implementation hash",
        ),
        "source_member_sha256": context["source_member"]["member_sha256"],
        "score_block_identities_sha256": context[
            "block_identities_sha256"
        ],
        "player_registry_sha256": context["player_registry_sha256"],
        "score_matrix_sha256": context["matrix_sha256"],
        "ordered_world_indices_sha256": world_hash,
        "ordered_occurrence_inputs_sha256": occurrence_hash,
        "occurrence_count": len(raw_occurrences),
        "stream_manifest_identity": _object_identity(
            item.get("stream_manifest_identity"),
            label="generator stream manifest",
        ),
    }


def _hard230_solver_proof_input(
    *,
    stream: Mapping[str, object],
    context: Mapping[str, object],
    origin_id: str,
    position: int,
    world_index: int,
) -> dict[str, object]:
    return {
        "strategy_id": HARD230_STRATEGY_ID,
        "generator_law_id": HARD230_GENERATOR_LAW_ID,
        "stream_id": stream["stream_id"],
        "generator_configuration_sha256": stream[
            "generator_configuration_sha256"
        ],
        "candidate_origin_id": origin_id,
        "stream_position": position,
        "source_world_index": world_index,
        **_source_lineage(context),
    }


def _hard230_occurrence(
    value: object,
    *,
    expected_position: int,
    expected_world_index: int,
    origin_id: str,
    stream: Mapping[str, object],
    context: Mapping[str, object],
    worlds_per_block: int,
    seen_rosters: set[str],
    retained_ordinal: int,
) -> tuple[dict[str, object], bool]:
    item = _mapping(value, label=f"generator occurrence[{expected_position}]")
    _exact_keys(
        item,
        {
            "stream_position",
            "source_world_index",
            "solver_call_ordinal",
            "solver_status",
            "solver_proof_identity",
            "roster_player_ids",
            "legality_proof_identity",
            "uses_realized_outcomes",
            "uses_atlas_world_ranking",
        },
        label=f"generator occurrence[{expected_position}]",
    )
    if (
        item.get("stream_position") != expected_position
        or item.get("source_world_index") != expected_world_index
        or item.get("solver_call_ordinal") != expected_position
    ):
        _fail("generator occurrence position/world/solver order differs")
    if item.get("uses_realized_outcomes") is not False:
        _fail("hard-230 generation may not consume realized outcomes")
    if item.get("uses_atlas_world_ranking") is not False:
        _fail("hard-230 generation may not consume Atlas world ranking")
    status = item.get("solver_status")
    if status not in {"optimal", "infeasible", "error"}:
        _fail("generator solver status differs")
    roster: list[str] | None = None
    if status == "optimal":
        roster = _roster(
            item.get("roster_player_ids"), label="generated roster player IDs"
        )
    elif item.get("roster_player_ids") is not None:
        _fail("non-optimal generator occurrence carries a roster")
    solver_input = _hard230_solver_proof_input(
        stream=stream,
        context=context,
        origin_id=origin_id,
        position=expected_position,
        world_index=expected_world_index,
    )
    solver_proof = _proof_identity(
        item.get("solver_proof_identity"),
        label=f"generator solver proof[{expected_position}]",
        expected_kind="incumbent-world-optimum-solver-result-v1",
        expected_input_sha256=_sha(solver_input, label="generator solver input"),
        expected_output_sha256=_sha(
            {"solver_status": status, "roster_player_ids": roster},
            label="generator solver output",
        ),
        expected_implementation_sha256=str(
            stream["solver_implementation_sha256"]
        ),
    )
    roster_hash: str | None = None
    legality: bool | None = None
    legality_proof: dict[str, object] | None = None
    scan: dict[str, object] | None = None
    decision = "rejected"
    rejection_reason: str | None = "solver-not-optimal"
    assigned_ordinal: int | None = None
    if status != "optimal":
        if item.get("legality_proof_identity") is not None:
            _fail("non-optimal generator occurrence carries legality proof")
    else:
        if roster is None:
            _fail("optimal generator occurrence is missing its roster")
        roster_hash = _sha(roster, label="generated roster")
        legality = _local_legality(roster, context=context)
        legality_proof = _legality_proof(
            item.get("legality_proof_identity"),
            roster=roster,
            context=context,
            legality_passed=legality,
            label=f"generator legality proof[{expected_position}]",
        )
        if not legality:
            rejection_reason = "independent-legality-audit-failed"
        else:
            scan = _score_scan(
                roster, context=context, worlds_per_block=worlds_per_block
            )
            if roster_hash in seen_rosters:
                rejection_reason = "duplicate-generated-roster"
            else:
                seen_rosters.add(roster_hash)
                if int(scan["maximum_score_milli_dk"]) < HARD230_THRESHOLD_MILLI:
                    rejection_reason = "no-inclusive-230-permitted-world-hit"
                else:
                    decision = "retained-pending-outer-solver-replay"
                    rejection_reason = None
                    assigned_ordinal = retained_ordinal
    body = {
        "schema_version": HARD230_OCCURRENCE_SCHEMA,
        "stream_position": expected_position,
        "source_world": {
            "candidate_origin_id": origin_id,
            "world_index": expected_world_index,
        },
        "source_lineage": _source_lineage(context),
        "solver_call_ordinal": expected_position,
        "reported_solver_status": status,
        "solver_proof_identity": solver_proof,
        "solver_optimality_proven_locally": False,
        "outer_solver_proof_replay_required": True,
        "roster_player_ids": roster,
        "roster_sha256": roster_hash,
        "legality_passed_by_local_replay": legality,
        "legality_proof_identity": legality_proof,
        "score_scan": scan,
        "retention_threshold_milli_dk": HARD230_THRESHOLD_MILLI,
        "retention_operator": ">=",
        "decision": decision,
        "rejection_reason": rejection_reason,
        "retained_ordinal": assigned_ordinal,
        "uses_realized_outcomes": False,
        "uses_atlas_world_ranking": False,
        **_false_authorities(),
    }
    return (
        _self_hash(body, "occurrence_sha256"),
        decision == "retained-pending-outer-solver-replay",
    )


def _build_hard230_from_context(
    *,
    candidate_origin_id: str,
    heldout_block: str | None,
    worlds_per_block: int,
    scope_kind: str,
    fit_scope_id: str,
    training_blocks: Sequence[str],
    context: Mapping[str, object],
    generator_stream_identity: Mapping[str, object],
    ordered_generator_world_indices: Sequence[int],
    paired_control: Mapping[str, object],
    occurrences: Sequence[Mapping[str, object]],
    require_production_width: bool,
) -> dict[str, object]:
    origin_id, origin_ordinal = _validated_origin(
        candidate_origin_id, heldout_block=heldout_block
    )
    world_order = _ordered_generator_world_indices(
        ordered_generator_world_indices, worlds_per_block=worlds_per_block
    )
    raw_occurrences = list(_sequence(occurrences, label="generator occurrences"))
    if not raw_occurrences:
        _fail("hard-230 generator stream must bind at least one occurrence")
    stream = _generator_stream_identity(
        generator_stream_identity,
        origin_id=origin_id,
        world_order=world_order,
        raw_occurrences=raw_occurrences,
        context=context,
    )
    control = _paired_control(
        paired_control,
        origin_id=origin_id,
        fit_scope_id=fit_scope_id,
        heldout_block=heldout_block,
        training_blocks=training_blocks,
        context=context,
    )
    target = int(control["retained_count"])
    computed_ceiling = min(
        HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        max(
            HARD230_MINIMUM_SOLVER_CALL_CEILING,
            HARD230_SOLVER_CALLS_PER_TARGET * target,
        ),
    )
    effective_ceiling = min(worlds_per_block, computed_ceiling)
    if target > effective_ceiling:
        _fail("paired hard-230 target exceeds maximum possible retained count")
    if len(raw_occurrences) > effective_ceiling:
        _fail("hard-230 generator stream exceeds its frozen effective ceiling")
    seen_rosters: set[str] = set()
    retained_ids: list[str] = []
    normalized: list[dict[str, object]] = []
    rejection_counts = {
        "solver-not-optimal": 0,
        "independent-legality-audit-failed": 0,
        "duplicate-generated-roster": 0,
        "no-inclusive-230-permitted-world-hit": 0,
    }
    for position, raw_occurrence in enumerate(raw_occurrences):
        if len(retained_ids) == target:
            _fail("generator stream continued after the exact paired target")
        occurrence, retained = _hard230_occurrence(
            raw_occurrence,
            expected_position=position,
            expected_world_index=world_order[position],
            origin_id=origin_id,
            stream=stream,
            context=context,
            worlds_per_block=worlds_per_block,
            seen_rosters=seen_rosters,
            retained_ordinal=len(retained_ids),
        )
        normalized.append(occurrence)
        if retained:
            retained_ids.append(str(occurrence["roster_sha256"]))
        else:
            rejection_counts[str(occurrence["rejection_reason"])] += 1
    target_reached = len(retained_ids) == target
    if not target_reached and len(normalized) != effective_ceiling:
        _fail("hard-230 stream stopped before target or frozen ceiling exhaustion")
    contract = frozen_hard230_generation_replenishment_contract_v1()
    body = {
        "schema_version": HARD230_RECEIPT_SCHEMA,
        "strategy_id": HARD230_STRATEGY_ID,
        "hard230_contract_sha256": contract["hard230_contract_sha256"],
        "scope_kind": scope_kind,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "candidate_origin_id": origin_id,
        "candidate_origin_ordinal": origin_ordinal,
        "candidate_origin_is_discovery_only": origin_ordinal >= 5,
        "source_member_identity": context["source_member"],
        "score_block_identities": context["block_identities"],
        "player_registry_sha256": context["player_registry_sha256"],
        "score_matrix_identity": context["matrix_identity"],
        "source_lineage": _source_lineage(context),
        "generator_stream_identity": stream,
        "paired_control": control,
        "paired_retained_count": target,
        "retention_threshold_milli_dk": HARD230_THRESHOLD_MILLI,
        "retention_operator": ">=",
        "computed_solver_call_ceiling": computed_ceiling,
        "effective_stream_ceiling": effective_ceiling,
        "attempted_visit_count": len(normalized),
        "solver_call_count": len(normalized),
        "reported_optimal_solve_count": sum(
            row["reported_solver_status"] == "optimal" for row in normalized
        ),
        "locally_legal_generated_occurrence_count": sum(
            row["legality_passed_by_local_replay"] is True for row in normalized
        ),
        "unique_locally_legal_generated_roster_count": len(seen_rosters),
        "retained_count_pending_outer_solver_replay": len(retained_ids),
        "retained_roster_sha256s": retained_ids,
        "retained_roster_sha256s_sha256": _sha(
            retained_ids, label="retained hard-230 roster hashes"
        ),
        "rejected_count": len(normalized) - len(retained_ids),
        "rejection_counts": rejection_counts,
        "occurrence_count": len(normalized),
        "occurrences": normalized,
        "occurrences_sha256": _ordered_records_sha256(
            normalized, label="hard-230 normalized occurrences"
        ),
        "source_ceiling_exhausted": len(normalized) == worlds_per_block,
        "compute_ceiling_exhausted": len(normalized) == computed_ceiling,
        "effective_ceiling_exhausted": len(normalized) == effective_ceiling,
        "exact_paired_retained_count_mechanically_reached": target_reached,
        "retained_shortfall": target - len(retained_ids),
        "status": (
            "mechanically-complete-pending-outer-solver-replay"
            if target_reached
            else "failed-exhausted-with-retained-shortfall"
        ),
        "cell_acceptance": False,
        "eligible_for_outer_acceptance_replay": target_reached,
        "threshold_was_not_lowered": True,
        "heldout_candidates_were_not_borrowed": True,
        "automatic_replenishment_past_ceiling": False,
        "optimizer_cloud_adapter_status": "pending-external-proof-replay",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "publication_status": "not-publishable",
        "outer_exact_source_and_solver_replay_required": True,
        "require_production_width": require_production_width,
        **_false_authorities(),
    }
    return _self_hash(body, "hard230_generation_receipt_sha256")


def build_hard230_generation_replenishment_v1(
    *,
    candidate_origin_id: str,
    heldout_block: str | None,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    score_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    score_matrix: np.ndarray,
    score_matrix_identity: Mapping[str, object],
    generator_stream_identity: Mapping[str, object],
    ordered_generator_world_indices: Sequence[int],
    paired_control: Mapping[str, object],
    occurrences: Sequence[Mapping[str, object]],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Replay one actual-generation hard-230 stream from source primitives."""
    _guard_contracts()
    width = _validated_world_count(
        worlds_per_block, require_production_width=require_production_width
    )
    scope_kind, fit_scope_id, training_blocks = _scope(heldout_block)
    origin_id, _ = _validated_origin(
        candidate_origin_id, heldout_block=heldout_block
    )
    permitted_blocks = _permitted_score_blocks(
        origin_id=origin_id, training_blocks=training_blocks
    )
    if heldout_block is not None and heldout_block in permitted_blocks:
        _fail("heldout block leaked into hard-230 score columns")
    context = _prepare_score_context(
        source_member_identity=source_member_identity,
        score_block_identities=score_block_identities,
        player_registry=player_registry,
        score_matrix=score_matrix,
        score_matrix_identity=score_matrix_identity,
        expected_block_ids=permitted_blocks,
        worlds_per_block=width,
    )
    return _build_hard230_from_context(
        candidate_origin_id=origin_id,
        heldout_block=heldout_block,
        worlds_per_block=width,
        scope_kind=scope_kind,
        fit_scope_id=fit_scope_id,
        training_blocks=training_blocks,
        context=context,
        generator_stream_identity=generator_stream_identity,
        ordered_generator_world_indices=ordered_generator_world_indices,
        paired_control=paired_control,
        occurrences=occurrences,
        require_production_width=require_production_width,
    )


def validate_hard230_generation_replenishment_v1(
    value: Mapping[str, object],
    **replay_inputs: object,
) -> dict[str, object]:
    """Require canonical replay of the source, stream, proofs, and decisions."""
    retained = _mapping(value, label="retained hard-230 generation receipt")
    expected = build_hard230_generation_replenishment_v1(**replay_inputs)
    if _canonical(retained, label="retained hard-230 receipt") != _canonical(
        expected, label="replayed hard-230 receipt"
    ):
        _fail("retained hard-230 generation receipt canonical replay differs")
    return expected


def _control_budget(
    value: object,
    *,
    fit_scope_id: str,
    heldout_block: str,
    training_blocks: Sequence[str],
    context: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="control budget identity")
    _exact_keys(
        item,
        {
            "control_id",
            "fit_scope_id",
            "heldout_block",
            "training_blocks",
            "source_member_sha256",
            "ordinary_r_block_identities_sha256",
            "player_registry_sha256",
            "score_matrix_sha256",
            "visit_count",
            "solve_count",
            "solver_implementation_sha256",
            "control_receipt_sha256",
            "receipt_identity",
            "uses_realized_outcomes",
            "uses_atlas_world_ranking",
        },
        label="control budget identity",
    )
    visits = _exact_int(item.get("visit_count"), label="control visits", minimum=1)
    solves = _exact_int(item.get("solve_count"), label="control solves", minimum=1)
    receipt = _object_identity(
        item.get("receipt_identity"), label="control budget receipt"
    )
    receipt_sha = _require_sha256(
        item.get("control_receipt_sha256"), label="control budget receipt hash"
    )
    if (
        visits != solves
        or item.get("fit_scope_id") != fit_scope_id
        or item.get("heldout_block") != heldout_block
        or item.get("training_blocks") != list(training_blocks)
        or item.get("source_member_sha256")
        != context["source_member"]["member_sha256"]
        or item.get("ordinary_r_block_identities_sha256")
        != context["block_identities_sha256"]
        or item.get("player_registry_sha256")
        != context["player_registry_sha256"]
        or item.get("score_matrix_sha256") != context["matrix_sha256"]
        or receipt["sha256"] != receipt_sha
    ):
        _fail("control budget differs from exact fit/source/count binding")
    if item.get("uses_realized_outcomes") is not False:
        _fail("tail-discovery control may not use realized outcomes")
    if item.get("uses_atlas_world_ranking") is not False:
        _fail("tail-discovery control may not use Atlas world ranking")
    return {
        "control_id": _nonempty_string(item.get("control_id"), label="control ID"),
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "source_member_sha256": context["source_member"]["member_sha256"],
        "ordinary_r_block_identities_sha256": context[
            "block_identities_sha256"
        ],
        "player_registry_sha256": context["player_registry_sha256"],
        "score_matrix_sha256": context["matrix_sha256"],
        "visit_count": visits,
        "solve_count": solves,
        "solver_implementation_sha256": _require_sha256(
            item.get("solver_implementation_sha256"),
            label="control solver implementation hash",
        ),
        "control_receipt_sha256": receipt_sha,
        "receipt_identity": receipt,
        "uses_realized_outcomes": False,
        "uses_atlas_world_ranking": False,
    }


def _classify_game_totals(
    game_totals: Sequence[int], *, game_registry: Sequence[str]
) -> dict[str, object]:
    if len(game_totals) != len(game_registry) or len(game_totals) < 2:
        _fail("game aggregate dimensions differ from exact game membership")
    ordered = sorted(
        zip(game_registry, game_totals, strict=True),
        key=lambda pair: (-int(pair[1]), str(pair[0])),
    )
    top = int(ordered[0][1])
    second = int(ordered[1][1])
    # The positive-top guard is essential: 0 >= 2*0 must not create a spike.
    if (
        top > 0
        and SINGLE_GAME_SPIKE_DENOMINATOR * top
        >= SINGLE_GAME_SPIKE_NUMERATOR * second
    ):
        regime = DISCOVERY_REGIMES[0]
    elif (
        top > 0
        and DOMINANT_GAME_DENOMINATOR * top
        >= DOMINANT_GAME_NUMERATOR * second
    ):
        regime = DISCOVERY_REGIMES[1]
    else:
        regime = DISCOVERY_REGIMES[2]
    return {
        "regime_id": regime,
        "anchor_game_id": ordered[0][0],
        "anchor_game_points_milli_dk": top,
        "top_two_game_points_milli_dk": top + second,
        "slate_game_points_milli_dk": sum(int(value) for value in game_totals),
    }


def _derive_world_profiles(
    *,
    context: Mapping[str, object],
    training_blocks: Sequence[str],
    worlds_per_block: int,
) -> tuple[list[dict[str, object]], str]:
    matrix = context["matrix"]
    game_registry = context["game_registry"]
    game_index = context["game_index"]
    players = context["player_registry"]
    block_ids = context["block_ids"]
    if tuple(block_ids) != WORLD_BLOCKS:
        _fail("tail-discovery aggregate source must be exact ordinary R0..R4")
    # Player and game dimensions were checked before reaching this allocation.
    profiles: list[dict[str, object]] = []
    for training_ordinal, block_id in enumerate(training_blocks):
        block_ordinal = WORLD_BLOCKS.index(block_id)
        block_start = block_ordinal * worlds_per_block
        for local_start in range(0, worlds_per_block, WORLD_AGGREGATE_CHUNK_SIZE):
            local_stop = min(
                worlds_per_block, local_start + WORLD_AGGREGATE_CHUNK_SIZE
            )
            chunk_width = local_stop - local_start
            game_totals = np.zeros(
                (len(game_registry), chunk_width), dtype=np.int64
            )
            absolute_start = block_start + local_start
            absolute_stop = block_start + local_stop
            for player_ordinal, player in enumerate(players):
                game_ordinal = game_index[str(player["game_id"])]
                game_totals[game_ordinal] += matrix[
                    player_ordinal, absolute_start:absolute_stop
                ]
            for local_offset in range(chunk_width):
                world_index = local_start + local_offset
                classification = _classify_game_totals(
                    [
                        int(game_totals[game_ordinal, local_offset])
                        for game_ordinal in range(len(game_registry))
                    ],
                    game_registry=game_registry,
                )
                profiles.append(
                    {
                        "block_id": block_id,
                        "training_block_ordinal": training_ordinal,
                        "world_index": world_index,
                        **classification,
                    }
                )
    expected_count = len(training_blocks) * worlds_per_block
    if len(profiles) != expected_count:
        _fail("bounded game aggregation did not cover exact training worlds")
    return profiles, _ordered_records_sha256(
        profiles, label="derived training-world game profiles"
    )


def _build_discovery_schedule_from_context(
    *,
    heldout_block: str,
    worlds_per_block: int,
    fit_scope_id: str,
    training_blocks: Sequence[str],
    context: Mapping[str, object],
    control_budget_identity: Mapping[str, object],
    require_production_width: bool,
) -> dict[str, object]:
    control = _control_budget(
        control_budget_identity,
        fit_scope_id=fit_scope_id,
        heldout_block=heldout_block,
        training_blocks=training_blocks,
        context=context,
    )
    budget = int(control["visit_count"])
    fit_world_count = len(training_blocks) * worlds_per_block
    if budget > fit_world_count:
        _fail("control budget exceeds unique ordinary-R fit worlds")
    profiles, profiles_sha = _derive_world_profiles(
        context=context,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
    )
    queues: dict[tuple[str, str], list[dict[str, object]]] = {}
    for profile in profiles:
        key = (str(profile["regime_id"]), str(profile["anchor_game_id"]))
        queues.setdefault(key, []).append(profile)
    for queue in queues.values():
        queue.sort(
            key=lambda row: (
                -int(row["anchor_game_points_milli_dk"]),
                -int(row["top_two_game_points_milli_dk"]),
                -int(row["slate_game_points_milli_dk"]),
                int(row["training_block_ordinal"]),
                int(row["world_index"]),
            )
        )
    regime_ordinal = {
        regime: ordinal for ordinal, regime in enumerate(DISCOVERY_REGIMES)
    }
    queue_keys = sorted(
        queues, key=lambda key: (regime_ordinal[key[0]], key[1])
    )
    queue_positions = {key: 0 for key in queue_keys}
    scheduled: list[dict[str, object]] = []
    while len(scheduled) < budget:
        progressed = False
        for key in queue_keys:
            queue_position = queue_positions[key]
            queue = queues[key]
            if queue_position >= len(queue):
                continue
            world = queue[queue_position]
            queue_positions[key] += 1
            progressed = True
            item = {
                "schedule_position": len(scheduled),
                "queue_id": f"{key[0]}:{key[1]}",
                "queue_position": queue_position,
                "regime_id": key[0],
                "anchor_game_id": key[1],
                "block_id": world["block_id"],
                "world_index": world["world_index"],
                "anchor_game_points_milli_dk": world[
                    "anchor_game_points_milli_dk"
                ],
                "top_two_game_points_milli_dk": world[
                    "top_two_game_points_milli_dk"
                ],
                "slate_game_points_milli_dk": world[
                    "slate_game_points_milli_dk"
                ],
                "score_matrix_sha256": context["matrix_sha256"],
            }
            scheduled.append(_self_hash(item, "schedule_item_sha256"))
            if len(scheduled) == budget:
                break
        if not progressed:
            _fail("tail-discovery queues exhausted before control budget")
    world_pairs = [
        (str(row["block_id"]), int(row["world_index"])) for row in scheduled
    ]
    if len(set(world_pairs)) != len(world_pairs):
        _fail("tail-discovery schedule repeated one ordinary-R world")
    queue_manifest = []
    for ordinal, key in enumerate(queue_keys):
        queue = queues[key]
        queue_manifest.append(
            {
                "queue_ordinal": ordinal,
                "queue_id": f"{key[0]}:{key[1]}",
                "regime_id": key[0],
                "anchor_game_id": key[1],
                "world_count": len(queue),
                "ordered_world_ids_sha256": _ordered_records_sha256(
                    (
                        {
                            "block_id": row["block_id"],
                            "world_index": row["world_index"],
                        }
                        for row in queue
                    ),
                    label=f"discovery queue {key[0]}:{key[1]}",
                ),
            }
        )
    contract = frozen_game_regime_tail_discovery_contract_v1()
    body = {
        "schema_version": DISCOVERY_SCHEDULE_SCHEMA,
        "strategy_id": DISCOVERY_STRATEGY_ID,
        "discovery_contract_sha256": contract["discovery_contract_sha256"],
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "world_block_registry": list(WORLD_BLOCKS),
        "worlds_per_block": worlds_per_block,
        "source_member_identity": context["source_member"],
        "ordinary_r_block_identities": context["block_identities"],
        "player_registry_sha256": context["player_registry_sha256"],
        "player_to_game_membership_sha256": context["player_registry_sha256"],
        "game_registry": context["game_registry"],
        "game_registry_sha256": _sha(
            context["game_registry"], label="game registry"
        ),
        "score_matrix_identity": context["matrix_identity"],
        "source_lineage": _source_lineage(context),
        "derived_training_world_profiles_sha256": profiles_sha,
        "fit_world_count": fit_world_count,
        "control_budget_identity": control,
        "control_visit_count": budget,
        "control_solve_count": int(control["solve_count"]),
        "scheduled_visit_count": len(scheduled),
        "authorized_solver_call_count": len(scheduled),
        "exact_control_budget_match": True,
        "queue_count": len(queue_manifest),
        "queue_manifest": queue_manifest,
        "queue_manifest_sha256": _ordered_records_sha256(
            queue_manifest, label="tail-discovery queue manifest"
        ),
        "schedule": scheduled,
        "schedule_items_sha256": _ordered_records_sha256(
            scheduled, label="tail-discovery schedule items"
        ),
        "scheduled_worlds_are_unique": True,
        "aggregate_chunk_size": WORLD_AGGREGATE_CHUNK_SIZE,
        "maximum_aggregate_buffer_shape": [
            len(context["game_registry"]),
            min(WORLD_AGGREGATE_CHUNK_SIZE, worlds_per_block),
        ],
        "arbitrary_caller_game_aggregates_accepted": False,
        "heldout_score_cells_used_for_schedule_features": False,
        "matrix_content_hash_validation_reads_all_blocks": True,
        "atlas_world_ranking_was_not_used": True,
        "achievable_lineup_optimum_was_not_used_for_scheduling": True,
        "realized_outcomes_were_not_used": True,
        "optimizer_cloud_adapter_status": "pending",
        "candidate_generation_status": "pending-external-solver-proof-replay",
        "heldout_evaluation_status": "available-as-diagnostic-pure-replay",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "publication_status": "not-publishable",
        "outer_exact_source_and_solver_replay_required": True,
        "require_production_width": require_production_width,
        **_false_authorities(),
    }
    return _self_hash(body, "discovery_schedule_sha256")


def _prepare_ordinary_r_context(
    *,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    ordinary_r_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    ordinary_r_score_matrix: np.ndarray,
    ordinary_r_score_matrix_identity: Mapping[str, object],
) -> dict[str, object]:
    return _prepare_score_context(
        source_member_identity=source_member_identity,
        score_block_identities=ordinary_r_block_identities,
        player_registry=player_registry,
        score_matrix=ordinary_r_score_matrix,
        score_matrix_identity=ordinary_r_score_matrix_identity,
        expected_block_ids=WORLD_BLOCKS,
        worlds_per_block=worlds_per_block,
    )


def build_game_regime_tail_discovery_schedule_v1(
    *,
    heldout_block: str,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    ordinary_r_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    ordinary_r_score_matrix: np.ndarray,
    ordinary_r_score_matrix_identity: Mapping[str, object],
    control_budget_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Derive the exact non-Atlas schedule from a bound ordinary-R matrix."""
    _guard_contracts()
    width = _validated_world_count(
        worlds_per_block, require_production_width=require_production_width
    )
    scope_kind, fit_scope_id, training_blocks = _scope(heldout_block)
    if scope_kind != "cross-fit" or heldout_block is None:
        _fail("tail discovery requires one exact ordinary-R heldout block")
    context = _prepare_ordinary_r_context(
        worlds_per_block=width,
        source_member_identity=source_member_identity,
        ordinary_r_block_identities=ordinary_r_block_identities,
        player_registry=player_registry,
        ordinary_r_score_matrix=ordinary_r_score_matrix,
        ordinary_r_score_matrix_identity=ordinary_r_score_matrix_identity,
    )
    return _build_discovery_schedule_from_context(
        heldout_block=heldout_block,
        worlds_per_block=width,
        fit_scope_id=fit_scope_id,
        training_blocks=training_blocks,
        context=context,
        control_budget_identity=control_budget_identity,
        require_production_width=require_production_width,
    )


def validate_game_regime_tail_discovery_schedule_v1(
    value: Mapping[str, object], **replay_inputs: object
) -> dict[str, object]:
    """Require exact source/matrix replay of a retained discovery schedule."""
    retained = _mapping(value, label="retained tail-discovery schedule")
    expected = build_game_regime_tail_discovery_schedule_v1(**replay_inputs)
    if _canonical(retained, label="retained discovery schedule") != _canonical(
        expected, label="replayed discovery schedule"
    ):
        _fail("retained tail-discovery schedule canonical replay differs")
    return expected


def _discovery_solver_input(
    *,
    schedule: Mapping[str, object],
    schedule_item: Mapping[str, object],
    context: Mapping[str, object],
) -> dict[str, object]:
    return {
        "strategy_id": DISCOVERY_STRATEGY_ID,
        "discovery_schedule_sha256": schedule["discovery_schedule_sha256"],
        "schedule_item_sha256": schedule_item["schedule_item_sha256"],
        "scheduled_world": {
            "block_id": schedule_item["block_id"],
            "world_index": schedule_item["world_index"],
        },
        "incumbent_legality_law_id": LEGALITY_AUDIT_LAW_ID,
        **_source_lineage(context),
    }


def _discovery_solve_occurrence(
    value: object,
    *,
    schedule: Mapping[str, object],
    schedule_item: Mapping[str, object],
    expected_position: int,
    context: Mapping[str, object],
    worlds_per_block: int,
    solver_implementation_sha256: str,
) -> tuple[dict[str, object], bool]:
    item = _mapping(value, label=f"discovery solve[{expected_position}]")
    _exact_keys(
        item,
        {
            "schedule_position",
            "schedule_item_sha256",
            "solver_call_ordinal",
            "solver_status",
            "solver_proof_identity",
            "roster_player_ids",
            "legality_proof_identity",
            "objective_score_milli_dk",
            "uses_realized_outcomes",
            "uses_atlas_world_ranking",
        },
        label=f"discovery solve[{expected_position}]",
    )
    if (
        item.get("schedule_position") != expected_position
        or item.get("solver_call_ordinal") != expected_position
        or item.get("schedule_item_sha256")
        != schedule_item.get("schedule_item_sha256")
    ):
        _fail("discovery solve does not bind its exact scheduled visit")
    if item.get("uses_realized_outcomes") is not False:
        _fail("tail-discovery solve may not use realized outcomes")
    if item.get("uses_atlas_world_ranking") is not False:
        _fail("tail-discovery solve may not use Atlas world ranking")
    status = item.get("solver_status")
    if status not in {"optimal", "infeasible", "error"}:
        _fail("tail-discovery solver status differs")
    roster: list[str] | None = None
    objective: int | None = None
    legality: bool | None = None
    legality_proof: dict[str, object] | None = None
    if status == "optimal":
        roster = _roster(
            item.get("roster_player_ids"),
            label="tail-discovery world-optimum roster IDs",
        )
        block_ordinal = WORLD_BLOCKS.index(str(schedule_item["block_id"]))
        column = block_ordinal * worlds_per_block + int(schedule_item["world_index"])
        local_objective = int(
            _score_roster_columns(
                roster, context=context, start=column, stop=column + 1
            )[0]
        )
        objective = _integer(
            item.get("objective_score_milli_dk"),
            label="tail-discovery simulated objective",
        )
        if objective != local_objective:
            _fail("tail-discovery objective differs from bound score matrix")
        legality = _local_legality(roster, context=context)
        legality_proof = _legality_proof(
            item.get("legality_proof_identity"),
            roster=roster,
            context=context,
            legality_passed=legality,
            label=f"discovery legality proof[{expected_position}]",
        )
    elif any(
        item.get(field) is not None
        for field in (
            "roster_player_ids",
            "legality_proof_identity",
            "objective_score_milli_dk",
        )
    ):
        _fail("non-optimal discovery solve carries candidate evidence")
    solver_input = _discovery_solver_input(
        schedule=schedule, schedule_item=schedule_item, context=context
    )
    solver_proof = _proof_identity(
        item.get("solver_proof_identity"),
        label=f"discovery solver proof[{expected_position}]",
        expected_kind="incumbent-world-optimum-solver-result-v1",
        expected_input_sha256=_sha(solver_input, label="discovery solver input"),
        expected_output_sha256=_sha(
            {
                "solver_status": status,
                "roster_player_ids": roster,
                "objective_score_milli_dk": objective,
            },
            label="discovery solver output",
        ),
        expected_implementation_sha256=solver_implementation_sha256,
    )
    complete = status == "optimal" and legality is True
    roster_hash = _sha(roster, label="discovery roster") if roster else None
    body = {
        "schema_version": DISCOVERY_OCCURRENCE_SCHEMA,
        "schedule_position": expected_position,
        "schedule_item_sha256": schedule_item["schedule_item_sha256"],
        "scheduled_world": {
            "block_id": schedule_item["block_id"],
            "world_index": schedule_item["world_index"],
        },
        "regime_id": schedule_item["regime_id"],
        "anchor_game_id": schedule_item["anchor_game_id"],
        "source_lineage": _source_lineage(context),
        "solver_call_ordinal": expected_position,
        "reported_solver_status": status,
        "solver_proof_identity": solver_proof,
        "solver_optimality_proven_locally": False,
        "outer_solver_proof_replay_required": True,
        "roster_player_ids": roster,
        "roster_sha256": roster_hash,
        "legality_passed_by_local_replay": legality,
        "legality_proof_identity": legality_proof,
        "objective_score_milli_dk": objective,
        "objective_replayed_from_bound_matrix": status == "optimal",
        "one_reported_optimum_locally_legal_candidate_generated": complete,
        "uses_realized_outcomes": False,
        "uses_atlas_world_ranking": False,
        **_false_authorities(),
    }
    return _self_hash(body, "discovery_occurrence_sha256"), complete


def _build_discovery_accounting_from_context(
    *,
    schedule: Mapping[str, object],
    solve_results: Sequence[Mapping[str, object]],
    context: Mapping[str, object],
    worlds_per_block: int,
) -> dict[str, object]:
    scheduled = list(_sequence(schedule.get("schedule"), label="schedule items"))
    results = list(_sequence(solve_results, label="tail-discovery solve results"))
    if len(results) != len(scheduled):
        _fail("tail-discovery solve-result count differs from exact budget")
    control = _mapping(
        schedule.get("control_budget_identity"), label="schedule control budget"
    )
    solver_implementation = str(control["solver_implementation_sha256"])
    occurrences: list[dict[str, object]] = []
    complete_flags: list[bool] = []
    for position, (raw_result, raw_schedule_item) in enumerate(
        zip(results, scheduled, strict=True)
    ):
        schedule_item = _mapping(
            raw_schedule_item, label=f"schedule item[{position}]"
        )
        occurrence, complete = _discovery_solve_occurrence(
            raw_result,
            schedule=schedule,
            schedule_item=schedule_item,
            expected_position=position,
            context=context,
            worlds_per_block=worlds_per_block,
            solver_implementation_sha256=solver_implementation,
        )
        occurrences.append(occurrence)
        complete_flags.append(complete)
    roster_hashes = [
        str(row["roster_sha256"])
        for row in occurrences
        if row["one_reported_optimum_locally_legal_candidate_generated"] is True
    ]
    mechanically_complete = all(complete_flags)
    body = {
        "schema_version": DISCOVERY_ACCOUNTING_SCHEMA,
        "strategy_id": DISCOVERY_STRATEGY_ID,
        "discovery_schedule_sha256": schedule["discovery_schedule_sha256"],
        "schedule_items_sha256": schedule["schedule_items_sha256"],
        "fit_scope_id": schedule["fit_scope_id"],
        "heldout_block": schedule["heldout_block"],
        "training_blocks": schedule["training_blocks"],
        "source_lineage": _source_lineage(context),
        "control_budget_identity": schedule["control_budget_identity"],
        "control_visit_count": schedule["control_visit_count"],
        "control_solve_count": schedule["control_solve_count"],
        "scheduled_visit_count": schedule["scheduled_visit_count"],
        "solve_result_inputs_sha256": _ordered_records_sha256(
            results, label="discovery solve result inputs"
        ),
        "solver_call_count": len(occurrences),
        "reported_optimal_solve_count": sum(
            row["reported_solver_status"] == "optimal" for row in occurrences
        ),
        "locally_legal_candidate_occurrence_count": sum(complete_flags),
        "unique_candidate_roster_count": len(set(roster_hashes)),
        "candidate_roster_sha256s": roster_hashes,
        "candidate_roster_sha256s_sha256": _sha(
            roster_hashes, label="tail-discovery candidate roster hashes"
        ),
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
        "occurrences_sha256": _ordered_records_sha256(
            occurrences, label="tail-discovery normalized occurrences"
        ),
        "exact_control_visit_and_solve_budget_preserved": (
            len(occurrences)
            == schedule["control_visit_count"]
            == schedule["control_solve_count"]
        ),
        "one_candidate_per_scheduled_visit_pending_outer_solver_replay": (
            mechanically_complete
        ),
        "mechanically_complete": mechanically_complete,
        "status": (
            "mechanically-complete-pending-outer-solver-replay"
            if mechanically_complete
            else "failed-one-or-more-solves-or-local-legality-audits"
        ),
        "cell_acceptance": False,
        "optimizer_cloud_adapter_status": "pending-external-proof-replay",
        "heldout_evaluation_status": (
            "eligible-for-diagnostic-heldout-evaluation"
            if mechanically_complete
            else "blocked-by-mechanical-shortfall"
        ),
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "publication_status": "not-publishable",
        "outer_exact_source_schedule_and_solver_replay_required": True,
        **_false_authorities(),
    }
    return _self_hash(body, "discovery_accounting_sha256")


def _prepare_discovery_replay(
    *,
    heldout_block: str,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    ordinary_r_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    ordinary_r_score_matrix: np.ndarray,
    ordinary_r_score_matrix_identity: Mapping[str, object],
    control_budget_identity: Mapping[str, object],
    require_production_width: bool,
) -> tuple[int, tuple[str, ...], dict[str, object], dict[str, object]]:
    _guard_contracts()
    width = _validated_world_count(
        worlds_per_block, require_production_width=require_production_width
    )
    scope_kind, fit_scope_id, training_blocks = _scope(heldout_block)
    if scope_kind != "cross-fit" or heldout_block is None:
        _fail("tail discovery requires one exact ordinary-R heldout block")
    context = _prepare_ordinary_r_context(
        worlds_per_block=width,
        source_member_identity=source_member_identity,
        ordinary_r_block_identities=ordinary_r_block_identities,
        player_registry=player_registry,
        ordinary_r_score_matrix=ordinary_r_score_matrix,
        ordinary_r_score_matrix_identity=ordinary_r_score_matrix_identity,
    )
    schedule = _build_discovery_schedule_from_context(
        heldout_block=heldout_block,
        worlds_per_block=width,
        fit_scope_id=fit_scope_id,
        training_blocks=training_blocks,
        context=context,
        control_budget_identity=control_budget_identity,
        require_production_width=require_production_width,
    )
    return width, training_blocks, context, schedule


def build_game_regime_tail_discovery_accounting_v1(
    *,
    heldout_block: str,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    ordinary_r_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    ordinary_r_score_matrix: np.ndarray,
    ordinary_r_score_matrix_identity: Mapping[str, object],
    control_budget_identity: Mapping[str, object],
    solve_results: Sequence[Mapping[str, object]],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Rebuild the full schedule, then bind one solve result to each visit."""
    width, _, context, schedule = _prepare_discovery_replay(
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_member_identity=source_member_identity,
        ordinary_r_block_identities=ordinary_r_block_identities,
        player_registry=player_registry,
        ordinary_r_score_matrix=ordinary_r_score_matrix,
        ordinary_r_score_matrix_identity=ordinary_r_score_matrix_identity,
        control_budget_identity=control_budget_identity,
        require_production_width=require_production_width,
    )
    return _build_discovery_accounting_from_context(
        schedule=schedule,
        solve_results=solve_results,
        context=context,
        worlds_per_block=width,
    )


def validate_game_regime_tail_discovery_accounting_v1(
    value: Mapping[str, object], **replay_inputs: object
) -> dict[str, object]:
    """Reject any retained accounting not rebuilt from the complete source."""
    retained = _mapping(value, label="retained tail-discovery accounting")
    expected = build_game_regime_tail_discovery_accounting_v1(**replay_inputs)
    if _canonical(retained, label="retained discovery accounting") != _canonical(
        expected, label="replayed discovery accounting"
    ):
        _fail("retained tail-discovery accounting canonical replay differs")
    return expected


def _build_heldout_evaluation_from_context(
    *,
    heldout_block: str,
    worlds_per_block: int,
    context: Mapping[str, object],
    accounting: Mapping[str, object],
) -> dict[str, object]:
    if accounting.get("mechanically_complete") is not True:
        _fail("heldout evaluation requires mechanically complete accounting")
    unique_rosters: list[list[str]] = []
    seen: set[str] = set()
    occurrences = _sequence(
        accounting.get("occurrences"), label="accounting occurrences"
    )
    for raw_occurrence in occurrences:
        occurrence = _mapping(raw_occurrence, label="accounting occurrence")
        roster_hash = str(occurrence["roster_sha256"])
        if roster_hash in seen:
            continue
        seen.add(roster_hash)
        unique_rosters.append(
            _roster(
                occurrence["roster_player_ids"],
                label="heldout evaluation roster",
            )
        )
    if not unique_rosters:
        _fail("heldout evaluation has no selected candidate rosters")
    heldout_ordinal = WORLD_BLOCKS.index(heldout_block)
    start = heldout_ordinal * worlds_per_block
    stop = start + worlds_per_block
    evaluations: list[dict[str, object]] = []
    for ordinal, roster in enumerate(unique_rosters):
        scores = _score_roster_columns(
            roster, context=context, start=start, stop=stop
        )
        roster_hash = _sha(roster, label="heldout evaluation roster")
        evaluations.append(
            {
                "selected_roster_ordinal": ordinal,
                "roster_player_ids": roster,
                "roster_sha256": roster_hash,
                "heldout_block": heldout_block,
                "heldout_world_count": worlds_per_block,
                "score_matrix_sha256": context["matrix_sha256"],
                "heldout_score_vector_sha256": _score_vector_sha256(
                    scores, label=f"heldout score vector {roster_hash}"
                ),
                "heldout_score_sum_milli_dk": sum(int(score) for score in scores),
                "heldout_score_maximum_milli_dk": int(scores.max()),
                "heldout_inclusive_230_hit_count": int(
                    np.count_nonzero(scores >= HARD230_THRESHOLD_MILLI)
                ),
            }
        )
    body = {
        "schema_version": DISCOVERY_EVALUATION_SCHEMA,
        "strategy_id": DISCOVERY_STRATEGY_ID,
        "discovery_accounting_sha256": accounting[
            "discovery_accounting_sha256"
        ],
        "fit_scope_id": accounting["fit_scope_id"],
        "training_blocks": accounting["training_blocks"],
        "heldout_block": heldout_block,
        "heldout_world_count": worlds_per_block,
        "heldout_matrix_column_range": {
            "start_inclusive": start,
            "stop_exclusive": stop,
        },
        "source_lineage": _source_lineage(context),
        "selected_roster_count": len(unique_rosters),
        "selected_roster_sha256s": [
            row["roster_sha256"] for row in evaluations
        ],
        "selected_roster_sha256s_sha256": _sha(
            [row["roster_sha256"] for row in evaluations],
            label="heldout selected roster hashes",
        ),
        "evaluations": evaluations,
        "evaluations_sha256": _ordered_records_sha256(
            evaluations, label="heldout roster evaluations"
        ),
        "evaluation_score_derivation_used_only_heldout_columns": True,
        "fit_score_columns_used_for_evaluation": False,
        "candidate_generation_worlds_used_for_evaluation": False,
        "realized_outcomes_used_for_evaluation": False,
        "status": "diagnostic-heldout-only-complete",
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "publication_status": "not-publishable",
        "outer_exact_source_and_solver_replay_required": True,
        **_false_authorities(),
    }
    return _self_hash(body, "heldout_evaluation_sha256")


def build_game_regime_tail_discovery_heldout_evaluation_v1(
    *,
    heldout_block: str,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    ordinary_r_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    ordinary_r_score_matrix: np.ndarray,
    ordinary_r_score_matrix_identity: Mapping[str, object],
    control_budget_identity: Mapping[str, object],
    solve_results: Sequence[Mapping[str, object]],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Score unique generated rosters on the heldout ordinary-R block only."""
    width, _, context, schedule = _prepare_discovery_replay(
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_member_identity=source_member_identity,
        ordinary_r_block_identities=ordinary_r_block_identities,
        player_registry=player_registry,
        ordinary_r_score_matrix=ordinary_r_score_matrix,
        ordinary_r_score_matrix_identity=ordinary_r_score_matrix_identity,
        control_budget_identity=control_budget_identity,
        require_production_width=require_production_width,
    )
    accounting = _build_discovery_accounting_from_context(
        schedule=schedule,
        solve_results=solve_results,
        context=context,
        worlds_per_block=width,
    )
    return _build_heldout_evaluation_from_context(
        heldout_block=heldout_block,
        worlds_per_block=width,
        context=context,
        accounting=accounting,
    )


def validate_game_regime_tail_discovery_heldout_evaluation_v1(
    value: Mapping[str, object], **replay_inputs: object
) -> dict[str, object]:
    """Require heldout-only result replay from source through accounting."""
    retained = _mapping(value, label="retained heldout evaluation")
    expected = build_game_regime_tail_discovery_heldout_evaluation_v1(
        **replay_inputs
    )
    if _canonical(retained, label="retained heldout evaluation") != _canonical(
        expected, label="replayed heldout evaluation"
    ):
        _fail("retained heldout evaluation canonical replay differs")
    return expected


__all__ = [
    "CANDIDATE_ORIGINS",
    "CorpusExtremeTailGenerationAdditionsError",
    "DISCOVERY_ACCOUNTING_SCHEMA",
    "DISCOVERY_CONTRACT_SCHEMA",
    "DISCOVERY_EVALUATION_SCHEMA",
    "DISCOVERY_OCCURRENCE_SCHEMA",
    "DISCOVERY_REGIMES",
    "DISCOVERY_SCHEDULE_SCHEMA",
    "DISCOVERY_STRATEGY_ID",
    "EXPECTED_DISCOVERY_CONTRACT_BODY_SHA256",
    "EXPECTED_DISCOVERY_IMPLEMENTATION_SHA256",
    "EXPECTED_DISCOVERY_STRATEGY_SHA256",
    "EXPECTED_HARD230_CONTRACT_BODY_SHA256",
    "EXPECTED_HARD230_IMPLEMENTATION_SHA256",
    "EXPECTED_HARD230_STRATEGY_SHA256",
    "HARD230_CONTRACT_SCHEMA",
    "HARD230_GENERATOR_LAW_ID",
    "HARD230_OCCURRENCE_SCHEMA",
    "HARD230_RECEIPT_SCHEMA",
    "HARD230_STRATEGY_ID",
    "HARD230_THRESHOLD_MILLI",
    "PRODUCTION_WORLDS_PER_BLOCK",
    "WORLD_AGGREGATE_CHUNK_SIZE",
    "WORLD_BLOCKS",
    "build_game_regime_tail_discovery_accounting_v1",
    "build_game_regime_tail_discovery_heldout_evaluation_v1",
    "build_game_regime_tail_discovery_schedule_v1",
    "build_hard230_generation_replenishment_v1",
    "canonical_score_matrix_sha256_v1",
    "frozen_game_regime_tail_discovery_contract_v1",
    "frozen_hard230_generation_replenishment_contract_v1",
    "validate_game_regime_tail_discovery_accounting_v1",
    "validate_game_regime_tail_discovery_heldout_evaluation_v1",
    "validate_game_regime_tail_discovery_schedule_v1",
    "validate_hard230_generation_replenishment_v1",
]
