"""Immutable cloud task authority for the grouped selector successor.

The source broad-selection manifest is read-only input authority.  This
module registers a separate dispatcher and matrix child, publishes an exact
24-fit budget for every slate/fold, publishes one 120-fit outer budget per
slate, and defines the five-fold create-once result.  No object is compatible
with the frozen 64-fit control receipt or command.
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
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as child_runtime,
)


BOOTSTRAP_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-bootstrap/v1"
)
RUN_AUTHORIZATION_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-run-authorization/v1"
)
SLATE_PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-slate-process-budget/v1"
)
TASK_MANIFEST_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-task-manifest/v1"
)
TASK_BINDING_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-task-binding/v1"
)
SLATE_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-slate-result/v1"
)
TASK_RESULT_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-task-result-envelope/v1"
)
MATRIX_CHILD_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-matrix-child-request/v1"
)
DISPATCHER_RUNTIME_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-dispatcher-runtime/v1"
)

TASK_COUNT: Final = contract.PANEL_SLATE_COUNT
FOLD_COUNT: Final = contract.FOLDS_PER_SLATE
FITS_PER_FOLD: Final = adapter.EXACT_FIT_COUNT
FITS_PER_SLATE: Final = FOLD_COUNT * FITS_PER_FOLD
MAXIMUM_BOOTSTRAP_BYTES: Final = 256_000
MAXIMUM_TASK_MANIFEST_BYTES: Final = 16_000_000
MAXIMUM_SLATE_PROCESS_BUDGET_BYTES: Final = 2_000_000
MAXIMUM_SLATE_RESULT_BYTES: Final = (
    FOLD_COUNT * adapter.FOLD_RECEIPT_BYTE_CEILING + 2_000_000
)
MAXIMUM_TASK_RESULT_ENVELOPE_BYTES: Final = 256_000
TASK_TIMEOUT_SECONDS: Final = 7_200

FIXED_GCP_PROJECT: Final = source_manifest.FIXED_GCP_PROJECT
FIXED_STORAGE_ENDPOINT: Final = source_manifest.FIXED_STORAGE_ENDPOINT
DISPATCHER_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_current_bank_selector_successor_cloud_v1.py"
)
DISPATCHER_IMAGE_PATH: Final = f"/app/{DISPATCHER_RELATIVE_PATH}"
DISPATCHER_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    DISPATCHER_IMAGE_PATH,
)
MANIFEST_IDENTITY_ENV: Final = "R6_SUCCESSOR_TASK_MANIFEST_IDENTITY"
ENABLE_ENV: Final = "R6_SUCCESSOR_DISPATCH_ENABLE"

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_REDIRECT_ENV_KEYS: Final = frozenset({
    "CURL_CA_BUNDLE", "GCE_METADATA_HOST", "GCE_METADATA_IP",
    "GOOGLE_APPLICATION_CREDENTIALS", "LD_AUDIT", "LD_LIBRARY_PATH",
    "LD_PRELOAD", "PYTHONBREAKPOINT", "PYTHONHOME", "PYTHONINSPECT",
    "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE",
    "REQUESTS_CA_BUNDLE", "SSL_CERT_DIR", "SSL_CERT_FILE",
})

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]

_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "heldout_matrix_columns_exposed_to_child": False,
    "source_control_runtime_compatibility_claimed": False,
    "source_control_receipt_compatibility_claimed": False,
    "current_generation_scientific_input_lookup_allowed": False,
    "object_listing_allowed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
}


class CorpusR6CurrentBankSelectorSuccessorCloudV1Error(ValueError):
    """The grouped selector cloud authority failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = _hash(body)
    return body


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
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(str(exc)) from exc


def _bind(value: Mapping[str, object], identity: object, *, label: str) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            value, identity, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(str(exc)) from exc


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            f"{label} is not JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _read_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    return _strict_json(raw, label=label), identity


