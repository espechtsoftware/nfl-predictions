#!/usr/bin/env python3
"""The week's BLENDED predicted ownership (reviewer 2026-09-29; the rule PREREG-L15 froze as BLEND_PCT and PREREG-O1's
amendment 1 grades as BLEND_LS): for a player LineStar's projected ownership covers, the mean of the ownership model's
percent and LineStar's percent; for every other player, the model's percent alone. Players are joined on normalized
name + position, as L15 did.

    python scripts/ownership_blend.py --sets ~/week4-sunday/ownership_sets.csv \\
        --linestar-dir ~/week4-sunday/linestar --season 2026 --week 4 --out ~/week4-sunday/ownership_blend.csv

Reads the model's file (scripts/ownership_sets.py sets) and the newest LineStar capture with a receipt
(scripts/linestar_ownership_capture.py) or the one named by --linestar. Writes the blended file (the model file's id
columns, `pred_own` = the blend, `model_own`, `linestar_own`, `blended`) and `<out>.receipt.json` (both inputs' sha256,
the capture's time, the join counts, the largest LineStar players that did not join). Pre-lock by construction when
both inputs are. The output carries third-party values: the week's private directory / the private bucket only.

Refuses (exit 2, named) when: an input is missing or lacks its columns; the capture's receipt names another season or
week; the capture is older than --max-age-hours; fewer than --min-joined LineStar players join the model's file; or a
value is not a percentage. It never fills a value in and never falls back to the model alone: a week without a valid
capture has no blended file, and the chain's ownership term then refuses by name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")


def norm(name: object) -> str:
    """L15's name key: lower case, generational suffixes and punctuation dropped, single spaces."""
    s = str(name).lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    s = re.sub(r"[^a-z ]", "", s)
    return " ".join(s.split())


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def newest_capture(d: Path) -> Path:
    """The newest linestar-own-*.csv in d that has its receipt beside it (a capture without a receipt did not finish)."""
    hits = sorted(c for c in d.glob("linestar-own-*.csv") if c.with_name(c.name[:-4] + ".receipt.json").is_file())
    if not hits:
        raise SystemExit(f"no LineStar capture with a receipt under {d}")
    return max(hits, key=lambda c: json.loads(c.with_name(c.name[:-4] + ".receipt.json").read_text()).get("captured_at_utc", ""))


