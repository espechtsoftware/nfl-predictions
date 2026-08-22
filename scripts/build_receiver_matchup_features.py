"""Build the P1 receiver-matchup research tables with PIT validation.

Runs sql/research/017l then 017m (deliberately OUTSIDE the production
sql/features build glob), then executes fail-closed point-in-time and
structural validation queries against the built tables. Default-off: both
the literal --execute flag and RECEIVER_MATCHUP_FEATURES_ENABLED=1 are
required for any BigQuery contact; `render` mode is offline and prints the
rendered SQL byte lengths only.

Validation law (each query must return zero violation rows):
  - every 017l/017m row's maximum source (season, week) is strictly before
    its target (season, week);
  - (gsis_id, season, week) and (defense, season, week, role_label) are
    unique;
  - percentiles lie in [0, 1]; supported concession rows have at least four
    prior defense games; shrunk rates are nonnegative.

This is research tooling: no production feature, model, fill, retrieval, or
policy surface is touched, and no realized target-week outcome is read as a
feature (source-game outcomes strictly prior to the target week are the
concession inputs, per the plan's design laws).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_SQL = ROOT / "sql" / "research"
ENABLE_ENV = "RECEIVER_MATCHUP_FEATURES_ENABLED"

SQL_FILES = (
    "017l_receiver_week_role_pit.sql",
    "017m_defense_receiver_role_concession_pit.sql",
)

VALIDATION_QUERIES: tuple[tuple[str, str], ...] = (
    (
        "role-pit-strictly-prior",
        """
        SELECT COUNT(*) AS violations
        FROM `${features}.receiver_week_role_pit`
        WHERE max_source_season_week IS NOT NULL
          AND max_source_season_week >= season * 100 + week
        """,
    ),
    (
        "role-unique-player-week",
        """
        SELECT COALESCE(SUM(n - 1), 0) AS violations FROM (
          SELECT COUNT(*) AS n
          FROM `${features}.receiver_week_role_pit`
          GROUP BY gsis_id, season, week
        )
        """,
    ),
    (
        "role-percentiles-bounded",
        """
        SELECT COUNT(*) AS violations
        FROM `${features}.receiver_week_role_pit`
        WHERE (role_consensus_score IS NOT NULL
               AND (role_consensus_score < 0 OR role_consensus_score > 1))
           OR (target_share_percentile IS NOT NULL
               AND (target_share_percentile < 0
                    OR target_share_percentile > 1))
        """,
    ),
    (
        "role-label-support-consistency",
        """
        SELECT COUNT(*) AS violations
        FROM `${features}.receiver_week_role_pit`
        WHERE (role_supported AND role_label IS NULL)
           OR (NOT role_supported AND role_label IS NOT NULL)
        """,
    ),
    (
        "concession-strictly-prior",
        """
        SELECT COUNT(*) AS violations
        FROM `${features}.defense_receiver_role_concession_pit`
        WHERE max_source_season_week IS NOT NULL
          AND max_source_season_week >= season * 100 + week
        """,
    ),
    (
        "concession-unique-defense-week-role",
        """
        SELECT COALESCE(SUM(n - 1), 0) AS violations FROM (
          SELECT COUNT(*) AS n
          FROM `${features}.defense_receiver_role_concession_pit`
          GROUP BY defense, season, week, role_label
        )
        """,
    ),
    (
        "concession-support-law",
        """
        SELECT COUNT(*) AS violations
        FROM `${features}.defense_receiver_role_concession_pit`
        WHERE (concession_supported AND prior_defense_games_l8 < 4)
           OR (NOT concession_supported AND prior_defense_games_l8 >= 4)
        """,
    ),
    (
        "concession-shrunk-rates-nonnegative",
        """
        SELECT COUNT(*) AS violations
        FROM `${features}.defense_receiver_role_concession_pit`
        WHERE dk_per_target_allowed_shrunk_l8 < 0
           OR catch_rate_allowed_shrunk_l8 < 0
           OR yards_per_target_allowed_shrunk_l8 < 0
        """,
    ),
)


def _render_all() -> dict[str, int]:
    from nfl_dfs.bq import render_sql

    rendered: dict[str, int] = {}
    for name in SQL_FILES:
        rendered[name] = len(render_sql(RESEARCH_SQL / name))
    return rendered


def _execute() -> dict[str, object]:
    from nfl_dfs import bq
    from nfl_dfs.bq import run_sql_file

    for name in SQL_FILES:
        run_sql_file(RESEARCH_SQL / name)
    checks: list[dict[str, object]] = []
    failures = 0
    for check_id, template in VALIDATION_QUERIES:
        rendered = template.replace("${features}", bq.settings.features)
        frame = bq.query_df(rendered)
        violations = int(frame["violations"].iloc[0])
        checks.append({"check": check_id, "violations": violations})
        if violations:
            failures += 1
    counts = bq.query_df(
        "SELECT 'receiver_week_role_pit' AS table_name, COUNT(*) AS n "
        f"FROM `{bq.settings.features}.receiver_week_role_pit` "
        "UNION ALL "
        "SELECT 'defense_receiver_role_concession_pit', COUNT(*) "
        f"FROM `{bq.settings.features}.defense_receiver_role_concession_pit`"
    )
    return {
        "schema_version": "receiver-matchup-p1-build/v1",
        "tables": {
            str(row["table_name"]): int(row["n"])
            for _, row in counts.iterrows()
        },
        "validation": checks,
        "validation_failures": failures,
        "uses_realized_outcomes_as_features": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render", help="offline render check; no BigQuery contact")
    execute = sub.add_parser("execute", help="build tables + validate")
    execute.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "render":
        rendered = _render_all()
        print(json.dumps({
            "schema_version": "receiver-matchup-p1-render/v1",
            "rendered_bytes": rendered,
            "bigquery_contacted": False,
        }, sort_keys=True))
        return 0
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        print(
            f"execution requires literal --execute and {ENABLE_ENV}=1",
            file=sys.stderr,
        )
        return 2
    receipt = _execute()
    print(json.dumps(receipt, sort_keys=True))
    return 3 if receipt["validation_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
