"""Replay-bound composite retrieval laws for the pre-Week-1 census.

The module is deliberately isolated from the frozen core engine. It supplies
two deterministic laws: ``hybrid-support-retrieval-v1`` and
``fixed-selector-ensemble-v1``.

Every entry point replays a canonical ordinary-R R0..R4 substrate receipt.
Historically outcome-derived support is accepted only through a replayed outer
fold producer receipt whose training membership is the exact complement of its
held-out membership. No raw outcome row, current held-out outcome, identity
feature, free-form rank, or free lineage hash is accepted by a selector.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import inspect
import json
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_preweek_additions as additions
from nfl_dfs.research import corpus_extreme_tail_preweek_selectors as preweek
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as t230
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


CONTRACT_SCHEMA: Final = "composite-retrieval-contract/v4"
IMPLEMENTATION_SCHEMA: Final = "composite-retrieval-implementation/v4"
SUBSTRATE_SCHEMA: Final = "canonical-composite-r0-r4-substrate/v3"
SOURCE_MANIFEST_SCHEMA: Final = "canonical-composite-source-manifest/v1"
SOURCE_MEMBER_SCHEMA: Final = "canonical-composite-source-member/v1"
SOURCE_MATRIX_SCHEMA: Final = "canonical-composite-score-matrix-artifact/v1"
SOURCE_MASK_SCHEMA: Final = "canonical-composite-candidate-mask-artifact/v1"
SOURCE_OCCURRENCE_SCHEMA: Final = "canonical-composite-occurrence-artifact/v1"
VECTOR_ARTIFACT_SCHEMA: Final = "canonical-support-vector-artifact/v1"
AUTHORITY_LOCK_SCHEMA: Final = "composite-retrieval-authority-lock/v1"
PRODUCER_AUTHORITY_LOCK_SCHEMA: Final = (
    "composite-retrieval-producer-authority-lock/v1"
)
STATIC_PRODUCER_SCHEMA: Final = "static-support-producer-receipt/v3"
OUTER_PRODUCER_SCHEMA: Final = "outer-crossfit-support-producer-receipt/v3"
OUTER_FOLD_SCHEMA: Final = "outer-crossfit-support-fold/v3"
UPSTREAM_RESULT_SCHEMA: Final = "upstream-selector-result-receipt/v2"
RECEIPT_SCHEMA: Final = "composite-retrieval-receipt/v4"
BOOK_SCHEMA: Final = "composite-retrieval-book/v2"
IMPLEMENTATION_ID: Final = "replay-bound-composite-retrieval-v4"
HYBRID_STRATEGY_ID: Final = "hybrid-support-retrieval-v1"
ENSEMBLE_STRATEGY_ID: Final = "fixed-selector-ensemble-v1"

# A release can exist only after a reviewed authority lock identity is frozen
# here and the literal implementation/strategy hashes are intentionally
# reminted.  Fixtures may build mechanics-only locks, but can never cross the
# release gate while this remains ``None``.
FROZEN_RELEASE_AUTHORITY_LOCK_IDENTITY: Final[Mapping[str, object] | None] = None
FROZEN_RELEASE_PRODUCER_AUTHORITY_LOCK_IDENTITY: Final[
    Mapping[str, object] | None
] = None

WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
PRODUCTION_WORLDS_PER_BLOCK: Final = 10_000
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
SLEEVE_SIZE: Final = 20

SUPPORT_SOURCE_ORDER: Final = (
    "simulated_tail_support",
    "realized_tail_posterior",
    "winner_topology_support",
    "novelty_residual_support",
)
OUTCOME_AWARE_SUPPORT_SOURCES: Final = frozenset(
    {"realized_tail_posterior", "winner_topology_support"}
)
SUPPORT_WEIGHTS: Final = {source: 1 for source in SUPPORT_SOURCE_ORDER}

ENSEMBLE_SOURCE_ORDER: Final = (
    "coverage-ge-230-v1",
    "bounded-tail-ladder-ge-210-250-v1",
    "block-robust-bounded-tail-ge-210-250-v1",
    "convex-excess-expected-max-ge-200-v1",
)
ENSEMBLE_SOURCE_IDENTITIES: Final = {
    "coverage-ge-230-v1": {
        "strategy_sha256": (
            "c43598db8dc2b081158f0660f8edc1ccae4ce1c58ff6a468036c6dbc089fa965"
        ),
        "implementation_sha256": (
            "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
        ),
    },
    "bounded-tail-ladder-ge-210-250-v1": {
        "strategy_sha256": (
            "e769cadb1a3189d736784225647d9a7342ab4ea25bd2b55f632dd0ec8de254fa"
        ),
        "implementation_sha256": (
            "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
        ),
    },
    "block-robust-bounded-tail-ge-210-250-v1": {
        "strategy_sha256": (
            "b3c4bf6ea5e09446e0fff6b901412c7e9370a1b0e1ac0053d864eaef36f958d9"
        ),
        "implementation_sha256": (
            "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
        ),
    },
    "convex-excess-expected-max-ge-200-v1": {
        "strategy_sha256": (
            "189dc6986c7d70b8315f9e41cb1fe5c6fce35c54f2756729254a0e1614dd1082"
        ),
        "implementation_sha256": (
            "1c94e9635d6038f629c40ce81cc2b3b3ed4fcad600e4832a0f231c5c9c19403d"
        ),
    },
}

FROZEN_SET_OBJECTIVE_ID: Final = "bounded-tail-ladder-ge-210-250-v1"
FROZEN_SET_OBJECTIVE_SHA256: Final = (
    "e769cadb1a3189d736784225647d9a7342ab4ea25bd2b55f632dd0ec8de254fa"
)
FROZEN_SET_IMPLEMENTATION_SHA256: Final = (
    "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
)
TAIL_RUNGS: Final = (
    (210.0, ">=", 1),
    (220.0, ">=", 2),
    (230.0, ">=", 4),
    (240.0, ">=", 8),
    (250.0, ">=", 16),
)

# Filled only after executable source identities and declarative contracts are
# static. A source-body or dependency change must intentionally mint v3.
EXPECTED_IMPLEMENTATION_SHA256: Final = (
    "d2d30be6df6732b40d32bdb99cb11cd5f70b9c7725c43bf261825c3ac6827e3a"
)
EXPECTED_STRATEGY_SHA256S: Final = {
    HYBRID_STRATEGY_ID: (
        "02c0279c7e13d6437ecfbb3a8027bca6db796feca6ddfd9e91e203db5779b8cd"
    ),
    ENSEMBLE_STRATEGY_ID: (
        "ec52a2e34ad09a7ba7b49a4515c76a2dabb85c50e90b62c79e53eb432d261500"
    ),
}

_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
    "publication_authority",
    "panel_membership_authority",
    "source_replay_authority",
    "realized_grade_open_authority",
    "outcome_authority",
)


class CorpusCompositeRetrievalError(ValueError):
    """A composite input, dependency, or receipt fails its exact v4 law."""


ReadExact = Callable[[Mapping[str, object]], bytes]


def _fail(message: str) -> None:
    raise CorpusCompositeRetrievalError(message)


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


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusCompositeRetrievalError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusCompositeRetrievalError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = _sha(result, label=field)
    return result


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _require_sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _nonempty(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, {"uri", "generation", "sha256", "bytes"}, label=label)
    uri = _nonempty(item.get("uri"), label=f"{label} URI")
    generation = _nonempty(
        item.get("generation"), label=f"{label} generation"
    )
    byte_count = item.get("bytes")
    if (
        not uri.startswith("gs://")
        or not generation.isdigit()
        or type(byte_count) is not int
        or byte_count < 1
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _require_sha256(item.get("sha256"), label=f"{label} hash"),
        "bytes": byte_count,
    }


def _read_exact_bytes(
    value: object, *, read_exact: ReadExact, label: str
) -> tuple[dict[str, object], bytes]:
    """Fetch one immutable uri@generation and verify its exact content identity."""
    identity = _object_identity(value, label=f"{label} object identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusCompositeRetrievalError(
            f"{label} exact-generation read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-generation content identity differs")
    return identity, raw


def _parse_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if type(key) is not str or key in result:
                raise ValueError("duplicate or non-string object key")
            result[key] = value
        return result

    def _constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant {value}")

    try:
        decoded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise CorpusCompositeRetrievalError(
            f"{label} is not strict canonical JSON"
        ) from exc
    body = dict(_mapping(decoded, label=label))
    if raw != _canonical(body, label=label):
        _fail(f"{label} bytes are not canonical JSON")
    return body


def _canonical_artifact(
    value: object, *, read_exact: ReadExact, label: str
) -> tuple[dict[str, object], dict[str, object]]:
    """Read one generation-pinned canonical-JSON artifact exactly."""
    identity, raw = _read_exact_bytes(value, read_exact=read_exact, label=label)
    return _parse_canonical_json(raw, label=f"{label} body"), identity


def _split_binary_artifact(
    value: object, *, read_exact: ReadExact, label: str
) -> tuple[dict[str, object], bytes, dict[str, object]]:
    """Read canonical metadata plus one NUL-delimited immutable binary payload."""
    identity, raw = _read_exact_bytes(value, read_exact=read_exact, label=label)
    metadata_raw, separator, payload = raw.partition(b"\0")
    if separator != b"\0" or not metadata_raw or not payload or b"\0" in metadata_raw:
        _fail(f"{label} binary envelope differs")
    metadata = _parse_canonical_json(metadata_raw, label=f"{label} metadata")
    return metadata, payload, identity


def _lineup_ids(value: Sequence[str]) -> list[str]:
    ids = list(_sequence(value, label="lineup IDs"))
    if (
        len(ids) < RANKING_DEPTH
        or any(type(lineup_id) is not str or not lineup_id for lineup_id in ids)
        or len(set(ids)) != len(ids)
        or ids != sorted(ids)
    ):
        _fail("lineup IDs must be at least 80 unique strings in ascending order")
    return ids


def _validated_full_matrix(
    value: np.ndarray,
    *,
    candidate_count: int,
    worlds_per_block: int,
    execution_mode: str,
) -> np.ndarray:
    if type(worlds_per_block) is not int or worlds_per_block < 1:
        _fail("worlds_per_block must be a positive exact integer")
    if execution_mode == "release":
        if worlds_per_block != PRODUCTION_WORLDS_PER_BLOCK:
            _fail("release mode requires exact production world width 10000")
    elif execution_mode == "fixture":
        if worlds_per_block == PRODUCTION_WORLDS_PER_BLOCK:
            _fail("production-width input may not be labeled fixture")
    else:
        _fail("execution_mode must be fixture or release")
    matrix = np.asarray(value)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.flags.c_contiguous
        or matrix.shape
        != (candidate_count, len(WORLD_BLOCKS) * worlds_per_block)
        or not np.isfinite(matrix).all()
    ):
        _fail("full scores must be finite C-contiguous float64 at exact R0..R4 shape")
    return matrix


def _matrix_sha256(values: np.ndarray, lineup_ids_sha256: str) -> str:
    digest = sha256()
    digest.update(canonical_json_bytes({
        "schema_version": "composite-float64-matrix/v2",
        "dtype": "float64-le",
        "shape": list(values.shape),
        "lineup_ids_sha256": lineup_ids_sha256,
        "column_order": "R0-R1-R2-R3-R4-block-major-world-index",
    }))
    digest.update(b"\0")
    digest.update(memoryview(np.ascontiguousarray(values, dtype="<f8")).cast("B"))
    return digest.hexdigest()


def _vector_sha256(values: np.ndarray, lineup_ids_sha256: str) -> str:
    digest = sha256()
    digest.update(canonical_json_bytes({
        "schema_version": "composite-float64-vector/v2",
        "dtype": "float64-le",
        "length": int(values.size),
        "lineup_ids_sha256": lineup_ids_sha256,
    }))
    digest.update(b"\0")
    digest.update(memoryview(np.ascontiguousarray(values, dtype="<f8")).cast("B"))
    return digest.hexdigest()


def _normalized_source_binding(value: object) -> dict[str, object]:
    item = _mapping(value, label="source binding")
    expected = {
        "candidate_mask_sha256",
        "occurrence_lineage_sha256",
        "source_manifest_identity",
        "source_member_identity",
        "source_score_matrix_identity",
    }
    _exact_keys(item, expected, label="source binding")
    normalized = {
        "candidate_mask_sha256": _require_sha256(
            item.get("candidate_mask_sha256"), label="candidate mask hash"
        ),
        "occurrence_lineage_sha256": _require_sha256(
            item.get("occurrence_lineage_sha256"),
            label="occurrence lineage hash",
        ),
        "source_manifest_identity": dict(
            _mapping(item.get("source_manifest_identity"), label="manifest identity")
        ),
        "source_member_identity": dict(
            _mapping(item.get("source_member_identity"), label="member identity")
        ),
        "source_score_matrix_identity": dict(
            _mapping(item.get("source_score_matrix_identity"), label="matrix identity")
        ),
    }
    _canonical(normalized, label="source binding")
    return normalized


def _normalized_producer_receipt_identities(value: object) -> dict[str, dict[str, object]]:
    item = _mapping(value, label="producer receipt identities")
    if set(item) != set(SUPPORT_SOURCE_ORDER):
        _fail("authority lock must pin exactly four producer receipts")
    return {
        source: _object_identity(
            item[source], label=f"{source} producer receipt identity"
        )
        for source in SUPPORT_SOURCE_ORDER
    }


def _authority_lock_body(
    *,
    authority_mode: str,
    source_manifest_receipt_identity: Mapping[str, object],
    source_member_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    if authority_mode not in {"fixture", "release"}:
        _fail("authority lock mode must be fixture or release")
    manifest_identity = _object_identity(
        source_manifest_receipt_identity,
        label="authority-lock source manifest identity",
    )
    member_identity = _object_identity(
        source_member_receipt_identity,
        label="authority-lock source member identity",
    )
    seed = {
        "source_manifest_receipt_identity": manifest_identity,
        "source_member_receipt_identity": member_identity,
    }
    body = {
        "schema_version": AUTHORITY_LOCK_SCHEMA,
        "authority_lock_id": f"{authority_mode}:" + _sha(
            seed, label="authority lock seed"
        ),
        "authority_mode": authority_mode,
        **seed,
        "reviewed_for_release": authority_mode == "release",
        "fixture_only_not_release_authority": authority_mode == "fixture",
        "release_lock_literal_frozen": authority_mode == "release",
        **_false_authorities(),
    }
    return _self_hash(body, "authority_lock_sha256")


def build_fixture_composite_authority_lock_v1(
    *,
    source_manifest_receipt_identity: Mapping[str, object],
    source_member_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build mechanics-only fixture provenance; it can never authorize release."""
    return _authority_lock_body(
        authority_mode="fixture",
        source_manifest_receipt_identity=source_manifest_receipt_identity,
        source_member_receipt_identity=source_member_receipt_identity,
    )


