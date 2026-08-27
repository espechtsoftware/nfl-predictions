"""Root-last publication of the exact fixed-G0 R6 candidate population.

The predecessor module :mod:`corpus_r6_fixed_g0_candidate_authority_v1`
does the expensive scientific work: it reopens the tracked G0 panel, all 54
accepted tasks, all 378 arm results, and the terminal structural-catalog
chain, then derives the complete unique-roster population and every original
arm/visit occurrence.  It deliberately does not own publication.

This module closes that final authority boundary.  Callers provide neither
candidate bytes nor candidate identities nor an output namespace.  A publish
run derives all 54 candidate artifacts, writes every artifact, exact
occurrence sidecar, and derivation receipt create-once, exact-reopens them,
and writes a terminal root last.  The public reopener follows only the
mechanically scoped identities in that root and invokes the predecessor's
full 54-slate replay before returning candidate-population or occurrence-
lineage authority.

No function accepts a score, outcome source, selector, graph writer, fill
policy, retrieval policy, or production-policy authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as core
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


RELEASE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-release/v1"
)
OBJECT_DESCRIPTOR_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-object-descriptor/v1"
)
PUBLICATION_MODE: Final = "create_once_root_last"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = (
    "research/corpus-r6-fixed-g0-candidate-authorities"
)
ROOT_FILENAME: Final = "candidate-authority-release.json"
CANDIDATE_RELEASE_FILENAME: Final = "accepted-candidate-release.json"
PANEL_RECEIPT_FILENAME: Final = "panel-derivation-receipt.json"
LINEAGE_FILENAME: Final = "exact-occurrence-lineage.json"
SLATE_RECEIPT_FILENAME: Final = "slate-derivation-receipt.json"
EXPECTED_ARM_RESULT_COUNT: Final = source.TASK_COUNT * core.EXPECTED_ARM_COUNT

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PREFIX = re.compile(
    rf"^gs://{re.escape(OUTPUT_BUCKET)}/{re.escape(OUTPUT_NAMESPACE)}/"
    r"(?P<run_id>[a-z0-9][a-z0-9-]{7,80})/$"
)

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], object]
GitHead = core.GitHead
GitBlob = core.GitBlob
GitStatus = core.GitStatus

_FALSE_AUTHORITY_FIELDS: Final = tuple(source.FALSE_AUTHORITY_FIELDS)
_DESCRIPTOR_FIELDS: Final = frozenset({
    "schema_version",
    "source_task_ordinal",
    "task_id",
    "slate",
    "candidate_artifact_identity",
    "candidate_artifact_sha256",
    "candidate_count",
    "ordered_candidate_ids_sha256",
    "lineage_sidecar_identity",
    "lineage_sidecar_sha256",
    "candidate_lineage_manifest_sha256",
    "visit_occurrence_count",
    "slate_derivation_identity",
    "slate_derivation_sha256",
    "object_descriptor_sha256",
})
_ROOT_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "target_uri",
    "run_id",
    "namespace",
    "catalog_replay_receipt_identity",
    "catalog_replay_receipt_sha256",
    "fixed_g0_panel_identity",
    "fixed_g0_panel_index_sha256",
    "candidate_release_identity",
    "candidate_release_sha256",
    "panel_derivation_identity",
    "panel_derivation_sha256",
    "task_count",
    "arm_result_count",
    "total_candidate_count",
    "total_visit_occurrence_count",
    "objects",
    "object_manifest_sha256",
    "candidate_population_authority",
    "exact_occurrence_provenance_authority",
    "authoritative_reopen_required",
    "structure_only_validation_authority",
    "complete",
    "all_candidate_generations_resolved_before_root_build",
    "every_output_exact_reopened",
    "every_predecessor_replayed",
    "root_create_once_requested_last",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "candidate_authority_release_sha256",
})


class CorpusR6FixedG0CandidateAuthorityReleaseV1Error(ValueError):
    """The fixed-G0 candidate publication or exact replay failed closed."""


@dataclass(frozen=True)
class ReopenedFixedG0CandidateAuthorityV1:
    """Authoritative, predecessor-replayed terminal release contents."""

    root: dict[str, object]
    root_identity: dict[str, object]
    authority_bundle: dict[str, object]
    candidate_release: dict[str, object]
    candidate_release_identity: dict[str, object]


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        value = as_dict()
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    body[field] = canonical_sha256(body)
    return body


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} SHA")
    if retained != canonical_sha256({
        key: nested for key, nested in value.items() if key != field
    }):
        _fail(f"{label} self-hash differs")
    return retained


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def output_prefix_for_run_v1(run_id: object) -> str:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("candidate-authority run ID differs")
    return (
        f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{run_id}/"
    )


def _prefix_from_root_identity(
    identity: Mapping[str, object],
) -> tuple[str, str]:
    uri = str(identity["uri"])
    suffix = ROOT_FILENAME
    if not uri.endswith(suffix):
        _fail("candidate-authority root URI differs")
    prefix = uri.removesuffix(suffix)
    match = _PREFIX.fullmatch(prefix)
    if match is None:
        _fail("candidate-authority root escapes the fixed namespace")
    return prefix, match.group("run_id")


def _scoped_reader(*, read_exact: ReadExact, prefix: str) -> ReadExact:
    if not callable(read_exact):
        _fail("candidate-authority exact reader differs")

    def read_scoped(identity_value: Mapping[str, object]) -> bytes:
        retained = _identity(identity_value, label="candidate-authority output")
        if not str(retained["uri"]).startswith(prefix):
            _fail("candidate-authority output identity escapes its run prefix")
        return read_exact(retained)

    return read_scoped


def _parse_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty canonical JSON bytes")

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(
            f"{label} is not valid JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return body


def _exact_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    return _parse_canonical_json(raw, label=label), identity


def _publish_json(
    body: Mapping[str, object],
    *,
    target_uri: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw = canonical_json_bytes(body)
    try:
        published = publish_create_once(target_uri, raw)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, label=f"{label} published identity")
    if (
        identity["uri"] != target_uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} create-once identity differs from intended bytes")
    reopened, reopened_identity = _exact_json(
        identity, read_exact=read_exact, label=label
    )
    if (
        reopened_identity != identity
        or canonical_json_bytes(reopened) != raw
    ):
        _fail(f"{label} exact reopen differs from intended bytes")
    return reopened, identity


def _bundle_lists(
    bundle: Mapping[str, object],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    if bundle.get("schema_version") != core.AUTHORITY_BUNDLE_SCHEMA:
        _fail("candidate-authority predecessor bundle schema differs")
    _self_hash(
        bundle,
        field="candidate_authority_bundle_sha256",
        label="candidate-authority predecessor bundle",
    )
    if bundle.get("task_count") != source.TASK_COUNT:
        _fail("candidate-authority predecessor bundle task count differs")
    if bundle.get("outcome_columns_read") != [] or any(
        bundle.get(field) is not False
        for field in ("uses_realized_outcomes", *_FALSE_AUTHORITY_FIELDS)
    ):
        _fail("candidate-authority predecessor bundle policy differs")
    candidate_release = source.validate_accepted_candidate_release_v1(
        bundle.get("candidate_release")
    )
    artifacts = [
        source.validate_accepted_candidate_artifact_v1(value)
        for value in _sequence(
            bundle.get("candidate_artifacts"), label="candidate artifacts"
        )
    ]
    sidecars = [
        _mapping(value, label=f"candidate lineage sidecar[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(bundle.get("lineage_sidecars"), label="lineage sidecars")
        )
    ]
    receipts = [
        _mapping(value, label=f"candidate derivation receipt[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            bundle.get("slate_derivation_receipts"),
            label="slate derivation receipts",
        ))
    ]
    panel = _mapping(
        bundle.get("panel_derivation_receipt"),
        label="candidate panel derivation receipt",
    )
    if panel.get("schema_version") != core.PANEL_DERIVATION_SCHEMA:
        _fail("candidate panel derivation schema differs")
    _self_hash(
        panel,
        field="panel_derivation_sha256",
        label="candidate panel derivation receipt",
    )
    if not (
        len(artifacts)
        == len(sidecars)
        == len(receipts)
        == source.TASK_COUNT
    ):
        _fail("candidate-authority predecessor bundle census differs")
    if (
        bundle.get("candidate_artifact_manifest_sha256")
        != canonical_sha256(artifacts)
        or bundle.get("lineage_sidecar_manifest_sha256")
        != canonical_sha256(sidecars)
        or bundle.get("slate_derivation_manifest_sha256")
        != canonical_sha256(receipts)
    ):
        _fail("candidate-authority predecessor manifests differ")
    return candidate_release, artifacts, sidecars, receipts, panel


def _object_descriptor(
    *,
    prefix: str,
    source_task_ordinal: int,
    artifact: Mapping[str, object],
    artifact_identity: Mapping[str, object],
    sidecar: Mapping[str, object],
    sidecar_identity: Mapping[str, object],
    receipt: Mapping[str, object],
    receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    slate = catalog_v1.expected_slate_for_source_task(source_task_ordinal)
    task_id = catalog_v1.task_id_for_source_task(source_task_ordinal)
    slate_id = slate["slate_id"]
    base = f"{prefix}source-task-{source_task_ordinal:02d}-{slate_id}/"
    retained_artifact_identity = _identity(
        artifact_identity, label="candidate artifact identity"
    )
    retained_sidecar_identity = _identity(
        sidecar_identity, label="lineage sidecar identity"
    )
    retained_receipt_identity = _identity(
        receipt_identity, label="slate derivation identity"
    )
    if (
        retained_artifact_identity["uri"] != f"{base}accepted-candidates.json"
        or retained_sidecar_identity["uri"] != f"{base}{LINEAGE_FILENAME}"
        or retained_receipt_identity["uri"] != f"{base}{SLATE_RECEIPT_FILENAME}"
        or artifact.get("source_task_ordinal") != source_task_ordinal
        or artifact.get("task_id") != task_id
        or artifact.get("slate") != slate
        or sidecar.get("schema_version") != core.LINEAGE_SIDECAR_SCHEMA
        or sidecar.get("source_task_ordinal") != source_task_ordinal
        or sidecar.get("task_id") != task_id
        or sidecar.get("slate") != slate
        or receipt.get("schema_version") != core.SLATE_DERIVATION_SCHEMA
        or receipt.get("source_task_ordinal") != source_task_ordinal
        or receipt.get("task_id") != task_id
        or receipt.get("slate") != slate
        or receipt.get("candidate_artifact_identity")
        != retained_artifact_identity
        or receipt.get("candidate_artifact_sha256")
        != artifact.get("candidate_artifact_sha256")
        or receipt.get("candidate_count") != artifact.get("candidate_count")
        or receipt.get("ordered_candidate_ids_sha256")
        != artifact.get("ordered_candidate_ids_sha256")
        or receipt.get("lineage_sidecar_sha256")
        != sidecar.get("candidate_lineage_sidecar_sha256")
        or receipt.get("candidate_lineage_manifest_sha256")
        != sidecar.get("candidate_lineage_manifest_sha256")
        or sidecar.get("candidate_count") != artifact.get("candidate_count")
    ):
        _fail(f"candidate-authority object[{source_task_ordinal}] binding differs")
    _self_hash(
        sidecar,
        field="candidate_lineage_sidecar_sha256",
        label=f"candidate lineage sidecar[{source_task_ordinal}]",
    )
    _self_hash(
        receipt,
        field="slate_derivation_sha256",
        label=f"slate derivation receipt[{source_task_ordinal}]",
    )
    body: dict[str, object] = {
        "schema_version": OBJECT_DESCRIPTOR_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "task_id": task_id,
        "slate": slate,
        "candidate_artifact_identity": retained_artifact_identity,
        "candidate_artifact_sha256": _digest(
            artifact.get("candidate_artifact_sha256"),
            label="candidate artifact SHA",
        ),
        "candidate_count": _integer(
            artifact.get("candidate_count"),
            label="candidate count",
            minimum=source.ENTRY_BUDGET,
        ),
        "ordered_candidate_ids_sha256": _digest(
            artifact.get("ordered_candidate_ids_sha256"),
            label="ordered candidate IDs SHA",
        ),
        "lineage_sidecar_identity": retained_sidecar_identity,
        "lineage_sidecar_sha256": _digest(
            sidecar.get("candidate_lineage_sidecar_sha256"),
            label="lineage sidecar SHA",
        ),
        "candidate_lineage_manifest_sha256": _digest(
            sidecar.get("candidate_lineage_manifest_sha256"),
            label="candidate lineage manifest SHA",
        ),
        "visit_occurrence_count": _integer(
            sidecar.get("visit_occurrence_count"),
            label="visit occurrence count",
            minimum=int(artifact["candidate_count"]),
        ),
        "slate_derivation_identity": retained_receipt_identity,
        "slate_derivation_sha256": _digest(
            receipt.get("slate_derivation_sha256"),
            label="slate derivation SHA",
        ),
    }
    return _with_hash(body, field="object_descriptor_sha256")


def _build_root(
    *,
    prefix: str,
    run_id: str,
    bundle: Mapping[str, object],
    candidate_release_identity: Mapping[str, object],
    panel_identity: Mapping[str, object],
    artifact_identities: Sequence[Mapping[str, object]],
    sidecar_identities: Sequence[Mapping[str, object]],
    receipt_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    candidate_release, artifacts, sidecars, receipts, panel = _bundle_lists(bundle)
    if not (
        len(artifact_identities)
        == len(sidecar_identities)
        == len(receipt_identities)
        == source.TASK_COUNT
    ):
        _fail("candidate-authority output identity census differs")
    retained_candidate_release_identity = _identity(
        candidate_release_identity, label="candidate release identity"
    )
    retained_panel_identity = _identity(
        panel_identity, label="panel derivation identity"
    )
    if (
        retained_candidate_release_identity["uri"]
        != f"{prefix}{CANDIDATE_RELEASE_FILENAME}"
        or retained_panel_identity["uri"] != f"{prefix}{PANEL_RECEIPT_FILENAME}"
        or candidate_release.get("namespace") != prefix
        or candidate_release.get("release_id") != run_id
        or panel.get("candidate_release_id") != run_id
        or panel.get("candidate_namespace") != prefix
        or panel.get("candidate_release_sha256")
        != candidate_release.get("accepted_candidate_release_sha256")
        or panel.get("candidate_release_body_sha256")
        != canonical_sha256(candidate_release)
    ):
        _fail("candidate-authority release/panel binding differs")
    descriptors = [
        _object_descriptor(
            prefix=prefix,
            source_task_ordinal=ordinal,
            artifact=artifacts[ordinal],
            artifact_identity=artifact_identities[ordinal],
            sidecar=sidecars[ordinal],
            sidecar_identity=sidecar_identities[ordinal],
            receipt=receipts[ordinal],
            receipt_identity=receipt_identities[ordinal],
        )
        for ordinal in range(source.TASK_COUNT)
    ]
    release_entries = [
        _mapping(value, label=f"candidate release entry[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            candidate_release.get("entries"), label="candidate release entries"
        ))
    ]
    panel_rows = [
        _mapping(value, label=f"candidate panel slate[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(panel.get("slates"), label="candidate panel slates")
        )
    ]
    if (
        len(release_entries) != source.TASK_COUNT
        or len(panel_rows) != source.TASK_COUNT
        or candidate_release.get("source_candidate_panel_identity")
        != panel.get("fixed_g0_panel_identity")
    ):
        _fail("candidate release/panel exact lattice differs")
    for ordinal, descriptor in enumerate(descriptors):
        release_entry = release_entries[ordinal]
        panel_row = panel_rows[ordinal]
        if (
            release_entry.get("source_task_ordinal") != ordinal
            or release_entry.get("task_id") != descriptor["task_id"]
            or release_entry.get("slate") != descriptor["slate"]
            or release_entry.get("candidate_artifact_identity")
            != descriptor["candidate_artifact_identity"]
            or release_entry.get("candidate_count")
            != descriptor["candidate_count"]
            or release_entry.get("ordered_candidate_ids_sha256")
            != descriptor["ordered_candidate_ids_sha256"]
            or panel_row.get("source_task_ordinal") != ordinal
            or panel_row.get("task_id") != descriptor["task_id"]
            or panel_row.get("slate") != descriptor["slate"]
            or panel_row.get("candidate_artifact_identity")
            != descriptor["candidate_artifact_identity"]
            or panel_row.get("candidate_count") != descriptor["candidate_count"]
            or panel_row.get("ordered_candidate_ids_sha256")
            != descriptor["ordered_candidate_ids_sha256"]
            or panel_row.get("lineage_sidecar_sha256")
            != descriptor["lineage_sidecar_sha256"]
            or panel_row.get("slate_derivation_sha256")
            != descriptor["slate_derivation_sha256"]
        ):
            _fail(f"candidate release/panel lattice[{ordinal}] differs")
    total_candidates = sum(int(row["candidate_count"]) for row in descriptors)
    total_visits = sum(int(row["visit_occurrence_count"]) for row in descriptors)
    if (
        panel.get("task_count") != source.TASK_COUNT
        or panel.get("arm_result_count") != EXPECTED_ARM_RESULT_COUNT
        or panel.get("total_candidate_count") != total_candidates
        or panel.get("total_visit_occurrence_count") != total_visits
    ):
        _fail("candidate-authority panel aggregate binding differs")
    body: dict[str, object] = {
        "schema_version": RELEASE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": f"{prefix}{ROOT_FILENAME}",
        "run_id": run_id,
        "namespace": prefix,
        "catalog_replay_receipt_identity": _identity(
            panel.get("catalog_replay_receipt_identity"),
            label="catalog replay receipt identity",
        ),
        "catalog_replay_receipt_sha256": _digest(
            panel.get("catalog_replay_receipt_sha256"),
            label="catalog replay receipt SHA",
        ),
        "fixed_g0_panel_identity": _identity(
            panel.get("fixed_g0_panel_identity"),
            label="fixed G0 panel identity",
        ),
        "fixed_g0_panel_index_sha256": _digest(
            panel.get("fixed_g0_panel_index_sha256"),
            label="fixed G0 panel-index SHA",
        ),
        "candidate_release_identity": retained_candidate_release_identity,
        "candidate_release_sha256": _digest(
            candidate_release.get("accepted_candidate_release_sha256"),
            label="accepted candidate release SHA",
        ),
        "panel_derivation_identity": retained_panel_identity,
        "panel_derivation_sha256": _digest(
            panel.get("panel_derivation_sha256"),
            label="panel derivation SHA",
        ),
        "task_count": source.TASK_COUNT,
        "arm_result_count": EXPECTED_ARM_RESULT_COUNT,
        "total_candidate_count": total_candidates,
        "total_visit_occurrence_count": total_visits,
        "objects": descriptors,
        "object_manifest_sha256": canonical_sha256(descriptors),
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
        "all_candidate_generations_resolved_before_root_build": True,
        "every_output_exact_reopened": True,
        "every_predecessor_replayed": True,
        "root_create_once_requested_last": True,
        **_policy(),
    }
    return _with_hash(body, field="candidate_authority_release_sha256")


def validate_fixed_g0_candidate_authority_release_structure_v1(
    value: object,
) -> dict[str, object]:
    """Validate the terminal layout only; this grants no authority."""
    root = _mapping(value, label="candidate-authority release root")
    _exact_keys(root, _ROOT_FIELDS, label="candidate-authority release root")
    _self_hash(
        root,
        field="candidate_authority_release_sha256",
        label="candidate-authority release root",
    )
    target_uri = root.get("target_uri")
    if type(target_uri) is not str:
        _fail("candidate-authority target URI differs")
    prefix, run_id = _prefix_from_root_identity({
        "uri": target_uri,
        "generation": "1",
        "sha256": "0" * 64,
        "bytes": 1,
    })
    catalog_receipt_identity = _identity(
        root.get("catalog_replay_receipt_identity"),
        label="catalog replay receipt identity",
    )
    expected_catalog_receipt_uri = (
        f"{core.catalog_adapter.FIXED_CATALOG_NAMESPACE}"
        f"{core.CATALOG_REPLAY_RECEIPT_FILENAME}"
    )
    candidate_release_identity = _identity(
        root.get("candidate_release_identity"),
        label="candidate release identity",
    )
    panel_identity = _identity(
        root.get("panel_derivation_identity"),
        label="panel derivation identity",
    )
    _identity(root.get("fixed_g0_panel_identity"), label="fixed G0 panel")
    if (
        root.get("schema_version") != RELEASE_SCHEMA
        or root.get("publication_mode") != PUBLICATION_MODE
        or root.get("run_id") != run_id
        or root.get("namespace") != prefix
        or catalog_receipt_identity["uri"] != expected_catalog_receipt_uri
        or candidate_release_identity["uri"]
        != f"{prefix}{CANDIDATE_RELEASE_FILENAME}"
        or panel_identity["uri"] != f"{prefix}{PANEL_RECEIPT_FILENAME}"
        or root.get("task_count") != source.TASK_COUNT
        or root.get("arm_result_count") != EXPECTED_ARM_RESULT_COUNT
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("authoritative_reopen_required") is not True
        or root.get("structure_only_validation_authority") is not False
        or root.get("complete") is not True
        or root.get("all_candidate_generations_resolved_before_root_build")
        is not True
        or root.get("every_output_exact_reopened") is not True
        or root.get("every_predecessor_replayed") is not True
        or root.get("root_create_once_requested_last") is not True
        or root.get("outcome_columns_read") != []
        or root.get("uses_realized_outcomes") is not False
        or any(root.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("candidate-authority release policy or namespace differs")
    for field in (
        "catalog_replay_receipt_sha256",
        "fixed_g0_panel_index_sha256",
        "candidate_release_sha256",
        "panel_derivation_sha256",
        "object_manifest_sha256",
    ):
        _digest(root.get(field), label=field)
    rows = [
        _mapping(value, label=f"candidate object descriptor[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(root.get("objects"), label="candidate object descriptors")
        )
    ]
    if (
        len(rows) != source.TASK_COUNT
        or root.get("object_manifest_sha256") != canonical_sha256(rows)
    ):
        _fail("candidate-authority object census/hash differs")
    seen_identities: set[tuple[str, str, str, int]] = set()
    for ordinal, row in enumerate(rows):
        _exact_keys(row, _DESCRIPTOR_FIELDS, label="candidate object descriptor")
        _self_hash(
            row,
            field="object_descriptor_sha256",
            label=f"candidate object descriptor[{ordinal}]",
        )
        slate = catalog_v1.expected_slate_for_source_task(ordinal)
        task_id = catalog_v1.task_id_for_source_task(ordinal)
        base = f"{prefix}source-task-{ordinal:02d}-{slate['slate_id']}/"
        artifact_identity = _identity(
            row.get("candidate_artifact_identity"),
            label=f"candidate artifact[{ordinal}]",
        )
        sidecar_identity = _identity(
            row.get("lineage_sidecar_identity"),
            label=f"lineage sidecar[{ordinal}]",
        )
        receipt_identity = _identity(
            row.get("slate_derivation_identity"),
            label=f"slate derivation[{ordinal}]",
        )
        identities = (artifact_identity, sidecar_identity, receipt_identity)
        keys = {
            (
                str(identity["uri"]),
                str(identity["generation"]),
                str(identity["sha256"]),
                int(identity["bytes"]),
            )
            for identity in identities
        }
        if (
            row.get("schema_version") != OBJECT_DESCRIPTOR_SCHEMA
            or row.get("source_task_ordinal") != ordinal
            or row.get("task_id") != task_id
            or row.get("slate") != slate
            or artifact_identity["uri"] != f"{base}accepted-candidates.json"
            or sidecar_identity["uri"] != f"{base}{LINEAGE_FILENAME}"
            or receipt_identity["uri"] != f"{base}{SLATE_RECEIPT_FILENAME}"
            or len(keys) != 3
            or any(key in seen_identities for key in keys)
            or _integer(
                row.get("candidate_count"),
                label="candidate count",
                minimum=source.ENTRY_BUDGET,
            )
            > _integer(
                row.get("visit_occurrence_count"),
                label="visit occurrence count",
                minimum=source.ENTRY_BUDGET,
            )
        ):
            _fail(f"candidate object descriptor[{ordinal}] differs")
        for field in (
            "candidate_artifact_sha256",
            "ordered_candidate_ids_sha256",
            "lineage_sidecar_sha256",
            "candidate_lineage_manifest_sha256",
            "slate_derivation_sha256",
        ):
            _digest(row.get(field), label=f"descriptor {field}")
        seen_identities.update(keys)
    if (
        root.get("total_candidate_count")
        != sum(int(row["candidate_count"]) for row in rows)
        or root.get("total_visit_occurrence_count")
        != sum(int(row["visit_occurrence_count"]) for row in rows)
    ):
        _fail("candidate-authority aggregate census differs")
    return root


def publish_fixed_g0_candidate_authority_release_v1(
    *,
    run_id: object,
    repository_root: Path,
    catalog_replay_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[dict[str, object], dict[str, object]]:
    """Derive and publish all fixed-G0 candidates and exact lineage root-last."""
    prefix = output_prefix_for_run_v1(run_id)
    retained_run_id = str(run_id)
    if not callable(read_exact) or not callable(publish_create_once):
        _fail("candidate-authority read/publish boundary differs")
    output_reader = _scoped_reader(read_exact=read_exact, prefix=prefix)
    try:
        material = core.derive_fixed_g0_candidate_material_v1(
            repository_root=repository_root,
            catalog_replay_receipt_identity=catalog_replay_receipt_identity,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(
            f"fixed-G0 candidate derivation failed: {exc}"
        ) from exc
    artifacts = [
        source.validate_accepted_candidate_artifact_v1(value)
        for value in _sequence(
            material.get("candidate_artifacts"), label="derived candidate artifacts"
        )
    ]
    if (
        material.get("schema_version") != core.MATERIAL_SCHEMA
        or material.get("task_count") != source.TASK_COUNT
        or len(artifacts) != source.TASK_COUNT
        or material.get("candidate_artifact_manifest_sha256")
        != canonical_sha256(artifacts)
    ):
        _fail("derived fixed-G0 candidate material differs")
    artifact_identities: list[dict[str, object]] = []
    for ordinal, artifact in enumerate(artifacts):
        slate_id = artifact["slate"]["slate_id"]
        target_uri = (
            f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
            "accepted-candidates.json"
        )
        _, identity = _publish_json(
            artifact,
            target_uri=target_uri,
            publish_create_once=publish_create_once,
            read_exact=output_reader,
            label=f"candidate artifact[{ordinal}]",
        )
        artifact_identities.append(identity)
    # Do not retain two complete 54-slate derivations simultaneously.  The
    # authoritative builder below independently replays G0 and then binds the
    # exact generations just published.
    del material
    del artifacts
    try:
        bundle = core.build_fixed_g0_candidate_authority_v1(
            release_id=retained_run_id,
            namespace=prefix,
            repository_root=repository_root,
            catalog_replay_receipt_identity=catalog_replay_receipt_identity,
            candidate_artifact_identities=artifact_identities,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(
            f"fixed-G0 candidate authority build failed: {exc}"
        ) from exc
    candidate_release, artifacts, sidecars, receipts, panel = _bundle_lists(bundle)
    sidecar_identities: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    for ordinal, sidecar in enumerate(sidecars):
        slate_id = sidecar["slate"]["slate_id"]
        base = f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
        _, identity = _publish_json(
            sidecar,
            target_uri=f"{base}{LINEAGE_FILENAME}",
            publish_create_once=publish_create_once,
            read_exact=output_reader,
            label=f"exact occurrence lineage[{ordinal}]",
        )
        sidecar_identities.append(identity)
    for ordinal, receipt in enumerate(receipts):
        slate_id = receipt["slate"]["slate_id"]
        base = f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
        _, identity = _publish_json(
            receipt,
            target_uri=f"{base}{SLATE_RECEIPT_FILENAME}",
            publish_create_once=publish_create_once,
            read_exact=output_reader,
            label=f"slate derivation receipt[{ordinal}]",
        )
        receipt_identities.append(identity)
    _, candidate_release_identity = _publish_json(
        candidate_release,
        target_uri=f"{prefix}{CANDIDATE_RELEASE_FILENAME}",
        publish_create_once=publish_create_once,
        read_exact=output_reader,
        label="accepted candidate release",
    )
    _, panel_identity = _publish_json(
        panel,
        target_uri=f"{prefix}{PANEL_RECEIPT_FILENAME}",
        publish_create_once=publish_create_once,
        read_exact=output_reader,
        label="candidate panel derivation receipt",
    )
    root = _build_root(
        prefix=prefix,
        run_id=retained_run_id,
        bundle=bundle,
        candidate_release_identity=candidate_release_identity,
        panel_identity=panel_identity,
        artifact_identities=artifact_identities,
        sidecar_identities=sidecar_identities,
        receipt_identities=receipt_identities,
    )
    validate_fixed_g0_candidate_authority_release_structure_v1(root)
    reopened_root, root_identity = _publish_json(
        root,
        target_uri=f"{prefix}{ROOT_FILENAME}",
        publish_create_once=publish_create_once,
        read_exact=output_reader,
        label="candidate-authority release root",
    )
    retained_root = validate_fixed_g0_candidate_authority_release_structure_v1(
        reopened_root
    )
    if canonical_json_bytes(retained_root) != canonical_json_bytes(root):
        _fail("candidate-authority root exact reopen differs")
    return retained_root, root_identity


def _assemble_bundle(
    *,
    candidate_release: Mapping[str, object],
    artifacts: Sequence[Mapping[str, object]],
    sidecars: Sequence[Mapping[str, object]],
    receipts: Sequence[Mapping[str, object]],
    panel: Mapping[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": core.AUTHORITY_BUNDLE_SCHEMA,
        "candidate_release": dict(candidate_release),
        "candidate_artifacts": [dict(value) for value in artifacts],
        "candidate_artifact_manifest_sha256": canonical_sha256(artifacts),
        "lineage_sidecars": [dict(value) for value in sidecars],
        "lineage_sidecar_manifest_sha256": canonical_sha256(sidecars),
        "slate_derivation_receipts": [dict(value) for value in receipts],
        "slate_derivation_manifest_sha256": canonical_sha256(receipts),
        "panel_derivation_receipt": dict(panel),
        "task_count": source.TASK_COUNT,
        **_policy(),
    }
    return _with_hash(body, field="candidate_authority_bundle_sha256")


def reopen_fixed_g0_candidate_authority_release_v1(
    root_identity: object,
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> ReopenedFixedG0CandidateAuthorityV1:
    """Exact-open every output and predecessor-replay all 54 accepted tasks."""
    retained_root_identity = _identity(
        root_identity, label="candidate-authority root identity"
    )
    prefix, run_id = _prefix_from_root_identity(retained_root_identity)
    output_reader = _scoped_reader(read_exact=read_exact, prefix=prefix)
    root_body, reopened_root_identity = _exact_json(
        retained_root_identity,
        read_exact=output_reader,
        label="candidate-authority release root",
    )
    root = validate_fixed_g0_candidate_authority_release_structure_v1(root_body)
    if root.get("target_uri") != reopened_root_identity["uri"]:
        _fail("candidate-authority root outer identity differs")
    candidate_release_body, candidate_release_identity = _exact_json(
        root["candidate_release_identity"],
        read_exact=output_reader,
        label="accepted candidate release",
    )
    candidate_release = source.validate_accepted_candidate_release_v1(
        candidate_release_body
    )
    panel, panel_identity = _exact_json(
        root["panel_derivation_identity"],
        read_exact=output_reader,
        label="candidate panel derivation receipt",
    )
    artifacts: list[dict[str, object]] = []
    sidecars: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    artifact_identities: list[dict[str, object]] = []
    sidecar_identities: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    for ordinal, raw_descriptor in enumerate(
        _sequence(root["objects"], label="candidate object descriptors")
    ):
        descriptor = _mapping(
            raw_descriptor, label=f"candidate object descriptor[{ordinal}]"
        )
        artifact_body, artifact_identity = _exact_json(
            descriptor["candidate_artifact_identity"],
            read_exact=output_reader,
            label=f"candidate artifact[{ordinal}]",
        )
        artifact = source.validate_accepted_candidate_artifact_v1(artifact_body)
        sidecar, sidecar_identity = _exact_json(
            descriptor["lineage_sidecar_identity"],
            read_exact=output_reader,
            label=f"exact occurrence lineage[{ordinal}]",
        )
        receipt, receipt_identity = _exact_json(
            descriptor["slate_derivation_identity"],
            read_exact=output_reader,
            label=f"slate derivation receipt[{ordinal}]",
        )
        expected_descriptor = _object_descriptor(
            prefix=prefix,
            source_task_ordinal=ordinal,
            artifact=artifact,
            artifact_identity=artifact_identity,
            sidecar=sidecar,
            sidecar_identity=sidecar_identity,
            receipt=receipt,
            receipt_identity=receipt_identity,
        )
        if canonical_json_bytes(descriptor) != canonical_json_bytes(
            expected_descriptor
        ):
            _fail(f"candidate object descriptor[{ordinal}] body binding differs")
        artifacts.append(artifact)
        sidecars.append(sidecar)
        receipts.append(receipt)
        artifact_identities.append(artifact_identity)
        sidecar_identities.append(sidecar_identity)
        receipt_identities.append(receipt_identity)
    bundle = _assemble_bundle(
        candidate_release=candidate_release,
        artifacts=artifacts,
        sidecars=sidecars,
        receipts=receipts,
        panel=panel,
    )
    try:
        validated_bundle = core.validate_fixed_g0_candidate_authority_v1(
            bundle,
            repository_root=repository_root,
            catalog_replay_receipt_identity=root[
                "catalog_replay_receipt_identity"
            ],
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV1Error(
            f"candidate-authority predecessor replay failed: {exc}"
        ) from exc
    expected_root = _build_root(
        prefix=prefix,
        run_id=run_id,
        bundle=validated_bundle,
        candidate_release_identity=candidate_release_identity,
        panel_identity=panel_identity,
        artifact_identities=artifact_identities,
        sidecar_identities=sidecar_identities,
        receipt_identities=receipt_identities,
    )
    if canonical_json_bytes(root) != canonical_json_bytes(expected_root):
        _fail("candidate-authority root predecessor replay differs")
    return ReopenedFixedG0CandidateAuthorityV1(
        root=root,
        root_identity=reopened_root_identity,
        authority_bundle=validated_bundle,
        candidate_release=candidate_release,
        candidate_release_identity=candidate_release_identity,
    )


__all__ = [
    "CANDIDATE_RELEASE_FILENAME",
    "CorpusR6FixedG0CandidateAuthorityReleaseV1Error",
    "LINEAGE_FILENAME",
    "OBJECT_DESCRIPTOR_SCHEMA",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "PANEL_RECEIPT_FILENAME",
    "PUBLICATION_MODE",
    "RELEASE_SCHEMA",
    "ROOT_FILENAME",
    "ReopenedFixedG0CandidateAuthorityV1",
    "SLATE_RECEIPT_FILENAME",
    "canonical_json_bytes",
    "canonical_sha256",
    "output_prefix_for_run_v1",
    "publish_fixed_g0_candidate_authority_release_v1",
    "reopen_fixed_g0_candidate_authority_release_v1",
    "validate_fixed_g0_candidate_authority_release_structure_v1",
]
