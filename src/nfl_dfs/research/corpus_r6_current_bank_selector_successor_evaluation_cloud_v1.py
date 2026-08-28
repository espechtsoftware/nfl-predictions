"""Cloud authority for the successor held-out evaluator and terminal root.

This module owns a separate evaluator command, process budget, 54-task
manifest, and one-task terminal manifest.  It never calls the frozen 64-fit
control evaluator.  A caller-supplied scoring callback may only turn one
generation-pinned held-out world artifact into the full projection-ordered
score matrix; the successor-native evaluator derives every metric itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as source_manifest,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as selection_cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_evaluation_v1 as evaluation,
)


RUN_AUTHORIZATION_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluation-run-authorization/v1"
)
BOOTSTRAP_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluation-bootstrap/v1"
)
PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluator-process-budget/v1"
)
TASK_BINDING_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluator-task-binding/v1"
)
TASK_MANIFEST_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluator-task-manifest/v1"
)
RUNTIME_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluator-runtime/v1"
)
TASK_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluator-task-envelope/v1"
)
TERMINAL_MANIFEST_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-terminal-manifest/v1"
)
TERMINAL_PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-terminal-process-budget/v1"
)
TERMINAL_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-terminal-envelope/v1"
)

MODE_EVALUATE: Final = "evaluate"
MODE_AGGREGATE: Final = "aggregate"
TASK_COUNT: Final = contract.PANEL_SLATE_COUNT
MAXIMUM_PROCESS_BUDGET_BYTES: Final = 2_000_000
MAXIMUM_TASK_MANIFEST_BYTES: Final = 32_000_000
MAXIMUM_EVALUATION_RESULT_BYTES: Final = 256_000_000
MAXIMUM_TERMINAL_RESULT_BYTES: Final = 256_000_000
MAXIMUM_BOOTSTRAP_BYTES: Final = 256_000
MAXIMUM_ENVELOPE_BYTES: Final = 4_000_000
MAXIMUM_SELECTION_RESULT_BYTES: Final = max(
    selection_cloud.MAXIMUM_SLATE_RESULT_BYTES,
    selection_cloud.MAXIMUM_RANK150_DPP_SLATE_RESULT_BYTES,
)
MAXIMUM_PROJECTION_BYTES: Final = 256_000_000
MAXIMUM_LATER_SOURCE_BYTES: Final = 8_000_000
MAXIMUM_WORLD_BYTES: Final = 128_000_000
TASK_TIMEOUT_SECONDS: Final = 1_800
TERMINAL_TIMEOUT_SECONDS: Final = 1_800
FIXED_GCP_PROJECT: Final = selection_cloud.FIXED_GCP_PROJECT
FIXED_STORAGE_ENDPOINT: Final = selection_cloud.FIXED_STORAGE_ENDPOINT
ENTRYPOINT_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_current_bank_selector_successor_evaluation_cloud_v1.py"
)
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
PYTHON_IMAGE_PATH: Final = "/usr/local/bin/python3.11"
MANIFEST_IDENTITY_ENV: Final = "R6_SUCCESSOR_EVALUATION_MANIFEST_IDENTITY"
TERMINAL_MANIFEST_IDENTITY_ENV: Final = (
    "R6_SUCCESSOR_TERMINAL_MANIFEST_IDENTITY"
)
ENABLE_ENV: Final = "R6_SUCCESSOR_EVALUATION_ENABLE"

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_REDIRECT_ENV_KEYS: Final = frozenset({
    "ALL_PROXY", "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE", "CLOUDSDK_CONFIG",
    "CURL_CA_BUNDLE", "GCE_METADATA_HOST", "GCE_METADATA_IP",
    "GOOGLE_APPLICATION_CREDENTIALS", "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
    "HTTP_PROXY", "HTTPS_PROXY", "LD_AUDIT", "LD_LIBRARY_PATH",
    "LD_PRELOAD", "NO_PROXY", "PYTHONHOME", "PYTHONPATH",
    "REQUESTS_CA_BUNDLE", "SSL_CERT_DIR", "SSL_CERT_FILE",
    "STORAGE_EMULATOR_HOST", "all_proxy", "http_proxy", "https_proxy",
    "no_proxy",
})
_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "current_generation_scientific_input_lookup_allowed": False,
    "object_listing_allowed": False,
    "selector_callable_present": False,
    "source_control_evaluator_compatibility_claimed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
}

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
ScoreHeldout = Callable[..., np.ndarray]


class CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(ValueError):
    """The successor evaluator cloud boundary failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
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


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    digest = value.get(field)
    if (
        type(digest) is not str
        or _SHA_RE.fullmatch(digest) is None
        or digest != _hash({key: item for key, item in value.items() if key != field})
    ):
        _fail(f"{label} self hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
            str(exc)
        ) from exc


def _bind(
    value: Mapping[str, object], identity_value: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            value, identity_value, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
            str(exc)
        ) from exc


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
            f"{label} is not JSON"
        ) from exc
    body = _mapping(value, label=label)
    if _canonical(body) != raw:
        _fail(f"{label} is not canonical JSON")
    return body


def _read_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
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
    *, uri: str, value: Mapping[str, object], maximum_bytes: int,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    raw = _canonical(value)
    if not raw or len(raw) > maximum_bytes:
        _fail("successor evaluation publication exceeds byte ceiling")
    identity = _identity(
        publish_create_once(uri, raw), label="create-once publication"
    )
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
        or read_exact(identity) != raw
    ):
        _fail("successor evaluation create-once exact reopen differs")
    return identity


def _safe_prefix(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(contract.OUTPUT_NAMESPACE)
        or not value.endswith("/")
        or "?" in value
        or "#" in value
        or "//" in value[5:]
        or any(part in {"", ".", ".."} for part in value[5:-1].split("/"))
    ):
        _fail("successor evaluation output prefix differs")
    return value


def canonical_command_v1(mode: str) -> list[str]:
    if mode not in {MODE_EVALUATE, MODE_AGGREGATE}:
        _fail("successor evaluation runtime mode differs")
    return [PYTHON_IMAGE_PATH, "-I", ENTRYPOINT_IMAGE_PATH, mode]


def _entrypoint_sha() -> str:
    path = Path(__file__).resolve().parents[3] / ENTRYPOINT_RELATIVE_PATH
    if not path.is_file():
        _fail("successor evaluation entrypoint is absent")
    return sha256(path.read_bytes()).hexdigest()


def process_spec_v1(mode: str) -> dict[str, object]:
    command = canonical_command_v1(mode)
    digest = _entrypoint_sha()
    return {
        "process_role": (
            "successor-heldout-evaluator"
            if mode == MODE_EVALUATE
            else "successor-terminal-aggregator"
        ),
        "runtime_mode": mode,
        "entrypoint_path": ENTRYPOINT_IMAGE_PATH,
        "entrypoint_sha256": digest,
        "command": command,
        "command_sha256": _hash({
            "command": command, "entrypoint_sha256": digest
        }),
    }


