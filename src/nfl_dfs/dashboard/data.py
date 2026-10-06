"""Every dashboard read, as pure functions over a ``query(sql) -> DataFrame``
callable.

SQL lives in ``sql/dashboard/<name>.sql``; :func:`render` substitutes the
dataset placeholders and prepends a ``-- dashboard:<name>`` marker line, which
the offline tests use to route a fake ``query``. Fetchers only shape SQL; the
derivations (newest batch, implied totals, weekly ranks, accuracy,
ownership calibration, leverage) take DataFrames and are unit-tested.

Licensed vendor data (Fantasy Points) is only ever compared here -- joined
next to our numbers, differenced, ranked, scored -- for pages behind IAP.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from ..config import settings
from .teams import canon_team, norm_name, parse_event_name

Query = Callable[[str], pd.DataFrame]

SKILL = ("QB", "RB", "WR", "TE")
DST_SPELLINGS = {"DST", "D", "DEF", "D/ST"}


# --------------------------------------------------------------------- SQL --

def _sql_dir() -> Path:
    candidates = (
        Path(__file__).resolve().parents[3] / "sql" / "dashboard",  # checkout
        Path.cwd() / "sql" / "dashboard",                           # container /app
    )
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


SQL_DIR = _sql_dir()


def dashboard_dataset() -> str:
    return f"{settings.project}.{os.environ.get('BQ_DASHBOARD_DATASET', 'nfl_dashboard')}"


def render(name: str, **subs: object) -> str:
    """Render ``sql/dashboard/<name>.sql``. ``${milly_contests}`` inlines the
    contest resolver as a subquery; ``${week_filter}`` defaults to empty."""
    text = (SQL_DIR / f"{name}.sql").read_text()
    if "${milly_contests}" in text:
        text = text.replace("${milly_contests}", render("milly_contests", _marker=False))
    # ${inc:NAME} inlines sql/dashboard/NAME.sql (shared CTE snippets).
    for inc in sorted(set(re.findall(r"\$\{inc:(\w+)\}", text))):
        inner = {k: v for k, v in subs.items() if k != "_marker"}
        text = text.replace("${inc:" + inc + "}", render(inc, _marker=False, **inner))
    values = {
        "raw": settings.raw,
        "features": settings.features,
        "predictions": settings.predictions,
        "dashboard": dashboard_dataset(),
        "week_filter": "",
        "week_filter_m": "",
        **{k: str(v) for k, v in subs.items() if not k.startswith("_") and k != "_marker"},
    }
    for key, value in values.items():
        text = text.replace("${" + key + "}", value)
    unresolved = re.findall(r"\$\{(\w+)\}", text)
    if unresolved:
        raise ValueError(f"unresolved placeholders in {name}.sql: {unresolved}")
    if subs.get("_marker", True) is False:
        return text
    return f"-- dashboard:{name}\n{text}"


def sql_name(sql: str) -> str:
    """The template name a rendered query came from (fake-query routing)."""
    first = sql.split("\n", 1)[0]
    return first.removeprefix("-- dashboard:").strip() if first.startswith("-- dashboard:") else ""


def _week_filter(week: int | None, alias: str = "x") -> str:
    return "" if week is None else f"AND {alias}.week = {int(week)}"


def is_missing_table(exc: BaseException) -> bool:
    msg = str(exc)
    return "Not found" in msg or "not found" in msg


# ---------------------------------------------------------------- generic --

def newest_rows(df: pd.DataFrame, ts_col: str, by: Iterable[str] | None = None) -> pd.DataFrame:
    """Rows carrying the newest ``ts_col`` (per ``by`` group when given):
    a "batch" is everything written at one timestamp."""
    if df.empty or ts_col not in df:
        return df.copy()
    ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    by = list(by or [])
    if by:
        newest = ts.groupby([df[c] for c in by]).transform("max")
    else:
        newest = pd.Series(ts.max(), index=df.index)
    return df[ts.eq(newest)].reset_index(drop=True)


def player_key(name: object, position: object, team: object) -> str:
    """Join key across our projections, Fantasy Points and DraftKings rows:
    a DST is its team; anyone else is normalised name + canonical team."""
    pos = str(position or "").upper()
    t = canon_team(team) or ""
    if pos in DST_SPELLINGS:
        return f"DST:{t or canon_team(name) or norm_name(name)}"
    return f"{norm_name(name)}:{t}"


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


# ------------------------------------------------------------ the calendar --

def lock_utc(schedule: pd.DataFrame, week: int) -> datetime | None:
    """Main-slate lock: 13:00 Eastern on the week's Sunday."""
    wk = schedule[(schedule.week == week) & (schedule.weekday == "Sunday")]
    if wk.empty:
        return None
    day = min(str(d) for d in wk.gameday)
    return pd.Timestamp(f"{day} 13:00", tz="America/New_York").tz_convert("UTC").to_pydatetime()


