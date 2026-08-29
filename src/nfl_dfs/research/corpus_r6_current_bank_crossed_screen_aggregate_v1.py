"""Deterministic JSON-only publishers for the R6 current-bank screen.

This module owns the three single-process publication roles which follow the
per-slate evaluators.  Its request contains generation-pinned identities only:
scientific bodies, derived grids, nominees, comparisons, bootstrap rows, and
output URIs are never caller inputs.  All deterministic scientific reductions
are delegated to the frozen contract's public APIs.

Transport is injected.  The guarded entrypoint owns the fixed-project object
store adapter; focused tests use an in-memory exact-generation transport.  The
terminal publisher passes a one-shot opener to the contract so predecessor
bodies are reduced and released instead of being list-materialized.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
import resource
import sys
from time import monotonic
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)


PUBLISHER_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-publisher-request/v1"
)
PUBLISHER_RUNTIME_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-publisher-runtime-evidence/v1"
)
PUBLISHER_RESOURCE_PRECHARGE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-publisher-resource-precharge/v1"
)
PUBLISHER_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-publisher-envelope/v1"
)

PUBLISH_NOMINATION: Final = "publish-nomination"
PUBLISH_AGGREGATE_FINALISTS: Final = "publish-aggregate-finalists"
PUBLISH_TERMINAL_ROOT: Final = "publish-terminal-root"
PUBLISHER_MODES: Final = (
    PUBLISH_NOMINATION,
    PUBLISH_AGGREGATE_FINALISTS,
    PUBLISH_TERMINAL_ROOT,
)
MODE_PROCESS_ROLE: Final = {
    PUBLISH_NOMINATION: "broad-nomination-publisher",
    PUBLISH_AGGREGATE_FINALISTS: "aggregate-finalist-publisher",
    PUBLISH_TERMINAL_ROOT: "terminal-root-publisher",
}
MODE_WRITE_ROLES: Final = {
    PUBLISH_NOMINATION: ("nomination",),
    PUBLISH_AGGREGATE_FINALISTS: ("aggregate", "confirmed-finalists"),
    PUBLISH_TERMINAL_ROOT: ("root",),
}

FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"
MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES: Final = 768_000_000
MAXIMUM_COMPACT_EVALUATION_STATE_BYTES: Final = 64_000_000
MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 5_400
MAXIMUM_PUBLISHER_PEAK_RSS_BYTES: Final = 24 * 1024 * 1024 * 1024
MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES: Final = MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
REQUIRED_CLOUD_RUN_CONTAINER_MEMORY_BYTES: Final = 32 * 1024 * 1024 * 1024
MAXIMUM_PUBLISHER_ENVELOPE_BYTES: Final = 4_000_000
PUBLISHER_BASELINE_RSS_RESERVE_BYTES: Final = 2 * 1024 * 1024 * 1024
PUBLISHER_SINGLE_BODY_RAW_RESERVE_BYTES: Final = (
    MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
)
PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER: Final = 16
PUBLISHER_SINGLE_BODY_DECODE_RESERVE_BYTES: Final = (
    PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER
    * MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
)
PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER: Final = 8
PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES: Final = (
    PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER
    * MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
)
PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES: Final = 4 * 1024 * 1024 * 1024
PUBLISHER_WORST_CASE_RSS_BYTES: Final = (
    PUBLISHER_BASELINE_RSS_RESERVE_BYTES
    + PUBLISHER_SINGLE_BODY_RAW_RESERVE_BYTES
    + PUBLISHER_SINGLE_BODY_DECODE_RESERVE_BYTES
    + PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES
    + PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES
)
PUBLISHER_SCRIPT_BASENAME: Final = (
    "run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py"
)
_REDIRECT_ENV_KEYS: Final = (
    "STORAGE_EMULATOR_HOST",
    "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_PRELOAD",
    "R6_GCS_ENDPOINT",
    "R6_PROJECT_OVERRIDE",
    "R6_AGGREGATE_COMMAND",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[
    [str, bytes, Mapping[str, object] | None], Mapping[str, object]
]


class CorpusR6CurrentBankCrossedScreenAggregateV1Error(ValueError):
    """A deterministic publisher could not prove its exact authority."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a nonnegative integer")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc


