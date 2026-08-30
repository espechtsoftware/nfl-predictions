#!/usr/bin/env python3
"""Guarded operator for the real outer-bound fixed-G0 candidate authority.

The operator deliberately has three narrow, default-off commands:

* ``prepublish`` performs the complete 54-slate candidate derivation using
  generation-exact reads, but exposes no storage write callback;
* ``publish`` exposes one callback constrained to the exact 165 create-once
  v2 output URIs and requires the terminal v2 root to be call 165; and
* ``reopen`` accepts one local generation-pinned v2 root identity and invokes
  the release module's complete independent predecessor replay read-only.

The catalog-recovery outer identity is never a caller input.  It is recovered
only from the fixed tracked publication/reopen receipt after a clean detached
worktree, exact ``origin/main`` equality, bound implementation bytes, and
module-origin checks have all passed.  No command reads outcomes or exposes a
list, current-generation lookup, overwrite, delete, graph, or deployment API.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
import stat
import sys
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_v1 as candidate_v1,
)
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_v2 as candidate,
)
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as release,
)
from nfl_dfs.research import (
    corpus_r6_fixed_g0_catalog_recovery_downstream_v1 as recovery_downstream,
)
from nfl_dfs.research import (
    corpus_r6_fixed_g0_catalog_recovery_v1 as recovery,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter,
)


OPERATOR_RECEIPT_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-operator-receipt/v2"
)
OPERATOR_FAILURE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-operator-failure/v2"
)
PROJECT: Final = "nfl-predictions-503414"
BOUND_API_COMMIT: Final = "93bca249eb0bf22e323ce0ff7a4c929469a38ca5"
OPERATOR_PATH: Final = "scripts/run_corpus_r6_fixed_g0_candidate_authority_v2.py"
RECOVERY_RECEIPT_PATH: Final = (
    "reports/2026-08-29-r6-fixed-g0-catalog-publication-reopen-receipt.json"
)
RECOVERY_RECEIPT_SCHEMA: Final = (
    "corpus-r6-fixed-g0-catalog-publication-reopen-receipt/v1"
)
RECOVERY_RECEIPT_BYTES: Final = 2_322
RECOVERY_RECEIPT_FILE_SHA256: Final = (
    "a2942dcf40295a1f385a03a3b59f3962e8cb9c846ac5e5c893736ae80f720f4b"
)
BOUND_CANDIDATE_CORE_SHA256: Final = (
    "da859efc30eb8e6687bbc8a9ee70ded91cd7864b262c2cc35f2ec635a37a286c"
)
BOUND_CANDIDATE_RELEASE_SHA256: Final = (
    "340a4963f455b083153924a516adc8b2b714c854797161d192d355d9a3bcd2ae"
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,80}\Z")
_V2_ROOT_URI = re.compile(
    rf"gs://{re.escape(release.OUTPUT_BUCKET)}/"
    rf"{re.escape(release.OUTPUT_NAMESPACE)}/"
    r"(?P<run_id>[a-z0-9][a-z0-9-]{7,80})/"
    rf"{re.escape(release.ROOT_FILENAME)}\Z"
)

_EXPECTED_RECOVERY_RECEIPT: Final = {
    "schema_version": RECOVERY_RECEIPT_SCHEMA,
    "complete": True,
    "recorded_at_utc": "2026-08-29T23:58:03Z",
    "publication_commit_sha": "f4a286769090c4657e56b1951a8057eb3f72d483",
    "implementation_commit_sha": "fe814836da474c792514d63b50cd8642832b1a87",
    "catalog_namespace": (
        "gs://nfl-predictions-503414-corpus-source/research/source/"
        "20260826-r6-player-catalog-fixed-g0-v1/"
    ),
    "outer_attestation_identity": {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/source/"
            "20260826-r6-player-catalog-fixed-g0-v1/"
            "fixed-g0-catalog-recovery-attestation-v2.json"
        ),
        "generation": "1788047679701105",
        "sha256": (
            "65f49bcc66c7761eee050ceb066252977b4a94ed48f0fa56da644c85a6c98cf2"
        ),
        "bytes": 53_857,
    },
    "outer_attestation_sha256": (
        "1e7da9aa777d7d347039dacd4071bff02fbc4f5e672d1572978bbd4c045a82b4"
    ),
    "inner_catalog_release_identity": {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/source/"
            "20260826-r6-player-catalog-fixed-g0-v1/catalog-release.json"
        ),
        "generation": "1788047593516963",
        "sha256": (
            "c43b760bedda901d53c25e367bd2b075b7766ceb77ed9089a207dbd9f8608a45"
        ),
        "bytes": 65_922,
    },
    "inner_replay_receipt_identity": {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/source/"
            "20260826-r6-player-catalog-fixed-g0-v1/fixed-g0-replay-receipt.json"
        ),
        "generation": "1788047635130538",
        "sha256": (
            "8cb6ba23dabf4f16ea9a087609fbfd66cae411e700a60bbba6b40b9700c9e574"
        ),
        "bytes": 7_399,
    },
    "publication": {
        "complete": True,
        "mode": "publish",
        "inner_object_count": 110,
        "total_object_count": 111,
        "inner_exact_reopen_complete": True,
        "outer_published_last": True,
        "outer_presence_state": "confirmed-present",
        "deployment_performed": False,
        "graph_mutation_performed": False,
    },
    "independent_reopen": {
        "complete": True,
        "mode": "reopen",
        "terminal_object_count": 111,
        "write_capability_enabled": False,
        "cloud_mutation_performed": False,
        "result_object_bodies_read": False,
    },
    "outcome_columns_read": [],
    "uses_realized_outcomes": False,
    "world_matrix_bodies_read": False,
    "world_schedule_bodies_read": False,
    "authority": {
        "downstream_pin_ready": True,
        "realized_outcome_authority": False,
        "production_promotion_authority": False,
    },
}

_BOUND_FILES: Final = {
    candidate.CORE_V2_MODULE_PATH: BOUND_CANDIDATE_CORE_SHA256,
    candidate.RELEASE_V2_MODULE_PATH: BOUND_CANDIDATE_RELEASE_SHA256,
}

_MODULE_ORIGIN_PATHS: Final = {
    "candidate_core_v1": candidate.FROZEN_CORE_V1_MODULE_PATH,
    "candidate_core_v2": candidate.CORE_V2_MODULE_PATH,
    "candidate_release_v2": candidate.RELEASE_V2_MODULE_PATH,
    "catalog_recovery_downstream_v1": recovery_downstream.DOWNSTREAM_MODULE_PATH,
    "catalog_recovery_v1": recovery.RECOVERY_MODULE_PATH,
    "catalog_adapter_v1": adapter.FIXED_ADAPTER_MODULE_PATH,
    "matchup_source_v2": "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
    "player_catalog_v1": "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py",
    "operator": OPERATOR_PATH,
}

_MODULES: Final = {
    "candidate_core_v1": candidate_v1,
    "candidate_core_v2": candidate,
    "candidate_release_v2": release,
    "catalog_recovery_downstream_v1": recovery_downstream,
    "catalog_recovery_v1": recovery,
    "catalog_adapter_v1": adapter,
    "matchup_source_v2": source,
    "player_catalog_v1": catalog,
}


class RunCorpusR6FixedG0CandidateAuthorityV2Error(RuntimeError):
    """The guarded candidate-v2 operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        partial_receipt: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.partial_receipt = (
            None if partial_receipt is None else dict(partial_receipt)
        )


