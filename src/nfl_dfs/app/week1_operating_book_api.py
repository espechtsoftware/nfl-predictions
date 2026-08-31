"""Read-only application seam for the immutable 2026 Week-1 money book."""

from __future__ import annotations

from collections.abc import Mapping
import os

from ..inference import prospective_generation_shadow_evaluation as shadow
from ..inference.prospective_generation_shadow_operator import (
    GCSImmutableObjectStore,
    ImmutableObjectStore,
)
from ..inference.week1_operating_book_export import (
    build_week1_operating_book_export_v1,
)
from ..inference.week1_operating_book_operator import (
    WEEK1_DRAFT_GROUP_ID,
    read_week1_operating_book_v1,
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
            exact_book=exact, salary_rows=salaries
        )
    except Exception as exc:
        raise Week1OperatingBookAPIError(
            "canonical Week-1 book failed exact read or DK export validation"
        ) from exc


__all__ = [
    "IDENTITY_ENV",
    "Week1OperatingBookAPIError",
    "load_week1_operating_book_export",
    "materialization_identity_from_environment",
]
