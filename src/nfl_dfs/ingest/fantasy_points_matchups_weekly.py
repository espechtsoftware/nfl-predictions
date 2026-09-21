"""Staging loader for the pre-lock Fantasy Points live matchup captures.

The capture (``ops.fantasy_points_matchups``) validates and archives three
vendor exports per target week but never loaded them anywhere; this module is
the missing ``nfl_raw`` path.  It accepts two inputs and re-derives every gate
from the bytes on disk rather than trusting a manifest field:

* a ``schema_version`` 2 capture run directory (one ``validated``/``archived``
  attempt per report, all attempts preserved on disk); or
* a seal document such as ``reports/2026-09-09-week1-fantasy-points-live-
  matchup-capture-seal.json`` that names independently validated members from
  older ``schema_version`` 1 runs.

Row law
-------
One staged row is one vendor row, tagged with the target week it was captured
for, the source season the vendor aggregated, the capture time, the exact
source hash and run id.  The append key is
``(season, target_week, report, identity, team, opponent, source_sha256)``:
a second capture of the same target week with different bytes appends beside
the first (every pre-lock snapshot is kept; the shadow join picks the latest
one before kickoff), while re-running the loader on the same bytes appends
nothing.  A conflicting duplicate inside one export fails the whole import.

Nothing here touches the Route Share path; the player resolver and team map
are imported read-only from it.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from ..names import norm_name
from ..ops.fantasy_points_matchups import (
    CAPTURE_ID,
    MANIFEST_SCHEMA_VERSION,
    MATCHUPS,
    _csv_shape,
    _team,
    advance_ledger,
    expected_schedule_pairs,
    ledger_path,
    new_ledger,
    read_matchup_pairs,
    reconcile_team,
    source_regime,
    validate_matchup_pairs,
)
from .fantasy_points_advanced import _grouped_rows
from .fantasy_points_coverage import TEAM_NAMES
from .fantasy_points_route import _resolve_player, _sha256, _snapshot_maps


SEASON = 2026
REPORTS = tuple(definition.key for definition in MATCHUPS)
TABLES = {
    "qb-coverage-matchup": "fantasy_points_qb_coverage_matchup_weekly",
    "wr-coverage-matchup": "fantasy_points_wr_coverage_matchup_weekly",
    "line-matchups": "fantasy_points_line_matchup_weekly",
}
SEAL_STATUS = "COMPLETE_FROM_INDEPENDENTLY_VALIDATED_REPORTS"
KEY_COLUMNS = (
    "season", "target_week", "report", "identity", "team", "opponent",
    "source_sha256",
)

# Frozen group-qualified vendor headers, read from the sealed Week-1 exports.
# Any drift fails the import; widen the contract deliberately, never by
# autodetection.
EXPECTED_HEADERS: dict[str, tuple[str, ...]] = {
    "qb-coverage-matchup": (
        "Player Details::Rank", "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G", "Player Details::Season",
        "Player Details::OPP", "Matchup::DB", "Matchup::DB/G", "Matchup::FP/DB",
        "Matchup::EXP FP/DB", "Matchup::COV GRADE", "Man::DEF MAN %",
        "Man::DEF FP/DB", "Man::QB MAN %", "Man::QB FP/DB",
        "Cover 2::DEF COVER 2 %", "Cover 2::DEF FP/DB", "Cover 2::QB COVER 2 %",
        "Cover 2::QB FP/DB", "Cover 3::DEF COVER 3 %", "Cover 3::DEF FP/DB",
        "Cover 3::QB Cover 3 %", "Cover 3::QB FP/DB", "Cover 4::DEF COVER 4 %",
        "Cover 4::DEF FP/DB", "Cover 4::QB Cover 4 %", "Cover 4::QB FP/DB",
        "Cover 6::DEF COVER 6 %", "Cover 6::DEF FP/DB", "Cover 6::QB COVER 6 %",
        "Cover 6::QB FP/DB",
    ),
    "wr-coverage-matchup": (
        "Player Details::Rank", "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G", "Player Details::Season",
        "Player Details::OPP", "Matchup::RTE", "Matchup::RTE/G", "Matchup::FP/RR",
        "Matchup::EXP FP/RTE", "Matchup::COV GRADE", "Matchup::YPRR",
        "Man::DEF MAN %", "Man::DEF FP/DB", "Man::FP/RTE", "Man::RTE %",
        "Man::YPRR", "Cover 2::DEF COVER 2 %", "Cover 2::DEF FP/DB",
        "Cover 2::FP/RTE", "Cover 2::RTE %", "Cover 2::YPRR",
        "Cover 3::DEF COVER 3 %", "Cover 3::DEF FP/DB", "Cover 3::FP/RTE",
        "Cover 3::RTE %", "Cover 3::YPRR", "Cover 4::DEF COVER 4 %",
        "Cover 4::DEF FP/DB", "Cover 4::FP/RTE", "Cover 4::RTE %", "Cover 4::YPRR",
        "Cover 6::DEF COVER 6 %", "Cover 6::DEF FP/DB", "Cover 6::FP/RTE",
        "Cover 6::RTE %", "Cover 6::YPRR",
    ),
    "line-matchups": (
        "Team Details::Rank", "Team Details::Name", "Team Details::G",
        "Team Details::Season", "Team Details::Location", "Team Details::Team Name",
        "Offense Stats::RUSH GRADE", "Offense Stats::PASS GRADE",
        "Offense Stats::ADJ YBC/ATT", "Offense Stats::PRESS %",
        "Offense Stats::PrROE", "Offense Stats::Team", "Offense Stats::TM ATT",
        "Offense Stats::YBCO", "Defense Stats::Name", "Defense Stats::ADJ YBC/ATT",
        "Defense Stats::PRESS %", "Defense Stats::PrROE", "Defense Stats::ATT",
        "Defense Stats::YBCO",
    ),
}
IDENTITY_GROUPS = {"Player Details", "Team Details"}
IDENTITY_EXTRA = {"Offense Stats::Team", "Defense Stats::Name"}
GROUP_PREFIX = {
    "Player Details": "id", "Team Details": "id",
    "Offense Stats": "offense", "Defense Stats": "defense",
}


def metric_column(semantic: str) -> str:
    """``"Cover 3::QB Cover 3 %"`` -> ``"cover_3__qb_cover_3_pct"``."""
    group, name = semantic.split("::", 1)
    prefix = GROUP_PREFIX.get(group) or re.sub(
        r"[^a-z0-9]+", "_", group.lower()
    ).strip("_")
    body = name.lower().replace("%", " pct ").replace("/", " per ")
    body = re.sub(r"[^a-z0-9]+", "_", body).strip("_")
    return f"{prefix}__{body}"


def metric_columns(report: str) -> list[str]:
    return [
        metric_column(column) for column in EXPECTED_HEADERS[report]
        if column.split("::", 1)[0] not in IDENTITY_GROUPS
        and column not in IDENTITY_EXTRA
    ]


def _utc_timestamp(value: object, field: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"matchup capture has invalid {field}") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"matchup capture {field} is not timezone-aware")
    return stamp.tz_convert("UTC")


def _safe_relative(value: object) -> Path:
    relative = Path(str(value or ""))
    if not relative.name or relative != Path(relative.name):
        raise ValueError(f"matchup artifact path is unsafe: {value!r}")
    return relative


def _rederive_artifact(
    *,
    report: str,
    local_path: Path,
    claimed_sha256: str,
    claimed_bytes: int,
    retrieved_at: pd.Timestamp,
    expected: set[tuple[str, str]],
    first_kickoff: pd.Timestamp,
    target_week: int,
) -> dict[str, Any]:
    """Re-run every capture-time gate on the bytes actually on disk."""
    if not local_path.is_file():
        raise FileNotFoundError(local_path)
    digest = _sha256(local_path)
    if digest != claimed_sha256:
        raise ValueError(f"{report}: artifact hash differs from the record")
    if local_path.stat().st_size != int(claimed_bytes):
        raise ValueError(f"{report}: artifact byte count differs from the record")
    if retrieved_at >= first_kickoff:
        raise ValueError(f"{report}: retrieved at/after the target week's first kickoff")
    columns, _ = _grouped_rows(local_path)
    if tuple(columns) != EXPECTED_HEADERS[report]:
        raise ValueError(f"{report}: vendor header drift; refusing to stage")
    pairs, seasons, source_rows = read_matchup_pairs(local_path, report)
    gate = validate_matchup_pairs(pairs, expected, report=report)
    if not gate["passes"]:
        raise ValueError(
            f"{report}: schedule gate fails on re-derivation "
            f"(unexpected {gate['unexpected_pairs']}, missing {gate['missing_pairs']})"
        )
    regime = source_regime(seasons, SEASON, target_week)
    rows, width = _csv_shape(local_path)
    return {
        "sha256": digest,
        "bytes": int(claimed_bytes),
        "csv_rows_including_headers": rows,
        "max_csv_columns": width,
        "source_rows": source_rows,
        "source_seasons": sorted(seasons),
        "source_regime": regime,
        "schedule_gate": gate,
    }


def validate_run_dir(
    run_dir: str | Path,
    *,
    target_week: int,
    allow_partial: bool = False,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate a schema-2 capture run and return its stageable artifacts."""
    root = Path(run_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "matchup capture manifest schema must be "
            f"{MANIFEST_SCHEMA_VERSION} (older captures are staged through a seal)"
        )
    if manifest.get("capture_id") != CAPTURE_ID:
        raise ValueError("matchup capture manifest has the wrong capture id")
    if manifest.get("target_season") != SEASON:
        raise ValueError("matchup capture manifest is not the 2026 season")
    if manifest.get("target_week") != int(target_week):
        raise ValueError("matchup capture target week differs from request")
    if manifest.get("status") not in {"complete", "failed"}:
        raise ValueError("matchup capture manifest is still running")
    first_kickoff = _utc_timestamp(manifest.get("first_kickoff_utc"), "first_kickoff_utc")
    expected = {
        (str(team), str(opponent))
        for team, opponent in manifest.get("expected_schedule_pairs", [])
    }
    if not expected:
        raise ValueError("matchup capture manifest has no expected schedule pairs")
    validated = manifest.get("validated_reports") or {}
    reports = {
        report["key"]: report for report in manifest.get("reports", [])
        if report.get("status") in {"validated", "archived"}
    }
    if set(validated) != set(reports):
        raise ValueError("matchup capture validated_reports disagree with report statuses")
    missing = [key for key in REPORTS if key not in reports]
    if missing and not allow_partial:
        raise ValueError(
            f"matchup capture has no validated export for {missing}; "
            "pass allow_partial to stage the validated reports only"
        )
    artifacts: dict[str, dict[str, Any]] = {}
    for key, report in reports.items():
        if key not in REPORTS:
            raise ValueError(f"matchup capture names an unknown report {key!r}")
        if validated[key].get("sha256") != report.get("sha256"):
            raise ValueError(f"{key}: validated_reports hash differs from the report record")
        relative = _safe_relative(report.get("path"))
        retrieved = _utc_timestamp(report.get("retrieved_at_utc"), "retrieved_at_utc")
        derived = _rederive_artifact(
            report=key, local_path=root / relative,
            claimed_sha256=str(report.get("sha256")),
            claimed_bytes=int(report.get("bytes", -1)),
            retrieved_at=retrieved, expected=expected,
            first_kickoff=first_kickoff, target_week=int(target_week),
        )
        artifacts[key] = {
            **derived,
            "report": key,
            "path": relative.name,
            "local_path": root / relative,
            "run_dir": root,
            "attempt": int(report.get("attempt", 0)),
            "retrieved_at": retrieved,
            "source_url": str(report.get("source_url", "")),
            "source_run_id": str(manifest["run_id"]),
            "archive_uri": report.get("archive_uri"),
            "ledger_exists": ledger_path(root).is_file(),
        }
    capture = {
        "input_kind": "run-dir",
        "capture_ref": root.name,
        "target_season": SEASON,
        "target_week": int(target_week),
        "first_kickoff_utc": first_kickoff,
        "expected_pairs": expected,
        "run_status": manifest.get("status"),
        "missing_reports": missing,
    }
    return capture, artifacts


