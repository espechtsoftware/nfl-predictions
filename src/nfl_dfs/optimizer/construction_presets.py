"""Named, receipted DraftKings Classic construction policies.

The optimizer's bare defaults describe only contest legality.  Any strategy
(stacking, salary spend, game diversity, punts, ownership shape, or a game
cap) enters through one of these explicit presets so callers can record the
effective construction rather than inheriting process state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from typing import Mapping

from .lineup import StackRules


LEGALITY_ONLY_PRESET_ID = "dk-classic-legality-only-v1"
INCUMBENT_GPP_PRESET_ID = "classic-incumbent-gpp-v1"
_UNSET = object()


@dataclass(frozen=True, slots=True)
class ConstructionPreset:
    """Complete effective state for optimizer construction levers."""

    preset_id: str
    stack: StackRules
    min_salary: int = 0
    min_games: int = 1
    punt_min: int = 0
    punt_max_salary: int | None = None
    punt_strict: bool = False
    value2_min: int = 0
    value2_max: int = 5_300
    own_barbell: bool = False
    own_barbell_low: float = 0.05
    own_barbell_high: float = 0.20
    own_barbell_nlow: int = 3
    own_barbell_nhigh: int = 2
    max_per_game: int = 0
    min_lowown: int = 0
    max_overlap: int = 8

    def __post_init__(self) -> None:
        if not self.preset_id:
            raise ValueError("construction preset id must be nonempty")
        if not 0 <= self.min_salary <= 50_000:
            raise ValueError("minimum salary must be in 0..50000")
        if self.min_games < 1:
            raise ValueError("minimum games must be at least one")
        for label, value in (
            ("punt_min", self.punt_min),
            ("value2_min", self.value2_min),
            ("max_per_game", self.max_per_game),
            ("min_lowown", self.min_lowown),
        ):
            if value < 0:
                raise ValueError(f"{label} must be nonnegative")
        if not 0 <= self.max_overlap <= 8:
            raise ValueError("maximum overlap must be in 0..8")

    def payload(self) -> dict:
        return {
            "schema_version": "classic-construction-preset-v1",
            "base_preset_id": self.preset_id,
            "stack": asdict(self.stack),
            "min_salary": self.min_salary,
            "min_games": self.min_games,
            "punt_min": self.punt_min,
            "punt_max_salary": self.punt_max_salary,
            "punt_strict": self.punt_strict,
            "value2_min": self.value2_min,
            "value2_max": self.value2_max,
            "own_barbell": self.own_barbell,
            "own_barbell_low": self.own_barbell_low,
            "own_barbell_high": self.own_barbell_high,
            "own_barbell_nlow": self.own_barbell_nlow,
            "own_barbell_nhigh": self.own_barbell_nhigh,
            "max_per_game": self.max_per_game,
            "min_lowown": self.min_lowown,
            "max_overlap": self.max_overlap,
        }

    def receipt(self) -> dict:
        payload = self.payload()
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        ).encode()
        digest = sha256(encoded).hexdigest()
        return {
            **payload,
            "effective_id": f"{self.preset_id}@sha256:{digest}",
            "sha256": digest,
        }

    def optimizer_environment(self) -> dict[str, str]:
        """Explicit environment-shaped adapter for existing optimizer APIs."""
        return {
            "MIN_LINEUP_SALARY": str(self.min_salary),
            "MIN_GAMES": str(self.min_games),
            "PUNT_MIN": str(self.punt_min),
            "PUNT_MAX": (
                "" if self.punt_max_salary is None
                else str(self.punt_max_salary)
            ),
            "PUNT_STRICT": "1" if self.punt_strict else "",
            "VALUE2_MIN": str(self.value2_min),
            "VALUE2_MAX": str(self.value2_max),
            "OWN_BARBELL": "1" if self.own_barbell else "",
            "OWN_BARBELL_LOW": str(self.own_barbell_low),
            "OWN_BARBELL_HIGH": str(self.own_barbell_high),
            "OWN_BARBELL_NLOW": str(self.own_barbell_nlow),
            "OWN_BARBELL_NHIGH": str(self.own_barbell_nhigh),
            "MAX_PER_GAME": str(self.max_per_game),
            "MIN_LOWOWN": str(self.min_lowown),
            "MAX_OVERLAP": str(self.max_overlap),
        }


_PRESETS = {
    LEGALITY_ONLY_PRESET_ID: ConstructionPreset(
        preset_id=LEGALITY_ONLY_PRESET_ID,
        stack=StackRules(),
    ),
    INCUMBENT_GPP_PRESET_ID: ConstructionPreset(
        preset_id=INCUMBENT_GPP_PRESET_ID,
        stack=StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        ),
        min_salary=49_000,
        min_games=2,
        punt_min=0,
        punt_max_salary=4_000,
        max_overlap=7,
    ),
}


def resolve_construction_preset(
    preset_id: str,
    *,
    qb_stack_min: int | None = None,
    bring_back_min: int | None = None,
    forbid_rb_vs_dst: bool | None = None,
    forbid_two_rb_same_team: bool | None = None,
    min_salary: int | None = None,
    min_games: int | None = None,
    punt_min: int | None = None,
    punt_max_salary: int | None | object = _UNSET,
    punt_strict: bool | None = None,
    value2_min: int | None = None,
    value2_max: int | None = None,
    own_barbell: bool | None = None,
    own_barbell_low: float | None = None,
    own_barbell_high: float | None = None,
    own_barbell_nlow: int | None = None,
    own_barbell_nhigh: int | None = None,
    max_per_game: int | None = None,
    min_lowown: int | None = None,
    max_overlap: int | None = None,
) -> ConstructionPreset:
    """Resolve one named base plus only the overrides explicitly supplied."""
    try:
        base = _PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError(f"unknown construction preset: {preset_id}") from exc
    stack_updates = {
        key: value for key, value in {
            "qb_stack_min": qb_stack_min,
            "bring_back_min": bring_back_min,
            "forbid_rb_vs_dst": forbid_rb_vs_dst,
            "forbid_two_rb_same_team": forbid_two_rb_same_team,
        }.items() if value is not None
    }
    updates = {
        key: value for key, value in {
            "min_salary": min_salary,
            "min_games": min_games,
            "punt_min": punt_min,
            "punt_strict": punt_strict,
            "value2_min": value2_min,
            "value2_max": value2_max,
            "own_barbell": own_barbell,
            "own_barbell_low": own_barbell_low,
            "own_barbell_high": own_barbell_high,
            "own_barbell_nlow": own_barbell_nlow,
            "own_barbell_nhigh": own_barbell_nhigh,
            "max_per_game": max_per_game,
            "min_lowown": min_lowown,
            "max_overlap": max_overlap,
    }.items() if value is not None
    }
    if punt_max_salary is not _UNSET:
        updates["punt_max_salary"] = punt_max_salary
    return replace(
        base,
        stack=replace(base.stack, **stack_updates),
        **updates,
    )


def resolve_construction_preset_from_environment(
    preset_id: str,
    env: Mapping[str, str],
    *,
    use_stack: bool = True,
) -> ConstructionPreset:
    """Resolve legacy replay knobs once, into a named effective preset."""
    def integer(raw: str | None) -> int | None:
        return int(raw) if raw not in (None, "") else None

    def enabled(raw: str | None) -> bool | None:
        if raw is None:
            return None
        return raw.strip().lower() not in {"", "0", "false", "off", "no"}

    stack_kwargs = ({
        "qb_stack_min": integer(env.get("STACK_QB_MIN")),
        "bring_back_min": integer(env.get("STACK_BRING_BACK")),
        "forbid_rb_vs_dst": enabled(env.get("FORBID_RB_DST")),
        "forbid_two_rb_same_team": enabled(
            env.get("FORBID_TWO_RB_SAME_TEAM")
        ),
    } if use_stack else {
        "qb_stack_min": 0,
        "bring_back_min": 0,
        "forbid_rb_vs_dst": False,
        "forbid_two_rb_same_team": False,
    })
    return resolve_construction_preset(
        preset_id,
        **stack_kwargs,
        min_salary=integer(env.get("MIN_LINEUP_SALARY")),
        min_games=integer(env.get("MIN_GAMES")),
        punt_min=integer(env.get("PUNT_MIN")),
        punt_max_salary=(
            int(env["PUNT_MAX"]) if env.get("PUNT_MAX")
            else None if "PUNT_MAX" in env else _UNSET
        ),
        punt_strict=enabled(env.get("PUNT_STRICT")),
        value2_min=integer(env.get("VALUE2_MIN")),
        value2_max=integer(env.get("VALUE2_MAX")),
        own_barbell=enabled(env.get("OWN_BARBELL")),
        own_barbell_low=(
            float(env["OWN_BARBELL_LOW"])
            if "OWN_BARBELL_LOW" in env else None
        ),
        own_barbell_high=(
            float(env["OWN_BARBELL_HIGH"])
            if "OWN_BARBELL_HIGH" in env else None
        ),
        own_barbell_nlow=integer(env.get("OWN_BARBELL_NLOW")),
        own_barbell_nhigh=integer(env.get("OWN_BARBELL_NHIGH")),
        max_per_game=integer(env.get("MAX_PER_GAME")),
        min_lowown=integer(env.get("MIN_LOWOWN")),
        max_overlap=integer(env.get("MAX_OVERLAP")),
    )
