"""Reopen-first, bounded publication runner for pre-lock lineage Phase 1.

This module is default-off and intentionally has no CLI registration.  One
explicit invocation may write only five allowlisted objects beneath the fixed
production bucket/prefix.  The first object is a complete capture authority,
so a later-clock retry can resume after every publication boundary without
regenerating the lineup book.  The fifth object is a root-last manifest that
binds and exact-reopens the other four provider generations.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Protocol

import numpy as np
import pulp

from ..config import settings
from ..research.effective_policy_rule_inventory import (
    generate_effective_policy_rule_inventory_v6,
)
from ..research.prelock_lineage_graph_v2 import (
    CREATE_ONCE_PUBLICATION_MODE,
    SIDECAR_PROVIDER_RECEIPT_SCHEMA,
    canonical_projection_json_bytes,
    project_prelock_lineage_summary_v2,
    reopen_prelock_lineage_summary_v2,
)
from .prelock_candidate_lineage_v1 import (
    canonical_json_bytes,
    canonical_sha256,
    validate_prelock_candidate_lineage_v1,
)
from .prelock_input_boundary_v1 import (
    build_prelock_input_read_manifest_v1,
    enforced_prelock_bigquery_boundary_v1,
)
from .prelock_lineage_runtime_v2 import (
    SEED_LABELS,
    build_capture_authority_v2,
    build_salary_snapshot_v2,
    build_sidecar_from_capture_v2,
    canonical_selector_matrix_bytes,
    selected_roster_order,
    validate_capture_authority_v2,
)
from .prelock_model_artifact_authority_v1 import ModelArtifactAuthority
from .production_policy import ADOPTED_CLASSIC_POLICY
from .week1_operating_book_suite_adapter import (
    BASE_RETRIEVAL_ID,
    BASE_SELECTION_ID,
)

VERSION: Final = "prospective-prelock-lineage-shadow/v2"
FINAL_MANIFEST_SCHEMA: Final = "prelock-lineage-final-manifest/v2"
EXECUTION_RECEIPT_SCHEMA: Final = "prelock-lineage-execution-receipt/v1"
ADAPTER_MANIFEST_SCHEMA: Final = "prelock-lineage-adapter-manifest/v2"
ENTRY_BUDGET: Final = 80
OBJECT_NAMES: Final[Mapping[str, str]] = {
    "capture-authority": "capture-authority.json",
    "selector-matrix": "selector-matrix.raw",
    "candidate-lineage-sidecar": "candidate-lineage.json",
    "aggregate-graph-projection": "graph-summary-v2.json",
    "final-manifest": "final-manifest.json",
}
_PREDECESSOR_ROLES: Final = tuple(
    role for role in OBJECT_NAMES if role != "final-manifest"
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_DIGEST: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT: Final = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ADAPTER_PATHS: Final = (
    "pyproject.toml",
    "src/nfl_dfs/bq.py",
    "src/nfl_dfs/backtest/engine.py",
    "src/nfl_dfs/config.py",
    "src/nfl_dfs/inference/generation_exposure.py",
    "src/nfl_dfs/inference/live_lineups.py",
    "src/nfl_dfs/inference/multiseed_portfolio.py",
    "src/nfl_dfs/inference/prelock_candidate_lineage_v1.py",
    "src/nfl_dfs/inference/prelock_lineage_runtime_v2.py",
    "src/nfl_dfs/inference/prelock_lineage_settlement_v2.py",
    "src/nfl_dfs/inference/prelock_input_boundary_v1.py",
    "src/nfl_dfs/inference/prelock_model_artifact_authority_v1.py",
    "src/nfl_dfs/inference/production_policy.py",
    "src/nfl_dfs/inference/prospective_prelock_lineage_shadow_v2.py",
    "src/nfl_dfs/inference/week1_operating_book_suite_adapter.py",
    "src/nfl_dfs/models/components.py",
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/optimizer/export.py",
    "src/nfl_dfs/optimizer/paid_classic_book_v2.py",
    "src/nfl_dfs/research/corpus_graph_vnext_contracts.py",
    "src/nfl_dfs/research/effective_policy_rule_inventory.py",
    "src/nfl_dfs/research/prelock_lineage_graph_v2.py",
)


class ProspectivePrelockLineageShadowV2Error(ValueError):
    """The bounded pre-lock runner or one immutable object failed closed."""


def _fail(message: str) -> None:
    raise ProspectivePrelockLineageShadowV2Error(message)


def _aware(value: datetime | str, *, label: str) -> datetime:
    if isinstance(value, str):
        try:
            retained = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ProspectivePrelockLineageShadowV2Error(f"{label} is invalid") from exc
    elif isinstance(value, datetime):
        retained = value
    else:
        _fail(f"{label} is not a timestamp")
    if retained.tzinfo is None or retained.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    return retained.astimezone(UTC)


def _seconds(value: datetime | str, *, mode: str = "floor") -> str:
    retained = _aware(value, label="timestamp")
    if mode == "ceil" and retained.microsecond:
        retained = retained.replace(microsecond=0) + timedelta(seconds=1)
    elif mode == "floor":
        retained = retained.replace(microsecond=0)
    elif mode != "ceil":
        _fail("timestamp precision mode differs")
    return retained.strftime("%Y-%m-%dT%H:%M:%SZ")


def _provider_time(value: datetime) -> str:
    retained = _aware(value, label="provider creation time")
    return retained.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _closed_json(raw: bytes, *, label: str) -> dict[str, object]:
    def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProspectivePrelockLineageShadowV2Error(
            f"{label} is not canonical JSON"
        ) from exc
    if not isinstance(value, Mapping) or canonical_json_bytes(value) != raw:
        _fail(f"{label} bytes are not the canonical JSON encoding")
    return dict(value)


def lineage_adapter_manifest_v2(
    repository: Path | None = None,
) -> dict[str, object]:
    """Bind every adapter/helper source not delegated solely to v6."""

    root = repository or Path(__file__).resolve().parents[3]
    files: list[dict[str, object]] = []
    for relative in _ADAPTER_PATHS:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            _fail(f"lineage adapter source is unavailable: {relative}")
        payload = path.read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    body: dict[str, object] = {
        "schema_version": ADAPTER_MANIFEST_SCHEMA,
        "files": files,
        "effective_policy_inventory_required": "v6",
        "transitive_scoring_surface_claimed_here": False,
    }
    body["manifest_sha256"] = canonical_sha256(body)
    return body


def _validate_clean_source_checkout_v1(
    repository: Path,
    *,
    expected_commit: str,
    required_paths: Sequence[str],
) -> None:
    """Require every hashed source to be tracked and clean at the receipt SHA."""

    root = repository.resolve()
    if not root.is_dir() or _COMMIT.fullmatch(expected_commit) is None:
        _fail("source checkout identity is invalid")

    def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
        )

    head = _git("rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.decode("ascii").strip() != expected_commit:
        _fail("execution source commit differs from the checked-out repository")
    paths = sorted(set(required_paths))
    if not paths or any(
        not path or path.startswith("/") or ".." in path.split("/") for path in paths
    ):
        _fail("execution source path census differs")
    tracked = _git("ls-files", "--", *paths)
    tracked_paths = {
        line for line in tracked.stdout.decode("utf-8").splitlines() if line
    }
    if tracked.returncode != 0 or tracked_paths != set(paths):
        _fail("execution source contains an untracked or absent hashed path")
    status = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status.returncode != 0 or status.stdout:
        _fail("execution source checkout is not globally clean")


def _validate_runtime_source_binding_v1(
    repository: Path,
    *,
    expected_commit: str,
    required_paths: Sequence[str],
) -> str:
    """Validate a clean checkout or an image with its embedded revision."""

    root = repository.resolve()
    if not root.is_dir() or _COMMIT.fullmatch(expected_commit) is None:
        _fail("runtime source identity is invalid")
    paths = sorted(set(required_paths))
    if not paths or any(
        not path or path.startswith("/") or ".." in path.split("/") for path in paths
    ):
        _fail("runtime source path census differs")
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        probe = None
    if probe is not None and probe.returncode == 0 and probe.stdout.strip() == b"true":
        _validate_clean_source_checkout_v1(
            root,
            expected_commit=expected_commit,
            required_paths=paths,
        )
        return "git-global-clean-checkout"
    embedded = str(os.environ.get("IMAGE_SOURCE_COMMIT_SHA", "")).strip()
    if embedded != expected_commit:
        _fail("runtime image revision differs from the execution source commit")
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            _fail("runtime image omits a manifest-bound source path")
    return "immutable-image-embedded-revision"


def build_execution_receipt_v1(
    *, image_digest: str, source_commit: str
) -> dict[str, object]:
    """Build a local compute/solver receipt; an immutable image is required."""

    if _IMAGE_DIGEST.fullmatch(image_digest) is None:
        _fail("execution image must be one immutable sha256 digest")
    if _COMMIT.fullmatch(source_commit) is None:
        _fail("execution source commit must be one exact 40-character commit")
    solver_path = Path(pulp.PULP_CBC_CMD(msg=False).path)
    if not solver_path.is_file() or solver_path.is_symlink():
        _fail("CBC solver binary is unavailable or symlinked")
    solver_bytes = solver_path.read_bytes()
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        physical_pages = int(os.sysconf("SC_PHYS_PAGES"))
        memory_bytes = page_size * physical_pages
    except (AttributeError, OSError, ValueError):
        memory_bytes = 0
    body: dict[str, object] = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "image_digest": image_digest,
        "source_commit": source_commit,
        "container_image_immutable": True,
        "solver": {
            "name": "cbc",
            "pulp_version": str(pulp.__version__),
            "binary_sha256": sha256(solver_bytes).hexdigest(),
            "binary_bytes": len(solver_bytes),
        },
        "compute_envelope": {
            "architecture": platform.machine(),
            "operating_system": platform.system(),
            "python_version": platform.python_version(),
            "numpy_version": str(np.__version__),
            "cpu_count": int(os.cpu_count() or 0),
            "memory_bytes": memory_bytes,
        },
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return validate_execution_receipt_v1(body)


def validate_execution_receipt_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("execution receipt is not a mapping")
    item = json.loads(canonical_json_bytes(value))
    fields = {
        "schema_version",
        "image_digest",
        "source_commit",
        "container_image_immutable",
        "solver",
        "compute_envelope",
        "receipt_sha256",
    }
    if set(item) != fields:
        _fail("execution receipt fields differ")
    retained = item.pop("receipt_sha256")
    if (
        item["schema_version"] != EXECUTION_RECEIPT_SCHEMA
        or _IMAGE_DIGEST.fullmatch(str(item["image_digest"])) is None
        or _COMMIT.fullmatch(str(item["source_commit"])) is None
        or item["container_image_immutable"] is not True
        or not isinstance(item["solver"], Mapping)
        or not isinstance(item["compute_envelope"], Mapping)
        or type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or retained != canonical_sha256(item)
    ):
        _fail("execution receipt identity differs")
    solver = item["solver"]
    compute = item["compute_envelope"]
    if set(solver) != {
        "name",
        "pulp_version",
        "binary_sha256",
        "binary_bytes",
    } or set(compute) != {
        "architecture",
        "operating_system",
        "python_version",
        "numpy_version",
        "cpu_count",
        "memory_bytes",
    }:
        _fail("execution solver or compute fields differ")
    if (
        solver["name"] != "cbc"
        or _SHA256.fullmatch(str(solver["binary_sha256"])) is None
        or type(solver["binary_bytes"]) is not int
        or solver["binary_bytes"] < 1
        or any(
            type(compute[key]) is not str or not compute[key]
            for key in (
                "architecture",
                "operating_system",
                "python_version",
                "numpy_version",
            )
        )
        or any(
            type(compute[key]) is not int or compute[key] < 0
            for key in (
                "cpu_count",
                "memory_bytes",
            )
        )
    ):
        _fail("execution solver or compute identity is incomplete")
    return {**item, "receipt_sha256": retained}


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a provider identity")
    item = dict(value)
    fields = {"uri", "generation", "sha256", "bytes", "time_created_utc"}
    if set(item) != fields:
        _fail(f"{label} provider identity fields differ")
    if (
        type(item["uri"]) is not str
        or not item["uri"].startswith("gs://")
        or type(item["generation"]) is not str
        or not item["generation"].isdigit()
        or int(item["generation"]) < 1
        or type(item["sha256"]) is not str
        or _SHA256.fullmatch(item["sha256"]) is None
        or type(item["bytes"]) is not int
        or item["bytes"] < 1
    ):
        _fail(f"{label} provider identity is invalid")
    _aware(str(item["time_created_utc"]), label=f"{label} creation time")
    return item


def _graph_identity(value: Mapping[str, object]) -> dict[str, object]:
    retained = _object_identity(value, label="sidecar object")
    return {key: retained[key] for key in ("uri", "generation", "sha256", "bytes")}


class ClosedObjectStore(Protocol):
    bucket_name: str
    prefix: str
    allowed_names: frozenset[str]

    def try_reopen(
        self, object_name: str
    ) -> tuple[bytes, dict[str, object]] | None: ...

    def create_or_reopen(
        self,
        object_name: str,
        payload: bytes,
        *,
        content_type: str,
        must_precede: datetime,
    ) -> dict[str, object]: ...

    def reopen_exact(
        self, object_name: str, identity: Mapping[str, object]
    ) -> bytes: ...


class GcsClosedObjectStore:
    """GCS implementation with a fixed bucket, prefix, and write set."""

    def __init__(self, storage_client: object, *, prefix: str) -> None:
        if not prefix or prefix.startswith("/") or ".." in prefix.split("/"):
            _fail("closed object prefix is invalid")
        self.bucket_name = settings.gcs_bucket
        self.prefix = prefix.rstrip("/")
        self.allowed_names = frozenset(OBJECT_NAMES.values())
        self._bucket = storage_client.bucket(self.bucket_name)

    def _blob(self, object_name: str):
        if object_name not in self.allowed_names or "/" in object_name:
            _fail("object name is outside the closed write manifest")
        return self._bucket.blob(f"{self.prefix}/{object_name}")

    @staticmethod
    def _not_found(exc: BaseException) -> bool:
        try:
            from google.api_core.exceptions import NotFound
        except ImportError:
            return exc.__class__.__name__ == "NotFound"
        return isinstance(exc, NotFound)

    @staticmethod
    def _precondition_failed(exc: BaseException) -> bool:
        try:
            from google.api_core.exceptions import PreconditionFailed
        except ImportError:
            return exc.__class__.__name__ == "PreconditionFailed"
        return isinstance(exc, PreconditionFailed)

    def try_reopen(self, object_name: str) -> tuple[bytes, dict[str, object]] | None:
        blob = self._blob(object_name)
        try:
            blob.reload()
        except Exception as exc:
            if self._not_found(exc):
                return None
            raise
        generation = str(blob.generation or "")
        if not generation.isdigit() or int(generation) < 1:
            _fail("provider object lacks one exact generation")
        payload = bytes(blob.download_as_bytes(if_generation_match=int(generation)))
        created = getattr(blob, "time_created", None)
        if not isinstance(created, datetime):
            _fail("provider object lacks trusted creation time")
        identity = _object_identity(
            {
                "uri": f"gs://{self.bucket_name}/{self.prefix}/{object_name}",
                "generation": generation,
                "sha256": sha256(payload).hexdigest(),
                "bytes": len(payload),
                "time_created_utc": _provider_time(created),
            },
            label=object_name,
        )
        return payload, identity

    def create_or_reopen(
        self,
        object_name: str,
        payload: bytes,
        *,
        content_type: str,
        must_precede: datetime,
    ) -> dict[str, object]:
        if not isinstance(payload, bytes) or not payload:
            _fail("create-once payload is empty")
        blob = self._blob(object_name)
        try:
            blob.upload_from_string(
                payload,
                content_type=content_type,
                if_generation_match=0,
            )
        except Exception as exc:
            if not self._precondition_failed(exc):
                raise
        reopened = self.try_reopen(object_name)
        if reopened is None:
            _fail("create-once object is absent after upload/reopen")
        existing, identity = reopened
        if existing != payload:
            _fail("create-once object already exists with different bytes")
        if (
            _aware(str(identity["time_created_utc"]), label="provider creation time")
            >= must_precede
        ):
            _fail("create-once provider object was not created before lock")
        return identity

    def reopen_exact(self, object_name: str, identity: Mapping[str, object]) -> bytes:
        expected = _object_identity(identity, label=f"expected {object_name}")
        reopened = self.try_reopen(object_name)
        if reopened is None:
            _fail(f"root-bound object {object_name} is absent")
        payload, observed = reopened
        if observed != expected:
            _fail(f"root-bound object {object_name} provider identity differs")
        return payload


def _sidecar_provider_receipt(
    identity: Mapping[str, object],
) -> dict[str, object]:
    provider = _object_identity(identity, label="sidecar provider object")
    body: dict[str, object] = {
        "schema_version": SIDECAR_PROVIDER_RECEIPT_SCHEMA,
        "publication_mode": CREATE_ONCE_PUBLICATION_MODE,
        "create_once": True,
        "create_once_precondition": "if_generation_match=0",
        "sidecar_identity": _graph_identity(provider),
        # The v1 graph receipt has a whole-second contract.  Ceil is the
        # conservative deterministic projection of fractional provider time:
        # it can never claim publication before GCS actually created it.
        "storage_created_at_utc": _seconds(
            str(provider["time_created_utc"]), mode="ceil"
        ),
        "storage_metadata_authority": "google-cloud-storage-object-metadata",
        "exact_generation_reopened": True,
        "canonical_sidecar_bytes_reopened": True,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def _build_final_manifest(
    *,
    capture: Mapping[str, object],
    objects: Mapping[str, Mapping[str, object]],
    sidecar_frozen_at_utc: str,
    projection_created_at_utc: str,
    graph_release_id: str,
) -> dict[str, object]:
    if set(objects) != set(_PREDECESSOR_ROLES):
        _fail("final manifest predecessor object set differs")
    retained = validate_capture_authority_v2(capture)
    bindings = [
        {
            "role": role,
            "object_name": OBJECT_NAMES[role],
            "identity": _object_identity(objects[role], label=role),
        }
        for role in _PREDECESSOR_ROLES
    ]
    body: dict[str, object] = {
        "schema_version": FINAL_MANIFEST_SCHEMA,
        "run_id": retained["run"]["run_id"],
        "season": retained["run"]["season"],
        "week": retained["run"]["week"],
        "slate_id": retained["run"]["slate_id"],
        "draft_group_id": retained["run"]["draft_group_id"],
        "slate_lock_at_utc": retained["run"]["slate_lock_at_utc"],
        "capture_sha256": retained["capture_sha256"],
        "sidecar_frozen_at_utc": sidecar_frozen_at_utc,
        "projection_created_at_utc": projection_created_at_utc,
        "graph_release_id": graph_release_id,
        "selector_retrieval_preset_bindings": {
            retained["selector_configuration"]["selector_id"]: retained[
                "selector_configuration"
            ]["retrieval_preset_id"]
        },
        "selected_roster_order_sha256": canonical_sha256(
            selected_roster_order(retained)
        ),
        "predecessor_objects": bindings,
        "predecessor_object_count": len(bindings),
        "root_is_fifth_object": True,
        "every_exact_generation_reopened": True,
        "all_objects_provider_created_prelock": True,
        "complete": True,
        "production_enabled": False,
        "graph_mutation_performed": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["manifest_sha256"] = canonical_sha256(body)
    return validate_final_manifest_v2(body)


def validate_final_manifest_v2(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("final manifest is not a mapping")
    item = json.loads(canonical_json_bytes(value))
    fields = {
        "schema_version",
        "run_id",
        "season",
        "week",
        "slate_id",
        "draft_group_id",
        "slate_lock_at_utc",
        "capture_sha256",
        "sidecar_frozen_at_utc",
        "projection_created_at_utc",
        "graph_release_id",
        "selector_retrieval_preset_bindings",
        "selected_roster_order_sha256",
        "predecessor_objects",
        "predecessor_object_count",
        "root_is_fifth_object",
        "every_exact_generation_reopened",
        "all_objects_provider_created_prelock",
        "complete",
        "production_enabled",
        "graph_mutation_performed",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "manifest_sha256",
    }
    if set(item) != fields:
        _fail("final manifest fields differ")
    retained_hash = item.pop("manifest_sha256")
    if (
        item["schema_version"] != FINAL_MANIFEST_SCHEMA
        or type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or retained_hash != canonical_sha256(item)
        or any(
            item[key] is not expected
            for key, expected in {
                "root_is_fifth_object": True,
                "every_exact_generation_reopened": True,
                "all_objects_provider_created_prelock": True,
                "complete": True,
                "production_enabled": False,
                "graph_mutation_performed": False,
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            }.items()
        )
    ):
        _fail("final manifest contract or self-hash differs")
    lock = _aware(str(item["slate_lock_at_utc"]), label="manifest slate lock")
    rows = item["predecessor_objects"]
    if (
        not isinstance(rows, list)
        or item["predecessor_object_count"] != len(_PREDECESSOR_ROLES)
        or len(rows) != len(_PREDECESSOR_ROLES)
        or [row.get("role") for row in rows if isinstance(row, Mapping)]
        != list(_PREDECESSOR_ROLES)
    ):
        _fail("final manifest predecessor census differs")
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "role",
            "object_name",
            "identity",
        }:
            _fail("final manifest predecessor binding fields differ")
        role = str(row["role"])
        if row["object_name"] != OBJECT_NAMES[role]:
            _fail("final manifest predecessor object name differs")
        identity = _object_identity(row["identity"], label=role)
        if (
            _aware(str(identity["time_created_utc"]), label=f"{role} creation time")
            >= lock
        ):
            _fail("final manifest binds a post-lock provider object")
    return {**item, "manifest_sha256": retained_hash}


def _validate_store_boundary(
    object_store: ClosedObjectStore, *, expected_prefix: str
) -> None:
    if (
        object_store.bucket_name != settings.gcs_bucket
        or object_store.prefix != expected_prefix
        or object_store.allowed_names != frozenset(OBJECT_NAMES.values())
    ):
        _fail("object store differs from the fixed bucket/prefix/write manifest")


def _request_scope(
    *,
    run_id: str,
    season: int,
    week: int,
    draft_group_id: int,
    expected_lock: datetime,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "season": season,
        "week": week,
        "slate_id": f"dk-{draft_group_id}",
        "draft_group_id": draft_group_id,
        "slate_lock_at_utc": _seconds(expected_lock),
    }


def _assert_scope(value: Mapping[str, object], request: Mapping[str, object]) -> None:
    if any(value.get(key) != expected for key, expected in request.items()):
        _fail("reopened artifact scope differs from the requested run")


def _reopen_complete(
    *,
    object_store: ClosedObjectStore,
    final_bytes: bytes,
    final_identity: Mapping[str, object],
    request: Mapping[str, object],
) -> dict[str, object]:
    final = validate_final_manifest_v2(
        _closed_json(final_bytes, label="final manifest")
    )
    _assert_scope(final, request)
    bound: dict[str, tuple[bytes, dict[str, object]]] = {}
    for row in final["predecessor_objects"]:
        role = str(row["role"])
        identity = _object_identity(row["identity"], label=role)
        payload = object_store.reopen_exact(str(row["object_name"]), identity)
        bound[role] = (payload, identity)

    capture = validate_capture_authority_v2(
        _closed_json(bound["capture-authority"][0], label="capture authority")
    )
    _assert_scope(capture["run"], request)
    if capture["capture_sha256"] != final["capture_sha256"]:
        _fail("final manifest capture identity differs")
    matrix = canonical_selector_matrix_bytes(
        capture["effective_candidates"]["selector_matrix_archive"]
    )
    if matrix != bound["selector-matrix"][0]:
        _fail("root-bound raw selector matrix differs from capture replay")
    capture_identity = _graph_identity(bound["capture-authority"][1])
    expected_sidecar = build_sidecar_from_capture_v2(
        capture=capture,
        capture_identity=capture_identity,
        frozen_at_utc=str(final["sidecar_frozen_at_utc"]),
    )
    sidecar = validate_prelock_candidate_lineage_v1(
        _closed_json(
            bound["candidate-lineage-sidecar"][0],
            label="candidate lineage sidecar",
        )
    )
    if sidecar != expected_sidecar:
        _fail("root-bound sidecar differs from exact capture replay")
    sidecar_receipt = _sidecar_provider_receipt(bound["candidate-lineage-sidecar"][1])
    bindings = final["selector_retrieval_preset_bindings"]
    reopened_graph = reopen_prelock_lineage_summary_v2(
        projection_bytes=bound["aggregate-graph-projection"][0],
        sidecar=sidecar,
        sidecar_identity=_graph_identity(bound["candidate-lineage-sidecar"][1]),
        selector_retrieval_preset_bindings=bindings,
        graph_release_id=str(final["graph_release_id"]),
        projection_created_at_utc=str(final["projection_created_at_utc"]),
        publication_mode=CREATE_ONCE_PUBLICATION_MODE,
        sidecar_provider_receipt=sidecar_receipt,
    )
    if (
        canonical_projection_json_bytes(reopened_graph)
        != bound["aggregate-graph-projection"][0]
    ):
        _fail("root-bound graph projection differs from exact replay")
    if final["selected_roster_order_sha256"] != canonical_sha256(
        selected_roster_order(capture)
    ):
        _fail("root-bound selected roster order differs")
    return {
        "schema_version": VERSION,
        "complete": True,
        "run_id": final["run_id"],
        "season": final["season"],
        "week": final["week"],
        "draft_group_id": final["draft_group_id"],
        "final_manifest": _object_identity(
            final_identity, label="final manifest object"
        ),
        "final_manifest_sha256": final["manifest_sha256"],
        "selected_roster_order_sha256": final["selected_roster_order_sha256"],
        "all_exact_generations_reopened": True,
        "production_enabled": False,
        "graph_mutation_performed": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }


def run_prelock_lineage_shadow_v2(
    *,
    store: object,
    object_store: ClosedObjectStore,
    run_id: str,
    season: int,
    week: int,
    draft_group_id: int,
    expected_lock_at: datetime | str,
    execution_receipt: Mapping[str, object],
    model_artifact_authority: ModelArtifactAuthority,
    now_factory: Callable[[], datetime] | None = None,
    build_lineups_fn: Callable[..., Sequence[object]] | None = None,
    repository: Path | None = None,
) -> dict[str, object]:
    """Run once or resume exactly; never publish or generate after lock."""

    if _RUN_ID.fullmatch(run_id) is None:
        _fail("run_id is not a path-safe identifier")
    season = int(season)
    week = int(week)
    draft_group_id = int(draft_group_id)
    if season != 2026 or not 1 <= week <= 18 or draft_group_id < 1:
        _fail("pre-lock lineage v2 requires one explicit 2026 classic slate")
    expected_lock = _aware(expected_lock_at, label="expected lock").replace(
        microsecond=0
    )
    prefix = f"prelock-lineage-v1/{season}/week-{week:02d}/{run_id}"
    _validate_store_boundary(object_store, expected_prefix=prefix)
    request = _request_scope(
        run_id=run_id,
        season=season,
        week=week,
        draft_group_id=draft_group_id,
        expected_lock=expected_lock,
    )

    # Complete-root first: this path is read-only and remains legal after lock.
    final_reopen = object_store.try_reopen(OBJECT_NAMES["final-manifest"])
    if final_reopen is not None:
        result = _reopen_complete(
            object_store=object_store,
            final_bytes=final_reopen[0],
            final_identity=final_reopen[1],
            request=request,
        )
        return {**result, "resumed": True, "generation_performed": False}

    def _now() -> datetime:
        value = datetime.now(UTC) if now_factory is None else now_factory()
        return _aware(value, label="lineage shadow clock")

    if _now() >= expected_lock:
        _fail("incomplete pre-lock lineage run cannot write or generate after lock")
    execution = validate_execution_receipt_v1(execution_receipt)
    capture_reopen = object_store.try_reopen(OBJECT_NAMES["capture-authority"])
    generation_performed = False
    returned_book_verified = False
    if capture_reopen is not None:
        capture = validate_capture_authority_v2(
            _closed_json(capture_reopen[0], label="capture authority")
        )
        capture_identity = capture_reopen[1]
        _assert_scope(capture["run"], request)
        if capture["execution_receipt"] != execution:
            _fail("retry execution receipt differs from the immutable capture")
    else:
        root = repository or Path(__file__).resolve().parents[3]
        adapter_manifest = lineage_adapter_manifest_v2(root)
        policy_inventory = generate_effective_policy_rule_inventory_v6(root)
        source_binding_mode = _validate_runtime_source_binding_v1(
            root,
            expected_commit=str(execution["source_commit"]),
            required_paths=[
                *[str(row["path"]) for row in adapter_manifest["files"]],
                *[str(row["path"]) for row in policy_inventory["source_identities"]],
            ],
        )
        policy = ADOPTED_CLASSIC_POLICY
        model_artifacts = model_artifact_authority.freeze(
            purpose_variants={
                "candidate-projection": policy.model_variant,
                "role-belief": policy.role_model_variant,
            },
            expected_member_count=policy.model_ensemble,
            must_precede=expected_lock,
        )
        method_identity = canonical_sha256(
            {
                "effective_policy_inventory_sha256": policy_inventory[
                    "inventory_sha256"
                ],
                "lineage_adapter_manifest_sha256": adapter_manifest["manifest_sha256"],
                "execution_receipt_sha256": execution["receipt_sha256"],
                "model_artifact_manifest_sha256": model_artifacts["manifest_sha256"],
            }
        )
        with enforced_prelock_bigquery_boundary_v1() as salary_boundary:
            salaries = store.classic_salaries(draft_group_id)
        salary_snapshot = build_salary_snapshot_v2(
            salaries,
            draft_group_id=draft_group_id,
            source_table_uri=f"bq://{settings.raw}.dk_salaries",
        )
        if salary_snapshot["slate_lock_at_utc"] != _seconds(expected_lock):
            _fail("expected lock differs from the one-read salary authority")
        bridge = {
            int(key): value
            for key, value in salary_snapshot["internal_to_draftable"].items()
        }
        salary_overrides = {
            int(row["internal_player_id"]): int(row["salary"])
            for row in salary_snapshot["catalog_rows"]
        }
        construction = policy.construction_preset()
        environment = policy.engine_environment(construction_preset=construction)
        environment["PROSPECTIVE_GENERATION_EXPOSURE"] = "1"
        run = {
            "run_id": run_id,
            "run_type": "prospective-lineage-shadow-v2",
            "season": season,
            "week": week,
            "slate_id": f"dk-{draft_group_id}",
            "draft_group_id": draft_group_id,
            "contest_id": None,
            "slate_lock_at_utc": _seconds(expected_lock),
            "capture_started_at_utc": _seconds(_now()),
            "policy_id": policy.policy_id,
            "code_sha256": method_identity,
        }
        native_batches: dict[str, Any] = {}
        callback_capture: list[dict[str, object]] = []
        callback_identity: list[dict[str, object]] = []

        def _native(label: str, batch: object):
            expected_label = SEED_LABELS[len(native_batches)]
            if label != expected_label:
                _fail("native callback order differs from registered R0-R4")
            native_batches[label] = batch
            return batch

        def _effective(batch: object) -> None:
            if callback_capture or set(native_batches) != set(SEED_LABELS):
                _fail("effective callback order or count differs")
            reopened_model_artifacts = model_artifact_authority.reopen_exact(
                model_artifacts
            )
            if reopened_model_artifacts != model_artifacts:
                _fail("post-generation model authority differs from preflight")
            captured = build_capture_authority_v2(
                run=run,
                native_batches=native_batches,
                effective_batch=batch,
                salary_snapshot=salary_snapshot,
                policy_environment=environment,
                effective_policy_inventory=policy_inventory,
                lineage_adapter_manifest=adapter_manifest,
                execution_receipt=execution,
                model_artifact_manifest=model_artifacts,
                model_artifacts_exact_reopened_after_generation=True,
                input_read_boundary=input_read_manifest,
                source_binding_mode=source_binding_mode,
                selector_id=BASE_SELECTION_ID,
                retrieval_preset_id=BASE_RETRIEVAL_ID,
                tail_line=float(policy.tail_line),
                entry_budget=ENTRY_BUDGET,
            )
            payload = canonical_json_bytes(captured)
            identity = object_store.create_or_reopen(
                OBJECT_NAMES["capture-authority"],
                payload,
                content_type="application/json",
                must_precede=expected_lock,
            )
            callback_capture.append(captured)
            callback_identity.append(identity)

        if build_lineups_fn is None:
            from .live_lineups import build_sim_lineups

            build_lineups_fn = build_sim_lineups
        with enforced_prelock_bigquery_boundary_v1() as generation_boundary:
            input_read_manifest = build_prelock_input_read_manifest_v1(
                salary_boundary=salary_boundary,
                generation_boundary=generation_boundary,
            )
            lineups = build_lineups_fn(
                season,
                week,
                n_entries=ENTRY_BUDGET,
                stack=construction.stack,
                tail_line=float(policy.tail_line),
                n_sims=int(environment["MULTISEED_WORLDS_PER_BLOCK"]),
                lev_scale=1.0,
                allowed_ids=set(bridge),
                salary_overrides=salary_overrides,
                theses=None,
                apply_notes=False,
                model_variant=policy.model_variant,
                cand_log_table="",
                cand_log_async=False,
                cand_log_required=False,
                panel_run_id=run_id,
                candidate_run_type=VERSION,
                policy_env=environment,
                construction_preset_receipt=construction.receipt(),
                expected_model_k=policy.model_ensemble,
                belief_model_variant=policy.role_model_variant,
                route_source_policy=False,
                distribution_artifact_spec=None,
                _native_candidate_transform=_native,
                _candidate_capture=_effective,
                _log_ownership_shadow=False,
            )
        generation_performed = True
        if len(callback_capture) != 1 or len(callback_identity) != 1:
            _fail("lineup build did not freeze one complete capture authority")
        capture = callback_capture[0]
        capture_identity = callback_identity[0]
        returned = [sorted(str(value) for value in lineup.ids) for lineup in lineups]
        if returned != selected_roster_order(capture):
            _fail("returned lineup order differs from typed selector replay")
        returned_book_verified = True

    if _now() >= expected_lock:
        _fail("lineage run reached a publication boundary at or after lock")
    capture = validate_capture_authority_v2(capture)
    matrix_bytes = canonical_selector_matrix_bytes(
        capture["effective_candidates"]["selector_matrix_archive"]
    )
    matrix_identity = object_store.create_or_reopen(
        OBJECT_NAMES["selector-matrix"],
        matrix_bytes,
        content_type="application/octet-stream",
        must_precede=expected_lock,
    )
    sidecar_frozen = _seconds(str(capture_identity["time_created_utc"]), mode="floor")
    sidecar = build_sidecar_from_capture_v2(
        capture=capture,
        capture_identity=_graph_identity(capture_identity),
        frozen_at_utc=sidecar_frozen,
    )
    sidecar_identity = object_store.create_or_reopen(
        OBJECT_NAMES["candidate-lineage-sidecar"],
        canonical_json_bytes(sidecar),
        content_type="application/json",
        must_precede=expected_lock,
    )
    sidecar_receipt = _sidecar_provider_receipt(sidecar_identity)
    projection_created = str(sidecar_receipt["storage_created_at_utc"])
    if _aware(projection_created, label="graph projection time") >= expected_lock:
        _fail("conservative graph projection timestamp reaches slate lock")
    bindings = {
        str(capture["selector_configuration"]["selector_id"]): str(
            capture["selector_configuration"]["retrieval_preset_id"]
        )
    }
    graph_release_id = f"prelock:{run_id}"
    projection = project_prelock_lineage_summary_v2(
        sidecar=sidecar,
        sidecar_identity=_graph_identity(sidecar_identity),
        selector_retrieval_preset_bindings=bindings,
        graph_release_id=graph_release_id,
        projection_created_at_utc=projection_created,
        publication_mode=CREATE_ONCE_PUBLICATION_MODE,
        sidecar_provider_receipt=sidecar_receipt,
    )
    graph_identity = object_store.create_or_reopen(
        OBJECT_NAMES["aggregate-graph-projection"],
        canonical_projection_json_bytes(projection),
        content_type="application/json",
        must_precede=expected_lock,
    )
    objects = {
        "capture-authority": capture_identity,
        "selector-matrix": matrix_identity,
        "candidate-lineage-sidecar": sidecar_identity,
        "aggregate-graph-projection": graph_identity,
    }
    # Exact-reopen every predecessor immediately before root publication.
    for role, identity in objects.items():
        object_store.reopen_exact(OBJECT_NAMES[role], identity)
    final = _build_final_manifest(
        capture=capture,
        objects=objects,
        sidecar_frozen_at_utc=sidecar_frozen,
        projection_created_at_utc=projection_created,
        graph_release_id=graph_release_id,
    )
    final_bytes = canonical_json_bytes(final)
    final_identity = object_store.create_or_reopen(
        OBJECT_NAMES["final-manifest"],
        final_bytes,
        content_type="application/json",
        must_precede=expected_lock,
    )
    # The root itself is exact-reopened as the fifth and final object.
    reopened_final = object_store.reopen_exact(
        OBJECT_NAMES["final-manifest"], final_identity
    )
    result = _reopen_complete(
        object_store=object_store,
        final_bytes=reopened_final,
        final_identity=final_identity,
        request=request,
    )
    return {
        **result,
        "resumed": capture_reopen is not None,
        "generation_performed": generation_performed,
        "returned_book_parity_observed": returned_book_verified,
    }


__all__ = [
    "ADAPTER_MANIFEST_SCHEMA",
    "ENTRY_BUDGET",
    "EXECUTION_RECEIPT_SCHEMA",
    "FINAL_MANIFEST_SCHEMA",
    "OBJECT_NAMES",
    "VERSION",
    "GcsClosedObjectStore",
    "ProspectivePrelockLineageShadowV2Error",
    "build_execution_receipt_v1",
    "lineage_adapter_manifest_v2",
    "run_prelock_lineage_shadow_v2",
    "validate_execution_receipt_v1",
    "validate_final_manifest_v2",
]
