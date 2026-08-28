"""One fixed 54-slate cloud entrypoint for the R6 hard-230 population arm.

The accepted Foundry-v12 panel already names one incumbent population result
per slate.  This boundary exact-opens that result, derives the P0 target from
its complete first-occurrence unique population, decodes the generation-pinned
R6 worlds, derives one score-blind deterministic R0 world order, and invokes
the native replenishing successor through its bounded create-once process.

There is deliberately one mode: 54 all-block final-fit tasks with R0 as the
candidate origin.  The module is storage-injected, never lists a bucket or
resolves a current generation, and reads no realized or held-out outcome.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_hard230_population_process_v1 as process
from nfl_dfs.research import corpus_extreme_tail_hard230_population_successor_v1 as successor
from nfl_dfs.research import corpus_extreme_tail_hard230_r6_source_decoder_v1 as decoder
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_parametric_snapshot as snapshot
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import corpus_v12_panel_index as panel_index


CONTRACT_ID: Final = "20260828-hard230-r6-cloud-entrypoint-v1"
RUN_AUTHORIZATION_SCHEMA: Final = "hard230-r6-run-authorization/v1"
TASK_MANIFEST_SCHEMA: Final = "hard230-r6-54-task-manifest/v1"
PERMUTATION_DERIVATION_SCHEMA: Final = "hard230-r6-world-permutation-derivation/v1"
TASK_RESULT_SCHEMA: Final = "hard230-r6-task-result/v1"
PREPARATION_RESULT_SCHEMA: Final = "hard230-r6-preparation-result/v1"
JOB_CONFIGURATION_SCHEMA: Final = "hard230-r6-cloud-run-job-configuration/v1"

TASK_COUNT: Final = panel_index.V12_SOURCE_TASK_COUNT
MODE_ID: Final = "hard230-all-block-final-fit-r0-54-slate-v1"
CANDIDATE_ORIGIN_ID: Final = "R0"
HELDOUT_BLOCK: Final = None
WORLDS_PER_BLOCK: Final = successor.PRODUCTION_WORLDS_PER_BLOCK
WORLD_PERMUTATION_LAW_ID: Final = "sha256-seed-index-order-r0-v1"

FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"
OUTPUT_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
)
REUSED_JOB_CPU: Final = "8"
REUSED_JOB_MEMORY: Final = "32Gi"
TASK_TIMEOUT_SECONDS: Final = 86_400
MAXIMUM_PANEL_INDEX_BYTES: Final = 16_000_000
MAXIMUM_SOURCE_FREEZE_BYTES: Final = decoder.MAX_SOURCE_FREEZE_BYTES
MAXIMUM_POPULATION_RECEIPT_BYTES: Final = 64_000_000
MAXIMUM_AUTHORITY_BYTES: Final = 4_000_000
MAXIMUM_MANIFEST_BYTES: Final = 8_000_000
MAXIMUM_TASK_RESULT_BYTES: Final = 1_000_000

ENTRYPOINT_RELATIVE_PATH: Final = (
    "scripts/run_corpus_extreme_tail_hard230_r6_cloud_v1.py"
)
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
ENTRYPOINT_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    ENTRYPOINT_IMAGE_PATH,
    "execute-task",
)
ENABLE_ENV: Final = "HARD230_R6_ENABLE"
MANIFEST_IDENTITY_ENV: Final = "HARD230_R6_TASK_MANIFEST_IDENTITY"

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")

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

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
SolverCallback = Callable[[legal.SolveRequest], legal.SolveOutcome]


class Hard230R6CloudEntrypointV1Error(ValueError):
    """The fixed hard-230 manifest, task, or publication failed closed."""


@dataclass(frozen=True, slots=True)
class Hard230R6TaskExecutionV1:
    task_result: Mapping[str, object]
    task_result_identity: Mapping[str, object]
    process_result: process.Hard230PopulationProcessResult


def _fail(message: str) -> None:
    raise Hard230R6CloudEntrypointV1Error(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230R6CloudEntrypointV1Error(
            f"{label} is not finite canonical JSON"
        ) from exc


def _hash(value: object, *, label: str) -> str:
    return sha256(_canonical(value, label=label)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _nonempty(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return successor._object_identity(value, label=label)
    except successor.Hard230PopulationSuccessorV1Error as exc:
        raise Hard230R6CloudEntrypointV1Error(str(exc)) from exc


def _bind(
    body: Mapping[str, object], identity: object, *, label: str
) -> dict[str, object]:
    try:
        return successor._object_identity(
            identity,
            label=f"{label} identity",
            payload=_canonical(body, label=label),
        )
    except successor.Hard230PopulationSuccessorV1Error as exc:
        raise Hard230R6CloudEntrypointV1Error(str(exc)) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    if field in body:
        _fail(f"{field} cannot already be present")
    retained = dict(body)
    retained[field] = _hash(retained, label=field)
    return retained


def _validate_self_hash(
    value: object, *, field: str, label: str
) -> dict[str, object]:
    item = _mapping(value, label=label)
    retained = _sha256(item.pop(field, None), label=f"{label} SHA-256")
    if retained != _hash(item, label=f"{label} body"):
        _fail(f"{label} self-hash differs")
    return {**item, field: retained}


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hard230R6CloudEntrypointV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item, label=label) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _prefix(value: object) -> str:
    prefix = _nonempty(value, label="output prefix")
    if (
        not prefix.startswith(OUTPUT_NAMESPACE)
        or not prefix.endswith("/")
        or "?" in prefix
        or "#" in prefix
        or "//" in prefix[5:]
        or any(part in {"", ".", ".."} for part in prefix[5:-1].split("/"))
    ):
        _fail("output prefix is outside the fixed non-root research namespace")
    return prefix


def _read_bytes(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise Hard230R6CloudEntrypointV1Error(
            f"{label} generation-pinned read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} differs from its exact content identity")
    return raw, identity


def _read_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_bytes(
        identity_value,
        read_exact=read_exact,
        label=label,
        maximum_bytes=maximum_bytes,
    )
    return _strict_json(raw, label=label), identity


def _publish_json(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    raw = _canonical(value, label=label)
    if len(raw) > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise Hard230R6CloudEntrypointV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, label=f"{label} publication")
    if identity["uri"] != uri:
        _fail(f"{label} publisher returned a different URI")
    _bind(value, identity, label=label)
    reopened, _ = _read_bytes(
        identity,
        read_exact=read_exact,
        label=f"published {label}",
        maximum_bytes=maximum_bytes,
    )
    if reopened != raw:
        _fail(f"{label} exact reopen differs")
    return identity


def _validate_panel_surface(value: object) -> dict[str, object]:
    panel = _mapping(value, label="v12 panel index")
    if set(panel) != set(panel_index._PANEL_KEYS):
        _fail("v12 panel index fields differ")
    retained_sha = _sha256(
        panel.get("panel_index_sha256"), label="v12 panel index SHA-256"
    )
    if retained_sha != batch.canonical_sha256({
        key: row for key, row in panel.items() if key != "panel_index_sha256"
    }):
        _fail("v12 panel index self-hash differs")
    coverage = _mapping(panel.get("coverage"), label="v12 panel coverage")
    slates = _sequence(panel.get("accepted_slates"), label="accepted slates")
    if (
        panel.get("schema_version") != panel_index.PANEL_INDEX_SCHEMA
        or panel.get("publication_mode") != panel_index.PUBLICATION_MODE
        or panel.get("accepted_slate_count") != TASK_COUNT
        or len(slates) != TASK_COUNT
        or panel.get("exclusions") != []
        or panel.get("failures") != []
        or panel.get("missing_tasks") != []
        or coverage != {
            "expected_task_count": TASK_COUNT,
            "accepted_task_count": TASK_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        }
        or any(panel.get(field) is not False for field in panel_index._FALSE_PANEL_FIELDS)
    ):
        _fail("v12 panel index is not the complete outcome-blind 54-slate panel")
    seen_slates: set[str] = set()
    seen_p0: set[tuple[object, ...]] = set()
    normalized: list[dict[str, object]] = []
    expected_arm_ids = list(batch.PARAMETER_SET_ORDER)
    for ordinal, raw_row in enumerate(slates):
        row = _mapping(raw_row, label=f"accepted slate[{ordinal}]")
        expected_fields = {
            "slate_id", "lane_ordinal", "lane_id", "task_ordinal",
            "source_task_ordinal", "source_task_authority_sha256",
            "task_acceptance_identity", "carrier_identity", "arms",
        }
        arms = [
            _mapping(arm, label=f"accepted slate[{ordinal}] arm[{arm_ordinal}]")
            for arm_ordinal, arm in enumerate(
                _sequence(row.get("arms"), label="accepted slate arms")
            )
        ]
        slate = _nonempty(row.get("slate_id"), label="accepted slate ID")
        if (
            set(row) != expected_fields
            or row.get("source_task_ordinal") != ordinal
            or len(arms) != len(expected_arm_ids)
            or [arm.get("arm_ordinal") for arm in arms]
            != list(range(len(expected_arm_ids)))
            or [arm.get("parameter_set_id") for arm in arms] != expected_arm_ids
            or any(
                set(arm) != {"arm_ordinal", "parameter_set_id", "result_identity"}
                for arm in arms
            )
            or slate in seen_slates
        ):
            _fail("accepted slate order, arm lattice, or uniqueness differs")
        p0_identity = _identity(
            arms[0]["result_identity"], label=f"accepted slate[{ordinal}] P0 result"
        )
        identity_key = tuple(p0_identity[key] for key in ("uri", "generation", "sha256", "bytes"))
        if identity_key in seen_p0:
            _fail("P0 population result identity repeats across slates")
        seen_slates.add(slate)
        seen_p0.add(identity_key)
        normalized.append({
            "task_index": ordinal,
            "slate_id": slate,
            "p0_population_receipt_identity": p0_identity,
        })
    return {**panel, "accepted_slates": slates, "_hard230_task_rows": normalized}


def build_run_authorization_v1(
    *,
    panel_index_identity: Mapping[str, object],
    later_source_freeze_identity: Mapping[str, object],
    optimizer_source_identity: Mapping[str, object],
    terminal_build_receipt_identity: Mapping[str, object],
    output_prefix: str,
    source_commit_sha: str,
    immutable_image_digest: str,
    reused_job_name: str,
) -> dict[str, object]:
    prefix = _prefix(output_prefix)
    if _COMMIT_RE.fullmatch(source_commit_sha) is None:
        _fail("source commit must be one lowercase 40-character Git SHA")
    if (
        not immutable_image_digest.startswith("sha256:")
        or _SHA_RE.fullmatch(immutable_image_digest[7:]) is None
        or _JOB_RE.fullmatch(reused_job_name) is None
    ):
        _fail("immutable image digest or reused job name differs")
    body = {
        "schema_version": RUN_AUTHORIZATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "mode_id": MODE_ID,
        "panel_index_identity": _identity(
            panel_index_identity, label="run panel index"
        ),
        "later_source_freeze_identity": _identity(
            later_source_freeze_identity, label="run later source freeze"
        ),
        "optimizer_source_identity": _identity(
            optimizer_source_identity, label="run optimizer source"
        ),
        "terminal_build_receipt_identity": _identity(
            terminal_build_receipt_identity, label="run terminal build receipt"
        ),
        "output_prefix": prefix,
        "source_commit_sha": source_commit_sha,
        "immutable_image_digest": immutable_image_digest,
        "reused_job_name": reused_job_name,
        "task_count": TASK_COUNT,
        "candidate_origin_id": CANDIDATE_ORIGIN_ID,
        "heldout_block": HELDOUT_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "cloud_execution_attestation_present": False,
        "launch_submission_authority": False,
        "one_reused_job_required": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _self_hash(body, "run_authorization_sha256")


def validate_run_authorization_v1(value: object) -> dict[str, object]:
    item = _validate_self_hash(
        value, field="run_authorization_sha256", label="run authorization"
    )
    expected = build_run_authorization_v1(
        panel_index_identity=item.get("panel_index_identity"),
        later_source_freeze_identity=item.get("later_source_freeze_identity"),
        optimizer_source_identity=item.get("optimizer_source_identity"),
        terminal_build_receipt_identity=item.get("terminal_build_receipt_identity"),
        output_prefix=str(item.get("output_prefix", "")),
        source_commit_sha=str(item.get("source_commit_sha", "")),
        immutable_image_digest=str(item.get("immutable_image_digest", "")),
        reused_job_name=str(item.get("reused_job_name", "")),
    )
    if _canonical(item, label="run authorization") != _canonical(
        expected, label="expected run authorization"
    ):
        _fail("run authorization canonical replay differs")
    return expected


def build_task_manifest_v1(
    *,
    run_authorization: Mapping[str, object],
    run_authorization_identity: Mapping[str, object],
    panel_index_sha256: str,
    later_source_freeze_sha256: str,
    task_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    authorization = validate_run_authorization_v1(run_authorization)
    authorization_identity = _bind(
        authorization, run_authorization_identity, label="run authorization"
    )
    rows = [_mapping(row, label=f"task row[{index}]") for index, row in enumerate(task_rows)]
    if len(rows) != TASK_COUNT:
        _fail("hard230 task manifest requires exactly 54 task rows")
    normalized: list[dict[str, object]] = []
    seen_slates: set[str] = set()
    seen_receipts: set[tuple[object, ...]] = set()
    for ordinal, row in enumerate(rows):
        if set(row) != {"task_index", "slate_id", "p0_population_receipt_identity"}:
            _fail(f"hard230 task row[{ordinal}] fields differ")
        slate = _nonempty(row.get("slate_id"), label=f"task row[{ordinal}] slate")
        identity = _identity(
            row.get("p0_population_receipt_identity"),
            label=f"task row[{ordinal}] P0 population receipt",
        )
        identity_key = tuple(identity[key] for key in ("uri", "generation", "sha256", "bytes"))
        if row.get("task_index") != ordinal or slate in seen_slates or identity_key in seen_receipts:
            _fail("hard230 task row order or uniqueness differs")
        seen_slates.add(slate)
        seen_receipts.add(identity_key)
        normalized.append({
            "task_index": ordinal,
            "slate_id": slate,
            "p0_population_receipt_identity": identity,
            "task_output_prefix": (
                f"{authorization['output_prefix']}tasks/task-{ordinal:03d}-{slate}/"
            ),
        })
    body = {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "contract_id": CONTRACT_ID,
        "mode_id": MODE_ID,
        "run_authorization_identity": authorization_identity,
        "run_authorization_sha256": authorization["run_authorization_sha256"],
        "panel_index_identity": authorization["panel_index_identity"],
        "panel_index_sha256": _sha256(
            panel_index_sha256, label="panel index SHA-256"
        ),
        "later_source_freeze_identity": authorization[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": _sha256(
            later_source_freeze_sha256, label="later source freeze SHA-256"
        ),
        "optimizer_source_identity": authorization["optimizer_source_identity"],
        "terminal_build_receipt_identity": authorization[
            "terminal_build_receipt_identity"
        ],
        "source_commit_sha": authorization["source_commit_sha"],
        "immutable_image_digest": authorization["immutable_image_digest"],
        "reused_job_name": authorization["reused_job_name"],
        "output_prefix": authorization["output_prefix"],
        "task_count": TASK_COUNT,
        "candidate_origin_id": CANDIDATE_ORIGIN_ID,
        "heldout_block": HELDOUT_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "task_rows": normalized,
        "task_rows_sha256": _hash(normalized, label="hard230 task rows"),
        "one_manifest_one_mode": True,
        "one_cloud_task_per_slate": True,
        "current_generation_input_lookup_allowed": False,
        "bucket_listing_allowed": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    retained = _self_hash(body, "task_manifest_sha256")
    if len(_canonical(retained, label="task manifest")) > MAXIMUM_MANIFEST_BYTES:
        _fail("hard230 task manifest exceeds its byte ceiling")
    return retained


def validate_task_manifest_v1(
    value: object, *, run_authorization: Mapping[str, object]
) -> dict[str, object]:
    item = _validate_self_hash(
        value, field="task_manifest_sha256", label="task manifest"
    )
    expected = build_task_manifest_v1(
        run_authorization=run_authorization,
        run_authorization_identity=item.get("run_authorization_identity"),
        panel_index_sha256=str(item.get("panel_index_sha256", "")),
        later_source_freeze_sha256=str(
            item.get("later_source_freeze_sha256", "")
        ),
        task_rows=[
            {
                "task_index": row.get("task_index"),
                "slate_id": row.get("slate_id"),
                "p0_population_receipt_identity": row.get(
                    "p0_population_receipt_identity"
                ),
            }
            for row in [
                _mapping(raw, label=f"task row[{index}]")
                for index, raw in enumerate(
                    _sequence(item.get("task_rows"), label="task manifest rows")
                )
            ]
        ],
    )
    if _canonical(item, label="task manifest") != _canonical(
        expected, label="expected task manifest"
    ):
        _fail("task manifest canonical replay differs")
    return expected


def build_cloud_run_job_configuration_v1(
    *, task_manifest: Mapping[str, object], task_manifest_identity: object
) -> dict[str, object]:
    manifest = _validate_self_hash(
        task_manifest, field="task_manifest_sha256", label="task manifest"
    )
    manifest_identity = _bind(
        manifest, task_manifest_identity, label="task manifest"
    )
    environment = {
        ENABLE_ENV: "1",
        MANIFEST_IDENTITY_ENV: _canonical(
            manifest_identity, label="manifest identity environment"
        ).decode("utf-8"),
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": manifest["source_commit_sha"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["immutable_image_digest"],
    }
    return {
        "schema_version": JOB_CONFIGURATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "mode_id": MODE_ID,
        "reused_job_name": manifest["reused_job_name"],
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "container_command": [ENTRYPOINT_COMMAND[0]],
        "container_args": list(ENTRYPOINT_COMMAND[1:]),
        "container_environment": environment,
        "task_count": TASK_COUNT,
        "parallelism": TASK_COUNT,
        "max_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "cpu": REUSED_JOB_CPU,
        "memory": REUSED_JOB_MEMORY,
        "new_job_creation_allowed": False,
        "one_manifest_one_mode": True,
    }


def prepare_54_task_manifest_v1(
    *,
    panel_index_identity: Mapping[str, object],
    later_source_freeze_identity: Mapping[str, object],
    optimizer_source_identity: Mapping[str, object],
    terminal_build_receipt_identity: Mapping[str, object],
    output_prefix: str,
    source_commit_sha: str,
    immutable_image_digest: str,
    reused_job_name: str,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Publish one prelaunch authorization and one exact 54-task manifest."""
    prefix = _prefix(output_prefix)
    panel_value, retained_panel_identity = _read_json(
        panel_index_identity,
        read_exact=read_exact,
        label="v12 panel index",
        maximum_bytes=MAXIMUM_PANEL_INDEX_BYTES,
    )
    panel = _validate_panel_surface(panel_value)
    source_raw, retained_source_identity = _read_bytes(
        later_source_freeze_identity,
        read_exact=read_exact,
        label="later source freeze",
        maximum_bytes=MAXIMUM_SOURCE_FREEZE_BYTES,
    )
    try:
        source_freeze = decoder._parse_source_freeze(source_raw)
    except decoder.Hard230R6SourceDecoderV1Error as exc:
        raise Hard230R6CloudEntrypointV1Error(str(exc)) from exc
    source_slates = [
        str(row.get("slate_id"))
        for row in _sequence(source_freeze.get("slates"), label="source slates")
        if isinstance(row, Mapping)
    ]
    panel_slates = [str(row["slate_id"]) for row in panel["_hard230_task_rows"]]
    if source_slates != panel_slates:
        _fail("later-source and accepted-panel 54-slate order differs")
    authorization = build_run_authorization_v1(
        panel_index_identity=retained_panel_identity,
        later_source_freeze_identity=retained_source_identity,
        optimizer_source_identity=optimizer_source_identity,
        terminal_build_receipt_identity=terminal_build_receipt_identity,
        output_prefix=prefix,
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
        reused_job_name=reused_job_name,
    )
    authorization_identity = _publish_json(
        uri=f"{prefix}authorities/run-authorization.json",
        value=authorization,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="run authorization",
    )
    manifest = build_task_manifest_v1(
        run_authorization=authorization,
        run_authorization_identity=authorization_identity,
        panel_index_sha256=str(panel["panel_index_sha256"]),
        later_source_freeze_sha256=str(source_freeze["freeze_sha256"]),
        task_rows=panel["_hard230_task_rows"],
    )
    manifest_identity = _publish_json(
        uri=f"{prefix}authorities/task-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="task manifest",
    )
    return {
        "schema_version": PREPARATION_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "mode_id": MODE_ID,
        "run_authorization_identity": authorization_identity,
        "task_manifest_identity": manifest_identity,
        "task_count": TASK_COUNT,
        "cloud_run_job_configuration": build_cloud_run_job_configuration_v1(
            task_manifest=manifest,
            task_manifest_identity=manifest_identity,
        ),
        "outcome_columns_read": [],
        **_false_authorities(),
    }


