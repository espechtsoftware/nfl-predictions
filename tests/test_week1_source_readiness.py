"""Offline contracts for the 2026 Week 1 identity-source repair.

These checks stay deliberately narrow: nflverse roster schema compatibility
and the score-blind DK-to-GSIS identity SQL.  They do not query BigQuery or
inspect realized outcomes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import nflverse_job


ROOT = Path(__file__).resolve().parents[1]
PLAYER_ID_MAP_SQL = ROOT / "sql" / "features" / "001_player_id_map.sql"


class _FakeFrame:
    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def to_pandas(self) -> pd.DataFrame:
        return self._frame.copy()


def _roster_frame(season: int) -> _FakeFrame:
    teams = (
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
    )
    rows = 1_024
    return _FakeFrame(pd.DataFrame({
        "season": [season] * rows,
        "week": [1] * rows,
        "gsis_id": [f"00-{index:07d}" for index in range(rows)],
        "team": [teams[index % len(teams)] for index in range(rows)],
        "position": [("QB", "RB", "WR", "TE")[index % 4]
                     for index in range(rows)],
        "full_name": [f"Example Player {index}" for index in range(rows)],
        "football_name": [f"Example{index}" for index in range(rows)],
        "last_name": [f"Player{index}" for index in range(rows)],
        "jersey_number": [float(index % 100) for index in range(rows)],
        "game_type": ["REG"] * rows,
    }))


def _depth_frame(
    pulled_at: datetime,
    *,
    team_count: int = 32,
    age_days: int = 0,
) -> _FakeFrame:
    teams = [f"T{index:02d}" for index in range(team_count)]
    rows = max(1_024, team_count)
    dt = pd.Timestamp(pulled_at) - pd.Timedelta(days=age_days)
    return _FakeFrame(pd.DataFrame({
        "dt": [dt] * rows,
        "team": [teams[index % team_count] for index in range(rows)],
        "gsis_id": [f"00-d{index:06d}" for index in range(rows)],
        "player_name": [f"Depth Player {index}" for index in range(rows)],
        "pos_abb": [("QB", "RB", "WR", "TE")[index % 4]
                    for index in range(rows)],
        "pos_rank": [(index % 8) + 1 for index in range(rows)],
    }))


class _FakeNfl:
    def __init__(self, *, data_season: int = 2025, roster_season: int = 2026):
        self.data_season = data_season
        self.roster_season = roster_season
        self.public_calls: list[list[int]] = []

    def get_current_season(self, roster: bool = False) -> int:
        return self.roster_season if roster else self.data_season

    def load_rosters_weekly(self, seasons: list[int]) -> _FakeFrame:
        self.public_calls.append(seasons)
        return _roster_frame(seasons[0])


class _FakeDownloader:
    def __init__(self, frame: _FakeFrame):
        self.frame = frame
        self.calls: list[tuple[str, str, dict[str, int]]] = []

    def download(self, repository: str, path: str, **kwargs) -> _FakeFrame:
        self.calls.append((repository, path, kwargs))
        return self.frame


class _FakeDepthNfl:
    def __init__(self, frame: _FakeFrame):
        self.frame = frame
        self.calls: list[list[int]] = []

    def load_depth_charts(self, seasons: list[int]) -> _FakeFrame:
        self.calls.append(seasons)
        return self.frame


def test_roster_jersey_number_is_destination_string_before_load(monkeypatch):
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        nflverse_job,
        "load_dataframe",
        lambda frame, table, **kwargs: captured.append(frame.copy()),
    )

    nflverse_job._load(
        _FakeFrame(pd.DataFrame({
            "season": [2026, 2026, 2026],
            "gsis_id": ["00-a", "00-b", "00-c"],
            "jersey_number": [12.0, 7.0, None],
        })),
        "rosters_weekly",
    )

    assert len(captured) == 1
    loaded = captured[0]
    assert isinstance(loaded["jersey_number"].dtype, pd.StringDtype)
    assert loaded["jersey_number"].tolist()[:2] == ["12", "7"]
    assert pd.isna(loaded["jersey_number"].iloc[2])


def test_roster_destination_normalizer_rejects_fractional_jersey_number():
    frame = pd.DataFrame({"jersey_number": [12.5]})

    with pytest.raises(ValueError, match=r"(?i)jersey_number.*(?:integer|integral)"):
        nflverse_job._normalize_destination_frame(frame, "rosters_weekly")


def test_roster_destination_normalizes_complete_string_contract_before_load():
    frame = pd.DataFrame({
        "draft_number": [12.0, None],
        "espn_id": [12345.0, None],
        "team": [" CHI ", "GB"],
        "season": pd.Series([2026, 2026], dtype="Int64"),
    })

    normalized = nflverse_job._normalize_destination_frame(
        frame, "rosters_weekly",
    )

    for column in ("draft_number", "espn_id", "team"):
        assert isinstance(normalized[column].dtype, pd.StringDtype)
    assert normalized["draft_number"].tolist()[0] == "12"
    assert normalized["espn_id"].tolist()[0] == "12345"
    assert normalized["team"].tolist() == ["CHI", "GB"]
    assert normalized["season"].dtype == frame["season"].dtype


def test_roster_destination_rejects_fractional_string_identifier():
    frame = pd.DataFrame({"draft_number": [12.5]})

    with pytest.raises(ValueError, match=r"draft_number.*integer"):
        nflverse_job._normalize_destination_frame(frame, "rosters_weekly")


def test_roster_contract_failure_occurs_before_delete_or_load(monkeypatch):
    mutations: list[str] = []
    monkeypatch.setattr(
        nflverse_job,
        "_delete_seasons",
        lambda *args, **kwargs: mutations.append("delete"),
    )
    monkeypatch.setattr(
        nflverse_job,
        "load_dataframe",
        lambda *args, **kwargs: mutations.append("load"),
    )

    with pytest.raises(ValueError, match=r"draft_number.*integer"):
        nflverse_job._load(
            pd.DataFrame({"season": [2026], "draft_number": [12.5]}),
            "rosters_weekly",
            replace_seasons=[2026],
        )

    assert mutations == []


def test_roster_destination_rejects_numpy_boolean_string_value():
    import numpy as np

    with pytest.raises(ValueError, match=r"status.*boolean"):
        nflverse_job._normalize_destination_frame(
            pd.DataFrame({"status": [np.bool_(True)]}),
            "rosters_weekly",
        )


def test_destination_normalizer_does_not_mutate_other_tables():
    frame = pd.DataFrame({
        "season": pd.Series([2026], dtype="Int64"),
        "jersey_number": pd.Series([12.5], dtype="float64"),
    })

    normalized = nflverse_job._normalize_destination_frame(frame, "pbp")

    pd.testing.assert_frame_equal(normalized, frame)


def test_preseason_loader_dependency_is_pinned_to_reviewed_version():
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert '"nflreadpy==0.1.5"' in pyproject


def test_preseason_refresh_restores_completed_and_planning_sources():
    roster_seasons, snapshot_seasons = (
        nflverse_job._prospective_source_seasons(
            [2025], planning_season=2026, roster_year=2026,
        )
    )

    assert roster_seasons == [2025, 2026]
    assert snapshot_seasons == [2025, 2026]

    in_season_rosters, in_season_snapshots = (
        nflverse_job._prospective_source_seasons(
            [2026], planning_season=2026, roster_year=2026,
        )
    )
    assert in_season_rosters == [2026]
    assert in_season_snapshots == [2025, 2026]


def test_preseason_planning_roster_bypasses_only_stale_season_guard(monkeypatch):
    nfl = _FakeNfl()
    downloader = _FakeDownloader(_roster_frame(2026))
    monkeypatch.setattr(
        nflverse_job, "_weekly_roster_downloader", lambda: downloader,
    )
    pulled_at = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)

    result = nflverse_job._weekly_roster_frame(
        nfl, season=2026, pulled_at=pulled_at,
    )

    assert nfl.public_calls == []
    assert downloader.calls == [(
        "nflverse-data",
        "weekly_rosters/roster_weekly_2026",
        {"season": 2026},
    )]
    assert set(result.season) == {2026}
    assert set(result.nflverse_source_mode) == {
        "nflreadpy-preseason-weekly-roster-path"
    }
    assert set(result.nflverse_source_path) == {
        "weekly_rosters/roster_weekly_2026"
    }
    assert result.nflverse_pulled_at.eq(pd.Timestamp(pulled_at)).all()


def test_completed_roster_season_keeps_public_loader(monkeypatch):
    nfl = _FakeNfl()
    downloader = _FakeDownloader(_roster_frame(2026))
    monkeypatch.setattr(
        nflverse_job, "_weekly_roster_downloader", lambda: downloader,
    )

    result = nflverse_job._weekly_roster_frame(
        nfl,
        season=2025,
        pulled_at=datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc),
    )

    assert nfl.public_calls == [[2025]]
    assert downloader.calls == []
    assert set(result.season) == {2025}
    assert set(result.nflverse_source_mode) == {
        "nflreadpy-public-weekly-roster"
    }


def test_preseason_roster_rejects_future_or_mismatched_source(monkeypatch):
    nfl = _FakeNfl()
    downloader = _FakeDownloader(_roster_frame(2025))
    monkeypatch.setattr(
        nflverse_job, "_weekly_roster_downloader", lambda: downloader,
    )
    pulled_at = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="outside nflreadpy"):
        nflverse_job._weekly_roster_frame(
            nfl, season=2027, pulled_at=pulled_at,
        )
    with pytest.raises(ValueError, match="has seasons"):
        nflverse_job._weekly_roster_frame(
            nfl, season=2026, pulled_at=pulled_at,
        )


def test_weekly_roster_requires_complete_identity_schema_and_coverage(monkeypatch):
    pulled_at = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    missing_name_field = _roster_frame(2026)._frame.drop(columns=["football_name"])
    downloader = _FakeDownloader(_FakeFrame(missing_name_field))
    monkeypatch.setattr(
        nflverse_job, "_weekly_roster_downloader", lambda: downloader,
    )

    with pytest.raises(ValueError, match=r"missing columns.*football_name"):
        nflverse_job._weekly_roster_frame(
            _FakeNfl(), season=2026, pulled_at=pulled_at,
        )

    tiny = _roster_frame(2026)._frame.iloc[:32].copy()
    monkeypatch.setattr(
        nflverse_job,
        "_weekly_roster_downloader",
        lambda: _FakeDownloader(_FakeFrame(tiny)),
    )
    with pytest.raises(ValueError, match=r"only 32 distinct GSIS"):
        nflverse_job._weekly_roster_frame(
            _FakeNfl(), season=2026, pulled_at=pulled_at,
        )


def test_depth_snapshot_requires_current_complete_source_and_stamps_receipt():
    pulled_at = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    nfl = _FakeDepthNfl(_depth_frame(pulled_at))

    result = nflverse_job._depth_snapshot_frame(
        nfl, seasons=[2025, 2026], pulled_at=pulled_at,
    )

    assert nfl.calls == [[2025, 2026]]
    assert set(result.nflverse_source_seasons) == {"2025,2026"}
    assert set(result.nflverse_source_mode) == {
        "nflreadpy-public-depth-snapshots"
    }
    assert result.nflverse_pulled_at.eq(pd.Timestamp(pulled_at)).all()


@pytest.mark.parametrize(
    ("team_count", "age_days", "message"),
    ((31, 0, "31 teams"), (32, 15, "stale")),
)
def test_depth_snapshot_rejects_incomplete_or_stale_source(
    team_count: int,
    age_days: int,
    message: str,
):
    pulled_at = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    nfl = _FakeDepthNfl(_depth_frame(
        pulled_at, team_count=team_count, age_days=age_days,
    ))

    with pytest.raises(ValueError, match=message):
        nflverse_job._depth_snapshot_frame(
            nfl, seasons=[2025, 2026], pulled_at=pulled_at,
        )


@pytest.mark.parametrize(
    ("source_team", "canonical_team"),
    (
        ("NOS", "NO"),
        ("TBB", "TB"),
        ("LVR", "LV"),
        ("GBP", "GB"),
        ("GNB", "GB"),
        ("JAC", "JAX"),
    ),
)
def test_player_id_map_sql_canonicalizes_required_team_aliases(
    source_team: str,
    canonical_team: str,
):
    sql = PLAYER_ID_MAP_SQL.read_text()
    pattern = rf"WHEN\s+['\"]{source_team}['\"]\s+THEN\s+['\"]{canonical_team}['\"]"

    assert re.search(pattern, sql, flags=re.IGNORECASE), (
        f"player_id_map must canonicalize {source_team} to {canonical_team}"
    )


def test_roster_fallback_maps_only_unique_full_identity_and_rejects_ambiguity():
    """The SQL must discard a roster identity shared by multiple GSIS IDs.

    Grouping by normalized name + canonical team + position means a unique
    identity survives and is available to ``roster_fallback``.  The HAVING
    predicate means an otherwise identical two-player collision produces no
    fallback row, so the DK player remains unmapped rather than guessed.
    """
    sql = re.sub(r"\s+", " ", PLAYER_ID_MAP_SQL.read_text()).upper()

    assert "UNIQUE_ROSTER_IDENTITY AS" in sql
    assert re.search(
        r"GROUP BY\s+(?:[A-Z]+\.)?CLEAN_NAME\s*,\s*"
        r"(?:[A-Z]+\.)?CANONICAL_TEAM\s*,\s*(?:[A-Z]+\.)?POSITION",
        sql,
    )
    assert re.search(
        r"HAVING\s+COUNT\s*\(\s*DISTINCT\s+GSIS_ID\s*\)\s*=\s*1",
        sql,
    )
    assert "ROSTER_FALLBACK AS" in sql
    assert re.search(r"JOIN\s+UNIQUE_ROSTER_IDENTITY\b", sql)
    assert re.search(r"\.CLEAN_NAME\s*=\s*[A-Z]+\.CLEAN_NAME", sql)
    assert re.search(r"\.CANONICAL_TEAM\s*=\s*[A-Z]+\.CANONICAL_TEAM", sql)
    assert re.search(r"\.POSITION\s*=\s*[A-Z]+\.POSITION", sql)


def test_primary_crosswalk_is_unique_and_live_dk_ids_cannot_fan_out():
    sql = re.sub(r"\s+", " ", PLAYER_ID_MAP_SQL.read_text()).upper()

    assert re.search(
        r"PARTITION BY\s+DK_PLAYER_ID\s+ORDER BY\s+PULLED_AT DESC",
        sql,
    )
    assert "UNIQUE_PLAYER_ID_IDENTITY AS" in sql
    primary = sql[
        sql.index("UNIQUE_PLAYER_ID_IDENTITY AS"):sql.index("MATCHED AS")
    ]
    assert "GROUP BY CLEAN_NAME, CANONICAL_TEAM, POSITION" in primary
    assert "HAVING COUNT(DISTINCT GSIS_ID) = 1" in primary
    assert "JOIN UNIQUE_PLAYER_ID_IDENTITY" in sql


def test_crosswalk_uses_known_name_variants_with_canonical_normalization():
    sql = re.sub(r"\s+", " ", PLAYER_ID_MAP_SQL.read_text()).upper()

    assert "UNNEST([P.NAME, P.MERGE_NAME]) AS ID_NAME" in sql
    assert "UNNEST([R.FULL_NAME, CONCAT(R.FOOTBALL_NAME, ' ', R.LAST_NAME)])" in sql
    assert sql.count("R\" +\", \" \"") >= 3
    for source_team, canonical_team in (
        ("ARZ", "ARI"),
        ("BLT", "BAL"),
        ("CLV", "CLE"),
        ("HST", "HOU"),
        ("NWE", "NE"),
        ("NOR", "NO"),
        ("SDG", "LAC"),
        ("TAM", "TB"),
    ):
        assert f"WHEN '{source_team}' THEN '{canonical_team}'" in sql


def test_match_precedence_is_manual_primary_alias_roster_then_depth():
    sql = re.sub(r"\s+", " ", PLAYER_ID_MAP_SQL.read_text()).upper()

    assert sql.index("MANUAL_MATCHES AS") < sql.index("MATCHED AS")
    assert sql.index("MATCHED AS") < sql.index("ALIAS_MATCHES AS")
    assert sql.index("ALIAS_MATCHES AS") < sql.index("PRESERVED_MATCHES AS")
    assert sql.index("MANUAL_MATCHES AS") < sql.index("PRESERVED_MATCHES AS")
    assert sql.index("PRESERVED_MATCHES AS") < sql.index("ROSTER_FALLBACK AS")
    assert sql.index("ROSTER_FALLBACK AS") < sql.index("DEPTH_FALLBACK AS")
    assert "UNIQUE_MANUAL_OVERRIDES AS" in sql
    assert "COUNT(DISTINCT GSIS_ID) = 1" in sql
    matched = sql[sql.index("MATCHED AS"):sql.index("CURRENT_ROSTER_SEASON AS")]
    assert re.search(
        r"WHERE\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"
        r"MANUAL_MATCHES\s+M\s+WHERE\s+M\.DK_PLAYER_ID\s*=\s*"
        r"D\.DK_PLAYER_ID\s*\)",
        matched,
    )
    assert re.search(
        r"SELECT\s+\*\s+FROM\s+MANUAL_MATCHES\s+UNION\s+ALL\s+"
        r"SELECT\s+\*\s+FROM\s+MATCHED\s+UNION\s+ALL\s+"
        r"SELECT\s+\*\s+FROM\s+ALIAS_MATCHES",
        sql[sql.index("PRESERVED_MATCHES AS"):sql.index("ROSTER_FALLBACK AS")],
    )
    fallback = sql[sql.index("ROSTER_FALLBACK AS"):]
    assert re.search(
        r"WHERE\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"
        r"PRESERVED_MATCHES\s+P\s+WHERE\s+P\.DK_PLAYER_ID\s*=\s*"
        r"D\.DK_PLAYER_ID\s*\)",
        fallback,
    )
    assert re.search(
        r"ROSTER_AUGMENTED_MATCHES AS\s*\(\s*SELECT\s+\*\s+FROM\s+"
        r"PRESERVED_MATCHES\s+UNION\s+ALL\s+"
        r"SELECT\s+\*\s+FROM\s+ROSTER_FALLBACK",
        sql,
    )
    assert re.search(
        r"SELECT\s+\*\s+FROM\s+ROSTER_AUGMENTED_MATCHES\s+UNION\s+ALL\s+"
        r"SELECT\s+\*\s+FROM\s+DEPTH_FALLBACK",
        sql,
    )


def test_depth_fallback_and_reviewed_live_aliases_are_exact_and_unique():
    sql = re.sub(r"\s+", " ", PLAYER_ID_MAP_SQL.read_text()).upper()

    assert "'KENNY GAINWELL' AS SOURCE_CLEAN_NAME" in sql
    assert "'KENNETH GAINWELL' AS TARGET_CLEAN_NAME" in sql
    assert "('HOLLYWOOD BROWN', 'MARQUISE BROWN')" in sql
    assert "('NICK SINGLETON', 'NICHOLAS SINGLETON')" in sql
    assert "('JOSHUA PITSENBERGER', 'JOSH PITSENBERGER')" in sql
    assert "('MATT HIBNER', 'MATTHEW HIBNER')" in sql
    assert "UNIQUE_DEPTH_IDENTITY AS" in sql
    depth_unique = sql[
        sql.index("UNIQUE_DEPTH_IDENTITY AS"):sql.index("DEPTH_FALLBACK AS")
    ]
    assert "GROUP BY CLEAN_NAME, CANONICAL_TEAM, POSITION" in depth_unique
    assert "HAVING COUNT(DISTINCT GSIS_ID) = 1" in depth_unique
    depth = sql[sql.index("DEPTH_FALLBACK AS"):]
    assert "X.CLEAN_NAME = D.CLEAN_NAME" in depth
    assert "X.CANONICAL_TEAM = D.CANONICAL_TEAM" in depth
    assert "X.POSITION = D.POSITION" in depth
    assert "ROSTER_AUGMENTED_MATCHES" in depth


def test_player_id_map_binds_live_sources_and_rejects_identity_conflicts():
    sql = re.sub(r"\s+", " ", PLAYER_ID_MAP_SQL.read_text()).upper()

    assert "LIVE_DK_SEASON AS" in sql
    assert "SELECT SEASON FROM LIVE_DK_SEASON" in sql
    assert sql.count("NFLVERSE_PULLED_AT") >= 4
    assert "INTERVAL 72 HOUR" in sql
    assert "INTERVAL 14 DAY" in sql
    assert "COUNT(DISTINCT R.TEAM) = 32" in sql
    assert "PLAYER_ID_OVERRIDES CONTAINS A NULL OR CONFLICTING" in sql
    assert "PLAYER_ID_MAP CONTAINS A DUPLICATE OR CONFLICTING" in sql
