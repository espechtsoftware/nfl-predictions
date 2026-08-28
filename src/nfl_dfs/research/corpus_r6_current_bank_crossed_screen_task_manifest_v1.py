"""Immutable task-array authority for the R6 current-bank crossed screen.

This module is deliberately transport-free.  It freezes the only supported
external execution layers, binds every Cloud Run task index to one canonical
request and its topology-derived outputs, validates the pre-design run
authorization, and builds compact task and layer terminal evidence.  Callers
provide generation-exact byte readers and create-once publishers; there is no
listing, current-generation resolution, graph, outcome, subprocess, or cloud
client capability here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)


PRE_DESIGN_RUN_AUTHORIZATION_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-pre-design-run-authorization/v1"
)
PROJECTION_TASK_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-projection-task-request/v1"
)
SELECTION_ASSEMBLER_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-selection-slate-assembler-request/v1"
)
EVALUATOR_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-evaluator-request/v1"
)
PUBLISHER_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-publisher-request/v1"
)
PROJECTION_EXECUTION_SUMMARY_SCHEMA: Final = (
    "corpus-r6-current-bank-projection-execution-summary/v1"
)
SELECTION_ASSEMBLER_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-selection-slate-assembler-envelope/v1"
)
EVALUATOR_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-evaluator-envelope/v1"
)
PUBLISHER_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-publisher-envelope/v1"
)
TASK_MANIFEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-task-manifest/v1"
)
CHILD_TASK_BINDING_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-child-task-binding-evidence/v1"
)
TASK_TERMINAL_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-task-terminal-evidence/v1"
)
DISPATCHER_RUNTIME_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-dispatcher-runtime-evidence/v1"
)
LAYER_EXECUTION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-layer-execution-receipt/v1"
)
OBSERVED_CLOUD_RUN_EXECUTION_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-observed-cloud-run-execution/v1"
)
CLOUD_RUN_EXECUTION_OBSERVATION_SOURCE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-run-execution-observation-source/v1"
)
LAYER_RESUME_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-layer-resume-authority/post-smoke-design-v1"
)

FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"
FIXED_CLOUD_RUN_LOCATION: Final = "us-central1"
FIXED_CLOUD_RUN_CPU_LIMIT: Final = "8"
FIXED_CLOUD_RUN_MEMORY_LIMIT: Final = "32Gi"
MAXIMUM_IDENTITY_ENV_BYTES: Final = 2_048
MAXIMUM_MANIFEST_BYTES: Final = 64_000_000
MAXIMUM_AUTHORIZATION_BYTES: Final = 2_000_000
MAXIMUM_TOPOLOGY_BYTES: Final = 4_000_000
MAXIMUM_BOOTSTRAP_MANIFEST_BYTES: Final = 8_000_000
MAXIMUM_DESIGN_BYTES: Final = 64_000_000
MAXIMUM_PROCESS_BUDGET_BYTES: Final = 16_000_000
MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES: Final = 512_000
MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES: Final = 4_000_000
MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES: Final = 4_000_000
MAXIMUM_CHILD_STDERR_BYTES: Final = 256_000
MAXIMUM_DISPATCHER_EXACT_IDENTITY_PROOFS: Final = 64
MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES: Final = 1_000_000_000
MAXIMUM_DISPATCHER_WALL_SECONDS: Final = 7_260
# These evaluator limits are mirrored here so this controller can bind the
# child envelope without importing the scientific evaluator.
_EVALUATOR_MAXIMUM_PLAYER_COUNT: Final = 512
_EVALUATOR_MAXIMUM_SOURCE_CANDIDATE_ROWS: Final = (
    contract.MAX_SELECTION_CANDIDATES_PER_FOLD
)
_EVALUATOR_MAXIMUM_EVALUATION_CANDIDATES: Final = 8_192
_EVALUATOR_MAXIMUM_LATER_SOURCE_BYTES: Final = 8_000_000
_EVALUATOR_MAXIMUM_COMPRESSED_WORLD_BYTES: Final = 128_000_000
_EVALUATOR_MAXIMUM_PLAYER_DRAW_MEMBER_BYTES: Final = (
    _EVALUATOR_MAXIMUM_PLAYER_COUNT * contract.WORLDS_PER_BLOCK * 4 + 65_536
)
_EVALUATOR_MAXIMUM_SCORE_MATRIX_BYTES: Final = (
    _EVALUATOR_MAXIMUM_EVALUATION_CANDIDATES
    * contract.WORLDS_PER_BLOCK * 8
)
_EVALUATOR_MAXIMUM_CANDIDATE_WORLD_ADDITIONS_PER_FOLD: Final = (
    _EVALUATOR_MAXIMUM_EVALUATION_CANDIDATES
    * contract.WORLDS_PER_BLOCK * 9
)
_EVALUATOR_MAXIMUM_PEAK_RSS_BYTES: Final = 7_500_000_000
_PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES: Final = 768_000_000
_PUBLISHER_MAXIMUM_COMPACT_EVALUATION_STATE_BYTES: Final = 64_000_000
_PUBLISHER_MAXIMUM_PEAK_RSS_BYTES: Final = 24 * 1024 * 1024 * 1024
_PROVIDER_CONTAINER_MEMORY_BYTES: Final = 32 * 1024 * 1024 * 1024
_PUBLISHER_PROVIDER_MEMORY_MARGIN_BYTES: Final = (
    _PROVIDER_CONTAINER_MEMORY_BYTES - _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES
)
_PUBLISHER_BASELINE_RSS_RESERVE_BYTES: Final = 2 * 1024 * 1024 * 1024
_PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER: Final = 16
_PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_RESERVE_BYTES: Final = (
    _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
    * _PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER
)
_PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER: Final = 8
_PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES: Final = (
    _PUBLISHER_MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
    * _PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER
)
_PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES: Final = 4 * 1024 * 1024 * 1024
_PUBLISHER_WORST_CASE_RSS_BYTES: Final = (
    _PUBLISHER_BASELINE_RSS_RESERVE_BYTES
    + _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
    + _PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_RESERVE_BYTES
    + _PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES
    + _PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES
)
# Post-smoke design bounds.  PRE_OUTPUT_RECOVERY_ALLOWED keeps every related
# pure design API fail-closed and none are exported or consumed in this release.
MAXIMUM_LAYER_RESUME_AUTHORITY_BYTES: Final = 256_000
MAXIMUM_LAYER_RECOVERY_EPOCHS: Final = 3
PRE_OUTPUT_RECOVERY_ALLOWED: Final = False

DISPATCH_MANIFEST_IDENTITY_ENV: Final = (
    "R6_CURRENT_BANK_TASK_MANIFEST_IDENTITY"
)
DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: Final = (
    "R6_CURRENT_BANK_LAYER_RESUME_AUTHORITY_IDENTITY"
)
ABSENT_RESUME_AUTHORITY_ENV_VALUE: Final = "absent"
CHILD_MANIFEST_IDENTITY_ENV: Final = "R6_TASK_MANIFEST_IDENTITY"
CHILD_MANIFEST_SELF_HASH_ENV: Final = "R6_TASK_MANIFEST_SELF_SHA256"
CHILD_TASK_BINDING_HASH_ENV: Final = "R6_TASK_BINDING_SHA256"
CHILD_LAYER_ID_ENV: Final = "R6_TASK_LAYER_ID"
CHILD_TASK_INDEX_ENV: Final = "R6_TASK_INDEX"
CHILD_REQUEST_HASH_ENV: Final = "R6_TASK_REQUEST_SHA256"
CHILD_OUTPUTS_HASH_ENV: Final = "R6_TASK_OUTPUTS_SHA256"
CHILD_COMMAND_HASH_ENV: Final = "R6_TASK_CHILD_COMMAND_SHA256"

_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_GENERATION_RE: Final = re.compile(r"[1-9][0-9]{0,30}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_SAFE_NAME_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}\Z")
_COMPLETE_PROVIDER_JOB_ENVIRONMENT_SEMANTICS: Final = (
    "complete-cloud-run-v2-provider-job-container-environment"
)
_FORBIDDEN_IMAGE_LAUNCH_ENVIRONMENT_KEYS: Final = frozenset({
    "CURL_CA_BUNDLE",
    "GCE_METADATA_HOST",
    "GCE_METADATA_IP",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "LD_AUDIT",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "PYTHONBREAKPOINT",
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
})

ReadExact = Callable[[Mapping[str, object]], bytes]
CreateOnce = Callable[[str, bytes], object]
ProveExactIdentity = Callable[[Mapping[str, object]], Mapping[str, object]]
_VALIDATED_PREDECESSOR_TOKEN: Final = object()


class CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(ValueError):
    """An immutable task/controller authority could not be proven exact."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str, maximum: int = 2_048) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        _fail(f"{label} must be a nonempty bounded string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        _fail(f"{label} contains a control character")
    return value


def _integer(value: object, *, label: str, maximum: int = 10**12) -> int:
    if type(value) is not int or value < 0 or value > maximum:
        _fail(f"{label} must be a bounded nonnegative integer")
    return value


def _sha(value: object, *, label: str) -> str:
    retained = _string(value, label=label, maximum=64)
    if _SHA256_RE.fullmatch(retained) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return retained


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = _string(item.get("uri"), label=f"{label} URI", maximum=2_048)
    generation = _string(
        item.get("generation"), label=f"{label} generation", maximum=31
    )
    byte_count = _integer(
        item.get("bytes"), label=f"{label} bytes", maximum=200_000_000_000
    )
    if (
        not uri.startswith("gs://")
        or "?" in uri
        or "#" in uri
        or uri.endswith("/")
        or "//" in uri[5:]
        or any(part in {"", ".", ".."} for part in uri[5:].split("/"))
        or _GENERATION_RE.fullmatch(generation) is None
        or byte_count < 1
    ):
        _fail(f"{label} is not a safe generation-exact GCS identity")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha(item.get("sha256"), label=f"{label} SHA-256"),
        "bytes": byte_count,
    }


def _optional_identity(value: object, *, label: str) -> dict[str, object] | None:
    return None if value is None else _identity(value, label=label)


def _canonical_bytes(value: object) -> bytes:
    return contract.canonical_json_bytes_v1(value)


