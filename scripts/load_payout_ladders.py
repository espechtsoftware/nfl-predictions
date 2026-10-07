#!/usr/bin/env python3
"""P1 (the approved plan 2026-10-04, reports/2026-10-04-agent-proposed-studies.md; the operator's Wed 10-07 directive):
load DraftKings payout ladders into `nfl_raw.dk_payout_ladders`, one row per payout tier, from a contest-details capture
-- the public contest-details JSON, {contest_id: {name, entryFee | fee, maximumEntries | max, entries,
maximumEntriesPerUser, draftGroupId, contestStartTime, totalPayouts, payoutSummary: [{minPosition, maxPosition,
tierPayoutDescriptions: {Cash | Ticket: text}, payoutDescriptions: [{value, ...}]}]}}. A description's value is per
position (every 2026 capture's ladder sums to DK's totalPayouts exactly). The lobby poll's
dk_contest_fills.payout_metadata_json is a one-line prize summary (one entry for the Millionaire), so it cannot give a
ladder.

Refuses (exit 3) before any write:
  - a contest without a positive entry fee or without tiers;
  - tiers that leave a gap or overlap (they must run 1, 2, ... without a hole);
  - a tier without a value, or carrying both Cash and Ticket (its value could not be split);
  - a ladder whose sum (positions x value) differs from DK's totalPayouts by more than 1%;
  - with --apply, a file whose content (sha256) is already loaded.
Dry run by default: prints each contest's structure in multiples of its fee (never dollars). --apply appends.
Dollars live only in BigQuery and in private files; tracked files report multiples (the operator's rule).

    python scripts/load_payout_ladders.py --season 2026 --week 4 --file <contest-details.json> [--captured-at ISO] [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

COLUMNS = ["loaded_at", "season", "week", "contest_id", "contest_name", "draft_group_id", "entry_fee", "max_entries",
           "max_entries_per_user", "entries_at_capture", "contest_start", "tier", "min_position", "max_position",
           "cash_value", "ticket_value", "ticket_description", "source_file", "source_sha256", "captured_at"]
POOL_TOLERANCE = 0.01


def _num(x):
    return None if x is None else float(x)


def ladder_rows(details: dict, season: int, week: int, source_file: str, source_sha256: str, captured_at: str) -> list[dict]:
    """The table's rows for one capture; raises ValueError on any refusal above."""
    rows = []
    for cid, c in details.items():
        fee = c.get("entryFee") if c.get("entryFee") is not None else c.get("fee")
        if fee is None or float(fee) <= 0:
            raise ValueError(f"contest {cid}: no positive entry fee")
        tiers = sorted(c.get("payoutSummary") or [], key=lambda t: int(t["minPosition"]))
        if not tiers:
            raise ValueError(f"contest {cid}: no payoutSummary tiers")
        expect, total = 1, 0.0
        for i, t in enumerate(tiers, 1):
            lo, hi = int(t["minPosition"]), int(t["maxPosition"])
            if lo != expect or hi < lo:
                raise ValueError(f"contest {cid}: tier {i} covers positions {lo}-{hi}; expected it to start at {expect}")
            expect = hi + 1
            kinds = t.get("tierPayoutDescriptions") or {}
            if "Cash" in kinds and "Ticket" in kinds:
                raise ValueError(f"contest {cid}: tier {i} pays both cash and a ticket; its value cannot be split")
            vals = [d.get("value") for d in t.get("payoutDescriptions") or []]
            if not vals or any(v is None for v in vals):
                raise ValueError(f"contest {cid}: tier {i} has no value")
            value = float(sum(vals))
            total += (hi - lo + 1) * value
            ticket = "Ticket" in kinds
            rows.append({"season": int(season), "week": int(week), "contest_id": str(cid), "contest_name": c.get("name"),
                         "draft_group_id": int(c["draftGroupId"]) if c.get("draftGroupId") is not None else None,
                         "entry_fee": float(fee),
                         "max_entries": int(c.get("maximumEntries") or c.get("max") or 0) or None,
                         "max_entries_per_user": int(c["maximumEntriesPerUser"]) if c.get("maximumEntriesPerUser") is not None else None,
                         "entries_at_capture": int(c["entries"]) if c.get("entries") is not None else None,
                         "contest_start": c.get("contestStartTime"), "tier": i, "min_position": lo, "max_position": hi,
                         "cash_value": 0.0 if ticket else value, "ticket_value": value if ticket else 0.0,
                         "ticket_description": kinds.get("Ticket"), "source_file": source_file,
                         "source_sha256": source_sha256, "captured_at": captured_at})
        tp = _num(c.get("totalPayouts"))
        if tp and abs(total - tp) > POOL_TOLERANCE * tp:
            raise ValueError(f"contest {cid}: the ladder sums to {total:.2f}, DK's totalPayouts is {tp:.2f}")
    return rows


