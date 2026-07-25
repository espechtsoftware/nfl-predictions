"""FastAPI service (guide Phase 7): slate view, projections table, lineup
builder with stacking options, exposure summary, DK-format CSV export.

Run locally:  uvicorn nfl_dfs.app.main:app --reload
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..optimizer.export import (
    exposure_summary,
    showdown_exposure_summary,
    to_dk_csv,
    to_dk_showdown_csv,
)
from ..optimizer.lineup import StackRules, core_and_variations, optimize_many
from ..optimizer.showdown import optimize_many_showdown
from .store import BigQueryStore, ProjectionStore

app = FastAPI(title="NFL DFS", version="0.1.0")


@lru_cache
def default_store() -> ProjectionStore:
    return BigQueryStore()


def get_store() -> ProjectionStore:
    return app.dependency_overrides.get(default_store, default_store)()


class LineupRequest(BaseModel):
    season: int
    week: int
    n_lineups: int = Field(1, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    qb_stack_min: int = Field(1, ge=0, le=3)
    bring_back_min: int = Field(0, ge=0, le=2)
    forbid_rb_vs_dst: bool = True
    max_overlap: int = Field(7, ge=1, le=8)


_PAGE_CSS = """
body{font-family:system-ui,sans-serif;margin:2rem auto;max-width:1080px;
     padding:0 1rem;color:#1a1a2e;background:#fafafa}
h1{font-size:1.5rem} h2{font-size:1.1rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;font-size:.9rem;background:#fff}
th,td{padding:.35rem .6rem;text-align:right;border-bottom:1px solid #e5e5ef}
th:first-child,td:first-child{text-align:left}
th{background:#1a1a2e;color:#fff;position:sticky;top:0}
tr:nth-child(-n+5) td:first-child{font-weight:600}
.up{color:#0a7a3d}.down{color:#b3261e}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
small{color:#666}
"""


def _defense_page(df, season: int) -> str:
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    sections = []
    for pos in ("QB", "RB", "WR", "TE"):
        grp = latest[latest.position == pos].sort_values("fp_allowed_season")
        if grp.empty:
            continue
        rows = []
        for r in grp.itertuples():
            arrow = ("<span class='down'>&#9660; fading</span>" if r.trend > 1.5
                     else "<span class='up'>&#9650; improving</span>" if r.trend < -1.5
                     else "&mdash;")
            rows.append(
                f"<tr><td>{r.team}</td><td>{r.fp_allowed_season:.1f}</td>"
                f"<td>{r.fp_allowed_l6:.1f}</td><td>{r.fp_allowed_l3:.1f}</td>"
                f"<td>{r.trend:+.1f}</td><td>{arrow}</td></tr>"
            )
        sections.append(
            f"<div><h2>vs {pos}</h2><table>"
            f"<tr><th>Team</th><th>Season</th><th>L6</th><th>L3</th>"
            f"<th>Trend</th><th></th></tr>{''.join(rows)}</table></div>"
        )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>NFL DFS — Defense vs Position</title>"
        f"<style>{_PAGE_CSS}</style></head><body>"
        f"<h1>DK points allowed per position &middot; {season}</h1>"
        f"<small>Season/L6/L3 = avg DK points allowed per game to the position "
        f"(fewest first = toughest defense). Trend = last 3 vs season norm: "
        f"positive means the defense is giving up more than usual lately. "
        f"API: <a href='/docs'>/docs</a>, "
        f"<a href='/defense/trends?season={season}'>/defense/trends</a></small>"
        f"<div class='grid'>{''.join(sections)}</div></body></html>"
    )


@app.get("/", response_class=HTMLResponse)
def defense_dashboard(
    season: int | None = None,
    store: ProjectionStore = Depends(get_store),
) -> str:
    df = store.defense_points_against(season)
    if df.empty:
        return ("<h1>No defense data yet</h1>"
                "<p>Run <code>nfl-dfs build-features</code> first.</p>")
    season = int(season or df.season.max())
    return _defense_page(df[df.season == season], season)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/defense/points-against")
def defense_points_against(
    season: int | None = None,
    position: str | None = None,
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    """Fantasy-style points-against: latest-week snapshot per team/position
    with season average, last-3/6, and trend (positive = fading defense)."""
    df = store.defense_points_against(season)
    if df.empty:
        raise HTTPException(404, "No defense data; run build-features")
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    if position:
        latest = latest[latest.position == position.upper()]
    return (
        latest.sort_values(["position", "fp_allowed_season"])
        .round(2).to_dict("records")
    )


@app.get("/defense/trends")
def defense_trends(
    season: int | None = None,
    top: int = Query(5, ge=1, le=32),
    store: ProjectionStore = Depends(get_store),
) -> dict:
    """Per position: defenses improving (clamping down vs. their season
    norm) and fading (allowing more lately)."""
    df = store.defense_points_against(season)
    if df.empty:
        raise HTTPException(404, "No defense data; run build-features")
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    out: dict = {}
    for pos, grp in latest.groupby("position"):
        g = grp.sort_values("trend").round(2)
        cols = ["team", "trend", "fp_allowed_l3", "fp_allowed_season", "week"]
        out[pos] = {
            "improving": g.head(top)[cols].to_dict("records"),
            "fading": g.tail(top)[cols].iloc[::-1].to_dict("records"),
        }
    return out


@app.get("/slates")
def slates(store: ProjectionStore = Depends(get_store)) -> list[dict]:
    return store.slates().to_dict("records")


@app.get("/projections")
def projections(
    season: int = Query(...),
    week: int = Query(...),
    position: str | None = None,
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    df = store.projections(season, week)
    if df.empty:
        raise HTTPException(404, f"No projections for {season} week {week}")
    if position:
        df = df[df.position == position.upper()]
    return df.sort_values("proj_points", ascending=False).to_dict("records")


def _player_pool(df: pd.DataFrame, objective: str) -> list[dict]:
    pool = []
    for r in df.itertuples():
        pool.append(
            {
                "id": int(r.dk_player_id),
                "name": r.display_name,
                "pos": r.position,
                "team": r.team,
                "opp": getattr(r, "opponent", None),
                "game_id": f"{r.team}@{getattr(r, 'opponent', '?')}",
                "salary": int(r.salary),
                "proj": float(getattr(r, objective)),
            }
        )
    return pool


@app.post("/lineups")
def build_lineups(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    df = store.projections(req.season, req.week)
    if df.empty:
        raise HTTPException(404, f"No projections for {req.season} week {req.week}")
    pool = _player_pool(df, req.objective)
    stack = StackRules(
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
    )
    lineups = optimize_many(
        pool, n_lineups=req.n_lineups, stack=stack,
        locks=set(req.locks), bans=set(req.bans), max_overlap=req.max_overlap,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    return {
        "lineups": [
            {
                "players": lu.slot_order(),
                "salary": lu.salary,
                "proj": round(lu.proj, 2),
            }
            for lu in lineups
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv(lineups),
    }


class CoreLineupRequest(LineupRequest):
    """Core-and-variations mode: a consensus core (picked on the stable
    median objective) locked into every entry, with the remaining spots
    varied on `objective` (defaults to ceiling — variation is for upside).
    core_size omitted = the system decides how many players it feels
    strongly about (conviction + positional value, with a budget guard so
    the core can't hoard the salary cap)."""

    objective: str = Field("proj_p90", pattern="^proj_(points|p50|p90)$")
    core_size: int | None = Field(None, ge=2, le=8)


@app.post("/lineups/core")
def build_core_lineups(
    req: CoreLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    df = store.projections(req.season, req.week)
    if df.empty:
        raise HTTPException(404, f"No projections for {req.season} week {req.week}")
    stable_pool = _player_pool(df, "proj_p50")
    upside_pool = _player_pool(df, req.objective)
    stack = StackRules(
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
    )
    core, lineups = core_and_variations(
        stable_pool, upside_pool, n_lineups=req.n_lineups,
        core_size=req.core_size, stack=stack,
        locks=set(req.locks), bans=set(req.bans),
        max_overlap=req.max_overlap if req.max_overlap != 7 else None,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    by_id = {p["id"]: p for p in upside_pool}
    return {
        "core": [
            {"id": c["id"], "conviction": c["conviction"],
             "name": by_id[c["id"]]["name"], "pos": by_id[c["id"]]["pos"],
             "team": by_id[c["id"]]["team"], "salary": by_id[c["id"]]["salary"]}
            for c in core
        ],
        "lineups": [
            {"players": lu.slot_order(), "salary": lu.salary,
             "proj": round(lu.proj, 2)}
            for lu in lineups
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv(lineups),
    }


# --- Showdown Captain Mode (single-game slates, guide §9.5) ---------------
#
# DK runs a showdown slate for every game, but the interesting ones here are
# the standalone prime-time games — Thursday and Monday night — so that's
# the default filter. Projections are reused from the classic pipeline
# (joined by DK player id); showdown-only positions (K, DST) fall back to
# DK's own points-per-game figure.

SHOWDOWN_DEFAULT_DAYS = "thu,mon"


def _showdown_games(store: ProjectionStore, days: str) -> pd.DataFrame:
    """One row per upcoming showdown draft group, filtered to the requested
    kickoff days (US/Eastern)."""
    sd = store.showdown_salaries()
    if sd.empty:
        return sd
    start = pd.to_datetime(sd.game_start, utc=True, format="ISO8601")
    sd = sd.assign(
        _day=start.dt.tz_convert("America/New_York").dt.day_name(),
        _start=start,
    )
    wanted = {d.strip().lower()[:3] for d in days.split(",") if d.strip()}
    if wanted:
        sd = sd[sd["_day"].str.lower().str[:3].isin(wanted)]
    return sd


def _showdown_pool(game: pd.DataFrame, proj: pd.DataFrame, objective: str) -> list[dict]:
    """Player pool for one showdown game: classic projections joined by DK
    player id, dk_ppg fallback for unprojected players (K, DST)."""
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    opp = {t: next((o for o in teams if o != t), None) for t in teams}
    by_id = {}
    if not proj.empty:
        by_id = proj.set_index("dk_player_id")[
            ["proj_points", "proj_p50", "proj_p90"]
        ].to_dict("index")
    pool = []
    for r in game.itertuples():
        row = by_id.get(r.dk_player_id)
        if row is not None and pd.notna(row[objective]):
            value, source = float(row[objective]), "model"
        elif pd.notna(r.dk_ppg):
            value, source = float(r.dk_ppg), "dk_ppg"
        else:
            continue  # no projection at all — can't rank the player
        pool.append(
            {
                "id": int(r.dk_player_id),
                "name": r.display_name,
                "pos": r.position,
                "team": r.team_abbr,
                "opp": opp.get(r.team_abbr),
                "game_id": int(r.draft_group_id),
                "salary": int(r.salary),
                "proj": value,
                "proj_source": source,
            }
        )
    return pool


class ShowdownLineupRequest(BaseModel):
    season: int
    week: int
    draft_group_id: int | None = None  # default: next upcoming Thu/Mon game
    days: str = SHOWDOWN_DEFAULT_DAYS
    n_lineups: int = Field(1, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    captain: int | None = None
    max_overlap: int = Field(5, ge=1, le=5)


@app.get("/showdown/slates")
def showdown_slates(
    days: str = Query(SHOWDOWN_DEFAULT_DAYS),
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    """Upcoming Captain Mode games (default: Thursday/Monday night)."""
    sd = _showdown_games(store, days)
    if sd.empty:
        raise HTTPException(404, "No upcoming showdown slates; run ingest-dk")
    out = []
    for gid, grp in sd.groupby("draft_group_id", sort=False):
        teams = sorted(t for t in grp.team_abbr.dropna().unique())
        out.append(
            {
                "draft_group_id": int(gid),
                "game": " vs ".join(teams),
                "day": grp["_day"].iloc[0],
                "game_start": str(grp["_start"].iloc[0]),
                "players": len(grp),
            }
        )
    return sorted(out, key=lambda g: g["game_start"])


@app.post("/showdown/lineups")
def build_showdown_lineups(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    sd = _showdown_games(store, "" if req.draft_group_id else req.days)
    if sd.empty:
        raise HTTPException(404, "No upcoming showdown slates; run ingest-dk")
    if req.draft_group_id is not None:
        game = sd[sd.draft_group_id == req.draft_group_id]
        if game.empty:
            raise HTTPException(404, f"No showdown slate {req.draft_group_id}")
    else:
        next_gid = sd.sort_values("_start").draft_group_id.iloc[0]
        game = sd[sd.draft_group_id == next_gid]

    proj = store.projections(req.season, req.week)
    pool = _showdown_pool(game, proj, req.objective)
    if len(pool) < 6 or len({p["team"] for p in pool}) < 2:
        raise HTTPException(422, "Showdown pool too thin to build a lineup")
    pool_ids = {p["id"] for p in pool}
    wanted = set(req.locks) | ({req.captain} if req.captain is not None else set())
    if wanted - pool_ids:
        raise HTTPException(
            422, f"Players not in this game's projectable pool: {sorted(wanted - pool_ids)}"
        )

    lineups = optimize_many_showdown(
        pool, n_lineups=req.n_lineups, locks=set(req.locks),
        bans=set(req.bans) & pool_ids,
        captain_lock=req.captain, max_overlap=req.max_overlap,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    return {
        "game": {
            "draft_group_id": int(game.draft_group_id.iloc[0]),
            "game": " vs ".join(teams),
            "day": game["_day"].iloc[0],
            "game_start": str(game["_start"].iloc[0]),
        },
        "lineups": [
            {
                "captain": lu.captain,
                "players": lu.slot_order(),
                "salary": lu.salary,
                "proj": round(lu.proj, 2),
            }
            for lu in lineups
        ],
        "exposure": showdown_exposure_summary(lineups),
        "dk_csv": to_dk_showdown_csv(lineups),
    }


@app.post("/showdown/lineups.csv")
def build_showdown_lineups_csv(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    payload = build_showdown_lineups(req, store)
    return Response(
        content=payload["dk_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_showdown_lineups.csv"},
    )


@app.post("/lineups.csv")
def build_lineups_csv(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    payload = build_lineups(req, store)
    return Response(
        content=payload["dk_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_lineups.csv"},
    )
