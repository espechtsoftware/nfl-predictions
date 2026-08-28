"""Immutable R6-world decoder for the native hard-230 population successor.

The R6 bank stores one generation-pinned float32 NPZ per slate/world block,
while the hard-230 successor deliberately accepts only an exact, sorted
``PlayerSpec`` registry and a C-contiguous little-endian int64 milli-DK
matrix.  This module is the narrow conversion boundary between those two
contracts.

The boundary exact-opens the existing point-in-time later-source freeze,
uses the proven current-bank evaluator NPZ loader, aligns every block to the
PIT catalog, applies one explicit float32-to-milli conversion law, and
publishes a source member, matrix artifact, and derivation proof create-once.
It never materializes candidate totals, tail lines, realized outcomes, ranks,
field data, ownership, payouts, or held-out blocks excluded from the fit.

Storage is injected.  The module neither lists a bucket nor resolves a
current generation and grants no scoring, selection, promotion, or production
authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Final, Protocol
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_generation_additions as source
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as evaluator,
)
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw


CONTRACT_ID: Final = "20260828-hard230-r6-source-decoder-v1"
SOURCE_MEMBER_SCHEMA: Final = "hard230-r6-source-member/v1"
MATRIX_ARTIFACT_SCHEMA: Final = "hard230-r6-fit-score-matrix-authority/v1"
DERIVATION_PROOF_SCHEMA: Final = "hard230-r6-matrix-derivation-proof/v1"
HEADER_SMOKE_SCHEMA: Final = "hard230-r6-world-artifact-header-smoke/v1"
CONVERSION_LAW_ID: Final = (
    "float32-promote-float64-times-1000-rint-ties-even-int64-le-v1"
)
WORLD_BLOCKS: Final = successor.WORLD_BLOCKS
WORLDS_PER_BLOCK: Final = successor.PRODUCTION_WORLDS_PER_BLOCK
MAX_SOURCE_FREEZE_BYTES: Final = 8_000_000
CONVERSION_ROW_CHUNK: Final = 32
MATRIX_ENCODING: Final = source.SCORE_MATRIX_ENCODING

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_realized_outcomes",
    "uses_heldout_scores",
    "historical_scoring_licensed",
    "selector_authority",
    "publication_authority",
    "promotion_authority",
    "decision_authority",
    "production_change_licensed",
    "graph_mutation_licensed",
)


class Hard230R6SourceDecoderV1Error(ValueError):
    """The source identity, NPZ surface, conversion, or publication failed."""


class ReadExact(Protocol):
    def __call__(self, identity: Mapping[str, object]) -> bytes: ...


class PublishCreateOnce(Protocol):
    def __call__(self, uri: str, payload: bytes) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class PreparedHard230R6SourceV1:
    """Exact successor inputs produced by one immutable conversion."""

    slate_id: str
    fit_scope_id: str
    heldout_block: str | None
    training_blocks: tuple[str, ...]
    worlds_per_block: int
    players: tuple[rw.PlayerSpec, ...]
    player_registry: tuple[Mapping[str, object], ...]
    score_matrix: np.ndarray = field(compare=False, repr=False)
    source_member: Mapping[str, object]
    source_member_identity: Mapping[str, object]
    score_block_identities: tuple[Mapping[str, object], ...]
    score_matrix_identity: Mapping[str, object]
    matrix_artifact_identity: Mapping[str, object]
    derivation_proof: Mapping[str, object]
    derivation_proof_identity: Mapping[str, object]
    source_lineage: Mapping[str, object]


def _fail(message: str) -> None:
    raise Hard230R6SourceDecoderV1Error(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230R6SourceDecoderV1Error(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    return sha256(_canonical(value, label=label)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _nonempty(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = _nonempty(item.get("uri"), label=f"{label} URI")
    generation = _nonempty(
        item.get("generation"), label=f"{label} generation"
    )
    digest = _sha256(item.get("sha256"), label=f"{label} SHA-256")
    byte_count = _integer(item.get("bytes"), label=f"{label} bytes", minimum=1)
    if not uri.startswith("gs://") or not generation.isdigit():
        _fail(f"{label} must be one generation-pinned GCS object")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _fit_scope(heldout_block: str | None) -> tuple[str, tuple[str, ...]]:
    if heldout_block is None:
        return "all-block-final-fit", WORLD_BLOCKS
    if heldout_block not in WORLD_BLOCKS:
        _fail("heldout_block must be null or one exact R0..R4 block")
    return (
        f"holdout-{heldout_block}",
        tuple(block for block in WORLD_BLOCKS if block != heldout_block),
    )


def _prefix(value: object) -> str:
    prefix = _nonempty(value, label="output prefix").rstrip("/")
    if not prefix.startswith("gs://") or prefix.count("/") < 3:
        _fail("output prefix must be one non-root GCS prefix")
    return prefix


def _read_exact_bytes(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if identity["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise Hard230R6SourceDecoderV1Error(
            f"{label} generation-pinned read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} differs from its exact content identity")
    return raw, identity


def _publish_bound(
    *,
    uri: str,
    payload: bytes,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    try:
        raw_identity = publish_create_once(uri, payload)
    except Exception as exc:
        raise Hard230R6SourceDecoderV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(raw_identity, label=f"{label} publication")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(payload)
        or identity["sha256"] != sha256(payload).hexdigest()
    ):
        _fail(f"{label} publication receipt differs from exact payload")
    reopened, _ = _read_exact_bytes(
        identity,
        read_exact=read_exact,
        label=f"published {label}",
        maximum_bytes=len(payload),
    )
    if reopened != payload:
        _fail(f"{label} exact reopen differs")
    return identity


def _parse_source_freeze(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hard230R6SourceDecoderV1Error(
            "later-source freeze is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label="later-source freeze")
    expected = _sha256(
        item.get("freeze_sha256"), label="later-source internal SHA-256"
    )
    try:
        return later.validate_source_freeze(
            item, expected_freeze_sha256=expected
        )
    except later.LR8LaterSourceError as exc:
        raise Hard230R6SourceDecoderV1Error(
            f"later-source freeze validation failed: {exc}"
        ) from exc


def _registry(
    raw_catalog: object,
) -> tuple[tuple[rw.PlayerSpec, ...], tuple[dict[str, object], ...]]:
    if isinstance(raw_catalog, (str, bytes)) or not isinstance(
        raw_catalog, Sequence
    ):
        _fail("PIT player catalog must be one ordered array")
    try:
        players = tuple(rw.PlayerSpec.from_mapping(row) for row in raw_catalog)
    except (KeyError, TypeError, ValueError, rw.ResidualWorldError) as exc:
        raise Hard230R6SourceDecoderV1Error(
            "PIT player catalog contains one malformed player"
        ) from exc
    player_ids = tuple(player.player_id for player in players)
    if (
        not successor.MIN_PLAYER_COUNT <= len(players) <= successor.MAX_PLAYER_COUNT
        or player_ids != tuple(sorted(set(player_ids)))
    ):
        _fail("PIT player catalog is empty, duplicated, unordered, or oversized")
    registry = tuple(
        {
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
        }
        for player in players
    )
    return players, registry


def _receipt_identity(receipt: Mapping[str, object], *, label: str) -> dict[str, object]:
    return _identity(
        {key: receipt.get(key) for key in ("uri", "generation", "sha256", "bytes")},
        label=label,
    )


def smoke_r6_world_artifact_header_v1(
    receipt: Mapping[str, object], raw: bytes
) -> dict[str, object]:
    """Inspect only ZIP/NPY headers; no array value is materialized."""
    retained = _mapping(receipt, label="world artifact receipt")
    block = _nonempty(retained.get("block"), label="world artifact block")
    candidate_rows = _integer(
        retained.get("candidate_rows"),
        label="world artifact candidate rows",
        minimum=1,
    )
    if (
        block not in WORLD_BLOCKS
        or type(raw) is not bytes
        or not 1 <= len(raw) <= evaluator.MAXIMUM_COMPRESSED_WORLD_BYTES
        or retained.get("bytes") != len(raw)
        or retained.get("sha256") != sha256(raw).hexdigest()
    ):
        _fail("world artifact header-smoke receipt differs")
    try:
        with ZipFile(BytesIO(raw), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (
                len(names) != len(set(names))
                or set(names) != evaluator.NPZ_MEMBERS
                or any(
                    info.is_dir()
                    or info.flag_bits & 0x1
                    or info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                    for info in infos
                )
            ):
                _fail("world artifact header-smoke member lattice differs")
            cand_shape, _, cand_dtype, _ = evaluator._npy_member_header_v1(
                archive, name="cand_ix.npy"
            )
            totals_shape, _, totals_dtype, _ = evaluator._npy_member_header_v1(
                archive, name="totals.npy"
            )
            tail_shape, _, tail_dtype, _ = evaluator._npy_member_header_v1(
                archive, name="tail_line.npy"
            )
            player_id_shape, _, player_id_dtype, player_id_bytes = (
                evaluator._npy_member_header_v1(archive, name="player_ids.npy")
            )
            draw_shape, _, draw_dtype, draw_bytes = (
                evaluator._npy_member_header_v1(archive, name="player_draws.npy")
            )
    except Hard230R6SourceDecoderV1Error:
        raise
    except evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error as exc:
        raise Hard230R6SourceDecoderV1Error(str(exc)) from exc
    except (BadZipFile, OSError, ValueError, KeyError) as exc:
        raise Hard230R6SourceDecoderV1Error(
            "world artifact header-smoke NPZ is unreadable"
        ) from exc
    player_count = player_id_shape[0] if len(player_id_shape) == 1 else -1
    if (
        cand_shape != (candidate_rows,)
        or cand_dtype.kind not in {"i", "u"}
        or totals_shape != (candidate_rows, WORLDS_PER_BLOCK)
        or totals_dtype.kind != "f"
        or tail_shape not in {(1,), ()}
        or tail_dtype.kind != "f"
        or not 1 <= player_count <= successor.MAX_PLAYER_COUNT
        or player_id_dtype.kind not in {"U", "S"}
        or player_id_bytes > evaluator.MAXIMUM_PLAYER_ID_MEMBER_BYTES
        or draw_shape != (player_count, WORLDS_PER_BLOCK)
        or draw_dtype != np.dtype(np.float32)
        or draw_bytes > evaluator.MAXIMUM_PLAYER_DRAW_MEMBER_BYTES
    ):
        _fail("world artifact header-smoke resource/shape contract differs")
    return {
        "schema_version": HEADER_SMOKE_SCHEMA,
        "contract_id": CONTRACT_ID,
        "block": block,
        "artifact_sha256": retained["sha256"],
        "candidate_rows": candidate_rows,
        "player_count": player_count,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "player_draws_dtype": np.dtype(np.float32).str,
        "player_draws_shape": [player_count, WORLDS_PER_BLOCK],
        "array_values_materialized": False,
        "candidate_totals_materialized": False,
        "tail_line_materialized": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }


def _to_milli_dk(blocks: Sequence[np.ndarray]) -> np.ndarray:
    if not blocks:
        _fail("no permitted R blocks were loaded")
    rows = int(blocks[0].shape[0])
    matrix = np.empty((rows, len(blocks) * WORLDS_PER_BLOCK), dtype="<i8")
    for block_ordinal, raw in enumerate(blocks):
        values = np.asarray(raw)
        if (
            values.dtype != np.dtype(np.float32)
            or values.shape != (rows, WORLDS_PER_BLOCK)
            or not values.flags.c_contiguous
            or not np.isfinite(values).all()
        ):
            _fail("aligned R-block matrix is not finite C float32 x 10,000")
        start = block_ordinal * WORLDS_PER_BLOCK
        stop = start + WORLDS_PER_BLOCK
        destination = matrix[:, start:stop]
        for row_start in range(0, rows, CONVERSION_ROW_CHUNK):
            row_stop = min(rows, row_start + CONVERSION_ROW_CHUNK)
            promoted = values[row_start:row_stop].astype(np.float64)
            rounded = np.rint(promoted * 1_000.0)
            if (
                not np.isfinite(rounded).all()
                or np.max(np.abs(rounded)) > successor.MAX_ABS_PLAYER_SCORE_MILLI
            ):
                _fail("float32 R-block value exceeds the milli-DK bound")
            destination[row_start:row_stop] = rounded.astype("<i8")
    if matrix.dtype != np.dtype("<i8") or not matrix.flags.c_contiguous:
        _fail("milli-DK conversion did not produce canonical little-endian int64")
    return matrix


def materialize_hard230_r6_source_v1(
    *,
    later_source_freeze_identity: Mapping[str, object],
    slate_id: str,
    heldout_block: str | None,
    output_prefix: str,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> PreparedHard230R6SourceV1:
    """Exact-open, convert, publish, and replay one successor source surface."""
    if not callable(read_exact) or not callable(publish_create_once):
        _fail("read/publish transports must be callable")
    slate = _nonempty(slate_id, label="slate ID")
    fit_scope_id, training_blocks = _fit_scope(heldout_block)
    prefix = _prefix(output_prefix)
    source_raw, source_freeze_identity = _read_exact_bytes(
        later_source_freeze_identity,
        read_exact=read_exact,
        label="later-source freeze",
        maximum_bytes=MAX_SOURCE_FREEZE_BYTES,
    )
    frozen = _parse_source_freeze(source_raw)
    matching = [
        _mapping(row, label="later-source slate")
        for row in frozen.get("slates", [])
        if isinstance(row, Mapping) and row.get("slate_id") == slate
    ]
    if len(matching) != 1:
        _fail("later-source freeze does not contain exactly one requested slate")
    slate_row = matching[0]
    players, registry = _registry(slate_row.get("catalog"))
    registry_sha = _sha(registry, label="player registry")
    if slate_row.get("catalog_sha256") != registry_sha:
        _fail("PIT player registry hash differs from later-source metadata")
    raw_receipts = slate_row.get("artifact_receipts")
    if isinstance(raw_receipts, (str, bytes)) or not isinstance(
        raw_receipts, Sequence
    ):
        _fail("later-source artifact receipts must be one ordered array")
    receipts_by_block: dict[str, dict[str, object]] = {}
    for raw_receipt in raw_receipts:
        receipt = _mapping(raw_receipt, label="later-source artifact receipt")
        block = receipt.get("block")
        if block in receipts_by_block or block not in WORLD_BLOCKS:
            _fail("later-source artifact block identities repeat or differ")
        receipts_by_block[str(block)] = receipt
    if tuple(receipts_by_block) != WORLD_BLOCKS:
        _fail("later-source artifact receipt order differs from R0..R4")

    catalog_ids = tuple(player.player_id for player in players)
    aligned_blocks: list[np.ndarray] = []
    input_identities: list[dict[str, object]] = []
    for block in training_blocks:
        receipt = receipts_by_block[block]
        identity = _receipt_identity(receipt, label=f"{block} artifact")
        raw, _ = _read_exact_bytes(
            identity,
            read_exact=read_exact,
            label=f"{block} artifact",
            maximum_bytes=evaluator.MAXIMUM_COMPRESSED_WORLD_BYTES,
        )
        try:
            loaded = evaluator._load_artifact_worlds_v1(receipt, raw)
        except evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error as exc:
            raise Hard230R6SourceDecoderV1Error(
                f"{block} artifact scientific validation failed: {exc}"
            ) from exc
        loaded_ids = tuple(loaded.player_ids)
        if (
            loaded.block != block
            or len(loaded_ids) != len(catalog_ids)
            or set(loaded_ids) != set(catalog_ids)
        ):
            _fail(f"{block} player IDs do not equal the PIT player registry")
        index = {player_id: ordinal for ordinal, player_id in enumerate(loaded_ids)}
        aligned = np.ascontiguousarray(
            loaded.player_draws[[index[player_id] for player_id in catalog_ids]],
            dtype=np.float32,
        )
        aligned.flags.writeable = False
        aligned_blocks.append(aligned)
        input_identities.append(identity)

    matrix = _to_milli_dk(aligned_blocks)
    matrix_sha = source.canonical_score_matrix_sha256_v1(matrix)
    decoder_source_sha = sha256(Path(__file__).read_bytes()).hexdigest()
    loader_source_sha = sha256(Path(evaluator.__file__).read_bytes()).hexdigest()
    source_member_body = {
        "schema_version": SOURCE_MEMBER_SCHEMA,
        "contract_id": CONTRACT_ID,
        "member_role": "hard230-r6-fit-source-decoder-authority",
        "slate_id": slate,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "later_source_freeze_identity": source_freeze_identity,
        "later_source_internal_sha256": frozen["freeze_sha256"],
        "player_registry": list(registry),
        "player_registry_sha256": registry_sha,
        "ordered_r_block_input_identities": input_identities,
        "ordered_r_block_input_identities_sha256": _sha(
            input_identities, label="ordered R-block input identities"
        ),
        "decoder_source_sha256": decoder_source_sha,
        "evaluator_loader_source_sha256": loader_source_sha,
        "conversion_law_id": CONVERSION_LAW_ID,
        "candidate_totals_materialized": False,
        "tail_line_materialized": False,
        "excluded_heldout_block_opened": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    source_member_payload = _canonical(
        source_member_body, label="source member"
    )
    source_member_object = _publish_bound(
        uri=f"{prefix}/source-member.json",
        payload=source_member_payload,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="source member",
    )
    source_member_identity = {
        "member_id": (
            f"hard230-r6-{slate}-{fit_scope_id}-{source_member_object['sha256'][:20]}"
        ),
        "slate_id": slate,
        "member_sha256": source_member_object["sha256"],
        "object_identity": source_member_object,
    }
    score_block_identities = tuple(
        {
            "block_id": block,
            "world_count": WORLDS_PER_BLOCK,
            "source_member_sha256": source_member_object["sha256"],
            "object_identity": identity,
        }
        for block, identity in zip(training_blocks, input_identities, strict=True)
    )

    matrix_metadata = {
        "schema_version": MATRIX_ARTIFACT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "matrix_id": f"hard230-r6-{slate}-{fit_scope_id}-fit-milli",
        "score_unit": "milli-DraftKings-points",
        "matrix_encoding": MATRIX_ENCODING,
        "matrix_shape": list(matrix.shape),
        "canonical_score_matrix_sha256": matrix_sha,
        "source_member_sha256": source_member_object["sha256"],
        "score_block_identities_sha256": _sha(
            score_block_identities, label="score block identities"
        ),
        "player_registry_sha256": registry_sha,
        "conversion_law_id": CONVERSION_LAW_ID,
        "block_order": list(training_blocks),
        "world_order": "block-major-then-source-world-index-ascending",
        "matrix_values_embedded": False,
        "matrix_reconstructed_from_exact_r_blocks": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    matrix_payload = _canonical(
        matrix_metadata, label="fit score matrix authority"
    )
    matrix_artifact_identity = _publish_bound(
        uri=f"{prefix}/fit-score-matrix-authority.json",
        payload=matrix_payload,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="fit score matrix",
    )
    derivation_input = {
        "matrix_id": matrix_metadata["matrix_id"],
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": list(matrix.shape),
        "artifact_identity": matrix_artifact_identity,
        "source_member_sha256": source_member_object["sha256"],
        "score_block_identities_sha256": matrix_metadata[
            "score_block_identities_sha256"
        ],
        "player_registry_sha256": registry_sha,
    }
    derivation_output = {"canonical_score_matrix_sha256": matrix_sha}
    proof_body = {
        "schema_version": DERIVATION_PROOF_SCHEMA,
        "contract_id": CONTRACT_ID,
        "proof_id": f"hard230-r6-matrix-{slate}-{fit_scope_id}",
        "proof_kind": "score-matrix-derivation-v1",
        "implementation_sha256": decoder_source_sha,
        "input_sha256": _sha(derivation_input, label="matrix derivation input"),
        "output_sha256": _sha(
            derivation_output, label="matrix derivation output"
        ),
        "conversion_law_id": CONVERSION_LAW_ID,
        "source_float_dtype": np.dtype(np.float32).str,
        "destination_dtype": np.dtype("<i8").str,
        "source_values_materialized": True,
        "candidate_totals_materialized": False,
        "tail_line_materialized": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    proof_payload = _canonical(proof_body, label="matrix derivation proof")
    proof_object_identity = _publish_bound(
        uri=f"{prefix}/fit-score-matrix-derivation-proof.json",
        payload=proof_payload,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="matrix derivation proof",
    )
    proof_identity = {
        "proof_id": proof_body["proof_id"],
        "proof_kind": "score-matrix-derivation-v1",
        "implementation_sha256": decoder_source_sha,
        "input_sha256": proof_body["input_sha256"],
        "output_sha256": proof_body["output_sha256"],
        "proof_object_identity": proof_object_identity,
    }
    matrix_identity = {
        **derivation_input,
        "canonical_score_matrix_sha256": matrix_sha,
        "derivation_proof_identity": proof_identity,
    }

    try:
        accepted = successor._prepare_source(
            slate_id=slate,
            candidate_origin_id=training_blocks[0],
            heldout_block=heldout_block,
            worlds_per_block=WORLDS_PER_BLOCK,
            source_member_identity=source_member_identity,
            score_block_identities=score_block_identities,
            player_registry=registry,
            score_matrix=matrix,
            score_matrix_identity=matrix_identity,
            require_production_width=True,
        )
    except successor.Hard230PopulationSuccessorV1Error as exc:
        raise Hard230R6SourceDecoderV1Error(
            f"decoded source is not accepted by the hard230 successor: {exc}"
        ) from exc
    matrix.flags.writeable = False
    return PreparedHard230R6SourceV1(
        slate_id=slate,
        fit_scope_id=fit_scope_id,
        heldout_block=heldout_block,
        training_blocks=training_blocks,
        worlds_per_block=WORLDS_PER_BLOCK,
        players=players,
        player_registry=registry,
        score_matrix=matrix,
        source_member=source_member_body,
        source_member_identity=source_member_identity,
        score_block_identities=score_block_identities,
        score_matrix_identity=matrix_identity,
        matrix_artifact_identity=matrix_artifact_identity,
        derivation_proof=proof_body,
        derivation_proof_identity=proof_identity,
        source_lineage=accepted["lineage"],
    )


__all__ = [
    "CONTRACT_ID",
    "CONVERSION_LAW_ID",
    "Hard230R6SourceDecoderV1Error",
    "PreparedHard230R6SourceV1",
    "materialize_hard230_r6_source_v1",
    "smoke_r6_world_artifact_header_v1",
]
