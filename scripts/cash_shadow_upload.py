#!/usr/bin/env python3
"""DraftKings upload CSV for a cash/double-up shadow arm (operator 2026-09-28: "add the upload file").

Turns `<cash dir>/cash_shadow.csv` (cash_shadow_paper.py build / build-b: one row per lineup, `ids` = the frame ids,
`|`-joined) into a DK classic upload with slate-specific draftable ids, exactly the way the tournament book is emitted:
  1. `book.csv` in DK slot order (QB,RB,RB,WR,WR,WR,TE,FLEX,DST) with dk_player_id, written by the pinned lab's `dk_csv`
     (FLEX = the position's latest starter when LIVE_FLEX_LATEST=1, as the chain sets it);
  2. the run dir's `frame.parquet` copied beside it (the draftable-id map and the slot eligibility check);
  3. `nfl_dfs.inference.dk_upload_csv_v1.rows_from_live_week_run` + `write_upload_csv` (fail-closed, create-only).

    PYTHONPATH=<pinned nfl2 src>:$PROD/src python scripts/cash_shadow_upload.py <cash dir> --run-dir <run dir> \\
        --output <OUT>/upload-<tag>-cash-A.csv [--ranks 1-5]

Refuses: a cash dir without cash_shadow.csv or receipt.json, a receipt whose frame sha256 differs from the run dir's
frame (the lineups were solved on another frame), an id the frame does not carry, an existing output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd


class _LU:
    def __init__(self, players: list[dict]):
        self.players = players


def lineups_from_cash_csv(cash_csv: Path, frame: pd.DataFrame) -> list[list[str]]:
    """The `ids` column, split; every id must be in the frame."""
    df = pd.read_csv(cash_csv, dtype=str)
    if "ids" not in df.columns:
        raise SystemExit(f"{cash_csv} has no ids column")
    known = set(frame["id"].astype(str))
    out = []
    for r, cell in zip(df.get("rank", range(1, len(df) + 1)), df["ids"]):
        ids = [x for x in str(cell).split("|") if x]
        if len(ids) != 9:
            raise SystemExit(f"cash lineup {r} has {len(ids)} ids, not 9")
        bad = [i for i in ids if i not in known]
        if bad:
            raise SystemExit(f"cash lineup {r} holds ids the run dir's frame does not carry: {bad}")
        out.append(ids)
    return out


def player_dicts(frame: pd.DataFrame) -> dict[str, dict]:
    df = pd.DataFrame({"id": frame["id"].astype(str), "name": frame["name"].astype(str), "pos": frame["pos"].astype(str),
                       "salary": pd.to_numeric(frame["salary"], errors="coerce").fillna(0).astype(int)})
    return {r["id"]: r for r in df.to_dict("records")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cash_dir", type=Path); ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True); ap.add_argument("--ranks", help="inclusive 1-based range, e.g. 1-5")
    a = ap.parse_args(argv)
    from nfl2.live import dk_csv                                   # the pinned lab clone on PYTHONPATH
    from nfl_dfs.inference import dk_upload_csv_v1 as up
    cash, run = a.cash_dir, a.run_dir
    for f in ("cash_shadow.csv", "receipt.json"):
        if not (cash / f).is_file():
            raise SystemExit(f"{cash / f} missing")
    if a.output.exists():
        raise SystemExit(f"{a.output} exists (create-only)")
    rec = json.loads((cash / "receipt.json").read_text())
    frame_sha = hashlib.sha256((run / "frame.parquet").read_bytes()).hexdigest()
    rec_sha = (rec.get("sha256") or {}).get("frame") or rec.get("frame_sha256")
    if rec_sha and rec_sha != frame_sha:
        raise SystemExit(f"the cash receipt's frame sha256 ({rec_sha[:12]}…) is not the run dir's ({frame_sha[:12]}…): built on another frame")
    frame = pd.read_parquet(run / "frame.parquet")
    lineups = lineups_from_cash_csv(cash / "cash_shadow.csv", frame)
    pdict = player_dicts(frame)
    n = dk_csv([_LU([pdict[i] for i in ids]) for ids in lineups], frame, cash / "book.csv")
    if n != len(lineups):
        raise SystemExit(f"dk_csv wrote {n} rows for {len(lineups)} lineups")
    if not (cash / "frame.parquet").is_file():
        shutil.copyfile(run / "frame.parquet", cash / "frame.parquet")
    rows, receipt = up.rows_from_live_week_run(cash.resolve())
    if a.ranks:
        first, last = (int(x) for x in a.ranks.split("-", 1))
        rows = up.slice_ranks(rows, first, last); receipt["ranks"] = {"first": first, "last": last}
    written = up.write_upload_csv(rows, a.output)
    receipt.update({"cash_dir": str(cash), "run_dir": str(run), "cash_receipt_kind": rec.get("kind"), "lineups": len(lineups)})
    print(json.dumps({"upload": written, "source": receipt}, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
