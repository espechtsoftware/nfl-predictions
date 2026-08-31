"""Independent post-terminal grader for paid-source ablations.

The grader first exact-reopens a complete score-blind terminal and every child
through the operator contract.  Only then does it exact-bind a separate
realized-player-points body and join those points to the already frozen K80
books.  Historical output is descriptive mechanism evidence only and cannot
change a production policy automatically.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import re
from typing import Final

import numpy as np

from . import corpus_r6_construction_allocation_grade_operator_v1 as outcomes
from . import paid_source_ablation_operator_v1 as operator
from . import paid_source_ablation_registry_v1 as registry


GRADE_SCHEMA: Final = "paid-source-ablation-independent-grade/v1"
PREFIXES: Final = (20, 40, 80)
THRESHOLDS: Final = (194, 200, 210, 220, 230, 240)
BOOTSTRAP_SEED: Final = 20_260_830
BOOTSTRAP_RESAMPLES: Final = 10_000
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")


class PaidSourceAblationGradeV1Error(ValueError):
    """The independent post-terminal grade contract differs."""


def _fail(message: str) -> None:
    raise PaidSourceAblationGradeV1Error(message)


def _open_recognized_outcomes(
    outcome_authority_identity: Mapping[str, object],
    *,
    read_exact: operator.ReadExact,
    verify_live_lease: outcomes.HistoricalOutcomeLeaseVerifierV1,
) -> outcomes.OpenedOutcomeAuthorityV1:
    """Open only the catalog-wide authority and replay every predecessor."""

    try:
        authority = outcomes.open_recognized_outcome_authority_v1(
            outcome_authority_identity,
            read_exact=read_exact,
            verify_live_lease=verify_live_lease,
        )
    except Exception as exc:
        raise PaidSourceAblationGradeV1Error(
            "recognized outcome authority/predecessor closure differs"
        ) from exc
    if (
        authority.completion.get("schema_version")
        != outcomes.RECOGNIZED_OUTCOME_COMPLETION_SCHEMA
        or authority.closure_receipt.get("recognized_authority_only") is not True
        or authority.closure_receipt.get(
            "all_content_identities_generation_exact_reopened"
        ) is not True
        or authority.closure_receipt.get("complete") is not True
    ):
        _fail("recognized outcome authority/predecessor closure differs")
    return authority


def _verify_live_lease_unchanged(
    authority: outcomes.OpenedOutcomeAuthorityV1,
    *,
    verify_live_lease: outcomes.HistoricalOutcomeLeaseVerifierV1,
) -> None:
    try:
        receipt = verify_live_lease(
            expected_identity=authority.lease_identity,
            catalog_run_id=str(authority.completion["run_id"]),
        )
    except Exception as exc:
        raise PaidSourceAblationGradeV1Error(
            "recognized historical-outcome lease changed during grade"
        ) from exc
    if (
        not isinstance(receipt, Mapping)
        or set(receipt) != {"body", "object_receipt"}
        or receipt.get("body") != authority.lease_body
        or receipt.get("object_receipt") != authority.lease_identity
        or registry.canonical_sha256(receipt["body"])
        != authority.lease_body_sha256
    ):
        _fail("recognized historical-outcome lease changed during grade")


def _actuals_by_slate(
    authority: outcomes.OpenedOutcomeAuthorityV1,
) -> dict[str, tuple[int, int, dict[str, int]]]:
    by_ordinal: dict[int, dict[str, int]] = {
        ordinal: {} for ordinal in authority.slate_keys
    }
    for (ordinal, player_id), score in authority.player_scores.items():
        if ordinal not in by_ordinal or str(player_id) in by_ordinal[ordinal]:
            _fail("recognized outcome player/slate authority differs")
        by_ordinal[ordinal][str(player_id)] = int(score)
    result: dict[str, tuple[int, int, dict[str, int]]] = {}
    for ordinal, (season, week, slate_id) in authority.slate_keys.items():
        if slate_id in result:
            _fail("recognized outcome authority repeats a slate")
        player_scores = by_ordinal[ordinal]
        if not player_scores:
            _fail("recognized outcome authority leaves one slate empty")
        result[slate_id] = (season, week, player_scores)
    if not result:
        _fail("recognized outcome authority has no slates")
    return result


def _score_population(
    *,
    candidate_rows: Sequence[Mapping[str, object]],
    actuals: Mapping[str, int],
    label: str,
) -> tuple[dict[str, int], dict[str, object]]:
    if not candidate_rows:
        _fail(f"{label} candidate population is empty")
    candidate_ids: list[str] = []
    seen_candidate_ids: set[str] = set()
    scores: list[int] = []
    for raw_row in candidate_rows:
        if not isinstance(raw_row, Mapping):
            _fail(f"{label} candidate row differs")
        candidate_id = raw_row.get("candidate_id")
        roster = raw_row.get("player_ids")
        if (
            type(candidate_id) is not str
            or not candidate_id
            or candidate_id in seen_candidate_ids
            or not isinstance(roster, Sequence)
            or isinstance(roster, (str, bytes))
            or len(roster) != 9
            or any(type(value) is not str or not value for value in roster)
            or len({str(value) for value in roster}) != 9
        ):
            _fail(f"{label}/{candidate_id} roster differs")
        missing = [str(value) for value in roster if str(value) not in actuals]
        if missing:
            _fail(f"{label}/{candidate_id} lacks realized players")
        candidate_ids.append(candidate_id)
        seen_candidate_ids.add(candidate_id)
        scores.append(sum(actuals[str(value)] for value in roster))
    best_ordinal = max(range(len(scores)), key=scores.__getitem__)
    best = scores[best_ordinal]
    score_by_id = dict(zip(candidate_ids, scores, strict=True))
    return {
        candidate_id: score_by_id[candidate_id] for candidate_id in candidate_ids
    }, {
        "candidate_count": len(candidate_ids),
        "candidate_score_manifest_sha256": registry.canonical_sha256(scores),
        "realized_ceiling_micro": best,
        "realized_ceiling_points": best / 1_000_000,
        "best_candidate_ordinal": best_ordinal,
        "best_candidate_id": candidate_ids[best_ordinal],
        "thresholds": [
            {
                "threshold": threshold,
                "realized_lineup_count_at_or_above": sum(
                    score >= threshold * 1_000_000 for score in scores
                ),
                "realized_opportunity": best >= threshold * 1_000_000,
            }
            for threshold in THRESHOLDS
        ],
    }


def _score_book(
    *,
    selected_ids: Sequence[object],
    score_by_id: Mapping[str, int],
    label: str,
) -> dict[str, object]:
    ids = [str(value) for value in selected_ids]
    if (
        len(ids) != registry.ENTRY_BUDGET
        or len(ids) != len(set(ids))
        or any(value not in score_by_id for value in ids)
    ):
        _fail(f"{label} is not exact K80 from the scored candidate population")
    scores = [score_by_id[value] for value in ids]
    return {
        "entry_budget": registry.ENTRY_BUDGET,
        "selected_score_manifest_sha256": registry.canonical_sha256(scores),
        "prefixes": [
            _score_prefix(ids=ids, scores=scores, prefix=prefix)
            for prefix in PREFIXES
        ],
    }


def _score_admission(
    *,
    admitted_ids: Sequence[object] | None,
    score_by_id: Mapping[str, int],
    label: str,
) -> dict[str, object]:
    if admitted_ids is None:
        return {
            "available": False,
            "reason": "no-distinct-admission-stage-direct-population-to-k80-selection",
        }
    ids = [str(value) for value in admitted_ids]
    if (
        not ids
        or len(ids) != len(set(ids))
        or any(value not in score_by_id for value in ids)
    ):
        _fail(f"{label} admission does not partition the candidate population")
    scores = [score_by_id[value] for value in ids]
    best_ordinal = max(range(len(scores)), key=scores.__getitem__)
    best = scores[best_ordinal]
    return {
        "available": True,
        "admitted_candidate_count": len(ids),
        "admitted_score_manifest_sha256": registry.canonical_sha256(scores),
        "realized_ceiling_micro": best,
        "realized_ceiling_points": best / 1_000_000,
        "best_admitted_ordinal": best_ordinal,
        "best_admitted_candidate_id": ids[best_ordinal],
        "thresholds": [
            {
                "threshold": threshold,
                "realized_lineup_count_at_or_above": sum(
                    score >= threshold * 1_000_000 for score in scores
                ),
                "realized_opportunity": best >= threshold * 1_000_000,
            }
            for threshold in THRESHOLDS
        ],
    }


def _score_prefix(
    *, ids: Sequence[str], scores: Sequence[int], prefix: int,
) -> dict[str, object]:
    retained_scores = list(scores[:prefix])
    if len(retained_scores) != prefix:
        _fail("selected score prefix differs")
    best_ordinal = max(
        range(len(retained_scores)), key=retained_scores.__getitem__
    )
    best = retained_scores[best_ordinal]
    return {
        "prefix": prefix,
        "weekly_max_micro": best,
        "weekly_max_points": best / 1_000_000,
        "best_selected_ordinal": best_ordinal,
        "best_selected_candidate_id": ids[best_ordinal],
        "mean_prefix_score_micro": sum(retained_scores) / prefix,
        "thresholds": [
            {
                "threshold": threshold,
                "weekly_max_at_or_above": best >= threshold * 1_000_000,
                "selected_lineup_count_at_or_above": sum(
                    score >= threshold * 1_000_000
                    for score in retained_scores
                ),
            }
            for threshold in THRESHOLDS
        ],
    }


def _decomposition(
    *,
    candidate_pool: Mapping[str, object],
    admission: Mapping[str, object],
    selected_book: Mapping[str, object],
) -> dict[str, object]:
    selected_k80 = int(_score_prefix_from_book(selected_book, 80)[
        "weekly_max_micro"
    ])
    candidate_ceiling = int(candidate_pool["realized_ceiling_micro"])
    admission_available = admission.get("available") is True
    admitted_ceiling = (
        int(admission["realized_ceiling_micro"])
        if admission_available else None
    )
    if (
        selected_k80 > candidate_ceiling
        or (admitted_ceiling is not None and (
            admitted_ceiling > candidate_ceiling or selected_k80 > admitted_ceiling
        ))
    ):
        _fail("paid-source realized ceiling nesting differs")
    candidate_thresholds = {
        int(row["threshold"]): row for row in candidate_pool["thresholds"]
    }
    selected_thresholds = {
        int(row["threshold"]): row
        for row in _score_prefix_from_book(selected_book, 80)["thresholds"]
    }
    admitted_thresholds = (
        {int(row["threshold"]): row for row in admission["thresholds"]}
        if admission_available else {}
    )
    return {
        "candidate_pool_realized_ceiling_micro": candidate_ceiling,
        "admitted_pool_realized_ceiling_micro": admitted_ceiling,
        "selected_k80_weekly_max_micro": selected_k80,
        "selector_regret_candidate_pool_to_selected_micro": (
            candidate_ceiling - selected_k80
        ),
        "admission_regret_micro": (
            candidate_ceiling - admitted_ceiling
            if admitted_ceiling is not None else None
        ),
        "retrieval_regret_within_admission_micro": (
            admitted_ceiling - selected_k80
            if admitted_ceiling is not None else None
        ),
        "candidate_pool_ceiling_exactly_selected": selected_k80 == candidate_ceiling,
        "admitted_pool_ceiling_exactly_selected": (
            selected_k80 == admitted_ceiling
            if admitted_ceiling is not None else None
        ),
        "thresholds": [
            _threshold_conversion(
                threshold=threshold,
                candidate_row=candidate_thresholds[threshold],
                admitted_row=admitted_thresholds.get(threshold),
                selected_row=selected_thresholds[threshold],
            )
            for threshold in THRESHOLDS
        ],
    }


def _score_prefix_from_book(
    selected_book: Mapping[str, object], prefix: int,
) -> Mapping[str, object]:
    try:
        return next(
            row for row in selected_book["prefixes"]
            if isinstance(row, Mapping) and row.get("prefix") == prefix
        )
    except (KeyError, TypeError, StopIteration) as exc:
        raise PaidSourceAblationGradeV1Error(
            "selected-book prefix surface differs"
        ) from exc


def _threshold_conversion(
    *,
    threshold: int,
    candidate_row: Mapping[str, object],
    admitted_row: Mapping[str, object] | None,
    selected_row: Mapping[str, object],
) -> dict[str, object]:
    candidate_opportunity = candidate_row.get("realized_opportunity") is True
    selected_hit = selected_row.get("weekly_max_at_or_above") is True
    admitted_opportunity = (
        admitted_row.get("realized_opportunity") is True
        if admitted_row is not None else None
    )
    return {
        "threshold": threshold,
        "candidate_pool_lineup_count_at_or_above": candidate_row[
            "realized_lineup_count_at_or_above"
        ],
        "admitted_pool_lineup_count_at_or_above": (
            admitted_row["realized_lineup_count_at_or_above"]
            if admitted_row is not None else None
        ),
        "selected_book_lineup_count_at_or_above": selected_row[
            "selected_lineup_count_at_or_above"
        ],
        "candidate_pool_opportunity": candidate_opportunity,
        "admitted_pool_opportunity": admitted_opportunity,
        "selected_book_hit": selected_hit,
        "supply_to_selected_conversion": (
            selected_hit if candidate_opportunity else None
        ),
        "admission_conversion": (
            admitted_opportunity if candidate_opportunity else None
        ),
        "retrieval_conversion_within_admission": (
            selected_hit if admitted_opportunity is True else None
        ),
    }


def _bootstrap_interval(
    values: Sequence[int], *, seasons: Sequence[int], paired: bool,
) -> dict[str, object]:
    if not values or len(values) != len(seasons):
        _fail("bootstrap vector/lattice differs")
    array = np.asarray(values, dtype=np.float64) / 1_000_000
    season_array = np.asarray(seasons, dtype=np.int64)
    season_values = sorted(set(int(value) for value in season_array))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    strata: list[np.ndarray] = []
    for season in season_values:
        indices = np.flatnonzero(season_array == season)
        if not len(indices):
            _fail("bootstrap season stratum is empty")
        strata.append(rng.choice(
            indices,
            size=(BOOTSTRAP_RESAMPLES, len(indices)),
            replace=True,
        ))
    samples = array[np.concatenate(strata, axis=1)].mean(axis=1)
    mean = float(array.mean())
    return {
        "estimator": (
            "season-stratified-slate-paired-bootstrap-mean-95pct"
            if paired
            else "season-stratified-slate-bootstrap-mean-95pct"
        ),
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "slate_count": len(array),
        "season_count": len(season_values),
        "mean_points": mean,
        "lower_95_points": float(np.quantile(samples, 0.025, method="linear")),
        "upper_95_points": float(np.quantile(samples, 0.975, method="linear")),
        "sum_micro": sum(values),
    }


def _factor_effects(
    experiment_id: str,
    cell_values: Mapping[str, int],
    *,
    metric: str,
) -> dict[str, int]:
    if experiment_id == registry.ODDS_EXPERIMENT_ID:
        on, off = registry.ODDS_CELL_ORDER
        y11 = cell_values[f"{on}--{on}"]
        y10 = cell_values[f"{on}--{off}"]
        y01 = cell_values[f"{off}--{on}"]
        y00 = cell_values[f"{off}--{off}"]
        return {
            f"{metric}_generation_effect_at_retrieval_off_micro": y10 - y00,
            f"{metric}_retrieval_effect_at_generation_on_micro": y11 - y10,
            f"{metric}_interaction_micro": y11 - y10 - y01 + y00,
            f"{metric}_operational_on_on_vs_off_off_micro": y11 - y00,
        }
    on_on, off_on, on_off, off_off = registry.MATCHUP_CELL_ORDER
    y11 = cell_values[on_on]
    y01 = cell_values[off_on]
    y10 = cell_values[on_off]
    y00 = cell_values[off_off]
    return {
        f"{metric}_conditional_fantasy_points_with_sis_on_micro": y11 - y01,
        f"{metric}_conditional_sis_with_fantasy_points_on_micro": y11 - y10,
        f"{metric}_fp_by_sis_interaction_micro": y11 - y01 - y10 + y00,
        f"{metric}_operational_on_on_vs_off_off_micro": y11 - y00,
    }


def _aggregate(
    experiment_id: str, weekly: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    cell_ids = (
        [f"{population}--{selection}" for population, selection in registry.ODDS_CROSS_ORDER]
        if experiment_id == registry.ODDS_EXPERIMENT_ID
        else list(registry.MATCHUP_CELL_ORDER)
    )
    return {
        "slate_count": len(weekly),
        "prefix_results": [
            _aggregate_prefix(
                experiment_id, weekly, cell_ids=cell_ids, prefix=prefix
            )
            for prefix in PREFIXES
        ],
    }


def _prefix_row(
    cell: Mapping[str, object], *, prefix: int,
) -> Mapping[str, object]:
    selected = cell.get("selected_book")
    if not isinstance(selected, Mapping):
        _fail("paid-source selected-book surface differs")
    return _score_prefix_from_book(selected, prefix)


def _cell_threshold(
    cell: Mapping[str, object], *, threshold: int, prefix: int,
) -> Mapping[str, object]:
    try:
        candidate_row = next(
            row for row in cell["candidate_pool"]["thresholds"]
            if isinstance(row, Mapping) and row.get("threshold") == threshold
        )
        admission = cell["admission"]
        admitted_row = (
            next(
                row for row in admission["thresholds"]
                if isinstance(row, Mapping) and row.get("threshold") == threshold
            )
            if admission.get("available") is True else None
        )
        selected_row = next(
            row for row in _prefix_row(cell, prefix=prefix)["thresholds"]
            if isinstance(row, Mapping) and row.get("threshold") == threshold
        )
    except (KeyError, TypeError, StopIteration) as exc:
        raise PaidSourceAblationGradeV1Error(
            "paid-source threshold conversion surface differs"
        ) from exc
    return _threshold_conversion(
        threshold=threshold,
        candidate_row=candidate_row,
        admitted_row=admitted_row,
        selected_row=selected_row,
    )


def _metric_summary(
    values: Sequence[int], *, seasons: Sequence[int],
    mean_field: str, sum_field: str,
) -> dict[str, object]:
    interval = _bootstrap_interval(values, seasons=seasons, paired=False)
    return {
        mean_field: interval["mean_points"],
        sum_field: interval["sum_micro"],
        "bootstrap_mean_interval_95": interval,
    }


def _conversion_summary(
    rows: Sequence[Mapping[str, object]], *, threshold: int,
) -> dict[str, object]:
    candidate_opportunities = sum(
        row["candidate_pool_opportunity"] is True for row in rows
    )
    admitted_supported = all(
        row["admitted_pool_opportunity"] is not None for row in rows
    )
    admitted_opportunities = (
        sum(row["admitted_pool_opportunity"] is True for row in rows)
        if admitted_supported else None
    )
    supply_converted = sum(
        row["supply_to_selected_conversion"] is True for row in rows
    )
    admission_converted = (
        sum(row["admission_conversion"] is True for row in rows)
        if admitted_supported else None
    )
    retrieval_converted = (
        sum(
            row["retrieval_conversion_within_admission"] is True for row in rows
        )
        if admitted_supported else None
    )
    return {
        "threshold": threshold,
        "candidate_pool_realized_lineup_count_at_or_above": sum(
            int(row["candidate_pool_lineup_count_at_or_above"])
            for row in rows
        ),
        "admitted_pool_realized_lineup_count_at_or_above": (
            sum(int(row["admitted_pool_lineup_count_at_or_above"]) for row in rows)
            if admitted_supported else None
        ),
        "selected_book_realized_lineup_count_at_or_above": sum(
            int(row["selected_book_lineup_count_at_or_above"])
            for row in rows
        ),
        "candidate_pool_opportunity_weeks": candidate_opportunities,
        "admitted_pool_opportunity_weeks": admitted_opportunities,
        "selected_book_hit_weeks": sum(
            row["selected_book_hit"] is True for row in rows
        ),
        "supply_to_selected_converted_weeks": supply_converted,
        "supply_to_selected_conversion_rate": (
            supply_converted / candidate_opportunities
            if candidate_opportunities else None
        ),
        "admission_conversion_supported": admitted_supported,
        "admission_converted_weeks": admission_converted,
        "admission_conversion_rate": (
            admission_converted / candidate_opportunities
            if admitted_supported and candidate_opportunities else None
        ),
        "retrieval_converted_weeks_within_admission": retrieval_converted,
        "retrieval_conversion_rate_within_admission": (
            retrieval_converted / admitted_opportunities
            if admitted_supported and admitted_opportunities else None
        ),
    }


def _aggregate_prefix(
    experiment_id: str,
    weekly: Sequence[Mapping[str, object]],
    *,
    cell_ids: Sequence[str],
    prefix: int,
) -> dict[str, object]:
    if not weekly:
        _fail("paid-source aggregate partition is empty")
    seasons = [int(row["season"]) for row in weekly]
    cells = {
        cell_id: {
            "candidate_supply": _metric_summary([
                int(row["cells"][cell_id]["candidate_pool"][
                    "realized_ceiling_micro"
                ])
                for row in weekly
            ], seasons=seasons,
                mean_field="mean_candidate_pool_realized_ceiling_points",
                sum_field="sum_candidate_pool_realized_ceiling_micro",
            ),
            "selected_book": _metric_summary([
                int(_prefix_row(row["cells"][cell_id], prefix=prefix)[
                    "weekly_max_micro"
                ])
                for row in weekly
            ], seasons=seasons,
                mean_field="mean_selected_weekly_max_points",
                sum_field="sum_selected_weekly_max_micro",
            ),
            "selector_regret_candidate_pool_to_selected": _metric_summary([
                int(row["cells"][cell_id]["candidate_pool"][
                    "realized_ceiling_micro"
                ]) - int(_prefix_row(row["cells"][cell_id], prefix=prefix)[
                    "weekly_max_micro"
                ])
                for row in weekly
            ], seasons=seasons,
                mean_field="mean_selector_regret_points",
                sum_field="sum_selector_regret_micro",
            ),
            "admission": _aggregate_admission(
                weekly, cell_id=cell_id, prefix=prefix, seasons=seasons
            ),
            "thresholds": [
                _conversion_summary(
                    [
                        _cell_threshold(
                            row["cells"][cell_id],
                            threshold=threshold,
                            prefix=prefix,
                        )
                        for row in weekly
                    ],
                    threshold=threshold,
                )
                for threshold in THRESHOLDS
            ],
        }
        for cell_id in cell_ids
    }
    weekly_effect_rows = [
        next(
            row for row in weekly_row["effects_by_prefix"]
            if row["prefix"] == prefix
        ) for weekly_row in weekly
    ]
    effect_vectors: dict[str, dict[str, list[int]]] = {
        family: {
            effect: [int(row[family][effect]) for row in weekly_effect_rows]
            for effect in weekly_effect_rows[0][family]
        }
        for family in (
            "candidate_supply_effects",
            "selected_book_effects",
            "selector_regret_effects",
        )
    }
    return {
        "prefix": prefix,
        "cells": cells,
        "paired_effects": {
            family: {
                effect: _bootstrap_interval(
                    values, seasons=seasons, paired=True
                )
                for effect, values in vectors.items()
            }
            for family, vectors in effect_vectors.items()
        },
        "paired_effect_vectors_micro": effect_vectors,
    }


def _aggregate_admission(
    weekly: Sequence[Mapping[str, object]],
    *,
    cell_id: str,
    prefix: int,
    seasons: Sequence[int],
) -> dict[str, object]:
    admissions = [row["cells"][cell_id]["admission"] for row in weekly]
    supported = all(row.get("available") is True for row in admissions)
    if not supported:
        if any(row.get("available") is not False for row in admissions):
            _fail("paid-source admission availability differs across slates")
        return {
            "available": False,
            "reason": "no-distinct-admission-stage-direct-population-to-k80-selection",
        }
    admitted = [int(row["realized_ceiling_micro"]) for row in admissions]
    selected = [
        int(_prefix_row(row["cells"][cell_id], prefix=prefix)["weekly_max_micro"])
        for row in weekly
    ]
    candidate = [
        int(row["cells"][cell_id]["candidate_pool"]["realized_ceiling_micro"])
        for row in weekly
    ]
    return {
        "available": True,
        "admitted_pool_realized_ceiling": _metric_summary(
            admitted,
            seasons=seasons,
            mean_field="mean_admitted_pool_realized_ceiling_points",
            sum_field="sum_admitted_pool_realized_ceiling_micro",
        ),
        "admission_regret_candidate_to_admitted": _metric_summary(
            [left - right for left, right in zip(candidate, admitted, strict=True)],
            seasons=seasons,
            mean_field="mean_admission_regret_points",
            sum_field="sum_admission_regret_micro",
        ),
        "retrieval_regret_admitted_to_selected": _metric_summary(
            [left - right for left, right in zip(admitted, selected, strict=True)],
            seasons=seasons,
            mean_field="mean_retrieval_regret_points",
            sum_field="sum_retrieval_regret_micro",
        ),
    }


def grade_paid_source_terminal_v1(
    terminal_envelope: Mapping[str, object],
    *,
    read_exact: operator.ReadExact,
    verify_live_lease: outcomes.HistoricalOutcomeLeaseVerifierV1,
    grade_id: str,
    outcome_authority_identity: Mapping[str, object],
    terminal_reopen: Callable[..., Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Exact-reopen frozen books, then open the recognized outcome closure."""

    retained_reopener = terminal_reopen or operator.reopen_paid_source_terminal_v1
    if not callable(retained_reopener):
        _fail("score-free terminal reopener differs")
    reopened = retained_reopener(terminal_envelope, read_exact=read_exact)
    retained_grade_id = str(grade_id).strip()
    if _ID.fullmatch(retained_grade_id) is None:
        _fail("grade ID differs")
    authority = _open_recognized_outcomes(
        outcome_authority_identity,
        read_exact=read_exact,
        verify_live_lease=verify_live_lease,
    )
    experiment_id = str(reopened["terminal"]["experiment_id"])
    actual_slates = _actuals_by_slate(authority)
    evidence = reopened["slate_evidence"]
    evidence_slate_ids = [str(row["slate"]["slate_id"]) for row in evidence]
    if (
        len(evidence_slate_ids) != len(set(evidence_slate_ids))
        or any(slate_id not in actual_slates for slate_id in evidence_slate_ids)
    ):
        _fail("frozen terminal slate keys differ from recognized outcomes")

    weekly: list[dict[str, object]] = []
    for slate in evidence:
        slate_id = str(slate["slate"]["slate_id"])
        outcome_season, outcome_week, actuals = actual_slates[slate_id]
        if (
            outcome_season != slate["slate"]["season"]
            or outcome_week != slate["slate"]["week"]
        ):
            _fail("outcome slate lattice differs")
        cells: dict[str, dict[str, object]] = {}
        if experiment_id == registry.ODDS_EXPERIMENT_ID:
            for output in slate["cell_outputs"]:
                cell_id = (
                    f"{output['population_cell_id']}--"
                    f"{output['selection_world_cell_id']}"
                )
                score_by_id, candidate_pool = _score_population(
                    candidate_rows=output["candidate_population_body"][
                        "candidate_rows"
                    ],
                    actuals=actuals,
                    label=f"{slate_id}/{cell_id}",
                )
                selected_book = _score_book(
                    selected_ids=output["selected_book_body"]["selected_lineup_ids"],
                    score_by_id=score_by_id,
                    label=f"{slate_id}/{cell_id}",
                )
                admission = _score_admission(
                    admitted_ids=None,
                    score_by_id=score_by_id,
                    label=f"{slate_id}/{cell_id}",
                )
                cells[cell_id] = {
                    "candidate_pool": candidate_pool,
                    "admission": admission,
                    "selected_book": selected_book,
                    "k80_decomposition": _decomposition(
                        candidate_pool=candidate_pool,
                        admission=admission,
                        selected_book=selected_book,
                    ),
                }
        else:
            score_by_id, candidate_pool = _score_population(
                candidate_rows=slate["accepted_candidate_artifact_body"]["rows"],
                actuals=actuals,
                label=f"{slate_id}/shared-candidate-population",
            )
            for cell in slate["cells"]:
                cell_id = str(cell["cell"]["cell_id"])
                selected_book = _score_book(
                    selected_ids=cell["retrieval"]["selected_k80_candidate_ids"],
                    score_by_id=score_by_id,
                    label=f"{slate_id}/{cell_id}",
                )
                admission = _score_admission(
                    admitted_ids=cell["retrieval"]["admitted_candidate_ids"],
                    score_by_id=score_by_id,
                    label=f"{slate_id}/{cell_id}",
                )
                cells[cell_id] = {
                    "candidate_pool": candidate_pool,
                    "admission": admission,
                    "selected_book": selected_book,
                    "k80_decomposition": _decomposition(
                        candidate_pool=candidate_pool,
                        admission=admission,
                        selected_book=selected_book,
                    ),
                }
        weekly.append({
            "slate_id": slate_id,
            "season": int(slate["slate"]["season"]),
            "week": int(slate["slate"]["week"]),
            "cells": cells,
            "effects_by_prefix": [
                {
                    "prefix": prefix,
                    "candidate_supply_effects": _factor_effects(
                        experiment_id,
                        {
                            cell_id: int(result["candidate_pool"][
                                "realized_ceiling_micro"
                            ])
                            for cell_id, result in cells.items()
                        },
                        metric="candidate_supply",
                    ),
                    "selected_book_effects": _factor_effects(experiment_id, {
                        cell_id: int(_prefix_row(
                            result, prefix=prefix
                        )["weekly_max_micro"])
                        for cell_id, result in cells.items()
                    }, metric="selected_book"),
                    "selector_regret_effects": _factor_effects(experiment_id, {
                        cell_id: (
                            int(result["candidate_pool"]["realized_ceiling_micro"])
                            - int(_prefix_row(
                                result, prefix=prefix
                            )["weekly_max_micro"])
                        )
                        for cell_id, result in cells.items()
                    }, metric="selector_regret"),
                }
                for prefix in PREFIXES
            ],
        })
    aggregate = _aggregate(experiment_id, weekly)
    season_aggregates = [
        {
            "season": season,
            "aggregate": _aggregate(
                experiment_id,
                [row for row in weekly if row["season"] == season],
            ),
        }
        for season in sorted({int(row["season"]) for row in weekly})
    ]
    _verify_live_lease_unchanged(
        authority, verify_live_lease=verify_live_lease
    )
    body: dict[str, object] = {
        "schema_version": GRADE_SCHEMA,
        "grade_id": retained_grade_id,
        "experiment_id": experiment_id,
        "terminal_identity": reopened["terminal_envelope"]["terminal_identity"],
        "terminal_sha256": reopened["terminal"]["terminal_sha256"],
        "recognized_outcome_completion_identity": authority.completion_identity,
        "recognized_outcome_completion_sha256": authority.completion[
            "completion_sha256"
        ],
        "recognized_outcome_snapshot_identity": authority.snapshot_identity,
        "recognized_outcome_snapshot_sha256": authority.snapshot[
            "outcome_snapshot_sha256"
        ],
        "outcome_predecessor_closure_sha256": authority.closure_receipt[
            "closure_sha256"
        ],
        "historical_outcome_lease_identity": authority.lease_identity,
        "historical_outcome_lease_body_sha256": authority.lease_body_sha256,
        "historical_outcome_lease_unchanged_through_grade": True,
        "historical_outcome_lease_release_owner": "external-launcher-watcher",
        "additional_historical_outcome_read": False,
        "outcome_authority_and_all_predecessors_generation_exact_reopened": True,
        "slate_count": len(weekly),
        "entry_budget": registry.ENTRY_BUDGET,
        "prefixes": list(PREFIXES),
        "thresholds": list(THRESHOLDS),
        "weekly_results": weekly,
        "weekly_result_manifest_sha256": registry.canonical_sha256(weekly),
        "aggregate": aggregate,
        "season_aggregates": season_aggregates,
        "multiplicity_family": (
            "odds-prop-override-two-cell-family"
            if experiment_id == registry.ODDS_EXPERIMENT_ID
            else "fantasy-points-by-sis-four-cell-family"
        ),
        "multiplicity_status": "reported-separately-no-cross-family-pooling",
        "factor_formula_contract": (
            "odds:each named metric uses y11-y10-y01+y00; generation="
            "y10-y00; retrieval=y11-y10; operational=y11-y00"
            if experiment_id == registry.ODDS_EXPERIMENT_ID
            else "fp-by-sis:each named metric uses y11-y01-y10+y00; "
            "conditional-fp=y11-y01; conditional-sis=y11-y10; "
            "operational=y11-y00"
        ),
        "metric_semantics": {
            "candidate_supply": "realized maximum over every frozen candidate",
            "selected_book": "realized maximum over the frozen ordered K prefix",
            "selector_regret": "candidate-supply ceiling minus selected-book maximum",
            "admission": (
                "not-present-in-odds-direct-population-to-selection-cross"
                if experiment_id == registry.ODDS_EXPERIMENT_ID
                else "realized maximum over the frozen matchup-admitted subset"
            ),
        },
        "selection_terminal_exact_reopened_before_outcome_join": True,
        "selection_frozen_before_outcome_join": True,
        "outcomes_read_during_selection": False,
        "uses_realized_outcomes_for_grade": True,
        "historical_evidence_status": "descriptive-mechanism-diagnostic-only",
        "automatic_policy_promotion": False,
        **{field: False for field in registry.FALSE_AUTHORITY_FIELDS},
    }
    body["grade_sha256"] = registry.canonical_sha256(body)
    return validate_paid_source_grade_v1(body)


