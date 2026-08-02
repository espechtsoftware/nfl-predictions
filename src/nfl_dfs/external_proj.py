"""External projections import + consensus diff (2026-08-02).

Purpose: a disagreement FLAG, not an input. Upload a CSV from any outside
source (ETR, Stokastic, free ownership sites) and the market page shows
where they and our model diverge most on projection and ownership. Big
divergence on a player we're concentrated in = "a human may know
something the data doesn't yet" (scheme-change-year insurance) — route
it through the watchlist, never blend it into the model.

Column names are sniffed loosely: name/player, proj/fpts/points,
own/ownership (either 0-1 or 0-100), ceiling/ceil, position/pos.
Re-uploading the same (source, season, week) replaces it.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timezone

import pandas as pd

from .bq import load_dataframe, query_df
from .config import settings

log = logging.getLogger(__name__)

TABLE = "external_projections"


def _table() -> str:
    return f"{settings.features}.{TABLE}"


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z ]", "", str(name).upper()).strip()


_ALIASES = {
    "name": ("name", "player", "player_name", "display_name"),
    "position": ("position", "pos"),
    "proj": ("proj", "projection", "fpts", "points", "proj_points", "fpts_proj"),
    "own_pct": ("own", "ownership", "own_pct", "proj_own", "ownership_pct",
                "projected_ownership", "roster%", "roster_pct"),
    "ceiling": ("ceiling", "ceil", "max", "p90"),
}


def parse_csv(text: str) -> pd.DataFrame:
    """Loose-schema parse -> columns [name, position, proj, own_pct,
    ceiling] (missing ones NaN). Ownership normalized to 0-100."""
    df = pd.read_csv(io.StringIO(text))
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    out = pd.DataFrame()
    for want, names in _ALIASES.items():
        src = next((cols[n] for n in names if n in cols), None)
        if src is not None:
            out[want] = df[src]
    if "name" not in out.columns or "proj" not in out.columns:
        raise ValueError(
            f"CSV needs at least a name and a projection column; saw "
            f"{list(df.columns)}")
    out["proj"] = pd.to_numeric(
        out.proj.astype(str).str.replace("%", ""), errors="coerce")
    if "own_pct" in out.columns:
        own = pd.to_numeric(
            out.own_pct.astype(str).str.replace("%", ""), errors="coerce")
        # 0-1 scale -> percent
        if own.max() is not None and own.max() <= 1.5:
            own = own * 100.0
        out["own_pct"] = own
    for c in ("position", "own_pct", "ceiling"):
        if c not in out.columns:
            out[c] = pd.NA
    out["ceiling"] = pd.to_numeric(out.ceiling, errors="coerce")
    out = out.dropna(subset=["proj"])
    out["name"] = out.name.astype(str)
    return out[["name", "position", "proj", "own_pct", "ceiling"]]


def import_csv(text: str, source: str, season: int, week: int) -> int:
    rows = parse_csv(text)
    rows = rows.assign(source=source, season=int(season), week=int(week),
                       uploaded_at=datetime.now(timezone.utc))
    from google.cloud import bigquery

    from .bq import client

    try:
        client().query(
            f"DELETE FROM `{_table()}` WHERE source = @s AND season = @y "
            f"AND week = @w",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("s", "STRING", source),
                bigquery.ScalarQueryParameter("y", "INT64", int(season)),
                bigquery.ScalarQueryParameter("w", "INT64", int(week))]),
        ).result()
    except Exception:
        log.info("external_projections absent; first import creates it")
    load_dataframe(rows, _table(), write_disposition="WRITE_APPEND")
    return len(rows)


def diff(projections: pd.DataFrame, season: int, week: int,
         limit: int = 40) -> pd.DataFrame:
    """Largest |our proj - theirs| among matched names, both directions,
    with their ownership alongside for the leverage read."""
    ext = query_df(
        f"""SELECT source, name, proj ext_proj, own_pct ext_own,
                   ceiling ext_ceiling
            FROM `{_table()}` WHERE season = {int(season)}
              AND week = {int(week)}""")
    if ext.empty or projections.empty:
        return pd.DataFrame()
    ext["nm"] = ext.name.map(_norm)
    ours = projections.copy()
    ours["nm"] = ours.display_name.map(_norm)
    j = ours.merge(ext, on="nm", how="inner")
    j["diff"] = (j.proj_points - j.ext_proj).round(2)
    j = j.reindex(j["diff"].abs().sort_values(ascending=False).index)
    cols = ["display_name", "position", "team", "salary", "proj_points",
            "ext_proj", "diff", "ext_own", "ext_ceiling", "source"]
    return j[[c for c in cols if c in j.columns]].head(int(limit)).round(2)
