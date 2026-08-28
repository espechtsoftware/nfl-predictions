"""Minimum 54-slate cloud path for the calibrated R6 L2b belief law.

The module turns the already-calibrated, fixed 2018--2022 L2b release into
immutable 2023--2025 player-world artifacts.  It does not fit a model, read a
lineup outcome, generate a lineup, run a selector, or grade a book.

Only two challenger cells are emitted:

``quarter-world-mixture``
    Exactly 25 percent of every R0--R4 block uses the calibrated L2b law.  The
    world columns are selected by a fixed SHA-256 ordering and are nested in
    the native cell.  This is a prespecified world-mixture treatment, not a
    lineup-allocation rule or a calibrated probability claim.

``native``
    Every column uses the calibrated L2b law.

The incumbent zero-fraction control is referenced from the existing later
source and is never copied.  There is deliberately no 50-percent cell or
parameter grid.  Each task publishes five blocks for each challenger, and a
root-last finalizer binds all 54 task results.  ``load_l2b_world_artifact_v1``
returns the same ``ScoringWorldBlockV1`` surface consumed by the existing
selector/evaluator cross-score path.

Storage is injected.  The module has no bucket-listing, current-generation,
BigQuery, IAM, deployment, or Cloud Run launch capability.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import math
import re
from typing import Final

import numpy as np
import pandas as pd

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as evaluator,
)
from nfl_dfs.research import corpus_r6_l2_base_rate_runtime_v1 as runtime
from nfl_dfs.research import corpus_r6_l2_base_rate_v1 as calibration
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research.object_identity import IDENTITY_FIELDS, content_identity


CONTRACT_ID: Final = "20260828-r6-l2b-panel-cloud-v1"
PIT_TARGET_PANEL_SCHEMA: Final = "corpus-r6-l2b-pit-target-panel/v1"
TASK_MANIFEST_SCHEMA: Final = "corpus-r6-l2b-54-task-manifest/v1"
WORLD_ARTIFACT_RECEIPT_SCHEMA: Final = (
    "corpus-r6-l2b-player-world-artifact-receipt/v1"
)
TASK_RESULT_SCHEMA: Final = "corpus-r6-l2b-panel-task-result/v1"
PANEL_ROOT_SCHEMA: Final = "corpus-r6-l2b-panel-root/v1"
PREPARATION_RESULT_SCHEMA: Final = "corpus-r6-l2b-panel-preparation/v1"
JOB_CONFIGURATION_SCHEMA: Final = "corpus-r6-l2b-cloud-job-configuration/v1"

TASK_COUNT: Final = 54
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
EXPECTED_SLATES: Final = tuple(
    (season, week)
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)
SKILL_POSITIONS: Final = frozenset({"RB", "WR", "TE"})
PIT_PLAYER_FIELDS: Final = (
    "gsis_id", "team", "position", "previous_state", "injury_status",
)

FRACTION_REGISTRY: Final = (
    {
        "fraction_id": "l2b-quarter-world-mixture",
        "numerator": 1,
        "denominator": 4,
        "columns_per_block": 2_500,
        "mechanism": "fixed-25-percent-l2b-world-mixture",
        "calibrated_probability_claimed": False,
    },
    {
        "fraction_id": "l2b-native",
        "numerator": 1,
        "denominator": 1,
        "columns_per_block": 10_000,
        "mechanism": "full-calibrated-l2b-target-law",
        "calibrated_probability_claimed": True,
    },
)
CONTROL_REFERENCE: Final = {
    "fraction_id": "incumbent-control",
    "numerator": 0,
    "denominator": 1,
    "artifact_policy": "reuse-later-source-r0-r4-no-republication",
}
MASK_LAW_ID: Final = "sha256-slate-block-world-quarter-prefix-v1"
COMPONENT_SEED_ROOT: Final = 8_273
MIXTURE_SEED_ROOT: Final = 8_291
FLOAT_CONVERSION_LAW: Final = "finite-float64-to-ieee754-float32-v1"

FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"
OUTPUT_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
)
REUSED_JOB_CPU: Final = "8"
REUSED_JOB_MEMORY: Final = "32Gi"
REUSED_JOB_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1"
REUSED_JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
TASK_TIMEOUT_SECONDS: Final = 86_400
ENTRYPOINT_RELATIVE_PATH: Final = "scripts/run_corpus_r6_l2b_panel_cloud_v1.py"
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
ENTRYPOINT_COMMAND: Final = (
    "/usr/local/bin/python3.11", "-I", ENTRYPOINT_IMAGE_PATH, "execute-task",
)
ENABLE_ENV: Final = "CORPUS_R6_L2B_PANEL_ENABLE"
MANIFEST_IDENTITY_ENV: Final = "CORPUS_R6_L2B_PANEL_MANIFEST_IDENTITY"
REUSED_JOB_UID_ENV: Final = "CORPUS_R6_L2B_PANEL_REUSED_JOB_UID"

MAXIMUM_JSON_INPUT_BYTES: Final = 16_000_000
MAXIMUM_WORLD_ARTIFACT_BYTES: Final = 96_000_000
MAXIMUM_TASK_RESULT_BYTES: Final = 4_000_000
MAXIMUM_PANEL_ROOT_BYTES: Final = 8_000_000
MAXIMUM_PLAYER_COUNT: Final = 1_024

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_JOB = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_BUILD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

_FORBIDDEN_TARGET_TOKENS: Final = frozenset({
    "actual", "actuals", "realized", "score", "scores", "points",
    "winner", "winning", "payout", "roi", "winnings", "rank", "finish",
    "outcome", "outcomes", "target_share", "carry_share", "snap_share",
})
_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_target_player_outcomes",
    "uses_lineup_outcomes",
    "historical_lineup_scoring_licensed",
    "selector_authority",
    "decision_authority",
    "promotion_authority",
    "production_change_licensed",
    "graph_mutation_licensed",
)

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


class CorpusR6L2BPanelCloudV1Error(ValueError):
    """The fixed L2b panel boundary was violated."""


@dataclass(frozen=True, slots=True)
class L2BPanelTaskExecutionV1:
    task_result: Mapping[str, object]
    task_result_identity: Mapping[str, object]


def _fail(message: str) -> None:
    raise CorpusR6L2BPanelCloudV1Error(message)


def _canonical(value: object, *, label: str = "value") -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"{label} is not finite canonical JSON"
        ) from exc


def _hash(value: object, *, label: str = "value") -> str:
    return sha256(_canonical(value, label=label)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be one canonical nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        retained = content_identity(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"{label} content identity differs"
        ) from exc
    identity = dict(zip(IDENTITY_FIELDS, retained, strict=True))
    if (
        not str(identity["uri"]).startswith("gs://")
        or not str(identity["generation"]).isdigit()
        or int(identity["bytes"]) < 1
    ):
        _fail(f"{label} must be one generation-pinned GCS object")
    return identity


def _source_identities(
    values: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    if not isinstance(values, Mapping) or not values:
        _fail("PIT source identities cannot be empty")
    result: dict[str, dict[str, object]] = {}
    for label in sorted(values):
        result[_string(label, label="PIT source label")] = _identity(
            values[label], label=f"PIT source {label}"
        )
    return result


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _self_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in body:
        _fail(f"{field} cannot already exist")
    result = dict(body)
    result[field] = _hash(result, label=field)
    return result


def _validate_self_hash(
    value: object, *, field: str, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    digest = item.pop(field, None)
    if type(digest) is not str or _SHA64.fullmatch(digest) is None:
        _fail(f"{label} SHA-256 differs")
    if digest != _hash(item, label=label):
        _fail(f"{label} self-hash differs")
    return {**item, field: digest}


def _read_bytes(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"{label} generation-pinned read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} differs from its exact content identity")
    return raw, identity


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item, label=label) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _read_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int = MAXIMUM_JSON_INPUT_BYTES,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_bytes(
        identity_value,
        read_exact=read_exact,
        label=label,
        maximum_bytes=maximum_bytes,
    )
    return _strict_json(raw, label=label), identity


def _publish(
    *,
    uri: str,
    raw: bytes,
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
        _fail(f"{label} publication bytes differ")
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, label=f"{label} publication")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} publication identity differs")
    reopened, _ = _read_bytes(
        identity,
        read_exact=read_exact,
        label=f"published {label}",
        maximum_bytes=maximum_bytes,
    )
    if reopened != raw:
        _fail(f"{label} exact reopen differs")
    return identity


def _publish_json(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    return _publish(
        uri=uri,
        raw=_canonical(value, label=label),
        maximum_bytes=maximum_bytes,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label=label,
    )


def _output_prefix(value: object) -> str:
    prefix = _string(value, label="output prefix")
    if (
        not prefix.startswith(OUTPUT_NAMESPACE)
        or not prefix.endswith("/")
        or "?" in prefix
        or "#" in prefix
        or "//" in prefix[5:]
        or any(part in {"", ".", ".."} for part in prefix[5:-1].split("/"))
    ):
        _fail("output prefix is outside the fixed research namespace")
    return prefix


def _target_field_tokens(name: str) -> set[str]:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
    return {
        token for token in re.split(r"[^a-z0-9]+", normalized) if token
    }


def build_pit_target_panel_v1(
    *,
    target_players: pd.DataFrame,
    source_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build the only target-player artifact accepted by panel tasks.

    The caller must catalog-spine the frame before this function.  Missing
    prior role history is represented as ``previous_state='unknown'`` and a
    missing injury observation as ``injury_status=null``; a player may not be
    silently dropped.  Current-week shares and labels are prohibited even if a
    caller promises not to use them.
    """
    if not isinstance(target_players, pd.DataFrame):
        _fail("PIT target players must be a DataFrame")
    columns = [str(name) for name in target_players.columns]
    required = {"season", "week", *PIT_PLAYER_FIELDS}
    if set(columns) != required:
        forbidden = [
            name for name in columns
            if _FORBIDDEN_TARGET_TOKENS.intersection(_target_field_tokens(name))
        ]
        if forbidden:
            _fail(f"PIT target players expose forbidden outcomes {sorted(forbidden)}")
        _fail("PIT target-player columns differ")
    frame = target_players.copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce")
    if (
        frame.empty
        or frame[["season", "week"]].isna().any().any()
        or not np.equal(frame["season"], np.floor(frame["season"])).all()
        or not np.equal(frame["week"], np.floor(frame["week"])).all()
    ):
        _fail("PIT target-player slate keys differ")
    frame["season"] = frame["season"].astype(int)
    frame["week"] = frame["week"].astype(int)
    frame["gsis_id"] = frame["gsis_id"].astype("string")
    frame["team"] = frame["team"].astype("string")
    frame["position"] = frame["position"].astype("string").str.upper()
    frame["previous_state"] = frame["previous_state"].fillna(
        "unknown"
    ).astype("string")
    frame["injury_status"] = frame["injury_status"].astype("string")
    if (
        frame["gsis_id"].isna().any()
        or frame["team"].isna().any()
        or (~frame["position"].isin(SKILL_POSITIONS)).any()
        or (~frame["previous_state"].isin(calibration.PREVIOUS_STATES)).any()
        or frame.duplicated(["season", "week", "gsis_id"]).any()
    ):
        _fail("PIT target-player identities or states differ")
    observed_keys = tuple(sorted({
        (int(row.season), int(row.week))
        for row in frame[["season", "week"]].itertuples(index=False)
    }))
    if observed_keys != EXPECTED_SLATES:
        _fail("PIT target panel must contain the exact 54-slate lattice")
    slates: list[dict[str, object]] = []
    for season, week in EXPECTED_SLATES:
        selected = frame[
            frame["season"].eq(season) & frame["week"].eq(week)
        ].sort_values("gsis_id", kind="mergesort")
        if selected.empty:
            _fail("PIT target panel contains an empty slate")
        players: list[dict[str, object]] = []
        for row in selected.itertuples(index=False):
            injury = None if pd.isna(row.injury_status) else str(row.injury_status)
            players.append({
                "gsis_id": str(row.gsis_id),
                "team": str(row.team),
                "position": str(row.position),
                "previous_state": str(row.previous_state),
                "injury_status": injury,
            })
        slates.append({
            "slate_id": f"{season}-w{week:02d}",
            "season": season,
            "week": week,
            "player_count": len(players),
            "players": players,
            "ordered_player_ids_sha256": _hash(
                [row["gsis_id"] for row in players], label="target player IDs"
            ),
            "players_sha256": _hash(players, label="target players"),
        })
    body: dict[str, object] = {
        "schema_version": PIT_TARGET_PANEL_SCHEMA,
        "contract_id": CONTRACT_ID,
        "slate_count": TASK_COUNT,
        "seasons": [2023, 2024, 2025],
        "weeks": list(range(1, 19)),
        "player_fields": list(PIT_PLAYER_FIELDS),
        "slates": slates,
        "source_identities": _source_identities(source_identities),
        "point_in_time_law": (
            "week-W previous_state uses completed weeks before W; injury_status "
            "is observed no later than the Sunday-main lock"
        ),
        "catalog_spine_required": True,
        "missing_previous_state_law": "unknown",
        "missing_injury_status_law": "null-not-out",
        "current_week_share_columns_present": False,
        "current_week_role_labels_present": False,
        "player_score_columns_present": False,
        **_false_authorities(),
    }
    return validate_pit_target_panel_v1(
        _self_hash(body, field="target_panel_sha256")
    )


