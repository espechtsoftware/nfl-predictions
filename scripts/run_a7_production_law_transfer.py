#!/usr/bin/env python3
"""Run the conditional frozen A7 production-law score-free transfer.

The predecessor gate is intentionally the first side-effecting boundary in
``run``.  It strictly validates the final positive A7 harvest and realized
lease closure before either a Cloud Storage or BigQuery client is created.
This runner contains no outcome query and never acquires an outcome lease.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Final

import numpy as np
from google.cloud import bigquery, storage


ROOT: Final = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books  # noqa: E402
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY  # noqa: E402
from nfl_dfs.optimizer.lineup import select_tail_entries  # noqa: E402
from nfl_dfs.research import a7_select_ladder as a7  # noqa: E402
from nfl_dfs.research import a7_production_law_transfer as science  # noqa: E402
from nfl_dfs.research.object_identity import (  # noqa: E402
    content_identity,
    live_object_receipt,
    same_object,
)

import finish_a7_select_ladder as a7_transport  # noqa: E402
import run_a2a_rank_factor_split_census as source_lock_api  # noqa: E402
from run_a7_select_ladder import (  # noqa: E402
    PROTOCOL_SHA256 as A7_PROTOCOL_SHA256,
    _array_receipt,
    _candidate_identities,
    _candidate_tags,
    _download_json_object_pinned as _a7_download_json_object_pinned,
    _download_artifact_pinned,
    _query_content_receipt,
)
from run_cbwu_seed_order_audit import (  # noqa: E402
    _candidate_batch,
    _query,
    _upload_create_only,
)
from run_exact_n_scorefree import _is_production_legal  # noqa: E402


VERSION: Final = science.VERSION
RUN_ID: Final = science.PROTOCOL_ID
PROJECT: Final = "nfl-predictions-503414"
PROTOCOL: Final = Path(
    "reports/2026-08-21-a7-production-law-scorefree-selector-transfer-v1.md"
)
PROTOCOL_SHA256: Final = (
    "2c0781ab849827fb6c59e9be8a3df03b5cb220e4e72581cfc08851bdac258aa2"
)
A7_OUT: Final = a7_transport.DEFAULT_OUT

SOURCE_LOCK_URI: Final = source_lock_api.SOURCE_LOCK_URI
SOURCE_LOCK_GENERATION: Final = source_lock_api.SOURCE_LOCK_GENERATION
SOURCE_LOCK_SHA256: Final = source_lock_api.SOURCE_LOCK_SHA256
SOURCE_LOCK_BYTES: Final = source_lock_api.SOURCE_LOCK_BYTES
SOURCE_POLICY_ID: Final = source_lock_api.SOURCE_POLICY_ID
SOURCE_PANELS: Final = source_lock_api.SOURCE_PANELS
SEASONS: Final = source_lock_api.SEASONS
WEEKS: Final = source_lock_api.WEEKS
WORLDS_PER_ARTIFACT: Final = source_lock_api.WORLDS_PER_ARTIFACT
ARTIFACT_COUNT: Final = source_lock_api.ARTIFACT_COUNT
CATALOG_ROWS: Final = source_lock_api.CATALOG_ROWS
REPAIR_PANEL: Final = "20260816-atlas-mvp-repair-r3-2025-v1"
REPAIR_ARTIFACT_URI: Final = (
    "gs://nfl-predictions-503414-raw/cand_scores/"
    "20260816-atlas-mvp-repair-r3-2025-v1/2025_w1_1b661a12cf24.npz"
)
REPAIR_ARTIFACT_SHA256: Final = (
    "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
)

CANDIDATE_TABLE: Final = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE: Final = f"{PROJECT}.nfl_predictions.slate_player_features"
CANDIDATE_SQL: Final = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256
FROM `{CANDIDATE_TABLE}`
WHERE (
  panel_run_id IN UNNEST(@source_panels)
  AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1)
) OR (
  panel_run_id=@repair_panel AND season=2025 AND week=1
)
ORDER BY season, week, panel_run_id, cand_ix
"""
PLAYER_SQL: Final = f"""
SELECT season, week, id AS player_id, name AS player_name, pos AS position,
       team, opp AS opponent, game_id, salary,
       COALESCE(proj,0.0) AS mean_projection
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""
CANDIDATE_COLUMNS: Final = (
    "panel_run_id", "season", "week", "cand_ix", "tag", "all_tags",
    "players", "score_artifact_uri", "score_artifact_sha256",
)
PLAYER_COLUMNS: Final = (
    "season", "week", "player_id", "player_name", "position", "team",
    "opponent", "game_id", "salary", "mean_projection",
)
FORBIDDEN_QUERY_TOKENS: Final = (
    "actual_score", "actual_rank", "actual_ownership", " actual ",
    "selected_rank", "selected ", "payout", "contest_rank", "winner",
    "labels_complete",
)

OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    f"a7-production-law-selector-transfer-runs/{RUN_ID}"
)
SMOKE_OUTPUT_URI: Final = f"{OUTPUT_PREFIX}/preflight/real-artifact-smoke.json"
SUPPORT_OUTPUT_URI: Final = f"{OUTPUT_PREFIX}/preflight/support-census.json"
FREEZE_MANIFEST_URI: Final = f"{OUTPUT_PREFIX}/preflight/freeze-manifest.json"
FULL_OUTPUT_URI: Final = f"{OUTPUT_PREFIX}/result.json"
FREEZE_MANIFEST_VERSION: Final = (
    "a7-production-law-scorefree-selector-transfer-freeze-v1"
)
MODES: Final = ("real-artifact-smoke", "support-census", "full")
SMOKE_SLATES: Final = ((2023, 1),)
FULL_SLATES: Final = tuple(
    (season, week) for season in SEASONS for week in WEEKS
)
FREEZE_IMPLEMENTATION_PATHS: Final = {
    "selector": Path("src/nfl_dfs/optimizer/lineup.py"),
    "production_policy": Path("src/nfl_dfs/inference/production_policy.py"),
    "candidate_combiner": Path(
        "src/nfl_dfs/inference/multiseed_portfolio.py"
    ),
    "inherited_science": Path("src/nfl_dfs/research/a7_select_ladder.py"),
    "transfer_science": Path(
        "src/nfl_dfs/research/a7_production_law_transfer.py"
    ),
    "object_identity": Path("src/nfl_dfs/research/object_identity.py"),
    "source_lock_validator": Path(
        "scripts/run_a2a_rank_factor_split_census.py"
    ),
    "inherited_runner": Path("scripts/run_a7_select_ladder.py"),
    "predecessor_finisher": Path("scripts/finish_a7_select_ladder.py"),
    "query_and_upload_helper": Path(
        "scripts/run_cbwu_seed_order_audit.py"
    ),
    "legality_helper": Path("scripts/run_exact_n_scorefree.py"),
    "runner": Path("scripts/run_a7_production_law_transfer.py"),
    "freeze_builder": Path(
        "scripts/freeze_a7_production_law_transfer.py"
    ),
    "dockerfile": Path("Dockerfile"),
    "cloudbuild": Path("cloudbuild.yaml"),
}
FROZEN_LAW: Final = {
    "source_policy_id": SOURCE_POLICY_ID,
    "source_lock": {
        "uri": SOURCE_LOCK_URI,
        "generation": SOURCE_LOCK_GENERATION,
        "sha256": SOURCE_LOCK_SHA256,
        "bytes": SOURCE_LOCK_BYTES,
    },
    "source_panels": list(SOURCE_PANELS),
    "slates": 54,
    "worlds_per_artifact": WORLDS_PER_ARTIFACT,
    "entry_count": a7.ENTRY_COUNT,
    "ladder_spec": a7.LADDER_SPEC,
    "control_env": dict(a7.CONTROL_ENV),
    "treatment_env": dict(a7.TREATMENT_ENV),
    "only_selector_delta": ["SELECT_LADDER"],
    "inherited_gate_protocol_id": a7.PROTOCOL_ID,
}


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} is not strict finite JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _file_identity(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"required immutable file is absent: {path}")
    raw = path.read_bytes()
    return {
        "name": path.name,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _completion(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("A7 final completion receipt is absent")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            raise RuntimeError("A7 final completion receipt differs")
        key, value = line.split("=", 1)
        if not key or key in result:
            raise RuntimeError("A7 final completion receipt fields differ")
        result[key] = value
    return result


def validate_a7_positive_license(
    out: Path = A7_OUT,
    *,
    closed_validator: Callable[[Path], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Strictly project the one A7 disposition that licenses this transfer.

    This is deliberately local-only.  ``run`` calls it before constructing a
    cloud client, and launch tooling must call the same command before job
    inventory or mutation.
    """
    validator = closed_validator or a7_transport._validate_closed
    try:
        closed = dict(validator(out))
    except Exception as exc:
        raise RuntimeError(
            "final A7 chain does not strictly validate as closed"
        ) from exc
    if closed != {
        **closed,
        "status": "already-closed",
        "run_id": a7_transport.RUN_ID,
        "disposition": "historical-positive-phase-s",
        "lease_action": "released-after-realized-outcome",
    }:
        raise RuntimeError("final A7 closure does not license the transfer")

    report_path = out / "report.json"
    completion_path = out / "completion.txt"
    release_path = out / "lease-release.txt"
    report_raw = report_path.read_bytes() if report_path.is_file() else b""
    report = _strict_json(report_raw, label="final A7 report")
    if report_raw != _canonical_json(report):
        raise RuntimeError("final A7 report is not canonical")
    completion = _completion(completion_path)
    outcome = report.get("outcome")
    fixed = {
        "version": "a7-select-ladder-phase-s-incumbent-v2",
        "run_id": a7_transport.RUN_ID,
        "protocol_sha256": A7_PROTOCOL_SHA256,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "production_law_scorefree_transfer_licensed": True,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    if any(report.get(key) != expected for key, expected in fixed.items()) or \
            not isinstance(outcome, dict) or outcome.get(
                "disposition"
            ) != "historical-positive-phase-s" or outcome.get(
                "production_law_scorefree_transfer_licensed"
            ) is not True or outcome.get(
                "prospective_shadow_licensed"
            ) is not False or outcome.get(
                "production_change_licensed"
            ) is not False:
        raise RuntimeError("final A7 report does not license the transfer")
    report_digest = sha256(report_raw).hexdigest()
    if completion.get("run_id") != a7_transport.RUN_ID or completion.get(
        "disposition"
    ) != "historical-positive-phase-s" or completion.get(
        "strict_science_replay"
    ) != "true" or completion.get("uses_realized_outcomes") != "true" or \
            completion.get("actual_score_query_executed") != "true" or \
            completion.get("production_change_licensed") != "false" or \
            completion.get("prospective_shadow_licensed") != "false" or \
            completion.get("historical_outcome_lease_released") != "false" or \
            completion.get("report_sha256") != report_digest or \
            closed.get("report_sha256") != report_digest:
        raise RuntimeError("final A7 completion does not license the transfer")

    report_identity = _file_identity(report_path)
    completion_identity = _file_identity(completion_path)
    release_identity = _file_identity(release_path)
    finish_identity = _file_identity(out / "finish.sha256")
    return {
        "version": "a7-production-law-transfer-predecessor-license-v1",
        "source_run_id": a7_transport.RUN_ID,
        "source_protocol_sha256": A7_PROTOCOL_SHA256,
        "disposition": "historical-positive-phase-s",
        "strict_science_replay": True,
        "historical_outcome_lease_exact_generation_closed": True,
        "lease_action": "released-after-realized-outcome",
        "report": report_identity,
        "completion": completion_identity,
        "lease_release": release_identity,
        "finish_ledger": finish_identity,
        "production_law_scorefree_transfer_licensed": True,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }


def validate_scorefree_queries() -> None:
    combined = f"{CANDIDATE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "A7 production-law transfer query contains forbidden fields: "
            + ", ".join(present)
        )


