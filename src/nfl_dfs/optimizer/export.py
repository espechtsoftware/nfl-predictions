"""DK upload CSV export and exposure reporting."""

from __future__ import annotations

import csv
import io
from collections import Counter

from .lineup import Lineup

DK_HEADER = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]


def to_dk_csv(lineups: list[Lineup]) -> str:
    """DraftKings bulk-upload format: one row per lineup, players as
    'Name (dk_id)' in slot order."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DK_HEADER)
    for lu in lineups:
        row = [f"{p['name']} ({p['id']})" for p in lu.slot_order()]
        writer.writerow(row)
    return buf.getvalue()


def exposure_summary(lineups: list[Lineup]) -> list[dict]:
    """Player exposure across a lineup set, sorted by exposure descending."""
    if not lineups:
        return []
    counts: Counter[str] = Counter()
    meta: dict[str, dict] = {}
    for lu in lineups:
        for p in lu.players:
            counts[p["id"]] += 1
            meta[p["id"]] = p
    n = len(lineups)
    return [
        {
            "id": pid,
            "name": meta[pid]["name"],
            "pos": meta[pid]["pos"],
            "team": meta[pid]["team"],
            "salary": meta[pid]["salary"],
            "exposure": count / n,
            "lineups": count,
        }
        for pid, count in counts.most_common()
    ]