def validate_pit_target_panel_v1(value: object) -> dict[str, object]:
    panel = _validate_self_hash(
        value, field="target_panel_sha256", label="PIT target panel"
    )
    expected = {
        "schema_version", "contract_id", "slate_count", "seasons", "weeks",
        "player_fields", "slates", "source_identities", "point_in_time_law",
        "catalog_spine_required", "missing_previous_state_law",
        "missing_injury_status_law", "current_week_share_columns_present",
        "current_week_role_labels_present", "player_score_columns_present",
        *_FALSE_AUTHORITY_FIELDS, "target_panel_sha256",
    }
    if (
        set(panel) != expected
        or panel.get("schema_version") != PIT_TARGET_PANEL_SCHEMA
        or panel.get("contract_id") != CONTRACT_ID
        or panel.get("slate_count") != TASK_COUNT
        or panel.get("seasons") != [2023, 2024, 2025]
        or panel.get("weeks") != list(range(1, 19))
        or panel.get("player_fields") != list(PIT_PLAYER_FIELDS)
        or panel.get("catalog_spine_required") is not True
        or panel.get("missing_previous_state_law") != "unknown"
        or panel.get("missing_injury_status_law") != "null-not-out"
        or any(panel.get(field) is not False for field in (
            "current_week_share_columns_present",
            "current_week_role_labels_present",
            "player_score_columns_present",
            *_FALSE_AUTHORITY_FIELDS,
        ))
    ):
        _fail("PIT target panel boundary differs")
    _source_identities(panel.get("source_identities"))
    slates = _sequence(panel.get("slates"), label="PIT target slates")
    if len(slates) != TASK_COUNT:
        _fail("PIT target slate count differs")
    for ordinal, ((season, week), raw_slate) in enumerate(
        zip(EXPECTED_SLATES, slates, strict=True)
    ):
        slate = _mapping(raw_slate, label=f"PIT target slate[{ordinal}]")
        players = [
            _mapping(row, label=f"PIT target player[{ordinal}]")
            for row in _sequence(slate.get("players"), label="PIT target players")
        ]
        if (
            set(slate) != {
                "slate_id", "season", "week", "player_count", "players",
                "ordered_player_ids_sha256", "players_sha256",
            }
            or slate.get("slate_id") != f"{season}-w{week:02d}"
            or slate.get("season") != season
            or slate.get("week") != week
            or slate.get("player_count") != len(players)
            or not players
            or any(set(player) != set(PIT_PLAYER_FIELDS) for player in players)
        ):
            _fail("PIT target slate fields differ")
        ids = [str(player["gsis_id"]) for player in players]
        if ids != sorted(set(ids)):
            _fail("PIT target players are not uniquely ordered")
        for player in players:
            if (
                not str(player["gsis_id"])
                or not str(player["team"])
                or player["position"] not in SKILL_POSITIONS
                or player["previous_state"] not in calibration.PREVIOUS_STATES
                or player["injury_status"] is not None
                and type(player["injury_status"]) is not str
            ):
                _fail("PIT target player fields differ")
        if (
            slate.get("ordered_player_ids_sha256")
            != _hash(ids, label="target player IDs")
            or slate.get("players_sha256") != _hash(players, label="target players")
        ):
            _fail("PIT target player hash differs")
    return panel


