"""Prospective append-only 2026 ingestion for the Fantasy Points last-four families.

The historical same-season importers are write-once for their frozen 2022--2025 grids.  This module owns the
2026 operating path for five of those families (operator directive 2026-09-23: collect every paid family we hold
history for, every week).  One weekly run downloads the target week's W-4..W-1 (or cumulative) windows from a
hash-frozen 2026 plan; this module validates that single-target manifest, parses it with the historical
family's OWN reader (the grid arguments select the one 2026 target window, so the parsing, identity and support
law is identical to the historical rows), archives the bytes by content hash, and appends to the historical table
only the logical rows that are not already present (identical re-runs are no-ops; a different hash for an existing
key fails closed).

Point-in-time: every export's source weeks end at W-1 (the plan and the manifest check both enforce it).
Completeness: a table's row count for W must be at least MIN_ROWS_VS_PRIOR_TARGET of its latest earlier 2026
target week (the unfinished-export lesson of the 2026 Week-2 Route Share capture).

  python -m nfl_dfs.ingest.fantasy_points_weekly_2026 <family> <run dir> --target-week W [--coverage-dir D] [--write]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import fantasy_points_advanced_receiving_support as adv_receiving
from . import fantasy_points_qb_shell as qb_shell
from . import fantasy_points_same_season_coverage as coverage
from . import fantasy_points_same_season_passing as passing
from . import fantasy_points_same_season_route_shape as route_shape
from .fantasy_points_route import _sha256
from .fantasy_points_same_season_coverage import _csv_shape


SEASON = 2026
SOURCE_URL_PREFIX = "https://data.fantasypoints.com/nfl/tools/"
MIN_ROWS_VS_PRIOR_TARGET = 0.80


@dataclass(frozen=True)
class Window:
    report: str
    context: str
    kind: str                 # "last_four" (W-4..W-1) or "cumulative" (1..W-1)
    first_target_week: int


@dataclass(frozen=True)
class Table:
    name: str
    keys: tuple[str, ...]
    hash_columns: tuple[str, ...]


@dataclass(frozen=True)
class Family:
    key: str
    plan_name: str
    plan_sha256: str
    windows: tuple[Window, ...]
    tables: tuple[Table, ...]

    @property
    def first_target_week(self) -> int:
        return min(window.first_target_week for window in self.windows)


FAMILIES: dict[str, Family] = {family.key: family for family in (
    Family(
        "advanced-passing", "2026-advanced-passing-last-four-weekly-v1",
        "cf9f4ba39f394230871aed8742c988184955878593c6fbb3f9a3293d947ab808",
        (Window("advanced-passing", "Player", "last_four", 5),),
        (Table(passing.TABLE, ("season", "target_week", "normalized_name", "pos"), ("source_sha256",)),),
    ),
    Family(
        "route-shape", "2026-route-shape-last-four-weekly-v1",
        "71648c115270327964bb3bc07dacbc5b7dfff34b714560c84e05bb52ed4e1c3a",
        (Window("receiving-separation-by-breaks", "Player", "last_four", 5),),
        (Table(route_shape.TABLE, ("season", "target_week", "normalized_name", "pos"), ("source_sha256",)),),
    ),
    Family(
        "coverage", "2026-coverage-last-four-weekly-v1",
        "2a89dee5774a681d30dab3dba571f64b50fe1f315ca9f138db85f9c46954f7a7",
        (Window("receiving-man-vs-zone", "Player", "last_four", 5),
         Window("receiving-separation-by-coverage", "Player", "last_four", 5),
         Window("coverage-matrix", "Defense", "last_four", 5)),
        (Table(coverage.RECEIVER_TABLE, ("season", "target_week", "normalized_name", "pos"),
               ("man_zone_source_sha256", "separation_source_sha256")),
         Table(coverage.DEFENSE_TABLE, ("season", "target_week", "team"), ("source_sha256",))),
    ),
    Family(
        # parsed together with the same target week's coverage run (its Defense matrix), as historically
        "qb-shell", "2026-qb-shell-fit-last-four-weekly-v1",
        "d5323cefcc220623100a79d3e3db38adefb2b953d20836c831b9acc2e2a9f8d8",
        (Window("coverage-matrix", "Offense", "last_four", 5),),
        (Table(qb_shell.TABLE, ("season", "target_week", "team"), ("off_source_sha256", "def_source_sha256")),),
    ),
    Family(
        "advanced-receiving", "2026-advanced-receiving-support-windows-weekly-v1",
        "d5b49f04d1c3eb580f93b386f13924b73126f510f919a9668538e9633c52acba",
        (Window("advanced-receiving", "Player", "cumulative", 5),
         Window("advanced-receiving", "Player", "last_four", 6)),
        (Table(adv_receiving.TABLE, ("season", "target_week", "window_type", "normalized_name", "pos"),
               ("source_sha256",)),),
    ),
)}


def _weeks(kind: str, target_week: int) -> list[int]:
    first = 1 if kind == "cumulative" else target_week - 4
    return list(range(first, target_week))


def _utc(value: object, field: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"weekly manifest has invalid {field}") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"weekly manifest {field} is not timezone-aware")
    return stamp.tz_convert("UTC")


def validate_manifest(family: Family, input_dir: str | Path, *, target_week: int) -> tuple[dict, list[dict]]:
    """Validate one complete single-target-week 2026 download of `family`; return (manifest, artifacts)."""
    target_week = int(target_week)
    if not family.first_target_week <= target_week <= 18:
        raise ValueError(f"{family.key}: 2026 target week must be within {family.first_target_week}..18")
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError(f"{family.key}: weekly manifest is not complete schema 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{family.plan_name}"):
        raise ValueError(f"{family.key}: weekly manifest has the wrong run id")
    if manifest.get("plan_sha256") != family.plan_sha256:
        raise ValueError(f"{family.key}: weekly manifest has the wrong frozen plan hash")
    if manifest.get("selected_target_week") != target_week:
        raise ValueError(f"{family.key}: weekly manifest target week differs")
    _utc(manifest.get("started_at_utc"), "started_at_utc")
    _utc(manifest.get("finished_at_utc"), "finished_at_utc")
    expected = {(w.report, w.context, tuple(_weeks(w.kind, target_week))): w
                for w in family.windows if target_week >= w.first_target_week}
    exports = manifest.get("exports")
    if not isinstance(exports, list) or len(exports) != len(expected):
        raise ValueError(f"{family.key}: weekly manifest has {len(exports or [])} exports; expected {len(expected)}")
    artifacts: list[dict] = []
    seen: set[tuple] = set()
    for item in exports:
        key = (item.get("report"), item.get("context"), tuple(item.get("weeks") or ()))
        if key not in expected or key in seen:
            raise ValueError(f"{family.key}: unexpected or repeated export {key}")
        seen.add(key)
        for name, value in {"status": "downloaded", "season": SEASON, "include_group_headers": True,
                            "target_week": target_week}.items():
            if item.get(name) != value:
                raise ValueError(f"{family.key}: export {key} {name}={item.get(name)!r}; expected {value!r}")
        if max(key[2]) >= target_week:
            raise ValueError(f"{family.key}: export {key} is not strictly prior to Week {target_week}")
        _utc(item.get("retrieved_at_utc"), "retrieved_at_utc")
        if not str(item.get("source_url", "")).startswith(SOURCE_URL_PREFIX):
            raise ValueError(f"{family.key}: export {key} has an unexpected source URL")
        relative = Path(str(item.get("path", "")))
        if not relative.name or relative != Path(relative.name):
            raise ValueError(f"{family.key}: export {key} has an unsafe path")
        path = root / relative
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"{family.key}: export {key} artifact is missing or changed")
        if path.stat().st_size != int(item.get("bytes", -1)):
            raise ValueError(f"{family.key}: export {key} byte count differs")
        rows, columns = _csv_shape(path)
        if rows != int(item.get("csv_rows_including_headers", -1)) or columns != int(item.get("max_csv_columns", -1)):
            raise ValueError(f"{family.key}: export {key} shape differs from manifest")
        artifacts.append({**item, "local_path": path, "window_type": expected[key].kind})
    return manifest, artifacts


def _keyed(family: Family, artifacts: list[dict]) -> dict[tuple, dict]:
    """Key the artifacts the way the family's historical reader expects."""
    out: dict[tuple, dict] = {}
    for item in artifacts:
        week = int(item["target_week"])
        if family.key in ("advanced-passing", "route-shape", "qb-shell"):
            key: tuple = (SEASON, week)
        elif family.key == "coverage":
            key = (item["report"], SEASON, week)
        else:
            key = (SEASON, week, item["window_type"])
        out[key] = item
    return out


