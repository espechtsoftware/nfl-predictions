#!/usr/bin/env python3
"""Validate the local-only A7-v2 shared-build source-lineage extension."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
from collections.abc import Callable, Mapping
from hashlib import sha256
import json
import lzma
from pathlib import Path
import re
import subprocess
from typing import Any, Final


ROOT: Final = Path(__file__).resolve().parents[1]
EXTENSION_ID: Final = "20260821-a7-v2-shared-build-source-lineage-v1"
RUN_ID: Final = "20260820-a7-select-ladder-phase-s-incumbent-v2"
BASE_CODE_SHA: Final = "f389f33336868d552220bcc9e6decfe557a85220"
TARGET_CODE_SHA: Final = "2bec2965442b90ec87990fb25f086de9005265dc"
IMAGE_REPOSITORY: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
)
SHARED_IMAGE_TAG: Final = f"{IMAGE_REPOSITORY}:lr8-smoke-2bec296"
PROTOCOL_PATH: Final = (
    "reports/2026-08-21-a7-v2-shared-build-source-lineage-extension.md"
)
PROTOCOL_SHA256: Final = (
    "ec22c4d898505abc11c00c56ddecbf12e9bbea3009f6369a4100f4539391ddd2"
)
LINEAGE_EVIDENCE_PATH: Final = (
    "tests/fixtures/a7_v2_source_lineage/lineage-evidence.json"
)
LINEAGE_EVIDENCE_SHA256: Final = (
    "f94b75786d7eac28b1508554794b02cf0903492afd14d65f99e5dfdca1a64a84"
)
BASE_TEST_FIXTURE_PATH: Final = (
    "tests/fixtures/a7_v2_source_lineage/"
    "base-test_recover_a7_v2_empty_preflight_shell.py.xz.b64"
)
BASE_TEST_FIXTURE_SHA256: Final = (
    "b19495dccd8aa1ebd823a0019f81d8e4a14302fad46ec4d266e19c623933fa30"
)
BASE_TEST_BYTES: Final = 9_588

RECOVERY_ROOT: Final = (
    "reports/a7-select-ladder-preflight-recovery-runs/"
    "20260821-a7-v2-build-gate-preclaim-recovery-v1"
)
RECOVERY_FILES: Final = {
    f"{RECOVERY_ROOT}/recovery.json": (
        "f25b87b7bce3dd170ad47f647c3f7d3606ad7de5cd646082c0b6ce34463e0e66"
    ),
    f"{RECOVERY_ROOT}/recovery.sha256": (
        "df10db0113f177f33b24c4039e9c9bb677955c2f01caf56e11b263a112a28411"
    ),
    f"{RECOVERY_ROOT}/incident.json": (
        "24bf6fc7d5336dcbc5d1718baddc81985099578003331a1d3a4c5e2a6e00c6e9"
    ),
    f"{RECOVERY_ROOT}/evidence.sha256": (
        "43272bf6af7b1b4f936d30401946b0b56dcecdafb53d9117cf1554b79efb03a9"
    ),
}
RECOVERY_LEDGER_BYTES: Final = (
    b"43272bf6af7b1b4f936d30401946b0b56dcecdafb53d9117cf1554b79efb03a9"
    b"  evidence.sha256\n"
    b"f25b87b7bce3dd170ad47f647c3f7d3606ad7de5cd646082c0b6ce34463e0e66"
    b"  recovery.json\n"
)

A7_SOURCE_PATHS: Final = (
    "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol-v2.md",
    "src/nfl_dfs/__init__.py",
    "src/nfl_dfs/analysis/__init__.py",
    "src/nfl_dfs/analysis/exact_n_portfolio.py",
    "src/nfl_dfs/backtest/__init__.py",
    "src/nfl_dfs/backtest/engine.py",
    "src/nfl_dfs/backtest/field.py",
    "src/nfl_dfs/backtest/payout.py",
    "src/nfl_dfs/inference/__init__.py",
    "src/nfl_dfs/inference/archetype_candidate_allocator.py",
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/optimizer/__init__.py",
    "src/nfl_dfs/research/a7_select_ladder.py",
    "src/nfl_dfs/research/__init__.py",
    "src/nfl_dfs/research/candidate_features.py",
    "src/nfl_dfs/research/paired_max_stats.py",
    "src/nfl_dfs/inference/multiseed_portfolio.py",
    "src/nfl_dfs/research/portfolio_effective_rank.py",
    "src/nfl_dfs/research/source_preflight.py",
    "scripts/run_cbwu_seed_order_audit.py",
    "scripts/run_exact_n_scorefree.py",
    "scripts/run_a7_select_ladder.py",
    "scripts/historical_outcome_lease.py",
    "cloudbuild.yaml",
    "scripts/freeze_a7_select_ladder.py",
    "scripts/cloud_a7_select_ladder.sh",
    "scripts/watch_a7_select_ladder_queue.sh",
    "scripts/finish_a7_select_ladder.py",
    "scripts/close_a7_select_ladder_failed_preflight_v1.py",
    "Dockerfile",
    "pyproject.toml",
)
ALLOWED_EMPTY_SOURCE_PATHS: Final = {
    "src/nfl_dfs/backtest/__init__.py",
    "src/nfl_dfs/inference/__init__.py",
    "src/nfl_dfs/optimizer/__init__.py",
}
RECOVERY_CONTROL_PATHS: Final = (
    "reports/2026-08-21-a7-v2-build-gate-preclaim-recovery-protocol.md",
    "scripts/recover_a7_v2_build_gate_preclaim.py",
    "tests/test_recover_a7_v2_build_gate_preclaim.py",
    "tests/test_finish_a7_select_ladder.py",
    "reports/2026-08-21-a7-v2-empty-preflight-shell-recovery-protocol.md",
    "scripts/recover_a7_v2_empty_preflight_shell.py",
)

ARCHIVE_TEST_PATH: Final = "tests/test_recover_a7_v2_empty_preflight_shell.py"
ARCHIVE_FIXTURE_PATH: Final = (
    "tests/fixtures/a7_v2_empty_preflight_shell/"
    "finish_a7_select_ladder.py.xz.b64"
)
ARCHIVE_REPAIR_PATHS: Final = {ARCHIVE_TEST_PATH, ARCHIVE_FIXTURE_PATH}
BASE_TEST_SHA256: Final = (
    "1c8a5e3a3a9b89217bba30575d789d800d3e5ecbb2181edd9191f2c40196ea22"
)
TARGET_TEST_SHA256: Final = (
    "bd9bee4395977c8ff392b8dd7321951924dc2e44f14a59e9e6d0577e4e1317b2"
)
TARGET_FIXTURE_SHA256: Final = (
    "a75dfbe29b76ae1ce756eae4794ee18d3c7f9772920692e75de58637588cf86c"
)
HISTORICAL_FINISHER_SHA256: Final = (
    "f9963fead2b4cccca035b03e09f0b17519c8e12e02273c2f93cad960982030d8"
)
HISTORICAL_FINISHER_BYTES: Final = 229_783

EXPECTED_DIFF_COUNT: Final = 61
EXPECTED_DIFF_SHA256: Final = (
    "362e3513e2beb37771c0b738a92c847ee4cabdc59093cba3f5b73870fed496da"
)
EXPECTED_CATEGORY_COUNTS: Final = {
    "archive-hermetic-repair": 2,
    "retained-administrative-state": 14,
    "unrelated-lr8-state": 45,
}
EXPECTED_STATUS_COUNTS: Final = {"A": 50, "M": 11}
A7_RECORD_PREFIX: Final = RECOVERY_ROOT + "/"
A7_RECORD_PATHS: Final = {
    "HANDOFF.md",
    "reports/2026-08-20-a7-code-review-and-scoring-concerns.md",
}

GitBlobLoader = Callable[[Path, str, str], bytes | None]
GitDiffLoader = Callable[[Path, str, str], list[dict[str, str]]]
CommitResolver = Callable[[Path, str], None]
AncestryChecker = Callable[[Path, str, str], None]


class SourceLineageError(RuntimeError):
    """Fail-closed source-lineage violation."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _validate_protocol(root: Path) -> bytes:
    path = root / PROTOCOL_PATH
    if path.is_symlink() or not path.is_file():
        raise SourceLineageError("A7 lineage extension protocol is absent")
    raw = path.read_bytes()
    if not raw or _sha(raw) != PROTOCOL_SHA256:
        raise SourceLineageError("A7 lineage extension protocol differs")
    return raw


