"""Outer- and capture-plan-bound R6 matchup component publication.

This successor accepts one candidate-authority-v2 root identity and one
tracked capture-plan-v3 body.  It exact-reopens the candidate authority,
requires the candidate, plan, and component outer bindings to agree, derives
the legacy receipt/release/catalog compatibility bodies only from that
authority, and invokes the frozen v1 create-once/root-last publisher.  Before
returning, it exact-reopens the complete materialized component graph and
replays the candidate and capture-plan predecessors again.

The compatibility v1 publisher remains a reducer, never authority.  This
module exposes no caller-selected inner catalog, candidate release, structural
catalog, adapter-lock body, or producer-code seam and reads no realized
outcome.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import stat
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate,
)
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_v2 as candidate_core,
)
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_outer_candidate_authority_v3 as capture,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_candidate_authority_v2 as durable_v2,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_v1 as publication_v1,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


PUBLICATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-component-publication-outer-candidate-authority/v3"
)
COMPONENT_PUBLICATION_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_component_publication_outer_candidate_authority_v3.py"
)
PUBLICATION_V1_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_component_publication_v1.py"
)
DURABLE_V2_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_component_publication_candidate_authority_v2.py"
)
COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS: Final = tuple(sorted((
    COMPONENT_PUBLICATION_MODULE_PATH,
    PUBLICATION_V1_MODULE_PATH,
    DURABLE_V2_MODULE_PATH,
    capture.CAPTURE_PLAN_MODULE_PATH,
    candidate_core.CORE_V2_MODULE_PATH,
    candidate_core.RELEASE_V2_MODULE_PATH,
)))

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_MEASUREMENT_FIELDS: Final = frozenset({"relative_path", "sha256", "bytes"})
_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "capture_plan",
    "capture_plan_sha256",
    "capture_plan_lock_relative_path",
    "capture_plan_observed_commit_sha",
    "fixed_g0_candidate_authority_root_identity",
    "fixed_g0_candidate_authority_root_sha256",
    "fixed_g0_candidate_authority_schema",
    "catalog_recovery_outer_identity",
    "catalog_recovery_outer_attestation_sha256",
    "catalog_recovery_candidate_binding",
    "catalog_inner_object_count",
    "catalog_inner_object_manifest_sha256",
    "accepted_candidate_release_identity",
    "accepted_candidate_release_sha256",
    "catalog_replay_receipt_identity",
    "catalog_replay_receipt_sha256",
    "catalog_release_identity",
    "catalog_release_sha256",
    "component_successor_implementation_commit_sha",
    "component_successor_implementation_measurements",
    "component_successor_implementation_measurements_sha256",
    "candidate_authority_exact_reopened",
    "capture_plan_tracked_exact_reopened",
    "capture_plan_deep_validated",
    "component_plan_candidate_outer_equality_verified",
    "inner_compatibility_inputs_derived_from_candidate_root",
    "component_successor_remote_exact_read_performed",
    "caller_catalog_replay_receipt_body_allowed",
    "caller_catalog_replay_receipt_identity_allowed",
    "caller_catalog_release_body_allowed",
    "caller_catalog_release_identity_allowed",
    "caller_structural_catalogs_allowed",
    "caller_candidate_release_body_allowed",
    "caller_candidate_release_identity_allowed",
    "caller_adapter_final_lock_body_allowed",
    "caller_producer_code_identity_allowed",
    "legacy_v1_publication_path_authoritative",
    "authoritative_consumer_requires_full_v3_result",
    "component_publication_receipt",
    "component_publication_receipt_sha256",
    "producer_release_identity",
    "producer_release_sha256",
    "all_v1_outputs_exact_reopened_before_return",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *source.FALSE_AUTHORITY_FIELDS,
    "outer_candidate_component_publication_receipt_sha256",
})

ReadExact = candidate.ReadExact
GitHead = candidate.GitHead
GitBlob = candidate.GitBlob
GitStatus = candidate.GitStatus
PublishCreateOnce = publication_v1.PublishCreateOnce


class CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
    ValueError
):
    """The outer/capture/candidate-rooted component publication failed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
        message
    )


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 40-hex")
    return value


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _runtime_path(repository_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
        _fail(f"component implementation path differs: {relative_path}")
    path = repository_root / relative
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"component implementation path is absent: {relative_path}"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        _fail(f"component implementation path differs: {relative_path}")
    return path


def _read_regular_nofollow(path: Path, *, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        _fail(f"{label} requires O_NOFOLLOW support")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags | nofollow)
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(mode):
            _fail(f"{label} is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            return handle.read()
    except CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error:
        raise
    except OSError as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"{label} secure current read failed"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _measure_implementation(
    *,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    bound_commit_sha: str | None = None,
) -> tuple[str, list[dict[str, object]]]:
    if (
        not isinstance(repository_root, Path)
        or not repository_root.is_absolute()
        or not callable(git_head)
        or not callable(git_blob)
        or not callable(git_status)
    ):
        _fail("component implementation Git boundary differs")
    try:
        root = repository_root.resolve(strict=True)
        current_head = _commit(
            git_head(root), label="component implementation current HEAD"
        )
        commit = (
            current_head
            if bound_commit_sha is None
            else _commit(
                bound_commit_sha, label="component implementation commit"
            )
        )
        status = git_status(root, COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS)
    except CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            "component implementation Git resolution failed"
        ) from exc
    if type(status) is not bytes or status != b"":
        _fail("component implementation files must be tracked-clean")
    rows: list[dict[str, object]] = []
    for relative_path in COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS:
        path = _runtime_path(root, relative_path)
        try:
            current_raw = _read_regular_nofollow(
                path, label=f"component implementation {relative_path}"
            )
            retained_raw = git_blob(root, commit, relative_path)
        except Exception as exc:
            raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
                f"component implementation read failed: {relative_path}"
            ) from exc
        if type(retained_raw) is not bytes or retained_raw != current_raw:
            _fail(f"component implementation code drift: {relative_path}")
        rows.append({
            "relative_path": relative_path,
            "sha256": sha256(current_raw).hexdigest(),
            "bytes": len(current_raw),
        })
    return commit, rows