def current_week(schedule: pd.DataFrame, today: date | None = None) -> int | None:
    """The first week with a game today or later (Eastern dates); after the
    season, the last week."""
    if schedule.empty:
        return None
    today = today or pd.Timestamp.now(tz="America/New_York").date()
    last = schedule.groupby("week").gameday.max()
    upcoming = last[last.astype(str) >= today.isoformat()]
    return int(upcoming.index.min()) if len(upcoming) else int(last.index.max())


def kickoff_utc(gameday: object, gametime: object) -> pd.Timestamp:
    t = str(gametime or "13:00")
    return pd.Timestamp(f"{gameday} {t}", tz="America/New_York").tz_convert("UTC")


# ------------------------------------------------------------ implied totals --

def odds_game_lines(odds: pd.DataFrame, open_days: int = 7) -> pd.DataFrame:
    """Per odds event: the newest pre-kickoff total and home spread, and the
    first pull inside the week's window (kickoff - ``open_days``).

    Spread lines are the betting convention (negative = favored), keyed by
    the team named in ``selection``; the home line is taken directly, or as
    minus the away line when only the away row exists in that pull."""
    cols = ["event_id", "away", "home", "start", "total", "home_spread",
            "total_open", "home_spread_open", "last_pull", "first_pull", "n_pulls"]
    if odds.empty:
        return pd.DataFrame(columns=cols)
    o = odds.copy()
    o["start"] = pd.to_datetime(o.start_time, utc=True, errors="coerce")
    o["pulled_at"] = pd.to_datetime(o.pulled_at, utc=True, errors="coerce")
    o = o[o.pulled_at < o.start]
    o = o[o.pulled_at >= o.start - pd.Timedelta(days=open_days)]
    if o.empty:
        return pd.DataFrame(columns=cols)
    teams = o.event_name.map(parse_event_name)
    o["away"] = teams.map(lambda t: t[0])
    o["home"] = teams.map(lambda t: t[1])
    o["line"] = _num(o.line)
    o["sel_team"] = o.selection.map(canon_team)

    tot = (o[o.market_type == "Total"].groupby(["event_id", "pulled_at"]).line.mean()
           .rename("total"))
    sp = o[o.market_type == "Spread"]
    home_sp = sp[sp.sel_team == sp.home].groupby(["event_id", "pulled_at"]).line.mean()
    away_sp = sp[sp.sel_team == sp.away].groupby(["event_id", "pulled_at"]).line.mean()
    spread = home_sp.combine_first(-away_sp).rename("home_spread")
    per_pull = pd.concat([tot, spread], axis=1).reset_index()

    rows = []
    meta = o.groupby("event_id").agg(away=("away", "first"), home=("home", "first"),
                                     start=("start", "first"))
    for eid, g in per_pull.groupby("event_id"):
        g = g.sort_values("pulled_at")
        both = g.dropna(subset=["total", "home_spread"])
        use = both if len(both) else g
        last, first = use.iloc[-1], use.iloc[0]
        rows.append({
            "event_id": eid, "away": meta.at[eid, "away"], "home": meta.at[eid, "home"],
            "start": meta.at[eid, "start"],
            "total": last.total, "home_spread": last.home_spread,
            "total_open": first.total, "home_spread_open": first.home_spread,
            "last_pull": last.pulled_at, "first_pull": first.pulled_at,
            "n_pulls": int(g.pulled_at.nunique()),
        })
    return pd.DataFrame(rows, columns=cols)


