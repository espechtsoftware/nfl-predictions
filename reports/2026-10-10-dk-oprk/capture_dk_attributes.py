"""Capture DraftKings' per-player draftable attributes for an NFL draft group into BigQuery (the operator 10-10: "are we considering
draft kings rankings at all? ... Let's be sure to be collecting it if it is available"). The draftables payload carries, per player,
draftStatAttributes id 90 (DK's points per game) and id -2 (DK's OPPONENT RANK vs the player's position: value "7th", sortValue 7,
1 = the toughest defense, 32 = the easiest, plus a "quality" label). Production's dk_client.draftables_frame keeps only id 90, and
no raw payload is archived, so the rank was never stored. This SEPARATE, read-only capture (the same public endpoint the hourly
ingest reads, one request per group) appends one row per (player, attribute) to nfl_raw.dk_draftable_attributes, and also the
player's newsStatus / draftAlerts count. It changes nothing on the money path (dk_salaries and its loop are untouched).

    python reports/2026-10-10-dk-oprk/capture_dk_attributes.py --group 154468 [--group ...]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from nfl_dfs.ingest import dk_client as C  # noqa: E402

TABLE = "nfl-predictions-503414.nfl_raw.dk_draftable_attributes"


def rows_for(gid: int, payload: dict, pulled_at: datetime) -> list[dict]:
    out, seen = [], set()
    for d in payload.get("draftables", []):
        pid = d.get("playerId")
        if pid in seen:                                   # DK repeats a player across roster slots; the attributes repeat too
            continue
        seen.add(pid)
        base = {"pulled_at": pulled_at, "draft_group_id": gid, "dk_player_id": pid, "display_name": d.get("displayName"),
                "team_abbr": d.get("teamAbbreviation"), "position": d.get("position"), "salary": d.get("salary"),
                "status": d.get("status"), "news_status": d.get("newsStatus"), "draft_alerts": len(d.get("draftAlerts") or [])}
        for a in d.get("draftStatAttributes", []) or []:
            sv = a.get("sortValue")
            try:
                svf = float(sv) if sv not in (None, "") else None
            except (TypeError, ValueError):
                svf = None
            out.append({**base, "attr_id": int(a.get("id")), "value": None if a.get("value") is None else str(a.get("value")),
                        "sort_value": svf, "quality": a.get("quality")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", type=int, action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pulled_at = datetime.now(timezone.utc)
    rows = []
    for gid in a.group:
        rows += rows_for(gid, C.fetch_draftables(gid), pulled_at)
    df = pd.DataFrame(rows)
    if df.empty:
        print("no attributes found"); return 3
    n_rank = int((df.attr_id == -2).sum()); n_players = df.dk_player_id.nunique()
    print(f"{pulled_at:%Y-%m-%dT%H:%M:%SZ}: {len(df)} rows, {n_players} players, opponent ranks {n_rank}, attr ids {sorted(df.attr_id.unique().tolist())}")
    if a.dry_run:
        print(df.head(4).to_string()); return 0
    from google.cloud import bigquery
    bq = bigquery.Client(project="nfl-predictions-503414")
    job = bq.load_table_from_dataframe(df, TABLE, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"))
    job.result()
    print(f"appended {len(df)} rows to {TABLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