def blend(sets: pd.DataFrame, ls: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """BLEND_PCT. `sets` needs display_name, pos, pred_own (%); `ls` needs name, pos, own_proj (%)."""
    for col, frame, what in (("pred_own", sets, "the model's file"), ("own_proj", ls, "the LineStar capture")):
        v = pd.to_numeric(frame[col], errors="coerce")
        if len(v) == 0 or not np.all(np.isfinite(v)):
            raise SystemExit(f"{what} holds {int((~np.isfinite(v)).sum())} {col} values that are not numbers (of {len(v)})")
        if float(v.min()) < -0.5 or float(v.max()) > 100.0 or float(v.max()) <= 1.0:
            raise SystemExit(f"{what}: {col} runs {float(v.min()):.3f}..{float(v.max()):.3f}, not percentages")
    d = sets.copy()
    d["_key"] = d.display_name.map(norm); d["_pos"] = d.pos.astype(str).str.upper()
    l = ls.assign(_key=ls.name.map(norm), _pos=ls.pos.astype(str).str.upper(), linestar_own=pd.to_numeric(ls.own_proj, errors="coerce"))
    dup = int(l.duplicated(["_key", "_pos"]).sum())
    l = l.drop_duplicates(["_key", "_pos"])
    d = d.merge(l[["_key", "_pos", "linestar_own"]], on=["_key", "_pos"], how="left")
    d["model_own"] = pd.to_numeric(d.pred_own, errors="coerce").clip(lower=0.0)
    d["blended"] = d.linestar_own.notna()
    d["pred_own"] = np.where(d.blended, (d.model_own + d.linestar_own.fillna(0.0)) / 2.0, d.model_own)
    joined = set(zip(d._key[d.blended], d._pos[d.blended]))
    lost = l[[k not in joined for k in zip(l._key, l._pos)]].sort_values("linestar_own", ascending=False)
    sk = d[d._pos.isin(SKILL)]
    meta = {"rule": "BLEND_PCT: mean(model %, LineStar projected %) where LineStar covers the player, the model % alone where not",
            "model_rows": int(len(d)), "linestar_rows": int(len(l)), "linestar_duplicates_dropped": dup, "joined": int(d.blended.sum()),
            "joined_skill": int(sk.blended.sum()), "linestar_rows_not_joined": int(len(lost)),
            "largest_not_joined": [{"name": r["name"], "pos": r["_pos"], "own_proj": round(float(r["linestar_own"]), 2)} for _, r in lost.head(8).iterrows()],
            "sum_pred_own": {"model": round(float(d.model_own.sum()), 1), "linestar_joined": round(float(d.linestar_own.sum()), 1),
                             "blend": round(float(d.pred_own.sum()), 1)},
            "top5": [{"name": r["display_name"], "pos": r["_pos"], "model": round(float(r["model_own"]), 2),
                      "linestar": None if pd.isna(r["linestar_own"]) else round(float(r["linestar_own"]), 2), "blend": round(float(r["pred_own"]), 2)}
                     for _, r in d.sort_values("pred_own", ascending=False).head(5).iterrows()]}
    d["pred_rank"] = d.pred_own.rank(ascending=False, method="first").astype(int)
    keep = [c for c in ("gsis_id", "dk_player_id", "id", "display_name", "pos", "team", "salary", "proj") if c in d.columns]
    return d[keep + ["pred_own", "pred_rank", "model_own", "linestar_own", "blended"]].sort_values("pred_rank").reset_index(drop=True), meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", type=Path, required=True, help="the ownership model's file (scripts/ownership_sets.py sets)")
    ap.add_argument("--linestar", type=Path, help="a capture csv (scripts/linestar_ownership_capture.py); its receipt must sit beside it")
    ap.add_argument("--linestar-dir", type=Path, help="take the newest capture with a receipt in this directory")
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-joined", type=int, default=100, help="refuse when fewer LineStar players join the model's file")
    ap.add_argument("--max-age-hours", type=float, default=30.0, help="refuse a capture older than this (last week's file is never this week's)")
    ap.add_argument("--now", help="tests: the current time, ISO UTC")
    a = ap.parse_args(argv)
    if bool(a.linestar) == bool(a.linestar_dir):
        raise SystemExit("name exactly one of --linestar and --linestar-dir")
    if not a.sets.is_file():
        raise SystemExit(f"the ownership model's file {a.sets} does not exist")
    cap = a.linestar or newest_capture(a.linestar_dir)
    rec_path = cap.with_name(cap.name[:-4] + ".receipt.json")
    if not cap.is_file() or not rec_path.is_file():
        raise SystemExit(f"the LineStar capture {cap} or its receipt {rec_path.name} does not exist")
    rec = json.loads(rec_path.read_text())
    if (rec.get("season"), rec.get("week")) != (a.season, a.week):
        raise SystemExit(f"the capture {cap.name} is for season {rec.get('season')} week {rec.get('week')}, not {a.season} week {a.week}")
    if rec.get("csv_sha256") != sha256_file(cap):
        raise SystemExit(f"the capture {cap.name} does not match its receipt's sha256")
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    taken = datetime.fromisoformat(str(rec.get("captured_at_utc")))
    age = (now - taken).total_seconds() / 3600.0
    if not 0 <= age <= a.max_age_hours:
        raise SystemExit(f"the capture {cap.name} was taken {age:.1f} h ago (allowed 0..{a.max_age_hours})")
    sets = pd.read_csv(a.sets); ls = pd.read_csv(cap)
    for frame, need, what in ((sets, {"display_name", "pos", "pred_own"}, a.sets), (ls, {"name", "pos", "own_proj"}, cap)):
        if not need <= set(frame.columns):
            raise SystemExit(f"{what} lacks {sorted(need - set(frame.columns))}")
    out, meta = blend(sets, ls)
    if meta["joined"] < a.min_joined:
        raise SystemExit(f"only {meta['joined']} LineStar players join the model's file (need >= {a.min_joined}); "
                         f"largest not joined: {meta['largest_not_joined'][:5]}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    receipt = {"kind": "blended predicted ownership (model + LineStar projected), pre-lock", "season": a.season, "week": a.week,
               "built_at_utc": now.isoformat(), "sets": str(a.sets), "sets_sha256": sha256_file(a.sets),
               "linestar_capture": str(cap), "linestar_sha256": sha256_file(cap), "linestar_captured_at_utc": rec.get("captured_at_utc"),
               "linestar_label": rec.get("label"), "capture_age_hours": round(age, 2), "out": a.out.name, "out_sha256": sha256_file(a.out), **meta,
               "source": "holds third-party values (LineStar); private storage only"}
    a.out.with_name(a.out.name + ".receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(f"blended ownership: {meta['joined']} of {meta['model_rows']} players blended with LineStar ({meta['linestar_rows_not_joined']} LineStar "
          f"rows not joined), capture {rec.get('label')} {age:.1f} h old -> {a.out}\n  top 5: "
          + "; ".join(f"{t['name']} {t['blend']}" for t in meta["top5"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
