#!/usr/bin/env python3
"""apply_swaps.py v1.1 -- apply one-for-one player swaps to an all-lineups upload CSV (draftable-id cells) and write a new upload.

  apply_swaps.py UPLOAD_CSV RUN_DIR OUT_CSV --swap ROW:OUT_DD:IN_DD [--swap ...] [--group 153428] [--no-fresh-dk] [--now ISO8601]
                 [--save-fresh PATH] [--fresh-file PATH]

ROW is the 1-based lineup row in UPLOAD_CSV order (row 1 = the Millionaire entry); OUT_DD / IN_DD are dk_draftable_ids,
i.e. the cells of the upload.  Checked before anything is written:
  * the row holds OUT_DD in exactly one slot; IN_DD is legal for that slot (FLEX takes RB/WR/TE) and is not already in the row;
  * neither player's game has started (a locked cell cannot be edited on DraftKings);
  * IN_DD is PRESENT in the FRESH DraftKings draftables (public API, the late-inactives watcher's call) and is not
    O/OUT/IR/D there -- a player missing from the fresh feed is rejected (fail closed; v1.1, lab review finding);
    --save-fresh writes the fetched feed to PATH and --fresh-file reads a saved feed instead of fetching, so a swap can be
    reproduced from its receipt; --no-fresh-dk falls back to the frame's captured status and the receipt says so;
  * the new roster passes nfl2.validator.validate_roster (9 players, slot counts, cap 50000, >= 2 games, <= 8 per team, no duplicates).
Only the requested cells change; every other line is byte-identical (asserted).  Nothing under ENTER changes -- publish with
  relayout_enter.sh OUT_CSV OUT_DIR TAG
afterwards; the DK-entries watcher then refills the operator's export.  A receipt is written next to OUT_CSV (<OUT_CSV>.swap.json).
"""
import argparse, csv, datetime as dt, hashlib, json, os, pathlib, sys
import pandas as pd

SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
ALLOWED = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "DST": {"DST"}}
BAD = {"O", "OUT", "IR", "D"}

ap = argparse.ArgumentParser()
ap.add_argument("upload"); ap.add_argument("run_dir"); ap.add_argument("out")
ap.add_argument("--swap", action="append", required=True, help="ROW:OUT_DD:IN_DD (repeatable)")
ap.add_argument("--group", type=int, default=int(os.environ.get("GROUP", "153428")))
ap.add_argument("--no-fresh-dk", action="store_true")
ap.add_argument("--now", default=None, help="override the clock (tests only)")
ap.add_argument("--save-fresh", default=None, help="write the fetched DraftKings draftables JSON here (receipt records its sha256)")
ap.add_argument("--fresh-file", default=None, help="read the DraftKings draftables JSON from here instead of fetching")
a = ap.parse_args()
now = pd.Timestamp(a.now) if a.now else pd.Timestamp.now(tz="UTC")
if now.tzinfo is None: now = now.tz_localize("UTC")

sys.path.insert(0, os.environ.get("CLONE", "/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c") + "/src")
from nfl2.validator import validate_roster  # noqa: E402

raw = pathlib.Path(a.upload).read_bytes()
term = b"\r\n" if b"\r\n" in raw else b"\n"
lines = raw.decode("utf-8").split(term.decode())
if lines and lines[-1] == "": lines = lines[:-1]
rows = [l.split(",") for l in lines]
if rows[0] != SLOTS: sys.exit(f"header {rows[0]} != {SLOTS}")
body = rows[1:]
if any(len(r) != 9 for r in body): sys.exit("a row does not have 9 cells")

f = pd.read_parquet(pathlib.Path(a.run_dir) / "frame.parquet",
                    columns=["dk_draftable_id", "dk_player_id", "name", "pos", "salary", "team", "opp", "game_id", "game_start", "status"])
f["dd"] = f.dk_draftable_id.astype(int).astype(str)
f["start"] = pd.to_datetime(f.game_start, utc=True, errors="coerce")
by = f.set_index("dd")
name, pos, team, opp = by.name.astype(str).to_dict(), by.pos.astype(str).to_dict(), by.team.astype(str).to_dict(), by.opp.astype(str).to_dict()
salary = pd.to_numeric(by.salary, errors="coerce").fillna(0).astype(int).to_dict()
game, start, fstatus = by.game_id.astype(str).to_dict(), by.start.to_dict(), by.status.astype(str).to_dict()

fresh, fresh_source = {}, "frame status (captured at build; --no-fresh-dk)"
if not a.no_fresh_dk:
    sys.path.insert(0, os.environ.get("PROD", "/home/erich/projects/nfl-predictions") + "/src")
    from nfl_dfs.ingest.dk_client import fetch_draftables  # noqa: E402
    if a.fresh_file:
        feed = json.loads(pathlib.Path(a.fresh_file).read_text()); feed_note = f"saved feed {a.fresh_file}"
    else:
        feed = fetch_draftables(a.group); feed_note = f"fetched {now.isoformat()}"
    if a.save_fresh:
        pathlib.Path(a.save_fresh).write_text(json.dumps(feed) + "\n")
    feed_sha = hashlib.sha256(json.dumps(feed).encode()).hexdigest()
    d = pd.DataFrame([{"dd": str(x.get("draftableId")), "status": str(x.get("status") or "")}
                      for x in feed.get("draftables", [])])   # the late-inactives watcher's parse
    if d.empty: sys.exit("fresh DraftKings draftables came back empty; rerun with --no-fresh-dk only if the operator accepts the captured status")
    fresh = dict(zip(d.dd, d.status.str.upper()))
    fresh_source = f"fresh DraftKings draftables (group {a.group}, {len(fresh)} rows, {feed_note}, feed sha256 {feed_sha[:16]})"

