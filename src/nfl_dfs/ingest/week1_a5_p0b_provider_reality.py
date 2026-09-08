"""Outcome-blind provider-reality audit for the Week-1 capture-v3 path.

This module is deliberately separate from the accepted P0-A collector.  The
default command only renders a no-contact plan.  ``audit`` is a separately
confirmed, read-only fact capture: it authenticates provider IAM/runtime
metadata and uses the accepted collector's fixed session transport to inspect
one active-entry CSV without publishing its bytes or any acquisition evidence.

The audit is not an activation path.  It never fills live pins, never invokes
the live collector/publishers, never executes or updates a Cloud Run job, and
never reads a contest result or standings payload.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Final, Protocol

from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_a5_dk_acquisition as acquisition
from nfl_dfs.ingest import week1_a5_dk_acquisition_pins as live_pins
from nfl_dfs.ingest import week1_a5_governed_capture_v3 as capture_v3

PLAN_SCHEMA: Final = "week1-a5-capture-v3-p0b-provider-reality-plan/v1"
INTENT_SCHEMA: Final = "week1-a5-capture-v3-p0b-provider-reality-intent/v1"
RECEIPT_SCHEMA: Final = "week1-a5-capture-v3-p0b-provider-reality-receipt/v1"
CONFIRMATION_PHRASE: Final = "capture-week1-a5-p0b-provider-reality-v1"

PROJECT: Final = acquisition.LIVE_PROJECT
AUTHORITY_BUCKET: Final = acquisition.LIVE_AUTHORITY_BUCKET
SESSION_STATE_PATH: Final = acquisition.LIVE_SESSION_STATE_PATH
SESSION_PROFILE: Final = acquisition.COLLECTOR_SESSION_PROFILE
ACCEPTANCE_PROFILE: Final = capture.ACCEPTANCE_ACQUISITION_PROFILE

ASSET_OPTIONS: Final = MappingProxyType(
    {
        "expandGroups": True,
        "expandResources": True,
        "expandRoles": True,
        "outputGroupEdges": True,
        "outputResourceEdges": True,
    }
)


def _asset_options(surface: str) -> dict[str, bool]:
    options = dict(ASSET_OPTIONS)
    if surface in {
        "collector_service_account",
        "authority_reader_service_account",
    }:
        options["analyzeServiceAccountImpersonation"] = True
    return options


AUTHORITY_BUCKET_PERMISSIONS: Final = (
    "storage.buckets.delete",
    "storage.buckets.setIamPolicy",
    "storage.buckets.update",
    "storage.objects.create",
    "storage.objects.delete",
    "storage.objects.update",
)
SERVICE_ACCOUNT_IMPERSONATION_PERMISSIONS: Final = (
    "iam.serviceAccounts.actAs",
    "iam.serviceAccounts.getAccessToken",
    "iam.serviceAccounts.getOpenIdToken",
    "iam.serviceAccounts.implicitDelegation",
    "iam.serviceAccounts.signBlob",
    "iam.serviceAccounts.signJwt",
)
JOB_MUTATION_PERMISSIONS: Final = (
    "run.jobs.delete",
    "run.jobs.setIamPolicy",
    "run.jobs.update",
)
SECRET_ACCESS_PERMISSIONS: Final = ("secretmanager.versions.access",)
SURFACE_PERMISSIONS: Final = MappingProxyType(
    {
        "authority_bucket": AUTHORITY_BUCKET_PERMISSIONS,
        "collector_job": JOB_MUTATION_PERMISSIONS,
        "collector_service_account": SERVICE_ACCOUNT_IMPERSONATION_PERMISSIONS,
        "authority_reader_service_account": (SERVICE_ACCOUNT_IMPERSONATION_PERMISSIONS),
        "session_secret": SECRET_ACCESS_PERMISSIONS,
    }
)

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE = re.compile(r"[a-z0-9.-]+/[a-z0-9._/-]+@sha256:[0-9a-f]{64}\Z")
_IMAGE_TAG = re.compile(r"[a-z0-9.-]+/[a-z0-9._/-]+:[A-Za-z0-9._-]+\Z")
_BUILD_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_SERVICE_ACCOUNT = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com\Z"
)
_PRINCIPAL = re.compile(r"(?:serviceAccount|user):[^\s]+\Z")
_JOB = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]\Z")
_SECRET = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,254}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")

_CREDENTIAL_KEYS: Final = frozenset(
    {
        "access_token",
        "authorization",
        "client_secret",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "password",
        "private_key",
        "refresh_token",
        "token",
    }
)


class Week1A5P0BProviderRealityError(RuntimeError):
    """The P0-B provider-reality fact gate failed closed."""


def _fail(message: str) -> None:
    raise Week1A5P0BProviderRealityError(message)


def _canonical_bytes(value: object) -> bytes:
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


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _seal(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} is already present")
    sealed = dict(value)
    sealed[field] = _canonical_sha(sealed)
    return sealed


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact(value: Mapping[str, object], fields: set[str], *, label: str) -> None:
    if set(value) != fields:
        _fail(
            f"{label} fields differ: missing={sorted(fields - set(value))} "
            f"unexpected={sorted(set(value) - fields)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _positive_decimal(value: object, *, label: str) -> str:
    if type(value) not in {str, int}:
        _fail(f"{label} must be a positive decimal")
    text = str(value)
    if not text.isdigit() or int(text) < 1 or text != str(int(text)):
        _fail(f"{label} must be a positive decimal")
    return text


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise Week1A5P0BProviderRealityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _reject_credential_material(value: object, *, label: str) -> None:
    """Refuse provider transcripts that could persist credential values."""

    if isinstance(value, Mapping):
        semantic_name = value.get("name")
        if (
            isinstance(semantic_name, str)
            and any(
                marker in re.sub(r"[^a-z0-9]+", "_", semantic_name.lower()).strip("_")
                for marker in _CREDENTIAL_KEYS
            )
            and any(field in value for field in ("value", "valueFrom", "value_from"))
        ):
            _fail(f"{label} contains forbidden credential material")
        for raw_key, child in value.items():
            key = re.sub(
                r"[^a-z0-9]+",
                "_",
                re.sub(r"(?<!^)(?=[A-Z])", "_", str(raw_key)).lower(),
            ).strip("_")
            if (
                key in _CREDENTIAL_KEYS
                or key.startswith("private_key")
                or key == "secret"
                and not isinstance(child, Mapping)
            ):
                _fail(f"{label} contains forbidden credential material")
            _reject_credential_material(child, label=label)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _reject_credential_material(child, label=label)


def _sorted_principals(value: object, *, label: str) -> list[str]:
    rows = [_string(item, label=label) for item in _sequence(value, label=label)]
    if rows != sorted(set(rows)):
        _fail(f"{label} must be unique and sorted")
    if any(_PRINCIPAL.fullmatch(item) is None for item in rows):
        _fail(f"{label} contains an unsupported or dynamic principal")
    return rows


def _validate_expected_access(value: object) -> dict[str, list[dict[str, object]]]:
    surfaces = _mapping(value, label="intent expected_effective_access")
    if set(surfaces) != set(SURFACE_PERMISSIONS):
        _fail("intent effective-access surfaces differ from the complete gate")
    retained: dict[str, list[dict[str, object]]] = {}
    for surface, permissions in SURFACE_PERMISSIONS.items():
        rows = _sequence(surfaces[surface], label=f"intent effective access {surface}")
        normalized: list[dict[str, object]] = []
        for ordinal, raw in enumerate(rows):
            row = _mapping(raw, label=f"intent {surface}[{ordinal}]")
            _exact(row, {"permission", "principals"}, label=f"intent {surface}")
            permission = _string(row["permission"], label="intent permission")
            normalized.append(
                {
                    "permission": permission,
                    "principals": _sorted_principals(
                        row["principals"], label=f"intent principals for {permission}"
                    ),
                }
            )
        if [row["permission"] for row in normalized] != list(permissions):
            _fail(f"intent {surface} permissions differ or are out of order")
        retained[surface] = normalized
    return retained


def validate_intent_v1(value: object) -> dict[str, object]:
    """Validate one independently reviewed, pre-contact P0-B intent."""

    row = _mapping(value, label="P0-B intent")
    _exact(
        row,
        {
            "schema_version",
            "created_at_utc",
            "project",
            "project_number",
            "organization",
            "region",
            "audit_principal",
            "source_commit",
            "collector_module_sha256",
            "build_id",
            "build_region",
            "source_archive",
            "image_tag",
            "image",
            "collector_job",
            "collector_service_account",
            "authority_reader_service_account",
            "session_secret",
            "contest_role",
            "locator_families",
            "expected_effective_access",
            "outcome_data_access_authorized",
            "cloud_mutation_authorized",
            "intent_sha256",
        },
        label="P0-B intent",
    )
    if row["schema_version"] != INTENT_SCHEMA:
        _fail("P0-B intent schema differs")
    claimed_sha = row.pop("intent_sha256")
    if type(claimed_sha) is not str or claimed_sha != _canonical_sha(row):
        _fail("P0-B intent hash differs")
    if row["project"] != PROJECT:
        _fail("P0-B intent project differs from the collector")
    row["project_number"] = _positive_decimal(
        row["project_number"], label="P0-B project number"
    )
    row["organization"] = _positive_decimal(
        row["organization"], label="P0-B organization"
    )
    region = _string(row["region"], label="P0-B region")
    if region != region.lower():
        _fail("P0-B region must be lowercase")
    row["created_at_utc"] = _timestamp(
        row["created_at_utc"], label="P0-B intent creation time"
    )
    row["audit_principal"] = _string(
        row["audit_principal"], label="P0-B audit principal"
    )
    if _PRINCIPAL.fullmatch(str(row["audit_principal"])) is None:
        _fail("P0-B audit principal is unsupported")
    source_commit = _string(row["source_commit"], label="P0-B source commit")
    if _COMMIT.fullmatch(source_commit) is None:
        _fail("P0-B source commit is not exact")
    module_sha = _string(
        row["collector_module_sha256"], label="P0-B collector module SHA"
    )
    if _SHA.fullmatch(module_sha) is None:
        _fail("P0-B collector module SHA is not exact")
    build_id = _string(row["build_id"], label="P0-B build ID")
    if _BUILD_ID.fullmatch(build_id) is None:
        _fail("P0-B build ID is not exact")
    if row["build_region"] != "global":
        _fail("P0-B build region must be global")

    source = _mapping(row["source_archive"], label="P0-B source archive")
    _exact(source, {"uri", "generation", "sha256", "bytes"}, label="source")
    uri = _string(source["uri"], label="P0-B source archive URI")
    if not uri.startswith(f"gs://{PROJECT}_cloudbuild/source/") or "#" in uri:
        _fail("P0-B source archive URI differs from the exact Cloud Build bucket")
    source["generation"] = _positive_decimal(
        source["generation"], label="P0-B source archive generation"
    )
    source_sha = _string(source["sha256"], label="P0-B source archive SHA")
    if _SHA.fullmatch(source_sha) is None:
        _fail("P0-B source archive SHA is not exact")
    if type(source["bytes"]) is not int or source["bytes"] < 1:
        _fail("P0-B source archive byte count is invalid")
    row["source_archive"] = source

    image_tag = _string(row["image_tag"], label="P0-B image tag")
    image = _string(row["image"], label="P0-B immutable image")
    if _IMAGE_TAG.fullmatch(image_tag) is None or _IMAGE.fullmatch(image) is None:
        _fail("P0-B image identity is malformed or mutable")
    if image.rsplit("@", 1)[0] != image_tag.rsplit(":", 1)[0]:
        _fail("P0-B image tag and digest name different repositories")

    job = _mapping(row["collector_job"], label="P0-B collector job")
    _exact(job, {"name", "uid", "generation"}, label="P0-B collector job")
    name = _string(job["name"], label="P0-B collector job name")
    uid = _string(job["uid"], label="P0-B collector job UID")
    if _JOB.fullmatch(name) is None or _UUID.fullmatch(uid) is None:
        _fail("P0-B collector job identity is malformed")
    job["generation"] = _positive_decimal(
        job["generation"], label="P0-B collector job generation"
    )
    row["collector_job"] = job

    for field in (
        "collector_service_account",
        "authority_reader_service_account",
    ):
        service_account = _string(row[field], label=f"P0-B {field}")
        if _SERVICE_ACCOUNT.fullmatch(
            service_account
        ) is None or not service_account.endswith(
            f"@{PROJECT}.iam.gserviceaccount.com"
        ):
            _fail(f"P0-B {field} is not dedicated to the exact project")
    if row["collector_service_account"] == row["authority_reader_service_account"]:
        _fail("P0-B collector and authority reader identities must be distinct")

    secret = _mapping(row["session_secret"], label="P0-B session secret")
    _exact(secret, {"name", "version", "volume_name"}, label="session secret")
    if _SECRET.fullmatch(_string(secret["name"], label="secret name")) is None:
        _fail("P0-B session secret name is invalid")
    secret["version"] = _positive_decimal(
        secret["version"], label="P0-B session secret version"
    )
    volume_name = _string(secret["volume_name"], label="session volume name")
    if _JOB.fullmatch(volume_name) is None:
        _fail("P0-B session volume name is invalid")
    row["session_secret"] = secret

    role = _string(row["contest_role"], label="P0-B contest role")
    if role not in capture.A5_ROLE_TABLE:
        _fail("P0-B contest role is outside exact A5")
    families: list[dict[str, object]] = []
    for ordinal, raw in enumerate(
        _sequence(row["locator_families"], label="P0-B locator families")
    ):
        family = _mapping(raw, label=f"locator family {ordinal}")
        _exact(
            family,
            {"scheme", "host", "port", "path_prefix"},
            label=f"locator family {ordinal}",
        )
        item = acquisition.LocatorFamily(
            scheme=_string(family["scheme"], label="locator scheme"),
            host=_string(family["host"], label="locator host"),
            port=family["port"] if type(family["port"]) is int else -1,
            path_prefix=_string(family["path_prefix"], label="locator path prefix"),
        )
        if (
            item.scheme != "https"
            or item.host != item.host.lower()
            or item.port != 443
            or not item.path_prefix.startswith("/")
            or item.path_prefix != item.path_prefix.strip()
        ):
            _fail("P0-B locator family differs from HTTPS/443 exact form")
        families.append(item.as_dict())
    if not families or families != sorted(
        {json.dumps(item, sort_keys=True): item for item in families}.values(),
        key=lambda item: (item["host"], item["path_prefix"]),
    ):
        _fail("P0-B locator families must be nonempty, unique, and sorted")
    row["locator_families"] = families
    row["expected_effective_access"] = _validate_expected_access(
        row["expected_effective_access"]
    )
    if row["outcome_data_access_authorized"] is not False:
        _fail("P0-B intent must not authorize outcome access")
    if row["cloud_mutation_authorized"] is not False:
        _fail("P0-B intent must not authorize cloud mutation")
    row["intent_sha256"] = claimed_sha
    return row


def plan_v1() -> dict[str, object]:
    """Render the inert operator contract without reading files or credentials."""

    body: dict[str, object] = {
        "schema_version": PLAN_SCHEMA,
        "mode": "no-contact-plan",
        "project": PROJECT,
        "authority_bucket": AUTHORITY_BUCKET,
        "session_state_path": str(SESSION_STATE_PATH),
        "session_profile": SESSION_PROFILE,
        "provider_contacted": False,
        "cloud_contacted": False,
        "cloud_mutation_authorized": False,
        "gcs_publication_authorized": False,
        "outcome_data_access_authorized": False,
        "activation_pin_change_authorized": False,
        "audit_requires": {
            "subcommand": "audit",
            "confirmation_phrase": CONFIRMATION_PHRASE,
            "canonical_precontact_intent": True,
            "create_once_evidence_directory": True,
            "create_once_receipt": True,
            "private_locator_file": True,
        },
        "read_only_provider_facts": [
            "project_ancestry",
            "authority_bucket_metadata_and_direct_policy",
            "complete_effective_mutation_access_analysis",
            "service_account_impersonation_analysis",
            "cloud_run_job_update_analysis_and_exact_spec",
            "fixed_secret_version_access_analysis_and_mount",
            "cloud_build_source_archive_and_artifact_registry_image",
            "one_active_entry_http_response_shape",
        ],
        "forbidden_operations": [
            "cloud_build_submit",
            "cloud_run_job_create_update_delete_or_execute",
            "iam_or_bucket_mutation",
            "gcs_object_publication",
            "live_pin_change",
            "provider_capture_or_authority_ledger_publication",
            "contest_entry_or_paid_action",
            "contest_detail_or_standings_read",
            "outcome_or_score_read",
            "legacy_v2_live_fallback",
        ],
        "effective_access_permissions": {
            key: list(value) for key, value in SURFACE_PERMISSIONS.items()
        },
    }
    body["plan_sha256"] = _canonical_sha(body)
    return body


class _FactPort(Protocol):
    def json(self, *, label: str, argv: Sequence[str]) -> object: ...

    def raw(self, *, label: str, argv: Sequence[str]) -> bytes: ...


@dataclass
class _RecordingGcloudPort:
    evidence_directory: Path

    def _write(self, label: str, raw: bytes) -> None:
        path = self.evidence_directory / f"{label}.json"
        try:
            with path.open("xb") as handle:
                handle.write(raw)
        except FileExistsError as exc:
            raise Week1A5P0BProviderRealityError(
                f"provider transcript already exists: {label}"
            ) from exc

    def json(self, *, label: str, argv: Sequence[str]) -> object:
        command = ["gcloud", *argv, "--format=json"]
        try:
            completed = subprocess.run(command, check=True, capture_output=True)
            value = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise Week1A5P0BProviderRealityError(
                f"read-only provider fact failed: {label} ({type(exc).__name__})"
            ) from exc
        _reject_credential_material(value, label=f"provider transcript {label}")
        self._write(label, _canonical_bytes(value))
        return value

    def raw(self, *, label: str, argv: Sequence[str]) -> bytes:
        command = ["gcloud", *argv]
        try:
            completed = subprocess.run(command, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise Week1A5P0BProviderRealityError(
                f"read-only provider bytes failed: {label} ({type(exc).__name__})"
            ) from exc
        projection = {
            "bytes": len(completed.stdout),
            "sha256": hashlib.sha256(completed.stdout).hexdigest(),
        }
        self._write(label, _canonical_bytes(projection))
        return completed.stdout


def _active_principal(value: object, *, expected: str) -> dict[str, object]:
    rows = _sequence(value, label="active gcloud accounts")
    active = []
    for raw in rows:
        row = _mapping(raw, label="gcloud account")
        if row.get("status") == "ACTIVE":
            active.append(_string(row.get("account"), label="active gcloud account"))
    expected_account = expected.split(":", 1)[1]
    if active != [expected_account]:
        _fail("active gcloud principal differs from the reviewed intent")
    return {"principal": expected, "one_active_account": True}


def _project_ancestry(
    value: object, *, project_number: str, organization: str
) -> list[dict[str, str]]:
    rows = _sequence(value, label="project ancestry")
    retained: list[dict[str, str]] = []
    for raw in rows:
        row = _mapping(raw, label="project ancestor")
        ancestor_type = _string(row.get("type"), label="ancestor type").lower()
        ancestor_id = _positive_decimal(row.get("id"), label="ancestor ID")
        if ancestor_type not in {"project", "folder", "organization"}:
            _fail("project ancestry contains an unknown resource type")
        retained.append({"type": ancestor_type, "id": ancestor_id})
    if (
        sum(row == {"type": "project", "id": project_number} for row in retained) != 1
        or sum(row == {"type": "organization", "id": organization} for row in retained)
        != 1
        or retained[-1] != {"type": "organization", "id": organization}
    ):
        _fail("project ancestry differs from the exact project/organization")
    return retained


def _bucket_metadata(value: object, *, project_number: str) -> dict[str, object]:
    row = _mapping(value, label="authority bucket metadata")
    if row.get("name") != AUTHORITY_BUCKET:
        _fail("authority bucket name differs")
    observed_project = row.get("projectNumber", row.get("project_number"))
    if (
        _positive_decimal(observed_project, label="bucket project number")
        != project_number
    ):
        _fail("authority bucket project differs")
    metageneration = _positive_decimal(
        row.get("metageneration"), label="authority bucket metageneration"
    )
    iam = _mapping(row.get("iamConfiguration"), label="bucket IAM configuration")
    uniform = _mapping(
        iam.get("uniformBucketLevelAccess"), label="uniform bucket access"
    )
    retention = _mapping(row.get("retentionPolicy"), label="bucket retention")
    versioning = _mapping(row.get("versioning"), label="bucket versioning")
    if (
        uniform.get("enabled") is not True
        or iam.get("publicAccessPrevention") != "enforced"
        or retention.get("isLocked") is not True
        or versioning.get("enabled") is not True
    ):
        _fail("authority bucket governance is not fully locked and private")
    seconds = retention.get("retentionPeriod")
    if type(seconds) is str and seconds.isdigit():
        seconds = int(seconds)
    if type(seconds) is not int or seconds < 604_800:
        _fail("authority bucket retention is shorter than seven days")
    return {
        "name": AUTHORITY_BUCKET,
        "project_number": project_number,
        "metageneration": metageneration,
        "retention_seconds": seconds,
        "retention_locked": True,
        "versioning_enabled": True,
        "uniform_bucket_level_access": True,
        "public_access_prevention": "enforced",
        "provider_response_sha256": _canonical_sha(row),
    }


def _direct_policy(
    value: object,
    *,
    collector: str,
    reader: str,
    metageneration: str,
    retention_seconds: int,
) -> dict[str, object]:
    row = _mapping(value, label="authority bucket direct IAM policy")
    policy_version = row.get("version", 1)
    if type(policy_version) is not int or policy_version not in {1, 3}:
        _fail("authority bucket IAM policy version differs")
    etag = _string(row.get("etag"), label="authority bucket IAM etag")
    bindings = acquisition._normalize_iam_bindings(
        row.get("bindings", []), label="authority bucket IAM bindings"
    )
    mutators = sorted(
        {
            member
            for binding in bindings
            if binding["role"] in acquisition._DIRECT_OBJECT_MUTATOR_ROLES
            for member in binding["members"]
        }
    )
    viewers = sorted(
        {
            member
            for binding in bindings
            if binding["role"] in acquisition._DIRECT_OBJECT_VIEWER_ROLES
            for member in binding["members"]
        }
    )
    public = sorted(
        {
            member
            for binding in bindings
            for member in binding["members"]
            if member in {"allUsers", "allAuthenticatedUsers"}
        }
    )
    governance = acquisition._validate_governance(
        {
            "authority_bucket_metageneration": metageneration,
            "retention_seconds": retention_seconds,
            "retention_locked": True,
            "versioning_enabled": True,
            "uniform_bucket_level_access": True,
            "iam_policy_version": policy_version,
            "iam_policy_etag_base64": etag,
            "iam_policy_sha256": acquisition._iam_policy_sha256(
                version=policy_version,
                etag_base64=etag,
                bindings=bindings,
            ),
            "iam_policy_bindings": list(bindings),
            "object_mutator_members": mutators,
            "object_viewer_members": viewers,
            "public_members": public,
        },
        label="P0-B direct authority governance",
    )
    if governance.object_mutator_members != (f"serviceAccount:{collector}",):
        _fail("authority bucket direct mutator differs from the sole collector")
    required_viewers = {
        f"serviceAccount:{collector}",
        f"serviceAccount:{reader}",
    }
    if set(governance.object_viewer_members) != required_viewers:
        _fail("authority bucket direct viewers differ from collector plus reader")
    result = governance.as_dict()
    result["provider_response_sha256"] = _canonical_sha(row)
    return result


def _has_errors(value: Mapping[str, object]) -> bool:
    return any(
        "error"
        in re.sub(
            r"[^a-z0-9]+",
            "_",
            re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower(),
        )
        and child not in (None, [], {})
        for key, child in value.items()
    )


def _asset_effective_access(
    value: object,
    *,
    scope: str,
    target: str,
    allowed_attachments: frozenset[str],
    options: Mapping[str, bool],
    permissions: Sequence[str],
    expected: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Validate one complete identity-by-permission Cloud Asset analysis."""

    response = _mapping(value, label="Cloud Asset response")
    main = _mapping(response.get("mainAnalysis"), label="Cloud Asset main analysis")
    expected_query = {
        "accessSelector": {"permissions": list(permissions)},
        "resourceSelector": {"fullResourceName": target},
        "options": dict(options),
        "scope": scope,
    }
    if (
        response.get("fullyExplored") is not True
        or main.get("fullyExplored") is not True
        or response.get("nonCriticalErrors", []) != []
        or main.get("nonCriticalErrors", []) != []
        or main.get("analysisQuery") != expected_query
        or _has_errors(response)
        or _has_errors(main)
    ):
        _fail("Cloud Asset analysis is incomplete, partial, or for another query")
    identities_by_permission: dict[str, set[str]] = {
        permission: set() for permission in permissions
    }
    binding_provenance: list[dict[str, object]] = []
    for raw_result in _sequence(
        main.get("analysisResults", []), label="Cloud Asset analysis results"
    ):
        result = _mapping(raw_result, label="Cloud Asset result")
        if (
            result.get("fullyExplored") is not True
            or result.get("nonCriticalErrors", []) != []
            or _has_errors(result)
        ):
            _fail("Cloud Asset result is incomplete or partial")
        identity_list = _mapping(
            result.get("identityList"), label="Cloud Asset identity list"
        )
        if identity_list.get("groupEdges", []) != []:
            _fail("Cloud Asset authority depends on mutable group membership")
        identities = sorted(
            {
                _string(
                    _mapping(item, label="Cloud Asset identity").get("name"),
                    label="Cloud Asset identity name",
                )
                for item in _sequence(
                    identity_list.get("identities"), label="Cloud Asset identities"
                )
            }
        )
        if not identities or any(
            _PRINCIPAL.fullmatch(item) is None for item in identities
        ):
            _fail("Cloud Asset returned an unsupported effective principal")
        attached = _string(
            result.get("attachedResourceFullName"),
            label="Cloud Asset attached resource",
        )
        if attached not in allowed_attachments:
            _fail("Cloud Asset binding is attached outside the exact ancestry")
        binding = _mapping(result.get("iamBinding"), label="Cloud Asset IAM binding")
        if set(binding) not in (
            {"role", "members"},
            {"role", "members", "condition"},
        ):
            _fail("Cloud Asset IAM binding shape differs")
        role = _string(binding["role"], label="Cloud Asset IAM binding role")
        members = sorted(
            {
                _string(member, label="Cloud Asset IAM binding member")
                for member in _sequence(
                    binding["members"], label="Cloud Asset IAM binding members"
                )
            }
        )
        if members != identities:
            _fail("Cloud Asset binding members differ from expanded identities")
        condition = (
            _mapping(binding["condition"], label="Cloud Asset IAM condition")
            if "condition" in binding
            else None
        )
        observed_permissions: set[str] = set()
        condition_evaluations: list[dict[str, object]] = []
        for raw_acl in _sequence(
            result.get("accessControlLists"), label="Cloud Asset access lists"
        ):
            acl = _mapping(raw_acl, label="Cloud Asset access list")
            if "conditionEvaluation" in acl:
                evaluation = _mapping(
                    acl["conditionEvaluation"],
                    label="Cloud Asset condition evaluation",
                )
                if evaluation.get("evaluationValue") not in {
                    "TRUE",
                    "FALSE",
                    "CONDITIONAL",
                }:
                    _fail("Cloud Asset condition evaluation differs")
                condition_evaluations.append(evaluation)
            resources = {
                _string(
                    _mapping(resource, label="Cloud Asset resource").get(
                        "fullResourceName"
                    ),
                    label="Cloud Asset resource name",
                )
                for resource in _sequence(
                    acl.get("resources"), label="Cloud Asset resources"
                )
            }
            if target not in resources:
                _fail("Cloud Asset effective resource omits the exact target")
            for raw_access in _sequence(
                acl.get("accesses"), label="Cloud Asset accesses"
            ):
                access = _mapping(raw_access, label="Cloud Asset access")
                if set(access) == {"role"}:
                    _string(access["role"], label="Cloud Asset expanded role")
                elif set(access) == {"permission"}:
                    permission = _string(
                        access["permission"], label="Cloud Asset permission"
                    )
                    if permission not in identities_by_permission:
                        _fail(
                            "Cloud Asset returned an unrequested effective permission"
                        )
                    observed_permissions.add(permission)
                else:
                    _fail("Cloud Asset returned an unknown access shape")
        if not observed_permissions:
            _fail("Cloud Asset result has no expanded requested permission")
        if (condition is None) != (not condition_evaluations):
            _fail("Cloud Asset binding condition/evaluation pair differs")
        for permission in observed_permissions:
            identities_by_permission[permission].update(identities)
        binding_provenance.append(
            {
                "attached_resource": attached,
                "role": role,
                "principals": identities,
                "permissions": sorted(observed_permissions),
                "inherited": attached != target,
                "condition": condition,
                "condition_evaluations": condition_evaluations,
            }
        )
    normalized = [
        {
            "permission": permission,
            "principals": sorted(identities_by_permission[permission]),
        }
        for permission in permissions
    ]
    if normalized != [dict(item) for item in expected]:
        _fail("effective authority differs from the independently reviewed intent")
    return {
        "scope": scope,
        "target": target,
        "principals_by_permission": normalized,
        "binding_provenance": sorted(
            binding_provenance, key=lambda item: _canonical_bytes(item)
        ),
        "fully_explored": True,
        "provider_response_sha256": _canonical_sha(response),
    }


