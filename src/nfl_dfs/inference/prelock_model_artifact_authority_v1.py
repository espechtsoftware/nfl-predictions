"""Read-only, generation-bracketed model authority for lineage shadows.

The existing production loader intentionally remains byte-identical.  This
adapter observes the exact registry objects immediately before generation and
reopens those same provider generations immediately after generation.  Since
GCS generations are monotone, an unchanged pre/post generation census proves
that the unmodified loader could only have read the bound registry bytes.
Nothing in this module writes a model or changes model selection.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final, Protocol

from ..config import settings
from ..models.components import COMPONENT_NAMES
from .prelock_candidate_lineage_v1 import canonical_json_bytes, canonical_sha256

MODEL_ARTIFACT_MANIFEST_SCHEMA: Final = "prelock-model-artifact-window-manifest/v1"
MODEL_PURPOSES: Final = ("candidate-projection", "role-belief")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_VARIANT: Final = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ISO_WEEK: Final = re.compile(r"^\d{4}-W\d{2}$")


class PrelockModelArtifactAuthorityError(ValueError):
    """Model-registry evidence is incomplete, mutable, or out of scope."""


def _fail(message: str) -> None:
    raise PrelockModelArtifactAuthorityError(message)


def _aware(value: object, *, label: str) -> datetime:
    if type(value) is not str:
        _fail(f"{label} is not timestamp text")
    try:
        retained = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PrelockModelArtifactAuthorityError(f"{label} is invalid") from exc
    if retained.tzinfo is None or retained.utcoffset() is None:
        _fail(f"{label} is not timezone-aware")
    return retained.astimezone(UTC)


def _provider_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        _fail("provider creation time is not timezone-aware")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a provider identity")
    item = dict(value)
    if set(item) != {
        "uri",
        "generation",
        "sha256",
        "bytes",
        "time_created_utc",
    }:
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
    _aware(item["time_created_utc"], label=f"{label} creation time")
    return item


def _model_label(component: str, variant: str) -> str:
    base = f"comp_{component}"
    return base if variant == "canonical" else f"{base}__{variant}"


def _version(variant: str, iso_week: str) -> str:
    family = "components" if variant == "canonical" else f"components__{variant}"
    return f"pooled/{family}/{iso_week}"


def _validate_artifact_names(
    names: Sequence[str], *, expected_member_count: int, label: str
) -> None:
    retained = sorted(names)
    if len(retained) != len(set(retained)):
        _fail(f"{label} repeats an artifact name")
    single = ["meta.json", "model.txt"]
    ensemble = [
        "ensemble.json",
        *[f"member_{index}.txt" for index in range(expected_member_count)],
        "meta.json",
    ]
    if retained not in (sorted(single), sorted(ensemble)):
        _fail(f"{label} artifact census differs from the registry contract")


def validate_model_artifact_manifest_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("model artifact manifest is not a mapping")
    try:
        item = json.loads(canonical_json_bytes(value))
    except ValueError as exc:
        raise PrelockModelArtifactAuthorityError(
            "model artifact manifest is not canonical JSON"
        ) from exc
    if set(item) != {
        "schema_version",
        "bucket",
        "registry_prefix",
        "scope",
        "expected_member_count",
        "model_sets",
        "frozen_before_generation",
        "provider_generations_required_unchanged_after_generation",
        "read_only",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "manifest_sha256",
    }:
        _fail("model artifact manifest fields differ")
    retained_hash = item.pop("manifest_sha256")
    if (
        item["schema_version"] != MODEL_ARTIFACT_MANIFEST_SCHEMA
        or type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or retained_hash != canonical_sha256(item)
        or item["bucket"] != settings.gcs_bucket
        or item["registry_prefix"] != settings.model_registry_prefix.rstrip("/")
        or item["scope"] != "pooled"
        or type(item["expected_member_count"]) is not int
        or item["expected_member_count"] < 1
        or any(
            item[key] is not expected
            for key, expected in {
                "frozen_before_generation": True,
                "provider_generations_required_unchanged_after_generation": True,
                "read_only": True,
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            }.items()
        )
    ):
        _fail("model artifact manifest contract or self-hash differs")
    model_sets = item["model_sets"]
    if not isinstance(model_sets, list) or [
        row.get("purpose") for row in model_sets if isinstance(row, Mapping)
    ] != list(MODEL_PURPOSES):
        _fail("model artifact purpose census differs")
    expected_member_count = item["expected_member_count"]
    for model_set in model_sets:
        if not isinstance(model_set, Mapping) or set(model_set) != {
            "purpose",
            "variant",
            "iso_week",
            "model_version",
            "components",
        }:
            _fail("model artifact set fields differ")
        variant = model_set["variant"]
        iso_week = model_set["iso_week"]
        if (
            type(variant) is not str
            or _VARIANT.fullmatch(variant) is None
            or type(iso_week) is not str
            or _ISO_WEEK.fullmatch(iso_week) is None
            or model_set["model_version"] != _version(variant, iso_week)
        ):
            _fail("model artifact set version differs")
        components = model_set["components"]
        if not isinstance(components, list) or [
            row.get("component") for row in components if isinstance(row, Mapping)
        ] != list(COMPONENT_NAMES):
            _fail("model component census or order differs")
        for component in components:
            if not isinstance(component, Mapping) or set(component) != {
                "component",
                "registry_label",
                "artifacts",
            }:
                _fail("model component fields differ")
            name = str(component["component"])
            if component["registry_label"] != _model_label(name, variant):
                _fail("model registry label differs")
            artifacts = component["artifacts"]
            if not isinstance(artifacts, list):
                _fail("model component artifacts are not an array")
            names = []
            for artifact in artifacts:
                if not isinstance(artifact, Mapping) or set(artifact) != {
                    "name",
                    "identity",
                }:
                    _fail("model artifact binding fields differ")
                artifact_name = artifact["name"]
                if type(artifact_name) is not str or "/" in artifact_name:
                    _fail("model artifact name differs")
                identity = _identity(
                    artifact["identity"],
                    label=f"{variant}/{name}/{artifact_name}",
                )
                expected_uri = (
                    f"gs://{item['bucket']}/{item['registry_prefix']}/pooled/"
                    f"{_model_label(name, variant)}/{iso_week}/{artifact_name}"
                )
                if identity["uri"] != expected_uri:
                    _fail("model artifact URI does not match its semantic binding")
                names.append(artifact_name)
            _validate_artifact_names(
                names,
                expected_member_count=expected_member_count,
                label=f"{variant}/{name}",
            )
    return {**item, "manifest_sha256": retained_hash}


class ModelArtifactAuthority(Protocol):
    def freeze(
        self,
        *,
        purpose_variants: Mapping[str, str],
        expected_member_count: int,
        must_precede: datetime,
    ) -> dict[str, object]: ...

    def reopen_exact(self, manifest: Mapping[str, object]) -> dict[str, object]: ...


class GcsModelArtifactAuthority:
    """Exact read-only GCS registry observer; it has no write method."""

    def __init__(self, storage_client: object) -> None:
        self.bucket_name = settings.gcs_bucket
        self.registry_prefix = settings.model_registry_prefix.rstrip("/")
        self._client = storage_client
        self._bucket = storage_client.bucket(self.bucket_name)

    def _list_names(self, prefix: str) -> list[str]:
        return sorted(
            str(blob.name)
            for blob in self._client.list_blobs(self._bucket, prefix=prefix)
        )

    def _latest_week(self, variant: str) -> str:
        label = _model_label("targets", variant)
        prefix = f"{self.registry_prefix}/pooled/{label}/"
        weeks = {
            name.removeprefix(prefix).split("/", 1)[0]
            for name in self._list_names(prefix)
            if name.startswith(prefix)
        }
        if not weeks or any(_ISO_WEEK.fullmatch(week) is None for week in weeks):
            _fail(f"model registry latest-week census differs for {variant}")
        return max(weeks)

    def _read_current(
        self, object_name: str, *, must_precede: datetime
    ) -> tuple[bytes, dict[str, object]]:
        blob = self._bucket.blob(object_name)
        blob.reload()
        generation = str(blob.generation or "")
        created = getattr(blob, "time_created", None)
        if (
            not generation.isdigit()
            or int(generation) < 1
            or not isinstance(created, datetime)
        ):
            _fail("model registry object lacks provider identity")
        payload = bytes(blob.download_as_bytes(if_generation_match=int(generation)))
        if not payload:
            _fail("model registry object is empty")
        created_text = _provider_time(created)
        if _aware(created_text, label="model artifact creation") >= must_precede:
            _fail("model registry object was not provider-created before lock")
        identity = {
            "uri": f"gs://{self.bucket_name}/{object_name}",
            "generation": generation,
            "sha256": sha256(payload).hexdigest(),
            "bytes": len(payload),
            "time_created_utc": created_text,
        }
        return payload, _identity(identity, label=object_name)

    def freeze(
        self,
        *,
        purpose_variants: Mapping[str, str],
        expected_member_count: int,
        must_precede: datetime,
    ) -> dict[str, object]:
        if list(purpose_variants) != list(MODEL_PURPOSES):
            _fail("model purpose/variant order differs")
        if type(expected_member_count) is not int or expected_member_count < 1:
            _fail("model member count differs")
        if must_precede.tzinfo is None or must_precede.utcoffset() is None:
            _fail("model artifact deadline is not timezone-aware")
        model_sets: list[dict[str, object]] = []
        for purpose in MODEL_PURPOSES:
            variant = purpose_variants[purpose]
            if _VARIANT.fullmatch(variant) is None:
                _fail("model registry variant differs")
            iso_week = self._latest_week(variant)
            component_rows: list[dict[str, object]] = []
            for component in COMPONENT_NAMES:
                label = _model_label(component, variant)
                base = f"{self.registry_prefix}/pooled/{label}/{iso_week}/"
                names = self._list_names(base)
                leaves = [
                    name.removeprefix(base)
                    for name in names
                    if name.startswith(base) and "/" not in name.removeprefix(base)
                ]
                if len(leaves) != len(names):
                    _fail("nested or out-of-prefix model artifact differs")
                _validate_artifact_names(
                    leaves,
                    expected_member_count=expected_member_count,
                    label=f"{variant}/{component}",
                )
                artifacts = []
                for leaf in sorted(leaves):
                    payload, identity = self._read_current(
                        f"{base}{leaf}", must_precede=must_precede
                    )
                    if leaf == "ensemble.json":
                        try:
                            ensemble = json.loads(payload)
                        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                            raise PrelockModelArtifactAuthorityError(
                                "model ensemble manifest is invalid"
                            ) from exc
                        if ensemble != {"k": expected_member_count}:
                            _fail("model ensemble member count differs")
                    artifacts.append({"name": leaf, "identity": identity})
                # Close a listing race inside the pre-generation freeze.
                if self._list_names(base) != names:
                    _fail("model registry artifact census changed during freeze")
                component_rows.append(
                    {
                        "component": component,
                        "registry_label": label,
                        "artifacts": artifacts,
                    }
                )
            model_sets.append(
                {
                    "purpose": purpose,
                    "variant": variant,
                    "iso_week": iso_week,
                    "model_version": _version(variant, iso_week),
                    "components": component_rows,
                }
            )
        body: dict[str, object] = {
            "schema_version": MODEL_ARTIFACT_MANIFEST_SCHEMA,
            "bucket": self.bucket_name,
            "registry_prefix": self.registry_prefix,
            "scope": "pooled",
            "expected_member_count": expected_member_count,
            "model_sets": model_sets,
            "frozen_before_generation": True,
            "provider_generations_required_unchanged_after_generation": True,
            "read_only": True,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        }
        body["manifest_sha256"] = canonical_sha256(body)
        return validate_model_artifact_manifest_v1(body)

    def reopen_exact(self, manifest: Mapping[str, object]) -> dict[str, object]:
        retained = validate_model_artifact_manifest_v1(manifest)
        for model_set in retained["model_sets"]:
            variant = str(model_set["variant"])
            if self._latest_week(variant) != model_set["iso_week"]:
                _fail("model registry latest week changed during generation")
            for component in model_set["components"]:
                artifacts = component["artifacts"]
                expected_names = sorted(
                    str(row["identity"]["uri"]) for row in artifacts
                )
                prefix = expected_names[0].rsplit("/", 1)[0] + "/"
                object_prefix = prefix.removeprefix(f"gs://{self.bucket_name}/")
                current_names = self._list_names(object_prefix)
                if [
                    f"gs://{self.bucket_name}/{name}" for name in current_names
                ] != expected_names:
                    _fail("model registry artifact census changed during generation")
                for artifact in artifacts:
                    identity = _identity(
                        artifact["identity"], label="frozen model artifact"
                    )
                    object_name = str(identity["uri"]).removeprefix(
                        f"gs://{self.bucket_name}/"
                    )
                    blob = self._bucket.blob(object_name)
                    blob.reload()
                    if str(blob.generation or "") != identity["generation"]:
                        _fail("model artifact generation changed during generation")
                    payload = bytes(
                        blob.download_as_bytes(
                            if_generation_match=int(identity["generation"])
                        )
                    )
                    created = getattr(blob, "time_created", None)
                    if not isinstance(created, datetime):
                        _fail("reopened model artifact lacks creation time")
                    observed = {
                        "uri": identity["uri"],
                        "generation": str(blob.generation),
                        "sha256": sha256(payload).hexdigest(),
                        "bytes": len(payload),
                        "time_created_utc": _provider_time(created),
                    }
                    if observed != identity:
                        _fail(
                            "model artifact provider identity changed during generation"
                        )
        return retained


__all__ = [
    "MODEL_ARTIFACT_MANIFEST_SCHEMA",
    "MODEL_PURPOSES",
    "GcsModelArtifactAuthority",
    "ModelArtifactAuthority",
    "PrelockModelArtifactAuthorityError",
    "validate_model_artifact_manifest_v1",
]
