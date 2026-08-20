#!/usr/bin/env python3
"""Run the frozen, outcome-blind A2a rank-factor split census.

This runner deliberately has no warehouse client, realized-score query,
candidate construction, lineup construction, or portfolio-selection import.
It reads only the locked catalog plus ``player_ids`` and ``player_draws`` from
the generation-pinned source artifacts.  Scientific calculations live only in
``nfl_dfs.research.a2a_rank_factor_split``; this file owns validation,
scope, deterministic serialization, and create-once transport.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Final

from google.cloud import storage
import numpy as np

from nfl_dfs.research import a2a_rank_factor_split as science
from nfl_dfs.research.object_identity import (
    content_identity,
    live_object_receipt,
    same_object,
)


PROJECT: Final = "nfl-predictions-503414"
PROTOCOL_ID: Final = "20260820-a2a-rank-factor-split-scorefree-v2"
RUN_ID: Final = PROTOCOL_ID
PROTOCOL: Final = Path(
    "reports/2026-08-20-a2a-rank-factor-split-scorefree-protocol.md"
)
PROTOCOL_SHA256: Final = (
    "329379ebd7be5e4a92ee34f8a8dd9ae2f6dca90517a81627800f5756852eeab7"
)

SOURCE_LOCK_URI: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    "production-law-dependence-runs/"
    "20260817-production-law-dependence-source-lock-v1/source-lock.json"
)
SOURCE_LOCK_GENERATION: Final = "1786950155692968"
SOURCE_LOCK_SHA256: Final = (
    "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c"
)
SOURCE_LOCK_BYTES: Final = 1_341_911
SOURCE_CATALOG_SHA256: Final = (
    "f18abb6302730f233665c06b353eb71b6997f3ced3bc91d12a9562a2815f96bc"
)
SOURCE_POLICY_ID: Final = "classic-k1-role12-boom40-poscal-cbwu-v4"
SOURCE_PANELS: Final = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
BLOCKS: Final = tuple(f"R{seed}" for seed in range(5))
SEASONS: Final = (2023, 2024, 2025)
WEEKS: Final = tuple(range(1, 19))
WORLDS_PER_ARTIFACT: Final = 10_000
ARTIFACT_COUNT: Final = 270
CATALOG_ROWS: Final = 10_729
ELIGIBLE_ROWS: Final = 9_469
FULL_GRID: Final = tuple(
    (season, week, seed)
    for season in SEASONS
    for week in WEEKS
    for seed in range(5)
)
SMOKE_GRID: Final = ((2023, 1, 0),)

OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    f"a2a-rank-factor-split-runs/{RUN_ID}"
)
SMOKE_OUTPUT_URI: Final = f"{OUTPUT_PREFIX}/smoke.json"
FULL_OUTPUT_URI: Final = f"{OUTPUT_PREFIX}/result.json"

SOURCE_LOCK_FIELDS: Final = frozenset({
    "actual_outcomes_queried",
    "analysis_image",
    "artifact_count",
    "artifact_receipts",
    "candidate_or_lineup_scores_read",
    "candidate_rows",
    "candidate_source_substitution",
    "candidate_union_rows",
    "catalog",
    "catalog_rows",
    "catalog_sha256",
    "code_sha",
    "eligible_rows",
    "production_change_licensed",
    "protocol_sha256",
    "run_id",
    "slates",
    "source_hashes",
    "source_panels",
    "source_policy_receipt",
    "source_population_amendment_sha256",
    "uses_realized_outcomes",
    "version",
})
ARTIFACT_FIELDS: Final = frozenset({
    "bytes",
    "candidate_rows",
    "generation",
    "panel_run_id",
    "season",
    "seed",
    "sha256",
    "updated",
    "uri",
    "week",
})
CATALOG_FIELDS: Final = frozenset({
    "season", "week", "player_id", "position", "team", "mean_projection",
})
# Metadata members are inspected to fail closed on schema drift.  Only the two
# player-world members are materialized; the candidate arrays are never read.
ARTIFACT_MEMBERS: Final = frozenset({
    "cand_ix", "totals", "tail_line", "player_ids", "player_draws",
})
LICENSE_FIELDS: Final = (
    "uses_realized_outcomes",
    "actual_outcomes_queried",
    "candidate_or_lineup_scores_read",
    "historical_remeasurement_licensed",
    "exact80_scoring_licensed",
    "single_stack_arm_licensed",
    "prospective_shadow_licensed",
    "production_change_licensed",
)
GATE_FIELDS: Final = frozenset({
    "passes",
    "mechanical_invariants_pass",
    "directional_conditions_pass",
    "conditions",
    "disposition",
    "licenses",
    "aggregate",
    "block_directions",
})


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("A2a source lock is not strict finite JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("A2a source lock root must be an object")
    return value


def _json_value(value: Any) -> Any:
    """Normalize reports to finite, deterministic JSON-native values."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (float, np.floating)):
        converted = float(value)
        if not math.isfinite(converted):
            raise RuntimeError("A2a result contains a non-finite number")
        return converted
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise RuntimeError("A2a result contains a non-string object key")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise RuntimeError(f"A2a result contains a non-JSON value: {type(value)!r}")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    normalized = _json_value(value)
    return (
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _identity_only(receipt: Mapping[str, Any]) -> dict[str, Any]:
    uri, generation, digest, byte_count = content_identity(receipt)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _catalog_source_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """Reproduce the source lock producer's digest (the list, no newline)."""
    raw = json.dumps(
        list(rows), sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def _expected_grid() -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (season, week, seed)
        for season in SEASONS
        for week in WEEKS
        for seed in range(len(BLOCKS))
    )


def _validate_artifact_grid(
    artifacts: object,
    *,
    expected_grid: Sequence[tuple[int, int, int]] | None = None,
    source_panels: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list):
        raise RuntimeError("A2a locked artifact receipts must be a list")
    grid = tuple(expected_grid if expected_grid is not None else _expected_grid())
    panels = tuple(source_panels if source_panels is not None else SOURCE_PANELS)
    if len(artifacts) != len(grid):
        raise RuntimeError("A2a locked artifact grid is incomplete")
    observed: list[tuple[int, int, int]] = []
    uris: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for row, key in zip(artifacts, grid, strict=True):
        if not isinstance(row, dict) or set(row) != ARTIFACT_FIELDS:
            raise RuntimeError("A2a locked artifact receipt schema differs")
        season, week, seed = key
        if type(row.get("season")) is not int or \
                type(row.get("week")) is not int or \
                type(row.get("seed")) is not int:
            raise RuntimeError("A2a locked artifact grid types differ")
        actual_key = (row["season"], row["week"], row["seed"])
        observed.append(actual_key)
        if actual_key != key or seed < 0 or seed >= len(panels):
            raise RuntimeError("A2a locked artifact order differs")
        if row.get("panel_run_id") != panels[seed]:
            raise RuntimeError("A2a locked artifact panel differs")
        uri = row.get("uri")
        digest = row.get("sha256")
        generation = str(row.get("generation", ""))
        if not isinstance(uri, str) or not uri.startswith("gs://") or \
                uri in uris or not generation.isdigit() or \
                not re.fullmatch(r"[0-9a-f]{64}", str(digest)) or \
                type(row.get("bytes")) is not int or row["bytes"] <= 0 or \
                type(row.get("candidate_rows")) is not int or \
                row["candidate_rows"] < 80 or \
                not isinstance(row.get("updated"), str):
            raise RuntimeError("A2a locked artifact identity differs")
        uris.add(uri)
        normalized.append(dict(row))
    if tuple(observed) != grid or len(set(observed)) != len(grid):
        raise RuntimeError("A2a locked artifact grid differs")
    return normalized


def _validate_catalog(
    catalog: object,
    *,
    expected_rows: int = CATALOG_ROWS,
    expected_eligible: int = ELIGIBLE_ROWS,
    expected_sha256: str = SOURCE_CATALOG_SHA256,
    expected_slates: set[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(catalog, list) or len(catalog) != expected_rows:
        raise RuntimeError("A2a locked catalog row count differs")
    rows: list[dict[str, Any]] = []
    keys: list[tuple[int, int, str]] = []
    eligible = 0
    for row in catalog:
        if not isinstance(row, dict) or set(row) != CATALOG_FIELDS:
            raise RuntimeError("A2a locked catalog schema differs")
        season, week = row.get("season"), row.get("week")
        player_id = row.get("player_id")
        position, team = row.get("position"), row.get("team")
        mean = row.get("mean_projection")
        if type(season) is not int or type(week) is not int or \
                not isinstance(player_id, str) or not player_id or \
                not isinstance(position, str) or not position or \
                not isinstance(team, str) or not team or \
                isinstance(mean, bool) or not isinstance(mean, (int, float)) or \
                not math.isfinite(float(mean)):
            raise RuntimeError("A2a locked catalog row differs")
        normalized = {
            "season": season,
            "week": week,
            "player_id": player_id,
            "position": position,
            "team": team,
            "mean_projection": float(mean),
        }
        rows.append(normalized)
        keys.append((season, week, player_id))
        if position in {"QB", "RB", "WR", "TE"} and float(mean) >= 4.0:
            eligible += 1
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise RuntimeError("A2a locked catalog keys are not canonical and unique")
    slates = {(season, week) for season, week, _ in keys}
    required_slates = expected_slates
    if required_slates is None:
        required_slates = {(s, w) for s in SEASONS for w in WEEKS}
    if slates != required_slates or eligible != expected_eligible:
        raise RuntimeError("A2a locked catalog population differs")
    if _catalog_source_digest(rows) != expected_sha256:
        raise RuntimeError("A2a locked catalog content differs")
    return rows


def _validate_source_lock(
    lock: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fixed = {
        "version": "production-law-dependence-source-lock-v1",
        "run_id": "20260817-production-law-dependence-source-lock-v1",
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "artifact_count": ARTIFACT_COUNT,
        "catalog_rows": CATALOG_ROWS,
        "candidate_union_rows": CATALOG_ROWS,
        "eligible_rows": ELIGIBLE_ROWS,
        "slates": len(SEASONS) * len(WEEKS),
        "catalog_sha256": SOURCE_CATALOG_SHA256,
        "source_panels": list(SOURCE_PANELS),
    }
    if set(lock) != SOURCE_LOCK_FIELDS or any(
        lock.get(key) != value for key, value in fixed.items()
    ):
        raise RuntimeError("A2a source lock contract differs")
    policy = lock.get("source_policy_receipt")
    if not isinstance(policy, dict) or policy.get("policy_id") != SOURCE_POLICY_ID or \
            policy.get("simulation_law") != {
                "dirichlet_k": None,
                "game_mode": "possession",
                "game_sim_usage_env": "",
                "td_ledger": False,
                "team_factors": True,
                "usage_allocation": "production-multinomial",
            }:
        raise RuntimeError("A2a source law differs")
    artifacts = _validate_artifact_grid(lock.get("artifact_receipts"))
    catalog = _validate_catalog(lock.get("catalog"))
    return artifacts, catalog


def _load_source_lock(
    gcs: storage.Client,
    *,
    uri: str,
    generation: str,
    digest: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if uri != SOURCE_LOCK_URI or generation != SOURCE_LOCK_GENERATION or \
            digest != SOURCE_LOCK_SHA256:
        raise RuntimeError("A2a source-lock argument identity differs")
    receipt, raw = live_object_receipt(gcs, uri)
    expected = {
        "uri": SOURCE_LOCK_URI,
        "generation": SOURCE_LOCK_GENERATION,
        "sha256": SOURCE_LOCK_SHA256,
        "bytes": SOURCE_LOCK_BYTES,
    }
    if not same_object(receipt, expected) or len(raw) != SOURCE_LOCK_BYTES or \
            sha256(raw).hexdigest() != SOURCE_LOCK_SHA256:
        raise RuntimeError("A2a source-lock content identity differs")
    lock = _strict_json(raw)
    artifacts, catalog = _validate_source_lock(lock)
    return _identity_only(receipt), artifacts, catalog


def _scope_grid(mode: str) -> tuple[tuple[int, int, int], ...]:
    if mode == "smoke":
        return SMOKE_GRID
    if mode == "full":
        return FULL_GRID
    raise ValueError("A2a mode must be exactly 'smoke' or 'full'")


def _select_artifacts(
    artifacts: Sequence[Mapping[str, Any]], mode: str,
) -> list[dict[str, Any]]:
    expected_full = _expected_grid()
    observed = tuple(
        (row.get("season"), row.get("week"), row.get("seed"))
        for row in artifacts
    )
    if observed != expected_full:
        raise RuntimeError("A2a source artifact grid changed before scope selection")
    wanted = set(_scope_grid(mode))
    selected = [dict(row) for row in artifacts if (
        row["season"], row["week"], row["seed"],
    ) in wanted]
    if tuple((r["season"], r["week"], r["seed"]) for r in selected) != \
            _scope_grid(mode):
        raise RuntimeError("A2a execution scope differs")
    return selected


def _catalog_by_slate(
    catalog: Sequence[Mapping[str, Any]],
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    result: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in catalog:
        result.setdefault(
            (int(row["season"]), int(row["week"])), [],
        ).append(dict(row))
    return result


def _download_player_worlds(
    gcs: storage.Client,
    locked: Mapping[str, Any],
) -> tuple[list[str], np.ndarray, dict[str, Any]]:
    receipt, raw = live_object_receipt(gcs, str(locked["uri"]))
    if not same_object(receipt, locked):
        raise RuntimeError("A2a artifact content identity differs")
    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            if set(archive.files) != ARTIFACT_MEMBERS:
                raise RuntimeError("A2a source artifact schema differs")
            player_ids_array = np.asarray(archive["player_ids"])
            draws = np.asarray(archive["player_draws"]).copy()
    except (OSError, ValueError) as exc:
        raise RuntimeError("A2a source artifact cannot be decoded") from exc
    if player_ids_array.ndim != 1:
        raise RuntimeError("A2a artifact player IDs differ")
    player_ids = player_ids_array.astype(str).tolist()
    if not player_ids or any(not value for value in player_ids) or \
            len(player_ids) != len(set(player_ids)) or draws.ndim != 2 or \
            draws.shape != (len(player_ids), WORLDS_PER_ARTIFACT) or \
            not np.isfinite(draws).all():
        raise RuntimeError("A2a artifact player worlds differ")
    return player_ids, draws, _identity_only(receipt)


def _catalog_rows_for_artifact(
    rows: Sequence[Mapping[str, Any]], player_ids: Sequence[str],
) -> list[dict[str, Any]]:
    by_id = {str(row["player_id"]): dict(row) for row in rows}
    if len(by_id) != len(rows) or not by_id or set(by_id) - set(player_ids):
        raise RuntimeError("A2a artifact/catalog player universe differs")
    # Preserve the frozen catalog order.  The artifact may contain additional
    # rows outside the candidate-union catalog; the science module proves that
    # every such unsupported row remains bit-exact.
    return [dict(row) for row in rows]


def _science_cell(
    catalog_rows: Sequence[Mapping[str, Any]],
    player_ids: Sequence[str],
    player_draws: np.ndarray,
) -> dict[str, Any]:
    """Thin adapter; the research module owns every scientific operation."""
    treatment, report = science.transform_and_measure_slate(
        catalog_rows=catalog_rows,
        player_ids=player_ids,
        control_draws=player_draws,
        expected_worlds=WORLDS_PER_ARTIFACT,
    )
    if not isinstance(treatment, np.ndarray) or treatment.shape != \
            player_draws.shape or not np.isfinite(treatment).all():
        raise RuntimeError("A2a science treatment array contract differs")
    if not isinstance(report, dict):
        raise RuntimeError("A2a science cell receipt must be an object")
    return report


def _science_aggregate(
    cells_by_block: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Thin adapter; aggregation and exact comparisons stay in science."""
    block_reports = {
        block: science.combine_reports(reports)
        for block, reports in cells_by_block.items()
    }
    gate = science.evaluate_mechanism_gate(block_reports)
    if not isinstance(gate, dict):
        raise RuntimeError("A2a science gate receipt must be an object")
    return {"block_reports": block_reports, "gate": gate}


def _licenses(*, historical_remeasurement: bool = False) -> dict[str, bool]:
    values = {field: False for field in LICENSE_FIELDS}
    values["historical_remeasurement_licensed"] = bool(
        historical_remeasurement
    )
    return values


def _full_disposition(gate: Mapping[str, Any]) -> tuple[str, dict[str, bool]]:
    if set(gate) != GATE_FIELDS:
        raise RuntimeError("A2a aggregate gate schema differs")
    mechanical = gate.get("mechanical_invariants_pass")
    directional = gate.get("directional_conditions_pass")
    passed = gate.get("passes")
    if not all(isinstance(value, bool) for value in (
        mechanical, directional, passed,
    )) or passed is not (mechanical and directional):
        raise RuntimeError("A2a aggregate gate contract differs")
    if mechanical is not True:
        expected = "a2a-scorefree-invalid", _licenses()
    elif directional is not True:
        expected = "a2a-scorefree-mechanism-fails", _licenses()
    else:
        expected = (
            "a2a-scorefree-mechanism-passes",
            _licenses(historical_remeasurement=True),
        )
    if gate.get("disposition") != expected[0] or \
            gate.get("licenses") != expected[1] or \
            not isinstance(gate.get("conditions"), Mapping) or \
            not isinstance(gate.get("aggregate"), Mapping) or \
            not isinstance(gate.get("block_directions"), Mapping):
        raise RuntimeError("A2a science gate disposition/license contract differs")
    return expected


def _upload_create_only(
    gcs: storage.Client, uri: str, payload: bytes,
) -> dict[str, Any]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("A2a output URI must name one GCS object")
    bucket_name, marker, object_name = uri[5:].partition("/")
    if not marker or not bucket_name or not object_name or \
            ".." in object_name.split("/"):
        raise ValueError("A2a output URI is invalid")
    blob = gcs.bucket(bucket_name).blob(object_name)
    blob.upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    receipt = {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "create_only": True,
    }
    content_identity(receipt)
    return receipt


def _expected_output_uri(mode: str) -> str:
    if mode == "smoke":
        return SMOKE_OUTPUT_URI
    if mode == "full":
        return FULL_OUTPUT_URI
    raise ValueError("A2a mode must be exactly 'smoke' or 'full'")


def run(
    *,
    mode: str,
    source_lock_uri: str,
    source_lock_generation: str,
    source_lock_sha256: str,
    output_uri: str,
) -> dict[str, Any]:
    if output_uri != _expected_output_uri(mode):
        raise RuntimeError("A2a output URI differs from the frozen mode")
    if tuple(science.REGISTERED_BLOCKS) != BLOCKS or \
            int(science.EXPECTED_WORLDS) != WORLDS_PER_ARTIFACT:
        raise RuntimeError("A2a science grid contract differs")
    if not PROTOCOL.is_file() or sha256(PROTOCOL.read_bytes()).hexdigest() != \
            PROTOCOL_SHA256:
        raise RuntimeError("A2a frozen protocol identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image):
        raise RuntimeError("A2a immutable code/image provenance is required")

    gcs = storage.Client(project=PROJECT)
    lock_receipt, all_artifacts, catalog = _load_source_lock(
        gcs,
        uri=source_lock_uri,
        generation=source_lock_generation,
        digest=source_lock_sha256,
    )
    selected = _select_artifacts(all_artifacts, mode)
    by_slate = _catalog_by_slate(catalog)
    cells_by_block: dict[str, list[dict[str, Any]]] = {
        block: [] for block in BLOCKS if mode == "full" or block == "R0"
    }
    artifact_reports: list[dict[str, Any]] = []
    source_artifacts: list[dict[str, Any]] = []
    slate_universes: dict[tuple[int, int], frozenset[str]] = {}

    for locked in selected:
        season = int(locked["season"])
        week = int(locked["week"])
        seed = int(locked["seed"])
        block = BLOCKS[seed]
        player_ids, draws, live_receipt = _download_player_worlds(gcs, locked)
        universe = frozenset(player_ids)
        slate = (season, week)
        prior = slate_universes.setdefault(slate, universe)
        if prior != universe:
            raise RuntimeError("A2a block player universes differ")
        slate_catalog = _catalog_rows_for_artifact(
            by_slate.get(slate, []), player_ids,
        )
        cell = _science_cell(slate_catalog, player_ids, draws)
        cell = _json_value(cell)
        if not isinstance(cell, dict):
            raise RuntimeError("A2a science cell receipt must be an object")
        # Round-trip the cell now so a late non-finite or unsupported type can
        # never poison a partially assembled full result.
        _canonical_json_bytes(cell)
        cells_by_block[block].append(cell)
        artifact_reports.append({
            "season": season,
            "week": week,
            "block": block,
            "report": cell,
        })
        source_artifacts.append({
            "season": season,
            "week": week,
            "block": block,
            "panel_run_id": locked["panel_run_id"],
            **live_receipt,
        })
        print("A2A_RANK_FACTOR_SPLIT_ARTIFACT_COMPLETE", season, week, block)

    scope = {
        "artifacts": len(selected),
        "slates": len({(row["season"], row["week"]) for row in selected}),
        "blocks": sorted(cells_by_block),
        "worlds_per_artifact": WORLDS_PER_ARTIFACT,
    }
    base: dict[str, Any] = {
        "version": (
            "a2a-rank-factor-split-scorefree-smoke-v2"
            if mode == "smoke"
            else "a2a-rank-factor-split-scorefree-result-v2"
        ),
        "run_id": RUN_ID,
        "mode": mode,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": code_sha,
        "analysis_image": image,
        "source_lock": lock_receipt,
        "source_catalog_sha256": SOURCE_CATALOG_SHA256,
        "scope": scope,
        "source_artifacts": source_artifacts,
        "artifact_reports": artifact_reports,
    }
    if mode == "smoke":
        cell = artifact_reports[0]["report"]
        mechanical = cell.get("mechanics")
        mechanics = (
            mechanical.get("passes") if isinstance(mechanical, dict) else None
        )
        if not isinstance(mechanics, bool):
            raise RuntimeError("A2a smoke mechanical gate contract differs")
        base.update({
            "disposition": (
                "a2a-scorefree-smoke-passes"
                if mechanics else "a2a-scorefree-invalid"
            ),
            **_licenses(),
        })
    else:
        aggregate = _json_value(_science_aggregate(cells_by_block))
        if not isinstance(aggregate, dict):
            raise RuntimeError("A2a aggregate receipt must be an object")
        gate = aggregate.get("gate")
        if not isinstance(gate, dict):
            raise RuntimeError("A2a aggregate gate receipt must be an object")
        disposition, licenses = _full_disposition(gate)
        base.update({
            "block_reports": aggregate["block_reports"],
            "gate": gate,
            "disposition": disposition,
            **licenses,
        })

    if set(LICENSE_FIELDS) - set(base) or any(
        not isinstance(base[field], bool) for field in LICENSE_FIELDS
    ):
        raise RuntimeError("A2a license schema differs")
    if mode != "full" or base["disposition"] != \
            "a2a-scorefree-mechanism-passes":
        if any(base[field] for field in LICENSE_FIELDS):
            raise RuntimeError("A2a non-passing result cannot carry a license")
    elif base["historical_remeasurement_licensed"] is not True or any(
        base[field] for field in LICENSE_FIELDS
        if field != "historical_remeasurement_licensed"
    ):
        raise RuntimeError("A2a passing result license set differs")

    raw = _canonical_json_bytes(base)
    # Exact repetition demonstrates deterministic serialization independent of
    # the create-once transport call.
    if raw != _canonical_json_bytes(base):
        raise RuntimeError("A2a result serialization is not deterministic")
    output = _upload_create_only(gcs, output_uri, raw)
    print("A2A_RANK_FACTOR_SPLIT_CENSUS_RESULT " + json.dumps({
        "mode": mode,
        "disposition": base["disposition"],
        "output": output,
    }, sort_keys=True))
    return {**base, "output": output}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--source-lock-uri", required=True)
    parser.add_argument("--source-lock-generation", required=True)
    parser.add_argument("--source-lock-sha256", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(
        mode=args.mode,
        source_lock_uri=args.source_lock_uri,
        source_lock_generation=args.source_lock_generation,
        source_lock_sha256=args.source_lock_sha256,
        output_uri=args.output_uri,
    )


if __name__ == "__main__":
    main()
