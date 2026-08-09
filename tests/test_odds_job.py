"""Offline coverage for the Odds-API-backed game-lines snapshot.

The original DK-sportsbook scrape never landed a row (403, see the README
deficiency log); this tests its 2026-07-31 replacement against a payload
modeled on The Odds API's live /odds response shape.
"""

from dataclasses import replace

import pandas as pd
import pytest

from nfl_dfs.config import settings
from nfl_dfs.ingest import odds_job


def _payload():
    return [
        {
            "id": "abc123",
            "commence_time": "2026-09-10T00:20:00Z",
            "home_team": "Philadelphia Eagles",
            "away_team": "Dallas Cowboys",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Philadelphia Eagles", "price": -170},
                                {"name": "Dallas Cowboys", "price": 142},
                            ],
                        },
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Philadelphia Eagles", "price": -110, "point": -3.5},
                                {"name": "Dallas Cowboys", "price": -110, "point": 3.5},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": -108, "point": 47.5},
                                {"name": "Under", "price": -112, "point": 47.5},
                            ],
                        },
                    ],
                },
                {
                    # A non-DK book in the payload must be ignored even if
                    # the API's bookmakers filter ever loosens.
                    "key": "fanduel",
                    "markets": [
                        {"key": "h2h", "outcomes": [{"name": "Dallas Cowboys", "price": 150}]},
                    ],
                },
            ],
        },
    ]


def test_rows_map_markets_and_format_odds():
    rows = odds_job._rows_from_payload(_payload())
    df = pd.DataFrame(rows)
    assert len(df) == 6  # 2 h2h + 2 spreads + 2 totals, fanduel ignored
    assert set(df.market_type) == {"Moneyline", "Spread", "Total"}
    assert set(df.event_name) == {"Dallas Cowboys @ Philadelphia Eagles"}

    ml = df[df.market_type == "Moneyline"].set_index("selection")
    assert ml.loc["Philadelphia Eagles", "odds_american"] == "-170"
    assert ml.loc["Dallas Cowboys", "odds_american"] == "+142"
    assert ml.line.isna().all()  # moneyline has no point

    total = df[df.market_type == "Total"]
    assert set(total.selection) == {"Over", "Under"}
    assert (total.line == 47.5).all()


def test_rows_empty_payload():
    assert odds_job._rows_from_payload([]) == []


def test_run_loads_snapshot(monkeypatch):
    monkeypatch.setattr(
        odds_job, "_fetch", lambda session=None, audit_rows=None: _payload()
    )
    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.odds_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df, kw)),
    )

    odds_job.run()

    assert len(loaded) == 1
    table, df, kw = loaded[0]
    assert table == "odds_snapshots"
    assert kw["write_disposition"] == "WRITE_APPEND"
    assert len(df) == 6


def test_run_noop_on_empty(monkeypatch):
    monkeypatch.setattr(
        odds_job, "_fetch", lambda session=None, audit_rows=None: []
    )

    def boom(*a, **k):
        raise AssertionError("must not load an empty frame")

    monkeypatch.setattr("nfl_dfs.ingest.odds_job.load_dataframe", boom)
    odds_job.run()  # must not raise


def test_fetch_requires_key(monkeypatch):
    monkeypatch.setattr(odds_job, "settings", replace(settings, odds_api_key=""))
    with pytest.raises(RuntimeError, match="ODDS_API_KEY"):
        odds_job._fetch()
