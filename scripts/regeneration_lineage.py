#!/usr/bin/env python3
"""Prove the Sunday regeneration lineage row by row and write an immutable manifest (audit VET-001).

  python scripts/regeneration_lineage.py --vetted-dir .../paid-vetted --replaced-dir .../paid-vetted-replaced \
        --promoted-dir .../paid-vetted-promoted --out lineage.json [--upload-csv upload-...-all.csv] [--entries-csv DKEntries.csv]

Exit 0 when every changed row has a receipted reason, every receipt hash binds its book, the promotion is exactly the
recorded permutation and the optional upload / entries files carry the promoted book; exit 1 otherwise (the manifest is
still written, with status FAILED and the problems). Run it before every upload; nothing here changes a book.
"""
import argparse, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.inference.regeneration_lineage import LineageError, build_manifest, write_manifest_create_once  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--vetted-dir", required=True); ap.add_argument("--replaced-dir", help="omit when no replacement step ran (recorded as replacement: none)"); ap.add_argument("--promoted-dir", required=True)
ap.add_argument("--upload-csv"); ap.add_argument("--entries-csv"); ap.add_argument("--contests"); ap.add_argument("--out", required=True)
a = ap.parse_args()
try:
    contests = None
    if a.contests:
        contests = json.load(open(a.contests)); contests = contests if isinstance(contests, list) else contests.get("contests")
    m = build_manifest(a.vetted_dir, a.replaced_dir, a.promoted_dir, upload_csv=a.upload_csv, entries_csv=a.entries_csv, contests=contests)
    write_manifest_create_once(m, a.out)
except LineageError as exc:
    print(f"LINEAGE FAILED: {exc}", file=sys.stderr); sys.exit(1)
print(f"lineage {m['status']}: {m['rows']} rows, {m['changed_rows']} replaced with reasons, promotion moved {len(m['promotion']['moved'])} rows, "
      f"upload checks {list(m['upload_checks'])} -> {a.out}")
if m["problems"]:
    for p in m["problems"]: print(f"  problem: {p}", file=sys.stderr)
    sys.exit(1)
