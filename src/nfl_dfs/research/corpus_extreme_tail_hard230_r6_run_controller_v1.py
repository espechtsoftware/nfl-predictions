"""Minimal smoke/full controller and terminal root for the R6 hard-230 run.

The scientific entrypoint owns one immutable 54-slate manifest.  This module
does not change that science.  It wraps the manifest with either a one-task
ordinal-zero smoke or the exact 54-task fanout, and it collects only the
manifest-known create-once task roots.  Every collected process receipt is
deep-opened before a compact, grader-facing terminal root becomes visible.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_hard230_population_process_v1 as process
from nfl_dfs.research import corpus_extreme_tail_hard230_population_successor_v1 as successor
from nfl_dfs.research import corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as entrypoint
from nfl_dfs.research import corpus_legal_feasibility as legal


CONTRACT_ID: Final = "20260828-hard230-r6-score-run-controller-v1"
CONTROLLER_MANIFEST_SCHEMA: Final = "hard230-r6-score-run-controller-manifest/v1"
CONTROLLER_PREPARATION_SCHEMA: Final = "hard230-r6-score-run-controller-preparation/v1"
LAUNCH_RECEIPT_SCHEMA: Final = "hard230-r6-score-run-launch-receipt/v1"
FINAL_ROOT_SCHEMA: Final = "hard230-r6-score-run-final-root/v1"
NOVEL_ROSTER_GRADER_ADAPTER_ID: Final = "hard230-v1"

TASK0_SMOKE_SCOPE: Final = "task0-smoke"
FULL_54_SCOPE: Final = "full-54"
SCOPES: Final = (TASK0_SMOKE_SCOPE, FULL_54_SCOPE)

REUSED_JOB_NAME: Final = "atlas-minimal-c-s2023-w2-v1"
REUSED_JOB_UID: Final = "a9389eb4-da2b-4e4a-90a4-9ef769043e1d"

CONTROLLER_MANIFEST_IDENTITY_ENV: Final = (
    "HARD230_R6_CONTROLLER_MANIFEST_IDENTITY"
)
CONTROLLER_ENTRYPOINT_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    entrypoint.ENTRYPOINT_IMAGE_PATH,
    "execute-controller-task",
)

MAXIMUM_CONTROLLER_MANIFEST_BYTES: Final = 4_000_000
MAXIMUM_LAUNCH_RECEIPT_BYTES: Final = 1_000_000
MAXIMUM_FINAL_ROOT_BYTES: Final = 4_000_000

ReadExact = Callable[[Mapping[str, object]], bytes]
OpenKnown = Callable[[str, int], tuple[bytes, Mapping[str, object]]]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


class Hard230R6RunControllerV1Error(ValueError):
    """The hard-230 controller or deterministic collection failed closed."""


def _fail(message: str) -> None:
    raise Hard230R6RunControllerV1Error(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230R6RunControllerV1Error(
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


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return entrypoint._identity(value, label=label)
    except entrypoint.Hard230R6CloudEntrypointV1Error as exc:
        raise Hard230R6RunControllerV1Error(str(exc)) from exc


def _bind(
    value: Mapping[str, object], identity: object, *, label: str
) -> dict[str, object]:
    try:
        return entrypoint._bind(value, identity, label=label)
    except entrypoint.Hard230R6CloudEntrypointV1Error as exc:
        raise Hard230R6RunControllerV1Error(str(exc)) from exc


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
    retained = item.pop(field, None)
    if (
        type(retained) is not str
        or len(retained) != 64
        or retained != _hash(item, label=f"{label} body")
    ):
        _fail(f"{label} self-hash differs")
    return {**item, field: retained}


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        import json

        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Hard230R6RunControllerV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item, label=label) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _read_json(
    identity: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _identity(identity, label=f"{label} identity")
    if int(retained["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    raw = read_exact(retained)
    if (
        type(raw) is not bytes
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    return _strict_json(raw, label=label), retained


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
    identity = _identity(
        publish_create_once(uri, raw), label=f"published {label}"
    )
    if identity["uri"] != uri or read_exact(identity) != raw:
        _fail(f"{label} create-once exact reopen differs")
    return identity


def _scope_task_indices(scope_id: str) -> list[int]:
    if scope_id == TASK0_SMOKE_SCOPE:
        return [0]
    if scope_id == FULL_54_SCOPE:
        return list(range(entrypoint.TASK_COUNT))
    _fail("hard230 controller scope differs")


def _grader_population_contract() -> dict[str, object]:
    return {
        "contract_id": "generation-exact-process-receipt-population-rosters/v1",
        "one_population_descriptor_per_role_per_slate": True,
        "population_roles": ["score-blind-control", "hard230-challenger"],
        "rosters_are_reached_by_exact_process_receipt_identity_and_json_pointer": True,
        "population_rosters_hash_is_canonical_json_sha256": True,
        "lineup_identity_field": "lineup_id",
        "roster_membership_field": "roster_player_ids",
    }


def _controller_prefix(source_manifest: Mapping[str, object], scope_id: str) -> str:
    prefix = _nonempty(
        source_manifest.get("output_prefix"), label="source output prefix"
    )
    if not prefix.endswith("/"):
        _fail("source output prefix must end in slash")
    return f"{prefix}controller/{scope_id}/"


def build_controller_manifest_v1(
    *,
    source_task_manifest: Mapping[str, object],
    source_task_manifest_identity: Mapping[str, object],
    scope_id: str,
    required_smoke_final_root_identity: Mapping[str, object] | None = None,
    required_smoke_final_root_sha256: str | None = None,
) -> dict[str, object]:
    """Build one thin execution manifest over the immutable science manifest."""
    source = _mapping(source_task_manifest, label="source task manifest")
    source_identity = _bind(
        source, source_task_manifest_identity, label="source task manifest"
    )
    if (
        source.get("schema_version") != entrypoint.TASK_MANIFEST_SCHEMA
        or source.get("mode_id") != entrypoint.MODE_ID
        or source.get("task_count") != entrypoint.TASK_COUNT
        or source.get("reused_job_name") != REUSED_JOB_NAME
    ):
        _fail("source task manifest hard230 law or fixed idle job differs")
    indices = _scope_task_indices(scope_id)
    smoke_identity: dict[str, object] | None
    if scope_id == TASK0_SMOKE_SCOPE:
        if (
            required_smoke_final_root_identity is not None
            or required_smoke_final_root_sha256 is not None
        ):
            _fail("task0 smoke cannot depend on a prior smoke root")
        smoke_identity = None
        smoke_sha = None
    else:
        smoke_identity = _identity(
            required_smoke_final_root_identity,
            label="required task0 smoke final root",
        )
        if (
            type(required_smoke_final_root_sha256) is not str
            or len(required_smoke_final_root_sha256) != 64
        ):
            _fail("required task0 smoke final-root SHA-256 differs")
        smoke_sha = required_smoke_final_root_sha256
    rows = _sequence(source.get("task_rows"), label="source task rows")
    expected_results: list[dict[str, object]] = []
    for cloud_index, scientific_index in enumerate(indices):
        row = _mapping(
            rows[scientific_index],
            label=f"source task row[{scientific_index}]",
        )
        expected_results.append({
            "cloud_task_index": cloud_index,
            "scientific_task_index": scientific_index,
            "slate_id": row.get("slate_id"),
            "task_result_uri": f"{row.get('task_output_prefix')}task-result.json",
        })
    prefix = _controller_prefix(source, scope_id)
    body = {
        "schema_version": CONTROLLER_MANIFEST_SCHEMA,
        "contract_id": CONTRACT_ID,
        "scope_id": scope_id,
        "source_task_manifest_identity": source_identity,
        "source_task_manifest_sha256": source.get("task_manifest_sha256"),
        "source_commit_sha": source.get("source_commit_sha"),
        "immutable_image_digest": source.get("immutable_image_digest"),
        "source_reused_job_name": source.get("reused_job_name"),
        "reused_job_name": REUSED_JOB_NAME,
        "reused_job_uid": REUSED_JOB_UID,
        "source_output_prefix": source.get("output_prefix"),
        "output_prefix": prefix,
        "cloud_task_count": len(indices),
        "scientific_task_count": entrypoint.TASK_COUNT,
        "scientific_task_indices": indices,
        "expected_task_results": expected_results,
        "expected_task_results_sha256": _hash(
            expected_results, label="controller expected task results"
        ),
        "required_smoke_final_root_identity": smoke_identity,
        "required_smoke_final_root_sha256": smoke_sha,
        "launch_receipt_uri": f"{prefix}launch-receipt.json",
        "final_root_uri": f"{prefix}final-root.json",
        "one_cloud_task_per_scientific_task": True,
        "task0_smoke_required_before_full": True,
        "current_generation_input_lookup_allowed": False,
        "known_create_once_result_generation_resolution_allowed": True,
        "bucket_listing_allowed": False,
        "logs_read": False,
        "outcome_columns_read": [],
        **entrypoint._false_authorities(),
    }
    retained = _self_hash(body, "controller_manifest_sha256")
    if len(_canonical(retained, label="controller manifest")) > MAXIMUM_CONTROLLER_MANIFEST_BYTES:
        _fail("controller manifest exceeds its byte ceiling")
    return retained


def validate_controller_manifest_v1(
    value: object, *, source_task_manifest: Mapping[str, object]
) -> dict[str, object]:
    item = _validate_self_hash(
        value,
        field="controller_manifest_sha256",
        label="controller manifest",
    )
    expected = build_controller_manifest_v1(
        source_task_manifest=source_task_manifest,
        source_task_manifest_identity=item.get("source_task_manifest_identity"),
        scope_id=str(item.get("scope_id", "")),
        required_smoke_final_root_identity=item.get(
            "required_smoke_final_root_identity"
        ),
        required_smoke_final_root_sha256=item.get(
            "required_smoke_final_root_sha256"
        ),
    )
    if _canonical(item, label="controller manifest") != _canonical(
        expected, label="expected controller manifest"
    ):
        _fail("controller manifest canonical replay differs")
    return expected


def build_controller_job_configuration_v1(
    *, controller_manifest: Mapping[str, object], controller_manifest_identity: object
) -> dict[str, object]:
    manifest = _validate_self_hash(
        controller_manifest,
        field="controller_manifest_sha256",
        label="controller manifest",
    )
    identity = _bind(
        manifest, controller_manifest_identity, label="controller manifest"
    )
    environment = {
        entrypoint.ENABLE_ENV: "1",
        CONTROLLER_MANIFEST_IDENTITY_ENV: _canonical(
            identity, label="controller manifest environment identity"
        ).decode("utf-8"),
        "GOOGLE_CLOUD_PROJECT": entrypoint.FIXED_GCP_PROJECT,
        "CODE_SHA": manifest["source_commit_sha"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["immutable_image_digest"],
    }
    count = int(manifest["cloud_task_count"])
    return {
        "schema_version": "hard230-r6-score-run-cloud-job-configuration/v1",
        "contract_id": CONTRACT_ID,
        "scope_id": manifest["scope_id"],
        "reused_job_name": manifest["reused_job_name"],
        "reused_job_uid": manifest["reused_job_uid"],
        "controller_manifest_identity": identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "container_command": [CONTROLLER_ENTRYPOINT_COMMAND[0]],
        "container_args": list(CONTROLLER_ENTRYPOINT_COMMAND[1:]),
        "container_environment": environment,
        "task_count": count,
        "parallelism": count,
        "max_retries": 0,
        "timeout_seconds": entrypoint.TASK_TIMEOUT_SECONDS,
        "cpu": entrypoint.REUSED_JOB_CPU,
        "memory": entrypoint.REUSED_JOB_MEMORY,
        "new_job_creation_allowed": False,
        "run_job_overrides_allowed": False,
    }


def _validate_smoke_gate(
    *,
    source_manifest: Mapping[str, object],
    source_manifest_identity: Mapping[str, object],
    smoke_root: Mapping[str, object],
    smoke_root_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> None:
    smoke_controller_identity = _identity(
        smoke_root.get("controller_manifest_identity"),
        label="smoke root controller manifest",
    )
    smoke_controller_value, _ = _read_json(
        smoke_controller_identity,
        read_exact=read_exact,
        label="task0 smoke controller manifest",
        maximum_bytes=MAXIMUM_CONTROLLER_MANIFEST_BYTES,
    )
    smoke_controller = validate_controller_manifest_v1(
        smoke_controller_value, source_task_manifest=source_manifest
    )
    launch_value, launch_identity = _read_json(
        smoke_root.get("launch_receipt_identity"),
        read_exact=read_exact,
        label="task0 smoke launch receipt",
        maximum_bytes=MAXIMUM_LAUNCH_RECEIPT_BYTES,
    )
    launch = validate_launch_receipt_v1(
        launch_value,
        controller_manifest=smoke_controller,
        controller_manifest_identity=smoke_controller_identity,
    )
    _bind(launch, launch_identity, label="task0 smoke launch receipt")
    validate_final_root_v1(
        smoke_root,
        controller_manifest=smoke_controller,
        controller_manifest_identity=smoke_controller_identity,
    )
    _bind(smoke_root, smoke_root_identity, label="task0 smoke final root")
    if (
        smoke_controller["scope_id"] != TASK0_SMOKE_SCOPE
        or smoke_controller["source_task_manifest_identity"]
        != _identity(source_manifest_identity, label="source manifest identity")
        or smoke_root.get("launch_receipt_identity") != launch_identity
        or smoke_root.get("launch_receipt_sha256")
        != launch.get("launch_receipt_sha256")
        or smoke_root.get("complete") is not True
    ):
        _fail("required task0 smoke gate differs")


def prepare_controller_manifest_v1(
    *,
    source_task_manifest_identity: Mapping[str, object],
    scope_id: str,
    required_smoke_final_root_identity: Mapping[str, object] | None,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    source, retained_source_identity, _ = entrypoint._open_manifest(
        manifest_identity=source_task_manifest_identity, read_exact=read_exact
    )
    smoke_identity: dict[str, object] | None = None
    smoke_sha: str | None = None
    if scope_id == FULL_54_SCOPE:
        smoke_value, smoke_identity = _read_json(
            required_smoke_final_root_identity,
            read_exact=read_exact,
            label="required task0 smoke final root",
            maximum_bytes=MAXIMUM_FINAL_ROOT_BYTES,
        )
        _validate_smoke_gate(
            source_manifest=source,
            source_manifest_identity=retained_source_identity,
            smoke_root=smoke_value,
            smoke_root_identity=smoke_identity,
            read_exact=read_exact,
        )
        smoke_sha = str(smoke_value.get("final_root_sha256", ""))
    elif required_smoke_final_root_identity is not None:
        _fail("task0 smoke controller cannot name a prior smoke root")
    manifest = build_controller_manifest_v1(
        source_task_manifest=source,
        source_task_manifest_identity=retained_source_identity,
        scope_id=scope_id,
        required_smoke_final_root_identity=smoke_identity,
        required_smoke_final_root_sha256=smoke_sha,
    )
    identity = _publish_json(
        uri=f"{_controller_prefix(source, scope_id)}controller-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_CONTROLLER_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="controller manifest",
    )
    return {
        "schema_version": CONTROLLER_PREPARATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "scope_id": scope_id,
        "controller_manifest_identity": identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "source_task_manifest_identity": retained_source_identity,
        "cloud_run_job_configuration": build_controller_job_configuration_v1(
            controller_manifest=manifest,
            controller_manifest_identity=identity,
        ),
        "outcome_columns_read": [],
        **entrypoint._false_authorities(),
    }


def open_controller_manifest_v1(
    *, controller_manifest_identity: Mapping[str, object], read_exact: ReadExact
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    value, retained_identity = _read_json(
        controller_manifest_identity,
        read_exact=read_exact,
        label="hard230 controller manifest",
        maximum_bytes=MAXIMUM_CONTROLLER_MANIFEST_BYTES,
    )
    source_identity = _identity(
        value.get("source_task_manifest_identity"),
        label="controller source manifest",
    )
    source, retained_source_identity, _ = entrypoint._open_manifest(
        manifest_identity=source_identity, read_exact=read_exact
    )
    manifest = validate_controller_manifest_v1(
        value, source_task_manifest=source
    )
    _bind(manifest, retained_identity, label="controller manifest")
    if retained_source_identity != manifest["source_task_manifest_identity"]:
        _fail("controller source manifest exact identity differs")
    if manifest["scope_id"] == FULL_54_SCOPE:
        smoke_value, smoke_identity = _read_json(
            manifest["required_smoke_final_root_identity"],
            read_exact=read_exact,
            label="required task0 smoke final root",
            maximum_bytes=MAXIMUM_FINAL_ROOT_BYTES,
        )
        _validate_smoke_gate(
            source_manifest=source,
            source_manifest_identity=retained_source_identity,
            smoke_root=smoke_value,
            smoke_root_identity=smoke_identity,
            read_exact=read_exact,
        )
        if smoke_value.get("final_root_sha256") != manifest[
            "required_smoke_final_root_sha256"
        ]:
            _fail("controller required smoke root hash differs")
    return manifest, retained_identity, source


def reopen_required_smoke_task0_result_v1(
    *,
    full_controller_manifest: Mapping[str, object],
    source_task_manifest: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the already accepted task-0 result for a full-run task-0 reuse."""
    manifest = _mapping(
        full_controller_manifest, label="full controller manifest"
    )
    if manifest.get("scope_id") != FULL_54_SCOPE:
        _fail("smoke task0 reuse is available only to the full controller")
    smoke_root, _ = _read_json(
        manifest.get("required_smoke_final_root_identity"),
        read_exact=read_exact,
        label="required task0 smoke final root",
        maximum_bytes=MAXIMUM_FINAL_ROOT_BYTES,
    )
    records = _sequence(smoke_root.get("task_records"), label="smoke task records")
    if len(records) != 1:
        _fail("required smoke root task coverage differs")
    record = _mapping(records[0], label="required smoke task0 record")
    task_value, task_identity = _read_json(
        record.get("task_result_identity"),
        read_exact=read_exact,
        label="required smoke task0 result",
        maximum_bytes=entrypoint.MAXIMUM_TASK_RESULT_BYTES,
    )
    task = entrypoint.validate_task_result_v1(task_value)
    _bind(task, task_identity, label="required smoke task0 result")
    source_rows = _sequence(
        source_task_manifest.get("task_rows"), label="source task rows"
    )
    source_zero = _mapping(source_rows[0], label="source task row[0]")
    if (
        record.get("scientific_task_index") != 0
        or record.get("task_result_identity") != task_identity
        or record.get("task_result_sha256") != task.get("task_result_sha256")
        or task.get("task_index") != 0
        or task.get("slate_id") != source_zero.get("slate_id")
        or task.get("task_manifest_identity")
        != manifest.get("source_task_manifest_identity")
        or task.get("task_manifest_sha256")
        != manifest.get("source_task_manifest_sha256")
    ):
        _fail("required smoke task0 result binding differs")
    return task, task_identity