def _policy_projection(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    bindings = row.get("bindings", [])
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes)):
        _fail(f"{label} bindings are malformed")
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(bindings):
        binding = _mapping(raw, label=f"{label} binding {ordinal}")
        if set(binding) not in ({"role", "members"}, {"role", "members", "condition"}):
            _fail(f"{label} binding shape differs")
        item: dict[str, object] = {
            "role": _string(binding["role"], label=f"{label} role"),
            "members": sorted(
                _string(member, label=f"{label} member")
                for member in _sequence(binding["members"], label=f"{label} members")
            ),
        }
        if "condition" in binding:
            item["condition"] = _mapping(
                binding["condition"], label=f"{label} condition"
            )
        normalized.append(item)
    normalized.sort(key=lambda item: _canonical_bytes(item))
    return {
        "version": row.get("version", 1),
        "etag": row.get("etag"),
        "bindings": normalized,
        "provider_response_sha256": _canonical_sha(row),
    }


def _job_projection(
    value: object, *, intent: Mapping[str, object]
) -> dict[str, object]:
    row = _mapping(value, label="collector Cloud Run job")
    metadata = _mapping(row.get("metadata"), label="collector job metadata")
    expected_job = _mapping(intent["collector_job"], label="intent collector job")
    if (
        metadata.get("name") != expected_job["name"]
        or metadata.get("uid") != expected_job["uid"]
        or str(metadata.get("generation")) != expected_job["generation"]
    ):
        _fail("collector job identity/generation differs from the intent")
    status = _mapping(row.get("status"), label="collector job status")
    if str(status.get("observedGeneration")) != expected_job["generation"]:
        _fail("collector job controller has not observed the exact generation")
    ready = [
        item
        for item in _sequence(status.get("conditions", []), label="job conditions")
        if isinstance(item, Mapping)
        and item.get("type") == "Ready"
        and item.get("status") == "True"
    ]
    if len(ready) != 1:
        _fail("collector job exact generation is not Ready")
    spec = _mapping(row.get("spec"), label="collector job spec")
    outer = _mapping(spec.get("template"), label="collector job outer template")
    outer_spec = _mapping(outer.get("spec"), label="collector job outer spec")
    task = _mapping(
        _mapping(outer_spec.get("template"), label="collector task template").get(
            "spec"
        ),
        label="collector task spec",
    )
    if outer_spec.get("taskCount") != 1 or outer_spec.get("parallelism") != 1:
        _fail("collector job must remain one-task/one-parallelism")
    if task.get("maxRetries") != 0:
        _fail("collector job retries must remain zero")
    if task.get("serviceAccountName") != intent["collector_service_account"]:
        _fail("collector job service account differs from the managed identity")
    containers = _sequence(task.get("containers"), label="collector job containers")
    if len(containers) != 1:
        _fail("collector job must have exactly one container")
    container = _mapping(containers[0], label="collector job container")
    if container.get("image") != intent["image"]:
        _fail("collector job image is not the exact immutable image")
    env_rows = _sequence(container.get("env", []), label="collector job environment")
    env: dict[str, str] = {}
    for raw_env in env_rows:
        item = _mapping(raw_env, label="collector job environment entry")
        if set(item) != {"name", "value"}:
            _fail("collector job contains a secret or unknown environment binding")
        name = _string(item["name"], label="collector environment name")
        value = _string(item["value"], label="collector environment value")
        if name in env:
            _fail("collector job repeats an environment variable")
        env[name] = value
    digest = str(intent["image"]).rsplit("@", 1)[1]
    expected_env = {
        "CODE_SHA": str(intent["source_commit"]),
        "COLLECTOR_IMAGE_DIGEST": digest,
    }
    if env != expected_env:
        _fail("collector job environment differs from exact source/image identity")

    secret = _mapping(intent["session_secret"], label="intent session secret")
    volumes = _sequence(task.get("volumes"), label="collector job volumes")
    mounts = _sequence(container.get("volumeMounts"), label="collector volume mounts")
    if len(volumes) != 1 or len(mounts) != 1:
        _fail("collector job must have one exact session-secret volume and mount")
    volume = _mapping(volumes[0], label="collector secret volume")
    mount = _mapping(mounts[0], label="collector secret mount")
    provider_secret = _mapping(volume.get("secret"), label="collector volume secret")
    items = _sequence(provider_secret.get("items"), label="collector secret items")
    expected_item = {
        "key": secret["version"],
        "path": SESSION_STATE_PATH.name,
    }
    if (
        volume.get("name") != secret["volume_name"]
        or provider_secret.get("secretName") != secret["name"]
        or items != [expected_item]
        or mount
        != {
            "name": secret["volume_name"],
            "mountPath": str(SESSION_STATE_PATH.parent),
        }
    ):
        _fail("collector job secret/version/path mount differs from the intent")
    return {
        "name": expected_job["name"],
        "uid": expected_job["uid"],
        "generation": expected_job["generation"],
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "service_account": intent["collector_service_account"],
        "image": intent["image"],
        "environment": expected_env,
        "session_secret": dict(secret),
        "session_state_path": str(SESSION_STATE_PATH),
        "provider_spec_sha256": _canonical_sha(row),
    }