def _normalize_measurements(value: object) -> list[dict[str, object]]:
    rows = [
        _mapping(row, label=f"component implementation[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(value, label="component implementation measurements")
        )
    ]
    if len(rows) != len(COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS):
        _fail("component implementation measurement count differs")
    normalized: list[dict[str, object]] = []
    for ordinal, row in enumerate(rows):
        if set(row) != set(_MEASUREMENT_FIELDS):
            _fail(f"component implementation[{ordinal}] fields differ")
        relative_path = row.get("relative_path")
        size = row.get("bytes")
        if (
            relative_path != COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS[ordinal]
            or type(size) is not int
            or size < 1
        ):
            _fail(f"component implementation[{ordinal}] differs")
        normalized.append({
            "relative_path": relative_path,
            "sha256": _digest(
                row.get("sha256"),
                label=f"component implementation[{ordinal}] SHA",
            ),
            "bytes": size,
        })
    return normalized


def _tracked_plan_and_adapter_lock(
    plan_value: object,
    *,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    bound_plan_commit_sha: str | None = None,
) -> tuple[dict[str, object], str, bytes]:
    try:
        plan = capture.validate_capture_plan_lock_v3(plan_value)
    except capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"capture-plan v3 structure differs: {exc}"
        ) from exc
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        _fail("capture-plan Git repository differs")
    try:
        root = repository_root.resolve(strict=True)
        current_head = _commit(git_head(root), label="capture-plan current HEAD")
        observed_commit = (
            current_head
            if bound_plan_commit_sha is None
            else _commit(bound_plan_commit_sha, label="capture-plan observed commit")
        )
        status = git_status(root, (capture.CAPTURE_PLAN_LOCK_PATH,))
        plan_blob = git_blob(
            root, observed_commit, capture.CAPTURE_PLAN_LOCK_PATH
        )
    except CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            "tracked capture-plan Git resolution failed"
        ) from exc
    expected_plan_raw = canonical_json_bytes(plan) + b"\n"
    plan_path = _runtime_path(root, capture.CAPTURE_PLAN_LOCK_PATH)
    if (
        type(status) is not bytes
        or status != b""
        or type(plan_blob) is not bytes
        or plan_blob != expected_plan_raw
        or _read_regular_nofollow(
            plan_path, label="tracked capture-plan current file"
        ) != expected_plan_raw
    ):
        _fail("tracked capture-plan Git/current bytes differ")
    adapter = _mapping(
        plan.get("adapter_final_release_lock_binding"),
        label="adapter final release lock binding",
    )
    adapter_commit = _commit(
        adapter.get("commit_sha"), label="adapter final release lock commit"
    )
    adapter_path = adapter.get("relative_path")
    if type(adapter_path) is not str:
        _fail("adapter final release lock path differs")
    try:
        adapter_raw = git_blob(root, adapter_commit, adapter_path)
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            "adapter final release lock Git read failed"
        ) from exc
    if (
        type(adapter_raw) is not bytes
        or len(adapter_raw) != adapter.get("bytes")
        or sha256(adapter_raw).hexdigest() != adapter.get("sha256")
    ):
        _fail("adapter final release lock Git binding differs")
    return plan, observed_commit, adapter_raw


