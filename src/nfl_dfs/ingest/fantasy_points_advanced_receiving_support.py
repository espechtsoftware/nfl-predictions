"""Outcome-blind support audit for exact prior-week Advanced Receiving windows.

This module intentionally never selects, queries, or accepts an outcome column.
It validates the one frozen vendor manifest, resolves identities, and describes
support and predictor redundancy before any predictive protocol is licensed.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_advanced import _grouped_rows, _number
from .fantasy_points_route import (
    PANEL_ID,
    _canonical_teams,
    _resolve_player,
    _sha256,
    _snapshot_maps,
)
from .fantasy_points_same_season_coverage import _csv_shape
from ..names import norm_name


PLAN_NAME = "same-season-advanced-receiving-support-windows-v1"
PLAN_SHA256 = "58199c502ef5c1a1d154b725fc81ce0e7229b36f86543a13527289f781783477"
SEASONS = (2022, 2023, 2024, 2025)
CUMULATIVE_TARGET_WEEKS = tuple(range(5, 19))
LAST_FOUR_TARGET_WEEKS = tuple(range(6, 19))
# The authenticated Advanced Receiving export is a receiver-only surface. All
# 34,227 rows in the frozen 108-file manifest are labeled WR or TE; RB usage is
# covered by the separate Bell Cow/Advanced Rushing families and must not be
# counted as an Advanced Receiving support failure.
POSITIONS = ("WR", "TE")
ROUTE_FLOORS = (20, 40, 80)

METRIC_SPECS = {
    "Receiving::TPRR": ("fp_adv_rec_tprr", False),
    "Receiving::aDOT": ("fp_adv_rec_adot", False),
    "Receiving::AY Share": ("fp_adv_rec_air_yard_share", True),
    "Receiving::YPRR": ("fp_adv_rec_yprr", False),
    "Advanced::1READ %": ("fp_adv_rec_first_read_rate", True),
    "FPTS::XFP/RR": ("fp_adv_rec_xfp_per_route", False),
}
METRICS = tuple(output for output, _ in METRIC_SPECS.values())
EXISTING_FEATURES = (
    "target_share_l4",
    "target_share_last",
    "snap_share_l4",
    "snap_share_last",
    "air_yards_share_l4",
    "wopr_l4",
    "adot_l8",
    "xfp_l4",
)


def expected_windows() -> dict[tuple[int, int, str], tuple[int, ...]]:
    windows: dict[tuple[int, int, str], tuple[int, ...]] = {}
    for season in SEASONS:
        for target_week in CUMULATIVE_TARGET_WEEKS:
            windows[(season, target_week, "cumulative")] = tuple(
                range(1, target_week)
            )
        for target_week in LAST_FOUR_TARGET_WEEKS:
            windows[(season, target_week, "last_four")] = tuple(
                range(target_week - 4, target_week)
            )
    return windows


def _window_type(target_week: int, weeks: tuple[int, ...]) -> str:
    if weeks == tuple(range(1, target_week)):
        return "cumulative"
    if target_week >= 6 and weeks == tuple(range(target_week - 4, target_week)):
        return "last_four"
    raise ValueError(
        f"target Week {target_week} has an unlicensed source window {weeks}"
    )


def validate_manifest(input_dir: str | Path) -> tuple[dict, dict[tuple, dict]]:
    """Require the complete, exact 108-export frozen grid and immutable bytes."""
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Advanced Receiving support manifest schema must be 1")
    if manifest.get("status") != "complete":
        raise ValueError("Advanced Receiving support manifest is not complete")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("Advanced Receiving support manifest has the wrong run id")
    if manifest.get("plan_sha256") != PLAN_SHA256:
        raise ValueError("Advanced Receiving support manifest has the wrong plan hash")
    if manifest.get("selected_target_week") is not None:
        raise ValueError("Advanced Receiving support manifest is a partial target run")

    exports = manifest.get("exports")
    expected = expected_windows()
    if not isinstance(exports, list) or len(exports) != len(expected):
        raise ValueError(
            f"Advanced Receiving support manifest has {len(exports or [])} "
            f"exports; expected {len(expected)}"
        )
    keyed: dict[tuple, dict] = {}
    for item in exports:
        if item.get("status") != "downloaded":
            raise ValueError("Advanced Receiving support manifest has a failed export")
        if item.get("report") != "advanced-receiving":
            raise ValueError("Advanced Receiving support manifest has another report")
        if item.get("context") != "Player":
            raise ValueError("Advanced Receiving support export is not Player context")
        if item.get("include_group_headers") is not True:
            raise ValueError("Advanced Receiving support export lacks group headers")
        season = int(item.get("season", 0))
        target_week = int(item.get("target_week", 0))
        weeks = tuple(int(value) for value in item.get("weeks", []))
        window_type = _window_type(target_week, weeks)
        key = (season, target_week, window_type)
        if key in keyed:
            raise ValueError(f"duplicate Advanced Receiving support export {key}")
        if expected.get(key) != weeks:
            raise ValueError(f"unexpected Advanced Receiving support export {key}")
        if max(weeks) >= target_week:
            raise ValueError(f"Advanced Receiving support source is not prior: {key}")
        relative = Path(str(item.get("path", "")))
        if not relative.name or relative != Path(relative.name):
            raise ValueError(f"Advanced Receiving support export has unsafe path: {key}")
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        if _sha256(path) != item.get("sha256"):
            raise ValueError(f"Advanced Receiving support hash mismatch: {key}")
        if path.stat().st_size != int(item.get("bytes", -1)):
            raise ValueError(f"Advanced Receiving support size mismatch: {key}")
        rows, columns = _csv_shape(path)
        if rows != int(item.get("csv_rows_including_headers", -1)):
            raise ValueError(f"Advanced Receiving support row mismatch: {key}")
        if columns != int(item.get("max_csv_columns", -1)):
            raise ValueError(f"Advanced Receiving support width mismatch: {key}")
        keyed[key] = {**item, "local_path": path, "window_type": window_type}
    if set(keyed) != set(expected):
        raise ValueError("Advanced Receiving support manifest is not the frozen grid")
    return manifest, keyed


def read_windows(
    manifest: dict,
    artifacts: dict[tuple, dict],
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Parse and resolve all receiver rows without consulting outcomes."""
    by_name, by_season_team = _snapshot_maps(snapshots)
    required = {
        "Player Details::Name",
        "Player Details::Team",
        "Player Details::POS",
        "Player Details::G",
        "Player Details::Season",
        "Receiving::RTE",
        *METRIC_SPECS,
    }
    output: list[dict] = []
    statuses: Counter[str] = Counter()
    duplicate_groups = 0
    for key in sorted(artifacts):
        season, target_week, window_type = key
        artifact = artifacts[key]
        columns, rows = _grouped_rows(artifact["local_path"])
        if missing := required - set(columns):
            raise ValueError(f"{artifact['path']} missing {sorted(missing)}")
        grouped: dict[tuple, list[tuple[int, dict[str, str]]]] = defaultdict(list)
        for source_row, row in enumerate(rows, start=3):
            if int(row["Player Details::Season"]) != season:
                raise ValueError(f"{artifact['path']} row {source_row} wrong season")
            games = int(row["Player Details::G"])
            if not 1 <= games <= len(artifact["weeks"]):
                raise ValueError(f"{artifact['path']} row {source_row} has G={games}")
            vendor_pos = row["Player Details::POS"].strip().upper()
            pos = "RB" if vendor_pos == "FB" else vendor_pos
            if pos not in POSITIONS:
                continue
            name = row["Player Details::Name"].strip()
            team = row["Player Details::Team"].strip()
            if not name or not team:
                raise ValueError(f"{artifact['path']} row {source_row} blank identity")
            identity = (norm_name(name), pos, _canonical_teams(team))
            grouped[identity].append((source_row, row))

        for identity in sorted(grouped):
            normalized_name, pos, teams = identity
            group = grouped[identity]
            duplicate = len(group) != 1
            duplicate_groups += int(duplicate)
            source_row, row = group[0]
            gsis_id, status = _resolve_player(
                season,
                normalized_name,
                pos,
                teams,
                by_name,
                by_season_team,
            )
            statuses[status] += 1
            routes = _number(row["Receiving::RTE"])
            if not np.isfinite(routes) or routes < 0:
                raise ValueError(f"{artifact['path']} row {source_row} invalid routes")
            metrics = {
                output_name: _number(row[source_name], percentage=percentage)
                for source_name, (output_name, percentage) in METRIC_SPECS.items()
            }
            if duplicate:
                routes = np.nan
                metrics = {name: np.nan for name in METRICS}
            for rate in ("fp_adv_rec_tprr", "fp_adv_rec_first_read_rate"):
                value = metrics[rate]
                if np.isfinite(value) and not 0 <= value <= 1:
                    raise ValueError(
                        f"{artifact['path']} row {source_row} invalid {rate}"
                    )
            output.append({
                "season": season,
                "target_week": target_week,
                "window_type": window_type,
                "source_week_start": min(artifact["weeks"]),
                "source_week_end": max(artifact["weeks"]),
                "gsis_id": gsis_id,
                "resolution_status": status,
                "vendor_name": row["Player Details::Name"].strip(),
                "normalized_name": normalized_name,
                "vendor_team": row["Player Details::Team"].strip(),
                "canonical_teams": ",".join(teams),
                "pos": pos,
                "games": int(row["Player Details::G"]),
                "routes": routes,
                "split_duplicate": duplicate,
                "source_run_id": manifest["run_id"],
                "source_file": artifact["path"],
                "source_sha256": artifact["sha256"],
                "source_rows": ",".join(str(value[0]) for value in group),
                **metrics,
            })
    frame = pd.DataFrame(output)
    keys = ["season", "target_week", "window_type", "normalized_name", "pos"]
    if frame.duplicated(keys).any():
        raise ValueError("Advanced Receiving support rows have duplicate identities")
    return frame, {
        "rows": int(len(frame)),
        "resolved_rows": int(frame.gsis_id.notna().sum()),
        "unresolved_rows": int(statuses["unresolved"]),
        "ambiguous_rows": int(statuses["ambiguous"]),
        "duplicate_groups_suppressed": int(duplicate_groups),
    }