def implied(total: float, home_spread: float) -> tuple[float, float]:
    """(away, home) implied team totals: total/2 -/+ spread/2, where
    ``home_spread`` is the home team's line (negative = home favored)."""
    home = total / 2.0 - home_spread / 2.0
    away = total / 2.0 + home_spread / 2.0
    return away, home


def implied_totals(games: pd.DataFrame, odds: pd.DataFrame, context: pd.DataFrame,
                   main_teams: set[str] | None = None) -> pd.DataFrame:
    """One row per scheduled game of the week: newest pre-kickoff odds,
    movement since the week's first pull, a fallback to the nflverse lines in
    team_week_context, and whether the game is on the main slate
    (``main_teams`` empty/None -> unknown)."""
    lines = odds_game_lines(odds)
    ctx = context.copy()
    if not ctx.empty:
        ctx["team"] = ctx.team.map(canon_team)
    rows = []
    for g in games.itertuples(index=False):
        away, home = canon_team(g.away_team), canon_team(g.home_team)
        kick = kickoff_utc(g.gameday, g.gametime)
        row = {"game_id": g.game_id, "kickoff_et": f"{g.weekday[:3]} {g.gametime}",
               "kickoff_utc": kick, "away": away, "home": home,
               "total": np.nan, "home_spread": np.nan, "total_move": np.nan,
               "spread_move": np.nan, "last_pull": pd.NaT, "n_pulls": 0, "source": "none"}
        m = lines[(lines.away == away) & (lines.home == home)] if len(lines) else lines
        if len(m):
            m = m.assign(gap=(m.start - kick).abs()).sort_values("gap")
            ln = m.iloc[0]
            if pd.notna(ln.total) and pd.notna(ln.home_spread):
                row.update(total=float(ln.total), home_spread=float(ln.home_spread),
                           total_move=float(ln.total - ln.total_open)
                           if pd.notna(ln.total_open) else np.nan,
                           spread_move=float(ln.home_spread - ln.home_spread_open)
                           if pd.notna(ln.home_spread_open) else np.nan,
                           last_pull=ln.last_pull, n_pulls=int(ln.n_pulls), source="odds")
        if row["source"] == "none" and not ctx.empty:
            h = ctx[ctx.team == home]
            if len(h) and pd.notna(h.iloc[0].game_total) and pd.notna(h.iloc[0].spread):
                row.update(total=float(h.iloc[0].game_total),
                           home_spread=float(h.iloc[0].spread), source="nflverse")
        if row["source"] != "none":
            row["away_implied"], row["home_implied"] = implied(row["total"], row["home_spread"])
        else:
            row["away_implied"] = row["home_implied"] = np.nan
        row["main_slate"] = (None if not main_teams
                             else bool(away in main_teams and home in main_teams))
        rows.append(row)
    return pd.DataFrame(rows)


def main_slate_fallback(games: pd.DataFrame) -> set[str]:
    """Without the Millionaire's draft group: Sunday games kicking off
    12:00-17:00 Eastern (the classic main slate's window)."""
    out: set[str] = set()
    for g in games.itertuples(index=False):
        if g.weekday == "Sunday" and "12:00" <= str(g.gametime) <= "17:00":
            out |= {canon_team(g.home_team), canon_team(g.away_team)}
    return {t for t in out if t}


