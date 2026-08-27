"""Candidate-authority-rooted successor to the R6 matchup capture plan.

The v1 capture-plan builder accepts a caller-supplied candidate-release body
and identity.  That is adequate structural evidence but it is not proof that
the population is the complete union of the seven accepted Foundry arms.
This successor removes that input seam.  Its public builder accepts only the
terminal fixed-G0 candidate-authority root identity, exact-reopens the root,
all 54 published candidate artifacts and occurrence sidecars, and replays all
fixed-G0 predecessors before projecting the reopened candidate release into
the otherwise unchanged v1 capture plan.

The resulting lock stays non-authoritative for capture, source execution,
scoring, graph mutation, promotion, and production.  Structural validation
alone does not establish candidate authority; the exact reopener below must
be used whenever the plan is consumed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_authority,
)
from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as capture_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


CAPTURE_PLAN_SCHEMA: Final = (
    "corpus-r6-matchup-capture-plan/candidate-authority-v2"
)
CAPTURE_PLAN_ID: Final = (
    "20260826-r6-matchup-source-v2-fixed-g0-candidate-authority"
)
CAPTURE_PLAN_SCOPE: Final = (
    "fixed-g0-candidate-authority-rooted-seven-pack-lock-for-finalization"
)
CAPTURE_PLAN_LOCK_PATH: Final = (
    "reports/corpus-r6-matchup-runs/"
    "20260826-r6-matchup-source-v2/"
    "capture-plan-candidate-authority-v2-lock.json"
)

_SUCCESSOR_FIELDS: Final = frozenset({
    "fixed_g0_candidate_authority_root_identity",
    "fixed_g0_candidate_authority_root_sha256",
    "fixed_g0_candidate_root_candidate_release_identity",
    "fixed_g0_candidate_root_candidate_release_sha256",
    "fixed_g0_candidate_root_exact_reopened",
    "complete_candidate_population_binding_verified",
    "exact_occurrence_provenance_binding_verified",
    "caller_candidate_release_body_allowed",
    "caller_candidate_release_identity_allowed",
    "candidate_authority_exact_reopen_required",
    "candidate_authority_structure_only_authority",
})
_PLAN_FIELDS: Final = frozenset({
    *capture_v1._PLAN_FIELDS,  # same public payload plus the corrected seam
    *_SUCCESSOR_FIELDS,
})
_ROOT_URI = re.compile(
    rf"^gs://{re.escape(candidate_authority.OUTPUT_BUCKET)}/"
    rf"{re.escape(candidate_authority.OUTPUT_NAMESPACE)}/"
    r"[a-z0-9][a-z0-9-]{7,80}/"
    rf"{re.escape(candidate_authority.ROOT_FILENAME)}$"
)

ReadExact = candidate_authority.ReadExact
GitHead = candidate_authority.GitHead
GitBlob = candidate_authority.GitBlob
GitStatus = candidate_authority.GitStatus


class CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(ValueError):
    """The candidate-authority-rooted capture plan failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(message)


def canonical_json_bytes(value: object) -> bytes:
    return source.canonical_json_bytes(value)


