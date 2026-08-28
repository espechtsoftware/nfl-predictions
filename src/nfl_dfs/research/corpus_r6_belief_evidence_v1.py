"""Real-player evidence extraction for the R6 L1/L2 belief calibrations.

This module has one narrow job: convert player-level, point-in-time sources
and already-generated conditional world banks into the two frames consumed by
``corpus_r6_belief_calibration_v1``.  It never constructs, selects, or scores
a lineup.

L1 resolves QB1/WR1/RB1 from each team's pre-lock ordinary mean, measures the
three frozen co-exceedance events in realized player points and in the paired
ordinary/shootout banks, and emits opposing-WR1 sufficient moments.  L2
reuses the audited latent-role source, preserving all-game lag features before
restricting labels to the Sunday main slate, then joins the frozen ordinary
mean and player actual on exact player-week identity.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from .belief_world_v1 import canonical_sha256
from .corpus_r6_belief_calibration_v1 import (
    CALIBRATION_SEASONS,
    L1_EVENT_COLUMNS,
    L1_METRICS,
    L1_MOMENT_COLUMNS,
    L2_RESIDUAL_COLUMNS,
)
from .latent_role_state import (
    FORBIDDEN_OUTCOME_COLUMNS,
    INPUT_FEATURES,
    SHARE_FIELDS,
    TARGET,
    TRANSITION_SOURCE_SQL,
    add_previous_state,
    classify_realized_states,
    prepare_transition_frame,
    transition_frame_sha256,
)
from .object_identity import IDENTITY_FIELDS, content_identity


L1_EVIDENCE_SCHEMA: Final = "corpus-r6-l1-real-player-evidence/v1"
L2_EVIDENCE_SCHEMA: Final = "corpus-r6-l2-real-player-evidence/v1"
L1_BANK_MANIFEST_SCHEMA: Final = "corpus-r6-l1-conditional-bank-manifest/v1"
ROLE_SOURCE_FIRST_SEASON: Final = 2018
ROLE_SOURCE_LAST_SEASON: Final = 2022

_SNAPSHOT_BASE_COLUMNS: Final = (
    "gsis_id",
    "season",
    "week",
    "pos",
    "team",
    "opp",
    "game_id",
    "mean_projection",
    "actual",
)
_LINEUP_OUTCOME_COLUMNS: Final = frozenset({
    "lineup_score",
    "selected_score",
    "winner_score",
    "payout",
    "roi",
    "winnings",
    "rank",
    "finish_position",
    "actual_score",
})
_ROLE_BY_POSITION: Final = {"QB": "QB1", "WR": "WR1", "RB": "RB1"}
_EVENT_THRESHOLDS: Final = {
    "qb_wr1_ge_50": (("QB1", "WR1"), 50.0),
    "qb_wr1_ge_70": (("QB1", "WR1"), 70.0),
    "qb_wr1_rb1_ge_75": (("QB1", "WR1", "RB1"), 75.0),
}


class BeliefEvidenceError(ValueError):
    """A player source, conditional bank, or exact join was not valid."""


@dataclass(frozen=True, slots=True)
class L1ConditionalBankShard:
    """One slate's row-aligned ordinary and conditional-shootout worlds."""

    season: int
    week: int
    player_ids: tuple[str, ...]
    ordinary_draws: np.ndarray
    shootout_draws: np.ndarray
    source_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class L1RealPlayerEvidence:
    event_rows: pd.DataFrame
    opposing_wr1_moment_rows: pd.DataFrame
    receipt: dict[str, object]


@dataclass(frozen=True, slots=True)
class L2RealPlayerEvidence:
    role_history: pd.DataFrame
    residual_history: pd.DataFrame
    receipt: dict[str, object]


