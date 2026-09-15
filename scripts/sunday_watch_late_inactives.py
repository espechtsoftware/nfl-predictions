"""Poll DraftKings' public draftables for the week's draft group; print as soon as any player in the entered files'
late-afternoon game slots is marked O/OUT/IR/D, and exit when the first O/OUT/IR appears or at WATCH_END_UTC.
Generalised from the Week-1 watcher.  Reads WEEK/GROUP/LIVE_DIR/OUT/LATE_CUTOFF_UTC/WATCH_END_UTC from the
environment (scripts/week_env.sh); the entered lineups are the ENTER/*.csv files (draftable ids) unless --entered
points elsewhere.  Rule 2 of the operating handoff: a flagged player is a CANDIDATE for a swap, decided by his live
DK status, never by this script."""
import argparse, csv, datetime as dt, glob, os, pathlib, sys, time
import pandas as pd

sys.path.insert(0, os.environ.get("PROD", "/home/erich/projects/nfl-predictions") + "/src")
from nfl_dfs.ingest.dk_client import fetch_draftables  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--entered", default=os.environ["OUT"] + "/ENTER/ENTER-*-entries-KEEP-first-*.csv"); a = ap.parse_args()
group = int(os.environ["GROUP"]); live = pathlib.Path(os.environ["LIVE_DIR"])
late_cutoff = pd.Timestamp(os.environ["LATE_CUTOFF_UTC"]); end = pd.Timestamp(os.environ["WATCH_END_UTC"]).to_pydatetime()
run = sorted(d for d in live.iterdir() if d.is_dir() and (d / "frame.parquet").exists())[-1]
f = pd.read_parquet(run / "frame.parquet"); f["dd"] = f.dk_draftable_id.astype(str); f["start"] = pd.to_datetime(f.game_start, utc=True, errors="coerce")
late = set(f[f.start > late_cutoff].dd); name = dict(zip(f.dd, f.display_name))
entered = set()
for p in glob.glob(a.entered):
    for r in list(csv.reader(open(p)))[1:]:
        entered.update(x for x in r if x in late)
print(f"watching {len(entered)} late-game players across {len(glob.glob(a.entered))} entered files (frame {run.name}, group {group})", flush=True)
def poll():
    d = pd.DataFrame([{"dd": str(x.get("draftableId")), "status": x.get("status")} for x in fetch_draftables(group).get("draftables", [])])
    return d, set(d[d.status.isin(["O", "OUT", "IR", "D"])].dd) & entered
d, seen = poll(); print("already flagged at start:", [f"{name[x]} ({d[d.dd == x].status.iloc[0]})" for x in seen], flush=True)
while dt.datetime.now(dt.UTC) < end:
    try:
        d, out = poll(); new = out - seen
        if new:
            print(f"{dt.datetime.now(dt.UTC):%H:%M}Z LATE-GAME STATUS CHANGE: " + ", ".join(f"{name[x]} ({d[d.dd == x].status.iloc[0]})" for x in new), flush=True); seen |= new
            if any(d[d.dd == x].status.iloc[0] in ("O", "OUT", "IR") for x in new):
                break
    except Exception as e:
        print("poll error", e, flush=True)
    time.sleep(240)
print(f"{dt.datetime.now(dt.UTC):%H:%M}Z watcher exit; flagged so far: {[name[x] for x in seen]}")
