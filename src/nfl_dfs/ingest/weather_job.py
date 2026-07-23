"""Game-time weather from Open-Meteo (free, no key) into nfl_raw.weather.

Only outdoor stadiums matter; roof type comes from nflverse stadium metadata
already joined into nfl_raw.schedules (roof, surface columns). Wind above
~15 mph is the main actionable signal.

Schedule: 3x daily Fri-Sun.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import requests

from ..bq import load_dataframe, query_df
from ..config import current_season, settings

log = logging.getLogger(__name__)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# Lat/long for current outdoor + retractable NFL stadiums, keyed by home team.
STADIUM_COORDS: dict[str, tuple[float, float]] = {
    "BAL": (39.2780, -76.6227), "BUF": (42.7738, -78.7870), "CAR": (35.2258, -80.8528),
    "CHI": (41.8623, -87.6167), "CIN": (39.0955, -84.5161), "CLE": (41.5061, -81.6995),
    "DEN": (39.7439, -105.0201), "GB": (44.5013, -88.0622), "JAX": (30.3239, -81.6373),
    "KC": (39.0489, -94.4839), "MIA": (25.9580, -80.2389), "NE": (42.0909, -71.2643),
    "NYG": (40.8135, -74.0745), "NYJ": (40.8135, -74.0745), "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -80.0158), "SEA": (47.5952, -122.3316), "TB": (27.9759, -82.5033),
    "TEN": (36.1665, -86.7713), "WAS": (38.9076, -76.8645),
    # Retractable / indoor teams included so join misses are explicit nulls
    "ARI": (33.5276, -112.2626), "ATL": (33.7554, -84.4009), "DAL": (32.7473, -97.0945),
    "DET": (42.3400, -83.0456), "HOU": (29.6847, -95.4107), "IND": (39.7601, -86.1639),
    "LA": (33.9535, -118.3392), "LAC": (33.9535, -118.3392), "LV": (36.0909, -115.1833),
    "MIN": (44.9736, -93.2575), "NO": (29.9511, -90.0812), "SF": (37.4032, -121.9698),
}


def upcoming_games() -> pd.DataFrame:
    season = current_season()
    return query_df(
        f"""
        SELECT game_id, home_team, gameday, gametime, roof
        FROM `{settings.raw}.schedules`
        WHERE season = {season}
          AND DATE(gameday) BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 4 DAY)
        """
    )


def fetch_forecast(lat: float, lon: float, gameday: str) -> dict:
    r = requests.get(
        OPEN_METEO,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m,precipitation_probability",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "start_date": gameday,
            "end_date": gameday,
            "timezone": "America/New_York",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def run() -> None:
    games = upcoming_games()
    rows = []
    for g in games.itertuples():
        coords = STADIUM_COORDS.get(g.home_team)
        if coords is None:
            continue
        gameday = str(g.gameday)[:10]
        try:
            fx = fetch_forecast(*coords, gameday)
        except requests.RequestException as exc:
            log.warning("Forecast failed for %s: %s", g.game_id, exc)
            continue
        hourly = fx.get("hourly", {})
        kickoff_hour = int(str(g.gametime or "13:00")[:2])
        idx = min(kickoff_hour, len(hourly.get("time", [])) - 1)
        if idx < 0:
            continue
        rows.append(
            {
                "pulled_at": datetime.now(timezone.utc),
                "game_id": g.game_id,
                "temp_f": hourly["temperature_2m"][idx],
                "wind_mph": hourly["wind_speed_10m"][idx],
                "precip_prob": hourly["precipitation_probability"][idx],
                "is_dome": g.roof in ("dome", "closed"),
            }
        )
    if rows:
        load_dataframe(pd.DataFrame(rows), "weather", write_disposition="WRITE_APPEND",
                       partition_field="pulled_at")
        log.info("Wrote weather for %d games", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
