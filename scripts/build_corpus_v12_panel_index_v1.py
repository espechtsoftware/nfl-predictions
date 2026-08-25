#!/usr/bin/env python3
"""Build or create-once publish the combined Foundry v12 panel index.

The command accepts exactly two generation-pinned terminal lane identities.
It derives every task acceptance/carrier binding from those terminal objects,
replays the complete outcome-blind panel locally, and has only one optional
write: an explicit create-only GCS object under ``--execute``.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Protocol

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_v12_panel_index as panel


PUBLICATION_RECEIPT_SCHEMA = "foundry-v12-panel-index-publication/v1"
_FALSE_AUTHORITY_FIELDS = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_LOCAL_BATCH_ACCEPTED_KEYS = frozenset({
    "schema_version",
    "batch_mode",
    "task_count",
    "matrix_cell_count",
    "batch_completion",
    "batch_acceptance",
    "final_output_inventory_sha256",
    "final_output_object_count",
    "complete",
    "accepted",
})


class CorpusV12PanelIndexCLIError(RuntimeError):
    """The panel CLI cannot proceed without weakening create-once replay."""


class PanelStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> Mapping[str, object]: ...


def _split_gcs_uri(value: object, *, label: str) -> tuple[str, str]:
    if type(value) is not str or not value.startswith("gs://"):
        raise CorpusV12PanelIndexCLIError(f"{label} must be an explicit GCS URI")
    bucket_name, separator, object_name = value[5:].partition("/")
    if (
        not separator
        or not bucket_name
        or not object_name
        or object_name.endswith("/")
        or "//" in object_name
    ):
        raise CorpusV12PanelIndexCLIError(f"{label} must name one GCS object")
    return bucket_name, object_name


def _collision_exceptions() -> tuple[type[BaseException], ...]:
    try:
        from google.api_core.exceptions import AlreadyExists, PreconditionFailed
    except ImportError as exc:  # pragma: no cover - production dependency gate
        raise CorpusV12PanelIndexCLIError(
            "google-api-core is required for execute mode"
        ) from exc
    return (AlreadyExists, PreconditionFailed)


class GCSPanelStore:
    """Generation-pinned GET plus create-only publication; never lists."""

    def __init__(
        self,
        client: object,
        *,
        collision_exceptions: tuple[type[BaseException], ...] | None = None,
    ) -> None:
        self._client = client
        self._collision_exceptions = (
            _collision_exceptions()
            if collision_exceptions is None
            else collision_exceptions
        )
        if not self._collision_exceptions:
            raise CorpusV12PanelIndexCLIError(
                "create-once collision exception set cannot be empty"
            )

    def read(self, identity: Mapping[str, object]) -> bytes:
        try:
            retained = batch.normalize_object_identity(
                identity, label="GCS exact-read identity"
            )
        except Exception as exc:
            raise CorpusV12PanelIndexCLIError(
                "GCS exact-read identity differs"
            ) from exc
        bucket_name, object_name = _split_gcs_uri(
            retained["uri"], label="GCS exact-read URI"
        )
        generation = int(str(retained["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        return blob.download_as_bytes(if_generation_match=generation)

    def _reopen_current(self, uri: str) -> tuple[dict[str, object], bytes]:
        bucket_name, object_name = _split_gcs_uri(uri, label="panel output URI")
        current = self._client.bucket(bucket_name).blob(object_name)
        current.reload()
        generation_value = current.generation
        if generation_value is None:
            raise CorpusV12PanelIndexCLIError(
                "published panel lacks a generation"
            )
        generation = int(generation_value)
        pinned = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = pinned.download_as_bytes(if_generation_match=generation)
        return (
            {
                "uri": uri,
                "generation": str(generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            raw,
        )

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            raise CorpusV12PanelIndexCLIError(
                "panel publication requires nonempty bytes"
            )
        bucket_name, object_name = _split_gcs_uri(uri, label="panel output URI")
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except self._collision_exceptions:
            identity, retained = self._reopen_current(uri)
            if retained != raw:
                raise CorpusV12PanelIndexCLIError(
                    "create-once panel collision differs from requested bytes"
                )
            return identity
        identity, retained = self._reopen_current(uri)
        if retained != raw:
            raise CorpusV12PanelIndexCLIError(
                "newly published panel differs on exact reopen"
            )
        return identity


def _load_identity(path: Path, *, label: str) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in rows:
            if key in value:
                raise CorpusV12PanelIndexCLIError(
                    f"{label} contains duplicate key {key!r}"
                )
            value[key] = item
        return value

    def reject_constant(value: str) -> object:
        raise CorpusV12PanelIndexCLIError(
            f"{label} contains non-finite value {value}"
        )

    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
        if (
            isinstance(value, Mapping)
            and value.get("schema_version")
            == "corpus-parametric-batch-accepted/v1"
        ):
            if (
                frozenset(value) != _LOCAL_BATCH_ACCEPTED_KEYS
                or value.get("complete") is not True
                or value.get("accepted") is not True
            ):
                raise CorpusV12PanelIndexCLIError(
                    f"{label} local batch-accepted envelope differs"
                )
            if batch.canonical_json_bytes(value) + b"\n" != raw:
                raise CorpusV12PanelIndexCLIError(
                    f"{label} local batch-accepted envelope is not canonical"
                )
            value = value["batch_acceptance"]
        return batch.normalize_object_identity(value, label=label)
    except CorpusV12PanelIndexCLIError:
        raise
    except Exception as exc:
        raise CorpusV12PanelIndexCLIError(
            f"{label} is not one exact object identity"
        ) from exc


def _publication_receipt(
    *,
    result: Mapping[str, object],
    panel_uri: str,
    raw: bytes,
    panel_identity: Mapping[str, object] | None,
    published: bool,
) -> dict[str, object]:
    retained_identity = (
        None
        if panel_identity is None
        else batch.normalize_object_identity(
            panel_identity, label="published panel identity"
        )
    )
    if published != (retained_identity is not None):
        raise CorpusV12PanelIndexCLIError(
            "publication receipt mode/identity differs"
        )
    if retained_identity is not None and (
        retained_identity["uri"] != panel_uri
        or retained_identity["sha256"] != sha256(raw).hexdigest()
        or retained_identity["bytes"] != len(raw)
    ):
        raise CorpusV12PanelIndexCLIError(
            "published panel identity differs from requested content"
        )
    body: dict[str, object] = {
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
        "mode": "create_once" if published else "validate_only",
        "panel_uri": panel_uri,
        "panel_id": result["panel_id"],
        "panel_object_identity": retained_identity,
        "panel_content_sha256": sha256(raw).hexdigest(),
        "panel_content_bytes": len(raw),
        "panel_index_sha256": result["panel_index_sha256"],
        "lane_count": result["lane_count"],
        "accepted_slate_count": result["accepted_slate_count"],
        "exact_input_replay_verified": True,
        "published": published,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["publication_receipt_sha256"] = batch.canonical_sha256(body)
    return body


def _write_local_receipt_create_once(
    path: Path, receipt: Mapping[str, object]
) -> None:
    raw = batch.canonical_json_bytes(dict(receipt)) + b"\n"
    try:
        _reject_local_receipt_symlinks(path)
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        try:
            _reject_local_receipt_symlinks(path)
            if not path.is_file() or path.read_bytes() != raw:
                raise CorpusV12PanelIndexCLIError(
                    "create-once local receipt collision differs"
                )
        except CorpusV12PanelIndexCLIError:
            raise
        except OSError as exc:
            raise CorpusV12PanelIndexCLIError(
                "create-once local receipt collision read failed"
            ) from exc
    except OSError as exc:
        raise CorpusV12PanelIndexCLIError(
            "create-once local receipt write failed"
        ) from exc


def _reject_local_receipt_symlinks(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise CorpusV12PanelIndexCLIError(
                "local receipt path cannot contain a symlink"
            )


def _preflight_local_receipt(
    path: Path,
    *,
    panel_uri: str,
    published: bool,
) -> dict[str, object] | None:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise CorpusV12PanelIndexCLIError(
            "local receipt output must be one absolute file path"
        )
    try:
        _reject_local_receipt_symlinks(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _reject_local_receipt_symlinks(path)
        if not path.parent.is_dir():
            raise CorpusV12PanelIndexCLIError(
                "local receipt parent must be a directory"
            )
        if not path.exists():
            return None
        if not path.is_file():
            raise CorpusV12PanelIndexCLIError(
                "local receipt target must be a regular file"
            )
        raw = path.read_bytes()
    except CorpusV12PanelIndexCLIError:
        raise
    except OSError as exc:
        raise CorpusV12PanelIndexCLIError(
            "local receipt path preflight failed"
        ) from exc

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise CorpusV12PanelIndexCLIError(
                    f"local receipt contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusV12PanelIndexCLIError(
            f"local receipt contains non-finite value {value}"
        )

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusV12PanelIndexCLIError(
            "existing local receipt is not canonical JSON"
        ) from exc
    if (
        not isinstance(value, Mapping)
        or batch.canonical_json_bytes(value) + b"\n" != raw
        or value.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA
        or value.get("mode")
        != ("create_once" if published else "validate_only")
        or value.get("panel_uri") != panel_uri
        or value.get("published") is not published
    ):
        raise CorpusV12PanelIndexCLIError(
            "existing local receipt preflight differs"
        )
    body = dict(value)
    retained_sha = body.pop("publication_receipt_sha256", None)
    if retained_sha != batch.canonical_sha256(body):
        raise CorpusV12PanelIndexCLIError(
            "existing local receipt self-hash differs"
        )
    return dict(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build/replay the exact two-lane Foundry v12 panel index"
    )
    parser.add_argument(
        "--lane-id",
        action="append",
        required=True,
        help="lane id in ordinal order; provide exactly twice",
    )
    parser.add_argument(
        "--lane-terminal-identity",
        action="append",
        required=True,
        type=Path,
        help=(
            "canonical terminal identity or canonical finish-batch local "
            "envelope used only as its batch_acceptance identity carrier; "
            "provide twice in lane order"
        ),
    )
    parser.add_argument("--panel-uri", required=True)
    parser.add_argument(
        "--receipt-output",
        type=Path,
        help="optional absolute create-once local publication receipt path",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser


def run(
    argv: Sequence[str],
    *,
    store: PanelStore,
) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    if len(args.lane_id) != 2 or len(args.lane_terminal_identity) != 2:
        raise CorpusV12PanelIndexCLIError(
            "exactly two lane ids and terminal identity files are required"
        )
    _split_gcs_uri(args.panel_uri, label="panel output URI")
    existing_local_receipt = (
        None
        if args.receipt_output is None
        else _preflight_local_receipt(
            args.receipt_output,
            panel_uri=args.panel_uri,
            published=bool(args.execute),
        )
    )
    terminal_identities = [
        _load_identity(path, label=f"lane[{ordinal}] terminal identity")
        for ordinal, path in enumerate(args.lane_terminal_identity)
    ]
    lane_inputs = [
        panel.derive_v12_lane_input(
            lane_ordinal=ordinal,
            lane_id=args.lane_id[ordinal],
            terminal_receipt_identity=terminal_identities[ordinal],
            read_exact=store.read,
        )
        for ordinal in range(2)
    ]
    result = panel.build_v12_panel_index(
        lane_inputs=lane_inputs, read_exact=store.read
    )
    replayed = panel.validate_v12_panel_index(
        result, lane_inputs=lane_inputs, read_exact=store.read
    )
    raw = batch.canonical_json_bytes(replayed)
    if existing_local_receipt is not None:
        existing_identity = existing_local_receipt.get(
            "panel_object_identity"
        )
        expected_existing = _publication_receipt(
            result=replayed,
            panel_uri=args.panel_uri,
            raw=raw,
            panel_identity=existing_identity,
            published=bool(args.execute),
        )
        if batch.canonical_json_bytes(existing_local_receipt) != (
            batch.canonical_json_bytes(expected_existing)
        ):
            raise CorpusV12PanelIndexCLIError(
                "existing local receipt content differs before publication"
            )
    panel_identity: Mapping[str, object] | None = None
    if args.execute:
        panel_identity = store.publish_create_once(args.panel_uri, raw)
        reopened = panel.reopen_v12_panel_index(
            panel_index_identity=panel_identity,
            lane_inputs=lane_inputs,
            read_exact=store.read,
        )
        if batch.canonical_json_bytes(reopened) != raw:
            raise CorpusV12PanelIndexCLIError(
                "published panel semantic replay differs"
            )
    receipt = _publication_receipt(
        result=replayed,
        panel_uri=args.panel_uri,
        raw=raw,
        panel_identity=panel_identity,
        published=bool(args.execute),
    )
    if args.receipt_output is not None:
        _write_local_receipt_create_once(args.receipt_output, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - production dependency gate
        raise CorpusV12PanelIndexCLIError(
            "google-cloud-storage is required for this command"
        ) from exc
    receipt = run(
        sys.argv[1:] if argv is None else argv,
        store=GCSPanelStore(storage.Client()),
    )
    sys.stdout.buffer.write(batch.canonical_json_bytes(receipt) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
