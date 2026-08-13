"""Fail-closed merged intake for valid SIS tranche-2 run context.

The original acquisition stopped after SIS exported team Passing Value with
the Passing Totals schema.  This importer binds the original and recovery
plans/states, quarantines every Passing Value artifact, and accepts only the
five report families whose CSV schemas were independently verified.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from ..ops.sis_downloads import artifact_name, load_plan, plan_request_ceiling
from .fantasy_points_same_season_coverage import _write_once
from .sis_team_context import (
    EXPECTED_SEASON_ROWS,
    KEY_COLUMNS,
    SCHEMAS,
    TEAM_ABBREVIATIONS,
    _read_artifact,
    _sha256,
)


TABLE = "sis_team_run_context_game"
SOURCE_RUN = "sis-team-run-context-tranche-2-v1"
ORIGINAL_PLAN = Path("automation/sis/plans/team-context-tranche-2.json")
RECOVERY_PLAN = Path(
    "automation/sis/plans/team-context-tranche-2-recovery.json")
EXPECTED_REPORTS = (
    "passing-totals",
    "rushing-totals",
    "rushing-value",
    "run-defense-totals",
    "run-defense-value",
)
EXCLUDED_REPORT = "passing-value"
EXPECTED_ORIGINAL_ARTIFACTS = 82
EXPECTED_ORIGINAL_VALID_ARTIFACTS = 68
EXPECTED_RECOVERY_ARTIFACTS = 22
EXPECTED_VALID_ARTIFACTS = 90
EXPECTED_EXCLUDED_ARTIFACTS = 14


def _state(root: Path, plan: Path) -> tuple[dict, Path]:
    state_path = root / f".{plan.stem}.run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("plan_sha256") != _sha256(plan):
        raise ValueError(f"{state_path.name} has another plan hash")
    if int(state.get("ceiling", -1)) != plan_request_ceiling(plan):
        raise ValueError(f"{state_path.name} ceiling differs from its plan")
    if not 0 <= int(state.get("used", -1)) <= int(state["ceiling"]):
        raise ValueError(f"{state_path.name} request count is invalid")
    return state, state_path


def _artifact_files(root: Path) -> set[str]:
    return {path.name for path in root.glob("*.csv")}


def _validate_excluded_passing_value(
    root: Path,
    specs: list,
) -> list[str]:
    """Prove the excluded files are the known stale-view failure, not data."""
    hashes = []
    totals_header = SCHEMAS["passing-totals"][0]
    for spec in specs:
        value_path = root / artifact_name(spec)
        manifest_path = value_path.with_suffix(".manifest.json")
        if not value_path.is_file() or not manifest_path.is_file():
            raise FileNotFoundError(
                value_path if not value_path.is_file() else manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("artifact") != value_path.name:
            raise ValueError(f"{manifest_path.name} points to another artifact")
        if manifest.get("sha256") != _sha256(value_path):
            raise ValueError(f"{value_path.name} hash differs from its manifest")
        with value_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        if not rows or tuple(rows[0]) != totals_header:
            raise ValueError(
                f"{value_path.name} is not the quarantined Totals-schema defect")
        totals_name = value_path.name.replace(
            "__passing-value__", "__passing-totals__")
        totals_path = root / totals_name
        if not totals_path.is_file() or _sha256(totals_path) != _sha256(value_path):
            raise ValueError(
                f"{value_path.name} does not match its known stale Totals view")
        hashes.append(_sha256(value_path))
    return sorted(hashes)


def read_merged_tranche(
    original_dir: str | Path,
    recovery_dir: str | Path,
    *,
    original_plan_path: str | Path = ORIGINAL_PLAN,
    recovery_plan_path: str | Path = RECOVERY_PLAN,
) -> tuple[pd.DataFrame, dict]:
    """Validate the exact 68+22 valid artifact union and merge team games."""
    original_root = Path(original_dir)
    recovery_root = Path(recovery_dir)
    original_plan = Path(original_plan_path)
    recovery_plan = Path(recovery_plan_path)
    original_specs = load_plan(original_plan)
    recovery_specs = load_plan(recovery_plan)
    if len(original_specs) != 108:
        raise ValueError("SIS original tranche-2 plan is not the frozen 108 exports")
    if len(recovery_specs) != EXPECTED_RECOVERY_ARTIFACTS:
        raise ValueError("SIS recovery plan is not the frozen 22 exports")
    if {spec.report for spec in recovery_specs} - set(EXPECTED_REPORTS):
        raise ValueError("SIS recovery plan contains an excluded report")

    original_state, original_state_path = _state(original_root, original_plan)
    recovery_state, recovery_state_path = _state(recovery_root, recovery_plan)

    original_files = _artifact_files(original_root)
    original_existing_specs = [
        spec for spec in original_specs if artifact_name(spec) in original_files]
    if len(original_files) != EXPECTED_ORIGINAL_ARTIFACTS or {
        artifact_name(spec) for spec in original_existing_specs
    } != original_files:
        raise ValueError("SIS original directory differs from its 82-artifact stop")
    recovery_files = _artifact_files(recovery_root)
    if recovery_files != {artifact_name(spec) for spec in recovery_specs}:
        raise ValueError("SIS recovery directory differs from its frozen plan")

    excluded_specs = [
        spec for spec in original_existing_specs if spec.report == EXCLUDED_REPORT]
    if len(excluded_specs) != EXPECTED_EXCLUDED_ARTIFACTS:
        raise ValueError("SIS excluded Passing Value artifact count differs")
    excluded_hashes = _validate_excluded_passing_value(
        original_root, excluded_specs)

    desired_specs = [
        spec for spec in original_specs if spec.report in EXPECTED_REPORTS]
    original_valid_specs = [
        spec for spec in original_existing_specs if spec.report in EXPECTED_REPORTS]
    if len(original_valid_specs) != EXPECTED_ORIGINAL_VALID_ARTIFACTS:
        raise ValueError("SIS original valid artifact count differs")
    missing_names = {
        artifact_name(spec) for spec in desired_specs
    } - {artifact_name(spec) for spec in original_valid_specs}
    if missing_names != {artifact_name(spec) for spec in recovery_specs}:
        raise ValueError("SIS recovery plan is not the exact original-plan remainder")
    if len(desired_specs) != EXPECTED_VALID_ARTIFACTS:
        raise ValueError("SIS valid artifact universe is not exactly 90")

    original_names = {artifact_name(spec) for spec in original_valid_specs}
    report_parts: dict[str, list[pd.DataFrame]] = {
        report: [] for report in EXPECTED_REPORTS}
    artifact_origins = {"original": 0, "recovery": 0}
    for spec in desired_specs:
        name = artifact_name(spec)
        origin = "original" if name in original_names else "recovery"
        root = original_root if origin == "original" else recovery_root
        artifact = root / name
        manifest = artifact.with_suffix(".manifest.json")
        report_parts[spec.report].append(
            _read_artifact(artifact, manifest, spec.report))
        artifact_origins[origin] += 1

    reports = {}
    for report, parts in report_parts.items():
        combined = pd.concat(parts, ignore_index=True)
        if combined.duplicated(list(KEY_COLUMNS)).any():
            raise ValueError(f"SIS {report} repeats a team-game across windows")
        counts = combined.groupby("season").size().to_dict()
        if counts != EXPECTED_SEASON_ROWS:
            raise ValueError(f"SIS {report} season rows differ: {counts}")
        reports[report] = combined

    base = reports[EXPECTED_REPORTS[0]]
    base_universe = set(map(tuple, base[list(KEY_COLUMNS)].to_numpy()))
    for report in EXPECTED_REPORTS[1:]:
        incoming = reports[report]
        if base_universe != set(map(tuple, incoming[list(KEY_COLUMNS)].to_numpy())):
            raise ValueError(f"SIS {report} team-game universe differs")
        incoming = incoming.drop(columns=["team_id"], errors="ignore")
        base = base.merge(
            incoming, on=list(KEY_COLUMNS), how="inner", validate="one_to_one")

    name_to_id: dict[str, int] = {}
    for frame in reports.values():
        for row in frame[["team_name", "team_id"]].drop_duplicates().itertuples(
            index=False
        ):
            prior = name_to_id.setdefault(str(row.team_name), int(row.team_id))
            if prior != int(row.team_id):
                raise ValueError(
                    f"SIS team name maps to multiple IDs: {row.team_name}")
    if missing := (set(base.team_name) | set(base.opp_name)) - set(
        TEAM_ABBREVIATIONS
    ):
        raise ValueError(f"SIS team abbreviations missing: {sorted(missing)}")
    if missing := set(base.opp_name) - set(name_to_id):
        raise ValueError(f"SIS opponent IDs missing: {sorted(missing)}")
    base["team"] = base.team_name.map(TEAM_ABBREVIATIONS)
    base["opp"] = base.opp_name.map(TEAM_ABBREVIATIONS)
    base["opp_team_id"] = base.opp_name.map(name_to_id).astype(int)
    base["game_key"] = base.apply(
        lambda row: f"{row.season}-{row.week:02d}-"
        + "-".join(sorted((row.team, row.opp))), axis=1)
    base["source_run_id"] = SOURCE_RUN
    metadata = {
        "source_original_plan_sha256": _sha256(original_plan),
        "source_recovery_plan_sha256": _sha256(recovery_plan),
        "source_original_state_sha256": _sha256(original_state_path),
        "source_recovery_state_sha256": _sha256(recovery_state_path),
    }
    for column, value in metadata.items():
        base[column] = value
    base = base.sort_values(["season", "week", "team_id"]).reset_index(drop=True)
    if base.duplicated(["season", "week", "team"]).any():
        raise ValueError("SIS run-context table repeats a canonical team-week")
    if not base.groupby("game_key").size().eq(2).all():
        raise ValueError(
            "SIS run-context table does not contain both sides of every game")

    audit = {
        "source_run_id": SOURCE_RUN,
        "artifacts": EXPECTED_VALID_ARTIFACTS,
        "artifact_origins": artifact_origins,
        "excluded_report": EXCLUDED_REPORT,
        "excluded_artifacts": len(excluded_specs),
        "excluded_unique_hashes": len(set(excluded_hashes)),
        "rows": int(len(base)),
        "games": int(base.game_key.nunique()),
        "seasons": sorted(map(int, base.season.unique())),
        "season_rows": {
            str(key): int(value)
            for key, value in base.groupby("season").size().items()
        },
        "columns": list(base.columns),
        "original_api_requests_used": int(original_state["used"]),
        "original_api_request_ceiling": int(original_state["ceiling"]),
        "recovery_api_requests_used": int(recovery_state["used"]),
        "recovery_api_request_ceiling": int(recovery_state["ceiling"]),
        "point_in_time_contract": "target week W may use only source week < W",
        **metadata,
    }
    return base, audit


def run(
    original_dir: str | Path,
    recovery_dir: str | Path,
    *,
    original_plan_path: str | Path = ORIGINAL_PLAN,
    recovery_plan_path: str | Path = RECOVERY_PLAN,
    write: bool = False,
) -> dict:
    from ..config import settings

    rows, audit = read_merged_tranche(
        original_dir,
        recovery_dir,
        original_plan_path=original_plan_path,
        recovery_plan_path=recovery_plan_path,
    )
    table_ref = f"{settings.raw}.{TABLE}"
    audit.update({"table": table_ref, "write_requested": bool(write)})
    if write:
        hash_columns = tuple(
            column for column in rows
            if column.startswith("source_sha256_")
            or column.startswith("source_original_")
            or column.startswith("source_recovery_")
        )
        audit["write_disposition"] = _write_once(
            table_ref, rows, run_id=SOURCE_RUN, hash_columns=hash_columns)
    print("SIS_TEAM_RUN_CONTEXT_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = ["EXPECTED_REPORTS", "read_merged_tranche", "run"]
