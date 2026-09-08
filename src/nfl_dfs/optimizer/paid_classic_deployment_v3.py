"""Provider-evidence attestation for the paid Classic v3 Cloud Run release.

Provider build and Cloud Run attestation remain read-only. The sole mutation
surface is the final activation publisher: it conditionally creates one
posttraffic object, inventories all of its provider-visible history, and
exact-reopens the returned generation. Successful receipts therefore record
observed provider state, not strings found in a shell script or YAML file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import yaml

SCHEMA: Final = "paid-classic-cloud-run-deployment-attestation/v2"
ACTIVATION_SCHEMA: Final = "paid-classic-pretraffic-deployment-authorization/v1"
FINAL_ACTIVATION_SCHEMA: Final = "paid-classic-final-activation-authority/v1"
FINAL_ACTIVATION_PUBLICATION_SCHEMA: Final = (
    "paid-classic-final-activation-publication/v1"
)
PAID_V3_PROJECT: Final = "nfl-predictions-503414"
PAID_V3_REGION: Final = "us-central1"
PAID_V3_SERVICE: Final = "nfl-dfs-app"
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_BUILD = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_PROVIDER_UID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_REVISION = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _provider_resource_identity(
    document: Mapping[str, Any],
    *,
    label: str,
    expected_name: str,
    expected_project: str,
    expected_region: str,
) -> dict[str, str]:
    metadata = document.get("metadata")
    if not isinstance(metadata, Mapping):
        _fail(f"Cloud Run {label} metadata is missing")
    uid = str(metadata.get("uid", ""))
    self_link = str(metadata.get("selfLink", ""))
    labels = metadata.get("labels")
    resource_kind = {
        "service": "services",
        "revision": "revisions",
    }.get(label)
    if resource_kind is None:  # pragma: no cover - internal caller contract
        _fail("Cloud Run provider-resource label is unsupported")
    expected_self_link_suffix = (
        f"/namespaces/{expected_project}/{resource_kind}/{expected_name}"
    )
    if (
        metadata.get("name") != expected_name
        or metadata.get("namespace") != expected_project
        or _PROVIDER_UID.fullmatch(uid) is None
        or not self_link
        or not self_link.rstrip("/").endswith(expected_self_link_suffix)
        or not isinstance(labels, Mapping)
        or labels.get("cloud.googleapis.com/location") != expected_region
    ):
        _fail(f"Cloud Run {label} provider identity differs")
    return {"uid": uid, "self_link": self_link}


def _validate_traffic(
    value: object,
    *,
    expected_revision: str,
    require_traffic: bool,
) -> int:
    if not isinstance(value, list) or not value:
        _fail("Cloud Run traffic is malformed")
    revisions: list[str] = []
    total = 0
    expected_percent = 0
    for row in value:
        if not isinstance(row, Mapping):
            _fail("Cloud Run traffic is malformed")
        revision = row.get("revisionName")
        percent = row.get("percent")
        if (
            not isinstance(revision, str)
            or not revision
            or type(percent) is not int
            or not 0 <= percent <= 100
        ):
            _fail("Cloud Run traffic is malformed")
        revisions.append(revision)
        total += percent
        if revision == expected_revision:
            expected_percent = percent
    if len(revisions) != len(set(revisions)) or total != 100:
        _fail("Cloud Run traffic is duplicated or does not total 100")
    if require_traffic:
        if len(value) != 1 or expected_percent != 100:
            _fail("Cloud Run traffic is not wholly on the attested revision")
        return 100
    if expected_percent != 0:
        _fail("pre-activation revision already receives traffic")
    return 0


def _validate_activation_object_identity(
    value: object,
    *,
    allow_none: bool,
) -> dict[str, object] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes",
    }:
        _fail("activation exact object identity schema differs")
    uri = str(value.get("uri", ""))
    generation = str(value.get("generation", ""))
    sha256 = str(value.get("sha256", ""))
    byte_value = value.get("bytes")
    if (
        not uri.startswith("gs://")
        or uri.count("/") < 3
        or not generation.isdigit()
        or int(generation) <= 0
        or _SHA256.fullmatch(sha256) is None
        or type(byte_value) is not int
        or byte_value <= 0
    ):
        _fail("activation exact object identity is invalid")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256,
        "bytes": byte_value,
    }


def _deployment_authorization_uri(
    *, project: str, service: str, revision: str,
) -> str:
    return (
        f"gs://{project}-paid-authority/paid-v3/{service}/{revision}/"
        "deployment-authorization.json"
    )


def _final_activation_uri(
    *, project: str, service: str, revision: str,
) -> str:
    return (
        f"gs://{project}-paid-authority/paid-v3/{service}/{revision}/"
        "activation.json"
    )


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


def validate_paid_classic_active_traffic_state_v3(
    service: Mapping[str, Any],
    *,
    expected_service: str,
    expected_revision: str,
    expected_project: str = PAID_V3_PROJECT,
    expected_region: str = PAID_V3_REGION,
) -> dict[str, object]:
    """Reconcile an ambiguous cutover only from exact provider state."""

    if (
        not isinstance(service, Mapping)
        or expected_project != PAID_V3_PROJECT
        or expected_region != PAID_V3_REGION
        or expected_service != PAID_V3_SERVICE
        or _REVISION.fullmatch(expected_revision) is None
    ):
        _fail("traffic reconciliation target differs from paid-v3 policy")
    identity = _provider_resource_identity(
        service,
        label="service",
        expected_name=expected_service,
        expected_project=expected_project,
        expected_region=expected_region,
    )
    _ready(service, label="service")
    status = service.get("status")
    if not isinstance(status, Mapping) or status.get(
        "latestReadyRevisionName"
    ) != expected_revision:
        _fail("traffic reconciliation latest revision differs")
    _validate_traffic(
        status.get("traffic"),
        expected_revision=expected_revision,
        require_traffic=True,
    )
    return {
        "cloud_run_service": expected_service,
        "cloud_run_revision": expected_revision,
        "cloud_run_service_uid": identity["uid"],
        "provider_traffic_percent": 100,
        "provider_service_record_sha256": _sha(service),
    }


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
    # These are all caller-controlled Cloud Build step semantics.  Provider
    # observations (status, timing, digest, etc.) are intentionally excluded,
    # but an execution field is never silently projected away.
    allowed = {
        "id", "name", "entrypoint", "args", "dir", "env", "script",
        "secretEnv", "volumes", "timeout", "waitFor", "allowExitCodes",
        "allowFailure", "automapSubstitutions",
    }
    defaults: dict[str, object] = {
        "entrypoint": None, "args": None, "dir": None, "env": None,
        "script": None, "secretEnv": None, "volumes": None, "timeout": None,
        "waitFor": None, "allowExitCodes": None, "allowFailure": None,
        "automapSubstitutions": None,
    }
    for row in steps:
        if not isinstance(row, Mapping):
            _fail("reviewed Cloud Build step is malformed")
        unknown = set(row) - allowed
        # Cloud Build adds observational fields to returned step records.  A
        # field outside the reviewed contract is otherwise an ambiguity: fail
        # closed if it is not one of the documented provider observations.
        if unknown - {
            "status", "timing", "pullTiming", "outputImages", "failureInfo",
            "exitCode",
        }:
            _fail("provider build step contains unreviewed execution fields")
        projected = {key: row.get(key, default) for key, default in defaults.items()}
        projected.update({"id": row.get("id"), "name": row.get("name")})
        if not projected.get("id") or not projected.get("name"):
            _fail("reviewed Cloud Build step lacks identity")
        projected_steps.append(projected)
    top_allowed = {
        "steps", "images", "timeout", "queueTtl", "options",
        "serviceAccount", "secrets", "availableSecrets", "substitutions",
    }
    unknown_top = set(value) - top_allowed - {
        "id", "name", "status", "createTime", "startTime", "finishTime",
        "logUrl", "logsBucket", "projectId", "results", "artifacts",
        "source", "sourceProvenance", "timing", "failureInfo", "warnings",
        "buildTriggerId", "tags",
    }
    if unknown_top:
        _fail("provider build contains unreviewed execution fields")
    return {
        "steps": projected_steps,
        "images": list(images),
        **{
            key: value.get(key) if key in value else None
            for key in (
                "timeout", "queueTtl", "options", "serviceAccount", "secrets",
                "availableSecrets", "substitutions",
            )
        },
    }


def _normalize_provider_build_law(
    value: Mapping[str, Any],
    *,
    source_commit: str,
    build_image: str,
    reviewed_law: Mapping[str, object],
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
    # Reviewed YAML uses symbolic defaults while provider records contain
    # concrete substitutions.  Keep the comparison closed-world: only the
    # two declared substitutions may be expanded.
    substitutions = normalized.get("substitutions")
    if isinstance(substitutions, Mapping):
        normalized["substitutions"] = {
            key: (f"${{{key}}}" if key in {"_CODE_SHA", "_BUILD_IMAGE"} else value)
            for key, value in substitutions.items()
        }
    # Cloud Build materializes these documented provider defaults even when
    # the submitted YAML omits them.  Normalize only exact defaults absent
    # from the reviewed contract; any non-default or reviewed value remains
    # part of the closed-world comparison.
    provider_options = normalized.get("options")
    expected_options = reviewed_law.get("options")
    if isinstance(provider_options, Mapping):
        provider_options = dict(provider_options)
        expected_options = (
            dict(expected_options) if isinstance(expected_options, Mapping) else {}
        )
        for key, default in (("logging", "LEGACY"), ("pool", {})):
            if key not in expected_options and provider_options.get(key) == default:
                provider_options.pop(key)
        normalized["options"] = provider_options or None
    if not isinstance(normalized, dict):  # pragma: no cover - defensive
        _fail("normalized Cloud Build law is malformed")
    return normalized


def _normalize_reviewed_build_law(value: Mapping[str, Any]) -> dict[str, object]:
    projected = _reviewed_build_law(value)
    substitutions = projected.get("substitutions")
    if isinstance(substitutions, Mapping):
        projected["substitutions"] = {
            key: (f"${{{key}}}" if key in {"_CODE_SHA", "_BUILD_IMAGE"} else val)
            for key, val in substitutions.items()
        }
    return projected


def _provider_time(value: object, *, label: str) -> datetime:
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        _fail(f"{label} is not an RFC3339 timestamp")
    if parsed.tzinfo is None:
        _fail(f"{label} is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def validate_paid_classic_build_evidence_v3(
    build: Mapping[str, Any],
    reviewed_build_contract: Mapping[str, Any],
    *,
    expected_build_id: str,
    expected_source_commit: str,
    expected_immutable_image: str,
    expected_project: str = PAID_V3_PROJECT,
) -> dict[str, object]:
    """Authenticate provider build evidence before any traffic mutation."""

    if not isinstance(build, Mapping) or not isinstance(
        reviewed_build_contract, Mapping
    ):
        _fail("Cloud Build evidence or reviewed contract is not an object")
    if _BUILD.fullmatch(expected_build_id) is None:
        _fail("expected Cloud Build ID is malformed")
    if expected_project != PAID_V3_PROJECT:
        _fail("Cloud Build project differs from the pinned production project")
    if _COMMIT.fullmatch(expected_source_commit) is None:
        _fail("expected source commit is malformed")
    if _IMAGE.fullmatch(expected_immutable_image) is None:
        _fail("expected image is not an immutable @sha256 reference")
    image_name, image_digest = expected_immutable_image.rsplit("@", 1)
    if _DIGEST.fullmatch(image_digest) is None:
        _fail("expected image digest is malformed")
    if build.get("id") != expected_build_id or build.get("status") != "SUCCESS":
        _fail("Cloud Build provider record is not the successful expected build")
    if build.get("projectId") != expected_project:
        _fail("Cloud Build provider record names another project")
    if not build.get("createTime") or not build.get("finishTime"):
        _fail("Cloud Build provider record lacks terminal timestamps")
    build_created = _provider_time(build["createTime"], label="Cloud Build createTime")
    build_finished = _provider_time(build["finishTime"], label="Cloud Build finishTime")
    if not build_created < build_finished:
        _fail("Cloud Build timestamps are not ordered")
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
    reviewed_law = _normalize_reviewed_build_law(reviewed_build_contract)
    normalized_provider_law = _normalize_provider_build_law(
        build,
        source_commit=expected_source_commit,
        build_image=build_image,
        reviewed_law=reviewed_law,
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
        "cloud_project": expected_project,
        "source_commit_sha": expected_source_commit,
        "image_digest": image_digest,
        "immutable_image_uri": expected_immutable_image,
        "provider_build_create_time": build["createTime"],
        "provider_build_finish_time": build["finishTime"],
        "provider_build_record_sha256": _sha(build),
        "reviewed_build_contract_sha256": _sha(reviewed_law),
        "provider_build_created_before_finished": True,
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
    expected_project: str = PAID_V3_PROJECT,
    expected_region: str = PAID_V3_REGION,
    require_traffic: bool = True,
    expected_activation_uri: str | None = None,
    expected_activation_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate real provider descriptions and return a self-hashed receipt."""

    if not isinstance(service, Mapping) or not isinstance(revision, Mapping):
        _fail("Cloud Run provider evidence is not an object")
    build_evidence = validate_paid_classic_build_evidence_v3(
        build,
        reviewed_build_contract,
        expected_build_id=expected_build_id,
        expected_source_commit=expected_source_commit,
        expected_immutable_image=expected_immutable_image,
        expected_project=expected_project,
    )
    image_digest = str(build_evidence["image_digest"])

    if (
        expected_project != PAID_V3_PROJECT
        or expected_region != PAID_V3_REGION
        or expected_service != PAID_V3_SERVICE
    ):
        _fail(
            "Cloud Run project, region, or service differs from the pinned "
            "production target"
        )
    service_identity = _provider_resource_identity(
        service,
        label="service",
        expected_name=expected_service,
        expected_project=expected_project,
        expected_region=expected_region,
    )
    _ready(service, label="service")
    status = service.get("status")
    if not isinstance(status, Mapping) or status.get(
        "latestReadyRevisionName"
    ) != expected_revision:
        _fail("Cloud Run latest ready revision differs")
    traffic_percent = _validate_traffic(
        status.get("traffic"),
        expected_revision=expected_revision,
        require_traffic=require_traffic,
    )
    revision_identity = _provider_resource_identity(
        revision,
        label="revision",
        expected_name=expected_revision,
        expected_project=expected_project,
        expected_region=expected_region,
    )
    _ready(revision, label="revision")
    revision_created = (revision.get("metadata") or {}).get(
        "creationTimestamp"
    )
    if not revision_created:
        _fail("Cloud Run revision provider record lacks a creation timestamp")
    if _provider_time(revision_created, label="Cloud Run revision creation") < _provider_time(
        build["finishTime"], label="Cloud Build finishTime"
    ):
        _fail("Cloud Run revision was created before the successful build finished")

    expected_env = {
        "IMAGE_SOURCE_COMMIT_SHA": expected_source_commit,
        "IMAGE_DIGEST": image_digest,
        "IMAGE_URI": expected_immutable_image,
        "PAID_V3_CLOUD_BUILD_ID": expected_build_id,
        "PAID_V3_SERVICE": expected_service,
        "PAID_V3_PROJECT": expected_project,
        "PAID_V3_REGION": expected_region,
    }
    activation_identity = _validate_activation_object_identity(
        expected_activation_identity,
        allow_none=True,
    )
    if activation_identity is not None:
        if (
            expected_activation_uri is not None
            and activation_identity["uri"] != expected_activation_uri
        ):
            _fail("activation URI differs from exact object identity")
        expected_activation_uri = str(activation_identity["uri"])
    if expected_activation_uri is not None:
        expected_env["PAID_V3_ACTIVATION_URI"] = expected_activation_uri
    if activation_identity is not None:
        expected_env.update({
            "PAID_V3_ACTIVATION_GENERATION": str(
                activation_identity["generation"]
            ),
            "PAID_V3_ACTIVATION_SHA256": str(activation_identity["sha256"]),
            "PAID_V3_ACTIVATION_BYTES": str(activation_identity["bytes"]),
        })
    for label, document in (("service", service), ("revision", revision)):
        container = _containers(document)[0]
        if container.get("image") != expected_immutable_image:
            _fail(f"Cloud Run {label} does not use the immutable image")
        environment = _env(container)
        if any(environment.get(key) != value for key, value in expected_env.items()):
            _fail(f"Cloud Run {label} runtime identity differs")
        exact_activation_names = {
            "PAID_V3_ACTIVATION_GENERATION",
            "PAID_V3_ACTIVATION_SHA256",
            "PAID_V3_ACTIVATION_BYTES",
        }
        if activation_identity is None and any(
            key in environment for key in exact_activation_names
        ):
            _fail(
                f"Cloud Run {label} pre-activation runtime carries stale "
                "exact activation coordinates"
            )
        if "PAID_V3_ACTIVATION_AUTHORITY_JSON" in environment:
            _fail(f"Cloud Run {label} carries a forbidden inline activation authority")
    body: dict[str, object] = {
        "schema_version": SCHEMA,
        "cloud_project": expected_project,
        "cloud_region": expected_region,
        "cloud_build_id": expected_build_id,
        "source_commit_sha": expected_source_commit,
        "image_digest": image_digest,
        "immutable_image_uri": expected_immutable_image,
        "cloud_run_service": expected_service,
        "cloud_run_revision": expected_revision,
        "cloud_run_service_uid": service_identity["uid"],
        "cloud_run_service_self_link": service_identity["self_link"],
        "cloud_run_revision_uid": revision_identity["uid"],
        "cloud_run_revision_self_link": revision_identity["self_link"],
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
        "provider_traffic_percent": traffic_percent,
        "activation_stage": "traffic" if require_traffic else "pre-activation",
        "activation_uri": expected_activation_uri,
        "activation_object_identity": activation_identity,
    }
    body["attestation_sha256"] = _sha(body)
    return body