# -------------------------------------------------------------- the players --

def fp_main_slate(fp: pd.DataFrame, draft_group: int | None) -> pd.DataFrame:
    """Fantasy Points' projections for the main slate, newest retrieval."""
    if fp.empty:
        return fp
    f = fp.copy()
    f["slate_id"] = f.slate_id.astype(str)
    if draft_group is not None and str(draft_group) in set(f.slate_id):
        f = f[f.slate_id == str(draft_group)]
    elif "slate_name" in f and (f.slate_name == "Main").any():
        f = f[f.slate_name == "Main"]
    return newest_rows(f, "retrieved_at")


def player_board(proj: pd.DataFrame, fp_proj: pd.DataFrame, fp_own: pd.DataFrame,
                 exposure: pd.DataFrame) -> pd.DataFrame:
    """Our projection next to FP's projection and projected ownership, and
    how often the player is in our pool and our book."""
    if proj.empty:
        return pd.DataFrame()
    b = proj.copy()
    b["key"] = [player_key(n, p, t) for n, p, t in zip(b.display_name, b.position, b.team)]
    if not fp_proj.empty:
        f = fp_proj.assign(key=[player_key(n, p, t) for n, p, t in
                                zip(fp_proj.name, fp_proj.position, fp_proj.team)])
        f = f.groupby("key", as_index=False).fantasy_points.mean()
        b = b.merge(f.rename(columns={"fantasy_points": "fp_proj"}), on="key", how="left")
    else:
        b["fp_proj"] = np.nan
    if not fp_own.empty:
        o = newest_rows(fp_own, "retrieved_at")
        o = o.assign(key=[player_key(n, p, t) for n, p, t in zip(o.name, o.position, o.team)])
        o = o.groupby("key", as_index=False).projected_ownership_pct.max()
        b = b.merge(o.rename(columns={"projected_ownership_pct": "fp_own"}), on="key", how="left")
    else:
        b["fp_own"] = np.nan
    if not exposure.empty:
        e = exposure[["dk_player_id", "pool_share", "book_share"]].copy()
        e["dk_player_id"] = _num(e.dk_player_id)
        b["dk_player_id"] = _num(b.dk_player_id)
        b = b.merge(e.drop_duplicates("dk_player_id"), on="dk_player_id", how="left")
    else:
        b["pool_share"] = b["book_share"] = np.nan
    b["proj_points"] = _num(b.proj_points)
    b["fp_proj"] = _num(b.fp_proj)
    b["fp_own"] = _num(b.fp_own)
    b["proj_minus_fp"] = b.proj_points - b.fp_proj
    b["book_minus_fp_own"] = 100.0 * b.book_share - b.fp_own
    return b.sort_values("proj_points", ascending=False).reset_index(drop=True)


# ------------------------------------------------------- time-series ranks --

