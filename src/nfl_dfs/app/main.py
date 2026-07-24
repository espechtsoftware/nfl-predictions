"""FastAPI service (guide Phase 7): slate view, projections table, lineup
builder with stacking options, exposure summary, DK-format CSV export.

Run locally:  uvicorn nfl_dfs.app.main:app --reload
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..optimizer.export import exposure_summary, to_dk_csv
from ..optimizer.lineup import StackRules, optimize_many
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