def parse(
    family: Family,
    manifest: dict,
    artifacts: list[dict],
    snapshots: pd.DataFrame,
    *,
    target_week: int,
    coverage_manifest: dict | None = None,
    coverage_artifacts: list[dict] | None = None,
) -> dict[str, pd.DataFrame]:
    """Rows per table for one 2026 target week, parsed by the historical family reader."""
    grid: dict[str, Any] = {"seasons": (SEASON,), "target_weeks": (int(target_week),)}
    keyed = _keyed(family, artifacts)
    if family.key == "advanced-passing":
        return {passing.TABLE: passing.read_windows(manifest, keyed, snapshots, **grid)[0]}
    if family.key == "route-shape":
        return {route_shape.TABLE: route_shape.read_windows(manifest, keyed, snapshots, **grid)[0]}
    if family.key == "coverage":
        receivers, _ = coverage.read_receiver_windows(manifest, keyed, snapshots, **grid)
        defenses, _ = coverage.read_defense_windows(manifest, keyed, **grid)
        return {coverage.RECEIVER_TABLE: receivers, coverage.DEFENSE_TABLE: defenses}
    if family.key == "qb-shell":
        if coverage_manifest is None or coverage_artifacts is None:
            raise ValueError("qb-shell needs the same target week's coverage run (its Defense matrix)")
        defense = _keyed(FAMILIES["coverage"], coverage_artifacts)
        rows = qb_shell.merge_windows(keyed, defense, **grid)
        rows["offense_source_run_id"] = manifest["run_id"]
        rows["defense_source_run_id"] = coverage_manifest["run_id"]
        rows["source_run_id"] = rows.offense_source_run_id + "|" + rows.defense_source_run_id   # as the historical write
        return {qb_shell.TABLE: rows}
    rows, _ = adv_receiving.read_windows(manifest, keyed, snapshots)
    return {adv_receiving.TABLE: rows}


