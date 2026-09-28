#!/usr/bin/env python3
"""Fetch each entered contest's public details (field size, state, entry fee, payout ladder) from DraftKings' public
contest API and write one JSON keyed by contest id -- the file the rehearsal, the ticket evaluator and the Monday
scoreboard read as `contest-details-<date>.json` (Week 3: produced inline on 2026-09-27; this is the tracked version).

  python scripts/dk_contest_details.py --contests contests.json --out contest-details-YYYYMMDD.json [--sleep 0.4]

No login, no account: `https://api.draftkings.com/contests/v1/contests/<id>?format=json`. Contest ids are public; the
output holds no entries and no user data. It is paced (one request every --sleep seconds) and fails loudly on any id
that does not resolve (exit 2, the ids named) rather than writing a partial file.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "https://api.draftkings.com/contests/v1/contests/{cid}?format=json"
KEEP = ("name", "entries", "maximumEntries", "maximumEntriesPerUser", "entryFee", "totalPayouts", "contestStateDetail",
        "draftGroupId", "contestStartTime", "payoutSummary")


def fetch(cid: str, timeout: int = 20) -> dict:
    with urllib.request.urlopen(URL.format(cid=cid), timeout=timeout) as r:
        d = json.load(r)["contestDetail"]
    out = {k: d.get(k) for k in KEEP}
    out["entries"] = d.get("entries"); out["max"] = d.get("maximumEntries"); out["fee"] = d.get("entryFee")
    out["state"] = d.get("contestStateDetail"); out["payout"] = d.get("totalPayouts")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contests", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sleep", type=float, default=0.4)
    a = ap.parse_args(argv)
    c = json.loads(a.contests.read_text()); c = c if isinstance(c, list) else c["contests"]
    ids = [str(x["contest_id"]) for x in c]
    if len(set(ids)) != len(ids):
        print("duplicate contest ids in the contests file", file=sys.stderr); return 2
    out, failed = {}, []
    for cid in ids:
        try:
            out[cid] = fetch(cid)
        except Exception as exc:                      # noqa: BLE001 - named per id below
            failed.append(f"{cid}: {exc}")
        time.sleep(a.sleep)
    if failed:
        print("contest details FAILED for: " + "; ".join(failed), file=sys.stderr)
        return 2
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    for cid, v in out.items():
        print(f"{cid} {v['state']} {v['entries']}/{v['max']} fee {v['fee']} tiers {len(v.get('payoutSummary') or [])} {str(v['name'])[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