def _bind(
    body: Mapping[str, object], identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            body, identity, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    body[field] = contract.canonical_sha256_v1(body)
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    expected = contract.canonical_sha256_v1({
        key: retained for key, retained in value.items() if key != field
    })
    if value.get(field) != expected:
        _fail(f"{label} self hash differs")


def strict_json_v1(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse exactly one finite UTF-8 JSON object and reject duplicate keys."""
    if type(raw) is not bytes:
        _fail(f"{label} exact reader must return bytes")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> object:
        _fail(f"{label} contains non-finite JSON constant {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite,
        )
    except CorpusR6CurrentBankCrossedScreenAggregateV1Error:
        raise
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    return _mapping(value, label=label)


def _read_json_v1(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} bytes differ from exact identity")
    body = strict_json_v1(raw, label=label)
    _bind(body, identity, label=label)
    return body, identity


def _identities(value: object, *, label: str) -> list[dict[str, object]]:
    return [
        _identity(row, label=f"{label}[{index}]")
        for index, row in enumerate(_sequence(value, label=label))
    ]


def _optional_identity(value: object, *, label: str) -> dict[str, object] | None:
    return None if value is None else _identity(value, label=label)


def build_publisher_request_v1(
    *,
    mode: str,
    design_identity: object,
    topology_identity: object,
    bootstrap_manifest_identity: object,
    launch_intent_identity: object,
    process_budget_identity: object,
    broad_evaluation_identities: object = (),
    nomination_identity: object | None = None,
    confirmation_evaluation_identities: object = (),
    predecessor_identities: object = (),
    prior_nomination_identity: object | None = None,
    prior_aggregate_identity: object | None = None,
    prior_finalist_identity: object | None = None,
    prior_root_identity: object | None = None,
) -> dict[str, object]:
    """Build one identity-only request for a fixed deterministic role."""
    retained_mode = _string(mode, label="publisher mode")
    if retained_mode not in PUBLISHER_MODES:
        _fail("publisher mode differs")
    broad = _identities(
        broad_evaluation_identities, label="broad evaluation identities"
    )
    nomination = _optional_identity(
        nomination_identity, label="nomination identity"
    )
    confirmation = _identities(
        confirmation_evaluation_identities,
        label="confirmation evaluation identities",
    )
    predecessors = _identities(
        predecessor_identities, label="predecessor identities"
    )
    prior_nomination = _optional_identity(
        prior_nomination_identity, label="prior nomination identity"
    )
    prior_aggregate = _optional_identity(
        prior_aggregate_identity, label="prior aggregate identity"
    )
    prior_finalist = _optional_identity(
        prior_finalist_identity, label="prior finalist identity"
    )
    prior_root = _optional_identity(
        prior_root_identity, label="prior root identity"
    )

    if retained_mode == PUBLISH_NOMINATION:
        if (
            len(broad) != contract.PANEL_SLATE_COUNT
            or nomination is not None
            or confirmation
            or predecessors
            or prior_aggregate is not None
            or prior_finalist is not None
            or prior_root is not None
        ):
            _fail("nomination publisher request lattice differs")
    elif retained_mode == PUBLISH_AGGREGATE_FINALISTS:
        if (
            len(broad) != contract.PANEL_SLATE_COUNT
            or nomination is None
            or len(confirmation) != contract.PANEL_SLATE_COUNT
            or predecessors
            or prior_nomination is not None
            or prior_root is not None
        ):
            _fail("aggregate/finalist publisher request lattice differs")
    elif (
        broad
        or nomination is not None
        or confirmation
        or len(predecessors) != contract.OUTPUT_OBJECT_COUNT - 1
        or prior_nomination is not None
        or prior_aggregate is not None
        or prior_finalist is not None
    ):
        _fail("terminal publisher request lattice differs")

    body = {
        "schema_version": PUBLISHER_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "mode": retained_mode,
        "process_role": MODE_PROCESS_ROLE[retained_mode],
        "process_ordinal": 0,
        "design_identity": _identity(
            design_identity, label="design publication identity"
        ),
        "topology_identity": _identity(
            topology_identity, label="topology identity"
        ),
        "bootstrap_manifest_identity": _identity(
            bootstrap_manifest_identity, label="bootstrap manifest identity"
        ),
        "launch_intent_identity": _identity(
            launch_intent_identity, label="launch intent identity"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="publisher process budget identity"
        ),
        "broad_evaluation_identities": broad,
        "nomination_identity": nomination,
        "confirmation_evaluation_identities": confirmation,
        "predecessor_identities": predecessors,
        "prior_nomination_identity": prior_nomination,
        "prior_aggregate_identity": prior_aggregate,
        "prior_finalist_identity": prior_finalist,
        "prior_root_identity": prior_root,
        "caller_scientific_bodies_accepted": False,
        "caller_grids_nominees_comparisons_bootstraps_accepted": False,
        "caller_output_uri_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="publisher_request_sha256")


def validate_publisher_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="publisher request")
    expected_fields = {
        "schema_version", "contract_id", "mode", "process_role",
        "process_ordinal", "design_identity", "topology_identity",
        "bootstrap_manifest_identity", "launch_intent_identity",
        "process_budget_identity", "broad_evaluation_identities",
        "nomination_identity", "confirmation_evaluation_identities",
        "predecessor_identities", "prior_nomination_identity",
        "prior_aggregate_identity", "prior_finalist_identity",
        "prior_root_identity", "caller_scientific_bodies_accepted",
        "caller_grids_nominees_comparisons_bootstraps_accepted",
        "caller_output_uri_accepted", "policy", "publisher_request_sha256",
    }
    if set(item) != expected_fields:
        _fail("publisher request fields differ")
    _self_hash(
        item, field="publisher_request_sha256", label="publisher request"
    )
    expected = build_publisher_request_v1(
        mode=item.get("mode"),
        design_identity=item.get("design_identity"),
        topology_identity=item.get("topology_identity"),
        bootstrap_manifest_identity=item.get("bootstrap_manifest_identity"),
        launch_intent_identity=item.get("launch_intent_identity"),
        process_budget_identity=item.get("process_budget_identity"),
        broad_evaluation_identities=item.get("broad_evaluation_identities"),
        nomination_identity=item.get("nomination_identity"),
        confirmation_evaluation_identities=item.get(
            "confirmation_evaluation_identities"
        ),
        predecessor_identities=item.get("predecessor_identities"),
        prior_nomination_identity=item.get("prior_nomination_identity"),
        prior_aggregate_identity=item.get("prior_aggregate_identity"),
        prior_finalist_identity=item.get("prior_finalist_identity"),
        prior_root_identity=item.get("prior_root_identity"),
    )
    if (
        item.get("schema_version") != PUBLISHER_REQUEST_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("process_ordinal") != 0
        or item.get("caller_scientific_bodies_accepted") is not False
        or item.get(
            "caller_grids_nominees_comparisons_bootstraps_accepted"
        ) is not False
        or item.get("caller_output_uri_accepted") is not False
        or item.get("policy") != contract.POLICY_CLAIMS
        or contract.canonical_json_bytes_v1(item)
        != contract.canonical_json_bytes_v1(expected)
    ):
        _fail("publisher request canonical replay differs")
    return expected


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def canonical_publisher_command_v1(mode: str) -> list[str]:
    retained_mode = _string(mode, label="publisher command mode")
    if retained_mode not in PUBLISHER_MODES:
        _fail("publisher command mode differs")
    return [
        str(Path(sys.executable).resolve()),
        str(
            (
                _repository_root_v1()
                / "scripts"
                / PUBLISHER_SCRIPT_BASENAME
            ).resolve()
        ),
        retained_mode,
    ]


def derive_observed_runtime_evidence_v1(
    *, mode: str, environ: Mapping[str, str], argv: object,
    pid: int, parent_pid: int,
) -> dict[str, object]:
    """Derive process-environment evidence; this is not cloud attestation."""
    retained_mode = _string(mode, label="publisher runtime mode")
    if retained_mode not in PUBLISHER_MODES:
        _fail("publisher runtime mode differs")
    environment = dict(environ)
    for key in _REDIRECT_ENV_KEYS:
        if environment.get(key):
            _fail(f"redirect environment {key} is forbidden")
    projects = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    code_commit = environment.get("CODE_SHA", "")
    image_digest = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    task_index = environment.get("CLOUD_RUN_TASK_INDEX", "")
    process_ordinal = environment.get("R6_AGGREGATE_PROCESS_ORDINAL", "")
    if (
        projects != {FIXED_GCP_PROJECT}
        or _COMMIT.fullmatch(code_commit) is None
        or not image_digest.startswith("sha256:")
        or _SHA256.fullmatch(image_digest[7:]) is None
        or task_index != "0"
        or process_ordinal != "0"
        or not environment.get("CLOUD_RUN_JOB")
        or not environment.get("CLOUD_RUN_EXECUTION")
    ):
        _fail("observed publisher environment differs")
    command = [
        _string(row, label=f"publisher runtime argv[{index}]")
        for index, row in enumerate(_sequence(argv, label="publisher runtime argv"))
    ]
    canonical = canonical_publisher_command_v1(retained_mode)
    if command != canonical:
        _fail("observed publisher command differs")
    entrypoint = Path(canonical[1])
    if not entrypoint.is_file():
        _fail("publisher entrypoint is absent")
    entrypoint_sha = sha256(entrypoint.read_bytes()).hexdigest()
    body = {
        "schema_version": PUBLISHER_RUNTIME_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "mode": retained_mode,
        "process_role": MODE_PROCESS_ROLE[retained_mode],
        "process_ordinal": 0,
        "project_id": FIXED_GCP_PROJECT,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "job_name": environment["CLOUD_RUN_JOB"],
        "execution_id": environment["CLOUD_RUN_EXECUTION"],
        "task_index": 0,
        "pid": _integer(pid, label="publisher runtime pid"),
        "parent_pid": _integer(parent_pid, label="publisher runtime parent pid"),
        "python_executable": canonical[0],
        "python_version": sys.version.split()[0],
        "entrypoint_path": canonical[1],
        "entrypoint_sha256": entrypoint_sha,
        "command": canonical,
        "command_sha256": contract.canonical_sha256_v1({
            "command": canonical,
            "entrypoint_sha256": entrypoint_sha,
        }),
        "storage_endpoint": FIXED_STORAGE_ENDPOINT,
        "redirect_environment_present": False,
        "evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
        "outer_launch_authority_identity": None,
    }
    return _with_hash(body, field="runtime_evidence_sha256")


def validate_observed_runtime_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="publisher runtime evidence")
    expected_fields = {
        "schema_version", "contract_id", "mode", "process_role",
        "process_ordinal", "project_id", "code_commit", "image_digest",
        "job_name", "execution_id", "task_index", "pid", "parent_pid",
        "python_executable", "python_version", "entrypoint_path",
        "entrypoint_sha256", "command", "command_sha256",
        "storage_endpoint", "redirect_environment_present",
        "evidence_strength", "outer_launch_authority_binding_required",
        "outer_launch_authority_identity", "runtime_evidence_sha256",
    }
    if set(item) != expected_fields:
        _fail("publisher runtime evidence fields differ")
    _self_hash(item, field="runtime_evidence_sha256", label="runtime evidence")
    mode = _string(item.get("mode"), label="runtime evidence mode")
    canonical = canonical_publisher_command_v1(mode)
    entrypoint_sha = sha256(Path(canonical[1]).read_bytes()).hexdigest()
    if (
        item.get("schema_version") != PUBLISHER_RUNTIME_EVIDENCE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("process_role") != MODE_PROCESS_ROLE[mode]
        or item.get("process_ordinal") != 0
        or item.get("project_id") != FIXED_GCP_PROJECT
        or item.get("storage_endpoint") != FIXED_STORAGE_ENDPOINT
        or item.get("redirect_environment_present") is not False
        or item.get("evidence_strength")
        != "process-environment-observation-only"
        or item.get("outer_launch_authority_binding_required") is not True
        or item.get("outer_launch_authority_identity") is not None
        or item.get("command") != canonical
        or item.get("entrypoint_path") != canonical[1]
        or item.get("entrypoint_sha256") != entrypoint_sha
        or item.get("command_sha256") != contract.canonical_sha256_v1({
            "command": canonical,
            "entrypoint_sha256": entrypoint_sha,
        })
        or _COMMIT.fullmatch(str(item.get("code_commit", ""))) is None
        or not str(item.get("image_digest", "")).startswith("sha256:")
        or _SHA256.fullmatch(str(item.get("image_digest", ""))[7:]) is None
        or item.get("task_index") != 0
    ):
        _fail("publisher runtime fixed binding differs")
    for field in ("process_ordinal", "task_index", "pid", "parent_pid"):
        _integer(item.get(field), label=f"publisher runtime {field}")
    for field in ("job_name", "execution_id", "python_version"):
        _string(item.get(field), label=f"publisher runtime {field}")
    return item


def _scientific_identities_v1(
    request: Mapping[str, object],
) -> list[dict[str, object]]:
    mode = str(request["mode"])
    if mode == PUBLISH_NOMINATION:
        return list(request["broad_evaluation_identities"])
    if mode == PUBLISH_AGGREGATE_FINALISTS:
        return [
            *request["broad_evaluation_identities"],
            request["nomination_identity"],
            *request["confirmation_evaluation_identities"],
        ]
    return list(request["predecessor_identities"])


def _read_row_v1(
    *, ordinal: int, channel: str, role: str,
    identity: Mapping[str, object], scientific_ordinal: int | None = None,
) -> dict[str, object]:
    return {
        "ordinal": ordinal,
        "channel": channel,
        "role": role,
        "scientific_ordinal": scientific_ordinal,
        "identity": dict(identity),
    }


def _contract_call_v1(callable_value: Callable[..., object], /, **kwargs: object) -> object:
    try:
        return callable_value(**kwargs)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc


def _publication_body_hash_v1(body: Mapping[str, object]) -> str:
    return contract.canonical_sha256_v1(body)


def _publish_v1(
    *, body: Mapping[str, object], descriptor: Mapping[str, object],
    prior_identity: object, publish_create_once: PublishCreateOnce,
) -> tuple[dict[str, object], int]:
    uri = _string(descriptor.get("uri"), label="publication write URI")
    ceiling = _integer(
        descriptor.get("max_bytes"), label="publication write byte ceiling"
    )
    if descriptor.get("create_once") is not True:
        _fail("publication write is not create-once")
    prior = _optional_identity(prior_identity, label="prior publication identity")
    if prior is not None and prior["uri"] != uri:
        _fail("prior publication URI differs from precharged output")
    raw = contract.canonical_json_bytes_v1(body)
    if len(raw) > ceiling:
        _fail("publication exceeds its precharged byte ceiling")
    published = _identity(
        publish_create_once(uri, raw, prior), label="published exact identity"
    )
    _bind(body, published, label="published authority")
    if published["uri"] != uri:
        _fail("published authority URI differs from precharged output")
    return published, len(raw)


class _ExactScientificJsonOpenerV1:
    """One-pass identity/address gate for the precompiled scientific lattice."""

    def __init__(
        self, *, identities: Sequence[Mapping[str, object]],
        read_exact: ReadExact, ledger: list[dict[str, object]],
    ) -> None:
        self._identities = [dict(row) for row in identities]
        self._read_exact = read_exact
        self._ledger = ledger
        self._next = 0

    @property
    def call_count(self) -> int:
        return self._next

    def open(self, *, role: str, identity_value: object) -> tuple[
        dict[str, object], dict[str, object]
    ]:
        if self._next >= len(self._identities):
            _fail("scientific opener is exhausted")
        identity = _identity(identity_value, label="scientific read identity")
        expected = self._identities[self._next]
        if identity != expected:
            _fail("scientific identity is not addressable at this ordinal")
        body, retained_identity = _read_json_v1(
            expected, read_exact=self._read_exact, label=role
        )
        self._ledger.append(_read_row_v1(
            ordinal=len(self._ledger),
            channel="publisher-scientific",
            role=role,
            identity=retained_identity,
            scientific_ordinal=self._next,
        ))
        self._next += 1
        return body, retained_identity

    def require_complete(self) -> None:
        if self._next != len(self._identities):
            _fail("scientific opener did not consume its exact lattice")


def _validate_common_authorities_v1(
    *, request: Mapping[str, object], observed_runtime: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    dict[str, object], dict[str, object], list[dict[str, object]],
    list[dict[str, object]],
]:
    ledger: list[dict[str, object]] = []

    def opened(role: str, identity_value: object) -> dict[str, object]:
        body, identity = _read_json_v1(
            identity_value, read_exact=read_exact, label=role
        )
        ledger.append(_read_row_v1(
            ordinal=len(ledger), channel="publisher-authority",
            role=role, identity=identity,
        ))
        return body

    design = opened("design", request["design_identity"])
    topology = opened("topology", request["topology_identity"])
    bootstrap_manifest = opened(
        "bootstrap-manifest", request["bootstrap_manifest_identity"]
    )
    launch_intent = opened(
        "launch-intent", request["launch_intent_identity"]
    )
    process_budget = opened(
        "publisher-process-budget", request["process_budget_identity"]
    )

    try:
        retained_design = contract.validate_design_authority_v1(
            design, publication_identity=request["design_identity"]
        )
        retained_topology = contract.validate_result_topology_v1(topology)
        _bind(retained_topology, request["topology_identity"], label="topology")
        retained_manifest = contract.validate_bootstrap_manifest_authority_v1(
            bootstrap_manifest,
            publication_identity=request["bootstrap_manifest_identity"],
            topology=retained_topology,
            topology_identity=request["topology_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
    if (
        retained_design["topology"] != retained_topology
        or retained_design["topology_identity"] != request["topology_identity"]
        or retained_design["bootstrap_manifest"] != retained_manifest
        or retained_design["bootstrap_manifest_identity"]
        != request["bootstrap_manifest_identity"]
    ):
        _fail("publisher design/topology/bootstrap authority differs")
    del launch_intent  # Its exact canonical body and identity were bound above.

    scientific = _scientific_identities_v1(request)
    try:
        compiled = contract.compile_publisher_process_budget_v1(
            process_role=request["process_role"],
            design=retained_design,
            design_publication_identity=request["design_identity"],
            topology_identity=request["topology_identity"],
            bootstrap_manifest=retained_manifest,
            bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
            launch_intent_identity=request["launch_intent_identity"],
            scientific_read_identities=scientific,
        )
        retained_budget = contract.validate_publisher_process_budget_v1(
            process_budget,
            design=retained_design,
            design_publication_identity=request["design_identity"],
            topology_identity=request["topology_identity"],
            bootstrap_manifest=retained_manifest,
            bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
            launch_intent_identity=request["launch_intent_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
    _bind(
        retained_budget, request["process_budget_identity"],
        label="publisher process budget",
    )
    if (
        contract.canonical_json_bytes_v1(compiled)
        != contract.canonical_json_bytes_v1(retained_budget)
        or retained_budget["process_role"] != request["process_role"]
    ):
        _fail("publisher process budget differs from exact compilation")
    expected_common = [
        request["design_identity"], request["topology_identity"],
        request["bootstrap_manifest_identity"], request["launch_intent_identity"],
    ]
    read_allowlist = [
        _mapping(row, label=f"publisher read allowlist[{index}]")
        for index, row in enumerate(retained_budget["read_allowlist"])
    ]
    if (
        [row.get("identity") for row in read_allowlist[:4]] != expected_common
        or [row.get("identity") for row in read_allowlist[4:]] != scientific
        or retained_budget["scientific_read_count"] != len(scientific)
    ):
        _fail("publisher process-budget read lattice differs")
    return (
        retained_design,
        retained_topology,
        retained_manifest,
        retained_budget,
        process_budget,
        scientific,
        ledger,
    )


def _runtime_observation_v1(
    *, request: Mapping[str, object], observed: Mapping[str, object],
    bootstrap_manifest: Mapping[str, object],
    process_budget: Mapping[str, object],
) -> dict[str, object]:
    try:
        built = contract.build_runtime_observation_v1(
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
            process_budget=process_budget,
            process_budget_identity=request["process_budget_identity"],
            launch_intent_identity=request["launch_intent_identity"],
            observed_code_commit=observed["code_commit"],
            observed_image_digest=observed["image_digest"],
            observed_command=observed["command"],
            observed_entrypoint_sha256=observed["entrypoint_sha256"],
            cloud_job_name=observed["job_name"],
            cloud_execution_name=observed["execution_id"],
            cloud_task_index=observed["task_index"],
        )
        retained = contract.validate_runtime_observation_v1(
            built,
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
            process_budget=process_budget,
            process_budget_identity=request["process_budget_identity"],
            launch_intent_identity=request["launch_intent_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
    return retained


def _write_descriptors_v1(
    *, request: Mapping[str, object],
    process_budget: Mapping[str, object], topology: Mapping[str, object],
) -> list[dict[str, object]]:
    writes = [
        _mapping(row, label=f"publisher write allowlist[{index}]")
        for index, row in enumerate(process_budget["write_allowlist"])
    ]
    expected_roles = list(MODE_WRITE_ROLES[str(request["mode"])])
    topology_by_role = {
        str(row["role"]): dict(row) for row in topology["objects"]
        if row["role"] in expected_roles
    }
    if (
        len(writes) != len(expected_roles)
        or [row.get("role") for row in writes] != expected_roles
        or process_budget["write_object_count"] != len(expected_roles)
    ):
        _fail("publisher write precharge differs")
    for descriptor, role in zip(writes, expected_roles, strict=True):
        topology_row = topology_by_role.get(role)
        if (
            topology_row is None
            or descriptor.get("ordinal") != topology_row["ordinal"]
            or descriptor.get("uri") != topology_row["uri"]
            or descriptor.get("create_once") is not True
        ):
            _fail("publisher write/topology binding differs")
        _integer(descriptor.get("max_bytes"), label="write maximum bytes")
    return writes


_EXPECTED_EVALUATION_READ_COUNTS: Final = {
    PUBLISH_NOMINATION: contract.PANEL_SLATE_COUNT,
    PUBLISH_AGGREGATE_FINALISTS: 2 * contract.PANEL_SLATE_COUNT,
    PUBLISH_TERMINAL_ROOT: 2 * contract.PANEL_SLATE_COUNT,
}
_EXPECTED_COMPACT_EVALUATION_RECORD_COUNTS: Final = dict(
    _EXPECTED_EVALUATION_READ_COUNTS
)


def _peak_rss_bytes_v1() -> int:
    # Linux reports ru_maxrss in KiB.  Cloud Run and the supported local
    # execution environment are Linux.
    retained = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1_024
    if retained < 0:
        _fail("publisher peak RSS observation differs")
    return retained


def _require_address_space_limit_v1(
    *, _getrlimit: Callable[[int], tuple[int, int]] = resource.getrlimit,
    _setrlimit: Callable[[int, tuple[int, int]], None] = resource.setrlimit,
) -> int:
    """Install the 24-GiB process AS ceiling before authority materialization."""
    try:
        soft, hard = _getrlimit(resource.RLIMIT_AS)
        if (
            hard != resource.RLIM_INFINITY
            and hard < MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES
        ):
            _fail("publisher hard address-space limit is below its precharge")
        if soft != MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES:
            _setrlimit(
                resource.RLIMIT_AS,
                (MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES, hard),
            )
        retained_soft, retained_hard = _getrlimit(resource.RLIMIT_AS)
    except CorpusR6CurrentBankCrossedScreenAggregateV1Error:
        raise
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher address-space limit could not be installed"
        ) from exc
    if (
        retained_soft != MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES
        or (
            retained_hard != resource.RLIM_INFINITY
            and retained_hard < retained_soft
        )
    ):
        _fail("publisher address-space limit differs from its precharge")
    return int(retained_soft)


def _require_resource_checkpoint_v1(
    *, started_at: float, clock: Callable[[], float],
    peak_rss_bytes: Callable[[], int], label: str,
) -> tuple[int, int]:
    elapsed = clock() - started_at
    rss = peak_rss_bytes()
    if not (0 <= elapsed <= MAXIMUM_PUBLISHER_WALL_SECONDS):
        _fail(f"{label} exceeds publisher wall-time ceiling")
    if type(rss) is not int or not 0 <= rss <= MAXIMUM_PUBLISHER_PEAK_RSS_BYTES:
        _fail(f"{label} exceeds publisher peak-RSS ceiling")
    return int(elapsed * 1_000), rss


def _evaluation_scientific_identities_v1(
    *, request: Mapping[str, object], topology: Mapping[str, object],
    scientific_identities: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    mode = str(request["mode"])
    if mode == PUBLISH_NOMINATION:
        evaluations = [dict(row) for row in scientific_identities]
    elif mode == PUBLISH_AGGREGATE_FINALISTS:
        evaluations = [
            *[dict(row) for row in scientific_identities[:contract.PANEL_SLATE_COUNT]],
            *[dict(row) for row in scientific_identities[contract.PANEL_SLATE_COUNT + 1:]],
        ]
    else:
        evaluations = [
            dict(identity)
            for descriptor, identity in zip(
                topology["objects"][:-1], scientific_identities, strict=True
            )
            if descriptor["role"] in {
                "broad-evaluation-result", "confirmation-evaluation-result",
            }
        ]
    if len(evaluations) != _EXPECTED_EVALUATION_READ_COUNTS[mode]:
        _fail("publisher evaluation scientific lattice differs")
    return evaluations


def _compile_resource_precharge_v1(
    *, request: Mapping[str, object], topology: Mapping[str, object],
    scientific_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    mode = str(request["mode"])
    scientific = [
        _identity(row, label=f"publisher resource scientific[{index}]")
        for index, row in enumerate(scientific_identities)
    ]
    if scientific != _scientific_identities_v1(request):
        _fail("publisher resource scientific lattice differs from request")
    evaluations = _evaluation_scientific_identities_v1(
        request=request, topology=topology, scientific_identities=scientific
    )
    if any(
        int(identity["bytes"]) > MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        for identity in scientific
    ):
        _fail("publisher scientific body exceeds resource precharge")
    body = {
        "schema_version": PUBLISHER_RESOURCE_PRECHARGE_SCHEMA,
        "mode": mode,
        "scientific_read_count": len(scientific),
        "scientific_read_bytes": sum(
            int(identity["bytes"]) for identity in scientific
        ),
        "evaluation_read_count": len(evaluations),
        "evaluation_read_bytes": sum(
            int(identity["bytes"]) for identity in evaluations
        ),
        "maximum_single_scientific_body_bytes": (
            MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        ),
        "maximum_compact_evaluation_state_bytes": (
            MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
        ),
        "maximum_wall_seconds": MAXIMUM_PUBLISHER_WALL_SECONDS,
        "maximum_peak_rss_bytes": MAXIMUM_PUBLISHER_PEAK_RSS_BYTES,
        "maximum_address_space_bytes": MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES,
        "required_cloud_run_container_memory_bytes": (
            REQUIRED_CLOUD_RUN_CONTAINER_MEMORY_BYTES
        ),
        "baseline_rss_reserve_bytes": PUBLISHER_BASELINE_RSS_RESERVE_BYTES,
        "single_body_raw_reserve_bytes": (
            PUBLISHER_SINGLE_BODY_RAW_RESERVE_BYTES
        ),
        "single_body_decode_expansion_multiplier": (
            PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER
        ),
        "single_body_decode_expansion_reserve_bytes": (
            PUBLISHER_SINGLE_BODY_DECODE_RESERVE_BYTES
        ),
        "compact_state_expansion_multiplier": (
            PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER
        ),
        "compact_state_expansion_reserve_bytes": (
            PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES
        ),
        "derivation_output_reserve_bytes": (
            PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES
        ),
        "worst_case_rss_bytes": PUBLISHER_WORST_CASE_RSS_BYTES,
        "maximum_envelope_bytes": MAXIMUM_PUBLISHER_ENVELOPE_BYTES,
        "maximum_retained_full_evaluation_body_count": 1,
        "expected_compact_evaluation_record_count": (
            _EXPECTED_COMPACT_EVALUATION_RECORD_COUNTS[mode]
        ),
    }
    return _with_hash(body, field="resource_precharge_sha256")


def _validate_resource_precharge_v1(
    value: object, *, mode: str,
    scientific_identities: Sequence[Mapping[str, object]],
    topology: Mapping[str, object], request: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="publisher resource precharge")
    expected_fields = {
        "schema_version", "mode", "scientific_read_count",
        "scientific_read_bytes", "evaluation_read_count",
        "evaluation_read_bytes", "maximum_single_scientific_body_bytes",
        "maximum_compact_evaluation_state_bytes", "maximum_wall_seconds",
        "maximum_peak_rss_bytes", "maximum_address_space_bytes",
        "required_cloud_run_container_memory_bytes",
        "baseline_rss_reserve_bytes", "single_body_raw_reserve_bytes",
        "single_body_decode_expansion_multiplier",
        "single_body_decode_expansion_reserve_bytes",
        "compact_state_expansion_multiplier",
        "compact_state_expansion_reserve_bytes",
        "derivation_output_reserve_bytes", "worst_case_rss_bytes",
        "maximum_envelope_bytes",
        "maximum_retained_full_evaluation_body_count",
        "expected_compact_evaluation_record_count",
        "resource_precharge_sha256",
    }
    if set(item) != expected_fields:
        _fail("publisher resource precharge fields differ")
    _self_hash(
        item, field="resource_precharge_sha256",
        label="publisher resource precharge",
    )
    expected = _compile_resource_precharge_v1(
        request=request, topology=topology,
        scientific_identities=scientific_identities,
    )
    if mode != request["mode"] or item != expected:
        _fail("publisher resource precharge canonical replay differs")
    return expected


def _stream_compact_evaluations_v1(
    *, phase: str, identities: Sequence[Mapping[str, object]],
    opener: _ExactScientificJsonOpenerV1, design: Mapping[str, object],
    design_identity: Mapping[str, object],
    topology_identity: Mapping[str, object], topology: Mapping[str, object],
    started_at: float, clock: Callable[[], float],
    peak_rss_bytes: Callable[[], int],
    initial_compact_state_bytes: int = 2,
    initial_compact_record_count: int = 0,
) -> tuple[list[dict[str, object]], int]:
    role = (
        "broad-evaluation-result"
        if phase == contract.BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
        if phase == contract.CONFIRMATION_PHASE
        else ""
    )
    if not role or len(identities) != contract.PANEL_SLATE_COUNT:
        _fail("publisher streamed evaluation phase lattice differs")
    read_role_prefix = (
        "broad" if phase == contract.BROAD_SCREEN_PHASE else "confirmation"
    )
    topology_rows = [
        row for row in topology["objects"] if row["role"] == role
    ]
    if len(topology_rows) != contract.PANEL_SLATE_COUNT:
        _fail("publisher streamed evaluation topology differs")
    records: list[dict[str, object]] = []
    if (
        type(initial_compact_state_bytes) is not int
        or type(initial_compact_record_count) is not int
        or initial_compact_state_bytes < 2
        or initial_compact_record_count < 0
    ):
        _fail("publisher initial compact evaluation state differs")
    compact_state_bytes = initial_compact_state_bytes
    slate_ids: set[str] = set()
    for source, (identity, descriptor) in enumerate(
        zip(identities, topology_rows, strict=True)
    ):
        body, retained_identity = opener.open(
            role=f"{read_role_prefix}-evaluation-{source:02d}",
            identity_value=identity,
        )
        try:
            evaluation = contract.validate_evaluation_result_v1(body)
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(
                str(exc)
            ) from exc
        _bind(
            evaluation, retained_identity,
            label=f"{phase} evaluation publication[{source}]",
        )
        slate_id = _string(
            evaluation.get("slate_id"), label=f"{phase} slate id[{source}]"
        )
        if (
            evaluation.get("source_ordinal") != source
            or evaluation.get("phase") != phase
            or evaluation.get("publication_role") != role
            or evaluation.get("design_publication_identity") != design_identity
            or evaluation.get("design_sha256") != design["design_sha256"]
            or evaluation.get("topology_identity") != topology_identity
            or retained_identity["uri"] != descriptor["uri"]
            or slate_id in slate_ids
        ):
            _fail("publisher streamed evaluation authority differs")
        slate_ids.add(slate_id)
        try:
            compact = contract._compact_evaluation_record_v1({
                "source_ordinal": source,
                "slate_id": slate_id,
                "phase": phase,
                "body": evaluation,
                "identity": retained_identity,
            })
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(
                str(exc)
            ) from exc
        minimal = contract._minimal_aggregate_evaluation_record_v1(compact)
        raw_minimal = contract.canonical_json_bytes_v1(minimal)
        compact_state_bytes += len(raw_minimal) + (
            1 if initial_compact_record_count + len(records) else 0
        )
        if compact_state_bytes > MAXIMUM_COMPACT_EVALUATION_STATE_BYTES:
            _fail("publisher compact evaluation state exceeds resource precharge")
        records.append(minimal)
        del body, evaluation, compact, minimal, raw_minimal
        _require_resource_checkpoint_v1(
            started_at=started_at, clock=clock, peak_rss_bytes=peak_rss_bytes,
            label=f"publisher streamed {phase} evaluation[{source}]",
        )
    if len(records) != contract.PANEL_SLATE_COUNT:
        _fail("publisher compact evaluation record count differs")
    return records, compact_state_bytes


def _nomination_from_compact_records_v1(
    *, design: Mapping[str, object], design_identity: Mapping[str, object],
    run_identity: Mapping[str, object], records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    try:
        broad = contract._build_broad_phase_authority_from_records_v1(
            retained_design=design,
            retained_design_identity=design_identity,
            run_identity=run_identity,
            records=records,
        )
        nomination = contract.deterministic_nominees_from_broad_authority_v1(
            broad
        )
        body = _with_hash({
            "schema_version": contract.NOMINATION_PUBLICATION_SCHEMA,
            "contract_id": contract.CONTRACT_ID,
            "design_publication_identity": dict(design_identity),
            "run_identity": dict(run_identity),
            "broad_phase_authority": broad,
            "broad_phase_authority_sha256": broad[
                "broad_phase_authority_sha256"
            ],
            "nomination": nomination,
            "nomination_sha256": nomination["nomination_sha256"],
            "derivation_law": (
                "exact-54-broad-evaluations-to-broad-authority-and-nomination"
            ),
            "caller_broad_authority_or_nominees_accepted": False,
            "policy": dict(contract.POLICY_CLAIMS),
        }, field="nomination_publication_sha256")
        return contract.validate_nomination_publication_v1(body)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc


def run_publisher_v1(
    request_value: object,
    *,
    observed_runtime: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    _clock: Callable[[], float] = monotonic,
    _peak_rss_bytes: Callable[[], int] = _peak_rss_bytes_v1,
    _address_space_limiter: Callable[[], int] = _require_address_space_limit_v1,
) -> dict[str, object]:
    """Execute one fixed publisher from exact JSON authorities only."""
    if _address_space_limiter() != MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES:
        _fail("publisher installed address-space limit differs")
    started_at = _clock()
    if type(started_at) not in {int, float}:
        _fail("publisher monotonic start observation differs")
    request = validate_publisher_request_v1(request_value)
    observed = validate_observed_runtime_evidence_v1(observed_runtime)
    if (
        observed["mode"] != request["mode"]
        or observed["process_role"] != request["process_role"]
    ):
        _fail("observed publisher runtime differs from request")
    (
        design,
        topology,
        bootstrap_manifest,
        process_budget,
        _,
        scientific_identities,
        ledger,
    ) = _validate_common_authorities_v1(
        request=request, observed_runtime=observed, read_exact=read_exact
    )
    del _
    runtime_observation = _runtime_observation_v1(
        request=request,
        observed=observed,
        bootstrap_manifest=bootstrap_manifest,
        process_budget=process_budget,
    )
    writes = _write_descriptors_v1(
        request=request, process_budget=process_budget, topology=topology
    )
    # The complete output lattice is checked before any call capable of
    # creating an object.  In aggregate mode this precharges both writes.
    if len(writes) != int(process_budget["write_object_count"]):
        _fail("publisher writes were not fully precharged")

    resource_precharge = _compile_resource_precharge_v1(
        request=request, topology=topology,
        scientific_identities=scientific_identities,
    )
    _validate_resource_precharge_v1(
        resource_precharge, mode=str(request["mode"]),
        scientific_identities=scientific_identities,
        topology=topology, request=request,
    )
    _require_resource_checkpoint_v1(
        started_at=float(started_at), clock=_clock,
        peak_rss_bytes=_peak_rss_bytes,
        label="publisher scientific precharge",
    )

    opener = _ExactScientificJsonOpenerV1(
        identities=scientific_identities, read_exact=read_exact, ledger=ledger
    )
    publication_records: list[dict[str, object]] = []

    def publish(
        *, body: Mapping[str, object], descriptor: Mapping[str, object],
        prior: object,
    ) -> dict[str, object]:
        identity, byte_count = _publish_v1(
            body=body, descriptor=descriptor, prior_identity=prior,
            publish_create_once=publish_create_once,
        )
        publication_records.append({
            "publication_index": len(publication_records),
            "ordinal": descriptor["ordinal"],
            "role": descriptor["role"],
            "identity": identity,
            "body_sha256": _publication_body_hash_v1(body),
            "publication_bytes": byte_count,
            "publication_byte_ceiling": descriptor["max_bytes"],
        })
        return identity

    mode = str(request["mode"])
    terminal_opener_calls = 0
    retained_compact_evaluation_record_count = 0
    retained_compact_evaluation_state_bytes = 0
    if mode == PUBLISH_NOMINATION:
        broad_records, broad_compact_bytes = _stream_compact_evaluations_v1(
            phase=contract.BROAD_SCREEN_PHASE,
            identities=request["broad_evaluation_identities"],
            opener=opener, design=design,
            design_identity=request["design_identity"],
            topology_identity=request["topology_identity"], topology=topology,
            started_at=float(started_at), clock=_clock,
            peak_rss_bytes=_peak_rss_bytes,
        )
        retained_compact_evaluation_record_count = len(broad_records)
        retained_compact_evaluation_state_bytes = broad_compact_bytes
        nomination = _nomination_from_compact_records_v1(
            design=design, design_identity=request["design_identity"],
            run_identity=bootstrap_manifest["run_identity"],
            records=broad_records,
        )
        nomination_identity = publish(
            body=nomination, descriptor=writes[0],
            prior=request["prior_nomination_identity"],
        )
        try:
            contract.validate_nomination_publication_authority_v1(
                nomination,
                publication_identity=nomination_identity,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
        del broad_records

    elif mode == PUBLISH_AGGREGATE_FINALISTS:
        broad_records, broad_compact_bytes = _stream_compact_evaluations_v1(
            phase=contract.BROAD_SCREEN_PHASE,
            identities=request["broad_evaluation_identities"],
            opener=opener, design=design,
            design_identity=request["design_identity"],
            topology_identity=request["topology_identity"], topology=topology,
            started_at=float(started_at), clock=_clock,
            peak_rss_bytes=_peak_rss_bytes,
        )
        nomination, nomination_identity = opener.open(
            role="nomination", identity_value=request["nomination_identity"]
        )
        try:
            nomination = contract.validate_nomination_publication_authority_v1(
                nomination, publication_identity=nomination_identity
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
        confirmation_records, confirmation_compact_bytes = (
            _stream_compact_evaluations_v1(
                phase=contract.CONFIRMATION_PHASE,
                identities=request["confirmation_evaluation_identities"],
                opener=opener, design=design,
                design_identity=request["design_identity"],
                topology_identity=request["topology_identity"],
                topology=topology, started_at=float(started_at), clock=_clock,
                peak_rss_bytes=_peak_rss_bytes,
                initial_compact_state_bytes=broad_compact_bytes,
                initial_compact_record_count=len(broad_records),
            )
        )
        retained_compact_evaluation_state_bytes = confirmation_compact_bytes
        if retained_compact_evaluation_state_bytes > (
            MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
        ):
            _fail("publisher compact evaluation state exceeds resource precharge")
        retained_compact_evaluation_record_count = (
            len(broad_records) + len(confirmation_records)
        )
        try:
            aggregate = contract._build_aggregate_mechanics_from_records_v1(
                retained_design=design,
                retained_design_identity=request["design_identity"],
                run_identity=bootstrap_manifest["run_identity"],
                nomination_publication=nomination,
                nomination_publication_identity=nomination_identity,
                broad_records=broad_records,
                confirmation_records=confirmation_records,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
        aggregate_identity = publish(
            body=aggregate, descriptor=writes[0],
            prior=request["prior_aggregate_identity"],
        )
        try:
            reopened_aggregate = contract.validate_aggregate_mechanics_authority_v1(
                aggregate, publication_identity=aggregate_identity
            )
            finalists = contract.deterministic_finalists_from_aggregate_v1(
                reopened_aggregate,
                aggregate_publication_identity=aggregate_identity,
            )
            finalist_publication = contract.build_finalist_publication_v1(
                finalists=finalists,
                aggregate=reopened_aggregate,
                aggregate_publication_identity=aggregate_identity,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
        finalist_identity = publish(
            body=finalist_publication, descriptor=writes[1],
            prior=request["prior_finalist_identity"],
        )
        try:
            contract.validate_finalist_publication_authority_v1(
                finalist_publication,
                publication_identity=finalist_identity,
                aggregate=reopened_aggregate,
                aggregate_publication_identity=aggregate_identity,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
        del broad_records, confirmation_records, nomination

    else:
        topology_rows = list(topology["objects"][:-1])
        if len(topology_rows) != contract.OUTPUT_OBJECT_COUNT - 1:
            _fail("terminal topology predecessor count differs")

        def predecessor_opener(
            descriptor_value: Mapping[str, object],
        ) -> tuple[dict[str, object], dict[str, object]]:
            nonlocal terminal_opener_calls
            descriptor = _mapping(
                descriptor_value, label="terminal predecessor descriptor"
            )
            if terminal_opener_calls >= len(topology_rows):
                _fail("terminal predecessor opener was overcalled")
            expected = _mapping(
                topology_rows[terminal_opener_calls],
                label="expected terminal predecessor descriptor",
            )
            if descriptor != expected:
                _fail("terminal predecessor descriptor/order differs")
            identity = request["predecessor_identities"][terminal_opener_calls]
            if identity["uri"] != expected["uri"]:
                _fail("terminal predecessor identity URI/order differs")
            body, retained_identity = opener.open(
                role=f"terminal-{int(expected['ordinal']):03d}-{expected['role']}",
                identity_value=identity,
            )
            terminal_opener_calls += 1
            return body, retained_identity

        try:
            root = contract.build_terminal_root_from_stream_v1(
                design=design,
                design_publication_identity=request["design_identity"],
                predecessor_opener=predecessor_opener,
                maximum_compact_evaluation_state_bytes=(
                    MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
                ),
                resource_checkpoint=lambda label: (
                    _require_resource_checkpoint_v1(
                        started_at=float(started_at), clock=_clock,
                        peak_rss_bytes=_peak_rss_bytes, label=label,
                    )
                ),
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
        if (
            terminal_opener_calls != contract.OUTPUT_OBJECT_COUNT - 1
            or root.get("predecessor_opener_call_count")
            != contract.OUTPUT_OBJECT_COUNT - 1
            or root.get("retained_full_evaluation_body_count") != 0
            or root.get("streaming_body_list_accepted") is not False
        ):
            _fail("terminal streaming reduction evidence differs")
        retained_compact_evaluation_record_count = int(
            root.get("retained_compact_evaluation_record_count", -1)
        )
        retained_compact_evaluation_state_bytes = int(
            root.get("retained_compact_evaluation_state_bytes", -1)
        )
        if retained_compact_evaluation_record_count != (
            _EXPECTED_COMPACT_EVALUATION_RECORD_COUNTS[mode]
        ) or not 2 <= retained_compact_evaluation_state_bytes <= (
            MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
        ):
            _fail("terminal compact evaluation record count differs")
        root_identity = publish(
            body=root, descriptor=writes[0], prior=request["prior_root_identity"]
        )
        # The builder is the one-pass authority.  Calling the mirrored stream
        # validator here would consume the 274-object budget a second time.
        # Exact create/resume transport has already reopened and byte-compared
        # the returned generation; this bind proves that generation contains
        # the exact builder result.
        _bind(root, root_identity, label="terminal root publication")

    opener.require_complete()
    expected_read_count = int(
        process_budget["read_object_count_excluding_budget_authority"]
    ) + 1
    if (
        len(ledger) != expected_read_count
        or opener.call_count != len(scientific_identities)
    ):
        _fail("publisher exact-read ledger count differs from precharge")
    if [row["role"] for row in publication_records] != list(
        MODE_WRITE_ROLES[mode]
    ):
        _fail("publisher publication order differs")
    if retained_compact_evaluation_record_count != (
        _EXPECTED_COMPACT_EVALUATION_RECORD_COUNTS[mode]
    ) or not 2 <= retained_compact_evaluation_state_bytes <= (
        MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
    ):
        _fail("publisher retained compact evaluation record count differs")
    observed_elapsed_milliseconds, observed_peak_rss_bytes = (
        _require_resource_checkpoint_v1(
            started_at=float(started_at), clock=_clock,
            peak_rss_bytes=_peak_rss_bytes,
            label="publisher terminal envelope",
        )
    )

    body = {
        "schema_version": PUBLISHER_ENVELOPE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "mode": mode,
        "process_role": request["process_role"],
        "process_ordinal": 0,
        "publisher_request_sha256": request["publisher_request_sha256"],
        "bootstrap_manifest_identity": request["bootstrap_manifest_identity"],
        "launch_intent_identity": request["launch_intent_identity"],
        "process_budget_identity": request["process_budget_identity"],
        "process_budget_sha256": process_budget[
            "publisher_process_budget_sha256"
        ],
        "runtime_observation": runtime_observation,
        "runtime_observation_sha256": runtime_observation[
            "runtime_observation_sha256"
        ],
        "read_ledger": ledger,
        "read_ledger_sha256": contract.canonical_sha256_v1(ledger),
        "read_object_count": len(ledger),
        "scientific_read_count": len(scientific_identities),
        "write_precharge": writes,
        "write_precharge_sha256": contract.canonical_sha256_v1(writes),
        "all_writes_precharged_before_first_create": True,
        "publication_count": len(publication_records),
        "publications": publication_records,
        "publications_sha256": contract.canonical_sha256_v1(publication_records),
        "resource_precharge": resource_precharge,
        "resource_precharge_sha256": resource_precharge[
            "resource_precharge_sha256"
        ],
        "observed_elapsed_milliseconds": observed_elapsed_milliseconds,
        "observed_peak_rss_bytes": observed_peak_rss_bytes,
        "maximum_retained_full_evaluation_body_count": 1,
        "retained_compact_evaluation_record_count": (
            retained_compact_evaluation_record_count
        ),
        "retained_compact_evaluation_state_bytes": (
            retained_compact_evaluation_state_bytes
        ),
        "terminal_predecessor_opener_call_count": (
            terminal_opener_calls if mode == PUBLISH_TERMINAL_ROOT else 0
        ),
        "terminal_full_predecessor_body_list_materialized": False,
        "caller_scientific_bodies_accepted": False,
        "caller_grids_nominees_comparisons_bootstraps_accepted": False,
        "transport_semantics": {
            "fixed_project": FIXED_GCP_PROJECT,
            "fixed_endpoint": FIXED_STORAGE_ENDPOINT,
            "generation_exact_reads": True,
            "create_once_precondition_zero": True,
            "successful_create_exact_reopen_required": True,
            "collision_requires_supplied_exact_identity": True,
            "current_generation_resolution_allowed": False,
            "listing_allowed": False,
            "platform_retry_allowed": False,
        },
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="publisher_envelope_sha256")


def validate_publisher_envelope_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="publisher envelope")
    expected_fields = {
        "schema_version", "contract_id", "mode", "process_role",
        "process_ordinal", "publisher_request_sha256",
        "bootstrap_manifest_identity", "launch_intent_identity",
        "process_budget_identity", "process_budget_sha256",
        "runtime_observation", "runtime_observation_sha256", "read_ledger",
        "read_ledger_sha256", "read_object_count", "scientific_read_count",
        "write_precharge", "write_precharge_sha256",
        "all_writes_precharged_before_first_create", "publication_count",
        "publications", "publications_sha256",
        "resource_precharge", "resource_precharge_sha256",
        "observed_elapsed_milliseconds", "observed_peak_rss_bytes",
        "maximum_retained_full_evaluation_body_count",
        "retained_compact_evaluation_record_count",
        "retained_compact_evaluation_state_bytes",
        "terminal_predecessor_opener_call_count",
        "terminal_full_predecessor_body_list_materialized",
        "caller_scientific_bodies_accepted",
        "caller_grids_nominees_comparisons_bootstraps_accepted",
        "transport_semantics", "policy", "publisher_envelope_sha256",
    }
    if set(item) != expected_fields:
        _fail("publisher envelope fields differ")
    _self_hash(
        item, field="publisher_envelope_sha256", label="publisher envelope"
    )
    mode = _string(item.get("mode"), label="publisher envelope mode")
    if mode not in PUBLISHER_MODES:
        _fail("publisher envelope mode differs")
    ledger = [
        _mapping(row, label=f"publisher envelope read[{index}]")
        for index, row in enumerate(
            _sequence(item.get("read_ledger"), label="publisher envelope reads")
        )
    ]
    publications = [
        _mapping(row, label=f"publisher envelope publication[{index}]")
        for index, row in enumerate(
            _sequence(item.get("publications"), label="publisher publications")
        )
    ]
    writes = [
        _mapping(row, label=f"publisher envelope write[{index}]")
        for index, row in enumerate(
            _sequence(item.get("write_precharge"), label="publisher writes")
        )
    ]
    runtime = _mapping(item.get("runtime_observation"), label="runtime observation")
    resource_precharge = _mapping(
        item.get("resource_precharge"), label="publisher resource precharge"
    )
    resource_fields = {
        "schema_version", "mode", "scientific_read_count",
        "scientific_read_bytes", "evaluation_read_count",
        "evaluation_read_bytes", "maximum_single_scientific_body_bytes",
        "maximum_compact_evaluation_state_bytes", "maximum_wall_seconds",
        "maximum_peak_rss_bytes", "maximum_address_space_bytes",
        "required_cloud_run_container_memory_bytes",
        "baseline_rss_reserve_bytes", "single_body_raw_reserve_bytes",
        "single_body_decode_expansion_multiplier",
        "single_body_decode_expansion_reserve_bytes",
        "compact_state_expansion_multiplier",
        "compact_state_expansion_reserve_bytes",
        "derivation_output_reserve_bytes", "worst_case_rss_bytes",
        "maximum_envelope_bytes",
        "maximum_retained_full_evaluation_body_count",
        "expected_compact_evaluation_record_count",
        "resource_precharge_sha256",
    }
    if set(resource_precharge) != resource_fields:
        _fail("publisher resource precharge fields differ")
    _self_hash(
        resource_precharge, field="resource_precharge_sha256",
        label="publisher resource precharge",
    )
    try:
        contract._self_hash(
            runtime, field="runtime_observation_sha256",
            label="publisher runtime observation",
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenAggregateV1Error(str(exc)) from exc
    expected_terminal_calls = (
        contract.OUTPUT_OBJECT_COUNT - 1 if mode == PUBLISH_TERMINAL_ROOT else 0
    )
    scientific_ledger = ledger[5:]
    evaluation_ledger = [
        row for row in scientific_ledger
        if "evaluation-" in str(row.get("role", ""))
    ]
    observed_elapsed = _integer(
        item.get("observed_elapsed_milliseconds"),
        label="publisher observed elapsed milliseconds",
    )
    observed_rss = _integer(
        item.get("observed_peak_rss_bytes"),
        label="publisher observed peak RSS bytes",
    )
    compact_state_bytes = _integer(
        item.get("retained_compact_evaluation_state_bytes"),
        label="publisher retained compact evaluation state bytes",
    )
    if (
        item.get("schema_version") != PUBLISHER_ENVELOPE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("process_role") != MODE_PROCESS_ROLE[mode]
        or item.get("process_ordinal") != 0
        or item.get("runtime_observation_sha256")
        != runtime.get("runtime_observation_sha256")
        or item.get("read_object_count") != len(ledger)
        or item.get("read_ledger_sha256") != contract.canonical_sha256_v1(ledger)
        or item.get("publication_count") != len(publications)
        or len(publications) != len(MODE_WRITE_ROLES[mode])
        or [row.get("role") for row in publications]
        != list(MODE_WRITE_ROLES[mode])
        or item.get("publications_sha256")
        != contract.canonical_sha256_v1(publications)
        or item.get("resource_precharge_sha256")
        != resource_precharge.get("resource_precharge_sha256")
        or resource_precharge.get("schema_version")
        != PUBLISHER_RESOURCE_PRECHARGE_SCHEMA
        or resource_precharge.get("mode") != mode
        or resource_precharge.get("scientific_read_count")
        != len(scientific_ledger)
        or resource_precharge.get("scientific_read_bytes")
        != sum(int(row["identity"]["bytes"]) for row in scientific_ledger)
        or resource_precharge.get("evaluation_read_count")
        != len(evaluation_ledger)
        or len(evaluation_ledger) != _EXPECTED_EVALUATION_READ_COUNTS[mode]
        or resource_precharge.get("evaluation_read_bytes")
        != sum(int(row["identity"]["bytes"]) for row in evaluation_ledger)
        or any(
            int(row["identity"]["bytes"])
            > MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
            for row in scientific_ledger
        )
        or resource_precharge.get("maximum_single_scientific_body_bytes")
        != MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        or resource_precharge.get("maximum_compact_evaluation_state_bytes")
        != MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
        or resource_precharge.get("maximum_wall_seconds")
        != MAXIMUM_PUBLISHER_WALL_SECONDS
        or resource_precharge.get("maximum_peak_rss_bytes")
        != MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
        or resource_precharge.get("maximum_address_space_bytes")
        != MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES
        or resource_precharge.get("required_cloud_run_container_memory_bytes")
        != REQUIRED_CLOUD_RUN_CONTAINER_MEMORY_BYTES
        or resource_precharge.get("baseline_rss_reserve_bytes")
        != PUBLISHER_BASELINE_RSS_RESERVE_BYTES
        or resource_precharge.get("single_body_raw_reserve_bytes")
        != PUBLISHER_SINGLE_BODY_RAW_RESERVE_BYTES
        or resource_precharge.get("single_body_decode_expansion_multiplier")
        != PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER
        or resource_precharge.get(
            "single_body_decode_expansion_reserve_bytes"
        ) != PUBLISHER_SINGLE_BODY_DECODE_RESERVE_BYTES
        or resource_precharge.get("compact_state_expansion_multiplier")
        != PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER
        or resource_precharge.get("compact_state_expansion_reserve_bytes")
        != PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES
        or resource_precharge.get("derivation_output_reserve_bytes")
        != PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES
        or resource_precharge.get("worst_case_rss_bytes")
        != PUBLISHER_WORST_CASE_RSS_BYTES
        or PUBLISHER_WORST_CASE_RSS_BYTES > MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
        or MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
        >= REQUIRED_CLOUD_RUN_CONTAINER_MEMORY_BYTES
        or resource_precharge.get("maximum_envelope_bytes")
        != MAXIMUM_PUBLISHER_ENVELOPE_BYTES
        or resource_precharge.get(
            "maximum_retained_full_evaluation_body_count"
        ) != 1
        or resource_precharge.get("expected_compact_evaluation_record_count")
        != _EXPECTED_COMPACT_EVALUATION_RECORD_COUNTS[mode]
        or item.get("maximum_retained_full_evaluation_body_count") != 1
        or item.get("retained_compact_evaluation_record_count")
        != _EXPECTED_COMPACT_EVALUATION_RECORD_COUNTS[mode]
        or not 2 <= compact_state_bytes <= MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
        or observed_elapsed > MAXIMUM_PUBLISHER_WALL_SECONDS * 1_000
        or observed_rss > MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
        or len(writes) != len(publications)
        or item.get("write_precharge_sha256")
        != contract.canonical_sha256_v1(writes)
        or item.get("all_writes_precharged_before_first_create") is not True
        or item.get("terminal_predecessor_opener_call_count")
        != expected_terminal_calls
        or item.get("terminal_full_predecessor_body_list_materialized") is not False
        or item.get("caller_scientific_bodies_accepted") is not False
        or item.get(
            "caller_grids_nominees_comparisons_bootstraps_accepted"
        ) is not False
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("publisher envelope authority differs")
    for index, row in enumerate(ledger):
        if row.get("ordinal") != index:
            _fail("publisher envelope read order differs")
        _identity(row.get("identity"), label="publisher envelope read identity")
    for index, row in enumerate(publications):
        if row.get("publication_index") != index:
            _fail("publisher envelope publication order differs")
        _identity(
            row.get("identity"), label="publisher envelope publication identity"
        )
    return item


__all__ = [
    "FIXED_GCP_PROJECT",
    "FIXED_STORAGE_ENDPOINT",
    "MODE_PROCESS_ROLE",
    "PUBLISH_AGGREGATE_FINALISTS",
    "PUBLISH_NOMINATION",
    "PUBLISH_TERMINAL_ROOT",
    "PUBLISHER_ENVELOPE_SCHEMA",
    "PUBLISHER_MODES",
    "PUBLISHER_REQUEST_SCHEMA",
    "PUBLISHER_RUNTIME_EVIDENCE_SCHEMA",
    "CorpusR6CurrentBankCrossedScreenAggregateV1Error",
    "build_publisher_request_v1",
    "canonical_publisher_command_v1",
    "derive_observed_runtime_evidence_v1",
    "run_publisher_v1",
    "strict_json_v1",
    "validate_observed_runtime_evidence_v1",
    "validate_publisher_envelope_v1",
    "validate_publisher_request_v1",
]
