"""Pure score-free A2a rank-factor split and exact mechanism gate.

The frozen scientific contract is
``reports/2026-08-20-a2a-rank-factor-split-scorefree-protocol.md``.
This module deliberately has no storage, outcome, lineup, or scoring imports.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

import numpy as np
import pandas as pd


VERSION = "a2a-rank-factor-split-scorefree-v2"
REGISTERED_BLOCKS = ("R0", "R1", "R2", "R3", "R4")
EXPECTED_WORLDS = 10_000
MIN_MEAN = 4.0
GENERIC_ATTENUATION = 0.5
QB_WR_ALLOCATION = 1.0
POSITIONS = ("QB", "RB", "WR", "TE")
MULTIPLICITY_CELLS = (
    "multiplicity_ge2", "multiplicity_ge3", "multiplicity_ge4",
)
CONDITIONAL_CELLS = (
    "qb_wr", "qb_te", "qb_rb", "wr_wr", "rb_rb", "te_te",
)
PROTECTED_CONDITIONAL_CELLS = (
    "qb_rb", "qb_te", "wr_wr", "rb_rb", "te_te",
)
EXPECTED_SLATE_KEYS = tuple(
    (season, week)
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)

_CATALOG_FIELDS = {
    "season", "week", "player_id", "position", "team", "mean_projection",
}
_FORBIDDEN_FIELD_PATTERNS = (
    r"(^|_)actual($|_)", r"(^|_)outcome($|_)", r"(^|_)ownership($|_)",
    r"(^|_)payout($|_)", r"(^|_)standing(s)?($|_)",
    r"(^|_)winner($|_)", r"(^|_)contest_result($|_)",
    r"(^|_)selected_lineup($|_)", r"(^|_)lineup_score($|_)",
    r"(^|_)candidate_score($|_)", r"^rank$",
)
_COUNT_FIELDS = (
    "eligible_rows", "eligible_groups", "transformed_rows",
    "eligible_group_worlds", "one_hot_assignments", "changed_rows",
    "changed_world_cells", "row_world_cells", "q90_rows_checked",
    "qb_rows_checked", "unchanged_rows_checked",
)
_INVARIANT_FIELDS = (
    "source_alignment_exact", "finite_output",
    "deterministic_repeat_exact", "exact_sorted_marginals",
    "exact_q90_boom_counts", "qb_bit_exact",
    "ineligible_or_unsupported_bit_exact", "row_world_budget_unchanged",
    "one_hot_exact",
)


def stable_open_unit_ranks(values: np.ndarray) -> np.ndarray:
    """Stable ordinal ranks ``(rank + 0.5) / W``; world index breaks ties."""
    row = np.asarray(values)
    if row.ndim != 1 or len(row) < 2 or row.dtype.kind not in "fiu":
        raise ValueError("A2a ranks require one real numeric draw row")
    if not np.isfinite(row).all():
        raise ValueError("A2a ranks require finite draws")
    order = np.argsort(row, kind="stable")
    ranks = np.empty(len(row), dtype=np.int64)
    ranks[order] = np.arange(len(row), dtype=np.int64)
    return (ranks.astype(np.float64) + 0.5) / float(len(row))


def competitive_wr_assignment(canonical_wr_ranks: np.ndarray) -> np.ndarray:
    """Return one WR-row offset per world; the first row wins rank ties.

    Callers must supply rows in canonical ``(player_id, source_row_index)``
    order. ``numpy.argmax`` then implements the frozen tie rule exactly.
    """
    ranks = np.asarray(canonical_wr_ranks, dtype=np.float64)
    if ranks.ndim != 2 or ranks.shape[0] < 2 or ranks.shape[1] < 2:
        raise ValueError("A2a competitive WR ranks require at least 2x2")
    if not np.isfinite(ranks).all():
        raise ValueError("A2a competitive WR ranks must be finite")
    return np.argmax(ranks, axis=0).astype(np.int64, copy=False)


def _normalise_catalog(
    catalog_rows: pd.DataFrame | Sequence[Mapping[str, object]],
) -> pd.DataFrame:
    frame = (
        catalog_rows.copy()
        if isinstance(catalog_rows, pd.DataFrame)
        else pd.DataFrame(list(catalog_rows))
    )
    forbidden = []
    for column in frame.columns:
        name = re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        if any(re.search(pattern, name) for pattern in _FORBIDDEN_FIELD_PATTERNS):
            forbidden.append(str(column))
    if forbidden:
        raise ValueError(f"A2a catalog contains forbidden fields {sorted(forbidden)}")
    if set(frame.columns) != _CATALOG_FIELDS:
        raise ValueError(
            f"A2a catalog fields differ: expected {sorted(_CATALOG_FIELDS)}"
        )
    if frame.empty or not frame.index.equals(pd.RangeIndex(len(frame))):
        raise ValueError("A2a catalog requires a nonempty canonical row index")
    if frame[["season", "week", "player_id", "position", "team"]].isna().any().any():
        raise ValueError("A2a catalog identity contains nulls")

    numeric_season = pd.to_numeric(frame.season, errors="raise").to_numpy(float)
    numeric_week = pd.to_numeric(frame.week, errors="raise").to_numpy(float)
    means = pd.to_numeric(frame.mean_projection, errors="raise").to_numpy(float)
    if not np.isfinite(numeric_season).all() or not np.isfinite(numeric_week).all() \
            or not np.isfinite(means).all() \
            or not np.equal(numeric_season, np.floor(numeric_season)).all() \
            or not np.equal(numeric_week, np.floor(numeric_week)).all():
        raise ValueError("A2a catalog numeric fields are invalid")
    frame["season"] = numeric_season.astype(np.int64)
    frame["week"] = numeric_week.astype(np.int64)
    frame["mean_projection"] = means
    for column in ("player_id", "position", "team"):
        raw = frame[column].astype(str)
        if raw.str.strip().ne(raw).any() or raw.eq("").any():
            raise ValueError(f"A2a catalog {column} is not canonical")
        frame[column] = raw
    frame["position"] = frame.position.str.upper()
    frame["team"] = frame.team.str.upper()
    if frame.duplicated(["season", "week", "player_id"]).any():
        raise ValueError("A2a catalog repeats a player-slate key")
    keys = list(zip(frame.season, frame.week, frame.player_id, strict=True))
    if keys != sorted(keys):
        raise ValueError("A2a catalog order is noncanonical")
    slates = frame[["season", "week"]].drop_duplicates()
    if len(slates) != 1:
        raise ValueError("A2a slate transform requires exactly one slate")
    return frame


def _normalise_inputs(
    catalog_rows: pd.DataFrame | Sequence[Mapping[str, object]],
    player_ids: Sequence[str],
    control_draws: np.ndarray,
    expected_worlds: int,
) -> tuple[pd.DataFrame, list[str], np.ndarray, dict[str, int]]:
    if isinstance(expected_worlds, bool) or not isinstance(expected_worlds, int) \
            or expected_worlds < 2:
        raise ValueError("A2a expected world count is invalid")
    frame = _normalise_catalog(catalog_rows)
    ids = [str(value) for value in player_ids]
    if any(not value or value.strip() != value for value in ids) \
            or len(ids) != len(set(ids)):
        raise ValueError("A2a artifact player identities are invalid")
    raw = np.asarray(control_draws)
    if raw.ndim != 2 or raw.shape != (len(ids), expected_worlds) \
            or raw.dtype.kind not in "fiu":
        raise ValueError("A2a artifact draws and identities are misaligned")
    values = np.ascontiguousarray(raw)
    if not np.isfinite(values).all():
        raise ValueError("A2a artifact contains a nonfinite draw")
    index = {player_id: row for row, player_id in enumerate(ids)}
    missing = set(frame.player_id) - set(index)
    if missing:
        raise ValueError("A2a artifact is missing a locked catalog row")
    return frame, ids, values, index


def _unsigned_view(values: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(values).view(
        np.dtype(f"u{values.dtype.itemsize}")
    ).reshape(values.shape)


def _apply_core(
    frame: pd.DataFrame,
    values: np.ndarray,
    artifact_index: Mapping[str, int],
) -> tuple[np.ndarray, dict[str, Any], np.ndarray]:
    meta = frame.copy()
    meta["_artifact_row"] = [artifact_index[value] for value in meta.player_id]
    meta["_eligible"] = (
        meta.position.isin(POSITIONS) & meta.mean_projection.ge(MIN_MEAN)
    )
    out = values.copy()
    transformed = np.zeros(len(values), dtype=bool)
    groups = one_hot = 0

    eligible = meta[meta._eligible]
    for _key, group in eligible.groupby(["season", "week", "team"], sort=True):
        qbs = group[group.position.eq("QB")]
        wrs = group[group.position.eq("WR")].sort_values(
            ["player_id", "_artifact_row"], kind="stable",
        )
        if len(qbs) != 1 or len(wrs) < 2:
            continue
        ordered_group = group.sort_values(
            ["player_id", "_artifact_row"], kind="stable",
        )
        rows = ordered_group._artifact_row.to_numpy(int)
        ranks = np.stack([stable_open_unit_ranks(values[row]) for row in rows])
        by_artifact = {row: offset for offset, row in enumerate(rows)}
        group_factor = ranks.mean(axis=0, dtype=np.float64)
        qb_row = int(qbs._artifact_row.iloc[0])
        qb_rank = ranks[by_artifact[qb_row]]
        wr_rows = wrs._artifact_row.to_numpy(int)
        wr_rank = np.stack([ranks[by_artifact[row]] for row in wr_rows])
        selected = competitive_wr_assignment(wr_rank)
        one_hot += int(len(selected))
        wr_offset = {row: offset for offset, row in enumerate(wr_rows)}

        for position, row in ordered_group[
            ["position", "_artifact_row"]
        ].itertuples(index=False, name=None):
            row = int(row)
            if position == "QB":
                continue
            priority = (
                ranks[by_artifact[row]]
                - GENERIC_ATTENUATION * (group_factor - 0.5)
            )
            if position == "WR":
                priority = priority + (
                    selected == wr_offset[row]
                ) * (QB_WR_ALLOCATION * (qb_rank - 0.5))
            order = np.argsort(priority, kind="stable")
            out[row, order] = np.sort(values[row], kind="stable")
            transformed[row] = True
        groups += 1

    return out, {
        "eligible_rows": int(meta._eligible.sum()),
        "eligible_groups": int(groups),
        "transformed_rows": int(transformed.sum()),
        "eligible_group_worlds": int(groups * values.shape[1]),
        "one_hot_assignments": int(one_hot),
    }, transformed


def _empty_cells() -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    multiplicity = {
        cell: {"groups": 0, "events": 0, "group_worlds": 0}
        for cell in MULTIPLICITY_CELLS
    }
    conditional = {
        cell: {
            "directed_pairs": 0, "both": 0, "conditioned": 0,
            "other_only": 0, "not_conditioned": 0, "pair_worlds": 0,
        }
        for cell in CONDITIONAL_CELLS
    }
    return multiplicity, conditional


def _measure(
    frame: pd.DataFrame,
    artifact_index: Mapping[str, int],
    flags: np.ndarray,
) -> dict[str, dict[str, int]]:
    meta = frame[
        frame.position.isin(POSITIONS) & frame.mean_projection.ge(MIN_MEAN)
    ].copy()
    meta["_artifact_row"] = [artifact_index[value] for value in meta.player_id]
    multiplicity, conditional = _empty_cells()
    worlds = flags.shape[1]

    def add_pair(cell: str, left: int, right: int) -> None:
        a, b = flags[left], flags[right]
        row = conditional[cell]
        row["directed_pairs"] += 1
        row["both"] += int(np.count_nonzero(a & b))
        row["conditioned"] += int(np.count_nonzero(a))
        row["other_only"] += int(np.count_nonzero((~a) & b))
        row["not_conditioned"] += int(np.count_nonzero(~a))
        row["pair_worlds"] += worlds

    for _key, group in meta.groupby(["season", "week", "team"], sort=True):
        rows = group._artifact_row.to_numpy(int)
        if len(rows) >= 3:
            counts = flags[rows].sum(axis=0)
            for threshold, cell in zip((2, 3, 4), MULTIPLICITY_CELLS, strict=True):
                multiplicity[cell]["groups"] += 1
                multiplicity[cell]["events"] += int(np.count_nonzero(counts >= threshold))
                multiplicity[cell]["group_worlds"] += worlds
        qbs = group[group.position.eq("QB")]._artifact_row.to_list()
        if len(qbs) == 1:
            qb = int(qbs[0])
            for position, cell in (("WR", "qb_wr"), ("TE", "qb_te"), ("RB", "qb_rb")):
                for teammate in group[group.position.eq(position)]._artifact_row:
                    add_pair(cell, qb, int(teammate))
        for position, cell in (("WR", "wr_wr"), ("RB", "rb_rb"), ("TE", "te_te")):
            teammates = [int(value) for value in group[
                group.position.eq(position)
            ]._artifact_row]
            for offset, left in enumerate(teammates):
                for right in teammates[offset + 1:]:
                    add_pair(cell, left, right)
                    add_pair(cell, right, left)
    return {**multiplicity, **conditional}


def transform_and_measure_slate(
    catalog_rows: pd.DataFrame | Sequence[Mapping[str, object]],
    player_ids: Sequence[str],
    control_draws: np.ndarray,
    *,
    expected_worlds: int = EXPECTED_WORLDS,
) -> tuple[np.ndarray, dict[str, object]]:
    """Apply the frozen transform to one slate and retain exact contributions."""
    frame, ids, control, artifact_index = _normalise_inputs(
        catalog_rows, player_ids, control_draws, expected_worlds,
    )
    treatment, core, transformed = _apply_core(frame, control, artifact_index)
    repeated, repeated_core, repeated_mask = _apply_core(frame, control, artifact_index)
    control_bits = _unsigned_view(control)
    treatment_bits = _unsigned_view(treatment)
    changed = control_bits != treatment_bits
    exact_marginals = bool(np.array_equal(
        np.sort(control_bits, axis=1), np.sort(treatment_bits, axis=1),
    ))
    thresholds = np.quantile(control, 0.90, axis=1)
    control_booms = control > thresholds[:, None]
    treatment_booms = treatment > thresholds[:, None]
    q90_exact = bool(np.array_equal(
        control_booms.sum(axis=1), treatment_booms.sum(axis=1),
    ))
    catalog_artifact_rows = np.array(
        [artifact_index[value] for value in frame.player_id], dtype=int,
    )
    qb_rows = np.array([
        artifact_index[item.player_id]
        for item in frame.itertuples(index=False) if item.position == "QB"
    ], dtype=int)
    unchanged = np.ones(len(control), dtype=bool)
    unchanged[np.flatnonzero(transformed)] = False
    mechanics = {
        **core,
        "changed_rows": int(changed.any(axis=1).sum()),
        "changed_world_cells": int(changed.sum()),
        "row_world_cells": int(control.size),
        "q90_rows_checked": int(len(control)),
        "qb_rows_checked": int(len(qb_rows)),
        "unchanged_rows_checked": int(unchanged.sum()),
        "source_alignment_exact": True,
        "finite_output": bool(np.isfinite(treatment).all()),
        "deterministic_repeat_exact": bool(
            treatment.tobytes() == repeated.tobytes()
            and core == repeated_core
            and np.array_equal(transformed, repeated_mask)
        ),
        "exact_sorted_marginals": exact_marginals,
        "exact_q90_boom_counts": q90_exact,
        "qb_bit_exact": bool(
            len(qb_rows) == 0
            or np.array_equal(control_bits[qb_rows], treatment_bits[qb_rows])
        ),
        "ineligible_or_unsupported_bit_exact": bool(
            np.array_equal(control_bits[unchanged], treatment_bits[unchanged])
        ),
        "row_world_budget_unchanged": treatment.shape == control.shape,
        "one_hot_exact": (
            core["one_hot_assignments"] == core["eligible_group_worlds"]
        ),
        "generic_attenuation": GENERIC_ATTENUATION,
        "qb_wr_allocation": QB_WR_ALLOCATION,
    }
    mechanics["nonvacuous"] = bool(
        core["eligible_groups"] > 0 and mechanics["changed_world_cells"] > 0
    )
    mechanics["passes"] = bool(
        all(mechanics[name] for name in _INVARIANT_FIELDS)
        and mechanics["nonvacuous"]
    )
    season, week = frame[["season", "week"]].iloc[0]
    report = {
        "version": VERSION,
        "scope": "slate",
        "season": int(season),
        "week": int(week),
        "slates": 1,
        "slate_keys": [[int(season), int(week)]],
        "worlds": int(expected_worlds),
        "artifact_rows": int(len(ids)),
        "catalog_rows": int(len(frame)),
        "catalog_artifact_rows": int(len(catalog_artifact_rows)),
        "mechanics": mechanics,
        "control": _measure(frame, artifact_index, control_booms),
        "treatment": _measure(frame, artifact_index, treatment_booms),
    }
    return treatment, report


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) \
            or int(value) < 0:
        raise ValueError(f"A2a {label} must be a nonnegative integer")
    return int(value)


def _sum_cells(reports: Sequence[Mapping[str, object]], arm: str) -> dict[str, dict[str, int]]:
    total = {**_empty_cells()[0], **_empty_cells()[1]}
    for report in reports:
        cells = report.get(arm)
        if not isinstance(cells, Mapping) or set(cells) != set(total):
            raise ValueError(f"A2a {arm} contribution schema differs")
        for cell, target in total.items():
            source = cells[cell]
            if not isinstance(source, Mapping) or set(source) != set(target):
                raise ValueError(f"A2a {arm} {cell} schema differs")
            for field in target:
                target[field] += _nonnegative_int(source[field], f"{cell}.{field}")
    return total


def combine_reports(reports: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Combine distinct one-slate reports into one exact block report."""
    rows = list(reports)
    if not rows:
        raise ValueError("A2a cannot combine an empty report list")
    if any(row.get("version") != VERSION or row.get("scope") != "slate" for row in rows):
        raise ValueError("A2a combine requires slate reports from this version")
    worlds = {_nonnegative_int(row.get("worlds"), "worlds") for row in rows}
    if len(worlds) != 1:
        raise ValueError("A2a slate reports have different world counts")
    slate_keys = [(int(row["season"]), int(row["week"])) for row in rows]
    if len(slate_keys) != len(set(slate_keys)):
        raise ValueError("A2a block repeats a slate")
    mechanics_rows = [row.get("mechanics") for row in rows]
    if any(not isinstance(item, Mapping) for item in mechanics_rows):
        raise ValueError("A2a slate mechanics are missing")
    mechanics = {
        name: sum(_nonnegative_int(item.get(name), name) for item in mechanics_rows)
        for name in _COUNT_FIELDS
    }
    for name in _INVARIANT_FIELDS:
        if any(not isinstance(item.get(name), bool) for item in mechanics_rows):
            raise ValueError(f"A2a mechanical invariant {name} differs")
        mechanics[name] = all(bool(item[name]) for item in mechanics_rows)
    mechanics.update({
        "generic_attenuation": GENERIC_ATTENUATION,
        "qb_wr_allocation": QB_WR_ALLOCATION,
    })
    mechanics["nonvacuous"] = bool(
        mechanics["eligible_groups"] > 0 and mechanics["changed_world_cells"] > 0
    )
    mechanics["passes"] = bool(
        all(mechanics[name] for name in _INVARIANT_FIELDS)
        and mechanics["nonvacuous"]
    )
    ordered_keys = sorted(slate_keys)
    return {
        "version": VERSION,
        "scope": "block",
        "slates": len(rows),
        "slate_keys": [[season, week] for season, week in ordered_keys],
        "worlds": worlds.pop(),
        "artifact_rows": sum(_nonnegative_int(row.get("artifact_rows"), "artifact_rows") for row in rows),
        "catalog_rows": sum(_nonnegative_int(row.get("catalog_rows"), "catalog_rows") for row in rows),
        "mechanics": mechanics,
        "control": _sum_cells(rows, "control"),
        "treatment": _sum_cells(rows, "treatment"),
    }


