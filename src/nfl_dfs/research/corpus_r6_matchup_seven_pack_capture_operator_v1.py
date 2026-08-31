"""Guarded operator boundary for the R6 matchup seven-pack capture.

Validation is local.  Task-0 and reopen are generation-pinned/read-only and
require their own explicit environment switches.  Publication has a separate
switch and receives only already-bounded query/storage callbacks.  Client
construction belongs to the CLI and must occur after ``require_mode_enabled``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import stat
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_paid_source_normalized_snapshot_v1 as snapshot
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_v2,
)


CAPTURE_REQUEST_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-capture-request/v2"
)
VALIDATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-request-validation/v1"
)
TASK0_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-task0-readiness/v1"
)
OPERATOR_PUBLICATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-operator-publication/v1"
)
OPERATOR_REOPEN_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-operator-reopen/v1"
)

TASK0_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SEVEN_PACK_TASK0"
PUBLISH_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SEVEN_PACK_PUBLISH"
REOPEN_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SEVEN_PACK_REOPEN"
ENABLE_VALUE: Final = "1"
MODE_ENABLE_ENV: Final = {
    "task0": TASK0_ENABLE_ENV,
    "publish": PUBLISH_ENABLE_ENV,
    "reopen": REOPEN_ENABLE_ENV,
}

GitHead = Callable[[Path], str]
GitBlob = Callable[[Path, str, str], bytes]
GitStatus = Callable[[Path, Sequence[str]], bytes]


class CorpusR6MatchupSevenPackCaptureOperatorV1Error(RuntimeError):
    """The seven-pack operator guard or request failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _with_hash(body: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    result = dict(body)
    result[field_name] = source.canonical_sha256(result)
    return result


def build_capture_request_v1(
    *, run_id: str,
    candidate_authority_v2_root_identity: Mapping[str, object],
    normalized_snapshot_terminal_identity: Mapping[str, object],
) -> dict[str, object]:
    # These core calls perform strict type validation; no string coercion is
    # allowed before namespace/output inventory construction.
    namespace = capture.output_namespace_for_run_v1(run_id)
    inventory = capture.output_uri_inventory_v1(run_id)
    try:
        fixed_root = source.normalize_object_identity_v2(
            candidate_authority_v2_root_identity,
            label="request candidate-authority v2 root",
        )
        normalized_terminal = source.normalize_object_identity_v2(
            normalized_snapshot_terminal_identity,
            label="request normalized snapshot terminal",
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(str(exc)) from exc
    expected_candidate_prefix = (
        f"gs://{candidate_v2.OUTPUT_BUCKET}/{candidate_v2.OUTPUT_NAMESPACE}/"
    )
    if (
        not str(fixed_root["uri"]).startswith(expected_candidate_prefix)
        or not str(fixed_root["uri"]).endswith(candidate_v2.ROOT_FILENAME)
    ):
        _fail("capture request candidate-authority v2 root URI differs")
    if (
        not str(normalized_terminal["uri"]).startswith(
            f"{snapshot.OUTPUT_PREFIX}/"
        )
        or not str(normalized_terminal["uri"]).endswith(
            "/snapshot-terminal.json"
        )
    ):
        _fail("capture request normalized snapshot terminal URI differs")
    if fixed_root["uri"] == normalized_terminal["uri"]:
        _fail("capture request reuses an input URI")
    body: dict[str, object] = {
        "schema_version": CAPTURE_REQUEST_SCHEMA,
        "run_id": run_id,
        "namespace": namespace,
        "candidate_authority_v2_root_identity": fixed_root,
        "normalized_snapshot_terminal_identity": normalized_terminal,
        "warehouse_query_pack_ids": list(capture.WAREHOUSE_PACK_IDS),
        "artifact_pack_ids": list(capture.ARTIFACT_PACK_IDS),
        "output_uri_inventory": list(inventory),
        "output_uri_inventory_sha256": source.canonical_sha256(list(inventory)),
        "external_actions_default_off": True,
        "synthetic_fallback_allowed": False,
        "listing_allowed": False,
        "overwrite_allowed": False,
        **_policy(),
    }
    return _with_hash(body, field_name="capture_request_sha256")


def validate_capture_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="seven-pack capture request")
    if set(item) != {
        "schema_version", "run_id", "namespace",
        "candidate_authority_v2_root_identity",
        "normalized_snapshot_terminal_identity", "warehouse_query_pack_ids",
        "artifact_pack_ids", "output_uri_inventory",
        "output_uri_inventory_sha256", "external_actions_default_off",
        "synthetic_fallback_allowed", "listing_allowed", "overwrite_allowed",
        *source.POLICY_FIELDS, "capture_request_sha256",
    }:
        _fail("seven-pack capture request fields differ")
    retained = item.get("capture_request_sha256")
    body = dict(item)
    del body["capture_request_sha256"]
    if (
        type(retained) is not str
        or sha256(source.canonical_json_bytes(body)).hexdigest() != retained
    ):
        _fail("seven-pack capture request self-hash differs")
    rebuilt = build_capture_request_v1(
        run_id=item.get("run_id"),
        candidate_authority_v2_root_identity=item.get(
            "candidate_authority_v2_root_identity"
        ),
        normalized_snapshot_terminal_identity=item.get(
            "normalized_snapshot_terminal_identity"
        ),
    )
    if rebuilt != item:
        _fail("seven-pack capture request canonical replay differs")
    return rebuilt


def _reopen_normalized_manifests_v1(
    *, request: Mapping[str, object], read_exact: capture.ReadExact,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Derive FP/SIS manifests only from one deep-reopened terminal."""

    try:
        reopened = snapshot.reopen_normalized_snapshot_v1(
            terminal_identity=request["normalized_snapshot_terminal_identity"],
            read_exact=read_exact,
        )
    except snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error as exc:
        raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(
            f"normalized snapshot exact reopen failed: {exc}"
        ) from exc
    manifests_value = _mapping(
        reopened.get("artifact_manifest_identities"),
        label="normalized snapshot artifact manifests",
    )
    if set(manifests_value) != set(capture.ARTIFACT_PACK_IDS):
        _fail("normalized snapshot artifact manifest registry differs")
    manifests: dict[str, dict[str, object]] = {}
    for pack_id in capture.ARTIFACT_PACK_IDS:
        try:
            manifests[pack_id] = source.normalize_object_identity_v2(
                manifests_value[pack_id],
                label=f"normalized snapshot {pack_id} manifest",
            )
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(
                str(exc)
            ) from exc
    input_uris = {
        str(request["candidate_authority_v2_root_identity"]["uri"]),
        str(request["normalized_snapshot_terminal_identity"]["uri"]),
        *(str(value["uri"]) for value in manifests.values()),
    }
    if len(input_uris) != 4:
        _fail("normalized snapshot and seven-pack input URIs overlap")
    return manifests, reopened


def require_mode_enabled_v1(
    mode: str, *, environment: Mapping[str, str] | None = None,
) -> None:
    if mode not in MODE_ENABLE_ENV:
        _fail("seven-pack external mode is not registered")
    env = os.environ if environment is None else environment
    variable = MODE_ENABLE_ENV[mode]
    if env.get(variable) != ENABLE_VALUE:
        _fail(f"{mode} is disabled; set {variable}=1 explicitly")


def _secure_current_file(repository_root: Path, relative_path: str) -> bytes:
    path = repository_root / relative_path
    try:
        root = repository_root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        info = os.lstat(path)
    except OSError as exc:
        raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(
            "implementation file is absent"
        ) from exc
    if (
        not repository_root.is_absolute()
        or root != repository_root
        or root not in resolved.parents
        or stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
    ):
        _fail("implementation file is not one repository-contained regular file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(
            "implementation file read failed"
        ) from exc
    if not raw or len(raw) != info.st_size:
        _fail("implementation file bytes differ")
    return raw


def build_clean_implementation_authority_v1(
    *, repository_root: Path, git_head: GitHead,
    git_blob: GitBlob, git_status: GitStatus,
) -> dict[str, object]:
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        _fail("repository root must be one absolute Path")
    try:
        commit = git_head(repository_root)
        status = git_status(repository_root, list(capture.IMPLEMENTATION_PATHS))
    except Exception as exc:
        raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(
            "implementation Git inspection failed"
        ) from exc
    if type(commit) is not str or len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        _fail("implementation Git HEAD differs")
    if status != b"":
        _fail("implementation paths are dirty or untracked")
    measurements: list[dict[str, object]] = []
    for relative_path in capture.IMPLEMENTATION_PATHS:
        current = _secure_current_file(repository_root, relative_path)
        try:
            committed = git_blob(repository_root, commit, relative_path)
        except Exception as exc:
            raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(
                "implementation Git blob read failed"
            ) from exc
        if type(committed) is not bytes or committed != current:
            _fail("implementation worktree bytes differ from the Git blob")
        measurements.append({
            "relative_path": relative_path,
            "sha256": sha256(current).hexdigest(),
            "bytes": len(current),
        })
    return capture.build_implementation_authority_v1(
        source_commit_sha=commit, measurements=measurements
    )


def build_provider_source_implementation_authority_v1(
    *, repository_root: Path, source_commit_sha: str,
) -> dict[str, object]:
    """Measure provider-checked-out bytes for a Git-free runtime image.

    This function proves only byte construction.  The cloud build gate must
    separately prove that ``source_commit_sha`` is its requested and resolved
    Git source.  Runtime publication remeasures the copied files below.
    """

    if (
        not isinstance(repository_root, Path)
        or not repository_root.is_absolute()
        or type(source_commit_sha) is not str
        or len(source_commit_sha) != 40
        or any(character not in "0123456789abcdef" for character in source_commit_sha)
    ):
        _fail("provider source implementation identity differs")
    measurements = []
    for relative_path in capture.IMPLEMENTATION_PATHS:
        raw = _secure_current_file(repository_root, relative_path)
        measurements.append({
            "relative_path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return capture.build_implementation_authority_v1(
        source_commit_sha=source_commit_sha, measurements=measurements
    )


def reopen_runtime_implementation_authority_v1(
    *, repository_root: Path, implementation_authority: Mapping[str, object],
) -> dict[str, object]:
    """Remeasure every bound file in a Git-free immutable runtime."""

    try:
        authority = capture.validate_implementation_authority_v1(
            implementation_authority
        )
    except capture.CorpusR6MatchupSevenPackCaptureV1Error as exc:
        raise CorpusR6MatchupSevenPackCaptureOperatorV1Error(str(exc)) from exc
    observed = build_provider_source_implementation_authority_v1(
        repository_root=repository_root,
        source_commit_sha=str(authority["source_commit_sha"]),
    )
    if observed != authority:
        _fail("runtime implementation bytes differ from build authority")
    return authority


def validate_request_only_v1(value: object) -> dict[str, object]:
    request = validate_capture_request_v1(value)
    body: dict[str, object] = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "capture_request_sha256": request["capture_request_sha256"],
        "run_id": request["run_id"],
        "namespace": request["namespace"],
        "output_uri_count": len(request["output_uri_inventory"]),
        "local_validation_complete": True,
        "cloud_client_constructed": False,
        "warehouse_client_constructed": False,
        "external_read_count": 0,
        "warehouse_query_count": 0,
        "publication_count": 0,
        **_policy(),
    }
    return _with_hash(body, field_name="validation_receipt_sha256")


def run_task0_v1(
    *, request_value: object, read_exact: capture.ReadExact,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    require_mode_enabled_v1("task0", environment=environment)
    request = validate_capture_request_v1(request_value)
    manifests, snapshot_reopen = _reopen_normalized_manifests_v1(
        request=request, read_exact=read_exact
    )
    preflight = capture.preflight_seven_pack_inputs_v1(
        fixed_source_root_identity=request[
            "candidate_authority_v2_root_identity"
        ],
        artifact_manifest_identities=manifests,
        read_exact=read_exact,
    )
    body: dict[str, object] = {
        "schema_version": TASK0_RECEIPT_SCHEMA,
        "capture_request_sha256": request["capture_request_sha256"],
        "normalized_snapshot_terminal_identity": request[
            "normalized_snapshot_terminal_identity"
        ],
        "normalized_snapshot_reopen_sha256": snapshot_reopen[
            "snapshot_reopen_sha256"
        ],
        "artifact_manifest_identities": manifests,
        "input_preflight": preflight,
        "input_preflight_sha256": preflight["input_preflight_sha256"],
        "scope": (
            "candidate-v2-and-normalized-terminal-derived-fp-sis-"
            "manifest-readiness-only"
        ),
        "warehouse_query_count": 0,
        "publication_count": 0,
        "publication_callback_exposed": False,
        "write_inventory_count": 0,
        "ambient_service_account_write_capability": "not_evaluated",
        "real_capture_still_required": True,
        **_policy(),
    }
    return _with_hash(body, field_name="task0_receipt_sha256")


def run_publish_v1(
    *, request_value: object,
    implementation_authority: Mapping[str, object],
    query_warehouse: capture.QueryWarehouse,
    read_exact: capture.ReadExact,
    publish_create_once: capture.PublishCreateOnceOrExactPrior,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    require_mode_enabled_v1("publish", environment=environment)
    request = validate_capture_request_v1(request_value)
    manifests, snapshot_reopen = _reopen_normalized_manifests_v1(
        request=request, read_exact=read_exact
    )
    result = capture.publish_seven_pack_capture_v1(
        run_id=request["run_id"],
        fixed_source_root_identity=request[
            "candidate_authority_v2_root_identity"
        ],
        artifact_manifest_identities=manifests,
        implementation_authority=implementation_authority,
        query_warehouse=query_warehouse,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
    )
    body: dict[str, object] = {
        "schema_version": OPERATOR_PUBLICATION_RECEIPT_SCHEMA,
        "capture_request_sha256": request["capture_request_sha256"],
        "normalized_snapshot_terminal_identity": request[
            "normalized_snapshot_terminal_identity"
        ],
        "normalized_snapshot_reopen_sha256": snapshot_reopen[
            "snapshot_reopen_sha256"
        ],
        "artifact_manifest_identities": manifests,
        "publication_receipt": result,
        "publication_receipt_sha256": result["publication_receipt_sha256"],
        "terminal_release_identity": result["terminal_release_identity"],
        "terminal_release_root_last": result["terminal_release_root_last"],
        "external_mode_was_explicitly_enabled": True,
        **_policy(),
    }
    return _with_hash(body, field_name="operator_publication_receipt_sha256")


def run_reopen_v1(
    *, release_identity: Mapping[str, object], read_exact: capture.ReadExact,
    expected_fixed_source_root_identity: Mapping[str, object] | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    require_mode_enabled_v1("reopen", environment=environment)
    result = capture.reopen_seven_pack_capture_v1(
        release_identity=release_identity,
        read_exact=read_exact,
        expected_fixed_source_root_identity=expected_fixed_source_root_identity,
    )
    body: dict[str, object] = {
        "schema_version": OPERATOR_REOPEN_RECEIPT_SCHEMA,
        "reopen_receipt": result,
        "reopen_receipt_sha256": result["reopen_receipt_sha256"],
        "complete": result["complete"],
        "write_capability_present": False,
        "warehouse_query_capability_present": False,
        "external_mode_was_explicitly_enabled": True,
        **_policy(),
    }
    return _with_hash(body, field_name="operator_reopen_receipt_sha256")


__all__ = [
    "CAPTURE_REQUEST_SCHEMA",
    "CorpusR6MatchupSevenPackCaptureOperatorV1Error",
    "PUBLISH_ENABLE_ENV",
    "REOPEN_ENABLE_ENV",
    "TASK0_ENABLE_ENV",
    "build_capture_request_v1",
    "build_clean_implementation_authority_v1",
    "build_provider_source_implementation_authority_v1",
    "reopen_runtime_implementation_authority_v1",
    "require_mode_enabled_v1",
    "run_publish_v1",
    "run_reopen_v1",
    "run_task0_v1",
    "validate_capture_request_v1",
    "validate_request_only_v1",
]
