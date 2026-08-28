"""Authority contract for one 54-slate F7/F8/F9 challenger bank.

The existing broad-selection task manifest is a read-only source index.  One
challenger task is derived from each of its 54 generation-pinned projection
bundles.  Every task runs all three population profiles, in registry order,
against one shared R0--R4 visit schedule and publishes three create-once
lineup objects plus one task receipt.

This module does not deploy, read outcomes, score lineups, mutate a graph, or
change a production default.  It deliberately rejects all inherited legacy
stack/game/thesis surfaces before a task can be represented.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as source_manifest,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles


TASK_MANIFEST_SCHEMA: Final = "corpus-r6-population-challenger-task-manifest/v1"
TASK_BINDING_SCHEMA: Final = "corpus-r6-population-challenger-task-binding/v1"
TASK_REQUEST_SCHEMA: Final = "corpus-r6-population-challenger-task-request/v1"
PROFILE_LINEUPS_SCHEMA: Final = "corpus-r6-population-challenger-lineups/v1"
TASK_RESULT_SCHEMA: Final = "corpus-r6-population-challenger-task-result/v1"
SCHEMA_SMOKE_SCHEMA: Final = "corpus-r6-population-challenger-schema-smoke/v1"

TASK_COUNT: Final = contract.PANEL_SLATE_COUNT
PROFILE_COUNT: Final = len(profiles.PROFILE_ORDER)
DEFAULT_WORK: Final = profiles.SharedSolverWork()
SOLVES_PER_PROFILE_PER_SLATE: Final = DEFAULT_WORK.solves_per_profile_per_slate
SOLVES_PER_TASK: Final = PROFILE_COUNT * SOLVES_PER_PROFILE_PER_SLATE
TOTAL_SOLVES: Final = TASK_COUNT * SOLVES_PER_TASK

FIXED_GCP_PROJECT: Final = source_manifest.FIXED_GCP_PROJECT
FIXED_STORAGE_ENDPOINT: Final = source_manifest.FIXED_STORAGE_ENDPOINT
DISPATCHER_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_population_challenger_v1.py"
)
DISPATCHER_IMAGE_PATH: Final = f"/app/{DISPATCHER_RELATIVE_PATH}"
DISPATCHER_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    DISPATCHER_IMAGE_PATH,
    "task",
)
MANIFEST_IDENTITY_ENV: Final = "R6_POPULATION_CHALLENGER_MANIFEST_IDENTITY"
ENABLE_ENV: Final = "R6_POPULATION_CHALLENGER_ENABLE"

MAXIMUM_SOURCE_MANIFEST_BYTES: Final = 16_000_000
MAXIMUM_TASK_MANIFEST_BYTES: Final = 16_000_000
MAXIMUM_PROJECTION_BUNDLE_BYTES: Final = 256_000_000
MAXIMUM_LATER_SOURCE_BYTES: Final = 32_000_000
MAXIMUM_WORLD_ARTIFACT_BYTES: Final = 256_000_000
MAXIMUM_PROFILE_LINEUPS_BYTES: Final = 32_000_000
MAXIMUM_TASK_RESULT_BYTES: Final = 256_000

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_GENERATION_RE: Final = re.compile(r"[1-9][0-9]*\Z")

_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "outcome_fields_read": False,
    "shared_world_schedule_across_profiles": True,
    "equal_solver_work_across_profiles": True,
    "inherited_structure_rules_allowed": False,
    "candidate_family_injection": False,
    "production_change_performed": False,
    "production_default_change_licensed": False,
    "graph_mutation_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
}


class CorpusR6PopulationChallengerAuthorityV1Error(ValueError):
    """The immutable population-challenger authority failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6PopulationChallengerAuthorityV1Error(message)