def _canonical_sha(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    body[field] = _canonical_sha(body)
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    if value.get(field) != _canonical_sha({key: row for key, row in value.items() if key != field}):
        _fail(f"{label} self hash differs")


def strict_json_v1(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse one canonical JSON object, rejecting duplicates and nonfinite values."""
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        retained: dict[str, object] = {}
        for key, value in values:
            if key in retained:
                _fail(f"{label} contains duplicate key {key!r}")
            retained[key] = value
        return retained

    def nonfinite(token: str) -> object:
        _fail(f"{label} contains nonfinite number {token}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical_bytes(item) != raw:
        _fail(f"{label} bytes are not canonical")
    return item


def _bind_body(value: Mapping[str, object], identity_value: object, *, label: str) -> dict[str, object]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = _canonical_bytes(value)
    if identity["bytes"] != len(raw) or identity["sha256"] != sha256(raw).hexdigest():
        _fail(f"{label} body identity differs")
    return identity


def _read_json_exact(
    identity_value: object, *, read_exact: ReadExact, label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    ceiling = _integer(
        maximum_bytes, label=f"{label} read byte ceiling",
        maximum=200_000_000_000,
    )
    if identity["bytes"] > ceiling:
        _fail(f"{label} identity exceeds its role-specific byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact body differs")
    return strict_json_v1(raw, label=label), identity


@dataclass(frozen=True)
class _LayerSpec:
    layer_id: str
    phase: str
    process_role: str
    mode: str
    task_count: int
    output_roles: tuple[str, ...]
    predecessor_layers: tuple[str, ...]
    request_kind: str
    request_byte_ceiling: int
    child_stdout_byte_ceiling: int
    maximum_wall_seconds: int


_LAYER_SPECS: Final = (
    _LayerSpec("projection", "projection", "projection-publisher", "publish-projection", 1, ("projection",), (), "projection", 512_000, 4_000_000, 7_200),
    _LayerSpec("broad-selection-receipt", contract.BROAD_SCREEN_PHASE, "broad-slate-assembler", "slate-assembler", contract.PANEL_SLATE_COUNT, ("broad-selection-receipt",), ("projection",), "selection", 16_000_000, 4_000_000, 7_200),
    _LayerSpec("broad-evaluation-result", contract.BROAD_SCREEN_PHASE, "broad-evaluator", "evaluate-slate", contract.PANEL_SLATE_COUNT, ("broad-evaluation-result",), ("projection", "broad-selection-receipt"), "evaluation", 128_000, 2_000_000, 1_800),
    _LayerSpec("nomination", contract.BROAD_SCREEN_PHASE, "broad-nomination-publisher", "publish-nomination", 1, ("nomination",), ("projection", "broad-selection-receipt", "broad-evaluation-result"), "publisher", 512_000, 4_000_000, 1_800),
    _LayerSpec("confirmation-selection-receipt", contract.CONFIRMATION_PHASE, "confirmation-slate-assembler", "slate-assembler", contract.PANEL_SLATE_COUNT, ("confirmation-selection-receipt",), ("projection", "broad-selection-receipt", "broad-evaluation-result", "nomination"), "selection", 16_000_000, 4_000_000, 7_200),
    _LayerSpec("confirmation-evaluation-result", contract.CONFIRMATION_PHASE, "confirmation-evaluator", "evaluate-slate", contract.PANEL_SLATE_COUNT, ("confirmation-evaluation-result",), ("projection", "broad-selection-receipt", "broad-evaluation-result", "nomination", "confirmation-selection-receipt"), "evaluation", 128_000, 2_000_000, 1_800),
    _LayerSpec("aggregate-finalists", contract.CONFIRMATION_PHASE, "aggregate-finalist-publisher", "publish-aggregate-finalists", 1, ("aggregate", "confirmed-finalists"), ("projection", "broad-selection-receipt", "broad-evaluation-result", "nomination", "confirmation-selection-receipt", "confirmation-evaluation-result"), "publisher", 512_000, 4_000_000, 1_800),
    _LayerSpec("terminal-root", "terminal", "terminal-root-publisher", "publish-terminal-root", 1, ("root",), ("projection", "broad-selection-receipt", "broad-evaluation-result", "nomination", "confirmation-selection-receipt", "confirmation-evaluation-result", "aggregate-finalists"), "publisher", 512_000, 4_000_000, 1_800),
)

_OUTPUT_STREAM_BYTE_CEILINGS: Final = {
    "projection": 256_000_000,
    "broad-selection-receipt": contract.BROAD_SELECTION_RECEIPT_MAX_BYTES,
    "broad-evaluation-result": 256_000_000,
    "nomination": 16_000_000,
    "confirmation-selection-receipt": (
        contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES
    ),
    "confirmation-evaluation-result": 768_000_000,
    "aggregate": 256_000_000,
    "confirmed-finalists": 16_000_000,
    "root": 16_000_000,
}
_LAYER_BY_ID: Final = {row.layer_id: row for row in _LAYER_SPECS}


def _layer(layer_id: object) -> _LayerSpec:
    retained = _string(layer_id, label="layer ID", maximum=64)
    if retained not in _LAYER_BY_ID:
        _fail("layer ID is not registered")
    return _LAYER_BY_ID[retained]


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def _entrypoint(path: Path) -> dict[str, object]:
    retained = path.resolve()
    if not retained.is_file():
        _fail("canonical task entrypoint is absent")
    try:
        relative = retained.relative_to(_repository_root_v1().resolve())
    except ValueError:
        _fail("canonical task entrypoint is outside the image source tree")
    return {
        "entrypoint_path": "/app/" + relative.as_posix(),
        "entrypoint_sha256": sha256(retained.read_bytes()).hexdigest(),
    }


def canonical_dispatcher_process_spec_v1() -> dict[str, object]:
    path = _repository_root_v1() / "scripts" / "run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
    entrypoint = _entrypoint(path)
    command = ["/usr/local/bin/python3.11", "-I", entrypoint["entrypoint_path"]]
    return {
        "component_role": "dispatcher",
        "command": command,
        **entrypoint,
        "image_canonical_command_authority": True,
        "ambient_host_command_authority": False,
    }


def _single_process_spec(role: str, script: str, mode: str | None) -> dict[str, object]:
    entrypoint = _entrypoint(_repository_root_v1() / "scripts" / script)
    command = ["/usr/local/bin/python3.11", entrypoint["entrypoint_path"]]
    if mode is not None:
        command.append(mode)
    return {
        "process_role": role,
        "process_chain": [{"component_role": "main", "command": command, **entrypoint}],
    }


def canonical_bootstrap_process_specs_v1() -> list[dict[str, object]]:
    """Return the only A--D process inventory accepted by a task manifest."""
    selection_script = "run_corpus_r6_current_bank_crossed_screen_selection_v1.py"
    selection_path = _entrypoint(_repository_root_v1() / "scripts" / selection_script)
    matrix_path = _entrypoint(
        _repository_root_v1() / "src" / "nfl_dfs" / "research"
        / "corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1.py"
    )
    python = "/usr/local/bin/python3.11"
    fold_chain = [
        {
            "component_role": "artifact-broker",
            "command": [python, selection_path["entrypoint_path"], "fold-broker"],
            **selection_path,
        },
        {
            "component_role": "matrix-selector",
            "command": [python, matrix_path["entrypoint_path"], "matrix-selector"],
            **matrix_path,
        },
    ]
    by_role: dict[str, dict[str, object]] = {
        "projection-publisher": _single_process_spec(
            "projection-publisher",
            "run_corpus_r6_current_bank_crossed_screen_projection_v1.py",
            None,
        ),
        "broad-fold-selector": {"process_role": "broad-fold-selector", "process_chain": deepcopy(fold_chain)},
        "broad-slate-assembler": _single_process_spec("broad-slate-assembler", selection_script, "slate-assembler"),
        "broad-evaluator": _single_process_spec("broad-evaluator", "run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py", "evaluate-slate"),
        "confirmation-fold-selector": {"process_role": "confirmation-fold-selector", "process_chain": deepcopy(fold_chain)},
        "confirmation-slate-assembler": _single_process_spec("confirmation-slate-assembler", selection_script, "slate-assembler"),
        "confirmation-evaluator": _single_process_spec("confirmation-evaluator", "run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py", "evaluate-slate"),
        "broad-nomination-publisher": _single_process_spec("broad-nomination-publisher", "run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py", "publish-nomination"),
        "aggregate-finalist-publisher": _single_process_spec("aggregate-finalist-publisher", "run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py", "publish-aggregate-finalists"),
        "terminal-root-publisher": _single_process_spec("terminal-root-publisher", "run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py", "publish-terminal-root"),
    }
    if set(by_role) != set(contract.PROCESS_ROLES):
        _fail("canonical process inventory differs from contract roles")
    return [deepcopy(by_role[role]) for role in contract.PROCESS_ROLES]


def image_entrypoint_authority_v1(
    *, dispatcher_process_spec: Mapping[str, object] | None = None,
    bootstrap_process_specs: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Bind source hashes only to the fixed `/app` paths used by the image."""
    dispatcher = dict(
        dispatcher_process_spec or canonical_dispatcher_process_spec_v1()
    )
    process_specs = [
        dict(row) for row in (
            bootstrap_process_specs or canonical_bootstrap_process_specs_v1()
        )
    ]
    root = _repository_root_v1().resolve()
    components = [{"process_role": "dispatcher", **dispatcher}]
    for spec in process_specs:
        for component in spec["process_chain"]:
            components.append({
                "process_role": spec["process_role"],
                **_mapping(component, label="image process component"),
            })
    rows: list[dict[str, object]] = []
    for index, component in enumerate(components):
        image_path = _string(
            component["entrypoint_path"], label="image entrypoint path"
        )
        if not image_path.startswith("/app/"):
            _fail("entrypoint is not an image-canonical /app path")
        relative = Path(image_path.removeprefix("/app/"))
        observed = (root / relative).resolve()
        if not observed.is_file() or sha256(observed.read_bytes()).hexdigest() != component["entrypoint_sha256"]:
            _fail("image entrypoint source/hash authority differs")
        rows.append({
            "ordinal": index,
            "process_role": component["process_role"],
            "component_role": component["component_role"],
            "repository_relative_path": relative.as_posix(),
            "image_canonical_path": image_path,
            "entrypoint_sha256": component["entrypoint_sha256"],
            "image_workdir": "/app",
            "ambient_host_path_is_image_authority": False,
            "image_canonical_command_authority": True,
        })
    return rows


def _process_spec(
    process_role: str,
    process_specs: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    snapshot = process_specs or canonical_bootstrap_process_specs_v1()
    rows = [dict(row) for row in snapshot if row["process_role"] == process_role]
    if len(rows) != 1:
        _fail("canonical process role is absent or repeated")
    return rows[0]


def _required_process_specs(
    layer: _LayerSpec,
    process_specs: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    roles = [layer.process_role]
    if layer.request_kind == "selection":
        roles.append(
            "broad-fold-selector"
            if layer.phase == contract.BROAD_SCREEN_PHASE
            else "confirmation-fold-selector"
        )
    return [_process_spec(role, process_specs) for role in roles]


def layer_registry_v1(
    output_prefix: str,
    *, _process_specs: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    topology = contract.build_result_topology_v1(output_prefix)
    prefix = str(topology["output_prefix"])
    process_specs = _process_specs or canonical_bootstrap_process_specs_v1()
    return [
        {
            "layer_ordinal": ordinal,
            "layer_id": row.layer_id,
            "phase": row.phase,
            "process_role": row.process_role,
            "mode": row.mode,
            "task_count": row.task_count,
            "parallelism": row.task_count,
            "output_roles": list(row.output_roles),
            "predecessor_layers": list(row.predecessor_layers),
            "request_kind": row.request_kind,
            "request_byte_ceiling": row.request_byte_ceiling,
            "child_stdout_byte_ceiling": row.child_stdout_byte_ceiling,
            "child_stderr_byte_ceiling": MAXIMUM_CHILD_STDERR_BYTES,
            "maximum_wall_seconds": row.maximum_wall_seconds,
            "manifest_uri": f"{prefix}authorities/task-manifests/{ordinal:02d}-{row.layer_id}.json",
            "layer_execution_receipt_uri": f"{prefix}authorities/layer-execution-receipts/{ordinal:02d}-{row.layer_id}.json",
            "cloud_run_observation_source_uri": (
                f"{prefix}authorities/cloud-run-execution-observations/"
                f"{ordinal:02d}-{row.layer_id}/initial.json"
            ),
            "recovery_allowed": False,
            "maximum_recovery_epochs": 0,
            "resume_authority_uris": [],
            "required_process_specs": _required_process_specs(row, process_specs),
        }
        for ordinal, row in enumerate(_LAYER_SPECS)
    ]


def _layer_descriptor(output_prefix: str, layer_id: str) -> dict[str, object]:
    rows = [row for row in layer_registry_v1(output_prefix) if row["layer_id"] == layer_id]
    if len(rows) != 1:
        _fail("registered layer descriptor is absent")
    return rows[0]


def _dispatcher_stream_proof_budgets_v1(
    *, topology: Mapping[str, object], registry: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    topology_rows = [
        _mapping(row, label=f"stream-proof topology row[{index}]")
        for index, row in enumerate(_sequence(
            topology.get("objects"), label="stream-proof topology rows"
        ))
    ]
    budgets: list[dict[str, object]] = []
    for layer in registry:
        output_roles = list(layer["output_roles"])
        descriptors = [
            row for row in topology_rows if row.get("role") in output_roles
        ]
        descriptor_ceilings = [
            _OUTPUT_STREAM_BYTE_CEILINGS[str(row["role"])] for row in descriptors
        ]
        task_count = int(layer["task_count"])
        if task_count == 1:
            proof_counts_by_task = [len(descriptors)]
            streamed_bytes_by_task = [sum(descriptor_ceilings)]
        else:
            if len(descriptors) != task_count:
                _fail("stream-proof topology/task descriptor count differs")
            proof_counts_by_task = [1] * task_count
            streamed_bytes_by_task = descriptor_ceilings
        if (
            not descriptors
            or max(proof_counts_by_task)
            > MAXIMUM_DISPATCHER_EXACT_IDENTITY_PROOFS
            or any(
                value > MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES
                for value in descriptor_ceilings
            )
        ):
            _fail("dispatcher streamed identity-proof ceiling differs")
        budgets.append({
            "layer_id": layer["layer_id"],
            "task_count": task_count,
            "output_proof_counts_by_task": proof_counts_by_task,
            "streamed_byte_ceilings_by_task": streamed_bytes_by_task,
            "layer_output_proof_count": sum(proof_counts_by_task),
            "layer_streamed_byte_ceiling": sum(streamed_bytes_by_task),
            "derived_from_exact_topology_output_descriptors": True,
        })
    return budgets


def _host_terminal_observation_budget_v1(
    *, output_prefix: str, registry: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Authorize only the host's bounded terminal-evidence generation harvest."""
    layers = []
    for row in registry:
        count = int(row["task_count"])
        layer_id = str(row["layer_id"])
        uris = [
            f"{output_prefix}authorities/task-terminal-evidence/"
            f"{layer_id}/task-{index:03d}.json"
            for index in range(count)
        ]
        layers.append({
            "layer_ordinal": int(row["layer_ordinal"]),
            "layer_id": layer_id,
            "task_count": count,
            "terminal_evidence_uris_sha256": _canonical_sha(uris),
        })
    return {
        "resolver_role": "host-finalizer-only",
        "uri_source": "exact-manifest-task-terminal-evidence-uris",
        "maximum_resolution_count_per_layer": max(
            int(row["task_count"]) for row in registry
        ),
        "total_resolution_count": sum(int(row["task_count"]) for row in registry),
        "per_layer_resolution_authorities": layers,
        "per_layer_resolution_authorities_sha256": _canonical_sha(layers),
        "current_generation_metadata_lookup_per_uri": 1,
        "immediate_generation_pin_required": True,
        "generation_exact_hash_read_required": True,
        "listing_allowed": False,
        "logs_allowed": False,
        "scientific_output_resolution_allowed": False,
    }


def _task_terminal_generation_resolution_base_v1(
    task_bindings: object,
) -> dict[str, object]:
    bindings = _sequence(
        task_bindings, label="terminal generation-resolution task bindings"
    )
    uris = [
        _string(
            _mapping(row, label=f"terminal generation binding[{index}]").get(
                "task_terminal_evidence_uri"
            ),
            label=f"terminal generation URI[{index}]",
            maximum=2_048,
        )
        for index, row in enumerate(bindings)
    ]
    if not uris or len(set(uris)) != len(uris):
        _fail("terminal generation-resolution URI ledger differs")
    return {
        "resolver_role": "host-finalizer-only",
        "uri_source": "exact-manifest-task-terminal-evidence-uris",
        "resolved_uri_count": len(uris),
        "resolved_uris_sha256": _canonical_sha(uris),
        "current_generation_metadata_lookup_per_uri": 1,
        "immediate_generation_pin_required": True,
        "generation_exact_hash_read_required": True,
        "listing_allowed": False,
        "logs_allowed": False,
        "scientific_output_resolution_allowed": False,
    }


def _host_terminal_generation_resolution_authority_v1(
    task_bindings: object,
) -> dict[str, object]:
    return {
        **_task_terminal_generation_resolution_base_v1(task_bindings),
        "current_generation_resolution_required": True,
    }


def _task_terminal_generation_resolution_scope_v1(
    task_bindings: object,
) -> dict[str, object]:
    return {
        **_task_terminal_generation_resolution_base_v1(task_bindings),
        "current_generation_resolution_performed": True,
    }


def build_pre_design_run_authorization_v1(
    *, output_prefix: str, code_commit: str, image_digest: str,
    reused_job_name: str,
) -> dict[str, object]:
    """Freeze the run, topology, image, one job, and complete layer order."""
    topology = contract.build_result_topology_v1(output_prefix)
    commit = _string(code_commit, label="authorized code commit", maximum=40)
    digest = _string(image_digest, label="authorized image digest", maximum=71)
    job = _string(reused_job_name, label="authorized reused job", maximum=63)
    if (
        _COMMIT_RE.fullmatch(commit) is None
        or not digest.startswith("sha256:")
        or _SHA256_RE.fullmatch(digest[7:]) is None
        or _JOB_RE.fullmatch(job) is None
    ):
        _fail("pre-design code/image/job authorization differs")
    dispatcher = canonical_dispatcher_process_spec_v1()
    process_specs = canonical_bootstrap_process_specs_v1()
    registry = layer_registry_v1(
        str(topology["output_prefix"]), _process_specs=process_specs
    )
    image_entrypoints = image_entrypoint_authority_v1(
        dispatcher_process_spec=dispatcher,
        bootstrap_process_specs=process_specs,
    )
    total_dispatchers = sum(int(row["task_count"]) for row in registry)
    simultaneous_process_trees = [
        {
            "layer_id": row["layer_id"],
            "simultaneous_process_tree_maximum": 1 + sum(
                len(spec["process_chain"])
                for spec in row["required_process_specs"]
            ),
            "derived_from_registered_dispatcher_and_process_chains": True,
        }
        for row in registry
    ]
    stream_proof_budgets = _dispatcher_stream_proof_budgets_v1(
        topology=topology, registry=registry
    )
    host_terminal_observation_budget = _host_terminal_observation_budget_v1(
        output_prefix=str(topology["output_prefix"]), registry=registry
    )
    publisher_resource_precharge = {
        "maximum_single_scientific_body_bytes": (
            _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        ),
        "maximum_peak_rss_bytes": _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES,
        "maximum_address_space_bytes": _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES,
        "required_cloud_run_container_memory_bytes": (
            _PROVIDER_CONTAINER_MEMORY_BYTES
        ),
        "baseline_rss_reserve_bytes": _PUBLISHER_BASELINE_RSS_RESERVE_BYTES,
        "single_body_raw_reserve_bytes": (
            _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        ),
        "single_body_decode_expansion_multiplier": (
            _PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER
        ),
        "single_body_decode_expansion_reserve_bytes": (
            _PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_RESERVE_BYTES
        ),
        "compact_state_expansion_multiplier": (
            _PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER
        ),
        "compact_state_expansion_reserve_bytes": (
            _PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES
        ),
        "derivation_output_reserve_bytes": (
            _PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES
        ),
        "worst_case_rss_bytes": _PUBLISHER_WORST_CASE_RSS_BYTES,
        "worst_case_rss_within_process_limit": True,
        "process_limit_strictly_below_provider_memory": True,
    }
    if not (
        _PUBLISHER_WORST_CASE_RSS_BYTES
        <= _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES
        < _PROVIDER_CONTAINER_MEMORY_BYTES
    ):
        _fail("publisher resource precharge does not fit provider memory")
    dispatcher_budget = {
        "external_dispatcher_process_count": total_dispatchers,
        "maximum_processes_per_dispatcher_task": max(
            int(row["simultaneous_process_tree_maximum"])
            for row in simultaneous_process_trees
        ),
        "simultaneous_process_tree_by_layer": simultaneous_process_trees,
        "simultaneous_process_tree_by_layer_sha256": _canonical_sha(
            simultaneous_process_trees
        ),
        "maximum_exact_reads_per_dispatcher": 256,
        "maximum_total_exact_reads": total_dispatchers * 256,
        "maximum_resume_authority_reads_per_dispatcher": 0,
        "maximum_resume_authority_bytes": 0,
        "maximum_resume_terminal_reopens_per_dispatcher": 0,
        "maximum_create_once_writes_per_dispatcher": 1,
        "maximum_total_create_once_writes": total_dispatchers,
        "maximum_dispatcher_rss_bytes": 512 * 1024 * 1024,
        "maximum_dispatcher_wall_seconds": MAXIMUM_DISPATCHER_WALL_SECONDS,
        "maximum_dispatcher_stdout_bytes": 8_192,
        "maximum_dispatcher_stderr_bytes": MAXIMUM_CHILD_STDERR_BYTES,
        "cloud_run_container_resource_limits": {
            "cpu": FIXED_CLOUD_RUN_CPU_LIMIT,
            "memory": FIXED_CLOUD_RUN_MEMORY_LIMIT,
        },
        "cloud_run_container_working_directory": "",
        "cloud_run_container_volume_mounts": [],
        "cloud_run_task_template_volumes": [],
        "publisher_maximum_single_scientific_body_bytes": (
            _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        ),
        "publisher_maximum_peak_rss_bytes": _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES,
        "cloud_run_container_memory_bytes": _PROVIDER_CONTAINER_MEMORY_BYTES,
        "publisher_provider_memory_margin_bytes": (
            _PUBLISHER_PROVIDER_MEMORY_MARGIN_BYTES
        ),
        "publisher_peak_rss_strictly_below_provider_memory": True,
        "publisher_resource_precharge_authority": publisher_resource_precharge,
        "publisher_resource_precharge_authority_sha256": _canonical_sha(
            publisher_resource_precharge
        ),
        "maximum_exact_identity_proofs_per_dispatcher": (
            MAXIMUM_DISPATCHER_EXACT_IDENTITY_PROOFS
        ),
        "maximum_streamed_bytes_per_exact_identity_proof": (
            MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES
        ),
        "streamed_publication_proof_budgets": stream_proof_budgets,
        "streamed_publication_proof_budgets_sha256": _canonical_sha(
            stream_proof_budgets
        ),
        "external_observation_source_object_count": len(registry),
        "maximum_observation_source_bytes_each": (
            MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES
        ),
        "external_observation_source_create_once_writes": len(registry),
        "layer_receipt_observation_source_exact_reads": len(registry),
    }
    body = {
        "schema_version": PRE_DESIGN_RUN_AUTHORIZATION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "authorization_semantics": "pre-design-run-authorization-and-launch-intent-token",
        "cloud_execution_attestation": False,
        "output_prefix": topology["output_prefix"],
        "child_run_prefix": topology["child_run_prefix"],
        "topology_sha256": topology["topology_sha256"],
        "code_commit": commit,
        "image_digest": digest,
        "reused_job_name": job,
        "dispatcher_process_spec": dispatcher,
        "dispatcher_process_spec_sha256": _canonical_sha(dispatcher),
        "layer_registry": registry,
        "layer_registry_sha256": _canonical_sha(registry),
        "layer_count": len(registry),
        "dispatcher_resource_budget": dispatcher_budget,
        "dispatcher_resource_budget_sha256": _canonical_sha(dispatcher_budget),
        "host_terminal_observation_budget": host_terminal_observation_budget,
        "host_terminal_observation_budget_sha256": _canonical_sha(
            host_terminal_observation_budget
        ),
        "image_entrypoint_authority": image_entrypoints,
        "image_entrypoint_authority_sha256": _canonical_sha(image_entrypoints),
        "one_reused_job_across_layers": True,
        "per_task_deploy_allowed": False,
        "maximum_task_retries": 0,
        "manifest_identity_known_at_authorization_time": False,
        "manifest_uri_lattice_frozen": True,
        "uses_realized_outcomes": False,
        "graph_capability_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    retained = _with_hash(body, field="pre_design_run_authorization_sha256")
    if len(_canonical_bytes(retained)) > MAXIMUM_AUTHORIZATION_BYTES:
        _fail("pre-design run authorization exceeds its byte ceiling")
    return retained


def validate_pre_design_run_authorization_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="pre-design run authorization")
    expected_fields = {
        "schema_version", "contract_id", "authorization_semantics",
        "cloud_execution_attestation", "output_prefix", "child_run_prefix",
        "topology_sha256", "code_commit", "image_digest", "reused_job_name",
        "dispatcher_process_spec", "dispatcher_process_spec_sha256",
        "layer_registry", "layer_registry_sha256", "layer_count",
        "dispatcher_resource_budget", "dispatcher_resource_budget_sha256",
        "host_terminal_observation_budget",
        "host_terminal_observation_budget_sha256",
        "image_entrypoint_authority", "image_entrypoint_authority_sha256",
        "one_reused_job_across_layers", "per_task_deploy_allowed",
        "maximum_task_retries", "manifest_identity_known_at_authorization_time",
        "manifest_uri_lattice_frozen", "uses_realized_outcomes",
        "graph_capability_allowed", "policy",
        "pre_design_run_authorization_sha256",
    }
    if set(item) != expected_fields:
        _fail("pre-design run authorization fields differ")
    _self_hash(item, field="pre_design_run_authorization_sha256", label="pre-design run authorization")
    expected = build_pre_design_run_authorization_v1(
        output_prefix=_string(item.get("output_prefix"), label="authorized output prefix"),
        code_commit=_string(item.get("code_commit"), label="authorized code commit"),
        image_digest=_string(item.get("image_digest"), label="authorized image digest"),
        reused_job_name=_string(item.get("reused_job_name"), label="authorized reused job"),
    )
    if _canonical_bytes(item) != _canonical_bytes(expected):
        _fail("pre-design run authorization canonical replay differs")
    return expected


def pre_design_run_authorization_uri_v1(output_prefix: str) -> str:
    topology = contract.build_result_topology_v1(output_prefix)
    return str(topology["output_prefix"]) + "authorities/pre-design-run-authorization.json"


def validate_pre_design_run_authorization_authority_v1(
    value: object, *, publication_identity: object, topology: object,
) -> dict[str, object]:
    retained = validate_pre_design_run_authorization_v1(value)
    identity = _bind_body(retained, publication_identity, label="pre-design run authorization")
    retained_topology = contract.validate_result_topology_v1(topology)
    if (
        identity["uri"] != pre_design_run_authorization_uri_v1(str(retained_topology["output_prefix"]))
        or retained["output_prefix"] != retained_topology["output_prefix"]
        or retained["topology_sha256"] != retained_topology["topology_sha256"]
    ):
        _fail("pre-design run authorization topology/URI binding differs")
    return retained


def build_projection_task_request_v1(
    *, design_identity: object, topology_identity: object,
    bootstrap_manifest_identity: object,
    pre_design_run_authorization_identity: object,
    process_budget_identity: object,
    prior_projection_identities: object = (),
) -> dict[str, object]:
    """Build A's closed request; its CLI argv is rendered only from this body."""
    raw_priors = _sequence(
        prior_projection_identities, label="prior projection identities"
    )
    if not raw_priors:
        raw_priors = [None] * contract.PANEL_SLATE_COUNT
    if len(raw_priors) != contract.PANEL_SLATE_COUNT:
        _fail("projection task requires exactly 54 prior-identity slots")
    priors = [
        _optional_identity(value, label=f"prior projection identity[{index}]")
        for index, value in enumerate(raw_priors)
    ]
    body = {
        "schema_version": PROJECTION_TASK_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "process_role": "projection-publisher",
        "process_ordinal": 0,
        "design_identity": _identity(design_identity, label="projection design"),
        "topology_identity": _identity(topology_identity, label="projection topology"),
        "bootstrap_manifest_identity": _identity(
            bootstrap_manifest_identity, label="projection bootstrap manifest"
        ),
        "pre_design_run_authorization_identity": _identity(
            pre_design_run_authorization_identity,
            label="projection pre-design run authorization",
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="projection publisher process budget"
        ),
        "prior_projection_identities": priors,
        "caller_output_uri_accepted": False,
        "caller_command_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="projection_task_request_sha256")


def validate_projection_task_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="projection task request")
    if set(item) != {
        "schema_version", "contract_id", "process_role", "process_ordinal",
        "design_identity", "topology_identity", "bootstrap_manifest_identity",
        "pre_design_run_authorization_identity", "process_budget_identity",
        "prior_projection_identities",
        "caller_output_uri_accepted", "caller_command_accepted", "policy",
        "projection_task_request_sha256",
    }:
        _fail("projection task request fields differ")
    _self_hash(item, field="projection_task_request_sha256", label="projection task request")
    expected = build_projection_task_request_v1(
        design_identity=item.get("design_identity"),
        topology_identity=item.get("topology_identity"),
        bootstrap_manifest_identity=item.get("bootstrap_manifest_identity"),
        pre_design_run_authorization_identity=item.get(
            "pre_design_run_authorization_identity"
        ),
        process_budget_identity=item.get("process_budget_identity"),
        prior_projection_identities=item.get("prior_projection_identities"),
    )
    if _canonical_bytes(item) != _canonical_bytes(expected):
        _fail("projection task request canonical replay differs")
    return expected


def _validate_request_for_layer(layer: _LayerSpec, value: object) -> dict[str, object]:
    """Validate a request without acquiring any A--D/scientific capability."""
    if layer.request_kind == "projection":
        return validate_projection_task_request_v1(value)
    if layer.request_kind == "selection":
        return _validate_selection_request_v1(value)
    if layer.request_kind == "evaluation":
        return _validate_evaluation_request_v1(value)
    return _validate_publisher_request_v1(value)


def build_selection_task_request_v1(
    *, phase: str, source_ordinal: int, design_identity: object,
    topology_identity: object, projection_bundle_identity: object,
    assembler_process_budget_identity: object,
    worker_process_budget_identities: object,
    nomination_identity: object | None = None,
    prior_selection_receipt_identity: object | None = None,
) -> dict[str, object]:
    """Build the manifest-canonical selection assembler request."""
    retained_phase = _string(phase, label="selection phase", maximum=64)
    source = _integer(
        source_ordinal, label="selection source ordinal",
        maximum=contract.PANEL_SLATE_COUNT - 1,
    )
    nomination = _optional_identity(
        nomination_identity, label="selection nomination"
    )
    if retained_phase == contract.BROAD_SCREEN_PHASE:
        if nomination is not None:
            _fail("broad selection request cannot accept nomination authority")
    elif retained_phase == contract.CONFIRMATION_PHASE:
        if nomination is None:
            _fail("confirmation selection request requires nomination authority")
    else:
        _fail("selection request phase differs")
    worker_budgets = [
        _identity(row, label=f"selection worker budget[{index}]")
        for index, row in enumerate(_sequence(
            worker_process_budget_identities,
            label="selection worker budgets",
        ))
    ]
    if len(worker_budgets) != contract.FOLDS_PER_SLATE:
        _fail("selection request worker budget count differs")
    body = {
        "schema_version": SELECTION_ASSEMBLER_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": source,
        "design_identity": _identity(
            design_identity, label="selection design"
        ),
        "topology_identity": _identity(
            topology_identity, label="selection topology"
        ),
        "projection_bundle_identity": _identity(
            projection_bundle_identity,
            label="selection projection bundle",
        ),
        "assembler_process_budget_identity": _identity(
            assembler_process_budget_identity,
            label="selection assembler process budget",
        ),
        "worker_process_budget_identities": worker_budgets,
        "nomination_identity": nomination,
        "prior_selection_receipt_identity": _optional_identity(
            prior_selection_receipt_identity,
            label="selection prior receipt",
        ),
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="assembler_request_sha256")


def _validate_selection_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="selection assembler request")
    fields = {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "design_identity", "topology_identity", "projection_bundle_identity",
        "assembler_process_budget_identity", "worker_process_budget_identities",
        "nomination_identity", "prior_selection_receipt_identity", "policy",
        "assembler_request_sha256",
    }
    if set(item) != fields:
        _fail("selection assembler request fields differ")
    _self_hash(item, field="assembler_request_sha256", label="selection assembler request")
    expected = build_selection_task_request_v1(
        phase=item.get("phase"),
        source_ordinal=item.get("source_ordinal"),
        design_identity=item.get("design_identity"),
        topology_identity=item.get("topology_identity"),
        projection_bundle_identity=item.get("projection_bundle_identity"),
        assembler_process_budget_identity=item.get(
            "assembler_process_budget_identity"
        ),
        worker_process_budget_identities=item.get(
            "worker_process_budget_identities"
        ),
        nomination_identity=item.get("nomination_identity"),
        prior_selection_receipt_identity=item.get(
            "prior_selection_receipt_identity"
        ),
    )
    if _canonical_bytes(item) != _canonical_bytes(expected):
        _fail("selection assembler request canonical replay differs")
    return expected


def build_evaluation_task_request_v1(
    *, phase: str, source_ordinal: int, design_identity: object,
    topology_identity: object, projection_bundle_identity: object,
    selection_receipt_identity: object, process_budget_identity: object,
    bootstrap_manifest_identity: object, launch_intent_identity: object,
    nomination_identity: object | None = None,
    prior_evaluation_identity: object | None = None,
) -> dict[str, object]:
    """Build the manifest-canonical evaluator request."""
    retained_phase = _string(phase, label="evaluator phase", maximum=64)
    source = _integer(
        source_ordinal, label="evaluator source ordinal",
        maximum=contract.PANEL_SLATE_COUNT - 1,
    )
    nomination = _optional_identity(
        nomination_identity, label="evaluator nomination"
    )
    if retained_phase == contract.BROAD_SCREEN_PHASE:
        if nomination is not None:
            _fail("broad evaluator request cannot accept nomination authority")
    elif retained_phase == contract.CONFIRMATION_PHASE:
        if nomination is None:
            _fail("confirmation evaluator request requires nomination authority")
    else:
        _fail("evaluator request phase differs")
    body = {
        "schema_version": EVALUATOR_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": source,
        "process_ordinal": source,
        "design_identity": _identity(
            design_identity, label="evaluator design"
        ),
        "topology_identity": _identity(
            topology_identity, label="evaluator topology"
        ),
        "projection_bundle_identity": _identity(
            projection_bundle_identity,
            label="evaluator projection bundle",
        ),
        "selection_receipt_identity": _identity(
            selection_receipt_identity,
            label="evaluator selection receipt",
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="evaluator process budget"
        ),
        "bootstrap_manifest_identity": _identity(
            bootstrap_manifest_identity, label="evaluator bootstrap"
        ),
        "launch_intent_identity": _identity(
            launch_intent_identity, label="evaluator launch intent"
        ),
        "nomination_identity": nomination,
        "prior_evaluation_identity": _optional_identity(
            prior_evaluation_identity, label="prior evaluation"
        ),
        "caller_heldout_identities_accepted": False,
        "caller_matrix_or_metric_input_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="evaluator_request_sha256")


def _validate_evaluation_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="evaluator request")
    fields = {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "process_ordinal", "design_identity", "topology_identity",
        "projection_bundle_identity", "selection_receipt_identity",
        "process_budget_identity", "bootstrap_manifest_identity",
        "launch_intent_identity", "nomination_identity",
        "prior_evaluation_identity", "caller_heldout_identities_accepted",
        "caller_matrix_or_metric_input_accepted", "policy",
        "evaluator_request_sha256",
    }
    if set(item) != fields:
        _fail("evaluator request fields differ")
    _self_hash(item, field="evaluator_request_sha256", label="evaluator request")
    expected = build_evaluation_task_request_v1(
        phase=item.get("phase"),
        source_ordinal=item.get("source_ordinal"),
        design_identity=item.get("design_identity"),
        topology_identity=item.get("topology_identity"),
        projection_bundle_identity=item.get("projection_bundle_identity"),
        selection_receipt_identity=item.get("selection_receipt_identity"),
        process_budget_identity=item.get("process_budget_identity"),
        bootstrap_manifest_identity=item.get("bootstrap_manifest_identity"),
        launch_intent_identity=item.get("launch_intent_identity"),
        nomination_identity=item.get("nomination_identity"),
        prior_evaluation_identity=item.get("prior_evaluation_identity"),
    )
    if _canonical_bytes(item) != _canonical_bytes(expected):
        _fail("evaluator request canonical replay differs")
    return expected


def build_publisher_task_request_v1(
    *, mode: str, design_identity: object, topology_identity: object,
    bootstrap_manifest_identity: object, launch_intent_identity: object,
    process_budget_identity: object, broad_evaluation_identities: object = (),
    nomination_identity: object | None = None,
    confirmation_evaluation_identities: object = (),
    predecessor_identities: object = (),
    prior_nomination_identity: object | None = None,
    prior_aggregate_identity: object | None = None,
    prior_finalist_identity: object | None = None,
    prior_root_identity: object | None = None,
) -> dict[str, object]:
    """Build the manifest-canonical deterministic publisher request."""
    retained_mode = _string(mode, label="publisher mode", maximum=64)
    role_by_mode = {
        "publish-nomination": "broad-nomination-publisher",
        "publish-aggregate-finalists": "aggregate-finalist-publisher",
        "publish-terminal-root": "terminal-root-publisher",
    }
    if retained_mode not in role_by_mode:
        _fail("publisher mode differs")
    broad = [
        _identity(row, label=f"broad evaluation[{index}]")
        for index, row in enumerate(_sequence(
            broad_evaluation_identities, label="broad evaluations"
        ))
    ]
    confirmation = [
        _identity(row, label=f"confirmation evaluation[{index}]")
        for index, row in enumerate(_sequence(
            confirmation_evaluation_identities,
            label="confirmation evaluations",
        ))
    ]
    predecessors = [
        _identity(row, label=f"terminal predecessor[{index}]")
        for index, row in enumerate(_sequence(
            predecessor_identities, label="terminal predecessors"
        ))
    ]
    nomination = _optional_identity(
        nomination_identity, label="publisher nomination"
    )
    prior_nomination = _optional_identity(
        prior_nomination_identity, label="prior nomination"
    )
    prior_aggregate = _optional_identity(
        prior_aggregate_identity, label="prior aggregate"
    )
    prior_finalist = _optional_identity(
        prior_finalist_identity, label="prior finalist"
    )
    prior_root = _optional_identity(prior_root_identity, label="prior root")
    if retained_mode == "publish-nomination":
        valid_lattice = (
            len(broad) == contract.PANEL_SLATE_COUNT
            and nomination is None and not confirmation and not predecessors
            and prior_aggregate is None and prior_finalist is None
            and prior_root is None
        )
    elif retained_mode == "publish-aggregate-finalists":
        valid_lattice = (
            len(broad) == contract.PANEL_SLATE_COUNT and nomination is not None
            and len(confirmation) == contract.PANEL_SLATE_COUNT
            and not predecessors and prior_nomination is None
            and prior_root is None
        )
    else:
        valid_lattice = (
            not broad and nomination is None and not confirmation
            and len(predecessors) == contract.OUTPUT_OBJECT_COUNT - 1
            and prior_nomination is None and prior_aggregate is None
            and prior_finalist is None
        )
    if not valid_lattice:
        _fail("publisher request lattice differs")
    body = {
        "schema_version": PUBLISHER_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "mode": retained_mode,
        "process_role": role_by_mode[retained_mode],
        "process_ordinal": 0,
        "design_identity": _identity(
            design_identity, label="publisher design"
        ),
        "topology_identity": _identity(
            topology_identity, label="publisher topology"
        ),
        "bootstrap_manifest_identity": _identity(
            bootstrap_manifest_identity, label="publisher bootstrap"
        ),
        "launch_intent_identity": _identity(
            launch_intent_identity, label="publisher launch intent"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="publisher process budget"
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


def _validate_publisher_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="publisher request")
    fields = {
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
    if set(item) != fields:
        _fail("publisher request fields differ")
    _self_hash(item, field="publisher_request_sha256", label="publisher request")
    expected = build_publisher_task_request_v1(
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
    if _canonical_bytes(item) != _canonical_bytes(expected):
        _fail("publisher request canonical replay differs")
    return expected


def _source_and_process(layer: _LayerSpec, request: Mapping[str, object], task_index: int) -> tuple[int | None, int]:
    if layer.task_count == contract.PANEL_SLATE_COUNT:
        source = _integer(request.get("source_ordinal"), label="request source ordinal")
        process = _integer(
            request.get("process_ordinal", source), label="request process ordinal"
        )
        if source != task_index or process != task_index:
            _fail("task index/source/process ordinal binding differs")
        return source, process
    process = _integer(request.get("process_ordinal"), label="request process ordinal")
    if task_index != 0 or process != 0:
        _fail("singular task process ordinal differs")
    return None, process


def _main_process_component(
    layer: _LayerSpec,
    process_specs: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    spec = _process_spec(layer.process_role, process_specs)
    chain = _sequence(spec["process_chain"], label="main process chain")
    if len(chain) != 1:
        _fail("externally dispatched process must have one main component")
    return _mapping(chain[0], label="main process component")


def render_child_command_v1(
    layer_id: str, request_value: object, *,
    _process_specs: Sequence[Mapping[str, object]] | None = None,
) -> list[str]:
    """Derive the child argv; no manifest or environment may supply a command."""
    layer = _layer(layer_id)
    request = _validate_request_for_layer(layer, request_value)
    command = list(_main_process_component(layer, _process_specs)["command"])
    if layer.request_kind != "projection":
        return [str(token) for token in command]
    command.extend(["--execute", "--project", FIXED_GCP_PROJECT])
    for prefix, identity_value in (
        ("design", request["design_identity"]),
        ("topology", request["topology_identity"]),
    ):
        identity = _identity(identity_value, label=f"projection {prefix}")
        command.extend([
            f"--{prefix}-uri", str(identity["uri"]),
            f"--{prefix}-generation", str(identity["generation"]),
            f"--{prefix}-sha256", str(identity["sha256"]),
            f"--{prefix}-bytes", str(identity["bytes"]),
        ])
    for identity_value in request["prior_projection_identities"]:
        if identity_value is not None:
            command.extend([
                "--resume-identity-json",
                _canonical_bytes(identity_value).decode("utf-8"),
            ])
    return [str(token) for token in command]


def _output_rows(
    *, layer: _LayerSpec, task_index: int, design: Mapping[str, object],
    request: Mapping[str, object],
) -> list[dict[str, object]]:
    topology_rows = [
        _mapping(row, label="topology output row")
        for row in design["topology"]["objects"]
        if row["role"] in layer.output_roles
    ]
    if layer.layer_id == "projection":
        selected = topology_rows
        priors = list(request["prior_projection_identities"])
    elif layer.task_count == contract.PANEL_SLATE_COUNT:
        role_rows = [row for row in topology_rows if row["role"] == layer.output_roles[0]]
        if len(role_rows) != contract.PANEL_SLATE_COUNT:
            _fail("topology layer output count differs")
        selected = [role_rows[task_index]]
        prior_field = (
            "prior_selection_receipt_identity"
            if layer.request_kind == "selection"
            else "prior_evaluation_identity"
        )
        priors = [request.get(prior_field)]
    else:
        selected = topology_rows
        if layer.layer_id == "nomination":
            priors = [request.get("prior_nomination_identity")]
        elif layer.layer_id == "aggregate-finalists":
            priors = [
                request.get("prior_aggregate_identity"),
                request.get("prior_finalist_identity"),
            ]
        else:
            priors = [request.get("prior_root_identity")]
    budgets = {
        str(row["uri"]): _mapping(row, label="design publication budget")
        for row in design["publication_budgets"]
    }
    if len(selected) != len(priors):
        _fail("task output/prior cardinality differs")
    outputs: list[dict[str, object]] = []
    role_offsets: dict[str, int] = {}
    for row, prior_value in zip(selected, priors, strict=True):
        uri = str(row["uri"])
        budget = budgets.get(uri)
        if budget is None or budget.get("create_once") is not True:
            _fail("task output is absent from create-once design budget")
        role = str(row["role"])
        source = role_offsets.get(role, 0)
        role_offsets[role] = source + 1
        if layer.task_count == contract.PANEL_SLATE_COUNT:
            source = task_index
        prior = _optional_identity(prior_value, label=f"prior {role} output")
        if prior is not None and prior["uri"] != uri:
            _fail("task prior output identity URI differs from its exact topology slot")
        outputs.append({
            "topology_ordinal": int(row["ordinal"]),
            "role": role,
            "source_ordinal": source if role in contract.LAYER_ROLES else None,
            "uri": uri,
            "maximum_bytes": int(budget["max_bytes"]),
            "create_once": True,
            "prior_identity": prior,
        })
    return outputs


def _task_science_binding_sha256_v1(task_value: Mapping[str, object]) -> str:
    return _canonical_sha({
        key: value for key, value in task_value.items()
        if key not in {
            "task_binding_sha256", "task_science_binding_sha256",
        }
    })


def _request_authority_gate(
    *, layer: _LayerSpec, request: Mapping[str, object],
    design_identity: Mapping[str, object], topology_identity: Mapping[str, object],
    bootstrap_identity: Mapping[str, object], authorization_identity: Mapping[str, object],
) -> None:
    if (
        request.get("design_identity") != design_identity
        or request.get("topology_identity") != topology_identity
    ):
        _fail("task request design/topology authority differs from manifest")
    if layer.request_kind in {"projection", "evaluation", "publisher"}:
        if request.get("bootstrap_manifest_identity") != bootstrap_identity:
            _fail("task request bootstrap authority differs from manifest")
    launch = request.get("launch_intent_identity")
    if layer.request_kind in {"evaluation", "publisher"} and launch != authorization_identity:
        _fail("task request launch authority differs from pre-design authorization")
    if layer.request_kind == "projection" and request.get(
        "pre_design_run_authorization_identity"
    ) != authorization_identity:
        _fail("projection request run authorization differs")
    if layer.request_kind in {"selection", "evaluation"} and request.get("phase") != layer.phase:
        _fail("task request phase differs from registered layer")
    if layer.request_kind == "publisher":
        if (
            request.get("process_role") != layer.process_role
            or request.get("mode") != layer.mode
        ):
            _fail("publisher request mode/role differs from registered layer")


def _receipt_publications(receipts: Sequence[Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    retained: dict[str, list[tuple[int, dict[str, object]]]] = {}
    for receipt in receipts:
        for record in receipt["task_records"]:
            for publication in record["publication_records"]:
                retained.setdefault(str(publication["role"]), []).append((
                    int(publication["topology_ordinal"]),
                    _identity(
                        publication["identity"], label="predecessor publication"
                    ),
                ))
    return {
        role: [identity for _ordinal, identity in sorted(rows)]
        for role, rows in retained.items()
    }


def _cross_layer_request_gate(
    *, layer: _LayerSpec, requests: Sequence[Mapping[str, object]],
    receipts: Sequence[Mapping[str, object]], design_identity: Mapping[str, object],
    topology: Mapping[str, object],
) -> None:
    outputs = _receipt_publications(receipts)
    projections = outputs.get("projection", [])
    if layer.layer_id != "projection" and len(projections) != contract.PANEL_SLATE_COUNT:
        _fail("predecessor projection lattice differs")
    for index, request in enumerate(requests):
        source = index if layer.task_count == contract.PANEL_SLATE_COUNT else None
        if source is not None and request.get("projection_bundle_identity") != projections[source]:
            _fail("task projection identity differs from completed projection layer")
        if layer.request_kind == "selection" and layer.phase == contract.CONFIRMATION_PHASE:
            nominations = outputs.get("nomination", [])
            if len(nominations) != 1 or request.get("nomination_identity") != nominations[0]:
                _fail("confirmation selection nomination authority differs")
        if layer.request_kind == "evaluation":
            receipt_role = (
                "broad-selection-receipt"
                if layer.phase == contract.BROAD_SCREEN_PHASE
                else "confirmation-selection-receipt"
            )
            selection = outputs.get(receipt_role, [])
            if len(selection) != contract.PANEL_SLATE_COUNT or request.get(
                "selection_receipt_identity"
            ) != selection[index]:
                _fail("evaluation selection authority differs from completed layer")
            if layer.phase == contract.CONFIRMATION_PHASE:
                nominations = outputs.get("nomination", [])
                if len(nominations) != 1 or request.get("nomination_identity") != nominations[0]:
                    _fail("confirmation evaluator nomination authority differs")
    if layer.layer_id == "nomination":
        if requests[0].get("broad_evaluation_identities") != outputs.get(
            "broad-evaluation-result", []
        ):
            _fail("nomination broad evaluation lattice differs")
    elif layer.layer_id == "aggregate-finalists":
        if (
            requests[0].get("broad_evaluation_identities")
            != outputs.get("broad-evaluation-result", [])
            or requests[0].get("confirmation_evaluation_identities")
            != outputs.get("confirmation-evaluation-result", [])
            or requests[0].get("nomination_identity")
            != (outputs.get("nomination", [None]) or [None])[0]
        ):
            _fail("aggregate/finalist predecessor lattice differs")
    elif layer.layer_id == "terminal-root":
        by_uri = {str(design_identity["uri"]): dict(design_identity)}
        for identities in outputs.values():
            by_uri.update({str(identity["uri"]): identity for identity in identities})
        expected = []
        for row in topology["objects"][:-1]:
            identity = by_uri.get(str(row["uri"]))
            if identity is None:
                _fail("terminal predecessor publication lattice is incomplete")
            expected.append(identity)
        if requests[0].get("predecessor_identities") != expected:
            _fail("terminal predecessor order differs")


def _validate_predecessor_receipt_record_v1(
    raw_record: object, *, expected_layer: str, output_prefix: str,
    expected_receipt_prefix: Sequence[Mapping[str, object]],
    design_identity: Mapping[str, object], design_sha256: str,
    topology_identity: Mapping[str, object], topology_sha256: str,
    bootstrap_identity: Mapping[str, object], bootstrap_sha256: str,
    authorization_identity: Mapping[str, object], authorization_sha256: str,
    code_commit: str, image_digest: str, reused_job_name: str,
    design: Mapping[str, object], topology: Mapping[str, object],
    bootstrap_manifest: Mapping[str, object],
    predecessor_receipts: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    record = _mapping(raw_record, label=f"predecessor {expected_layer} record")
    if set(record) != {
        "identity", "receipt", "manifest", "task_terminal_records",
        "projection_process_budget", "observation_source",
    }:
        _fail("predecessor receipt authority record fields differ")
    receipt = validate_layer_execution_receipt_v1(record["receipt"])
    receipt_identity = _bind_body(
        receipt, record["identity"], label=f"predecessor {expected_layer} receipt"
    )
    descriptor = _layer_descriptor(output_prefix, expected_layer)
    manifest = validate_task_manifest_v1(record["manifest"])
    manifest_identity = _bind_body(
        manifest, receipt["manifest_identity"],
        label=f"predecessor {expected_layer} manifest",
    )
    if (
        receipt_identity["uri"] != descriptor["layer_execution_receipt_uri"]
        or receipt_identity["bytes"] > MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES
        or manifest_identity["uri"] != descriptor["manifest_uri"]
        or manifest["layer_id"] != expected_layer
        or manifest["layer_ordinal"] != descriptor["layer_ordinal"]
        or manifest["predecessor_layer_receipts"]
        != list(expected_receipt_prefix)
        or receipt["predecessor_layer_receipts"]
        != list(expected_receipt_prefix)
        or receipt["manifest_identity"] != manifest_identity
        or receipt["task_manifest_sha256"] != manifest["task_manifest_sha256"]
        or receipt["design_identity"] != design_identity
        or receipt["design_sha256"] != design_sha256
        or receipt["topology_identity"] != topology_identity
        or receipt["topology_sha256"] != topology_sha256
        or receipt["bootstrap_manifest_identity"] != bootstrap_identity
        or receipt["bootstrap_manifest_sha256"] != bootstrap_sha256
        or receipt["pre_design_run_authorization_identity"]
        != authorization_identity
        or receipt["pre_design_run_authorization_sha256"]
        != authorization_sha256
        or receipt["code_commit"] != code_commit
        or receipt["image_digest"] != image_digest
        or receipt["reused_job_name"] != reused_job_name
        or any(
            receipt[field] != manifest[field]
            for field in (
                "design_identity", "design_sha256", "topology_identity",
                "topology_sha256", "bootstrap_manifest_identity",
                "bootstrap_manifest_sha256",
                "pre_design_run_authorization_identity",
                "pre_design_run_authorization_sha256", "code_commit",
                "image_digest", "reused_job_name", "phase", "process_role",
                "task_count",
            )
        )
    ):
        _fail("predecessor receipt URI/manifest/authority graph differs")
    observed = validate_observed_cloud_run_execution_authority_v1(
        receipt["observed_execution_authority"],
        manifest=manifest,
        manifest_identity=manifest_identity,
        observation_source=record["observation_source"],
        task_terminal_records=record["task_terminal_records"],
    )
    _bind_body(
        validate_cloud_run_execution_observation_source_v1(
            record["observation_source"],
            manifest=manifest,
            manifest_identity=manifest_identity,
            task_terminal_records=record["task_terminal_records"],
        ),
        observed["observation_source_identity"],
        label=f"predecessor {expected_layer} observation source",
    )
    if (
        receipt["recovery_allowed"] is not False
        or receipt["layer_resume_authority_identity"] is not None
    ):
        _fail("pre-output predecessor receipt binds forbidden recovery authority")
    predecessor_layer = _layer(expected_layer)
    if predecessor_layer.layer_id == "projection":
        try:
            projection_budget = contract.validate_publisher_process_budget_v1(
                record["projection_process_budget"],
                design=design,
                design_publication_identity=design_identity,
                topology_identity=topology_identity,
                bootstrap_manifest=bootstrap_manifest,
                bootstrap_manifest_identity=bootstrap_identity,
                launch_intent_identity=authorization_identity,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(
                "predecessor projection process budget graph differs"
            ) from exc
        _bind_body(
            projection_budget,
            manifest["task_bindings"][0]["request"]["process_budget_identity"],
            label="predecessor projection process budget",
        )
    elif record["projection_process_budget"] is not None:
        _fail("non-projection predecessor carries a projection process budget")
    predecessor_requests = [
        _mapping(task["request"], label="predecessor task request")
        for task in manifest["task_bindings"]
    ]
    for index, task in enumerate(manifest["task_bindings"]):
        expected_outputs = _output_rows(
            layer=predecessor_layer,
            task_index=index,
            design=design,
            request=predecessor_requests[index],
        )
        if task["expected_outputs"] != expected_outputs:
            _fail("predecessor manifest output descriptors differ from current design")
    _cross_layer_request_gate(
        layer=predecessor_layer,
        requests=predecessor_requests,
        receipts=predecessor_receipts,
        design_identity=design_identity,
        topology=topology,
    )
    raw_terminals = _sequence(
        record["task_terminal_records"],
        label=f"predecessor {expected_layer} terminal records",
    )
    if len(raw_terminals) != int(manifest["task_count"]):
        _fail("predecessor terminal record count differs")
    for index, (raw_terminal, compact, state) in enumerate(zip(
        raw_terminals, receipt["task_records"], observed["terminal_states"],
        strict=True,
    )):
        evidence, evidence_identity = _validated_terminal_record_v1(
                raw_terminal,
                manifest=manifest,
                manifest_identity=manifest_identity,
                expected_task_index=index,
                label=f"predecessor terminal record[{index}]",
            )
        resumed = False
        expected_publications = [
            {
                "topology_ordinal": descriptor_row["topology_ordinal"],
                "role": descriptor_row["role"],
                "identity": publication,
            }
            for descriptor_row, publication in zip(
                manifest["task_bindings"][index]["expected_outputs"],
                evidence["publication_identities"], strict=True,
            )
        ]
        if (
            evidence_identity != compact["task_terminal_evidence_identity"]
            or manifest_identity
            != compact["task_terminal_evidence_manifest_identity"]
            or evidence["task_terminal_evidence_sha256"]
            != compact["task_terminal_evidence_sha256"]
            or evidence["task_binding_sha256"] != compact["task_binding_sha256"]
            or manifest["task_bindings"][index].get(
                "task_science_binding_sha256",
                _task_science_binding_sha256_v1(
                    manifest["task_bindings"][index]
                ),
            ) != compact["task_science_binding_sha256"]
            or compact["resumed_exact_same_manifest"] is not resumed
            or compact["terminal_evidence_generation_exact_reopen_proved"] is not True
            or expected_publications != compact["publication_records"]
            or compact["publication_records_sha256"]
            != _canonical_sha(expected_publications)
            or evidence["publication_evidence_sha256"]
            != compact["publication_evidence_sha256"]
            or evidence["task_completed"] is not True
            or (
                not resumed
                and evidence["cloud_execution_name"] != observed["execution_name"]
            )
            or state["task_terminal_evidence_sha256"]
            != evidence["task_terminal_evidence_sha256"]
        ):
            _fail("predecessor compact terminal identity ledger differs")
    return receipt, receipt_identity


def build_task_manifest_v1(
    *, layer_id: str, design: object, design_identity: object,
    topology: object, topology_identity: object, bootstrap_manifest: object,
    bootstrap_manifest_identity: object, pre_design_run_authorization: object,
    pre_design_run_authorization_identity: object, task_requests: object,
    predecessor_layer_receipts: object = (),
    projection_process_budget: object | None = None,
    _validated_predecessor_token: object | None = None,
    _validated_predecessor_receipts: object = (),
    _validated_receipt_bindings: object = (),
) -> dict[str, object]:
    """Build one immutable, complete, task-indexed layer manifest."""
    layer = _layer(layer_id)
    retained_topology = contract.validate_result_topology_v1(topology)
    topology_authority = _bind_body(retained_topology, topology_identity, label="task topology")
    bootstrap_authority = _identity(
        bootstrap_manifest_identity, label="task bootstrap manifest"
    )
    retained_bootstrap = contract.validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_authority,
        topology=retained_topology,
        topology_identity=topology_authority,
    )
    design_authority = _identity(design_identity, label="task design")
    retained_design = contract.validate_design_authority_v1(
        design, publication_identity=design_authority
    )
    authorization_authority = _identity(
        pre_design_run_authorization_identity, label="task pre-design authorization"
    )
    authorization = validate_pre_design_run_authorization_authority_v1(
        pre_design_run_authorization,
        publication_identity=authorization_authority,
        topology=retained_topology,
    )
    if (
        retained_design["topology"] != retained_topology
        or retained_design["topology_identity"] != topology_authority
        or retained_design["bootstrap_manifest_identity"] != bootstrap_authority
        or retained_design["bootstrap_manifest"] != retained_bootstrap
        or retained_bootstrap.get("run_identity") != authorization_authority
        or retained_bootstrap.get("run_identity_semantics")
        != "pre-design-run-authorization-and-launch-intent-token"
        or retained_bootstrap.get("launch_intent_identity_must_equal_run_identity") is not True
        or retained_bootstrap.get("run_identity_is_cloud_execution_attestation") is not False
        or retained_bootstrap["code_commit"] != authorization["code_commit"]
        or retained_bootstrap["image_digest"] != authorization["image_digest"]
    ):
        _fail("design/topology/bootstrap/pre-design authority graph differs")
    process_specs_snapshot = canonical_bootstrap_process_specs_v1()
    descriptor_rows = layer_registry_v1(
        str(retained_topology["output_prefix"]),
        _process_specs=process_specs_snapshot,
    )
    descriptor = next(
        row for row in descriptor_rows if row["layer_id"] == layer.layer_id
    )
    registered = [row for row in authorization["layer_registry"] if row["layer_id"] == layer.layer_id]
    if registered != [descriptor]:
        _fail("pre-design layer authorization differs")
    required_specs = _required_process_specs(layer, process_specs_snapshot)
    for expected in required_specs:
        actual = contract.bootstrap_process_spec_v1(
            retained_bootstrap, process_role=str(expected["process_role"])
        )
        if actual != expected:
            _fail("bootstrap process spec differs from canonical layer command")

    retained_projection_budget: dict[str, object] | None = None
    if layer.layer_id == "projection":
        if projection_process_budget is None:
            _fail("projection manifest requires its exact publisher process budget")
        try:
            retained_projection_budget = contract.validate_publisher_process_budget_v1(
                projection_process_budget,
                design=retained_design,
                design_publication_identity=design_authority,
                topology_identity=topology_authority,
                bootstrap_manifest=retained_bootstrap,
                bootstrap_manifest_identity=bootstrap_authority,
                launch_intent_identity=authorization_authority,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(
                "projection publisher process budget authority differs"
            ) from exc
        if (
            retained_projection_budget.get("process_role") != "projection-publisher"
            or len(_canonical_bytes(retained_projection_budget))
            > MAXIMUM_PROCESS_BUDGET_BYTES
        ):
            _fail("projection publisher process budget precharge differs")
    elif projection_process_budget is not None:
        _fail("non-projection manifest cannot carry a projection process budget")

    raw_receipts = _sequence(
        predecessor_layer_receipts, label="predecessor layer receipts"
    )
    receipts: list[dict[str, object]] = []
    receipt_bindings: list[dict[str, object]] = []
    if _validated_predecessor_token is _VALIDATED_PREDECESSOR_TOKEN:
        if raw_receipts:
            _fail("internal compact predecessor replay cannot accept raw records")
        receipts = [
            validate_layer_execution_receipt_v1(row)
            for row in _sequence(
                _validated_predecessor_receipts,
                label="validated compact predecessor receipts",
            )
        ]
        receipt_bindings = [
            _mapping(row, label="validated compact predecessor binding")
            for row in _sequence(
                _validated_receipt_bindings,
                label="validated compact predecessor bindings",
            )
        ]
        if (
            len(receipts) != len(layer.predecessor_layers)
            or len(receipt_bindings) != len(layer.predecessor_layers)
            or any(
                receipt["layer_id"] != expected_layer
                or binding != {
                    "layer_id": expected_layer,
                    "receipt_identity": _identity(
                        binding.get("receipt_identity"),
                        label="validated predecessor receipt identity",
                    ),
                    "layer_execution_receipt_sha256": receipt[
                        "layer_execution_receipt_sha256"
                    ],
                }
                for expected_layer, receipt, binding in zip(
                    layer.predecessor_layers, receipts, receipt_bindings, strict=True
                )
            )
        ):
            _fail("validated compact predecessor ledger differs")
    else:
        if _validated_predecessor_token is not None:
            _fail("invalid internal compact predecessor replay token")
        if len(raw_receipts) != len(layer.predecessor_layers):
            _fail("predecessor layer receipt count differs from global barrier")
        for expected_layer, raw_record in zip(
            layer.predecessor_layers, raw_receipts, strict=True
        ):
            receipt, identity = _validate_predecessor_receipt_record_v1(
                raw_record,
                expected_layer=expected_layer,
                output_prefix=str(retained_topology["output_prefix"]),
                expected_receipt_prefix=receipt_bindings,
                design_identity=design_authority,
                design_sha256=str(retained_design["design_sha256"]),
                topology_identity=topology_authority,
                topology_sha256=str(retained_topology["topology_sha256"]),
                bootstrap_identity=bootstrap_authority,
                bootstrap_sha256=str(retained_bootstrap["bootstrap_manifest_sha256"]),
                authorization_identity=authorization_authority,
                authorization_sha256=str(
                    authorization["pre_design_run_authorization_sha256"]
                ),
                code_commit=str(authorization["code_commit"]),
                image_digest=str(authorization["image_digest"]),
                reused_job_name=str(authorization["reused_job_name"]),
                design=retained_design,
                topology=retained_topology,
                bootstrap_manifest=retained_bootstrap,
                predecessor_receipts=receipts,
            )
            receipts.append(receipt)
            receipt_bindings.append({
                "layer_id": expected_layer,
                "receipt_identity": identity,
                "layer_execution_receipt_sha256": receipt[
                    "layer_execution_receipt_sha256"
                ],
            })

    raw_requests = _sequence(task_requests, label="task requests")
    if len(raw_requests) != layer.task_count:
        _fail("task request count differs from registered layer")
    requests: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    for task_index, raw_request in enumerate(raw_requests):
        request = _validate_request_for_layer(layer, raw_request)
        request_raw = _canonical_bytes(request)
        if len(request_raw) > layer.request_byte_ceiling:
            _fail("task request exceeds registered byte ceiling")
        source, process = _source_and_process(layer, request, task_index)
        _request_authority_gate(
            layer=layer,
            request=request,
            design_identity=design_authority,
            topology_identity=topology_authority,
            bootstrap_identity=bootstrap_authority,
            authorization_identity=authorization_authority,
        )
        if retained_projection_budget is not None:
            _bind_body(
                retained_projection_budget,
                request.get("process_budget_identity"),
                label="projection publisher process budget",
            )
        outputs = _output_rows(
            layer=layer, task_index=task_index, design=retained_design,
            request=request,
        )
        child_command = render_child_command_v1(
            layer.layer_id, request, _process_specs=process_specs_snapshot
        )
        component = _main_process_component(layer, process_specs_snapshot)
        task_body = {
            "task_ordinal": task_index,
            "task_index": task_index,
            "source_ordinal": source,
            "process_ordinal": process,
            "phase": layer.phase,
            "process_role": layer.process_role,
            "request_schema": request["schema_version"],
            "request": request,
            "request_bytes": len(request_raw),
            "request_sha256": sha256(request_raw).hexdigest(),
            "expected_outputs": outputs,
            "expected_outputs_sha256": _canonical_sha(outputs),
            "child_command": child_command,
            "child_command_sha256": _canonical_sha({
                "command": child_command,
                "entrypoint_sha256": component["entrypoint_sha256"],
            }),
            "child_stdout_byte_ceiling": layer.child_stdout_byte_ceiling,
            "child_stderr_byte_ceiling": MAXIMUM_CHILD_STDERR_BYTES,
            "maximum_wall_seconds": layer.maximum_wall_seconds,
            "task_terminal_evidence_uri": (
                f"{retained_topology['output_prefix']}authorities/"
                f"task-terminal-evidence/{layer.layer_id}/task-{task_index:03d}.json"
            ),
        }
        if layer.request_kind == "evaluation":
            task_body["maximum_peak_rss_bytes"] = (
                _EVALUATOR_MAXIMUM_PEAK_RSS_BYTES
            )
        elif layer.request_kind == "publisher":
            task_body["maximum_peak_rss_bytes"] = (
                _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES
            )
        task_body["task_science_binding_sha256"] = (
            _task_science_binding_sha256_v1(task_body)
        )
        bindings.append(_with_hash(task_body, field="task_binding_sha256"))
        requests.append(request)
    _cross_layer_request_gate(
        layer=layer, requests=requests, receipts=receipts,
        design_identity=design_authority,
        topology=retained_topology,
    )
    dispatcher = authorization["dispatcher_process_spec"]
    host_terminal_resolution = (
        _host_terminal_generation_resolution_authority_v1(bindings)
    )
    body = {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "output_prefix": retained_topology["output_prefix"],
        "layer_ordinal": descriptor["layer_ordinal"],
        "layer_id": layer.layer_id,
        "phase": layer.phase,
        "process_role": layer.process_role,
        "mode": layer.mode,
        "task_count": layer.task_count,
        "manifest_uri": descriptor["manifest_uri"],
        "layer_execution_receipt_uri": descriptor["layer_execution_receipt_uri"],
        "design_identity": design_authority,
        "design_sha256": retained_design["design_sha256"],
        "topology_identity": topology_authority,
        "topology_sha256": retained_topology["topology_sha256"],
        "bootstrap_manifest_identity": bootstrap_authority,
        "bootstrap_manifest_sha256": retained_bootstrap["bootstrap_manifest_sha256"],
        "pre_design_run_authorization_identity": authorization_authority,
        "pre_design_run_authorization_sha256": authorization[
            "pre_design_run_authorization_sha256"
        ],
        "code_commit": authorization["code_commit"],
        "image_digest": authorization["image_digest"],
        "reused_job_name": authorization["reused_job_name"],
        "dispatcher_process_spec": dispatcher,
        "dispatcher_process_spec_sha256": authorization[
            "dispatcher_process_spec_sha256"
        ],
        "required_process_specs": required_specs,
        "required_process_specs_sha256": _canonical_sha(required_specs),
        "predecessor_layer_receipts": receipt_bindings,
        "predecessor_layer_receipts_sha256": _canonical_sha(receipt_bindings),
        "task_bindings": bindings,
        "task_bindings_sha256": _canonical_sha(bindings),
        "task_index_selects_exactly_one_request": True,
        "caller_manifest_request_or_command_accepted": False,
        "one_reused_job_across_layers": True,
        "per_task_deploy_allowed": False,
        "current_generation_resolution_allowed": False,
        "current_generation_resolution_policy_scope": (
            "scientific-and-task-input-authorities-only"
        ),
        "host_terminal_evidence_generation_resolution_authority": (
            host_terminal_resolution
        ),
        "host_terminal_evidence_generation_resolution_authority_sha256": (
            _canonical_sha(host_terminal_resolution)
        ),
        "listing_allowed": False,
        "uses_realized_outcomes": False,
        "graph_capability_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    retained = _with_hash(body, field="task_manifest_sha256")
    if len(_canonical_bytes(retained)) > MAXIMUM_MANIFEST_BYTES:
        _fail("task manifest exceeds its byte ceiling")
    return retained


def _validate_output_descriptor(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {
        "topology_ordinal", "role", "source_ordinal", "uri", "maximum_bytes",
        "create_once", "prior_identity",
    }:
        _fail(f"{label} fields differ")
    _integer(item.get("topology_ordinal"), label=f"{label} topology ordinal", maximum=contract.OUTPUT_OBJECT_COUNT)
    _string(item.get("role"), label=f"{label} role", maximum=64)
    if item.get("source_ordinal") is not None:
        _integer(item.get("source_ordinal"), label=f"{label} source ordinal", maximum=contract.PANEL_SLATE_COUNT - 1)
    uri = _string(item.get("uri"), label=f"{label} URI")
    if not uri.startswith(contract.OUTPUT_NAMESPACE) or item.get("create_once") is not True:
        _fail(f"{label} URI/create-once policy differs")
    _integer(item.get("maximum_bytes"), label=f"{label} byte ceiling", maximum=200_000_000_000)
    _optional_identity(item.get("prior_identity"), label=f"{label} prior identity")
    return item


def validate_task_manifest_v1(value: object) -> dict[str, object]:
    """Validate the closed manifest itself; authority validation reopens A0 bodies."""
    item = _mapping(value, label="task manifest")
    expected_fields = {
        "schema_version", "contract_id", "output_prefix", "layer_ordinal",
        "layer_id", "phase", "process_role", "mode", "task_count",
        "manifest_uri", "layer_execution_receipt_uri", "design_identity",
        "design_sha256", "topology_identity", "topology_sha256",
        "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
        "pre_design_run_authorization_identity",
        "pre_design_run_authorization_sha256", "code_commit", "image_digest",
        "reused_job_name", "dispatcher_process_spec",
        "dispatcher_process_spec_sha256", "required_process_specs",
        "required_process_specs_sha256", "predecessor_layer_receipts",
        "predecessor_layer_receipts_sha256", "task_bindings",
        "task_bindings_sha256", "task_index_selects_exactly_one_request",
        "caller_manifest_request_or_command_accepted",
        "one_reused_job_across_layers", "per_task_deploy_allowed",
        "current_generation_resolution_allowed",
        "current_generation_resolution_policy_scope",
        "host_terminal_evidence_generation_resolution_authority",
        "host_terminal_evidence_generation_resolution_authority_sha256",
        "listing_allowed",
        "uses_realized_outcomes", "graph_capability_allowed", "policy",
        "task_manifest_sha256",
    }
    if set(item) != expected_fields:
        _fail("task manifest fields differ")
    _self_hash(item, field="task_manifest_sha256", label="task manifest")
    if len(_canonical_bytes(item)) > MAXIMUM_MANIFEST_BYTES:
        _fail("task manifest exceeds its byte ceiling")
    layer = _layer(item.get("layer_id"))
    process_specs_snapshot = canonical_bootstrap_process_specs_v1()
    descriptor = next(
        row for row in layer_registry_v1(
            _string(item.get("output_prefix"), label="manifest output prefix"),
            _process_specs=process_specs_snapshot,
        )
        if row["layer_id"] == layer.layer_id
    )
    invariants = (
        item.get("schema_version") == TASK_MANIFEST_SCHEMA,
        item.get("contract_id") == contract.CONTRACT_ID,
        item.get("layer_ordinal") == descriptor["layer_ordinal"],
        item.get("phase") == layer.phase,
        item.get("process_role") == layer.process_role,
        item.get("mode") == layer.mode,
        item.get("task_count") == layer.task_count,
        item.get("manifest_uri") == descriptor["manifest_uri"],
        item.get("layer_execution_receipt_uri") == descriptor["layer_execution_receipt_uri"],
        item.get("dispatcher_process_spec") == canonical_dispatcher_process_spec_v1(),
        item.get("required_process_specs")
        == _required_process_specs(layer, process_specs_snapshot),
        item.get("task_index_selects_exactly_one_request") is True,
        item.get("caller_manifest_request_or_command_accepted") is False,
        item.get("one_reused_job_across_layers") is True,
        item.get("per_task_deploy_allowed") is False,
        item.get("current_generation_resolution_allowed") is False,
        item.get("current_generation_resolution_policy_scope")
        == "scientific-and-task-input-authorities-only",
        item.get("host_terminal_evidence_generation_resolution_authority")
        == _host_terminal_generation_resolution_authority_v1(
            item.get("task_bindings")
        ),
        item.get(
            "host_terminal_evidence_generation_resolution_authority_sha256"
        )
        == _canonical_sha(
            item.get("host_terminal_evidence_generation_resolution_authority")
        ),
        item.get("listing_allowed") is False,
        item.get("uses_realized_outcomes") is False,
        item.get("graph_capability_allowed") is False,
        item.get("policy") == contract.POLICY_CLAIMS,
    )
    if not all(invariants):
        _fail("task manifest fixed registry/policy binding differs")
    for field in (
        "design_sha256", "topology_sha256", "bootstrap_manifest_sha256",
        "pre_design_run_authorization_sha256", "dispatcher_process_spec_sha256",
        "required_process_specs_sha256", "predecessor_layer_receipts_sha256",
        "task_bindings_sha256",
        "host_terminal_evidence_generation_resolution_authority_sha256",
        "task_manifest_sha256",
    ):
        _sha(item.get(field), label=f"manifest {field}")
    design_identity = _identity(item.get("design_identity"), label="manifest design")
    topology_identity = _identity(item.get("topology_identity"), label="manifest topology")
    bootstrap_identity = _identity(item.get("bootstrap_manifest_identity"), label="manifest bootstrap")
    authorization_identity = _identity(item.get("pre_design_run_authorization_identity"), label="manifest run authorization")
    if (
        item["dispatcher_process_spec_sha256"] != _canonical_sha(item["dispatcher_process_spec"])
        or item["required_process_specs_sha256"] != _canonical_sha(item["required_process_specs"])
    ):
        _fail("manifest process-spec hashes differ")
    predecessors = _sequence(item.get("predecessor_layer_receipts"), label="manifest predecessor receipts")
    if len(predecessors) != len(layer.predecessor_layers):
        _fail("manifest predecessor barrier count differs")
    for expected_layer, raw in zip(layer.predecessor_layers, predecessors, strict=True):
        row = _mapping(raw, label="manifest predecessor receipt")
        if set(row) != {"layer_id", "receipt_identity", "layer_execution_receipt_sha256"} or row.get("layer_id") != expected_layer:
            _fail("manifest predecessor receipt order/fields differ")
        predecessor_identity = _identity(
            row.get("receipt_identity"), label="manifest predecessor receipt"
        )
        expected_receipt_uri = _layer_descriptor(
            str(item["output_prefix"]), expected_layer
        )["layer_execution_receipt_uri"]
        if (
            predecessor_identity["uri"] != expected_receipt_uri
            or predecessor_identity["bytes"]
            > MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES
        ):
            _fail("manifest predecessor receipt URI/byte ceiling differs")
        _sha(row.get("layer_execution_receipt_sha256"), label="manifest predecessor receipt hash")
    if item["predecessor_layer_receipts_sha256"] != _canonical_sha(predecessors):
        _fail("manifest predecessor receipt-set hash differs")
    bindings = _sequence(item.get("task_bindings"), label="manifest task bindings")
    if len(bindings) != layer.task_count:
        _fail("manifest task binding count differs")
    retained_bindings = []
    for index, raw in enumerate(bindings):
        task = _mapping(raw, label=f"task binding[{index}]")
        base_task_fields = {
            "task_ordinal", "task_index", "source_ordinal", "process_ordinal",
            "phase", "process_role", "request_schema", "request",
            "request_bytes", "request_sha256", "expected_outputs",
            "expected_outputs_sha256", "child_command",
            "child_command_sha256", "child_stdout_byte_ceiling",
            "child_stderr_byte_ceiling", "maximum_wall_seconds",
            "task_terminal_evidence_uri", "task_binding_sha256",
        }
        if layer.request_kind in {"evaluation", "publisher"}:
            base_task_fields.add("maximum_peak_rss_bytes")
        if set(task) != base_task_fields | {"task_science_binding_sha256"}:
            _fail("task binding fields differ")
        _self_hash(task, field="task_binding_sha256", label=f"task binding[{index}]")
        request = _validate_request_for_layer(layer, task.get("request"))
        request_raw = _canonical_bytes(request)
        source, process = _source_and_process(layer, request, index)
        _request_authority_gate(
            layer=layer, request=request, design_identity=design_identity,
            topology_identity=topology_identity, bootstrap_identity=bootstrap_identity,
            authorization_identity=authorization_identity,
        )
        outputs = [
            _validate_output_descriptor(value, label=f"task[{index}] output[{offset}]")
            for offset, value in enumerate(
                _sequence(task.get("expected_outputs"), label="task expected outputs")
            )
        ]
        command = render_child_command_v1(
            layer.layer_id, request, _process_specs=process_specs_snapshot
        )
        component = _main_process_component(layer, process_specs_snapshot)
        if (
            task.get("task_ordinal") != index
            or task.get("task_index") != index
            or task.get("source_ordinal") != source
            or task.get("process_ordinal") != process
            or task.get("phase") != layer.phase
            or task.get("process_role") != layer.process_role
            or task.get("request_schema") != request.get("schema_version")
            or task.get("request_bytes") != len(request_raw)
            or task.get("request_sha256") != sha256(request_raw).hexdigest()
            or task.get("expected_outputs_sha256") != _canonical_sha(outputs)
            or task.get("child_command") != command
            or task.get("child_command_sha256") != _canonical_sha({"command": command, "entrypoint_sha256": component["entrypoint_sha256"]})
            or task.get("child_stdout_byte_ceiling") != layer.child_stdout_byte_ceiling
            or task.get("child_stderr_byte_ceiling") != MAXIMUM_CHILD_STDERR_BYTES
            or task.get("maximum_wall_seconds") != layer.maximum_wall_seconds
            or (
                layer.request_kind == "evaluation"
                and task.get("maximum_peak_rss_bytes")
                != _EVALUATOR_MAXIMUM_PEAK_RSS_BYTES
            )
            or (
                layer.request_kind == "publisher"
                and task.get("maximum_peak_rss_bytes")
                != _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES
            )
            or task.get("task_terminal_evidence_uri")
            != f"{item['output_prefix']}authorities/task-terminal-evidence/{layer.layer_id}/task-{index:03d}.json"
            or task.get("task_science_binding_sha256")
            != _task_science_binding_sha256_v1(task)
        ):
            _fail("task binding canonical request/command/output binding differs")
        retained_bindings.append(task)
    if item["task_bindings_sha256"] != _canonical_sha(retained_bindings):
        _fail("manifest task binding-set hash differs")
    return item


def validate_task_manifest_authority_v1(
    value: object, *, publication_identity: object, design: object,
    topology: object, bootstrap_manifest: object,
    pre_design_run_authorization: object,
    predecessor_layer_receipts: object = (),
    projection_process_budget: object | None = None,
) -> dict[str, object]:
    item = validate_task_manifest_v1(value)
    identity = _bind_body(item, publication_identity, label="task manifest")
    if identity["uri"] != item["manifest_uri"]:
        _fail("task manifest publication URI differs")
    rebuilt = build_task_manifest_v1(
        layer_id=str(item["layer_id"]),
        design=design,
        design_identity=item["design_identity"],
        topology=topology,
        topology_identity=item["topology_identity"],
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=item["bootstrap_manifest_identity"],
        pre_design_run_authorization=pre_design_run_authorization,
        pre_design_run_authorization_identity=item[
            "pre_design_run_authorization_identity"
        ],
        task_requests=[row["request"] for row in item["task_bindings"]],
        predecessor_layer_receipts=predecessor_layer_receipts,
        projection_process_budget=projection_process_budget,
    )
    if _canonical_bytes(item) != _canonical_bytes(rebuilt):
        _fail("task manifest full authority replay differs")
    return rebuilt


def reopen_task_manifest_authority_v1(
    manifest_identity: object, *, read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open the manifest and every non-scientific authority it binds."""
    manifest_value, identity = _read_json_exact(
        manifest_identity, read_exact=read_exact, label="task manifest",
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    manifest = validate_task_manifest_v1(manifest_value)
    authorization, _ = _read_json_exact(
        manifest["pre_design_run_authorization_identity"],
        read_exact=read_exact,
        label="pre-design run authorization",
        maximum_bytes=MAXIMUM_AUTHORIZATION_BYTES,
    )
    topology, _ = _read_json_exact(
        manifest["topology_identity"], read_exact=read_exact,
        label="task topology",
        maximum_bytes=MAXIMUM_TOPOLOGY_BYTES,
    )
    bootstrap, _ = _read_json_exact(
        manifest["bootstrap_manifest_identity"], read_exact=read_exact,
        label="task bootstrap manifest",
        maximum_bytes=MAXIMUM_BOOTSTRAP_MANIFEST_BYTES,
    )
    design, _ = _read_json_exact(
        manifest["design_identity"], read_exact=read_exact, label="task design",
        maximum_bytes=MAXIMUM_DESIGN_BYTES,
    )
    projection_process_budget = None
    if manifest["layer_id"] == "projection":
        request = manifest["task_bindings"][0]["request"]
        projection_process_budget, _ = _read_json_exact(
            request["process_budget_identity"], read_exact=read_exact,
            label="projection publisher process budget",
            maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
        )
    retained_topology = contract.validate_result_topology_v1(topology)
    topology_authority = _bind_body(
        retained_topology, manifest["topology_identity"], label="task topology"
    )
    bootstrap_authority = _identity(
        manifest["bootstrap_manifest_identity"], label="task bootstrap manifest"
    )
    retained_bootstrap = contract.validate_bootstrap_manifest_authority_v1(
        bootstrap,
        publication_identity=bootstrap_authority,
        topology=retained_topology,
        topology_identity=topology_authority,
    )
    design_authority = _identity(manifest["design_identity"], label="task design")
    retained_design = contract.validate_design_authority_v1(
        design, publication_identity=design_authority
    )
    authorization_authority = _identity(
        manifest["pre_design_run_authorization_identity"],
        label="task pre-design authorization",
    )
    retained_authorization = validate_pre_design_run_authorization_authority_v1(
        authorization,
        publication_identity=authorization_authority,
        topology=retained_topology,
    )
    retained_receipts: list[dict[str, object]] = []
    receipt_bindings: list[dict[str, object]] = []
    for row in manifest["predecessor_layer_receipts"]:
        receipt, receipt_identity = _read_json_exact(
            row["receipt_identity"], read_exact=read_exact,
            label=f"predecessor {row['layer_id']} receipt",
            maximum_bytes=MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
        )
        retained_receipt = validate_layer_execution_receipt_v1(receipt)
        predecessor_manifest, predecessor_manifest_identity = _read_json_exact(
            retained_receipt["manifest_identity"], read_exact=read_exact,
            label=f"predecessor {row['layer_id']} manifest",
            maximum_bytes=MAXIMUM_MANIFEST_BYTES,
        )
        observation_source, _ = _read_json_exact(
            retained_receipt["observed_execution_authority"][
                "observation_source_identity"
            ],
            read_exact=read_exact,
            label=f"predecessor {row['layer_id']} observation source",
            maximum_bytes=MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES,
        )
        predecessor_projection_budget = None
        if retained_receipt["layer_id"] == "projection":
            budget_identity = predecessor_manifest["task_bindings"][0]["request"][
                "process_budget_identity"
            ]
            predecessor_projection_budget, _ = _read_json_exact(
                budget_identity, read_exact=read_exact,
                label="predecessor projection publisher process budget",
                maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
            )
        terminal_records = []
        for compact in retained_receipt["task_records"]:
            evidence_manifest_identity = _identity(
                compact["task_terminal_evidence_manifest_identity"],
                label=(
                    f"predecessor {row['layer_id']} task "
                    f"{compact['task_index']} evidence manifest"
                ),
            )
            if evidence_manifest_identity != predecessor_manifest_identity:
                _fail("predecessor terminal evidence manifest identity differs")
            evidence, evidence_identity = _read_json_exact(
                compact["task_terminal_evidence_identity"], read_exact=read_exact,
                label=(
                    f"predecessor {row['layer_id']} task "
                    f"{compact['task_index']} terminal evidence"
                ),
                maximum_bytes=MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES,
            )
            terminal_records.append({
                "identity": evidence_identity,
                "evidence": evidence,
            })
        predecessor_record = {
            "identity": receipt_identity,
            "receipt": retained_receipt,
            "manifest": predecessor_manifest,
            "task_terminal_records": terminal_records,
            "projection_process_budget": predecessor_projection_budget,
            "observation_source": observation_source,
        }
        validated_receipt, validated_identity = _validate_predecessor_receipt_record_v1(
            predecessor_record,
            expected_layer=str(row["layer_id"]),
            output_prefix=str(retained_topology["output_prefix"]),
            expected_receipt_prefix=receipt_bindings,
            design_identity=design_authority,
            design_sha256=str(retained_design["design_sha256"]),
            topology_identity=topology_authority,
            topology_sha256=str(retained_topology["topology_sha256"]),
            bootstrap_identity=bootstrap_authority,
            bootstrap_sha256=str(retained_bootstrap["bootstrap_manifest_sha256"]),
            authorization_identity=authorization_authority,
            authorization_sha256=str(
                retained_authorization["pre_design_run_authorization_sha256"]
            ),
            code_commit=str(retained_authorization["code_commit"]),
            image_digest=str(retained_authorization["image_digest"]),
            reused_job_name=str(retained_authorization["reused_job_name"]),
            design=retained_design,
            topology=retained_topology,
            bootstrap_manifest=retained_bootstrap,
            predecessor_receipts=retained_receipts,
        )
        retained_receipts.append(validated_receipt)
        receipt_bindings.append({
            "layer_id": str(row["layer_id"]),
            "receipt_identity": validated_identity,
            "layer_execution_receipt_sha256": validated_receipt[
                "layer_execution_receipt_sha256"
            ],
        })
        del (
            predecessor_record,
            predecessor_manifest,
            observation_source,
            terminal_records,
            predecessor_projection_budget,
        )
    retained = build_task_manifest_v1(
        layer_id=str(manifest["layer_id"]),
        design=retained_design,
        design_identity=design_authority,
        topology=retained_topology,
        topology_identity=topology_authority,
        bootstrap_manifest=retained_bootstrap,
        bootstrap_manifest_identity=bootstrap_authority,
        pre_design_run_authorization=retained_authorization,
        pre_design_run_authorization_identity=authorization_authority,
        task_requests=[row["request"] for row in manifest["task_bindings"]],
        predecessor_layer_receipts=(),
        projection_process_budget=projection_process_budget,
        _validated_predecessor_token=_VALIDATED_PREDECESSOR_TOKEN,
        _validated_predecessor_receipts=retained_receipts,
        _validated_receipt_bindings=receipt_bindings,
    )
    if _bind_body(retained, identity, label="task manifest")["uri"] != retained[
        "manifest_uri"
    ] or _canonical_bytes(retained) != _canonical_bytes(manifest):
        _fail("task manifest full authority replay differs")
    return {
        "manifest": retained,
        "manifest_identity": identity,
        "pre_design_run_authorization": authorization,
        "topology": topology,
        "bootstrap_manifest": bootstrap,
        "design": design,
        "projection_process_budget": projection_process_budget,
        "predecessor_layer_receipts": retained_receipts,
    }


def child_task_binding_environment_v1(
    manifest_value: object, *, manifest_identity: object, task_index: int,
) -> dict[str, str]:
    """Return the bounded scalar-only environment proof for one child task."""
    manifest = validate_task_manifest_v1(manifest_value)
    identity = _bind_body(manifest, manifest_identity, label="child task manifest")
    index = _integer(
        task_index, label="child task index", maximum=int(manifest["task_count"]) - 1
    )
    task = manifest["task_bindings"][index]
    raw_identity = _canonical_bytes(identity)
    if len(raw_identity) > MAXIMUM_IDENTITY_ENV_BYTES:
        _fail("child manifest identity environment value exceeds its ceiling")
    return {
        CHILD_MANIFEST_IDENTITY_ENV: raw_identity.decode("utf-8"),
        CHILD_MANIFEST_SELF_HASH_ENV: str(manifest["task_manifest_sha256"]),
        CHILD_TASK_BINDING_HASH_ENV: str(task["task_binding_sha256"]),
        CHILD_LAYER_ID_ENV: str(manifest["layer_id"]),
        CHILD_TASK_INDEX_ENV: str(index),
        CHILD_REQUEST_HASH_ENV: str(task["request_sha256"]),
        CHILD_OUTPUTS_HASH_ENV: str(task["expected_outputs_sha256"]),
        CHILD_COMMAND_HASH_ENV: str(task["child_command_sha256"]),
    }


def parse_child_task_binding_environment_v1(
    environ_value: Mapping[str, str],
) -> dict[str, object]:
    """Validate child binding scalars before construction of any cloud client."""
    environment = dict(environ_value)
    expected_keys = {
        CHILD_MANIFEST_IDENTITY_ENV,
        CHILD_MANIFEST_SELF_HASH_ENV,
        CHILD_TASK_BINDING_HASH_ENV,
        CHILD_LAYER_ID_ENV,
        CHILD_TASK_INDEX_ENV,
        CHILD_REQUEST_HASH_ENV,
        CHILD_OUTPUTS_HASH_ENV,
        CHILD_COMMAND_HASH_ENV,
    }
    supplied_binding_keys = {
        key for key, value in environment.items()
        if key.startswith("R6_TASK_") and value != ""
    }
    if supplied_binding_keys != expected_keys:
        _fail("child task binding environment fields differ")
    raw_identity_text = environment.get(CHILD_MANIFEST_IDENTITY_ENV, "")
    if (
        not isinstance(raw_identity_text, str)
        or not raw_identity_text
        or len(raw_identity_text.encode("utf-8")) > MAXIMUM_IDENTITY_ENV_BYTES
    ):
        _fail("child manifest identity environment value differs")
    identity_value = strict_json_v1(
        raw_identity_text.encode("utf-8"), label="child manifest identity environment"
    )
    identity = _identity(identity_value, label="child manifest identity environment")
    layer = _layer(environment.get(CHILD_LAYER_ID_ENV))
    index_text = environment.get(CHILD_TASK_INDEX_ENV, "")
    if not index_text.isdecimal() or len(index_text) > 6:
        _fail("child task index environment value differs")
    index = int(index_text)
    if index >= layer.task_count:
        _fail("child task index is outside the registered layer")
    for key in (
        CHILD_MANIFEST_SELF_HASH_ENV,
        CHILD_TASK_BINDING_HASH_ENV,
        CHILD_REQUEST_HASH_ENV,
        CHILD_OUTPUTS_HASH_ENV,
        CHILD_COMMAND_HASH_ENV,
    ):
        _sha(environment.get(key), label=f"child environment {key}")
    return {
        "manifest_identity": identity,
        "manifest_self_sha256": environment[CHILD_MANIFEST_SELF_HASH_ENV],
        "task_binding_sha256": environment[CHILD_TASK_BINDING_HASH_ENV],
        "layer_id": layer.layer_id,
        "task_index": index,
        "request_sha256": environment[CHILD_REQUEST_HASH_ENV],
        "expected_outputs_sha256": environment[CHILD_OUTPUTS_HASH_ENV],
        "child_command_sha256": environment[CHILD_COMMAND_HASH_ENV],
    }


def validate_child_task_binding_environment_v1(
    environ_value: Mapping[str, str],
) -> dict[str, object]:
    """Compatibility spelling for the strict child environment parser."""
    return parse_child_task_binding_environment_v1(environ_value)


def _observed_command(value: object) -> list[str]:
    return [
        _string(token, label=f"observed child command[{index}]", maximum=4_096)
        for index, token in enumerate(
            _sequence(value, label="observed child command")
        )
    ]


def validate_child_task_binding_v1(
    manifest_value: object, *, manifest_identity: object,
    environ: Mapping[str, str], raw_request: bytes, observed_command: object,
    expected_process_role: str | None = None, expected_phase: str | None = None,
    expected_source_ordinal: int | None = None,
    expected_process_ordinal: int | None = None,
) -> dict[str, object]:
    """Bind child request bytes and argv to exactly one selected manifest task."""
    manifest = validate_task_manifest_v1(manifest_value)
    identity = _bind_body(manifest, manifest_identity, label="child task manifest")
    parsed = parse_child_task_binding_environment_v1(environ)
    if (
        parsed["manifest_identity"] != identity
        or parsed["manifest_self_sha256"] != manifest["task_manifest_sha256"]
        or parsed["layer_id"] != manifest["layer_id"]
    ):
        _fail("child environment manifest authority differs")
    index = int(parsed["task_index"])
    if index >= int(manifest["task_count"]):
        _fail("child task index differs from manifest task count")
    task = manifest["task_bindings"][index]
    request_bytes = _canonical_bytes(task["request"])
    if type(raw_request) is not bytes or raw_request != request_bytes:
        _fail("child request bytes differ from selected manifest task")
    command = _observed_command(observed_command)
    if (
        command != task["child_command"]
        or parsed["task_binding_sha256"] != task["task_binding_sha256"]
        or parsed["request_sha256"] != task["request_sha256"]
        or parsed["expected_outputs_sha256"] != task["expected_outputs_sha256"]
        or parsed["child_command_sha256"] != task["child_command_sha256"]
    ):
        _fail("child environment request/command/output task binding differs")
    expected_values = (
        (expected_process_role, task["process_role"], "process role"),
        (expected_phase, task["phase"], "phase"),
        (expected_source_ordinal, task["source_ordinal"], "source ordinal"),
        (expected_process_ordinal, task["process_ordinal"], "process ordinal"),
    )
    for expected, actual, label in expected_values:
        if expected is not None and expected != actual:
            _fail(f"child expected {label} differs from selected task")
    body = {
        "schema_version": CHILD_TASK_BINDING_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "phase": task["phase"],
        "process_role": task["process_role"],
        "task_index": index,
        "source_ordinal": task["source_ordinal"],
        "process_ordinal": task["process_ordinal"],
        "task_binding_sha256": task["task_binding_sha256"],
        "request_sha256": task["request_sha256"],
        "request_bytes": task["request_bytes"],
        "expected_outputs_sha256": task["expected_outputs_sha256"],
        "child_command_sha256": task["child_command_sha256"],
        "manifest_generation_exact_reopen_required": True,
        "caller_request_or_command_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="child_task_binding_evidence_sha256")


def validate_child_task_binding_evidence_v1(
    value: object, *, manifest: object, manifest_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="child task binding evidence")
    if set(item) != {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "phase", "process_role",
        "task_index", "source_ordinal", "process_ordinal",
        "task_binding_sha256", "request_sha256", "request_bytes",
        "expected_outputs_sha256", "child_command_sha256",
        "manifest_generation_exact_reopen_required",
        "caller_request_or_command_accepted", "policy",
        "child_task_binding_evidence_sha256",
    }:
        _fail("child task binding evidence fields differ")
    _self_hash(
        item,
        field="child_task_binding_evidence_sha256",
        label="child task binding evidence",
    )
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity, label="child evidence task manifest"
    )
    index = _integer(
        item.get("task_index"), label="child evidence task index",
        maximum=int(retained_manifest["task_count"]) - 1,
    )
    task = retained_manifest["task_bindings"][index]
    if (
        item.get("schema_version") != CHILD_TASK_BINDING_EVIDENCE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("manifest_identity") != identity
        or item.get("task_manifest_sha256")
        != retained_manifest["task_manifest_sha256"]
        or item.get("layer_id") != retained_manifest["layer_id"]
        or item.get("phase") != task["phase"]
        or item.get("process_role") != task["process_role"]
        or item.get("source_ordinal") != task["source_ordinal"]
        or item.get("process_ordinal") != task["process_ordinal"]
        or item.get("task_binding_sha256") != task["task_binding_sha256"]
        or item.get("request_sha256") != task["request_sha256"]
        or item.get("request_bytes") != task["request_bytes"]
        or item.get("expected_outputs_sha256")
        != task["expected_outputs_sha256"]
        or item.get("child_command_sha256") != task["child_command_sha256"]
        or item.get("manifest_generation_exact_reopen_required") is not True
        or item.get("caller_request_or_command_accepted") is not False
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("child task binding evidence authority differs")
    return item


def reopen_child_task_binding_v1(
    *, environ: Mapping[str, str], raw_request: bytes, observed_command: object,
    read_exact: ReadExact, expected_process_role: str | None = None,
    expected_phase: str | None = None,
    expected_source_ordinal: int | None = None,
    expected_process_ordinal: int | None = None,
) -> dict[str, object]:
    """Exact-reopen full authority and return compact child binding evidence."""
    parsed = parse_child_task_binding_environment_v1(environ)
    authority = reopen_task_manifest_authority_v1(
        parsed["manifest_identity"], read_exact=read_exact
    )
    return validate_child_task_binding_v1(
        authority["manifest"],
        manifest_identity=authority["manifest_identity"],
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        expected_process_role=expected_process_role,
        expected_phase=expected_phase,
        expected_source_ordinal=expected_source_ordinal,
        expected_process_ordinal=expected_process_ordinal,
    )


def _child_json(raw: bytes) -> dict[str, object]:
    if raw.endswith(b"\n") and not raw.endswith(b"\n\n"):
        raw = raw[:-1]
    return strict_json_v1(raw, label="child stdout envelope")


def _manifest_process_spec_v1(
    manifest: Mapping[str, object], *, process_role: str,
) -> dict[str, object]:
    rows = [
        _mapping(row, label=f"manifest {process_role} process spec")
        for row in _sequence(
            manifest.get("required_process_specs"),
            label="manifest required process specs",
        )
        if isinstance(row, Mapping) and row.get("process_role") == process_role
    ]
    if len(rows) != 1:
        _fail(f"manifest {process_role} process spec is absent or repeated")
    return rows[0]


def _process_chain_v1(
    manifest: Mapping[str, object], *, process_role: str,
) -> list[dict[str, object]]:
    spec = _manifest_process_spec_v1(manifest, process_role=process_role)
    return [
        _mapping(row, label=f"manifest {process_role} component[{index}]")
        for index, row in enumerate(_sequence(
            spec.get("process_chain"), label=f"manifest {process_role} process chain"
        ))
    ]


def _validate_contract_runtime_observation_transport_v1(
    value: object, *, manifest: Mapping[str, object],
    task: Mapping[str, object], expected_process_role: str,
    expected_process_budget_sha256: object, expected_execution_name: str,
) -> dict[str, object]:
    runtime = _mapping(value, label="child contract runtime observation")
    fields = {
        "schema_version", "contract_id", "process_role",
        "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
        "process_budget_identity", "process_budget_sha256",
        "launch_intent_identity", "observed_code_commit",
        "observed_image_digest", "observed_command",
        "observed_entrypoint_sha256", "cloud_job_name_observed",
        "cloud_execution_name_observed", "cloud_task_index_observed",
        "read_object_count_including_process_budget_authority",
        "read_byte_ceiling_including_process_budget_authority",
        "cloud_values_are_unattested_observations",
        "terminal_execution_attestation_required", "policy",
        "runtime_observation_sha256",
    }
    if set(runtime) != fields:
        _fail("child contract runtime observation fields differ")
    _self_hash(
        runtime, field="runtime_observation_sha256",
        label="child contract runtime observation",
    )
    chain = _process_chain_v1(manifest, process_role=expected_process_role)
    if len(chain) != 1:
        _fail("child contract runtime requires one canonical component")
    component = chain[0]
    command = [
        _string(token, label=f"child runtime command[{index}]", maximum=4_096)
        for index, token in enumerate(_sequence(
            runtime.get("observed_command"), label="child runtime command"
        ))
    ]
    request = _mapping(task.get("request"), label="child runtime task request")
    read_count = _integer(
        runtime.get("read_object_count_including_process_budget_authority"),
        label="child runtime read-object count", maximum=10_000,
    )
    read_bytes = _integer(
        runtime.get("read_byte_ceiling_including_process_budget_authority"),
        label="child runtime read-byte ceiling", maximum=200_000_000_000,
    )
    if (
        runtime.get("schema_version") != contract.RUNTIME_OBSERVATION_SCHEMA
        or runtime.get("contract_id") != contract.CONTRACT_ID
        or runtime.get("process_role") != expected_process_role
        or runtime.get("bootstrap_manifest_identity")
        != manifest["bootstrap_manifest_identity"]
        or runtime.get("bootstrap_manifest_sha256")
        != manifest["bootstrap_manifest_sha256"]
        or runtime.get("process_budget_identity")
        != request.get("process_budget_identity")
        or runtime.get("process_budget_sha256")
        != _sha(
            expected_process_budget_sha256,
            label="child runtime expected process-budget SHA-256",
        )
        or runtime.get("launch_intent_identity")
        != manifest["pre_design_run_authorization_identity"]
        or runtime.get("observed_code_commit") != manifest["code_commit"]
        or runtime.get("observed_image_digest") != manifest["image_digest"]
        or command != component.get("command")
        or runtime.get("observed_entrypoint_sha256")
        != component.get("entrypoint_sha256")
        or runtime.get("cloud_job_name_observed") != manifest["reused_job_name"]
        or runtime.get("cloud_task_index_observed") != task["task_index"]
        or runtime.get("cloud_execution_name_observed") != expected_execution_name
        or read_count < 1
        or read_bytes < int(request["process_budget_identity"]["bytes"])
        or runtime.get("cloud_values_are_unattested_observations") is not True
        or runtime.get("terminal_execution_attestation_required") is not True
        or runtime.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("child contract runtime observation authority differs")
    return runtime


def _validate_process_runtime_evidence_transport_v1(
    value: object, *, manifest: Mapping[str, object], component: Mapping[str, object],
    mode: str, process_ordinal: int, task_index: int,
    expected_execution_name: str,
) -> dict[str, object]:
    runtime = _mapping(value, label=f"{mode} runtime evidence")
    fields = {
        "schema_version", "contract_id", "project_id", "code_commit",
        "image_digest", "job_name", "execution_id", "task_index",
        "process_ordinal", "mode", "redirect_environment_present",
        "storage_endpoint", "evidence_strength",
        "outer_launch_authority_binding_required", "pid", "parent_pid",
        "python_executable", "python_version", "entrypoint_path",
        "entrypoint_sha256", "command", "command_sha256",
        "runtime_evidence_sha256",
    }
    if set(runtime) != fields:
        _fail(f"{mode} runtime evidence fields differ")
    _self_hash(
        runtime, field="runtime_evidence_sha256", label=f"{mode} runtime evidence"
    )
    command = component.get("command")
    if (
        runtime.get("schema_version")
        != "corpus-r6-current-bank-observed-process-runtime/v1"
        or runtime.get("contract_id") != contract.CONTRACT_ID
        or runtime.get("project_id") != FIXED_GCP_PROJECT
        or runtime.get("code_commit") != manifest["code_commit"]
        or runtime.get("image_digest") != manifest["image_digest"]
        or runtime.get("job_name") != manifest["reused_job_name"]
        or runtime.get("execution_id") != expected_execution_name
        or runtime.get("task_index") != task_index
        or runtime.get("process_ordinal") != process_ordinal
        or runtime.get("mode") != mode
        or runtime.get("redirect_environment_present") is not False
        or runtime.get("storage_endpoint") != FIXED_STORAGE_ENDPOINT
        or runtime.get("evidence_strength")
        != "process-environment-observation-only"
        or runtime.get("outer_launch_authority_binding_required") is not True
        or runtime.get("command") != command
        or runtime.get("python_executable") != command[0]
        or runtime.get("entrypoint_path") != component.get("entrypoint_path")
        or runtime.get("entrypoint_sha256") != component.get("entrypoint_sha256")
        or runtime.get("command_sha256") != _canonical_sha({
            "command": command,
            "entrypoint_sha256": component.get("entrypoint_sha256"),
        })
    ):
        _fail(f"{mode} runtime evidence authority differs")
    for field in ("pid", "parent_pid"):
        _integer(runtime.get(field), label=f"{mode} runtime {field}")
    for field in ("execution_id", "python_version"):
        _string(runtime.get(field), label=f"{mode} runtime {field}", maximum=512)
    return runtime


def _validate_read_row_transport_v1(
    value: object, *, index: int, channel: str, role: str,
    identity: object | None = None, scientific_ordinal: int | None | object = ...,
) -> dict[str, object]:
    row = _mapping(value, label=f"child read ledger[{index}]")
    expected_fields = {"ordinal", "channel", "role", "identity"}
    if scientific_ordinal is not ...:
        expected_fields.add("scientific_ordinal")
    if (
        set(row) != expected_fields
        or row.get("ordinal") != index
        or row.get("channel") != channel
        or row.get("role") != role
    ):
        _fail("child read ledger fields/order differ")
    retained_identity = _identity(
        row.get("identity"), label=f"child read ledger[{index}] identity"
    )
    if identity is not None and retained_identity != identity:
        _fail("child read ledger identity differs from selected task")
    if scientific_ordinal is not ... and row.get("scientific_ordinal") != scientific_ordinal:
        _fail("child scientific read ordinal differs")
    return row


def _validate_selection_child_evidence_transport_v1(
    value: object, *, manifest: Mapping[str, object],
    task: Mapping[str, object], fold_ordinal: int, execution_name: str,
    process_budget_binding: Mapping[str, object],
) -> dict[str, object]:
    evidence = _mapping(value, label=f"selection child evidence[{fold_ordinal}]")
    fields = {
        "schema_version", "phase", "source_ordinal", "fold_ordinal",
        "heldout_block", "process_ordinal", "logical_fold_process_count",
        "os_process_count", "ordered_process_chain",
        "ordered_process_chain_sha256", "broker_command",
        "broker_entrypoint_sha256", "matrix_command",
        "matrix_entrypoint_sha256", "broker_runtime_evidence",
        "broker_runtime_evidence_sha256", "matrix_runtime_evidence",
        "matrix_runtime_evidence_sha256", "training_artifact_read_ledger",
        "training_artifact_read_ledger_sha256",
        "training_artifact_read_count", "bootstrap_manifest_identity",
        "bootstrap_manifest_sha256", "process_budget_identity",
        "launch_intent_identity", "fit_count", "matrix_capability_sha256",
        "matrix_response_sha256", "matrix_response_bytes",
        "child_output_bytes", "child_output_byte_ceiling",
        "selection_fold_receipt_sha256", "runtime_evidence_strength",
        "outer_launch_authority_binding_required",
        "outer_launch_authority_identity",
        "transport_capability_reached_matrix_process",
        "heldout_identity_reached_matrix_process",
        "child_execution_evidence_sha256",
    }
    if set(evidence) != fields:
        _fail("selection child execution evidence fields differ")
    _self_hash(
        evidence, field="child_execution_evidence_sha256",
        label="selection child execution evidence",
    )
    request = _mapping(task["request"], label="selection task request")
    fold_role = (
        "broad-fold-selector"
        if task["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-fold-selector"
    )
    process_chain = _process_chain_v1(manifest, process_role=fold_role)
    if len(process_chain) != 2:
        _fail("selection child process chain differs")
    process_ordinal = int(task["source_ordinal"]) * contract.FOLDS_PER_SLATE + fold_ordinal
    broker = _validate_process_runtime_evidence_transport_v1(
        evidence.get("broker_runtime_evidence"),
        manifest=manifest,
        component=process_chain[0],
        mode="fold-broker",
        process_ordinal=process_ordinal,
        task_index=int(task["task_index"]),
        expected_execution_name=execution_name,
    )
    matrix = _validate_process_runtime_evidence_transport_v1(
        evidence.get("matrix_runtime_evidence"),
        manifest=manifest,
        component=process_chain[1],
        mode="matrix-selector",
        process_ordinal=process_ordinal,
        task_index=int(task["task_index"]),
        expected_execution_name=execution_name,
    )
    heldout_block = contract.WORLD_BLOCKS[fold_ordinal]
    training_roles = [
        f"training-world-{block}"
        for block in contract.WORLD_BLOCKS if block != heldout_block
    ]
    training_rows = [
        _validate_read_row_transport_v1(
            row, index=index, channel="process-budget", role=role
        )
        for index, (row, role) in enumerate(zip(
            _sequence(
                evidence.get("training_artifact_read_ledger"),
                label="selection training artifact ledger",
            ),
            training_roles,
            strict=True,
        ))
    ]
    budget_binding = _mapping(
        process_budget_binding,
        label=f"selection worker budget binding[{fold_ordinal}]",
    )
    budget_training_rows = [
        row for row in budget_binding["read_allowlist"]
        if str(row["role"]).startswith("training-world-")
    ]
    response_bytes = _integer(
        evidence.get("matrix_response_bytes"),
        label="selection matrix response bytes",
        maximum=MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES,
    )
    output_bytes = _integer(
        evidence.get("child_output_bytes"),
        label="selection child output bytes",
        maximum=MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES,
    )
    output_ceiling = _integer(
        evidence.get("child_output_byte_ceiling"),
        label="selection child output byte ceiling",
        maximum=MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES,
    )
    fit_count = _integer(
        evidence.get("fit_count"), label="selection child fit count",
        maximum=10**12,
    )
    if (
        evidence.get("schema_version")
        != "corpus-r6-current-bank-child-execution-evidence/v1"
        or evidence.get("phase") != task["phase"]
        or evidence.get("source_ordinal") != task["source_ordinal"]
        or evidence.get("fold_ordinal") != fold_ordinal
        or evidence.get("heldout_block") != heldout_block
        or evidence.get("process_ordinal") != process_ordinal
        or evidence.get("logical_fold_process_count") != 1
        or evidence.get("os_process_count") != 2
        or evidence.get("ordered_process_chain") != process_chain
        or evidence.get("ordered_process_chain_sha256")
        != _canonical_sha(process_chain)
        or evidence.get("broker_command") != process_chain[0]["command"]
        or evidence.get("broker_entrypoint_sha256")
        != process_chain[0]["entrypoint_sha256"]
        or evidence.get("matrix_command") != process_chain[1]["command"]
        or evidence.get("matrix_entrypoint_sha256")
        != process_chain[1]["entrypoint_sha256"]
        or evidence.get("broker_runtime_evidence_sha256")
        != broker["runtime_evidence_sha256"]
        or evidence.get("matrix_runtime_evidence_sha256")
        != matrix["runtime_evidence_sha256"]
        or len(training_rows) != 4
        or evidence.get("training_artifact_read_count") != 4
        or evidence.get("training_artifact_read_ledger_sha256")
        != _canonical_sha(training_rows)
        or evidence.get("bootstrap_manifest_identity")
        != manifest["bootstrap_manifest_identity"]
        or evidence.get("bootstrap_manifest_sha256")
        != manifest["bootstrap_manifest_sha256"]
        or evidence.get("process_budget_identity")
        != request["worker_process_budget_identities"][fold_ordinal]
        or budget_binding.get("process_budget_identity")
        != request["worker_process_budget_identities"][fold_ordinal]
        or [
            {"role": row["role"], "identity": row["identity"]}
            for row in training_rows
        ] != budget_training_rows
        or [row["role"] for row in budget_training_rows] != training_roles
        or fit_count != budget_binding.get("compute_fit_precharge")
        or output_ceiling != budget_binding.get("child_output_byte_ceiling")
        or evidence.get("launch_intent_identity")
        != manifest["pre_design_run_authorization_identity"]
        or fit_count < 1
        or response_bytes < 1
        or output_bytes < 1
        or response_bytes > output_ceiling
        or output_bytes > output_ceiling
        or evidence.get("runtime_evidence_strength")
        != "process-environment-observation-only"
        or evidence.get("outer_launch_authority_binding_required") is not True
        or evidence.get("outer_launch_authority_identity")
        != manifest["pre_design_run_authorization_identity"]
        or evidence.get("transport_capability_reached_matrix_process") is not False
        or evidence.get("heldout_identity_reached_matrix_process") is not False
        or broker["execution_id"] != matrix["execution_id"]
    ):
        _fail("selection child execution evidence authority differs")
    for field in (
        "matrix_capability_sha256", "matrix_response_sha256",
        "selection_fold_receipt_sha256",
    ):
        _sha(evidence.get(field), label=f"selection child {field}")
    return evidence


def _exact_task_process_budget_bindings_v1(
    *, manifest: Mapping[str, object], task: Mapping[str, object],
    read_exact: ReadExact,
) -> list[dict[str, object]]:
    """Exact-open and retain only replay-critical process-budget metadata."""
    layer = _layer(manifest["layer_id"])
    request = _mapping(task["request"], label="task process-budget request")
    if layer.request_kind == "selection":
        identities = [
            request["assembler_process_budget_identity"],
            *_sequence(
                request["worker_process_budget_identities"],
                label="selection worker process-budget identities",
            ),
        ]
    else:
        identities = [request["process_budget_identity"]]
    bindings: list[dict[str, object]] = []
    for index, raw_identity in enumerate(identities):
        body, identity = _read_json_exact(
            raw_identity,
            read_exact=read_exact,
            label=f"task process budget[{index}]",
            maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
        )
        _bind_body(body, identity, label=f"task process budget[{index}]")
        schema = body.get("schema_version")
        if schema == contract.PROCESS_BUDGET_SCHEMA:
            hash_field = "process_budget_sha256"
        elif schema == contract.EVALUATOR_PROCESS_BUDGET_SCHEMA:
            hash_field = "evaluator_process_budget_sha256"
        elif schema == contract.PUBLISHER_PROCESS_BUDGET_SCHEMA:
            hash_field = "publisher_process_budget_sha256"
        else:
            _fail("task process budget schema differs")
        expected_schema = (
            contract.PROCESS_BUDGET_SCHEMA
            if layer.request_kind == "selection"
            else contract.EVALUATOR_PROCESS_BUDGET_SCHEMA
            if layer.request_kind == "evaluation"
            else contract.PUBLISHER_PROCESS_BUDGET_SCHEMA
        )
        if schema != expected_schema:
            _fail("task process budget schema differs from registered layer")
        _self_hash(body, field=hash_field, label=f"task process budget[{index}]")
        if schema == contract.PROCESS_BUDGET_SCHEMA:
            try:
                body = contract.validate_process_budget_v1(body)
            except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
                raise CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(
                    f"task process budget[{index}] canonical authority differs"
                ) from exc
        if body.get("process_role") != (
            (
                task["process_role"]
                if index == 0
                else (
                    "broad-fold-selector"
                    if task["phase"] == contract.BROAD_SCREEN_PHASE
                    else "confirmation-fold-selector"
                )
            )
        ):
            _fail("task process budget role differs")
        expected_process_ordinal = (
            int(task["process_ordinal"])
            if index == 0
            else int(task["source_ordinal"]) * contract.FOLDS_PER_SLATE + index - 1
        )
        if (
            body.get("contract_id") != contract.CONTRACT_ID
            or body.get("policy") != contract.POLICY_CLAIMS
            or body.get("process_ordinal") != expected_process_ordinal
        ):
            _fail("task process budget contract/process/policy differs")
        if layer.request_kind in {"selection", "evaluation"} and (
            body.get("phase") != task["phase"]
            or body.get("source_ordinal") != task["source_ordinal"]
        ):
            _fail("task process budget phase/source differs")
        if layer.request_kind == "selection" and index > 0 and (
            "fold_ordinal" in body
            or body.get("process_ordinal")
            != int(task["source_ordinal"]) * contract.FOLDS_PER_SLATE + index - 1
        ):
            _fail("selection worker process budget fold/process differs")
        reads = []
        for read_index, raw_row in enumerate(_sequence(
            body.get("read_allowlist"),
            label=f"task process budget[{index}] reads",
        )):
            row = _mapping(
                raw_row, label=f"task process budget[{index}] read[{read_index}]"
            )
            if set(row) != {"role", "identity"}:
                _fail("task process budget read fields differ")
            reads.append({
                "role": _string(
                    row.get("role"), label="task process budget read role",
                    maximum=128,
                ),
                "identity": _identity(
                    row.get("identity"), label="task process budget read identity"
                ),
            })
        writes = []
        for write_index, raw_row in enumerate(_sequence(
            body.get("write_allowlist"),
            label=f"task process budget[{index}] writes",
        )):
            row = _mapping(
                raw_row,
                label=f"task process budget[{index}] write[{write_index}]",
            )
            ordinal_field = (
                "ordinal" if schema == contract.PUBLISHER_PROCESS_BUDGET_SCHEMA
                else "source_ordinal"
            )
            if set(row) != {
                ordinal_field, "role", "uri", "max_bytes", "create_once",
            }:
                _fail("task process budget write fields differ")
            retained_write = {
                ordinal_field: _integer(
                    row.get(ordinal_field),
                    label="task process budget write ordinal",
                    maximum=contract.OUTPUT_OBJECT_COUNT,
                ),
                "role": _string(
                    row.get("role"), label="task process budget write role",
                    maximum=128,
                ),
                "uri": _string(
                    row.get("uri"), label="task process budget write URI",
                    maximum=2_048,
                ),
                "max_bytes": _integer(
                    row.get("max_bytes"),
                    label="task process budget write byte ceiling",
                    maximum=MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES,
                ),
                "create_once": row.get("create_once"),
            }
            if retained_write["create_once"] is not True:
                _fail("task process budget write is not create-once")
            writes.append(retained_write)
        read_count_field = (
            "read_object_count"
            if schema == contract.PROCESS_BUDGET_SCHEMA
            else "read_object_count_excluding_budget_authority"
        )
        read_bytes_field = (
            "read_byte_ceiling"
            if schema == contract.PROCESS_BUDGET_SCHEMA
            else "read_byte_ceiling_excluding_budget_authority"
        )
        read_bytes = sum(int(row["identity"]["bytes"]) for row in reads)
        write_bytes = sum(int(row["max_bytes"]) for row in writes)
        if (
            body.get(read_count_field) != len(reads)
            or body.get(read_bytes_field) != read_bytes
            or body.get("write_object_count") != len(writes)
            or body.get("write_byte_ceiling") != write_bytes
        ):
            _fail("task process budget count/byte precharge differs")
        false_policy_fields = {
            "current_generation_lookup_allowed",
            "environment_redirect_allowed",
            "git_ref_redirect_allowed",
        }
        if schema == contract.PROCESS_BUDGET_SCHEMA:
            false_policy_fields.add("endpoint_override_allowed")
        if any(body.get(field) is not False for field in false_policy_fields):
            _fail("task process budget redirect/current policy differs")
        if (
            schema in {
                contract.EVALUATOR_PROCESS_BUDGET_SCHEMA,
                contract.PUBLISHER_PROCESS_BUDGET_SCHEMA,
            }
            and body.get("process_budget_authority_added_at_runtime") is not True
        ):
            _fail("task process budget runtime-authority policy differs")
        bindings.append({
            "schema_version": schema,
            "process_budget_identity": identity,
            "process_budget_sha256": str(body[hash_field]),
            "read_allowlist": reads,
            "read_object_count_excluding_budget_authority": len(reads),
            "read_byte_ceiling_excluding_budget_authority": read_bytes,
            "write_allowlist": writes,
            "write_object_count": len(writes),
            "write_byte_ceiling": write_bytes,
            "compute_fit_precharge": _integer(
                body.get("compute_fit_precharge", 0),
                label="task process budget fit precharge",
                maximum=10**12,
            ),
            "child_output_byte_ceiling": _integer(
                body.get("child_output_byte_ceiling", 0),
                label="task process budget child output byte ceiling",
                maximum=MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES,
            ),
        })
    return bindings


def _validate_child_envelope_transport_v1(
    *, manifest: Mapping[str, object], task: Mapping[str, object], value: object,
    process_budget_bindings: Sequence[Mapping[str, object]],
    child_elapsed_milliseconds: int,
    cloud_execution_name: str,
) -> dict[str, object]:
    """Validate the complete transport envelope without importing A--D."""
    layer = _layer(manifest["layer_id"])
    budget_bindings = [
        _mapping(row, label=f"task process budget binding[{index}]")
        for index, row in enumerate(process_budget_bindings)
    ]
    process_budget_sha256s = [
        str(row["process_budget_sha256"]) for row in budget_bindings
    ]
    envelope = _mapping(value, label="child stdout envelope")
    common = {"schema_version", "contract_id", "policy", "task_binding_evidence"}
    if layer.request_kind == "projection":
        if len(process_budget_sha256s) != 1:
            _fail("projection exact process-budget hash ledger differs")
        projection_budget = budget_bindings[0]
        expected = common | {
            "design_identity", "topology_identity", "topology_sha256",
            "panel_identity", "panel_self_sha256", "structural_replay",
            "projection_count", "projection_identities",
            "projection_identities_sha256", "projection_layer",
            "planned_write_bytes", "planned_write_ceiling_bytes",
            "source_ordinal_order", "fold_order", "selector_executed",
            "world_artifact_read", "old_seven_arm_reconstruction_executed",
            "old_book_fields_copied", "input_listing_performed",
            "input_current_generation_resolution_performed",
            "projection_task_request_sha256",
            "process_budget_identity", "publisher_process_budget_sha256",
            "runtime_observation", "runtime_observation_sha256",
            "read_ledger", "read_ledger_sha256", "read_object_count",
            "write_ledger", "write_ledger_sha256", "write_object_count",
            "read_budget_exhausted", "write_budget_exhausted",
            "projection_execution_summary_sha256",
        }
        hash_field = "projection_execution_summary_sha256"
        values = [
            _identity(row, label=f"projection envelope identity[{index}]")
            for index, row in enumerate(_sequence(
                envelope.get("projection_identities"),
                label="projection envelope identities",
            ))
        ]
        runtime_observation = _mapping(
            envelope.get("runtime_observation"),
            label="projection runtime observation",
        )
        _self_hash(
            runtime_observation, field="runtime_observation_sha256",
            label="projection runtime observation",
        )
        reads = [
            _mapping(row, label=f"projection read ledger[{index}]")
            for index, row in enumerate(_sequence(
                envelope.get("read_ledger"), label="projection read ledger"
            ))
        ]
        writes = [
            _mapping(row, label=f"projection write ledger[{index}]")
            for index, row in enumerate(_sequence(
                envelope.get("write_ledger"), label="projection write ledger"
            ))
        ]
        runtime_observation = _validate_contract_runtime_observation_transport_v1(
            runtime_observation,
            manifest=manifest,
            task=task,
            expected_process_role="projection-publisher",
            expected_process_budget_sha256=process_budget_sha256s[0],
            expected_execution_name=cloud_execution_name,
        )
        structural_replay = _mapping(
            envelope.get("structural_replay"), label="projection structural replay"
        )
        if set(structural_replay) != {
            "structural_object_count", "underlying_exact_read_count",
            "structural_identities_sha256", "no_listing_api",
            "no_current_generation_input_read",
        }:
            _fail("projection structural replay fields differ")
        expected_read_roles = [
            "design", "topology",
            *[f"structural-{index:03d}" for index in range(111)],
        ]
        for index, (row, role) in enumerate(zip(
            reads, expected_read_roles, strict=True
        )):
            if (
                set(row) != {"ordinal", "role", "identity"}
                or row.get("ordinal") != index
                or row.get("role") != role
            ):
                _fail("projection read-ledger row fields/order differ")
            _identity(row.get("identity"), label=f"projection read[{index}] identity")
        read_identities = [
            _identity(row["identity"], label=f"projection read[{index}] identity")
            for index, row in enumerate(reads)
        ]
        budget_reads = list(projection_budget["read_allowlist"])
        if len(budget_reads) != 4 + 111:
            _fail("projection exact process-budget read lattice differs")
        expected_core_budget_reads = [*budget_reads[:2], *budget_reads[4:]]
        expected_core_read_identities = [
            row["identity"] for row in expected_core_budget_reads
        ]
        budget_writes = list(projection_budget["write_allowlist"])
        try:
            projection_layer = contract.validate_layer_binding_v1(
                envelope.get("projection_layer"), role="projection"
            )
            contract.validate_panel_identity_v1(
                envelope.get("panel_identity"),
                panel_self_sha256=envelope.get("panel_self_sha256"),
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenTaskManifestV1Error(
                "projection layer/panel transport authority differs"
            ) from exc
        outputs = task["expected_outputs"]
        for index, (row, output, publication) in enumerate(zip(
            writes, outputs, values, strict=True
        )):
            if (
                set(row) != {
                    "ordinal", "role", "uri", "maximum_bytes",
                    "publication_identity", "exact_generation_reopen_proved",
                }
                or row.get("ordinal") != output["topology_ordinal"]
                or row.get("role") != "projection"
                or row.get("uri") != output["uri"]
                or row.get("maximum_bytes") != output["maximum_bytes"]
                or row.get("publication_identity") != publication
                or row.get("exact_generation_reopen_proved") is not True
            ):
                _fail("projection write-ledger row/output binding differs")
        if (
            envelope.get("schema_version") != PROJECTION_EXECUTION_SUMMARY_SCHEMA
            or envelope.get("design_identity") != manifest["design_identity"]
            or envelope.get("topology_identity") != manifest["topology_identity"]
            or envelope.get("topology_sha256") != manifest["topology_sha256"]
            or read_identities[:2] != [
                task["request"]["design_identity"],
                task["request"]["topology_identity"],
            ]
            or read_identities != expected_core_read_identities
            or projection_budget.get("process_budget_identity")
            != task["request"].get("process_budget_identity")
            or read_identities[2] != envelope.get("panel_identity")
            or structural_replay != {
                "structural_object_count": 111,
                "underlying_exact_read_count": 111,
                "structural_identities_sha256": _canonical_sha(read_identities[2:]),
                "no_listing_api": True,
                "no_current_generation_input_read": True,
            }
            or envelope.get("projection_count") != contract.PANEL_SLATE_COUNT
            or len(values) != contract.PANEL_SLATE_COUNT
            or envelope.get("projection_identities_sha256") != _canonical_sha(values)
            or [row["source_ordinal"] for row in projection_layer["entries"]]
            != list(range(contract.PANEL_SLATE_COUNT))
            or [row["identity"] for row in projection_layer["entries"]] != values
            or envelope.get("planned_write_bytes")
            != sum(int(identity["bytes"]) for identity in values)
            or envelope.get("planned_write_ceiling_bytes")
            != sum(int(row["maximum_bytes"]) for row in task["expected_outputs"])
            or envelope.get("source_ordinal_order")
            != list(range(contract.PANEL_SLATE_COUNT))
            or envelope.get("fold_order") != list(contract.WORLD_BLOCKS)
            or envelope.get("projection_task_request_sha256")
            != task["request"].get("projection_task_request_sha256")
            or envelope.get("process_budget_identity")
            != task["request"].get("process_budget_identity")
            or envelope.get("publisher_process_budget_sha256")
            != process_budget_sha256s[0]
            or runtime_observation.get("process_role") != "projection-publisher"
            or runtime_observation.get("process_budget_identity")
            != task["request"].get("process_budget_identity")
            or runtime_observation.get("launch_intent_identity")
            != task["request"].get("pre_design_run_authorization_identity")
            or runtime_observation.get("bootstrap_manifest_identity")
            != task["request"].get("bootstrap_manifest_identity")
            or runtime_observation.get("cloud_task_index_observed") != 0
            or envelope.get("runtime_observation_sha256")
            != runtime_observation.get("runtime_observation_sha256")
            or len(reads) != 113
            or envelope.get("read_object_count") != 113
            or envelope.get("read_ledger_sha256") != _canonical_sha(reads)
            or runtime_observation.get(
                "read_object_count_including_process_budget_authority"
            ) != int(projection_budget[
                "read_object_count_excluding_budget_authority"
            ]) + 1
            or runtime_observation.get(
                "read_byte_ceiling_including_process_budget_authority"
            ) != int(projection_budget[
                "read_byte_ceiling_excluding_budget_authority"
            ]) + int(
                task["request"]["process_budget_identity"]["bytes"]
            )
            or len(writes) != contract.PANEL_SLATE_COUNT
            or budget_writes != [
                {
                    "ordinal": output["topology_ordinal"],
                    "role": output["role"],
                    "uri": output["uri"],
                    "max_bytes": output["maximum_bytes"],
                    "create_once": True,
                }
                for output in task["expected_outputs"]
            ]
            or projection_budget.get("write_object_count") != len(writes)
            or projection_budget.get("write_byte_ceiling")
            != sum(int(row["maximum_bytes"]) for row in task["expected_outputs"])
            or envelope.get("write_object_count") != contract.PANEL_SLATE_COUNT
            or envelope.get("write_ledger_sha256") != _canonical_sha(writes)
            or envelope.get("read_budget_exhausted") is not True
            or envelope.get("write_budget_exhausted") is not True
            or any(envelope.get(field) is not False for field in (
                "selector_executed", "world_artifact_read",
                "old_seven_arm_reconstruction_executed", "old_book_fields_copied",
                "input_listing_performed",
                "input_current_generation_resolution_performed",
            ))
        ):
            _fail("projection child envelope transport authority differs")
    elif layer.request_kind == "selection":
        if len(process_budget_sha256s) != 1 + contract.FOLDS_PER_SLATE:
            _fail("selection exact process-budget hash ledger differs")
        expected = common | {
            "phase", "source_ordinal", "assembler_request_sha256",
            "assembler_runtime_evidence", "assembler_runtime_evidence_sha256",
            "runtime_evidence_strength", "outer_launch_authority_binding_required",
            "outer_launch_authority_identity", "launch_intent_identity",
            "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
            "assembler_process_chain", "assembler_process_chain_sha256",
            "assembler_process_budget_identity", "assembler_process_budget_sha256",
            "child_envelope_sha256s", "child_envelopes_sha256",
            "child_execution_evidence", "child_execution_evidence_sha256s",
            "child_execution_evidence_set_sha256", "child_process_count",
            "logical_fold_process_count", "child_os_process_count",
            "phase_process_lattice_fragment", "child_fit_count",
            "assembler_read_ledger", "assembler_read_ledger_sha256",
            "assembler_world_artifact_body_read_count",
            "assembler_selection_algorithm_execution_count", "publication_count",
            "selection_receipt_identity", "selection_receipt_sha256",
            "prior_selection_receipt_identity",
            "selection_receipt_publication_resumed",
            "create_once_resume_exact_generation_proved",
            "assembler_envelope_sha256",
        }
        hash_field = "assembler_envelope_sha256"
        request = _mapping(task["request"], label="selection child task request")
        assembler_chain = _process_chain_v1(
            manifest, process_role=str(task["process_role"])
        )
        if len(assembler_chain) != 1:
            _fail("selection assembler process chain differs")
        assembler_runtime = _validate_process_runtime_evidence_transport_v1(
            envelope.get("assembler_runtime_evidence"),
            manifest=manifest,
            component=assembler_chain[0],
            mode="slate-assembler",
            process_ordinal=int(task["source_ordinal"]),
            task_index=int(task["task_index"]),
            expected_execution_name=cloud_execution_name,
        )
        child_envelope_hashes = [
            _sha(row, label=f"selection child envelope SHA-256[{index}]")
            for index, row in enumerate(_sequence(
                envelope.get("child_envelope_sha256s"),
                label="selection child envelope SHA-256s",
            ))
        ]
        child_evidence = [
            _validate_selection_child_evidence_transport_v1(
                row, manifest=manifest, task=task, fold_ordinal=index
                , execution_name=cloud_execution_name,
                process_budget_binding=budget_bindings[index + 1],
            )
            for index, row in enumerate(_sequence(
                envelope.get("child_execution_evidence"),
                label="selection child execution evidence",
            ))
        ]
        child_evidence_hashes = [
            row["child_execution_evidence_sha256"] for row in child_evidence
        ]
        expected_process_ordinals = [
            int(task["source_ordinal"]) * contract.FOLDS_PER_SLATE + fold
            for fold in range(contract.FOLDS_PER_SLATE)
        ]
        phase_lattice = _mapping(
            envelope.get("phase_process_lattice_fragment"),
            label="selection phase process lattice fragment",
        )
        expected_phase_lattice = {
            "phase": task["phase"],
            "source_ordinal": task["source_ordinal"],
            "logical_fold_process_count": contract.FOLDS_PER_SLATE,
            "os_process_count": 2 * contract.FOLDS_PER_SLATE,
            "ordered_process_chain": _process_chain_v1(
                manifest,
                process_role=(
                    "broad-fold-selector"
                    if task["phase"] == contract.BROAD_SCREEN_PHASE
                    else "confirmation-fold-selector"
                ),
            ),
            "fold_ordinals": list(range(contract.FOLDS_PER_SLATE)),
            "heldout_blocks": list(contract.WORLD_BLOCKS),
            "process_ordinals": expected_process_ordinals,
            "child_execution_evidence_sha256s": child_evidence_hashes,
        }
        selection_identity = _identity(
            envelope.get("selection_receipt_identity"),
            label="selection receipt publication identity",
        )
        raw_assembler_ledger = _sequence(
            envelope.get("assembler_read_ledger"),
            label="selection assembler read ledger",
        )
        expected_reads: list[tuple[str, str, object]] = [
            ("bootstrap-authority", "design", request["design_identity"]),
            ("bootstrap-authority", "topology", request["topology_identity"]),
            ("process-budget", "projection-bundle", request["projection_bundle_identity"]),
        ]
        if task["phase"] == contract.CONFIRMATION_PHASE:
            expected_reads.append(
                ("process-budget", "nomination", request["nomination_identity"])
            )
        expected_reads.extend([
            (
                "bootstrap-authority", "assembler-process-budget",
                request["assembler_process_budget_identity"],
            ),
            *[
                (
                    "bootstrap-authority", f"fold-{fold}-process-budget",
                    request["worker_process_budget_identities"][fold],
                )
                for fold in range(contract.FOLDS_PER_SLATE)
            ],
            (
                "bootstrap-authority", "published-selection-receipt",
                selection_identity,
            ),
        ])
        assembler_ledger = [
            _validate_read_row_transport_v1(
                row, index=index, channel=channel, role=role, identity=identity
            )
            for index, (row, (channel, role, identity)) in enumerate(zip(
                raw_assembler_ledger, expected_reads, strict=True
            ))
        ]
        assembler_budget = budget_bindings[0]
        assembler_budget_reads = assembler_budget["read_allowlist"]
        expected_assembler_budget_reads = [{
            "role": "projection-bundle",
            "identity": request["projection_bundle_identity"],
        }]
        if task["phase"] == contract.CONFIRMATION_PHASE:
            expected_assembler_budget_reads.append({
                "role": "nomination",
                "identity": request["nomination_identity"],
            })
        expected_assembler_budget_writes = [{
            "source_ordinal": task["source_ordinal"],
            "role": task["expected_outputs"][0]["role"],
            "uri": task["expected_outputs"][0]["uri"],
            "max_bytes": task["expected_outputs"][0]["maximum_bytes"],
            "create_once": True,
        }]
        if (
            envelope.get("schema_version") != SELECTION_ASSEMBLER_ENVELOPE_SCHEMA
            or envelope.get("phase") != task["phase"]
            or envelope.get("source_ordinal") != task["source_ordinal"]
            or envelope.get("assembler_request_sha256")
            != task["request"].get("assembler_request_sha256")
            or envelope.get("assembler_runtime_evidence_sha256")
            != assembler_runtime["runtime_evidence_sha256"]
            or envelope.get("runtime_evidence_strength")
            != "process-environment-observation-only"
            or envelope.get("outer_launch_authority_binding_required") is not True
            or envelope.get("outer_launch_authority_identity")
            != manifest["pre_design_run_authorization_identity"]
            or envelope.get("launch_intent_identity")
            != manifest["pre_design_run_authorization_identity"]
            or envelope.get("bootstrap_manifest_identity")
            != manifest["bootstrap_manifest_identity"]
            or envelope.get("bootstrap_manifest_sha256")
            != manifest["bootstrap_manifest_sha256"]
            or envelope.get("assembler_process_chain") != assembler_chain
            or envelope.get("assembler_process_chain_sha256")
            != _canonical_sha(assembler_chain)
            or envelope.get("assembler_process_budget_identity")
            != request["assembler_process_budget_identity"]
            or envelope.get("assembler_process_budget_sha256")
            != process_budget_sha256s[0]
            or assembler_budget.get("process_budget_identity")
            != request["assembler_process_budget_identity"]
            or assembler_budget_reads != expected_assembler_budget_reads
            or assembler_budget.get("read_object_count_excluding_budget_authority")
            != len(expected_assembler_budget_reads)
            or assembler_budget.get("write_allowlist")
            != expected_assembler_budget_writes
            or assembler_budget.get("write_object_count") != 1
            or assembler_budget.get("write_byte_ceiling")
            != task["expected_outputs"][0]["maximum_bytes"]
            or assembler_budget.get("compute_fit_precharge") != 0
            or assembler_budget.get("child_output_byte_ceiling") != 0
            or len(child_envelope_hashes) != contract.FOLDS_PER_SLATE
            or len(set(child_envelope_hashes)) != contract.FOLDS_PER_SLATE
            or envelope.get("child_envelopes_sha256")
            != _canonical_sha(child_envelope_hashes)
            or len(child_evidence) != contract.FOLDS_PER_SLATE
            or envelope.get("child_execution_evidence_sha256s")
            != child_evidence_hashes
            or envelope.get("child_execution_evidence_set_sha256")
            != _canonical_sha(child_evidence)
            or phase_lattice != expected_phase_lattice
            or envelope.get("child_fit_count")
            != sum(int(row["fit_count"]) for row in child_evidence)
            or len({
                (
                    row["broker_runtime_evidence"]["execution_id"],
                    row["broker_runtime_evidence"]["pid"],
                    row["matrix_runtime_evidence"]["pid"],
                )
                for row in child_evidence
            }) != contract.FOLDS_PER_SLATE
            or envelope.get("assembler_read_ledger_sha256")
            != _canonical_sha(assembler_ledger)
            or envelope.get("publication_count") != 1
            or envelope.get("child_process_count") != contract.FOLDS_PER_SLATE
            or envelope.get("logical_fold_process_count") != contract.FOLDS_PER_SLATE
            or envelope.get("child_os_process_count") != 2 * contract.FOLDS_PER_SLATE
            or envelope.get("assembler_world_artifact_body_read_count") != 0
            or envelope.get("assembler_selection_algorithm_execution_count") != 0
            or envelope.get("create_once_resume_exact_generation_proved") is not True
            or envelope.get("selection_receipt_publication_resumed")
            is not (task["expected_outputs"][0]["prior_identity"] is not None)
            or envelope.get("prior_selection_receipt_identity")
            != request["prior_selection_receipt_identity"]
            or selection_identity["uri"] != task["expected_outputs"][0]["uri"]
            or selection_identity["bytes"]
            > int(task["expected_outputs"][0]["maximum_bytes"])
        ):
            _fail("selection child envelope transport authority differs")
        _sha(
            envelope.get("selection_receipt_sha256"),
            label="selection receipt inner SHA-256",
        )
    elif layer.request_kind == "evaluation":
        if len(process_budget_sha256s) != 1:
            _fail("evaluator exact process-budget hash ledger differs")
        evaluator_budget = budget_bindings[0]
        expected = common | {
            "phase", "source_ordinal", "process_ordinal",
            "evaluator_request_sha256", "runtime_observation",
            "runtime_observation_sha256", "process_budget_identity",
            "process_budget_sha256", "read_ledger", "read_ledger_sha256",
            "read_object_count", "receipt_read_ordinal", "nomination_read_ordinal",
            "first_heldout_read_ordinal", "heldout_artifact_read_count",
            "fold_stream_consumption_order", "evaluation_result_sha256",
            "evaluation_publication_identity", "publication_bytes",
            "publication_byte_ceiling", "resource_precharge",
            "resource_precharge_sha256", "observed_elapsed_milliseconds",
            "observed_peak_rss_bytes", "selector_imported_or_callable",
            "caller_matrix_or_metric_input_accepted", "evaluator_envelope_sha256",
        }
        hash_field = "evaluator_envelope_sha256"
        request = _mapping(task["request"], label="evaluator child task request")
        runtime_observation = _validate_contract_runtime_observation_transport_v1(
            envelope.get("runtime_observation"),
            manifest=manifest,
            task=task,
            expected_process_role=str(task["process_role"]),
            expected_process_budget_sha256=process_budget_sha256s[0],
            expected_execution_name=cloud_execution_name,
        )
        raw_reads = _sequence(
            envelope.get("read_ledger"), label="evaluator read ledger"
        )
        expected_known_reads: list[tuple[str, str, object]] = [
            ("bootstrap-authority", "design", request["design_identity"]),
            ("bootstrap-authority", "topology", request["topology_identity"]),
            (
                "bootstrap-authority", "bootstrap-manifest",
                request["bootstrap_manifest_identity"],
            ),
            (
                "bootstrap-authority", "launch-intent",
                request["launch_intent_identity"],
            ),
            (
                "process-budget", "projection-bundle",
                request["projection_bundle_identity"],
            ),
            (
                "process-budget", "selection-receipt",
                request["selection_receipt_identity"],
            ),
        ]
        if task["phase"] == contract.CONFIRMATION_PHASE:
            expected_known_reads.append(
                ("process-budget", "nomination", request["nomination_identity"])
            )
        expected_known_reads.append((
            "bootstrap-authority", "process-budget",
            request["process_budget_identity"],
        ))
        known_count = len(expected_known_reads)
        scientific_roles = [
            "later-source",
            *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS],
        ]
        if len(raw_reads) != known_count + len(scientific_roles):
            _fail("evaluator read-ledger length differs")
        evaluator_reads = [
            _validate_read_row_transport_v1(
                raw_reads[index], index=index, channel=channel,
                role=role, identity=identity,
            )
            for index, (channel, role, identity) in enumerate(expected_known_reads)
        ]
        evaluator_reads.extend(
            _validate_read_row_transport_v1(
                raw_reads[known_count + offset],
                index=known_count + offset,
                channel="process-budget-scientific",
                role=role,
            )
            for offset, role in enumerate(scientific_roles)
        )
        read_identities = [
            _identity(row["identity"], label=f"evaluator read identity[{index}]")
            for index, row in enumerate(evaluator_reads)
        ]
        budget_reads = list(evaluator_budget["read_allowlist"])
        if len({str(row["role"]) for row in budget_reads}) != len(budget_reads):
            _fail("evaluator exact process-budget read roles repeat")
        budget_read_by_role = {
            str(row["role"]): row["identity"] for row in budget_reads
        }
        observed_budget_read_by_role = {
            str(row["role"]): row["identity"]
            for row in evaluator_reads if row["role"] != "process-budget"
        }
        if len({str(row["uri"]) for row in read_identities[known_count:]}) != 6:
            _fail("evaluator scientific read URI lattice repeats")
        publication = _identity(
            envelope.get("evaluation_publication_identity"),
            label="evaluator publication identity",
        )
        output = _mapping(task["expected_outputs"][0], label="evaluator output")
        resource_precharge = _mapping(
            envelope.get("resource_precharge"), label="evaluator resource precharge"
        )
        resource_fields = {
            "schema_version", "candidate_counts_by_fold",
            "score_matrix_bytes_by_fold",
            "candidate_world_additions_by_fold", "maximum_player_count",
            "maximum_source_candidate_rows", "maximum_evaluation_candidates",
            "maximum_later_source_bytes", "maximum_compressed_world_bytes",
            "maximum_player_draw_member_bytes", "maximum_score_matrix_bytes",
            "maximum_candidate_world_additions_per_fold",
            "maximum_wall_seconds", "maximum_peak_rss_bytes",
            "maximum_envelope_bytes", "resource_precharge_sha256",
        }
        if set(resource_precharge) != resource_fields:
            _fail("evaluator resource precharge fields differ")
        _self_hash(
            resource_precharge, field="resource_precharge_sha256",
            label="evaluator resource precharge",
        )
        candidate_counts = [
            _integer(row, label=f"evaluator candidate count[{index}]", maximum=10**9)
            for index, row in enumerate(_sequence(
                resource_precharge.get("candidate_counts_by_fold"),
                label="evaluator candidate counts",
            ))
        ]
        matrix_bytes = [
            _integer(row, label=f"evaluator matrix bytes[{index}]", maximum=10**12)
            for index, row in enumerate(_sequence(
                resource_precharge.get("score_matrix_bytes_by_fold"),
                label="evaluator matrix bytes",
            ))
        ]
        additions = [
            _integer(row, label=f"evaluator additions[{index}]", maximum=10**15)
            for index, row in enumerate(_sequence(
                resource_precharge.get("candidate_world_additions_by_fold"),
                label="evaluator candidate-world additions",
            ))
        ]
        maximum_candidates = _integer(
            resource_precharge.get("maximum_evaluation_candidates"),
            label="maximum evaluation candidates", maximum=10**9,
        )
        maximum_matrix_bytes = _integer(
            resource_precharge.get("maximum_score_matrix_bytes"),
            label="maximum evaluator matrix bytes", maximum=200_000_000_000,
        )
        maximum_additions = _integer(
            resource_precharge.get("maximum_candidate_world_additions_per_fold"),
            label="maximum candidate-world additions", maximum=10**15,
        )
        maximum_peak_rss = _integer(
            resource_precharge.get("maximum_peak_rss_bytes"),
            label="maximum evaluator RSS", maximum=200_000_000_000,
        )
        observed_elapsed = _integer(
            envelope.get("observed_elapsed_milliseconds"),
            label="observed evaluator elapsed milliseconds",
            maximum=int(task["maximum_wall_seconds"]) * 1_000,
        )
        observed_rss = _integer(
            envelope.get("observed_peak_rss_bytes"),
            label="observed evaluator peak RSS", maximum=200_000_000_000,
        )
        if (
            envelope.get("schema_version") != EVALUATOR_ENVELOPE_SCHEMA
            or envelope.get("phase") != task["phase"]
            or envelope.get("source_ordinal") != task["source_ordinal"]
            or envelope.get("process_ordinal") != task["process_ordinal"]
            or envelope.get("evaluator_request_sha256")
            != task["request"].get("evaluator_request_sha256")
            or envelope.get("runtime_observation_sha256")
            != runtime_observation["runtime_observation_sha256"]
            or envelope.get("process_budget_identity")
            != request["process_budget_identity"]
            or envelope.get("process_budget_sha256")
            != process_budget_sha256s[0]
            or evaluator_budget.get("process_budget_identity")
            != request["process_budget_identity"]
            or observed_budget_read_by_role != budget_read_by_role
            or envelope.get("read_object_count") != len(evaluator_reads)
            or envelope.get("read_ledger_sha256")
            != _canonical_sha(evaluator_reads)
            or runtime_observation.get(
                "read_object_count_including_process_budget_authority"
            ) != int(evaluator_budget[
                "read_object_count_excluding_budget_authority"
            ]) + 1
            or runtime_observation.get(
                "read_byte_ceiling_including_process_budget_authority"
            ) != int(evaluator_budget[
                "read_byte_ceiling_excluding_budget_authority"
            ]) + int(request["process_budget_identity"]["bytes"])
            or envelope.get("receipt_read_ordinal") != 5
            or envelope.get("nomination_read_ordinal")
            != (6 if task["phase"] == contract.CONFIRMATION_PHASE else None)
            or envelope.get("first_heldout_read_ordinal") != known_count + 1
            or envelope.get("heldout_artifact_read_count")
            != contract.FOLDS_PER_SLATE
            or envelope.get("fold_stream_consumption_order")
            != list(range(contract.FOLDS_PER_SLATE))
            or envelope.get("selector_imported_or_callable") is not False
            or envelope.get("caller_matrix_or_metric_input_accepted") is not False
            or publication["uri"] != output["uri"]
            or publication["bytes"] != envelope.get("publication_bytes")
            or envelope.get("publication_byte_ceiling") != output["maximum_bytes"]
            or publication["bytes"] > int(output["maximum_bytes"])
            or evaluator_budget.get("write_allowlist") != [{
                "source_ordinal": task["source_ordinal"],
                "role": output["role"],
                "uri": output["uri"],
                "max_bytes": output["maximum_bytes"],
                "create_once": True,
            }]
            or evaluator_budget.get("write_object_count") != 1
            or evaluator_budget.get("write_byte_ceiling")
            != output["maximum_bytes"]
            or evaluator_budget.get("compute_fit_precharge") != 0
            or envelope.get("resource_precharge_sha256")
            != resource_precharge["resource_precharge_sha256"]
            or len(candidate_counts) != contract.FOLDS_PER_SLATE
            or len(matrix_bytes) != contract.FOLDS_PER_SLATE
            or len(additions) != contract.FOLDS_PER_SLATE
            or any(
                not 1 <= count <= maximum_candidates
                for count in candidate_counts
            )
            or matrix_bytes != [
                count * contract.WORLDS_PER_BLOCK * 8
                for count in candidate_counts
            ]
            or additions != [
                count * contract.WORLDS_PER_BLOCK * 9
                for count in candidate_counts
            ]
            or resource_precharge.get("maximum_player_count")
            != _EVALUATOR_MAXIMUM_PLAYER_COUNT
            or resource_precharge.get("maximum_source_candidate_rows")
            != _EVALUATOR_MAXIMUM_SOURCE_CANDIDATE_ROWS
            or maximum_candidates != _EVALUATOR_MAXIMUM_EVALUATION_CANDIDATES
            or resource_precharge.get("maximum_later_source_bytes")
            != _EVALUATOR_MAXIMUM_LATER_SOURCE_BYTES
            or resource_precharge.get("maximum_compressed_world_bytes")
            != _EVALUATOR_MAXIMUM_COMPRESSED_WORLD_BYTES
            or resource_precharge.get("maximum_player_draw_member_bytes")
            != _EVALUATOR_MAXIMUM_PLAYER_DRAW_MEMBER_BYTES
            or maximum_matrix_bytes != _EVALUATOR_MAXIMUM_SCORE_MATRIX_BYTES
            or maximum_additions
            != _EVALUATOR_MAXIMUM_CANDIDATE_WORLD_ADDITIONS_PER_FOLD
            or resource_precharge.get("maximum_wall_seconds")
            != task["maximum_wall_seconds"]
            or maximum_peak_rss != task["maximum_peak_rss_bytes"]
            or resource_precharge.get("maximum_envelope_bytes")
            != task["child_stdout_byte_ceiling"]
            or int(read_identities[known_count]["bytes"])
            > int(resource_precharge["maximum_later_source_bytes"])
            or any(
                int(identity["bytes"])
                > int(resource_precharge["maximum_compressed_world_bytes"])
                for identity in read_identities[known_count + 1:]
            )
            or observed_elapsed > child_elapsed_milliseconds
            or observed_rss > task["maximum_peak_rss_bytes"]
        ):
            _fail("evaluator child envelope transport authority differs")
        _sha(
            envelope.get("evaluation_result_sha256"),
            label="evaluation result inner SHA-256",
        )
    else:
        if len(process_budget_sha256s) != 1:
            _fail("publisher exact process-budget hash ledger differs")
        publisher_budget = budget_bindings[0]
        expected = common | {
            "mode", "process_role", "process_ordinal", "publisher_request_sha256",
            "bootstrap_manifest_identity", "launch_intent_identity",
            "process_budget_identity", "process_budget_sha256",
            "runtime_observation", "runtime_observation_sha256", "read_ledger",
            "read_ledger_sha256", "read_object_count", "scientific_read_count",
            "write_precharge", "write_precharge_sha256",
            "all_writes_precharged_before_first_create", "publication_count",
            "publications", "publications_sha256",
            "terminal_predecessor_opener_call_count",
            "terminal_full_predecessor_body_list_materialized",
            "caller_scientific_bodies_accepted",
            "caller_grids_nominees_comparisons_bootstraps_accepted",
            "transport_semantics", "resource_precharge",
            "resource_precharge_sha256", "observed_elapsed_milliseconds",
            "observed_peak_rss_bytes",
            "maximum_retained_full_evaluation_body_count",
            "retained_compact_evaluation_record_count",
            "retained_compact_evaluation_state_bytes",
            "publisher_envelope_sha256",
        }
        hash_field = "publisher_envelope_sha256"
        request = _mapping(task["request"], label="publisher child task request")
        runtime_observation = _validate_contract_runtime_observation_transport_v1(
            envelope.get("runtime_observation"),
            manifest=manifest,
            task=task,
            expected_process_role=str(task["process_role"]),
            expected_process_budget_sha256=process_budget_sha256s[0],
            expected_execution_name=cloud_execution_name,
        )
        if layer.mode == "publish-nomination":
            scientific_identities = list(request["broad_evaluation_identities"])
            scientific_roles = [
                f"broad-evaluation-{source:02d}"
                for source in range(contract.PANEL_SLATE_COUNT)
            ]
        elif layer.mode == "publish-aggregate-finalists":
            scientific_identities = [
                *request["broad_evaluation_identities"],
                request["nomination_identity"],
                *request["confirmation_evaluation_identities"],
            ]
            scientific_roles = [
                *[
                    f"broad-evaluation-{source:02d}"
                    for source in range(contract.PANEL_SLATE_COUNT)
                ],
                "nomination",
                *[
                    f"confirmation-evaluation-{source:02d}"
                    for source in range(contract.PANEL_SLATE_COUNT)
                ],
            ]
        else:
            scientific_identities = list(request["predecessor_identities"])
            topology_rows = contract.build_result_topology_v1(
                str(manifest["output_prefix"])
            )["objects"][:-1]
            scientific_roles = [
                f"terminal-{int(row['ordinal']):03d}-{row['role']}"
                for row in topology_rows
            ]
        raw_publisher_reads = _sequence(
            envelope.get("read_ledger"), label="publisher read ledger"
        )
        expected_common_reads = [
            ("design", request["design_identity"]),
            ("topology", request["topology_identity"]),
            ("bootstrap-manifest", request["bootstrap_manifest_identity"]),
            ("launch-intent", request["launch_intent_identity"]),
            ("publisher-process-budget", request["process_budget_identity"]),
        ]
        if len(raw_publisher_reads) != len(expected_common_reads) + len(
            scientific_identities
        ):
            _fail("publisher read-ledger length differs")
        publisher_reads = [
            _validate_read_row_transport_v1(
                raw_publisher_reads[index], index=index,
                channel="publisher-authority", role=role, identity=identity,
                scientific_ordinal=None,
            )
            for index, (role, identity) in enumerate(expected_common_reads)
        ]
        publisher_reads.extend(
            _validate_read_row_transport_v1(
                raw_publisher_reads[len(expected_common_reads) + offset],
                index=len(expected_common_reads) + offset,
                channel="publisher-scientific", role=role, identity=identity,
                scientific_ordinal=offset,
            )
            for offset, (role, identity) in enumerate(zip(
                scientific_roles, scientific_identities, strict=True
            ))
        )
        exact_budget_reads = list(publisher_budget["read_allowlist"])
        if len(exact_budget_reads) != 4 + len(scientific_identities):
            _fail("publisher exact process-budget read lattice differs")
        if (
            [row["role"] for row in exact_budget_reads[:4]]
            != ["design", "topology", "bootstrap-manifest", "launch-intent"]
            or [row["identity"] for row in exact_budget_reads[:4]]
            != [identity for _, identity in expected_common_reads[:4]]
            or [row["role"] for row in exact_budget_reads[4:]]
            != [f"scientific-{index:03d}" for index in range(
                len(scientific_identities)
            )]
            or [row["identity"] for row in exact_budget_reads[4:]]
            != scientific_identities
        ):
            _fail("publisher exact process-budget read identities differ")
        write_precharge = [
            _mapping(row, label=f"publisher write precharge[{index}]")
            for index, row in enumerate(_sequence(
                envelope.get("write_precharge"),
                label="publisher write precharge",
            ))
        ]
        expected_write_precharge = [
            {
                "ordinal": output["topology_ordinal"],
                "role": output["role"],
                "uri": output["uri"],
                "max_bytes": output["maximum_bytes"],
                "create_once": True,
            }
            for output in task["expected_outputs"]
        ]
        publications = [
            _mapping(row, label=f"publisher publication[{index}]")
            for index, row in enumerate(_sequence(
                envelope.get("publications"), label="publisher publications"
            ))
        ]
        for index, row in enumerate(publications):
            if set(row) != {
                "publication_index", "ordinal", "role", "identity", "body_sha256",
                "publication_bytes", "publication_byte_ceiling",
            } or row.get("publication_index") != index:
                _fail("publisher publication row fields/order differ")
            publication = _identity(
                row.get("identity"), label=f"publisher publication[{index}] identity"
            )
            output = task["expected_outputs"][index]
            if (
                row.get("ordinal") != output["topology_ordinal"]
                or row.get("role") != output["role"]
                or publication["uri"] != output["uri"]
                or row.get("body_sha256") != publication["sha256"]
                or row.get("publication_bytes") != publication["bytes"]
                or row.get("publication_byte_ceiling") != output["maximum_bytes"]
                or publication["bytes"] > int(output["maximum_bytes"])
            ):
                _fail("publisher publication/output binding differs")
        transport_semantics = _mapping(
            envelope.get("transport_semantics"),
            label="publisher transport semantics",
        )
        expected_transport_semantics = {
            "fixed_project": FIXED_GCP_PROJECT,
            "fixed_endpoint": FIXED_STORAGE_ENDPOINT,
            "generation_exact_reads": True,
            "create_once_precondition_zero": True,
            "successful_create_exact_reopen_required": True,
            "collision_requires_supplied_exact_identity": True,
            "current_generation_resolution_allowed": False,
            "listing_allowed": False,
            "platform_retry_allowed": False,
        }
        resource_precharge = _mapping(
            envelope.get("resource_precharge"),
            label="publisher resource precharge",
        )
        resource_fields = {
            "schema_version", "mode", "scientific_read_count",
            "scientific_read_bytes", "evaluation_read_count",
            "evaluation_read_bytes", "maximum_single_scientific_body_bytes",
            "maximum_compact_evaluation_state_bytes", "maximum_wall_seconds",
            "maximum_peak_rss_bytes", "maximum_envelope_bytes",
            "maximum_retained_full_evaluation_body_count",
            "expected_compact_evaluation_record_count",
            "maximum_address_space_bytes",
            "required_cloud_run_container_memory_bytes",
            "baseline_rss_reserve_bytes", "single_body_raw_reserve_bytes",
            "single_body_decode_expansion_multiplier",
            "single_body_decode_expansion_reserve_bytes",
            "compact_state_expansion_multiplier",
            "compact_state_expansion_reserve_bytes",
            "derivation_output_reserve_bytes", "worst_case_rss_bytes",
            "resource_precharge_sha256",
        }
        if set(resource_precharge) != resource_fields:
            _fail("publisher resource precharge fields differ")
        _self_hash(
            resource_precharge, field="resource_precharge_sha256",
            label="publisher resource precharge",
        )
        evaluation_identities = [
            identity for role, identity in zip(
                scientific_roles, scientific_identities, strict=True
            )
            if "evaluation" in role
        ]
        expected_compact_count = (
            contract.PANEL_SLATE_COUNT
            if layer.mode == "publish-nomination"
            else 2 * contract.PANEL_SLATE_COUNT
        )
        observed_elapsed = _integer(
            envelope.get("observed_elapsed_milliseconds"),
            label="publisher observed elapsed milliseconds",
            maximum=int(task["maximum_wall_seconds"]) * 1_000,
        )
        observed_rss = _integer(
            envelope.get("observed_peak_rss_bytes"),
            label="publisher observed peak RSS",
            maximum=200_000_000_000,
        )
        retained_compact_bytes = _integer(
            envelope.get("retained_compact_evaluation_state_bytes"),
            label="publisher retained compact evaluation-state bytes",
            maximum=_PUBLISHER_MAXIMUM_COMPACT_EVALUATION_STATE_BYTES,
        )
        if (
            envelope.get("schema_version") != PUBLISHER_ENVELOPE_SCHEMA
            or envelope.get("mode") != layer.mode
            or envelope.get("process_role") != layer.process_role
            or envelope.get("process_ordinal") != 0
            or envelope.get("publisher_request_sha256")
            != task["request"].get("publisher_request_sha256")
            or envelope.get("bootstrap_manifest_identity")
            != manifest["bootstrap_manifest_identity"]
            or envelope.get("launch_intent_identity")
            != manifest["pre_design_run_authorization_identity"]
            or envelope.get("process_budget_identity")
            != request["process_budget_identity"]
            or envelope.get("process_budget_sha256")
            != process_budget_sha256s[0]
            or publisher_budget.get("process_budget_identity")
            != request["process_budget_identity"]
            or envelope.get("runtime_observation_sha256")
            != runtime_observation["runtime_observation_sha256"]
            or envelope.get("read_object_count") != len(publisher_reads)
            or envelope.get("scientific_read_count")
            != len(scientific_identities)
            or envelope.get("read_ledger_sha256")
            != _canonical_sha(publisher_reads)
            or runtime_observation.get(
                "read_object_count_including_process_budget_authority"
            ) != int(publisher_budget[
                "read_object_count_excluding_budget_authority"
            ]) + 1
            or runtime_observation.get(
                "read_byte_ceiling_including_process_budget_authority"
            ) != int(publisher_budget[
                "read_byte_ceiling_excluding_budget_authority"
            ]) + int(request["process_budget_identity"]["bytes"])
            or write_precharge != expected_write_precharge
            or publisher_budget.get("write_allowlist")
            != expected_write_precharge
            or publisher_budget.get("write_object_count")
            != len(expected_write_precharge)
            or publisher_budget.get("write_byte_ceiling")
            != sum(int(row["max_bytes"]) for row in expected_write_precharge)
            or envelope.get("write_precharge_sha256")
            != _canonical_sha(write_precharge)
            or envelope.get("publication_count") != len(publications)
            or len(publications) != len(task["expected_outputs"])
            or envelope.get("publications_sha256") != _canonical_sha(publications)
            or envelope.get("all_writes_precharged_before_first_create") is not True
            or envelope.get("terminal_full_predecessor_body_list_materialized") is not False
            or envelope.get("caller_scientific_bodies_accepted") is not False
            or envelope.get(
                "caller_grids_nominees_comparisons_bootstraps_accepted"
            ) is not False
            or envelope.get("terminal_predecessor_opener_call_count")
            != (
                contract.OUTPUT_OBJECT_COUNT - 1
                if layer.mode == "publish-terminal-root" else 0
            )
            or envelope.get("resource_precharge_sha256")
            != resource_precharge["resource_precharge_sha256"]
            or resource_precharge.get("schema_version")
            != "corpus-r6-current-bank-crossed-screen-publisher-resource-precharge/v1"
            or resource_precharge.get("mode") != layer.mode
            or resource_precharge.get("scientific_read_count")
            != len(scientific_identities)
            or resource_precharge.get("scientific_read_bytes")
            != sum(int(identity["bytes"]) for identity in scientific_identities)
            or resource_precharge.get("evaluation_read_count")
            != len(evaluation_identities)
            or resource_precharge.get("evaluation_read_bytes")
            != sum(int(identity["bytes"]) for identity in evaluation_identities)
            or resource_precharge.get("maximum_single_scientific_body_bytes")
            != _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
            or any(
                int(identity["bytes"])
                > _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
                for identity in scientific_identities
            )
            or resource_precharge.get("maximum_compact_evaluation_state_bytes")
            != _PUBLISHER_MAXIMUM_COMPACT_EVALUATION_STATE_BYTES
            or resource_precharge.get("maximum_wall_seconds")
            != task["maximum_wall_seconds"]
            or resource_precharge.get("maximum_peak_rss_bytes")
            != task["maximum_peak_rss_bytes"]
            or resource_precharge.get("maximum_address_space_bytes")
            != _PUBLISHER_MAXIMUM_PEAK_RSS_BYTES
            or resource_precharge.get("required_cloud_run_container_memory_bytes")
            != _PROVIDER_CONTAINER_MEMORY_BYTES
            or resource_precharge.get("baseline_rss_reserve_bytes")
            != _PUBLISHER_BASELINE_RSS_RESERVE_BYTES
            or resource_precharge.get("single_body_raw_reserve_bytes")
            != _PUBLISHER_MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
            or resource_precharge.get("single_body_decode_expansion_multiplier")
            != _PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_MULTIPLIER
            or resource_precharge.get("single_body_decode_expansion_reserve_bytes")
            != _PUBLISHER_SINGLE_BODY_DECODE_EXPANSION_RESERVE_BYTES
            or resource_precharge.get("compact_state_expansion_multiplier")
            != _PUBLISHER_COMPACT_STATE_EXPANSION_MULTIPLIER
            or resource_precharge.get("compact_state_expansion_reserve_bytes")
            != _PUBLISHER_COMPACT_STATE_EXPANSION_RESERVE_BYTES
            or resource_precharge.get("derivation_output_reserve_bytes")
            != _PUBLISHER_DERIVATION_OUTPUT_RESERVE_BYTES
            or resource_precharge.get("worst_case_rss_bytes")
            != _PUBLISHER_WORST_CASE_RSS_BYTES
            or resource_precharge.get("worst_case_rss_bytes")
            != sum((
                int(resource_precharge["baseline_rss_reserve_bytes"]),
                int(resource_precharge["single_body_raw_reserve_bytes"]),
                int(resource_precharge[
                    "single_body_decode_expansion_reserve_bytes"
                ]),
                int(resource_precharge[
                    "compact_state_expansion_reserve_bytes"
                ]),
                int(resource_precharge["derivation_output_reserve_bytes"]),
            ))
            or not (
                int(resource_precharge["worst_case_rss_bytes"])
                <= int(resource_precharge["maximum_peak_rss_bytes"])
                == int(resource_precharge["maximum_address_space_bytes"])
                < int(resource_precharge[
                    "required_cloud_run_container_memory_bytes"
                ])
            )
            or resource_precharge.get("maximum_envelope_bytes")
            != task["child_stdout_byte_ceiling"]
            or resource_precharge.get(
                "maximum_retained_full_evaluation_body_count"
            ) != 1
            or resource_precharge.get("expected_compact_evaluation_record_count")
            != expected_compact_count
            or envelope.get("maximum_retained_full_evaluation_body_count") != 1
            or envelope.get("retained_compact_evaluation_record_count")
            != expected_compact_count
            or not 2 <= retained_compact_bytes <= int(
                resource_precharge["maximum_compact_evaluation_state_bytes"]
            )
            or observed_elapsed > child_elapsed_milliseconds
            or observed_rss > task["maximum_peak_rss_bytes"]
            or transport_semantics != expected_transport_semantics
        ):
            _fail("publisher child envelope transport authority differs")
    if set(envelope) != expected:
        _fail("child stdout envelope fields differ from its registered role")
    if (
        envelope.get("contract_id") != contract.CONTRACT_ID
        or envelope.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("child stdout envelope contract/policy differs")
    _self_hash(envelope, field=hash_field, label="child stdout envelope")
    return envelope


def _publication_identities_from_child(
    *, manifest: Mapping[str, object], task: Mapping[str, object],
    envelope: Mapping[str, object],
) -> list[dict[str, object]]:
    layer = _layer(manifest["layer_id"])
    if layer.request_kind == "projection":
        values = envelope.get("projection_identities")
        if (
            envelope.get("design_identity") != manifest["design_identity"]
            or envelope.get("topology_identity") != manifest["topology_identity"]
        ):
            _fail("projection child authority differs from task manifest")
    elif layer.request_kind == "selection":
        values = [envelope.get("selection_receipt_identity")]
        if (
            envelope.get("assembler_request_sha256")
            != task["request"].get("assembler_request_sha256")
            or envelope.get("phase") != task["phase"]
            or envelope.get("source_ordinal") != task["source_ordinal"]
        ):
            _fail("selection child request/ordinal authority differs")
    elif layer.request_kind == "evaluation":
        values = [envelope.get("evaluation_publication_identity")]
        if (
            envelope.get("evaluator_request_sha256")
            != task["request"].get("evaluator_request_sha256")
            or envelope.get("phase") != task["phase"]
            or envelope.get("source_ordinal") != task["source_ordinal"]
        ):
            _fail("evaluation child request/ordinal authority differs")
    else:
        publications = _sequence(
            envelope.get("publications"), label="publisher child publications"
        )
        values = [
            _mapping(row, label="publisher child publication").get("identity")
            for row in publications
        ]
        if (
            envelope.get("publisher_request_sha256")
            != task["request"].get("publisher_request_sha256")
            or envelope.get("mode") != layer.mode
            or envelope.get("process_role") != layer.process_role
        ):
            _fail("publisher child request/mode authority differs")
    identities = [
        _identity(value, label=f"child publication identity[{index}]")
        for index, value in enumerate(
            _sequence(values, label="child publication identities")
        )
    ]
    outputs = task["expected_outputs"]
    if (
        len(identities) != len(outputs)
        or any(
            identity["uri"] != descriptor["uri"]
            or identity["bytes"] > descriptor["maximum_bytes"]
            or (
                descriptor["prior_identity"] is not None
                and identity != descriptor["prior_identity"]
            )
            for identity, descriptor in zip(identities, outputs, strict=True)
        )
    ):
        _fail("child publication identities differ from output ceiling/exact prior")
    return identities


def build_dispatcher_runtime_evidence_v1(
    *, manifest: object, manifest_identity: object, task_index: int,
    cloud_execution_name: str, kernel_observed_command: object,
    selected_environment: object,
) -> dict[str, object]:
    """Bind the dispatcher preclient kernel/runtime projection for one task."""
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity,
        label="dispatcher runtime evidence manifest",
    )
    index = _integer(
        task_index, label="dispatcher runtime task index",
        maximum=int(retained_manifest["task_count"]) - 1,
    )
    execution = _string(
        cloud_execution_name, label="dispatcher runtime execution", maximum=512
    )
    command = [
        _string(token, label=f"dispatcher kernel command[{offset}]", maximum=4_096)
        for offset, token in enumerate(_sequence(
            kernel_observed_command, label="dispatcher kernel command"
        ))
    ]
    environment = _mapping(
        selected_environment, label="dispatcher selected environment"
    )
    expected_environment = {
        "R6_CURRENT_BANK_TASK_DISPATCH_ENABLED": "1",
        DISPATCH_MANIFEST_IDENTITY_ENV: _canonical_bytes(identity).decode("utf-8"),
        DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: ABSENT_RESUME_AUTHORITY_ENV_VALUE,
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": retained_manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": retained_manifest["image_digest"],
        "CLOUD_RUN_JOB": retained_manifest["reused_job_name"],
        "CLOUD_RUN_EXECUTION": execution,
        "CLOUD_RUN_TASK_INDEX": str(index),
        "CLOUD_RUN_TASK_COUNT": str(retained_manifest["task_count"]),
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    if (
        command != retained_manifest["dispatcher_process_spec"]["command"]
        or environment != expected_environment
    ):
        _fail("dispatcher kernel command/environment differs from manifest runtime")
    body = {
        "schema_version": DISPATCHER_RUNTIME_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "layer_id": retained_manifest["layer_id"],
        "task_index": index,
        "task_count": retained_manifest["task_count"],
        "task_attempt": 0,
        "cloud_execution_name": execution,
        "kernel_observed_command": command,
        "kernel_observed_command_sha256": _canonical_sha(command),
        "selected_environment": environment,
        "selected_environment_sha256": _canonical_sha(environment),
        "preclient_validation_completed": True,
        "recovery_allowed": False,
    }
    return _with_hash(body, field="dispatcher_runtime_evidence_sha256")


def validate_dispatcher_runtime_evidence_v1(
    value: object, *, manifest: object, manifest_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="dispatcher runtime evidence")
    expected_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "task_index", "task_count",
        "task_attempt", "cloud_execution_name", "kernel_observed_command",
        "kernel_observed_command_sha256", "selected_environment",
        "selected_environment_sha256", "preclient_validation_completed",
        "recovery_allowed", "dispatcher_runtime_evidence_sha256",
    }
    if set(item) != expected_fields:
        _fail("dispatcher runtime evidence fields differ")
    _self_hash(
        item, field="dispatcher_runtime_evidence_sha256",
        label="dispatcher runtime evidence",
    )
    rebuilt = build_dispatcher_runtime_evidence_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        task_index=_integer(
            item.get("task_index"), label="dispatcher runtime task index"
        ),
        cloud_execution_name=_string(
            item.get("cloud_execution_name"),
            label="dispatcher runtime execution", maximum=512,
        ),
        kernel_observed_command=item.get("kernel_observed_command"),
        selected_environment=item.get("selected_environment"),
    )
    if _canonical_bytes(item) != _canonical_bytes(rebuilt):
        _fail("dispatcher runtime evidence canonical replay differs")
    return rebuilt


def build_task_terminal_evidence_v1(
    *, manifest: object, manifest_identity: object, task_index: int,
    cloud_execution_name: str, child_exit_code: int, child_stdout: bytes,
    child_stderr: bytes, elapsed_milliseconds: int,
    read_exact: ReadExact,
    prove_exact_identity: ProveExactIdentity,
    dispatcher_kernel_observed_command: object,
    dispatcher_selected_environment: object,
    timed_out: bool = False, stdout_overflow: bool = False,
    stderr_overflow: bool = False,
) -> dict[str, object]:
    """Reduce bounded child output to one body-free process terminal record."""
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity, label="terminal task manifest"
    )
    index = _integer(
        task_index, label="terminal task index",
        maximum=int(retained_manifest["task_count"]) - 1,
    )
    task = retained_manifest["task_bindings"][index]
    execution = _string(
        cloud_execution_name, label="cloud execution name", maximum=512
    )
    dispatcher_runtime_evidence = build_dispatcher_runtime_evidence_v1(
        manifest=retained_manifest,
        manifest_identity=identity,
        task_index=index,
        cloud_execution_name=execution,
        kernel_observed_command=dispatcher_kernel_observed_command,
        selected_environment=dispatcher_selected_environment,
    )
    exit_code = _integer(child_exit_code, label="child exit code", maximum=255)
    elapsed = _integer(
        elapsed_milliseconds, label="child elapsed milliseconds",
        maximum=int(task["maximum_wall_seconds"]) * 1_000 + 60_000,
    )
    if type(child_stdout) is not bytes or type(child_stderr) is not bytes:
        _fail("child terminal streams must be bytes")
    if len(child_stdout) > int(task["child_stdout_byte_ceiling"]):
        _fail("child stdout exceeds the selected task ceiling")
    if len(child_stderr) > int(task["child_stderr_byte_ceiling"]):
        _fail("child stderr exceeds the selected task ceiling")
    for value, label in (
        (timed_out, "timed-out flag"),
        (stdout_overflow, "stdout-overflow flag"),
        (stderr_overflow, "stderr-overflow flag"),
    ):
        if type(value) is not bool:
            _fail(f"child {label} must be boolean")
    completed = (
        exit_code == 0 and not timed_out and not stdout_overflow
        and not stderr_overflow
    )
    binding_evidence: dict[str, object] | None = None
    publications: list[dict[str, object]] = []
    envelope_sha: str | None = None
    envelope_schema: str | None = None
    if completed:
        process_budget_bindings = _exact_task_process_budget_bindings_v1(
            manifest=retained_manifest, task=task, read_exact=read_exact
        )
        envelope = _validate_child_envelope_transport_v1(
            manifest=retained_manifest, task=task,
            value=_child_json(child_stdout),
            process_budget_bindings=process_budget_bindings,
            child_elapsed_milliseconds=elapsed,
            cloud_execution_name=execution,
        )
        binding_evidence = validate_child_task_binding_evidence_v1(
            envelope.get("task_binding_evidence"),
            manifest=retained_manifest,
            manifest_identity=identity,
        )
        publications = _publication_identities_from_child(
            manifest=retained_manifest, task=task, envelope=envelope
        )
        for offset, publication in enumerate(publications):
            proved = _identity(
                prove_exact_identity(publication),
                label=f"child publication[{offset}] exact proof",
            )
            if proved != publication:
                _fail(
                    f"child publication[{offset}] exact-generation proof differs"
                )
        envelope_sha = sha256(child_stdout).hexdigest()
        envelope_schema = _string(
            envelope.get("schema_version"), label="child envelope schema", maximum=256
        )
    publication_evidence = []
    if completed:
        publication_evidence = [
            {
                "output_ordinal": offset,
                "descriptor_uri": descriptor["uri"],
                "descriptor_maximum_bytes": descriptor["maximum_bytes"],
                "publication_identity": publication,
                "publication_within_descriptor_ceiling": (
                    publication["bytes"] <= descriptor["maximum_bytes"]
                ),
                "prior_identity": descriptor["prior_identity"],
                "exact_prior_generation_matched": (
                    descriptor["prior_identity"] is None
                    or publication == descriptor["prior_identity"]
                ),
                "successful_create_or_exact_prior_reopen_required": True,
                "publication_generation_exact_reopen_proved": True,
                "accepted_from_canonical_child_envelope": True,
            }
            for offset, (descriptor, publication) in enumerate(zip(
                task["expected_outputs"], publications, strict=True
            ))
        ]
    body = {
        "schema_version": TASK_TERMINAL_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "layer_id": retained_manifest["layer_id"],
        "phase": task["phase"],
        "process_role": task["process_role"],
        "task_index": index,
        "source_ordinal": task["source_ordinal"],
        "process_ordinal": task["process_ordinal"],
        "task_binding_sha256": task["task_binding_sha256"],
        "task_science_binding_sha256": task.get(
            "task_science_binding_sha256",
            _task_science_binding_sha256_v1(task),
        ),
        "request_sha256": task["request_sha256"],
        "expected_outputs": task["expected_outputs"],
        "expected_outputs_sha256": task["expected_outputs_sha256"],
        "child_command_sha256": task["child_command_sha256"],
        "cloud_execution_name": execution,
        "dispatcher_runtime_evidence": dispatcher_runtime_evidence,
        "dispatcher_runtime_evidence_sha256": dispatcher_runtime_evidence[
            "dispatcher_runtime_evidence_sha256"
        ],
        "child_exit_code": exit_code,
        "elapsed_milliseconds": elapsed,
        "timed_out": timed_out,
        "stdout_overflow": stdout_overflow,
        "stderr_overflow": stderr_overflow,
        "child_stdout_bytes": len(child_stdout),
        "child_stdout_sha256": sha256(child_stdout).hexdigest(),
        "child_stdout_byte_ceiling": task["child_stdout_byte_ceiling"],
        "child_stderr_bytes": len(child_stderr),
        "child_stderr_sha256": sha256(child_stderr).hexdigest(),
        "child_stderr_byte_ceiling": task["child_stderr_byte_ceiling"],
        "child_envelope_schema": envelope_schema,
        "child_envelope_sha256": envelope_sha,
        "child_task_binding_evidence": binding_evidence,
        "publication_identities": publications,
        "publication_evidence": publication_evidence,
        "publication_evidence_sha256": _canonical_sha(publication_evidence),
        "task_completed": completed,
        "raw_child_streams_embedded": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    retained = _with_hash(body, field="task_terminal_evidence_sha256")
    if len(_canonical_bytes(retained)) > MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES:
        _fail("task terminal evidence exceeds its byte ceiling")
    return retained


def validate_task_terminal_evidence_v1(
    value: object, *, manifest: object, manifest_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="task terminal evidence")
    expected_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "phase", "process_role",
        "task_index", "source_ordinal", "process_ordinal",
        "task_binding_sha256", "task_science_binding_sha256", "request_sha256",
        "expected_outputs",
        "expected_outputs_sha256", "child_command_sha256",
        "cloud_execution_name", "child_exit_code", "elapsed_milliseconds",
        "dispatcher_runtime_evidence", "dispatcher_runtime_evidence_sha256",
        "timed_out", "stdout_overflow", "stderr_overflow",
        "child_stdout_bytes", "child_stdout_sha256",
        "child_stdout_byte_ceiling", "child_stderr_bytes",
        "child_stderr_sha256", "child_stderr_byte_ceiling",
        "child_envelope_schema", "child_envelope_sha256",
        "child_task_binding_evidence", "publication_identities",
        "publication_evidence", "publication_evidence_sha256",
        "task_completed", "raw_child_streams_embedded", "policy",
        "task_terminal_evidence_sha256",
    }
    if set(item) != expected_fields:
        _fail("task terminal evidence fields differ")
    _self_hash(
        item, field="task_terminal_evidence_sha256",
        label="task terminal evidence",
    )
    if len(_canonical_bytes(item)) > MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES:
        _fail("task terminal evidence exceeds its byte ceiling")
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity, label="terminal evidence manifest"
    )
    index = _integer(
        item.get("task_index"), label="terminal evidence task index",
        maximum=int(retained_manifest["task_count"]) - 1,
    )
    task = retained_manifest["task_bindings"][index]
    dispatcher_runtime_evidence = validate_dispatcher_runtime_evidence_v1(
        item.get("dispatcher_runtime_evidence"),
        manifest=retained_manifest,
        manifest_identity=identity,
    )
    completed = item.get("task_completed") is True
    flags_clear = (
        item.get("child_exit_code") == 0
        and item.get("timed_out") is False
        and item.get("stdout_overflow") is False
        and item.get("stderr_overflow") is False
    )
    publications = [
        _identity(row, label=f"terminal publication[{offset}]")
        for offset, row in enumerate(
            _sequence(item.get("publication_identities"), label="terminal publications")
        )
    ]
    publication_evidence = [
        _mapping(row, label=f"terminal publication evidence[{offset}]")
        for offset, row in enumerate(_sequence(
            item.get("publication_evidence"), label="terminal publication evidence"
        ))
    ]
    for offset, row in enumerate(publication_evidence):
        if set(row) != {
            "output_ordinal", "descriptor_uri", "descriptor_maximum_bytes",
            "publication_identity", "publication_within_descriptor_ceiling",
            "prior_identity", "exact_prior_generation_matched",
            "successful_create_or_exact_prior_reopen_required",
            "publication_generation_exact_reopen_proved",
            "accepted_from_canonical_child_envelope",
        } or row.get("output_ordinal") != offset:
            _fail("terminal publication evidence fields/order differ")
    if completed:
        binding = validate_child_task_binding_evidence_v1(
            item.get("child_task_binding_evidence"),
            manifest=retained_manifest,
            manifest_identity=identity,
        )
        if (
            not flags_clear
            or len(publications) != len(task["expected_outputs"])
            or any(
                publication["uri"] != output["uri"]
                for publication, output in zip(
                    publications, task["expected_outputs"], strict=True
                )
            )
            or item.get("child_envelope_sha256") is None
            or item.get("child_envelope_schema") is None
            or binding["task_binding_sha256"] != task["task_binding_sha256"]
            or len(publication_evidence) != len(task["expected_outputs"])
            or any(
                row.get("descriptor_uri") != descriptor["uri"]
                or row.get("descriptor_maximum_bytes") != descriptor["maximum_bytes"]
                or row.get("publication_identity") != publication
                or row.get("publication_within_descriptor_ceiling") is not True
                or row.get("prior_identity") != descriptor["prior_identity"]
                or row.get("exact_prior_generation_matched") is not True
                or row.get("successful_create_or_exact_prior_reopen_required") is not True
                or row.get("publication_generation_exact_reopen_proved") is not True
                or row.get("accepted_from_canonical_child_envelope") is not True
                for row, descriptor, publication in zip(
                    publication_evidence, task["expected_outputs"], publications,
                    strict=True,
                )
            )
        ):
            _fail("completed task terminal authority differs")
    elif (
        flags_clear
        or publications
        or item.get("child_task_binding_evidence") is not None
        or item.get("child_envelope_sha256") is not None
        or item.get("child_envelope_schema") is not None
        or publication_evidence
    ):
        _fail("failed task terminal evidence contains accepted child authority")
    if (
        item.get("schema_version") != TASK_TERMINAL_EVIDENCE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("manifest_identity") != identity
        or item.get("task_manifest_sha256")
        != retained_manifest["task_manifest_sha256"]
        or item.get("layer_id") != retained_manifest["layer_id"]
        or item.get("phase") != task["phase"]
        or item.get("process_role") != task["process_role"]
        or item.get("source_ordinal") != task["source_ordinal"]
        or item.get("process_ordinal") != task["process_ordinal"]
        or item.get("task_binding_sha256") != task["task_binding_sha256"]
        or item.get("task_science_binding_sha256")
        != task.get(
            "task_science_binding_sha256", _task_science_binding_sha256_v1(task)
        )
        or item.get("request_sha256") != task["request_sha256"]
        or item.get("expected_outputs") != task["expected_outputs"]
        or item.get("expected_outputs_sha256")
        != task["expected_outputs_sha256"]
        or item.get("child_command_sha256") != task["child_command_sha256"]
        or item.get("child_stdout_byte_ceiling")
        != task["child_stdout_byte_ceiling"]
        or item.get("child_stderr_byte_ceiling")
        != task["child_stderr_byte_ceiling"]
        or item.get("raw_child_streams_embedded") is not False
        or dispatcher_runtime_evidence["task_index"] != index
        or dispatcher_runtime_evidence["cloud_execution_name"]
        != item.get("cloud_execution_name")
        or item.get("dispatcher_runtime_evidence_sha256")
        != dispatcher_runtime_evidence["dispatcher_runtime_evidence_sha256"]
        or item.get("publication_evidence_sha256")
        != _canonical_sha(publication_evidence)
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("task terminal evidence manifest binding differs")
    _string(item.get("cloud_execution_name"), label="terminal cloud execution")
    _integer(item.get("child_exit_code"), label="terminal child exit", maximum=255)
    _integer(item.get("elapsed_milliseconds"), label="terminal elapsed", maximum=int(task["maximum_wall_seconds"]) * 1_000 + 60_000)
    stdout_bytes = _integer(item.get("child_stdout_bytes"), label="terminal stdout bytes", maximum=int(task["child_stdout_byte_ceiling"]))
    stderr_bytes = _integer(item.get("child_stderr_bytes"), label="terminal stderr bytes", maximum=int(task["child_stderr_byte_ceiling"]))
    if stdout_bytes > int(task["child_stdout_byte_ceiling"]) or stderr_bytes > int(task["child_stderr_byte_ceiling"]):
        _fail("terminal stream byte evidence exceeds task ceiling")
    _sha(item.get("child_stdout_sha256"), label="terminal stdout SHA-256")
    _sha(item.get("child_stderr_sha256"), label="terminal stderr SHA-256")
    return item


def _validated_terminal_record_v1(
    raw_record: object, *, manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object], expected_task_index: int,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate terminal evidence bound to the one unchanged layer manifest."""
    record = _mapping(raw_record, label=label)
    if set(record) != {"identity", "evidence"}:
        _fail(f"{label} fields differ")
    evidence_value = _mapping(record.get("evidence"), label=f"{label} evidence")
    evidence = validate_task_terminal_evidence_v1(
        evidence_value, manifest=manifest, manifest_identity=manifest_identity
    )
    evidence_identity = _bind_body(
        evidence, record.get("identity"), label=f"{label} identity"
    )
    task_index = _integer(
        evidence.get("task_index"), label=f"{label} task index",
        maximum=int(manifest["task_count"]) - 1,
    )
    if task_index != expected_task_index:
        _fail(f"{label} task index/order differs")
    task = manifest["task_bindings"][task_index]
    if (
        evidence_identity["uri"] != task["task_terminal_evidence_uri"]
        or evidence_identity["bytes"] > MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES
    ):
        _fail(f"{label} identity URI/byte ceiling differs")
    return evidence, evidence_identity


def build_layer_resume_authority_v1(
    *, manifest: object, manifest_identity: object, recovery_epoch: int,
    task_terminal_evidence_identities: object,
    prior_resume_authority_identity: object | None = None,
    prior_resume_authority: object | None = None,
    prior_observed_execution_identity: object | None = None,
    prior_layer_execution_receipt_identity: object | None = None,
    _structural_replay: bool = False,
) -> dict[str, object]:
    """Freeze sparse, completed same-manifest task slots for one recovery launch."""
    if not PRE_OUTPUT_RECOVERY_ALLOWED:
        _fail("layer recovery is not authorized in the pre-output release")
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity, label="resume authority manifest"
    )
    if identity["uri"] != retained_manifest["manifest_uri"]:
        _fail("resume authority manifest URI differs")
    epoch = _integer(
        recovery_epoch, label="resume recovery epoch",
        maximum=MAXIMUM_LAYER_RECOVERY_EPOCHS,
    )
    if epoch < 1:
        _fail("resume recovery epoch must be positive")
    descriptor = _layer_descriptor(
        str(retained_manifest["output_prefix"]),
        str(retained_manifest["layer_id"]),
    )
    raw_slots = _sequence(
        task_terminal_evidence_identities,
        label="resume task terminal evidence identities",
    )
    if len(raw_slots) != int(retained_manifest["task_count"]):
        _fail("resume task slot count differs from manifest")
    slots: list[dict[str, object]] = []
    completed: list[int] = []
    missing: list[int] = []
    for index, raw_identity in enumerate(raw_slots):
        terminal_identity = _optional_identity(
            raw_identity, label=f"resume task terminal evidence[{index}]"
        )
        task = retained_manifest["task_bindings"][index]
        if terminal_identity is None:
            missing.append(index)
        else:
            if (
                terminal_identity["uri"] != task["task_terminal_evidence_uri"]
                or terminal_identity["bytes"]
                > MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES
            ):
                _fail("resume task terminal identity URI/byte ceiling differs")
            completed.append(index)
        slots.append({
            "task_index": index,
            "task_terminal_evidence_identity": terminal_identity,
        })
    prior_observed = _optional_identity(
        prior_observed_execution_identity,
        label="resume prior observed execution",
    )
    if (
        prior_observed is not None
        and prior_observed["bytes"] > MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES
    ):
        _fail("resume prior observed execution exceeds its byte ceiling")
    prior_receipt = _optional_identity(
        prior_layer_execution_receipt_identity,
        label="resume prior layer receipt",
    )
    if prior_receipt is not None and (
        prior_receipt["uri"] != descriptor["layer_execution_receipt_uri"]
        or prior_receipt["bytes"] > MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES
    ):
        _fail("resume prior layer receipt URI/byte ceiling differs")
    if not completed:
        _fail("present layer resume authority must bind at least one completed task")
    prior_resume_identity = _optional_identity(
        prior_resume_authority_identity,
        label="prior layer resume authority",
    )
    if epoch == 1:
        if prior_resume_identity is not None or prior_resume_authority is not None:
            _fail("first recovery epoch cannot bind a prior resume authority")
    else:
        if prior_resume_identity is None:
            _fail("later recovery epoch requires its exact prior resume authority")
        if (
            prior_resume_identity["uri"]
            != descriptor["resume_authority_uris"][epoch - 2]
            or prior_resume_identity["bytes"]
            > MAXIMUM_LAYER_RESUME_AUTHORITY_BYTES
        ):
            _fail("prior resume authority epoch URI/byte ceiling differs")
        if prior_resume_authority is None:
            if not _structural_replay:
                _fail("resume builder requires the exact prior authority body")
        else:
            prior_resume = validate_layer_resume_authority_v1(
                prior_resume_authority,
                manifest=retained_manifest,
                manifest_identity=identity,
            )
            _bind_body(
                prior_resume, prior_resume_identity,
                label="prior layer resume authority",
            )
            if (
                prior_resume["recovery_epoch"] != epoch - 1
                or any(
                    old_slot["task_terminal_evidence_identity"] is not None
                    and old_slot["task_terminal_evidence_identity"]
                    != new_slot["task_terminal_evidence_identity"]
                    for old_slot, new_slot in zip(
                        prior_resume["task_slots"], slots, strict=True
                    )
                )
            ):
                _fail("resume authority does not monotonically extend prior slots")
    body = {
        "schema_version": LAYER_RESUME_AUTHORITY_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "resume_authority_uri": descriptor["resume_authority_uris"][epoch - 1],
        "manifest_identity": identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "layer_ordinal": retained_manifest["layer_ordinal"],
        "layer_id": retained_manifest["layer_id"],
        "task_count": retained_manifest["task_count"],
        "recovery_epoch": epoch,
        "prior_resume_authority_identity": prior_resume_identity,
        "prior_observed_execution_identity": prior_observed,
        "prior_layer_execution_receipt_identity": prior_receipt,
        "task_slots": slots,
        "task_slots_sha256": _canonical_sha(slots),
        "completed_task_indices": completed,
        "missing_task_indices": missing,
        "completed_task_count": len(completed),
        "original_manifest_unchanged": True,
        "sparse_completed_task_slots_allowed": True,
        "automatic_task_retry_allowed": False,
        "terminal_evidence_bodies_embedded": False,
        "caller_task_or_evidence_body_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    retained = _with_hash(body, field="layer_resume_authority_sha256")
    if len(_canonical_bytes(retained)) > MAXIMUM_LAYER_RESUME_AUTHORITY_BYTES:
        _fail("layer resume authority exceeds its byte ceiling")
    return retained


def validate_layer_resume_authority_v1(
    value: object, *, manifest: object, manifest_identity: object,
) -> dict[str, object]:
    if not PRE_OUTPUT_RECOVERY_ALLOWED:
        _fail("layer recovery is not authorized in the pre-output release")
    item = _mapping(value, label="layer resume authority")
    expected_fields = {
        "schema_version", "contract_id", "resume_authority_uri",
        "manifest_identity", "task_manifest_sha256", "layer_ordinal",
        "layer_id", "task_count", "recovery_epoch",
        "prior_observed_execution_identity",
        "prior_layer_execution_receipt_identity",
        "prior_resume_authority_identity", "task_slots",
        "task_slots_sha256", "completed_task_indices", "missing_task_indices",
        "completed_task_count", "original_manifest_unchanged",
        "sparse_completed_task_slots_allowed", "automatic_task_retry_allowed",
        "terminal_evidence_bodies_embedded",
        "caller_task_or_evidence_body_accepted", "policy",
        "layer_resume_authority_sha256",
    }
    if set(item) != expected_fields:
        _fail("layer resume authority fields differ")
    _self_hash(
        item, field="layer_resume_authority_sha256",
        label="layer resume authority",
    )
    if len(_canonical_bytes(item)) > MAXIMUM_LAYER_RESUME_AUTHORITY_BYTES:
        _fail("layer resume authority exceeds its byte ceiling")
    rebuilt = build_layer_resume_authority_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        recovery_epoch=_integer(
            item.get("recovery_epoch"), label="resume recovery epoch",
            maximum=MAXIMUM_LAYER_RECOVERY_EPOCHS,
        ),
        task_terminal_evidence_identities=[
            _mapping(row, label=f"resume task slot[{index}]").get(
                "task_terminal_evidence_identity"
            )
            for index, row in enumerate(_sequence(
                item.get("task_slots"), label="resume task slots"
            ))
        ],
        prior_resume_authority_identity=item.get(
            "prior_resume_authority_identity"
        ),
        prior_observed_execution_identity=item.get(
            "prior_observed_execution_identity"
        ),
        prior_layer_execution_receipt_identity=item.get(
            "prior_layer_execution_receipt_identity"
        ),
        _structural_replay=True,
    )
    if _canonical_bytes(item) != _canonical_bytes(rebuilt):
        _fail("layer resume authority canonical replay differs")
    return rebuilt


def reopen_layer_resume_authority_v1(
    resume_authority_identity: object, *, manifest: object,
    manifest_identity: object, read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open a resume authority and every sparse completed task slot."""
    if not PRE_OUTPUT_RECOVERY_ALLOWED:
        _fail("layer recovery is not authorized in the pre-output release")
    value, identity = _read_json_exact(
        resume_authority_identity,
        read_exact=read_exact,
        label="layer resume authority",
        maximum_bytes=MAXIMUM_LAYER_RESUME_AUTHORITY_BYTES,
    )
    retained_manifest = validate_task_manifest_v1(manifest)
    retained_manifest_identity = _bind_body(
        retained_manifest, manifest_identity,
        label="resume authority current manifest",
    )
    authority = validate_layer_resume_authority_v1(
        value,
        manifest=retained_manifest,
        manifest_identity=retained_manifest_identity,
    )
    if identity["uri"] != authority["resume_authority_uri"]:
        _fail("layer resume authority publication URI differs")
    prior_resume_authorities: list[dict[str, object]] = []
    newer = authority
    while newer["prior_resume_authority_identity"] is not None:
        prior_value, prior_identity = _read_json_exact(
            newer["prior_resume_authority_identity"],
            read_exact=read_exact,
            label="prior layer resume authority",
            maximum_bytes=MAXIMUM_LAYER_RESUME_AUTHORITY_BYTES,
        )
        prior = validate_layer_resume_authority_v1(
            prior_value,
            manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
        )
        _bind_body(prior, prior_identity, label="prior layer resume authority")
        if (
            prior_identity["uri"] != prior["resume_authority_uri"]
            or prior["recovery_epoch"] != newer["recovery_epoch"] - 1
            or any(
                old_slot["task_terminal_evidence_identity"] is not None
                and old_slot["task_terminal_evidence_identity"]
                != new_slot["task_terminal_evidence_identity"]
                for old_slot, new_slot in zip(
                    prior["task_slots"], newer["task_slots"], strict=True
                )
            )
        ):
            _fail("resume authority prior-epoch monotone chain differs")
        prior_resume_authorities.append(prior)
        newer = prior
    if newer["recovery_epoch"] != 1:
        _fail("resume authority chain does not terminate at epoch one")
    prior_observed_execution = None
    if authority["prior_observed_execution_identity"] is not None:
        prior_observed_execution, _ = _read_json_exact(
            authority["prior_observed_execution_identity"],
            read_exact=read_exact,
            label="resume prior observed execution",
            maximum_bytes=MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
        )
    prior_receipt = None
    if authority["prior_layer_execution_receipt_identity"] is not None:
        prior_receipt_value, prior_receipt_identity = _read_json_exact(
            authority["prior_layer_execution_receipt_identity"],
            read_exact=read_exact,
            label="resume prior layer execution receipt",
            maximum_bytes=MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
        )
        prior_receipt = validate_layer_execution_receipt_v1(prior_receipt_value)
        _bind_body(
            prior_receipt, prior_receipt_identity,
            label="resume prior layer execution receipt",
        )
        if (
            prior_receipt["manifest_identity"] != retained_manifest_identity
            or prior_receipt["task_manifest_sha256"]
            != retained_manifest["task_manifest_sha256"]
            or prior_receipt["layer_id"] != retained_manifest["layer_id"]
        ):
            _fail("resume prior layer receipt manifest/layer differs")
    terminal_records: list[dict[str, object] | None] = []
    for index, slot in enumerate(authority["task_slots"]):
        terminal_identity = slot["task_terminal_evidence_identity"]
        if terminal_identity is None:
            terminal_records.append(None)
            continue
        evidence_value, evidence_identity = _read_json_exact(
            terminal_identity,
            read_exact=read_exact,
            label=f"resume task[{index}] terminal evidence",
            maximum_bytes=MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES,
        )
        evidence = validate_task_terminal_evidence_v1(
            evidence_value,
            manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
        )
        _bind_body(
            evidence, evidence_identity,
            label=f"resume task[{index}] terminal evidence",
        )
        if evidence["task_index"] != index or evidence["task_completed"] is not True:
            _fail("resume terminal evidence task/completion differs")
        terminal_records.append({"identity": evidence_identity, "evidence": evidence})
    return {
        "resume_authority": authority,
        "resume_authority_identity": identity,
        "prior_layer_execution_receipt": prior_receipt,
        "prior_observed_execution": prior_observed_execution,
        "prior_resume_authorities": prior_resume_authorities,
        "task_terminal_records": terminal_records,
    }


def _resume_identity_from_environment_value_v1(
    raw_value: object, *, manifest: Mapping[str, object],
) -> dict[str, object] | None:
    if raw_value == ABSENT_RESUME_AUTHORITY_ENV_VALUE:
        return None
    _fail("layer recovery is absent-only in the pre-output release")


def _execution_condition_v1(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"type", "state"} or item != {
        "type": "Completed", "state": "CONDITION_SUCCEEDED",
    }:
        _fail(f"{label} differs")
    return item


def _provider_container_spec_v1(
    value: object, *, manifest: Mapping[str, object], label: str,
) -> dict[str, object]:
    """Retain the exact bounded Cloud Run v2 container launch subtree."""
    item = _mapping(value, label=label)
    if set(item) != {
        "image", "command", "args", "environment", "working_dir",
        "volume_mounts", "resource_limits",
    }:
        _fail(f"{label} fields differ")
    command = [
        _string(token, label=f"{label} command[{index}]", maximum=4_096)
        for index, token in enumerate(_sequence(
            item.get("command"), label=f"{label} command",
        ))
    ]
    args = [
        _string(token, label=f"{label} args[{index}]", maximum=4_096)
        for index, token in enumerate(_sequence(
            item.get("args"), label=f"{label} args",
        ))
    ]
    environment = _mapping(item.get("environment"), label=f"{label} environment")
    volume_mounts = _sequence(
        item.get("volume_mounts"), label=f"{label} volume mounts"
    )
    resource_limits = _mapping(
        item.get("resource_limits"), label=f"{label} resource limits"
    )
    expected_command = list(manifest["dispatcher_process_spec"]["command"])
    if (
        item.get("image") != manifest["image_digest"]
        or command != expected_command[:1]
        or args != expected_command[1:]
        or command + args != expected_command
        or item.get("working_dir") != ""
        or volume_mounts
        or resource_limits != {
            "cpu": FIXED_CLOUD_RUN_CPU_LIMIT,
            "memory": FIXED_CLOUD_RUN_MEMORY_LIMIT,
        }
        or not _FORBIDDEN_IMAGE_LAUNCH_ENVIRONMENT_KEYS.isdisjoint(environment)
    ):
        _fail(f"{label} launch authority differs")
    return {
        "image": item["image"],
        "command": command,
        "args": args,
        "environment": environment,
        "working_dir": "",
        "volume_mounts": [],
        "resource_limits": resource_limits,
    }


def _provider_execution_task_template_v1(
    value: object, *, manifest: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="provider execution TaskTemplate")
    if set(item) != {
        "containers", "maximum_task_retries", "timeout_seconds", "volumes",
    }:
        _fail("provider execution TaskTemplate fields differ")
    containers = [
        _provider_container_spec_v1(
            row, manifest=manifest,
            label=f"provider execution TaskTemplate container[{index}]",
        )
        for index, row in enumerate(_sequence(
            item.get("containers"),
            label="provider execution TaskTemplate containers",
        ))
    ]
    volumes = _sequence(item.get("volumes"), label="provider TaskTemplate volumes")
    if (
        len(containers) != 1
        or volumes
        or item.get("maximum_task_retries") != 0
        or item.get("timeout_seconds") != MAXIMUM_DISPATCHER_WALL_SECONDS
    ):
        _fail("provider execution TaskTemplate authority differs")
    return {
        "containers": containers,
        "maximum_task_retries": 0,
        "timeout_seconds": MAXIMUM_DISPATCHER_WALL_SECONDS,
        "volumes": [],
    }


def _provider_run_job_overrides_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="provider RunJob overrides")
    expected = {
        "container_overrides": [],
        "task_count": None,
        "timeout_seconds": None,
    }
    if item != expected:
        _fail("provider RunJob execution overrides are present")
    return expected


def validate_cloud_run_execution_observation_source_v1(
    value: object, *, manifest: object, manifest_identity: object,
    task_terminal_records: object,
) -> dict[str, object]:
    """Validate one normalized Cloud Run v2 plus per-task kernel observation."""
    item = _mapping(value, label="Cloud Run execution observation source")
    expected_fields = {
        "schema_version", "contract_id", "collection_semantics",
        "manifest_identity", "task_manifest_sha256", "project_id", "location",
        "job_name", "job_uid", "job_generation", "execution_name",
        "execution_uid", "execution_generation", "code_commit", "image_digest",
        "job_dispatcher_command", "job_dispatcher_command_sha256",
        "job_dispatcher_environment", "job_dispatcher_environment_sha256",
        "job_dispatcher_environment_semantics",
        "job_dispatcher_environment_complete_provider_spec",
        "job_dispatcher_environment_redirect_keys_absent",
        "provider_job_container_spec", "provider_job_container_spec_sha256",
        "provider_execution_task_template",
        "provider_execution_task_template_sha256",
        "provider_run_job_overrides", "provider_run_job_overrides_sha256",
        "task_terminal_generation_resolution_scope",
        "task_terminal_generation_resolution_scope_sha256",
        "task_count", "parallelism", "maximum_task_retries",
        "task_observations", "task_observations_sha256",
        "execution_conditions", "execution_conditions_sha256",
        "source_capture_complete", "provider_attestation_claimed",
        "cloud_run_execution_observation_source_sha256",
    }
    if set(item) != expected_fields:
        _fail("Cloud Run execution observation source fields differ")
    _self_hash(
        item,
        field="cloud_run_execution_observation_source_sha256",
        label="Cloud Run execution observation source",
    )
    if len(_canonical_bytes(item)) > MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES:
        _fail("Cloud Run execution observation source exceeds its byte ceiling")
    retained_manifest = validate_task_manifest_v1(manifest)
    retained_manifest_identity = _bind_body(
        retained_manifest, manifest_identity,
        label="Cloud Run observation source manifest",
    )
    terminal_generation_scope = _mapping(
        item.get("task_terminal_generation_resolution_scope"),
        label="source task-terminal generation-resolution scope",
    )
    expected_terminal_generation_scope = (
        _task_terminal_generation_resolution_scope_v1(
            retained_manifest["task_bindings"]
        )
    )
    execution = _string(
        item.get("execution_name"), label="source execution name", maximum=512
    )
    job_generation = _string(
        item.get("job_generation"), label="source job generation", maximum=31
    )
    execution_generation = _string(
        item.get("execution_generation"),
        label="source execution generation", maximum=31,
    )
    if (
        _GENERATION_RE.fullmatch(job_generation) is None
        or _GENERATION_RE.fullmatch(execution_generation) is None
    ):
        _fail("source Cloud Run generation differs")
    command = [
        _string(row, label=f"source job command[{index}]", maximum=4_096)
        for index, row in enumerate(_sequence(
            item.get("job_dispatcher_command"), label="source job command"
        ))
    ]
    common_environment = {
        "R6_CURRENT_BANK_TASK_DISPATCH_ENABLED": "1",
        DISPATCH_MANIFEST_IDENTITY_ENV: _canonical_bytes(
            retained_manifest_identity
        ).decode("utf-8"),
        DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: (
            ABSENT_RESUME_AUTHORITY_ENV_VALUE
        ),
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": retained_manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": retained_manifest["image_digest"],
        "CLOUD_RUN_JOB": retained_manifest["reused_job_name"],
    }
    supplied_common_environment = _mapping(
        item.get("job_dispatcher_environment"),
        label="source job dispatcher environment",
    )
    provider_job_container = _provider_container_spec_v1(
        item.get("provider_job_container_spec"),
        manifest=retained_manifest,
        label="provider job container spec",
    )
    provider_execution_template = _provider_execution_task_template_v1(
        item.get("provider_execution_task_template"),
        manifest=retained_manifest,
    )
    provider_run_job_overrides = _provider_run_job_overrides_v1(
        item.get("provider_run_job_overrides")
    )
    count = _integer(
        item.get("task_count"), label="source task count", maximum=220
    )
    parallelism = _integer(
        item.get("parallelism"), label="source parallelism", maximum=220
    )
    raw_observations = _sequence(
        item.get("task_observations"), label="source task observations"
    )
    if len(raw_observations) != count:
        _fail("source task observation count differs")
    observations: list[dict[str, object]] = []
    for index, raw_observation in enumerate(raw_observations):
        observation = _mapping(
            raw_observation, label=f"source task observation[{index}]"
        )
        if set(observation) != {
            "task_index", "task_name", "attempt", "terminal_state",
            "exit_code", "task_terminal_evidence_sha256", "conditions",
            "kernel_dispatcher_command", "kernel_dispatcher_command_sha256",
            "kernel_dispatcher_environment",
            "kernel_dispatcher_environment_sha256",
        }:
            _fail("source task observation fields differ")
        kernel_command = [
            _string(
                token, label=f"source task[{index}] kernel command token",
                maximum=4_096,
            )
            for token in _sequence(
                observation.get("kernel_dispatcher_command"),
                label=f"source task[{index}] kernel command",
            )
        ]
        kernel_environment = _mapping(
            observation.get("kernel_dispatcher_environment"),
            label=f"source task[{index}] kernel environment",
        )
        expected_kernel_environment = {
            **common_environment,
            "CLOUD_RUN_EXECUTION": execution,
            "CLOUD_RUN_TASK_INDEX": str(index),
            "CLOUD_RUN_TASK_COUNT": str(count),
            "CLOUD_RUN_TASK_ATTEMPT": "0",
        }
        conditions = [
            _execution_condition_v1(
                row, label=f"source task[{index}] condition[{offset}]"
            )
            for offset, row in enumerate(_sequence(
                observation.get("conditions"),
                label=f"source task[{index}] conditions",
            ))
        ]
        retained_observation = {
            "task_index": _integer(
                observation.get("task_index"), label="source task index",
                maximum=count - 1,
            ),
            "task_name": _string(
                observation.get("task_name"), label="source task name", maximum=512
            ),
            "attempt": _integer(
                observation.get("attempt"), label="source task attempt", maximum=0
            ),
            "terminal_state": _string(
                observation.get("terminal_state"),
                label="source terminal state", maximum=32,
            ),
            "exit_code": _integer(
                observation.get("exit_code"), label="source exit code", maximum=255
            ),
            "task_terminal_evidence_sha256": _sha(
                observation.get("task_terminal_evidence_sha256"),
                label="source terminal evidence SHA-256",
            ),
            "conditions": conditions,
            "kernel_dispatcher_command": kernel_command,
            "kernel_dispatcher_command_sha256": _sha(
                observation.get("kernel_dispatcher_command_sha256"),
                label="source kernel command SHA-256",
            ),
            "kernel_dispatcher_environment": kernel_environment,
            "kernel_dispatcher_environment_sha256": _sha(
                observation.get("kernel_dispatcher_environment_sha256"),
                label="source kernel environment SHA-256",
            ),
        }
        if (
            retained_observation["task_index"] != index
            or retained_observation["task_name"] != f"{execution}/tasks/{index}"
            or retained_observation["attempt"] != 0
            or retained_observation["terminal_state"] != "SUCCEEDED"
            or retained_observation["exit_code"] != 0
            or conditions
            != [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}]
            or kernel_command != command
            or kernel_command != retained_manifest["dispatcher_process_spec"]["command"]
            or retained_observation["kernel_dispatcher_command_sha256"]
            != _canonical_sha(kernel_command)
            or kernel_environment != expected_kernel_environment
            or retained_observation["kernel_dispatcher_environment_sha256"]
            != _canonical_sha(kernel_environment)
        ):
            _fail("source kernel/task observation authority differs")
        observations.append(retained_observation)
    execution_conditions = [
        _execution_condition_v1(row, label=f"source execution condition[{index}]")
        for index, row in enumerate(_sequence(
            item.get("execution_conditions"),
            label="source execution conditions",
        ))
    ]
    if (
        item.get("schema_version")
        != CLOUD_RUN_EXECUTION_OBSERVATION_SOURCE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("collection_semantics")
        != "cloud-run-v2-api-plus-dispatcher-kernel-observation"
        or item.get("manifest_identity") != retained_manifest_identity
        or item.get("task_manifest_sha256")
        != retained_manifest["task_manifest_sha256"]
        or item.get("project_id") != FIXED_GCP_PROJECT
        or item.get("location") != FIXED_CLOUD_RUN_LOCATION
        or item.get("job_name") != retained_manifest["reused_job_name"]
        or item.get("code_commit") != retained_manifest["code_commit"]
        or item.get("image_digest") != retained_manifest["image_digest"]
        or command != retained_manifest["dispatcher_process_spec"]["command"]
        or item.get("job_dispatcher_command_sha256") != _canonical_sha(command)
        or supplied_common_environment != common_environment
        or item.get("job_dispatcher_environment_sha256")
        != _canonical_sha(common_environment)
        or item.get("job_dispatcher_environment_semantics")
        != _COMPLETE_PROVIDER_JOB_ENVIRONMENT_SEMANTICS
        or item.get("job_dispatcher_environment_complete_provider_spec") is not True
        or item.get("job_dispatcher_environment_redirect_keys_absent") is not True
        or not _FORBIDDEN_IMAGE_LAUNCH_ENVIRONMENT_KEYS.isdisjoint(
            supplied_common_environment
        )
        or provider_job_container["command"] + provider_job_container["args"]
        != command
        or provider_job_container["environment"] != common_environment
        or item.get("provider_job_container_spec_sha256")
        != _canonical_sha(provider_job_container)
        or provider_execution_template["containers"] != [provider_job_container]
        or item.get("provider_execution_task_template_sha256")
        != _canonical_sha(provider_execution_template)
        or provider_run_job_overrides != {
            "container_overrides": [], "task_count": None,
            "timeout_seconds": None,
        }
        or item.get("provider_run_job_overrides_sha256")
        != _canonical_sha(provider_run_job_overrides)
        or terminal_generation_scope != expected_terminal_generation_scope
        or item.get("task_terminal_generation_resolution_scope_sha256")
        != _canonical_sha(terminal_generation_scope)
        or count != retained_manifest["task_count"]
        or parallelism != retained_manifest["task_count"]
        or item.get("maximum_task_retries") != 0
        or item.get("task_observations_sha256") != _canonical_sha(observations)
        or execution_conditions
        != [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}]
        or item.get("execution_conditions_sha256")
        != _canonical_sha(execution_conditions)
        or item.get("source_capture_complete") is not True
        or item.get("provider_attestation_claimed") is not False
    ):
        _fail("Cloud Run execution observation source authority differs")
    for field, label in (
        ("job_uid", "source job UID"),
        ("execution_uid", "source execution UID"),
    ):
        _string(item.get(field), label=label, maximum=128)
    raw_terminal_records = _sequence(
        task_terminal_records, label="observation source terminal records"
    )
    if len(raw_terminal_records) != count:
        _fail("observation source terminal-record count differs")
    for index, (raw_record, observation) in enumerate(zip(
        raw_terminal_records, observations, strict=True
    )):
        evidence, _evidence_identity = _validated_terminal_record_v1(
            raw_record,
            manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
            expected_task_index=index,
            label=f"observation source terminal record[{index}]",
        )
        runtime = evidence["dispatcher_runtime_evidence"]
        if (
            evidence["task_completed"] is not True
            or evidence["cloud_execution_name"] != execution
            or evidence["task_terminal_evidence_sha256"]
            != observation["task_terminal_evidence_sha256"]
            or runtime["kernel_observed_command"]
            != observation["kernel_dispatcher_command"]
            or runtime["kernel_observed_command_sha256"]
            != observation["kernel_dispatcher_command_sha256"]
            or runtime["selected_environment"]
            != observation["kernel_dispatcher_environment"]
            or runtime["selected_environment_sha256"]
            != observation["kernel_dispatcher_environment_sha256"]
        ):
            _fail("observation source differs from exact terminal runtime evidence")
    return item


def build_observed_cloud_run_execution_authority_v1(
    *, manifest: object, manifest_identity: object,
    observation_source: object, observation_source_identity: object,
    task_terminal_records: object,
) -> dict[str, object]:
    """Derive compact execution authority only from one exact source body."""
    retained_manifest = validate_task_manifest_v1(manifest)
    retained_manifest_identity = _bind_body(
        retained_manifest, manifest_identity, label="observed execution manifest"
    )
    source = validate_cloud_run_execution_observation_source_v1(
        observation_source,
        manifest=retained_manifest,
        manifest_identity=retained_manifest_identity,
        task_terminal_records=task_terminal_records,
    )
    source_identity = _bind_body(
        source, observation_source_identity,
        label="Cloud Run execution observation source",
    )
    descriptor = _layer_descriptor(
        str(retained_manifest["output_prefix"]),
        str(retained_manifest["layer_id"]),
    )
    if (
        source_identity["uri"] != descriptor["cloud_run_observation_source_uri"]
        or source_identity["bytes"] > MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES
    ):
        _fail("Cloud Run observation source URI/byte ceiling differs")
    terminal_states = [
        {
            "task_index": row["task_index"],
            "task_name": row["task_name"],
            "attempt": row["attempt"],
            "terminal_state": row["terminal_state"],
            "exit_code": row["exit_code"],
            "task_terminal_evidence_sha256": row[
                "task_terminal_evidence_sha256"
            ],
            "conditions": row["conditions"],
        }
        for row in source["task_observations"]
    ]
    body = {
        "schema_version": OBSERVED_CLOUD_RUN_EXECUTION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "evidence_semantics": (
            "exact-opened-cloud-run-v2-plus-kernel-observation-not-provider-attestation"
        ),
        "observation_source_identity": source_identity,
        "observation_source_sha256": source[
            "cloud_run_execution_observation_source_sha256"
        ],
        "observation_source_exact_open_required": True,
        "task_terminal_generation_resolution_scope": deepcopy(
            source["task_terminal_generation_resolution_scope"]
        ),
        "task_terminal_generation_resolution_scope_sha256": source[
            "task_terminal_generation_resolution_scope_sha256"
        ],
        "manifest_identity": retained_manifest_identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "project_id": source["project_id"],
        "location": source["location"],
        "job_name": source["job_name"],
        "job_uid": source["job_uid"],
        "job_generation": source["job_generation"],
        "execution_name": source["execution_name"],
        "execution_uid": source["execution_uid"],
        "execution_generation": source["execution_generation"],
        "code_commit": source["code_commit"],
        "image_digest": source["image_digest"],
        "dispatcher_command": source["job_dispatcher_command"],
        "dispatcher_command_sha256": source["job_dispatcher_command_sha256"],
        "dispatcher_environment": source["job_dispatcher_environment"],
        "dispatcher_environment_sha256": source[
            "job_dispatcher_environment_sha256"
        ],
        "dispatcher_environment_semantics": source[
            "job_dispatcher_environment_semantics"
        ],
        "dispatcher_environment_complete_provider_spec": source[
            "job_dispatcher_environment_complete_provider_spec"
        ],
        "dispatcher_environment_redirect_keys_absent": source[
            "job_dispatcher_environment_redirect_keys_absent"
        ],
        "execution_task_template_overrides_present": False,
        "execution_command_override_present": False,
        "execution_environment_override_present": False,
        "effective_dispatcher_command_equals_job_spec": True,
        "effective_dispatcher_environment_equals_job_spec": True,
        "layer_resume_authority_identity": None,
        "resume_authority_explicitly_absent": True,
        "task_count": source["task_count"],
        "parallelism": source["parallelism"],
        "maximum_task_retries": source["maximum_task_retries"],
        "terminal_states": terminal_states,
        "terminal_states_sha256": _canonical_sha(terminal_states),
        "execution_conditions": source["execution_conditions"],
        "execution_conditions_sha256": source[
            "execution_conditions_sha256"
        ],
        "execution_completed": True,
        "provider_attestation_claimed": False,
    }
    return _with_hash(body, field="observed_cloud_run_execution_sha256")


def validate_observed_cloud_run_execution_authority_v1(
    value: object, *, manifest: object, manifest_identity: object,
    observation_source: object, task_terminal_records: object,
) -> dict[str, object]:
    item = _mapping(value, label="observed Cloud Run execution authority")
    expected_fields = {
        "schema_version", "contract_id", "evidence_semantics",
        "observation_source_identity", "observation_source_sha256",
        "observation_source_exact_open_required",
        "task_terminal_generation_resolution_scope",
        "task_terminal_generation_resolution_scope_sha256",
        "manifest_identity",
        "task_manifest_sha256", "project_id", "location", "job_name",
        "job_uid", "job_generation", "execution_name", "execution_uid",
        "execution_generation", "code_commit", "image_digest",
        "dispatcher_command", "dispatcher_command_sha256",
        "dispatcher_environment", "dispatcher_environment_sha256",
        "dispatcher_environment_semantics",
        "dispatcher_environment_complete_provider_spec",
        "dispatcher_environment_redirect_keys_absent",
        "execution_task_template_overrides_present",
        "execution_command_override_present",
        "execution_environment_override_present",
        "effective_dispatcher_command_equals_job_spec",
        "effective_dispatcher_environment_equals_job_spec",
        "layer_resume_authority_identity", "resume_authority_explicitly_absent",
        "task_count", "parallelism", "maximum_task_retries",
        "terminal_states", "terminal_states_sha256", "execution_conditions",
        "execution_conditions_sha256", "execution_completed",
        "provider_attestation_claimed", "observed_cloud_run_execution_sha256",
    }
    if set(item) != expected_fields:
        _fail("observed Cloud Run execution authority fields differ")
    _self_hash(
        item, field="observed_cloud_run_execution_sha256",
        label="observed Cloud Run execution authority",
    )
    rebuilt = build_observed_cloud_run_execution_authority_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        observation_source=observation_source,
        observation_source_identity=item.get("observation_source_identity"),
        task_terminal_records=task_terminal_records,
    )
    if _canonical_bytes(item) != _canonical_bytes(rebuilt):
        _fail("observed Cloud Run execution exact-source derivation differs")
    return rebuilt


def reopen_observed_cloud_run_execution_authority_v1(
    value: object, *, manifest: object, manifest_identity: object,
    task_terminal_records: object, read_exact: ReadExact,
) -> dict[str, object]:
    item = _mapping(value, label="observed Cloud Run execution authority")
    source, _ = _read_json_exact(
        item.get("observation_source_identity"),
        read_exact=read_exact,
        label="Cloud Run execution observation source",
        maximum_bytes=MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES,
    )
    return validate_observed_cloud_run_execution_authority_v1(
        item,
        manifest=manifest,
        manifest_identity=manifest_identity,
        observation_source=source,
        task_terminal_records=task_terminal_records,
    )


def build_layer_execution_receipt_v1(
    *, manifest: object, manifest_identity: object,
    observed_execution_authority: object, task_terminal_records: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build a compact identity/hash ledger for one externally observed layer."""
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity, label="layer receipt manifest"
    )
    raw_records = _sequence(task_terminal_records, label="task terminal records")
    observed = reopen_observed_cloud_run_execution_authority_v1(
        observed_execution_authority,
        manifest=retained_manifest,
        manifest_identity=identity,
        task_terminal_records=raw_records,
        read_exact=read_exact,
    )
    if observed["layer_resume_authority_identity"] is not None:
        _fail("pre-output layer receipt cannot bind recovery authority")
    task_count = int(retained_manifest["task_count"])
    states = observed["terminal_states"]
    if len(raw_records) != task_count:
        _fail("layer receipt terminal-evidence count differs from manifest")
    records: list[dict[str, object]] = []
    for index, raw_record in enumerate(raw_records):
        evidence, evidence_identity = _validated_terminal_record_v1(
                raw_record,
                manifest=retained_manifest,
                manifest_identity=identity,
                expected_task_index=index,
                label=f"task terminal record[{index}]",
            )
        resumed = False
        task = retained_manifest["task_bindings"][index]
        state = states[index]
        if (
            evidence_identity["uri"] != task["task_terminal_evidence_uri"]
            or evidence_identity["bytes"] > MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES
            or evidence["task_index"] != index
            or (
                not resumed
                and evidence["cloud_execution_name"] != observed["execution_name"]
            )
            or evidence["task_completed"] is not True
            or state["task_terminal_evidence_sha256"]
            != evidence["task_terminal_evidence_sha256"]
        ):
            _fail("layer receipt task/evidence/execution binding differs")
        publications = [
            {
                "topology_ordinal": descriptor["topology_ordinal"],
                "role": descriptor["role"],
                "identity": publication,
            }
            for descriptor, publication in zip(
                task["expected_outputs"], evidence["publication_identities"],
                strict=True,
            )
        ]
        records.append({
            "task_index": index,
            "task_binding_sha256": task["task_binding_sha256"],
            "task_science_binding_sha256": task.get(
                "task_science_binding_sha256",
                _task_science_binding_sha256_v1(task),
            ),
            "task_terminal_evidence_identity": evidence_identity,
            "task_terminal_evidence_manifest_identity": (
                identity
            ),
            "task_terminal_evidence_sha256": evidence[
                "task_terminal_evidence_sha256"
            ],
            "publication_records": publications,
            "publication_records_sha256": _canonical_sha(publications),
            "publication_evidence_sha256": evidence["publication_evidence_sha256"],
            "resumed_exact_same_manifest": resumed,
            "terminal_evidence_generation_exact_reopen_proved": True,
        })
    body = {
        "schema_version": LAYER_EXECUTION_RECEIPT_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": identity,
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "design_identity": retained_manifest["design_identity"],
        "design_sha256": retained_manifest["design_sha256"],
        "topology_identity": retained_manifest["topology_identity"],
        "topology_sha256": retained_manifest["topology_sha256"],
        "bootstrap_manifest_identity": retained_manifest["bootstrap_manifest_identity"],
        "bootstrap_manifest_sha256": retained_manifest["bootstrap_manifest_sha256"],
        "pre_design_run_authorization_identity": retained_manifest[
            "pre_design_run_authorization_identity"
        ],
        "pre_design_run_authorization_sha256": retained_manifest[
            "pre_design_run_authorization_sha256"
        ],
        "predecessor_layer_receipts": deepcopy(
            retained_manifest["predecessor_layer_receipts"]
        ),
        "predecessor_layer_receipts_sha256": retained_manifest[
            "predecessor_layer_receipts_sha256"
        ],
        "layer_ordinal": retained_manifest["layer_ordinal"],
        "layer_id": retained_manifest["layer_id"],
        "phase": retained_manifest["phase"],
        "process_role": retained_manifest["process_role"],
        "code_commit": retained_manifest["code_commit"],
        "image_digest": retained_manifest["image_digest"],
        "reused_job_name": retained_manifest["reused_job_name"],
        "observed_execution_authority": observed,
        "observed_execution_authority_sha256": observed[
            "observed_cloud_run_execution_sha256"
        ],
        "recovery_allowed": False,
        "layer_resume_authority_identity": None,
        "layer_resume_authority_sha256": None,
        "recovery_epoch": None,
        "resume_authority_body_embedded": False,
        "task_count": task_count,
        "completed_task_count": task_count,
        "task_records": records,
        "task_records_sha256": _canonical_sha(records),
        "all_tasks_completed": True,
        "bodies_embedded": False,
        "external_attestation_claimed": False,
        "one_reused_job": True,
        "current_generation_resolution_allowed": True,
        "current_generation_resolution_scope": (
            "host-finalizer-exact-manifest-task-terminal-evidence-uris-only"
        ),
        "task_terminal_generation_resolution_scope": deepcopy(
            observed["task_terminal_generation_resolution_scope"]
        ),
        "task_terminal_generation_resolution_scope_sha256": observed[
            "task_terminal_generation_resolution_scope_sha256"
        ],
        "listing_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    retained = _with_hash(body, field="layer_execution_receipt_sha256")
    if len(_canonical_bytes(retained)) > MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES:
        _fail("layer execution receipt exceeds its compact byte ceiling")
    return retained


def validate_layer_execution_receipt_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="layer execution receipt")
    expected_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "design_identity", "design_sha256",
        "topology_identity", "topology_sha256", "bootstrap_manifest_identity",
        "bootstrap_manifest_sha256", "pre_design_run_authorization_identity",
        "pre_design_run_authorization_sha256", "predecessor_layer_receipts",
        "predecessor_layer_receipts_sha256", "layer_ordinal", "layer_id", "phase",
        "process_role", "code_commit", "image_digest", "reused_job_name",
        "observed_execution_authority", "observed_execution_authority_sha256",
        "recovery_allowed",
        "layer_resume_authority_identity", "layer_resume_authority_sha256",
        "recovery_epoch", "resume_authority_body_embedded",
        "task_count", "completed_task_count", "task_records",
        "task_records_sha256", "all_tasks_completed", "bodies_embedded",
        "external_attestation_claimed", "one_reused_job",
        "current_generation_resolution_allowed", "current_generation_resolution_scope",
        "task_terminal_generation_resolution_scope",
        "task_terminal_generation_resolution_scope_sha256",
        "listing_allowed", "policy",
        "layer_execution_receipt_sha256",
    }
    if set(item) != expected_fields:
        _fail("layer execution receipt fields differ")
    _self_hash(
        item, field="layer_execution_receipt_sha256",
        label="layer execution receipt",
    )
    if len(_canonical_bytes(item)) > MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES:
        _fail("layer execution receipt exceeds its compact byte ceiling")
    layer = _layer(item.get("layer_id"))
    records = [
        _mapping(row, label=f"receipt task record[{index}]")
        for index, row in enumerate(_sequence(
            item.get("task_records"), label="receipt task records"
        ))
    ]
    if len(records) != layer.task_count:
        _fail("receipt compact task-record count differs")
    for index, row in enumerate(records):
        if set(row) != {
            "task_index", "task_binding_sha256", "task_science_binding_sha256",
            "task_terminal_evidence_identity",
            "task_terminal_evidence_manifest_identity",
            "task_terminal_evidence_sha256",
            "publication_records", "publication_records_sha256",
            "publication_evidence_sha256",
            "resumed_exact_same_manifest",
            "terminal_evidence_generation_exact_reopen_proved",
        } or row.get("task_index") != index:
            _fail("receipt compact task-record fields/order differ")
        evidence_identity = _identity(
            row.get("task_terminal_evidence_identity"),
            label=f"receipt terminal evidence[{index}]",
        )
        if evidence_identity["bytes"] > MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES:
            _fail("receipt terminal evidence identity exceeds its byte ceiling")
        evidence_manifest_identity = _identity(
            row.get("task_terminal_evidence_manifest_identity"),
            label=f"receipt terminal evidence manifest[{index}]",
        )
        if evidence_manifest_identity["bytes"] > MAXIMUM_MANIFEST_BYTES:
            _fail("receipt terminal evidence manifest exceeds its byte ceiling")
        publications = []
        for offset, raw_publication in enumerate(_sequence(
            row.get("publication_records"), label=f"receipt publications[{index}]"
        )):
            publication = _mapping(
                raw_publication, label=f"receipt publication[{index},{offset}]"
            )
            if set(publication) != {"topology_ordinal", "role", "identity"}:
                _fail("receipt publication-record fields differ")
            _integer(
                publication.get("topology_ordinal"),
                label="receipt publication topology ordinal",
                maximum=contract.OUTPUT_OBJECT_COUNT - 1,
            )
            _string(publication.get("role"), label="receipt publication role", maximum=64)
            _identity(publication.get("identity"), label="receipt publication identity")
            publications.append(publication)
        for field in (
            "task_binding_sha256", "task_science_binding_sha256",
            "task_terminal_evidence_sha256",
            "publication_records_sha256", "publication_evidence_sha256",
        ):
            _sha(row.get(field), label=f"receipt task record {field}")
        if (
            type(row.get("resumed_exact_same_manifest")) is not bool
            or row.get("terminal_evidence_generation_exact_reopen_proved") is not True
            or evidence_manifest_identity != item.get("manifest_identity")
            or row["publication_records_sha256"] != _canonical_sha(publications)
        ):
            _fail("receipt publication identity ledger hash differs")
    predecessors = _sequence(
        item.get("predecessor_layer_receipts"), label="receipt predecessors"
    )
    if len(predecessors) != len(layer.predecessor_layers):
        _fail("receipt predecessor-chain length differs")
    for expected_layer, raw in zip(layer.predecessor_layers, predecessors, strict=True):
        row = _mapping(raw, label="receipt predecessor binding")
        if set(row) != {
            "layer_id", "receipt_identity", "layer_execution_receipt_sha256"
        } or row.get("layer_id") != expected_layer:
            _fail("receipt predecessor-chain fields/order differ")
        _identity(row.get("receipt_identity"), label="receipt predecessor identity")
        _sha(row.get("layer_execution_receipt_sha256"), label="receipt predecessor hash")
    observed = _mapping(
        item.get("observed_execution_authority"),
        label="receipt observed execution authority",
    )
    observed_fields = {
        "schema_version", "contract_id", "evidence_semantics",
        "observation_source_identity", "observation_source_sha256",
        "observation_source_exact_open_required",
        "task_terminal_generation_resolution_scope",
        "task_terminal_generation_resolution_scope_sha256",
        "manifest_identity",
        "task_manifest_sha256", "project_id", "location", "job_name", "job_uid",
        "job_generation", "execution_name", "execution_uid",
        "execution_generation", "code_commit", "image_digest",
        "dispatcher_command", "dispatcher_command_sha256",
        "dispatcher_environment", "dispatcher_environment_sha256",
        "dispatcher_environment_semantics",
        "dispatcher_environment_complete_provider_spec",
        "dispatcher_environment_redirect_keys_absent",
        "execution_task_template_overrides_present",
        "execution_command_override_present",
        "execution_environment_override_present",
        "effective_dispatcher_command_equals_job_spec",
        "effective_dispatcher_environment_equals_job_spec", "task_count",
        "layer_resume_authority_identity", "resume_authority_explicitly_absent",
        "parallelism", "maximum_task_retries", "terminal_states",
        "terminal_states_sha256", "execution_conditions",
        "execution_conditions_sha256", "execution_completed",
        "provider_attestation_claimed", "observed_cloud_run_execution_sha256",
    }
    if set(observed) != observed_fields:
        _fail("receipt observed execution fields differ")
    _self_hash(
        observed, field="observed_cloud_run_execution_sha256",
        label="receipt observed execution",
    )
    source_identity = _identity(
        observed.get("observation_source_identity"),
        label="receipt observation source identity",
    )
    _sha(
        observed.get("observation_source_sha256"),
        label="receipt observation source SHA-256",
    )
    terminal_generation_scope = _mapping(
        item.get("task_terminal_generation_resolution_scope"),
        label="receipt task-terminal generation-resolution scope",
    )
    expected_terminal_generation_scope = (
        _task_terminal_generation_resolution_scope_v1([
            {
                "task_terminal_evidence_uri": _identity(
                    record["task_terminal_evidence_identity"],
                    label="receipt generation-resolution terminal identity",
                )["uri"]
            }
            for record in records
        ])
    )
    observed_command = [
        _string(token, label="receipt observed command token", maximum=4_096)
        for token in _sequence(
            observed.get("dispatcher_command"),
            label="receipt observed dispatcher command",
        )
    ]
    observed_environment = _mapping(
        observed.get("dispatcher_environment"),
        label="receipt observed dispatcher environment",
    )
    states = [
        _mapping(row, label=f"receipt observed task state[{index}]")
        for index, row in enumerate(_sequence(
            observed.get("terminal_states"), label="receipt observed task states"
        ))
    ]
    if len(states) != layer.task_count:
        _fail("receipt observed task-state count differs")
    for index, (state, record) in enumerate(zip(states, records, strict=True)):
        if (
            set(state) != {
                "task_index", "task_name", "attempt", "terminal_state",
                "exit_code", "task_terminal_evidence_sha256", "conditions",
            }
            or state.get("task_index") != index
            or state.get("task_name")
            != f"{observed.get('execution_name')}/tasks/{index}"
            or state.get("attempt") != 0
            or state.get("terminal_state") != "SUCCEEDED"
            or state.get("exit_code") != 0
            or state.get("task_terminal_evidence_sha256")
            != record["task_terminal_evidence_sha256"]
            or state.get("conditions")
            != [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}]
        ):
            _fail("receipt observed terminal-state order/completion differs")
    execution_conditions = _sequence(
        observed.get("execution_conditions"),
        label="receipt observed execution conditions",
    )
    resume_shape_valid = (
        item.get("recovery_allowed") is False
        and item.get("layer_resume_authority_identity") is None
        and item.get("layer_resume_authority_sha256") is None
        and item.get("recovery_epoch") is None
        and observed.get("layer_resume_authority_identity") is None
        and observed.get("resume_authority_explicitly_absent") is True
        and not any(row["resumed_exact_same_manifest"] for row in records)
    )
    if (
        item.get("schema_version") != LAYER_EXECUTION_RECEIPT_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("layer_ordinal")
        != next(index for index, row in enumerate(_LAYER_SPECS) if row == layer)
        or item.get("phase") != layer.phase
        or item.get("process_role") != layer.process_role
        or item.get("task_count") != layer.task_count
        or item.get("completed_task_count") != layer.task_count
        or item.get("predecessor_layer_receipts_sha256") != _canonical_sha(predecessors)
        or item.get("task_records_sha256") != _canonical_sha(records)
        or item.get("observed_execution_authority_sha256")
        != observed.get("observed_cloud_run_execution_sha256")
        or observed.get("schema_version") != OBSERVED_CLOUD_RUN_EXECUTION_SCHEMA
        or observed.get("evidence_semantics")
        != "exact-opened-cloud-run-v2-plus-kernel-observation-not-provider-attestation"
        or source_identity["bytes"] > MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES
        or observed.get("dispatcher_command_sha256")
        != _canonical_sha(observed_command)
        or observed.get("dispatcher_environment_sha256")
        != _canonical_sha(observed_environment)
        or observed.get("dispatcher_environment_semantics")
        != _COMPLETE_PROVIDER_JOB_ENVIRONMENT_SEMANTICS
        or observed.get("dispatcher_environment_complete_provider_spec") is not True
        or observed.get("dispatcher_environment_redirect_keys_absent") is not True
        or not _FORBIDDEN_IMAGE_LAUNCH_ENVIRONMENT_KEYS.isdisjoint(
            observed_environment
        )
        or observed.get("execution_task_template_overrides_present") is not False
        or observed.get("execution_command_override_present") is not False
        or observed.get("execution_environment_override_present") is not False
        or observed.get("effective_dispatcher_command_equals_job_spec") is not True
        or observed.get("effective_dispatcher_environment_equals_job_spec") is not True
        or observed.get("contract_id") != contract.CONTRACT_ID
        or observed.get("project_id") != FIXED_GCP_PROJECT
        or observed.get("location") != FIXED_CLOUD_RUN_LOCATION
        or observed.get("manifest_identity") != item.get("manifest_identity")
        or observed.get("task_manifest_sha256") != item.get("task_manifest_sha256")
        or observed.get("code_commit") != item.get("code_commit")
        or observed.get("image_digest") != item.get("image_digest")
        or observed.get("job_name") != item.get("reused_job_name")
        or observed.get("task_count") != layer.task_count
        or observed.get("parallelism") != layer.task_count
        or observed.get("maximum_task_retries") != 0
        or observed.get("terminal_states_sha256") != _canonical_sha(states)
        or execution_conditions
        != [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}]
        or observed.get("execution_conditions_sha256")
        != _canonical_sha(execution_conditions)
        or observed.get("execution_completed") is not True
        or observed.get("observation_source_exact_open_required") is not True
        or terminal_generation_scope != expected_terminal_generation_scope
        or observed.get("task_terminal_generation_resolution_scope")
        != terminal_generation_scope
        or item.get("task_terminal_generation_resolution_scope_sha256")
        != _canonical_sha(terminal_generation_scope)
        or observed.get("task_terminal_generation_resolution_scope_sha256")
        != item.get("task_terminal_generation_resolution_scope_sha256")
        or observed.get("provider_attestation_claimed") is not False
        or not resume_shape_valid
        or item.get("resume_authority_body_embedded") is not False
        or item.get("all_tasks_completed") is not True
        or item.get("bodies_embedded") is not False
        or item.get("external_attestation_claimed") is not False
        or item.get("one_reused_job") is not True
        or item.get("current_generation_resolution_allowed") is not True
        or item.get("current_generation_resolution_scope")
        != "host-finalizer-exact-manifest-task-terminal-evidence-uris-only"
        or item.get("listing_allowed") is not False
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("layer execution receipt fixed compact authority differs")
    for field in (
        "task_manifest_sha256", "design_sha256", "topology_sha256",
        "bootstrap_manifest_sha256", "pre_design_run_authorization_sha256",
        "observed_execution_authority_sha256", "task_records_sha256",
        "predecessor_layer_receipts_sha256",
        "task_terminal_generation_resolution_scope_sha256",
        "layer_execution_receipt_sha256",
    ):
        _sha(item.get(field), label=f"receipt {field}")
    for field in (
        "manifest_identity", "design_identity", "topology_identity",
        "bootstrap_manifest_identity", "pre_design_run_authorization_identity",
    ):
        _identity(item.get(field), label=f"receipt {field}")
    return item


def publish_create_once_or_exact_prior_v1(
    *, uri: str, value: object, prior_identity: object | None,
    publish_create_once: CreateOnce, read_exact: ReadExact,
    maximum_bytes: int,
) -> dict[str, object]:
    """Create once, or exact-resume only; a prior never falls through to create."""
    target = _string(uri, label="immutable publication URI")
    ceiling = _integer(
        maximum_bytes, label="immutable publication byte ceiling",
        maximum=200_000_000_000,
    )
    raw = value if type(value) is bytes else _canonical_bytes(value)
    if type(raw) is not bytes or not raw or len(raw) > ceiling:
        _fail("immutable publication bytes exceed their ceiling")
    prior = _optional_identity(prior_identity, label="immutable prior identity")
    if prior is not None:
        if (
            prior["uri"] != target
            or prior["bytes"] != len(raw)
            or prior["sha256"] != sha256(raw).hexdigest()
        ):
            _fail("immutable prior identity metadata differs before exact read")
        reopened = read_exact(prior)
        if type(reopened) is not bytes or reopened != raw:
            _fail("immutable exact-prior body differs")
        return prior
    returned = _identity(
        publish_create_once(target, raw), label="immutable created identity"
    )
    if (
        returned["uri"] != target
        or returned["bytes"] != len(raw)
        or returned["sha256"] != sha256(raw).hexdigest()
    ):
        _fail("immutable created identity differs")
    reopened = read_exact(returned)
    if type(reopened) is not bytes or reopened != raw:
        _fail("immutable created generation exact reopen differs")
    return returned


def validate_layer_execution_receipt_authority_v1(
    value: object, *, manifest: object, manifest_identity: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open every compact terminal/source before receipt publication."""
    receipt = validate_layer_execution_receipt_v1(value)
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity,
        label="layer receipt authority manifest",
    )
    if (
        receipt["manifest_identity"] != identity
        or receipt["task_manifest_sha256"]
        != retained_manifest["task_manifest_sha256"]
        or receipt["layer_id"] != retained_manifest["layer_id"]
    ):
        _fail("layer receipt authority manifest/layer differs")
    terminal_records: list[dict[str, object]] = []
    for index, compact in enumerate(receipt["task_records"]):
        evidence, evidence_identity = _read_json_exact(
            compact["task_terminal_evidence_identity"],
            read_exact=read_exact,
            label=f"layer receipt task[{index}] terminal evidence",
            maximum_bytes=MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES,
        )
        terminal_records.append({
            "identity": evidence_identity,
            "evidence": evidence,
        })
    rebuilt = build_layer_execution_receipt_v1(
        manifest=retained_manifest,
        manifest_identity=identity,
        observed_execution_authority=receipt["observed_execution_authority"],
        task_terminal_records=terminal_records,
        read_exact=read_exact,
    )
    if _canonical_bytes(receipt) != _canonical_bytes(rebuilt):
        _fail("layer receipt full exact authority replay differs")
    return rebuilt


def publish_cloud_run_execution_observation_source_v1(
    source_value: object, *, manifest: object, manifest_identity: object,
    task_terminal_records: object, prior_identity: object | None,
    publish_create_once: CreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    retained_manifest = validate_task_manifest_v1(manifest)
    identity = _bind_body(
        retained_manifest, manifest_identity,
        label="observation source publication manifest",
    )
    source = validate_cloud_run_execution_observation_source_v1(
        source_value,
        manifest=retained_manifest,
        manifest_identity=identity,
        task_terminal_records=task_terminal_records,
    )
    uri = _layer_descriptor(
        str(retained_manifest["output_prefix"]),
        str(retained_manifest["layer_id"]),
    )["cloud_run_observation_source_uri"]
    return publish_create_once_or_exact_prior_v1(
        uri=str(uri),
        value=source,
        prior_identity=prior_identity,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        maximum_bytes=MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES,
    )


def publish_task_terminal_evidence_v1(
    evidence_value: object, *, manifest: object,
    prior_identity: object | None, publish_create_once: CreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    manifest_value = validate_task_manifest_v1(manifest)
    evidence = validate_task_terminal_evidence_v1(
        evidence_value,
        manifest=manifest_value,
        manifest_identity=evidence_value.get("manifest_identity")
        if isinstance(evidence_value, Mapping) else None,
    )
    task = manifest_value["task_bindings"][int(evidence["task_index"])]
    supplied_prior = _optional_identity(
        prior_identity, label="task terminal supplied prior"
    )
    if supplied_prior is not None:
        _fail("task terminal recovery is disabled in the pre-output release")
    return publish_create_once_or_exact_prior_v1(
        uri=str(task["task_terminal_evidence_uri"]),
        value=evidence,
        prior_identity=None,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        maximum_bytes=MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES,
    )


def publish_layer_execution_receipt_v1(
    receipt_value: object, *, output_prefix: str, manifest: object,
    manifest_identity: object,
    prior_identity: object | None, publish_create_once: CreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    receipt = validate_layer_execution_receipt_authority_v1(
        receipt_value,
        manifest=manifest,
        manifest_identity=manifest_identity,
        read_exact=read_exact,
    )
    expected_uri = _layer_descriptor(
        output_prefix, str(receipt["layer_id"])
    )["layer_execution_receipt_uri"]
    return publish_create_once_or_exact_prior_v1(
        uri=str(expected_uri), value=receipt, prior_identity=prior_identity,
        publish_create_once=publish_create_once, read_exact=read_exact,
        maximum_bytes=MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
    )


def publish_task_manifest_v1(
    manifest_value: object, *, prior_identity: object | None,
    publish_create_once: CreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    manifest = validate_task_manifest_v1(manifest_value)
    return publish_create_once_or_exact_prior_v1(
        uri=str(manifest["manifest_uri"]),
        value=manifest,
        prior_identity=prior_identity,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )


__all__ = [
    "CHILD_COMMAND_HASH_ENV",
    "CHILD_LAYER_ID_ENV",
    "CHILD_MANIFEST_IDENTITY_ENV",
    "CHILD_MANIFEST_SELF_HASH_ENV",
    "CHILD_OUTPUTS_HASH_ENV",
    "CHILD_REQUEST_HASH_ENV",
    "CHILD_TASK_BINDING_EVIDENCE_SCHEMA",
    "CHILD_TASK_BINDING_HASH_ENV",
    "CHILD_TASK_INDEX_ENV",
    "CorpusR6CurrentBankCrossedScreenTaskManifestV1Error",
    "ABSENT_RESUME_AUTHORITY_ENV_VALUE",
    "DISPATCH_MANIFEST_IDENTITY_ENV",
    "DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV",
    "DISPATCHER_RUNTIME_EVIDENCE_SCHEMA",
    "EVALUATOR_REQUEST_SCHEMA",
    "FIXED_CLOUD_RUN_CPU_LIMIT",
    "FIXED_CLOUD_RUN_LOCATION",
    "FIXED_CLOUD_RUN_MEMORY_LIMIT",
    "FIXED_GCP_PROJECT",
    "FIXED_STORAGE_ENDPOINT",
    "LAYER_EXECUTION_RECEIPT_SCHEMA",
    "MAXIMUM_AUTHORIZATION_BYTES",
    "MAXIMUM_BOOTSTRAP_MANIFEST_BYTES",
    "MAXIMUM_DESIGN_BYTES",
    "MAXIMUM_DISPATCHER_EXACT_IDENTITY_PROOFS",
    "MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES",
    "MAXIMUM_DISPATCHER_WALL_SECONDS",
    "MAXIMUM_IDENTITY_ENV_BYTES",
    "MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES",
    "MAXIMUM_MANIFEST_BYTES",
    "MAXIMUM_CLOUD_RUN_OBSERVATION_SOURCE_BYTES",
    "MAXIMUM_PROCESS_BUDGET_BYTES",
    "MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES",
    "MAXIMUM_TOPOLOGY_BYTES",
    "OBSERVED_CLOUD_RUN_EXECUTION_SCHEMA",
    "CLOUD_RUN_EXECUTION_OBSERVATION_SOURCE_SCHEMA",
    "PRE_DESIGN_RUN_AUTHORIZATION_SCHEMA",
    "PROJECTION_TASK_REQUEST_SCHEMA",
    "PUBLISHER_REQUEST_SCHEMA",
    "SELECTION_ASSEMBLER_REQUEST_SCHEMA",
    "TASK_MANIFEST_SCHEMA",
    "TASK_TERMINAL_EVIDENCE_SCHEMA",
    "build_layer_execution_receipt_v1",
    "build_observed_cloud_run_execution_authority_v1",
    "build_dispatcher_runtime_evidence_v1",
    "build_evaluation_task_request_v1",
    "build_pre_design_run_authorization_v1",
    "build_projection_task_request_v1",
    "build_publisher_task_request_v1",
    "build_selection_task_request_v1",
    "build_task_manifest_v1",
    "build_task_terminal_evidence_v1",
    "canonical_bootstrap_process_specs_v1",
    "canonical_dispatcher_process_spec_v1",
    "child_task_binding_environment_v1",
    "image_entrypoint_authority_v1",
    "layer_registry_v1",
    "parse_child_task_binding_environment_v1",
    "pre_design_run_authorization_uri_v1",
    "publish_create_once_or_exact_prior_v1",
    "publish_cloud_run_execution_observation_source_v1",
    "publish_layer_execution_receipt_v1",
    "publish_task_manifest_v1",
    "publish_task_terminal_evidence_v1",
    "render_child_command_v1",
    "reopen_child_task_binding_v1",
    "reopen_observed_cloud_run_execution_authority_v1",
    "reopen_task_manifest_authority_v1",
    "strict_json_v1",
    "validate_child_task_binding_environment_v1",
    "validate_child_task_binding_evidence_v1",
    "validate_child_task_binding_v1",
    "validate_cloud_run_execution_observation_source_v1",
    "validate_dispatcher_runtime_evidence_v1",
    "validate_layer_execution_receipt_v1",
    "validate_layer_execution_receipt_authority_v1",
    "validate_observed_cloud_run_execution_authority_v1",
    "validate_pre_design_run_authorization_authority_v1",
    "validate_pre_design_run_authorization_v1",
    "validate_projection_task_request_v1",
    "validate_task_manifest_authority_v1",
    "validate_task_manifest_v1",
    "validate_task_terminal_evidence_v1",
]
