"""No-world-artifact assembler for the current-bank crossed screen.

This module deliberately has no dependency on the executable selection
implementation.  It owns the canonical worker/request envelopes, validates
five independently produced fold envelopes against their predeclared process
budgets, and publishes exactly one immutable per-slate selection receipt.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)


FOLD_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-selection-fold-worker-request/v1"
)
FOLD_CHILD_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-selection-fold-child-envelope/v1"
)
ASSEMBLER_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-selection-slate-assembler-request/v1"
)
ASSEMBLER_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-selection-slate-assembler-envelope/v1"
)
OBSERVED_RUNTIME_SCHEMA: Final = (
    "corpus-r6-current-bank-observed-process-runtime/v1"
)
PHASE_CHILD_LATTICE_SCHEMA: Final = (
    "corpus-r6-current-bank-phase-child-execution-lattice/v1"
)
FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
_BROKER_SCRIPT_BASENAME: Final = (
    "run_corpus_r6_current_bank_crossed_screen_selection_v1.py"
)
_MATRIX_ENTRYPOINT_BASENAME: Final = (
    "corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1.py"
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
    "R6_WORKER_COMMAND",
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[
    [str, bytes, Mapping[str, object] | None], Mapping[str, object]
]
SpawnChild = Callable[[Mapping[str, object], int], Mapping[str, object]]


class CorpusR6CurrentBankSelectionAssemblerV1Error(ValueError):
    """The isolated-fold or no-artifact assembly boundary failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectionAssemblerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a nonnegative integer")
    return value


def _sha(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _SHA256.fullmatch(text) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return text


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    if value.get(field) != contract.canonical_sha256_v1(
        {key: item for key, item in value.items() if key != field}
    ):
        _fail(f"{label} self hash differs")


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = contract.canonical_sha256_v1(result)
    return result


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc


def _selection_receipt_byte_ceiling(phase: str) -> int:
    if phase == contract.BROAD_SCREEN_PHASE:
        return contract.BROAD_SELECTION_RECEIPT_MAX_BYTES
    if phase == contract.CONFIRMATION_PHASE:
        return contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES
    _fail("selection receipt phase differs")


def _bind(
    body: Mapping[str, object], identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            body, identity, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if not isinstance(raw, bytes):
        _fail(f"{label} exact reader must return bytes")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except CorpusR6CurrentBankSelectionAssemblerV1Error:
        raise
    except Exception as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    return _mapping(value, label=label)


def _read_identity_bytes(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        not isinstance(raw, bytes)
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} bytes differ from exact identity")
    return raw, identity


def _read_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_identity_bytes(
        identity_value, read_exact=read_exact, label=label
    )
    body = _strict_json(raw, label=label)
    _bind(body, identity, label=label)
    return body, identity


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def _entrypoint_sha256_v1(path: str) -> str:
    target = Path(path)
    if not target.is_absolute() or not target.is_file():
        _fail("canonical entrypoint is absent or not absolute")
    return sha256(target.read_bytes()).hexdigest()


def canonical_fold_broker_command_v1() -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str((_repository_root_v1() / "scripts" / _BROKER_SCRIPT_BASENAME).resolve()),
        "fold-broker",
    ]


def canonical_slate_assembler_command_v1() -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str((_repository_root_v1() / "scripts" / _BROKER_SCRIPT_BASENAME).resolve()),
        "slate-assembler",
    ]


def canonical_matrix_selector_command_v1() -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str((Path(__file__).resolve().parent / _MATRIX_ENTRYPOINT_BASENAME).resolve()),
        "matrix-selector",
    ]


def _canonical_command_for_mode_v1(mode: str) -> list[str]:
    if mode == "fold-broker":
        return canonical_fold_broker_command_v1()
    if mode == "slate-assembler":
        return canonical_slate_assembler_command_v1()
    if mode == "matrix-selector":
        return canonical_matrix_selector_command_v1()
    _fail("runtime mode differs")


def canonical_fold_process_chain_v1() -> list[dict[str, object]]:
    commands = (
        ("artifact-broker", canonical_fold_broker_command_v1()),
        ("matrix-selector", canonical_matrix_selector_command_v1()),
    )
    return [
        {
            "component_role": component_role,
            "command": command,
            "entrypoint_path": command[1],
            "entrypoint_sha256": _entrypoint_sha256_v1(command[1]),
        }
        for component_role, command in commands
    ]


def _canonical_single_process_chain_v1(mode: str) -> list[dict[str, object]]:
    command = _canonical_command_for_mode_v1(mode)
    return [{
        "component_role": "main",
        "command": command,
        "entrypoint_path": command[1],
        "entrypoint_sha256": _entrypoint_sha256_v1(command[1]),
    }]


def _bootstrap_process_chain_v1(
    manifest: Mapping[str, object], *, process_role: str,
) -> list[dict[str, object]]:
    matches = [
        _mapping(row, label=f"bootstrap {process_role} spec")
        for row in _sequence(
            manifest.get("process_specs"), label="bootstrap process specs"
        )
        if isinstance(row, Mapping) and row.get("process_role") == process_role
    ]
    if len(matches) != 1:
        _fail(f"bootstrap manifest {process_role} spec differs")
    return [
        _mapping(row, label=f"bootstrap {process_role} process-chain component")
        for row in _sequence(
            matches[0].get("process_chain"),
            label=f"bootstrap {process_role} process chain",
        )
    ]


def validate_execution_environment_v1(
    environ_value: Mapping[str, str], *, mode: str,
) -> dict[str, object]:
    """Reject semantic mode/project/code/endpoint redirects before any client."""
    environment = dict(environ_value)
    _canonical_command_for_mode_v1(mode)
    for key in _REDIRECT_ENV_KEYS:
        if environment.get(key):
            _fail(f"redirect environment {key} is forbidden")
    project_values = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    if project_values != {FIXED_GCP_PROJECT}:
        _fail("observed execution project differs from fixed project")
    code_commit = environment.get("CODE_SHA", "")
    image_digest = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    task_index_text = environment.get("CLOUD_RUN_TASK_INDEX", "")
    process_ordinal_text = environment.get("R6_SELECTOR_PROCESS_ORDINAL", "")
    if (
        _COMMIT.fullmatch(code_commit) is None
        or not image_digest.startswith("sha256:")
        or _SHA256.fullmatch(image_digest[7:]) is None
        or not task_index_text.isdecimal()
        or not process_ordinal_text.isdecimal()
    ):
        _fail("observed runtime commit/image/task/process environment differs")
    for key in ("CLOUD_RUN_JOB", "CLOUD_RUN_EXECUTION"):
        if not environment.get(key):
            _fail(f"observed runtime {key} is absent")
    return {
        "project_id": FIXED_GCP_PROJECT,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "job_name": environment["CLOUD_RUN_JOB"],
        "execution_id": environment["CLOUD_RUN_EXECUTION"],
        "task_index": int(task_index_text),
        "process_ordinal": int(process_ordinal_text),
        "mode": mode,
        "redirect_environment_present": False,
        "storage_endpoint": "https://storage.googleapis.com",
        "evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
    }