def _validated_later_source(value: object) -> dict[str, object]:
    source = _mapping(value, label="later source freeze")
    try:
        return later.validate_source_freeze(
            source, expected_freeze_sha256=str(source.get("freeze_sha256"))
        )
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            "later source freeze validation failed"
        ) from exc


def _validated_terminal_build_receipt(
    value: object, *, source_commit_sha: str, immutable_image_digest: str,
) -> dict[str, object]:
    receipt = _mapping(value, label="terminal build receipt")
    required = {
        "build_id", "finish_time", "image_digest", "image_tag", "project_id",
        "region", "source_commit", "start_time", "status",
    }
    start_text = receipt.get("start_time")
    finish_text = receipt.get("finish_time")
    try:
        start = datetime.fromisoformat(str(start_text).replace("Z", "+00:00"))
        finish = datetime.fromisoformat(str(finish_text).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            "terminal build receipt timestamps differ"
        ) from exc
    if (
        set(receipt) != required
        or _BUILD_ID.fullmatch(str(receipt.get("build_id", ""))) is None
        or receipt.get("status") != "SUCCESS"
        or receipt.get("project_id") != FIXED_GCP_PROJECT
        or receipt.get("region") != "us-central1"
        or receipt.get("source_commit") != source_commit_sha
        or receipt.get("image_digest") != immutable_image_digest
        or type(receipt.get("image_tag")) is not str
        or not str(receipt["image_tag"]).startswith(
            f"us-central1-docker.pkg.dev/{FIXED_GCP_PROJECT}/"
        )
        or type(start_text) is not str
        or type(finish_text) is not str
        or start.tzinfo is None
        or finish.tzinfo is None
        or start > finish
    ):
        _fail("terminal build receipt does not bind the successful code/image")
    return receipt


def _read_terminal_build_receipt(
    identity_value: object,
    *,
    source_commit_sha: str,
    immutable_image_digest: str,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Exact-open the existing Cloud Build JSON format, canonical or pretty."""
    raw, identity = _read_bytes(
        identity_value,
        read_exact=read_exact,
        label=label,
        maximum_bytes=MAXIMUM_JSON_INPUT_BYTES,
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    return _validated_terminal_build_receipt(
        value,
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
    ), identity


def _slate_catalog(raw_slate: Mapping[str, object]) -> list[dict[str, object]]:
    catalog = [
        _mapping(row, label="later source catalog player")
        for row in _sequence(raw_slate.get("catalog"), label="later source catalog")
    ]
    if not 1 <= len(catalog) <= MAXIMUM_PLAYER_COUNT:
        _fail("later source catalog size differs")
    ids = [str(row.get("id")) for row in catalog]
    if ids != sorted(set(ids)):
        _fail("later source catalog order differs")
    return catalog


def _validate_target_catalog_alignment(
    *, target_slate: Mapping[str, object], source_slate: Mapping[str, object]
) -> None:
    catalog = _slate_catalog(source_slate)
    skill_catalog = [
        row for row in catalog if str(row.get("pos")).upper() in SKILL_POSITIONS
    ]
    targets = [
        _mapping(row, label="aligned PIT target player")
        for row in _sequence(target_slate.get("players"), label="aligned targets")
    ]
    if [str(row.get("id")) for row in skill_catalog] != [
        str(row.get("gsis_id")) for row in targets
    ]:
        _fail("PIT target players do not exactly spine the skill catalog")
    for catalog_row, target_row in zip(skill_catalog, targets, strict=True):
        if (
            str(catalog_row.get("team")) != str(target_row.get("team"))
            or str(catalog_row.get("pos")).upper()
            != str(target_row.get("position")).upper()
        ):
            _fail("PIT target team/position differs from the source catalog")


def _artifact_identities(source_slate: Mapping[str, object]) -> list[dict[str, object]]:
    receipts = [
        _mapping(row, label="ordinary world receipt")
        for row in _sequence(
            source_slate.get("artifact_receipts"), label="ordinary receipts"
        )
    ]
    if [str(row.get("block")) for row in receipts] != list(WORLD_BLOCKS):
        _fail("ordinary world block lattice differs")
    return [
        _identity(
            {key: row.get(key) for key in IDENTITY_FIELDS},
            label=f"ordinary {row['block']} artifact",
        )
        for row in receipts
    ]


def prepare_54_task_manifest_v1(
    *,
    later_source_freeze_identity: Mapping[str, object],
    calibration_release_identity: Mapping[str, object],
    pit_target_panel_identity: Mapping[str, object],
    terminal_build_receipt_identity: Mapping[str, object],
    output_prefix: str,
    source_commit_sha: str,
    immutable_image_digest: str,
    reused_job_name: str,
    reused_job_uid: str,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Validate all compact authorities and publish one fixed task manifest."""
    prefix = _output_prefix(output_prefix)
    if _SHA40.fullmatch(source_commit_sha) is None:
        _fail("source commit must be one lowercase 40-hex SHA")
    if _IMAGE.fullmatch(immutable_image_digest) is None:
        _fail("immutable image digest differs")
    if (
        _JOB.fullmatch(reused_job_name) is None
        or reused_job_name != REUSED_JOB_NAME
    ):
        _fail("reused Cloud Run job name differs")
    if (
        _UUID.fullmatch(reused_job_uid) is None
        or reused_job_uid != REUSED_JOB_UID
    ):
        _fail("reused Cloud Run job UID differs")
    source_raw, source_identity = _read_json(
        later_source_freeze_identity,
        read_exact=read_exact,
        label="later source freeze",
    )
    source = _validated_later_source(source_raw)
    release_raw, release_identity = _read_json(
        calibration_release_identity,
        read_exact=read_exact,
        label="L2b calibration release",
    )
    try:
        release = calibration.validate_l2_base_rate_calibration_release_v1(
            release_raw
        )
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            "L2b calibration release validation failed"
        ) from exc
    if (
        release.get("final_fit_seasons") != [2018, 2019, 2020, 2021, 2022]
        or release.get("final_fit_scope") != "prospective-2023-plus-only"
        or release.get("gate", {}).get("passes") is not True
        or release.get("prospective_challenger_bank_generation_licensed")
        is not True
        or release.get("uses_lineup_outcomes") is not False
    ):
        _fail("L2b release is not the passing fixed 2018--2022 fit")
    target_raw, target_identity = _read_json(
        pit_target_panel_identity,
        read_exact=read_exact,
        label="PIT target panel",
    )
    targets = validate_pit_target_panel_v1(target_raw)
    build_receipt, build_identity = _read_terminal_build_receipt(
        terminal_build_receipt_identity,
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
        read_exact=read_exact,
        label="terminal build receipt",
    )
    source_slates = _sequence(source.get("slates"), label="later source slates")
    target_slates = _sequence(targets.get("slates"), label="PIT target slates")
    if len(source_slates) != TASK_COUNT or len(target_slates) != TASK_COUNT:
        _fail("L2b panel authority does not contain 54 slates")
    rows: list[dict[str, object]] = []
    for task_index, ((season, week), source_row, target_row) in enumerate(
        zip(EXPECTED_SLATES, source_slates, target_slates, strict=True)
    ):
        source_slate = _mapping(source_row, label=f"source slate[{task_index}]")
        target_slate = _mapping(target_row, label=f"target slate[{task_index}]")
        slate_id = f"{season}-w{week:02d}"
        if (
            source_slate.get("slate_id") != slate_id
            or target_slate.get("slate_id") != slate_id
        ):
            _fail("source and target slate order differs")
        _validate_target_catalog_alignment(
            target_slate=target_slate, source_slate=source_slate
        )
        rows.append({
            "task_index": task_index,
            "slate_id": slate_id,
            "season": season,
            "week": week,
            "target_slate_sha256": _hash(target_slate, label="target slate"),
            "ordinary_world_artifact_identities": _artifact_identities(source_slate),
            "task_result_uri": f"{prefix}task-results/{task_index:02d}-{slate_id}.json",
        })
    body: dict[str, object] = {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "contract_id": CONTRACT_ID,
        "task_count": TASK_COUNT,
        "task_rows": rows,
        "later_source_freeze_identity": source_identity,
        "calibration_release_identity": release_identity,
        "calibration_id": release["calibration_id"],
        "calibration_release_sha256": release["release_sha256"],
        "calibration_fit_seasons": [2018, 2019, 2020, 2021, 2022],
        "calibration_fit_held_fixed_across_panel": True,
        "pit_target_panel_identity": target_identity,
        "pit_target_panel_sha256": targets["target_panel_sha256"],
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": _hash(
            build_receipt, label="terminal build receipt"
        ),
        "terminal_build_id": build_receipt["build_id"],
        "source_commit_sha": source_commit_sha,
        "immutable_image_digest": immutable_image_digest,
        "reused_job_name": reused_job_name,
        "reused_job_uid": reused_job_uid,
        "output_prefix": prefix,
        "world_blocks": list(WORLD_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "control_reference": dict(CONTROL_REFERENCE),
        "fraction_registry": [dict(row) for row in FRACTION_REGISTRY],
        "fraction_cells_are_nested": True,
        "additional_fraction_grid_allowed": False,
        "mask_law_id": MASK_LAW_ID,
        "component_seed_root": COMPONENT_SEED_ROOT,
        "mixture_seed_root": MIXTURE_SEED_ROOT,
        "one_reused_job": True,
        "one_immutable_image": True,
        "new_job_creation_allowed": False,
        "calibration_uses_historical_player_outcomes": True,
        "target_player_outcomes_read": False,
        **_false_authorities(),
    }
    manifest = validate_task_manifest_v1(
        _self_hash(body, field="task_manifest_sha256")
    )
    manifest_identity = _publish_json(
        uri=f"{prefix}task-manifest.json",
        value=manifest,
        maximum_bytes=MAXIMUM_JSON_INPUT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="L2b task manifest",
    )
    config = {
        "schema_version": JOB_CONFIGURATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "reused_job_name": reused_job_name,
        "reused_job_uid": reused_job_uid,
        "task_count": TASK_COUNT,
        "parallelism": TASK_COUNT,
        "max_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "cpu": REUSED_JOB_CPU,
        "memory": REUSED_JOB_MEMORY,
        "immutable_image_digest": immutable_image_digest,
        "container_command": list(ENTRYPOINT_COMMAND[:3]),
        "container_args": list(ENTRYPOINT_COMMAND[3:]),
        "environment": {
            ENABLE_ENV: "1",
            MANIFEST_IDENTITY_ENV: json.dumps(
                manifest_identity, sort_keys=True, separators=(",", ":")
            ),
            "CODE_SHA": source_commit_sha,
            "R6_RUNTIME_IMAGE_DIGEST": immutable_image_digest,
            REUSED_JOB_UID_ENV: reused_job_uid,
        },
        "new_job_creation_allowed": False,
        "iam_mutation_required": False,
        "launch_submission_authority": False,
    }
    result = {
        "schema_version": PREPARATION_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "task_count": TASK_COUNT,
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "cloud_run_job_configuration": config,
        "real_artifact_smoke_required_before_fanout": True,
        "fanout_launched": False,
        **_false_authorities(),
    }
    return result


