"""P3 receiver-matchup annotation builder (matchup plan §5.5).

Joins the built PIT layers — receiver roles (017l), defense role
concessions (017m), defender/alignment quality (017n), FantasyPoints
prior-window alignment, and FantasyPoints prior-season shell fit — into
`receiver-matchup/v1` annotation rows for one slate's player catalog,
through the fail-closed metric-family contract
(`receiver_matchup_contract`).

FROZEN v1 component laws (fixed before any outcome is read; plan §5.5):

1. role concession: the opponent defense's receiving-DK allowed per game
   over its last eight prior games to the receiver's consensus pre-lock
   role (supported 017l role x supported 017m concession row).
2. alignment vulnerability: the receiver's prior-window wide/slot route
   mix crossed with the opponent's exposure-weighted defender
   DK-per-target allowed per alignment (unit-level view over ALL
   supported defenders from 017n).
3. defender workload quality: the mean shrunk DK-per-target allowed of
   the opponent's top-two workload defenders for the receiver's DOMINANT
   alignment (who the receiver is most likely to see; still
   inferred-from-prior-alignment-workload, never an assignment claim).
4. shell fit: (man FPRR - zone FPRR) x (opponent man rate - league mean
   man rate), all prior-season FantasyPoints values.

Each supported component becomes a within-slate percentile over the
slate's eligible WR/TE receivers (larger = more favorable to the
offense). `matchup_edge_score` is the unweighted mean of supported
component percentiles and requires at least two supported components;
`easy_coverage_v1` is true only when the edge is at least 0.75 and no
supported component percentile is below 0.40 (plan's frozen law).

Missing stays missing with a registered reason — never zero, never
"average". Target-week outcomes are never read. The family stays
PROVISIONAL until the P3 outcome-blind reality smoke (real task-0
catalog plus one governed winner slate) freezes it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from nfl_dfs.research.receiver_matchup_contract import (
    MetricFamily,
    ReceiverMatchupContractError,
    build_annotation_object,
    receiver_matchup_family_v1,
)


ELIGIBLE_POSITIONS = ("WR", "TE")
COMPONENT_NAMES = (
    "role_concession",
    "alignment_vulnerability",
    "defender_workload_quality",
    "shell_fit",
)
EASY_COVERAGE_EDGE_MINIMUM = 0.75
EASY_COVERAGE_COMPONENT_FLOOR = 0.40
MINIMUM_SUPPORTED_COMPONENTS = 2


class ReceiverMatchupAnnotationError(ValueError):
    """Raised when slate inputs differ from the annotation laws."""


def _fail(message: str) -> None:
    raise ReceiverMatchupAnnotationError(message)


@dataclass(frozen=True, slots=True)
class SlateMatchupInputs:
    """In-memory slate inputs; every list row is a plain string-keyed dict.

    role_rows: 017l rows for (season, week) keyed by gsis_id.
    concession_rows: 017m rows for (season, week): defense, role_label,
        receiving_dk_allowed_per_game_l8, concession_supported.
    defender_rows: 017n rows for (season, week): defense, alignment,
        defender_exposure_weight, dk_per_target_allowed_shrunk_l8,
        workload_rank, defender_supported.
    alignment_rows: FantasyPoints l4 rows: gsis_id, player_wide_share,
        alignment_supported.
    shell_receiver_rows: FantasyPoints prior-season rows: gsis_id,
        man_fprr, zone_fprr.
    shell_defense_rows: FantasyPoints prior-season defense rows: team,
        def_man_rate.
    opponent_by_team: pre-lock schedule map team -> opponent for the
        slate week.
    """

    season: int
    week: int
    role_rows: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    concession_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    defender_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    alignment_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    shell_receiver_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    shell_defense_rows: Sequence[Mapping[str, object]] = field(
        default_factory=tuple
    )
    opponent_by_team: Mapping[str, str] = field(default_factory=dict)


def _percentiles(values: Mapping[str, float]) -> dict[str, float]:
    """PERCENT_RANK over supported values: strictly-less count / (n-1)."""
    if not values:
        return {}
    ordered = sorted(values.values())
    n = len(ordered)
    result: dict[str, float] = {}
    for key, value in values.items():
        if n == 1:
            result[key] = 0.0
            continue
        below = 0
        for other in ordered:
            if other < value:
                below += 1
            else:
                break
        result[key] = below / (n - 1)
    return result


def _defense_alignment_view(
    defender_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    """Exposure-weighted unit vulnerability and top-two defender quality."""
    unit_num: dict[tuple[str, str], float] = {}
    unit_den: dict[tuple[str, str], float] = {}
    top_two: dict[tuple[str, str], list[tuple[int, float]]] = {}
    for row in defender_rows:
        if row.get("defender_supported") is not True:
            continue
        key = (str(row["defense"]), str(row["alignment"]))
        weight = row.get("defender_exposure_weight")
        rate = row.get("dk_per_target_allowed_shrunk_l8")
        rank = row.get("workload_rank")
        if weight is None or rate is None:
            continue
        unit_num[key] = unit_num.get(key, 0.0) + float(weight) * float(rate)
        unit_den[key] = unit_den.get(key, 0.0) + float(weight)
        if isinstance(rank, int) and rank <= 2:
            top_two.setdefault(key, []).append((rank, float(rate)))
    unit = {
        key: unit_num[key] / unit_den[key]
        for key in unit_num
        if unit_den.get(key)
    }
    top = {
        key: sum(rate for _, rate in sorted(rows)) / len(rows)
        for key, rows in top_two.items()
    }
    return unit, top


def build_matchup_rows(
    inputs: SlateMatchupInputs,
    catalog_players: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Compute annotation rows for the slate catalog's WR/TE receivers."""
    role_by_id = {
        str(row["gsis_id"]): row for row in inputs.role_rows
    }
    concession = {
        (str(row["defense"]), str(row["role_label"])): row
        for row in inputs.concession_rows
        if row.get("concession_supported") is True
    }
    unit_vulnerability, top_defender_quality = _defense_alignment_view(
        inputs.defender_rows
    )
    alignment_by_id = {
        str(row["gsis_id"]): row
        for row in inputs.alignment_rows
        if row.get("alignment_supported") is True
        and row.get("player_wide_share") is not None
    }
    shell_by_id = {
        str(row["gsis_id"]): row
        for row in inputs.shell_receiver_rows
        if row.get("man_fprr") is not None
        and row.get("zone_fprr") is not None
    }
    man_rates = [
        float(row["def_man_rate"])
        for row in inputs.shell_defense_rows
        if row.get("def_man_rate") is not None
    ]
    league_man_rate = (
        sum(man_rates) / len(man_rates) if man_rates else None
    )
    shell_defense = {
        str(row["team"]): row
        for row in inputs.shell_defense_rows
        if row.get("def_man_rate") is not None
    }

    eligible: list[dict[str, object]] = []
    seen: set[str] = set()
    for player in catalog_players:
        position = str(player.get("pos", ""))
        gsis_id = str(player.get("id", ""))
        if position not in ELIGIBLE_POSITIONS or not gsis_id:
            continue
        if gsis_id in seen:
            _fail(f"catalog repeats receiver {gsis_id!r}")
        seen.add(gsis_id)
        team = str(player.get("team", ""))
        opponent = inputs.opponent_by_team.get(team)
        eligible.append({
            "gsis_id": gsis_id,
            "team": team,
            "opponent": opponent,
        })
    if not eligible:
        _fail("slate catalog has no eligible WR/TE receivers")

    raw_components: dict[str, dict[str, float]] = {
        name: {} for name in COMPONENT_NAMES
    }
    contexts: dict[str, dict[str, object]] = {}
    for row in eligible:
        gsis_id = str(row["gsis_id"])
        opponent = row["opponent"]
        role = role_by_id.get(gsis_id)
        context: dict[str, object] = {
            "role": role,
            "opponent": opponent,
            "missing": {},
        }
        contexts[gsis_id] = context
        if opponent is None:
            context["missing"]["opponent"] = "source-absent"
            continue
        opponent_key = str(opponent)

        if role is not None and role.get("role_supported") is True:
            matched = concession.get(
                (opponent_key, str(role.get("role_label")))
            )
            if matched is not None and matched.get(
                "receiving_dk_allowed_per_game_l8"
            ) is not None:
                raw_components["role_concession"][gsis_id] = float(
                    matched["receiving_dk_allowed_per_game_l8"]
                )

        alignment = alignment_by_id.get(gsis_id)
        wide = unit_vulnerability.get((opponent_key, "wide"))
        slot = unit_vulnerability.get((opponent_key, "slot"))
        if alignment is not None and wide is not None and slot is not None:
            wide_share = float(alignment["player_wide_share"])
            raw_components["alignment_vulnerability"][gsis_id] = (
                wide_share * wide + (1.0 - wide_share) * slot
            )
        if alignment is not None:
            dominant = (
                "wide"
                if float(alignment["player_wide_share"]) >= 0.5
                else "slot"
            )
            top = top_defender_quality.get((opponent_key, dominant))
            if top is not None:
                raw_components["defender_workload_quality"][gsis_id] = top

        shell = shell_by_id.get(gsis_id)
        defense_shell = shell_defense.get(opponent_key)
        if (
            shell is not None
            and defense_shell is not None
            and league_man_rate is not None
        ):
            raw_components["shell_fit"][gsis_id] = (
                float(shell["man_fprr"]) - float(shell["zone_fprr"])
            ) * (
                float(defense_shell["def_man_rate"]) - league_man_rate
            )

    percentiles = {
        name: _percentiles(values)
        for name, values in raw_components.items()
    }

    annotation_rows: list[dict[str, object]] = []
    for row in eligible:
        gsis_id = str(row["gsis_id"])
        context = contexts[gsis_id]
        role = context["role"]
        missing: dict[str, str] = dict(context["missing"])
        values: dict[str, object] = {}

        if role is None:
            values.update({
                "role_label": None,
                "role_consensus_score": None,
                "role_component_count": None,
                "role_supported": False,
            })
            missing.update({
                "role_label": "source-absent",
                "role_consensus_score": "source-absent",
                "role_component_count": "source-absent",
            })
        else:
            supported = role.get("role_supported") is True
            values.update({
                "role_label": (
                    str(role["role_label"]) if supported else None
                ),
                "role_consensus_score": (
                    float(role["role_consensus_score"])
                    if role.get("role_consensus_score") is not None
                    else None
                ),
                "role_component_count": (
                    int(role["role_component_count"])
                    if role.get("role_component_count") is not None
                    else None
                ),
                "role_supported": supported,
            })
            if values["role_label"] is None:
                missing["role_label"] = "below-support-threshold"
            if values["role_consensus_score"] is None:
                missing["role_consensus_score"] = "source-absent"
            if values["role_component_count"] is None:
                missing["role_component_count"] = "source-absent"

        component_percentiles: dict[str, float] = {}
        for name in COMPONENT_NAMES:
            value = percentiles[name].get(gsis_id)
            if value is not None:
                component_percentiles[name] = value

        raw_role = raw_components["role_concession"].get(gsis_id)
        values["opponent_role_concession_l8"] = raw_role
        if raw_role is None:
            missing["opponent_role_concession_l8"] = (
                missing.get("opponent", "below-support-threshold")
            )
        values["opponent_role_concession_over_expectation_l8"] = None
        missing["opponent_role_concession_over_expectation_l8"] = (
            "source-absent"
        )

        alignment = alignment_by_id.get(gsis_id)
        if alignment is None:
            values["wide_route_share_l4"] = None
            values["slot_route_share_l4"] = None
            missing["wide_route_share_l4"] = "vendor-window-incomplete"
            missing["slot_route_share_l4"] = "vendor-window-incomplete"
        else:
            wide_share = float(alignment["player_wide_share"])
            values["wide_route_share_l4"] = wide_share
            values["slot_route_share_l4"] = 1.0 - wide_share

        opponent = context["opponent"]
        opponent_key = None if opponent is None else str(opponent)
        wide_vulnerability = (
            None if opponent_key is None
            else unit_vulnerability.get((opponent_key, "wide"))
        )
        slot_vulnerability = (
            None if opponent_key is None
            else unit_vulnerability.get((opponent_key, "slot"))
        )
        values["defense_wide_vulnerability_l8"] = wide_vulnerability
        values["defense_slot_vulnerability_l8"] = slot_vulnerability
        if wide_vulnerability is None:
            missing["defense_wide_vulnerability_l8"] = (
                missing.get("opponent", "below-support-threshold")
            )
        if slot_vulnerability is None:
            missing["defense_slot_vulnerability_l8"] = (
                missing.get("opponent", "below-support-threshold")
            )

        top_quality = raw_components["defender_workload_quality"].get(
            gsis_id
        )
        values["defender_workload_quality_l8"] = top_quality
        values["defender_evidence_grain"] = (
            "sis-defender-alignment" if top_quality is not None else None
        )
        if top_quality is None:
            reason = missing.get("opponent", "below-support-threshold")
            missing["defender_workload_quality_l8"] = reason
            missing["defender_evidence_grain"] = reason
        values["top_workload_defender_out"] = None
        missing["top_workload_defender_out"] = "source-absent"

        shell_value = raw_components["shell_fit"].get(gsis_id)
        values["shell_fit_edge_prior_season"] = shell_value
        if shell_value is None:
            missing["shell_fit_edge_prior_season"] = (
                "vendor-window-incomplete"
            )

        values["matchup_component_count"] = len(component_percentiles)
        if len(component_percentiles) >= MINIMUM_SUPPORTED_COMPONENTS:
            edge = sum(component_percentiles.values()) / len(
                component_percentiles
            )
            values["matchup_edge_score"] = edge
            values["easy_coverage_v1"] = (
                edge >= EASY_COVERAGE_EDGE_MINIMUM
                and min(component_percentiles.values())
                >= EASY_COVERAGE_COMPONENT_FLOOR
            )
        else:
            values["matchup_edge_score"] = None
            values["easy_coverage_v1"] = None
            missing["matchup_edge_score"] = "below-support-threshold"
            missing["easy_coverage_v1"] = "below-support-threshold"

        missing.pop("opponent", None)
        annotation_rows.append({
            "player_id": gsis_id,
            "values": values,
            "missing": {
                name: reason
                for name, reason in missing.items()
                if values.get(name) is None and name in values
            },
        })
    return annotation_rows


