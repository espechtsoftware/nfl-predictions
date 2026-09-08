"""Versioned semantic NFL game identity and final Classic roster audit.

Raw provider ``game_id`` values are provenance, not a grouping key.  A single
physical game can arrive as an nflverse identifier for skill players and as
directional ``TEAM@OPP`` text for DST rows.  This module derives the game from
the unordered, normalized team/opponent pair without mutating either source
field.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import pandas as pd

CANONICAL_GAME_POLICY_ID: Final = "unordered-normalized-team-opponent-v2"

# The aliases are deliberately local to the identity policy.  Importing an
# inference module here would make the shared optimizer depend on live-model
# code and would leave the identity implicit rather than versioned.
TEAM_ALIASES: Final = {
    "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
    "GBP": "GB", "GNB": "GB", "JAC": "JAX", "KCC": "KC",
    "KAN": "KC", "LVR": "LV", "OAK": "LV", "LAR": "LA",
    "RAM": "LA", "STL": "LA", "NEP": "NE", "NWE": "NE",
    "NOS": "NO", "NOR": "NO", "SDC": "LAC", "SDG": "LAC",
    "SD": "LAC", "SFO": "SF", "TBB": "TB", "TAM": "TB",
    "WFT": "WAS", "WSH": "WAS",
}

_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "DST"})


@dataclass(frozen=True, slots=True)
class CanonicalGameIdentity:
    """One player's semantic game plus untouched raw provenance."""

    canonical_game_key: str
    team: str
    opponent: str
    raw_game_id: str | None


def _required_text(value: object, *, label: str) -> str:
    if value is None:
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: {label} is missing")
    # Missing pandas/NumPy scalars must be rejected before ``str`` turns them
    # into plausible identifiers such as ``<NA>`` or ``NaT``.  ``pd.isna``
    # also covers NumPy floating NaN and datetime64/timedelta64 NaT.  Reject
    # non-scalar results rather than allowing their truth value to be guessed.
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, bool) and missing:
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: {label} is missing")
    if not isinstance(missing, bool) and hasattr(missing, "item"):
        try:
            if bool(missing.item()):
                raise ValueError(
                    f"{CANONICAL_GAME_POLICY_ID}: {label} is missing"
                )
        except ValueError:
            raise
        except (TypeError, AttributeError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: {label} is missing")
    text = str(value).strip()
    if not text or text.upper() in {
        "NAN", "NAT", "<NA>", "NONE", "NULL", "INF", "+INF", "-INF", "INFINITY",
        "+INFINITY", "-INFINITY",
    }:
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: {label} is missing")
    return text


def normalize_team(value: object, *, label: str = "team") -> str:
    """Normalize a team abbreviation under the frozen v2 alias table."""

    team = _required_text(value, label=label).upper()
    return TEAM_ALIASES.get(team, team)


def canonical_game_key(team: object, opponent: object) -> str:
    """Return an order-invariant semantic key for one physical game."""

    normalized_team = normalize_team(team, label="team")
    normalized_opponent = normalize_team(opponent, label="opponent")
    if normalized_team == normalized_opponent:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: team and opponent are identical"
        )
    return "|".join(sorted((normalized_team, normalized_opponent)))


def player_game_identity(player: Mapping[str, object]) -> CanonicalGameIdentity:
    """Derive identity while retaining the provider's raw ``game_id``."""

    _required_text(player.get("id"), label="player id")
    opponent = player.get("opp")
    if opponent is None:
        opponent = player.get("opponent")
    if (
        player.get("opp") is not None
        and player.get("opponent") is not None
        and normalize_team(player["opp"], label="opp")
        != normalize_team(player["opponent"], label="opponent")
    ):
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: opp and opponent disagree"
        )
    team = normalize_team(player.get("team"), label="team")
    opp = normalize_team(opponent, label="opponent")
    raw = player.get("game_id")
    raw_text = (
        None if raw is None
        else _required_text(raw, label="raw game_id provenance")
    )
    return CanonicalGameIdentity(
        canonical_game_key=canonical_game_key(team, opp),
        team=team,
        opponent=opp,
        raw_game_id=raw_text,
    )