def build_launch_receipt_v1(
    *,
    controller_manifest: Mapping[str, object],
    controller_manifest_identity: Mapping[str, object],
    job_uid: str,
    execution_name: str,
) -> dict[str, object]:
    manifest = _mapping(controller_manifest, label="launch controller manifest")
    identity = _bind(
        manifest, controller_manifest_identity, label="launch controller manifest"
    )
    uid = _nonempty(job_uid, label="Cloud Run job UID")
    execution = _nonempty(execution_name, label="Cloud Run execution name")
    if (
        uid != manifest.get("reused_job_uid")
        or not execution.startswith(f"{manifest['reused_job_name']}-")
    ):
        _fail("Cloud Run execution is not owned by the reused job")
    return _self_hash({
        "schema_version": LAUNCH_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "scope_id": manifest["scope_id"],
        "controller_manifest_identity": identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "project_id": entrypoint.FIXED_GCP_PROJECT,
        "location": "us-central1",
        "job_name": manifest["reused_job_name"],
        "job_uid": uid,
        "execution_name": execution,
        "cloud_task_count": manifest["cloud_task_count"],
        "run_job_overrides": None,
        "single_async_submission": True,
        "logs_read": False,
        "outcome_columns_read": [],
        **entrypoint._false_authorities(),
    }, "launch_receipt_sha256")