def validate_task_manifest_v1(value: object) -> dict[str, object]:
    manifest = _validate_self_hash(
        value, field="task_manifest_sha256", label="L2b task manifest"
    )
    expected_fields = {
        "schema_version", "contract_id", "task_count", "task_rows",
        "later_source_freeze_identity", "calibration_release_identity",
        "calibration_id", "calibration_release_sha256",
        "calibration_fit_seasons", "calibration_fit_held_fixed_across_panel",
        "pit_target_panel_identity", "pit_target_panel_sha256",
        "terminal_build_receipt_identity", "terminal_build_receipt_sha256",
        "terminal_build_id", "source_commit_sha", "immutable_image_digest",
        "reused_job_name", "reused_job_uid", "output_prefix",
        "world_blocks", "worlds_per_block", "control_reference",
        "fraction_registry", "fraction_cells_are_nested",
        "additional_fraction_grid_allowed", "mask_law_id",
        "component_seed_root", "mixture_seed_root", "one_reused_job",
        "one_immutable_image", "new_job_creation_allowed",
        "calibration_uses_historical_player_outcomes",
        "target_player_outcomes_read", *_FALSE_AUTHORITY_FIELDS,
        "task_manifest_sha256",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != TASK_MANIFEST_SCHEMA
        or manifest.get("contract_id") != CONTRACT_ID
        or manifest.get("task_count") != TASK_COUNT
        or manifest.get("world_blocks") != list(WORLD_BLOCKS)
        or manifest.get("worlds_per_block") != WORLDS_PER_BLOCK
        or manifest.get("control_reference") != CONTROL_REFERENCE
        or manifest.get("fraction_registry")
        != [dict(row) for row in FRACTION_REGISTRY]
        or manifest.get("fraction_cells_are_nested") is not True
        or manifest.get("additional_fraction_grid_allowed") is not False
        or manifest.get("mask_law_id") != MASK_LAW_ID
        or manifest.get("component_seed_root") != COMPONENT_SEED_ROOT
        or manifest.get("mixture_seed_root") != MIXTURE_SEED_ROOT
        or manifest.get("calibration_fit_seasons")
        != [2018, 2019, 2020, 2021, 2022]
        or manifest.get("calibration_fit_held_fixed_across_panel") is not True
        or manifest.get("one_reused_job") is not True
        or manifest.get("one_immutable_image") is not True
        or manifest.get("new_job_creation_allowed") is not False
        or manifest.get("calibration_uses_historical_player_outcomes") is not True
        or manifest.get("target_player_outcomes_read") is not False
        or any(manifest.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("L2b task manifest policy differs")
    for name in (
        "later_source_freeze_identity", "calibration_release_identity",
        "pit_target_panel_identity", "terminal_build_receipt_identity",
    ):
        _identity(manifest.get(name), label=name)
    if (
        _SHA40.fullmatch(str(manifest.get("source_commit_sha", ""))) is None
        or _IMAGE.fullmatch(str(manifest.get("immutable_image_digest", ""))) is None
        or manifest.get("reused_job_name") != REUSED_JOB_NAME
        or manifest.get("reused_job_uid") != REUSED_JOB_UID
        or _SHA64.fullmatch(str(manifest.get("calibration_release_sha256", "")))
        is None
        or _SHA64.fullmatch(str(manifest.get("pit_target_panel_sha256", "")))
        is None
        or _SHA64.fullmatch(
            str(manifest.get("terminal_build_receipt_sha256", ""))
        ) is None
        or _BUILD_ID.fullmatch(str(manifest.get("terminal_build_id", ""))) is None
        or _output_prefix(manifest.get("output_prefix"))
        != manifest.get("output_prefix")
    ):
        _fail("L2b task manifest identity fields differ")
    rows = [
        _mapping(row, label="L2b task row")
        for row in _sequence(manifest.get("task_rows"), label="L2b task rows")
    ]
    if len(rows) != TASK_COUNT:
        _fail("L2b task row count differs")
    for index, ((season, week), row) in enumerate(
        zip(EXPECTED_SLATES, rows, strict=True)
    ):
        slate_id = f"{season}-w{week:02d}"
        identities = [
            _identity(identity, label="task ordinary artifact")
            for identity in _sequence(
                row.get("ordinary_world_artifact_identities"),
                label="task ordinary artifacts",
            )
        ]
        if (
            set(row) != {
                "task_index", "slate_id", "season", "week",
                "target_slate_sha256", "ordinary_world_artifact_identities",
                "task_result_uri",
            }
            or row.get("task_index") != index
            or row.get("slate_id") != slate_id
            or row.get("season") != season
            or row.get("week") != week
            or _SHA64.fullmatch(str(row.get("target_slate_sha256", ""))) is None
            or len(identities) != len(WORLD_BLOCKS)
            or row.get("task_result_uri")
            != f"{manifest['output_prefix']}task-results/{index:02d}-{slate_id}.json"
        ):
            _fail("L2b task row fields differ")
    return manifest


def _open_manifest(
    *, manifest_identity: Mapping[str, object], read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_json(
        manifest_identity,
        read_exact=read_exact,
        label="L2b task manifest",
    )
    manifest = validate_task_manifest_v1(raw)
    build, retained_build_identity = _read_terminal_build_receipt(
        manifest["terminal_build_receipt_identity"],
        source_commit_sha=str(manifest["source_commit_sha"]),
        immutable_image_digest=str(manifest["immutable_image_digest"]),
        read_exact=read_exact,
        label="manifest terminal build receipt",
    )
    if (
        retained_build_identity != manifest["terminal_build_receipt_identity"]
        or _hash(build, label="manifest terminal build receipt")
        != manifest["terminal_build_receipt_sha256"]
        or build["build_id"] != manifest["terminal_build_id"]
    ):
        _fail("manifest terminal build receipt binding differs")
    return manifest, identity


def _seed(root: int, *, slate_id: str, block: str, role: str) -> int:
    raw = f"{CONTRACT_ID}|{root}|{slate_id}|{block}|{role}".encode("utf-8")
    return int.from_bytes(sha256(raw).digest()[:8], "big") % (2**63 - 1)


def fraction_world_mask_v1(
    *, slate_id: str, block: str, fraction_id: str,
) -> np.ndarray:
    registry = {str(row["fraction_id"]): row for row in FRACTION_REGISTRY}
    if fraction_id not in registry or block not in WORLD_BLOCKS:
        _fail("L2b fraction or block differs")
    count = int(registry[fraction_id]["columns_per_block"])
    if count == WORLDS_PER_BLOCK:
        result = np.ones(WORLDS_PER_BLOCK, dtype=np.bool_)
        result.flags.writeable = False
        return result
    order = sorted(
        range(WORLDS_PER_BLOCK),
        key=lambda index: sha256(
            f"{MASK_LAW_ID}|{slate_id}|{block}|{index:05d}".encode("utf-8")
        ).digest(),
    )
    result = np.zeros(WORLDS_PER_BLOCK, dtype=np.bool_)
    result[np.asarray(order[:count], dtype=np.int64)] = True
    result.flags.writeable = False
    return result


def _target_frame(target_slate: Mapping[str, object]) -> pd.DataFrame:
    rows = _sequence(target_slate.get("players"), label="task target players")
    frame = pd.DataFrame(rows, columns=list(PIT_PLAYER_FIELDS))
    frame.insert(1, "season", int(target_slate["season"]))
    frame.insert(2, "week", int(target_slate["week"]))
    return frame


def _artifact_receipt(
    source_slate: Mapping[str, object], *, block: str,
) -> dict[str, object]:
    rows = [
        _mapping(row, label="ordinary artifact receipt")
        for row in _sequence(
            source_slate.get("artifact_receipts"), label="ordinary receipts"
        )
        if isinstance(row, Mapping) and row.get("block") == block
    ]
    if len(rows) != 1:
        _fail("ordinary source does not contain one exact block receipt")
    return rows[0]


def _aligned_ordinary_block(
    *,
    source_slate: Mapping[str, object],
    block: str,
    expected_identity: Mapping[str, object],
    raw: bytes,
) -> tuple[list[dict[str, object]], np.ndarray]:
    receipt = _artifact_receipt(source_slate, block=block)
    observed_identity = _identity(
        {key: receipt.get(key) for key in IDENTITY_FIELDS},
        label=f"ordinary {block} receipt",
    )
    if observed_identity != _identity(expected_identity, label=f"expected {block}"):
        _fail("ordinary artifact differs from task manifest")
    try:
        loaded = evaluator._load_artifact_worlds_v1(receipt, raw)
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            f"ordinary {block} artifact validation failed"
        ) from exc
    catalog = _slate_catalog(source_slate)
    catalog_ids = [str(row["id"]) for row in catalog]
    loaded_ids = list(loaded.player_ids)
    if set(catalog_ids) != set(loaded_ids) or len(catalog_ids) != len(loaded_ids):
        _fail("ordinary artifact player universe differs from catalog")
    by_id = {player_id: index for index, player_id in enumerate(loaded_ids)}
    draws = np.ascontiguousarray(
        loaded.player_draws[[by_id[player_id] for player_id in catalog_ids]],
        dtype=np.float32,
    )
    if draws.shape != (len(catalog), WORLDS_PER_BLOCK):
        _fail("aligned ordinary player-world matrix differs")
    draws.flags.writeable = False
    return catalog, draws


def _npz_bytes(
    *, player_ids: Sequence[str], player_draws: np.ndarray, mask: np.ndarray,
) -> tuple[bytes, list[dict[str, object]]]:
    maximum = max(len(value) for value in player_ids)
    ids = np.asarray(list(player_ids), dtype=f"<U{maximum}")
    draws = np.ascontiguousarray(player_draws, dtype=np.float32)
    retained_mask = np.ascontiguousarray(mask, dtype=np.bool_)
    try:
        return retrieval.canonical_npz_bytes((
            ("player_ids", ids),
            ("player_draws", draws),
            ("l2b_world_mask", retained_mask),
        ))
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            "L2b artifact canonical NPZ write failed"
        ) from exc


def _validate_world_receipt(value: object) -> dict[str, object]:
    receipt = _validate_self_hash(
        value, field="receipt_sha256", label="L2b world receipt"
    )
    expected = {
        "schema_version", "contract_id", "slate_id", "season", "week",
        "block", "fraction", "mask_law_id", "mask_sha256", "player_count",
        "skill_player_count", "world_count", "ordered_player_ids_sha256",
        "ordinary_world_artifact_identity", "calibration_release_identity",
        "pit_target_panel_identity", "component_seed", "mixture_seed",
        "l2b_application_receipt_sha256", "l2b_component_receipt_sha256",
        "l2b_challenger_receipt_sha256", "l2b_belief_world_artifact_sha256",
        "float_conversion_law", "npz_members", "world_artifact_identity",
        "non_skill_rows_byte_identical_to_incumbent",
        "unmasked_columns_byte_identical_to_incumbent",
        "fraction_cells_nested", "calibration_fit_held_fixed",
        "target_player_columns", *_FALSE_AUTHORITY_FIELDS, "receipt_sha256",
    }
    fraction = receipt.get("fraction")
    registry = {row["fraction_id"]: row for row in FRACTION_REGISTRY}
    season = receipt.get("season")
    week = receipt.get("week")
    block = receipt.get("block")
    if (
        set(receipt) != expected
        or receipt.get("schema_version") != WORLD_ARTIFACT_RECEIPT_SCHEMA
        or receipt.get("contract_id") != CONTRACT_ID
        or block not in WORLD_BLOCKS
        or type(season) is not int
        or type(week) is not int
        or (season, week) not in EXPECTED_SLATES
        or receipt.get("slate_id") != f"{season}-w{week:02d}"
        or not isinstance(fraction, Mapping)
        or fraction not in FRACTION_REGISTRY
        or receipt.get("mask_law_id") != MASK_LAW_ID
        or receipt.get("world_count") != WORLDS_PER_BLOCK
        or type(receipt.get("player_count")) is not int
        or not 1 <= int(receipt["player_count"]) <= MAXIMUM_PLAYER_COUNT
        or type(receipt.get("skill_player_count")) is not int
        or not 1 <= int(receipt["skill_player_count"]) < int(receipt["player_count"])
        or receipt.get("float_conversion_law") != FLOAT_CONVERSION_LAW
        or receipt.get("non_skill_rows_byte_identical_to_incumbent") is not True
        or receipt.get("unmasked_columns_byte_identical_to_incumbent") is not True
        or receipt.get("fraction_cells_nested") is not True
        or receipt.get("calibration_fit_held_fixed") is not True
        or receipt.get("target_player_columns") != [
            "gsis_id", "season", "week", "team", "position",
            "previous_state", "injury_status",
        ]
        or any(receipt.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
        or receipt.get("component_seed") != _seed(
            COMPONENT_SEED_ROOT,
            slate_id=str(receipt.get("slate_id")),
            block=str(block),
            role="component",
        )
        or receipt.get("mixture_seed") != _seed(
            MIXTURE_SEED_ROOT,
            slate_id=str(receipt.get("slate_id")),
            block=str(block),
            role="mixture",
        )
    ):
        _fail("L2b world receipt boundary differs")
    for name in (
        "ordinary_world_artifact_identity", "calibration_release_identity",
        "pit_target_panel_identity", "world_artifact_identity",
    ):
        _identity(receipt.get(name), label=name)
    for name in (
        "mask_sha256", "ordered_player_ids_sha256",
        "l2b_application_receipt_sha256", "l2b_component_receipt_sha256",
        "l2b_challenger_receipt_sha256", "l2b_belief_world_artifact_sha256",
    ):
        if _SHA64.fullmatch(str(receipt.get(name, ""))) is None:
            _fail(f"L2b world receipt {name} differs")
    members = receipt.get("npz_members")
    if (
        not isinstance(members, list)
        or [row.get("name") for row in members if isinstance(row, Mapping)]
        != ["player_ids", "player_draws", "l2b_world_mask"]
    ):
        _fail("L2b world receipt NPZ members differ")
    return receipt


def load_l2b_world_artifact_v1(
    receipt_value: Mapping[str, object], raw: bytes,
) -> evaluator.ScoringWorldBlockV1:
    """Validate one immutable artifact and expose the shared scoring surface."""
    receipt = _validate_world_receipt(receipt_value)
    identity = _identity(
        receipt["world_artifact_identity"], label="L2b world artifact"
    )
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail("L2b world artifact bytes differ")
    try:
        with np.load(BytesIO(raw), allow_pickle=False) as archive:
            if archive.files != [
                "player_ids", "player_draws", "l2b_world_mask"
            ]:
                _fail("L2b world artifact member order differs")
            ids_array = np.asarray(archive["player_ids"])
            draws = np.asarray(archive["player_draws"])
            mask = np.asarray(archive["l2b_world_mask"])
    except CorpusR6L2BPanelCloudV1Error:
        raise
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            "L2b world artifact is not a safe NPZ"
        ) from exc
    ids = tuple(ids_array.astype(str).tolist())
    fraction = receipt["fraction"]
    expected_mask = fraction_world_mask_v1(
        slate_id=str(receipt["slate_id"]),
        block=str(receipt["block"]),
        fraction_id=str(fraction["fraction_id"]),
    )
    descriptors = [
        {
            "name": name,
            "dtype": array.dtype.str,
            "shape": [int(size) for size in array.shape],
            "data_sha256": sha256(
                np.ascontiguousarray(array).tobytes(order="C")
            ).hexdigest(),
        }
        for name, array in (
            ("player_ids", ids_array),
            ("player_draws", draws),
            ("l2b_world_mask", mask),
        )
    ]
    if (
        len(ids) != receipt["player_count"]
        or ids != tuple(sorted(set(ids)))
        or _hash(list(ids), label="loaded artifact player IDs")
        != receipt["ordered_player_ids_sha256"]
        or draws.dtype != np.dtype(np.float32)
        or draws.shape != (len(ids), WORLDS_PER_BLOCK)
        or not draws.flags.c_contiguous
        or not np.isfinite(draws).all()
        or mask.dtype != np.dtype(np.bool_)
        or mask.shape != (WORLDS_PER_BLOCK,)
        or int(mask.sum()) != fraction["columns_per_block"]
        or not np.array_equal(mask, expected_mask)
        or sha256(np.ascontiguousarray(mask).tobytes()).hexdigest()
        != receipt["mask_sha256"]
        or descriptors != receipt["npz_members"]
    ):
        _fail("L2b world artifact materialized arrays differ")
    retained = np.ascontiguousarray(draws, dtype=np.float32)
    retained.flags.writeable = False
    return evaluator.ScoringWorldBlockV1(
        block=str(receipt["block"]), player_ids=ids, player_draws=retained
    )


def _task_sources(
    *, manifest: Mapping[str, object], task_index: int, read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object],
]:
    source_raw, _ = _read_json(
        manifest["later_source_freeze_identity"],
        read_exact=read_exact,
        label="task later source",
    )
    source = _validated_later_source(source_raw)
    release_raw, _ = _read_json(
        manifest["calibration_release_identity"],
        read_exact=read_exact,
        label="task calibration release",
    )
    try:
        release = calibration.validate_l2_base_rate_calibration_release_v1(
            release_raw
        )
    except Exception as exc:
        raise CorpusR6L2BPanelCloudV1Error(
            "task calibration release validation failed"
        ) from exc
    targets_raw, _ = _read_json(
        manifest["pit_target_panel_identity"],
        read_exact=read_exact,
        label="task PIT target panel",
    )
    targets = validate_pit_target_panel_v1(targets_raw)
    row = manifest["task_rows"][task_index]
    source_slate = source["slates"][task_index]
    target_slate = targets["slates"][task_index]
    if (
        row["slate_id"] != source_slate["slate_id"]
        or row["slate_id"] != target_slate["slate_id"]
        or row["target_slate_sha256"]
        != _hash(target_slate, label="task target slate")
    ):
        _fail("task compact authorities differ from the manifest")
    _validate_target_catalog_alignment(
        target_slate=target_slate, source_slate=source_slate
    )
    return release, source_slate, target_slate, row


