#!/usr/bin/env python3
"""Fail-closed transport, producer wrapper, and harvest for B1 corpus-tail.

The frozen science remains in ``run_b1_corpus_tail_model.py`` and
``nfl_dfs.research.b1_corpus_tail``.  This module owns only transport:
immutable build/job/manifest validation, the one no-retry execution,
terminal-before-body harvesting, independent decision replay, and
generation-matched lease closure.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Final

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_b1_corpus_tail_model as runner  # noqa: E402
from nfl_dfs.research import b1_corpus_tail as science  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
RUN_ID: Final = "20260820-b1-corpus-tail-model-v1"
JOB: Final = "atlas-minimal-c-s2023-w1-v1"
JOB_UID: Final = "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
BUILD_SERVICE_ACCOUNT: Final = (
    "projects/nfl-predictions-503414/serviceAccounts/" + SERVICE_ACCOUNT
)
BUILD_LOGS_BUCKET: Final = "gs://817589974517.cloudbuild-logs.googleusercontent.com"
GIT_SOURCE_URL: Final = "https://github.com/espechtsoftware/nfl-predictions.git"
IMAGE_REPOSITORY: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
)
CPU: Final = "8"
MEMORY: Final = "32Gi"
TIMEOUT_SECONDS: Final = "14400"
PROTOCOL_SHA256: Final = (
    "a91dbb5ee761087096131a51616605b648d9c1f057d11001c09cb7312659f309"
)
SCIENCE_SHA256: Final = (
    "44a81cda46301f12abbc23a31f2848dfe33d8ab964418be0ba32983289d31a04"
)
RUNNER_SHA256: Final = (
    "5e3eefd42adf8d62cc23832f8581c68c5890ec5265d85c69d88b4efb2c0c7223"
)
SMOKE_SHA256: Final = (
    "7b5a7c35f05d10c14f0394f400e41b72fbecfa5278dfb9053892e5bdb1990e00"
)

RESULT_PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/b1-corpus-tail-runs/" + RUN_ID
)
ATTEMPT_URI: Final = runner.HISTORICAL_ATTEMPT_URI
REPORT_URI: Final = RESULT_PREFIX + "/historical-report.json"
MODEL_URI: Final = RESULT_PREFIX + "/model.json"
MANIFEST_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    f"b1-corpus-tail/{RUN_ID}/launch-manifest.json"
)
LAUNCH_INTENT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    f"b1-corpus-tail/{RUN_ID}/launch-intent.json"
)
RELEASE_INTENT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    f"b1-corpus-tail/{RUN_ID}/lease-release-intent.json"
)
LEASE_URI: Final = runner.LEASE_URI
DEFAULT_OUT: Final = ROOT / "reports/b1-corpus-tail-runs" / RUN_ID
A2A_OUT: Final = (
    ROOT / "reports/a2a-production-law-dependence-runs"
    / "20260820-a2a-production-law-dependence-remeasurement-v1"
)
A2A_RUN_ID: Final = "20260820-a2a-production-law-dependence-remeasurement-v1"

SMOKE_FILES: Final = frozenset({
    "outcome-blind-smoke.json",
    "outcome-blind-smoke.json.sha256",
    "outcome-blind-smoke-final.json",
    "outcome-blind-smoke-final.json.sha256",
    "outcome-blind-smoke-locked.json",
    "outcome-blind-smoke-locked.json.sha256",
})
IMPLEMENTATION_PATHS: Final = {
    "protocol": "reports/2026-08-20-b1-corpus-tail-model-protocol.md",
    "science": "src/nfl_dfs/research/b1_corpus_tail.py",
    "runner": "scripts/run_b1_corpus_tail_model.py",
    "science_tests": "tests/test_b1_corpus_tail.py",
    "runner_tests": "tests/test_b1_corpus_tail_runner.py",
    "smoke": (
        "reports/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1/"
        "outcome-blind-smoke-locked.json"
    ),
    "b1_protocol": "reports/2026-08-18-b1-union-c-census-protocol.md",
    "b1_report": (
        "reports/b1-union-c-census-runs/"
        "20260818-b1-union-c-census-v1/report.json"
    ),
    "b1_runner": "scripts/run_b1_union_c_census.py",
    "a2a_finisher": (
        "scripts/finish_a2a_production_law_dependence_remeasurement.py"
    ),
    "lease_tool": "scripts/historical_outcome_lease.py",
    "finisher": "scripts/finish_b1_corpus_tail_model.py",
    "launcher": "scripts/cloud_b1_corpus_tail_model.sh",
    "watcher": "scripts/watch_b1_corpus_tail_queue.sh",
    "transport_tests": "tests/test_b1_corpus_tail_transport.py",
    "dockerfile": "Dockerfile",
    "cloudbuild": "cloudbuild.yaml",
}
RUNTIME_IMPLEMENTATION_KEYS: Final = frozenset({
    "protocol", "science", "runner", "smoke", "b1_protocol", "b1_report",
    "b1_runner", "lease_tool", "finisher", "launcher", "watcher",
    "cloudbuild",
})
TRANSPORT_REPAIR_ENV: Final = {
    "finisher": "B1_CORPUS_TAIL_FINISHER_REPAIR_SHA256",
    "launcher": "B1_CORPUS_TAIL_LAUNCHER_REPAIR_SHA256",
    "watcher": "B1_CORPUS_TAIL_WATCHER_REPAIR_SHA256",
}

PREPARED_FILES: Final = frozenset({
    "build-metadata.json", "job-before.json", "job-after.json",
    "job-executions-before.json", "job-executions-after.json",
    "schedulers-before.json", "schedulers-after.json", "prefix-before.json",
    "prefix-after.json", "lease-before.json", "lease-after.json",
    "manifest.json", "manifest-object.json",
})
LAUNCH_FILES: Final = frozenset({
    "prepared.sha256", "manifest.json", "manifest-object.json",
    "lease-receipt.json", "job-launch.json", "job-executions-launch.json",
    "schedulers-launch.json", "prefix-launch.json", "launch-intent.json",
    "launch-intent-object.json", "job-launch-final.json",
    "job-executions-launch-final.json", "schedulers-launch-final.json",
    "prefix-launch-final.json", "executions.txt",
})


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        value = json.loads(
            raw, object_pairs_hook=_strict_object, parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"B1 {label} is not strict JSON") from exc

    def walk(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise RuntimeError(f"B1 {label} contains non-finite JSON")
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return value


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _load_json(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"B1 {label} is absent")
    return _strict_json_bytes(path.read_bytes(), label=label)


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _hex(value: object, *, length: int, label: str) -> str:
    text = str(value)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", text) is None:
        raise RuntimeError(f"B1 {label} differs")
    return text


def _positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise RuntimeError(f"B1 {label} differs")
    return value


def _nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise RuntimeError(f"B1 {label} differs")
    return value


def _finite(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"B1 {label} differs")
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"B1 {label} differs")
    return number


def _utc_timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"B1 {label} differs")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"B1 {label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RuntimeError(f"B1 {label} differs")
    return value


def _write_exclusive_or_equal(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise RuntimeError(f"B1 immutable local file differs: {path}")


def _gcs_parts(uri: str) -> tuple[str, str]:
    if re.fullmatch(r"gs://[^/]+/.+", uri) is None:
        raise RuntimeError("B1 GCS URI differs")
    bucket, name = uri[5:].split("/", 1)
    if not bucket or not name or ".." in name.split("/"):
        raise RuntimeError("B1 GCS URI differs")
    return bucket, name


def _blob_metadata(blob: Any, *, uri: str, raw: bytes) -> dict[str, Any]:
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "metageneration": str(blob.metageneration),
        "bytes": len(raw),
        "sha256": _sha_bytes(raw),
    }


def _metadata(
    value: Mapping[str, Any], *, uri: str, label: str,
    create_only: bool | None = None,
) -> dict[str, Any]:
    keys = {"uri", "generation", "metageneration", "bytes", "sha256"}
    if create_only is not None:
        keys.add("create_only")
    if set(value) != keys or value.get("uri") != uri:
        raise RuntimeError(f"B1 {label} object fields differ")
    generation = str(value.get("generation", ""))
    metageneration = str(value.get("metageneration", ""))
    if re.fullmatch(r"[1-9][0-9]*", generation) is None or metageneration != "1":
        raise RuntimeError(f"B1 {label} object identity differs")
    result = {
        "uri": uri,
        "generation": generation,
        "metageneration": metageneration,
        "bytes": _positive_int(value.get("bytes"), label=f"{label} bytes"),
        "sha256": _hex(value.get("sha256"), length=64, label=f"{label} SHA"),
    }
    if create_only is not None:
        if value.get("create_only") is not create_only:
            raise RuntimeError(f"B1 {label} create-only proof differs")
        result["create_only"] = create_only
    return result


def _download_generation(
    client: storage.Client, identity: Mapping[str, Any], *, label: str,
) -> tuple[dict[str, Any], bytes]:
    expected = _metadata(
        identity, uri=str(identity.get("uri", "")), label=label,
    )
    bucket, name = _gcs_parts(expected["uri"])
    blob = client.bucket(bucket).blob(name, generation=int(expected["generation"]))
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=int(expected["generation"]))
    observed = _blob_metadata(blob, uri=expected["uri"], raw=raw)
    if observed != expected:
        raise RuntimeError(f"B1 {label} changed")
    return observed, raw


def _upload_create_once(
    client: storage.Client, uri: str, raw: bytes,
) -> dict[str, Any]:
    bucket, name = _gcs_parts(uri)
    blob = client.bucket(bucket).blob(name)
    blob.upload_from_string(
        raw, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    reopened = blob.download_as_bytes(if_generation_match=int(blob.generation))
    if reopened != raw:
        raise RuntimeError(f"B1 create-only object reopen differs: {uri}")
    return _metadata(
        {**_blob_metadata(blob, uri=uri, raw=raw), "create_only": True},
        uri=uri, label="published", create_only=True,
    )


def _upload_create_once_or_same(
    client: storage.Client, uri: str, raw: bytes,
) -> dict[str, Any]:
    try:
        return _upload_create_once(client, uri, raw)
    except PreconditionFailed:
        bucket, name = _gcs_parts(uri)
        blob = client.bucket(bucket).blob(name)
        blob.reload()
        existing = blob.download_as_bytes(if_generation_match=int(blob.generation))
        if existing != raw:
            raise RuntimeError(f"B1 immutable governance object differs: {uri}")
        return _metadata(
            {**_blob_metadata(blob, uri=uri, raw=raw), "create_only": True},
            uri=uri, label="published", create_only=True,
        )


def _prefix_inventory(client: storage.Client) -> list[dict[str, Any]]:
    bucket, prefix = _gcs_parts(RESULT_PREFIX + "/")
    rows = []
    for blob in client.list_blobs(bucket, prefix=prefix):
        rows.append({
            "uri": f"gs://{bucket}/{blob.name}",
            "generation": str(blob.generation),
            "metageneration": str(blob.metageneration),
            "bytes": int(blob.size or 0),
        })
    return sorted(rows, key=lambda row: row["uri"])


def _require_empty_prefix(client: storage.Client) -> None:
    if _prefix_inventory(client):
        raise RuntimeError("B1 result prefix/attempt path is not exactly empty")


def _require_lease_absent(client: storage.Client) -> None:
    bucket, name = _gcs_parts(LEASE_URI)
    blob = client.bucket(bucket).blob(name)
    try:
        blob.reload()
    except NotFound:
        return
    raise RuntimeError("B1 historical-outcome lease is already held")


def _absence_receipt(*, kind: str, checked_at: str) -> dict[str, Any]:
    target = RESULT_PREFIX if kind == "result-prefix-and-attempt" else LEASE_URI
    if kind not in {"result-prefix-and-attempt", "historical-outcome-lease"}:
        raise RuntimeError("B1 absence receipt kind differs")
    return {
        "version": "b1-corpus-tail-absence-receipt-v1",
        "kind": kind,
        "target": target,
        "state": "absent",
        "checked_at": _utc_timestamp(checked_at, label="absence time"),
    }


def _validate_absence(value: object, *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "kind", "target", "state", "checked_at",
    }:
        raise RuntimeError("B1 absence receipt fields differ")
    expected = _absence_receipt(kind=kind, checked_at=str(value["checked_at"]))
    if value != expected:
        raise RuntimeError("B1 absence receipt differs")
    return value


def _capture_absence(
    *, kind: str, output: Path, client: storage.Client | None = None,
) -> dict[str, Any]:
    gcs = storage.Client(project=PROJECT) if client is None else client
    if kind == "result-prefix-and-attempt":
        _require_empty_prefix(gcs)
    else:
        _require_lease_absent(gcs)
    value = _absence_receipt(
        kind=kind, checked_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_exclusive_or_equal(output, _canonical_json(value))
    return value


def _canonicalize_external_json(raw_path: Path, output: Path) -> Any:
    value = _strict_json_bytes(raw_path.read_bytes(), label="external JSON")
    _write_exclusive_or_equal(output, _canonical_json(value))
    return value


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True, capture_output=True,
    ).stdout


def _validate_smoke_staging(
    out: Path, *, code_sha: str, root: Path = ROOT,
    git_loader: Callable[[Path, str, str], bytes] = _git_blob,
) -> None:
    if out.is_symlink() or not out.is_dir() or {
        path.name for path in out.iterdir()
    } != set(SMOKE_FILES):
        raise RuntimeError("B1 smoke staging inventory differs")
    for name in SMOKE_FILES:
        path = out / name
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        if path.is_symlink() or not path.is_file() or path.read_bytes() != \
                git_loader(root, code_sha, relative):
            raise RuntimeError("B1 smoke staging differs from source commit")
    locked = out / "outcome-blind-smoke-locked.json"
    smoke = _strict_json_bytes(locked.read_bytes(), label="locked smoke")
    if _sha(locked) != SMOKE_SHA256 or not isinstance(smoke, dict) or \
            smoke.get("status") != "OUTCOME_BLIND_REALITY_SMOKE_OK" or \
            smoke.get("uses_realized_outcomes") is not False or \
            smoke.get("winner_fields_read") != [] or \
            smoke.get("source", {}).get("realized_outcome_columns_read") != [] or \
            smoke.get("canonical_selected") != 80:
        raise RuntimeError("B1 locked smoke boundary differs")


def _a2a_terminal(
    *, root: Path = ROOT, code_sha: str | None = None,
    git_loader: Callable[[Path, str, str], bytes] = _git_blob,
) -> dict[str, Any]:
    out = root / A2A_OUT.relative_to(ROOT)
    success = (out / "lease-release.json", out / "lease-release.sha256")
    failure = (out / "failure-closure.json", out / "failure-closure.sha256")
    present = [pair for pair in (success, failure) if all(path.is_file() for path in pair)]
    if len(present) != 1:
        raise RuntimeError("B1 waits for exactly one terminal A2a lease closure")
    body_path, ledger_path = present[0]
    body_raw = body_path.read_bytes()
    body = _strict_json_bytes(body_raw, label="A2a terminal closure")
    if not isinstance(body, dict) or body.get("run_id") != A2A_RUN_ID or \
            body.get("active_lease_exact_generation_closed") is not True or \
            body.get("historical_retry_licensed") is not False or \
            body.get("production_change_licensed") is not False:
        raise RuntimeError("B1 A2a terminal closure differs")
    if body_path.name == "lease-release.json":
        if body.get("release_complete") is not True:
            raise RuntimeError("B1 A2a success lease closure is incomplete")
        disposition = str(body.get("intent", {}).get("disposition", ""))
        terminal_kind = "success"
    else:
        if body.get("disposition") != "closed-terminal-failed-no-retry":
            raise RuntimeError("B1 A2a failure closure differs")
        disposition = str(body["disposition"])
        terminal_kind = "failure"
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    matching = [
        line for line in lines
        if re.fullmatch(rf"{_sha_bytes(body_raw)}  {re.escape(body_path.name)}", line)
    ]
    if len(matching) != 1:
        raise RuntimeError("B1 A2a terminal checksum differs")
    if code_sha is not None:
        for path in (body_path, ledger_path):
            relative = path.resolve().relative_to(root.resolve()).as_posix()
            if path.read_bytes() != git_loader(root, code_sha, relative):
                raise RuntimeError("B1 A2a terminal closure is not in source commit")
    return {
        "run_id": A2A_RUN_ID,
        "terminal_kind": terminal_kind,
        "disposition": disposition,
        "body_path": body_path.resolve().relative_to(root.resolve()).as_posix(),
        "body_sha256": _sha_bytes(body_raw),
        "ledger_path": ledger_path.resolve().relative_to(root.resolve()).as_posix(),
        "ledger_sha256": _sha(ledger_path),
        "lease_generation_closed": str(body.get("active_lease_generation", "")),
    }


def _implementation_receipts(
    *, root: Path, code_sha: str,
    git_loader: Callable[[Path, str, str], bytes] = _git_blob,
) -> dict[str, dict[str, str]]:
    _hex(code_sha, length=40, label="source commit")
    result: dict[str, dict[str, str]] = {}
    for key, relative in IMPLEMENTATION_PATHS.items():
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"B1 implementation is absent: {relative}")
        current = path.read_bytes()
        if current != git_loader(root, code_sha, relative):
            raise RuntimeError(f"B1 implementation differs from commit: {relative}")
        result[key] = {"path": relative, "sha256": _sha_bytes(current)}
    hard = {
        "protocol": PROTOCOL_SHA256,
        "science": SCIENCE_SHA256,
        "runner": RUNNER_SHA256,
        "smoke": SMOKE_SHA256,
        "b1_protocol": runner.B1_PROTOCOL_SHA256,
        "b1_report": runner.B1_REPORT_SHA256,
        "b1_runner": runner.B1_RUNNER_SHA256,
    }
    if any(result[key]["sha256"] != digest for key, digest in hard.items()):
        raise RuntimeError("B1 frozen scientific implementation differs")
    return result


def _validate_current_implementation(
    manifest: Mapping[str, Any], *, root: Path = ROOT,
    env: Mapping[str, str] | None = None, runtime_only: bool = False,
) -> dict[str, str]:
    frozen = manifest.get("implementation")
    if not isinstance(frozen, dict) or set(frozen) != set(IMPLEMENTATION_PATHS):
        raise RuntimeError("B1 implementation manifest differs")
    values = os.environ if env is None else env
    repairs: dict[str, str] = {}
    for key, relative in IMPLEMENTATION_PATHS.items():
        if runtime_only and key not in RUNTIME_IMPLEMENTATION_KEYS:
            continue
        row = frozen.get(key)
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or \
                row.get("path") != relative:
            raise RuntimeError(f"B1 implementation row differs: {key}")
        path = root / relative
        current = _sha(path)
        expected = _hex(row.get("sha256"), length=64, label=f"{key} SHA")
        if current == expected:
            continue
        repair = TRANSPORT_REPAIR_ENV.get(key)
        if repair is None or values.get(repair) != current:
            raise RuntimeError(f"B1 frozen implementation changed: {relative}")
        repairs[key] = current
    return repairs


def _image_tag(code_sha: str) -> str:
    return f"{IMAGE_REPOSITORY}:b1-tail-{code_sha[:7]}"


def _expected_cloud_build_steps(image_tag: str) -> list[dict[str, Any]]:
    """Extend the exact committed A2a build with only B1 container smokes."""
    import finish_a2a_production_law_dependence_remeasurement as a2a_finish

    steps = a2a_finish._expected_cloud_build_steps(image_tag)
    smoke = steps[2]["args"][1]
    marker = (
        f"docker run --rm '{image_tag}' \\\n"
        "  python scripts/run_atlas_minimal_world_selection_c.py --help >/dev/null\n"
    )
    addition = "".join((
        f"docker run --rm '{image_tag}' \\\n"
        "  python scripts/run_b1_corpus_tail_model.py --help >/dev/null\n",
        f"docker run --rm '{image_tag}' \\\n"
        "  python scripts/finish_b1_corpus_tail_model.py --help >/dev/null\n",
        f"docker run --rm '{image_tag}' \\\n"
        "  bash -n scripts/cloud_b1_corpus_tail_model.sh\n",
        f"docker run --rm '{image_tag}' \\\n"
        "  bash -n scripts/watch_b1_corpus_tail_queue.sh\n",
    ))
    if smoke.count(marker) != 1:
        raise RuntimeError("B1 Cloud Build insertion marker differs")
    steps[2]["args"][1] = smoke.replace(marker, addition + marker)
    return steps


def _validate_build_metadata(
    value: Mapping[str, Any], *, build_id: str, image: str, code_sha: str,
) -> str:
    _hex(code_sha, length=40, label="build source commit")
    if re.fullmatch(r"[0-9A-Za-z-]{8,80}", build_id) is None or re.fullmatch(
        rf"{re.escape(IMAGE_REPOSITORY)}@sha256:[0-9a-f]{{64}}", image,
    ) is None:
        raise RuntimeError("B1 immutable build identity differs")
    source = {"url": GIT_SOURCE_URL, "revision": code_sha}
    provenance = value.get("sourceProvenance")
    if value.get("id") != build_id or value.get("source") != {"gitSource": source} or \
            not isinstance(provenance, Mapping) or \
            provenance.get("resolvedGitSource") != source:
        raise RuntimeError("B1 Cloud Build direct-Git source differs")
    tag = _image_tag(code_sha)
    substitutions = value.get("substitutions")
    if not isinstance(substitutions, Mapping) or substitutions.get("_IMAGE") != tag:
        raise RuntimeError("B1 Cloud Build image substitution differs")
    declared = {
        substitutions[key] for key in ("COMMIT_SHA", "_CODE_SHA")
        if key in substitutions
    }
    if declared and declared != {code_sha}:
        raise RuntimeError("B1 Cloud Build declared commit differs")
    steps = value.get("steps")
    if not isinstance(steps, list) or len(steps) != 3:
        raise RuntimeError("B1 Cloud Build validation steps differ")
    normalized_steps = []
    for row in steps:
        if not isinstance(row, Mapping):
            raise RuntimeError("B1 Cloud Build validation step differs")
        normalized_steps.append({
            "name": row.get("name"), "id": row.get("id"),
            "entrypoint": row.get("entrypoint", ""),
            "args": row.get("args", []), "env": row.get("env", []),
            "dir": row.get("dir", ""), "secretEnv": row.get("secretEnv", []),
            "status": row.get("status"),
            "allowFailure": row.get("allowFailure", False),
            "allowExitCodes": row.get("allowExitCodes", []),
            "waitFor": row.get("waitFor", []), "timeout": row.get("timeout", ""),
            "script": row.get("script", ""), "volumes": row.get("volumes", []),
            "automapSubstitutions": row.get("automapSubstitutions", False),
            "exitCode": row.get("exitCode", 0),
        })
    digest = image.rsplit("@", 1)[1]
    images = value.get("results", {}).get("images", [])
    if value.get("status") != "SUCCESS" or value.get("images") != [tag] or \
            value.get("artifacts") != {"images": [tag]} or \
            value.get("serviceAccount") != BUILD_SERVICE_ACCOUNT or \
            value.get("logsBucket") != BUILD_LOGS_BUCKET or \
            value.get("timeout") != "10800s" or \
            normalized_steps != _expected_cloud_build_steps(tag) or not any(
                isinstance(row, Mapping) and row.get("name") == tag
                and row.get("digest") == digest for row in images
            ):
        raise RuntimeError("B1 Cloud Build/test/image gate differs")
    return tag


def _static_job_contract(*, code_sha: str, image: str) -> dict[str, Any]:
    return {
        "image": image,
        "command": ["python"],
        "args": ["scripts/finish_b1_corpus_tail_model.py", "--help"],
        "env": {
            "B1_CORPUS_TAIL_HISTORICAL_ENABLED": "1",
            "ANALYSIS_IMAGE": image,
            "CODE_SHA": code_sha,
        },
        "working_dir": "", "volume_mounts": [], "volumes": [],
        "startup_probe": None, "tasks": 1, "parallelism": 1,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "max_retries": 0, "timeout_seconds": int(TIMEOUT_SECONDS),
        "service_account": SERVICE_ACCOUNT,
    }


def _execution_contract(
    *, manifest: Mapping[str, Any], intent_generation: str,
) -> dict[str, Any]:
    expected = _static_job_contract(
        code_sha=manifest["code"]["commit_sha"],
        image=manifest["image"]["uri"],
    )
    expected["args"] = [
        "scripts/finish_b1_corpus_tail_model.py", "execute-frozen",
        "--launch-intent-generation", intent_generation,
    ]
    return expected


def _job_spec_sha256(value: Mapping[str, Any]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, dict) or not spec:
        raise RuntimeError("B1 reused-job spec is absent")
    return _sha_bytes(_canonical_json(spec))


def _job_identity(value: Mapping[str, Any]) -> tuple[str, str, str]:
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("name") != JOB or \
            metadata.get("uid") != JOB_UID:
        raise RuntimeError("B1 reused-job identity differs")
    generation = _positive_int(
        metadata.get("generation"), label="reused-job generation",
    )
    return str(metadata["uid"]), str(generation), _job_spec_sha256(value)


def _container_contract(
    *, outer: Mapping[str, Any], task: Mapping[str, Any],
    expected: Mapping[str, Any], label: str,
) -> None:
    containers = task.get("containers", [])
    if _positive_int(outer.get("taskCount"), label=f"{label} task count") != 1 or \
            _positive_int(outer.get("parallelism"), label=f"{label} parallelism") != 1 or \
            not isinstance(containers, list) or len(containers) != 1:
        raise RuntimeError(f"B1 {label} task shape differs")
    container = containers[0]
    env_rows = container.get("env", []) if isinstance(container, Mapping) else []
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise RuntimeError(f"B1 {label} environment differs")
    env = {row["name"]: row["value"] for row in env_rows}
    if len(env) != len(env_rows) or env != expected["env"] or \
            container.get("image") != expected["image"] or \
            container.get("command") != expected["command"] or \
            container.get("args") != expected["args"] or \
            container.get("workingDir", "") != "" or \
            container.get("volumeMounts", []) != [] or \
            container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != expected["resources"] or \
            task.get("volumes", []) != [] or _nonnegative_int(
                task.get("maxRetries"), label=f"{label} max retries",
            ) != 0 or task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError(f"B1 {label} executable contract differs")


def _validate_job_spec(
    value: Mapping[str, Any], *, code_sha: str, image: str,
) -> tuple[str, str, str]:
    identity = _job_identity(value)
    spec = value.get("spec", {})
    outer = spec.get("template", {}).get("spec", {})
    task = outer.get("template", {}).get("spec", {}) \
        if isinstance(outer, Mapping) else {}
    _container_contract(
        outer=outer, task=task,
        expected=_static_job_contract(code_sha=code_sha, image=image),
        label="reused-job",
    )
    return identity


def _validate_job_idle(value: object) -> None:
    if not isinstance(value, list):
        raise RuntimeError("B1 reused-job execution census differs")
    for row in value:
        if not isinstance(row, Mapping):
            raise RuntimeError("B1 reused-job execution row differs")
        completed = [
            item for item in row.get("status", {}).get("conditions", [])
            if isinstance(item, Mapping) and item.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") not in {"True", "False"}:
            raise RuntimeError("B1 reused job is not idle")


def _validate_unscheduled(value: object) -> None:
    if not isinstance(value, list):
        raise RuntimeError("B1 scheduler census differs")
    marker = f"/jobs/{JOB}"
    for row in value:
        if not isinstance(row, Mapping):
            raise RuntimeError("B1 scheduler row differs")
        target = row.get("httpTarget", {})
        uri = target.get("uri", "") if isinstance(target, Mapping) else ""
        if not isinstance(uri, str) or marker in uri:
            raise RuntimeError("B1 reused job scheduler state differs")


def _validate_prepare_inputs(
    *, code_sha: str, image: str, build_id: str,
    build_metadata: Mapping[str, Any], job_before: Mapping[str, Any],
    executions_before: object, schedulers_before: object,
    root: Path = ROOT,
) -> None:
    _validate_build_metadata(
        build_metadata, build_id=build_id, image=image, code_sha=code_sha,
    )
    _implementation_receipts(root=root, code_sha=code_sha)
    _a2a_terminal(root=root, code_sha=code_sha)
    _job_identity(job_before)
    _validate_job_idle(executions_before)
    _validate_unscheduled(schedulers_before)


def _build_manifest(
    *, code_sha: str, image: str, build_id: str,
    build_metadata: Mapping[str, Any], job_before: Mapping[str, Any],
    job_after: Mapping[str, Any], executions_before: object,
    executions_after: object, schedulers_before: object,
    schedulers_after: object, prefix_before: Mapping[str, Any],
    prefix_after: Mapping[str, Any], lease_before: Mapping[str, Any],
    lease_after: Mapping[str, Any], frozen_at: str, root: Path = ROOT,
) -> dict[str, Any]:
    tag = _validate_build_metadata(
        build_metadata, build_id=build_id, image=image, code_sha=code_sha,
    )
    implementation = _implementation_receipts(root=root, code_sha=code_sha)
    predecessor = _a2a_terminal(root=root, code_sha=code_sha)
    _validate_job_idle(executions_before)
    _validate_job_idle(executions_after)
    _validate_unscheduled(schedulers_before)
    _validate_unscheduled(schedulers_after)
    _validate_absence(prefix_before, kind="result-prefix-and-attempt")
    _validate_absence(prefix_after, kind="result-prefix-and-attempt")
    _validate_absence(lease_before, kind="historical-outcome-lease")
    _validate_absence(lease_after, kind="historical-outcome-lease")
    prior_uid, prior_generation, prior_spec = _job_identity(job_before)
    uid, generation, spec_sha = _validate_job_spec(
        job_after, code_sha=code_sha, image=image,
    )
    if uid != prior_uid or int(generation) <= int(prior_generation):
        raise RuntimeError("B1 reused-job generation chain differs")
    manifest = {
        "version": "b1-corpus-tail-launch-manifest-v1",
        "status": "frozen-before-one-historical-execution",
        "run_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "code": {"commit_sha": code_sha},
        "image": {"uri": image},
        "build": {
            "id": build_id, "tag": tag,
            "metadata_sha256": _sha_bytes(_canonical_json(build_metadata)),
        },
        "job": {
            "name": JOB, "uid": uid,
            "prior_generation": prior_generation,
            "prior_spec_sha256": prior_spec,
            "generation": generation, "spec_sha256": spec_sha,
            "service_account": SERVICE_ACCOUNT,
            "update_mode": "reuse-only-update-existing",
            "scheduler_target_absent": True,
        },
        "static_job_contract": _static_job_contract(
            code_sha=code_sha, image=image,
        ),
        "implementation": implementation,
        "queue_predecessor": predecessor,
        "output": {
            "prefix": RESULT_PREFIX, "attempt_uri": ATTEMPT_URI,
            "report_uri": REPORT_URI, "model_uri": MODEL_URI,
            "prelaunch_inventory": [], "create_only": True,
        },
        "lease": {
            "active_uri": LEASE_URI,
            "launch_intent_uri": LAUNCH_INTENT_URI,
            "release_intent_uri": RELEASE_INTENT_URI,
        },
        "preflight": {
            "frozen_at": _utc_timestamp(frozen_at, label="manifest time"),
            "job_idle_before_update": True,
            "job_idle_after_update": True,
            "schedulers_before_sha256": _sha_bytes(_canonical_json(schedulers_before)),
            "schedulers_after_sha256": _sha_bytes(_canonical_json(schedulers_after)),
            "prefix_before_sha256": _sha_bytes(_canonical_json(prefix_before)),
            "prefix_after_sha256": _sha_bytes(_canonical_json(prefix_after)),
            "lease_before_sha256": _sha_bytes(_canonical_json(lease_before)),
            "lease_after_sha256": _sha_bytes(_canonical_json(lease_after)),
        },
        "historical_looks": 1,
        "uses_realized_outcomes": True,
        "actual_outcomes_queried_before_execution": False,
        "winner_target_or_feature_used": False,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    _validate_manifest(manifest, root=root, env={}, validate_files=True)
    return manifest


MANIFEST_KEYS: Final = frozenset({
    "version", "status", "run_id", "protocol_sha256", "code", "image",
    "build", "job", "static_job_contract", "implementation",
    "queue_predecessor", "output", "lease", "preflight",
    "historical_looks", "uses_realized_outcomes",
    "actual_outcomes_queried_before_execution", "winner_target_or_feature_used",
    "historical_retry_licensed", "production_change_licensed",
})


def _validate_manifest(
    value: object, *, root: Path = ROOT, env: Mapping[str, str] | None = None,
    validate_files: bool = True, runtime_only: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != MANIFEST_KEYS:
        raise RuntimeError("B1 launch manifest fields differ")
    fixed = {
        "version": "b1-corpus-tail-launch-manifest-v1",
        "status": "frozen-before-one-historical-execution",
        "run_id": RUN_ID, "protocol_sha256": PROTOCOL_SHA256,
        "historical_looks": 1, "uses_realized_outcomes": True,
        "actual_outcomes_queried_before_execution": False,
        "winner_target_or_feature_used": False,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise RuntimeError("B1 launch manifest frozen identity differs")
    code = value.get("code")
    image = value.get("image")
    if not isinstance(code, dict) or set(code) != {"commit_sha"} or \
            re.fullmatch(r"[0-9a-f]{40}", str(code.get("commit_sha", ""))) is None or \
            not isinstance(image, dict) or set(image) != {"uri"} or re.fullmatch(
                rf"{re.escape(IMAGE_REPOSITORY)}@sha256:[0-9a-f]{{64}}",
                str(image.get("uri", "")),
            ) is None:
        raise RuntimeError("B1 launch manifest code/image differs")
    code_sha = str(code["commit_sha"])
    image_uri = str(image["uri"])
    build = value.get("build")
    if not isinstance(build, dict) or set(build) != {
        "id", "tag", "metadata_sha256",
    } or build.get("tag") != _image_tag(code_sha) or re.fullmatch(
        r"[0-9A-Za-z-]{8,80}", str(build.get("id", "")),
    ) is None:
        raise RuntimeError("B1 launch manifest build differs")
    _hex(build.get("metadata_sha256"), length=64, label="build metadata SHA")
    job = value.get("job")
    if not isinstance(job, dict) or set(job) != {
        "name", "uid", "prior_generation", "prior_spec_sha256", "generation",
        "spec_sha256", "service_account", "update_mode",
        "scheduler_target_absent",
    } or job.get("name") != JOB or job.get("uid") != JOB_UID or \
            re.fullmatch(r"[1-9][0-9]*", str(job.get("prior_generation", ""))) is None or \
            re.fullmatch(r"[1-9][0-9]*", str(job.get("generation", ""))) is None or \
            int(job["generation"]) <= int(job["prior_generation"]) or \
            job.get("service_account") != SERVICE_ACCOUNT or \
            job.get("update_mode") != "reuse-only-update-existing" or \
            job.get("scheduler_target_absent") is not True:
        raise RuntimeError("B1 launch manifest reused-job differs")
    for key in ("prior_spec_sha256", "spec_sha256"):
        _hex(job.get(key), length=64, label=key)
    if value.get("static_job_contract") != _static_job_contract(
        code_sha=code_sha, image=image_uri,
    ):
        raise RuntimeError("B1 launch manifest job contract differs")
    output = value.get("output")
    if output != {
        "prefix": RESULT_PREFIX, "attempt_uri": ATTEMPT_URI,
        "report_uri": REPORT_URI, "model_uri": MODEL_URI,
        "prelaunch_inventory": [], "create_only": True,
    } or value.get("lease") != {
        "active_uri": LEASE_URI, "launch_intent_uri": LAUNCH_INTENT_URI,
        "release_intent_uri": RELEASE_INTENT_URI,
    }:
        raise RuntimeError("B1 launch manifest output/lease differs")
    predecessor = value.get("queue_predecessor")
    if not isinstance(predecessor, dict) or set(predecessor) != {
        "run_id", "terminal_kind", "disposition", "body_path", "body_sha256",
        "ledger_path", "ledger_sha256", "lease_generation_closed",
    } or predecessor.get("run_id") != A2A_RUN_ID or \
            predecessor.get("terminal_kind") not in {"success", "failure"}:
        raise RuntimeError("B1 queue predecessor differs")
    expected_a2a_names = (
        ("lease-release.json", "lease-release.sha256")
        if predecessor["terminal_kind"] == "success"
        else ("failure-closure.json", "failure-closure.sha256")
    )
    expected_a2a_prefix = (
        "reports/a2a-production-law-dependence-runs/"
        "20260820-a2a-production-law-dependence-remeasurement-v1/"
    )
    if predecessor.get("body_path") != expected_a2a_prefix + expected_a2a_names[0] or \
            predecessor.get("ledger_path") != expected_a2a_prefix + expected_a2a_names[1] or \
            re.fullmatch(r"[1-9][0-9]*", str(
                predecessor.get("lease_generation_closed", "")
            )) is None:
        raise RuntimeError("B1 queue predecessor paths/generation differ")
    for key in ("body_sha256", "ledger_sha256"):
        _hex(predecessor.get(key), length=64, label=f"predecessor {key}")
    implementation = value.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != set(
        IMPLEMENTATION_PATHS
    ):
        raise RuntimeError("B1 launch manifest implementation differs")
    for key, relative in IMPLEMENTATION_PATHS.items():
        row = implementation.get(key)
        if not isinstance(row, dict) or row.get("path") != relative or \
                set(row) != {"path", "sha256"}:
            raise RuntimeError(f"B1 launch manifest implementation row differs: {key}")
        _hex(row.get("sha256"), length=64, label=f"{key} SHA")
    hard = {
        "protocol": PROTOCOL_SHA256, "science": SCIENCE_SHA256,
        "runner": RUNNER_SHA256, "smoke": SMOKE_SHA256,
        "b1_protocol": runner.B1_PROTOCOL_SHA256,
        "b1_report": runner.B1_REPORT_SHA256,
        "b1_runner": runner.B1_RUNNER_SHA256,
    }
    if any(implementation[key]["sha256"] != digest for key, digest in hard.items()):
        raise RuntimeError("B1 launch manifest scientific pins differ")
    preflight = value.get("preflight")
    if not isinstance(preflight, dict) or set(preflight) != {
        "frozen_at", "job_idle_before_update", "job_idle_after_update",
        "schedulers_before_sha256", "schedulers_after_sha256",
        "prefix_before_sha256", "prefix_after_sha256",
        "lease_before_sha256", "lease_after_sha256",
    } or preflight.get("job_idle_before_update") is not True or \
            preflight.get("job_idle_after_update") is not True:
        raise RuntimeError("B1 launch manifest preflight differs")
    _utc_timestamp(preflight.get("frozen_at"), label="manifest time")
    for key in set(preflight) - {
        "frozen_at", "job_idle_before_update", "job_idle_after_update",
    }:
        _hex(preflight.get(key), length=64, label=key)
    if validate_files:
        _validate_current_implementation(
            value, root=root, env=env, runtime_only=runtime_only,
        )
        for path_key, sha_key in (
            ("body_path", "body_sha256"), ("ledger_path", "ledger_sha256"),
        ):
            path = root / str(predecessor[path_key])
            if _sha(path) != predecessor[sha_key]:
                raise RuntimeError("B1 queue predecessor bytes differ")
    return value


def _manifest_receipt(
    value: object, *, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "manifest_sha256", "object",
    } or value.get("version") != "b1-corpus-tail-manifest-receipt-v1":
        raise RuntimeError("B1 manifest receipt fields differ")
    raw = _canonical_json(manifest)
    if value.get("manifest_sha256") != _sha_bytes(raw):
        raise RuntimeError("B1 manifest receipt body SHA differs")
    obj = value.get("object")
    if not isinstance(obj, Mapping):
        raise RuntimeError("B1 manifest object receipt differs")
    metadata = _metadata(
        obj, uri=MANIFEST_URI, label="launch manifest", create_only=True,
    )
    if metadata["sha256"] != _sha_bytes(raw) or metadata["bytes"] != len(raw):
        raise RuntimeError("B1 manifest object body differs")
    return {
        "version": value["version"], "manifest_sha256": value["manifest_sha256"],
        "object": metadata,
    }


def _publish_manifest(
    manifest_path: Path, receipt_path: Path,
    *, client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest = _validate_manifest(_load_json(manifest_path, label="launch manifest"))
    raw = _canonical_json(manifest)
    gcs = storage.Client(project=PROJECT) if client is None else client
    obj = _upload_create_once_or_same(gcs, MANIFEST_URI, raw)
    receipt = {
        "version": "b1-corpus-tail-manifest-receipt-v1",
        "manifest_sha256": _sha_bytes(raw), "object": obj,
    }
    _manifest_receipt(receipt, manifest=manifest)
    _write_exclusive_or_equal(receipt_path, _canonical_json(receipt))
    return receipt


def _load_live_manifest(
    manifest: Mapping[str, Any], receipt: Mapping[str, Any],
    *, client: storage.Client,
) -> dict[str, Any]:
    validated = _manifest_receipt(receipt, manifest=manifest)
    identity = {
        key: item for key, item in validated["object"].items()
        if key != "create_only"
    }
    _, raw = _download_generation(client, identity, label="launch manifest")
    if raw != _canonical_json(manifest):
        raise RuntimeError("B1 live launch manifest differs")
    return validated


def _parse_checksum_ledger(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"B1 checksum ledger is absent: {path.name}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise RuntimeError(f"B1 checksum ledger differs: {path.name}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise RuntimeError(f"B1 checksum ledger is empty: {path.name}")
    return rows


def _validate_hash_ledger(
    path: Path, *, base: Path, expected: set[str] | frozenset[str],
) -> None:
    rows = _parse_checksum_ledger(path)
    if len(rows) != len(expected) or {name for _, name in rows} != set(expected):
        raise RuntimeError(f"B1 checksum population differs: {path.name}")
    for digest, name in rows:
        candidate = base / name
        try:
            candidate.resolve().relative_to(base.resolve())
        except ValueError as exc:
            raise RuntimeError("B1 checksum path escapes run directory") from exc
        if candidate.is_symlink() or not candidate.is_file() or _sha(candidate) != digest:
            raise RuntimeError(f"B1 completed artifact differs: {name}")


def _validate_prepared_local(
    out: Path, *, root: Path = ROOT, env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_hash_ledger(
        out / "prepared.sha256", base=out, expected=PREPARED_FILES,
    )
    manifest = _validate_manifest(
        _load_json(out / "manifest.json", label="launch manifest"),
        root=root, env=env,
    )
    receipt = _manifest_receipt(
        _load_json(out / "manifest-object.json", label="manifest receipt"),
        manifest=manifest,
    )
    build = _load_json(out / "build-metadata.json", label="build metadata")
    _validate_build_metadata(
        build, build_id=manifest["build"]["id"], image=manifest["image"]["uri"],
        code_sha=manifest["code"]["commit_sha"],
    )
    if _sha_bytes(_canonical_json(build)) != manifest["build"]["metadata_sha256"]:
        raise RuntimeError("B1 prepared build metadata differs")
    before = _job_identity(_load_json(out / "job-before.json", label="job before"))
    after = _validate_job_spec(
        _load_json(out / "job-after.json", label="job after"),
        code_sha=manifest["code"]["commit_sha"], image=manifest["image"]["uri"],
    )
    if before != (
        manifest["job"]["uid"], manifest["job"]["prior_generation"],
        manifest["job"]["prior_spec_sha256"],
    ) or after != (
        manifest["job"]["uid"], manifest["job"]["generation"],
        manifest["job"]["spec_sha256"],
    ):
        raise RuntimeError("B1 prepared reused-job chain differs")
    for name in ("job-executions-before.json", "job-executions-after.json"):
        _validate_job_idle(_load_json(out / name, label=name))
    for name in ("schedulers-before.json", "schedulers-after.json"):
        _validate_unscheduled(_load_json(out / name, label=name))
    checks = (
        ("schedulers-before.json", "schedulers_before_sha256", None),
        ("schedulers-after.json", "schedulers_after_sha256", None),
        ("prefix-before.json", "prefix_before_sha256", "result-prefix-and-attempt"),
        ("prefix-after.json", "prefix_after_sha256", "result-prefix-and-attempt"),
        ("lease-before.json", "lease_before_sha256", "historical-outcome-lease"),
        ("lease-after.json", "lease_after_sha256", "historical-outcome-lease"),
    )
    for filename, key, kind in checks:
        value = _load_json(out / filename, label=filename)
        if kind is not None:
            _validate_absence(value, kind=kind)
        if _sha_bytes(_canonical_json(value)) != manifest["preflight"][key]:
            raise RuntimeError(f"B1 prepared receipt differs: {filename}")
    return manifest, receipt


def _validate_lease_receipt(
    value: object, *, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"lease", "object"}:
        raise RuntimeError("B1 historical lease receipt differs")
    lease = value.get("lease")
    obj = value.get("object")
    if not isinstance(lease, dict) or set(lease) != {
        "version", "run_id", "job", "code_sha", "image", "acquired_at",
    } or not isinstance(obj, dict) or set(obj) != {
        "uri", "generation", "sha256", "bytes", "create_only",
    }:
        raise RuntimeError("B1 historical lease fields differ")
    expected = {
        "version": "historical-outcome-active-v1", "run_id": RUN_ID, "job": JOB,
        "code_sha": manifest["code"]["commit_sha"],
        "image": manifest["image"]["uri"],
    }
    if any(lease.get(key) != item for key, item in expected.items()):
        raise RuntimeError("B1 historical lease identity differs")
    _utc_timestamp(lease.get("acquired_at"), label="lease acquisition time")
    generation = str(obj.get("generation", ""))
    if obj.get("uri") != LEASE_URI or obj.get("create_only") is not True or \
            re.fullmatch(r"[1-9][0-9]*", generation) is None or \
            re.fullmatch(r"[0-9a-f]{64}", str(obj.get("sha256", ""))) is None or \
            type(obj.get("bytes")) is not int or obj["bytes"] <= 0:
        raise RuntimeError("B1 historical lease object differs")
    raw = _canonical_json(lease)
    if len(raw) != obj["bytes"] or _sha_bytes(raw) != obj["sha256"]:
        raise RuntimeError("B1 historical lease body differs")
    return {"lease": lease, "object": obj}


def _load_live_lease(
    client: storage.Client, receipt: Mapping[str, Any],
    *, manifest: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    validated = _validate_lease_receipt(receipt, manifest=manifest)
    obj = validated["object"]
    bucket, name = _gcs_parts(LEASE_URI)
    blob = client.bucket(bucket).blob(name, generation=int(obj["generation"]))
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=int(obj["generation"]))
    if str(blob.generation) != obj["generation"] or len(raw) != obj["bytes"] or \
            _sha_bytes(raw) != obj["sha256"] or \
            _strict_json_bytes(raw, label="live lease") != validated["lease"]:
        raise RuntimeError("B1 live historical lease changed")
    return blob, validated


def _recover_live_lease(
    *, manifest_path: Path, receipt_path: Path,
    client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest = _validate_manifest(_load_json(manifest_path, label="launch manifest"))
    gcs = storage.Client(project=PROJECT) if client is None else client
    bucket, name = _gcs_parts(LEASE_URI)
    blob = gcs.bucket(bucket).blob(name)
    blob.reload()
    generation = int(blob.generation)
    raw = blob.download_as_bytes(if_generation_match=generation)
    lease = _strict_json_bytes(raw, label="recoverable lease")
    receipt = {
        "lease": lease,
        "object": {
            "uri": LEASE_URI, "generation": str(generation),
            "sha256": _sha_bytes(raw), "bytes": len(raw), "create_only": True,
        },
    }
    _validate_lease_receipt(receipt, manifest=manifest)
    canonical = _canonical_json(receipt)
    if receipt_path.exists() and receipt_path.read_bytes() != canonical:
        preserved = receipt_path.with_name(receipt_path.name + ".incomplete")
        _write_exclusive_or_equal(preserved, receipt_path.read_bytes())
        receipt_path.unlink()
    _write_exclusive_or_equal(receipt_path, canonical)
    return receipt


def _launch_intent(
    *, manifest: Mapping[str, Any], manifest_receipt: Mapping[str, Any],
    lease_receipt: Mapping[str, Any], registered_at: str,
) -> dict[str, Any]:
    manifest_obj = _manifest_receipt(
        manifest_receipt, manifest=manifest,
    )["object"]
    lease = _validate_lease_receipt(lease_receipt, manifest=manifest)
    return {
        "version": "b1-corpus-tail-launch-intent-v1", "run_id": RUN_ID,
        "manifest_object": {
            key: item for key, item in manifest_obj.items() if key != "create_only"
        },
        "lease_object": dict(lease["object"]),
        "lease_receipt_sha256": _sha_bytes(_canonical_json(lease)),
        "registered_at": _utc_timestamp(registered_at, label="intent time"),
        "job": dict(manifest["job"]),
        "result_prefix": RESULT_PREFIX,
        "attempt_uri": ATTEMPT_URI, "report_uri": REPORT_URI,
        "model_uri": MODEL_URI, "historical_looks": 1, "max_retries": 0,
        "relaunch_if_ambiguous": False,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }


def _validate_launch_intent(
    value: object, *, manifest: Mapping[str, Any],
    manifest_receipt: Mapping[str, Any], lease_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "run_id", "manifest_object", "lease_object",
        "lease_receipt_sha256", "registered_at", "job", "result_prefix",
        "attempt_uri", "report_uri", "model_uri", "historical_looks",
        "max_retries", "relaunch_if_ambiguous", "historical_retry_licensed",
        "production_change_licensed",
    }:
        raise RuntimeError("B1 launch intent fields differ")
    expected = _launch_intent(
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease_receipt, registered_at=str(value["registered_at"]),
    )
    if value != expected:
        raise RuntimeError("B1 launch intent differs")
    return expected


def _intent_receipt(
    value: object, *, intent: Mapping[str, Any], uri: str, version: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "intent_sha256", "object",
    } or value.get("version") != version:
        raise RuntimeError("B1 intent receipt fields differ")
    raw = _canonical_json(intent)
    if value.get("intent_sha256") != _sha_bytes(raw):
        raise RuntimeError("B1 intent receipt SHA differs")
    obj = value.get("object")
    if not isinstance(obj, Mapping):
        raise RuntimeError("B1 intent object differs")
    metadata = _metadata(obj, uri=uri, label="intent", create_only=True)
    if metadata["bytes"] != len(raw) or metadata["sha256"] != _sha_bytes(raw):
        raise RuntimeError("B1 intent object body differs")
    return {"version": version, "intent_sha256": value["intent_sha256"], "object": metadata}


def _publish_launch_intent(
    out: Path, *, client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest, manifest_receipt = _validate_prepared_local(out)
    lease = _validate_lease_receipt(
        _load_json(out / "lease-receipt.json", label="lease receipt"),
        manifest=manifest,
    )
    intent = _launch_intent(
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease, registered_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_exclusive_or_equal(out / "launch-intent.json", _canonical_json(intent))
    gcs = storage.Client(project=PROJECT) if client is None else client
    obj = _upload_create_once_or_same(gcs, LAUNCH_INTENT_URI, _canonical_json(intent))
    receipt = {
        "version": "b1-corpus-tail-launch-intent-receipt-v1",
        "intent_sha256": _sha_bytes(_canonical_json(intent)), "object": obj,
    }
    _intent_receipt(
        receipt, intent=intent, uri=LAUNCH_INTENT_URI,
        version="b1-corpus-tail-launch-intent-receipt-v1",
    )
    _write_exclusive_or_equal(
        out / "launch-intent-object.json", _canonical_json(receipt),
    )
    return receipt


def _load_live_launch_intent(
    out: Path, *, manifest: Mapping[str, Any],
    manifest_receipt: Mapping[str, Any], lease_receipt: Mapping[str, Any],
    client: storage.Client,
) -> tuple[dict[str, Any], dict[str, Any]]:
    intent = _validate_launch_intent(
        _load_json(out / "launch-intent.json", label="launch intent"),
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease_receipt,
    )
    receipt = _intent_receipt(
        _load_json(out / "launch-intent-object.json", label="intent receipt"),
        intent=intent, uri=LAUNCH_INTENT_URI,
        version="b1-corpus-tail-launch-intent-receipt-v1",
    )
    identity = {
        key: item for key, item in receipt["object"].items()
        if key != "create_only"
    }
    _, raw = _download_generation(client, identity, label="launch intent")
    if raw != _canonical_json(intent):
        raise RuntimeError("B1 live launch intent differs")
    return intent, receipt


def _validate_launch_ready(
    *, out: Path, job_current: Mapping[str, Any], executions: object,
    schedulers: object, require_intent: bool,
    client: storage.Client | None = None,
) -> None:
    manifest, manifest_receipt = _validate_prepared_local(out)
    gcs = storage.Client(project=PROJECT) if client is None else client
    _load_live_manifest(manifest, manifest_receipt, client=gcs)
    _require_empty_prefix(gcs)
    _validate_job_idle(executions)
    _validate_unscheduled(schedulers)
    current = _validate_job_spec(
        job_current, code_sha=manifest["code"]["commit_sha"],
        image=manifest["image"]["uri"],
    )
    if current != (
        manifest["job"]["uid"], manifest["job"]["generation"],
        manifest["job"]["spec_sha256"],
    ):
        raise RuntimeError("B1 live reused-job generation/spec differs")
    lease = _validate_lease_receipt(
        _load_json(out / "lease-receipt.json", label="lease receipt"),
        manifest=manifest,
    )
    _load_live_lease(gcs, lease, manifest=manifest)
    if require_intent:
        _load_live_launch_intent(
            out, manifest=manifest, manifest_receipt=manifest_receipt,
            lease_receipt=lease, client=gcs,
        )


def _execution_ledger(path: Path) -> tuple[str, str, str, str, str, str]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("B1 execution ledger is absent")
    lines = path.read_text(encoding="utf-8").splitlines()
    fields = lines[0].split() if len(lines) == 1 else []
    if len(fields) != 6 or fields[0] != JOB or re.fullmatch(
        rf"{re.escape(JOB)}-[a-z0-9]+", fields[1],
    ) is None or fields[2:5] != [ATTEMPT_URI, REPORT_URI, MODEL_URI] or \
            re.fullmatch(r"[1-9][0-9]*", fields[5]) is None:
        raise RuntimeError("B1 execution ledger differs")
    return tuple(fields)  # type: ignore[return-value]


def _validate_launch_local(
    out: Path, *, root: Path = ROOT, env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    _validate_hash_ledger(out / "launch.sha256", base=out, expected=LAUNCH_FILES)
    manifest, manifest_receipt = _validate_prepared_local(out, root=root, env=env)
    lease = _validate_lease_receipt(
        _load_json(out / "lease-receipt.json", label="lease receipt"),
        manifest=manifest,
    )
    intent = _validate_launch_intent(
        _load_json(out / "launch-intent.json", label="launch intent"),
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease,
    )
    intent_receipt = _intent_receipt(
        _load_json(out / "launch-intent-object.json", label="intent receipt"),
        intent=intent, uri=LAUNCH_INTENT_URI,
        version="b1-corpus-tail-launch-intent-receipt-v1",
    )
    intent_generation = intent_receipt["object"]["generation"]
    for suffix in ("launch", "launch-final"):
        observed = _validate_job_spec(
            _load_json(out / f"job-{suffix}.json", label=f"job {suffix}"),
            code_sha=manifest["code"]["commit_sha"], image=manifest["image"]["uri"],
        )
        if observed != (
            manifest["job"]["uid"], manifest["job"]["generation"],
            manifest["job"]["spec_sha256"],
        ):
            raise RuntimeError("B1 launch reused-job identity differs")
        _validate_job_idle(_load_json(
            out / f"job-executions-{suffix}.json", label=f"executions {suffix}",
        ))
        _validate_unscheduled(_load_json(
            out / f"schedulers-{suffix}.json", label=f"schedulers {suffix}",
        ))
        _validate_absence(
            _load_json(out / f"prefix-{suffix}.json", label=f"prefix {suffix}"),
            kind="result-prefix-and-attempt",
        )
    _, execution, _, _, _, ledger_generation = _execution_ledger(out / "executions.txt")
    if ledger_generation != intent_generation:
        raise RuntimeError("B1 execution/intent generation differs")
    return manifest, manifest_receipt, lease, execution, intent_generation


def _load_remote_launch_bundle(
    *, intent_generation: str, client: storage.Client,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if re.fullmatch(r"[1-9][0-9]*", intent_generation) is None:
        raise RuntimeError("B1 launch-intent generation differs")
    bucket, name = _gcs_parts(LAUNCH_INTENT_URI)
    blob = client.bucket(bucket).blob(name, generation=int(intent_generation))
    blob.reload()
    intent_raw = blob.download_as_bytes(if_generation_match=int(intent_generation))
    if str(blob.generation) != intent_generation or str(blob.metageneration) != "1":
        raise RuntimeError("B1 remote launch-intent object identity differs")
    intent = _strict_json_bytes(intent_raw, label="remote launch intent")
    if not isinstance(intent, dict) or intent.get("run_id") != RUN_ID:
        raise RuntimeError("B1 remote launch intent identity differs")
    manifest_identity = intent.get("manifest_object")
    if not isinstance(manifest_identity, Mapping):
        raise RuntimeError("B1 remote manifest identity is absent")
    manifest_meta, manifest_raw = _download_generation(
        client, manifest_identity, label="remote manifest",
    )
    manifest = _strict_json_bytes(manifest_raw, label="remote manifest")
    if not isinstance(manifest, dict) or manifest_raw != _canonical_json(manifest):
        raise RuntimeError("B1 remote manifest is not canonical")
    _validate_manifest(manifest, runtime_only=True)
    manifest_receipt = {
        "version": "b1-corpus-tail-manifest-receipt-v1",
        "manifest_sha256": _sha_bytes(manifest_raw),
        "object": {**manifest_meta, "create_only": True},
    }
    lease_object = intent.get("lease_object")
    if not isinstance(lease_object, dict):
        raise RuntimeError("B1 remote launch lease object is absent")
    # The lease receipt is reconstructed from the exact current generation.
    lease_identity = {
        "uri": LEASE_URI,
        "generation": str(lease_object.get("generation", "")),
        "metageneration": "1",
        "bytes": lease_object.get("bytes"),
        "sha256": lease_object.get("sha256"),
    }
    _, lease_raw = _download_generation(client, lease_identity, label="active lease")
    lease_body = _strict_json_bytes(lease_raw, label="active lease")
    lease_receipt = {"lease": lease_body, "object": dict(lease_object)}
    _validate_lease_receipt(lease_receipt, manifest=manifest)
    _validate_launch_intent(
        intent, manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease_receipt,
    )
    if intent_raw != _canonical_json(intent) or _sha_bytes(intent_raw) != \
            _sha_bytes(_canonical_json(intent)):
        raise RuntimeError("B1 remote launch intent is not canonical")
    return manifest, manifest_receipt, lease_receipt, intent


def _validate_attempt(
    value: object, *, manifest: Mapping[str, Any],
    lease_receipt: Mapping[str, Any], metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "run_id", "protocol_sha256", "started_at", "lease",
        "b1_protocol_sha256", "b1_report_sha256", "b1_runner_sha256",
        "uses_realized_outcomes_at_creation", "retry_licensed",
        "production_licensed",
    }:
        raise RuntimeError("B1 historical attempt fields differ")
    expected = {
        "version": "b1-corpus-tail-historical-attempt-v1", "run_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "lease": dict(lease_receipt),
        "b1_protocol_sha256": runner.B1_PROTOCOL_SHA256,
        "b1_report_sha256": runner.B1_REPORT_SHA256,
        "b1_runner_sha256": runner.B1_RUNNER_SHA256,
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False, "production_licensed": False,
    }
    if any(value.get(key) != item for key, item in expected.items()):
        raise RuntimeError("B1 historical attempt identity differs")
    _utc_timestamp(value.get("started_at"), label="historical attempt time")
    if metadata is not None:
        _metadata(metadata, uri=ATTEMPT_URI, label="historical attempt")
    return value


METRIC_KEYS: Final = frozenset({
    "rows", "slates", "prevalence_ge200", "prevalence_ge210",
    "average_precision_ge200", "p_line_average_precision_ge200",
    "average_precision_ge210", "p_line_average_precision_ge210",
    "brier_ge200", "fold_prevalence_brier_ge200",
    "spearman_tail_score_vs_actual", "mean_predicted_ge200",
})
BOOK_KEYS: Final = frozenset({
    "slates", "mean_weekly_max", "median_weekly_max", "maximum",
    "threshold_counts",
})
THRESHOLD_KEYS: Final = frozenset({"187", "194", "200", "210", "220", "230", "240"})


def _validate_metric_block(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != METRIC_KEYS:
        raise RuntimeError(f"B1 {label} metric fields differ")
    _positive_int(value.get("rows"), label=f"{label} rows")
    _positive_int(value.get("slates"), label=f"{label} slates")
    for key in METRIC_KEYS - {"rows", "slates"}:
        _finite(value.get(key), label=f"{label} {key}")
    for key in (
        "prevalence_ge200", "prevalence_ge210", "average_precision_ge200",
        "p_line_average_precision_ge200", "average_precision_ge210",
        "p_line_average_precision_ge210", "brier_ge200",
        "fold_prevalence_brier_ge200", "mean_predicted_ge200",
    ):
        if not 0.0 <= float(value[key]) <= 1.0:
            raise RuntimeError(f"B1 {label} bounded metric differs: {key}")
    return value


def _validate_book(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BOOK_KEYS:
        raise RuntimeError(f"B1 {label} book fields differ")
    _positive_int(value.get("slates"), label=f"{label} slates")
    for key in ("mean_weekly_max", "median_weekly_max", "maximum"):
        _finite(value.get(key), label=f"{label} {key}")
    counts = value.get("threshold_counts")
    if not isinstance(counts, dict) or set(counts) != THRESHOLD_KEYS:
        raise RuntimeError(f"B1 {label} threshold counts differ")
    for key in THRESHOLD_KEYS:
        _nonnegative_int(counts[key], label=f"{label} threshold {key}")
        if counts[key] > value["slates"]:
            raise RuntimeError(f"B1 {label} threshold count exceeds slates")
    ordered = [counts[key] for key in ("187", "194", "200", "210", "220", "230", "240")]
    if ordered != sorted(ordered, reverse=True):
        raise RuntimeError(f"B1 {label} threshold counts are not monotone")
    return value


def _validate_redundancy(value: object, *, label: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "candidate_budget", "entry_budget", "max_shared_players_first_pass",
        "overlap_rejections_before_fill", "deterministic_backfills",
    } or _positive_int(value.get("candidate_budget"), label=f"{label} candidates") < 80 or \
            value.get("entry_budget") != 80 or \
            value.get("max_shared_players_first_pass") != 7:
        raise RuntimeError(f"B1 {label} redundancy differs")
    _nonnegative_int(value.get("overlap_rejections_before_fill"), label=f"{label} rejects")
    _nonnegative_int(value.get("deterministic_backfills"), label=f"{label} backfills")


def _replay_decision(report: Mapping[str, Any]) -> tuple[dict[str, bool], bool]:
    loso = _validate_metric_block(report.get("loso"), label="LOSO")
    _validate_metric_block(
        report.get("walk_forward_companion"), label="walk-forward",
    )
    exact80 = report.get("exact80")
    if not isinstance(exact80, dict) or set(exact80) != {
        "books", "slates", "selection_gates",
    }:
        raise RuntimeError("B1 exact80 fields differ")
    books = exact80.get("books")
    if not isinstance(books, dict) or set(books) != {
        "control", "challenger", "naive_p_line",
    }:
        raise RuntimeError("B1 exact80 book population differs")
    for key in books:
        _validate_book(books[key], label=key)
    slates = exact80.get("slates")
    if not isinstance(slates, list) or len(slates) != 54:
        raise RuntimeError("B1 exact80 slate population differs")
    keys: set[tuple[int, int]] = set()
    equal_budgets = True
    for row in slates:
        if not isinstance(row, dict) or set(row) != {
            "season", "week", "candidate_budget_control",
            "candidate_budget_challenger", "entries_control",
            "entries_challenger", "challenger_control_overlap",
            "challenger_redundancy", "naive_redundancy",
        }:
            raise RuntimeError("B1 exact80 slate receipt fields differ")
        season = _positive_int(row.get("season"), label="slate season")
        week = _positive_int(row.get("week"), label="slate week")
        if season not in {2023, 2024, 2025} or (season, week) in keys:
            raise RuntimeError("B1 exact80 slate identity differs")
        keys.add((season, week))
        control_budget = _positive_int(
            row.get("candidate_budget_control"), label="control candidate budget",
        )
        challenger_budget = _positive_int(
            row.get("candidate_budget_challenger"), label="challenger candidate budget",
        )
        equal_budgets = equal_budgets and control_budget == challenger_budget and \
            row.get("entries_control") == row.get("entries_challenger") == 80
        overlap = _nonnegative_int(
            row.get("challenger_control_overlap"), label="book overlap",
        )
        if overlap > 80:
            raise RuntimeError("B1 exact80 book overlap differs")
        _validate_redundancy(row.get("challenger_redundancy"), label="challenger")
        _validate_redundancy(row.get("naive_redundancy"), label="naive")
    prediction = {
        "ge200_pr_beats_prevalence": (
            loso["average_precision_ge200"] > loso["prevalence_ge200"]
        ),
        "ge200_pr_beats_p_line": (
            loso["average_precision_ge200"] > loso["p_line_average_precision_ge200"]
        ),
        "ge210_pr_beats_prevalence": (
            loso["average_precision_ge210"] > loso["prevalence_ge210"]
        ),
        "positive_brier_skill_vs_fold_prevalence": (
            loso["brier_ge200"] < loso["fold_prevalence_brier_ge200"]
        ),
    }
    control = books["control"]
    treatment = books["challenger"]
    selection = {
        "equal_candidate_and_entry_budgets": bool(equal_budgets),
        "mean_weekly_max_improves": (
            treatment["mean_weekly_max"] > control["mean_weekly_max"]
        ),
        "ge200_count_improves": (
            treatment["threshold_counts"]["200"]
            > control["threshold_counts"]["200"]
        ),
        "ge210_count_noninferior": (
            treatment["threshold_counts"]["210"]
            >= control["threshold_counts"]["210"]
        ),
        "ge194_count_protected": (
            treatment["threshold_counts"]["194"]
            >= control["threshold_counts"]["194"]
        ),
    }
    if exact80.get("selection_gates") != selection:
        raise RuntimeError("B1 reported exact80 gates differ from independent replay")
    gates = {**prediction, **selection}
    if report.get("historical_gates") != gates:
        raise RuntimeError("B1 historical gates differ from independent replay")
    return gates, all(gates.values())


def _validate_report(
    value: object, *, manifest: Mapping[str, Any],
    lease_receipt: Mapping[str, Any], attempt: Mapping[str, Any],
    attempt_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "population", "model", "loso", "walk_forward_companion",
        "exact80", "historical_gates", "historical_pass", "licenses",
        "uses_winner_target_or_feature", "uses_realized_outcomes",
        "source_lock", "model_artifact_sha256", "model_file_sha256",
    } or value.get("version") != "b1-corpus-tail-historical-evaluation-v1" or \
            value.get("uses_winner_target_or_feature") is not False or \
            value.get("uses_realized_outcomes") is not True:
        raise RuntimeError("B1 historical report boundary differs")
    population = value.get("population")
    if not isinstance(population, dict) or set(population) != {
        "deduplicated_rosters", "slates", "seasons", "canonical_candidate_rows",
    } or population.get("deduplicated_rosters") != runner.EXPECTED_DEDUP_ROWS or \
            population.get("slates") != runner.EXPECTED_SLATES or \
            population.get("seasons") != [2023, 2024, 2025] or \
            _positive_int(
                population.get("canonical_candidate_rows"),
                label="canonical candidates",
            ) < 80 * runner.EXPECTED_SLATES:
        raise RuntimeError("B1 historical population differs")
    model = value.get("model")
    if model != {
        "version": science.MODEL_VERSION,
        "feature_columns": list(science.FEATURE_COLUMNS),
        "target": "actual_score_ge_200", "winner_fields_used": [],
        "hyperparameter_grid": [],
    }:
        raise RuntimeError("B1 historical model contract differs")
    _, passed = _replay_decision(value)
    if value.get("historical_pass") is not passed or value.get("licenses") != {
        "write_2026_shadow_artifact": passed, "run_2026_shadow": passed,
        "production": False, "historical_retune": False,
    }:
        raise RuntimeError("B1 historical license truth table differs")
    _hex(value.get("model_artifact_sha256"), length=64, label="model artifact SHA")
    if passed:
        _hex(value.get("model_file_sha256"), length=64, label="model file SHA")
    elif value.get("model_file_sha256") is not None:
        raise RuntimeError("B1 failed report unexpectedly licenses a model file")
    source = value.get("source_lock")
    if not isinstance(source, dict) or set(source) != {
        "executed_at", "protocol_sha256", "candidate_frame_sha256",
        "player_frame_sha256", "b1_protocol_sha256", "b1_report_sha256",
        "b1_runner_sha256", "historical_lease", "historical_attempt",
        "candidate_query", "player_query", "realized_outcome_columns_read",
    } or source.get("protocol_sha256") != PROTOCOL_SHA256 or \
            source.get("b1_protocol_sha256") != runner.B1_PROTOCOL_SHA256 or \
            source.get("b1_report_sha256") != runner.B1_REPORT_SHA256 or \
            source.get("b1_runner_sha256") != runner.B1_RUNNER_SHA256 or \
            source.get("historical_lease") != lease_receipt["object"] or \
            source.get("historical_attempt") != {
                **attempt_metadata, "create_only": True,
            } or source.get("realized_outcome_columns_read") != ["actual_score"]:
        raise RuntimeError("B1 historical source lock differs")
    executed = _utc_timestamp(source.get("executed_at"), label="report execution time")
    for key in ("candidate_frame_sha256", "player_frame_sha256"):
        _hex(source.get(key), length=64, label=key)
    query_times = []
    expected_queries = {
        "candidate_query": runner._candidate_sql(outcomes=True, one_slate=False),
        "player_query": runner._player_sql(one_slate=False),
    }
    for key, sql in expected_queries.items():
        row = source.get(key)
        if not isinstance(row, dict) or set(row) != {
            "job_id", "location", "created", "started", "ended",
            "total_bytes_processed", "query_sha256",
        } or not isinstance(row.get("job_id"), str) or not row["job_id"] or \
                row.get("location") != "US" or row.get("query_sha256") != \
                _sha_bytes(sql.encode()) or type(row.get("total_bytes_processed")) is not int or \
                row["total_bytes_processed"] < 0:
            raise RuntimeError(f"B1 {key} receipt differs")
        times = [
            datetime.fromisoformat(
                _utc_timestamp(row.get(field), label=f"{key} {field}").replace("Z", "+00:00")
            ) for field in ("created", "started", "ended")
        ]
        if times != sorted(times):
            raise RuntimeError(f"B1 {key} chronology differs")
        query_times.extend(times)
    attempt_time = datetime.fromisoformat(
        str(attempt["started_at"]).replace("Z", "+00:00")
    )
    executed_time = datetime.fromisoformat(executed.replace("Z", "+00:00"))
    if min(query_times) < attempt_time or max(query_times) > executed_time:
        raise RuntimeError("B1 attempt/query/report chronology differs")
    return value


def _validate_model(value: object, *, report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("B1 model artifact is not an object")
    expected_keys = {
        "version", "target", "target_threshold", "feature_columns",
        "impute_medians", "standardize_means", "standardize_scales",
        "coefficients", "intercept", "training_rows", "training_slates",
        "training_seasons", "training_prevalence_ge200", "fixed_estimator",
        "winner_fields_used", "production_licensed", "prospective_shadow_only",
        "historical_gate_passed", "historical_gate_scope", "protocol_sha256",
        "historical_run_id", "historical_source_rows",
        "historical_deduplicated_rosters", "artifact_sha256",
    }
    if set(value) != expected_keys or value.get("version") != science.MODEL_VERSION or \
            value.get("target") != "actual_score_ge_200" or \
            value.get("target_threshold") != 200.0 or \
            value.get("feature_columns") != list(science.FEATURE_COLUMNS) or \
            value.get("winner_fields_used") != [] or \
            value.get("production_licensed") is not False or \
            value.get("prospective_shadow_only") is not True or \
            value.get("historical_gate_passed") is not True or \
            value.get("historical_gate_scope") != "LOSO-2023-2025-B1-union" or \
            value.get("protocol_sha256") != PROTOCOL_SHA256 or \
            value.get("historical_run_id") != RUN_ID or \
            value.get("historical_source_rows") != runner.EXPECTED_SOURCE_ROWS or \
            value.get("historical_deduplicated_rosters") != runner.EXPECTED_DEDUP_ROWS:
        raise RuntimeError("B1 model artifact boundary differs")
    if value.get("fixed_estimator") != {
        "type": "sklearn.linear_model.LogisticRegression", "C": 1.0,
        "solver": "lbfgs", "penalty": "l2", "class_weight": None,
        "max_iter": 2000,
        "sample_weight": "each season-week has equal total weight",
    }:
        raise RuntimeError("B1 model estimator differs")
    width = len(science.FEATURE_COLUMNS)
    for key in (
        "impute_medians", "standardize_means", "standardize_scales", "coefficients",
    ):
        vector = value.get(key)
        if not isinstance(vector, list) or len(vector) != width:
            raise RuntimeError(f"B1 model vector differs: {key}")
        for item in vector:
            _finite(item, label=f"model {key}")
    if any(float(item) <= 0 for item in value["standardize_scales"]):
        raise RuntimeError("B1 model scaling differs")
    _finite(value.get("intercept"), label="model intercept")
    _finite(value.get("training_prevalence_ge200"), label="training prevalence")
    if not 0.0 < float(value["training_prevalence_ge200"]) < 1.0:
        raise RuntimeError("B1 model training prevalence differs")
    if value.get("training_rows") != runner.EXPECTED_DEDUP_ROWS or \
            value.get("training_slates") != runner.EXPECTED_SLATES or \
            value.get("training_seasons") != [2023, 2024, 2025] or \
            value.get("artifact_sha256") != science.artifact_sha256(value) or \
            value.get("artifact_sha256") != report["model_artifact_sha256"]:
        raise RuntimeError("B1 model artifact identity differs")
    return value


def _inventory_metadata(value: object, *, failure: bool = False) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RuntimeError("B1 result inventory differs")
    allowed = {ATTEMPT_URI, REPORT_URI, MODEL_URI}
    seen: set[str] = set()
    rows = []
    for row in value:
        if not isinstance(row, dict) or set(row) != {
            "uri", "generation", "metageneration", "bytes",
        } or row.get("uri") not in allowed or row["uri"] in seen or \
                re.fullmatch(r"[1-9][0-9]*", str(row.get("generation", ""))) is None or \
                str(row.get("metageneration", "")) != "1" or \
                type(row.get("bytes")) is not int or row["bytes"] <= 0:
            raise RuntimeError("B1 result inventory row differs")
        seen.add(str(row["uri"]))
        rows.append(dict(row))
    if not failure and ATTEMPT_URI not in seen:
        raise RuntimeError("B1 successful inventory lacks the one-shot attempt")
    return sorted(rows, key=lambda row: row["uri"])


def execute_frozen(
    *, intent_generation: str, client: storage.Client | None = None,
    runner_main: Callable[[list[str]], int] = runner.main,
) -> dict[str, Any]:
    """Run the unchanged one-shot runner, then publish its outputs create-only."""
    if os.environ.get("B1_CORPUS_TAIL_HISTORICAL_ENABLED") != "1":
        raise RuntimeError("B1 historical transport is not explicitly enabled")
    gcs = storage.Client(project=PROJECT) if client is None else client
    manifest, _, lease, _ = _load_remote_launch_bundle(
        intent_generation=intent_generation, client=gcs,
    )
    if os.environ.get("CODE_SHA") != manifest["code"]["commit_sha"] or \
            os.environ.get("ANALYSIS_IMAGE") != manifest["image"]["uri"]:
        raise RuntimeError("B1 execution environment differs from manifest")
    _require_empty_prefix(gcs)
    with tempfile.TemporaryDirectory(prefix="b1-corpus-tail-") as directory:
        temp = Path(directory)
        lease_path = temp / "lease-receipt.json"
        report_path = temp / "historical-report.json"
        model_path = temp / "model.json"
        attempt_receipt_path = temp / "attempt-receipt.json"
        lease_path.write_bytes(_canonical_json(lease))
        result = runner_main([
            "--historical-report", str(report_path),
            "--historical-model", str(model_path),
            "--protocol-sha256", PROTOCOL_SHA256,
            "--historical-lease-receipt", str(lease_path),
            "--historical-attempt-receipt", str(attempt_receipt_path),
        ])
        if result != 0:
            raise RuntimeError("B1 frozen runner returned nonzero")
        attempt_receipt = _load_json(attempt_receipt_path, label="attempt receipt")
        if not isinstance(attempt_receipt, dict) or set(attempt_receipt) != {
            "attempt", "object",
        }:
            raise RuntimeError("B1 runner attempt receipt differs")
        attempt_obj = attempt_receipt["object"]
        if not isinstance(attempt_obj, dict):
            raise RuntimeError("B1 runner attempt object differs")
        attempt_identity = _metadata(
            {key: item for key, item in attempt_obj.items() if key != "create_only"},
            uri=ATTEMPT_URI, label="attempt",
        )
        _, attempt_raw = _download_generation(gcs, attempt_identity, label="attempt")
        attempt = _strict_json_bytes(attempt_raw, label="attempt")
        _validate_attempt(
            attempt, manifest=manifest, lease_receipt=lease,
            metadata=attempt_identity,
        )
        if _inventory_metadata(_prefix_inventory(gcs)) != [{
            "uri": ATTEMPT_URI, "generation": attempt_identity["generation"],
            "metageneration": attempt_identity["metageneration"],
            "bytes": attempt_identity["bytes"],
        }]:
            raise RuntimeError("B1 prefix changed between attempt and output publication")
        report_raw = report_path.read_bytes()
        report = _strict_json_bytes(report_raw, label="runner report")
        if not isinstance(report, dict) or report_raw != _canonical_json(report):
            raise RuntimeError("B1 runner report is not canonical")
        _validate_report(
            report, manifest=manifest, lease_receipt=lease, attempt=attempt,
            attempt_metadata=attempt_identity,
        )
        model_obj = None
        if report["historical_pass"]:
            model_raw = model_path.read_bytes()
            model = _strict_json_bytes(model_raw, label="runner model")
            if not isinstance(model, dict) or model_raw != _canonical_json(model):
                raise RuntimeError("B1 runner model is not canonical")
            _validate_model(model, report=report)
            if _sha_bytes(model_raw) != report["model_file_sha256"]:
                raise RuntimeError("B1 runner model file SHA differs")
            model_obj = _upload_create_once(gcs, MODEL_URI, model_raw)
        elif model_path.exists():
            raise RuntimeError("B1 failed historical gate emitted a model")
        report_obj = _upload_create_once(gcs, REPORT_URI, report_raw)
        expected_uris = {ATTEMPT_URI, REPORT_URI}
        if model_obj is not None:
            expected_uris.add(MODEL_URI)
        inventory = _inventory_metadata(_prefix_inventory(gcs))
        if {row["uri"] for row in inventory} != expected_uris:
            raise RuntimeError("B1 final producer inventory differs")
        return {
            "historical_pass": bool(report["historical_pass"]),
            "report_object": report_obj, "model_object": model_obj,
            "attempt_object": attempt_identity,
        }


def _gcloud_execution(name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="b1-execution-") as directory:
        raw_path = Path(directory) / "execution.raw.json"
        with raw_path.open("xb") as handle:
            subprocess.run([
                "gcloud", "run", "jobs", "executions", "describe", name,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ], check=True, stdout=handle)
        value = _strict_json_bytes(raw_path.read_bytes(), label="execution metadata")
    if not isinstance(value, dict):
        raise RuntimeError("B1 execution metadata differs")
    return value


def _execution_count(status: Mapping[str, Any], key: str) -> int:
    return 0 if key not in status else _nonnegative_int(
        status[key], label=f"execution {key}",
    )


def _validate_execution_terminal(
    value: Mapping[str, Any], *, execution: str, manifest: Mapping[str, Any],
    intent_generation: str, completed_status: str,
) -> None:
    metadata = value.get("metadata")
    status = value.get("status")
    if not isinstance(metadata, Mapping) or not isinstance(status, Mapping):
        raise RuntimeError("B1 execution metadata schema differs")
    labels = metadata.get("labels")
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if metadata.get("name") != execution or _positive_int(
        metadata.get("generation"), label="execution generation",
    ) != 1 or not isinstance(labels, Mapping) or \
            labels.get("run.googleapis.com/job") != JOB or \
            labels.get("run.googleapis.com/jobUid") != JOB_UID or \
            str(labels.get("run.googleapis.com/jobGeneration")) != \
            manifest["job"]["generation"] or _positive_int(
                status.get("observedGeneration"), label="execution observed generation",
            ) != 1:
        raise RuntimeError("B1 execution identity differs")
    expected_success = 1 if completed_status == "True" else 0
    expected_failure = 0 if completed_status == "True" else 1
    if len(completed) != 1 or completed[0].get("status") != completed_status or \
            _execution_count(status, "succeededCount") != expected_success or \
            _execution_count(status, "failedCount") != expected_failure or \
            _execution_count(status, "cancelledCount") != 0 or \
            _execution_count(status, "retriedCount") != 0 or \
            not isinstance(status.get("completionTime"), str) or \
            not status["completionTime"]:
        raise RuntimeError("B1 execution is not strict terminal")
    spec = value.get("spec")
    outer = spec if isinstance(spec, Mapping) else {}
    task = outer.get("template", {}).get("spec", {})
    _container_contract(
        outer=outer, task=task,
        expected=_execution_contract(
            manifest=manifest, intent_generation=intent_generation,
        ), label="execution",
    )


def _harvest_paths(out: Path) -> dict[str, Path]:
    base = out / "harvest"
    return {
        "execution": base / "execution.json", "inventory": base / "inventory.json",
        "attempt_meta": base / "attempt-metadata.json", "attempt": base / "attempt.json",
        "report_meta": base / "report-metadata.json", "report": base / "historical-report.json",
        "model_meta": base / "model-metadata.json", "model": base / "model.json",
    }


def _completion_bytes(
    *, report: Mapping[str, Any], execution: Mapping[str, Any],
    report_metadata: Mapping[str, Any],
) -> bytes:
    disposition = (
        "historical-gates-pass-shadow-licensed"
        if report["historical_pass"] else "historical-gates-fail-closed"
    )
    return "".join((
        f"run_id={RUN_ID}\n",
        f"validated_execution_completion={execution['status']['completionTime']}\n",
        "uses_realized_outcomes=true\n",
        "actual_outcomes_queried=true\n",
        f"disposition={disposition}\n",
        f"report_generation={report_metadata['generation']}\n",
        f"report_sha256={report_metadata['sha256']}\n",
        f"historical_pass={str(report['historical_pass']).lower()}\n",
        "historical_outcome_lease_release_licensed=true\n",
        "historical_retry_licensed=false\n",
        "production_change_licensed=false\n",
    )).encode("utf-8")


def _validate_completed_local(
    out: Path, *, manifest: Mapping[str, Any], lease: Mapping[str, Any],
    execution_name: str, intent_generation: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    paths = _harvest_paths(out)
    execution = _load_json(paths["execution"], label="retained execution")
    inventory = _load_json(paths["inventory"], label="retained inventory")
    if not isinstance(execution, dict):
        raise RuntimeError("B1 retained execution differs")
    _validate_execution_terminal(
        execution, execution=execution_name, manifest=manifest,
        intent_generation=intent_generation, completed_status="True",
    )
    inventory = _inventory_metadata(inventory)
    identities: dict[str, tuple[dict[str, Any], bytes]] = {}
    for uri, meta_key, body_key in (
        (ATTEMPT_URI, "attempt_meta", "attempt"),
        (REPORT_URI, "report_meta", "report"),
        (MODEL_URI, "model_meta", "model"),
    ):
        matches = [row for row in inventory if row["uri"] == uri]
        if not matches:
            if uri == MODEL_URI:
                continue
            raise RuntimeError("B1 retained inventory lacks required object")
        metadata = _load_json(paths[meta_key], label=f"retained {uri} metadata")
        raw = paths[body_key].read_bytes()
        if not isinstance(metadata, dict):
            raise RuntimeError("B1 retained object metadata differs")
        checked = _metadata(metadata, uri=uri, label="retained result")
        if checked["bytes"] != len(raw) or checked["sha256"] != _sha_bytes(raw) or \
                any(checked[key] != matches[0][key] for key in (
                    "uri", "generation", "metageneration", "bytes",
                )):
            raise RuntimeError("B1 retained object content identity differs")
        identities[uri] = (checked, raw)
    attempt = _strict_json_bytes(identities[ATTEMPT_URI][1], label="retained attempt")
    if identities[ATTEMPT_URI][1] != _canonical_json(attempt):
        raise RuntimeError("B1 retained attempt is not canonical")
    _validate_attempt(
        attempt, manifest=manifest, lease_receipt=lease,
        metadata=identities[ATTEMPT_URI][0],
    )
    report = _strict_json_bytes(identities[REPORT_URI][1], label="retained report")
    if not isinstance(report, dict) or identities[REPORT_URI][1] != _canonical_json(report):
        raise RuntimeError("B1 retained report differs")
    _validate_report(
        report, manifest=manifest, lease_receipt=lease, attempt=attempt,
        attempt_metadata=identities[ATTEMPT_URI][0],
    )
    has_model = MODEL_URI in identities
    if has_model != bool(report["historical_pass"]):
        raise RuntimeError("B1 retained model population differs from decision")
    if has_model:
        model = _strict_json_bytes(identities[MODEL_URI][1], label="retained model")
        if identities[MODEL_URI][1] != _canonical_json(model):
            raise RuntimeError("B1 retained model is not canonical")
        _validate_model(model, report=report)
        if identities[MODEL_URI][0]["sha256"] != report["model_file_sha256"]:
            raise RuntimeError("B1 retained model file SHA differs")
    expected = {
        "harvest/execution.json", "harvest/inventory.json",
        "harvest/attempt-metadata.json", "harvest/attempt.json",
        "harvest/report-metadata.json", "harvest/historical-report.json",
        "completion.txt",
    }
    if has_model:
        expected |= {"harvest/model-metadata.json", "harvest/model.json"}
    completion = _completion_bytes(
        report=report, execution=execution,
        report_metadata=identities[REPORT_URI][0],
    )
    _write_exclusive_or_equal(out / "completion.txt", completion)
    ledger = "".join(
        f"{_sha(out / name)}  {name}\n" for name in sorted(expected)
    ).encode("utf-8")
    _write_exclusive_or_equal(out / "finish.sha256", ledger)
    _validate_hash_ledger(out / "finish.sha256", base=out, expected=expected)
    return execution, identities[REPORT_URI][0], report, inventory


def finish(
    *, out: Path = DEFAULT_OUT,
    execution_loader: Callable[[str], dict[str, Any]] = _gcloud_execution,
    client: storage.Client | None = None,
) -> dict[str, Any]:
    """Open no result body until the exact execution is strict terminal success."""
    manifest, manifest_receipt, lease, execution_name, intent_generation = \
        _validate_launch_local(out)
    if (out / "finish.sha256").is_file():
        _, report_meta, report, inventory = _validate_completed_local(
            out, manifest=manifest, lease=lease, execution_name=execution_name,
            intent_generation=intent_generation,
        )
        return {"report": report, "object": report_meta, "inventory": inventory,
                "already_complete": True}
    gcs = storage.Client(project=PROJECT) if client is None else client
    _load_live_manifest(manifest, manifest_receipt, client=gcs)
    _load_live_lease(gcs, lease, manifest=manifest)
    _load_live_launch_intent(
        out, manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease, client=gcs,
    )
    execution = execution_loader(execution_name)
    _validate_execution_terminal(
        execution, execution=execution_name, manifest=manifest,
        intent_generation=intent_generation, completed_status="True",
    )
    # Body firewall: only now inventory, then generation-pin every body.
    inventory = _inventory_metadata(_prefix_inventory(gcs))
    uris = {row["uri"] for row in inventory}
    if not {ATTEMPT_URI, REPORT_URI} <= uris or not uris <= {
        ATTEMPT_URI, REPORT_URI, MODEL_URI,
    }:
        raise RuntimeError("B1 strict-success inventory differs")
    downloaded: dict[str, tuple[dict[str, Any], bytes]] = {}
    for row in inventory:
        # Metadata inventory intentionally precedes bodies.  Resolve the hash
        # only through a generation-qualified read after the exact URI set.
        bucket, name = _gcs_parts(row["uri"])
        blob = gcs.bucket(bucket).blob(name, generation=int(row["generation"]))
        blob.reload()
        raw = blob.download_as_bytes(if_generation_match=int(row["generation"]))
        observed = _blob_metadata(blob, uri=row["uri"], raw=raw)
        if any(observed[key] != row[key] for key in (
            "uri", "generation", "metageneration", "bytes",
        )):
            raise RuntimeError("B1 result metadata changed after inventory")
        downloaded[row["uri"]] = (observed, raw)
    attempt = _strict_json_bytes(downloaded[ATTEMPT_URI][1], label="result attempt")
    _validate_attempt(
        attempt, manifest=manifest, lease_receipt=lease,
        metadata=downloaded[ATTEMPT_URI][0],
    )
    report = _strict_json_bytes(downloaded[REPORT_URI][1], label="result report")
    if not isinstance(report, dict) or downloaded[REPORT_URI][1] != _canonical_json(report):
        raise RuntimeError("B1 result report is not canonical")
    _validate_report(
        report, manifest=manifest, lease_receipt=lease, attempt=attempt,
        attempt_metadata=downloaded[ATTEMPT_URI][0],
    )
    if (MODEL_URI in downloaded) != bool(report["historical_pass"]):
        raise RuntimeError("B1 result/model population differs")
    if MODEL_URI in downloaded:
        model = _strict_json_bytes(downloaded[MODEL_URI][1], label="result model")
        _validate_model(model, report=report)
        if downloaded[MODEL_URI][0]["sha256"] != report["model_file_sha256"]:
            raise RuntimeError("B1 result model SHA differs")
    pending = out / ".strict-harvest.pending"
    harvest = out / "harvest"
    if pending.exists() or harvest.exists():
        raise RuntimeError("B1 immutable harvest path already exists")
    pending.mkdir()
    (pending / "execution.json").write_bytes(_canonical_json(execution))
    (pending / "inventory.json").write_bytes(_canonical_json(inventory))
    mapping = {
        ATTEMPT_URI: ("attempt-metadata.json", "attempt.json"),
        REPORT_URI: ("report-metadata.json", "historical-report.json"),
        MODEL_URI: ("model-metadata.json", "model.json"),
    }
    for uri, (meta_name, body_name) in mapping.items():
        if uri in downloaded:
            (pending / meta_name).write_bytes(_canonical_json(downloaded[uri][0]))
            (pending / body_name).write_bytes(downloaded[uri][1])
    pending.rename(harvest)
    execution, report_meta, report, inventory = _validate_completed_local(
        out, manifest=manifest, lease=lease, execution_name=execution_name,
        intent_generation=intent_generation,
    )
    return {"report": report, "object": report_meta, "inventory": inventory,
            "already_complete": False}


def _release_intent(
    *, out: Path, manifest_receipt: Mapping[str, Any],
    lease: Mapping[str, Any], execution: Mapping[str, Any],
    report: Mapping[str, Any] | None, inventory: list[dict[str, Any]],
    terminal_status: str,
) -> dict[str, Any]:
    if terminal_status not in {"success", "failure"}:
        raise RuntimeError("B1 release terminal status differs")
    return {
        "version": "b1-corpus-tail-lease-release-intent-v1", "run_id": RUN_ID,
        "terminal_status": terminal_status,
        "manifest_object": {
            key: item for key, item in manifest_receipt["object"].items()
            if key != "create_only"
        },
        "lease_object": dict(lease["object"]),
        "execution": {
            "name": execution["metadata"]["name"],
            "sha256": _sha(
                _harvest_paths(out)["execution"]
                if terminal_status == "success" else out / "failed-execution.json"
            ),
            "completion_time": execution["status"]["completionTime"],
        },
        "result_inventory": inventory,
        "result_body_read": terminal_status == "success",
        "completion_sha256": _sha(out / "completion.txt")
        if terminal_status == "success" else None,
        "historical_pass": report["historical_pass"] if report is not None else None,
        "disposition": (
            "historical-gates-pass-shadow-licensed"
            if report is not None and report["historical_pass"]
            else "historical-gates-fail-closed"
            if report is not None else "closed-terminal-failed-no-retry"
        ),
        "possible_historical_outcome_access": True,
        "historical_outcome_lease_release_licensed": True,
        "release_action": "delete-only-exact-active-generation-after-create-only-intent",
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }


def _delete_intended_lease(
    client: storage.Client, *, lease: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> bool:
    try:
        blob, _ = _load_live_lease(client, lease, manifest=manifest)
    except NotFound:
        return False
    blob.delete(if_generation_match=int(lease["object"]["generation"]))
    return True


def _validate_release_local(
    out: Path, *, intent: Mapping[str, Any], lease: Mapping[str, Any],
) -> dict[str, Any]:
    release = _load_json(out / "lease-release.json", label="lease release")
    if not isinstance(release, dict) or set(release) != {
        "version", "run_id", "intent", "intent_object",
        "active_lease_generation", "active_lease_exact_generation_closed",
        "release_complete", "historical_retry_licensed",
        "production_change_licensed",
    }:
        raise RuntimeError("B1 local lease release fields differ")
    receipt = _intent_receipt(
        release["intent_object"], intent=intent, uri=RELEASE_INTENT_URI,
        version="b1-corpus-tail-release-intent-receipt-v1",
    )
    expected = {
        "version": "b1-corpus-tail-lease-release-v1", "run_id": RUN_ID,
        "intent": dict(intent), "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True, "release_complete": True,
        "historical_retry_licensed": False, "production_change_licensed": False,
    }
    if release != expected:
        raise RuntimeError("B1 local lease release differs")
    _validate_hash_ledger(
        out / "lease-release.sha256", base=out,
        expected={"lease-release.json"},
    )
    return release


def close_lease(
    *, out: Path = DEFAULT_OUT, client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest, manifest_receipt, lease, execution_name, intent_generation = \
        _validate_launch_local(out)
    execution, _, report, inventory = _validate_completed_local(
        out, manifest=manifest, lease=lease, execution_name=execution_name,
        intent_generation=intent_generation,
    )
    intent = _release_intent(
        out=out, manifest_receipt=manifest_receipt, lease=lease,
        execution=execution, report=report, inventory=inventory,
        terminal_status="success",
    )
    if (out / "lease-release.sha256").is_file():
        release = _validate_release_local(out, intent=intent, lease=lease)
        return {**release, "active_lease_deleted_in_this_call": False}
    raw = _canonical_json(intent)
    gcs = storage.Client(project=PROJECT) if client is None else client
    obj = _upload_create_once_or_same(gcs, RELEASE_INTENT_URI, raw)
    receipt = {
        "version": "b1-corpus-tail-release-intent-receipt-v1",
        "intent_sha256": _sha_bytes(raw), "object": obj,
    }
    _intent_receipt(
        receipt, intent=intent, uri=RELEASE_INTENT_URI,
        version="b1-corpus-tail-release-intent-receipt-v1",
    )
    deleted = _delete_intended_lease(gcs, lease=lease, manifest=manifest)
    release = {
        "version": "b1-corpus-tail-lease-release-v1", "run_id": RUN_ID,
        "intent": intent, "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True, "release_complete": True,
        "historical_retry_licensed": False, "production_change_licensed": False,
    }
    _write_exclusive_or_equal(out / "lease-release.json", _canonical_json(release))
    _write_exclusive_or_equal(
        out / "lease-release.sha256",
        f"{_sha_bytes(_canonical_json(release))}  lease-release.json\n".encode(),
    )
    _validate_release_local(out, intent=intent, lease=lease)
    return {**release, "active_lease_deleted_in_this_call": deleted}


def _validate_failed_local(
    out: Path, *, manifest_receipt: Mapping[str, Any],
    lease: Mapping[str, Any], execution_name: str, manifest: Mapping[str, Any],
    intent_generation: str,
) -> dict[str, Any]:
    execution = _load_json(out / "failed-execution.json", label="failed execution")
    if not isinstance(execution, dict) or (out / "failed-execution.json").read_bytes() != \
            _canonical_json(execution):
        raise RuntimeError("B1 retained failed execution differs")
    _validate_execution_terminal(
        execution, execution=execution_name, manifest=manifest,
        intent_generation=intent_generation, completed_status="False",
    )
    closure = _load_json(out / "failure-closure.json", label="failure closure")
    if not isinstance(closure, dict) or set(closure) != {
        "version", "run_id", "intent", "intent_object",
        "active_lease_generation", "active_lease_exact_generation_closed",
        "disposition", "possible_historical_outcome_access",
        "historical_retry_licensed", "production_change_licensed",
    }:
        raise RuntimeError("B1 retained failure closure fields differ")
    candidate = closure.get("intent")
    if not isinstance(candidate, Mapping):
        raise RuntimeError("B1 retained failure intent differs")
    intent = _release_intent(
        out=out, manifest_receipt=manifest_receipt, lease=lease,
        execution=execution, report=None,
        inventory=_inventory_metadata(candidate.get("result_inventory"), failure=True),
        terminal_status="failure",
    )
    receipt = _intent_receipt(
        closure["intent_object"], intent=intent, uri=RELEASE_INTENT_URI,
        version="b1-corpus-tail-release-intent-receipt-v1",
    )
    expected = {
        "version": "b1-corpus-tail-failure-closure-v1", "run_id": RUN_ID,
        "intent": intent, "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True,
        "disposition": "closed-terminal-failed-no-retry",
        "possible_historical_outcome_access": True,
        "historical_retry_licensed": False, "production_change_licensed": False,
    }
    if closure != expected:
        raise RuntimeError("B1 retained failure closure differs")
    _validate_hash_ledger(
        out / "failure-closure.sha256", base=out,
        expected={"failed-execution.json", "failure-closure.json"},
    )
    return closure


def close_failed_execution(
    *, out: Path = DEFAULT_OUT, client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest, manifest_receipt, lease, execution_name, intent_generation = \
        _validate_launch_local(out)
    if (out / "failure-closure.sha256").is_file():
        return _validate_failed_local(
            out, manifest_receipt=manifest_receipt, lease=lease,
            execution_name=execution_name, manifest=manifest,
            intent_generation=intent_generation,
        )
    execution = _load_json(out / "failed-execution.json", label="failed execution")
    if not isinstance(execution, dict) or (out / "failed-execution.json").read_bytes() != \
            _canonical_json(execution):
        raise RuntimeError("B1 failed execution metadata is not canonical")
    _validate_execution_terminal(
        execution, execution=execution_name, manifest=manifest,
        intent_generation=intent_generation, completed_status="False",
    )
    gcs = storage.Client(project=PROJECT) if client is None else client
    _load_live_manifest(manifest, manifest_receipt, client=gcs)
    _load_live_launch_intent(
        out, manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease, client=gcs,
    )
    inventory = _inventory_metadata(_prefix_inventory(gcs), failure=True)
    intent = _release_intent(
        out=out, manifest_receipt=manifest_receipt, lease=lease,
        execution=execution, report=None, inventory=inventory,
        terminal_status="failure",
    )
    raw = _canonical_json(intent)
    obj = _upload_create_once_or_same(gcs, RELEASE_INTENT_URI, raw)
    receipt = {
        "version": "b1-corpus-tail-release-intent-receipt-v1",
        "intent_sha256": _sha_bytes(raw), "object": obj,
    }
    _intent_receipt(
        receipt, intent=intent, uri=RELEASE_INTENT_URI,
        version="b1-corpus-tail-release-intent-receipt-v1",
    )
    _delete_intended_lease(gcs, lease=lease, manifest=manifest)
    closure = {
        "version": "b1-corpus-tail-failure-closure-v1", "run_id": RUN_ID,
        "intent": intent, "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True,
        "disposition": "closed-terminal-failed-no-retry",
        "possible_historical_outcome_access": True,
        "historical_retry_licensed": False, "production_change_licensed": False,
    }
    _write_exclusive_or_equal(out / "failure-closure.json", _canonical_json(closure))
    ledger = (
        f"{_sha(out / 'failed-execution.json')}  failed-execution.json\n"
        f"{_sha(out / 'failure-closure.json')}  failure-closure.json\n"
    ).encode("utf-8")
    _write_exclusive_or_equal(out / "failure-closure.sha256", ledger)
    return _validate_failed_local(
        out, manifest_receipt=manifest_receipt, lease=lease,
        execution_name=execution_name, manifest=manifest,
        intent_generation=intent_generation,
    )


def _verify_pushed(path: Path, *, root: Path = ROOT, remote_ref: str) -> None:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    committed = subprocess.run(
        ["git", "-C", str(root), "show", f"{remote_ref}:{relative}"],
        check=True, capture_output=True,
    ).stdout
    if committed != path.read_bytes():
        raise RuntimeError(f"B1 file is not byte-identical in {remote_ref}: {relative}")


def _verify_pushed_manifest(
    out: Path, *, root: Path = ROOT, remote_ref: str = "origin/main",
) -> None:
    _verify_pushed(out / "manifest.json", root=root, remote_ref=remote_ref)
    manifest = _validate_manifest(_load_json(out / "manifest.json", label="manifest"))
    predecessor = manifest["queue_predecessor"]
    _verify_pushed(root / predecessor["body_path"], root=root, remote_ref=remote_ref)
    _verify_pushed(root / predecessor["ledger_path"], root=root, remote_ref=remote_ref)


def _write_manifest_from_args(args: argparse.Namespace) -> None:
    manifest = _build_manifest(
        code_sha=args.code_sha, image=args.image, build_id=args.build_id,
        build_metadata=_load_json(args.build_metadata, label="build metadata"),
        job_before=_load_json(args.job_before, label="job before"),
        job_after=_load_json(args.job_after, label="job after"),
        executions_before=_load_json(args.executions_before, label="executions before"),
        executions_after=_load_json(args.executions_after, label="executions after"),
        schedulers_before=_load_json(args.schedulers_before, label="schedulers before"),
        schedulers_after=_load_json(args.schedulers_after, label="schedulers after"),
        prefix_before=_load_json(args.prefix_before, label="prefix before"),
        prefix_after=_load_json(args.prefix_after, label="prefix after"),
        lease_before=_load_json(args.lease_before, label="lease before"),
        lease_after=_load_json(args.lease_after, label="lease after"),
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_exclusive_or_equal(args.output, _canonical_json(manifest))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)
    staging = sub.add_parser("validate-smoke-staging")
    staging.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    staging.add_argument("--code-sha", required=True)
    a2a = sub.add_parser("validate-a2a-terminal")
    a2a.add_argument("--code-sha")
    pre = sub.add_parser("validate-prepare-inputs")
    pre.add_argument("--code-sha", required=True)
    pre.add_argument("--image", required=True)
    pre.add_argument("--build-id", required=True)
    pre.add_argument("--build-metadata", type=Path, required=True)
    pre.add_argument("--job-before", type=Path, required=True)
    pre.add_argument("--executions-before", type=Path, required=True)
    pre.add_argument("--schedulers-before", type=Path, required=True)
    prepare = sub.add_parser("prepare-manifest")
    prepare.add_argument("--code-sha", required=True)
    prepare.add_argument("--image", required=True)
    prepare.add_argument("--build-id", required=True)
    for name in (
        "build-metadata", "job-before", "job-after", "executions-before",
        "executions-after", "schedulers-before", "schedulers-after",
        "prefix-before", "prefix-after", "lease-before", "lease-after",
    ):
        prepare.add_argument(f"--{name}", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    publish = sub.add_parser("publish-manifest")
    publish.add_argument("--manifest", type=Path, required=True)
    publish.add_argument("--receipt", type=Path, required=True)
    prepared = sub.add_parser("validate-prepared")
    prepared.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    prepared.add_argument("--code-sha", required=True)
    prepared.add_argument("--image", required=True)
    prepared.add_argument("--build-id", required=True)
    sub.add_parser("check-empty-prefix")
    sub.add_parser("check-lease-absent")
    prefix = sub.add_parser("capture-empty-prefix")
    prefix.add_argument("--output", type=Path, required=True)
    lease_absence = sub.add_parser("capture-lease-absence")
    lease_absence.add_argument("--output", type=Path, required=True)
    pushed = sub.add_parser("verify-pushed-manifest")
    pushed.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    pushed.add_argument("--remote-ref", default="origin/main")
    ready = sub.add_parser("validate-launch-ready")
    ready.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    ready.add_argument("--job-current", type=Path, required=True)
    ready.add_argument("--executions", type=Path, required=True)
    ready.add_argument("--schedulers", type=Path, required=True)
    ready.add_argument("--require-intent", action="store_true")
    recover = sub.add_parser("recover-lease")
    recover.add_argument("--manifest", type=Path, required=True)
    recover.add_argument("--receipt", type=Path, required=True)
    intent = sub.add_parser("publish-launch-intent")
    intent.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    generation = sub.add_parser("intent-generation")
    generation.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    execute = sub.add_parser("execute-frozen")
    execute.add_argument("--launch-intent-generation", required=True)
    harvest = sub.add_parser("finish")
    harvest.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    close = sub.add_parser("close-lease")
    close.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    failed = sub.add_parser("close-failed-execution")
    failed.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "canonicalize-external-json":
        _canonicalize_external_json(args.raw, args.output)
    elif args.command == "validate-smoke-staging":
        _validate_smoke_staging(args.output_dir, code_sha=args.code_sha)
        print("B1_CORPUS_TAIL_SMOKE_STAGING_VALID")
    elif args.command == "validate-a2a-terminal":
        print("B1_CORPUS_TAIL_A2A_TERMINAL " + json.dumps(
            _a2a_terminal(code_sha=args.code_sha), sort_keys=True,
        ))
    elif args.command == "validate-prepare-inputs":
        _validate_prepare_inputs(
            code_sha=args.code_sha, image=args.image, build_id=args.build_id,
            build_metadata=_load_json(args.build_metadata, label="build metadata"),
            job_before=_load_json(args.job_before, label="job before"),
            executions_before=_load_json(args.executions_before, label="executions before"),
            schedulers_before=_load_json(args.schedulers_before, label="schedulers before"),
        )
        print("B1_CORPUS_TAIL_PREPARE_INPUTS_VALID")
    elif args.command == "prepare-manifest":
        _write_manifest_from_args(args)
    elif args.command == "publish-manifest":
        print(json.dumps(_publish_manifest(args.manifest, args.receipt), sort_keys=True))
    elif args.command == "validate-prepared":
        manifest, _ = _validate_prepared_local(args.output_dir)
        if manifest["code"]["commit_sha"] != args.code_sha or \
                manifest["image"]["uri"] != args.image or \
                manifest["build"]["id"] != args.build_id:
            raise RuntimeError("B1 watcher/prepared identity differs")
        print("B1_CORPUS_TAIL_PREPARED_VALID")
    elif args.command == "check-empty-prefix":
        _require_empty_prefix(storage.Client(project=PROJECT))
        print("B1_CORPUS_TAIL_RESULT_PREFIX_AND_ATTEMPT_EMPTY")
    elif args.command == "check-lease-absent":
        _require_lease_absent(storage.Client(project=PROJECT))
        print("B1_CORPUS_TAIL_OUTCOME_LEASE_ABSENT")
    elif args.command == "capture-empty-prefix":
        _capture_absence(kind="result-prefix-and-attempt", output=args.output)
        print("B1_CORPUS_TAIL_RESULT_PREFIX_AND_ATTEMPT_EMPTY")
    elif args.command == "capture-lease-absence":
        _capture_absence(kind="historical-outcome-lease", output=args.output)
        print("B1_CORPUS_TAIL_OUTCOME_LEASE_ABSENT")
    elif args.command == "verify-pushed-manifest":
        _verify_pushed_manifest(args.output_dir, remote_ref=args.remote_ref)
        print("B1_CORPUS_TAIL_MANIFEST_AND_A2A_TERMINAL_PUSHED")
    elif args.command == "validate-launch-ready":
        _validate_launch_ready(
            out=args.output_dir,
            job_current=_load_json(args.job_current, label="current job"),
            executions=_load_json(args.executions, label="current executions"),
            schedulers=_load_json(args.schedulers, label="current schedulers"),
            require_intent=args.require_intent,
        )
        print("B1_CORPUS_TAIL_LAUNCH_READY")
    elif args.command == "recover-lease":
        value = _recover_live_lease(
            manifest_path=args.manifest, receipt_path=args.receipt,
        )
        print("B1_CORPUS_TAIL_LEASE_RECOVERED " + json.dumps(
            value["object"], sort_keys=True,
        ))
    elif args.command == "publish-launch-intent":
        value = _publish_launch_intent(args.output_dir)
        print("B1_CORPUS_TAIL_LAUNCH_INTENT " + json.dumps(
            value["object"], sort_keys=True,
        ))
    elif args.command == "intent-generation":
        receipt = _load_json(
            args.output_dir / "launch-intent-object.json", label="intent receipt",
        )
        generation = str(receipt.get("object", {}).get("generation", "")) \
            if isinstance(receipt, dict) else ""
        if re.fullmatch(r"[1-9][0-9]*", generation) is None:
            raise RuntimeError("B1 launch-intent generation differs")
        print(generation)
    elif args.command == "execute-frozen":
        value = execute_frozen(intent_generation=args.launch_intent_generation)
        print("B1_CORPUS_TAIL_EXECUTION_PUBLISHED " + json.dumps(value, sort_keys=True))
    elif args.command == "finish":
        value = finish(out=args.output_dir)
        print("B1_CORPUS_TAIL_HARVESTED historical_pass=" + str(
            value["report"]["historical_pass"]
        ).lower())
    elif args.command == "close-lease":
        value = close_lease(out=args.output_dir)
        print("B1_CORPUS_TAIL_LEASE_CLOSED " + json.dumps({
            "active_lease_deleted_in_this_call": value[
                "active_lease_deleted_in_this_call"
            ],
            "historical_pass": value["intent"]["historical_pass"],
        }, sort_keys=True))
    else:
        value = close_failed_execution(out=args.output_dir)
        print("B1_CORPUS_TAIL_TERMINAL_FAILURE_CLOSED " + value["disposition"])


if __name__ == "__main__":
    main()
