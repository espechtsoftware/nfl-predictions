#!/usr/bin/env python3
"""Default-off cloud adapter for the outcome-blind Core v1 catalog.

The runner exposes three narrow commands: one-slate structural smoke, full
54-slate authority/shard materialization, and exact authority/root/shard
reopen.  It performs no historical-outcome access and prints one compact
receipt JSON object only.
Google Cloud clients are imported and constructed only after both explicit
execution gates pass.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import re
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import corpus_core_v1_catalog_materializer as core_cloud  # noqa: E402
from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLED_ENV: Final = "CORE_V1_CATALOG_CLOUD_ENABLED"
SMOKE_RECEIPT_SCHEMA: Final = "core-v1-catalog-cloud-smoke-receipt/v1"
MATERIALIZE_RECEIPT_SCHEMA: Final = (
    "core-v1-catalog-cloud-materialization-receipt/v1"
)
REOPEN_RECEIPT_SCHEMA: Final = "core-v1-catalog-cloud-reopen-receipt/v1"

_BYTES: Final = re.compile(r"[1-9][0-9]*")
_CATALOG_ID: Final = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")


class CoreV1CatalogCloudError(RuntimeError):
    """The default-off Core v1 cloud boundary failed closed."""


def _fail(message: str) -> None:
    raise CoreV1CatalogCloudError(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1CatalogCloudError(str(exc)) from exc


def _gcs_parts(uri: str) -> tuple[str, str]:
    identity = _identity(
        {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
        label="Core v1 cloud object URI",
    )
    bucket, name = str(identity["uri"]).removeprefix("gs://").split("/", 1)
    return bucket, name


def _generation(value: object, *, label: str) -> str:
    if type(value) is int and value >= 1:
        return str(value)
    if (
        type(value) is str
        and value.isdigit()
        and not value.startswith("0")
    ):
        return value
    _fail(f"{label} must be one positive generation")


class GenerationPinnedGCS:
    """Generation-pinned GET and equal-content create-once publication."""

    def __init__(self, client: object):
        self._client = client

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label="Core v1 exact-read identity")
        bucket_name, name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise CoreV1CatalogCloudError(
                "Core v1 generation-pinned read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation, label="reopened object generation")
            != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("Core v1 generation-pinned object differs")
        return raw

    def _resolve_current_exact(
        self, uri: str,
    ) -> tuple[dict[str, object], bytes]:
        bucket_name, name = _gcs_parts(uri)
        try:
            current = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            current.reload()
            generation = _generation(
                current.generation,
                label="create-once recovered generation",
            )
        except Exception as exc:
            raise CoreV1CatalogCloudError(
                "Core v1 create-once current-generation resolution failed"
            ) from exc
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=int(generation)
            )
            blob.reload(if_generation_match=int(generation))
            raw = blob.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise CoreV1CatalogCloudError(
                "Core v1 create-once recovery read failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("Core v1 recovered create-once object is empty")
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        # Reuse the ordinary exact reader as the final recovery boundary.
        if self.read_exact(identity) != raw:
            _fail("Core v1 recovered create-once bytes differ")
        return identity, raw

    def publish_create_once(
        self, uri: str, raw: bytes,
    ) -> core_cloud.CreateOncePublication:
        _gcs_parts(uri)
        if type(raw) is not bytes or not raw:
            _fail("Core v1 create-once payload must be nonempty bytes")
        bucket_name, name = _gcs_parts(uri)
        created = False
        try:
            blob = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
            created = True
        except Exception:
            # Ambiguous upload outcomes and precondition failures share one
            # recovery law: exactly one byte-identical generation or failure.
            created = False
        identity, reopened = self._resolve_current_exact(uri)
        if reopened != raw:
            _fail("existing Core v1 create-once object differs")
        return core_cloud.CreateOncePublication(
            identity=identity, created=created
        )


def _pin(args: argparse.Namespace, stem: str) -> dict[str, object]:
    raw_bytes = getattr(args, f"{stem}_bytes")
    if type(raw_bytes) is not str or _BYTES.fullmatch(raw_bytes) is None:
        _fail(f"{stem.replace('_', ' ')} bytes must be canonical")
    return _identity({
        "uri": getattr(args, f"{stem}_uri"),
        "generation": getattr(args, f"{stem}_generation"),
        "sha256": getattr(args, f"{stem}_sha256"),
        "bytes": int(raw_bytes),
    }, label=f"{stem.replace('_', ' ')} identity")


def _add_pin(parser: argparse.ArgumentParser, stem: str, label: str) -> None:
    option = stem.replace("_", "-")
    parser.add_argument(f"--{option}-uri", required=True, help=f"{label} GCS URI")
    parser.add_argument(f"--{option}-generation", required=True)
    parser.add_argument(f"--{option}-sha256", required=True)
    parser.add_argument(f"--{option}-bytes", required=True)


def _add_gate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    smoke = commands.add_parser(
        "slate-smoke", help="outcome-blind one-slate structural projection"
    )
    _add_gate(smoke)
    smoke.add_argument("--source-ordinal", type=int, required=True)
    _add_pin(smoke, "source_panel", "terminal source panel")
    _add_pin(smoke, "t230_result", "one-slate T230 result")

    materialize = commands.add_parser(
        "materialize", help="create/recover authority, 54 shards, and root"
    )
    _add_gate(materialize)
    materialize.add_argument("--catalog-id", required=True)
    materialize.add_argument("--output-prefix", required=True)
    materialize.add_argument(
        "--max-logical-catalog-bytes", type=int, required=True
    )
    _add_pin(materialize, "source_panel", "terminal source panel")
    _add_pin(materialize, "t230_panel_release", "terminal T230 panel release")

    reopen = commands.add_parser(
        "reopen", help="generation-reopen one root and all shards"
    )
    _add_gate(reopen)
    _add_pin(reopen, "root", "sharded Core v1 root")
    return parser


def _require_gate(
    args: argparse.Namespace, *, environ: Mapping[str, str],
) -> None:
    if args.execute is not True or environ.get(ENABLED_ENV) != "1":
        _fail(f"--execute and {ENABLED_ENV}=1 are required explicitly")
    if args.project != PROJECT:
        _fail("Core v1 cloud project differs")


def _receipt(value: Mapping[str, object]) -> dict[str, object]:
    body = dict(value)
    body["cli_receipt_sha256"] = core_cloud.canonical_sha256(body)
    return body


def _smoke_receipt(report: Mapping[str, object]) -> dict[str, object]:
    return _receipt({
        "schema_version": SMOKE_RECEIPT_SCHEMA,
        "status": "CORE_V1_SLATE_SMOKE_CLOSED",
        "source_ordinal": report["source_ordinal"],
        "slate": report["slate"],
        "source_panel_identity": report["source_panel_identity"],
        "t230_result_identity": report["t230_result_identity"],
        "t230_slate_result_sha256": report["t230_slate_result_sha256"],
        "slate_catalog_sha256": report["slate_catalog_sha256"],
        "structural_counts": report["structural_counts"],
        "structural_hashes": report["structural_hashes"],
        "outcome_fields_read": [],
        "science_recomputation_performed": False,
        "root_publication_authority": False,
        "production_change_licensed": False,
        "decision_authority": False,
    })


def _materialize_receipt(
    published: core_cloud.PublishedShardedCoreV1Catalog,
) -> dict[str, object]:
    root = published.root
    return _receipt({
        "schema_version": MATERIALIZE_RECEIPT_SCHEMA,
        "status": "CORE_V1_SHARDED_CATALOG_CLOSED",
        "root_identity": dict(published.root_identity),
        "catalog_identity": dict(published.catalog_identity),
        "sharded_catalog_root_sha256": root["sharded_catalog_root_sha256"],
        "catalog_sha256": root["catalog_sha256"],
        "shard_count": root["shard_count"],
        "shard_descriptors_sha256": root["shard_descriptors_sha256"],
        "materialization_metrics": root["materialization_metrics"],
        "catalog_created": published.catalog_created,
        "created_shard_count": published.created_shard_count,
        "recovered_shard_count": published.recovered_shard_count,
        "root_created": published.root_created,
        "outcome_fields_read": [],
        "science_recomputation_performed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    })


def _reopen_receipt(
    reopened: core_cloud.ReopenedShardedCoreV1Catalog,
) -> dict[str, object]:
    catalog = reopened.logical_catalog
    membership_count = sum(
        int(row["union_population"]["lineup_count"])
        for row in catalog["slates"]  # type: ignore[index]
    )
    return _receipt({
        "schema_version": REOPEN_RECEIPT_SCHEMA,
        "status": "CORE_V1_SHARDED_CATALOG_REOPENED",
        "root_identity": dict(reopened.root_identity),
        "catalog_identity": dict(reopened.catalog_identity),
        "catalog_sha256": catalog["catalog_sha256"],
        "source_slate_count": catalog["source_slate_count"],
        "book_cell_count": catalog["book_cell_count"],
        "contrast_cell_count": catalog["contrast_cell_count"],
        "union_roster_membership_count": membership_count,
        "outcome_fields_read": [],
        "science_recomputation_performed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    })


def _execute(
    args: argparse.Namespace, *, store: GenerationPinnedGCS,
) -> dict[str, object]:
    if args.command == "slate-smoke":
        report = core_cloud.build_core_v1_slate_smoke_projection(
            source_ordinal=args.source_ordinal,
            source_panel_identity=_pin(args, "source_panel"),
            t230_result_identity=_pin(args, "t230_result"),
            read_exact=store.read_exact,
        )
        return _smoke_receipt(report)
    if args.command == "materialize":
        if (
            type(args.catalog_id) is not str
            or _CATALOG_ID.fullmatch(args.catalog_id) is None
        ):
            _fail("Core v1 catalog ID differs")
        published = core_cloud.materialize_sharded_core_v1_catalog(
            catalog_id=args.catalog_id,
            source_panel_identity=_pin(args, "source_panel"),
            t230_panel_release_identity=_pin(args, "t230_panel_release"),
            output_prefix=args.output_prefix,
            max_logical_catalog_bytes=args.max_logical_catalog_bytes,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
        return _materialize_receipt(published)
    if args.command == "reopen":
        root_identity = _pin(args, "root")
        reopened = core_cloud.reopen_sharded_core_v1_catalog_authority(
            root_identity=root_identity, read_exact=store.read_exact
        )
        return _reopen_receipt(reopened)
    raise AssertionError("argparse admitted an unknown Core v1 command")


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    retained_environ = os.environ if environ is None else environ
    _require_gate(args, environ=retained_environ)
    if storage_client is None:
        # This import and client construction are unreachable while default-off.
        from google.cloud import storage

        storage_client = storage.Client(project=PROJECT)
    receipt = _execute(args, store=GenerationPinnedGCS(storage_client))
    print(core_cloud.canonical_json_bytes(receipt).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CoreV1CatalogCloudError,
        core_cloud.CorpusCoreV1CatalogMaterializerError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


__all__ = [
    "CoreV1CatalogCloudError",
    "ENABLED_ENV",
    "GenerationPinnedGCS",
    "PROJECT",
    "main",
]
