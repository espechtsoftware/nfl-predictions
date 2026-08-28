"""Pure fresh-run preparation for the first crossed-screen task layer.

The controller in this module has no storage discovery, cloud, subprocess,
Git, outcome, or graph capability.  It accepts only the frozen source bytes,
the generation-pinned panel-root identity/body, and injected exact-read/
create-once transports.  It publishes the fixed projection authority chain in
one acyclic order and exact-reopens every created generation before returning
the projection task-manifest identity.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_projection_v1 as projection,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


PROJECTION_PREPARATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-projection-preparation-receipt/v1"
)
MAXIMUM_CODE_INPUT_BYTES: Final = 16_000_000
MAXIMUM_REPORT_INPUT_BYTES: Final = 16_000_000
MAXIMUM_PROJECTION_TASK_REQUEST_BYTES: Final = 512_000
MAXIMUM_PROJECTION_PREPARATION_RECEIPT_BYTES: Final = 512_000
FROZEN_CONTRACT_MODULE_BYTES: Final = 374_457
FROZEN_CONTRACT_MODULE_SHA256: Final = (
    "729e1d4302bda62a7000d747c7dc869abb10a0a1a65f98fbcdf2e4409686c846"
)
FROZEN_PREOUTPUT_REPORT_BYTES: Final = 43_407
FROZEN_PREOUTPUT_REPORT_SHA256: Final = (
    "83d6c9d40e709a75615ddc87288a7133e1a24e9d2106ffcda76f6e47113c4f0d"
)

_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_JOB_RE: Final = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], object]

_AUTHORITY_SPECS: Final = (
    ("contract-module-source", "code_source", None),
    ("preoutput-contract-source", "report_source", None),
    (
        "pre-design-run-authorization",
        "pre_design_run_authorization",
        "pre_design_run_authorization_sha256",
    ),
    ("topology", "topology", "topology_sha256"),
    ("bootstrap-manifest", "bootstrap_manifest", "bootstrap_manifest_sha256"),
    ("design", "design", "design_sha256"),
    (
        "projection-publisher-process-budget",
        "projection_process_budget",
        "publisher_process_budget_sha256",
    ),
    (
        "projection-task-request",
        "projection_task_request",
        "projection_task_request_sha256",
    ),
    (
        "projection-task-manifest",
        "projection_task_manifest",
        "task_manifest_sha256",
    ),
)


class CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error(ValueError):
    """The immutable first-layer preparation authority could not be proven."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error(message)


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
        raise CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error(
            str(exc)
        ) from exc


def _canonical_bytes(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error(
            str(exc)
        ) from exc


def _with_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = contract.canonical_sha256_v1(retained)
    return retained


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    observed = value.get(field)
    if type(observed) is not str or _SHA256_RE.fullmatch(observed) is None:
        _fail(f"{label} self-hash differs")
    body = dict(value)
    body.pop(field, None)
    if observed != contract.canonical_sha256_v1(body):
        _fail(f"{label} self-hash differs")


def _bind_body(
    body_value: object, identity_value: object, *, label: str,
) -> dict[str, object]:
    body = _mapping(body_value, label=label)
    identity = _identity(identity_value, label=f"{label} identity")
    raw = _canonical_bytes(body)
    if (
        len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} differs from its exact identity")
    return identity


def _bind_publication_value(
    value: object, identity_value: object, *, label: str,
) -> dict[str, object]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = value if type(value) is bytes else _canonical_bytes(
        _mapping(value, label=label)
    )
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} differs from its exact identity")
    return identity


