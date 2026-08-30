"""Outer-bound successor for the complete fixed-G0 R6 candidate authority.

The frozen v1 implementation remains the scientific derivation engine.  This
successor changes its trust boundary: the sole catalog input is the published
catalog-recovery *outer* generation.  The read-only recovery downstream
reopener must validate that generation before v1 is allowed to read any inner
catalog object, and every inner identity is checked against the 110-object
manifest returned by that reopener.

The successor adds no score, realized-outcome, historical grader, warehouse
outcome, or world-matrix read.  It truthfully retains the v1 replay of accepted
task/carrier/result objects and world schedules needed to reconstruct the
complete cross-arm candidate population and exact occurrence provenance.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from pathlib import Path
import re
import stat
from typing import Final

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as v1
from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_downstream_v1 as recovery_downstream
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


MATERIAL_SCHEMA: Final = "corpus-r6-fixed-g0-candidate-material/v2"
SLATE_DERIVATION_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-slate-derivation/v2"
)
PANEL_DERIVATION_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-panel-derivation/v2"
)
AUTHORITY_BUNDLE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-bundle/v2"
)
CANDIDATE_IMPLEMENTATION_BINDING_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-implementation-binding/v2"
)
READ_CLASS_ATTESTATION_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-read-class-attestation/v2"
)

CORE_V2_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v2.py"
)
FROZEN_CORE_V1_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v1.py"
)
RELEASE_V2_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_fixed_g0_candidate_authority_release_v2.py"
)
CANDIDATE_IMPLEMENTATION_PATHS: Final = tuple(sorted((
    recovery_downstream.DOWNSTREAM_MODULE_PATH,
    FROZEN_CORE_V1_MODULE_PATH,
    CORE_V2_MODULE_PATH,
    RELEASE_V2_MODULE_PATH,
)))

_BINDING_FIELD: Final = "catalog_recovery_candidate_binding"
_OUTER_IDENTITY_FIELD: Final = "catalog_recovery_outer_identity"
_OUTER_SHA_FIELD: Final = "catalog_recovery_outer_attestation_sha256"
_READ_CLASS_FIELD: Final = "read_class_attestation"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_COMMIT: Final = re.compile(r"^[0-9a-f]{40}$")

ReadExact = v1.ReadExact
GitHead = v1.GitHead
GitBlob = v1.GitBlob
GitStatus = v1.GitStatus


class CorpusR6FixedG0CandidateAuthorityV2Error(ValueError):
    """The outer-bound candidate authority failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CandidateAuthorityV2Error(message)


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
            _fail("authority object keys differ")
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_thaw(item) for item in value]
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV2Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase full Git commit")
    return value


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = _mapping(value, label="hashed body")
    body[field] = source.canonical_sha256(body)
    return body


