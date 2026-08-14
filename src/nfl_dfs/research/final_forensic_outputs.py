"""Pure report builders for the frozen final-preseason forensic analysis."""

from __future__ import annotations

import copy
from collections import Counter
import json
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .final_forensic import (
    REQUIRED_MECHANISM_FAMILIES,
    TAILS,
    WAREHOUSE_TABLE_SCHEMAS,
    audit_roster,
)


def _roster(value: str) -> tuple[str, ...]:
    ids = tuple(item for item in str(value).split(",") if item)
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError("forensic roster is not nine unique players")
    return ids


def portfolio_slate(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    hpcs: Mapping[str, Any],
    *,
    known_winner_score: float | None = None,
) -> dict[str, Any]:
    """Describe exact-80 score/exposure/prefix behavior for one slate."""
    selected = candidates[
        candidates.selected.fillna(False).astype(bool)
    ].sort_values("selected_rank", kind="stable").copy()
    roster_keys = selected.players.map(lambda value: tuple(sorted(_roster(value))))
    if len(selected) != 80 or roster_keys.duplicated().any():
        raise ValueError("portfolio analysis requires 80 distinct selected rosters")
    scores = pd.to_numeric(selected.actual_score, errors="raise").to_numpy(float)
    player_rows = players.set_index("id")
    exposures = Counter(
        player for roster in selected.players.map(_roster) for player in roster
    )
    lineup_salaries = [
        int(player_rows.loc[list(roster), "salary"].sum())
        for roster in selected.players.map(_roster)
    ]
    prefix = {
        str(count): {
            "best": float(scores[:count].max()),
            "top3_mean": float(np.mean(np.sort(scores[:count])[-3:])),
            "entries_added": count - (0 if count == 20 else count // 2),
        }
        for count in (20, 40, 80)
    }
    top_exposures = [
        {
            "id": player_id,
            "count": count,
            "rate": count / 80.0,
            "pos": str(player_rows.loc[player_id, "pos"]),
            "salary": int(player_rows.loc[player_id, "salary"]),
            "actual": float(player_rows.loc[player_id, "actual"]),
        }
        for player_id, count in sorted(
            exposures.items(), key=lambda item: (-item[1], item[0])
        )[:25]
    ]
    output = {
        "entries": 80,
        "duplicate_rosters": 0,
        "candidate_count": int(len(candidates)),
        "score_distribution": {
            "minimum": float(scores.min()),
            "mean": float(scores.mean()),
            "median": float(np.median(scores)),
            "p90": float(np.quantile(scores, 0.90)),
            "maximum": float(scores.max()),
            "top3": sorted(map(float, scores), reverse=True)[:3],
            "top5": sorted(map(float, scores), reverse=True)[:5],
            "top10": sorted(map(float, scores), reverse=True)[:10],
        },
        "tail_counts": {
            str(tail): int((scores >= tail).sum()) for tail in TAILS
        },
        "outcome_blind_selected_prefixes": prefix,
        "salary": {
            "minimum": min(lineup_salaries),
            "mean": float(np.mean(lineup_salaries)),
            "maximum": max(lineup_salaries),
        },
        "unique_selected_players": len(exposures),
        "top_exposures": top_exposures,
        "candidate_oracle": float(hpcs["C"]["actual_score"]),
        "selected_best": float(hpcs["S"]["actual_score"]),
        "selection_gap": float(hpcs["gaps"]["selection"]),
        "selected_scores_by_rank": list(map(float, scores)),
    }
    if known_winner_score is not None:
        output["known_first_place"] = {
            "score": float(known_winner_score),
            "selected_gap": float(known_winner_score - scores.max()),
            "selected_beats": bool(scores.max() > known_winner_score),
        }
    return output


def player_capture_slate(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    hpcs: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the salary→served→candidate→selected capture funnel."""
    frame = players.copy()
    candidate_rosters = candidates.players.map(_roster)
    candidate_support = set().union(*(set(ids) for ids in candidate_rosters))
    selected_rosters = candidates[
        candidates.selected.fillna(False).astype(bool)
    ].players.map(_roster)
    selected_exposure = Counter(
        player for roster in selected_rosters for player in roster
    )
    served = (
        frame.mean_projection.notna()
        if "mean_projection" in frame
        else pd.Series(True, index=frame.index)
    )
    layers = {
        layer: set(map(str, hpcs[layer]["players"]))
        for layer in ("H", "P", "C", "S")
    }
    thresholds: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for tail in (20, 25, 30, 35):
        boom = frame[pd.to_numeric(frame.actual, errors="raise").ge(tail)]
        thresholds[str(tail)] = {
            "salary_listed": len(boom),
            "served_distribution": int(served.loc[boom.index].sum()),
            "candidate_support": int(boom.id.astype(str).isin(candidate_support).sum()),
            "selected_exposure": int(boom.id.astype(str).isin(selected_exposure).sum()),
            **{
                f"oracle_{layer}": int(boom.id.astype(str).isin(ids).sum())
                for layer, ids in layers.items()
            },
        }
    for row in frame[pd.to_numeric(frame.actual, errors="raise").ge(20)].itertuples():
        player_id = str(row.id)
        has_served = bool(served.loc[row.Index])
        if not has_served:
            first_failed = "served_distribution"
        elif player_id not in candidate_support:
            first_failed = "player_support"
        elif player_id not in selected_exposure:
            first_failed = "selected_exposure"
        else:
            first_failed = "captured"
        records.append({
            "id": player_id,
            "pos": str(row.pos),
            "salary": int(row.salary),
            "actual": float(row.actual),
            "first_failed_stage": first_failed,
            "selected_exposure": selected_exposure.get(player_id, 0),
            **{f"in_{layer}": player_id in ids for layer, ids in layers.items()},
        })
    calibration: dict[str, Any] = {}
    for position, group in frame.groupby("pos"):
        actual = pd.to_numeric(group.actual, errors="raise")
        means = pd.to_numeric(group.get("mean_projection"), errors="coerce")
        p90 = pd.to_numeric(group.get("proj_p90"), errors="coerce")
        calibration[str(position)] = {
            "rows": len(group),
            "mean_supported": int(means.notna().sum()),
            "mean_mae": (
                float((actual[means.notna()] - means.dropna()).abs().mean())
                if means.notna().any() else None
            ),
            "mean_spearman": (
                float(actual[means.notna()].corr(means.dropna(), method="spearman"))
                if means.notna().sum() >= 2 else None
            ),
            "p90_interval_coverage": (
                float((actual[p90.notna()] <= p90.dropna()).mean())
                if p90.notna().any() else None
            ),
        }
    return {
        "threshold_funnel": thresholds,
        "realized_20_plus_players": records,
        "calibration": calibration,
    }


def candidate_scorecard(candidates: pd.DataFrame) -> dict[str, Any]:
    """Measure candidate rank skill and generator yield without fitting."""
    actual = pd.to_numeric(candidates.actual_score, errors="raise")
    correlations: dict[str, Any] = {}
    for field in ("p_line", "sim_mean", "sim_q99"):
        values = pd.to_numeric(candidates.get(field), errors="coerce")
        mask = values.notna() & actual.notna()
        correlations[field] = {
            "rows": int(mask.sum()),
            "pearson": float(values[mask].corr(actual[mask])) if mask.sum() >= 2 else None,
            "spearman": (
                float(values[mask].corr(actual[mask], method="spearman"))
                if mask.sum() >= 2 else None
            ),
        }
    tag_column = "tag" if "tag" in candidates else None
    tag_yield = []
    if tag_column:
        for tag, group in candidates.groupby(tag_column, dropna=False):
            scores = pd.to_numeric(group.actual_score, errors="raise")
            tag_yield.append({
                "tag": str(tag),
                "candidates": len(group),
                "selected": int(group.selected.fillna(False).astype(bool).sum()),
                "actual_max": float(scores.max()),
                "ge200": int((scores >= 200).sum()),
            })
    return {
        "candidate_count": len(candidates),
        "selected_count": int(candidates.selected.fillna(False).astype(bool).sum()),
        "rank_skill": correlations,
        "generator_yield": sorted(tag_yield, key=lambda row: row["tag"]),
    }


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set, dict)):
        import json

        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _nullable_float(value: Any) -> float | None:
    if value is None or bool(pd.isna(value)):
        return None
    return float(value)


def _nullable_int(value: Any) -> int | None:
    if value is None or bool(pd.isna(value)):
        return None
    return int(value)


def _feature_missing(value: Any) -> tuple[str, bool]:
    raw = _nullable_string(value)
    if raw is None:
        return "[]", False
    normalized = raw.strip()
    return raw, normalized.lower() not in {"", "[]", "null", "none"}


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, int, float, bool, list, tuple, dict)):
        return value
    return str(value)


def _source_json(row: Any, supplied_field: str) -> str:
    supplied = getattr(row, supplied_field, None)
    if supplied is not None and not bool(pd.isna(supplied)):
        parsed = json.loads(str(supplied))
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    values = {
        key: _json_value(value)
        for key, value in row._asdict().items()
        if key not in {"Index", supplied_field}
    }
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def _ordered_warehouse_frame(table_id: str, rows: list[dict[str, Any]]) -> pd.DataFrame:
    fields = WAREHOUSE_TABLE_SCHEMAS[table_id]
    columns = [field["name"] for field in fields]
    frame = pd.DataFrame(rows, columns=columns)
    if list(frame) != columns:
        raise ValueError(f"warehouse {table_id} columns differ from frozen schema")
    for field in fields:
        name, kind, mode = field["name"], field["type"], field["mode"]
        if kind == "STRING":
            frame[name] = frame[name].astype("string")
        elif kind == "INTEGER":
            frame[name] = pd.to_numeric(frame[name], errors="raise").astype(
                "int64" if mode == "REQUIRED" else "Int64"
            )
        elif kind == "FLOAT":
            frame[name] = pd.to_numeric(frame[name], errors="coerce").astype(float)
        elif kind == "BOOLEAN":
            frame[name] = frame[name].astype(
                "bool" if mode == "REQUIRED" else "boolean"
            )
        else:
            raise ValueError(f"unsupported frozen warehouse type: {kind}")
        if mode == "REQUIRED" and frame[name].isna().any():
            raise ValueError(f"warehouse {table_id}.{name} contains NULL")
    return frame


def warehouse_slate_frames(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    hpcs: Mapping[str, Any],
    *,
    scope: str,
    season: int,
    week: int,
    manifest_sha256: str,
    analysis_code_sha: str,
    analysis_image: str,
) -> dict[str, pd.DataFrame]:
    """Materialize the exact queryable corpus behind one forensic slate."""
    provenance = {
        "manifest_sha256": str(manifest_sha256),
        "analysis_code_sha": str(analysis_code_sha),
        "analysis_image": str(analysis_image),
        "scope": str(scope),
        "season": int(season),
        "week": int(week),
    }
    player_frame = players.copy()
    player_frame["id"] = player_frame.id.astype(str)
    if player_frame.id.duplicated().any():
        raise ValueError("warehouse player corpus repeats player ids within slate")
    player_by_id = player_frame.set_index("id")
    player_rows = []
    for row in player_frame.itertuples(index=False):
        missing_raw, missing_any = _feature_missing(
            getattr(row, "feature_missing", None)
        )
        player_rows.append({
            **provenance,
            "slate_run_id": _nullable_string(getattr(row, "slate_run_id", None)),
            "player_id": str(row.id),
            "player_name": str(getattr(row, "name", row.id)),
            "position": str(row.pos),
            "team": str(row.team),
            "opponent": str(row.opp),
            "game_id": str(row.game_id),
            "kickoff_time": str(row.kickoff_time),
            "salary": int(row.salary),
            "actual_score": float(row.actual),
            "mean_projection": _nullable_float(
                getattr(row, "mean_projection", None)
            ),
            "proj_p10": _nullable_float(getattr(row, "proj_p10", None)),
            "proj_p50": _nullable_float(getattr(row, "proj_p50", None)),
            "proj_p90": _nullable_float(getattr(row, "proj_p90", None)),
            "proj_std": _nullable_float(getattr(row, "proj_std", None)),
            "fp_route_source_season": _nullable_int(
                getattr(row, "fp_route_source_season", None)
            ),
            "fp_route_source_week": _nullable_int(
                getattr(row, "fp_route_source_week", None)
            ),
            "fp_route_prior_observations": _nullable_int(
                getattr(row, "fp_route_prior_observations", None)
            ),
            "fp_route_share_last": _nullable_float(
                getattr(row, "fp_route_share_last", None)
            ),
            "fp_route_share_l4": _nullable_float(
                getattr(row, "fp_route_share_l4", None)
            ),
            "fp_route_share_jump": _nullable_float(
                getattr(row, "fp_route_share_jump", None)
            ),
            "fp_route_cross_season": _nullable_int(
                getattr(row, "fp_route_cross_season", None)
            ),
            "estimated_ownership": _nullable_float(
                getattr(row, "own_est", None)
            ),
            "actual_ownership": _nullable_float(
                getattr(row, "actual_ownership", None)
            ),
            "actual_ownership_contests": (
                int(row.actual_ownership_contests)
                if hasattr(row, "actual_ownership_contests")
                and not pd.isna(row.actual_ownership_contests)
                else None
            ),
            "feature_missing": missing_raw,
            "feature_missing_any": missing_any,
            "source_features_json": _source_json(row, "source_features_json"),
        })

    candidate_rows = []
    canonical_rosters: set[str] = set()
    for row in candidates.itertuples(index=False):
        roster_ordered = str(row.players)
        player_ids = tuple(item for item in roster_ordered.split(",") if item)
        if len(player_ids) != 9 or len(set(player_ids)) != 9:
            raise ValueError("warehouse candidate roster is not nine unique players")
        missing = set(player_ids) - set(player_by_id.index)
        if missing:
            raise ValueError(f"warehouse candidate has unknown players: {sorted(missing)}")
        roster_key = ",".join(sorted(player_ids))
        if roster_key in canonical_rosters:
            raise ValueError("warehouse candidate corpus repeats a roster")
        canonical_rosters.add(roster_key)
        reconstructed_salary = int(player_by_id.loc[list(player_ids), "salary"].sum())
        reported_salary = getattr(row, "salary", None)
        if reported_salary is not None and not pd.isna(reported_salary) and \
                int(reported_salary) != reconstructed_salary:
            raise ValueError("warehouse candidate salary fails reconstruction")
        selected_rank = getattr(row, "selected_rank", None)
        candidate_rows.append({
            **provenance,
            "panel_run_id": _nullable_string(getattr(row, "panel_run_id", None)),
            "source_seed": (
                int(row.source_seed)
                if hasattr(row, "source_seed") and not pd.isna(row.source_seed)
                else None
            ),
            "candidate_index": int(row.cand_ix),
            "roster_ordered": roster_ordered,
            "roster_key": roster_key,
            "salary": reconstructed_salary,
            "actual_score": float(row.actual_score),
            "selected": bool(row.selected),
            "selected_rank": int(selected_rank) if not pd.isna(selected_rank) else None,
            "p_line": _nullable_float(getattr(row, "p_line", None)),
            "sim_mean": _nullable_float(getattr(row, "sim_mean", None)),
            "sim_q99": _nullable_float(getattr(row, "sim_q99", None)),
            "tag": _nullable_string(getattr(row, "tag", None)),
            "all_tags": _nullable_string(getattr(row, "all_tags", None)),
            "source_candidate_json": _source_json(
                row, "source_candidate_json"
            ),
        })
    candidate_frame = _ordered_warehouse_frame("candidate_corpus", candidate_rows)
    selected = candidate_frame[candidate_frame.selected].copy()
    ranks = sorted(pd.to_numeric(selected.selected_rank, errors="raise").astype(int))
    if len(selected) != 80 or ranks != list(range(80)):
        raise ValueError("warehouse actual selections are not ranked exact-80")
    selection_rows = selected[[
        "manifest_sha256", "analysis_code_sha", "analysis_image", "scope",
        "season", "week", "selected_rank", "candidate_index", "roster_ordered",
        "roster_key", "salary", "actual_score", "p_line", "sim_mean", "sim_q99",
        "tag", "all_tags",
        "source_candidate_json",
    ]].sort_values("selected_rank", kind="stable").to_dict("records")

    oracle_rows = []
    for layer in ("H", "P", "C", "S"):
        player_ids = tuple(map(str, hpcs[layer]["players"]))
        audit = audit_roster(player_frame, player_ids)
        if not audit["valid"] or not np.isclose(
            audit["actual_score"], float(hpcs[layer]["actual_score"]),
            rtol=0.0, atol=1e-6,
        ):
            raise ValueError(f"warehouse {layer} roster fails independent audit")
        oracle_rows.append({
            **provenance,
            "layer": layer,
            "roster_key": ",".join(sorted(player_ids)),
            "salary": int(audit["salary"]),
            "actual_score": float(audit["actual_score"]),
            "solver_status": hpcs[layer].get(
                "solver_status", "candidate_scan" if layer == "C" else "selected_scan"
            ),
            "legality_verified": True,
            "player_support_gap": float(hpcs["gaps"]["player_support"]),
            "construction_gap": float(hpcs["gaps"]["construction"]),
            "selection_gap": float(hpcs["gaps"]["selection"]),
        })

    return {
        "player_corpus": _ordered_warehouse_frame("player_corpus", player_rows),
        "candidate_corpus": candidate_frame,
        "actual_selections": _ordered_warehouse_frame(
            "actual_selections", selection_rows
        ),
        "oracle_rosters": _ordered_warehouse_frame("oracle_rosters", oracle_rows),
    }


def registry_outputs(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build the four outcome-free closure outputs from the frozen ledger."""
    ledger = list(manifest["arm_ledger"])
    provenance = {
        "manifest_sha256": manifest["manifest_sha256"],
        "production": manifest["production"],
        "panels": manifest["panels"],
        "arm_ledger": ledger,
        "report_inventory": manifest["report_inventory"],
        "artifact_inventory": manifest["artifacts"],
        "warehouse_retention": copy.deepcopy(manifest["warehouse_retention"]),
        "analysis_checklist": manifest["analysis_checklist"],
    }
    meta = {
        "arms": [{
            "arm_id": row["id"],
            "family": row["family"],
            "status": row["status"],
            "effect": row["gate"],
            "breadth": "read cited result; never infer breadth from nested thresholds",
            "uncertainty": "read cited result/diagnostic; no unregistered pooled p-value",
            "cost": row["cloud_cost_status"],
            "kill_reason": row["gate"] if row["status"] == "rejected" else None,
            "falsifier": row["transfer_boundary"],
        } for row in ledger]
    }
    readiness = {
        "checks": [
            {
                "check": "production policy deployed",
                "status": "ready",
                "evidence": manifest["production"],
                "owner_action": "none before the first real slate",
                "deadline": "Week 1 slate open",
            },
            {
                "check": "first-slate authenticated UI to DK CSV smoke",
                "status": "pending_external_slate",
                "evidence": "No 2026 DraftKings classic slate exists yet.",
                "owner_action": "Run the documented authenticated 80-lineup export smoke.",
                "deadline": "before first Week 1 entry",
            },
            {
                "check": "weekly paid-vendor and Odds API acquisition",
                "status": "scheduled_manual_auth",
                "evidence": "README weekly checklist and unified nfl-weekly-data launcher",
                "owner_action": "Run Wednesday after both vendor sessions can be refreshed.",
                "deadline": "Wednesday of each slate week",
            },
            {
                "check": "contest standings and payout retention",
                "status": "required_prospective",
                "evidence": "No historical complete standings table is available.",
                "owner_action": "Download target GPP standings/payout CSV within ten days.",
                "deadline": "after every settled 2026 contest",
            },
            {
                "check": "forensic review corpus removed from BigQuery",
                "status": "required_before_production_build",
                "evidence": manifest["warehouse_retention"],
                "owner_action": (
                    "Run the manifest-bound cleanup, verify all four tables "
                    "absent, and commit the receipt."
                ),
                "deadline": "before first 2026 production feature/lineup build",
            },
        ]
    }
    prospective_rows = [
        row for row in ledger
        if row["status"] in {"prospective_only", "deferred_with_falsifier"}
        or "2026 shadow" in row["production_relevance"]
    ]
    prospective = {
        "items": [{
            "item": row["id"],
            "priority": "predeclared" if row["status"] == "prospective_only" else "triggered",
            "predeclared_question": row["gate"],
            "trigger": row["transfer_boundary"],
            "decision_law": "freeze before outcome; use the cited prospective contract",
            "transfer_boundary": row["transfer_boundary"],
        } for row in prospective_rows]
    }
    exhaustion_rows = []
    for family in REQUIRED_MECHANISM_FAMILIES:
        rows = [row for row in ledger if row["family"] == family]
        exhaustion_rows.append({
            "taxonomy_family": family,
            "terminal_arms": [row["id"] for row in rows],
            "open_historical_arms": [],
            "prospective_items": [
                row["id"] for row in rows
                if row["status"] in {"prospective_only", "deferred_with_falsifier"}
            ],
            "falsifier": (
                "Outcome-unseen evidence, new grain/mechanism, or a documented "
                "integrity defect may reopen only the named boundary."
            ),
            "certified": bool(rows),
        })
    return {
        "provenance_and_arm_ledger": provenance,
        "experiment_meta_analysis_and_kill_list": meta,
        "week1_operational_readiness": readiness,
        "prospective_charter_and_opportunity_register": prospective,
        "exhaustion_certificate": {"families": exhaustion_rows},
    }


__all__ = [
    "candidate_scorecard",
    "player_capture_slate",
    "portfolio_slate",
    "registry_outputs",
    "warehouse_slate_frames",
]
