"""Validate and import a DraftKings full contest-standings CSV.

DK's "Export to CSV" on any contest's standings page produces a file with
entry rows on the left and a player summary block on the right; the summary
columns are `Player`, `Roster Position`, `%Drafted`, `FPTS`. That summary —
one row per player with actual ownership — is what we keep.

There is no public API for this.  The recommended 2026 workflow is the
manual-safe ``nfl-dfs capture-dk-standings`` command: it validates by default
and writes only with an explicit ``--apply``.  Applying archives the exact
source bytes create-only before loading deterministic, retry-safe warehouse
jobs.  The older ``import-ownership`` command remains for historical imports.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..bq import load_dataframe
from ..config import settings

log = logging.getLogger(__name__)

PLAYER_COL = "Player"
REQUIRED = {PLAYER_COL, "%Drafted"}
SLOT_RE = re.compile(r"(?:^|\s)(CPT|FLEX|QB|RB|WR|TE|DST|K)\s+")
CAPTURE_VERSION = "dk-full-field-v1"
DEFAULT_ARCHIVE_PREFIX = "operator/dk-contest-standings/v1"
EVIDENCE_TIMING = "post_settlement"
CLASSIC_SHAPE = Counter({"QB": 1, "RB": 2, "WR": 3, "TE": 1,
                         "FLEX": 1, "DST": 1})
SHOWDOWN_SHAPE = Counter({"CPT": 1, "FLEX": 5})


def _read_export(path: str | Path) -> pd.DataFrame:
    return _parse_export_bytes(_read_source_bytes(path), path)


def _read_source_bytes(path: str | Path) -> bytes:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"standings source is not a file: {source}")
    if source.stat().st_size <= 0:
        raise ValueError(f"standings source is empty: {source}")
    payload = source.read_bytes()
    if not payload:
        raise ValueError(f"standings source is empty: {source}")
    return payload


def _parse_export_bytes(payload: bytes, source: str | Path) -> pd.DataFrame:
    # String-first is deliberate: EntryId is an external identifier and must
    # not lose digits through pandas' numeric inference.
    try:
        return pd.read_csv(io.BytesIO(payload), dtype=str)
    except Exception as exc:
        raise ValueError(f"could not parse standings CSV {source}: {exc}") from exc


def _numeric(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(
        series.astype("string").str.replace(",", "", regex=False),
        errors="coerce",
    )


def _money(series: pd.Series | None, index: pd.Index) -> pd.Series:
    if series is None:
        return pd.Series(float("nan"), index=index, dtype="float64")
    values = (
        series.astype("string")
        .str.strip()
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    )
    return pd.to_numeric(values, errors="coerce")


def _parse_standings_frame(raw: pd.DataFrame, source: str | Path) -> pd.DataFrame:
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(
            f"{source} does not look like a DK contest-standings export; "
            f"missing columns {sorted(missing)}"
        )
    selected = raw[raw[PLAYER_COL].notna()].copy()
    out = pd.DataFrame(
        {
            "display_name": selected[PLAYER_COL].astype(str).str.strip(),
            "roster_position": (
                selected["Roster Position"].fillna("").astype(str).str.strip()
                if "Roster Position" in selected else ""
            ),
            "pct_drafted": pd.to_numeric(
                selected["%Drafted"].astype("string").str.rstrip("%"),
                errors="coerce",
            ),
            "fpts": _numeric(selected.get("FPTS")),
        }
    )
    if out.empty:
        raise ValueError(f"no player ownership rows found in {source}")
    if out.pct_drafted.isna().any():
        raise ValueError(f"{source}: ownership block contains invalid %Drafted values")
    if out.display_name.eq("").any():
        raise ValueError(f"{source}: ownership block contains an empty player name")
    return out.reset_index(drop=True)


def parse_standings_csv(path: str | Path) -> pd.DataFrame:
    """Extract the per-player ownership block from a standings export."""
    return _parse_standings_frame(_read_export(path), path)


def parse_lineup_slots(lineup: str) -> list[dict[str, str]]:
    """Parse a DK lineup into ordered ``[{slot, player}, ...]`` records.

    Splitting at token boundaries preserves names losslessly and works for
    both Classic (nine slots) and Showdown (CPT plus five FLEX slots).
    """
    text = str(lineup).strip()
    matches = list(SLOT_RE.finditer(text))
    slots: list[dict[str, str]] = []
    for ix, match in enumerate(matches):
        end = matches[ix + 1].start() if ix + 1 < len(matches) else len(text)
        player = text[match.end():end].strip()
        if not player:
            raise ValueError(f"empty player after {match.group(1)} in lineup {text!r}")
        slots.append({"slot": match.group(1), "player": player})
    return slots


def _roster_format(slots: list[dict[str, str]]) -> str:
    shape = Counter(item["slot"] for item in slots)
    if shape == CLASSIC_SHAPE:
        return "classic"
    if shape == SHOWDOWN_SHAPE:
        return "showdown"
    raise ValueError(
        "unexpected DraftKings roster shape "
        f"{dict(sorted(shape.items()))}; expected NFL Classic {dict(CLASSIC_SHAPE)} "
        f"or Showdown {dict(SHOWDOWN_SHAPE)}"
    )


def _duplicate_key(slots: list[dict[str, str]], roster_format: str) -> str:
    if roster_format == "classic":
        return "|".join(sorted(item["player"] for item in slots))
    captain = next(item["player"] for item in slots if item["slot"] == "CPT")
    flex = sorted(item["player"] for item in slots if item["slot"] == "FLEX")
    return f"CPT:{captain}|FLEX:" + "|".join(flex)


def _parse_entries_frame(raw: pd.DataFrame, source: str | Path) -> pd.DataFrame:
    need = {"Rank", "Lineup"}
    if not need <= set(raw.columns):
        raise ValueError(f"{source}: no entry block (missing {need - set(raw.columns)})")
    selected = (
        raw[raw["Lineup"].notna() & raw["Rank"].notna()]
        .copy()
        .reset_index(drop=True)
    )
    parsed = selected["Lineup"].astype(str).map(parse_lineup_slots)
    bad = parsed.map(len).eq(0)
    if bad.any():
        raise ValueError(f"{int(bad.sum())} entry lineups contained no DK slot tokens")

    formats: list[str] = []
    shape_errors: list[str] = []
    for slots in parsed:
        try:
            formats.append(_roster_format(slots))
        except ValueError as exc:
            shape_errors.append(str(exc))
            formats.append("invalid")
    if shape_errors:
        raise ValueError(
            f"{len(shape_errors)} entries have invalid roster shapes; "
            f"first={shape_errors[0]}"
        )

    ranks = _numeric(selected["Rank"])
    out = pd.DataFrame({
        "rank": ranks,
        "entry_id": (
            selected["EntryId"].fillna("").astype(str).str.strip()
            if "EntryId" in selected else selected.index.astype(str)
        ),
        "entry_name": (
            selected["EntryName"].fillna("").astype(str)
            if "EntryName" in selected else ""
        ),
        "points": _numeric(selected.get("Points")),
        "time_remaining_raw": (
            selected["TimeRemaining"].fillna("").astype(str).str.strip()
            if "TimeRemaining" in selected else ""
        ),
        "payout": _money(
            selected.get("Winnings", selected.get("Prize")), selected.index
        ),
        "payout_raw": (
            selected.get("Winnings", selected.get("Prize")).fillna("").astype(str)
            if ("Winnings" in selected or "Prize" in selected) else ""
        ),
        "lineup": selected["Lineup"].astype(str),
        "roster_format": formats,
    })
    out["lineup_slots_json"] = parsed.map(json.dumps)
    out["n_players"] = parsed.map(len).astype(int)
    out["players_key"] = parsed.map(
        lambda slots: "|".join(sorted(item["player"] for item in slots)))
    out["duplicate_key"] = [
        _duplicate_key(slots, roster_format)
        for slots, roster_format in zip(parsed, formats, strict=True)
    ]
    out["lineup_sha256"] = out["duplicate_key"].map(
        lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    )
    out["is_top20"] = out["rank"].le(20)
    out = out.dropna(subset=["rank"]).reset_index(drop=True)
    if out.empty or out["rank"].min() > 1:
        raise ValueError(f"{source}: entry block does not contain the contest winner")
    if not out["is_top20"].any():
        raise ValueError(f"{source}: entry block contains no top-20 entries")
    if (~out["rank"].mod(1).eq(0)).any():
        raise ValueError(f"{source}: entry ranks must be positive integers")
    out["rank"] = out["rank"].astype("int64")
    return out


def parse_entries_csv(path: str | Path) -> pd.DataFrame:
    """Extract the per-ENTRY rows (left block): every submitted lineup
    with rank and points. This is the joint-structure data the field/
    dupe modeling needs (in-season queue 10a/10b; RTS blueprint) — DK
    purges standings exports after ~4 days, so losing these rows at
    import time loses them forever. `players_key` (sorted, delimited)
    is the duplicate-grouping key; the raw lineup string is kept
    lossless for slot-level parsing later."""
    return _parse_entries_frame(_read_export(path), path)


def _validate_settled_time(values: pd.Series) -> None:
    for raw_value in values.fillna("").astype(str):
        value = raw_value.strip().lower()
        if value in {"0", "0.0", "00:00", "00:00:00"}:
            continue
        try:
            if float(value) == 0:
                continue
        except ValueError:
            pass
        raise ValueError(
            "standings export is not demonstrably settled: "
            f"TimeRemaining contains {raw_value!r}"
        )


def _validate_ownership_against_entries(
    entries: pd.DataFrame,
    ownership: pd.DataFrame,
) -> None:
    appearances: Counter[str] = Counter()
    for slots_json in entries.lineup_slots_json:
        appearances.update(item["player"] for item in json.loads(slots_json))
    denominator = float(len(entries))
    derived = {
        name: count * 100.0 / denominator
        for name, count in appearances.items()
    }
    summary = ownership.groupby("display_name").pct_drafted.sum().to_dict()
    missing = sorted(set(derived) - set(summary))
    unexpected = sorted(
        name for name in set(summary) - set(derived) if float(summary[name]) > 0.011
    )
    mismatched = sorted(
        name
        for name in set(derived) & set(summary)
        if abs(float(summary[name]) - derived[name]) > 0.011
    )
    if missing or unexpected or mismatched:
        raise ValueError(
            "ownership summary does not reproduce the complete entry field: "
            f"missing={missing[:3]} unexpected={unexpected[:3]} "
            f"pct_mismatch={mismatched[:3]}"
        )


def _validate_full_field_payload(
    path: str | Path,
    payload: bytes,
    *,
    expected_entries: int,
) -> dict[str, Any]:
    raw = _parse_export_bytes(payload, path)
    settlement_columns = {"EntryId", "Points", "TimeRemaining"}
    if missing := settlement_columns - set(raw.columns):
        raise ValueError(
            "full-field post-settlement capture is missing required columns "
            f"{sorted(missing)}"
        )
    entries = _parse_entries_frame(raw, path)
    ownership = _parse_standings_frame(raw, path)
    if len(entries) != expected_entries:
        raise ValueError(
            f"full-field count mismatch: expected {expected_entries}, "
            f"parsed {len(entries)}"
        )
    if entries.entry_id.eq("").any():
        raise ValueError("full-field capture requires a non-empty EntryId on every row")
    if entries.entry_id.duplicated().any():
        raise ValueError("full-field capture contains duplicate EntryId values")
    if entries["rank"].le(0).any():
        raise ValueError("entry ranks must be positive integers")
    if entries.points.isna().any():
        raise ValueError("post-settlement capture requires Points on every entry")
    if entries.roster_format.nunique() != 1:
        raise ValueError("full-field capture mixes Classic and Showdown lineups")
    for slots_json in entries.lineup_slots_json:
        names = [item["player"] for item in json.loads(slots_json)]
        if len(names) != len(set(names)):
            raise ValueError("an entry lineup contains the same player more than once")
    _validate_settled_time(entries.time_remaining_raw)

    # DK competition rank is one plus the number of entries with a strictly
    # greater score. This catches plausible-looking truncated/cross-wired rows.
    score_counts = entries.points.value_counts().sort_index(ascending=False)
    expected_rank_by_score: dict[float, int] = {}
    n_better = 0
    for score, count in score_counts.items():
        expected_rank_by_score[float(score)] = n_better + 1
        n_better += int(count)
    expected_ranks = entries.points.map(
        lambda score: expected_rank_by_score[float(score)]
    )
    if not entries["rank"].eq(expected_ranks).all():
        raise ValueError("entry ranks do not reproduce competition rank from Points")

    if ownership.pct_drafted.isna().any():
        raise ValueError("ownership block contains non-numeric %Drafted values")
    if (~ownership.pct_drafted.between(0, 100)).any():
        raise ValueError("ownership %Drafted values must be between 0 and 100")
    roster_format = str(entries.roster_format.iloc[0])
    expected_mass = 900.0 if roster_format == "classic" else 600.0
    ownership_mass = float(ownership.pct_drafted.sum())
    if abs(ownership_mass - expected_mass) > 2.0:
        raise ValueError(
            f"ownership mass {ownership_mass:.3f} is inconsistent with "
            f"{roster_format} expected mass {expected_mass:.1f}"
        )
    _validate_ownership_against_entries(entries, ownership)

    source = Path(path)
    dupes = entries.groupby("duplicate_key").size()
    return {
        "entries": entries,
        "ownership": ownership,
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "source_bytes": len(payload),
        "source_filename": source.name,
        "roster_format": roster_format,
        "ownership_mass": ownership_mass,
        "distinct_lineups": int(len(dupes)),
        "max_duplicate_count": int(dupes.max()),
        "winner_score": float(entries.loc[entries["rank"].eq(1), "points"].max()),
    }


def validate_full_field_capture(
    path: str | Path,
    *,
    expected_entries: int,
) -> dict[str, Any]:
    """Validate one complete, settled DK field without any external write."""
    if expected_entries <= 0:
        raise ValueError("expected_entries must be positive")
    payload = _read_source_bytes(path)
    return _validate_full_field_payload(
        path, payload, expected_entries=expected_entries
    )


def _captured_at(path: Path, value: str | None) -> tuple[datetime, str]:
    if value is None:
        return (
            datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            "source_file_mtime",
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("captured_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("captured_at must include a UTC offset")
    return parsed.astimezone(timezone.utc), "operator_supplied"


def _safe_component(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized or not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
        raise ValueError(f"{field} must contain only letters, digits, '.', '_' or '-'")
    return normalized


def _safe_prefix(value: str) -> str:
    normalized = value.strip().strip("/")
    if (
        not normalized
        or not re.fullmatch(r"[A-Za-z0-9._/-]+", normalized)
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        raise ValueError("archive_prefix must be a non-empty safe object prefix")
    return normalized


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _archive_bytes_create_only(
    *,
    bucket_name: str,
    object_name: str,
    payload: bytes,
    content_type: str,
) -> str:
    """Create one immutable GCS object, accepting only byte-identical retry."""
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    blob = storage.Client(project=settings.project).bucket(bucket_name).blob(object_name)
    try:
        blob.upload_from_string(
            payload,
            content_type=content_type,
            if_generation_match=0,
        )
        return "created"
    except PreconditionFailed:
        if blob.download_as_bytes() != payload:
            raise RuntimeError(
                f"create-only archive conflict at gs://{bucket_name}/{object_name}"
            )
        return "already-identical"


def _preflight_warehouse_contract() -> None:
    """Fail before archival if an existing destination cannot accept v1."""
    from google.api_core.exceptions import NotFound

    from ..bq import client

    contracts = {
        f"{settings.raw}.contest_entries": {
            "partition": "imported_at",
            "clustering": ["season", "week", "contest_id"],
            "schema": {
                "imported_at": "TIMESTAMP",
                "season": "INTEGER",
                "week": "INTEGER",
                "contest_id": "STRING",
                "rank": "INTEGER",
                "entry_id": "STRING",
                "points": "FLOAT",
                "lineup": "STRING",
                "players_key": "STRING",
            },
        },
        f"{settings.raw}.contest_ownership": {
            "partition": "imported_at",
            "clustering": [],
            "schema": {
                "imported_at": "TIMESTAMP",
                "season": "INTEGER",
                "week": "INTEGER",
                "contest_id": "STRING",
                "display_name": "STRING",
                "pct_drafted": "FLOAT",
            },
        },
    }
    aliases = {"INT64": "INTEGER", "FLOAT64": "FLOAT", "BOOL": "BOOLEAN"}
    c = client()
    for table_id, contract in contracts.items():
        try:
            table = c.get_table(table_id)
        except NotFound:
            continue
        partition = getattr(getattr(table, "time_partitioning", None), "field", None)
        clustering = list(getattr(table, "clustering_fields", None) or [])
        if partition != contract["partition"] or clustering != contract["clustering"]:
            raise RuntimeError(
                f"warehouse table {table_id} has partition/clustering "
                f"{partition!r}/{clustering!r}; expected "
                f"{contract['partition']!r}/{contract['clustering']!r}"
            )
        actual = {
            field.name: aliases.get(field.field_type.upper(), field.field_type.upper())
            for field in table.schema
        }
        missing = sorted(set(contract["schema"]) - set(actual))
        wrong = sorted(
            name for name, expected in contract["schema"].items()
            if name in actual and actual[name] != expected
        )
        if missing or wrong:
            raise RuntimeError(
                f"warehouse table {table_id} is incompatible: "
                f"missing={missing} wrong_types={wrong}"
            )


def _with_capture_columns(
    frame: pd.DataFrame,
    *,
    imported_at: datetime,
    captured_at: datetime,
    capture_id: str,
    season: int,
    week: int,
    contest_id: str,
    contest_name: str,
    expected_entries: int,
    source_sha256: str,
    source_bytes: int,
    source_uri: str,
) -> pd.DataFrame:
    out = frame.copy()
    columns: list[tuple[str, Any]] = [
        ("imported_at", imported_at),
        ("captured_at", captured_at),
        ("evidence_timing", EVIDENCE_TIMING),
        ("capture_version", CAPTURE_VERSION),
        ("capture_id", capture_id),
        ("import_id", capture_id),
        ("season", season),
        ("week", week),
        ("contest_id", contest_id),
        ("contest_name", contest_name),
        ("expected_entries", expected_entries),
        ("source_sha256", source_sha256),
        ("source_bytes", source_bytes),
        ("source_uri", source_uri),
    ]
    for offset, (name, value) in enumerate(columns):
        out.insert(offset, name, value)
    return out


def capture_full_field(
    path: str,
    *,
    season: int,
    week: int,
    contest_id: str,
    contest_name: str,
    expected_entries: int,
    captured_at: str | None = None,
    bucket_name: str | None = None,
    archive_prefix: str = DEFAULT_ARCHIVE_PREFIX,
    confirm_settled: bool = False,
    confirm_full_field: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    """Validate, then optionally archive and import one complete DK field.

    Validation is the default and has no GCP side effects. ``apply=True`` is
    create-only: the exact CSV is archived first, deterministic BigQuery load
    job ids make retries non-duplicating, and the receipt is archived last.
    """
    if season < 2026 or not 1 <= week <= 22:
        raise ValueError("full-field capture supports season >= 2026 and weeks 1-22")
    safe_contest_id = _safe_component(contest_id, "contest_id")
    if not safe_contest_id.isdigit():
        raise ValueError("contest_id must be the numeric DraftKings contest ID")
    contest_name = contest_name.strip()
    if not contest_name:
        raise ValueError("contest_name is required")
    prefix = _safe_prefix(archive_prefix)
    bucket = _safe_component(bucket_name or settings.gcs_bucket, "bucket_name")
    source_path = Path(path)
    if not re.search(
        rf"(?:^|\D){re.escape(safe_contest_id)}(?:\D|$)", source_path.name
    ):
        raise ValueError(
            f"contest_id {safe_contest_id} is not present in source filename "
            f"{source_path.name!r}"
        )
    if apply and not confirm_settled:
        raise ValueError("--apply requires explicit --confirm-settled")
    if apply and not confirm_full_field:
        raise ValueError("--apply requires explicit --confirm-full-field")
    captured, capture_time_basis = _captured_at(source_path, captured_at)
    if expected_entries <= 0:
        raise ValueError("expected_entries must be positive")
    source_payload = _read_source_bytes(source_path)
    validated = _validate_full_field_payload(
        source_path, source_payload, expected_entries=expected_entries
    )
    captured_iso = captured.isoformat().replace("+00:00", "Z")
    evidence_timing = (
        EVIDENCE_TIMING if confirm_settled
        else "settlement_pending_operator_confirmation"
    )

    identity = {
        "capture_version": CAPTURE_VERSION,
        "season": season,
        "week": week,
        "contest_id": safe_contest_id,
        "contest_name": contest_name,
        "expected_entries": expected_entries,
        "confirm_full_field": confirm_full_field,
        "confirm_settled": confirm_settled,
        "captured_at": captured_iso,
        "capture_time_basis": capture_time_basis,
        "evidence_timing": evidence_timing,
        "source_sha256": validated["source_sha256"],
        "source_bytes": validated["source_bytes"],
        "archive_bucket": bucket,
        "archive_prefix": prefix,
    }
    capture_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
    object_root = (
        f"{prefix}/season={season}/week={week:02d}/"
        f"contest_id={safe_contest_id}/capture_id={capture_id}"
    )
    source_object = f"{object_root}/source.csv"
    receipt_object = f"{object_root}/receipt.json"
    source_uri = f"gs://{bucket}/{source_object}"
    entries_job_id = f"dk_entries_{capture_id}"
    ownership_job_id = f"dk_ownership_{capture_id}"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "capture_version": CAPTURE_VERSION,
        "capture_id": capture_id,
        "evidence_timing": evidence_timing,
        "source": {
            "uri": source_uri,
            "sha256": validated["source_sha256"],
            "bytes": validated["source_bytes"],
            "original_filename": validated["source_filename"],
            "captured_at": captured_iso,
            "capture_time_basis": capture_time_basis,
        },
        "contest": {
            "season": season,
            "week": week,
            "contest_id": safe_contest_id,
            "contest_name": contest_name,
            "expected_entries": expected_entries,
            "observed_entries": len(validated["entries"]),
            "ownership_rows": len(validated["ownership"]),
            "roster_format": validated["roster_format"],
            "metadata_basis": (
                "operator_confirmed_dk_page_and_filename_contest_id_checked"
                if confirm_full_field else
                "operator_confirmation_pending_filename_contest_id_checked"
            ),
        },
        "validation": {
            "settled_points_complete": True,
            "entry_ids_unique": True,
            "competition_ranks_reproduced": True,
            "ownership_reproduced_from_entries": True,
            "operator_confirmed_settled": confirm_settled,
            "operator_confirmed_full_field": confirm_full_field,
            "operator_confirmed_contest_metadata": confirm_full_field,
            "field_size_basis": "operator_confirmed_dk_displayed_entry_count",
            "ownership_mass": validated["ownership_mass"],
            "distinct_lineups": validated["distinct_lineups"],
            "max_duplicate_count": validated["max_duplicate_count"],
            "winner_score": validated["winner_score"],
        },
        "warehouse": {
            "entries_table": f"{settings.raw}.contest_entries",
            "ownership_table": f"{settings.raw}.contest_ownership",
            "deterministic_imported_at": captured_iso,
            "entries_load_job_id": entries_job_id,
            "ownership_load_job_id": ownership_job_id,
        },
        "receipt_uri": f"gs://{bucket}/{receipt_object}",
    }
    if not apply:
        return {**manifest, "status": "validated-only", "apply_required": True}

    _preflight_warehouse_contract()
    source_disposition = _archive_bytes_create_only(
        bucket_name=bucket,
        object_name=source_object,
        payload=source_payload,
        content_type="text/csv",
    )
    # A deterministic value is required because the BigQuery job id is
    # create-only. It represents when these bytes became available, while the
    # job metadata/receipt record the later execution itself.
    imported_at = captured
    common = {
        "imported_at": imported_at,
        "captured_at": captured,
        "capture_id": capture_id,
        "season": season,
        "week": week,
        "contest_id": safe_contest_id,
        "contest_name": contest_name,
        "expected_entries": expected_entries,
        "source_sha256": validated["source_sha256"],
        "source_bytes": validated["source_bytes"],
        "source_uri": source_uri,
    }
    entries = _with_capture_columns(validated["entries"], **common)
    ownership = _with_capture_columns(validated["ownership"], **common)
    load_dataframe(
        entries,
        "contest_entries",
        write_disposition="WRITE_APPEND",
        partition_field="imported_at",
        clustering_fields=("season", "week", "contest_id"),
        job_id=entries_job_id,
    )
    load_dataframe(
        ownership,
        "contest_ownership",
        write_disposition="WRITE_APPEND",
        partition_field="imported_at",
        job_id=ownership_job_id,
    )
    receipt_disposition = _archive_bytes_create_only(
        bucket_name=bucket,
        object_name=receipt_object,
        payload=_canonical_json(manifest),
        content_type="application/json",
    )
    log.info(
        "Captured %d complete entries and %d ownership rows for %s W%d "
        "contest %s (source=%s receipt=%s)",
        len(entries), len(ownership), season, week, safe_contest_id,
        source_disposition, receipt_disposition,
    )
    return {
        **manifest,
        "status": "applied",
        "source_archive_disposition": source_disposition,
        "receipt_archive_disposition": receipt_disposition,
    }


def run(
    path: str,
    season: int,
    week: int,
    contest_id: str,
    contest_name: str | None = None,
) -> int:
    # Parse and validate BOTH irreplaceable blocks before writing either one.
    # DK standings expire quickly; a successful job must never mean
    # "ownership landed but all entry-level lineup evidence disappeared."
    df = parse_standings_csv(path)
    entries = parse_entries_csv(path)
    imported_at = datetime.now(timezone.utc)
    import_id = hashlib.sha256(
        Path(path).read_bytes()
        + f"|{season}|{week}|{contest_id}".encode()
    ).hexdigest()
    df.insert(0, "imported_at", imported_at)
    df.insert(1, "import_id", import_id)
    df.insert(2, "season", season)
    df.insert(3, "week", week)
    df.insert(4, "contest_id", contest_id)
    df.insert(5, "contest_name", contest_name or "")
    entries.insert(0, "imported_at", imported_at)
    entries.insert(1, "import_id", import_id)
    entries.insert(2, "season", season)
    entries.insert(3, "week", week)
    entries.insert(4, "contest_id", contest_id)
    entries.insert(5, "contest_name", contest_name or "")

    # Entries load first: if its schema/parser contract fails, ownership is
    # not allowed to create a falsely-green import. Both loads still surface
    # normally to Cloud Run on any warehouse error.
    load_dataframe(entries, "contest_entries", write_disposition="WRITE_APPEND")
    load_dataframe(df, "contest_ownership", write_disposition="WRITE_APPEND")
    dupes = entries.groupby("players_key").size()
    log.info(
        "Imported %d entries (%d top-20, %d distinct, max dupe %d) and %d "
        "ownership rows for %s wk %s contest %s",
        len(entries), int(entries.is_top20.sum()), len(dupes), int(dupes.max()),
        len(df), season, week, contest_id,
    )
    return len(df)
