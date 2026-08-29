#!/usr/bin/env python3
"""Run four score-blind selectors on a complete-union modeled-tail sieve.

This operator never regenerates a population and never reruns the eight
selectors stored in the predecessor combined result.  A worker exact-opens
one completed combined task, reloads its already-bound common player/world
source, reconstructs only the persisted complete-union score matrix, requires
the predecessor matrix SHA-256, screens all union rows to exact top 250, and
then runs the bounded re-portfolio
core.  Collection publishes a public normalized-roster surface before one
create-last score-free terminal.  ``grade`` is a thin use of the existing
direct-roster realized scorer and is intentionally a separate command.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Final

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for _import_path in (ROOT, ROOT / "src"):
    if str(_import_path) not in sys.path:
        sys.path.insert(0, str(_import_path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_combined_frontier_reportfolio_v1 as frontier,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_combined_population_all_block_execution_v1 as predecessor_execution,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_combined_population_all_block_v1 as predecessor_science,
)
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as l2b_panel  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_novel_roster_realized_grader_v1 as grader,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_population_crossed_cloud_v1 as crossed,
)
from nfl_dfs.research.corpus_legal_feasibility import (  # noqa: E402
    cross_score_full_union,
)

try:  # noqa: E402
    from scripts import run_corpus_r6_combined_population_all_block_v1 as prior_operator
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    import run_corpus_r6_combined_population_all_block_v1 as prior_operator


ADAPTER_ID: Final = "combined-complete-union-sieve-reportfolio-v1"
MANIFEST_SCHEMA: Final = "corpus-r6-combined-frontier-reportfolio-manifest/v1"
TASK_RESULT_SCHEMA: Final = (
    "corpus-r6-combined-frontier-reportfolio-task-result/v1"
)
NORMALIZED_SURFACE_SCHEMA: Final = (
    "corpus-r6-combined-frontier-reportfolio-normalized-surface/v1"
)
TERMINAL_SCHEMA: Final = "corpus-r6-combined-frontier-reportfolio-terminal/v1"
GRADE_SCHEMA: Final = (
    "corpus-r6-combined-frontier-reportfolio-descriptive-realized-grade/v1"
)
PROVIDER_TERMINAL_SCHEMA: Final = (
    "corpus-r6-combined-frontier-provider-terminal-execution/v1"
)

ENABLE_ENV: Final = "R6_COMBINED_FRONTIER_REPORTFOLIO_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_SCORE_BLIND_FRONTIER_REPORTFOLIO_V1"
MANIFEST_IDENTITY_ENV: Final = (
    "R6_COMBINED_FRONTIER_REPORTFOLIO_MANIFEST_IDENTITY"
)
FIXED_PROJECT: Final = predecessor_execution.FIXED_GCP_PROJECT
FIXED_REGION: Final = predecessor_execution.FIXED_REGION
FIXED_REUSED_JOB_NAME: Final = predecessor_execution.FIXED_REUSED_JOB_NAME
FIXED_REUSED_JOB_UID: Final = predecessor_execution.FIXED_REUSED_JOB_UID
TASK_COUNT: Final = predecessor_execution.TASK_COUNT
BOOK_COUNT_PER_SLATE: Final = 12
ENTRY_BUDGETS: Final = frontier.ENTRY_BUDGETS
SELECTOR_IDS: Final = frontier.SELECTOR_IDS
EXPECTED_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    "/app/scripts/run_corpus_r6_combined_frontier_reportfolio_v1.py",
    "task",
    "--execute",
)
FIXED_PARALLELISM: Final = TASK_COUNT
FIXED_MAX_RETRIES: Final = 0
FIXED_TIMEOUT_SECONDS: Final = predecessor_execution.FIXED_TIMEOUT_SECONDS
FIXED_CPU: Final = predecessor_execution.FIXED_CPU
FIXED_MEMORY: Final = predecessor_execution.FIXED_MEMORY
JOB_AUTHORITY_SHA_ENV: Final = predecessor_execution.JOB_AUTHORITY_SHA_ENV

MAXIMUM_REQUEST_BYTES: Final = 1_000_000
MAXIMUM_MANIFEST_BYTES: Final = 2_000_000
MAXIMUM_PREDECESSOR_TERMINAL_BYTES: Final = 2_000_000
MAXIMUM_PREDECESSOR_TASK_BYTES: Final = 256_000_000
MAXIMUM_TASK_RESULT_BYTES: Final = 256_000_000
MAXIMUM_NORMALIZED_SURFACE_BYTES: Final = 64_000_000
MAXIMUM_TERMINAL_BYTES: Final = 2_000_000
MAXIMUM_GRADE_BYTES: Final = 128_000_000

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_RE: Final = re.compile(r"sha256:[0-9a-f]{64}\Z")


class RunCorpusR6CombinedFrontierReportfolioV1Error(RuntimeError):
    """The bounded combined-frontier operator failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CombinedFrontierReportfolioV1Error(message)


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
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: _hash(body)}


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc


