"""Root-last publication for the outer-bound fixed-G0 candidate authority.

The fixed output contract is 165 create-once objects: 54 complete accepted-
candidate artifacts, 54 exact occurrence-lineage sidecars, 54 outer-bound
slate receipts, one accepted-candidate release, one outer-bound panel receipt,
and one v2 terminal root published last.  A legacy root is never published or
accepted by the authoritative reopener.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as core_v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as core
from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as recovery
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


RELEASE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-release/v2"
)
OBJECT_DESCRIPTOR_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-object-descriptor/v2"
)
PUBLICATION_MANIFEST_ROW_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-publication-object/v2"
)
PUBLICATION_MODE: Final = "create_once_root_last"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = (
    "research/corpus-r6-fixed-g0-candidate-authorities-v2"
)
ROOT_FILENAME: Final = "candidate-authority-release-v2.json"
CANDIDATE_RELEASE_FILENAME: Final = "accepted-candidate-release.json"
PANEL_RECEIPT_FILENAME: Final = "panel-derivation-receipt.json"
LINEAGE_FILENAME: Final = "exact-occurrence-lineage.json"
SLATE_RECEIPT_FILENAME: Final = "slate-derivation-receipt.json"

ARTIFACT_COUNT: Final = source.TASK_COUNT
SIDECAR_COUNT: Final = source.TASK_COUNT
SLATE_RECEIPT_COUNT: Final = source.TASK_COUNT
NON_ROOT_OBJECT_COUNT: Final = (
    ARTIFACT_COUNT + SIDECAR_COUNT + SLATE_RECEIPT_COUNT + 2
)
TOTAL_OBJECT_COUNT: Final = NON_ROOT_OBJECT_COUNT + 1
EXPECTED_ARM_RESULT_COUNT: Final = source.TASK_COUNT * core_v1.EXPECTED_ARM_COUNT

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PREFIX = re.compile(
    rf"^gs://{re.escape(OUTPUT_BUCKET)}/{re.escape(OUTPUT_NAMESPACE)}/"
    r"(?P<run_id>[a-z0-9][a-z0-9-]{7,80})/$"
)
_FALSE_AUTHORITY_FIELDS: Final = tuple(source.FALSE_AUTHORITY_FIELDS)

ReadExact = core.ReadExact
PublishCreateOnce = Callable[[str, bytes], object]
GitHead = core.GitHead
GitBlob = core.GitBlob
GitStatus = core.GitStatus

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
    "catalog_recovery_outer_identity",
    "catalog_recovery_outer_attestation_sha256",
    "object_descriptor_sha256",
})
_PUBLICATION_ROW_FIELDS: Final = frozenset({
    "schema_version", "publication_ordinal", "role", "source_task_ordinal",
    "identity",
})
_ROOT_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "target_uri",
    "run_id",
    "namespace",
    "catalog_recovery_outer_identity",
    "catalog_recovery_outer_attestation_sha256",
    "catalog_recovery_candidate_binding",
    "read_class_attestation",
    "catalog_inner_object_count",
    "catalog_inner_object_manifest_sha256",
    "catalog_replay_receipt_identity",
    "catalog_replay_receipt_sha256",
    "catalog_release_identity",
    "catalog_release_sha256",
    "fixed_g0_panel_identity",
    "fixed_g0_panel_index_sha256",
    "g0_source_commit_sha",
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
    "non_root_publication_manifest",
    "non_root_publication_manifest_sha256",
    "published_role_counts",
    "published_non_root_object_count",
    "published_total_object_count",
    "published_legacy_root_count",
    "legacy_root_published",
    "candidate_population_authority",
    "exact_occurrence_provenance_authority",
    "authoritative_reopen_required",
    "structure_only_validation_authority",
    "complete",
    "complete_cross_arm_candidate_population_preserved",
    "all_candidate_generations_resolved_before_root_build",
    "every_output_exact_reopened",
    "every_predecessor_replayed",
    "catalog_recovery_outer_read_before_any_inner_read",
    "root_create_once_requested_last",
    "world_matrix_bodies_read",
    "realized_outcome_bodies_read",
    "historical_grader_outcome_sources_read",
    "warehouse_outcome_sources_read",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "candidate_authority_release_sha256",
})


class CorpusR6FixedG0CandidateAuthorityReleaseV2Error(ValueError):
    """The v2 candidate publication or deep exact reopen failed closed."""


@dataclass(frozen=True, slots=True)
class ReopenedFixedG0CandidateAuthorityV2:
    """Deep-replayed v2 terminal authority."""

    root: dict[str, object]
    root_identity: dict[str, object]
    authority_bundle: dict[str, object]
    candidate_release: dict[str, object]
    candidate_release_identity: dict[str, object]


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return {str(key): _thaw(item) for key, item in value.items()}


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return [_thaw(item) for item in value]


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            _fail("publication object keys differ")
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_thaw(item) for item in value]
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        value = as_dict()
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(str(exc)) from exc


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
    body = _mapping(value, label="hashed body")
    body[field] = canonical_sha256(body)
    return body


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} SHA")
    if retained != canonical_sha256({
        key: item for key, item in value.items() if key != field
    }):
        _fail(f"{label} self-hash differs")
    return retained


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def output_prefix_for_run_v2(run_id: object) -> str:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("candidate-authority v2 run ID differs")
    return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{run_id}/"


def _prefix_from_root_identity(
    identity: Mapping[str, object],
) -> tuple[str, str]:
    uri = str(identity["uri"])
    if not uri.endswith(ROOT_FILENAME):
        _fail("candidate-authority v2 root URI differs; legacy root rejected")
    prefix = uri.removesuffix(ROOT_FILENAME)
    match = _PREFIX.fullmatch(prefix)
    if match is None:
        _fail("candidate-authority v2 root escapes its fixed namespace")
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
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(
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
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(
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
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, label=f"{label} published identity")
    if identity["uri"] != target_uri:
        _fail(f"{label} published URI differs")
    reopened, reopened_identity = _exact_json(
        identity, read_exact=read_exact, label=label
    )
    if reopened_identity != identity or canonical_json_bytes(reopened) != raw:
        _fail(f"{label} exact reopen differs from intended bytes")
    return reopened, identity


def _bundle_lists(
    bundle: Mapping[str, object],
) -> tuple[
    dict[str, object], list[dict[str, object]], list[dict[str, object]],
    list[dict[str, object]], dict[str, object],
]:
    if bundle.get("schema_version") != core.AUTHORITY_BUNDLE_SCHEMA:
        _fail("candidate-authority v2 predecessor bundle schema differs")
    _self_hash(
        bundle,
        field="candidate_authority_bundle_sha256",
        label="candidate-authority v2 predecessor bundle",
    )
    candidate_release = source.validate_accepted_candidate_release_v1(
        bundle.get("candidate_release")
    )
    artifacts = [
        source.validate_accepted_candidate_artifact_v1(value)
        for value in _sequence(bundle.get("candidate_artifacts"), label="artifacts")
    ]
    sidecars = [
        _mapping(value, label=f"lineage sidecar[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            bundle.get("lineage_sidecars"), label="lineage sidecars"
        ))
    ]
    receipts = [
        _mapping(value, label=f"slate receipt[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            bundle.get("slate_derivation_receipts"), label="slate receipts"
        ))
    ]
    panel = _mapping(bundle.get("panel_derivation_receipt"), label="panel receipt")
    if not (
        bundle.get("task_count") == source.TASK_COUNT
        and len(artifacts) == len(sidecars) == len(receipts) == source.TASK_COUNT
        and panel.get("schema_version") == core.PANEL_DERIVATION_SCHEMA
        and bundle.get("candidate_artifact_manifest_sha256")
        == canonical_sha256(artifacts)
        and bundle.get("lineage_sidecar_manifest_sha256")
        == canonical_sha256(sidecars)
        and bundle.get("slate_derivation_manifest_sha256")
        == canonical_sha256(receipts)
        and bundle.get("complete_cross_arm_candidate_population_preserved") is True
        and bundle.get("exact_occurrence_provenance_preserved") is True
    ):
        _fail("candidate-authority v2 bundle census/manifest differs")
    _self_hash(panel, field="panel_derivation_sha256", label="panel receipt")
    binding = _mapping(
        bundle.get("catalog_recovery_candidate_binding"),
        label="candidate recovery binding",
    )
    for value, label in [
        (panel, "panel"),
        *[(receipt, f"receipt[{ordinal}]")
          for ordinal, receipt in enumerate(receipts)],
    ]:
        if (
            value.get("catalog_recovery_candidate_binding") != binding
            or value.get("catalog_recovery_outer_identity")
            != bundle.get("catalog_recovery_outer_identity")
            or value.get("catalog_recovery_outer_attestation_sha256")
            != bundle.get("catalog_recovery_outer_attestation_sha256")
        ):
            _fail(f"{label} recovery binding differs")
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
    base = f"{prefix}source-task-{source_task_ordinal:02d}-{slate['slate_id']}/"
    artifact_id = _identity(artifact_identity, label="candidate artifact identity")
    sidecar_id = _identity(sidecar_identity, label="lineage sidecar identity")
    receipt_id = _identity(receipt_identity, label="slate receipt identity")
    if (
        artifact_id["uri"] != f"{base}accepted-candidates.json"
        or sidecar_id["uri"] != f"{base}{LINEAGE_FILENAME}"
        or receipt_id["uri"] != f"{base}{SLATE_RECEIPT_FILENAME}"
        or artifact.get("source_task_ordinal") != source_task_ordinal
        or artifact.get("task_id") != task_id
        or artifact.get("slate") != slate
        or sidecar.get("schema_version") != core_v1.LINEAGE_SIDECAR_SCHEMA
        or sidecar.get("source_task_ordinal") != source_task_ordinal
        or sidecar.get("task_id") != task_id
        or sidecar.get("slate") != slate
        or receipt.get("schema_version") != core.SLATE_DERIVATION_SCHEMA
        or receipt.get("source_task_ordinal") != source_task_ordinal
        or receipt.get("task_id") != task_id
        or receipt.get("slate") != slate
        or receipt.get("candidate_artifact_identity") != artifact_id
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
        label=f"lineage sidecar[{source_task_ordinal}]",
    )
    _self_hash(
        receipt,
        field="slate_derivation_sha256",
        label=f"slate receipt[{source_task_ordinal}]",
    )
    body = {
        "schema_version": OBJECT_DESCRIPTOR_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "task_id": task_id,
        "slate": slate,
        "candidate_artifact_identity": artifact_id,
        "candidate_artifact_sha256": _digest(
            artifact.get("candidate_artifact_sha256"), label="candidate artifact SHA"
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
        "lineage_sidecar_identity": sidecar_id,
        "lineage_sidecar_sha256": _digest(
            sidecar.get("candidate_lineage_sidecar_sha256"),
            label="lineage sidecar SHA",
        ),
        "candidate_lineage_manifest_sha256": _digest(
            sidecar.get("candidate_lineage_manifest_sha256"),
            label="lineage manifest SHA",
        ),
        "visit_occurrence_count": _integer(
            sidecar.get("visit_occurrence_count"),
            label="visit occurrence count",
            minimum=int(artifact["candidate_count"]),
        ),
        "slate_derivation_identity": receipt_id,
        "slate_derivation_sha256": _digest(
            receipt.get("slate_derivation_sha256"), label="slate receipt SHA"
        ),
        "catalog_recovery_outer_identity": receipt[
            "catalog_recovery_outer_identity"
        ],
        "catalog_recovery_outer_attestation_sha256": receipt[
            "catalog_recovery_outer_attestation_sha256"
        ],
    }
    return _with_hash(body, field="object_descriptor_sha256")


def _publication_manifest(
    *,
    artifact_identities: Sequence[Mapping[str, object]],
    sidecar_identities: Sequence[Mapping[str, object]],
    receipt_identities: Sequence[Mapping[str, object]],
    candidate_release_identity: Mapping[str, object],
    panel_identity: Mapping[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def append(role: str, source_task_ordinal: int | None, identity: object) -> None:
        rows.append({
            "schema_version": PUBLICATION_MANIFEST_ROW_SCHEMA,
            "publication_ordinal": len(rows),
            "role": role,
            "source_task_ordinal": source_task_ordinal,
            "identity": _identity(identity, label=f"{role} publication identity"),
        })

    for ordinal, identity in enumerate(artifact_identities):
        append("candidate_artifact", ordinal, identity)
    for ordinal, identity in enumerate(sidecar_identities):
        append("exact_occurrence_lineage_sidecar", ordinal, identity)
    for ordinal, identity in enumerate(receipt_identities):
        append("outer_bound_slate_derivation_receipt", ordinal, identity)
    append("accepted_candidate_release", None, candidate_release_identity)
    append("outer_bound_panel_derivation_receipt", None, panel_identity)
    if len(rows) != NON_ROOT_OBJECT_COUNT:
        _fail("candidate publication manifest count differs")
    return rows


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
        len(artifact_identities) == len(sidecar_identities)
        == len(receipt_identities) == source.TASK_COUNT
    ):
        _fail("candidate-authority output identity census differs")
    release_identity = _identity(
        candidate_release_identity, label="candidate release identity"
    )
    panel_id = _identity(panel_identity, label="panel identity")
    if (
        release_identity["uri"] != f"{prefix}{CANDIDATE_RELEASE_FILENAME}"
        or panel_id["uri"] != f"{prefix}{PANEL_RECEIPT_FILENAME}"
        or candidate_release.get("namespace") != prefix
        or candidate_release.get("release_id") != run_id
        or panel.get("candidate_release_id") != run_id
        or panel.get("candidate_namespace") != prefix
        or panel.get("candidate_release_sha256")
        != candidate_release.get("accepted_candidate_release_sha256")
        or panel.get("candidate_release_body_sha256")
        != canonical_sha256(candidate_release)
    ):
        _fail("candidate release/panel binding differs")
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
        _mapping(value, label=f"panel slate[{ordinal}]")
        for ordinal, value in enumerate(_sequence(panel.get("slates"), label="slates"))
    ]
    if len(release_entries) != source.TASK_COUNT or len(panel_rows) != source.TASK_COUNT:
        _fail("candidate release/panel lattice census differs")
    for ordinal, descriptor in enumerate(descriptors):
        release_entry = release_entries[ordinal]
        panel_row = panel_rows[ordinal]
        if (
            release_entry.get("source_task_ordinal") != ordinal
            or release_entry.get("candidate_artifact_identity")
            != descriptor["candidate_artifact_identity"]
            or release_entry.get("candidate_count") != descriptor["candidate_count"]
            or release_entry.get("ordered_candidate_ids_sha256")
            != descriptor["ordered_candidate_ids_sha256"]
            or panel_row.get("source_task_ordinal") != ordinal
            or panel_row.get("candidate_artifact_identity")
            != descriptor["candidate_artifact_identity"]
            or panel_row.get("candidate_count") != descriptor["candidate_count"]
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
        _fail("candidate panel aggregate binding differs")
    publication_manifest = _publication_manifest(
        artifact_identities=artifact_identities,
        sidecar_identities=sidecar_identities,
        receipt_identities=receipt_identities,
        candidate_release_identity=release_identity,
        panel_identity=panel_id,
    )
    binding = _mapping(
        bundle.get("catalog_recovery_candidate_binding"),
        label="candidate recovery binding",
    )
    body: dict[str, object] = {
        "schema_version": RELEASE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": f"{prefix}{ROOT_FILENAME}",
        "run_id": run_id,
        "namespace": prefix,
        "catalog_recovery_outer_identity": bundle[
            "catalog_recovery_outer_identity"
        ],
        "catalog_recovery_outer_attestation_sha256": bundle[
            "catalog_recovery_outer_attestation_sha256"
        ],
        "catalog_recovery_candidate_binding": binding,
        "read_class_attestation": bundle["read_class_attestation"],
        "catalog_inner_object_count": binding["catalog_inner_object_count"],
        "catalog_inner_object_manifest_sha256": binding[
            "catalog_inner_object_manifest_sha256"
        ],
        "catalog_replay_receipt_identity": panel[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": panel[
            "catalog_replay_receipt_sha256"
        ],
        "catalog_release_identity": panel["catalog_release_identity"],
        "catalog_release_sha256": panel["catalog_release_sha256"],
        "fixed_g0_panel_identity": panel["fixed_g0_panel_identity"],
        "fixed_g0_panel_index_sha256": panel["fixed_g0_panel_index_sha256"],
        "g0_source_commit_sha": panel["g0_source_commit_sha"],
        "candidate_release_identity": release_identity,
        "candidate_release_sha256": candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "panel_derivation_identity": panel_id,
        "panel_derivation_sha256": panel["panel_derivation_sha256"],
        "task_count": source.TASK_COUNT,
        "arm_result_count": EXPECTED_ARM_RESULT_COUNT,
        "total_candidate_count": total_candidates,
        "total_visit_occurrence_count": total_visits,
        "objects": descriptors,
        "object_manifest_sha256": canonical_sha256(descriptors),
        "non_root_publication_manifest": publication_manifest,
        "non_root_publication_manifest_sha256": canonical_sha256(
            publication_manifest
        ),
        "published_role_counts": {
            "candidate_artifact": ARTIFACT_COUNT,
            "exact_occurrence_lineage_sidecar": SIDECAR_COUNT,
            "outer_bound_slate_derivation_receipt": SLATE_RECEIPT_COUNT,
            "accepted_candidate_release": 1,
            "outer_bound_panel_derivation_receipt": 1,
            "v2_terminal_root": 1,
        },
        "published_non_root_object_count": NON_ROOT_OBJECT_COUNT,
        "published_total_object_count": TOTAL_OBJECT_COUNT,
        "published_legacy_root_count": 0,
        "legacy_root_published": False,
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
        "complete_cross_arm_candidate_population_preserved": True,
        "all_candidate_generations_resolved_before_root_build": True,
        "every_output_exact_reopened": True,
        "every_predecessor_replayed": True,
        "catalog_recovery_outer_read_before_any_inner_read": True,
        "root_create_once_requested_last": True,
        "world_matrix_bodies_read": False,
        "realized_outcome_bodies_read": False,
        "historical_grader_outcome_sources_read": False,
        "warehouse_outcome_sources_read": False,
        **_policy(),
    }
    return _with_hash(body, field="candidate_authority_release_sha256")


def validate_fixed_g0_candidate_authority_release_structure_v2(
    value: object,
) -> dict[str, object]:
    """Validate v2 terminal layout only; this grants no authority."""

    root = _mapping(value, label="candidate-authority v2 root")
    _exact_keys(root, _ROOT_FIELDS, label="candidate-authority v2 root")
    _self_hash(
        root,
        field="candidate_authority_release_sha256",
        label="candidate-authority v2 root",
    )
    if root.get("schema_version") != RELEASE_SCHEMA:
        _fail("candidate-authority legacy root schema rejected")
    target_uri = root.get("target_uri")
    if type(target_uri) is not str:
        _fail("candidate-authority v2 target URI differs")
    prefix, run_id = _prefix_from_root_identity({
        "uri": target_uri,
        "generation": "1",
        "sha256": "0" * 64,
        "bytes": 1,
    })
    outer_identity = _identity(
        root.get("catalog_recovery_outer_identity"),
        label="catalog recovery outer identity",
    )
    binding = _mapping(
        root.get("catalog_recovery_candidate_binding"),
        label="candidate recovery binding",
    )
    recovery_binding = _mapping(
        binding.get("catalog_recovery_code_and_lock_binding"),
        label="catalog recovery code/lock binding",
    )
    core._validate_hash(
        binding,
        field="candidate_implementation_binding_sha256",
        label="candidate recovery binding",
    )
    release_identity = _identity(
        root.get("candidate_release_identity"), label="candidate release identity"
    )
    panel_identity = _identity(
        root.get("panel_derivation_identity"), label="panel identity"
    )
    catalog_receipt_identity = _identity(
        root.get("catalog_replay_receipt_identity"),
        label="derived catalog replay receipt identity",
    )
    catalog_release_identity = _identity(
        root.get("catalog_release_identity"),
        label="derived catalog release identity",
    )
    if (
        root.get("publication_mode") != PUBLICATION_MODE
        or root.get("run_id") != run_id
        or root.get("namespace") != prefix
        or root.get("target_uri") != f"{prefix}{ROOT_FILENAME}"
        or outer_identity["uri"] != recovery.OUTER_ATTESTATION_URI
        or release_identity["uri"] != f"{prefix}{CANDIDATE_RELEASE_FILENAME}"
        or panel_identity["uri"] != f"{prefix}{PANEL_RECEIPT_FILENAME}"
        or binding.get("catalog_recovery_outer_identity") != outer_identity
        or recovery_binding.get("outer_attestation_identity") != outer_identity
        or binding.get("catalog_inner_replay_receipt_identity")
        != catalog_receipt_identity
        or binding.get("catalog_inner_replay_receipt_sha256")
        != root.get("catalog_replay_receipt_sha256")
        or binding.get("catalog_inner_release_identity")
        != catalog_release_identity
        or binding.get("catalog_inner_release_sha256")
        != root.get("catalog_release_sha256")
        or root.get("catalog_recovery_outer_attestation_sha256")
        != binding.get("catalog_recovery_outer_attestation_sha256")
        or root.get("read_class_attestation") != binding.get("read_class_attestation")
        or root.get("catalog_inner_object_count") != 110
        or root.get("catalog_inner_object_count")
        != binding.get("catalog_inner_object_count")
        or root.get("catalog_inner_object_manifest_sha256")
        != binding.get("catalog_inner_object_manifest_sha256")
        or root.get("task_count") != source.TASK_COUNT
        or root.get("arm_result_count") != EXPECTED_ARM_RESULT_COUNT
        or root.get("published_non_root_object_count") != NON_ROOT_OBJECT_COUNT
        or root.get("published_total_object_count") != TOTAL_OBJECT_COUNT
        or root.get("published_legacy_root_count") != 0
        or root.get("legacy_root_published") is not False
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("authoritative_reopen_required") is not True
        or root.get("structure_only_validation_authority") is not False
        or root.get("complete") is not True
        or root.get("complete_cross_arm_candidate_population_preserved") is not True
        or root.get("all_candidate_generations_resolved_before_root_build") is not True
        or root.get("every_output_exact_reopened") is not True
        or root.get("every_predecessor_replayed") is not True
        or root.get("catalog_recovery_outer_read_before_any_inner_read") is not True
        or root.get("root_create_once_requested_last") is not True
        or root.get("world_matrix_bodies_read") is not False
        or root.get("realized_outcome_bodies_read") is not False
        or root.get("historical_grader_outcome_sources_read") is not False
        or root.get("warehouse_outcome_sources_read") is not False
        or root.get("outcome_columns_read") != []
        or root.get("uses_realized_outcomes") is not False
        or any(root.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("candidate-authority v2 policy, outer binding, or namespace differs")
    if root.get("published_role_counts") != {
        "candidate_artifact": 54,
        "exact_occurrence_lineage_sidecar": 54,
        "outer_bound_slate_derivation_receipt": 54,
        "accepted_candidate_release": 1,
        "outer_bound_panel_derivation_receipt": 1,
        "v2_terminal_root": 1,
    }:
        _fail("candidate-authority v2 publication role census differs")
    for field in (
        "catalog_recovery_outer_attestation_sha256",
        "catalog_inner_object_manifest_sha256",
        "catalog_replay_receipt_sha256",
        "catalog_release_sha256",
        "fixed_g0_panel_index_sha256",
        "candidate_release_sha256",
        "panel_derivation_sha256",
        "object_manifest_sha256",
        "non_root_publication_manifest_sha256",
    ):
        _digest(root.get(field), label=field)
    core._commit(root.get("g0_source_commit_sha"), label="fixed G0 source commit")

    descriptors = [
        _mapping(value, label=f"object descriptor[{ordinal}]")
        for ordinal, value in enumerate(_sequence(root.get("objects"), label="objects"))
    ]
    if (
        len(descriptors) != source.TASK_COUNT
        or root.get("object_manifest_sha256") != canonical_sha256(descriptors)
    ):
        _fail("candidate-authority v2 descriptor census/hash differs")
    for ordinal, descriptor in enumerate(descriptors):
        _exact_keys(descriptor, _DESCRIPTOR_FIELDS, label="object descriptor")
        _self_hash(
            descriptor,
            field="object_descriptor_sha256",
            label=f"object descriptor[{ordinal}]",
        )
        if (
            descriptor.get("source_task_ordinal") != ordinal
            or descriptor.get("catalog_recovery_outer_identity") != outer_identity
            or descriptor.get("catalog_recovery_outer_attestation_sha256")
            != root.get("catalog_recovery_outer_attestation_sha256")
        ):
            _fail(f"object descriptor[{ordinal}] outer binding differs")
    publication_rows = [
        _mapping(value, label=f"publication row[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            root.get("non_root_publication_manifest"), label="publication manifest"
        ))
    ]
    expected_roles = (
        ["candidate_artifact"] * 54
        + ["exact_occurrence_lineage_sidecar"] * 54
        + ["outer_bound_slate_derivation_receipt"] * 54
        + ["accepted_candidate_release", "outer_bound_panel_derivation_receipt"]
    )
    if (
        len(publication_rows) != NON_ROOT_OBJECT_COUNT
        or root.get("non_root_publication_manifest_sha256")
        != canonical_sha256(publication_rows)
    ):
        _fail("candidate-authority v2 publication manifest differs")
    seen: set[tuple[str, str, str, int]] = set()
    for ordinal, row in enumerate(publication_rows):
        _exact_keys(row, _PUBLICATION_ROW_FIELDS, label="publication row")
        identity = _identity(row.get("identity"), label="publication identity")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        expected_source = ordinal % 54 if ordinal < 162 else None
        if (
            row.get("schema_version") != PUBLICATION_MANIFEST_ROW_SCHEMA
            or row.get("publication_ordinal") != ordinal
            or row.get("role") != expected_roles[ordinal]
            or row.get("source_task_ordinal") != expected_source
            or key in seen
            or not str(identity["uri"]).startswith(prefix)
        ):
            _fail(f"publication row[{ordinal}] differs")
        seen.add(key)
    if (
        root.get("total_candidate_count")
        != sum(int(row["candidate_count"]) for row in descriptors)
        or root.get("total_visit_occurrence_count")
        != sum(int(row["visit_occurrence_count"]) for row in descriptors)
    ):
        _fail("candidate-authority v2 aggregate census differs")
    return root


def _assemble_bundle(
    *,
    candidate_release: Mapping[str, object],
    artifacts: Sequence[Mapping[str, object]],
    sidecars: Sequence[Mapping[str, object]],
    receipts: Sequence[Mapping[str, object]],
    panel: Mapping[str, object],
) -> dict[str, object]:
    retained_panel = _mapping(panel, label="panel receipt")
    binding_fields = {
        "catalog_recovery_outer_identity": retained_panel[
            "catalog_recovery_outer_identity"
        ],
        "catalog_recovery_outer_attestation_sha256": retained_panel[
            "catalog_recovery_outer_attestation_sha256"
        ],
        "catalog_recovery_candidate_binding": retained_panel[
            "catalog_recovery_candidate_binding"
        ],
        "read_class_attestation": retained_panel["read_class_attestation"],
    }
    body: dict[str, object] = {
        "schema_version": core.AUTHORITY_BUNDLE_SCHEMA,
        "candidate_release": _mapping(candidate_release, label="candidate release"),
        "candidate_artifacts": [_mapping(value, label="artifact") for value in artifacts],
        "candidate_artifact_manifest_sha256": canonical_sha256(artifacts),
        "lineage_sidecars": [_mapping(value, label="sidecar") for value in sidecars],
        "lineage_sidecar_manifest_sha256": canonical_sha256(sidecars),
        "slate_derivation_receipts": [
            _mapping(value, label="slate receipt") for value in receipts
        ],
        "slate_derivation_manifest_sha256": canonical_sha256(receipts),
        "panel_derivation_receipt": retained_panel,
        "task_count": source.TASK_COUNT,
        **_policy(),
        **binding_fields,
        "complete_cross_arm_candidate_population_preserved": True,
        "exact_occurrence_provenance_preserved": True,
    }
    return _with_hash(body, field="candidate_authority_bundle_sha256")


def publish_fixed_g0_candidate_authority_release_v2(
    *,
    run_id: object,
    repository_root: Path,
    catalog_recovery_outer_identity: Mapping[str, object],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[dict[str, object], dict[str, object]]:
    """Publish exactly 165 objects, with only the v2 terminal root last."""

    prefix = output_prefix_for_run_v2(run_id)
    retained_run_id = str(run_id)
    if not callable(read_exact) or not callable(publish_create_once):
        _fail("candidate-authority read/publish boundary differs")
    output_reader = _scoped_reader(read_exact=read_exact, prefix=prefix)
    try:
        material = core.derive_fixed_g0_candidate_material_v2(
            repository_root=repository_root,
            catalog_recovery_outer_identity=catalog_recovery_outer_identity,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(
            f"fixed-G0 v2 candidate derivation failed: {exc}"
        ) from exc
    artifacts = [
        source.validate_accepted_candidate_artifact_v1(value)
        for value in _sequence(material.get("candidate_artifacts"), label="artifacts")
    ]
    if (
        material.get("schema_version") != core.MATERIAL_SCHEMA
        or len(artifacts) != source.TASK_COUNT
        or material.get("candidate_artifact_manifest_sha256")
        != canonical_sha256(artifacts)
    ):
        _fail("derived v2 candidate material differs")
    artifact_identities: list[dict[str, object]] = []
    for ordinal, artifact in enumerate(artifacts):
        target_uri = (
            f"{prefix}source-task-{ordinal:02d}-{artifact['slate']['slate_id']}/"
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
    del material
    del artifacts
    try:
        bundle = core.build_fixed_g0_candidate_authority_v2(
            release_id=retained_run_id,
            namespace=prefix,
            repository_root=repository_root,
            catalog_recovery_outer_identity=catalog_recovery_outer_identity,
            candidate_artifact_identities=artifact_identities,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(
            f"fixed-G0 v2 candidate authority build failed: {exc}"
        ) from exc
    candidate_release, artifacts, sidecars, receipts, panel = _bundle_lists(bundle)
    sidecar_identities: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    for ordinal, sidecar in enumerate(sidecars):
        base = f"{prefix}source-task-{ordinal:02d}-{sidecar['slate']['slate_id']}/"
        _, identity = _publish_json(
            sidecar,
            target_uri=f"{base}{LINEAGE_FILENAME}",
            publish_create_once=publish_create_once,
            read_exact=output_reader,
            label=f"lineage sidecar[{ordinal}]",
        )
        sidecar_identities.append(identity)
    for ordinal, receipt in enumerate(receipts):
        base = f"{prefix}source-task-{ordinal:02d}-{receipt['slate']['slate_id']}/"
        _, identity = _publish_json(
            receipt,
            target_uri=f"{base}{SLATE_RECEIPT_FILENAME}",
            publish_create_once=publish_create_once,
            read_exact=output_reader,
            label=f"outer-bound slate receipt[{ordinal}]",
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
        label="outer-bound panel receipt",
    )
    if len(artifact_identities) + len(sidecar_identities) + len(receipt_identities) + 2 != NON_ROOT_OBJECT_COUNT:
        _fail("candidate-authority non-root publication census differs")
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
    validate_fixed_g0_candidate_authority_release_structure_v2(root)
    reopened_root, root_identity = _publish_json(
        root,
        target_uri=f"{prefix}{ROOT_FILENAME}",
        publish_create_once=publish_create_once,
        read_exact=output_reader,
        label="candidate-authority v2 terminal root",
    )
    retained = validate_fixed_g0_candidate_authority_release_structure_v2(
        reopened_root
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(root):
        _fail("candidate-authority v2 root exact reopen differs")
    return retained, root_identity


def reopen_fixed_g0_candidate_authority_release_v2(
    root_identity: object,
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> ReopenedFixedG0CandidateAuthorityV2:
    """Read root, open recovery outer, then deep-reconstruct the exact root."""

    retained_root_identity = _identity(
        root_identity, label="candidate-authority v2 root identity"
    )
    # Namespace/filename rejection occurs before the first storage read.  A v1
    # root can therefore never be treated as this authoritative root.
    prefix, run_id = _prefix_from_root_identity(retained_root_identity)
    output_reader = _scoped_reader(read_exact=read_exact, prefix=prefix)
    root_body, reopened_root_identity = _exact_json(
        retained_root_identity,
        read_exact=output_reader,
        label="candidate-authority v2 terminal root",
    )
    if root_body.get("schema_version") != RELEASE_SCHEMA:
        _fail("candidate-authority legacy root schema rejected")
    root = validate_fixed_g0_candidate_authority_release_structure_v2(root_body)
    if root.get("target_uri") != reopened_root_identity["uri"]:
        _fail("candidate-authority v2 root outer identity differs")

    # This is deliberately before every non-root output read.  It reads the
    # recovery outer only and derives the inner receipt/release/110 identities.
    _, current_binding = core._open_outer_and_binding(
        repository_root=repository_root,
        catalog_recovery_outer_identity=root["catalog_recovery_outer_identity"],
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        candidate_implementation_commit_sha=root[
            "catalog_recovery_candidate_binding"
        ]["candidate_implementation_commit_sha"],
    )
    if current_binding != root["catalog_recovery_candidate_binding"]:
        _fail("candidate-authority v2 root recovery/code binding differs")

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
        label="outer-bound panel receipt",
    )
    artifacts: list[dict[str, object]] = []
    sidecars: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    artifact_identities: list[dict[str, object]] = []
    sidecar_identities: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    for ordinal, raw_descriptor in enumerate(_sequence(root["objects"], label="objects")):
        descriptor = _mapping(raw_descriptor, label=f"object descriptor[{ordinal}]")
        artifact_body, artifact_identity = _exact_json(
            descriptor["candidate_artifact_identity"],
            read_exact=output_reader,
            label=f"candidate artifact[{ordinal}]",
        )
        artifact = source.validate_accepted_candidate_artifact_v1(artifact_body)
        sidecar, sidecar_identity = _exact_json(
            descriptor["lineage_sidecar_identity"],
            read_exact=output_reader,
            label=f"lineage sidecar[{ordinal}]",
        )
        receipt, receipt_identity = _exact_json(
            descriptor["slate_derivation_identity"],
            read_exact=output_reader,
            label=f"outer-bound slate receipt[{ordinal}]",
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
        if canonical_json_bytes(descriptor) != canonical_json_bytes(expected_descriptor):
            _fail(f"object descriptor[{ordinal}] body binding differs")
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
        validated_bundle = core.validate_fixed_g0_candidate_authority_v2(
            bundle,
            repository_root=repository_root,
            catalog_recovery_outer_identity=root[
                "catalog_recovery_outer_identity"
            ],
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityReleaseV2Error(
            f"candidate-authority v2 predecessor replay failed: {exc}"
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
        _fail("candidate-authority v2 root predecessor replay differs")
    return ReopenedFixedG0CandidateAuthorityV2(
        root=root,
        root_identity=reopened_root_identity,
        authority_bundle=validated_bundle,
        candidate_release=candidate_release,
        candidate_release_identity=candidate_release_identity,
    )


__all__ = [
    "CANDIDATE_RELEASE_FILENAME",
    "CorpusR6FixedG0CandidateAuthorityReleaseV2Error",
    "LINEAGE_FILENAME",
    "NON_ROOT_OBJECT_COUNT",
    "OBJECT_DESCRIPTOR_SCHEMA",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "PANEL_RECEIPT_FILENAME",
    "PUBLICATION_MODE",
    "RELEASE_SCHEMA",
    "ROOT_FILENAME",
    "ReopenedFixedG0CandidateAuthorityV2",
    "SLATE_RECEIPT_FILENAME",
    "TOTAL_OBJECT_COUNT",
    "canonical_json_bytes",
    "canonical_sha256",
    "output_prefix_for_run_v2",
    "publish_fixed_g0_candidate_authority_release_v2",
    "reopen_fixed_g0_candidate_authority_release_v2",
    "validate_fixed_g0_candidate_authority_release_structure_v2",
]
