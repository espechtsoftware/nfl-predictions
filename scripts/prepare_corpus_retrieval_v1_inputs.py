#!/usr/bin/env python3
"""Capture and publish exact outcome-blind task-0 retrieval inputs.

This preparer is deliberately separate from both the retrieval worker and the
corpus producer.  It selects only roster lineage and point-in-time player
fields and validates them against the five retained NPZ bodies.  Publication
is a separate, independently gated phase: it stages exact source bodies into
the dedicated retrieval bucket, publishes the query authority first, rebuilds
the candidate and player objects against that real generation-pinned identity,
and then constructs the snapshot and suite from published identities only.

Neither phase selects a realized-score column or launches a retrieval task.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from nfl_dfs.research import corpus_retrieval_engine as engine


PROJECT = "nfl-predictions-503414"
LOCATION = "US"
TASK_ID = "slate-2023-w1"
SNAPSHOT_AT = "2026-08-21T17:42:00Z"
ENABLE_ENV = "CORPUS_RETRIEVAL_INPUT_CAPTURE_ENABLED"
PUBLICATION_ENABLE_ENV = "CORPUS_RETRIEVAL_INPUT_PUBLICATION_ENABLED"
RUN_ID = "20260821-corpus-retrieval-engine-v1"
SNAPSHOT_ID = "20260821-corpus-retrieval-task0-snapshot-v1"
DEDICATED_BUCKET = "nfl-predictions-503414-corpus-retrieval"
INPUT_PREFIX = (
    f"gs://{DEDICATED_BUCKET}/research/corpus-retrieval-inputs/{RUN_ID}/"
)
OUTPUT_PREFIX = (
    f"gs://{DEDICATED_BUCKET}/research/corpus-retrieval-runs/{RUN_ID}/"
)
CODE_REPOSITORY = "https://github.com/espechtsoftware/nfl-predictions.git"
RUN_ROOT = Path(
    "reports/corpus-retrieval-runs/"
    f"{RUN_ID}"
)
CANDIDATE_SQL_PATH = RUN_ROOT / "governance/candidate-rows.sql"
PLAYER_SQL_PATH = RUN_ROOT / "governance/player-catalog.sql"
CANDIDATE_SQL_SHA256 = (
    "ede519d53fb008b1cef5c8321879c20a9aa9405dbfb0f51ef0919d2f7cffef23"
)
PLAYER_SQL_SHA256 = (
    "d6e2dff351a4a8d2a7f10db917edd33574453272dc86b33bdf43dda1a29e2996"
)
CANDIDATE_JOB_ID = "corpus_retrieval_v1_candidates_20260821t174200z"
PLAYER_JOB_ID = "corpus_retrieval_v1_players_20260821t174200z"
PANEL_IDS = (
    "20260815-atlas-money-worlds-r0-v1",
    "20260815-atlas-money-worlds-r1-v1",
    "20260815-atlas-money-worlds-r2-v1",
    "20260815-atlas-money-worlds-r3-v1",
    "20260815-atlas-money-worlds-r4-v1",
)
EXPECTED_CANDIDATE_COUNTS = (255, 257, 254, 256, 254)
EXPECTED_PLAYER_COUNT = 773
SOURCE_LOCK_ORIGIN = {
    "uri": (
        "gs://nfl-predictions-503414-raw/research/"
        "production-law-dependence-runs/"
        "20260817-production-law-dependence-source-lock-v1/source-lock.json"
    ),
    "generation": "1786950155692968",
    "sha256": "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c",
    "bytes": 1_341_911,
}
WORLD_ORIGINS = (
    {
        "block_id": "R0",
        "panel_id": PANEL_IDS[0],
        "expected_candidate_count": EXPECTED_CANDIDATE_COUNTS[0],
        "origin": {
            "uri": (
                "gs://nfl-predictions-503414-raw/cand_scores/"
                "20260815-atlas-money-worlds-r0-v1/2023_w1_886e19454d2e.npz"
            ),
            "generation": "1786843060343205",
            "sha256": "c35ecb83ecc8cacb802735f5b4f44c64b8733822e0d36e9475bab1b68de65498",
            "bytes": 31_752_021,
        },
    },
    {
        "block_id": "R1",
        "panel_id": PANEL_IDS[1],
        "expected_candidate_count": EXPECTED_CANDIDATE_COUNTS[1],
        "origin": {
            "uri": (
                "gs://nfl-predictions-503414-raw/cand_scores/"
                "20260815-atlas-money-worlds-r1-v1/2023_w1_f88dca75e9b6.npz"
            ),
            "generation": "1786842999474453",
            "sha256": "391e770f5a0d51f4375b7239a7184681039e1769d4fe4122b0d7e216c30b2f8f",
            "bytes": 31_826_199,
        },
    },
    {
        "block_id": "R2",
        "panel_id": PANEL_IDS[2],
        "expected_candidate_count": EXPECTED_CANDIDATE_COUNTS[2],
        "origin": {
            "uri": (
                "gs://nfl-predictions-503414-raw/cand_scores/"
                "20260815-atlas-money-worlds-r2-v1/2023_w1_299dd21af798.npz"
            ),
            "generation": "1786843081394196",
            "sha256": "e5de1cd0be8ee3ad990f9ea8a399f8b03bf3e0b18d8441f2ad98fc6b66a52046",
            "bytes": 31_713_457,
        },
    },
    {
        "block_id": "R3",
        "panel_id": PANEL_IDS[3],
        "expected_candidate_count": EXPECTED_CANDIDATE_COUNTS[3],
        "origin": {
            "uri": (
                "gs://nfl-predictions-503414-raw/cand_scores/"
                "20260815-atlas-money-worlds-r3-v1/2023_w1_db82b55fef56.npz"
            ),
            "generation": "1786843100083841",
            "sha256": "17f66dd5727513182c8634dc1184e616d41bb60c474209075b6043925b3c5ef3",
            "bytes": 31_788_248,
        },
    },
    {
        "block_id": "R4",
        "panel_id": PANEL_IDS[4],
        "expected_candidate_count": EXPECTED_CANDIDATE_COUNTS[4],
        "origin": {
            "uri": (
                "gs://nfl-predictions-503414-raw/cand_scores/"
                "20260815-atlas-money-worlds-r4-v1/2023_w1_b82a85a8bf8b.npz"
            ),
            "generation": "1786843157821536",
            "sha256": "1b0e7bce938bfb532b4f563f2f466645ff5a18039cb0c1b41e36f0b5713daba0",
            "bytes": 31_718_004,
        },
    },
)

QUERY_AUTHORITY_URI = f"{INPUT_PREFIX}governance/query-authority.json"
CANDIDATE_ROWS_URI = f"{INPUT_PREFIX}tasks/0000/candidate-rows.json"
PLAYER_CATALOG_URI = f"{INPUT_PREFIX}tasks/0000/player-catalog.json"
SOURCE_LOCK_URI = f"{INPUT_PREFIX}sources/source-lock.json"
PRODUCER_AUTHORITY_URI = (
    f"{INPUT_PREFIX}governance/snapshot-producer-authority.json"
)
SNAPSHOT_MANIFEST_URI = f"{INPUT_PREFIX}governance/snapshot-manifest.json"
SUITE_MANIFEST_URI = f"{OUTPUT_PREFIX}governance/suite-manifest.json"
PUBLICATION_RECEIPT_URI = f"{INPUT_PREFIX}governance/input-publication.json"

PublishCreateOnce = Callable[[str, bytes, str], Mapping[str, object]]
ReadExact = Callable[[Mapping[str, object]], bytes]
PristineCheck = Callable[[Sequence[str]], None]


class RetrievalInputCaptureError(RuntimeError):
    """The outcome-blind input capture failed closed."""


class RetrievalInputPublicationError(RuntimeError):
    """The create-once input publication failed closed."""


def _canonical(value: object) -> bytes:
    return engine.canonical_json_bytes(value)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return engine.normalize_object_identity(value, label=label)
    except (AttributeError, engine.CorpusRetrievalError) as exc:
        raise RetrievalInputPublicationError(
            f"{label} is not an exact generation/SHA/byte identity"
        ) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = engine.canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = value.get(field)
    body = {key: item for key, item in value.items() if key != field}
    if type(retained) is not str or retained != engine.canonical_sha256(body):
        raise RetrievalInputPublicationError(f"{label} self-hash differs")


def _read_canonical(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise RetrievalInputPublicationError(f"{label} is absent")
    raw = path.read_bytes()
    try:
        return engine.parse_canonical_json_bytes(raw, label=label)
    except (AttributeError, engine.CorpusRetrievalError) as exc:
        raise RetrievalInputPublicationError(
            f"{label} is not exact canonical JSON"
        ) from exc


def _read_local_exact(
    path: Path, identity: Mapping[str, object], *, label: str,
) -> bytes:
    expected = _identity(identity, label=f"{label} identity")
    if path.is_symlink() or not path.is_file():
        raise RetrievalInputPublicationError(f"{label} body is absent")
    raw = path.read_bytes()
    if len(raw) != expected["bytes"] or _sha(raw) != expected["sha256"]:
        raise RetrievalInputPublicationError(f"{label} content identity differs")
    return raw


def _write_once(path: Path, raw: bytes) -> None:
    if type(raw) is not bytes or not raw:
        raise RetrievalInputCaptureError("capture body must be nonempty bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o444)
    except FileExistsError as exc:
        raise RetrievalInputCaptureError(
            f"create-once capture path already exists: {path}"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if path.is_symlink() or path.read_bytes() != raw:
        raise RetrievalInputCaptureError("create-once capture replay differs")


def _publish_and_reopen(
    *, uri: str, raw: bytes, media_type: str,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
    seen_uris: set[str],
) -> dict[str, object]:
    if uri in seen_uris:
        raise RetrievalInputPublicationError(
            f"publication plan repeats deterministic URI: {uri}"
        )
    if type(raw) is not bytes or not raw:
        raise RetrievalInputPublicationError("publication body must be nonempty bytes")
    seen_uris.add(uri)
    try:
        retained = _identity(
            publish_create_once(uri, raw, media_type),
            label=f"published {uri}",
        )
    except RetrievalInputPublicationError:
        raise
    except Exception as exc:
        raise RetrievalInputPublicationError(
            f"create-once publication failed: {uri}"
        ) from exc
    if (
        retained["uri"] != uri
        or retained["sha256"] != _sha(raw)
        or retained["bytes"] != len(raw)
    ):
        raise RetrievalInputPublicationError(
            f"publisher returned a different identity: {uri}"
        )
    try:
        reopened = read_exact(retained)
    except Exception as exc:
        raise RetrievalInputPublicationError(
            f"published identity did not reopen: {uri}"
        ) from exc
    if type(reopened) is not bytes or reopened != raw:
        raise RetrievalInputPublicationError(
            f"published identity did not reopen byte-identically: {uri}"
        )
    return retained


def _iso(value: object, *, label: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RetrievalInputCaptureError(f"{label} timestamp is absent")
    return value.astimezone(timezone.utc).isoformat()


def _query(
    client: object, *, sql: str, job_id: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    try:
        job = client.get_job(job_id, project=PROJECT, location=LOCATION)
    except NotFound:
        try:
            job = client.query(
                sql,
                job_config=bigquery.QueryJobConfig(use_query_cache=False),
                job_id=job_id,
                location=LOCATION,
                job_retry=None,
            )
        except Exception as exc:
            raise RetrievalInputCaptureError(
                f"outcome-blind query launch failed: {job_id}"
            ) from exc
    if getattr(job, "query", None) != sql:
        raise RetrievalInputCaptureError(f"retained query SQL differs: {job_id}")
    try:
        result = job.result()
        rows = [dict(row.items()) for row in result]
    except Exception as exc:
        raise RetrievalInputCaptureError(
            f"outcome-blind query failed: {job_id}"
        ) from exc
    if job.error_result is not None or job.location != LOCATION:
        raise RetrievalInputCaptureError(f"query terminal metadata differs: {job_id}")
    receipt = {
        "job_id": str(job.job_id),
        "project": PROJECT,
        "location": str(job.location),
        "sql_sha256": _sha(sql.encode("utf-8")),
        "snapshot_at_utc": SNAPSHOT_AT,
        "created": _iso(job.created, label="query created"),
        "started": _iso(job.started, label="query started"),
        "ended": _iso(job.ended, label="query ended"),
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "cache_hit": bool(job.cache_hit),
        "error_result": None,
        "row_count": len(rows),
        "rows_sha256": engine.canonical_sha256(rows),
    }
    return rows, receipt


def _load_artifact_player_ids(
    path: Path, *, expected_identity: Mapping[str, object],
) -> list[str]:
    if path.is_symlink() or not path.is_file():
        raise RetrievalInputCaptureError(f"source artifact is absent: {path}")
    expected = _identity(expected_identity, label="source artifact identity")
    raw = path.read_bytes()
    if len(raw) != expected["bytes"] or _sha(raw) != expected["sha256"]:
        raise RetrievalInputCaptureError("source artifact content identity differs")
    try:
        with np.load(path, allow_pickle=False) as archive:
            if archive.files != [
                "cand_ix", "totals", "tail_line", "player_ids", "player_draws"
            ]:
                raise RetrievalInputCaptureError("source NPZ member order differs")
            ids = np.asarray(archive["player_ids"])
            draws = np.asarray(archive["player_draws"])
            candidates = np.asarray(archive["cand_ix"])
    except RetrievalInputCaptureError:
        raise
    except Exception as exc:
        raise RetrievalInputCaptureError("source artifact decode failed") from exc
    if (
        ids.ndim != 1
        or ids.dtype.kind != "U"
        or draws.dtype != np.dtype("float32")
        or draws.shape != (len(ids), engine.WORLDS_PER_BLOCK)
        or candidates.dtype != np.dtype("int32")
    ):
        raise RetrievalInputCaptureError("source artifact player/world shape differs")
    result = [str(value) for value in ids]
    if len(result) != EXPECTED_PLAYER_COUNT or len(result) != len(set(result)):
        raise RetrievalInputCaptureError("source artifact player universe differs")
    return result


def _validate_rows(
    *, candidate_rows: Sequence[Mapping[str, object]],
    player_rows: Sequence[Mapping[str, object]], artifacts_dir: Path,
    candidate_receipt: Mapping[str, object],
    player_receipt: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    try:
        normalized_candidate_rows = engine.normalize_candidate_query_rows(
            candidate_rows
        )
        normalized_player_rows = engine.normalize_player_query_rows(player_rows)
    except (AttributeError, engine.CorpusRetrievalError) as exc:
        raise RetrievalInputCaptureError("query row normalization failed") from exc
    candidate_receipt_with_normalized_hash = {
        **dict(candidate_receipt),
        "normalized_rows_sha256": engine.canonical_sha256(
            normalized_candidate_rows
        ),
    }
    dummy_authority = engine.object_identity_for_bytes(
        uri=QUERY_AUTHORITY_URI,
        generation="1",
        raw=b'{"local":"unpublished-query-authority"}',
    )
    candidate_body = engine.build_candidate_rows_object(
        task_id=TASK_ID,
        source_authority=dummy_authority,
        source_sql_sha256=CANDIDATE_SQL_SHA256,
        source_query_receipt=candidate_receipt_with_normalized_hash,
        rows=normalized_candidate_rows,
    )
    player_body = engine.build_player_catalog_object(
        task_id=TASK_ID,
        source_authority=dummy_authority,
        players=normalized_player_rows,
    )
    panel_counts = Counter(str(row["panel_id"]) for row in candidate_body["rows"])
    if panel_counts != Counter(dict(zip(PANEL_IDS, EXPECTED_CANDIDATE_COUNTS))):
        raise RetrievalInputCaptureError("candidate panel census differs")
    player_ids = [str(row["id"]) for row in player_body["players"]]
    artifact_universes = [
        _load_artifact_player_ids(
            artifacts_dir / f"R{ordinal}.npz",
            expected_identity=WORLD_ORIGINS[ordinal]["origin"],
        )
        for ordinal in range(len(WORLD_ORIGINS))
    ]
    if any(set(ids) != set(player_ids) for ids in artifact_universes):
        raise RetrievalInputCaptureError("catalog/artifact player universes differ")
    used_ids = {
        str(player_id)
        for row in candidate_body["rows"]
        for player_id in row["players"]
    }
    if not used_ids or not used_ids.issubset(set(player_ids)):
        raise RetrievalInputCaptureError("candidate roster is outside player catalog")
    validation = {
        "schema_version": "corpus-retrieval-input-capture-validation/v1",
        "task_id": TASK_ID,
        "snapshot_at_utc": SNAPSHOT_AT,
        "candidate_rows": len(candidate_body["rows"]),
        "candidate_rows_by_panel": dict(sorted(panel_counts.items())),
        "catalog_players": len(player_ids),
        "candidate_used_players": len(used_ids),
        "artifact_blocks": 5,
        "worlds_per_block": engine.WORLDS_PER_BLOCK,
        "actual_outcome_columns_selected": False,
        "uses_realized_outcomes": False,
        "raw_candidate_query_rows_sha256": candidate_receipt["rows_sha256"],
        "raw_player_query_rows_sha256": player_receipt["rows_sha256"],
        "normalized_candidate_rows_sha256": engine.canonical_sha256(
            candidate_body["rows"]
        ),
        "normalized_player_rows_sha256": engine.canonical_sha256(
            player_body["players"]
        ),
        "artifact_origins": [
            _identity(row["origin"], label=f"artifact origin {row['block_id']}")
            for row in WORLD_ORIGINS
        ],
    }
    validation["validation_sha256"] = engine.canonical_sha256(validation)
    return (
        [dict(row) for row in candidate_body["rows"]],
        [dict(row) for row in player_body["players"]],
        validation,
    )


def capture(args: argparse.Namespace) -> dict[str, object]:
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        raise RetrievalInputCaptureError(
            f"capture requires --execute and {ENABLE_ENV}=1"
        )
    candidate_sql = args.candidate_sql.read_text(encoding="utf-8")
    player_sql = args.player_sql.read_text(encoding="utf-8")
    if (
        _sha(candidate_sql.encode("utf-8")) != CANDIDATE_SQL_SHA256
        or _sha(player_sql.encode("utf-8")) != PLAYER_SQL_SHA256
    ):
        raise RetrievalInputCaptureError("frozen input SQL bytes differ")
    forbidden = ("actual_score", "actual_ownership", "payout", "winnings")
    lowered = f"{candidate_sql}\n{player_sql}".lower()
    if any(token in lowered for token in forbidden):
        raise RetrievalInputCaptureError("input SQL selects a realized-outcome field")

    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    candidate_rows, candidate_receipt = _query(
        client, sql=candidate_sql, job_id=CANDIDATE_JOB_ID
    )
    player_rows, player_receipt = _query(
        client, sql=player_sql, job_id=PLAYER_JOB_ID
    )
    normalized_candidate_rows, normalized_player_rows, validation = _validate_rows(
        candidate_rows=candidate_rows,
        player_rows=player_rows,
        artifacts_dir=args.artifacts_dir,
        candidate_receipt=candidate_receipt,
        player_receipt=player_receipt,
    )
    candidate_receipt["normalized_rows_sha256"] = engine.canonical_sha256(
        normalized_candidate_rows
    )
    player_receipt["normalized_rows_sha256"] = engine.canonical_sha256(
        normalized_player_rows
    )
    try:
        query_authority = engine.build_input_query_authority(
            task_id=TASK_ID,
            snapshot_at_utc=SNAPSHOT_AT,
            candidate_query=candidate_receipt,
            player_query=player_receipt,
        )
        engine.validate_input_query_authority(query_authority)
    except (AttributeError, engine.CorpusRetrievalError) as exc:
        raise RetrievalInputCaptureError(
            "core input-query authority assembly failed"
        ) from exc
    bodies = {
        "candidate-query-rows.json": normalized_candidate_rows,
        "player-query-rows.json": normalized_player_rows,
        "query-authority.json": query_authority,
        "validation.json": validation,
    }
    if args.output_dir.exists():
        raise RetrievalInputCaptureError("capture output directory already exists")
    for name, body in bodies.items():
        _write_once(args.output_dir / name, _canonical(body))
    result = {
        "schema_version": "corpus-retrieval-input-capture/v1",
        "task_id": TASK_ID,
        "snapshot_at_utc": SNAPSHOT_AT,
        "files": {
            name: {"sha256": _sha(_canonical(body)), "bytes": len(_canonical(body))}
            for name, body in sorted(bodies.items())
        },
        "validation_sha256": validation["validation_sha256"],
        "uses_realized_outcomes": False,
        "published": False,
    }
    result["capture_sha256"] = engine.canonical_sha256(result)
    _write_once(args.output_dir / "capture.json", _canonical(result))
    return result


_CAPTURE_FILES = frozenset({
    "candidate-query-rows.json",
    "player-query-rows.json",
    "query-authority.json",
    "validation.json",
})


def _validate_query_receipt(
    value: object, *, label: str, expected_job_id: str,
    expected_sql_sha256: str, normalized_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RetrievalInputPublicationError(f"{label} is not an object")
    required = {
        "job_id", "project", "location", "sql_sha256", "snapshot_at_utc",
        "created", "started", "ended", "total_bytes_processed", "cache_hit",
        "error_result", "row_count", "rows_sha256", "normalized_rows_sha256",
    }
    if set(value) != required:
        raise RetrievalInputPublicationError(f"{label} fields differ")
    if (
        value["job_id"] != expected_job_id
        or value["project"] != PROJECT
        or value["location"] != LOCATION
        or value["sql_sha256"] != expected_sql_sha256
        or value["snapshot_at_utc"] != SNAPSHOT_AT
        or value["error_result"] is not None
        or type(value["row_count"]) is not int
        or value["row_count"] != len(normalized_rows)
        or value["normalized_rows_sha256"]
        != engine.canonical_sha256(normalized_rows)
    ):
        raise RetrievalInputPublicationError(f"{label} authority differs")
    for field in ("created", "started", "ended"):
        timestamp = value[field]
        if type(timestamp) is not str or not timestamp.endswith("+00:00"):
            raise RetrievalInputPublicationError(
                f"{label}.{field} is not an aware UTC timestamp"
            )
    if (
        type(value["total_bytes_processed"]) is not int
        or value["total_bytes_processed"] < 0
        or type(value["cache_hit"]) is not bool
        or type(value["rows_sha256"]) is not str
        or len(value["rows_sha256"]) != 64
        or type(value["normalized_rows_sha256"]) is not str
        or len(value["normalized_rows_sha256"]) != 64
    ):
        raise RetrievalInputPublicationError(f"{label} terminal metadata differs")
    return dict(value)


def _load_capture(capture_dir: Path) -> dict[str, object]:
    if capture_dir.is_symlink() or not capture_dir.is_dir():
        raise RetrievalInputPublicationError("capture directory is absent")
    names = {path.name for path in capture_dir.iterdir()}
    if names != _CAPTURE_FILES | {"capture.json"}:
        raise RetrievalInputPublicationError("capture directory inventory differs")
    capture = _read_canonical(capture_dir / "capture.json", label="capture manifest")
    if not isinstance(capture, Mapping) or set(capture) != {
        "schema_version", "task_id", "snapshot_at_utc", "files",
        "validation_sha256", "uses_realized_outcomes", "published",
        "capture_sha256",
    }:
        raise RetrievalInputPublicationError("capture manifest fields differ")
    _validate_self_hash(capture, field="capture_sha256", label="capture manifest")
    if (
        capture["schema_version"] != "corpus-retrieval-input-capture/v1"
        or capture["task_id"] != TASK_ID
        or capture["snapshot_at_utc"] != SNAPSHOT_AT
        or capture["uses_realized_outcomes"] is not False
        or capture["published"] is not False
    ):
        raise RetrievalInputPublicationError("capture manifest authority differs")
    files = capture["files"]
    if not isinstance(files, Mapping) or set(files) != _CAPTURE_FILES:
        raise RetrievalInputPublicationError("capture file manifest differs")
    values: dict[str, object] = {}
    raw_files: dict[str, bytes] = {}
    for name in sorted(_CAPTURE_FILES):
        retained = files[name]
        if not isinstance(retained, Mapping) or set(retained) != {"sha256", "bytes"}:
            raise RetrievalInputPublicationError(f"capture identity differs: {name}")
        path = capture_dir / name
        if path.is_symlink() or not path.is_file():
            raise RetrievalInputPublicationError(f"capture file is absent: {name}")
        raw = path.read_bytes()
        if (
            type(retained["sha256"]) is not str
            or retained["sha256"] != _sha(raw)
            or type(retained["bytes"]) is not int
            or retained["bytes"] != len(raw)
            or not raw
        ):
            raise RetrievalInputPublicationError(
                f"capture file content identity differs: {name}"
            )
        try:
            values[name] = engine.parse_canonical_json_bytes(
                raw, label=f"capture file {name}"
            )
        except engine.CorpusRetrievalError as exc:
            raise RetrievalInputPublicationError(
                f"capture file is not canonical: {name}"
            ) from exc
        raw_files[name] = raw

    candidate_rows = values["candidate-query-rows.json"]
    player_rows = values["player-query-rows.json"]
    query_authority = values["query-authority.json"]
    validation = values["validation.json"]
    if type(candidate_rows) is not list or type(player_rows) is not list:
        raise RetrievalInputPublicationError("captured rows are not arrays")
    if not isinstance(query_authority, Mapping) or set(query_authority) != {
        "schema_version", "task_id", "snapshot_at_utc", "candidate_query",
        "player_query", "actual_outcome_columns_selected",
        "uses_realized_outcomes", "query_authority_sha256",
    }:
        raise RetrievalInputPublicationError("query authority fields differ")
    try:
        normalized_query_authority = engine.validate_input_query_authority(
            query_authority
        )
    except (AttributeError, engine.CorpusRetrievalError) as exc:
        raise RetrievalInputPublicationError("query authority differs") from exc
    if normalized_query_authority != query_authority:
        raise RetrievalInputPublicationError("query authority replay differs")
    candidate_receipt = _validate_query_receipt(
        query_authority["candidate_query"],
        label="candidate query receipt",
        expected_job_id=CANDIDATE_JOB_ID,
        expected_sql_sha256=CANDIDATE_SQL_SHA256,
        normalized_rows=candidate_rows,
    )
    _validate_query_receipt(
        query_authority["player_query"],
        label="player query receipt",
        expected_job_id=PLAYER_JOB_ID,
        expected_sql_sha256=PLAYER_SQL_SHA256,
        normalized_rows=player_rows,
    )

    placeholder = engine.object_identity_for_bytes(
        uri=QUERY_AUTHORITY_URI,
        generation="1",
        raw=raw_files["query-authority.json"],
    )
    try:
        normalized_candidates = engine.build_candidate_rows_object(
            task_id=TASK_ID,
            source_authority=placeholder,
            source_sql_sha256=CANDIDATE_SQL_SHA256,
            source_query_receipt=candidate_receipt,
            rows=candidate_rows,
        )
        normalized_players = engine.build_player_catalog_object(
            task_id=TASK_ID,
            source_authority=placeholder,
            players=player_rows,
        )
    except engine.CorpusRetrievalError as exc:
        raise RetrievalInputPublicationError("captured row schema differs") from exc
    if (
        normalized_candidates["rows"] != candidate_rows
        or normalized_players["players"] != player_rows
    ):
        raise RetrievalInputPublicationError("captured rows are not normalized")
    panel_counts = Counter(
        str(row["panel_id"]) for row in normalized_candidates["rows"]
    )
    if panel_counts != Counter(dict(zip(PANEL_IDS, EXPECTED_CANDIDATE_COUNTS))):
        raise RetrievalInputPublicationError("captured candidate census differs")
    if len(normalized_players["players"]) != EXPECTED_PLAYER_COUNT:
        raise RetrievalInputPublicationError("captured player census differs")

    if not isinstance(validation, Mapping):
        raise RetrievalInputPublicationError("capture validation is not an object")
    _validate_self_hash(
        validation, field="validation_sha256", label="capture validation"
    )
    if (
        capture["validation_sha256"] != validation["validation_sha256"]
        or validation.get("task_id") != TASK_ID
        or validation.get("snapshot_at_utc") != SNAPSHOT_AT
        or validation.get("candidate_rows") != len(candidate_rows)
        or validation.get("catalog_players") != len(player_rows)
        or validation.get("normalized_candidate_rows_sha256")
        != engine.canonical_sha256(candidate_rows)
        or validation.get("normalized_player_rows_sha256")
        != engine.canonical_sha256(player_rows)
        or validation.get("raw_candidate_query_rows_sha256")
        != query_authority["candidate_query"]["rows_sha256"]
        or validation.get("raw_player_query_rows_sha256")
        != query_authority["player_query"]["rows_sha256"]
        or validation.get("actual_outcome_columns_selected") is not False
        or validation.get("uses_realized_outcomes") is not False
        or validation.get("artifact_origins")
        != [row["origin"] for row in WORLD_ORIGINS]
    ):
        raise RetrievalInputPublicationError("capture validation differs")
    return {
        "capture": dict(capture),
        "candidate_rows": candidate_rows,
        "player_rows": player_rows,
        "query_authority": dict(query_authority),
        "query_authority_raw": raw_files["query-authority.json"],
        "validation": dict(validation),
    }


def _planned_publication_uris() -> list[str]:
    return [
        QUERY_AUTHORITY_URI,
        CANDIDATE_ROWS_URI,
        PLAYER_CATALOG_URI,
        SOURCE_LOCK_URI,
        *[
            f"{INPUT_PREFIX}tasks/0000/worlds/{row['block_id']}.npz"
            for row in WORLD_ORIGINS
        ],
        PRODUCER_AUTHORITY_URI,
        SNAPSHOT_MANIFEST_URI,
        SUITE_MANIFEST_URI,
        PUBLICATION_RECEIPT_URI,
    ]


def _publish_input_bundle(
    *, capture_bundle: Mapping[str, object], source_lock_raw: bytes,
    source_lock_origin: Mapping[str, object],
    world_sources: Sequence[Mapping[str, object]],
    engine_release: Mapping[str, object], created_at_utc: str,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
    assert_pristine: PristineCheck,
) -> dict[str, object]:
    """Publish one deterministic input bundle from locally verified bytes.

    ``assert_pristine`` must census all object generations beneath both
    supplied prefixes.  Publication still uses create-if-absent semantics to
    close the race between that census and each write.
    """
    query_authority = capture_bundle.get("query_authority")
    candidate_rows = capture_bundle.get("candidate_rows")
    player_rows = capture_bundle.get("player_rows")
    capture_manifest = capture_bundle.get("capture")
    validation = capture_bundle.get("validation")
    if (
        not isinstance(query_authority, Mapping)
        or type(candidate_rows) is not list
        or type(player_rows) is not list
        or not isinstance(capture_manifest, Mapping)
        or not isinstance(validation, Mapping)
    ):
        raise RetrievalInputPublicationError("capture bundle shape differs")
    try:
        normalized_query_authority = engine.validate_input_query_authority(
            query_authority
        )
    except (AttributeError, engine.CorpusRetrievalError) as exc:
        raise RetrievalInputPublicationError(
            "capture query authority failed core validation"
        ) from exc
    if normalized_query_authority != query_authority:
        raise RetrievalInputPublicationError("capture query authority replay differs")
    query_authority = normalized_query_authority
    query_raw = _canonical(query_authority)
    if query_raw != capture_bundle.get("query_authority_raw"):
        raise RetrievalInputPublicationError("query authority capture bytes differ")

    source_lock_identity = _identity(
        source_lock_origin, label="source-lock origin"
    )
    if (
        type(source_lock_raw) is not bytes
        or len(source_lock_raw) != source_lock_identity["bytes"]
        or _sha(source_lock_raw) != source_lock_identity["sha256"]
    ):
        raise RetrievalInputPublicationError("source-lock origin bytes differ")
    if len(world_sources) != len(WORLD_ORIGINS):
        raise RetrievalInputPublicationError("world source count differs")
    normalized_worlds: list[dict[str, object]] = []
    for ordinal, (raw_row, frozen) in enumerate(
        zip(world_sources, WORLD_ORIGINS, strict=True)
    ):
        if not isinstance(raw_row, Mapping) or set(raw_row) != {
            "block_id", "panel_id", "expected_candidate_count", "origin", "raw",
        }:
            raise RetrievalInputPublicationError(
                f"world source[{ordinal}] fields differ"
            )
        if (
            raw_row["block_id"] != frozen["block_id"]
            or raw_row["panel_id"] != frozen["panel_id"]
            or raw_row["expected_candidate_count"]
            != frozen["expected_candidate_count"]
        ):
            raise RetrievalInputPublicationError(
                f"world source[{ordinal}] frozen metadata differs"
            )
        origin = _identity(raw_row["origin"], label=f"world {ordinal} origin")
        if origin != _identity(frozen["origin"], label=f"frozen world {ordinal}"):
            raise RetrievalInputPublicationError(
                f"world source[{ordinal}] origin identity differs"
            )
        raw = raw_row["raw"]
        if (
            type(raw) is not bytes
            or len(raw) != origin["bytes"]
            or _sha(raw) != origin["sha256"]
        ):
            raise RetrievalInputPublicationError(
                f"world source[{ordinal}] origin bytes differ"
            )
        normalized_worlds.append({
            "block_id": frozen["block_id"],
            "panel_id": frozen["panel_id"],
            "expected_candidate_count": frozen["expected_candidate_count"],
            "origin": origin,
            "raw": raw,
        })

    def source_bodies(
        query_identity: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        try:
            candidate = engine.build_candidate_rows_object(
                task_id=TASK_ID,
                source_authority=query_identity,
                source_sql_sha256=CANDIDATE_SQL_SHA256,
                source_query_receipt=query_authority["candidate_query"],
                rows=candidate_rows,
            )
            player = engine.build_player_catalog_object(
                task_id=TASK_ID,
                source_authority=query_identity,
                players=player_rows,
            )
            engine.validate_candidate_rows_object(candidate)
            engine.validate_player_catalog_object(player)
        except engine.CorpusRetrievalError as exc:
            raise RetrievalInputPublicationError(
                "query authority could not bind source bodies"
            ) from exc
        if (
            candidate["source_authority"] != player["source_authority"]
            or candidate["source_query_receipt"]
            != query_authority["candidate_query"]
            or query_authority["player_query"]["row_count"] != len(player_rows)
            or query_authority["player_query"]["normalized_rows_sha256"]
            != engine.canonical_sha256(player["players"])
            or validation.get("normalized_candidate_rows_sha256")
            != engine.canonical_sha256(candidate["rows"])
            or validation.get("normalized_player_rows_sha256")
            != engine.canonical_sha256(player["players"])
        ):
            raise RetrievalInputPublicationError(
                "candidate/player query binding differs"
            )
        return candidate, player

    def world_bindings(
        staged_identities: Sequence[Mapping[str, object]],
    ) -> list[dict[str, object]]:
        if len(staged_identities) != len(normalized_worlds):
            raise RetrievalInputPublicationError("staged world identity count differs")
        return [{
            "ordinal": ordinal,
            "block_id": row["block_id"],
            "panel_id": row["panel_id"],
            "expected_candidate_count": row["expected_candidate_count"],
            "origin": row["origin"],
            "staged": _identity(
                staged,
                label=f"staged world {row['block_id']}",
            ),
        } for ordinal, (row, staged) in enumerate(
            zip(normalized_worlds, staged_identities, strict=True)
        )]

    def producer_body(
        *, query_identity: Mapping[str, object],
        candidate_identity: Mapping[str, object],
        player_identity: Mapping[str, object],
        staged_source_lock: Mapping[str, object],
        staged_worlds: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        return _self_hash({
            "schema_version": "corpus-retrieval-snapshot-producer-authority/v1",
            "publication_mode": "create_once",
            "run_id": RUN_ID,
            "snapshot_id": SNAPSHOT_ID,
            "task_id": TASK_ID,
            "capture_sha256": capture_manifest["capture_sha256"],
            "capture_validation_sha256": validation["validation_sha256"],
            "query_authority": _identity(
                query_identity, label="producer query authority"
            ),
            "candidate_query_rows_sha256": query_authority[
                "candidate_query"
            ]["rows_sha256"],
            "candidate_normalized_rows_sha256": validation[
                "normalized_candidate_rows_sha256"
            ],
            "player_query_rows_sha256": query_authority[
                "player_query"
            ]["rows_sha256"],
            "player_normalized_rows_sha256": validation[
                "normalized_player_rows_sha256"
            ],
            "candidate_rows_object": _identity(
                candidate_identity, label="producer candidate rows"
            ),
            "player_catalog_object": _identity(
                player_identity, label="producer player catalog"
            ),
            "source_lock": {
                "origin": source_lock_identity,
                "staged": _identity(
                    staged_source_lock, label="producer staged source lock"
                ),
            },
            "world_blocks": [dict(row) for row in staged_worlds],
            "uses_realized_outcomes": False,
            "licenses": {
                "corpus_fill_authority": False,
                "historical_outcome_read_authority": False,
                "live_money_policy_authority": False,
                "production_default_change_authority": False,
            },
        }, "producer_authority_sha256")

    def snapshot_body(
        *, candidate_identity: Mapping[str, object],
        player_identity: Mapping[str, object],
        staged_worlds: Sequence[Mapping[str, object]],
        producer_identity: Mapping[str, object],
    ) -> dict[str, object]:
        task = {
            "task_index": 0,
            "task_id": TASK_ID,
            "slate": {"season": 2023, "week": 1, "slate_id": "2023-w1-main"},
            "candidate_rows_object": candidate_identity,
            "player_catalog_object": player_identity,
            "world_blocks": [{
                "ordinal": row["ordinal"],
                "block_id": row["block_id"],
                "panel_id": row["panel_id"],
                "artifact_object": row["staged"],
                "format": "retained-candidate-world-npz/v1",
                "expected_candidate_count": row["expected_candidate_count"],
                "expected_player_count": EXPECTED_PLAYER_COUNT,
                "expected_world_count": engine.WORLDS_PER_BLOCK,
            } for row in staged_worlds],
        }
        try:
            result = engine.build_snapshot_manifest(
                snapshot_id=SNAPSHOT_ID,
                created_at_utc=created_at_utc,
                producer={
                    "producer_id": "corpus-retrieval-input-stager",
                    "producer_version": "v1",
                    "producer_run_id": RUN_ID,
                    "producer_authority": producer_identity,
                },
                tasks=[task],
            )
            engine.validate_snapshot_manifest(result)
            return result
        except engine.CorpusRetrievalError as exc:
            raise RetrievalInputPublicationError("snapshot assembly failed") from exc

    def suite_body(
        snapshot: Mapping[str, object],
        snapshot_identity: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            result = engine.build_suite_manifest(
                run_id=RUN_ID,
                created_at_utc=created_at_utc,
                output_prefix=OUTPUT_PREFIX,
                snapshot_manifest=snapshot,
                snapshot_manifest_identity=snapshot_identity,
                entry_budget=engine.DEFAULT_ENTRY_BUDGET,
                engine_release=engine_release,
            )
            engine.validate_suite_manifest(result)
        except engine.CorpusRetrievalError as exc:
            raise RetrievalInputPublicationError("suite assembly failed") from exc
        if result["suite_manifest_uri"] != SUITE_MANIFEST_URI:
            raise RetrievalInputPublicationError("suite publication URI differs")
        return result

    # Close every pure schema/content failure before the first cloud write.
    preview_query_identity = engine.object_identity_for_bytes(
        uri=QUERY_AUTHORITY_URI, generation="1", raw=query_raw
    )
    preview_candidate, preview_player = source_bodies(preview_query_identity)
    preview_candidate_raw = _canonical(preview_candidate)
    preview_player_raw = _canonical(preview_player)
    preview_candidate_identity = engine.object_identity_for_bytes(
        uri=CANDIDATE_ROWS_URI, generation="1", raw=preview_candidate_raw
    )
    preview_player_identity = engine.object_identity_for_bytes(
        uri=PLAYER_CATALOG_URI, generation="1", raw=preview_player_raw
    )
    preview_source_lock = engine.object_identity_for_bytes(
        uri=SOURCE_LOCK_URI, generation="1", raw=source_lock_raw
    )
    preview_world_identities = [
        engine.object_identity_for_bytes(
            uri=f"{INPUT_PREFIX}tasks/0000/worlds/{row['block_id']}.npz",
            generation="1",
            raw=row["raw"],
        ) for row in normalized_worlds
    ]
    preview_worlds = world_bindings(preview_world_identities)
    preview_producer = producer_body(
        query_identity=preview_query_identity,
        candidate_identity=preview_candidate_identity,
        player_identity=preview_player_identity,
        staged_source_lock=preview_source_lock,
        staged_worlds=preview_worlds,
    )
    preview_producer_identity = engine.object_identity_for_bytes(
        uri=PRODUCER_AUTHORITY_URI,
        generation="1",
        raw=_canonical(preview_producer),
    )
    preview_snapshot = snapshot_body(
        candidate_identity=preview_candidate_identity,
        player_identity=preview_player_identity,
        staged_worlds=preview_worlds,
        producer_identity=preview_producer_identity,
    )
    preview_snapshot_identity = engine.object_identity_for_bytes(
        uri=SNAPSHOT_MANIFEST_URI,
        generation="1",
        raw=_canonical(preview_snapshot),
    )
    suite_body(preview_snapshot, preview_snapshot_identity)

    planned = _planned_publication_uris()
    if len(planned) != len(set(planned)):
        raise RetrievalInputPublicationError("publication plan repeats a URI")
    try:
        assert_pristine([INPUT_PREFIX, OUTPUT_PREFIX])
    except Exception as exc:
        raise RetrievalInputPublicationError(
            "dedicated input/output namespace is not pristine"
        ) from exc

    seen_uris: set[str] = set()
    publication_order: list[str] = []

    def publish(uri: str, raw: bytes, media_type: str) -> dict[str, object]:
        identity = _publish_and_reopen(
            uri=uri,
            raw=raw,
            media_type=media_type,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            seen_uris=seen_uris,
        )
        publication_order.append(uri)
        return identity

    query_identity = publish(QUERY_AUTHORITY_URI, query_raw, "application/json")
    candidate_body, player_body = source_bodies(query_identity)
    candidate_identity = publish(
        CANDIDATE_ROWS_URI, _canonical(candidate_body), "application/json"
    )
    player_identity = publish(
        PLAYER_CATALOG_URI, _canonical(player_body), "application/json"
    )
    staged_source_lock = publish(
        SOURCE_LOCK_URI, source_lock_raw, "application/json"
    )
    staged_world_identities: list[dict[str, object]] = []
    for row in normalized_worlds:
        staged_world_identities.append(publish(
            f"{INPUT_PREFIX}tasks/0000/worlds/{row['block_id']}.npz",
            row["raw"],
            "application/octet-stream",
        ))
    staged_worlds = world_bindings(staged_world_identities)

    producer_authority = producer_body(
        query_identity=query_identity,
        candidate_identity=candidate_identity,
        player_identity=player_identity,
        staged_source_lock=staged_source_lock,
        staged_worlds=staged_worlds,
    )
    producer_identity = publish(
        PRODUCER_AUTHORITY_URI,
        _canonical(producer_authority),
        "application/json",
    )

    snapshot = snapshot_body(
        candidate_identity=candidate_identity,
        player_identity=player_identity,
        staged_worlds=staged_worlds,
        producer_identity=producer_identity,
    )
    snapshot_identity = publish(
        SNAPSHOT_MANIFEST_URI, _canonical(snapshot), "application/json"
    )
    suite = suite_body(snapshot, snapshot_identity)
    suite_identity = publish(
        SUITE_MANIFEST_URI, _canonical(suite), "application/json"
    )

    receipt = _self_hash({
        "schema_version": "corpus-retrieval-input-publication/v1",
        "publication_mode": "create_once",
        "created_at_utc": created_at_utc,
        "project": PROJECT,
        "bucket": DEDICATED_BUCKET,
        "input_prefix": INPUT_PREFIX,
        "output_prefix": OUTPUT_PREFIX,
        "run_id": RUN_ID,
        "snapshot_id": SNAPSHOT_ID,
        "task_id": TASK_ID,
        "namespace_pristine_before_publication": True,
        "query_authority": query_identity,
        "candidate_rows_object": candidate_identity,
        "player_catalog_object": player_identity,
        "source_lock": {
            "origin": source_lock_identity,
            "staged": staged_source_lock,
        },
        "world_blocks": staged_worlds,
        "producer_authority": producer_identity,
        "snapshot_manifest": snapshot_identity,
        "suite_manifest": suite_identity,
        "publication_order_before_receipt": list(publication_order),
        "publication_receipt_published_last": True,
        "candidate_player_source_authority_equal": (
            candidate_body["source_authority"] == player_body["source_authority"]
            == query_identity
        ),
        "every_published_object_generation_pinned_and_reopened": True,
        "uses_realized_outcomes": False,
        "retrieval_task_launched": False,
        "licenses": {
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }, "input_publication_sha256")
    receipt_identity = publish(
        PUBLICATION_RECEIPT_URI, _canonical(receipt), "application/json"
    )
    if seen_uris != set(planned) or publication_order[-1] != PUBLICATION_RECEIPT_URI:
        raise RetrievalInputPublicationError("publication coverage/order differs")
    return {
        "publication_receipt": receipt,
        "publication_receipt_identity": receipt_identity,
        "snapshot_manifest": snapshot,
        "snapshot_manifest_identity": snapshot_identity,
        "suite_manifest": suite,
        "suite_manifest_identity": suite_identity,
    }


class _CloudCreateOnceStorage:
    """Minimal generation-pinned adapter, imported only behind both gates."""

    def __init__(self, *, execute: bool, environ: Mapping[str, str]):
        if not execute or environ.get(PUBLICATION_ENABLE_ENV) != "1":
            raise RetrievalInputPublicationError(
                "publication requires --execute and "
                f"{PUBLICATION_ENABLE_ENV}=1"
            )
        from google.cloud import storage

        self._client = storage.Client(project=PROJECT)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        identity = _identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label="cloud object URI",
        )
        bucket, name = str(identity["uri"])[5:].split("/", 1)
        if bucket != DEDICATED_BUCKET:
            raise RetrievalInputPublicationError(
                "publication escaped the dedicated retrieval bucket"
            )
        return bucket, name

    def assert_pristine(self, prefixes: Sequence[str]) -> None:
        if list(prefixes) != [INPUT_PREFIX, OUTPUT_PREFIX]:
            raise RetrievalInputPublicationError("pristine-prefix plan differs")
        for prefix in prefixes:
            bucket, name = self._parts(prefix.removesuffix("/") + "/sentinel")
            object_prefix = name.removesuffix("sentinel")
            rows = list(self._client.list_blobs(
                bucket, prefix=object_prefix, versions=True,
            ))
            if rows:
                raise RetrievalInputPublicationError(
                    f"create-once namespace already contains objects: {prefix}"
                )

    def _exact_versions(self, uri: str) -> list[object]:
        bucket, name = self._parts(uri)
        return [
            blob for blob in self._client.list_blobs(
                bucket, prefix=name, versions=True,
            )
            if blob.name == name
        ]

    def read(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label="cloud read identity")
        bucket, name = self._parts(str(identity["uri"]))
        blob = self._client.bucket(bucket).blob(
            name, generation=int(str(identity["generation"]))
        )
        raw = blob.download_as_bytes(
            if_generation_match=int(str(identity["generation"]))
        )
        if len(raw) != identity["bytes"] or _sha(raw) != identity["sha256"]:
            raise RetrievalInputPublicationError(
                "generation-pinned cloud object differs"
            )
        return raw

    def publish(self, uri: str, raw: bytes, media_type: str) -> dict[str, object]:
        if self._exact_versions(uri):
            raise RetrievalInputPublicationError(
                f"create-once URI already has an object generation: {uri}"
            )
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type=media_type,
                if_generation_match=0,
            )
        except Exception as exc:
            raise RetrievalInputPublicationError(
                f"create-if-absent upload failed: {uri}"
            ) from exc
        generations = self._exact_versions(uri)
        if (
            len(generations) != 1
            or generations[0].generation is None
            or str(generations[0].generation) != str(blob.generation)
        ):
            raise RetrievalInputPublicationError(
                f"create-once generation census differs: {uri}"
            )
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": _sha(raw),
            "bytes": len(raw),
        }
        self.read(identity)
        return identity


def publish_captured_inputs(args: argparse.Namespace) -> dict[str, object]:
    if not args.execute or os.environ.get(PUBLICATION_ENABLE_ENV) != "1":
        raise RetrievalInputPublicationError(
            "publication requires --execute and "
            f"{PUBLICATION_ENABLE_ENV}=1"
        )
    required = {
        "capture_dir": args.capture_dir,
        "source_lock_path": args.source_lock_path,
        "created_at_utc": args.created_at_utc,
        "code_commit": args.code_commit,
        "image_uri": args.image_uri,
        "publication_receipt": args.publication_receipt,
    }
    absent = sorted(key for key, value in required.items() if value is None)
    if absent:
        raise RetrievalInputPublicationError(
            f"publication arguments are absent: {absent}"
        )
    receipt_path = args.publication_receipt
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RetrievalInputPublicationError(
            "local publication receipt path already exists"
        )

    capture_bundle = _load_capture(args.capture_dir)
    source_lock_raw = _read_local_exact(
        args.source_lock_path,
        SOURCE_LOCK_ORIGIN,
        label="source lock",
    )
    worlds = []
    for row in WORLD_ORIGINS:
        block_id = str(row["block_id"])
        worlds.append({
            "block_id": block_id,
            "panel_id": row["panel_id"],
            "expected_candidate_count": row["expected_candidate_count"],
            "origin": row["origin"],
            "raw": _read_local_exact(
                args.artifacts_dir / f"{block_id}.npz",
                row["origin"],
                label=f"world {block_id}",
            ),
        })
    image_uri = str(args.image_uri)
    image_digest = image_uri.rsplit("@", 1)[-1]
    release = {
        "engine_version": "corpus-retrieval-engine-v1",
        "code_repository": CODE_REPOSITORY,
        "code_commit": str(args.code_commit),
        "image_uri": image_uri,
        "image_digest": image_digest,
    }
    storage = _CloudCreateOnceStorage(execute=args.execute, environ=os.environ)
    result = _publish_input_bundle(
        capture_bundle=capture_bundle,
        source_lock_raw=source_lock_raw,
        source_lock_origin=SOURCE_LOCK_ORIGIN,
        world_sources=worlds,
        engine_release=release,
        created_at_utc=str(args.created_at_utc),
        publish_create_once=storage.publish,
        read_exact=storage.read,
        assert_pristine=storage.assert_pristine,
    )
    try:
        _write_once(receipt_path, _canonical(result))
    except RetrievalInputCaptureError as exc:
        raise RetrievalInputPublicationError(
            "local publication receipt write failed after cloud publication"
        ) from exc
    return result


def _arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sql", type=Path, default=CANDIDATE_SQL_PATH)
    parser.add_argument("--player-sql", type=Path, default=PLAYER_SQL_PATH)
    parser.add_argument(
        "--artifacts-dir", type=Path,
        default=Path("/tmp/corpus-retrieval-smoke.N0Ww6T"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--publish-staged-inputs", action="store_true")
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--source-lock-path", type=Path)
    parser.add_argument("--created-at-utc")
    parser.add_argument("--code-commit")
    parser.add_argument("--image-uri")
    parser.add_argument("--publication-receipt", type=Path)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments().parse_args(argv)
    if args.publish_staged_inputs:
        result = publish_captured_inputs(args)
        print(json.dumps({
            "input_publication_sha256": result["publication_receipt"][
                "input_publication_sha256"
            ],
            "publication_receipt_identity": result[
                "publication_receipt_identity"
            ],
            "snapshot_manifest_identity": result["snapshot_manifest_identity"],
            "suite_manifest_identity": result["suite_manifest_identity"],
            "uses_realized_outcomes": False,
            "retrieval_task_launched": False,
        }, sort_keys=True))
    else:
        if args.output_dir is None:
            raise RetrievalInputCaptureError("capture requires --output-dir")
        result = capture(args)
        print(json.dumps({
            "capture_sha256": result["capture_sha256"],
            "uses_realized_outcomes": False,
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
