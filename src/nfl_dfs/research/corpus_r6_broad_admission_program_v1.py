"""Pure 54-slate coordinator for the fixed-corpus admission tournament.

The score-free seam freezes both admission budgets before any outcomes are
available.  Historical grading then requires the complete 2023--2025 lattice,
fits the direct arm strictly walk-forward, and reports descriptive retention
only.  It cannot generate candidates, select K80, or promote a production
policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_broad_admission_tournament_v1 as core
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_controller_v1 as score_free,
)


VERSION: Final = "corpus-r6-broad-admission-program-v1"
SLATE_PACKAGE_SCHEMA: Final = (
    "corpus-r6-broad-admission-score-free-slate-package/v1"
)
PROGRAM_GRADE_SCHEMA: Final = (
    "corpus-r6-broad-admission-historical-program-grade/v1"
)
EXPECTED_SLATE_IDS: Final = tuple(
    f"{season}-w{week:02d}"
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)
_MICRO: Final = 1_000_000
_PACKAGE_FIELDS: Final = frozenset({
    "schema_version", "version", "source_ordinal", "slate", "slate_id",
    "slate_freeze", "slate_freeze_sha256", "candidate_count",
    "admission_budgets", "budget_packages", "budget_packages_sha256",
    "uses_realized_outcomes", "direct_admission_included",
    "candidate_generation_performed", "k80_selection_performed",
    "full_union_oracle_is_training_target", "automatic_policy_promotion",
    "production_change_licensed", "package_sha256",
})
_BUDGET_PACKAGE_FIELDS: Final = frozenset({
    "admission_budget", "reference_admission", "reference_admission_sha256",
    "quota_admission", "quota_admission_sha256", "quota_blend",
    "quota_blend_sha256", "total_admission_budget_held_fixed",
    "uses_realized_outcomes", "direct_admission_included",
    "automatic_policy_promotion", "budget_package_sha256",
})


class CorpusR6BroadAdmissionProgramV1Error(ValueError):
    """The fixed historical admission program contract differed."""


def _fail(message: str) -> None:
    raise CorpusR6BroadAdmissionProgramV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _hash(value: object) -> str:
    return batch.canonical_sha256(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} is already present")
    body = dict(value)
    return {**body, field: _hash(body)}


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    if value.get(field) != _hash({
        key: child for key, child in value.items() if key != field
    }):
        _fail(f"{label} self-hash differs")


def _expected_slate(source_ordinal: object) -> str:
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < len(EXPECTED_SLATE_IDS)
    ):
        _fail("source ordinal is outside the exact 54-slate lattice")
    return EXPECTED_SLATE_IDS[source_ordinal]


def _budget_package(
    *, slate_freeze: Mapping[str, object], budget: int,
) -> dict[str, object]:
    reference = core.build_reference_admission_v1(slate_freeze, budget=budget)
    quota = core.build_quota_admission_v1(slate_freeze, budget=budget)
    blend = core.build_fixed_budget_reference_challenger_blend_v1(
        slate_freeze=slate_freeze,
        reference_admission=reference,
        challenger_admission=quota,
    )
    return _with_hash({
        "admission_budget": budget,
        "reference_admission": reference,
        "reference_admission_sha256": reference["admission_sha256"],
        "quota_admission": quota,
        "quota_admission_sha256": quota["admission_sha256"],
        "quota_blend": blend,
        "quota_blend_sha256": blend["blend_sha256"],
        "total_admission_budget_held_fixed": True,
        "uses_realized_outcomes": False,
        "direct_admission_included": False,
        "automatic_policy_promotion": False,
    }, field="budget_package_sha256")


def build_score_free_slate_package_v1(
    slate_freeze: Mapping[str, object], *, source_ordinal: int,
) -> dict[str, object]:
    """Freeze exact reference/quota A250+A500 admissions for one slate."""

    freeze = core._validated_freeze(slate_freeze)
    expected_slate_id = _expected_slate(source_ordinal)
    slate = core._slate(freeze["slate"])
    binding = _mapping(freeze["source_binding"], label="slate source binding")
    if (
        slate["slate_id"] != expected_slate_id
        or (
            "source_ordinal" in binding
            and binding["source_ordinal"] != source_ordinal
        )
    ):
        _fail("score-free package slate/ordinal binding differs")
    budget_packages = [
        _budget_package(slate_freeze=freeze, budget=budget)
        for budget in core.ADMISSION_BUDGETS
    ]
    body = {
        "schema_version": SLATE_PACKAGE_SCHEMA,
        "version": VERSION,
        "source_ordinal": source_ordinal,
        "slate": slate,
        "slate_id": expected_slate_id,
        "slate_freeze": freeze,
        "slate_freeze_sha256": freeze["slate_freeze_sha256"],
        "candidate_count": freeze["candidate_count"],
        "admission_budgets": list(core.ADMISSION_BUDGETS),
        "budget_packages": budget_packages,
        "budget_packages_sha256": _hash(budget_packages),
        "uses_realized_outcomes": False,
        "direct_admission_included": False,
        "candidate_generation_performed": False,
        "k80_selection_performed": False,
        "full_union_oracle_is_training_target": False,
        "automatic_policy_promotion": False,
        "production_change_licensed": False,
    }
    try:
        score_free.reject_outcome_carriers_v1(
            body, label="broad-admission score-free slate package"
        )
    except Exception as exc:
        raise CorpusR6BroadAdmissionProgramV1Error(
            f"score-free slate package carries outcome authority: {exc}"
        ) from exc
    return _with_hash(body, field="package_sha256")


def validate_score_free_slate_package_v1(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Validate and deterministically replay one score-free slate package."""

    item = _mapping(value, label="score-free slate package")
    try:
        score_free.reject_outcome_carriers_v1(
            item, label="broad-admission score-free slate package"
        )
    except Exception as exc:
        raise CorpusR6BroadAdmissionProgramV1Error(
            f"score-free slate package carries outcome authority: {exc}"
        ) from exc
    if set(item) != _PACKAGE_FIELDS:
        _fail("score-free slate package fields differ")
    _validate_self_hash(item, field="package_sha256", label="slate package")
    source_ordinal = item.get("source_ordinal")
    expected_slate_id = _expected_slate(source_ordinal)
    freeze = core._validated_freeze(item.get("slate_freeze"))
    slate = core._slate(freeze["slate"])
    binding = _mapping(freeze["source_binding"], label="slate source binding")
    raw_budget_packages = _sequence(
        item.get("budget_packages"), label="score-free budget packages"
    )
    if (
        item.get("schema_version") != SLATE_PACKAGE_SCHEMA
        or item.get("version") != VERSION
        or item.get("slate") != slate
        or item.get("slate_id") != expected_slate_id
        or slate["slate_id"] != expected_slate_id
        or (
            "source_ordinal" in binding
            and binding["source_ordinal"] != source_ordinal
        )
        or item.get("slate_freeze_sha256") != freeze["slate_freeze_sha256"]
        or item.get("candidate_count") != freeze["candidate_count"]
        or item.get("admission_budgets") != list(core.ADMISSION_BUDGETS)
        or item.get("budget_packages_sha256") != _hash(raw_budget_packages)
        or item.get("uses_realized_outcomes") is not False
        or item.get("direct_admission_included") is not False
        or item.get("candidate_generation_performed") is not False
        or item.get("k80_selection_performed") is not False
        or item.get("full_union_oracle_is_training_target") is not False
        or item.get("automatic_policy_promotion") is not False
        or item.get("production_change_licensed") is not False
    ):
        _fail("score-free slate package authority differs")
    budget_packages: list[dict[str, object]] = []
    for ordinal, raw_budget_package in enumerate(raw_budget_packages):
        budget_package = _mapping(
            raw_budget_package, label=f"budget package[{ordinal}]"
        )
        if set(budget_package) != _BUDGET_PACKAGE_FIELDS:
            _fail("score-free budget package fields differ")
        _validate_self_hash(
            budget_package,
            field="budget_package_sha256",
            label="budget package",
        )
        budget = budget_package.get("admission_budget")
        if budget not in core.ADMISSION_BUDGETS:
            _fail("score-free budget package budget differs")
        reference = core._validated_admission(
            budget_package.get("reference_admission"), slate_freeze=freeze
        )
        quota = core._validated_admission(
            budget_package.get("quota_admission"), slate_freeze=freeze
        )
        blend = core._validated_blend(
            budget_package.get("quota_blend"),
            slate_freeze=freeze,
            admissions_by_id={
                core.REFERENCE_ADMISSION_ID: reference,
                core.QUOTA_ADMISSION_ID: quota,
            },
        )
        replay = _budget_package(slate_freeze=freeze, budget=budget)
        if (
            budget_package != replay
            or reference["admission_id"] != core.REFERENCE_ADMISSION_ID
            or quota["admission_id"] != core.QUOTA_ADMISSION_ID
            or budget_package.get("reference_admission_sha256")
            != reference["admission_sha256"]
            or budget_package.get("quota_admission_sha256")
            != quota["admission_sha256"]
            or budget_package.get("quota_blend_sha256") != blend["blend_sha256"]
            or budget_package.get("total_admission_budget_held_fixed") is not True
            or budget_package.get("uses_realized_outcomes") is not False
            or budget_package.get("direct_admission_included") is not False
            or budget_package.get("automatic_policy_promotion") is not False
        ):
            _fail("score-free budget package replay differs")
        budget_packages.append(budget_package)
    if [entry["admission_budget"] for entry in budget_packages] != list(
        core.ADMISSION_BUDGETS
    ):
        _fail("score-free budget package order differs")
    return item


