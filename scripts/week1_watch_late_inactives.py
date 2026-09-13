"""Poll DraftKings' public draftables for draft group 151307; exit (and print) as soon as any player in the entered book's
3:25 CT game slots is marked O/OUT/IR, or at 20:25Z (3:25 CT)."""
import csv, glob, time, pathlib, datetime as dt, pandas as pd, sys
sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
from nfl_dfs.ingest.dk_client import fetch_draftables
L = pathlib.Path("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01"); run = sorted([d for d in L.iterdir() if d.is_dir() and (d / "frame.parquet").exists()])[-1]
f = pd.read_parquet(run / "frame.parquet"); f["dd"] = f.dk_draftable_id.astype(str); f["start"] = pd.to_datetime(f.game_start, utc=True, errors="coerce")
late = set(f[f.start > pd.Timestamp("2026-09-13 18:30:00+00:00")].dd); name = dict(zip(f.dd, f.display_name))
entered = set()
for p in glob.glob("/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912/reports/week1-entered-book-candidates/entered-candidate-v4b-*.csv") + glob.glob("/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912/reports/week1-entered-book-candidates/entered-candidate-v6b-*.csv"):
    for r in list(csv.reader(open(p)))[1:]: entered.update(x for x in r[1:] if x in late)
print(f"watching {len(entered)} late-game players in the entered candidates", flush=True)
seen = set(pd.DataFrame([{"dd": str(x.get("draftableId")), "status": x.get("status")} for x in fetch_draftables(151307).get("draftables", [])]).query("status in [\"O\",\"OUT\",\"IR\",\"D\"]").dd) & entered; print("already flagged at start:", [name[x] for x in seen], flush=True)
while dt.datetime.now(dt.UTC) < dt.datetime(2026, 9, 13, 20, 25, tzinfo=dt.UTC):
    try:
        d = pd.DataFrame([{"dd": str(x.get("draftableId")), "status": x.get("status")} for x in fetch_draftables(151307).get("draftables", [])])
        out = set(d[d.status.isin(["O", "OUT", "IR", "D"])].dd) & entered
        new = out - seen
        if new:
            print(f"{dt.datetime.now(dt.UTC):%H:%M}Z LATE-GAME STATUS CHANGE: " + ", ".join(f"{name[x]} ({d[d.dd==x].status.iloc[0]})" for x in new), flush=True); seen |= new
            if any(d[d.dd == x].status.iloc[0] in ("O", "OUT", "IR") for x in new): break
    except Exception as e:
        print("poll error", e, flush=True)
    time.sleep(240)
print(f"{dt.datetime.now(dt.UTC):%H:%M}Z watcher exit; flagged so far: {[name[x] for x in seen]}")
