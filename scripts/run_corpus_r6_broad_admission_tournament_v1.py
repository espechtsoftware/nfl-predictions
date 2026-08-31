#!/usr/bin/env python3
"""Execute the fixed-corpus A250/A500 broad-admission tournament.

The six commands in this file form two deliberately separated state machines.
``prepare/task/collect/reopen`` are outcome-blind and freeze the complete
54-slate admission lattice.  ``grade/grade-reopen`` can run only after that
lattice has been deeply replayed.  The grade path accepts only the recognized
catalog completion plus its live historical-outcome lease, and grade-reopen
uses only persisted derived score documents (never the catalog or lease).

This runner never creates or updates a Cloud Run job and never launches an
execution.  It has no list, overwrite, delete, retry, or policy-promotion
surface.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Final, Protocol


ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from scripts import run_corpus_r6_combined_frontier_reportfolio_v1 as parent  # noqa: E402
from scripts import run_corpus_r6_construction_allocation_grade_v1 as grade_runner  # noqa: E402
from nfl_dfs.research import corpus_r6_broad_admission_program_v1 as program  # noqa: E402
from nfl_dfs.research import corpus_r6_broad_admission_tournament_v1 as core  # noqa: E402
from nfl_dfs.research import corpus_r6_construction_allocation_cross_operator_v1 as runtime_contract  # noqa: E402
from nfl_dfs.research import corpus_r6_construction_allocation_grade_operator_v1 as recognized_outcomes  # noqa: E402
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as roster_grader  # noqa: E402


TASK_COUNT: Final = 54
PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
FIXED_REUSED_JOB_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1"
FIXED_REUSED_JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
OUTPUT_ROOT: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-broad-admission/"
)

FROZEN_COMBINED_TERMINAL_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-combined-population-all-block/"
        "20260829-score-sprint-170b7b4e-v2/full54/full-54/"
        "descriptive-terminal-v2.json"
    ),
    "generation": "1787999967997744",
    "sha256": "f6f2679f44032246508ac5905b51d53d4a3f1f178d15103a203d488017a796d1",
    "bytes": 35_870,
}
FROZEN_FRONTIER_MANIFEST_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-combined-frontier-reportfolio/"
        "20260829-score-sprint-28db339e-v1/full54/manifest.json"
    ),
    "generation": "1788029467812121",
    "sha256": "206a4dde7203bbd62b1ff6c6beee10ece26580c51650732132a0a7f8df08f114",
    "bytes": 55_096,
}

MANIFEST_SCHEMA: Final = "corpus-r6-broad-admission-execution-manifest/v1"
RUNTIME_AUTHORITY_SCHEMA: Final = "corpus-r6-broad-admission-runtime-authority/v1"
TASK_SCHEMA: Final = "corpus-r6-broad-admission-execution-task/v1"
SMOKE_SCHEMA: Final = "corpus-r6-broad-admission-task0-smoke/v1"
TERMINAL_SCHEMA: Final = "corpus-r6-broad-admission-execution-terminal/v1"
SCORE_SCHEMA: Final = "corpus-r6-broad-admission-realized-scores/v1"
GRADE_TERMINAL_SCHEMA: Final = "corpus-r6-broad-admission-grade-terminal/v1"

ENABLE_ENV: Final = "R6_BROAD_ADMISSION_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_FIXED_CORPUS_ADMISSION_TOURNAMENT_V1"
OUTCOMES_ALLOWED_ENV: Final = "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED"
REQUEST_B64_ENV: Final = "R6_BROAD_ADMISSION_REQUEST_B64"
REQUEST_SHA256_ENV: Final = "R6_BROAD_ADMISSION_REQUEST_SHA256"
TASK0_SMOKE_ENV: Final = "R6_BROAD_ADMISSION_TASK0_SMOKE"
BOUND_IDENTITY_ENV: Final = "R6_BROAD_ADMISSION_BOUND_IDENTITY"
CODE_SHA_ENV: Final = "CODE_SHA"
IMAGE_DIGEST_ENV: Final = "IMAGE_DIGEST"
IMAGE_URI_ENV: Final = "IMAGE_URI"
BUILD_ID_ENV: Final = "BUILD_ID"

MAX_REQUEST_BYTES: Final = 2_000_000
MAX_MANIFEST_BYTES: Final = 4_000_000
MAX_TASK_BYTES: Final = 128_000_000
MAX_TERMINAL_BYTES: Final = 4_000_000
MAX_SCORE_BYTES: Final = 64_000_000
MAX_GRADE_BYTES: Final = 256_000_000
MAX_CLOSURE_BYTES: Final = 4_000_000

_SHA = re.compile(r"^[0-9a-f]{64}$")
_GENERATION = re.compile(r"^[0-9]+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BUILD_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_EXECUTION = re.compile(r"^[a-z][a-z0-9-]{2,100}$")


class BroadAdmissionRunnerV1Error(RuntimeError):
    """An immutable authority, execution fact, or replay differed."""


class ExactStore(Protocol):
    def read_exact(self, identity: Mapping[str, object]) -> bytes: ...
    def open_known(self, uri: str, maximum_bytes: int) -> tuple[bytes, Mapping[str, object]]: ...
    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]: ...


class ExecutionProvider(Protocol):
    def status(
        self, execution_id: str, *, manifest: Mapping[str, object],
        manifest_identity: Mapping[str, object],
    ) -> Mapping[str, object]: ...


def _fail(message: str) -> None:
    raise BroadAdmissionRunnerV1Error(message)


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
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BroadAdmissionRunnerV1Error("canonical JSON differs") from exc


def _document(value: object) -> bytes:
    return _canonical(value) + b"\n"


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: _hash(body)}


def _validate_self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    body = dict(value)
    retained = body.pop(field, None)
    if type(retained) is not str or _SHA.fullmatch(retained) is None or retained != _hash(body):
        _fail(f"{label} self-hash differs")


def _identity(
    value: object, *, label: str, expected_uri: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) not in (
        {"uri", "generation", "sha256", "bytes"},
        {"uri", "generation", "sha256", "bytes", "create_once"},
    ):
        _fail(f"{label} content-identity fields differ")
    uri, generation = item.get("uri"), item.get("generation")
    digest, size = item.get("sha256"), item.get("bytes")
    if (
        type(uri) is not str or not uri.startswith("gs://")
        or (expected_uri is not None and uri != expected_uri)
        or type(generation) not in {str, int}
        or _GENERATION.fullmatch(str(generation)) is None
        or int(str(generation)) <= 0
        or type(digest) is not str or _SHA.fullmatch(digest) is None
        or type(size) is not int or size <= 0
        or ("create_once" in item and item["create_once"] is not True)
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri, "generation": str(generation), "sha256": digest,
        "bytes": size,
    }


def _parse_document(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BroadAdmissionRunnerV1Error(f"{label} is not JSON") from exc
    body = _mapping(value, label=label)
    if raw not in {_canonical(body), _document(body)}:
        _fail(f"{label} canonical JSON replay differs")
    return body


def _read(
    identity_value: object, *, store: ExactStore, label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if identity["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    try:
        raw = store.read_exact(identity)
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error(f"{label} generation-exact read failed") from exc
    if (
        type(raw) is not bytes or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact bytes differ")
    return _parse_document(raw, label=label), identity


def _open_known(
    uri: str, *, store: ExactStore, label: str, maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        raw, observed = store.open_known(uri, maximum_bytes)
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error(f"{label} known-name open failed") from exc
    identity = _identity(observed, label=f"{label} identity", expected_uri=uri)
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail(f"{label} known-name bytes differ")
    return _parse_document(raw, label=label), identity


def _publish(
    uri: str, value: Mapping[str, object], *, store: ExactStore,
    maximum_bytes: int,
) -> dict[str, object]:
    raw = _document(dict(value))
    if len(raw) > maximum_bytes:
        _fail("create-once publication exceeds its byte ceiling")
    try:
        published = store.publish_create_once(uri, raw)
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error(f"create-once publication failed for {uri}") from exc
    identity = _identity(published, label="create-once publication", expected_uri=uri)
    if (
        not isinstance(published, Mapping) or published.get("create_once") is not True
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail("create-once publication receipt differs")
    reopened = store.read_exact(identity)
    if reopened != raw:
        _fail("create-once publication exact reopen differs")
    return identity


def _output_prefix(value: object) -> str:
    if (
        type(value) is not str or not value.startswith(OUTPUT_ROOT)
        or not value.endswith("/") or "//" in value[5:]
        or any(part in {"", ".", ".."} for part in value[5:].split("/")[:-1])
    ):
        _fail("broad-admission output prefix differs")
    return value


def _image_digest(immutable_image: object) -> str:
    if type(immutable_image) is not str or "@" not in immutable_image:
        _fail("immutable image differs")
    digest = immutable_image.rsplit("@", 1)[1]
    if _IMAGE.fullmatch(digest) is None:
        _fail("immutable image digest differs")
    return digest


def _validate_build_attestation(
    identity_value: object, *, code_sha: str, image_digest: str,
    store: ExactStore,
) -> tuple[dict[str, object], dict[str, object]]:
    body, identity = _read(
        identity_value, store=store, label="runtime build attestation",
        maximum_bytes=256_000,
    )
    try:
        retained = runtime_contract.validate_runtime_build_attestation_v1(
            body, expected_code_sha=code_sha,
            expected_image_digest=image_digest,
        )
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error(str(exc)) from exc
    return retained, identity


def _task_uri(prefix: str, ordinal: int) -> str:
    return f"{prefix}slates/{ordinal:02d}/score-free-package.json"


def _score_uri(prefix: str, ordinal: int) -> str:
    return f"{prefix}slates/{ordinal:02d}/realized-scores.json"


def _manifest_body(
    *, combined_identity: Mapping[str, object], combined_terminal: Mapping[str, object],
    frontier_identity: Mapping[str, object], frontier_manifest: Mapping[str, object],
    build_identity: Mapping[str, object], build_attestation: Mapping[str, object],
    code_sha: str, immutable_image: str, output_prefix: str,
) -> dict[str, object]:
    prefix = _output_prefix(output_prefix)
    bindings = [{
        "source_ordinal": ordinal,
        "slate_id": slate_id,
        "frontier_task_binding_sha256": frontier_manifest["task_bindings"][ordinal][
            "task_binding_sha256"
        ],
        "result_uri": _task_uri(prefix, ordinal),
        "score_uri": _score_uri(prefix, ordinal),
    } for ordinal, slate_id in enumerate(program.EXPECTED_SLATE_IDS)]
    return _with_hash({
        "schema_version": MANIFEST_SCHEMA,
        "combined_terminal_identity": dict(combined_identity),
        "combined_terminal_sha256": combined_terminal["terminal_sha256"],
        "frontier_manifest_identity": dict(frontier_identity),
        "frontier_manifest_sha256": frontier_manifest["manifest_sha256"],
        "runtime_build_attestation_identity": dict(build_identity),
        "runtime_build_attestation_sha256": build_attestation[
            "runtime_build_attestation_sha256"
        ],
        "build_id": build_attestation["build_id"],
        "code_sha": code_sha,
        "immutable_image": immutable_image,
        "image_digest": _image_digest(immutable_image),
        "output_prefix": prefix,
        "manifest_uri": f"{prefix}manifest.json",
        "task_count": TASK_COUNT,
        "project_id": PROJECT,
        "region": REGION,
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "task_bindings": bindings,
        "task_bindings_sha256": _hash(bindings),
        "terminal_uri": f"{prefix}full-54/terminal.json",
        "outcome_closure_uri": f"{prefix}full-54/outcome-closure.json",
        "program_grade_uri": f"{prefix}full-54/program-grade.json",
        "grade_terminal_uri": f"{prefix}full-54/grade-terminal.json",
        "fixed_corpus": True,
        "admission_budgets": list(core.ADMISSION_BUDGETS),
        "uses_realized_outcomes": False,
        "candidate_generation_performed": False,
        "k80_selection_performed": False,
        "automatic_policy_promotion": False,
        "production_change_licensed": False,
    }, field="manifest_sha256")


def _validate_manifest(value: object) -> dict[str, object]:
    item = _mapping(value, label="broad-admission manifest")
    expected_fields = {
        "schema_version", "combined_terminal_identity", "combined_terminal_sha256",
        "frontier_manifest_identity", "frontier_manifest_sha256",
        "runtime_build_attestation_identity", "runtime_build_attestation_sha256",
        "build_id", "code_sha", "immutable_image", "image_digest",
        "output_prefix", "manifest_uri", "task_count", "project_id", "region",
        "reused_job_name", "reused_job_uid", "task_bindings",
        "task_bindings_sha256", "terminal_uri", "outcome_closure_uri",
        "program_grade_uri", "grade_terminal_uri", "fixed_corpus",
        "admission_budgets", "uses_realized_outcomes",
        "candidate_generation_performed", "k80_selection_performed",
        "automatic_policy_promotion", "production_change_licensed",
        "manifest_sha256",
    }
    _validate_self_hash(item, field="manifest_sha256", label="manifest")
    prefix = _output_prefix(item.get("output_prefix"))
    bindings = [_mapping(row, label="manifest task binding") for row in _sequence(
        item.get("task_bindings"), label="manifest task bindings"
    )]
    if (
        set(item) != expected_fields or item.get("schema_version") != MANIFEST_SCHEMA
        or item.get("combined_terminal_identity") != FROZEN_COMBINED_TERMINAL_IDENTITY
        or item.get("frontier_manifest_identity") != FROZEN_FRONTIER_MANIFEST_IDENTITY
        or _COMMIT.fullmatch(str(item.get("code_sha", ""))) is None
        or item.get("image_digest") != _image_digest(item.get("immutable_image"))
        or _BUILD_ID.fullmatch(str(item.get("build_id", ""))) is None
        or item.get("manifest_uri") != f"{prefix}manifest.json"
        or item.get("task_count") != TASK_COUNT
        or item.get("project_id") != PROJECT or item.get("region") != REGION
        or item.get("reused_job_name") != FIXED_REUSED_JOB_NAME
        or item.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or len(bindings) != TASK_COUNT
        or item.get("task_bindings_sha256") != _hash(bindings)
        or item.get("terminal_uri") != f"{prefix}full-54/terminal.json"
        or item.get("outcome_closure_uri") != f"{prefix}full-54/outcome-closure.json"
        or item.get("program_grade_uri") != f"{prefix}full-54/program-grade.json"
        or item.get("grade_terminal_uri") != f"{prefix}full-54/grade-terminal.json"
        or item.get("fixed_corpus") is not True
        or item.get("admission_budgets") != list(core.ADMISSION_BUDGETS)
        or item.get("uses_realized_outcomes") is not False
        or item.get("candidate_generation_performed") is not False
        or item.get("k80_selection_performed") is not False
        or item.get("automatic_policy_promotion") is not False
        or item.get("production_change_licensed") is not False
    ):
        _fail("broad-admission manifest authority differs")
    for ordinal, (slate_id, binding) in enumerate(zip(
        program.EXPECTED_SLATE_IDS, bindings, strict=True
    )):
        if (
            set(binding) != {
                "source_ordinal", "slate_id", "frontier_task_binding_sha256",
                "result_uri", "score_uri",
            }
            or binding.get("source_ordinal") != ordinal
            or binding.get("slate_id") != slate_id
            or _SHA.fullmatch(str(binding.get("frontier_task_binding_sha256", ""))) is None
            or binding.get("result_uri") != _task_uri(prefix, ordinal)
            or binding.get("score_uri") != _score_uri(prefix, ordinal)
        ):
            _fail(f"manifest task binding[{ordinal}] differs")
    return item


def _open_manifest(
    identity_value: object, *, store: ExactStore,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    manifest, identity = _read(
        identity_value, store=store, label="broad-admission manifest",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    retained = _validate_manifest(manifest)
    if identity["uri"] != retained["manifest_uri"]:
        _fail("broad-admission manifest outer URI differs")
    build, build_identity = _validate_build_attestation(
        retained["runtime_build_attestation_identity"],
        code_sha=str(retained["code_sha"]),
        image_digest=str(retained["image_digest"]), store=store,
    )
    if (
        build_identity != retained["runtime_build_attestation_identity"]
        or build["runtime_build_attestation_sha256"]
        != retained["runtime_build_attestation_sha256"]
        or build["build_id"] != retained["build_id"]
    ):
        _fail("manifest runtime-build binding differs")
    frontier, frontier_identity = parent._open_manifest(
        retained["frontier_manifest_identity"], store=store
    )
    combined, combined_identity = parent._open_predecessor_terminal(
        retained["combined_terminal_identity"], store=store
    )
    if (
        frontier_identity != FROZEN_FRONTIER_MANIFEST_IDENTITY
        or combined_identity != FROZEN_COMBINED_TERMINAL_IDENTITY
        or frontier["manifest_sha256"] != retained["frontier_manifest_sha256"]
        or combined["terminal_sha256"] != retained["combined_terminal_sha256"]
        or frontier["predecessor_terminal_identity"] != combined_identity
        or len(frontier["task_bindings"]) != TASK_COUNT
        or [row["slate_id"] for row in frontier["task_bindings"]]
        != list(program.EXPECTED_SLATE_IDS)
        or any(
            retained["task_bindings"][ordinal]["frontier_task_binding_sha256"]
            != frontier["task_bindings"][ordinal]["task_binding_sha256"]
            for ordinal in range(TASK_COUNT)
        )
    ):
        _fail("manifest immutable-parent replay differs")
    return retained, identity, frontier


def prepare_from_request_v1(
    request: Mapping[str, object], *, store: ExactStore,
) -> dict[str, object]:
    item = _mapping(request, label="broad-admission prepare request")
    if set(item) != {
        "combined_terminal_identity", "frontier_manifest_identity",
        "runtime_build_attestation_identity", "code_sha", "immutable_image",
        "output_prefix",
    }:
        _fail("prepare request fields differ")
    combined_expected = _identity(item["combined_terminal_identity"], label="combined terminal")
    frontier_expected = _identity(item["frontier_manifest_identity"], label="frontier manifest")
    if (
        combined_expected != FROZEN_COMBINED_TERMINAL_IDENTITY
        or frontier_expected != FROZEN_FRONTIER_MANIFEST_IDENTITY
        or _COMMIT.fullmatch(str(item.get("code_sha", ""))) is None
    ):
        _fail("prepare frozen authority differs")
    digest = _image_digest(item.get("immutable_image"))
    # Validate every authority before the first write.
    combined, combined_identity = parent._open_predecessor_terminal(
        combined_expected, store=store
    )
    frontier, frontier_identity = parent._open_manifest(frontier_expected, store=store)
    build, build_identity = _validate_build_attestation(
        item["runtime_build_attestation_identity"],
        code_sha=str(item["code_sha"]), image_digest=digest, store=store,
    )
    if (
        combined_identity != combined_expected or frontier_identity != frontier_expected
        or frontier["predecessor_terminal_identity"] != combined_identity
        or frontier["predecessor_terminal_sha256"] != combined["terminal_sha256"]
        or len(frontier["task_bindings"]) != TASK_COUNT
        or [row["slate_id"] for row in frontier["task_bindings"]]
        != list(program.EXPECTED_SLATE_IDS)
    ):
        _fail("prepare immutable parent binding differs")
    manifest = _manifest_body(
        combined_identity=combined_identity, combined_terminal=combined,
        frontier_identity=frontier_identity, frontier_manifest=frontier,
        build_identity=build_identity, build_attestation=build,
        code_sha=str(item["code_sha"]), immutable_image=str(item["immutable_image"]),
        output_prefix=str(item["output_prefix"]),
    )
    identity = _publish(
        str(manifest["manifest_uri"]), manifest, store=store,
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    reopened, reopened_identity, _ = _open_manifest(identity, store=store)
    if reopened != manifest or reopened_identity != identity:
        _fail("prepared manifest exact reopen differs")
    return _with_hash({
        "schema_version": "corpus-r6-broad-admission-prepare-result/v1",
        "manifest_identity": identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "task_count": TASK_COUNT,
        "build_id": build["build_id"],
        "all_nonpublication_authorities_validated_before_first_write": True,
        "uses_realized_outcomes": False,
        "execution_launched": False,
        "deployment_mutation_performed": False,
        "complete": True,
    }, field="prepare_result_sha256")


def _runtime_authority(
    *, manifest: Mapping[str, object], manifest_identity: Mapping[str, object],
    environment: Mapping[str, str], ordinal: int,
) -> dict[str, object]:
    try:
        bound_raw = environment.get(BOUND_IDENTITY_ENV, "")
        bound = _identity(json.loads(bound_raw), label="runtime bound identity")
    except (TypeError, json.JSONDecodeError) as exc:
        raise BroadAdmissionRunnerV1Error("runtime bound identity differs") from exc
    if bound != dict(manifest_identity) or bound_raw.encode("utf-8") != _canonical(bound):
        _fail("runtime bound identity differs")
    if (
        environment.get(ENABLE_ENV) != ENABLE_VALUE
        or environment.get(OUTCOMES_ALLOWED_ENV) != "false"
        or environment.get(CODE_SHA_ENV) != manifest["code_sha"]
        or environment.get(IMAGE_DIGEST_ENV) != manifest["image_digest"]
        or environment.get(IMAGE_URI_ENV) != manifest["immutable_image"]
        or environment.get(BUILD_ID_ENV) != manifest["build_id"]
        or environment.get("CLOUD_RUN_JOB") != FIXED_REUSED_JOB_NAME
        or environment.get("CLOUD_RUN_TASK_INDEX") != str(ordinal)
        or environment.get("CLOUD_RUN_TASK_COUNT") != str(TASK_COUNT)
        or environment.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
        or _EXECUTION.fullmatch(environment.get("CLOUD_RUN_EXECUTION", "")) is None
    ):
        _fail("reserved Cloud Run task authority differs")
    return _with_hash({
        "schema_version": RUNTIME_AUTHORITY_SCHEMA,
        "project_id": PROJECT, "region": REGION,
        "job_name": FIXED_REUSED_JOB_NAME, "reused_job_uid": FIXED_REUSED_JOB_UID,
        "execution_id": environment["CLOUD_RUN_EXECUTION"],
        "source_ordinal": ordinal, "task_count": TASK_COUNT, "task_attempt": 0,
        "manifest_identity": dict(manifest_identity),
        "manifest_sha256": manifest["manifest_sha256"],
        "code_sha": manifest["code_sha"], "image_digest": manifest["image_digest"],
        "build_id": manifest["build_id"], "immutable_image": manifest["immutable_image"],
        "authority_source": "reserved-cloud-run-metadata-and-frozen-job-uid",
    }, field="runtime_authority_sha256")


def _validate_runtime_authority(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object], ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label="task runtime authority")
    _validate_self_hash(item, field="runtime_authority_sha256", label="runtime authority")
    if (
        set(item) != {
            "schema_version", "project_id", "region", "job_name", "reused_job_uid",
            "execution_id", "source_ordinal", "task_count", "task_attempt",
            "manifest_identity", "manifest_sha256", "code_sha", "image_digest",
            "build_id", "immutable_image", "authority_source", "runtime_authority_sha256",
        }
        or item.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or item.get("project_id") != PROJECT or item.get("region") != REGION
        or item.get("job_name") != FIXED_REUSED_JOB_NAME
        or item.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or _EXECUTION.fullmatch(str(item.get("execution_id", ""))) is None
        or item.get("source_ordinal") != ordinal or item.get("task_count") != TASK_COUNT
        or item.get("task_attempt") != 0
        or item.get("manifest_identity") != dict(manifest_identity)
        or item.get("manifest_sha256") != manifest["manifest_sha256"]
        or item.get("code_sha") != manifest["code_sha"]
        or item.get("image_digest") != manifest["image_digest"]
        or item.get("build_id") != manifest["build_id"]
        or item.get("immutable_image") != manifest["immutable_image"]
        or item.get("authority_source")
        != "reserved-cloud-run-metadata-and-frozen-job-uid"
    ):
        _fail("task runtime authority differs")
    return item


def _project_union_rows(science: Mapping[str, object]) -> list[dict[str, object]]:
    union = _mapping(science.get("union"), label="combined science union")
    rows = []
    for raw in _sequence(union.get("union_lineups"), label="combined union lineups"):
        row = _mapping(raw, label="combined union lineup")
        lineup_id = row.get("lineup_id")
        roster = row.get("roster_player_ids")
        if type(lineup_id) is not str or not isinstance(roster, list):
            _fail("combined union lineup surface differs")
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster),
            "roster_sha256": _hash(list(roster)),
        })
    if not rows or [row["lineup_id"] for row in rows] != sorted({
        str(row["lineup_id"]) for row in rows
    }):
        _fail("combined union lineup projection differs")
    return rows


def _rebuild_task_science(
    *, manifest: Mapping[str, object], frontier: Mapping[str, object],
    ordinal: int, store: ExactStore,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    predecessor, predecessor_identity, matrix = parent._reconstruct_predecessor_matrix_v1(
        manifest=frontier, source_ordinal=ordinal, store=store
    )
    science = _mapping(predecessor.get("science_result"), label="combined science result")
    freeze = core.freeze_combined_slate_inputs_v1(
        combined_result=science, all_block_score_matrix=matrix,
        source_ordinal=ordinal,
    )
    package = program.build_score_free_slate_package_v1(
        freeze, source_ordinal=ordinal
    )
    return package, predecessor_identity, _project_union_rows(science), science


def _task_body(
    *, manifest: Mapping[str, object], manifest_identity: Mapping[str, object],
    frontier: Mapping[str, object], ordinal: int, environment: Mapping[str, str],
    store: ExactStore, smoke: bool,
) -> dict[str, object]:
    package, predecessor_identity, lineups, science = _rebuild_task_science(
        manifest=manifest, frontier=frontier, ordinal=ordinal, store=store
    )
    runtime = _runtime_authority(
        manifest=manifest, manifest_identity=manifest_identity,
        environment=environment, ordinal=ordinal,
    )
    union = _mapping(science["union"], label="combined science union")
    return _with_hash({
        "schema_version": TASK_SCHEMA,
        "manifest_identity": dict(manifest_identity),
        "manifest_sha256": manifest["manifest_sha256"],
        "source_ordinal": ordinal, "slate_id": package["slate_id"],
        "runtime_authority": runtime,
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "predecessor_task_result_identity": predecessor_identity,
        "predecessor_science_result_sha256": science["result_sha256"],
        "predecessor_union_sha256": union["union_sha256"],
        "score_free_package": package,
        "package_sha256": package["package_sha256"],
        "union_lineup_count": len(lineups),
        "union_lineups": lineups,
        "union_lineups_sha256": _hash(lineups),
        "task0_smoke": smoke,
        "publication_performed": not smoke,
        "uses_realized_outcomes": False,
        "candidate_generation_performed": False,
        "k80_selection_performed": False,
    }, field="task_result_sha256")


def _validate_task_result(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object], frontier: Mapping[str, object],
    ordinal: int, store: ExactStore,
) -> dict[str, object]:
    item = _mapping(value, label=f"broad-admission task[{ordinal}]")
    _validate_self_hash(item, field="task_result_sha256", label=f"task[{ordinal}]")
    expected_fields = {
        "schema_version", "manifest_identity", "manifest_sha256", "source_ordinal",
        "slate_id", "runtime_authority", "runtime_authority_sha256",
        "predecessor_task_result_identity", "predecessor_science_result_sha256",
        "predecessor_union_sha256", "score_free_package", "package_sha256",
        "union_lineup_count", "union_lineups", "union_lineups_sha256",
        "task0_smoke", "publication_performed", "uses_realized_outcomes",
        "candidate_generation_performed", "k80_selection_performed",
        "task_result_sha256",
    }
    runtime = _validate_runtime_authority(
        item.get("runtime_authority"), manifest=manifest,
        manifest_identity=manifest_identity, ordinal=ordinal,
    )
    package = program.validate_score_free_slate_package_v1(item.get("score_free_package"))
    lineups = [_mapping(row, label="task union lineup") for row in _sequence(
        item.get("union_lineups"), label="task union lineups"
    )]
    replay_package, predecessor_identity, replay_lineups, science = _rebuild_task_science(
        manifest=manifest, frontier=frontier, ordinal=ordinal, store=store
    )
    union = _mapping(science["union"], label="combined science union")
    if (
        set(item) != expected_fields or item.get("schema_version") != TASK_SCHEMA
        or item.get("manifest_identity") != dict(manifest_identity)
        or item.get("manifest_sha256") != manifest["manifest_sha256"]
        or item.get("source_ordinal") != ordinal
        or item.get("slate_id") != program.EXPECTED_SLATE_IDS[ordinal]
        or runtime["runtime_authority_sha256"] != item.get("runtime_authority_sha256")
        or item.get("predecessor_task_result_identity") != predecessor_identity
        or item.get("predecessor_science_result_sha256") != science["result_sha256"]
        or item.get("predecessor_union_sha256") != union["union_sha256"]
        or package != replay_package or item.get("package_sha256") != package["package_sha256"]
        or lineups != replay_lineups or item.get("union_lineup_count") != len(lineups)
        or item.get("union_lineups_sha256") != _hash(lineups)
        or item.get("task0_smoke") is not False
        or item.get("publication_performed") is not True
        or item.get("uses_realized_outcomes") is not False
        or item.get("candidate_generation_performed") is not False
        or item.get("k80_selection_performed") is not False
    ):
        _fail(f"broad-admission task[{ordinal}] replay differs")
    return item


def task_from_request_v1(
    request: Mapping[str, object], *, store: ExactStore,
    environment: Mapping[str, str],
) -> dict[str, object]:
    item = _mapping(request, label="broad-admission task request")
    if set(item) != {"manifest_identity"}:
        _fail("task request fields differ")
    manifest, manifest_identity, frontier = _open_manifest(
        item["manifest_identity"], store=store
    )
    try:
        ordinal = int(environment.get("CLOUD_RUN_TASK_INDEX", ""))
    except ValueError as exc:
        raise BroadAdmissionRunnerV1Error("runtime task ordinal differs") from exc
    if environment.get("CLOUD_RUN_TASK_INDEX") != str(ordinal) or not 0 <= ordinal < TASK_COUNT:
        _fail("runtime task ordinal differs")
    smoke = environment.get(TASK0_SMOKE_ENV) == "true"
    if environment.get(TASK0_SMOKE_ENV) not in {"true", "false"} or (smoke and ordinal != 0):
        _fail("task-0 smoke authority differs")
    body = _task_body(
        manifest=manifest, manifest_identity=manifest_identity, frontier=frontier,
        ordinal=ordinal, environment=environment, store=store, smoke=smoke,
    )
    if smoke:
        return _with_hash({
            "schema_version": SMOKE_SCHEMA,
            "manifest_identity": manifest_identity,
            "source_ordinal": 0,
            "slate_id": body["slate_id"],
            "package_sha256": body["package_sha256"],
            "union_lineups_sha256": body["union_lineups_sha256"],
            "task_result_sha256": body["task_result_sha256"],
            "publication_performed": False,
            "uses_realized_outcomes": False,
            "complete": True,
        }, field="smoke_result_sha256")
    identity = _publish(
        str(manifest["task_bindings"][ordinal]["result_uri"]), body,
        store=store, maximum_bytes=MAX_TASK_BYTES,
    )
    return _with_hash({
        "schema_version": "corpus-r6-broad-admission-task-result/v1",
        "task_result_identity": identity,
        "task_result_sha256": body["task_result_sha256"],
        "package_sha256": body["package_sha256"],
        "publication_performed": True,
        "uses_realized_outcomes": False,
        "complete": True,
    }, field="task_receipt_sha256")


def _validate_execution_receipt(
    value: object, *, execution_id: str, manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="provider execution receipt")
    _validate_self_hash(item, field="execution_receipt_sha256", label="execution receipt")
    if (
        set(item) != {
            "schema_version", "project_id", "region", "execution_id",
            "execution_uid", "job_name", "reused_job_uid", "task_count",
            "parallelism", "max_retries", "succeeded_count", "failed_count",
            "cancelled_count", "running_count", "terminal", "code_sha",
            "immutable_image", "image_digest", "build_id", "manifest_identity",
            "manifest_sha256", "bound_identity", "service_account",
            "timeout_seconds", "cpu", "memory",
            "task0_smoke", "outcomes_allowed", "command", "args",
            "provider_observed", "execution_receipt_sha256",
        }
        or item.get("schema_version")
        != "corpus-r6-broad-admission-provider-execution/v1"
        or item.get("project_id") != PROJECT or item.get("region") != REGION
        or item.get("execution_id") != execution_id
        or type(item.get("execution_uid")) is not str or not item["execution_uid"]
        or item.get("job_name") != FIXED_REUSED_JOB_NAME
        or item.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or item.get("task_count") != TASK_COUNT or item.get("parallelism") != TASK_COUNT
        or item.get("max_retries") != 0 or item.get("succeeded_count") != TASK_COUNT
        or item.get("failed_count") != 0 or item.get("cancelled_count") != 0
        or item.get("running_count") != 0 or item.get("terminal") is not True
        or item.get("code_sha") != manifest["code_sha"]
        or item.get("immutable_image") != manifest["immutable_image"]
        or item.get("image_digest") != manifest["image_digest"]
        or item.get("build_id") != manifest["build_id"]
        or item.get("manifest_identity") != dict(manifest_identity)
        or item.get("manifest_sha256") != manifest["manifest_sha256"]
        or item.get("bound_identity") != dict(manifest_identity)
        or item.get("service_account")
        != "817589974517-compute@developer.gserviceaccount.com"
        or item.get("timeout_seconds") != 21_600
        or item.get("cpu") != "8" or item.get("memory") != "32Gi"
        or item.get("task0_smoke") is not False
        or item.get("outcomes_allowed") is not False
        or item.get("command") != ["/bin/bash"]
        or item.get("args") != [
            "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
            "container-run", "task",
        ]
        or item.get("provider_observed") is not True
    ):
        _fail("provider terminal execution differs")
    return item


def collect_from_request_v1(
    request: Mapping[str, object], *, store: ExactStore,
    provider: ExecutionProvider,
) -> dict[str, object]:
    item = _mapping(request, label="broad-admission collect request")
    if set(item) != {"manifest_identity", "execution_id"}:
        _fail("collect request fields differ")
    execution_id = item.get("execution_id")
    if type(execution_id) is not str or _EXECUTION.fullmatch(execution_id) is None:
        _fail("collect execution ID differs")
    manifest, manifest_identity, frontier = _open_manifest(
        item["manifest_identity"], store=store
    )
    # Provider terminality and the full execution spec are proven before the
    # first deterministic task-result name is resolved.
    receipt = _validate_execution_receipt(
        provider.status(execution_id, manifest=manifest, manifest_identity=manifest_identity),
        execution_id=execution_id, manifest=manifest,
        manifest_identity=manifest_identity,
    )
    descriptors: list[dict[str, object]] = []
    for ordinal, binding in enumerate(manifest["task_bindings"]):
        task, task_identity = _open_known(
            str(binding["result_uri"]), store=store, label=f"task[{ordinal}]",
            maximum_bytes=MAX_TASK_BYTES,
        )
        retained = _validate_task_result(
            task, manifest=manifest, manifest_identity=manifest_identity,
            frontier=frontier, ordinal=ordinal, store=store,
        )
        if retained["runtime_authority"]["execution_id"] != execution_id:
            _fail(f"task[{ordinal}] execution differs")
        descriptors.append({
            "source_ordinal": ordinal, "slate_id": retained["slate_id"],
            "task_result_identity": task_identity,
            "task_result_sha256": retained["task_result_sha256"],
            "package_sha256": retained["package_sha256"],
            "union_lineups_sha256": retained["union_lineups_sha256"],
            "runtime_authority_sha256": retained["runtime_authority_sha256"],
        })
    terminal = _with_hash({
        "schema_version": TERMINAL_SCHEMA,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "execution_id": execution_id,
        "execution_receipt": receipt,
        "execution_receipt_sha256": receipt["execution_receipt_sha256"],
        "task_count": TASK_COUNT,
        "task_results": descriptors,
        "task_results_sha256": _hash(descriptors),
        "all_tasks_generation_exact_reopened": True,
        "all_parent_unions_and_matrices_reconstructed": True,
        "score_free_lattice_complete": True,
        "root_published_last": True,
        "uses_realized_outcomes": False,
        "automatic_policy_promotion": False,
        "complete": True,
    }, field="terminal_sha256")
    identity = _publish(
        str(manifest["terminal_uri"]), terminal, store=store,
        maximum_bytes=MAX_TERMINAL_BYTES,
    )
    return _with_hash({
        "schema_version": "corpus-r6-broad-admission-collect-result/v1",
        "terminal_identity": identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "task_count": TASK_COUNT,
        "root_published_last": True,
        "uses_realized_outcomes": False,
        "complete": True,
    }, field="collect_result_sha256")


def _open_score_free_terminal(
    identity_value: object, *, store: ExactStore,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    list[dict[str, object]], list[dict[str, object]],
]:
    terminal, terminal_identity = _read(
        identity_value, store=store, label="broad-admission terminal",
        maximum_bytes=MAX_TERMINAL_BYTES,
    )
    _validate_self_hash(terminal, field="terminal_sha256", label="terminal")
    manifest, manifest_identity, frontier = _open_manifest(
        terminal.get("manifest_identity"), store=store
    )
    descriptors = [_mapping(row, label="terminal task descriptor") for row in _sequence(
        terminal.get("task_results"), label="terminal task results"
    )]
    if (
        set(terminal) != {
            "schema_version", "manifest_identity", "manifest_sha256", "execution_id",
            "execution_receipt", "execution_receipt_sha256", "task_count",
            "task_results", "task_results_sha256",
            "all_tasks_generation_exact_reopened",
            "all_parent_unions_and_matrices_reconstructed",
            "score_free_lattice_complete", "root_published_last",
            "uses_realized_outcomes", "automatic_policy_promotion", "complete",
            "terminal_sha256",
        }
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal_identity["uri"] != manifest["terminal_uri"]
        or terminal.get("manifest_identity") != manifest_identity
        or terminal.get("manifest_sha256") != manifest["manifest_sha256"]
        or len(descriptors) != TASK_COUNT or terminal.get("task_count") != TASK_COUNT
        or terminal.get("task_results_sha256") != _hash(descriptors)
        or terminal.get("all_tasks_generation_exact_reopened") is not True
        or terminal.get("all_parent_unions_and_matrices_reconstructed") is not True
        or terminal.get("score_free_lattice_complete") is not True
        or terminal.get("root_published_last") is not True
        or terminal.get("uses_realized_outcomes") is not False
        or terminal.get("automatic_policy_promotion") is not False
        or terminal.get("complete") is not True
    ):
        _fail("score-free terminal authority differs")
    receipt = _validate_execution_receipt(
        terminal.get("execution_receipt"),
        execution_id=str(terminal.get("execution_id")), manifest=manifest,
        manifest_identity=manifest_identity,
    )
    if receipt["execution_receipt_sha256"] != terminal.get("execution_receipt_sha256"):
        _fail("terminal execution receipt binding differs")
    packages: list[dict[str, object]] = []
    tasks: list[dict[str, object]] = []
    for ordinal, descriptor in enumerate(descriptors):
        if set(descriptor) != {
            "source_ordinal", "slate_id", "task_result_identity",
            "task_result_sha256", "package_sha256", "union_lineups_sha256",
            "runtime_authority_sha256",
        } or descriptor.get("source_ordinal") != ordinal:
            _fail(f"terminal task descriptor[{ordinal}] differs")
        task, observed = _read(
            descriptor["task_result_identity"], store=store,
            label=f"terminal task[{ordinal}]", maximum_bytes=MAX_TASK_BYTES,
        )
        retained = _validate_task_result(
            task, manifest=manifest, manifest_identity=manifest_identity,
            frontier=frontier, ordinal=ordinal, store=store,
        )
        if (
            observed != descriptor["task_result_identity"]
            or retained["task_result_sha256"] != descriptor["task_result_sha256"]
            or retained["package_sha256"] != descriptor["package_sha256"]
            or retained["union_lineups_sha256"] != descriptor["union_lineups_sha256"]
            or retained["runtime_authority_sha256"]
            != descriptor["runtime_authority_sha256"]
            or retained["runtime_authority"]["execution_id"]
            != terminal["execution_id"]
        ):
            _fail(f"terminal task descriptor[{ordinal}] binding differs")
        tasks.append(retained)
        packages.append(retained["score_free_package"])
    # Complete-lattice validation occurs here, before grade can open outcomes.
    for package in packages:
        program.validate_score_free_slate_package_v1(package)
    if [package["slate_id"] for package in packages] != list(program.EXPECTED_SLATE_IDS):
        _fail("score-free package lattice differs")
    return terminal, terminal_identity, manifest, packages, tasks


def reopen_from_request_v1(
    request: Mapping[str, object], *, store: ExactStore,
) -> dict[str, object]:
    item = _mapping(request, label="broad-admission reopen request")
    if set(item) != {"terminal_identity"}:
        _fail("reopen request fields differ")
    _terminal, identity, _manifest, packages, tasks = _open_score_free_terminal(
        item["terminal_identity"], store=store
    )
    return _with_hash({
        "schema_version": "corpus-r6-broad-admission-reopen-result/v1",
        "terminal_identity": identity, "task_count": len(tasks),
        "package_lattice_sha256": _hash([
            package["package_sha256"] for package in packages
        ]),
        "all_tasks_and_parents_generation_exact_reopened": True,
        "all_packages_independently_recomputed": True,
        "catalog_reread": False, "outcome_reread": False,
        "uses_realized_outcomes": False, "complete": True,
    }, field="reopen_result_sha256")


def _normalized_scoring_slates(tasks: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [{
        "source_ordinal": ordinal,
        "slate_id": task["slate_id"],
        "populations": [{
            "population_id": "fixed-combined-r6-union",
            "dimensions": {"entry_budget": 0},
            "lineups": [{
                "lineup_id": row["lineup_id"],
                "roster_player_ids": row["roster_player_ids"],
            } for row in task["union_lineups"]],
        }],
        "books": [],
    } for ordinal, task in enumerate(tasks)]


def _reverify_lease(authority: object, *, verifier: object) -> None:
    try:
        receipt = verifier(
            expected_identity=authority.lease_identity,
            catalog_run_id=str(authority.completion["run_id"]),
        )
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error("historical-outcome lease recheck failed") from exc
    item = _mapping(receipt, label="historical-outcome lease receipt")
    body = _mapping(item.get("body"), label="historical-outcome lease body")
    identity = _identity(item.get("object_receipt"), label="historical-outcome lease")
    if (
        set(item) != {"body", "object_receipt"}
        or body != authority.lease_body or identity != authority.lease_identity
        or _hash(body) != authority.lease_body_sha256
    ):
        _fail("historical-outcome lease changed during grade")


def _validated_lineup_score_rows(
    value: object, *, task: Mapping[str, object], label: str,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    rows = [
        _mapping(row, label=f"{label} row[{ordinal}]")
        for ordinal, row in enumerate(_sequence(value, label=label))
    ]
    task_rows = [
        _mapping(row, label=f"{label} task roster[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(task.get("union_lineups"), label=f"{label} task rosters")
        )
    ]
    expected_roster_hashes: dict[str, str] = {}
    for row in task_rows:
        lineup_id = row.get("lineup_id")
        roster_hash = row.get("roster_sha256")
        if (
            type(lineup_id) is not str or not lineup_id
            or lineup_id in expected_roster_hashes
            or type(roster_hash) is not str or _SHA.fullmatch(roster_hash) is None
        ):
            _fail(f"{label} task roster lattice differs")
        expected_roster_hashes[lineup_id] = roster_hash
    if (
        len(expected_roster_hashes) != len(task_rows) or len(rows) != len(task_rows)
    ):
        _fail(f"{label} task roster lattice differs")
    scores: dict[str, int] = {}
    observed_roster_hashes: dict[str, str] = {}
    for row in rows:
        lineup_id = row.get("lineup_id")
        roster_hash = row.get("roster_sha256")
        score = row.get("realized_score_micro")
        if (
            set(row) != {"lineup_id", "roster_sha256", "realized_score_micro"}
            or type(lineup_id) is not str or not lineup_id
            or lineup_id in scores
            or type(roster_hash) is not str or _SHA.fullmatch(roster_hash) is None
            or type(score) is not int
        ):
            _fail(f"{label} row authority differs")
        scores[lineup_id] = score
        observed_roster_hashes[lineup_id] = roster_hash
    if observed_roster_hashes != expected_roster_hashes:
        _fail(f"{label} lineup/roster coverage differs")
    return rows, scores


def _score_document(
    *, task: Mapping[str, object], slate_grade: Mapping[str, object],
    authority: object,
) -> dict[str, object]:
    rows, realized = _validated_lineup_score_rows(
        slate_grade.get("lineup_score_rows"), task=task,
        label="public scorer lineup scores",
    )
    if (
        slate_grade.get("source_ordinal") != task["source_ordinal"]
        or slate_grade.get("slate_id") != task["slate_id"]
        or slate_grade.get("lineup_score_rows_sha256") != _hash(rows)
    ):
        _fail("public roster scorer/task union binding differs")
    return _with_hash({
        "schema_version": SCORE_SCHEMA,
        "source_ordinal": task["source_ordinal"], "slate_id": task["slate_id"],
        "task_result_sha256": task["task_result_sha256"],
        "union_lineups_sha256": task["union_lineups_sha256"],
        "outcome_completion_identity": authority.completion_identity,
        "outcome_snapshot_identity": authority.snapshot_identity,
        "slate_grade": dict(slate_grade),
        "slate_grade_sha256": slate_grade["slate_grade_sha256"],
        "realized_scores_micro": realized,
        "realized_scores_sha256": _hash(realized),
        "every_distinct_roster_scored_once": True,
        "uses_realized_outcomes": True, "complete": True,
    }, field="score_document_sha256")


def _validate_closure(value: object) -> dict[str, object]:
    item = _mapping(value, label="outcome predecessor closure")
    _validate_self_hash(item, field="closure_sha256", label="outcome closure")
    if (
        set(item) != {
            "schema_version", "outcome_completion_identity",
            "outcome_completion_sha256", "outcome_snapshot_identity",
            "outcome_snapshot_sha256", "predecessor_identities",
            "predecessor_identities_sha256", "predecessor_identity_count",
            "historical_outcome_lease_identity",
            "historical_outcome_lease_body_sha256",
            "historical_outcome_lease_verified_before_snapshot_open",
            "historical_outcome_lease_release_required", "lease_release_owner",
            "source_slate_count", "outcome_row_count",
            "all_content_identities_generation_exact_reopened",
            "all_observed_predecessor_identities_enumerated",
            "base_snapshot_and_panel_predecessor_replayed",
            "catalog_snapshot_reconstructed_from_persisted_source",
            "recognized_authority_only", "uses_realized_outcomes",
            "additional_historical_outcome_read", "complete", "closure_sha256",
        }
        or item.get("schema_version") != recognized_outcomes.OUTCOME_CLOSURE_SCHEMA
        or item.get("recognized_authority_only") is not True
        or item.get("all_content_identities_generation_exact_reopened") is not True
        or item.get("historical_outcome_lease_verified_before_snapshot_open") is not True
        or item.get("uses_realized_outcomes") is not True
        or item.get("complete") is not True
        or item.get("predecessor_identities_sha256")
        != _hash(item.get("predecessor_identities"))
        or item.get("predecessor_identity_count")
        != len(_sequence(item.get("predecessor_identities"), label="outcome predecessors"))
    ):
        _fail("outcome predecessor closure differs")
    return item


def grade_from_request_v1(
    request: Mapping[str, object], *, store: ExactStore,
    verify_live_lease: object,
) -> dict[str, object]:
    item = _mapping(request, label="broad-admission grade request")
    if set(item) != {"terminal_identity", "outcome_authority_identity"}:
        _fail("grade request fields differ")
    # Every score-free task, package, parent union, and modeled matrix is
    # reopened and independently reconstructed before the first outcome read.
    terminal, terminal_identity, manifest, packages, tasks = _open_score_free_terminal(
        item["terminal_identity"], store=store
    )
    try:
        authority = recognized_outcomes.open_recognized_outcome_authority_v1(
            item["outcome_authority_identity"], read_exact=store.read_exact,
            verify_live_lease=verify_live_lease,
        )
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error(str(exc)) from exc
    if (
        authority.completion_identity
        != _identity(item["outcome_authority_identity"], label="outcome authority")
        or [authority.slate_keys[index][2] for index in range(TASK_COUNT)]
        != list(program.EXPECTED_SLATE_IDS)
    ):
        _fail("recognized outcome slate authority differs")
    try:
        slate_grades = roster_grader.score_normalized_slates_v1(
            slates=_normalized_scoring_slates(tasks),
            player_scores=authority.player_scores,
        )
    except Exception as exc:
        raise BroadAdmissionRunnerV1Error(str(exc)) from exc
    if len(slate_grades) != TASK_COUNT:
        _fail("public roster scorer did not return exact 54")
    score_documents = [
        _score_document(task=task, slate_grade=slate_grades[ordinal], authority=authority)
        for ordinal, task in enumerate(tasks)
    ]
    realized = {
        str(document["slate_id"]): dict(document["realized_scores_micro"])
        for document in score_documents
    }
    grade = program.grade_historical_program_v1(
        packages=packages, realized_scores_by_slate=realized,
        outcome_identity=authority.completion_identity,
    )
    program._validate_program_grade_v1(grade)
    closure = _validate_closure(authority.closure_receipt)
    # No child is written until scoring and the full program grade succeed and
    # the live lease is observed unchanged once more.
    _reverify_lease(authority, verifier=verify_live_lease)
    score_descriptors = []
    for ordinal, document in enumerate(score_documents):
        identity = _publish(
            str(manifest["task_bindings"][ordinal]["score_uri"]), document,
            store=store, maximum_bytes=MAX_SCORE_BYTES,
        )
        score_descriptors.append({
            "source_ordinal": ordinal, "slate_id": document["slate_id"],
            "score_identity": identity,
            "score_document_sha256": document["score_document_sha256"],
            "slate_grade_sha256": document["slate_grade_sha256"],
            "realized_scores_sha256": document["realized_scores_sha256"],
        })
    closure_identity = _publish(
        str(manifest["outcome_closure_uri"]), closure, store=store,
        maximum_bytes=MAX_CLOSURE_BYTES,
    )
    grade_identity = _publish(
        str(manifest["program_grade_uri"]), grade, store=store,
        maximum_bytes=MAX_GRADE_BYTES,
    )
    _reverify_lease(authority, verifier=verify_live_lease)
    root = _with_hash({
        "schema_version": GRADE_TERMINAL_SCHEMA,
        "manifest_identity": terminal["manifest_identity"],
        "manifest_sha256": manifest["manifest_sha256"],
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "outcome_completion_identity": authority.completion_identity,
        "outcome_completion_sha256": authority.completion["completion_sha256"],
        "outcome_snapshot_identity": authority.snapshot_identity,
        "outcome_snapshot_sha256": authority.snapshot["outcome_snapshot_sha256"],
        "historical_outcome_lease_identity": authority.lease_identity,
        "historical_outcome_lease_body_sha256": authority.lease_body_sha256,
        "outcome_closure_identity": closure_identity,
        "outcome_closure_sha256": closure["closure_sha256"],
        "score_documents": score_descriptors,
        "score_documents_sha256": _hash(score_descriptors),
        "program_grade_identity": grade_identity,
        "program_grade_sha256": grade["program_grade_sha256"],
        "score_free_bodies_opened_before_outcomes": True,
        "all_distinct_rosters_scored_by_public_scorer": True,
        "historical_outcome_lease_unchanged_through_grade": True,
        "publication_order": [
            "score-documents", "outcome-predecessor-closure", "program-grade",
            "grade-terminal-root",
        ],
        "grade_root_published_last": True,
        "descriptive_only": True,
        "automatic_policy_promotion": False,
        "uses_realized_outcomes": True, "complete": True,
    }, field="grade_terminal_sha256")
    root_identity = _publish(
        str(manifest["grade_terminal_uri"]), root, store=store,
        maximum_bytes=MAX_TERMINAL_BYTES,
    )
    return _with_hash({
        "schema_version": "corpus-r6-broad-admission-grade-result/v1",
        "grade_terminal_identity": root_identity,
        "grade_terminal_sha256": root["grade_terminal_sha256"],
        "program_grade_sha256": grade["program_grade_sha256"],
        "grade_root_published_last": True,
        "descriptive_only": True, "complete": True,
    }, field="grade_result_sha256")


def _validate_score_document(
    value: object, *, descriptor: Mapping[str, object], task: Mapping[str, object],
    root: Mapping[str, object], ordinal: int,
) -> tuple[dict[str, object], dict[str, int]]:
    item = _mapping(value, label=f"score document[{ordinal}]")
    _validate_self_hash(item, field="score_document_sha256", label="score document")
    grade = _mapping(item.get("slate_grade"), label="persisted slate grade")
    _validate_self_hash(grade, field="slate_grade_sha256", label="persisted slate grade")
    rows, row_scores = _validated_lineup_score_rows(
        grade.get("lineup_score_rows"), task=task,
        label="persisted lineup scores",
    )
    realized = _mapping(item.get("realized_scores_micro"), label="persisted realized scores")
    if (
        set(item) != {
            "schema_version", "source_ordinal", "slate_id",
            "task_result_sha256", "union_lineups_sha256",
            "outcome_completion_identity", "outcome_snapshot_identity",
            "slate_grade", "slate_grade_sha256", "realized_scores_micro",
            "realized_scores_sha256", "every_distinct_roster_scored_once",
            "uses_realized_outcomes", "complete", "score_document_sha256",
        }
        or item.get("schema_version") != SCORE_SCHEMA
        or item.get("source_ordinal") != ordinal or item.get("slate_id") != task["slate_id"]
        or item.get("task_result_sha256") != task["task_result_sha256"]
        or item.get("union_lineups_sha256") != task["union_lineups_sha256"]
        or item.get("outcome_completion_identity") != root["outcome_completion_identity"]
        or item.get("outcome_snapshot_identity") != root["outcome_snapshot_identity"]
        or item.get("slate_grade_sha256") != grade["slate_grade_sha256"]
        or grade.get("source_ordinal") != ordinal or grade.get("slate_id") != task["slate_id"]
        or grade.get("lineup_score_rows_sha256") != _hash(rows)
        or any(type(key) is not str or type(score) is not int
               for key, score in realized.items())
        or realized != row_scores
        or item.get("realized_scores_sha256") != _hash(realized)
        or item.get("every_distinct_roster_scored_once") is not True
        or item.get("uses_realized_outcomes") is not True or item.get("complete") is not True
        or set(descriptor) != {
            "source_ordinal", "slate_id", "score_identity",
            "score_document_sha256", "slate_grade_sha256",
            "realized_scores_sha256",
        }
        or descriptor.get("source_ordinal") != ordinal
        or descriptor.get("slate_id") != item["slate_id"]
        or descriptor.get("score_document_sha256") != item["score_document_sha256"]
        or descriptor.get("slate_grade_sha256") != item["slate_grade_sha256"]
        or descriptor.get("realized_scores_sha256") != item["realized_scores_sha256"]
    ):
        _fail(f"persisted score document[{ordinal}] differs")
    return item, dict(row_scores)


def _validate_grade_root(value: object) -> dict[str, object]:
    item = _mapping(value, label="broad-admission grade terminal")
    _validate_self_hash(item, field="grade_terminal_sha256", label="grade terminal")
    descriptors = _sequence(item.get("score_documents"), label="grade score documents")
    if (
        set(item) != {
            "schema_version", "manifest_identity", "manifest_sha256",
            "terminal_identity", "terminal_sha256", "outcome_completion_identity",
            "outcome_completion_sha256", "outcome_snapshot_identity",
            "outcome_snapshot_sha256", "historical_outcome_lease_identity",
            "historical_outcome_lease_body_sha256", "outcome_closure_identity",
            "outcome_closure_sha256", "score_documents",
            "score_documents_sha256", "program_grade_identity",
            "program_grade_sha256", "score_free_bodies_opened_before_outcomes",
            "all_distinct_rosters_scored_by_public_scorer",
            "historical_outcome_lease_unchanged_through_grade",
            "publication_order", "grade_root_published_last", "descriptive_only",
            "automatic_policy_promotion", "uses_realized_outcomes", "complete",
            "grade_terminal_sha256",
        }
        or item.get("schema_version") != GRADE_TERMINAL_SCHEMA
        or len(descriptors) != TASK_COUNT
        or item.get("score_documents_sha256") != _hash(descriptors)
        or item.get("score_free_bodies_opened_before_outcomes") is not True
        or item.get("all_distinct_rosters_scored_by_public_scorer") is not True
        or item.get("historical_outcome_lease_unchanged_through_grade") is not True
        or item.get("publication_order") != [
            "score-documents", "outcome-predecessor-closure", "program-grade",
            "grade-terminal-root",
        ]
        or item.get("grade_root_published_last") is not True
        or item.get("descriptive_only") is not True
        or item.get("automatic_policy_promotion") is not False
        or item.get("uses_realized_outcomes") is not True or item.get("complete") is not True
    ):
        _fail("grade terminal authority differs")
    return item


def grade_reopen_from_request_v1(
    request: Mapping[str, object], *, store: ExactStore,
) -> dict[str, object]:
    item = _mapping(request, label="broad-admission grade-reopen request")
    if set(item) != {"grade_terminal_identity"}:
        _fail("grade-reopen request fields differ")
    root, root_identity = _read(
        item["grade_terminal_identity"], store=store, label="grade terminal",
        maximum_bytes=MAX_TERMINAL_BYTES,
    )
    root = _validate_grade_root(root)
    terminal, terminal_identity, manifest, packages, tasks = _open_score_free_terminal(
        root["terminal_identity"], store=store
    )
    if (
        root_identity["uri"] != manifest["grade_terminal_uri"]
        or root["manifest_identity"] != terminal["manifest_identity"]
        or root["manifest_sha256"] != manifest["manifest_sha256"]
        or root["terminal_identity"] != terminal_identity
        or root["terminal_sha256"] != terminal["terminal_sha256"]
    ):
        _fail("grade terminal score-free binding differs")
    closure, closure_identity = _read(
        root["outcome_closure_identity"], store=store,
        label="persisted outcome closure", maximum_bytes=MAX_CLOSURE_BYTES,
    )
    closure = _validate_closure(closure)
    if (
        closure_identity != root["outcome_closure_identity"]
        or closure["closure_sha256"] != root["outcome_closure_sha256"]
        or closure["outcome_completion_identity"] != root["outcome_completion_identity"]
        or closure["outcome_completion_sha256"] != root["outcome_completion_sha256"]
        or closure["outcome_snapshot_identity"] != root["outcome_snapshot_identity"]
        or closure["outcome_snapshot_sha256"] != root["outcome_snapshot_sha256"]
        or closure["historical_outcome_lease_identity"]
        != root["historical_outcome_lease_identity"]
        or closure["historical_outcome_lease_body_sha256"]
        != root["historical_outcome_lease_body_sha256"]
    ):
        _fail("persisted outcome closure/root binding differs")
    realized: dict[str, dict[str, int]] = {}
    descriptors = _sequence(root["score_documents"], label="score documents")
    for ordinal, raw_descriptor in enumerate(descriptors):
        descriptor = _mapping(raw_descriptor, label=f"score descriptor[{ordinal}]")
        score, observed = _read(
            descriptor["score_identity"], store=store,
            label=f"score document[{ordinal}]", maximum_bytes=MAX_SCORE_BYTES,
        )
        if observed != descriptor["score_identity"]:
            _fail(f"score document[{ordinal}] identity differs")
        _document_body, scores = _validate_score_document(
            score, descriptor=descriptor, task=tasks[ordinal], root=root,
            ordinal=ordinal,
        )
        realized[str(tasks[ordinal]["slate_id"])] = scores
    stored_grade, grade_identity = _read(
        root["program_grade_identity"], store=store,
        label="persisted program grade", maximum_bytes=MAX_GRADE_BYTES,
    )
    program._validate_program_grade_v1(stored_grade)
    if (
        grade_identity != root["program_grade_identity"]
        or stored_grade["program_grade_sha256"] != root["program_grade_sha256"]
    ):
        _fail("persisted program grade binding differs")
    recomputed = program.grade_historical_program_v1(
        packages=packages, realized_scores_by_slate=realized,
        outcome_identity=root["outcome_completion_identity"],
    )
    if _canonical(recomputed) != _canonical(stored_grade):
        _fail("persisted program grade independent recomputation differs")
    return _with_hash({
        "schema_version": "corpus-r6-broad-admission-grade-reopen-result/v1",
        "grade_terminal_identity": root_identity,
        "program_grade_sha256": recomputed["program_grade_sha256"],
        "score_free_lattice_and_parents_replayed": True,
        "persisted_derived_scores_replayed": True,
        "program_grade_independently_recomputed": True,
        "catalog_reread": False, "outcome_snapshot_reread": False,
        "historical_outcome_lease_reread": False,
        "uses_realized_outcomes": True,
        "complete": True,
    }, field="grade_reopen_result_sha256")


class GCloudExecutionStatusV1:
    """Read one named Cloud Run execution and prove its exact frozen spec."""

    def status(
        self, execution_id: str, *, manifest: Mapping[str, object],
        manifest_identity: Mapping[str, object],
    ) -> Mapping[str, object]:
        completed = subprocess.run(
            [
                "gcloud", "run", "jobs", "executions", "describe", execution_id,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ],
            check=True, capture_output=True, text=True,
        )
        execution = _mapping(json.loads(completed.stdout), label="Cloud Run execution")
        metadata = _mapping(execution.get("metadata"), label="execution metadata")
        labels = _mapping(metadata.get("labels", {}), label="execution labels")
        annotations = _mapping(metadata.get("annotations", {}), label="execution annotations")
        spec = _mapping(execution.get("spec"), label="execution spec")
        template = _mapping(spec.get("template"), label="execution template")
        task_spec = _mapping(template.get("spec"), label="execution task spec")
        containers = _sequence(task_spec.get("containers"), label="execution containers")
        if len(containers) != 1:
            _fail("execution container count differs")
        container = _mapping(containers[0], label="execution container")
        status = _mapping(execution.get("status"), label="execution status")

        def _count(name: str) -> int:
            value = status.get(name, 0)
            if value in {None, ""}:
                return 0
            if type(value) is not int or value < 0:
                _fail(f"execution {name} differs")
            return value

        def _env(name: str) -> str:
            values = [
                row.get("value") for row in _sequence(container.get("env"), label="execution env")
                if isinstance(row, Mapping) and row.get("name") == name
            ]
            if len(values) != 1 or type(values[0]) is not str:
                _fail(f"execution env {name} differs")
            return values[0]

        request_b64 = _env(REQUEST_B64_ENV)
        try:
            request_raw = base64.b64decode(request_b64, validate=True)
        except Exception as exc:
            raise BroadAdmissionRunnerV1Error("execution request base64 differs") from exc
        expected_request = {"manifest_identity": dict(manifest_identity)}
        bound_raw = _env(BOUND_IDENTITY_ENV)
        try:
            bound_identity = _identity(
                json.loads(bound_raw), label="execution bound identity"
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise BroadAdmissionRunnerV1Error(
                "execution bound identity differs"
            ) from exc
        conditions = _sequence(status.get("conditions"), label="execution conditions")
        completed_true = any(
            isinstance(row, Mapping) and row.get("type") == "Completed"
            and str(row.get("status")).lower() == "true" for row in conditions
        )
        image = str(container.get("image", ""))
        job_uid = (
            labels.get("run.googleapis.com/jobUid")
            or annotations.get("run.googleapis.com/jobUid")
        )
        if (
            metadata.get("name") != execution_id
            or labels.get("run.googleapis.com/job") != FIXED_REUSED_JOB_NAME
            or job_uid != FIXED_REUSED_JOB_UID
            or spec.get("taskCount") != TASK_COUNT
            or spec.get("parallelism") != TASK_COUNT
            or task_spec.get("maxRetries") != 0
            or task_spec.get("serviceAccountName")
            != "817589974517-compute@developer.gserviceaccount.com"
            or not (
                task_spec.get("timeoutSeconds") == "21600"
                or task_spec.get("timeout") == "21600s"
            )
            or container.get("command") != ["/bin/bash"]
            or container.get("args") != [
                "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
                "container-run", "task",
            ]
            or image != manifest["immutable_image"]
            or _mapping(container.get("resources"), label="execution resources").get(
                "limits"
            ) != {"cpu": "8", "memory": "32Gi"}
            or _env(ENABLE_ENV) != ENABLE_VALUE
            or _env(OUTCOMES_ALLOWED_ENV) != "false"
            or _env(CODE_SHA_ENV) != manifest["code_sha"]
            or _env(IMAGE_DIGEST_ENV) != manifest["image_digest"]
            or _env(IMAGE_URI_ENV) != manifest["immutable_image"]
            or _env(BUILD_ID_ENV) != manifest["build_id"]
            or bound_identity != dict(manifest_identity)
            or bound_raw.encode("utf-8") != _canonical(bound_identity)
            or _env(TASK0_SMOKE_ENV) != "false"
            or sha256(request_raw).hexdigest() != _env(REQUEST_SHA256_ENV)
            or request_raw not in {
                _canonical(expected_request), _document(expected_request)
            }
            or not completed_true
        ):
            _fail("Cloud Run execution provider observation differs")
        return _with_hash({
            "schema_version": "corpus-r6-broad-admission-provider-execution/v1",
            "project_id": PROJECT, "region": REGION,
            "execution_id": execution_id, "execution_uid": str(metadata.get("uid", "")),
            "job_name": FIXED_REUSED_JOB_NAME, "reused_job_uid": FIXED_REUSED_JOB_UID,
            "task_count": TASK_COUNT, "parallelism": TASK_COUNT, "max_retries": 0,
            "succeeded_count": _count("succeededCount"),
            "failed_count": _count("failedCount"),
            "cancelled_count": _count("cancelledCount"),
            "running_count": _count("runningCount"),
            "terminal": completed_true,
            "code_sha": manifest["code_sha"],
            "immutable_image": manifest["immutable_image"],
            "image_digest": manifest["image_digest"],
            "build_id": manifest["build_id"], "manifest_identity": dict(manifest_identity),
            "manifest_sha256": manifest["manifest_sha256"],
            "bound_identity": dict(manifest_identity),
            "service_account": "817589974517-compute@developer.gserviceaccount.com",
            "timeout_seconds": 21_600, "cpu": "8", "memory": "32Gi",
            "task0_smoke": False, "outcomes_allowed": False,
            "command": ["/bin/bash"],
            "args": [
                "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
                "container-run", "task",
            ],
            "provider_observed": True,
        }, field="execution_receipt_sha256")


def _load_request(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be one existing absolute regular file")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_REQUEST_BYTES:
        _fail(f"{label} exceeds its byte ceiling")
    return _parse_document(raw, label=label)


def _early_gate(command: str, environment: Mapping[str, str]) -> None:
    expected_outcomes = "true" if command == "grade" else "false"
    if (
        environment.get(ENABLE_ENV) != ENABLE_VALUE
        or environment.get(OUTCOMES_ALLOWED_ENV) != expected_outcomes
    ):
        _fail(
            f"{command} requires {ENABLE_ENV}={ENABLE_VALUE} and "
            f"{OUTCOMES_ALLOWED_ENV}={expected_outcomes}"
        )


def _manifest_environment_gate(
    manifest: Mapping[str, object], environment: Mapping[str, str],
) -> None:
    if (
        environment.get(CODE_SHA_ENV) != manifest["code_sha"]
        or environment.get(IMAGE_DIGEST_ENV) != manifest["image_digest"]
        or environment.get(BUILD_ID_ENV) != manifest["build_id"]
    ):
        _fail("controller code/image/build environment differs from manifest")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "task", "collect", "reopen", "grade", "grade-reopen"):
        child = commands.add_parser(name)
        child.add_argument("--request", type=Path, required=True)
        child.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute:
        _fail("broad-admission action requires literal --execute")
    _early_gate(args.command, os.environ)
    request = _load_request(args.request, label=f"{args.command} request")
    store = grade_runner.GCSExactCreateOnceStoreV1()
    if args.command == "prepare":
        digest = _image_digest(request.get("immutable_image"))
        build, _ = _validate_build_attestation(
            request.get("runtime_build_attestation_identity"),
            code_sha=str(request.get("code_sha", "")), image_digest=digest,
            store=store,
        )
        if (
            os.environ.get(CODE_SHA_ENV) != request.get("code_sha")
            or os.environ.get(IMAGE_DIGEST_ENV) != digest
            or os.environ.get(BUILD_ID_ENV) != build["build_id"]
        ):
            _fail("prepare code/image/build environment differs")
        result = prepare_from_request_v1(request, store=store)
        manifest, _, _ = _open_manifest(result["manifest_identity"], store=store)
        _manifest_environment_gate(manifest, os.environ)
    elif args.command == "task":
        result = task_from_request_v1(request, store=store, environment=os.environ)
    elif args.command == "collect":
        manifest, _, _ = _open_manifest(request["manifest_identity"], store=store)
        _manifest_environment_gate(manifest, os.environ)
        result = collect_from_request_v1(
            request, store=store, provider=GCloudExecutionStatusV1()
        )
    elif args.command == "reopen":
        terminal, _ = _read(
            request["terminal_identity"], store=store, label="terminal gate",
            maximum_bytes=MAX_TERMINAL_BYTES,
        )
        manifest, _, _ = _open_manifest(terminal["manifest_identity"], store=store)
        _manifest_environment_gate(manifest, os.environ)
        result = reopen_from_request_v1(request, store=store)
    elif args.command == "grade":
        terminal, _ = _read(
            request["terminal_identity"], store=store, label="terminal gate",
            maximum_bytes=MAX_TERMINAL_BYTES,
        )
        manifest, _, _ = _open_manifest(terminal["manifest_identity"], store=store)
        _manifest_environment_gate(manifest, os.environ)
        result = grade_from_request_v1(
            request, store=store,
            verify_live_lease=grade_runner.GCSLiveHistoricalOutcomeLeaseVerifierV1(
                store=store
            ),
        )
    elif args.command == "grade-reopen":
        root, _ = _read(
            request["grade_terminal_identity"], store=store,
            label="grade terminal gate", maximum_bytes=MAX_TERMINAL_BYTES,
        )
        terminal, _ = _read(
            root["terminal_identity"], store=store, label="terminal gate",
            maximum_bytes=MAX_TERMINAL_BYTES,
        )
        manifest, _, _ = _open_manifest(terminal["manifest_identity"], store=store)
        _manifest_environment_gate(manifest, os.environ)
        result = grade_reopen_from_request_v1(request, store=store)
    else:  # pragma: no cover
        _fail("unknown broad-admission action")
    stdout = {
        "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
        "command": args.command,
        "task0_nonpublishing_smoke": (
            args.command == "task" and os.environ.get(TASK0_SMOKE_ENV) == "true"
        ),
        "result": result,
        "uses_realized_outcomes": args.command in {"grade", "grade-reopen"},
        "complete": True,
    }
    sys.stdout.buffer.write(_document(stdout))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BroadAdmissionRunnerV1Error,
        program.CorpusR6BroadAdmissionProgramV1Error,
        core.CorpusR6BroadAdmissionTournamentV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:  # controlled boundary for imported parent validators
        print(f"broad-admission command failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "BroadAdmissionRunnerV1Error", "ENABLE_ENV", "ENABLE_VALUE",
    "FROZEN_COMBINED_TERMINAL_IDENTITY", "FROZEN_FRONTIER_MANIFEST_IDENTITY",
    "GCloudExecutionStatusV1", "GRADE_TERMINAL_SCHEMA", "MANIFEST_SCHEMA",
    "OUTCOMES_ALLOWED_ENV", "OUTPUT_ROOT", "SCORE_SCHEMA", "SMOKE_SCHEMA",
    "TASK_COUNT", "TASK_SCHEMA", "TERMINAL_SCHEMA", "collect_from_request_v1",
    "grade_from_request_v1", "grade_reopen_from_request_v1",
    "prepare_from_request_v1", "reopen_from_request_v1", "task_from_request_v1",
]
