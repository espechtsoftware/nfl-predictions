#!/usr/bin/env python3
"""Monday refit of the satellite late swap's per-type strength offsets (sat_late_swap_live.py --offsets).

The live line of a flat-payout contest is the Millionaire field's conditional final quantile at the contest's paid share
plus the contest type's offset: satellite fields are stronger than the Millionaire's. After settlement the offset is
measured directly, per contest: its real line (the points of its last paid place AMONG THE OTHER ENTRANTS -- our own
entries are removed, as the rehearsal does, so a contest we won does not set the line at our own score) minus the
Millionaire's final score quantile at the same share (1 - paid / entries), averaged over the contests of each type (the
layout name: sat20, supersat2, ...). Only flat-payout contests are fitted; top-heavy ones are never swapped.
Our handle is the user entered in the most layout contests (>= 80% of them); it is kept in memory, never printed.
Read-only against BigQuery.

    python scripts/fit_late_swap_offsets.py --layout <entered bundle>/ENTER-layout.txt --details contest-details.json \\
        --season 2026 --week 4 --milly-contest-id <id> --out offsets-w04.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sat_late_swap_live import flat_payout, paid_places, parse_layout  # noqa: E402


def fit_offsets(layout: list[dict], details: dict, points_by_cid: dict[str, np.ndarray], milly_points: np.ndarray) -> dict:
    """{type: {offset, sd, n}} over the flat-payout contests with settled standings.
    `points_by_cid[cid]` = the final points of the contest's OTHER entrants (ours removed), any order."""
    per: dict[str, list[float]] = {}
    seen: set[str] = set()
    for c in layout:
        cid, name = c["cid"], c["name"]
        if cid in seen or cid not in details or not flat_payout(details[cid]) or cid not in points_by_cid:
            continue
        seen.add(cid)
        paid, n = paid_places(details[cid])
        pts = np.asarray(points_by_cid[cid], dtype=float)
        if paid <= 0 or n <= 0 or len(pts) < paid:
            continue
        line = float(np.sort(pts)[::-1][paid - 1])                     # the last paid place's points
        per.setdefault(name, []).append(line - float(np.quantile(milly_points, 1 - paid / n)))
    return {k: {"offset": round(float(np.mean(v)), 2), "sd": round(float(np.std(v, ddof=1)), 2) if len(v) > 1 else None,
                "n": len(v)} for k, v in sorted(per.items())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--layout", type=Path, required=True); ap.add_argument("--details", type=Path, required=True)
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--milly-contest-id", required=True); ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    layout = parse_layout(a.layout)
    details = json.loads(a.details.read_text())
    cids = sorted({c["cid"] for c in layout} | {a.milly_contest_id})
    df = query_df(f"""SELECT contest_id, entry_name, points FROM `{settings.raw}.contest_entries`
                      WHERE season = {a.season} AND week = {a.week} AND contest_id IN ({', '.join(repr(c) for c in cids)})
                      QUALIFY ROW_NUMBER() OVER (PARTITION BY contest_id, entry_id ORDER BY imported_at DESC) = 1""")
    df["contest_id"] = df.contest_id.astype(str)
    df["user"] = df.entry_name.astype(str).str.extract(r"^([^ (]+)")[0]
    layout_cids = {c["cid"] for c in layout} & set(df.contest_id)
    reach = df[df.contest_id.isin(layout_cids)].groupby("user").contest_id.nunique().sort_values(ascending=False)
    if reach.empty or reach.iloc[0] < 0.8 * len(layout_cids):
        print(f"could not identify our entries (best user reaches {0 if reach.empty else reach.iloc[0]} of "
              f"{len(layout_cids)} contests); refusing, a line would include our own scores", file=sys.stderr)
        return 2
    me = reach.index[0]
    print(f"our entries identified in {reach.iloc[0]} of {len(layout_cids)} settled layout contests and removed from the fields")
    others = df[df.user != me]
    by = {cid: g.points.to_numpy(float) for cid, g in others.groupby("contest_id")}
    if a.milly_contest_id not in by:
        print(f"no settled Millionaire standings for contest {a.milly_contest_id}", file=sys.stderr)
        return 2
    fit = fit_offsets(layout, details, by, by[a.milly_contest_id])
    missing = sorted({c["name"] for c in layout if c["cid"] in details and flat_payout(details[c["cid"]])} - set(fit))
    for k, v in fit.items():
        print(f"{k:14s} offset {v['offset']:+6.2f}  (n {v['n']}, sd {v['sd']})")
    if missing:
        print(f"flat contest types without settled standings (offset not refit): {', '.join(missing)}", file=sys.stderr)
    if a.out:
        a.out.write_text(json.dumps({k: v["offset"] for k, v in fit.items()}, indent=1))
        print(f"wrote {a.out} (pass it to sat_late_swap_live.py --offsets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
