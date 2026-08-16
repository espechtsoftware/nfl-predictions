"""Artifact-native receipts for ATLAS current-money world acquisition."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import re
from typing import Any, Mapping

import numpy as np


ARTIFACT_NAME_RE = re.compile(
    r"^cand_scores/(?P<panel>20260815-atlas-money-worlds-r[0-4]-v1)/"
    r"(?P<season>202[3-5])_w(?P<week>[1-9][0-9]*)_"
    r"(?P<slate_run_id>[0-9a-f]+)\.npz$"
)


def parse_utc(value: str) -> datetime:
    """Parse one required timezone-aware ISO timestamp."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("ATLAS source timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("ATLAS source timestamp must be timezone-aware")
    return parsed


def parse_artifact_name(name: str) -> dict[str, Any]:
    """Parse one exact registered artifact object name."""
    match = ARTIFACT_NAME_RE.fullmatch(str(name))
    if match is None:
        raise ValueError("ATLAS source object name is invalid")
    values = match.groupdict()
    return {
        "panel_run_id": values["panel"],
        "season": int(values["season"]),
        "week": int(values["week"]),
        "slate_run_id": values["slate_run_id"],
    }


def validate_object_interval(
    *, created: str, execution_start: str, execution_complete: str,
) -> None:
    """Require an object to have been created by its registered execution."""
    start = parse_utc(execution_start)
    complete = parse_utc(execution_complete)
    when = parse_utc(created)
    if complete < start or not start <= when <= complete:
        raise ValueError("ATLAS source object is outside execution interval")


def validate_player_world_payload(payload: bytes) -> dict[str, int | str]:
    """Validate and summarize one recovered immutable NPZ payload."""
    digest = sha256(payload).hexdigest()
    try:
        with np.load(BytesIO(payload), allow_pickle=False) as artifact:
            required = {
                "cand_ix", "totals", "tail_line", "player_ids",
                "player_draws",
            }
            if set(artifact.files) != required:
                raise ValueError("ATLAS source artifact arrays differ")
            cand_ix = np.asarray(artifact["cand_ix"])
            totals = np.asarray(artifact["totals"])
            tail_line = np.asarray(artifact["tail_line"])
            player_ids = np.asarray(artifact["player_ids"]).astype(str)
            player_draws = np.asarray(artifact["player_draws"])
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("ATLAS"):
            raise
        raise ValueError("ATLAS source artifact cannot be decoded") from exc

    if totals.ndim != 2 or totals.shape[0] <= 0 or totals.shape[1] != 10_000:
        raise ValueError("ATLAS source candidate-world shape differs")
    if cand_ix.ndim != 1 or not np.array_equal(
        cand_ix, np.arange(totals.shape[0], dtype=cand_ix.dtype),
    ):
        raise ValueError("ATLAS source candidate identities differ")
    if tail_line.size != 1 or not np.isfinite(tail_line).all():
        raise ValueError("ATLAS source tail line differs")
    if player_draws.ndim != 2 or player_draws.shape[0] <= 0 or \
            player_draws.shape[1] != 10_000:
        raise ValueError("ATLAS source player-world shape differs")
    if player_ids.ndim != 1 or len(player_ids) != player_draws.shape[0] or \
            len(set(player_ids.tolist())) != len(player_ids) or \
            any(not value for value in player_ids):
        raise ValueError("ATLAS source player identities differ")
    if not np.isfinite(totals).all() or not np.isfinite(player_draws).all():
        raise ValueError("ATLAS source worlds contain nonfinite values")
    return {
        "sha256": digest,
        "source_rows": int(totals.shape[0]),
        "players": int(player_draws.shape[0]),
        "worlds": int(player_draws.shape[1]),
    }


def validate_environment_receipt(receipt: Mapping[str, Any]) -> dict[str, str]:
    """Verify one complete execution-environment receipt."""
    values = receipt.get("values")
    if not isinstance(values, Mapping):
        raise ValueError("ATLAS environment receipt values are invalid")
    normalized = dict(sorted(
        (str(key), str(value)) for key, value in values.items()
    ))
    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"),
    ).encode()
    if receipt.get("sha256") != sha256(encoded).hexdigest():
        raise ValueError("ATLAS environment receipt hash differs")
    return normalized


__all__ = [
    "parse_artifact_name", "parse_utc", "validate_environment_receipt",
    "validate_object_interval", "validate_player_world_payload",
]