def validate_paid_source_grade_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("paid-source grade is not a mapping")
    item = dict(value)
    retained = item.pop("grade_sha256", None)
    expected_fields = set(registry.FALSE_AUTHORITY_FIELDS) | {
        "schema_version",
        "grade_id",
        "experiment_id",
        "terminal_identity",
        "terminal_sha256",
        "recognized_outcome_completion_identity",
        "recognized_outcome_completion_sha256",
        "recognized_outcome_snapshot_identity",
        "recognized_outcome_snapshot_sha256",
        "outcome_predecessor_closure_sha256",
        "historical_outcome_lease_identity",
        "historical_outcome_lease_body_sha256",
        "historical_outcome_lease_unchanged_through_grade",
        "historical_outcome_lease_release_owner",
        "additional_historical_outcome_read",
        "outcome_authority_and_all_predecessors_generation_exact_reopened",
        "slate_count",
        "entry_budget",
        "prefixes",
        "thresholds",
        "weekly_results",
        "weekly_result_manifest_sha256",
        "aggregate",
        "season_aggregates",
        "multiplicity_family",
        "multiplicity_status",
        "factor_formula_contract",
        "metric_semantics",
        "selection_terminal_exact_reopened_before_outcome_join",
        "selection_frozen_before_outcome_join",
        "outcomes_read_during_selection",
        "uses_realized_outcomes_for_grade",
        "historical_evidence_status",
        "automatic_policy_promotion",
    }
    if (
        not registry.is_sha256(retained)
        or registry.canonical_sha256(item) != retained
        or set(item) != expected_fields
        or item.get("schema_version") != GRADE_SCHEMA
        or item.get("experiment_id") not in {
            registry.ODDS_EXPERIMENT_ID,
            registry.MATCHUP_EXPERIMENT_ID,
        }
        or item.get("entry_budget") != registry.ENTRY_BUDGET
        or item.get("prefixes") != list(PREFIXES)
        or item.get("thresholds") != list(THRESHOLDS)
        or item.get(
            "outcome_authority_and_all_predecessors_generation_exact_reopened"
        ) is not True
        or item.get("historical_outcome_lease_unchanged_through_grade") is not True
        or item.get("historical_outcome_lease_release_owner")
        != "external-launcher-watcher"
        or item.get("additional_historical_outcome_read") is not False
        or item.get("selection_terminal_exact_reopened_before_outcome_join") is not True
        or item.get("selection_frozen_before_outcome_join") is not True
        or item.get("outcomes_read_during_selection") is not False
        or item.get("uses_realized_outcomes_for_grade") is not True
        or item.get("historical_evidence_status")
        != "descriptive-mechanism-diagnostic-only"
        or item.get("automatic_policy_promotion") is not False
    ):
        _fail("paid-source grade policy differs")
    if (
        _ID.fullmatch(str(item.get("grade_id"))) is None
        or not registry.is_sha256(item.get("terminal_sha256"))
        or not registry.is_sha256(
            item.get("recognized_outcome_completion_sha256")
        )
        or not registry.is_sha256(
            item.get("recognized_outcome_snapshot_sha256")
        )
        or not registry.is_sha256(item.get("outcome_predecessor_closure_sha256"))
        or not registry.is_sha256(
            item.get("historical_outcome_lease_body_sha256")
        )
    ):
        _fail("paid-source grade identities differ")
    _validate_identity(item.get("terminal_identity"), require_create_once=True)
    _validate_identity(item.get("recognized_outcome_completion_identity"))
    _validate_identity(item.get("recognized_outcome_snapshot_identity"))
    _validate_identity(item.get("historical_outcome_lease_identity"))
    weekly = item.get("weekly_results")
    if (
        not isinstance(weekly, Sequence)
        or isinstance(weekly, (str, bytes))
        or not weekly
        or item.get("slate_count") != len(weekly)
        or item.get("weekly_result_manifest_sha256")
        != registry.canonical_sha256(weekly)
        or len({str(row.get("slate_id")) for row in weekly}) != len(weekly)
    ):
        _fail("paid-source weekly grade manifest differs")
    experiment_id = str(item["experiment_id"])
    expected_cell_ids = (
        [
            f"{population}--{selection}"
            for population, selection in registry.ODDS_CROSS_ORDER
        ]
        if experiment_id == registry.ODDS_EXPERIMENT_ID
        else list(registry.MATCHUP_CELL_ORDER)
    )
    for row in weekly:
        if (
            not isinstance(row, Mapping)
            or set(row) != {
                "slate_id", "season", "week", "cells", "effects_by_prefix"
            }
            or list(row["cells"]) != expected_cell_ids
            or not isinstance(row.get("effects_by_prefix"), Sequence)
            or [
                effect_row.get("prefix")
                for effect_row in row["effects_by_prefix"]
                if isinstance(effect_row, Mapping)
            ] != list(PREFIXES)
        ):
            _fail("paid-source weekly grade row differs")
        for cell in row["cells"].values():
            if (
                not isinstance(cell, Mapping)
                or set(cell) != {
                    "candidate_pool", "admission", "selected_book",
                    "k80_decomposition",
                }
            ):
                _fail("paid-source weekly cell grade differs")
            _validate_candidate_pool(cell["candidate_pool"])
            _validate_admission(cell["admission"])
            _validate_selected_book(cell["selected_book"])
            expected_decomposition = _decomposition(
                candidate_pool=cell["candidate_pool"],
                admission=cell["admission"],
                selected_book=cell["selected_book"],
            )
            if cell["k80_decomposition"] != expected_decomposition:
                _fail("paid-source K80 decomposition differs")
        for effect_row in row["effects_by_prefix"]:
            prefix = effect_row["prefix"]
            expected_effect_row = {
                "prefix": prefix,
                "candidate_supply_effects": _factor_effects(
                    experiment_id,
                    {
                        str(cell_id): int(cell["candidate_pool"][
                            "realized_ceiling_micro"
                        ]) for cell_id, cell in row["cells"].items()
                    },
                    metric="candidate_supply",
                ),
                "selected_book_effects": _factor_effects(
                    experiment_id,
                    {
                        str(cell_id): int(_prefix_row(
                            cell, prefix=prefix
                        )["weekly_max_micro"])
                        for cell_id, cell in row["cells"].items()
                    },
                    metric="selected_book",
                ),
                "selector_regret_effects": _factor_effects(
                    experiment_id,
                    {
                        str(cell_id): (
                            int(cell["candidate_pool"]["realized_ceiling_micro"])
                            - int(_prefix_row(
                                cell, prefix=prefix
                            )["weekly_max_micro"])
                        )
                        for cell_id, cell in row["cells"].items()
                    },
                    metric="selector_regret",
                ),
            }
            if effect_row != expected_effect_row:
                _fail("paid-source weekly factor effects differ")
    expected_aggregate = _aggregate(experiment_id, weekly)
    expected_seasons = [
        {
            "season": season,
            "aggregate": _aggregate(
                experiment_id,
                [row for row in weekly if row["season"] == season],
            ),
        }
        for season in sorted({int(row["season"]) for row in weekly})
    ]
    expected_formula = (
        "odds:each named metric uses y11-y10-y01+y00; generation="
        "y10-y00; retrieval=y11-y10; operational=y11-y00"
        if experiment_id == registry.ODDS_EXPERIMENT_ID
        else "fp-by-sis:each named metric uses y11-y01-y10+y00; "
        "conditional-fp=y11-y01; conditional-sis=y11-y10; "
        "operational=y11-y00"
    )
    expected_family = (
        "odds-prop-override-two-cell-family"
        if experiment_id == registry.ODDS_EXPERIMENT_ID
        else "fantasy-points-by-sis-four-cell-family"
    )
    if (
        item.get("aggregate") != expected_aggregate
        or item.get("season_aggregates") != expected_seasons
        or item.get("factor_formula_contract") != expected_formula
        or item.get("multiplicity_family") != expected_family
        or item.get("multiplicity_status")
        != "reported-separately-no-cross-family-pooling"
        or item.get("metric_semantics") != {
            "candidate_supply": "realized maximum over every frozen candidate",
            "selected_book": "realized maximum over the frozen ordered K prefix",
            "selector_regret": "candidate-supply ceiling minus selected-book maximum",
            "admission": (
                "not-present-in-odds-direct-population-to-selection-cross"
                if experiment_id == registry.ODDS_EXPERIMENT_ID
                else "realized maximum over the frozen matchup-admitted subset"
            ),
        }
    ):
        _fail("paid-source aggregate differs")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("paid-source grade claims automatic downstream authority")
    return {**item, "grade_sha256": retained}