def _validate_protocol() -> None:
    path = ROOT / PROTOCOL
    if path.is_symlink() or not path.is_file() or sha256(
        path.read_bytes()
    ).hexdigest() != PROTOCOL_SHA256:
        raise RuntimeError("A7 production-law transfer protocol differs")
    if science.PROTOCOL_ID != RUN_ID or a7.LADDER_SPEC != (
        "170:10,180:10,187:7,194:7,200:6,210:10"
    ) or a7.CONTROL_ENV != {"SELECT_LSE": "0", "SELECT_LADDER": ""} or \
            a7.TREATMENT_ENV != {
                "SELECT_LSE": "0", "SELECT_LADDER": a7.LADDER_SPEC,
            }:
        raise RuntimeError("A7 production-law inherited selector law differs")


def _implementation_receipts() -> dict[str, str]:
    receipts: dict[str, str] = {}
    for label, relative in FREEZE_IMPLEMENTATION_PATHS.items():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(
                f"A7 production-law freeze source is absent: {relative}"
            )
        receipts[label] = sha256(path.read_bytes()).hexdigest()
    return receipts


def _validate_implementation_receipts(value: object) -> None:
    if not isinstance(value, dict) or set(value) != set(
        FREEZE_IMPLEMENTATION_PATHS
    ) or any(
        re.fullmatch(r"[0-9a-f]{64}", str(digest)) is None
        for digest in value.values()
    ):
        raise RuntimeError("A7 production-law freeze implementation differs")
    current = _implementation_receipts()
    for label, digest in current.items():
        if value[label] != digest:
            raise RuntimeError(
                f"A7 production-law freeze implementation differs: {label}"
            )


