"""Fail-closed validation and support census for the canonical DST event frame.

This module is deliberately score-free with respect to lineup outcomes.  It
validates completed-game defense/special-teams labels, their current
DraftKings reconstruction, and strictly-prior component windows before a
future event-ledger model is allowed to consume them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from hashlib import sha256
import json
import re
from typing import Any, Final

import numpy as np
import pandas as pd

from ..models.dst_scoring import (
    DST_COMPONENTS,
    DST_SCORING_LAW,
    DST_SCORING_LAW_ID,
    points_allowed_points,
    score_dst_components,
)


EVENT_FRAME_VERSION: Final = "dst-team-game-event-frame-2026-08-17-v1"
SCORING_LAW_SOURCE_SHA256: Final = (
    DST_SCORING_LAW.sources[0].content_sha256
)
TAIL_THRESHOLDS: Final = (15, 20, 25)
KEY_COLUMNS: Final = ("season", "week", "game_id", "team")
BASE_COLUMNS: Final = (
    *KEY_COLUMNS,
    "opponent",
    "opponent_final_score",
    "pa",
    "excluded_defensive_td_points",
    "excluded_safety_points",
    "excluded_non_dst_points",
    *DST_COMPONENTS,
    "defensive_safeties",
    "defensive_return_tds",
    "points_allowed_tier_points",
    "reconstructed_dst_dk_points",
    "authoritative_source_raw_rows",
    "authoritative_source_matched_rows",
    "authoritative_source_rejected_rows",
    "authoritative_distinct_score_count",
    "authoritative_source_status",
    "authoritative_dst_dk_points",
    "dst_dk_points",
    "score_reconciliation_delta",
    "score_reconciliation_status",
    "event_frame_version",
    "scoring_law_id",
    "scoring_law_source_sha256",
    "event_vector_payload",
    "event_vector_sha256",
)
PRIOR_COLUMNS: Final = (
    "dst_points_l4",
    "dst_points_l16",
    "dst_event_games_prior_l4",
    "dst_event_games_prior_l16",
    *(f"dst_event_{component}_l4" for component in DST_COMPONENTS),
    "dst_event_points_allowed_l4",
    *(f"dst_event_{component}_l16" for component in DST_COMPONENTS),
    "dst_event_points_allowed_l16",
)
_HEX64 = re.compile(r"[0-9A-Fa-f]{64}")


class DstEventFrameError(ValueError):
    """Raised when the canonical DST source frame is unsafe to consume."""


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise DstEventFrameError(f"DST event frame lacks columns {missing}")


def _numbers(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise DstEventFrameError(f"DST event frame {column} is not finite")
    return values


def _nonnegative_integers(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = _numbers(frame, column)
    if np.any(values < 0) or np.any(values != np.floor(values)):
        raise DstEventFrameError(
            f"DST event frame {column} is not a nonnegative integer",
        )
    return values


def _assert_close(
    observed: pd.Series | np.ndarray,
    expected: pd.Series | np.ndarray,
    *,
    label: str,
    atol: float = 1e-9,
) -> None:
    left = np.asarray(observed, dtype=float)
    right = np.asarray(expected, dtype=float)
    if left.shape != right.shape or not np.allclose(
        left,
        right,
        atol=atol,
        rtol=0.0,
        equal_nan=True,
    ):
        raise DstEventFrameError(f"DST event frame {label} differs")


def _expected_prior_series(
    frame: pd.DataFrame,
    source: str,
    *,
    window: int,
    within_season: bool,
    aggregate: str,
) -> pd.Series:
    groups = ["team", "season"] if within_season else ["team"]
    grouped = frame.groupby(groups, sort=False, dropna=False)[source]
    shifted = grouped.shift(1)
    regrouped = shifted.groupby(
        [frame[column] for column in groups], sort=False, dropna=False,
    )
    rolling = regrouped.rolling(window=window, min_periods=1)
    if aggregate == "mean":
        result = rolling.mean()
    elif aggregate == "count":
        result = rolling.count()
    else:
        raise AssertionError("unsupported prior-window aggregate")
    return result.reset_index(level=list(range(len(groups))), drop=True)


def _validate_prior_windows(frame: pd.DataFrame) -> None:
    ordered = frame.sort_values(
        ["team", "season", "week", "game_id"], kind="mergesort",
    ).reset_index(drop=True)
    sources = {"dst_points": "dst_dk_points", **{
        component: component for component in DST_COMPONENTS
    }, "points_allowed": "pa"}
    for suffix, window, within_season in (("l4", 4, True), ("l16", 16, False)):
        for output_prefix, source in sources.items():
            expected = _expected_prior_series(
                ordered,
                source,
                window=window,
                within_season=within_season,
                aggregate="mean",
            )
            _assert_close(
                ordered[
                    f"dst_event_{output_prefix}_{suffix}"
                    if output_prefix != "dst_points"
                    else f"dst_points_{suffix}"
                ],
                expected,
                label=f"{output_prefix}_{suffix} is not strictly prior",
            )
        expected_count = _expected_prior_series(
            ordered.assign(_row=1.0),
            "_row",
            window=window,
            within_season=within_season,
            aggregate="count",
        )
        _assert_close(
            ordered[f"dst_event_games_prior_{suffix}"],
            expected_count.fillna(0.0),
            label=f"dst_games_prior_{suffix} differs",
        )


def _canonical_event_payload(row: object) -> str:
    """Rebuild the exact BigQuery ``TO_JSON_STRING(STRUCT(...))`` payload."""
    payload = {
        "event_frame_version": str(getattr(row, "event_frame_version")),
        "scoring_law_id": str(getattr(row, "scoring_law_id")),
        "game_id": str(getattr(row, "game_id")),
        "season": int(getattr(row, "season")),
        "week": int(getattr(row, "week")),
        "team": str(getattr(row, "team")),
        "opponent": str(getattr(row, "opponent")),
        "sacks": int(getattr(row, "sacks")),
        "interceptions": int(getattr(row, "interceptions")),
        "fumble_recoveries": int(getattr(row, "fumble_recoveries")),
        "safeties": int(getattr(row, "safeties")),
        "defensive_safeties": int(getattr(row, "defensive_safeties")),
        "blocked_kicks": int(getattr(row, "blocked_kicks")),
        "return_tds": int(getattr(row, "return_tds")),
        "defensive_return_tds": int(getattr(row, "defensive_return_tds")),
        "defensive_conversions": int(getattr(row, "defensive_conversions")),
        "opponent_final_score": int(getattr(row, "opponent_final_score")),
        "excluded_defensive_td_points": int(
            getattr(row, "excluded_defensive_td_points")
        ),
        "excluded_safety_points": int(getattr(row, "excluded_safety_points")),
        "points_allowed": int(getattr(row, "pa")),
        "reconstructed_dst_dk_points": int(
            getattr(row, "reconstructed_dst_dk_points")
        ),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def validate_dst_event_frame(
    frame: pd.DataFrame,
    *,
    require_reconciled_authoritative_scores: bool = True,
    validate_prior_windows: bool = True,
    expected_authoritative_rows_by_season: Mapping[int, int] | None = None,
) -> dict[str, Any]:
    """Validate one fully materialized canonical team-game event frame.

    The strict default rejects every authoritative/reconstruction difference.
    A caller may set ``require_reconciled_authoritative_scores=False`` only to
    produce a diagnosis/census; that result does not license a downstream fit.
    """
    if frame.empty:
        raise DstEventFrameError("DST event frame is empty")
    _require_columns(frame, BASE_COLUMNS)
    if validate_prior_windows:
        _require_columns(frame, PRIOR_COLUMNS)
    if frame[list(KEY_COLUMNS)].isna().any().any():
        raise DstEventFrameError("DST event frame has a null key")
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise DstEventFrameError("DST event frame repeats a team-game key")
    if frame.duplicated(["season", "week", "team"]).any():
        raise DstEventFrameError("DST event frame repeats a team-week key")

    work = frame.copy()
    work["season"] = pd.to_numeric(work.season, errors="raise").astype(int)
    work["week"] = pd.to_numeric(work.week, errors="raise").astype(int)
    if (work.week < 1).any() or (work.season < 1900).any():
        raise DstEventFrameError("DST event frame season/week is malformed")
    if work.team.astype(str).eq(work.opponent.astype(str)).any():
        raise DstEventFrameError("DST event frame has a self-opponent")

    for key, group in work.groupby(
        ["season", "week", "game_id"], sort=False, dropna=False,
    ):
        if len(group) != 2 or group.team.nunique() != 2:
            raise DstEventFrameError(
                f"DST event frame game {key!r} does not have two teams",
            )
        teams = set(group.team.astype(str))
        if any(str(row.opponent) not in teams - {str(row.team)}
               for row in group.itertuples(index=False)):
            raise DstEventFrameError(
                f"DST event frame game {key!r} has an opponent mismatch",
            )

    integer_columns = (
        "opponent_final_score",
        "pa",
        "excluded_defensive_td_points",
        "excluded_safety_points",
        "excluded_non_dst_points",
        *DST_COMPONENTS,
        "defensive_safeties",
        "defensive_return_tds",
        "authoritative_source_raw_rows",
        "authoritative_source_matched_rows",
        "authoritative_source_rejected_rows",
        "authoritative_distinct_score_count",
    )
    numeric = {
        column: _nonnegative_integers(work, column)
        for column in integer_columns
    }
    _assert_close(
        numeric["excluded_non_dst_points"],
        numeric["excluded_defensive_td_points"]
        + numeric["excluded_safety_points"],
        label="excluded non-DST points",
    )
    _assert_close(
        numeric["pa"],
        numeric["opponent_final_score"]
        - numeric["excluded_non_dst_points"],
        label="points allowed reconstruction",
    )
    if np.any(numeric["excluded_defensive_td_points"] % 6 != 0):
        raise DstEventFrameError("DST defensive-TD exclusions are not multiples of 6")
    if np.any(numeric["excluded_safety_points"] % 2 != 0):
        raise DstEventFrameError("DST safety exclusions are not multiples of 2")
    if np.any(numeric["defensive_return_tds"] > numeric["return_tds"]):
        raise DstEventFrameError("DST defensive return TDs exceed all return TDs")
    if np.any(numeric["defensive_safeties"] > numeric["safeties"]):
        raise DstEventFrameError("DST defensive safeties exceed all safeties")

    # Every excluded point on one team row must be an explicit event credited
    # to the reciprocal DST row. This closes the accounting identity instead
    # of accepting a clipped scalar PA value.
    for key, group in work.groupby(
        ["season", "week", "game_id"], sort=False, dropna=False,
    ):
        by_team = {str(row.team): row for row in group.itertuples(index=False)}
        for row in group.itertuples(index=False):
            opponent_row = by_team[str(row.opponent)]
            if int(row.excluded_defensive_td_points) != (
                int(opponent_row.defensive_return_tds) * 6
            ):
                raise DstEventFrameError(
                    f"DST game {key!r} defensive-TD exclusion is not reciprocal"
                )
            if int(row.excluded_safety_points) != (
                int(opponent_row.defensive_safeties) * 2
            ):
                raise DstEventFrameError(
                    f"DST game {key!r} safety exclusion is not reciprocal"
                )

    reconstructed: list[float] = []
    tier_points: list[float] = []
    for row in work.itertuples(index=False):
        components = {
            component: float(getattr(row, component))
            for component in DST_COMPONENTS
        }
        reconstructed.append(score_dst_components(
            components,
            points_allowed=float(row.pa),
        ))
        tier_points.append(points_allowed_points(float(row.pa)))
    _assert_close(
        work.points_allowed_tier_points,
        tier_points,
        label="points-allowed tier",
    )
    _assert_close(
        work.reconstructed_dst_dk_points,
        reconstructed,
        label="canonical score reconstruction",
    )

    raw_rows = numeric["authoritative_source_raw_rows"].astype(np.int64)
    matched_rows = numeric["authoritative_source_matched_rows"].astype(np.int64)
    rejected_rows = numeric["authoritative_source_rejected_rows"].astype(np.int64)
    distinct_scores = numeric["authoritative_distinct_score_count"].astype(np.int64)
    if np.any(raw_rows != matched_rows + rejected_rows):
        raise DstEventFrameError("DST authoritative source row counts differ")
    if np.any(distinct_scores > matched_rows):
        raise DstEventFrameError("DST authoritative distinct scores exceed matches")
    if np.any((matched_rows > 0) != (distinct_scores > 0)):
        raise DstEventFrameError("DST authoritative matched-score support differs")
    expected_source_status = np.where(
        raw_rows == 0,
        "source_unavailable",
        np.where(
            matched_rows == 0,
            "source_unmatched",
            np.where(
                distinct_scores > 1,
                "source_conflict",
                np.where(
                    rejected_rows > 0,
                    "source_partial_rejection",
                    np.where(
                        matched_rows > 1,
                        "source_match_duplicate_identical",
                        "source_match_unique",
                    ),
                ),
            ),
        ),
    )
    if not np.array_equal(
        work.authoritative_source_status.astype(str).to_numpy(),
        expected_source_status,
    ):
        raise DstEventFrameError("DST authoritative source status differs")

    authoritative = pd.to_numeric(
        work.authoritative_dst_dk_points, errors="coerce",
    ).to_numpy(dtype=float)
    if np.isinf(authoritative).any():
        raise DstEventFrameError("DST authoritative score is infinite")
    reconstruction = np.asarray(reconstructed, dtype=float)
    has_authoritative = np.isfinite(authoritative)
    if not np.array_equal(has_authoritative, distinct_scores == 1):
        raise DstEventFrameError("DST authoritative scalar/source support differs")
    delta = authoritative - reconstruction
    mismatch = has_authoritative & (np.abs(delta) > 1e-9)
    expected_score = np.where(has_authoritative, authoritative, reconstruction)
    _assert_close(work.dst_dk_points, expected_score, label="canonical score choice")
    expected_delta = np.where(has_authoritative, delta, np.nan)
    _assert_close(
        pd.to_numeric(work.score_reconciliation_delta, errors="coerce"),
        expected_delta,
        label="score reconciliation delta",
    )
    expected_status = np.where(
        (raw_rows > 0) & (matched_rows == 0),
        "source_unmatched",
        np.where(
            distinct_scores > 1,
            "source_conflict",
            np.where(
                rejected_rows > 0,
                "source_partial_rejection",
                np.where(
                    ~has_authoritative,
                    "reconstruction_only",
                    np.where(
                        mismatch,
                        "authoritative_override_mismatch",
                        "authoritative_match",
                    ),
                ),
            ),
        ),
    )
    if not np.array_equal(
        work.score_reconciliation_status.astype(str).to_numpy(),
        expected_status,
    ):
        raise DstEventFrameError("DST score reconciliation status differs")
    source_failure = np.isin(
        expected_source_status,
        ["source_unmatched", "source_conflict", "source_partial_rejection"],
    )
    if require_reconciled_authoritative_scores and source_failure.any():
        sample = work.loc[source_failure, list(KEY_COLUMNS)].head(5).to_dict("records")
        raise DstEventFrameError(
            "DST authoritative source remains unmatched/conflicted/rejected; "
            f"count={int(source_failure.sum())}, sample={sample}",
        )
    if require_reconciled_authoritative_scores and mismatch.any():
        sample = work.loc[mismatch, list(KEY_COLUMNS)].head(5).to_dict("records")
        raise DstEventFrameError(
            "DST authoritative scores remain unreconciled; "
            f"count={int(mismatch.sum())}, sample={sample}",
        )

    if not work.event_frame_version.astype(str).eq(EVENT_FRAME_VERSION).all():
        raise DstEventFrameError("DST event-frame version differs")
    if not work.scoring_law_id.astype(str).eq(DST_SCORING_LAW_ID).all():
        raise DstEventFrameError("DST event frame scoring-law ID differs")
    if not work.scoring_law_source_sha256.astype(str).eq(
        SCORING_LAW_SOURCE_SHA256,
    ).all():
        raise DstEventFrameError("DST event frame scoring-law source hash differs")
    if not work.event_vector_sha256.astype(str).map(
        lambda value: _HEX64.fullmatch(value) is not None,
    ).all():
        raise DstEventFrameError("DST event-vector hash is malformed")
    for row in work.itertuples(index=False):
        expected_payload = _canonical_event_payload(row)
        if str(row.event_vector_payload) != expected_payload:
            raise DstEventFrameError("DST event-vector payload differs")
        expected_hash = sha256(expected_payload.encode("utf-8")).hexdigest()
        if str(row.event_vector_sha256).lower() != expected_hash:
            raise DstEventFrameError("DST event-vector hash differs")
    if work.event_vector_sha256.astype(str).duplicated().any():
        raise DstEventFrameError("DST event-vector hash repeats")

    coverage_contract: dict[int, int] | None = None
    if expected_authoritative_rows_by_season is not None:
        coverage_contract = {}
        for season, count in expected_authoritative_rows_by_season.items():
            if (
                isinstance(season, (bool, np.bool_))
                or not isinstance(season, (int, np.integer))
                or isinstance(count, (bool, np.bool_))
                or not isinstance(count, (int, np.integer))
                or int(count) < 0
            ):
                raise DstEventFrameError(
                    "DST authoritative coverage contract is malformed"
                )
            coverage_contract[int(season)] = int(count)
        seasons = set(int(value) for value in work.season.unique())
        if set(coverage_contract) != seasons:
            raise DstEventFrameError("DST authoritative coverage seasons differ")
        actual = {
            int(season): int(group.authoritative_dst_dk_points.notna().sum())
            for season, group in work.groupby("season", sort=True)
        }
        if actual != coverage_contract:
            raise DstEventFrameError("DST authoritative coverage counts differ")
    elif require_reconciled_authoritative_scores:
        raise DstEventFrameError(
            "DST strict validation requires an authoritative coverage contract"
        )

    if validate_prior_windows:
        _validate_prior_windows(work)

    return {
        "version": EVENT_FRAME_VERSION,
        "scoring_law_id": DST_SCORING_LAW_ID,
        "rows": int(len(work)),
        "games": int(work.game_id.nunique()),
        "seasons": sorted(int(value) for value in work.season.unique()),
        "authoritative_rows": int(has_authoritative.sum()),
        "authoritative_mismatches": int(mismatch.sum()),
        "authoritative_source_failures": int(source_failure.sum()),
        "authoritative_coverage_contract": coverage_contract,
        "strict_reconciliation_required": bool(
            require_reconciled_authoritative_scores
        ),
        "prior_windows_validated": bool(validate_prior_windows),
    }


def census_dst_event_support(frame: pd.DataFrame) -> dict[str, Any]:
    """Return season support after mechanical validation, without licensing it."""
    receipt = validate_dst_event_frame(
        frame,
        require_reconciled_authoritative_scores=False,
        validate_prior_windows=True,
    )
    work = frame.copy()
    work["season"] = pd.to_numeric(work.season, errors="raise").astype(int)
    records: list[dict[str, Any]] = []
    for season, group in work.groupby("season", sort=True):
        authoritative = pd.to_numeric(
            group.authoritative_dst_dk_points, errors="coerce",
        )
        mismatch = group.score_reconciliation_status.astype(str).eq(
            "authoritative_override_mismatch",
        )
        source_failure = group.authoritative_source_status.astype(str).isin(
            ["source_unmatched", "source_conflict", "source_partial_rejection"],
        )
        canonical = pd.to_numeric(group.dst_dk_points, errors="raise")
        reconstructed = pd.to_numeric(
            group.reconstructed_dst_dk_points, errors="raise",
        )
        records.append({
            "season": int(season),
            "rows": int(len(group)),
            "games": int(group.game_id.nunique()),
            "authoritative_rows": int(authoritative.notna().sum()),
            "authoritative_mismatches": int(mismatch.sum()),
            "authoritative_source_raw_rows": int(pd.to_numeric(
                group.authoritative_source_raw_rows, errors="raise",
            ).sum()),
            "authoritative_source_matched_rows": int(pd.to_numeric(
                group.authoritative_source_matched_rows, errors="raise",
            ).sum()),
            "authoritative_source_rejected_rows": int(pd.to_numeric(
                group.authoritative_source_rejected_rows, errors="raise",
            ).sum()),
            "authoritative_source_failures": int(source_failure.sum()),
            "nonzero_components": {
                component: int(pd.to_numeric(
                    group[component], errors="raise",
                ).gt(0).sum())
                for component in DST_COMPONENTS
            },
            "canonical_tail_support": {
                f"ge_{threshold}": int(canonical.ge(threshold).sum())
                for threshold in TAIL_THRESHOLDS
            },
            "reconstructed_tail_support": {
                f"ge_{threshold}": int(reconstructed.ge(threshold).sum())
                for threshold in TAIL_THRESHOLDS
            },
        })
    return {**receipt, "season_support": records}


__all__ = [
    "BASE_COLUMNS",
    "DstEventFrameError",
    "EVENT_FRAME_VERSION",
    "KEY_COLUMNS",
    "PRIOR_COLUMNS",
    "SCORING_LAW_SOURCE_SHA256",
    "TAIL_THRESHOLDS",
    "census_dst_event_support",
    "validate_dst_event_frame",
]
