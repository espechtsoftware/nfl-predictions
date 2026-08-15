"""Point-in-time DraftKings scoring for historical recourse sizing.

The prospective recourse policy consumes points known at one decision time.
Historical box-score labels cannot provide that state because they include the
rest of the game.  This module reconstructs player and DST points from
timestamped nflverse play-by-play, and can therefore be stopped at an exact
timezone-aware instant.

The implementation deliberately mirrors the canonical full-game scorers in
``sql/features/013_player_week_actuals.sql`` and
``sql/features/024_team_defense_week.sql``.  A historical recourse run is not
licensed merely because this code exists: its full-game results must first be
reconciled to those authoritative tables under the frozen protocol.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import hashlib

import numpy as np
import pandas as pd

from ..models.scoring import StatLine, dk_points


TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
PLAYER_COMPONENTS = (
    "pass_yards",
    "pass_tds",
    "interceptions",
    "rush_yards",
    "rush_tds",
    "receptions",
    "rec_yards",
    "rec_tds",
    "fumbles_lost",
    "two_point_conversions",
    "return_tds",
)
DST_COMPONENTS = (
    "sacks",
    "interceptions",
    "fumble_recoveries",
    "safeties",
    "blocked_kicks",
    "return_tds",
    "defensive_conversions",
)

# nflverse exposes only one lateral-player identity and one aggregate lateral
# yard value on these eight multi-lateral plays.  The timestamped descriptions
# themselves enumerate every intermediate player and yard allocation.  These
# checksum-bound deltas are the deterministic difference between the structured
# fields and that description; they are not inferred from a fantasy outcome.
# The table closes the 12 known full-game reconciliation residuals and, most
# importantly for recourse, makes the two pre-3:55 plays identifiable.
MULTI_LATERAL_ADJUSTMENTS = {
    ("2023_09_TB_HOU", 4520): {
        "description_sha256": "c1c95aa2edc75631096849944e7f0632592f6542578ba6fed35618bea79e98ce",
        "rec_yards": {"00-0036985": -3.0},
    },
    ("2023_16_BUF_LAC", 4111): {
        "description_sha256": "e1992c85a9bcebcb32d53acb43f4c84bb6de523e4f2d3472181bcf403553cb53",
        "rec_yards": {"00-0033699": -2.0},
    },
    ("2024_03_SF_LA", 4434): {
        "description_sha256": "b7dc3c57193ee6669cb7fae9ce86ef70e25817289499869a81407bad32473442",
        "rec_yards": {
            "00-0033576": 17.0,
            "00-0036261": 5.0,
            "00-0037525": 1.0,
            "00-0039351": -3.0,
        },
    },
    ("2024_04_JAX_HOU", 4287): {
        "description_sha256": "4eb3e84f12ab009d0f9d79350ded09f874a6a64935c88271ef76da017a337d06",
        "rec_yards": {"00-0036196": -7.0},
    },
    ("2024_05_DAL_PIT", 4583): {
        "description_sha256": "727ceed8a5da555243a966439dcb5b0f713e2db950b6036650adfb79a8c29187",
        "rec_yards": {"00-0039896": -2.0},
    },
    ("2024_09_LAC_CLE", 2105): {
        "description_sha256": "32b16b45033f7a2d18ad31241c4d7748203bf13cd41eee0fe634ec34d8d64a65",
        "rec_yards": {"00-0036988": 9.0, "00-0039915": -6.0},
    },
    ("2025_15_CLE_CHI", 1934): {
        "description_sha256": "57b3253942bb810394d4b434252225b80188e0583185f6623b2f80bc9b94a329",
        "rec_yards": {"00-0034827": 4.0},
    },
    ("2025_18_IND_HOU", 4468): {
        "description_sha256": "5f459bfeda3feab7cdcc97b19510d6aef5b297da5db8e35631908eb1c769a16e",
        "rec_yards": {"00-0036252": -9.0},
    },
}


def _aware(value, label: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return stamp


def _normal_team(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    team = str(value).strip().upper()
    if not team:
        return None
    return TEAM_ALIASES.get(team, team)


def _number(row: pd.Series, column: str) -> float:
    if column not in row.index:
        return 0.0
    value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(value) else float(value)


def _player_id(row: pd.Series, column: str) -> str | None:
    if column not in row.index:
        return None
    value = row[column]
    if value is None or pd.isna(value):
        return None
    player_id = str(value).strip()
    return player_id or None


def _prepare_pbp(pbp: pd.DataFrame, *, as_of=None) -> tuple[pd.DataFrame, dict]:
    required = {"game_id", "season", "week", "time_of_day"}
    missing = required - set(pbp.columns)
    if missing:
        raise ValueError("recourse PBP missing " + ", ".join(sorted(missing)))
    frame = pbp.copy()
    frame["_event_time"] = pd.to_datetime(
        frame.time_of_day, format="mixed", errors="coerce", utc=True,
    )
    scoring_relevant = pd.Series(False, index=frame.index)
    for column in (
        "passing_yards", "pass_touchdown", "interception",
        "rushing_yards", "rush_touchdown", "complete_pass",
        "receiving_yards", "lateral_receiving_yards",
        "lateral_rushing_yards", "fumble_lost", "two_point_attempt",
        "return_touchdown", "sack", "safety", "punt_blocked",
        "defensive_two_point_conv",
    ):
        if column in frame:
            scoring_relevant |= pd.to_numeric(
                frame[column], errors="coerce",
            ).fillna(0).ne(0)
    for column in ("field_goal_result", "extra_point_result"):
        if column in frame:
            scoring_relevant |= frame[column].astype("string").str.lower().eq(
                "blocked",
            ).fillna(False)
    missing_times = frame.loc[scoring_relevant & frame._event_time.isna()]
    if not missing_times.empty:
        raise ValueError(
            f"{len(missing_times)} scoring-relevant PBP rows lack event time"
        )
    source_rows = len(frame)
    current = None
    if as_of is not None:
        current = _aware(as_of, "recourse scoring as-of").tz_convert("UTC")
        frame = frame.loc[frame._event_time.le(current)].copy()
    frame = frame.sort_values(
        ["season", "week", "game_id", "_event_time", "play_id"],
        kind="mergesort",
        na_position="first",
    )
    return frame, {
        "as_of": current.isoformat() if current is not None else None,
        "source_rows": int(source_rows),
        "included_rows": int(len(frame)),
        "excluded_after_as_of": int(source_rows - len(frame)),
        "scoring_relevant_missing_time": int(len(missing_times)),
    }


def _blank_player_stats() -> dict[str, float]:
    return {column: 0.0 for column in PLAYER_COMPONENTS}


def score_skill_players(
    pbp: pd.DataFrame,
    *,
    as_of=None,
) -> tuple[pd.DataFrame, dict]:
    """Score offensive and individual special-teams players through ``as_of``.

    The returned identity is nflverse ``gsis_id``.  A completed pass credits
    one reception only to the primary receiver; a lateral recipient receives
    the official lateral receiving yards but no reception.  Successful pass
    conversions credit both passer and receiver, matching the weekly label.
    """
    frame, receipt = _prepare_pbp(pbp, as_of=as_of)
    slate_keys = frame[["season", "week"]].drop_duplicates()
    if len(slate_keys) > 1:
        raise ValueError("skill recourse scorer requires one season-week")
    stats: defaultdict[str, dict[str, float]] = defaultdict(_blank_player_stats)

    def add(player_id: str | None, component: str, value: float) -> None:
        if player_id is not None and value:
            stats[player_id][component] += float(value)

    touchback_fumbles = 0
    multi_fumble_plays = 0
    non_boxscore_fumbles = 0
    multi_lateral_plays = 0
    multi_lateral_player_adjustments = 0
    for _, row in frame.iterrows():
        passer = _player_id(row, "passer_player_id")
        receiver = _player_id(row, "receiver_player_id")
        rusher = _player_id(row, "rusher_player_id")
        lateral_receiver = _player_id(row, "lateral_receiver_player_id")
        lateral_rusher = _player_id(row, "lateral_rusher_player_id")
        td_player = _player_id(row, "td_player_id")

        add(passer, "pass_yards", _number(row, "passing_yards"))
        add(passer, "pass_tds", _number(row, "pass_touchdown"))
        add(passer, "interceptions", _number(row, "interception"))

        add(rusher, "rush_yards", _number(row, "rushing_yards"))
        add(lateral_rusher, "rush_yards", _number(row, "lateral_rushing_yards"))
        if _number(row, "rush_touchdown"):
            add(td_player or lateral_rusher or rusher, "rush_tds", 1.0)

        add(receiver, "rec_yards", _number(row, "receiving_yards"))
        add(
            lateral_receiver,
            "rec_yards",
            _number(row, "lateral_receiving_yards"),
        )
        play_id = pd.to_numeric(
            pd.Series([row.get("play_id")]), errors="coerce",
        ).iloc[0]
        adjustment = None
        if not pd.isna(play_id):
            adjustment = MULTI_LATERAL_ADJUSTMENTS.get(
                (str(row.game_id), int(play_id)),
            )
        if adjustment is not None:
            description = str(row.get("desc", ""))
            digest = hashlib.sha256(description.encode("utf-8")).hexdigest()
            if digest != adjustment["description_sha256"]:
                raise ValueError(
                    f"multi-lateral description checksum differs: {row.game_id} "
                    f"play {int(play_id)}"
                )
            multi_lateral_plays += 1
            for player_id, yards in adjustment["rec_yards"].items():
                add(str(player_id), "rec_yards", float(yards))
                multi_lateral_player_adjustments += 1
        if _number(row, "complete_pass"):
            add(receiver, "receptions", 1.0)
        if _number(row, "pass_touchdown"):
            add(td_player or lateral_receiver or receiver, "rec_tds", 1.0)

        if (
            _number(row, "two_point_attempt")
            and str(row.get("two_point_conv_result", "")).lower() == "success"
        ):
            play_type = str(row.get("play_type", "")).lower()
            fantasy_player = _player_id(row, "fantasy_player_id")
            if passer is not None or play_type in {"pass", "no_play"}:
                add(passer, "two_point_conversions", 1.0)
                add(
                    receiver or fantasy_player,
                    "two_point_conversions",
                    1.0,
                )
            else:
                add(rusher or fantasy_player, "two_point_conversions", 1.0)

        if _number(row, "fumble_lost"):
            lost_players: list[str] = []
            # The authoritative player label counts passing/rushing/receiving
            # fumbles. It does not count a return muff or a fumble by a
            # lateral-only player in those offensive stat categories.
            boxscore_fumblers = {receiver, rusher}
            if _number(row, "sack"):
                boxscore_fumblers.add(passer)
            boxscore_fumblers.discard(None)
            opposing_recovery_seen = False
            for index in (1, 2):
                fumbler = _player_id(row, f"fumbled_{index}_player_id")
                fumble_team = _normal_team(row.get(f"fumbled_{index}_team"))
                recovery_team = _normal_team(
                    row.get(f"fumble_recovery_{index}_team"),
                )
                if (
                    fumbler is not None
                    and fumble_team is not None
                    and recovery_team is not None
                    and fumble_team != recovery_team
                ):
                    opposing_recovery_seen = True
                    if fumbler in boxscore_fumblers:
                        lost_players.append(fumbler)
            if not lost_players and not opposing_recovery_seen:
                # End-zone touchbacks have no recovery team but are a player
                # fumble lost in the authoritative weekly stat line.
                fallback = _player_id(row, "fumbled_1_player_id")
                if fallback in boxscore_fumblers:
                    lost_players = [fallback]
                    touchback_fumbles += 1
            if not lost_players:
                non_boxscore_fumbles += 1
            if len(lost_players) > 1:
                multi_fumble_plays += 1
            for player_id in dict.fromkeys(lost_players):
                add(player_id, "fumbles_lost", 1.0)

        special_returners = {
            _player_id(row, "kickoff_returner_player_id"),
            _player_id(row, "lateral_kickoff_returner_player_id"),
            _player_id(row, "punt_returner_player_id"),
            _player_id(row, "lateral_punt_returner_player_id"),
        }
        special_returners.discard(None)
        blocked_return = bool(
            _number(row, "punt_blocked")
            or str(row.get("field_goal_result", "")).lower() == "blocked"
            or str(row.get("extra_point_result", "")).lower() == "blocked"
        )
        own_kickoff_td = bool(
            _number(row, "own_kickoff_recovery_td")
            and td_player == _player_id(row, "own_kickoff_recovery_player_id")
        )
        if (
            _number(row, "touchdown")
            and td_player is not None
            and (td_player in special_returners or blocked_return or own_kickoff_td)
        ):
            add(td_player, "return_tds", 1.0)

    rows = []
    for player_id in sorted(stats):
        components = stats[player_id]
        points = dk_points(StatLine(**components))
        rows.append({"player_id": player_id, **components, "dk_points": points})
    result = pd.DataFrame(
        rows,
        columns=["player_id", *PLAYER_COMPONENTS, "dk_points"],
    )
    return result, {
        **receipt,
        "players_scored": int(len(result)),
        "touchback_fumbles": int(touchback_fumbles),
        "multi_lost_fumble_plays": int(multi_fumble_plays),
        "non_boxscore_fumbles": int(non_boxscore_fumbles),
        "multi_lateral_plays_adjusted": int(multi_lateral_plays),
        "multi_lateral_players_adjusted": int(
            multi_lateral_player_adjustments
        ),
        "multi_lateral_rule": "checksum_bound_timestamped_pbp_description",
        "scorer": "pit-dk-skill-v1",
    }


def _points_allowed_tier(points_allowed: float) -> float:
    if points_allowed <= 0:
        return 10.0
    if points_allowed <= 6:
        return 7.0
    if points_allowed <= 13:
        return 4.0
    if points_allowed <= 20:
        return 1.0
    if points_allowed <= 27:
        return 0.0
    if points_allowed <= 34:
        return -1.0
    return -4.0


def _game_teams(frame: pd.DataFrame) -> dict[str, tuple[str, str]]:
    required = {"home_team", "away_team"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("DST PBP missing " + ", ".join(sorted(missing)))
    teams: dict[str, tuple[str, str]] = {}
    for game_id, group in frame.groupby("game_id", sort=True):
        homes = {_normal_team(value) for value in group.home_team.dropna()}
        aways = {_normal_team(value) for value in group.away_team.dropna()}
        homes.discard(None)
        aways.discard(None)
        if len(homes) != 1 or len(aways) != 1:
            raise ValueError(f"game {game_id} does not have one home/away team")
        teams[str(game_id)] = (next(iter(homes)), next(iter(aways)))
    return teams


def score_team_defenses(
    pbp: pd.DataFrame,
    *,
    as_of=None,
    active_game_ids: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Score DSTs in games that have started by ``as_of``.

    ``active_game_ids`` can preserve a game whose filtered frame has no event
    yet; normally the caller simply supplies the full slate PBP and games with
    no included timestamped row are omitted (and therefore remain at zero in
    the recourse adapter).  Points allowed mirror the canonical exclusion of
    offensive points surrendered on defensive returns and safeties.
    """
    source = pbp.copy()
    source_teams = _game_teams(source)
    frame, receipt = _prepare_pbp(source, as_of=as_of)
    started = set(frame.game_id.astype(str))
    if active_game_ids is not None:
        requested = {str(value) for value in active_game_ids}
        unknown = requested - set(source_teams)
        if unknown:
            raise ValueError("active DST games are absent from PBP")
        started |= requested

    def blank() -> dict[str, float]:
        return {column: 0.0 for column in DST_COMPONENTS}

    events: defaultdict[tuple[str, str], dict[str, float]] = defaultdict(blank)
    not_allowed: defaultdict[tuple[str, str], float] = defaultdict(float)
    scores: dict[str, tuple[float, float]] = {}
    season_week: dict[str, tuple[int, int]] = {}

    def credit(game_id: str, team: str | None, component: str, value: float) -> None:
        if team is not None and value:
            events[(game_id, team)][component] += float(value)

    for _, row in frame.iterrows():
        game_id = str(row.game_id)
        season_week[game_id] = (int(row.season), int(row.week))
        defteam = _normal_team(row.get("defteam"))
        credit(game_id, defteam, "sacks", _number(row, "sack"))
        credit(game_id, defteam, "interceptions", _number(row, "interception"))
        credit(game_id, defteam, "safeties", _number(row, "safety"))
        blocked = (
            _number(row, "punt_blocked")
            or str(row.get("field_goal_result", "")).lower() == "blocked"
            or str(row.get("extra_point_result", "")).lower() == "blocked"
        )
        credit(game_id, defteam, "blocked_kicks", float(bool(blocked)))
        credit(
            game_id,
            defteam,
            "defensive_conversions",
            _number(row, "defensive_two_point_conv"),
        )

        for index in (1, 2):
            fumble_team = _normal_team(row.get(f"fumbled_{index}_team"))
            recovery_team = _normal_team(
                row.get(f"fumble_recovery_{index}_team"),
            )
            if (
                fumble_team is not None
                and recovery_team is not None
                and fumble_team != recovery_team
            ):
                credit(game_id, recovery_team, "fumble_recoveries", 1.0)

        td_team = _normal_team(row.get("td_team"))
        play_type = str(row.get("play_type", "")).lower()
        if (
            _number(row, "touchdown")
            and td_team is not None
            and (
                (_number(row, "return_touchdown") and td_team == defteam)
                or play_type in {"kickoff", "punt", "field_goal"}
            )
        ):
            credit(game_id, td_team, "return_tds", 1.0)

        posteam = _normal_team(row.get("posteam"))
        if posteam is not None:
            if (
                _number(row, "return_touchdown")
                and td_team == defteam
                and play_type in {"pass", "run"}
            ):
                not_allowed[(game_id, posteam)] += 6.0
            if _number(row, "safety"):
                not_allowed[(game_id, posteam)] += 2.0

        home_score = _number(row, "total_home_score")
        away_score = _number(row, "total_away_score")
        scores[game_id] = (home_score, away_score)

    rows = []
    for game_id in sorted(started):
        if game_id not in scores:
            # A caller may explicitly mark a just-started game before its
            # first PBP row. Both DSTs then have zero observed points rather
            # than the in-game 10-point shutout tier.
            continue
        home, away = source_teams[game_id]
        home_score, away_score = scores[game_id]
        season, week = season_week[game_id]
        for team, opponent_score in ((home, away_score), (away, home_score)):
            components = events[(game_id, team)]
            pa = max(0.0, opponent_score - not_allowed[(game_id, team)])
            points = (
                components["sacks"]
                + 2.0 * components["interceptions"]
                + 2.0 * components["fumble_recoveries"]
                + 2.0 * components["safeties"]
                + 2.0 * components["blocked_kicks"]
                + 6.0 * components["return_tds"]
                + 2.0 * components["defensive_conversions"]
                + _points_allowed_tier(pa)
            )
            rows.append({
                "season": season,
                "week": week,
                "game_id": game_id,
                "team": team,
                **components,
                "points_allowed": pa,
                "dk_points": float(points),
            })
    result = pd.DataFrame(
        rows,
        columns=[
            "season", "week", "game_id", "team", *DST_COMPONENTS,
            "points_allowed", "dk_points",
        ],
    )
    return result, {
        **receipt,
        "games_started": int(len(started)),
        "games_scored": int(result.game_id.nunique()) if not result.empty else 0,
        "defenses_scored": int(len(result)),
        "scorer": "pit-dk-dst-v1",
    }


