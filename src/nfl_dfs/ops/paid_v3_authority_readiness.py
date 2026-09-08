"""Provision and authenticate the fixed paid-v3 authority bucket.

The command is deliberately inert by default.  ``plan`` performs no provider
call, ``apply`` is a separately confirmed infrastructure operation, and
``preflight`` is read-only.  None of the paths inspect a lineup, score,
outcome, or paid payload.  The only object body used here is the fixed,
non-sensitive capability canary defined in this module.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import inspect
from importlib.metadata import version as distribution_version
import json
import os
from pathlib import Path
import re
import sys
from typing import Final


PLAN_SCHEMA: Final = "paid-v3-authority-provisioning-plan/v1"
READINESS_SCHEMA: Final = "paid-v3-authority-provider-readiness/v1"
APPLY_SCHEMA: Final = "paid-v3-authority-provisioning-receipt/v1"
INTENT_SCHEMA: Final = "paid-v3-authority-provisioning-intent/v1"

PROJECT: Final = "nfl-predictions-503414"
PROJECT_NUMBER: Final = "817589974517"
REGION: Final = "us-central1"
BUCKET: Final = "nfl-predictions-503414-paid-authority"
BUCKET_URI: Final = f"gs://{BUCKET}"
DEPLOYER_MEMBER: Final = "user:espechtsoftware@gmail.com"
RUNTIME_MEMBER: Final = (
    "serviceAccount:817589974517-compute@developer.gserviceaccount.com"
)
OBJECT_VIEWER: Final = "roles/storage.objectViewer"
OBJECT_CREATOR: Final = "roles/storage.objectCreator"
SOFT_DELETE_RETENTION_SECONDS: Final = 7 * 24 * 60 * 60
STORAGE_MINIMUM_VERSION: Final = (2, 16, 0)
STORAGE_MINIMUM_VERSION_TEXT: Final = "2.16.0"
CONFIRMATION_PHRASE: Final = (
    "provision-nfl-predictions-503414-paid-authority"
)

PROBE_OBJECT: Final = "paid-v3/provider-readiness/capability-v1.json"
PROBE_URI: Final = f"{BUCKET_URI}/{PROBE_OBJECT}"
_PROBE_DOCUMENT: Final = {
    "bucket": BUCKET,
    "outcome_data": False,
    "project": PROJECT,
    "purpose": "paid-v3-storage-list-and-generation-read-capability",
    "schema_version": "paid-v3-provider-readiness-canary/v1",
}
PROBE_BYTES: Final = (
    json.dumps(
        _PROBE_DOCUMENT,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    + b"\n"
)
PROBE_SHA256: Final = hashlib.sha256(PROBE_BYTES).hexdigest()

REQUIRED_BINDINGS: Final = (
    (OBJECT_VIEWER, DEPLOYER_MEMBER),
    (OBJECT_CREATOR, DEPLOYER_MEMBER),
    (OBJECT_VIEWER, RUNTIME_MEMBER),
)

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}\Z")
_VERSION = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:\.post[1-9][0-9]*)?(?:\+[0-9A-Za-z.-]+)?\Z"
)


class PaidV3AuthorityReadinessError(RuntimeError):
    """The paid-v3 infrastructure path could not prove its exact contract."""


def _fail(message: str) -> None:
    raise PaidV3AuthorityReadinessError(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _sha(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _seal(value: Mapping[str, object]) -> dict[str, object]:
    if "receipt_sha256" in value:
        _fail("receipt body already contains a receipt hash")
    sealed = dict(value)
    sealed["receipt_sha256"] = _sha(sealed)
    return sealed


def _validate_seal(value: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping):
        _fail("receipt is not an object")
    claimed = value.get("receipt_sha256")
    body = dict(value)
    body.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or claimed != _sha(body):
        _fail("receipt hash differs")


def assert_storage_api_support_v1(
    *,
    installed_version: str | None = None,
    bucket_class: type[object] | None = None,
    blob_class: type[object] | None = None,
) -> dict[str, object]:
    """Prove the installed client has the R4 soft-delete/read API surface."""

    if installed_version is None:
        installed_version = distribution_version("google-cloud-storage")
    match = _VERSION.fullmatch(installed_version)
    if match is None:
        _fail("google-cloud-storage version is non-release or malformed")
    parsed = tuple(
        int(match.group(name)) for name in ("major", "minor", "patch")
    )
    if parsed < STORAGE_MINIMUM_VERSION:
        _fail(
            "google-cloud-storage is below the required 2.16.0 soft-delete floor"
        )

    if bucket_class is None or blob_class is None:
        from google.cloud.storage import Blob, Bucket

        bucket_class = Bucket
        blob_class = Blob
    list_parameters = inspect.signature(bucket_class.list_blobs).parameters
    blob_parameters = inspect.signature(blob_class).parameters
    required_list_parameters = {"prefix", "versions", "soft_deleted"}
    if not required_list_parameters.issubset(list_parameters):
        _fail("Storage Bucket.list_blobs lacks the reviewed R4 parameters")
    if "generation" not in blob_parameters:
        _fail("Storage Blob constructor lacks generation binding")
    for method in ("reload", "download_as_bytes", "upload_from_string"):
        if not callable(getattr(blob_class, method, None)):
            _fail(f"Storage Blob.{method} is unavailable")
    upload_parameters = inspect.signature(
        blob_class.upload_from_string
    ).parameters
    if "if_generation_match" not in upload_parameters:
        _fail("Storage conditional create precondition is unavailable")
    return {
        "distribution": "google-cloud-storage",
        "installed_version": installed_version,
        "minimum_version": STORAGE_MINIMUM_VERSION_TEXT,
        "bucket_list_parameters": sorted(required_list_parameters),
        "generation_bound_blob": True,
        "exact_reload": True,
        "exact_download_as_bytes": True,
        "conditional_create": True,
    }


def provisioning_plan_v1() -> dict[str, object]:
    """Return the fixed plan without importing credentials or contacting GCP."""

    body: dict[str, object] = {
        "schema_version": PLAN_SCHEMA,
        "mode": "dry-run",
        "cloud_contacted": False,
        "cloud_mutation_authorized": False,
        "outcome_data_accessed": False,
        "project": PROJECT,
        "project_number": PROJECT_NUMBER,
        "bucket": BUCKET,
        "bucket_uri": BUCKET_URI,
        "location": REGION,
        "uniform_bucket_level_access": True,
        "public_access_prevention": "enforced",
        "soft_delete_retention_seconds": SOFT_DELETE_RETENTION_SECONDS,
        "required_iam_bindings": [
            {"role": role, "member": member}
            for role, member in REQUIRED_BINDINGS
        ],
        "capability_probe": {
            "uri": PROBE_URI,
            "bytes": len(PROBE_BYTES),
            "sha256": PROBE_SHA256,
            "outcome_data": False,
            "create_precondition": {"if_generation_match": 0},
            "required_list_views": ["live", "versions", "soft_deleted"],
            "required_read": ["generation_pinned_reload", "download_as_bytes"],
        },
        "operations": [
            {
                "operation": "create_bucket_if_absent",
                "existing_bucket_behavior": (
                    "validate exact immutable/configuration contract or stop"
                ),
            },
            {
                "operation": "add_missing_required_iam_bindings",
                "existing_policy_behavior": "preserve every existing binding",
            },
            {
                "operation": "create_capability_probe_if_absent",
                "existing_probe_behavior": (
                    "exact-reopen matching sole generation or stop"
                ),
            },
        ],
        "forbidden_operations": [
            "bucket_delete",
            "bucket_recreate",
            "bucket_location_change",
            "existing_binding_remove",
            "object_overwrite",
            "object_delete",
        ],
        "apply_requires": {
            "subcommand": "apply",
            "confirmation_phrase": CONFIRMATION_PHRASE,
            "create_only_intent_and_receipt_paths": True,
            "exact_deployer_principal": DEPLOYER_MEMBER,
            "exact_release_environment": [
                "IMAGE_SOURCE_COMMIT_SHA",
                "IMAGE_URI",
                "IMAGE_DIGEST",
            ],
        },
        "durable_receipt_guidance": (
            "Write intent and receipts beneath a durable reports/paid-v3-"
            "authority-readiness-runs/<attempt>/ directory, commit and push "
            "them with the reviewed source, retain both exact-image actor "
            "preflight receipts, never record credential tokens, and never "
            "blindly retry an ambiguous apply or publication."
        ),
    }
    body["plan_sha256"] = _sha(body)
    return body


def _positive_decimal(value: object, *, label: str) -> str:
    if isinstance(value, bool):
        _fail(f"{label} is invalid")
    token = str(value or "")
    if not token.isdigit() or int(token) <= 0 or token != str(int(token)):
        _fail(f"{label} is invalid")
    return token


def _bucket_metadata_v1(bucket: object) -> dict[str, object]:
    try:
        bucket.reload()  # type: ignore[attr-defined]
        name = getattr(bucket, "name", None)
        location = getattr(bucket, "location", None)
        project_number = _positive_decimal(
            getattr(bucket, "project_number", None),
            label="authority bucket project number",
        )
        metageneration = _positive_decimal(
            getattr(bucket, "metageneration", None),
            label="authority bucket metageneration",
        )
        iam_configuration = getattr(bucket, "iam_configuration")
        uniform = getattr(
            iam_configuration, "uniform_bucket_level_access_enabled"
        )
        prevention = getattr(
            iam_configuration, "public_access_prevention"
        )
        soft_delete_policy = getattr(bucket, "soft_delete_policy")
        retention = getattr(
            soft_delete_policy, "retention_duration_seconds"
        )
    except PaidV3AuthorityReadinessError:
        raise
    except Exception as exc:
        _fail(
            "authority bucket metadata could not be authenticated "
            f"({type(exc).__name__})"
        )
    if (
        name != BUCKET
        or not isinstance(location, str)
        or location.lower() != REGION
        or project_number != PROJECT_NUMBER
        or uniform is not True
        or prevention != "enforced"
        or type(retention) is not int
        or retention <= 0
    ):
        _fail("authority bucket metadata differs from the fixed contract")
    return {
        "name": BUCKET,
        "project_number": project_number,
        "location": REGION,
        "metageneration": metageneration,
        "uniform_bucket_level_access": True,
        "public_access_prevention": "enforced",
        "soft_delete_retention_seconds": retention,
    }


def _policy_bindings(policy: object) -> list[dict[str, object]]:
    raw_bindings = getattr(policy, "bindings", None)
    if not isinstance(raw_bindings, list):
        _fail("authority bucket IAM policy bindings are malformed")
    normalized: list[dict[str, object]] = []
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            _fail("authority bucket IAM policy binding is malformed")
        role = raw.get("role")
        members = raw.get("members")
        condition = raw.get("condition")
        if (
            not isinstance(role, str)
            or not role
            or not isinstance(members, (set, frozenset, list, tuple))
            or any(not isinstance(member, str) for member in members)
            or condition is not None and not isinstance(condition, Mapping)
        ):
            _fail("authority bucket IAM policy binding is malformed")
        normalized.append({
            "role": role,
            "members": sorted(set(members)),
            "condition": dict(condition) if condition is not None else None,
        })
    return normalized


def _required_iam_v1(policy: object) -> list[dict[str, str]]:
    bindings = _policy_bindings(policy)
    for role, member in REQUIRED_BINDINGS:
        unconditional = [
            binding
            for binding in bindings
            if binding["role"] == role
            and binding["condition"] is None
            and member in binding["members"]
        ]
        if len(unconditional) != 1:
            _fail(
                "authority bucket lacks one exact unconditional required IAM "
                f"binding: {role} {member}"
            )
    return [
        {"role": role, "member": member}
        for role, member in REQUIRED_BINDINGS
    ]


def _read_iam_v1(bucket: object) -> tuple[object, list[dict[str, str]]]:
    try:
        policy = bucket.get_iam_policy(  # type: ignore[attr-defined]
            requested_policy_version=3
        )
    except Exception as exc:
        _fail(
            "authority bucket IAM policy could not be authenticated "
            f"({type(exc).__name__})"
        )
    return policy, _required_iam_v1(policy)


def _client_project_v1(storage_client: object) -> None:
    if getattr(storage_client, "project", None) != PROJECT:
        _fail("Storage client project differs from the fixed paid-v3 project")


def _exact_project_bucket_v1(storage_client: object) -> object:
    _client_project_v1(storage_client)
    try:
        rows = list(storage_client.list_buckets(  # type: ignore[attr-defined]
            project=PROJECT, prefix=BUCKET
        ))
    except Exception as exc:
        _fail(
            "authority bucket inventory could not be authenticated "
            f"({type(exc).__name__})"
        )
    exact = [row for row in rows if getattr(row, "name", None) == BUCKET]
    if len(exact) != 1:
        _fail("exact authority bucket inventory does not contain one bucket")
    return exact[0]


def _generation(value: object) -> str:
    return _positive_decimal(value, label="capability probe generation")


def _probe_census_v1(storage_client: object) -> dict[str, list[str]]:
    from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
        read_paid_classic_final_generation_census_v3,
    )

    try:
        return read_paid_classic_final_generation_census_v3(
            PROBE_URI, storage_client=storage_client
        )
    except Exception as exc:
        _fail(
            "capability probe three-view census could not be authenticated "
            f"({type(exc).__name__})"
        )


def _exact_probe_read_v1(
    storage_client: object,
    generation: str,
) -> tuple[dict[str, object], bytes]:
    generation = _generation(generation)
    try:
        bucket = storage_client.bucket(BUCKET)  # type: ignore[attr-defined]
        blob = bucket.blob(PROBE_OBJECT, generation=int(generation))
        blob.reload()
        observed_generation = _generation(getattr(blob, "generation", None))
        raw = blob.download_as_bytes()
    except PaidV3AuthorityReadinessError:
        raise
    except Exception as exc:
        _fail(
            "capability probe exact-generation read could not be authenticated "
            f"({type(exc).__name__})"
        )
    if observed_generation != generation or not isinstance(raw, bytes):
        _fail("capability probe exact-generation representation differs")
    identity = {
        "uri": PROBE_URI,
        "generation": generation,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return identity, raw


def _probe_data_plane_v1(storage_client: object) -> dict[str, object]:
    before = _probe_census_v1(storage_client)
    if (
        len(before["live"]) != 1
        or before["noncurrent"]
        or before["soft_deleted"]
    ):
        _fail("capability probe does not have one clean historical generation")
    identity, raw = _exact_probe_read_v1(storage_client, before["live"][0])
    if raw != PROBE_BYTES or identity != {
        "uri": PROBE_URI,
        "generation": before["live"][0],
        "sha256": PROBE_SHA256,
        "bytes": len(PROBE_BYTES),
    }:
        _fail("capability probe exact bytes differ from the outcome-blind canary")
    after = _probe_census_v1(storage_client)
    if after != before:
        _fail("capability probe census changed during exact-generation read")
    return {
        "object_identity": identity,
        "generation_census": after,
        "list_views": ["live", "versions", "soft_deleted"],
        "iterators_fully_consumed": True,
        "generation_pinned_reload": True,
        "download_as_bytes": True,
        "content_decoded": False,
        "content_printed": False,
        "outcome_data": False,
    }


def _expected_principal(actor: str) -> str:
    if actor == "deployer":
        return DEPLOYER_MEMBER
    if actor == "runtime":
        return RUNTIME_MEMBER
    _fail("preflight actor is outside the reviewed deployer/runtime pair")


def resolve_adc_principal_v1() -> str:
    """Resolve the ADC email through token-info without retaining the token."""

    try:
        import google.auth
        from google.auth.transport.requests import Request
        import requests

        credentials, _ = google.auth.default(scopes=[
            "openid",
            "email",
            "https://www.googleapis.com/auth/cloud-platform",
        ])
        credentials.refresh(Request())
        token = credentials.token
        if not isinstance(token, str) or not token:
            _fail("ADC refresh did not return a token")
        response = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": token},
            timeout=30,
        )
        status = response.status_code
        payload = response.json() if status == 200 else None
    except PaidV3AuthorityReadinessError:
        raise
    except Exception as exc:
        _fail(f"ADC principal could not be resolved ({type(exc).__name__})")
    finally:
        if "credentials" in locals():
            try:
                credentials.token = None
            except Exception:
                pass
        if "token" in locals():
            token = None
    if (
        status != 200
        or not isinstance(payload, Mapping)
        or payload.get("email_verified") not in {True, "true", "True"}
        or not isinstance(payload.get("email"), str)
    ):
        _fail("ADC token-info did not authenticate one verified email")
    email = str(payload["email"])
    prefix = "serviceAccount:" if email.endswith(".gserviceaccount.com") else "user:"
    return prefix + email


def _release_identity_v1(
    source_commit: str,
    image: str,
    environment: Mapping[str, str],
) -> dict[str, str]:
    if _COMMIT.fullmatch(source_commit) is None or _IMAGE.fullmatch(image) is None:
        _fail("exact release source or immutable image identity is malformed")
    digest = image.rsplit("@", 1)[1]
    required = {
        "IMAGE_SOURCE_COMMIT_SHA": source_commit,
        "IMAGE_URI": image,
        "IMAGE_DIGEST": digest,
    }
    if any(environment.get(key) != value for key, value in required.items()):
        _fail("running release environment differs from the requested identity")
    return {"source_commit": source_commit, "image": image, "digest": digest}


def _normalize_release_identity_v1(
    value: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {
        "source_commit", "image", "digest",
    }:
        _fail("release identity schema differs")
    source_commit = value.get("source_commit")
    image = value.get("image")
    digest = value.get("digest")
    if (
        not isinstance(source_commit, str)
        or _COMMIT.fullmatch(source_commit) is None
        or not isinstance(image, str)
        or _IMAGE.fullmatch(image) is None
        or not isinstance(digest, str)
        or image.rsplit("@", 1)[1] != digest
    ):
        _fail("release identity differs")
    return {
        "source_commit": source_commit,
        "image": image,
        "digest": digest,
    }


def _configuration_from_receipt_v1(
    receipt: Mapping[str, object],
) -> dict[str, object]:
    _validate_seal(receipt)
    if receipt.get("schema_version") != READINESS_SCHEMA:
        _fail("paired deployer receipt schema differs")
    if (
        receipt.get("actor") != "deployer"
        or receipt.get("principal") != DEPLOYER_MEMBER
        or receipt.get("project") != PROJECT
        or receipt.get("project_number") != PROJECT_NUMBER
        or receipt.get("bucket") != BUCKET
        or receipt.get("bucket_uri") != BUCKET_URI
        or receipt.get("location") != REGION
        or receipt.get("uniform_bucket_level_access") is not True
        or receipt.get("public_access_prevention") != "enforced"
        or type(receipt.get("soft_delete_retention_seconds")) is not int
        or int(receipt["soft_delete_retention_seconds"]) <= 0
        or receipt.get("required_iam_bindings")
        != [
            {"role": role, "member": member}
            for role, member in REQUIRED_BINDINGS
        ]
        or receipt.get("iam_authenticated") is not True
        or receipt.get("iam_policy_read_by_actor") is not True
        or receipt.get("cloud_mutation_performed") is not False
        or receipt.get("destructive_or_recreate_operation_performed") is not False
        or receipt.get("outcome_data_accessed") is not False
        or receipt.get("paid_payload_accessed") is not False
    ):
        _fail("paired deployer receipt configuration differs")
    probe = receipt.get("capability_probe")
    if not isinstance(probe, Mapping):
        _fail("paired deployer receipt lacks capability probe evidence")
    identity = probe.get("object_identity")
    if not isinstance(identity, Mapping):
        _fail("paired deployer receipt lacks exact probe identity")
    generation = _generation(identity.get("generation"))
    expected_identity = {
        "uri": PROBE_URI,
        "generation": generation,
        "sha256": PROBE_SHA256,
        "bytes": len(PROBE_BYTES),
    }
    if (
        dict(identity) != expected_identity
        or probe.get("generation_census") != {
            "live": [generation],
            "noncurrent": [],
            "soft_deleted": [],
        }
        or probe.get("list_views") != ["live", "versions", "soft_deleted"]
        or probe.get("iterators_fully_consumed") is not True
        or probe.get("generation_pinned_reload") is not True
        or probe.get("download_as_bytes") is not True
        or probe.get("content_decoded") is not False
        or probe.get("content_printed") is not False
        or probe.get("outcome_data") is not False
    ):
        _fail("paired deployer receipt probe evidence differs")
    release_value = receipt.get("release_identity")
    if isinstance(release_value, Mapping):
        normalized_release = _normalize_release_identity_v1(release_value)
    else:
        _fail("paired deployer receipt release identity differs")
    return {
        "project_number": PROJECT_NUMBER,
        "soft_delete_retention_seconds": receipt[
            "soft_delete_retention_seconds"
        ],
        "probe_identity": dict(identity),
        "receipt_sha256": receipt["receipt_sha256"],
        "release_identity": normalized_release,
    }


def preflight_paid_v3_authority_v1(
    *,
    storage_client: object,
    actor: str,
    principal: str,
    release_identity: Mapping[str, str],
    paired_deployer_receipt: Mapping[str, object] | None = None,
    observed_at: str | None = None,
) -> dict[str, object]:
    """Read-only provider authentication for one exact release identity."""

    expected_principal = _expected_principal(actor)
    if principal != expected_principal:
        _fail("authenticated principal differs from the requested actor")
    normalized_release = _normalize_release_identity_v1(release_identity)
    _client_project_v1(storage_client)
    storage_api = assert_storage_api_support_v1()
    paired: dict[str, object] | None = None
    if actor == "deployer":
        bucket = _exact_project_bucket_v1(storage_client)
        metadata = _bucket_metadata_v1(bucket)
        _, required_iam = _read_iam_v1(bucket)
        iam_authenticated = True
    else:
        if paired_deployer_receipt is None:
            _fail("runtime preflight requires one exact deployer receipt")
        paired = _configuration_from_receipt_v1(paired_deployer_receipt)
        paired_release = paired["release_identity"]
        if paired_release != normalized_release:
            _fail("runtime release identity differs from the deployer receipt")
        bucket = storage_client.bucket(BUCKET)  # type: ignore[attr-defined]
        metadata = {
            "name": BUCKET,
            "project_number": paired["project_number"],
            "location": REGION,
            "metageneration": None,
            "uniform_bucket_level_access": True,
            "public_access_prevention": "enforced",
            "soft_delete_retention_seconds": paired[
                "soft_delete_retention_seconds"
            ],
        }
        required_iam = [
            {"role": role, "member": member}
            for role, member in REQUIRED_BINDINGS
        ]
        iam_authenticated = True
    probe = _probe_data_plane_v1(storage_client)
    if paired is not None and probe["object_identity"] != paired["probe_identity"]:
        _fail("runtime probe identity differs from the deployer receipt")
    body: dict[str, object] = {
        "schema_version": READINESS_SCHEMA,
        "observed_at": observed_at or _now(),
        "actor": actor,
        "principal": principal,
        "project": PROJECT,
        "project_number": metadata["project_number"],
        "bucket": BUCKET,
        "bucket_uri": BUCKET_URI,
        "location": REGION,
        "bucket_metageneration": metadata["metageneration"],
        "uniform_bucket_level_access": True,
        "public_access_prevention": "enforced",
        "soft_delete_retention_seconds": metadata[
            "soft_delete_retention_seconds"
        ],
        "required_iam_bindings": required_iam,
        "iam_authenticated": iam_authenticated,
        "iam_policy_read_by_actor": actor == "deployer",
        "storage_api": storage_api,
        "release_identity": normalized_release,
        "capability_probe": probe,
        "paired_deployer_receipt_sha256": (
            paired["receipt_sha256"] if paired is not None else None
        ),
        "cloud_contacted": True,
        "cloud_mutation_performed": False,
        "destructive_or_recreate_operation_performed": False,
        "outcome_data_accessed": False,
        "paid_payload_accessed": False,
    }
    return _seal(body)


def _missing_iam_bindings_v1(policy: object) -> list[tuple[str, str]]:
    bindings = _policy_bindings(policy)
    missing: list[tuple[str, str]] = []
    for role, member in REQUIRED_BINDINGS:
        if not any(
            binding["role"] == role
            and binding["condition"] is None
            and member in binding["members"]
            for binding in bindings
        ):
            missing.append((role, member))
    return missing


def _add_missing_iam_bindings_v1(
    policy: object,
    missing: Sequence[tuple[str, str]],
) -> None:
    bindings = _policy_bindings(policy)
    for role, member in missing:
        matches = [
            binding
            for binding in bindings
            if binding["role"] == role and binding["condition"] is None
        ]
        if len(matches) > 1:
            _fail("authority IAM policy has duplicate unconditional roles")
        if matches:
            members = list(matches[0]["members"])
            members.append(member)
            matches[0]["members"] = sorted(set(members))
        else:
            bindings.append({
                "role": role,
                "members": [member],
                "condition": None,
            })
    policy.bindings = [  # type: ignore[attr-defined]
        {
            "role": binding["role"],
            "members": set(binding["members"]),
            **(
                {"condition": binding["condition"]}
                if binding["condition"] is not None
                else {}
            ),
        }
        for binding in bindings
    ]
    if getattr(policy, "version", None) is None:
        policy.version = 3  # type: ignore[attr-defined]


def _create_bucket_v1(storage_client: object) -> object:
    bucket = storage_client.bucket(BUCKET)  # type: ignore[attr-defined]
    bucket.iam_configuration.uniform_bucket_level_access_enabled = True
    bucket.iam_configuration.public_access_prevention = "enforced"
    bucket.soft_delete_policy.retention_duration_seconds = (
        SOFT_DELETE_RETENTION_SECONDS
    )
    return storage_client.create_bucket(  # type: ignore[attr-defined]
        bucket,
        project=PROJECT,
        location=REGION,
        retry=None,
    )


def _list_exact_buckets_allow_absent_v1(storage_client: object) -> list[object]:
    _client_project_v1(storage_client)
    try:
        rows = list(storage_client.list_buckets(  # type: ignore[attr-defined]
            project=PROJECT, prefix=BUCKET
        ))
    except Exception as exc:
        _fail(
            "authority bucket inventory could not be authenticated "
            f"({type(exc).__name__})"
        )
    exact = [row for row in rows if getattr(row, "name", None) == BUCKET]
    if len(exact) > 1:
        _fail("authority bucket inventory contains duplicate exact names")
    return exact


def apply_paid_v3_authority_provisioning_v1(
    *,
    storage_client: object,
    principal: str,
    release_identity: Mapping[str, str],
    observed_at: str | None = None,
) -> dict[str, object]:
    """Add only the fixed bucket, missing IAM, and create-once canary."""

    if principal != DEPLOYER_MEMBER:
        _fail("only the exact reviewed deployer principal may apply provisioning")
    normalized_release = _normalize_release_identity_v1(release_identity)
    storage_api = assert_storage_api_support_v1()
    exact = _list_exact_buckets_allow_absent_v1(storage_client)
    bucket_create_requested = not exact
    bucket_created_now = False
    bucket_create_ambiguous_reconciled = False
    if exact:
        bucket = exact[0]
        _bucket_metadata_v1(bucket)
    else:
        try:
            bucket = _create_bucket_v1(storage_client)
            bucket_created_now = True
        except Exception:
            reconciled = _list_exact_buckets_allow_absent_v1(storage_client)
            if len(reconciled) != 1:
                _fail("bucket create failed and exact provider state is not usable")
            bucket = reconciled[0]
            bucket_create_ambiguous_reconciled = True
        _bucket_metadata_v1(bucket)

    try:
        policy = bucket.get_iam_policy(requested_policy_version=3)
    except Exception as exc:
        _fail(f"authority IAM read failed ({type(exc).__name__})")
    missing = _missing_iam_bindings_v1(policy)
    iam_set_requested = bool(missing)
    iam_set_returned = False
    iam_set_ambiguous_reconciled = False
    if missing:
        _add_missing_iam_bindings_v1(policy, missing)
        try:
            bucket.set_iam_policy(policy, retry=None)
            iam_set_returned = True
        except Exception:
            try:
                reconciled_policy = bucket.get_iam_policy(
                    requested_policy_version=3
                )
                _required_iam_v1(reconciled_policy)
            except Exception:
                _fail("IAM apply failed and exact provider state is not usable")
            iam_set_ambiguous_reconciled = True
    _, required_iam = _read_iam_v1(bucket)

    census = _probe_census_v1(storage_client)
    probe_create_requested = not any(census.values())
    probe_created_now = False
    probe_create_ambiguous_reconciled = False
    provider_generation: str | None = None
    if probe_create_requested:
        blob = bucket.blob(PROBE_OBJECT)
        try:
            blob.upload_from_string(
                PROBE_BYTES,
                content_type="application/json",
                if_generation_match=0,
                retry=None,
            )
            provider_generation = _generation(getattr(blob, "generation", None))
            probe_created_now = True
        except Exception:
            probe_create_ambiguous_reconciled = True
    probe = _probe_data_plane_v1(storage_client)
    if (
        provider_generation is not None
        and probe["object_identity"]["generation"] != provider_generation
    ):
        _fail("probe provider-returned generation differs after exact reopen")

    metadata = _bucket_metadata_v1(bucket)
    body: dict[str, object] = {
        "schema_version": APPLY_SCHEMA,
        "observed_at": observed_at or _now(),
        "actor": "deployer",
        "principal": principal,
        "project": PROJECT,
        "project_number": metadata["project_number"],
        "bucket": BUCKET,
        "bucket_uri": BUCKET_URI,
        "location": REGION,
        "bucket_metageneration": metadata["metageneration"],
        "uniform_bucket_level_access": True,
        "public_access_prevention": "enforced",
        "soft_delete_retention_seconds": metadata[
            "soft_delete_retention_seconds"
        ],
        "required_iam_bindings": required_iam,
        "iam_authenticated": True,
        "iam_policy_read_by_actor": True,
        "storage_api": storage_api,
        "release_identity": normalized_release,
        "capability_probe": probe,
        "mutations": {
            "bucket_create_requested": bucket_create_requested,
            "bucket_created_now": bucket_created_now,
            "bucket_create_ambiguous_reconciled": (
                bucket_create_ambiguous_reconciled
            ),
            "iam_set_requested": iam_set_requested,
            "iam_set_returned": iam_set_returned,
            "iam_set_ambiguous_reconciled": iam_set_ambiguous_reconciled,
            "probe_create_requested": probe_create_requested,
            "probe_created_now": probe_created_now,
            "probe_create_ambiguous_reconciled": (
                probe_create_ambiguous_reconciled
            ),
        },
        "cloud_contacted": True,
        "cloud_mutation_performed": any((
            bucket_created_now,
            bucket_create_ambiguous_reconciled,
            iam_set_returned,
            iam_set_ambiguous_reconciled,
            probe_created_now,
            probe_create_ambiguous_reconciled,
        )),
        "destructive_or_recreate_operation_performed": False,
        "outcome_data_accessed": False,
        "paid_payload_accessed": False,
    }
    return _seal(body)


def _write_create_only(path: Path, value: Mapping[str, object]) -> None:
    with path.open("xb") as stream:
        stream.write(_canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _storage_client() -> object:
    from google.cloud import storage

    return storage.Client(project=PROJECT)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run, explicitly provision, or read-only authenticate the "
            "fixed paid-v3 Cloud Storage authority boundary."
        )
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", help="render the no-contact default plan")

    apply = subparsers.add_parser(
        "apply", help="explicitly add the fixed infrastructure contract"
    )
    apply.add_argument("--confirm", required=True)
    apply.add_argument("--source-commit", required=True)
    apply.add_argument("--image", required=True)
    apply.add_argument("--receipt", required=True, type=Path)

    preflight = subparsers.add_parser(
        "preflight", help="read-only list/reload/download authentication"
    )
    preflight.add_argument("--actor", required=True, choices=("deployer", "runtime"))
    preflight.add_argument("--source-commit", required=True)
    preflight.add_argument("--image", required=True)
    preflight.add_argument("--receipt", required=True, type=Path)
    preflight.add_argument("--deployer-receipt", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    storage_client_factory: Callable[[], object] = _storage_client,
    principal_resolver: Callable[[], str] = resolve_adc_principal_v1,
    environment: Mapping[str, str] | None = None,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    command = args.command or "plan"
    if command == "plan":
        sys.stdout.write(_canonical_bytes(provisioning_plan_v1()).decode("utf-8"))
        return 0

    if command == "apply":
        if args.confirm != CONFIRMATION_PHRASE:
            print(
                "paid-v3 authority provisioning is disabled; provide the exact "
                "apply confirmation phrase",
                file=sys.stderr,
            )
            return 2
        intent_path = Path(f"{args.receipt}.intent.json")
        if args.receipt.exists() or intent_path.exists():
            print("paid-v3 apply intent or receipt already exists", file=sys.stderr)
            return 2
        try:
            release_identity = _release_identity_v1(
                args.source_commit,
                args.image,
                os.environ if environment is None else environment,
            )
        except Exception as exc:
            print(f"paid-v3 apply release identity failed closed: {exc}", file=sys.stderr)
            return 2
        intent = _seal({
            "schema_version": INTENT_SCHEMA,
            "created_at": _now(),
            "plan": provisioning_plan_v1(),
            "release_identity": release_identity,
            "receipt_path": str(args.receipt),
            "warning": (
                "If apply exits nonzero, do not blindly retry; authenticate exact "
                "provider state with a new read-only preflight."
            ),
        })
        try:
            _write_create_only(intent_path, intent)
            receipt = apply_paid_v3_authority_provisioning_v1(
                storage_client=storage_client_factory(),
                principal=principal_resolver(),
                release_identity=release_identity,
            )
            _write_create_only(args.receipt, receipt)
        except Exception as exc:
            print(f"paid-v3 authority apply failed closed: {exc}", file=sys.stderr)
            return 2
        sys.stdout.write(_canonical_bytes(receipt).decode("utf-8"))
        return 0

    if command == "preflight":
        if args.receipt.exists():
            print("paid-v3 preflight receipt already exists", file=sys.stderr)
            return 2
        paired_receipt: Mapping[str, object] | None = None
        if args.actor == "runtime" and args.deployer_receipt is None:
            print("runtime preflight requires --deployer-receipt", file=sys.stderr)
            return 2
        if args.deployer_receipt is not None:
            try:
                loaded = json.loads(args.deployer_receipt.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"deployer receipt could not be read: {exc}", file=sys.stderr)
                return 2
            if not isinstance(loaded, Mapping):
                print("deployer receipt is not an object", file=sys.stderr)
                return 2
            paired_receipt = loaded
        try:
            release_identity = _release_identity_v1(
                args.source_commit,
                args.image,
                os.environ if environment is None else environment,
            )
            receipt = preflight_paid_v3_authority_v1(
                storage_client=storage_client_factory(),
                actor=args.actor,
                principal=principal_resolver(),
                release_identity=release_identity,
                paired_deployer_receipt=paired_receipt,
            )
            _write_create_only(args.receipt, receipt)
        except Exception as exc:
            print(f"paid-v3 authority preflight failed closed: {exc}", file=sys.stderr)
            return 2
        sys.stdout.write(_canonical_bytes(receipt).decode("utf-8"))
        return 0

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
