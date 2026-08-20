#!/usr/bin/env python3
"""Fail-closed transport for the licensed B1 2026 prospective shadow.

This file adds no model, selector, threshold, feature, or adoption science.
Those frozen laws remain in ``run_b1_corpus_tail_model.py`` and
``nfl_dfs.research.b1_corpus_tail``.  This wrapper only:

* proves that the historical pass, portable model, and lease closure are
  byte-identical in a pushed Git commit;
* prepares a Cloud Run deployment whose persisted default is
  ``CORPUS_TAIL_SHADOW_ENABLED=0``;
* binds one create-only pre-lock freeze intent and receipt for each of exact
  2026 Weeks 1--6;
* binds one create-only post-settlement score artifact for each frozen week;
* feeds the six generation-pinned receipt/score pairs to the already-frozen
  adoption command and publishes its result create-only.

The runtime commands intentionally have no retry path.  An existing attempt
object means that phase is ambiguous or already consumed and therefore fails
closed.  Production is never mutated by this module.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable, Final, Mapping, Sequence

import pandas as pd
from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import bigquery, storage


ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import finish_b1_corpus_tail_model as historical  # noqa: E402
import run_b1_corpus_tail_model as runner  # noqa: E402
from nfl_dfs.research import b1_corpus_tail as science  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
SEASON: Final = 2026
WEEKS: Final = tuple(range(1, 7))
RUN_ID: Final = historical.RUN_ID
TRANSPORT_ID: Final = "2026-b1-corpus-tail-shadow-v1"
BUCKET: Final = f"{PROJECT}-raw"
PREFIX: Final = f"research/b1-corpus-tail-shadow/{TRANSPORT_ID}"
DEPLOYMENT_URI: Final = f"gs://{BUCKET}/{PREFIX}/deployment-manifest.json"
HISTORICAL_OUT: Final = ROOT / "reports/b1-corpus-tail-runs" / RUN_ID
DEFAULT_OUT: Final = ROOT / "reports/b1-corpus-tail-shadow-runs" / TRANSPORT_ID
SCRIPT_PATH: Final = "scripts/run_b1_corpus_tail_shadow_transport.py"
IMAGE_REPOSITORY: Final = historical.IMAGE_REPOSITORY
SERVICE_ACCOUNT: Final = historical.SERVICE_ACCOUNT
CPU: Final = "4"
MEMORY: Final = "16Gi"
TIMEOUT_SECONDS: Final = "14400"

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_IMAGE = re.compile(
    rf"{re.escape(IMAGE_REPOSITORY)}@sha256:[0-9a-f]{{64}}"
)


class ShadowTransportError(RuntimeError):
    """The prospective shadow transport failed a frozen boundary."""


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ShadowTransportError(f"{label} contains non-finite JSON: {value}")

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ShadowTransportError(f"{label} repeats JSON key {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=strict_object,
        )
    except ShadowTransportError:
        raise
    except Exception as exc:
        raise ShadowTransportError(f"{label} is not strict JSON") from exc


def _load_canonical(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ShadowTransportError(f"{label} is absent: {path}")
    raw = path.read_bytes()
    value = _strict_json_bytes(raw, label=label)
    if raw != _canonical_json(value):
        raise ShadowTransportError(f"{label} is not canonical JSON")
    return value


def _write_create_once(path: Path, value: Any) -> str:
    raw = _canonical_json(value)
    digest = sha256(raw).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    created_path = False
    created_sidecar = False
    try:
        with path.open("xb") as handle:
            handle.write(raw)
        created_path = True
        with sidecar.open("x", encoding="utf-8") as handle:
            handle.write(f"{digest}  {path.name}\n")
        created_sidecar = True
    except Exception:
        if created_sidecar:
            sidecar.unlink(missing_ok=True)
        if created_path:
            path.unlink(missing_ok=True)
        raise
    return digest


def _utc(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ShadowTransportError(f"{label} is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ShadowTransportError(f"{label} is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ShadowTransportError(f"{label} is not timezone-aware")
    return parsed


def _exact_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise ShadowTransportError(f"{label} must be an exact JSON integer")
    return value


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or "/" not in uri[5:]:
        raise ShadowTransportError(f"invalid GCS URI: {uri}")
    bucket, name = uri[5:].split("/", 1)
    if not bucket or not name:
        raise ShadowTransportError(f"invalid GCS URI: {uri}")
    return bucket, name


def _object_identity(
    value: object,
    *,
    uri: str | None = None,
    create_only: bool | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ShadowTransportError("object identity is absent")
    expected = {"uri", "generation", "metageneration", "bytes", "sha256"}
    if create_only is not None:
        expected.add("create_only")
    if set(value) != expected:
        raise ShadowTransportError("object identity schema differs")
    observed_uri = value.get("uri")
    if not isinstance(observed_uri, str) or (uri is not None and observed_uri != uri):
        raise ShadowTransportError("object identity URI differs")
    if _GENERATION.fullmatch(str(value.get("generation", ""))) is None:
        raise ShadowTransportError("object generation differs")
    if str(value.get("metageneration", "")) != "1":
        raise ShadowTransportError("object metageneration differs")
    if type(value.get("bytes")) is not int or int(value["bytes"]) <= 0:
        raise ShadowTransportError("object byte count differs")
    if _HEX64.fullmatch(str(value.get("sha256", ""))) is None:
        raise ShadowTransportError("object SHA-256 differs")
    if create_only is not None and value.get("create_only") is not create_only:
        raise ShadowTransportError("object create-only flag differs")
    return dict(value)


def _blob_identity(blob: Any, *, uri: str, raw: bytes) -> dict[str, Any]:
    identity = {
        "uri": uri,
        "generation": str(blob.generation or ""),
        "metageneration": str(blob.metageneration or ""),
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }
    return _object_identity(identity, uri=uri)


def _upload_create_once(
    client: storage.Client,
    *,
    uri: str,
    raw: bytes,
) -> dict[str, Any]:
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name)
    try:
        blob.upload_from_string(
            raw,
            content_type="application/json",
            if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise ShadowTransportError(
            f"create-only object already exists; phase may not retry: {uri}"
        ) from exc
    blob.reload()
    return _blob_identity(blob, uri=uri, raw=raw)


def _metadata_only(client: storage.Client, *, uri: str) -> dict[str, Any]:
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name)
    try:
        blob.reload()
    except NotFound as exc:
        raise ShadowTransportError(f"required object is absent: {uri}") from exc
    value = {
        "uri": uri,
        "generation": str(blob.generation or ""),
        "metageneration": str(blob.metageneration or ""),
        "bytes": int(blob.size or 0),
        # Metadata-only phase deliberately does not pretend it observed bytes.
        "sha256": "0" * 64,
    }
    checked = _object_identity(value, uri=uri)
    checked.pop("sha256")
    return checked


def _download_generation(
    client: storage.Client,
    identity: Mapping[str, Any],
    *,
    label: str,
) -> tuple[dict[str, Any], bytes]:
    if isinstance(identity, Mapping) and "create_only" in identity:
        checked_with_flag = _object_identity(identity, create_only=True)
        checked = {
            key: item for key, item in checked_with_flag.items()
            if key != "create_only"
        }
    else:
        checked = _object_identity(identity)
    uri = str(checked["uri"])
    bucket_name, name = _gcs_parts(uri)
    generation = int(checked["generation"])
    blob = client.bucket(bucket_name).blob(name, generation=generation)
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=generation)
    observed = _blob_identity(blob, uri=uri, raw=raw)
    if observed != checked:
        raise ShadowTransportError(f"{label} content identity changed")
    return observed, raw


def _download_current(
    client: storage.Client,
    *,
    uri: str,
    label: str,
) -> tuple[dict[str, Any], bytes]:
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name)
    try:
        blob.reload()
    except NotFound as exc:
        raise ShadowTransportError(f"{label} is absent: {uri}") from exc
    generation = int(blob.generation or 0)
    raw = blob.download_as_bytes(if_generation_match=generation)
    return _blob_identity(blob, uri=uri, raw=raw), raw


def _git(
    args: Sequence[str],
    *,
    root: Path,
    capture: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=capture,
    )


def _ledger_members(path: Path, *, base: Path) -> set[Path]:
    if path.is_symlink() or not path.is_file():
        raise ShadowTransportError(f"checksum ledger is absent: {path}")
    members: set[Path] = {path}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ShadowTransportError(f"checksum ledger differs: {path.name}")
        member = base / match.group(2)
        try:
            member.resolve().relative_to(base.resolve())
        except ValueError as exc:
            raise ShadowTransportError("checksum member escapes run directory") from exc
        if member.is_symlink() or not member.is_file():
            raise ShadowTransportError(f"checksum member is absent: {member}")
        if sha256(member.read_bytes()).hexdigest() != match.group(1):
            raise ShadowTransportError(f"checksum member differs: {member}")
        members.add(member)
    return members


def _verify_pushed_bundle(
    *,
    root: Path,
    commit: str,
    remote_ref: str,
    paths: set[Path],
    git: Callable[..., subprocess.CompletedProcess[bytes]] = _git,
) -> None:
    if _HEX40.fullmatch(commit) is None:
        raise ShadowTransportError("evidence commit must be full lowercase SHA")
    try:
        resolved = git(
            ["rev-parse", "--verify", f"{commit}^{{commit}}"], root=root
        ).stdout.decode().strip()
        if resolved != commit:
            raise ShadowTransportError("evidence commit does not resolve exactly")
        git(["merge-base", "--is-ancestor", commit, remote_ref], root=root)
    except subprocess.CalledProcessError as exc:
        raise ShadowTransportError(
            f"evidence commit is not present in pushed ref {remote_ref}"
        ) from exc
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise ShadowTransportError(f"committed evidence file is absent: {path}")
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError as exc:
            raise ShadowTransportError("evidence file is outside repository") from exc
        try:
            committed = git(["show", f"{commit}:{relative}"], root=root).stdout
        except subprocess.CalledProcessError as exc:
            raise ShadowTransportError(
                f"evidence file is not tracked at {commit}: {relative}"
            ) from exc
        if committed != path.read_bytes():
            raise ShadowTransportError(
                f"evidence file differs from {commit}: {relative}"
            )


def _require_pushed_commit(
    *, root: Path, commit: str, remote_ref: str,
) -> None:
    if _HEX40.fullmatch(commit) is None:
        raise ShadowTransportError("evidence commit must be full lowercase SHA")
    try:
        resolved = _git(
            ["rev-parse", "--verify", f"{commit}^{{commit}}"], root=root
        ).stdout.decode().strip()
        if resolved != commit:
            raise ShadowTransportError("evidence commit does not resolve exactly")
        _git(["merge-base", "--is-ancestor", commit, remote_ref], root=root)
    except subprocess.CalledProcessError as exc:
        raise ShadowTransportError(
            f"evidence commit is not present in pushed ref {remote_ref}"
        ) from exc


def _committed_historical_checkout(
    *, root: Path, commit: str, out: Path, destination: Path,
) -> Path:
    """Materialize only the historical proof tree from the evidence commit."""
    try:
        run_relative = out.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ShadowTransportError("historical run path is outside repository") from exc
    try:
        manifest_raw = _git(
            ["show", f"{commit}:{run_relative}/manifest.json"], root=root
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise ShadowTransportError("committed historical manifest is absent") from exc
    manifest = _strict_json_bytes(manifest_raw, label="committed historical manifest")
    if not isinstance(manifest, dict):
        raise ShadowTransportError("committed historical manifest differs")
    implementation = manifest.get("implementation")
    predecessor = manifest.get("queue_predecessor")
    if not isinstance(implementation, dict) or not isinstance(predecessor, dict):
        raise ShadowTransportError("committed historical manifest boundary differs")
    paths = {run_relative}
    for row in implementation.values():
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ShadowTransportError("committed implementation receipt differs")
        paths.add(row["path"])
    for key in ("body_path", "ledger_path"):
        if not isinstance(predecessor.get(key), str):
            raise ShadowTransportError("committed predecessor receipt differs")
        paths.add(predecessor[key])
    try:
        archive = _git(
            ["archive", "--format=tar", commit, "--", *sorted(paths)], root=root
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise ShadowTransportError("could not materialize committed historical proof") from exc
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            if not member.isfile():
                continue
            target = destination / member.name
            try:
                target.resolve().relative_to(destination.resolve())
            except ValueError as exc:
                raise ShadowTransportError("committed archive path escapes checkout") from exc
            source = bundle.extractfile(member)
            if source is None:
                raise ShadowTransportError("committed archive member is unreadable")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
    return destination / run_relative


def _historical_evidence(
    *,
    out: Path,
    root: Path,
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], set[Path]
]:
    try:
        manifest, manifest_receipt, lease, execution_name, intent_generation = (
            historical._validate_launch_local(out, root=root)
        )
        execution, report_meta, report, inventory = historical._validate_completed_local(
            out,
            manifest=manifest,
            lease=lease,
            execution_name=execution_name,
            intent_generation=intent_generation,
        )
        intent = historical._release_intent(
            out=out,
            manifest_receipt=manifest_receipt,
            lease=lease,
            execution=execution,
            report=report,
            inventory=inventory,
            terminal_status="success",
        )
        release = historical._validate_release_local(
            out, intent=intent, lease=lease
        )
    except Exception as exc:
        raise ShadowTransportError("historical B1 evidence does not strictly validate") from exc
    if report.get("historical_pass") is not True or report.get("licenses") != {
        "write_2026_shadow_artifact": True,
        "run_2026_shadow": True,
        "production": False,
        "historical_retune": False,
    }:
        raise ShadowTransportError("historical B1 result does not license the shadow")
    if intent.get("disposition") != "historical-gates-pass-shadow-licensed":
        raise ShadowTransportError("historical B1 closure disposition differs")
    if (
        release.get("active_lease_exact_generation_closed") is not True
        or release.get("release_complete") is not True
        or release.get("historical_retry_licensed") is not False
        or release.get("production_change_licensed") is not False
    ):
        raise ShadowTransportError("historical B1 lease is not safely closed")
    model_path = out / "harvest/model.json"
    model_meta_path = out / "harvest/model-metadata.json"
    model = _load_canonical(model_path, label="historical model")
    model_meta = _load_canonical(model_meta_path, label="historical model metadata")
    if not isinstance(model, dict) or not isinstance(model_meta, dict):
        raise ShadowTransportError("historical model evidence differs")
    try:
        historical._validate_model(model, report=report)
    except Exception as exc:
        raise ShadowTransportError("historical model does not strictly validate") from exc
    model_object = _object_identity(model_meta, uri=historical.MODEL_URI)
    if (
        model_object["sha256"] != report["model_file_sha256"]
        or model_object["bytes"] != len(model_path.read_bytes())
        or model_object["sha256"] != sha256(model_path.read_bytes()).hexdigest()
    ):
        raise ShadowTransportError("historical model object differs from retained bytes")
    report_object = _object_identity(report_meta, uri=historical.REPORT_URI)

    committed: set[Path] = set()
    for ledger_name in (
        "prepared.sha256",
        "launch.sha256",
        "finish.sha256",
        "lease-release.sha256",
    ):
        committed |= _ledger_members(out / ledger_name, base=out)
    committed |= {
        out / "manifest.json",
        out / "manifest-object.json",
        out / "completion.txt",
        out / "lease-release.json",
        model_path,
        model_meta_path,
    }
    for row in manifest["implementation"].values():
        committed.add(root / row["path"])
    predecessor = manifest["queue_predecessor"]
    committed |= {
        root / predecessor["body_path"],
        root / predecessor["ledger_path"],
    }
    return manifest, report, release, {
        "model": model,
        "model_object": model_object,
        "report_object": report_object,
    }, committed


def validate_historical_license(
    *,
    out: Path = HISTORICAL_OUT,
    root: Path = ROOT,
    evidence_commit: str,
    remote_ref: str = "origin/main",
) -> dict[str, Any]:
    """Return the only historical evidence that may license this shadow."""
    _require_pushed_commit(root=root, commit=evidence_commit, remote_ref=remote_ref)
    with tempfile.TemporaryDirectory(prefix="b1-tail-historical-git-") as directory:
        checkout = Path(directory) / "checkout"
        committed_out = _committed_historical_checkout(
            root=root,
            commit=evidence_commit,
            out=out,
            destination=checkout,
        )
        manifest, report, release, retained, _ = _historical_evidence(
            out=committed_out, root=checkout
        )
    model = retained["model"]
    result = {
        "version": "b1-corpus-tail-shadow-historical-license-v1",
        "transport_id": TRANSPORT_ID,
        "historical_run_id": RUN_ID,
        "protocol_sha256": historical.PROTOCOL_SHA256,
        "evidence_commit": evidence_commit,
        "remote_ref": remote_ref,
        "historical_code_commit": manifest["code"]["commit_sha"],
        "historical_image": manifest["image"]["uri"],
        "historical_report_object": retained["report_object"],
        "historical_model_object": retained["model_object"],
        "model_artifact_sha256": model["artifact_sha256"],
        "historical_gate_passed": True,
        "shadow_licensed": True,
        "historical_retry_licensed": False,
        "historical_lease_generation_closed": release[
            "active_lease_generation"
        ],
        "historical_lease_exact_generation_closed": True,
        "prospective_season": SEASON,
        "prospective_weeks": list(WEEKS),
        "shadow_enabled_default": False,
        "production_licensed": False,
    }
    # Cross-check the report rather than trusting a single copied Boolean.
    if report["model_artifact_sha256"] != result["model_artifact_sha256"]:
        raise ShadowTransportError("historical report/model artifact binding differs")
    return result


def _validate_historical_license_document(value: object) -> dict[str, Any]:
    keys = {
        "version", "transport_id", "historical_run_id", "protocol_sha256",
        "evidence_commit", "remote_ref", "historical_code_commit",
        "historical_image", "historical_report_object",
        "historical_model_object", "model_artifact_sha256",
        "historical_gate_passed", "shadow_licensed",
        "historical_retry_licensed", "historical_lease_generation_closed",
        "historical_lease_exact_generation_closed", "prospective_season",
        "prospective_weeks", "shadow_enabled_default", "production_licensed",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ShadowTransportError("historical shadow license schema differs")
    if (
        value["version"] != "b1-corpus-tail-shadow-historical-license-v1"
        or value["transport_id"] != TRANSPORT_ID
        or value["historical_run_id"] != RUN_ID
        or value["protocol_sha256"] != historical.PROTOCOL_SHA256
        or _HEX40.fullmatch(str(value["evidence_commit"])) is None
        or _HEX40.fullmatch(str(value["historical_code_commit"])) is None
        or _IMAGE.fullmatch(str(value["historical_image"])) is None
        or _HEX64.fullmatch(str(value["model_artifact_sha256"])) is None
        or value["historical_gate_passed"] is not True
        or value["shadow_licensed"] is not True
        or value["historical_retry_licensed"] is not False
        or _GENERATION.fullmatch(
            str(value["historical_lease_generation_closed"])
        ) is None
        or value["historical_lease_exact_generation_closed"] is not True
        or value["prospective_season"] != SEASON
        or value["prospective_weeks"] != list(WEEKS)
        or value["shadow_enabled_default"] is not False
        or value["production_licensed"] is not False
    ):
        raise ShadowTransportError("historical shadow license boundary differs")
    _object_identity(
        value["historical_report_object"], uri=historical.REPORT_URI
    )
    _object_identity(value["historical_model_object"], uri=historical.MODEL_URI)
    return value


def _validate_build(
    value: object,
    *,
    build_id: str,
    code_sha: str,
    image: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("id") != build_id:
        raise ShadowTransportError("shadow build identity differs")
    if value.get("status") != "SUCCESS":
        raise ShadowTransportError("shadow build is not successful")
    source = {"url": historical.GIT_SOURCE_URL, "revision": code_sha}
    if (
        value.get("source", {}).get("gitSource") != source
        or value.get("sourceProvenance", {}).get("resolvedGitSource") != source
    ):
        raise ShadowTransportError("shadow build is not exact direct-Git source")
    steps = value.get("steps")
    if not isinstance(steps, list) or len(steps) != 3:
        raise ShadowTransportError("shadow build steps differ")
    ids = [str(row.get("id", "")) for row in steps if isinstance(row, dict)]
    required = ["full-test-suite", "build-image", "smoke-atlas-mvp-runner"]
    if ids != required:
        raise ShadowTransportError("shadow build test/image gate differs")
    if any(row.get("status") != "SUCCESS" for row in steps):
        raise ShadowTransportError("shadow build contains a non-successful step")
    tag = f"{IMAGE_REPOSITORY}:b1-shadow-{code_sha[:7]}"
    substitutions = value.get("substitutions")
    if not isinstance(substitutions, Mapping) or substitutions.get("_IMAGE") != tag:
        raise ShadowTransportError("shadow build substitutions differ")
    for optional_commit_key in ("COMMIT_SHA", "_CODE_SHA"):
        if optional_commit_key in substitutions and \
                substitutions[optional_commit_key] != code_sha:
            raise ShadowTransportError("shadow build substitutions differ")
    images = value.get("results", {}).get("images", [])
    digest = image.rsplit("@", 1)[1]
    if not isinstance(images, list) or not any(
        isinstance(row, dict)
        and row.get("name") == tag
        and row.get("digest") == digest
        for row in images
    ):
        raise ShadowTransportError("shadow build does not bind immutable image")
    if (
        value.get("timeout") != "10800s"
        or value.get("serviceAccount") != historical.BUILD_SERVICE_ACCOUNT
        or value.get("logsBucket") != historical.BUILD_LOGS_BUCKET
    ):
        raise ShadowTransportError("shadow build compute contract differs")
    return value


def _job_parts(value: object) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise ShadowTransportError("Cloud Run job metadata differs")
    metadata = value.get("metadata")
    spec = value.get("spec")
    if not isinstance(metadata, dict) or not isinstance(spec, dict):
        raise ShadowTransportError("Cloud Run job schema differs")
    outer = spec.get("template", {}).get("spec")
    task = outer.get("template", {}).get("spec") if isinstance(outer, dict) else None
    if not isinstance(outer, dict) or not isinstance(task, dict):
        raise ShadowTransportError("Cloud Run job task schema differs")
    return metadata, outer, task


def _job_identity(value: object, *, name: str, uid: str) -> tuple[str, str]:
    metadata, _, _ = _job_parts(value)
    if metadata.get("name") != name or metadata.get("uid") != uid:
        raise ShadowTransportError("reused shadow job identity differs")
    generation = str(metadata.get("generation", ""))
    if _GENERATION.fullmatch(generation) is None:
        raise ShadowTransportError("reused shadow job generation differs")
    return uid, generation


def _require_idle(executions: object) -> None:
    try:
        historical._validate_job_idle(executions)
    except Exception as exc:
        raise ShadowTransportError("reused shadow job is not idle") from exc


def _require_unscheduled(schedulers: object, *, job_name: str) -> None:
    if not isinstance(schedulers, list):
        raise ShadowTransportError("scheduler inventory differs")
    needle = f"/jobs/{job_name}:run"
    for row in schedulers:
        if needle in json.dumps(row, sort_keys=True, separators=(",", ":")):
            raise ShadowTransportError("reused shadow job has a scheduler target")


def _validate_inert_job(
    value: object,
    *,
    name: str,
    uid: str,
    code_sha: str,
    image: str,
) -> str:
    _, generation = _job_identity(value, name=name, uid=uid)
    _, outer, task = _job_parts(value)
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        raise ShadowTransportError("shadow job container count differs")
    container = containers[0]
    if not isinstance(container, dict):
        raise ShadowTransportError("shadow job container differs")
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise ShadowTransportError("shadow job environment differs")
    env = {str(row["name"]): str(row["value"]) for row in env_rows}
    if len(env) != len(env_rows):
        raise ShadowTransportError("shadow job environment repeats a name")
    expected_env = {
        "ANALYSIS_IMAGE": image,
        "CODE_SHA": code_sha,
        "CORPUS_TAIL_SHADOW_ENABLED": "0",
    }
    resources = container.get("resources", {}).get("limits", {})
    if (
        outer.get("taskCount") != 1
        or outer.get("parallelism") != 1
        or container.get("image") != image
        or container.get("command") != ["python"]
        or container.get("args") != [SCRIPT_PATH, "--help"]
        or env != expected_env
        or resources != {"cpu": CPU, "memory": MEMORY}
        or task.get("maxRetries") != 0
        or str(task.get("timeoutSeconds")) != TIMEOUT_SECONDS
        or task.get("serviceAccountName") != SERVICE_ACCOUNT
        or task.get("volumes", []) != []
        or outer.get("volumes", []) != []
    ):
        raise ShadowTransportError("shadow job is not exact inert/default-off spec")
    if any(key in container for key in ("volumeMounts", "workingDir", "startupProbe")):
        raise ShadowTransportError("shadow job retains inherited executable state")
    return generation


def validate_reuse_candidate(
    *,
    job_name: str,
    job_uid: str,
    job: object,
    executions: object,
    schedulers: object,
) -> dict[str, str]:
    """Prove an existing job is idle and unscheduled before any update."""
    _, generation = _job_identity(job, name=job_name, uid=job_uid)
    _require_idle(executions)
    _require_unscheduled(schedulers, job_name=job_name)
    return {"job": job_name, "uid": job_uid, "generation": generation}


def build_deployment_manifest(
    *,
    license_document: Mapping[str, Any],
    license_sha256: str,
    code_sha: str,
    image: str,
    build_id: str,
    build_metadata: object,
    job_name: str,
    job_uid: str,
    job_before: object,
    job_after: object,
    executions_before: object,
    executions_after: object,
    schedulers_before: object,
    schedulers_after: object,
) -> dict[str, Any]:
    license_document = _validate_historical_license_document(dict(license_document))
    if sha256(_canonical_json(license_document)).hexdigest() != license_sha256:
        raise ShadowTransportError("historical license SHA-256 differs")
    if _HEX40.fullmatch(code_sha) is None or _IMAGE.fullmatch(image) is None:
        raise ShadowTransportError("shadow deployment code/image differs")
    if re.fullmatch(r"[0-9A-Za-z-]{8,80}", build_id) is None:
        raise ShadowTransportError("shadow deployment build ID differs")
    _validate_build(
        build_metadata, build_id=build_id, code_sha=code_sha, image=image
    )
    _, prior_generation = _job_identity(job_before, name=job_name, uid=job_uid)
    _require_idle(executions_before)
    _require_unscheduled(schedulers_before, job_name=job_name)
    generation = _validate_inert_job(
        job_after, name=job_name, uid=job_uid, code_sha=code_sha, image=image
    )
    _require_idle(executions_after)
    _require_unscheduled(schedulers_after, job_name=job_name)
    if int(generation) <= int(prior_generation):
        raise ShadowTransportError("reused shadow job was not updated in place")
    return {
        "version": "b1-corpus-tail-shadow-deployment-v1",
        "status": "deployed-default-off-awaiting-explicit-week-intent",
        "transport_id": TRANSPORT_ID,
        "season": SEASON,
        "weeks": list(WEEKS),
        "code": {
            "commit_sha": code_sha,
            "image": image,
            "build_id": build_id,
        },
        "job": {
            "name": job_name,
            "uid": job_uid,
            "prior_generation": prior_generation,
            "generation": generation,
            "update_mode": "reuse-only-update-existing",
            "scheduler_target_absent": True,
            "task_count": 1,
            "max_retries": 0,
        },
        "historical_license": {
            "sha256": license_sha256,
            "evidence_commit": license_document["evidence_commit"],
            "historical_report_object": license_document[
                "historical_report_object"
            ],
            "historical_model_object": license_document[
                "historical_model_object"
            ],
            "model_artifact_sha256": license_document[
                "model_artifact_sha256"
            ],
            "historical_gate_passed": True,
            "historical_lease_exact_generation_closed": True,
        },
        "default_environment": {
            "ANALYSIS_IMAGE": image,
            "CODE_SHA": code_sha,
            "CORPUS_TAIL_SHADOW_ENABLED": "0",
        },
        "weekly_execution_override": {
            "CORPUS_TAIL_SHADOW_ENABLED": "1",
            "required": True,
        },
        "deployment_uri": DEPLOYMENT_URI,
        "receipt_prefix": f"gs://{BUCKET}/{PREFIX}/weeks",
        "create_only": True,
        "uses_realized_outcomes_at_deployment": False,
        "production_licensed": False,
        "automatic_production_mutation": False,
    }


def _validate_deployment(value: object) -> dict[str, Any]:
    keys = {
        "version", "status", "transport_id", "season", "weeks", "code",
        "job", "historical_license", "default_environment",
        "weekly_execution_override", "deployment_uri", "receipt_prefix",
        "create_only", "uses_realized_outcomes_at_deployment",
        "production_licensed", "automatic_production_mutation",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ShadowTransportError("shadow deployment schema differs")
    if (
        value["version"] != "b1-corpus-tail-shadow-deployment-v1"
        or value["status"] != "deployed-default-off-awaiting-explicit-week-intent"
        or value["transport_id"] != TRANSPORT_ID
        or value["season"] != SEASON
        or value["weeks"] != list(WEEKS)
        or value["deployment_uri"] != DEPLOYMENT_URI
        or value["receipt_prefix"] != f"gs://{BUCKET}/{PREFIX}/weeks"
        or value["create_only"] is not True
        or value["uses_realized_outcomes_at_deployment"] is not False
        or value["production_licensed"] is not False
        or value["automatic_production_mutation"] is not False
    ):
        raise ShadowTransportError("shadow deployment boundary differs")
    code = value["code"]
    job = value["job"]
    hist = value["historical_license"]
    if (
        not isinstance(code, dict)
        or set(code) != {"commit_sha", "image", "build_id"}
        or _HEX40.fullmatch(str(code["commit_sha"])) is None
        or _IMAGE.fullmatch(str(code["image"])) is None
        or not isinstance(job, dict)
        or set(job) != {
            "name", "uid", "prior_generation", "generation", "update_mode",
            "scheduler_target_absent", "task_count", "max_retries",
        }
        or _GENERATION.fullmatch(str(job["prior_generation"])) is None
        or _GENERATION.fullmatch(str(job["generation"])) is None
        or int(job["generation"]) <= int(job["prior_generation"])
        or job["update_mode"] != "reuse-only-update-existing"
        or job["scheduler_target_absent"] is not True
        or job["task_count"] != 1
        or job["max_retries"] != 0
        or not isinstance(hist, dict)
        or set(hist) != {
            "sha256", "evidence_commit", "historical_report_object",
            "historical_model_object", "model_artifact_sha256",
            "historical_gate_passed", "historical_lease_exact_generation_closed",
        }
        or hist["historical_gate_passed"] is not True
        or hist["historical_lease_exact_generation_closed"] is not True
    ):
        raise ShadowTransportError("shadow deployment code/job/license differs")
    _object_identity(hist["historical_report_object"], uri=historical.REPORT_URI)
    _object_identity(hist["historical_model_object"], uri=historical.MODEL_URI)
    if value["default_environment"] != {
        "ANALYSIS_IMAGE": code["image"],
        "CODE_SHA": code["commit_sha"],
        "CORPUS_TAIL_SHADOW_ENABLED": "0",
    } or value["weekly_execution_override"] != {
        "CORPUS_TAIL_SHADOW_ENABLED": "1",
        "required": True,
    }:
        raise ShadowTransportError("shadow deployment is not default-off")
    return value


def _week_root(week: int) -> str:
    if week not in WEEKS:
        raise ShadowTransportError("shadow week must be exactly one of Weeks 1--6")
    return f"gs://{BUCKET}/{PREFIX}/weeks/week-{week:02d}"


def _week_uris(week: int) -> dict[str, str]:
    base = _week_root(week)
    return {
        "freeze_intent": f"{base}/freeze-intent.json",
        "freeze_attempt": f"{base}/freeze-attempt.json",
        "shadow_receipt": f"{base}/shadow-receipt.json",
        "settlement_attempt": f"{base}/settlement-attempt.json",
        "settled_scores": f"{base}/settled-scores.json",
    }


def build_week_intent(
    *,
    deployment: Mapping[str, Any],
    deployment_object: Mapping[str, Any],
    week: int,
    lock_at: str,
    snapshot_id: str,
    panels: Sequence[str],
    canonical_panel: str,
) -> dict[str, Any]:
    deployment = _validate_deployment(dict(deployment))
    deployment_object = _object_identity(
        deployment_object, uri=DEPLOYMENT_URI, create_only=True
    )
    if deployment_object["sha256"] != sha256(_canonical_json(deployment)).hexdigest():
        raise ShadowTransportError("deployment object does not bind manifest bytes")
    week = _exact_int(week, label="week")
    _week_root(week)
    lock = _utc(lock_at, label="contest lock").astimezone(timezone.utc)
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise ShadowTransportError("weekly snapshot ID is absent")
    if not isinstance(canonical_panel, str) or not canonical_panel.strip():
        raise ShadowTransportError("weekly canonical panel is absent")
    if any(not isinstance(item, str) or not item.strip() for item in panels):
        raise ShadowTransportError("weekly panel list is invalid")
    ordered = sorted(set(panels))
    if len(ordered) != len(panels) or canonical_panel not in ordered:
        raise ShadowTransportError("weekly panels repeat or omit the canonical panel")
    return {
        "version": "b1-corpus-tail-shadow-week-intent-v1",
        "transport_id": TRANSPORT_ID,
        "season": SEASON,
        "week": week,
        "deployment_object": deployment_object,
        "model_artifact_sha256": deployment["historical_license"][
            "model_artifact_sha256"
        ],
        "snapshot_id": snapshot_id,
        "lock_at": lock.isoformat(),
        "panels": ordered,
        "canonical_panel": canonical_panel,
        "output": _week_uris(week),
        "outcomes_allowed": False,
        "winner_fields_allowed": False,
        "shadow_enabled_execution_required": True,
        "production_licensed": False,
        "create_only": True,
    }


def _validate_week_intent(
    value: object,
    *,
    deployment: Mapping[str, Any],
) -> dict[str, Any]:
    keys = {
        "version", "transport_id", "season", "week", "deployment_object",
        "model_artifact_sha256", "snapshot_id", "lock_at", "panels",
        "canonical_panel", "output", "outcomes_allowed",
        "winner_fields_allowed", "shadow_enabled_execution_required",
        "production_licensed", "create_only",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ShadowTransportError("weekly shadow intent schema differs")
    deployment = _validate_deployment(dict(deployment))
    week = _exact_int(value["week"], label="intent week")
    if (
        value["version"] != "b1-corpus-tail-shadow-week-intent-v1"
        or value["transport_id"] != TRANSPORT_ID
        or value["season"] != SEASON
        or week not in WEEKS
        or value["model_artifact_sha256"]
        != deployment["historical_license"]["model_artifact_sha256"]
        or value["output"] != _week_uris(week)
        or value["outcomes_allowed"] is not False
        or value["winner_fields_allowed"] is not False
        or value["shadow_enabled_execution_required"] is not True
        or value["production_licensed"] is not False
        or value["create_only"] is not True
    ):
        raise ShadowTransportError("weekly shadow intent boundary differs")
    _object_identity(
        value["deployment_object"], uri=DEPLOYMENT_URI, create_only=True
    )
    _utc(value["lock_at"], label="contest lock")
    panels = value["panels"]
    if (
        not isinstance(panels, list)
        or not panels
        or panels != sorted(set(panels))
        or value["canonical_panel"] not in panels
        or not isinstance(value["snapshot_id"], str)
        or not value["snapshot_id"].strip()
    ):
        raise ShadowTransportError("weekly shadow panel/snapshot boundary differs")
    return value


def _validate_runtime_environment(deployment: Mapping[str, Any], *, freeze: bool) -> None:
    code = deployment["code"]
    expected_enabled = "1" if freeze else "0"
    if (
        os.environ.get("CODE_SHA") != code["commit_sha"]
        or os.environ.get("ANALYSIS_IMAGE") != code["image"]
        or os.environ.get("CORPUS_TAIL_SHADOW_ENABLED", "0") != expected_enabled
    ):
        raise ShadowTransportError("shadow runtime environment differs")


def _runtime_model(
    client: storage.Client,
    *,
    deployment: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    hist = deployment["historical_license"]
    _, report_raw = _download_generation(
        client, hist["historical_report_object"], label="historical report"
    )
    _, model_raw = _download_generation(
        client, hist["historical_model_object"], label="historical model"
    )
    report = _strict_json_bytes(report_raw, label="historical report")
    model = _strict_json_bytes(model_raw, label="historical model")
    if (
        not isinstance(report, dict)
        or not isinstance(model, dict)
        or report_raw != _canonical_json(report)
        or model_raw != _canonical_json(model)
    ):
        raise ShadowTransportError("historical report/model is not canonical")
    try:
        historical._validate_model(model, report=report)
    except Exception as exc:
        raise ShadowTransportError("runtime historical model does not validate") from exc
    if (
        report.get("historical_pass") is not True
        or model["artifact_sha256"] != hist["model_artifact_sha256"]
    ):
        raise ShadowTransportError("runtime historical license/model differs")
    return model, model_raw


def _load_remote_deployment(
    client: storage.Client,
    identity: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    observed, raw = _download_generation(client, identity, label="deployment")
    value = _strict_json_bytes(raw, label="deployment")
    if not isinstance(value, dict) or raw != _canonical_json(value):
        raise ShadowTransportError("deployment object is not canonical")
    return _validate_deployment(value), observed


def _load_remote_week_intent(
    client: storage.Client,
    *,
    week: int,
    generation: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if _GENERATION.fullmatch(generation) is None:
        raise ShadowTransportError("weekly intent generation differs")
    uri = _week_uris(week)["freeze_intent"]
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name, generation=int(generation))
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=int(generation))
    intent_object = _blob_identity(blob, uri=uri, raw=raw)
    intent = _strict_json_bytes(raw, label="weekly intent")
    if not isinstance(intent, dict) or raw != _canonical_json(intent):
        raise ShadowTransportError("weekly intent is not canonical")
    deployment, _ = _load_remote_deployment(client, intent["deployment_object"])
    return _validate_week_intent(intent, deployment=deployment), deployment, intent_object


def execute_freeze(
    *,
    week: int,
    intent_generation: str,
    storage_client: storage.Client | None = None,
    runner_main: Callable[[list[str]], int] = runner.main,
) -> dict[str, Any]:
    """Execute one pre-lock freeze only after explicit default-off override."""
    week = _exact_int(week, label="week")
    client = storage.Client(project=PROJECT) if storage_client is None else storage_client
    intent, deployment, intent_object = _load_remote_week_intent(
        client, week=week, generation=intent_generation
    )
    _validate_runtime_environment(deployment, freeze=True)
    model, model_raw = _runtime_model(client, deployment=deployment)
    attempt = {
        "version": "b1-corpus-tail-shadow-freeze-attempt-v1",
        "transport_id": TRANSPORT_ID,
        "season": SEASON,
        "week": week,
        "intent_object": intent_object,
        "model_object": deployment["historical_license"][
            "historical_model_object"
        ],
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False,
        "production_licensed": False,
    }
    attempt_raw = _canonical_json(attempt)
    attempt_object = _upload_create_once(
        client, uri=intent["output"]["freeze_attempt"], raw=attempt_raw
    )
    with tempfile.TemporaryDirectory(prefix="b1-tail-shadow-") as directory:
        temp = Path(directory)
        model_path = temp / "model.json"
        output = temp / "shadow-receipt.json"
        model_path.write_bytes(model_raw)
        argv = [
            "--shadow", f"{SEASON}:{week}",
            "--shadow-canonical-panel", intent["canonical_panel"],
            "--model-artifact", str(model_path),
            "--shadow-output", str(output),
            "--snapshot-id", intent["snapshot_id"],
            "--lock-at", intent["lock_at"],
        ]
        for panel in intent["panels"]:
            argv.extend(["--shadow-panel", panel])
        if runner_main(argv) != 0:
            raise ShadowTransportError("frozen shadow runner returned nonzero")
        raw = output.read_bytes()
        receipt = _strict_json_bytes(raw, label="shadow receipt")
        if not isinstance(receipt, dict) or raw != _canonical_json(receipt):
            raise ShadowTransportError("shadow receipt is not canonical")
        if (
            receipt.get("season") != SEASON
            or receipt.get("week") != week
            or receipt.get("model_artifact_sha256") != model["artifact_sha256"]
            or receipt.get("uses_realized_outcomes") is not False
            or receipt.get("production_licensed") is not False
        ):
            raise ShadowTransportError("shadow receipt boundary differs")
        _validate_shadow_receipt(receipt, week=week, deployment=deployment)
        _require_receipt_matches_intent(receipt, intent)
        receipt_object = _upload_create_once(
            client, uri=intent["output"]["shadow_receipt"], raw=raw
        )
    return {
        "version": "b1-corpus-tail-shadow-freeze-publication-v1",
        "season": SEASON,
        "week": week,
        "intent_object": intent_object,
        "attempt_object": attempt_object,
        "receipt_object": receipt_object,
        "uses_realized_outcomes": False,
        "production_licensed": False,
    }


def _validate_shadow_receipt(value: object, *, week: int, deployment: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    keys = {
        "version", "policy_version", "season", "week",
        "model_artifact_sha256", "source_identity", "candidate_budget_control",
        "candidate_budget_challenger", "entry_budget", "redundancy",
        "control_entries", "challenger_entries", "uses_realized_outcomes",
        "uses_winner_target_or_feature", "production_licensed",
        "prospective_adoption_gate_required",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ShadowTransportError("shadow receipt schema differs")
    if (
        value["version"] != "b1-corpus-tail-shadow-receipt-v1"
        or value["policy_version"] != science.POLICY_VERSION
        or value["season"] != SEASON
        or value["week"] != week
        or value["model_artifact_sha256"]
        != deployment["historical_license"]["model_artifact_sha256"]
        or value["uses_realized_outcomes"] is not False
        or value["uses_winner_target_or_feature"] is not False
        or value["production_licensed"] is not False
        or value["prospective_adoption_gate_required"] is not True
        or _exact_int(value["candidate_budget_control"], label="control budget")
        != _exact_int(value["candidate_budget_challenger"], label="challenger budget")
        or _exact_int(value["entry_budget"], label="entry budget") != 80
    ):
        raise ShadowTransportError("shadow receipt boundary differs")
    try:
        control = runner._book_keys(value["control_entries"], challenger=False)
        challenger = runner._book_keys(value["challenger_entries"], challenger=True)
        source = value["source_identity"]
        snapshot = runner._utc_timestamp(source.get("snapshot_at"), field="snapshot")
        lock = runner._utc_timestamp(source.get("lock_at"), field="contest lock")
    except Exception as exc:
        raise ShadowTransportError("shadow receipt book/source differs") from exc
    if snapshot >= lock or source.get("realized_outcome_columns_read") != []:
        raise ShadowTransportError("shadow receipt is not outcome-blind/pre-lock")
    return control, challenger


def _require_receipt_matches_intent(
    receipt: Mapping[str, Any], intent: Mapping[str, Any]
) -> None:
    source = receipt.get("source_identity")
    if not isinstance(source, Mapping) or (
        source.get("snapshot_id") != intent["snapshot_id"]
        or source.get("lock_at") != intent["lock_at"]
        or source.get("panels") != intent["panels"]
        or source.get("canonical_panel") != intent["canonical_panel"]
    ):
        raise ShadowTransportError("shadow receipt differs from weekly intent")


def _settlement_sql() -> str:
    return f"""