def _role_source_sql() -> str:
    """Add main-slate eligibility without changing all-game state lags."""
    marker = "SELECT\n  t.gsis_id, t.season"
    if TRANSITION_SOURCE_SQL.count(marker) != 1:
        raise RuntimeError("latent-role transition SQL projection marker differs")
    replacement = """SELECT
  t.gsis_id, t.game_id,
  EXISTS (
    SELECT 1
    FROM `{raw}.schedules` main_schedule
    WHERE main_schedule.game_id = t.game_id
      AND main_schedule.game_type = 'REG'
      AND main_schedule.weekday = 'Sunday'
      AND SAFE.PARSE_TIME('%H:%M', main_schedule.gametime)
            >= TIME '13:00:00'
      AND SAFE.PARSE_TIME('%H:%M', main_schedule.gametime)
            < TIME '19:00:00'
  ) AS is_sunday_main,
  t.season"""
    result = TRANSITION_SOURCE_SQL.replace(marker, replacement)
    result = result.replace(
        "WHERE t.season BETWEEN 2018 AND 2025",
        "WHERE t.season BETWEEN 2018 AND 2022",
    )
    if "WHERE t.season BETWEEN 2018 AND 2022" not in result:
        raise RuntimeError("latent-role transition SQL season marker differs")
    return result


ROLE_HISTORY_SOURCE_SQL: Final = _role_source_sql()
ROLE_HISTORY_SOURCE_SQL_SHA256: Final = sha256(
    ROLE_HISTORY_SOURCE_SQL.encode("utf-8")
).hexdigest()