def _validate_identity(value: object, *, require_create_once: bool = False) -> None:
    if not isinstance(value, Mapping):
        _fail("paid-source grade identity differs")
    expected = {"uri", "generation", "sha256", "bytes"}
    if require_create_once or value.get("create_once") is True:
        expected.add("create_once")
    if (
        set(value) != expected
        or type(value.get("uri")) is not str
        or not value.get("uri")
        or type(value.get("generation")) is not str
        or not value.get("generation")
        or not registry.is_sha256(value.get("sha256"))
        or type(value.get("bytes")) is not int
        or value.get("bytes") <= 0
        or (require_create_once and value.get("create_once") is not True)
    ):
        _fail("paid-source grade identity differs")


def _validate_candidate_pool(value: object) -> None:
    if not isinstance(value, Mapping):
        _fail("paid-source candidate-pool grade differs")
    count = value.get("candidate_count")
    ceiling = value.get("realized_ceiling_micro")
    ordinal = value.get("best_candidate_ordinal")
    thresholds = value.get("thresholds")
    if (
        set(value) != {
            "candidate_count", "candidate_score_manifest_sha256",
            "realized_ceiling_micro", "realized_ceiling_points",
            "best_candidate_ordinal", "best_candidate_id", "thresholds",
        }
        or type(count) is not int or count <= 0
        or not registry.is_sha256(value.get("candidate_score_manifest_sha256"))
        or type(ceiling) is not int
        or value.get("realized_ceiling_points") != ceiling / 1_000_000
        or type(ordinal) is not int or not 0 <= ordinal < count
        or type(value.get("best_candidate_id")) is not str
        or not value.get("best_candidate_id")
        or not _valid_opportunity_thresholds(
            thresholds, maximum=ceiling, maximum_count=count
        )
    ):
        _fail("paid-source candidate-pool grade differs")


