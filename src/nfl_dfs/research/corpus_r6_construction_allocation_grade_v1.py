"""Isolated realized grader for the construction x allocation cross.

The grader accepts only a fully validated score-blind selection receipt.  It
then joins explicit, content-identified realized player points and reports
K20/K40/K80, the 194--240 tail surface, candidate ceiling, selector regret,
both factor effects, full-panel and season aggregates, and the preregistered
K80 difference-in-differences.

Historical output is descriptive mechanism evidence only.  It cannot promote
or modify a production policy automatically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from statistics import stdev
from typing import Final

from . import corpus_r6_construction_allocation_cross_v1 as cross
from . import corpus_r6_construction_allocation_cross_operator_v1 as operator


GRADE_SCHEMA: Final = "corpus-r6-construction-allocation-grade/v1"
OUTCOME_DOCUMENT_SCHEMA: Final = (
    "corpus-r6-construction-allocation-slate-outcomes/v1"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ConstructionAllocationGradeError(ValueError):
    """The post-selection historical grade contract differs."""


def _fail(message: str) -> None:
    raise ConstructionAllocationGradeError(message)


def _points_micro(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        _fail(f"{label} is not a score")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ConstructionAllocationGradeError(
            f"{label} is not a score"
        ) from exc
    if not decimal.is_finite():
        _fail(f"{label} is not finite")
    scaled = decimal * Decimal(1_000_000)
    if scaled != scaled.to_integral_value():
        _fail(f"{label} exceeds six-decimal micro-point precision")
    return int(scaled)


def _actuals(value: object, *, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping) or not value:
        _fail(f"{label} is not a nonempty mapping")
    result: dict[str, int] = {}
    for raw_id, raw_points in value.items():
        player_id = str(raw_id)
        if not player_id or player_id in result:
            _fail(f"{label} player IDs are empty or collide")
        result[player_id] = _points_micro(
            raw_points, label=f"{label}[{player_id}]"
        )
    return result


def _identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a content identity")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    if (
        type(uri) is not str
        or not uri
        or type(generation) not in {str, int}
        or not str(generation)
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        or type(size) is not int
        or size <= 0
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": size,
    }


def outcome_document_v1(
    *, slate_id: str, actual_points: Mapping[object, object],
) -> dict[str, object]:
    actuals = _actuals(actual_points, label=f"{slate_id} actuals")
    body: dict[str, object] = {
        "schema_version": OUTCOME_DOCUMENT_SCHEMA,
        "slate_id": slate_id,
        "player_points_micro": dict(sorted(actuals.items())),
        "precision": "integer-millionths-of-one-dk-point",
    }
    return {**body, "outcome_sha256": cross.canonical_sha256(body)}


def _bind_outcome_document(
    *,
    slate_id: str,
    actual_points: Mapping[object, object],
    outcome_identity: Mapping[str, object],
) -> tuple[dict[str, int], dict[str, object]]:
    document = outcome_document_v1(
        slate_id=slate_id, actual_points=actual_points
    )
    identity = _identity(outcome_identity, label=f"{slate_id} outcomes")
    raw = cross.canonical_json_bytes(document)
    if (
        identity["sha256"] != hashlib.sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
    ):
        _fail(f"{slate_id} outcome identity is not bound to its score map")
    return dict(document["player_points_micro"]), identity


def _open_outcome_document(
    *,
    slate_id: str,
    outcome_identity: Mapping[str, object],
    read_exact: operator.ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(outcome_identity, label=f"{slate_id} outcomes")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or hashlib.sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{slate_id} outcome exact read differs")
    try:
        document = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConstructionAllocationGradeError(
            f"{slate_id} outcome JSON differs"
        ) from exc
    if not isinstance(document, Mapping) or cross.canonical_json_bytes(
        document
    ) != raw:
        _fail(f"{slate_id} outcome canonical replay differs")
    body = {
        key: value for key, value in document.items()
        if key != "outcome_sha256"
    }
    points = document.get("player_points_micro")
    if (
        set(document) != {
            "schema_version", "slate_id", "player_points_micro", "precision",
            "outcome_sha256",
        }
        or document.get("schema_version") != OUTCOME_DOCUMENT_SCHEMA
        or document.get("slate_id") != slate_id
        or document.get("precision")
        != "integer-millionths-of-one-dk-point"
        or document.get("outcome_sha256") != cross.canonical_sha256(body)
        or not isinstance(points, Mapping)
        or not points
        or any(
            type(player_id) is not str
            or not player_id
            or type(score) is not int
            for player_id, score in points.items()
        )
    ):
        _fail(f"{slate_id} outcome document differs")
    return dict(document), identity


def _roster_score(
    roster: Sequence[object], actuals: Mapping[str, int], *, label: str,
) -> int:
    if (
        isinstance(roster, (str, bytes))
        or len(roster) != 9
        or len({str(value) for value in roster}) != 9
    ):
        _fail(f"{label} roster differs")
    missing = [str(value) for value in roster if str(value) not in actuals]
    if missing:
        _fail(f"{label} lacks realized players: " + ", ".join(missing))
    return sum(actuals[str(value)] for value in roster)


def _mean_interval(values_micro: Sequence[int]) -> dict[str, object]:
    if not values_micro:
        _fail("paired interval is empty")
    values = [int(value) / 1_000_000 for value in values_micro]
    mean = sum(values) / len(values)
    if len(values) == 1:
        half_width = 0.0
    else:
        half_width = 1.96 * stdev(values) / math.sqrt(len(values))
    return {
        "estimator": "slate-paired-mean-normal-95pct",
        "slate_count": len(values),
        "mean_points": mean,
        "lower_95_points": mean - half_width,
        "upper_95_points": mean + half_width,
        "sum_micro": sum(values_micro),
    }


def _cell(
    preset_id: str, allocation_id: str,
) -> str:
    return f"{preset_id}--{allocation_id}"


def _aggregate_weekly(
    weekly: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build the complete factor surface for one nonempty slate partition."""

    if not weekly:
        _fail("aggregate slate partition is empty")
    aggregates: list[dict[str, object]] = []
    effect_rows: list[dict[str, object]] = []
    incumbent_control = _cell(
        cross.PRESET_ORDER[0], cross.ALLOCATION_INCUMBENT
    )
    incumbent_boom = _cell(
        cross.PRESET_ORDER[0], cross.ALLOCATION_BOOM_FIRST
    )
    legality_control = _cell(
        cross.PRESET_ORDER[1], cross.ALLOCATION_INCUMBENT
    )
    legality_boom = _cell(
        cross.PRESET_ORDER[1], cross.ALLOCATION_BOOM_FIRST
    )
    for prefix in cross.PREFIXES:
        scores_by_cell: dict[str, list[int]] = {}
        regrets_by_cell: dict[str, list[int]] = {}
        for cell_id in cross.CELL_ORDER:
            scores_by_cell[cell_id] = []
            regrets_by_cell[cell_id] = []
            for weekly_row in weekly:
                try:
                    prefix_row = next(
                        row
                        for row in weekly_row["cells"][cell_id]["prefixes"]
                        if row["prefix"] == prefix
                    )
                    scores_by_cell[cell_id].append(int(
                        prefix_row["weekly_max_micro"]
                    ))
                    regrets_by_cell[cell_id].append(int(
                        prefix_row["selector_regret_micro"]
                    ))
                except (KeyError, TypeError, StopIteration, ValueError) as exc:
                    raise ConstructionAllocationGradeError(
                        "weekly aggregate grid differs"
                    ) from exc
        cell_aggregates: dict[str, dict[str, object]] = {}
        for cell_id in cross.CELL_ORDER:
            scores = scores_by_cell[cell_id]
            regrets = regrets_by_cell[cell_id]
            oracles = [score + regret for score, regret in zip(
                scores, regrets, strict=True
            )]
            cell_aggregates[cell_id] = {
                "mean_weekly_max_points": (
                    sum(scores) / len(scores) / 1_000_000
                ),
                "sum_weekly_max_micro": sum(scores),
                "mean_candidate_oracle_points": (
                    sum(oracles) / len(oracles) / 1_000_000
                ),
                "mean_selector_regret_points": (
                    sum(regrets) / len(regrets) / 1_000_000
                ),
                "thresholds": [
                    {
                        "threshold": threshold,
                        "weeks_at_or_above": sum(
                            value >= threshold * 1_000_000
                            for value in scores
                        ),
                    }
                    for threshold in cross.THRESHOLDS
                ],
            }
        allocation_incumbent_preset = [
            right - left for left, right in zip(
                scores_by_cell[incumbent_control],
                scores_by_cell[incumbent_boom],
                strict=True,
            )
        ]
        allocation_legality_preset = [
            right - left for left, right in zip(
                scores_by_cell[legality_control],
                scores_by_cell[legality_boom],
                strict=True,
            )
        ]
        construction_incumbent_allocation = [
            right - left for left, right in zip(
                scores_by_cell[incumbent_control],
                scores_by_cell[legality_control],
                strict=True,
            )
        ]
        construction_boom_allocation = [
            right - left for left, right in zip(
                scores_by_cell[incumbent_boom],
                scores_by_cell[legality_boom],
                strict=True,
            )
        ]
        did = [
            legality - incumbent for incumbent, legality in zip(
                allocation_incumbent_preset,
                allocation_legality_preset,
                strict=True,
            )
        ]
        aggregates.append({
            "prefix": prefix,
            "slate_count": len(weekly),
            "cells": cell_aggregates,
            "effects": {
                "allocation_effect_within_incumbent_preset": _mean_interval(
                    allocation_incumbent_preset
                ),
                "allocation_effect_within_legality_only_preset": _mean_interval(
                    allocation_legality_preset
                ),
                "construction_effect_within_160_40_allocation": _mean_interval(
                    construction_incumbent_allocation
                ),
                "construction_effect_within_40_160_allocation": _mean_interval(
                    construction_boom_allocation
                ),
                "difference_in_differences": _mean_interval(did),
            },
        })
        effect_rows.append({
            "prefix": prefix,
            "allocation_effect_within_incumbent_preset_micro": (
                allocation_incumbent_preset
            ),
            "allocation_effect_within_legality_only_preset_micro": (
                allocation_legality_preset
            ),
            "construction_effect_within_160_40_allocation_micro": (
                construction_incumbent_allocation
            ),
            "construction_effect_within_40_160_allocation_micro": (
                construction_boom_allocation
            ),
            "difference_in_differences_micro": did,
        })
    return aggregates, effect_rows