@dataclass(frozen=True, slots=True)
class LocalAuthorityContextV2:
    repository_root: Path
    repository: adapter.SubprocessGitRepositoryV1
    clean_head: str
    origin_main: str
    module_origins: Mapping[str, str]
    recovery_receipt_file: Mapping[str, object]
    catalog_recovery_outer_identity: Mapping[str, object]
    catalog_recovery_outer_attestation_sha256: str


def _fail(message: str) -> None:
    raise RunCorpusR6FixedG0CandidateAuthorityV2Error(message)


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
            _fail("operator object keys differ")
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_thaw(item) for item in value]
    return value


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            "operator value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = _mapping(value, label="operator receipt")
    body[field] = canonical_sha256(body)
    return body


def _parse_strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except RunCorpusR6FixedG0CandidateAuthorityV2Error:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    return _mapping(value, label=label)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(str(exc)) from exc


def _run_id(value: object) -> str:
    if type(value) is not str or _RUN_ID.fullmatch(value) is None:
        _fail("candidate-authority v2 run ID differs")
    # Bind validation to the release API as well as the local lexical gate.
    release.output_prefix_for_run_v2(value)
    return value


def _project(value: object) -> str:
    if value != PROJECT:
        _fail("candidate-authority project differs from the fixed project")
    return PROJECT


def _execute(value: object, *, label: str) -> None:
    if value is not True:
        _fail(f"{label} requires its explicit confirmation flag")


def _require_api_signature(function: Callable[..., object], expected: tuple[str, ...]) -> None:
    observed = tuple(inspect.signature(function).parameters)
    if observed != expected:
        _fail(f"bound API signature differs for {function.__name__}")


def _require_bound_api_signatures() -> None:
    _require_api_signature(
        candidate.derive_fixed_g0_candidate_material_v2,
        (
            "repository_root",
            "catalog_recovery_outer_identity",
            "read_exact",
            "git_head",
            "git_blob",
            "git_status",
        ),
    )
    _require_api_signature(
        release.publish_fixed_g0_candidate_authority_release_v2,
        (
            "run_id",
            "repository_root",
            "catalog_recovery_outer_identity",
            "read_exact",
            "publish_create_once",
            "git_head",
            "git_blob",
            "git_status",
        ),
    )
    _require_api_signature(
        release.reopen_fixed_g0_candidate_authority_release_v2,
        (
            "root_identity",
            "repository_root",
            "read_exact",
            "git_head",
            "git_blob",
            "git_status",
        ),
    )


def _git_commit(raw: bytes, *, label: str) -> str:
    try:
        value = raw.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            f"{label} is not ASCII"
        ) from exc
    if _COMMIT.fullmatch(value) is None:
        _fail(f"{label} differs")
    return value


def _require_detached_head(repository: adapter.SubprocessGitRepositoryV1) -> None:
    try:
        repository._run(["symbolic-ref", "-q", "HEAD"], label="detached HEAD")
    except Exception:
        return
    _fail("candidate publication requires an explicit detached Git worktree")