def _object_identity(
    *, uri: str, generation: str, digest: str, byte_count: int | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "uri": uri,
        "generation": str(generation),
        "sha256": str(digest),
    }
    if byte_count is not None:
        value["bytes"] = int(byte_count)
    if not uri.startswith("gs://") or re.fullmatch(
        r"[1-9][0-9]*", value["generation"],
    ) is None or re.fullmatch(
        r"[0-9a-f]{64}", value["sha256"],
    ) is None or (byte_count is not None and int(byte_count) <= 0):
        raise RuntimeError("A7 production-law immutable object identity differs")
    return value


def _preflight_object_identity(value: object, *, uri: str) -> dict[str, Any]:
    required = {"uri", "generation", "metageneration", "sha256", "bytes"}
    if not isinstance(value, dict) or set(value) != required or value.get(
        "uri"
    ) != uri or value.get("metageneration") != "1":
        raise RuntimeError("A7 production-law freeze preflight identity differs")
    _object_identity(
        uri=uri,
        generation=str(value.get("generation", "")),
        digest=str(value.get("sha256", "")),
        byte_count=int(value.get("bytes", 0)),
    )
    return dict(value)


def _validate_freeze_manifest(
    manifest: object,
    *,
    predecessor: Mapping[str, Any],
    code_sha: str,
    image: str,
    candidate_query_sha256: str,
    player_query_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    required = {
        "version", "status", "run_id", "protocol_id", "protocol_sha256",
        "code_sha", "image", "predecessor_license", "frozen_law",
        "implementation_sha256", "source_query_sha256", "preflights",
        "support_passed", "full_execution_licensed",
        "uses_realized_outcomes", "actual_score_query_executed",
        "historical_outcome_lease_acquired", "production_mutated",
        "shadow_deployment_licensed", "licenses",
    }
    fixed = {
        "version": FREEZE_MANIFEST_VERSION,
        "status": "frozen-for-one-scorefree-transfer",
        "run_id": RUN_ID,
        "protocol_id": science.PROTOCOL_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": code_sha,
        "image": image,
        "predecessor_license": dict(predecessor),
        "frozen_law": FROZEN_LAW,
        "source_query_sha256": {
            "candidates": candidate_query_sha256,
            "players": player_query_sha256,
        },
        "support_passed": True,
        "full_execution_licensed": True,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "historical_outcome_lease_acquired": False,
        "production_mutated": False,
        "shadow_deployment_licensed": False,
        "licenses": science.licenses(),
    }
    if not isinstance(manifest, dict) or set(manifest) != required or any(
        manifest.get(key) != expected for key, expected in fixed.items()
    ):
        raise RuntimeError("A7 production-law execution freeze differs")
    _validate_implementation_receipts(manifest.get("implementation_sha256"))
    preflights = manifest.get("preflights")
    if not isinstance(preflights, dict) or set(preflights) != {
        "smoke", "support"
    }:
        raise RuntimeError("A7 production-law freeze preflight set differs")
    return (
        _preflight_object_identity(preflights["smoke"], uri=SMOKE_OUTPUT_URI),
        _preflight_object_identity(
            preflights["support"], uri=SUPPORT_OUTPUT_URI,
        ),
    )


def _load_execution_freeze(
    gcs: storage.Client,
    *,
    identity: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    code_sha: str,
    image: str,
    candidate_query_sha256: str,
    player_query_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if identity.get("uri") != FREEZE_MANIFEST_URI:
        raise RuntimeError("A7 production-law freeze-manifest URI differs")
    manifest, manifest_object = _a7_download_json_object_pinned(
        gcs, dict(identity),
    )
    smoke_identity, support_identity = _validate_freeze_manifest(
        manifest,
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        candidate_query_sha256=candidate_query_sha256,
        player_query_sha256=player_query_sha256,
    )
    return manifest, manifest_object, smoke_identity, support_identity


def _identity_only(receipt: Mapping[str, Any]) -> dict[str, Any]:
    uri, generation, digest, byte_count = content_identity(receipt)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _load_production_source_lock(
    gcs: storage.Client,
) -> tuple[
    dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]
]:
    receipt, raw = live_object_receipt(gcs, SOURCE_LOCK_URI)
    expected = {
        "uri": SOURCE_LOCK_URI,
        "generation": SOURCE_LOCK_GENERATION,
        "sha256": SOURCE_LOCK_SHA256,
        "bytes": SOURCE_LOCK_BYTES,
    }
    if not same_object(receipt, expected) or len(raw) != SOURCE_LOCK_BYTES or \
            sha256(raw).hexdigest() != SOURCE_LOCK_SHA256:
        raise RuntimeError("A7 production-law source lock identity differs")
    lock = source_lock_api._strict_json(raw)
    artifacts, catalog = source_lock_api._validate_source_lock(lock)
    r3 = next(
        row for row in artifacts
        if (row["season"], row["week"], row["seed"]) == (2025, 1, 3)
    )
    substitution = lock.get("candidate_source_substitution")
    if substitution != {
        "season": 2025,
        "week": 1,
        "seed": 3,
        "panel_run_id": REPAIR_PANEL,
        "original_uri": r3["uri"],
        "repaired_uri": REPAIR_ARTIFACT_URI,
        "sha256": REPAIR_ARTIFACT_SHA256,
        "byte_identical": True,
    } or r3["sha256"] != REPAIR_ARTIFACT_SHA256:
        raise RuntimeError("A7 production-law R3 repair binding differs")
    policy = lock.get("source_policy_receipt")
    if not isinstance(policy, dict) or policy.get("policy_id") != SOURCE_POLICY_ID:
        raise RuntimeError("A7 production-law source policy differs")
    return _identity_only(receipt), artifacts, catalog, policy


def _candidate_params() -> list[Any]:
    return [
        bigquery.ArrayQueryParameter(
            "source_panels", "STRING", list(SOURCE_PANELS),
        ),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
    ]


def _player_params() -> list[Any]:
    return [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
    ]


def _canonical_panel(panel: str) -> str:
    return SOURCE_PANELS[3] if panel == REPAIR_PANEL else panel


def _validate_player_source(
    frame: Any,
    locked_catalog: Sequence[Mapping[str, Any]],
) -> dict[tuple[int, int, str], dict[str, Any]]:
    if tuple(str(value) for value in frame.columns) != PLAYER_COLUMNS or \
            frame.empty or frame.duplicated(
                ["season", "week", "player_id"]
            ).any():
        raise RuntimeError("A7 production-law player source differs")
    result: dict[tuple[int, int, str], dict[str, Any]] = {}
    slates: set[tuple[int, int]] = set()
    for raw in frame.to_dict("records"):
        try:
            season, week = int(raw["season"]), int(raw["week"])
            player_id = str(raw["player_id"])
            projection = float(raw["mean_projection"])
            salary = int(raw["salary"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError("A7 production-law player row differs") from exc
        strings = tuple(str(raw[key]) for key in (
            "player_name", "position", "team", "opponent", "game_id",
        ))
        key = (season, week, player_id)
        if (season, week) not in set(FULL_SLATES) or not player_id or any(
            not value for value in strings
        ) or not math.isfinite(projection) or salary <= 0 or key in result:
            raise RuntimeError("A7 production-law player row differs")
        slates.add((season, week))
        result[key] = {
            **raw,
            "season": season,
            "week": week,
            "player_id": player_id,
            "position": strings[1].upper(),
            "team": strings[2].upper(),
            "mean_projection": projection,
            "salary": salary,
        }
    if slates != set(FULL_SLATES):
        raise RuntimeError("A7 production-law player slate grid differs")
    for row in locked_catalog:
        key = (int(row["season"]), int(row["week"]), str(row["player_id"]))
        current = result.get(key)
        if current is None or current["position"] != str(row["position"]).upper() or \
                current["team"] != str(row["team"]).upper() or current[
                    "mean_projection"
                ] != float(row["mean_projection"]):
            raise RuntimeError("A7 production-law locked catalog differs")
    return result


def _validate_candidate_source(
    frame: Any,
    artifacts: Sequence[Mapping[str, Any]],
    locked_catalog: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int, int], Any]:
    if tuple(str(value) for value in frame.columns) != CANDIDATE_COLUMNS or \
            frame.empty:
        raise RuntimeError("A7 production-law candidate source differs")
    locked = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in artifacts
    }
    if len(locked) != ARTIFACT_COUNT:
        raise RuntimeError("A7 production-law locked artifact grid differs")
    groups: dict[tuple[str, int, int], Any] = {}
    unions: dict[tuple[int, int], set[str]] = {}
    observed_rows = 0
    for (season_raw, week_raw, raw_panel), group in frame.groupby(
        ["season", "week", "panel_run_id"], sort=False,
    ):
        season, week, panel = int(season_raw), int(week_raw), str(raw_panel)
        canonical = _canonical_panel(panel)
        if canonical not in SOURCE_PANELS:
            raise RuntimeError("A7 production-law candidate panel differs")
        expected_raw = (
            REPAIR_PANEL
            if (season, week, canonical) == (2025, 1, SOURCE_PANELS[3])
            else canonical
        )
        if panel != expected_raw:
            raise RuntimeError("A7 production-law repair substitution differs")
        key = (canonical, season, week)
        source = locked.get(key)
        if source is None or key in groups:
            raise RuntimeError("A7 production-law candidate grid differs")
        ordered = group.sort_values("cand_ix", kind="stable").reset_index(drop=True)
        try:
            indices = [int(value) for value in ordered.cand_ix]
        except (TypeError, ValueError) as exc:
            raise RuntimeError("A7 production-law candidate index differs") from exc
        if indices != list(range(len(ordered))) or len(ordered) != int(
            source["candidate_rows"]
        ):
            raise RuntimeError("A7 production-law candidate rows differ")
        expected_uri = REPAIR_ARTIFACT_URI if panel == REPAIR_PANEL else source["uri"]
        if ordered.score_artifact_uri.astype(str).unique().tolist() != [
            expected_uri
        ] or ordered.score_artifact_sha256.astype(str).unique().tolist() != [
            source["sha256"]
        ]:
            raise RuntimeError("A7 production-law candidate artifact differs")
        union = unions.setdefault((season, week), set())
        for row in ordered.to_dict("records"):
            roster = [value for value in str(row["players"]).split(",") if value]
            try:
                tags = json.loads(str(row["all_tags"]))
            except json.JSONDecodeError as exc:
                raise RuntimeError("A7 production-law candidate tags differ") from exc
            if len(roster) != 9 or len(set(roster)) != 9 or not str(
                row["tag"]
            ) or not isinstance(tags, list) or not tags or any(
                not isinstance(value, str) or not value for value in tags
            ):
                raise RuntimeError("A7 production-law candidate row differs")
            union.update(roster)
        groups[key] = ordered
        observed_rows += len(ordered)
    expected_keys = {
        (panel, season, week) for panel in SOURCE_PANELS
        for season, week in FULL_SLATES
    }
    locked_unions: dict[tuple[int, int], set[str]] = {}
    for row in locked_catalog:
        locked_unions.setdefault(
            (int(row["season"]), int(row["week"])), set(),
        ).add(str(row["player_id"]))
    if set(groups) != expected_keys or observed_rows != sum(
        int(row["candidate_rows"]) for row in artifacts
    ) or unions != locked_unions or sum(map(len, unions.values())) != CATALOG_ROWS:
        raise RuntimeError("A7 production-law candidate population differs")
    return groups


def _slate_catalog(frame: Any, season: int, week: int) -> Any:
    return frame[
        frame.season.astype(int).eq(season)
        & frame.week.astype(int).eq(week)
    ].copy()


def _prepare_slate(
    *,
    season: int,
    week: int,
    candidate_groups: Mapping[tuple[str, int, int], Any],
    players: Any,
    artifact_map: Mapping[tuple[str, int, int], Mapping[str, Any]],
    gcs: storage.Client,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = _slate_catalog(players, season, week)
    books = {}
    artifact_receipts = []
    for seed, panel in enumerate(SOURCE_PANELS):
        source = artifact_map[(panel, season, week)]
        artifact, receipt = _download_artifact_pinned(
            gcs,
            str(source["uri"]),
            str(source["sha256"]),
            generation=str(source["generation"]),
            expected_bytes=int(source["bytes"]),
        )
        group = candidate_groups[(panel, season, week)]
        books[f"R{seed}"] = _candidate_batch(group, artifact, catalog)
        artifact_receipts.append({
            "seed": seed,
            "canonical_panel": panel,
            "candidate_panel": str(group.panel_run_id.iloc[0]),
            "season": season,
            "week": week,
            "candidate_rows": len(group),
            **receipt,
        })
    order = tuple(books)
    if order != ("R0", "R1", "R2", "R3", "R4"):
        raise RuntimeError("A7 production-law source order differs")
    combined = combine_cbwu_books(
        books, order, expected_worlds_per_book=WORLDS_PER_ARTIFACT,
    )
    totals = np.asarray(combined.candidate_totals)
    identities = _candidate_identities(combined)
    tags = _candidate_tags(combined)
    selected = a7.select_books(totals)

    production_env = ADOPTED_CLASSIC_POLICY.engine_environment({})
    if production_env.get("SELECT_LSE") != "0" or production_env.get(
        "SELECT_LADDER"
    ) != "":
        raise RuntimeError("A7 production-law control policy differs")
    production_control = select_tail_entries(
        totals, a7.ENTRY_COUNT, 194.0, env=production_env,
    )
    if [int(value) for value in production_control] != selected["control"]:
        raise RuntimeError("A7 production-law control order differs")
    selector_delta = {
        key for key in set(a7.CONTROL_ENV) | set(a7.TREATMENT_ENV)
        if a7.CONTROL_ENV.get(key) != a7.TREATMENT_ENV.get(key)
    }
    if selector_delta != {"SELECT_LADDER"}:
        raise RuntimeError("A7 production-law selector delta differs")

    arms: dict[str, Any] = {}
    for arm in ("control", "treatment"):
        indices = selected[arm]
        if not all(_is_production_legal(combined.candidates[index]) for index in indices):
            raise RuntimeError(f"A7 production-law {arm} book is illegal")
        selected_ids = a7.selected_identities(identities, indices)
        arms[arm] = {
            "selector_env": dict(
                a7.CONTROL_ENV if arm == "control" else a7.TREATMENT_ENV
            ),
            "indices": indices,
            "identities": selected_ids,
            "candidate_source_counts": a7.candidate_source_counts(indices, tags),
            "scorefree": a7.scorefree_book_receipt(
                candidate_totals=totals,
                candidate_identities=identities,
                selected=indices,
                player_ids=combined.player_ids,
                player_draws=np.asarray(combined.row_draws),
            ),
        }
    input_receipts = {
        "candidate_totals": _array_receipt(totals),
        "player_draws": _array_receipt(np.asarray(combined.row_draws)),
        "player_ids_sha256": sha256(_canonical_json({
            "player_ids": [str(value) for value in combined.player_ids],
        })).hexdigest(),
        "candidate_identities_sha256": sha256(_canonical_json({
            "candidate_identities": identities,
        })).hexdigest(),
        "candidate_tags_sha256": sha256(_canonical_json({
            "candidate_tags": tags,
        })).hexdigest(),
    }
    row = {
        "season": season,
        "week": week,
        "uses_realized_outcomes": False,
        "candidate_budget": len(combined.candidates),
        "world_count": int(totals.shape[1]),
        "candidate_pool_shared_across_arms": True,
        "player_worlds_shared_across_arms": True,
        "candidate_totals_shared_across_arms": True,
        "only_selector_input_differs": True,
        "selector_delta": ["SELECT_LADDER"],
        "production_control_reproduced": True,
        "combined_input_receipts": input_receipts,
        "control": arms["control"],
        "treatment": arms["treatment"],
    }
    return row, artifact_receipts


def _compact_slate(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "season": row["season"],
        "week": row["week"],
        "candidate_budget": row["candidate_budget"],
        "world_count": row["world_count"],
        "candidate_pool_shared_across_arms": True,
        "player_worlds_shared_across_arms": True,
        "candidate_totals_shared_across_arms": True,
        "only_selector_input_differs": True,
        "production_control_reproduced": True,
        "combined_input_receipts": row["combined_input_receipts"],
        "control_identities_sha256": sha256(_canonical_json({
            "identities": row["control"]["identities"],
        })).hexdigest(),
        "treatment_identities_sha256": sha256(_canonical_json({
            "identities": row["treatment"]["identities"],
        })).hexdigest(),
        "scorefree_receipt_sha256": sha256(_canonical_json({
            arm: row[arm]["scorefree"] for arm in ("control", "treatment")
        })).hexdigest(),
    }


def _expected_output(mode: str) -> str:
    if mode == "real-artifact-smoke":
        return SMOKE_OUTPUT_URI
    if mode == "support-census":
        return SUPPORT_OUTPUT_URI
    if mode == "full":
        return FULL_OUTPUT_URI
    raise ValueError(f"unknown A7 production-law transfer mode: {mode!r}")


def _validate_expected_query_hashes(
    *,
    mode: str,
    candidate_receipt: Mapping[str, Any],
    player_receipt: Mapping[str, Any],
    expected_candidate_sha256: str,
    expected_player_sha256: str,
) -> None:
    expected = (expected_candidate_sha256, expected_player_sha256)
    if mode == "real-artifact-smoke":
        if expected != ("", ""):
            raise RuntimeError("A7 production-law smoke cannot receive frozen hashes")
        return
    if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in expected) or \
            candidate_receipt.get("sha256") != expected_candidate_sha256 or \
            player_receipt.get("sha256") != expected_player_sha256:
        raise RuntimeError("A7 production-law frozen source query differs")


def _validate_preflight_receipt(
    value: Mapping[str, Any],
    *,
    mode: str,
    predecessor: Mapping[str, Any],
    code_sha: str,
    image: str,
    expected_candidate_sha256: str,
    expected_player_sha256: str,
    expected_preflight_receipts: Mapping[str, Any],
) -> dict[str, Any]:
    query = value.get("source_query_receipts")
    if not isinstance(query, dict) or set(query) != {"candidates", "players"}:
        raise RuntimeError(f"A7 production-law {mode} query receipt differs")
    fixed = {
        "version": VERSION,
        "run_id": RUN_ID,
        "mode": mode,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": code_sha,
        "image": image,
        "predecessor_license": dict(predecessor),
        "preflight_receipts": dict(expected_preflight_receipts),
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "historical_outcome_lease_acquired": False,
        "production_mutated": False,
        "execution_freeze": None,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()) or \
            query["candidates"].get("sha256") != expected_candidate_sha256 or \
            query["players"].get("sha256") != expected_player_sha256 or \
            value.get("transfer_gate") is not None:
        raise RuntimeError(f"A7 production-law {mode} receipt boundary differs")
    if mode == "real-artifact-smoke":
        if value.get("decision") != science.smoke_disposition() or value.get(
            "support"
        ) is not None or value.get("scope") != [[2023, 1]] or len(
            value.get("source_artifacts", [])
        ) != 5:
            raise RuntimeError("A7 production-law smoke receipt differs")
    elif mode == "support-census":
        support = value.get("support")
        if not isinstance(support, dict) or value.get(
            "decision"
        ) != science.support_disposition(support) or value["decision"].get(
            "full_execution_freeze_licensed"
        ) is not True or value.get("scope") != [
            [season, week] for season, week in FULL_SLATES
        ] or len(value.get("source_artifacts", [])) != ARTIFACT_COUNT:
            raise RuntimeError("A7 production-law support receipt did not pass")
    else:
        raise ValueError(f"unsupported preflight mode {mode!r}")
    return dict(value)


def _load_pinned_preflight(
    gcs: storage.Client,
    identity: Mapping[str, Any],
    *,
    uri: str,
    mode: str,
    predecessor: Mapping[str, Any],
    code_sha: str,
    image: str,
    expected_candidate_sha256: str,
    expected_player_sha256: str,
    expected_preflight_receipts: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if identity.get("uri") != uri:
        raise RuntimeError(f"A7 production-law {mode} object URI differs")
    value, object_identity = _a7_download_json_object_pinned(
        gcs, dict(identity),
    )
    validated = _validate_preflight_receipt(
        value,
        mode=mode,
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        expected_candidate_sha256=expected_candidate_sha256,
        expected_player_sha256=expected_player_sha256,
        expected_preflight_receipts=expected_preflight_receipts,
    )
    return validated, object_identity


def run(
    *,
    mode: str,
    output_uri: str,
    expected_candidate_query_sha256: str = "",
    expected_player_query_sha256: str = "",
    a7_out: Path = A7_OUT,
    smoke_generation: str = "",
    smoke_sha256: str = "",
    smoke_bytes: int | None = None,
    freeze_generation: str = "",
    freeze_sha256: str = "",
    freeze_bytes: int | None = None,
) -> dict[str, Any]:
    if mode not in MODES or output_uri != _expected_output(mode):
        raise RuntimeError("A7 production-law execution identity differs")

    # Load-bearing order: this local-only exact predecessor validation must
    # finish before construction of either cloud client below.
    predecessor = validate_a7_positive_license(a7_out)
    _validate_protocol()
    validate_scorefree_queries()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ) is None:
        raise RuntimeError("A7 production-law immutable code/image is required")

    smoke_identity: dict[str, Any] | None = None
    freeze_identity: dict[str, Any] | None = None
    if mode == "real-artifact-smoke":
        if smoke_generation or smoke_sha256 or smoke_bytes is not None or \
                freeze_generation or freeze_sha256 or freeze_bytes is not None:
            raise RuntimeError("A7 production-law smoke has frozen prerequisites")
    elif mode == "support-census":
        if freeze_generation or freeze_sha256 or freeze_bytes is not None:
            raise RuntimeError("A7 production-law support cannot use a freeze")
        smoke_identity = _object_identity(
            uri=SMOKE_OUTPUT_URI,
            generation=smoke_generation,
            digest=smoke_sha256,
            byte_count=smoke_bytes,
        )
    else:
        if smoke_generation or smoke_sha256 or smoke_bytes is not None:
            raise RuntimeError(
                "A7 production-law full preflights must come from the freeze"
            )
        freeze_identity = _object_identity(
            uri=FREEZE_MANIFEST_URI,
            generation=freeze_generation,
            digest=freeze_sha256,
            byte_count=freeze_bytes,
        )

    gcs = storage.Client(project=PROJECT)
    preflight_receipts: dict[str, Any] = {}
    execution_freeze: dict[str, Any] | None = None
    if mode == "support-census":
        assert smoke_identity is not None
        _smoke, preflight_receipts["smoke"] = _load_pinned_preflight(
            gcs,
            smoke_identity,
            uri=SMOKE_OUTPUT_URI,
            mode="real-artifact-smoke",
            predecessor=predecessor,
            code_sha=code_sha,
            image=image,
            expected_candidate_sha256=expected_candidate_query_sha256,
            expected_player_sha256=expected_player_query_sha256,
            expected_preflight_receipts={},
        )
    elif mode == "full":
        assert freeze_identity is not None
        (
            _freeze,
            execution_freeze,
            frozen_smoke,
            frozen_support,
        ) = _load_execution_freeze(
            gcs,
            identity=freeze_identity,
            predecessor=predecessor,
            code_sha=code_sha,
            image=image,
            candidate_query_sha256=expected_candidate_query_sha256,
            player_query_sha256=expected_player_query_sha256,
        )
        _smoke, preflight_receipts["smoke"] = _load_pinned_preflight(
            gcs,
            frozen_smoke,
            uri=SMOKE_OUTPUT_URI,
            mode="real-artifact-smoke",
            predecessor=predecessor,
            code_sha=code_sha,
            image=image,
            expected_candidate_sha256=expected_candidate_query_sha256,
            expected_player_sha256=expected_player_query_sha256,
            expected_preflight_receipts={},
        )
        _support, preflight_receipts["support"] = _load_pinned_preflight(
            gcs,
            frozen_support,
            uri=SUPPORT_OUTPUT_URI,
            mode="support-census",
            predecessor=predecessor,
            code_sha=code_sha,
            image=image,
            expected_candidate_sha256=expected_candidate_query_sha256,
            expected_player_sha256=expected_player_query_sha256,
            expected_preflight_receipts={
                "smoke": preflight_receipts["smoke"],
            },
        )
    source_lock, artifacts, locked_catalog, source_policy = (
        _load_production_source_lock(gcs)
    )
    bq = bigquery.Client(project=PROJECT)
    candidates = _query(bq, CANDIDATE_SQL, _candidate_params())
    players = _query(bq, PLAYER_SQL, _player_params())
    candidate_query = _query_content_receipt(candidates, CANDIDATE_COLUMNS)
    player_query = _query_content_receipt(players, PLAYER_COLUMNS)
    _validate_expected_query_hashes(
        mode=mode,
        candidate_receipt=candidate_query,
        player_receipt=player_query,
        expected_candidate_sha256=expected_candidate_query_sha256,
        expected_player_sha256=expected_player_query_sha256,
    )
    _validate_player_source(players, locked_catalog)
    groups = _validate_candidate_source(candidates, artifacts, locked_catalog)
    artifact_map = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in artifacts
    }

    scope = SMOKE_SLATES if mode == "real-artifact-smoke" else FULL_SLATES
    rows: list[dict[str, Any]] = []
    artifact_receipts: list[dict[str, Any]] = []
    for season, week in scope:
        row, receipts = _prepare_slate(
            season=season,
            week=week,
            candidate_groups=groups,
            players=players,
            artifact_map=artifact_map,
            gcs=gcs,
        )
        rows.append(row)
        artifact_receipts.extend(receipts)

    if mode == "real-artifact-smoke":
        decision = science.smoke_disposition()
        retained_slates: list[dict[str, Any]] = [_compact_slate(rows[0])]
        support = None
        gate = None
    elif mode == "support-census":
        support = a7.support_census(rows)
        decision = science.support_disposition(support)
        retained_slates = [_compact_slate(row) for row in rows]
        gate = None
    else:
        transfer = science.aggregate_transfer(rows)
        decision = {
            key: transfer[key]
            for key in (
                "version", "protocol_id", "uses_realized_outcomes",
                "actual_score_query_executed", "scorefree_transfer_passed",
                "disposition", "licenses",
            )
        }
        retained_slates = rows
        support = transfer["gate"]["support"]
        gate = transfer

    report = {
        "version": VERSION,
        "run_id": RUN_ID,
        "mode": mode,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": code_sha,
        "image": image,
        "predecessor_license": predecessor,
        "source_lock": source_lock,
        "source_policy_id": SOURCE_POLICY_ID,
        "source_simulation_law": source_policy["simulation_law"],
        "source_panels": list(SOURCE_PANELS),
        "source_query_receipts": {
            "candidates": candidate_query,
            "players": player_query,
        },
        "preflight_receipts": preflight_receipts,
        "execution_freeze": execution_freeze,
        "source_grid": {
            "slates": 54,
            "artifacts": ARTIFACT_COUNT,
            "worlds_per_artifact": WORLDS_PER_ARTIFACT,
            "candidate_rows": sum(int(row["candidate_rows"]) for row in artifacts),
            "candidate_union_rows": CATALOG_ROWS,
            "r3_2025_w1_candidate_substitution": REPAIR_PANEL,
            "generation_pinned": True,
        },
        "selector": {
            "inherited_protocol_id": a7.PROTOCOL_ID,
            "ladder_spec": a7.LADDER_SPEC,
            "mean_weight": 0,
            "entry_count": a7.ENTRY_COUNT,
            "prefix_counts": list(a7.PREFIX_COUNTS),
            "control_env": dict(a7.CONTROL_ENV),
            "treatment_env": dict(a7.TREATMENT_ENV),
            "only_selector_delta": ["SELECT_LADDER"],
            "shared_candidate_and_world_batch": True,
        },
        "scope": [[season, week] for season, week in scope],
        "source_artifacts": artifact_receipts,
        "slates": retained_slates,
        "support": support,
        "transfer_gate": gate,
        "decision": decision,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "historical_outcome_lease_acquired": False,
        "production_mutated": False,
    }
    payload = _canonical_json(report)
    output = _upload_create_only(gcs, output_uri, payload)
    return {**report, "output": output}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-predecessor")
    validate.add_argument("--a7-output-dir", type=Path, default=A7_OUT)
    execute = sub.add_parser("run")
    execute.add_argument("--mode", choices=MODES, required=True)
    execute.add_argument("--output-uri", required=True)
    execute.add_argument("--a7-output-dir", type=Path, default=A7_OUT)
    execute.add_argument("--expected-candidate-query-sha256", default="")
    execute.add_argument("--expected-player-query-sha256", default="")
    execute.add_argument("--smoke-generation", default="")
    execute.add_argument("--smoke-sha256", default="")
    execute.add_argument("--smoke-bytes", type=int)
    execute.add_argument("--freeze-generation", default="")
    execute.add_argument("--freeze-sha256", default="")
    execute.add_argument("--freeze-bytes", type=int)
    args = parser.parse_args()
    if args.command == "validate-predecessor":
        value = validate_a7_positive_license(args.a7_output_dir)
        print(json.dumps(value, sort_keys=True))
    else:
        result = run(
            mode=args.mode,
            output_uri=args.output_uri,
            expected_candidate_query_sha256=(
                args.expected_candidate_query_sha256
            ),
            expected_player_query_sha256=args.expected_player_query_sha256,
            a7_out=args.a7_output_dir,
            smoke_generation=args.smoke_generation,
            smoke_sha256=args.smoke_sha256,
            smoke_bytes=args.smoke_bytes,
            freeze_generation=args.freeze_generation,
            freeze_sha256=args.freeze_sha256,
            freeze_bytes=args.freeze_bytes,
        )
        print(json.dumps({
            "run_id": result["run_id"],
            "mode": result["mode"],
            "decision": result["decision"],
            "output": result["output"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