def build_slate_annotation_object(
    *,
    inputs: SlateMatchupInputs,
    catalog_players: Sequence[Mapping[str, object]],
    family: MetricFamily | None = None,
    task_id: str,
    slate_id: str,
    lock_time_utc: str,
    maximum_source_time_utc: str,
    player_catalog_identity: Mapping[str, object],
    source_identities: Mapping[str, Mapping[str, object]],
    created_at_utc: str,
) -> dict[str, object]:
    """Build the create-once annotation object through the contract."""
    rows = build_matchup_rows(inputs, catalog_players)
    try:
        return build_annotation_object(
            family=family or receiver_matchup_family_v1(),
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


def _native(value: object) -> object:
    """Convert BigQuery/pandas scalars to plain Python; NaN becomes None."""
    if value is None:
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and value != value:
        return None
    return value


def _records(frame: object) -> tuple[dict[str, object], ...]:
    return tuple(
        {key: _native(value) for key, value in row.items()}
        for row in frame.to_dict("records")
    )


def fetch_slate_inputs(season: int, week: int) -> SlateMatchupInputs:
    """Read the built PIT layers for one slate week from BigQuery."""
    from nfl_dfs import bq

    features = bq.settings.features
    raw = bq.settings.raw
    params = {"season": season, "week": week}
    role_rows = _records(bq.query_df(
        f"SELECT gsis_id, team, role_label, role_consensus_score, "
        f"role_component_count, role_supported "
        f"FROM `{features}.receiver_week_role_pit` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    concession_rows = _records(bq.query_df(
        f"SELECT defense, role_label, receiving_dk_allowed_per_game_l8, "
        f"concession_supported "
        f"FROM `{features}.defense_receiver_role_concession_pit` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    defender_rows = _records(bq.query_df(
        f"SELECT defense, alignment, defender_exposure_weight, "
        f"dk_per_target_allowed_shrunk_l8, workload_rank, "
        f"defender_supported "
        f"FROM `{features}.defender_alignment_quality_week_pit` "
        "WHERE season = @season AND week = @week",
        params,
    ))
    alignment_rows = _records(bq.query_df(
        f"SELECT gsis_id, player_wide_share, alignment_supported "
        f"FROM `{raw}.fantasy_points_alignment_player_l4` "
        "WHERE season = @season AND target_week = @week "
        "AND gsis_id IS NOT NULL",
        params,
    ))
    shell_receiver_rows = _records(bq.query_df(
        f"SELECT gsis_id, man_fprr, zone_fprr "
        f"FROM `{raw}.fantasy_points_receiver_coverage_prior` "
        "WHERE season = @season AND gsis_id IS NOT NULL",
        {"season": season},
    ))
    shell_defense_rows = _records(bq.query_df(
        f"SELECT team, def_man_rate "
        f"FROM `{raw}.fantasy_points_defense_coverage_prior` "
        "WHERE season = @season",
        {"season": season},
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
    return SlateMatchupInputs(
        season=season,
        week=week,
        role_rows=role_rows,
        concession_rows=concession_rows,
        defender_rows=defender_rows,
        alignment_rows=alignment_rows,
        shell_receiver_rows=shell_receiver_rows,
        shell_defense_rows=shell_defense_rows,
        opponent_by_team=opponent_by_team,
    )


__all__ = [
    "COMPONENT_NAMES",
    "EASY_COVERAGE_COMPONENT_FLOOR",
    "EASY_COVERAGE_EDGE_MINIMUM",
    "ELIGIBLE_POSITIONS",
    "MINIMUM_SUPPORTED_COMPONENTS",
    "ReceiverMatchupAnnotationError",
    "SlateMatchupInputs",
    "build_matchup_rows",
    "build_slate_annotation_object",
    "fetch_slate_inputs",
]