def weekly_ranks(df: pd.DataFrame, value: str, higher_is_better: bool = True,
                 team: str = "team", week: str = "week") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rank teams within each week on ``value`` (1 = best) and summarise each
    team: season mean, last-3 mean, trend (L3 - season), latest weekly rank
    and the rank of its season mean.

    Returns (long rows with ``rank``, one summary row per team)."""
    if df.empty or value not in df:
        return pd.DataFrame(), pd.DataFrame()
    d = df[[team, week, value]].dropna(subset=[value]).copy()
    d[value] = d[value].astype(float)
    # An in-progress week (only Thursday's game played) would rank two teams
    # 1-2; weeks with fewer than half the busiest week's teams are left out.
    per_week = d.groupby(week)[team].nunique()
    d = d[d[week].isin(per_week[per_week >= 0.5 * per_week.max()].index)]
    d["rank"] = d.groupby(week)[value].rank(ascending=not higher_is_better, method="min")
    d = d.sort_values([team, week])
    g = d.groupby(team)
    summ = pd.DataFrame({
        "games": g[value].size(),
        "season": g[value].mean(),
        "l3": g[value].apply(lambda s: s.tail(3).mean()),
        "latest": g[value].last(),
        "latest_rank": g["rank"].last(),
        "best_rank": g["rank"].min(),
    })
    summ["trend"] = summ.l3 - summ.season
    summ["season_rank"] = summ.season.rank(ascending=not higher_is_better, method="min")
    summ = summ.reset_index().sort_values("season_rank").reset_index(drop=True)
    return d.reset_index(drop=True), summ


def defense_totals(dpa: pd.DataFrame, position: str = "ALL") -> pd.DataFrame:
    """DK points allowed per defense-week, over all skill positions or one."""
    if dpa.empty:
        return pd.DataFrame(columns=["team", "week", "fp_allowed"])
    d = dpa if position == "ALL" else dpa[dpa.position == position]
    return d.groupby(["team", "week"], as_index=False).fp_allowed.sum()


# ---------------------------------------------------------------- accuracy --

def accuracy_by_week(ours: pd.DataFrame, fp: pd.DataFrame, min_proj: float = 5.0) -> pd.DataFrame:
    """MAE and bias of our projection against realized DK points, by week
    and position (plus ALL), on players we projected at ``min_proj`` or more;
    FP's MAE on the players both sources priced, with ours on that same set."""
    cols = ["week", "position", "n", "mae_ours", "bias_ours",
            "n_common", "mae_ours_common", "mae_fp_common"]
    if ours.empty:
        return pd.DataFrame(columns=cols)
    o = ours.copy()
    o["proj_points"] = _num(o.proj_points)
    o["dk_points"] = _num(o.dk_points)
    o = o[(o.proj_points >= min_proj) & o.dk_points.notna()]
    o["key"] = [player_key(n, p, t) for n, p, t in zip(o.display_name, o.position, o.team)]
    if not fp.empty:
        f = fp.assign(key=[player_key(n, p, t) for n, p, t in zip(fp.name, fp.position, fp.team)])
        f = f.groupby(["week", "key"], as_index=False).fantasy_points.mean()
        o = o.merge(f, on=["week", "key"], how="left")
    else:
        o["fantasy_points"] = np.nan
    o["fantasy_points"] = _num(o.fantasy_points)
    rows = []
    for (wk, pos), g in pd.concat([o, o.assign(position="ALL")]).groupby(["week", "position"]):
        err = g.proj_points - g.dk_points
        c = g.dropna(subset=["fantasy_points"])
        rows.append({
            "week": int(wk), "position": pos, "n": len(g),
            "mae_ours": float(err.abs().mean()), "bias_ours": float(err.mean()),
            "n_common": len(c),
            "mae_ours_common": float((c.proj_points - c.dk_points).abs().mean()) if len(c) else np.nan,
            "mae_fp_common": float((c.fantasy_points - c.dk_points).abs().mean()) if len(c) else np.nan,
        })
    return pd.DataFrame(rows, columns=cols)


