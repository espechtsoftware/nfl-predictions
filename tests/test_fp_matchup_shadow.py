import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs import bq
from nfl_dfs.ingest import fantasy_points_matchups_weekly as weekly
from nfl_dfs.ops import fantasy_points_matchups as matchups
from nfl_dfs.research import fp_matchup_shadow as shadow
from tests.fp_matchup_fixtures import (
    FakeDriver,
    capture,
    directional_pairs,
    export_rows_for,
    schedule_frame,
    snapshots_for,
)


KICKOFF = pd.Timestamp("2026-09-27T17:00:00Z")
REPO = Path(__file__).resolve().parents[1]


def _staged_frame(report: str, *, retrieved: str, sha: str, value: float = 1.0) -> pd.DataFrame:
    pairs = directional_pairs(schedule_frame())
    rows = []
    for team, opponent in pairs:
        row = {
            "season": 2026, "target_week": 3, "report": report,
            "identity": team if report == "line-matchups" else f"00-{team}",
            "team": team, "opponent": opponent,
            "gsis_id": None if report == "line-matchups" else f"00-{team}",
            "resolution_status": "team" if report == "line-matchups" else "resolved",
            "vendor_name": team, "pos": None if report == "line-matchups" else "QB",
            "games": 17, "source_season": 2025, "source_regime": "vendor-prior-season-early",
            "source_sha256": sha, "source_run_id": f"run-{sha}",
            "source_retrieved_at": pd.Timestamp(retrieved),
            "first_kickoff_utc": KICKOFF, "archive_uri": f"gs://b/{sha}",
        }
        for column in weekly.metric_columns(report):
            row[column] = value
        rows.append(row)
    return pd.DataFrame(rows)


