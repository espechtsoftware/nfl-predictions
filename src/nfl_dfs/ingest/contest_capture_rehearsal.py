"""Local settlement rehearsal for the Week-1 contest-capture boundary.

This module deliberately cannot apply a capture.  It reopens a versioned
pre-lock contest manifest and its local evidence, runs the existing complete
field validator in validation-only mode, reconciles the payout ladder (ties
included), prepares structural warehouse row shapes in memory, and emits a
self-hashed local receipt.  Cloud Storage and BigQuery are never contacted.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from . import ownership_import


MANIFEST_SCHEMA = "dk-contest-manifest/v2"
RECEIPT_SCHEMA = "week1-contest-capture-rehearsal/v1"
MICRO_DOLLARS = Decimal("1000000")
CENT_MICRO = 10_000


class CaptureRehearsalError(ValueError):
    """A local contest-capture rehearsal contract was violated."""


def _fail(message: str) -> None:
    raise CaptureRehearsalError(message)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
    ):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            f"{label} fields differ: missing={sorted(expected - actual)} "
            f"unexpected={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} must be a non-empty string")
    return value.strip()


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _timestamp(value: object, *, label: str) -> datetime:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaptureRehearsalError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        _fail(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _local_identity(
    raw: object,
    *,
    label: str,
    manifest_dir: Path,
    captured_at_required: bool,
) -> tuple[dict[str, object], bytes]:
    identity = _mapping(raw, label=label)
    expected = {"uri", "sha256", "bytes"}
    if captured_at_required:
        expected.add("captured_at")
    _exact_keys(identity, expected, label=label)
    uri = _string(identity.get("uri"), label=f"{label} uri")
    candidate = Path(uri)
    if candidate.is_absolute() or ".." in candidate.parts:
        _fail(f"{label} uri must be a safe path relative to the manifest")
    path = (manifest_dir / candidate).resolve()
    try:
        path.relative_to(manifest_dir.resolve())
    except ValueError:
        _fail(f"{label} uri escapes the manifest directory")
    if not path.is_file():
        _fail(f"{label} local artifact does not exist: {uri}")
    payload = path.read_bytes()
    expected_sha = _string(identity.get("sha256"), label=f"{label} sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        _fail(f"{label} sha256 must be lowercase hexadecimal")
    expected_bytes = _integer(identity.get("bytes"), label=f"{label} bytes", minimum=1)
    if len(payload) != expected_bytes or _sha256(payload) != expected_sha:
        _fail(f"{label} content identity does not match reopened local bytes")
    normalized: dict[str, object] = {
        "uri": uri,
        "sha256": expected_sha,
        "bytes": expected_bytes,
    }
    if captured_at_required:
        normalized["captured_at"] = _iso(
            _timestamp(identity.get("captured_at"), label=f"{label} captured_at")
        )
    return normalized, payload


def _json_object(payload: bytes, *, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureRehearsalError(f"{label} must contain valid JSON") from exc
    return _mapping(value, label=label)


def _normalize_payout_ladder(
    raw_rows: object, *, field_size: int
) -> tuple[list[dict[str, object]], dict[int, int]]:
    rows = _sequence(raw_rows, label="payout_ladder")
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"payout_ladder[{ordinal}]")
        _exact_keys(
            row,
            {"rank_start", "rank_end", "payout_micro", "award_label"},
            label=f"payout_ladder[{ordinal}]",
        )
        start = _integer(
            row.get("rank_start"), label=f"payout_ladder[{ordinal}] rank_start", minimum=1
        )
        end = _integer(
            row.get("rank_end"), label=f"payout_ladder[{ordinal}] rank_end", minimum=start
        )
        payout = _integer(
            row.get("payout_micro"),
            label=f"payout_ladder[{ordinal}] payout_micro",
        )
        if end > field_size:
            _fail("payout ladder rank exceeds the contest field size")
        normalized.append(
            {
                "rank_start": start,
                "rank_end": end,
                "payout_micro": payout,
                "award_label": _string(
                    row.get("award_label"),
                    label=f"payout_ladder[{ordinal}] award_label",
                ),
            }
        )
    normalized.sort(key=lambda row: (int(row["rank_start"]), int(row["rank_end"])))
    if not normalized or normalized[0]["rank_start"] != 1:
        _fail("payout ladder must begin at rank 1")
    payout_by_rank: dict[int, int] = {}
    previous_end = 0
    previous_payout: int | None = None
    for row in normalized:
        start = int(row["rank_start"])
        end = int(row["rank_end"])
        payout = int(row["payout_micro"])
        if start != previous_end + 1:
            _fail("payout ladder contains a gap or overlap")
        if previous_payout is not None and payout > previous_payout:
            _fail("payout ladder is not nonincreasing by rank")
        for rank in range(start, end + 1):
            payout_by_rank[rank] = payout
        previous_end = end
        previous_payout = payout
    return normalized, payout_by_rank


def _normalize_manifest(
    raw: object, *, manifest_path: Path
) -> tuple[dict[str, object], bytes]:
    body = _mapping(raw, label="contest manifest")
    _exact_keys(
        body,
        {
            "schema_version",
            "rehearsal_fixture",
            "manifest_frozen_at",
            "contest",
            "payout_ladder",
            "source_identities",
            "book_bindings",
            "correction_lineage",
        },
        label="contest manifest",
    )
    if body.get("schema_version") != MANIFEST_SCHEMA:
        _fail(f"contest manifest schema must be {MANIFEST_SCHEMA}")
    rehearsal_fixture = body.get("rehearsal_fixture")
    if not isinstance(rehearsal_fixture, bool):
        _fail("rehearsal_fixture must be boolean")

    contest = _mapping(body.get("contest"), label="contest")
    _exact_keys(
        contest,
        {
            "season",
            "week",
            "contest_id",
            "contest_name",
            "draft_group_id",
            "slate_id",
            "roster_format",
            "field_size",
            "entry_fee_micro",
            "entry_limit",
            "lock_at",
            "late_swap",
        },
        label="contest",
    )
    season = _integer(contest.get("season"), label="contest season", minimum=2026)
    week = _integer(contest.get("week"), label="contest week", minimum=1)
    if week > 22:
        _fail("contest week must be <= 22")
    contest_id = _string(contest.get("contest_id"), label="contest_id")
    draft_group_id = _string(
        contest.get("draft_group_id"), label="draft_group_id"
    )
    if not contest_id.isdigit() or not draft_group_id.isdigit():
        _fail("contest_id and draft_group_id must be numeric DraftKings IDs")
    roster_format = _string(contest.get("roster_format"), label="roster_format")
    if roster_format != "classic":
        _fail("Week-1 contest rehearsal supports DraftKings Classic only")
    field_size = _integer(contest.get("field_size"), label="field_size", minimum=2)
    entry_limit = _integer(contest.get("entry_limit"), label="entry_limit", minimum=1)
    if entry_limit > field_size:
        _fail("entry_limit cannot exceed field_size")
    entry_fee_micro = _integer(
        contest.get("entry_fee_micro"), label="entry_fee_micro", minimum=1
    )
    lock_at = _timestamp(contest.get("lock_at"), label="lock_at")
    manifest_frozen_at = _timestamp(
        body.get("manifest_frozen_at"), label="manifest_frozen_at"
    )
    if manifest_frozen_at >= lock_at:
        _fail("contest manifest must freeze before slate lock")

    late_swap = _mapping(contest.get("late_swap"), label="late_swap")
    _exact_keys(
        late_swap,
        {"enabled", "policy", "state_at_freeze"},
        label="late_swap",
    )
    if not isinstance(late_swap.get("enabled"), bool):
        _fail("late_swap enabled must be boolean")
    if _string(late_swap.get("state_at_freeze"), label="late_swap state_at_freeze") != "prelock":
        _fail("late_swap state_at_freeze must be prelock")

    payout_ladder, payout_by_rank = _normalize_payout_ladder(
        body.get("payout_ladder"), field_size=field_size
    )

    sources = _mapping(body.get("source_identities"), label="source_identities")
    _exact_keys(
        sources,
        {"contest_metadata", "payout_ladder", "late_swap"},
        label="source_identities",
    )
    normalized_sources: dict[str, object] = {}
    source_payloads: dict[str, Mapping[str, object]] = {}
    for name in sorted(sources):
        identity, payload = _local_identity(
            sources[name],
            label=f"source_identities.{name}",
            manifest_dir=manifest_path.parent,
            captured_at_required=True,
        )
        if _timestamp(identity["captured_at"], label=f"{name} captured_at") > manifest_frozen_at:
            _fail(f"{name} source was captured after the manifest freeze")
        normalized_sources[name] = identity
        source_payloads[name] = _json_object(
            payload, label=f"source_identities.{name} evidence"
        )

    contest_evidence = source_payloads["contest_metadata"]
    expected_contest_evidence: dict[str, object] = {
        "schema_version": "dk-contest-metadata-evidence/v1",
        "season": season,
        "week": week,
        "contest_id": contest_id,
        "contest_name": _string(contest.get("contest_name"), label="contest_name"),
        "draft_group_id": draft_group_id,
        "slate_id": _string(contest.get("slate_id"), label="slate_id"),
        "field_size": field_size,
        "entry_fee_micro": entry_fee_micro,
        "entry_limit": entry_limit,
        "lock_at": _iso(lock_at),
    }
    if _canonical_bytes(dict(contest_evidence)) != _canonical_bytes(
        expected_contest_evidence
    ):
        _fail("contest metadata evidence does not exactly match the manifest")

    payout_evidence = source_payloads["payout_ladder"]
    expected_payout_evidence = {
        "schema_version": "dk-payout-ladder-evidence/v1",
        "contest_id": contest_id,
        "rows": payout_ladder,
    }
    if _canonical_bytes(dict(payout_evidence)) != _canonical_bytes(
        expected_payout_evidence
    ):
        _fail("payout ladder evidence does not exactly match the manifest")

    late_swap_evidence = source_payloads["late_swap"]
    expected_late_swap_evidence = {
        "schema_version": "dk-late-swap-evidence/v1",
        "contest_id": contest_id,
        "draft_group_id": draft_group_id,
        "enabled": late_swap["enabled"],
        "policy": _string(late_swap.get("policy"), label="late_swap policy"),
        "state_at_freeze": "prelock",
    }
    if _canonical_bytes(dict(late_swap_evidence)) != _canonical_bytes(
        expected_late_swap_evidence
    ):
        _fail("late-swap evidence does not exactly match the manifest")

    binding_rows = _sequence(body.get("book_bindings"), label="book_bindings")
    if not binding_rows:
        _fail("book_bindings must include paid and shadow books")
    normalized_bindings: list[dict[str, object]] = []
    book_ids: set[str] = set()
    paid_entries = 0
    purposes: set[str] = set()
    for ordinal, raw_binding in enumerate(binding_rows):
        binding = _mapping(raw_binding, label=f"book_bindings[{ordinal}]")
        _exact_keys(
            binding,
            {"book_id", "purpose", "entry_count", "frozen_at", "artifact_identity"},
            label=f"book_bindings[{ordinal}]",
        )
        book_id = _string(binding.get("book_id"), label=f"book[{ordinal}] id")
        if book_id in book_ids:
            _fail("book_bindings repeat a book_id")
        book_ids.add(book_id)
        purpose = _string(binding.get("purpose"), label=f"book[{ordinal}] purpose")
        if purpose not in {"paid", "shadow"}:
            _fail("book purpose must be paid or shadow")
        purposes.add(purpose)
        entry_count = _integer(
            binding.get("entry_count"), label=f"book[{ordinal}] entry_count", minimum=1
        )
        if purpose == "paid":
            paid_entries += entry_count
        frozen_at = _timestamp(binding.get("frozen_at"), label=f"book[{ordinal}] frozen_at")
        if frozen_at > manifest_frozen_at or frozen_at >= lock_at:
            _fail("every bound book must freeze before the manifest and slate lock")
        artifact_identity, artifact_payload = _local_identity(
            binding.get("artifact_identity"),
            label=f"book[{ordinal}] artifact_identity",
            manifest_dir=manifest_path.parent,
            captured_at_required=False,
        )
        artifact = _json_object(
            artifact_payload, label=f"book[{ordinal}] artifact"
        )
        lineup_rows = _sequence(
            artifact.get("lineup_ids"), label=f"book[{ordinal}] lineup_ids"
        )
        lineup_ids = [
            _string(value, label=f"book[{ordinal}] lineup_id")
            for value in lineup_rows
        ]
        if len(lineup_ids) != entry_count or len(set(lineup_ids)) != entry_count:
            _fail("bound book lineup IDs must be exact-count and unique")
        common_artifact = {
            "book_id": book_id,
            "contest_id": contest_id,
            "draft_group_id": draft_group_id,
            "lineup_ids": lineup_ids,
        }
        if purpose == "paid":
            _exact_keys(
                artifact,
                {
                    "schema_version",
                    "book_id",
                    "contest_id",
                    "draft_group_id",
                    "requested_entries",
                    "lineup_ids",
                    "receipt",
                },
                label=f"book[{ordinal}] paid artifact",
            )
            paid_receipt = _mapping(
                artifact.get("receipt"), label=f"book[{ordinal}] paid receipt"
            )
            _exact_keys(
                paid_receipt,
                {"exact_k", "unique_rosters", "dk_legal", "active_players_only"},
                label=f"book[{ordinal}] paid receipt",
            )
            if any(
                paid_receipt.get(name) is not True
                for name in (
                    "exact_k",
                    "unique_rosters",
                    "dk_legal",
                    "active_players_only",
                )
            ):
                _fail("paid-classic v2 integrity receipt fields must all be true")
            requested_entries = _integer(
                artifact.get("requested_entries"),
                label=f"book[{ordinal}] requested_entries",
                minimum=1,
            )
            if requested_entries != entry_count:
                _fail("paid-classic v2 requested_entries differs from the binding")
            expected_artifact = {
                "schema_version": "paid-classic-book/v2",
                **common_artifact,
                "requested_entries": entry_count,
                "receipt": {
                    "exact_k": True,
                    "unique_rosters": True,
                    "dk_legal": True,
                    "active_players_only": True,
                },
            }
        else:
            _exact_keys(
                artifact,
                {
                    "schema_version",
                    "book_id",
                    "contest_id",
                    "draft_group_id",
                    "lineup_ids",
                },
                label=f"book[{ordinal}] shadow artifact",
            )
            expected_artifact = {
                "schema_version": "shadow-classic-book/v1",
                **common_artifact,
            }
        if _canonical_bytes(dict(artifact)) != _canonical_bytes(expected_artifact):
            _fail("bound book semantics do not exactly match its manifest binding")
        normalized_bindings.append(
            {
                "book_id": book_id,
                "purpose": purpose,
                "entry_count": entry_count,
                "frozen_at": _iso(frozen_at),
                "artifact_identity": artifact_identity,
            }
        )
    if purposes != {"paid", "shadow"}:
        _fail("book_bindings must contain at least one paid and one shadow book")
    if paid_entries > entry_limit:
        _fail("paid book entries exceed the contest entry_limit")
    normalized_bindings.sort(key=lambda row: (str(row["purpose"]), str(row["book_id"])))

    correction = _mapping(body.get("correction_lineage"), label="correction_lineage")
    _exact_keys(
        correction,
        {"revision", "supersedes_manifest_sha256", "reason"},
        label="correction_lineage",
    )
    revision = _integer(correction.get("revision"), label="correction revision")
    supersedes = correction.get("supersedes_manifest_sha256")
    reason = _string(correction.get("reason"), label="correction reason")
    if revision == 0:
        if supersedes is not None:
            _fail("initial contest manifest cannot supersede another manifest")
    else:
        supersedes = _string(supersedes, label="supersedes_manifest_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", supersedes):
            _fail("supersedes_manifest_sha256 must be lowercase hexadecimal")

    normalized: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "rehearsal_fixture": rehearsal_fixture,
        "manifest_frozen_at": _iso(manifest_frozen_at),
        "contest": {
            "season": season,
            "week": week,
            "contest_id": contest_id,
            "contest_name": _string(contest.get("contest_name"), label="contest_name"),
            "draft_group_id": draft_group_id,
            "slate_id": _string(contest.get("slate_id"), label="slate_id"),
            "roster_format": roster_format,
            "field_size": field_size,
            "entry_fee_micro": entry_fee_micro,
            "entry_limit": entry_limit,
            "lock_at": _iso(lock_at),
            "late_swap": {
                "enabled": late_swap["enabled"],
                "policy": _string(late_swap.get("policy"), label="late_swap policy"),
                "state_at_freeze": "prelock",
            },
        },
        "payout_ladder": payout_ladder,
        "source_identities": normalized_sources,
        "book_bindings": normalized_bindings,
        "correction_lineage": {
            "revision": revision,
            "supersedes_manifest_sha256": supersedes,
            "reason": reason,
        },
    }
    # Payout lookup is an implementation detail returned alongside normalized
    # bytes, never an unreceipted mutation of the manifest.
    normalized_bytes = _canonical_bytes(normalized)
    normalized["_payout_by_rank"] = payout_by_rank
    return normalized, normalized_bytes


def _money_micro(value: object, *, label: str) -> int:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        _fail(f"{label} is missing")
    try:
        amount = Decimal(str(value)) * MICRO_DOLLARS
    except Exception as exc:
        raise CaptureRehearsalError(f"{label} is not numeric") from exc
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _reconcile_payouts(
    entries: pd.DataFrame, payout_by_rank: Mapping[int, int]
) -> dict[str, object]:
    discrepancies: list[str] = []
    maximum_residual = Decimal(0)
    for score, tied in entries.groupby("points", sort=False):
        rank = int(tied["rank"].iloc[0])
        tie_size = len(tied)
        scheduled = sum(
            int(payout_by_rank.get(position, 0))
            for position in range(rank, rank + tie_size)
        )
        expected_each = Decimal(scheduled) / Decimal(tie_size)
        actuals = {
            _money_micro(value, label=f"rank {rank} actual payout")
            for value in tied["payout"].tolist()
        }
        if len(actuals) != 1:
            discrepancies.append(f"tied entries disagree on payout at rank {rank}")
            continue
        residual = abs(Decimal(next(iter(actuals))) - expected_each)
        maximum_residual = max(maximum_residual, residual)
        if residual > CENT_MICRO:
            discrepancies.append(
                f"split payout does not reconcile at rank {rank} score {score}"
            )
    if discrepancies:
        _fail("; ".join(discrepancies))
    observed = sum(
        _money_micro(value, label="entry actual payout")
        for value in entries["payout"].tolist()
    )
    scheduled = sum(int(value) for value in payout_by_rank.values())
    if abs(observed - scheduled) > len(entries) * CENT_MICRO:
        _fail("observed field payouts do not reconcile to the payout ladder")
    winner_rows = entries.loc[entries["rank"].eq(1)].copy()
    return {
        "payout_reconciled": True,
        "scheduled_prize_pool_micro": scheduled,
        "observed_prize_pool_micro": observed,
        "maximum_tie_rounding_residual_micro": int(maximum_residual),
        "winner_score_micropoints": _money_micro(
            winner_rows["points"].max(), label="winner score"
        ),
        "first_place_tie_count": len(winner_rows),
        "winner_entry_ids": sorted(winner_rows["entry_id"].astype(str).tolist()),
        "winner_duplicate_keys": sorted(
            winner_rows["duplicate_key"].astype(str).unique().tolist()
        ),
    }


def _json_safe(value: object) -> object:
    if isinstance(value, (datetime, pd.Timestamp)):
        return _iso(value.to_pydatetime() if isinstance(value, pd.Timestamp) else value)
    if value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item") and callable(value.item):
        return _json_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    return value


def _frame_identity(frame: pd.DataFrame, *, sort_by: list[str]) -> dict[str, object]:
    ordered = frame.sort_values(sort_by, kind="mergesort").reset_index(drop=True)
    records = _json_safe(ordered.to_dict(orient="records"))
    assert isinstance(records, list)
    return {
        "row_count": len(ordered),
        "columns": list(ordered.columns),
        "rows_sha256": _sha256(_canonical_bytes(records)),
    }


def rehearse_capture(
    *,
    standings_path: str | Path,
    manifest_path: str | Path,
    captured_at: str,
    rehearsed_at: str,
    confirm_settled: bool,
    confirm_full_field: bool,
) -> dict[str, object]:
    """Run one complete local rehearsal and return a self-hashed receipt."""
    manifest_file = Path(manifest_path)
    if not manifest_file.is_file():
        _fail(f"contest manifest is not a file: {manifest_file}")
    manifest_raw_bytes = manifest_file.read_bytes()
    try:
        manifest_raw = json.loads(manifest_raw_bytes)
    except json.JSONDecodeError as exc:
        raise CaptureRehearsalError("contest manifest is not valid JSON") from exc
    normalized, normalized_bytes = _normalize_manifest(
        manifest_raw, manifest_path=manifest_file
    )
    payout_by_rank = normalized.pop("_payout_by_rank")
    assert isinstance(payout_by_rank, Mapping)
    contest = normalized["contest"]
    assert isinstance(contest, Mapping)
    capture_at_dt = _timestamp(captured_at, label="captured_at")
    rehearsal_at_dt = _timestamp(rehearsed_at, label="rehearsed_at")
    lock_at = _timestamp(contest["lock_at"], label="contest lock_at")
    if capture_at_dt <= lock_at:
        _fail("representative standings capture must occur after slate lock")
    if normalized["rehearsal_fixture"] is False and rehearsal_at_dt < capture_at_dt:
        _fail("a real-data rehearsal cannot precede its standings capture")
    if confirm_settled is not True or confirm_full_field is not True:
        _fail("explicit confirm_settled and confirm_full_field are required")

    # This call is the production validator itself, with apply=False hardcoded.
    # It performs no GCS or BigQuery call.
    capture = ownership_import.capture_full_field(
        str(standings_path),
        season=int(contest["season"]),
        week=int(contest["week"]),
        contest_id=str(contest["contest_id"]),
        contest_name=str(contest["contest_name"]),
        expected_entries=int(contest["field_size"]),
        captured_at=_iso(capture_at_dt),
        bucket_name="local-rehearsal",
        confirm_settled=confirm_settled,
        confirm_full_field=confirm_full_field,
        apply=False,
    )
    if capture.get("status") != "validated-only":
        _fail("production capture validator did not remain validation-only")
    if capture.get("evidence_timing") != ownership_import.EVIDENCE_TIMING:
        _fail("production capture validator did not confirm post-settlement timing")
    captured_contest = _mapping(capture.get("contest"), label="captured contest")
    if (
        captured_contest.get("roster_format") != contest["roster_format"]
        or captured_contest.get("observed_entries") != contest["field_size"]
    ):
        _fail("captured field differs from the pre-lock contest manifest")

    source = _mapping(capture.get("source"), label="capture source")
    validated = ownership_import.validate_full_field_capture(
        standings_path, expected_entries=int(contest["field_size"])
    )
    if (
        validated.get("source_sha256") != source.get("sha256")
        or validated.get("source_bytes") != source.get("bytes")
    ):
        _fail("standings source changed between validation reads")
    entries = validated["entries"]
    ownership = validated["ownership"]
    if not isinstance(entries, pd.DataFrame) or not isinstance(ownership, pd.DataFrame):
        _fail("production validator did not return entry and ownership frames")
    payout_receipt = _reconcile_payouts(entries, payout_by_rank)

    source_receipt = dict(source)
    if normalized["rehearsal_fixture"] is True:
        source_receipt["simulated_captured_at"] = source_receipt.pop("captured_at")
        source_receipt["capture_time_basis"] = "simulated_operator_supplied"
        source_receipt["timestamp_role"] = "representative_simulation"
    common = {
        "imported_at": capture_at_dt,
        "captured_at": capture_at_dt,
        "capture_id": str(capture["capture_id"]),
        "season": int(contest["season"]),
        "week": int(contest["week"]),
        "contest_id": str(contest["contest_id"]),
        "contest_name": str(contest["contest_name"]),
        "expected_entries": int(contest["field_size"]),
        "source_sha256": str(source["sha256"]),
        "source_bytes": int(source["bytes"]),
        "source_uri": str(source["uri"]),
    }
    entry_load = ownership_import._with_capture_columns(entries, **common)
    ownership_load = ownership_import._with_capture_columns(ownership, **common)
    warehouse = _mapping(capture.get("warehouse"), label="warehouse plan")

    manifest_identity = {
        "uri": manifest_file.name,
        "sha256": _sha256(manifest_raw_bytes),
        "bytes": len(manifest_raw_bytes),
        "semantic_sha256": _sha256(normalized_bytes),
    }
    binding_rows = normalized["book_bindings"]
    assert isinstance(binding_rows, list)
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "mode": "local-validation-only",
        "rehearsal_fixture": normalized["rehearsal_fixture"],
        "timeline": {
            "rehearsed_at": _iso(rehearsal_at_dt),
            "representative_capture_at": _iso(capture_at_dt),
            "representative_capture_is_simulated": normalized[
                "rehearsal_fixture"
            ],
        },
        "network_or_cloud_reads_performed": False,
        "external_writes_performed": False,
        "outcome_access": {
            "settlement_values_read": True,
            "synthetic_outcomes_read": normalized["rehearsal_fixture"],
            "live_realized_outcomes_read": not normalized["rehearsal_fixture"],
            "outcome_bearing_when_rehearsal_fixture_false": True,
        },
        "scientific_or_production_evidence_allowed": False,
        "apply_eligible": False,
        "contest_manifest_identity": manifest_identity,
        "contest_manifest": normalized,
        "capture_validation": {
            "capture_version": capture["capture_version"],
            "capture_id": capture["capture_id"],
            "status": capture["status"],
            "apply_required_for_live_capture": capture["apply_required"],
            "source": source_receipt,
            "contest": captured_contest,
            "validation": capture["validation"],
        },
        "settlement_rehearsal": payout_receipt,
        "book_binding_summary": {
            "paid_book_count": sum(row["purpose"] == "paid" for row in binding_rows),
            "shadow_book_count": sum(
                row["purpose"] == "shadow" for row in binding_rows
            ),
            "paid_entry_count": sum(
                int(row["entry_count"])
                for row in binding_rows
                if row["purpose"] == "paid"
            ),
            "all_books_frozen_before_lock": True,
        },
        "warehouse_structural_rehearsal": {
            "entries_table": str(warehouse["entries_table"]).rsplit(".", 1)[-1],
            "ownership_table": str(warehouse["ownership_table"]).rsplit(".", 1)[-1],
            "dataset_resolution_deferred_to_live_settings": True,
            "live_destination_identity_reproduced": False,
            "entries_load_job_id": warehouse["entries_load_job_id"],
            "ownership_load_job_id": warehouse["ownership_load_job_id"],
            "entries_payload": _frame_identity(entry_load, sort_by=["entry_id"]),
            "ownership_payload": _frame_identity(
                ownership_load, sort_by=["display_name", "roster_position"]
            ),
            "load_calls_performed": 0,
        },
        "checks": {
            "contest_identity_matches": True,
            "complete_field_count_matches": True,
            "entry_ids_unique": True,
            "competition_ranks_reproduced": True,
            "settled_time_reproduced": True,
            "rosters_parse_and_are_dk_classic_shape": True,
            "ownership_reproduced_from_field": True,
            "payout_ladder_reconciles_including_ties": True,
            "contest_sources_reopened_by_content_identity": True,
            "paid_and_shadow_books_reopened_by_content_identity": True,
            "correction_lineage_valid": True,
            "warehouse_structural_payloads_prepared_without_load": True,
        },
        "complete": True,
    }
    rehearsal_id = _sha256(
        _canonical_bytes(
            {
                "manifest_semantic_sha256": manifest_identity["semantic_sha256"],
                "capture_id": capture["capture_id"],
                "rehearsed_at": _iso(rehearsal_at_dt),
            }
        )
    )
    body["rehearsal_id"] = rehearsal_id
    body["receipt_sha256"] = _sha256(_canonical_bytes(body))
    return body


def receipt_bytes(receipt: Mapping[str, object]) -> bytes:
    """Return the human-readable canonical receipt representation."""
    return (
        json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def write_receipt_create_only(
    path: str | Path, receipt: Mapping[str, object]
) -> str:
    """Create one local receipt; accept only a byte-identical retry."""
    target = Path(path)
    payload = receipt_bytes(receipt)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise CaptureRehearsalError(
                f"create-only receipt conflict at {target}"
            )
        return "already-identical"
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return "created"
