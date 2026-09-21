"""Shared offline fixtures for the Fantasy Points live matchup chain.

Builds vendor-shaped exports (two-row grouped headers identical to the sealed
Week-1 files), a schedule frame, and a scripted browser driver so the capture,
the staging loader and the shadow join can be exercised end to end without
Playwright or BigQuery.
"""

from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from nfl_dfs.config import settings
from nfl_dfs.ingest.fantasy_points_matchups_weekly import EXPECTED_HEADERS, expected_archive_uri
from nfl_dfs.ops import fantasy_points_matchups as matchups


TEAM_FULL = {
    "BUF": "Buffalo Bills", "BAL": "Baltimore Ravens", "KC": "Kansas City Chiefs",
    "DEN": "Denver Broncos", "ARI": "Arizona Cardinals", "CAR": "Carolina Panthers",
    "LAC": "Los Angeles Chargers", "CHI": "Chicago Bears",
}
VENDOR_CODE = {"BAL": "BLT", "ARI": "ARZ"}  # vendor spellings for some clubs
DEFAULT_NOW = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)


def schedule_frame(
    games: list[tuple[str, str]] | None = None, *, gameday: str = "2026-09-27",
) -> pd.DataFrame:
    games = games or [("BUF", "BAL"), ("KC", "DEN")]
    return pd.DataFrame([
        {"home_team": home, "away_team": away, "gameday": gameday, "gametime": "13:00"}
        for home, away in games
    ])


def _write_grouped(path: Path, report: str, rows: list[list[str]]) -> None:
    headers = EXPECTED_HEADERS[report]
    groups: list[str] = []
    seen = ""
    for column in headers:
        group = column.split("::", 1)[0]
        groups.append(group if group != seen else "")
        seen = group
    names = [column.split("::", 1)[1] for column in headers]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(groups)
        writer.writerow(names)
        for row in rows:
            assert len(row) == len(headers), (report, len(row), len(headers))
            writer.writerow(row)


def player_rows(
    report: str,
    players: list[tuple[str, str, str, str]],
    *,
    season: int = 2025,
    value: float = 0.5,
    games: int = 17,
) -> list[list[str]]:
    """``players`` = (name, vendor team cell, pos, vendor opponent cell)."""
    width = len(EXPECTED_HEADERS[report])
    rows = []
    for rank, (name, team, pos, opponent) in enumerate(players, start=1):
        identity = [str(rank), name, team, pos, str(games), str(season), opponent]
        metrics = [f"{value + rank / 100:.2f}"] * (width - len(identity))
        rows.append(identity + metrics)
    return rows


def line_rows(
    pairs: list[tuple[str, str]], *, season: int = 2025, value: float = 1.5, games: int = 17,
) -> list[list[str]]:
    rows = []
    for rank, (team, opponent) in enumerate(pairs, start=1):
        full = TEAM_FULL[team]
        location, nickname = full.rsplit(" ", 1)
        rows.append([
            str(rank), full, str(games), str(season), location, nickname,
            f"{value:.2f}", f"{value:.2f}", f"{value:.2f}", "40.0", "5.0",
            VENDOR_CODE.get(team, team), "500", "900",
            TEAM_FULL[opponent], f"{value:.2f}", "35.0", "1.0", "480", "1000",
        ])
    return rows


def export_rows_for(report: str, pairs: list[tuple[str, str]], **kwargs: Any) -> list[list[str]]:
    """A complete export covering every scheduled team once (per side)."""
    if report == "line-matchups":
        return line_rows(pairs, **kwargs)
    pos = "QB" if report == "qb-coverage-matchup" else "WR"
    players = [
        (f"{pos} {team}", VENDOR_CODE.get(team, team), pos, VENDOR_CODE.get(opponent, opponent))
        for team, opponent in pairs
    ]
    return player_rows(report, players, **kwargs)


def directional_pairs(schedule: pd.DataFrame) -> list[tuple[str, str]]:
    pairs = []
    for row in schedule.itertuples(index=False):
        pairs.append((row.home_team, row.away_team))
        pairs.append((row.away_team, row.home_team))
    return sorted(pairs)


class FakeResponse:
    def __init__(self, definition: matchups.MatchupDefinition, *, status: int = 200) -> None:
        self.status = status
        self.request = type("Request", (), {})()
        self.request.post_data = json.dumps({
            "context": {"tableProperty": definition.property, "requiresSchedule": True},
        })

    def json(self) -> dict[str, Any]:
        return {"content": {"ok": True}, "errors": None}


