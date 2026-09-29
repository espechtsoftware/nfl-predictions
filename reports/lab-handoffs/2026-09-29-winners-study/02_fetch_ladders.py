"""Payout ladders for every contest of a week from DraftKings' PUBLIC contest API (no login; the call scripts/dk_contest_details.py
makes), paced. Contest ids are read from the warehouse at run time; none are written in this file.

    python 02_fetch_ladders.py 2 contest-details-2026-w02.json
"""
import json, sys, time, urllib.request
from google.cloud import bigquery
week, out = int(sys.argv[1]), sys.argv[2]
P = "nfl-predictions-503414"
ids = [r.contest_id for r in bigquery.Client(project=P).query(
    f"SELECT DISTINCT contest_id FROM `{P}.nfl_raw.contest_entries` WHERE season = 2026 AND week = {week}").result()]
URL = "https://api.draftkings.com/contests/v1/contests/{cid}?format=json"
res, failed = {}, []
for cid in ids:
    try:
        with urllib.request.urlopen(URL.format(cid=cid), timeout=20) as r:
            d = json.load(r)["contestDetail"]
        res[str(cid)] = {"name": d.get("name"), "entries": d.get("entries"), "max": d.get("maximumEntries"), "maxPerUser": d.get("maximumEntriesPerUser"),
                         "fee": d.get("entryFee"), "payout": d.get("totalPayouts"), "state": d.get("contestStateDetail"), "payoutSummary": d.get("payoutSummary")}
    except Exception as exc:                                  # named below, never a partial success
        failed.append(f"{cid}: {exc}")
    time.sleep(1.0)
if failed:
    sys.exit("contest details FAILED for: " + "; ".join(failed))
json.dump(res, open(out, "w"), indent=1)
print(len(res), "ladders written to", out)