def validate_launch_receipt_v1(
    value: object,
    *,
    controller_manifest: Mapping[str, object],
    controller_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _validate_self_hash(
        value, field="launch_receipt_sha256", label="launch receipt"
    )
    expected = build_launch_receipt_v1(
        controller_manifest=controller_manifest,
        controller_manifest_identity=controller_manifest_identity,
        job_uid=str(item.get("job_uid", "")),
        execution_name=str(item.get("execution_name", "")),
    )
    if _canonical(item, label="launch receipt") != _canonical(
        expected, label="expected launch receipt"
    ):
        _fail("launch receipt canonical replay differs")
    return expected


def _validated_population_descriptor(
    *,
    population: object,
    population_role: str,
    process_receipt_identity: Mapping[str, object],
    task_result: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(population, label=f"{population_role} population")
    rosters = [
        _mapping(row, label=f"{population_role} roster[{index}]")
        for index, row in enumerate(
            _sequence(item.get("population_rosters"), label=f"{population_role} rosters")
        )
    ]
    ids: list[str] = []
    for index, row in enumerate(rosters):
        players = _sequence(
            row.get("roster_player_ids"),
            label=f"{population_role} roster[{index}] players",
        )
        lineup_id = _nonempty(
            row.get("lineup_id"), label=f"{population_role} roster[{index}] lineup ID"
        )
        if (
            set(row) != {
                "lineup_id",
                "roster_player_ids",
                "roster_sha256",
                "first_occurrence_ordinal",
                "fit_world_score_vector_sha256",
            }
            or len(players) != 9
            or any(type(player) is not str or not player for player in players)
            or len(set(players)) != 9
            or row.get("roster_sha256")
            != _hash(players, label=f"{population_role} roster[{index}] players")
            or type(row.get("first_occurrence_ordinal")) is not int
            or int(row["first_occurrence_ordinal"]) < 0
            or type(row.get("fit_world_score_vector_sha256")) is not str
            or len(str(row["fit_world_score_vector_sha256"])) != 64
        ):
            _fail(f"{population_role} roster[{index}] grader shape differs")
        ids.append(lineup_id)
    count = len(rosters)
    roster_sha = _hash(rosters, label=f"{population_role} population rosters")
    expected_count_field = (
        "score_blind_control_population_count"
        if population_role == "score-blind-control"
        else "hard230_challenger_population_count"
    )
    expected_hash_field = (
        "score_blind_control_population_sha256"
        if population_role == "score-blind-control"
        else "hard230_challenger_population_sha256"
    )
    expected_population_id = (
        successor.CONTROL_POPULATION_ID
        if population_role == "score-blind-control"
        else successor.CHALLENGER_POPULATION_ID
    )
    if (
        count < 1
        or len(ids) != len(set(ids))
        or item.get("population_id") != expected_population_id
        or item.get("population_lineup_count") != count
        or item.get("population_rosters_sha256") != roster_sha
        or task_result.get(expected_count_field) != count
        or task_result.get(expected_hash_field) != roster_sha
    ):
        _fail(f"{population_role} population count/hash binding differs")
    field = (
        "score_blind_control_population"
        if population_role == "score-blind-control"
        else "hard230_challenger_population"
    )
    return {
        "population_role": population_role,
        "population_id": expected_population_id,
        "process_receipt_identity": _identity(
            process_receipt_identity, label=f"{population_role} process receipt"
        ),
        "population_rosters_json_pointer": (
            f"/scientific_receipt/{field}/population_rosters"
        ),
        "population_lineup_count": count,
        "population_rosters_sha256": roster_sha,
    }


def _collect_task_record(
    *,
    expected: Mapping[str, object],
    controller_manifest: Mapping[str, object],
    source_manifest: Mapping[str, object],
    open_known: OpenKnown,
    read_exact: ReadExact,
) -> dict[str, object]:
    scientific_index = int(expected["scientific_task_index"])
    uri = str(expected["task_result_uri"])
    opened = open_known(uri, entrypoint.MAXIMUM_TASK_RESULT_BYTES)
    if not isinstance(opened, tuple) or len(opened) != 2 or type(opened[0]) is not bytes:
        _fail(f"task[{scientific_index}] known result opener differs")
    raw, supplied_identity = opened
    identity = _identity(
        supplied_identity, label=f"task[{scientific_index}] result identity"
    )
    if (
        identity["uri"] != uri
        or len(raw) > entrypoint.MAXIMUM_TASK_RESULT_BYTES
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"task[{scientific_index}] result exact-open differs")
    task_result = entrypoint.validate_task_result_v1(
        _strict_json(raw, label=f"task[{scientific_index}] result")
    )
    _bind(task_result, identity, label=f"task[{scientific_index}] result")
    source_row = _mapping(
        _sequence(source_manifest.get("task_rows"), label="source task rows")[
            scientific_index
        ],
        label=f"source task row[{scientific_index}]",
    )
    if (
        task_result.get("task_index") != scientific_index
        or task_result.get("slate_id") != expected.get("slate_id")
        or task_result.get("slate_id") != source_row.get("slate_id")
        or task_result.get("task_manifest_identity")
        != controller_manifest.get("source_task_manifest_identity")
        or task_result.get("task_manifest_sha256")
        != controller_manifest.get("source_task_manifest_sha256")
        or task_result.get("p0_population_receipt_identity")
        != source_row.get("p0_population_receipt_identity")
    ):
        _fail(f"task[{scientific_index}] result manifest binding differs")
    process_value, process_identity = _read_json(
        task_result["process_receipt_identity"],
        read_exact=read_exact,
        label=f"task[{scientific_index}] process receipt",
        maximum_bytes=process.MAX_ROOT_BYTES,
    )
    try:
        retained_process = process.validate_process_receipt_v1(process_value)
    except process.Hard230PopulationProcessV1Error as exc:
        raise Hard230R6RunControllerV1Error(str(exc)) from exc
    _bind(retained_process, process_identity, label=f"task[{scientific_index}] process receipt")
    if (
        retained_process.get("task_index") != scientific_index
        or retained_process.get("slate_id") != expected.get("slate_id")
        or retained_process.get("process_receipt_sha256")
        != task_result.get("process_receipt_sha256")
        or process_identity != task_result.get("process_receipt_identity")
    ):
        _fail(f"task[{scientific_index}] process receipt binding differs")
    scientific = _mapping(
        retained_process.get("scientific_receipt"),
        label=f"task[{scientific_index}] scientific receipt",
    )
    populations = [
        _validated_population_descriptor(
            population=scientific.get("score_blind_control_population"),
            population_role="score-blind-control",
            process_receipt_identity=process_identity,
            task_result=task_result,
        ),
        _validated_population_descriptor(
            population=scientific.get("hard230_challenger_population"),
            population_role="hard230-challenger",
            process_receipt_identity=process_identity,
            task_result=task_result,
        ),
    ]
    return {
        "cloud_task_index": expected["cloud_task_index"],
        "scientific_task_index": scientific_index,
        "slate_id": expected["slate_id"],
        "task_result_identity": identity,
        "task_result_sha256": task_result["task_result_sha256"],
        "process_receipt_identity": process_identity,
        "process_receipt_sha256": retained_process["process_receipt_sha256"],
        "p0_target_count": task_result["p0_target_count"],
        "populations": populations,
        "populations_sha256": _hash(populations, label="task population descriptors"),
    }


def build_final_root_v1(
    *,
    controller_manifest: Mapping[str, object],
    controller_manifest_identity: Mapping[str, object],
    launch_receipt: Mapping[str, object],
    launch_receipt_identity: Mapping[str, object],
    task_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    manifest = _mapping(controller_manifest, label="final controller manifest")
    manifest_identity = _bind(
        manifest, controller_manifest_identity, label="final controller manifest"
    )
    launch = validate_launch_receipt_v1(
        launch_receipt,
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    launch_identity = _bind(
        launch, launch_receipt_identity, label="final launch receipt"
    )
    records = [
        _mapping(row, label=f"final task record[{index}]")
        for index, row in enumerate(task_records)
    ]
    expected = _sequence(
        manifest.get("expected_task_results"), label="controller expected results"
    )
    if (
        len(records) != len(expected)
        or [row.get("cloud_task_index") for row in records]
        != list(range(len(records)))
        or [row.get("scientific_task_index") for row in records]
        != [row.get("scientific_task_index") for row in expected]
        or [row.get("slate_id") for row in records]
        != [row.get("slate_id") for row in expected]
    ):
        _fail("final task record order/coverage differs")
    population_count = sum(
        len(_sequence(row.get("populations"), label="final populations"))
        for row in records
    )
    if population_count != 2 * len(records):
        _fail("final root must expose control and challenger for every slate")
    body = {
        "schema_version": FINAL_ROOT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "scope_id": manifest["scope_id"],
        "complete": True,
        "controller_manifest_identity": manifest_identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "source_task_manifest_identity": manifest["source_task_manifest_identity"],
        "source_task_manifest_sha256": manifest["source_task_manifest_sha256"],
        "required_smoke_final_root_identity": manifest[
            "required_smoke_final_root_identity"
        ],
        "required_smoke_final_root_sha256": manifest[
            "required_smoke_final_root_sha256"
        ],
        "launch_receipt_identity": launch_identity,
        "launch_receipt_sha256": launch["launch_receipt_sha256"],
        "execution_name": launch["execution_name"],
        "scientific_task_count": len(records),
        "new_scientific_execution_count": (
            len(records)
            if manifest["scope_id"] == TASK0_SMOKE_SCOPE
            else len(records) - 1
        ),
        "reused_required_smoke_result_count": (
            0 if manifest["scope_id"] == TASK0_SMOKE_SCOPE else 1
        ),
        "population_descriptor_count": population_count,
        "task_records": records,
        "task_records_sha256": _hash(records, label="final task records"),
        "grader_population_contract": _grader_population_contract(),
        "all_known_result_uris_generation_pinned": True,
        "all_task_and_process_roots_exact_reopened": True,
        "bucket_listing_used": False,
        "logs_read": False,
        "outcome_columns_read": [],
        **entrypoint._false_authorities(),
    }
    retained = _self_hash(body, "final_root_sha256")
    if len(_canonical(retained, label="hard230 final root")) > MAXIMUM_FINAL_ROOT_BYTES:
        _fail("hard230 final root exceeds its byte ceiling")
    return retained


def validate_final_root_v1(
    value: object,
    *,
    controller_manifest: Mapping[str, object],
    controller_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _validate_self_hash(
        value, field="final_root_sha256", label="hard230 final root"
    )
    launch_identity = _identity(
        item.get("launch_receipt_identity"), label="final root launch receipt"
    )
    # Canonical replay of launch content is performed during collection.  The
    # root itself retains the exact identity and immutable receipt hash.
    records = [
        _mapping(row, label=f"final task record[{index}]")
        for index, row in enumerate(
            _sequence(item.get("task_records"), label="final task records")
        )
    ]
    manifest = _mapping(controller_manifest, label="validated root controller")
    identity = _bind(
        manifest, controller_manifest_identity, label="validated root controller"
    )
    expected_results = _sequence(
        manifest.get("expected_task_results"), label="validated root expected results"
    )
    if (
        item.get("schema_version") != FINAL_ROOT_SCHEMA
        or item.get("contract_id") != CONTRACT_ID
        or item.get("scope_id") != manifest.get("scope_id")
        or item.get("complete") is not True
        or item.get("controller_manifest_identity") != identity
        or item.get("controller_manifest_sha256")
        != manifest.get("controller_manifest_sha256")
        or item.get("source_task_manifest_identity")
        != manifest.get("source_task_manifest_identity")
        or item.get("source_task_manifest_sha256")
        != manifest.get("source_task_manifest_sha256")
        or item.get("required_smoke_final_root_identity")
        != manifest.get("required_smoke_final_root_identity")
        or item.get("required_smoke_final_root_sha256")
        != manifest.get("required_smoke_final_root_sha256")
        or type(item.get("launch_receipt_sha256")) is not str
        or len(str(item.get("launch_receipt_sha256"))) != 64
        or item.get("scientific_task_count") != len(expected_results)
        or item.get("new_scientific_execution_count")
        != (
            len(expected_results)
            if manifest.get("scope_id") == TASK0_SMOKE_SCOPE
            else len(expected_results) - 1
        )
        or item.get("reused_required_smoke_result_count")
        != (0 if manifest.get("scope_id") == TASK0_SMOKE_SCOPE else 1)
        or len(records) != len(expected_results)
        or item.get("task_records_sha256")
        != _hash(records, label="validated final task records")
        or item.get("population_descriptor_count") != 2 * len(records)
        or item.get("grader_population_contract") != _grader_population_contract()
        or item.get("all_known_result_uris_generation_pinned") is not True
        or item.get("all_task_and_process_roots_exact_reopened") is not True
        or item.get("bucket_listing_used") is not False
        or item.get("logs_read") is not False
        or item.get("outcome_columns_read") != []
        or any(item.get(field) is not False for field in entrypoint._FALSE_AUTHORITY_FIELDS)
    ):
        _fail("hard230 final root fixed law or binding differs")
    for ordinal, (record, expected_result) in enumerate(zip(records, expected_results)):
        populations = _sequence(
            record.get("populations"), label=f"final task[{ordinal}] populations"
        )
        if (
            set(record) != {
                "cloud_task_index",
                "scientific_task_index",
                "slate_id",
                "task_result_identity",
                "task_result_sha256",
                "process_receipt_identity",
                "process_receipt_sha256",
                "p0_target_count",
                "populations",
                "populations_sha256",
            }
            or record.get("cloud_task_index") != ordinal
            or record.get("scientific_task_index")
            != expected_result.get("scientific_task_index")
            or record.get("slate_id") != expected_result.get("slate_id")
            or len(populations) != 2
            or [
                _mapping(row, label="final population").get("population_role")
                for row in populations
            ] != ["score-blind-control", "hard230-challenger"]
            or record.get("populations_sha256")
            != _hash(populations, label="validated population descriptors")
        ):
            _fail(f"hard230 final task record[{ordinal}] differs")
        task_identity = _identity(
            record.get("task_result_identity"), label="final task result"
        )
        process_identity = _identity(
            record.get("process_receipt_identity"), label="final process receipt"
        )
        if (
            type(record.get("task_result_sha256")) is not str
            or len(str(record["task_result_sha256"])) != 64
            or type(record.get("process_receipt_sha256")) is not str
            or len(str(record["process_receipt_sha256"])) != 64
            or type(record.get("p0_target_count")) is not int
            or int(record["p0_target_count"]) < 1
            or task_identity["uri"] != expected_result.get("task_result_uri")
        ):
            _fail(f"hard230 final task record[{ordinal}] identity differs")
        expected_roles = (
            (
                "score-blind-control",
                successor.CONTROL_POPULATION_ID,
                "/scientific_receipt/score_blind_control_population/population_rosters",
            ),
            (
                "hard230-challenger",
                successor.CHALLENGER_POPULATION_ID,
                "/scientific_receipt/hard230_challenger_population/population_rosters",
            ),
        )
        for population, expected_population in zip(populations, expected_roles):
            descriptor = _mapping(population, label="final population descriptor")
            role, population_id, pointer = expected_population
            if (
                set(descriptor) != {
                    "population_role",
                    "population_id",
                    "process_receipt_identity",
                    "population_rosters_json_pointer",
                    "population_lineup_count",
                    "population_rosters_sha256",
                }
                or descriptor.get("population_role") != role
                or descriptor.get("population_id") != population_id
                or descriptor.get("process_receipt_identity") != process_identity
                or descriptor.get("population_rosters_json_pointer") != pointer
                or type(descriptor.get("population_lineup_count")) is not int
                or int(descriptor["population_lineup_count"]) < 1
                or type(descriptor.get("population_rosters_sha256")) is not str
                or len(str(descriptor["population_rosters_sha256"])) != 64
            ):
                _fail(f"hard230 final population descriptor[{ordinal}] differs")
    return {**item, "final_root_sha256": item["final_root_sha256"]}


def novel_roster_grader_inputs_from_final_root_v1(
    *,
    final_root: Mapping[str, object],
    controller_manifest: Mapping[str, object],
    controller_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Project the exact public input seam of the generic hard230 grader."""
    root = validate_final_root_v1(
        final_root,
        controller_manifest=controller_manifest,
        controller_manifest_identity=controller_manifest_identity,
    )
    if root["scope_id"] != FULL_54_SCOPE or root["scientific_task_count"] != 54:
        _fail("generic hard230 grading requires the complete full-54 root")
    task_result_identities = [
        _identity(
            _mapping(record, label=f"grader task record[{ordinal}]").get(
                "task_result_identity"
            ),
            label=f"grader task result[{ordinal}]",
        )
        for ordinal, record in enumerate(
            _sequence(root["task_records"], label="grader task records")
        )
    ]
    return {
        "adapter_id": NOVEL_ROSTER_GRADER_ADAPTER_ID,
        "task_manifest_identity": root["source_task_manifest_identity"],
        "task_result_identities": task_result_identities,
    }


def collect_and_publish_final_root_v1(
    *,
    controller_manifest_identity: Mapping[str, object],
    launch_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
    open_known: OpenKnown,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Deep-open every known result and publish the compact final root last."""
    manifest, manifest_identity, source = open_controller_manifest_v1(
        controller_manifest_identity=controller_manifest_identity,
        read_exact=read_exact,
    )
    launch_value, launch_identity = _read_json(
        launch_receipt_identity,
        read_exact=read_exact,
        label="hard230 launch receipt",
        maximum_bytes=MAXIMUM_LAUNCH_RECEIPT_BYTES,
    )
    launch = validate_launch_receipt_v1(
        launch_value,
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    _bind(launch, launch_identity, label="hard230 launch receipt")
    records = [
        _collect_task_record(
            expected=_mapping(row, label=f"expected result[{index}]"),
            controller_manifest=manifest,
            source_manifest=source,
            open_known=open_known,
            read_exact=read_exact,
        )
        for index, row in enumerate(
            _sequence(manifest["expected_task_results"], label="expected results")
        )
    ]
    root = build_final_root_v1(
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
        launch_receipt=launch,
        launch_receipt_identity=launch_identity,
        task_records=records,
    )
    validate_final_root_v1(
        root,
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    root_identity = _publish_json(
        uri=str(manifest["final_root_uri"]),
        value=root,
        maximum_bytes=MAXIMUM_FINAL_ROOT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="hard230 final root",
    )
    return {
        "schema_version": "hard230-r6-score-run-finalization/v1",
        "scope_id": manifest["scope_id"],
        "complete": True,
        "controller_manifest_identity": manifest_identity,
        "launch_receipt_identity": launch_identity,
        "final_root_identity": root_identity,
        "final_root_sha256": root["final_root_sha256"],
        "scientific_task_count": root["scientific_task_count"],
        "population_descriptor_count": root["population_descriptor_count"],
        "outcome_columns_read": [],
        **entrypoint._false_authorities(),
    }


__all__ = [
    "CONTROLLER_ENTRYPOINT_COMMAND",
    "CONTROLLER_MANIFEST_IDENTITY_ENV",
    "FULL_54_SCOPE",
    "Hard230R6RunControllerV1Error",
    "NOVEL_ROSTER_GRADER_ADAPTER_ID",
    "REUSED_JOB_NAME",
    "REUSED_JOB_UID",
    "TASK0_SMOKE_SCOPE",
    "build_controller_job_configuration_v1",
    "build_controller_manifest_v1",
    "build_final_root_v1",
    "build_launch_receipt_v1",
    "collect_and_publish_final_root_v1",
    "open_controller_manifest_v1",
    "novel_roster_grader_inputs_from_final_root_v1",
    "prepare_controller_manifest_v1",
    "reopen_required_smoke_task0_result_v1",
    "validate_controller_manifest_v1",
    "validate_final_root_v1",
    "validate_launch_receipt_v1",
]