def _strict_json(raw: bytes, *, label: str, maximum_bytes: int) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
        _fail(f"{label} bytes differ")
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(
            f"{label} is not JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if _canonical(body) != raw:
        _fail(f"{label} is not canonical JSON")
    return body


def _read_json(
    identity_value: object,
    *,
    store: object,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    raw = store.read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    return _strict_json(raw, label=label, maximum_bytes=maximum_bytes), identity


def _open_known_json(
    uri: str,
    *,
    store: object,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity_value = store.open_known(uri, maximum_bytes)
    identity = _identity(identity_value, label=f"{label} identity")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} known-object identity differs")
    return _strict_json(raw, label=label, maximum_bytes=maximum_bytes), identity


def _publish_json(
    *, uri: str, value: Mapping[str, object], maximum_bytes: int, store: object
) -> dict[str, object]:
    raw = _canonical(value)
    if not raw or len(raw) > maximum_bytes:
        _fail("publication exceeds its exact byte ceiling")
    identity = _identity(
        store.publish_create_once(uri, raw), label="published object"
    )
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
        or store.read_exact(identity) != raw
    ):
        _fail("create-once publication exact reopen differs")
    return identity


def _output_prefix(value: object) -> str:
    marker = "/research/corpus-r6-combined-frontier-reportfolio/"
    if (
        type(value) is not str
        or not value.startswith(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
        )
        or marker not in value
        or not value.endswith("/")
        or "//" in value[5:]
    ):
        _fail("combined-frontier output prefix differs")
    return value


def _result_uri(*, output_prefix: str, source_ordinal: int) -> str:
    if type(source_ordinal) is not int or not 0 <= source_ordinal < TASK_COUNT:
        _fail("combined-frontier source ordinal differs")
    return f"{_output_prefix(output_prefix)}slates/{source_ordinal:02d}/result.json"


def _manifest_uri(output_prefix: str) -> str:
    return f"{_output_prefix(output_prefix)}manifest.json"


def _normalized_surface_uri(output_prefix: str) -> str:
    return f"{_output_prefix(output_prefix)}full-54/normalized-surface.json"


def _terminal_uri(output_prefix: str) -> str:
    return f"{_output_prefix(output_prefix)}full-54/terminal.json"


def _grade_uri(output_prefix: str) -> str:
    return f"{_output_prefix(output_prefix)}full-54/descriptive-realized-grade.json"


def _open_predecessor_terminal(
    identity_value: object, *, store: object
) -> tuple[dict[str, object], dict[str, object]]:
    terminal, identity = _read_json(
        identity_value,
        store=store,
        label="predecessor combined terminal",
        maximum_bytes=MAXIMUM_PREDECESSOR_TERMINAL_BYTES,
    )
    try:
        retained = predecessor_execution.validate_descriptive_terminal_envelope_v2(
            terminal
        )
    except predecessor_execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    if identity["uri"] != retained["terminal_uri"]:
        _fail("predecessor combined terminal outer URI differs")
    return retained, identity


def build_manifest_v1(
    *,
    predecessor_terminal: Mapping[str, object],
    predecessor_terminal_identity: object,
    terminal_build_receipt_identity: object,
    code_commit: str,
    image_digest: str,
    immutable_image_uri: str,
    output_prefix: str,
) -> dict[str, object]:
    terminal = predecessor_execution.validate_descriptive_terminal_envelope_v2(
        predecessor_terminal
    )
    terminal_identity = _identity(
        predecessor_terminal_identity, label="predecessor terminal"
    )
    build_identity = _identity(
        terminal_build_receipt_identity, label="terminal build receipt"
    )
    prefix = _output_prefix(output_prefix)
    if (
        terminal_identity["uri"] != terminal["terminal_uri"]
        or terminal_identity["sha256"] != sha256(_canonical(terminal)).hexdigest()
        or terminal_identity["bytes"] != len(_canonical(terminal))
        or _COMMIT_RE.fullmatch(code_commit) is None
        or _IMAGE_RE.fullmatch(image_digest) is None
        or type(immutable_image_uri) is not str
        or not immutable_image_uri.endswith(f"@{image_digest}")
    ):
        _fail("combined-frontier manifest outer authority differs")
    descriptors = _sequence(
        terminal["task_results"], label="predecessor terminal task results"
    )
    if len(descriptors) != TASK_COUNT:
        _fail("combined-frontier predecessor terminal is not exact 54")
    bindings: list[dict[str, object]] = []
    for ordinal, raw_descriptor in enumerate(descriptors):
        descriptor = _mapping(
            raw_descriptor, label=f"predecessor descriptor[{ordinal}]"
        )
        body = {
            "source_ordinal": ordinal,
            "slate_id": descriptor["slate_id"],
            "predecessor_task_result_identity": descriptor[
                "task_result_identity"
            ],
            "predecessor_task_result_sha256": descriptor["task_result_sha256"],
            "predecessor_science_result_sha256": descriptor[
                "science_result_sha256"
            ],
            "predecessor_union_lineup_count": descriptor["union_lineup_count"],
            "result_uri": _result_uri(
                output_prefix=prefix, source_ordinal=ordinal
            ),
        }
        bindings.append(_with_hash(body, field="task_binding_sha256"))
    body = {
        "schema_version": MANIFEST_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "predecessor_terminal_identity": terminal_identity,
        "predecessor_terminal_sha256": terminal["terminal_sha256"],
        "predecessor_task_manifest_identity": terminal[
            "task_manifest_identity"
        ],
        "predecessor_task_manifest_sha256": terminal["task_manifest_sha256"],
        "later_source_identity": terminal["later_source_identity"],
        "terminal_build_receipt_identity": build_identity,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "immutable_image_uri": immutable_image_uri,
        "output_prefix": prefix,
        "manifest_uri": _manifest_uri(prefix),
        "normalized_surface_uri": _normalized_surface_uri(prefix),
        "terminal_uri": _terminal_uri(prefix),
        "descriptive_grade_uri": _grade_uri(prefix),
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "task_count": TASK_COUNT,
        "book_count_per_slate": BOOK_COUNT_PER_SLATE,
        "selector_ids": list(SELECTOR_IDS),
        "entry_budgets": list(ENTRY_BUDGETS),
        "task_bindings": bindings,
        "task_binding_sha256s": [
            row["task_binding_sha256"] for row in bindings
        ],
        "complete_union_candidate_source": True,
        "candidate_sieve_law": frontier.SIEVE_LAW,
        "candidate_sieve_limit": frontier.SIEVE_LIMIT,
        "old_book_membership_used_for_sieve": False,
        "predecessor_populations_reused": True,
        "predecessor_eight_selectors_rerun": False,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "promotion_authority": False,
        "production_change_licensed": False,
    }
    return _with_hash(body, field="manifest_sha256")


def validate_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="combined-frontier manifest")
    expected_fields = {
        "schema_version", "adapter_id", "predecessor_terminal_identity",
        "predecessor_terminal_sha256", "predecessor_task_manifest_identity",
        "predecessor_task_manifest_sha256", "later_source_identity",
        "terminal_build_receipt_identity", "code_commit", "image_digest",
        "immutable_image_uri", "output_prefix", "manifest_uri",
        "normalized_surface_uri", "terminal_uri", "descriptive_grade_uri",
        "reused_job_name", "reused_job_uid", "project_id", "region",
        "task_count", "book_count_per_slate", "selector_ids", "entry_budgets",
        "task_bindings", "task_binding_sha256s",
        "complete_union_candidate_source", "candidate_sieve_law",
        "candidate_sieve_limit", "old_book_membership_used_for_sieve",
        "predecessor_populations_reused", "predecessor_eight_selectors_rerun",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "descriptive_only", "promotion_authority",
        "production_change_licensed", "manifest_sha256",
    }
    prefix = _output_prefix(manifest.get("output_prefix"))
    bindings = [
        _mapping(row, label="combined-frontier task binding")
        for row in _sequence(manifest.get("task_bindings"), label="task bindings")
    ]
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("adapter_id") != ADAPTER_ID
        or manifest.get("manifest_sha256")
        != _hash({key: row for key, row in manifest.items() if key != "manifest_sha256"})
        or _COMMIT_RE.fullmatch(str(manifest.get("code_commit"))) is None
        or _IMAGE_RE.fullmatch(str(manifest.get("image_digest"))) is None
        or manifest.get("immutable_image_uri")
        is None
        or not str(manifest["immutable_image_uri"]).endswith(
            f"@{manifest['image_digest']}"
        )
        or manifest.get("manifest_uri") != _manifest_uri(prefix)
        or manifest.get("normalized_surface_uri") != _normalized_surface_uri(prefix)
        or manifest.get("terminal_uri") != _terminal_uri(prefix)
        or manifest.get("descriptive_grade_uri") != _grade_uri(prefix)
        or manifest.get("reused_job_name") != FIXED_REUSED_JOB_NAME
        or manifest.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or manifest.get("project_id") != FIXED_PROJECT
        or manifest.get("region") != FIXED_REGION
        or manifest.get("task_count") != TASK_COUNT
        or manifest.get("book_count_per_slate") != BOOK_COUNT_PER_SLATE
        or manifest.get("entry_budgets") != list(ENTRY_BUDGETS)
        or manifest.get("selector_ids") != list(SELECTOR_IDS)
        or len(bindings) != TASK_COUNT
        or manifest.get("task_binding_sha256s")
        != [row.get("task_binding_sha256") for row in bindings]
        or manifest.get("complete_union_candidate_source") is not True
        or manifest.get("candidate_sieve_law") != frontier.SIEVE_LAW
        or manifest.get("candidate_sieve_limit") != frontier.SIEVE_LIMIT
        or manifest.get("old_book_membership_used_for_sieve") is not False
        or manifest.get("predecessor_populations_reused") is not True
        or manifest.get("predecessor_eight_selectors_rerun") is not False
        or manifest.get("population_regeneration_performed") is not False
        or manifest.get("outcome_columns_read") != []
        or manifest.get("uses_realized_outcomes") is not False
        or manifest.get("descriptive_only") is not True
        or manifest.get("promotion_authority") is not False
        or manifest.get("production_change_licensed") is not False
    ):
        _fail("combined-frontier manifest fixed law differs")
    _identity(manifest["predecessor_terminal_identity"], label="predecessor terminal")
    _identity(
        manifest["predecessor_task_manifest_identity"],
        label="predecessor task manifest",
    )
    _identity(manifest["later_source_identity"], label="later source")
    _identity(manifest["terminal_build_receipt_identity"], label="build receipt")
    for field in ("predecessor_terminal_sha256", "predecessor_task_manifest_sha256"):
        _digest(manifest[field], label=field)
    for ordinal, binding in enumerate(bindings):
        expected_binding_fields = {
            "source_ordinal", "slate_id", "predecessor_task_result_identity",
            "predecessor_task_result_sha256", "predecessor_science_result_sha256",
            "predecessor_union_lineup_count", "result_uri", "task_binding_sha256",
        }
        if (
            set(binding) != expected_binding_fields
            or binding.get("source_ordinal") != ordinal
            or binding.get("result_uri")
            != _result_uri(output_prefix=prefix, source_ordinal=ordinal)
            or binding.get("task_binding_sha256")
            != _hash({
                key: row for key, row in binding.items()
                if key != "task_binding_sha256"
            })
            or type(binding.get("slate_id")) is not str
            or type(binding.get("predecessor_union_lineup_count")) is not int
            or int(binding["predecessor_union_lineup_count"])
            <= frontier.SIEVE_LIMIT
        ):
            _fail(f"combined-frontier task binding[{ordinal}] differs")
        _identity(
            binding["predecessor_task_result_identity"],
            label=f"predecessor result[{ordinal}]",
        )
        _digest(binding["predecessor_task_result_sha256"], label="task result")
        _digest(binding["predecessor_science_result_sha256"], label="science result")
    return manifest


def build_job_configuration_v1(
    *, manifest: Mapping[str, object], manifest_identity: object
) -> dict[str, object]:
    """Derive the exact configuration for the existing reusable job."""
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="provider manifest")
    body = {
        "schema_version": (
            "corpus-r6-combined-frontier-provider-job-configuration/v1"
        ),
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "task_manifest_identity": identity,
        "task_manifest_sha256": retained["manifest_sha256"],
        "image_digest": retained["image_digest"],
        "immutable_image_uri": retained["immutable_image_uri"],
        "container_command": [EXPECTED_COMMAND[0]],
        "container_args": list(EXPECTED_COMMAND[1:]),
        "container_environment": {
            ENABLE_ENV: ENABLE_VALUE,
            MANIFEST_IDENTITY_ENV: _canonical(identity).decode("utf-8"),
            "GOOGLE_CLOUD_PROJECT": FIXED_PROJECT,
            "CODE_SHA": retained["code_commit"],
            "R6_RUNTIME_IMAGE_DIGEST": retained["image_digest"],
        },
        "task_count": TASK_COUNT,
        "parallelism": FIXED_PARALLELISM,
        "max_retries": FIXED_MAX_RETRIES,
        "timeout_seconds": FIXED_TIMEOUT_SECONDS,
        "cpu": FIXED_CPU,
        "memory": FIXED_MEMORY,
        "working_directory": "",
        "volumes": [],
        "volume_mounts": [],
        "new_job_creation_allowed": False,
    }
    projection = predecessor_execution._provider_job_projection_from_configuration_v1(
        body
    )
    body["container_environment"][JOB_AUTHORITY_SHA_ENV] = _hash(projection)
    return _with_hash(body, field="job_configuration_sha256")