def canonical_game_identities(
    players: Sequence[Mapping[str, object]],
) -> list[CanonicalGameIdentity]:
    identities = [player_game_identity(player) for player in players]
    opponents_by_team: dict[str, set[str]] = defaultdict(set)
    games_by_participant: dict[str, set[str]] = defaultdict(set)
    games_by_raw_id: dict[str, set[str]] = defaultdict(set)
    for identity in identities:
        opponents_by_team[identity.team].add(identity.opponent)
        games_by_participant[identity.team].add(identity.canonical_game_key)
        games_by_participant[identity.opponent].add(identity.canonical_game_key)
        if identity.raw_game_id is not None:
            games_by_raw_id[identity.raw_game_id].add(
                identity.canonical_game_key
            )
    ambiguous = sorted(
        team for team, opponents in opponents_by_team.items()
        if len(opponents) != 1
    )
    if ambiguous:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: team maps to multiple opponents: "
            + ",".join(ambiguous)
        )
    participant_ambiguous = sorted(
        team for team, games in games_by_participant.items()
        if len(games) != 1
    )
    if participant_ambiguous:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: participant maps to multiple games: "
            + ",".join(participant_ambiguous)
        )
    raw_ambiguous = sorted(
        raw_id for raw_id, games in games_by_raw_id.items()
        if len(games) != 1
    )
    if raw_ambiguous:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: raw game_id is ambiguous across "
            "multiple games: "
            + ",".join(raw_ambiguous)
        )
    return identities


def canonical_game_counts(
    players: Sequence[Mapping[str, object]],
) -> Counter[str]:
    return Counter(
        identity.canonical_game_key
        for identity in canonical_game_identities(players)
    )


def raw_game_provenance(
    players: Sequence[Mapping[str, object]],
) -> dict[str, list[str]]:
    """Expose, rather than overwrite, raw representations per physical game."""

    values: dict[str, set[str]] = defaultdict(set)
    for identity in canonical_game_identities(players):
        if identity.raw_game_id is not None:
            values[identity.canonical_game_key].add(identity.raw_game_id)
    return {key: sorted(values[key]) for key in sorted(values)}


def resolve_game_lock_key(
    players: Sequence[Mapping[str, object]], target: object, *, minimum: int
) -> str:
    """Resolve a canonical or raw lock target, rejecting every weak match."""

    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: game-lock minimum must be positive"
        )
    token = _required_text(target, label="game-lock target")
    identities = canonical_game_identities(players)
    canonical_keys = {identity.canonical_game_key for identity in identities}
    matches: set[str] = set()
    if token in canonical_keys:
        matches.add(token)
    matches.update(
        identity.canonical_game_key for identity in identities
        if identity.raw_game_id == token
    )
    if not matches:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: game-lock target has zero matches"
        )
    if len(matches) != 1:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: game-lock target is ambiguous"
        )
    key = next(iter(matches))
    available = sum(
        identity.canonical_game_key == key for identity in identities
    )
    if available < minimum:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: game-lock target has only "
            f"{available} players for minimum {minimum}"
        )
    return key


def audit_classic_roster_semantics(
    players: Sequence[Mapping[str, Any]],
    *,
    salary_cap: int = 50_000,
    max_from_team: int = 8,
) -> dict[str, object]:
    """Independently recompute final DK legality and semantic-game facts."""

    if len(players) != 9:
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: roster size is not nine")
    player_ids = [
        _required_text(player.get("id"), label="player id")
        for player in players
    ]
    if len(set(player_ids)) != 9:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: roster player IDs are not unique"
        )
    positions = Counter(str(player.get("pos") or "").strip().upper() for player in players)
    if (
        set(positions) - _POSITIONS
        or positions["QB"] != 1
        or positions["DST"] != 1
        or positions["RB"] not in {2, 3}
        or positions["WR"] not in {3, 4}
        or positions["TE"] not in {1, 2}
    ):
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: roster position shape is illegal"
        )
    try:
        salary = sum(int(player["salary"]) for player in players)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: roster salary is invalid"
        ) from exc
    if salary > salary_cap:
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: salary cap exceeded")
    teams = Counter(normalize_team(player.get("team")) for player in players)
    if len(teams) < 2 or max(teams.values()) > max_from_team:
        raise ValueError(f"{CANONICAL_GAME_POLICY_ID}: team limit violated")
    identities = canonical_game_identities(players)
    if any(identity.raw_game_id is None for identity in identities):
        raise ValueError(
            f"{CANONICAL_GAME_POLICY_ID}: raw game_id provenance is missing"
        )
    games = Counter(identity.canonical_game_key for identity in identities)
    return {
        "canonical_game_policy_id": CANONICAL_GAME_POLICY_ID,
        "canonical_game_count": len(games),
        "canonical_max_players_same_game": max(games.values()),
        "canonical_game_player_counts": dict(sorted(games.items())),
        "raw_game_id_provenance": raw_game_provenance(players),
        "salary": salary,
        "draftkings_legal": True,
    }
