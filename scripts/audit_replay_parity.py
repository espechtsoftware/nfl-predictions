"""Fail-closed replay/live projection and candidate-mean parity audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("panel_run_id")
    parser.add_argument(
        "--promoted", action="store_true",
        help="read the promoted research candidate rows instead of staging")
    parser.add_argument("--model-weight", type=float, default=0.45)
    parser.add_argument("--expected-slates", type=int, default=107)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not 0.0 <= args.model_weight <= 1.0:
        parser.error("--model-weight must be between zero and one")
    panel = _panel_id(args.panel_run_id)
    table = "replay_candidates" if args.promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if args.promoted else ""
    model_weight = args.model_weight
    result = query_df(f"""
        WITH features AS (
          SELECT season, week, id, pos, proj, mean_projection,
                 model_points_pre, market_points
          FROM `{settings.predictions}.slate_player_features`
          WHERE panel_run_id = '{panel}' {eligibility}
        ), duplicate_keys AS (
          SELECT COUNT(*) AS n FROM (
            SELECT season, week, id
            FROM features GROUP BY season, week, id HAVING COUNT(*) != 1)
        ), candidates AS (
          SELECT c.season, c.week, c.cand_ix, c.sim_mean,
                 COUNTIF(f.id IS NULL) AS missing,
                 SUM(IF(f.pos = 'DST', f.proj,
                        COALESCE(f.mean_projection, f.proj))) AS expected_mean
          FROM `{settings.predictions}.{table}` c
          CROSS JOIN UNNEST(SPLIT(c.players, ',')) player_id
          LEFT JOIN features f
            ON f.season = c.season AND f.week = c.week AND f.id = player_id
          WHERE c.panel_run_id = '{panel}' {eligibility}
          GROUP BY c.season, c.week, c.cand_ix, c.sim_mean
        )
        SELECT
          COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-',
                                CAST(week AS STRING))) AS slates,
          COUNT(*) AS candidate_rows,
          (SELECT COUNT(*) FROM features) AS feature_rows,
          (SELECT n FROM duplicate_keys) AS duplicate_feature_keys,
          (SELECT COUNT(*) FROM features
           WHERE pos != 'DST' AND market_points IS NOT NULL)
            AS covered_offense_rows,
          (SELECT COUNT(*) FROM features
           WHERE pos != 'DST' AND market_points IS NULL)
            AS uncovered_offense_rows,
          (SELECT MAX(ABS(mean_projection -
                          ({model_weight} * model_points_pre
                           + {1.0 - model_weight} * market_points)))
           FROM features WHERE pos != 'DST' AND market_points IS NOT NULL)
            AS blend_max_abs_error,
          (SELECT MAX(ABS(mean_projection - model_points_pre))
           FROM features WHERE pos != 'DST' AND market_points IS NULL)
            AS uncovered_max_abs_error,
          SUM(missing) AS missing_roster_players,
          MAX(ABS(sim_mean - expected_mean)) AS candidate_mean_max_abs_error,
          APPROX_QUANTILES(ABS(sim_mean - expected_mean), 100)[OFFSET(95)]
            AS candidate_mean_p95_abs_error
        FROM candidates
        """).iloc[0].to_dict()

    int_fields = (
        "slates", "candidate_rows", "feature_rows", "duplicate_feature_keys",
        "covered_offense_rows", "uncovered_offense_rows",
        "missing_roster_players",
    )
    float_fields = (
        "blend_max_abs_error", "uncovered_max_abs_error",
        "candidate_mean_max_abs_error", "candidate_mean_p95_abs_error",
    )
    report = {name: int(result.get(name) or 0) for name in int_fields}
    report.update({
        name: float(result[name]) if result.get(name) is not None else None
        for name in float_fields
    })
    failures: list[str] = []
    if not report["candidate_rows"]:
        failures.append("candidate rows are empty")
    if not report["feature_rows"]:
        failures.append("feature rows are empty")
    if report["duplicate_feature_keys"]:
        failures.append("feature snapshot has duplicate player keys")
    if not report["covered_offense_rows"]:
        failures.append("market coverage is zero")
    if ((report["blend_max_abs_error"] is None)
            or report["blend_max_abs_error"] > 1e-5):
        failures.append("persisted covered means do not match model/market blend")
    if ((report["uncovered_max_abs_error"] is None)
            or report["uncovered_max_abs_error"] > 1e-5):
        failures.append("uncovered means do not match post-shaping model means")
    if report["missing_roster_players"]:
        failures.append("candidate rosters have missing players")
    if ((report["candidate_mean_max_abs_error"] is None)
            or report["candidate_mean_max_abs_error"] > 1e-3):
        failures.append(
            "candidate simulated means do not equal persisted player means")
    if report.get("slates") != args.expected_slates:
        failures.append(
            f"panel has {report.get('slates', 0)} slates, "
            f"want {args.expected_slates}")
    report["passes"] = not failures
    payload = {
        "panel_run_id": panel,
        "source_table": table,
        "model_weight": args.model_weight,
        "expected_slates": args.expected_slates,
        "audit": report,
        "failures": failures,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