def _replay_composite_authority_lock(
    value: object, *, read_exact: ReadExact, execution_mode: str
) -> tuple[dict[str, object], dict[str, object]]:
    retained, identity = _canonical_artifact(
        value, read_exact=read_exact, label="composite authority lock"
    )
    expected_keys = {
        "schema_version",
        "authority_lock_id",
        "authority_mode",
        "source_manifest_receipt_identity",
        "source_member_receipt_identity",
        "reviewed_for_release",
        "fixture_only_not_release_authority",
        "release_lock_literal_frozen",
        "authority_lock_sha256",
        *_FALSE_AUTHORITY_FIELDS,
    }
    _exact_keys(retained, expected_keys, label="composite authority lock")
    if any(retained.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS):
        _fail("composite authority lock grants forbidden authority")
    authority_mode = retained.get("authority_mode")
    if (
        retained.get("schema_version") != AUTHORITY_LOCK_SCHEMA
        or authority_mode != execution_mode
    ):
        _fail("composite authority lock mode or schema differs")
    expected = _authority_lock_body(
        authority_mode=str(authority_mode),
        source_manifest_receipt_identity=_mapping(
            retained.get("source_manifest_receipt_identity"),
            label="locked source manifest identity",
        ),
        source_member_receipt_identity=_mapping(
            retained.get("source_member_receipt_identity"),
            label="locked source member identity",
        ),
    )
    if _canonical(retained, label="retained authority lock") != _canonical(
        expected, label="replayed authority lock"
    ):
        _fail("composite authority lock canonical replay differs")
    if execution_mode == "release":
        if FROZEN_RELEASE_AUTHORITY_LOCK_IDENTITY is None:
            _fail("no reviewed release authority lock identity is frozen")
        frozen = _object_identity(
            FROZEN_RELEASE_AUTHORITY_LOCK_IDENTITY,
            label="frozen release authority lock identity",
        )
        if identity != frozen:
            _fail("release authority lock differs from frozen literal identity")
    return expected, identity


