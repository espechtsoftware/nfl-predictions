"""RB and QB matchup annotation builders (families two and three).

Mirrors the frozen receiver-family pattern with position-specific
components; the percentile/edge/easy laws are IDENTICAL constants
(within-slate percentiles over eligible players, at least two supported
components, 0.75 edge / 0.40 floor).

RB components (larger = offense-favorable):
  1. opponent rushing DK allowed per game to the RB's consensus role;
  2. opponent RB receiving DK allowed per game to that role (checkdowns);
  3. opponent run-defense EPA allowed per attempt (unit context).

QB components:
  1. opponent full-QB-DK allowed per game;
  2. opponent pressures per game, NEGATED before ranking (fewer
     pressures is offense-favorable);
  3. opponent DB yards-per-target allowed (secondary quality).

Both families are PROVISIONAL until their own outcome-blind reality
smokes freeze them. Missing stays null with registered reasons; no
target-week outcome is read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from nfl_dfs.research.receiver_matchup_annotations import (
    EASY_COVERAGE_COMPONENT_FLOOR,
    EASY_COVERAGE_EDGE_MINIMUM,
    MINIMUM_SUPPORTED_COMPONENTS,
    ReceiverMatchupAnnotationError,
    _percentiles,
)
from nfl_dfs.research.receiver_matchup_contract import (
    MetricFamily,
    ReceiverMatchupContractError,
    build_annotation_object,
    qb_matchup_family_v1,
    rb_matchup_family_v1,
)


RB_COMPONENTS = (
    "rushing_concession",
    "receiving_concession",
    "run_context",
)
QB_COMPONENTS = (
    "qb_concession",
    "pressure_inverted",
    "secondary",
)


@dataclass(frozen=True, slots=True)
class RbQbSlateInputs:
    """Slate-week inputs for the RB and QB families (plain dict rows)."""

    season: int
    week: int
    rb_role_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    rb_concession_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    defense_context_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    secondary_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    opponent_by_team: Mapping[str, str] = field(default_factory=dict)


def _fail(message: str) -> None:
    raise ReceiverMatchupAnnotationError(message)


def _eligible(
    catalog_players: Sequence[Mapping[str, object]],
    positions: tuple[str, ...],
    opponent_by_team: Mapping[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for player in catalog_players:
        position = str(player.get("pos", ""))
        gsis_id = str(player.get("id", ""))
        if position not in positions or not gsis_id:
            continue
        if gsis_id in seen:
            _fail(f"catalog repeats player {gsis_id!r}")
        seen.add(gsis_id)
        team = str(player.get("team", ""))
        rows.append({
            "gsis_id": gsis_id,
            "team": team,
            "opponent": opponent_by_team.get(team),
        })
    if not rows:
        _fail("slate catalog has no eligible players for this family")
    return rows


def _edge_fields(
    component_percentiles: Mapping[str, float],
    easy_field: str,
) -> tuple[dict[str, object], dict[str, str]]:
    values: dict[str, object] = {
        "matchup_component_count": len(component_percentiles),
    }
    missing: dict[str, str] = {}
    if len(component_percentiles) >= MINIMUM_SUPPORTED_COMPONENTS:
        edge = sum(component_percentiles.values()) / len(
            component_percentiles
        )
        values["matchup_edge_score"] = edge
        values[easy_field] = (
            edge >= EASY_COVERAGE_EDGE_MINIMUM
            and min(component_percentiles.values())
            >= EASY_COVERAGE_COMPONENT_FLOOR
        )
    else:
        values["matchup_edge_score"] = None
        values[easy_field] = None
        missing["matchup_edge_score"] = "below-support-threshold"
        missing[easy_field] = "below-support-threshold"
    return values, missing


def build_rb_matchup_rows(
    inputs: RbQbSlateInputs,
    catalog_players: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    role_by_id = {str(row["gsis_id"]): row for row in inputs.rb_role_rows}
    concession = {
        (str(row["defense"]), str(row["role_label"])): row
        for row in inputs.rb_concession_rows
        if row.get("concession_supported") is True
    }
    context = {
        str(row["defense"]): row
        for row in inputs.defense_context_rows
        if row.get("run_context_supported") is True
    }
    eligible = _eligible(
        catalog_players, ("RB",), inputs.opponent_by_team
    )
    raw: dict[str, dict[str, float]] = {
        name: {} for name in RB_COMPONENTS
    }
    for row in eligible:
        gsis_id = str(row["gsis_id"])
        opponent = row["opponent"]
        if opponent is None:
            continue
        role = role_by_id.get(gsis_id)
        if role is not None and role.get("role_supported") is True:
            matched = concession.get((str(opponent), str(role["role_label"])))
            if matched is not None:
                rushing = matched.get("rushing_dk_allowed_per_game_l8")
                receiving = matched.get("receiving_dk_allowed_per_game_l8")
                if rushing is not None:
                    raw["rushing_concession"][gsis_id] = float(rushing)
                if receiving is not None:
                    raw["receiving_concession"][gsis_id] = float(receiving)
        unit = context.get(str(opponent))
        if unit is not None and unit.get(
            "rdef_epa_per_attempt_l8"
        ) is not None:
            raw["run_context"][gsis_id] = float(
                unit["rdef_epa_per_attempt_l8"]
            )
    percentiles = {
        name: _percentiles(values) for name, values in raw.items()
    }
    annotation_rows: list[dict[str, object]] = []
    for row in eligible:
        gsis_id = str(row["gsis_id"])
        opponent = row["opponent"]
        opponent_reason = (
            "source-absent" if opponent is None
            else "below-support-threshold"
        )
        role = role_by_id.get(gsis_id)
        values: dict[str, object] = {}
        missing: dict[str, str] = {}
        supported = role is not None and role.get("role_supported") is True
        values["role_supported"] = bool(supported)
        values["role_label"] = (
            str(role["role_label"]) if supported else None
        )
        values["role_consensus_score"] = (
            float(role["role_consensus_score"])
            if role is not None
            and role.get("role_consensus_score") is not None
            else None
        )
        values["role_component_count"] = (
            int(role["role_component_count"])
            if role is not None
            and role.get("role_component_count") is not None
            else None
        )
        if values["role_label"] is None:
            missing["role_label"] = (
                "source-absent" if role is None
                else "below-support-threshold"
            )
        if values["role_consensus_score"] is None:
            missing["role_consensus_score"] = "source-absent"
        if values["role_component_count"] is None:
            missing["role_component_count"] = "source-absent"

        rushing = raw["rushing_concession"].get(gsis_id)
        receiving = raw["receiving_concession"].get(gsis_id)
        values["opponent_rushing_concession_l8"] = rushing
        values["opponent_receiving_concession_l8"] = receiving
        if rushing is None:
            missing["opponent_rushing_concession_l8"] = opponent_reason
        if receiving is None:
            missing["opponent_receiving_concession_l8"] = opponent_reason
        unit = (
            None if opponent is None else context.get(str(opponent))
        )
        epa = None if unit is None else unit.get("rdef_epa_per_attempt_l8")
        boom = None if unit is None else unit.get("rdef_boom_rate_l8")
        values["opponent_rdef_epa_per_attempt_l8"] = (
            None if epa is None else float(epa)
        )
        values["opponent_rdef_boom_rate_l8"] = (
            None if boom is None else float(boom)
        )
        if epa is None:
            missing["opponent_rdef_epa_per_attempt_l8"] = opponent_reason
        if boom is None:
            missing["opponent_rdef_boom_rate_l8"] = opponent_reason

        component_percentiles = {
            name: percentiles[name][gsis_id]
            for name in RB_COMPONENTS
            if gsis_id in percentiles[name]
        }
        edge_values, edge_missing = _edge_fields(
            component_percentiles, "easy_ground_matchup_v1"
        )
        values.update(edge_values)
        missing.update(edge_missing)
        annotation_rows.append({
            "player_id": gsis_id,
            "values": values,
            "missing": {
                name: reason for name, reason in missing.items()
                if values.get(name) is None and name in values
            },
        })
    return annotation_rows


def build_qb_matchup_rows(
    inputs: RbQbSlateInputs,
    catalog_players: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    context = {
        str(row["defense"]): row for row in inputs.defense_context_rows
    }
    secondary = {
        str(row["team"]): row
        for row in inputs.secondary_rows
        if row.get("db_ypt_allowed_l6") is not None
    }
    eligible = _eligible(
        catalog_players, ("QB",), inputs.opponent_by_team
    )
    raw: dict[str, dict[str, float]] = {
        name: {} for name in QB_COMPONENTS
    }
    for row in eligible:
        gsis_id = str(row["gsis_id"])
        opponent = row["opponent"]
        if opponent is None:
            continue
        unit = context.get(str(opponent))
        if unit is not None:
            if (
                unit.get("qb_concession_supported") is True
                and unit.get("qb_dk_allowed_per_game_l8") is not None
            ):
                raw["qb_concession"][gsis_id] = float(
                    unit["qb_dk_allowed_per_game_l8"]
                )
            if (
                unit.get("pass_rush_supported") is True
                and unit.get("pressures_per_game_l8") is not None
            ):
                raw["pressure_inverted"][gsis_id] = -float(
                    unit["pressures_per_game_l8"]
                )
        cover = secondary.get(str(opponent))
        if cover is not None:
            raw["secondary"][gsis_id] = float(cover["db_ypt_allowed_l6"])
    percentiles = {
        name: _percentiles(values) for name, values in raw.items()
    }
    annotation_rows: list[dict[str, object]] = []
    for row in eligible:
        gsis_id = str(row["gsis_id"])
        opponent = row["opponent"]
        opponent_reason = (
            "source-absent" if opponent is None
            else "below-support-threshold"
        )
        unit = None if opponent is None else context.get(str(opponent))
        cover = None if opponent is None else secondary.get(str(opponent))
        values: dict[str, object] = {}
        missing: dict[str, str] = {}
        concession = raw["qb_concession"].get(gsis_id)
        values["opponent_qb_dk_concession_l8"] = concession
        if concession is None:
            missing["opponent_qb_dk_concession_l8"] = opponent_reason
        pressures = (
            None if unit is None else unit.get("pressures_per_game_l8")
        )
        sacks = None if unit is None else unit.get("sacks_per_game_l8")
        values["opponent_pressures_per_game_l8"] = (
            None if pressures is None else float(pressures)
        )
        values["opponent_sacks_per_game_l8"] = (
            None if sacks is None else float(sacks)
        )
        if pressures is None:
            missing["opponent_pressures_per_game_l8"] = opponent_reason
        if sacks is None:
            missing["opponent_sacks_per_game_l8"] = opponent_reason
        ypt = None if cover is None else cover.get("db_ypt_allowed_l6")
        values["opponent_secondary_ypt_allowed_l6"] = (
            None if ypt is None else float(ypt)
        )
        if ypt is None:
            missing["opponent_secondary_ypt_allowed_l6"] = opponent_reason
        component_percentiles = {
            name: percentiles[name][gsis_id]
            for name in QB_COMPONENTS
            if gsis_id in percentiles[name]
        }
        edge_values, edge_missing = _edge_fields(
            component_percentiles, "easy_pass_matchup_v1"
        )
        values.update(edge_values)
        missing.update(edge_missing)
        annotation_rows.append({
            "player_id": gsis_id,
            "values": values,
            "missing": {
                name: reason for name, reason in missing.items()
                if values.get(name) is None and name in values
            },
        })
    return annotation_rows


def build_family_annotation_object(
    *,
    family: MetricFamily,
    rows: Sequence[Mapping[str, object]],
    task_id: str,
    slate_id: str,
    lock_time_utc: str,
    maximum_source_time_utc: str,
    player_catalog_identity: Mapping[str, object],
    source_identities: Mapping[str, Mapping[str, object]],
    created_at_utc: str,
) -> dict[str, object]:
    try:
        return build_annotation_object(
            family=family,
            task_id=task_id,
            slate_id=slate_id,
            lock_time_utc=lock_time_utc,
            maximum_source_time_utc=maximum_source_time_utc,
            player_catalog_identity=player_catalog_identity,
            source_identities=source_identities,
            rows=rows,
            created_at_utc=created_at_utc,
        )
    except ReceiverMatchupContractError as exc:
        raise ReceiverMatchupAnnotationError(
            f"annotation rows differ from the family contract: {exc}"
        ) from exc


def fetch_rb_qb_slate_inputs(season: int, week: int) -> RbQbSlateInputs:
    """Read the built RB/QB PIT layers for one slate week from BigQuery."""
    from nfl_dfs import bq
    from nfl_dfs.research.receiver_matchup_annotations import _records

    features = bq.settings.features
    raw = bq.settings.raw
    params = {"season": season, "week": week}
    rb_roles = _records(bq.query_df(
        f"SELECT gsis_id, team, role_label, role_consensus_score, "
        f"role_component_count, role_supported "
        f"FROM `{features}.rb_week_role_pit` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    rb_concessions = _records(bq.query_df(
        f"SELECT defense, role_label, rushing_dk_allowed_per_game_l8, "
        f"receiving_dk_allowed_per_game_l8, concession_supported "
        f"FROM `{features}.defense_rb_role_concession_pit` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    defense_context = _records(bq.query_df(
        f"SELECT defense, rdef_epa_per_attempt_l8, rdef_boom_rate_l8, "
        f"run_context_supported, pressures_per_game_l8, sacks_per_game_l8, "
        f"pass_rush_supported, qb_dk_allowed_per_game_l8, "
        f"qb_concession_supported "
        f"FROM `{features}.team_defense_context_pit` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    secondary = _records(bq.query_df(
        f"SELECT team, db_ypt_allowed_l6 "
        f"FROM `{features}.defense_week_coverage` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    schedule = _records(bq.query_df(
        f"SELECT home_team, away_team FROM `{raw}.schedules` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    opponent_by_team: dict[str, str] = {}
    for game in schedule:
        home = str(game["home_team"])
        away = str(game["away_team"])
        opponent_by_team[home] = away
        opponent_by_team[away] = home
    return RbQbSlateInputs(
        season=season,
        week=week,
        rb_role_rows=rb_roles,
        rb_concession_rows=rb_concessions,
        defense_context_rows=defense_context,
        secondary_rows=secondary,
        opponent_by_team=opponent_by_team,
    )


__all__ = [
    "QB_COMPONENTS",
    "RB_COMPONENTS",
    "RbQbSlateInputs",
    "build_family_annotation_object",
    "build_qb_matchup_rows",
    "build_rb_matchup_rows",
    "fetch_rb_qb_slate_inputs",
    "qb_matchup_family_v1",
    "rb_matchup_family_v1",
]