def _validated_program_packages(
    packages: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    raw_packages = _sequence(packages, label="historical slate packages")
    if len(raw_packages) != len(EXPECTED_SLATE_IDS):
        _fail("historical program requires the exact 54-slate lattice")
    retained = [
        validate_score_free_slate_package_v1(raw)
        for raw in raw_packages
    ]
    if (
        [item["source_ordinal"] for item in retained]
        != list(range(len(EXPECTED_SLATE_IDS)))
        or [item["slate_id"] for item in retained] != list(EXPECTED_SLATE_IDS)
    ):
        _fail("historical packages differ from exact ordinal lattice")
    return retained


def _normalized_realized_scores(
    *, packages: Sequence[Mapping[str, object]],
    realized_scores_by_slate: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    raw_panel = _mapping(
        realized_scores_by_slate, label="historical realized-score panel"
    )
    if set(raw_panel) != set(EXPECTED_SLATE_IDS):
        _fail("realized-score panel must cover the exact 54-slate lattice")
    retained: dict[str, dict[str, int]] = {}
    for package in packages:
        slate_id = str(package["slate_id"])
        raw_scores = _mapping(
            raw_panel[slate_id], label=f"realized scores {slate_id}"
        )
        lineup_ids = [
            str(row["lineup_id"])
            for row in package["slate_freeze"]["candidate_features"]
        ]
        if (
            set(raw_scores) != set(lineup_ids)
            or any(type(value) is not int for value in raw_scores.values())
        ):
            _fail(f"realized-score coverage differs for {slate_id}")
        retained[slate_id] = {
            lineup_id: raw_scores[lineup_id] for lineup_id in lineup_ids
        }
    return retained


def _fit_walk_forward_rankers(
    *, packages: Sequence[Mapping[str, object]],
    realized_scores: Mapping[str, Mapping[str, int]],
    outcome_identity: Mapping[str, object],
) -> dict[int, dict[str, object]]:
    by_slate = {str(item["slate_id"]): item for item in packages}
    rankers: dict[int, dict[str, object]] = {}
    for target_season, training_count in ((2024, 18), (2025, 36)):
        training_slate_ids = list(EXPECTED_SLATE_IDS[:training_count])
        training = [(
            by_slate[slate_id]["slate_freeze"],
            realized_scores[slate_id],
            outcome_identity,
        ) for slate_id in training_slate_ids]
        rankers[target_season] = core.fit_past_season_direct_ranker_v1(
            training=training,
            target_season=target_season,
            expected_training_slate_ids=training_slate_ids,
        )
    return rankers


def _arm_rows(
    *, package: Mapping[str, object], budget: int,
    grade: Mapping[str, object],
) -> list[dict[str, object]]:
    admission_grades = _sequence(
        grade["admission_grades"], label="admission grade rows"
    )
    blend_grades = _sequence(
        grade["fixed_total_budget_blend_grades"], label="blend grade rows"
    )
    reference = next(
        row for row in admission_grades
        if row["admission_id"] == core.REFERENCE_ADMISSION_ID
    )
    reference_max = int(reference["realized_max_micro"])
    rows: list[dict[str, object]] = []
    for arm_kind, raw_rows, id_field in (
        ("admission", admission_grades, "admission_id"),
        ("blend", blend_grades, "challenger_admission_id"),
    ):
        for raw_row in raw_rows:
            row = _mapping(raw_row, label=f"{arm_kind} grade row")
            arm_id = str(row[id_field])
            rows.append({
                "slate_id": package["slate_id"],
                "source_ordinal": package["source_ordinal"],
                "admission_budget": budget,
                "arm_kind": arm_kind,
                "arm_id": arm_id,
                "arm_key": f"{arm_kind}::{arm_id}",
                "grade_sha256": grade["grade_sha256"],
                "realized_max_micro": row["realized_max_micro"],
                "reference_realized_max_micro": reference_max,
                "paired_max_lift_vs_reference_micro": (
                    int(row["realized_max_micro"]) - reference_max
                ),
                "fixed_corpus_max_retained": row["fixed_corpus_max_retained"],
                "fixed_corpus_max_gap_micro": row["fixed_corpus_max_gap_micro"],
                "threshold_retention": row["threshold_retention"],
            })
    return rows


def _aggregate_arm_rows(
    per_slate_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    keys = sorted({
        (int(row["admission_budget"]), str(row["arm_kind"]), str(row["arm_id"]))
        for row in per_slate_rows
    })
    summaries: list[dict[str, object]] = []
    for budget, arm_kind, arm_id in keys:
        rows = [
            row for row in per_slate_rows
            if (
                row["admission_budget"] == budget
                and row["arm_kind"] == arm_kind
                and row["arm_id"] == arm_id
            )
        ]
        lifts = [int(row["paired_max_lift_vs_reference_micro"]) for row in rows]
        retained_count = sum(
            row["fixed_corpus_max_retained"] is True for row in rows
        )
        threshold_rows: list[dict[str, object]] = []
        for threshold in core.THRESHOLDS:
            entries = [
                next(
                    item for item in row["threshold_retention"]
                    if item["threshold"] == threshold
                )
                for row in rows
            ]
            full_candidates = sum(
                int(item["fixed_corpus_candidate_count"]) for item in entries
            )
            retained_candidates = sum(
                int(item["retained_candidate_count"]) for item in entries
            )
            opportunity_slates = sum(
                item["fixed_corpus_has_opportunity"] is True for item in entries
            )
            retained_slates = sum(
                item["slate_opportunity_retained"] is True for item in entries
            )
            threshold_rows.append({
                "threshold": threshold,
                "fixed_corpus_candidate_count": full_candidates,
                "retained_candidate_count": retained_candidates,
                "candidate_retention_fraction_ppm": (
                    retained_candidates * _MICRO // full_candidates
                    if full_candidates else None
                ),
                "fixed_corpus_opportunity_slate_count": opportunity_slates,
                "retained_opportunity_slate_count": retained_slates,
                "slate_opportunity_retention_fraction_ppm": (
                    retained_slates * _MICRO // opportunity_slates
                    if opportunity_slates else None
                ),
            })
        summaries.append({
            "admission_budget": budget,
            "arm_kind": arm_kind,
            "arm_id": arm_id,
            "arm_key": f"{arm_kind}::{arm_id}",
            "paired_slate_count": len(rows),
            "paired_max_lift_sum_micro": sum(lifts),
            "paired_max_lift_mean_numerator_micro": sum(lifts),
            "paired_max_lift_mean_denominator": len(rows),
            "paired_win_count": sum(lift > 0 for lift in lifts),
            "paired_tie_count": sum(lift == 0 for lift in lifts),
            "paired_loss_count": sum(lift < 0 for lift in lifts),
            "fixed_corpus_max_retained_slate_count": retained_count,
            "fixed_corpus_max_retention_fraction_ppm": (
                retained_count * _MICRO // len(rows)
            ),
            "threshold_retention": threshold_rows,
        })
    return summaries


def grade_historical_program_v1(
    *, packages: Sequence[Mapping[str, object]],
    realized_scores_by_slate: Mapping[str, Mapping[str, int]],
    outcome_identity: Mapping[str, object],
) -> dict[str, object]:
    """Grade the exact 54-slate walk-forward admission program once."""

    # This complete lattice gate intentionally precedes every outcome touch.
    retained_packages = _validated_program_packages(packages)
    try:
        normalized_outcome_identity = batch.normalize_object_identity(
            outcome_identity, label="historical admission outcome identity"
        )
    except Exception as exc:
        raise CorpusR6BroadAdmissionProgramV1Error(
            "historical outcome identity is not generation-exact"
        ) from exc
    realized = _normalized_realized_scores(
        packages=retained_packages,
        realized_scores_by_slate=realized_scores_by_slate,
    )
    rankers = _fit_walk_forward_rankers(
        packages=retained_packages,
        realized_scores=realized,
        outcome_identity=normalized_outcome_identity,
    )
    grade_records: list[dict[str, object]] = []
    per_slate_rows: list[dict[str, object]] = []
    for package in retained_packages:
        slate = core._slate(package["slate"])
        ranker = rankers.get(int(slate["season"]))
        for budget_package in package["budget_packages"]:
            budget = int(budget_package["admission_budget"])
            admissions = [
                budget_package["reference_admission"],
                budget_package["quota_admission"],
            ]
            blends = [budget_package["quota_blend"]]
            if ranker is not None:
                direct = core.build_direct_ranker_admission_v1(
                    package["slate_freeze"], ranker=ranker, budget=budget
                )
                admissions.append(direct)
                blends.append(
                    core.build_fixed_budget_reference_challenger_blend_v1(
                        slate_freeze=package["slate_freeze"],
                        reference_admission=budget_package["reference_admission"],
                        challenger_admission=direct,
                    )
                )
            grade = core.grade_fixed_budget_admissions_v1(
                slate_freeze=package["slate_freeze"],
                admissions=admissions,
                blends=blends,
                realized_scores_micro=realized[str(package["slate_id"])],
                outcome_identity=normalized_outcome_identity,
            )
            record = _with_hash({
                "slate_id": package["slate_id"],
                "source_ordinal": package["source_ordinal"],
                "admission_budget": budget,
                "package_sha256": package["package_sha256"],
                "grade": grade,
                "grade_sha256": grade["grade_sha256"],
            }, field="grade_record_sha256")
            grade_records.append(record)
            per_slate_rows.extend(
                _arm_rows(package=package, budget=budget, grade=grade)
            )
    arm_summaries = _aggregate_arm_rows(per_slate_rows)
    package_bindings = [{
        "source_ordinal": package["source_ordinal"],
        "slate_id": package["slate_id"],
        "package_sha256": package["package_sha256"],
        "slate_freeze_sha256": package["slate_freeze_sha256"],
    } for package in retained_packages]
    ranker_rows = [{
        "target_season": season,
        "ranker": rankers[season],
        "ranker_sha256": rankers[season]["ranker_sha256"],
    } for season in (2024, 2025)]
    realized_bindings = [{
        "slate_id": slate_id,
        "realized_scores_sha256": _hash(realized[slate_id]),
    } for slate_id in EXPECTED_SLATE_IDS]
    body = {
        "schema_version": PROGRAM_GRADE_SCHEMA,
        "version": VERSION,
        "expected_slate_ids": list(EXPECTED_SLATE_IDS),
        "slate_count": len(EXPECTED_SLATE_IDS),
        "package_bindings": package_bindings,
        "package_bindings_sha256": _hash(package_bindings),
        "admission_budgets": list(core.ADMISSION_BUDGETS),
        "thresholds": list(core.THRESHOLDS),
        "outcome_identity": normalized_outcome_identity,
        "outcome_identity_sha256": _hash(normalized_outcome_identity),
        "realized_score_bindings": realized_bindings,
        "realized_score_bindings_sha256": _hash(realized_bindings),
        "walk_forward_rankers": ranker_rows,
        "walk_forward_rankers_sha256": _hash(ranker_rows),
        "walk_forward_folds": [
            {"target_season": 2024, "training_slate_count": 18,
             "training_slate_ids": list(EXPECTED_SLATE_IDS[:18])},
            {"target_season": 2025, "training_slate_count": 36,
             "training_slate_ids": list(EXPECTED_SLATE_IDS[:36])},
        ],
        "direct_arm_present_only_in_target_seasons": [2024, 2025],
        "slate_budget_grades": grade_records,
        "slate_budget_grades_sha256": _hash(grade_records),
        "per_slate_arm_deltas": per_slate_rows,
        "per_slate_arm_deltas_sha256": _hash(per_slate_rows),
        "arm_summaries": arm_summaries,
        "arm_summaries_sha256": _hash(arm_summaries),
        "fixed_corpus_and_admission_budget": True,
        "hindsight_union_gap_is_not_a_recovery_target": True,
        "k80_selection_is_secondary_and_not_performed": True,
        "descriptive_only": True,
        "automatic_policy_promotion": False,
        "production_change_licensed": False,
        "uses_realized_outcomes": True,
    }
    result = _with_hash(body, field="program_grade_sha256")
    _validate_program_grade_v1(result)
    return result


def _validate_program_grade_v1(value: Mapping[str, object]) -> dict[str, object]:
    item = _mapping(value, label="historical admission program grade")
    expected_fields = {
        "schema_version", "version", "expected_slate_ids", "slate_count",
        "package_bindings", "package_bindings_sha256", "admission_budgets",
        "thresholds", "outcome_identity", "outcome_identity_sha256",
        "realized_score_bindings", "realized_score_bindings_sha256",
        "walk_forward_rankers", "walk_forward_rankers_sha256",
        "walk_forward_folds", "direct_arm_present_only_in_target_seasons",
        "slate_budget_grades", "slate_budget_grades_sha256",
        "per_slate_arm_deltas", "per_slate_arm_deltas_sha256",
        "arm_summaries", "arm_summaries_sha256",
        "fixed_corpus_and_admission_budget",
        "hindsight_union_gap_is_not_a_recovery_target",
        "k80_selection_is_secondary_and_not_performed", "descriptive_only",
        "automatic_policy_promotion", "production_change_licensed",
        "uses_realized_outcomes", "program_grade_sha256",
    }
    _validate_self_hash(item, field="program_grade_sha256", label="program grade")
    nested = (
        ("package_bindings", "package_bindings_sha256"),
        ("realized_score_bindings", "realized_score_bindings_sha256"),
        ("walk_forward_rankers", "walk_forward_rankers_sha256"),
        ("slate_budget_grades", "slate_budget_grades_sha256"),
        ("per_slate_arm_deltas", "per_slate_arm_deltas_sha256"),
        ("arm_summaries", "arm_summaries_sha256"),
    )
    if (
        set(item) != expected_fields
        or item.get("schema_version") != PROGRAM_GRADE_SCHEMA
        or item.get("version") != VERSION
        or item.get("expected_slate_ids") != list(EXPECTED_SLATE_IDS)
        or item.get("slate_count") != len(EXPECTED_SLATE_IDS)
        or item.get("admission_budgets") != list(core.ADMISSION_BUDGETS)
        or item.get("thresholds") != list(core.THRESHOLDS)
        or item.get("outcome_identity")
        != batch.normalize_object_identity(
            item.get("outcome_identity"), label="program outcome identity"
        )
        or item.get("outcome_identity_sha256") != _hash(item["outcome_identity"])
        or any(item.get(digest) != _hash(item.get(field)) for field, digest in nested)
        or item.get("direct_arm_present_only_in_target_seasons") != [2024, 2025]
        or len(item.get("slate_budget_grades", [])) != 108
        or item.get("fixed_corpus_and_admission_budget") is not True
        or item.get("hindsight_union_gap_is_not_a_recovery_target") is not True
        or item.get("k80_selection_is_secondary_and_not_performed") is not True
        or item.get("descriptive_only") is not True
        or item.get("automatic_policy_promotion") is not False
        or item.get("production_change_licensed") is not False
        or item.get("uses_realized_outcomes") is not True
    ):
        _fail("historical admission program grade authority differs")
    return item


__all__ = [
    "EXPECTED_SLATE_IDS",
    "PROGRAM_GRADE_SCHEMA",
    "SLATE_PACKAGE_SCHEMA",
    "VERSION",
    "CorpusR6BroadAdmissionProgramV1Error",
    "build_score_free_slate_package_v1",
    "grade_historical_program_v1",
    "validate_score_free_slate_package_v1",
]