def _producer_authority_lock_body(
    *,
    authority_mode: str,
    source_authority_lock_identity: Mapping[str, object],
    substrate_receipt_sha256: str,
    producer_receipt_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if authority_mode not in {"fixture", "release"}:
        _fail("producer authority lock mode must be fixture or release")
    source_lock_identity = _object_identity(
        source_authority_lock_identity,
        label="producer lock source authority identity",
    )
    substrate_hash = _require_sha256(
        substrate_receipt_sha256, label="producer lock substrate receipt hash"
    )
    producer_identities = _normalized_producer_receipt_identities(
        producer_receipt_identities
    )
    seed = {
        "source_authority_lock_identity": source_lock_identity,
        "substrate_receipt_sha256": substrate_hash,
        "producer_receipt_identities": producer_identities,
    }
    body = {
        "schema_version": PRODUCER_AUTHORITY_LOCK_SCHEMA,
        "producer_authority_lock_id": f"{authority_mode}:" + _sha(
            seed, label="producer authority lock seed"
        ),
        "authority_mode": authority_mode,
        **seed,
        "reviewed_for_release": authority_mode == "release",
        "fixture_only_not_release_authority": authority_mode == "fixture",
        "release_lock_literal_frozen": authority_mode == "release",
        **_false_authorities(),
    }
    return _self_hash(body, "producer_authority_lock_sha256")


def build_fixture_producer_authority_lock_v1(
    *,
    source_authority_lock_identity: Mapping[str, object],
    substrate_receipt_sha256: str,
    producer_receipt_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build a mechanics-only fixture lock over four exact producer receipts."""
    return _producer_authority_lock_body(
        authority_mode="fixture",
        source_authority_lock_identity=source_authority_lock_identity,
        substrate_receipt_sha256=substrate_receipt_sha256,
        producer_receipt_identities=producer_receipt_identities,
    )


def _replay_producer_authority_lock(
    value: object,
    *,
    source_authority_lock_identity: Mapping[str, object],
    substrate_receipt_sha256: str,
    read_exact: ReadExact,
    execution_mode: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained, identity = _canonical_artifact(
        value, read_exact=read_exact, label="producer authority lock"
    )
    expected_keys = {
        "schema_version", "producer_authority_lock_id", "authority_mode",
        "source_authority_lock_identity", "substrate_receipt_sha256",
        "producer_receipt_identities", "reviewed_for_release",
        "fixture_only_not_release_authority", "release_lock_literal_frozen",
        "producer_authority_lock_sha256", *_FALSE_AUTHORITY_FIELDS,
    }
    _exact_keys(retained, expected_keys, label="producer authority lock")
    if any(retained.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS):
        _fail("producer authority lock grants forbidden authority")
    if (
        retained.get("schema_version") != PRODUCER_AUTHORITY_LOCK_SCHEMA
        or retained.get("authority_mode") != execution_mode
    ):
        _fail("producer authority lock mode or schema differs")
    expected = _producer_authority_lock_body(
        authority_mode=execution_mode,
        source_authority_lock_identity=source_authority_lock_identity,
        substrate_receipt_sha256=substrate_receipt_sha256,
        producer_receipt_identities=_mapping(
            retained.get("producer_receipt_identities"),
            label="locked producer receipt identities",
        ),
    )
    if _canonical(retained, label="retained producer lock") != _canonical(
        expected, label="replayed producer lock"
    ):
        _fail("producer authority lock canonical replay differs")
    if execution_mode == "release":
        if FROZEN_RELEASE_PRODUCER_AUTHORITY_LOCK_IDENTITY is None:
            _fail("no reviewed release producer authority lock identity is frozen")
        frozen = _object_identity(
            FROZEN_RELEASE_PRODUCER_AUTHORITY_LOCK_IDENTITY,
            label="frozen release producer authority lock identity",
        )
        if identity != frozen:
            _fail("release producer authority lock differs from frozen literal identity")
    return expected, identity


def _matrix_artifact_payload_bytes(
    metadata: Mapping[str, object], values: np.ndarray
) -> bytes:
    return _canonical(metadata, label="matrix artifact metadata") + b"\0" + bytes(
        memoryview(np.ascontiguousarray(values, dtype="<f8")).cast("B")
    )


def _replay_matrix_artifact(
    value: object,
    *,
    read_exact: ReadExact,
    lineup_ids_sha256: str,
    full_scores: np.ndarray,
    worlds_per_block: int,
) -> tuple[dict[str, object], dict[str, object]]:
    metadata, payload, identity = _split_binary_artifact(
        value, read_exact=read_exact, label="source score matrix artifact"
    )
    matrix = np.asarray(full_scores)
    matrix_hash = _matrix_sha256(matrix, lineup_ids_sha256)
    expected = {
        "schema_version": SOURCE_MATRIX_SCHEMA,
        "matrix_id": _nonempty(metadata.get("matrix_id"), label="matrix ID"),
        "lineup_ids_sha256": lineup_ids_sha256,
        "full_score_matrix_sha256": matrix_hash,
        "full_score_shape": list(matrix.shape),
        "dtype": "float64-le",
        "column_order": "R0-R1-R2-R3-R4-block-major-world-index",
        "world_block_registry": list(WORLD_BLOCKS),
        "worlds_per_block": worlds_per_block,
    }
    if _canonical(metadata, label="retained matrix metadata") != _canonical(
        expected, label="replayed matrix metadata"
    ) or payload != bytes(memoryview(np.ascontiguousarray(matrix, dtype="<f8")).cast("B")):
        _fail("authoritative score matrix artifact replay differs")
    return expected, identity


def _replay_authoritative_source_artifacts(
    authority_lock: Mapping[str, object],
    *,
    read_exact: ReadExact,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    worlds_per_block: int,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Exact-read the lock-rooted manifest/member/matrix/mask/occurrence chain."""
    manifest, manifest_identity = _canonical_artifact(
        authority_lock.get("source_manifest_receipt_identity"),
        read_exact=read_exact,
        label="source manifest receipt",
    )
    member, member_identity = _canonical_artifact(
        authority_lock.get("source_member_receipt_identity"),
        read_exact=read_exact,
        label="source member receipt",
    )
    ids = _lineup_ids(lineup_ids)
    lineup_hash = _sha(ids, label="lineup IDs")

    _exact_keys(
        member,
        {
            "schema_version", "member_id", "member_ordinal", "slate_id",
            "lineup_ids_sha256", "score_matrix_artifact_identity",
            "candidate_mask_artifact_identity", "occurrence_artifact_identity",
        },
        label="source member receipt body",
    )
    member_ordinal = member.get("member_ordinal")
    if (
        member.get("schema_version") != SOURCE_MEMBER_SCHEMA
        or type(member_ordinal) is not int
        or member_ordinal < 0
        or member.get("lineup_ids_sha256") != lineup_hash
    ):
        _fail("authoritative source member receipt replay differs")
    matrix_body, matrix_identity = _replay_matrix_artifact(
        member.get("score_matrix_artifact_identity"),
        read_exact=read_exact,
        lineup_ids_sha256=lineup_hash,
        full_scores=full_scores,
        worlds_per_block=worlds_per_block,
    )
    mask, mask_identity = _canonical_artifact(
        member.get("candidate_mask_artifact_identity"),
        read_exact=read_exact,
        label="candidate mask artifact",
    )
    occurrence, occurrence_identity = _canonical_artifact(
        member.get("occurrence_artifact_identity"),
        read_exact=read_exact,
        label="occurrence artifact",
    )

    mask_content = {
        "schema_version": "canonical-composite-candidate-mask-content/v1",
        "selected_lineup_ids": ids,
    }
    expected_mask = {
        "schema_version": SOURCE_MASK_SCHEMA,
        "candidate_mask_id": _nonempty(
            mask.get("candidate_mask_id"), label="candidate mask ID"
        ),
        "selected_lineup_ids": ids,
        "lineup_ids_sha256": lineup_hash,
        "candidate_count": len(ids),
        "candidate_mask_sha256": _sha(mask_content, label="candidate mask"),
    }
    if _canonical(mask, label="retained mask artifact") != _canonical(
        expected_mask, label="replayed mask artifact"
    ):
        _fail("authoritative candidate mask artifact replay differs")

    occurrence_rows = list(
        _sequence(occurrence.get("lineup_occurrences"), label="lineup occurrences")
    )
    normalized_occurrences: list[dict[str, object]] = []
    for ordinal, raw in enumerate(occurrence_rows):
        row = _mapping(raw, label=f"lineup occurrence[{ordinal}]")
        _exact_keys(
            row, {"lineup_id", "occurrence_count"},
            label=f"lineup occurrence[{ordinal}]",
        )
        count = row.get("occurrence_count")
        if type(count) is not int or count < 0:
            _fail("lineup occurrence count must be a nonnegative exact integer")
        normalized_occurrences.append({
            "lineup_id": _nonempty(
                row.get("lineup_id"), label=f"lineup occurrence[{ordinal}] ID"
            ),
            "occurrence_count": count,
        })
    if [row["lineup_id"] for row in normalized_occurrences] != ids:
        _fail("authoritative occurrence rows differ from lineup universe")
    occurrence_hash = _sha({
        "schema_version": "canonical-composite-occurrence-content/v1",
        "lineup_occurrences": normalized_occurrences,
    }, label="occurrence lineage")
    expected_occurrence = {
        "schema_version": SOURCE_OCCURRENCE_SCHEMA,
        "occurrence_artifact_id": _nonempty(
            occurrence.get("occurrence_artifact_id"), label="occurrence artifact ID"
        ),
        "lineup_occurrences": normalized_occurrences,
        "lineup_ids_sha256": lineup_hash,
        "occurrence_lineage_sha256": occurrence_hash,
    }
    if _canonical(occurrence, label="retained occurrence artifact") != _canonical(
        expected_occurrence, label="replayed occurrence artifact"
    ):
        _fail("authoritative occurrence artifact replay differs")

    _exact_keys(
        manifest,
        {"schema_version", "manifest_id", "member_count", "member_receipt_identities"},
        label="source manifest receipt body",
    )
    manifest_members = [
        _object_identity(raw, label=f"manifest member receipt identity[{ordinal}]")
        for ordinal, raw in enumerate(_sequence(
            manifest.get("member_receipt_identities"),
            label="manifest member receipt identities",
        ))
    ]
    if (
        manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA
        or type(manifest.get("member_count")) is not int
        or manifest.get("member_count") != len(manifest_members)
        or not manifest_members
        or len({tuple(identity.values()) for identity in manifest_members})
        != len(manifest_members)
        or member_ordinal >= len(manifest_members)
        or manifest_members[member_ordinal] != member_identity
    ):
        _fail("authoritative source manifest receipt replay differs")
    source = {
        "candidate_mask_sha256": expected_mask["candidate_mask_sha256"],
        "occurrence_lineage_sha256": occurrence_hash,
        "source_manifest_identity": {
            "manifest_id": _nonempty(manifest.get("manifest_id"), label="manifest ID"),
            "manifest_sha256": manifest_identity["sha256"],
            "object_identity": manifest_identity,
        },
        "source_member_identity": {
            "member_id": _nonempty(member.get("member_id"), label="member ID"),
            "member_ordinal": member_ordinal,
            "member_sha256": member_identity["sha256"],
            "slate_id": _nonempty(member.get("slate_id"), label="slate ID"),
        },
        "source_score_matrix_identity": {
            "matrix_id": matrix_body["matrix_id"],
            "matrix_sha256": matrix_body["full_score_matrix_sha256"],
            "object_identity": matrix_identity,
        },
    }
    return source, {
        "source_manifest_receipt": manifest_identity,
        "source_member_receipt": member_identity,
        "score_matrix_artifact": matrix_identity,
        "candidate_mask_artifact": mask_identity,
        "occurrence_artifact": occurrence_identity,
    }


def _source_binding(
    *,
    authority_lock: Mapping[str, object],
    read_exact: ReadExact,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    worlds_per_block: int,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    return _replay_authoritative_source_artifacts(
        authority_lock,
        read_exact=read_exact,
        lineup_ids=lineup_ids,
        full_scores=full_scores,
        worlds_per_block=worlds_per_block,
    )


def _upstream_fit_scope(
    *,
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    source_binding: Mapping[str, object],
    execution_mode: str,
) -> dict[str, object]:
    try:
        return preweek.build_extreme_tail_preweek_fit_scope_binding_v1(
            lineup_ids=lineup_ids,
            fit_scores=scores,
            training_blocks=training_blocks,
            heldout_block=heldout_block,
            worlds_per_block=worlds_per_block,
            candidate_mask_sha256=str(source_binding["candidate_mask_sha256"]),
            occurrence_lineage_sha256=str(
                source_binding["occurrence_lineage_sha256"]
            ),
            source_manifest_identity=_mapping(
                source_binding["source_manifest_identity"], label="manifest"
            ),
            source_member_identity=_mapping(
                source_binding["source_member_identity"], label="member"
            ),
            source_score_matrix_identity=_mapping(
                source_binding["source_score_matrix_identity"], label="matrix"
            ),
            require_production_width=execution_mode == "release",
        )
    except Exception as exc:
        raise CorpusCompositeRetrievalError(
            f"upstream fit-scope replay failed: {exc}"
        ) from exc


def build_canonical_substrate_receipt_v1(
    *,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    worlds_per_block: int,
    execution_mode: str,
    authority_lock_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build the all-five-block source/generation/matrix authority receipt."""
    ids = _lineup_ids(lineup_ids)
    matrix = _validated_full_matrix(
        full_scores,
        candidate_count=len(ids),
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
    )
    authority_lock, normalized_lock_identity = _replay_composite_authority_lock(
        authority_lock_identity,
        read_exact=read_exact,
        execution_mode=execution_mode,
    )
    source, source_artifact_identities = _source_binding(
        authority_lock=authority_lock,
        read_exact=read_exact,
        lineup_ids=ids,
        full_scores=matrix,
        worlds_per_block=worlds_per_block,
    )
    upstream = _upstream_fit_scope(
        lineup_ids=ids,
        scores=matrix,
        training_blocks=WORLD_BLOCKS,
        heldout_block=None,
        worlds_per_block=worlds_per_block,
        source_binding=source,
        execution_mode=execution_mode,
    )
    lineup_hash = _sha(ids, label="lineup IDs")
    body = {
        "schema_version": SUBSTRATE_SCHEMA,
        "execution_mode": execution_mode,
        "release_width_gate_passed": execution_mode == "release",
        "fixture_only_not_release_authority": execution_mode == "fixture",
        "world_block_registry": list(WORLD_BLOCKS),
        "column_order": "R0-R1-R2-R3-R4-block-major-world-index",
        "worlds_per_block": worlds_per_block,
        "candidate_count": len(ids),
        "lineup_ids_sha256": lineup_hash,
        "full_score_shape": list(matrix.shape),
        "full_score_matrix_sha256": _matrix_sha256(matrix, lineup_hash),
        "authority_lock_identity": normalized_lock_identity,
        "authority_lock_sha256": authority_lock["authority_lock_sha256"],
        "source_binding": source,
        "source_binding_sha256": _sha(source, label="source binding"),
        "source_artifact_identities": source_artifact_identities,
        "source_artifact_identities_sha256": _sha(
            source_artifact_identities, label="source artifact identities"
        ),
        "source_authority_law": (
            "exact-generation-authority-lock-to-manifest-member-matrix-mask-"
            "occurrence-artifact-replay"
        ),
        "upstream_all_block_fit_scope": upstream,
        "upstream_all_block_fit_scope_sha256": upstream[
            "fit_scope_binding_sha256"
        ],
        "uses_no_raw_or_current_heldout_outcomes": True,
        **_false_authorities(),
    }
    return _self_hash(body, "substrate_receipt_sha256")


def validate_canonical_substrate_receipt_v1(
    value: object,
    *,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    worlds_per_block: int,
    execution_mode: str,
    authority_lock_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    retained = _mapping(value, label="substrate receipt")
    expected = build_canonical_substrate_receipt_v1(
        lineup_ids=lineup_ids,
        full_scores=full_scores,
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
        authority_lock_identity=authority_lock_identity,
        read_exact=read_exact,
    )
    if _canonical(retained, label="retained substrate") != _canonical(
        expected, label="replayed substrate"
    ):
        _fail("canonical substrate receipt replay differs")
    return expected


def _producer_contract(value: object) -> dict[str, str]:
    item = _mapping(value, label="producer contract")
    expected = {
        "producer_id",
        "producer_version",
        "producer_implementation_sha256",
        "producer_executable_sha256",
        "fit_callable_sha256",
        "predict_callable_sha256",
    }
    _exact_keys(item, expected, label="producer contract")
    return {
        "producer_id": _nonempty(item.get("producer_id"), label="producer ID"),
        "producer_version": _nonempty(
            item.get("producer_version"), label="producer version"
        ),
        "producer_implementation_sha256": _require_sha256(
            item.get("producer_implementation_sha256"),
            label="producer implementation hash",
        ),
        "producer_executable_sha256": _require_sha256(
            item.get("producer_executable_sha256"),
            label="producer executable hash",
        ),
        "fit_callable_sha256": _require_sha256(
            item.get("fit_callable_sha256"), label="fit callable hash"
        ),
        "predict_callable_sha256": _require_sha256(
            item.get("predict_callable_sha256"), label="predict callable hash"
        ),
    }


def _finite_vector(
    value: object, *, candidate_count: int, label: str
) -> np.ndarray:
    vector = np.asarray(value)
    if (
        vector.dtype != np.dtype(np.float64)
        or vector.ndim != 1
        or not vector.flags.c_contiguous
        or vector.shape != (candidate_count,)
        or not np.isfinite(vector).all()
    ):
        _fail(f"{label} must be one finite C-contiguous float64 vector")
    return vector


def _vector_artifact_payload_bytes(
    metadata: Mapping[str, object], values: np.ndarray
) -> bytes:
    return _canonical(metadata, label="vector artifact metadata") + b"\0" + bytes(
        memoryview(np.ascontiguousarray(values, dtype="<f8")).cast("B")
    )


def _replay_vector_artifact(
    value: object,
    *,
    read_exact: ReadExact,
    source: str,
    artifact_role: str,
    fold_id: str | None,
    lineup_ids_sha256: str,
    substrate_receipt_sha256: str,
    producer_contract_sha256: str,
    candidate_count: int,
    training_outcome_member_binding_sha256: str | None,
    heldout_outcome_member_binding_sha256: str | None,
    heldout_member_ids_sha256: str | None,
) -> tuple[np.ndarray, dict[str, object]]:
    metadata, payload, identity = _split_binary_artifact(
        value,
        read_exact=read_exact,
        label=f"{source} {artifact_role} artifact",
    )
    if len(payload) != candidate_count * np.dtype("<f8").itemsize:
        _fail(f"{source} authoritative vector artifact length differs")
    values = _finite_vector(
        np.frombuffer(payload, dtype="<f8").copy(),
        candidate_count=candidate_count,
        label=f"{source} {artifact_role}",
    )
    expected_metadata = {
        "schema_version": VECTOR_ARTIFACT_SCHEMA,
        "source": source,
        "artifact_role": artifact_role,
        "fold_id": fold_id,
        "lineup_ids_sha256": lineup_ids_sha256,
        "substrate_receipt_sha256": substrate_receipt_sha256,
        "producer_contract_sha256": producer_contract_sha256,
        "training_outcome_member_binding_sha256": (
            training_outcome_member_binding_sha256
        ),
        "heldout_outcome_member_binding_sha256": (
            heldout_outcome_member_binding_sha256
        ),
        "heldout_member_ids_sha256": heldout_member_ids_sha256,
        "vector_length": candidate_count,
        "vector_sha256": _vector_sha256(values, lineup_ids_sha256),
    }
    if _canonical(metadata, label="retained vector metadata") != _canonical(
        expected_metadata, label="replayed vector metadata"
    ):
        _fail(f"{source} authoritative vector metadata replay differs")
    if payload != bytes(memoryview(np.ascontiguousarray(values, dtype="<f8")).cast("B")):
        _fail(f"{source} authoritative vector artifact content differs")
    return values, identity


def _producer_contract_from_artifact(
    value: object, *, read_exact: ReadExact, source: str
) -> tuple[dict[str, str], dict[str, object]]:
    body, identity = _canonical_artifact(
        value,
        read_exact=read_exact,
        label=f"{source} producer contract artifact",
    )
    return _producer_contract(body), identity


def _authoritative_producer_receipt(
    value: object,
    *,
    expected_identity: Mapping[str, object],
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    receipt, identity = _canonical_artifact(
        value, read_exact=read_exact, label=label
    )
    authority_pin = _object_identity(
        expected_identity, label=f"{label} independent authority pin"
    )
    if identity != authority_pin:
        _fail(f"{label} differs from independent authority pin")
    return receipt, identity


def build_static_support_producer_receipt_v1(
    *,
    source: str,
    vector_artifact_identity: Mapping[str, object],
    lineup_ids: Sequence[str],
    substrate_receipt: Mapping[str, object],
    producer_contract_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    if source not in SUPPORT_SOURCE_ORDER or source in OUTCOME_AWARE_SUPPORT_SOURCES:
        _fail("static support source must be simulated-tail or novelty-residual")
    ids = _lineup_ids(lineup_ids)
    substrate = _mapping(substrate_receipt, label="substrate receipt")
    substrate_hash = _require_sha256(
        substrate.get("substrate_receipt_sha256"), label="substrate receipt hash"
    )
    if substrate.get("lineup_ids_sha256") != _sha(ids, label="lineup IDs"):
        _fail("static producer lineup universe differs from substrate")
    contract, normalized_contract_identity = _producer_contract_from_artifact(
        producer_contract_identity, read_exact=read_exact, source=source
    )
    contract_hash = _sha(contract, label="producer contract")
    vector, vector_identity = _replay_vector_artifact(
        vector_artifact_identity,
        read_exact=read_exact,
        source=source,
        artifact_role="static-support-vector",
        fold_id=None,
        lineup_ids_sha256=str(substrate["lineup_ids_sha256"]),
        substrate_receipt_sha256=substrate_hash,
        producer_contract_sha256=contract_hash,
        candidate_count=len(ids),
        training_outcome_member_binding_sha256=None,
        heldout_outcome_member_binding_sha256=None,
        heldout_member_ids_sha256=None,
    )
    body = {
        "schema_version": STATIC_PRODUCER_SCHEMA,
        "source": source,
        "producer_contract": contract,
        "producer_contract_identity": normalized_contract_identity,
        "producer_contract_sha256": contract_hash,
        "substrate_receipt_sha256": substrate_hash,
        "lineup_ids_sha256": substrate["lineup_ids_sha256"],
        "vector_sha256": _vector_sha256(
            vector, str(substrate["lineup_ids_sha256"])
        ),
        "vector_artifact_identity": vector_identity,
        "vector_length": len(ids),
        "evidence_origin": "ordinary-r-simulated-or-outcome-blind-residual-only",
        "consumes_historically_outcome_derived_outer_crossfit_evidence": False,
        "uses_no_raw_or_current_heldout_outcomes": True,
        **_false_authorities(),
    }
    return _self_hash(body, "producer_receipt_sha256")


def validate_static_support_producer_receipt_v1(
    value: object,
    *,
    source: str,
    lineup_ids: Sequence[str],
    substrate_receipt: Mapping[str, object],
    expected_producer_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    retained, _identity = _authoritative_producer_receipt(
        value,
        expected_identity=expected_producer_receipt_identity,
        read_exact=read_exact,
        label=f"{source} static producer receipt",
    )
    expected = build_static_support_producer_receipt_v1(
        source=source,
        vector_artifact_identity=_mapping(
            retained.get("vector_artifact_identity"),
            label=f"{source} static vector artifact identity",
        ),
        lineup_ids=lineup_ids,
        substrate_receipt=substrate_receipt,
        producer_contract_identity=_mapping(
            retained.get("producer_contract_identity"),
            label=f"{source} producer contract identity",
        ),
        read_exact=read_exact,
    )
    if _canonical(retained, label="retained static producer") != _canonical(
        expected, label="replayed static producer"
    ):
        _fail(f"{source} static producer receipt replay differs")
    return expected


def _outcome_registry(value: object) -> list[dict[str, object]]:
    rows = list(_sequence(value, label="outcome member registry"))
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(rows):
        item = _mapping(raw, label=f"outcome member[{ordinal}]")
        _exact_keys(
            item,
            {"member_id", "outcome_object_identity"},
            label=f"outcome member[{ordinal}]",
        )
        normalized.append({
            "member_id": _nonempty(
                item.get("member_id"), label=f"outcome member[{ordinal}] ID"
            ),
            "outcome_object_identity": _object_identity(
                item.get("outcome_object_identity"),
                label=f"outcome member[{ordinal}] object",
            ),
        })
    ids = [str(row["member_id"]) for row in normalized]
    if len(ids) < 2 or len(set(ids)) != len(ids) or ids != sorted(ids):
        _fail("outcome member registry must be unique, sorted, and have at least two")
    return normalized


def _outcome_registry_from_artifact(
    value: object, *, read_exact: ReadExact, source: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    body, identity = _canonical_artifact(
        value,
        read_exact=read_exact,
        label=f"{source} outcome member registry artifact",
    )
    _exact_keys(
        body,
        {"schema_version", "outcome_members"},
        label=f"{source} outcome member registry body",
    )
    if body.get("schema_version") != "outer-crossfit-outcome-member-registry/v1":
        _fail(f"{source} outcome member registry schema differs")
    return _outcome_registry(body.get("outcome_members")), identity


def _outer_fold_inputs(
    value: object,
    *,
    source: str,
    outcome_member_registry: Sequence[Mapping[str, object]],
    candidate_count: int,
    lineup_ids_sha256: str,
    substrate_receipt_sha256: str,
    producer_contract_sha256: str,
    read_exact: ReadExact,
) -> tuple[list[dict[str, object]], list[np.ndarray]]:
    rows = list(_sequence(value, label="outer fold inputs"))
    normalized: list[dict[str, object]] = []
    predictions: list[np.ndarray] = []
    heldout_seen: list[str] = []
    registry = _outcome_registry(outcome_member_registry)
    member_ids = [str(row["member_id"]) for row in registry]
    member_set = set(member_ids)
    by_member = {str(row["member_id"]): row for row in registry}
    for ordinal, raw in enumerate(rows):
        item = _mapping(raw, label=f"outer fold[{ordinal}]")
        _exact_keys(
            item,
            {"fold_id", "heldout_member_ids", "prediction_artifact_identity"},
            label=f"outer fold[{ordinal}]",
        )
        fold_id = _nonempty(item.get("fold_id"), label=f"outer fold[{ordinal}] ID")
        heldout = list(
            _sequence(
                item.get("heldout_member_ids"),
                label=f"outer fold[{ordinal}] heldout IDs",
            )
        )
        if (
            not heldout
            or any(type(member) is not str for member in heldout)
            or len(set(heldout)) != len(heldout)
            or heldout != sorted(heldout)
            or not set(heldout).issubset(member_set)
        ):
            _fail("outer fold heldout membership differs")
        training = [member for member in member_ids if member not in set(heldout)]
        training_binding_hash = _sha(
            [by_member[member] for member in training],
            label=f"outer fold[{ordinal}] training outcome member binding",
        )
        heldout_binding_hash = _sha(
            [by_member[member] for member in heldout],
            label=f"outer fold[{ordinal}] heldout outcome member binding",
        )
        prediction, prediction_identity = _replay_vector_artifact(
            item.get("prediction_artifact_identity"),
            read_exact=read_exact,
            source=source,
            artifact_role="outer-fold-prediction",
            fold_id=fold_id,
            lineup_ids_sha256=lineup_ids_sha256,
            substrate_receipt_sha256=substrate_receipt_sha256,
            producer_contract_sha256=producer_contract_sha256,
            candidate_count=candidate_count,
            training_outcome_member_binding_sha256=training_binding_hash,
            heldout_outcome_member_binding_sha256=heldout_binding_hash,
            heldout_member_ids_sha256=_sha(
                heldout, label=f"outer fold[{ordinal}] heldout IDs"
            ),
        )
        normalized.append({
            "fold_id": fold_id,
            "heldout_member_ids": heldout,
            "training_outcome_member_binding_sha256": training_binding_hash,
            "heldout_outcome_member_binding_sha256": heldout_binding_hash,
            "prediction_artifact_identity": prediction_identity,
        })
        predictions.append(prediction)
        heldout_seen.extend(heldout)
    fold_ids = [str(row["fold_id"]) for row in normalized]
    if (
        len(rows) < 2
        or len(set(fold_ids)) != len(fold_ids)
        or fold_ids != sorted(fold_ids)
        or sorted(heldout_seen) != list(member_ids)
        or len(heldout_seen) != len(set(heldout_seen))
    ):
        _fail("outer folds must be sorted and partition every outcome member once")
    return normalized, predictions


def _aggregate_outer_predictions(predictions: Sequence[np.ndarray]) -> np.ndarray:
    stacked = np.stack(predictions, axis=0)
    return np.ascontiguousarray(stacked.mean(axis=0, dtype=np.float64))


def build_outer_crossfit_support_producer_receipt_v1(
    *,
    source: str,
    lineup_ids: Sequence[str],
    substrate_receipt: Mapping[str, object],
    producer_contract_identity: Mapping[str, object],
    outcome_member_registry_identity: Mapping[str, object],
    outer_fold_inputs: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    if source not in OUTCOME_AWARE_SUPPORT_SOURCES:
        _fail("outer-crossfit producer source must be outcome-aware support")
    ids = _lineup_ids(lineup_ids)
    substrate = _mapping(substrate_receipt, label="substrate receipt")
    substrate_hash = _require_sha256(
        substrate.get("substrate_receipt_sha256"), label="substrate receipt hash"
    )
    lineup_hash = _sha(ids, label="lineup IDs")
    if substrate.get("lineup_ids_sha256") != lineup_hash:
        _fail("outer producer lineup universe differs from substrate")
    contract, normalized_contract_identity = _producer_contract_from_artifact(
        producer_contract_identity, read_exact=read_exact, source=source
    )
    contract_hash = _sha(contract, label="producer contract")
    registry, normalized_registry_identity = _outcome_registry_from_artifact(
        outcome_member_registry_identity, read_exact=read_exact, source=source
    )
    member_ids = [str(row["member_id"]) for row in registry]
    folds, predictions = _outer_fold_inputs(
        outer_fold_inputs,
        source=source,
        outcome_member_registry=registry,
        candidate_count=len(ids),
        lineup_ids_sha256=lineup_hash,
        substrate_receipt_sha256=substrate_hash,
        producer_contract_sha256=contract_hash,
        read_exact=read_exact,
    )
    by_member = {str(row["member_id"]): row for row in registry}
    fold_receipts: list[dict[str, object]] = []
    for raw_fold, prediction in zip(folds, predictions, strict=True):
        heldout = list(raw_fold["heldout_member_ids"])
        training = [member for member in member_ids if member not in set(heldout)]
        training_binding = [by_member[member] for member in training]
        fold_receipts.append(_self_hash({
            "schema_version": OUTER_FOLD_SCHEMA,
            "fold_id": raw_fold["fold_id"],
            "training_member_ids": training,
            "heldout_member_ids": heldout,
            "heldout_member_ids_sha256": _sha(
                heldout, label="heldout outcome member IDs"
            ),
            "training_is_exact_registry_complement_of_heldout": True,
            "training_outcome_member_binding_sha256": _sha(
                training_binding, label="training outcome member binding"
            ),
            "heldout_outcome_member_binding_sha256": _sha(
                [by_member[member] for member in heldout],
                label="heldout outcome member binding",
            ),
            "heldout_outcome_content_supplied_to_fit": False,
            "prediction_artifact_identity": raw_fold[
                "prediction_artifact_identity"
            ],
            "prediction_vector_sha256": _vector_sha256(prediction, lineup_hash),
            "prediction_vector_length": len(ids),
        }, "outer_fold_sha256"))
    aggregate = _aggregate_outer_predictions(predictions)
    body = {
        "schema_version": OUTER_PRODUCER_SCHEMA,
        "source": source,
        "producer_contract": contract,
        "producer_contract_identity": normalized_contract_identity,
        "producer_contract_sha256": contract_hash,
        "substrate_receipt_sha256": substrate_hash,
        "lineup_ids_sha256": lineup_hash,
        "outcome_member_registry": registry,
        "outcome_member_registry_identity": normalized_registry_identity,
        "outcome_member_registry_sha256": _sha(
            registry, label="outcome member registry"
        ),
        "outer_fold_count": len(fold_receipts),
        "outer_folds": fold_receipts,
        "outer_folds_sha256": _sha(fold_receipts, label="outer folds"),
        "aggregate_law": "equal-mean-of-all-outer-fold-prediction-vectors",
        "vector_sha256": _vector_sha256(aggregate, lineup_hash),
        "vector_length": len(ids),
        "consumes_historically_outcome_derived_outer_crossfit_evidence": True,
        "uses_no_raw_or_current_heldout_outcomes": True,
        "raw_outcome_rows_exposed_to_composite_selector": False,
        **_false_authorities(),
    }
    return _self_hash(body, "producer_receipt_sha256")


def validate_outer_crossfit_support_producer_receipt_v1(
    value: object,
    *,
    source: str,
    lineup_ids: Sequence[str],
    substrate_receipt: Mapping[str, object],
    expected_producer_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    retained, _identity = _authoritative_producer_receipt(
        value,
        expected_identity=expected_producer_receipt_identity,
        read_exact=read_exact,
        label=f"{source} outer producer receipt",
    )
    retained_folds = list(
        _sequence(retained.get("outer_folds"), label="retained outer folds")
    )
    outer_inputs: list[dict[str, object]] = []
    for ordinal, raw_fold in enumerate(retained_folds):
        fold = _mapping(raw_fold, label=f"retained outer fold[{ordinal}]")
        fold_id = _nonempty(
            fold.get("fold_id"), label=f"retained outer fold[{ordinal}] ID"
        )
        outer_inputs.append({
            "fold_id": fold_id,
            "heldout_member_ids": list(
                _sequence(
                    fold.get("heldout_member_ids"),
                    label=f"retained outer fold[{ordinal}] heldout IDs",
                )
            ),
            "prediction_artifact_identity": _mapping(
                fold.get("prediction_artifact_identity"),
                label=f"retained outer fold[{ordinal}] prediction identity",
            ),
        })
    expected = build_outer_crossfit_support_producer_receipt_v1(
        source=source,
        lineup_ids=lineup_ids,
        substrate_receipt=substrate_receipt,
        producer_contract_identity=_mapping(
            retained.get("producer_contract_identity"),
            label=f"{source} producer contract identity",
        ),
        outcome_member_registry_identity=_mapping(
            retained.get("outcome_member_registry_identity"),
            label=f"{source} outcome registry identity",
        ),
        outer_fold_inputs=outer_inputs,
        read_exact=read_exact,
    )
    if _canonical(retained, label="retained outer producer") != _canonical(
        expected, label="replayed outer producer"
    ):
        _fail(f"{source} outer-crossfit producer receipt replay differs")
    return expected


def _fit_view(
    matrix: np.ndarray, *, heldout_block: str, worlds_per_block: int
) -> tuple[np.ndarray, list[str]]:
    if heldout_block not in WORLD_BLOCKS:
        _fail("heldout block must be one exact canonical ordinary-R block")
    training_blocks = [block for block in WORLD_BLOCKS if block != heldout_block]
    columns = np.concatenate([
        np.arange(
            WORLD_BLOCKS.index(block) * worlds_per_block,
            (WORLD_BLOCKS.index(block) + 1) * worlds_per_block,
            dtype=np.int64,
        )
        for block in training_blocks
    ])
    return np.ascontiguousarray(matrix[:, columns], dtype=np.float64), training_blocks


def _public_strategy_contracts() -> dict[str, dict[str, object]]:
    observed: dict[str, dict[str, object]] = {}
    for row in t230.frozen_extreme_tail_strategies_v1():
        strategy_id = str(row.get("strategy_id"))
        if strategy_id in ENSEMBLE_SOURCE_ORDER:
            observed[strategy_id] = dict(row)
    for row in additions.frozen_preweek_additions_registry_v1():
        strategy_id = str(row.get("strategy_id"))
        if strategy_id in ENSEMBLE_SOURCE_ORDER:
            observed[strategy_id] = dict(row)
    if set(observed) != set(ENSEMBLE_SOURCE_ORDER):
        _fail("public ensemble strategy registry is incomplete")
    for strategy_id in ENSEMBLE_SOURCE_ORDER:
        row = observed[strategy_id]
        identities = ENSEMBLE_SOURCE_IDENTITIES[strategy_id]
        retained = row.get("strategy_sha256")
        if (
            retained != identities["strategy_sha256"]
            or row.get(
                "selector_implementation_sha256",
                row.get("implementation_sha256"),
            )
            != identities["implementation_sha256"]
            or _sha(
                {key: value for key, value in row.items() if key != "strategy_sha256"},
                label=f"{strategy_id} public strategy",
            )
            != retained
        ):
            _fail(f"{strategy_id} public strategy or implementation drifted")
    return observed


def _select_blockmin_fixture(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    worlds_per_block: int,
) -> tuple[list[int], list[dict[str, object]]]:
    """Exact dynamic-width reference; fixture-only and never release authority."""
    block_count = scores.shape[1] // worlds_per_block
    events = [
        [
            scores[
                :,
                block * worlds_per_block:(block + 1) * worlds_per_block,
            ] >= threshold
            for block in range(block_count)
        ]
        for threshold, _operator, _weight in TAIL_RUNGS
    ]
    covered = [
        [np.zeros(worlds_per_block, dtype=bool) for _ in range(block_count)]
        for _ in TAIL_RUNGS
    ]
    block_utility = np.zeros(block_count, dtype=np.int64)
    primary = np.count_nonzero(scores > 200.0, axis=1)
    means = scores.mean(axis=1, dtype=np.float64)
    remaining = set(range(len(lineup_ids)))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < RANKING_DEPTH:
        best: int | None = None
        best_added: np.ndarray | None = None
        best_key: tuple[object, ...] | None = None
        for candidate in sorted(remaining):
            added = np.zeros(block_count, dtype=np.int64)
            for rung, (_threshold, _operator, weight) in enumerate(TAIL_RUNGS):
                for block in range(block_count):
                    added[block] += weight * int(np.count_nonzero(
                        events[rung][block][candidate] & ~covered[rung][block]
                    ))
            after = block_utility + added
            key = (
                tuple(-int(value) for value in np.sort(after)),
                -int(primary[candidate]),
                -float(means[candidate]),
                lineup_ids[candidate],
            )
            if best_key is None or key < best_key:
                best, best_added, best_key = candidate, added, key
        if best is None or best_added is None:
            _fail("fixture block-robust rank ended before 80")
        block_utility += best_added
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "leximin_profile_after": sorted(int(value) for value in block_utility),
            "discovery_primary_event_count": int(primary[best]),
            "discovery_mean_score": float(means[best]),
            "fixture_reference_only": True,
        })
        for rung in range(len(TAIL_RUNGS)):
            for block in range(block_count):
                covered[rung][block] |= events[rung][block][best]
        remaining.remove(best)
    return selected, trace


def _dispatch_upstream_selector(
    *,
    strategy_id: str,
    fit_scores: np.ndarray,
    lineup_ids: Sequence[str],
    worlds_per_block: int,
    execution_mode: str,
) -> tuple[list[int], list[dict[str, object]], str]:
    strategies = _public_strategy_contracts()
    strategy = strategies[strategy_id]
    if strategy_id == "coverage-ge-230-v1":
        selected, trace = t230._select_coverage_packed(
            fit_scores,
            budget=RANKING_DEPTH,
            threshold=230.0,
            operator=">=",
            lineup_ids=lineup_ids,
        )
        tier = "exact-public-executable-replay"
    elif strategy_id == "bounded-tail-ladder-ge-210-250-v1":
        selected, trace = t230._select_ladder_packed(
            fit_scores,
            budget=RANKING_DEPTH,
            rungs=list(strategy["parameters"]["rungs"]),
            lineup_ids=lineup_ids,
        )
        tier = "exact-public-executable-replay"
    elif strategy_id == "block-robust-bounded-tail-ge-210-250-v1":
        if execution_mode == "release":
            selected, trace = t230._select_blockmin_ladder_packed(
                fit_scores,
                budget=RANKING_DEPTH,
                rungs=list(strategy["parameters"]["rungs"]),
                lineup_ids=lineup_ids,
            )
            tier = "exact-public-executable-replay"
        else:
            selected, trace = _select_blockmin_fixture(
                scores=fit_scores,
                lineup_ids=lineup_ids,
                worlds_per_block=worlds_per_block,
            )
            tier = "fixture-reference-replay-not-release-authority"
    elif strategy_id == "convex-excess-expected-max-ge-200-v1":
        rows = np.arange(len(lineup_ids), dtype=np.int64)
        means = fit_scores.mean(axis=1, dtype=np.float64)
        primary = np.count_nonzero(fit_scores > 200.0, axis=1)
        selected, trace = additions._select_convex_expected_max(
            scores=fit_scores,
            canonical_source_rows=rows,
            lineup_ids=lineup_ids,
            means=means,
            primary_counts=primary,
        )
        tier = "exact-public-executable-replay"
    else:  # pragma: no cover
        _fail(f"unsupported upstream selector {strategy_id!r}")
    if len(selected) != RANKING_DEPTH or len(set(selected)) != RANKING_DEPTH:
        _fail("upstream selector did not produce exact rank 80")
    return selected, trace, tier


def _books(
    *, strategy: Mapping[str, object], rank: Sequence[str]
) -> list[dict[str, object]]:
    return [
        _self_hash({
            "schema_version": BOOK_SCHEMA,
            "strategy_id": strategy["strategy_id"],
            "strategy_sha256": strategy["strategy_sha256"],
            "entry_budget": budget,
            "entry_count": budget,
            "ranking_prefix_law": "exact-prefix-of-one-deterministic-rank-80",
            "selected_lineup_ids": list(rank[:budget]),
            "selected_lineup_ids_sha256": _sha(
                list(rank[:budget]), label=f"rank-{budget} lineup IDs"
            ),
            **_false_authorities(),
        }, "book_sha256")
        for budget in ENTRY_BUDGETS
    ]


def build_upstream_selector_result_receipt_v1(
    *,
    strategy_id: str,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    heldout_block: str,
    worlds_per_block: int,
    execution_mode: str,
    authority_lock_identity: Mapping[str, object],
    substrate_receipt: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    if strategy_id not in ENSEMBLE_SOURCE_ORDER:
        _fail("upstream selector ID is not in the fixed ensemble registry")
    ids = _lineup_ids(lineup_ids)
    matrix = _validated_full_matrix(
        full_scores,
        candidate_count=len(ids),
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
    )
    substrate = validate_canonical_substrate_receipt_v1(
        substrate_receipt,
        lineup_ids=ids,
        full_scores=matrix,
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
        authority_lock_identity=authority_lock_identity,
        read_exact=read_exact,
    )
    fit_scores, training_blocks = _fit_view(
        matrix, heldout_block=heldout_block, worlds_per_block=worlds_per_block
    )
    fit_scope = _upstream_fit_scope(
        lineup_ids=ids,
        scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_binding=_mapping(
            substrate["source_binding"], label="replayed substrate source binding"
        ),
        execution_mode=execution_mode,
    )
    selected, trace, replay_tier = _dispatch_upstream_selector(
        strategy_id=strategy_id,
        fit_scores=fit_scores,
        lineup_ids=ids,
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
    )
    strategy = _public_strategy_contracts()[strategy_id]
    rank = [ids[index] for index in selected]
    body = {
        "schema_version": UPSTREAM_RESULT_SCHEMA,
        "strategy_id": strategy_id,
        "strategy_sha256": strategy["strategy_sha256"],
        "implementation_sha256": ENSEMBLE_SOURCE_IDENTITIES[strategy_id][
            "implementation_sha256"
        ],
        "execution_mode": execution_mode,
        "replay_tier": replay_tier,
        "release_eligible": execution_mode == "release",
        "substrate_receipt_sha256": substrate["substrate_receipt_sha256"],
        "fit_scope_binding": fit_scope,
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "heldout_block": heldout_block,
        "training_blocks": training_blocks,
        "ranking_depth": RANKING_DEPTH,
        "selected_lineup_ids": rank,
        "selected_lineup_ids_sha256": _sha(rank, label="upstream rank"),
        "selection_trace": trace,
        "selection_trace_sha256": _sha(trace, label="upstream trace"),
        "books": _books(strategy=strategy, rank=rank),
        "uses_no_raw_or_current_heldout_outcomes": True,
        "consumes_historically_outcome_derived_outer_crossfit_evidence": False,
        **_false_authorities(),
    }
    return _self_hash(body, "upstream_result_sha256")


def validate_upstream_selector_result_receipt_v1(
    value: object,
    **inputs: object,
) -> dict[str, object]:
    retained = _mapping(value, label="upstream selector receipt")
    expected = build_upstream_selector_result_receipt_v1(**inputs)
    if _canonical(retained, label="retained upstream result") != _canonical(
        expected, label="replayed upstream result"
    ):
        _fail("upstream selector result receipt replay differs")
    return expected


def _normalized_average_tie_ranks(values: np.ndarray) -> np.ndarray:
    count = values.size
    if count == 1 or np.all(values == values[0]):
        return np.full(count, 0.5, dtype=np.float64)
    order = sorted(range(count), key=lambda index: (float(values[index]), index))
    result = np.empty(count, dtype=np.float64)
    start = 0
    while start < count:
        stop = start + 1
        while stop < count and values[order[stop]] == values[order[start]]:
            stop += 1
        normalized = ((start + stop - 1) / 2.0) / float(count - 1)
        for position in range(start, stop):
            result[order[position]] = normalized
        start = stop
    return result


def _support_vectors_from_replayed_producers(
    *,
    lineup_ids: Sequence[str],
    substrate_receipt: Mapping[str, object],
    authority_lock: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, np.ndarray], list[dict[str, object]]]:
    normalized_pins = _normalized_producer_receipt_identities(
        authority_lock.get("producer_receipt_identities")
    )
    arrays: dict[str, np.ndarray] = {}
    pointers: list[dict[str, object]] = []
    for source in SUPPORT_SOURCE_ORDER:
        if source in OUTCOME_AWARE_SUPPORT_SOURCES:
            receipt = validate_outer_crossfit_support_producer_receipt_v1(
                normalized_pins[source],
                source=source,
                lineup_ids=lineup_ids,
                substrate_receipt=substrate_receipt,
                expected_producer_receipt_identity=normalized_pins[source],
                read_exact=read_exact,
            )
            contract_hash = str(receipt["producer_contract_sha256"])
            predictions = []
            for raw_fold in _sequence(receipt["outer_folds"], label="outer folds"):
                fold = _mapping(raw_fold, label="outer fold")
                fold_id = str(fold["fold_id"])
                vector, _artifact_identity = _replay_vector_artifact(
                    fold["prediction_artifact_identity"],
                    read_exact=read_exact,
                    source=source,
                    artifact_role="outer-fold-prediction",
                    fold_id=fold_id,
                    lineup_ids_sha256=str(receipt["lineup_ids_sha256"]),
                    substrate_receipt_sha256=str(
                        receipt["substrate_receipt_sha256"]
                    ),
                    producer_contract_sha256=contract_hash,
                    candidate_count=len(lineup_ids),
                    training_outcome_member_binding_sha256=str(
                        fold["training_outcome_member_binding_sha256"]
                    ),
                    heldout_outcome_member_binding_sha256=str(
                        fold["heldout_outcome_member_binding_sha256"]
                    ),
                    heldout_member_ids_sha256=_sha(
                        list(
                            _sequence(
                                fold["heldout_member_ids"],
                                label="outer fold heldout IDs",
                            )
                        ),
                        label="outer fold heldout IDs",
                    ),
                )
                predictions.append(vector)
            vector = _aggregate_outer_predictions(predictions)
        else:
            receipt = validate_static_support_producer_receipt_v1(
                normalized_pins[source],
                source=source,
                lineup_ids=lineup_ids,
                substrate_receipt=substrate_receipt,
                expected_producer_receipt_identity=normalized_pins[source],
                read_exact=read_exact,
            )
            vector, _artifact_identity = _replay_vector_artifact(
                receipt["vector_artifact_identity"],
                read_exact=read_exact,
                source=source,
                artifact_role="static-support-vector",
                fold_id=None,
                lineup_ids_sha256=str(receipt["lineup_ids_sha256"]),
                substrate_receipt_sha256=str(
                    receipt["substrate_receipt_sha256"]
                ),
                producer_contract_sha256=str(
                    receipt["producer_contract_sha256"]
                ),
                candidate_count=len(lineup_ids),
                training_outcome_member_binding_sha256=None,
                heldout_outcome_member_binding_sha256=None,
                heldout_member_ids_sha256=None,
            )
        if receipt["substrate_receipt_sha256"] != substrate_receipt.get(
            "substrate_receipt_sha256"
        ):
            _fail(f"{source} producer substrate differs")
        arrays[source] = vector
        pointers.append({
            "source": source,
            "producer_receipt_sha256": receipt["producer_receipt_sha256"],
            "producer_contract_sha256": receipt["producer_contract_sha256"],
            "producer_receipt_object_identity": normalized_pins[source],
            "vector_sha256": receipt["vector_sha256"],
            "substrate_receipt_sha256": receipt["substrate_receipt_sha256"],
        })
    return arrays, pointers


def _hybrid_shortlist(
    *, lineup_ids: Sequence[str], arrays: Mapping[str, np.ndarray]
) -> tuple[list[int], list[dict[str, object]], list[int]]:
    normalized = {
        source: _normalized_average_tie_ranks(arrays[source])
        for source in SUPPORT_SOURCE_ORDER
    }
    shortlist: set[int] = set()
    sleeves: list[dict[str, object]] = []
    for source in SUPPORT_SOURCE_ORDER:
        ordered = sorted(
            range(len(lineup_ids)),
            key=lambda index: (-float(normalized[source][index]), lineup_ids[index]),
        )
        selected = ordered[:SLEEVE_SIZE]
        shortlist.update(selected)
        sleeves.append({
            "source": source,
            "fixed_count": SLEEVE_SIZE,
            "selected_lineup_ids": [lineup_ids[index] for index in selected],
        })
    aggregate = np.zeros(len(lineup_ids), dtype=np.float64)
    for source in SUPPORT_SOURCE_ORDER:
        aggregate += SUPPORT_WEIGHTS[source] * normalized[source]
    supplement = sorted(
        (index for index in range(len(lineup_ids)) if index not in shortlist),
        key=lambda index: (-float(aggregate[index]), lineup_ids[index]),
    )[: RANKING_DEPTH - len(shortlist)]
    shortlist.update(supplement)
    if len(shortlist) != RANKING_DEPTH:
        _fail("fixed sleeves and supplement cannot produce exact shortlist 80")
    return sorted(shortlist, key=lambda index: lineup_ids[index]), sleeves, supplement


def _borda_rank(
    *, lineup_ids: Sequence[str], ranks: Mapping[str, Sequence[str]]
) -> tuple[list[str], list[dict[str, object]]]:
    points = {lineup_id: 0 for lineup_id in lineup_ids}
    presence = {lineup_id: 0 for lineup_id in lineup_ids}
    best_rank = {lineup_id: RANKING_DEPTH for lineup_id in lineup_ids}
    source_positions: dict[str, dict[str, int]] = {}
    for source in ENSEMBLE_SOURCE_ORDER:
        positions = {lineup_id: rank for rank, lineup_id in enumerate(ranks[source])}
        source_positions[source] = positions
        for lineup_id, rank in positions.items():
            points[lineup_id] += RANKING_DEPTH - rank
            presence[lineup_id] += 1
            best_rank[lineup_id] = min(best_rank[lineup_id], rank)
    union = [lineup_id for lineup_id in lineup_ids if presence[lineup_id]]
    if len(union) < RANKING_DEPTH:
        _fail("upstream rank union cannot produce exact ensemble rank 80")
    selected = sorted(
        union,
        key=lambda lineup_id: (
            -points[lineup_id],
            -presence[lineup_id],
            best_rank[lineup_id],
            lineup_id,
        ),
    )[:RANKING_DEPTH]
    trace = [
        {
            "selection_rank": rank,
            "lineup_id": lineup_id,
            "borda_points": points[lineup_id],
            "source_rank_presence_count": presence[lineup_id],
            "best_zero_based_source_rank": best_rank[lineup_id],
            "source_zero_based_ranks": {
                source: source_positions[source].get(lineup_id)
                for source in ENSEMBLE_SOURCE_ORDER
            },
        }
        for rank, lineup_id in enumerate(selected)
    ]
    return selected, trace


_LOCAL_EXECUTABLE_CALLABLES: Final = (
    "_fail",
    "_mapping",
    "_sequence",
    "_exact_keys",
    "_sha",
    "_canonical",
    "_self_hash",
    "_false_authorities",
    "_require_sha256",
    "_nonempty",
    "_object_identity",
    "_read_exact_bytes",
    "_parse_canonical_json",
    "_canonical_artifact",
    "_split_binary_artifact",
    "_lineup_ids",
    "_validated_full_matrix",
    "_matrix_sha256",
    "_vector_sha256",
    "_normalized_source_binding",
    "_normalized_producer_receipt_identities",
    "_authority_lock_body",
    "build_fixture_composite_authority_lock_v1",
    "_replay_composite_authority_lock",
    "_producer_authority_lock_body",
    "build_fixture_producer_authority_lock_v1",
    "_replay_producer_authority_lock",
    "_matrix_artifact_payload_bytes",
    "_replay_matrix_artifact",
    "_replay_authoritative_source_artifacts",
    "_source_binding",
    "_upstream_fit_scope",
    "build_canonical_substrate_receipt_v1",
    "validate_canonical_substrate_receipt_v1",
    "_producer_contract",
    "_finite_vector",
    "_vector_artifact_payload_bytes",
    "_replay_vector_artifact",
    "_producer_contract_from_artifact",
    "_authoritative_producer_receipt",
    "build_static_support_producer_receipt_v1",
    "validate_static_support_producer_receipt_v1",
    "_outcome_registry",
    "_outcome_registry_from_artifact",
    "_outer_fold_inputs",
    "_aggregate_outer_predictions",
    "build_outer_crossfit_support_producer_receipt_v1",
    "validate_outer_crossfit_support_producer_receipt_v1",
    "_fit_view",
    "_public_strategy_contracts",
    "_select_blockmin_fixture",
    "_dispatch_upstream_selector",
    "_books",
    "build_upstream_selector_result_receipt_v1",
    "validate_upstream_selector_result_receipt_v1",
    "_normalized_average_tie_ranks",
    "_support_vectors_from_replayed_producers",
    "_hybrid_shortlist",
    "_borda_rank",
    "build_hybrid_support_retrieval_v1",
    "build_fixed_selector_ensemble_v1",
    "validate_hybrid_support_retrieval_v1",
    "validate_fixed_selector_ensemble_v1",
    "_callable_source_identity",
    "_module_executable_identity",
    "_implementation_body",
    "_strategy_bodies",
    "_contract_identities_unchecked",
    "_guard_literal_contracts",
    "frozen_composite_retrieval_implementation_v1",
    "frozen_composite_retrieval_registry_v1",
)


def _callable_source_identity(value: object, *, logical_name: str) -> dict[str, object]:
    if not callable(value):
        _fail(f"executable callable {logical_name} is absent")
    try:
        source = inspect.getsource(value).encode("utf-8")
    except (OSError, TypeError) as exc:
        raise CorpusCompositeRetrievalError(
            f"executable callable {logical_name} has no source"
        ) from exc
    return {
        "logical_name": logical_name,
        "source_bytes": len(source),
        "source_sha256": sha256(source).hexdigest(),
    }


def _module_executable_identity(value: object, *, logical_name: str) -> dict[str, object]:
    """Bind a full dependency module blob and every live Python function in it."""
    try:
        module_source = inspect.getsource(value).encode("utf-8")
        namespace = vars(value)
    except (OSError, TypeError) as exc:
        raise CorpusCompositeRetrievalError(
            f"dependency module {logical_name} has no inspectable source"
        ) from exc
    functions = [
        _callable_source_identity(function, logical_name=f"{logical_name}.{name}")
        for name, function in sorted(namespace.items())
        if inspect.isfunction(function)
    ]
    if not functions:
        _fail(f"dependency module {logical_name} has no executable functions")
    return {
        "logical_name": logical_name,
        "module_source_bytes": len(module_source),
        "module_source_sha256": sha256(module_source).hexdigest(),
        "live_function_sources": functions,
        "live_function_sources_sha256": _sha(
            functions, label=f"{logical_name} live function sources"
        ),
    }


def _implementation_body() -> dict[str, object]:
    local = [
        _callable_source_identity(globals().get(name), logical_name=name)
        for name in _LOCAL_EXECUTABLE_CALLABLES
    ]
    external_values = (
        (
            "t230.frozen_extreme_tail_strategies_v1",
            t230.frozen_extreme_tail_strategies_v1,
        ),
        (
            "additions.frozen_preweek_additions_registry_v1",
            additions.frozen_preweek_additions_registry_v1,
        ),
        ("t230._select_coverage_packed", t230._select_coverage_packed),
        ("t230._select_ladder_packed", t230._select_ladder_packed),
        ("t230._select_blockmin_ladder_packed", t230._select_blockmin_ladder_packed),
        (
            "additions._select_convex_expected_max",
            additions._select_convex_expected_max,
        ),
        (
            "preweek.build_extreme_tail_preweek_fit_scope_binding_v1",
            preweek.build_extreme_tail_preweek_fit_scope_binding_v1,
        ),
        ("composite.canonical_json_bytes", canonical_json_bytes),
        ("composite.canonical_sha256", canonical_sha256),
        ("legal.canonical_json_bytes", legal.canonical_json_bytes),
        ("legal.canonical_sha256", legal.canonical_sha256),
    )
    external = [
        _callable_source_identity(value, logical_name=name)
        for name, value in external_values
    ]
    dependency_modules = [
        _module_executable_identity(module, logical_name=name)
        for name, module in (
            ("corpus_extreme_tail_retrieval_suite", t230),
            ("corpus_extreme_tail_preweek_additions", additions),
            ("corpus_extreme_tail_preweek_selectors", preweek),
            ("corpus_legal_feasibility", legal),
        )
    ]
    return {
        "schema_version": IMPLEMENTATION_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "local_executable_callables": local,
        "external_executable_callables": external,
        "dependency_module_executable_identities": dependency_modules,
        "contract_constant_registry": {
            "contract_schema": CONTRACT_SCHEMA,
            "implementation_schema": IMPLEMENTATION_SCHEMA,
            "substrate_schema": SUBSTRATE_SCHEMA,
            "source_manifest_schema": SOURCE_MANIFEST_SCHEMA,
            "source_member_schema": SOURCE_MEMBER_SCHEMA,
            "source_matrix_schema": SOURCE_MATRIX_SCHEMA,
            "source_mask_schema": SOURCE_MASK_SCHEMA,
            "source_occurrence_schema": SOURCE_OCCURRENCE_SCHEMA,
            "vector_artifact_schema": VECTOR_ARTIFACT_SCHEMA,
            "authority_lock_schema": AUTHORITY_LOCK_SCHEMA,
            "producer_authority_lock_schema": PRODUCER_AUTHORITY_LOCK_SCHEMA,
            "static_producer_schema": STATIC_PRODUCER_SCHEMA,
            "outer_producer_schema": OUTER_PRODUCER_SCHEMA,
            "outer_fold_schema": OUTER_FOLD_SCHEMA,
            "upstream_result_schema": UPSTREAM_RESULT_SCHEMA,
            "receipt_schema": RECEIPT_SCHEMA,
            "book_schema": BOOK_SCHEMA,
            "hybrid_strategy_id": HYBRID_STRATEGY_ID,
            "ensemble_strategy_id": ENSEMBLE_STRATEGY_ID,
            "support_source_order": list(SUPPORT_SOURCE_ORDER),
            "outcome_aware_support_sources": sorted(
                OUTCOME_AWARE_SUPPORT_SOURCES
            ),
            "support_weights": dict(SUPPORT_WEIGHTS),
            "ensemble_source_order": list(ENSEMBLE_SOURCE_ORDER),
            "ensemble_source_identities": ENSEMBLE_SOURCE_IDENTITIES,
            "frozen_set_objective_id": FROZEN_SET_OBJECTIVE_ID,
            "frozen_set_objective_sha256": FROZEN_SET_OBJECTIVE_SHA256,
            "frozen_set_implementation_sha256": (
                FROZEN_SET_IMPLEMENTATION_SHA256
            ),
            "tail_rungs": [list(rung) for rung in TAIL_RUNGS],
            "false_authority_fields": list(_FALSE_AUTHORITY_FIELDS),
        },
        "world_block_registry": list(WORLD_BLOCKS),
        "production_worlds_per_block": PRODUCTION_WORLDS_PER_BLOCK,
        "fixture_gate": "dynamic-width-reference-never-release-authority",
        "support_normalization": (
            "average-tie-empirical-rank;all-equal-vector-is-one-half"
        ),
        "hybrid_sleeves": {
            "source_order": list(SUPPORT_SOURCE_ORDER),
            "per_source_count": SLEEVE_SIZE,
            "weights": dict(SUPPORT_WEIGHTS),
            "missing_source": "fail-closed-no-renormalization",
        },
        "source_authority": (
            "fixture-mechanics-or-literal-reviewed-release-lock-rooted-exact-"
            "manifest-member-matrix-mask-occurrence-replay"
        ),
        "producer_authority": (
            "review-lock-pinned-exact-producer-contract-outcome-registry-"
            "receipt-and-vector-artifact-replay"
        ),
        "release_authority_lock_frozen": (
            FROZEN_RELEASE_AUTHORITY_LOCK_IDENTITY is not None
            and FROZEN_RELEASE_PRODUCER_AUTHORITY_LOCK_IDENTITY is not None
        ),
        "frozen_release_source_authority_lock_identity": (
            FROZEN_RELEASE_AUTHORITY_LOCK_IDENTITY
        ),
        "frozen_release_producer_authority_lock_identity": (
            FROZEN_RELEASE_PRODUCER_AUTHORITY_LOCK_IDENTITY
        ),
        "hybrid_set_objective": {
            "strategy_id": FROZEN_SET_OBJECTIVE_ID,
            "strategy_sha256": FROZEN_SET_OBJECTIVE_SHA256,
            "implementation_sha256": FROZEN_SET_IMPLEMENTATION_SHA256,
            "rungs": [
                {"threshold": threshold, "operator": operator, "weight": weight}
                for threshold, operator, weight in TAIL_RUNGS
            ],
        },
        "ensemble": {
            "source_order": list(ENSEMBLE_SOURCE_ORDER),
            "source_identities": ENSEMBLE_SOURCE_IDENTITIES,
            "points": "80-minus-zero-based-rank",
            "missing_source": "fail-closed-no-renormalization",
            "ties": [
                "descending-total-borda-points",
                "descending-source-rank-presence-count",
                "ascending-best-zero-based-source-rank",
                "ascending-lineup-id",
            ],
        },
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "prefix_law": "one-rank80-with-exact-4-14-80-prefix-books",
        "raw_outcome_interface": False,
        "identity_feature_interface": False,
        "heldout_score_selection_interface": False,
        **_false_authorities(),
    }


def _strategy_bodies(implementation_hash: str) -> dict[str, dict[str, object]]:
    common = {
        "schema_version": CONTRACT_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": implementation_hash,
        "world_block_registry": list(WORLD_BLOCKS),
        "release_worlds_per_block": PRODUCTION_WORLDS_PER_BLOCK,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "prefix_law": "one-rank80-with-exact-4-14-80-prefix-books",
        "source_law": "exact-read-authority-lock-rooted-canonical-substrate-only",
        "forbidden_inputs": [
            "raw-outcome-rows",
            "current-heldout-outcomes",
            "player-team-contest-or-slate-identity-features",
            "heldout-score-columns-used-for-selection",
            "free-lineage-hashes",
            "free-selector-ranks",
            "caller-selected-sleeves-weights-or-ties",
            "caller-minted-release-source-or-producer-authority-locks",
        ],
        **_false_authorities(),
    }
    return {
        HYBRID_STRATEGY_ID: {
            **common,
            "strategy_id": HYBRID_STRATEGY_ID,
            "method": "replayed-four-sleeve-then-finite-t230-objective-v1",
            "support_source_order": list(SUPPORT_SOURCE_ORDER),
            "outcome_aware_sources": sorted(OUTCOME_AWARE_SUPPORT_SOURCES),
            "outcome_aware_input_law": (
                "exact-read-reviewed-lock-pinned-producer-contract-outcome-"
                "registry-receipt-vector-artifacts-and-exact-outer-fold-"
                "training-complements"
            ),
            "sleeve_counts": {
                source: SLEEVE_SIZE for source in SUPPORT_SOURCE_ORDER
            },
            "supplement_weights": dict(SUPPORT_WEIGHTS),
            "missing_source_law": "fail-closed-no-weight-renormalization",
            "set_objective_id": FROZEN_SET_OBJECTIVE_ID,
            "set_objective_sha256": FROZEN_SET_OBJECTIVE_SHA256,
            "set_objective_implementation_sha256": (
                FROZEN_SET_IMPLEMENTATION_SHA256
            ),
            "consumes_historically_outcome_derived_outer_crossfit_evidence": True,
            "uses_no_raw_or_current_heldout_outcomes": True,
        },
        ENSEMBLE_STRATEGY_ID: {
            **common,
            "strategy_id": ENSEMBLE_STRATEGY_ID,
            "method": "replayed-fixed-equal-weight-borda-rank80-v1",
            "selector_source_order": list(ENSEMBLE_SOURCE_ORDER),
            "selector_source_identities": ENSEMBLE_SOURCE_IDENTITIES,
            "selector_weights": {
                source: 1 for source in ENSEMBLE_SOURCE_ORDER
            },
            "rank_points": "80-minus-zero-based-rank",
            "missing_rank_points": 0,
            "missing_source_law": "fail-closed-no-weight-renormalization",
            "consumes_historically_outcome_derived_outer_crossfit_evidence": False,
            "uses_no_raw_or_current_heldout_outcomes": True,
        },
    }


def _contract_identities_unchecked() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    implementation = _self_hash(_implementation_body(), "implementation_sha256")
    strategies = {
        strategy_id: _self_hash(body, "strategy_sha256")
        for strategy_id, body in _strategy_bodies(
            str(implementation["implementation_sha256"])
        ).items()
    }
    return implementation, strategies


def _guard_literal_contracts() -> None:
    implementation, strategies = _contract_identities_unchecked()
    if implementation["implementation_sha256"] != EXPECTED_IMPLEMENTATION_SHA256:
        _fail("composite executable implementation identity drifted")
    observed = {
        strategy_id: strategy["strategy_sha256"]
        for strategy_id, strategy in strategies.items()
    }
    if observed != EXPECTED_STRATEGY_SHA256S:
        _fail("composite strategy identity drifted")
    _public_strategy_contracts()
    if (
        tuple(t230.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or t230.RANKING_DEPTH != RANKING_DEPTH
        or tuple(t230.TAIL_RUNGS) != TAIL_RUNGS
        or tuple(preweek._WORLD_BLOCKS) != WORLD_BLOCKS
        or preweek._PRODUCTION_WORLDS_PER_BLOCK
        != PRODUCTION_WORLDS_PER_BLOCK
    ):
        _fail("canonical world, budget, or T230 dependency drifted")


def frozen_composite_retrieval_implementation_v1() -> dict[str, object]:
    _guard_literal_contracts()
    return _contract_identities_unchecked()[0]


def frozen_composite_retrieval_registry_v1() -> list[dict[str, object]]:
    _guard_literal_contracts()
    strategies = _contract_identities_unchecked()[1]
    return [strategies[HYBRID_STRATEGY_ID], strategies[ENSEMBLE_STRATEGY_ID]]


def build_hybrid_support_retrieval_v1(
    *,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    heldout_block: str,
    worlds_per_block: int,
    execution_mode: str,
    authority_lock_identity: Mapping[str, object],
    producer_authority_lock_identity: Mapping[str, object],
    substrate_receipt: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Replay four producers, shortlist exactly 80, and apply raw T230."""
    _guard_literal_contracts()
    ids = _lineup_ids(lineup_ids)
    matrix = _validated_full_matrix(
        full_scores,
        candidate_count=len(ids),
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
    )
    substrate = validate_canonical_substrate_receipt_v1(
        substrate_receipt,
        lineup_ids=ids,
        full_scores=matrix,
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
        authority_lock_identity=authority_lock_identity,
        read_exact=read_exact,
    )
    source_authority_lock, normalized_lock_identity = _replay_composite_authority_lock(
        authority_lock_identity,
        read_exact=read_exact,
        execution_mode=execution_mode,
    )
    producer_authority_lock, normalized_producer_lock_identity = (
        _replay_producer_authority_lock(
            producer_authority_lock_identity,
            source_authority_lock_identity=normalized_lock_identity,
            substrate_receipt_sha256=str(substrate["substrate_receipt_sha256"]),
            read_exact=read_exact,
            execution_mode=execution_mode,
        )
    )
    fit_scores, training_blocks = _fit_view(
        matrix, heldout_block=heldout_block, worlds_per_block=worlds_per_block
    )
    fit_scope = _upstream_fit_scope(
        lineup_ids=ids,
        scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_binding=_mapping(
            substrate["source_binding"], label="replayed substrate source binding"
        ),
        execution_mode=execution_mode,
    )
    arrays, producer_pointers = _support_vectors_from_replayed_producers(
        lineup_ids=ids,
        substrate_receipt=substrate,
        authority_lock=producer_authority_lock,
        read_exact=read_exact,
    )
    shortlist, sleeves, supplement = _hybrid_shortlist(
        lineup_ids=ids, arrays=arrays
    )
    shortlist_ids = [ids[index] for index in shortlist]
    shortlist_scores = np.ascontiguousarray(
        fit_scores[np.asarray(shortlist, dtype=np.int64)], dtype=np.float64
    )
    set_strategy = _public_strategy_contracts()[FROZEN_SET_OBJECTIVE_ID]
    selected_local, objective_trace = t230._select_ladder_packed(
        shortlist_scores,
        budget=RANKING_DEPTH,
        rungs=list(set_strategy["parameters"]["rungs"]),
        lineup_ids=shortlist_ids,
    )
    if len(selected_local) != RANKING_DEPTH:
        _fail("raw T230 set objective did not produce exact rank 80")
    rank = [shortlist_ids[index] for index in selected_local]
    strategy = frozen_composite_retrieval_registry_v1()[0]
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "strategy_id": HYBRID_STRATEGY_ID,
        "strategy_sha256": strategy["strategy_sha256"],
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
        "execution_mode": execution_mode,
        "release_eligible": execution_mode == "release",
        "authority_lock_identity": normalized_lock_identity,
        "authority_lock_sha256": source_authority_lock["authority_lock_sha256"],
        "producer_authority_lock_identity": normalized_producer_lock_identity,
        "producer_authority_lock_sha256": producer_authority_lock[
            "producer_authority_lock_sha256"
        ],
        "substrate_receipt_sha256": substrate["substrate_receipt_sha256"],
        "fit_scope_binding": fit_scope,
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "heldout_block": heldout_block,
        "training_blocks": training_blocks,
        "support_producer_pointers": producer_pointers,
        "support_producer_pointers_sha256": _sha(
            producer_pointers, label="support producer pointers"
        ),
        "normalization_law": "average-tie-empirical-rank",
        "sleeves": sleeves,
        "sleeves_sha256": _sha(sleeves, label="hybrid sleeves"),
        "shortlist_lineup_ids": shortlist_ids,
        "shortlist_lineup_ids_sha256": _sha(shortlist_ids, label="shortlist"),
        "supplement_lineup_ids": [ids[index] for index in supplement],
        "supplement_weights": dict(SUPPORT_WEIGHTS),
        "set_objective_id": FROZEN_SET_OBJECTIVE_ID,
        "set_objective_sha256": FROZEN_SET_OBJECTIVE_SHA256,
        "set_objective_implementation_sha256": FROZEN_SET_IMPLEMENTATION_SHA256,
        "set_objective_rungs": [
            {"threshold": threshold, "operator": operator, "weight": weight}
            for threshold, operator, weight in TAIL_RUNGS
        ],
        "set_objective_trace": objective_trace,
        "set_objective_trace_sha256": _sha(
            objective_trace, label="set objective trace"
        ),
        "ranking_depth": RANKING_DEPTH,
        "selected_lineup_ids": rank,
        "selected_lineup_ids_sha256": _sha(rank, label="hybrid rank"),
        "books": _books(strategy=strategy, rank=rank),
        "consumes_historically_outcome_derived_outer_crossfit_evidence": True,
        "uses_no_raw_or_current_heldout_outcomes": True,
        **_false_authorities(),
    }
    return _self_hash(body, "receipt_sha256")


def validate_hybrid_support_retrieval_v1(
    value: object,
    **inputs: object,
) -> dict[str, object]:
    retained = _mapping(value, label="hybrid receipt")
    expected = build_hybrid_support_retrieval_v1(**inputs)
    if _canonical(retained, label="retained hybrid") != _canonical(
        expected, label="replayed hybrid"
    ):
        _fail("hybrid receipt canonical replay differs")
    return expected


def build_fixed_selector_ensemble_v1(
    *,
    lineup_ids: Sequence[str],
    full_scores: np.ndarray,
    heldout_block: str,
    worlds_per_block: int,
    execution_mode: str,
    authority_lock_identity: Mapping[str, object],
    substrate_receipt: Mapping[str, object],
    upstream_selector_receipts: Mapping[str, Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Replay all four public selectors and aggregate their exact ranks."""
    _guard_literal_contracts()
    ids = _lineup_ids(lineup_ids)
    matrix = _validated_full_matrix(
        full_scores,
        candidate_count=len(ids),
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
    )
    substrate = validate_canonical_substrate_receipt_v1(
        substrate_receipt,
        lineup_ids=ids,
        full_scores=matrix,
        worlds_per_block=worlds_per_block,
        execution_mode=execution_mode,
        authority_lock_identity=authority_lock_identity,
        read_exact=read_exact,
    )
    authority_lock, normalized_lock_identity = _replay_composite_authority_lock(
        authority_lock_identity,
        read_exact=read_exact,
        execution_mode=execution_mode,
    )
    receipts = _mapping(upstream_selector_receipts, label="upstream receipts")
    if set(receipts) != set(ENSEMBLE_SOURCE_ORDER):
        _fail("all four upstream selector receipts are required; no renormalization")
    ranks: dict[str, list[str]] = {}
    pointers: list[dict[str, object]] = []
    common_fit_scope_hash: str | None = None
    for strategy_id in ENSEMBLE_SOURCE_ORDER:
        replayed = validate_upstream_selector_result_receipt_v1(
            receipts[strategy_id],
            strategy_id=strategy_id,
            lineup_ids=ids,
            full_scores=matrix,
            heldout_block=heldout_block,
            worlds_per_block=worlds_per_block,
            execution_mode=execution_mode,
            authority_lock_identity=normalized_lock_identity,
            substrate_receipt=substrate,
            read_exact=read_exact,
        )
        fit_hash = str(replayed["fit_scope_binding_sha256"])
        if common_fit_scope_hash is None:
            common_fit_scope_hash = fit_hash
        elif fit_hash != common_fit_scope_hash:
            _fail("ensemble upstream selectors do not share one exact fit scope")
        rank = list(replayed["selected_lineup_ids"])
        if len(rank) != RANKING_DEPTH or len(set(rank)) != RANKING_DEPTH:
            _fail("replayed upstream selector rank is not exact unique 80")
        ranks[strategy_id] = rank
        pointers.append({
            "strategy_id": strategy_id,
            "strategy_sha256": replayed["strategy_sha256"],
            "implementation_sha256": replayed["implementation_sha256"],
            "upstream_result_sha256": replayed["upstream_result_sha256"],
            "fit_scope_binding_sha256": fit_hash,
            "selected_lineup_ids_sha256": replayed["selected_lineup_ids_sha256"],
            "replay_tier": replayed["replay_tier"],
        })
    rank, trace = _borda_rank(lineup_ids=ids, ranks=ranks)
    strategy = frozen_composite_retrieval_registry_v1()[1]
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "strategy_id": ENSEMBLE_STRATEGY_ID,
        "strategy_sha256": strategy["strategy_sha256"],
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
        "execution_mode": execution_mode,
        "release_eligible": execution_mode == "release",
        "authority_lock_identity": normalized_lock_identity,
        "authority_lock_sha256": authority_lock["authority_lock_sha256"],
        "substrate_receipt_sha256": substrate["substrate_receipt_sha256"],
        "fit_scope_binding_sha256": common_fit_scope_hash,
        "heldout_block": heldout_block,
        "source_order": list(ENSEMBLE_SOURCE_ORDER),
        "source_weights": {source: 1 for source in ENSEMBLE_SOURCE_ORDER},
        "missing_source_law": "fail-closed-no-weight-renormalization",
        "upstream_result_pointers": pointers,
        "upstream_result_pointers_sha256": _sha(
            pointers, label="upstream result pointers"
        ),
        "aggregation_law": "equal-weight-borda-80-minus-zero-based-rank",
        "ranking_depth": RANKING_DEPTH,
        "selected_lineup_ids": rank,
        "selected_lineup_ids_sha256": _sha(rank, label="ensemble rank"),
        "selection_trace": trace,
        "selection_trace_sha256": _sha(trace, label="ensemble trace"),
        "books": _books(strategy=strategy, rank=rank),
        "consumes_historically_outcome_derived_outer_crossfit_evidence": False,
        "uses_no_raw_or_current_heldout_outcomes": True,
        **_false_authorities(),
    }
    return _self_hash(body, "receipt_sha256")


def validate_fixed_selector_ensemble_v1(
    value: object,
    **inputs: object,
) -> dict[str, object]:
    retained = _mapping(value, label="ensemble receipt")
    expected = build_fixed_selector_ensemble_v1(**inputs)
    if _canonical(retained, label="retained ensemble") != _canonical(
        expected, label="replayed ensemble"
    ):
        _fail("ensemble receipt canonical replay differs")
    return expected
