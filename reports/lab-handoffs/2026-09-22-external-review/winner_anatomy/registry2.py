import re, numpy as np, pandas as pd
from pathlib import Path
R = str(Path(__file__).resolve().parents[3])          # reports/ (winner registry CSVs)
a = pd.read_csv(f"{R}/milly-winners-2019-2023-2024.csv").rename(columns={"ownership_pct": "own", "fantasy_points": "pts"})
a["own"] = a.own.astype(str).str.rstrip("%").astype(float)
b = pd.read_csv(f"{R}/2025-milly-rosters.csv").rename(columns={"own_pct": "own"}); b["season"] = 2025
w = pd.concat([a, b[["season", "week", "position", "player", "salary", "own", "pts"]]], ignore_index=True)
w["slot"] = w.position
def last(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()).strip()
    return re.sub(r"[^a-z]", "", s.split(" ", 1)[-1] if " " in s else s)
def first(s): return re.sub(r"[^a-z]", "", str(s).lower())[:1]
ws = pd.read_csv("ws_hist.csv"); ws["last"] = ws.player_display_name.map(last); ws["fi"] = ws.player_display_name.map(first)
w["last"] = w.player.map(last); w["fi"] = w.player.map(first)
NICK = {"cardinals":"ARI","falcons":"ATL","ravens":"BAL","bills":"BUF","panthers":"CAR","bears":"CHI","bengals":"CIN","browns":"CLE",
 "cowboys":"DAL","broncos":"DEN","lions":"DET","packers":"GB","texans":"HOU","colts":"IND","jaguars":"JAX","chiefs":"KC","raiders":"LV",
 "chargers":"LAC","rams":"LA","dolphins":"MIA","vikings":"MIN","patriots":"NE","saints":"NO","giants":"NYG","jets":"NYJ","eagles":"PHI",
 "steelers":"PIT","49ers":"SF","seahawks":"SEA","buccaneers":"TB","titans":"TEN","commanders":"WAS","washington":"WAS","redskins":"WAS","footballteam":"WAS"}
sch = pd.read_csv("sched_hist.csv")
opp = {}
for g in sch.itertuples():
    opp[(g.season, g.week, g.home_team)] = (g.away_team, g.total_line, g.gametime); opp[(g.season, g.week, g.away_team)] = (g.home_team, g.total_line, g.gametime)
teams = []
for r in w.itertuples():
    if r.slot == "DST":
        k = re.sub(r"[^a-z0-9]", "", str(r.player).lower()); t = NICK.get(k)
        if t == "LA" and (r.season, r.week, "LA") not in opp: t = "LAR"
        if t == "LV" and (r.season, r.week, "LV") not in opp: t = "OAK"
        teams.append((t, "DST")); continue
    c = ws[(ws.season == r.season) & (ws.week == r.week) & (ws["last"] == r.last)]
    if len(c) > 1: c = c[c.fi == r.fi] if (c.fi == r.fi).any() else c
    if len(c) > 1: c = c.iloc[[np.argmin(np.abs(c.dk.to_numpy() - r.pts))]]
    if len(c) == 1 and abs(c.dk.iloc[0] - r.pts) < 1.0:
        teams.append((c.team.iloc[0], c.position.iloc[0]))
    else:
        teams.append((None, None))
w["team"] = [t for t, _ in teams]; w["pos"] = [p for _, p in teams]
w.loc[w.slot == "DST", "pos"] = "DST"
w["pos"] = w.pos.replace({"FB": "RB"})
print("matched", w.team.notna().mean().round(3), "unmatched by slot", w[w.team.isna()].slot.value_counts().to_dict())
w["opp"] = [opp.get((s, k, t), (None,))[0] for s, k, t in zip(w.season, w.week, w.team)]
w["gtime"] = [opp.get((s, k, t), (None, None, None))[2] for s, k, t in zip(w.season, w.week, w.team)]
w.to_csv("registry_teams.csv", index=False)