def execute_manifest_task_v1(
    *,
    manifest_identity: Mapping[str, object],
    task_index: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> L2BPanelTaskExecutionV1:
    """Execute one slate and publish ten immutable player-world artifacts."""
    manifest, retained_manifest_identity = _open_manifest(
        manifest_identity=manifest_identity, read_exact=read_exact
    )
    if type(task_index) is not int or not 0 <= task_index < TASK_COUNT:
        _fail("L2b task index differs")
    release, source_slate, target_slate, task_row = _task_sources(
        manifest=manifest, task_index=task_index, read_exact=read_exact
    )
    slate_id = str(task_row["slate_id"])
    target = _target_frame(target_slate)
    artifacts: list[dict[str, object]] = []
    for block_ordinal, block in enumerate(WORLD_BLOCKS):
        ordinary_identity = task_row["ordinary_world_artifact_identities"][
            block_ordinal
        ]
        raw_ordinary, _ = _read_bytes(
            ordinary_identity,
            read_exact=read_exact,
            label=f"ordinary {slate_id} {block}",
            maximum_bytes=evaluator.MAXIMUM_COMPRESSED_WORLD_BYTES,
        )
        catalog, ordinary = _aligned_ordinary_block(
            source_slate=source_slate,
            block=block,
            expected_identity=ordinary_identity,
            raw=raw_ordinary,
        )
        player_ids = tuple(str(row["id"]) for row in catalog)
        skill_indexes = np.asarray([
            index for index, row in enumerate(catalog)
            if str(row["pos"]).upper() in SKILL_POSITIONS
        ], dtype=np.int64)
        skill_ids = tuple(player_ids[index] for index in skill_indexes)
        if skill_ids != tuple(str(value) for value in target["gsis_id"]):
            _fail("task skill-player order differs from PIT target order")
        component_seed = _seed(
            COMPONENT_SEED_ROOT, slate_id=slate_id, block=block, role="component"
        )
        mixture_seed = _seed(
            MIXTURE_SEED_ROOT, slate_id=slate_id, block=block, role="mixture"
        )
        world_ids = tuple(f"{block}:{index:05d}" for index in range(WORLDS_PER_BLOCK))
        try:
            built = runtime.build_l2_base_rate_prospective_bank_v1(
                release=release,
                target_players=target,
                ordinary_draws=np.ascontiguousarray(
                    ordinary[skill_indexes], dtype=np.float64
                ),
                player_ids=skill_ids,
                world_ids=world_ids,
                calibration_source_identity=manifest["calibration_release_identity"],
                source_identities={
                    "ordinary_world": ordinary_identity,
                    "pit_target_panel": manifest["pit_target_panel_identity"],
                },
                component_seed=component_seed,
                mixture_seed=mixture_seed,
            )
        except Exception as exc:
            raise CorpusR6L2BPanelCloudV1Error(
                f"L2b runtime failed for {slate_id} {block}"
            ) from exc
        native_skill = np.asarray(built.bank.draws, dtype=np.float64)
        if (
            native_skill.shape != (len(skill_ids), WORLDS_PER_BLOCK)
            or not np.isfinite(native_skill).all()
        ):
            _fail("L2b native skill matrix differs")
        for fraction in FRACTION_REGISTRY:
            fraction_id = str(fraction["fraction_id"])
            mask = fraction_world_mask_v1(
                slate_id=slate_id, block=block, fraction_id=fraction_id
            )
            result = ordinary.copy()
            selected_columns = np.flatnonzero(mask)
            converted = np.ascontiguousarray(native_skill, dtype=np.float32)
            result[np.ix_(skill_indexes, selected_columns)] = converted[
                :, selected_columns
            ]
            if (
                not np.array_equal(
                    result[np.setdiff1d(np.arange(len(player_ids)), skill_indexes)],
                    ordinary[np.setdiff1d(np.arange(len(player_ids)), skill_indexes)],
                )
                or not np.array_equal(result[:, ~mask], ordinary[:, ~mask])
            ):
                _fail("L2b fractional bank changed protected incumbent cells")
            artifact_raw, descriptors = _npz_bytes(
                player_ids=player_ids, player_draws=result, mask=mask
            )
            artifact_uri = (
                f"{manifest['output_prefix']}world-banks/{slate_id}/"
                f"{fraction_id}/{block}.npz"
            )
            artifact_identity = _publish(
                uri=artifact_uri,
                raw=artifact_raw,
                maximum_bytes=MAXIMUM_WORLD_ARTIFACT_BYTES,
                publish_create_once=publish_create_once,
                read_exact=read_exact,
                label=f"{slate_id} {fraction_id} {block} world artifact",
            )
            receipt_body: dict[str, object] = {
                "schema_version": WORLD_ARTIFACT_RECEIPT_SCHEMA,
                "contract_id": CONTRACT_ID,
                "slate_id": slate_id,
                "season": int(task_row["season"]),
                "week": int(task_row["week"]),
                "block": block,
                "fraction": dict(fraction),
                "mask_law_id": MASK_LAW_ID,
                "mask_sha256": sha256(
                    np.ascontiguousarray(mask).tobytes()
                ).hexdigest(),
                "player_count": len(player_ids),
                "skill_player_count": len(skill_ids),
                "world_count": WORLDS_PER_BLOCK,
                "ordered_player_ids_sha256": _hash(
                    list(player_ids), label="artifact player IDs"
                ),
                "ordinary_world_artifact_identity": _identity(
                    ordinary_identity, label="receipt ordinary artifact"
                ),
                "calibration_release_identity": _identity(
                    manifest["calibration_release_identity"],
                    label="receipt calibration release",
                ),
                "pit_target_panel_identity": _identity(
                    manifest["pit_target_panel_identity"],
                    label="receipt PIT target panel",
                ),
                "component_seed": component_seed,
                "mixture_seed": mixture_seed,
                "l2b_application_receipt_sha256": built.application.receipt[
                    "receipt_sha256"
                ],
                "l2b_component_receipt_sha256": built.components.receipt[
                    "receipt_sha256"
                ],
                "l2b_challenger_receipt_sha256": built.bank.receipt[
                    "receipt_sha256"
                ],
                "l2b_belief_world_artifact_sha256": built.bank.belief_world_artifact[
                    "artifact_sha256"
                ],
                "float_conversion_law": FLOAT_CONVERSION_LAW,
                "npz_members": descriptors,
                "world_artifact_identity": artifact_identity,
                "non_skill_rows_byte_identical_to_incumbent": True,
                "unmasked_columns_byte_identical_to_incumbent": True,
                "fraction_cells_nested": True,
                "calibration_fit_held_fixed": True,
                "target_player_columns": list(target.columns),
                **_false_authorities(),
            }
            receipt = _validate_world_receipt(
                _self_hash(receipt_body, field="receipt_sha256")
            )
            receipt_identity = _publish_json(
                uri=(
                    f"{manifest['output_prefix']}world-banks/{slate_id}/"
                    f"{fraction_id}/{block}.receipt.json"
                ),
                value=receipt,
                maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
                publish_create_once=publish_create_once,
                read_exact=read_exact,
                label=f"{slate_id} {fraction_id} {block} receipt",
            )
            load_l2b_world_artifact_v1(receipt, artifact_raw)
            artifacts.append({
                "fraction_id": fraction_id,
                "block": block,
                "world_artifact_identity": artifact_identity,
                "world_artifact_receipt_identity": receipt_identity,
                "world_artifact_receipt_sha256": receipt["receipt_sha256"],
            })
    expected_pairs = [
        (str(fraction["fraction_id"]), block)
        for block in WORLD_BLOCKS
        for fraction in FRACTION_REGISTRY
    ]
    if [(row["fraction_id"], row["block"]) for row in artifacts] != expected_pairs:
        _fail("L2b task artifact lattice differs")
    task_body: dict[str, object] = {
        "schema_version": TASK_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "task_index": task_index,
        "slate_id": slate_id,
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": manifest["task_manifest_sha256"],
        "calibration_release_identity": manifest["calibration_release_identity"],
        "calibration_release_sha256": manifest["calibration_release_sha256"],
        "pit_target_panel_identity": manifest["pit_target_panel_identity"],
        "target_slate_sha256": task_row["target_slate_sha256"],
        "fraction_registry": [dict(row) for row in FRACTION_REGISTRY],
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "source_read_roles": [
            "manifest", "later-source", "calibration-release",
            "pit-target-panel", *[f"ordinary-{block}" for block in WORLD_BLOCKS],
        ],
        "target_outcome_columns_read": [],
        "lineup_outcome_columns_read": [],
        "complete": True,
        **_false_authorities(),
    }
    task_result = _validate_task_result_v1(
        _self_hash(task_body, field="task_result_sha256")
    )
    task_result_identity = _publish_json(
        uri=str(task_row["task_result_uri"]),
        value=task_result,
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label=f"L2b task result {slate_id}",
    )
    return L2BPanelTaskExecutionV1(task_result, task_result_identity)


def _validate_task_result_v1(value: object) -> dict[str, object]:
    result = _validate_self_hash(
        value, field="task_result_sha256", label="L2b task result"
    )
    expected_fields = {
        "schema_version", "contract_id", "task_index", "slate_id",
        "manifest_identity", "manifest_sha256",
        "calibration_release_identity", "calibration_release_sha256",
        "pit_target_panel_identity", "target_slate_sha256",
        "fraction_registry", "artifact_count", "artifacts",
        "source_read_roles", "target_outcome_columns_read",
        "lineup_outcome_columns_read", "complete", *_FALSE_AUTHORITY_FIELDS,
        "task_result_sha256",
    }
    task_index = result.get("task_index")
    if (
        set(result) != expected_fields
        or result.get("schema_version") != TASK_RESULT_SCHEMA
        or result.get("contract_id") != CONTRACT_ID
        or type(task_index) is not int
        or not 0 <= task_index < TASK_COUNT
        or result.get("slate_id")
        != f"{EXPECTED_SLATES[task_index][0]}-w{EXPECTED_SLATES[task_index][1]:02d}"
        or _SHA64.fullmatch(str(result.get("manifest_sha256", ""))) is None
        or _SHA64.fullmatch(
            str(result.get("calibration_release_sha256", ""))
        ) is None
        or _SHA64.fullmatch(str(result.get("target_slate_sha256", ""))) is None
        or result.get("fraction_registry")
        != [dict(row) for row in FRACTION_REGISTRY]
        or result.get("artifact_count") != len(WORLD_BLOCKS) * len(FRACTION_REGISTRY)
        or result.get("target_outcome_columns_read") != []
        or result.get("lineup_outcome_columns_read") != []
        or result.get("source_read_roles") != [
            "manifest", "later-source", "calibration-release",
            "pit-target-panel", *[f"ordinary-{block}" for block in WORLD_BLOCKS],
        ]
        or result.get("complete") is not True
        or any(result.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("L2b task result policy differs")
    _identity(result.get("manifest_identity"), label="task manifest identity")
    _identity(
        result.get("calibration_release_identity"),
        label="task calibration identity",
    )
    _identity(result.get("pit_target_panel_identity"), label="task target identity")
    artifacts = [
        _mapping(row, label="task result artifact")
        for row in _sequence(result.get("artifacts"), label="task artifacts")
    ]
    expected_pairs = [
        (str(fraction["fraction_id"]), block)
        for block in WORLD_BLOCKS
        for fraction in FRACTION_REGISTRY
    ]
    if [(row.get("fraction_id"), row.get("block")) for row in artifacts] != expected_pairs:
        _fail("L2b task result artifact order differs")
    for row in artifacts:
        if set(row) != {
            "fraction_id", "block", "world_artifact_identity",
            "world_artifact_receipt_identity", "world_artifact_receipt_sha256",
        }:
            _fail("L2b task result artifact fields differ")
        _identity(row["world_artifact_identity"], label="result world artifact")
        _identity(
            row["world_artifact_receipt_identity"], label="result world receipt"
        )
        if _SHA64.fullmatch(str(row["world_artifact_receipt_sha256"])) is None:
            _fail("L2b task result receipt SHA differs")
    return result


def _validate_task_result_lineage_v1(
    *,
    manifest: Mapping[str, object],
    retained_manifest_identity: Mapping[str, object],
    task_index: int,
    task_result_identity: Mapping[str, object],
    result: Mapping[str, object],
    read_exact: ReadExact,
) -> None:
    """Bind one validated task and all ten receipts to its manifest row."""
    task_row = manifest["task_rows"][task_index]
    if (
        result.get("task_index") != task_index
        or result.get("slate_id") != task_row["slate_id"]
        or result.get("manifest_identity") != retained_manifest_identity
        or result.get("manifest_sha256") != manifest["task_manifest_sha256"]
        or result.get("calibration_release_identity")
        != manifest["calibration_release_identity"]
        or result.get("calibration_release_sha256")
        != manifest["calibration_release_sha256"]
        or result.get("pit_target_panel_identity")
        != manifest["pit_target_panel_identity"]
        or result.get("target_slate_sha256") != task_row["target_slate_sha256"]
        or task_result_identity["uri"] != task_row["task_result_uri"]
    ):
        _fail("task result does not align with the panel manifest")
    ordinary_by_block = dict(zip(
        WORLD_BLOCKS,
        task_row["ordinary_world_artifact_identities"],
        strict=True,
    ))
    fraction_by_id = {
        str(row["fraction_id"]): row for row in FRACTION_REGISTRY
    }
    for artifact in result["artifacts"]:
        receipt_raw, retained_receipt_identity = _read_json(
            artifact["world_artifact_receipt_identity"],
            read_exact=read_exact,
            label=(
                f"task[{task_index}] {artifact['fraction_id']} "
                f"{artifact['block']} world receipt"
            ),
            maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
        receipt = _validate_world_receipt(receipt_raw)
        fraction_id = str(artifact["fraction_id"])
        block = str(artifact["block"])
        if (
            retained_receipt_identity
            != artifact["world_artifact_receipt_identity"]
            or receipt["receipt_sha256"]
            != artifact["world_artifact_receipt_sha256"]
            or receipt["world_artifact_identity"]
            != artifact["world_artifact_identity"]
            or receipt["slate_id"] != result["slate_id"]
            or receipt["season"] != task_row["season"]
            or receipt["week"] != task_row["week"]
            or receipt["block"] != block
            or receipt["fraction"] != fraction_by_id[fraction_id]
            or receipt["ordinary_world_artifact_identity"]
            != ordinary_by_block[block]
            or receipt["calibration_release_identity"]
            != manifest["calibration_release_identity"]
            or receipt["pit_target_panel_identity"]
            != manifest["pit_target_panel_identity"]
        ):
            _fail("task world receipt does not align with the panel manifest")


def finalize_panel_root_v1(
    *,
    manifest_identity: Mapping[str, object],
    task_result_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Exact-open all 54 results and publish one selector-ready bank root."""
    manifest, retained_manifest_identity = _open_manifest(
        manifest_identity=manifest_identity, read_exact=read_exact
    )
    identities = [
        _identity(row, label=f"task result identity[{index}]")
        for index, row in enumerate(task_result_identities)
    ]
    if len(identities) != TASK_COUNT or len({row["uri"] for row in identities}) != TASK_COUNT:
        _fail("panel finalization requires 54 unique ordered task results")
    results: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    for index, identity in enumerate(identities):
        raw, _ = _read_bytes(
            identity,
            read_exact=read_exact,
            label=f"task result[{index}]",
            maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
        result = _validate_task_result_v1(_strict_json(raw, label="task result"))
        _validate_task_result_lineage_v1(
            manifest=manifest,
            retained_manifest_identity=retained_manifest_identity,
            task_index=index,
            task_result_identity=identity,
            result=result,
            read_exact=read_exact,
        )
        results.append({
            "task_index": index,
            "slate_id": result["slate_id"],
            "task_result_identity": identity,
            "task_result_sha256": result["task_result_sha256"],
        })
        for artifact in result["artifacts"]:
            cells.append({
                "task_index": index,
                "slate_id": result["slate_id"],
                **artifact,
            })
    body: dict[str, object] = {
        "schema_version": PANEL_ROOT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": manifest["task_manifest_sha256"],
        "calibration_release_identity": manifest["calibration_release_identity"],
        "calibration_release_sha256": manifest["calibration_release_sha256"],
        "pit_target_panel_identity": manifest["pit_target_panel_identity"],
        "pit_target_panel_sha256": manifest["pit_target_panel_sha256"],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "terminal_build_receipt_sha256": manifest[
            "terminal_build_receipt_sha256"
        ],
        "terminal_build_id": manifest["terminal_build_id"],
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "reused_job_name": manifest["reused_job_name"],
        "reused_job_uid": manifest["reused_job_uid"],
        "task_count": TASK_COUNT,
        "task_results": results,
        "fraction_registry": [dict(row) for row in FRACTION_REGISTRY],
        "control_reference": dict(CONTROL_REFERENCE),
        "world_blocks": list(WORLD_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "cell_count": len(cells),
        "cells": cells,
        "downstream_adapter": {
            "module": (
                "nfl_dfs.research.corpus_r6_l2b_panel_cloud_v1"
            ),
            "callable": "load_l2b_world_artifact_v1",
            "surface": "ScoringWorldBlockV1",
            "candidate_cross_score": (
                "corpus_r6_current_bank_crossed_screen_evaluation_v1."
                "_cross_score_full_union_v1"
            ),
        },
        "selector_evaluator_chain_reusable": True,
        "all_task_and_world_receipts_exactly_validated": True,
        "complete": True,
        **_false_authorities(),
    }
    root = _self_hash(body, field="panel_root_sha256")
    root_identity = _publish_json(
        uri=f"{manifest['output_prefix']}panel-root.json",
        value=root,
        maximum_bytes=MAXIMUM_PANEL_ROOT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="L2b panel root",
    )
    return {
        "schema_version": "corpus-r6-l2b-panel-finalization/v1",
        "contract_id": CONTRACT_ID,
        "panel_root_identity": root_identity,
        "panel_root_sha256": root["panel_root_sha256"],
        "task_count": TASK_COUNT,
        "cell_count": len(cells),
        "complete": True,
        **_false_authorities(),
    }


__all__ = [
    "CONTRACT_ID",
    "CONTROL_REFERENCE",
    "ENABLE_ENV",
    "EXPECTED_SLATES",
    "FRACTION_REGISTRY",
    "L2BPanelTaskExecutionV1",
    "MANIFEST_IDENTITY_ENV",
    "REUSED_JOB_UID_ENV",
    "REUSED_JOB_NAME",
    "REUSED_JOB_UID",
    "TASK_COUNT",
    "WORLD_BLOCKS",
    "WORLDS_PER_BLOCK",
    "build_pit_target_panel_v1",
    "execute_manifest_task_v1",
    "finalize_panel_root_v1",
    "fraction_world_mask_v1",
    "load_l2b_world_artifact_v1",
    "prepare_54_task_manifest_v1",
    "validate_pit_target_panel_v1",
    "validate_task_manifest_v1",
]