def canonical_bytes_v1(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6PopulationChallengerAuthorityV1Error(
            "value is not finite canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_bytes_v1(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: canonical_sha256_v1(body)}


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _sha(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _SHA_RE.fullmatch(retained) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return retained


def object_identity_v1(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=f"{label} identity")
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} identity fields differ")
    uri = _string(item["uri"], label=f"{label} URI")
    generation = _string(item["generation"], label=f"{label} generation")
    if not uri.startswith("gs://") or _GENERATION_RE.fullmatch(generation) is None:
        _fail(f"{label} object location/generation differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha(item["sha256"], label=f"{label} SHA-256"),
        "bytes": _integer(item["bytes"], label=f"{label} bytes", minimum=1),
    }


def strict_json_bytes_v1(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6PopulationChallengerAuthorityV1Error(
            f"{label} is not JSON"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_bytes_v1(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def exact_read_json_v1(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = object_identity_v1(identity_value, label=label)
    if identity["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact bytes differ")
    return strict_json_bytes_v1(raw, label=label), identity


def bind_body_to_identity_v1(
    value: Mapping[str, object], identity_value: object, *, label: str
) -> dict[str, object]:
    identity = object_identity_v1(identity_value, label=label)
    raw = canonical_bytes_v1(value)
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail(f"{label} body/content identity differs")
    return identity


def publish_canonical_create_once_v1(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    raw = canonical_bytes_v1(value)
    if not raw or len(raw) > maximum_bytes:
        _fail("create-once object exceeds its exact byte ceiling")
    identity = object_identity_v1(
        publish_create_once(uri, raw), label="create-once publication"
    )
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
        or read_exact(identity) != raw
    ):
        _fail("create-once publication exact reopen differs")
    return identity


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def dispatcher_process_spec_v1() -> dict[str, object]:
    path = _repository_root_v1() / DISPATCHER_RELATIVE_PATH
    if not path.is_file():
        _fail("population challenger dispatcher entrypoint is absent")
    digest = sha256(path.read_bytes()).hexdigest()
    command = list(DISPATCHER_COMMAND)
    return {
        "process_role": "population-challenger-task-dispatcher",
        "entrypoint_path": DISPATCHER_IMAGE_PATH,
        "entrypoint_sha256": digest,
        "command": command,
        "command_sha256": canonical_sha256_v1({
            "command": command,
            "entrypoint_sha256": digest,
        }),
        "one_process_runs_all_profiles_for_one_slate": True,
    }


def _safe_output_prefix(value: object) -> str:
    prefix = _string(value, label="challenger output prefix")
    if not prefix.startswith(contract.OUTPUT_NAMESPACE) or not prefix.endswith("/"):
        _fail("challenger output prefix is outside the fixed research namespace")
    if "?" in prefix or "#" in prefix or "//" in prefix[5:]:
        _fail("challenger output prefix differs")
    if any(part in {"", ".", ".."} for part in prefix[5:-1].split("/")):
        _fail("challenger output prefix path differs")
    return prefix


def _profile_output_uri(prefix: str, source_ordinal: int, profile_id: str) -> str:
    return f"{prefix}slates/{source_ordinal:02d}/{profile_id}/lineups.json"


def _task_result_uri(prefix: str, source_ordinal: int) -> str:
    return f"{prefix}slates/{source_ordinal:02d}/task-result.json"


def _source_task_rows_v1(value: object) -> list[dict[str, object]]:
    try:
        manifest = source_manifest.validate_task_manifest_v1(value)
    except Exception as exc:
        raise CorpusR6PopulationChallengerAuthorityV1Error(
            f"source task manifest is invalid: {exc}"
        ) from exc
    if (
        manifest.get("layer_id") != "broad-selection-receipt"
        or manifest.get("phase") != contract.BROAD_SCREEN_PHASE
        or manifest.get("task_count") != TASK_COUNT
        or manifest.get("uses_realized_outcomes") is not False
        or _mapping(manifest.get("policy"), label="source policy").get(
            "uses_realized_outcomes"
        ) is not False
    ):
        _fail("source manifest is not the 54-slate outcome-blind broad layer")
    bindings = _sequence(manifest.get("task_bindings"), label="source task bindings")
    rows: list[dict[str, object]] = []
    for expected_index, raw in enumerate(bindings):
        binding = _mapping(raw, label=f"source task binding[{expected_index}]")
        request = _mapping(
            binding.get("request"), label=f"source task request[{expected_index}]"
        )
        if (
            binding.get("task_index") != expected_index
            or binding.get("source_ordinal") != expected_index
            or request.get("source_ordinal") != expected_index
            or request.get("phase") != contract.BROAD_SCREEN_PHASE
            or _mapping(
                request.get("policy"), label="source request policy"
            ).get("uses_realized_outcomes") is not False
        ):
            _fail("source task order/policy differs")
        rows.append({
            "source_ordinal": expected_index,
            "source_task_binding_sha256": _sha(
                binding.get("task_binding_sha256"),
                label="source task binding SHA-256",
            ),
            "projection_bundle_identity": object_identity_v1(
                request.get("projection_bundle_identity"),
                label="source projection bundle",
            ),
        })
    if len(rows) != TASK_COUNT:
        _fail("source task count differs")
    return rows


def build_task_manifest_v1(
    *,
    source_task_manifest_identity: object,
    output_prefix: str,
    code_commit: str,
    image_digest: str,
    reused_job_name: str,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build the sole 54-task, three-profile challenger authority."""
    source_body, source_identity = exact_read_json_v1(
        source_task_manifest_identity,
        read_exact=read_exact,
        label="source task manifest",
        maximum_bytes=MAXIMUM_SOURCE_MANIFEST_BYTES,
    )
    source_rows = _source_task_rows_v1(source_body)
    prefix = _safe_output_prefix(output_prefix)
    commit = _string(code_commit, label="code commit")
    digest = _string(image_digest, label="image digest")
    job = _string(reused_job_name, label="reused job name")
    if _COMMIT_RE.fullmatch(commit) is None:
        _fail("code commit must be lowercase 40-hex")
    if not digest.startswith("sha256:") or _SHA_RE.fullmatch(digest[7:]) is None:
        _fail("image digest must be sha256:<lowercase-64-hex>")
    if len(job) > 63 or re.fullmatch(r"[a-z][a-z0-9-]*", job) is None:
        _fail("reused job name differs")

    # No caller-supplied work/profile/legacy options exist at this seam.
    inherited = profiles.InheritedConstraintSurface()
    profiles.require_neutral_inherited_constraints_v1(inherited)
    registry = profiles.population_profile_registry_v1()
    work = DEFAULT_WORK.payload()
    work_sha = canonical_sha256_v1(work)
    process_spec = dispatcher_process_spec_v1()
    task_bindings: list[dict[str, object]] = []
    for row in source_rows:
        index = int(row["source_ordinal"])
        expected_outputs = {
            "profile_lineup_uris": {
                profile_id: _profile_output_uri(prefix, index, profile_id)
                for profile_id in profiles.PROFILE_ORDER
            },
            "task_result_uri": _task_result_uri(prefix, index),
            "create_once": True,
        }
        request = _with_hash({
            "schema": TASK_REQUEST_SCHEMA,
            "task_index": index,
            "source_ordinal": index,
            "source_task_manifest_identity": source_identity,
            "source_task_manifest_sha256": source_body["task_manifest_sha256"],
            "source_task_binding_sha256": row["source_task_binding_sha256"],
            "projection_bundle_identity": row["projection_bundle_identity"],
            "profile_order": list(profiles.PROFILE_ORDER),
            "profile_registry_sha256": registry["registry_sha256"],
            "work_sha256": work_sha,
            "work_sha256_by_profile": {
                profile_id: work_sha for profile_id in profiles.PROFILE_ORDER
            },
            "solves_per_profile": SOLVES_PER_PROFILE_PER_SLATE,
            "total_solves": SOLVES_PER_TASK,
            "inherited_constraint_surface": inherited.payload(),
            "inherited_constraint_conflicts": [],
            "expected_outputs": expected_outputs,
            "code_commit": commit,
            "image_digest": digest,
            "reused_job_name": job,
            "policy": dict(_POLICY),
        }, field="request_sha256")
        task_bindings.append(_with_hash({
            "schema": TASK_BINDING_SCHEMA,
            "task_index": index,
            "source_ordinal": index,
            "request": request,
            "request_sha256": request["request_sha256"],
            "expected_outputs": expected_outputs,
            "expected_outputs_sha256": canonical_sha256_v1(expected_outputs),
            "dispatcher_command": list(DISPATCHER_COMMAND),
            "one_process_runs_all_profiles": True,
        }, field="task_binding_sha256"))

    manifest = _with_hash({
        "schema": TASK_MANIFEST_SCHEMA,
        "source_task_manifest_identity": source_identity,
        "source_task_manifest_sha256": source_body["task_manifest_sha256"],
        "output_prefix": prefix,
        "code_commit": commit,
        "image_digest": digest,
        "reused_job_name": job,
        "dispatcher_process_spec": process_spec,
        "dispatcher_process_spec_sha256": canonical_sha256_v1(process_spec),
        "task_count": TASK_COUNT,
        "profile_count": PROFILE_COUNT,
        "profile_registry": registry,
        "profile_registry_sha256": registry["registry_sha256"],
        "work": work,
        "work_sha256": work_sha,
        "work_sha256_by_profile": {
            profile_id: work_sha for profile_id in profiles.PROFILE_ORDER
        },
        "solves_per_profile_per_slate": SOLVES_PER_PROFILE_PER_SLATE,
        "solves_per_task": SOLVES_PER_TASK,
        "total_solve_attempts": TOTAL_SOLVES,
        "inherited_constraint_surface": inherited.payload(),
        "inherited_constraint_conflicts": [],
        "task_bindings": task_bindings,
        "task_bindings_sha256": canonical_sha256_v1(task_bindings),
        "one_reused_job_for_all_tasks": True,
        "one_process_per_task_runs_all_profiles": True,
        "task_index_selects_exactly_one_request": True,
        "per_profile_deploy_allowed": False,
        "production_default_changes": [],
        "policy": dict(_POLICY),
    }, field="task_manifest_sha256")
    if len(canonical_bytes_v1(manifest)) > MAXIMUM_TASK_MANIFEST_BYTES:
        _fail("challenger task manifest exceeds its byte ceiling")
    return validate_task_manifest_v1(manifest)


def validate_task_request_v1(value: object) -> dict[str, object]:
    request = _mapping(value, label="challenger task request")
    expected = {
        "schema", "task_index", "source_ordinal",
        "source_task_manifest_identity", "source_task_manifest_sha256",
        "source_task_binding_sha256", "projection_bundle_identity",
        "profile_order", "profile_registry_sha256", "work_sha256",
        "work_sha256_by_profile", "solves_per_profile", "total_solves",
        "inherited_constraint_surface", "inherited_constraint_conflicts",
        "expected_outputs", "code_commit", "image_digest", "reused_job_name",
        "policy", "request_sha256",
    }
    if set(request) != expected or request.get("schema") != TASK_REQUEST_SCHEMA:
        _fail("challenger task request fields/schema differ")
    retained_sha = _sha(request["request_sha256"], label="request SHA-256")
    if canonical_sha256_v1({
        key: item for key, item in request.items() if key != "request_sha256"
    }) != retained_sha:
        _fail("challenger task request self-hash differs")
    index = _integer(request["task_index"], label="task index")
    if index >= TASK_COUNT or request["source_ordinal"] != index:
        _fail("challenger task/source ordinal differs")
    object_identity_v1(request["source_task_manifest_identity"], label="source manifest")
    object_identity_v1(request["projection_bundle_identity"], label="projection bundle")
    _sha(
        request["source_task_manifest_sha256"],
        label="request source manifest self-hash",
    )
    _sha(
        request["source_task_binding_sha256"],
        label="request source task binding SHA-256",
    )
    commit = _string(request["code_commit"], label="request code commit")
    image_digest = _string(request["image_digest"], label="request image digest")
    job = _string(request["reused_job_name"], label="request reused job name")
    if (
        _COMMIT_RE.fullmatch(commit) is None
        or not image_digest.startswith("sha256:")
        or _SHA_RE.fullmatch(image_digest[7:]) is None
        or len(job) > 63
        or re.fullmatch(r"[a-z][a-z0-9-]*", job) is None
    ):
        _fail("challenger task code/image/job authority differs")
    registry = profiles.population_profile_registry_v1()
    work_sha = canonical_sha256_v1(DEFAULT_WORK.payload())
    if (
        request["profile_order"] != list(profiles.PROFILE_ORDER)
        or request["profile_registry_sha256"] != registry["registry_sha256"]
        or request["work_sha256"] != work_sha
        or request["work_sha256_by_profile"]
        != {profile_id: work_sha for profile_id in profiles.PROFILE_ORDER}
        or request["solves_per_profile"] != SOLVES_PER_PROFILE_PER_SLATE
        or request["total_solves"] != SOLVES_PER_TASK
        or request["inherited_constraint_surface"]
        != profiles.InheritedConstraintSurface().payload()
        or request["inherited_constraint_conflicts"] != []
        or request["policy"] != _POLICY
    ):
        _fail("challenger task equal-work/safety binding differs")
    outputs = _mapping(request["expected_outputs"], label="expected outputs")
    prefix = str(outputs.get("task_result_uri", "")).rsplit("slates/", 1)[0]
    _safe_output_prefix(prefix)
    if outputs != {
        "profile_lineup_uris": {
            profile_id: _profile_output_uri(prefix, index, profile_id)
            for profile_id in profiles.PROFILE_ORDER
        },
        "task_result_uri": _task_result_uri(prefix, index),
        "create_once": True,
    }:
        _fail("challenger task output binding differs")
    return request


def validate_task_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="challenger task manifest")
    expected = {
        "schema", "source_task_manifest_identity", "source_task_manifest_sha256",
        "output_prefix", "code_commit", "image_digest", "reused_job_name",
        "dispatcher_process_spec", "dispatcher_process_spec_sha256",
        "task_count", "profile_count", "profile_registry",
        "profile_registry_sha256", "work", "work_sha256",
        "work_sha256_by_profile", "solves_per_profile_per_slate",
        "solves_per_task", "total_solve_attempts",
        "inherited_constraint_surface", "inherited_constraint_conflicts",
        "task_bindings", "task_bindings_sha256",
        "one_reused_job_for_all_tasks", "one_process_per_task_runs_all_profiles",
        "task_index_selects_exactly_one_request", "per_profile_deploy_allowed",
        "production_default_changes", "policy", "task_manifest_sha256",
    }
    if set(manifest) != expected or manifest.get("schema") != TASK_MANIFEST_SCHEMA:
        _fail("challenger task manifest fields/schema differ")
    retained_sha = _sha(
        manifest["task_manifest_sha256"], label="task manifest SHA-256"
    )
    if canonical_sha256_v1({
        key: item for key, item in manifest.items()
        if key != "task_manifest_sha256"
    }) != retained_sha:
        _fail("challenger task manifest self-hash differs")
    if len(canonical_bytes_v1(manifest)) > MAXIMUM_TASK_MANIFEST_BYTES:
        _fail("challenger task manifest exceeds its byte ceiling")
    source_identity = object_identity_v1(
        manifest["source_task_manifest_identity"], label="source manifest"
    )
    prefix = _safe_output_prefix(manifest["output_prefix"])
    commit = _string(manifest["code_commit"], label="manifest code commit")
    image_digest = _string(
        manifest["image_digest"], label="manifest image digest"
    )
    job = _string(manifest["reused_job_name"], label="manifest reused job name")
    if (
        _COMMIT_RE.fullmatch(commit) is None
        or not image_digest.startswith("sha256:")
        or _SHA_RE.fullmatch(image_digest[7:]) is None
        or len(job) > 63
        or re.fullmatch(r"[a-z][a-z0-9-]*", job) is None
    ):
        _fail("challenger manifest code/image/job authority differs")
    registry = profiles.population_profile_registry_v1()
    work = DEFAULT_WORK.payload()
    work_sha = canonical_sha256_v1(work)
    process_spec = dispatcher_process_spec_v1()
    if (
        manifest["task_count"] != TASK_COUNT
        or manifest["profile_count"] != PROFILE_COUNT
        or manifest["profile_registry"] != registry
        or manifest["profile_registry_sha256"] != registry["registry_sha256"]
        or manifest["work"] != work
        or manifest["work_sha256"] != work_sha
        or manifest["work_sha256_by_profile"]
        != {profile_id: work_sha for profile_id in profiles.PROFILE_ORDER}
        or manifest["solves_per_profile_per_slate"]
        != SOLVES_PER_PROFILE_PER_SLATE
        or manifest["solves_per_task"] != SOLVES_PER_TASK
        or manifest["total_solve_attempts"] != TOTAL_SOLVES
        or manifest["inherited_constraint_surface"]
        != profiles.InheritedConstraintSurface().payload()
        or manifest["inherited_constraint_conflicts"] != []
        or manifest["dispatcher_process_spec"] != process_spec
        or manifest["dispatcher_process_spec_sha256"]
        != canonical_sha256_v1(process_spec)
        or manifest["one_reused_job_for_all_tasks"] is not True
        or manifest["one_process_per_task_runs_all_profiles"] is not True
        or manifest["task_index_selects_exactly_one_request"] is not True
        or manifest["per_profile_deploy_allowed"] is not False
        or manifest["production_default_changes"] != []
        or manifest["policy"] != _POLICY
    ):
        _fail("challenger task manifest fixed authority differs")
    # The source object's content SHA and its internal manifest self-hash are
    # deliberately distinct.  ``build_task_manifest_v1`` exact-opens and
    # validates both; retaining both here prevents either from being confused
    # for the other during dispatcher replay.
    _sha(
        manifest["source_task_manifest_sha256"],
        label="source task manifest self-hash",
    )
    bindings = _sequence(manifest["task_bindings"], label="challenger task bindings")
    if (
        len(bindings) != TASK_COUNT
        or manifest["task_bindings_sha256"] != canonical_sha256_v1(bindings)
    ):
        _fail("challenger task binding count/hash differs")
    seen_projection_identities: set[str] = set()
    for expected_index, raw in enumerate(bindings):
        binding = _mapping(raw, label=f"challenger task binding[{expected_index}]")
        if set(binding) != {
            "schema", "task_index", "source_ordinal", "request",
            "request_sha256", "expected_outputs", "expected_outputs_sha256",
            "dispatcher_command", "one_process_runs_all_profiles",
            "task_binding_sha256",
        } or binding.get("schema") != TASK_BINDING_SCHEMA:
            _fail("challenger task binding fields/schema differ")
        binding_sha = _sha(
            binding["task_binding_sha256"], label="task binding SHA-256"
        )
        if canonical_sha256_v1({
            key: item for key, item in binding.items()
            if key != "task_binding_sha256"
        }) != binding_sha:
            _fail("challenger task binding self-hash differs")
        request = validate_task_request_v1(binding["request"])
        if (
            request["task_index"] != expected_index
            or request["source_task_manifest_identity"] != source_identity
            or request["source_task_manifest_sha256"]
            != manifest["source_task_manifest_sha256"]
            or request["code_commit"] != manifest["code_commit"]
            or request["image_digest"] != manifest["image_digest"]
            or request["reused_job_name"] != manifest["reused_job_name"]
            or binding["task_index"] != expected_index
            or binding["source_ordinal"] != expected_index
            or binding["request_sha256"] != request["request_sha256"]
            or binding["expected_outputs"] != request["expected_outputs"]
            or binding["expected_outputs_sha256"]
            != canonical_sha256_v1(request["expected_outputs"])
            or binding["dispatcher_command"] != list(DISPATCHER_COMMAND)
            or binding["one_process_runs_all_profiles"] is not True
        ):
            _fail("challenger task binding cross-authority differs")
        if not str(request["expected_outputs"]["task_result_uri"]).startswith(
            prefix
        ):
            _fail("challenger task output escapes manifest prefix")
        projection_key = canonical_sha256_v1(request["projection_bundle_identity"])
        if projection_key in seen_projection_identities:
            _fail("challenger projection identity repeats")
        seen_projection_identities.add(projection_key)
    return manifest


def task_request_v1(value: object, *, task_index: int) -> dict[str, object]:
    manifest = validate_task_manifest_v1(value)
    index = _integer(task_index, label="task index")
    if index >= TASK_COUNT:
        _fail("task index is outside the 54-slate authority")
    request = validate_task_request_v1(manifest["task_bindings"][index]["request"])
    if request["task_index"] != index:
        _fail("task index did not select exactly one request")
    return request


def validate_outcome_blind_schema_projection_v1(value: object) -> dict[str, object]:
    """Validate a metadata-only projection of real source artifacts.

    The caller projects these fields before invoking this validator; candidate
    arrays, simulated score matrices, and all realized outcome fields are not
    members of this schema and therefore cannot be inspected here.
    """
    smoke = _mapping(value, label="outcome-blind schema projection")
    expected = {
        "schema", "source_manifest", "projection_bundle", "later_source",
        "outcome_or_score_values_read", "smoke_sha256",
    }
    if set(smoke) != expected or smoke.get("schema") != SCHEMA_SMOKE_SCHEMA:
        _fail("outcome-blind schema projection fields differ")
    retained_sha = _sha(smoke["smoke_sha256"], label="schema smoke SHA-256")
    if canonical_sha256_v1({
        key: item for key, item in smoke.items() if key != "smoke_sha256"
    }) != retained_sha:
        _fail("outcome-blind schema projection self-hash differs")
    source = _mapping(smoke["source_manifest"], label="smoke source manifest")
    projection = _mapping(
        smoke["projection_bundle"], label="smoke projection bundle"
    )
    later = _mapping(smoke["later_source"], label="smoke later source")
    if set(source) != {
        "schema_version", "layer_id", "phase", "task_count",
        "uses_realized_outcomes", "task_manifest_sha256",
    } or (
        source["schema_version"] != source_manifest.TASK_MANIFEST_SCHEMA
        or source["layer_id"] != "broad-selection-receipt"
        or source["phase"] != contract.BROAD_SCREEN_PHASE
        or source["task_count"] != TASK_COUNT
        or source["uses_realized_outcomes"] is not False
    ):
        _fail("real source manifest metadata shape differs")
    if set(projection) != {
        "schema_version", "slate_id", "source_ordinal", "fold_count",
        "fold_order", "uses_realized_outcomes", "historical_scoring_performed",
        "later_source_identity", "world_artifact_identities",
        "projection_bundle_sha256",
    } or (
        projection["schema_version"] != contract.PROJECTION_BUNDLE_SCHEMA
        or projection["fold_count"] != contract.FOLDS_PER_SLATE
        or projection["fold_order"] != list(contract.WORLD_BLOCKS)
        or projection["uses_realized_outcomes"] is not False
        or projection["historical_scoring_performed"] is not False
    ):
        _fail("real projection-bundle metadata shape differs")
    object_identity_v1(projection["later_source_identity"], label="smoke later source")
    world_identities = _mapping(
        projection["world_artifact_identities"], label="smoke world artifacts"
    )
    if list(world_identities) != [
        f"world_artifact_{block.casefold()}" for block in contract.WORLD_BLOCKS
    ]:
        _fail("real projection world-artifact order differs")
    for block, identity in world_identities.items():
        object_identity_v1(identity, label=f"smoke {block}")
    if set(later) != {
        "schema", "slate_count", "uses_realized_outcomes",
        "historical_scoring_licensed", "candidate_or_lineup_scores_read",
        "slate_id", "season", "week", "catalog_count", "artifact_blocks",
    } or (
        later["schema"] != "lr8-later-period-source-freeze-v1"
        or later["slate_count"] != TASK_COUNT
        or later["uses_realized_outcomes"] is not False
        or later["historical_scoring_licensed"] is not False
        or later["candidate_or_lineup_scores_read"] is not False
        or later["slate_id"] != projection["slate_id"]
        or later["artifact_blocks"] != list(contract.WORLD_BLOCKS)
    ):
        _fail("real later-source metadata shape differs")
    if smoke["outcome_or_score_values_read"] is not False:
        _fail("schema smoke is not outcome/score blind")
    return smoke


def build_outcome_blind_schema_projection_v1(
    *,
    source_manifest_metadata: Mapping[str, object],
    projection_bundle_metadata: Mapping[str, object],
    later_source_metadata: Mapping[str, object],
) -> dict[str, object]:
    return validate_outcome_blind_schema_projection_v1(_with_hash({
        "schema": SCHEMA_SMOKE_SCHEMA,
        "source_manifest": dict(source_manifest_metadata),
        "projection_bundle": dict(projection_bundle_metadata),
        "later_source": dict(later_source_metadata),
        "outcome_or_score_values_read": False,
    }, field="smoke_sha256"))


__all__ = [
    "CorpusR6PopulationChallengerAuthorityV1Error",
    "DEFAULT_WORK",
    "DISPATCHER_COMMAND",
    "DISPATCHER_IMAGE_PATH",
    "DISPATCHER_RELATIVE_PATH",
    "ENABLE_ENV",
    "FIXED_GCP_PROJECT",
    "FIXED_STORAGE_ENDPOINT",
    "MANIFEST_IDENTITY_ENV",
    "MAXIMUM_LATER_SOURCE_BYTES",
    "MAXIMUM_PROFILE_LINEUPS_BYTES",
    "MAXIMUM_PROJECTION_BUNDLE_BYTES",
    "MAXIMUM_TASK_MANIFEST_BYTES",
    "MAXIMUM_TASK_RESULT_BYTES",
    "MAXIMUM_WORLD_ARTIFACT_BYTES",
    "PROFILE_LINEUPS_SCHEMA",
    "SCHEMA_SMOKE_SCHEMA",
    "SOLVES_PER_PROFILE_PER_SLATE",
    "SOLVES_PER_TASK",
    "TASK_COUNT",
    "TASK_MANIFEST_SCHEMA",
    "TASK_RESULT_SCHEMA",
    "TOTAL_SOLVES",
    "bind_body_to_identity_v1",
    "build_outcome_blind_schema_projection_v1",
    "build_task_manifest_v1",
    "canonical_bytes_v1",
    "canonical_sha256_v1",
    "dispatcher_process_spec_v1",
    "exact_read_json_v1",
    "object_identity_v1",
    "publish_canonical_create_once_v1",
    "strict_json_bytes_v1",
    "task_request_v1",
    "validate_outcome_blind_schema_projection_v1",
    "validate_task_manifest_v1",
    "validate_task_request_v1",
]