def _verify_module_origins(repository_root: Path) -> dict[str, str]:
    origins: dict[str, str] = {}
    for label, relative_path in _MODULE_ORIGIN_PATHS.items():
        expected = (repository_root / relative_path).resolve()
        raw_path = Path(__file__) if label == "operator" else Path(
            str(getattr(_MODULES[label], "__file__", ""))
        )
        try:
            mode = raw_path.lstat().st_mode
        except OSError as exc:
            raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
                f"{label} module origin is absent"
            ) from exc
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or raw_path.resolve() != expected:
            _fail(f"{label} module origin escapes the explicit repository root")
        origins[label] = relative_path
    return origins


def _require_unchanged_bound_file(
    *,
    repository_root: Path,
    repository: adapter.SubprocessGitRepositoryV1,
    current_head: str,
    relative_path: str,
    expected_sha256: str,
) -> None:
    try:
        base_raw = repository.read_tracked(BOUND_API_COMMIT, relative_path)
        current_raw = repository.read_tracked(current_head, relative_path)
        path = repository_root / relative_path
        mode = path.lstat().st_mode
        worktree_raw = path.read_bytes()
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            f"bound implementation read failed: {relative_path}"
        ) from exc
    if (
        stat.S_ISLNK(mode)
        or not stat.S_ISREG(mode)
        or base_raw != current_raw
        or current_raw != worktree_raw
        or sha256(base_raw).hexdigest() != expected_sha256
    ):
        _fail(f"bound candidate-v2 API bytes differ: {relative_path}")


def _validate_recovery_receipt(
    value: object,
    *,
    repository: adapter.SubprocessGitRepositoryV1,
    current_head: str,
) -> tuple[dict[str, object], str]:
    receipt = _mapping(value, label="tracked recovery publication receipt")
    if receipt != _EXPECTED_RECOVERY_RECEIPT:
        _fail("tracked recovery publication receipt differs from the fixed receipt")
    if (
        receipt.get("schema_version") != RECOVERY_RECEIPT_SCHEMA
        or receipt.get("complete") is not True
        or receipt.get("publication", {}).get("complete") is not True
        or receipt.get("publication", {}).get("outer_published_last") is not True
        or receipt.get("independent_reopen", {}).get("complete") is not True
        or receipt.get("independent_reopen", {}).get("cloud_mutation_performed") is not False
        or receipt.get("authority") != {
            "downstream_pin_ready": True,
            "realized_outcome_authority": False,
            "production_promotion_authority": False,
        }
        or receipt.get("outcome_columns_read") != []
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("world_matrix_bodies_read") is not False
        or receipt.get("world_schedule_bodies_read") is not False
    ):
        _fail("tracked recovery publication receipt authority differs")
    outer = _identity(
        receipt.get("outer_attestation_identity"),
        label="tracked recovery outer identity",
    )
    if outer != _EXPECTED_RECOVERY_RECEIPT["outer_attestation_identity"]:
        _fail("tracked recovery outer identity differs")
    outer_sha = receipt.get("outer_attestation_sha256")
    if type(outer_sha) is not str or _SHA256.fullmatch(outer_sha) is None:
        _fail("tracked recovery outer internal hash differs")
    for field in ("publication_commit_sha", "implementation_commit_sha"):
        commit = receipt.get(field)
        if type(commit) is not str or _COMMIT.fullmatch(commit) is None:
            _fail(f"tracked recovery {field} differs")
        recovery.require_git_ancestor_v1(
            repository,
            ancestor_commit_sha=commit,
            descendant_commit_sha=current_head,
            label=f"tracked-recovery-{field}-to-current-head",
        )
    return outer, outer_sha


