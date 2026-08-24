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
        return batch.normalize_object_identity(value, label=label)
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
        help="canonical terminal identity JSON in lane order; provide twice",
    )
    parser.add_argument("--panel-uri", required=True)
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
    return _publication_receipt(
        result=replayed,
        panel_uri=args.panel_uri,
        raw=raw,
        panel_identity=panel_identity,
        published=bool(args.execute),
    )


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