def local_file_identity(path: str | Path) -> dict[str, object]:
    """Return a content-pinned identity for a local smoke/research source.

    A durable calibration release should use the uploaded object's GCS
    identity.  This helper is deliberately explicit about its local URI and
    exists so a real schema smoke can be repeatable before upload.
    """
    source = Path(path).resolve(strict=True)
    raw = source.read_bytes()
    stat = source.stat()
    return {
        "uri": source.as_uri(),
        "generation": str(stat.st_mtime_ns),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity(value: Mapping[str, object], *, label: str) -> dict[str, object]:
    try:
        fields = content_identity(value)
    except (TypeError, ValueError) as exc:
        raise BeliefEvidenceError(f"{label} identity differs") from exc
    return dict(zip(IDENTITY_FIELDS, fields, strict=True))


def _records_sha256(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    records: list[dict[str, object]] = []
    for values in frame.loc[:, list(columns)].itertuples(index=False, name=None):
        record: dict[str, object] = {}
        for name, value in zip(columns, values, strict=True):
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            elif isinstance(value, np.bool_):
                value = bool(value)
            record[str(name)] = value
        records.append(record)
    return canonical_sha256(records)


def _validate_snapshot(
    rows: pd.DataFrame,
    *,
    expected_seasons: Sequence[int] = CALIBRATION_SEASONS,
) -> pd.DataFrame:
    if not isinstance(rows, pd.DataFrame):
        raise BeliefEvidenceError("player snapshot must be a dataframe")
    if missing := set(_SNAPSHOT_BASE_COLUMNS) - set(rows.columns):
        raise BeliefEvidenceError(
            f"player snapshot missing columns {sorted(missing)}"
        )
    forbidden = _LINEUP_OUTCOME_COLUMNS & {
        str(column).strip().lower() for column in rows.columns
    }
    if forbidden:
        raise BeliefEvidenceError(
            f"player snapshot exposes lineup outcomes {sorted(forbidden)}"
        )
    out = rows.loc[:, list(_SNAPSHOT_BASE_COLUMNS)].copy()
    out["gsis_id"] = out["gsis_id"].astype("string")
    out["season"] = pd.to_numeric(out["season"], errors="raise").astype(int)
    out["week"] = pd.to_numeric(out["week"], errors="raise").astype(int)
    out["pos"] = out["pos"].astype("string").str.upper()
    for name in ("team", "opp", "game_id"):
        out[name] = out[name].astype("string")
    expected = {int(value) for value in expected_seasons}
    out = out[out["season"].isin(expected)].copy()
    if set(out["season"]) != expected:
        raise BeliefEvidenceError("player snapshot calibration seasons differ")
    if not out["week"].between(1, 18).all():
        raise BeliefEvidenceError("player snapshot week is outside 1--18")
    if out[["gsis_id", "team", "opp", "game_id"]].isna().any().any():
        raise BeliefEvidenceError("player snapshot identities are empty")
    if (
        (out["gsis_id"].str.len() == 0)
        | (out["team"].str.len() == 0)
        | (out["opp"].str.len() == 0)
        | (out["game_id"].str.len() == 0)
    ).any():
        raise BeliefEvidenceError("player snapshot identities are empty")
    # The frozen player snapshot represents every DST with the shared legacy
    # placeholder ``gsis_id=0.0``.  DST is not consumed by either belief-law
    # extractor, so its repeated placeholder must not invalidate otherwise
    # exact offensive-player evidence.  All positions that can enter L1/L2
    # remain one-row-per-player-week and fail closed on a duplicate.
    skill_identity_rows = out[out["pos"].isin(("QB", "RB", "WR", "TE"))]
    if skill_identity_rows.duplicated(["gsis_id", "season", "week"]).any():
        raise BeliefEvidenceError("skill-player snapshot identities repeat")
    for name in ("mean_projection", "actual"):
        values = pd.to_numeric(out[name], errors="raise").astype(float)
        if not np.isfinite(values).all():
            raise BeliefEvidenceError(f"player snapshot {name} is nonfinite")
        out[name] = values
    return out.sort_values(
        ["season", "week", "game_id", "team", "pos", "gsis_id"],
        kind="mergesort",
    ).reset_index(drop=True)


def snapshot_schema_smoke_v1(columns: Sequence[object]) -> dict[str, object]:
    """Validate only source column names; no player label value is read."""
    names = tuple(str(value) for value in columns)
    missing = sorted(set(_SNAPSHOT_BASE_COLUMNS) - set(names))
    forbidden = sorted(_LINEUP_OUTCOME_COLUMNS & {
        value.strip().lower() for value in names
    })
    if missing:
        raise BeliefEvidenceError(f"player snapshot missing columns {missing}")
    if forbidden:
        raise BeliefEvidenceError(
            f"player snapshot exposes lineup outcomes {forbidden}"
        )
    body: dict[str, object] = {
        "schema": "corpus-r6-belief-evidence-source-schema-smoke/v1",
        "column_count": len(names),
        "columns_sha256": canonical_sha256(list(names)),
        "required_columns": list(_SNAPSHOT_BASE_COLUMNS),
        "uses_player_outcomes": False,
        "uses_lineup_outcomes": False,
        "values_read": False,
        "passes": True,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def _validate_shard(shard: L1ConditionalBankShard) -> L1ConditionalBankShard:
    if type(shard.season) is not int or shard.season not in CALIBRATION_SEASONS:
        raise BeliefEvidenceError("L1 shard season differs")
    if type(shard.week) is not int or not 1 <= shard.week <= 18:
        raise BeliefEvidenceError("L1 shard week differs")
    players = tuple(str(value) for value in shard.player_ids)
    if not players or any(not value for value in players) or len(set(players)) != len(players):
        raise BeliefEvidenceError("L1 shard player identities differ")
    ordinary = np.asarray(shard.ordinary_draws, dtype=np.float64)
    shootout = np.asarray(shard.shootout_draws, dtype=np.float64)
    if (
        ordinary.ndim != 2
        or ordinary.shape != shootout.shape
        or ordinary.shape[0] != len(players)
        or ordinary.shape[1] < 2
        or not np.isfinite(ordinary).all()
        or not np.isfinite(shootout).all()
    ):
        raise BeliefEvidenceError("L1 shard matrix shape or values differ")
    _identity(shard.source_identity, label="L1 shard")
    return L1ConditionalBankShard(
        season=shard.season,
        week=shard.week,
        player_ids=players,
        ordinary_draws=np.ascontiguousarray(ordinary),
        shootout_draws=np.ascontiguousarray(shootout),
        source_identity=shard.source_identity,
    )


def _team_roles(slate: pd.DataFrame) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for game_id, game in slate.groupby("game_id", sort=True):
        teams = tuple(sorted(str(value) for value in game["team"].unique()))
        if len(teams) != 2:
            raise BeliefEvidenceError(
                f"L1 game {game_id!r} does not contain exactly two teams"
            )
        for team in teams:
            side = game[game["team"].eq(team)]
            if set(str(value) for value in side["opp"].unique()) != {
                value for value in teams if value != team
            }:
                raise BeliefEvidenceError(
                    f"L1 game {game_id!r} opponent mapping differs"
                )
            for position, role in _ROLE_BY_POSITION.items():
                candidates = side[side["pos"].eq(position)].sort_values(
                    ["mean_projection", "gsis_id"],
                    ascending=[False, True],
                    kind="mergesort",
                )
                if candidates.empty:
                    raise BeliefEvidenceError(
                        f"L1 game {game_id!r} team {team!r} lacks {position}"
                    )
                result[(team, role)] = str(candidates.iloc[0]["gsis_id"])
    return result


def _moments(x: np.ndarray, y: np.ndarray) -> dict[str, float | int]:
    left = np.asarray(x, dtype=np.float64).reshape(-1)
    right = np.asarray(y, dtype=np.float64).reshape(-1)
    if left.shape != right.shape or left.size == 0:
        raise BeliefEvidenceError("opposing-WR1 moment vectors do not align")
    return {
        "count": int(left.size),
        "sum_x": float(left.sum(dtype=np.float64)),
        "sum_y": float(right.sum(dtype=np.float64)),
        "sum_x2": float(np.square(left).sum(dtype=np.float64)),
        "sum_y2": float(np.square(right).sum(dtype=np.float64)),
        "sum_xy": float(np.multiply(left, right).sum(dtype=np.float64)),
    }


def build_l1_real_player_evidence_v1(
    *,
    player_snapshot: pd.DataFrame,
    bank_shards: Sequence[L1ConditionalBankShard],
    snapshot_source_identity: Mapping[str, object],
) -> L1RealPlayerEvidence:
    """Extract the exact L1 event probabilities and correlation moments."""
    snapshot = _validate_snapshot(player_snapshot)
    snapshot_identity = _identity(
        snapshot_source_identity, label="player snapshot"
    )
    if isinstance(bank_shards, (str, bytes)) or not isinstance(
        bank_shards, Sequence
    ):
        raise BeliefEvidenceError("L1 bank shards must be an ordered sequence")
    validated = tuple(_validate_shard(value) for value in bank_shards)
    by_slate: dict[tuple[int, int], L1ConditionalBankShard] = {}
    for shard in validated:
        key = (shard.season, shard.week)
        if key in by_slate:
            raise BeliefEvidenceError(f"L1 shard {key} repeats")
        by_slate[key] = shard
    expected_slates = {
        (int(row.season), int(row.week))
        for row in snapshot[["season", "week"]]
        .drop_duplicates()
        .itertuples(index=False)
    }
    if set(by_slate) != expected_slates:
        missing = sorted(expected_slates - set(by_slate))
        extra = sorted(set(by_slate) - expected_slates)
        raise BeliefEvidenceError(
            f"L1 shard slate coverage differs; missing={missing} extra={extra}"
        )

    event_records: list[dict[str, object]] = []
    moment_vectors: dict[tuple[int, str], tuple[list[np.ndarray], list[np.ndarray]]] = {
        (season, component): ([], [])
        for season in CALIBRATION_SEASONS
        for component in ("ordinary", "shootout", "observed")
    }
    shard_identities: dict[str, dict[str, object]] = {}
    world_counts: dict[str, int] = {}
    for season, week in sorted(expected_slates):
        slate = snapshot[
            snapshot["season"].eq(season) & snapshot["week"].eq(week)
        ].copy()
        # World banks intentionally exclude DST; event roles are QB/RB/WR.
        skill = slate[slate["pos"].isin(("QB", "RB", "WR", "TE"))].copy()
        shard = by_slate[(season, week)]
        if set(shard.player_ids) != set(str(value) for value in skill["gsis_id"]):
            raise BeliefEvidenceError(
                f"L1 shard {(season, week)} player support differs"
            )
        row_by_player = {
            player_id: index for index, player_id in enumerate(shard.player_ids)
        }
        roles = _team_roles(skill)
        actual_by_player = skill.set_index("gsis_id")["actual"].to_dict()
        for game_id, game in skill.groupby("game_id", sort=True):
            teams = tuple(sorted(str(value) for value in game["team"].unique()))
            for team in teams:
                sample_id = f"{season}-w{week:02d}-{game_id}-{team}"
                indices = {
                    role: row_by_player[player_id]
                    for (role_team, role), player_id in roles.items()
                    if role_team == team
                }
                actual = {
                    role: float(actual_by_player[player_id])
                    for (role_team, role), player_id in roles.items()
                    if role_team == team
                }
                for metric in L1_METRICS:
                    role_names, threshold = _EVENT_THRESHOLDS[metric]
                    ordinary_total = sum(
                        shard.ordinary_draws[indices[role]] for role in role_names
                    )
                    shootout_total = sum(
                        shard.shootout_draws[indices[role]] for role in role_names
                    )
                    event_records.append({
                        "season": season,
                        "sample_id": sample_id,
                        "metric": metric,
                        "observed_event": int(
                            sum(actual[role] for role in role_names) >= threshold
                        ),
                        "ordinary_probability": float(
                            np.mean(ordinary_total >= threshold)
                        ),
                        "shootout_probability": float(
                            np.mean(shootout_total >= threshold)
                        ),
                    })
            left_team, right_team = teams
            left_id = roles[(left_team, "WR1")]
            right_id = roles[(right_team, "WR1")]
            left_index = row_by_player[left_id]
            right_index = row_by_player[right_id]
            moment_vectors[(season, "ordinary")][0].append(
                shard.ordinary_draws[left_index]
            )
            moment_vectors[(season, "ordinary")][1].append(
                shard.ordinary_draws[right_index]
            )
            moment_vectors[(season, "shootout")][0].append(
                shard.shootout_draws[left_index]
            )
            moment_vectors[(season, "shootout")][1].append(
                shard.shootout_draws[right_index]
            )
            moment_vectors[(season, "observed")][0].append(
                np.asarray([actual_by_player[left_id]], dtype=np.float64)
            )
            moment_vectors[(season, "observed")][1].append(
                np.asarray([actual_by_player[right_id]], dtype=np.float64)
            )
        shard_label = f"{season}-w{week:02d}"
        shard_identities[shard_label] = _identity(
            shard.source_identity, label=f"L1 shard {shard_label}"
        )
        world_counts[shard_label] = int(shard.ordinary_draws.shape[1])

    events = pd.DataFrame(event_records, columns=L1_EVENT_COLUMNS).sort_values(
        ["season", "sample_id", "metric"], kind="mergesort"
    ).reset_index(drop=True)
    moment_records: list[dict[str, object]] = []
    for season in CALIBRATION_SEASONS:
        for component in ("ordinary", "shootout", "observed"):
            x_parts, y_parts = moment_vectors[(season, component)]
            if len(x_parts) < 2 or len(x_parts) != len(y_parts):
                raise BeliefEvidenceError(
                    f"L1 {season} {component} lacks opposing-WR1 support"
                )
            values = _moments(np.concatenate(x_parts), np.concatenate(y_parts))
            moment_records.append({
                "season": season,
                "component": component,
                **values,
            })
    moments = pd.DataFrame(moment_records, columns=L1_MOMENT_COLUMNS).sort_values(
        ["season", "component"], kind="mergesort"
    ).reset_index(drop=True)
    body: dict[str, object] = {
        "schema": L1_EVIDENCE_SCHEMA,
        "snapshot_source_identity": snapshot_identity,
        "bank_source_identities": shard_identities,
        "calibration_seasons": list(CALIBRATION_SEASONS),
        "slate_count": len(expected_slates),
        "event_row_count": len(events),
        "team_game_count": int(events["sample_id"].nunique()),
        "opposing_game_count": int(
            moments[moments["component"].eq("observed")]["count"].sum()
        ),
        "world_counts_by_slate": world_counts,
        "event_evidence_sha256": _records_sha256(events, L1_EVENT_COLUMNS),
        "opposing_wr1_moment_evidence_sha256": _records_sha256(
            moments, L1_MOMENT_COLUMNS
        ),
        "role_resolution": "max-prelock-ordinary-mean-then-gsis-id",
        "uses_player_outcomes": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return L1RealPlayerEvidence(events, moments, body)


def load_pre2023_sunday_main_role_history_v1(
    query: Callable[..., pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Load and label the exact score-free role source through 2022.

    The query retains every regular-season game while previous-state features
    are formed.  Only after those all-game lags exist are label rows restricted
    to the Sunday 1pm/late-afternoon target universe.
    """
    if query is None:
        from ..bq import query_df
        from ..config import settings

        rows = query_df(
            ROLE_HISTORY_SOURCE_SQL.format(
                raw=settings.raw,
                features=settings.features,
            )
        )
    else:
        rows = query(ROLE_HISTORY_SOURCE_SQL)
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        raise BeliefEvidenceError("L2 role source returned no rows")
    forbidden = FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns)
    if forbidden:
        raise BeliefEvidenceError(
            f"L2 role source exposed outcomes {sorted(forbidden)}"
        )
    required = {"game_id", "is_sunday_main", "season", "week", "gsis_id"}
    if missing := required - set(rows.columns):
        raise BeliefEvidenceError(f"L2 role source missing {sorted(missing)}")
    result = rows.copy()
    result["season"] = pd.to_numeric(result["season"], errors="raise").astype(int)
    if set(result["season"]) - set(range(ROLE_SOURCE_FIRST_SEASON, ROLE_SOURCE_LAST_SEASON + 1)):
        raise BeliefEvidenceError("L2 role source season boundary differs")
    result[TARGET] = classify_realized_states(result)
    result = result[result[TARGET].notna()].copy()
    if result.empty:
        raise BeliefEvidenceError("L2 role source produced no usable labels")
    result = add_previous_state(result)
    result = result[result["is_sunday_main"].fillna(False).astype(bool)].copy()
    if result.empty:
        raise BeliefEvidenceError("L2 role source produced no Sunday-main labels")
    return result.sort_values(
        ["season", "week", "team", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)


def _validate_role_history(rows: pd.DataFrame) -> pd.DataFrame:
    required = {
        "gsis_id",
        "season",
        "week",
        "team",
        "position",
        *SHARE_FIELDS,
        *INPUT_FEATURES,
        TARGET,
    }
    if not isinstance(rows, pd.DataFrame) or (missing := required - set(rows.columns)):
        raise BeliefEvidenceError(f"L2 role history missing {sorted(missing)}")
    forbidden = FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns)
    if forbidden:
        raise BeliefEvidenceError(
            f"L2 role history exposed outcomes {sorted(forbidden)}"
        )
    result = rows.copy()
    result["season"] = pd.to_numeric(result["season"], errors="raise").astype(int)
    result["week"] = pd.to_numeric(result["week"], errors="raise").astype(int)
    expected = set(range(ROLE_SOURCE_FIRST_SEASON, ROLE_SOURCE_LAST_SEASON + 1))
    if set(result["season"]) != expected:
        raise BeliefEvidenceError("L2 role history season support differs")
    if result.duplicated(["gsis_id", "season", "week"]).any():
        raise BeliefEvidenceError("L2 role history identities repeat")
    if "is_sunday_main" in result and not result["is_sunday_main"].fillna(False).all():
        raise BeliefEvidenceError("L2 role history contains non-main label rows")
    prepare_transition_frame(result)
    return result.sort_values(
        ["season", "week", "team", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)


def build_l2_real_player_evidence_v1(
    *,
    role_history: pd.DataFrame,
    player_snapshot: pd.DataFrame,
    snapshot_source_identity: Mapping[str, object],
    role_source_identity: Mapping[str, object],
) -> L2RealPlayerEvidence:
    """Join exact CAL19/WF21/HOLD22 role labels to player residuals."""
    source_roles = _validate_role_history(role_history)
    snapshot = _validate_snapshot(player_snapshot)
    snapshot_identity = _identity(
        snapshot_source_identity, label="player snapshot"
    )
    role_identity = _identity(role_source_identity, label="role source")
    skill = snapshot[snapshot["pos"].isin(("RB", "WR", "TE"))].copy()
    observed = skill[[
        "gsis_id", "season", "week", "pos", "mean_projection", "actual"
    ]].rename(columns={"pos": "snapshot_position"})
    # The immutable PIT-clean snapshot is the exact ordinary-mean spine.
    # Some warehouse Sunday-main training rows were not research-eligible in
    # that freeze (three in 2021 and 213 in 2022 in the 2026-08-28 census).
    # They cannot acquire a different, post-hoc ordinary mean.  Intersect the
    # *role history* with the frozen spine in the three label seasons, while
    # preserving complete 2018/2020 main-slate training rows.  This is an
    # explicit population boundary, not a left-join imputation.
    calibration_roles = source_roles[
        source_roles["season"].isin(CALIBRATION_SEASONS)
    ].copy()
    role_match = calibration_roles.merge(
        observed[["gsis_id", "season", "week", "snapshot_position"]],
        on=["gsis_id", "season", "week"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    matched_role = role_match["_merge"].eq("both")
    position_disagreement = matched_role & ~role_match["position"].astype(str).eq(
        role_match["snapshot_position"].astype(str)
    )
    if position_disagreement.any():
        raise BeliefEvidenceError("L2 role/snapshot positions disagree")
    matched_keys = role_match.loc[
        matched_role, ["gsis_id", "season", "week"]
    ]
    filtered_calibration_roles = calibration_roles.merge(
        matched_keys,
        on=["gsis_id", "season", "week"],
        how="inner",
        validate="one_to_one",
    )
    prior_roles = source_roles[
        ~source_roles["season"].isin(CALIBRATION_SEASONS)
    ]
    roles = pd.concat(
        [prior_roles, filtered_calibration_roles], ignore_index=True
    ).sort_values(
        ["season", "week", "team", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)
    target = roles[roles["season"].isin(CALIBRATION_SEASONS)].copy()
    expected = target[["gsis_id", "season", "week", "position"]].copy()
    joined = expected.merge(
        observed,
        on=["gsis_id", "season", "week"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing = joined[~joined["_merge"].eq("both")][
        ["gsis_id", "season", "week"]
    ]
    if not missing.empty:
        example = missing.head(5).to_dict("records")
        raise BeliefEvidenceError(
            "L2 role labels lack frozen ordinary/player-actual rows; "
            f"missing={len(missing)} examples={example}"
        )
    if not joined["position"].astype(str).eq(
        joined["snapshot_position"].astype(str)
    ).all():
        raise BeliefEvidenceError("L2 role/snapshot positions disagree")
    residual = joined[["gsis_id", "season", "week"]].copy()
    residual["ordinary_mean"] = joined["mean_projection"].to_numpy(dtype=float)
    residual["player_actual_points"] = joined["actual"].to_numpy(dtype=float)
    residual = residual.loc[:, list(L2_RESIDUAL_COLUMNS)].sort_values(
        ["season", "week", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)
    body: dict[str, object] = {
        "schema": L2_EVIDENCE_SCHEMA,
        "snapshot_source_identity": snapshot_identity,
        "role_source_identity": role_identity,
        "role_source_sql_sha256": ROLE_HISTORY_SOURCE_SQL_SHA256,
        "role_source_first_season": ROLE_SOURCE_FIRST_SEASON,
        "role_source_last_season": ROLE_SOURCE_LAST_SEASON,
        "role_row_count_before_snapshot_intersection": len(source_roles),
        "role_row_count": len(roles),
        "residual_row_count": len(residual),
        "calibration_role_rows_excluded_without_frozen_ordinary_mean": int(
            (~matched_role).sum()
        ),
        "snapshot_skill_rows_without_usable_role_label": int(
            len(observed) - len(filtered_calibration_roles)
        ),
        "role_history_sha256": transition_frame_sha256(roles),
        "residual_history_sha256": _records_sha256(
            residual, L2_RESIDUAL_COLUMNS
        ),
        "target_universe": "regular-season-sunday-main-1300-to-1900",
        "calibration_population_spine": "immutable-pit-clean-player-snapshot",
        "previous_state_formed_before_target_universe_filter": True,
        "residual_definition": "player-actual-minus-prelock-ordinary-mean",
        "uses_player_outcomes": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return L2RealPlayerEvidence(roles, residual, body)


__all__ = [
    "BeliefEvidenceError",
    "L1_BANK_MANIFEST_SCHEMA",
    "L1ConditionalBankShard",
    "L1RealPlayerEvidence",
    "L2RealPlayerEvidence",
    "ROLE_HISTORY_SOURCE_SQL",
    "ROLE_HISTORY_SOURCE_SQL_SHA256",
    "build_l1_real_player_evidence_v1",
    "build_l2_real_player_evidence_v1",
    "load_pre2023_sunday_main_role_history_v1",
    "local_file_identity",
    "snapshot_schema_smoke_v1",
]
