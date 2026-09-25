"""Fetch every input the 2026-09-25 outside-the-box analyses use, into OUT (outside the repo).

Sources: nflverse releases (schedules with closing lines, weekly player stats, PFR snap counts), Fantasy Football
Calculator preseason ADP, and LineStar's public GetSalariesV5 endpoint -- the same endpoint and politeness rules as
src/nfl_dfs/ingest/linestar_backfill.py (one pass, 1.2 s between calls, no retries). LineStar data is third-party:
never commit it; only aggregate statistics go into reports.

usage: python fetch_public_inputs.py OUT
"""
import json, os, re, sys, time
import requests

OUT = sys.argv[1]
os.makedirs(os.path.join(OUT, "linestar"), exist_ok=True)
NV = "https://github.com/nflverse/nflverse-data/releases/download"
FILES = {"games.csv": f"{NV}/schedules/games.csv", "ps_all.parquet": f"{NV}/player_stats/player_stats.parquet"}
FILES.update({f"ps_{y}.parquet": f"{NV}/stats_player/stats_player_week_{y}.parquet" for y in (2025, 2026)})
FILES.update({f"snaps_{y}.parquet": f"{NV}/snap_counts/snap_counts_{y}.parquet" for y in range(2018, 2026)})
FILES.update({f"adp_{y}.json": f"https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={y}&position=all"
              for y in (2022, 2023, 2024, 2025)})
s = requests.Session()
for name, url in FILES.items():
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        r = s.get(url, timeout=120); r.raise_for_status(); open(path, "wb").write(r.content)

API = "https://www.linestarapp.com/DesktopModules/DailyFantasyApi/API/Fantasy/GetSalariesV5?sport=1&site=1&periodId={pid}"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research"}
p0 = s.get(API.format(pid=0), headers=HEADERS, timeout=30).json()
pmap = {}
for p in p0["Periods"]:
    m = re.match(r"^Week (\d+), (\d{4})$", p.get("Name", ""))
    if m and (2022 <= int(m.group(2)) <= 2025 or (int(m.group(2)) == 2026 and int(m.group(1)) in (1, 2))):
        pmap[int(p["Id"])] = (int(m.group(2)), int(m.group(1)))
json.dump({str(k): v for k, v in pmap.items()}, open(os.path.join(OUT, "linestar", "pmap.json"), "w"))
for pid in sorted(pmap):
    path = os.path.join(OUT, "linestar", f"p{pid}.json")
    if os.path.exists(path):
        continue
    time.sleep(1.2)
    r = s.get(API.format(pid=pid), headers=HEADERS, timeout=30); r.raise_for_status()
    json.dump(r.json(), open(path, "w"))
print(f"inputs in {OUT}: {len(FILES)} public files, {len(pmap)} LineStar periods")