def _validate_admission(value: object) -> None:
    if not isinstance(value, Mapping):
        _fail("paid-source admission grade differs")
    if value.get("available") is False:
        if value != {
            "available": False,
            "reason": "no-distinct-admission-stage-direct-population-to-k80-selection",
        }:
            _fail("paid-source unavailable-admission grade differs")
        return
    count = value.get("admitted_candidate_count")
    ceiling = value.get("realized_ceiling_micro")
    ordinal = value.get("best_admitted_ordinal")
    if (
        value.get("available") is not True
        or set(value) != {
            "available", "admitted_candidate_count",
            "admitted_score_manifest_sha256", "realized_ceiling_micro",
            "realized_ceiling_points", "best_admitted_ordinal",
            "best_admitted_candidate_id", "thresholds",
        }
        or type(count) is not int or count < registry.ENTRY_BUDGET
        or not registry.is_sha256(value.get("admitted_score_manifest_sha256"))
        or type(ceiling) is not int
        or value.get("realized_ceiling_points") != ceiling / 1_000_000
        or type(ordinal) is not int or not 0 <= ordinal < count
        or type(value.get("best_admitted_candidate_id")) is not str
        or not value.get("best_admitted_candidate_id")
        or not _valid_opportunity_thresholds(
            value.get("thresholds"), maximum=ceiling, maximum_count=count
        )
    ):
        _fail("paid-source admission grade differs")