def _finite_summary(values: pd.Series) -> dict:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric[np.isfinite(numeric)]
    if numeric.empty:
        return {"rows": 0, "mean": None, "median": None, "q25": None, "q75": None}
    return {
        "rows": int(len(numeric)),
        "mean": float(numeric.mean()),
        "median": float(numeric.median()),
        "q25": float(numeric.quantile(0.25)),
        "q75": float(numeric.quantile(0.75)),
    }


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    left_numeric = pd.to_numeric(left, errors="coerce")
    right_numeric = pd.to_numeric(right, errors="coerce")
    valid = np.isfinite(left_numeric) & np.isfinite(right_numeric)
    if (
        valid.sum() < 3
        or left_numeric[valid].nunique() < 2
        or right_numeric[valid].nunique() < 2
    ):
        return None
    correlation = left_numeric[valid].corr(right_numeric[valid], method="spearman")
    return float(correlation) if np.isfinite(correlation) else None


def support_summary(rows: pd.DataFrame) -> list[dict]:
    summary: list[dict] = []
    keys = ["season", "target_week", "window_type", "pos"]
    for key, group in rows.groupby(keys, sort=True):
        season, target_week, window_type, pos = key
        route_values = pd.to_numeric(group.routes, errors="coerce")
        finite_routes = route_values[np.isfinite(route_values)]
        entry = {
            "season": int(season),
            "target_week": int(target_week),
            "window_type": str(window_type),
            "position": str(pos),
            "rows": int(len(group)),
            "resolved_rows": int(group.gsis_id.notna().sum()),
            "routes": _finite_summary(route_values),
            "route_floors": {},
            "metric_availability": {},
        }
        for floor in ROUTE_FLOORS:
            count = int(finite_routes.ge(floor).sum())
            entry["route_floors"][str(floor)] = {
                "rows": count,
                "rate": count / len(group) if len(group) else 0.0,
            }
        for metric in METRICS:
            count = int(pd.to_numeric(group[metric], errors="coerce").notna().sum())
            entry["metric_availability"][metric] = {
                "rows": count,
                "rate": count / len(group) if len(group) else 0.0,
            }
        summary.append(entry)
    return summary


