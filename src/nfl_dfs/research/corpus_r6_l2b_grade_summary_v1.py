"""Deterministic, local-only summary of the complete L2b realized grade."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path
from typing import Final, Mapping, Sequence

from nfl_dfs.research.corpus_r6_score_sprint_scorecard_v1 import (
    MICRO_DK_PER_POINT,
    ScorecardInputV1,
    build_scorecard_v1,
    canonical_json_bytes_v1,
    canonical_sha256_v1,
)


SUMMARY_SCHEMA: Final = "corpus-r6-l2b-realized-grade-summary/v1"
EXPECTED_CELL_COUNT: Final = 300
EXPECTED_BUDGET_CENSUS: Final = {4: 30, 14: 30, 80: 100, 100: 70, 150: 70}
THRESHOLDS: Final = (194, 200, 220, 230)
BENCHMARK_MEAN_MICRO: Final = 178_435_000
BENCHMARK_COUNTS: Final = {194: 8, 200: 6, 220: 4, 230: 2}
FRACTIONS: Final = ("l2b-quarter-world-mixture", "l2b-native")


class CorpusR6L2BGradeSummaryV1Error(ValueError):
    """The validated input does not describe the exact L2b summary surface."""


def _fail(message: str) -> None:
    raise CorpusR6L2BGradeSummaryV1Error(message)


def _mean_display(numerator: int, denominator: int) -> str:
    value = Decimal(numerator) / Decimal(denominator) / MICRO_DK_PER_POINT
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN))


def _delta_display(numerator: int, denominator: int) -> str:
    value = Decimal(numerator) / Decimal(denominator) / MICRO_DK_PER_POINT
    return f"{value.quantize(Decimal('0.001'), rounding=ROUND_HALF_EVEN):+}"


def _threshold_counts(rows: object) -> dict[int, int]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        _fail("threshold rows are not an array")
    result: dict[int, int] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            _fail("threshold row is not an object")
        threshold = raw.get("threshold_dk")
        count = raw.get("slates_with_at_least_one_hit")
        if type(threshold) is not int or type(count) is not int:
            _fail("threshold row has non-integer values")
        result[threshold] = count
    if set(result) != set(THRESHOLDS):
        _fail("threshold registry differs")
    return result


def _coord_key(coordinate: Mapping[str, object]) -> bytes:
    return canonical_json_bytes_v1(dict(coordinate))


def _pair_key(coordinate: Mapping[str, object]) -> bytes:
    return canonical_json_bytes_v1({
        key: value for key, value in coordinate.items() if key != "fraction_id"
    })


def summarize_validated_l2b_v1(
    scorecard: Mapping[str, object], grade: Mapping[str, object]
) -> dict[str, object]:
    """Summarize an already scorecard-validated grade (exposed for unit tests)."""
    if scorecard.get("complete") is not True:
        _fail("scorecard is incomplete")
    groups = scorecard.get("diagnostic_groups")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
        _fail("diagnostic groups are absent")
    rows: list[Mapping[str, object]] = []
    for group in groups:
        if not isinstance(group, Mapping) or not isinstance(group.get("rows"), Sequence):
            _fail("diagnostic group differs")
        rows.extend(group["rows"])
    if len(rows) != EXPECTED_CELL_COUNT:
        _fail("L2b summary requires exactly 300 performance cells")

    raw_cells = grade.get("aggregate_cells")
    if not isinstance(raw_cells, Sequence) or isinstance(raw_cells, (str, bytes)):
        _fail("aggregate cells are absent")
    vectors: dict[bytes, list[int]] = {}
    for cell in raw_cells:
        if not isinstance(cell, Mapping) or not isinstance(cell.get("coordinate"), Mapping):
            _fail("aggregate cell coordinate differs")
        slate_rows = cell.get("slate_rows")
        if not isinstance(slate_rows, Sequence) or isinstance(slate_rows, (str, bytes)):
            _fail("aggregate slate rows differ")
        vector = []
        for slate in slate_rows:
            if not isinstance(slate, Mapping) or type(slate.get("weekly_maximum_micro")) is not int:
                _fail("weekly maximum differs")
            vector.append(slate["weekly_maximum_micro"])
        if len(vector) != 54:
            _fail("weekly vector is not 54 slates")
        vectors[_coord_key(cell["coordinate"])] = vector

    all_cells: list[dict[str, object]] = []
    census: dict[int, int] = {}
    for row in rows:
        coordinate = row.get("selection_coordinate")
        rational = row.get("mean_weekly_maximum_micro")
        budget = row.get("entry_budget")
        if not isinstance(coordinate, Mapping) or not isinstance(rational, Mapping):
            _fail("performance row differs")
        if coordinate.get("adapter_id") != "l2b-current-union-selectors-v1":
            _fail("foreign adapter in L2b summary")
        if type(budget) is not int or type(rational.get("numerator")) is not int or rational.get("denominator") != 54:
            _fail("performance mean differs")
        counts = _threshold_counts(row.get("thresholds"))
        census[budget] = census.get(budget, 0) + 1
        all_cells.append({
            "selection_coordinate": dict(coordinate),
            "entry_budget": budget,
            "estimand_class": row.get("estimand_class"),
            "mean_weekly_maximum_micro": dict(rational),
            "mean_weekly_maximum_dk": _mean_display(rational["numerator"], 54),
            "threshold_counts": {str(t): counts[t] for t in THRESHOLDS},
            "predeclared_before_outcome_open": True,
        })
    all_cells.sort(key=lambda cell: _coord_key(cell["selection_coordinate"]))
    if census != EXPECTED_BUDGET_CENSUS:
        _fail(f"entry-budget census differs: {census!r}")
    if set(vectors) != {_coord_key(cell["selection_coordinate"]) for cell in all_cells}:
        _fail("raw grade and validated performance coordinates differ")
    for ordinal, cell in enumerate(all_cells):
        cell["cell_ordinal"] = ordinal

    tops: list[dict[str, object]] = []
    for budget in (80, 100, 150):
        candidates = [cell for cell in all_cells if cell["entry_budget"] == budget]
        winner = sorted(
            candidates,
            key=lambda cell: (-cell["mean_weekly_maximum_micro"]["numerator"],
                              _coord_key(cell["selection_coordinate"])),
        )[0]
        numerator = winner["mean_weekly_maximum_micro"]["numerator"]
        counts = {int(k): v for k, v in winner["threshold_counts"].items()}
        tops.append({
            **winner,
            "winner_selected_after_outcomes": True,
            "descriptive_only": True,
            "promotion_authority": False,
            "descriptive_delta_vs_178_435_micro": {
                "numerator": numerator - BENCHMARK_MEAN_MICRO * 54,
                "denominator": 54,
                "unit": "micro_dk",
            },
            "descriptive_delta_vs_178_435_dk": _delta_display(
                numerator - BENCHMARK_MEAN_MICRO * 54, 54
            ),
            "threshold_count_deltas_vs_benchmark": {
                str(t): counts[t] - BENCHMARK_COUNTS[t] for t in THRESHOLDS
            },
            "scientifically_paired_to_current_benchmark": False,
            "comparison_caveat": (
                "rotated-heldout versus all-block-final-fit estimand"
                + ("" if budget == 80 else "; entry budget also differs")
            ),
        })

    by_pair: dict[bytes, dict[str, dict[str, object]]] = {}
    for cell in all_cells:
        coord = cell["selection_coordinate"]
        by_pair.setdefault(_pair_key(coord), {})[str(coord.get("fraction_id"))] = cell
    if len(by_pair) != 150 or any(set(pair) != set(FRACTIONS) for pair in by_pair.values()):
        _fail("fraction-pair census differs")
    contrasts: list[dict[str, object]] = []
    for key in sorted(by_pair):
        quarter, native = (by_pair[key][fraction] for fraction in FRACTIONS)
        qv = vectors[_coord_key(quarter["selection_coordinate"])]
        nv = vectors[_coord_key(native["selection_coordinate"])]
        deltas = [q - n for q, n in zip(qv, nv, strict=True)]
        contrasts.append({
            "paired_coordinate_without_fraction": json.loads(key),
            "contrast": "l2b-quarter-world-mixture minus l2b-native",
            "mean_delta_micro": {"numerator": sum(deltas), "denominator": 54, "unit": "micro_dk"},
            "mean_delta_dk": _delta_display(sum(deltas), 54),
            "threshold_count_deltas": {
                str(t): quarter["threshold_counts"][str(t)] - native["threshold_counts"][str(t)]
                for t in THRESHOLDS
            },
            "weekly_delta_sign_counts": {
                "positive": sum(delta > 0 for delta in deltas),
                "tied": sum(delta == 0 for delta in deltas),
                "negative": sum(delta < 0 for delta in deltas),
            },
            "scientifically_paired": True,
            "pairing_scope": "same 54 slates, heldout block, selector, and entry budget",
            "not_incumbent_control": True,
        })

    body = {
        "schema_version": SUMMARY_SCHEMA,
        "source_scorecard_sha256": scorecard.get("scorecard_sha256"),
        "cell_count": len(all_cells),
        "entry_budget_census": {str(k): census[k] for k in sorted(census)},
        "all_cells": all_cells,
        "descriptive_post_outcome_top_cells": tops,
        "matched_fraction_contrasts": contrasts,
        "current_k80_benchmark_reference": {
            "mean_weekly_maximum_dk": "178.435",
            "threshold_counts": {str(t): BENCHMARK_COUNTS[t] for t in THRESHOLDS},
            "estimand_class": "all-block-final-fit-exact-k80",
            "reference_only": True,
        },
        "inference_guardrails": {
            "post_outcome_winner_selection": True,
            "winner_selection_is_descriptive_only": True,
            "current_benchmark_pair_available": False,
            "reason": "the 300-cell grade omits the zero-fraction incumbent and its rotated-heldout vector; 178.435 is all-block final-fit",
        },
        "external_reads_performed": False,
        "outcome_source_read": False,
        "cloud_mutation_performed": False,
        "complete": True,
    }
    return {**body, "summary_sha256": canonical_sha256_v1(body)}


def summarize_l2b_grade_v1(path: Path) -> dict[str, object]:
    """Strictly validate and summarize one already-local L2b grade."""
    scorecard = build_scorecard_v1([ScorecardInputV1("l2b-realized-grade", path)])
    try:
        grade = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusR6L2BGradeSummaryV1Error("validated local grade reread failed") from exc
    if not isinstance(grade, Mapping):
        _fail("grade root is not an object")
    return summarize_validated_l2b_v1(scorecard, grade)


def render_compact_markdown_v1(summary: Mapping[str, object]) -> str:
    tops = summary.get("descriptive_post_outcome_top_cells")
    if not isinstance(tops, Sequence):
        _fail("summary top cells absent")
    lines = [
        "# L2b realized-grade compact comparison",
        "",
        "| row | K | mean weekly max | >=194 | >=200 | >=220 | >=230 | delta vs 178.435 | status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        "| current reference | 80 | 178.435 | 8 | 6 | 4 | 2 | — | reference only; not paired |",
    ]
    for cell in tops:
        counts = cell["threshold_counts"]
        coord = cell["selection_coordinate"]
        label = f"{coord['fraction_id']} / {coord['heldout_block']} / {coord['selector_id']}"
        lines.append(
            f"| {label} | {cell['entry_budget']} | {cell['mean_weekly_maximum_dk']} | "
            f"{counts['194']} | {counts['200']} | {counts['220']} | {counts['230']} | "
            f"{cell['descriptive_delta_vs_178_435_dk']} | post-outcome descriptive winner |"
        )
    lines += [
        "",
        "**Guardrail:** the three displayed L2b winners were selected after viewing realized outcomes. They are descriptive only and cannot authorize promotion.",
        "",
        "The JSON contains all 300 predeclared cells and 150 scientifically paired quarter-mixture-minus-native challenger contrasts. Neither fraction is the incumbent control; the 178.435 reference is an unmatched all-block final-fit estimand.",
        "",
    ]
    return "\n".join(lines)
