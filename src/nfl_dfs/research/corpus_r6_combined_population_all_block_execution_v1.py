"""Pure 54-slate execution and terminal law for the combined R6 union.

The scientific adapter lives in
``corpus_r6_combined_population_all_block_v1``.  This module adds only the
small immutable execution surface needed to run one score-free task per
slate, collect all 54 results, and expose them to the public direct-roster
grader.  It performs no storage, warehouse, outcome, or deployment I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_combined_population_all_block_v1 as combined,
)
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader
from nfl_dfs.research import corpus_r6_population_crossed_cloud_v1 as crossed


MANIFEST_SCHEMA: Final = "corpus-r6-combined-population-all-block-manifest/v1"
TASK_BINDING_SCHEMA: Final = (
    "corpus-r6-combined-population-all-block-task-binding/v1"
)
TASK_RESULT_SCHEMA: Final = (
    "corpus-r6-combined-population-all-block-task-result/v1"
)
TERMINAL_SCHEMA: Final = "corpus-r6-combined-population-all-block-terminal/v1"
RUNTIME_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-combined-population-all-block-runtime-authority/v1"
)
TASK_COUNT: Final = grader.SOURCE_SLATE_COUNT
BOOK_COUNT_PER_SLATE: Final = 8
FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_REUSED_JOB_NAME: Final = "atlas-minimal-c-s2023-w3-v1"
FIXED_REUSED_JOB_UID: Final = "064df315-0fb5-4b86-a5f9-6c73ac1c5eb3"
FIXED_REGION: Final = "us-central1"
FIXED_CPU: Final = "8"
FIXED_MEMORY: Final = "32Gi"
FIXED_TIMEOUT_SECONDS: Final = 21600
DISPATCHER_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    "/app/scripts/run_corpus_r6_combined_population_all_block_v1.py",
    "task",
)
ENABLE_ENV: Final = "R6_COMBINED_POPULATION_ALL_BLOCK_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_HISTORICAL_FINALIST_CONFIRMATION_V1"
MANIFEST_IDENTITY_ENV: Final = "R6_COMBINED_POPULATION_ALL_BLOCK_MANIFEST_IDENTITY"
JOB_AUTHORITY_SHA_ENV: Final = "R6_COMBINED_POPULATION_ALL_BLOCK_JOB_AUTHORITY_SHA256"

FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-freezes/"
        "20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json"
    ),
    "generation": "1787756181440564",
    "sha256": "57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467",
    "bytes": 89879,
}
FIXED_PROFILE_TERMINAL_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-current-bank-crossed-screens/"
        "20260829-score-sprint-c9f12ed7-f7f8f9-crossed-v1/"
        "terminal-experiment-root.json"
    ),
    "generation": "1787985545845384",
    "sha256": "224f173a4e87232f2299d25e1ee493d9271a23bffc1e5cb5c6bb17695730a814",
    "bytes": 25972,
}
FIXED_HARD230_TERMINAL_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-hard230/20260829-score-sprint-c9f12ed7-v1/"
        "selector-bridge/full-54/terminal.json"
    ),
    "generation": "1787983108965129",
    "sha256": "08fa65cc26efcae0f430a28b2eb729040ce8acfd6271984c29536cb5352cf9e4",
    "bytes": 55023048,
}

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_RE: Final = re.compile(r"sha256:[0-9a-f]{64}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")


class CorpusR6CombinedPopulationAllBlockExecutionV1Error(ValueError):
    """The fixed combined-population execution surface differs."""


def _fail(message: str) -> None:
    raise CorpusR6CombinedPopulationAllBlockExecutionV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _canonical(value: object) -> bytes:
    try:
        return grader.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CombinedPopulationAllBlockExecutionV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: _hash(body)}


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6CombinedPopulationAllBlockExecutionV1Error(str(exc)) from exc


def _output_prefix(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("gs://nfl-predictions-503414-corpus-retrieval/research/")
        or not value.endswith("/")
        or "//" in value[5:]
        or "/corpus-r6-combined-population-all-block/" not in value
    ):
        _fail("combined output prefix differs")
    return value


def task_result_uri_v1(*, output_prefix: str, source_ordinal: int) -> str:
    prefix = _output_prefix(output_prefix)
    if type(source_ordinal) is not int or not 0 <= source_ordinal < TASK_COUNT:
        _fail("combined source ordinal differs")
    return f"{prefix}slates/{source_ordinal:02d}/selection-result.json"


def terminal_uri_v1(*, output_prefix: str) -> str:
    return f"{_output_prefix(output_prefix)}full-54/terminal.json"


def grade_uri_v1(*, output_prefix: str) -> str:
    return f"{_output_prefix(output_prefix)}full-54/realized-grade.json"


def _provider_job_projection_from_configuration_v1(
    configuration: Mapping[str, object],
) -> dict[str, object]:
    env = dict(_mapping(configuration["container_environment"], label="job environment"))
    env.pop(JOB_AUTHORITY_SHA_ENV, None)
    return {
        "job_name": configuration["reused_job_name"],
        "job_uid": configuration["reused_job_uid"],
        "project_id": configuration["project_id"],
        "region": configuration["region"],
        "image_digest": configuration["image_digest"],
        "immutable_image_uri": configuration["immutable_image_uri"],
        "source_commit": env["CODE_SHA"],
        "container_command": configuration["container_command"],
        "container_args": configuration["container_args"],
        "container_environment": env,
        "task_count": configuration["task_count"],
        "parallelism": configuration["parallelism"],
        "max_retries": configuration["max_retries"],
        "timeout_seconds": configuration["timeout_seconds"],
        "cpu": configuration["cpu"], "memory": configuration["memory"],
        "working_directory": configuration["working_directory"],
        "volumes": configuration["volumes"],
        "volume_mounts": configuration["volume_mounts"],
        "provider_observed": True,
    }


def build_job_configuration_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    """Derive the one exact reused-job configuration and command."""
    retained = validate_task_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="combined job manifest")
    body = {
        "schema_version": "corpus-r6-combined-population-all-block-job-configuration/v1",
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "project_id": FIXED_GCP_PROJECT,
        "task_manifest_identity": identity,
        "task_manifest_sha256": retained["task_manifest_sha256"],
        "terminal_build_receipt_identity": retained[
            "terminal_build_receipt_identity"
        ],
        "terminal_build_receipt_sha256": retained[
            "terminal_build_receipt_sha256"
        ],
        "image_digest": retained["image_digest"],
        "immutable_image_uri": retained["immutable_image_uri"],
        "container_command": [DISPATCHER_COMMAND[0]],
        "container_args": list(DISPATCHER_COMMAND[1:]),
        "container_environment": {
            ENABLE_ENV: ENABLE_VALUE,
            MANIFEST_IDENTITY_ENV: _canonical(identity).decode("utf-8"),
            "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
            "CODE_SHA": retained["code_commit"],
            "R6_RUNTIME_IMAGE_DIGEST": retained["image_digest"],
        },
        "task_count": TASK_COUNT,
        "parallelism": TASK_COUNT,
        "max_retries": 0,
        "timeout_seconds": FIXED_TIMEOUT_SECONDS,
        "cpu": FIXED_CPU,
        "memory": FIXED_MEMORY,
        "region": FIXED_REGION,
        "working_directory": "",
        "volumes": [],
        "volume_mounts": [],
        "new_job_creation_allowed": False,
    }
    authority_projection = _provider_job_projection_from_configuration_v1(body)
    body["container_environment"][JOB_AUTHORITY_SHA_ENV] = _hash(authority_projection)
    return _with_hash(body, field="job_configuration_sha256")


def build_runtime_authority_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
    environment: Mapping[str, str],
    observed_command: Sequence[str],
    observed_project_id: str,
) -> dict[str, object]:
    """Bind reserved Cloud Run metadata and observed process command."""
    retained = validate_task_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="combined runtime manifest")
    config = build_job_configuration_v1(
        manifest=retained, manifest_identity=identity
    )
    deployed = expected_provider_job_observation_v1(
        manifest=retained, manifest_identity=identity
    )
    env = dict(environment)
    command = [str(value) for value in observed_command]
    index_text = env.get("CLOUD_RUN_TASK_INDEX", "")
    count_text = env.get("CLOUD_RUN_TASK_COUNT", "")
    attempt_text = env.get("CLOUD_RUN_TASK_ATTEMPT", "")
    execution_id = env.get("CLOUD_RUN_EXECUTION", "")
    if (
        command != list(DISPATCHER_COMMAND)
        or env.get("CLOUD_RUN_JOB") != FIXED_REUSED_JOB_NAME
        or not execution_id
        or len(execution_id) > 512
        or not index_text.isdecimal()
        or not count_text.isdecimal()
        or attempt_text != "0"
        or int(count_text) != TASK_COUNT
        or not 0 <= int(index_text) < TASK_COUNT
        or observed_project_id != FIXED_GCP_PROJECT
        or env.get(ENABLE_ENV) != ENABLE_VALUE
        or env.get(MANIFEST_IDENTITY_ENV)
        != _canonical(identity).decode("utf-8")
        or env.get(JOB_AUTHORITY_SHA_ENV) != _hash(deployed)
    ):
        _fail("combined reserved Cloud Run runtime differs from job authority")
    return _with_hash({
        "schema_version": RUNTIME_AUTHORITY_SCHEMA,
        "task_index": int(index_text),
        "task_count": int(count_text),
        "task_attempt": 0,
        "project_id": FIXED_GCP_PROJECT,
        "job_name": FIXED_REUSED_JOB_NAME,
        "job_uid": FIXED_REUSED_JOB_UID,
        "execution_id": execution_id,
        "observed_command": command,
        "job_configuration": config,
        "job_configuration_sha256": config["job_configuration_sha256"],
        "deployed_job_observation": deployed,
        "deployed_job_observation_sha256": _hash(deployed),
        "terminal_build_receipt_identity": retained[
            "terminal_build_receipt_identity"
        ],
        "terminal_build_receipt_sha256": retained[
            "terminal_build_receipt_sha256"
        ],
        "authority_source": "reserved-cloud-run-metadata-and-observed-command",
    }, field="runtime_authority_sha256")


def validate_runtime_authority_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    authority = _mapping(value, label="combined runtime authority")
    if set(authority) != {
        "schema_version", "task_index", "task_count", "task_attempt",
        "project_id", "job_name", "job_uid", "execution_id", "observed_command",
        "job_configuration", "job_configuration_sha256",
        "deployed_job_observation", "deployed_job_observation_sha256",
        "terminal_build_receipt_identity", "terminal_build_receipt_sha256",
        "authority_source",
        "runtime_authority_sha256",
    } or authority.get(
        "runtime_authority_sha256"
    ) != _hash({
        key: item for key, item in authority.items()
        if key != "runtime_authority_sha256"
    }):
        _fail("combined runtime authority fields/hash differ")
    environment = {
        "CLOUD_RUN_TASK_INDEX": str(authority.get("task_index", "")),
        "CLOUD_RUN_TASK_COUNT": str(authority.get("task_count", "")),
        "CLOUD_RUN_TASK_ATTEMPT": str(authority.get("task_attempt", "")),
        "CLOUD_RUN_JOB": str(authority.get("job_name", "")),
        "CLOUD_RUN_EXECUTION": str(authority.get("execution_id", "")),
        "GOOGLE_CLOUD_PROJECT": str(authority.get("project_id", "")),
        ENABLE_ENV: ENABLE_VALUE,
        MANIFEST_IDENTITY_ENV: _canonical(
            _identity(manifest_identity, label="runtime replay manifest")
        ).decode("utf-8"),
        JOB_AUTHORITY_SHA_ENV: str(
            authority.get("deployed_job_observation_sha256", "")
        ),
    }
    expected = build_runtime_authority_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        environment=environment,
        observed_command=_sequence(
            authority.get("observed_command"), label="runtime observed command"
        ),
        observed_project_id=str(authority.get("project_id", "")),
    )
    if _canonical(authority) != _canonical(expected):
        _fail("combined runtime authority canonical replay differs")
    return expected


def build_task_manifest_v1(
    *,
    incumbent_panel_freeze: Mapping[str, object],
    incumbent_panel_freeze_identity: object,
    profile_terminal_root: Mapping[str, object],
    profile_terminal_identity: object,
    profile_task_manifest: Mapping[str, object],
    profile_task_result_descriptors: Sequence[Mapping[str, object]],
    profile_task_results: Sequence[Mapping[str, object]],
    hard230_terminal: Mapping[str, object],
    hard230_terminal_identity: object,
    terminal_build_receipt: Mapping[str, object],
    terminal_build_receipt_identity: object,
    output_prefix: str,
) -> dict[str, object]:
    """Bind the three completed source panels into one 54-task manifest."""
    incumbent_identity = _identity(
        incumbent_panel_freeze_identity, label="incumbent panel freeze"
    )
    profile_identity = _identity(
        profile_terminal_identity, label="profile terminal root"
    )
    hard_identity = _identity(
        hard230_terminal_identity, label="hard230 selector terminal"
    )
    build_identity = _identity(
        terminal_build_receipt_identity, label="combined terminal build receipt"
    )
    build_receipt = _mapping(
        terminal_build_receipt, label="combined terminal build receipt"
    )
    if (
        incumbent_identity != FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY
        or profile_identity != FIXED_PROFILE_TERMINAL_IDENTITY
        or hard_identity != FIXED_HARD230_TERMINAL_IDENTITY
    ):
        _fail("combined source terminal identity differs from the frozen finalists")
    prefix = _output_prefix(output_prefix)
    if (
        set(build_receipt) != {
            "build_id", "finish_time", "image_digest", "image_tag",
            "project_id", "region", "source_commit", "start_time", "status",
        }
        or _COMMIT_RE.fullmatch(str(build_receipt.get("source_commit"))) is None
        or _IMAGE_RE.fullmatch(str(build_receipt.get("image_digest"))) is None
        or build_receipt.get("project_id") != FIXED_GCP_PROJECT
        or build_receipt.get("region") != "us-central1"
        or build_receipt.get("status") != "SUCCESS"
    ):
        _fail("combined immutable build receipt/job authority differs")

    incumbent = _mapping(incumbent_panel_freeze, label="incumbent panel freeze")
    profile_root = _mapping(profile_terminal_root, label="profile terminal root")
    profile_manifest = crossed.validate_task_manifest_v1(profile_task_manifest)
    hard_terminal = _mapping(hard230_terminal, label="hard230 terminal")
    incumbent_rows = [
        _mapping(row, label="incumbent slate descriptor")
        for row in _sequence(incumbent.get("slate_freezes"), label="incumbent slates")
    ]
    profile_rows = [
        _mapping(row, label="profile result descriptor")
        for row in profile_task_result_descriptors
    ]
    profile_results = [
        crossed.validate_slate_result_v1(row) for row in profile_task_results
    ]
    profile_bindings = [
        _mapping(row, label="profile task binding")
        for row in _sequence(
            profile_manifest.get("task_bindings"), label="profile task bindings"
        )
    ]
    hard_rows = [
        _mapping(row, label="hard230 slate result")
        for row in _sequence(hard_terminal.get("slate_results"), label="hard230 slates")
    ]
    later_identity = _identity(
        incumbent.get("later_source_freeze_identity"), label="common later source"
    )
    if (
        incumbent.get("source_slate_count") != TASK_COUNT
        or profile_root.get("source_slate_count") != TASK_COUNT
        or hard_terminal.get("source_slate_count") != TASK_COUNT
        or not (
            len(incumbent_rows)
            == len(profile_rows)
            == len(profile_results)
            == len(profile_bindings)
            == len(hard_rows)
            == TASK_COUNT
        )
        or profile_root.get("adapter_id") != grader.POPULATION_CROSSED_ADAPTER
        or profile_manifest.get("profile_order") != list(combined.PROFILE_SOURCE_IDS)
    ):
        _fail("combined source terminal census differs")
    if (
        profile_manifest.get("task_manifest_sha256")
        != profile_root.get("task_manifest_sha256")
        or hard_terminal.get("later_source_identity") != later_identity
    ):
        _fail("combined source terminal later/manifest binding differs")

    bindings: list[dict[str, object]] = []
    for ordinal, (
        incumbent_row, profile_row, profile_result, profile_binding, hard_row
    ) in enumerate(
        zip(
            incumbent_rows, profile_rows, profile_results, profile_bindings,
            hard_rows, strict=True,
        )
    ):
        slate_id = incumbent_row.get("slate_id")
        request = crossed.validate_task_request_v1(profile_binding.get("request"))
        if (
            incumbent_row.get("source_ordinal") != ordinal
            or profile_row.get("source_ordinal") != ordinal
            or hard_row.get("source_ordinal") != ordinal
            or profile_binding.get("source_ordinal") != ordinal
            or profile_result.get("source_ordinal") != ordinal
            or slate_id != profile_row.get("slate_id")
            or slate_id != profile_result.get("slate_id")
            or slate_id != profile_binding.get("slate_id")
            or slate_id != hard_row.get("slate_id")
            or hard_row.get("later_source_identity") != later_identity
            or request.get("profile_order") != list(combined.PROFILE_SOURCE_IDS)
            or request.get("request_sha256") != profile_binding.get("request_sha256")
            or request.get("request_sha256") != profile_result.get("task_request_sha256")
            or profile_result.get("slate_result_sha256")
            != profile_row.get("task_result_sha256")
        ):
            _fail(f"combined source slate[{ordinal}] alignment differs")
        binding = _with_hash({
            "schema_version": TASK_BINDING_SCHEMA,
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "incumbent_slate_freeze_identity": incumbent_row[
                "slate_freeze_identity"
            ],
            "incumbent_slate_freeze_sha256": incumbent_row[
                "slate_freeze_sha256"
            ],
            "incumbent_task_result_sha256": incumbent_row["task_result_sha256"],
            "profile_task_result_identity": profile_row["task_result_identity"],
            "profile_task_result_sha256": profile_result["slate_result_sha256"],
            "profile_source_request": request,
            "profile_source_request_sha256": request["request_sha256"],
            "hard230_slate_result_sha256": hard_row["slate_result_sha256"],
            "hard230_source_member_identity": hard_row["source_member_identity"],
            "result_uri": task_result_uri_v1(
                output_prefix=prefix, source_ordinal=ordinal
            ),
        }, field="task_binding_sha256")
        bindings.append(binding)

    body = {
        "schema_version": MANIFEST_SCHEMA,
        "adapter_id": combined.ADAPTER_ID,
        "incumbent_panel_freeze_identity": incumbent_identity,
        "incumbent_panel_freeze_sha256": incumbent["panel_freeze_sha256"],
        "profile_terminal_identity": profile_identity,
        "profile_terminal_sha256": profile_root[
            "terminal_experiment_root_sha256"
        ],
        "profile_task_manifest_identity": profile_root["task_manifest_identity"],
        "profile_task_manifest_sha256": profile_root["task_manifest_sha256"],
        "hard230_terminal_identity": hard_identity,
        "hard230_terminal_sha256": hard_terminal["terminal_sha256"],
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": _hash(build_receipt),
        "terminal_build_id": build_receipt["build_id"],
        "later_source_identity": later_identity,
        "output_prefix": prefix,
        "terminal_uri": terminal_uri_v1(output_prefix=prefix),
        "code_commit": build_receipt["source_commit"],
        "image_digest": build_receipt["image_digest"],
        "immutable_image_uri": f"{build_receipt['image_tag']}@{build_receipt['image_digest']}",
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "task_count": TASK_COUNT,
        "entry_budget": combined.ENTRY_BUDGET,
        "strategy_count_per_slate": BOOK_COUNT_PER_SLATE,
        "source_population_ids": list(combined.SOURCE_ORDER),
        "task_bindings": bindings,
        "task_binding_sha256s": [row["task_binding_sha256"] for row in bindings],
        "one_reused_job_for_all_slates": True,
        "common_world_matrix_reconstructed_once_per_slate": True,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_finalist_confirmation": True,
        "untouched_confirmatory_inference": False,
    }
    return _with_hash(body, field="task_manifest_sha256")


def validate_task_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="combined task manifest")
    expected_fields = {
        "schema_version", "adapter_id", "incumbent_panel_freeze_identity",
        "incumbent_panel_freeze_sha256", "profile_terminal_identity",
        "profile_terminal_sha256", "profile_task_manifest_identity",
        "profile_task_manifest_sha256", "hard230_terminal_identity",
        "hard230_terminal_sha256", "terminal_build_receipt_identity",
        "terminal_build_receipt_sha256", "terminal_build_id",
        "later_source_identity", "output_prefix",
        "terminal_uri", "code_commit", "image_digest", "immutable_image_uri", "reused_job_name",
        "reused_job_uid",
        "task_count", "entry_budget", "strategy_count_per_slate",
        "source_population_ids", "task_bindings", "task_binding_sha256s",
        "one_reused_job_for_all_slates",
        "common_world_matrix_reconstructed_once_per_slate",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "historical_finalist_confirmation",
        "untouched_confirmatory_inference", "task_manifest_sha256",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("adapter_id") != combined.ADAPTER_ID
        or manifest.get("task_manifest_sha256")
        != _hash({key: row for key, row in manifest.items() if key != "task_manifest_sha256"})
        or _identity(manifest.get("incumbent_panel_freeze_identity"), label="incumbent")
        != FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY
        or _identity(manifest.get("profile_terminal_identity"), label="profiles")
        != FIXED_PROFILE_TERMINAL_IDENTITY
        or _identity(manifest.get("hard230_terminal_identity"), label="hard230")
        != FIXED_HARD230_TERMINAL_IDENTITY
        or _identity(
            manifest.get("terminal_build_receipt_identity"), label="build receipt"
        )["uri"] == ""
        or manifest.get("task_count") != TASK_COUNT
        or manifest.get("entry_budget") != combined.ENTRY_BUDGET
        or manifest.get("strategy_count_per_slate") != BOOK_COUNT_PER_SLATE
        or manifest.get("source_population_ids") != list(combined.SOURCE_ORDER)
        or manifest.get("terminal_uri")
        != terminal_uri_v1(output_prefix=str(manifest.get("output_prefix")))
        or _COMMIT_RE.fullmatch(str(manifest.get("code_commit"))) is None
        or _IMAGE_RE.fullmatch(str(manifest.get("image_digest"))) is None
        or manifest.get("reused_job_name") != FIXED_REUSED_JOB_NAME
        or manifest.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or manifest.get("one_reused_job_for_all_slates") is not True
        or manifest.get("common_world_matrix_reconstructed_once_per_slate") is not True
        or manifest.get("population_regeneration_performed") is not False
        or manifest.get("outcome_columns_read") != []
        or manifest.get("uses_realized_outcomes") is not False
        or manifest.get("historical_finalist_confirmation") is not True
        or manifest.get("untouched_confirmatory_inference") is not False
    ):
        _fail("combined task manifest fixed law differs")
    for field in (
        "incumbent_panel_freeze_sha256", "profile_terminal_sha256",
        "profile_task_manifest_sha256", "hard230_terminal_sha256",
        "terminal_build_receipt_sha256",
    ):
        _digest(manifest.get(field), label=field)
    _identity(manifest.get("profile_task_manifest_identity"), label="profile manifest")
    _identity(manifest.get("later_source_identity"), label="later source")
    bindings = [
        _mapping(row, label="combined task binding")
        for row in _sequence(manifest.get("task_bindings"), label="task bindings")
    ]
    if (
        len(bindings) != TASK_COUNT
        or manifest.get("task_binding_sha256s")
        != [row.get("task_binding_sha256") for row in bindings]
    ):
        _fail("combined task binding census differs")
    seen_slates: set[str] = set()
    for ordinal, binding in enumerate(bindings):
        expected_binding_fields = {
            "schema_version", "source_ordinal", "slate_id",
            "incumbent_slate_freeze_identity", "incumbent_slate_freeze_sha256",
            "incumbent_task_result_sha256", "profile_task_result_identity",
            "profile_task_result_sha256", "profile_source_request",
            "profile_source_request_sha256", "hard230_slate_result_sha256",
            "hard230_source_member_identity", "result_uri",
            "task_binding_sha256",
        }
        request = crossed.validate_task_request_v1(binding.get("profile_source_request"))
        slate_id = binding.get("slate_id")
        if (
            set(binding) != expected_binding_fields
            or binding.get("schema_version") != TASK_BINDING_SCHEMA
            or binding.get("source_ordinal") != ordinal
            or type(slate_id) is not str
            or not slate_id
            or slate_id in seen_slates
            or binding.get("task_binding_sha256")
            != _hash({key: row for key, row in binding.items() if key != "task_binding_sha256"})
            or request.get("source_ordinal") != ordinal
            or request.get("profile_order") != list(combined.PROFILE_SOURCE_IDS)
            or binding.get("profile_source_request_sha256") != request.get("request_sha256")
            or binding.get("result_uri")
            != task_result_uri_v1(output_prefix=str(manifest["output_prefix"]), source_ordinal=ordinal)
        ):
            _fail(f"combined task binding[{ordinal}] differs")
        seen_slates.add(str(slate_id))
        _identity(binding.get("incumbent_slate_freeze_identity"), label="incumbent leaf")
        _identity(binding.get("profile_task_result_identity"), label="profile result")
        _mapping(binding.get("hard230_source_member_identity"), label="hard230 member")
        for field in (
            "incumbent_slate_freeze_sha256", "incumbent_task_result_sha256",
            "profile_task_result_sha256", "profile_source_request_sha256",
            "hard230_slate_result_sha256",
        ):
            _digest(binding.get(field), label=field)
    return manifest


def build_task_result_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
    source_ordinal: int,
    runtime_authority: Mapping[str, object],
    science_result: Mapping[str, object],
) -> dict[str, object]:
    retained_manifest = validate_task_manifest_v1(manifest)
    retained_identity = _identity(manifest_identity, label="combined task manifest")
    if type(source_ordinal) is not int or not 0 <= source_ordinal < TASK_COUNT:
        _fail("combined task result source ordinal differs")
    binding = retained_manifest["task_bindings"][source_ordinal]
    retained_runtime = validate_runtime_authority_v1(
        runtime_authority,
        manifest=retained_manifest,
        manifest_identity=retained_identity,
    )
    if retained_runtime["task_index"] != source_ordinal:
        _fail("combined runtime task index differs from result source ordinal")
    normalized = combined.normalized_slate_for_grader_v1(
        science_result, source_ordinal=source_ordinal
    )
    if (
        normalized["slate_id"] != binding["slate_id"]
        or normalized["later_source_identity"]
        != retained_manifest["later_source_identity"]
    ):
        _fail("combined task result source binding differs")
    body = {
        "schema_version": TASK_RESULT_SCHEMA,
        "adapter_id": combined.ADAPTER_ID,
        "source_ordinal": source_ordinal,
        "slate_id": normalized["slate_id"],
        "task_manifest_identity": retained_identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "task_binding_sha256": binding["task_binding_sha256"],
        "runtime_authority": retained_runtime,
        "runtime_authority_sha256": retained_runtime[
            "runtime_authority_sha256"
        ],
        "science_result": dict(science_result),
        "science_result_sha256": science_result["result_sha256"],
        "union_lineup_count": science_result["union"]["union_lineup_count"],
        "book_count": science_result["book_count"],
        "entry_budget": science_result["entry_budget"],
        "common_world_matrix_reconstructed_once": True,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }
    return _with_hash(body, field="task_result_sha256")


def validate_task_result_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    result = _mapping(value, label="combined task result")
    retained_manifest = validate_task_manifest_v1(manifest)
    retained_manifest_identity = _identity(
        manifest_identity, label="expected combined task manifest"
    )
    expected_fields = {
        "schema_version", "adapter_id", "source_ordinal", "slate_id",
        "task_manifest_identity", "task_manifest_sha256", "task_binding_sha256",
        "runtime_authority", "runtime_authority_sha256",
        "science_result", "science_result_sha256", "union_lineup_count",
        "book_count", "entry_budget", "common_world_matrix_reconstructed_once",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "complete", "task_result_sha256",
    }
    ordinal = result.get("source_ordinal")
    if type(ordinal) is not int or not 0 <= ordinal < TASK_COUNT:
        _fail("combined task result source ordinal differs")
    binding = retained_manifest["task_bindings"][ordinal]
    science = _mapping(result.get("science_result"), label="combined science result")
    runtime = validate_runtime_authority_v1(
        result.get("runtime_authority"),
        manifest=retained_manifest,
        manifest_identity=retained_manifest_identity,
    )
    if runtime["task_index"] != ordinal:
        _fail("combined runtime task index differs from persisted source ordinal")
    normalized = combined.normalized_slate_for_grader_v1(
        science, source_ordinal=ordinal
    )
    if (
        set(result) != expected_fields
        or result.get("schema_version") != TASK_RESULT_SCHEMA
        or result.get("adapter_id") != combined.ADAPTER_ID
        or result.get("task_result_sha256")
        != _hash({key: row for key, row in result.items() if key != "task_result_sha256"})
        or result.get("slate_id") != binding["slate_id"]
        or normalized["slate_id"] != binding["slate_id"]
        or result.get("task_manifest_sha256")
        != retained_manifest["task_manifest_sha256"]
        or result.get("task_manifest_identity") != retained_manifest_identity
        or result.get("task_binding_sha256") != binding["task_binding_sha256"]
        or result.get("runtime_authority_sha256")
        != runtime["runtime_authority_sha256"]
        or result.get("science_result_sha256") != science.get("result_sha256")
        or result.get("union_lineup_count")
        != science.get("union", {}).get("union_lineup_count")
        or result.get("book_count") != BOOK_COUNT_PER_SLATE
        or result.get("entry_budget") != combined.ENTRY_BUDGET
        or result.get("common_world_matrix_reconstructed_once") is not True
        or result.get("population_regeneration_performed") is not False
        or result.get("outcome_columns_read") != []
        or result.get("uses_realized_outcomes") is not False
        or result.get("complete") is not True
    ):
        _fail("combined task result fixed law differs")
    _identity(result.get("task_manifest_identity"), label="result task manifest")
    return result


def normalized_task_result_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    result = validate_task_result_v1(
        value, manifest=manifest, manifest_identity=manifest_identity
    )
    return combined.normalized_slate_for_grader_v1(
        result["science_result"], source_ordinal=int(result["source_ordinal"])
    )


def validate_exact_science_replay_v1(
    persisted_task_result: object,
    *,
    replayed_science_result: object,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    """Require exact source/matrix/selector replay, not coherent substitution."""
    persisted = validate_task_result_v1(
        persisted_task_result,
        manifest=manifest,
        manifest_identity=manifest_identity,
    )
    replayed = _mapping(
        replayed_science_result, label="exact replayed combined science result"
    )
    ordinal = int(persisted["source_ordinal"])
    try:
        combined.validate_exact_science_replay_v1(
            persisted["science_result"], replayed, source_ordinal=ordinal
        )
    except combined.CorpusR6CombinedPopulationAllBlockV1Error as exc:
        raise CorpusR6CombinedPopulationAllBlockExecutionV1Error(str(exc)) from exc
    return persisted


def expected_provider_job_observation_v1(
    *, manifest: Mapping[str, object], manifest_identity: object
) -> dict[str, object]:
    return _provider_job_projection_from_configuration_v1(
        build_job_configuration_v1(
            manifest=manifest, manifest_identity=manifest_identity
        )
    )


def validate_provider_job_observation_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object
) -> dict[str, object]:
    """Validate the provider-observed deployed job, not a desired config."""
    retained = validate_task_manifest_v1(manifest)
    expected = expected_provider_job_observation_v1(
        manifest=retained, manifest_identity=manifest_identity
    )
    row = _mapping(value, label="combined provider job observation")
    required = {
        "job_name", "job_uid", "project_id", "region", "image_digest", "immutable_image_uri",
        "source_commit", "container_command", "container_args",
        "container_environment", "task_count", "parallelism", "max_retries",
        "timeout_seconds", "cpu", "memory", "working_directory", "volumes",
        "volume_mounts", "provider_observed",
    }
    if (
        set(row) != required
        or row != expected
    ):
        _fail("combined provider-observed reused job differs")
    return row


def validate_provider_terminal_execution_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object
) -> dict[str, object]:
    """Require one provider-terminal 54/54 execution before result discovery."""
    row = _mapping(value, label="combined provider terminal execution")
    job = validate_provider_job_observation_v1(
        row.get("job_observation"), manifest=manifest,
        manifest_identity=manifest_identity,
    )
    if (
        set(row) != {
            "execution_id", "job_name", "job_uid", "task_count",
            "succeeded_count", "failed_count", "cancelled_count",
            "running_count", "terminal", "provider_observed", "job_observation",
        }
        or type(row.get("execution_id")) is not str
        or not row["execution_id"]
        or row.get("job_name") != FIXED_REUSED_JOB_NAME
        or row.get("job_uid") != FIXED_REUSED_JOB_UID
        or row.get("task_count") != TASK_COUNT
        or row.get("succeeded_count") != TASK_COUNT
        or row.get("failed_count") != 0
        or row.get("cancelled_count") != 0
        or row.get("running_count") != 0
        or row.get("terminal") is not True
        or row.get("provider_observed") is not True
        or job["task_count"] != TASK_COUNT
    ):
        _fail("combined provider terminal execution is not exact 54/54 success")
    return row


def build_terminal_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
    task_results: Sequence[tuple[Mapping[str, object], Mapping[str, object]]],
    provider_terminal_execution: Mapping[str, object],
) -> dict[str, object]:
    retained_manifest = validate_task_manifest_v1(manifest)
    retained_manifest_identity = _identity(
        manifest_identity, label="combined terminal manifest"
    )
    pairs = list(task_results)
    provider_terminal = validate_provider_terminal_execution_v1(
        provider_terminal_execution, manifest=retained_manifest,
        manifest_identity=retained_manifest_identity,
    )
    if len(pairs) != TASK_COUNT:
        _fail("combined terminal requires exactly 54 task results")
    descriptors: list[dict[str, object]] = []
    normalized: list[dict[str, object]] = []
    execution_ids: set[str] = set()
    for ordinal, (raw_result, raw_identity) in enumerate(pairs):
        result = validate_task_result_v1(
            raw_result,
            manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
        )
        identity = _identity(raw_identity, label=f"combined task result[{ordinal}]")
        binding = retained_manifest["task_bindings"][ordinal]
        if (
            result["source_ordinal"] != ordinal
            or identity["uri"] != binding["result_uri"]
            or identity["sha256"] != sha256(_canonical(result)).hexdigest()
            or identity["bytes"] != len(_canonical(result))
        ):
            _fail(f"combined terminal task result[{ordinal}] binding differs")
        descriptors.append({
            "source_ordinal": ordinal,
            "slate_id": result["slate_id"],
            "task_result_identity": identity,
            "task_result_sha256": result["task_result_sha256"],
            "science_result_sha256": result["science_result_sha256"],
            "union_lineup_count": result["union_lineup_count"],
        })
        execution_ids.add(str(result["runtime_authority"]["execution_id"]))
        normalized.append(normalized_task_result_v1(
            result,
            manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
        ))
    try:
        grader.validate_external_normalized_terminal_v1(
            adapter_id=combined.ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6CombinedPopulationAllBlockExecutionV1Error(str(exc)) from exc
    if execution_ids != {str(provider_terminal["execution_id"])}:
        _fail("combined task results do not share provider terminal execution")
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "adapter_id": combined.ADAPTER_ID,
        "task_manifest_identity": retained_manifest_identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "incumbent_panel_freeze_identity": retained_manifest[
            "incumbent_panel_freeze_identity"
        ],
        "profile_terminal_identity": retained_manifest["profile_terminal_identity"],
        "hard230_terminal_identity": retained_manifest["hard230_terminal_identity"],
        "later_source_identity": retained_manifest["later_source_identity"],
        "output_prefix": retained_manifest["output_prefix"],
        "terminal_uri": retained_manifest["terminal_uri"],
        "source_slate_count": TASK_COUNT,
        "book_count_per_slate": BOOK_COUNT_PER_SLATE,
        "entry_budget": combined.ENTRY_BUDGET,
        "task_results": descriptors,
        "task_results_sha256": _hash(descriptors),
        "execution_id": provider_terminal["execution_id"],
        "provider_terminal_execution": provider_terminal,
        "provider_terminal_execution_sha256": _hash(provider_terminal),
        "all_task_results_exact_opened": True,
        "all_task_results_adapter_validated": True,
        "generic_normalized_terminal_validated": True,
        "terminal_built_after_all_task_results": True,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_finalist_confirmation": True,
        "untouched_confirmatory_inference": False,
        "complete": True,
    }
    return _with_hash(body, field="terminal_sha256")


def validate_terminal_envelope_v1(value: object) -> dict[str, object]:
    terminal = _mapping(value, label="combined terminal")
    expected_fields = {
        "schema_version", "adapter_id", "task_manifest_identity",
        "task_manifest_sha256", "incumbent_panel_freeze_identity",
        "profile_terminal_identity", "hard230_terminal_identity",
        "later_source_identity", "output_prefix", "terminal_uri",
        "source_slate_count", "book_count_per_slate", "entry_budget",
        "task_results", "task_results_sha256", "all_task_results_exact_opened",
        "execution_id", "provider_terminal_execution",
        "provider_terminal_execution_sha256",
        "all_task_results_adapter_validated", "generic_normalized_terminal_validated",
        "terminal_built_after_all_task_results", "population_regeneration_performed",
        "outcome_columns_read", "uses_realized_outcomes",
        "historical_finalist_confirmation", "untouched_confirmatory_inference",
        "complete", "terminal_sha256",
    }
    descriptors = [
        _mapping(row, label="combined terminal result descriptor")
        for row in _sequence(terminal.get("task_results"), label="terminal results")
    ]
    if (
        set(terminal) != expected_fields
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("adapter_id") != combined.ADAPTER_ID
        or terminal.get("terminal_sha256")
        != _hash({key: row for key, row in terminal.items() if key != "terminal_sha256"})
        or terminal.get("source_slate_count") != TASK_COUNT
        or terminal.get("book_count_per_slate") != BOOK_COUNT_PER_SLATE
        or terminal.get("entry_budget") != combined.ENTRY_BUDGET
        or len(descriptors) != TASK_COUNT
        or terminal.get("task_results_sha256") != _hash(descriptors)
        or terminal.get("provider_terminal_execution_sha256")
        != _hash(terminal.get("provider_terminal_execution"))
        or terminal.get("execution_id")
        != _mapping(terminal.get("provider_terminal_execution"), label="terminal provider execution").get("execution_id")
        or [row.get("source_ordinal") for row in descriptors] != list(range(TASK_COUNT))
        or len({str(row.get("slate_id")) for row in descriptors}) != TASK_COUNT
        or terminal.get("terminal_uri")
        != terminal_uri_v1(output_prefix=str(terminal.get("output_prefix")))
        or terminal.get("all_task_results_exact_opened") is not True
        or terminal.get("all_task_results_adapter_validated") is not True
        or terminal.get("generic_normalized_terminal_validated") is not True
        or terminal.get("terminal_built_after_all_task_results") is not True
        or terminal.get("population_regeneration_performed") is not False
        or terminal.get("outcome_columns_read") != []
        or terminal.get("uses_realized_outcomes") is not False
        or terminal.get("historical_finalist_confirmation") is not True
        or terminal.get("untouched_confirmatory_inference") is not False
        or terminal.get("complete") is not True
    ):
        _fail("combined terminal fixed law differs")
    _identity(terminal.get("task_manifest_identity"), label="terminal manifest")
    _identity(terminal.get("later_source_identity"), label="terminal later source")
    if (
        _identity(terminal.get("incumbent_panel_freeze_identity"), label="incumbent")
        != FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY
        or _identity(terminal.get("profile_terminal_identity"), label="profiles")
        != FIXED_PROFILE_TERMINAL_IDENTITY
        or _identity(terminal.get("hard230_terminal_identity"), label="hard230")
        != FIXED_HARD230_TERMINAL_IDENTITY
    ):
        _fail("combined terminal source identity differs")
    _digest(terminal.get("task_manifest_sha256"), label="terminal manifest SHA")
    for ordinal, row in enumerate(descriptors):
        if set(row) != {
            "source_ordinal", "slate_id", "task_result_identity",
            "task_result_sha256", "science_result_sha256", "union_lineup_count",
        } or row.get("source_ordinal") != ordinal:
            _fail(f"combined terminal descriptor[{ordinal}] differs")
        _identity(row.get("task_result_identity"), label="terminal task result")
        _digest(row.get("task_result_sha256"), label="task result SHA")
        _digest(row.get("science_result_sha256"), label="science result SHA")
        if type(row.get("union_lineup_count")) is not int or row["union_lineup_count"] < 80:
            _fail("combined terminal union count differs")
    return terminal


def validate_terminal_with_results_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    task_results: Sequence[tuple[Mapping[str, object], Mapping[str, object]]],
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    terminal = validate_terminal_envelope_v1(value)
    expected = build_terminal_v1(
        manifest=manifest,
        manifest_identity=terminal["task_manifest_identity"],
        task_results=task_results,
        provider_terminal_execution=terminal["provider_terminal_execution"],
    )
    if _canonical(terminal) != _canonical(expected):
        _fail("combined terminal exact result reconstruction differs")
    normalized = tuple(
        normalized_task_result_v1(
            result,
            manifest=manifest,
            manifest_identity=terminal["task_manifest_identity"],
        )
        for result, _identity_value in task_results
    )
    return expected, normalized


__all__ = [
    "BOOK_COUNT_PER_SLATE",
    "FIXED_HARD230_TERMINAL_IDENTITY",
    "FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY",
    "FIXED_PROFILE_TERMINAL_IDENTITY",
    "MANIFEST_SCHEMA",
    "TASK_COUNT",
    "TASK_RESULT_SCHEMA",
    "TERMINAL_SCHEMA",
    "CorpusR6CombinedPopulationAllBlockExecutionV1Error",
    "build_task_manifest_v1",
    "build_task_result_v1",
    "build_runtime_authority_v1",
    "build_terminal_v1",
    "grade_uri_v1",
    "normalized_task_result_v1",
    "task_result_uri_v1",
    "terminal_uri_v1",
    "validate_task_manifest_v1",
    "validate_task_result_v1",
    "validate_runtime_authority_v1",
    "validate_exact_science_replay_v1",
    "validate_terminal_envelope_v1",
    "validate_terminal_with_results_v1",
]