def canonical_sha256(value: object) -> str:
    return source.canonical_sha256(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _digest(value: object, *, label: str) -> str:
    try:
        return capture_v1._digest(value, label=label)
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(str(exc)) from exc


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(str(exc)) from exc


def _base_projection(value: Mapping[str, object]) -> dict[str, object]:
    projected = {
        key: item for key, item in value.items()
        if key not in _SUCCESSOR_FIELDS and key != "capture_plan_sha256"
    }
    projected.update({
        "schema_version": capture_v1.CAPTURE_PLAN_SCHEMA,
        "capture_plan_id": capture_v1.CAPTURE_PLAN_ID,
        "capture_plan_scope": capture_v1.CAPTURE_PLAN_SCOPE,
        "capture_plan_lock_relative_path": capture_v1.CAPTURE_PLAN_LOCK_PATH,
    })
    projected["capture_plan_sha256"] = capture_v1.canonical_sha256(projected)
    try:
        return capture_v1.validate_capture_plan_lock_v1(projected)
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(
            f"v1 capture-plan projection differs: {exc}"
        ) from exc


def _authority_binding(
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    *,
    expected_root_identity: Mapping[str, object],
    expected_candidate_release_identity: Mapping[str, object] | None = None,
    expected_candidate_release_sha256: object | None = None,
    expected_catalog_receipt_identity: Mapping[str, object] | None = None,
    expected_catalog_receipt_sha256: object | None = None,
) -> dict[str, object]:
    root_identity = _identity(reopened.root_identity, label="reopened candidate root")
    retained_root_identity = _identity(
        expected_root_identity, label="candidate-authority root identity"
    )
    root = _mapping(reopened.root, label="reopened candidate-authority root")
    candidate_release_identity = _identity(
        reopened.candidate_release_identity,
        label="reopened accepted candidate release",
    )
    candidate_release = _mapping(
        reopened.candidate_release, label="reopened accepted candidate release"
    )
    if (
        root_identity != retained_root_identity
        or _ROOT_URI.fullmatch(str(root_identity["uri"])) is None
        or root.get("target_uri") != root_identity["uri"]
        or root.get("candidate_authority_release_sha256") is None
        or root.get("candidate_release_identity") != candidate_release_identity
        or root.get("candidate_release_sha256")
        != candidate_release.get("accepted_candidate_release_sha256")
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("authoritative_reopen_required") is not True
        or root.get("structure_only_validation_authority") is not False
        or root.get("complete") is not True
    ):
        _fail("reopened candidate-authority root binding differs")
    root_sha = _digest(
        root.get("candidate_authority_release_sha256"),
        label="candidate-authority root self-hash",
    )
    release_sha = _digest(
        candidate_release.get("accepted_candidate_release_sha256"),
        label="accepted candidate release self-hash",
    )
    if (
        expected_candidate_release_identity is not None
        and candidate_release_identity
        != _identity(
            expected_candidate_release_identity,
            label="capture-plan accepted candidate release",
        )
    ):
        _fail("candidate root release identity differs from capture plan")
    if (
        expected_candidate_release_sha256 is not None
        and release_sha
        != _digest(
            expected_candidate_release_sha256,
            label="capture-plan accepted candidate release SHA",
        )
    ):
        _fail("candidate root release SHA differs from capture plan")
    if (
        expected_catalog_receipt_identity is not None
        and root.get("catalog_replay_receipt_identity")
        != _identity(
            expected_catalog_receipt_identity,
            label="capture-plan fixed-G0 replay receipt",
        )
    ):
        _fail("candidate root catalog receipt identity differs from capture plan")
    if (
        expected_catalog_receipt_sha256 is not None
        and root.get("catalog_replay_receipt_sha256")
        != _digest(
            expected_catalog_receipt_sha256,
            label="capture-plan fixed-G0 replay receipt SHA",
        )
    ):
        _fail("candidate root catalog receipt SHA differs from capture plan")
    return {
        "root_identity": root_identity,
        "root_sha256": root_sha,
        "candidate_release_identity": candidate_release_identity,
        "candidate_release_sha256": release_sha,
    }


def _upgrade(
    base_plan_value: Mapping[str, object],
    *,
    binding: Mapping[str, object],
) -> dict[str, object]:
    try:
        base_plan = capture_v1.validate_capture_plan_lock_v1(base_plan_value)
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(str(exc)) from exc
    if (
        base_plan["accepted_candidate_release_identity"]
        != binding["candidate_release_identity"]
        or base_plan["accepted_candidate_release_sha256"]
        != binding["candidate_release_sha256"]
    ):
        _fail("base capture plan differs from reopened candidate authority")
    body = {
        key: item for key, item in base_plan.items() if key != "capture_plan_sha256"
    }
    body.update({
        "schema_version": CAPTURE_PLAN_SCHEMA,
        "capture_plan_id": CAPTURE_PLAN_ID,
        "capture_plan_scope": CAPTURE_PLAN_SCOPE,
        "capture_plan_lock_relative_path": CAPTURE_PLAN_LOCK_PATH,
        "fixed_g0_candidate_authority_root_identity": binding["root_identity"],
        "fixed_g0_candidate_authority_root_sha256": binding["root_sha256"],
        "fixed_g0_candidate_root_candidate_release_identity": binding[
            "candidate_release_identity"
        ],
        "fixed_g0_candidate_root_candidate_release_sha256": binding[
            "candidate_release_sha256"
        ],
        "fixed_g0_candidate_root_exact_reopened": True,
        "complete_candidate_population_binding_verified": True,
        "exact_occurrence_provenance_binding_verified": True,
        "caller_candidate_release_body_allowed": False,
        "caller_candidate_release_identity_allowed": False,
        "candidate_authority_exact_reopen_required": True,
        "candidate_authority_structure_only_authority": False,
    })
    body["capture_plan_sha256"] = canonical_sha256(body)
    return validate_capture_plan_lock_v2(body)


def validate_capture_plan_lock_v2(value: object) -> dict[str, object]:
    """Validate structure only; this deliberately grants no root authority."""
    item = _mapping(value, label="candidate-authority capture plan")
    if set(item) != set(_PLAN_FIELDS):
        _fail("candidate-authority capture-plan fields differ")
    retained = _digest(item.get("capture_plan_sha256"), label="capture-plan self-hash")
    unhashed = {
        key: nested
        for key, nested in item.items()
        if key != "capture_plan_sha256"
    }
    if canonical_sha256(unhashed) != retained:
        _fail("candidate-authority capture-plan self-hash differs")
    base_plan = _base_projection(item)
    root_identity = _identity(
        item.get("fixed_g0_candidate_authority_root_identity"),
        label="candidate-authority root identity",
    )
    root_candidate_identity = _identity(
        item.get("fixed_g0_candidate_root_candidate_release_identity"),
        label="candidate root release identity",
    )
    root_sha = _digest(
        item.get("fixed_g0_candidate_authority_root_sha256"),
        label="candidate-authority root SHA",
    )
    root_release_sha = _digest(
        item.get("fixed_g0_candidate_root_candidate_release_sha256"),
        label="candidate root release SHA",
    )
    prefix = str(root_identity["uri"]).removesuffix(candidate_authority.ROOT_FILENAME)
    if (
        item.get("schema_version") != CAPTURE_PLAN_SCHEMA
        or item.get("capture_plan_id") != CAPTURE_PLAN_ID
        or item.get("capture_plan_scope") != CAPTURE_PLAN_SCOPE
        or item.get("capture_plan_lock_relative_path") != CAPTURE_PLAN_LOCK_PATH
        or _ROOT_URI.fullmatch(str(root_identity["uri"])) is None
        or root_candidate_identity["uri"]
        != f"{prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}"
        or root_candidate_identity != base_plan["accepted_candidate_release_identity"]
        or root_release_sha != base_plan["accepted_candidate_release_sha256"]
        or item.get("fixed_g0_candidate_root_exact_reopened") is not True
        or item.get("complete_candidate_population_binding_verified") is not True
        or item.get("exact_occurrence_provenance_binding_verified") is not True
        or item.get("caller_candidate_release_body_allowed") is not False
        or item.get("caller_candidate_release_identity_allowed") is not False
        or item.get("candidate_authority_exact_reopen_required") is not True
        or item.get("candidate_authority_structure_only_authority") is not False
    ):
        _fail("candidate-authority capture-plan fixed law differs")
    normalized = dict(item)
    normalized.update({
        "fixed_g0_candidate_authority_root_identity": root_identity,
        "fixed_g0_candidate_authority_root_sha256": root_sha,
        "fixed_g0_candidate_root_candidate_release_identity": root_candidate_identity,
        "fixed_g0_candidate_root_candidate_release_sha256": root_release_sha,
        "capture_plan_sha256": retained,
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("candidate-authority capture-plan canonical replay differs")
    return normalized


def _reopen_candidate_authority(
    plan: Mapping[str, object],
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> candidate_authority.ReopenedFixedG0CandidateAuthorityV1:
    try:
        reopened = candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
            plan["fixed_g0_candidate_authority_root_identity"],
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(
            f"candidate-authority exact reopen failed: {exc}"
        ) from exc
    _authority_binding(
        reopened,
        expected_root_identity=plan["fixed_g0_candidate_authority_root_identity"],
        expected_candidate_release_identity=plan[
            "accepted_candidate_release_identity"
        ],
        expected_candidate_release_sha256=plan[
            "accepted_candidate_release_sha256"
        ],
        expected_catalog_receipt_identity=plan[
            "fixed_g0_replay_receipt_identity"
        ],
        expected_catalog_receipt_sha256=plan[
            "fixed_g0_replay_receipt_sha256"
        ],
    )
    return reopened


def build_capture_plan_lock_v2(
    *,
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    candidate_authority_root_identity: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    producer_id: str,
    producer_release_id: str,
    producer_namespace: str,
) -> dict[str, object]:
    """Build v2; the only candidate input is the terminal root identity."""
    try:
        reopened = candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
            candidate_authority_root_identity,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(
            f"candidate-authority exact reopen failed: {exc}"
        ) from exc
    binding = _authority_binding(
        reopened, expected_root_identity=candidate_authority_root_identity
    )
    try:
        base_plan = capture_v1.build_capture_plan_lock_v1(
            adapter_final_release_lock_commit_sha=adapter_final_release_lock_commit_sha,
            adapter_final_release_lock_raw=adapter_final_release_lock_raw,
            fixed_g0_replay_receipt=fixed_g0_replay_receipt,
            fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            accepted_candidate_release=reopened.candidate_release,
            accepted_candidate_release_identity=reopened.candidate_release_identity,
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
            implementation_commit_sha=implementation_commit_sha,
            implementation_measurements=implementation_measurements,
            producer_id=producer_id,
            producer_release_id=producer_release_id,
            producer_namespace=producer_namespace,
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(str(exc)) from exc
    if (
        base_plan["fixed_g0_replay_receipt_identity"]
        != reopened.root["catalog_replay_receipt_identity"]
        or base_plan["fixed_g0_replay_receipt_sha256"]
        != reopened.root["catalog_replay_receipt_sha256"]
    ):
        _fail("candidate authority and capture plan use different catalog roots")
    return _upgrade(base_plan, binding=binding)


def validate_capture_plan_against_prerequisites_v2(
    value: object,
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Exact-reopen the internal root and rebuild against all prerequisites."""
    plan = validate_capture_plan_lock_v2(value)
    reopened = _reopen_candidate_authority(
        plan,
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    base_plan = _base_projection(plan)
    try:
        rebuilt_base = capture_v1.validate_capture_plan_against_prerequisites_v1(
            base_plan,
            adapter_final_release_lock_commit_sha=adapter_final_release_lock_commit_sha,
            adapter_final_release_lock_raw=adapter_final_release_lock_raw,
            fixed_g0_replay_receipt=fixed_g0_replay_receipt,
            fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            accepted_candidate_release=reopened.candidate_release,
            accepted_candidate_release_identity=reopened.candidate_release_identity,
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
        )
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupCapturePlanCandidateAuthorityV2Error(str(exc)) from exc
    binding = _authority_binding(
        reopened,
        expected_root_identity=plan["fixed_g0_candidate_authority_root_identity"],
        expected_candidate_release_identity=plan[
            "accepted_candidate_release_identity"
        ],
        expected_candidate_release_sha256=plan[
            "accepted_candidate_release_sha256"
        ],
        expected_catalog_receipt_identity=plan[
            "fixed_g0_replay_receipt_identity"
        ],
        expected_catalog_receipt_sha256=plan[
            "fixed_g0_replay_receipt_sha256"
        ],
    )
    rebuilt = _upgrade(rebuilt_base, binding=binding)
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(plan):
        _fail("capture plan differs from exact-opened candidate authority")
    return rebuilt


__all__ = [
    "CAPTURE_PLAN_ID",
    "CAPTURE_PLAN_LOCK_PATH",
    "CAPTURE_PLAN_SCHEMA",
    "CAPTURE_PLAN_SCOPE",
    "CorpusR6MatchupCapturePlanCandidateAuthorityV2Error",
    "build_capture_plan_lock_v2",
    "canonical_json_bytes",
    "canonical_sha256",
    "validate_capture_plan_against_prerequisites_v2",
    "validate_capture_plan_lock_v2",
]