def test_select_point_in_time_keeps_latest_capture_before_kickoff():
    early = _staged_frame("line-matchups", retrieved="2026-09-22T15:00Z", sha="a", value=1.0)
    late = _staged_frame("line-matchups", retrieved="2026-09-24T12:00Z", sha="b", value=2.0)
    selected = shadow.select_point_in_time(
        pd.concat([early, late]), season=2026, week=3, kickoff=KICKOFF,
        generated_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert len(selected) == 4
    assert selected.source_sha256.eq("b").all()
    assert selected.offense__ybco.eq(2.0).all()
    assert selected.captures_available.eq(2).all()
    assert selected.week.eq(3).all()
    assert selected.pit_lag_hours.round(1).eq(77.0).all()


def test_shadow_fails_closed_on_a_capture_at_or_after_kickoff():
    fine = _staged_frame("line-matchups", retrieved="2026-09-22T15:00Z", sha="a")
    at_kickoff = _staged_frame("line-matchups", retrieved="2026-09-27T17:00Z", sha="b")
    with pytest.raises(shadow.MatchupLeakageError, match="at/after their target kickoff"):
        shadow.select_point_in_time(
            pd.concat([fine, at_kickoff]), season=2026, week=3, kickoff=KICKOFF,
            generated_at=datetime(2026, 9, 25, tzinfo=UTC),
        )
    wrong_week = fine.assign(target_week=4)
    with pytest.raises(ValueError, match="not all for the requested target week"):
        shadow.select_point_in_time(
            wrong_week, season=2026, week=3, kickoff=KICKOFF,
            generated_at=datetime(2026, 9, 25, tzinfo=UTC),
        )
    future_source = fine.assign(source_season=2027)
    with pytest.raises(shadow.MatchupLeakageError, match="source season after"):
        shadow.assert_capture_strict_prior(future_source)


def test_build_requires_every_report_and_reports_lags():
    staged = {
        key: _staged_frame(key, retrieved="2026-09-22T15:00Z", sha="a")
        for key in weekly.REPORTS
    }
    frames, audit = shadow.build(
        week=3, kickoff=KICKOFF, staged=staged, generated_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    for key in weekly.REPORTS:
        assert len(frames[key]) == 4
        assert audit["reports"][key]["shadow_rows"] == 4
        assert audit["reports"][key]["distinct_captures"] == 1
        assert audit["reports"][key]["min_pit_lag_hours"] == pytest.approx(122.0)
        assert "target_week" not in frames[key].columns and "week" in frames[key].columns
    del staged["wr-coverage-matchup"]
    with pytest.raises(ValueError, match="wr-coverage-matchup: nothing staged"):
        shadow.build(week=3, kickoff=KICKOFF, staged=staged, generated_at=datetime(2026, 9, 25, tzinfo=UTC))


class FakeWarehouse:
    def __init__(self, staged: dict[str, pd.DataFrame], snapshots: pd.DataFrame) -> None:
        self.staged = staged
        self.snapshots = snapshots
        self.shadow: dict[str, pd.DataFrame] = {}
        self.loads: list[tuple[str, int]] = []

    def query_df(self, sql: str, params=None):
        from google.api_core.exceptions import NotFound

        if "rosters_weekly" in sql:
            return self.snapshots
        table = sql.split("`")[1]
        name = table.rsplit(".", 1)[1]
        for key, staged_name in weekly.TABLES.items():
            if staged_name == name:
                if key not in self.staged:
                    raise NotFound(table)
                return self.staged[key]
        if table in self.shadow:
            return self.shadow[table]
        raise NotFound(table)

    def load_dataframe(self, df, table, write_disposition="WRITE_TRUNCATE", **_):
        assert write_disposition == "WRITE_APPEND"
        self.loads.append((table, len(df)))
        self.shadow[table] = pd.concat([self.shadow.get(table, pd.DataFrame()), df], ignore_index=True)


def test_run_end_to_end_capture_stage_shadow_and_ledger(tmp_path, monkeypatch):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    script = {d.key: [export_rows_for(d.key, pairs)] for d in matchups.MATCHUPS}
    run_dir = capture(tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, archive=True).parent

    house = FakeWarehouse({}, snapshots_for(schedule))

    def query_df(sql, params=None):
        if "rosters_weekly" in sql:
            return house.snapshots
        table = sql.split("`")[1]
        for key, staged_name in weekly.TABLES.items():
            if staged_name == table.rsplit(".", 1)[1]:
                if key not in house.staged:
                    from google.api_core.exceptions import NotFound

                    raise NotFound(table)
                frame = house.staged[key]
                if params and "target_week" in params:
                    return frame[(frame.season == params["season"]) & (frame.target_week == params["target_week"])]
                return frame
        return house.query_df(sql, params)

    def load_dataframe(df, table, write_disposition="WRITE_TRUNCATE", **_):
        assert write_disposition == "WRITE_APPEND"
        name = table.rsplit(".", 1)[1]
        for key, staged_name in weekly.TABLES.items():
            if staged_name == name:
                house.staged[key] = pd.concat([house.staged.get(key, pd.DataFrame()), df], ignore_index=True)
                return
        house.load_dataframe(df, table, write_disposition)

    monkeypatch.setattr(bq, "query_df", query_df)
    monkeypatch.setattr(bq, "load_dataframe", load_dataframe)
    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)

    weekly.run(run_dir, target_week=3, write=True)
    audit = shadow.run(week=3, write=True, run_dir=run_dir, now=datetime(2026, 9, 25, tzinfo=UTC))
    assert audit["featureset_activated"] is False
    assert [rows for _, rows in house.loads] == [4, 4, 4]
    for key in weekly.REPORTS:
        table = f"{bq.settings.features}.{shadow.SHADOW_TABLES[key]}"
        assert audit["shadow_tables"][key] == table
        assert audit["reports"][key]["write_disposition"] == "appended"
        assert audit["reports"][key]["ledger"] == "consumed"
        frame = house.shadow[table]
        assert frame.week.eq(3).all()
        assert (frame.pit_lag_hours > 0).all()
    ledger = matchups.read_ledger(run_dir)
    for key in weekly.REPORTS:
        assert ledger["reports"][key]["consumed"]["table"].endswith(shadow.SHADOW_TABLES[key])

    again = shadow.run(week=3, write=True, run_dir=run_dir, now=datetime(2026, 9, 25, tzinfo=UTC))
    assert len(house.loads) == 3
    assert all(item["write_disposition"] == "already-identical" for item in again["reports"].values())


def test_shadow_tables_are_not_wired_into_production_features():
    names = list(shadow.SHADOW_TABLES.values()) + list(weekly.TABLES.values())
    pattern = re.compile("|".join(map(re.escape, names)))
    featureset = (REPO / "src" / "nfl_dfs" / "models" / "featureset.py").read_text()
    assert not pattern.search(featureset)
    for sql_path in sorted((REPO / "sql" / "features").glob("*.sql")):
        assert not pattern.search(sql_path.read_text()), sql_path.name
    inference = (REPO / "src" / "nfl_dfs" / "inference").glob("*.py")
    for path in inference:
        assert not pattern.search(path.read_text()), path.name
