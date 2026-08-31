"""Execution boundary for the fixed-corpus Fantasy Points x SIS ablation.

The lower-level paid-source modules deliberately stop at pure scientific
builders.  This module supplies the production-shaped seam from one exact
candidate-rooted matchup source-v3 release plus one deep-reopened 54-member
float64 R0--R3 discovery-matrix freeze terminal to:

* a read-only, non-publishing task-0 reality smoke;
* one complete 54-slate, score-free four-cell terminal;
* a separately authorized realized-outcome grade; and
* an independent grade reopen that consumes only persisted derived scores.

Nothing is enabled implicitly.  Storage and source-v3 reopening are injected
callbacks; the executable CLI owns the genuine GCS/Git adapters and the
explicit environment gates.  No API in this module lists, overwrites, deletes,
deploys, mutates a graph, enters a contest, or promotes a policy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

import numpy as np

from . import corpus_r6_construction_allocation_cross_operator_v1 as build_authority
from . import corpus_r6_matchup_source_v2 as source
from . import corpus_r6_paid_source_ablation_v1 as matchup
from . import corpus_r6_paid_source_discovery_matrix_freeze_v1 as matrix_freeze
from . import paid_source_ablation_grade_v1 as grade
from . import paid_source_ablation_operator_v1 as operator
from . import paid_source_ablation_registry_v1 as registry


REQUEST_SCHEMA: Final = "corpus-r6-paid-source-fp-sis-execution-request/v2"
TASK0_SCHEMA: Final = "corpus-r6-paid-source-fp-sis-task0/v1"
TASK0_CLOUD_RESULT_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-cloud-result/v1"
)
TASK0_PROVIDER_SPEC_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-provider-execution-spec/v1"
)
TASK_RESULT_SCHEMA: Final = "corpus-r6-paid-source-fp-sis-slate-result/v2"
TASK_PUBLICATION_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-slate-publication/v2"
)
TERMINAL_SCHEMA: Final = "corpus-r6-paid-source-fp-sis-terminal/v2"
SELECTION_RESULT_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-score-free-terminal-result/v2"
)
GRADE_RESULT_SCHEMA: Final = "corpus-r6-paid-source-fp-sis-grade-result/v1"
GRADE_REOPEN_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-grade-independent-reopen/v1"
)
OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/"
    "research/corpus-r6-paid-source-fp-sis"
)
TASK_COUNT: Final = 54
MAX_WORLD_COUNT: Final = matrix_freeze.DISCOVERY_WORLD_COUNT
MAX_MATRIX_BYTES: Final = matrix_freeze.MAX_MATRIX_BYTES
PROVIDER_PROJECT_ID: Final = "nfl-predictions-503414"
PROVIDER_REGION: Final = "us-central1"
PROVIDER_JOB_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1"
PROVIDER_JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
PROVIDER_SERVICE_ACCOUNT: Final = (
    "817589974517-compute@developer.gserviceaccount.com"
)
PROVIDER_TASK_TIMEOUT_SECONDS: Final = 21_600
PROVIDER_CPU: Final = "8"
PROVIDER_MEMORY: Final = "32Gi"

_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,80}\Z")
_GRADE_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,100}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_BUILD_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}\Z"
)
_TASK0_EXECUTION = re.compile(
    rf"{re.escape(PROVIDER_JOB_NAME)}-[a-z0-9]{{5}}\Z"
)

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
SourceV3Reopen = Callable[[int], Mapping[str, object]]
LeaseVerifier = Callable[..., Mapping[str, object]]
MatrixRegistryReopen = Callable[..., object]
FetchExactToFile = Callable[[Mapping[str, object], object], None]


class PaidSourceAblationExecutionV1Error(ValueError):
    """The exact execution, score-free, or grade boundary differed."""


def _fail(message: str) -> None:
    raise PaidSourceAblationExecutionV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(
    value: object, *, label: str, require_create_once: bool = False,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    create_once = item.pop("create_once", None)
    try:
        retained = source.normalize_object_identity_v2(item, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise PaidSourceAblationExecutionV1Error(str(exc)) from exc
    if require_create_once and create_once is not True:
        _fail(f"{label} must be create-once")
    if create_once is not None and create_once is not True:
        _fail(f"{label} create-once marker differs")
    if create_once is True:
        retained["create_once"] = True
    return retained


def _read_exact(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> bytes:
    raw_identity = {
        key: identity[key] for key in ("uri", "generation", "sha256", "bytes")
    }
    try:
        raw = read_exact(raw_identity)
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != raw_identity["bytes"]
        or sha256(raw).hexdigest() != raw_identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    return raw


def _parse_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw or raw.endswith(b"\n"):
        _fail(f"{label} must be canonical JSON without a trailing newline")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"{label} JSON differs"
        ) from exc
    item = _mapping(value, label=label)
    if registry.canonical_json_bytes(item) != raw:
        _fail(f"{label} canonical replay differs")
    return item


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = registry.canonical_sha256(result)
    return result


def _validate_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    if not registry.is_sha256(retained):
        _fail(f"{label} self-hash differs")
    body = dict(value)
    del body[field]
    if registry.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _policy(*, uses_realized_outcomes: bool) -> dict[str, object]:
    return {
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
        "source_value_established": False,
        "uses_realized_outcomes": uses_realized_outcomes,
        **{field: False for field in registry.FALSE_AUTHORITY_FIELDS},
    }


def build_fp_sis_execution_request_v1(
    *,
    run_id: str,
    frozen_at: str,
    source_v3_release_identity: Mapping[str, object],
    discovery_matrix_freeze_terminal_identity: Mapping[str, object],
    code_sha: str,
    immutable_image: str,
    build_id: str,
    runtime_build_attestation_identity: Mapping[str, object],
) -> dict[str, object]:
    """Freeze the sole score-free execution request.

    The caller must supply genuine generations.  This function never resolves
    a current object and cannot synthesize a cloud identity from local bytes.
    """

    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("paid-source run ID differs")
    if type(frozen_at) is not str or not frozen_at.endswith("Z"):
        _fail("paid-source frozen_at must be explicit UTC")
    try:
        parsed_frozen_at = datetime.fromisoformat(frozen_at[:-1] + "+00:00")
    except ValueError as exc:
        raise PaidSourceAblationExecutionV1Error(
            "paid-source frozen_at must be explicit UTC"
        ) from exc
    if parsed_frozen_at.tzinfo != timezone.utc:
        _fail("paid-source frozen_at must be explicit UTC")
    if type(code_sha) is not str or _COMMIT.fullmatch(code_sha) is None:
        _fail("paid-source code SHA differs")
    if type(immutable_image) is not str or _IMAGE.fullmatch(immutable_image) is None:
        _fail("paid-source immutable image differs")
    if type(build_id) is not str or _BUILD_ID.fullmatch(build_id) is None:
        _fail("paid-source provider build ID differs")
    source_identity = _identity(
        source_v3_release_identity, label="source-v3 release identity"
    )
    matrix_terminal_identity = _identity(
        discovery_matrix_freeze_terminal_identity,
        label="discovery matrix freeze terminal identity",
    )
    if source_identity["uri"] == matrix_terminal_identity["uri"]:
        _fail("paid-source input identities reuse an object URI")
    attestation_identity = _identity(
        runtime_build_attestation_identity,
        label="runtime build attestation identity",
        require_create_once=True,
    )
    body: dict[str, object] = {
        "schema_version": REQUEST_SCHEMA,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "registry_sha256": registry.frozen_paid_source_ablation_registry_v1()[
            "registry_sha256"
        ],
        "run_id": run_id,
        "frozen_at": frozen_at,
        "code_sha": code_sha,
        "immutable_image": immutable_image,
        "image_digest": immutable_image.rsplit("@", 1)[1],
        "build_id": build_id,
        "runtime_build_attestation_identity": attestation_identity,
        "source_v3_release_identity": source_identity,
        "discovery_matrix_freeze_terminal_identity": matrix_terminal_identity,
        "selection_bank_law": {
            "block_order": list(matrix_freeze.DISCOVERY_BLOCKS),
            "worlds_per_block": matrix_freeze.WORLDS_PER_BLOCK,
            "world_count": matrix_freeze.DISCOVERY_WORLD_COUNT,
            "dtype": matrix_freeze.MATRIX_DTYPE.str,
            "scoring_law_id": matrix_freeze.SCORING_LAW_ID,
            "r4_heldout_bound_but_not_read": True,
        },
        "source_task_count": TASK_COUNT,
        "output_prefix": OUTPUT_PREFIX,
        "terminal_uri": f"{OUTPUT_PREFIX}/{run_id}/terminal.json",
        "entry_budget": registry.ENTRY_BUDGET,
        "admission_cap": registry.MATCHUP_ADMISSION_CAP,
        "task0_required_before_full_execution": True,
        "task0_publication_allowed": False,
        "target_slate_outcomes_allowed": False,
        "all_cells_fixed_before_execution": True,
        "one_slate_per_task_required": True,
        "collector_reads_zero_matrix_bodies": True,
        **_policy(uses_realized_outcomes=False),
    }
    return _with_hash(body, field="execution_request_sha256")


def validate_fp_sis_execution_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="paid-source execution request")
    _validate_hash(
        item, field="execution_request_sha256",
        label="paid-source execution request",
    )
    expected = build_fp_sis_execution_request_v1(
        run_id=item.get("run_id"),
        frozen_at=item.get("frozen_at"),
        source_v3_release_identity=item.get("source_v3_release_identity"),
        discovery_matrix_freeze_terminal_identity=item.get(
            "discovery_matrix_freeze_terminal_identity"
        ),
        code_sha=item.get("code_sha"),
        immutable_image=item.get("immutable_image"),
        build_id=item.get("build_id"),
        runtime_build_attestation_identity=item.get(
            "runtime_build_attestation_identity"
        ),
    )
    if item != expected:
        _fail("paid-source execution request canonical replay differs")
    return expected


def open_discovery_world_matrix_file_v2(
    path: object,
    *,
    matrix_registry_entry: Mapping[str, object],
    candidate_ids: Sequence[str],
    candidate_artifact_identity: Mapping[str, object],
) -> tuple[dict[str, object], np.memmap]:
    """Open one exact float64 R0--R3 matrix as a disk-backed memmap."""

    from pathlib import Path

    retained_path = Path(path)

    entry = _mapping(
        matrix_registry_entry, label="paid-source discovery matrix registry entry"
    )
    required = {
        "source_task_ordinal", "slate", "matrix_identity",
        "candidate_artifact_identity", "candidate_ids_sha256",
        "source_world_artifact_identities",
        "source_world_artifact_manifest_sha256", "block_order",
        "worlds_per_block", "world_count", "dtype", "scoring_law_id",
        "r4_heldout_identity", "r4_heldout_not_read",
        "matrix_lineage_sha256", "matrix_body_sha256",
    }
    identity = _identity(entry.get("matrix_identity"), label="discovery world matrix")
    candidate_identity = _identity(
        candidate_artifact_identity, label="discovery candidate artifact"
    )
    source_identities = [
        _identity(value, label="discovery R0-R3 source identity")
        for value in _sequence(
            entry.get("source_world_artifact_identities"),
            label="discovery R0-R3 source identities",
        )
    ]
    ids = [str(value) for value in candidate_ids]
    if (
        set(entry) != required
        or not ids
        or len(ids) != len(set(ids))
        or entry.get("candidate_artifact_identity") != candidate_identity
        or entry.get("candidate_ids_sha256") != registry.canonical_sha256(ids)
        or entry.get("source_world_artifact_identities") != source_identities
        or len(source_identities) != len(matrix_freeze.DISCOVERY_BLOCKS)
        or entry.get("source_world_artifact_manifest_sha256")
        != registry.canonical_sha256(source_identities)
        or entry.get("block_order") != list(matrix_freeze.DISCOVERY_BLOCKS)
        or entry.get("worlds_per_block") != matrix_freeze.WORLDS_PER_BLOCK
        or entry.get("world_count") != matrix_freeze.DISCOVERY_WORLD_COUNT
        or entry.get("dtype") != matrix_freeze.MATRIX_DTYPE.str
        or entry.get("scoring_law_id") != matrix_freeze.SCORING_LAW_ID
        or entry.get("r4_heldout_not_read") is not True
        or not registry.is_sha256(entry.get("matrix_lineage_sha256"))
        or not registry.is_sha256(entry.get("matrix_body_sha256"))
        or identity["bytes"] > MAX_MATRIX_BYTES
        or not retained_path.is_absolute()
        or not retained_path.is_file()
        or retained_path.is_symlink()
        or retained_path.stat().st_size != identity["bytes"]
    ):
        _fail("paid-source discovery matrix registry/identity differs")
    digest = sha256()
    body_digest = sha256()
    with retained_path.open("rb") as handle:
        header_raw = handle.readline(16 * 1024 * 1024)
        if not header_raw.endswith(b"\n"):
            _fail("paid-source discovery matrix envelope differs")
        digest.update(header_raw)
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            body_digest.update(chunk)
    if (
        digest.hexdigest() != identity["sha256"]
        or body_digest.hexdigest() != entry["matrix_body_sha256"]
    ):
        _fail("paid-source discovery matrix file hash differs")
    delimiter = len(header_raw) - 1
    if delimiter <= 0:
        _fail("paid-source discovery matrix envelope differs")
    header = _parse_canonical(
        header_raw[:-1], label="paid-source discovery matrix header"
    )
    expected_header = {
        "schema_version": matrix_freeze.MATRIX_ENVELOPE_SCHEMA,
        "candidate_ids": ids,
        "candidate_artifact_identity": candidate_identity,
        "candidate_ids_sha256": registry.canonical_sha256(ids),
        "dtype": matrix_freeze.MATRIX_DTYPE.str,
        "shape": [len(ids), matrix_freeze.DISCOVERY_WORLD_COUNT],
        "block_order": list(matrix_freeze.DISCOVERY_BLOCKS),
        "worlds_per_block": matrix_freeze.WORLDS_PER_BLOCK,
        "source_world_artifact_identities": source_identities,
        "source_world_artifact_manifest_sha256": registry.canonical_sha256(
            source_identities
        ),
        "r4_heldout_not_read": True,
    }
    shape = tuple(expected_header["shape"])
    if (
        header != expected_header
        or identity["bytes"] != len(header_raw)
        + int(np.prod(shape)) * matrix_freeze.MATRIX_DTYPE.itemsize
    ):
        _fail("paid-source discovery matrix header/body differs")
    values = np.memmap(
        retained_path,
        dtype=matrix_freeze.MATRIX_DTYPE,
        mode="r",
        offset=len(header_raw),
        shape=shape,
        order="C",
    )
    for start in range(0, len(ids), 64):
        if not np.isfinite(values[start : start + 64]).all():
            _fail("paid-source discovery matrix contains a non-finite value")
    return header, values


def _runtime_build_attestation(
    request: Mapping[str, object], *, read_exact: ReadExact,
) -> dict[str, object]:
    identity = _identity(
        request["runtime_build_attestation_identity"],
        label="runtime build attestation",
    )
    raw = _read_exact(
        identity, read_exact=read_exact, label="runtime build attestation"
    )
    attestation = _parse_canonical(raw, label="runtime build attestation")
    try:
        retained = build_authority.validate_runtime_build_attestation_v1(
            attestation,
            expected_code_sha=str(request["code_sha"]),
            expected_image_digest=str(request["image_digest"]),
        )
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"runtime build attestation differs: {exc}"
        ) from exc
    if retained.get("build_id") != request["build_id"]:
        _fail("runtime build attestation provider ID differs")
    return retained


def _reopen_matrix_registry(
    request: Mapping[str, object],
    *,
    read_exact: ReadExact,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    if not callable(reopen_discovery_matrix_registry):
        _fail("discovery matrix registry reopener differs")
    try:
        reopened = reopen_discovery_matrix_registry(
            terminal_identity=request[
                "discovery_matrix_freeze_terminal_identity"
            ],
            read_exact=read_exact,
        )
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"discovery matrix freeze deep reopen failed: {exc}"
        ) from exc
    terminal = _mapping(
        getattr(reopened, "terminal", None), label="discovery matrix terminal"
    )
    terminal_identity = _identity(
        getattr(reopened, "terminal_identity", None),
        label="reopened discovery matrix terminal identity",
    )
    rows = [
        _mapping(value, label=f"discovery matrix registry[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(
                getattr(reopened, "matrix_registry", None),
                label="discovery matrix registry",
            )
        )
    ]
    receipt = _mapping(
        getattr(reopened, "reopen_receipt", None),
        label="discovery matrix registry reopen receipt",
    )
    if (
        terminal_identity
        != request["discovery_matrix_freeze_terminal_identity"]
        or terminal.get("schema_version") != matrix_freeze.TERMINAL_SCHEMA
        or terminal.get("task_count") != TASK_COUNT
        or terminal.get("matrix_registry") != rows
        or terminal.get("matrix_registry_sha256")
        != registry.canonical_sha256(rows)
        or terminal.get("scoring_law", {}).get("scoring_law_id")
        != matrix_freeze.SCORING_LAW_ID
        or terminal.get("r4_heldout_bound_but_not_read") is not True
        or terminal.get("complete") is not True
        or len(rows) != TASK_COUNT
        or [row.get("source_task_ordinal") for row in rows]
        != list(range(TASK_COUNT))
        or any(row.get("dtype") != matrix_freeze.MATRIX_DTYPE.str for row in rows)
        or any(
            row.get("block_order") != list(matrix_freeze.DISCOVERY_BLOCKS)
            or row.get("worlds_per_block") != matrix_freeze.WORLDS_PER_BLOCK
            or row.get("world_count") != matrix_freeze.DISCOVERY_WORLD_COUNT
            or row.get("scoring_law_id") != matrix_freeze.SCORING_LAW_ID
            or row.get("r4_heldout_not_read") is not True
            for row in rows
        )
        or receipt.get("complete") is not True
    ):
        _fail("discovery matrix freeze terminal/registry differs")
    return terminal, rows, receipt


def _upstream_seven_pack(
    deep: Mapping[str, object], *, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    release = _mapping(deep.get("release"), label="source-v3 release")
    release_identity = _identity(
        release.get("upstream_source_release_identity"),
        label="source-v3 seven-pack release identity",
    )
    release_body = _parse_canonical(
        _read_exact(
            release_identity, read_exact=read_exact,
            label="source-v3 seven-pack release",
        ),
        label="source-v3 seven-pack release",
    )
    packs = _sequence(release_body.get("packs"), label="seven-pack entries")
    if len(packs) != len(source.PACK_IDS):
        _fail("source-v3 predecessor does not contain the exact seven-pack")
    row_objects: list[dict[str, object]] = []
    for ordinal, raw_pack in enumerate(packs):
        pack = _mapping(raw_pack, label=f"seven-pack entry[{ordinal}]")
        row_identity = _identity(
            pack.get("exact_rows_identity"),
            label=f"seven-pack rows[{ordinal}] identity",
        )
        row_objects.append(_parse_canonical(
            _read_exact(
                row_identity, read_exact=read_exact,
                label=f"seven-pack rows[{ordinal}]",
            ),
            label=f"seven-pack rows[{ordinal}]",
        ))
    try:
        validated = source.validate_upstream_release_v1(
            release_body, pack_row_objects=row_objects
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise PaidSourceAblationExecutionV1Error(str(exc)) from exc
    return validated, release_identity, row_objects


def _slate_input(
    *,
    ordinal: int,
    deep: Mapping[str, object],
    matrix_registry_entry: Mapping[str, object],
    read_exact: ReadExact,
    fetch_exact_to_file: FetchExactToFile,
    workspace: Path,
) -> tuple[dict[str, object], Path]:
    release = _mapping(deep.get("release"), label="source-v3 release")
    member = _mapping(deep.get("member"), label="source-v3 member")
    candidate_binding = _mapping(
        deep.get("candidate_authority_binding"),
        label="source-v3 candidate authority binding",
    )
    catalog = _mapping(deep.get("structural_catalog"), label="structural catalog")
    candidates = _mapping(
        deep.get("candidate_artifact"), label="accepted candidate artifact"
    )
    entries = _sequence(release.get("entries"), label="source-v3 entries")
    if (
        not 0 <= ordinal < len(entries)
        or member.get("source_task_ordinal") != ordinal
        or catalog.get("source_task_ordinal") != ordinal
        or candidates.get("source_task_ordinal") != ordinal
        or entries[ordinal] != member
    ):
        _fail(f"source-v3 ordinal[{ordinal}] differs")
    candidate_identity = _identity(
        candidate_binding.get("candidate_artifact_identity"),
        label=f"candidate artifact[{ordinal}] identity",
    )
    if candidate_identity != _identity(
        member.get("candidate_artifact_identity"),
        label=f"source member candidate[{ordinal}] identity",
    ):
        _fail(f"source-v3 candidate identity[{ordinal}] differs")
    matrix_entry = _mapping(
        matrix_registry_entry, label=f"discovery matrix registry[{ordinal}]"
    )
    if (
        matrix_entry.get("source_task_ordinal") != ordinal
        or matrix_entry.get("slate") != candidates.get("slate")
        or matrix_entry.get("candidate_artifact_identity") != candidate_identity
    ):
        _fail(f"discovery matrix candidate/slate lineage[{ordinal}] differs")
    catalog_identity = _identity(
        member.get("catalog_identity"),
        label=f"structural catalog[{ordinal}] identity",
    )
    ids = [str(row["candidate_id"]) for row in candidates["rows"]]
    retained_workspace = Path(workspace)
    if (
        not retained_workspace.is_absolute()
        or retained_workspace.is_symlink()
        or not callable(fetch_exact_to_file)
    ):
        _fail("paid-source matrix workspace/fetcher differs")
    retained_workspace.mkdir(parents=True, exist_ok=True)
    matrix_path = retained_workspace / f"discovery-matrix-{ordinal:02d}.bin"
    if matrix_path.exists() or matrix_path.is_symlink():
        _fail("paid-source matrix destination already exists")
    retained_matrix_identity = _identity(
        matrix_entry.get("matrix_identity"),
        label=f"discovery world matrix[{ordinal}] identity",
    )
    try:
        fetch_exact_to_file(retained_matrix_identity, matrix_path)
    except Exception as exc:
        if matrix_path.exists() and matrix_path.is_file():
            matrix_path.unlink()
        raise PaidSourceAblationExecutionV1Error(
            f"discovery world matrix[{ordinal}] exact file fetch failed"
        ) from exc
    values: np.memmap | None = None
    try:
        header, values = open_discovery_world_matrix_file_v2(
            matrix_path,
            matrix_registry_entry=matrix_entry,
            candidate_ids=ids,
            candidate_artifact_identity=candidate_identity,
        )
        binding = matchup.build_discovery_world_matrix_binding_v2(
            world_matrix_identity=retained_matrix_identity,
            candidate_ids=ids,
            world_scores=values,
            matrix_header=header,
            matrix_registry_entry=matrix_entry,
        )
        upstream, upstream_identity, pack_rows = _upstream_seven_pack(
            deep, read_exact=read_exact
        )
    except Exception:
        mapped = getattr(values, "_mmap", None)
        if mapped is not None:
            mapped.close()
        if matrix_path.exists() and matrix_path.is_file():
            matrix_path.unlink()
        raise
    return ({
        "structural_catalog": catalog,
        "structural_catalog_identity": catalog_identity,
        "accepted_candidate_artifact": candidates,
        "accepted_candidate_artifact_identity": candidate_identity,
        "upstream_source_release": upstream,
        "upstream_source_release_identity": upstream_identity,
        "upstream_pack_row_objects": pack_rows,
        "world_matrix_binding": binding,
        "world_scores": values,
    }, matrix_path)


def _release_slate_matrix(
    slate_input: dict[str, object], matrix_path: Path,
) -> None:
    values = slate_input.pop("world_scores", None)
    mapped = getattr(values, "_mmap", None)
    if mapped is not None:
        mapped.close()
    if matrix_path.exists() and matrix_path.is_file():
        matrix_path.unlink()


def run_fp_sis_task0_v1(
    request_value: object,
    *,
    read_exact: ReadExact,
    fetch_exact_to_file: FetchExactToFile,
    matrix_workspace: Path,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
    canonical_source_v3_reopen_by_ordinal: SourceV3Reopen,
) -> dict[str, object]:
    """Run the one-slate gate with no reachable publication callback."""

    request = validate_fp_sis_execution_request_v1(request_value)
    if (
        not callable(read_exact)
        or not callable(fetch_exact_to_file)
        or not callable(canonical_source_v3_reopen_by_ordinal)
    ):
        _fail("paid-source task0 callbacks differ")
    attestation = _runtime_build_attestation(request, read_exact=read_exact)
    _, matrix_registry, matrix_reopen = _reopen_matrix_registry(
        request,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    try:
        deep = canonical_source_v3_reopen_by_ordinal(0)
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"source-v3 task0 deep reopen failed: {exc}"
        ) from exc
    slate_input, matrix_path = _slate_input(
        ordinal=0,
        deep=_mapping(deep, label="source-v3 task0 reopen"),
        matrix_registry_entry=matrix_registry[0],
        read_exact=read_exact,
        fetch_exact_to_file=fetch_exact_to_file,
        workspace=matrix_workspace,
    )
    try:
        census = matchup.run_fp_sis_retrieval_support_census_v1(**slate_input)
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"paid-source task0 scientific replay failed: {exc}"
        ) from exc
    finally:
        _release_slate_matrix(slate_input, matrix_path)
    if census.get("source_task_ordinal") != 0 or census.get(
        "support_gate_status"
    ) != "passed":
        _fail("paid-source task0 support gate did not pass")
    body: dict[str, object] = {
        "schema_version": TASK0_SCHEMA,
        "execution_request_sha256": request["execution_request_sha256"],
        "run_id": request["run_id"],
        "source_v3_release_identity": request["source_v3_release_identity"],
        "discovery_matrix_freeze_terminal_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "discovery_matrix_registry_reopen_sha256": matrix_reopen[
            "registry_reopen_sha256"
        ],
        "task0_world_matrix_identity": matrix_registry[0]["matrix_identity"],
        "runtime_build_attestation_sha256": attestation[
            "runtime_build_attestation_sha256"
        ],
        "task0_slate_support_census_sha256": census[
            "slate_support_census_sha256"
        ],
        "task0_source_task_ordinal": 0,
        "task0_k80_feasible_all_four_cells": True,
        "all_54_input_identities_frozen": True,
        "full_cohort_execution_launched": False,
        "publication_performed": False,
        "publication_callback_present": False,
        "write_api_reachable_from_task0": False,
        "runtime_principal_write_authority_status": "not-evaluated",
        "recognized_outcome_callback_present": False,
        "runtime_principal_outcome_authority_status": "not-evaluated",
        "outcome_artifacts_read": [],
        "world_matrix_body_read_count": 1,
        "matrix_streamed_to_disk_and_memmapped": True,
        "selection_bank_r0_r3_float64_exact": True,
        "r4_body_read": False,
        "mechanical_launch_gate_passed": True,
        "complete": True,
        **_policy(uses_realized_outcomes=False),
    }
    return _with_hash(body, field="task0_receipt_sha256")


def validate_fp_sis_task0_receipt_v1(
    value: object, *, request_value: object,
) -> dict[str, object]:
    receipt = _mapping(value, label="paid-source task0 receipt")
    request = validate_fp_sis_execution_request_v1(request_value)
    _validate_hash(receipt, field="task0_receipt_sha256", label="task0 receipt")
    expected_fields = {
        "schema_version",
        "execution_request_sha256",
        "run_id",
        "source_v3_release_identity",
        "discovery_matrix_freeze_terminal_identity",
        "discovery_matrix_registry_reopen_sha256",
        "task0_world_matrix_identity",
        "runtime_build_attestation_sha256",
        "task0_slate_support_census_sha256",
        "task0_source_task_ordinal",
        "task0_k80_feasible_all_four_cells",
        "all_54_input_identities_frozen",
        "full_cohort_execution_launched",
        "publication_performed",
        "publication_callback_present",
        "write_api_reachable_from_task0",
        "runtime_principal_write_authority_status",
        "recognized_outcome_callback_present",
        "runtime_principal_outcome_authority_status",
        "outcome_artifacts_read",
        "world_matrix_body_read_count",
        "matrix_streamed_to_disk_and_memmapped",
        "selection_bank_r0_r3_float64_exact",
        "r4_body_read",
        "mechanical_launch_gate_passed",
        "complete",
        "automatic_policy_promotion",
        "production_policy_authority",
        "source_value_established",
        "uses_realized_outcomes",
        "task0_receipt_sha256",
        *registry.FALSE_AUTHORITY_FIELDS,
    }
    if set(receipt) != expected_fields:
        _fail("paid-source task0 receipt fields differ")
    task0_matrix_identity = _identity(
        receipt.get("task0_world_matrix_identity"),
        label="task0 discovery world matrix identity",
    )
    if (
        receipt.get("schema_version") != TASK0_SCHEMA
        or receipt.get("execution_request_sha256")
        != request["execution_request_sha256"]
        or receipt.get("run_id") != request["run_id"]
        or receipt.get("source_v3_release_identity")
        != request["source_v3_release_identity"]
        or receipt.get("discovery_matrix_freeze_terminal_identity")
        != request["discovery_matrix_freeze_terminal_identity"]
        or not registry.is_sha256(
            receipt.get("discovery_matrix_registry_reopen_sha256")
        )
        or receipt.get("task0_source_task_ordinal") != 0
        or receipt.get("task0_k80_feasible_all_four_cells") is not True
        or receipt.get("all_54_input_identities_frozen") is not True
        or receipt.get("full_cohort_execution_launched") is not False
        or receipt.get("publication_performed") is not False
        or receipt.get("publication_callback_present") is not False
        or receipt.get("write_api_reachable_from_task0") is not False
        or receipt.get("runtime_principal_write_authority_status")
        != "not-evaluated"
        or receipt.get("recognized_outcome_callback_present") is not False
        or receipt.get("runtime_principal_outcome_authority_status")
        != "not-evaluated"
        or receipt.get("outcome_artifacts_read") != []
        or receipt.get("world_matrix_body_read_count") != 1
        or receipt.get("matrix_streamed_to_disk_and_memmapped") is not True
        or receipt.get("selection_bank_r0_r3_float64_exact") is not True
        or receipt.get("r4_body_read") is not False
        or task0_matrix_identity["bytes"] > MAX_MATRIX_BYTES
        or receipt.get("mechanical_launch_gate_passed") is not True
        or receipt.get("complete") is not True
        or receipt.get("uses_realized_outcomes") is not False
        or not registry.is_sha256(
            receipt.get("runtime_build_attestation_sha256")
        )
        or not registry.is_sha256(
            receipt.get("task0_slate_support_census_sha256")
        )
    ):
        _fail("paid-source task0 receipt differs")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if receipt.get(field) is not False:
            _fail("paid-source task0 receipt claims downstream authority")
    return receipt


def validate_fp_sis_task0_provider_gate_v1(
    value: object, *, request_value: object,
) -> dict[str, object]:
    """Validate the provider-observed task-0 execution used by full54.

    This gate is deliberately more than a copy of the scientific receipt.  It
    binds that receipt to the exact terminal Cloud Run execution, immutable
    build, service account, task mechanics, resource envelope, command, and
    complete environment-name lattice observed by the provider.  A caller
    cannot substitute a locally rehashed receipt because the retained receipt
    must be the one extracted from the exact execution's canonical stdout.
    """

    request = validate_fp_sis_execution_request_v1(request_value)
    gate = _mapping(value, label="paid-source task0 provider gate")
    execution_row = _mapping(
        gate.get("execution"), label="paid-source task0 provider execution"
    )
    provider_spec = _mapping(
        gate.get("provider_execution_spec"),
        label="paid-source task0 provider execution spec",
    )
    _validate_hash(
        provider_spec,
        field="provider_execution_spec_sha256",
        label="paid-source task0 provider execution spec",
    )
    receipt = validate_fp_sis_task0_receipt_v1(
        gate.get("operator_receipt"), request_value=request
    )
    expected_gate_fields = {
        "schema_version", "mode", "code_sha", "cloud_build_id",
        "provider_resolved_image", "execution", "provider_execution_spec",
        "request_sha256", "operator_receipt", "exact_execution_stdout_only",
        "task0_provider_gate_eligible", "outcome_artifacts_read", "complete",
    }
    expected_execution_fields = {
        "name", "uid", "task_count", "succeeded_count", "failed_count",
        "cancelled_count", "running_count", "creation_time", "start_time",
        "completion_time",
    }
    expected_spec_fields = {
        "schema_version", "provider", "project_id", "region", "job_name",
        "job_uid", "job_generation", "execution_name", "execution_uid",
        "service_account_name", "task_count", "max_retries",
        "timeout_seconds", "image", "command", "args", "cpu", "memory",
        "environment_names", "environment_bindings",
        "request_payload_sha256", "creation_time", "start_time",
        "completion_time", "provider_observed_from_execution_describe",
        "uses_realized_outcomes", "provider_execution_spec_sha256",
    }
    expected_environment_names = sorted([
        "BUILD_ID", "CODE_SHA", "IMAGE_DIGEST", "IMAGE_SOURCE_COMMIT_SHA",
        "IMAGE_URI", "R6_PAID_SOURCE_FP_SIS_ENABLE",
        "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED",
        "R6_PAID_SOURCE_FP_SIS_REQUEST_B64",
        "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256",
    ])
    environment = _mapping(
        provider_spec.get("environment_bindings"),
        label="paid-source task0 provider environment bindings",
    )
    expected_environment_fields = {
        "code_sha", "image_source_commit_sha", "image_digest", "build_id",
        "image_uri", "enable_name", "enable_value", "outcomes_name",
        "outcomes_allowed", "request_b64_name", "request_sha256_name",
        "request_sha256", "execution_request_sha256",
    }
    execution_name = execution_row.get("name")
    execution_uid = execution_row.get("uid")
    time_fields = ("creation_time", "start_time", "completion_time")
    if (
        set(gate) != expected_gate_fields
        or set(execution_row) != expected_execution_fields
        or set(provider_spec) != expected_spec_fields
        or set(environment) != expected_environment_fields
        or gate.get("schema_version") != TASK0_CLOUD_RESULT_SCHEMA
        or gate.get("mode") != "task0"
        or gate.get("code_sha") != request["code_sha"]
        or gate.get("cloud_build_id") != request["build_id"]
        or gate.get("provider_resolved_image") != request["immutable_image"]
        or not registry.is_sha256(gate.get("request_sha256"))
        or gate.get("operator_receipt") != receipt
        or gate.get("exact_execution_stdout_only") is not True
        or gate.get("task0_provider_gate_eligible") is not True
        or gate.get("outcome_artifacts_read") != []
        or gate.get("complete") is not True
        or type(execution_name) is not str
        or _TASK0_EXECUTION.fullmatch(execution_name) is None
        or type(execution_uid) is not str or not execution_uid
        or execution_row.get("task_count") != 1
        or execution_row.get("succeeded_count") != 1
        or execution_row.get("failed_count") != 0
        or execution_row.get("cancelled_count") != 0
        or execution_row.get("running_count") != 0
        or any(
            type(execution_row.get(field)) is not str
            or not execution_row[field]
            for field in time_fields
        )
        or provider_spec.get("schema_version") != TASK0_PROVIDER_SPEC_SCHEMA
        or provider_spec.get("provider") != "google-cloud-run-v2-api"
        or provider_spec.get("project_id") != PROVIDER_PROJECT_ID
        or provider_spec.get("region") != PROVIDER_REGION
        or provider_spec.get("job_name") != PROVIDER_JOB_NAME
        or provider_spec.get("job_uid") != PROVIDER_JOB_UID
        or type(provider_spec.get("job_generation")) is not str
        or not str(provider_spec["job_generation"]).isdigit()
        or provider_spec.get("execution_name") != execution_name
        or provider_spec.get("execution_uid") != execution_uid
        or provider_spec.get("service_account_name")
        != PROVIDER_SERVICE_ACCOUNT
        or provider_spec.get("task_count") != 1
        or provider_spec.get("max_retries") != 0
        or provider_spec.get("timeout_seconds")
        != PROVIDER_TASK_TIMEOUT_SECONDS
        or provider_spec.get("image") != request["immutable_image"]
        or provider_spec.get("command") != ["/bin/bash"]
        or provider_spec.get("args") != [
            "/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh",
            "container-run", "task0",
        ]
        or provider_spec.get("cpu") != PROVIDER_CPU
        or provider_spec.get("memory") != PROVIDER_MEMORY
        or provider_spec.get("environment_names") != expected_environment_names
        or provider_spec.get("request_payload_sha256")
        != gate["request_sha256"]
        or any(
            provider_spec.get(field) != execution_row[field]
            for field in time_fields
        )
        or provider_spec.get("provider_observed_from_execution_describe")
        is not True
        or provider_spec.get("uses_realized_outcomes") is not False
        or environment.get("code_sha") != request["code_sha"]
        or environment.get("image_source_commit_sha") != request["code_sha"]
        or environment.get("image_digest") != request["image_digest"]
        or environment.get("build_id") != request["build_id"]
        or environment.get("image_uri") != request["immutable_image"]
        or environment.get("enable_name")
        != "R6_PAID_SOURCE_FP_SIS_ENABLE"
        or environment.get("enable_value")
        != "I_UNDERSTAND_FIXED_CORPUS_FP_SIS_ABLATION_V1"
        or environment.get("outcomes_name")
        != "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED"
        or environment.get("outcomes_allowed") is not False
        or environment.get("request_b64_name")
        != "R6_PAID_SOURCE_FP_SIS_REQUEST_B64"
        or environment.get("request_sha256_name")
        != "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256"
        or environment.get("request_sha256") != gate["request_sha256"]
        or environment.get("execution_request_sha256")
        != request["execution_request_sha256"]
    ):
        _fail("paid-source exact task0 provider gate differs")
    return gate


def _diagnostics_from_census(
    census: Mapping[str, object],
) -> dict[str, object]:
    cells = [
        _mapping(value, label="paid-source diagnostic cell")
        for value in census["cells"]
    ]
    rows = [{
        "cell_id": cell["cell"]["cell_id"],
        "fantasy_points_support": cell["fantasy_points_support"],
        "sis_support": cell["sis_support"],
        "component_support": cell["component_support"],
        "marginal_turnover": cell["marginal_turnover"],
        "admission_order_turnover_vs_on_on": cell[
            "admission_order_turnover_vs_on_on"
        ],
        "selected_k80_order_turnover_vs_on_on": cell[
            "selected_k80_order_turnover_vs_on_on"
        ],
        "qualifying_candidate_count": cell["retrieval"][
            "qualifying_candidate_count"
        ],
        "admitted_candidate_count": cell["retrieval"][
            "admitted_candidate_count"
        ],
        "selected_candidate_count": len(
            cell["retrieval"]["selected_k80_candidate_ids"]
        ),
    } for cell in cells]
    return {
        "raw_missing_and_stale_source_support": census["raw_source_support"],
        "served_feature_marginal_candidate_book_diagnostics": rows,
        "diagnostic_manifest_sha256": registry.canonical_sha256(rows),
        "candidate_turnover_count_all_cells": census[
            "candidate_turnover_count_all_cells"
        ],
        "world_matrix_turnover_count_all_cells": census[
            "world_matrix_turnover_count_all_cells"
        ],
    }


def validate_fp_sis_slate_task_result_v2(
    value: object,
    *,
    request_value: object,
    task0_receipt_value: object,
    task0_provider_gate_value: object,
    expected_ordinal: int,
    matrix_registry_entry: Mapping[str, object],
) -> dict[str, object]:
    request = validate_fp_sis_execution_request_v1(request_value)
    task0 = validate_fp_sis_task0_receipt_v1(
        task0_receipt_value, request_value=request
    )
    task0_provider_gate = validate_fp_sis_task0_provider_gate_v1(
        task0_provider_gate_value, request_value=request
    )
    if task0_provider_gate["operator_receipt"] != task0:
        _fail("paid-source task0 receipt/provider gate differs")
    task0_provider_gate_sha256 = registry.canonical_sha256(task0_provider_gate)
    item = _mapping(value, label=f"paid-source slate result[{expected_ordinal}]")
    _validate_hash(
        item, field="slate_result_sha256", label="paid-source slate result"
    )
    census = matchup.validate_fp_sis_retrieval_support_census_v1(
        item.get("slate_support_census")
    )
    entry = _mapping(
        matrix_registry_entry,
        label=f"paid-source matrix registry[{expected_ordinal}]",
    )
    expected_fields = {
        "schema_version", "execution_request_sha256", "task0_receipt_sha256",
        "task0_provider_gate_sha256",
        "run_id", "source_task_ordinal", "slate",
        "discovery_matrix_freeze_terminal_identity",
        "discovery_matrix_registry_reopen_sha256", "matrix_registry_entry",
        "matrix_lineage_sha256", "slate_support_census",
        "slate_support_census_sha256", "diagnostics", "admission_cap",
        "entry_budget", "one_matrix_body_read", "r4_body_read",
        "matrix_streamed_to_disk_and_memmapped",
        "selection_bank_r0_r3_float64_exact", "outcomes_read", "complete",
        "slate_result_sha256", "automatic_policy_promotion",
        "production_policy_authority", "source_value_established",
        "uses_realized_outcomes", *registry.FALSE_AUTHORITY_FIELDS,
    }
    if (
        set(item) != expected_fields
        or type(expected_ordinal) is not int
        or not 0 <= expected_ordinal < TASK_COUNT
        or item.get("schema_version") != TASK_RESULT_SCHEMA
        or item.get("execution_request_sha256")
        != request["execution_request_sha256"]
        or item.get("task0_receipt_sha256") != task0["task0_receipt_sha256"]
        or item.get("task0_provider_gate_sha256")
        != task0_provider_gate_sha256
        or item.get("run_id") != request["run_id"]
        or item.get("source_task_ordinal") != expected_ordinal
        or item.get("slate") != entry.get("slate")
        or census.get("source_task_ordinal") != expected_ordinal
        or census.get("slate") != entry.get("slate")
        or item.get("discovery_matrix_freeze_terminal_identity")
        != request["discovery_matrix_freeze_terminal_identity"]
        or not registry.is_sha256(
            item.get("discovery_matrix_registry_reopen_sha256")
        )
        or item.get("matrix_registry_entry") != entry
        or item.get("matrix_lineage_sha256")
        != entry.get("matrix_lineage_sha256")
        or item.get("slate_support_census_sha256")
        != census["slate_support_census_sha256"]
        or item.get("diagnostics") != _diagnostics_from_census(census)
        or item.get("admission_cap") != registry.MATCHUP_ADMISSION_CAP
        or item.get("entry_budget") != registry.ENTRY_BUDGET
        or item.get("one_matrix_body_read") is not True
        or item.get("r4_body_read") is not False
        or item.get("matrix_streamed_to_disk_and_memmapped") is not True
        or item.get("selection_bank_r0_r3_float64_exact") is not True
        or item.get("outcomes_read") != []
        or item.get("complete") is not True
        or any(
            item.get(field) != policy_value
            for field, policy_value in _policy(
                uses_realized_outcomes=False
            ).items()
        )
    ):
        _fail(f"paid-source slate result[{expected_ordinal}] differs")
    return item


def run_fp_sis_slate_task_v2(
    request_value: object,
    *,
    task0_receipt_value: object,
    task0_provider_gate_value: object,
    source_task_ordinal: int,
    read_exact: ReadExact,
    fetch_exact_to_file: FetchExactToFile,
    matrix_workspace: Path,
    publish_create_once: PublishCreateOnce,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
    canonical_source_v3_reopen_by_ordinal: SourceV3Reopen,
) -> dict[str, object]:
    """Execute and publish exactly one score-free slate."""

    request = validate_fp_sis_execution_request_v1(request_value)
    task0 = validate_fp_sis_task0_receipt_v1(
        task0_receipt_value, request_value=request
    )
    task0_provider_gate = validate_fp_sis_task0_provider_gate_v1(
        task0_provider_gate_value, request_value=request
    )
    if task0_provider_gate["operator_receipt"] != task0:
        _fail("paid-source task0 receipt/provider gate differs")
    if (
        type(source_task_ordinal) is not int
        or not 0 <= source_task_ordinal < TASK_COUNT
    ):
        _fail("paid-source slate task ordinal differs")
    if not all(callable(value) for value in (
        read_exact, fetch_exact_to_file, publish_create_once,
        reopen_discovery_matrix_registry, canonical_source_v3_reopen_by_ordinal,
    )):
        _fail("paid-source slate execution callbacks differ")
    _runtime_build_attestation(request, read_exact=read_exact)
    _, matrix_registry, matrix_reopen = _reopen_matrix_registry(
        request,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    if matrix_reopen["registry_reopen_sha256"] != task0[
        "discovery_matrix_registry_reopen_sha256"
    ]:
        _fail("discovery matrix registry changed after task0")
    try:
        deep = _mapping(
            canonical_source_v3_reopen_by_ordinal(source_task_ordinal),
            label=f"source-v3 reopen[{source_task_ordinal}]",
        )
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"source-v3 deep reopen[{source_task_ordinal}] failed: {exc}"
        ) from exc
    slate_input, matrix_path = _slate_input(
        ordinal=source_task_ordinal,
        deep=deep,
        matrix_registry_entry=matrix_registry[source_task_ordinal],
        read_exact=read_exact,
        fetch_exact_to_file=fetch_exact_to_file,
        workspace=matrix_workspace,
    )
    try:
        census = matchup.run_fp_sis_retrieval_support_census_v1(**slate_input)
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"paid-source slate[{source_task_ordinal}] execution failed: {exc}"
        ) from exc
    finally:
        _release_slate_matrix(slate_input, matrix_path)
    if census.get("support_gate_status") != "passed":
        _fail(f"paid-source slate[{source_task_ordinal}] support gate failed")
    body: dict[str, object] = {
        "schema_version": TASK_RESULT_SCHEMA,
        "execution_request_sha256": request["execution_request_sha256"],
        "task0_receipt_sha256": task0["task0_receipt_sha256"],
        "task0_provider_gate_sha256": registry.canonical_sha256(
            task0_provider_gate
        ),
        "run_id": request["run_id"],
        "source_task_ordinal": source_task_ordinal,
        "slate": census["slate"],
        "discovery_matrix_freeze_terminal_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "discovery_matrix_registry_reopen_sha256": matrix_reopen[
            "registry_reopen_sha256"
        ],
        "matrix_registry_entry": matrix_registry[source_task_ordinal],
        "matrix_lineage_sha256": matrix_registry[source_task_ordinal][
            "matrix_lineage_sha256"
        ],
        "slate_support_census": census,
        "slate_support_census_sha256": census["slate_support_census_sha256"],
        "diagnostics": _diagnostics_from_census(census),
        "admission_cap": registry.MATCHUP_ADMISSION_CAP,
        "entry_budget": registry.ENTRY_BUDGET,
        "one_matrix_body_read": True,
        "r4_body_read": False,
        "matrix_streamed_to_disk_and_memmapped": True,
        "selection_bank_r0_r3_float64_exact": True,
        "outcomes_read": [],
        "complete": True,
        **_policy(uses_realized_outcomes=False),
    }
    body = _with_hash(body, field="slate_result_sha256")
    validate_fp_sis_slate_task_result_v2(
        body,
        request_value=request,
        task0_receipt_value=task0,
        task0_provider_gate_value=task0_provider_gate,
        expected_ordinal=source_task_ordinal,
        matrix_registry_entry=matrix_registry[source_task_ordinal],
    )
    raw = registry.canonical_json_bytes(body)
    uri = (
        f"{request['output_prefix']}/{request['run_id']}/"
        f"tasks/{source_task_ordinal:04d}.json"
    )
    identity = _identity(
        publish_create_once(uri, raw),
        label=f"published paid-source slate[{source_task_ordinal}]",
        require_create_once=True,
    )
    if identity["uri"] != uri or _read_exact(
        identity,
        read_exact=read_exact,
        label=f"published paid-source slate[{source_task_ordinal}]",
    ) != raw:
        _fail(f"published paid-source slate[{source_task_ordinal}] differs")
    result: dict[str, object] = {
        "schema_version": TASK_PUBLICATION_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "slate": body["slate"],
        "slate_result_identity": identity,
        "slate_result_sha256": body["slate_result_sha256"],
        "task0_provider_gate_sha256": body["task0_provider_gate_sha256"],
        "one_slate_only": True,
        "matrix_body_read_count": 1,
        "complete": True,
        **_policy(uses_realized_outcomes=False),
    }
    return _with_hash(result, field="slate_publication_sha256")


def _open_slate_publication_v2(
    publication_value: object,
    *,
    ordinal: int,
    request: Mapping[str, object],
    task0: Mapping[str, object],
    task0_provider_gate: Mapping[str, object],
    matrix_registry_entry: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    publication = _mapping(
        publication_value, label=f"slate publication[{ordinal}]"
    )
    _validate_hash(
        publication,
        field="slate_publication_sha256",
        label=f"slate publication[{ordinal}]",
    )
    identity = _identity(
        publication.get("slate_result_identity"),
        label=f"slate result[{ordinal}] identity",
        require_create_once=True,
    )
    body = validate_fp_sis_slate_task_result_v2(
        _parse_canonical(
            _read_exact(
                identity, read_exact=read_exact,
                label=f"slate result[{ordinal}]",
            ),
            label=f"slate result[{ordinal}]",
        ),
        request_value=request,
        task0_receipt_value=task0,
        task0_provider_gate_value=task0_provider_gate,
        expected_ordinal=ordinal,
        matrix_registry_entry=matrix_registry_entry,
    )
    expected_fields = {
        "schema_version", "source_task_ordinal", "slate",
        "slate_result_identity", "slate_result_sha256", "one_slate_only",
        "task0_provider_gate_sha256",
        "matrix_body_read_count", "complete", "slate_publication_sha256",
        "automatic_policy_promotion", "production_policy_authority",
        "source_value_established", "uses_realized_outcomes",
        *registry.FALSE_AUTHORITY_FIELDS,
    }
    if (
        set(publication) != expected_fields
        or publication.get("schema_version") != TASK_PUBLICATION_SCHEMA
        or publication.get("source_task_ordinal") != ordinal
        or publication.get("slate") != body["slate"]
        or publication.get("slate_result_identity") != identity
        or publication.get("slate_result_sha256")
        != body["slate_result_sha256"]
        or publication.get("task0_provider_gate_sha256")
        != body["task0_provider_gate_sha256"]
        or publication.get("one_slate_only") is not True
        or publication.get("matrix_body_read_count") != 1
        or publication.get("complete") is not True
        or any(
            publication.get(field) != policy_value
            for field, policy_value in _policy(
                uses_realized_outcomes=False
            ).items()
        )
    ):
        _fail(f"slate publication[{ordinal}] differs")
    return body, identity


def collect_fp_sis_score_free_terminal_v2(
    request_value: object,
    *,
    task0_receipt_value: object,
    task0_provider_gate_value: object,
    slate_publications: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
) -> dict[str, object]:
    """Collect 54 compact results; read zero matrices; publish root last."""

    request = validate_fp_sis_execution_request_v1(request_value)
    task0 = validate_fp_sis_task0_receipt_v1(
        task0_receipt_value, request_value=request
    )
    task0_provider_gate = validate_fp_sis_task0_provider_gate_v1(
        task0_provider_gate_value, request_value=request
    )
    if task0_provider_gate["operator_receipt"] != task0:
        _fail("paid-source task0 receipt/provider gate differs")
    task0_provider_gate_sha256 = registry.canonical_sha256(task0_provider_gate)
    if not all(callable(value) for value in (
        read_exact, publish_create_once, reopen_discovery_matrix_registry,
    )):
        _fail("paid-source collector callbacks differ")
    _runtime_build_attestation(request, read_exact=read_exact)
    _, matrix_registry, matrix_reopen = _reopen_matrix_registry(
        request,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    if matrix_reopen["registry_reopen_sha256"] != task0[
        "discovery_matrix_registry_reopen_sha256"
    ]:
        _fail("discovery matrix registry changed before collect")
    publications = [
        _mapping(value, label=f"slate publication[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(slate_publications, label="slate publications")
        )
    ]
    if len(publications) != TASK_COUNT:
        _fail("paid-source collector requires exactly 54 slate publications")
    censuses: list[dict[str, object]] = []
    task_rows: list[dict[str, object]] = []
    for ordinal, publication in enumerate(publications):
        body, identity = _open_slate_publication_v2(
            publication,
            ordinal=ordinal,
            request=request,
            task0=task0,
            task0_provider_gate=task0_provider_gate,
            matrix_registry_entry=matrix_registry[ordinal],
            read_exact=read_exact,
        )
        censuses.append(body["slate_support_census"])
        task_rows.append({
            "source_task_ordinal": ordinal,
            "slate": body["slate"],
            "task0_provider_gate_sha256": body[
                "task0_provider_gate_sha256"
            ],
            "slate_result_identity": identity,
            "slate_result_sha256": body["slate_result_sha256"],
            "slate_support_census_sha256": body[
                "slate_support_census_sha256"
            ],
            "matrix_lineage_sha256": body["matrix_lineage_sha256"],
        })
    panel = matchup.build_fp_sis_panel_support_census_v1(censuses)
    if panel.get("support_gate_status") != "passed":
        _fail("paid-source 54-slate panel support gate failed")
    panel_raw = registry.canonical_json_bytes(panel)
    panel_uri = f"{request['output_prefix']}/{request['run_id']}/panel-support.json"
    panel_identity = _identity(
        publish_create_once(panel_uri, panel_raw),
        label="paid-source panel support",
        require_create_once=True,
    )
    if panel_identity["uri"] != panel_uri or _read_exact(
        panel_identity,
        read_exact=read_exact,
        label="paid-source panel support",
    ) != panel_raw:
        _fail("paid-source panel support publication differs")
    terminal: dict[str, object] = {
        "schema_version": TERMINAL_SCHEMA,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "run_id": request["run_id"],
        "frozen_at": request["frozen_at"],
        "execution_request": request,
        "execution_request_sha256": request["execution_request_sha256"],
        "task0_receipt": task0,
        "task0_receipt_sha256": task0["task0_receipt_sha256"],
        "task0_provider_gate": task0_provider_gate,
        "task0_provider_gate_sha256": task0_provider_gate_sha256,
        "discovery_matrix_freeze_terminal_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "discovery_matrix_registry_reopen_sha256": matrix_reopen[
            "registry_reopen_sha256"
        ],
        "slate_results": task_rows,
        "slate_result_manifest_sha256": registry.canonical_sha256(task_rows),
        "panel_support_identity": panel_identity,
        "panel_support_sha256": panel["panel_support_census_sha256"],
        "slate_count": TASK_COUNT,
        "cell_ids": list(registry.MATCHUP_CELL_ORDER),
        "admission_cap": registry.MATCHUP_ADMISSION_CAP,
        "entry_budget": registry.ENTRY_BUDGET,
        "one_slate_per_task": True,
        "collector_matrix_body_read_count": 0,
        "selection_bank_r0_r3_float64_exact": True,
        "all_54_score_free_slates_complete": True,
        "root_published_last": True,
        "historical_evidence_status": "awaiting-independent-grade",
        "outcomes_read": [],
        "complete": True,
        **_policy(uses_realized_outcomes=False),
    }
    terminal = _with_hash(terminal, field="terminal_sha256")
    terminal_raw = registry.canonical_json_bytes(terminal)
    terminal_identity = _identity(
        publish_create_once(request["terminal_uri"], terminal_raw),
        label="paid-source score-free terminal",
        require_create_once=True,
    )
    if terminal_identity["uri"] != request["terminal_uri"] or _read_exact(
        terminal_identity,
        read_exact=read_exact,
        label="paid-source score-free terminal",
    ) != terminal_raw:
        _fail("paid-source score-free terminal publication differs")
    reopened = reopen_fp_sis_score_free_terminal_v1(
        terminal_identity=terminal_identity,
        terminal_sha256=terminal["terminal_sha256"],
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    body: dict[str, object] = {
        "schema_version": SELECTION_RESULT_SCHEMA,
        "execution_request_sha256": request["execution_request_sha256"],
        "task0_receipt_sha256": task0["task0_receipt_sha256"],
        "task0_provider_gate_sha256": task0_provider_gate_sha256,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "run_id": request["run_id"],
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "slate_count": TASK_COUNT,
        "cell_ids": list(registry.MATCHUP_CELL_ORDER),
        "admission_cap": registry.MATCHUP_ADMISSION_CAP,
        "entry_budget": registry.ENTRY_BUDGET,
        "all_54_score_free_slates_complete": True,
        "one_slate_per_task": True,
        "collector_matrix_body_read_count": 0,
        "terminal_root_last": True,
        "independent_terminal_reopen_complete": reopened["complete"],
        "outcomes_read_during_selection": False,
        "grade_required_for_value_claim": True,
        "complete": True,
        **_policy(uses_realized_outcomes=False),
    }
    return _with_hash(body, field="selection_result_sha256")


def _removed_all54_in_memory_terminal_v1(
    request_value: object,
    *,
    task0_receipt_value: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    canonical_source_v3_reopen_by_ordinal: SourceV3Reopen,
) -> dict[str, object]:
    """Removed: the v1 path retained all 54 matrix bodies in memory."""

    _fail("all-54 in-memory paid-source execution is removed; use slate tasks")


def _terminal_envelope(
    *, terminal_identity: Mapping[str, object], terminal_sha256: str,
) -> dict[str, object]:
    identity = _identity(
        terminal_identity, label="paid-source terminal identity",
        require_create_once=True,
    )
    if not registry.is_sha256(terminal_sha256):
        _fail("paid-source terminal SHA differs")
    body: dict[str, object] = {
        "schema_version": operator.TERMINAL_ENVELOPE_SCHEMA,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "terminal_identity": identity,
        "terminal_sha256": terminal_sha256,
        "complete": True,
        "create_once": True,
        "uses_realized_outcomes": False,
    }
    body["envelope_sha256"] = registry.canonical_sha256(body)
    return body


def _reopen_fp_sis_execution_terminal_v2(
    terminal_envelope: Mapping[str, object],
    *,
    read_exact: ReadExact,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
) -> dict[str, object]:
    envelope = _mapping(terminal_envelope, label="paid-source terminal envelope")
    terminal_identity = _identity(
        envelope.get("terminal_identity"),
        label="paid-source terminal identity",
        require_create_once=True,
    )
    terminal_sha256 = envelope.get("terminal_sha256")
    terminal = _parse_canonical(
        _read_exact(
            terminal_identity, read_exact=read_exact,
            label="paid-source score-free terminal",
        ),
        label="paid-source score-free terminal",
    )
    _validate_hash(terminal, field="terminal_sha256", label="score-free terminal")
    if terminal_sha256 != terminal["terminal_sha256"]:
        _fail("paid-source terminal SHA differs")
    request = validate_fp_sis_execution_request_v1(
        terminal.get("execution_request")
    )
    task0 = validate_fp_sis_task0_receipt_v1(
        terminal.get("task0_receipt"), request_value=request
    )
    task0_provider_gate = validate_fp_sis_task0_provider_gate_v1(
        terminal.get("task0_provider_gate"), request_value=request
    )
    if task0_provider_gate["operator_receipt"] != task0:
        _fail("paid-source terminal task0 receipt/provider gate differs")
    task0_provider_gate_sha256 = registry.canonical_sha256(task0_provider_gate)
    _, matrix_registry, matrix_reopen = _reopen_matrix_registry(
        request,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    rows = [
        _mapping(value, label=f"terminal slate result[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(terminal.get("slate_results"), label="terminal slate results")
        )
    ]
    if (
        terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("experiment_id") != registry.MATCHUP_EXPERIMENT_ID
        or terminal.get("run_id") != request["run_id"]
        or terminal.get("frozen_at") != request["frozen_at"]
        or terminal.get("execution_request_sha256")
        != request["execution_request_sha256"]
        or terminal.get("task0_receipt_sha256") != task0["task0_receipt_sha256"]
        or terminal.get("task0_provider_gate_sha256")
        != task0_provider_gate_sha256
        or terminal.get("discovery_matrix_freeze_terminal_identity")
        != request["discovery_matrix_freeze_terminal_identity"]
        or terminal.get("discovery_matrix_registry_reopen_sha256")
        != matrix_reopen["registry_reopen_sha256"]
        or terminal.get("slate_count") != TASK_COUNT
        or len(rows) != TASK_COUNT
        or terminal.get("slate_result_manifest_sha256")
        != registry.canonical_sha256(rows)
        or terminal.get("cell_ids") != list(registry.MATCHUP_CELL_ORDER)
        or terminal.get("admission_cap") != registry.MATCHUP_ADMISSION_CAP
        or terminal.get("entry_budget") != registry.ENTRY_BUDGET
        or terminal.get("one_slate_per_task") is not True
        or terminal.get("collector_matrix_body_read_count") != 0
        or terminal.get("selection_bank_r0_r3_float64_exact") is not True
        or terminal.get("all_54_score_free_slates_complete") is not True
        or terminal.get("root_published_last") is not True
        or terminal.get("historical_evidence_status")
        != "awaiting-independent-grade"
        or terminal.get("outcomes_read") != []
        or terminal.get("complete") is not True
        or any(
            terminal.get(field) != policy_value
            for field, policy_value in _policy(
                uses_realized_outcomes=False
            ).items()
        )
    ):
        _fail("paid-source score-free terminal fields differ")
    censuses: list[dict[str, object]] = []
    for ordinal, row in enumerate(rows):
        identity = _identity(
            row.get("slate_result_identity"),
            label=f"terminal slate result[{ordinal}] identity",
            require_create_once=True,
        )
        result = validate_fp_sis_slate_task_result_v2(
            _parse_canonical(
                _read_exact(
                    identity, read_exact=read_exact,
                    label=f"terminal slate result[{ordinal}]",
                ),
                label=f"terminal slate result[{ordinal}]",
            ),
            request_value=request,
            task0_receipt_value=task0,
            task0_provider_gate_value=task0_provider_gate,
            expected_ordinal=ordinal,
            matrix_registry_entry=matrix_registry[ordinal],
        )
        expected_row = {
            "source_task_ordinal": ordinal,
            "slate": result["slate"],
            "task0_provider_gate_sha256": result[
                "task0_provider_gate_sha256"
            ],
            "slate_result_identity": identity,
            "slate_result_sha256": result["slate_result_sha256"],
            "slate_support_census_sha256": result[
                "slate_support_census_sha256"
            ],
            "matrix_lineage_sha256": result["matrix_lineage_sha256"],
        }
        if row != expected_row:
            _fail(f"terminal slate result lineage[{ordinal}] differs")
        censuses.append(result["slate_support_census"])
    panel_identity = _identity(
        terminal.get("panel_support_identity"),
        label="terminal panel support identity",
        require_create_once=True,
    )
    panel = matchup.validate_fp_sis_panel_support_census_v1(
        _parse_canonical(
            _read_exact(
                panel_identity, read_exact=read_exact,
                label="terminal panel support",
            ),
            label="terminal panel support",
        )
    )
    if (
        panel.get("panel_support_census_sha256")
        != terminal.get("panel_support_sha256")
        or panel != matchup.build_fp_sis_panel_support_census_v1(censuses)
    ):
        _fail("terminal panel support replay differs")
    return {
        "terminal_envelope": envelope,
        "terminal": terminal,
        "panel_support": panel,
        "slate_evidence": censuses,
        "matrix_registry_reopen_receipt": matrix_reopen,
        "task0_provider_gate": task0_provider_gate,
        "matrix_bodies_read": 0,
        "complete": True,
    }


def reopen_fp_sis_score_free_terminal_v1(
    *,
    terminal_identity: Mapping[str, object],
    terminal_sha256: str,
    read_exact: ReadExact,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
) -> dict[str, object]:
    """Reopen root and compact children without reading any matrix body."""

    envelope = _terminal_envelope(
        terminal_identity=terminal_identity,
        terminal_sha256=terminal_sha256,
    )
    reopened = _reopen_fp_sis_execution_terminal_v2(
        envelope,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    terminal = reopened["terminal"]
    task0_provider_gate = reopened["task0_provider_gate"]
    task0_execution = task0_provider_gate["execution"]
    result: dict[str, object] = {
        "schema_version": "corpus-r6-paid-source-fp-sis-terminal-reopen/v2",
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "run_id": terminal["run_id"],
        "terminal_identity": envelope["terminal_identity"],
        "terminal_sha256": terminal_sha256,
        "task0_provider_gate_sha256": registry.canonical_sha256(
            task0_provider_gate
        ),
        "task0_provider_execution": {
            "name": task0_execution["name"],
            "uid": task0_execution["uid"],
            "completion_time": task0_execution["completion_time"],
        },
        "task0_provider_execution_spec_sha256": task0_provider_gate[
            "provider_execution_spec"
        ]["provider_execution_spec_sha256"],
        "slate_count": TASK_COUNT,
        "all_children_generation_exact_reopened": True,
        "score_free_terminal_recomputed": True,
        "matrix_body_read_count": 0,
        "recognized_outcome_callback_present": False,
        "runtime_principal_outcome_authority_status": "not-evaluated",
        "outcome_artifacts_read": [],
        "publication_callback_present": False,
        "runtime_principal_write_authority_status": "not-evaluated",
        "complete": True,
        **_policy(uses_realized_outcomes=False),
    }
    return _with_hash(result, field="terminal_reopen_sha256")


def publish_fp_sis_grade_v1(
    *,
    terminal_identity: Mapping[str, object],
    terminal_sha256: str,
    grade_id: str,
    outcome_authority_identity: Mapping[str, object],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    verify_live_lease: LeaseVerifier,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
) -> dict[str, object]:
    """Open outcomes only after the score-free root, then publish one grade."""

    if type(grade_id) is not str or _GRADE_ID.fullmatch(grade_id) is None:
        _fail("paid-source grade ID differs")
    if not all(callable(value) for value in (
        read_exact, publish_create_once, verify_live_lease,
        reopen_discovery_matrix_registry,
    )):
        _fail("paid-source grade callbacks differ")
    envelope = _terminal_envelope(
        terminal_identity=terminal_identity,
        terminal_sha256=terminal_sha256,
    )
    try:
        body = grade.grade_paid_source_terminal_v1(
            envelope,
            read_exact=read_exact,
            verify_live_lease=verify_live_lease,
            grade_id=grade_id,
            outcome_authority_identity=outcome_authority_identity,
            terminal_reopen=lambda terminal_envelope, *, read_exact: (
                _reopen_fp_sis_execution_terminal_v2(
                    terminal_envelope,
                    read_exact=read_exact,
                    reopen_discovery_matrix_registry=(
                        reopen_discovery_matrix_registry
                    ),
                )
            ),
        )
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            f"paid-source recognized-outcome grade failed: {exc}"
        ) from exc
    raw = registry.canonical_json_bytes(body)
    run_id = str(_reopen_fp_sis_execution_terminal_v2(
        envelope,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )["terminal"]["run_id"])
    uri = f"{OUTPUT_PREFIX}/{run_id}/grades/{grade_id}/grade.json"
    try:
        identity = _identity(
            publish_create_once(uri, raw),
            label="published paid-source grade",
            require_create_once=True,
        )
    except Exception as exc:
        raise PaidSourceAblationExecutionV1Error(
            "paid-source grade create-once publication failed"
        ) from exc
    if identity["uri"] != uri or _read_exact(
        identity, read_exact=read_exact, label="published paid-source grade"
    ) != raw:
        _fail("published paid-source grade exact reopen differs")
    grade.validate_paid_source_grade_v1(
        _parse_canonical(raw, label="published paid-source grade")
    )
    result: dict[str, object] = {
        "schema_version": GRADE_RESULT_SCHEMA,
        "grade_id": grade_id,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "terminal_identity": envelope["terminal_identity"],
        "terminal_sha256": terminal_sha256,
        "grade_identity": identity,
        "grade_sha256": body["grade_sha256"],
        "recognized_outcome_completion_identity": body[
            "recognized_outcome_completion_identity"
        ],
        "recognized_outcome_snapshot_identity": body[
            "recognized_outcome_snapshot_identity"
        ],
        "historical_outcome_lease_identity": body[
            "historical_outcome_lease_identity"
        ],
        "score_free_terminal_reopened_before_outcomes": True,
        "grade_create_once": True,
        "grade_exact_reopened": True,
        "automatic_policy_promotion": False,
        "complete": True,
        **_policy(uses_realized_outcomes=True),
    }
    return _with_hash(result, field="grade_result_sha256")


def reopen_fp_sis_grade_v1(
    *,
    grade_identity: Mapping[str, object],
    read_exact: ReadExact,
    reopen_discovery_matrix_registry: MatrixRegistryReopen,
) -> dict[str, object]:
    """Independently replay persisted derived scores without outcome access."""

    identity = _identity(
        grade_identity, label="paid-source grade identity",
        require_create_once=True,
    )
    raw = _read_exact(
        identity, read_exact=read_exact, label="paid-source grade"
    )
    body = grade.validate_paid_source_grade_v1(
        _parse_canonical(raw, label="paid-source grade")
    )
    envelope = _terminal_envelope(
        terminal_identity=body["terminal_identity"],
        terminal_sha256=str(body["terminal_sha256"]),
    )
    reopened = _reopen_fp_sis_execution_terminal_v2(
        envelope,
        read_exact=read_exact,
        reopen_discovery_matrix_registry=reopen_discovery_matrix_registry,
    )
    if reopened.get("complete") is not True:
        _fail("paid-source score-free terminal did not reopen during grade replay")
    result: dict[str, object] = {
        "schema_version": GRADE_REOPEN_SCHEMA,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "grade_identity": identity,
        "grade_sha256": body["grade_sha256"],
        "terminal_identity": body["terminal_identity"],
        "terminal_sha256": body["terminal_sha256"],
        "persisted_derived_scores_replayed": True,
        "score_free_terminal_and_children_reopened": True,
        "recognized_outcome_completion_reread": False,
        "outcome_snapshot_reread": False,
        "historical_outcome_lease_reread": False,
        "grade_internal_aggregates_independently_recomputed": True,
        "automatic_policy_promotion": False,
        "complete": True,
        **_policy(uses_realized_outcomes=True),
    }
    return _with_hash(result, field="grade_reopen_sha256")


__all__ = [
    "GRADE_REOPEN_SCHEMA",
    "GRADE_RESULT_SCHEMA",
    "MAX_MATRIX_BYTES",
    "OUTPUT_PREFIX",
    "PaidSourceAblationExecutionV1Error",
    "PROVIDER_CPU",
    "PROVIDER_JOB_NAME",
    "PROVIDER_JOB_UID",
    "PROVIDER_MEMORY",
    "PROVIDER_PROJECT_ID",
    "PROVIDER_REGION",
    "PROVIDER_SERVICE_ACCOUNT",
    "PROVIDER_TASK_TIMEOUT_SECONDS",
    "REQUEST_SCHEMA",
    "SELECTION_RESULT_SCHEMA",
    "TASK0_SCHEMA",
    "TASK0_CLOUD_RESULT_SCHEMA",
    "TASK0_PROVIDER_SPEC_SCHEMA",
    "TASK_PUBLICATION_SCHEMA",
    "TASK_RESULT_SCHEMA",
    "TERMINAL_SCHEMA",
    "build_fp_sis_execution_request_v1",
    "collect_fp_sis_score_free_terminal_v2",
    "open_discovery_world_matrix_file_v2",
    "publish_fp_sis_grade_v1",
    "reopen_fp_sis_grade_v1",
    "reopen_fp_sis_score_free_terminal_v1",
    "run_fp_sis_slate_task_v2",
    "run_fp_sis_task0_v1",
    "validate_fp_sis_execution_request_v1",
    "validate_fp_sis_slate_task_result_v2",
    "validate_fp_sis_task0_receipt_v1",
    "validate_fp_sis_task0_provider_gate_v1",
]