def derive_world_permutation_v1(
    *,
    slate_id: str,
    source_lineage: Mapping[str, object],
    p0_target_authority_identity: Mapping[str, object],
    population_receipt_identity: Mapping[str, object],
    population_result_sha256: str,
) -> tuple[dict[str, object], list[int]]:
    """Return an explicit SHA-256-keyed permutation and its compact proof."""
    seed_input = {
        "law_id": WORLD_PERMUTATION_LAW_ID,
        "mode_id": MODE_ID,
        "slate_id": _nonempty(slate_id, label="permutation slate ID"),
        "candidate_origin_id": CANDIDATE_ORIGIN_ID,
        "heldout_block": HELDOUT_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "source_lineage": _mapping(source_lineage, label="permutation source lineage"),
        "p0_target_authority_identity": _identity(
            p0_target_authority_identity, label="permutation P0 target"
        ),
        "population_receipt_identity": _identity(
            population_receipt_identity, label="permutation population receipt"
        ),
        "population_result_sha256": _sha256(
            population_result_sha256, label="population result SHA-256"
        ),
    }
    seed_sha = _hash(seed_input, label="world permutation seed input")
    seed = bytes.fromhex(seed_sha)
    order = sorted(
        range(WORLDS_PER_BLOCK),
        key=lambda index: (
            sha256(seed + index.to_bytes(4, "big", signed=False)).digest(), index
        ),
    )
    derivation = _self_hash({
        "schema_version": PERMUTATION_DERIVATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "law_id": WORLD_PERMUTATION_LAW_ID,
        "seed_input": seed_input,
        "seed_sha256": seed_sha,
        "ordered_world_indices_sha256": _hash(
            order, label="ordered world indices"
        ),
        "world_count": WORLDS_PER_BLOCK,
        "full_permutation_verified": sorted(order) == list(range(WORLDS_PER_BLOCK)),
        "outcome_columns_read": [],
        **_false_authorities(),
    }, "permutation_derivation_sha256")
    return derivation, order