def _source_object_metadata(
    value: object, *, source: Mapping[str, object]
) -> dict[str, object]:
    row = _mapping(value, label="Cloud Build source object metadata")
    bucket, name = str(source["uri"])[5:].split("/", 1)
    if (
        row.get("bucket") != bucket
        or row.get("name") != name
        or str(row.get("generation")) != source["generation"]
        or str(row.get("size")) != str(source["bytes"])
        or str(row.get("metageneration")) != "1"
    ):
        _fail("Cloud Build source object metadata differs from the exact archive")
    return {
        "uri": source["uri"],
        "generation": source["generation"],
        "bytes": source["bytes"],
        "metageneration": "1",
        "provider_response_sha256": _canonical_sha(row),
    }


def _build_projection(
    value: object, *, intent: Mapping[str, object]
) -> dict[str, object]:
    row = _mapping(value, label="Cloud Build metadata")
    source = _mapping(intent["source_archive"], label="intent source archive")
    bucket, name = str(source["uri"])[5:].split("/", 1)
    expected_storage_source = {
        "bucket": bucket,
        "object": name,
        "generation": source["generation"],
    }
    source_body = _mapping(row.get("source"), label="Cloud Build source")
    provenance = _mapping(
        row.get("sourceProvenance"), label="Cloud Build source provenance"
    )
    if (
        row.get("id") != intent["build_id"]
        or row.get("status") != "SUCCESS"
        or source_body.get("storageSource") != expected_storage_source
        or provenance.get("resolvedStorageSource") != expected_storage_source
    ):
        _fail("Cloud Build identity/status/source provenance differs")
    substitutions = _mapping(
        row.get("substitutions"), label="Cloud Build substitutions"
    )
    if (
        substitutions.get("_CODE_SHA") != intent["source_commit"]
        or substitutions.get("_IMAGE") != intent["image_tag"]
    ):
        _fail("Cloud Build source/image substitutions differ")
    images = _sequence(
        _mapping(row.get("results"), label="Cloud Build results").get("images"),
        label="Cloud Build result images",
    )
    expected_digest = str(intent["image"]).rsplit("@", 1)[1]
    matching = [
        image
        for image in images
        if isinstance(image, Mapping)
        and image.get("name") == intent["image_tag"]
        and image.get("digest") == expected_digest
    ]
    if len(matching) != 1:
        _fail("Cloud Build result does not bind the exact image digest")
    return {
        "build_id": intent["build_id"],
        "build_region": intent["build_region"],
        "status": "SUCCESS",
        "source_commit": intent["source_commit"],
        "source_archive": dict(source),
        "image_tag": intent["image_tag"],
        "image": intent["image"],
        "provider_response_sha256": _canonical_sha(row),
    }


