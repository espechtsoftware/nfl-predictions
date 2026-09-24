"""Shared loaders and vectorised lineup features for the winner anatomy (2026 W1/W2 real fields)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path.cwd()          # run from the data directory (outside the repo); see README
MILLY = {1: "193028206", 2: "195648007"}
POS_CODE = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}


def players(week: int) -> pd.DataFrame:
    s = pd.read_parquet(HERE / "salaries.parquet")
    s = s[(s.week == week) & (s.position.isin(POS_CODE))].copy()
    s["display_name"] = s.display_name.str.strip()
    s = s.sort_values("salary", ascending=False).drop_duplicates("display_name")
    sch = pd.read_parquet(HERE / "sched.parquet")
    sch = sch[sch.week == week]
    rows = []
    for g in sch.itertuples():
        rows.append({"team": g.home_team, "game": g.game_id, "opp": g.away_team, "total": g.total_line,
                     "team_total": (g.total_line + g.spread_line) / 2})
        rows.append({"team": g.away_team, "game": g.game_id, "opp": g.home_team, "total": g.total_line,
                     "team_total": (g.total_line - g.spread_line) / 2})
    tm = pd.DataFrame(rows)
    alias = {"LA": "LA", "LAR": "LA", "JAX": "JAX", "WSH": "WAS"}
    s["team"] = s.team_abbr.map(lambda t: alias.get(t, t))
    s = s.merge(tm, on="team", how="left")
    s["late"] = (pd.to_datetime(s.game_start).dt.hour >= 20).astype(int)
    lp = pd.read_csv(HERE / "live_proj_2026.csv")
    lp = lp[lp.week == week].drop_duplicates("display_name")
    s = s.merge(lp[["display_name", "proj_points", "gsis_id"]], on="display_name", how="left")
    o = pd.read_parquet(HERE / "ownership.parquet")
    fp = o[o.week == week].groupby("display_name").fpts.max()
    s["fpts"] = s.display_name.map(fp)
    dk = pd.read_csv(HERE / "dk_points_2026.csv")
    dk = dk[dk.week == week].set_index("player_id").dk
    miss = s.fpts.isna() & s.gsis_id.notna()
    s.loc[miss, "fpts"] = s.loc[miss, "gsis_id"].map(dk)
    s["fpts"] = s.fpts.fillna(0.0)
    s["pos_code"] = s.position.map(POS_CODE)
    return s.reset_index(drop=True)


def ownership(contest_id: str) -> pd.Series:
    o = pd.read_parquet(HERE / "ownership.parquet")
    return o[o.contest_id == contest_id].set_index("display_name").own


def parse(entries: pd.DataFrame, pl: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(N, 9) player-row indices (-1 when unmatched) and the FLEX position index."""
    idx = {n: i for i, n in enumerate(pl.display_name)}
    out = np.full((len(entries), 9), -1, dtype=np.int32)
    flex = np.full(len(entries), -1, dtype=np.int32)
    for r, js in enumerate(entries.lineup_slots_json.to_numpy()):
        try:
            slots = json.loads(js)
        except (TypeError, ValueError):
            continue
        if len(slots) != 9:
            continue
        for k, sl in enumerate(slots):
            j = idx.get(str(sl["player"]).strip(), -1)
            out[r, k] = j
            if sl["slot"] == "FLEX":
                flex[r] = j
    return out, flex


def features(L: np.ndarray, pl: pd.DataFrame, own: pd.Series, flex: np.ndarray | None = None) -> pd.DataFrame:
    """Lineup features for an (N, 9) index matrix over the week's player table."""
    ok = (L >= 0).all(axis=1)
    L = np.where(L < 0, 0, L)
    sal = pl.salary.to_numpy(float)[L]
    pos = pl.pos_code.to_numpy()[L]
    team = pd.factorize(pl.team)[0][L]
    opp_code = pd.Series(pd.factorize(pl.team)[1]).reset_index().set_index(0)["index"]
    oppc = pl.opp.map(opp_code).fillna(-9).astype(int).to_numpy()[L]
    game = pd.factorize(pl.game)[0][L]
    ownv = pl.display_name.map(own).fillna(0.0).to_numpy(float)[L]
    proj = pl.proj_points.fillna(0.0).to_numpy(float)[L]
    pts = pl.fpts.to_numpy(float)[L]
    late = pl.late.to_numpy()[L]
    tt = pl.team_total.to_numpy(float)[L]
    gt = pl.total.to_numpy(float)[L]
    skill = pos != 4
    isqb = pos == 0
    qb_col = np.argmax(isqb, axis=1)
    rr = np.arange(len(L))
    qb_team = team[rr, qb_col]
    qb_opp = oppc[rr, qb_col]
    passc = (pos == 2) | (pos == 3)
    stack = ((team == qb_team[:, None]) & passc).sum(axis=1)
    rb_with_qb = ((team == qb_team[:, None]) & (pos == 1)).sum(axis=1)
    bringback = ((team == qb_opp[:, None]) & skill).sum(axis=1)
    dst_col = np.argmax(pos == 4, axis=1)
    dst_opp = oppc[rr, dst_col]
    dst_vs = ((team == dst_opp[:, None]) & skill).sum(axis=1)
    g = np.sort(game, axis=1)
    run = np.ones_like(g); best = np.ones(len(g), dtype=int)
    for k in range(1, 9):
        run[:, k] = np.where(g[:, k] == g[:, k - 1], run[:, k - 1] + 1, 1)
        best = np.maximum(best, run[:, k])
    n_games = 1 + (np.diff(g, axis=1) != 0).sum(axis=1)
    t = np.sort(team, axis=1)
    n_teams = 1 + (np.diff(t, axis=1) != 0).sum(axis=1)
    f = pd.DataFrame({
        "ok": ok,
        "salary": sal.sum(axis=1),
        "n_7k": ((sal >= 7000) & skill).sum(axis=1),
        "n_le4k": ((sal <= 4000) & skill).sum(axis=1),
        "stack": stack, "rb_with_qb": rb_with_qb, "bringback": bringback, "dst_vs_own": dst_vs,
        "max_game": best, "n_games": n_games, "n_teams": n_teams,
        "late": late.sum(axis=1),
        "own_sum": ownv.sum(axis=1), "own_logprod": np.log(np.maximum(ownv, 0.05) / 100).sum(axis=1),
        "own_max": ownv.max(axis=1), "n_own_lt5": ((ownv < 5) & skill).sum(axis=1),
        "n_own_ge20": (ownv >= 20).sum(axis=1),
        "proj": proj.sum(axis=1), "qb_team_total": tt[rr, qb_col], "qb_game_total": gt[rr, qb_col],
        "pts_check": pts.sum(axis=1),
        "qb_sal": sal[rr, qb_col], "dst_sal": sal[rr, dst_col],
        "rb_sal": np.where(pos == 1, sal, 0).sum(axis=1), "wr_sal": np.where(pos == 2, sal, 0).sum(axis=1),
        "te_sal": np.where(pos == 3, sal, 0).sum(axis=1),
        "n_te": (pos == 3).sum(axis=1), "n_rb": (pos == 1).sum(axis=1), "n_wr": (pos == 2).sum(axis=1),
    })
    if flex is not None:
        f["flex_pos"] = np.where(flex >= 0, pl.position.to_numpy()[np.maximum(flex, 0)], "?")
    return f
