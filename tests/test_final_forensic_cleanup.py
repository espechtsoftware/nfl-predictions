from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from google.api_core.exceptions import NotFound
from google.cloud import bigquery
import pytest

from nfl_dfs.research.final_forensic import (
    WAREHOUSE_TABLE_PREFIX,
    WAREHOUSE_TABLE_SCHEMAS,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cleanup_final_forensic_warehouse",
    ROOT / "scripts/cleanup_final_forensic_warehouse.py",
)
assert SPEC and SPEC.loader
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


def _manifest():
    return {
        "manifest_sha256": "a" * 64,
        "warehouse_retention": {
            "cleanup_policy": "delete_after_review_before_week1",
            "cleanup_deadline": "before_first_2026_production_build",
            "tables": [
                {
                    "id": table_id,
                    "table": WAREHOUSE_TABLE_PREFIX + table_id,
                    "schema": schema,
                }
                for table_id, schema in WAREHOUSE_TABLE_SCHEMAS.items()
            ],
        },
    }


class _Client:
    def __init__(self, manifest, *, omit=None):
        self.tables = {}
        for row in manifest["warehouse_retention"]["tables"]:
            if row["id"] == omit:
                continue
            self.tables[row["table"]] = SimpleNamespace(
                schema=[
                    bigquery.SchemaField(
                        field["name"], field["type"], mode=field["mode"]
                    )
                    for field in row["schema"]
                ],
                labels={"manifest": manifest["manifest_sha256"][:32]},
                description=f"Manifest {manifest['manifest_sha256']}.",
                expires=datetime(2026, 11, 1, tzinfo=timezone.utc),
                num_rows=123,
            )

    def get_table(self, table):
        if table not in self.tables:
            raise NotFound("missing")
        return self.tables[table]

    def delete_table(self, table, *, not_found_ok):
        assert not not_found_ok
        del self.tables[table]


def test_cleanup_requires_complete_verified_corpus_then_proves_absence():
    manifest = _manifest()
    client = _Client(manifest)
    receipt = cleanup.delete_corpus(client, manifest)

    assert receipt["production_preflight"] == "pass"
    assert len(receipt["tables"]) == 4
    assert all(row["verified_absent"] for row in receipt["tables"])
    assert not client.tables
    verified = cleanup.verify_absent(client, manifest, receipt)
    assert verified["production_preflight"] == "pass"


def test_cleanup_refuses_partial_corpus_without_deleting_anything():
    manifest = _manifest()
    client = _Client(manifest, omit="oracle_rosters")
    with pytest.raises(RuntimeError, match="complete four-table corpus"):
        cleanup.delete_corpus(client, manifest)
    assert len(client.tables) == 3
