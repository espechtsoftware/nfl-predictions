"""Pure fresh-run preparation for crossed-screen task layers one through seven.

This module owns no cloud, subprocess, storage-discovery, outcome, or graph
capability.  One exact projection-preparation receipt and the registry-required
generation-pinned predecessor layer receipts are its entire authority input.
Every process budget and request is derived from those reopened authorities,
published create-once at a deterministic URI, exact-reopened, and finally
bound by one immutable task manifest plus a compact preparation receipt.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_projection_preparation_v1
    as projection_preparation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


LAYER_PREPARATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-layer-preparation-receipt/v1"
)
MAXIMUM_LAYER_PREPARATION_RECEIPT_BYTES: Final = 4_000_000
MAXIMUM_PROJECTION_BUNDLE_BYTES: Final = 256_000_000
MAXIMUM_NOMINATION_BYTES: Final = 16_000_000

_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], object]


class CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(ValueError):
    """A later-layer immutable preparation authority could not be proven."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    if hasattr(value, "as_dict") and callable(value.as_dict):
        value = value.as_dict()
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc


def _canonical_bytes(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc


def _canonical_sha(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    body[field] = _canonical_sha(body)
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    observed = value.get(field)
    body = {key: row for key, row in value.items() if key != field}
    if (
        type(observed) is not str
        or _SHA256_RE.fullmatch(observed) is None
        or observed != _canonical_sha(body)
    ):
        _fail(f"{label} self hash differs")


def _bind_body(
    value: Mapping[str, object], identity_value: object, *, label: str,
) -> dict[str, object]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = _canonical_bytes(value)
    if (
        int(identity["bytes"]) != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} body identity differs")
    return identity


def _read_json_exact(
    identity_value: object, *, read_exact: ReadExact, label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its exact-read byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != int(identity["bytes"])
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact body differs")
    try:
        body = task_manifest.strict_json_v1(raw, label=label)
    except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc
    return body, identity


def _publish_json_create_once(
    *, uri: str, value: Mapping[str, object], maximum_bytes: int,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    try:
        identity = task_manifest.publish_create_once_or_exact_prior_v1(
            uri=uri,
            value=value,
            prior_identity=None,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            maximum_bytes=maximum_bytes,
        )
    except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc
    return _bind_body(value, identity, label="created layer authority")


def _target_descriptor(
    *, output_prefix: str, layer_id: str, layer_ordinal: int,
) -> dict[str, object]:
    registry = task_manifest.layer_registry_v1(output_prefix)
    rows = [row for row in registry if row["layer_id"] == layer_id]
    if (
        len(rows) != 1
        or rows[0]["layer_ordinal"] != layer_ordinal
        or layer_ordinal <= 0
    ):
        _fail("target layer ID/ordinal is not a registered later layer")
    return dict(rows[0])


def layer_preparation_authority_plan_v1(
    *, output_prefix: str, layer_id: str, layer_ordinal: int,
) -> list[dict[str, object]]:
    """Return the only budget/request/manifest publication order for a layer."""
    topology = contract.build_result_topology_v1(output_prefix)
    prefix = str(topology["output_prefix"])
    descriptor = _target_descriptor(
        output_prefix=prefix,
        layer_id=layer_id,
        layer_ordinal=layer_ordinal,
    )
    base = (
        f"{prefix}authorities/layer-preparation/"
        f"{layer_ordinal:02d}-{layer_id}/"
    )
    plan: list[dict[str, object]] = []
    for task_index in range(int(descriptor["task_count"])):
        if descriptor["request_kind"] == "selection":
            for fold_ordinal in range(contract.FOLDS_PER_SLATE):
                plan.append({
                    "publication_ordinal": len(plan),
                    "authority_role": "worker-process-budget",
                    "task_index": task_index,
                    "fold_ordinal": fold_ordinal,
                    "uri": (
                        f"{base}task-{task_index:03d}/"
                        f"fold-{fold_ordinal:02d}-process-budget.json"
                    ),
                    "maximum_bytes": task_manifest.MAXIMUM_PROCESS_BUDGET_BYTES,
                    "body_self_hash_field": "process_budget_sha256",
                })
            plan.append({
                "publication_ordinal": len(plan),
                "authority_role": "assembler-process-budget",
                "task_index": task_index,
                "fold_ordinal": None,
                "uri": f"{base}task-{task_index:03d}/assembler-process-budget.json",
                "maximum_bytes": task_manifest.MAXIMUM_PROCESS_BUDGET_BYTES,
                "body_self_hash_field": "process_budget_sha256",
            })
            request_hash = "assembler_request_sha256"
        else:
            budget_hash = (
                "evaluator_process_budget_sha256"
                if descriptor["request_kind"] == "evaluation"
                else "publisher_process_budget_sha256"
            )
            plan.append({
                "publication_ordinal": len(plan),
                "authority_role": "process-budget",
                "task_index": task_index,
                "fold_ordinal": None,
                "uri": f"{base}task-{task_index:03d}/process-budget.json",
                "maximum_bytes": task_manifest.MAXIMUM_PROCESS_BUDGET_BYTES,
                "body_self_hash_field": budget_hash,
            })
            request_hash = (
                "evaluator_request_sha256"
                if descriptor["request_kind"] == "evaluation"
                else "publisher_request_sha256"
            )
        plan.append({
            "publication_ordinal": len(plan),
            "authority_role": "task-request",
            "task_index": task_index,
            "fold_ordinal": None,
            "uri": f"{base}task-{task_index:03d}/request.json",
            "maximum_bytes": int(descriptor["request_byte_ceiling"]),
            "body_self_hash_field": request_hash,
        })
    plan.append({
        "publication_ordinal": len(plan),
        "authority_role": "task-manifest",
        "task_index": None,
        "fold_ordinal": None,
        "uri": str(descriptor["manifest_uri"]),
        "maximum_bytes": task_manifest.MAXIMUM_MANIFEST_BYTES,
        "body_self_hash_field": "task_manifest_sha256",
    })
    if len({str(row["uri"]) for row in plan}) != len(plan):
        _fail("layer preparation authority URI plan is not unique")
    return plan


def layer_preparation_receipt_uri_v1(
    *, output_prefix: str, layer_id: str, layer_ordinal: int,
) -> str:
    topology = contract.build_result_topology_v1(output_prefix)
    descriptor = _target_descriptor(
        output_prefix=str(topology["output_prefix"]),
        layer_id=layer_id,
        layer_ordinal=layer_ordinal,
    )
    return (
        f"{topology['output_prefix']}authorities/preparation-receipts/"
        f"{descriptor['layer_ordinal']:02d}-{descriptor['layer_id']}.json"
    )


def _authority_record(
    *, plan_row: Mapping[str, object], value: Mapping[str, object],
    identity: Mapping[str, object],
) -> dict[str, object]:
    field = str(plan_row["body_self_hash_field"])
    body_hash = value.get(field)
    if type(body_hash) is not str or _SHA256_RE.fullmatch(body_hash) is None:
        _fail("published layer authority body self hash differs")
    retained_identity = _bind_body(
        value, identity, label="published layer authority"
    )
    if retained_identity["uri"] != plan_row["uri"]:
        _fail("published layer authority URI differs from its plan")
    return {
        "publication_ordinal": int(plan_row["publication_ordinal"]),
        "authority_role": str(plan_row["authority_role"]),
        "task_index": plan_row["task_index"],
        "fold_ordinal": plan_row["fold_ordinal"],
        "identity": retained_identity,
        "body_self_hash_field": field,
        "body_self_hash": body_hash,
    }


def _publish_planned_authority(
    *, plan: Sequence[Mapping[str, object]], publication_ordinal: int,
    value: Mapping[str, object], publish_create_once: PublishCreateOnce,
    read_exact: ReadExact, authority_records: list[dict[str, object]],
) -> dict[str, object]:
    if publication_ordinal != len(authority_records):
        _fail("layer authority publication order differs")
    row = plan[publication_ordinal]
    identity = _publish_json_create_once(
        uri=str(row["uri"]),
        value=value,
        maximum_bytes=int(row["maximum_bytes"]),
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_records.append(
        _authority_record(plan_row=row, value=value, identity=identity)
    )
    return identity


def _reopen_projection_preparation(
    *, receipt_value: object, receipt_identity_value: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    supplied = _mapping(receipt_value, label="projection preparation receipt")
    try:
        receipt = projection_preparation.validate_projection_preparation_receipt_v1(
            supplied
        )
    except projection_preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc
    receipt_identity = _bind_body(
        receipt, receipt_identity_value, label="projection preparation receipt"
    )
    reopened_receipt, _ = _read_json_exact(
        receipt_identity,
        read_exact=read_exact,
        label="projection preparation receipt",
        maximum_bytes=(
            projection_preparation.MAXIMUM_PROJECTION_PREPARATION_RECEIPT_BYTES
        ),
    )
    if _canonical_bytes(reopened_receipt) != _canonical_bytes(receipt):
        _fail("projection preparation receipt exact reopen differs")
    lattice = projection_preparation.projection_preparation_uri_lattice_v1(
        str(receipt["output_prefix"])
    )
    if receipt_identity["uri"] != lattice["projection-preparation-receipt"]:
        _fail("projection preparation receipt URI differs")
    reopened = task_manifest.reopen_task_manifest_authority_v1(
        receipt["projection_task_manifest_identity"], read_exact=read_exact
    )
    manifest = reopened["manifest"]
    if (
        reopened["manifest_identity"]
        != receipt["projection_task_manifest_identity"]
        or manifest["layer_id"] != "projection"
        or manifest["predecessor_layer_receipts"] != []
        or reopened["projection_process_budget"] is None
        or manifest["output_prefix"] != receipt["output_prefix"]
        or manifest["code_commit"] != receipt["code_commit"]
        or manifest["image_digest"] != receipt["image_digest"]
        or manifest["reused_job_name"] != receipt["reused_job_name"]
    ):
        _fail("projection preparation root authority differs")
    records = {
        str(row["authority_role"]): row["identity"]
        for row in receipt["authority_publications"]
    }
    request = manifest["task_bindings"][0]["request"]
    expected = {
        "pre-design-run-authorization": manifest[
            "pre_design_run_authorization_identity"
        ],
        "topology": manifest["topology_identity"],
        "bootstrap-manifest": manifest["bootstrap_manifest_identity"],
        "design": manifest["design_identity"],
        "projection-publisher-process-budget": request[
            "process_budget_identity"
        ],
        "projection-task-manifest": reopened["manifest_identity"],
    }
    if any(records.get(role) != identity for role, identity in expected.items()):
        _fail("projection preparation publication ledger differs")
    return {
        "receipt": receipt,
        "receipt_identity": receipt_identity,
        **reopened,
    }


def _expected_output_identities(
    *, topology: Mapping[str, object], receipts: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    by_role: dict[str, list[tuple[int, dict[str, object]]]] = {}
    seen_uris: set[str] = set()
    for receipt in receipts:
        for task_record in receipt["task_records"]:
            for publication in task_record["publication_records"]:
                identity = _identity(
                    publication["identity"],
                    label="predecessor publication identity",
                )
                uri = str(identity["uri"])
                if uri in seen_uris:
                    _fail("predecessor publication URI is repeated")
                seen_uris.add(uri)
                by_role.setdefault(str(publication["role"]), []).append((
                    int(publication["topology_ordinal"]), identity,
                ))
    retained = {
        role: [identity for _ordinal, identity in sorted(rows)]
        for role, rows in by_role.items()
    }
    for role, identities in retained.items():
        expected_uris = [
            str(row["uri"]) for row in topology["objects"]
            if row["role"] == role
        ]
        if [str(identity["uri"]) for identity in identities] != expected_uris:
            _fail("predecessor publication topology order differs")
    return retained


def _reopen_predecessor_chain(
    *, target_descriptor: Mapping[str, object], predecessor_records_value: object,
    core: Mapping[str, object], read_exact: ReadExact,
) -> tuple[
    list[dict[str, object]], list[dict[str, object]],
    dict[str, list[dict[str, object]]],
]:
    raw_records = _sequence(
        predecessor_records_value, label="predecessor layer receipt records"
    )
    expected_layers = list(target_descriptor["predecessor_layers"])
    if len(raw_records) != len(expected_layers):
        _fail("predecessor layer receipt count differs from registry")
    receipts: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    registry = {
        str(row["layer_id"]): row
        for row in task_manifest.layer_registry_v1(
            str(core["manifest"]["output_prefix"])
        )
    }
    for expected_layer, raw_record in zip(
        expected_layers, raw_records, strict=True
    ):
        record = _mapping(
            raw_record, label=f"predecessor {expected_layer} input record"
        )
        if set(record) != {"identity", "receipt"}:
            _fail("predecessor input record fields differ")
        supplied_receipt = _mapping(
            record["receipt"], label=f"predecessor {expected_layer} receipt"
        )
        receipt_identity = _bind_body(
            supplied_receipt,
            record["identity"],
            label=f"predecessor {expected_layer} receipt",
        )
        reopened_receipt, _ = _read_json_exact(
            receipt_identity,
            read_exact=read_exact,
            label=f"predecessor {expected_layer} receipt",
            maximum_bytes=task_manifest.MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
        )
        try:
            receipt = task_manifest.validate_layer_execution_receipt_v1(
                reopened_receipt
            )
        except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
                str(exc)
            ) from exc
        descriptor = registry[expected_layer]
        if (
            _canonical_bytes(receipt) != _canonical_bytes(supplied_receipt)
            or receipt["layer_id"] != expected_layer
            or receipt["layer_ordinal"] != descriptor["layer_ordinal"]
            or receipt_identity["uri"] != descriptor["layer_execution_receipt_uri"]
            or receipt["predecessor_layer_receipts"] != bindings
        ):
            _fail("predecessor layer receipt order/identity differs")
        reopened_manifest = task_manifest.reopen_task_manifest_authority_v1(
            receipt["manifest_identity"], read_exact=read_exact
        )
        manifest = reopened_manifest["manifest"]
        try:
            validated_receipt = (
                task_manifest.validate_layer_execution_receipt_authority_v1(
                    receipt,
                    manifest=manifest,
                    manifest_identity=reopened_manifest["manifest_identity"],
                    read_exact=read_exact,
                )
            )
        except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
                str(exc)
            ) from exc
        core_equal = all(
            receipt[field] == core["manifest"][field]
            and manifest[field] == core["manifest"][field]
            for field in (
                "design_identity", "design_sha256", "topology_identity",
                "topology_sha256", "bootstrap_manifest_identity",
                "bootstrap_manifest_sha256",
                "pre_design_run_authorization_identity",
                "pre_design_run_authorization_sha256", "code_commit",
                "image_digest", "reused_job_name",
            )
        )
        if (
            _canonical_bytes(validated_receipt) != _canonical_bytes(receipt)
            or manifest["layer_id"] != expected_layer
            or manifest["layer_ordinal"] != descriptor["layer_ordinal"]
            or manifest["predecessor_layer_receipts"] != bindings
            or reopened_manifest["predecessor_layer_receipts"] != receipts
            or not core_equal
            or (
                expected_layer == "projection"
                and reopened_manifest["manifest_identity"]
                != core["manifest_identity"]
            )
            or (
                expected_layer != "projection"
                and reopened_manifest["projection_process_budget"] is not None
            )
        ):
            _fail("predecessor layer receipt authority graph differs")
        receipts.append(receipt)
        bindings.append({
            "layer_id": expected_layer,
            "receipt_identity": receipt_identity,
            "layer_execution_receipt_sha256": receipt[
                "layer_execution_receipt_sha256"
            ],
        })
        del reopened_manifest, manifest, reopened_receipt, supplied_receipt
    outputs = _expected_output_identities(
        topology=core["topology"], receipts=receipts
    )
    return receipts, bindings, outputs


def _read_scientific_body(
    identity_value: object, *, read_exact: ReadExact, label: str,
    maximum_bytes: int,
) -> dict[str, object]:
    body, _ = _read_json_exact(
        identity_value,
        read_exact=read_exact,
        label=label,
        maximum_bytes=maximum_bytes,
    )
    return body


def _publish_selection_task_authorities(
    *, descriptor: Mapping[str, object], core: Mapping[str, object],
    outputs: Mapping[str, list[dict[str, object]]],
    plan: Sequence[Mapping[str, object]], plan_cursor: int,
    authority_records: list[dict[str, object]],
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> tuple[list[dict[str, object]], int]:
    phase = str(descriptor["phase"])
    role_prefix = (
        "broad" if phase == contract.BROAD_SCREEN_PHASE else "confirmation"
    )
    projections = outputs.get("projection", [])
    nominations = outputs.get("nomination", [])
    if len(projections) != contract.PANEL_SLATE_COUNT:
        _fail("selection preparation projection lattice differs")
    nomination_identity = None
    if phase == contract.CONFIRMATION_PHASE:
        if len(nominations) != 1:
            _fail("confirmation selection nomination lattice differs")
        nomination_identity = nominations[0]
    requests: list[dict[str, object]] = []
    for source, projection_identity in enumerate(projections):
        projection = _read_scientific_body(
            projection_identity,
            read_exact=read_exact,
            label=f"selection projection[{source}]",
            maximum_bytes=MAXIMUM_PROJECTION_BUNDLE_BYTES,
        )
        nomination = None
        if nomination_identity is not None:
            nomination = _read_scientific_body(
                nomination_identity,
                read_exact=read_exact,
                label="selection nomination",
                maximum_bytes=MAXIMUM_NOMINATION_BYTES,
            )
        worker_identities: list[dict[str, object]] = []
        for fold in range(contract.FOLDS_PER_SLATE):
            try:
                budget = contract.compile_process_budget_v1(
                    process_role=f"{role_prefix}-fold-selector",
                    projection_bundle=projection,
                    projection_bundle_identity=projection_identity,
                    topology=core["topology"],
                    topology_identity=core["manifest"]["topology_identity"],
                    source_ordinal=source,
                    fold_ordinal=fold,
                    nomination_publication=nomination,
                    nomination_publication_identity=nomination_identity,
                )
                contract.validate_process_budget_v1(budget)
            except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
                raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
                    str(exc)
                ) from exc
            worker_identities.append(_publish_planned_authority(
                plan=plan,
                publication_ordinal=plan_cursor,
                value=budget,
                publish_create_once=publish_create_once,
                read_exact=read_exact,
                authority_records=authority_records,
            ))
            plan_cursor += 1
        try:
            assembler_budget = contract.compile_process_budget_v1(
                process_role=f"{role_prefix}-slate-assembler",
                projection_bundle=projection,
                projection_bundle_identity=projection_identity,
                topology=core["topology"],
                topology_identity=core["manifest"]["topology_identity"],
                source_ordinal=source,
                nomination_publication=nomination,
                nomination_publication_identity=nomination_identity,
            )
            contract.validate_process_budget_v1(assembler_budget)
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
                str(exc)
            ) from exc
        assembler_identity = _publish_planned_authority(
            plan=plan,
            publication_ordinal=plan_cursor,
            value=assembler_budget,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            authority_records=authority_records,
        )
        plan_cursor += 1
        request = task_manifest.build_selection_task_request_v1(
            phase=phase,
            source_ordinal=source,
            design_identity=core["manifest"]["design_identity"],
            topology_identity=core["manifest"]["topology_identity"],
            projection_bundle_identity=projection_identity,
            assembler_process_budget_identity=assembler_identity,
            worker_process_budget_identities=worker_identities,
            nomination_identity=nomination_identity,
            prior_selection_receipt_identity=None,
        )
        task_manifest.render_child_command_v1(str(descriptor["layer_id"]), request)
        _publish_planned_authority(
            plan=plan,
            publication_ordinal=plan_cursor,
            value=request,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            authority_records=authority_records,
        )
        plan_cursor += 1
        requests.append(request)
        del projection, nomination, assembler_budget, worker_identities
    return requests, plan_cursor


def _publish_evaluation_task_authorities(
    *, descriptor: Mapping[str, object], core: Mapping[str, object],
    outputs: Mapping[str, list[dict[str, object]]],
    plan: Sequence[Mapping[str, object]], plan_cursor: int,
    authority_records: list[dict[str, object]],
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> tuple[list[dict[str, object]], int]:
    phase = str(descriptor["phase"])
    projections = outputs.get("projection", [])
    receipt_role = (
        "broad-selection-receipt"
        if phase == contract.BROAD_SCREEN_PHASE
        else "confirmation-selection-receipt"
    )
    selection_identities = outputs.get(receipt_role, [])
    nominations = outputs.get("nomination", [])
    if (
        len(projections) != contract.PANEL_SLATE_COUNT
        or len(selection_identities) != contract.PANEL_SLATE_COUNT
    ):
        _fail("evaluation preparation predecessor lattice differs")
    nomination_identity = None
    if phase == contract.CONFIRMATION_PHASE:
        if len(nominations) != 1:
            _fail("confirmation evaluation nomination lattice differs")
        nomination_identity = nominations[0]
    requests: list[dict[str, object]] = []
    for source, (projection_identity, selection_identity) in enumerate(zip(
        projections, selection_identities, strict=True
    )):
        projection = _read_scientific_body(
            projection_identity,
            read_exact=read_exact,
            label=f"evaluation projection[{source}]",
            maximum_bytes=MAXIMUM_PROJECTION_BUNDLE_BYTES,
        )
        selection = _read_scientific_body(
            selection_identity,
            read_exact=read_exact,
            label=f"evaluation selection receipt[{source}]",
            maximum_bytes=(
                contract.BROAD_SELECTION_RECEIPT_MAX_BYTES
                if phase == contract.BROAD_SCREEN_PHASE
                else contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES
            ),
        )
        nomination = None
        if nomination_identity is not None:
            nomination = _read_scientific_body(
                nomination_identity,
                read_exact=read_exact,
                label="evaluation nomination",
                maximum_bytes=MAXIMUM_NOMINATION_BYTES,
            )
        try:
            budget = contract.compile_evaluator_process_budget_v1(
                design=core["design"],
                design_publication_identity=core["manifest"]["design_identity"],
                bootstrap_manifest=core["bootstrap_manifest"],
                bootstrap_manifest_identity=core["manifest"][
                    "bootstrap_manifest_identity"
                ],
                launch_intent_identity=core["manifest"][
                    "pre_design_run_authorization_identity"
                ],
                projection_bundle=projection,
                projection_bundle_identity=projection_identity,
                topology_identity=core["manifest"]["topology_identity"],
                source_ordinal=source,
                selection_receipt=selection,
                selection_receipt_identity=selection_identity,
                nomination_publication=nomination,
                nomination_publication_identity=nomination_identity,
            )
            contract.validate_evaluator_process_budget_v1(
                budget,
                design=core["design"],
                design_publication_identity=core["manifest"]["design_identity"],
                bootstrap_manifest=core["bootstrap_manifest"],
                bootstrap_manifest_identity=core["manifest"][
                    "bootstrap_manifest_identity"
                ],
                launch_intent_identity=core["manifest"][
                    "pre_design_run_authorization_identity"
                ],
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
                str(exc)
            ) from exc
        budget_identity = _publish_planned_authority(
            plan=plan,
            publication_ordinal=plan_cursor,
            value=budget,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            authority_records=authority_records,
        )
        plan_cursor += 1
        request = task_manifest.build_evaluation_task_request_v1(
            phase=phase,
            source_ordinal=source,
            design_identity=core["manifest"]["design_identity"],
            topology_identity=core["manifest"]["topology_identity"],
            projection_bundle_identity=projection_identity,
            selection_receipt_identity=selection_identity,
            process_budget_identity=budget_identity,
            bootstrap_manifest_identity=core["manifest"][
                "bootstrap_manifest_identity"
            ],
            launch_intent_identity=core["manifest"][
                "pre_design_run_authorization_identity"
            ],
            nomination_identity=nomination_identity,
            prior_evaluation_identity=None,
        )
        task_manifest.render_child_command_v1(str(descriptor["layer_id"]), request)
        _publish_planned_authority(
            plan=plan,
            publication_ordinal=plan_cursor,
            value=request,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            authority_records=authority_records,
        )
        plan_cursor += 1
        requests.append(request)
        del projection, selection, nomination, budget
    return requests, plan_cursor


def _publisher_lattice(
    *, descriptor: Mapping[str, object], core: Mapping[str, object],
    outputs: Mapping[str, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    layer_id = str(descriptor["layer_id"])
    broad = outputs.get("broad-evaluation-result", [])
    nominations = outputs.get("nomination", [])
    confirmation = outputs.get("confirmation-evaluation-result", [])
    if layer_id == "nomination":
        scientific = broad
        request_fields = {
            "broad_evaluation_identities": broad,
            "nomination_identity": None,
            "confirmation_evaluation_identities": [],
            "predecessor_identities": [],
        }
    elif layer_id == "aggregate-finalists":
        if len(nominations) != 1:
            _fail("aggregate preparation nomination lattice differs")
        scientific = [*broad, nominations[0], *confirmation]
        request_fields = {
            "broad_evaluation_identities": broad,
            "nomination_identity": nominations[0],
            "confirmation_evaluation_identities": confirmation,
            "predecessor_identities": [],
        }
    elif layer_id == "terminal-root":
        by_uri = {str(core["manifest"]["design_identity"]["uri"]): core[
            "manifest"
        ]["design_identity"]}
        for identities in outputs.values():
            by_uri.update({str(identity["uri"]): identity for identity in identities})
        scientific = []
        for row in core["topology"]["objects"][:-1]:
            identity = by_uri.get(str(row["uri"]))
            if identity is None:
                _fail("terminal preparation predecessor lattice is incomplete")
            scientific.append(identity)
        request_fields = {
            "broad_evaluation_identities": [],
            "nomination_identity": None,
            "confirmation_evaluation_identities": [],
            "predecessor_identities": scientific,
        }
    else:
        _fail("publisher layer ID differs")
    return scientific, request_fields


def _publish_publisher_task_authorities(
    *, descriptor: Mapping[str, object], core: Mapping[str, object],
    outputs: Mapping[str, list[dict[str, object]]],
    plan: Sequence[Mapping[str, object]], plan_cursor: int,
    authority_records: list[dict[str, object]],
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> tuple[list[dict[str, object]], int]:
    scientific, request_fields = _publisher_lattice(
        descriptor=descriptor, core=core, outputs=outputs
    )
    try:
        budget = contract.compile_publisher_process_budget_v1(
            process_role=str(descriptor["process_role"]),
            design=core["design"],
            design_publication_identity=core["manifest"]["design_identity"],
            topology_identity=core["manifest"]["topology_identity"],
            bootstrap_manifest=core["bootstrap_manifest"],
            bootstrap_manifest_identity=core["manifest"][
                "bootstrap_manifest_identity"
            ],
            launch_intent_identity=core["manifest"][
                "pre_design_run_authorization_identity"
            ],
            scientific_read_identities=scientific,
        )
        contract.validate_publisher_process_budget_v1(
            budget,
            design=core["design"],
            design_publication_identity=core["manifest"]["design_identity"],
            topology_identity=core["manifest"]["topology_identity"],
            bootstrap_manifest=core["bootstrap_manifest"],
            bootstrap_manifest_identity=core["manifest"][
                "bootstrap_manifest_identity"
            ],
            launch_intent_identity=core["manifest"][
                "pre_design_run_authorization_identity"
            ],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc
    budget_identity = _publish_planned_authority(
        plan=plan,
        publication_ordinal=plan_cursor,
        value=budget,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        authority_records=authority_records,
    )
    plan_cursor += 1
    request = task_manifest.build_publisher_task_request_v1(
        mode=str(descriptor["mode"]),
        design_identity=core["manifest"]["design_identity"],
        topology_identity=core["manifest"]["topology_identity"],
        bootstrap_manifest_identity=core["manifest"][
            "bootstrap_manifest_identity"
        ],
        launch_intent_identity=core["manifest"][
            "pre_design_run_authorization_identity"
        ],
        process_budget_identity=budget_identity,
        **request_fields,
        prior_nomination_identity=None,
        prior_aggregate_identity=None,
        prior_finalist_identity=None,
        prior_root_identity=None,
    )
    task_manifest.render_child_command_v1(str(descriptor["layer_id"]), request)
    _publish_planned_authority(
        plan=plan,
        publication_ordinal=plan_cursor,
        value=request,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        authority_records=authority_records,
    )
    return [request], plan_cursor + 1


def build_layer_preparation_receipt_v1(
    *, projection_preparation_receipt: object,
    projection_preparation_receipt_identity: object,
    descriptor: Mapping[str, object], core_manifest: Mapping[str, object],
    predecessor_bindings: object, authority_records: object,
) -> dict[str, object]:
    prep = projection_preparation.validate_projection_preparation_receipt_v1(
        projection_preparation_receipt
    )
    prep_identity = _bind_body(
        prep,
        projection_preparation_receipt_identity,
        label="layer receipt projection preparation",
    )
    predecessor_rows = [
        _mapping(row, label=f"layer preparation predecessor[{index}]")
        for index, row in enumerate(_sequence(
            predecessor_bindings, label="layer preparation predecessors"
        ))
    ]
    records = [
        _mapping(row, label=f"layer preparation publication[{index}]")
        for index, row in enumerate(_sequence(
            authority_records, label="layer preparation publications"
        ))
    ]
    body = {
        "schema_version": LAYER_PREPARATION_RECEIPT_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "preparation_role": "registered-later-layer-fresh-run",
        "output_prefix": core_manifest["output_prefix"],
        "layer_ordinal": descriptor["layer_ordinal"],
        "layer_id": descriptor["layer_id"],
        "phase": descriptor["phase"],
        "request_kind": descriptor["request_kind"],
        "task_count": descriptor["task_count"],
        "projection_preparation_receipt_identity": prep_identity,
        "projection_preparation_receipt_sha256": prep[
            "projection_preparation_receipt_sha256"
        ],
        "design_identity": core_manifest["design_identity"],
        "design_sha256": core_manifest["design_sha256"],
        "topology_identity": core_manifest["topology_identity"],
        "topology_sha256": core_manifest["topology_sha256"],
        "bootstrap_manifest_identity": core_manifest[
            "bootstrap_manifest_identity"
        ],
        "bootstrap_manifest_sha256": core_manifest[
            "bootstrap_manifest_sha256"
        ],
        "pre_design_run_authorization_identity": core_manifest[
            "pre_design_run_authorization_identity"
        ],
        "pre_design_run_authorization_sha256": core_manifest[
            "pre_design_run_authorization_sha256"
        ],
        "code_commit": core_manifest["code_commit"],
        "image_digest": core_manifest["image_digest"],
        "reused_job_name": core_manifest["reused_job_name"],
        "predecessor_layer_receipt_count": len(predecessor_rows),
        "predecessor_layer_receipts": predecessor_rows,
        "predecessor_layer_receipts_sha256": _canonical_sha(predecessor_rows),
        "authority_publication_count": len(records),
        "authority_publications": records,
        "authority_publications_sha256": _canonical_sha(records),
        "process_budget_publication_count": sum(
            row["authority_role"]
            in {
                "worker-process-budget", "assembler-process-budget",
                "process-budget",
            }
            for row in records
        ),
        "task_request_publication_count": sum(
            row["authority_role"] == "task-request" for row in records
        ),
        "task_manifest_identity": records[-1]["identity"],
        "task_manifest_sha256": records[-1]["body_self_hash"],
        "preparation_receipt_uri": layer_preparation_receipt_uri_v1(
            output_prefix=str(core_manifest["output_prefix"]),
            layer_id=str(descriptor["layer_id"]),
            layer_ordinal=int(descriptor["layer_ordinal"]),
        ),
        "fresh_run_only": True,
        "recovery_allowed": False,
        "all_prior_same_output_identities_absent": True,
        "predecessors_reopened_generation_exact": True,
        "terminal_evidence_reopened_generation_exact": True,
        "sequential_source_task_preparation": True,
        "maximum_simultaneous_scientific_bodies": (
            3 if descriptor["request_kind"] == "evaluation"
            else 2 if descriptor["request_kind"] == "selection"
            else 0
        ),
        "one_reused_job_across_layers": True,
        "current_generation_resolution_allowed": False,
        "listing_allowed": False,
        "uses_realized_outcomes": False,
        "graph_capability_allowed": False,
        "caller_output_uri_or_identity_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    receipt = _with_hash(body, field="layer_preparation_receipt_sha256")
    return validate_layer_preparation_receipt_v1(receipt)


def validate_layer_preparation_receipt_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="layer preparation receipt")
    expected_fields = {
        "schema_version", "contract_id", "preparation_role", "output_prefix",
        "layer_ordinal", "layer_id", "phase", "request_kind", "task_count",
        "projection_preparation_receipt_identity",
        "projection_preparation_receipt_sha256", "design_identity",
        "design_sha256", "topology_identity", "topology_sha256",
        "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
        "pre_design_run_authorization_identity",
        "pre_design_run_authorization_sha256", "code_commit", "image_digest",
        "reused_job_name", "predecessor_layer_receipt_count",
        "predecessor_layer_receipts", "predecessor_layer_receipts_sha256",
        "authority_publication_count", "authority_publications",
        "authority_publications_sha256", "process_budget_publication_count",
        "task_request_publication_count", "task_manifest_identity",
        "task_manifest_sha256", "preparation_receipt_uri", "fresh_run_only",
        "recovery_allowed", "all_prior_same_output_identities_absent",
        "predecessors_reopened_generation_exact",
        "terminal_evidence_reopened_generation_exact",
        "sequential_source_task_preparation",
        "maximum_simultaneous_scientific_bodies",
        "one_reused_job_across_layers",
        "current_generation_resolution_allowed", "listing_allowed",
        "uses_realized_outcomes", "graph_capability_allowed",
        "caller_output_uri_or_identity_accepted", "policy",
        "layer_preparation_receipt_sha256",
    }
    if set(item) != expected_fields:
        _fail("layer preparation receipt fields differ")
    _self_hash(
        item,
        field="layer_preparation_receipt_sha256",
        label="layer preparation receipt",
    )
    if len(_canonical_bytes(item)) > MAXIMUM_LAYER_PREPARATION_RECEIPT_BYTES:
        _fail("layer preparation receipt exceeds its byte ceiling")
    output_prefix = str(item.get("output_prefix", ""))
    layer_id = str(item.get("layer_id", ""))
    layer_ordinal = item.get("layer_ordinal")
    if type(layer_ordinal) is not int:
        _fail("layer preparation ordinal differs")
    descriptor = _target_descriptor(
        output_prefix=output_prefix,
        layer_id=layer_id,
        layer_ordinal=layer_ordinal,
    )
    plan = layer_preparation_authority_plan_v1(
        output_prefix=output_prefix,
        layer_id=layer_id,
        layer_ordinal=layer_ordinal,
    )
    prep_identity = _identity(
        item.get("projection_preparation_receipt_identity"),
        label="layer preparation projection receipt",
    )
    prep_lattice = projection_preparation.projection_preparation_uri_lattice_v1(
        output_prefix
    )
    predecessors = [
        _mapping(row, label=f"layer preparation predecessor[{index}]")
        for index, row in enumerate(_sequence(
            item.get("predecessor_layer_receipts"),
            label="layer preparation predecessors",
        ))
    ]
    if len(predecessors) != len(descriptor["predecessor_layers"]):
        _fail("layer preparation predecessor count differs")
    registry = {
        str(row["layer_id"]): row
        for row in task_manifest.layer_registry_v1(output_prefix)
    }
    normalized_predecessors: list[dict[str, object]] = []
    for expected_layer, row in zip(
        descriptor["predecessor_layers"], predecessors, strict=True
    ):
        if set(row) != {
            "layer_id", "receipt_identity", "layer_execution_receipt_sha256"
        } or row.get("layer_id") != expected_layer:
            _fail("layer preparation predecessor fields/order differ")
        receipt_identity = _identity(
            row.get("receipt_identity"), label="layer preparation predecessor"
        )
        receipt_hash = row.get("layer_execution_receipt_sha256")
        if (
            receipt_identity["uri"]
            != registry[str(expected_layer)]["layer_execution_receipt_uri"]
            or type(receipt_hash) is not str
            or _SHA256_RE.fullmatch(receipt_hash) is None
        ):
            _fail("layer preparation predecessor identity/hash differs")
        normalized_predecessors.append({
            "layer_id": expected_layer,
            "receipt_identity": receipt_identity,
            "layer_execution_receipt_sha256": receipt_hash,
        })
    records = [
        _mapping(row, label=f"layer preparation publication[{index}]")
        for index, row in enumerate(_sequence(
            item.get("authority_publications"),
            label="layer preparation publications",
        ))
    ]
    if len(records) != len(plan):
        _fail("layer preparation authority publication count differs")
    normalized_records: list[dict[str, object]] = []
    for expected, record in zip(plan, records, strict=True):
        if set(record) != {
            "publication_ordinal", "authority_role", "task_index",
            "fold_ordinal", "identity", "body_self_hash_field",
            "body_self_hash",
        }:
            _fail("layer preparation authority publication fields differ")
        identity = _identity(
            record.get("identity"), label="layer preparation publication"
        )
        body_hash = record.get("body_self_hash")
        if (
            record.get("publication_ordinal") != expected["publication_ordinal"]
            or record.get("authority_role") != expected["authority_role"]
            or record.get("task_index") != expected["task_index"]
            or record.get("fold_ordinal") != expected["fold_ordinal"]
            or identity["uri"] != expected["uri"]
            or record.get("body_self_hash_field")
            != expected["body_self_hash_field"]
            or type(body_hash) is not str
            or _SHA256_RE.fullmatch(body_hash) is None
        ):
            _fail("layer preparation authority publication plan differs")
        normalized_records.append({
            "publication_ordinal": expected["publication_ordinal"],
            "authority_role": expected["authority_role"],
            "task_index": expected["task_index"],
            "fold_ordinal": expected["fold_ordinal"],
            "identity": identity,
            "body_self_hash_field": expected["body_self_hash_field"],
            "body_self_hash": body_hash,
        })
    commit = item.get("code_commit")
    digest = item.get("image_digest")
    job = item.get("reused_job_name")
    expected_budget_count = sum(
        row["authority_role"]
        in {"worker-process-budget", "assembler-process-budget", "process-budget"}
        for row in normalized_records
    )
    invariants = (
        item.get("schema_version") == LAYER_PREPARATION_RECEIPT_SCHEMA,
        item.get("contract_id") == contract.CONTRACT_ID,
        item.get("preparation_role") == "registered-later-layer-fresh-run",
        item.get("phase") == descriptor["phase"],
        item.get("request_kind") == descriptor["request_kind"],
        item.get("task_count") == descriptor["task_count"],
        prep_identity["uri"] == prep_lattice["projection-preparation-receipt"],
        type(item.get("projection_preparation_receipt_sha256")) is str,
        _SHA256_RE.fullmatch(
            str(item.get("projection_preparation_receipt_sha256"))
        ) is not None,
        item.get("predecessor_layer_receipt_count") == len(predecessors),
        item.get("predecessor_layer_receipts_sha256")
        == _canonical_sha(normalized_predecessors),
        item.get("authority_publication_count") == len(records),
        item.get("authority_publications_sha256")
        == _canonical_sha(normalized_records),
        item.get("process_budget_publication_count") == expected_budget_count,
        item.get("task_request_publication_count") == descriptor["task_count"],
        item.get("task_manifest_identity") == normalized_records[-1]["identity"],
        item.get("task_manifest_sha256")
        == normalized_records[-1]["body_self_hash"],
        item.get("preparation_receipt_uri")
        == layer_preparation_receipt_uri_v1(
            output_prefix=output_prefix,
            layer_id=layer_id,
            layer_ordinal=layer_ordinal,
        ),
        type(commit) is str and _COMMIT_RE.fullmatch(commit) is not None,
        type(digest) is str
        and digest.startswith("sha256:")
        and _SHA256_RE.fullmatch(digest[7:]) is not None,
        type(job) is str and _JOB_RE.fullmatch(job) is not None,
        item.get("fresh_run_only") is True,
        item.get("recovery_allowed") is False,
        item.get("all_prior_same_output_identities_absent") is True,
        item.get("predecessors_reopened_generation_exact") is True,
        item.get("terminal_evidence_reopened_generation_exact") is True,
        item.get("sequential_source_task_preparation") is True,
        item.get("maximum_simultaneous_scientific_bodies")
        == (
            3 if descriptor["request_kind"] == "evaluation"
            else 2 if descriptor["request_kind"] == "selection"
            else 0
        ),
        item.get("one_reused_job_across_layers") is True,
        item.get("current_generation_resolution_allowed") is False,
        item.get("listing_allowed") is False,
        item.get("uses_realized_outcomes") is False,
        item.get("graph_capability_allowed") is False,
        item.get("caller_output_uri_or_identity_accepted") is False,
        item.get("policy") == contract.POLICY_CLAIMS,
    )
    for field in (
        "design_identity", "topology_identity", "bootstrap_manifest_identity",
        "pre_design_run_authorization_identity",
    ):
        _identity(item.get(field), label=f"layer preparation {field}")
    for field in (
        "design_sha256", "topology_sha256", "bootstrap_manifest_sha256",
        "pre_design_run_authorization_sha256", "task_manifest_sha256",
    ):
        value_hash = item.get(field)
        if type(value_hash) is not str or _SHA256_RE.fullmatch(value_hash) is None:
            _fail(f"layer preparation {field} differs")
    if not all(invariants):
        _fail("layer preparation receipt fixed authority differs")
    return item


def prepare_registered_layer_v1(
    *, projection_preparation_receipt: object,
    projection_preparation_receipt_identity: object,
    target_layer_id: str, target_layer_ordinal: int,
    predecessor_layer_receipts: object,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    """Prepare one exact registered later layer, fresh-run only."""
    core = _reopen_projection_preparation(
        receipt_value=projection_preparation_receipt,
        receipt_identity_value=projection_preparation_receipt_identity,
        read_exact=read_exact,
    )
    descriptor = _target_descriptor(
        output_prefix=str(core["manifest"]["output_prefix"]),
        layer_id=target_layer_id,
        layer_ordinal=target_layer_ordinal,
    )
    receipts, bindings, outputs = _reopen_predecessor_chain(
        target_descriptor=descriptor,
        predecessor_records_value=predecessor_layer_receipts,
        core=core,
        read_exact=read_exact,
    )
    plan = layer_preparation_authority_plan_v1(
        output_prefix=str(core["manifest"]["output_prefix"]),
        layer_id=target_layer_id,
        layer_ordinal=target_layer_ordinal,
    )
    authority_records: list[dict[str, object]] = []
    plan_cursor = 0
    if descriptor["request_kind"] == "selection":
        requests, plan_cursor = _publish_selection_task_authorities(
            descriptor=descriptor,
            core=core,
            outputs=outputs,
            plan=plan,
            plan_cursor=plan_cursor,
            authority_records=authority_records,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    elif descriptor["request_kind"] == "evaluation":
        requests, plan_cursor = _publish_evaluation_task_authorities(
            descriptor=descriptor,
            core=core,
            outputs=outputs,
            plan=plan,
            plan_cursor=plan_cursor,
            authority_records=authority_records,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    else:
        requests, plan_cursor = _publish_publisher_task_authorities(
            descriptor=descriptor,
            core=core,
            outputs=outputs,
            plan=plan,
            plan_cursor=plan_cursor,
            authority_records=authority_records,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    if plan_cursor != len(plan) - 1:
        _fail("layer request/budget publication plan is incomplete")
    try:
        manifest = task_manifest.build_task_manifest_v1(
            layer_id=target_layer_id,
            design=core["design"],
            design_identity=core["manifest"]["design_identity"],
            topology=core["topology"],
            topology_identity=core["manifest"]["topology_identity"],
            bootstrap_manifest=core["bootstrap_manifest"],
            bootstrap_manifest_identity=core["manifest"][
                "bootstrap_manifest_identity"
            ],
            pre_design_run_authorization=core["pre_design_run_authorization"],
            pre_design_run_authorization_identity=core["manifest"][
                "pre_design_run_authorization_identity"
            ],
            task_requests=requests,
            predecessor_layer_receipts=(),
            projection_process_budget=None,
            _validated_predecessor_token=(
                task_manifest._VALIDATED_PREDECESSOR_TOKEN
            ),
            _validated_predecessor_receipts=receipts,
            _validated_receipt_bindings=bindings,
        )
    except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error(
            str(exc)
        ) from exc
    manifest_identity = _publish_planned_authority(
        plan=plan,
        publication_ordinal=plan_cursor,
        value=manifest,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        authority_records=authority_records,
    )
    reopened = task_manifest.reopen_task_manifest_authority_v1(
        manifest_identity, read_exact=read_exact
    )
    if (
        reopened["manifest"] != manifest
        or reopened["manifest_identity"] != manifest_identity
        or reopened["projection_process_budget"] is not None
        or reopened["predecessor_layer_receipts"] != receipts
        or manifest["predecessor_layer_receipts"] != bindings
        or manifest["code_commit"] != core["manifest"]["code_commit"]
        or manifest["image_digest"] != core["manifest"]["image_digest"]
        or manifest["reused_job_name"] != core["manifest"]["reused_job_name"]
    ):
        _fail("prepared layer manifest exact authority reopen differs")
    preparation_receipt = build_layer_preparation_receipt_v1(
        projection_preparation_receipt=core["receipt"],
        projection_preparation_receipt_identity=core["receipt_identity"],
        descriptor=descriptor,
        core_manifest=core["manifest"],
        predecessor_bindings=bindings,
        authority_records=authority_records,
    )
    preparation_receipt_identity = _publish_json_create_once(
        uri=str(preparation_receipt["preparation_receipt_uri"]),
        value=preparation_receipt,
        maximum_bytes=MAXIMUM_LAYER_PREPARATION_RECEIPT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    return {
        "layer_id": target_layer_id,
        "layer_ordinal": target_layer_ordinal,
        "task_count": descriptor["task_count"],
        "manifest_identity": deepcopy(manifest_identity),
        "task_manifest_identity": deepcopy(manifest_identity),
        "preparation_receipt": deepcopy(preparation_receipt),
        "preparation_receipt_identity": deepcopy(
            preparation_receipt_identity
        ),
        "predecessor_layer_receipts": deepcopy(bindings),
        "authority_publications": deepcopy(authority_records),
        "request_count": len(requests),
    }


__all__ = [
    "CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error",
    "LAYER_PREPARATION_RECEIPT_SCHEMA",
    "MAXIMUM_LAYER_PREPARATION_RECEIPT_BYTES",
    "build_layer_preparation_receipt_v1",
    "layer_preparation_authority_plan_v1",
    "layer_preparation_receipt_uri_v1",
    "prepare_registered_layer_v1",
    "validate_layer_preparation_receipt_v1",
]