def _image_projection(
    value: object, *, intent: Mapping[str, object]
) -> dict[str, object]:
    row = _mapping(value, label="Artifact Registry image metadata")
    summary = _mapping(row.get("image_summary"), label="Artifact Registry summary")
    digest = str(intent["image"]).rsplit("@", 1)[1]
    if (
        summary.get("digest") != digest
        or summary.get("fully_qualified_digest") != intent["image"]
    ):
        _fail("Artifact Registry metadata differs from exact image digest")
    return {
        "image": intent["image"],
        "digest": digest,
        "provider_response_sha256": _canonical_sha(row),
    }


def _secret_version(
    value: object, *, intent: Mapping[str, object]
) -> dict[str, object]:
    row = _mapping(value, label="session secret version")
    secret = _mapping(intent["session_secret"], label="intent session secret")
    expected_name = (
        f"projects/{intent['project_number']}/secrets/{secret['name']}"
        f"/versions/{secret['version']}"
    )
    actual_name = row.get("name")
    accepted_names = {
        expected_name,
        expected_name.replace(
            f"projects/{intent['project_number']}", f"projects/{PROJECT}"
        ),
    }
    if actual_name not in accepted_names or row.get("state") != "ENABLED":
        _fail("session storage-state secret version is not exact and enabled")
    return {
        "name": secret["name"],
        "version": secret["version"],
        "state": "ENABLED",
        "provider_resource_name": actual_name,
        "provider_response_sha256": _canonical_sha(row),
    }