def window_overlap(rows: pd.DataFrame) -> list[dict]:
    """Describe cumulative/last-four agreement on resolved common players."""
    output: list[dict] = []
    for season in SEASONS:
        for target_week in LAST_FOUR_TARGET_WEEKS:
            parts = {}
            for window_type in ("cumulative", "last_four"):
                part = rows[
                    rows.season.eq(season)
                    & rows.target_week.eq(target_week)
                    & rows.window_type.eq(window_type)
                    & rows.gsis_id.notna()
                ].copy()
                if part.gsis_id.duplicated().any():
                    raise ValueError("resolved Advanced Receiving window is not unique")
                parts[window_type] = part
            joined = parts["cumulative"].merge(
                parts["last_four"],
                on="gsis_id",
                how="inner",
                suffixes=("_cumulative", "_last_four"),
                validate="one_to_one",
            )
            metrics: dict[str, dict] = {}
            for metric in METRICS:
                left = pd.to_numeric(joined[f"{metric}_cumulative"], errors="coerce")
                right = pd.to_numeric(joined[f"{metric}_last_four"], errors="coerce")
                valid = np.isfinite(left) & np.isfinite(right)
                delta = right[valid] - left[valid]
                metrics[metric] = {
                    "paired_rows": int(valid.sum()),
                    "spearman": _spearman(left, right),
                    "mean_delta_last_four_minus_cumulative": (
                        float(delta.mean()) if len(delta) else None
                    ),
                    "median_absolute_delta": (
                        float(delta.abs().median()) if len(delta) else None
                    ),
                }
            output.append({
                "season": season,
                "target_week": target_week,
                "cumulative_resolved_players": int(len(parts["cumulative"])),
                "last_four_resolved_players": int(len(parts["last_four"])),
                "common_resolved_players": int(len(joined)),
                "metrics": metrics,
            })
    return output