def derive_observed_runtime_evidence_v1(
    *, mode: str, process_ordinal: int, environ: Mapping[str, str],
    argv: object, pid: int, parent_pid: int,
) -> dict[str, object]:
    environment = validate_execution_environment_v1(environ, mode=mode)
    process = _integer(process_ordinal, label="observed process ordinal")
    if environment["process_ordinal"] != process:
        _fail("observed process ordinal differs from environment")
    command = [
        _string(value, label=f"observed command[{index}]")
        for index, value in enumerate(_sequence(argv, label="observed command"))
    ]
    canonical = _canonical_command_for_mode_v1(mode)
    if command != canonical:
        _fail("observed process command differs from canonical entrypoint")
    entrypoint_sha = _entrypoint_sha256_v1(canonical[1])
    body = {
        "schema_version": OBSERVED_RUNTIME_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        **environment,
        "pid": _integer(pid, label="observed pid"),
        "parent_pid": _integer(parent_pid, label="observed parent pid"),
        "python_executable": canonical[0],
        "python_version": sys.version.split()[0],
        "entrypoint_path": canonical[1],
        "entrypoint_sha256": entrypoint_sha,
        "command": canonical,
        "command_sha256": contract.canonical_sha256_v1({
            "command": canonical,
            "entrypoint_sha256": entrypoint_sha,
        }),
    }
    return _with_hash(body, field="runtime_evidence_sha256")


def validate_observed_runtime_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="observed runtime evidence")
    if set(item) != {
        "schema_version", "contract_id", "project_id", "code_commit",
        "image_digest", "job_name", "execution_id", "task_index",
        "process_ordinal", "mode", "redirect_environment_present",
        "storage_endpoint", "evidence_strength",
        "outer_launch_authority_binding_required", "pid", "parent_pid",
        "python_executable", "python_version", "entrypoint_path",
        "entrypoint_sha256", "command", "command_sha256",
        "runtime_evidence_sha256",
    }:
        _fail("observed runtime evidence fields differ")
    _self_hash(item, field="runtime_evidence_sha256", label="runtime evidence")
    mode = _string(item.get("mode"), label="runtime mode")
    command = _canonical_command_for_mode_v1(mode)
    if (
        item.get("schema_version") != OBSERVED_RUNTIME_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("project_id") != FIXED_GCP_PROJECT
        or item.get("storage_endpoint") != "https://storage.googleapis.com"
        or item.get("evidence_strength")
        != "process-environment-observation-only"
        or item.get("outer_launch_authority_binding_required") is not True
        or item.get("redirect_environment_present") is not False
        or item.get("command") != command
        or item.get("python_executable") != command[0]
        or item.get("entrypoint_path") != command[1]
        or item.get("entrypoint_sha256") != _entrypoint_sha256_v1(command[1])
        or item.get("command_sha256") != contract.canonical_sha256_v1({
            "command": command,
            "entrypoint_sha256": item.get("entrypoint_sha256"),
        })
        or _COMMIT.fullmatch(str(item.get("code_commit", ""))) is None
        or not str(item.get("image_digest", "")).startswith("sha256:")
        or _SHA256.fullmatch(str(item.get("image_digest", ""))[7:]) is None
    ):
        _fail("observed runtime evidence fixed binding differs")
    for field in ("task_index", "process_ordinal", "pid", "parent_pid"):
        _integer(item.get(field), label=f"runtime {field}")
    for field in ("job_name", "execution_id", "python_version"):
        _string(item.get(field), label=f"runtime {field}")
    return item


# Backwards-incompatible by design: commands and runtimes are now observed,
# never supplied by a worker request.


def build_fold_worker_request_v1(
    *,
    phase: str,
    source_ordinal: int,
    fold_ordinal: int,
    design_identity: object,
    topology_identity: object,
    projection_bundle_identity: object,
    process_budget_identity: object,
    nomination_identity: object | None = None,
) -> dict[str, object]:
    retained_phase = _string(phase, label="worker phase")
    source = _integer(source_ordinal, label="worker source ordinal")
    fold = _integer(fold_ordinal, label="worker fold ordinal")
    if source >= contract.PANEL_SLATE_COUNT or fold >= contract.FOLDS_PER_SLATE:
        _fail("worker source/fold ordinal differs")
    if retained_phase == contract.BROAD_SCREEN_PHASE:
        if nomination_identity is not None:
            _fail("broad worker request cannot accept nomination authority")
        nomination = None
    elif retained_phase == contract.CONFIRMATION_PHASE:
        if nomination_identity is None:
            _fail("confirmation worker request requires nomination authority")
        nomination = _identity(nomination_identity, label="nomination identity")
    else:
        _fail("worker phase differs")
    process_ordinal = source * contract.FOLDS_PER_SLATE + fold
    body = {
        "schema_version": FOLD_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": source,
        "fold_ordinal": fold,
        "process_ordinal": process_ordinal,
        "design_identity": _identity(design_identity, label="design identity"),
        "topology_identity": _identity(
            topology_identity, label="topology identity"
        ),
        "projection_bundle_identity": _identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="process budget identity"
        ),
        "nomination_identity": nomination,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="worker_request_sha256")


def validate_fold_worker_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="fold worker request")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "fold_ordinal", "process_ordinal", "design_identity",
        "topology_identity", "projection_bundle_identity",
        "process_budget_identity", "nomination_identity",
        "policy", "worker_request_sha256",
    }:
        _fail("fold worker request fields differ")
    _self_hash(item, field="worker_request_sha256", label="fold worker request")
    expected = build_fold_worker_request_v1(
        phase=item.get("phase"),
        source_ordinal=item.get("source_ordinal"),
        fold_ordinal=item.get("fold_ordinal"),
        design_identity=item.get("design_identity"),
        topology_identity=item.get("topology_identity"),
        projection_bundle_identity=item.get("projection_bundle_identity"),
        process_budget_identity=item.get("process_budget_identity"),
        nomination_identity=item.get("nomination_identity"),
    )
    if contract.canonical_json_bytes_v1(item) != contract.canonical_json_bytes_v1(expected):
        _fail("fold worker request canonical replay differs")
    return expected


def _read_row(
    *, ordinal: int, channel: str, role: str, identity: object,
) -> dict[str, object]:
    if channel not in {"bootstrap-authority", "process-budget"}:
        _fail("read ledger channel differs")
    return {
        "ordinal": _integer(ordinal, label="read ordinal"),
        "channel": channel,
        "role": _string(role, label="read role"),
        "identity": _identity(identity, label=f"{role} identity"),
    }