def _validate_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} {field}")
    body = {key: item for key, item in value.items() if key != field}
    if source.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _read_class_attestation() -> dict[str, object]:
    """Describe wrapper-added and inherited reads without hiding v1 replay."""

    return {
        "schema_version": READ_CLASS_ATTESTATION_SCHEMA,
        "v2_wrapper_added_predecessor_read_classes": [
            "catalog_recovery_outer_attestation",
        ],
        "inherited_v1_derivation_read_classes": [
            "fixed_g0_panel_authority",
            "catalog_replay_receipt_body",
            "catalog_release_body",
            "catalog_derivation_receipt_bodies_54",
            "player_catalog_bodies_54",
            "task_acceptance_bodies_54",
            "carrier_bodies_54",
            "accepted_arm_result_object_bodies_378",
            "world_schedule_bodies_54",
        ],
        "inherited_v1_build_validation_additional_read_classes": [
            "published_candidate_artifact_bodies_54",
        ],
        "accepted_task_result_and_carrier_bodies_reopened": True,
        "world_schedule_bodies_read": True,
        "world_matrix_bodies_read": False,
        "realized_outcome_bodies_read": False,
        "historical_grader_outcome_sources_read": False,
        "warehouse_outcome_sources_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }


def _measure_candidate_implementation_v2(
    *,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    implementation_commit_sha: str | None = None,
) -> tuple[str, list[dict[str, object]]]:
    """Bind clean tracked bytes for the outer adapter and both v2 modules."""

    repository = Path(repository_root)
    if not callable(git_head) or not callable(git_blob) or not callable(git_status):
        _fail("candidate implementation Git callbacks differ")
    try:
        current_head = _commit(
            git_head(repository), label="candidate implementation current HEAD"
        )
        implementation_commit = (
            current_head
            if implementation_commit_sha is None
            else _commit(
                implementation_commit_sha,
                label="candidate implementation bound commit",
            )
        )
        status_bytes = git_status(repository, CANDIDATE_IMPLEMENTATION_PATHS)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV2Error(
            "candidate implementation Git resolution failed"
        ) from exc
    if type(status_bytes) is not bytes or status_bytes != b"":
        _fail("candidate implementation files must be tracked-clean")

    measurements: list[dict[str, object]] = []
    for relative_path in CANDIDATE_IMPLEMENTATION_PATHS:
        path = repository / relative_path
        try:
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                _fail(f"candidate implementation path differs: {relative_path}")
            worktree_raw = path.read_bytes()
            tracked_raw = git_blob(repository, implementation_commit, relative_path)
        except CorpusR6FixedG0CandidateAuthorityV2Error:
            raise
        except Exception as exc:
            raise CorpusR6FixedG0CandidateAuthorityV2Error(
                f"candidate implementation read failed: {relative_path}"
            ) from exc
        if type(tracked_raw) is not bytes or tracked_raw != worktree_raw:
            _fail(f"candidate implementation code drift: {relative_path}")
        measurements.append({
            "relative_path": relative_path,
            "sha256": sha256(worktree_raw).hexdigest(),
            "bytes": len(worktree_raw),
        })
    return implementation_commit, measurements


def _open_outer_and_binding(
    *,
    repository_root: Path,
    catalog_recovery_outer_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    candidate_implementation_commit_sha: str | None = None,
) -> tuple[
    recovery_downstream.ReopenedFixedG0CatalogRecoveryAuthorityV1,
    dict[str, object],
]:
    """Open the outer first, then measure the exact consumer implementation."""

    try:
        authority = recovery_downstream.reopen_fixed_g0_catalog_recovery_authority_v1(
            repository_root=Path(repository_root),
            outer_identity=catalog_recovery_outer_identity,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV2Error(
            f"catalog recovery outer authoritative reopen failed: {exc}"
        ) from exc
    outer_identity = _identity(
        authority.outer_identity, label="catalog recovery outer identity"
    )
    if outer_identity != _identity(
        catalog_recovery_outer_identity,
        label="requested catalog recovery outer identity",
    ):
        _fail("catalog recovery outer identity differs after reopen")
    if (
        tuple(authority.read_order) != ("catalog_recovery_outer",)
        or authority.inner_object_bodies_read is not False
        or authority.write_capability_exposed is not False
    ):
        _fail("catalog recovery downstream read boundary differs")

    implementation_commit, measurements = _measure_candidate_implementation_v2(
        repository_root=Path(repository_root),
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        implementation_commit_sha=candidate_implementation_commit_sha,
    )
    manifest = [_mapping(row, label="outer inner-object manifest row")
                for row in authority.inner_object_manifest]
    recovery_binding = _mapping(
        authority.recovery_code_and_lock_binding,
        label="catalog recovery code/lock binding",
    )
    outer_attestation = _mapping(
        authority.outer_attestation, label="catalog recovery outer attestation"
    )
    read_classes = _read_class_attestation()
    binding = _with_hash({
        "schema_version": CANDIDATE_IMPLEMENTATION_BINDING_SCHEMA,
        _OUTER_IDENTITY_FIELD: outer_identity,
        _OUTER_SHA_FIELD: _digest(
            authority.outer_attestation_sha256,
            label="catalog recovery outer attestation SHA",
        ),
        "catalog_recovery_code_and_lock_binding": recovery_binding,
        "catalog_inner_object_count": len(manifest),
        "catalog_inner_object_manifest_sha256": source.canonical_sha256(manifest),
        "catalog_inner_replay_receipt_identity": _identity(
            authority.inner_replay_receipt_identity,
            label="outer-derived replay receipt identity",
        ),
        "catalog_inner_replay_receipt_sha256": _digest(
            outer_attestation.get("inner_replay_receipt_sha256"),
            label="outer-derived replay receipt internal SHA",
        ),
        "catalog_inner_release_identity": _identity(
            authority.inner_catalog_release_identity,
            label="outer-derived catalog release identity",
        ),
        "catalog_inner_release_sha256": _digest(
            outer_attestation.get("inner_catalog_release_sha256"),
            label="outer-derived catalog release internal SHA",
        ),
        "candidate_implementation_commit_sha": implementation_commit,
        "candidate_implementation_measurements": measurements,
        "candidate_implementation_measurements_sha256": (
            source.canonical_sha256(measurements)
        ),
        "inner_authority_derived_only_from_validated_outer": True,
        "catalog_recovery_outer_read_before_any_inner_read": True,
        "legacy_catalog_root_accepted_as_authority": False,
        _READ_CLASS_FIELD: read_classes,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }, field="candidate_implementation_binding_sha256")
    return authority, binding


def _expected_manifest_from_material(
    material: Mapping[str, object],
) -> list[dict[str, object]]:
    predecessors = [
        _mapping(value, label=f"candidate predecessor[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            material.get("slate_predecessor_bindings"),
            label="candidate predecessor bindings",
        ))
    ]
    if len(predecessors) != source.TASK_COUNT:
        _fail("candidate material predecessor census differs")
    rows: list[dict[str, object]] = []
    for ordinal, predecessor in enumerate(predecessors):
        catalog_binding = _mapping(
            predecessor.get("catalog_binding"),
            label=f"candidate catalog binding[{ordinal}]",
        )
        rows.extend((
            {
                "object_ordinal": len(rows),
                "role": "catalog_derivation_receipt",
                "source_task_ordinal": ordinal,
                "identity": _identity(
                    catalog_binding.get("derivation_identity"),
                    label=f"catalog derivation identity[{ordinal}]",
                ),
            },
            {
                "object_ordinal": len(rows) + 1,
                "role": "player_catalog",
                "source_task_ordinal": ordinal,
                "identity": _identity(
                    catalog_binding.get("catalog_identity"),
                    label=f"player catalog identity[{ordinal}]",
                ),
            },
        ))
    rows.extend((
        {
            "object_ordinal": len(rows),
            "role": "catalog_release",
            "source_task_ordinal": None,
            "identity": _identity(
                material.get("catalog_release_identity"),
                label="catalog release identity",
            ),
        },
        {
            "object_ordinal": len(rows) + 1,
            "role": "inner_replay_receipt",
            "source_task_ordinal": None,
            "identity": _identity(
                material.get("catalog_replay_receipt_identity"),
                label="catalog replay receipt identity",
            ),
        },
    ))
    return rows


def _require_outer_manifest(
    *,
    authority: recovery_downstream.ReopenedFixedG0CatalogRecoveryAuthorityV1,
    material: Mapping[str, object],
) -> None:
    expected = _expected_manifest_from_material(material)
    retained = [
        _mapping(row, label=f"outer inner-object manifest[{ordinal}]")
        for ordinal, row in enumerate(authority.inner_object_manifest)
    ]
    if (
        len(retained) != 110
        or retained != expected
        or _identity(material.get("catalog_release_identity"), label="release")
        != _identity(authority.inner_catalog_release_identity, label="outer release")
        or _identity(
            material.get("catalog_replay_receipt_identity"), label="receipt"
        )
        != _identity(
            authority.inner_replay_receipt_identity, label="outer receipt"
        )
        or material.get("catalog_release_sha256")
        != authority.outer_attestation.get("inner_catalog_release_sha256")
        or material.get("catalog_replay_receipt_sha256")
        != authority.outer_attestation.get("inner_replay_receipt_sha256")
    ):
        _fail("candidate catalog identities differ from outer 110-object manifest")


def _outer_manifest_gated_reader(
    *,
    authority: recovery_downstream.ReopenedFixedG0CatalogRecoveryAuthorityV1,
    read_exact: ReadExact,
) -> tuple[ReadExact, Callable[[], None]]:
    """Reject any inner catalog read not selected by the validated outer.

    The frozen v1 engine obtains the release identity from the inner receipt.
    This guard makes that compatibility behavior safe: even a coherently
    substituted receipt cannot cause a backing read of an alternate release,
    catalog, or derivation object.  The exact expected v1 read order is receipt,
    release, then catalog/derivation for each of the 54 source ordinals.
    """

    if not callable(read_exact):
        _fail("candidate predecessor exact reader differs")
    manifest = [
        _mapping(row, label=f"outer manifest row[{ordinal}]")
        for ordinal, row in enumerate(authority.inner_object_manifest)
    ]
    if len(manifest) != 110:
        _fail("catalog recovery outer manifest count differs")
    expected_sequence = [
        _identity(
            authority.inner_replay_receipt_identity,
            label="outer-derived replay receipt",
        ),
        _identity(
            authority.inner_catalog_release_identity,
            label="outer-derived catalog release",
        ),
    ]
    for ordinal in range(source.TASK_COUNT):
        # v1 opens the structural catalog first, then that catalog's source
        # derivation receipt; the outer manifest itself stores the pair in the
        # reverse (derivation, catalog) publication order.
        expected_sequence.extend((
            _identity(
                manifest[ordinal * 2 + 1]["identity"],
                label=f"outer-derived catalog[{ordinal}]",
            ),
            _identity(
                manifest[ordinal * 2]["identity"],
                label=f"outer-derived derivation[{ordinal}]",
            ),
        ))
    observed: list[dict[str, object]] = []

    def guarded(identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="candidate predecessor identity")
        if str(identity["uri"]).startswith(
            v1.catalog_adapter.FIXED_CATALOG_NAMESPACE
        ):
            ordinal = len(observed)
            if ordinal >= len(expected_sequence) or identity != expected_sequence[ordinal]:
                _fail(
                    "inner catalog read differs from outer-derived exact sequence"
                )
            observed.append(identity)
        return read_exact(identity)

    def require_complete() -> None:
        if observed != expected_sequence:
            _fail("inner catalog replay did not consume all 110 outer identities")

    return guarded, require_complete


def _binding_fields(binding: Mapping[str, object]) -> dict[str, object]:
    retained = _mapping(binding, label="candidate recovery binding")
    _validate_hash(
        retained,
        field="candidate_implementation_binding_sha256",
        label="candidate recovery binding",
    )
    return {
        _OUTER_IDENTITY_FIELD: retained[_OUTER_IDENTITY_FIELD],
        _OUTER_SHA_FIELD: retained[_OUTER_SHA_FIELD],
        _BINDING_FIELD: retained,
        _READ_CLASS_FIELD: retained[_READ_CLASS_FIELD],
    }


def _upgrade_material(
    material_v1: Mapping[str, object], *, binding: Mapping[str, object],
) -> dict[str, object]:
    body = _mapping(material_v1, label="v1 candidate material")
    body.pop("candidate_material_sha256", None)
    body["schema_version"] = MATERIAL_SCHEMA
    body.update(_binding_fields(binding))
    body["catalog_inner_object_manifest_sha256"] = binding[
        "catalog_inner_object_manifest_sha256"
    ]
    body["catalog_inner_object_count"] = binding["catalog_inner_object_count"]
    return _with_hash(body, field="candidate_material_sha256")


def _upgrade_receipt(
    receipt_v1: Mapping[str, object], *, binding: Mapping[str, object],
) -> dict[str, object]:
    body = _mapping(receipt_v1, label="v1 slate derivation receipt")
    body.pop("slate_derivation_sha256", None)
    body["schema_version"] = SLATE_DERIVATION_SCHEMA
    body.update(_binding_fields(binding))
    body["complete_cross_arm_candidate_population_preserved"] = True
    body["exact_occurrence_provenance_preserved"] = True
    return _with_hash(body, field="slate_derivation_sha256")


def _downgrade_receipt(receipt_v2: Mapping[str, object]) -> dict[str, object]:
    body = _mapping(receipt_v2, label="v2 slate derivation receipt")
    _validate_hash(
        body,
        field="slate_derivation_sha256",
        label="v2 slate derivation receipt",
    )
    if body.get("schema_version") != SLATE_DERIVATION_SCHEMA:
        _fail("v2 slate derivation schema differs")
    for field in (
        "slate_derivation_sha256",
        _OUTER_IDENTITY_FIELD,
        _OUTER_SHA_FIELD,
        _BINDING_FIELD,
        _READ_CLASS_FIELD,
        "complete_cross_arm_candidate_population_preserved",
        "exact_occurrence_provenance_preserved",
    ):
        body.pop(field, None)
    body["schema_version"] = v1.SLATE_DERIVATION_SCHEMA
    return _with_hash(body, field="slate_derivation_sha256")


def _upgrade_panel(
    panel_v1: Mapping[str, object],
    *,
    receipts_v2: Sequence[Mapping[str, object]],
    binding: Mapping[str, object],
) -> dict[str, object]:
    body = _mapping(panel_v1, label="v1 panel derivation receipt")
    body.pop("panel_derivation_sha256", None)
    body["schema_version"] = PANEL_DERIVATION_SCHEMA
    slates = [
        _mapping(value, label=f"panel slate[{ordinal}]")
        for ordinal, value in enumerate(_sequence(body.get("slates"), label="slates"))
    ]
    if len(slates) != source.TASK_COUNT or len(receipts_v2) != source.TASK_COUNT:
        _fail("panel/receipt census differs")
    for ordinal, row in enumerate(slates):
        row["slate_derivation_sha256"] = receipts_v2[ordinal][
            "slate_derivation_sha256"
        ]
    body["slates"] = slates
    body["slate_derivation_manifest_sha256"] = source.canonical_sha256(
        list(receipts_v2)
    )
    body.update(_binding_fields(binding))
    body["all_54_receipts_outer_bound"] = True
    return _with_hash(body, field="panel_derivation_sha256")


def _downgrade_panel(
    panel_v2: Mapping[str, object],
    *,
    receipts_v1: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    body = _mapping(panel_v2, label="v2 panel derivation receipt")
    _validate_hash(
        body,
        field="panel_derivation_sha256",
        label="v2 panel derivation receipt",
    )
    if body.get("schema_version") != PANEL_DERIVATION_SCHEMA:
        _fail("v2 panel derivation schema differs")
    for field in (
        "panel_derivation_sha256",
        _OUTER_IDENTITY_FIELD,
        _OUTER_SHA_FIELD,
        _BINDING_FIELD,
        _READ_CLASS_FIELD,
        "all_54_receipts_outer_bound",
    ):
        body.pop(field, None)
    body["schema_version"] = v1.PANEL_DERIVATION_SCHEMA
    slates = [
        _mapping(value, label=f"panel slate[{ordinal}]")
        for ordinal, value in enumerate(_sequence(body.get("slates"), label="slates"))
    ]
    if len(slates) != source.TASK_COUNT or len(receipts_v1) != source.TASK_COUNT:
        _fail("v2 panel/receipt census differs")
    for ordinal, row in enumerate(slates):
        row["slate_derivation_sha256"] = receipts_v1[ordinal][
            "slate_derivation_sha256"
        ]
    body["slates"] = slates
    body["slate_derivation_manifest_sha256"] = source.canonical_sha256(
        list(receipts_v1)
    )
    return _with_hash(body, field="panel_derivation_sha256")


def _upgrade_bundle(
    bundle_v1: Mapping[str, object], *, binding: Mapping[str, object],
) -> dict[str, object]:
    body = _mapping(bundle_v1, label="v1 candidate authority bundle")
    body.pop("candidate_authority_bundle_sha256", None)
    receipts_v1 = [
        _mapping(value, label=f"v1 slate receipt[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            body.get("slate_derivation_receipts"), label="v1 slate receipts"
        ))
    ]
    receipts_v2 = [
        _upgrade_receipt(receipt, binding=binding) for receipt in receipts_v1
    ]
    panel_v2 = _upgrade_panel(
        _mapping(body.get("panel_derivation_receipt"), label="v1 panel receipt"),
        receipts_v2=receipts_v2,
        binding=binding,
    )
    body["schema_version"] = AUTHORITY_BUNDLE_SCHEMA
    body["slate_derivation_receipts"] = receipts_v2
    body["slate_derivation_manifest_sha256"] = source.canonical_sha256(receipts_v2)
    body["panel_derivation_receipt"] = panel_v2
    body.update(_binding_fields(binding))
    body["complete_cross_arm_candidate_population_preserved"] = True
    body["exact_occurrence_provenance_preserved"] = True
    return _with_hash(body, field="candidate_authority_bundle_sha256")


def _downgrade_bundle(bundle_v2: Mapping[str, object]) -> dict[str, object]:
    body = _mapping(bundle_v2, label="v2 candidate authority bundle")
    _validate_hash(
        body,
        field="candidate_authority_bundle_sha256",
        label="v2 candidate authority bundle",
    )
    if body.get("schema_version") != AUTHORITY_BUNDLE_SCHEMA:
        _fail("v2 candidate authority bundle schema differs")
    receipts_v2 = [
        _mapping(value, label=f"v2 slate receipt[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            body.get("slate_derivation_receipts"), label="v2 slate receipts"
        ))
    ]
    receipts_v1 = [_downgrade_receipt(receipt) for receipt in receipts_v2]
    panel_v1 = _downgrade_panel(
        _mapping(body.get("panel_derivation_receipt"), label="v2 panel receipt"),
        receipts_v1=receipts_v1,
    )
    for field in (
        "candidate_authority_bundle_sha256",
        _OUTER_IDENTITY_FIELD,
        _OUTER_SHA_FIELD,
        _BINDING_FIELD,
        _READ_CLASS_FIELD,
        "complete_cross_arm_candidate_population_preserved",
        "exact_occurrence_provenance_preserved",
    ):
        body.pop(field, None)
    body["schema_version"] = v1.AUTHORITY_BUNDLE_SCHEMA
    body["slate_derivation_receipts"] = receipts_v1
    body["slate_derivation_manifest_sha256"] = source.canonical_sha256(receipts_v1)
    body["panel_derivation_receipt"] = panel_v1
    return _with_hash(body, field="candidate_authority_bundle_sha256")


