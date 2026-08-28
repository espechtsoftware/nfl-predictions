"""Thin 54-slate cloud path for crossing F7/F8/F9 with retrieval laws.

The population challenger publishes three immutable lineup objects per slate.
Those objects are not members of the current-bank candidate universe, so they
cannot truthfully pass through the current-bank successor task manifest.  This
module supplies the smallest distinct authority: one task per slate exact-opens
the three population objects, reconstructs the shared five-block draw bank,
builds five outcome-blind fold plans, and runs the already-frozen grouped,
rank-150, and DPP selectors.

The published result carries no held-out score values.  It binds the sampled
rosters, fit-only selector outputs, held-out matrix digest, and all immutable
source identities needed by a later evaluator to reconstruct the held-out rows.
No realized outcome is read anywhere in this boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as source_manifest,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as population_authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as population_runtime,
)
from nfl_dfs.research import (
    corpus_r6_population_crossed_scoring_v1 as crossed,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import residual_world_columns as rw


TASK_MANIFEST_SCHEMA: Final = "corpus-r6-population-crossed-task-manifest/v1"
TASK_BINDING_SCHEMA: Final = "corpus-r6-population-crossed-task-binding/v1"
TASK_REQUEST_SCHEMA: Final = "corpus-r6-population-crossed-task-request/v1"
SLATE_RESULT_SCHEMA: Final = "corpus-r6-population-crossed-slate-result/v1"
FOLD_RESULT_SCHEMA: Final = "corpus-r6-population-crossed-fold-result/v1"
PROFILE_RESULT_SCHEMA: Final = "corpus-r6-population-crossed-profile-result/v1"
TASK_COMPLETION_SCHEMA: Final = "corpus-r6-population-crossed-task-completion/v1"
PREPARATION_SCHEMA: Final = "corpus-r6-population-crossed-preparation/v1"
JOB_CONFIGURATION_SCHEMA: Final = (
    "corpus-r6-population-crossed-cloud-run-job-configuration/v1"
)

TASK_COUNT: Final = population_authority.TASK_COUNT
FOLD_COUNT: Final = len(rw.WORLD_BLOCKS)
PROFILE_COUNT: Final = len(profiles.PROFILE_ORDER)
SELECTORS_PER_PROFILE_FOLD: Final = 7
SELECTOR_CELLS_PER_SLATE: Final = (
    FOLD_COUNT * PROFILE_COUNT * SELECTORS_PER_PROFILE_FOLD
)

FIXED_GCP_PROJECT: Final = population_authority.FIXED_GCP_PROJECT
FIXED_STORAGE_ENDPOINT: Final = population_authority.FIXED_STORAGE_ENDPOINT
DISPATCHER_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_population_crossed_cloud_v1.py"
)
DISPATCHER_IMAGE_PATH: Final = f"/app/{DISPATCHER_RELATIVE_PATH}"
DISPATCHER_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    DISPATCHER_IMAGE_PATH,
    "task",
)
MANIFEST_IDENTITY_ENV: Final = "R6_POPULATION_CROSSED_MANIFEST_IDENTITY"
ENABLE_ENV: Final = "R6_POPULATION_CROSSED_ENABLE"

MAXIMUM_POPULATION_MANIFEST_BYTES: Final = 16_000_000
MAXIMUM_POPULATION_TASK_RESULT_BYTES: Final = (
    population_authority.MAXIMUM_TASK_RESULT_BYTES
)
MAXIMUM_PROFILE_LINEUPS_BYTES: Final = (
    population_authority.MAXIMUM_PROFILE_LINEUPS_BYTES
)
MAXIMUM_TASK_MANIFEST_BYTES: Final = 16_000_000
MAXIMUM_SLATE_RESULT_BYTES: Final = 256_000_000
MAXIMUM_TASK_COMPLETION_BYTES: Final = 256_000
TASK_TIMEOUT_SECONDS: Final = 7_200

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_DIGEST_RE: Final = re.compile(r"sha256:[0-9a-f]{64}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")

_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "heldout_scores_available_to_selectors": False,
    "equal_count_across_population_profiles": True,
    "one_reused_job_for_all_slates": True,
    "production_default_change_licensed": False,
    "promotion_authority": False,
}

_SELECTOR_LATTICE: Final = {
    "grouped_native_per_profile_fold": 3,
    "exact_rank150_per_profile_fold": 3,
    "dpp_per_profile_fold": 1,
    "entry_budgets": [4, 14, 80, 100, 150],
}


class CorpusR6PopulationCrossedCloudV1Error(ValueError):
    """The population-crossed cloud authority failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6PopulationCrossedCloudV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return population_authority.canonical_bytes_v1(value)
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: _hash(body)}


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return population_authority.object_identity_v1(value, label=label)
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _bind(
    value: Mapping[str, object], identity: object, *, label: str
) -> dict[str, object]:
    try:
        return population_authority.bind_body_to_identity_v1(
            value, identity, label=label
        )
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _read_json(
    identity: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        return population_authority.exact_read_json_v1(
            identity,
            read_exact=read_exact,
            label=label,
            maximum_bytes=maximum_bytes,
        )
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _publish(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    try:
        return population_authority.publish_canonical_create_once_v1(
            uri=uri,
            value=value,
            maximum_bytes=maximum_bytes,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _safe_output_prefix(value: object) -> str:
    if type(value) is not str or not value.endswith("/"):
        _fail("population-crossed output prefix differs")
    if not value.startswith(current_contract.OUTPUT_NAMESPACE):
        _fail("population-crossed output prefix escapes the research namespace")
    if "?" in value or "#" in value or "//" in value[5:]:
        _fail("population-crossed output prefix differs")
    if any(part in {"", ".", ".."} for part in value[5:-1].split("/")):
        _fail("population-crossed output prefix path differs")
    return value


def dispatcher_process_spec_v1() -> dict[str, object]:
    root = Path(__file__).resolve().parents[3]
    path = root / DISPATCHER_RELATIVE_PATH
    if not path.is_file():
        _fail("population-crossed dispatcher entrypoint is absent")
    digest = sha256(path.read_bytes()).hexdigest()
    command = list(DISPATCHER_COMMAND)
    return {
        "process_role": "population-crossed-slate-dispatcher",
        "entrypoint_path": DISPATCHER_IMAGE_PATH,
        "entrypoint_sha256": digest,
        "command": command,
        "command_sha256": _hash({
            "command": command,
            "entrypoint_sha256": digest,
        }),
        "one_process_runs_all_folds_and_profiles_for_one_slate": True,
    }


def _slate_result_uri(prefix: str, source_ordinal: int) -> str:
    return f"{prefix}slates/{source_ordinal:02d}/selection-result.json"


def _validate_population_result_binding_v1(
    *,
    result_value: object,
    result_identity: object,
    population_binding: Mapping[str, object],
    source_ordinal: int,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        result = population_runtime.validate_task_result_v1(result_value)
    except population_runtime.CorpusR6PopulationChallengerRuntimeV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
    identity = _bind(result, result_identity, label="population task result")
    source_request = _mapping(
        population_binding.get("request"), label="population source request"
    )
    expected_outputs = _mapping(
        source_request.get("expected_outputs"), label="population expected outputs"
    )
    expected_profile_uris = _mapping(
        expected_outputs.get("profile_lineup_uris"),
        label="population profile output URIs",
    )
    rows = [
        _mapping(row, label="population profile result")
        for row in _sequence(result.get("profile_results"), label="profile results")
    ]
    if (
        result.get("task_index") != source_ordinal
        or result.get("source_ordinal") != source_ordinal
        or result.get("request_sha256") != source_request.get("request_sha256")
        or identity.get("uri") != expected_outputs.get("task_result_uri")
        or [row.get("profile_id") for row in rows]
        != list(profiles.PROFILE_ORDER)
    ):
        _fail("population task result/source binding differs")
    for row in rows:
        profile_id = str(row["profile_id"])
        lineup_identity = _identity(
            row.get("lineups_identity"), label=f"{profile_id} lineups"
        )
        if lineup_identity["uri"] != expected_profile_uris.get(profile_id):
            _fail("population profile lineup URI differs from source manifest")
    return result, identity


def build_task_manifest_v1(
    *,
    population_task_manifest_identity: object,
    population_task_result_identities: object,
    output_prefix: str,
    code_commit: str,
    image_digest: str,
    reused_job_name: str,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build one immutable 54-task authority from completed population outputs."""
    population_body, population_identity = _read_json(
        population_task_manifest_identity,
        read_exact=read_exact,
        label="population task manifest",
        maximum_bytes=MAXIMUM_POPULATION_MANIFEST_BYTES,
    )
    try:
        population_manifest = population_authority.validate_task_manifest_v1(
            population_body
        )
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
    _bind(
        population_manifest,
        population_identity,
        label="population task manifest",
    )
    identities = [
        _identity(row, label=f"population task result[{index}]")
        for index, row in enumerate(
            _sequence(
                population_task_result_identities,
                label="population task result identities",
            )
        )
    ]
    if len(identities) != TASK_COUNT:
        _fail("population-crossed preparation requires exactly 54 task results")
    prefix = _safe_output_prefix(output_prefix)
    if _COMMIT_RE.fullmatch(code_commit) is None:
        _fail("code commit must be lowercase 40-hex")
    if _DIGEST_RE.fullmatch(image_digest) is None:
        _fail("image digest must be sha256:<lowercase-64-hex>")
    if _JOB_RE.fullmatch(reused_job_name) is None:
        _fail("reused Cloud Run job name differs")

    process_spec = dispatcher_process_spec_v1()
    bindings: list[dict[str, object]] = []
    for source_ordinal, (population_binding, result_identity) in enumerate(
        zip(population_manifest["task_bindings"], identities, strict=True)
    ):
        result_body, retained_result_identity = _read_json(
            result_identity,
            read_exact=read_exact,
            label=f"population task result[{source_ordinal}]",
            maximum_bytes=MAXIMUM_POPULATION_TASK_RESULT_BYTES,
        )
        result, retained_result_identity = _validate_population_result_binding_v1(
            result_value=result_body,
            result_identity=retained_result_identity,
            population_binding=population_binding,
            source_ordinal=source_ordinal,
        )
        profile_identities = {
            str(row["profile_id"]): _identity(
                row["lineups_identity"], label=f"{row['profile_id']} lineups"
            )
            for row in result["profile_results"]
        }
        profile_counts = {
            str(row["profile_id"]): int(row["unique_lineup_count"])
            for row in result["profile_results"]
        }
        request = _with_hash({
            "schema": TASK_REQUEST_SCHEMA,
            "task_index": source_ordinal,
            "source_ordinal": source_ordinal,
            "population_task_manifest_identity": population_identity,
            "population_task_manifest_sha256": population_manifest[
                "task_manifest_sha256"
            ],
            "population_task_binding_sha256": population_binding[
                "task_binding_sha256"
            ],
            "population_generation_request_sha256": result[
                "request_sha256"
            ],
            "population_task_result_identity": retained_result_identity,
            "population_task_result_sha256": result["task_result_sha256"],
            "projection_bundle_identity": population_binding["request"][
                "projection_bundle_identity"
            ],
            "profile_lineup_identities": profile_identities,
            "profile_lineup_identities_sha256": _hash(profile_identities),
            "profile_unique_lineup_counts": profile_counts,
            "profile_order": list(profiles.PROFILE_ORDER),
            "fold_order": list(rw.WORLD_BLOCKS),
            "expected_result_uri": _slate_result_uri(prefix, source_ordinal),
            "code_commit": code_commit,
            "image_digest": image_digest,
            "reused_job_name": reused_job_name,
            "policy": dict(_POLICY),
        }, field="request_sha256")
        binding = _with_hash({
            "schema": TASK_BINDING_SCHEMA,
            "task_index": source_ordinal,
            "source_ordinal": source_ordinal,
            "slate_id": result["source_authority"]["slate_id"],
            "request": request,
            "request_sha256": request["request_sha256"],
            "result_uri": request["expected_result_uri"],
            "dispatcher_command": list(DISPATCHER_COMMAND),
        }, field="task_binding_sha256")
        bindings.append(binding)

    body = {
        "schema": TASK_MANIFEST_SCHEMA,
        "population_task_manifest_identity": population_identity,
        "population_task_manifest_sha256": population_manifest[
            "task_manifest_sha256"
        ],
        "population_task_result_identities": identities,
        "population_task_result_identities_sha256": _hash(identities),
        "output_prefix": prefix,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "reused_job_name": reused_job_name,
        "dispatcher_process_spec": process_spec,
        "dispatcher_process_spec_sha256": _hash(process_spec),
        "task_count": TASK_COUNT,
        "fold_count_per_slate": FOLD_COUNT,
        "profile_count_per_fold": PROFILE_COUNT,
        "selectors_per_profile_fold": SELECTORS_PER_PROFILE_FOLD,
        "selector_cells_per_slate": SELECTOR_CELLS_PER_SLATE,
        "profile_order": list(profiles.PROFILE_ORDER),
        "fold_order": list(rw.WORLD_BLOCKS),
        "task_bindings": bindings,
        "task_binding_sha256s": [row["task_binding_sha256"] for row in bindings],
        "one_reused_job_for_all_slates": True,
        "per_profile_or_parameter_deploy_allowed": False,
        "policy": dict(_POLICY),
    }
    manifest = _with_hash(body, field="task_manifest_sha256")
    if len(_canonical(manifest)) > MAXIMUM_TASK_MANIFEST_BYTES:
        _fail("population-crossed task manifest exceeds its byte ceiling")
    return validate_task_manifest_v1(manifest)


def validate_task_request_v1(value: object) -> dict[str, object]:
    request = _mapping(value, label="population-crossed task request")
    expected = {
        "schema", "task_index", "source_ordinal",
        "population_task_manifest_identity", "population_task_manifest_sha256",
        "population_task_binding_sha256", "population_generation_request_sha256",
        "population_task_result_identity", "population_task_result_sha256",
        "projection_bundle_identity",
        "profile_lineup_identities", "profile_lineup_identities_sha256",
        "profile_unique_lineup_counts", "profile_order", "fold_order",
        "expected_result_uri", "code_commit", "image_digest", "reused_job_name",
        "policy", "request_sha256",
    }
    if set(request) != expected or request.get("schema") != TASK_REQUEST_SCHEMA:
        _fail("population-crossed task request fields/schema differ")
    if request.get("request_sha256") != _hash({
        key: row for key, row in request.items() if key != "request_sha256"
    }):
        _fail("population-crossed task request self-hash differs")
    index = request.get("task_index")
    profiles_by_id = _mapping(
        request.get("profile_lineup_identities"), label="profile identities"
    )
    counts = _mapping(
        request.get("profile_unique_lineup_counts"), label="profile counts"
    )
    if (
        type(index) is not int
        or not 0 <= index < TASK_COUNT
        or request.get("source_ordinal") != index
        or tuple(profiles_by_id) != profiles.PROFILE_ORDER
        or tuple(counts) != profiles.PROFILE_ORDER
        or any(type(value) is not int or value < crossed.MINIMUM_COMMON_COUNT
               for value in counts.values())
        or request.get("profile_lineup_identities_sha256") != _hash(profiles_by_id)
        or request.get("profile_order") != list(profiles.PROFILE_ORDER)
        or request.get("fold_order") != list(rw.WORLD_BLOCKS)
        or request.get("policy") != _POLICY
        or _COMMIT_RE.fullmatch(str(request.get("code_commit"))) is None
        or _DIGEST_RE.fullmatch(str(request.get("image_digest"))) is None
        or _JOB_RE.fullmatch(str(request.get("reused_job_name"))) is None
    ):
        _fail("population-crossed task request fixed authority differs")
    for field in (
        "population_task_manifest_sha256",
        "population_task_binding_sha256",
        "population_generation_request_sha256",
        "population_task_result_sha256",
    ):
        _sha(request.get(field), label=field)
    for profile_id, identity in profiles_by_id.items():
        _identity(identity, label=f"{profile_id} lineups")
    _identity(
        request.get("population_task_manifest_identity"),
        label="population manifest",
    )
    _identity(
        request.get("population_task_result_identity"),
        label="population task result",
    )
    _identity(request.get("projection_bundle_identity"), label="projection bundle")
    expected_uri = request.get("expected_result_uri")
    if (
        type(expected_uri) is not str
        or not expected_uri.startswith(current_contract.OUTPUT_NAMESPACE)
        or not expected_uri.endswith(f"slates/{index:02d}/selection-result.json")
        or "?" in expected_uri
        or "#" in expected_uri
    ):
        _fail("population-crossed task result URI differs")
    return request


def validate_task_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="population-crossed task manifest")
    expected = {
        "schema", "population_task_manifest_identity",
        "population_task_manifest_sha256", "population_task_result_identities",
        "population_task_result_identities_sha256", "output_prefix", "code_commit",
        "image_digest", "reused_job_name", "dispatcher_process_spec",
        "dispatcher_process_spec_sha256", "task_count", "fold_count_per_slate",
        "profile_count_per_fold", "selectors_per_profile_fold",
        "selector_cells_per_slate", "profile_order", "fold_order", "task_bindings",
        "task_binding_sha256s", "one_reused_job_for_all_slates",
        "per_profile_or_parameter_deploy_allowed", "policy", "task_manifest_sha256",
    }
    if set(manifest) != expected or manifest.get("schema") != TASK_MANIFEST_SCHEMA:
        _fail("population-crossed task manifest fields/schema differ")
    if manifest.get("task_manifest_sha256") != _hash({
        key: row for key, row in manifest.items() if key != "task_manifest_sha256"
    }):
        _fail("population-crossed task manifest self-hash differs")
    identities = [
        _identity(row, label=f"population result identity[{index}]")
        for index, row in enumerate(
            _sequence(
                manifest.get("population_task_result_identities"),
                label="population result identities",
            )
        )
    ]
    bindings = [
        _mapping(row, label=f"population-crossed binding[{index}]")
        for index, row in enumerate(
            _sequence(manifest.get("task_bindings"), label="task bindings")
        )
    ]
    if (
        len(identities) != TASK_COUNT
        or len(bindings) != TASK_COUNT
        or len({
            (row["uri"], row["generation"], row["sha256"], row["bytes"])
            for row in identities
        }) != TASK_COUNT
        or manifest.get("population_task_result_identities_sha256") != _hash(identities)
        or manifest.get("task_count") != TASK_COUNT
        or manifest.get("fold_count_per_slate") != FOLD_COUNT
        or manifest.get("profile_count_per_fold") != PROFILE_COUNT
        or manifest.get("selectors_per_profile_fold") != SELECTORS_PER_PROFILE_FOLD
        or manifest.get("selector_cells_per_slate") != SELECTOR_CELLS_PER_SLATE
        or manifest.get("profile_order") != list(profiles.PROFILE_ORDER)
        or manifest.get("fold_order") != list(rw.WORLD_BLOCKS)
        or manifest.get("task_binding_sha256s")
        != [row.get("task_binding_sha256") for row in bindings]
        or manifest.get("one_reused_job_for_all_slates") is not True
        or manifest.get("per_profile_or_parameter_deploy_allowed") is not False
        or manifest.get("policy") != _POLICY
        or len(_canonical(manifest)) > MAXIMUM_TASK_MANIFEST_BYTES
    ):
        _fail("population-crossed task manifest fixed authority differs")
    _safe_output_prefix(manifest.get("output_prefix"))
    _identity(
        manifest.get("population_task_manifest_identity"),
        label="population manifest",
    )
    process = _mapping(
        manifest.get("dispatcher_process_spec"), label="dispatcher process spec"
    )
    if (
        process.get("command") != list(DISPATCHER_COMMAND)
        or process.get("entrypoint_path") != DISPATCHER_IMAGE_PATH
        or process.get("one_process_runs_all_folds_and_profiles_for_one_slate")
        is not True
        or manifest.get("dispatcher_process_spec_sha256") != _hash(process)
    ):
        _fail("population-crossed dispatcher process authority differs")
    for index, (binding, result_identity) in enumerate(
        zip(bindings, identities, strict=True)
    ):
        if binding.get("task_binding_sha256") != _hash({
            key: row for key, row in binding.items() if key != "task_binding_sha256"
        }):
            _fail("population-crossed task binding self-hash differs")
        request = validate_task_request_v1(binding.get("request"))
        if (
            binding.get("schema") != TASK_BINDING_SCHEMA
            or binding.get("task_index") != index
            or binding.get("source_ordinal") != index
            or request["task_index"] != index
            or binding.get("request_sha256") != request["request_sha256"]
            or binding.get("result_uri") != request["expected_result_uri"]
            or binding.get("dispatcher_command") != list(DISPATCHER_COMMAND)
            or request["population_task_manifest_identity"]
            != manifest["population_task_manifest_identity"]
            or request["population_task_manifest_sha256"]
            != manifest["population_task_manifest_sha256"]
            or request["population_task_result_identity"] != result_identity
            or request["code_commit"] != manifest["code_commit"]
            or request["image_digest"] != manifest["image_digest"]
            or request["reused_job_name"] != manifest["reused_job_name"]
            or not str(binding.get("result_uri")).startswith(
                str(manifest["output_prefix"])
            )
        ):
            _fail("population-crossed task binding cross-authority differs")
    return manifest


def task_request_v1(value: object, *, task_index: int) -> dict[str, object]:
    manifest = validate_task_manifest_v1(value)
    if type(task_index) is not int or not 0 <= task_index < TASK_COUNT:
        _fail("task index is outside the 54-slate authority")
    return validate_task_request_v1(
        manifest["task_bindings"][task_index]["request"]
    )


def _load_task_sources_v1(
    request: Mapping[str, object], *, read_exact: ReadExact
) -> tuple[object, dict[str, dict[str, object]], dict[str, object]]:
    result_body, result_identity = _read_json(
        request["population_task_result_identity"],
        read_exact=read_exact,
        label="population task result",
        maximum_bytes=MAXIMUM_POPULATION_TASK_RESULT_BYTES,
    )
    try:
        result = population_runtime.validate_task_result_v1(result_body)
    except population_runtime.CorpusR6PopulationChallengerRuntimeV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
    _bind(result, result_identity, label="population task result")
    if (
        result.get("task_index") != request["task_index"]
        or result.get("source_ordinal") != request["source_ordinal"]
        or result.get("request_sha256")
        != request.get("population_generation_request_sha256")
    ):
        _fail("population task result execution binding differs")
    # The task result stores its own self-hash, while the request binds both
    # that self-hash and the generation-exact content identity.
    if result["task_result_sha256"] != request["population_task_result_sha256"]:
        _fail("population task result self-hash differs from task request")

    projection_body, projection_identity = _read_json(
        request["projection_bundle_identity"],
        read_exact=read_exact,
        label="projection bundle",
        maximum_bytes=population_authority.MAXIMUM_PROJECTION_BUNDLE_BYTES,
    )
    try:
        source = population_runtime._projection_source_authority_v1(
            projection_body,
            projection_identity=projection_identity,
            expected_source_ordinal=int(request["source_ordinal"]),
        )
        prepared = population_runtime._prepared_slate_v1(
            source, read_exact=read_exact
        )
    except population_runtime.CorpusR6PopulationChallengerRuntimeV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
    if source != result.get("source_authority"):
        _fail("population result/projection source authority differs")

    profile_bodies: dict[str, dict[str, object]] = {}
    for profile_id in profiles.PROFILE_ORDER:
        body, identity = _read_json(
            request["profile_lineup_identities"][profile_id],
            read_exact=read_exact,
            label=f"{profile_id} lineups",
            maximum_bytes=MAXIMUM_PROFILE_LINEUPS_BYTES,
        )
        try:
            retained = population_runtime.validate_profile_lineups_v1(
                body, players=prepared.players
            )
        except population_runtime.CorpusR6PopulationChallengerRuntimeV1Error as exc:
            raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
        _bind(retained, identity, label=f"{profile_id} lineups")
        if (
            retained["profile"]["profile_id"] != profile_id
            or retained["source_authority"] != source
        ):
            _fail("population profile/source authority differs")
        profile_bodies[profile_id] = retained
    return prepared, profile_bodies, source


def _validate_selector_result_v1(
    value: object, *, profile_id: str
) -> dict[str, object]:
    result = _mapping(value, label="population-crossed selector result")
    if (
        result.get("schema") != crossed.SELECTOR_RESULT_SCHEMA
        or result.get("selector_result_sha256") != _hash({
            key: row for key, row in result.items()
            if key != "selector_result_sha256"
        })
        or result.get("profile_id") != profile_id
        or result.get("source_arm_id") != profile_id
        or result.get("selector_input_source_arm_registry") != [profile_id]
        or result.get("heldout_score_columns_present") is not False
        or result.get("heldout_matrix_or_digest_read") is not False
        or result.get("realized_outcomes_read") is not False
    ):
        _fail("population-crossed selector result authority differs")
    grouped = _mapping(result.get("grouped_result"), label="grouped selector result")
    ranked = _mapping(result.get("rank150_result"), label="rank150 selector result")
    dpp = _mapping(result.get("dpp_result"), label="DPP selector result")
    if (
        grouped.get("schema_version") != successor.RESULT_SCHEMA
        or grouped.get("selector_count") != 3
        or grouped.get("result_sha256") != result.get("grouped_result_sha256")
        or ranked.get("schema_version") != rank150.RESULT_SCHEMA
        or ranked.get("selector_count") != 3
        or ranked.get("ranking_depth") != rank150.RANKING_DEPTH
        or ranked.get("result_sha256") != result.get("rank150_result_sha256")
        or dpp.get("schema_version") != diversity.RESULT_SCHEMA
        or dpp.get("entry_budget") != diversity.ENTRY_BUDGET
        or dpp.get("result_sha256") != result.get("dpp_result_sha256")
    ):
        _fail("population-crossed native selector lattice differs")
    return result


def _evaluation_book_descriptors_v1(
    *, selector_result: Mapping[str, object], sampled_lineup_ids: Sequence[str]
) -> list[dict[str, object]]:
    """Normalize the seven native selector outputs for a held-out evaluator."""
    sampled = set(str(row) for row in sampled_lineup_ids)
    grouped = _mapping(
        selector_result["grouped_result"], label="grouped selector result"
    )
    ranked = _mapping(
        selector_result["rank150_result"], label="rank150 selector result"
    )
    dpp = _mapping(selector_result["dpp_result"], label="DPP selector result")
    sources: list[tuple[str, int, str, str, object, Sequence[int]]] = []
    for raw in _sequence(grouped.get("selectors"), label="grouped selectors"):
        row = _mapping(raw, label="grouped selector")
        sources.append((
            "grouped-native-rank80",
            int(row.get("ordinal", -1)),
            str(row.get("preset_id")),
            str(row.get("selector_result_sha256")),
            row.get("prefixes"),
            successor.PREFIX_SIZES,
        ))
    for raw in _sequence(ranked.get("selectors"), label="rank150 selectors"):
        row = _mapping(raw, label="rank150 selector")
        sources.append((
            "exact-rank150-continuation",
            int(row.get("ordinal", -1)),
            str(row.get("preset_id")),
            str(row.get("selector_result_sha256")),
            row.get("entry_books"),
            rank150.ENTRY_BUDGETS,
        ))
    dpp_contract = _mapping(
        dpp.get("strategy_contract"), label="DPP strategy contract"
    )
    sources.append((
        "effective-independent-tail-shots",
        0,
        str(dpp_contract.get("strategy_id")),
        str(dpp.get("result_sha256")),
        dpp.get("prefixes"),
        diversity.PREFIX_SIZES,
    ))
    if (
        len(sources) != SELECTORS_PER_PROFILE_FOLD
        or len({(family, ordinal, selector_id) for (
            family, ordinal, selector_id, _source_sha, _prefixes, _sizes
        ) in sources}) != SELECTORS_PER_PROFILE_FOLD
    ):
        _fail("population-crossed evaluator selector coordinates differ")
    descriptors: list[dict[str, object]] = []
    for family, ordinal, selector_id, source_sha, raw_prefixes, sizes in sources:
        prefixes = [
            _mapping(row, label=f"{family} evaluator prefix")
            for row in _sequence(raw_prefixes, label=f"{family} evaluator prefixes")
        ]
        if [row.get("prefix_size") for row in prefixes] != list(sizes):
            _fail("population-crossed evaluator prefix lattice differs")
        normalized_prefixes: list[dict[str, object]] = []
        for prefix in prefixes:
            size = int(prefix["prefix_size"])
            selected = [
                str(row)
                for row in _sequence(
                    prefix.get("selected_lineup_ids"),
                    label="evaluator selected lineup IDs",
                )
            ]
            if (
                len(selected) != size
                or len(set(selected)) != size
                or not set(selected) <= sampled
                or prefix.get("selected_lineup_ids_sha256") != _hash(selected)
            ):
                _fail("population-crossed evaluator selected book differs")
            normalized_prefixes.append({
                "entry_budget": size,
                "selected_lineup_ids": selected,
                "selected_lineup_ids_sha256": prefix[
                    "selected_lineup_ids_sha256"
                ],
                "selected_rosters_sha256": prefix[
                    "selected_rosters_sha256"
                ],
                "source_prefix_sha256": prefix["prefix_sha256"],
            })
        descriptors.append(_with_hash({
            "selector_family": family,
            "selector_ordinal": ordinal,
            "selector_id": selector_id,
            "source_selector_result_sha256": source_sha,
            "prefixes": normalized_prefixes,
            "entry_budgets": [row["entry_budget"] for row in normalized_prefixes],
            "heldout_score_rows_required": sorted({
                lineup_id
                for prefix in normalized_prefixes
                for lineup_id in prefix["selected_lineup_ids"]
            }),
            "heldout_score_values_present": False,
        }, field="book_descriptor_sha256"))
    return descriptors


def _build_profile_result_v1(
    *,
    profile_id: str,
    plan: Mapping[str, object],
    fold_inputs: crossed.PopulationCrossedFoldInputsV1,
    selector_result: Mapping[str, object],
    request: Mapping[str, object],
    source: Mapping[str, object],
) -> dict[str, object]:
    retained_selector = _validate_selector_result_v1(
        selector_result, profile_id=profile_id
    )
    profile_plan = next(
        row for row in plan["profiles"] if row["profile_id"] == profile_id
    )
    evaluation = fold_inputs.evaluation
    book_descriptors = _evaluation_book_descriptors_v1(
        selector_result=retained_selector,
        sampled_lineup_ids=fold_inputs.selection.sampled_lineup_ids,
    )
    heldout_key = f"world_artifact_{evaluation.heldout_block.casefold()}"
    evaluator_recipe = _with_hash({
        "projection_bundle_identity": request["projection_bundle_identity"],
        "population_profile_lineups_identity": request[
            "profile_lineup_identities"
        ][profile_id],
        "plan_sha256": plan["plan_sha256"],
        "profile_plan_sha256": profile_plan["profile_plan_sha256"],
        "profile_id": profile_id,
        "heldout_block": evaluation.heldout_block,
        "heldout_world_artifact_identity": source[
            "world_artifact_identities"
        ][heldout_key],
        "later_source_identity": source["later_source_identity"],
        "sampled_lineup_ids_sha256": profile_plan[
            "sampled_lineup_ids_sha256"
        ],
        "sampled_candidate_rows_sha256": profile_plan[
            "sampled_candidate_rows_sha256"
        ],
        "evaluation_binding_sha256": evaluation.binding[
            "evaluation_binding_sha256"
        ],
        "reconstruction_function": (
            "reconstruct_profile_fold_for_evaluation_v1"
        ),
        "heldout_score_values_persisted": False,
        "realized_outcomes_read": False,
    }, field="evaluator_recipe_sha256")
    body = {
        "schema": PROFILE_RESULT_SCHEMA,
        "profile_id": profile_id,
        "source_arm_id": profile_id,
        "plan_sha256": plan["plan_sha256"],
        "profile_plan_sha256": profile_plan["profile_plan_sha256"],
        "sampled_lineup_count": profile_plan["sampled_lineup_count"],
        "sampled_lineup_ids": profile_plan["sampled_lineup_ids"],
        "sampled_lineup_ids_sha256": profile_plan[
            "sampled_lineup_ids_sha256"
        ],
        "sampled_candidate_rows": profile_plan["sampled_candidate_rows"],
        "sampled_candidate_rows_sha256": profile_plan[
            "sampled_candidate_rows_sha256"
        ],
        "selection_binding": dict(fold_inputs.selection.binding),
        "selection_binding_sha256": fold_inputs.selection.binding[
            "selection_binding_sha256"
        ],
        "evaluation_binding": dict(evaluation.binding),
        "evaluation_binding_sha256": evaluation.binding[
            "evaluation_binding_sha256"
        ],
        "selector_result": retained_selector,
        "selector_result_sha256": retained_selector[
            "selector_result_sha256"
        ],
        "evaluation_book_descriptors": book_descriptors,
        "evaluation_book_descriptors_sha256": _hash(book_descriptors),
        "evaluation_book_descriptor_count": len(book_descriptors),
        "grouped_selector_count": 3,
        "rank150_selector_count": 3,
        "dpp_selector_count": 1,
        "selector_cell_count": SELECTORS_PER_PROFILE_FOLD,
        "evaluator_recipe": evaluator_recipe,
        "evaluator_recipe_sha256": evaluator_recipe[
            "evaluator_recipe_sha256"
        ],
        "heldout_score_values_persisted": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field="profile_result_sha256")


def build_slate_result_v1(
    *,
    request: Mapping[str, object],
    task_binding_sha256: str,
    prepared: object,
    profile_lineups_by_id: Mapping[str, object],
    source: Mapping[str, object],
) -> dict[str, object]:
    """Run all 15 profile/folds sequentially and retain no held-out matrix."""
    retained_request = validate_task_request_v1(request)
    folds: list[dict[str, object]] = []
    for fold_ordinal, heldout_block in enumerate(rw.WORLD_BLOCKS):
        try:
            plan = crossed.build_population_crossed_fold_plan_v1(
                profile_lineups_by_id=profile_lineups_by_id,
                prepared=prepared,
                heldout_block=heldout_block,
            )
        except crossed.CorpusR6PopulationCrossedScoringV1Error as exc:
            raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
        profile_results: list[dict[str, object]] = []
        for profile_id in profiles.PROFILE_ORDER:
            try:
                fold_inputs = crossed.materialize_population_crossed_profile_fold_v1(
                    plan=plan, prepared=prepared, profile_id=profile_id
                )
                selector_result = crossed.run_population_crossed_selectors_v1(
                    fold_inputs.selection
                )
            except crossed.CorpusR6PopulationCrossedScoringV1Error as exc:
                raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
            profile_results.append(_build_profile_result_v1(
                profile_id=profile_id,
                plan=plan,
                fold_inputs=fold_inputs,
                selector_result=selector_result,
                request=retained_request,
                source=source,
            ))
            del fold_inputs
        fold_body = {
            "schema": FOLD_RESULT_SCHEMA,
            "fold_ordinal": fold_ordinal,
            "heldout_block": heldout_block,
            "training_blocks": [
                block for block in rw.WORLD_BLOCKS if block != heldout_block
            ],
            "plan_sha256": plan["plan_sha256"],
            "common_count": plan["common_count"],
            "profile_order": list(profiles.PROFILE_ORDER),
            "profile_results": profile_results,
            "profile_result_sha256s": [
                row["profile_result_sha256"] for row in profile_results
            ],
            "selector_cell_count": PROFILE_COUNT * SELECTORS_PER_PROFILE_FOLD,
            "score_values_read_for_sampling": False,
            "heldout_scores_available_to_selectors": False,
            "realized_outcomes_read": False,
        }
        folds.append(_with_hash(fold_body, field="fold_result_sha256"))

    body = {
        "schema": SLATE_RESULT_SCHEMA,
        "source_ordinal": retained_request["source_ordinal"],
        "slate_id": source["slate_id"],
        "task_request_sha256": retained_request["request_sha256"],
        "task_binding_sha256": task_binding_sha256,
        "population_task_result_identity": retained_request[
            "population_task_result_identity"
        ],
        "population_task_result_sha256": retained_request[
            "population_task_result_sha256"
        ],
        "projection_bundle_identity": retained_request[
            "projection_bundle_identity"
        ],
        "profile_lineup_identities": retained_request[
            "profile_lineup_identities"
        ],
        "source_authority_sha256": source["source_authority_sha256"],
        "fold_count": FOLD_COUNT,
        "fold_order": list(rw.WORLD_BLOCKS),
        "fold_results": folds,
        "fold_result_sha256s": [row["fold_result_sha256"] for row in folds],
        "profile_fold_count": FOLD_COUNT * PROFILE_COUNT,
        "selector_cell_count": SELECTOR_CELLS_PER_SLATE,
        "selector_lattice": dict(_SELECTOR_LATTICE),
        "outcome_blind_fold_plans": True,
        "heldout_score_values_persisted": False,
        "realized_outcomes_read": False,
        "policy": dict(_POLICY),
    }
    result = _with_hash(body, field="slate_result_sha256")
    if len(_canonical(result)) > MAXIMUM_SLATE_RESULT_BYTES:
        _fail("population-crossed slate result exceeds its byte ceiling")
    return validate_slate_result_v1(result)


def validate_slate_result_v1(value: object) -> dict[str, object]:
    result = _mapping(value, label="population-crossed slate result")
    source_ordinal = result.get("source_ordinal")
    slate_id = result.get("slate_id")
    if (
        result.get("schema") != SLATE_RESULT_SCHEMA
        or result.get("slate_result_sha256") != _hash({
            key: row for key, row in result.items() if key != "slate_result_sha256"
        })
        or result.get("fold_count") != FOLD_COUNT
        or result.get("fold_order") != list(rw.WORLD_BLOCKS)
        or result.get("profile_fold_count") != FOLD_COUNT * PROFILE_COUNT
        or result.get("selector_cell_count") != SELECTOR_CELLS_PER_SLATE
        or result.get("selector_lattice") != _SELECTOR_LATTICE
        or type(source_ordinal) is not int
        or not 0 <= source_ordinal < TASK_COUNT
        or type(slate_id) is not str
        or not slate_id
        or result.get("outcome_blind_fold_plans") is not True
        or result.get("heldout_score_values_persisted") is not False
        or result.get("realized_outcomes_read") is not False
        or result.get("policy") != _POLICY
        or len(_canonical(result)) > MAXIMUM_SLATE_RESULT_BYTES
    ):
        _fail("population-crossed slate result fixed authority differs")
    folds = [
        _mapping(row, label=f"population-crossed fold[{index}]")
        for index, row in enumerate(
            _sequence(result.get("fold_results"), label="fold results")
        )
    ]
    if (
        len(folds) != FOLD_COUNT
        or result.get("fold_result_sha256s")
        != [row.get("fold_result_sha256") for row in folds]
    ):
        _fail("population-crossed fold result order differs")
    for fold_ordinal, (heldout_block, fold) in enumerate(
        zip(rw.WORLD_BLOCKS, folds, strict=True)
    ):
        if (
            fold.get("schema") != FOLD_RESULT_SCHEMA
            or fold.get("fold_result_sha256") != _hash({
                key: row for key, row in fold.items()
                if key != "fold_result_sha256"
            })
            or fold.get("fold_ordinal") != fold_ordinal
            or fold.get("heldout_block") != heldout_block
            or fold.get("training_blocks")
            != [block for block in rw.WORLD_BLOCKS if block != heldout_block]
            or fold.get("profile_order") != list(profiles.PROFILE_ORDER)
            or fold.get("selector_cell_count")
            != PROFILE_COUNT * SELECTORS_PER_PROFILE_FOLD
            or fold.get("score_values_read_for_sampling") is not False
            or fold.get("heldout_scores_available_to_selectors") is not False
            or fold.get("realized_outcomes_read") is not False
        ):
            _fail("population-crossed fold result authority differs")
        profile_rows = [
            _mapping(row, label="population-crossed profile result")
            for row in _sequence(
                fold.get("profile_results"), label="profile results"
            )
        ]
        if (
            [row.get("profile_id") for row in profile_rows]
            != list(profiles.PROFILE_ORDER)
            or fold.get("profile_result_sha256s")
            != [row.get("profile_result_sha256") for row in profile_rows]
        ):
            _fail("population-crossed profile result order differs")
        for profile_id, row in zip(
            profiles.PROFILE_ORDER, profile_rows, strict=True
        ):
            selection_binding = _mapping(
                row.get("selection_binding"), label="selection binding"
            )
            evaluation_binding = _mapping(
                row.get("evaluation_binding"), label="evaluation binding"
            )
            evaluator_recipe = _mapping(
                row.get("evaluator_recipe"), label="evaluator recipe"
            )
            if (
                row.get("schema") != PROFILE_RESULT_SCHEMA
                or row.get("profile_result_sha256") != _hash({
                    key: item for key, item in row.items()
                    if key != "profile_result_sha256"
                })
                or row.get("source_arm_id") != profile_id
                or row.get("profile_id") != profile_id
                or row.get("plan_sha256") != fold.get("plan_sha256")
                or type(row.get("sampled_lineup_count")) is not int
                or row.get("sampled_lineup_count")
                != len(row.get("sampled_lineup_ids", []))
                or row.get("sampled_lineup_ids_sha256")
                != _hash(row.get("sampled_lineup_ids"))
                or row.get("sampled_candidate_rows_sha256")
                != _hash(row.get("sampled_candidate_rows"))
                or len(row.get("sampled_candidate_rows", []))
                != row.get("sampled_lineup_count")
                or row.get("selector_cell_count")
                != SELECTORS_PER_PROFILE_FOLD
                or row.get("evaluation_book_descriptor_count")
                != SELECTORS_PER_PROFILE_FOLD
                or row.get("evaluation_book_descriptors_sha256")
                != _hash(row.get("evaluation_book_descriptors"))
                or row.get("heldout_score_values_persisted") is not False
                or row.get("realized_outcomes_read") is not False
                or row.get("selection_binding_sha256")
                != selection_binding.get("selection_binding_sha256")
                or selection_binding.get("selection_binding_sha256")
                != _hash({
                    key: item for key, item in selection_binding.items()
                    if key != "selection_binding_sha256"
                })
                or row.get("evaluation_binding_sha256")
                != evaluation_binding.get("evaluation_binding_sha256")
                or evaluation_binding.get("evaluation_binding_sha256")
                != _hash({
                    key: item for key, item in evaluation_binding.items()
                    if key != "evaluation_binding_sha256"
                })
                or row.get("evaluator_recipe_sha256")
                != evaluator_recipe.get("evaluator_recipe_sha256")
                or evaluator_recipe.get("evaluator_recipe_sha256")
                != _hash({
                    key: item for key, item in evaluator_recipe.items()
                    if key != "evaluator_recipe_sha256"
                })
                or evaluator_recipe.get("profile_id") != profile_id
                or evaluator_recipe.get("heldout_block") != heldout_block
                or evaluator_recipe.get("plan_sha256") != fold.get("plan_sha256")
                or evaluator_recipe.get("profile_plan_sha256")
                != row.get("profile_plan_sha256")
                or evaluator_recipe.get("sampled_lineup_ids_sha256")
                != row.get("sampled_lineup_ids_sha256")
                or evaluator_recipe.get("sampled_candidate_rows_sha256")
                != row.get("sampled_candidate_rows_sha256")
                or evaluator_recipe.get("evaluation_binding_sha256")
                != row.get("evaluation_binding_sha256")
                or evaluator_recipe.get("heldout_score_values_persisted")
                is not False
                or evaluator_recipe.get("realized_outcomes_read") is not False
            ):
                _fail("population-crossed profile result authority differs")
            _validate_selector_result_v1(
                row.get("selector_result"), profile_id=profile_id
            )
            expected_books = _evaluation_book_descriptors_v1(
                selector_result=row["selector_result"],
                sampled_lineup_ids=row["sampled_lineup_ids"],
            )
            if row["evaluation_book_descriptors"] != expected_books:
                _fail("population-crossed evaluator book descriptors differ")
    return result


def reconstruct_profile_fold_for_evaluation_v1(
    *,
    slate_result: object,
    prepared: object,
    profile_lineups_by_id: Mapping[str, object],
    heldout_block: str,
    profile_id: str,
) -> crossed.PopulationCrossedFoldInputsV1:
    """Rebuild and verify the exact evaluator input from immutable sources."""
    result = validate_slate_result_v1(slate_result)
    if heldout_block not in rw.WORLD_BLOCKS or profile_id not in profiles.PROFILE_ORDER:
        _fail("population-crossed evaluator coordinate differs")
    fold = result["fold_results"][rw.WORLD_BLOCKS.index(heldout_block)]
    row = next(
        item for item in fold["profile_results"] if item["profile_id"] == profile_id
    )
    try:
        plan = crossed.build_population_crossed_fold_plan_v1(
            profile_lineups_by_id=profile_lineups_by_id,
            prepared=prepared,
            heldout_block=heldout_block,
        )
        inputs = crossed.materialize_population_crossed_profile_fold_v1(
            plan=plan, prepared=prepared, profile_id=profile_id
        )
    except crossed.CorpusR6PopulationCrossedScoringV1Error as exc:
        raise CorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc
    if (
        plan["plan_sha256"] != fold["plan_sha256"]
        or inputs.selection.binding != row["selection_binding"]
        or inputs.evaluation.binding != row["evaluation_binding"]
        or list(inputs.selection.sampled_lineup_ids)
        != row["sampled_lineup_ids"]
        or list(inputs.selection.candidate_rows)
        != row["sampled_candidate_rows"]
    ):
        _fail("reconstructed population evaluator input differs")
    return inputs


def execute_task_v1(
    *,
    task_manifest: object,
    task_manifest_identity: object,
    task_index: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    manifest = validate_task_manifest_v1(task_manifest)
    manifest_identity = _bind(
        manifest, task_manifest_identity, label="population-crossed task manifest"
    )
    request = task_request_v1(manifest, task_index=task_index)
    prepared, profile_bodies, source = _load_task_sources_v1(
        request, read_exact=read_exact
    )
    binding = manifest["task_bindings"][task_index]
    if binding.get("slate_id") != source.get("slate_id"):
        _fail("population-crossed task binding/source slate differs")
    result = build_slate_result_v1(
        request=request,
        task_binding_sha256=str(binding["task_binding_sha256"]),
        prepared=prepared,
        profile_lineups_by_id=profile_bodies,
        source=source,
    )
    result_identity = _publish(
        uri=str(binding["result_uri"]),
        value=result,
        maximum_bytes=MAXIMUM_SLATE_RESULT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    completion = _with_hash({
        "schema": TASK_COMPLETION_SCHEMA,
        "task_index": task_index,
        "source_ordinal": result["source_ordinal"],
        "slate_id": result["slate_id"],
        "task_manifest_identity": manifest_identity,
        "task_binding_sha256": binding["task_binding_sha256"],
        "slate_result_identity": result_identity,
        "slate_result_sha256": result["slate_result_sha256"],
        "fold_count": FOLD_COUNT,
        "profile_fold_count": FOLD_COUNT * PROFILE_COUNT,
        "selector_cell_count": SELECTOR_CELLS_PER_SLATE,
        "heldout_score_values_persisted": False,
        "realized_outcomes_read": False,
    }, field="task_completion_sha256")
    if len(_canonical(completion)) > MAXIMUM_TASK_COMPLETION_BYTES:
        _fail("population-crossed task completion exceeds its byte ceiling")
    return validate_task_completion_v1(completion)


def validate_task_completion_v1(value: object) -> dict[str, object]:
    completion = _mapping(value, label="population-crossed task completion")
    expected = {
        "schema", "task_index", "source_ordinal", "slate_id",
        "task_manifest_identity", "task_binding_sha256", "slate_result_identity",
        "slate_result_sha256", "fold_count", "profile_fold_count",
        "selector_cell_count", "heldout_score_values_persisted",
        "realized_outcomes_read", "task_completion_sha256",
    }
    if (
        set(completion) != expected
        or completion.get("schema") != TASK_COMPLETION_SCHEMA
        or completion.get("task_completion_sha256") != _hash({
            key: row for key, row in completion.items()
            if key != "task_completion_sha256"
        })
        or completion.get("task_index") != completion.get("source_ordinal")
        or type(completion.get("task_index")) is not int
        or not 0 <= completion["task_index"] < TASK_COUNT
        or type(completion.get("slate_id")) is not str
        or not completion["slate_id"]
        or completion.get("fold_count") != FOLD_COUNT
        or completion.get("profile_fold_count") != FOLD_COUNT * PROFILE_COUNT
        or completion.get("selector_cell_count") != SELECTOR_CELLS_PER_SLATE
        or completion.get("heldout_score_values_persisted") is not False
        or completion.get("realized_outcomes_read") is not False
        or len(_canonical(completion)) > MAXIMUM_TASK_COMPLETION_BYTES
    ):
        _fail("population-crossed task completion authority differs")
    _identity(completion.get("task_manifest_identity"), label="task manifest")
    _identity(completion.get("slate_result_identity"), label="slate result")
    _sha(completion.get("task_binding_sha256"), label="task binding SHA-256")
    _sha(completion.get("slate_result_sha256"), label="slate result SHA-256")
    return completion


def build_cloud_run_job_configuration_v1(
    *,
    task_manifest: object,
    task_manifest_identity: object,
) -> dict[str, object]:
    manifest = validate_task_manifest_v1(task_manifest)
    identity = _bind(
        manifest, task_manifest_identity, label="population-crossed task manifest"
    )
    environment = {
        ENABLE_ENV: "1",
        MANIFEST_IDENTITY_ENV: _canonical(identity).decode("utf-8"),
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["image_digest"],
    }
    body = {
        "schema": JOB_CONFIGURATION_SCHEMA,
        "reused_job_name": manifest["reused_job_name"],
        "task_manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "image_digest": manifest["image_digest"],
        "container_command": [DISPATCHER_COMMAND[0]],
        "container_args": list(DISPATCHER_COMMAND[1:]),
        "container_environment": environment,
        "task_count": TASK_COUNT,
        "parallelism": TASK_COUNT,
        "max_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "cpu": source_manifest.FIXED_CLOUD_RUN_CPU_LIMIT,
        "memory": source_manifest.FIXED_CLOUD_RUN_MEMORY_LIMIT,
        "working_directory": "",
        "volume_mounts": [],
        "volumes": [],
        "new_job_creation_allowed": False,
        "per_profile_or_parameter_deploy_allowed": False,
    }
    return _with_hash(body, field="job_configuration_sha256")


def prepare_task_manifest_v1(
    *,
    population_task_manifest_identity: object,
    population_task_result_identities: object,
    output_prefix: str,
    code_commit: str,
    image_digest: str,
    reused_job_name: str,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    manifest = build_task_manifest_v1(
        population_task_manifest_identity=population_task_manifest_identity,
        population_task_result_identities=population_task_result_identities,
        output_prefix=output_prefix,
        code_commit=code_commit,
        image_digest=image_digest,
        reused_job_name=reused_job_name,
        read_exact=read_exact,
    )
    identity = _publish(
        uri=f"{manifest['output_prefix']}authorities/task-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    body = {
        "schema": PREPARATION_SCHEMA,
        "task_manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "population_task_manifest_identity": manifest[
            "population_task_manifest_identity"
        ],
        "task_count": TASK_COUNT,
        "profile_fold_count": TASK_COUNT * FOLD_COUNT * PROFILE_COUNT,
        "selector_cell_count": TASK_COUNT * SELECTOR_CELLS_PER_SLATE,
        "job_configuration": build_cloud_run_job_configuration_v1(
            task_manifest=manifest,
            task_manifest_identity=identity,
        ),
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field="preparation_sha256")


__all__ = [
    "CorpusR6PopulationCrossedCloudV1Error",
    "DISPATCHER_COMMAND",
    "DISPATCHER_IMAGE_PATH",
    "ENABLE_ENV",
    "FOLD_COUNT",
    "MANIFEST_IDENTITY_ENV",
    "MAXIMUM_SLATE_RESULT_BYTES",
    "MAXIMUM_TASK_COMPLETION_BYTES",
    "MAXIMUM_TASK_MANIFEST_BYTES",
    "PROFILE_COUNT",
    "SELECTOR_CELLS_PER_SLATE",
    "SLATE_RESULT_SCHEMA",
    "TASK_COUNT",
    "TASK_MANIFEST_SCHEMA",
    "build_cloud_run_job_configuration_v1",
    "build_slate_result_v1",
    "build_task_manifest_v1",
    "dispatcher_process_spec_v1",
    "execute_task_v1",
    "prepare_task_manifest_v1",
    "reconstruct_profile_fold_for_evaluation_v1",
    "task_request_v1",
    "validate_slate_result_v1",
    "validate_task_completion_v1",
    "validate_task_manifest_v1",
    "validate_task_request_v1",
]
