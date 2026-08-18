#!/usr/bin/env python3
"""Delete and verify the complete temporary final-forensic BigQuery corpus.

The repair3 freeze wrote the live unsuffixed four-table corpus and the
authoritative repair4 freeze wrote four suffixed tables into the isolated
review dataset. This Week-1 gate treats their union as one
indivisible eight-table corpus: before any deletion the dataset inventory must
equal that union exactly, and after deletion the dataset must be empty.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

PROJECT = "nfl-predictions-503414"
ISOLATION_DATASET = f"{PROJECT}.nfl_forensic_review"
RECEIPT_VERSION = "aggregate-final-forensic-cleanup-v3"
WAREHOUSE_TABLE_PREFIX = ISOLATION_DATASET + ".final_forensic_20260814_"
WAREHOUSE_TABLE_IDS = frozenset({
    "actual_selections",
    "candidate_corpus",
    "oracle_rosters",
    "player_corpus",
})
REQUIRED_MANIFEST_SUFFIXES = frozenset({"", "_repair4"})
# Pin the historical files themselves. The live research validator has since
# acquired later checklist fields, so applying it retroactively would reject
# these immutable manifests for reasons unrelated to their warehouse contract.
REQUIRED_MANIFEST_FILE_SHA256 = {
    "122303a1fc14ae76c9379010eb632b8c4ae837408d4726fe47611ec88be20ce7": (
        "bdd4afa398ae8739319553725b8f6b4ef052e478d505746bed22d751732f051d"
    ),
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02": (
        "565cdcfaffad6e131449c991dda64dc171cad2d23ec0b3dc55ae0a53c9ef94e3"
    ),
}
# The dataset is dedicated to the final forensic review. Keeping this explicit
# makes any future exception a reviewed contract change.
ALLOWED_POST_CLEANUP_INVENTORY: tuple[str, ...] = ()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        required=True,
        action="append",
        help="manifest path; provide once for repair3 and once for repair4",
    )
    parser.add_argument(
        "--confirm-manifest-sha",
        required=True,
        action="append",
        help="typed internal manifest SHA paired by position with --manifest",
    )
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
    raw = path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    if manifest["manifest_sha256"] != confirmation:
        raise RuntimeError("typed manifest confirmation differs")
    file_sha = hashlib.sha256(raw).hexdigest()
    if REQUIRED_MANIFEST_FILE_SHA256.get(confirmation) != file_sha:
        raise RuntimeError("manifest bytes differ from the frozen cleanup identity")
    return {
        "manifest": manifest,
        "manifest_sha256": confirmation,
        "manifest_file_sha256": file_sha,
    }


def _manifest_suffix(manifest: Mapping[str, Any]) -> str:
    suffixes: set[str] = set()
    warehouse_tables = manifest["warehouse_retention"]["tables"]
    table_rows = {
        row["id"]: row for row in warehouse_tables
    }
    if (
        len(warehouse_tables) != len(WAREHOUSE_TABLE_IDS)
        or len(table_rows) != len(warehouse_tables)
        or set(table_rows) != WAREHOUSE_TABLE_IDS
    ):
        raise RuntimeError("manifest warehouse table inventory is incomplete")
    for table_id in WAREHOUSE_TABLE_IDS:
        row = table_rows[table_id]
        base = WAREHOUSE_TABLE_PREFIX + table_id
        table_name = str(row.get("table", ""))
        if (
            set(row) != {"id", "table", "schema"}
            or not table_name.startswith(base)
            or not isinstance(row.get("schema"), list)
            or not row["schema"]
        ):
            raise RuntimeError(f"manifest warehouse contract differs: {table_id}")
        suffixes.add(table_name.removeprefix(base))
    if len(suffixes) != 1:
        raise RuntimeError("manifest warehouse suffix differs across tables")
    return next(iter(suffixes))


def _aggregate_contract(bindings: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    bound = list(bindings)
    if len(bound) != 2:
        raise RuntimeError("cleanup requires exactly the repair3 and repair4 manifests")

    suffixes: set[str] = set()
    manifest_shas: set[str] = set()
    table_owners: dict[str, str] = {}
    manifest_receipt_rows: list[dict[str, Any]] = []
    policies: set[tuple[str, str]] = set()
    datasets: set[str] = set()
    for binding in bound:
        manifest = binding["manifest"]
        manifest_sha = str(binding["manifest_sha256"])
        if manifest.get("manifest_sha256") != manifest_sha:
            raise RuntimeError("bound manifest SHA differs from manifest payload")
        file_sha = str(binding.get("manifest_file_sha256", ""))
        if len(file_sha) != 64 or any(c not in "0123456789abcdef" for c in file_sha):
            raise RuntimeError("manifest file SHA-256 binding is invalid")
        suffixes.add(_manifest_suffix(manifest))
        if manifest_sha in manifest_shas:
            raise RuntimeError("aggregate manifest SHAs are not unique")
        manifest_shas.add(manifest_sha)

        retention = manifest["warehouse_retention"]
        datasets.add(str(retention.get("isolation_dataset", "")))
        policies.add((retention["cleanup_policy"], retention["cleanup_deadline"]))
        tables = sorted(str(row["table"]) for row in retention["tables"])
        for table_name in tables:
            if table_name in table_owners:
                raise RuntimeError("aggregate manifests contain a duplicate table identity")
            table_owners[table_name] = manifest_sha
        manifest_receipt_rows.append({
            "manifest_sha256": manifest_sha,
            "manifest_file_sha256": file_sha,
            "table_inventory": tables,
        })

    if suffixes != REQUIRED_MANIFEST_SUFFIXES:
        raise RuntimeError("cleanup requires the exact repair3 and repair4 table variants")
    if datasets != {ISOLATION_DATASET}:
        raise RuntimeError("aggregate manifests do not bind the isolation dataset")
    if len(policies) != 1:
        raise RuntimeError("aggregate manifest cleanup policies differ")
    expected_tables = sorted(table_owners)
    if len(expected_tables) != 2 * len(WAREHOUSE_TABLE_IDS):
        raise RuntimeError("aggregate forensic inventory is not exactly eight tables")
    cleanup_policy, cleanup_deadline = next(iter(policies))
    return {
        "dataset": ISOLATION_DATASET,
        "cleanup_policy": cleanup_policy,
        "cleanup_deadline": cleanup_deadline,
        "manifests": sorted(
            manifest_receipt_rows, key=lambda row: row["table_inventory"]
        ),
        "table_owners": table_owners,
        "table_inventory": expected_tables,
    }


def _list_inventory(client: bigquery.Client, dataset: str) -> list[str]:
    inventory: list[str] = []
    for item in client.list_tables(dataset):
        table_id = getattr(item, "table_id", None)
        if not isinstance(table_id, str) or not table_id:
            raise RuntimeError("BigQuery returned an unidentifiable dataset object")
        inventory.append(f"{dataset}.{table_id}")
    if len(inventory) != len(set(inventory)):
        raise RuntimeError("BigQuery returned duplicate dataset identities")
    return sorted(inventory)


def _require_exact_inventory(
    client: bigquery.Client,
    dataset: str,
    expected: Iterable[str],
    *,
    stage: str,
) -> list[str]:
    expected_sorted = sorted(expected)
    actual = _list_inventory(client, dataset)
    if actual != expected_sorted:
        missing = sorted(set(expected_sorted) - set(actual))
        extra = sorted(set(actual) - set(expected_sorted))
        raise RuntimeError(
            f"forensic dataset inventory differs {stage}; missing={missing}, extra={extra}"
        )
    return actual


def delete_corpus(
    client: bigquery.Client,
    bindings: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    bindings = list(bindings)
    contract = _aggregate_contract(bindings)
    inventory_before = _require_exact_inventory(
        client,
        contract["dataset"],
        contract["table_inventory"],
        stage="before deletion",
    )

    verified: list[dict[str, Any]] = []
    for manifest_row in contract["manifests"]:
        manifest_sha = manifest_row["manifest_sha256"]
        binding = next(
            row for row in bindings if row["manifest_sha256"] == manifest_sha
        )
        manifest = binding["manifest"]
        table_rows = {
            row["table"]: row for row in manifest["warehouse_retention"]["tables"]
        }
        for table_name in manifest_row["table_inventory"]:
            table = client.get_table(table_name)
            expected_schema = table_rows[table_name]["schema"]
            if (
                _schema(table) != expected_schema
                or (table.labels or {}).get("manifest") != manifest_sha[:32]
                or manifest_sha not in (table.description or "")
                or table.expires is None
            ):
                raise RuntimeError(f"refusing unverified forensic table: {table_name}")
            verified.append({
                "manifest_sha256": manifest_sha,
                "table": table_name,
                "rows_before_delete": int(table.num_rows),
                "scheduled_expiry": table.expires.isoformat(),
                "verified_absent": False,
            })

    # No deletion occurs until the complete aggregate inventory and all eight
    # table metadata contracts have passed.
    _require_exact_inventory(
        client,
        contract["dataset"],
        inventory_before,
        stage="at the deletion boundary",
    )
    for row in verified:
        client.delete_table(row["table"], not_found_ok=False)
    for row in verified:
        try:
            client.get_table(row["table"])
        except NotFound:
            row["verified_absent"] = True
        else:
            raise RuntimeError(f"forensic table remains after deletion: {row['table']}")
    inventory_after = _require_exact_inventory(
        client,
        contract["dataset"],
        ALLOWED_POST_CLEANUP_INVENTORY,
        stage="after deletion",
    )
    return {
        "receipt_version": RECEIPT_VERSION,
        "project": PROJECT,
        "isolation_dataset": contract["dataset"],
        "manifests": contract["manifests"],
        "cleanup_policy": contract["cleanup_policy"],
        "cleanup_deadline": contract["cleanup_deadline"],
        "inventory_before": inventory_before,
        "deleted_table_identities": sorted(verified, key=lambda row: row["table"]),
        "allowed_inventory_after": list(ALLOWED_POST_CLEANUP_INVENTORY),
        "inventory_after": inventory_after,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "production_preflight": "pass",
    }


def _validate_receipt(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
    required_keys = {
        "receipt_version", "project", "isolation_dataset", "manifests",
        "cleanup_policy", "cleanup_deadline", "inventory_before",
        "deleted_table_identities", "allowed_inventory_after", "inventory_after",
        "deleted_at", "production_preflight",
    }
    if set(receipt) != required_keys:
        raise RuntimeError("cleanup receipt fields differ from the aggregate contract")
    if (
        receipt.get("receipt_version") != RECEIPT_VERSION
        or receipt.get("project") != PROJECT
        or receipt.get("isolation_dataset") != contract["dataset"]
        or receipt.get("manifests") != contract["manifests"]
        or receipt.get("cleanup_policy") != contract["cleanup_policy"]
        or receipt.get("cleanup_deadline") != contract["cleanup_deadline"]
        or receipt.get("inventory_before") != contract["table_inventory"]
        or receipt.get("allowed_inventory_after")
        != list(ALLOWED_POST_CLEANUP_INVENTORY)
        or receipt.get("inventory_after") != list(ALLOWED_POST_CLEANUP_INVENTORY)
        or receipt.get("production_preflight") != "pass"
        or not isinstance(receipt.get("deleted_at"), str)
        or not receipt.get("deleted_at")
    ):
        raise RuntimeError("cleanup receipt differs from the aggregate frozen corpus")

    deleted = receipt.get("deleted_table_identities")
    if not isinstance(deleted, list):
        raise RuntimeError("cleanup receipt deleted identities are malformed")
    expected_owner = contract["table_owners"]
    if [row.get("table") for row in deleted] != contract["table_inventory"]:
        raise RuntimeError("cleanup receipt deleted inventory differs")
    for row in deleted:
        if set(row) != {
            "manifest_sha256", "table", "rows_before_delete",
            "scheduled_expiry", "verified_absent",
        }:
            raise RuntimeError("cleanup receipt deleted identity fields differ")
        if (
            row["manifest_sha256"] != expected_owner[row["table"]]
            or not isinstance(row["rows_before_delete"], int)
            or row["rows_before_delete"] < 0
            or not isinstance(row["scheduled_expiry"], str)
            or not row["scheduled_expiry"]
            or row["verified_absent"] is not True
        ):
            raise RuntimeError("cleanup receipt deleted identity differs")


def verify_absent(
    client: bigquery.Client,
    bindings: Iterable[Mapping[str, Any]],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _aggregate_contract(bindings)
    _validate_receipt(contract, receipt)
    for table_name in contract["table_inventory"]:
        try:
            client.get_table(table_name)
        except NotFound:
            continue
        raise RuntimeError(f"forensic table remains before production: {table_name}")
    inventory_after = _require_exact_inventory(
        client,
        contract["dataset"],
        ALLOWED_POST_CLEANUP_INVENTORY,
        stage="during production preflight",
    )
    return {
        "receipt_version": RECEIPT_VERSION,
        "manifest_sha256s": sorted(
            row["manifest_sha256"] for row in contract["manifests"]
        ),
        "verified_absent_tables": contract["table_inventory"],
        "inventory_after": inventory_after,
        "production_preflight": "pass",
    }


def main() -> int:
    args = _parser().parse_args()
    if len(args.manifest) != len(args.confirm_manifest_sha):
        raise RuntimeError("each --manifest requires one paired typed SHA")
    bindings = [
        _load_manifest(Path(path), confirmation)
        for path, confirmation in zip(
            args.manifest, args.confirm_manifest_sha, strict=True
        )
    ]
    receipt_path = Path(args.receipt)
    client = bigquery.Client(project=PROJECT, location="US")
    if args.delete:
        if receipt_path.exists():
            raise RuntimeError("cleanup receipt already exists; refusing to replace it")
        receipt = delete_corpus(client, bindings)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, sort_keys=True))
    else:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        print(json.dumps(verify_absent(client, bindings, receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