def split_payout_multiple(tiers: list[dict], rank: int, n_tied: int, fee: float) -> float:
    """The realized payout multiple of an entry at a reported rank shared by n_tied entries: DraftKings pools the prizes
    of positions rank .. rank + n_tied - 1 and splits them equally -- the sum over tiers of overlap(tier, [rank,
    rank + n_tied - 1]) x the tier's per-position value, over n_tied x fee. Positions past the last tier pay 0, so a tie
    across the cash line gets its partial share (the reviewer, 10-07). v_dk_entry_tier.split_payout_multiple is this."""
    hi = rank + n_tied - 1
    paid = sum(max(0, min(int(t["max_position"]), hi) - max(int(t["min_position"]), rank) + 1)
               * (float(t["cash_value"]) + float(t["ticket_value"])) for t in tiers)
    return paid / (n_tied * float(fee))


def structure(rows: list[dict]) -> pd.DataFrame:
    """Per contest, in multiples of its fee (never dollars): positions paid and their share of the field, the pool ratio
    (paid / fees at capacity), the first and min-cash multiples, the payout kind, and -- for a flat ticket ladder -- the
    break-even ticket rate as a multiple of the field's (1 / the pool ratio)."""
    d = pd.DataFrame(rows)
    out = []
    for cid, g in d.groupby("contest_id", sort=False):
        g = g.sort_values("tier"); fee = g.entry_fee.iloc[0]; cap = g.max_entries.iloc[0]
        per = g.cash_value + g.ticket_value; n = g.max_position - g.min_position + 1
        pool = float((n * per).sum()); paid = int(g.max_position.max())
        flat = per.nunique() == 1
        kind = "ticket" if (g.ticket_value > 0).all() else "cash" if (g.cash_value > 0).all() else "mixed"
        out.append({"contest_id": cid, "name": str(g.contest_name.iloc[0])[:48], "kind": kind, "max_entries": cap,
                    "paid": paid, "paid_share": round(paid / cap, 4) if cap else None,
                    "pool_ratio": round(pool / (fee * cap), 4) if cap else None,
                    "first_x": round(per.iloc[0] / fee, 2), "min_cash_x": round(per.iloc[-1] / fee, 2),
                    "break_even_x_field_rate": round((fee * cap) / pool, 3) if (flat and cap) else None})
    return pd.DataFrame(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--file", type=Path, required=True)
    ap.add_argument("--captured-at", default=None, help="the capture time (ISO); default: the file's modification time")
    ap.add_argument("--apply", action="store_true", help="append to nfl_raw.dk_payout_ladders (default: dry run)")
    a = ap.parse_args(argv)
    raw = a.file.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
    cap_at = a.captured_at or datetime.fromtimestamp(a.file.stat().st_mtime, timezone.utc).isoformat()
    try:
        rows = ladder_rows(json.loads(raw), a.season, a.week, a.file.name, sha, cap_at)
    except (ValueError, KeyError, TypeError) as e:
        print(f"PAYOUT LADDERS REFUSED ({a.file.name}): {e}", file=sys.stderr)
        return 3
    st = structure(rows)
    pd.set_option("display.width", 200)
    print(f"{a.file.name} (sha256 {sha[:12]}): {st.shape[0]} contests, {len(rows)} tiers; season {a.season} week {a.week}")
    print(st.to_string(index=False))
    if not a.apply:
        print("dry run: nothing written (pass --apply)")
        return 0
    from nfl_dfs.bq import load_dataframe, query_df
    from nfl_dfs.config import settings
    table = f"{settings.raw}.dk_payout_ladders"
    n = int(query_df(f"SELECT COUNT(*) n FROM `{table}` WHERE source_sha256 = @sha", {"sha": sha}).n.iloc[0])
    if n:
        print(f"PAYOUT LADDERS REFUSED ({a.file.name}): this content (sha256 {sha[:12]}) is already loaded ({n} rows)", file=sys.stderr)
        return 3
    df = pd.DataFrame(rows).assign(loaded_at=pd.Timestamp.now(tz="UTC"))
    df["contest_start"] = pd.to_datetime(df.contest_start, utc=True, errors="coerce")
    df["captured_at"] = pd.to_datetime(df.captured_at, utc=True)
    load_dataframe(df[COLUMNS], table, write_disposition="WRITE_APPEND")
    print(f"loaded {len(df)} tiers into {table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
