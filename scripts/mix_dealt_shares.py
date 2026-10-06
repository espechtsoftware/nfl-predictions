#!/usr/bin/env python3
"""The shape mix the operator actually ENTERS (reviewer 2026-10-05, --main mix item c): after `enter_layout write` (the
small-contest overlap limit applied), each dealt entry's book row is mapped back to its study-18 cell through the union's
candidate tags, and the dealt entry shares are printed beside the quotas, with the shape marginals of the dealt entries.

    python scripts/mix_dealt_shares.py --stage <ENTER staging dir> --upload <the bundle's upload csv> --run <union run dir>

Reads the stage's ENTER-rowmap.json ({contest: [0-based upload rows]}), the upload (DK ids per slot), the union run's
candidates.parquet (players as frame ids, tag mix_<cell>) and frame.parquet (frame id -> dk_player_id). A row with no mix
tag (the tail sleeve, a house replacement) is counted as `house`. Informational: exit 0 unless an input is unreadable;
a run whose union main is not mix prints one line and exits 0.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.inference.enter_layout import ROWMAP_NAME  # noqa: E402
from nfl_dfs.inference.mix_shapes import MIX_CELLS, PORTFOLIOS, cell_of_tag  # noqa: E402


def dealt_shares(rowmap: dict[str, list[int]], upload_rows: list[list[str]], cell_of_set: dict[frozenset, str],
                 pos: dict, team: dict, opp: dict, game: dict, cells: dict = MIX_CELLS) -> dict:
    counts: Counter = Counter(); shape: Counter = Counter(); n = 0
    for rows in rowmap.values():
        for r in rows:
            ids = upload_rows[r]
            counts[cell_of_set.get(frozenset(ids), "house")] += 1; n += 1
            qb = next((i for i in ids if pos.get(i) == "QB"), None)
            if qb is None:
                continue
            mates = sum(1 for i in ids if pos.get(i) in ("WR", "TE") and team.get(i) == team.get(qb))
            bring = sum(1 for i in ids if pos.get(i) in ("RB", "WR", "TE") and team.get(i) == opp.get(qb))
            shape["qb_plus1"] += mates == 1; shape["qb_plus2"] += mates >= 2; shape["bringback"] += bring >= 1
            shape["in_qb_game"] += sum(1 for i in ids if pos.get(i) != "DST" and game.get(i) == game.get(qb))
            # dual = a second-game pair, as mix_shapes.shape_violations defines it: a game other than the QB's with >= 1
            # non-DST player from EACH of its two teams
            teams_by_game: dict = {}
            for i in ids:
                if pos.get(i) != "DST" and game.get(i) != game.get(qb):
                    teams_by_game.setdefault(game.get(i), set()).add(team.get(i))
            shape["dual"] += any(len(t) == 2 for t in teams_by_game.values())
    return {"entries": n, "cells": {c: counts.get(c, 0) for c in [*cells, "house"]},
            "shares": {c: round(counts.get(c, 0) / n, 3) if n else None for c in [*cells, "house"]},
            "quotas": {c: cells[c][0] for c in cells},
            "shape": {k: round(v / n, 3) if n else None for k, v in shape.items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", type=Path, required=True); ap.add_argument("--upload", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    a = ap.parse_args(argv)
    rec = json.loads((a.run / "receipt.json").read_text())
    if ((rec.get("config", {}).get("union") or {}).get("main")) != "mix":
        print("MIX DEALT: not a mix main (nothing to report)")
        return 0
    rowmap = json.loads((a.stage / ROWMAP_NAME).read_text())
    upload_rows = [r for r in list(csv.reader(open(a.upload, newline="")))[1:]]
    fr = pd.read_parquet(a.run / "frame.parquet")
    dk_of = {str(i): str(int(d)) for i, d in zip(fr["id"].astype(str), fr["dk_player_id"]) if pd.notna(d)}
    cands = pd.read_parquet(a.run / "candidates.parquet")
    cell_of_set: dict[frozenset, str] = {}
    for players, tag in zip(cands["players"].astype(str), cands["tag"].astype(str)):
        cell = cell_of_tag(tag)
        if cell is not None:
            cell_of_set.setdefault(frozenset(dk_of.get(p.strip(), "?") for p in players.split(",")), cell)
    by_dk = fr.assign(dk=fr["dk_player_id"].astype("Int64").astype(str))
    pos, team, opp, game = (dict(zip(by_dk.dk, by_dk[c].astype(str))) for c in ("pos", "team", "opp", "game_id"))
    portfolio = (((rec.get("config", {}).get("union") or {}).get("mix") or {}).get("mix") or {}).get("portfolio", "mix")
    out = dealt_shares(rowmap, upload_rows, cell_of_set, pos, team, opp, game, PORTFOLIOS[portfolio])
    out["portfolio"] = portfolio
    print("MIX DEALT (the entries as staged, after the small-contest overlap limit): "
          + " / ".join(f"{c} {out['cells'][c]} ({out['shares'][c]}; quota {out['quotas'].get(c, '-')})" for c in out["cells"])
          + f" of {out['entries']} entries; shape {json.dumps(out['shape'], sort_keys=True)}")
    (a.stage / "ENTER-mix-dealt.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
