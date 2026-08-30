"""Outer-bound successor to the R6 matchup capture-plan lock.

The historical capture-plan builders accepted independently supplied catalog
receipt/release bodies and an older candidate root.  This successor exposes
only the terminal fixed-G0 candidate-authority-v2 root as catalog/candidate
authority.  It deep-reopens that root first, derives compatibility bodies from
identities carried by the root, and then projects into the frozen v1 capture
plan.  The successor binds the recovery outer and its own clean implementation
bytes and can be securely reopened from a tracked lock.

The lock is still outcome-blind and non-authoritative for capture execution,
source publication, scoring, retrieval, graph mutation, promotion, or
production policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate,
)
from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as capture_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


CAPTURE_PLAN_SCHEMA: Final = (
    "corpus-r6-matchup-capture-plan/outer-candidate-authority-v3"
)
CAPTURE_PLAN_ID: Final = (
    "20260830-r6-matchup-source-v2-outer-candidate-authority"
)
CAPTURE_PLAN_SCOPE: Final = (
    "fixed-g0-recovery-outer-and-candidate-v2-rooted-lock-for-finalization"
)
CAPTURE_PLAN_LOCK_PATH: Final = (
    "reports/corpus-r6-matchup-runs/"
    "20260830-r6-matchup-source-v2/"
    "capture-plan-outer-candidate-authority-v3-lock.json"
)
CAPTURE_PLAN_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_capture_plan_outer_candidate_authority_v3.py"
)
CAPTURE_V1_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_capture_plan_v1.py"
)
CANDIDATE_RELEASE_V2_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_fixed_g0_candidate_authority_release_v2.py"
)
CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS: Final = tuple(sorted((
    CAPTURE_PLAN_MODULE_PATH,
    CAPTURE_V1_MODULE_PATH,
    CANDIDATE_RELEASE_V2_MODULE_PATH,
    *capture_v1.IMPLEMENTATION_PATHS,
)))

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_CANDIDATE_ROOT_URI = re.compile(
    rf"^gs://{re.escape(candidate.OUTPUT_BUCKET)}/"
    rf"{re.escape(candidate.OUTPUT_NAMESPACE)}/"
    r"[a-z0-9][a-z0-9-]{7,80}/"
    rf"{re.escape(candidate.ROOT_FILENAME)}$"
)

_SUCCESSOR_FIELDS: Final = frozenset({
    "catalog_recovery_outer_identity",
    "catalog_recovery_outer_attestation_sha256",
    "catalog_recovery_candidate_binding",
    "catalog_inner_object_count",
    "catalog_inner_object_manifest_sha256",
    "fixed_g0_candidate_authority_root_identity",
    "fixed_g0_candidate_authority_root_sha256",
    "fixed_g0_candidate_authority_schema",
    "fixed_g0_candidate_root_candidate_release_identity",
    "fixed_g0_candidate_root_candidate_release_sha256",
    "capture_successor_implementation_commit_sha",
    "capture_successor_implementation_measurements",
    "capture_successor_implementation_measurements_sha256",
    "candidate_authority_exact_reopened",
    "candidate_authority_v1_root_accepted",
    "candidate_authority_structure_only_validation_authority",
    "caller_catalog_replay_receipt_body_allowed",
    "caller_catalog_replay_receipt_identity_allowed",
    "caller_catalog_release_body_allowed",
    "caller_catalog_release_identity_allowed",
    "caller_candidate_release_body_allowed",
    "caller_candidate_release_identity_allowed",
    "inner_compatibility_inputs_derived_from_candidate_root",
    "catalog_recovery_outer_read_before_any_inner_read",
    "capture_successor_remote_exact_read_performed",
})
# The v1 builder accepted caller-supplied bodies and therefore truthfully
# recorded ``lock_builder_cloud_read_performed=false``.  This successor opens
# the candidate root and its predecessors itself.  Carrying that old field
# forward would make the v3 lock contradict its own exact-reopen evidence, so
# it exists only in the reconstructed v1 compatibility projection below.
_V1_PROJECTION_ONLY_FIELDS: Final = frozenset({
    "lock_builder_cloud_read_performed",
})
_PLAN_FIELDS: Final = frozenset({
    *(capture_v1._PLAN_FIELDS - _V1_PROJECTION_ONLY_FIELDS),
    *_SUCCESSOR_FIELDS,
})
_MEASUREMENT_FIELDS: Final = frozenset({"relative_path", "sha256", "bytes"})

ReadExact = candidate.ReadExact
GitHead = candidate.GitHead
GitBlob = candidate.GitBlob
GitStatus = candidate.GitStatus
ReadGitBlob = capture_v1.ReadGitBlob
SecureReadCurrent = capture_v1.SecureReadCurrent


class CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(ValueError):
    """The outer-candidate-rooted capture plan failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
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
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
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