def _asset_target(surface: str, intent: Mapping[str, object]) -> str:
    project_number = intent["project_number"]
    if surface == "authority_bucket":
        return f"//storage.googleapis.com/{AUTHORITY_BUCKET}"
    if surface == "collector_job":
        job = _mapping(intent["collector_job"], label="intent collector job")
        return (
            f"//run.googleapis.com/projects/{project_number}/locations/"
            f"{intent['region']}/jobs/{job['name']}"
        )
    if surface == "collector_service_account":
        account = intent["collector_service_account"]
        return f"//iam.googleapis.com/projects/{PROJECT}/serviceAccounts/{account}"
    if surface == "authority_reader_service_account":
        account = intent["authority_reader_service_account"]
        return f"//iam.googleapis.com/projects/{PROJECT}/serviceAccounts/{account}"
    if surface == "session_secret":
        secret = _mapping(intent["session_secret"], label="intent session secret")
        return (
            f"//secretmanager.googleapis.com/projects/{project_number}/secrets/"
            f"{secret['name']}"
        )
    raise AssertionError(surface)


def _asset_argv(
    *,
    organization: str,
    target: str,
    permissions: Sequence[str],
    analyze_service_account_impersonation: bool,
) -> list[str]:
    argv = [
        "asset",
        "analyze-iam-policy",
        f"--organization={organization}",
        f"--full-resource-name={target}",
        f"--permissions={','.join(permissions)}",
        "--expand-groups",
        "--expand-roles",
        "--expand-resources",
        "--show-response",
        "--output-resource-edges",
        "--output-group-edges",
    ]
    if analyze_service_account_impersonation:
        argv.append("--analyze-service-account-impersonation")
    return argv


