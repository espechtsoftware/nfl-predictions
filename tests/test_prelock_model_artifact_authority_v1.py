from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from nfl_dfs.config import settings
from nfl_dfs.inference.prelock_model_artifact_authority_v1 import (
    GcsModelArtifactAuthority,
    PrelockModelArtifactAuthorityError,
    validate_model_artifact_manifest_v1,
)
from nfl_dfs.models.components import COMPONENT_NAMES

LOCK = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)


@dataclass
class _Record:
    payload: bytes
    generation: int
    created: datetime


class _Blob:
    def __init__(self, bucket: _Bucket, name: str) -> None:
        self._bucket = bucket
        self.name = name
        self.generation: int | None = None
        self.time_created: datetime | None = None

    def reload(self) -> None:
        record = self._bucket.objects[self.name]
        self.generation = record.generation
        self.time_created = record.created

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        record = self._bucket.objects[self.name]
        if record.generation != if_generation_match:
            raise RuntimeError("provider generation moved")
        return record.payload


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, _Record] = {}
        self.blobs: dict[str, _Blob] = {}

    def blob(self, name: str) -> _Blob:
        return self.blobs.setdefault(name, _Blob(self, name))


class _Client:
    def __init__(self) -> None:
        self.bucket_object = _Bucket()

    def bucket(self, name: str) -> _Bucket:
        assert name == settings.gcs_bucket
        return self.bucket_object

    def list_blobs(self, bucket: _Bucket, *, prefix: str):
        assert bucket is self.bucket_object
        return [
            bucket.blob(name)
            for name in sorted(bucket.objects)
            if name.startswith(prefix)
        ]


def _registry() -> _Client:
    client = _Client()
    generation = 10_000
    created = datetime(2026, 9, 13, 15, 0, 0, 500_000, tzinfo=UTC)
    for variant in ("tail_k1", "tail_k1_role"):
        for component in COMPONENT_NAMES:
            label = f"comp_{component}__{variant}"
            base = f"{settings.model_registry_prefix}/pooled/{label}/2026-W36"
            for name in ("meta.json", "model.txt"):
                generation += 1
                client.bucket_object.objects[f"{base}/{name}"] = _Record(
                    payload=f"{variant}/{component}/{name}".encode(),
                    generation=generation,
                    created=created,
                )
    return client


def test_gcs_model_artifacts_are_exactly_bracketed_without_a_write_surface() -> None:
    client = _registry()
    authority = GcsModelArtifactAuthority(client)
    manifest = authority.freeze(
        purpose_variants={
            "candidate-projection": "tail_k1",
            "role-belief": "tail_k1_role",
        },
        expected_member_count=1,
        must_precede=LOCK,
    )

    assert authority.reopen_exact(manifest) == manifest
    assert manifest["read_only"] is True
    assert manifest["provider_generations_required_unchanged_after_generation"] is True
    assert not hasattr(authority, "create")
    assert not hasattr(authority, "upload")
    assert len(manifest["model_sets"]) == 2
    assert all(
        len(model_set["components"]) == len(COMPONENT_NAMES)
        for model_set in manifest["model_sets"]
    )


def test_model_generation_change_between_freeze_and_reopen_fails_closed() -> None:
    client = _registry()
    authority = GcsModelArtifactAuthority(client)
    manifest = authority.freeze(
        purpose_variants={
            "candidate-projection": "tail_k1",
            "role-belief": "tail_k1_role",
        },
        expected_member_count=1,
        must_precede=LOCK,
    )
    identity = manifest["model_sets"][0]["components"][0]["artifacts"][0]["identity"]
    object_name = identity["uri"].removeprefix(f"gs://{settings.gcs_bucket}/")
    client.bucket_object.objects[object_name].generation += 1

    with pytest.raises(
        PrelockModelArtifactAuthorityError,
        match="generation changed",
    ):
        authority.reopen_exact(manifest)


def test_model_manifest_rejects_semantically_wrong_provider_uri() -> None:
    client = _registry()
    manifest = GcsModelArtifactAuthority(client).freeze(
        purpose_variants={
            "candidate-projection": "tail_k1",
            "role-belief": "tail_k1_role",
        },
        expected_member_count=1,
        must_precede=LOCK,
    )
    manifest["model_sets"][0]["components"][0]["artifacts"][0]["identity"]["uri"] = (
        "gs://wrong-bucket/models/pooled/comp_targets__tail_k1/2026-W36/meta.json"
    )

    with pytest.raises(PrelockModelArtifactAuthorityError):
        validate_model_artifact_manifest_v1(manifest)