def _prepare_local_context(repository_root: Path) -> LocalAuthorityContextV2:
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        _fail("repository root must be one explicit absolute path")
    if repository_root.is_symlink():
        _fail("repository root must not be a symlink")
    try:
        resolved_root = repository_root.resolve(strict=True)
    except OSError as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            "repository root does not exist"
        ) from exc
    if resolved_root != repository_root or not repository_root.is_dir():
        _fail("repository root must be one canonical directory")

    repository = adapter.SubprocessGitRepositoryV1(repository_root)
    try:
        clean_head = repository.require_current_clean_head()
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            "candidate publication requires a wholly tracked-clean worktree"
        ) from exc
    _require_detached_head(repository)
    try:
        origin_main = _git_commit(
            repository._run(
                ["rev-parse", "--verify", recovery.DURABLE_REMOTE_REF],
                label="origin/main",
            ),
            label="origin/main",
        )
    except Exception as exc:
        if isinstance(exc, RunCorpusR6FixedG0CandidateAuthorityV2Error):
            raise
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            "origin/main resolution failed"
        ) from exc
    if clean_head != origin_main:
        _fail("clean detached HEAD must equal origin/main exactly")
    recovery.require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=BOUND_API_COMMIT,
        descendant_commit_sha=clean_head,
        label="bound-candidate-v2-API-to-current-head",
    )
    _require_bound_api_signatures()
    for relative_path, expected_hash in _BOUND_FILES.items():
        _require_unchanged_bound_file(
            repository_root=repository_root,
            repository=repository,
            current_head=clean_head,
            relative_path=relative_path,
            expected_sha256=expected_hash,
        )
    module_origins = _verify_module_origins(repository_root)

    operator_file = repository_root / OPERATOR_PATH
    receipt_file = repository_root / RECOVERY_RECEIPT_PATH
    try:
        operator_mode = operator_file.lstat().st_mode
        receipt_mode = receipt_file.lstat().st_mode
        operator_raw = operator_file.read_bytes()
        tracked_operator_raw = repository.read_tracked(clean_head, OPERATOR_PATH)
        receipt_raw = receipt_file.read_bytes()
        tracked_receipt_raw = repository.read_tracked(clean_head, RECOVERY_RECEIPT_PATH)
        base_receipt_raw = repository.read_tracked(
            BOUND_API_COMMIT, RECOVERY_RECEIPT_PATH
        )
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            "operator/recovery receipt tracked-byte resolution failed"
        ) from exc
    if (
        stat.S_ISLNK(operator_mode)
        or not stat.S_ISREG(operator_mode)
        or operator_raw != tracked_operator_raw
    ):
        _fail("candidate operator must be tracked at the clean current HEAD")
    if (
        stat.S_ISLNK(receipt_mode)
        or not stat.S_ISREG(receipt_mode)
        or receipt_raw != tracked_receipt_raw
        or receipt_raw != base_receipt_raw
        or len(receipt_raw) != RECOVERY_RECEIPT_BYTES
        or sha256(receipt_raw).hexdigest() != RECOVERY_RECEIPT_FILE_SHA256
    ):
        _fail("tracked recovery publication receipt bytes differ")
    outer_identity, outer_sha = _validate_recovery_receipt(
        _parse_strict_json(receipt_raw, label="tracked recovery publication receipt"),
        repository=repository,
        current_head=clean_head,
    )
    return LocalAuthorityContextV2(
        repository_root=repository_root,
        repository=repository,
        clean_head=clean_head,
        origin_main=origin_main,
        module_origins=module_origins,
        recovery_receipt_file={
            "relative_path": RECOVERY_RECEIPT_PATH,
            "sha256": RECOVERY_RECEIPT_FILE_SHA256,
            "bytes": RECOVERY_RECEIPT_BYTES,
        },
        catalog_recovery_outer_identity=outer_identity,
        catalog_recovery_outer_attestation_sha256=outer_sha,
    )


def _same_root(context: LocalAuthorityContextV2, value: Path) -> None:
    if not isinstance(value, Path) or value.resolve() != context.repository_root:
        _fail("candidate implementation callback repository root differs")


def _git_callbacks(
    context: LocalAuthorityContextV2,
) -> tuple[
    Callable[[Path], str],
    Callable[[Path, str, str], bytes],
    Callable[[Path, Sequence[str]], bytes],
]:
    def git_head(root: Path) -> str:
        _same_root(context, root)
        try:
            observed = context.repository.require_current_clean_head()
        except Exception as exc:
            raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
                "candidate implementation current HEAD recheck failed"
            ) from exc
        if observed != context.clean_head:
            _fail("candidate implementation current HEAD changed during operation")
        return observed

    def git_blob(root: Path, commit: str, relative_path: str) -> bytes:
        _same_root(context, root)
        return context.repository.read_tracked(commit, relative_path)

    def git_status(root: Path, relative_paths: Sequence[str]) -> bytes:
        _same_root(context, root)
        paths = list(relative_paths)
        if (
            not paths
            or any(
                type(path) is not str
                or not path
                or path.startswith("/")
                or ".." in Path(path).parts
                for path in paths
            )
        ):
            _fail("candidate implementation status paths differ")
        return context.repository._run(
            ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
            label="candidate implementation status",
        )

    return git_head, git_blob, git_status