def expected_worker_read_ledger_v1(
    *, request: object, process_budget: object,
) -> list[dict[str, object]]:
    worker = validate_fold_worker_request_v1(request)
    try:
        budget = contract.validate_process_budget_v1(process_budget)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    roles = {
        str(row["role"]): _identity(
            row["identity"], label=f"budget {row['role']} identity"
        )
        for row in budget["read_allowlist"]
    }
    expected_budget_roles = [
        "projection-bundle", "later-source",
        *[
            f"training-world-{block}"
            for block in contract.WORLD_BLOCKS
            if block != contract.WORLD_BLOCKS[int(worker["fold_ordinal"])]
        ],
    ]
    if worker["phase"] == contract.CONFIRMATION_PHASE:
        expected_budget_roles.append("nomination")
    if list(roles) != expected_budget_roles:
        _fail("worker process-budget read roles differ")
    order: list[tuple[str, str, object]] = [
        ("bootstrap-authority", "design", worker["design_identity"]),
        ("bootstrap-authority", "topology", worker["topology_identity"]),
        ("process-budget", "projection-bundle", roles["projection-bundle"]),
    ]
    if worker["phase"] == contract.CONFIRMATION_PHASE:
        order.append(("process-budget", "nomination", roles["nomination"]))
    order.append((
        "bootstrap-authority", "process-budget",
        worker["process_budget_identity"],
    ))
    order.append(("process-budget", "later-source", roles["later-source"]))
    order.extend(
        ("process-budget", role, roles[role])
        for role in expected_budget_roles
        if role.startswith("training-world-")
    )
    return [
        _read_row(ordinal=index, channel=channel, role=role, identity=identity)
        for index, (channel, role, identity) in enumerate(order)
    ]


