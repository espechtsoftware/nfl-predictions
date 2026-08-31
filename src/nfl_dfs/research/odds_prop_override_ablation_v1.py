"""Outcome-blind Odds API prop-override ablation contracts.

The control in this experiment is *not* ``BLEND_MODEL_WEIGHT=1.0``.  Both
cells preserve the same 45 percent model / 55 percent market blend.  The only
change is whether an eligible common-lock Odds API player-prop mean may
override the exact DraftKings PPG market fallback.

The current live ``_pm`` branch is not assumed to implement the on cell: it
replaces the whole market vector when aggregate prop coverage clears its
threshold, leaving missing prop rows to the blend helper's model-only NaN
fallback.  This cohort instead requires an explicit per-player
``prop if eligible else DK PPG`` market vector before applying 45/55, and an
outer adapter must not label the live branch as parity until that law is
demonstrated exactly.

The pure builders below provide three boundaries:

* an exact-body historical DraftKings PPG fallback authority gate;
* a projection support census with missing/stale/post-lock/fallback and
  marginal-rank turnover; and
* an outcome-free population/book influence trace once an outer generator
  supplies exact projected candidate and selected-book membership.

No function reads cloud storage, a warehouse, realized points, or a contest
result.  Returned objects are preregistration/support evidence only and make
no claim that the Odds API improves lineup scores.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import math
import re
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry


FALLBACK_AUTHORITY_SCHEMA: Final = "odds-ablation-dk-ppg-authority/v1"
PROP_AUTHORITY_SCHEMA: Final = "odds-ablation-prop-snapshot-authority/v1"
SUPPORT_CENSUS_SCHEMA: Final = "odds-prop-override-support-census/v1"
PANEL_SUPPORT_CENSUS_SCHEMA: Final = (
    "odds-prop-override-panel-support-census/v1"
)
INFLUENCE_TRACE_SCHEMA: Final = "odds-prop-override-influence-trace/v1"
CANDIDATE_POPULATION_SCHEMA: Final = (
    "odds-prop-override-candidate-population/v1"
)
SELECTION_WORLD_SCHEMA: Final = "odds-prop-override-selection-world/v1"
SELECTED_BOOK_SCHEMA: Final = "odds-prop-override-selected-book/v1"

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_OUTCOME_KEYS: Final = frozenset({
    "actual_points",
    "actual_score",
    "contest_finish",
    "contest_rank",
    "lineup_score",
    "payout",
    "realized_points",
    "realized_score",
    "winner",
    "winning_score",
})


class OddsPropOverrideAblationV1Error(ValueError):
    """The incremental Odds prop-override contract is invalid."""


def _fail(message: str) -> None:
    raise OddsPropOverrideAblationV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _number(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        _fail(f"{label} must be a finite number")
    return float(value)


def _optional_number(value: object, *, label: str) -> float | None:
    return None if value is None else _number(value, label=label)


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise OddsPropOverrideAblationV1Error(
            f"{label} is not a valid timestamp"
        ) from exc
    return value, parsed


def _reject_outcomes(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if normalized in _FORBIDDEN_OUTCOME_KEYS or (
                "realized" in normalized
                and normalized not in {"uses_realized_outcomes"}
            ) or "grade" in normalized:
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            if normalized == "outcome_columns_read" and item != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            _reject_outcomes(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_outcomes(item, label=f"{label}[{ordinal}]")


def _policy() -> dict[str, object]:
    return {
        "evidence_class": "outcome-blind-source-influence-only",
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "value_claim": "not_evaluated",
        **{field: False for field in registry.FALSE_AUTHORITY_FIELDS},
    }


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = registry.canonical_sha256(result)
    return result


def _validate_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    if not registry.is_sha256(retained):
        _fail(f"{label} self-hash is invalid")
    body = {key: item for key, item in value.items() if key != field}
    if registry.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _bind_body(
    value: object, identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = source.normalize_object_identity_v2(identity, label=label)
    raw = registry.canonical_json_bytes(value)
    if normalized["sha256"] != registry.canonical_sha256(value) or normalized[
        "bytes"
    ] != len(raw):
        _fail(f"{label} differs from its exact canonical body")
    return normalized


def _slate(value: object) -> dict[str, object]:
    item = _mapping(value, label="Odds slate")
    _exact_keys(item, {"slate_id", "season", "week"}, label="Odds slate")
    if (
        type(item["slate_id"]) is not str
        or not item["slate_id"]
        or type(item["season"]) is not int
        or item["season"] < 2000
        or type(item["week"]) is not int
        or not 1 <= item["week"] <= 18
    ):
        _fail("Odds slate values differ")
    return item


def build_dk_ppg_fallback_authority_v1(
    *,
    slate: Mapping[str, object],
    common_lock_time_utc: str,
    common_lock_identity: Mapping[str, object],
    source_snapshot_time_utc: str,
    source_snapshot_identity: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the exact projection of a historical DK-PPG fallback source.

    The returned body becomes authority only when an outer capture layer
    persists it and the support census exact-binds the supplied object
    identity.  Every player row must have a finite fallback; a partial
    historical snapshot is a NO-GO for the off cell.
    """
    normalized_slate = _slate(slate)
    lock, lock_dt = _timestamp(common_lock_time_utc, label="common lock")
    snapshot, snapshot_dt = _timestamp(
        source_snapshot_time_utc, label="DK-PPG source snapshot"
    )
    # The common-lock boundary is strict throughout this experiment.  A
    # snapshot stamped exactly at lock cannot establish that its contents were
    # observable before lock, so it is no more eligible than a later snapshot.
    if snapshot_dt >= lock_dt:
        _fail("DK-PPG source snapshot is not strictly before common lock")
    normalized_rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"DK-PPG row[{ordinal}]")
        _exact_keys(row, {"gsis_id", "dk_ppg"}, label=f"DK-PPG row[{ordinal}]")
        player_id = row["gsis_id"]
        if type(player_id) is not str or not player_id or player_id in seen:
            _fail("DK-PPG authority repeats or lacks a player identity")
        seen.add(player_id)
        normalized_rows.append({
            "gsis_id": player_id,
            "dk_ppg": _number(row["dk_ppg"], label="DK PPG"),
        })
    normalized_rows.sort(key=lambda row: str(row["gsis_id"]))
    if not normalized_rows:
        _fail("DK-PPG fallback authority has no player rows")
    body: dict[str, object] = {
        "schema_version": FALLBACK_AUTHORITY_SCHEMA,
        "slate": normalized_slate,
        "common_lock_time_utc": lock,
        "common_lock_identity": source.normalize_object_identity_v2(
            common_lock_identity, label="common-lock authority identity"
        ),
        "source_snapshot_time_utc": snapshot,
        "source_snapshot_identity": source.normalize_object_identity_v2(
            source_snapshot_identity, label="DK-PPG source snapshot identity"
        ),
        "provenance_class": "exact-point-in-time-draftkings-snapshot",
        "fallback_scope": "every-tested-player",
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "ordered_player_ids_sha256": registry.canonical_sha256([
            row["gsis_id"] for row in normalized_rows
        ]),
        "rows_sha256": registry.canonical_sha256(normalized_rows),
        **_policy(),
    }
    return _with_hash(body, field="fallback_authority_sha256")


def validate_dk_ppg_fallback_authority_v1(
    value: object,
    *,
    identity: Mapping[str, object] | None = None,
    expected_slate: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="DK-PPG fallback authority")
    _reject_outcomes(item, label="DK-PPG fallback authority")
    _validate_hash(
        item, field="fallback_authority_sha256", label="DK-PPG fallback authority"
    )
    rebuilt = build_dk_ppg_fallback_authority_v1(
        slate=_mapping(item.get("slate"), label="fallback slate"),
        common_lock_time_utc=str(item.get("common_lock_time_utc")),
        common_lock_identity=_mapping(
            item.get("common_lock_identity"), label="fallback common-lock identity"
        ),
        source_snapshot_time_utc=str(item.get("source_snapshot_time_utc")),
        source_snapshot_identity=_mapping(
            item.get("source_snapshot_identity"), label="fallback source snapshot"
        ),
        rows=[
            _mapping(row, label="fallback row")
            for row in _sequence(item.get("rows"), label="fallback rows")
        ],
    )
    if item != rebuilt:
        _fail("DK-PPG fallback authority canonical replay differs")
    if expected_slate is not None and rebuilt["slate"] != _slate(expected_slate):
        _fail("DK-PPG fallback authority has another slate")
    if identity is not None:
        _bind_body(rebuilt, identity, label="DK-PPG fallback authority identity")
    return rebuilt


