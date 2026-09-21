"""Pre-upload exposure sheet (operator directive after Week 2 2026).

One row per player held by the book: rows held and share, share inside the
majors' block, served projection, market points and market source (from
``market_source_log``), DraftKings status, whether the books posted a line,
field-ownership projection when one is supplied, and every flag that needs a
stated reason before upload:

* ``over_30``       held in more than 30% of the book
* ``majors_over_20`` held in more than 20% of the majors' rows
* ``dst_over_20``   a DST held in more than 20% of the book
* ``injured_over_10`` Questionable/Doubtful/Out status held in more than 10%
* ``no_line_over_5`` no posted prop line (model-only) held in more than 5%
* ``market_gap``    served projection more than 15% above the market

The sheet is a monitor, not a selector: it changes nothing, it names what the
operator must accept or reject.  Pure functions here; ``scripts/exposure_sheet.py``
does the file and warehouse I/O.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

MAJORS_DEFAULT = ("milly", "flea", "huddle", "nickel", "pylon")
THRESHOLDS = {"over_30": 0.30, "majors_over_20": 0.20, "dst_over_20": 0.20, "injured_over_10": 0.10, "no_line_over_5": 0.05, "market_gap_ratio": 1.15}
INJURED = {"Q", "D", "O", "IR", "OUT", "DOUBTFUL", "QUESTIONABLE"}


def contest_blocks(contests: list[dict]) -> list[dict]:
    """Sequential layout: contests.json order gives each contest a row block [first, last] (1-based)."""
    out, p0 = [], 0
    for c in contests:
        e = int(c["entries"]); out.append({"name": str(c.get("name")), "rows": [p0 + 1, p0 + e]}); p0 += e
    return out


def majors_row_mask(contests: list[dict], n_rows: int, majors: tuple[str, ...] = MAJORS_DEFAULT) -> np.ndarray:
    mask = np.zeros(n_rows, dtype=bool)
    for b in contest_blocks(contests):
        if b["name"] in majors:
            mask[b["rows"][0] - 1: b["rows"][1]] = True
    return mask


def build_sheet(
    book_rows: list[list[str]],
    players: pd.DataFrame,
    contests: list[dict],
    *,
    market_source: pd.DataFrame | None = None,
    status: dict[str, str] | None = None,
    field_own: dict[str, float] | None = None,
    majors: tuple[str, ...] = MAJORS_DEFAULT,
) -> pd.DataFrame:
    """``book_rows``: K lists of 9 player ids (strings) in upload order.  ``players``: one row per slate player with
    ``id``, ``name``, ``pos``, ``team``, ``salary``, ``proj`` (and optional ``market_points``).  ``market_source``:
    latest ``market_source_log`` batch (``gsis_id`` or ``id``, ``source``, ``market_points``).  ``status``: DK status
    by id.  ``field_own``: projected field ownership share (0-1) by id when available."""
    K = len(book_rows)
    if K == 0:
        raise ValueError("empty book")
    if any(len(r) != 9 for r in book_rows):
        raise ValueError("every book row must hold nine players")
    blocks = contest_blocks(contests)
    if blocks and blocks[-1]["rows"][1] != K:
        raise ValueError(f"contests.json covers {blocks[-1]['rows'][1]} rows, book has {K}")
    mmask = majors_row_mask(contests, K, majors); n_majors = int(mmask.sum())
    rows_held: dict[str, int] = {}; majors_held: dict[str, int] = {}
    for i, r in enumerate(book_rows):
        for p in r:
            rows_held[p] = rows_held.get(p, 0) + 1
            if mmask[i]: majors_held[p] = majors_held.get(p, 0) + 1
    info = players.set_index(players["id"].astype(str))
    src = None
    if market_source is not None and len(market_source):
        key = "id" if "id" in market_source.columns else "gsis_id"
        src = market_source.drop_duplicates(key).set_index(market_source[key].astype(str))
    out = []
    for p, n in rows_held.items():
        row = info.loc[p] if p in info.index else None
        name = str(row["name"]) if row is not None else p
        pos = str(row["pos"]) if row is not None else "?"
        proj = float(row["proj"]) if row is not None and pd.notna(row["proj"]) else math.nan
        market = math.nan; source = "unknown"
        if src is not None and p in src.index:
            source = str(src.loc[p, "source"]); market = float(src.loc[p, "market_points"]) if pd.notna(src.loc[p, "market_points"]) else math.nan
        elif row is not None and "market_points" in info.columns and pd.notna(row.get("market_points")):
            market = float(row["market_points"]); source = "frame"
        st = (status or {}).get(p, "") or ""
        share = n / K; mshare = (majors_held.get(p, 0) / n_majors) if n_majors else 0.0
        own = (field_own or {}).get(p, math.nan)
        flags = []
        if share > THRESHOLDS["over_30"] and not (pd.notna(own) and own >= 0.30): flags.append("over_30")
        if n_majors and mshare > THRESHOLDS["majors_over_20"] and not (pd.notna(own) and own >= 0.30): flags.append("majors_over_20")
        if pos == "DST" and share > THRESHOLDS["dst_over_20"]: flags.append("dst_over_20")
        if st.upper() in INJURED and share > THRESHOLDS["injured_over_10"]: flags.append("injured_over_10")
        if source.startswith("model_only_no_line") and share > THRESHOLDS["no_line_over_5"]: flags.append("no_line_over_5")
        if pd.notna(market) and pd.notna(proj) and market > 0 and proj > THRESHOLDS["market_gap_ratio"] * market: flags.append("market_gap")
        out.append({"id": p, "name": name, "pos": pos, "team": (str(row["team"]) if row is not None else "?"), "salary": (int(row["salary"]) if row is not None and pd.notna(row["salary"]) else None),
                    "rows": n, "share": round(share, 4), "majors_rows": majors_held.get(p, 0), "majors_share": round(mshare, 4), "proj": (round(proj, 2) if pd.notna(proj) else None),
                    "market_points": (round(market, 2) if pd.notna(market) else None), "market_source": source, "status": st, "field_own": (round(own, 4) if pd.notna(own) else None),
                    "flags": ",".join(flags)})
    sheet = pd.DataFrame(out).sort_values(["rows", "name"], ascending=[False, True]).reset_index(drop=True)
    return sheet


def sheet_markdown(sheet: pd.DataFrame, *, min_share: float = 0.15) -> str:
    """Markdown table of every player at or above ``min_share`` or carrying a flag; flagged rows first."""
    view = sheet[(sheet["share"] >= min_share) | (sheet["flags"] != "")].copy()
    view["_f"] = view["flags"].ne("").astype(int); view = view.sort_values(["_f", "rows"], ascending=[False, False])
    lines = ["| player | pos | team | salary | rows | share | majors share | proj | market | source | status | field own | flags |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in view.itertuples():
        lines.append(f"| {r.name} | {r.pos} | {r.team} | {r.salary if r.salary is not None else ''} | {r.rows} | {100*r.share:.1f}% | {100*r.majors_share:.1f}% | {r.proj if r.proj is not None else ''} | {r.market_points if r.market_points is not None else ''} | {r.market_source} | {r.status} | {('%.0f%%' % (100*r.field_own)) if r.field_own is not None else ''} | {r.flags} |")
    n_flag = int((sheet["flags"] != "").sum())
    head = f"{len(sheet)} players held; {n_flag} flagged (each flag needs a stated reason before upload).\n\n"
    return head + "\n".join(lines) + "\n"