def build_run_authorization_v1(
    *, selection_task_manifest_identity: object, output_prefix: str,
    code_commit: str, image_digest: str, reused_job_name: str,
) -> dict[str, object]:
    prefix = _safe_prefix(output_prefix)
    if (
        _COMMIT_RE.fullmatch(str(code_commit)) is None
        or not str(image_digest).startswith("sha256:")
        or _SHA_RE.fullmatch(str(image_digest)[7:]) is None
        or _JOB_RE.fullmatch(str(reused_job_name)) is None
    ):
        _fail("successor evaluator run authorization runtime differs")
    return _with_hash({
        "schema_version": RUN_AUTHORIZATION_SCHEMA,
        "selection_task_manifest_identity": _identity(
            selection_task_manifest_identity,
            label="selection task manifest",
        ),
        "output_prefix": prefix,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "reused_job_name": reused_job_name,
        "task_count": TASK_COUNT,
        "max_retries": 0,
        "launch_submission_authority": False,
        "policy": dict(_POLICY),
    }, field="run_authorization_sha256")


def validate_run_authorization_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor evaluator run authorization")
    _self_hash(
        item, field="run_authorization_sha256", label="run authorization"
    )
    expected = build_run_authorization_v1(
        selection_task_manifest_identity=item.get(
            "selection_task_manifest_identity"
        ),
        output_prefix=str(item.get("output_prefix", "")),
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        reused_job_name=str(item.get("reused_job_name", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor evaluator run authorization replay differs")
    return expected


def build_bootstrap_v1(
    *, code_commit: str, image_digest: str, run_authorization_identity: object,
) -> dict[str, object]:
    if (
        _COMMIT_RE.fullmatch(str(code_commit)) is None
        or not str(image_digest).startswith("sha256:")
        or _SHA_RE.fullmatch(str(image_digest)[7:]) is None
    ):
        _fail("successor evaluator bootstrap runtime differs")
    specs = [process_spec_v1(MODE_EVALUATE), process_spec_v1(MODE_AGGREGATE)]
    return _with_hash({
        "schema_version": BOOTSTRAP_SCHEMA,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "run_authorization_identity": _identity(
            run_authorization_identity, label="evaluator run authorization"
        ),
        "process_specs": specs,
        "process_specs_sha256": _hash(specs),
        "source_control_evaluator_compatible": False,
        "policy": dict(_POLICY),
    }, field="bootstrap_sha256")


def validate_bootstrap_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor evaluator bootstrap")
    _self_hash(item, field="bootstrap_sha256", label="evaluator bootstrap")
    expected = build_bootstrap_v1(
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        run_authorization_identity=item.get("run_authorization_identity"),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor evaluator bootstrap replay differs")
    return expected


def build_evaluator_process_budget_v1(
    *, source_ordinal: int, slate_id: str,
    selection_task_manifest_identity: object,
    source_task_manifest_identity: object, selection_bootstrap_identity: object,
    evaluator_bootstrap_identity: object, run_authorization_identity: object,
    selection_result_identity: object, projection_bundle_identity: object,
    later_source_identity: object, world_artifact_identities: object,
    result_uri: str,
) -> dict[str, object]:
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < TASK_COUNT
        or type(slate_id) is not str
        or not slate_id
    ):
        _fail("successor evaluator process coordinate differs")
    worlds = _mapping(
        world_artifact_identities, label="evaluator world artifact identities"
    )
    roles = {f"world_artifact_{block.lower()}" for block in contract.WORLD_BLOCKS}
    if set(worlds) != roles:
        _fail("successor evaluator world role lattice differs")
    fixed = [
        ("selection-task-manifest", selection_task_manifest_identity),
        ("source-task-manifest", source_task_manifest_identity),
        ("selection-bootstrap", selection_bootstrap_identity),
        ("evaluator-bootstrap", evaluator_bootstrap_identity),
        ("run-authorization", run_authorization_identity),
        ("selection-slate-result", selection_result_identity),
        ("projection-bundle", projection_bundle_identity),
        ("later-source", later_source_identity),
        *[
            (f"heldout-world-{block}", worlds[f"world_artifact_{block.lower()}"])
            for block in contract.WORLD_BLOCKS
        ],
    ]
    reads = [
        {"role": role, "identity": _identity(identity, label=role)}
        for role, identity in fixed
    ]
    if len({row["identity"]["uri"] for row in reads}) != len(reads):
        _fail("successor evaluator read URI repeats")
    if (
        type(result_uri) is not str
        or not result_uri.startswith(contract.OUTPUT_NAMESPACE)
        or not result_uri.endswith(f"source-{source_ordinal:03d}.json")
    ):
        _fail("successor evaluator result URI differs")
    result = _with_hash({
        "schema_version": PROCESS_BUDGET_SCHEMA,
        "process_role": "successor-heldout-evaluator",
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "read_allowlist": reads,
        "read_object_count": len(reads),
        "read_byte_ceiling": sum(int(row["identity"]["bytes"]) for row in reads),
        "write_allowlist": [{
            "role": "successor-evaluation-result",
            "uri": result_uri,
            "max_bytes": MAXIMUM_EVALUATION_RESULT_BYTES,
            "create_once": True,
        }],
        "write_object_count": 1,
        "write_byte_ceiling": MAXIMUM_EVALUATION_RESULT_BYTES,
        "heldout_fold_count": contract.FOLDS_PER_SLATE,
        "heldout_worlds_per_fold": contract.WORLDS_PER_BLOCK,
        "selector_fit_count": 0,
        "source_control_evaluator_compatible": False,
        "current_generation_input_lookup_allowed": False,
        "policy": dict(_POLICY),
    }, field="process_budget_sha256")
    if len(_canonical(result)) > MAXIMUM_PROCESS_BUDGET_BYTES:
        _fail("successor evaluator process budget exceeds byte ceiling")
    return result


def validate_evaluator_process_budget_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor evaluator process budget")
    _self_hash(item, field="process_budget_sha256", label="evaluator budget")
    rows = [
        _mapping(row, label="evaluator read row")
        for row in _sequence(item.get("read_allowlist"), label="evaluator reads")
    ]
    by_role = {str(row.get("role")): row.get("identity") for row in rows}
    writes = _sequence(item.get("write_allowlist"), label="evaluator writes")
    if len(by_role) != len(rows) or len(writes) != 1:
        _fail("successor evaluator budget read/write lattice differs")
    write = _mapping(writes[0], label="evaluator result write")
    expected = build_evaluator_process_budget_v1(
        source_ordinal=int(item.get("source_ordinal", -1)),
        slate_id=str(item.get("slate_id", "")),
        selection_task_manifest_identity=by_role.get("selection-task-manifest"),
        source_task_manifest_identity=by_role.get("source-task-manifest"),
        selection_bootstrap_identity=by_role.get("selection-bootstrap"),
        evaluator_bootstrap_identity=by_role.get("evaluator-bootstrap"),
        run_authorization_identity=by_role.get("run-authorization"),
        selection_result_identity=by_role.get("selection-slate-result"),
        projection_bundle_identity=by_role.get("projection-bundle"),
        later_source_identity=by_role.get("later-source"),
        world_artifact_identities={
            f"world_artifact_{block.lower()}": by_role.get(
                f"heldout-world-{block}"
            )
            for block in contract.WORLD_BLOCKS
        },
        result_uri=str(write.get("uri", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor evaluator process budget replay differs")
    return expected


def build_task_binding_v1(
    *, source_ordinal: int, slate_id: str,
    selection_task_binding_sha256: str, selection_result_identity: object,
    projection_bundle_identity: object, process_budget_identity: object,
    result_uri: str,
) -> dict[str, object]:
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < TASK_COUNT
        or _SHA_RE.fullmatch(str(selection_task_binding_sha256)) is None
    ):
        _fail("successor evaluator task binding coordinate differs")
    return _with_hash({
        "schema_version": TASK_BINDING_SCHEMA,
        "task_index": source_ordinal,
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "selection_task_binding_sha256": selection_task_binding_sha256,
        "selection_result_identity": _identity(
            selection_result_identity, label="selection result"
        ),
        "projection_bundle_identity": _identity(
            projection_bundle_identity, label="projection bundle"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="evaluator process budget"
        ),
        "result_uri": result_uri,
        "heldout_fold_count": contract.FOLDS_PER_SLATE,
        "selector_fit_count": 0,
    }, field="task_binding_sha256")


def build_task_manifest_v1(
    *, output_prefix: str, selection_task_manifest_identity: object,
    source_task_manifest_identity: object, selection_bootstrap_identity: object,
    evaluator_bootstrap_identity: object, run_authorization_identity: object,
    code_commit: str, image_digest: str, task_bindings: object,
) -> dict[str, object]:
    prefix = _safe_prefix(output_prefix)
    bindings = [
        _mapping(row, label=f"evaluator task binding[{index}]")
        for index, row in enumerate(_sequence(task_bindings, label="task bindings"))
    ]
    if (
        len(bindings) != TASK_COUNT
        or [row.get("task_index") for row in bindings] != list(range(TASK_COUNT))
        or _COMMIT_RE.fullmatch(str(code_commit)) is None
        or not str(image_digest).startswith("sha256:")
        or _SHA_RE.fullmatch(str(image_digest)[7:]) is None
    ):
        _fail("successor evaluator task manifest lattice differs")
    for index, row in enumerate(bindings):
        expected = build_task_binding_v1(
            source_ordinal=index,
            slate_id=str(row.get("slate_id", "")),
            selection_task_binding_sha256=str(
                row.get("selection_task_binding_sha256", "")
            ),
            selection_result_identity=row.get("selection_result_identity"),
            projection_bundle_identity=row.get("projection_bundle_identity"),
            process_budget_identity=row.get("process_budget_identity"),
            result_uri=str(row.get("result_uri", "")),
        )
        if _canonical(row) != _canonical(expected) or row["result_uri"] != (
            f"{prefix}evaluations/source-{index:03d}.json"
        ):
            _fail(f"successor evaluator task binding[{index}] differs")
    return _with_hash({
        "schema_version": TASK_MANIFEST_SCHEMA,
        "output_prefix": prefix,
        "selection_task_manifest_identity": _identity(
            selection_task_manifest_identity, label="selection task manifest"
        ),
        "source_task_manifest_identity": _identity(
            source_task_manifest_identity, label="source task manifest"
        ),
        "selection_bootstrap_identity": _identity(
            selection_bootstrap_identity, label="selection bootstrap"
        ),
        "evaluator_bootstrap_identity": _identity(
            evaluator_bootstrap_identity, label="evaluator bootstrap"
        ),
        "run_authorization_identity": _identity(
            run_authorization_identity, label="evaluator run authorization"
        ),
        "code_commit": code_commit,
        "image_digest": image_digest,
        "process_spec": process_spec_v1(MODE_EVALUATE),
        "task_count": TASK_COUNT,
        "task_bindings": bindings,
        "task_bindings_sha256": _hash(bindings),
        "one_task_per_slate": True,
        "selector_fit_count": 0,
        "source_control_evaluator_compatible": False,
        "policy": dict(_POLICY),
    }, field="task_manifest_sha256")


def validate_task_manifest_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor evaluator task manifest")
    _self_hash(item, field="task_manifest_sha256", label="evaluator manifest")
    expected = build_task_manifest_v1(
        output_prefix=str(item.get("output_prefix", "")),
        selection_task_manifest_identity=item.get("selection_task_manifest_identity"),
        source_task_manifest_identity=item.get("source_task_manifest_identity"),
        selection_bootstrap_identity=item.get("selection_bootstrap_identity"),
        evaluator_bootstrap_identity=item.get("evaluator_bootstrap_identity"),
        run_authorization_identity=item.get("run_authorization_identity"),
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        task_bindings=item.get("task_bindings"),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor evaluator task manifest replay differs")
    return expected


def prepare_evaluation_task_manifest_v1(
    *, selection_task_manifest_identity: object,
    selection_result_identities: object, output_prefix: str,
    code_commit: str, image_digest: str, reused_job_name: str,
    read_exact: ReadExact, publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Publish one bootstrap, 54 exact budgets, and the evaluation manifest."""
    prefix = _safe_prefix(output_prefix)
    selection_manifest_value, selection_manifest_identity = _read_json(
        selection_task_manifest_identity,
        read_exact=read_exact,
        label="selection task manifest",
        maximum_bytes=selection_cloud.MAXIMUM_TASK_MANIFEST_BYTES,
    )
    source_value, source_identity = _read_json(
        selection_manifest_value["source_control_task_manifest_identity"],
        read_exact=read_exact,
        label="source task manifest",
        maximum_bytes=source_manifest.MAXIMUM_MANIFEST_BYTES,
    )
    selection_bootstrap_value, selection_bootstrap_identity = _read_json(
        selection_manifest_value["bootstrap_identity"],
        read_exact=read_exact,
        label="selection bootstrap",
        maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
    )
    try:
        selection_manifest = selection_cloud.validate_task_manifest_v1(
            selection_manifest_value,
            source_task_manifest=source_value,
            bootstrap=selection_bootstrap_value,
        )
    except selection_cloud.CorpusR6CurrentBankSelectorSuccessorCloudV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
            str(exc)
        ) from exc
    _bind(
        selection_manifest,
        selection_manifest_identity,
        label="selection task manifest",
    )
    result_identities = [
        _identity(row, label=f"selection result[{index}]")
        for index, row in enumerate(
            _sequence(selection_result_identities, label="selection results")
        )
    ]
    if len(result_identities) != TASK_COUNT:
        _fail("successor evaluator preparation requires 54 selection results")
    run_authorization = build_run_authorization_v1(
        selection_task_manifest_identity=selection_manifest_identity,
        output_prefix=prefix,
        code_commit=code_commit,
        image_digest=image_digest,
        reused_job_name=reused_job_name,
    )
    run_authorization_identity = _publish(
        uri=f"{prefix}authorities/evaluator-run-authorization.json",
        value=run_authorization,
        maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    bootstrap = build_bootstrap_v1(
        code_commit=code_commit,
        image_digest=image_digest,
        run_authorization_identity=run_authorization_identity,
    )
    bootstrap_identity = _publish(
        uri=f"{prefix}authorities/evaluator-bootstrap.json",
        value=bootstrap,
        maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    bindings: list[dict[str, object]] = []
    budget_identities: list[dict[str, object]] = []
    for source, (selection_binding, selection_result_identity) in enumerate(
        zip(
            selection_manifest["task_bindings"],
            result_identities,
            strict=True,
        )
    ):
        if selection_result_identity["uri"] != selection_binding["result_uri"]:
            _fail("selection result URI differs from selection task binding")
        selection_result, retained_selection_identity = _read_json(
            selection_result_identity,
            read_exact=read_exact,
            label=f"selection result[{source}]",
            maximum_bytes=MAXIMUM_SELECTION_RESULT_BYTES,
        )
        bundle, bundle_identity = _read_json(
            selection_binding["projection_bundle_identity"],
            read_exact=read_exact,
            label=f"projection bundle[{source}]",
            maximum_bytes=MAXIMUM_PROJECTION_BYTES,
        )
        try:
            retained_bundle = contract.validate_projection_bundle_v1(bundle)
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
                str(exc)
            ) from exc
        _bind(retained_bundle, bundle_identity, label="projection bundle")
        evaluation._validate_selection_slate_result_v1(
            selection_result, projection_bundle=retained_bundle
        )
        _bind(
            selection_result,
            retained_selection_identity,
            label="selection result",
        )
        if (
            retained_bundle["source_ordinal"] != source
            or selection_result["source_ordinal"] != source
            or selection_result["slate_id"] != retained_bundle["slate_id"]
        ):
            _fail("successor evaluation preparation source/slate differs")
        projection0 = retained_bundle["fold_projections"][0]
        result_uri = f"{prefix}evaluations/source-{source:03d}.json"
        budget = build_evaluator_process_budget_v1(
            source_ordinal=source,
            slate_id=str(retained_bundle["slate_id"]),
            selection_task_manifest_identity=selection_manifest_identity,
            source_task_manifest_identity=source_identity,
            selection_bootstrap_identity=selection_bootstrap_identity,
            evaluator_bootstrap_identity=bootstrap_identity,
            run_authorization_identity=run_authorization_identity,
            selection_result_identity=retained_selection_identity,
            projection_bundle_identity=bundle_identity,
            later_source_identity=projection0["later_source_identity"],
            world_artifact_identities=projection0[
                "world_artifact_identities"
            ],
            result_uri=result_uri,
        )
        budget_identity = _publish(
            uri=(
                f"{prefix}authorities/evaluator-process-budgets/"
                f"source-{source:03d}.json"
            ),
            value=budget,
            maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
        budget_identities.append(budget_identity)
        bindings.append(build_task_binding_v1(
            source_ordinal=source,
            slate_id=str(retained_bundle["slate_id"]),
            selection_task_binding_sha256=str(
                selection_binding["task_binding_sha256"]
            ),
            selection_result_identity=retained_selection_identity,
            projection_bundle_identity=bundle_identity,
            process_budget_identity=budget_identity,
            result_uri=result_uri,
        ))
    manifest = build_task_manifest_v1(
        output_prefix=prefix,
        selection_task_manifest_identity=selection_manifest_identity,
        source_task_manifest_identity=source_identity,
        selection_bootstrap_identity=selection_bootstrap_identity,
        evaluator_bootstrap_identity=bootstrap_identity,
        run_authorization_identity=run_authorization_identity,
        code_commit=code_commit,
        image_digest=image_digest,
        task_bindings=bindings,
    )
    manifest_identity = _publish(
        uri=f"{prefix}authorities/evaluator-task-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    return {
        "schema_version": (
            "corpus-r6-current-bank-selector-successor-evaluation-preparation/v1"
        ),
        "run_authorization_identity": run_authorization_identity,
        "bootstrap_identity": bootstrap_identity,
        "task_manifest_identity": manifest_identity,
        "process_budget_identities": budget_identities,
        "task_count": TASK_COUNT,
        "heldout_fold_count": TASK_COUNT * contract.FOLDS_PER_SLATE,
        "selector_fit_count": 0,
        "job_configuration": build_evaluation_job_configuration_v1(
            task_manifest=manifest,
            task_manifest_identity=manifest_identity,
            reused_job_name=reused_job_name,
        ),
    }


def derive_runtime_evidence_v1(
    *, mode: str, environ: Mapping[str, str], observed_command: object,
    pid: int, parent_pid: int,
) -> dict[str, object]:
    env = dict(environ)
    command = [str(value) for value in _sequence(observed_command, label="command")]
    count = TASK_COUNT if mode == MODE_EVALUATE else 1
    index_text = env.get("CLOUD_RUN_TASK_INDEX", "")
    count_text = env.get("CLOUD_RUN_TASK_COUNT", "")
    if (
        command != canonical_command_v1(mode)
        or any(env.get(key) for key in _REDIRECT_ENV_KEYS)
        or env.get(ENABLE_ENV) != "1"
        or env.get("GOOGLE_CLOUD_PROJECT") != FIXED_GCP_PROJECT
        or not index_text.isdecimal()
        or not count_text.isdecimal()
        or int(count_text) != count
        or int(index_text) != 0 and mode == MODE_AGGREGATE
        or not 0 <= int(index_text) < count
        or env.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
        or _COMMIT_RE.fullmatch(env.get("CODE_SHA", "")) is None
        or not env.get("R6_RUNTIME_IMAGE_DIGEST", "").startswith("sha256:")
        or _SHA_RE.fullmatch(env.get("R6_RUNTIME_IMAGE_DIGEST", "")[7:]) is None
        or not env.get("CLOUD_RUN_JOB")
        or not env.get("CLOUD_RUN_EXECUTION")
        or type(pid) is not int
        or type(parent_pid) is not int
        or pid < 1
        or parent_pid < 1
        or pid == parent_pid
    ):
        _fail("successor evaluator observed runtime differs")
    spec = process_spec_v1(mode)
    return _with_hash({
        "schema_version": RUNTIME_SCHEMA,
        "runtime_mode": mode,
        "project_id": FIXED_GCP_PROJECT,
        "storage_endpoint": FIXED_STORAGE_ENDPOINT,
        "code_commit": env["CODE_SHA"],
        "image_digest": env["R6_RUNTIME_IMAGE_DIGEST"],
        "job_name": env["CLOUD_RUN_JOB"],
        "execution_id": env["CLOUD_RUN_EXECUTION"],
        "task_index": int(index_text),
        "task_count": int(count_text),
        "task_attempt": 0,
        "pid": pid,
        "parent_pid": parent_pid,
        "entrypoint_path": spec["entrypoint_path"],
        "entrypoint_sha256": spec["entrypoint_sha256"],
        "command": command,
        "command_sha256": spec["command_sha256"],
        "source_control_evaluator_compatibility_claimed": False,
        "terminal_cloud_execution_attestation_present": False,
    }, field="runtime_evidence_sha256")


class ExactScientificReadGateV1:
    """One ordered, exhaustive scientific capability; no listing or lookup."""

    def __init__(
        self, *, rows: Sequence[Mapping[str, object]], read_exact: ReadExact,
    ) -> None:
        self._rows = [
            {"role": str(row["role"]), "identity": _identity(
                row["identity"], label=f"scientific {row['role']}"
            )}
            for row in rows
        ]
        expected = [
            "later-source",
            *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS],
        ]
        if (
            [row["role"] for row in self._rows] != expected
            or len({row["identity"]["uri"] for row in self._rows}) != len(expected)
        ):
            _fail("successor scientific capability lattice differs")
        self._read_exact = read_exact
        self._ordinal = 0
        self.ledger: list[dict[str, object]] = []

    def read(self, role: str, identity_value: object) -> bytes:
        if self._ordinal >= len(self._rows):
            _fail("successor scientific capability is exhausted")
        row = self._rows[self._ordinal]
        identity = _identity(identity_value, label=f"scientific read {role}")
        if row != {"role": role, "identity": identity}:
            _fail("successor scientific read role/order/identity differs")
        raw = self._read_exact(identity)
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("successor scientific exact bytes differ")
        self.ledger.append({
            "ordinal": self._ordinal, "role": role, "identity": identity
        })
        self._ordinal += 1
        return raw

    def require_complete(self) -> list[dict[str, object]]:
        if self._ordinal != len(self._rows):
            _fail("successor scientific capability was not exhausted exactly")
        return list(self.ledger)


def run_evaluator_task_v1(
    *, task_manifest: object, task_manifest_identity: object,
    observed_runtime: object, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce, score_heldout: ScoreHeldout,
) -> dict[str, object]:
    manifest = validate_task_manifest_v1(task_manifest)
    manifest_identity = _bind(
        manifest, task_manifest_identity, label="evaluator task manifest"
    )
    runtime = _mapping(observed_runtime, label="evaluator observed runtime")
    _self_hash(runtime, field="runtime_evidence_sha256", label="evaluator runtime")
    source = int(runtime.get("task_index", -1))
    if (
        runtime.get("schema_version") != RUNTIME_SCHEMA
        or runtime.get("runtime_mode") != MODE_EVALUATE
        or runtime.get("task_count") != TASK_COUNT
        or runtime.get("code_commit") != manifest["code_commit"]
        or runtime.get("image_digest") != manifest["image_digest"]
        or not 0 <= source < TASK_COUNT
    ):
        _fail("successor evaluator runtime/manifest differs")
    binding = manifest["task_bindings"][source]
    budget_value, budget_identity = _read_json(
        binding["process_budget_identity"], read_exact=read_exact,
        label="evaluator process budget", maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
    )
    budget = validate_evaluator_process_budget_v1(budget_value)
    _bind(budget, budget_identity, label="evaluator process budget")
    by_role = {
        str(row["role"]): row["identity"] for row in budget["read_allowlist"]
    }
    selection_manifest_value, _ = _read_json(
        by_role["selection-task-manifest"], read_exact=read_exact,
        label="selection task manifest", maximum_bytes=selection_cloud.MAXIMUM_TASK_MANIFEST_BYTES,
    )
    source_manifest_value, _ = _read_json(
        by_role["source-task-manifest"], read_exact=read_exact,
        label="source task manifest", maximum_bytes=source_manifest.MAXIMUM_MANIFEST_BYTES,
    )
    selection_bootstrap_value, _ = _read_json(
        by_role["selection-bootstrap"], read_exact=read_exact,
        label="selection bootstrap", maximum_bytes=selection_cloud.MAXIMUM_TASK_MANIFEST_BYTES,
    )
    try:
        selection_manifest = selection_cloud.validate_task_manifest_v1(
            selection_manifest_value,
            source_task_manifest=source_manifest_value,
            bootstrap=selection_bootstrap_value,
        )
    except selection_cloud.CorpusR6CurrentBankSelectorSuccessorCloudV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(
            str(exc)
        ) from exc
    if (
        selection_manifest["task_bindings"][source]["task_binding_sha256"]
        != binding["selection_task_binding_sha256"]
        or by_role["selection-slate-result"] != binding["selection_result_identity"]
        or by_role["projection-bundle"] != binding["projection_bundle_identity"]
        or budget["source_ordinal"] != source
        or budget["slate_id"] != binding["slate_id"]
    ):
        _fail("successor evaluator predecessor task binding differs")
    selection_result, selection_identity = _read_json(
        by_role["selection-slate-result"], read_exact=read_exact,
        label="selection slate result", maximum_bytes=MAXIMUM_SELECTION_RESULT_BYTES,
    )
    bundle, bundle_identity = _read_json(
        by_role["projection-bundle"], read_exact=read_exact,
        label="projection bundle", maximum_bytes=MAXIMUM_PROJECTION_BYTES,
    )
    try:
        retained_bundle = contract.validate_projection_bundle_v1(bundle)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error(str(exc)) from exc
    _bind(retained_bundle, bundle_identity, label="projection bundle")
    if retained_bundle["source_ordinal"] != source:
        _fail("successor evaluator projection source differs")
    evaluator_bootstrap, _ = _read_json(
        by_role["evaluator-bootstrap"], read_exact=read_exact,
        label="evaluator bootstrap", maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
    )
    retained_evaluator_bootstrap = validate_bootstrap_v1(evaluator_bootstrap)
    run_authorization, _ = _read_json(
        by_role["run-authorization"], read_exact=read_exact,
        label="evaluator run authorization", maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
    )
    retained_run_authorization = validate_run_authorization_v1(
        run_authorization
    )
    if (
        retained_evaluator_bootstrap.get("code_commit") != runtime["code_commit"]
        or retained_evaluator_bootstrap.get("image_digest") != runtime["image_digest"]
        or retained_evaluator_bootstrap.get("run_authorization_identity")
        != by_role["run-authorization"]
        or retained_run_authorization["selection_task_manifest_identity"]
        != by_role["selection-task-manifest"]
        or retained_run_authorization["reused_job_name"]
        != runtime["job_name"]
    ):
        _fail("successor evaluator bootstrap/runtime differs")
    scientific_rows = [
        row for row in budget["read_allowlist"]
        if row["role"] == "later-source"
        or str(row["role"]).startswith("heldout-world-")
    ]
    gate = ExactScientificReadGateV1(rows=scientific_rows, read_exact=read_exact)
    later_raw = gate.read("later-source", by_role["later-source"])
    later_body = _strict_json(later_raw, label="later source")
    _bind(later_body, by_role["later-source"], label="later source")
    fold_inputs = []
    for fold, block in enumerate(contract.WORLD_BLOCKS):
        role = f"heldout-world-{block}"
        identity = by_role[role]
        raw = gate.read(role, identity)
        scores = score_heldout(
            projection=retained_bundle["fold_projections"][fold],
            later_source_body=later_body,
            heldout_artifact_identity=identity,
            raw_artifact=raw,
        )
        fold_inputs.append({
            "fold_ordinal": fold,
            "heldout_artifact_identity": identity,
            "heldout_score_matrix": scores,
        })
    execution_binding = evaluation.build_evaluation_execution_binding_v1(
        source_ordinal=source,
        slate_id=str(binding["slate_id"]),
        task_manifest_identity=manifest_identity,
        process_budget_identity=budget_identity,
        runtime_evidence=runtime,
    )
    result = evaluation.build_evaluation_result_v1(
        selection_slate_result=selection_result,
        selection_slate_result_identity=selection_identity,
        projection_bundle=retained_bundle,
        projection_bundle_identity=bundle_identity,
        heldout_fold_input_stream=fold_inputs,
        later_source_body=later_body,
        execution_binding=execution_binding,
    )
    write = budget["write_allowlist"][0]
    published = _publish(
        uri=str(write["uri"]), value=result,
        maximum_bytes=int(write["max_bytes"]),
        publish_create_once=publish_create_once, read_exact=read_exact,
    )
    ledger = gate.require_complete()
    envelope = _with_hash({
        "schema_version": TASK_ENVELOPE_SCHEMA,
        "source_ordinal": source,
        "slate_id": binding["slate_id"],
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "process_budget_identity": budget_identity,
        "process_budget_sha256": budget["process_budget_sha256"],
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "scientific_read_ledger": ledger,
        "scientific_read_ledger_sha256": _hash(ledger),
        "evaluation_result_sha256": result["evaluation_result_sha256"],
        "evaluation_result_identity": published,
        "publication_mode": "create-once-exact-reopen",
        "source_control_evaluator_invoked": False,
        "policy": dict(_POLICY),
    }, field="task_envelope_sha256")
    if len(_canonical(envelope)) > MAXIMUM_ENVELOPE_BYTES:
        _fail("successor evaluator task envelope exceeds byte ceiling")
    return envelope


def build_terminal_process_budget_v1(
    *, evaluator_task_manifest_identity: object,
    evaluation_result_identities: object, result_uri: str,
) -> dict[str, object]:
    identities = [
        _identity(row, label=f"evaluation result[{index}]")
        for index, row in enumerate(
            _sequence(evaluation_result_identities, label="evaluation identities")
        )
    ]
    if len(identities) != TASK_COUNT or len({row["uri"] for row in identities}) != TASK_COUNT:
        _fail("successor terminal evaluation identity panel differs")
    reads = [{
        "role": "evaluator-task-manifest",
        "identity": _identity(
            evaluator_task_manifest_identity, label="evaluator task manifest"
        ),
    }, *[
        {"role": f"evaluation-source-{source:03d}", "identity": identity}
        for source, identity in enumerate(identities)
    ]]
    if (
        type(result_uri) is not str
        or not result_uri.startswith(contract.OUTPUT_NAMESPACE)
        or not result_uri.endswith("terminal-aggregate.json")
    ):
        _fail("successor terminal result URI differs")
    return _with_hash({
        "schema_version": TERMINAL_PROCESS_BUDGET_SCHEMA,
        "process_role": "successor-terminal-aggregator",
        "read_allowlist": reads,
        "read_object_count": len(reads),
        "read_byte_ceiling": sum(int(row["identity"]["bytes"]) for row in reads),
        "write_allowlist": [{
            "role": "successor-terminal-aggregate",
            "uri": result_uri,
            "max_bytes": MAXIMUM_TERMINAL_RESULT_BYTES,
            "create_once": True,
        }],
        "write_object_count": 1,
        "write_byte_ceiling": MAXIMUM_TERMINAL_RESULT_BYTES,
        "expected_evaluation_count": TASK_COUNT,
        "realized_outcome_read_allowed": False,
        "source_control_aggregate_compatible": False,
        "policy": dict(_POLICY),
    }, field="terminal_process_budget_sha256")


def validate_terminal_process_budget_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor terminal process budget")
    _self_hash(
        item, field="terminal_process_budget_sha256", label="terminal budget"
    )
    reads = [
        _mapping(row, label=f"terminal read[{index}]")
        for index, row in enumerate(
            _sequence(item.get("read_allowlist"), label="terminal reads")
        )
    ]
    writes = _sequence(item.get("write_allowlist"), label="terminal writes")
    if (
        len(reads) != TASK_COUNT + 1
        or reads[0].get("role") != "evaluator-task-manifest"
        or [row.get("role") for row in reads[1:]]
        != [f"evaluation-source-{source:03d}" for source in range(TASK_COUNT)]
        or len(writes) != 1
    ):
        _fail("successor terminal process budget lattice differs")
    write = _mapping(writes[0], label="terminal write")
    expected = build_terminal_process_budget_v1(
        evaluator_task_manifest_identity=reads[0].get("identity"),
        evaluation_result_identities=[row.get("identity") for row in reads[1:]],
        result_uri=str(write.get("uri", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor terminal process budget replay differs")
    return expected


def build_terminal_manifest_v1(
    *, evaluator_task_manifest_identity: object,
    terminal_process_budget_identity: object, code_commit: str,
    image_digest: str, reused_job_name: str,
) -> dict[str, object]:
    if (
        _COMMIT_RE.fullmatch(str(code_commit)) is None
        or not str(image_digest).startswith("sha256:")
        or _SHA_RE.fullmatch(str(image_digest)[7:]) is None
        or _JOB_RE.fullmatch(str(reused_job_name)) is None
    ):
        _fail("successor terminal runtime identity differs")
    return _with_hash({
        "schema_version": TERMINAL_MANIFEST_SCHEMA,
        "evaluator_task_manifest_identity": _identity(
            evaluator_task_manifest_identity, label="evaluator task manifest"
        ),
        "terminal_process_budget_identity": _identity(
            terminal_process_budget_identity, label="terminal process budget"
        ),
        "code_commit": code_commit,
        "image_digest": image_digest,
        "reused_job_name": reused_job_name,
        "process_spec": process_spec_v1(MODE_AGGREGATE),
        "task_count": 1,
        "realized_outcome_identity_present": False,
        "policy": dict(_POLICY),
    }, field="terminal_manifest_sha256")


def validate_terminal_manifest_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="successor terminal manifest")
    _self_hash(
        item, field="terminal_manifest_sha256", label="terminal manifest"
    )
    expected = build_terminal_manifest_v1(
        evaluator_task_manifest_identity=item.get(
            "evaluator_task_manifest_identity"
        ),
        terminal_process_budget_identity=item.get(
            "terminal_process_budget_identity"
        ),
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        reused_job_name=str(item.get("reused_job_name", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor terminal manifest replay differs")
    return expected


def build_terminal_job_configuration_v1(
    *, terminal_manifest: object, terminal_manifest_identity: object,
    reused_job_name: str,
) -> dict[str, object]:
    manifest = _mapping(terminal_manifest, label="terminal manifest")
    _self_hash(
        manifest, field="terminal_manifest_sha256", label="terminal manifest"
    )
    identity = _bind(
        manifest, terminal_manifest_identity, label="terminal manifest"
    )
    if (
        manifest.get("schema_version") != TERMINAL_MANIFEST_SCHEMA
        or manifest.get("process_spec") != process_spec_v1(MODE_AGGREGATE)
        or _JOB_RE.fullmatch(str(reused_job_name)) is None
        or manifest.get("reused_job_name") != reused_job_name
    ):
        _fail("successor terminal job configuration authority differs")
    environment = {
        ENABLE_ENV: "1",
        TERMINAL_MANIFEST_IDENTITY_ENV: _canonical(identity).decode("utf-8"),
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["image_digest"],
    }
    return _with_hash({
        "schema_version": (
            "corpus-r6-current-bank-selector-successor-terminal-job-config/v1"
        ),
        "reused_job_name": reused_job_name,
        "terminal_manifest_identity": identity,
        "image_digest": manifest["image_digest"],
        "container_command": [PYTHON_IMAGE_PATH],
        "container_args": ["-I", ENTRYPOINT_IMAGE_PATH, MODE_AGGREGATE],
        "container_environment": environment,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "timeout_seconds": TERMINAL_TIMEOUT_SECONDS,
        "cpu": source_manifest.FIXED_CLOUD_RUN_CPU_LIMIT,
        "memory": source_manifest.FIXED_CLOUD_RUN_MEMORY_LIMIT,
        "new_job_creation_allowed": False,
        "source_control_aggregate_compatible": False,
    }, field="job_configuration_sha256")


def prepare_terminal_manifest_v1(
    *, evaluator_task_manifest_identity: object,
    evaluation_result_identities: object, result_uri: str,
    reused_job_name: str, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Validate all 54 results and publish one exact terminal manifest."""
    evaluator_manifest_value, evaluator_manifest_identity = _read_json(
        evaluator_task_manifest_identity,
        read_exact=read_exact,
        label="evaluator task manifest",
        maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
    )
    evaluator_manifest = validate_task_manifest_v1(evaluator_manifest_value)
    _bind(
        evaluator_manifest,
        evaluator_manifest_identity,
        label="evaluator task manifest",
    )
    identities = [
        _identity(row, label=f"evaluation result[{source}]")
        for source, row in enumerate(
            _sequence(evaluation_result_identities, label="evaluation results")
        )
    ]
    if len(identities) != TASK_COUNT:
        _fail("successor terminal preparation requires 54 evaluations")
    for source, (identity, binding) in enumerate(
        zip(identities, evaluator_manifest["task_bindings"], strict=True)
    ):
        if identity["uri"] != binding["result_uri"]:
            _fail("evaluation result URI differs from evaluator task binding")
        result, retained_identity = _read_json(
            identity,
            read_exact=read_exact,
            label=f"evaluation result[{source}]",
            maximum_bytes=MAXIMUM_EVALUATION_RESULT_BYTES,
        )
        retained = evaluation.validate_evaluation_result_v1(result)
        _bind(retained, retained_identity, label=f"evaluation result[{source}]")
        if (
            retained["source_ordinal"] != source
            or retained["slate_id"] != binding["slate_id"]
            or retained["execution_authority_present"] is not True
            or retained["execution_binding"]["task_manifest_identity"]
            != evaluator_manifest_identity
            or retained["execution_binding"]["process_budget_identity"]
            != binding["process_budget_identity"]
        ):
            _fail("successor terminal evaluation execution authority differs")
    budget = build_terminal_process_budget_v1(
        evaluator_task_manifest_identity=evaluator_manifest_identity,
        evaluation_result_identities=identities,
        result_uri=result_uri,
    )
    prefix = result_uri.rsplit("terminal-aggregate.json", 1)[0]
    _safe_prefix(prefix)
    budget_identity = _publish(
        uri=f"{prefix}authorities/terminal-process-budget.json",
        value=budget,
        maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    manifest = build_terminal_manifest_v1(
        evaluator_task_manifest_identity=evaluator_manifest_identity,
        terminal_process_budget_identity=budget_identity,
        code_commit=str(evaluator_manifest["code_commit"]),
        image_digest=str(evaluator_manifest["image_digest"]),
        reused_job_name=reused_job_name,
    )
    manifest_identity = _publish(
        uri=f"{prefix}authorities/terminal-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_BOOTSTRAP_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    return {
        "schema_version": (
            "corpus-r6-current-bank-selector-successor-terminal-preparation/v1"
        ),
        "terminal_process_budget_identity": budget_identity,
        "terminal_manifest_identity": manifest_identity,
        "evaluation_count": TASK_COUNT,
        "job_configuration": build_terminal_job_configuration_v1(
            terminal_manifest=manifest,
            terminal_manifest_identity=manifest_identity,
            reused_job_name=reused_job_name,
        ),
    }


def run_terminal_task_v1(
    *, terminal_manifest: object, terminal_manifest_identity: object,
    observed_runtime: object, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    manifest = validate_terminal_manifest_v1(terminal_manifest)
    manifest_identity = _bind(
        manifest, terminal_manifest_identity, label="terminal manifest"
    )
    runtime = _mapping(observed_runtime, label="terminal runtime")
    _self_hash(runtime, field="runtime_evidence_sha256", label="terminal runtime")
    if (
        manifest.get("schema_version") != TERMINAL_MANIFEST_SCHEMA
        or manifest.get("process_spec") != process_spec_v1(MODE_AGGREGATE)
        or manifest.get("task_count") != 1
        or manifest.get("realized_outcome_identity_present") is not False
        or runtime.get("runtime_mode") != MODE_AGGREGATE
        or runtime.get("task_index") != 0
        or runtime.get("task_count") != 1
        or runtime.get("code_commit") != manifest.get("code_commit")
        or runtime.get("image_digest") != manifest.get("image_digest")
        or runtime.get("job_name") != manifest.get("reused_job_name")
    ):
        _fail("successor terminal manifest/runtime differs")
    budget_value, budget_identity = _read_json(
        manifest["terminal_process_budget_identity"], read_exact=read_exact,
        label="terminal process budget", maximum_bytes=MAXIMUM_PROCESS_BUDGET_BYTES,
    )
    budget = validate_terminal_process_budget_v1(budget_value)
    if (
        budget.get("schema_version") != TERMINAL_PROCESS_BUDGET_SCHEMA
        or budget.get("expected_evaluation_count") != TASK_COUNT
        or budget.get("realized_outcome_read_allowed") is not False
    ):
        _fail("successor terminal process budget differs")
    rows = list(budget["read_allowlist"])
    evaluator_manifest, evaluator_manifest_identity = _read_json(
        rows[0]["identity"], read_exact=read_exact,
        label="evaluator task manifest", maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
    )
    retained_evaluator_manifest = validate_task_manifest_v1(evaluator_manifest)
    _bind(
        retained_evaluator_manifest,
        evaluator_manifest_identity,
        label="evaluator task manifest",
    )
    if evaluator_manifest_identity != manifest["evaluator_task_manifest_identity"]:
        _fail("successor terminal evaluator manifest differs")
    publications = []
    for source, row in enumerate(rows[1:]):
        if row["role"] != f"evaluation-source-{source:03d}":
            _fail("successor terminal evaluation read order differs")
        result, identity = _read_json(
            row["identity"], read_exact=read_exact,
            label=f"evaluation result[{source}]",
            maximum_bytes=MAXIMUM_EVALUATION_RESULT_BYTES,
        )
        retained_result = evaluation.validate_evaluation_result_v1(result)
        if (
            retained_result["source_ordinal"] != source
            or retained_result["execution_binding"]["task_manifest_identity"]
            != evaluator_manifest_identity
        ):
            _fail("successor terminal evaluation authority differs")
        publications.append({
            "evaluation_result": retained_result,
            "evaluation_identity": identity,
        })
    terminal_execution = evaluation.build_terminal_execution_binding_v1(
        terminal_manifest_identity=manifest_identity,
        process_budget_identity=budget_identity,
        runtime_evidence=runtime,
    )
    terminal = evaluation.build_terminal_aggregate_v1(
        evaluation_publications=publications,
        execution_binding=terminal_execution,
    )
    write = budget["write_allowlist"][0]
    published = _publish(
        uri=str(write["uri"]), value=terminal,
        maximum_bytes=int(write["max_bytes"]),
        publish_create_once=publish_create_once, read_exact=read_exact,
    )
    envelope = _with_hash({
        "schema_version": TERMINAL_ENVELOPE_SCHEMA,
        "terminal_manifest_identity": manifest_identity,
        "terminal_manifest_sha256": manifest["terminal_manifest_sha256"],
        "terminal_process_budget_identity": budget_identity,
        "terminal_process_budget_sha256": budget[
            "terminal_process_budget_sha256"
        ],
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "terminal_aggregate_identity": published,
        "terminal_aggregate_sha256": terminal["terminal_aggregate_sha256"],
        "evaluation_count": TASK_COUNT,
        "realized_outcome_read_count": 0,
        "publication_mode": "create-once-exact-reopen",
        "policy": dict(_POLICY),
    }, field="terminal_envelope_sha256")
    if len(_canonical(envelope)) > MAXIMUM_ENVELOPE_BYTES:
        _fail("successor terminal envelope exceeds byte ceiling")
    return envelope


def build_evaluation_job_configuration_v1(
    *, task_manifest: object, task_manifest_identity: object,
    reused_job_name: str,
) -> dict[str, object]:
    manifest = validate_task_manifest_v1(task_manifest)
    manifest_identity = _bind(
        manifest, task_manifest_identity, label="evaluator task manifest"
    )
    if _JOB_RE.fullmatch(str(reused_job_name)) is None:
        _fail("successor evaluator reused job name differs")
    environment = {
        ENABLE_ENV: "1",
        MANIFEST_IDENTITY_ENV: _canonical(manifest_identity).decode("utf-8"),
        "GOOGLE_CLOUD_PROJECT": FIXED_GCP_PROJECT,
        "CODE_SHA": manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["image_digest"],
    }
    return _with_hash({
        "schema_version": (
            "corpus-r6-current-bank-selector-successor-evaluation-job-config/v1"
        ),
        "reused_job_name": reused_job_name,
        "task_manifest_identity": manifest_identity,
        "image_digest": manifest["image_digest"],
        "container_command": [PYTHON_IMAGE_PATH],
        "container_args": ["-I", ENTRYPOINT_IMAGE_PATH, MODE_EVALUATE],
        "container_environment": environment,
        "task_count": TASK_COUNT,
        "parallelism": TASK_COUNT,
        "max_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "cpu": source_manifest.FIXED_CLOUD_RUN_CPU_LIMIT,
        "memory": source_manifest.FIXED_CLOUD_RUN_MEMORY_LIMIT,
        "new_job_creation_allowed": False,
        "source_control_evaluator_compatible": False,
    }, field="job_configuration_sha256")


__all__ = [
    "BOOTSTRAP_SCHEMA", "ENABLE_ENV", "ENTRYPOINT_IMAGE_PATH",
    "MANIFEST_IDENTITY_ENV", "MODE_AGGREGATE", "MODE_EVALUATE",
    "PROCESS_BUDGET_SCHEMA", "RUNTIME_SCHEMA", "TASK_COUNT",
    "TASK_MANIFEST_SCHEMA", "TERMINAL_MANIFEST_IDENTITY_ENV",
    "TERMINAL_MANIFEST_SCHEMA", "TERMINAL_PROCESS_BUDGET_SCHEMA",
    "CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error",
    "ExactScientificReadGateV1", "build_bootstrap_v1",
    "build_evaluation_job_configuration_v1",
    "build_evaluator_process_budget_v1", "build_run_authorization_v1",
    "build_task_binding_v1", "build_task_manifest_v1",
    "build_terminal_job_configuration_v1", "build_terminal_manifest_v1",
    "build_terminal_process_budget_v1", "prepare_evaluation_task_manifest_v1",
    "prepare_terminal_manifest_v1",
    "canonical_command_v1", "derive_runtime_evidence_v1", "process_spec_v1",
    "run_evaluator_task_v1", "run_terminal_task_v1",
    "validate_bootstrap_v1", "validate_evaluator_process_budget_v1",
    "validate_run_authorization_v1", "validate_task_manifest_v1",
    "validate_terminal_manifest_v1", "validate_terminal_process_budget_v1",
]