def build_prop_snapshot_authority_v1(
    *,
    slate: Mapping[str, object],
    common_lock_time_utc: str,
    common_lock_identity: Mapping[str, object],
    source_snapshot_identity: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build a positive-boundary projection of Odds prop player means."""
    normalized_slate = _slate(slate)
    lock, _ = _timestamp(common_lock_time_utc, label="common lock")
    normalized_rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"prop row[{ordinal}]")
        _exact_keys(
            row,
            {"gsis_id", "prop_market_points", "latest_snapshot_time_utc"},
            label=f"prop row[{ordinal}]",
        )
        player_id = row["gsis_id"]
        if type(player_id) is not str or not player_id or player_id in seen:
            _fail("prop authority repeats or lacks a player identity")
        seen.add(player_id)
        timestamp, _ = _timestamp(
            row["latest_snapshot_time_utc"], label="prop latest snapshot"
        )
        normalized_rows.append({
            "gsis_id": player_id,
            "prop_market_points": _number(
                row["prop_market_points"], label="prop market points"
            ),
            "latest_snapshot_time_utc": timestamp,
        })
    normalized_rows.sort(key=lambda row: str(row["gsis_id"]))
    body: dict[str, object] = {
        "schema_version": PROP_AUTHORITY_SCHEMA,
        "slate": normalized_slate,
        "common_lock_time_utc": lock,
        "common_lock_identity": source.normalize_object_identity_v2(
            common_lock_identity, label="common-lock authority identity"
        ),
        "source_snapshot_identity": source.normalize_object_identity_v2(
            source_snapshot_identity, label="Odds source snapshot identity"
        ),
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "ordered_player_ids_sha256": registry.canonical_sha256([
            row["gsis_id"] for row in normalized_rows
        ]),
        "rows_sha256": registry.canonical_sha256(normalized_rows),
        **_policy(),
    }
    return _with_hash(body, field="prop_authority_sha256")


def validate_prop_snapshot_authority_v1(
    value: object,
    *,
    identity: Mapping[str, object] | None = None,
    expected_slate: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="prop snapshot authority")
    _reject_outcomes(item, label="prop snapshot authority")
    _validate_hash(item, field="prop_authority_sha256", label="prop authority")
    rebuilt = build_prop_snapshot_authority_v1(
        slate=_mapping(item.get("slate"), label="prop slate"),
        common_lock_time_utc=str(item.get("common_lock_time_utc")),
        common_lock_identity=_mapping(
            item.get("common_lock_identity"), label="prop common-lock identity"
        ),
        source_snapshot_identity=_mapping(
            item.get("source_snapshot_identity"), label="prop source snapshot"
        ),
        rows=[
            _mapping(row, label="prop row")
            for row in _sequence(item.get("rows"), label="prop rows")
        ],
    )
    if item != rebuilt:
        _fail("prop snapshot authority canonical replay differs")
    if expected_slate is not None and rebuilt["slate"] != _slate(expected_slate):
        _fail("prop snapshot authority has another slate")
    if identity is not None:
        _bind_body(rebuilt, identity, label="prop snapshot authority identity")
    return rebuilt


def _rank_by_mean(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda row: (-float(row["blended_mean"]), str(row["gsis_id"])),
    )
    return {str(row["gsis_id"]): ordinal for ordinal, row in enumerate(ordered)}


def build_odds_prop_override_support_census_v1(
    *,
    slate: Mapping[str, object],
    model_rows: Sequence[Mapping[str, object]],
    fallback_authority: Mapping[str, object],
    fallback_authority_identity: Mapping[str, object],
    prop_authority: Mapping[str, object],
    prop_authority_identity: Mapping[str, object],
) -> dict[str, object]:
    """Run both 45/55 projection cells and report score-free influence."""
    registry.validate_paid_source_ablation_registry_v1(
        registry.frozen_paid_source_ablation_registry_v1()
    )
    normalized_slate = _slate(slate)
    fallback = validate_dk_ppg_fallback_authority_v1(
        fallback_authority,
        identity=fallback_authority_identity,
        expected_slate=normalized_slate,
    )
    props = validate_prop_snapshot_authority_v1(
        prop_authority,
        identity=prop_authority_identity,
        expected_slate=normalized_slate,
    )
    if (
        fallback["common_lock_time_utc"] != props["common_lock_time_utc"]
        or fallback["common_lock_identity"] != props["common_lock_identity"]
    ):
        _fail("fallback and prop authorities use different common locks")
    _, lock_dt = _timestamp(
        fallback["common_lock_time_utc"], label="common lock"
    )
    fallback_by_id = {
        str(row["gsis_id"]): float(row["dk_ppg"])
        for row in fallback["rows"]
    }
    prop_by_id = {str(row["gsis_id"]): dict(row) for row in props["rows"]}
    models: list[dict[str, object]] = []
    seen: set[str] = set()
    for ordinal, raw in enumerate(model_rows):
        row = _mapping(raw, label=f"model row[{ordinal}]")
        _exact_keys(row, {"gsis_id", "model_mean"}, label=f"model row[{ordinal}]")
        player_id = row["gsis_id"]
        if (
            type(player_id) is not str
            or not player_id
            or player_id in seen
            or player_id not in fallback_by_id
        ):
            _fail("model rows and exact DK-PPG fallback universe differ")
        seen.add(player_id)
        models.append({
            "gsis_id": player_id,
            "model_mean": _number(row["model_mean"], label="model mean"),
        })
    models.sort(key=lambda row: str(row["gsis_id"]))
    if set(fallback_by_id) != seen:
        _fail("DK-PPG fallback authority does not exactly cover model players")

    cells: list[dict[str, object]] = []
    status_by_player: dict[str, str] = {}
    for player_id in sorted(seen):
        prop = prop_by_id.get(player_id)
        if prop is None:
            status_by_player[player_id] = "missing"
            continue
        _, snapshot_dt = _timestamp(
            prop["latest_snapshot_time_utc"], label="prop snapshot"
        )
        age_seconds = int((lock_dt - snapshot_dt).total_seconds())
        # Production's point-in-time boundary is strict (< common lock), so a
        # row stamped exactly at lock is excluded with later observations.
        if age_seconds <= 0:
            status_by_player[player_id] = "post_lock_excluded"
        elif age_seconds > registry.ODDS_STALE_REPORTING_AGE_SECONDS:
            status_by_player[player_id] = "retained_stale"
        else:
            status_by_player[player_id] = "retained_fresh"
    input_prop_ids_outside_model = sorted(set(prop_by_id) - seen)

    for cell_id in registry.ODDS_CELL_ORDER:
        cell = registry.odds_cell_v1(cell_id)
        enabled = cell["prop_override_enabled"] is True
        rows: list[dict[str, object]] = []
        counts = {
            "model_player_count": len(models),
            "input_prop_player_count": len(prop_by_id),
            "retained_prop_player_count": 0,
            "excluded_prop_player_count": 0,
            "missing_prop_player_count": 0,
            "stale_prop_player_count": 0,
            "post_lock_prop_player_count": 0,
            "fallback_player_count": 0,
            "physically_excluded_by_control_count": 0,
            "prop_players_outside_model_count": len(input_prop_ids_outside_model),
        }
        for model in models:
            player_id = str(model["gsis_id"])
            status = status_by_player[player_id]
            if status == "missing":
                counts["missing_prop_player_count"] += 1
            elif status == "retained_stale":
                counts["stale_prop_player_count"] += 1
                if enabled:
                    counts["retained_prop_player_count"] += 1
            elif status == "post_lock_excluded":
                counts["post_lock_prop_player_count"] += 1
            elif status == "retained_fresh" and enabled:
                counts["retained_prop_player_count"] += 1
            use_prop = enabled and status in {"retained_fresh", "retained_stale"}
            if player_id in prop_by_id and not use_prop:
                counts["excluded_prop_player_count"] += 1
            market = (
                float(prop_by_id[player_id]["prop_market_points"])
                if use_prop
                else fallback_by_id[player_id]
            )
            if not use_prop:
                counts["fallback_player_count"] += 1
            blended = (
                registry.MODEL_WEIGHT * float(model["model_mean"])
                + registry.MARKET_WEIGHT * market
            )
            rows.append({
                "gsis_id": player_id,
                "model_mean": float(model["model_mean"]),
                "market_mean": market,
                "market_source": "odds-api-prop" if use_prop else "dk-ppg-fallback",
                "prop_status": status,
                "blended_mean": blended,
                "world_row_shift": blended - float(model["model_mean"]),
            })
        counts["excluded_prop_player_count"] += len(
            input_prop_ids_outside_model
        )
        if not enabled:
            counts["physically_excluded_by_control_count"] = len(prop_by_id)
        ranks = _rank_by_mean(rows)
        for row in rows:
            row["blended_mean_rank"] = ranks[str(row["gsis_id"])]
        cells.append({
            "cell": cell,
            "source_state_counts": counts,
            "rows": rows,
            "row_count": len(rows),
            "rows_sha256": registry.canonical_sha256(rows),
            "changed_world_row_law": "shift-marginal-mean-preserve-centered-shape",
            "changed_world_row_count": sum(
                float(row["world_row_shift"]) != 0.0 for row in rows
            ),
        })

    on_rows = {row["gsis_id"]: row for row in cells[0]["rows"]}
    off_rows = {row["gsis_id"]: row for row in cells[1]["rows"]}
    changed = [
        player_id for player_id in sorted(on_rows)
        if on_rows[player_id]["blended_mean"] != off_rows[player_id]["blended_mean"]
    ]
    rank_changed = [
        player_id for player_id in sorted(on_rows)
        if on_rows[player_id]["blended_mean_rank"]
        != off_rows[player_id]["blended_mean_rank"]
    ]
    body: dict[str, object] = {
        "schema_version": SUPPORT_CENSUS_SCHEMA,
        "experiment_id": registry.ODDS_EXPERIMENT_ID,
        "slate": normalized_slate,
        "common_lock_time_utc": fallback["common_lock_time_utc"],
        "common_lock_identity": fallback["common_lock_identity"],
        "registry_sha256": registry.frozen_paid_source_ablation_registry_v1()[
            "registry_sha256"
        ],
        "fallback_authority_identity": source.normalize_object_identity_v2(
            fallback_authority_identity, label="fallback authority identity"
        ),
        "fallback_authority_body": fallback,
        "prop_authority_identity": source.normalize_object_identity_v2(
            prop_authority_identity, label="prop authority identity"
        ),
        "prop_authority_body": props,
        "historical_dk_ppg_fallback_authority_gate_passed": True,
        "model_weight": registry.MODEL_WEIGHT,
        "market_weight": registry.MARKET_WEIGHT,
        "blend_model_weight_one_rejected_as_control": True,
        "cells": cells,
        "cell_manifest_sha256": registry.canonical_sha256(cells),
        "input_prop_player_ids_outside_model": input_prop_ids_outside_model,
        "changed_player_mean_count": len(changed),
        "changed_player_ids_sha256": registry.canonical_sha256(changed),
        "changed_world_row_count_on_vs_off": len(changed),
        "world_row_change_law": (
            "same-centered-shape-shifted-to-cell-specific-blended-mean"
        ),
        "changed_player_rank_count": len(rank_changed),
        "changed_player_rank_ids_sha256": registry.canonical_sha256(rank_changed),
        "marginal_turnover": {
            "mean_changed_player_count": len(changed),
            "rank_changed_player_count": len(rank_changed),
            "maximum_absolute_rank_change": max(
                (
                    abs(
                        int(on_rows[player_id]["blended_mean_rank"])
                        - int(off_rows[player_id]["blended_mean_rank"])
                    )
                    for player_id in on_rows
                ),
                default=0,
            ),
        },
        "historical_execution_status": "support-gate-passed",
        **_policy(),
    }
    return _with_hash(body, field="support_census_sha256")


def validate_odds_prop_override_support_census_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="Odds support census")
    _reject_outcomes(item, label="Odds support census")
    _validate_hash(item, field="support_census_sha256", label="Odds support census")
    _exact_keys(
        item,
        set(_policy()) | {
            "schema_version",
            "experiment_id",
            "slate",
            "common_lock_time_utc",
            "common_lock_identity",
            "registry_sha256",
            "fallback_authority_identity",
            "fallback_authority_body",
            "prop_authority_identity",
            "prop_authority_body",
            "historical_dk_ppg_fallback_authority_gate_passed",
            "model_weight",
            "market_weight",
            "blend_model_weight_one_rejected_as_control",
            "cells",
            "cell_manifest_sha256",
            "input_prop_player_ids_outside_model",
            "changed_player_mean_count",
            "changed_player_ids_sha256",
            "changed_world_row_count_on_vs_off",
            "world_row_change_law",
            "changed_player_rank_count",
            "changed_player_rank_ids_sha256",
            "marginal_turnover",
            "historical_execution_status",
            "support_census_sha256",
        },
        label="Odds support census",
    )
    if (
        item.get("schema_version") != SUPPORT_CENSUS_SCHEMA
        or item.get("experiment_id") != registry.ODDS_EXPERIMENT_ID
        or item.get("registry_sha256")
        != registry.frozen_paid_source_ablation_registry_v1()["registry_sha256"]
        or item.get("model_weight") != registry.MODEL_WEIGHT
        or item.get("market_weight") != registry.MARKET_WEIGHT
        or item.get("blend_model_weight_one_rejected_as_control") is not True
        or item.get("historical_dk_ppg_fallback_authority_gate_passed") is not True
        or item.get("historical_execution_status") != "support-gate-passed"
        or item.get("world_row_change_law")
        != "same-centered-shape-shifted-to-cell-specific-blended-mean"
        or item.get("value_claim") != "not_evaluated"
        or item.get("source_value_established") is not False
    ):
        _fail("Odds support census policy differs")
    _timestamp(item.get("common_lock_time_utc"), label="Odds common lock")
    cells = _sequence(item.get("cells"), label="Odds support cells")
    if len(cells) != len(registry.ODDS_CELL_ORDER):
        _fail("Odds support census requires exactly two cells")
    registry.validate_cell_order_v1(
        [_mapping(cell, label="Odds cell")["cell"] for cell in cells],
        experiment="odds",
    )
    if item.get("cell_manifest_sha256") != registry.canonical_sha256(cells):
        _fail("Odds support census cell manifest differs")
    on = _mapping(cells[0], label="Odds on cell")
    off = _mapping(cells[1], label="Odds off cell")
    outside_ids = _sequence(
        item.get("input_prop_player_ids_outside_model"),
        label="Odds prop IDs outside model",
    )
    if (
        any(type(value) is not str or not value for value in outside_ids)
        or outside_ids != sorted(set(outside_ids))
    ):
        _fail("Odds prop IDs outside model are not unique and ordered")

    def validate_cell(
        cell: Mapping[str, object], *, enabled: bool, label: str,
    ) -> list[dict[str, object]]:
        _exact_keys(cell, {
            "cell",
            "source_state_counts",
            "rows",
            "row_count",
            "rows_sha256",
            "changed_world_row_law",
            "changed_world_row_count",
        }, label=label)
        row_values = [
            _mapping(row, label=f"{label} row")
            for row in _sequence(cell.get("rows"), label=f"{label} rows")
        ]
        if (
            cell.get("row_count") != len(row_values)
            or cell.get("rows_sha256") != registry.canonical_sha256(row_values)
            or cell.get("changed_world_row_law")
            != "shift-marginal-mean-preserve-centered-shape"
        ):
            _fail(f"{label} row manifest differs")
        ids = [row.get("gsis_id") for row in row_values]
        if (
            any(type(player_id) is not str or not player_id for player_id in ids)
            or ids != sorted(set(ids))
            or set(ids) & set(outside_ids)
        ):
            _fail(f"{label} player universe differs")
        valid_statuses = {
            "missing",
            "post_lock_excluded",
            "retained_fresh",
            "retained_stale",
        }
        for row in row_values:
            _exact_keys(row, {
                "gsis_id",
                "model_mean",
                "market_mean",
                "market_source",
                "prop_status",
                "blended_mean",
                "world_row_shift",
                "blended_mean_rank",
            }, label=f"{label} player row")
            model_mean = _number(row["model_mean"], label="model mean")
            market_mean = _number(row["market_mean"], label="market mean")
            blended_mean = _number(row["blended_mean"], label="blended mean")
            shift = _number(row["world_row_shift"], label="world row shift")
            status = row["prop_status"]
            market_source = row["market_source"]
            if status not in valid_statuses or market_source not in {
                "odds-api-prop",
                "dk-ppg-fallback",
            }:
                _fail(f"{label} source state differs")
            use_prop = enabled and status in {"retained_fresh", "retained_stale"}
            if (market_source == "odds-api-prop") is not use_prop:
                _fail(f"{label} did not apply the frozen prop override state")
            expected_blend = (
                registry.MODEL_WEIGHT * model_mean
                + registry.MARKET_WEIGHT * market_mean
            )
            if not math.isclose(blended_mean, expected_blend, abs_tol=1e-12):
                _fail(f"{label} did not preserve the 45/55 blend")
            if not math.isclose(shift, blended_mean - model_mean, abs_tol=1e-12):
                _fail(f"{label} world-row shift differs")
            _integer(row["blended_mean_rank"], label="blended mean rank")
        expected_ranks = _rank_by_mean(row_values)
        if any(
            row["blended_mean_rank"] != expected_ranks[str(row["gsis_id"])]
            for row in row_values
        ):
            _fail(f"{label} blended-mean ranks differ")
        expected_counts = {
            "model_player_count": len(row_values),
            "input_prop_player_count": (
                sum(row["prop_status"] != "missing" for row in row_values)
                + len(outside_ids)
            ),
            "retained_prop_player_count": sum(
                row["market_source"] == "odds-api-prop" for row in row_values
            ),
            "excluded_prop_player_count": sum(
                row["prop_status"] != "missing"
                and row["market_source"] == "dk-ppg-fallback"
                for row in row_values
            ) + len(outside_ids),
            "missing_prop_player_count": sum(
                row["prop_status"] == "missing" for row in row_values
            ),
            "stale_prop_player_count": sum(
                row["prop_status"] == "retained_stale" for row in row_values
            ),
            "post_lock_prop_player_count": sum(
                row["prop_status"] == "post_lock_excluded" for row in row_values
            ),
            "fallback_player_count": sum(
                row["market_source"] == "dk-ppg-fallback" for row in row_values
            ),
            "physically_excluded_by_control_count": (
                0
                if enabled
                else (
                    sum(
                        row["prop_status"] != "missing" for row in row_values
                    )
                    + len(outside_ids)
                )
            ),
            "prop_players_outside_model_count": len(outside_ids),
        }
        if cell.get("source_state_counts") != expected_counts:
            _fail(f"{label} source-state counts differ")
        if cell.get("changed_world_row_count") != sum(
            float(row["world_row_shift"]) != 0.0 for row in row_values
        ):
            _fail(f"{label} changed world-row count differs")
        return row_values

    on_rows = validate_cell(on, enabled=True, label="Odds on cell")
    off_rows = validate_cell(off, enabled=False, label="Odds off cell")
    if (
        [row["gsis_id"] for row in on_rows]
        != [row["gsis_id"] for row in off_rows]
        or any(
            on_row["model_mean"] != off_row["model_mean"]
            or on_row["prop_status"] != off_row["prop_status"]
            for on_row, off_row in zip(on_rows, off_rows, strict=True)
        )
    ):
        _fail("Odds support census cells do not preserve the exact universe")
    changed = [
        str(on_row["gsis_id"])
        for on_row, off_row in zip(on_rows, off_rows, strict=True)
        if on_row["blended_mean"] != off_row["blended_mean"]
    ]
    rank_changed = [
        str(on_row["gsis_id"])
        for on_row, off_row in zip(on_rows, off_rows, strict=True)
        if on_row["blended_mean_rank"] != off_row["blended_mean_rank"]
    ]
    expected_marginal = {
        "mean_changed_player_count": len(changed),
        "rank_changed_player_count": len(rank_changed),
        "maximum_absolute_rank_change": max(
            (
                abs(
                    int(on_row["blended_mean_rank"])
                    - int(off_row["blended_mean_rank"])
                )
                for on_row, off_row in zip(on_rows, off_rows, strict=True)
            ),
            default=0,
        ),
    }
    if (
        item.get("changed_player_mean_count") != len(changed)
        or item.get("changed_world_row_count_on_vs_off") != len(changed)
        or item.get("changed_player_ids_sha256")
        != registry.canonical_sha256(changed)
        or item.get("changed_player_rank_count") != len(rank_changed)
        or item.get("changed_player_rank_ids_sha256")
        != registry.canonical_sha256(rank_changed)
        or item.get("marginal_turnover") != expected_marginal
    ):
        _fail("Odds support census marginal turnover differs")
    source.normalize_object_identity_v2(
        _mapping(item.get("common_lock_identity"), label="Odds common lock"),
        label="Odds common-lock identity",
    )
    source.normalize_object_identity_v2(
        _mapping(
            item.get("fallback_authority_identity"),
            label="Odds fallback authority",
        ),
        label="Odds fallback authority identity",
    )
    source.normalize_object_identity_v2(
        _mapping(item.get("prop_authority_identity"), label="Odds prop authority"),
        label="Odds prop authority identity",
    )
    fallback = validate_dk_ppg_fallback_authority_v1(
        _mapping(
            item.get("fallback_authority_body"),
            label="Odds fallback authority body",
        ),
        identity=_mapping(
            item.get("fallback_authority_identity"),
            label="Odds fallback authority identity",
        ),
        expected_slate=_mapping(item.get("slate"), label="Odds slate"),
    )
    props = validate_prop_snapshot_authority_v1(
        _mapping(
            item.get("prop_authority_body"),
            label="Odds prop authority body",
        ),
        identity=_mapping(
            item.get("prop_authority_identity"),
            label="Odds prop authority identity",
        ),
        expected_slate=_mapping(item.get("slate"), label="Odds slate"),
    )
    rebuilt = build_odds_prop_override_support_census_v1(
        slate=_mapping(item.get("slate"), label="Odds slate"),
        model_rows=[{
            "gsis_id": row["gsis_id"],
            "model_mean": row["model_mean"],
        } for row in on_rows],
        fallback_authority=fallback,
        fallback_authority_identity=_mapping(
            item.get("fallback_authority_identity"),
            label="Odds fallback authority identity",
        ),
        prop_authority=props,
        prop_authority_identity=_mapping(
            item.get("prop_authority_identity"),
            label="Odds prop authority identity",
        ),
    )
    if rebuilt != item:
        _fail("Odds support census canonical replay differs")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("Odds support census claims downstream authority")
    return item


def build_odds_prop_override_panel_support_census_v1(
    slate_censuses: Sequence[Mapping[str, object]],
    *,
    preregistered_slates: Sequence[Mapping[str, object]],
    preregistered_panel_identity: Mapping[str, object],
) -> dict[str, object]:
    """Aggregate every slate in one exact predeclared historical panel.

    The panel may have any predeclared length, but its exact identity and
    ordered slate list are inputs.  Historical execution cannot silently
    omit a preregistered slate whose DK-PPG authority failed.
    """
    values = [
        validate_odds_prop_override_support_census_v1(value)
        for value in slate_censuses
    ]
    if not values:
        _fail("Odds panel support census requires at least one tested slate")
    expected_slates = [_slate(value) for value in preregistered_slates]
    if not expected_slates:
        _fail("Odds preregistered panel requires at least one slate")
    panel_identity = _bind_body(
        expected_slates,
        preregistered_panel_identity,
        label="Odds preregistered panel identity",
    )
    keys = [
        (
            int(value["slate"]["season"]),
            int(value["slate"]["week"]),
            str(value["slate"]["slate_id"]),
        )
        for value in values
    ]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        _fail("Odds panel support censuses must be unique and slate-ordered")
    if [value["slate"] for value in values] != expected_slates:
        _fail("Odds support censuses do not cover the exact preregistered panel")
    cell_rows = []
    for cell_id in registry.ODDS_CELL_ORDER:
        cells = [
            next(
                cell
                for cell in value["cells"]
                if cell["cell"]["cell_id"] == cell_id
            )
            for value in values
        ]
        count_fields = sorted(cells[0]["source_state_counts"])
        cell_rows.append({
            "cell_id": cell_id,
            "slate_count": len(cells),
            "source_state_count_totals": {
                field: sum(
                    int(cell["source_state_counts"][field]) for cell in cells
                )
                for field in count_fields
            },
        })
    body: dict[str, object] = {
        "schema_version": PANEL_SUPPORT_CENSUS_SCHEMA,
        "experiment_id": registry.ODDS_EXPERIMENT_ID,
        "slate_count": len(values),
        "slates": [value["slate"] for value in values],
        "preregistered_panel_identity": panel_identity,
        "preregistered_slate_manifest_sha256": registry.canonical_sha256(
            expected_slates
        ),
        "slate_support_census_sha256s": [
            value["support_census_sha256"] for value in values
        ],
        "slate_support_manifest_sha256": registry.canonical_sha256([
            value["support_census_sha256"] for value in values
        ]),
        "cells": cell_rows,
        "cell_manifest_sha256": registry.canonical_sha256(cell_rows),
        "historical_dk_ppg_fallback_authority_gate_passed_all_slates": True,
        "historical_execution_status": "support-gate-passed",
        "prospective_fallback_if_any_historical_slate_missing": True,
        **_policy(),
    }
    return _with_hash(body, field="panel_support_census_sha256")


def validate_odds_prop_override_panel_support_census_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="Odds panel support census")
    _reject_outcomes(item, label="Odds panel support census")
    _validate_hash(
        item,
        field="panel_support_census_sha256",
        label="Odds panel support census",
    )
    _exact_keys(
        item,
        set(_policy()) | {
            "schema_version",
            "experiment_id",
            "slate_count",
            "slates",
            "preregistered_panel_identity",
            "preregistered_slate_manifest_sha256",
            "slate_support_census_sha256s",
            "slate_support_manifest_sha256",
            "cells",
            "cell_manifest_sha256",
            "historical_dk_ppg_fallback_authority_gate_passed_all_slates",
            "historical_execution_status",
            "prospective_fallback_if_any_historical_slate_missing",
            "panel_support_census_sha256",
        },
        label="Odds panel support census",
    )
    cells = [
        _mapping(cell, label="Odds panel support cell")
        for cell in _sequence(item.get("cells"), label="Odds panel support cells")
    ]
    slates = _sequence(item.get("slates"), label="Odds panel slates")
    slate_hashes = _sequence(
        item.get("slate_support_census_sha256s"),
        label="Odds panel support hashes",
    )
    if (
        item.get("schema_version") != PANEL_SUPPORT_CENSUS_SCHEMA
        or item.get("experiment_id") != registry.ODDS_EXPERIMENT_ID
        or item.get("slate_count") != len(slates)
        or len(slates) == 0
        or len(slate_hashes) != len(slates)
        or any(not registry.is_sha256(value) for value in slate_hashes)
        or item.get("slate_support_manifest_sha256")
        != registry.canonical_sha256(slate_hashes)
        or [cell.get("cell_id") for cell in cells]
        != list(registry.ODDS_CELL_ORDER)
        or any(cell.get("slate_count") != len(slates) for cell in cells)
        or item.get("cell_manifest_sha256")
        != registry.canonical_sha256(cells)
        or item.get(
            "historical_dk_ppg_fallback_authority_gate_passed_all_slates"
        ) is not True
        or item.get("historical_execution_status") != "support-gate-passed"
        or item.get("prospective_fallback_if_any_historical_slate_missing")
        is not True
        or item.get("value_claim") != "not_evaluated"
        or item.get("source_value_established") is not False
    ):
        _fail("Odds panel support census policy differs")
    normalized_slates = [_slate(slate) for slate in slates]
    if normalized_slates != slates:
        _fail("Odds panel support slates differ from canonical projections")
    _bind_body(
        normalized_slates,
        _mapping(
            item.get("preregistered_panel_identity"),
            label="Odds preregistered panel identity",
        ),
        label="Odds preregistered panel identity",
    )
    if item.get("preregistered_slate_manifest_sha256") != (
        registry.canonical_sha256(normalized_slates)
    ):
        _fail("Odds preregistered slate manifest differs")
    keys = [
        (int(slate["season"]), int(slate["week"]), str(slate["slate_id"]))
        for slate in normalized_slates
    ]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        _fail("Odds panel support slates are not unique and ordered")
    count_fields: set[str] | None = None
    for cell in cells:
        _exact_keys(
            cell,
            {"cell_id", "slate_count", "source_state_count_totals"},
            label="Odds panel support cell",
        )
        counts = _mapping(
            cell.get("source_state_count_totals"),
            label="Odds panel source-state totals",
        )
        if count_fields is None:
            count_fields = set(counts)
        if set(counts) != count_fields:
            _fail("Odds panel source-state total fields differ")
        for field, count in counts.items():
            _integer(count, label=f"Odds panel {field}")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("Odds panel support census claims downstream authority")
    return item


def _membership_metrics(
    left: Sequence[str], right: Sequence[str], *, ordered: bool,
) -> dict[str, object]:
    left_ids = [str(value) for value in left]
    right_ids = [str(value) for value in right]
    if len(left_ids) != len(set(left_ids)) or len(right_ids) != len(set(right_ids)):
        _fail("population influence membership repeats an ID")
    left_set, right_set = set(left_ids), set(right_ids)
    union = left_set | right_set
    shared = left_set & right_set
    right_rank = {lineup_id: rank for rank, lineup_id in enumerate(right_ids)}
    displacement = [
        abs(rank - right_rank[lineup_id])
        for rank, lineup_id in enumerate(left_ids)
        if lineup_id in right_rank
    ]
    return {
        "left_count": len(left_ids),
        "right_count": len(right_ids),
        "shared_count": len(shared),
        "jaccard": len(shared) / len(union) if union else 1.0,
        "membership_turnover_count": len(left_set ^ right_set),
        "exact_membership_equal": left_set == right_set,
        "exact_order_equal": left_ids == right_ids if ordered else None,
        "shared_mean_absolute_rank_displacement": (
            sum(displacement) / len(displacement) if displacement else None
        ),
    }


def _census_projection_rows_sha256(
    census: Mapping[str, object], cell_id: str,
) -> str:
    for raw in census["cells"]:
        cell = _mapping(raw, label="Odds support cell")
        state = _mapping(cell.get("cell"), label="Odds support cell state")
        if state.get("cell_id") == cell_id:
            retained = cell.get("rows_sha256")
            if not registry.is_sha256(retained):
                _fail("Odds support cell lacks projection-row authority")
            return str(retained)
    _fail(f"Odds support census lacks cell {cell_id!r}")


def _normalize_candidate_population_body(
    value: object,
    *,
    census: Mapping[str, object],
    population_cell_id: str,
) -> tuple[dict[str, object], list[str]]:
    body = _mapping(value, label="Odds candidate population body")
    _reject_outcomes(body, label="Odds candidate population body")
    _exact_keys(
        body,
        {
            "schema_version",
            "slate",
            "population_cell_id",
            "support_census_sha256",
            "generation_projection_rows_sha256",
            "candidate_rows",
            "solve_failure_count",
            "retry_count",
            "outcome_columns_read",
            "uses_realized_outcomes",
        },
        label="Odds candidate population body",
    )
    rows = [
        _mapping(row, label="Odds candidate population row")
        for row in _sequence(
            body.get("candidate_rows"), label="Odds candidate population rows"
        )
    ]
    candidate_ids: list[str] = []
    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        _exact_keys(
            row,
            {"candidate_id", "player_ids"},
            label="Odds candidate population row",
        )
        candidate_id = row.get("candidate_id")
        player_ids = _sequence(row.get("player_ids"), label="Odds lineup player IDs")
        if (
            type(candidate_id) is not str
            or not candidate_id
            or len(player_ids) != 9
            or any(type(player_id) is not str or not player_id for player_id in player_ids)
            or len(player_ids) != len(set(player_ids))
        ):
            _fail("Odds candidate population row differs")
        candidate_ids.append(candidate_id)
        normalized_rows.append({
            "candidate_id": candidate_id,
            "player_ids": list(player_ids),
        })
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        _fail("Odds candidate population membership differs")
    normalized = {
        "schema_version": CANDIDATE_POPULATION_SCHEMA,
        "slate": census["slate"],
        "population_cell_id": population_cell_id,
        "support_census_sha256": census["support_census_sha256"],
        "generation_projection_rows_sha256": _census_projection_rows_sha256(
            census, population_cell_id
        ),
        "candidate_rows": normalized_rows,
        "solve_failure_count": _integer(
            body.get("solve_failure_count"), label="Odds solve failure count"
        ),
        "retry_count": _integer(body.get("retry_count"), label="Odds retry count"),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    if body != normalized:
        _fail("Odds candidate population body differs from its crossing")
    return normalized, candidate_ids


def _normalize_selection_world_body(
    value: object,
    *,
    census: Mapping[str, object],
    selection_world_cell_id: str,
) -> dict[str, object]:
    body = _mapping(value, label="Odds selection-world body")
    _reject_outcomes(body, label="Odds selection-world body")
    _exact_keys(
        body,
        {
            "schema_version",
            "slate",
            "selection_world_cell_id",
            "support_census_sha256",
            "projection_rows_sha256",
            "player_order_sha256",
            "world_count",
            "world_matrix_sha256",
            "world_matrix_bytes",
            "outcome_columns_read",
            "uses_realized_outcomes",
        },
        label="Odds selection-world body",
    )
    normalized = {
        "schema_version": SELECTION_WORLD_SCHEMA,
        "slate": census["slate"],
        "selection_world_cell_id": selection_world_cell_id,
        "support_census_sha256": census["support_census_sha256"],
        "projection_rows_sha256": _census_projection_rows_sha256(
            census, selection_world_cell_id
        ),
        "player_order_sha256": registry.canonical_sha256([
            row["gsis_id"]
            for cell in census["cells"]
            if cell["cell"]["cell_id"] == selection_world_cell_id
            for row in cell["rows"]
        ]),
        "world_count": _integer(
            body.get("world_count"), label="Odds selection-world count", minimum=1
        ),
        "world_matrix_sha256": body.get("world_matrix_sha256"),
        "world_matrix_bytes": _integer(
            body.get("world_matrix_bytes"),
            label="Odds selection-world matrix bytes",
            minimum=1,
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    if (
        not registry.is_sha256(normalized["player_order_sha256"])
        or not registry.is_sha256(normalized["world_matrix_sha256"])
        or body != normalized
    ):
        _fail("Odds selection-world body differs from its crossing")
    return normalized


def _normalize_selected_book_body(
    value: object,
    *,
    census: Mapping[str, object],
    population_cell_id: str,
    selection_world_cell_id: str,
    candidate_population_identity: Mapping[str, object],
    selection_world_identity: Mapping[str, object],
    candidate_ids: Sequence[str],
) -> tuple[dict[str, object], list[str]]:
    body = _mapping(value, label="Odds selected-book body")
    _reject_outcomes(body, label="Odds selected-book body")
    _exact_keys(
        body,
        {
            "schema_version",
            "slate",
            "population_cell_id",
            "selection_world_cell_id",
            "support_census_sha256",
            "candidate_population_identity",
            "selection_world_identity",
            "selected_lineup_ids",
            "entry_budget",
            "added_latency_ms",
            "outcome_columns_read",
            "uses_realized_outcomes",
        },
        label="Odds selected-book body",
    )
    selected = _sequence(
        body.get("selected_lineup_ids"), label="Odds selected-book lineup IDs"
    )
    latency_ms = _number(body.get("added_latency_ms"), label="Odds added latency")
    normalized = {
        "schema_version": SELECTED_BOOK_SCHEMA,
        "slate": census["slate"],
        "population_cell_id": population_cell_id,
        "selection_world_cell_id": selection_world_cell_id,
        "support_census_sha256": census["support_census_sha256"],
        "candidate_population_identity": dict(candidate_population_identity),
        "selection_world_identity": dict(selection_world_identity),
        "selected_lineup_ids": list(selected),
        "entry_budget": registry.ENTRY_BUDGET,
        "added_latency_ms": latency_ms,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    if (
        body != normalized
        or latency_ms < 0.0
        or len(selected) != registry.ENTRY_BUDGET
        or any(type(value) is not str or not value for value in selected)
        or len(selected) != len(set(selected))
        or not set(selected).issubset(candidate_ids)
    ):
        _fail("Odds selected-book body differs from its crossing")
    return normalized, [str(value) for value in selected]


def build_odds_candidate_population_body_v1(
    *,
    support_census: Mapping[str, object],
    population_cell_id: str,
    candidate_rows: Sequence[Mapping[str, object]],
    solve_failure_count: int,
    retry_count: int,
) -> dict[str, object]:
    census = validate_odds_prop_override_support_census_v1(support_census)
    body: dict[str, object] = {
        "schema_version": CANDIDATE_POPULATION_SCHEMA,
        "slate": census["slate"],
        "population_cell_id": population_cell_id,
        "support_census_sha256": census["support_census_sha256"],
        "generation_projection_rows_sha256": _census_projection_rows_sha256(
            census, population_cell_id
        ),
        "candidate_rows": [dict(row) for row in candidate_rows],
        "solve_failure_count": solve_failure_count,
        "retry_count": retry_count,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _normalize_candidate_population_body(
        body, census=census, population_cell_id=population_cell_id
    )[0]


def build_odds_selection_world_body_v1(
    *,
    support_census: Mapping[str, object],
    selection_world_cell_id: str,
    player_order_sha256: str,
    world_count: int,
    world_matrix_sha256: str,
    world_matrix_bytes: int,
) -> dict[str, object]:
    census = validate_odds_prop_override_support_census_v1(support_census)
    body: dict[str, object] = {
        "schema_version": SELECTION_WORLD_SCHEMA,
        "slate": census["slate"],
        "selection_world_cell_id": selection_world_cell_id,
        "support_census_sha256": census["support_census_sha256"],
        "projection_rows_sha256": _census_projection_rows_sha256(
            census, selection_world_cell_id
        ),
        "player_order_sha256": player_order_sha256,
        "world_count": world_count,
        "world_matrix_sha256": world_matrix_sha256,
        "world_matrix_bytes": world_matrix_bytes,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _normalize_selection_world_body(
        body,
        census=census,
        selection_world_cell_id=selection_world_cell_id,
    )


def build_odds_selected_book_body_v1(
    *,
    support_census: Mapping[str, object],
    population_cell_id: str,
    selection_world_cell_id: str,
    candidate_population_identity: Mapping[str, object],
    selection_world_identity: Mapping[str, object],
    candidate_ids: Sequence[str],
    selected_lineup_ids: Sequence[str],
    added_latency_ms: float,
) -> dict[str, object]:
    census = validate_odds_prop_override_support_census_v1(support_census)
    population_identity = source.normalize_object_identity_v2(
        candidate_population_identity,
        label="Odds candidate population identity",
    )
    world_identity = source.normalize_object_identity_v2(
        selection_world_identity,
        label="Odds selection-world identity",
    )
    body: dict[str, object] = {
        "schema_version": SELECTED_BOOK_SCHEMA,
        "slate": census["slate"],
        "population_cell_id": population_cell_id,
        "selection_world_cell_id": selection_world_cell_id,
        "support_census_sha256": census["support_census_sha256"],
        "candidate_population_identity": population_identity,
        "selection_world_identity": world_identity,
        "selected_lineup_ids": list(selected_lineup_ids),
        "entry_budget": registry.ENTRY_BUDGET,
        "added_latency_ms": added_latency_ms,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _normalize_selected_book_body(
        body,
        census=census,
        population_cell_id=population_cell_id,
        selection_world_cell_id=selection_world_cell_id,
        candidate_population_identity=population_identity,
        selection_world_identity=world_identity,
        candidate_ids=candidate_ids,
    )[0]


def build_odds_prop_override_influence_trace_v1(
    *,
    support_census: Mapping[str, object],
    cell_outputs: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Compare the complete population-source x selection-world crossing.

    ``cell_outputs`` supplies the exact canonical bodies and object identities
    emitted by the outer immutable generation run.  Candidate membership,
    selection-world authority, selected-book membership, and operational
    counts are derived from those bodies rather than trusted as loose parallel
    fields.  No body may contain a realized score.
    """
    census = validate_odds_prop_override_support_census_v1(support_census)
    outputs = _sequence(cell_outputs, label="Odds cell outputs")
    if len(outputs) != len(registry.ODDS_CROSS_ORDER):
        _fail("Odds influence trace requires the exact four-cell crossing")
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(outputs):
        item = _mapping(raw, label=f"Odds output[{ordinal}]")
        _exact_keys(item, {
            "population_cell_id",
            "selection_world_cell_id",
            "selection_world_identity",
            "selection_world_body",
            "candidate_population_identity",
            "candidate_population_body",
            "selected_book_identity",
            "selected_book_body",
        }, label=f"Odds output[{ordinal}]")
        population_cell_id, selection_world_cell_id = registry.ODDS_CROSS_ORDER[
            ordinal
        ]
        if (
            item["population_cell_id"] != population_cell_id
            or item["selection_world_cell_id"] != selection_world_cell_id
        ):
            _fail("Odds influence output cell order differs")
        population_body, candidate_ids = _normalize_candidate_population_body(
            item["candidate_population_body"],
            census=census,
            population_cell_id=population_cell_id,
        )
        population_identity = _bind_body(
            population_body,
            _mapping(
                item["candidate_population_identity"],
                label="Odds candidate population identity",
            ),
            label=f"Odds {population_cell_id} candidate population identity",
        )
        selection_body = _normalize_selection_world_body(
            item["selection_world_body"],
            census=census,
            selection_world_cell_id=selection_world_cell_id,
        )
        selection_identity = _bind_body(
            selection_body,
            _mapping(
                item["selection_world_identity"],
                label="Odds selection-world identity",
            ),
            label=f"Odds {selection_world_cell_id} selection-world identity",
        )
        book_body, selected = _normalize_selected_book_body(
            item["selected_book_body"],
            census=census,
            population_cell_id=population_cell_id,
            selection_world_cell_id=selection_world_cell_id,
            candidate_population_identity=population_identity,
            selection_world_identity=selection_identity,
            candidate_ids=candidate_ids,
        )
        book_identity = _bind_body(
            book_body,
            _mapping(
                item["selected_book_identity"],
                label="Odds selected-book identity",
            ),
            label=(
                f"Odds {population_cell_id} by {selection_world_cell_id} "
                "selected-book identity"
            ),
        )
        normalized.append({
            "population_cell_id": population_cell_id,
            "selection_world_cell_id": selection_world_cell_id,
            "selection_world_identity": selection_identity,
            "selection_world_body": selection_body,
            "candidate_population_identity": population_identity,
            "candidate_population_body": population_body,
            "candidate_ids": candidate_ids,
            "candidate_ids_sha256": registry.canonical_sha256(candidate_ids),
            "selected_book_identity": book_identity,
            "selected_book_body": book_body,
            "selected_lineup_ids": selected,
            "selected_lineup_ids_sha256": registry.canonical_sha256(selected),
            "solve_failure_count": population_body["solve_failure_count"],
            "retry_count": population_body["retry_count"],
            "added_latency_ms": book_body["added_latency_ms"],
        })
    for left, right in ((0, 1), (2, 3)):
        if (
            normalized[left]["candidate_population_identity"]
            != normalized[right]["candidate_population_identity"]
            or normalized[left]["candidate_population_body"]
            != normalized[right]["candidate_population_body"]
            or normalized[left]["candidate_ids"]
            != normalized[right]["candidate_ids"]
            or normalized[left]["solve_failure_count"]
            != normalized[right]["solve_failure_count"]
            or normalized[left]["retry_count"] != normalized[right]["retry_count"]
        ):
            _fail(
                "Odds selection-world crossing changed its generated population"
            )
    for left, right in ((0, 2), (1, 3)):
        if (
            normalized[left]["selection_world_identity"]
            != normalized[right]["selection_world_identity"]
            or normalized[left]["selection_world_body"]
            != normalized[right]["selection_world_body"]
        ):
            _fail("Odds population crossing changed its selection-world authority")
    population_turnover = _membership_metrics(
        normalized[0]["candidate_ids"], normalized[2]["candidate_ids"], ordered=False
    )
    book_turnover = {
        "population_on_selection_on_vs_off": _membership_metrics(
            normalized[0]["selected_lineup_ids"],
            normalized[1]["selected_lineup_ids"],
            ordered=True,
        ),
        "population_off_selection_on_vs_off": _membership_metrics(
            normalized[2]["selected_lineup_ids"],
            normalized[3]["selected_lineup_ids"],
            ordered=True,
        ),
        "selection_on_population_on_vs_off": _membership_metrics(
            normalized[0]["selected_lineup_ids"],
            normalized[2]["selected_lineup_ids"],
            ordered=True,
        ),
        "selection_off_population_on_vs_off": _membership_metrics(
            normalized[1]["selected_lineup_ids"],
            normalized[3]["selected_lineup_ids"],
            ordered=True,
        ),
        "operational_on_on_vs_off_off": _membership_metrics(
            normalized[0]["selected_lineup_ids"],
            normalized[3]["selected_lineup_ids"],
            ordered=True,
        ),
    }
    body: dict[str, object] = {
        "schema_version": INFLUENCE_TRACE_SCHEMA,
        "experiment_id": registry.ODDS_EXPERIMENT_ID,
        "slate": census["slate"],
        "support_census_sha256": census["support_census_sha256"],
        "support_census_body": census,
        "source_state_trace": {
            "cells": [cell["source_state_counts"] for cell in census["cells"]],
            "marginal_turnover": census["marginal_turnover"],
        },
        "cell_outputs": normalized,
        "candidate_population_turnover": population_turnover,
        "selected_book_order_turnover": book_turnover,
        "operational_turnover": {
            "solve_failure_delta_on_minus_off": (
                normalized[0]["solve_failure_count"]
                - normalized[3]["solve_failure_count"]
            ),
            "retry_delta_on_minus_off": (
                normalized[0]["retry_count"] - normalized[3]["retry_count"]
            ),
            "latency_ms_on_minus_off": (
                normalized[0]["added_latency_ms"]
                - normalized[3]["added_latency_ms"]
            ),
        },
        "source_supply_effect": "not_evaluated_without_independent_grade",
        "source_conditioned_retrieval_effect": (
            "not_evaluated_without_independent_grade"
        ),
        "interaction_effect": "not_evaluated_without_independent_grade",
        "operational_on_on_vs_off_off_effect": (
            "not_evaluated_without_independent_grade"
        ),
        **_policy(),
    }
    return _with_hash(body, field="influence_trace_sha256")


def validate_odds_prop_override_influence_trace_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="Odds influence trace")
    _reject_outcomes(item, label="Odds influence trace")
    _validate_hash(
        item, field="influence_trace_sha256", label="Odds influence trace"
    )
    _exact_keys(
        item,
        set(_policy()) | {
            "schema_version",
            "experiment_id",
            "slate",
            "support_census_sha256",
            "support_census_body",
            "source_state_trace",
            "cell_outputs",
            "candidate_population_turnover",
            "selected_book_order_turnover",
            "operational_turnover",
            "source_supply_effect",
            "source_conditioned_retrieval_effect",
            "interaction_effect",
            "operational_on_on_vs_off_off_effect",
            "influence_trace_sha256",
        },
        label="Odds influence trace",
    )
    if (
        item.get("schema_version") != INFLUENCE_TRACE_SCHEMA
        or item.get("experiment_id") != registry.ODDS_EXPERIMENT_ID
        or item.get("value_claim") != "not_evaluated"
        or item.get("source_supply_effect")
        != "not_evaluated_without_independent_grade"
        or item.get("source_conditioned_retrieval_effect")
        != "not_evaluated_without_independent_grade"
        or item.get("interaction_effect")
        != "not_evaluated_without_independent_grade"
        or item.get("operational_on_on_vs_off_off_effect")
        != "not_evaluated_without_independent_grade"
        or item.get("source_value_established") is not False
    ):
        _fail("Odds influence trace policy differs")
    retained_census = validate_odds_prop_override_support_census_v1(
        _mapping(
            item.get("support_census_body"),
            label="Odds influence support census",
        )
    )
    if (
        item.get("support_census_sha256")
        != retained_census["support_census_sha256"]
        or item.get("slate") != retained_census["slate"]
    ):
        _fail("Odds influence trace support-census binding differs")
    _slate(item.get("slate"))
    source_trace = _mapping(
        item.get("source_state_trace"), label="Odds source-state trace"
    )
    _exact_keys(
        source_trace,
        {"cells", "marginal_turnover"},
        label="Odds source-state trace",
    )
    source_cells = [
        _mapping(cell, label="Odds source-state count cell")
        for cell in _sequence(
            source_trace["cells"], label="Odds source-state count cells"
        )
    ]
    if len(source_cells) != len(registry.ODDS_CELL_ORDER) or set(
        source_cells[0]
    ) != set(source_cells[1]):
        _fail("Odds source-state trace cells differ")
    for cell in source_cells:
        for field, count in cell.items():
            _integer(count, label=f"Odds source-state {field}")
    marginal_trace = _mapping(
        source_trace["marginal_turnover"], label="Odds marginal turnover"
    )
    if set(marginal_trace) != {
        "mean_changed_player_count",
        "rank_changed_player_count",
        "maximum_absolute_rank_change",
    }:
        _fail("Odds marginal turnover fields differ")
    for field, count in marginal_trace.items():
        _integer(count, label=f"Odds marginal turnover {field}")
    outputs = [
        _mapping(value, label="Odds influence output")
        for value in _sequence(
            item.get("cell_outputs"), label="Odds influence outputs"
        )
    ]
    if [
        (output.get("population_cell_id"), output.get("selection_world_cell_id"))
        for output in outputs
    ] != list(registry.ODDS_CROSS_ORDER):
        _fail("Odds influence trace cells differ")
    expected_fields = {
        "population_cell_id",
        "selection_world_cell_id",
        "selection_world_identity",
        "selection_world_body",
        "candidate_population_identity",
        "candidate_population_body",
        "candidate_ids",
        "candidate_ids_sha256",
        "selected_book_identity",
        "selected_book_body",
        "selected_lineup_ids",
        "selected_lineup_ids_sha256",
        "solve_failure_count",
        "retry_count",
        "added_latency_ms",
    }
    for ordinal, output in enumerate(outputs):
        _exact_keys(output, expected_fields, label=f"Odds influence output[{ordinal}]")
        candidates = _sequence(
            output["candidate_ids"], label="Odds influence candidate IDs"
        )
        selected = _sequence(
            output["selected_lineup_ids"],
            label="Odds influence selected IDs",
        )
        if (
            not candidates
            or any(type(value) is not str or not value for value in candidates)
            or any(type(value) is not str or not value for value in selected)
            or len(candidates) != len(set(candidates))
            or len(selected) != registry.ENTRY_BUDGET
            or len(selected) != len(set(selected))
            or not set(selected).issubset(candidates)
            or output["candidate_ids_sha256"]
            != registry.canonical_sha256(candidates)
            or output["selected_lineup_ids_sha256"]
            != registry.canonical_sha256(selected)
        ):
            _fail("Odds influence output membership differs")
        population_cell_id, selection_world_cell_id = registry.ODDS_CROSS_ORDER[
            ordinal
        ]
        population_body, body_candidate_ids = _normalize_candidate_population_body(
            output["candidate_population_body"],
            census=retained_census,
            population_cell_id=population_cell_id,
        )
        population_identity = _bind_body(
            population_body,
            _mapping(
                output["candidate_population_identity"],
                label="Odds candidate population identity",
            ),
            label="Odds candidate population identity",
        )
        selection_body = _normalize_selection_world_body(
            output["selection_world_body"],
            census=retained_census,
            selection_world_cell_id=selection_world_cell_id,
        )
        selection_identity = _bind_body(
            selection_body,
            _mapping(
                output["selection_world_identity"],
                label="Odds selection-world identity",
            ),
            label="Odds selection-world identity",
        )
        book_body, body_selected_ids = _normalize_selected_book_body(
            output["selected_book_body"],
            census=retained_census,
            population_cell_id=population_cell_id,
            selection_world_cell_id=selection_world_cell_id,
            candidate_population_identity=population_identity,
            selection_world_identity=selection_identity,
            candidate_ids=body_candidate_ids,
        )
        book_identity = _bind_body(
            book_body,
            _mapping(
                output["selected_book_identity"],
                label="Odds selected-book identity",
            ),
            label="Odds selected-book identity",
        )
        if (
            candidates != body_candidate_ids
            or selected != body_selected_ids
            or output["candidate_population_identity"] != population_identity
            or output["selection_world_identity"] != selection_identity
            or output["selected_book_identity"] != book_identity
            or output["solve_failure_count"] != population_body["solve_failure_count"]
            or output["retry_count"] != population_body["retry_count"]
            or output["added_latency_ms"] != book_body["added_latency_ms"]
        ):
            _fail("Odds influence output differs from exact bodies")
    for left, right in ((0, 1), (2, 3)):
        if (
            outputs[left]["candidate_population_identity"]
            != outputs[right]["candidate_population_identity"]
            or outputs[left]["candidate_population_body"]
            != outputs[right]["candidate_population_body"]
            or outputs[left]["candidate_ids"] != outputs[right]["candidate_ids"]
            or outputs[left]["solve_failure_count"]
            != outputs[right]["solve_failure_count"]
            or outputs[left]["retry_count"] != outputs[right]["retry_count"]
        ):
            _fail("Odds selection-world crossing changed its generated population")
    for left, right in ((0, 2), (1, 3)):
        if (
            outputs[left]["selection_world_identity"]
            != outputs[right]["selection_world_identity"]
            or outputs[left]["selection_world_body"]
            != outputs[right]["selection_world_body"]
        ):
            _fail("Odds population crossing changed its selection-world authority")
    expected_population_turnover = _membership_metrics(
        outputs[0]["candidate_ids"], outputs[2]["candidate_ids"], ordered=False
    )
    expected_book_turnover = {
        "population_on_selection_on_vs_off": _membership_metrics(
            outputs[0]["selected_lineup_ids"],
            outputs[1]["selected_lineup_ids"],
            ordered=True,
        ),
        "population_off_selection_on_vs_off": _membership_metrics(
            outputs[2]["selected_lineup_ids"],
            outputs[3]["selected_lineup_ids"],
            ordered=True,
        ),
        "selection_on_population_on_vs_off": _membership_metrics(
            outputs[0]["selected_lineup_ids"],
            outputs[2]["selected_lineup_ids"],
            ordered=True,
        ),
        "selection_off_population_on_vs_off": _membership_metrics(
            outputs[1]["selected_lineup_ids"],
            outputs[3]["selected_lineup_ids"],
            ordered=True,
        ),
        "operational_on_on_vs_off_off": _membership_metrics(
            outputs[0]["selected_lineup_ids"],
            outputs[3]["selected_lineup_ids"],
            ordered=True,
        ),
    }
    expected_operational = {
        "solve_failure_delta_on_minus_off": (
            outputs[0]["solve_failure_count"]
            - outputs[3]["solve_failure_count"]
        ),
        "retry_delta_on_minus_off": (
            outputs[0]["retry_count"] - outputs[3]["retry_count"]
        ),
        "latency_ms_on_minus_off": (
            outputs[0]["added_latency_ms"] - outputs[3]["added_latency_ms"]
        ),
    }
    if (
        item.get("candidate_population_turnover")
        != expected_population_turnover
        or item.get("selected_book_order_turnover") != expected_book_turnover
        or item.get("operational_turnover") != expected_operational
    ):
        _fail("Odds influence trace turnover differs")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("Odds influence trace claims downstream authority")
    return item


__all__ = [
    "OddsPropOverrideAblationV1Error",
    "build_odds_candidate_population_body_v1",
    "build_dk_ppg_fallback_authority_v1",
    "build_odds_prop_override_influence_trace_v1",
    "build_odds_prop_override_panel_support_census_v1",
    "build_odds_prop_override_support_census_v1",
    "build_odds_selected_book_body_v1",
    "build_odds_selection_world_body_v1",
    "build_prop_snapshot_authority_v1",
    "validate_dk_ppg_fallback_authority_v1",
    "validate_odds_prop_override_influence_trace_v1",
    "validate_odds_prop_override_panel_support_census_v1",
    "validate_odds_prop_override_support_census_v1",
    "validate_prop_snapshot_authority_v1",
]