def novel_or_identical(rows: pd.DataFrame, existing: pd.DataFrame, table: Table) -> pd.DataFrame:
    """Rows whose logical key is not stored yet; an existing key with a different source hash fails closed."""
    keys, hashes = list(table.keys), list(table.hash_columns)
    if rows.duplicated(keys).any():
        raise ValueError(f"{table.name}: weekly rows repeat logical keys")
    if existing.empty:
        return rows.copy()
    if existing.duplicated(keys).any():
        raise RuntimeError(f"{table.name}: stored rows repeat logical keys")
    joined = rows.merge(existing[keys + hashes], on=keys, how="left", suffixes=("", "_existing"), indicator=True)
    overlap = joined._merge.eq("both")
    differs = pd.Series(False, index=joined.index)
    for column in hashes:
        differs |= overlap & joined[column].ne(joined[f"{column}_existing"])
    if differs.any():
        raise RuntimeError(f"{table.name}: append conflicts with stored rows: "
                           f"{joined.loc[differs, keys].to_dict('records')[:5]}")
    novel = joined.loc[joined._merge.eq("left_only"), keys]
    return rows.merge(novel, on=keys, how="inner", validate="one_to_one") if len(novel) else rows.iloc[0:0].copy()


def check_completeness(table: Table, rows: int, prior_rows: int | None) -> None:
    """Refuse a week far smaller than the latest earlier 2026 target week (an unfinished vendor export)."""
    if rows == 0:
        raise ValueError(f"{table.name}: the weekly export produced no rows")
    if prior_rows and rows < MIN_ROWS_VS_PRIOR_TARGET * prior_rows:
        raise ValueError(f"{table.name}: {rows} rows vs {prior_rows} for the previous 2026 target week "
                         f"(minimum {MIN_ROWS_VS_PRIOR_TARGET:.0%}); re-download after the vendor finishes the week")


def _archive(family: Family, artifact: dict, bucket_name: str) -> tuple[str, str]:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    object_name = (f"licensed/fantasy-points/{family.key}/season={SEASON}/"
                   f"target_week={int(artifact['target_week']):02d}/sha256={artifact['sha256']}/{artifact['path']}")
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    try:
        blob.upload_from_filename(str(artifact["local_path"]), content_type="text/csv", if_generation_match=0)
        disposition = "created"
    except PreconditionFailed:
        if hashlib.sha256(blob.download_as_bytes()).hexdigest() != artifact["sha256"]:
            raise RuntimeError(f"{family.key}: archive object is non-identical")
        disposition = "already-identical"
    return f"gs://{bucket_name}/{object_name}", disposition