def _read_exact_bytes(
    identity_value: object, *, read_exact: ReadExact, label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if identity["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its exact-read byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact body differs")
    return raw, identity


def _publish_json_create_once_v1(
    *, uri: str, value: Mapping[str, object], maximum_bytes: int,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    identity = task_manifest.publish_create_once_or_exact_prior_v1(
        uri=uri,
        value=value,
        prior_identity=None,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        maximum_bytes=maximum_bytes,
    )
    return _bind_body(value, identity, label="created immutable authority")


def _publish_raw_create_once_v1(
    *, uri: str, raw: bytes, maximum_bytes: int,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    identity = task_manifest.publish_create_once_or_exact_prior_v1(
        uri=uri,
        value=raw,
        prior_identity=None,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        maximum_bytes=maximum_bytes,
    )
    return _bind_publication_value(
        raw, identity, label="created immutable source authority"
    )


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def _validate_frozen_source_bytes_v1(
    raw_value: object, *, relative_path: str, expected_bytes: int,
    expected_sha256: str, label: str,
) -> bytes:
    if type(raw_value) is not bytes:
        _fail(f"{label} must be exact bytes")
    raw = bytes(raw_value)
    path = (_repository_root_v1() / relative_path).resolve()
    try:
        path.relative_to(_repository_root_v1().resolve())
    except ValueError:
        _fail(f"{label} path is outside the frozen source tree")
    if (
        not path.is_file()
        or len(raw) != expected_bytes
        or sha256(raw).hexdigest() != expected_sha256
        or path.read_bytes() != raw
    ):
        _fail(f"{label} differs from the frozen source authority")
    return raw


def projection_preparation_uri_lattice_v1(output_prefix: str) -> dict[str, str]:
    """Return the only first-layer preparation publication URI lattice."""
    topology = contract.build_result_topology_v1(output_prefix)
    prefix = str(topology["output_prefix"])
    design_rows = [row for row in topology["objects"] if row["role"] == "design"]
    if len(design_rows) != 1:
        _fail("projection preparation design topology differs")
    lattice = {
        "contract-module-source": (
            prefix + "authorities/sources/contract-module.py"
        ),
        "preoutput-contract-source": (
            prefix + "authorities/sources/preoutput-contract.md"
        ),
        "pre-design-run-authorization": (
            task_manifest.pre_design_run_authorization_uri_v1(prefix)
        ),
        "topology": prefix + "authorities/topology.json",
        "bootstrap-manifest": prefix + "authorities/bootstrap-manifest.json",
        "design": str(design_rows[0]["uri"]),
        "projection-publisher-process-budget": (
            prefix
            + "authorities/process-budgets/00-projection-publisher.json"
        ),
        "projection-task-request": (
            prefix + "authorities/task-requests/00-projection/task-000.json"
        ),
        "projection-task-manifest": (
            prefix + "authorities/task-manifests/00-projection.json"
        ),
        "projection-preparation-receipt": (
            prefix + "authorities/preparation-receipts/00-projection.json"
        ),
    }
    if (
        len(set(lattice.values())) != len(lattice)
        or any(not uri.startswith(prefix) for uri in lattice.values())
    ):
        _fail("projection preparation URI lattice differs")
    return lattice


def _validate_structural_inventory_v1(
    identities_value: object,
) -> list[dict[str, object]]:
    raw = _sequence(identities_value, label="projection structural identities")
    identities = [
        _identity(value, label=f"projection structural identity[{index}]")
        for index, value in enumerate(raw)
    ]
    keys = [
        (
            str(identity["uri"]),
            str(identity["generation"]),
            str(identity["sha256"]),
            int(identity["bytes"]),
        )
        for identity in identities
    ]
    if (
        len(identities) != contract.EXACT_STRUCTURAL_OBJECT_COUNT
        or len(set(keys)) != contract.EXACT_STRUCTURAL_OBJECT_COUNT
        or len({str(identity["uri"]) for identity in identities})
        != contract.EXACT_STRUCTURAL_OBJECT_COUNT
        or identities[0] != contract.PANEL_IDENTITY
    ):
        _fail("projection structural identity inventory differs")
    return identities


def _validate_projection_budget_inventory_v1(
    budget_value: object, *, structural_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    budget = _mapping(budget_value, label="projection publisher process budget")
    reads = [
        _mapping(row, label=f"projection budget read[{index}]")
        for index, row in enumerate(
            _sequence(budget.get("read_allowlist"), label="projection budget reads")
        )
    ]
    scientific_rows = reads[4:]
    scientific = [
        _identity(row.get("identity"), label=f"projection budget scientific[{index}]")
        for index, row in enumerate(scientific_rows)
    ]
    expected_roles = [
        f"scientific-{index:03d}"
        for index in range(contract.EXACT_STRUCTURAL_OBJECT_COUNT)
    ]
    if (
        budget.get("process_role") != "projection-publisher"
        or budget.get("process_ordinal") != 0
        or budget.get("scientific_read_count")
        != contract.EXACT_STRUCTURAL_OBJECT_COUNT
        or [row.get("role") for row in scientific_rows] != expected_roles
        or scientific != list(structural_identities)
        or budget.get("scientific_read_identities_sha256")
        != contract.canonical_sha256_v1(list(structural_identities))
    ):
        _fail("projection publisher budget structural inventory differs")
    return budget


def _authority_publication_records_v1(
    *, output_prefix: str, authority_values: Mapping[str, object],
    authority_identities: Mapping[str, object],
) -> list[dict[str, object]]:
    lattice = projection_preparation_uri_lattice_v1(output_prefix)
    records: list[dict[str, object]] = []
    for ordinal, (role, key, hash_field) in enumerate(_AUTHORITY_SPECS):
        value = authority_values.get(key)
        identity = _bind_publication_value(
            value, authority_identities.get(key), label=f"{role} publication"
        )
        self_hash = (
            _mapping(value, label=f"{role} body").get(hash_field)
            if hash_field is not None
            else None
        )
        if (
            identity["uri"] != lattice[role]
            or (
                hash_field is not None
                and (
                    type(self_hash) is not str
                    or _SHA256_RE.fullmatch(self_hash) is None
                )
            )
        ):
            _fail(f"{role} publication URI/self-hash differs")
        records.append({
            "publication_ordinal": ordinal,
            "authority_role": role,
            "identity": identity,
            "body_self_hash_field": hash_field,
            "body_self_hash": self_hash,
        })
    return records


def build_projection_preparation_receipt_v1(
    *, output_prefix: str, code_identity: object, report_identity: object,
    panel_root_body: object, panel_root_identity: object,
    structural_identities: object,
    code_commit: str, image_digest: str, reused_job_name: str,
    authority_values: Mapping[str, object],
    authority_identities: Mapping[str, object],
) -> dict[str, object]:
    """Build the compact, self-hashed receipt for the prepared A authority graph."""
    topology = contract.build_result_topology_v1(output_prefix)
    prefix = str(topology["output_prefix"])
    code = _identity(code_identity, label="preparation code identity")
    report = _identity(report_identity, label="preparation report identity")
    panel = _identity(panel_root_identity, label="preparation panel root identity")
    structural = _validate_structural_inventory_v1(structural_identities)
    retained_panel_root = _mapping(
        panel_root_body, label="preparation panel-root body"
    )
    derived_structural = projection.projection_structural_identity_inventory_v1(
        retained_panel_root, panel_identity=panel
    )
    if (
        panel != contract.PANEL_IDENTITY
        or structural[0] != panel
        or structural != derived_structural
    ):
        _fail("preparation frozen panel identity differs")
    records = _authority_publication_records_v1(
        output_prefix=prefix,
        authority_values=authority_values,
        authority_identities=authority_identities,
    )
    manifest_identity = records[-1]["identity"]
    body = {
        "schema_version": PROJECTION_PREPARATION_RECEIPT_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "preparation_role": "projection-first-layer-fresh-run",
        "output_prefix": prefix,
        "child_run_prefix": topology["child_run_prefix"],
        "code_identity": code,
        "report_identity": report,
        "panel_root_body": retained_panel_root,
        "panel_root_identity": panel,
        "panel_self_sha256": contract.PANEL_SELF_SHA256,
        "structural_identity_count": len(structural),
        "structural_identities": structural,
        "structural_identities_sha256": contract.canonical_sha256_v1(structural),
        "code_commit": code_commit,
        "image_digest": image_digest,
        "reused_job_name": reused_job_name,
        "authority_publication_count": len(records),
        "authority_publications": records,
        "authority_publications_sha256": contract.canonical_sha256_v1(records),
        "projection_task_manifest_identity": manifest_identity,
        "projection_task_manifest_sha256": records[-1]["body_self_hash"],
        "predecessor_layer_receipt_count": 0,
        "prior_projection_identity_slot_count": contract.PANEL_SLATE_COUNT,
        "all_prior_projection_identities_absent": True,
        "fresh_run_only": True,
        "recovery_allowed": False,
        "one_reused_job_across_layers": True,
        "current_generation_resolution_allowed": False,
        "listing_allowed": False,
        "uses_realized_outcomes": False,
        "graph_capability_allowed": False,
        "caller_output_uri_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    receipt = _with_hash(body, field="projection_preparation_receipt_sha256")
    return validate_projection_preparation_receipt_v1(receipt)


def validate_projection_preparation_receipt_v1(
    value: object,
) -> dict[str, object]:
    """Validate the compact preparation receipt and its fixed URI ledger."""
    item = _mapping(value, label="projection preparation receipt")
    expected_fields = {
        "schema_version", "contract_id", "preparation_role", "output_prefix",
        "child_run_prefix", "code_identity", "report_identity",
        "panel_root_body", "panel_root_identity", "panel_self_sha256",
        "structural_identity_count",
        "structural_identities", "structural_identities_sha256", "code_commit",
        "image_digest",
        "reused_job_name", "authority_publication_count",
        "authority_publications", "authority_publications_sha256",
        "projection_task_manifest_identity", "projection_task_manifest_sha256",
        "predecessor_layer_receipt_count", "prior_projection_identity_slot_count",
        "all_prior_projection_identities_absent", "fresh_run_only",
        "recovery_allowed", "one_reused_job_across_layers",
        "current_generation_resolution_allowed", "listing_allowed",
        "uses_realized_outcomes", "graph_capability_allowed",
        "caller_output_uri_accepted", "policy",
        "projection_preparation_receipt_sha256",
    }
    if set(item) != expected_fields:
        _fail("projection preparation receipt fields differ")
    _self_hash(
        item,
        field="projection_preparation_receipt_sha256",
        label="projection preparation receipt",
    )
    topology = contract.build_result_topology_v1(str(item.get("output_prefix", "")))
    lattice = projection_preparation_uri_lattice_v1(
        str(topology["output_prefix"])
    )
    code = _identity(item.get("code_identity"), label="receipt code identity")
    report = _identity(item.get("report_identity"), label="receipt report identity")
    panel = _identity(
        item.get("panel_root_identity"), label="receipt panel root identity"
    )
    panel_root = _mapping(
        item.get("panel_root_body"), label="receipt panel-root body"
    )
    structural = _validate_structural_inventory_v1(
        item.get("structural_identities")
    )
    derived_structural = projection.projection_structural_identity_inventory_v1(
        panel_root, panel_identity=panel
    )
    records = [
        _mapping(row, label=f"receipt authority publication[{index}]")
        for index, row in enumerate(
            _sequence(
                item.get("authority_publications"),
                label="receipt authority publications",
            )
        )
    ]
    if len(records) != len(_AUTHORITY_SPECS):
        _fail("projection preparation authority publication count differs")
    normalized_records: list[dict[str, object]] = []
    for ordinal, (record, (role, _key, hash_field)) in enumerate(
        zip(records, _AUTHORITY_SPECS, strict=True)
    ):
        if set(record) != {
            "publication_ordinal", "authority_role", "identity",
            "body_self_hash_field", "body_self_hash",
        }:
            _fail("projection preparation authority record fields differ")
        identity = _identity(
            record.get("identity"), label=f"receipt {role} identity"
        )
        body_hash = record.get("body_self_hash")
        hash_binding_valid = (
            body_hash is None
            if hash_field is None
            else type(body_hash) is str
            and _SHA256_RE.fullmatch(body_hash) is not None
        )
        if (
            record.get("publication_ordinal") != ordinal
            or record.get("authority_role") != role
            or identity["uri"] != lattice[role]
            or record.get("body_self_hash_field") != hash_field
            or not hash_binding_valid
        ):
            _fail("projection preparation authority record differs")
        normalized_records.append({
            "publication_ordinal": ordinal,
            "authority_role": role,
            "identity": identity,
            "body_self_hash_field": hash_field,
            "body_self_hash": body_hash,
        })
    commit = item.get("code_commit")
    digest = item.get("image_digest")
    job = item.get("reused_job_name")
    invariants = (
        item.get("schema_version") == PROJECTION_PREPARATION_RECEIPT_SCHEMA,
        item.get("contract_id") == contract.CONTRACT_ID,
        item.get("preparation_role") == "projection-first-layer-fresh-run",
        item.get("child_run_prefix") == topology["child_run_prefix"],
        code != report,
        code["uri"] == lattice["contract-module-source"],
        code["bytes"] == FROZEN_CONTRACT_MODULE_BYTES,
        code["sha256"] == FROZEN_CONTRACT_MODULE_SHA256,
        report["uri"] == lattice["preoutput-contract-source"],
        report["bytes"] == FROZEN_PREOUTPUT_REPORT_BYTES,
        report["sha256"] == FROZEN_PREOUTPUT_REPORT_SHA256,
        panel == contract.PANEL_IDENTITY,
        structural == derived_structural,
        item.get("panel_self_sha256") == contract.PANEL_SELF_SHA256,
        item.get("structural_identity_count")
        == contract.EXACT_STRUCTURAL_OBJECT_COUNT,
        item.get("structural_identities_sha256")
        == contract.canonical_sha256_v1(structural),
        type(commit) is str and _COMMIT_RE.fullmatch(commit) is not None,
        type(digest) is str
        and digest.startswith("sha256:")
        and _SHA256_RE.fullmatch(digest[7:]) is not None,
        type(job) is str and _JOB_RE.fullmatch(job) is not None,
        item.get("authority_publication_count") == len(_AUTHORITY_SPECS),
        item.get("authority_publications_sha256")
        == contract.canonical_sha256_v1(normalized_records),
        code == normalized_records[0]["identity"],
        report == normalized_records[1]["identity"],
        item.get("projection_task_manifest_identity")
        == normalized_records[-1]["identity"],
        item.get("projection_task_manifest_sha256")
        == normalized_records[-1]["body_self_hash"],
        item.get("predecessor_layer_receipt_count") == 0,
        item.get("prior_projection_identity_slot_count")
        == contract.PANEL_SLATE_COUNT,
        item.get("all_prior_projection_identities_absent") is True,
        item.get("fresh_run_only") is True,
        item.get("recovery_allowed") is False,
        item.get("one_reused_job_across_layers") is True,
        item.get("current_generation_resolution_allowed") is False,
        item.get("listing_allowed") is False,
        item.get("uses_realized_outcomes") is False,
        item.get("graph_capability_allowed") is False,
        item.get("caller_output_uri_accepted") is False,
        item.get("policy") == contract.POLICY_CLAIMS,
    )
    if not all(invariants):
        _fail("projection preparation receipt fixed authority differs")
    return item


def prepare_projection_first_layer_v1(
    *, output_prefix: str, contract_module_bytes: bytes,
    preoutput_report_bytes: bytes, code_commit: str, image_digest: str,
    reused_job_name: str,
    panel_root_body: object, panel_root_identity: object,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    """Create and exact-reopen the fresh projection layer's authority chain."""
    topology = contract.build_result_topology_v1(output_prefix)
    prefix = str(topology["output_prefix"])
    lattice = projection_preparation_uri_lattice_v1(prefix)
    authorization = task_manifest.build_pre_design_run_authorization_v1(
        output_prefix=prefix,
        code_commit=code_commit,
        image_digest=image_digest,
        reused_job_name=reused_job_name,
    )
    if (
        authorization.get("code_commit") != code_commit
        or authorization.get("image_digest") != image_digest
        or authorization.get("reused_job_name") != reused_job_name
        or authorization.get("output_prefix") != prefix
    ):
        _fail("pre-design code/image/job authority differs from preparation input")

    code_raw = _validate_frozen_source_bytes_v1(
        contract_module_bytes,
        relative_path=contract.MODULE_PATH,
        expected_bytes=FROZEN_CONTRACT_MODULE_BYTES,
        expected_sha256=FROZEN_CONTRACT_MODULE_SHA256,
        label="contract module source",
    )
    report_raw = _validate_frozen_source_bytes_v1(
        preoutput_report_bytes,
        relative_path=contract.CONTRACT_REPORT_PATH,
        expected_bytes=FROZEN_PREOUTPUT_REPORT_BYTES,
        expected_sha256=FROZEN_PREOUTPUT_REPORT_SHA256,
        label="preoutput contract report source",
    )
    panel = _identity(panel_root_identity, label="exact panel-root identity")
    if panel != contract.PANEL_IDENTITY:
        _fail("preparation input identity authority differs")
    panel_raw = _canonical_bytes(
        _mapping(panel_root_body, label="frozen panel-root body")
    )
    reopened_panel_raw, _ = _read_exact_bytes(
        panel,
        read_exact=read_exact,
        label="frozen panel root",
        maximum_bytes=int(contract.PANEL_IDENTITY["bytes"]),
    )
    if panel_raw != reopened_panel_raw:
        _fail("supplied frozen panel-root body differs from exact reopen")
    panel_root = batch.parse_canonical_json_bytes(
        reopened_panel_raw, label="frozen panel root"
    )
    structural = _validate_structural_inventory_v1(
        projection.projection_structural_identity_inventory_v1(
            panel_root, panel_identity=panel
        )
    )

    authority_values: dict[str, object] = {}
    authority_identities: dict[str, object] = {}

    code = _publish_raw_create_once_v1(
        uri=lattice["contract-module-source"],
        raw=code_raw,
        maximum_bytes=MAXIMUM_CODE_INPUT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_values["code_source"] = code_raw
    authority_identities["code_source"] = code
    report = _publish_raw_create_once_v1(
        uri=lattice["preoutput-contract-source"],
        raw=report_raw,
        maximum_bytes=MAXIMUM_REPORT_INPUT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_values["report_source"] = report_raw
    authority_identities["report_source"] = report

    task_manifest.validate_pre_design_run_authorization_v1(authorization)
    authorization_identity = _publish_json_create_once_v1(
        uri=lattice["pre-design-run-authorization"],
        value=authorization,
        maximum_bytes=task_manifest.MAXIMUM_AUTHORIZATION_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_values["pre_design_run_authorization"] = authorization
    authority_identities["pre_design_run_authorization"] = authorization_identity
    task_manifest.validate_pre_design_run_authorization_authority_v1(
        authorization,
        publication_identity=authorization_identity,
        topology=topology,
    )

    contract.validate_result_topology_v1(topology)
    topology_identity = _publish_json_create_once_v1(
        uri=lattice["topology"],
        value=topology,
        maximum_bytes=task_manifest.MAXIMUM_TOPOLOGY_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_values["topology"] = topology
    authority_identities["topology"] = topology_identity

    process_specs = task_manifest.canonical_bootstrap_process_specs_v1()
    bootstrap = contract.build_bootstrap_manifest_v1(
        topology=topology,
        topology_identity=topology_identity,
        run_identity=authorization_identity,
        code_commit=code_commit,
        image_digest=image_digest,
        process_specs=process_specs,
    )
    if (
        bootstrap.get("run_identity") != authorization_identity
        or bootstrap.get("code_commit") != code_commit
        or bootstrap.get("image_digest") != image_digest
    ):
        _fail("bootstrap code/image/run authority differs from preparation input")
    contract.validate_bootstrap_manifest_v1(bootstrap)
    bootstrap_identity = _publish_json_create_once_v1(
        uri=lattice["bootstrap-manifest"],
        value=bootstrap,
        maximum_bytes=task_manifest.MAXIMUM_BOOTSTRAP_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    contract.validate_bootstrap_manifest_authority_v1(
        bootstrap,
        publication_identity=bootstrap_identity,
        topology=topology,
        topology_identity=topology_identity,
    )
    authority_values["bootstrap_manifest"] = bootstrap
    authority_identities["bootstrap_manifest"] = bootstrap_identity

    design = contract.build_design_v1(
        output_prefix=prefix,
        code_identity=code,
        report_identity=report,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
    )
    if (
        design.get("code_identity") != code
        or design.get("report_identity") != report
    ):
        _fail("design source authority differs from preparation input")
    contract.validate_design_v1(design)
    design_identity = _publish_json_create_once_v1(
        uri=lattice["design"],
        value=design,
        maximum_bytes=task_manifest.MAXIMUM_DESIGN_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    contract.validate_design_authority_v1(
        design, publication_identity=design_identity
    )
    authority_values["design"] = design
    authority_identities["design"] = design_identity

    budget = contract.compile_publisher_process_budget_v1(
        process_role="projection-publisher",
        design=design,
        design_publication_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
        launch_intent_identity=authorization_identity,
        scientific_read_identities=structural,
    )
    contract.validate_publisher_process_budget_v1(
        budget,
        design=design,
        design_publication_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
        launch_intent_identity=authorization_identity,
    )
    _validate_projection_budget_inventory_v1(
        budget, structural_identities=structural
    )
    budget_identity = _publish_json_create_once_v1(
        uri=lattice["projection-publisher-process-budget"],
        value=budget,
        maximum_bytes=task_manifest.MAXIMUM_PROCESS_BUDGET_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_values["projection_process_budget"] = budget
    authority_identities["projection_process_budget"] = budget_identity

    request = task_manifest.build_projection_task_request_v1(
        design_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest_identity=bootstrap_identity,
        pre_design_run_authorization_identity=authorization_identity,
        process_budget_identity=budget_identity,
        prior_projection_identities=[None] * contract.PANEL_SLATE_COUNT,
    )
    task_manifest.validate_projection_task_request_v1(request)
    if request["prior_projection_identities"] != [
        None
    ] * contract.PANEL_SLATE_COUNT:
        _fail("projection preparation is not a fresh run")
    request_identity = _publish_json_create_once_v1(
        uri=lattice["projection-task-request"],
        value=request,
        maximum_bytes=MAXIMUM_PROJECTION_TASK_REQUEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    authority_values["projection_task_request"] = request
    authority_identities["projection_task_request"] = request_identity

    manifest = task_manifest.build_task_manifest_v1(
        layer_id="projection",
        design=design,
        design_identity=design_identity,
        topology=topology,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
        pre_design_run_authorization=authorization,
        pre_design_run_authorization_identity=authorization_identity,
        task_requests=[request],
        predecessor_layer_receipts=[],
        projection_process_budget=budget,
    )
    if manifest["manifest_uri"] != lattice["projection-task-manifest"]:
        _fail("projection task-manifest URI differs from the preparation lattice")
    if (
        manifest.get("code_commit") != code_commit
        or manifest.get("image_digest") != image_digest
        or manifest.get("reused_job_name") != reused_job_name
    ):
        _fail("projection manifest code/image/job authority differs")
    manifest_identity = task_manifest.publish_task_manifest_v1(
        manifest,
        prior_identity=None,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    task_manifest.validate_task_manifest_authority_v1(
        manifest,
        publication_identity=manifest_identity,
        design=design,
        topology=topology,
        bootstrap_manifest=bootstrap,
        pre_design_run_authorization=authorization,
        predecessor_layer_receipts=[],
        projection_process_budget=budget,
    )
    authority_values["projection_task_manifest"] = manifest
    authority_identities["projection_task_manifest"] = manifest_identity

    reopened = task_manifest.reopen_task_manifest_authority_v1(
        manifest_identity, read_exact=read_exact
    )
    if (
        reopened["manifest"] != manifest
        or reopened["pre_design_run_authorization"] != authorization
        or reopened["topology"] != topology
        or reopened["bootstrap_manifest"] != bootstrap
        or reopened["design"] != design
        or reopened["projection_process_budget"] != budget
        or reopened["predecessor_layer_receipts"] != []
        or manifest["task_bindings"][0]["request"] != request
    ):
        _fail("projection task-manifest exact authority reopen differs")

    receipt = build_projection_preparation_receipt_v1(
        output_prefix=prefix,
        code_identity=code,
        report_identity=report,
        panel_root_body=panel_root,
        panel_root_identity=panel,
        structural_identities=structural,
        code_commit=code_commit,
        image_digest=image_digest,
        reused_job_name=reused_job_name,
        authority_values=authority_values,
        authority_identities=authority_identities,
    )
    receipt_identity = _publish_json_create_once_v1(
        uri=lattice["projection-preparation-receipt"],
        value=receipt,
        maximum_bytes=MAXIMUM_PROJECTION_PREPARATION_RECEIPT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )

    return {
        "code_identity": deepcopy(code),
        "report_identity": deepcopy(report),
        "pre_design_run_authorization_identity": deepcopy(authorization_identity),
        "topology_identity": deepcopy(topology_identity),
        "bootstrap_manifest_identity": deepcopy(bootstrap_identity),
        "design_identity": deepcopy(design_identity),
        "projection_process_budget_identity": deepcopy(budget_identity),
        "projection_task_request_identity": deepcopy(request_identity),
        "projection_task_manifest_identity": deepcopy(manifest_identity),
        "manifest_identity": deepcopy(manifest_identity),
        "preparation_receipt_identity": deepcopy(receipt_identity),
        "preparation_receipt": deepcopy(receipt),
        "structural_identities": deepcopy(structural),
    }


__all__ = [
    "CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error",
    "MAXIMUM_CODE_INPUT_BYTES",
    "FROZEN_CONTRACT_MODULE_BYTES",
    "FROZEN_CONTRACT_MODULE_SHA256",
    "FROZEN_PREOUTPUT_REPORT_BYTES",
    "FROZEN_PREOUTPUT_REPORT_SHA256",
    "MAXIMUM_PROJECTION_PREPARATION_RECEIPT_BYTES",
    "MAXIMUM_PROJECTION_TASK_REQUEST_BYTES",
    "MAXIMUM_REPORT_INPUT_BYTES",
    "PROJECTION_PREPARATION_RECEIPT_SCHEMA",
    "build_projection_preparation_receipt_v1",
    "prepare_projection_first_layer_v1",
    "projection_preparation_uri_lattice_v1",
    "validate_projection_preparation_receipt_v1",
]