def build_fold_child_envelope_v1(
    *,
    request: object,
    process_budget: object,
    read_ledger: object,
    selection_fold_receipt: object,
    broker_runtime_evidence: object,
    matrix_runtime_evidence: object,
    matrix_capability_sha256: str,
    matrix_response_sha256: str,
    matrix_response_bytes: int,
    bootstrap_manifest_identity: object,
    bootstrap_manifest_sha256: str,
    bootstrap_process_chain: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    worker = validate_fold_worker_request_v1(request)
    try:
        budget = contract.validate_process_budget_v1(process_budget)
        receipt = _mapping(
            selection_fold_receipt, label="selection fold receipt"
        )
        contract.validate_policy_block_v1(
            receipt.get("policy"), label="selection fold receipt"
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    broker_runtime = validate_observed_runtime_evidence_v1(
        broker_runtime_evidence
    )
    matrix_runtime = validate_observed_runtime_evidence_v1(
        matrix_runtime_evidence
    )
    expected_ledger = expected_worker_read_ledger_v1(
        request=worker, process_budget=budget
    )
    ledger = [
        _mapping(row, label=f"child read ledger[{index}]")
        for index, row in enumerate(_sequence(read_ledger, label="child read ledger"))
    ]
    if ledger != expected_ledger:
        _fail("child read ledger differs from exact worker budget")
    if (
        budget["phase"] != worker["phase"]
        or budget["source_ordinal"] != worker["source_ordinal"]
        or budget["process_ordinal"] != worker["process_ordinal"]
        or receipt.get("phase") != worker["phase"]
        or receipt.get("source_ordinal") != worker["source_ordinal"]
        or receipt.get("fold_ordinal") != worker["fold_ordinal"]
        or receipt.get("selector_process_ordinal") != worker["process_ordinal"]
        or receipt.get("cell_count") != budget["compute_fit_precharge"]
        or broker_runtime["mode"] != "fold-broker"
        or matrix_runtime["mode"] != "matrix-selector"
        or broker_runtime["process_ordinal"] != worker["process_ordinal"]
        or matrix_runtime["process_ordinal"] != worker["process_ordinal"]
        or broker_runtime["code_commit"] != matrix_runtime["code_commit"]
        or broker_runtime["image_digest"] != matrix_runtime["image_digest"]
    ):
        _fail("child phase/source/process/fit binding differs")
    training_roles = [
        row["role"] for row in ledger if str(row["role"]).startswith("training-world-")
    ]
    heldout_role = f"training-world-{contract.WORLD_BLOCKS[int(worker['fold_ordinal'])]}"
    if len(training_roles) != 4 or heldout_role in training_roles:
        _fail("child held-out artifact entered its training read ledger")
    response_bytes = _integer(
        matrix_response_bytes, label="matrix response bytes"
    )
    child_ceiling = int(budget["child_output_byte_ceiling"])
    if response_bytes < 1 or response_bytes > child_ceiling:
        _fail("matrix response exceeds child byte ceiling")
    artifact_reads = [
        row for row in ledger if str(row["role"]).startswith("training-world-")
    ]
    process_chain = [
        _mapping(row, label=f"bootstrap process chain[{index}]")
        for index, row in enumerate(
            _sequence(bootstrap_process_chain, label="bootstrap process chain")
        )
    ]
    if process_chain != canonical_fold_process_chain_v1():
        _fail("bootstrap fold process chain differs from canonical executables")
    launch_authority = _identity(
        launch_intent_identity, label="child launch intent identity"
    )
    artifact_reads = [
        {**row, "ordinal": index}
        for index, row in enumerate(artifact_reads)
    ]
    evidence = {
        "schema_version": "corpus-r6-current-bank-child-execution-evidence/v1",
        "phase": worker["phase"],
        "source_ordinal": worker["source_ordinal"],
        "fold_ordinal": worker["fold_ordinal"],
        "heldout_block": contract.WORLD_BLOCKS[int(worker["fold_ordinal"])],
        "process_ordinal": worker["process_ordinal"],
        "logical_fold_process_count": 1,
        "os_process_count": 2,
        "ordered_process_chain": process_chain,
        "ordered_process_chain_sha256": contract.canonical_sha256_v1(
            process_chain
        ),
        "broker_command": broker_runtime["command"],
        "broker_entrypoint_sha256": broker_runtime["entrypoint_sha256"],
        "matrix_command": matrix_runtime["command"],
        "matrix_entrypoint_sha256": matrix_runtime["entrypoint_sha256"],
        "broker_runtime_evidence": broker_runtime,
        "broker_runtime_evidence_sha256": broker_runtime[
            "runtime_evidence_sha256"
        ],
        "matrix_runtime_evidence": matrix_runtime,
        "matrix_runtime_evidence_sha256": matrix_runtime[
            "runtime_evidence_sha256"
        ],
        "training_artifact_read_ledger": artifact_reads,
        "training_artifact_read_ledger_sha256": contract.canonical_sha256_v1(
            artifact_reads
        ),
        "training_artifact_read_count": len(artifact_reads),
        "bootstrap_manifest_identity": _identity(
            bootstrap_manifest_identity, label="bootstrap manifest identity"
        ),
        "bootstrap_manifest_sha256": _sha(
            bootstrap_manifest_sha256, label="bootstrap manifest SHA-256"
        ),
        "process_budget_identity": worker["process_budget_identity"],
        "launch_intent_identity": launch_authority,
        "fit_count": receipt["cell_count"],
        "matrix_capability_sha256": _sha(
            matrix_capability_sha256, label="matrix capability SHA-256"
        ),
        "matrix_response_sha256": _sha(
            matrix_response_sha256, label="matrix response SHA-256"
        ),
        "matrix_response_bytes": response_bytes,
        "child_output_bytes": 0,
        "child_output_byte_ceiling": child_ceiling,
        "selection_fold_receipt_sha256": receipt[
            "selection_fold_receipt_sha256"
        ],
        "runtime_evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
        "outer_launch_authority_identity": launch_authority,
        "transport_capability_reached_matrix_process": False,
        "heldout_identity_reached_matrix_process": False,
    }
    evidence = _with_hash(evidence, field="child_execution_evidence_sha256")
    body = {
        "schema_version": FOLD_CHILD_ENVELOPE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": worker["phase"],
        "source_ordinal": worker["source_ordinal"],
        "fold_ordinal": worker["fold_ordinal"],
        "process_ordinal": worker["process_ordinal"],
        "worker_request_sha256": worker["worker_request_sha256"],
        "child_execution_evidence": evidence,
        "child_execution_evidence_sha256": evidence[
            "child_execution_evidence_sha256"
        ],
        "design_identity": worker["design_identity"],
        "topology_identity": worker["topology_identity"],
        "projection_bundle_identity": worker["projection_bundle_identity"],
        "process_budget_identity": worker["process_budget_identity"],
        "process_budget_sha256": budget["process_budget_sha256"],
        "read_ledger": ledger,
        "read_ledger_sha256": contract.canonical_sha256_v1(ledger),
        "read_object_count": len(ledger),
        "later_source_body_read_count": 1,
        "training_artifact_body_read_count": 4,
        "heldout_artifact_read_client_allowlisted": False,
        "heldout_artifact_read": False,
        "compute_fit_precharge": budget["compute_fit_precharge"],
        "observed_fit_count": receipt["cell_count"],
        "selection_fold_receipt": receipt,
        "selection_fold_receipt_sha256": receipt[
            "selection_fold_receipt_sha256"
        ],
        "stdout_payload_count": 1,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    # The exact canonical envelope length is self-bound. Length digit-width
    # stabilizes quickly; fail rather than publish a non-fixed-point value.
    for _ in range(8):
        candidate = _with_hash(body, field="child_envelope_sha256")
        observed = len(contract.canonical_json_bytes_v1(candidate))
        if observed == body["child_execution_evidence"]["child_output_bytes"]:
            if observed > child_ceiling:
                _fail("child envelope exceeds precharged stdout byte ceiling")
            return candidate
        evidence = dict(body["child_execution_evidence"])
        evidence["child_output_bytes"] = observed
        evidence = _with_hash(
            {key: value for key, value in evidence.items()
             if key != "child_execution_evidence_sha256"},
            field="child_execution_evidence_sha256",
        )
        body["child_execution_evidence"] = evidence
        body["child_execution_evidence_sha256"] = evidence[
            "child_execution_evidence_sha256"
        ]
    _fail("child envelope byte-count fixed point did not stabilize")


def validate_fold_child_envelope_v1(
    value: object, *, request: object, process_budget: object,
) -> dict[str, object]:
    item = _mapping(value, label="fold child envelope")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "fold_ordinal", "process_ordinal", "worker_request_sha256",
        "child_execution_evidence", "child_execution_evidence_sha256",
        "design_identity", "topology_identity",
        "projection_bundle_identity", "process_budget_identity",
        "process_budget_sha256", "read_ledger", "read_ledger_sha256",
        "read_object_count", "later_source_body_read_count",
        "training_artifact_body_read_count",
        "heldout_artifact_read_client_allowlisted", "heldout_artifact_read",
        "compute_fit_precharge", "observed_fit_count",
        "selection_fold_receipt", "selection_fold_receipt_sha256",
        "stdout_payload_count", "policy", "child_envelope_sha256",
    }:
        _fail("fold child envelope fields differ")
    _self_hash(item, field="child_envelope_sha256", label="fold child envelope")
    if (
        item.get("schema_version") != FOLD_CHILD_ENVELOPE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("later_source_body_read_count") != 1
        or item.get("training_artifact_body_read_count") != 4
        or item.get("heldout_artifact_read_client_allowlisted") is not False
        or item.get("heldout_artifact_read") is not False
        or item.get("stdout_payload_count") != 1
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("fold child envelope fixed policy differs")
    evidence = _mapping(
        item.get("child_execution_evidence"), label="child execution evidence"
    )
    _self_hash(
        evidence,
        field="child_execution_evidence_sha256",
        label="child execution evidence",
    )
    if (
        evidence.get("child_execution_evidence_sha256")
        != item.get("child_execution_evidence_sha256")
        or evidence.get("child_output_bytes")
        != len(contract.canonical_json_bytes_v1(item))
        or evidence.get("child_output_bytes", 0)
        > evidence.get("child_output_byte_ceiling", -1)
        or evidence.get("transport_capability_reached_matrix_process") is not False
        or evidence.get("heldout_identity_reached_matrix_process") is not False
        or evidence.get("runtime_evidence_strength")
        != "process-environment-observation-only"
        or evidence.get("outer_launch_authority_binding_required") is not True
        or evidence.get("outer_launch_authority_identity")
        != evidence.get("launch_intent_identity")
        or evidence.get("logical_fold_process_count") != 1
        or evidence.get("os_process_count") != 2
        or evidence.get("ordered_process_chain")
        != canonical_fold_process_chain_v1()
        or evidence.get("ordered_process_chain_sha256")
        != contract.canonical_sha256_v1(canonical_fold_process_chain_v1())
    ):
        _fail("child execution evidence byte/capability binding differs")
    expected = build_fold_child_envelope_v1(
        request=request,
        process_budget=process_budget,
        read_ledger=item.get("read_ledger"),
        selection_fold_receipt=item.get("selection_fold_receipt"),
        broker_runtime_evidence=evidence.get("broker_runtime_evidence"),
        matrix_runtime_evidence=evidence.get("matrix_runtime_evidence"),
        matrix_capability_sha256=evidence.get("matrix_capability_sha256"),
        matrix_response_sha256=evidence.get("matrix_response_sha256"),
        matrix_response_bytes=evidence.get("matrix_response_bytes"),
        bootstrap_manifest_identity=evidence.get("bootstrap_manifest_identity"),
        bootstrap_manifest_sha256=evidence.get("bootstrap_manifest_sha256"),
        bootstrap_process_chain=evidence.get("ordered_process_chain"),
        launch_intent_identity=evidence.get("launch_intent_identity"),
    )
    if contract.canonical_json_bytes_v1(item) != contract.canonical_json_bytes_v1(expected):
        _fail("fold child envelope canonical replay differs")
    return expected


def build_slate_assembler_request_v1(
    *,
    phase: str,
    source_ordinal: int,
    design_identity: object,
    topology_identity: object,
    projection_bundle_identity: object,
    assembler_process_budget_identity: object,
    worker_process_budget_identities: object,
    nomination_identity: object | None = None,
    prior_selection_receipt_identity: object | None = None,
) -> dict[str, object]:
    retained_phase = _string(phase, label="assembler phase")
    source = _integer(source_ordinal, label="assembler source ordinal")
    if source >= contract.PANEL_SLATE_COUNT:
        _fail("assembler source ordinal differs")
    budgets = [
        _identity(value, label=f"worker budget identity[{index}]")
        for index, value in enumerate(
            _sequence(
                worker_process_budget_identities,
                label="worker process budget identities",
            )
        )
    ]
    if len(budgets) != contract.FOLDS_PER_SLATE:
        _fail("assembler requires exactly five worker budgets")
    if retained_phase == contract.BROAD_SCREEN_PHASE:
        if nomination_identity is not None:
            _fail("broad assembler cannot accept nomination authority")
        nomination = None
    elif retained_phase == contract.CONFIRMATION_PHASE:
        if nomination_identity is None:
            _fail("confirmation assembler requires nomination authority")
        nomination = _identity(nomination_identity, label="nomination identity")
    else:
        _fail("assembler phase differs")
    prior = (
        None
        if prior_selection_receipt_identity is None
        else _identity(
            prior_selection_receipt_identity,
            label="prior selection receipt identity",
        )
    )
    if (
        prior is not None
        and int(prior["bytes"]) > _selection_receipt_byte_ceiling(retained_phase)
    ):
        _fail("prior selection receipt exceeds phase byte ceiling")
    body = {
        "schema_version": ASSEMBLER_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": source,
        "design_identity": _identity(design_identity, label="design identity"),
        "topology_identity": _identity(
            topology_identity, label="topology identity"
        ),
        "projection_bundle_identity": _identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "assembler_process_budget_identity": _identity(
            assembler_process_budget_identity,
            label="assembler process budget identity",
        ),
        "worker_process_budget_identities": budgets,
        "nomination_identity": nomination,
        "prior_selection_receipt_identity": prior,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="assembler_request_sha256")


def validate_slate_assembler_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="slate assembler request")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "design_identity", "topology_identity", "projection_bundle_identity",
        "assembler_process_budget_identity",
        "worker_process_budget_identities", "nomination_identity",
        "prior_selection_receipt_identity", "policy",
        "assembler_request_sha256",
    }:
        _fail("slate assembler request fields differ")
    _self_hash(item, field="assembler_request_sha256", label="assembler request")
    expected = build_slate_assembler_request_v1(
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
    if contract.canonical_json_bytes_v1(item) != contract.canonical_json_bytes_v1(expected):
        _fail("slate assembler request canonical replay differs")
    return expected


def _reopen_common_authorities(
    request: Mapping[str, object], *, read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    dict[str, object] | None, dict[str, object] | None,
    dict[str, object] | None,
    list[dict[str, object]],
]:
    ledger: list[dict[str, object]] = []

    def opened(role: str, identity: object) -> dict[str, object]:
        body, retained = _read_json(identity, read_exact=read_exact, label=role)
        ledger.append(_read_row(
            ordinal=len(ledger),
            channel=(
                "process-budget"
                if role in {"projection-bundle", "nomination"}
                else "bootstrap-authority"
            ),
            role=role, identity=retained,
        ))
        return body

    design_raw = opened("design", request["design_identity"])
    try:
        design = contract.validate_design_authority_v1(
            design_raw, publication_identity=request["design_identity"]
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    topology_raw = opened("topology", request["topology_identity"])
    try:
        topology = contract.validate_result_topology_v1(topology_raw)
        _bind(topology, request["topology_identity"], label="topology")
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    if design["topology"] != topology:
        _fail("reopened topology differs from topology-bearing design")
    bundle_raw = opened("projection-bundle", request["projection_bundle_identity"])
    try:
        bundle = contract.validate_projection_bundle_authority_v1(
            bundle_raw,
            publication_identity=request["projection_bundle_identity"],
            topology=topology,
            topology_identity=request["topology_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    nomination_publication: dict[str, object] | None = None
    nomination: dict[str, object] | None = None
    broad_authority: dict[str, object] | None = None
    if request["phase"] == contract.CONFIRMATION_PHASE:
        nomination_raw = opened("nomination", request["nomination_identity"])
        try:
            nomination_publication = (
                contract.validate_nomination_publication_authority_v1(
                    nomination_raw,
                    publication_identity=request["nomination_identity"],
                )
            )
            nomination = nomination_publication["nomination"]
            broad_authority = nomination_publication["broad_phase_authority"]
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    return (
        design, topology, bundle, nomination_publication, nomination,
        broad_authority, ledger,
    )


def _compile_budget(
    *,
    role: str,
    request: Mapping[str, object],
    topology: Mapping[str, object],
    bundle: Mapping[str, object],
    fold_ordinal: int | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "process_role": role,
        "projection_bundle": bundle,
        "projection_bundle_identity": request["projection_bundle_identity"],
        "topology": topology,
        "topology_identity": request["topology_identity"],
        "source_ordinal": request["source_ordinal"],
        "fold_ordinal": fold_ordinal,
    }
    if request["phase"] == contract.CONFIRMATION_PHASE:
        kwargs.update({
            "nomination_publication": request[
                "_reopened_nomination_publication"
            ],
            "nomination_publication_identity": request["nomination_identity"],
        })
    try:
        return contract.compile_process_budget_v1(**kwargs)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc


def _exact_budget(
    *,
    identity: object,
    expected: Mapping[str, object],
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, retained_identity = _read_json(identity, read_exact=read_exact, label=label)
    try:
        budget = contract.validate_process_budget_v1(raw)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    _bind(budget, retained_identity, label=label)
    if not retained_identity["uri"].startswith(contract.OUTPUT_NAMESPACE):
        _fail(f"{label} URI is outside the fixed output namespace")
    if contract.canonical_json_bytes_v1(budget) != contract.canonical_json_bytes_v1(expected):
        _fail(f"{label} differs from freshly compiled process budget")
    return budget, retained_identity


def run_slate_assembler_v1(
    request_value: object,
    *,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    assembler_runtime_evidence: object,
    spawn_child: SpawnChild | None = None,
    child_envelopes: object | None = None,
) -> dict[str, object]:
    """Validate/spawn five folds and create-once emit one slate receipt."""
    request = validate_slate_assembler_request_v1(request_value)
    observed_assembler_runtime = validate_observed_runtime_evidence_v1(
        assembler_runtime_evidence
    )
    if (
        observed_assembler_runtime["mode"] != "slate-assembler"
        or observed_assembler_runtime["process_ordinal"]
        != request["source_ordinal"]
    ):
        _fail("observed assembler runtime differs from source ordinal")
    if (spawn_child is None) == (child_envelopes is None):
        _fail("assembler requires exactly one child source: spawn or five envelopes")
    (
        design, topology, bundle, nomination_publication, nomination,
        embedded_broad_authority, ledger,
    ) = _reopen_common_authorities(request, read_exact=read_exact)
    bootstrap_manifest = _mapping(
        design.get("bootstrap_manifest"), label="design bootstrap manifest"
    )
    bootstrap_manifest_identity = _identity(
        design.get("bootstrap_manifest_identity"),
        label="design bootstrap manifest identity",
    )
    launch_intent_identity = _identity(
        bootstrap_manifest.get("run_identity"),
        label="bootstrap run/launch authorization",
    )
    internal_request = dict(request)
    internal_request["_reopened_nomination_publication"] = (
        nomination_publication
    )
    internal_request["_reopened_nomination"] = nomination
    internal_request["_embedded_broad_phase_authority"] = (
        embedded_broad_authority
    )
    assembler_role = (
        "broad-slate-assembler"
        if request["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-slate-assembler"
    )
    assembler_process_chain = _bootstrap_process_chain_v1(
        bootstrap_manifest, process_role=assembler_role
    )
    if (
        assembler_process_chain
        != _canonical_single_process_chain_v1("slate-assembler")
        or observed_assembler_runtime["code_commit"]
        != bootstrap_manifest["code_commit"]
        or observed_assembler_runtime["image_digest"]
        != bootstrap_manifest["image_digest"]
    ):
        _fail("assembler runtime differs from exact bootstrap manifest")
    expected_assembler_budget = _compile_budget(
        role=assembler_role,
        request=internal_request,
        topology=topology,
        bundle=bundle,
        fold_ordinal=None,
    )
    assembler_budget, assembler_budget_identity = _exact_budget(
        identity=request["assembler_process_budget_identity"],
        expected=expected_assembler_budget,
        read_exact=read_exact,
        label="assembler process budget",
    )
    ledger.append(_read_row(
        ordinal=len(ledger), channel="bootstrap-authority",
        role="assembler-process-budget", identity=assembler_budget_identity,
    ))
    fold_budgets: list[dict[str, object]] = []
    fold_requests: list[dict[str, object]] = []
    fold_role = (
        "broad-fold-selector"
        if request["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-fold-selector"
    )
    for fold in range(contract.FOLDS_PER_SLATE):
        expected_budget = _compile_budget(
            role=fold_role,
            request=internal_request,
            topology=topology,
            bundle=bundle,
            fold_ordinal=fold,
        )
        budget, budget_identity = _exact_budget(
            identity=request["worker_process_budget_identities"][fold],
            expected=expected_budget,
            read_exact=read_exact,
            label=f"fold-{fold} process budget",
        )
        ledger.append(_read_row(
            ordinal=len(ledger), channel="bootstrap-authority",
            role=f"fold-{fold}-process-budget", identity=budget_identity,
        ))
        fold_budgets.append(budget)
        fold_requests.append(build_fold_worker_request_v1(
            phase=request["phase"],
            source_ordinal=request["source_ordinal"],
            fold_ordinal=fold,
            design_identity=request["design_identity"],
            topology_identity=request["topology_identity"],
            projection_bundle_identity=request["projection_bundle_identity"],
            process_budget_identity=budget_identity,
            nomination_identity=request["nomination_identity"],
        ))
    if spawn_child is not None:
        raw_children = [
            spawn_child(
                child_request,
                int(fold_budgets[fold]["child_output_byte_ceiling"]),
            )
            for fold, child_request in enumerate(fold_requests)
        ]
    else:
        raw_children = _sequence(child_envelopes, label="child envelopes")
    if len(raw_children) != contract.FOLDS_PER_SLATE:
        _fail("assembler requires exactly five isolated child envelopes")
    children = [
        validate_fold_child_envelope_v1(
            raw_children[fold],
            request=fold_requests[fold],
            process_budget=fold_budgets[fold],
        )
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    if [child["fold_ordinal"] for child in children] != list(range(contract.FOLDS_PER_SLATE)):
        _fail("assembler child fold order differs")
    if len({child["child_envelope_sha256"] for child in children}) != contract.FOLDS_PER_SLATE:
        _fail("assembler child envelopes are not five distinct authorities")
    child_evidence = [child["child_execution_evidence"] for child in children]
    if (
        [row["heldout_block"] for row in child_evidence]
        != list(contract.WORLD_BLOCKS)
        or [row["process_ordinal"] for row in child_evidence]
        != [
            int(request["source_ordinal"]) * contract.FOLDS_PER_SLATE + fold
            for fold in range(contract.FOLDS_PER_SLATE)
        ]
        or len({
            (
                row["broker_runtime_evidence"]["execution_id"],
                row["broker_runtime_evidence"]["pid"],
                row["matrix_runtime_evidence"]["pid"],
            )
            for row in child_evidence
        }) != contract.FOLDS_PER_SLATE
    ):
        _fail("assembler five-child block/process/runtime lattice differs")
    if any(
        row["bootstrap_manifest_identity"] != bootstrap_manifest_identity
        or row["bootstrap_manifest_sha256"]
        != bootstrap_manifest["bootstrap_manifest_sha256"]
        or row["ordered_process_chain"] != canonical_fold_process_chain_v1()
        or row["broker_runtime_evidence"]["code_commit"]
        != bootstrap_manifest["code_commit"]
        or row["matrix_runtime_evidence"]["code_commit"]
        != bootstrap_manifest["code_commit"]
        or row["broker_runtime_evidence"]["image_digest"]
        != bootstrap_manifest["image_digest"]
        or row["matrix_runtime_evidence"]["image_digest"]
        != bootstrap_manifest["image_digest"]
        or row["launch_intent_identity"] != launch_intent_identity
        or row["outer_launch_authority_identity"]
        != launch_intent_identity
        for row in child_evidence
    ):
        _fail("child runtime/process chain differs from exact bootstrap manifest")
    try:
        receipt = contract.build_selection_receipt_v1(
            projection_bundle=bundle,
            projection_bundle_identity=request["projection_bundle_identity"],
            topology=topology,
            topology_identity=request["topology_identity"],
            phase=request["phase"],
            fold_receipts=[child["selection_fold_receipt"] for child in children],
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=bootstrap_manifest_identity,
            launch_intent_identity=launch_intent_identity,
            child_execution_evidence=child_evidence,
            nomination_publication=nomination_publication,
            nomination_publication_identity=request["nomination_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    if (
        receipt["fit_count"] != sum(child["observed_fit_count"] for child in children)
        or receipt["assembler_artifact_body_read_count"] != 0
        or receipt["assembler_selector_execution_count"] != 0
        or assembler_budget["compute_fit_precharge"] != 0
    ):
        _fail("assembled receipt count or no-artifact boundary differs")
    writes = assembler_budget["write_allowlist"]
    if len(writes) != 1:
        _fail("assembler budget does not authorize exactly one publication")
    write = writes[0]
    expected_receipt_ceiling = _selection_receipt_byte_ceiling(
        str(request["phase"])
    )
    if int(write["max_bytes"]) != expected_receipt_ceiling:
        _fail("assembler publication byte ceiling differs from phase contract")
    raw_receipt = contract.canonical_json_bytes_v1(receipt)
    if len(raw_receipt) > expected_receipt_ceiling:
        _fail("selection receipt exceeds precharged publication bytes")
    prior_identity = request["prior_selection_receipt_identity"]
    if prior_identity is not None and (
        prior_identity["uri"] != write["uri"]
        or prior_identity["bytes"] != len(raw_receipt)
        or prior_identity["sha256"] != sha256(raw_receipt).hexdigest()
    ):
        _fail("prior selection receipt URI/body hash/size differs")
    published_identity = _identity(
        publish_create_once(
            str(write["uri"]), raw_receipt, prior_identity
        ),
        label="selection receipt publication",
    )
    if (
        published_identity["uri"] != write["uri"]
        or published_identity["bytes"] != len(raw_receipt)
        or published_identity["sha256"] != sha256(raw_receipt).hexdigest()
    ):
        _fail("selection receipt create-once identity differs")
    reopened_raw, reopened_identity = _read_identity_bytes(
        published_identity,
        read_exact=read_exact,
        label="published selection receipt",
    )
    if reopened_raw != raw_receipt:
        _fail("published selection receipt bytes differ on exact reopen")
    try:
        contract.validate_selection_receipt_authority_v1(
            _strict_json(reopened_raw, label="published selection receipt"),
            publication_identity=reopened_identity,
            projection_bundle=bundle,
            projection_bundle_identity=request["projection_bundle_identity"],
            topology=topology,
            topology_identity=request["topology_identity"],
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=bootstrap_manifest_identity,
            launch_intent_identity=launch_intent_identity,
            nomination_publication=nomination_publication,
            nomination_publication_identity=request["nomination_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionAssemblerV1Error(str(exc)) from exc
    ledger.append(_read_row(
        ordinal=len(ledger), channel="bootstrap-authority",
        role="published-selection-receipt", identity=reopened_identity,
    ))
    child_envelope_sha256s = [
        child["child_envelope_sha256"] for child in children
    ]
    body = {
        "schema_version": ASSEMBLER_ENVELOPE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": request["phase"],
        "source_ordinal": request["source_ordinal"],
        "assembler_request_sha256": request["assembler_request_sha256"],
        "assembler_runtime_evidence": observed_assembler_runtime,
        "assembler_runtime_evidence_sha256": observed_assembler_runtime[
            "runtime_evidence_sha256"
        ],
        "runtime_evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
        "outer_launch_authority_identity": launch_intent_identity,
        "launch_intent_identity": launch_intent_identity,
        "bootstrap_manifest_identity": bootstrap_manifest_identity,
        "bootstrap_manifest_sha256": bootstrap_manifest[
            "bootstrap_manifest_sha256"
        ],
        "assembler_process_chain": assembler_process_chain,
        "assembler_process_chain_sha256": contract.canonical_sha256_v1(
            assembler_process_chain
        ),
        "assembler_process_budget_identity": assembler_budget_identity,
        "assembler_process_budget_sha256": assembler_budget[
            "process_budget_sha256"
        ],
        "child_envelope_sha256s": child_envelope_sha256s,
        "child_envelopes_sha256": contract.canonical_sha256_v1(
            child_envelope_sha256s
        ),
        "child_execution_evidence": child_evidence,
        "child_execution_evidence_sha256s": [
            row["child_execution_evidence_sha256"] for row in child_evidence
        ],
        "child_execution_evidence_set_sha256": contract.canonical_sha256_v1(
            child_evidence
        ),
        "child_process_count": len(children),
        "logical_fold_process_count": len(children),
        "child_os_process_count": sum(
            int(row["os_process_count"]) for row in child_evidence
        ),
        "phase_process_lattice_fragment": {
            "phase": request["phase"],
            "source_ordinal": request["source_ordinal"],
            "logical_fold_process_count": contract.FOLDS_PER_SLATE,
            "os_process_count": 2 * contract.FOLDS_PER_SLATE,
            "ordered_process_chain": canonical_fold_process_chain_v1(),
            "fold_ordinals": list(range(contract.FOLDS_PER_SLATE)),
            "heldout_blocks": list(contract.WORLD_BLOCKS),
            "process_ordinals": [
                row["process_ordinal"] for row in child_evidence
            ],
            "child_execution_evidence_sha256s": [
                row["child_execution_evidence_sha256"] for row in child_evidence
            ],
        },
        "child_fit_count": sum(child["observed_fit_count"] for child in children),
        "assembler_read_ledger": ledger,
        "assembler_read_ledger_sha256": contract.canonical_sha256_v1(ledger),
        "assembler_world_artifact_body_read_count": 0,
        "assembler_selection_algorithm_execution_count": 0,
        "publication_count": 1,
        "selection_receipt_identity": reopened_identity,
        "selection_receipt_sha256": receipt["selection_receipt_sha256"],
        "prior_selection_receipt_identity": prior_identity,
        "selection_receipt_publication_resumed": prior_identity is not None,
        "create_once_resume_exact_generation_proved": (
            prior_identity is None or reopened_identity == prior_identity
        ),
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="assembler_envelope_sha256")


def build_phase_child_lattice_v1(
    *, phase: str, assembler_envelopes: object,
) -> dict[str, object]:
    """Prove one phase contains exactly 54 x 5 = 270 distinct children."""
    retained_phase = _string(phase, label="phase child lattice phase")
    if retained_phase not in {
        contract.BROAD_SCREEN_PHASE, contract.CONFIRMATION_PHASE,
    }:
        _fail("phase child lattice phase differs")
    envelopes = [
        _mapping(value, label=f"assembler envelope[{index}]")
        for index, value in enumerate(
            _sequence(assembler_envelopes, label="assembler envelopes")
        )
    ]
    if len(envelopes) != contract.PANEL_SLATE_COUNT:
        _fail("phase child lattice requires exactly 54 slate envelopes")
    phase_launch_identity = _identity(
        envelopes[0].get("launch_intent_identity"),
        label="phase launch intent identity",
    )
    evidence: list[dict[str, object]] = []
    for source, envelope in enumerate(envelopes):
        _self_hash(
            envelope,
            field="assembler_envelope_sha256",
            label=f"assembler envelope[{source}]",
        )
        rows = [
            _mapping(value, label=f"child evidence[{source},{fold}]")
            for fold, value in enumerate(
                _sequence(
                    envelope.get("child_execution_evidence"),
                    label=f"assembler child evidence[{source}]",
                )
            )
        ]
        child_envelope_sha256s = [
            _sha(value, label=f"child envelope hash[{source},{fold}]")
            for fold, value in enumerate(
                _sequence(
                    envelope.get("child_envelope_sha256s"),
                    label=f"assembler child envelope hashes[{source}]",
                )
            )
        ]
        expected_ordinals = [
            source * contract.FOLDS_PER_SLATE + fold
            for fold in range(contract.FOLDS_PER_SLATE)
        ]
        if (
            envelope.get("phase") != retained_phase
            or envelope.get("source_ordinal") != source
            or envelope.get("child_process_count") != contract.FOLDS_PER_SLATE
            or envelope.get("logical_fold_process_count")
            != contract.FOLDS_PER_SLATE
            or envelope.get("child_os_process_count")
            != 2 * contract.FOLDS_PER_SLATE
            or envelope.get("runtime_evidence_strength")
            != "process-environment-observation-only"
            or envelope.get("outer_launch_authority_binding_required") is not True
            or envelope.get("outer_launch_authority_identity")
            != phase_launch_identity
            or envelope.get("launch_intent_identity") != phase_launch_identity
            or len(child_envelope_sha256s) != contract.FOLDS_PER_SLATE
            or len(set(child_envelope_sha256s)) != contract.FOLDS_PER_SLATE
            or envelope.get("child_envelopes_sha256")
            != contract.canonical_sha256_v1(child_envelope_sha256s)
            or len(rows) != contract.FOLDS_PER_SLATE
            or [row.get("fold_ordinal") for row in rows]
            != list(range(contract.FOLDS_PER_SLATE))
            or [row.get("heldout_block") for row in rows]
            != list(contract.WORLD_BLOCKS)
            or [row.get("process_ordinal") for row in rows]
            != expected_ordinals
            or envelope.get("child_execution_evidence_set_sha256")
            != contract.canonical_sha256_v1(rows)
        ):
            _fail("phase child lattice slate/fold/process binding differs")
        for row in rows:
            _self_hash(
                row,
                field="child_execution_evidence_sha256",
                label="phase child execution evidence",
            )
            if (
                row.get("runtime_evidence_strength")
                != "process-environment-observation-only"
                or row.get("outer_launch_authority_binding_required") is not True
                or row.get("outer_launch_authority_identity")
                != phase_launch_identity
                or row.get("launch_intent_identity") != phase_launch_identity
                or row.get("logical_fold_process_count") != 1
                or row.get("os_process_count") != 2
                or row.get("ordered_process_chain")
                != canonical_fold_process_chain_v1()
            ):
                _fail("phase child outer runtime binding hook differs")
            broker_runtime = validate_observed_runtime_evidence_v1(
                row.get("broker_runtime_evidence")
            )
            matrix_runtime = validate_observed_runtime_evidence_v1(
                row.get("matrix_runtime_evidence")
            )
            if (
                broker_runtime["mode"] != "fold-broker"
                or matrix_runtime["mode"] != "matrix-selector"
                or broker_runtime["process_ordinal"] != row["process_ordinal"]
                or matrix_runtime["process_ordinal"] != row["process_ordinal"]
            ):
                _fail("phase child two-process runtime lattice differs")
        evidence.extend(rows)
    process_ordinals = [int(row["process_ordinal"]) for row in evidence]
    evidence_hashes = [
        str(row["child_execution_evidence_sha256"]) for row in evidence
    ]
    broker_runtime_hashes = [
        str(row["broker_runtime_evidence_sha256"]) for row in evidence
    ]
    matrix_runtime_hashes = [
        str(row["matrix_runtime_evidence_sha256"]) for row in evidence
    ]
    if (
        process_ordinals != list(range(contract.FOLD_SELECTOR_SUBPROCESS_COUNT))
        or len(set(evidence_hashes)) != contract.FOLD_SELECTOR_SUBPROCESS_COUNT
    ):
        _fail("phase child lattice does not contain exact distinct 0..269")
    body = {
        "schema_version": PHASE_CHILD_LATTICE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "slate_count": contract.PANEL_SLATE_COUNT,
        "folds_per_slate": contract.FOLDS_PER_SLATE,
        "logical_fold_process_count": contract.FOLD_SELECTOR_SUBPROCESS_COUNT,
        "os_processes_per_logical_fold": 2,
        "os_process_count": 2 * contract.FOLD_SELECTOR_SUBPROCESS_COUNT,
        "process_ordinals": process_ordinals,
        "child_execution_evidence_sha256s": evidence_hashes,
        "child_execution_evidence_set_sha256": contract.canonical_sha256_v1(
            evidence
        ),
        "broker_runtime_evidence_sha256s": broker_runtime_hashes,
        "matrix_runtime_evidence_sha256s": matrix_runtime_hashes,
        "ordered_process_chain": canonical_fold_process_chain_v1(),
        "ordered_process_chain_sha256": contract.canonical_sha256_v1(
            canonical_fold_process_chain_v1()
        ),
        "complete_54_by_5_lattice": True,
        "runtime_evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
        "outer_launch_authority_identity": phase_launch_identity,
        "launch_intent_identity": phase_launch_identity,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="phase_child_lattice_sha256")


__all__ = [
    "ASSEMBLER_ENVELOPE_SCHEMA",
    "ASSEMBLER_REQUEST_SCHEMA",
    "FOLD_CHILD_ENVELOPE_SCHEMA",
    "FOLD_REQUEST_SCHEMA",
    "FIXED_GCP_PROJECT",
    "OBSERVED_RUNTIME_SCHEMA",
    "PHASE_CHILD_LATTICE_SCHEMA",
    "CorpusR6CurrentBankSelectionAssemblerV1Error",
    "build_fold_child_envelope_v1",
    "build_fold_worker_request_v1",
    "build_phase_child_lattice_v1",
    "build_slate_assembler_request_v1",
    "canonical_fold_broker_command_v1",
    "canonical_fold_process_chain_v1",
    "canonical_matrix_selector_command_v1",
    "canonical_slate_assembler_command_v1",
    "derive_observed_runtime_evidence_v1",
    "expected_worker_read_ledger_v1",
    "run_slate_assembler_v1",
    "validate_execution_environment_v1",
    "validate_fold_child_envelope_v1",
    "validate_fold_worker_request_v1",
    "validate_observed_runtime_evidence_v1",
    "validate_slate_assembler_request_v1",
]