def validate_paid_classic_deployment_attestation_v3(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Reopen a retained attestation without trusting unbound text fields."""

    if not isinstance(value, Mapping):
        _fail("attestation is not an object")
    expected = {
        "schema_version", "cloud_project", "cloud_region",
        "cloud_build_id", "source_commit_sha",
        "image_digest", "immutable_image_uri", "cloud_run_service",
        "cloud_run_revision", "cloud_run_service_uid",
        "cloud_run_service_self_link", "cloud_run_revision_uid",
        "cloud_run_revision_self_link", "provider_build_create_time",
        "provider_build_finish_time", "provider_revision_create_time",
        "provider_build_record_sha256", "provider_service_record_sha256",
        "provider_revision_record_sha256", "reviewed_build_contract_sha256",
        "provider_ready",
        "provider_traffic_percent", "activation_stage", "activation_uri",
        "activation_object_identity",
        "attestation_sha256",
    }
    body = dict(value)
    if set(body) != expected:
        _fail("attestation schema differs")
    claimed = body.pop("attestation_sha256", None)
    if claimed != _sha(body):
        _fail("attestation hash differs")
    if (
        body.get("schema_version") != SCHEMA
        or body.get("cloud_project") != PAID_V3_PROJECT
        or body.get("cloud_region") != PAID_V3_REGION
        or _BUILD.fullmatch(str(body.get("cloud_build_id", ""))) is None
        or _COMMIT.fullmatch(str(body.get("source_commit_sha", ""))) is None
        or _DIGEST.fullmatch(str(body.get("image_digest", ""))) is None
        or _IMAGE.fullmatch(str(body.get("immutable_image_uri", ""))) is None
        or str(body["immutable_image_uri"]).rsplit("@", 1)[1]
        != body["image_digest"]
        or body.get("cloud_run_service") != PAID_V3_SERVICE
        or _REVISION.fullmatch(str(body.get("cloud_run_revision", ""))) is None
        or _PROVIDER_UID.fullmatch(
            str(body.get("cloud_run_service_uid", ""))
        ) is None
        or _PROVIDER_UID.fullmatch(
            str(body.get("cloud_run_revision_uid", ""))
        ) is None
        or not str(body.get("cloud_run_service_self_link", "")).rstrip(
            "/"
        ).endswith(
            f"/namespaces/{PAID_V3_PROJECT}/services/{PAID_V3_SERVICE}"
        )
        or not str(body.get("cloud_run_revision_self_link", "")).rstrip(
            "/"
        ).endswith(
            f"/namespaces/{PAID_V3_PROJECT}/revisions/"
            + str(body.get("cloud_run_revision"))
        )
        or not body.get("provider_build_create_time")
        or not body.get("provider_build_finish_time")
        or not body.get("provider_revision_create_time")
        or body.get("provider_ready") is not True
        or body.get("activation_stage") not in {"pre-activation", "traffic"}
        or body.get("provider_traffic_percent") != (
            100 if body.get("activation_stage") == "traffic" else 0
        )
        or (body.get("activation_uri") is not None and not str(
            body.get("activation_uri")
        ).startswith("gs://"))
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
    activation_identity = _validate_activation_object_identity(
        body.get("activation_object_identity"),
        allow_none=True,
    )
    if activation_identity is not None and (
        activation_identity["uri"] != body.get("activation_uri")
    ):
        _fail("attestation activation object identity differs from its URI")
    body["activation_object_identity"] = activation_identity
    build_created = _provider_time(
        body["provider_build_create_time"], label="Cloud Build createTime"
    )
    build_finished = _provider_time(
        body["provider_build_finish_time"], label="Cloud Build finishTime"
    )
    revision_created = _provider_time(
        body["provider_revision_create_time"],
        label="Cloud Run revision creation",
    )
    if not build_created < build_finished <= revision_created:
        _fail("attestation provider timestamps are not causally ordered")
    body["attestation_sha256"] = claimed
    return body


def validate_paid_classic_activation_authority_v3(
    value: Mapping[str, object],
    *,
    expected_project: str,
    expected_region: str,
    expected_build_id: str,
    expected_source_commit: str,
    expected_image: str,
    expected_service: str,
    expected_revision: str,
) -> dict[str, object]:
    """Validate an externally pinned authority for the activated revision.

    The authority is created from an authenticated no-traffic staging
    revision and names a distinct, predeclared runtime revision.  Its exact
    GCS identity is injected into that runtime revision, avoiding the
    self-reference that would result from asking a revision to name an object
    created only after that same revision receives traffic.
    """

    if not isinstance(value, Mapping):
        _fail("activation authority is not an object")
    expected = {
        "schema_version", "cloud_project", "cloud_region", "cloud_build_id",
        "source_commit_sha", "immutable_image_uri", "cloud_run_service",
        "staging_revision", "authorized_runtime_revision", "activation_uri",
        "staging_pre_activation", "activation_authorized", "authority_sha256",
    }
    body = dict(value)
    if set(body) != expected:
        _fail("activation authority schema differs")
    claimed = body.pop("authority_sha256", None)
    if claimed != _sha(body):
        _fail("activation authority hash differs")
    expected_activation_uri = _deployment_authorization_uri(
        project=expected_project,
        service=expected_service,
        revision=expected_revision,
    )
    if (
        body.get("schema_version") != ACTIVATION_SCHEMA
        or expected_project != PAID_V3_PROJECT
        or expected_region != PAID_V3_REGION
        or expected_service != PAID_V3_SERVICE
        or _BUILD.fullmatch(expected_build_id) is None
        or _COMMIT.fullmatch(expected_source_commit) is None
        or _IMAGE.fullmatch(expected_image) is None
        or body.get("cloud_project") != expected_project
        or body.get("cloud_region") != expected_region
        or body.get("cloud_build_id") != expected_build_id
        or body.get("source_commit_sha") != expected_source_commit
        or body.get("immutable_image_uri") != expected_image
        or body.get("cloud_run_service") != expected_service
        or body.get("authorized_runtime_revision") != expected_revision
        or _REVISION.fullmatch(str(body.get("staging_revision", ""))) is None
        or _REVISION.fullmatch(expected_revision) is None
        or body.get("staging_revision") == expected_revision
        or body.get("activation_uri") != expected_activation_uri
        or body.get("activation_authorized") is not True
        or not isinstance(body.get("staging_pre_activation"), Mapping)
    ):
        _fail("activation authority identity differs")
    nested = body["staging_pre_activation"]
    try:
        nested = validate_paid_classic_deployment_attestation_v3(nested)
    except ValueError as exc:
        _fail(f"activation authority staging receipt is invalid: {exc}")
    cross_fields = {
        "cloud_project": "cloud_project",
        "cloud_region": "cloud_region",
        "cloud_build_id": "cloud_build_id",
        "source_commit_sha": "source_commit_sha",
        "immutable_image_uri": "immutable_image_uri",
        "cloud_run_service": "cloud_run_service",
        "staging_revision": "cloud_run_revision",
        "activation_uri": "activation_uri",
    }
    if (
        nested.get("activation_stage") != "pre-activation"
        or nested.get("activation_object_identity") is not None
        or any(
            body.get(outer) != nested.get(inner)
            for outer, inner in cross_fields.items()
        )
    ):
        _fail("activation authority staging identity is not cross-bound")
    body["authority_sha256"] = claimed
    return body


def create_paid_classic_activation_authority_v3(
    staging_pre_activation: Mapping[str, object],
    *,
    expected_project: str,
    expected_region: str,
    expected_build_id: str,
    expected_source_commit: str,
    expected_image: str,
    expected_service: str,
    authorized_runtime_revision: str,
    activation_uri: str,
) -> dict[str, object]:
    """Create one pre-traffic authority from an authenticated staging receipt."""

    staging = validate_paid_classic_deployment_attestation_v3(
        staging_pre_activation
    )
    body: dict[str, object] = {
        "schema_version": ACTIVATION_SCHEMA,
        "cloud_project": expected_project,
        "cloud_region": expected_region,
        "cloud_build_id": expected_build_id,
        "source_commit_sha": expected_source_commit,
        "immutable_image_uri": expected_image,
        "cloud_run_service": expected_service,
        "staging_revision": staging["cloud_run_revision"],
        "authorized_runtime_revision": authorized_runtime_revision,
        "activation_uri": activation_uri,
        "staging_pre_activation": staging,
        "activation_authorized": True,
    }
    body["authority_sha256"] = _sha(body)
    return validate_paid_classic_activation_authority_v3(
        body,
        expected_project=expected_project,
        expected_region=expected_region,
        expected_build_id=expected_build_id,
        expected_source_commit=expected_source_commit,
        expected_image=expected_image,
        expected_service=expected_service,
        expected_revision=authorized_runtime_revision,
    )


def validate_paid_classic_final_activation_authority_v3(
    value: Mapping[str, object],
    *,
    deployment_authorization: Mapping[str, object],
    deployment_authorization_identity: Mapping[str, object],
    expected_project: str,
    expected_region: str,
    expected_build_id: str,
    expected_source_commit: str,
    expected_image: str,
    expected_service: str,
    expected_revision: str,
) -> dict[str, object]:
    """Authenticate the post-traffic fact which alone enables money output."""

    authorization_identity = _validate_activation_object_identity(
        deployment_authorization_identity,
        allow_none=False,
    )
    if authorization_identity is None:  # pragma: no cover - narrowed above
        _fail("deployment authorization identity is absent")
    authorization = validate_paid_classic_activation_authority_v3(
        deployment_authorization,
        expected_project=expected_project,
        expected_region=expected_region,
        expected_build_id=expected_build_id,
        expected_source_commit=expected_source_commit,
        expected_image=expected_image,
        expected_service=expected_service,
        expected_revision=expected_revision,
    )
    if authorization_identity["uri"] != authorization["activation_uri"]:
        _fail("deployment authorization object URI differs")
    if not isinstance(value, Mapping):
        _fail("final activation authority is not an object")
    expected = {
        "schema_version", "cloud_project", "cloud_region", "cloud_build_id",
        "source_commit_sha", "immutable_image_uri", "cloud_run_service",
        "cloud_run_revision", "activation_uri",
        "deployment_authorization_identity",
        "deployment_authorization_sha256", "active_traffic_attestation",
        "money_output_authorized", "authority_sha256",
    }
    body = dict(value)
    if set(body) != expected:
        _fail("final activation authority schema differs")
    claimed = body.pop("authority_sha256", None)
    if claimed != _sha(body):
        _fail("final activation authority hash differs")
    expected_final_uri = _final_activation_uri(
        project=expected_project,
        service=expected_service,
        revision=expected_revision,
    )
    if (
        body.get("schema_version") != FINAL_ACTIVATION_SCHEMA
        or body.get("cloud_project") != expected_project
        or body.get("cloud_region") != expected_region
        or body.get("cloud_build_id") != expected_build_id
        or body.get("source_commit_sha") != expected_source_commit
        or body.get("immutable_image_uri") != expected_image
        or body.get("cloud_run_service") != expected_service
        or body.get("cloud_run_revision") != expected_revision
        or body.get("activation_uri") != expected_final_uri
        or body.get("deployment_authorization_identity")
        != authorization_identity
        or body.get("deployment_authorization_sha256")
        != authorization["authority_sha256"]
        or body.get("money_output_authorized") is not True
        or not isinstance(body.get("active_traffic_attestation"), Mapping)
    ):
        _fail("final activation authority identity differs")
    try:
        traffic = validate_paid_classic_deployment_attestation_v3(
            body["active_traffic_attestation"]
        )
    except ValueError as exc:
        _fail(f"final activation traffic attestation is invalid: {exc}")
    cross_fields = {
        "cloud_project": "cloud_project",
        "cloud_region": "cloud_region",
        "cloud_build_id": "cloud_build_id",
        "source_commit_sha": "source_commit_sha",
        "immutable_image_uri": "immutable_image_uri",
        "cloud_run_service": "cloud_run_service",
        "cloud_run_revision": "cloud_run_revision",
    }
    if (
        traffic.get("activation_stage") != "traffic"
        or traffic.get("provider_traffic_percent") != 100
        or traffic.get("activation_uri") != authorization["activation_uri"]
        or traffic.get("activation_object_identity")
        != authorization_identity
        or any(
            body.get(outer) != traffic.get(inner)
            for outer, inner in cross_fields.items()
        )
    ):
        _fail("final activation is not bound to exact active provider traffic")
    body["active_traffic_attestation"] = traffic
    body["authority_sha256"] = claimed
    return body


def create_paid_classic_final_activation_authority_v3(
    deployment_authorization: Mapping[str, object],
    deployment_authorization_identity: Mapping[str, object],
    active_traffic_attestation: Mapping[str, object],
    *,
    expected_project: str,
    expected_region: str,
    expected_build_id: str,
    expected_source_commit: str,
    expected_image: str,
    expected_service: str,
    expected_revision: str,
) -> dict[str, object]:
    """Create the final gate only from authenticated active provider state."""

    authorization = validate_paid_classic_activation_authority_v3(
        deployment_authorization,
        expected_project=expected_project,
        expected_region=expected_region,
        expected_build_id=expected_build_id,
        expected_source_commit=expected_source_commit,
        expected_image=expected_image,
        expected_service=expected_service,
        expected_revision=expected_revision,
    )
    identity = _validate_activation_object_identity(
        deployment_authorization_identity,
        allow_none=False,
    )
    if identity is None:  # pragma: no cover - narrowed above
        _fail("deployment authorization identity is absent")
    traffic = validate_paid_classic_deployment_attestation_v3(
        active_traffic_attestation
    )
    body: dict[str, object] = {
        "schema_version": FINAL_ACTIVATION_SCHEMA,
        "cloud_project": expected_project,
        "cloud_region": expected_region,
        "cloud_build_id": expected_build_id,
        "source_commit_sha": expected_source_commit,
        "immutable_image_uri": expected_image,
        "cloud_run_service": expected_service,
        "cloud_run_revision": expected_revision,
        "activation_uri": _final_activation_uri(
            project=expected_project,
            service=expected_service,
            revision=expected_revision,
        ),
        "deployment_authorization_identity": identity,
        "deployment_authorization_sha256": authorization["authority_sha256"],
        "active_traffic_attestation": traffic,
        "money_output_authorized": True,
    }
    body["authority_sha256"] = _sha(body)
    return validate_paid_classic_final_activation_authority_v3(
        body,
        deployment_authorization=authorization,
        deployment_authorization_identity=identity,
        expected_project=expected_project,
        expected_region=expected_region,
        expected_build_id=expected_build_id,
        expected_source_commit=expected_source_commit,
        expected_image=expected_image,
        expected_service=expected_service,
        expected_revision=expected_revision,
    )


_ACTIVATION_IDENTITY_ENV: Final = {
    "uri": "PAID_V3_ACTIVATION_URI",
    "generation": "PAID_V3_ACTIVATION_GENERATION",
    "sha256": "PAID_V3_ACTIVATION_SHA256",
    "bytes": "PAID_V3_ACTIVATION_BYTES",
}


def paid_classic_activation_identity_from_environment_v3(
    environment: Mapping[str, str],
) -> dict[str, object]:
    raw = {
        field: str(environment.get(name, "")).strip()
        for field, name in _ACTIVATION_IDENTITY_ENV.items()
    }
    if any(not value for value in raw.values()):
        _fail("activation authority requires exact uri/generation/sha256/bytes")
    if not raw["bytes"].isdigit():
        _fail("activation authority byte length is invalid")
    return _validate_activation_object_identity({
        "uri": raw["uri"],
        "generation": raw["generation"],
        "sha256": raw["sha256"],
        "bytes": int(raw["bytes"]),
    }, allow_none=False)


def _read_exact_gcs_activation_v3(identity: Mapping[str, object]) -> bytes:
    from google.cloud import storage

    bucket_name, object_name = str(identity["uri"])[5:].split("/", 1)
    blob = storage.Client().bucket(bucket_name).blob(
        object_name, generation=int(str(identity["generation"]))
    )
    blob.reload()
    if str(blob.generation) != str(identity["generation"]):
        _fail("activation authority generation differs")
    return blob.download_as_bytes()


_FINAL_GENERATION_CENSUS_KEYS: Final = {
    "live", "noncurrent", "soft_deleted",
}


def _gcs_target_v3(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        _fail("final activation URI is invalid")
    try:
        bucket_name, object_name = uri[5:].split("/", 1)
    except ValueError:
        _fail("final activation URI is invalid")
    if not bucket_name or not object_name:
        _fail("final activation URI is invalid")
    return bucket_name, object_name


def _generation_token_v3(value: object) -> str:
    if isinstance(value, bool):
        _fail("final activation provider generation is invalid")
    generation = str(value or "")
    if (
        not generation.isdigit()
        or int(generation) <= 0
        or generation != str(int(generation))
    ):
        _fail("final activation provider generation is invalid")
    return generation


def validate_paid_classic_final_generation_census_v3(
    value: Mapping[str, object],
) -> dict[str, list[str]]:
    """Normalize one complete exact-name live/version/tombstone inventory."""

    if not isinstance(value, Mapping) or set(value) != _FINAL_GENERATION_CENSUS_KEYS:
        _fail("final activation generation census schema differs")
    normalized: dict[str, list[str]] = {}
    all_generations: list[str] = []
    for label in ("live", "noncurrent", "soft_deleted"):
        rows = value[label]
        if (
            not isinstance(rows, Sequence)
            or isinstance(rows, (str, bytes, bytearray))
        ):
            _fail("final activation generation census is malformed")
        generations = [_generation_token_v3(row) for row in rows]
        if len(generations) != len(set(generations)):
            _fail("final activation generation census is duplicated")
        generations.sort(key=int)
        normalized[label] = generations
        all_generations.extend(generations)
    if len(all_generations) != len(set(all_generations)):
        _fail("final activation generation census categories overlap")
    return normalized


def read_paid_classic_final_generation_census_v3(
    uri: str,
    *,
    storage_client: object | None = None,
) -> dict[str, list[str]]:
    """Fully consume every provider view for one exact activation name."""

    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    bucket_name, object_name = _gcs_target_v3(uri)
    bucket = storage_client.bucket(bucket_name)  # type: ignore[attr-defined]

    def exact_generations(rows: object) -> list[str]:
        # Materializing the iterator is intentional: a later-page provider
        # error must fail the census rather than silently yield a prefix.
        materialized = list(rows)  # type: ignore[arg-type]
        generations: list[str] = []
        for blob in materialized:
            name = getattr(blob, "name", None)
            if not isinstance(name, str):
                _fail("final activation generation census is malformed")
            if name != object_name:
                continue
            generations.append(_generation_token_v3(
                getattr(blob, "generation", None)
            ))
        if len(generations) != len(set(generations)):
            _fail("final activation generation census is duplicated")
        return generations

    live = exact_generations(bucket.list_blobs(prefix=object_name))
    versions = exact_generations(
        bucket.list_blobs(prefix=object_name, versions=True)
    )
    soft_deleted = exact_generations(
        bucket.list_blobs(prefix=object_name, soft_deleted=True)
    )
    if not set(live).issubset(versions):
        _fail("final activation generation census provider views disagree")
    return validate_paid_classic_final_generation_census_v3({
        "live": live,
        "noncurrent": sorted(set(versions) - set(live), key=int),
        "soft_deleted": soft_deleted,
    })


def _read_exact_gcs_final_activation_v3(
    uri: str,
    generation: str,
    *,
    storage_client: object | None = None,
) -> tuple[dict[str, object], bytes]:
    """Download only the generation selected by the complete census."""

    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    generation = _generation_token_v3(generation)
    bucket_name, object_name = _gcs_target_v3(uri)
    blob = storage_client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
        object_name, generation=int(generation)
    )
    blob.reload()
    if _generation_token_v3(getattr(blob, "generation", None)) != generation:
        _fail("final activation provider generation differs")
    raw = blob.download_as_bytes()
    if not isinstance(raw, bytes):
        _fail("final activation provider did not return bytes")
    identity = _validate_activation_object_identity(
        {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        allow_none=False,
    )
    if identity is None:  # pragma: no cover - narrowed above
        _fail("final activation exact identity is absent")
    return identity, raw


def _read_generation_census_v3(
    uri: str,
    reader: Callable[[str], Mapping[str, object]],
    *,
    action: str,
) -> dict[str, list[str]]:
    try:
        census = reader(uri)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - all provider uncertainty closes
        _fail(
            f"final activation {action} could not be authenticated "
            f"({type(exc).__name__})"
        )
    return validate_paid_classic_final_generation_census_v3(census)


def _require_empty_final_generation_census_v3(
    census: Mapping[str, object],
) -> dict[str, list[str]]:
    normalized = validate_paid_classic_final_generation_census_v3(census)
    if any(normalized.values()):
        _fail("final activation generation history already exists")
    return normalized


def _require_unique_final_generation_census_v3(
    census: Mapping[str, object],
) -> tuple[dict[str, list[str]], str]:
    normalized = validate_paid_classic_final_generation_census_v3(census)
    if (
        len(normalized["live"]) != 1
        or normalized["noncurrent"]
        or normalized["soft_deleted"]
    ):
        _fail("final activation does not have one unique historical generation")
    return normalized, normalized["live"][0]


def require_paid_classic_final_activation_absent_v3(
    *,
    expected_project: str,
    expected_service: str,
    expected_revision: str,
    generation_census_reader: (
        Callable[[str], Mapping[str, object]] | None
    ) = None,
) -> str:
    """Fail closed unless every provider history view is empty."""

    if (
        expected_project != PAID_V3_PROJECT
        or expected_service != PAID_V3_SERVICE
        or _REVISION.fullmatch(expected_revision) is None
    ):
        _fail("final activation absence target differs from paid-v3 policy")
    uri = _final_activation_uri(
        project=expected_project,
        service=expected_service,
        revision=expected_revision,
    )
    reader = (
        read_paid_classic_final_generation_census_v3
        if generation_census_reader is None
        else generation_census_reader
    )
    census = _read_generation_census_v3(uri, reader, action="absence")
    _require_empty_final_generation_census_v3(census)
    return uri


def publish_paid_classic_final_activation_authority_v3(
    raw: bytes,
    *,
    expected_project: str,
    expected_service: str,
    expected_revision: str,
    storage_client: object | None = None,
) -> dict[str, object]:
    """Atomically create, census, and exact-reopen the final money gate."""

    if (
        expected_project != PAID_V3_PROJECT
        or expected_service != PAID_V3_SERVICE
        or _REVISION.fullmatch(expected_revision) is None
    ):
        _fail("final activation publication target differs from paid-v3 policy")
    if not isinstance(raw, bytes) or not raw:
        _fail("final activation publication bytes are invalid")
    uri = _final_activation_uri(
        project=expected_project,
        service=expected_service,
        revision=expected_revision,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"final activation publication bytes are not JSON: {exc}")
    if not isinstance(payload, Mapping):
        _fail("final activation publication payload is not an object")
    payload_body = dict(payload)
    claimed = payload_body.pop("authority_sha256", None)
    if (
        payload.get("schema_version") != FINAL_ACTIVATION_SCHEMA
        or payload.get("activation_uri") != uri
        or payload.get("money_output_authorized") is not True
        or claimed != _sha(payload_body)
    ):
        _fail("final activation publication payload identity differs")

    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    census_reader = lambda target: read_paid_classic_final_generation_census_v3(
        target, storage_client=storage_client
    )
    before = _read_generation_census_v3(
        uri, census_reader, action="prepublication census"
    )
    _require_empty_final_generation_census_v3(before)
    bucket_name, object_name = _gcs_target_v3(uri)
    blob = storage_client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
        object_name
    )
    try:
        blob.upload_from_string(
            raw,
            content_type="application/json",
            if_generation_match=0,
        )
    except Exception as exc:  # noqa: BLE001 - conditional ambiguity closes
        _fail(
            "final activation conditional publication failed "
            f"({type(exc).__name__})"
        )
    provider_generation = _generation_token_v3(
        getattr(blob, "generation", None)
    )
    after = _read_generation_census_v3(
        uri, census_reader, action="postpublication census"
    )
    normalized_after, unique_generation = (
        _require_unique_final_generation_census_v3(after)
    )
    if unique_generation != provider_generation:
        _fail("final activation provider-returned generation differs")
    identity, reopened = _read_exact_gcs_final_activation_v3(
        uri,
        provider_generation,
        storage_client=storage_client,
    )
    if reopened != raw:
        _fail("final activation exact-reopened bytes differ")
    final_census = _read_generation_census_v3(
        uri, census_reader, action="exact-reopen census"
    )
    if final_census != normalized_after:
        _fail("final activation generation census changed during exact reopen")
    body: dict[str, object] = {
        "schema_version": FINAL_ACTIVATION_PUBLICATION_SCHEMA,
        "activation_object_identity": identity,
        "generation_census": final_census,
        "create_precondition": {"if_generation_match": 0},
        "created_now": True,
    }
    body["receipt_sha256"] = _sha(body)
    return body


def reopen_paid_classic_deployment_authorization_v3(
    environment: Mapping[str, str],
    *,
    object_reader: Callable[[Mapping[str, object]], bytes] | None = None,
) -> dict[str, object]:
    """Reopen the exact pretraffic object used only to stage a revision.

    This object deliberately cannot authorize money output.  It exists so the
    runtime revision can carry immutable coordinates before Cloud Run traffic
    is changed; the separate final activation authority is created only after
    provider traffic is reconciled.
    """

    identity = paid_classic_activation_identity_from_environment_v3(environment)
    reader = _read_exact_gcs_activation_v3 if object_reader is None else object_reader
    try:
        raw = reader(identity)
    except ValueError:
        raise
    except Exception as exc:
        _fail(
            "activation authority exact object read failed "
            f"({type(exc).__name__})"
        )
    if not isinstance(raw, bytes):
        _fail("activation authority reader did not return bytes")
    if len(raw) != identity["bytes"]:
        _fail("activation authority byte length differs")
    if hashlib.sha256(raw).hexdigest() != identity["sha256"]:
        _fail("activation authority bytes hash differs")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"activation authority bytes are not canonical JSON: {exc}")
    deployment_authorization = validate_paid_classic_activation_authority_v3(
        value,
        expected_project=str(environment.get("PAID_V3_PROJECT", "")),
        expected_region=str(environment.get("PAID_V3_REGION", "")),
        expected_build_id=str(environment.get("PAID_V3_CLOUD_BUILD_ID", "")),
        expected_source_commit=str(environment.get("IMAGE_SOURCE_COMMIT_SHA", "")),
        expected_image=str(environment.get("IMAGE_URI", "")),
        expected_service=str(environment.get("PAID_V3_SERVICE", "")),
        expected_revision=str(environment.get("K_REVISION", "")),
    )
    if deployment_authorization.get("activation_uri") != identity["uri"]:
        _fail("deployment authorization URI differs from its exact object identity")
    return {
        "authority": deployment_authorization,
        "object_identity": identity,
    }


def reopen_paid_classic_activation_authority_v3(
    environment: Mapping[str, str],
    *,
    object_reader: Callable[[Mapping[str, object]], bytes] | None = None,
    final_object_reader: (
        Callable[[str, str], tuple[Mapping[str, object], bytes]] | None
    ) = None,
    final_generation_census_reader: (
        Callable[[str], Mapping[str, object]] | None
    ) = None,
) -> dict[str, object]:
    """Require pretraffic authority plus one historically unique final gate."""

    deployment_envelope = reopen_paid_classic_deployment_authorization_v3(
        environment,
        object_reader=object_reader,
    )
    deployment_authorization = deployment_envelope["authority"]
    identity = deployment_envelope["object_identity"]

    final_uri = _final_activation_uri(
        project=str(environment.get("PAID_V3_PROJECT", "")),
        service=str(environment.get("PAID_V3_SERVICE", "")),
        revision=str(environment.get("K_REVISION", "")),
    )
    census_reader = (
        read_paid_classic_final_generation_census_v3
        if final_generation_census_reader is None
        else final_generation_census_reader
    )
    census_before = _read_generation_census_v3(
        final_uri, census_reader, action="runtime census"
    )
    normalized_census, final_generation = (
        _require_unique_final_generation_census_v3(census_before)
    )
    final_reader = (
        _read_exact_gcs_final_activation_v3
        if final_object_reader is None
        else final_object_reader
    )
    try:
        final_identity_raw, final_raw = final_reader(
            final_uri, final_generation
        )
    except ValueError:
        raise
    except Exception as exc:
        _fail(
            "final activation exact object read failed "
            f"({type(exc).__name__})"
        )
    final_identity = _validate_activation_object_identity(
        final_identity_raw,
        allow_none=False,
    )
    if final_identity is None:  # pragma: no cover - narrowed above
        _fail("final activation exact object identity is absent")
    if final_identity["uri"] != final_uri:
        _fail("final activation URI differs from the runtime gate URI")
    if final_identity["generation"] != final_generation:
        _fail("final activation identity differs from the unique generation")
    if not isinstance(final_raw, bytes):
        _fail("final activation reader did not return bytes")
    if len(final_raw) != final_identity["bytes"]:
        _fail("final activation byte length differs")
    if hashlib.sha256(final_raw).hexdigest() != final_identity["sha256"]:
        _fail("final activation bytes hash differs")
    try:
        final_value = json.loads(final_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"final activation bytes are not canonical JSON: {exc}")
    authority = validate_paid_classic_final_activation_authority_v3(
        final_value,
        deployment_authorization=deployment_authorization,
        deployment_authorization_identity=identity,
        expected_project=str(environment.get("PAID_V3_PROJECT", "")),
        expected_region=str(environment.get("PAID_V3_REGION", "")),
        expected_build_id=str(environment.get("PAID_V3_CLOUD_BUILD_ID", "")),
        expected_source_commit=str(environment.get("IMAGE_SOURCE_COMMIT_SHA", "")),
        expected_image=str(environment.get("IMAGE_URI", "")),
        expected_service=str(environment.get("PAID_V3_SERVICE", "")),
        expected_revision=str(environment.get("K_REVISION", "")),
    )
    census_after = _read_generation_census_v3(
        final_uri, census_reader, action="runtime exact-reopen census"
    )
    if census_after != normalized_census:
        _fail("final activation generation census changed during runtime read")
    return {
        "authority": authority,
        "object_identity": final_identity,
        "deployment_authorization": deployment_authorization,
        "deployment_authorization_object_identity": identity,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-build-only",
        action="store_true",
        help="authenticate build/provider law without mutating or attesting Cloud Run",
    )
    parser.add_argument(
        "--pre-activation",
        action="store_true",
        help="attest the Ready revision while it receives no traffic",
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
    parser.add_argument("--activation-uri")
    parser.add_argument("--activation-generation")
    parser.add_argument("--activation-sha256")
    parser.add_argument("--activation-bytes", type=int)
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
    activation_values = (
        args.activation_uri,
        args.activation_generation,
        args.activation_sha256,
        args.activation_bytes,
    )
    if any(value is not None for value in activation_values[1:]) and any(
        value is None for value in activation_values
    ):
        parser.error(
            "exact activation identity requires URI, generation, sha256, and bytes"
        )
    activation_identity = None
    if all(value is not None for value in activation_values):
        activation_identity = {
            "uri": args.activation_uri,
            "generation": args.activation_generation,
            "sha256": args.activation_sha256,
            "bytes": args.activation_bytes,
        }
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
        require_traffic=not args.pre_activation,
        expected_activation_uri=args.activation_uri,
        expected_activation_identity=activation_identity,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
