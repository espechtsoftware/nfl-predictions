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
    archive_check_ok,
    capture,
    directional_pairs,
    export_rows_for,
    schedule_frame,
    snapshots_for,
)


KICKOFF = pd.Timestamp("2026-09-27T17:00:00Z")
GENERATED = datetime(2026, 9, 25, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[1]


def _staged_frame(report: str, *, retrieved: str, sha: str, value: float = 1.0, unresolved: set | None = None) -> pd.DataFrame:
    pairs = directional_pairs(schedule_frame())
    rows = []
    for index, (team, opponent) in enumerate(pairs):
        player = report != "line-matchups"
        pos = "QB" if report == "qb-coverage-matchup" else "WR"
        resolved = player and team not in (unresolved or set())
        row = {
            "season": 2026, "target_week": 3, "report": report,
            "source_sha256": sha, "source_row": index + 3,
            "identity": (f"00-{team}" if resolved else f"UNRESOLVED:{pos.lower()} {team.lower()}:{pos}:{team}") if player else team,
            "team": team, "opponent": opponent,
            "gsis_id": f"00-{team}" if resolved else None,
            "resolution_status": ("resolved" if resolved else "unresolved") if player else "team",
            "vendor_name": f"{pos} {team}" if player else team,
            "normalized_name": f"{pos.lower()} {team.lower()}" if player else "",
            "vendor_pos": pos if player else "", "pos": pos if player else None,
            "canonical_teams": team,
            "games": 17, "source_season": 2025, "source_regime": "vendor-prior-season-early",
            "source_run_id": f"run-{sha}",
            "source_retrieved_at": pd.Timestamp(retrieved),
            "first_kickoff_utc": KICKOFF, "archive_uri": f"gs://b/{sha}",
        }
        for column in weekly.metric_columns(report):
            row[column] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _snapshots() -> pd.DataFrame:
    rows = []
    for index, (team, _) in enumerate(directional_pairs(schedule_frame())):
        for pos in ("QB", "WR"):
            rows.append({"season": 2026, "gsis_id": f"00-{pos}{index:03d}", "name": f"{pos} {team}", "pos": pos, "team": team})
    return pd.DataFrame(rows)


def test_select_point_in_time_keeps_latest_capture_before_kickoff():
    early = _staged_frame("line-matchups", retrieved="2026-09-22T15:00Z", sha="a", value=1.0)
    late = _staged_frame("line-matchups", retrieved="2026-09-24T12:00Z", sha="b", value=2.0)
    selected = shadow.select_point_in_time(
        pd.concat([early, late]), season=2026, week=3, kickoff=KICKOFF, generated_at=GENERATED,
    )
    assert len(selected) == 4
    assert selected.source_sha256.eq("b").all()
    assert selected.offense__ybco.eq(2.0).all()
    assert selected.captures_available.eq(2).all()
    assert selected.week.eq(3).all()
    assert selected.pit_lag_hours.round(1).eq(77.0).all()


def test_shadow_dedupes_on_vendor_identity_across_resolution_changes():
    # Tuesday: BUF's QB unresolved; Thursday: resolved.  One shadow row.
    early = _staged_frame("qb-coverage-matchup", retrieved="2026-09-22T15:00Z", sha="a", unresolved={"BUF"})
    late = _staged_frame("qb-coverage-matchup", retrieved="2026-09-24T12:00Z", sha="b")
    selected = shadow.select_point_in_time(
        pd.concat([early, late]), season=2026, week=3, kickoff=KICKOFF, generated_at=GENERATED,
    )
    assert len(selected) == 4
    assert selected.source_sha256.eq("b").all()
    resolved = shadow.resolve_identities(selected, report="qb-coverage-matchup", snapshots=_snapshots())
    assert resolved.gsis_id.notna().all()
    assert resolved.resolution_status.eq("resolved").all()
    assert not resolved.identity.str.startswith("UNRESOLVED").any()
    # Without a snapshot row the build-time resolution says so; nothing is guessed.
    partial = shadow.resolve_identities(selected, report="qb-coverage-matchup", snapshots=_snapshots().iloc[2:])
    assert partial.resolution_status.tolist().count("unresolved") == 1


def test_shadow_fails_closed_on_a_capture_at_or_after_kickoff():
    fine = _staged_frame("line-matchups", retrieved="2026-09-22T15:00Z", sha="a")
    at_kickoff = _staged_frame("line-matchups", retrieved="2026-09-27T17:00Z", sha="b")
    with pytest.raises(shadow.MatchupLeakageError, match="at/after their target kickoff"):
        shadow.select_point_in_time(
            pd.concat([fine, at_kickoff]), season=2026, week=3, kickoff=KICKOFF, generated_at=GENERATED,
        )
    # The schedule authority, not the rows, decides the kickoff.
    with pytest.raises(shadow.MatchupLeakageError, match="at/after their target kickoff"):
        shadow.select_point_in_time(
            fine, season=2026, week=3, kickoff=pd.Timestamp("2026-09-22T15:00Z"), generated_at=GENERATED,
        )
    with pytest.raises(shadow.MatchupLeakageError, match="disagree with the schedule"):
        shadow.select_point_in_time(
            fine, season=2026, week=3, kickoff=pd.Timestamp("2026-09-28T17:00Z"), generated_at=GENERATED,
        )
    wrong_week = fine.assign(target_week=4)
    with pytest.raises(ValueError, match="not all for the requested target week"):
        shadow.select_point_in_time(wrong_week, season=2026, week=3, kickoff=KICKOFF, generated_at=GENERATED)
    future_source = fine.assign(source_season=2027)
    with pytest.raises(shadow.MatchupLeakageError, match="source season after"):
        shadow.assert_capture_strict_prior(future_source, kickoff=KICKOFF)


def test_build_requires_every_report_and_reports_lags():
    staged = {key: _staged_frame(key, retrieved="2026-09-22T15:00Z", sha="a") for key in weekly.REPORTS}
    frames, audit = shadow.build(
        week=3, kickoff=KICKOFF, staged=staged, snapshots=_snapshots(), generated_at=GENERATED,
    )
    for key in weekly.REPORTS:
        assert len(frames[key]) == 4
        assert audit["reports"][key]["shadow_rows"] == 4
        assert audit["reports"][key]["distinct_captures"] == 1
        assert audit["reports"][key]["min_pit_lag_hours"] == pytest.approx(122.0)
        assert audit["reports"][key]["selected_captures"] == {"run-a": "a"}
        assert "target_week" not in frames[key].columns and "week" in frames[key].columns
    assert frames["line-matchups"].gsis_id.isna().all()
    assert frames["qb-coverage-matchup"].gsis_id.notna().all()
    del staged["wr-coverage-matchup"]
    with pytest.raises(ValueError, match="wr-coverage-matchup: nothing staged"):
        shadow.build(week=3, kickoff=KICKOFF, staged=staged, snapshots=_snapshots(), generated_at=GENERATED)


class FakeWarehouse:
    """Staging tables written by the loader; shadow tables written by the join."""

    def __init__(self, snapshots: pd.DataFrame) -> None:
        self.snapshots = snapshots
        self.staged: dict[str, pd.DataFrame] = {}
        self.shadow: dict[str, pd.DataFrame] = {}
        self.loads: list[tuple[str, int]] = []

    def _staged_key(self, table: str):
        name = table.rsplit(".", 1)[1]
        return next((key for key, staged_name in weekly.TABLES.items() if staged_name == name), None)

    def query_df(self, sql: str, params=None):
        from google.api_core.exceptions import NotFound

        if "rosters_weekly" in sql:
            return self.snapshots
        table = sql.split("`")[1]
        key = self._staged_key(table)
        if key is not None:
            if key not in self.staged:
                raise NotFound(table)
            frame = self.staged[key]
            week = params.get("target_week", params.get("week"))
            return frame[(frame.season == params["season"]) & (frame.target_week == week)]
        if table in self.shadow:
            return self.shadow[table]
        raise NotFound(table)

    def load_dataframe(self, df, table, write_disposition="WRITE_TRUNCATE", **_):
        assert write_disposition == "WRITE_APPEND"
        key = self._staged_key(table)
        if key is not None:
            self.staged[key] = pd.concat([self.staged.get(key, pd.DataFrame()), df], ignore_index=True)
            return
        self.loads.append((table, len(df)))
        self.shadow[table] = pd.concat([self.shadow.get(table, pd.DataFrame()), df], ignore_index=True)


def test_run_end_to_end_capture_stage_shadow_and_ledgers(tmp_path, monkeypatch):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    house = FakeWarehouse(snapshots_for(schedule))
    monkeypatch.setattr(bq, "query_df", house.query_df)
    monkeypatch.setattr(bq, "load_dataframe", house.load_dataframe)
    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)
    monkeypatch.setattr(weekly, "_schedule", lambda season, week: schedule)
    root = tmp_path / "automated"

    script = {d.key: [export_rows_for(d.key, pairs)] for d in matchups.MATCHUPS}
    run_a = capture(tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, archive=True).parent
    weekly.run(run_a, target_week=3, write=True, archive_check=archive_check_ok)
    audit = shadow.run(week=3, write=True, output_root=root, now=GENERATED)
    assert audit["featureset_activated"] is False
    assert [rows for _, rows in house.loads] == [4, 4, 4]
    for key in weekly.REPORTS:
        table = f"{bq.settings.features}.{shadow.SHADOW_TABLES[key]}"
        assert audit["shadow_tables"][key] == table
        assert audit["reports"][key]["write_disposition"] == "appended"
        assert audit["consumed_ledgers"][run_a.name][key] == "consumed"
        frame = house.shadow[table]
        assert frame.week.eq(3).all()
        assert (frame.pit_lag_hours > 0).all()
    ledger = matchups.read_ledger(run_a)
    for key in weekly.REPORTS:
        assert ledger["reports"][key]["consumed"]["table"].endswith(shadow.SHADOW_TABLES[key])
        assert ledger["reports"][key]["consumed"]["sha256"] == ledger["reports"][key]["validated"]["sha256"]

    again = shadow.run(week=3, write=True, output_root=root, now=GENERATED)
    assert len(house.loads) == 3
    assert all(item["write_disposition"] == "already-identical" for item in again["reports"].values())

    # A later capture B supersedes A: B's rows are appended, B's ledger is
    # consumed, A's ledger is untouched (it was consumed for its own bytes).
    script = {d.key: [export_rows_for(d.key, pairs, value=0.9)] for d in matchups.MATCHUPS}
    run_b = capture(
        tmp_path / "b", monkeypatch, FakeDriver(script), schedule=schedule, archive=True,
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    ).parent
    (root / run_b.name).symlink_to(run_b)
    weekly.run(run_b, target_week=3, write=True, archive_check=archive_check_ok)
    third = shadow.run(week=3, write=True, output_root=root, now=GENERATED)
    assert [rows for _, rows in house.loads] == [4, 4, 4, 4, 4, 4]
    for key in weekly.REPORTS:
        assert third["reports"][key]["selected_captures"].keys() == {run_b.name}
        assert third["consumed_ledgers"] == {run_b.name: {k: "consumed" for k in weekly.REPORTS}} or \
            third["consumed_ledgers"][run_b.name][key] == "consumed"
    assert matchups.read_ledger(run_b)["reports"]["line-matchups"]["consumed"]["sha256"] == \
        matchups.read_ledger(run_b)["reports"]["line-matchups"]["validated"]["sha256"]
    assert matchups.read_ledger(run_a)["reports"]["line-matchups"]["consumed"]["sha256"] == \
        matchups.read_ledger(run_a)["reports"]["line-matchups"]["validated"]["sha256"]

    # Without output_root the ledgers are left alone and the audit says so.
    fourth = shadow.run(week=3, write=True, now=GENERATED)
    assert fourth["consumed_ledgers"] == "not-recorded (no output_root)"


def test_shadow_dry_run_writes_nothing(tmp_path, monkeypatch):
    schedule = schedule_frame()
    house = FakeWarehouse(snapshots_for(schedule))
    house.staged = {key: _staged_frame(key, retrieved="2026-09-22T15:00Z", sha="a") for key in weekly.REPORTS}
    monkeypatch.setattr(bq, "query_df", house.query_df)
    monkeypatch.setattr(bq, "load_dataframe", house.load_dataframe)
    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)
    audit = shadow.run(week=3, write=False, now=GENERATED)
    assert house.loads == []
    assert all(r["append_rows"] == 4 for r in audit["reports"].values())
    assert "write_disposition" not in audit["reports"]["line-matchups"]


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