def _publish(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    raw = _canonical(value)
    if not raw or len(raw) > maximum_bytes:
        _fail("create-once object exceeds its exact byte ceiling")
    identity = _identity(
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


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _entrypoint_sha(relative_path: str) -> str:
    path = _repository_root() / relative_path
    if not path.is_file():
        _fail(f"registered entrypoint {relative_path!r} is absent")
    return sha256(path.read_bytes()).hexdigest()


def _safe_output_prefix(value: object) -> str:
    if type(value) is not str or not value.startswith(contract.OUTPUT_NAMESPACE):
        _fail("successor output prefix is outside the fixed namespace")
    if not value.endswith("/") or "?" in value or "#" in value or "//" in value[5:]:
        _fail("successor output prefix differs")
    if any(part in {"", ".", ".."} for part in value[5:-1].split("/")):
        _fail("successor output prefix path differs")
    return value


def dispatcher_process_spec_v1() -> dict[str, object]:
    entrypoint_sha = _entrypoint_sha(DISPATCHER_RELATIVE_PATH)
    command = list(DISPATCHER_COMMAND)
    return {
        "process_role": "grouped-successor-task-dispatcher",
        "entrypoint_path": DISPATCHER_IMAGE_PATH,
        "entrypoint_sha256": entrypoint_sha,
        "command": command,
        "command_sha256": _hash({
            "command": command, "entrypoint_sha256": entrypoint_sha
        }),
    }


def build_run_authorization_v1(
    *,
    source_task_manifest_identity: object,
    output_prefix: str,
    code_commit: str,
    image_digest: str,
    reused_job_name: str,
) -> dict[str, object]:
    prefix = _safe_output_prefix(output_prefix)
    if (
        _COMMIT_RE.fullmatch(str(code_commit)) is None
        or not str(image_digest).startswith("sha256:")
        or _SHA_RE.fullmatch(str(image_digest)[7:]) is None
        or type(reused_job_name) is not str
        or not reused_job_name
        or len(reused_job_name) > 63
        or re.fullmatch(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", reused_job_name)
        is None
    ):
        _fail("successor run authorization runtime/job binding differs")
    body = {
        "schema_version": RUN_AUTHORIZATION_SCHEMA,
        "source_task_manifest_identity": _identity(
            source_task_manifest_identity,
            label="run authorization source manifest",
        ),
        "output_prefix": prefix,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "reused_job_name": reused_job_name,
        "dispatcher_process_spec": dispatcher_process_spec_v1(),
        "task_count": TASK_COUNT,
        "task_attempt_limit": 0,
        "cloud_execution_attestation_present": False,
        "launch_submission_authority": False,
        "source_control_runtime_compatibility_claimed": False,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="run_authorization_sha256")


def validate_run_authorization_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor run authorization")
    if item.get("run_authorization_sha256") != _hash({
        key: row for key, row in item.items() if key != "run_authorization_sha256"
    }):
        _fail("successor run authorization self hash differs")
    expected = build_run_authorization_v1(
        source_task_manifest_identity=item.get("source_task_manifest_identity"),
        output_prefix=str(item.get("output_prefix", "")),
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        reused_job_name=str(item.get("reused_job_name", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor run authorization canonical replay differs")
    return expected


def matrix_process_spec_v1() -> dict[str, object]:
    entrypoint_sha = child_runtime.entrypoint_source_sha256_v1()
    command = child_runtime.canonical_matrix_selector_command_v1()
    return {
        "process_role": adapter.PROCESS_ROLE,
        "entrypoint_path": child_runtime.ENTRYPOINT_IMAGE_PATH,
        "entrypoint_sha256": entrypoint_sha,
        "command": command,
        "command_sha256": _hash({
            "command": command, "entrypoint_sha256": entrypoint_sha
        }),
    }


def build_bootstrap_v1(
    *, code_commit: str, image_digest: str, run_authorization_identity: object,
) -> dict[str, object]:
    if (
        _COMMIT_RE.fullmatch(str(code_commit)) is None
        or not str(image_digest).startswith("sha256:")
        or _SHA_RE.fullmatch(str(image_digest)[7:]) is None
    ):
        _fail("successor bootstrap commit/image differs")
    specs = [dispatcher_process_spec_v1(), matrix_process_spec_v1()]
    body = {
        "schema_version": BOOTSTRAP_SCHEMA,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "run_authorization_identity": _identity(
            run_authorization_identity, label="successor run authorization"
        ),
        "process_specs": specs,
        "process_specs_sha256": _hash(specs),
        "source_control_process_spec_compatible": False,
        "source_control_receipt_compatible": False,
        "policy": dict(_POLICY),
    }
    retained = _with_hash(body, field="bootstrap_sha256")
    if len(_canonical(retained)) > MAXIMUM_BOOTSTRAP_BYTES:
        _fail("successor bootstrap exceeds its byte ceiling")
    return retained


def validate_bootstrap_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor bootstrap")
    if item.get("bootstrap_sha256") != _hash({
        key: row for key, row in item.items() if key != "bootstrap_sha256"
    }):
        _fail("successor bootstrap self hash differs")
    expected = build_bootstrap_v1(
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        run_authorization_identity=item.get("run_authorization_identity"),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor bootstrap canonical replay differs")
    return expected


def build_slate_process_budget_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    source_task_manifest_identity: object,
    bootstrap_identity: object,
    run_authorization_identity: object,
    design_identity: object,
    topology_identity: object,
    projection_bundle_identity: object,
    source_process_budget_identities: object,
    successor_process_budget_identities: object,
    scientific_read_identities: object,
    result_uri: str,
) -> dict[str, object]:
    if type(source_ordinal) is not int or not 0 <= source_ordinal < TASK_COUNT:
        _fail("successor slate budget source ordinal differs")
    if type(slate_id) is not str or not slate_id or len(slate_id) > 128:
        _fail("successor slate budget slate ID differs")
    source_budgets = [
        _identity(row, label=f"source process budget[{index}]")
        for index, row in enumerate(_sequence(
            source_process_budget_identities,
            label="source process budget identities",
        ))
    ]
    successor_budgets = [
        _identity(row, label=f"successor process budget[{index}]")
        for index, row in enumerate(_sequence(
            successor_process_budget_identities,
            label="successor process budget identities",
        ))
    ]
    scientific = [
        _identity(row, label=f"scientific read[{index}]")
        for index, row in enumerate(_sequence(
            scientific_read_identities, label="scientific read identities"
        ))
    ]
    if (
        len(source_budgets) != FOLD_COUNT
        or len(successor_budgets) != FOLD_COUNT
        or len({row["uri"] for row in source_budgets}) != FOLD_COUNT
        or len({row["uri"] for row in successor_budgets}) != FOLD_COUNT
        or len(scientific) != 6
        or len({row["uri"] for row in scientific}) != 6
    ):
        _fail("successor slate budget fold/scientific read lattice differs")
    fixed_reads = [
        ("source-control-task-manifest", source_task_manifest_identity),
        ("successor-bootstrap", bootstrap_identity),
        ("run-authorization", run_authorization_identity),
        ("source-design", design_identity),
        ("source-topology", topology_identity),
        ("source-projection-bundle", projection_bundle_identity),
        *[
            (f"source-process-budget-fold-{fold}", identity)
            for fold, identity in enumerate(source_budgets)
        ],
        *[
            (f"successor-process-budget-fold-{fold}", identity)
            for fold, identity in enumerate(successor_budgets)
        ],
        ("later-source", scientific[0]),
        *[
            (f"world-{block}", scientific[index + 1])
            for index, block in enumerate(contract.WORLD_BLOCKS)
        ],
    ]
    reads = [
        {"role": role, "identity": _identity(identity, label=role)}
        for role, identity in fixed_reads
    ]
    if len({row["role"] for row in reads}) != len(reads):
        _fail("successor slate budget read roles repeat")
    if (
        type(result_uri) is not str
        or not result_uri.startswith(contract.OUTPUT_NAMESPACE)
        or not result_uri.endswith(f"source-{source_ordinal:03d}.json")
    ):
        _fail("successor slate result URI differs")
    body = {
        "schema_version": SLATE_PROCESS_BUDGET_SCHEMA,
        "process_role": "grouped-successor-slate-dispatcher",
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "read_allowlist": reads,
        "read_object_count": len(reads),
        "read_byte_ceiling": sum(
            int(row["identity"]["bytes"]) for row in reads
        ),
        "write_allowlist": [{
            "role": "successor-slate-result",
            "uri": result_uri,
            "max_bytes": MAXIMUM_SLATE_RESULT_BYTES,
            "create_once": True,
        }],
        "write_object_count": 1,
        "write_byte_ceiling": MAXIMUM_SLATE_RESULT_BYTES,
        "fold_process_count": FOLD_COUNT,
        "fit_precharge_per_fold": FITS_PER_FOLD,
        "compute_fit_precharge": FITS_PER_SLATE,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "current_generation_input_lookup_allowed": False,
        "create_once_equal_output_recovery_allowed": True,
        "policy": dict(_POLICY),
    }
    retained = _with_hash(body, field="slate_process_budget_sha256")
    if len(_canonical(retained)) > MAXIMUM_SLATE_PROCESS_BUDGET_BYTES:
        _fail("successor slate process budget exceeds its byte ceiling")
    return retained


def validate_slate_process_budget_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor slate process budget")
    if item.get("slate_process_budget_sha256") != _hash({
        key: row
        for key, row in item.items()
        if key != "slate_process_budget_sha256"
    }):
        _fail("successor slate process budget self hash differs")
    reads = [
        _mapping(row, label=f"successor slate read[{index}]")
        for index, row in enumerate(
            _sequence(item.get("read_allowlist"), label="successor slate reads")
        )
    ]
    by_role = {str(row.get("role")): row.get("identity") for row in reads}
    if len(by_role) != len(reads):
        _fail("successor slate process budget roles repeat")
    source_ids = [by_role.get(f"source-process-budget-fold-{fold}") for fold in range(FOLD_COUNT)]
    successor_ids = [by_role.get(f"successor-process-budget-fold-{fold}") for fold in range(FOLD_COUNT)]
    scientific = [by_role.get("later-source"), *[by_role.get(f"world-{block}") for block in contract.WORLD_BLOCKS]]
    writes = _sequence(item.get("write_allowlist"), label="successor slate writes")
    if len(writes) != 1:
        _fail("successor slate process budget write lattice differs")
    write = _mapping(writes[0], label="successor slate result write")
    expected = build_slate_process_budget_v1(
        source_ordinal=int(item.get("source_ordinal", -1)),
        slate_id=str(item.get("slate_id", "")),
        source_task_manifest_identity=by_role.get("source-control-task-manifest"),
        bootstrap_identity=by_role.get("successor-bootstrap"),
        run_authorization_identity=by_role.get("run-authorization"),
        design_identity=by_role.get("source-design"),
        topology_identity=by_role.get("source-topology"),
        projection_bundle_identity=by_role.get("source-projection-bundle"),
        source_process_budget_identities=source_ids,
        successor_process_budget_identities=successor_ids,
        scientific_read_identities=scientific,
        result_uri=str(write.get("uri", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor slate process budget canonical replay differs")
    return expected


def build_task_binding_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    source_task_binding: object,
    projection_bundle_identity: object,
    source_process_budget_identities: object,
    successor_process_budget_identities: object,
    slate_process_budget_identity: object,
    result_uri: str,
) -> dict[str, object]:
    source_task = _mapping(source_task_binding, label="source task binding")
    source_budgets = [
        _identity(row, label=f"binding source budget[{index}]")
        for index, row in enumerate(_sequence(
            source_process_budget_identities, label="binding source budgets"
        ))
    ]
    successor_budgets = [
        _identity(row, label=f"binding successor budget[{index}]")
        for index, row in enumerate(_sequence(
            successor_process_budget_identities,
            label="binding successor budgets",
        ))
    ]
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < TASK_COUNT
        or source_task.get("task_index") != source_ordinal
        or source_task.get("source_ordinal") != source_ordinal
        or len(source_budgets) != FOLD_COUNT
        or len(successor_budgets) != FOLD_COUNT
    ):
        _fail("successor task source/fold binding differs")
    body = {
        "schema_version": TASK_BINDING_SCHEMA,
        "task_index": source_ordinal,
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "source_task_binding_sha256": source_task.get("task_binding_sha256"),
        "source_task_science_binding_sha256": source_task.get(
            "task_science_binding_sha256"
        ),
        "source_request_sha256": source_task.get("request_sha256"),
        "projection_bundle_identity": _identity(
            projection_bundle_identity, label="binding projection bundle"
        ),
        "source_process_budget_identities": source_budgets,
        "successor_process_budget_identities": successor_budgets,
        "slate_process_budget_identity": _identity(
            slate_process_budget_identity, label="binding slate budget"
        ),
        "result_uri": result_uri,
        "fit_count_precharge": FITS_PER_SLATE,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
    }
    return _with_hash(body, field="task_binding_sha256")


def build_task_manifest_v1(
    *,
    output_prefix: str,
    source_task_manifest: object,
    source_task_manifest_identity: object,
    bootstrap: object,
    bootstrap_identity: object,
    run_authorization_identity: object,
    task_bindings: object,
) -> dict[str, object]:
    prefix = _safe_output_prefix(output_prefix)
    source = source_manifest.validate_task_manifest_v1(source_task_manifest)
    source_identity = _bind(
        source, source_task_manifest_identity, label="source control task manifest"
    )
    retained_bootstrap = validate_bootstrap_v1(bootstrap)
    retained_bootstrap_identity = _bind(
        retained_bootstrap, bootstrap_identity, label="successor bootstrap"
    )
    launch_identity = _identity(
        run_authorization_identity, label="successor run authorization"
    )
    bindings = [
        _mapping(row, label=f"successor task binding[{index}]")
        for index, row in enumerate(_sequence(task_bindings, label="task bindings"))
    ]
    if (
        source["layer_id"] != "broad-selection-receipt"
        or source["phase"] != contract.BROAD_SCREEN_PHASE
        or source["task_count"] != TASK_COUNT
        or len(bindings) != TASK_COUNT
        or [row.get("task_index") for row in bindings] != list(range(TASK_COUNT))
        or retained_bootstrap["run_authorization_identity"] != launch_identity
    ):
        _fail("successor source manifest/task/bootstrap lattice differs")
    for index, binding in enumerate(bindings):
        expected = build_task_binding_v1(
            source_ordinal=index,
            slate_id=str(binding.get("slate_id", "")),
            source_task_binding=source["task_bindings"][index],
            projection_bundle_identity=binding.get("projection_bundle_identity"),
            source_process_budget_identities=binding.get(
                "source_process_budget_identities"
            ),
            successor_process_budget_identities=binding.get(
                "successor_process_budget_identities"
            ),
            slate_process_budget_identity=binding.get(
                "slate_process_budget_identity"
            ),
            result_uri=str(binding.get("result_uri", "")),
        )
        if _canonical(binding) != _canonical(expected):
            _fail(f"successor task binding[{index}] replay differs")
        if binding["result_uri"] != f"{prefix}results/source-{index:03d}.json":
            _fail("successor task result URI order differs")
    body = {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "output_prefix": prefix,
        "source_control_task_manifest_identity": source_identity,
        "source_control_task_manifest_sha256": source[
            "task_manifest_sha256"
        ],
        "source_control_layer_id": source["layer_id"],
        "bootstrap_identity": retained_bootstrap_identity,
        "bootstrap_sha256": retained_bootstrap["bootstrap_sha256"],
        "run_authorization_identity": launch_identity,
        "code_commit": retained_bootstrap["code_commit"],
        "image_digest": retained_bootstrap["image_digest"],
        "dispatcher_process_spec": dispatcher_process_spec_v1(),
        "matrix_process_spec": matrix_process_spec_v1(),
        "task_count": TASK_COUNT,
        "task_bindings": bindings,
        "task_bindings_sha256": _hash(bindings),
        "fit_count_precharge_per_task": FITS_PER_SLATE,
        "fit_count_precharge_total": TASK_COUNT * FITS_PER_SLATE,
        "one_cloud_task_per_slate": True,
        "five_sequential_isolated_matrix_children_per_task": True,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "policy": dict(_POLICY),
    }
    retained = _with_hash(body, field="task_manifest_sha256")
    if len(_canonical(retained)) > MAXIMUM_TASK_MANIFEST_BYTES:
        _fail("successor task manifest exceeds its byte ceiling")
    return retained


def validate_task_manifest_v1(
    value: object, *, source_task_manifest: object, bootstrap: object,
) -> dict[str, object]:
    item = _mapping(value, label="successor task manifest")
    if item.get("task_manifest_sha256") != _hash({
        key: row for key, row in item.items() if key != "task_manifest_sha256"
    }):
        _fail("successor task manifest self hash differs")
    expected = build_task_manifest_v1(
        output_prefix=str(item.get("output_prefix", "")),
        source_task_manifest=source_task_manifest,
        source_task_manifest_identity=item.get(
            "source_control_task_manifest_identity"
        ),
        bootstrap=bootstrap,
        bootstrap_identity=item.get("bootstrap_identity"),
        run_authorization_identity=item.get("run_authorization_identity"),
        task_bindings=item.get("task_bindings"),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor task manifest canonical replay differs")
    return expected


def prepare_task_manifest_v1(
    *,
    source_task_manifest_identity: object,
    output_prefix: str,
    code_commit: str,
    image_digest: str,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    run_authorization_identity: object | None = None,
    reused_job_name: str | None = None,
) -> dict[str, object]:
    """Publish exact bootstrap, 270 fold budgets, 54 slate budgets and manifest."""
    prefix = _safe_output_prefix(output_prefix)
    source_value, source_identity = _read_json(
        source_task_manifest_identity,
        read_exact=read_exact,
        label="source control task manifest",
        maximum_bytes=source_manifest.MAXIMUM_MANIFEST_BYTES,
    )
    source = source_manifest.validate_task_manifest_v1(source_value)
    _bind(source, source_identity, label="source control task manifest")
    if (
        source["layer_id"] != "broad-selection-receipt"
        or source["phase"] != contract.BROAD_SCREEN_PHASE
        or source["task_count"] != TASK_COUNT
    ):
        _fail("source control task manifest is not the 54-slate broad layer")
    if (run_authorization_identity is None) == (reused_job_name is None):
        _fail("exactly one run authorization identity or reused job is required")
    if reused_job_name is not None:
        run_authorization = build_run_authorization_v1(
            source_task_manifest_identity=source_identity,
            output_prefix=prefix,
            code_commit=code_commit,
            image_digest=image_digest,
            reused_job_name=reused_job_name,
        )
        launch_identity = _publish(
            uri=f"{prefix}authorities/run-authorization.json",
            value=run_authorization,
            maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    else:
        launch_identity = _identity(
            run_authorization_identity, label="successor run authorization"
        )
        # Content-pin an externally prepared prelaunch token.  It is never
        # treated as a Cloud Run terminal attestation.
        launch_raw = read_exact(launch_identity)
        if (
            type(launch_raw) is not bytes
            or len(launch_raw) != launch_identity["bytes"]
            or sha256(launch_raw).hexdigest() != launch_identity["sha256"]
        ):
            _fail("successor run authorization exact bytes differ")
    bootstrap = build_bootstrap_v1(
        code_commit=code_commit,
        image_digest=image_digest,
        run_authorization_identity=launch_identity,
    )
    bootstrap_identity = _publish(
        uri=f"{prefix}authorities/bootstrap.json",
        value=bootstrap,
        maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    topology_value, _ = _read_json(
        source["topology_identity"],
        read_exact=read_exact,
        label="source topology",
        maximum_bytes=source_manifest.MAXIMUM_TOPOLOGY_BYTES,
    )
    topology = contract.validate_result_topology_v1(topology_value)
    _bind(topology, source["topology_identity"], label="source topology")
    design_value, _ = _read_json(
        source["design_identity"],
        read_exact=read_exact,
        label="source design",
        maximum_bytes=source_manifest.MAXIMUM_DESIGN_BYTES,
    )
    try:
        design = contract.validate_design_authority_v1(
            design_value, publication_identity=source["design_identity"]
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            f"source design authority differs: {exc}"
        ) from exc
    if design["topology"] != topology:
        _fail("source design/topology authority differs")
    topology_identity = source["topology_identity"]
    design_identity = source["design_identity"]
    bindings: list[dict[str, object]] = []
    published_fold_budget_identities: list[dict[str, object]] = []
    published_slate_budget_identities: list[dict[str, object]] = []
    for source_ordinal, source_task in enumerate(source["task_bindings"]):
        request = _mapping(
            source_task["request"],
            label=f"source task request[{source_ordinal}]",
        )
        bundle_value, bundle_identity = _read_json(
            request["projection_bundle_identity"],
            read_exact=read_exact,
            label=f"projection bundle[{source_ordinal}]",
            maximum_bytes=256_000_000,
        )
        try:
            bundle = contract.validate_projection_bundle_authority_v1(
                bundle_value,
                publication_identity=bundle_identity,
                topology=topology,
                topology_identity=topology_identity,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(
                f"projection bundle[{source_ordinal}] authority differs: {exc}"
            ) from exc
        if (
            bundle["source_ordinal"] != source_ordinal
            or request["source_ordinal"] != source_ordinal
        ):
            _fail("source task/projection bundle ordinal differs")
        source_budget_identities = [
            _identity(row, label=f"source budget[{source_ordinal},{fold}]")
            for fold, row in enumerate(request["worker_process_budget_identities"])
        ]
        successor_budget_identities: list[dict[str, object]] = []
        for fold, source_budget_identity in enumerate(source_budget_identities):
            source_budget_value, retained_source_budget_identity = _read_json(
                source_budget_identity,
                read_exact=read_exact,
                label=f"source process budget[{source_ordinal},{fold}]",
                maximum_bytes=source_manifest.MAXIMUM_PROCESS_BUDGET_BYTES,
            )
            try:
                source_budget = contract.validate_process_budget_v1(
                    source_budget_value
                )
                expected_source_budget = contract.compile_process_budget_v1(
                    process_role="broad-fold-selector",
                    projection_bundle=bundle,
                    projection_bundle_identity=bundle_identity,
                    topology=topology,
                    topology_identity=topology_identity,
                    source_ordinal=source_ordinal,
                    fold_ordinal=fold,
                )
            except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
                raise CorpusR6CurrentBankSelectorSuccessorCloudV1Error(
                    f"source process budget[{source_ordinal},{fold}] differs: {exc}"
                ) from exc
            if _canonical(source_budget) != _canonical(expected_source_budget):
                _fail("source process budget differs from exact control replay")
            successor_budget = adapter.compile_successor_process_budget_v1(
                source_process_budget=source_budget,
                source_process_budget_identity=retained_source_budget_identity,
                source_projection=bundle["fold_projections"][fold],
            )
            successor_identity = _publish(
                uri=(
                    f"{prefix}authorities/process-budgets/"
                    f"source-{source_ordinal:03d}-fold-{fold}.json"
                ),
                value=successor_budget,
                maximum_bytes=source_manifest.MAXIMUM_PROCESS_BUDGET_BYTES,
                publish_create_once=publish_create_once,
                read_exact=read_exact,
            )
            successor_budget_identities.append(successor_identity)
            published_fold_budget_identities.append(successor_identity)
        first_projection = bundle["fold_projections"][0]
        worlds = first_projection["world_artifact_identities"]
        scientific_ids = [
            first_projection["later_source_identity"],
            *[
                worlds[f"world_artifact_{block.lower()}"]
                for block in contract.WORLD_BLOCKS
            ],
        ]
        result_uri = f"{prefix}results/source-{source_ordinal:03d}.json"
        slate_budget = build_slate_process_budget_v1(
            source_ordinal=source_ordinal,
            slate_id=str(bundle["slate_id"]),
            source_task_manifest_identity=source_identity,
            bootstrap_identity=bootstrap_identity,
            run_authorization_identity=launch_identity,
            design_identity=design_identity,
            topology_identity=topology_identity,
            projection_bundle_identity=bundle_identity,
            source_process_budget_identities=source_budget_identities,
            successor_process_budget_identities=successor_budget_identities,
            scientific_read_identities=scientific_ids,
            result_uri=result_uri,
        )
        slate_budget_identity = _publish(
            uri=(
                f"{prefix}authorities/slate-process-budgets/"
                f"source-{source_ordinal:03d}.json"
            ),
            value=slate_budget,
            maximum_bytes=MAXIMUM_SLATE_PROCESS_BUDGET_BYTES,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
        published_slate_budget_identities.append(slate_budget_identity)
        bindings.append(build_task_binding_v1(
            source_ordinal=source_ordinal,
            slate_id=str(bundle["slate_id"]),
            source_task_binding=source_task,
            projection_bundle_identity=bundle_identity,
            source_process_budget_identities=source_budget_identities,
            successor_process_budget_identities=successor_budget_identities,
            slate_process_budget_identity=slate_budget_identity,
            result_uri=result_uri,
        ))
    manifest = build_task_manifest_v1(
        output_prefix=prefix,
        source_task_manifest=source,
        source_task_manifest_identity=source_identity,
        bootstrap=bootstrap,
        bootstrap_identity=bootstrap_identity,
        run_authorization_identity=launch_identity,
        task_bindings=bindings,
    )
    manifest_identity = _publish(
        uri=f"{prefix}authorities/task-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    job_name = reused_job_name
    if job_name is None:
        launch_value = _strict_json(
            read_exact(launch_identity), label="successor run authorization"
        )
        if launch_value.get("schema_version") == RUN_AUTHORIZATION_SCHEMA:
            job_name = str(
                validate_run_authorization_v1(launch_value)["reused_job_name"]
            )
    job_configuration = (
        None
        if job_name is None
        else build_cloud_run_job_configuration_v1(
            task_manifest=manifest,
            task_manifest_identity=manifest_identity,
            reused_job_name=job_name,
        )
    )
    return {
        "schema_version": (
            "corpus-r6-current-bank-grouped-selector-preparation-result/v1"
        ),
        "bootstrap_identity": bootstrap_identity,
        "task_manifest_identity": manifest_identity,
        "source_task_manifest_identity": source_identity,
        "run_authorization_identity": launch_identity,
        "task_count": TASK_COUNT,
        "fold_budget_count": len(published_fold_budget_identities),
        "slate_budget_count": len(published_slate_budget_identities),
        "fit_count_precharge_total": TASK_COUNT * FITS_PER_SLATE,
        "cloud_run_job_configuration": job_configuration,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
    }


def build_cloud_run_job_configuration_v1(
    *,
    task_manifest: object,
    task_manifest_identity: object,
    reused_job_name: str,
) -> dict[str, object]:
    manifest = _mapping(task_manifest, label="successor task manifest")
    if manifest.get("task_manifest_sha256") != _hash({
        key: row for key, row in manifest.items() if key != "task_manifest_sha256"
    }):
        _fail("successor job configuration manifest self hash differs")
    if (
        manifest.get("schema_version") != TASK_MANIFEST_SCHEMA
        or manifest.get("task_count") != TASK_COUNT
        or manifest.get("dispatcher_process_spec") != dispatcher_process_spec_v1()
        or manifest.get("source_control_fit_parity_claimed") is not False
        or manifest.get("source_control_receipt_compatible") is not False
    ):
        _fail("successor job configuration manifest authority differs")
    manifest_identity = _bind(
        manifest, task_manifest_identity, label="successor task manifest"
    )
    if (
        type(reused_job_name) is not str
        or re.fullmatch(
            r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", reused_job_name
        ) is None
    ):
        _fail("successor reused Cloud Run job name differs")
    environment = {
        ENABLE_ENV: "1",
        MANIFEST_IDENTITY_ENV: _canonical(manifest_identity).decode("utf-8"),
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["image_digest"],
    }
    body = {
        "schema_version": (
            "corpus-r6-current-bank-grouped-selector-cloud-run-job-configuration/v1"
        ),
        "reused_job_name": reused_job_name,
        "task_manifest_identity": manifest_identity,
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
        "per_task_deploy_allowed": False,
        "source_control_command_compatible": False,
    }
    return _with_hash(body, field="job_configuration_sha256")


def build_dispatcher_runtime_evidence_v1(
    *,
    environ: Mapping[str, str],
    observed_command: object,
    pid: int,
    parent_pid: int,
) -> dict[str, object]:
    environment = dict(environ)
    if any(environment.get(key) for key in _REDIRECT_ENV_KEYS):
        _fail("successor dispatcher redirect environment is forbidden")
    command = [str(row) for row in _sequence(
        observed_command, label="successor dispatcher command"
    )]
    project_values = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    index_text = environment.get("CLOUD_RUN_TASK_INDEX", "")
    count_text = environment.get("CLOUD_RUN_TASK_COUNT", "")
    attempt_text = environment.get("CLOUD_RUN_TASK_ATTEMPT", "")
    commit = environment.get("CODE_SHA", "")
    image = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    if (
        command != list(DISPATCHER_COMMAND)
        or environment.get(ENABLE_ENV) != "1"
        or project_values != {FIXED_GCP_PROJECT}
        or environment.get("GOOGLE_CLOUD_PROJECT") != FIXED_GCP_PROJECT
        or _COMMIT_RE.fullmatch(commit) is None
        or not image.startswith("sha256:")
        or _SHA_RE.fullmatch(image[7:]) is None
        or not index_text.isdecimal()
        or not count_text.isdecimal()
        or attempt_text != "0"
        or int(count_text) != TASK_COUNT
        or not 0 <= int(index_text) < TASK_COUNT
        or type(pid) is not int
        or type(parent_pid) is not int
        or pid < 1
        or parent_pid < 1
        or pid == parent_pid
    ):
        _fail("successor dispatcher runtime environment differs")
    job = environment.get("CLOUD_RUN_JOB", "")
    execution = environment.get("CLOUD_RUN_EXECUTION", "")
    if not job or not execution or len(job) > 512 or len(execution) > 512:
        _fail("successor dispatcher job/execution differs")
    spec = dispatcher_process_spec_v1()
    body = {
        "schema_version": DISPATCHER_RUNTIME_SCHEMA,
        "project_id": FIXED_GCP_PROJECT,
        "storage_endpoint": FIXED_STORAGE_ENDPOINT,
        "code_commit": commit,
        "image_digest": image,
        "job_name": job,
        "execution_id": execution,
        "task_index": int(index_text),
        "task_count": int(count_text),
        "task_attempt": 0,
        "pid": pid,
        "parent_pid": parent_pid,
        "entrypoint_path": spec["entrypoint_path"],
        "entrypoint_sha256": spec["entrypoint_sha256"],
        "command": command,
        "command_sha256": spec["command_sha256"],
        "source_control_dispatcher_compatibility_claimed": False,
        "terminal_cloud_execution_attestation_present": False,
    }
    return _with_hash(body, field="dispatcher_runtime_evidence_sha256")


def build_matrix_child_request_v1(
    *,
    source_process_budget: object,
    source_process_budget_identity: object,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    matrix_capability: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    from nfl_dfs.research import (
        corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
    )

    body = {
        "schema_version": MATRIX_CHILD_REQUEST_SCHEMA,
        "source_process_budget": _mapping(
            source_process_budget, label="source process budget"
        ),
        "source_process_budget_identity": _identity(
            source_process_budget_identity,
            label="source process budget identity",
        ),
        "successor_process_budget": _mapping(
            successor_process_budget, label="successor process budget"
        ),
        "successor_process_budget_identity": _identity(
            successor_process_budget_identity,
            label="successor process budget identity",
        ),
        "matrix_capability": worker.validate_matrix_capability_v1(
            matrix_capability
        ),
        "launch_intent_identity": _identity(
            launch_intent_identity, label="launch intent identity"
        ),
        "object_store_client_exposed": False,
        "heldout_artifact_identity_exposed": False,
    }
    return _with_hash(body, field="child_request_sha256")


def validate_matrix_child_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="grouped selector child request")
    if item.get("child_request_sha256") != _hash({
        key: row for key, row in item.items() if key != "child_request_sha256"
    }):
        _fail("grouped selector child request self hash differs")
    expected = build_matrix_child_request_v1(
        source_process_budget=item.get("source_process_budget"),
        source_process_budget_identity=item.get(
            "source_process_budget_identity"
        ),
        successor_process_budget=item.get("successor_process_budget"),
        successor_process_budget_identity=item.get(
            "successor_process_budget_identity"
        ),
        matrix_capability=item.get("matrix_capability"),
        launch_intent_identity=item.get("launch_intent_identity"),
    )
    if (
        item.get("schema_version") != MATRIX_CHILD_REQUEST_SCHEMA
        or item.get("object_store_client_exposed") is not False
        or item.get("heldout_artifact_identity_exposed") is not False
        or _canonical(item) != _canonical(expected)
    ):
        _fail("grouped selector child request replay differs")
    return expected


def validate_dispatcher_runtime_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor dispatcher runtime evidence")
    if item.get("dispatcher_runtime_evidence_sha256") != _hash({
        key: row
        for key, row in item.items()
        if key != "dispatcher_runtime_evidence_sha256"
    }):
        _fail("successor dispatcher runtime self hash differs")
    spec = dispatcher_process_spec_v1()
    if (
        item.get("schema_version") != DISPATCHER_RUNTIME_SCHEMA
        or item.get("project_id") != FIXED_GCP_PROJECT
        or item.get("storage_endpoint") != FIXED_STORAGE_ENDPOINT
        or _COMMIT_RE.fullmatch(str(item.get("code_commit", ""))) is None
        or not str(item.get("image_digest", "")).startswith("sha256:")
        or _SHA_RE.fullmatch(str(item.get("image_digest", ""))[7:]) is None
        or item.get("task_count") != TASK_COUNT
        or item.get("task_attempt") != 0
        or item.get("entrypoint_path") != spec["entrypoint_path"]
        or item.get("entrypoint_sha256") != spec["entrypoint_sha256"]
        or item.get("command") != spec["command"]
        or item.get("command_sha256") != spec["command_sha256"]
        or item.get("source_control_dispatcher_compatibility_claimed") is not False
        or item.get("terminal_cloud_execution_attestation_present") is not False
    ):
        _fail("successor dispatcher runtime fixed binding differs")
    for field in ("task_index", "task_count", "task_attempt", "pid", "parent_pid"):
        if type(item.get(field)) is not int or int(item[field]) < 0:
            _fail(f"successor dispatcher runtime {field} differs")
    if (
        not 0 <= int(item["task_index"]) < TASK_COUNT
        or item["pid"] < 1
        or item["parent_pid"] < 1
        or item["pid"] == item["parent_pid"]
    ):
        _fail("successor dispatcher runtime process/task identity differs")
    return item


def _validate_fold_receipt_structural_v1(
    value: object, *, source_ordinal: int, fold_ordinal: int,
) -> dict[str, object]:
    receipt = _mapping(value, label=f"successor fold receipt[{fold_ordinal}]")
    if receipt.get("successor_fold_receipt_sha256") != _hash({
        key: row
        for key, row in receipt.items()
        if key != "successor_fold_receipt_sha256"
    }):
        _fail("successor fold receipt self hash differs")
    launch = _mapping(
        receipt.get("outer_launch_envelope"), label="successor fold launch envelope"
    )
    if launch.get("outer_launch_envelope_sha256") != _hash({
        key: row
        for key, row in launch.items()
        if key != "outer_launch_envelope_sha256"
    }):
        _fail("successor fold launch envelope self hash differs")
    if (
        receipt.get("schema_version") != adapter.FOLD_RECEIPT_SCHEMA
        or receipt.get("phase") != contract.BROAD_SCREEN_PHASE
        or receipt.get("source_ordinal") != source_ordinal
        or receipt.get("fold_ordinal") != fold_ordinal
        or receipt.get("process_ordinal")
        != source_ordinal * FOLD_COUNT + fold_ordinal
        or receipt.get("heldout_block") != contract.WORLD_BLOCKS[fold_ordinal]
        or receipt.get("fit_count") != FITS_PER_FOLD
        or receipt.get("view_count") != adapter.EXACT_VIEW_COUNT
        or receipt.get("selector_count_per_view")
        != adapter.EXACT_SELECTORS_PER_VIEW
        or receipt.get("source_control_fit_parity_claimed") is not False
        or receipt.get("source_control_receipt_compatible") is not False
        or receipt.get("publication_authority") is not False
        or launch.get("runtime_evidence", {}).get("runtime_mode")
        != child_runtime.RUNTIME_MODE
        or launch.get("runtime_task_index") != source_ordinal
        or launch.get("runtime_process_ordinal")
        != source_ordinal * FOLD_COUNT + fold_ordinal
    ):
        _fail("successor fold receipt structural authority differs")
    cells = _sequence(receipt.get("cell_sha256s"), label="successor fold cells")
    if len(cells) != FITS_PER_FOLD:
        _fail("successor fold receipt cell count differs")
    return receipt


def build_slate_result_v1(
    *,
    task_manifest: object,
    task_manifest_identity: object,
    task_binding: object,
    bootstrap: object,
    slate_process_budget: object,
    slate_process_budget_identity: object,
    fold_receipts: object,
    dispatcher_runtime_evidence: object,
) -> dict[str, object]:
    manifest = _mapping(task_manifest, label="successor task manifest")
    if manifest.get("task_manifest_sha256") != _hash({
        key: row for key, row in manifest.items() if key != "task_manifest_sha256"
    }):
        _fail("successor task manifest self hash differs at assembly")
    manifest_identity = _bind(
        manifest, task_manifest_identity, label="successor task manifest"
    )
    binding = _mapping(task_binding, label="successor task binding")
    if binding.get("task_binding_sha256") != _hash({
        key: row for key, row in binding.items() if key != "task_binding_sha256"
    }):
        _fail("successor task binding self hash differs")
    retained_bootstrap = validate_bootstrap_v1(bootstrap)
    budget = validate_slate_process_budget_v1(slate_process_budget)
    budget_identity = _bind(
        budget, slate_process_budget_identity, label="successor slate budget"
    )
    runtime = validate_dispatcher_runtime_evidence_v1(
        dispatcher_runtime_evidence
    )
    source = int(binding.get("source_ordinal", -1))
    folds = [
        _validate_fold_receipt_structural_v1(
            row, source_ordinal=source, fold_ordinal=index
        )
        for index, row in enumerate(
            _sequence(fold_receipts, label="successor fold receipts")
        )
    ]
    if (
        len(folds) != FOLD_COUNT
        or manifest.get("task_bindings", [])[source] != binding
        or binding.get("slate_process_budget_identity") != budget_identity
        or budget.get("source_ordinal") != source
        or budget.get("slate_id") != binding.get("slate_id")
        or runtime["task_index"] != source
        or runtime["code_commit"] != manifest.get("code_commit")
        or runtime["image_digest"] != manifest.get("image_digest")
        or retained_bootstrap["code_commit"] != runtime["code_commit"]
        or retained_bootstrap["image_digest"] != runtime["image_digest"]
        or retained_bootstrap["run_authorization_identity"]
        != manifest.get("run_authorization_identity")
        or [
            row["successor_process_budget_identity"] for row in folds
        ] != binding.get("successor_process_budget_identities")
    ):
        _fail("successor five-fold slate assembly authority differs")
    body = {
        "schema_version": SLATE_RESULT_SCHEMA,
        "source_ordinal": source,
        "slate_id": binding["slate_id"],
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "task_binding_sha256": binding["task_binding_sha256"],
        "bootstrap_identity": manifest["bootstrap_identity"],
        "bootstrap_sha256": retained_bootstrap["bootstrap_sha256"],
        "run_authorization_identity": manifest["run_authorization_identity"],
        "slate_process_budget_identity": budget_identity,
        "slate_process_budget_sha256": budget[
            "slate_process_budget_sha256"
        ],
        "dispatcher_runtime_evidence": runtime,
        "dispatcher_runtime_evidence_sha256": runtime[
            "dispatcher_runtime_evidence_sha256"
        ],
        "fold_count": FOLD_COUNT,
        "fold_order": list(contract.WORLD_BLOCKS),
        "fold_receipts": folds,
        "fold_receipt_sha256s": [
            row["successor_fold_receipt_sha256"] for row in folds
        ],
        "fit_count": FITS_PER_SLATE,
        "fit_count_by_fold": [FITS_PER_FOLD] * FOLD_COUNT,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "terminal_cloud_execution_attestation_present": False,
        "publication_mode": "create-once-exact-reopen",
        "policy": dict(_POLICY),
    }
    retained = _with_hash(body, field="slate_result_sha256")
    if len(_canonical(retained)) > MAXIMUM_SLATE_RESULT_BYTES:
        _fail("successor slate result exceeds its byte ceiling")
    return retained


def build_task_result_envelope_v1(
    *,
    slate_result: object,
    slate_result_identity: object,
) -> dict[str, object]:
    result = _mapping(slate_result, label="successor slate result")
    if result.get("slate_result_sha256") != _hash({
        key: row for key, row in result.items() if key != "slate_result_sha256"
    }):
        _fail("successor slate result self hash differs")
    identity = _bind(result, slate_result_identity, label="successor slate result")
    body = {
        "schema_version": TASK_RESULT_ENVELOPE_SCHEMA,
        "source_ordinal": result["source_ordinal"],
        "slate_id": result["slate_id"],
        "task_manifest_identity": result["task_manifest_identity"],
        "task_binding_sha256": result["task_binding_sha256"],
        "slate_result_identity": identity,
        "slate_result_sha256": result["slate_result_sha256"],
        "fold_count": result["fold_count"],
        "fit_count": result["fit_count"],
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "terminal_cloud_execution_attestation_present": False,
    }
    retained = _with_hash(body, field="task_result_envelope_sha256")
    if len(_canonical(retained)) > MAXIMUM_TASK_RESULT_ENVELOPE_BYTES:
        _fail("successor task result envelope exceeds its byte ceiling")
    return retained


__all__ = [
    "BOOTSTRAP_SCHEMA",
    "DISPATCHER_COMMAND",
    "DISPATCHER_RUNTIME_SCHEMA",
    "ENABLE_ENV",
    "FITS_PER_FOLD",
    "FITS_PER_SLATE",
    "MANIFEST_IDENTITY_ENV",
    "MATRIX_CHILD_REQUEST_SCHEMA",
    "MAXIMUM_SLATE_RESULT_BYTES",
    "MAXIMUM_TASK_MANIFEST_BYTES",
    "RUN_AUTHORIZATION_SCHEMA",
    "SLATE_PROCESS_BUDGET_SCHEMA",
    "SLATE_RESULT_SCHEMA",
    "TASK_COUNT",
    "TASK_MANIFEST_SCHEMA",
    "TASK_RESULT_ENVELOPE_SCHEMA",
    "TASK_TIMEOUT_SECONDS",
    "CorpusR6CurrentBankSelectorSuccessorCloudV1Error",
    "build_bootstrap_v1",
    "build_cloud_run_job_configuration_v1",
    "build_dispatcher_runtime_evidence_v1",
    "build_matrix_child_request_v1",
    "build_run_authorization_v1",
    "build_slate_process_budget_v1",
    "build_slate_result_v1",
    "build_task_binding_v1",
    "build_task_manifest_v1",
    "build_task_result_envelope_v1",
    "dispatcher_process_spec_v1",
    "matrix_process_spec_v1",
    "prepare_task_manifest_v1",
    "validate_bootstrap_v1",
    "validate_dispatcher_runtime_evidence_v1",
    "validate_matrix_child_request_v1",
    "validate_run_authorization_v1",
    "validate_slate_process_budget_v1",
    "validate_task_manifest_v1",
]
