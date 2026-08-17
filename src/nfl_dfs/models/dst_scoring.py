"""Versioned DraftKings NFL Classic defense/special-teams scoring law.

This module is the canonical executable contract for DST scoring.  The
warehouse SQL cannot import Python, so focused offline tests require its
literal expression to remain in parity with this contract.

The rule snapshot is intentionally date-versioned.  DraftKings can change
contest rules; a future rule change must create a new contract instead of
silently mutating historical semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Final


# nflfastR's ordinary offensive-play categories. Points scored by the
# opposing defense on these plays are excluded from the subject DST's points
# allowed; scores on punt/kick/field-goal plays are not. Warehouse SQL pins the
# same literal tuple with focused parity tests because it cannot import Python.
OFFENSIVE_PLAY_TYPES: Final = ("pass", "run", "qb_kneel", "qb_spike")


@dataclass(frozen=True)
class EventRule:
    """One countable DST event and its DraftKings fantasy-point value."""

    component: str
    official_label: str
    points: float


@dataclass(frozen=True)
class PointsAllowedTier:
    """An inclusive upper bound for one points-allowed fantasy tier."""

    maximum: int | None
    points: float


@dataclass(frozen=True)
class OfficialRuleSource:
    """Immutable receipt for the official rule material used to freeze a law."""

    url: str
    selector: str
    content_sha256: str
    retrieved_at: str
    last_modified: str | None = None


@dataclass(frozen=True)
class DstScoringLaw:
    """Machine-readable contract for one version of the DK Classic DST law."""

    law_id: str
    product: str
    game_type_id: int
    verified_on: str
    event_rules: tuple[EventRule, ...]
    points_allowed_tiers: tuple[PointsAllowedTier, ...]
    points_allowed_inclusions: tuple[str, ...]
    points_allowed_exclusions: tuple[str, ...]
    reciprocal_defensive_conversion_return_counts_as_pa: bool
    yards_allowed_fantasy_component_present: bool
    sources: tuple[OfficialRuleSource, ...]

    @property
    def components(self) -> tuple[str, ...]:
        return tuple(rule.component for rule in self.event_rules)

    def manifest(self) -> dict[str, object]:
        """Return a JSON-serializable representation for receipts/reviews."""

        return {
            "law_id": self.law_id,
            "product": self.product,
            "game_type_id": self.game_type_id,
            "verified_on": self.verified_on,
            "event_points": {
                rule.component: rule.points for rule in self.event_rules
            },
            "points_allowed_tiers": [
                {"maximum": tier.maximum, "points": tier.points}
                for tier in self.points_allowed_tiers
            ],
            "points_allowed_inclusions": list(self.points_allowed_inclusions),
            "points_allowed_exclusions": list(self.points_allowed_exclusions),
            "reciprocal_defensive_conversion_return_counts_as_pa": (
                self.reciprocal_defensive_conversion_return_counts_as_pa
            ),
            "yards_allowed_fantasy_component_present": (
                self.yards_allowed_fantasy_component_present
            ),
            "sources": [
                {
                    "url": source.url,
                    "selector": source.selector,
                    "content_sha256": source.content_sha256,
                    "retrieved_at": source.retrieved_at,
                    "last_modified": source.last_modified,
                }
                for source in self.sources
            ],
        }


DST_SCORING_LAW = DstScoringLaw(
    law_id="draftkings-nfl-classic-dst-2026-08-17-v1",
    product="DraftKings NFL Classic",
    game_type_id=1,
    verified_on="2026-08-17",
    event_rules=(
        EventRule("sacks", "Sack", 1.0),
        EventRule("interceptions", "Interception", 2.0),
        EventRule("fumble_recoveries", "Fumble Recovery", 2.0),
        EventRule("safeties", "Safety", 2.0),
        EventRule("blocked_kicks", "Blocked Kick", 2.0),
        EventRule("return_tds", "Defense/Special Teams Return TD", 6.0),
        EventRule(
            "defensive_conversions",
            "2 Pt Conversion/Extra Point Return",
            2.0,
        ),
    ),
    points_allowed_tiers=(
        PointsAllowedTier(0, 10.0),
        PointsAllowedTier(6, 7.0),
        PointsAllowedTier(13, 4.0),
        PointsAllowedTier(20, 1.0),
        PointsAllowedTier(27, 0.0),
        PointsAllowedTier(34, -1.0),
        PointsAllowedTier(None, -4.0),
    ),
    points_allowed_inclusions=(
        "rushing_touchdown",
        "passing_touchdown",
        "offensive_fumble_recovery_touchdown",
        "punt_return_touchdown",
        "kick_return_touchdown",
        "field_goal_return_touchdown",
        "blocked_field_goal_touchdown",
        "blocked_punt_touchdown",
        "offensive_two_point_conversion",
        "defensive_two_point_or_extra_point_return",
        "extra_point",
        "field_goal",
    ),
    points_allowed_exclusions=(
        "points_surrendered_while_the_subject_team_offense_is_on_field",
    ),
    # DraftKings' current NFL Classic scoring notes explicitly include a
    # 2-point/extra-point return among plays charged to the opposing DST's PA.
    reciprocal_defensive_conversion_return_counts_as_pa=True,
    # The official DST scoring table is exhaustive and contains no
    # passing-, rushing-, total- or other yards-allowed fantasy component.
    yards_allowed_fantasy_component_present=False,
    sources=(
        OfficialRuleSource(
            url=(
                "https://api.draftkings.com/rules-and-scoring/"
                "RulesAndScoring.json"
            ),
            selector=(
                "top-level group 1; rule name NFL Classic; gameTypes contains 1"
            ),
            content_sha256=(
                "fb0ac704f9bbc5d8fd96727280ad8ef7760b1a9d2456474dd760904543d7bbe5"
            ),
            retrieved_at="2026-08-17T19:59:59Z",
            last_modified="2026-08-13T14:08:31Z",
        ),
        OfficialRuleSource(
            url=(
                "https://api.draftkings.com/lineups/v1/gametypes/1/"
                "rules?format=json"
            ),
            selector=(
                "gameTypeId=1; gameTypeName=Classic; rulesUrl=/help/rules/1/1"
            ),
            content_sha256=(
                "0a46969690423d45a93388ff6402ac0335604003deda70e1d525081f6047fb35"
            ),
            retrieved_at="2026-08-17T19:59:58Z",
        ),
    ),
)

DST_COMPONENTS = DST_SCORING_LAW.components
DST_SCORING_LAW_ID = DST_SCORING_LAW.law_id


def points_allowed_points(points_allowed: float) -> float:
    """Return the fantasy points for a nonnegative points-allowed value."""

    value = float(points_allowed)
    if not math.isfinite(value) or value < 0:
        raise ValueError("DST points allowed must be finite and nonnegative")
    for tier in DST_SCORING_LAW.points_allowed_tiers:
        if tier.maximum is None or value <= tier.maximum:
            return tier.points
    raise AssertionError("DST scoring law has no terminal points-allowed tier")


def is_offensive_play_type(play_type: object) -> bool:
    """Return whether an nflfastR play has the offense on the field."""
    return str(play_type).strip().lower() in OFFENSIVE_PLAY_TYPES


def score_dst_components(
    components: Mapping[str, float],
    *,
    points_allowed: float,
) -> float:
    """Score one complete DST event vector under the frozen canonical law.

    Missing or extra components fail closed.  In particular, a caller cannot
    accidentally introduce yards-allowed scoring or omit a sparse event.
    """

    expected = set(DST_COMPONENTS)
    supplied = set(components)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(
            f"DST component contract differs; missing={missing}, extra={extra}"
        )

    points = 0.0
    weights = {rule.component: rule.points for rule in DST_SCORING_LAW.event_rules}
    for component in DST_COMPONENTS:
        value = float(components[component])
        if not math.isfinite(value) or value < 0:
            raise ValueError(
                f"DST component {component} must be finite and nonnegative"
            )
        points += weights[component] * value
    return points + points_allowed_points(points_allowed)


__all__ = [
    "DST_COMPONENTS",
    "DST_SCORING_LAW",
    "DST_SCORING_LAW_ID",
    "DstScoringLaw",
    "EventRule",
    "OfficialRuleSource",
    "OFFENSIVE_PLAY_TYPES",
    "PointsAllowedTier",
    "points_allowed_points",
    "is_offensive_play_type",
    "score_dst_components",
]