def _effective_access_set(
    port: _FactPort,
    *,
    intent: Mapping[str, object],
    ancestry: Sequence[Mapping[str, str]],
    pass_name: str,
) -> dict[str, object]:
    scope = f"organizations/{intent['organization']}"
    prefixes = {
        "project": "//cloudresourcemanager.googleapis.com/projects/",
        "folder": "//cloudresourcemanager.googleapis.com/folders/",
        "organization": "//cloudresourcemanager.googleapis.com/organizations/",
    }
    allowed_attachments = frozenset(
        prefixes[item["type"]] + item["id"] for item in ancestry
    )
    allowed_attachments |= {f"//cloudresourcemanager.googleapis.com/projects/{PROJECT}"}
    expected = _mapping(
        intent["expected_effective_access"], label="expected effective access"
    )
    result: dict[str, object] = {}
    for surface, permissions in SURFACE_PERMISSIONS.items():
        target = _asset_target(surface, intent)
        options = _asset_options(surface)
        observed = port.json(
            label=f"asset-{surface}-{pass_name}",
            argv=_asset_argv(
                organization=str(intent["organization"]),
                target=target,
                permissions=permissions,
                analyze_service_account_impersonation=bool(
                    options.get("analyzeServiceAccountImpersonation")
                ),
            ),
        )
        result[surface] = _asset_effective_access(
            observed,
            scope=scope,
            target=target,
            allowed_attachments=allowed_attachments | {target},
            options=options,
            permissions=permissions,
            expected=_sequence(expected[surface], label=f"expected {surface}"),
        )
    return result


def _assert_all_pins_absent() -> None:
    values = {
        name: value
        for name, value in vars(live_pins).items()
        if name.startswith("PINNED_")
    }
    values["PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR"] = (
        capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR
    )
    if not values or any(value is not None for value in values.values()):
        _fail("P0-B fact audit requires every activation/live pin to remain absent")


def _private_locator(path: Path, *, families: Sequence[Mapping[str, object]]) -> str:
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            _fail("acceptance locator file must be a private regular file")
        locator = path.read_text(encoding="utf-8").strip()
    except Week1A5P0BProviderRealityError:
        raise
    except (OSError, UnicodeError) as exc:
        raise Week1A5P0BProviderRealityError(
            "private acceptance locator file is unavailable"
        ) from exc
    canonical = acquisition._canonical_url(locator, label="P0-B acceptance locator")
    allowed = tuple(
        acquisition.LocatorFamily(
            str(item["scheme"]),
            str(item["host"]),
            str(item["path_prefix"]),
            int(item["port"]),
        )
        for item in families
    )
    if not any(family.accepts(canonical) for family in allowed):
        _fail("acceptance locator is outside the pre-reviewed family set")
    return canonical