def _population_target(
    *,
    raw: bytes,
    identity: Mapping[str, object],
    expected_slate_id: str,
    expected_source_freeze_sha256: str,
    players: Sequence[object],
) -> tuple[dict[str, object], list[str]]:
    try:
        result = snapshot.validate_variant_result_bytes(
            raw, identity=identity, require_authoritative=True
        )
    except snapshot.CorpusParametricSnapshotError as exc:
        raise Hard230R6CloudEntrypointV1Error(
            f"P0 population receipt differs: {exc}"
        ) from exc
    profile = _mapping(result.get("profile"), label="P0 population profile")
    slate = _mapping(result.get("slate"), label="P0 population slate")
    if (
        profile.get("ordinal") != 0
        or profile.get("parameter_set_id") != "incumbent"
        or slate.get("slate_id") != expected_slate_id
        or result.get("later_source_freeze_manifest_sha256")
        != expected_source_freeze_sha256
    ):
        _fail("P0 population profile, slate, or source-freeze binding differs")
    visits = [
        tuple(str(player_id) for player_id in _sequence(row, label="P0 visit roster"))
        for row in _sequence(result.get("visit_rosters"), label="P0 visit rosters")
    ]
    unique = [
        tuple(str(player_id) for player_id in _sequence(row, label="P0 unique roster"))
        for row in _sequence(result.get("unique_rosters"), label="P0 unique rosters")
    ]
    first = _sequence(
        result.get("first_occurrence_visit_indices"),
        label="P0 first-occurrence indices",
    )
    replay_unique, replay_first = legal.first_occurrence_unique(visits)
    if tuple(unique) != replay_unique or tuple(first) != replay_first:
        _fail("P0 population first-occurrence deduplication does not replay")
    incumbent = legal.frozen_policy_profiles()[0]
    if incumbent.parameter_set_id != "incumbent":
        _fail("frozen profile zero is no longer incumbent")
    lineup_ids: list[str] = []
    for ordinal, roster in enumerate(unique):
        try:
            audited = legal.audit_dk_classic(players, roster)
            legal._audit_profile_compliance(players, audited, incumbent)
        except legal.CorpusLegalFeasibilityError as exc:
            raise Hard230R6CloudEntrypointV1Error(
                f"P0 unique roster[{ordinal}] is not incumbent legal: {exc}"
            ) from exc
        lineup_ids.append(v12_import.canonical_lineup_id(slate, audited))
    if not lineup_ids or len(set(lineup_ids)) != len(lineup_ids):
        _fail("P0 population is empty or has duplicate canonical lineup IDs")
    return result, lineup_ids


