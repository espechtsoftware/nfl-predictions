"""2025 Millionaire winners (reports/2025-milly-winners.csv): the winner's QB game ranked by total (nflverse total_line,
closing) among that week's Sunday main-slate games (Sunday, kickoff before 17:00 ET). Reads BigQuery; prints the table."""
import pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings as s
w = pd.read_csv("reports/2025-milly-winners.csv")
sch = query_df(f"""SELECT week, game_id, home_team, away_team, total_line, gameday, gametime, weekday FROM `{s.raw}.schedules`
                   WHERE season = 2025 AND game_type = 'REG'""")
sch = sch[(sch.weekday == "Sunday") & (sch.gametime.astype(str) < "17:00")]
ro = query_df(f"""SELECT DISTINCT week, team, full_name, position FROM `{s.raw}.rosters_weekly` WHERE season = 2025 AND position = 'QB'""")
rows = []
for r in w.itertuples():
    g = sch[sch.week == r.week].copy(); q = ro[(ro.week == r.week) & (ro.full_name == r.qb_name)]
    if q.empty or g.empty:
        rows.append(dict(week=r.week, found=False)); continue
    t = q.team.iloc[0]; gg = g[(g.home_team == t) | (g.away_team == t)]
    if gg.empty:
        rows.append(dict(week=r.week, found=False)); continue
    g["rk"] = g.total_line.rank(method="first"); n = len(g); rk = float(g.loc[gg.index[0], "rk"])
    rows.append(dict(week=r.week, found=True, games=n, total=float(gg.total_line.iloc[0]), total_rank_from_low=int(rk),
                     third="bottom" if rk <= n / 3 else ("top" if rk > 2 * n / 3 else "middle"),
                     stack_players=int(r.stack_players), sub10=int(r.sub10_count)))
print(pd.DataFrame(rows).to_string(index=False))
