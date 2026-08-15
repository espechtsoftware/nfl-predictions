"""Append-only warehouse intake for the frozen 2026 SIS pass-tail views."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .sis_team_context import (
    KEY_COLUMNS,
    TABLE as TEAM_TABLE,
    TEAM_ABBREVIATIONS,
    _read_artifact,
)
from .sis_asoe import TABLE as ATTEMPT_TABLE
from ..ops import sis_downloads as sis


SEASON = 2026


def _load_manifest(input_dir: str | Path, *, target_week: int) -> tuple[Path, dict]:
    root = Path(input_dir)
    manifest = json.loads(
        (root / "pass-tail-weekly.manifest.json").read_text(encoding="utf-8")
    )
    result = json.loads(
        (root / "pass-tail-weekly.result.json").read_text(encoding="utf-8")
    )
    if manifest.get("schema_version") != 1:
        raise ValueError("SIS pass-tail weekly manifest schema must be 1")
    if manifest.get("version") != sis.PASS_TAIL_WEEKLY_VERSION:
        raise ValueError("SIS pass-tail weekly manifest version differs")
    if int(manifest.get("season", -1)) != SEASON:
        raise ValueError("SIS pass-tail weekly manifest has another season")
    if int(manifest.get("target_week", -1)) != int(target_week):
        raise ValueError("SIS pass-tail weekly target week differs")
    protocol = Path(
        "reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md"
    )
    protocol_hash = sis._sha256(protocol)
    if manifest.get("protocol_sha256") != protocol_hash:
        raise ValueError("SIS pass-tail weekly protocol hash differs")
    source_start = int(manifest.get("source_week_start", -1))
    source_end = int(manifest.get("source_week_end", -1))
    expected_identity = hashlib.sha256(
        (
            protocol_hash + f"|{sis.PASS_TAIL_WEEKLY_VERSION}|2026|"
            f"{int(target_week)}|{source_start}|{source_end}"
        ).encode()
    ).hexdigest()
    if manifest.get("acquisition_identity") != expected_identity:
        raise ValueError("SIS pass-tail weekly acquisition identity differs")
    reproduced = sis._analyze_pass_tail_weekly_manifest(root, manifest)
    if result != reproduced or not result.get("passes"):
        raise ValueError("SIS pass-tail weekly acquisition did not reproduce")
    return root, manifest


def _artifact_map(manifest: dict) -> dict[tuple[str, str], dict]:
    artifacts = {
        (str(item["report"]), str(item["slice"])): item
        for item in manifest["artifacts"]
    }
    if len(artifacts) != 5:
        raise ValueError("SIS pass-tail weekly artifact identities differ")
    return artifacts


def _read_team_context(root: Path, manifest: dict) -> pd.DataFrame:
    artifacts = _artifact_map(manifest)
    parts = {}
    for report in (
        "pass-defense-totals", "pass-defense-value", "pass-rush-totals",
    ):
        item = artifacts[(report, "all")]
        path = root / item["artifact"]
        parts[report] = _read_artifact(
            path, path.with_suffix(".manifest.json"), report)
    base = parts["pass-defense-totals"]
    for report in ("pass-defense-value", "pass-rush-totals"):
        incoming = parts[report]
        if set(map(tuple, base[list(KEY_COLUMNS)].to_numpy())) != set(
            map(tuple, incoming[list(KEY_COLUMNS)].to_numpy())
        ):
            raise ValueError(f"SIS weekly {report} team-game universe differs")
        incoming = incoming.drop(columns=["team_id"], errors="ignore")
        base = base.merge(
            incoming, on=list(KEY_COLUMNS), how="inner", validate="one_to_one"
        )
    name_to_id: dict[str, int] = {}
    for frame in parts.values():
        for row in frame[["team_name", "team_id"]].drop_duplicates().itertuples(
            index=False
        ):
            prior = name_to_id.setdefault(str(row.team_name), int(row.team_id))
            if prior != int(row.team_id):
                raise ValueError("SIS weekly team name maps to multiple IDs")
    names = set(base.team_name) | set(base.opp_name)
    if missing := names - set(TEAM_ABBREVIATIONS):
        raise ValueError(f"SIS weekly team aliases missing {sorted(missing)}")
    if missing := set(base.opp_name) - set(name_to_id):
        raise ValueError(f"SIS weekly opponent IDs missing {sorted(missing)}")
    base["team"] = base.team_name.map(TEAM_ABBREVIATIONS)
    base["opp"] = base.opp_name.map(TEAM_ABBREVIATIONS)
    base["opp_team_id"] = base.opp_name.map(name_to_id).astype(int)
    base["game_key"] = base.apply(
        lambda row: f"{row.season}-{row.week:02d}-"
        + "-".join(sorted((row.team, row.opp))), axis=1,
    )
    base["source_run_id"] = str(manifest["acquisition_identity"])
    base = base.sort_values(["season", "week", "team_id"]).reset_index(drop=True)
    if base.duplicated(["season", "week", "team"]).any():
        raise ValueError("SIS weekly context repeats team-week")
    if not base.groupby("game_key").size().eq(2).all():
        raise ValueError("SIS weekly context lacks both game sides")
    start, end = (
        int(manifest["source_week_start"]), int(manifest["source_week_end"])
    )
    if not base.week.between(start, end).all():
        raise ValueError("SIS weekly context row lies outside source window")
    return base


def _read_alignment_attempts(root: Path, manifest: dict) -> pd.DataFrame:
    artifacts = _artifact_map(manifest)
    records: list[dict] = []
    for alignment in ("wide", "slot"):
        item = artifacts[("pass-defense-totals", alignment)]
        path = root / item["artifact"]
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        identities = {
            (
                int(row["season"]), int(row["week"]),
                str(row["team"]), str(row["opp"]),
            ): int(row["teamId"])
            for row in item["identities"]
        }
        if len(identities) != len(rows):
            raise ValueError("SIS weekly alignment identity row count differs")
        for row in rows:
            key = (
                int(row["Season"]), int(row["Week"]),
                str(row["Team"]), str(row["Opp."]),
            )
            if key not in identities:
                raise ValueError("SIS weekly alignment row lacks stable identity")
            if key[2] not in TEAM_ABBREVIATIONS or key[3] not in TEAM_ABBREVIATIONS:
                raise ValueError("SIS weekly alignment row has unknown team")
            attempts = float(str(row["Att"]).replace(",", ""))
            if attempts < 0 or not attempts.is_integer():
                raise ValueError("SIS weekly alignment attempt is invalid")
            records.append({
                "season": key[0],
                "week": key[1],
                "defense": TEAM_ABBREVIATIONS[key[2]],
                "offense": TEAM_ABBREVIATIONS[key[3]],
                "team_id": identities[key],
                "alignment": alignment,
                "attempts": int(attempts),
                "source_sha256": item["sha256"],
                "source_run_id": str(manifest["acquisition_identity"]),
            })
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("SIS weekly alignment attempt rows are empty")
    keys = ["season", "week", "defense", "alignment"]
    if frame.duplicated(keys).any():
        raise ValueError("SIS weekly alignment attempts repeat logical keys")
    start, end = (
        int(manifest["source_week_start"]), int(manifest["source_week_end"])
    )
    if not frame.week.between(start, end).all():
        raise ValueError("SIS weekly alignment row lies outside source window")
    return frame


def read_exports(
    input_dir: str | Path, *, target_week: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    root, manifest = _load_manifest(input_dir, target_week=target_week)
    context = _read_team_context(root, manifest)
    attempts = _read_alignment_attempts(root, manifest)
    return context, attempts, {
        "version": sis.PASS_TAIL_WEEKLY_VERSION,
        "source_run_id": manifest["acquisition_identity"],
        "season": SEASON,
        "target_week": int(target_week),
        "source_week_start": int(manifest["source_week_start"]),
        "source_week_end": int(manifest["source_week_end"]),
        "context_rows": int(len(context)),
        "attempt_rows": int(len(attempts)),
        "artifacts": len(manifest["artifacts"]),
        "api_requests_used": int(manifest["api_requests_used"]),
    }


def _novel_or_identical(
    rows: pd.DataFrame,
    existing: pd.DataFrame,
    *,
    keys: list[str],
    hash_columns: list[str],
) -> pd.DataFrame:
    if existing.empty:
        return rows.copy()
    required = set([*keys, *hash_columns])
    if missing := required - set(existing):
        raise ValueError(f"existing SIS weekly rows lack {sorted(missing)}")
    if existing.duplicated(keys).any():
        raise RuntimeError("existing SIS weekly rows repeat logical keys")
    joined = rows.merge(
        existing[[*keys, *hash_columns]], on=keys, how="left",
        suffixes=("", "_existing"), indicator=True,
    )
    overlap = joined._merge.eq("both")
    same = pd.Series(True, index=joined.index)
    for column in hash_columns:
        same &= joined[column].eq(joined[f"{column}_existing"])
    if (overlap & ~same).any():
        bad = joined.loc[overlap & ~same, keys].to_dict("records")[:5]
        raise RuntimeError(f"SIS weekly append conflicts: {bad}")
    novel_keys = joined.loc[joined._merge.eq("left_only"), keys]
    if novel_keys.empty:
        return rows.iloc[0:0].copy()
    return rows.merge(novel_keys, on=keys, how="inner", validate="one_to_one")


def _archive(root: Path, manifest: dict, bucket_name: str) -> list[dict]:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    bucket = storage.Client().bucket(bucket_name)
    output = []
    for item in manifest["artifacts"]:
        object_name = (
            "licensed/sis/pass-tail/season=2026/"
            f"target_week={int(manifest['target_week']):02d}/"
            f"sha256={item['sha256']}/{item['artifact']}"
        )
        blob = bucket.blob(object_name)
        disposition = "created"
        try:
            blob.upload_from_filename(
                str(root / item["artifact"]), content_type="text/csv",
                if_generation_match=0,
            )
        except PreconditionFailed:
            if hashlib.sha256(blob.download_as_bytes()).hexdigest() != item["sha256"]:
                raise RuntimeError("hash-addressed SIS weekly archive differs")
            disposition = "already-identical"
        output.append({
            "artifact": item["artifact"],
            "uri": f"gs://{bucket_name}/{object_name}",
            "disposition": disposition,
        })
    return output


def run(
    input_dir: str | Path, *, target_week: int, write: bool = False,
) -> dict:
    from ..bq import load_dataframe, query_df
    from ..config import settings

    root, manifest = _load_manifest(input_dir, target_week=target_week)
    context = _read_team_context(root, manifest)
    attempts = _read_alignment_attempts(root, manifest)
    team_ref = f"{settings.raw}.{TEAM_TABLE}"
    attempt_ref = f"{settings.raw}.{ATTEMPT_TABLE}"
    team_keys = ["season", "week", "team"]
    team_hashes = [
        "source_sha256_pass_defense_totals",
        "source_sha256_pass_defense_value",
        "source_sha256_pass_rush_totals",
    ]
    attempt_keys = ["season", "week", "defense", "alignment"]
    existing_context = query_df(f"""
        SELECT {', '.join([*team_keys, *team_hashes])}
        FROM `{team_ref}`
        WHERE season=@season AND week BETWEEN @start_week AND @end_week
        """, params={
            "season": SEASON,
            "start_week": int(manifest["source_week_start"]),
            "end_week": int(manifest["source_week_end"]),
        })
    existing_attempts = query_df(f"""
        SELECT {', '.join([*attempt_keys, 'source_sha256'])}
        FROM `{attempt_ref}`
        WHERE season=@season AND week BETWEEN @start_week AND @end_week
        """, params={
            "season": SEASON,
            "start_week": int(manifest["source_week_start"]),
            "end_week": int(manifest["source_week_end"]),
        })
    novel_context = _novel_or_identical(
        context, existing_context, keys=team_keys, hash_columns=team_hashes)
    novel_attempts = _novel_or_identical(
        attempts, existing_attempts, keys=attempt_keys,
        hash_columns=["source_sha256"],
    )
    audit = {
        "version": sis.PASS_TAIL_WEEKLY_VERSION,
        "source_run_id": manifest["acquisition_identity"],
        "season": SEASON,
        "target_week": int(target_week),
        "source_week_start": int(manifest["source_week_start"]),
        "source_week_end": int(manifest["source_week_end"]),
        "context_table": team_ref,
        "attempt_table": attempt_ref,
        "context_rows": int(len(context)),
        "attempt_rows": int(len(attempts)),
        "append_context_rows": int(len(novel_context)),
        "append_attempt_rows": int(len(novel_attempts)),
        "write_requested": bool(write),
        "point_in_time_contract": "only completed source weeks strictly below W",
    }
    if write:
        audit["archives"] = _archive(root, manifest, settings.gcs_bucket)
        now = datetime.now(UTC)
        if not novel_context.empty:
            payload = novel_context.copy()
            payload["ingested_at"] = now
            load_dataframe(payload, team_ref, write_disposition="WRITE_APPEND")
        if not novel_attempts.empty:
            payload = novel_attempts.copy()
            payload["ingested_at"] = now
            load_dataframe(payload, attempt_ref, write_disposition="WRITE_APPEND")
        audit["context_write_disposition"] = (
            "appended" if not novel_context.empty else "already-identical")
        audit["attempt_write_disposition"] = (
            "appended" if not novel_attempts.empty else "already-identical")
    print("SIS_PASS_TAIL_WEEKLY_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = ["read_exports", "run"]