def points_information_as_of(
    pbp: pd.DataFrame,
    player_catalog: pd.DataFrame,
    authoritative_skill: pd.DataFrame,
    authoritative_dst: pd.DataFrame,
    *,
    as_of,
    final_game_ids: Iterable[str],
) -> tuple[pd.DataFrame, dict]:
    """Build the outcome-safe status frame consumed by recourse v1.

    Final labels are read only for games explicitly declared final as of the
    decision. In-progress games use the cutoff PBP reconstruction. Unstarted
    games are fixed at zero even though the supplied PBP and authoritative
    tables may contain their eventual outcomes.
    """
    current = _aware(as_of, "recourse points-information as-of").tz_convert("UTC")
    required_catalog = {
        "player_id", "position", "team", "game_id", "kickoff_time",
    }
    missing_catalog = required_catalog - set(player_catalog.columns)
    if missing_catalog:
        raise ValueError(
            "recourse points catalog missing "
            + ", ".join(sorted(missing_catalog))
        )
    catalog = player_catalog.copy()
    catalog["player_id"] = catalog.player_id.astype(str)
    catalog["game_id"] = catalog.game_id.astype(str)
    catalog["team"] = catalog.team.map(_normal_team)
    catalog["position"] = catalog.position.astype(str).str.upper().replace(
        {"DEF": "DST"},
    )
    catalog["kickoff_utc"] = pd.to_datetime(
        catalog.kickoff_time, format="mixed", errors="coerce", utc=True,
    )
    output_id = "dk_id" if "dk_id" in catalog.columns else "player_id"
    catalog["output_id"] = catalog[output_id].astype(str)
    if (
        catalog.player_id.eq("").any()
        or catalog.game_id.eq("").any()
        or catalog.team.isna().any()
        or catalog.kickoff_utc.isna().any()
        or catalog.output_id.eq("").any()
        or catalog.output_id.duplicated().any()
    ):
        raise ValueError("recourse points catalog identity/kickoff is invalid")

    final_games = {str(value) for value in final_game_ids}
    unknown_final = final_games - set(catalog.game_id)
    if unknown_final:
        raise ValueError("final-game declaration includes an unknown game")
    premature = catalog[
        catalog.game_id.isin(final_games) & catalog.kickoff_utc.gt(current)
    ]
    if not premature.empty:
        raise ValueError("a game is declared final before its kickoff")

    skill, skill_receipt = score_skill_players(pbp, as_of=current)
    dst, dst_receipt = score_team_defenses(pbp, as_of=current)
    partial_skill = dict(zip(skill.player_id, skill.dk_points, strict=True))
    partial_dst = dict(zip(dst.team, dst.dk_points, strict=True))

    def _authoritative_map(
        frame: pd.DataFrame, key: str, label: str,
    ) -> dict[str, float]:
        required = {key, "dk_points"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                f"authoritative {label} missing "
                + ", ".join(sorted(missing))
            )
        data = frame[[key, "dk_points"]].copy()
        data[key] = data[key].astype(str) if key != "team" else data[key].map(
            _normal_team,
        )
        data["dk_points"] = pd.to_numeric(data.dk_points, errors="coerce")
        if (
            data[key].isna().any()
            or data[key].duplicated().any()
            or not np.isfinite(data.dk_points.to_numpy(dtype=float)).all()
        ):
            raise ValueError(f"authoritative {label} is not unique and finite")
        return dict(zip(data[key], data.dk_points, strict=True))

    final_skill = _authoritative_map(
        authoritative_skill, "player_id", "skill points",
    )
    final_dst = _authoritative_map(
        authoritative_dst, "team", "DST points",
    )
    rows = []
    missing_final: list[str] = []
    for row in catalog.itertuples(index=False):
        if row.kickoff_utc > current:
            status = "not_started"
            points = 0.0
            source = "zero_before_kickoff"
        elif row.game_id in final_games:
            status = "final"
            mapping = final_dst if row.position == "DST" else final_skill
            key = row.team if row.position == "DST" else row.player_id
            if key not in mapping:
                missing_final.append(str(key))
                continue
            points = float(mapping[key])
            source = "authoritative_final"
        else:
            status = "in_progress"
            mapping = partial_dst if row.position == "DST" else partial_skill
            key = row.team if row.position == "DST" else row.player_id
            points = float(mapping.get(key, 0.0))
            source = "timestamped_pbp_to_date"
        rows.append({
            "dk_id": row.output_id,
            "points_to_date": points,
            "game_status": status,
            "available_at": current.isoformat(),
            "game_id": row.game_id,
            "points_source": source,
        })
    if missing_final:
        raise ValueError(
            "authoritative final points omit catalog identities: "
            + ", ".join(sorted(missing_final))
        )
    result = pd.DataFrame(rows)
    status_counts = {
        status: int(result.game_status.eq(status).sum())
        for status in ("not_started", "in_progress", "final")
    }
    return result, {
        "as_of": current.isoformat(),
        "players": int(len(result)),
        "final_game_ids": sorted(final_games),
        "status_counts": status_counts,
        "skill_scorer": skill_receipt,
        "dst_scorer": dst_receipt,
        "final_points_rule": "authoritative_labels_only_for_as_of_final_games",
        "uses_unstarted_or_in_progress_final_outcomes": False,
        "scorer": "pit-dk-points-information-v1",
    }


__all__ = [
    "DST_COMPONENTS",
    "PLAYER_COMPONENTS",
    "MULTI_LATERAL_ADJUSTMENTS",
    "score_skill_players",
    "score_team_defenses",
    "points_information_as_of",
]