def _require_bundle_binding(
    bundle: Mapping[str, object], *, expected_binding: Mapping[str, object],
) -> None:
    binding = _mapping(bundle.get(_BINDING_FIELD), label="bundle recovery binding")
    if binding != _mapping(expected_binding, label="expected recovery binding"):
        _fail("candidate bundle outer/code binding differs")
    fields = _binding_fields(binding)
    for field, expected in fields.items():
        if bundle.get(field) != expected:
            _fail(f"candidate bundle {field} differs")
    receipts = [
        _mapping(value, label=f"candidate receipt[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            bundle.get("slate_derivation_receipts"), label="candidate receipts"
        ))
    ]
    if len(receipts) != source.TASK_COUNT:
        _fail("candidate bundle receipt census differs")
    for ordinal, receipt in enumerate(receipts):
        for field, expected in fields.items():
            if receipt.get(field) != expected:
                _fail(f"candidate receipt[{ordinal}] {field} differs")
    panel = _mapping(bundle.get("panel_derivation_receipt"), label="candidate panel")
    for field, expected in fields.items():
        if panel.get(field) != expected:
            _fail(f"candidate panel {field} differs")


def derive_fixed_g0_candidate_material_v2(
    *,
    repository_root: Path,
    catalog_recovery_outer_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Derive complete candidate material after opening only the outer input."""

    authority, binding = _open_outer_and_binding(
        repository_root=repository_root,
        catalog_recovery_outer_identity=catalog_recovery_outer_identity,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    guarded_reader, require_complete_catalog_replay = _outer_manifest_gated_reader(
        authority=authority, read_exact=read_exact
    )
    try:
        material_v1 = v1.derive_fixed_g0_candidate_material_v1(
            repository_root=repository_root,
            catalog_replay_receipt_identity=authority.inner_replay_receipt_identity,
            read_exact=guarded_reader,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV2Error(
            f"inherited v1 candidate derivation failed: {exc}"
        ) from exc
    require_complete_catalog_replay()
    _require_outer_manifest(authority=authority, material=material_v1)
    return _upgrade_material(material_v1, binding=binding)


def build_fixed_g0_candidate_authority_v2(
    *,
    release_id: str,
    namespace: str,
    repository_root: Path,
    catalog_recovery_outer_identity: Mapping[str, object],
    candidate_artifact_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Build the 54-slate outer-bound candidate authority bundle."""

    authority, binding = _open_outer_and_binding(
        repository_root=repository_root,
        catalog_recovery_outer_identity=catalog_recovery_outer_identity,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    guarded_reader, require_complete_catalog_replay = _outer_manifest_gated_reader(
        authority=authority, read_exact=read_exact
    )
    try:
        bundle_v1 = v1.build_fixed_g0_candidate_authority_v1(
            release_id=release_id,
            namespace=namespace,
            repository_root=repository_root,
            catalog_replay_receipt_identity=authority.inner_replay_receipt_identity,
            candidate_artifact_identities=candidate_artifact_identities,
            read_exact=guarded_reader,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV2Error(
            f"inherited v1 candidate authority build failed: {exc}"
        ) from exc
    require_complete_catalog_replay()
    panel = _mapping(
        bundle_v1.get("panel_derivation_receipt"), label="v1 panel receipt"
    )
    material_projection = {
        "slate_predecessor_bindings": [
            {"catalog_binding": receipt["catalog_binding"]}
            for receipt in _sequence(
                bundle_v1.get("slate_derivation_receipts"),
                label="v1 slate receipts",
            )
        ],
        "catalog_release_identity": panel["catalog_release_identity"],
        "catalog_release_sha256": panel["catalog_release_sha256"],
        "catalog_replay_receipt_identity": panel["catalog_replay_receipt_identity"],
        "catalog_replay_receipt_sha256": panel[
            "catalog_replay_receipt_sha256"
        ],
    }
    _require_outer_manifest(authority=authority, material=material_projection)
    return _upgrade_bundle(bundle_v1, binding=binding)


def validate_fixed_g0_candidate_authority_v2(
    value: object,
    *,
    repository_root: Path,
    catalog_recovery_outer_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Deep exact replay and byte-reconstruct the complete v2 authority."""

    item = _mapping(value, label="v2 candidate authority bundle")
    retained_binding = _mapping(
        item.get(_BINDING_FIELD), label="v2 candidate recovery binding"
    )
    bound_commit = _commit(
        retained_binding.get("candidate_implementation_commit_sha"),
        label="v2 candidate implementation commit",
    )
    authority, binding = _open_outer_and_binding(
        repository_root=repository_root,
        catalog_recovery_outer_identity=catalog_recovery_outer_identity,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        candidate_implementation_commit_sha=bound_commit,
    )
    guarded_reader, require_complete_catalog_replay = _outer_manifest_gated_reader(
        authority=authority, read_exact=read_exact
    )
    _require_bundle_binding(item, expected_binding=binding)
    projected_v1 = _downgrade_bundle(item)
    try:
        validated_v1 = v1.validate_fixed_g0_candidate_authority_v1(
            projected_v1,
            repository_root=repository_root,
            catalog_replay_receipt_identity=authority.inner_replay_receipt_identity,
            read_exact=guarded_reader,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV2Error(
            f"inherited v1 candidate authority replay failed: {exc}"
        ) from exc
    require_complete_catalog_replay()
    panel = _mapping(
        validated_v1.get("panel_derivation_receipt"), label="validated v1 panel"
    )
    material_projection = {
        "slate_predecessor_bindings": [
            {"catalog_binding": receipt["catalog_binding"]}
            for receipt in _sequence(
                validated_v1.get("slate_derivation_receipts"),
                label="validated v1 slate receipts",
            )
        ],
        "catalog_release_identity": panel["catalog_release_identity"],
        "catalog_release_sha256": panel["catalog_release_sha256"],
        "catalog_replay_receipt_identity": panel["catalog_replay_receipt_identity"],
        "catalog_replay_receipt_sha256": panel[
            "catalog_replay_receipt_sha256"
        ],
    }
    _require_outer_manifest(authority=authority, material=material_projection)
    rebuilt = _upgrade_bundle(validated_v1, binding=binding)
    if source.canonical_json_bytes(rebuilt) != source.canonical_json_bytes(item):
        _fail("v2 candidate authority differs from exact predecessor replay")
    return rebuilt


__all__ = [
    "AUTHORITY_BUNDLE_SCHEMA",
    "CANDIDATE_IMPLEMENTATION_BINDING_SCHEMA",
    "CANDIDATE_IMPLEMENTATION_PATHS",
    "CORE_V2_MODULE_PATH",
    "CorpusR6FixedG0CandidateAuthorityV2Error",
    "MATERIAL_SCHEMA",
    "FROZEN_CORE_V1_MODULE_PATH",
    "PANEL_DERIVATION_SCHEMA",
    "READ_CLASS_ATTESTATION_SCHEMA",
    "RELEASE_V2_MODULE_PATH",
    "SLATE_DERIVATION_SCHEMA",
    "build_fixed_g0_candidate_authority_v2",
    "derive_fixed_g0_candidate_material_v2",
    "validate_fixed_g0_candidate_authority_v2",
]