def _open_manifest(
    *, manifest_identity: object, read_exact: ReadExact
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    manifest_value, retained_manifest_identity = _read_json(
        manifest_identity,
        read_exact=read_exact,
        label="hard230 task manifest",
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    authorization_value, authorization_identity = _read_json(
        manifest_value.get("run_authorization_identity"),
        read_exact=read_exact,
        label="hard230 run authorization",
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
    )
    authorization = validate_run_authorization_v1(authorization_value)
    manifest = validate_task_manifest_v1(
        manifest_value, run_authorization=authorization
    )
    _bind(manifest, retained_manifest_identity, label="task manifest")
    if authorization_identity != manifest["run_authorization_identity"]:
        _fail("manifest run-authorization exact identity differs")
    return manifest, retained_manifest_identity, authorization


def execute_manifest_task_v1(
    *,
    manifest_identity: Mapping[str, object],
    task_index: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    solver_callback: SolverCallback = legal.default_cbc_solver,
) -> Hard230R6TaskExecutionV1:
    """Execute one of the exactly 54 predeclared final-fit tasks."""
    manifest, retained_manifest_identity, authorization = _open_manifest(
        manifest_identity=manifest_identity, read_exact=read_exact
    )
    if type(task_index) is not int or not 0 <= task_index < TASK_COUNT:
        _fail("Cloud task index is outside 0..53")
    task = _mapping(manifest["task_rows"][task_index], label="hard230 task row")
    if task.get("task_index") != task_index:
        _fail("Cloud task index differs from its manifest row")
    slate_id = str(task["slate_id"])
    task_prefix = str(task["task_output_prefix"])
    prepared = decoder.materialize_hard230_r6_source_v1(
        later_source_freeze_identity=manifest["later_source_freeze_identity"],
        slate_id=slate_id,
        heldout_block=HELDOUT_BLOCK,
        output_prefix=f"{task_prefix}decoder",
        read_exact=read_exact,
        publish_create_once=publish_create_once,
    )
    population_raw, population_identity = _read_bytes(
        task["p0_population_receipt_identity"],
        read_exact=read_exact,
        label="P0 population receipt",
        maximum_bytes=MAXIMUM_POPULATION_RECEIPT_BYTES,
    )
    population, lineup_ids = _population_target(
        raw=population_raw,
        identity=population_identity,
        expected_slate_id=slate_id,
        expected_source_freeze_sha256=str(
            manifest["later_source_freeze_sha256"]
        ),
        players=prepared.players,
    )
    p0_target = successor.build_p0_target_authority_v1(
        slate_id=slate_id,
        candidate_origin_id=CANDIDATE_ORIGIN_ID,
        heldout_block=HELDOUT_BLOCK,
        source_lineage=prepared.source_lineage,
        retained_lineup_ids=lineup_ids,
        population_receipt_identity=population_identity,
    )
    p0_identity = _publish_json(
        uri=f"{task_prefix}authorities/p0-target.json",
        value=p0_target,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="P0 target authority",
    )
    derivation, order = derive_world_permutation_v1(
        slate_id=slate_id,
        source_lineage=prepared.source_lineage,
        p0_target_authority_identity=p0_identity,
        population_receipt_identity=population_identity,
        population_result_sha256=str(population["result_sha256"]),
    )
    derivation_identity = _publish_json(
        uri=f"{task_prefix}authorities/world-permutation-derivation.json",
        value=derivation,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="world permutation derivation",
    )
    permutation = successor.build_world_permutation_authority_v1(
        slate_id=slate_id,
        candidate_origin_id=CANDIDATE_ORIGIN_ID,
        heldout_block=HELDOUT_BLOCK,
        worlds_per_block=WORLDS_PER_BLOCK,
        ordered_world_indices=order,
        source_lineage=prepared.source_lineage,
        derivation_identity=derivation_identity,
    )
    permutation_identity = _publish_json(
        uri=f"{task_prefix}authorities/world-permutation.json",
        value=permutation,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="world permutation authority",
    )
    budget = process.build_process_budget_v1(
        slate_id=slate_id,
        candidate_origin_id=CANDIDATE_ORIGIN_ID,
        heldout_block=HELDOUT_BLOCK,
        p0_target_authority=p0_target,
        p0_target_authority_identity=p0_identity,
        world_permutation_authority=permutation,
        world_permutation_authority_identity=permutation_identity,
        output_prefix=f"{task_prefix}process",
        execution_mode=successor.RELEASE_EXECUTION_MODE,
    )
    budget_identity = _publish_json(
        uri=f"{task_prefix}authorities/process-budget.json",
        value=budget,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="process budget",
    )
    runtime = successor.build_runtime_authority_v1(
        slate_id=slate_id,
        candidate_origin_id=CANDIDATE_ORIGIN_ID,
        heldout_block=HELDOUT_BLOCK,
        source_commit_sha=str(manifest["source_commit_sha"]),
        immutable_image_digest=str(manifest["immutable_image_digest"]),
        contract_source_sha256=sha256(Path(successor.__file__).read_bytes()).hexdigest(),
        process_source_sha256=sha256(Path(process.__file__).read_bytes()).hexdigest(),
        solver_implementation_sha256=sha256(Path(legal.__file__).read_bytes()).hexdigest(),
        solver_authority_sha256=legal.canonical_sha256(
            legal._cbc_runtime_authority()
        ),
        optimizer_source_identity=authorization["optimizer_source_identity"],
        terminal_build_receipt_identity=authorization[
            "terminal_build_receipt_identity"
        ],
        task_manifest_identity=retained_manifest_identity,
        launch_intent_identity=manifest["run_authorization_identity"],
        process_budget_identity=budget_identity,
        p0_target_authority_identity=p0_identity,
        world_permutation_authority_identity=permutation_identity,
    )
    runtime_identity = _publish_json(
        uri=f"{task_prefix}authorities/runtime.json",
        value=runtime,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="runtime authority",
    )
    request = process.build_process_request_v1(
        task_index=task_index,
        process_budget=budget,
        process_budget_identity=budget_identity,
        source_member_identity=prepared.source_member_identity,
        score_block_identities=prepared.score_block_identities,
        player_registry_sha256=str(prepared.source_lineage["player_registry_sha256"]),
        score_matrix_identity=prepared.score_matrix_identity,
        p0_target_authority_identity=p0_identity,
        world_permutation_authority_identity=permutation_identity,
        runtime_authority_identity=runtime_identity,
        require_production_width=True,
    )
    request_identity = _publish_json(
        uri=f"{task_prefix}authorities/process-request.json",
        value=request,
        maximum_bytes=MAXIMUM_AUTHORITY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="process request",
    )
    scientific = process.execute_and_publish_process_v1(
        process_request=request,
        process_request_identity=request_identity,
        process_budget=budget,
        process_budget_identity=budget_identity,
        player_registry=prepared.player_registry,
        score_matrix=prepared.score_matrix,
        p0_target_authority=p0_target,
        world_permutation_authority=permutation,
        runtime_authority=runtime,
        publisher=publish_create_once,
        reader=read_exact,
        solver_callback=solver_callback,
    )
    successor_receipt = scientific.scientific_result.receipt
    control = successor_receipt["score_blind_control_population"]
    challenger = successor_receipt["hard230_challenger_population"]
    task_result = _self_hash({
        "schema_version": TASK_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "mode_id": MODE_ID,
        "complete": True,
        "task_index": task_index,
        "slate_id": slate_id,
        "task_manifest_identity": retained_manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "p0_population_receipt_identity": population_identity,
        "p0_population_result_sha256": population["result_sha256"],
        "p0_target_authority_identity": p0_identity,
        "p0_target_authority_sha256": p0_target["p0_target_authority_sha256"],
        "p0_target_count": len(lineup_ids),
        "world_permutation_derivation_identity": derivation_identity,
        "world_permutation_authority_identity": permutation_identity,
        "world_permutation_authority_sha256": permutation[
            "world_permutation_authority_sha256"
        ],
        "source_member_identity": prepared.source_member_identity,
        "score_matrix_identity": prepared.score_matrix_identity,
        "process_budget_identity": budget_identity,
        "runtime_authority_identity": runtime_identity,
        "process_request_identity": request_identity,
        "process_receipt_identity": scientific.process_receipt_identity,
        "process_receipt_sha256": scientific.process_receipt[
            "process_receipt_sha256"
        ],
        "evidence_index_identity": scientific.evidence_index_identity,
        "evidence_index_sha256": scientific.evidence_index[
            "evidence_index_sha256"
        ],
        "actual_shared_solver_call_count": successor_receipt[
            "actual_shared_solver_call_count"
        ],
        "hard230_exact_target_reached": successor_receipt[
            "hard230_exact_target_reached"
        ],
        "hard230_shortfall": successor_receipt["hard230_shortfall"],
        "score_blind_control_population_count": control[
            "population_lineup_count"
        ],
        "score_blind_control_population_sha256": control[
            "population_rosters_sha256"
        ],
        "hard230_challenger_population_count": challenger[
            "population_lineup_count"
        ],
        "hard230_challenger_population_sha256": challenger[
            "population_rosters_sha256"
        ],
        "terminal_execution_attestation_present": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }, "task_result_sha256")
    task_result_identity = _publish_json(
        uri=f"{task_prefix}task-result.json",
        value=task_result,
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="task result",
    )
    return Hard230R6TaskExecutionV1(
        task_result=task_result,
        task_result_identity=task_result_identity,
        process_result=scientific,
    )


def validate_task_result_v1(value: object) -> dict[str, object]:
    item = _validate_self_hash(
        value, field="task_result_sha256", label="task result"
    )
    if (
        item.get("schema_version") != TASK_RESULT_SCHEMA
        or item.get("contract_id") != CONTRACT_ID
        or item.get("mode_id") != MODE_ID
        or item.get("complete") is not True
        or item.get("terminal_execution_attestation_present") is not False
        or item.get("outcome_columns_read") != []
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("task result fixed law or false-authority boundary differs")
    for field in (
        "task_manifest_identity", "p0_population_receipt_identity",
        "p0_target_authority_identity", "world_permutation_derivation_identity",
        "world_permutation_authority_identity", "process_budget_identity",
        "runtime_authority_identity", "process_request_identity",
        "process_receipt_identity", "evidence_index_identity",
    ):
        _identity(item.get(field), label=f"task result {field}")
    return item


__all__ = [
    "CANDIDATE_ORIGIN_ID",
    "CONTRACT_ID",
    "ENABLE_ENV",
    "ENTRYPOINT_COMMAND",
    "FIXED_GCP_PROJECT",
    "FIXED_STORAGE_ENDPOINT",
    "Hard230R6CloudEntrypointV1Error",
    "Hard230R6TaskExecutionV1",
    "MANIFEST_IDENTITY_ENV",
    "MODE_ID",
    "TASK_COUNT",
    "build_cloud_run_job_configuration_v1",
    "build_run_authorization_v1",
    "build_task_manifest_v1",
    "derive_world_permutation_v1",
    "execute_manifest_task_v1",
    "prepare_54_task_manifest_v1",
    "validate_run_authorization_v1",
    "validate_task_manifest_v1",
    "validate_task_result_v1",
]