class ExactGCSStoreV2:
    """Generation-exact read/create-once GCS transport with no broad APIs."""

    def __init__(self, client: object) -> None:
        self._client = client

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if type(uri) is not str or not uri.startswith("gs://"):
            _fail("candidate operator object URI is not gs://")
        bucket, marker, name = uri[5:].partition("/")
        if (
            not marker
            or not bucket
            or not name
            or name.endswith("/")
            or "//" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            _fail("candidate operator object URI differs")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="candidate operator exact read")
        bucket, name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        raw = blob.download_as_bytes(
            if_generation_match=generation,
            timeout=300,
            retry=None,
        )
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("candidate operator generation-exact read differs")
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("candidate operator create-once bytes differ")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                timeout=300,
                retry=None,
            )
        except Exception as exc:
            if exc.__class__.__name__ in {"Conflict", "PreconditionFailed"}:
                raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
                    "candidate output already exists; overwrite/retry is forbidden"
                ) from exc
            raise
        generation = getattr(blob, "generation", None)
        if generation is None:
            _fail("candidate create-once publication lacks a generation")
        return _identity(
            {
                "uri": uri,
                "generation": str(generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            label="candidate create-once identity",
        )


StoreFactory = Callable[[str], ExactGCSStoreV2]


def _default_store_factory(project: str) -> ExactGCSStoreV2:
    # Deliberately lazy: every local/Git/receipt check must finish first.
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            "google-cloud-storage is required only after local validation"
        ) from exc
    return ExactGCSStoreV2(storage.Client(project=project))


class CountingExactReaderV2:
    def __init__(self, read_exact: Callable[[Mapping[str, object]], bytes]) -> None:
        self._read_exact = read_exact
        self.count = 0

    def __call__(self, identity: Mapping[str, object]) -> bytes:
        raw = self._read_exact(identity)
        self.count += 1
        return raw


def _expected_publication_uris(run_id: str) -> tuple[str, ...]:
    prefix = release.output_prefix_for_run_v2(run_id)
    artifacts: list[str] = []
    sidecars: list[str] = []
    receipts: list[str] = []
    for ordinal in range(source.TASK_COUNT):
        slate = catalog.expected_slate_for_source_task(ordinal)
        base = f"{prefix}source-task-{ordinal:02d}-{slate['slate_id']}/"
        artifacts.append(f"{base}accepted-candidates.json")
        sidecars.append(f"{base}{release.LINEAGE_FILENAME}")
        receipts.append(f"{base}{release.SLATE_RECEIPT_FILENAME}")
    return tuple(
        [
            *artifacts,
            *sidecars,
            *receipts,
            f"{prefix}{release.CANDIDATE_RELEASE_FILENAME}",
            f"{prefix}{release.PANEL_RECEIPT_FILENAME}",
            f"{prefix}{release.ROOT_FILENAME}",
        ]
    )


class PublicationAuditV2:
    """Allow only the fixed 165-call create-once sequence."""

    def __init__(
        self,
        *,
        run_id: str,
        publish_create_once: Callable[[str, bytes], Mapping[str, object]],
    ) -> None:
        if not callable(publish_create_once):
            _fail("candidate publication callback differs")
        self.expected_uris = _expected_publication_uris(run_id)
        if len(self.expected_uris) != release.TOTAL_OBJECT_COUNT:
            _fail("candidate publication plan is not exactly 165 objects")
        self._publish_create_once = publish_create_once
        self.attempted_uris: list[str] = []
        self.successful_identities: list[dict[str, object]] = []
        self.failed_uri: str | None = None

    @property
    def root_published(self) -> bool:
        return bool(
            self.successful_identities
            and self.successful_identities[-1]["uri"] == self.expected_uris[-1]
        )

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        ordinal = len(self.attempted_uris)
        if ordinal >= len(self.expected_uris):
            _fail("candidate publisher attempted more than 165 objects")
        expected_uri = self.expected_uris[ordinal]
        legacy_root = expected_uri.removesuffix(release.ROOT_FILENAME) + (
            "candidate-authority-release.json"
        )
        if uri == legacy_root or uri != expected_uri:
            _fail(f"candidate publication URI/order differs at ordinal {ordinal}")
        if type(raw) is not bytes or not raw:
            _fail(f"candidate publication bytes differ at ordinal {ordinal}")
        parsed = _parse_strict_json(raw, label=f"publication object[{ordinal}]")
        if canonical_json_bytes(parsed) != raw:
            _fail(f"publication object[{ordinal}] is not canonical JSON")
        self.attempted_uris.append(uri)
        try:
            published = self._publish_create_once(uri, raw)
        except Exception:
            self.failed_uri = uri
            raise
        identity = _identity(published, label=f"published object[{ordinal}]")
        if (
            identity["uri"] != uri
            or identity["sha256"] != sha256(raw).hexdigest()
            or identity["bytes"] != len(raw)
        ):
            self.failed_uri = uri
            _fail(f"published object[{ordinal}] identity differs")
        self.successful_identities.append(identity)
        return identity

    def require_complete(self, root_identity: Mapping[str, object]) -> None:
        normalized_root = _identity(root_identity, label="published v2 root")
        if (
            tuple(self.attempted_uris) != self.expected_uris
            or len(self.successful_identities) != release.TOTAL_OBJECT_COUNT
            or len({row["uri"] for row in self.successful_identities})
            != release.TOTAL_OBJECT_COUNT
            or normalized_root != self.successful_identities[-1]
            or normalized_root["uri"] != self.expected_uris[-1]
            or self.failed_uri is not None
        ):
            _fail("candidate publication did not complete exact 165/root-last law")


def _validate_candidate_material(value: object) -> dict[str, object]:
    material = _mapping(value, label="derived candidate-v2 material")
    retained_hash = material.get("candidate_material_sha256")
    if (
        type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or retained_hash
        != canonical_sha256({
            key: item
            for key, item in material.items()
            if key != "candidate_material_sha256"
        })
    ):
        _fail("derived candidate-v2 material self-hash differs")
    artifacts = [
        source.validate_accepted_candidate_artifact_v1(item)
        for item in _sequence(
            material.get("candidate_artifacts"), label="candidate artifacts"
        )
    ]
    sidecars = [
        _mapping(item, label=f"candidate lineage sidecar[{ordinal}]")
        for ordinal, item in enumerate(
            _sequence(material.get("lineage_sidecars"), label="lineage sidecars")
        )
    ]
    predecessors = [
        _mapping(item, label=f"candidate predecessor[{ordinal}]")
        for ordinal, item in enumerate(
            _sequence(
                material.get("slate_predecessor_bindings"),
                label="candidate predecessors",
            )
        )
    ]
    if (
        material.get("schema_version") != candidate.MATERIAL_SCHEMA
        or material.get("task_count") != source.TASK_COUNT
        or material.get("arm_result_count")
        != source.TASK_COUNT * candidate_v1.EXPECTED_ARM_COUNT
        or len(artifacts) != source.TASK_COUNT
        or len(sidecars) != source.TASK_COUNT
        or len(predecessors) != source.TASK_COUNT
        or material.get("candidate_artifact_manifest_sha256")
        != canonical_sha256(artifacts)
        or material.get("lineage_sidecar_manifest_sha256")
        != canonical_sha256(sidecars)
        or material.get("slate_predecessor_manifest_sha256")
        != canonical_sha256(predecessors)
        or material.get("catalog_inner_object_count") != 110
        or material.get("candidate_filter_applied") is not False
        or material.get("selected_rosters_used_as_population") is not False
        or material.get("outcome_columns_read") != []
        or material.get("uses_realized_outcomes") is not False
        or any(material.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
    ):
        _fail("derived candidate-v2 material census/policy differs")
    for ordinal, (artifact, sidecar) in enumerate(zip(artifacts, sidecars, strict=True)):
        sidecar_hash = sidecar.get("candidate_lineage_sidecar_sha256")
        if (
            artifact.get("source_task_ordinal") != ordinal
            or int(artifact.get("candidate_count", 0)) < source.ENTRY_BUDGET
            or sidecar.get("schema_version") != candidate_v1.LINEAGE_SIDECAR_SCHEMA
            or sidecar.get("source_task_ordinal") != ordinal
            or sidecar.get("candidate_count") != artifact.get("candidate_count")
            or type(sidecar_hash) is not str
            or _SHA256.fullmatch(sidecar_hash) is None
            or sidecar_hash
            != canonical_sha256({
                key: item
                for key, item in sidecar.items()
                if key != "candidate_lineage_sidecar_sha256"
            })
        ):
            _fail(f"derived candidate-v2 slate[{ordinal}] differs")
    return material


def _context_fields(context: LocalAuthorityContextV2) -> dict[str, object]:
    return {
        "repository_root": str(context.repository_root),
        "clean_detached_head": context.clean_head,
        "origin_main": context.origin_main,
        "head_equals_origin_main": context.clean_head == context.origin_main,
        "whole_worktree_tracked_clean": True,
        "module_origins": dict(context.module_origins),
        "bound_api_commit": BOUND_API_COMMIT,
        "bound_candidate_core_sha256": BOUND_CANDIDATE_CORE_SHA256,
        "bound_candidate_release_sha256": BOUND_CANDIDATE_RELEASE_SHA256,
        "recovery_publication_receipt_file": dict(context.recovery_receipt_file),
        "catalog_recovery_outer_identity": dict(
            context.catalog_recovery_outer_identity
        ),
        "catalog_recovery_outer_attestation_sha256": (
            context.catalog_recovery_outer_attestation_sha256
        ),
        "catalog_recovery_outer_derived_only_from_tracked_receipt": True,
    }


def _no_outcome_fields() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "realized_outcome_bodies_read": False,
        "historical_grader_outcome_sources_read": False,
        "warehouse_outcome_sources_read": False,
        "world_matrix_bodies_read": False,
        "outcome_data_accessed": False,
    }


def _failure_receipt(
    *,
    operation: str,
    run_id: str,
    project: str,
    context: LocalAuthorityContextV2,
    audit: PublicationAuditV2,
    read_count: int,
    error: BaseException,
) -> dict[str, object]:
    return _with_hash(
        {
            "schema_version": OPERATOR_FAILURE_SCHEMA,
            "operation": operation,
            "run_id": run_id,
            "project": project,
            **_context_fields(context),
            "generation_exact_read_count": read_count,
            "create_once_attempt_count": len(audit.attempted_uris),
            "create_once_success_count": len(audit.successful_identities),
            "failed_uri": audit.failed_uri,
            "v2_root_published": audit.root_published,
            "legacy_v1_root_published": False,
            "cloud_mutation_performed": bool(audit.successful_identities),
            "storage_listing_performed": False,
            "storage_overwrite_performed": False,
            "storage_delete_performed": False,
            "unrelated_cloud_mutation_performed": False,
            "graph_mutation_performed": False,
            "deployment_performed": False,
            **_no_outcome_fields(),
            "error_type": type(error).__name__,
            "complete": False,
        },
        field="operator_failure_sha256",
    )


def _derive_material(
    *,
    context: LocalAuthorityContextV2,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    git_head, git_blob, git_status = _git_callbacks(context)
    try:
        material = candidate.derive_fixed_g0_candidate_material_v2(
            repository_root=context.repository_root,
            catalog_recovery_outer_identity=(
                context.catalog_recovery_outer_identity
            ),
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
        validated = _validate_candidate_material(material)
        if (
            validated.get("catalog_recovery_outer_identity")
            != context.catalog_recovery_outer_identity
            or validated.get("catalog_recovery_outer_attestation_sha256")
            != context.catalog_recovery_outer_attestation_sha256
        ):
            _fail("derived candidate-v2 material recovery outer binding differs")
        return validated
    except RunCorpusR6FixedG0CandidateAuthorityV2Error:
        raise
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            f"real read-only candidate-v2 material derivation failed: {exc}"
        ) from exc


def run_prepublish_production_v2(
    *,
    run_id: object,
    project: object,
    repository_root: Path,
    execute: object,
) -> dict[str, object]:
    """Derive and validate all 54 candidate artifacts without any write API."""

    retained_run_id = _run_id(run_id)
    retained_project = _project(project)
    _execute(execute, label="prepublish")
    context = _prepare_local_context(repository_root)
    store = _default_store_factory(retained_project)
    reader = CountingExactReaderV2(store.read_exact)
    material = _derive_material(context=context, read_exact=reader)
    artifacts = _sequence(material["candidate_artifacts"], label="candidate artifacts")
    return _with_hash(
        {
            "schema_version": OPERATOR_RECEIPT_SCHEMA,
            "operation": "prepublish",
            "run_id": retained_run_id,
            "project": retained_project,
            **_context_fields(context),
            "candidate_material_sha256": material["candidate_material_sha256"],
            "candidate_artifact_manifest_sha256": material[
                "candidate_artifact_manifest_sha256"
            ],
            "task_count": len(artifacts),
            "validated_source_task_ordinals": list(range(source.TASK_COUNT)),
            "arm_result_count": material["arm_result_count"],
            "total_candidate_count": sum(
                int(_mapping(item, label="candidate artifact")["candidate_count"])
                for item in artifacts
            ),
            "generation_exact_read_count": reader.count,
            "write_capability_exposed": False,
            "cloud_mutation_performed": False,
            "storage_listing_performed": False,
            "storage_overwrite_performed": False,
            "storage_delete_performed": False,
            "unrelated_cloud_mutation_performed": False,
            "graph_mutation_performed": False,
            "deployment_performed": False,
            **_no_outcome_fields(),
            "complete": True,
        },
        field="operator_receipt_sha256",
    )


def run_publish_production_v2(
    *,
    run_id: object,
    project: object,
    repository_root: Path,
    execute: object,
    confirm_165_object_publication: object,
) -> dict[str, object]:
    """Publish the sole fixed candidate-v2 authority create-once/root-last."""

    retained_run_id = _run_id(run_id)
    retained_project = _project(project)
    _execute(execute, label="publish")
    _execute(
        confirm_165_object_publication,
        label="publish 165-object confirmation",
    )
    context = _prepare_local_context(repository_root)
    store = _default_store_factory(retained_project)
    reader = CountingExactReaderV2(store.read_exact)
    audit = PublicationAuditV2(
        run_id=retained_run_id,
        publish_create_once=store.publish_create_once,
    )
    git_head, git_blob, git_status = _git_callbacks(context)
    try:
        root, root_identity = (
            release.publish_fixed_g0_candidate_authority_release_v2(
                run_id=retained_run_id,
                repository_root=context.repository_root,
                catalog_recovery_outer_identity=(
                    context.catalog_recovery_outer_identity
                ),
                read_exact=reader,
                publish_create_once=audit.publish_create_once,
                git_head=git_head,
                git_blob=git_blob,
                git_status=git_status,
            )
        )
        audit.require_complete(root_identity)
        reopened = release.reopen_fixed_g0_candidate_authority_release_v2(
            root_identity,
            repository_root=context.repository_root,
            read_exact=reader,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
        if (
            reopened.root != root
            or reopened.root_identity != _identity(
                root_identity, label="published candidate-v2 root"
            )
            or reopened.root.get("catalog_recovery_outer_identity")
            != context.catalog_recovery_outer_identity
        ):
            _fail("independent candidate-v2 publication reopen differs")
    except Exception as exc:
        partial = _failure_receipt(
            operation="publish",
            run_id=retained_run_id,
            project=retained_project,
            context=context,
            audit=audit,
            read_count=reader.count,
            error=exc,
        )
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            f"candidate-v2 publication/reopen failed: {exc}",
            partial_receipt=partial,
        ) from exc
    normalized_root_identity = _identity(
        root_identity, label="published candidate-v2 root"
    )
    return _with_hash(
        {
            "schema_version": OPERATOR_RECEIPT_SCHEMA,
            "operation": "publish",
            "run_id": retained_run_id,
            "project": retained_project,
            **_context_fields(context),
            "candidate_authority_root_identity": normalized_root_identity,
            "candidate_authority_release_sha256": root[
                "candidate_authority_release_sha256"
            ],
            "task_count": root["task_count"],
            "arm_result_count": root["arm_result_count"],
            "create_once_attempt_count": len(audit.attempted_uris),
            "create_once_success_count": len(audit.successful_identities),
            "published_total_object_count": release.TOTAL_OBJECT_COUNT,
            "v2_root_published_last": True,
            "legacy_v1_root_published": False,
            "independent_full_v2_reopen_complete": True,
            "generation_exact_read_count": reader.count,
            "write_capability_exposed_only_as_fixed_create_once_sequence": True,
            "cloud_mutation_performed": True,
            "storage_listing_performed": False,
            "storage_overwrite_performed": False,
            "storage_delete_performed": False,
            "unrelated_cloud_mutation_performed": False,
            "graph_mutation_performed": False,
            "deployment_performed": False,
            **_no_outcome_fields(),
            "complete": True,
        },
        field="operator_receipt_sha256",
    )


def _load_v2_root_identity_file(path: Path) -> tuple[dict[str, object], str]:
    if not isinstance(path, Path) or not path.is_absolute():
        _fail("v2 root identity file must be one explicit absolute path")
    if path.is_symlink() or not path.is_file():
        _fail("v2 root identity file must be one regular non-symlink file")
    raw = path.read_bytes()
    framed = raw[:-1] if raw.endswith(b"\n") else raw
    if raw not in {framed, framed + b"\n"}:
        _fail("v2 root identity file framing differs")
    identity_value = _parse_strict_json(framed, label="v2 root identity file")
    if canonical_json_bytes(identity_value) != framed:
        _fail("v2 root identity file is not canonical JSON")
    if set(identity_value) != {"uri", "generation", "sha256", "bytes"}:
        _fail("v2 root identity file must directly contain only one identity")
    identity = _identity(identity_value, label="v2 root identity file")
    match = _V2_ROOT_URI.fullmatch(str(identity["uri"]))
    if match is None:
        _fail("v2 root identity URI differs; legacy v1 root rejected")
    return identity, match.group("run_id")


def run_reopen_production_v2(
    *,
    root_identity_file: Path,
    project: object,
    repository_root: Path,
    execute: object,
) -> dict[str, object]:
    """Read-only full v2 exact reopen from one generation-pinned identity file."""

    retained_project = _project(project)
    _execute(execute, label="reopen")
    root_identity, run_id = _load_v2_root_identity_file(root_identity_file)
    context = _prepare_local_context(repository_root)
    store = _default_store_factory(retained_project)
    reader = CountingExactReaderV2(store.read_exact)
    git_head, git_blob, git_status = _git_callbacks(context)
    try:
        reopened = release.reopen_fixed_g0_candidate_authority_release_v2(
            root_identity,
            repository_root=context.repository_root,
            read_exact=reader,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise RunCorpusR6FixedG0CandidateAuthorityV2Error(
            f"independent candidate-v2 exact reopen failed: {exc}"
        ) from exc
    root = reopened.root
    if (
        reopened.root_identity != root_identity
        or root.get("schema_version") != release.RELEASE_SCHEMA
        or root.get("complete") is not True
        or root.get("run_id") != run_id
        or root.get("catalog_recovery_outer_identity")
        != context.catalog_recovery_outer_identity
        or root.get("catalog_recovery_outer_attestation_sha256")
        != context.catalog_recovery_outer_attestation_sha256
    ):
        _fail("independently reopened candidate-v2 root authority differs")
    return _with_hash(
        {
            "schema_version": OPERATOR_RECEIPT_SCHEMA,
            "operation": "reopen",
            "run_id": run_id,
            "project": retained_project,
            **_context_fields(context),
            "candidate_authority_root_identity": root_identity,
            "candidate_authority_release_sha256": root[
                "candidate_authority_release_sha256"
            ],
            "task_count": root["task_count"],
            "arm_result_count": root["arm_result_count"],
            "generation_exact_read_count": reader.count,
            "full_v2_predecessor_replay_complete": True,
            "write_capability_exposed": False,
            "cloud_mutation_performed": False,
            "storage_listing_performed": False,
            "storage_overwrite_performed": False,
            "storage_delete_performed": False,
            "unrelated_cloud_mutation_performed": False,
            "graph_mutation_performed": False,
            "deployment_performed": False,
            **_no_outcome_fields(),
            "complete": True,
        },
        field="operator_receipt_sha256",
    )


def _emit(value: Mapping[str, object]) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value) + b"\n")
    sys.stdout.buffer.flush()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guarded real fixed-G0 candidate-authority v2 operator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepublish = subparsers.add_parser("prepublish")
    prepublish.add_argument("--run-id", required=True)
    prepublish.add_argument("--project", required=True)
    prepublish.add_argument("--repository-root", type=Path, required=True)
    prepublish.add_argument("--execute", action="store_true")

    publish = subparsers.add_parser("publish")
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--project", required=True)
    publish.add_argument("--repository-root", type=Path, required=True)
    publish.add_argument("--execute", action="store_true")
    publish.add_argument(
        "--confirm-165-object-publication", action="store_true"
    )

    reopen = subparsers.add_parser("reopen")
    reopen.add_argument("--root-identity-file", type=Path, required=True)
    reopen.add_argument("--project", required=True)
    reopen.add_argument("--repository-root", type=Path, required=True)
    reopen.add_argument("--execute", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "prepublish":
            result = run_prepublish_production_v2(
                run_id=args.run_id,
                project=args.project,
                repository_root=args.repository_root,
                execute=args.execute,
            )
        elif args.command == "publish":
            result = run_publish_production_v2(
                run_id=args.run_id,
                project=args.project,
                repository_root=args.repository_root,
                execute=args.execute,
                confirm_165_object_publication=(
                    args.confirm_165_object_publication
                ),
            )
        else:
            result = run_reopen_production_v2(
                root_identity_file=args.root_identity_file,
                project=args.project,
                repository_root=args.repository_root,
                execute=args.execute,
            )
    except RunCorpusR6FixedG0CandidateAuthorityV2Error as exc:
        failure = exc.partial_receipt or _with_hash(
            {
                "schema_version": OPERATOR_FAILURE_SCHEMA,
                "operation": str(args.command),
                "error_type": type(exc).__name__,
                "complete": False,
                "cloud_mutation_performed": False,
                "unrelated_cloud_mutation_performed": False,
                **_no_outcome_fields(),
            },
            field="operator_failure_sha256",
        )
        _emit(failure)
        return 1
    _emit(result)
    return 0


__all__ = [
    "ExactGCSStoreV2",
    "LocalAuthorityContextV2",
    "OPERATOR_FAILURE_SCHEMA",
    "OPERATOR_RECEIPT_SCHEMA",
    "PROJECT",
    "PublicationAuditV2",
    "RunCorpusR6FixedG0CandidateAuthorityV2Error",
    "canonical_json_bytes",
    "main",
    "run_prepublish_production_v2",
    "run_publish_production_v2",
    "run_reopen_production_v2",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