def validate_seal(
    seal_path: str | Path,
    *,
    target_week: int,
    output_root: str | Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate a seal of independently validated schema-1 run members."""
    seal_path = Path(seal_path)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if seal.get("schema_version") != 1:
        raise ValueError("matchup seal schema must be 1")
    if seal.get("capture_id") != CAPTURE_ID:
        raise ValueError("matchup seal has the wrong capture id")
    if seal.get("status") != SEAL_STATUS:
        raise ValueError(f"matchup seal status must be {SEAL_STATUS}")
    if seal.get("target_season") != SEASON:
        raise ValueError("matchup seal is not the 2026 season")
    if seal.get("target_week") != int(target_week):
        raise ValueError("matchup seal target week differs from request")
    first_kickoff = _utc_timestamp(seal.get("first_kickoff_utc"), "first_kickoff_utc")
    members = seal.get("members")
    if not isinstance(members, list) or sorted(
        member.get("report") for member in members
    ) != sorted(REPORTS):
        raise ValueError("matchup seal must name exactly the three reports once")
    root = Path(output_root)
    artifacts: dict[str, dict[str, Any]] = {}
    expected_pairs: set[tuple[str, str]] | None = None
    for member in members:
        key = str(member["report"])
        run_id = str(member.get("source_run_id", ""))
        if not run_id or run_id != Path(run_id).name:
            raise ValueError(f"{key}: seal member has an unsafe run id")
        run_dir = root / run_id
        run_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        if run_manifest.get("capture_id") != CAPTURE_ID or run_manifest.get(
            "target_week"
        ) != int(target_week) or run_manifest.get("target_season") != SEASON:
            raise ValueError(f"{key}: member run manifest identity differs from the seal")
        run_kickoff = _utc_timestamp(run_manifest.get("first_kickoff_utc"), "first_kickoff_utc")
        if run_kickoff != first_kickoff:
            raise ValueError(f"{key}: member run kickoff differs from the seal")
        pairs = {
            (str(team), str(opponent))
            for team, opponent in run_manifest.get("expected_schedule_pairs", [])
        }
        if expected_pairs is None:
            expected_pairs = pairs
        elif pairs != expected_pairs:
            raise ValueError(f"{key}: member runs disagree on the expected schedule")
        record = next(
            (
                report for report in run_manifest.get("reports", [])
                if report.get("key") == key and report.get("sha256") == member.get("sha256")
            ),
            None,
        )
        if record is None:
            raise ValueError(f"{key}: member run has no report record with the sealed hash")
        relative = _safe_relative(record.get("path"))
        retrieved = _utc_timestamp(member.get("retrieved_at_utc"), "retrieved_at_utc")
        if retrieved != _utc_timestamp(record.get("retrieved_at_utc"), "retrieved_at_utc"):
            raise ValueError(f"{key}: seal retrieval time differs from the run record")
        derived = _rederive_artifact(
            report=key, local_path=run_dir / relative,
            claimed_sha256=str(member.get("sha256")),
            claimed_bytes=int(member.get("bytes", -1)),
            retrieved_at=retrieved, expected=pairs,
            first_kickoff=first_kickoff, target_week=int(target_week),
        )
        artifacts[key] = {
            **derived,
            "report": key,
            "path": relative.name,
            "local_path": run_dir / relative,
            "run_dir": run_dir,
            "attempt": 1,
            "retrieved_at": retrieved,
            "source_url": str(member.get("source_url", "")),
            "source_run_id": run_id,
            "archive_uri": member.get("archive_uri"),
            "ledger_exists": ledger_path(run_dir).is_file(),
        }
    assert expected_pairs is not None
    capture = {
        "input_kind": "seal",
        "capture_ref": seal_path.name,
        "target_season": SEASON,
        "target_week": int(target_week),
        "first_kickoff_utc": first_kickoff,
        "expected_pairs": expected_pairs,
        "run_status": seal.get("status"),
        "missing_reports": [],
    }
    return capture, artifacts


def _numeric(value: str, *, report: str, column: str, row: int) -> float | None:
    text = value.strip()
    if text in {"", "-"}:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(
            f"{report}: non-numeric {column!r} {text!r} at source row {row}"
        ) from exc


def normalize_report(
    capture: dict[str, Any],
    artifact: dict[str, Any],
    snapshots: pd.DataFrame | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Turn one validated export into staged rows with full lineage."""
    report = str(artifact["report"])
    columns, rows = _grouped_rows(Path(artifact["local_path"]))
    if tuple(columns) != EXPECTED_HEADERS[report]:
        raise ValueError(f"{report}: vendor header drift; refusing to stage")
    expected: set[tuple[str, str]] = capture["expected_pairs"]
    player_report = report != "line-matchups"
    if player_report:
        if snapshots is None:
            raise ValueError(f"{report}: player resolution needs roster snapshots")
        by_name, by_season_team = _snapshot_maps(snapshots)
    metric_names = metric_columns(report)
    metric_semantics = [
        column for column in columns
        if column.split("::", 1)[0] not in IDENTITY_GROUPS
        and column not in IDENTITY_EXTRA
    ]
    (source_season,) = artifact["source_seasons"]
    records: list[dict[str, Any]] = []
    statuses: list[str] = []
    for index, row in enumerate(rows):
        source_row = index + 3  # two header rows, 1-based
        if player_report:
            name = row["Player Details::Name"].strip()
            vendor_team = row["Player Details::Team"].strip()
            pos = row["Player Details::POS"].strip().upper()
            opponent = _team(row["Player Details::OPP"])
            games = row["Player Details::G"].strip()
            season_cell = row["Player Details::Season"].strip()
            if not name or not vendor_team or not pos:
                raise ValueError(f"{report}: blank identity at source row {source_row}")
            if report == "qb-coverage-matchup" and pos != "QB":
                raise ValueError(f"{report}: non-QB row at source row {source_row}")
            canonical = tuple(sorted({
                _team(part) for part in vendor_team.split(",") if part.strip()
            }))
            team = reconcile_team(_team(vendor_team), opponent, expected)
            if team is None:
                raise ValueError(
                    f"{report}: {name} {vendor_team!r} vs {opponent} is not a "
                    f"scheduled Week {capture['target_week']} pair"
                )
            normalized = norm_name(name)
            resolved_pos = "RB" if pos == "FB" else pos
            gsis_id, status = _resolve_player(
                SEASON, normalized, resolved_pos, canonical, by_name, by_season_team,
            )
            statuses.append(status)
            identity = gsis_id or f"UNRESOLVED:{normalized}:{resolved_pos}:{','.join(canonical)}"
            vendor_name = name
        else:
            vendor_name = row["Team Details::Name"].strip()
            vendor_team = row["Offense Stats::Team"].strip()
            defense_name = row["Defense Stats::Name"].strip()
            if defense_name not in TEAM_NAMES:
                raise ValueError(f"{report}: unknown defense {defense_name!r}")
            opponent = TEAM_NAMES[defense_name]
            team = _team(vendor_team)
            if (team, opponent) not in expected:
                raise ValueError(
                    f"{report}: {team} vs {opponent} is not a scheduled "
                    f"Week {capture['target_week']} pair"
                )
            canonical = (team,)
            pos = None
            resolved_pos = None
            normalized = None
            gsis_id, status = None, "team"
            identity = team
            games = row["Team Details::G"].strip()
            season_cell = row["Team Details::Season"].strip()
        if int(season_cell) != int(source_season):
            raise ValueError(f"{report}: mixed source season at source row {source_row}")
        record: dict[str, Any] = {
            "season": SEASON,
            "target_week": int(capture["target_week"]),
            "report": report,
            "identity": identity,
            "team": team,
            "opponent": opponent,
            "gsis_id": gsis_id,
            "resolution_status": status,
            "vendor_name": vendor_name,
            "normalized_name": normalized,
            "vendor_team": vendor_team,
            "canonical_teams": ",".join(canonical),
            "vendor_pos": pos,
            "pos": resolved_pos,
            "games": int(games) if games else None,
            "source_season": int(source_season),
            "source_regime": str(artifact["source_regime"]),
        }
        for semantic, column in zip(metric_semantics, metric_names):
            record[column] = _numeric(
                row[semantic], report=report, column=column, row=source_row,
            )
        record.update({
            "source_file": str(artifact["path"]),
            "source_sha256": str(artifact["sha256"]),
            "source_row": source_row,
            "source_retrieved_at": artifact["retrieved_at"],
            "source_run_id": str(artifact["source_run_id"]),
            "source_attempt": int(artifact["attempt"]),
            "first_kickoff_utc": capture["first_kickoff_utc"],
            "capture_ref": str(capture["capture_ref"]),
            "archive_uri": artifact.get("archive_uri"),
        })
        records.append(record)
    out = pd.DataFrame(records)
    if out.empty:
        raise ValueError(f"{report}: export has no rows")
    keys = list(KEY_COLUMNS)
    if out.duplicated(keys).any():
        bad = out.loc[out.duplicated(keys, keep=False), keys].head(5).to_dict("records")
        raise ValueError(f"{report}: duplicate identities inside one export: {bad}")
    audit = {
        "report": report,
        "source_rows": int(len(rows)),
        "normalized_rows": int(len(out)),
        "resolved_rows": int(out.gsis_id.notna().sum()),
        "unresolved_rows": int(statuses.count("unresolved")),
        "ambiguous_rows": int(statuses.count("ambiguous")),
        "teams": int(out.team.nunique()),
        "source_season": int(source_season),
        "source_regime": str(artifact["source_regime"]),
        "source_sha256": str(artifact["sha256"]),
        "source_run_id": str(artifact["source_run_id"]),
        "metric_columns": metric_names,
    }
    return out, audit


def rows_to_append(rows: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    """Return rows whose append key is absent from ``existing``.

    Same key means same bytes (the hash is part of the key), so an overlap is
    skipped, never compared or overwritten.  Duplicate keys already stored
    are a corrupted table and fail closed.
    """
    keys = list(KEY_COLUMNS)
    if missing := set(keys) - set(rows.columns):
        raise ValueError(f"staged rows missing {sorted(missing)}")
    if existing.empty:
        return rows.reset_index(drop=True)
    if missing := set(keys) - set(existing.columns):
        raise ValueError(f"existing matchup rows missing {sorted(missing)}")
    present = existing[keys].copy()
    if present.duplicated(keys).any():
        raise RuntimeError("existing matchup rows contain duplicate append keys")
    joined = rows.merge(present, on=keys, how="left", indicator=True)
    novel = joined.loc[joined._merge.eq("left_only")].drop(columns="_merge")
    return novel.reset_index(drop=True)


def _job_id(report: str, artifact: dict[str, Any], target_week: int) -> str:
    return (
        f"fp-matchup-weekly--{report}--s{SEASON}-w{int(target_week):02d}"
        f"--{str(artifact['sha256'])[:20]}"
    )


def _write_receipt(artifact: dict[str, Any], receipt: dict[str, Any]) -> Path:
    run_dir = Path(artifact["run_dir"])
    path = run_dir / f"staging-receipt-{artifact['report']}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def _record_staged(artifact: dict[str, Any], *, rows: int, table: str, now: datetime) -> None:
    run_dir = Path(artifact["run_dir"])
    key = str(artifact["report"])
    if not ledger_path(run_dir).is_file():
        # A schema-1 member run predates the ledger.  Its downloaded and
        # validated statuses were re-derived above from the bytes on disk,
        # and are recorded as such rather than assumed.
        new_ledger(run_dir, str(artifact["source_run_id"]), REPORTS)
        advance_ledger(
            run_dir, key, "downloaded", now=now, path=artifact["path"],
            sha256=artifact["sha256"], attempt=artifact["attempt"],
            rederived_by="fantasy_points_matchups_weekly",
        )
        advance_ledger(
            run_dir, key, "validated", now=now, path=artifact["path"],
            sha256=artifact["sha256"], attempt=artifact["attempt"],
            archive_uri=artifact.get("archive_uri"),
            rederived_by="fantasy_points_matchups_weekly",
        )
    advance_ledger(
        run_dir, key, "staged", now=now, path=artifact["path"],
        sha256=artifact["sha256"], table=table, rows=int(rows),
    )


def _existing_rows(table_ref: str, target_week: int):
    from google.api_core.exceptions import NotFound

    from ..bq import query_df

    try:
        frame = query_df(f"""
            SELECT season, target_week, report, identity, team, opponent,
                   source_sha256
            FROM `{table_ref}`
            WHERE season = @season AND target_week = @target_week
            """, params={"season": SEASON, "target_week": int(target_week)})
    except NotFound:
        return pd.DataFrame(columns=list(KEY_COLUMNS)), False
    return frame, True


def run(
    input_path: str | Path,
    *,
    target_week: int,
    write: bool = False,
    allow_partial: bool = False,
    output_root: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Audit one capture (run dir or seal) and optionally append it."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    if not 1 <= int(target_week) <= 18:
        raise ValueError("matchup target week must be between 1 and 18")
    input_path = Path(input_path)
    if input_path.is_dir():
        capture, artifacts = validate_run_dir(
            input_path, target_week=target_week, allow_partial=allow_partial,
        )
    elif input_path.is_file() and input_path.suffix == ".json":
        if output_root is None:
            raise ValueError("a seal needs output_root to locate its member runs")
        capture, artifacts = validate_seal(
            input_path, target_week=target_week, output_root=output_root,
        )
    else:
        raise ValueError(f"matchup input is neither a run directory nor a seal: {input_path}")
    if write:
        for key, artifact in artifacts.items():
            if not artifact.get("archive_uri"):
                raise ValueError(
                    f"{key}: no hash-addressed archive recorded; a write needs the "
                    "GCS object (re-run the capture with --archive)"
                )
    snapshots = None
    if any(key != "line-matchups" for key in artifacts):
        snapshots = query_df(f"""
            SELECT DISTINCT CAST(season AS INT64) AS season, gsis_id,
                   full_name AS name, position AS pos, team
            FROM `{settings.raw}.rosters_weekly`
            WHERE CAST(season AS INT64) = @season
              AND CAST(week AS INT64) <= @target_week
              AND gsis_id IS NOT NULL AND full_name IS NOT NULL
            """, params={"season": SEASON, "target_week": int(target_week)})
    stamp = now or datetime.now(UTC)
    audit: dict[str, Any] = {
        "input_kind": capture["input_kind"],
        "capture_ref": capture["capture_ref"],
        "season": SEASON,
        "target_week": int(target_week),
        "first_kickoff_utc": capture["first_kickoff_utc"].isoformat(),
        "run_status": capture["run_status"],
        "missing_reports": capture["missing_reports"],
        "allow_partial": bool(allow_partial),
        "write_requested": bool(write),
        "reports": {},
    }
    for key in REPORTS:
        if key not in artifacts:
            continue
        artifact = artifacts[key]
        rows, report_audit = normalize_report(capture, artifact, snapshots)
        table_ref = f"{settings.raw}.{TABLES[key]}"
        existing, table_existed = _existing_rows(table_ref, target_week)
        novel = rows_to_append(rows, existing)
        report_audit.update({
            "table": table_ref,
            "table_existed": bool(table_existed),
            "existing_rows_for_target_week": int(len(existing)),
            "append_rows": int(len(novel)),
            "archive_uri": artifact.get("archive_uri"),
            "status": "validated",
        })
        if write:
            if novel.empty:
                report_audit["write_disposition"] = "already-identical"
            else:
                payload = novel.copy()
                payload["ingested_at"] = stamp
                load_dataframe(
                    payload, table_ref, write_disposition="WRITE_APPEND",
                    job_id=_job_id(key, artifact, target_week),
                )
                report_audit["write_disposition"] = "appended"
            _record_staged(artifact, rows=len(novel), table=table_ref, now=stamp)
            report_audit["status"] = "staged"
            report_audit["receipt"] = str(_write_receipt(artifact, {
                **report_audit, "staged_at_utc": stamp.isoformat(),
            }))
        audit["reports"][key] = report_audit
    audit["status_counts"] = {
        status: sum(1 for item in audit["reports"].values() if item["status"] == status)
        for status in ("validated", "staged")
    }
    print("FP_MATCHUP_WEEKLY_IMPORT_JSON=" + json.dumps(audit, sort_keys=True, default=str))
    return audit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import-fantasy-points-matchups-weekly",
        description="Stage one validated live matchup capture into nfl_raw",
    )
    parser.add_argument("--input", required=True, type=Path,
                        help="a schema-2 capture run directory or a seal JSON")
    parser.add_argument("--target-week", required=True, type=int)
    parser.add_argument("--output-root", type=Path, default=None,
                        help="fantasy-points/automated root (needed for a seal)")
    parser.add_argument("--allow-partial", action="store_true",
                        help="stage the validated reports even if a report has none")
    parser.add_argument("--write", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run(
        args.input, target_week=args.target_week, write=args.write,
        allow_partial=args.allow_partial, output_root=args.output_root,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