SELECT cand_ix, players, actual_score, labels_complete
FROM `{runner.CANDIDATE_TABLE}`
WHERE panel_run_id = @canonical_panel
  AND season = @season
  AND week = @week
ORDER BY cand_ix
"""


def _query_settled_scores(
    client: bigquery.Client,
    *,
    week: int,
    canonical_panel: str,
    expected_rosters: set[str],
    receipt_sha256: str,
) -> dict[str, Any]:
    job_id = f"b1_tail_shadow_settle_{SEASON}_w{week:02d}_{receipt_sha256[:16]}"
    job = client.query(
        _settlement_sql(),
        job_id=job_id,
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("canonical_panel", "STRING", canonical_panel),
            bigquery.ScalarQueryParameter("season", "INT64", SEASON),
            bigquery.ScalarQueryParameter("week", "INT64", week),
        ]),
    )
    frame = job.result().to_dataframe(create_bqstorage_client=False)
    if frame.empty:
        raise ShadowTransportError("settled-score query returned no candidates")
    labels = frame.labels_complete
    if labels.isna().any() or not pd.api.types.is_bool_dtype(labels.dtype) or not labels.all():
        raise ShadowTransportError("settled-score labels are not exact and complete")
    observed: dict[str, float] = {}
    for row in frame.itertuples(index=False):
        try:
            roster = ",".join(science.canonical_roster(row.players))
            score = float(row.actual_score)
        except Exception as exc:
            raise ShadowTransportError("settled-score row is invalid") from exc
        if not math.isfinite(score):
            raise ShadowTransportError("settled-score row is non-finite")
        if roster in observed and abs(observed[roster] - score) > 1e-6:
            raise ShadowTransportError("settled-score roster disagrees across rows")
        observed[roster] = score
    if not expected_rosters <= set(observed):
        raise ShadowTransportError("settled scores do not cover both exact-80 books")
    if (
        job.ended is None
        or job.ended.tzinfo is None
        or job.ended.utcoffset() is None
    ):
        raise ShadowTransportError("settled-score query lacks completion time")
    return {
        "version": "b1-corpus-tail-settled-scores-v1",
        "season": SEASON,
        "week": week,
        "labels_complete": True,
        "source_identity": {
            "source": "replay_candidates_staging.actual_score",
            "job_id": str(job.job_id),
            "query_sha256": sha256(_settlement_sql().encode()).hexdigest(),
            "captured_at": job.ended.astimezone(timezone.utc).isoformat(),
        },
        "scores": [
            {"roster_key": key, "actual_score": observed[key]}
            for key in sorted(expected_rosters)
        ],
    }


def execute_settlement(
    *,
    week: int,
    storage_client: storage.Client | None = None,
    bigquery_client: bigquery.Client | None = None,
) -> dict[str, Any]:
    """Collect scores only for one already frozen exact-80 union."""
    week = _exact_int(week, label="week")
    _week_root(week)
    gcs = storage.Client(project=PROJECT) if storage_client is None else storage_client
    deployment_object, deployment_raw = _download_current(
        gcs, uri=DEPLOYMENT_URI, label="deployment"
    )
    deployment = _strict_json_bytes(deployment_raw, label="deployment")
    if not isinstance(deployment, dict) or deployment_raw != _canonical_json(deployment):
        raise ShadowTransportError("deployment is not canonical")
    deployment = _validate_deployment(deployment)
    _validate_runtime_environment(deployment, freeze=False)
    uris = _week_uris(week)
    receipt_object, receipt_raw = _download_current(
        gcs, uri=uris["shadow_receipt"], label="shadow receipt"
    )
    receipt = _strict_json_bytes(receipt_raw, label="shadow receipt")
    control, challenger = _validate_shadow_receipt(
        receipt, week=week, deployment=deployment
    )
    intent_object, intent_raw = _download_current(
        gcs, uri=uris["freeze_intent"], label="freeze intent"
    )
    intent = _strict_json_bytes(intent_raw, label="freeze intent")
    if not isinstance(intent, dict) or intent_raw != _canonical_json(intent):
        raise ShadowTransportError("freeze intent is not canonical")
    _validate_week_intent(intent, deployment=deployment)
    _require_receipt_matches_intent(receipt, intent)
    attempt = {
        "version": "b1-corpus-tail-shadow-settlement-attempt-v1",
        "transport_id": TRANSPORT_ID,
        "season": SEASON,
        "week": week,
        "deployment_object": deployment_object,
        "freeze_intent_object": intent_object,
        "shadow_receipt_object": receipt_object,
        "query_sha256": sha256(_settlement_sql().encode()).hexdigest(),
        "outcomes_queried_at_creation": False,
        "retry_licensed": False,
        "production_licensed": False,
    }
    attempt_object = _upload_create_once(
        gcs, uri=uris["settlement_attempt"], raw=_canonical_json(attempt)
    )
    bq = bigquery.Client(project=PROJECT) if bigquery_client is None else bigquery_client
    scores = _query_settled_scores(
        bq,
        week=week,
        canonical_panel=receipt["source_identity"]["canonical_panel"],
        expected_rosters=set(control) | set(challenger),
        receipt_sha256=receipt_object["sha256"],
    )
    scores_raw = _canonical_json(scores)
    scores_object = _upload_create_once(
        gcs, uri=uris["settled_scores"], raw=scores_raw
    )
    return {
        "version": "b1-corpus-tail-shadow-settlement-publication-v1",
        "season": SEASON,
        "week": week,
        "attempt_object": attempt_object,
        "scores_object": scores_object,
        "labels_complete": True,
        "production_licensed": False,
    }


def _adoption_uris() -> dict[str, str]:
    base = f"gs://{BUCKET}/{PREFIX}/adoption"
    return {
        "attempt": f"{base}/attempt.json",
        "result": f"{base}/result.json",
    }


def execute_adoption(
    *,
    storage_client: storage.Client | None = None,
) -> dict[str, Any]:
    """Grade exact 2026 Weeks 1--6 with the frozen runner contract."""
    client = storage.Client(project=PROJECT) if storage_client is None else storage_client
    deployment_object, deployment_raw = _download_current(
        client, uri=DEPLOYMENT_URI, label="deployment"
    )
    deployment = _strict_json_bytes(deployment_raw, label="deployment")
    if not isinstance(deployment, dict) or deployment_raw != _canonical_json(deployment):
        raise ShadowTransportError("deployment is not canonical")
    deployment = _validate_deployment(deployment)
    _validate_runtime_environment(deployment, freeze=False)

    # Inventory all twelve required artifacts before opening any score body.
    metadata: dict[int, dict[str, dict[str, Any]]] = {}
    for week in WEEKS:
        uris = _week_uris(week)
        metadata[week] = {
            "shadow_receipt": _metadata_only(
                client, uri=uris["shadow_receipt"]
            ),
            "settled_scores": _metadata_only(
                client, uri=uris["settled_scores"]
            ),
        }
    attempt = {
        "version": "b1-corpus-tail-shadow-adoption-attempt-v1",
        "transport_id": TRANSPORT_ID,
        "season": SEASON,
        "weeks": list(WEEKS),
        "deployment_object": deployment_object,
        "input_metadata": metadata,
        "result_uri": _adoption_uris()["result"],
        "input_bodies_read_at_creation": False,
        "production_mutation_licensed": False,
        "retry_licensed": False,
    }
    attempt_object = _upload_create_once(
        client, uri=_adoption_uris()["attempt"], raw=_canonical_json(attempt)
    )

    with tempfile.TemporaryDirectory(prefix="b1-tail-adoption-") as directory:
        temp = Path(directory)
        weeks: list[dict[str, Any]] = []
        for week in WEEKS:
            identities: dict[str, dict[str, Any]] = {}
            for kind in ("shadow_receipt", "settled_scores"):
                meta = metadata[week][kind]
                # Resolve SHA only by a generation-qualified body read.
                uri = str(meta["uri"])
                bucket_name, name = _gcs_parts(uri)
                blob = client.bucket(bucket_name).blob(
                    name, generation=int(meta["generation"])
                )
                blob.reload()
                raw = blob.download_as_bytes(
                    if_generation_match=int(meta["generation"])
                )
                observed = _blob_identity(blob, uri=uri, raw=raw)
                if any(observed[key] != meta[key] for key in (
                    "uri", "generation", "metageneration", "bytes"
                )):
                    raise ShadowTransportError("adoption input changed after inventory")
                path = temp / f"week-{week:02d}-{kind}.json"
                path.write_bytes(raw)
                identities[kind] = {
                    "path": str(path),
                    "sha256": observed["sha256"],
                }
            weeks.append({"week": week, **identities})
        manifest = {
            "version": "b1-corpus-tail-adoption-grade-manifest-v1",
            "season": SEASON,
            "weeks": weeks,
        }
        manifest_path = temp / "grade-manifest.json"
        manifest_path.write_bytes(_canonical_json(manifest))
        result_path = temp / "adoption-result.json"
        try:
            grades = runner._materialize_adoption_grades(manifest_path)
            result = science.evaluate_six_week_adoption(grades)
        except Exception as exc:
            raise ShadowTransportError("frozen six-week adoption grading failed") from exc
        result_raw = _canonical_json(result)
        result_object = _upload_create_once(
            client, uri=_adoption_uris()["result"], raw=result_raw
        )
    return {
        "version": "b1-corpus-tail-shadow-adoption-publication-v1",
        "season": SEASON,
        "weeks": list(WEEKS),
        "attempt_object": attempt_object,
        "result_object": result_object,
        "prospective_gate_passed": result["prospective_gate_passed"],
        "production_review_licensed": result["production_review_licensed"],
        "automatic_production_mutation": False,
    }


def _execution_count(status: Mapping[str, Any], key: str) -> int:
    value = status.get(key, 0)
    if type(value) is not int or value < 0:
        raise ShadowTransportError(f"execution {key} differs")
    return value


def _phase_args(
    *, phase: str, week: int | None, intent_generation: str | None,
) -> list[str]:
    if phase == "freeze":
        if week not in WEEKS or _GENERATION.fullmatch(intent_generation or "") is None:
            raise ShadowTransportError("freeze execution arguments differ")
        return [
            SCRIPT_PATH, "execute-freeze", "--week", str(week),
            "--intent-generation", str(intent_generation),
        ]
    if phase == "settlement":
        if week not in WEEKS or intent_generation is not None:
            raise ShadowTransportError("settlement execution arguments differ")
        return [SCRIPT_PATH, "execute-settlement", "--week", str(week)]
    if phase == "adoption":
        if week is not None or intent_generation is not None:
            raise ShadowTransportError("adoption execution arguments differ")
        return [SCRIPT_PATH, "execute-adoption"]
    raise ShadowTransportError("unknown shadow execution phase")


def validate_execution_terminal(
    value: object,
    *,
    deployment: Mapping[str, Any],
    phase: str,
    week: int | None = None,
    intent_generation: str | None = None,
) -> dict[str, Any]:
    """Require one strict-success/no-retry execution before any body read."""
    deployment = _validate_deployment(dict(deployment))
    if not isinstance(value, dict):
        raise ShadowTransportError("execution metadata differs")
    metadata = value.get("metadata")
    status = value.get("status")
    spec = value.get("spec")
    if not isinstance(metadata, dict) or not isinstance(status, dict) or not isinstance(spec, dict):
        raise ShadowTransportError("execution schema differs")
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, dict) and row.get("type") == "Completed"
    ]
    job = deployment["job"]
    labels = metadata.get("labels")
    name = str(metadata.get("name", ""))
    if (
        re.fullmatch(rf"{re.escape(job['name'])}-[a-z0-9]+", name) is None
        or metadata.get("generation") != 1
        or not isinstance(labels, dict)
        or labels.get("run.googleapis.com/job") != job["name"]
        or labels.get("run.googleapis.com/jobUid") != job["uid"]
        or str(labels.get("run.googleapis.com/jobGeneration")) != job["generation"]
        or status.get("observedGeneration") != 1
        or len(completed) != 1
        or completed[0].get("status") != "True"
        or _execution_count(status, "succeededCount") != 1
        or _execution_count(status, "failedCount") != 0
        or _execution_count(status, "cancelledCount") != 0
        or _execution_count(status, "retriedCount") != 0
        or not isinstance(status.get("completionTime"), str)
        or not status["completionTime"]
    ):
        raise ShadowTransportError("execution is not strict terminal success")
    _utc(status["completionTime"], label="execution completion")
    task = spec.get("template", {}).get("spec")
    if not isinstance(task, dict):
        raise ShadowTransportError("execution task contract differs")
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(containers[0], dict):
        raise ShadowTransportError("execution container contract differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise ShadowTransportError("execution environment differs")
    env = {str(row["name"]): str(row["value"]) for row in env_rows}
    if len(env) != len(env_rows):
        raise ShadowTransportError("execution environment repeats a name")
    expected_env = dict(deployment["default_environment"])
    if phase == "freeze":
        expected_env["CORPUS_TAIL_SHADOW_ENABLED"] = "1"
    expected_args = _phase_args(
        phase=phase, week=week, intent_generation=intent_generation,
    )
    if (
        spec.get("taskCount") != 1
        or spec.get("parallelism") != 1
        or container.get("image") != deployment["code"]["image"]
        or container.get("command") != ["python"]
        or container.get("args") != expected_args
        or env != expected_env
        or container.get("resources", {}).get("limits")
        != {"cpu": CPU, "memory": MEMORY}
        or task.get("maxRetries") != 0
        or str(task.get("timeoutSeconds")) != TIMEOUT_SECONDS
        or task.get("serviceAccountName") != SERVICE_ACCOUNT
        or task.get("volumes", []) != []
    ):
        raise ShadowTransportError("execution does not match its frozen phase")
    return value


def _validate_settled_document(
    value: object,
    *,
    receipt: Mapping[str, Any],
    deployment: Mapping[str, Any],
    week: int,
) -> dict[str, Any]:
    control, challenger = _validate_shadow_receipt(
        receipt, week=week, deployment=deployment
    )
    if not isinstance(value, dict) or set(value) != {
        "version", "season", "week", "labels_complete", "source_identity", "scores",
    }:
        raise ShadowTransportError("settled score schema differs")
    if (
        value["version"] != "b1-corpus-tail-settled-scores-v1"
        or value["season"] != SEASON
        or value["week"] != week
        or value["labels_complete"] is not True
    ):
        raise ShadowTransportError("settled score boundary differs")
    source = value["source_identity"]
    if not isinstance(source, dict) or set(source) != {
        "source", "job_id", "query_sha256", "captured_at",
    } or source["source"] != "replay_candidates_staging.actual_score" or \
            not isinstance(source["job_id"], str) or not source["job_id"] or \
            source["query_sha256"] != sha256(_settlement_sql().encode()).hexdigest():
        raise ShadowTransportError("settled score source identity differs")
    _utc(source["captured_at"], label="settled score capture")
    scores: dict[str, float] = {}
    if not isinstance(value["scores"], list):
        raise ShadowTransportError("settled scores are absent")
    for row in value["scores"]:
        if not isinstance(row, dict) or set(row) != {"roster_key", "actual_score"}:
            raise ShadowTransportError("settled score row schema differs")
        key = row["roster_key"]
        score = row["actual_score"]
        if (
            not isinstance(key, str) or key in scores or isinstance(score, bool)
            or not isinstance(score, (int, float)) or not math.isfinite(score)
        ):
            raise ShadowTransportError("settled score row differs")
        scores[key] = float(score)
    if set(scores) != set(control) | set(challenger):
        raise ShadowTransportError("settled scores do not exactly cover both books")
    return value


def _validate_adoption_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "season", "weeks", "control", "challenger", "paired",
        "gates", "prospective_gate_passed", "production_review_licensed",
        "automatic_production_mutation", "winner_fields_used",
    }:
        raise ShadowTransportError("adoption result schema differs")
    if (
        value["version"] != "b1-corpus-tail-six-week-adoption-v1"
        or value["season"] != SEASON
        or value["weeks"] != list(WEEKS)
        or type(value["prospective_gate_passed"]) is not bool
        or value["production_review_licensed"] is not value["prospective_gate_passed"]
        or value["automatic_production_mutation"] is not False
        or value["winner_fields_used"] != []
    ):
        raise ShadowTransportError("adoption result boundary differs")
    return value


def harvest_phase(
    *,
    deployment: Mapping[str, Any],
    execution: Mapping[str, Any],
    phase: str,
    out: Path,
    week: int | None = None,
    intent_generation: str | None = None,
    storage_client: storage.Client | None = None,
) -> dict[str, Any]:
    """Harvest only after strict terminal metadata; never before it."""
    deployment = _validate_deployment(dict(deployment))
    execution = validate_execution_terminal(
        dict(execution), deployment=deployment, phase=phase, week=week,
        intent_generation=intent_generation,
    )
    client = storage.Client(project=PROJECT) if storage_client is None else storage_client
    if phase == "freeze":
        assert week is not None
        uri = _week_uris(week)["shadow_receipt"]
    elif phase == "settlement":
        assert week is not None
        uri = _week_uris(week)["settled_scores"]
    else:
        uri = _adoption_uris()["result"]
    metadata, raw = _download_current(client, uri=uri, label=f"{phase} result")
    value = _strict_json_bytes(raw, label=f"{phase} result")
    if not isinstance(value, dict) or raw != _canonical_json(value):
        raise ShadowTransportError(f"{phase} result is not canonical")
    if phase == "freeze":
        _validate_shadow_receipt(value, week=int(week), deployment=deployment)
    elif phase == "settlement":
        receipt_meta, receipt_raw = _download_current(
            client, uri=_week_uris(int(week))["shadow_receipt"], label="shadow receipt"
        )
        del receipt_meta
        receipt = _strict_json_bytes(receipt_raw, label="shadow receipt")
        _validate_settled_document(
            value, receipt=receipt, deployment=deployment, week=int(week)
        )
    else:
        _validate_adoption_result(value)
    if out.exists():
        raise ShadowTransportError("harvest directory already exists")
    pending = out.with_name(out.name + ".pending")
    if pending.exists():
        raise ShadowTransportError("harvest pending directory already exists")
    pending.mkdir(parents=True)
    (pending / "execution.json").write_bytes(_canonical_json(execution))
    (pending / "result-metadata.json").write_bytes(_canonical_json(metadata))
    (pending / "result.json").write_bytes(raw)
    ledger = "".join(
        f"{sha256((pending / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ("execution.json", "result-metadata.json", "result.json")
    )
    (pending / "harvest.sha256").write_text(ledger, encoding="utf-8")
    pending.rename(out)
    return {
        "phase": phase,
        "season": SEASON,
        "week": week,
        "object": metadata,
        "production_mutated": False,
    }


def _canonicalize_external(raw: Path, output: Path) -> None:
    if output.exists():
        raise ShadowTransportError("canonical output already exists")
    value = _strict_json_bytes(raw.read_bytes(), label="external JSON")
    _write_create_once(output, value)


def _publish_json(path: Path, *, uri: str) -> dict[str, Any]:
    raw = path.read_bytes()
    value = _strict_json_bytes(raw, label=path.name)
    if raw != _canonical_json(value):
        raise ShadowTransportError(f"{path.name} is not canonical")
    obj = _upload_create_once(storage.Client(project=PROJECT), uri=uri, raw=raw)
    return {**obj, "create_only": True}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)

    hist = sub.add_parser("validate-historical-license")
    hist.add_argument("--historical-out", type=Path, default=HISTORICAL_OUT)
    hist.add_argument("--evidence-commit", required=True)
    hist.add_argument("--remote-ref", default="origin/main")
    hist.add_argument("--output", type=Path, required=True)

    deploy = sub.add_parser("prepare-deployment")
    deploy.add_argument("--historical-license", type=Path, required=True)
    deploy.add_argument("--code-sha", required=True)
    deploy.add_argument("--image", required=True)
    deploy.add_argument("--build-id", required=True)
    deploy.add_argument("--build-metadata", type=Path, required=True)
    deploy.add_argument("--job-name", required=True)
    deploy.add_argument("--job-uid", required=True)
    for name in (
        "job-before", "job-after", "executions-before", "executions-after",
        "schedulers-before", "schedulers-after",
    ):
        deploy.add_argument(f"--{name}", type=Path, required=True)
    deploy.add_argument("--output", type=Path, required=True)

    reuse = sub.add_parser("validate-reuse-candidate")
    reuse.add_argument("--job-name", required=True)
    reuse.add_argument("--job-uid", required=True)
    reuse.add_argument("--job", type=Path, required=True)
    reuse.add_argument("--executions", type=Path, required=True)
    reuse.add_argument("--schedulers", type=Path, required=True)

    inert = sub.add_parser("validate-inert-job")
    inert.add_argument("--deployment", type=Path, required=True)
    inert.add_argument("--job", type=Path, required=True)
    inert.add_argument("--executions", type=Path, required=True)
    inert.add_argument("--schedulers", type=Path, required=True)

    publish_deploy = sub.add_parser("publish-deployment")
    publish_deploy.add_argument("--deployment", type=Path, required=True)
    publish_deploy.add_argument("--receipt", type=Path, required=True)

    week = sub.add_parser("prepare-week")
    week.add_argument("--deployment", type=Path, required=True)
    week.add_argument("--deployment-receipt", type=Path, required=True)
    week.add_argument("--week", type=int, required=True, choices=WEEKS)
    week.add_argument("--lock-at", required=True)
    week.add_argument("--snapshot-id", required=True)
    week.add_argument("--canonical-panel", required=True)
    week.add_argument("--panel", action="append", default=[])
    week.add_argument("--output", type=Path, required=True)

    publish_week = sub.add_parser("publish-week")
    publish_week.add_argument("--week", type=int, required=True, choices=WEEKS)
    publish_week.add_argument("--intent", type=Path, required=True)
    publish_week.add_argument("--receipt", type=Path, required=True)

    freeze = sub.add_parser("execute-freeze")
    freeze.add_argument("--week", type=int, required=True, choices=WEEKS)
    freeze.add_argument("--intent-generation", required=True)

    settle = sub.add_parser("execute-settlement")
    settle.add_argument("--week", type=int, required=True, choices=WEEKS)

    sub.add_parser("execute-adoption")

    harvest = sub.add_parser("harvest")
    harvest.add_argument("--deployment", type=Path, required=True)
    harvest.add_argument("--execution", type=Path, required=True)
    harvest.add_argument(
        "--phase", required=True, choices=("freeze", "settlement", "adoption")
    )
    harvest.add_argument("--week", type=int, choices=WEEKS)
    harvest.add_argument("--intent-generation")
    harvest.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _args()
    if args.command == "canonicalize-external-json":
        _canonicalize_external(args.raw, args.output)
    elif args.command == "validate-historical-license":
        value = validate_historical_license(
            out=args.historical_out,
            evidence_commit=args.evidence_commit,
            remote_ref=args.remote_ref,
        )
        digest = _write_create_once(args.output, value)
        print(json.dumps({"historical_license": str(args.output), "sha256": digest}))
    elif args.command == "prepare-deployment":
        license_document = _load_canonical(
            args.historical_license, label="historical license"
        )
        value = build_deployment_manifest(
            license_document=license_document,
            license_sha256=sha256(args.historical_license.read_bytes()).hexdigest(),
            code_sha=args.code_sha,
            image=args.image,
            build_id=args.build_id,
            build_metadata=_load_canonical(args.build_metadata, label="build metadata"),
            job_name=args.job_name,
            job_uid=args.job_uid,
            job_before=_load_canonical(args.job_before, label="job before"),
            job_after=_load_canonical(args.job_after, label="job after"),
            executions_before=_load_canonical(
                args.executions_before, label="executions before"
            ),
            executions_after=_load_canonical(
                args.executions_after, label="executions after"
            ),
            schedulers_before=_load_canonical(
                args.schedulers_before, label="schedulers before"
            ),
            schedulers_after=_load_canonical(
                args.schedulers_after, label="schedulers after"
            ),
        )
        digest = _write_create_once(args.output, value)
        print(json.dumps({"deployment": str(args.output), "sha256": digest}))
    elif args.command == "validate-reuse-candidate":
        print(json.dumps(validate_reuse_candidate(
            job_name=args.job_name,
            job_uid=args.job_uid,
            job=_load_canonical(args.job, label="job"),
            executions=_load_canonical(args.executions, label="executions"),
            schedulers=_load_canonical(args.schedulers, label="schedulers"),
        ), sort_keys=True))
    elif args.command == "validate-inert-job":
        deployment = _load_canonical(args.deployment, label="deployment")
        deployment = _validate_deployment(deployment)
        generation = _validate_inert_job(
            _load_canonical(args.job, label="job"),
            name=deployment["job"]["name"],
            uid=deployment["job"]["uid"],
            code_sha=deployment["code"]["commit_sha"],
            image=deployment["code"]["image"],
        )
        if generation != deployment["job"]["generation"]:
            raise ShadowTransportError("live shadow job generation differs")
        _require_idle(_load_canonical(args.executions, label="executions"))
        _require_unscheduled(
            _load_canonical(args.schedulers, label="schedulers"),
            job_name=deployment["job"]["name"],
        )
        print("B1_CORPUS_TAIL_SHADOW_JOB_INERT")
    elif args.command == "publish-deployment":
        value = _publish_json(args.deployment, uri=DEPLOYMENT_URI)
        _write_create_once(args.receipt, {
            "version": "b1-corpus-tail-shadow-deployment-receipt-v1",
            "object": value,
        })
        print(json.dumps(value, sort_keys=True))
    elif args.command == "prepare-week":
        deployment = _load_canonical(args.deployment, label="deployment")
        receipt = _load_canonical(
            args.deployment_receipt, label="deployment receipt"
        )
        if not isinstance(receipt, dict) or set(receipt) != {"version", "object"}:
            raise ShadowTransportError("deployment receipt schema differs")
        value = build_week_intent(
            deployment=deployment,
            deployment_object=receipt["object"],
            week=args.week,
            lock_at=args.lock_at,
            snapshot_id=args.snapshot_id,
            panels=args.panel,
            canonical_panel=args.canonical_panel,
        )
        digest = _write_create_once(args.output, value)
        print(json.dumps({"week_intent": str(args.output), "sha256": digest}))
    elif args.command == "publish-week":
        uri = _week_uris(args.week)["freeze_intent"]
        value = _publish_json(args.intent, uri=uri)
        _write_create_once(args.receipt, {
            "version": "b1-corpus-tail-shadow-week-intent-receipt-v1",
            "season": SEASON,
            "week": args.week,
            "object": value,
        })
        print(json.dumps(value, sort_keys=True))
    elif args.command == "execute-freeze":
        print(json.dumps(execute_freeze(
            week=args.week, intent_generation=args.intent_generation
        ), sort_keys=True))
    elif args.command == "execute-settlement":
        print(json.dumps(execute_settlement(week=args.week), sort_keys=True))
    elif args.command == "execute-adoption":
        print(json.dumps(execute_adoption(), sort_keys=True))
    else:
        deployment = _load_canonical(args.deployment, label="deployment")
        execution = _load_canonical(args.execution, label="execution")
        print(json.dumps(harvest_phase(
            deployment=deployment,
            execution=execution,
            phase=args.phase,
            out=args.output_dir,
            week=args.week,
            intent_generation=args.intent_generation,
        ), sort_keys=True))


if __name__ == "__main__":
    main()
