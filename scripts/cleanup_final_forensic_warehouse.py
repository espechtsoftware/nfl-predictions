#!/usr/bin/env python3
"""Delete and verify the temporary final-forensic BigQuery corpus.

The four tables are isolated from production while an independent review is
performed.  This command is the mandatory, manifest-bound Week-1 cleanup gate:
it refuses a partial/unrelated corpus, deletes only the four frozen table ids,
and writes a receipt only after all four are independently absent.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from nfl_dfs.research.final_forensic import (
    WAREHOUSE_TABLE_SCHEMAS,
    validate_freeze_manifest,
)


PROJECT = "nfl-predictions-503414"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--confirm-manifest-sha", required=True)
    parser.add_argument("--receipt", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--delete", action="store_true")
    action.add_argument("--verify-only", action="store_true")
    return parser


def _schema(table: bigquery.Table) -> list[dict[str, str]]:
    return [
        {"name": field.name, "type": field.field_type, "mode": field.mode}
        for field in table.schema
    ]


def _load_manifest(path: Path, confirmation: str) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_freeze_manifest(manifest, repo_root=Path.cwd(), verify_files=False)
    if manifest["manifest_sha256"] != confirmation:
        raise RuntimeError("typed manifest confirmation differs")
    return manifest


def delete_corpus(
    client: bigquery.Client,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    contract = manifest["warehouse_retention"]
    table_rows = {row["id"]: row for row in contract["tables"]}
    verified: list[dict[str, Any]] = []
    for table_id, expected_schema in WAREHOUSE_TABLE_SCHEMAS.items():
        table_name = table_rows[table_id]["table"]
        try:
            table = client.get_table(table_name)
        except NotFound as exc:
            raise RuntimeError(
                f"cleanup requires the complete four-table corpus; missing {table_name}"
            ) from exc
        if (
            _schema(table) != expected_schema
            or (table.labels or {}).get("manifest")
            != manifest["manifest_sha256"][:32]
            or manifest["manifest_sha256"] not in (table.description or "")
            or table.expires is None
        ):
            raise RuntimeError(f"refusing unverified forensic table: {table_name}")
        verified.append({
            "id": table_id,
            "table": table_name,
            "rows_before_delete": int(table.num_rows),
            "scheduled_expiry": table.expires.isoformat(),
        })
    for row in verified:
        client.delete_table(row["table"], not_found_ok=False)
    for row in verified:
        try:
            client.get_table(row["table"])
        except NotFound:
            row["verified_absent"] = True
        else:
            raise RuntimeError(f"forensic table remains after deletion: {row['table']}")
    return {
        "manifest_sha256": manifest["manifest_sha256"],
        "cleanup_policy": contract["cleanup_policy"],
        "cleanup_deadline": contract["cleanup_deadline"],
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "tables": verified,
        "production_preflight": "pass",
    }


def verify_absent(
    client: bigquery.Client,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    expected = {row["table"] for row in manifest["warehouse_retention"]["tables"]}
    recorded = {row["table"] for row in receipt.get("tables", [])}
    if (
        receipt.get("manifest_sha256") != manifest["manifest_sha256"]
        or receipt.get("production_preflight") != "pass"
        or expected != recorded
        or not all(row.get("verified_absent") is True for row in receipt["tables"])
    ):
        raise RuntimeError("cleanup receipt differs from the frozen corpus")
    remaining = []
    for table_name in sorted(expected):
        try:
            client.get_table(table_name)
        except NotFound:
            continue
        remaining.append(table_name)
    if remaining:
        raise RuntimeError(f"forensic tables remain before production: {remaining}")
    return {
        "manifest_sha256": manifest["manifest_sha256"],
        "verified_absent_tables": sorted(expected),
        "production_preflight": "pass",
    }


def main() -> int:
    args = _parser().parse_args()
    manifest = _load_manifest(Path(args.manifest), args.confirm_manifest_sha)
    receipt_path = Path(args.receipt)
    client = bigquery.Client(project=PROJECT, location="US")
    if args.delete:
        if receipt_path.exists():
            raise RuntimeError("cleanup receipt already exists; refusing to replace it")
        receipt = delete_corpus(client, manifest)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, sort_keys=True))
    else:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        print(json.dumps(verify_absent(client, manifest, receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
