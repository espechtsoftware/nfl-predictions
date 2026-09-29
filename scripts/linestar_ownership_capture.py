#!/usr/bin/env python3
"""Live capture of LineStar's PROJECTED ownership for the Sunday main slate (PREREG-O1, third arm; L15's prospective
confirmation, laptop 2026-09-29 12:36). Pre-lock by construction: the file carries its own UTC capture time.

    python scripts/linestar_ownership_capture.py --season 2026 --week 4 --out <dir> [--label saturday|t70]

Fetches LineStar's public GetSalariesV5 (the same endpoint and pacing as linestar_backfill.py; third-party data, kept
under the week's private directory / the private bucket, never committed), finds the period "Week W, SEASON", takes the
Main slate's Ownership.Projected, and writes <out>/linestar-own-<label>-<utc>.csv (name, pos, team, opp, salary,
own_proj) plus a receipt (sha256, captured_at_utc, period id, slate id, row counts). Refuses (exit 2, named) when the
period, the Main slate or the projected ownership is missing, or the file would be empty. Grading is O1's rule
(within-slate Spearman with the realized Millionaire ownership), done Monday beside FP and LAG.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

API = "https://www.linestarapp.com/DesktopModules/DailyFantasyApi/API/Fantasy/GetSalariesV5?sport=1&site=1&periodId={pid}"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research"}


def period_id(periods: list[dict], season: int, week: int) -> int:
    for p in periods:
        m = re.match(r"^Week (\d+), (\d{4})$", str(p.get("Name", "")))
        if m and int(m.group(2)) == season and int(m.group(1)) == week:
            return int(p["Id"])
    raise SystemExit(f"LineStar lists no period 'Week {week}, {season}'")


def projected_rows(payload: dict) -> tuple[list[dict], dict]:
    """The Main slate's players with a projected ownership. Returns (rows, meta); refuses by name on any gap."""
    own = payload.get("Ownership") or {}
    mains = [s for s in own.get("Slates", []) if s.get("SlateName") == "Main" and s.get("Mode") == 0]
    if not mains:
        raise SystemExit("no Main slate (SlateName == 'Main', Mode 0) in the LineStar payload")
    sid = mains[0]["Id"]
    proj = {o["SalaryId"]: o["Owned"] for o in (own.get("Projected") or {}).get(str(sid), [])}
    if not proj:
        raise SystemExit(f"no projected ownership for the Main slate (id {sid}) yet")
    try:
        sal = json.loads(payload["SalaryContainerJson"])["Salaries"]
    except (KeyError, ValueError, TypeError) as exc:
        raise SystemExit(f"unreadable SalaryContainerJson: {exc}") from None
    rows = [{"name": r["Name"], "pos": str(r["POS"]).upper(), "team": r.get("PTEAM"), "opp": r.get("OTEAM"),
             "salary": r.get("SAL"), "own_proj": float(proj[r["Id"]]), "linestar_salary_id": r["Id"], "linestar_pid": r.get("PID")}
            for r in sal if r["Id"] in proj]
    if not rows:
        raise SystemExit("the projected ownership names no salary row of the Main slate")
    return rows, {"slate_id": sid, "projected_rows": len(proj), "salary_rows": len(sal)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True); ap.add_argument("--label", default="capture")
    ap.add_argument("--payload", type=Path, help="tests: read this saved payload instead of fetching")
    ap.add_argument("--min-rows", type=int, default=100, help="refuse a capture with fewer projected players (LineStar fills the week's "
                                                             "projections late in the week; a Tuesday pull held 5 rows)")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    if a.payload:
        payload = json.loads(a.payload.read_text()); pid = None
    else:
        import time
        import requests
        s = requests.Session()
        p0 = s.get(API.format(pid=0), headers=HEADERS, timeout=30); p0.raise_for_status()
        pid = period_id(p0.json().get("Periods", []), a.season, a.week)
        time.sleep(1.2)
        r = s.get(API.format(pid=pid), headers=HEADERS, timeout=30); r.raise_for_status()
        payload = r.json()
    rows, meta = projected_rows(payload)
    if len(rows) < a.min_rows:
        raise SystemExit(f"only {len(rows)} players carry a projected ownership (need >= {a.min_rows}): LineStar has not filled "
                         f"{a.season} W{a.week} yet; nothing written")
    a.out.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    csv_path = a.out / f"linestar-own-{a.label}-{stamp}.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    raw_path = a.out / f"linestar-own-{a.label}-{stamp}.payload.json"
    raw_path.write_text(json.dumps(payload))
    receipt = {"kind": "LineStar projected ownership, live capture (PREREG-O1 third arm)", "season": a.season, "week": a.week,
               "label": a.label, "captured_at_utc": now.isoformat(), "period_id": pid, **meta, "rows": len(rows),
               "csv": csv_path.name, "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
               "payload": raw_path.name, "payload_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
               "source": "third-party (LineStar); private storage only"}
    (a.out / f"linestar-own-{a.label}-{stamp}.receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(f"LineStar projected ownership: {len(rows)} players of the Main slate (period {pid}, slate {meta['slate_id']}) "
          f"captured {now:%Y-%m-%dT%H:%M:%SZ} -> {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
