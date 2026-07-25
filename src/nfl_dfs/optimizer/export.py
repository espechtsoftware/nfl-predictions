"""DK upload CSV export and exposure reporting."""

from __future__ import annotations

import csv
import io
from collections import Counter

from .lineup import Lineup
from .showdown import ShowdownLineup

DK_HEADER = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
DK_SHOWDOWN_HEADER = ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]


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


def to_dk_showdown_csv(lineups: list[ShowdownLineup]) -> str:
    """DraftKings Showdown bulk-upload format: CPT first, then five FLEX."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DK_SHOWDOWN_HEADER)
    for lu in lineups:
        writer.writerow([f"{p['name']} ({p['id']})" for p in lu.slot_order()])
    return buf.getvalue()


def showdown_exposure_summary(lineups: list[ShowdownLineup]) -> list[dict]:
    """Classic exposure plus how often each player is the captain."""
    exp = exposure_summary(lineups)
    cpt_counts = Counter(lu.captain["id"] for lu in lineups)
    n = len(lineups)
    for row in exp:
        row["cpt_lineups"] = cpt_counts.get(row["id"], 0)
        row["cpt_exposure"] = cpt_counts.get(row["id"], 0) / n
    return exp


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