def _response_shape(raw: bytes, *, contest_role: str) -> dict[str, object]:
    """Retain structural CSV facts only; never row values or provider bytes."""

    inspection = capture.inspect_acceptance_provider_bytes_v1(
        raw, contest_role=contest_role
    )
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    except UnicodeDecodeError as exc:  # parser above normally closes this
        raise Week1A5P0BProviderRealityError(
            "active-entry response is not UTF-8 CSV"
        ) from exc
    metadata_header = ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if [cell.strip().lstrip("\ufeff") for cell in row[:4]] == metadata_header
        ),
        None,
    )
    if header_index is None:
        _fail("active-entry response omits the exact DKEntries header")
    header = [cell.strip() for cell in rows[header_index]]
    widths = sorted({len(row) for row in rows[header_index:] if any(row)})
    return {
        "schema_version": inspection["schema_version"],
        "source_profile": inspection["source_profile"],
        "contest_role": inspection["contest_role"],
        "contest_id": inspection["contest_id"],
        "encoding": "utf-8-sig",
        "header": header,
        "header_sha256": _canonical_sha(header),
        "header_ordinal": header_index,
        "nonempty_row_widths": widths,
        "entry_count": inspection["entry_count"],
        "unique_entry_count": inspection["unique_entry_count"],
        "all_rosters_have_nine_unique_draftables": inspection[
            "all_rosters_have_nine_unique_draftables"
        ],
        "raw_sha256": inspection["raw_sha256"],
        "raw_bytes": inspection["raw_bytes"],
        "entry_projection_sha256": inspection["entry_projection_sha256"],
        "body_retained": False,
        "row_values_retained": False,
        "writes_performed": False,
    }


def _transport_probe(
    *,
    intent: Mapping[str, object],
    locator: str,
    transport_factory: Callable[..., object] | None = None,
) -> dict[str, object]:
    families = tuple(
        acquisition.LocatorFamily(
            str(item["scheme"]),
            str(item["host"]),
            str(item["path_prefix"]),
            int(item["port"]),
        )
        for item in _sequence(intent["locator_families"], label="locator families")
        if isinstance(item, Mapping)
    )
    factory = transport_factory or acquisition._RequestsSessionTransport
    transport = factory(
        storage_state_path=SESSION_STATE_PATH,
        session_profile=SESSION_PROFILE,
        locator_families=families,
    )
    perform = getattr(transport, "perform", None)
    if not callable(perform):
        _fail("P0-B transport factory did not return the collector transport")
    event = perform(method="GET", locator=locator)
    rule = acquisition.AcquisitionRule(
        profile=ACCEPTANCE_PROFILE,
        method="GET",
        request_locator_kind="reviewed-p0b-private-locator-file",
        media_type="text/csv",
        disposition="attachment-csv",
        effective_locator_families=families,
    )
    normalized = acquisition._normalize_transport_event(
        event,
        rule=rule,
        request_locator=locator,
        policy=SimpleNamespace(session_profile=SESSION_PROFILE),
    )
    raw = getattr(event, "body", None)
    if not isinstance(raw, bytes):
        _fail("P0-B transport response body differs from exact collector type")
    return {
        "acquisition_profile": ACCEPTANCE_PROFILE,
        "capture_v3_schema": capture_v3.ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA,
        "transport_event": normalized,
        "response_shape": _response_shape(
            raw, contest_role=str(intent["contest_role"])
        ),
        "provider_bytes_published": False,
        "acquisition_receipt_published": False,
        "authority_ledger_published": False,
        "legacy_v2_live_fallback_used": False,
        "outcome_data_accessed": False,
    }


def _pre_or_post_facts(
    port: _FactPort,
    *,
    intent: Mapping[str, object],
    ancestry: Sequence[Mapping[str, str]],
    pass_name: str,
) -> dict[str, object]:
    job = _mapping(intent["collector_job"], label="intent collector job")
    secret = _mapping(intent["session_secret"], label="intent session secret")
    bucket_value = port.json(
        label=f"authority-bucket-{pass_name}",
        argv=["storage", "buckets", "describe", f"gs://{AUTHORITY_BUCKET}", "--raw"],
    )
    bucket = _bucket_metadata(
        bucket_value, project_number=str(intent["project_number"])
    )
    direct = _direct_policy(
        port.json(
            label=f"authority-bucket-policy-{pass_name}",
            argv=[
                "storage",
                "buckets",
                "get-iam-policy",
                f"gs://{AUTHORITY_BUCKET}",
            ],
        ),
        collector=str(intent["collector_service_account"]),
        reader=str(intent["authority_reader_service_account"]),
        metageneration=str(bucket["metageneration"]),
        retention_seconds=int(bucket["retention_seconds"]),
    )
    job_value = port.json(
        label=f"collector-job-{pass_name}",
        argv=[
            "run",
            "jobs",
            "describe",
            str(job["name"]),
            "--project",
            PROJECT,
            "--region",
            str(intent["region"]),
        ],
    )
    service_policies = {
        "collector": _policy_projection(
            port.json(
                label=f"collector-service-account-policy-{pass_name}",
                argv=[
                    "iam",
                    "service-accounts",
                    "get-iam-policy",
                    str(intent["collector_service_account"]),
                    "--project",
                    PROJECT,
                ],
            ),
            label="collector service-account direct policy",
        ),
        "authority_reader": _policy_projection(
            port.json(
                label=f"authority-reader-service-account-policy-{pass_name}",
                argv=[
                    "iam",
                    "service-accounts",
                    "get-iam-policy",
                    str(intent["authority_reader_service_account"]),
                    "--project",
                    PROJECT,
                ],
            ),
            label="authority-reader service-account direct policy",
        ),
    }
    job_policy = _policy_projection(
        port.json(
            label=f"collector-job-policy-{pass_name}",
            argv=[
                "run",
                "jobs",
                "get-iam-policy",
                str(job["name"]),
                "--project",
                PROJECT,
                "--region",
                str(intent["region"]),
            ],
        ),
        label="collector job direct policy",
    )
    secret_value = port.json(
        label=f"session-secret-version-{pass_name}",
        argv=[
            "secrets",
            "versions",
            "describe",
            str(secret["version"]),
            f"--secret={secret['name']}",
            "--project",
            PROJECT,
        ],
    )
    secret_policy = _policy_projection(
        port.json(
            label=f"session-secret-policy-{pass_name}",
            argv=[
                "secrets",
                "get-iam-policy",
                str(secret["name"]),
                "--project",
                PROJECT,
            ],
        ),
        label="session secret direct policy",
    )
    return {
        "authority_bucket": bucket,
        "authority_bucket_direct_policy": direct,
        "collector_job": _job_projection(job_value, intent=intent),
        "service_account_direct_policies": service_policies,
        "collector_job_direct_policy": job_policy,
        "session_secret_version": _secret_version(secret_value, intent=intent),
        "session_secret_direct_policy": secret_policy,
        "effective_access": _effective_access_set(
            port, intent=intent, ancestry=ancestry, pass_name=pass_name
        ),
    }