class FakeDriver:
    """Scripted vendor surface.

    ``script`` maps a report key to the list of exports the vendor answers
    with on successive attempts; each entry is the row list to write.
    """

    def __init__(
        self,
        script: dict[str, list[list[list[str]]]],
        *,
        options: tuple[str, ...] = ("1", "2", "3"),
        retained: bool = True,
        history_scope: tuple[str, ...] = ("All",),
        rows_rendered: int = 5,
    ) -> None:
        self.script = {key: list(value) for key, value in script.items()}
        self.options = options
        self.retained = retained
        self.history_scope = history_scope
        self.rows_rendered = rows_rendered
        self.events: list[str] = []
        self.current: matchups.MatchupDefinition | None = None
        self.selected: str | None = "2"
        self.url = "https://data.fantasypoints.com/nfl/tools/"

    def navigate(self, definition: matchups.MatchupDefinition) -> None:
        self.current = definition
        self.selected = "2"
        self.url = f"{matchups.BASE_URL}{definition.path}"
        self.events.append(f"navigate:{definition.key}")

    def week_control(self) -> dict[str, Any]:
        return {
            "present": True,
            "selected": self.selected,
            "history_scope": sorted(self.history_scope),
        }

    def visible_options(self) -> list[str]:
        return list(self.options)

    def select_week(self, week: int) -> None:
        if str(week) not in self.options:
            raise matchups.MatchupCaptureError(
                "vendor-week-unavailable", f"Schedule Week has no option {week}",
                options_visible=self.visible_options(),
            )
        self.selected = str(week)
        self.events.append(f"select:{week}")

    def apply(self, definition: matchups.MatchupDefinition) -> FakeResponse:
        self.events.append(f"apply:{definition.key}")
        if not self.retained:
            self.selected = "2"
        return FakeResponse(definition)

    def rendered_rows(self) -> int:
        return self.rows_rendered

    def export(self, destination: Path) -> str:
        assert self.current is not None
        pending = self.script[self.current.key]
        if not pending:
            raise AssertionError(f"no scripted export left for {self.current.key}")
        rows = pending.pop(0)
        _write_grouped(destination, self.current.key, rows)
        self.events.append(f"export:{self.current.key}")
        return f"{self.current.property}Export.csv"


def factory_for(driver: FakeDriver):
    @contextmanager
    def factory(profile_dir: Path, headless: bool, timeout_seconds: float) -> Iterator[FakeDriver]:
        yield driver

    return factory


def fake_archive(path: Path, digest: str, season: int, week: int) -> str:
    """Same hash-addressed object law as the real archive, no upload."""
    return expected_archive_uri(digest, path.name, week)


def archive_check_ok(uri: str) -> dict[str, Any]:
    return {"exists": True, "generation": "1"}


def capture(
    tmp_path: Path,
    monkeypatch,
    driver: FakeDriver,
    *,
    schedule: pd.DataFrame | None = None,
    week: int = 3,
    now: datetime | None = None,
    archive: bool = False,
    max_attempts: int = 3,
) -> Path:
    """Run the capture against the fake driver with a frozen clock."""
    schedule = schedule_frame() if schedule is None else schedule
    frozen = now or DEFAULT_NOW
    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)
    monkeypatch.setattr(matchups, "_archive", fake_archive)
    return matchups.run(
        season=2026, week=week, output_root=tmp_path / "automated",
        profile_dir=tmp_path / "profile", headless=True, timeout_seconds=1.0,
        archive=archive, now=frozen, clock=lambda: frozen,
        max_attempts=max_attempts, driver_factory=factory_for(driver),
    )


def snapshots_for(schedule: pd.DataFrame) -> pd.DataFrame:
    """Roster snapshots resolving every scripted player name to one gsis id."""
    rows = []
    for index, (team, _) in enumerate(directional_pairs(schedule)):
        for pos in ("QB", "WR"):
            rows.append({
                "season": 2026, "gsis_id": f"00-{pos}{index:03d}",
                "name": f"{pos} {team}", "pos": pos, "team": team,
            })
    return pd.DataFrame(rows)


__all__ = [
    "DEFAULT_NOW", "FakeDriver", "_write_grouped", "archive_check_ok", "capture",
    "directional_pairs", "export_rows_for", "fake_archive", "schedule_frame",
    "settings", "snapshots_for",
]