def grade_cross_v1(
    selection_receipt: Mapping[str, object],
    *,
    grade_id: str,
    actual_points_by_slate: Mapping[str, Mapping[object, object]],
    outcome_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Grade only after the exact four-cell selection has been frozen."""

    try:
        selection = cross.validate_score_blind_cross_v1(selection_receipt)
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionAllocationGradeError(str(exc)) from exc
    retained_grade_id = str(grade_id).strip()
    if _ID.fullmatch(retained_grade_id) is None:
        _fail("grade ID differs")
    slate_ids = [str(row["slate_id"]) for row in selection["slates"]]
    if set(actual_points_by_slate) != set(slate_ids):
        _fail("realized point slate keys differ from the frozen panel")
    if set(outcome_identities) != set(slate_ids):
        _fail("outcome identity slate keys differ from the frozen panel")

    weekly: list[dict[str, object]] = []
    for slate in selection["slates"]:
        slate_id = str(slate["slate_id"])
        actuals, outcome_identity = _bind_outcome_document(
            slate_id=slate_id,
            actual_points=actual_points_by_slate[slate_id],
            outcome_identity=outcome_identities[slate_id],
        )
        cell_scores: dict[str, dict[str, object]] = {}
        for cell_id in cross.CELL_ORDER:
            cell = slate["cells"][cell_id]
            selected_scores = [
                _roster_score(
                    roster, actuals,
                    label=f"{slate_id}/{cell_id}/selected-{ordinal}",
                )
                for ordinal, roster in enumerate(cell["selected_rosters"])
            ]
            candidate_scores = [
                _roster_score(
                    roster, actuals,
                    label=f"{slate_id}/{cell_id}/candidate-{ordinal}",
                )
                for ordinal, roster in enumerate(
                    cell["combined_candidate_rosters"]
                )
            ]
            oracle_ordinal = max(
                range(len(candidate_scores)), key=candidate_scores.__getitem__
            )
            oracle = candidate_scores[oracle_ordinal]
            prefixes = []
            for prefix in cross.PREFIXES:
                prefix_scores = selected_scores[:prefix]
                best_ordinal = max(
                    range(prefix), key=prefix_scores.__getitem__
                )
                best = prefix_scores[best_ordinal]
                prefixes.append({
                    "prefix": prefix,
                    "weekly_max_micro": best,
                    "weekly_max_points": best / 1_000_000,
                    "best_selected_ordinal": best_ordinal,
                    "best_selected_roster": cell["selected_rosters"][
                        best_ordinal
                    ],
                    "candidate_oracle_micro": oracle,
                    "candidate_oracle_points": oracle / 1_000_000,
                    "candidate_oracle_ordinal": oracle_ordinal,
                    "candidate_oracle_roster": cell[
                        "combined_candidate_rosters"
                    ][oracle_ordinal],
                    "selector_regret_micro": oracle - best,
                    "selector_regret_points": (oracle - best) / 1_000_000,
                })
            cell_scores[cell_id] = {
                "construction_preset_id": cell["construction_preset_id"],
                "allocation_id": cell["allocation_id"],
                "prefixes": prefixes,
            }
        weekly.append({
            "season": int(slate["season"]),
            "week": int(slate["week"]),
            "slate_id": slate_id,
            "outcome_identity": outcome_identity,
            "cells": cell_scores,
        })

    aggregates, effect_rows = _aggregate_weekly(weekly)
    season_aggregates = []
    for season in sorted({int(row["season"]) for row in weekly}):
        season_weekly = [
            row for row in weekly if int(row["season"]) == season
        ]
        season_results, season_vectors = _aggregate_weekly(season_weekly)
        season_aggregates.append({
            "season": season,
            "slate_count": len(season_weekly),
            "aggregate_results": season_results,
            "paired_effect_vectors": season_vectors,
        })

    k80 = next(row for row in aggregates if row["prefix"] == 80)
    report_body: dict[str, object] = {
        "schema_version": GRADE_SCHEMA,
        "grade_id": retained_grade_id,
        "selection_panel_id": selection["panel_id"],
        "selection_receipt_sha256": selection["receipt_sha256"],
        "selection_scientific_sha256": selection["scientific_sha256"],
        "cell_order": list(cross.CELL_ORDER),
        "slate_count": len(weekly),
        "prefixes": list(cross.PREFIXES),
        "thresholds": list(cross.THRESHOLDS),
        "weekly_results": weekly,
        "aggregate_results": aggregates,
        "paired_effect_vectors": effect_rows,
        "season_aggregate_results": season_aggregates,
        "primary_estimand": {
            "prefix": 80,
            "name": "allocation-by-construction-difference-in-differences",
            "formula": (
                "(legality-only 40/160 - legality-only 160/40) - "
                "(incumbent-preset 40/160 - incumbent-preset 160/40)"
            ),
            "estimate": k80["effects"]["difference_in_differences"],
        },
        "target_slate_outcomes_read_for_grading": True,
        "target_slate_outcomes_absent_during_selection": True,
        "selection_frozen_before_target_slate_outcome_join": True,
        "target_slate_outcomes_already_existed_before_replay": True,
        "selection_reopened_from_create_once_terminal": False,
        "historical_evidence_status": "descriptive-diagnostic-only",
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    return {**report_body, "report_sha256": cross.canonical_sha256(report_body)}


def grade_published_cross_v1(
    terminal_envelope: Mapping[str, object],
    *,
    read_exact: operator.ReadExact,
    grade_id: str,
    outcome_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Production grader entry: exact-reopen terminal before outcome join."""

    try:
        reopened = operator.reopen_terminal_bundle_v1(
            terminal_envelope, read_exact=read_exact
        )
    except operator.ConstructionAllocationCrossOperatorError as exc:
        raise ConstructionAllocationGradeError(str(exc)) from exc
    slate_ids = [str(row["slate_id"]) for row in reopened["selection"]["slates"]]
    if set(outcome_identities) != set(slate_ids):
        _fail("published outcome identity slate keys differ")
    actual_points_by_slate: dict[str, dict[str, str]] = {}
    normalized_identities: dict[str, dict[str, object]] = {}
    for slate_id in slate_ids:
        document, identity = _open_outcome_document(
            slate_id=slate_id,
            outcome_identity=outcome_identities[slate_id],
            read_exact=read_exact,
        )
        actual_points_by_slate[slate_id] = {
            str(player_id): str(Decimal(int(micro)) / Decimal(1_000_000))
            for player_id, micro in document["player_points_micro"].items()
        }
        normalized_identities[slate_id] = identity
    report = grade_cross_v1(
        reopened["selection"],
        grade_id=grade_id,
        actual_points_by_slate=actual_points_by_slate,
        outcome_identities=normalized_identities,
    )
    body = {
        key: value for key, value in report.items() if key != "report_sha256"
    }
    body.update({
        "selection_reopened_from_create_once_terminal": True,
        "selection_terminal_identity": reopened["terminal_envelope"][
            "terminal_identity"
        ],
        "selection_terminal_envelope_sha256": reopened[
            "terminal_envelope"
        ]["envelope_sha256"],
        "all_outcome_documents_generation_exact_reopened": True,
    })
    return {**body, "report_sha256": cross.canonical_sha256(body)}


def validate_grade_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("grade is not a mapping")
    item = dict(value)
    retained = item.pop("report_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or cross.canonical_sha256(item) != retained
        or item.get("schema_version") != GRADE_SCHEMA
        or item.get("cell_order") != list(cross.CELL_ORDER)
        or item.get("prefixes") != list(cross.PREFIXES)
        or item.get("thresholds") != list(cross.THRESHOLDS)
        or item.get("slate_count") != len(cross.EXPECTED_SLATE_IDS)
        or item.get("target_slate_outcomes_read_for_grading") is not True
        or item.get("target_slate_outcomes_absent_during_selection") is not True
        or item.get(
            "selection_frozen_before_target_slate_outcome_join"
        ) is not True
        or item.get(
            "target_slate_outcomes_already_existed_before_replay"
        ) is not True
        or item.get("historical_evidence_status")
        != "descriptive-diagnostic-only"
        or type(item.get("selection_reopened_from_create_once_terminal"))
        is not bool
        or item.get("automatic_policy_promotion") is not False
        or item.get("production_policy_authority") is not False
    ):
        _fail("grade fixed law or self-hash differs")
    if (
        _ID.fullmatch(str(item.get("grade_id", ""))) is None
        or type(item.get("selection_panel_id")) is not str
        or not item.get("selection_panel_id")
        or _SHA256.fullmatch(str(item.get(
            "selection_receipt_sha256", ""
        ))) is None
        or _SHA256.fullmatch(str(item.get(
            "selection_scientific_sha256", ""
        ))) is None
    ):
        _fail("grade selection binding differs")
    primary = item.get("primary_estimand")
    if (
        not isinstance(primary, Mapping)
        or primary.get("prefix") != 80
        or primary.get("name")
        != "allocation-by-construction-difference-in-differences"
    ):
        _fail("grade primary estimand differs")
    aggregates = item.get("aggregate_results")
    weekly = item.get("weekly_results")
    vectors = item.get("paired_effect_vectors")
    season_aggregates = item.get("season_aggregate_results")
    if (
        not isinstance(aggregates, list)
        or [row.get("prefix") for row in aggregates if isinstance(row, Mapping)]
        != list(cross.PREFIXES)
        or not isinstance(weekly, list)
        or [row.get("slate_id") for row in weekly if isinstance(row, Mapping)]
        != list(cross.EXPECTED_SLATE_IDS)
        or not isinstance(vectors, list)
        or [row.get("prefix") for row in vectors if isinstance(row, Mapping)]
        != list(cross.PREFIXES)
        or not isinstance(season_aggregates, list)
        or primary.get("estimate")
        != aggregates[-1].get("effects", {}).get("difference_in_differences")
    ):
        _fail("grade difference-in-differences binding differs")
    for expected_slate_id, weekly_row in zip(
        cross.EXPECTED_SLATE_IDS, weekly, strict=True
    ):
        if not isinstance(weekly_row, Mapping):
            _fail("grade weekly row differs")
        outcome_identity = weekly_row.get("outcome_identity")
        cells = weekly_row.get("cells")
        if (
            weekly_row.get("slate_id") != expected_slate_id
            or type(weekly_row.get("season")) is not int
            or type(weekly_row.get("week")) is not int
            or not isinstance(outcome_identity, Mapping)
            or dict(outcome_identity) != _identity(
                outcome_identity, label=f"{expected_slate_id} outcomes"
            )
            or not isinstance(cells, Mapping)
            or set(cells) != set(cross.CELL_ORDER)
        ):
            _fail("grade weekly row binding differs")
        for cell_id in cross.CELL_ORDER:
            cell = cells[cell_id]
            definition = cross.CELL_DEFINITION[cell_id]
            if (
                not isinstance(cell, Mapping)
                or cell.get("construction_preset_id")
                != definition["construction_preset_id"]
                or cell.get("allocation_id") != definition["allocation_id"]
                or not isinstance(cell.get("prefixes"), list)
                or [
                    row.get("prefix")
                    for row in cell["prefixes"]
                    if isinstance(row, Mapping)
                ] != list(cross.PREFIXES)
            ):
                _fail("grade weekly cell binding differs")
            oracle_signature: tuple[object, ...] | None = None
            for prefix_row in cell["prefixes"]:
                if not isinstance(prefix_row, Mapping):
                    _fail("grade weekly prefix row differs")
                prefix = prefix_row.get("prefix")
                best = prefix_row.get("weekly_max_micro")
                oracle = prefix_row.get("candidate_oracle_micro")
                regret = prefix_row.get("selector_regret_micro")
                best_ordinal = prefix_row.get("best_selected_ordinal")
                oracle_ordinal = prefix_row.get("candidate_oracle_ordinal")
                best_roster = prefix_row.get("best_selected_roster")
                oracle_roster = prefix_row.get("candidate_oracle_roster")
                current_oracle_signature = (
                    oracle, oracle_ordinal, oracle_roster
                )
                if oracle_signature is None:
                    oracle_signature = current_oracle_signature
                if (
                    type(prefix) is not int
                    or type(best) is not int
                    or type(oracle) is not int
                    or type(regret) is not int
                    or regret != oracle - best
                    or prefix_row.get("weekly_max_points")
                    != best / 1_000_000
                    or prefix_row.get("candidate_oracle_points")
                    != oracle / 1_000_000
                    or prefix_row.get("selector_regret_points")
                    != regret / 1_000_000
                    or type(best_ordinal) is not int
                    or not 0 <= best_ordinal < prefix
                    or type(oracle_ordinal) is not int
                    or oracle_ordinal < 0
                    or not isinstance(best_roster, list)
                    or len(best_roster) != 9
                    or len({str(value) for value in best_roster}) != 9
                    or not isinstance(oracle_roster, list)
                    or len(oracle_roster) != 9
                    or len({str(value) for value in oracle_roster}) != 9
                    or current_oracle_signature != oracle_signature
                ):
                    _fail("grade weekly score surface differs")
    expected_aggregates, expected_vectors = _aggregate_weekly(weekly)
    if aggregates != expected_aggregates or vectors != expected_vectors:
        _fail("grade paired effect/aggregate surface differs")
    expected_season_aggregates = []
    for season in sorted({int(row["season"]) for row in weekly}):
        season_weekly = [
            row for row in weekly if int(row["season"]) == season
        ]
        season_results, season_vectors = _aggregate_weekly(season_weekly)
        expected_season_aggregates.append({
            "season": season,
            "slate_count": len(season_weekly),
            "aggregate_results": season_results,
            "paired_effect_vectors": season_vectors,
        })
    if season_aggregates != expected_season_aggregates:
        _fail("grade season aggregate surface differs")
    if primary.get("estimate") != _mean_interval(
        vectors[-1]["difference_in_differences_micro"]
    ):
        _fail("grade primary difference-in-differences differs")
    return {**item, "report_sha256": retained}


def validate_published_grade_v1(value: object) -> dict[str, object]:
    report = validate_grade_v1(value)
    identity = report.get("selection_terminal_identity")
    normalized_identity = (
        _identity(identity, label="published grade terminal")
        if isinstance(identity, Mapping)
        else None
    )
    if (
        report.get("selection_reopened_from_create_once_terminal") is not True
        or not isinstance(identity, Mapping)
        or normalized_identity is None
        or dict(identity) != {**normalized_identity, "create_once": True}
        or _SHA256.fullmatch(str(report.get(
            "selection_terminal_envelope_sha256", ""
        ))) is None
        or report.get(
            "all_outcome_documents_generation_exact_reopened"
        ) is not True
    ):
        _fail("published grade terminal binding differs")
    return report


__all__ = [
    "ConstructionAllocationGradeError",
    "GRADE_SCHEMA",
    "OUTCOME_DOCUMENT_SCHEMA",
    "grade_cross_v1",
    "grade_published_cross_v1",
    "outcome_document_v1",
    "validate_grade_v1",
    "validate_published_grade_v1",
]
