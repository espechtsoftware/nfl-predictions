#!/usr/bin/env python3
"""Keep the reviewed weekly operator inputs off this machine, in private storage.

`contests.json` and `chosen-dose.env` are the two files the Sunday build refuses
to start without. They were living only in `$OUT` on one host, so a lost machine
lost them and nothing recorded which version a build actually used.

They must NOT go in this repository: it is public, and contests.json carries the
per-contest entry counts, keep counts and fees, i.e. the week's stake plan. This
tool puts them in the project's private bucket instead, which gives the same
machine independence and versioning without publishing anything.

  validate  shape-check a local pair; no network
  push      validate, then upload as the reviewed inputs for one season/week
  pull      download into $OUT, validate, and write a receipt

The receipt pins each object by uri/generation/sha256/bytes using the chain's
standard identity (research/object_identity.py), and deliberately contains NO
contest ids and no per-contest figures, only aggregates that are already public
in the evidence record. That makes the receipt safe to commit while the values
stay private.

  python scripts/week_inputs.py validate --contests c.json --dose dose.env
  python scripts/week_inputs.py push --season 2026 --week 3 --contests c.json --dose dose.env
  python scripts/week_inputs.py pull --season 2026 --week 3 --out /home/erich/week3-sunday
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import UTC, datetime

DEFAULT_BUCKET = "nfl-predictions-503414-raw"
MANIFEST = "manifest.json"
INPUT_FILES = ("contests.json", "chosen-dose.env")
PREFIX = "week-inputs"
PROJECT = "nfl-predictions-503414"
# Matches build_inputs.assess_files (90 -> 1 on 2026-09-22): a volume floor is not a data-quality
# check, and 90 would fail closed on an ordinary 89-entry week. Every real malformation still fails.
MIN_BOOK_ENTRIES = 1
CONTEST_FIELDS = ("name", "contest_id", "entries", "keep", "fee")
DOSE_KEYS = ("CHOSEN_LEV", "CHOSEN_BOOM")


def object_uri(bucket: str, season: int, week: int, name: str) -> str:
    return f"gs://{bucket}/{PREFIX}/{season}/w{week:02d}/{name}"


def parse_dose(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def validate_dose(text: str) -> list[str]:
    """Mirror what check_build_inputs.py requires, so this cannot pass and that fail."""
    problems = []
    dose = parse_dose(text)
    for key in DOSE_KEYS:
        if key not in dose:
            problems.append(f"chosen-dose is missing {key}")
            continue
        try:
            if int(dose[key]) <= 0:
                problems.append(f"{key} must be positive, got {dose[key]!r}")
        except ValueError:
            problems.append(f"{key} is not an integer: {dose[key]!r}")
    return problems


def validate_contests(text: str, min_entries: int = MIN_BOOK_ENTRIES) -> list[str]:
    problems = []
    try:
        data = json.loads(text)
    except ValueError as exc:
        return [f"contests.json is not valid JSON: {exc}"]
    if isinstance(data, dict):
        data = data.get("contests")
    if not isinstance(data, list) or not data:
        return ["contests.json must be a non-empty JSON list of contest objects"]
    seen = set()
    total = 0
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            problems.append(f"contest {i} is not an object")
            continue
        for field in CONTEST_FIELDS:
            if field not in row:
                problems.append(f"contest {i} is missing {field}")
        cid = str(row.get("contest_id", "")).strip()
        if not cid:
            problems.append(f"contest {i} has an empty contest_id")
        elif cid in seen:
            problems.append(f"contest_id {cid} appears more than once")
        else:
            seen.add(cid)
        for field in ("entries", "keep"):
            if field in row:
                try:
                    value = int(row[field])
                except (TypeError, ValueError):
                    problems.append(f"contest {i} {field} is not an integer")
                    continue
                if field == "entries" and value < 1:
                    problems.append(f"contest {i} entries must be at least 1")
                if field == "keep" and value < 0:
                    problems.append(f"contest {i} keep must not be negative")
                if field == "entries":
                    total += value
        # fee is a MONEY value, not an integer. Real contests.json files carry
        # 0.25 for the quarter satellites; validating it as an int both truncated
        # the total (Week 2 read $238 against the settled $246, exactly the two
        # 16 x $0.25 contests) and would reject "0.25" written as a string.
        if "fee" in row:
            try:
                fee = float(row["fee"])
            except (TypeError, ValueError):
                problems.append(f"contest {i} fee is not a number")
            else:
                if fee < 0:
                    problems.append(f"contest {i} fee must not be negative")
        if "keep" in row and "entries" in row:
            try:
                if int(row["keep"]) > int(row["entries"]):
                    problems.append(f"contest {i} keeps more rows than it enters")
            except (TypeError, ValueError):
                pass
    if total < min_entries:
        problems.append(f"contests total {total} entries, minimum {min_entries}")
    return problems


def summarise(contests_text: str, dose_text: str) -> dict:
    """Aggregates only. No contest ids, no per-contest figures."""
    data = json.loads(contests_text)
    if isinstance(data, dict):
        data = data.get("contests") or []
    dose = parse_dose(dose_text)
    return {
        "contests": len(data),
        "total_entries": sum(int(c.get("entries", 0)) for c in data),
        "total_fee": round(sum(float(c.get("fee", 0)) * int(c.get("entries", 0))
                               for c in data), 2),
        "chosen_lev": int(dose.get("CHOSEN_LEV", 0)),
        "chosen_boom": int(dose.get("CHOSEN_BOOM", 0)),
    }


def _client():
    from google.cloud import storage
    return storage.Client(project=PROJECT)


def _receipt(client, uri: str, raw: bytes) -> dict:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
    from nfl_dfs.research.object_identity import live_object_receipt
    receipt, _ = live_object_receipt(client, uri, raw=raw)
    return receipt


def cmd_validate(a) -> int:
    contests = pathlib.Path(a.contests).read_text()
    dose = pathlib.Path(a.dose).read_text()
    problems = validate_contests(contests, a.min_entries) + validate_dose(dose)
    if problems:
        print("INVALID:")
        for p in problems:
            print(f"  - {p}")
        return 1
    s = summarise(contests, dose)
    print(f"OK: {s['contests']} contests, {s['total_entries']} entries, "
          f"${s['total_fee']:.2f} total fee; dose lev {s['chosen_lev']} boom {s['chosen_boom']}")
    return 0


def cmd_push(a) -> int:
    contests = pathlib.Path(a.contests).read_bytes()
    dose = pathlib.Path(a.dose).read_bytes()
    problems = (validate_contests(contests.decode(), a.min_entries)
                + validate_dose(dose.decode()))
    if problems:
        print("REFUSING to publish invalid inputs:")
        for p in problems:
            print(f"  - {p}")
        return 1
    client = _client()
    out = {}
    for name, raw in zip(INPUT_FILES, (contests, dose)):
        uri = object_uri(a.bucket, a.season, a.week, name)
        bucket_name, _, blob_name = uri[5:].partition("/")
        blob = client.bucket(bucket_name).blob(blob_name)
        blob.upload_from_string(raw)
        out[name] = _receipt(client, uri, raw)
        print(f"  uploaded {uri}")
        print(f"    generation {out[name]['generation']}  sha256 {out[name]['sha256'][:16]}…  "
              f"{out[name]['bytes']} bytes")
    # The manifest is written LAST and is the single commit point. Both files are
    # separate objects, so without it a `pull` overlapping a `push` could install
    # one push's contests beside another push's dose. A pull resolves the pair
    # THROUGH this manifest, by generation, so it sees either the whole old pair
    # or the whole new one.
    manifest = {"schema": "week-inputs-manifest/v1", "season": a.season, "week": a.week,
                "published_utc": datetime.now(UTC).isoformat(),
                "objects": {n: {k: out[n][k] for k in ("uri", "generation", "sha256", "bytes")}
                            for n in INPUT_FILES}}
    m_uri = object_uri(a.bucket, a.season, a.week, MANIFEST)
    m_bucket, _, m_blob = m_uri[5:].partition("/")
    m_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    client.bucket(m_bucket).blob(m_blob).upload_from_string(m_raw)
    print(f"  uploaded {m_uri}  (pins the pair)")
    s = summarise(contests.decode(), dose.decode())
    print(f"\nreviewed inputs for {a.season} week {a.week}: {s['contests']} contests, "
          f"{s['total_entries']} entries, dose lev {s['chosen_lev']} boom {s['chosen_boom']}")
    return 0


def cmd_pull(a) -> int:
    client = _client()
    out_dir = pathlib.Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    m_uri = object_uri(a.bucket, a.season, a.week, MANIFEST)
    m_bucket, _, m_blob = m_uri[5:].partition("/")
    m_handle = client.bucket(m_bucket).blob(m_blob)
    if not m_handle.exists():
        print(f"MISSING: {m_uri}\n  push the reviewed inputs first "
              f"(python scripts/week_inputs.py push --season {a.season} --week {a.week} …)")
        return 1
    manifest = json.loads(m_handle.download_as_bytes())
    pinned = manifest.get("objects", {})
    missing = [n for n in INPUT_FILES if n not in pinned]
    if missing:
        print(f"REFUSING: {m_uri} does not pin {missing}")
        return 1

    # Fetch each file AT THE GENERATION THE MANIFEST NAMES, so an operator push
    # landing mid-pull cannot produce a mixed pair.
    receipts, texts = {}, {}
    for name in INPUT_FILES:
        want = pinned[name]
        uri = want["uri"]
        bucket_name, _, blob_name = uri[5:].partition("/")
        blob = client.bucket(bucket_name).blob(blob_name, generation=int(want["generation"]))
        try:
            raw = blob.download_as_bytes()
        except Exception as exc:
            print(f"REFUSING: cannot read {uri} at the pinned generation "
                  f"{want['generation']}: {exc}")
            return 1
        receipt = _receipt(client, uri, raw)
        if receipt["sha256"] != want["sha256"]:
            print(f"REFUSING: {uri} generation {want['generation']} hashes "
                  f"{receipt['sha256'][:16]}…, manifest says {want['sha256'][:16]}…")
            return 1
        receipt["generation"] = str(want["generation"])
        receipts[name] = receipt
        texts[name] = raw.decode()

    problems = (validate_contests(texts["contests.json"], a.min_entries)
                + validate_dose(texts["chosen-dose.env"]))
    if problems:
        print("REFUSING to install invalid inputs (nothing written):")
        for p in problems:
            print(f"  - {p}")
        return 1

    for name, text in texts.items():
        (out_dir / name).write_text(text)
    s = summarise(texts["contests.json"], texts["chosen-dose.env"])
    receipt = {"schema": "week-inputs/v2", "season": a.season, "week": a.week,
               "fetched_utc": datetime.now(UTC).isoformat(), "out": str(out_dir),
               "manifest_published_utc": manifest.get("published_utc"),
               "objects": receipts, "summary": s}
    receipt_path = out_dir / "week-inputs-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"installed into {out_dir}:")
    for name, r in receipts.items():
        print(f"  {name}  generation {r['generation']}  sha256 {r['sha256'][:16]}…")
    print(f"  {s['contests']} contests, {s['total_entries']} entries, "
          f"dose lev {s['chosen_lev']} boom {s['chosen_boom']}")
    print(f"receipt: {receipt_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--min-entries", type=int, default=MIN_BOOK_ENTRIES)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate"); v.add_argument("--contests", required=True); v.add_argument("--dose", required=True)
    p = sub.add_parser("push"); p.add_argument("--season", type=int, required=True); p.add_argument("--week", type=int, required=True)
    p.add_argument("--contests", required=True); p.add_argument("--dose", required=True)
    g = sub.add_parser("pull"); g.add_argument("--season", type=int, required=True); g.add_argument("--week", type=int, required=True)
    g.add_argument("--out", required=True)

    a = ap.parse_args(argv)
    return {"validate": cmd_validate, "push": cmd_push, "pull": cmd_pull}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
