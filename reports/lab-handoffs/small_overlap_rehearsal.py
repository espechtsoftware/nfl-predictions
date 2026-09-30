#!/usr/bin/env python3
"""Rehearse ENTER_SMALL_MAX_SHARED on a real upload through the real enter_layout write + check (operator 2026-09-30:
in effect for Week 4; laptop 71b10e40 item 2). Outcome-blind: for each M, the ranks replaced, the relaxations
(fallbacks), write/check agreement, and the projection and predicted ownership of the rows swapped in minus out.
Scratch output only; prints aggregates.

  PYTHONPATH=<checkout>/src python reports/lab-handoffs/small_overlap_rehearsal.py --contests C.json --upload U.csv \
      --frame frame.parquet [--own-sets ownership_sets.csv] [--ms 5,4] [--layout head] [order args passed through: --order ...]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

from nfl_dfs.inference import enter_layout as EL


def run(cmd, contests, upload, stage, extra, m):
    env_old = os.environ.get(EL.SMALL_OVERLAP_ENV)
    if m is None:
        os.environ.pop(EL.SMALL_OVERLAP_ENV, None)
    else:
        os.environ[EL.SMALL_OVERLAP_ENV] = str(m)
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = EL.main([cmd, str(contests), str(upload), str(stage)] + extra)
    finally:
        if env_old is None:
            os.environ.pop(EL.SMALL_OVERLAP_ENV, None)
        else:
            os.environ[EL.SMALL_OVERLAP_ENV] = env_old
    return rc, out.getvalue(), err.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contests", type=Path, required=True); ap.add_argument("--upload", type=Path, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--own-sets", type=Path)
    ap.add_argument("--ms", default="5,4"); ap.add_argument("--layout", default="head")
    a, extra = ap.parse_known_args()
    extra = ["--layout", a.layout] + extra
    fr = pd.read_parquet(a.frame)
    proj = {str(d): float(p) for d, p in zip(fr.dk_draftable_id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0))}
    own = {}
    if a.own_sets:
        s = pd.read_csv(a.own_sets, dtype=str)
        pid = dict(zip(fr.dk_draftable_id.astype(str), fr.dk_player_id.astype("Int64").astype(str)))
        by_pid = dict(zip(s.dk_player_id.astype(str), pd.to_numeric(s.pred_own, errors="coerce").fillna(0)))
        own = {d: float(by_pid.get(p, 0.0)) for d, p in pid.items()}
    hdr, body = EL._read_rows(a.upload)
    rowp = [sum(proj.get(c.strip(), 0.0) for c in EL.row_players(hdr, r)) for r in body]
    rowo = [sum(own.get(c.strip(), 0.0) for c in EL.row_players(hdr, r)) for r in body]
    contests = EL._contests(a.contests)
    small = [EL.label(c) for c in contests if str(c.get("track", "mean")) == "mean" and "ranks" not in c and 2 <= int(c["entries"]) <= 5]
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "head"
        rc, _, _ = run("write", a.contests, a.upload, base, extra, None)
        if rc:
            raise SystemExit("the layout without the limit failed")
        head_map = json.loads((base / EL.ROWMAP_NAME).read_text())
        print(f"{len(contests)} contests; small main-track (2-5, unpinned): {len(small)}; upload rows {len(body)}; missing projections "
              f"{sum(1 for r in body for c in EL.row_players(hdr, r) if c.strip() not in proj)}")
        for m in [int(x) for x in a.ms.split(",")]:
            st = Path(tmp) / f"m{m}"
            rc, out, err = run("write", a.contests, a.upload, st, extra, m)
            if rc:
                print(f"M={m}: WRITE FAILED\n{out}\n{err}"); continue
            rc_c, _, _ = run("check", a.contests, a.upload, st, extra, m)
            rc_off, _, _ = run("check", a.contests, a.upload, st, extra, None)
            mp = json.loads((st / EL.ROWMAP_NAME).read_text())
            changed = [k for k in small if mp[k] != head_map[k]]
            outs = [r for k in changed for r in head_map[k] if r not in mp[k]]
            ins = [r for k in changed for r in mp[k] if r not in head_map[k]]
            rec = next((l for l in out.splitlines() if l.startswith("small_overlap: ")), "small_overlap: {}")
            banners = [l for l in out.splitlines() if l.startswith("!!!")]
            others_same = all(mp[k] == head_map[k] for k in head_map if k not in small)
            dp = (sum(rowp[r] for r in ins) - sum(rowp[r] for r in outs)) / max(len(ins), 1)
            do = (sum(rowo[r] for r in ins) - sum(rowo[r] for r in outs)) / max(len(ins), 1)
            print(f"M={m}: {len(changed)} of {len(small)} small contests changed, {len(ins)} rows swapped; per swapped row: "
                  f"projection {dp:+.2f}, predicted ownership {do:+.1f}; relaxations {len(banners)}"
                  + (f" {banners}" if banners else "") + f"; record {rec[len('small_overlap: '):]}"
                  f"; check with M: {'PASS' if rc_c == 0 else 'FAIL'}; check without M: {'FAIL (guards)' if rc_off else 'pass (no change)'}"
                  f"; other contests unchanged: {others_same}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