def status_of(dd):
    s = fresh.get(dd) if fresh else fstatus.get(dd)
    return (s or "").upper().replace("NONE", "").strip()

receipt = {"tool": "apply_swaps.py v1.1", "input": a.upload, "input_sha256": hashlib.sha256(raw).hexdigest(), "run_dir": a.run_dir,
           "status_source": fresh_source, "now_utc": now.isoformat(), "swaps": []}
problems = []
for spec in a.swap:
    try: r, out_dd, in_dd = spec.split(":"); r = int(r)
    except ValueError: sys.exit(f"bad --swap {spec!r}; want ROW:OUT_DD:IN_DD")
    if not 1 <= r <= len(body): problems.append(f"{spec}: row {r} outside 1..{len(body)}"); continue
    row = body[r - 1]
    hits = [i for i, c in enumerate(row) if c == out_dd]
    if len(hits) != 1: problems.append(f"{spec}: row {r} holds {out_dd} in {len(hits)} slots"); continue
    i = hits[0]; slot = SLOTS[i]
    for dd, what in ((out_dd, "out"), (in_dd, "in")):
        if dd not in pos: problems.append(f"{spec}: {what} player {dd} not in the frame"); break
    else:
        if pos[in_dd] not in ALLOWED[slot]: problems.append(f"{spec}: {name[in_dd]} is {pos[in_dd]}, slot {slot} takes {sorted(ALLOWED[slot])}")
        if in_dd in row: problems.append(f"{spec}: {name[in_dd]} is already in row {r}")
        for dd, what in ((out_dd, "out"), (in_dd, "in")):
            st = start.get(dd)
            if st is None or pd.isna(st): problems.append(f"{spec}: {what} player {name[dd]} has no game start")
            elif st <= now: problems.append(f"{spec}: {what} player {name[dd]} game started {st.isoformat()} (locked cell)")
        present = (in_dd in fresh) if fresh else (in_dd in fstatus)
        if not present: problems.append(f"{spec}: {name[in_dd]} ({in_dd}) is NOT PRESENT in the {'fresh DraftKings feed' if fresh else 'frame status map'}; refusing (fail closed)")
        elif status_of(in_dd) in BAD: problems.append(f"{spec}: {name[in_dd]} is {status_of(in_dd)} per {fresh_source}")
        if problems: continue
        new = list(row); new[i] = in_dd
        v = validate_roster(new, pos, team, opp, salary, game=game)
        if v: problems.append(f"{spec}: validator: {v}"); continue
        receipt["swaps"].append({"row": r, "slot": slot, "slot_index": i,
                                 "out": {"dd": out_dd, "name": name[out_dd], "pos": pos[out_dd], "salary": salary[out_dd], "team": team[out_dd], "status": status_of(out_dd) or "none"},
                                 "in": {"dd": in_dd, "name": name[in_dd], "pos": pos[in_dd], "salary": salary[in_dd], "team": team[in_dd], "status": status_of(in_dd) or "none"},
                                 "salary_before": sum(salary[c] for c in row), "salary_after": sum(salary[c] for c in new)})
        body[r - 1] = new
if problems:
    print("APPLY-SWAPS FAILED; nothing written:"); [print("  " + p) for p in problems]; sys.exit(2)

out_text = term.decode().join([",".join(SLOTS)] + [",".join(r) for r in body]) + term.decode()
changed = {s["row"] for s in receipt["swaps"]}
old_lines = raw.decode("utf-8").split(term.decode()); new_lines = out_text.split(term.decode())
assert len(old_lines) == len(new_lines), "line count changed"
for k, (o, n) in enumerate(zip(old_lines, new_lines)):
    if k == 0 or (k - 1 + 1) not in changed: assert o == n, f"line {k} changed unexpectedly"
pathlib.Path(a.out).write_bytes(out_text.encode("utf-8"))
receipt["output"] = a.out; receipt["output_sha256"] = hashlib.sha256(out_text.encode()).hexdigest(); receipt["rows"] = len(body)
pathlib.Path(a.out + ".swap.json").write_text(json.dumps(receipt, indent=2) + "\n")
for s in receipt["swaps"]:
    print(f"row {s['row']:3d} {s['slot']:<4} OUT {s['out']['name']} ({s['out']['team']} {s['out']['pos']} ${s['out']['salary']:,} {s['out']['status']}) -> IN {s['in']['name']} ({s['in']['team']} {s['in']['pos']} ${s['in']['salary']:,} {s['in']['status']}); salary {s['salary_before']:,} -> {s['salary_after']:,}")
print(f"wrote {a.out} ({len(body)} rows, {len(changed)} changed) sha256 {receipt['output_sha256'][:16]}; status source: {fresh_source}")
