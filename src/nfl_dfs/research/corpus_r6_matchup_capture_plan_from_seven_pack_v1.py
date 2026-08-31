"""Build capture-plan-v3 only from a deep-reopened seven-pack release.

This is the Commit-A to Commit-B bridge.  It accepts one generation-pinned
seven-pack terminal identity, independently reopens that complete graph,
derives candidate-authority-v2 from the release, reads the fixed adapter lock
from Commit A, and byte-builds capture-plan-v3.  It has no publication or
outcome capability; the caller may create the returned canonical lock file
once, after this function succeeds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
from typing import Final

from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_outer_candidate_authority_v3 as capture_v3,
)
from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as seven_pack
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as fixed_g0,
)


BRIDGE_SCHEMA: Final = "corpus-r6-matchup-capture-plan-from-seven-pack/v1"
FREEZE_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_CAPTURE_PLAN_V3_FREEZE"
ENABLE_VALUE: Final = "1"
PRODUCER_ID: Final = "r6-matchup-component-producer-v1"
PRODUCER_RELEASE_ID: Final = "20260830-r6-matchup-component-release-v3"
PRODUCER_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-source/research/"
    "corpus-r6-matchup-components-v3/20260830-r6-matchup-source-v3/"
)

ReadExact = Callable[[Mapping[str, object]], bytes]
GitHead = Callable[[Path], str]
GitBlob = Callable[[Path, str, str], bytes]
GitStatus = Callable[[Path, Sequence[str]], bytes]


class CorpusR6MatchupCapturePlanFromSevenPackV1Error(RuntimeError):
    """The exact seven-pack to capture-plan bridge failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(str(exc)) from exc