def _release_facts(
    port: _FactPort, *, intent: Mapping[str, object]
) -> dict[str, object]:
    source = _mapping(intent["source_archive"], label="intent source archive")
    exact_source = f"{source['uri']}#{source['generation']}"
    metadata = _source_object_metadata(
        port.json(
            label="source-archive-metadata",
            argv=["storage", "objects", "describe", exact_source, "--raw"],
        ),
        source=source,
    )
    archive = port.raw(
        label="source-archive-content-identity",
        argv=["storage", "cat", exact_source],
    )
    if (
        len(archive) != source["bytes"]
        or hashlib.sha256(archive).hexdigest() != source["sha256"]
    ):
        _fail("Cloud Build source archive bytes differ from exact intent")
    build = _build_projection(
        port.json(
            label="cloud-build",
            argv=[
                "builds",
                "describe",
                str(intent["build_id"]),
                "--project",
                PROJECT,
                "--region",
                str(intent["build_region"]),
            ],
        ),
        intent=intent,
    )
    image = _image_projection(
        port.json(
            label="artifact-registry-image",
            argv=[
                "artifacts",
                "docker",
                "images",
                "describe",
                str(intent["image"]),
            ],
        ),
        intent=intent,
    )
    return {
        "source_archive_metadata": metadata,
        "source_archive_content_identity": {
            "uri": source["uri"],
            "generation": source["generation"],
            "bytes": len(archive),
            "sha256": hashlib.sha256(archive).hexdigest(),
        },
        "build": build,
        "artifact_registry_image": image,
    }


def audit_provider_reality_v1(
    *,
    intent: object,
    acceptance_locator: str,
    fact_port: _FactPort,
    transport_factory: Callable[..., object] | None = None,
    observed_at_utc: str | None = None,
) -> dict[str, object]:
    """Collect one provider-real fact bundle through only read-only surfaces."""

    retained = validate_intent_v1(intent)
    _assert_all_pins_absent()
    if acquisition._module_sha256() != retained["collector_module_sha256"]:
        _fail("accepted collector module differs from the reviewed intent")
    canonical_locator = acquisition._canonical_url(
        acceptance_locator, label="P0-B acceptance locator"
    )
    families = _sequence(retained["locator_families"], label="locator families")
    if not any(
        acquisition.LocatorFamily(
            str(item["scheme"]),
            str(item["host"]),
            str(item["path_prefix"]),
            int(item["port"]),
        ).accepts(canonical_locator)
        for item in families
        if isinstance(item, Mapping)
    ):
        _fail("acceptance locator is outside the pre-reviewed family set")

    principal = _active_principal(
        fact_port.json(
            label="active-gcloud-principal",
            argv=["auth", "list", "--filter=status:ACTIVE"],
        ),
        expected=str(retained["audit_principal"]),
    )
    ancestry = _project_ancestry(
        fact_port.json(
            label="project-ancestry",
            argv=["projects", "get-ancestors", PROJECT],
        ),
        project_number=str(retained["project_number"]),
        organization=str(retained["organization"]),
    )
    release = _release_facts(fact_port, intent=retained)
    before = _pre_or_post_facts(
        fact_port, intent=retained, ancestry=ancestry, pass_name="before"
    )
    transport = _transport_probe(
        intent=retained,
        locator=canonical_locator,
        transport_factory=transport_factory,
    )
    after = _pre_or_post_facts(
        fact_port, intent=retained, ancestry=ancestry, pass_name="after"
    )
    if before != after:
        _fail("provider authority/runtime facts changed during the transport probe")
    observed = _timestamp(
        observed_at_utc or datetime.now(UTC).isoformat(),
        label="P0-B audit observation time",
    )
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "observed_at_utc": observed,
        "intent_sha256": retained["intent_sha256"],
        "audit_principal": principal,
        "project_ancestry": ancestry,
        "release_identity": release,
        "provider_authority_and_runtime": before,
        "transport_probe": transport,
        "provider_facts_stable_across_probe": True,
        "provider_calls_read_only": True,
        "cloud_mutation_performed": False,
        "cloud_run_job_executed": False,
        "gcs_object_published": False,
        "activation_pins_changed": False,
        "provider_capture_published": False,
        "authority_ledger_published": False,
        "paid_action_performed": False,
        "contest_detail_or_standings_read": False,
        "outcome_data_accessed": False,
        "legacy_v2_live_fallback_used": False,
        "release_gate": "HOLD_FOR_INDEPENDENT_REVIEW_AND_PIN_ONLY_SUCCESSOR",
    }
    return _seal(body, field="receipt_sha256")


def _read_canonical_intent(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise Week1A5P0BProviderRealityError(
            "P0-B intent is unavailable or invalid JSON"
        ) from exc
    if raw != _canonical_bytes(value):
        _fail("P0-B intent is not canonical create-once JSON")
    return validate_intent_v1(value)


def _write_create_once(path: Path, value: object, *, label: str) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(_canonical_bytes(value))
    except FileExistsError as exc:
        raise Week1A5P0BProviderRealityError(f"refusing to overwrite {label}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", help="render the no-contact plan")
    audit = subparsers.add_parser(
        "audit", help="run one separately authorized read-only real-fact capture"
    )
    audit.add_argument("--confirm", required=True)
    audit.add_argument("--intent", required=True, type=Path)
    audit.add_argument("--acceptance-locator-file", required=True, type=Path)
    audit.add_argument("--evidence-directory", required=True, type=Path)
    audit.add_argument("--receipt", required=True, type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    fact_port_factory: Callable[[Path], _FactPort] = _RecordingGcloudPort,
    transport_factory: Callable[..., object] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    if args.command in {None, "plan"}:
        sys.stdout.buffer.write(_canonical_bytes(plan_v1()))
        return 0
    try:
        if args.confirm != CONFIRMATION_PHRASE:
            _fail("P0-B real-fact audit confirmation phrase differs")
        intent = _read_canonical_intent(args.intent)
        locator = _private_locator(
            args.acceptance_locator_file,
            families=_sequence(intent["locator_families"], label="locator families"),
        )
        if args.receipt.exists() or args.evidence_directory.exists():
            _fail("P0-B evidence directory and receipt must both be absent")
        args.evidence_directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        if stat.S_IMODE(args.evidence_directory.stat().st_mode) & 0o077:
            _fail("P0-B evidence directory is not private")
        _write_create_once(
            args.evidence_directory / "intent.json", intent, label="intent transcript"
        )
        receipt = audit_provider_reality_v1(
            intent=intent,
            acceptance_locator=locator,
            fact_port=fact_port_factory(args.evidence_directory),
            transport_factory=transport_factory,
        )
        _write_create_once(args.receipt, receipt, label="P0-B receipt")
        sys.stdout.buffer.write(_canonical_bytes(receipt))
        return 0
    except (
        Week1A5P0BProviderRealityError,
        acquisition.Week1A5DraftKingsAcquisitionError,
        capture.Week1A5CaptureContractError,
    ) as exc:
        print(f"P0-B provider-reality HOLD: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "AUTHORITY_BUCKET_PERMISSIONS",
    "CONFIRMATION_PHRASE",
    "INTENT_SCHEMA",
    "JOB_MUTATION_PERMISSIONS",
    "PLAN_SCHEMA",
    "PROJECT",
    "RECEIPT_SCHEMA",
    "SECRET_ACCESS_PERMISSIONS",
    "SERVICE_ACCOUNT_IMPERSONATION_PERMISSIONS",
    "SURFACE_PERMISSIONS",
    "Week1A5P0BProviderRealityError",
    "audit_provider_reality_v1",
    "main",
    "plan_v1",
    "validate_intent_v1",
]