def compare_conditional_lifts(
    control: Mapping[str, int], treatment: Mapping[str, int],
) -> int:
    """Compare treatment/control lift by exact integer cross multiplication."""
    fields = {"both", "conditioned", "other_only", "not_conditioned"}
    if not fields.issubset(control) or not fields.issubset(treatment):
        raise ValueError("A2a conditional contribution fields are incomplete")
    c = {name: _nonnegative_int(control[name], name) for name in fields}
    t = {name: _nonnegative_int(treatment[name], name) for name in fields}
    c_den = c["conditioned"] * c["other_only"]
    t_den = t["conditioned"] * t["other_only"]
    if c_den == 0 or t_den == 0:
        raise ValueError("A2a conditional lift has a zero denominator")
    left = t["both"] * t["not_conditioned"] * c_den
    right = c["both"] * c["not_conditioned"] * t_den
    return (left > right) - (left < right)


def _aggregate_blocks(blocks: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    rows = [blocks[name] for name in REGISTERED_BLOCKS]
    first = rows[0]
    keys = first.get("slate_keys")
    if any(row.get("slate_keys") != keys for row in rows):
        raise ValueError("A2a block slate grids differ")
    mechanics_rows = [row["mechanics"] for row in rows]
    mechanics = {
        name: sum(_nonnegative_int(item[name], name) for item in mechanics_rows)
        for name in _COUNT_FIELDS
    }
    for name in _INVARIANT_FIELDS:
        mechanics[name] = all(bool(item.get(name)) for item in mechanics_rows)
    mechanics.update({
        "generic_attenuation": GENERIC_ATTENUATION,
        "qb_wr_allocation": QB_WR_ALLOCATION,
    })
    mechanics["nonvacuous"] = bool(
        mechanics["eligible_groups"] > 0 and mechanics["changed_world_cells"] > 0
    )
    mechanics["passes"] = bool(
        all(mechanics[name] for name in _INVARIANT_FIELDS)
        and mechanics["nonvacuous"]
    )
    return {
        "version": VERSION, "scope": "aggregate", "slates": first["slates"],
        "slate_keys": keys,
        "worlds": sum(_nonnegative_int(row["worlds"], "worlds") for row in rows),
        "artifact_rows": first["artifact_rows"],
        "catalog_rows": first["catalog_rows"],
        "mechanics": mechanics,
        "control": _sum_cells(rows, "control"),
        "treatment": _sum_cells(rows, "treatment"),
    }


def evaluate_mechanism_gate(
    blocks: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Apply the frozen exact aggregate plus three-of-five mechanism gate."""
    if tuple(sorted(blocks)) != REGISTERED_BLOCKS:
        raise ValueError("A2a gate requires exact R0--R4 blocks")
    for name, report in blocks.items():
        if report.get("version") != VERSION or report.get("scope") != "block":
            raise ValueError(f"A2a {name} block report contract differs")
    aggregate = _aggregate_blocks(blocks)
    expected_keys = [[season, week] for season, week in EXPECTED_SLATE_KEYS]
    complete_grid = all(
        block.get("slates") == len(EXPECTED_SLATE_KEYS)
        and block.get("slate_keys") == expected_keys
        for block in blocks.values()
    )
    exact_worlds = all(
        block.get("worlds") == EXPECTED_WORLDS for block in blocks.values()
    ) and aggregate["worlds"] == EXPECTED_WORLDS * len(REGISTERED_BLOCKS)
    denominator_valid = True
    directions: dict[str, dict[str, int | None]] = {}
    for name, report in blocks.items():
        try:
            qb_wr = compare_conditional_lifts(
                report["control"]["qb_wr"], report["treatment"]["qb_wr"],
            )
            for cell in PROTECTED_CONDITIONAL_CELLS:
                compare_conditional_lifts(
                    report["control"][cell], report["treatment"][cell],
                )
        except ValueError:
            denominator_valid = False
            qb_wr = None
        directions[name] = {
            "qb_wr": qb_wr,
            "multiplicity_ge3": (
                int(report["treatment"]["multiplicity_ge3"]["events"])
                - int(report["control"]["multiplicity_ge3"]["events"])
            ),
        }
    try:
        aggregate_qb_wr = compare_conditional_lifts(
            aggregate["control"]["qb_wr"], aggregate["treatment"]["qb_wr"],
        )
        protected = {
            cell: compare_conditional_lifts(
                aggregate["control"][cell], aggregate["treatment"][cell],
            )
            for cell in PROTECTED_CONDITIONAL_CELLS
        }
    except ValueError:
        denominator_valid = False
        aggregate_qb_wr = None
        protected = {cell: None for cell in PROTECTED_CONDITIONAL_CELLS}

    conditions: dict[str, bool] = {
        "complete_54x5_grid": complete_grid,
        "exact_world_counts": exact_worlds,
        "all_block_mechanics_pass": all(
            bool(block["mechanics"].get("passes")) for block in blocks.values()
        ),
        "aggregate_mechanics_pass": bool(aggregate["mechanics"]["passes"]),
        "conditional_denominators_nonzero": denominator_valid,
        "aggregate_qb_wr_strictly_greater": aggregate_qb_wr == 1,
        "qb_wr_strictly_greater_in_at_least_three_blocks": sum(
            row["qb_wr"] == 1 for row in directions.values()
        ) >= 3,
        "aggregate_multiplicity_ge3_strictly_less": (
            aggregate["treatment"]["multiplicity_ge3"]["events"]
            < aggregate["control"]["multiplicity_ge3"]["events"]
        ),
        "multiplicity_ge3_strictly_less_in_at_least_three_blocks": sum(
            row["multiplicity_ge3"] < 0 for row in directions.values()
        ) >= 3,
        "aggregate_multiplicity_ge2_no_greater": (
            aggregate["treatment"]["multiplicity_ge2"]["events"]
            <= aggregate["control"]["multiplicity_ge2"]["events"]
        ),
        "aggregate_multiplicity_ge4_no_greater": (
            aggregate["treatment"]["multiplicity_ge4"]["events"]
            <= aggregate["control"]["multiplicity_ge4"]["events"]
        ),
    }
    conditions.update({
        f"aggregate_{cell}_no_greater": protected[cell] is not None
        and protected[cell] <= 0
        for cell in PROTECTED_CONDITIONAL_CELLS
    })
    mechanical_names = {
        "complete_54x5_grid", "exact_world_counts", "all_block_mechanics_pass",
        "aggregate_mechanics_pass", "conditional_denominators_nonzero",
    }
    mechanical = all(conditions[name] for name in mechanical_names)
    directional = all(
        value for name, value in conditions.items() if name not in mechanical_names
    )
    passes = mechanical and directional
    disposition = (
        "a2a-scorefree-mechanism-passes" if passes else
        "a2a-scorefree-invalid" if not mechanical else
        "a2a-scorefree-mechanism-fails"
    )
    licenses = {
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "historical_remeasurement_licensed": passes,
        "exact80_scoring_licensed": False,
        "single_stack_arm_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    return {
        "passes": passes,
        "mechanical_invariants_pass": mechanical,
        "directional_conditions_pass": directional,
        "conditions": conditions,
        "disposition": disposition,
        "licenses": licenses,
        "aggregate": aggregate,
        "block_directions": directions,
    }


__all__ = [
    "CONDITIONAL_CELLS", "EXPECTED_WORLDS", "MULTIPLICITY_CELLS",
    "REGISTERED_BLOCKS", "VERSION", "combine_reports",
    "compare_conditional_lifts", "competitive_wr_assignment",
    "evaluate_mechanism_gate", "stable_open_unit_ranks",
    "transform_and_measure_slate",
]
