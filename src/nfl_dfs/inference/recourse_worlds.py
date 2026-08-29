"""Immutable, outcome-free world transport for prospective late swap.

The initial lineup build can retain the exact player-by-world simulation used
to construct its candidate book.  At a later decision time this module turns
that frozen artifact into remaining-score worlds using only timestamped
points-to-date and game status, then hands the result to the separately frozen
recourse proposer.  It does not read contest results, final future outcomes,
ownership results, rank, payout, or ROI.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping

import numpy as np
import pandas as pd

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..optimizer.late_swap import (
    propose_recourse_rosters,
    validate_information_as_of,
)


RECOURSE_WORLD_ARTIFACT_VERSION = "prospective-recourse-worlds-v1"
RECOURSE_WORLD_MEMBERS = frozenset({
    "metadata", "player_ids", "player_draws", "candidate_rosters",
})
GAME_STATUSES = frozenset({"not_started", "in_progress", "final"})
FORBIDDEN_METADATA_FIELDS = frozenset({
    "actual", "actual_score", "final_score", "actual_ownership",
    "contest_rank", "payout", "roi",
})


def _aware(value, label: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return stamp


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"recourse metadata cannot encode {type(value).__name__}")


def _forbidden_metadata_paths(value, path="metadata") -> list[str]:
    found = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_METADATA_FIELDS:
                found.append(child)
            found.extend(_forbidden_metadata_paths(nested, child))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_forbidden_metadata_paths(nested, f"{path}[{index}]"))
    return found


def encode_recourse_world_artifact(
    batch: CandidateBatch,
    dk_id_by_player_id: Mapping[object, str | int],
    *,
    generated_at,
    context: Mapping[str, object] | None = None,
) -> tuple[bytes, dict]:
    """Encode an exact combined candidate batch with DK-local identities."""
    _validate_candidate_batch(batch)
    stamp = _aware(generated_at, "recourse artifact generated-at")
    artifact_context = dict(context or {})
    forbidden_paths = _forbidden_metadata_paths({
        "batch": batch.metadata, "context": artifact_context,
    })
    if forbidden_paths:
        raise ValueError(
            "recourse artifact metadata contains outcome fields: "
            + ", ".join(forbidden_paths)
        )
    missing = [
        player_id for player_id in batch.player_ids
        if player_id not in dk_id_by_player_id
    ]
    if missing:
        raise ValueError(
            "recourse artifact lacks DK ids for players: "
            + ", ".join(str(value) for value in missing)
        )
    player_ids = np.asarray([
        str(dk_id_by_player_id[player_id]) for player_id in batch.player_ids
    ], dtype=str)
    if np.any(player_ids == "") or len(set(player_ids.tolist())) != len(player_ids):
        raise ValueError("recourse artifact DK player ids must be unique")
    translated = dict(zip(batch.player_ids, player_ids.tolist(), strict=True))
    candidate_rosters = np.asarray([
        sorted(translated[player_id] for player_id in lineup.ids)
        for lineup in batch.candidates
    ], dtype=str)
    if candidate_rosters.shape != (len(batch.candidates), 9):
        raise ValueError("recourse artifact candidates are not exact-nine")
    metadata = {
        "artifact_version": RECOURSE_WORLD_ARTIFACT_VERSION,
        "generated_at": stamp.isoformat(),
        "portfolio": str(batch.metadata.get("portfolio", "")),
        "candidate_batch_metadata": batch.metadata,
        "context": artifact_context,
        "uses_post_decision_outcomes": False,
    }
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        metadata=np.asarray(json.dumps(
            metadata, default=_json_default, separators=(",", ":"),
            sort_keys=True,
        )),
        player_ids=player_ids,
        player_draws=np.asarray(batch.row_draws, dtype=np.float32),
        candidate_rosters=candidate_rosters,
    )
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    return payload, {
        "artifact_version": RECOURSE_WORLD_ARTIFACT_VERSION,
        "sha256": digest,
        "bytes": len(payload),
        "generated_at": stamp.isoformat(),
        "players": int(len(player_ids)),
        "candidates": int(len(candidate_rosters)),
        "worlds": int(batch.row_draws.shape[1]),
        "uses_post_decision_outcomes": False,
    }


def decode_recourse_world_artifact(
    payload: bytes, expected_sha256: str,
) -> dict:
    """Verify checksum, members, identity alignment, and artifact contract."""
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(expected_sha256):
        raise ValueError(
            f"recourse artifact sha256 differs: {digest} != {expected_sha256}"
        )
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        if set(archive.files) != RECOURSE_WORLD_MEMBERS:
            raise ValueError(
                "recourse artifact members differ: "
                + ", ".join(sorted(archive.files))
            )
        decoded = {name: archive[name].copy() for name in archive.files}
    try:
        metadata = json.loads(str(decoded["metadata"].item()))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("recourse artifact metadata is invalid") from exc
    if metadata.get("artifact_version") != RECOURSE_WORLD_ARTIFACT_VERSION:
        raise ValueError("recourse artifact version differs")
    generated = _aware(metadata.get("generated_at"), "artifact generated-at")
    player_ids = np.asarray(decoded["player_ids"]).astype(str)
    draws = np.asarray(decoded["player_draws"], dtype=np.float32)
    rosters = np.asarray(decoded["candidate_rosters"]).astype(str)
    if player_ids.ndim != 1 or len(set(player_ids.tolist())) != len(player_ids):
        raise ValueError("recourse artifact player ids are not unique")
    if draws.ndim != 2 or draws.shape[0] != len(player_ids) or draws.shape[1] < 2:
        raise ValueError("recourse artifact player worlds are misaligned")
    if not np.isfinite(draws).all():
        raise ValueError("recourse artifact player worlds are nonfinite")
    if rosters.ndim != 2 or rosters.shape[1] != 9 or len(rosters) < 1:
        raise ValueError("recourse artifact candidate rosters are malformed")
    universe = set(player_ids.tolist())
    roster_keys = []
    for roster in rosters:
        key = tuple(sorted(roster.tolist()))
        if len(set(key)) != 9 or not set(key) <= universe:
            raise ValueError("recourse artifact candidate roster is invalid")
        roster_keys.append(key)
    if len(set(roster_keys)) != len(roster_keys):
        raise ValueError("recourse artifact candidate rosters repeat")
    return {
        "metadata": metadata,
        "generated_at": generated,
        "player_ids": player_ids,
        "player_draws": draws,
        "candidate_rosters": roster_keys,
        "sha256": digest,
    }


def persist_recourse_world_artifact(
    batch: CandidateBatch,
    dk_id_by_player_id: Mapping[object, str | int],
    *,
    generated_at,
    bucket_name: str,
    object_name: str,
    context: Mapping[str, object] | None = None,
    storage_client=None,
) -> dict:
    """Create one immutable GCS artifact and return its checksum receipt."""
    bucket_name = str(bucket_name).strip()
    object_name = str(object_name).strip().lstrip("/")
    if not bucket_name or not object_name or ".." in object_name.split("/"):
        raise ValueError("recourse artifact bucket/object is invalid")
    payload, receipt = encode_recourse_world_artifact(
        batch,
        dk_id_by_player_id,
        generated_at=generated_at,
        context=context,
    )
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob(object_name)
    blob.upload_from_string(
        payload,
        content_type="application/octet-stream",
        if_generation_match=0,
    )
    return {
        **receipt,
        "uri": f"gs://{bucket_name}/{object_name}",
        "create_only": True,
    }


def load_recourse_world_artifact(
    uri: str, expected_sha256: str, *, storage_client=None,
) -> dict:
    """Load and verify one GCS artifact by its pinned checksum."""
    raw = str(uri).strip()
    if not raw.startswith("gs://"):
        raise ValueError("recourse artifact URI must use gs://")
    bucket_name, separator, object_name = raw[5:].partition("/")
    if not separator or not bucket_name or not object_name:
        raise ValueError("recourse artifact URI is incomplete")
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    payload = storage_client.bucket(bucket_name).blob(object_name).download_as_bytes()
    return decode_recourse_world_artifact(payload, expected_sha256)


def derive_remaining_worlds(
    artifact: dict,
    player_catalog: pd.DataFrame,
    status_information: pd.DataFrame,
    *,
    as_of,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Convert frozen full-game worlds into current remaining-score worlds.

    Not-started players retain their initial worlds. Final players contribute
    their timestamped points and zero remaining score. For an in-progress
    locked player, v1 uses ``max(initial full-game draw, points_to_date)``;
    equivalently the returned remaining draw is
    ``max(draw - points_to_date, 0)``. This conservative floor rule is frozen
    prospectively and disclosed in the receipt.
    """
    current = _aware(as_of, "recourse remaining-world as-of")
    generated = _aware(artifact["generated_at"], "artifact generated-at")
    if generated.tz_convert("UTC") > current.tz_convert("UTC"):
        raise ValueError("recourse artifact was generated after the decision")
    required_catalog = {"dk_id", "kickoff"}
    missing_catalog = required_catalog - set(player_catalog.columns)
    if missing_catalog:
        raise ValueError(
            "recourse world catalog missing "
            + ", ".join(sorted(missing_catalog))
        )
    catalog = player_catalog.copy()
    catalog["dk_id"] = catalog.dk_id.astype(str)
    catalog["_kickoff"] = pd.to_datetime(
        catalog.kickoff, errors="coerce", utc=True
    )
    if (
        catalog.dk_id.eq("").any()
        or catalog.dk_id.duplicated().any()
        or catalog._kickoff.isna().any()
    ):
        raise ValueError("recourse world catalog identity/kickoff is invalid")
    catalog = catalog.set_index("dk_id", drop=False)
    player_ids = [str(value) for value in artifact["player_ids"]]
    missing_players = set(player_ids) - set(catalog.index)
    if missing_players:
        raise ValueError(
            "recourse world catalog omits artifact players: "
            + ", ".join(sorted(missing_players))
        )

    required_status = {
        "dk_id", "points_to_date", "game_status", "available_at",
    }
    missing_status = required_status - set(status_information.columns)
    if missing_status:
        raise ValueError(
            "recourse game status missing " + ", ".join(sorted(missing_status))
        )
    forbidden_status = FORBIDDEN_METADATA_FIELDS & set(status_information.columns)
    if forbidden_status:
        raise ValueError(
            "recourse game status contains outcome fields: "
            + ", ".join(sorted(forbidden_status))
        )
    information_receipt = validate_information_as_of(
        status_information, current
    )
    status = status_information.copy()
    status["dk_id"] = status.dk_id.astype(str)
    status["game_status"] = status.game_status.astype(str).str.lower()
    status["points_to_date"] = pd.to_numeric(
        status.points_to_date, errors="coerce"
    )
    if status.dk_id.eq("").any() or status.dk_id.duplicated().any():
        raise ValueError("recourse game status repeats a player")
    if not set(status.game_status) <= GAME_STATUSES:
        raise ValueError("recourse game status has an unknown state")
    if not np.isfinite(status.points_to_date.to_numpy(dtype=float)).all():
        raise ValueError("recourse game status points are nonfinite")
    unknown_status = set(status.dk_id) - set(catalog.index)
    if unknown_status:
        raise ValueError(
            "recourse game status has unknown players: "
            + ", ".join(sorted(unknown_status))
        )
    status = status.set_index("dk_id", drop=False)

    draws = np.asarray(artifact["player_draws"], dtype=np.float32).copy()
    observed_rows: list[dict] = []
    counts = {state: 0 for state in GAME_STATUSES}
    current_utc = current.tz_convert("UTC")
    for row_index, player_id in enumerate(player_ids):
        has_started = bool(catalog.loc[player_id, "_kickoff"] <= current_utc)
        if player_id not in status.index:
            if has_started:
                raise ValueError(
                    f"recourse game status missing locked player {player_id}"
                )
            game_status = "not_started"
            points = 0.0
            available_at = current.isoformat()
        else:
            row = status.loc[player_id]
            game_status = str(row.game_status)
            points = float(row.points_to_date)
            available_at = pd.Timestamp(row.available_at).isoformat()
        if not has_started and (game_status != "not_started" or points != 0):
            raise ValueError(
                f"recourse game status reveals pre-kickoff points for {player_id}"
            )
        if has_started and game_status == "not_started":
            raise ValueError(
                f"recourse game status is stale for locked player {player_id}"
            )
        if game_status == "final":
            draws[row_index] = 0.0
        elif game_status == "in_progress":
            draws[row_index] = np.maximum(draws[row_index] - points, 0.0)
        counts[game_status] += 1
        if game_status != "not_started":
            observed_rows.append({
                "dk_id": player_id,
                "points_to_date": points,
                "available_at": available_at,
            })
    remaining = pd.DataFrame(draws.T, columns=player_ids)
    points = pd.DataFrame(
        observed_rows,
        columns=["dk_id", "points_to_date", "available_at"],
    )
    receipt = {
        "artifact_version": RECOURSE_WORLD_ARTIFACT_VERSION,
        "artifact_sha256": str(artifact["sha256"]),
        "artifact_generated_at": generated.isoformat(),
        "as_of": current.isoformat(),
        "players": len(player_ids),
        "worlds": int(draws.shape[1]),
        "status_counts": counts,
        "conditioning_rule": {
            "not_started": "retain_initial_full_game_draw",
            "in_progress": "max_initial_full_game_draw_or_points_to_date",
            "final": "fixed_points_to_date_zero_remaining",
        },
        "information_receipt": information_receipt,
        "uses_post_decision_outcomes": False,
    }
    return remaining, points, receipt


def propose_recourse_from_artifact(
    artifact: dict,
    entry_rosters: Mapping[str, list[str | int] | tuple[str | int, ...]],
    player_catalog: pd.DataFrame,
    status_information: pd.DataFrame,
    *,
    as_of,
) -> dict:
    """Run the frozen proposer from one verified retained-world artifact."""
    remaining, points, adapter_receipt = derive_remaining_worlds(
        artifact, player_catalog, status_information, as_of=as_of
    )
    result = propose_recourse_rosters(
        entry_rosters,
        artifact["candidate_rosters"],
        player_catalog,
        remaining,
        points,
        as_of=as_of,
        worlds_generated_at=artifact["generated_at"],
    )
    result["world_adapter_receipt"] = adapter_receipt
    return result


__all__ = [
    "GAME_STATUSES",
    "RECOURSE_WORLD_ARTIFACT_VERSION",
    "decode_recourse_world_artifact",
    "derive_remaining_worlds",
    "encode_recourse_world_artifact",
    "load_recourse_world_artifact",
    "persist_recourse_world_artifact",
    "propose_recourse_from_artifact",
]
