"""One-time historical DK salary backfill from RotoGuru (2014+).

Semicolon-separated, ugly, complete, free. Run once, then rely on your own
append-only dk_salaries log going forward.
"""

from __future__ import annotations

import io
import logging
import time

import pandas as pd
import requests

from ..bq import load_dataframe

log = logging.getLogger(__name__)

URL = "http://rotoguru1.com/cgi-bin/fyday.pl?week={week}&year={year}&game=dk&scsv=1"
COLUMNS = {
    "Week": "week",
    "Year": "season",
    "GID": "rotoguru_gid",
    "Name": "display_name",
    "Pos": "position",
    "Team": "team_abbr",
    "h/a": "home_away",
    "Oppt": "opponent",
    "DK points": "dk_points",
    "DK salary": "salary",
}


def fetch_week(year: int, week: int, session: requests.Session) -> pd.DataFrame:
    r = session.get(URL.format(week=week, year=year), timeout=30)
    r.raise_for_status()
    text = r.text
    # The scsv payload is embedded in a <pre> block on an HTML page.
    if "<pre>" in text:
        text = text.split("<pre>")[1].split("</pre>")[0]
    df = pd.read_csv(io.StringIO(text.strip()), sep=";")
    df = df.rename(columns=COLUMNS)[list(COLUMNS.values())]
    # RotoGuru names are "Last, First"; normalize to "First Last".
    df["display_name"] = (
        df["display_name"]
        .str.split(", ", n=1)
        .map(lambda p: f"{p[1]} {p[0]}" if isinstance(p, list) and len(p) == 2 else p)
    )
    df["team_abbr"] = df["team_abbr"].str.upper()
    df["opponent"] = df["opponent"].str.upper()
    return df


def run(first_season: int = 2014, last_season: int | None = None) -> None:
    import datetime

    last = last_season or datetime.date.today().year - 1
    session = requests.Session()
    session.headers["User-Agent"] = "nfl-dfs-personal-research"
    frames = []
    for year in range(first_season, last + 1):
        for week in range(1, 19):
            try:
                df = fetch_week(year, week, session)
            except Exception as exc:  # noqa: BLE001 - a missing week is fine
                log.warning("Skipping %s week %s: %s", year, week, exc)
                continue
            if not df.empty:
                frames.append(df)
                log.info("%s week %s: %d rows", year, week, len(df))
            time.sleep(3)  # rate-limit; RotoGuru is a one-man shop

    if frames:
        load_dataframe(pd.concat(frames, ignore_index=True), "dk_salaries_historical")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
