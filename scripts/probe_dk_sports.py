"""DK sports-inventory probe (2026-08-04). Run this in LATE AUGUST to
verify the CFB collection filter before the first Saturday:

    python scripts/probe_dk_sports.py

Expected once DK posts CFB slates: a sportId=5 row with nonzero count
AND `cfb_draft_groups()` returning the same number. If the lobby shows
CFB contests but sportId=5 is absent here, DK changed the id — update
dk_client.CFB_SPORT_ID to whichever sportId carries the college groups
(identify by group count spiking on Saturdays and team-style names in
fetch_draftables output). NFL sanity: sportId=1 should always be the
largest bucket in-season.
"""
import sys
from collections import Counter

import requests

sys.path.insert(0, "src")
from nfl_dfs.ingest import dk_client

s = requests.Session()
r = s.get(dk_client.DK_GROUPS, headers=dk_client.HEADERS, timeout=30)
r.raise_for_status()
groups = r.json().get("draftGroups", [])
print(f"total draft groups: {len(groups)}")
for (sid,), n in sorted(Counter((g.get("sportId"),) for g in groups).items(),
                        key=lambda x: -x[1]):
    tag = {1: "NFL", 5: "CFB"}.get(sid, "")
    print(f"  sportId={sid:>3} {tag:>4}: {n}")
cfb = dk_client.cfb_draft_groups(s)
print(f"cfb_draft_groups() -> {len(cfb)}")
nfl = dk_client.nfl_draft_groups(s)
print(f"nfl_draft_groups() -> {len(nfl)}")
