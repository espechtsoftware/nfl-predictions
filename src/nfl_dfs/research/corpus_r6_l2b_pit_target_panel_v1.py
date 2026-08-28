"""Catalog-spined, outcome-blind target panel for the R6 L2b runtime.

This module performs no query and no publication.  The immutable later-source
catalog is the complete player spine; the supplied frame may add only the
previous role state and pre-lock injury status required by L2b.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Final

import numpy as np
import pandas as pd

from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as panel


SOURCE_COLUMNS: Final = (
    "season", "week", "gsis_id", "team", "position",
    "previous_state", "injury_status",
)
_KEY_COLUMNS: Final = ("season", "week", "gsis_id")
_FORBIDDEN_EXTRA_PATTERNS: Final = (
    "actual", "realized", "score", "points", "outcome", "winner",
    "payout", "winnings", "roi", "rank", "finish", "target_share",
    "carry_share", "snap_share", "current_role", "current_state",
    "current_week", "role_label", "target_state",
)


class CorpusR6L2BPITTargetPanelV1Error(ValueError):
    """The score-free catalog-spine contract was violated."""


def _fail(message: str) -> None:
    raise CorpusR6L2BPITTargetPanelV1Error(message)


def _normalized_name(value: object) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value)).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _source_frame(value: object) -> pd.DataFrame:
    if not isinstance(value, pd.DataFrame):
        _fail("score-free source must be one DataFrame")
    columns = [str(column) for column in value.columns]
    expected = set(SOURCE_COLUMNS)
    if set(columns) != expected or len(columns) != len(expected):
        extras = sorted(set(columns) - expected)
        forbidden = [
            name for name in extras
            if any(
                pattern in _normalized_name(name)
                for pattern in _FORBIDDEN_EXTRA_PATTERNS
            )
        ]
        if forbidden:
            _fail(
                "score-free source exposes current-week role or outcome "
                f"fields {forbidden}"
            )
        _fail("score-free source columns differ")
    frame = value.loc[:, SOURCE_COLUMNS].copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce")
    if (
        frame.empty
        or frame[["season", "week"]].isna().any().any()
        or not np.equal(frame["season"], np.floor(frame["season"])).all()
        or not np.equal(frame["week"], np.floor(frame["week"])).all()
    ):
        _fail("score-free source slate keys differ")
    frame["season"] = frame["season"].astype(int)
    frame["week"] = frame["week"].astype(int)
    for name in ("gsis_id", "team", "position", "previous_state"):
        frame[name] = frame[name].astype("string")
    frame["position"] = frame["position"].str.upper()
    frame["previous_state"] = frame["previous_state"].fillna("unknown")
    frame["injury_status"] = frame["injury_status"].astype("string")
    if (
        frame[["gsis_id", "team", "position"]].isna().any().any()
        or frame.duplicated(list(_KEY_COLUMNS)).any()
    ):
        _fail("score-free source player keys are null or duplicated")
    return frame


def _catalog_spine(
    later_source_freeze: Mapping[str, object],
) -> tuple[dict[str, object], pd.DataFrame]:
    try:
        source = panel._validated_later_source(later_source_freeze)
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise CorpusR6L2BPITTargetPanelV1Error(str(exc)) from exc
    slates = source.get("slates")
    if not isinstance(slates, list) or len(slates) != panel.TASK_COUNT:
        _fail("later-source catalog must contain the exact 54 slates")
    rows: list[dict[str, object]] = []
    for ordinal, ((season, week), raw_slate) in enumerate(
        zip(panel.EXPECTED_SLATES, slates, strict=True)
    ):
        if not isinstance(raw_slate, Mapping):
            _fail(f"later-source slate[{ordinal}] differs")
        slate = dict(raw_slate)
        if slate.get("slate_id") != f"{season}-w{week:02d}":
            _fail("later-source slate order differs")
        try:
            catalog = panel._slate_catalog(slate)
        except panel.CorpusR6L2BPanelCloudV1Error as exc:
            raise CorpusR6L2BPITTargetPanelV1Error(str(exc)) from exc
        skill = [
            row for row in catalog
            if str(row.get("pos", "")).upper() in panel.SKILL_POSITIONS
        ]
        if not skill:
            _fail("later-source slate has no skill-player catalog spine")
        rows.extend({
            "season": season,
            "week": week,
            "gsis_id": str(row["id"]),
            "catalog_team": str(row["team"]),
            "catalog_position": str(row["pos"]).upper(),
        } for row in skill)
    return source, pd.DataFrame(rows)


def materialize_catalog_spined_pit_target_panel_v1(
    *,
    later_source_freeze: Mapping[str, object],
    later_source_freeze_identity: Mapping[str, object],
    score_free_source: pd.DataFrame,
    score_free_source_identity: Mapping[str, object],
) -> dict[str, object]:
    """Return the exact canonicalizable target panel consumed by L2b tasks.

    Callers must exact-open both immutable identities before invoking this
    pure materializer.  The local CLI in this workstream enforces that byte
    binding before it reads either input.
    """
    try:
        source_identity = panel._identity(
            later_source_freeze_identity, label="later-source freeze"
        )
        frame_identity = panel._identity(
            score_free_source_identity, label="score-free source frame"
        )
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise CorpusR6L2BPITTargetPanelV1Error(str(exc)) from exc
    _, spine = _catalog_spine(later_source_freeze)
    frame = _source_frame(score_free_source)
    expected_keys = list(
        spine.loc[:, _KEY_COLUMNS].itertuples(index=False, name=None)
    )
    observed_keys = list(
        frame.loc[:, _KEY_COLUMNS]
        .sort_values(list(_KEY_COLUMNS), kind="mergesort")
        .itertuples(index=False, name=None)
    )
    sorted_expected = sorted(expected_keys)
    if observed_keys != sorted_expected:
        missing = len(set(sorted_expected) - set(observed_keys))
        extra = len(set(observed_keys) - set(sorted_expected))
        _fail(
            "score-free source does not exactly match the catalog spine "
            f"(missing={missing}, extra={extra})"
        )
    aligned = spine.merge(
        frame,
        on=list(_KEY_COLUMNS),
        how="left",
        sort=False,
        validate="one_to_one",
    )
    if (
        not aligned["catalog_team"].eq(aligned["team"].astype(str)).all()
        or not aligned["catalog_position"].eq(
            aligned["position"].astype(str).str.upper()
        ).all()
    ):
        _fail("score-free source team/position differs from the catalog spine")
    target = aligned.loc[:, SOURCE_COLUMNS].copy()
    try:
        return panel.build_pit_target_panel_v1(
            target_players=target,
            source_identities={
                "later-source-freeze": source_identity,
                "score-free-target-source": frame_identity,
            },
        )
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise CorpusR6L2BPITTargetPanelV1Error(str(exc)) from exc


__all__ = [
    "CorpusR6L2BPITTargetPanelV1Error",
    "SOURCE_COLUMNS",
    "materialize_catalog_spined_pit_target_panel_v1",
]
