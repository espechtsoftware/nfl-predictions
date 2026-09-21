#!/usr/bin/env python3
"""Append an in-season SIS team-context plan's artifacts to the two team-context tables (append-once by team-week).

  python scripts/import_sis_team_context_weekly.py --input-dir sis/weekly/<run> --plan automation/sis/plans/<plan>.json [--write] [--audit OUT.json]

Without --write it validates, merges and reports what would be appended and which team-weeks already exist.
"""
import argparse, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.ingest.sis_team_context_weekly import run  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--input-dir", required=True); ap.add_argument("--plan", required=True); ap.add_argument("--write", action="store_true"); ap.add_argument("--audit")
a = ap.parse_args()
audit = run(a.input_dir, a.plan, write=a.write)
text = json.dumps(audit, indent=2, default=str)
if a.audit: pathlib.Path(a.audit).write_text(text + "\n")
for fam, rec in audit["families"].items():
    print(f"{fam}: {rec.get('status')} | table {rec.get('table')} | merged {rec.get('rows_merged')} | to append {rec.get('rows_to_append')} | already present {len(rec.get('keys_already_present', []))} | coverage {rec.get('coverage_merged')}")