def target_coverage_summary(rows: pd.DataFrame, existing: pd.DataFrame) -> list[dict]:
    """Measure vendor support against every eligible target-slate player."""
    needed = {"season", "target_week", "gsis_id", "pos"}
    if missing := needed - set(existing.columns):
        raise ValueError(f"target player universe missing {sorted(missing)}")
    if existing.duplicated(["season", "target_week", "gsis_id"]).any():
        raise ValueError("target player universe has duplicate target players")
    output: list[dict] = []
    for (season, target_week, window_type) in sorted(expected_windows()):
        for pos in POSITIONS:
            target = existing[
                existing.season.eq(season)
                & existing.target_week.eq(target_week)
                & existing.pos.eq(pos)
            ][["gsis_id"]]
            vendor = rows[
                rows.season.eq(season)
                & rows.target_week.eq(target_week)
                & rows.window_type.eq(window_type)
                & rows.pos.eq(pos)
                & rows.gsis_id.notna()
            ].copy()
            if vendor.gsis_id.duplicated().any():
                raise ValueError("resolved vendor support has duplicate target players")
            joined = target.merge(vendor, on="gsis_id", how="left", validate="one_to_one")
            denominator = int(len(target))
            matched = int(joined.source_file.notna().sum()) if denominator else 0
            entry = {
                "season": season,
                "target_week": target_week,
                "window_type": window_type,
                "position": pos,
                "eligible_target_rows": denominator,
                "matched_vendor_rows": matched,
                "matched_rate": matched / denominator if denominator else 0.0,
                "route_floors": {},
                "metric_availability": {},
            }
            route_values = pd.to_numeric(joined.routes, errors="coerce")
            for floor in ROUTE_FLOORS:
                count = int(route_values.ge(floor).sum())
                entry["route_floors"][str(floor)] = {
                    "rows": count,
                    "rate": count / denominator if denominator else 0.0,
                }
            for metric in METRICS:
                count = int(
                    pd.to_numeric(joined[metric], errors="coerce").notna().sum()
                )
                entry["metric_availability"][metric] = {
                    "rows": count,
                    "rate": count / denominator if denominator else 0.0,
                }
            output.append(entry)
    return output