def _with_hash(value: Mapping[str, object]) -> dict[str, object]:
    body = dict(value)
    if "capture_plan_sha256" in body:
        _fail("capture-plan self-hash must not be supplied")
    body["capture_plan_sha256"] = canonical_sha256(body)
    return body


def _exact_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            f"{label} exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            f"{label} must be canonical JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    return body, identity


def _runtime_path(repository_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
        _fail(f"capture implementation path differs: {relative_path}")
    path = repository_root / relative
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            f"capture implementation path is absent: {relative_path}"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        _fail(f"capture implementation path differs: {relative_path}")
    return path


def _measure_implementation(
    *, repository_root: Path, git_head: GitHead, git_blob: GitBlob,
    git_status: GitStatus, bound_commit_sha: str | None = None,
) -> tuple[str, list[dict[str, object]]]:
    if (
        not isinstance(repository_root, Path)
        or not repository_root.is_absolute()
        or not callable(git_head)
        or not callable(git_blob)
        or not callable(git_status)
    ):
        _fail("capture implementation Git boundary differs")
    try:
        root = repository_root.resolve(strict=True)
        current_head = _commit(
            git_head(root), label="capture implementation current HEAD"
        )
        commit = (
            current_head if bound_commit_sha is None
            else _commit(bound_commit_sha, label="capture implementation commit")
        )
        status_raw = git_status(root, CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS)
    except CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            "capture implementation Git resolution failed"
        ) from exc
    if type(status_raw) is not bytes or status_raw != b"":
        _fail("capture implementation files must be tracked-clean")
    measurements: list[dict[str, object]] = []
    for relative_path in CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS:
        path = _runtime_path(root, relative_path)
        try:
            raw = path.read_bytes()
            committed = git_blob(root, commit, relative_path)
        except Exception as exc:
            raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
                f"capture implementation read failed: {relative_path}"
            ) from exc
        if type(committed) is not bytes or committed != raw:
            _fail(f"capture implementation code drift: {relative_path}")
        measurements.append({
            "relative_path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return commit, measurements


def _normalize_measurements(value: object) -> list[dict[str, object]]:
    rows = [
        _mapping(row, label=f"capture implementation measurement[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(value, label="capture implementation measurements")
        )
    ]
    if len(rows) != len(CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS):
        _fail("capture implementation measurement count differs")
    normalized: list[dict[str, object]] = []
    for ordinal, row in enumerate(rows):
        if set(row) != set(_MEASUREMENT_FIELDS):
            _fail(f"capture implementation measurement[{ordinal}] fields differ")
        path = row.get("relative_path")
        size = row.get("bytes")
        if (
            path != CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS[ordinal]
            or type(size) is not int
            or size < 1
        ):
            _fail(f"capture implementation measurement[{ordinal}] differs")
        normalized.append({
            "relative_path": path,
            "sha256": _digest(
                row.get("sha256"),
                label=f"capture implementation measurement[{ordinal}] SHA",
            ),
            "bytes": size,
        })
    return normalized


def _validated_candidate_recovery_binding(
    value: object,
    *,
    outer_identity: Mapping[str, object],
    outer_sha256: str,
    replay_receipt_identity: Mapping[str, object],
    replay_receipt_sha256: str,
    catalog_release_identity: Mapping[str, object],
    catalog_release_sha256: str,
    inner_object_count: int,
    inner_object_manifest_sha256: str,
) -> dict[str, object]:
    """Validate every candidate-binding field consumed by this successor."""

    binding = _mapping(value, label="candidate recovery/code binding")
    retained_sha = _digest(
        binding.get("candidate_implementation_binding_sha256"),
        label="candidate recovery/code binding SHA",
    )
    unhashed = dict(binding)
    del unhashed["candidate_implementation_binding_sha256"]
    recovery_binding = _mapping(
        binding.get("catalog_recovery_code_and_lock_binding"),
        label="catalog recovery code/lock binding",
    )
    if (
        canonical_sha256(unhashed) != retained_sha
        or _identity(
            binding.get("catalog_recovery_outer_identity"),
            label="candidate binding catalog recovery outer",
        ) != dict(outer_identity)
        or binding.get("catalog_recovery_outer_attestation_sha256")
        != outer_sha256
        or _identity(
            binding.get("catalog_inner_replay_receipt_identity"),
            label="candidate binding replay receipt",
        ) != dict(replay_receipt_identity)
        or binding.get("catalog_inner_replay_receipt_sha256")
        != replay_receipt_sha256
        or _identity(
            binding.get("catalog_inner_release_identity"),
            label="candidate binding catalog release",
        ) != dict(catalog_release_identity)
        or binding.get("catalog_inner_release_sha256")
        != catalog_release_sha256
        or binding.get("catalog_inner_object_count") != inner_object_count
        or binding.get("catalog_inner_object_manifest_sha256")
        != inner_object_manifest_sha256
        or _identity(
            recovery_binding.get("outer_attestation_identity"),
            label="catalog recovery code/lock outer",
        ) != dict(outer_identity)
        or recovery_binding.get("outer_attestation_sha256") != outer_sha256
    ):
        _fail("candidate recovery/code binding projection differs")
    return binding


def _require_implementation_projection(
    *,
    base: Mapping[str, object],
    implementation_commit: str,
    implementation_measurements: Sequence[Mapping[str, object]],
) -> None:
    """Keep the inherited v1 code identity equal to the measured successor."""

    measurements = _normalize_measurements(implementation_measurements)
    by_path = {str(row["relative_path"]): row for row in measurements}
    inherited = [by_path[path] for path in capture_v1.IMPLEMENTATION_PATHS]
    if (
        base.get("implementation_commit_sha") != implementation_commit
        or base.get("implementation_measurements") != inherited
    ):
        _fail("v1 implementation projection differs from capture successor")


def _candidate_binding(
    reopened: candidate.ReopenedFixedG0CandidateAuthorityV2,
    *, expected_root_identity: object,
) -> dict[str, object]:
    root = _mapping(reopened.root, label="candidate-authority v2 root")
    root_identity = _identity(
        reopened.root_identity, label="candidate-authority v2 root"
    )
    expected_identity = _identity(
        expected_root_identity, label="expected candidate-authority v2 root"
    )
    candidate_release = _mapping(
        reopened.candidate_release, label="accepted candidate release"
    )
    candidate_release_identity = _identity(
        reopened.candidate_release_identity,
        label="accepted candidate release",
    )
    outer_identity = _identity(
        root.get("catalog_recovery_outer_identity"),
        label="candidate catalog recovery outer",
    )
    outer_sha = _digest(
        root.get("catalog_recovery_outer_attestation_sha256"),
        label="candidate catalog recovery outer SHA",
    )
    root_sha = _digest(
        root.get("candidate_authority_release_sha256"),
        label="candidate-authority v2 root SHA",
    )
    candidate_release_sha = _digest(
        candidate_release.get("accepted_candidate_release_sha256"),
        label="accepted candidate release SHA",
    )
    root_unhashed = dict(root)
    del root_unhashed["candidate_authority_release_sha256"]
    root_raw = canonical_json_bytes(root)
    replay_receipt_identity = _identity(
        root.get("catalog_replay_receipt_identity"),
        label="candidate-root catalog replay receipt",
    )
    catalog_release_identity = _identity(
        root.get("catalog_release_identity"),
        label="candidate-root catalog release",
    )
    binding = _validated_candidate_recovery_binding(
        root.get("catalog_recovery_candidate_binding"),
        outer_identity=outer_identity,
        outer_sha256=outer_sha,
        replay_receipt_identity=replay_receipt_identity,
        replay_receipt_sha256=_digest(
            root.get("catalog_replay_receipt_sha256"),
            label="candidate-root catalog replay receipt SHA",
        ),
        catalog_release_identity=catalog_release_identity,
        catalog_release_sha256=_digest(
            root.get("catalog_release_sha256"),
            label="candidate-root catalog release SHA",
        ),
        inner_object_count=110,
        inner_object_manifest_sha256=_digest(
            root.get("catalog_inner_object_manifest_sha256"),
            label="candidate-root catalog inner manifest SHA",
        ),
    )
    if (
        root_identity != expected_identity
        or _CANDIDATE_ROOT_URI.fullmatch(str(root_identity["uri"])) is None
        or root_identity["sha256"] != sha256(root_raw).hexdigest()
        or root_identity["bytes"] != len(root_raw)
        or root_sha != canonical_sha256(root_unhashed)
        or root.get("schema_version") != candidate.RELEASE_SCHEMA
        or root.get("target_uri") != root_identity["uri"]
        or root.get("catalog_recovery_outer_identity") != outer_identity
        or binding.get("catalog_recovery_outer_identity") != outer_identity
        or binding.get("catalog_recovery_outer_attestation_sha256") != outer_sha
        or root.get("candidate_release_identity") != candidate_release_identity
        or root.get("candidate_release_sha256") != candidate_release_sha
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("authoritative_reopen_required") is not True
        or root.get("structure_only_validation_authority") is not False
        or root.get("catalog_recovery_outer_read_before_any_inner_read") is not True
        or root.get("complete") is not True
        or root.get("legacy_root_published") is not False
        or root.get("published_total_object_count") != candidate.TOTAL_OBJECT_COUNT
    ):
        _fail("candidate-authority v2 root binding differs")
    return {
        "root": root,
        "root_identity": root_identity,
        "root_sha256": root_sha,
        "candidate_release": candidate_release,
        "candidate_release_identity": candidate_release_identity,
        "candidate_release_sha256": candidate_release_sha,
        "outer_identity": outer_identity,
        "outer_sha256": outer_sha,
        "recovery_binding": binding,
    }


def _open_candidate(
    *, candidate_authority_root_identity: Mapping[str, object],
    repository_root: Path, read_exact: ReadExact, git_head: GitHead,
    git_blob: GitBlob, git_status: GitStatus,
) -> tuple[candidate.ReopenedFixedG0CandidateAuthorityV2, dict[str, object]]:
    try:
        reopened = candidate.reopen_fixed_g0_candidate_authority_release_v2(
            candidate_authority_root_identity,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            f"candidate-authority v2 exact reopen failed: {exc}"
        ) from exc
    return reopened, _candidate_binding(
        reopened, expected_root_identity=candidate_authority_root_identity
    )


def _derived_inner_bodies(
    *, binding: Mapping[str, object], read_exact: ReadExact,
) -> dict[str, object]:
    root = _mapping(binding.get("root"), label="candidate root")
    receipt, receipt_identity = _exact_json(
        root.get("catalog_replay_receipt_identity"),
        read_exact=read_exact,
        label="outer-derived catalog replay receipt",
    )
    catalog_release, catalog_release_identity = _exact_json(
        root.get("catalog_release_identity"),
        read_exact=read_exact,
        label="outer-derived catalog release",
    )
    if (
        receipt.get("replay_receipt_sha256")
        != root.get("catalog_replay_receipt_sha256")
        or catalog_release.get("release_sha256")
        != root.get("catalog_release_sha256")
        or receipt.get("catalog_release_identity") != catalog_release_identity
    ):
        _fail("candidate-root-derived catalog compatibility binding differs")
    return {
        "receipt": receipt,
        "receipt_identity": receipt_identity,
        "catalog_release": catalog_release,
        "catalog_release_identity": catalog_release_identity,
    }


def _base_projection(value: Mapping[str, object]) -> dict[str, object]:
    body = {
        key: nested for key, nested in value.items()
        if key not in _SUCCESSOR_FIELDS and key != "capture_plan_sha256"
    }
    body.update({
        "schema_version": capture_v1.CAPTURE_PLAN_SCHEMA,
        "capture_plan_id": capture_v1.CAPTURE_PLAN_ID,
        "capture_plan_scope": capture_v1.CAPTURE_PLAN_SCOPE,
        "capture_plan_lock_relative_path": capture_v1.CAPTURE_PLAN_LOCK_PATH,
        # This is a property of the in-memory v1 compatibility builder only;
        # the enclosing v3 operation has already performed remote reads.
        "lock_builder_cloud_read_performed": False,
    })
    body["capture_plan_sha256"] = capture_v1.canonical_sha256(body)
    try:
        return capture_v1.validate_capture_plan_lock_v1(body)
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            f"v1 capture-plan projection differs: {exc}"
        ) from exc


def _upgrade(
    base_plan_value: Mapping[str, object], *, binding: Mapping[str, object],
    implementation_commit: str,
    implementation_measurements: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    try:
        base = capture_v1.validate_capture_plan_lock_v1(base_plan_value)
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    if (
        base["fixed_g0_replay_receipt_identity"]
        != binding["root"]["catalog_replay_receipt_identity"]
        or base["catalog_release_identity"]
        != binding["root"]["catalog_release_identity"]
        or base["accepted_candidate_release_identity"]
        != binding["candidate_release_identity"]
        or base["accepted_candidate_release_sha256"]
        != binding["candidate_release_sha256"]
    ):
        _fail("base capture plan differs from candidate-authority v2 root")
    measurements = _normalize_measurements(implementation_measurements)
    _require_implementation_projection(
        base=base,
        implementation_commit=implementation_commit,
        implementation_measurements=measurements,
    )
    body = {
        key: nested for key, nested in base.items()
        if key not in {"capture_plan_sha256", *_V1_PROJECTION_ONLY_FIELDS}
    }
    body.update({
        "schema_version": CAPTURE_PLAN_SCHEMA,
        "capture_plan_id": CAPTURE_PLAN_ID,
        "capture_plan_scope": CAPTURE_PLAN_SCOPE,
        "capture_plan_lock_relative_path": CAPTURE_PLAN_LOCK_PATH,
        "catalog_recovery_outer_identity": binding["outer_identity"],
        "catalog_recovery_outer_attestation_sha256": binding["outer_sha256"],
        "catalog_recovery_candidate_binding": binding["recovery_binding"],
        "catalog_inner_object_count": binding["root"][
            "catalog_inner_object_count"
        ],
        "catalog_inner_object_manifest_sha256": binding["root"][
            "catalog_inner_object_manifest_sha256"
        ],
        "fixed_g0_candidate_authority_root_identity": binding["root_identity"],
        "fixed_g0_candidate_authority_root_sha256": binding["root_sha256"],
        "fixed_g0_candidate_authority_schema": candidate.RELEASE_SCHEMA,
        "fixed_g0_candidate_root_candidate_release_identity": binding[
            "candidate_release_identity"
        ],
        "fixed_g0_candidate_root_candidate_release_sha256": binding[
            "candidate_release_sha256"
        ],
        "capture_successor_implementation_commit_sha": implementation_commit,
        "capture_successor_implementation_measurements": measurements,
        "capture_successor_implementation_measurements_sha256": (
            canonical_sha256(measurements)
        ),
        "candidate_authority_exact_reopened": True,
        "candidate_authority_v1_root_accepted": False,
        "candidate_authority_structure_only_validation_authority": False,
        "caller_catalog_replay_receipt_body_allowed": False,
        "caller_catalog_replay_receipt_identity_allowed": False,
        "caller_catalog_release_body_allowed": False,
        "caller_catalog_release_identity_allowed": False,
        "caller_candidate_release_body_allowed": False,
        "caller_candidate_release_identity_allowed": False,
        "inner_compatibility_inputs_derived_from_candidate_root": True,
        "catalog_recovery_outer_read_before_any_inner_read": True,
        "capture_successor_remote_exact_read_performed": True,
    })
    return validate_capture_plan_lock_v3(_with_hash(body))


def validate_capture_plan_lock_v3(value: object) -> dict[str, object]:
    """Validate the tracked structure; remote authority still requires reopen."""
    item = _mapping(value, label="outer-candidate capture plan")
    if set(item) != set(_PLAN_FIELDS):
        _fail("outer-candidate capture-plan fields differ")
    retained_sha = _digest(
        item.get("capture_plan_sha256"), label="capture-plan self-hash"
    )
    unhashed = dict(item)
    del unhashed["capture_plan_sha256"]
    if canonical_sha256(unhashed) != retained_sha:
        _fail("outer-candidate capture-plan self-hash differs")
    base = _base_projection(item)
    root_identity = _identity(
        item.get("fixed_g0_candidate_authority_root_identity"),
        label="candidate-authority v2 root",
    )
    outer_identity = _identity(
        item.get("catalog_recovery_outer_identity"),
        label="catalog recovery outer",
    )
    binding = _mapping(
        item.get("catalog_recovery_candidate_binding"),
        label="candidate recovery/code binding",
    )
    candidate_release_identity = _identity(
        item.get("fixed_g0_candidate_root_candidate_release_identity"),
        label="candidate root release",
    )
    measurements = _normalize_measurements(
        item.get("capture_successor_implementation_measurements")
    )
    replay_receipt_identity = _identity(
        base.get("fixed_g0_replay_receipt_identity"),
        label="projected replay receipt",
    )
    catalog_release_identity = _identity(
        base.get("catalog_release_identity"),
        label="projected catalog release",
    )
    binding = _validated_candidate_recovery_binding(
        binding,
        outer_identity=outer_identity,
        outer_sha256=_digest(
            item.get("catalog_recovery_outer_attestation_sha256"),
            label="catalog recovery outer SHA",
        ),
        replay_receipt_identity=replay_receipt_identity,
        replay_receipt_sha256=_digest(
            base.get("fixed_g0_replay_receipt_sha256"),
            label="projected replay receipt SHA",
        ),
        catalog_release_identity=catalog_release_identity,
        catalog_release_sha256=_digest(
            base.get("catalog_release_sha256"),
            label="projected catalog release SHA",
        ),
        inner_object_count=110,
        inner_object_manifest_sha256=_digest(
            item.get("catalog_inner_object_manifest_sha256"),
            label="catalog inner manifest SHA",
        ),
    )
    implementation_commit = _commit(
        item.get("capture_successor_implementation_commit_sha"),
        label="capture successor implementation commit",
    )
    _require_implementation_projection(
        base=base,
        implementation_commit=implementation_commit,
        implementation_measurements=measurements,
    )
    if (
        item.get("schema_version") != CAPTURE_PLAN_SCHEMA
        or item.get("capture_plan_id") != CAPTURE_PLAN_ID
        or item.get("capture_plan_scope") != CAPTURE_PLAN_SCOPE
        or item.get("capture_plan_lock_relative_path") != CAPTURE_PLAN_LOCK_PATH
        or _CANDIDATE_ROOT_URI.fullmatch(str(root_identity["uri"])) is None
        or item.get("fixed_g0_candidate_authority_schema")
        != candidate.RELEASE_SCHEMA
        or binding.get("catalog_recovery_outer_identity") != outer_identity
        or binding.get("catalog_recovery_outer_attestation_sha256")
        != item.get("catalog_recovery_outer_attestation_sha256")
        or item.get("fixed_g0_candidate_root_candidate_release_identity")
        != candidate_release_identity
        or candidate_release_identity != base["accepted_candidate_release_identity"]
        or item.get("fixed_g0_candidate_root_candidate_release_sha256")
        != base["accepted_candidate_release_sha256"]
        or item.get("capture_successor_implementation_measurements_sha256")
        != canonical_sha256(measurements)
        or item.get("candidate_authority_exact_reopened") is not True
        or item.get("candidate_authority_v1_root_accepted") is not False
        or item.get("candidate_authority_structure_only_validation_authority")
        is not False
        or item.get("caller_catalog_replay_receipt_body_allowed") is not False
        or item.get("caller_catalog_replay_receipt_identity_allowed") is not False
        or item.get("caller_catalog_release_body_allowed") is not False
        or item.get("caller_catalog_release_identity_allowed") is not False
        or item.get("caller_candidate_release_body_allowed") is not False
        or item.get("caller_candidate_release_identity_allowed") is not False
        or item.get("inner_compatibility_inputs_derived_from_candidate_root")
        is not True
        or item.get("catalog_recovery_outer_read_before_any_inner_read") is not True
        or item.get("capture_successor_remote_exact_read_performed") is not True
    ):
        _fail("outer-candidate capture-plan binding differs")
    _digest(
        item.get("catalog_recovery_outer_attestation_sha256"),
        label="catalog recovery outer SHA",
    )
    _digest(
        item.get("fixed_g0_candidate_authority_root_sha256"),
        label="candidate-authority v2 root SHA",
    )
    _digest(
        item.get("fixed_g0_candidate_root_candidate_release_sha256"),
        label="candidate release SHA",
    )
    _digest(
        item.get("catalog_inner_object_manifest_sha256"),
        label="catalog inner manifest SHA",
    )
    if (
        type(item.get("catalog_inner_object_count")) is not int
        or item["catalog_inner_object_count"] != 110
    ):
        _fail("catalog inner object count differs")
    return item


def build_capture_plan_lock_v3(
    *, adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    candidate_authority_root_identity: Mapping[str, object],
    repository_root: Path, read_exact: ReadExact,
    git_head: GitHead, git_blob: GitBlob, git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_id: str, producer_release_id: str, producer_namespace: str,
) -> dict[str, object]:
    """Build from the candidate-v2 root; no independent inner input exists."""
    _, binding = _open_candidate(
        candidate_authority_root_identity=candidate_authority_root_identity,
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    inner = _derived_inner_bodies(binding=binding, read_exact=read_exact)
    implementation_commit, measurements = _measure_implementation(
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    by_path = {str(row["relative_path"]): row for row in measurements}
    base_measurements = [by_path[path] for path in capture_v1.IMPLEMENTATION_PATHS]
    try:
        base = capture_v1.build_capture_plan_lock_v1(
            adapter_final_release_lock_commit_sha=(
                adapter_final_release_lock_commit_sha
            ),
            adapter_final_release_lock_raw=adapter_final_release_lock_raw,
            fixed_g0_replay_receipt=inner["receipt"],
            fixed_g0_replay_receipt_identity=inner["receipt_identity"],
            catalog_release=inner["catalog_release"],
            catalog_release_identity=inner["catalog_release_identity"],
            accepted_candidate_release=binding["candidate_release"],
            accepted_candidate_release_identity=binding[
                "candidate_release_identity"
            ],
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
            implementation_commit_sha=implementation_commit,
            implementation_measurements=base_measurements,
            producer_id=producer_id,
            producer_release_id=producer_release_id,
            producer_namespace=producer_namespace,
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    return _upgrade(
        base,
        binding=binding,
        implementation_commit=implementation_commit,
        implementation_measurements=measurements,
    )


def validate_capture_plan_against_prerequisites_v3(
    value: object,
    *, repository_root: Path, read_exact: ReadExact,
    git_head: GitHead, git_blob: GitBlob, git_status: GitStatus,
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Deep-reopen candidate v2, derive inner bodies, and byte-rebuild."""
    plan = validate_capture_plan_lock_v3(value)
    _, binding = _open_candidate(
        candidate_authority_root_identity=plan[
            "fixed_g0_candidate_authority_root_identity"
        ],
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if (
        binding["outer_identity"] != plan["catalog_recovery_outer_identity"]
        or binding["outer_sha256"]
        != plan["catalog_recovery_outer_attestation_sha256"]
        or binding["root_sha256"]
        != plan["fixed_g0_candidate_authority_root_sha256"]
    ):
        _fail("capture plan and candidate authority outer/root differ")
    inner = _derived_inner_bodies(binding=binding, read_exact=read_exact)
    implementation_commit, measurements = _measure_implementation(
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        bound_commit_sha=str(plan["capture_successor_implementation_commit_sha"]),
    )
    if measurements != plan["capture_successor_implementation_measurements"]:
        _fail("capture successor implementation measurements differ")
    base = _base_projection(plan)
    try:
        rebuilt_base = capture_v1.validate_capture_plan_against_prerequisites_v1(
            base,
            adapter_final_release_lock_commit_sha=(
                adapter_final_release_lock_commit_sha
            ),
            adapter_final_release_lock_raw=adapter_final_release_lock_raw,
            fixed_g0_replay_receipt=inner["receipt"],
            fixed_g0_replay_receipt_identity=inner["receipt_identity"],
            catalog_release=inner["catalog_release"],
            catalog_release_identity=inner["catalog_release_identity"],
            accepted_candidate_release=binding["candidate_release"],
            accepted_candidate_release_identity=binding[
                "candidate_release_identity"
            ],
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    rebuilt = _upgrade(
        rebuilt_base,
        binding=binding,
        implementation_commit=implementation_commit,
        implementation_measurements=measurements,
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(plan):
        _fail("capture plan differs from exact-opened candidate authority")
    return rebuilt


def reopen_capture_plan_lock_from_git_v3(
    *, plan_commit_sha: str, plan_file_sha256: str, plan_file_bytes: int,
    read_git_blob: ReadGitBlob, secure_read_current: SecureReadCurrent,
    repository_clean: bool,
) -> dict[str, object]:
    """Securely reopen the tracked v3 lock and all inherited local evidence."""
    if repository_clean is not True:
        _fail("capture-plan replay requires a clean repository")
    commit = _commit(plan_commit_sha, label="capture-plan commit")
    expected_sha = _digest(plan_file_sha256, label="capture-plan file SHA")
    if type(plan_file_bytes) is not int or plan_file_bytes < 1:
        _fail("capture-plan file bytes differ")
    try:
        raw = capture_v1._read_git_blob_exact(
            commit_sha=commit,
            path=CAPTURE_PLAN_LOCK_PATH,
            expected_sha256=expected_sha,
            expected_bytes=plan_file_bytes,
            read_git_blob=read_git_blob,
            secure_read_current=secure_read_current,
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            "tracked capture-plan lock must be canonical JSON"
        ) from exc
    plan = validate_capture_plan_lock_v3(parsed)
    if raw != canonical_json_bytes(plan) + b"\n":
        _fail("tracked capture-plan lock must be canonical JSON plus one newline")
    implementation_commit = str(
        plan["capture_successor_implementation_commit_sha"]
    )
    for row_value in plan["capture_successor_implementation_measurements"]:
        row = _mapping(row_value, label="capture implementation measurement")
        try:
            capture_v1._read_git_blob_exact(
                commit_sha=implementation_commit,
                path=str(row["relative_path"]),
                expected_sha256=str(row["sha256"]),
                expected_bytes=int(row["bytes"]),
                read_git_blob=read_git_blob,
                secure_read_current=secure_read_current,
            )
        except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
            raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
                str(exc)
            ) from exc
    # Preserve the v1 tracked-reopen boundary.  Projecting to v1 and merely
    # validating its fields is not enough: its adapter-final lock and accepted
    # G0 lock are historical Git blobs and must still be exact-opened here.
    base = _base_projection(plan)
    final_binding = _mapping(
        base["adapter_final_release_lock_binding"],
        label="adapter final release lock binding",
    )
    try:
        final_raw = capture_v1._read_git_blob_exact(
            commit_sha=str(final_binding["commit_sha"]),
            path=str(final_binding["relative_path"]),
            expected_sha256=str(final_binding["sha256"]),
            expected_bytes=int(final_binding["bytes"]),
            read_git_blob=read_git_blob,
            secure_read_current=secure_read_current,
        )
        final_lock = capture_v1._validate_adapter_final_release_lock_raw(
            final_raw
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    if final_lock["final_release_lock_sha256"] != final_binding[
        "internal_sha256"
    ]:
        _fail("adapter final release lock internal binding differs")
    fixed = capture_v1.fixed_g0_authority_binding_v1()
    try:
        g0_raw = capture_v1._read_git_blob_exact(
            commit_sha=str(fixed["evidence_source_commit_sha"]),
            path=str(fixed["g0_lock_relative_path"]),
            expected_sha256=str(fixed["g0_lock_file_sha256"]),
            expected_bytes=int(fixed["g0_lock_file_bytes"]),
            read_git_blob=read_git_blob,
            secure_read_current=secure_read_current,
        )
        g0 = capture_v1._parse_canonical_json(
            g0_raw,
            label="accepted August-23 G0 lock",
            require_one_newline=True,
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    if g0.get("g0_authority_lock_sha256") != fixed[
        "g0_lock_internal_sha256"
    ]:
        _fail("accepted G0 internal binding differs")
    return plan


__all__ = [
    "CAPTURE_PLAN_ID",
    "CAPTURE_PLAN_LOCK_PATH",
    "CAPTURE_PLAN_SCHEMA",
    "CAPTURE_PLAN_SCOPE",
    "CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS",
    "CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error",
    "build_capture_plan_lock_v3",
    "canonical_json_bytes",
    "canonical_sha256",
    "reopen_capture_plan_lock_from_git_v3",
    "validate_capture_plan_against_prerequisites_v3",
    "validate_capture_plan_lock_v3",
]
