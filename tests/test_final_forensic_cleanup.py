from __future__ import annotations

from copy import deepcopy
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


def _binding(suffix: str, manifest_sha: str, file_sha: str):
    manifest = {
        "manifest_sha256": manifest_sha,
        "warehouse_retention": {
            "cleanup_policy": "delete_after_review_before_week1",
            "cleanup_deadline": "before_first_2026_production_build",
            "isolation_dataset": cleanup.ISOLATION_DATASET,
            "tables": [
                {
                    "id": table_id,
                    "table": WAREHOUSE_TABLE_PREFIX + table_id + suffix,
                    "schema": schema,
                }
                for table_id, schema in WAREHOUSE_TABLE_SCHEMAS.items()
            ],
        },
    }
    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha,
        "manifest_file_sha256": file_sha,
    }


def _bindings():
    return [
        _binding("", "a" * 64, "c" * 64),
        _binding("_repair4", "b" * 64, "d" * 64),
    ]


def test_tracked_repair3_and_repair4_manifest_bytes_are_frozen():
    base = (
        ROOT
        / "reports/final-forensic-runs/20260814-final-preseason-forensic-v1"
    )
    bindings = [
        cleanup._load_manifest(
            base / "freeze_manifest_repair3.json",
            "122303a1fc14ae76c9379010eb632b8c4ae837408d4726fe47611ec88be20ce7",
        ),
        cleanup._load_manifest(
            base / "freeze_manifest_repair4.json",
            "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02",
        ),
    ]
    contract = cleanup._aggregate_contract(bindings)
    assert len(contract["table_inventory"]) == 8
    assert {
        row["manifest_file_sha256"] for row in contract["manifests"]
    } == set(cleanup.REQUIRED_MANIFEST_FILE_SHA256.values())


def test_superseded_original_manifest_is_not_a_cleanup_identity():
    base = (
        ROOT
        / "reports/final-forensic-runs/20260814-final-preseason-forensic-v1"
    )
    with pytest.raises(RuntimeError, match="frozen cleanup identity"):
        cleanup._load_manifest(
            base / "freeze_manifest.json",
            "470d336085c04ffcca5ae2e28d42deb3fb3f8037f195855845f49e7975a86776",
        )


class _Client:
    def __init__(self, bindings, *, omit=None, extra=None):
        self.tables = {}
        self.deleted = []
        for binding in bindings:
            manifest = binding["manifest"]
            for row in manifest["warehouse_retention"]["tables"]:
                if row["table"] == omit:
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
        if extra:
            self.tables[extra] = SimpleNamespace()

    def list_tables(self, dataset):
        assert dataset == cleanup.ISOLATION_DATASET
        return [
            SimpleNamespace(table_id=table.rsplit(".", 1)[-1])
            for table in self.tables
        ]

    def get_table(self, table):
        if table not in self.tables:
            raise NotFound("missing")
        return self.tables[table]

    def delete_table(self, table, *, not_found_ok):
        assert not not_found_ok
        self.deleted.append(table)
        del self.tables[table]


def test_cleanup_requires_exact_aggregate_then_proves_zero_inventory():
    bindings = _bindings()
    client = _Client(bindings)
    receipt = cleanup.delete_corpus(client, bindings)

    assert receipt["receipt_version"] == cleanup.RECEIPT_VERSION
    assert receipt["production_preflight"] == "pass"
    assert len(receipt["manifests"]) == 2
    assert len(receipt["inventory_before"]) == 8
    assert len(receipt["deleted_table_identities"]) == 8
    assert receipt["allowed_inventory_after"] == []
    assert receipt["inventory_after"] == []
    assert all(
        row["verified_absent"] for row in receipt["deleted_table_identities"]
    )
    assert sorted(client.deleted) == receipt["inventory_before"]
    assert not client.tables

    verified = cleanup.verify_absent(client, bindings, receipt)
    assert verified["production_preflight"] == "pass"
    assert len(verified["verified_absent_tables"]) == 8
    assert verified["inventory_after"] == []


def test_cleanup_refuses_extra_dataset_object_before_any_deletion():
    bindings = _bindings()
    extra = cleanup.ISOLATION_DATASET + ".unmanifested_table"
    client = _Client(bindings, extra=extra)
    with pytest.raises(RuntimeError, match="extra=.*unmanifested_table"):
        cleanup.delete_corpus(client, bindings)
    assert client.deleted == []
    assert len(client.tables) == 9


def test_cleanup_refuses_missing_repair4_table_before_any_deletion():
    bindings = _bindings()
    missing = bindings[1]["manifest"]["warehouse_retention"]["tables"][0]["table"]
    client = _Client(bindings, omit=missing)
    with pytest.raises(RuntimeError, match="missing=.*repair4"):
        cleanup.delete_corpus(client, bindings)
    assert client.deleted == []
    assert len(client.tables) == 7


def test_cleanup_requires_both_exact_manifest_variants():
    bindings = _bindings()
    client = _Client(bindings)
    with pytest.raises(RuntimeError, match="exactly the repair3 and repair4"):
        cleanup.delete_corpus(client, bindings[:1])
    assert client.deleted == []

    wrong_variant = [bindings[0], _binding("_repair2", "e" * 64, "f" * 64)]
    with pytest.raises(RuntimeError, match="exact repair3 and repair4"):
        cleanup.delete_corpus(_Client(wrong_variant), wrong_variant)


def test_receipt_binds_every_manifest_and_exact_inventory():
    bindings = _bindings()
    client = _Client(bindings)
    receipt = cleanup.delete_corpus(client, bindings)

    changed = deepcopy(receipt)
    changed["manifests"][0]["manifest_file_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="aggregate frozen corpus"):
        cleanup.verify_absent(client, bindings, changed)

    changed = deepcopy(receipt)
    changed["inventory_before"] = changed["inventory_before"][:-1]
    with pytest.raises(RuntimeError, match="aggregate frozen corpus"):
        cleanup.verify_absent(client, bindings, changed)


def test_verify_only_refuses_any_reappearing_or_extra_object():
    bindings = _bindings()
    clean = _Client(bindings)
    receipt = cleanup.delete_corpus(clean, bindings)

    reappeared = _Client([])
    reappeared.tables[receipt["inventory_before"][0]] = SimpleNamespace()
    with pytest.raises(RuntimeError, match="remains before production"):
        cleanup.verify_absent(reappeared, bindings, receipt)

    extra = _Client([], extra=cleanup.ISOLATION_DATASET + ".new_object")
    with pytest.raises(RuntimeError, match="extra=.*new_object"):
        cleanup.verify_absent(extra, bindings, receipt)
