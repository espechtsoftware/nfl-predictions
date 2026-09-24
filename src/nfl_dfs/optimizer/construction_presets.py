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
import math
from typing import Mapping

from .lineup import StackRules


LEGALITY_ONLY_PRESET_ID = "dk-classic-legality-only-v1"
INCUMBENT_GPP_PRESET_ID = "classic-incumbent-gpp-v1"
BASE_CONSTRUCTION_RECEIPT_SCOPE = "base-policy-only-v1"
UNRECEIPTED_CONSTRUCTION_SCOPE = "unreceipted"
_UNSET = object()


def construction_receipt_scope(
    receipt: Mapping[str, object] | None,
) -> str:
    """Name the evidence boundary without implying an absent receipt exists."""
    return (
        BASE_CONSTRUCTION_RECEIPT_SCOPE
        if receipt is not None
        else UNRECEIPTED_CONSTRUCTION_SCOPE
    )


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


def preset_from_receipt(receipt: Mapping[str, object]) -> ConstructionPreset:
    """Reopen one complete base-preset receipt and verify its content hash.

    A base receipt is evidence only when every field represented by the
    preset is present and covered by its digest.  Unknown or omitted fields
    fail closed.  Candidate-family locks, bans, salary bands, and similar
    overlays remain a separate identity boundary.
    """
    if not isinstance(receipt, Mapping):
        raise ValueError("construction receipt must be a mapping")
    expected_keys = {
        "schema_version", "base_preset_id", "stack", "min_salary",
        "min_games", "punt_min", "punt_max_salary", "punt_strict",
        "value2_min", "value2_max", "own_barbell", "own_barbell_low",
        "own_barbell_high", "own_barbell_nlow", "own_barbell_nhigh",
        "max_per_game", "min_lowown", "max_overlap", "effective_id",
        "sha256",
    }
    actual_keys = set(receipt)
    if actual_keys != expected_keys:
        raise ValueError(
            "construction receipt fields differ: "
            f"missing={sorted(expected_keys - actual_keys)} "
            f"unexpected={sorted(actual_keys - expected_keys)}"
        )
    if receipt["schema_version"] != "classic-construction-preset-v1":
        raise ValueError("unknown construction receipt schema")
    raw_stack = receipt["stack"]
    if not isinstance(raw_stack, Mapping):
        raise ValueError("construction receipt stack must be a mapping")
    stack_fields = set(StackRules.__dataclass_fields__)
    if set(raw_stack) != stack_fields:
        raise ValueError(
            "construction receipt stack fields differ: "
            f"missing={sorted(stack_fields - set(raw_stack))} "
            f"unexpected={sorted(set(raw_stack) - stack_fields)}"
        )
    integer_fields = {
        "min_salary", "min_games", "punt_min", "value2_min",
        "value2_max", "own_barbell_nlow", "own_barbell_nhigh",
        "max_per_game", "min_lowown", "max_overlap",
    }
    boolean_fields = {"punt_strict", "own_barbell"}
    float_fields = {"own_barbell_low", "own_barbell_high"}
    if any(type(receipt[key]) is not int for key in integer_fields):
        raise ValueError("construction receipt integer field type differs")
    if any(type(receipt[key]) is not bool for key in boolean_fields):
        raise ValueError("construction receipt boolean field type differs")
    if any(
        type(receipt[key]) not in {int, float}
        or not math.isfinite(float(receipt[key]))
        for key in float_fields
    ):
        raise ValueError("construction receipt float field type differs")
    if type(receipt["base_preset_id"]) is not str:
        raise ValueError("construction receipt preset id type differs")
    if (
        receipt["punt_max_salary"] is not None
        and type(receipt["punt_max_salary"]) is not int
    ):
        raise ValueError("construction receipt punt ceiling type differs")
    stack_integer_fields = {"qb_stack_min", "bring_back_min"}
    stack_nullable_integer_fields = {"qb_stack_max", "bring_back_max"}
    stack_boolean_fields = {
        "forbid_rb_vs_dst", "forbid_two_rb_same_team",
        "require_rb_vs_dst", "require_two_rb_same_team",
    }
    if any(type(raw_stack[key]) is not int for key in stack_integer_fields):
        raise ValueError("construction receipt stack integer type differs")
    if any(
        raw_stack[key] is not None and type(raw_stack[key]) is not int
        for key in stack_nullable_integer_fields
    ):
        raise ValueError("construction receipt stack bound type differs")
    if any(type(raw_stack[key]) is not bool for key in stack_boolean_fields):
        raise ValueError("construction receipt stack boolean type differs")
    # Reconstruct with the serialized values themselves.  The dataclasses and
    # canonical equality below reject type coercion (for example ``"false"``
    # becoming truthy) instead of silently normalizing a forged receipt.
    try:
        preset = ConstructionPreset(
            preset_id=receipt["base_preset_id"],
            stack=StackRules(**dict(raw_stack)),
            min_salary=receipt["min_salary"],
            min_games=receipt["min_games"],
            punt_min=receipt["punt_min"],
            punt_max_salary=receipt["punt_max_salary"],
            punt_strict=receipt["punt_strict"],
            value2_min=receipt["value2_min"],
            value2_max=receipt["value2_max"],
            own_barbell=receipt["own_barbell"],
            own_barbell_low=receipt["own_barbell_low"],
            own_barbell_high=receipt["own_barbell_high"],
            own_barbell_nlow=receipt["own_barbell_nlow"],
            own_barbell_nhigh=receipt["own_barbell_nhigh"],
            max_per_game=receipt["max_per_game"],
            min_lowown=receipt["min_lowown"],
            max_overlap=receipt["max_overlap"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("construction receipt values are malformed") from exc
    canonical = preset.receipt()
    if dict(receipt) != canonical:
        raise ValueError("construction receipt content hash or values differ")
    return preset


def verify_construction_execution(
    receipt: Mapping[str, object],
    *,
    stack: StackRules | None,
    env: Mapping[str, str] | None,
) -> ConstructionPreset:
    """Prove that a named receipt equals the executed base construction."""
    preset = preset_from_receipt(receipt)
    if stack is None:
        raise ValueError(
            "a receipted construction law requires explicit StackRules"
        )
    if asdict(stack) != asdict(preset.stack):
        raise ValueError("executed StackRules differ from construction receipt")
    if env is None:
        raise ValueError(
            "a receipted construction law requires an explicit environment"
        )
    expected_env = preset.optimizer_environment()
    mismatches = {
        key: {"expected": value, "actual": env.get(key)}
        for key, value in expected_env.items()
        if env.get(key) != value
    }
    if mismatches:
        raise ValueError(
            f"executed construction environment differs: {mismatches}"
        )
    return preset


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
    qb_stack_max: int | None | object = _UNSET,
    bring_back_max: int | None | object = _UNSET,
    require_rb_vs_dst: bool | None = None,
    require_two_rb_same_team: bool | None = None,
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
            "require_rb_vs_dst": require_rb_vs_dst,
            "require_two_rb_same_team": require_two_rb_same_team,
        }.items() if value is not None
    }
    if qb_stack_max is not _UNSET:
        stack_updates["qb_stack_max"] = qb_stack_max
    if bring_back_max is not _UNSET:
        stack_updates["bring_back_max"] = bring_back_max
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
    } if use_stack else asdict(StackRules()))
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