def redundancy_summary(rows: pd.DataFrame, existing: pd.DataFrame) -> list[dict]:
    """Correlate predictors with predictors only; outcome columns are forbidden."""
    forbidden = {"actual", "selected", "score", "placement", "rank", "roi"}
    lowered = {str(column).lower() for column in existing.columns}
    if forbidden & lowered:
        raise ValueError("outcome-bearing columns are forbidden in support audit")
    needed = {"season", "target_week", "gsis_id", *EXISTING_FEATURES}
    if missing := needed - set(existing.columns):
        raise ValueError(f"existing feature panel missing {sorted(missing)}")
    if existing.duplicated(["season", "target_week", "gsis_id"]).any():
        raise ValueError("existing feature panel has duplicate target players")
    resolved = rows[rows.gsis_id.notna()].copy()
    joined = resolved.merge(
        existing,
        on=["season", "target_week", "gsis_id"],
        how="inner",
        validate="many_to_one",
    )
    output: list[dict] = []
    for window_type in ("cumulative", "last_four"):
        for season in SEASONS:
            part = joined[
                joined.window_type.eq(window_type) & joined.season.eq(season)
            ]
            for metric in METRICS:
                left = pd.to_numeric(part[metric], errors="coerce")
                for feature in EXISTING_FEATURES:
                    right = pd.to_numeric(part[feature], errors="coerce")
                    valid = np.isfinite(left) & np.isfinite(right)
                    output.append({
                        "window_type": window_type,
                        "season": season,
                        "vendor_metric": metric,
                        "existing_feature": feature,
                        "paired_rows": int(valid.sum()),
                        "spearman": _spearman(left, right),
                    })
    return output


def build_report(
    rows: pd.DataFrame,
    existing: pd.DataFrame,
    *,
    manifest: dict,
    row_audit: dict,
) -> dict:
    return {
        "protocol": PLAN_NAME,
        "outcome_blind": True,
        "run_id": manifest["run_id"],
        "plan_sha256": manifest["plan_sha256"],
        "exports": len(manifest["exports"]),
        "row_audit": row_audit,
        "fixed_route_floors": list(ROUTE_FLOORS),
        "support_by_window": support_summary(rows),
        "target_universe_coverage": target_coverage_summary(rows, existing),
        "cumulative_last_four_overlap": window_overlap(rows),
        "predictor_redundancy": redundancy_summary(rows, existing),
        "disposition": "support-audit-only-no-predictive-license",
    }


def run(input_dir: str | Path, *, output: str | Path | None = None) -> dict:
    """Run the outcome-blind audit against point-in-time predictor tables."""
    from ..bq import query_df
    from ..config import settings

    manifest, artifacts = validate_manifest(input_dir)
    snapshots = query_df(f"""
        SELECT DISTINCT season, gsis_id, name, pos, team
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
        """, params={"panel_id": PANEL_ID})
    rows, row_audit = read_windows(manifest, artifacts, snapshots)
    existing = query_df(f"""
      WITH latest AS (
        SELECT p.season, p.week AS target_week, p.gsis_id, p.pos,
               f.target_share_l4, p.target_share_last,
               f.snap_share_l4, p.snap_share_last,
               f.air_yards_share_l4, f.wopr_l4, f.adot_l8, f.xfp_l4
        FROM `{settings.predictions}.slate_player_features` p
        LEFT JOIN `{settings.features}.player_week_training` f
          USING (season, week, gsis_id)
        WHERE p.panel_run_id = @panel_id AND p.research_eligible
          AND p.season BETWEEN 2022 AND 2025
          AND p.week BETWEEN 5 AND 18
          AND p.pos IN ('RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY p.season, p.week, p.gsis_id
          ORDER BY p.generated_at DESC
        ) = 1
      )
      SELECT * FROM latest
      """, params={"panel_id": PANEL_ID})
    report = build_report(rows, existing, manifest=manifest, row_audit=row_audit)
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FP_ADVANCED_RECEIVING_SUPPORT_JSON=" + json.dumps(report, sort_keys=True))
    return report
