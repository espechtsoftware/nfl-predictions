"""Read-only application seam for the immutable 2026 Week-1 money book."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from ..inference import prospective_generation_shadow_evaluation as shadow
from ..inference.prospective_generation_shadow_operator import (
    GCSImmutableObjectStore,
    ImmutableObjectStore,
)
from ..inference.week1_operating_book_export import (
    build_week1_operating_book_export_v1,
    build_week1_operating_book_export_v2,
)
from ..inference.week1_operating_book_operator import (
    WEEK1_DRAFT_GROUP_ID,
    WEEK1_SEASON,
    WEEK1_WEEK,
    read_week1_operating_book_v1,
)
from ..optimizer.paid_classic_deployment_v3 import (
    reopen_paid_classic_activation_authority_v3,
)

IDENTITY_ENV = {
    "uri": "WEEK1_OPERATING_BOOK_URI",
    "generation": "WEEK1_OPERATING_BOOK_GENERATION",
    "sha256": "WEEK1_OPERATING_BOOK_SHA256",
    "bytes": "WEEK1_OPERATING_BOOK_BYTES",
}


class Week1OperatingBookAPIError(RuntimeError):
    """The deployed app lacks one exact, usable Week-1 book authority."""


def materialization_identity_from_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Resolve the all-or-nothing generation-pinned identity; no URI-only mode."""

    env = os.environ if environment is None else environment
    raw = {
        "uri": env.get("WEEK1_OPERATING_BOOK_URI", ""),
        "generation": env.get("WEEK1_OPERATING_BOOK_GENERATION", ""),
        "sha256": env.get("WEEK1_OPERATING_BOOK_SHA256", ""),
        "bytes": env.get("WEEK1_OPERATING_BOOK_BYTES", ""),
    }
    missing = [field for field, value in raw.items() if not str(value)]
    if missing:
        raise Week1OperatingBookAPIError(
            "canonical Week-1 book is not configured by exact object identity"
        )
    try:
        raw["bytes"] = int(str(raw["bytes"]))
        return shadow.normalize_object_identity_v1(
            raw, label="deployed Week-1 materialization identity"
        )
    except Exception as exc:
        raise Week1OperatingBookAPIError(
            "canonical Week-1 object identity is invalid"
        ) from exc


def load_week1_operating_book_export(
    *,
    projection_store,
    object_store: ImmutableObjectStore | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Exact-read and render the artifact selected only by deployment config."""

    identity = materialization_identity_from_environment(environment)
    storage = GCSImmutableObjectStore() if object_store is None else object_store
    try:
        exact = read_week1_operating_book_v1(
            store=storage, materialization_identity=identity
        )
        salaries = projection_store.classic_salaries(
            int(WEEK1_DRAFT_GROUP_ID)
        )
        return build_week1_operating_book_export_v1(
            exact_book=exact, salary_rows=salaries,
        )
    except Exception as exc:
        raise Week1OperatingBookAPIError(
            "canonical Week-1 book failed exact read or DK export validation"
        ) from exc


def load_week1_operating_book_export_v2(
    *,
    projection_store,
    object_store: ImmutableObjectStore | None = None,
    environment: Mapping[str, str] | None = None,
    activation_object_reader: (
        Callable[[Mapping[str, object]], bytes] | None
    ) = None,
    final_activation_object_reader: (
        Callable[[str, str], tuple[Mapping[str, object], bytes]] | None
    ) = None,
) -> dict[str, object]:
    """Render the canonical-game successor from exact live authorities."""

    env = os.environ if environment is None else environment
    identity = materialization_identity_from_environment(env)
    storage = GCSImmutableObjectStore() if object_store is None else object_store
    try:
        activation = reopen_paid_classic_activation_authority_v3(
            env,
            object_reader=activation_object_reader,
            final_object_reader=final_activation_object_reader,
        )
        exact = read_week1_operating_book_v1(
            store=storage, materialization_identity=identity
        )
        validated_at = _week1_paid_validation_time_v2()
        salaries = projection_store.classic_salaries(
            int(WEEK1_DRAFT_GROUP_ID)
        )
        projections = projection_store.projection_batch(
            WEEK1_SEASON, WEEK1_WEEK, as_of=validated_at
        )
        schedules = projection_store.schedule_games(
            WEEK1_SEASON, WEEK1_WEEK
        )
        return build_week1_operating_book_export_v2(
            exact_book=exact,
            salary_rows=salaries,
            projection_rows=projections,
            schedule_rows=schedules,
            validated_at=validated_at,
            source_commit_sha=env.get("IMAGE_SOURCE_COMMIT_SHA", ""),
            immutable_image_digest=env.get("IMAGE_DIGEST", ""),
            cloud_build_id=env.get("PAID_V3_CLOUD_BUILD_ID", ""),
            immutable_image_uri=env.get("IMAGE_URI", ""),
            running_revision=env.get("K_REVISION", ""),
            cloud_project=str(activation["authority"]["cloud_project"]),
            cloud_region=str(activation["authority"]["cloud_region"]),
            cloud_run_service=str(
                activation["authority"]["cloud_run_service"]
            ),
            activation_authority_uri=str(
                activation["object_identity"]["uri"]
            ),
            activation_authority_generation=str(
                activation["object_identity"]["generation"]
            ),
            activation_authority_object_sha256=str(
                activation["object_identity"]["sha256"]
            ),
            activation_authority_bytes=int(
                activation["object_identity"]["bytes"]
            ),
            activation_authority_sha256=str(
                activation["authority"]["authority_sha256"]
            ),
        )
    except Exception as exc:
        raise Week1OperatingBookAPIError(
            "canonical Week-1 book failed exact read or v2 semantic validation"
        ) from exc


def _week1_paid_validation_time_v2() -> datetime:
    """Server-owned point-in-time boundary shared by all Week-1 joins."""

    return datetime.now(timezone.utc)


__all__ = [
    "IDENTITY_ENV",
    "Week1OperatingBookAPIError",
    "load_week1_operating_book_export",
    "load_week1_operating_book_export_v2",
    "materialization_identity_from_environment",
]