def _valid_opportunity_thresholds(
    value: object, *, maximum: int, maximum_count: int,
) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and [row.get("threshold") for row in value if isinstance(row, Mapping)]
        == list(THRESHOLDS)
        and all(
            isinstance(row, Mapping)
            and set(row) == {
                "threshold", "realized_lineup_count_at_or_above",
                "realized_opportunity",
            }
            and type(row.get("realized_lineup_count_at_or_above")) is int
            and 0 <= row["realized_lineup_count_at_or_above"] <= maximum_count
            and type(row.get("realized_opportunity")) is bool
            and row["realized_opportunity"] is (
                maximum >= row["threshold"] * 1_000_000
            )
            for row in value
        )
    )


def _validate_selected_book(value: object) -> None:
    if not isinstance(value, Mapping):
        _fail("paid-source selected-book grade differs")
    prefixes = value.get("prefixes")
    if (
        set(value) != {
            "entry_budget", "selected_score_manifest_sha256", "prefixes"
        }
        or value.get("entry_budget") != registry.ENTRY_BUDGET
        or not registry.is_sha256(value.get("selected_score_manifest_sha256"))
        or not isinstance(prefixes, Sequence)
        or isinstance(prefixes, (str, bytes))
        or [row.get("prefix") for row in prefixes if isinstance(row, Mapping)]
        != list(PREFIXES)
    ):
        _fail("paid-source selected-book grade differs")
    previous_maximum: int | None = None
    for prefix_row in prefixes:
        prefix = prefix_row.get("prefix")
        weekly_max = prefix_row.get("weekly_max_micro")
        ordinal = prefix_row.get("best_selected_ordinal")
        thresholds = prefix_row.get("thresholds")
        if (
            not isinstance(prefix_row, Mapping)
            or set(prefix_row) != {
                "prefix", "weekly_max_micro", "weekly_max_points",
                "best_selected_ordinal", "best_selected_candidate_id",
                "mean_prefix_score_micro", "thresholds",
            }
            or prefix not in PREFIXES
            or type(weekly_max) is not int
            or prefix_row.get("weekly_max_points") != weekly_max / 1_000_000
            or type(ordinal) is not int or not 0 <= ordinal < prefix
            or type(prefix_row.get("best_selected_candidate_id")) is not str
            or not prefix_row.get("best_selected_candidate_id")
            or type(prefix_row.get("mean_prefix_score_micro")) not in {int, float}
            or not isinstance(thresholds, Sequence)
            or [row.get("threshold") for row in thresholds if isinstance(row, Mapping)]
            != list(THRESHOLDS)
            or any(
                not isinstance(row, Mapping)
                or set(row) != {
                    "threshold", "weekly_max_at_or_above",
                    "selected_lineup_count_at_or_above",
                }
                or type(row.get("weekly_max_at_or_above")) is not bool
                or type(row.get("selected_lineup_count_at_or_above")) is not int
                or not 0 <= row["selected_lineup_count_at_or_above"] <= prefix
                or row["weekly_max_at_or_above"] is not (
                    weekly_max >= row["threshold"] * 1_000_000
                )
                for row in thresholds
            )
            or (previous_maximum is not None and weekly_max < previous_maximum)
        ):
            _fail("paid-source selected-book prefix grade differs")
        previous_maximum = weekly_max


__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "GRADE_SCHEMA",
    "PaidSourceAblationGradeV1Error",
    "PREFIXES",
    "THRESHOLDS",
    "grade_paid_source_terminal_v1",
    "validate_paid_source_grade_v1",
]
