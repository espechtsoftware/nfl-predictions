#!/usr/bin/env python3
"""Study 60's ladder rows (the format agreed with the reviewer, 2026-10-07): one PRIVATE CSV per week holding his big
contests' lines from the payout-ladder table. Positions and counts only, never dollars.

    python scripts/cash_line_rows.py --week 5 --plan-s24 <the week's s38_plan output, e.g. plan-week5-rev6-s24.json>
        [--out-dir ~/private/cash-line]

Columns: contest_id, week, role, entries, size, paid_places, cash500_last_position, seat_last_position, ladder_sha256.
- role. The s24 plan's `big` flag is his big-win rule as s38_plan.convert sets it. The $20 Millionaire tickets and the
  $125 FFWC qualifier are NOT big and are left out. Precedence is big > gpp > sat:
  - "big": a contest he enters at a fee of $333 or more, or on a won ticket (a plan contest marked "ticket": true);
  - "gpp": a multi-tier big contest, prize "$500+ finish" (the Millionaire); its line is cash500_last_position;
  - "sat": a single-prize big contest, a seat; its line is seat_last_position.
- entries: his entries in the contest (the plan). size: the contest's maximum entries. paid_places: the last paid
  position.
- cash500_last_position: the last position whose CASH prize is >= 500 (0 if none).
- seat_last_position: the last position awarding a ticket (0 if none).
- ladder_sha256: the capture the ladder came from (`nfl_raw.v_dk_payout_ladder_latest.source_sha256`).
The file is written ONCE (an existing file is refused), only under ~/private, with <file>.sha256 beside it. A big
contest without a ladder refuses the week.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

CASH_LINE = 500.0
BIG_FEE = 333.0
GPP_PRIZE = "$500+ finish"
COLUMNS = ["contest_id", "week", "role", "entries", "size", "paid_places", "cash500_last_position", "seat_last_position",
           "ladder_sha256"]
PRIVATE = Path.home() / "private"


def role_of(contest: dict) -> str | None:
    """big > gpp > sat for a big contest; None (left out) for one that is not big."""
    if not contest.get("big"):
        return None
    if float(contest.get("fee") or 0.0) >= BIG_FEE or contest.get("ticket") is True:
        return "big"
    if str(contest.get("prize", "")).strip() == GPP_PRIZE:
        return "gpp"
    return "sat"


def ladder_lines(tiers: pd.DataFrame) -> dict:
    """One contest's tiers -> size, paid_places, cash500_last_position, seat_last_position, ladder_sha256."""
    shas = sorted(set(tiers.source_sha256.astype(str)))
    if len(shas) != 1:
        raise ValueError(f"contest {tiers.contest_id.iloc[0]}: {len(shas)} ladder captures in the latest view")
    cash = pd.to_numeric(tiers.cash_value, errors="coerce").fillna(0.0)
    ticket = pd.to_numeric(tiers.ticket_value, errors="coerce").fillna(0.0)
    last = pd.to_numeric(tiers.max_position, errors="coerce").fillna(0).astype(int)
    paid = last[(cash > 0) | (ticket > 0)]
    return {"size": int(pd.to_numeric(tiers.max_entries, errors="coerce").max()),
            "paid_places": int(paid.max()) if len(paid) else 0,
            "cash500_last_position": int(last[cash >= CASH_LINE].max()) if (cash >= CASH_LINE).any() else 0,
            "seat_last_position": int(last[ticket > 0].max()) if (ticket > 0).any() else 0,
            "ladder_sha256": shas[0]}


def rows(plan: list[dict], tiers: pd.DataFrame, week: int) -> tuple[list[dict], list[str]]:
    """The week's rows in plan order, and the warnings: a line that disagrees with the plan's seats."""
    out, warn = [], []
    by = {str(c): g for c, g in tiers.groupby(tiers.contest_id.astype(str))}
    for c in plan:
        role = role_of(c)
        if role is None:
            continue
        cid = str(c["contest_id"])
        if cid not in by:
            raise ValueError(f"big contest {cid} ({c.get('name')}) has no ladder in nfl_raw.v_dk_payout_ladder_latest")
        lines = ladder_lines(by[cid])
        line = lines["cash500_last_position"] if role == "gpp" else lines["seat_last_position"] if role == "sat" else None
        if line is not None and c.get("seats") is not None and int(c["seats"]) != line:
            warn.append(f"{cid} ({c.get('name')}, {role}): the ladder's line {line} != the plan's seats {c['seats']}")
        out.append({"contest_id": cid, "week": int(week), "role": role, "entries": int(c["entries"]), **lines})
    return out, warn


def write_once(rows_: list[dict], out_dir: Path, week: int) -> Path:
    out_dir = Path(out_dir).expanduser().resolve()
    if PRIVATE.resolve() not in (out_dir, *out_dir.parents):
        raise ValueError(f"{out_dir} is not under {PRIVATE}: the file names his contests and stays private")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"cash-lines-w{week:02d}.csv"
    if path.exists():
        raise FileExistsError(f"{path} exists: written once")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows_)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (out_dir / f"{path.name}.sha256").write_text(f"{digest}  {path.name}\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--plan-s24", type=Path, required=True, help="the week's s38_plan output (contest_id, big, prize, fee, entries, seats)")
    ap.add_argument("--out-dir", type=Path, default=PRIVATE / "cash-line")
    a = ap.parse_args(argv)
    plan = json.loads(a.plan_s24.read_text())
    plan = plan["contests"] if isinstance(plan, dict) else plan
    ids = [str(c["contest_id"]) for c in plan if role_of(c)]
    if not ids:
        raise SystemExit(f"{a.plan_s24}: no big contest")
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    tiers = query_df(f"SELECT contest_id, max_entries, max_position, cash_value, ticket_value, source_sha256 "
                     f"FROM `{settings.raw}.v_dk_payout_ladder_latest` WHERE contest_id IN UNNEST(@ids)", {"ids": ids})
    out, warn = rows(plan, tiers, a.week)
    for x in warn:
        print(f"WARNING: {x}")
    path = write_once(out, a.out_dir, a.week)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    roles = {r: sum(1 for x in out if x["role"] == r) for r in ("big", "gpp", "sat")}
    print(f"W{a.week}: {len(out)} big contests ({roles}) -> {path} (sha256 {digest}); plan {a.plan_s24.name} "
          f"(sha256 {hashlib.sha256(a.plan_s24.read_bytes()).hexdigest()[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
