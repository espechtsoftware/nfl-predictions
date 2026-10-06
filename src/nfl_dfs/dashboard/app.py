"""Dashboard v2: one server-rendered page per section.

Serve:  nfl-dfs dashboard [--port 8080]
        (uvicorn nfl_dfs.dashboard.app:create_app --factory)

Every page renders, with an explanatory note, when its table is missing or
empty or when a query fails. BigQuery results are cached in-process for
DASHBOARD_CACHE_TTL seconds (default 600). The Milly Neo4j graph is local
only and not part of the UI (operator 2026-10-04; scripts/load_milly_neo4j.py).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from ..config import current_season
from . import data as D
from . import milly as M
from .html import (fmt_num, filters, line_chart, note, page, select, table,
                   text_input, esc)
from .stakes import Reader, gcs_reader, stake_rows
from .teams import canon_team, display_team

log = logging.getLogger(__name__)


# The Millionaire week view loads max(1% of the field, 10 lineups) up to this
# many lineups (Week 1 2026: 832k entries -> 8,320); the page states the share.
TOP_CAP = 10_000


class TTLCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self._d: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, fn: Callable[[], object]) -> object:
        now = time.monotonic()
        with self._lock:
            hit = self._d.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        val = fn()
        with self._lock:
            self._d[key] = (now, val)
        return val


def create_app(query: D.Query | None = None,
               env: dict | None = None,
               stake_reader: Reader | None = None) -> FastAPI:
    """``query`` defaults to nfl_dfs.bq.query_df, ``stake_reader`` to the
    private week-inputs bucket; tests pass fakes."""
    if query is None:
        from ..bq import query_df as query  # noqa: PLC0415
    env = dict(os.environ if env is None else env)
    cache = TTLCache(float(env.get("DASHBOARD_CACHE_TTL", "600")))
    stake_reader = stake_reader or gcs_reader
    app = FastAPI(title="DFS dashboard", version="2", docs_url=None, redoc_url=None)

    def q(sql: str) -> pd.DataFrame:
        def run() -> pd.DataFrame:
            try:
                return query(sql)
            except Exception as exc:
                if D.is_missing_table(exc):
                    log.warning("%s: table not found", D.sql_name(sql))
                    return pd.DataFrame()
                raise
        return cache.get(sql, run).copy()  # type: ignore[union-attr]

    def guarded(fn: Callable[[], str]) -> str:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 -- a page never 500s on a source
            log.exception("section failed")
            return note(f"This section is unavailable: {type(exc).__name__}: "
                        f"{str(exc).splitlines()[0][:300] if str(exc) else ''}", error=True)

    # ------------------------------------------------------------ context --

    def schedule(season: int) -> pd.DataFrame:
        return D.fetch_schedule(q, season)

    def resolve(season: int | None, week: int | None) -> tuple[int, int | None, pd.DataFrame]:
        season = int(season or env.get("DASHBOARD_SEASON") or current_season())
        try:
            sch = schedule(season)
        except Exception:  # noqa: BLE001 -- sections report their own failures
            log.exception("schedule unavailable")
            sch = pd.DataFrame(columns=D.SCHEDULE_COLUMNS)
        if week is None:
            week = D.current_week(sch)
        return season, week, sch

    def milly_contest(season: int, week: int | None) -> pd.Series | None:
        if week is None:
            return None
        mc = D.fetch_milly_contests(q, season)
        if mc.empty:
            return None
        m = mc[mc.week == week]
        return m.iloc[0] if len(m) else None

    def week_picker(season: int, week: int | None, sch: pd.DataFrame, action: str,
                    extra: list[str] | None = None) -> str:
        weeks = sorted(int(w) for w in sch.week.unique()) if not sch.empty else ([week] if week else [])
        return filters([text_input("season", "Season", season, 5),
                        select("week", "Week", [(w, f"Week {w}") for w in weeks], week),
                        *(extra or [])], action)

    def header(title: str, sub: str) -> str:
        return f"<h1>{esc(title)}</h1><p class='sub'>{sub}</p>"

    # -------------------------------------------------------------- pages --

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"ok": True, "app": "dashboard-v2",
                             "code_sha": env.get("CODE_SHA", "unknown")})

    @app.get("/", response_class=HTMLResponse)
    def overview(season: int | None = None, week: int | None = None) -> str:
        season, week, sch = resolve(season, week)

        def cards() -> str:
            m = milly_contest(season, week)
            games = sch[sch.week == week] if week else sch.iloc[0:0]
            lk = D.lock_utc(sch, week) if week else None
            items = [("Week", f"{season} · Week {week}" if week else "–"),
                     ("Games", str(len(games))),
                     ("Main-slate lock (UTC)", lk.strftime("%a %H:%M") if lk else "–"),
                     ("Millionaire", f"{m.contest_id} · {int(m.field_size):,} max" if m is not None
                      and pd.notna(m.get("field_size")) else (str(m.contest_id) if m is not None else "not resolved"))]
            warn = ""
            if m is not None and pd.notna(m.get("lobby_contest_id")) \
                    and str(m.get("lobby_contest_id")) != str(m.contest_id):
                warn = note(f"The lobby's Millionaire is {m.get('lobby_contest_id')} but the imported "
                            f"standings are {m.contest_id}; the dashboard uses the standings.")
            return warn + "<div class='grid'>" + "".join(
                f"<div class='card stat'><div class='k'>{esc(k)}</div><div class='v'>{esc(v)}</div></div>"
                for k, v in items) + "</div>"

        def fresh() -> str:
            f = D.fetch_freshness(q, season)
            return table(f, [("source", "Source", None, "l"), ("newest", "Newest row (UTC)", None, "l")])

        pages = "".join(
            f"<div class='card'><b><a href='{h}'>{esc(t)}</a></b><div class='muted'>{esc(d)}</div></div>"
            for h, t, d in (
                ("/games", "Games", "Implied totals from the newest pre-kickoff odds, with movement"),
                ("/players", "Players", "Our projections vs Fantasy Points, pool and book exposure"),
                ("/offense", "Offense", "Weekly offense ranks: DK points, points, yards, plays"),
                ("/defense", "Defense", "Weekly DK points allowed ranks, by position"),
                ("/accuracy", "Accuracy", "Projection MAE, ownership calibration, book leverage"),
                ("/arms", "Arms", "Every arm and shadow per week vs the Millionaire field"),
                ("/milly", "Milly", "Winning scores, lines and winners' construction"),
                ("/insights", "Insights", "What won vs Fantasy Points and us; repeat top finishers")))
        body = (header("Overview", "Read-only views over the warehouse and the published week tables.")
                + guarded(cards) + f"<div class='grid'>{pages}</div>"
                + "<h2>Freshness</h2>" + guarded(fresh))
        return page("Overview", body, "/")

    @app.get("/games", response_class=HTMLResponse)
    def games_page(season: int | None = None, week: int | None = None) -> str:
        season, week, sch = resolve(season, week)

        def build() -> str:
            if week is None or sch.empty:
                return note("No schedule rows for this season yet.")
            games = sch[sch.week == week]
            odds = D.fetch_odds(q, games)
            ctx = D.fetch_context(q, season, week)
            m = milly_contest(season, week)
            main, how = set(), "unknown"
            if m is not None and pd.notna(m.get("draft_group_id")):
                main = D.fetch_slate_teams(q, int(m.draft_group_id))
                how = f"teams on the Millionaire's draft group {int(m.draft_group_id)}"
            if not main:
                main, how = D.main_slate_fallback(games), "Sunday 12:00-17:00 ET kickoffs (no draft group)"
            t = D.implied_totals(games, odds, ctx, main)
            if t.empty:
                return note("No games this week.")
            t = t.sort_values(["main_slate", "kickoff_utc"], ascending=[False, True])
            t["matchup"] = [f"{display_team(a)} @ {display_team(h)}" for a, h in zip(t.away, t.home)]
            t["slate"] = t.main_slate.map({True: "main", False: "off-slate", None: "?"})
            t["pull"] = pd.to_datetime(t.last_pull, utc=True).dt.strftime("%a %H:%M")
            games_tbl = table(t, [
                ("kickoff_et", "Kickoff ET", None, "l"), ("matchup", "Game", None, "l"),
                ("slate", "Slate", None, "l"), ("total", "Total", fmt_num(1)),
                ("total_move", "Δ total", fmt_num(1, signed=True)),
                ("home_spread", "Home spread", fmt_num(1, signed=True)),
                ("spread_move", "Δ spread", fmt_num(1, signed=True)),
                ("away_implied", "Away implied", fmt_num(2)), ("home_implied", "Home implied", fmt_num(2)),
                ("source", "Source", None, "l"), ("pull", "Last pull UTC", None, "l"),
                ("n_pulls", "Pulls")])
            teams = pd.concat([
                pd.DataFrame({"team": t.away, "opp": t.home, "implied": t.away_implied, "slate": t.slate}),
                pd.DataFrame({"team": t.home, "opp": t.away, "implied": t.home_implied, "slate": t.slate})])
            teams = teams.dropna(subset=["implied"]).sort_values("implied", ascending=False)
            hi = teams.implied.max() if len(teams) else 1
            teams["bar"] = [f"<span class='bar' style='width:{max(2, 160 * v / hi):.0f}px'></span> {v:.1f}"
                            for v in teams.implied]
            teams["team_d"] = teams.team.map(display_team)
            teams["opp_d"] = teams.opp.map(display_team)
            team_tbl = table(teams, [("team_d", "Team", None, "l"), ("opp_d", "Opp", None, "l"),
                                     ("slate", "Slate", None, "l"), ("bar", "Implied total", str, "l")])
            return (f"<p class='sub'>Main slate: {esc(how)}. Implied = total/2 ∓ home spread/2 "
                    f"(spread negative = favored). Movement is newest minus the first pull within "
                    f"7 days of kickoff; only pulls before kickoff count. Source 'nflverse' = "
                    f"team_week_context fallback (no odds pull).</p>{games_tbl}"
                    f"<h2>Teams by implied total</h2>{team_tbl}")

        body = (header(f"Games · Week {week}", "Totals, spreads and implied team totals")
                + week_picker(season, week, sch, "/games") + guarded(build))
        return page("Games", body, "/games")

    @app.get("/players", response_class=HTMLResponse)
    def players_page(season: int | None = None, week: int | None = None,
                     pos: str = "ALL", n: int = 60, slate: str = "main") -> str:
        season, week, sch = resolve(season, week)

        def build() -> str:
            lk = D.lock_utc(sch, week) if week else None
            if lk is None:
                return note("No Sunday games for this week in the schedule.")
            proj = D.fetch_projections(q, season, week, lk)
            if proj.empty:
                return note("No pre-lock projection batch for this week yet.")
            m = milly_contest(season, week)
            fp_proj, fp_own = D.fetch_fp_week(q, season, week, lk)
            fp_main = D.fp_main_slate(fp_proj, int(m.draft_group_id) if m is not None
                                      and pd.notna(m.get("draft_group_id")) else None)
            exp = D.fetch_exposure(q, season, week)
            b = D.player_board(proj, fp_main, fp_own, exp)
            if slate == "main":
                main = (D.fetch_slate_teams(q, int(m.draft_group_id)) if m is not None
                        and pd.notna(m.get("draft_group_id")) else set())
                main = main or D.main_slate_fallback(sch[sch.week == week])
                b = b[b.team.map(canon_team).isin(main)]
            if pos != "ALL":
                b = b[b.position == pos]
            b["team_d"] = b.team.map(display_team)
            b["opp_d"] = b.opponent.map(display_team)
            batch = pd.to_datetime(proj.generated_at, utc=True).max()
            notes = [f"Our batch: {batch:%a %H:%M} UTC (newest before lock)."]
            if fp_main.empty:
                notes.append("No Fantasy Points projections for this week.")
            if exp.empty:
                notes.append("Pool/book exposure not published for this week yet "
                             "(scripts/publish_dashboard_week.py).")
            else:
                src = exp.book_source.iloc[0] if "book_source" in exp else "unlabelled"
                notes.append(f"Exposure from run {esc(exp.run_id.iloc[0])}; 'In book' = {esc(src)}.")
            pct = fmt_num(1, pct=True)
            share = lambda v: pct(100 * float(v)) if v is not None and pd.notna(v) else pct(np.nan)  # noqa: E731
            tbl = table(b, [
                ("display_name", "Player", None, "l"), ("position", "Pos", None, "l"),
                ("team_d", "Team", None, "l"), ("opp_d", "Opp", None, "l"), ("salary", "Salary", fmt_num(0)),
                ("proj_points", "Our proj", fmt_num(1)), ("proj_p90", "Our p90", fmt_num(1)),
                ("fp_proj", "FP proj", fmt_num(1)), ("proj_minus_fp", "Ours − FP", fmt_num(1, signed=True)),
                ("fp_own", "FP own", pct), ("pool_share", "In pool", share),
                ("book_share", "In book", share),
                ("book_minus_fp_own", "Book − FP own", fmt_num(1, signed=True))], max_rows=int(n))
            return f"<p class='sub'>{' '.join(notes)}</p>{tbl}"

        body = (header(f"Players · Week {week}",
                       "Top projected players; Fantasy Points columns are licensed and shown only "
                       "as comparisons here")
                + week_picker(season, week, sch, "/players", [
                    select("pos", "Position", [(p, p) for p in ("ALL", "QB", "RB", "WR", "TE", "DST")], pos),
                    select("slate", "Slate", [("main", "Main slate"), ("all", "All games")], slate),
                    text_input("n", "Rows", n, 4)])
                + guarded(build))
        return page("Players", body, "/players")

    def rank_section(long: pd.DataFrame, summ: pd.DataFrame, value: str, label: str,
                     highlight: list[str], higher_is_better: bool) -> str:
        if summ.empty:
            return note("No completed weeks yet.")
        hl = [t for t in highlight if t in set(summ.team)] or list(summ.team.head(3))
        series = [{"label": display_team(t), "highlight": t in hl,
                   "points": [(int(r.week), float(r["rank"])) for _, r in g.iterrows()]}
                  for t, g in long.groupby("team")]
        series.sort(key=lambda s: s["highlight"])
        n_teams = int(long.groupby("week").team.nunique().max())
        chart = line_chart(series, invert_y=True, y_min=1, y_max=n_teams,
                           y_label=f"rank ({label})")
        s = summ.copy()
        s["team_d"] = s.team.map(display_team)
        tbl = table(s, [("season_rank", "Rank", fmt_num(0)), ("team_d", "Team", None, "l"),
                        ("games", "G"), ("season", f"{label}/g", fmt_num(1)),
                        ("l3", "L3", fmt_num(1)), ("trend", "Trend", fmt_num(1, signed=True)),
                        ("latest", "Last wk", fmt_num(1)), ("latest_rank", "Last-wk rank", fmt_num(0)),
                        ("best_rank", "Best rank", fmt_num(0))])
        direction = "most" if higher_is_better else "fewest"
        return (f"<p class='sub'>Rank 1 = {direction} {esc(label)} that week. Highlighted: "
                f"{esc(', '.join(display_team(t) for t in hl))} (set with ?teams=KC,BUF). "
                f"Trend = last-3 average minus season average.</p>{chart}{tbl}")

    @app.get("/offense", response_class=HTMLResponse)
    def offense_page(season: int | None = None, metric: str = "dk_points", teams: str = "") -> str:
        season, _, _ = resolve(season, None)
        labels = {"dk_points": "DK points", "points": "points scored", "yards": "yards", "plays": "plays"}
        metric = metric if metric in labels else "dk_points"

        def build() -> str:
            off = D.fetch_offense(q, season)
            if off.empty:
                return note("No completed games this season yet.")
            off["team"] = off.team.map(canon_team)
            long, summ = D.weekly_ranks(off, metric, higher_is_better=True)
            hl = [canon_team(t) for t in teams.split(",") if canon_team(t)]
            extra = off.groupby("team")[["points", "yards", "plays"]].mean().reset_index()
            summ = summ.merge(extra.rename(columns={"points": "pts_pg", "yards": "yds_pg",
                                                    "plays": "plays_pg"}), on="team", how="left")
            out = rank_section(long, summ, metric, labels[metric], hl, True)
            s = summ.copy()
            s["team_d"] = s.team.map(display_team)
            return out + "<h2>Per game</h2>" + table(s, [
                ("team_d", "Team", None, "l"), ("pts_pg", "Points/g", fmt_num(1)),
                ("yds_pg", "Yards/g", fmt_num(0)), ("plays_pg", "Plays/g", fmt_num(1))])

        body = (header(f"Offense · {season}", "Team offense ranked week by week")
                + filters([text_input("season", "Season", season, 5),
                           select("metric", "Metric", list(labels.items()), metric),
                           text_input("teams", "Highlight", teams, 12)], "/offense")
                + guarded(build))
        return page("Offense", body, "/offense")

    @app.get("/defense", response_class=HTMLResponse)
    def defense_page(season: int | None = None, pos: str = "ALL", teams: str = "") -> str:
        season, _, _ = resolve(season, None)
        pos = pos if pos in ("ALL", "QB", "RB", "WR", "TE") else "ALL"

        def build() -> str:
            dpa = D.fetch_defense(q, season)
            if dpa.empty:
                return note("defense_points_against has no rows for this season yet.")
            dpa["team"] = dpa.team.map(canon_team)
            tot = D.defense_totals(dpa, pos)
            long, summ = D.weekly_ranks(tot, "fp_allowed", higher_is_better=False)
            hl = [canon_team(t) for t in teams.split(",") if canon_team(t)]
            label = "DK pts allowed" + ("" if pos == "ALL" else f" to {pos}")
            return rank_section(long, summ, "fp_allowed", label, hl, False)

        body = (header(f"Defense · {season}", "DK points allowed, ranked week by week (1 = toughest)")
                + filters([text_input("season", "Season", season, 5),
                           select("pos", "Position", [(p, p) for p in ("ALL", "QB", "RB", "WR", "TE")], pos),
                           text_input("teams", "Highlight", teams, 12)], "/defense")
                + guarded(build))
        return page("Defense", body, "/defense")

    @app.get("/accuracy", response_class=HTMLResponse)
    def accuracy_page(season: int | None = None, week: int | None = None) -> str:
        season, week, sch = resolve(season, week)
        inputs: dict = {}

        def acc_inputs():
            if not inputs:
                inputs["ours"], inputs["fp"], inputs["fp_own"] = D.fetch_accuracy_inputs(q, season)
            return inputs["ours"], inputs["fp"], inputs["fp_own"]

        def projections() -> str:
            ours, fp, _ = acc_inputs()
            acc = D.accuracy_by_week(ours, fp)
            if acc.empty:
                return note("No scored weeks with a pre-lock projection batch yet.")
            allp = acc[acc.position == "ALL"]
            chart = line_chart([
                {"label": "Ours (all)", "highlight": True,
                 "points": [(int(r.week), r.mae_ours) for r in allp.itertuples()]},
                {"label": "Ours (FP set)", "highlight": True,
                 "points": [(int(r.week), r.mae_ours_common) for r in allp.itertuples()]},
                {"label": "FP (FP set)", "highlight": True,
                 "points": [(int(r.week), r.mae_fp_common) for r in allp.itertuples()]}],
                y_label="MAE (DK pts)")
            return (chart + table(acc, [
                ("week", "Wk"), ("position", "Pos", None, "l"), ("n", "n"),
                ("mae_ours", "MAE ours", fmt_num(2)), ("bias_ours", "Bias ours", fmt_num(2, signed=True)),
                ("n_common", "n (both)"), ("mae_ours_common", "MAE ours (both)", fmt_num(2)),
                ("mae_fp_common", "MAE FP (both)", fmt_num(2))]))

        def ownership() -> str:
            _, _, fp_own = acc_inputs()
            real = D.fetch_field_ownership(q, season, None)
            if real.empty:
                return note("No Millionaire standings imported this season yet.")
            if fp_own.empty:
                return note("No Fantasy Points projected ownership this season yet.")
            pred = fp_own.rename(columns={"projected_ownership_pct": "own"})
            cal, weeks = D.ownership_calibration(pred, real)
            if cal.empty:
                return note("No week has both FP projected ownership and Millionaire results yet.")
            chart = line_chart([{"label": "FP projected vs realized", "highlight": True,
                                 "points": [(round(r.mean_pred, 1), r.mean_real) for r in cal.itertuples()]}],
                               x_label="mean projected own %", y_label="mean realized own %",
                               y_min=0, diagonal=True)
            return (chart + table(cal, [("bin", "Projected bin", None, "l"), ("n", "n"),
                                        ("mean_pred", "Mean projected", fmt_num(1, pct=True)),
                                        ("mean_real", "Mean realized", fmt_num(1, pct=True))])
                    + "<h2>Per week</h2>" + table(weeks, [
                        ("week", "Wk"), ("n", "Players"), ("spearman", "Spearman", fmt_num(3)),
                        ("mae", "MAE (pts of %)", fmt_num(2)), ("undrafted", "Priced, undrafted")]))

        def leverage() -> str:
            if week is None:
                return note("No week selected.")
            exp = D.fetch_exposure(q, season, week)
            if exp.empty:
                return note("No published book exposure for this week.")
            real = D.fetch_field_ownership(q, season, week)
            if real.empty:
                return note("The week's Millionaire standings are not imported yet.")
            lev, summ = D.book_leverage(exp, real)
            return (f"<p class='sub'>Active share {summ['active_share']:.3f} (0 = the field's "
                    f"exposures, 1 = disjoint) over {summ['players_held']} players held; "
                    f"book-weighted field ownership {summ['book_weighted_field_own']:.1f}%.</p>"
                    + table(lev, [("player", "Player", None, "l"), ("position", "Pos", None, "l"),
                                  ("book_pct", "Book", fmt_num(1, pct=True)),
                                  ("field_pct", "Field", fmt_num(1, pct=True)),
                                  ("leverage", "Book − field", fmt_num(1, signed=True)),
                                  ("fpts", "DK pts", fmt_num(1))], max_rows=60))

        body = (header(f"Accuracy · {season}", "How our numbers held up")
                + week_picker(season, week, sch, "/accuracy")
                + "<h2>Projection error by week</h2><p class='sub'>Newest pre-lock batch vs realized DK "
                  "points, skill players projected ≥ 5. 'Both' = players Fantasy Points also priced "
                  "(the fair comparison).</p>" + guarded(projections)
                + "<h2>Ownership calibration</h2><p class='sub'>Fantasy Points projected ownership vs "
                  "realized Millionaire ownership (counted from the contest's lineups); players priced "
                  "and drafted (PREREG-O1 population).</p>" + guarded(ownership)
                + f"<h2>Book leverage · Week {week}</h2>" + guarded(leverage))
        return page("Accuracy", body, "/accuracy")

    @app.get("/arms", response_class=HTMLResponse)
    def arms_page(season: int | None = None, week: int | None = None, kinds: str = "core") -> str:
        season, week, sch = resolve(season, week)
        core = ["pool", "book", "played", "vetted", "shadow", "cash_shadow", "paper"]

        def build() -> str:
            arms = D.fetch_arms(q, season)
            if arms.empty:
                return note("arms_weekly is empty or not created yet: run sql/dashboard/ddl.sql, then "
                            "scripts/publish_dashboard_week.py --apply after each week.")
            a = arms if kinds == "all" else arms[arms.kind.isin(core)]
            cols = [("arm", "Arm", None, "l"), ("kind", "Kind", None, "l"),
                    ("contest_id", "Contest", None, "l"), ("n_lineups", "Lineups"),
                    ("mean_points", "Mean pts", fmt_num(1)), ("best_points", "Best pts", fmt_num(1)),
                    ("best_rank", "Best Milly rank", fmt_num(0)), ("cash_rate", "Cash rate", fmt_num(3)),
                    ("cash_basis", "Cash rate at", None, "l")]
            wk = a[a.week == week].sort_values(["kind", "best_points"], ascending=[True, False])
            # the reviewer (10-05): an arm without a contest is measured at the Millionaire's cash line, not its own
            wk = wk.assign(cash_basis=["≥ Millionaire cash line" if c is None or pd.isna(c) or str(c) == "" else
                                       "its own contest's cash line" for c in wk.contest_id])
            out = f"<h2>Week {week}</h2>" + (table(wk, cols) if len(wk) else note("Nothing published for this week."))
            piv = a.pivot_table(index=["arm", "kind"], columns="week", values="best_points", aggfunc="max")
            rk = a.pivot_table(index=["arm", "kind"], columns="week", values="best_rank", aggfunc="min")
            if not piv.empty:
                piv.columns = [f"W{c} best" for c in piv.columns]
                rk.columns = [f"W{c} rank" for c in rk.columns]
                both = piv.join(rk).reset_index()
                order = [c for w in sorted(a.week.unique()) for c in (f"W{w} best", f"W{w} rank")]
                scols = [("arm", "Arm", None, "l"), ("kind", "Kind", None, "l")] + [
                    (c, c, fmt_num(1) if c.endswith("best") else fmt_num(0)) for c in order if c in both]
                out += "<h2>Season</h2>" + table(both, scols)
            return out

        def stakes() -> str:
            if week is None:
                return note("No week selected.")
            text = cache.get(f"stakes:{season}:{week}", lambda: stake_reader(season, week))
            plan = stake_rows(text)  # type: ignore[arg-type]
            if plan.empty:
                return note(f"No reviewed week inputs (contests.json) for {season} week {week} in "
                            f"private storage.")
            tot = plan[["entries", "keep", "stake"]].sum()
            return (f"<p class='sub'>{len(plan)} contests · {int(tot.entries)} entries · "
                    f"{int(tot.keep)} kept · stake ${tot.stake:,.2f} (fee × entries). Read at request "
                    f"time from private storage; never stored by the dashboard.</p>"
                    + table(plan, [("name", "Label", None, "l"), ("dk_name", "Contest", None, "l"),
                                   ("contest_id", "Id", None, "l"), ("entries", "Entries"),
                                   ("keep", "Keep"), ("fee", "Fee", fmt_num(2)),
                                   ("stake", "Stake", fmt_num(2))]))

        body = (header(f"Arms · {season}", "Every published arm, ranked against the week's Millionaire "
                       "field (best rank = 1 + entries scoring above our best lineup)")
                + week_picker(season, week, sch, "/arms", [
                    select("kinds", "Kinds", [("core", "books & shadows"), ("all", "all incl. uploads/orderings")], kinds)])
                + guarded(build)
                + f"<h2>Stake plan · Week {week}</h2>" + guarded(stakes))
        return page("Arms", body, "/arms")

    @app.get("/milly", response_class=HTMLResponse)
    def milly_page(season: int | None = None, week: int | None = None) -> str:
        season, week, sch = resolve(season, week)

        def season_view() -> str:
            lines = D.fetch_milly_lines(q, season)
            if lines.empty:
                return note("No Millionaire standings imported this season yet.")
            try:
                arms = D.fetch_arms(q, season)
            except Exception:  # noqa: BLE001 -- the published table is optional
                arms = pd.DataFrame()
            try:
                cl = D.fetch_contest_lines(q, season)
            except Exception:  # noqa: BLE001 -- the published table is optional
                cl = pd.DataFrame()
            if not cl.empty:
                pub_lines = cl.assign(contest_id=cl.contest_id.astype(str))[["contest_id", "cash_line"]]
                lines = lines.assign(contest_id=lines.contest_id.astype(str)).merge(
                    pub_lines.rename(columns={"cash_line": "published_cash"}), on="contest_id", how="left")
                lines["cash_line"] = lines.cash_line.fillna(lines.published_cash)
            ovw = M.ours_vs_winner(lines, arms)
            top = D.fetch_milly_top(q, season, None, top_n=1, top_share=0.0)
            slate = D.fetch_milly_slate(q, season, None)
            cons = M.lineup_construction(top, slate, sch)
            win = M.winners(cons)
            ovw = ovw.merge(win[["week", "stack_label", "salary", "dupes", "qb"]], on="week", how="left")
            return table(ovw, [
                ("week", "Wk"), ("n_entries", "Entries", fmt_num(0)), ("winning_score", "Winner", fmt_num(2)),
                ("top_01pct_line", "Top 0.1%", fmt_num(2)), ("top_1pct_line", "Top 1%", fmt_num(2)),
                ("cash_line", "Cash line", fmt_num(2)), ("qb", "Winner QB", None, "l"),
                ("stack_label", "Winner stack", None, "l"), ("salary", "Winner salary", fmt_num(0)),
                ("dupes", "Winner dupes", fmt_num(0)),
                ("our_best", "Our best", fmt_num(2)), ("our_rank", "Our rank", fmt_num(0)),
                ("our_source", "From", None, "l"), ("gap", "Gap to winner", fmt_num(2)),
                ("book_best", "Book best", fmt_num(2)), ("book_rank", "Book rank", fmt_num(0))])

        def week_view() -> str:
            if week is None:
                return note("No week selected.")
            top = D.fetch_milly_top(q, season, week, top_n=TOP_CAP, top_share=0.01)
            if top.empty:
                return note(f"Week {week}'s Millionaire standings are not imported yet.")
            slate = D.fetch_milly_slate(q, season, week)
            own = D.fetch_field_ownership(q, season, week)
            cons = M.lineup_construction(top, slate, sch, own)
            summ = M.construction_summary(cons)
            out = ""
            win = M.winners(cons)
            if len(win):
                w = win.iloc[0]
                players = M.lineup_players(top, w.lineup_key)
                shape = (esc(w.stack_label) if isinstance(w.stack_label, str)
                         else f"stack unknown ({int(w.matched)} of 9 players resolved to the slate)")
                sal = f"salary {w.salary:,.0f}" if pd.notna(w.salary) else "salary unknown"
                own_s = f"ownership sum {w.own_sum:.0f}%" if pd.notna(w.own_sum) else "ownership unknown"
                out += ("<div class='card'><b>Winning lineup</b> · "
                        f"{w.points:.2f} pts · {shape} · {sal} · {own_s} · "
                        f"{int(w.dupes or 1)} identical in the field"
                        "<div class='scroll'><table>" + "".join(
                            f"<tr><td class='l'>{esc(s)}</td><td class='l'>{esc(p)}</td></tr>"
                            for s, p in players) + "</table></div></div>")
            n_entries = int(pd.to_numeric(top.n_entries, errors="coerce").max())
            shown = len(top)
            share = (f"top {shown:,} lineups = {100 * shown / n_entries:.2f}% of {n_entries:,}"
                     if n_entries else f"top {shown:,} lineups")
            if len(summ) and int(summ.iloc[0].n) == 0:
                out += (f"<h2>Top construction ({esc(share)})</h2>"
                        + note(f"No lineup resolved fully to the slate ({int(summ.iloc[0].n_excluded)} "
                               f"excluded): the week's Millionaire has no draft group / salary pull."))
            elif len(summ):
                s = summ.iloc[0]
                out += (f"<h2>Top construction ({esc(share)}; {int(s.n):,} fully resolved, "
                        f"{int(s.n_excluded):,} excluded)</h2><div class='grid'>" + "".join(
                    f"<div class='card stat'><div class='k'>{esc(k)}</div><div class='v'>{v}</div></div>"
                    for k, v in (("QB + 2 or more", f"{100 * s.share_qb_stack2:.0f}%"),
                                 ("With a bring-back", f"{100 * s.share_bring_back:.0f}%"),
                                 ("Mean salary", f"{s.mean_salary:,.0f}"),
                                 ("Mean ownership sum", f"{s.mean_own_sum:.0f}%"),
                                 ("Median dupes", f"{s.median_dupes:.0f}"),
                                 ("Most common shape", f"{esc(s.top_shape)} ({100 * s.top_shape_share:.0f}%)")))
                    + "</div>")
            out += "<h2>Top 10</h2>" + table(cons.head(10), [
                ("rank", "Rank", fmt_num(0)), ("points", "Pts", fmt_num(2)), ("qb", "QB", None, "l"),
                ("stack_label", "Stack", None, "l"), ("n_games", "Games"), ("salary", "Salary", fmt_num(0)),
                ("own_sum", "Own sum", fmt_num(0, pct=True)), ("dupes", "Dupes", fmt_num(0))])
            mo = M.most_owned(own, 12)
            out += "<h2>Most owned in the field</h2>" + table(mo, [
                ("display_name", "Player", None, "l"), ("own", "Owned", fmt_num(1, pct=True)),
                ("fpts", "DK pts", fmt_num(1))])
            return out

        body = (header(f"Millionaire · {season}", "The main-slate Millionaire each week: lines, winners "
                       "and how the top of the field was built (lineups and points only). 'Played' = the "
                       "upload files after R4/swap; 'Book' = the pre-R4 union book.csv. Cash line: "
                       "standings payouts, else the published contest_lines (contest-details ladder)")
                + week_picker(season, week, sch, "/milly")
                + "<h2>Season</h2>" + guarded(season_view)
                + f"<h2>Week {week}</h2>" + guarded(week_view))
        return page("Milly", body, "/milly")

    @app.get("/insights", response_class=HTMLResponse)
    def insights_page(season: int | None = None, week: int | None = None) -> str:
        season, week, sch = resolve(season, week)
        pct = fmt_num(1, pct=True)

        def ins(name: str) -> pd.DataFrame:
            df = D.fetch_insight(q, name, season)
            return df[df.week == week] if (week is not None and not df.empty and "week" in df) else df

        def winners_vs_field() -> str:
            df = ins("winners_vs_field")
            if df.empty:
                return note("Needs Fantasy Points ownership and the week's Millionaire standings.")
            book = ins("book_fp")
            df = pd.concat([df, book], ignore_index=True) if not book.empty else df
            return table(df, [("grp", "Group", None, "l"), ("n", "Lineups", fmt_num(0)),
                              ("own_sum", "FP own sum", pct), ("proj_sum", "FP proj sum", fmt_num(1)),
                              ("unmatched", "Unmatched slots", fmt_num(2))])

        def leverage_paid() -> str:
            df = ins("leverage_paid")
            if df.empty:
                return note("No qualifying players (or no FP ownership / standings for this week).")
            return table(df, [("category", "", None, "l"), ("player", "Player", None, "l"),
                              ("fp_own", "FP proj own", pct), ("realized", "Realized", pct),
                              ("top1_rate", "In top 1%", pct), ("fpts", "DK pts", fmt_num(1))])

        def stacks() -> str:
            df = ins("stacks")
            if df.empty:
                return note("No top-1% stacks for this week yet.")
            df["team_d"] = df.team.map(display_team)
            return table(df, [("qb", "QB", None, "l"), ("catcher", "Pass catcher", None, "l"),
                              ("team_d", "Team", None, "l"), ("lineups", "Top-1% lineups"),
                              ("share_top1", "Share of top 1%", pct),
                              ("pair_fp_own", "Pair FP own", pct)])

        def repeat_finishers() -> str:
            df = D.fetch_insight(q, "repeat_finishers", season)   # season-wide, no week filter
            if df.empty:
                return note("No Millionaire standings with user names imported this season yet.")
            return table(df, [("username", "User", None, "l"), ("entries", "Entries", fmt_num(0)),
                              ("weeks", "Weeks"), ("top1_weeks", "Top-1% weeks"),
                              ("top1_lineups", "Top-1% lineups", fmt_num(0)),
                              ("top01_lineups", "Top-0.1% lineups", fmt_num(0)),
                              ("best_rank", "Best rank", fmt_num(0)), ("top1_rate", "Top-1% rate", pct),
                              ("top_qb", "Most-used QB in top 1%", None, "l"),
                              ("top_qb_lineups", "QB lineups", fmt_num(0))])

        def disagreements() -> str:
            ours, fp, _ = D.fetch_accuracy_inputs(q, season)
            summ, players = D.projection_disagreements(ours, fp)
            if summ.empty:
                return note("No scored week where we and Fantasy Points differed by 4+ points yet.")
            if week is not None:
                players = players[players.week == week]
            return (table(summ, [("week", "Wk"), ("position", "Pos", None, "l"), ("n", "Players"),
                                 ("ours_closer", "Ours closer"), ("fp_closer", "FP closer"),
                                 ("mae_ours", "MAE ours", fmt_num(2)), ("mae_fp", "MAE FP", fmt_num(2))])
                    + f"<h3>Week {week}</h3>"
                    + table(players, [("display_name", "Player", None, "l"), ("position", "Pos", None, "l"),
                                      ("proj_points", "Ours", fmt_num(1)), ("fantasy_points", "FP", fmt_num(1)),
                                      ("dk_points", "Actual", fmt_num(1)), ("gap", "Ours − FP", fmt_num(1, signed=True)),
                                      ("closer", "Closer", None, "l")], max_rows=40))

        def book_vs_top() -> str:
            df = ins("book_vs_top")
            if df.empty:
                return note("Needs the published book exposure and the week's Millionaire standings.")
            return table(df, [("player", "Player", None, "l"), ("position", "Pos", None, "l"),
                              ("book_pct", "Our book", pct), ("top01_pct", "Top 0.1%", pct),
                              ("field_pct", "Field", pct), ("fp_own", "FP proj own", pct),
                              ("divergence", "Book − top 0.1%", fmt_num(1, signed=True))], max_rows=40)

        body = (header(f"Insights · Week {week}", "Fantasy Points' pre-lock view against what won the "
                       "Millionaire, and against us")
                + week_picker(season, week, sch, "/insights")
                + "<h2>1 · Winners vs the projected field</h2><p class='sub'>Mean per-lineup sum of FP "
                  "projected ownership and projection: do winners skew chalk or contrarian?</p>"
                + guarded(winners_vs_field)
                + "<h2>2 · Leverage that paid, chalk that busted</h2><p class='sub'>Under-owned vs FP "
                  "(realized ≤ 0.6×FP, ≥ 3 pts below) and over-represented in the top 1% (≥ 1.5× field "
                  "rate); or FP ≥ 15% and at most half the field rate in the top 1%.</p>"
                + guarded(leverage_paid)
                + "<h2>3 · QB + pass-catcher stacks in the top 1%</h2>" + guarded(stacks)
                + f"<h2>4 · Repeat top finishers by user name · {season}</h2><p class='sub'>Season-wide "
                  "over the Millionaires: DraftKings user names (entry name without its (k/n) "
                  "counter) with a top-1% lineup, most top-1% weeks first; cuts by rank over the "
                  "whole field, ties inside; top 50.</p>"
                + guarded(repeat_finishers)
                + "<h2>5 · Ours vs FP vs actual where we disagreed by 4+ points</h2>"
                + guarded(disagreements)
                + "<h2>6 · Our book against the top 0.1%</h2>" + guarded(book_vs_top))
        return page("Insights", body, "/insights")

    return app