def expected_provider_job_observation_v1(
    *, manifest: Mapping[str, object], manifest_identity: object
) -> dict[str, object]:
    configuration = build_job_configuration_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    return predecessor_execution._provider_job_projection_from_configuration_v1(
        configuration
    )


def validate_provider_job_observation_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    observed = _mapping(value, label="combined-frontier provider job")
    expected = expected_provider_job_observation_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    expected_without_uri = {
        key: row for key, row in expected.items() if key != "immutable_image_uri"
    }
    observed_without_uri = {
        key: row for key, row in observed.items() if key != "immutable_image_uri"
    }
    if (
        observed_without_uri != expected_without_uri
        or not prior_operator._execution_image_matches_job_image_v1(
            execution_uri=observed.get("immutable_image_uri"),
            job_uri=expected.get("immutable_image_uri"),
            expected_digest=expected.get("image_digest"),
        )
    ):
        _fail("combined-frontier provider job observation differs")
    return observed


def build_provider_terminal_execution_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    """Seal one provider-observed exact 54/54 terminal execution."""
    raw = _mapping(value, label="provider terminal execution")
    expected_fields = {
        "execution_id", "job_name", "job_uid", "task_count",
        "succeeded_count", "failed_count", "cancelled_count",
        "running_count", "terminal", "provider_observed", "job_observation",
    }
    job = validate_provider_job_observation_v1(
        raw.get("job_observation"),
        manifest=manifest,
        manifest_identity=manifest_identity,
    )
    retained_manifest = validate_manifest_v1(manifest)
    retained_identity = _identity(manifest_identity, label="provider manifest")
    if (
        set(raw) != expected_fields
        or type(raw.get("execution_id")) is not str
        or not raw["execution_id"]
        or raw.get("job_name") != FIXED_REUSED_JOB_NAME
        or raw.get("job_uid") != FIXED_REUSED_JOB_UID
        or raw.get("task_count") != TASK_COUNT
        or raw.get("succeeded_count") != TASK_COUNT
        or raw.get("failed_count") != 0
        or raw.get("cancelled_count") != 0
        or raw.get("running_count") != 0
        or raw.get("terminal") is not True
        or raw.get("provider_observed") is not True
        or job.get("task_count") != TASK_COUNT
    ):
        _fail("combined-frontier provider execution is not exact 54/54 terminal")
    return _with_hash({
        "schema_version": PROVIDER_TERMINAL_SCHEMA,
        "manifest_identity": retained_identity,
        "manifest_sha256": retained_manifest["manifest_sha256"],
        **raw,
        "job_observation_sha256": _hash(job),
    }, field="provider_terminal_execution_sha256")


def validate_provider_terminal_execution_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    proof = _mapping(value, label="combined-frontier provider terminal proof")
    expected_fields = {
        "schema_version", "manifest_identity", "manifest_sha256",
        "execution_id", "job_name", "job_uid", "task_count",
        "succeeded_count", "failed_count", "cancelled_count",
        "running_count", "terminal", "provider_observed", "job_observation",
        "job_observation_sha256", "provider_terminal_execution_sha256",
    }
    retained_manifest = validate_manifest_v1(manifest)
    retained_identity = _identity(manifest_identity, label="provider manifest")
    if (
        set(proof) != expected_fields
        or proof.get("schema_version") != PROVIDER_TERMINAL_SCHEMA
        or proof.get("manifest_identity") != retained_identity
        or proof.get("manifest_sha256") != retained_manifest["manifest_sha256"]
        or proof.get("provider_terminal_execution_sha256")
        != _hash({
            key: row for key, row in proof.items()
            if key != "provider_terminal_execution_sha256"
        })
        or proof.get("job_observation_sha256")
        != _hash(proof.get("job_observation"))
    ):
        _fail("combined-frontier provider terminal proof differs")
    raw = {
        key: proof[key] for key in (
            "execution_id", "job_name", "job_uid", "task_count",
            "succeeded_count", "failed_count", "cancelled_count",
            "running_count", "terminal", "provider_observed", "job_observation",
        )
    }
    expected = build_provider_terminal_execution_v1(
        raw, manifest=retained_manifest, manifest_identity=retained_identity
    )
    if _canonical(proof) != _canonical(expected):
        _fail("combined-frontier provider terminal proof canonical replay differs")
    return proof


