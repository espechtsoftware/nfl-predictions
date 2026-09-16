"""Fill a DraftKings entries export (DKEntries.csv: Entry ID, Contest Name, Contest ID, Entry Fee, QB..DST, ...) with the
per-contest keep-first lineups from /home/erich/week1-sunday/ENTER/, preserving every other column verbatim.
Entries of each contest are filled in file order: the first rows receive the KEEPERS, the rest the fill lineups (to be
withdrawn).  Writes <out_dir>/DKEntries-FILLED-keepers-first.csv plus WITHDRAW-these-entry-ids.txt and KEEP-these-entry-ids.txt.
Usage: python fill_dk_entries.py DKEntries.csv [--contests contests.json] [--enter-dir DIR] [--out-dir DIR] [--frame frame.parquet]
(2026-09-16: the contest map comes from the week's contests.json — name, contest_id, entries, keep — when --contests or
$CONTESTS_JSON is given; the Week-1 map below is the fallback.)"""
import argparse, csv, glob, json, os, pathlib, sys
import pandas as pd

CONTESTS = {  # contest id -> (per-contest keep-first file pattern, keepers)
    "193028206": ("ENTER-milly-193028206-*-entries-KEEP-first-*.csv", 19),
    "193028208": ("ENTER-playaction-193028208-*-entries-KEEP-first-*.csv", 7),
    "194478066": ("ENTER-ffwc-q6-194478066-*-entries-KEEP-first-*.csv", 1),
    "194478065": ("ENTER-ffwc-q5-194478065-*-entries-KEEP-first-*.csv", 3),
}
SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("template"); ap.add_argument("--enter-dir", default="/home/erich/week1-sunday/ENTER"); ap.add_argument("--out-dir", default="/home/erich/week1-sunday/ENTER")
    ap.add_argument("--frame", default=None, help="frame.parquet for 'Name (ID)' cells; bare IDs if absent")
    ap.add_argument("--contests", default=os.environ.get("CONTESTS_JSON"), help="the week's contests.json (name, contest_id, entries, keep)"); a = ap.parse_args()
    global CONTESTS
    if a.contests:
        CONTESTS = {str(c["contest_id"]): (f"ENTER-{c['name']}-{c['contest_id']}-*-entries-KEEP-first-*.csv", int(c["keep"])) for c in json.load(open(a.contests))}
    raw = pathlib.Path(a.template).read_bytes().decode("utf-8-sig"); rows = list(csv.reader(raw.splitlines()))
    hdr = rows[0]; low = [h.strip().lower() for h in hdr]
    try:
        i_entry = low.index("entry id"); i_cid = low.index("contest id"); i_qb = low.index("qb")
    except ValueError:
        sys.exit(f"not a DraftKings entries export: header {hdr[:6]}")
    assert [h.strip().upper() for h in hdr[i_qb:i_qb + 9]] == SLOTS, f"lineup columns not QB..DST at {i_qb}: {hdr[i_qb:i_qb + 9]}"
    names = {}
    if a.frame:
        f = pd.read_parquet(a.frame); names = dict(zip(f.dk_draftable_id.astype(str), f.display_name.astype(str)))
    cell = (lambda pid: f"{names[pid]} ({pid})" if pid in names else pid)
    lineups = {}
    for cid, (pat, k) in CONTESTS.items():
        fs = sorted(glob.glob(str(pathlib.Path(a.enter_dir) / pat)))
        if fs: lineups[cid] = (pd.read_csv(fs[-1], dtype=str).values.tolist(), k, fs[-1])
    by_contest = {}
    for r_i, r in enumerate(rows[1:], start=1):
        if len(r) > i_cid and r[i_entry].strip() and r[i_cid].strip() in CONTESTS: by_contest.setdefault(r[i_cid].strip(), []).append(r_i)
    keep_ids, withdraw_ids, summary = [], [], []
    for cid, idxs in by_contest.items():
        if cid not in lineups: summary.append(f"contest {cid}: {len(idxs)} entries in the export but NO lineup file in {a.enter_dir}"); continue
        lus, k, src = lineups[cid]; n = min(len(idxs), len(lus))
        for j in range(n):
            r = rows[idxs[j]]; r[i_qb:i_qb + 9] = [cell(str(p)) for p in lus[j]]
            (keep_ids if j < k else withdraw_ids).append((cid, r[i_entry].strip()))
        summary.append(f"contest {cid}: {len(idxs)} entries in the export, {len(lus)} lineups available -> filled {n} (keepers {min(k, n)}, withdraw {max(0, n - min(k, n))}); source {pathlib.Path(src).name}"
                       + ("" if len(idxs) == len(lus) else f"  ** MISMATCH: export has {len(idxs)} entries, file has {len(lus)} lineups **"))
    out = pathlib.Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    with (out / "DKEntries-FILLED-keepers-first.csv").open("w", newline="") as h:
        w = csv.writer(h); [w.writerow(r) for r in rows]
    (out / "WITHDRAW-these-entry-ids.txt").write_text("".join(f"{cid}\t{eid}\n" for cid, eid in withdraw_ids))
    (out / "KEEP-these-entry-ids.txt").write_text("".join(f"{cid}\t{eid}\n" for cid, eid in keep_ids))
    (out / "FILL-SUMMARY.txt").write_text("\n".join(summary) + f"\nkeep {len(keep_ids)} entries, withdraw {len(withdraw_ids)} entries\n")
    print("\n".join(summary)); print(f"keep {len(keep_ids)} / withdraw {len(withdraw_ids)} -> {out / 'DKEntries-FILLED-keepers-first.csv'}")


if __name__ == "__main__":
    main()
