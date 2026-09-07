"""Provider-evidence attestation for the paid Classic v3 Cloud Run release.

This module is deliberately read-only.  The deployment wrapper performs the
mutation, then supplies the durable Cloud Build, Service, and Revision JSON
descriptions here.  A successful receipt therefore records observed provider
state, not strings found in a shell script or YAML file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import yaml

SCHEMA: Final = "paid-classic-cloud-run-deployment-attestation/v1"
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_BUILD = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")


def _fail(message: str) -> None:
    raise ValueError(f"{SCHEMA}: {message}")


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _ready(document: Mapping[str, Any], *, label: str) -> None:
    metadata = document.get("metadata")
    status = document.get("status")
    if not isinstance(metadata, Mapping) or not isinstance(status, Mapping):
        _fail(f"Cloud Run {label} provider record is incomplete")
    generation = metadata.get("generation")
    observed = status.get("observedGeneration")
    if generation is None or observed is None:
        _fail(f"Cloud Run {label} generation evidence is missing")
    if str(generation) != str(observed):
        _fail(f"Cloud Run {label} generation is not observed")
    ready = [
        row for row in status.get("conditions", [])
        if isinstance(row, Mapping) and row.get("type") == "Ready"
    ]
    if len(ready) != 1 or ready[0].get("status") != "True":
        _fail(f"Cloud Run {label} is not provider-confirmed Ready")


def _containers(document: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    try:
        containers = document["spec"]["template"]["spec"]["containers"]
    except (KeyError, TypeError):
        try:
            containers = document["spec"]["containers"]
        except (KeyError, TypeError):
            _fail("provider object has no container specification")
    if not isinstance(containers, list) or len(containers) != 1:
        _fail("provider object must have exactly one container")
    return containers


def _env(container: Mapping[str, Any]) -> dict[str, str]:
    rows = container.get("env", [])
    if not isinstance(rows, list):
        _fail("container environment is malformed")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            _fail("container environment row is malformed")
        name = str(row.get("name", ""))
        if not name or name in result or "value" not in row:
            _fail("container environment names are empty, duplicated, or indirect")
        result[name] = str(row["value"])
    return result


def _reviewed_build_law(
    value: Mapping[str, Any],
) -> dict[str, object]:
    """Project the immutable, security-relevant Cloud Build contract."""

    steps = value.get("steps")
    images = value.get("images")
    if not isinstance(steps, list) or not isinstance(images, list):
        _fail("reviewed Cloud Build contract is malformed")
    projected_steps: list[dict[str, object]] = []
    allowed = {"id", "name", "entrypoint", "args", "dir", "env"}
    for row in steps:
        if not isinstance(row, Mapping):
            _fail("reviewed Cloud Build step is malformed")
        projected = {
            key: child
            for key, child in row.items()
            if key in allowed
        }
        if not projected.get("id") or not projected.get("name"):
            _fail("reviewed Cloud Build step lacks identity")
        projected_steps.append(projected)
    return {"steps": projected_steps, "images": list(images)}


def _normalize_provider_build_law(
    value: Mapping[str, Any],
    *,
    source_commit: str,
    build_image: str,
) -> dict[str, object]:
    """Normalize provider-expanded substitutions back to reviewed tokens."""

    projected = _reviewed_build_law(value)

    def normalize(item: object) -> object:
        if isinstance(item, str):
            return item.replace(build_image, "${_BUILD_IMAGE}").replace(
                source_commit, "${_CODE_SHA}"
            )
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        return item

    normalized = normalize(projected)
    if not isinstance(normalized, dict):  # pragma: no cover - defensive
        _fail("normalized Cloud Build law is malformed")
    return normalized


def validate_paid_classic_build_evidence_v3(
    build: Mapping[str, Any],
    reviewed_build_contract: Mapping[str, Any],
    *,
    expected_build_id: str,
    expected_source_commit: str,
    expected_immutable_image: str,
) -> dict[str, object]:
    """Authenticate provider build evidence before any traffic mutation."""

    if _BUILD.fullmatch(expected_build_id) is None:
        _fail("expected Cloud Build ID is malformed")
    if _COMMIT.fullmatch(expected_source_commit) is None:
        _fail("expected source commit is malformed")
    if _IMAGE.fullmatch(expected_immutable_image) is None:
        _fail("expected image is not an immutable @sha256 reference")
    image_name, image_digest = expected_immutable_image.rsplit("@", 1)
    if _DIGEST.fullmatch(image_digest) is None:
        _fail("expected image digest is malformed")
    if build.get("id") != expected_build_id or build.get("status") != "SUCCESS":
        _fail("Cloud Build provider record is not the successful expected build")
    if not build.get("createTime") or not build.get("finishTime"):
        _fail("Cloud Build provider record lacks terminal timestamps")
    substitutions = build.get("substitutions")
    if not isinstance(substitutions, Mapping) or substitutions.get(
        "_CODE_SHA"
    ) != expected_source_commit:
        _fail("Cloud Build provider record does not bind the source commit")
    build_image = str(substitutions.get("_BUILD_IMAGE", ""))
    if build_image != f"{image_name}:paid-v3-{expected_source_commit}":
        _fail("Cloud Build provider record does not bind the reviewed image tag")
    images = (build.get("results") or {}).get("images")
    if not isinstance(images, list) or len(images) != 1:
        _fail("Cloud Build provider record must contain one image result")
    image_result = images[0]
    if not isinstance(image_result, Mapping) or image_result.get(
        "digest"
    ) != image_digest:
        _fail("Cloud Build image digest differs")
    built_reference = str(image_result.get("name", ""))
    built_name = built_reference.rsplit(":", 1)[0]
    if built_reference != image_name and built_name != image_name:
        _fail("Cloud Build image repository differs")
    reviewed_law = _reviewed_build_law(reviewed_build_contract)
    normalized_provider_law = _normalize_provider_build_law(
        build,
        source_commit=expected_source_commit,
        build_image=build_image,
    )
    if normalized_provider_law != reviewed_law:
        _fail("Cloud Build provider record differs from the reviewed build law")
    declared_images = build.get("images")
    if not isinstance(declared_images, list) or len(declared_images) != 1:
        _fail("Cloud Build provider record has an ambiguous image declaration")
    declared_name = str(declared_images[0]).rsplit(":", 1)[0]
    if declared_name != image_name:
        _fail("Cloud Build declared image repository differs")
    return {
        "schema_version": "paid-classic-cloud-build-attestation/v1",
        "cloud_build_id": expected_build_id,
        "source_commit_sha": expected_source_commit,
        "image_digest": image_digest,
        "immutable_image_uri": expected_immutable_image,
        "provider_build_create_time": build["createTime"],
        "provider_build_finish_time": build["finishTime"],
        "provider_build_record_sha256": _sha(build),
        "reviewed_build_contract_sha256": _sha(reviewed_law),
    }


def attest_paid_classic_deployment_v3(
    build: Mapping[str, Any],
    service: Mapping[str, Any],
    revision: Mapping[str, Any],
    reviewed_build_contract: Mapping[str, Any],
    *,
    expected_build_id: str,
    expected_source_commit: str,
    expected_immutable_image: str,
    expected_service: str,
    expected_revision: str,
) -> dict[str, object]:
    """Validate real provider descriptions and return a self-hashed receipt."""

    build_evidence = validate_paid_classic_build_evidence_v3(
        build,
        reviewed_build_contract,
        expected_build_id=expected_build_id,
        expected_source_commit=expected_source_commit,
        expected_immutable_image=expected_immutable_image,
    )
    image_digest = str(build_evidence["image_digest"])

    if (service.get("metadata") or {}).get("name") != expected_service:
        _fail("Cloud Run service name differs")
    _ready(service, label="service")
    status = service.get("status")
    if not isinstance(status, Mapping) or status.get(
        "latestReadyRevisionName"
    ) != expected_revision:
        _fail("Cloud Run latest ready revision differs")
    traffic = status.get("traffic")
    if not isinstance(traffic, list) or sum(
        int(row.get("percent", 0))
        for row in traffic
        if isinstance(row, Mapping)
        and row.get("revisionName") == expected_revision
    ) != 100:
        _fail("Cloud Run traffic is not wholly on the attested revision")
    if (revision.get("metadata") or {}).get("name") != expected_revision:
        _fail("Cloud Run revision provider record differs")
    _ready(revision, label="revision")
    revision_created = (revision.get("metadata") or {}).get(
        "creationTimestamp"
    )
    if not revision_created:
        _fail("Cloud Run revision provider record lacks a creation timestamp")

    expected_env = {
        "IMAGE_SOURCE_COMMIT_SHA": expected_source_commit,
        "IMAGE_DIGEST": image_digest,
        "IMAGE_URI": expected_immutable_image,
        "PAID_V3_CLOUD_BUILD_ID": expected_build_id,
    }
    for label, document in (("service", service), ("revision", revision)):
        container = _containers(document)[0]
        if container.get("image") != expected_immutable_image:
            _fail(f"Cloud Run {label} does not use the immutable image")
        environment = _env(container)
        if any(environment.get(key) != value for key, value in expected_env.items()):
            _fail(f"Cloud Run {label} runtime identity differs")
    body: dict[str, object] = {
        "schema_version": SCHEMA,
        "cloud_build_id": expected_build_id,
        "source_commit_sha": expected_source_commit,
        "image_digest": image_digest,
        "immutable_image_uri": expected_immutable_image,
        "cloud_run_service": expected_service,
        "cloud_run_revision": expected_revision,
        "provider_build_create_time": build_evidence[
            "provider_build_create_time"
        ],
        "provider_build_finish_time": build_evidence[
            "provider_build_finish_time"
        ],
        "provider_revision_create_time": revision_created,
        "provider_build_record_sha256": build_evidence[
            "provider_build_record_sha256"
        ],
        "provider_service_record_sha256": _sha(service),
        "provider_revision_record_sha256": _sha(revision),
        "reviewed_build_contract_sha256": build_evidence[
            "reviewed_build_contract_sha256"
        ],
        "provider_ready": True,
        "provider_traffic_percent": 100,
    }
    body["attestation_sha256"] = _sha(body)
    return body


def validate_paid_classic_deployment_attestation_v3(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Reopen a retained attestation without trusting unbound text fields."""

    expected = {
        "schema_version", "cloud_build_id", "source_commit_sha",
        "image_digest", "immutable_image_uri", "cloud_run_service",
        "cloud_run_revision", "provider_build_create_time",
        "provider_build_finish_time", "provider_revision_create_time",
        "provider_build_record_sha256", "provider_service_record_sha256",
        "provider_revision_record_sha256", "reviewed_build_contract_sha256",
        "provider_ready",
        "provider_traffic_percent", "attestation_sha256",
    }
    body = dict(value)
    if set(body) != expected:
        _fail("attestation schema differs")
    claimed = body.pop("attestation_sha256", None)
    if claimed != _sha(body):
        _fail("attestation hash differs")
    if (
        body.get("schema_version") != SCHEMA
        or _BUILD.fullmatch(str(body.get("cloud_build_id", ""))) is None
        or _COMMIT.fullmatch(str(body.get("source_commit_sha", ""))) is None
        or _DIGEST.fullmatch(str(body.get("image_digest", ""))) is None
        or _IMAGE.fullmatch(str(body.get("immutable_image_uri", ""))) is None
        or str(body["immutable_image_uri"]).rsplit("@", 1)[1]
        != body["image_digest"]
        or not body.get("cloud_run_service")
        or not body.get("cloud_run_revision")
        or not body.get("provider_build_create_time")
        or not body.get("provider_build_finish_time")
        or not body.get("provider_revision_create_time")
        or body.get("provider_ready") is not True
        or body.get("provider_traffic_percent") != 100
        or any(
            re.fullmatch(r"[0-9a-f]{64}", str(body.get(field, ""))) is None
            for field in (
                "provider_build_record_sha256",
                "provider_service_record_sha256",
                "provider_revision_record_sha256",
                "reviewed_build_contract_sha256",
            )
        )
    ):
        _fail("attestation identity is invalid")
    body["attestation_sha256"] = claimed
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-build-only",
        action="store_true",
        help="authenticate build/provider law without mutating or attesting Cloud Run",
    )
    parser.add_argument("--build-json", type=Path, required=True)
    parser.add_argument("--service-json", type=Path)
    parser.add_argument("--revision-json", type=Path)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--service")
    parser.add_argument("--revision")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    build = json.loads(args.build_json.read_text())
    reviewed = yaml.safe_load(args.build_contract.read_text())
    if args.verify_build_only:
        evidence = validate_paid_classic_build_evidence_v3(
            build,
            reviewed,
            expected_build_id=args.build_id,
            expected_source_commit=args.source_commit,
            expected_immutable_image=args.image,
        )
        print(json.dumps(evidence, sort_keys=True))
        return 0
    if any(value is None for value in (
        args.service_json, args.revision_json, args.service,
        args.revision, args.output,
    )):
        parser.error(
            "deployment attestation requires --service-json, --revision-json, "
            "--service, --revision, and --output"
        )
    receipt = attest_paid_classic_deployment_v3(
        build,
        json.loads(args.service_json.read_text()),
        json.loads(args.revision_json.read_text()),
        reviewed,
        expected_build_id=args.build_id,
        expected_source_commit=args.source_commit,
        expected_immutable_image=args.image,
        expected_service=args.service,
        expected_revision=args.revision,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
