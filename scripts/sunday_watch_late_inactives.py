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
OUT_STATUSES = ("O", "OUT", "IR")       # will not play: a swap CANDIDATE
WATCH_STATUSES = OUT_STATUSES + ("D",)  # D is a warning, not yet a swap


def poll():
    """Return the raw frame and {draftable id -> status} for every WATCHED entered player.

    Defect found 2026-09-18, two days before Week 2.  This used to return only the SET of
    flagged ids, and the loop alerted on `out - seen` with `seen |= new`.  A player already
    listed D at startup entered `seen` and stayed there, so when he later turned OUT the set
    difference was empty: no alert, no break.  Doubtful-to-out is the single most important
    transition on a Sunday and it was the one case guaranteed to be silent.  Track the
    STATUS per player rather than membership, and alert on any change.
    """
    d = pd.DataFrame([{"dd": str(x.get("draftableId")), "status": x.get("status")}
                      for x in fetch_draftables(group).get("draftables", [])])
    flagged = d[d.status.isin(WATCH_STATUSES) & d.dd.isin(entered)]
    return d, dict(zip(flagged.dd, flagged.status))


d, state = poll()
print("already flagged at start: "
      + (", ".join(f"{name[x]} ({st})" for x, st in sorted(state.items())) or "(none)"), flush=True)
if any(st in OUT_STATUSES for st in state.values()):
    print("NOTE: a player is ALREADY ruled out at startup -- treat as a swap candidate now. "
          "The watcher keeps running so later transitions are still caught.", flush=True)
while dt.datetime.now(dt.UTC) < end:
    try:
        d, now = poll()
        changed = {x: st for x, st in now.items() if state.get(x) != st}
        if changed:
            print(f"{dt.datetime.now(dt.UTC):%H:%M}Z LATE-GAME STATUS CHANGE: "
                  + ", ".join(f"{name[x]} ({state.get(x, '-')} -> {st})"
                              for x, st in sorted(changed.items())), flush=True)
        escalated = {x: st for x, st in changed.items()
                     if st in OUT_STATUSES and state.get(x) not in OUT_STATUSES}
        state.update(now)
        if escalated:
            print(f"{dt.datetime.now(dt.UTC):%H:%M}Z RULED OUT: "
                  + ", ".join(f"{name[x]} ({st})" for x, st in sorted(escalated.items()))
                  + "  -- swap candidate(s); decide on live DK status, not on this script.", flush=True)
            break
    except Exception as e:
        print("poll error", e, flush=True)
    time.sleep(240)
print(f"{dt.datetime.now(dt.UTC):%H:%M}Z watcher exit; final flagged state: "
      + (", ".join(f"{name[x]} ({st})" for x, st in sorted(state.items())) or "(none)"))