def configure_existing_job_v1(
    *, manifest_identity: object, store: object, provider: object
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    current_identity = provider.describe_job_identity(FIXED_REUSED_JOB_NAME)
    if current_identity != {
        "job_name": FIXED_REUSED_JOB_NAME,
        "job_uid": FIXED_REUSED_JOB_UID,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "provider_observed": True,
    }:
        _fail("combined-frontier reusable job identity differs")
    configuration = build_job_configuration_v1(
        manifest=manifest, manifest_identity=retained_identity
    )
    provider.update_existing_job(configuration)
    observation = validate_provider_job_observation_v1(
        provider.describe_job(FIXED_REUSED_JOB_NAME),
        manifest=manifest,
        manifest_identity=retained_identity,
    )
    return {
        "schema_version": "corpus-r6-combined-frontier-configure-result/v1",
        "job_configuration_sha256": configuration["job_configuration_sha256"],
        "job_observation": observation,
        "job_observation_sha256": _hash(observation),
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "new_job_created": False,
        "complete": True,
    }


def launch_existing_job_v1(
    *, manifest_identity: object, store: object, provider: object
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    observation = validate_provider_job_observation_v1(
        provider.describe_job(FIXED_REUSED_JOB_NAME),
        manifest=manifest,
        manifest_identity=retained_identity,
    )
    execution_id = provider.launch_existing_job(FIXED_REUSED_JOB_NAME)
    if type(execution_id) is not str or not execution_id:
        _fail("combined-frontier provider launch returned no execution ID")
    return {
        "schema_version": "corpus-r6-combined-frontier-launch-result/v1",
        "execution_id": execution_id,
        "job_observation_sha256": _hash(observation),
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "new_job_created": False,
        "complete": True,
    }


def status_existing_execution_v1(
    *,
    manifest_identity: object,
    execution_id: str,
    store: object,
    provider: object,
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    raw = provider.describe_execution(execution_id)
    if raw.get("execution_id") != execution_id:
        _fail("combined-frontier provider status execution ID differs")
    return build_provider_terminal_execution_v1(
        raw, manifest=manifest, manifest_identity=retained_identity
    )


def prepare_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="combined-frontier prepare request")
    expected = {
        "predecessor_terminal_identity", "terminal_build_receipt_identity",
        "code_commit", "image_digest", "immutable_image_uri", "output_prefix",
    }
    if set(item) != expected:
        _fail("combined-frontier prepare request fields differ")
    terminal, terminal_identity = _open_predecessor_terminal(
        item["predecessor_terminal_identity"], store=store
    )
    try:
        _receipt, build_identity = l2b_panel._read_terminal_build_receipt(
            item["terminal_build_receipt_identity"],
            source_commit_sha=str(item["code_commit"]),
            immutable_image_digest=str(item["image_digest"]),
            read_exact=store.read_exact,
            label="combined-frontier terminal build receipt",
        )
    except l2b_panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    manifest = build_manifest_v1(
        predecessor_terminal=terminal,
        predecessor_terminal_identity=terminal_identity,
        terminal_build_receipt_identity=build_identity,
        code_commit=str(item["code_commit"]),
        image_digest=str(item["image_digest"]),
        immutable_image_uri=str(item["immutable_image_uri"]),
        output_prefix=str(item["output_prefix"]),
    )
    identity = _publish_json(
        uri=str(manifest["manifest_uri"]),
        value=manifest,
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-frontier-reportfolio-prepare-result/v1",
        "manifest_identity": identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "task_count": TASK_COUNT,
        "complete_union_candidate_source": True,
        "candidate_sieve_law": frontier.SIEVE_LAW,
        "candidate_sieve_limit": frontier.SIEVE_LIMIT,
        "old_book_membership_used_for_sieve": False,
        "predecessor_populations_reused": True,
        "predecessor_eight_selectors_rerun": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _open_manifest(
    identity_value: object, *, store: object
) -> tuple[dict[str, object], dict[str, object]]:
    manifest, identity = _read_json(
        identity_value,
        store=store,
        label="combined-frontier manifest",
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    retained = validate_manifest_v1(manifest)
    if identity["uri"] != retained["manifest_uri"]:
        _fail("combined-frontier manifest outer URI differs")
    try:
        _receipt, build_identity = l2b_panel._read_terminal_build_receipt(
            retained["terminal_build_receipt_identity"],
            source_commit_sha=str(retained["code_commit"]),
            immutable_image_digest=str(retained["image_digest"]),
            read_exact=store.read_exact,
            label="combined-frontier retained terminal build receipt",
        )
    except l2b_panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    if build_identity != retained["terminal_build_receipt_identity"]:
        _fail("combined-frontier retained build receipt identity differs")
    return retained, identity


def _observed_command_v1(raw_cmdline: bytes | None = None) -> list[str]:
    if raw_cmdline is None:
        raw_cmdline = Path("/proc/self/cmdline").read_bytes()
    if type(raw_cmdline) is not bytes or not raw_cmdline.endswith(b"\x00"):
        _fail("combined-frontier process command is unavailable")
    try:
        command = [part.decode("utf-8") for part in raw_cmdline[:-1].split(b"\x00")]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(
            "combined-frontier process command is not UTF-8"
        ) from exc
    if command != list(EXPECTED_COMMAND):
        _fail("combined-frontier process command differs")
    return command


def build_runtime_authority_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
    environment: Mapping[str, str],
    observed_command: Sequence[str],
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="runtime manifest")
    env = dict(environment)
    command = [str(value) for value in observed_command]
    index_text = env.get("CLOUD_RUN_TASK_INDEX", "")
    count_text = env.get("CLOUD_RUN_TASK_COUNT", "")
    attempt_text = env.get("CLOUD_RUN_TASK_ATTEMPT", "")
    execution_id = env.get("CLOUD_RUN_EXECUTION", "")
    if (
        command != list(EXPECTED_COMMAND)
        or env.get("CLOUD_RUN_JOB") != FIXED_REUSED_JOB_NAME
        or not execution_id
        or not index_text.isdecimal()
        or not count_text.isdecimal()
        or attempt_text != "0"
        or int(count_text) != TASK_COUNT
        or not 0 <= int(index_text) < TASK_COUNT
        or env.get(ENABLE_ENV) != ENABLE_VALUE
        or env.get(MANIFEST_IDENTITY_ENV) != _canonical(identity).decode("utf-8")
        or env.get("CODE_SHA") != retained["code_commit"]
        or env.get("R6_RUNTIME_IMAGE_DIGEST") != retained["image_digest"]
    ):
        _fail("combined-frontier reserved Cloud Run runtime differs")
    return _with_hash({
        "schema_version": "corpus-r6-combined-frontier-runtime-authority/v1",
        "source_ordinal": int(index_text),
        "task_count": int(count_text),
        "task_attempt": 0,
        "execution_id": execution_id,
        "job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "manifest_identity": identity,
        "manifest_sha256": retained["manifest_sha256"],
        "code_commit": retained["code_commit"],
        "image_digest": retained["image_digest"],
        "observed_command": command,
        "authority_source": "reserved-cloud-run-metadata-and-exact-process-command",
    }, field="runtime_authority_sha256")


def validate_runtime_authority_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> dict[str, object]:
    runtime = _mapping(value, label="combined-frontier runtime authority")
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="runtime manifest")
    expected_fields = {
        "schema_version", "source_ordinal", "task_count", "task_attempt",
        "execution_id", "job_name", "reused_job_uid", "project_id", "region",
        "manifest_identity", "manifest_sha256", "code_commit", "image_digest",
        "observed_command", "authority_source", "runtime_authority_sha256",
    }
    if (
        set(runtime) != expected_fields
        or runtime.get("schema_version")
        != "corpus-r6-combined-frontier-runtime-authority/v1"
        or runtime.get("runtime_authority_sha256")
        != _hash({
            key: row for key, row in runtime.items()
            if key != "runtime_authority_sha256"
        })
        or type(runtime.get("source_ordinal")) is not int
        or not 0 <= int(runtime["source_ordinal"]) < TASK_COUNT
        or runtime.get("task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or type(runtime.get("execution_id")) is not str
        or not runtime["execution_id"]
        or runtime.get("job_name") != FIXED_REUSED_JOB_NAME
        or runtime.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or runtime.get("project_id") != FIXED_PROJECT
        or runtime.get("region") != FIXED_REGION
        or runtime.get("manifest_identity") != identity
        or runtime.get("manifest_sha256") != retained["manifest_sha256"]
        or runtime.get("code_commit") != retained["code_commit"]
        or runtime.get("image_digest") != retained["image_digest"]
        or runtime.get("observed_command") != list(EXPECTED_COMMAND)
        or runtime.get("authority_source")
        != "reserved-cloud-run-metadata-and-exact-process-command"
    ):
        _fail("combined-frontier runtime authority differs")
    return runtime


def _reconstruct_predecessor_matrix_v1(
    *,
    manifest: Mapping[str, object],
    source_ordinal: int,
    store: object,
) -> tuple[dict[str, object], dict[str, object], np.ndarray]:
    terminal, terminal_identity = _open_predecessor_terminal(
        manifest["predecessor_terminal_identity"], store=store
    )
    if (
        terminal_identity != manifest["predecessor_terminal_identity"]
        or terminal["terminal_sha256"] != manifest["predecessor_terminal_sha256"]
        or terminal["task_manifest_identity"]
        != manifest["predecessor_task_manifest_identity"]
        or terminal["task_manifest_sha256"]
        != manifest["predecessor_task_manifest_sha256"]
        or terminal["later_source_identity"] != manifest["later_source_identity"]
    ):
        _fail("combined-frontier predecessor terminal binding differs")
    source_manifest, source_manifest_identity = prior_operator._open_manifest(
        terminal["task_manifest_identity"], store=store
    )
    if source_manifest_identity != manifest["predecessor_task_manifest_identity"]:
        _fail("combined-frontier predecessor manifest identity differs")
    binding = manifest["task_bindings"][source_ordinal]
    descriptor = terminal["task_results"][source_ordinal]
    if (
        descriptor["task_result_identity"]
        != binding["predecessor_task_result_identity"]
        or descriptor["task_result_sha256"]
        != binding["predecessor_task_result_sha256"]
        or descriptor["science_result_sha256"]
        != binding["predecessor_science_result_sha256"]
        or descriptor["union_lineup_count"]
        != binding["predecessor_union_lineup_count"]
    ):
        _fail("combined-frontier predecessor descriptor binding differs")
    predecessor_result, predecessor_identity = _read_json(
        binding["predecessor_task_result_identity"],
        store=store,
        label=f"predecessor task result[{source_ordinal}]",
        maximum_bytes=MAXIMUM_PREDECESSOR_TASK_BYTES,
    )
    try:
        retained_result = predecessor_execution.validate_task_result_v1(
            predecessor_result,
            manifest=source_manifest,
            manifest_identity=source_manifest_identity,
        )
    except predecessor_execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    source_binding = source_manifest["task_bindings"][source_ordinal]
    try:
        prepared, _profile_bodies, profile_source = crossed._load_task_sources_v1(
            source_binding["profile_source_request"],
            read_exact=store.read_exact,
        )
    except crossed.CorpusR6PopulationCrossedCloudV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    science = _mapping(
        retained_result["science_result"], label="predecessor science result"
    )
    matrix_binding = _mapping(
        science["matrix_binding"], label="predecessor matrix binding"
    )
    union = _mapping(science["union"], label="predecessor union")
    union_rows = [
        _mapping(row, label="predecessor union lineup")
        for row in _sequence(union["union_lineups"], label="union lineups")
    ]
    player_rows = tuple(prepared.players)
    player_ids = [str(getattr(player, "player_id", "")) for player in player_rows]
    if (
        predecessor_identity != binding["predecessor_task_result_identity"]
        or retained_result["source_ordinal"] != source_ordinal
        or retained_result["task_result_sha256"]
        != binding["predecessor_task_result_sha256"]
        or retained_result["science_result_sha256"]
        != binding["predecessor_science_result_sha256"]
        or retained_result["slate_id"] != binding["slate_id"]
        or prepared.slate_id != binding["slate_id"]
        or profile_source["later_source_identity"] != manifest["later_source_identity"]
        or matrix_binding["player_ids_sha256"] != _hash(player_ids)
        or union["union_lineup_count"] != len(union_rows)
        or union["union_lineup_count"]
        != binding["predecessor_union_lineup_count"]
    ):
        _fail("combined-frontier predecessor/source replay binding differs")
    try:
        scores = cross_score_full_union(
            player_rows,
            prepared.player_draws,
            [row["roster_player_ids"] for row in union_rows],
            expected_worlds=int(matrix_binding["shape"][1]),
        )
    except Exception as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(
            f"combined-frontier matrix reconstruction failed: {exc}"
        ) from exc
    if (
        scores.dtype != np.dtype(np.float64)
        or not scores.flags.c_contiguous
        or list(scores.shape) != matrix_binding["shape"]
        or not np.isfinite(scores).all()
        or predecessor_science._score_matrix_sha256(scores)
        != matrix_binding["score_matrix_sha256"]
    ):
        _fail("combined-frontier reconstructed predecessor matrix differs")
    return retained_result, predecessor_identity, scores


def build_task_result_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
    runtime_authority: Mapping[str, object],
    predecessor_task_result: Mapping[str, object],
    predecessor_task_result_identity: object,
    all_block_score_matrix: np.ndarray,
) -> dict[str, object]:
    retained_manifest = validate_manifest_v1(manifest)
    retained_identity = _identity(manifest_identity, label="task manifest")
    runtime = validate_runtime_authority_v1(
        runtime_authority,
        manifest=retained_manifest,
        manifest_identity=retained_identity,
    )
    ordinal = int(runtime["source_ordinal"])
    binding = retained_manifest["task_bindings"][ordinal]
    predecessor_identity = _identity(
        predecessor_task_result_identity, label="predecessor task result"
    )
    predecessor_result = _mapping(
        predecessor_task_result, label="predecessor task result"
    )
    if (
        predecessor_identity != binding["predecessor_task_result_identity"]
        or predecessor_result.get("task_result_sha256")
        != binding["predecessor_task_result_sha256"]
        or predecessor_result.get("science_result_sha256")
        != binding["predecessor_science_result_sha256"]
    ):
        _fail("combined-frontier task predecessor binding differs")
    try:
        result = frontier.run_combined_frontier_reportfolio_v1(
            combined_result=predecessor_result["science_result"],
            all_block_score_matrix=all_block_score_matrix,
            source_ordinal=ordinal,
        )
        normalized = frontier.normalized_slate_for_grader_v1(
            result, source_ordinal=ordinal
        )
    except frontier.CorpusR6CombinedFrontierReportfolioV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    if (
        normalized["slate_id"] != binding["slate_id"]
        or normalized["later_source_identity"]
        != retained_manifest["later_source_identity"]
        or len(normalized["books"]) != BOOK_COUNT_PER_SLATE
    ):
        _fail("combined-frontier normalized task surface differs")
    body = {
        "schema_version": TASK_RESULT_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "source_ordinal": ordinal,
        "slate_id": normalized["slate_id"],
        "manifest_identity": retained_identity,
        "manifest_sha256": retained_manifest["manifest_sha256"],
        "task_binding_sha256": binding["task_binding_sha256"],
        "runtime_authority": runtime,
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "predecessor_task_result_identity": predecessor_identity,
        "predecessor_task_result_sha256": predecessor_result[
            "task_result_sha256"
        ],
        "predecessor_science_result_sha256": predecessor_result[
            "science_result_sha256"
        ],
        "frontier_result": result,
        "frontier_result_sha256": result["result_sha256"],
        "normalized_slate_sha256": _hash(normalized),
        "book_count": len(normalized["books"]),
        "entry_budgets": list(ENTRY_BUDGETS),
        "predecessor_matrix_exact_sha_verified": True,
        "predecessor_populations_reused": True,
        "predecessor_eight_selectors_rerun": False,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "promotion_authority": False,
        "production_change_licensed": False,
        "complete": True,
    }
    return _with_hash(body, field="task_result_sha256")


def validate_task_result_v1(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    result = _mapping(value, label="combined-frontier task result")
    retained_manifest = validate_manifest_v1(manifest)
    retained_identity = _identity(manifest_identity, label="task manifest")
    expected_fields = {
        "schema_version", "adapter_id", "source_ordinal", "slate_id",
        "manifest_identity", "manifest_sha256", "task_binding_sha256",
        "runtime_authority", "runtime_authority_sha256",
        "predecessor_task_result_identity", "predecessor_task_result_sha256",
        "predecessor_science_result_sha256", "frontier_result",
        "frontier_result_sha256", "normalized_slate_sha256", "book_count",
        "entry_budgets", "predecessor_matrix_exact_sha_verified",
        "predecessor_populations_reused", "predecessor_eight_selectors_rerun",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "descriptive_only", "promotion_authority",
        "production_change_licensed", "complete", "task_result_sha256",
    }
    ordinal = result.get("source_ordinal")
    if type(ordinal) is not int or not 0 <= ordinal < TASK_COUNT:
        _fail("combined-frontier task result source ordinal differs")
    binding = retained_manifest["task_bindings"][ordinal]
    runtime = validate_runtime_authority_v1(
        result.get("runtime_authority"),
        manifest=retained_manifest,
        manifest_identity=retained_identity,
    )
    try:
        normalized = frontier.normalized_slate_for_grader_v1(
            result.get("frontier_result"), source_ordinal=ordinal
        )
    except frontier.CorpusR6CombinedFrontierReportfolioV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    if (
        set(result) != expected_fields
        or result.get("schema_version") != TASK_RESULT_SCHEMA
        or result.get("adapter_id") != ADAPTER_ID
        or result.get("task_result_sha256")
        != _hash({
            key: row for key, row in result.items()
            if key != "task_result_sha256"
        })
        or runtime["source_ordinal"] != ordinal
        or result.get("slate_id") != binding["slate_id"]
        or normalized["slate_id"] != binding["slate_id"]
        or normalized["later_source_identity"]
        != retained_manifest["later_source_identity"]
        or result.get("manifest_identity") != retained_identity
        or result.get("manifest_sha256") != retained_manifest["manifest_sha256"]
        or result.get("task_binding_sha256") != binding["task_binding_sha256"]
        or result.get("runtime_authority_sha256")
        != runtime["runtime_authority_sha256"]
        or result.get("predecessor_task_result_identity")
        != binding["predecessor_task_result_identity"]
        or result.get("predecessor_task_result_sha256")
        != binding["predecessor_task_result_sha256"]
        or result.get("predecessor_science_result_sha256")
        != binding["predecessor_science_result_sha256"]
        or result.get("frontier_result_sha256")
        != _mapping(result.get("frontier_result"), label="frontier result").get(
            "result_sha256"
        )
        or result.get("normalized_slate_sha256") != _hash(normalized)
        or result.get("book_count") != BOOK_COUNT_PER_SLATE
        or result.get("entry_budgets") != list(ENTRY_BUDGETS)
        or result.get("predecessor_matrix_exact_sha_verified") is not True
        or result.get("predecessor_populations_reused") is not True
        or result.get("predecessor_eight_selectors_rerun") is not False
        or result.get("population_regeneration_performed") is not False
        or result.get("outcome_columns_read") != []
        or result.get("uses_realized_outcomes") is not False
        or result.get("descriptive_only") is not True
        or result.get("promotion_authority") is not False
        or result.get("production_change_licensed") is not False
        or result.get("complete") is not True
    ):
        _fail("combined-frontier task result fixed law differs")
    return result, normalized


def execute_task_v1(
    *,
    manifest_identity: object,
    runtime_authority: Mapping[str, object],
    store: object,
) -> dict[str, object]:
    manifest, retained_manifest_identity = _open_manifest(
        manifest_identity, store=store
    )
    runtime = validate_runtime_authority_v1(
        runtime_authority,
        manifest=manifest,
        manifest_identity=retained_manifest_identity,
    )
    ordinal = int(runtime["source_ordinal"])
    predecessor_result, predecessor_identity, scores = (
        _reconstruct_predecessor_matrix_v1(
            manifest=manifest, source_ordinal=ordinal, store=store
        )
    )
    result = build_task_result_v1(
        manifest=manifest,
        manifest_identity=retained_manifest_identity,
        runtime_authority=runtime,
        predecessor_task_result=predecessor_result,
        predecessor_task_result_identity=predecessor_identity,
        all_block_score_matrix=scores,
    )
    result_identity = _publish_json(
        uri=str(manifest["task_bindings"][ordinal]["result_uri"]),
        value=result,
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-frontier-reportfolio-task-completion/v1",
        "source_ordinal": ordinal,
        "slate_id": result["slate_id"],
        "execution_id": runtime["execution_id"],
        "task_result_identity": result_identity,
        "task_result_sha256": result["task_result_sha256"],
        "book_count": BOOK_COUNT_PER_SLATE,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _smoke_analysis_v1(
    *,
    predecessor_result: Mapping[str, object],
    predecessor_identity: Mapping[str, object],
    scores: np.ndarray,
    expected_slate_id: str,
    expected_later_source_identity: Mapping[str, object],
    expected_complete_union_count: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    try:
        result = frontier.run_combined_frontier_reportfolio_v1(
            combined_result=predecessor_result["science_result"],
            all_block_score_matrix=scores,
            source_ordinal=0,
        )
        normalized = frontier.normalized_slate_for_grader_v1(
            result, source_ordinal=0
        )
    except frontier.CorpusR6CombinedFrontierReportfolioV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    sieve = _mapping(result.get("frontier"), label="smoke sieve result")
    full_count = sieve.get("complete_union_lineup_count")
    sieve_count = sieve.get("candidate_count")
    prior_count = sieve.get("prior_eight_book_union_count")
    overlap_count = sieve.get("candidate_in_prior_eight_books_count")
    novel_count = sieve.get("candidate_absent_from_prior_eight_books_count")
    if (
        normalized["slate_id"] != expected_slate_id
        or normalized["later_source_identity"]
        != expected_later_source_identity
        or len(normalized["books"]) != BOOK_COUNT_PER_SLATE
        or sieve.get("shortlist_law") != frontier.SIEVE_LAW
        or sieve.get("old_book_membership_used_for_sieve") is not False
        or full_count != expected_complete_union_count
        or type(full_count) is not int
        or full_count <= frontier.SIEVE_LIMIT
        or sieve_count != frontier.SIEVE_LIMIT
        or type(prior_count) is not int
        or type(overlap_count) is not int
        or type(novel_count) is not int
        or overlap_count + novel_count != frontier.SIEVE_LIMIT
        or novel_count <= 0
    ):
        _fail("combined-frontier smoke normalized binding differs")
    receipt = {
        "source_ordinal": 0,
        "slate_id": normalized["slate_id"],
        "predecessor_task_result_identity": predecessor_identity,
        "predecessor_task_result_sha256": predecessor_result[
            "task_result_sha256"
        ],
        "predecessor_score_matrix_sha256": predecessor_result[
            "science_result"
        ]["matrix_binding"]["score_matrix_sha256"],
        "frontier_result_sha256": result["result_sha256"],
        "complete_union_lineup_count": full_count,
        "complete_union_lineup_ids_sha256": sieve[
            "complete_union_lineup_ids_sha256"
        ],
        "complete_union_sieve_evidence_sha256": sieve[
            "complete_union_sieve_evidence_sha256"
        ],
        "complete_union_modeled_world_mean_vector_payload_sha256": sieve[
            "complete_union_modeled_world_mean_vector_payload_sha256"
        ],
        "complete_union_modeled_world_mean_vector_binding_sha256": sieve[
            "complete_union_modeled_world_mean_vector_binding_sha256"
        ],
        "candidate_sieve_law": sieve["shortlist_law"],
        "candidate_sieve_count": sieve_count,
        "candidate_lineup_ids_sha256": sieve["candidate_lineup_ids_sha256"],
        "candidate_sieve_evidence_sha256": sieve[
            "candidate_sieve_evidence_sha256"
        ],
        "prior_eight_book_union_count": prior_count,
        "prior_eight_book_union_lineup_ids_sha256": sieve[
            "prior_eight_book_union_lineup_ids_sha256"
        ],
        "candidate_in_prior_eight_books_count": overlap_count,
        "candidate_absent_from_prior_eight_books_count": novel_count,
        "source_books_sha256": sieve["source_books_sha256"],
        "selector_ids": [
            selector["strategy_id"] for selector in result["selectors"]
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": len(normalized["books"]),
        "predecessor_matrix_exact_sha_verified": True,
        "complete_union_candidate_source": True,
        "old_book_membership_used_for_sieve": False,
        "predecessor_populations_reused": True,
        "predecessor_eight_selectors_rerun": False,
        "publication_performed": False,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }
    return result, normalized, receipt


def preflight_smoke_from_request_v1(
    request: object, *, store: object
) -> dict[str, object]:
    """Run task 0 from the predecessor terminal before any build freeze."""
    item = _mapping(request, label="combined-frontier preflight smoke request")
    if set(item) != {"predecessor_terminal_identity"}:
        _fail("combined-frontier preflight smoke request fields differ")
    terminal, terminal_identity = _open_predecessor_terminal(
        item["predecessor_terminal_identity"], store=store
    )
    descriptor = _mapping(
        terminal["task_results"][0], label="preflight predecessor descriptor[0]"
    )
    binding = {
        "slate_id": descriptor["slate_id"],
        "predecessor_task_result_identity": descriptor["task_result_identity"],
        "predecessor_task_result_sha256": descriptor["task_result_sha256"],
        "predecessor_science_result_sha256": descriptor[
            "science_result_sha256"
        ],
        "predecessor_union_lineup_count": descriptor["union_lineup_count"],
    }
    predecessor_view = {
        "predecessor_terminal_identity": terminal_identity,
        "predecessor_terminal_sha256": terminal["terminal_sha256"],
        "predecessor_task_manifest_identity": terminal["task_manifest_identity"],
        "predecessor_task_manifest_sha256": terminal["task_manifest_sha256"],
        "later_source_identity": terminal["later_source_identity"],
        "task_bindings": [binding],
    }
    predecessor_result, predecessor_identity, scores = (
        _reconstruct_predecessor_matrix_v1(
            manifest=predecessor_view, source_ordinal=0, store=store
        )
    )
    if predecessor_identity != binding["predecessor_task_result_identity"]:
        _fail("combined-frontier preflight predecessor identity differs")
    _result, _normalized, receipt = _smoke_analysis_v1(
        predecessor_result=predecessor_result,
        predecessor_identity=predecessor_identity,
        scores=scores,
        expected_slate_id=str(binding["slate_id"]),
        expected_later_source_identity=terminal["later_source_identity"],
        expected_complete_union_count=int(binding["predecessor_union_lineup_count"]),
    )
    return _with_hash({
        "schema_version": (
            "corpus-r6-combined-frontier-real-artifact-preflight-smoke/v1"
        ),
        "predecessor_terminal_identity": terminal_identity,
        "predecessor_terminal_sha256": terminal["terminal_sha256"],
        **receipt,
    }, field="smoke_sha256")


def smoke_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    """Run one manifest-bound outcome-blind task-0 smoke without publication."""
    item = _mapping(request, label="combined-frontier smoke request")
    if set(item) != {"manifest_identity"}:
        _fail("combined-frontier smoke request fields differ")
    manifest, manifest_identity = _open_manifest(
        item["manifest_identity"], store=store
    )
    predecessor_result, predecessor_identity, scores = (
        _reconstruct_predecessor_matrix_v1(
            manifest=manifest, source_ordinal=0, store=store
        )
    )
    binding = manifest["task_bindings"][0]
    if predecessor_identity != binding["predecessor_task_result_identity"]:
        _fail("combined-frontier smoke predecessor identity differs")
    _result, _normalized, receipt = _smoke_analysis_v1(
        predecessor_result=predecessor_result,
        predecessor_identity=predecessor_identity,
        scores=scores,
        expected_slate_id=str(binding["slate_id"]),
        expected_later_source_identity=manifest["later_source_identity"],
        expected_complete_union_count=int(binding["predecessor_union_lineup_count"]),
    )
    return _with_hash({
        "schema_version": "corpus-r6-combined-frontier-real-artifact-smoke/v1",
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        **receipt,
    }, field="smoke_sha256")


def _open_all_task_results(
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    store: object,
) -> tuple[
    list[tuple[dict[str, object], dict[str, object]]],
    tuple[dict[str, object], ...],
]:
    pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    normalized: list[dict[str, object]] = []
    for ordinal, binding in enumerate(manifest["task_bindings"]):
        body, identity = _open_known_json(
            str(binding["result_uri"]),
            store=store,
            label=f"combined-frontier task result[{ordinal}]",
            maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
        result, slate = validate_task_result_v1(
            body, manifest=manifest, manifest_identity=manifest_identity
        )
        if result["source_ordinal"] != ordinal:
            _fail(f"combined-frontier result[{ordinal}] ordinal differs")
        pairs.append((result, identity))
        normalized.append(slate)
    try:
        retained = grader.validate_external_normalized_terminal_v1(
            adapter_id=ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    return pairs, retained


def collect_from_request_v1(
    request: object, *, store: object, provider: object
) -> dict[str, object]:
    item = _mapping(request, label="combined-frontier collect request")
    if set(item) != {"manifest_identity", "execution_id"}:
        _fail("combined-frontier collect request fields differ")
    manifest, manifest_identity = _open_manifest(
        item["manifest_identity"], store=store
    )
    provider_terminal = status_existing_execution_v1(
        manifest_identity=manifest_identity,
        execution_id=str(item["execution_id"]),
        store=store,
        provider=provider,
    )
    if provider_terminal["execution_id"] != item["execution_id"]:
        _fail("combined-frontier collect execution ID differs")
    pairs, normalized = _open_all_task_results(
        manifest=manifest, manifest_identity=manifest_identity, store=store
    )
    execution_ids = {
        str(result["runtime_authority"]["execution_id"])
        for result, _identity_value in pairs
    }
    if execution_ids != {str(provider_terminal["execution_id"])}:
        _fail("combined-frontier task/provider execution IDs differ")
    execution_id = next(iter(execution_ids))
    surface = _with_hash({
        "schema_version": NORMALIZED_SURFACE_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "predecessor_terminal_identity": manifest[
            "predecessor_terminal_identity"
        ],
        "predecessor_terminal_sha256": manifest[
            "predecessor_terminal_sha256"
        ],
        "later_source_identity": manifest["later_source_identity"],
        "execution_id": execution_id,
        "provider_terminal_execution_sha256": provider_terminal[
            "provider_terminal_execution_sha256"
        ],
        "source_slate_count": TASK_COUNT,
        "book_count_per_slate": BOOK_COUNT_PER_SLATE,
        "entry_budgets": list(ENTRY_BUDGETS),
        "slates": list(normalized),
        "slates_sha256": _hash(list(normalized)),
        "public_external_normalized_boundary_validated": True,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "promotion_authority": False,
        "production_change_licensed": False,
        "complete": True,
    }, field="normalized_surface_sha256")
    surface_identity = _publish_json(
        uri=str(manifest["normalized_surface_uri"]),
        value=surface,
        maximum_bytes=MAXIMUM_NORMALIZED_SURFACE_BYTES,
        store=store,
    )
    descriptors = [{
        "source_ordinal": ordinal,
        "slate_id": result["slate_id"],
        "task_result_identity": identity,
        "task_result_sha256": result["task_result_sha256"],
        "frontier_result_sha256": result["frontier_result_sha256"],
        "normalized_slate_sha256": result["normalized_slate_sha256"],
    } for ordinal, (result, identity) in enumerate(pairs)]
    terminal = _with_hash({
        "schema_version": TERMINAL_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "predecessor_terminal_identity": manifest[
            "predecessor_terminal_identity"
        ],
        "predecessor_terminal_sha256": manifest[
            "predecessor_terminal_sha256"
        ],
        "later_source_identity": manifest["later_source_identity"],
        "output_prefix": manifest["output_prefix"],
        "terminal_uri": manifest["terminal_uri"],
        "execution_id": execution_id,
        "provider_terminal_execution": provider_terminal,
        "provider_terminal_execution_sha256": provider_terminal[
            "provider_terminal_execution_sha256"
        ],
        "source_slate_count": TASK_COUNT,
        "book_count_per_slate": BOOK_COUNT_PER_SLATE,
        "task_results": descriptors,
        "task_results_sha256": _hash(descriptors),
        "normalized_surface_identity": surface_identity,
        "normalized_surface_sha256": surface["normalized_surface_sha256"],
        "all_task_results_exact_opened_before_terminal": True,
        "provider_exact_54_of_54_terminal_validated_before_terminal": True,
        "public_external_normalized_boundary_validated_before_terminal": True,
        "terminal_published_after_normalized_surface": True,
        "predecessor_populations_reused": True,
        "predecessor_eight_selectors_rerun": False,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "promotion_authority": False,
        "production_change_licensed": False,
        "complete": True,
    }, field="terminal_sha256")
    terminal_identity = _publish_json(
        uri=str(manifest["terminal_uri"]),
        value=terminal,
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-frontier-reportfolio-collect-result/v1",
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "normalized_surface_identity": surface_identity,
        "normalized_surface_sha256": surface["normalized_surface_sha256"],
        "source_slate_count": TASK_COUNT,
        "aggregate_book_count": TASK_COUNT * BOOK_COUNT_PER_SLATE,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _reopen_terminal_and_surface_v1(
    identity_value: object, *, store: object, reopen_task_results: bool
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    tuple[dict[str, object], ...],
]:
    terminal, terminal_identity = _read_json(
        identity_value,
        store=store,
        label="combined-frontier terminal",
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
    )
    manifest, manifest_identity = _open_manifest(
        terminal.get("manifest_identity"), store=store
    )
    descriptors = _sequence(terminal.get("task_results"), label="task results")
    expected_terminal_fields = {
        "schema_version", "adapter_id", "manifest_identity", "manifest_sha256",
        "predecessor_terminal_identity", "predecessor_terminal_sha256",
        "later_source_identity", "output_prefix", "terminal_uri", "execution_id",
        "provider_terminal_execution", "provider_terminal_execution_sha256",
        "source_slate_count", "book_count_per_slate", "task_results",
        "task_results_sha256", "normalized_surface_identity",
        "normalized_surface_sha256", "all_task_results_exact_opened_before_terminal",
        "provider_exact_54_of_54_terminal_validated_before_terminal",
        "public_external_normalized_boundary_validated_before_terminal",
        "terminal_published_after_normalized_surface",
        "predecessor_populations_reused", "predecessor_eight_selectors_rerun",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "descriptive_only", "promotion_authority",
        "production_change_licensed", "complete", "terminal_sha256",
    }
    if (
        set(terminal) != expected_terminal_fields
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("adapter_id") != ADAPTER_ID
        or terminal.get("terminal_sha256")
        != _hash({
            key: row for key, row in terminal.items()
            if key != "terminal_sha256"
        })
        or terminal_identity["uri"] != manifest["terminal_uri"]
        or terminal.get("terminal_uri") != manifest["terminal_uri"]
        or terminal.get("manifest_identity") != manifest_identity
        or terminal.get("manifest_sha256") != manifest["manifest_sha256"]
        or terminal.get("predecessor_terminal_identity")
        != manifest["predecessor_terminal_identity"]
        or terminal.get("predecessor_terminal_sha256")
        != manifest["predecessor_terminal_sha256"]
        or terminal.get("later_source_identity") != manifest["later_source_identity"]
        or terminal.get("output_prefix") != manifest["output_prefix"]
        or terminal.get("provider_terminal_execution_sha256")
        != _mapping(
            terminal.get("provider_terminal_execution"),
            label="terminal provider proof",
        ).get("provider_terminal_execution_sha256")
        or terminal.get("source_slate_count") != TASK_COUNT
        or terminal.get("book_count_per_slate") != BOOK_COUNT_PER_SLATE
        or len(descriptors) != TASK_COUNT
        or terminal.get("task_results_sha256") != _hash(descriptors)
        or terminal.get("all_task_results_exact_opened_before_terminal") is not True
        or terminal.get(
            "provider_exact_54_of_54_terminal_validated_before_terminal"
        ) is not True
        or terminal.get(
            "public_external_normalized_boundary_validated_before_terminal"
        ) is not True
        or terminal.get("terminal_published_after_normalized_surface") is not True
        or terminal.get("predecessor_populations_reused") is not True
        or terminal.get("predecessor_eight_selectors_rerun") is not False
        or terminal.get("population_regeneration_performed") is not False
        or terminal.get("outcome_columns_read") != []
        or terminal.get("uses_realized_outcomes") is not False
        or terminal.get("descriptive_only") is not True
        or terminal.get("promotion_authority") is not False
        or terminal.get("production_change_licensed") is not False
        or terminal.get("complete") is not True
    ):
        _fail("combined-frontier terminal fixed law differs")
    provider_terminal = validate_provider_terminal_execution_v1(
        terminal["provider_terminal_execution"],
        manifest=manifest,
        manifest_identity=manifest_identity,
    )
    if (
        provider_terminal["provider_terminal_execution_sha256"]
        != terminal["provider_terminal_execution_sha256"]
        or provider_terminal["execution_id"] != terminal["execution_id"]
    ):
        _fail("combined-frontier terminal provider proof binding differs")
    surface, surface_identity = _read_json(
        terminal["normalized_surface_identity"],
        store=store,
        label="combined-frontier normalized surface",
        maximum_bytes=MAXIMUM_NORMALIZED_SURFACE_BYTES,
    )
    surface_body = {
        key: row for key, row in surface.items()
        if key != "normalized_surface_sha256"
    }
    expected_surface_fields = {
        "schema_version", "adapter_id", "manifest_identity", "manifest_sha256",
        "predecessor_terminal_identity", "predecessor_terminal_sha256",
        "later_source_identity", "execution_id",
        "provider_terminal_execution_sha256", "source_slate_count",
        "book_count_per_slate", "entry_budgets", "slates", "slates_sha256",
        "public_external_normalized_boundary_validated",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "descriptive_only", "promotion_authority",
        "production_change_licensed", "complete", "normalized_surface_sha256",
    }
    if (
        set(surface) != expected_surface_fields
        or surface_identity != terminal["normalized_surface_identity"]
        or surface_identity["uri"] != manifest["normalized_surface_uri"]
        or surface.get("schema_version") != NORMALIZED_SURFACE_SCHEMA
        or surface.get("adapter_id") != ADAPTER_ID
        or surface.get("normalized_surface_sha256") != _hash(surface_body)
        or surface.get("normalized_surface_sha256")
        != terminal["normalized_surface_sha256"]
        or surface.get("manifest_identity") != manifest_identity
        or surface.get("manifest_sha256") != manifest["manifest_sha256"]
        or surface.get("predecessor_terminal_identity")
        != manifest["predecessor_terminal_identity"]
        or surface.get("predecessor_terminal_sha256")
        != manifest["predecessor_terminal_sha256"]
        or surface.get("later_source_identity") != manifest["later_source_identity"]
        or surface.get("execution_id") != terminal["execution_id"]
        or surface.get("provider_terminal_execution_sha256")
        != terminal["provider_terminal_execution_sha256"]
        or surface.get("source_slate_count") != TASK_COUNT
        or surface.get("book_count_per_slate") != BOOK_COUNT_PER_SLATE
        or surface.get("entry_budgets") != list(ENTRY_BUDGETS)
        or len(_sequence(surface.get("slates"), label="normalized slates"))
        != TASK_COUNT
        or surface.get("slates_sha256") != _hash(surface.get("slates"))
        or surface.get("public_external_normalized_boundary_validated") is not True
        or surface.get("population_regeneration_performed") is not False
        or surface.get("outcome_columns_read") != []
        or surface.get("uses_realized_outcomes") is not False
        or surface.get("descriptive_only") is not True
        or surface.get("promotion_authority") is not False
        or surface.get("production_change_licensed") is not False
        or surface.get("complete") is not True
    ):
        _fail("combined-frontier normalized surface differs")
    try:
        normalized = grader.validate_external_normalized_terminal_v1(
            adapter_id=ADAPTER_ID, slates=surface["slates"]
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(str(exc)) from exc
    if reopen_task_results:
        pairs, result_normalized = _open_all_task_results(
            manifest=manifest, manifest_identity=manifest_identity, store=store
        )
        expected_descriptors = [{
            "source_ordinal": ordinal,
            "slate_id": result["slate_id"],
            "task_result_identity": identity,
            "task_result_sha256": result["task_result_sha256"],
            "frontier_result_sha256": result["frontier_result_sha256"],
            "normalized_slate_sha256": result["normalized_slate_sha256"],
        } for ordinal, (result, identity) in enumerate(pairs)]
        if (
            expected_descriptors != descriptors
            or _canonical(result_normalized) != _canonical(normalized)
            or {
                str(result["runtime_authority"]["execution_id"])
                for result, _identity_value in pairs
            } != {str(provider_terminal["execution_id"])}
        ):
            _fail("combined-frontier terminal exact task replay differs")
    return terminal, terminal_identity, manifest, normalized


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="combined-frontier grade request")
    if set(item) != {"terminal_identity", "outcome_snapshot_identity"}:
        _fail("combined-frontier grade request fields differ")
    terminal, terminal_identity, manifest, normalized = (
        _reopen_terminal_and_surface_v1(
            item["terminal_identity"], store=store, reopen_task_results=True
        )
    )
    snapshot, snapshot_identity, player_scores, slate_keys = (
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            read_outcome_exact=store.read_exact,
        )
    )
    if (
        snapshot.get("later_source_freeze_identity")
        != terminal["later_source_identity"]
        or set(slate_keys) != set(range(TASK_COUNT))
        or any(
            slate_keys[ordinal][2] != normalized[ordinal]["slate_id"]
            for ordinal in range(TASK_COUNT)
        )
    ):
        _fail("combined-frontier terminal/outcome source or slate binding differs")
    slate_grades = grader.score_normalized_slates_v1(
        slates=normalized, player_scores=player_scores
    )
    aggregates = grader.aggregate_normalized_slate_grades_v1(slate_grades)
    grade = _with_hash({
        "schema_version": GRADE_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "normalized_surface_identity": terminal["normalized_surface_identity"],
        "normalized_surface_sha256": terminal["normalized_surface_sha256"],
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "later_source_identity": terminal["later_source_identity"],
        "source_slate_count": TASK_COUNT,
        "book_count_per_slate": BOOK_COUNT_PER_SLATE,
        "slate_grades": slate_grades,
        "slate_grades_sha256": _hash(slate_grades),
        "aggregate_cells": aggregates,
        "aggregate_cells_sha256": _hash(aggregates),
        "score_free_terminal_and_all_task_results_validated_before_outcome_open": True,
        "population_regeneration_performed": False,
        "descriptive_only": True,
        "promotion_authority": False,
        "production_change_licensed": False,
        "complete": True,
    }, field="grade_sha256")
    grade_identity = _publish_json(
        uri=str(manifest["descriptive_grade_uri"]),
        value=grade,
        maximum_bytes=MAXIMUM_GRADE_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-frontier-reportfolio-grade-result/v1",
        "grade_identity": grade_identity,
        "grade_sha256": grade["grade_sha256"],
        "aggregate_cell_count": len(aggregates),
        "source_slate_count": TASK_COUNT,
        "descriptive_only": True,
        "promotion_authority": False,
        "production_change_licensed": False,
        "complete": True,
    }


def _load_request(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be one existing absolute file")
    return _strict_json(
        path.read_bytes(), label=label, maximum_bytes=MAXIMUM_REQUEST_BYTES
    )


def _manifest_identity_from_environment() -> dict[str, object]:
    raw = os.environ.get(MANIFEST_IDENTITY_ENV, "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunCorpusR6CombinedFrontierReportfolioV1Error(
            "combined-frontier manifest identity environment is not JSON"
        ) from exc
    identity = _identity(parsed, label="runtime manifest")
    if raw.encode("utf-8") != _canonical(identity):
        _fail("runtime manifest identity environment is not canonical JSON")
    return identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (
        "preflight-smoke", "prepare", "smoke", "configure", "launch",
        "status", "collect", "grade",
    ):
        child = commands.add_parser(command)
        child.add_argument("--request", type=Path, required=True)
        child.add_argument("--execute", action="store_true")
    task = commands.add_parser("task")
    task.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute or os.environ.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail(
            f"execution requires --execute and {ENABLE_ENV}={ENABLE_VALUE}"
        )
    store = prior_operator.GCSExactTransportV1()
    if args.command == "preflight-smoke":
        result = preflight_smoke_from_request_v1(
            _load_request(args.request, label="preflight smoke request"),
            store=store,
        )
    elif args.command == "prepare":
        result = prepare_from_request_v1(
            _load_request(args.request, label="prepare request"), store=store
        )
    elif args.command == "smoke":
        result = smoke_from_request_v1(
            _load_request(args.request, label="smoke request"), store=store
        )
    elif args.command == "configure":
        request = _load_request(args.request, label="configure request")
        if set(request) != {"manifest_identity"}:
            _fail("combined-frontier configure request fields differ")
        result = configure_existing_job_v1(
            manifest_identity=request["manifest_identity"],
            store=store,
            provider=prior_operator.GCloudRunProviderV1(),
        )
    elif args.command == "launch":
        request = _load_request(args.request, label="launch request")
        if set(request) != {"manifest_identity"}:
            _fail("combined-frontier launch request fields differ")
        result = launch_existing_job_v1(
            manifest_identity=request["manifest_identity"],
            store=store,
            provider=prior_operator.GCloudRunProviderV1(),
        )
    elif args.command == "status":
        request = _load_request(args.request, label="status request")
        if set(request) != {"manifest_identity", "execution_id"}:
            _fail("combined-frontier status request fields differ")
        result = status_existing_execution_v1(
            manifest_identity=request["manifest_identity"],
            execution_id=str(request["execution_id"]),
            store=store,
            provider=prior_operator.GCloudRunProviderV1(),
        )
    elif args.command == "task":
        manifest_identity = _manifest_identity_from_environment()
        manifest, retained_identity = _open_manifest(
            manifest_identity, store=store
        )
        runtime = build_runtime_authority_v1(
            manifest=manifest,
            manifest_identity=retained_identity,
            environment=os.environ,
            observed_command=_observed_command_v1(),
        )
        result = execute_task_v1(
            manifest_identity=retained_identity,
            runtime_authority=runtime,
            store=store,
        )
    elif args.command == "collect":
        result = collect_from_request_v1(
            _load_request(args.request, label="collect request"),
            store=store,
            provider=prior_operator.GCloudRunProviderV1(),
        )
    elif args.command == "grade":
        result = grade_from_request_v1(
            _load_request(args.request, label="grade request"), store=store
        )
    else:  # pragma: no cover - argparse owns the command registry.
        _fail("unknown combined-frontier command")
    sys.stdout.buffer.write(_canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6CombinedFrontierReportfolioV1Error,
        prior_operator.RunCorpusR6CombinedPopulationAllBlockV1Error,
        predecessor_execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error,
        frontier.CorpusR6CombinedFrontierReportfolioV1Error,
        grader.CorpusR6NovelRosterRealizedGraderV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
