"""Outcome-blind fixed-budget allocation for the 2026 archetype shadow.

The incumbent CBWU path produces five complete native candidate books and
retains only one native-book-sized union.  This module supplies the prospective
treatment's *allocation* law for that trimming step.  It does not generate
lineups, select the final exact-80 portfolio, read realized scores, or alter the
production policy.

All ranks are within one slate's pre-lock union.  Stable candidate keys break
ties, making the result deterministic across processes and pandas versions.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil, floor

import pandas as pd


ALLOCATION_VERSION = "prospective-archetype-allocation-v1"
ARCHETYPE_ORDER = (
    "block3_joint_tail",
    "block3_q99_tail",
    "other_high_tail",
    "structural_diversity",
)
ARCHETYPE_WEIGHTS = {
    "block3_joint_tail": 0.30,
    "block3_q99_tail": 0.25,
    "other_high_tail": 0.25,
    "structural_diversity": 0.20,
}
REQUIRED_COLUMNS = {
    "candidate_key",
    "source_seed",
    "sim_q99",
    "p_line",
    "largest_team_block",
    "qb_stack_count",
    "bring_back_count",
}
FORBIDDEN_OUTCOME_COLUMNS = {
    "actual",
    "actual_score",
    "actual_rank",
    "dk_points",
    "finish",
    "finish_position",
    "payout",
    "profit",
    "roi",
    "selected_actual_best",
}


def _validate_prelock_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(
            "archetype allocation frame missing " + ", ".join(sorted(missing))
        )
    forbidden = FORBIDDEN_OUTCOME_COLUMNS & set(frame.columns)
    forbidden.update(
        column for column in frame.columns
        if str(column).lower().startswith("actual_")
    )
    if forbidden:
        raise ValueError(
            "archetype allocation frame contains post-lock outcomes: "
            + ", ".join(sorted(forbidden))
        )
    if frame.empty:
        raise ValueError("archetype allocation frame is empty")
    out = frame.copy()
    out["candidate_key"] = out.candidate_key.astype(str)
    out["source_seed"] = out.source_seed.astype(str)
    if out.candidate_key.eq("").any() or out.candidate_key.duplicated().any():
        raise ValueError("candidate keys must be nonempty and unique")
    for column in (
        "sim_q99",
        "p_line",
        "largest_team_block",
        "qb_stack_count",
        "bring_back_count",
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any():
            raise ValueError(f"archetype allocation {column} must be complete")
    if out.p_line.lt(0).any() or out.p_line.gt(1).any():
        raise ValueError("p_line must be in [0, 1]")
    if out[["largest_team_block", "qb_stack_count", "bring_back_count"]].lt(
        0
    ).any().any():
        raise ValueError("lineup structure counts must be nonnegative")
    return out


def _rank_frame(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    ordered = frame[["candidate_key", column]].sort_values(
        [column, "candidate_key"],
        ascending=[False, True],
        kind="mergesort",
    )
    return ordered.assign(**{f"{column}_rank": range(1, len(ordered) + 1)})[
        ["candidate_key", f"{column}_rank"]
    ]


def classify_archetypes(frame: pd.DataFrame) -> pd.DataFrame:
    """Assign the frozen four-way slate-relative archetype.

    ``top`` means the first ``ceil(N / 3)`` rows after descending metric and
    ascending candidate-key ordering.  This is an exact, portable tercile even
    when many candidates have tied simulation summaries.
    """
    out = _validate_prelock_frame(frame)
    for column in ("sim_q99", "p_line"):
        out = out.merge(
            _rank_frame(out, column), on="candidate_key", validate="one_to_one"
        )
    top_n = ceil(len(out) / 3)
    top_q99 = out.sim_q99_rank.le(top_n)
    top_p_line = out.p_line_rank.le(top_n)
    block3 = out.largest_team_block.eq(3)
    out["archetype"] = "structural_diversity"
    out.loc[top_q99 | top_p_line, "archetype"] = "other_high_tail"
    out.loc[block3 & top_q99 & ~top_p_line, "archetype"] = "block3_q99_tail"
    out.loc[block3 & top_q99 & top_p_line, "archetype"] = "block3_joint_tail"
    out["archetype_allocation_version"] = ALLOCATION_VERSION
    return out


def _largest_remainder_counts(
    budget: int,
    labels: Sequence[str],
    weights: dict[str, float] | None = None,
) -> dict[str, int]:
    if budget < 0:
        raise ValueError("allocation budget must be nonnegative")
    ordered = tuple(str(label) for label in labels)
    if not ordered or len(set(ordered)) != len(ordered):
        raise ValueError("allocation labels must be distinct and nonempty")
    use_weights = (
        {label: 1 / len(ordered) for label in ordered}
        if weights is None
        else {label: float(weights[label]) for label in ordered}
    )
    if set(use_weights) != set(ordered) or any(
        value < 0 for value in use_weights.values()
    ):
        raise ValueError("allocation weights differ from labels or are negative")
    total = sum(use_weights.values())
    if total <= 0:
        raise ValueError("allocation weights sum to zero")
    exact = {label: budget * use_weights[label] / total for label in ordered}
    counts = {label: floor(exact[label]) for label in ordered}
    remainder = budget - sum(counts.values())
    priority = sorted(
        ordered,
        key=lambda label: (-(exact[label] - counts[label]), ordered.index(label)),
    )
    for label in priority[:remainder]:
        counts[label] += 1
    return counts


def _candidate_sort(frame: pd.DataFrame) -> pd.DataFrame:
    priority = {label: index for index, label in enumerate(ARCHETYPE_ORDER)}
    out = frame.assign(
        _archetype_priority=frame.archetype.map(priority).astype(int),
        _tail_rank_sum=frame.sim_q99_rank + frame.p_line_rank,
    )
    return out.sort_values(
        [
            "_archetype_priority",
            "_tail_rank_sum",
            "sim_q99_rank",
            "p_line_rank",
            "bring_back_count",
            "qb_stack_count",
            "candidate_key",
        ],
        ascending=[True, True, True, True, False, False, True],
        kind="mergesort",
    )


def allocate_archetype_budget(
    frame: pd.DataFrame,
    budget: int,
    source_order: Sequence[str],
) -> tuple[pd.DataFrame, dict]:
    """Select an exact, source-balanced, fixed-budget prospective union.

    Archetype quotas are attempted in their frozen order.  Within each quota,
    sources rotate in ``source_order`` while their equal largest-remainder
    source quotas remain open.  Any infeasible archetype quota falls through to
    the best remaining pre-lock candidate while preserving source quotas.
    Source quotas relax only when a source lacks enough unique candidates to
    fill its total allocation; the receipt exposes every deviation.
    """
    if not isinstance(budget, int) or budget <= 0:
        raise ValueError("allocation budget must be a positive integer")
    out = classify_archetypes(frame)
    if len(out) < budget:
        raise ValueError(
            f"candidate union has {len(out)} rows for budget {budget}"
        )
    sources = tuple(str(source) for source in source_order)
    if not sources or len(set(sources)) != len(sources):
        raise ValueError("source order must contain distinct source ids")
    unknown = set(out.source_seed) - set(sources)
    if unknown:
        raise ValueError(
            f"source population contains unknown sources {sorted(unknown)}"
        )

    archetype_targets = _largest_remainder_counts(
        budget, ARCHETYPE_ORDER, ARCHETYPE_WEIGHTS
    )
    source_targets = _largest_remainder_counts(budget, sources)
    source_used = {source: 0 for source in sources}
    selected: list[str] = []
    selected_set: set[str] = set()

    def first_available(group: str, source: str) -> str | None:
        eligible = _candidate_sort(
            out[
                out.archetype.eq(group)
                & out.source_seed.eq(source)
                & ~out.candidate_key.isin(selected_set)
            ]
        )
        return None if eligible.empty else str(eligible.candidate_key.iloc[0])

    # Primary pass: exact archetype targets subject to equal source capacity.
    for group_index, group in enumerate(ARCHETYPE_ORDER):
        cursor = group_index % len(sources)
        for _ in range(archetype_targets[group]):
            chosen_source = None
            chosen_key = None
            for offset in range(len(sources)):
                source = sources[(cursor + offset) % len(sources)]
                if source_used[source] >= source_targets[source]:
                    continue
                key = first_available(group, source)
                if key is not None:
                    chosen_source, chosen_key = source, key
                    cursor = (cursor + offset + 1) % len(sources)
                    break
            if chosen_key is None:
                break
            selected.append(chosen_key)
            selected_set.add(chosen_key)
            source_used[chosen_source] += 1

    # Frozen first fallback: fill each source's remaining quota from its best
    # remaining candidate, regardless of archetype deficit.
    for source in sources:
        need = source_targets[source] - source_used[source]
        remaining = _candidate_sort(
            out[
                out.source_seed.eq(source)
                & ~out.candidate_key.isin(selected_set)
            ]
        )
        for key in remaining.candidate_key.astype(str).head(need):
            selected.append(key)
            selected_set.add(key)
            source_used[source] += 1

    # Last fallback is permitted only for a source with too few unique rows.
    # It is globally deterministic and is disclosed as source-quota relaxation.
    if len(selected) < budget:
        remaining = _candidate_sort(out[~out.candidate_key.isin(selected_set)])
        for key in remaining.candidate_key.astype(str).head(budget - len(selected)):
            selected.append(key)
            selected_set.add(key)
            source = str(out.loc[out.candidate_key.eq(key), "source_seed"].iloc[0])
            source_used[source] += 1

    if len(selected) != budget or len(selected_set) != budget:
        raise RuntimeError("archetype allocator did not produce an exact budget")
    keyed_rank = {key: rank for rank, key in enumerate(selected, start=1)}
    chosen = out[out.candidate_key.isin(selected_set)].copy()
    chosen["allocation_rank"] = chosen.candidate_key.map(keyed_rank).astype(int)
    chosen = chosen.sort_values("allocation_rank").reset_index(drop=True)
    actual_archetypes = {
        label: int(chosen.archetype.eq(label).sum()) for label in ARCHETYPE_ORDER
    }
    actual_sources = {
        source: int(chosen.source_seed.eq(source).sum()) for source in sources
    }
    receipt = {
        "allocation_version": ALLOCATION_VERSION,
        "input_candidates": int(len(out)),
        "candidate_budget": int(budget),
        "archetype_order": list(ARCHETYPE_ORDER),
        "archetype_weights": dict(ARCHETYPE_WEIGHTS),
        "archetype_targets": archetype_targets,
        "archetype_available": {
            label: int(out.archetype.eq(label).sum()) for label in ARCHETYPE_ORDER
        },
        "archetype_selected": actual_archetypes,
        "archetype_shortfall": {
            label: max(0, archetype_targets[label] - actual_archetypes[label])
            for label in ARCHETYPE_ORDER
        },
        "source_order": list(sources),
        "source_targets": source_targets,
        "source_available": {
            source: int(out.source_seed.eq(source).sum()) for source in sources
        },
        "source_selected": actual_sources,
        "source_quota_relaxed": actual_sources != source_targets,
        "uses_realized_outcomes": False,
    }
    return chosen, receipt


__all__ = [
    "ALLOCATION_VERSION",
    "ARCHETYPE_ORDER",
    "ARCHETYPE_WEIGHTS",
    "allocate_archetype_budget",
    "classify_archetypes",
]