def _registered_source_paths() -> tuple[str, ...]:
    return tuple(sorted(set((
        *A7_SOURCE_PATHS,
        *RECOVERY_CONTROL_PATHS,
        *RECOVERY_FILES,
        ARCHIVE_TEST_PATH,
        ARCHIVE_FIXTURE_PATH,
    ))))


def _registered_evidence(root: Path) -> dict[str, Any]:
    path = root / LINEAGE_EVIDENCE_PATH
    if path.is_symlink() or not path.is_file():
        raise SourceLineageError("A7 lineage evidence fixture is absent")
    raw = path.read_bytes()
    if _sha(raw) != LINEAGE_EVIDENCE_SHA256:
        raise SourceLineageError("A7 lineage evidence fixture differs")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceLineageError("A7 lineage evidence JSON differs") from exc
    if not isinstance(value, dict) or raw != _canonical_json(value) + b"\n" or \
            set(value) != {
                "version", "base_code_sha", "target_code_sha",
                "base_is_ancestor_of_target", "sources", "complete_delta",
            } or value.get("version") != "a7-v2-source-lineage-evidence-v1" or \
            value.get("base_code_sha") != BASE_CODE_SHA or \
            value.get("target_code_sha") != TARGET_CODE_SHA or \
            value.get("base_is_ancestor_of_target") is not True:
        raise SourceLineageError("A7 lineage evidence authority differs")

    sources = value.get("sources")
    expected_paths = set(_registered_source_paths())
    if not isinstance(sources, dict) or set(sources) != expected_paths:
        raise SourceLineageError("A7 lineage evidence source population differs")
    for relative, row in sources.items():
        if not isinstance(row, dict) or set(row) != {
            "base_sha256", "target_sha256",
        }:
            raise SourceLineageError("A7 lineage evidence source row differs")
        for digest in row.values():
            if digest is not None and (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise SourceLineageError("A7 lineage evidence source hash differs")

    for relative in (*A7_SOURCE_PATHS, *RECOVERY_CONTROL_PATHS):
        row = sources[relative]
        if not row["base_sha256"] or \
                row["base_sha256"] != row["target_sha256"]:
            raise SourceLineageError("A7 lineage evidence equal source differs")
    for relative, target_sha in RECOVERY_FILES.items():
        row = sources[relative]
        if row != {"base_sha256": None, "target_sha256": target_sha}:
            raise SourceLineageError("A7 lineage evidence recovery source differs")
    if sources[ARCHIVE_TEST_PATH] != {
        "base_sha256": BASE_TEST_SHA256,
        "target_sha256": TARGET_TEST_SHA256,
    } or sources[ARCHIVE_FIXTURE_PATH] != {
        "base_sha256": None,
        "target_sha256": TARGET_FIXTURE_SHA256,
    }:
        raise SourceLineageError("A7 lineage evidence archive source differs")

    rows = value.get("complete_delta")
    if not isinstance(rows, list):
        raise SourceLineageError("A7 lineage evidence complete delta differs")
    _validate_diff(rows)
    return value


def _registered_base_test(root: Path) -> bytes:
    path = root / BASE_TEST_FIXTURE_PATH
    if path.is_symlink() or not path.is_file():
        raise SourceLineageError("A7 lineage base-test fixture is absent")
    fixture = path.read_bytes()
    if _sha(fixture) != BASE_TEST_FIXTURE_SHA256:
        raise SourceLineageError("A7 lineage base-test fixture differs")
    try:
        encoded = b"".join(fixture.split())
        raw = lzma.decompress(base64.b64decode(encoded, validate=True))
    except (ValueError, lzma.LZMAError) as exc:
        raise SourceLineageError("A7 lineage base-test encoding differs") from exc
    if len(raw) != BASE_TEST_BYTES or _sha(raw) != BASE_TEST_SHA256:
        raise SourceLineageError("A7 lineage base-test bytes differ")
    return raw


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _resolve_commit(root: Path, commit: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise SourceLineageError("A7 lineage commit identity differs")
    result = _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if result.returncode != 0 or result.stdout.strip() != commit.encode("ascii"):
        raise SourceLineageError("A7 lineage exact commit is unavailable")


def _require_ancestry(root: Path, base: str, target: str) -> None:
    result = _git(
        root, "merge-base", "--is-ancestor", base, target,
    )
    if result.returncode != 0:
        raise SourceLineageError("A7 lineage ancestry differs")


def _git_blob(root: Path, commit: str, relative: str) -> bytes | None:
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise SourceLineageError("A7 lineage source path differs")
    result = _git(root, "show", f"{commit}:{relative}")
    if result.returncode == 0:
        return result.stdout
    return None


def _git_diff(root: Path, base: str, target: str) -> list[dict[str, str]]:
    result = _git(
        root, "diff", "--name-status", "--no-renames", "-z",
        base, target, "--",
    )
    if result.returncode != 0:
        raise SourceLineageError("A7 lineage Git delta is unavailable")
    parts = result.stdout.split(b"\0")
    if not parts or parts[-1] != b"":
        raise SourceLineageError("A7 lineage Git delta framing differs")
    parts.pop()
    if len(parts) % 2:
        raise SourceLineageError("A7 lineage Git delta population differs")
    rows: list[dict[str, str]] = []
    for index in range(0, len(parts), 2):
        try:
            status = parts[index].decode("ascii")
            path = parts[index + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceLineageError("A7 lineage Git delta encoding differs") from exc
        if status not in {"A", "M", "D", "T"} or not path:
            raise SourceLineageError("A7 lineage Git delta row differs")
        rows.append({"path": path, "status": status})
    return sorted(rows, key=lambda row: row["path"])


def _required_blob(
    loader: GitBlobLoader, root: Path, commit: str, relative: str,
) -> bytes:
    raw = loader(root, commit, relative)
    if not isinstance(raw, bytes) or (
        not raw and relative not in ALLOWED_EMPTY_SOURCE_PATHS
    ):
        raise SourceLineageError(f"A7 lineage source is absent: {relative}")
    return raw


def _validate_evidence_sources(
    root: Path, loader: GitBlobLoader, evidence: Mapping[str, Any],
) -> None:
    sources = evidence["sources"]
    if not isinstance(sources, Mapping):
        raise SourceLineageError("A7 lineage evidence sources differ")
    for relative in _registered_source_paths():
        row = sources[relative]
        for commit, field in (
            (BASE_CODE_SHA, "base_sha256"),
            (TARGET_CODE_SHA, "target_sha256"),
        ):
            expected = row[field]
            raw = loader(root, commit, relative)
            if expected is None:
                if raw is not None:
                    raise SourceLineageError(
                        f"A7 lineage evidence unexpected source exists: {relative}"
                    )
            elif not isinstance(raw, bytes) or (
                not raw and relative not in ALLOWED_EMPTY_SOURCE_PATHS
            ) or _sha(raw) != expected:
                raise SourceLineageError(
                    f"A7 lineage evidence source differs: {relative}"
                )


def _local_exact(root: Path, relative: str, expected: bytes) -> None:
    path = root / relative
    if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
        raise SourceLineageError(f"A7 lineage local source differs: {relative}")


def _equal_sources(
    root: Path, loader: GitBlobLoader,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in (*A7_SOURCE_PATHS, *RECOVERY_CONTROL_PATHS):
        base = _required_blob(loader, root, BASE_CODE_SHA, relative)
        target = _required_blob(loader, root, TARGET_CODE_SHA, relative)
        if base != target:
            raise SourceLineageError(f"A7 governed source changed: {relative}")
        _local_exact(root, relative, target)
        result[relative] = _sha(target)
    return result


def _validate_recovery(
    root: Path, retained_root: Path, loader: GitBlobLoader,
) -> dict[str, Any]:
    retained: dict[str, bytes] = {}
    for relative, expected_sha in RECOVERY_FILES.items():
        path = retained_root / relative
        if path.is_symlink() or not path.is_file():
            raise SourceLineageError(f"A7 retained recovery is absent: {relative}")
        raw = path.read_bytes()
        if _sha(raw) != expected_sha:
            raise SourceLineageError(f"A7 retained recovery differs: {relative}")
        committed = _required_blob(loader, root, TARGET_CODE_SHA, relative)
        if committed != raw:
            raise SourceLineageError(f"A7 committed recovery differs: {relative}")
        retained[relative] = raw

    recovery_path = f"{RECOVERY_ROOT}/recovery.json"
    ledger_path = f"{RECOVERY_ROOT}/recovery.sha256"
    incident_path = f"{RECOVERY_ROOT}/incident.json"
    if retained[ledger_path] != RECOVERY_LEDGER_BYTES:
        raise SourceLineageError("A7 retained recovery receipt ledger differs")
    try:
        recovery = json.loads(retained[recovery_path])
        incident = json.loads(retained[incident_path])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceLineageError("A7 retained recovery JSON differs") from exc
    expected_licenses = {
        "historical_scoring_licensed": False,
        "old_build_or_image_reuse_licensed": False,
        "preflight_retry_licensed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "repair_override_licensed": False,
        "same_v2_first_preflight_prepare_claim_licensed": True,
        "same_v2_fresh_exact_source_build_licensed": True,
    }
    if not isinstance(recovery, Mapping) or recovery.get(
        "version"
    ) != "a7-v2-build-gate-preclaim-recovery-v1" or recovery.get(
        "recovery_id"
    ) != "20260821-a7-v2-build-gate-preclaim-recovery-v1" or recovery.get(
        "run_id"
    ) != RUN_ID or recovery.get("fresh_code_sha") != BASE_CODE_SHA or \
            recovery.get("status") != "complete-upon-final-atomic-rename" or \
            recovery.get("licenses") != expected_licenses:
        raise SourceLineageError("A7 retained recovery authority differs")
    fresh = incident.get("fresh_source") if isinstance(incident, Mapping) else None
    if not isinstance(fresh, Mapping) or fresh.get(
        "fresh_code_sha"
    ) != BASE_CODE_SHA or incident.get("run_id") != RUN_ID:
        raise SourceLineageError("A7 retained recovery incident differs")
    return {
        "recovery_json_sha256": RECOVERY_FILES[recovery_path],
        "recovery_ledger_sha256": RECOVERY_FILES[ledger_path],
        "incident_sha256": RECOVERY_FILES[incident_path],
        "fresh_code_sha": BASE_CODE_SHA,
    }


def _archive_repair(
    root: Path, loader: GitBlobLoader,
) -> dict[str, Any]:
    base_test = _required_blob(loader, root, BASE_CODE_SHA, ARCHIVE_TEST_PATH)
    target_test = _required_blob(loader, root, TARGET_CODE_SHA, ARCHIVE_TEST_PATH)
    fixture = _required_blob(loader, root, TARGET_CODE_SHA, ARCHIVE_FIXTURE_PATH)
    if loader(root, BASE_CODE_SHA, ARCHIVE_FIXTURE_PATH) is not None or \
            _sha(base_test) != BASE_TEST_SHA256 or \
            _sha(target_test) != TARGET_TEST_SHA256 or \
            _sha(fixture) != TARGET_FIXTURE_SHA256:
        raise SourceLineageError("A7 archive-hermetic repair bytes differ")
    if base_test != _registered_base_test(root):
        raise SourceLineageError("A7 archive-hermetic base-test fixture differs")
    _local_exact(root, ARCHIVE_TEST_PATH, target_test)
    _local_exact(root, ARCHIVE_FIXTURE_PATH, fixture)
    try:
        encoded = b"".join(fixture.split())
        historical = lzma.decompress(base64.b64decode(encoded, validate=True))
    except (ValueError, lzma.LZMAError) as exc:
        raise SourceLineageError("A7 historical fixture encoding differs") from exc
    if len(historical) != HISTORICAL_FINISHER_BYTES or \
            _sha(historical) != HISTORICAL_FINISHER_SHA256:
        raise SourceLineageError("A7 historical finisher fixture differs")
    return {
        "base_test_sha256": BASE_TEST_SHA256,
        "target_test_sha256": TARGET_TEST_SHA256,
        "target_fixture_sha256": TARGET_FIXTURE_SHA256,
        "historical_finisher_bytes": HISTORICAL_FINISHER_BYTES,
        "historical_finisher_sha256": HISTORICAL_FINISHER_SHA256,
    }


def _classify_path(path: str) -> str:
    if path in ARCHIVE_REPAIR_PATHS:
        return "archive-hermetic-repair"
    if path in A7_RECORD_PATHS or path.startswith(A7_RECORD_PREFIX):
        return "retained-administrative-state"
    if "lr8" in path.lower():
        return "unrelated-lr8-state"
    raise SourceLineageError(f"A7 lineage unclassified change: {path}")


def _validate_diff(rows: list[dict[str, str]]) -> dict[str, Any]:
    unique_paths = {row.get("path") for row in rows}
    if len(rows) != EXPECTED_DIFF_COUNT or len(unique_paths) != len(rows):
        raise SourceLineageError("A7 lineage complete-delta population differs")
    normalized: list[dict[str, str]] = []
    categories: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "status"} or \
                not isinstance(row["path"], str) or \
                row["status"] not in {"A", "M", "D", "T"}:
            raise SourceLineageError("A7 lineage complete-delta row differs")
        normalized.append({"path": row["path"], "status": row["status"]})
        categories[_classify_path(row["path"])] += 1
        statuses[row["status"]] += 1
    normalized.sort(key=lambda row: row["path"])
    digest = _sha(_canonical_json(normalized))
    if dict(categories) != EXPECTED_CATEGORY_COUNTS or \
            dict(statuses) != EXPECTED_STATUS_COUNTS or \
            digest != EXPECTED_DIFF_SHA256:
        raise SourceLineageError("A7 lineage complete-delta receipt differs")
    return {
        "path_count": len(normalized),
        "sha256": digest,
        "category_counts": dict(sorted(categories.items())),
        "status_counts": dict(sorted(statuses.items())),
    }


def _validate(
    *, root: Path = ROOT, retained_root: Path | None = None,
    blob_loader: GitBlobLoader = _git_blob,
    diff_loader: GitDiffLoader = _git_diff,
    commit_resolver: CommitResolver = _resolve_commit,
    ancestry_checker: AncestryChecker = _require_ancestry,
) -> dict[str, Any]:
    """Validate through explicit seams; public authority uses only live Git."""
    root = root.resolve()
    retained = root if retained_root is None else retained_root.resolve()
    protocol = _validate_protocol(root)
    evidence = _registered_evidence(root)
    for commit in (BASE_CODE_SHA, TARGET_CODE_SHA):
        commit_resolver(root, commit)
    ancestry_checker(root, BASE_CODE_SHA, TARGET_CODE_SHA)
    _validate_evidence_sources(root, blob_loader, evidence)
    equal = _equal_sources(root, blob_loader)
    recovery = _validate_recovery(root, retained, blob_loader)
    archive = _archive_repair(root, blob_loader)
    rows = diff_loader(root, BASE_CODE_SHA, TARGET_CODE_SHA)
    delta = _validate_diff(rows)
    if sorted(rows, key=lambda row: row["path"]) != evidence["complete_delta"]:
        raise SourceLineageError("A7 lineage evidence Git delta differs")
    return {
        "version": "a7-v2-shared-build-source-lineage-receipt-v1",
        "extension_id": EXTENSION_ID,
        "run_id": RUN_ID,
        "base_code_sha": BASE_CODE_SHA,
        "target_code_sha": TARGET_CODE_SHA,
        "shared_image_tag": SHARED_IMAGE_TAG,
        "protocol": {"path": PROTOCOL_PATH, "sha256": _sha(protocol)},
        "lineage_evidence": {
            "path": LINEAGE_EVIDENCE_PATH,
            "sha256": LINEAGE_EVIDENCE_SHA256,
            "source_count": len(evidence["sources"]),
        },
        "recovery": recovery,
        "equal_source_count": len(equal),
        "equal_source_sha256": _sha(_canonical_json(equal)),
        "archive_repair": archive,
        "complete_delta": delta,
        "licenses": {
            "a7_first_preflight_prepare_claim_with_exact_shared_build": True,
            "a7_smoke_or_later_authority_changed": False,
            "historical_scoring_licensed": False,
            "lr8_authority_granted": False,
            "old_build_or_image_reuse_licensed": False,
            "preflight_retry_licensed": False,
            "production_change_licensed": False,
            "repair_override_licensed": False,
        },
    }


def validate(
    *, root: Path = ROOT, retained_root: Path | None = None,
) -> dict[str, Any]:
    """Return authority only after validation against the live local Git graph."""
    return _validate(root=root, retained_root=retained_root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser


def main() -> None:
    args = _parser().parse_args()
    print(_canonical_json(validate(root=args.root)).decode("utf-8"))


if __name__ == "__main__":
    main()
