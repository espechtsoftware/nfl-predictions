#!/usr/bin/env python3
"""R5 (outside-the-box plan; operator-approved 2026-09-24): snapshot Kalshi's public NFL player and fantasy markets.

Capture only. Nothing here enters a projection until the markets are graded (plan §2, from Week 6). Public API, no
account. Paced, with backoff on HTTP 429.
- **The snapshot:** every OPEN market of each series in SERIES, paginated. Each market's full raw record, as Kalshi
  returns it, is written with the capture time to ONE gzipped JSONL file per snapshot:
  `<out>/kalshi-<label>-<UTC stamp>.jsonl.gz`.
- **The manifest** sits beside it: per-series counts, the file's sha256 and bytes.
- **Upload:** with --upload, both files go to the private bucket
  (gs://nfl-predictions-503414-raw/kalshi/season=S/week=WW/), CREATE-ONLY (if_generation_match=0), so a snapshot is
  never overwritten. Never commit a snapshot to the public repo.

    python scripts/kalshi_capture.py --season 2026 --week 3 --label sat-build --out ~/week3-sunday/kalshi [--upload]
    python scripts/kalshi_capture.py ... --label t70 ...          # Sunday, at the T-70 build
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.elections.kalshi.com/trade-api/v2"
BUCKET = "nfl-predictions-503414-raw"
# The series with open weekly markets on 2026-09-25 (discovered from /series?category=Sports), plus the ladder and anytime-TD
# series named in the review (captured whenever they list open markets).
SERIES = ("KXNFLFFPTS", "KXNFLFFPTSLADDER", "KXNFLFFWEEKLEAD", "KXNFLFFWEEKTOP", "KXNFLANYTD", "KXNFLTD", "KXNFL2TD",
          "KXNFLFIRSTTD", "KXNFLTEAMFIRSTTD", "KXNFLFIRSTTDTEAM", "KXNFLDSTTD", "KXNFLPASSYDS", "KXNFLPASSTDS",
          "KXNFLPASSINT", "KXNFLPASSCOMP", "KXNFLPASSATT", "KXNFLRSHYDS", "KXNFLRSHATT", "KXNFLRECYDS", "KXNFLREC",
          "KXNFLRRYDS", "KXNFLLONGREC", "KXNFLTEAMSACK", "KXNFLTEAMYDS")
PAGE, PACE, MAX_TRIES = 1000, 0.35, 6


def fetch_json(url: str, opener=urllib.request.urlopen, sleep=time.sleep) -> dict:
    """GET with backoff on 429 / 5xx / network errors (1, 2, 4, 8, 16 s); raises after MAX_TRIES."""
    for attempt in range(MAX_TRIES):
        try:
            with opener(url, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == MAX_TRIES - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == MAX_TRIES - 1:
                raise
        sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def series_markets(series: str, opener=urllib.request.urlopen, sleep=time.sleep) -> list[dict]:
    """Every open market of one series, following the cursor."""
    out, cursor = [], ""
    while True:
        q = {"series_ticker": series, "status": "open", "limit": PAGE}
        if cursor:
            q["cursor"] = cursor
        d = fetch_json(f"{API}/markets?{urllib.parse.urlencode(q)}", opener, sleep)
        out.extend(d.get("markets") or [])
        cursor = d.get("cursor") or ""
        sleep(PACE)
        if not cursor or not d.get("markets"):
            return out


def snapshot(label: str, season: int, week: int, out_dir: Path, opener=urllib.request.urlopen, sleep=time.sleep,
             now: datetime | None = None) -> tuple[Path, Path, dict]:
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    data, man = out_dir / f"kalshi-{label}-{stamp}.jsonl.gz", out_dir / f"kalshi-{label}-{stamp}.manifest.json"
    if data.exists() or man.exists():
        raise SystemExit(f"{data.name} exists; a snapshot is written once")
    counts, errors = {}, {}
    with gzip.open(data, "wt", encoding="utf-8") as fh:
        for s in SERIES:
            try:
                ms = series_markets(s, opener, sleep)
            except Exception as exc:                          # one bad series never loses the rest; it is recorded
                errors[s] = repr(exc)[:300]
                continue
            counts[s] = len(ms)
            for m in ms:
                fh.write(json.dumps({"captured_utc": now.isoformat(), "series": s, "market": m}, sort_keys=True) + "\n")
    raw = data.read_bytes()
    manifest = {"source": API, "season": season, "week": week, "label": label, "captured_utc": now.isoformat(),
                "series_counts": counts, "series_errors": errors, "markets": sum(counts.values()),
                "file": data.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    man.write_text(json.dumps(manifest, indent=1) + "\n")
    return data, man, manifest


def upload(paths: list[Path], season: int, week: int) -> list[str]:
    from google.cloud import storage
    bucket = storage.Client().bucket(BUCKET)
    uris = []
    for p in paths:
        name = f"kalshi/season={season}/week={week:02d}/{p.name}"
        bucket.blob(name).upload_from_filename(str(p), if_generation_match=0)      # create-only: never overwrite
        uris.append(f"gs://{BUCKET}/{name}")
    return uris


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--label", required=True, help="e.g. sat-build or t70")
    ap.add_argument("--out", type=Path, required=True); ap.add_argument("--upload", action="store_true")
    a = ap.parse_args(argv)
    data, man, m = snapshot(a.label, a.season, a.week, a.out.expanduser())
    print(f"kalshi {a.label}: {m['markets']} markets from {len(m['series_counts'])} series "
          f"({len(m['series_errors'])} failed: {sorted(m['series_errors'])}) -> {data} sha256 {m['sha256'][:16]}")
    if a.upload:
        for u in upload([data, man], a.season, a.week):
            print("uploaded", u)
    return 1 if m["series_errors"] and not m["series_counts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