def spearman(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 3:
        return float("nan")
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


OWN_BINS = (0.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 101.0)


def ownership_calibration(pred: pd.DataFrame, real: pd.DataFrame,
                          bins: tuple[float, ...] = OWN_BINS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Projected (``pred``: week, name, own) vs realized Millionaire
    ownership (``real``: week, display_name, own), both in percent.

    Population follows PREREG-O1: players priced by the source AND drafted in
    the field (undrafted are counted, not scored). Returns (per-bin mean
    projected vs realized, per-week n/Spearman/MAE/undrafted)."""
    if pred.empty or real.empty:
        return pd.DataFrame(), pd.DataFrame()
    # Join on normalised name AND team when the realized rows carry the
    # slate-resolved team (milly_field_ownership.sql); a name that collides
    # within a side is dropped, never merged.
    with_team = "team" in real and "team" in pred and real.team.notna().any()

    def keyed(df: pd.DataFrame, name: str) -> pd.DataFrame:
        k = df[name].map(norm_name)
        if with_team:
            k = k + ":" + df.team.map(lambda t: canon_team(t) or "")
            df = df[df.team.notna()]
            k = k.loc[df.index]
        out = df.assign(key=k)
        n = out.groupby(["week", "key"]).key.transform("size")
        return out[n == 1][["week", "key", "own"]]

    p, r = keyed(pred, "name"), keyed(real, "display_name")
    j = p.merge(r, on=["week", "key"], suffixes=("_pred", "_real"))
    undrafted = p.merge(r[["week", "key"]], on=["week", "key"], how="left", indicator=True)
    und = undrafted[undrafted._merge == "left_only"].groupby("week").size()
    weeks = []
    for wk, g in j.groupby("week"):
        weeks.append({"week": int(wk), "n": len(g),
                      "spearman": spearman(g.own_pred, g.own_real),
                      "mae": float((g.own_pred - g.own_real).abs().mean()),
                      "undrafted": int(und.get(wk, 0))})
    j["bin"] = pd.cut(j.own_pred, list(bins), right=False)
    cal = (j.groupby("bin", observed=True)
           .agg(n=("own_pred", "size"), mean_pred=("own_pred", "mean"),
                mean_real=("own_real", "mean")).reset_index())
    cal["bin"] = cal["bin"].astype(str)
    return cal, pd.DataFrame(weeks)


def book_leverage(exposure: pd.DataFrame, field_own: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Our book's exposure against realized Millionaire ownership for one
    week: per player book %, field %, leverage (book - field) and DK points;
    plus the active share 0.5 * sum|w - f| / 9 (0 = the field's exposures,
    1 = disjoint), as in scripts/book_vs_field_scoreboard.information_lines."""
    if exposure.empty or field_own.empty:
        return pd.DataFrame(), {}
    # Join on the DraftKings player id when the field rows carry the
    # slate-resolved id; otherwise on normalised name (the rows of one
    # contest's standings, where names are the identity DraftKings prints).
    by_id = ("dk_player_id" in field_own and "dk_player_id" in exposure
             and field_own.dk_player_id.notna().any())
    if by_id:
        e = exposure.assign(key=_num(exposure.dk_player_id).astype("Int64").astype("string"))
        f = field_own.dropna(subset=["dk_player_id"])
        f = f.assign(key=_num(f.dk_player_id).astype("Int64").astype("string"))
    else:
        e = exposure.assign(key=exposure.player.map(norm_name))
        f = field_own.assign(key=field_own.display_name.map(norm_name))
    e = e.groupby("key", as_index=False).agg(player=("player", "first"),
                                             position=("position", "first"),
                                             book_share=("book_share", "max"))
    f = f.groupby("key", as_index=False).agg(field_own=("own", "max"), fpts=("fpts", "max"),
                                             display_name=("display_name", "first"))
    j = e.merge(f, on="key", how="outer")
    j["player"] = j.player.fillna(j.display_name)
    j["book_pct"] = 100.0 * j.book_share.fillna(0.0)
    j["field_pct"] = j.field_own.fillna(0.0)
    j["leverage"] = j.book_pct - j.field_pct
    active = float(0.5 * (j.book_pct - j.field_pct).abs().sum() / 100.0 / 9.0)
    held = j[j.book_pct > 0]
    summary = {"active_share": active, "players_held": int(len(held)),
               "book_weighted_field_own": float((held.book_pct * held.field_pct).sum() / 900.0)
               if len(held) else float("nan")}
    out = j[(j.book_pct > 0) | (j.field_pct >= 5)].sort_values("leverage", ascending=False)
    return out[["player", "position", "book_pct", "field_pct", "leverage", "fpts"]].reset_index(drop=True), summary


# ---------------------------------------------------------------- fetchers --
# Each returns a DataFrame; callers wrap them in the app's TTL cache.

SCHEDULE_COLUMNS = ["season", "week", "game_id", "gameday", "gametime", "weekday", "home_team",
                    "away_team", "home_score", "away_score", "total_line", "spread_line"]


def fetch_schedule(query: Query, season: int) -> pd.DataFrame:
    df = query(render("schedules_season", season=int(season)))
    return df if not df.empty else pd.DataFrame(columns=SCHEDULE_COLUMNS)


def fetch_milly_contests(query: Query, season: int) -> pd.DataFrame:
    df = query(render("milly_contests"))
    return df[df.season == int(season)].reset_index(drop=True) if not df.empty else df


def fetch_slate_teams(query: Query, draft_group: int) -> set[str]:
    df = query(render("slate_teams", draft_group=int(draft_group)))
    return {t for t in (canon_team(x) for x in df.get("team_abbr", [])) if t}


def fetch_odds(query: Query, games: pd.DataFrame) -> pd.DataFrame:
    if games.empty:
        return pd.DataFrame()
    days = sorted(str(d) for d in games.gameday)
    start = (date.fromisoformat(days[0]) - timedelta(days=1)).isoformat()
    end = (date.fromisoformat(days[-1]) + timedelta(days=2)).isoformat()
    pulled_from = (date.fromisoformat(days[0]) - timedelta(days=9)).isoformat()
    return query(render("odds_week", start=start, end=end, pulled_from=pulled_from))


def fetch_context(query: Query, season: int, week: int) -> pd.DataFrame:
    return query(render("team_context_week", season=int(season), week=int(week)))


def fetch_projections(query: Query, season: int, week: int, lock: datetime) -> pd.DataFrame:
    return query(render("projections_week", season=int(season), week=int(week),
                        lock_utc=lock.strftime("%Y-%m-%d %H:%M:%S+00")))


def fetch_fp_week(query: Query, season: int, week: int, lock: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    lk = lock.strftime("%Y-%m-%d %H:%M:%S+00")
    proj = query(render("fp_projections_week", season=int(season), week=int(week), lock_utc=lk))
    own = query(render("fp_ownership_week", season=int(season), week=int(week), lock_utc=lk))
    return proj, own


def fetch_exposure(query: Query, season: int, week: int | None = None) -> pd.DataFrame:
    return query(render("pool_exposure", season=int(season), week_filter=_week_filter(week, "pool_exposure")))


def fetch_arms(query: Query, season: int) -> pd.DataFrame:
    return query(render("arms_weekly", season=int(season)))


def fetch_contest_lines(query: Query, season: int) -> pd.DataFrame:
    return query(render("contest_lines", season=int(season)))


def fetch_offense(query: Query, season: int) -> pd.DataFrame:
    return query(render("offense_weekly", season=int(season)))


def fetch_defense(query: Query, season: int) -> pd.DataFrame:
    return query(render("defense_weekly", season=int(season)))


def fetch_accuracy_inputs(query: Query, season: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ours = query(render("accuracy_ours", season=int(season)))
    fp = query(render("fp_projections_season", season=int(season)))
    fp_own = query(render("fp_ownership_season", season=int(season)))
    return ours, fp, fp_own


def fetch_milly_lines(query: Query, season: int) -> pd.DataFrame:
    return query(render("milly_lines", season=int(season)))


def fetch_milly_top(query: Query, season: int, week: int | None, top_n: int = 2000,
                    top_share: float = 0.01, cash_rows: int = 0) -> pd.DataFrame:
    return query(render("milly_top_lineups", season=int(season), week_filter=_week_filter(week),
                        top_n=int(top_n), top_share=float(top_share), cash_rows=int(cash_rows)))


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def fetch_milly_user_lineups(query: Query, season: int, week: int | None, users: list[str]) -> pd.DataFrame:
    """Every Millionaire lineup of ``users`` (milly_user_lineups.sql), in fetch_milly_top's columns. The names are
    inlined as a literal, so each must match USERNAME_RE; anything else is refused (never quoted or escaped)."""
    bad = [u for u in users if not USERNAME_RE.match(u)]
    if bad:
        raise ValueError(f"refusing {len(bad)} user name(s) outside [A-Za-z0-9_.-]: {bad[:3]}")
    if not users:
        raise ValueError("no users given")
    arr = "[" + ", ".join(f"'{u}'" for u in sorted(set(users))) + "]"
    return query(render("milly_user_lineups", season=int(season), week_filter=_week_filter(week), users_array=arr))


def fetch_milly_slate(query: Query, season: int, week: int | None) -> pd.DataFrame:
    return query(render("milly_slate", season=int(season), week_filter_m=_week_filter(week, "m")))


def fetch_field_ownership(query: Query, season: int, week: int | None) -> pd.DataFrame:
    return query(render("milly_field_ownership", season=int(season), week_filter=_week_filter(week),
                        week_filter_m=_week_filter(week, "m")))


def fetch_freshness(query: Query, season: int) -> pd.DataFrame:
    return query(render("freshness", season=int(season)))


# ---------------------------------------------------------------- insights --

def projection_disagreements(ours: pd.DataFrame, fp: pd.DataFrame,
                             threshold: float = 4.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Insight 5: players where our projection and Fantasy Points' differed by
    ``threshold`` or more, and who was closer to the realized DK points.
    Returns (per week/position: n, ours closer, FP closer, MAE of each on
    those players; the player rows, largest disagreement first)."""
    cols = ["week", "position", "n", "ours_closer", "fp_closer", "mae_ours", "mae_fp"]
    if ours.empty or fp.empty:
        return pd.DataFrame(columns=cols), pd.DataFrame()
    o = ours.copy()
    o["key"] = [player_key(n, p, t) for n, p, t in zip(o.display_name, o.position, o.team)]
    f = fp.assign(key=[player_key(n, p, t) for n, p, t in zip(fp.name, fp.position, fp.team)])
    f = f.groupby(["week", "key"], as_index=False).fantasy_points.mean()
    j = o.merge(f, on=["week", "key"])
    for c in ("proj_points", "fantasy_points", "dk_points"):
        j[c] = _num(j[c])
    j = j.dropna(subset=["proj_points", "fantasy_points", "dk_points"])
    j["gap"] = j.proj_points - j.fantasy_points
    d = j[j.gap.abs() >= threshold].copy()
    if d.empty:
        return pd.DataFrame(columns=cols), d
    d["err_ours"] = (d.proj_points - d.dk_points).abs()
    d["err_fp"] = (d.fantasy_points - d.dk_points).abs()
    d["closer"] = np.where(d.err_ours < d.err_fp, "ours",
                           np.where(d.err_fp < d.err_ours, "FP", "tie"))
    rows = []
    for (wk, pos), g in pd.concat([d, d.assign(position="ALL")]).groupby(["week", "position"]):
        rows.append({"week": int(wk), "position": pos, "n": len(g),
                     "ours_closer": int((g.closer == "ours").sum()),
                     "fp_closer": int((g.closer == "FP").sum()),
                     "mae_ours": float(g.err_ours.mean()), "mae_fp": float(g.err_fp.mean())})
    players = d.sort_values(["week", "gap"], key=lambda s: s.abs() if s.name == "gap" else s,
                            ascending=[True, False])
    return pd.DataFrame(rows, columns=cols), players[[
        "week", "display_name", "position", "team", "proj_points", "fantasy_points",
        "dk_points", "gap", "closer"]].reset_index(drop=True)


def fetch_insight(query: Query, name: str, season: int) -> pd.DataFrame:
    """One insight query (sql/dashboard/insight_<name>.sql) for the season."""
    return query(render(f"insight_{name}", season=int(season)))