def run(
    family_key: str,
    input_dir: str | Path,
    *,
    target_week: int,
    write: bool = False,
    coverage_dir: str | Path | None = None,
) -> dict:
    """Validate, parse and (with write) archive + append one 2026 target week of one family."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    family = FAMILIES[family_key]
    manifest, artifacts = validate_manifest(family, input_dir, target_week=target_week)
    coverage_manifest = coverage_artifacts = None
    if family.key == "qb-shell":
        if coverage_dir is None:
            raise ValueError("qb-shell needs --coverage-dir (the same target week's coverage run)")
        coverage_manifest, coverage_artifacts = validate_manifest(
            FAMILIES["coverage"], coverage_dir, target_week=target_week)
    snapshots = query_df(f"""
        SELECT DISTINCT CAST(season AS INT64) AS season, gsis_id, full_name AS name, position AS pos, team
        FROM `{settings.raw}.rosters_weekly`
        WHERE CAST(season AS INT64) = @season AND CAST(week AS INT64) <= @target_week
          AND gsis_id IS NOT NULL AND full_name IS NOT NULL
        """, params={"season": SEASON, "target_week": int(target_week)})
    tables = parse(family, manifest, artifacts, snapshots, target_week=target_week,
                   coverage_manifest=coverage_manifest, coverage_artifacts=coverage_artifacts)
    audit: dict[str, Any] = {
        "family": family.key, "season": SEASON, "target_week": int(target_week),
        "source_run_id": manifest["run_id"], "plan_sha256": family.plan_sha256,
        "exports": [{"report": a["report"], "context": a["context"], "weeks": a["weeks"], "sha256": a["sha256"]}
                    for a in artifacts],
        "write_requested": bool(write), "tables": {},
        "point_in_time_contract": "every source window ends at W-1",
    }
    novel_by_table: dict[str, pd.DataFrame] = {}
    for table in family.tables:
        rows = tables[table.name]
        ref = f"{settings.raw}.{table.name}"
        prior = query_df(f"""
            SELECT COUNT(*) AS n FROM `{ref}`
            WHERE season = @season AND target_week = (
              SELECT MAX(target_week) FROM `{ref}` WHERE season = @season AND target_week < @target_week)
            """, params={"season": SEASON, "target_week": int(target_week)})
        prior_rows = int(prior.n.iloc[0]) if len(prior) else 0
        check_completeness(table, len(rows), prior_rows)
        existing = query_df(f"""
            SELECT {', '.join(table.keys)}, {', '.join(table.hash_columns)} FROM `{ref}`
            WHERE season = @season AND target_week = @target_week
            """, params={"season": SEASON, "target_week": int(target_week)})
        novel_by_table[table.name] = novel_or_identical(rows, existing, table)
        audit["tables"][table.name] = {
            "rows": int(len(rows)), "prior_target_week_rows": prior_rows,
            "existing_rows": int(len(existing)), "append_rows": int(len(novel_by_table[table.name])),
            **({"resolved_rows": int(rows.gsis_id.notna().sum())} if "gsis_id" in rows else {}),
        }
    if write:
        audit["archive"] = [dict(zip(("uri", "disposition"), _archive(family, a, settings.gcs_bucket)))
                            for a in artifacts]
        for table in family.tables:
            novel = novel_by_table[table.name]
            if not novel.empty:
                load_dataframe(novel, f"{settings.raw}.{table.name}", write_disposition="WRITE_APPEND")
            audit["tables"][table.name]["write_disposition"] = "appended" if not novel.empty else "already-identical"
        audit["ingested_at"] = datetime.now(UTC).isoformat()
    print("FP_WEEKLY_2026_IMPORT_JSON=" + json.dumps(audit, sort_keys=True, default=str))
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fp-weekly-2026", description=__doc__.splitlines()[0])
    parser.add_argument("family", choices=sorted(FAMILIES))
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--target-week", type=int, required=True)
    parser.add_argument("--coverage-dir", type=Path, help="qb-shell only: the same target week's coverage run")
    parser.add_argument("--write", action="store_true")
    a = parser.parse_args(argv)
    run(a.family, a.input_dir, target_week=a.target_week, write=a.write, coverage_dir=a.coverage_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["FAMILIES", "Family", "check_completeness", "novel_or_identical", "parse", "run", "validate_manifest"]
