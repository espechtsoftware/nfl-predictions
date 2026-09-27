#!/usr/bin/env python3
"""Write a local page of standings links for the week's entered contests (operator request 2026-09-27; nothing automated).

For each contest in the week's private contests.json, the page lists the contest's name and our entry count, with two links
the operator clicks in their own signed-in browser:
  * "Export CSV": DraftKings' own standings export for that contest (downloads the file when signed in);
  * "Contest page": the contest's page on DraftKings, as a fallback.
Nothing here contacts DraftKings; it only writes an HTML file. Write it NEXT TO contests.json (private), never in the repo.

    python scripts/dk_standings_links.py --contests ~/week3-sunday/contests.json --out ~/week3-sunday/standings-links.html
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

EXPORT_URL = "https://www.draftkings.com/contest/exportfullstandingscsv/{cid}"
CONTEST_URL = "https://www.draftkings.com/contest/gamecenter/{cid}"


def page(contests: list[dict], title: str) -> str:
    rows = []
    for i, c in enumerate(contests, 1):
        cid = str(c["contest_id"]).strip()
        if not cid.isdigit():
            raise ValueError(f"contest_id {cid!r} is not a numeric DraftKings id")
        rows.append(f"<tr><td>{i}</td><td>{html.escape(str(c.get('name', cid)))}</td><td>{int(c.get('entries', 0))}</td>"
                    f"<td><a href='{EXPORT_URL.format(cid=cid)}'>Export CSV</a></td>"
                    f"<td><a href='{CONTEST_URL.format(cid=cid)}' target='_blank'>Contest page</a></td>"
                    f"<td><code>{cid}</code></td></tr>")
    return ("<!doctype html><html><head><meta charset='utf-8'><title>" + html.escape(title) + "</title>"
            "<style>body{font-family:sans-serif;margin:16px}td,th{padding:4px 10px;border-bottom:1px solid #ddd}"
            "a{font-weight:600}</style></head><body><h2>" + html.escape(title) + "</h2>"
            f"<p>{len(contests)} contests. Sign in to DraftKings in this browser first, then click each Export CSV link "
            "(one at a time).</p><table><tr><th>#</th><th>Contest</th><th>Our entries</th><th></th><th></th><th>id</th></tr>"
            + "".join(rows) + "</table></body></html>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contests", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", default="DraftKings standings exports")
    a = ap.parse_args(argv)
    data = json.loads(a.contests.read_text())
    data = data if isinstance(data, list) else data.get("contests")
    if not isinstance(data, list) or not data:
        raise SystemExit("contests.json must be a non-empty list")
    a.out.write_text(page(data, a.title))
    print(f"wrote {a.out}: {len(data)} contests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