def _exact_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    try:
        value = _mapping(json.loads(raw.decode("utf-8")), label=label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(
            f"{label} canonical JSON differs"
        ) from exc
    if source.canonical_json_bytes(value) != raw:
        _fail(f"{label} canonical bytes differ")
    return value, identity


def _load_release_and_rows(
    *, release_identity: Mapping[str, object], read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    # The full independent replay is deliberately first.  No capture-plan
    # inputs or bytes are assembled until it has succeeded.
    try:
        reopened = seven_pack.reopen_seven_pack_capture_v1(
            release_identity=release_identity, read_exact=read_exact
        )
    except seven_pack.CorpusR6MatchupSevenPackCaptureV1Error as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(
            f"seven-pack independent reopen failed: {exc}"
        ) from exc
    if (
        reopened.get("complete") is not True
        or reopened.get("all_seven_rows_exact_reopened") is not True
        or reopened.get("all_seven_provenance_objects_exact_reopened") is not True
        or reopened.get(
            "all_artifact_manifest_shards_and_predecessors_exact_reopened"
        ) is not True
    ):
        _fail("seven-pack independent reopen is incomplete")
    release, retained_identity = _exact_json(
        release_identity, read_exact=read_exact, label="seven-pack terminal release"
    )
    packs = _sequence(release.get("packs"), label="seven-pack release packs")
    if len(packs) != len(source.PACK_IDS):
        _fail("seven-pack release pack count differs")
    rows: list[dict[str, object]] = []
    for ordinal, (expected_pack_id, pack_value) in enumerate(
        zip(source.PACK_IDS, packs, strict=True)
    ):
        pack = _mapping(pack_value, label=f"seven-pack pack[{ordinal}]")
        if pack.get("pack_id") != expected_pack_id:
            _fail("seven-pack release pack order differs")
        row_object, _ = _exact_json(
            pack.get("exact_rows_identity"),
            read_exact=read_exact,
            label=f"seven-pack {expected_pack_id} rows",
        )
        try:
            rows.append(source.validate_upstream_pack_rows_v1(
                row_object, expected_pack_id=expected_pack_id
            ))
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(str(exc)) from exc
    candidate_identity = _identity(
        release.get("fixed_source_root_identity"),
        label="seven-pack candidate-authority v2 root",
    )
    if reopened.get("fixed_source_root_identity") != candidate_identity:
        _fail("seven-pack reopen and release candidate root differ")
    try:
        validated_release = source.validate_upstream_release_v1(
            release,
            pack_row_objects=rows,
            expected_fixed_source_root_identity=candidate_identity,
            expected_namespace=release.get("namespace"),
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(str(exc)) from exc
    if retained_identity != reopened.get("release_identity"):
        _fail("seven-pack release identity differs from independent reopen")
    return validated_release, reopened, rows


def build_capture_plan_from_seven_pack_v1(
    *, release_identity: Mapping[str, object], repository_root: Path,
    read_exact: ReadExact, git_head: GitHead, git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Return canonical capture-plan-v3 bytes after full predecessor replay."""

    release, reopened, rows = _load_release_and_rows(
        release_identity=release_identity, read_exact=read_exact
    )
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        _fail("repository root must be one absolute Path")
    try:
        commit = git_head(repository_root)
        adapter_raw = git_blob(
            repository_root, commit, fixed_g0.FIXED_FINAL_RELEASE_LOCK_PATH
        )
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(
            "Commit-A adapter-lock read failed"
        ) from exc
    if type(adapter_raw) is not bytes or not adapter_raw:
        _fail("Commit-A adapter-lock bytes differ")
    candidate_identity = _identity(
        release["fixed_source_root_identity"],
        label="candidate-authority v2 root derived from seven-pack",
    )
    try:
        plan = capture_v3.build_capture_plan_lock_v3(
            adapter_final_release_lock_commit_sha=commit,
            adapter_final_release_lock_raw=adapter_raw,
            candidate_authority_root_identity=candidate_identity,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            upstream_source_release=release,
            upstream_source_release_identity=release_identity,
            upstream_pack_row_objects=rows,
            producer_id=PRODUCER_ID,
            producer_release_id=PRODUCER_RELEASE_ID,
            producer_namespace=PRODUCER_NAMESPACE,
        )
        rebuilt = capture_v3.validate_capture_plan_against_prerequisites_v3(
            plan,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            adapter_final_release_lock_commit_sha=commit,
            adapter_final_release_lock_raw=adapter_raw,
            upstream_source_release=release,
            upstream_source_release_identity=release_identity,
            upstream_pack_row_objects=rows,
        )
    except capture_v3.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error as exc:
        raise CorpusR6MatchupCapturePlanFromSevenPackV1Error(str(exc)) from exc
    # The tracked capture-plan lock is a canonical JSON text file, not merely
    # the canonical JSON value.  Source-v3 deliberately binds the exact file
    # bytes and requires one trailing newline, so the bridge receipt must bind
    # those same bytes before Commit B is created.
    plan_raw = source.canonical_json_bytes(rebuilt) + b"\n"
    body: dict[str, object] = {
        "schema_version": BRIDGE_SCHEMA,
        "capture_plan": rebuilt,
        "capture_plan_relative_path": capture_v3.CAPTURE_PLAN_LOCK_PATH,
        "capture_plan_sha256": sha256(plan_raw).hexdigest(),
        "capture_plan_bytes": len(plan_raw),
        "commit_a_sha": commit,
        "seven_pack_release_identity": _identity(
            release_identity, label="seven-pack release"
        ),
        "seven_pack_reopen_receipt_sha256": reopened[
            "reopen_receipt_sha256"
        ],
        "candidate_authority_v2_root_identity": candidate_identity,
        "warehouse_pack_ids": list(seven_pack.WAREHOUSE_PACK_IDS),
        "artifact_pack_ids": list(seven_pack.ARTIFACT_PACK_IDS),
        "capture_plan_built_after_complete_seven_pack_reopen": True,
        "capture_plan_requires_distinct_tracking_commit_b": True,
        "capture_plan_publication_count": 0,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    body["bridge_receipt_sha256"] = source.canonical_sha256(body)
    return body


__all__ = [
    "BRIDGE_SCHEMA",
    "ENABLE_VALUE",
    "FREEZE_ENABLE_ENV",
    "PRODUCER_ID",
    "PRODUCER_NAMESPACE",
    "PRODUCER_RELEASE_ID",
    "CorpusR6MatchupCapturePlanFromSevenPackV1Error",
    "build_capture_plan_from_seven_pack_v1",
]
