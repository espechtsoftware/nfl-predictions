"""Shared immutable-artifact source resolution for research protocols."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import hashlib
from pathlib import Path
import re
from typing import Any


SHA256_RE = re.compile(r"[0-9a-f]{64}")
CODE_SHA_RE = re.compile(r"[0-9a-f]{40}")
IMAGE_RE = re.compile(r".+@sha256:[0-9a-f]{64}")


def validate_execution_identity(code_sha: str, image: str) -> None:
    """Require a full code commit and immutable container image."""
    if CODE_SHA_RE.fullmatch(str(code_sha)) is None:
        raise ValueError("source preflight requires a full code SHA")
    if IMAGE_RE.fullmatch(str(image)) is None:
        raise ValueError("source preflight requires an immutable image digest")


def verify_local_sha256(
    sources: Mapping[str, tuple[str | Path, str]],
) -> dict[str, str]:
    """Verify named local protocol/report sources and return their hashes."""
    receipts: dict[str, str] = {}
    for name, (raw_path, expected) in sources.items():
        path = Path(raw_path)
        if not path.is_file() or SHA256_RE.fullmatch(str(expected)) is None:
            raise ValueError(f"source preflight local identity is invalid: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"source preflight local identity differs: {name}")
        receipts[str(name)] = actual
    return receipts


def _valid_gcs_object(uri: str) -> bool:
    if not uri.startswith("gs://") or uri.endswith("/"):
        return False
    bucket, marker, name = uri[5:].partition("/")
    return bool(marker and bucket and name and ".." not in name.split("/"))


def resolve_panel_artifacts(
    rows: Sequence[Mapping[str, Any]],
    *,
    panel_ids: Sequence[str],
    expected_slates: int,
    panel_field: str = "panel_run_id",
    season_field: str = "season",
    week_field: str = "week",
    uri_field: str = "score_artifact_uri",
    sha_field: str = "score_artifact_sha256",
) -> dict[str, Any]:
    """Resolve exactly one immutable artifact for every panel/slate cell.

    Candidate tables commonly contain many rows for one artifact. This helper
    collapses those rows only after proving that each panel/slate cell names
    one URI and one digest and that the panel-by-slate grid is complete.
    """
    expected_panels = tuple(str(value) for value in panel_ids)
    if (
        not expected_panels
        or len(set(expected_panels)) != len(expected_panels)
        or expected_slates <= 0
    ):
        raise ValueError("source preflight expected panel grid is invalid")

    grouped: dict[tuple[str, int, int], dict[str, Any]] = {}
    values: dict[tuple[str, int, int], dict[str, set[str]]] = defaultdict(
        lambda: {"uris": set(), "digests": set()}
    )
    row_counts: dict[tuple[str, int, int], int] = defaultdict(int)
    for row in rows:
        try:
            panel = str(row[panel_field])
            season = int(row[season_field])
            week = int(row[week_field])
            uri = str(row[uri_field])
            digest = str(row[sha_field])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("source preflight row is incomplete") from exc
        if panel not in expected_panels:
            raise ValueError("source preflight found an unexpected panel")
        if not _valid_gcs_object(uri) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("source preflight artifact identity is invalid")
        key = (panel, season, week)
        values[key]["uris"].add(uri)
        values[key]["digests"].add(digest)
        row_counts[key] += 1

    for key, identity in values.items():
        if len(identity["uris"]) != 1 or len(identity["digests"]) != 1:
            raise ValueError("source preflight artifact identity is ambiguous")
        grouped[key] = {
            "panel_run_id": key[0],
            "season": key[1],
            "week": key[2],
            "uri": next(iter(identity["uris"])),
            "sha256": next(iter(identity["digests"])),
            "source_rows": row_counts[key],
        }

    slate_keys = sorted({(key[1], key[2]) for key in grouped})
    expected_keys = {
        (panel, season, week)
        for panel in expected_panels
        for season, week in slate_keys
    }
    if len(slate_keys) != expected_slates or set(grouped) != expected_keys:
        raise ValueError("source preflight panel/slate grid is incomplete")

    panel_order = {panel: index for index, panel in enumerate(expected_panels)}
    artifacts = sorted(
        grouped.values(),
        key=lambda row: (
            int(row["season"]), int(row["week"]),
            panel_order[str(row["panel_run_id"])],
        ),
    )
    return {
        "panel_ids": list(expected_panels),
        "slates": [[season, week] for season, week in slate_keys],
        "slate_count": len(slate_keys),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


__all__ = [
    "resolve_panel_artifacts", "validate_execution_identity",
    "verify_local_sha256",
]
