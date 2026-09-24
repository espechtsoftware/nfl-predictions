#!/usr/bin/env python3
"""Monday per-contest-type scoring of ENTER bundles: the entered head layout (control) against paper bundles (production
ae9f014d: R1 live-status re-layout, R2 tighter Questionable caps; never entered).

A bundle is a directory of per-contest ENTER files, `ENTER-<name>-<contest_id>-<n>-entries-KEEP-first-<k>.csv` (header
QB,RB,RB,WR,WR,WR,TE,FLEX,DST; slot cells are DraftKings draftable ids, never entry keys). Each lineup's realized points
use the field's own scoring (contest_ownership fpts by display name, as book_vs_field_scoreboard.py does), with ids
mapped through the week's run frame (dk_draftable_id -> display_name).

Per contest TYPE (the name; contest ids are never printed): contests, entries, the mean over contests of each contest's
best and average lineup, entries at 194+, and the share of the Millionaire field above each contest's best. Then each
paper bundle minus the control, per type.

    python paper_bundle_outcomes.py SEASON WEEK MILLY_CONTEST_ID FRAME_PARQUET control=ENTERED_BUNDLE_DIR LABEL=BUNDLE_DIR ...

Read-only against BigQuery; writes nothing. Run only after the week's outcomes are released and the standings imported.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np
import pandas as pd

ENTER_RE = re.compile(r"^ENTER-(?P<name>.+)-(?P<cid>\d+)-(?P<n>\d+)-entries-KEEP-first-(?P<k>\d+)\.csv$")


def read_bundle(bundle: Path) -> list[dict]:
    """One record per contest file: name, contest id, declared entries, rows (lists of draftable ids)."""
    out = []
    for f in sorted(bundle.glob("ENTER-*.csv")):
        m = ENTER_RE.match(f.name)
        if not m:
            continue                       # ENTER-all-rows-..., sheets and the like
        rows = [r for r in list(csv.reader(open(f, newline="")))[1:] if r]
        if len(rows) != int(m["n"]):
            raise SystemExit(f"{f.name}: {len(rows)} rows, the name declares {m['n']}")
        out.append({"name": m["name"], "cid": m["cid"], "rows": rows})
    if not out:
        raise SystemExit(f"no ENTER-<name>-<id>-<n>-entries-KEEP-first-<k>.csv files in {bundle}")
    return out


def score_bundle(contests: list[dict], pts_of: dict[str, float], field: np.ndarray) -> pd.DataFrame:
    """Per contest: realized best, mean, 194+ entries and the field share strictly above its best."""
    recs = []
    for c in contests:
        pts = np.array([sum(pts_of.get(str(i), 0.0) for i in r) for r in c["rows"]], float)
        recs.append({"type": c["name"], "cid": c["cid"], "entries": len(pts), "best": float(pts.max()),
                     "mean": float(pts.mean()), "ge194": int((pts >= 194).sum()),
                     "field_above_best": float((field > pts.max()).mean())})
    return pd.DataFrame(recs)


def by_type(per: pd.DataFrame) -> pd.DataFrame:
    return per.groupby("type", sort=False).agg(contests=("cid", "size"), entries=("entries", "sum"),
                                                contest_best=("best", "mean"), contest_mean=("mean", "mean"),
                                                ge194=("ge194", "sum"), field_above_best=("field_above_best", "mean"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("season", type=int)
    ap.add_argument("week", type=int)
    ap.add_argument("contest_id")
    ap.add_argument("frame", type=Path)
    ap.add_argument("bundles", nargs="+", help="control=DIR first, then LABEL=DIR")
    a = ap.parse_args()
    specs = [s.partition("=") for s in a.bundles]
    if specs[0][0] != "control":
        raise SystemExit("the first bundle must be control=<entered bundle dir>")
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    fr = pd.read_parquet(a.frame)
    name_of = dict(zip(pd.to_numeric(fr.dk_draftable_id, errors="coerce").astype("Int64").astype(str), fr.display_name.astype(str)))
    fp = query_df(f"SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership` "
                  f"WHERE season={a.season} AND week={a.week} GROUP BY 1")
    real = dict(zip(fp.display_name.astype(str), fp.fpts.astype(float)))
    field = query_df(f"SELECT points FROM `{settings.raw}.contest_entries` WHERE season={a.season} AND week={a.week} "
                     f"AND contest_id='{a.contest_id}'").points.to_numpy(float)
    if not len(field) or not real:
        raise SystemExit("no standings / ownership imported for this week yet")
    tables = {}
    for label, _, d in specs:
        contests = read_bundle(Path(d).expanduser())
        ids = {i for c in contests for r in c["rows"] for i in r}
        unmapped = sorted(i for i in ids if i not in name_of)
        if unmapped:
            raise SystemExit(f"{label}: {len(unmapped)} draftable ids are not in the frame (wrong week or frame): {unmapped[:5]}")
        pts_of = {i: real.get(name_of[i], 0.0) for i in ids}
        unmatched = sum(name_of[i] not in real for i in ids)
        tables[label] = by_type(score_bundle(contests, pts_of, field))
        print(f"== {label}: {len(contests)} contests, {sum(len(c['rows']) for c in contests)} entries, "
              f"{len(ids)} players ({unmatched} with no fpts row, counted 0)")
        print(tables[label].round({"contest_best": 2, "contest_mean": 2, "field_above_best": 5}).to_string())
    ctrl = tables["control"]
    for label, t in tables.items():
        if label == "control":
            continue
        if list(t.index) != list(ctrl.index) or (t.entries != ctrl.entries).any():
            print(f"== {label} - control: contest types or entry counts differ; no per-type difference printed")
            continue
        diff = (t[["contest_best", "contest_mean", "ge194", "field_above_best"]] - ctrl[["contest_best", "contest_mean", "ge194", "field_above_best"]])
        print(f"== {label} - control (per type; lower field_above_best is better)")
        print(diff.round({"contest_best": 2, "contest_mean": 2, "field_above_best": 5}).to_string())


if __name__ == "__main__":
    main()