def _open_candidate(
    *,
    root_identity: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[candidate.ReopenedFixedG0CandidateAuthorityV2, dict[str, object]]:
    try:
        return capture._open_candidate(
            candidate_authority_root_identity=root_identity,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"candidate-authority v2 exact reopen failed: {exc}"
        ) from exc


def _shallow_reopen_candidate_root_before_inner(
    *,
    root_identity: Mapping[str, object],
    plan: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Read only the terminal root and compare plan/outer before deep replay."""

    identity = _identity(root_identity, label="candidate-authority v2 root")
    # Reuse the authoritative namespace parser so a legacy root is rejected
    # without performing even the terminal-root storage read.
    try:
        candidate._prefix_from_root_identity(identity)
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"candidate-authority legacy root rejected: {exc}"
        ) from exc
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            "candidate-authority terminal root exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail("candidate-authority terminal root content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            "candidate-authority terminal root must be canonical JSON"
        ) from exc
    if not isinstance(parsed, Mapping) or canonical_json_bytes(parsed) != raw:
        _fail("candidate-authority terminal root canonical bytes differ")
    try:
        root = candidate.validate_fixed_g0_candidate_authority_release_structure_v2(
            parsed
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"candidate-authority terminal root structure differs: {exc}"
        ) from exc
    if (
        root.get("target_uri") != identity["uri"]
        or identity != plan.get("fixed_g0_candidate_authority_root_identity")
        or root.get("candidate_authority_release_sha256")
        != plan.get("fixed_g0_candidate_authority_root_sha256")
        or root.get("catalog_recovery_outer_identity")
        != plan.get("catalog_recovery_outer_identity")
        or root.get("catalog_recovery_outer_attestation_sha256")
        != plan.get("catalog_recovery_outer_attestation_sha256")
        or root.get("catalog_recovery_candidate_binding")
        != plan.get("catalog_recovery_candidate_binding")
        or root.get("catalog_inner_object_count")
        != plan.get("catalog_inner_object_count")
        or root.get("catalog_inner_object_manifest_sha256")
        != plan.get("catalog_inner_object_manifest_sha256")
        or root.get("catalog_replay_receipt_identity")
        != plan.get("fixed_g0_replay_receipt_identity")
        or root.get("catalog_replay_receipt_sha256")
        != plan.get("fixed_g0_replay_receipt_sha256")
        or root.get("catalog_release_identity")
        != plan.get("catalog_release_identity")
        or root.get("catalog_release_sha256")
        != plan.get("catalog_release_sha256")
        or root.get("candidate_release_identity")
        != plan.get("fixed_g0_candidate_root_candidate_release_identity")
        or root.get("candidate_release_sha256")
        != plan.get("fixed_g0_candidate_root_candidate_release_sha256")
    ):
        _fail("candidate terminal root and capture-plan outer differ before inner read")
    return root


def _require_plan_candidate_equality(
    *, plan: Mapping[str, object], binding: Mapping[str, object]
) -> None:
    if (
        plan.get("fixed_g0_candidate_authority_root_identity")
        != binding.get("root_identity")
        or plan.get("fixed_g0_candidate_authority_root_sha256")
        != binding.get("root_sha256")
        or plan.get("catalog_recovery_outer_identity")
        != binding.get("outer_identity")
        or plan.get("catalog_recovery_outer_attestation_sha256")
        != binding.get("outer_sha256")
        or plan.get("catalog_recovery_candidate_binding")
        != binding.get("recovery_binding")
        or plan.get("catalog_inner_object_count")
        != binding["root"]["catalog_inner_object_count"]
        or plan.get("catalog_inner_object_manifest_sha256")
        != binding["root"]["catalog_inner_object_manifest_sha256"]
        or plan.get("fixed_g0_candidate_root_candidate_release_identity")
        != binding.get("candidate_release_identity")
        or plan.get("fixed_g0_candidate_root_candidate_release_sha256")
        != binding.get("candidate_release_sha256")
    ):
        _fail("component, capture plan, and candidate outer/root differ")


def _derive_inner_inputs(
    *,
    binding: Mapping[str, object],
    reopened: candidate.ReopenedFixedG0CandidateAuthorityV2,
    read_exact: ReadExact,
) -> dict[str, object]:
    try:
        inner = capture._derived_inner_bodies(
            binding=binding, read_exact=read_exact
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"candidate-root-derived compatibility reopen failed: {exc}"
        ) from exc
    release = _mapping(inner["catalog_release"], label="catalog release")
    entries = [
        _mapping(row, label=f"catalog release entry[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(release.get("entries"), label="catalog release entries")
        )
    ]
    if len(entries) != source.TASK_COUNT:
        _fail("candidate-root-derived catalog release must contain 54 entries")
    catalogs: list[dict[str, object]] = []
    for ordinal, entry in enumerate(entries):
        try:
            body, _ = capture._exact_json(
                entry.get("catalog_identity"),
                read_exact=read_exact,
                label=f"outer-derived structural catalog[{ordinal}]",
            )
        except Exception as exc:
            raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
                f"structural catalog[{ordinal}] exact reopen failed: {exc}"
            ) from exc
        catalogs.append(body)
    return {
        **inner,
        "structural_catalogs": catalogs,
        "candidate_release": _mapping(
            reopened.candidate_release, label="accepted candidate release"
        ),
        "candidate_release_identity": _identity(
            reopened.candidate_release_identity,
            label="accepted candidate release",
        ),
    }


def _deep_validate_plan(
    *,
    plan: Mapping[str, object],
    adapter_raw: bytes,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    adapter = _mapping(
        plan.get("adapter_final_release_lock_binding"),
        label="adapter final release lock binding",
    )
    try:
        return capture.validate_capture_plan_against_prerequisites_v3(
            plan,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            adapter_final_release_lock_commit_sha=str(adapter["commit_sha"]),
            adapter_final_release_lock_raw=adapter_raw,
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"capture-plan v3 deep validation failed: {exc}"
        ) from exc


def _compatibility_binding(
    *, binding: Mapping[str, object]
) -> dict[str, object]:
    root = _mapping(binding.get("root"), label="candidate root")
    return {
        "fixed_g0_candidate_authority_root_identity": binding["root_identity"],
        "fixed_g0_candidate_authority_root_sha256": binding["root_sha256"],
        "fixed_g0_candidate_authority_schema": candidate.RELEASE_SCHEMA,
        "catalog_recovery_outer_identity": binding["outer_identity"],
        "catalog_recovery_outer_attestation_sha256": binding["outer_sha256"],
        "catalog_recovery_candidate_binding": binding["recovery_binding"],
        "catalog_inner_object_count": root["catalog_inner_object_count"],
        "catalog_inner_object_manifest_sha256": root[
            "catalog_inner_object_manifest_sha256"
        ],
        "accepted_candidate_release_identity": binding[
            "candidate_release_identity"
        ],
        "accepted_candidate_release_sha256": binding["candidate_release_sha256"],
        "catalog_replay_receipt_identity": root[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": root["catalog_replay_receipt_sha256"],
        "catalog_release_identity": root["catalog_release_identity"],
        "catalog_release_sha256": root["catalog_release_sha256"],
    }


def _validate_v1_result(
    result: object,
    *,
    binding: Mapping[str, object],
    reopened: candidate.ReopenedFixedG0CandidateAuthorityV2,
) -> tuple[dict[str, object], dict[str, object]]:
    item = _mapping(result, label="v1 component publication result")
    if set(item) != {"publication_receipt", "offline_panel"}:
        _fail("v1 component publication result fields differ")
    try:
        receipt = publication_v1.validate_component_publication_receipt_v1(
            item["publication_receipt"]
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    panel = _mapping(item["offline_panel"], label="v1 offline panel")
    if (
        receipt.get("fixed_g0_replay_receipt_identity")
        != binding["catalog_replay_receipt_identity"]
        or receipt.get("catalog_release_identity")
        != binding["catalog_release_identity"]
        or receipt.get("accepted_candidate_release_identity")
        != binding["accepted_candidate_release_identity"]
        or panel.get("fixed_g0_replay_receipt_identity")
        != binding["catalog_replay_receipt_identity"]
        or panel.get("catalog_release_identity")
        != binding["catalog_release_identity"]
        or panel.get("accepted_candidate_release_identity")
        != binding["accepted_candidate_release_identity"]
        or panel.get("accepted_candidate_release") != reopened.candidate_release
    ):
        _fail("v1 component publication differs from outer candidate authority")
    return receipt, panel


def _build_receipt(
    *,
    plan: Mapping[str, object],
    plan_commit: str,
    binding: Mapping[str, object],
    implementation_commit: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    v1_receipt: Mapping[str, object],
) -> dict[str, object]:
    measurements = _normalize_measurements(implementation_measurements)
    body: dict[str, object] = {
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
        "capture_plan": dict(plan),
        "capture_plan_sha256": plan["capture_plan_sha256"],
        "capture_plan_lock_relative_path": capture.CAPTURE_PLAN_LOCK_PATH,
        "capture_plan_observed_commit_sha": plan_commit,
        **_compatibility_binding(binding=binding),
        "component_successor_implementation_commit_sha": implementation_commit,
        "component_successor_implementation_measurements": measurements,
        "component_successor_implementation_measurements_sha256": (
            canonical_sha256(measurements)
        ),
        "candidate_authority_exact_reopened": True,
        "capture_plan_tracked_exact_reopened": True,
        "capture_plan_deep_validated": True,
        "component_plan_candidate_outer_equality_verified": True,
        "inner_compatibility_inputs_derived_from_candidate_root": True,
        "component_successor_remote_exact_read_performed": True,
        "caller_catalog_replay_receipt_body_allowed": False,
        "caller_catalog_replay_receipt_identity_allowed": False,
        "caller_catalog_release_body_allowed": False,
        "caller_catalog_release_identity_allowed": False,
        "caller_structural_catalogs_allowed": False,
        "caller_candidate_release_body_allowed": False,
        "caller_candidate_release_identity_allowed": False,
        "caller_adapter_final_lock_body_allowed": False,
        "caller_producer_code_identity_allowed": False,
        "legacy_v1_publication_path_authoritative": False,
        "authoritative_consumer_requires_full_v3_result": True,
        "component_publication_receipt": dict(v1_receipt),
        "component_publication_receipt_sha256": v1_receipt[
            "component_publication_receipt_sha256"
        ],
        "producer_release_identity": v1_receipt["producer_release_identity"],
        "producer_release_sha256": v1_receipt["producer_release_sha256"],
        "all_v1_outputs_exact_reopened_before_return": True,
        **_policy(),
    }
    body["outer_candidate_component_publication_receipt_sha256"] = (
        canonical_sha256(body)
    )
    return validate_component_publication_outer_candidate_authority_receipt_v3(
        body
    )


def validate_component_publication_outer_candidate_authority_receipt_v3(
    value: object,
) -> dict[str, object]:
    """Validate receipt structure; authority still requires full reopen."""

    item = _mapping(value, label="outer-candidate component receipt")
    if set(item) != set(_RECEIPT_FIELDS):
        _fail("outer-candidate component receipt fields differ")
    retained = _digest(
        item.get("outer_candidate_component_publication_receipt_sha256"),
        label="outer-candidate component receipt self-hash",
    )
    unhashed = dict(item)
    del unhashed["outer_candidate_component_publication_receipt_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("outer-candidate component receipt self-hash differs")
    for field, expected in _policy().items():
        if item.get(field) != expected:
            _fail("outer-candidate component receipt claims authority")
    try:
        plan = capture.validate_capture_plan_lock_v3(item.get("capture_plan"))
    except capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"embedded capture plan differs: {exc}"
        ) from exc
    root_identity = _identity(
        item.get("fixed_g0_candidate_authority_root_identity"),
        label="candidate-authority v2 root",
    )
    outer_identity = _identity(
        item.get("catalog_recovery_outer_identity"),
        label="catalog recovery outer",
    )
    candidate_identity = _identity(
        item.get("accepted_candidate_release_identity"),
        label="accepted candidate release",
    )
    replay_identity = _identity(
        item.get("catalog_replay_receipt_identity"),
        label="catalog replay receipt",
    )
    catalog_identity = _identity(
        item.get("catalog_release_identity"), label="catalog release"
    )
    binding = _mapping(
        item.get("catalog_recovery_candidate_binding"),
        label="catalog recovery candidate binding",
    )
    measurements = _normalize_measurements(
        item.get("component_successor_implementation_measurements")
    )
    try:
        v1_receipt = publication_v1.validate_component_publication_receipt_v1(
            item.get("component_publication_receipt")
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    fixed_false = (
        "caller_catalog_replay_receipt_body_allowed",
        "caller_catalog_replay_receipt_identity_allowed",
        "caller_catalog_release_body_allowed",
        "caller_catalog_release_identity_allowed",
        "caller_structural_catalogs_allowed",
        "caller_candidate_release_body_allowed",
        "caller_candidate_release_identity_allowed",
        "caller_adapter_final_lock_body_allowed",
        "caller_producer_code_identity_allowed",
        "legacy_v1_publication_path_authoritative",
    )
    fixed_true = (
        "candidate_authority_exact_reopened",
        "capture_plan_tracked_exact_reopened",
        "capture_plan_deep_validated",
        "component_plan_candidate_outer_equality_verified",
        "inner_compatibility_inputs_derived_from_candidate_root",
        "component_successor_remote_exact_read_performed",
        "authoritative_consumer_requires_full_v3_result",
        "all_v1_outputs_exact_reopened_before_return",
    )
    if (
        item.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA
        or item.get("capture_plan_sha256") != plan["capture_plan_sha256"]
        or item.get("capture_plan_lock_relative_path")
        != capture.CAPTURE_PLAN_LOCK_PATH
        or item.get("fixed_g0_candidate_authority_schema")
        != candidate.RELEASE_SCHEMA
        or root_identity != plan["fixed_g0_candidate_authority_root_identity"]
        or item.get("fixed_g0_candidate_authority_root_sha256")
        != plan["fixed_g0_candidate_authority_root_sha256"]
        or outer_identity != plan["catalog_recovery_outer_identity"]
        or item.get("catalog_recovery_outer_attestation_sha256")
        != plan["catalog_recovery_outer_attestation_sha256"]
        or binding != plan["catalog_recovery_candidate_binding"]
        or item.get("catalog_inner_object_count")
        != plan["catalog_inner_object_count"]
        or item.get("catalog_inner_object_manifest_sha256")
        != plan["catalog_inner_object_manifest_sha256"]
        or candidate_identity
        != plan["fixed_g0_candidate_root_candidate_release_identity"]
        or item.get("accepted_candidate_release_sha256")
        != plan["fixed_g0_candidate_root_candidate_release_sha256"]
        or replay_identity != plan["fixed_g0_replay_receipt_identity"]
        or item.get("catalog_replay_receipt_sha256")
        != plan["fixed_g0_replay_receipt_sha256"]
        or catalog_identity != plan["catalog_release_identity"]
        or item.get("catalog_release_sha256") != plan["catalog_release_sha256"]
        or item.get("component_successor_implementation_measurements_sha256")
        != canonical_sha256(measurements)
        or v1_receipt["fixed_g0_replay_receipt_identity"] != replay_identity
        or v1_receipt["catalog_release_identity"] != catalog_identity
        or v1_receipt["accepted_candidate_release_identity"] != candidate_identity
        or v1_receipt["upstream_source_release_identity"]
        != plan["upstream_source_release_identity"]
        or v1_receipt["producer_id"] != plan["producer_id"]
        or v1_receipt["producer_release_id"] != plan["producer_release_id"]
        or v1_receipt["producer_namespace"] != plan["producer_namespace"]
        or item.get("component_publication_receipt_sha256")
        != v1_receipt["component_publication_receipt_sha256"]
        or item.get("producer_release_identity")
        != v1_receipt["producer_release_identity"]
        or item.get("producer_release_sha256")
        != v1_receipt["producer_release_sha256"]
        or any(item.get(field) is not False for field in fixed_false)
        or any(item.get(field) is not True for field in fixed_true)
    ):
        _fail("outer-candidate component receipt binding differs")
    for field in (
        "fixed_g0_candidate_authority_root_sha256",
        "catalog_recovery_outer_attestation_sha256",
        "catalog_inner_object_manifest_sha256",
        "accepted_candidate_release_sha256",
        "catalog_replay_receipt_sha256",
        "catalog_release_sha256",
    ):
        _digest(item.get(field), label=field)
    _commit(
        item.get("capture_plan_observed_commit_sha"),
        label="capture-plan observed commit",
    )
    _commit(
        item.get("component_successor_implementation_commit_sha"),
        label="component successor implementation commit",
    )
    if item.get("catalog_inner_object_count") != 110:
        _fail("catalog inner object count differs")
    normalized = dict(item)
    normalized.update({
        "capture_plan": plan,
        "fixed_g0_candidate_authority_root_identity": root_identity,
        "catalog_recovery_outer_identity": outer_identity,
        "catalog_recovery_candidate_binding": binding,
        "accepted_candidate_release_identity": candidate_identity,
        "catalog_replay_receipt_identity": replay_identity,
        "catalog_release_identity": catalog_identity,
        "component_successor_implementation_measurements": measurements,
        "component_publication_receipt": v1_receipt,
        "outer_candidate_component_publication_receipt_sha256": retained,
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("outer-candidate component receipt canonical replay differs")
    return normalized


def publish_all_54_component_release_outer_candidate_authority_v3(
    *,
    candidate_authority_root_identity: Mapping[str, object],
    capture_plan: Mapping[str, object],
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Publish root-last from only the candidate root and tracked v3 plan."""

    plan, plan_commit, adapter_raw = _tracked_plan_and_adapter_lock(
        capture_plan,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    requested_root = _identity(
        candidate_authority_root_identity,
        label="requested candidate-authority v2 root",
    )
    if requested_root != plan["fixed_g0_candidate_authority_root_identity"]:
        _fail("candidate root differs from tracked capture plan before reopen")
    _shallow_reopen_candidate_root_before_inner(
        root_identity=requested_root,
        plan=plan,
        read_exact=read_exact,
    )
    reopened, binding = _open_candidate(
        root_identity=requested_root,
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    _require_plan_candidate_equality(plan=plan, binding=binding)
    _deep_validate_plan(
        plan=plan,
        adapter_raw=adapter_raw,
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    inner = _derive_inner_inputs(
        binding=binding, reopened=reopened, read_exact=read_exact
    )
    implementation_commit, measurements = _measure_implementation(
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    try:
        result = publication_v1.publish_all_54_component_release_v1(
            producer_id=str(plan["producer_id"]),
            producer_release_id=str(plan["producer_release_id"]),
            producer_namespace=str(plan["producer_namespace"]),
            fixed_g0_replay_receipt=inner["receipt"],
            fixed_g0_replay_receipt_identity=inner["receipt_identity"],
            catalog_release=inner["catalog_release"],
            catalog_release_identity=inner["catalog_release_identity"],
            structural_catalogs=inner["structural_catalogs"],
            accepted_candidate_release=inner["candidate_release"],
            accepted_candidate_release_identity=inner[
                "candidate_release_identity"
            ],
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
            producer_code_identity=plan["component_producer_code_identity"],
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    compatibility = _compatibility_binding(binding=binding)
    v1_receipt, panel = _validate_v1_result(
        result, binding=compatibility, reopened=reopened
    )
    receipt = _build_receipt(
        plan=plan,
        plan_commit=plan_commit,
        binding=binding,
        implementation_commit=implementation_commit,
        implementation_measurements=measurements,
        v1_receipt=v1_receipt,
    )
    provisional = {
        "publication_receipt": receipt,
        "component_publication_result": {
            "publication_receipt": v1_receipt,
            "offline_panel": panel,
        },
    }
    return validate_component_publication_against_outer_candidate_authority_v3(
        provisional,
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )


def validate_component_publication_against_outer_candidate_authority_v3(
    value: object,
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Exact-reopen candidate, plan, and every durable v1 component object."""

    result = _mapping(value, label="outer-candidate component result")
    if set(result) != {"publication_receipt", "component_publication_result"}:
        _fail("outer-candidate component result fields differ")
    receipt = validate_component_publication_outer_candidate_authority_receipt_v3(
        result["publication_receipt"]
    )
    plan, _, adapter_raw = _tracked_plan_and_adapter_lock(
        receipt["capture_plan"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        bound_plan_commit_sha=str(receipt["capture_plan_observed_commit_sha"]),
    )
    _shallow_reopen_candidate_root_before_inner(
        root_identity=receipt["fixed_g0_candidate_authority_root_identity"],
        plan=plan,
        read_exact=read_exact,
    )
    reopened, binding = _open_candidate(
        root_identity=receipt["fixed_g0_candidate_authority_root_identity"],
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    _require_plan_candidate_equality(plan=plan, binding=binding)
    compatibility = _compatibility_binding(binding=binding)
    for field, expected in compatibility.items():
        if receipt.get(field) != expected:
            _fail(f"component receipt exact {field} differs")
    _deep_validate_plan(
        plan=plan,
        adapter_raw=adapter_raw,
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    implementation_commit, measurements = _measure_implementation(
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        bound_commit_sha=str(
            receipt["component_successor_implementation_commit_sha"]
        ),
    )
    if (
        implementation_commit
        != receipt["component_successor_implementation_commit_sha"]
        or measurements
        != receipt["component_successor_implementation_measurements"]
    ):
        _fail("component successor implementation binding differs")
    component_result = _mapping(
        result["component_publication_result"],
        label="nested v1 component publication result",
    )
    try:
        panel = durable_v2._durable_validate_full_result(
            receipt=receipt,
            component_result=component_result,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error(
            f"full v1 durable component replay failed: {exc}"
        ) from exc
    return {
        "publication_receipt": receipt,
        "component_publication_result": {
            "publication_receipt": receipt["component_publication_receipt"],
            "offline_panel": panel,
        },
    }


__all__ = [
    "COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS",
    "CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error",
    "PUBLICATION_RECEIPT_SCHEMA",
    "publish_all_54_component_release_outer_candidate_authority_v3",
    "validate_component_publication_against_outer_candidate_authority_v3",
    "validate_component_publication_outer_candidate_authority_receipt_v3",
]
