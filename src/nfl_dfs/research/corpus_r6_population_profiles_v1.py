"""Executable F7--F9 construction profiles for one shared historical bank.

This module is intentionally isolated from production configuration.  It
owns no environment reads, deployment path, object store, historical outcome
reader, or production default.  The three profiles compile to the existing
request-local DK Classic model seam in :mod:`corpus_legal_feasibility`.

The important boundary is that the profile owns *all* strategic structure
constraints.  A caller must disclose any inherited QB-partner, opposing-WR,
bring-back, game-stack, or ambient override.  Non-neutral inherited structure
fails closed with a per-profile conflict report instead of being silently
intersected with the requested profile.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.optimizer.lineup import StackRules
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    ConstraintDose,
    EffectivePolicyProfile,
    FreshLegalModel,
    StackRuleDose,
    audit_dk_classic,
    build_fresh_legal_model,
)
from nfl_dfs.research.corpus_parametric_batch import (
    PARAMETER_ORDER,
    SELECTED_ENTRY_BUDGET,
    SOLVER_TIMEOUT_SECONDS,
    SOLVE_ATTEMPTS_PER_BLOCK,
    WORLDS_PER_BLOCK,
)


PROFILE_SCHEMA: Final = "corpus-r6-population-profile/v1"
REGISTRY_SCHEMA: Final = "corpus-r6-population-profile-registry/v1"
SHARED_BANK_PLAN_SCHEMA: Final = "corpus-r6-population-shared-bank-plan/v1"
WORK_SCHEMA: Final = "corpus-r6-population-equal-solver-work/v1"
INHERITED_SURFACE_SCHEMA: Final = "corpus-r6-inherited-constraint-surface/v1"
MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_population_profiles_v1.py"
)
PROFILE_ORDER: Final = (
    "F7-qb-and-bringback-relaxed",
    "F8-game-cap-3",
    "F9-single-partner",
)

# These keys can restore or carve structure in the legacy backtest path.
# Presence is rejected even when the textual value looks equivalent: one
# profile must have one owner, and the direct model seam never needs them.
STRUCTURE_ENV_KEYS: Final = frozenset({
    "MAX_PER_GAME",
    "MIN_LINEUP_SALARY",
    "OPEN_BOOM_SOLVES",
    "SINGLE_STACK_BOOM_SOLVES",
    "STACK_BRING_BACK",
    "STACK_QB_MIN",
})

# Static audit of the legacy construction routes that could otherwise make a
# named profile vacuous.  The shared bank deliberately bypasses these routes
# and enters at ``build_fresh_legal_model`` with a fresh explicit dose.
LEGACY_CONSTRAINT_AUDIT: Final = (
    {
        "rule": "QB WR/TE partner minimum",
        "source": "backtest.replay:STACK_QB_MIN -> StackRules.qb_stack_min",
        "disposition": "must-not-be-inherited",
    },
    {
        "rule": "opponent skill-player bring-back minimum",
        "source": (
            "backtest.replay:STACK_BRING_BACK -> StackRules.bring_back_min"
        ),
        "disposition": "must-not-be-inherited",
    },
    {
        "rule": "opposing WR mandate",
        "source": "backtest.engine:thesis player locks",
        "global_hard_rule_found": False,
        "disposition": "forced QB/WR/opposing-WR thesis locks must be absent",
    },
    {
        "rule": "partial boom structure carve",
        "source": (
            "backtest.engine:OPEN_BOOM_SOLVES/SINGLE_STACK_BOOM_SOLVES"
        ),
        "disposition": "must-not-be-inherited",
    },
    {
        "rule": "five-player game lock",
        "source": "backtest.engine:game/dark game_lock=(game_id,5)",
        "disposition": "must-not-be-inherited",
    },
    {
        "rule": "ambient maximum from game",
        "source": "optimizer.lineup:MAX_PER_GAME",
        "disposition": "must-not-be-inherited",
    },
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")


class CorpusR6PopulationProfileError(ValueError):
    """A profile, plan, roster, or inherited constraint is invalid."""


class InheritedConstraintConflict(CorpusR6PopulationProfileError):
    """Inherited structure would silently alter at least one profile."""

    def __init__(self, conflicts: Sequence[Mapping[str, object]]) -> None:
        self.conflicts = tuple(dict(row) for row in conflicts)
        super().__init__(
            "inherited construction rules conflict with requested profiles: "
            + canonical_json_bytes_v1(list(self.conflicts)).decode("utf-8")
        )


def canonical_json_bytes_v1(value: object) -> bytes:
    """Return deterministic JSON bytes, rejecting non-finite values."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6PopulationProfileError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _strict_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusR6PopulationProfileError(
            f"{label} must be an exact integer >= {minimum}"
        )
    return value


def _strict_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        raise CorpusR6PopulationProfileError(f"{label} must be a nonempty string")
    return value


def _strict_sha(value: object, *, label: str) -> str:
    retained = _strict_string(value, label=label)
    if _SHA256.fullmatch(retained) is None:
        raise CorpusR6PopulationProfileError(f"{label} must be lowercase SHA-256")
    return retained


@dataclass(frozen=True, slots=True)
class PopulationProfile:
    """One complete, centrally owned construction profile."""

    ordinal: int
    profile_id: str
    comparison_base_profile_id: str
    hypothesis: str
    min_lineup_salary: int
    qb_partner_min: int
    qb_partner_max: int | None
    bring_back_min: int
    bring_back_max: int | None
    max_from_game: int | None
    forbid_rb_vs_dst: bool
    forbid_two_rb_same_team: bool

    def __post_init__(self) -> None:
        _strict_int(self.ordinal, label="profile ordinal")
        _strict_string(self.profile_id, label="profile id")
        _strict_string(
            self.comparison_base_profile_id, label="comparison base profile id"
        )
        _strict_string(self.hypothesis, label="profile hypothesis")
        _strict_int(self.min_lineup_salary, label="minimum lineup salary")
        _strict_int(self.qb_partner_min, label="QB partner minimum")
        _strict_int(self.bring_back_min, label="bring-back minimum")
        for label, value, minimum in (
            ("QB partner maximum", self.qb_partner_max, self.qb_partner_min),
            ("bring-back maximum", self.bring_back_max, self.bring_back_min),
        ):
            if value is not None and (
                type(value) is not int or value < minimum
            ):
                raise CorpusR6PopulationProfileError(
                    f"{label} must be None or an exact integer >= its minimum"
                )
        if self.max_from_game is not None:
            _strict_int(self.max_from_game, label="maximum from game", minimum=1)
        if type(self.forbid_rb_vs_dst) is not bool or type(
            self.forbid_two_rb_same_team
        ) is not bool:
            raise CorpusR6PopulationProfileError(
                "RB structural rules must be literal booleans"
            )

    def body(self) -> dict[str, object]:
        return {
            "schema": PROFILE_SCHEMA,
            "ordinal": self.ordinal,
            "profile_id": self.profile_id,
            "comparison_base_profile_id": self.comparison_base_profile_id,
            "hypothesis": self.hypothesis,
            "constraints": {
                "min_lineup_salary": self.min_lineup_salary,
                "qb_partner_min": self.qb_partner_min,
                "qb_partner_max": self.qb_partner_max,
                "bring_back_min": self.bring_back_min,
                "bring_back_max": self.bring_back_max,
                "max_from_game": self.max_from_game,
                "forbid_rb_vs_dst": self.forbid_rb_vs_dst,
                "forbid_two_rb_same_team": self.forbid_two_rb_same_team,
                "opposing_wr_min": 0,
                "opposing_wr_max": None,
            },
            "dk_classic_hard_rules_preserved": True,
            "profile_owns_all_strategic_constraints": True,
            "production_default_change_licensed": False,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_sha256_v1(self.body())

    def payload(self) -> dict[str, object]:
        return {**self.body(), "profile_sha256": self.fingerprint}

    def as_effective_policy(self) -> EffectivePolicyProfile:
        """Compile into the existing request-local legal model input."""
        parameter_values = {
            "min_lineup_salary": self.min_lineup_salary,
            "qb_stack_min": self.qb_partner_min,
            "bring_back_min": self.bring_back_min,
            "forbid_rb_vs_dst": self.forbid_rb_vs_dst,
            "forbid_two_rb_same_team": self.forbid_two_rb_same_team,
        }
        return EffectivePolicyProfile(
            ordinal=self.ordinal,
            parameter_set_id=self.profile_id,
            parameter_set_sha256=self.fingerprint,
            parameter_values=tuple(
                (name, parameter_values[name]) for name in PARAMETER_ORDER
            ),
            stack=StackRuleDose(
                qb_stack_min=self.qb_partner_min,
                qb_stack_max=self.qb_partner_max,
                bring_back_min=self.bring_back_min,
                bring_back_max=self.bring_back_max,
                forbid_rb_vs_dst=self.forbid_rb_vs_dst,
                forbid_two_rb_same_team=self.forbid_two_rb_same_team,
                require_rb_vs_dst=False,
                require_two_rb_same_team=False,
            ),
            constraints=ConstraintDose(
                budget=rw.SALARY_CAP,
                locks=(),
                bans=(),
                banned_lineups=(),
                max_overlap=rw.ROSTER_SIZE - 1,
                punt_max_salary=None,
                punt_min=0,
                game_lock=None,
                min_salary=self.min_lineup_salary,
                max_salary=None,
                max_per_game=self.max_from_game or 0,
                env=(),
            ),
        )


@dataclass(frozen=True, slots=True)
class InheritedConstraintSurface:
    """Every legacy structure source outside the requested profile."""

    qb_partner_min: int = 0
    qb_partner_max: int | None = None
    bring_back_min: int = 0
    bring_back_max: int | None = None
    opposing_wr_min: int = 0
    opposing_wr_max: int | None = None
    max_from_game: int | None = None
    min_from_game: int = 0
    forced_qb_wr_pair_count: int = 0
    forced_qb_wr_opposing_wr_triplet_count: int = 0
    ambient_profile_overrides: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("inherited QB partner minimum", self.qb_partner_min),
            ("inherited bring-back minimum", self.bring_back_min),
            ("inherited opposing-WR minimum", self.opposing_wr_min),
            ("inherited game minimum", self.min_from_game),
            ("forced QB/WR pair count", self.forced_qb_wr_pair_count),
            (
                "forced QB/WR/opposing-WR triplet count",
                self.forced_qb_wr_opposing_wr_triplet_count,
            ),
        ):
            _strict_int(value, label=label)
        for label, value, minimum in (
            ("inherited QB partner maximum", self.qb_partner_max, 0),
            ("inherited bring-back maximum", self.bring_back_max, 0),
            ("inherited opposing-WR maximum", self.opposing_wr_max, 0),
            ("inherited maximum from game", self.max_from_game, 1),
        ):
            if value is not None:
                _strict_int(value, label=label, minimum=minimum)
        if self.qb_partner_max is not None and (
            self.qb_partner_max < self.qb_partner_min
        ):
            raise CorpusR6PopulationProfileError(
                "inherited QB partner maximum is below its minimum"
            )
        if self.bring_back_max is not None and (
            self.bring_back_max < self.bring_back_min
        ):
            raise CorpusR6PopulationProfileError(
                "inherited bring-back maximum is below its minimum"
            )
        if self.opposing_wr_max is not None and (
            self.opposing_wr_max < self.opposing_wr_min
        ):
            raise CorpusR6PopulationProfileError(
                "inherited opposing-WR maximum is below its minimum"
            )
        overrides = tuple(self.ambient_profile_overrides)
        if overrides != tuple(sorted(overrides)) or len(dict(overrides)) != len(
            overrides
        ) or any(
            type(key) is not str or not key or type(value) is not str
            for key, value in overrides
        ):
            raise CorpusR6PopulationProfileError(
                "ambient profile overrides must be unique sorted string pairs"
            )

    @property
    def neutral(self) -> bool:
        return self == InheritedConstraintSurface()

    def payload(self) -> dict[str, object]:
        return {
            "schema": INHERITED_SURFACE_SCHEMA,
            "qb_partner_min": self.qb_partner_min,
            "qb_partner_max": self.qb_partner_max,
            "bring_back_min": self.bring_back_min,
            "bring_back_max": self.bring_back_max,
            "opposing_wr_min": self.opposing_wr_min,
            "opposing_wr_max": self.opposing_wr_max,
            "max_from_game": self.max_from_game,
            "min_from_game": self.min_from_game,
            "forced_qb_wr_pair_count": self.forced_qb_wr_pair_count,
            "forced_qb_wr_opposing_wr_triplet_count": (
                self.forced_qb_wr_opposing_wr_triplet_count
            ),
            "ambient_profile_overrides": dict(self.ambient_profile_overrides),
        }


@dataclass(frozen=True, slots=True)
class SharedSolverWork:
    """One work dose shared byte-for-byte by every profile."""

    world_blocks: tuple[str, ...] = tuple(rw.WORLD_BLOCKS)
    worlds_per_block: int = WORLDS_PER_BLOCK
    solve_attempts_per_block: int = SOLVE_ATTEMPTS_PER_BLOCK
    solver_timeout_seconds: int = SOLVER_TIMEOUT_SECONDS
    selected_entry_budget: int = SELECTED_ENTRY_BUDGET

    def __post_init__(self) -> None:
        if self.world_blocks != tuple(rw.WORLD_BLOCKS):
            raise CorpusR6PopulationProfileError(
                "shared work must preserve canonical R0..R4 block order"
            )
        worlds = _strict_int(
            self.worlds_per_block, label="worlds per block", minimum=1
        )
        attempts = _strict_int(
            self.solve_attempts_per_block,
            label="solve attempts per block",
            minimum=1,
        )
        if attempts > worlds:
            raise CorpusR6PopulationProfileError(
                "solve attempts per block exceed available worlds"
            )
        _strict_int(
            self.solver_timeout_seconds,
            label="solver timeout seconds",
            minimum=1,
        )
        _strict_int(
            self.selected_entry_budget,
            label="selected entry budget",
            minimum=1,
        )

    @property
    def solves_per_profile_per_slate(self) -> int:
        return len(self.world_blocks) * self.solve_attempts_per_block

    def payload(self) -> dict[str, object]:
        return {
            "schema": WORK_SCHEMA,
            "world_blocks": list(self.world_blocks),
            "worlds_per_block": self.worlds_per_block,
            "solve_attempts_per_block": self.solve_attempts_per_block,
            "solver_timeout_seconds": self.solver_timeout_seconds,
            "selected_entry_budget": self.selected_entry_budget,
            "solves_per_profile_per_slate": self.solves_per_profile_per_slate,
            "profile_specific_overrides": False,
        }


_PROFILES: Final = (
    PopulationProfile(
        ordinal=7,
        profile_id=PROFILE_ORDER[0],
        comparison_base_profile_id="F0-incumbent",
        hypothesis=(
            "the QB-partner and bring-back minima jointly exclude useful "
            "high-tail legal lineups"
        ),
        min_lineup_salary=49_000,
        qb_partner_min=0,
        qb_partner_max=None,
        bring_back_min=0,
        bring_back_max=None,
        max_from_game=None,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
    ),
    PopulationProfile(
        ordinal=8,
        profile_id=PROFILE_ORDER[1],
        comparison_base_profile_id=PROFILE_ORDER[0],
        hypothesis=(
            "winner-like dispersion with no more than three players from one "
            "game improves tail support"
        ),
        min_lineup_salary=49_000,
        qb_partner_min=0,
        qb_partner_max=None,
        bring_back_min=0,
        bring_back_max=None,
        max_from_game=3,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
    ),
    PopulationProfile(
        ordinal=9,
        profile_id=PROFILE_ORDER[2],
        comparison_base_profile_id="F0-incumbent",
        hypothesis=(
            "the modal exactly-one QB pass-catcher shape improves tail support "
            "while retaining an opponent skill-player bring-back"
        ),
        min_lineup_salary=49_000,
        qb_partner_min=1,
        qb_partner_max=1,
        bring_back_min=1,
        bring_back_max=None,
        max_from_game=None,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
    ),
)


def population_profiles_v1() -> tuple[PopulationProfile, ...]:
    """Return the exact immutable F7--F9 registry."""
    return _PROFILES


def population_profile_v1(profile_id: str) -> PopulationProfile:
    for profile in _PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise CorpusR6PopulationProfileError(f"unknown population profile {profile_id!r}")


def population_profile_registry_v1() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": REGISTRY_SCHEMA,
        "profiles": [profile.payload() for profile in _PROFILES],
        "profile_order": list(PROFILE_ORDER),
        "legacy_constraint_audit": list(LEGACY_CONSTRAINT_AUDIT),
        "shared_historical_bank_required": True,
        "production_default_change_licensed": False,
    }
    return {**body, "registry_sha256": canonical_sha256_v1(body)}


def inherited_constraint_surface_v1(
    *,
    stack: StackRules | None = None,
    max_per_game: int | None = None,
    game_lock: tuple[str, int] | None = None,
    environment: Mapping[str, str] | None = None,
    opposing_wr_min: int = 0,
    opposing_wr_max: int | None = None,
    forced_qb_wr_pair_count: int = 0,
    forced_qb_wr_opposing_wr_triplet_count: int = 0,
) -> InheritedConstraintSurface:
    """Normalize legacy engine inputs into the auditable conflict surface."""
    if stack is not None and type(stack) is not StackRules:
        raise CorpusR6PopulationProfileError("inherited stack must be StackRules")
    if game_lock is not None:
        if (
            type(game_lock) is not tuple
            or len(game_lock) != 2
            or type(game_lock[0]) is not str
            or not game_lock[0]
        ):
            raise CorpusR6PopulationProfileError("inherited game lock differs")
        min_from_game = _strict_int(
            game_lock[1], label="inherited game-lock minimum", minimum=1
        )
    else:
        min_from_game = 0
    env = {} if environment is None else dict(environment)
    if any(type(key) is not str or type(value) is not str for key, value in env.items()):
        raise CorpusR6PopulationProfileError(
            "inherited environment must map strings to strings"
        )
    overrides = tuple(sorted(
        (key, env[key]) for key in STRUCTURE_ENV_KEYS if key in env
    ))
    return InheritedConstraintSurface(
        qb_partner_min=0 if stack is None else stack.qb_stack_min,
        qb_partner_max=None if stack is None else stack.qb_stack_max,
        bring_back_min=0 if stack is None else stack.bring_back_min,
        bring_back_max=None if stack is None else stack.bring_back_max,
        opposing_wr_min=opposing_wr_min,
        opposing_wr_max=opposing_wr_max,
        max_from_game=max_per_game,
        min_from_game=min_from_game,
        forced_qb_wr_pair_count=forced_qb_wr_pair_count,
        forced_qb_wr_opposing_wr_triplet_count=(
            forced_qb_wr_opposing_wr_triplet_count
        ),
        ambient_profile_overrides=overrides,
    )


def inherited_constraint_conflicts_v1(
    surface: InheritedConstraintSurface,
    profiles: Sequence[PopulationProfile] | None = None,
) -> tuple[dict[str, object], ...]:
    """Return every non-neutral legacy rule against every affected profile."""
    if type(surface) is not InheritedConstraintSurface:
        raise CorpusR6PopulationProfileError(
            "inherited surface must be InheritedConstraintSurface"
        )
    selected = _PROFILES if profiles is None else tuple(profiles)
    if not selected or any(type(profile) is not PopulationProfile for profile in selected):
        raise CorpusR6PopulationProfileError("profiles must be PopulationProfile rows")
    active: list[tuple[str, object]] = []
    for field in (
        "qb_partner_min",
        "qb_partner_max",
        "bring_back_min",
        "bring_back_max",
        "opposing_wr_min",
        "opposing_wr_max",
        "max_from_game",
        "min_from_game",
        "forced_qb_wr_pair_count",
        "forced_qb_wr_opposing_wr_triplet_count",
    ):
        value = getattr(surface, field)
        if value not in (0, None):
            active.append((field, value))
    active.extend(
        (f"environment:{key}", value)
        for key, value in surface.ambient_profile_overrides
    )
    conflicts: list[dict[str, object]] = []
    for profile in selected:
        intended = profile.body()["constraints"]
        for field, inherited_value in active:
            profile_value = (
                intended.get(field) if isinstance(intended, Mapping) else None
            )
            conflicts.append({
                "profile_id": profile.profile_id,
                "rule": field,
                "inherited_value": inherited_value,
                "profile_value": profile_value,
                "disposition": "reject-multiple-constraint-owners",
            })
    return tuple(conflicts)


def require_neutral_inherited_constraints_v1(
    surface: InheritedConstraintSurface,
    profiles: Sequence[PopulationProfile] | None = None,
) -> None:
    conflicts = inherited_constraint_conflicts_v1(surface, profiles)
    if conflicts:
        raise InheritedConstraintConflict(conflicts)


def build_profile_model_v1(
    players: Sequence[rw.PlayerSpec],
    profile_id: str,
    objective_micro: Sequence[int],
    *,
    construction_serial: int,
    model_name: str,
    inherited_surface: InheritedConstraintSurface | None = None,
) -> FreshLegalModel:
    """Build one executable DK model without consulting production state."""
    profile = population_profile_v1(profile_id)
    surface = inherited_surface or InheritedConstraintSurface()
    require_neutral_inherited_constraints_v1(surface, (profile,))
    return build_fresh_legal_model(
        players,
        profile.as_effective_policy(),
        objective_micro,
        construction_serial=construction_serial,
        model_name=model_name,
    )


def roster_shape_v1(
    players: Sequence[rw.PlayerSpec], roster: Sequence[object]
) -> dict[str, object]:
    identity = audit_dk_classic(players, roster)
    by_id = {player.player_id: player for player in players}
    chosen = tuple(by_id[player_id] for player_id in identity)
    qb = next(player for player in chosen if player.position == "QB")
    dst = next(player for player in chosen if player.position == "DST")
    game_counts = Counter(player.game_id for player in chosen)
    return {
        "roster": list(identity),
        "salary": sum(player.salary for player in chosen),
        "qb_partner_count": sum(
            player.team == qb.team and player.position in {"WR", "TE"}
            for player in chosen
        ),
        "bring_back_count": sum(
            player.team == qb.opponent and player.position in {"RB", "WR", "TE"}
            for player in chosen
        ),
        "opposing_wr_count": sum(
            player.team == qb.opponent and player.position == "WR"
            for player in chosen
        ),
        "max_from_game": max(game_counts.values()),
        "rb_vs_dst_count": sum(
            player.position == "RB" and player.team == dst.opponent
            for player in chosen
        ),
        "same_team_rb_pair_count": sum(
            count * (count - 1) // 2
            for count in Counter(
                player.team for player in chosen if player.position == "RB"
            ).values()
        ),
    }


def audit_profile_roster_v1(
    players: Sequence[rw.PlayerSpec],
    roster: Sequence[object],
    profile_id: str,
) -> dict[str, object]:
    """Require DK legality and the exact requested profile shape."""
    profile = population_profile_v1(profile_id)
    shape = roster_shape_v1(players, roster)
    violations: list[str] = []
    if int(shape["salary"]) < profile.min_lineup_salary:
        violations.append("min_lineup_salary")
    partners = int(shape["qb_partner_count"])
    if partners < profile.qb_partner_min or (
        profile.qb_partner_max is not None and partners > profile.qb_partner_max
    ):
        violations.append("qb_partner_range")
    bring_backs = int(shape["bring_back_count"])
    if bring_backs < profile.bring_back_min or (
        profile.bring_back_max is not None
        and bring_backs > profile.bring_back_max
    ):
        violations.append("bring_back_range")
    if profile.max_from_game is not None and (
        int(shape["max_from_game"]) > profile.max_from_game
    ):
        violations.append("max_from_game")
    if profile.forbid_rb_vs_dst and int(shape["rb_vs_dst_count"]):
        violations.append("forbid_rb_vs_dst")
    if profile.forbid_two_rb_same_team and int(
        shape["same_team_rb_pair_count"]
    ):
        violations.append("forbid_two_rb_same_team")
    if violations:
        raise CorpusR6PopulationProfileError(
            f"roster violates {profile_id}: {tuple(violations)}"
        )
    return {
        **shape,
        "profile_id": profile.profile_id,
        "profile_sha256": profile.fingerprint,
    }


def iter_equal_work_cells_v1(
    work: SharedSolverWork,
) -> Iterator[tuple[str, str, int]]:
    """Yield the identical block/visit lattice once for each profile."""
    if type(work) is not SharedSolverWork:
        raise CorpusR6PopulationProfileError("work must be SharedSolverWork")
    for profile in _PROFILES:
        for block in work.world_blocks:
            for visit in range(work.solve_attempts_per_block):
                yield profile.profile_id, block, visit


def _normalize_object_identity(
    value: object, *, label: str
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes"
    }:
        raise CorpusR6PopulationProfileError(f"{label} content identity differs")
    uri = _strict_string(value["uri"], label=f"{label} URI")
    generation = _strict_string(
        value["generation"], label=f"{label} generation"
    )
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusR6PopulationProfileError(f"{label} generation differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _strict_sha(value["sha256"], label=f"{label} SHA-256"),
        "bytes": _strict_int(value["bytes"], label=f"{label} bytes", minimum=1),
    }


def build_shared_historical_bank_plan_v1(
    *,
    run_id: str,
    source_identities_by_slate: Mapping[str, Mapping[str, object]],
    world_schedule_sha256_by_slate: Mapping[str, str],
    source_commit_sha: str,
    module_sha256: str,
    solver_identity: Mapping[str, object],
    inherited_surface: InheritedConstraintSurface,
    work: SharedSolverWork | None = None,
) -> dict[str, object]:
    """Bind profiles, equal work, code, solver, and immutable slate sources."""
    _strict_string(run_id, label="run id")
    commit = _strict_string(source_commit_sha, label="source commit")
    if _COMMIT.fullmatch(commit) is None:
        raise CorpusR6PopulationProfileError(
            "source commit must be lowercase 40-hex"
        )
    module_digest = _strict_sha(module_sha256, label="module SHA-256")
    selected_work = work or SharedSolverWork()
    require_neutral_inherited_constraints_v1(inherited_surface)
    if (
        not isinstance(source_identities_by_slate, Mapping)
        or not source_identities_by_slate
        or not isinstance(world_schedule_sha256_by_slate, Mapping)
        or set(source_identities_by_slate) != set(world_schedule_sha256_by_slate)
    ):
        raise CorpusR6PopulationProfileError(
            "source and world-schedule slate sets must be equal and nonempty"
        )
    source_rows = []
    for slate_id in sorted(source_identities_by_slate):
        _strict_string(slate_id, label="slate id")
        source_rows.append({
            "slate_id": slate_id,
            "source_identity": _normalize_object_identity(
                source_identities_by_slate[slate_id],
                label=f"source {slate_id}",
            ),
            "world_schedule_sha256": _strict_sha(
                world_schedule_sha256_by_slate[slate_id],
                label=f"world schedule {slate_id}",
            ),
        })
    if not isinstance(solver_identity, Mapping) or set(solver_identity) != {
        "name", "version", "binary_sha256", "options_sha256", "exact_mode"
    }:
        raise CorpusR6PopulationProfileError("solver identity fields differ")
    if solver_identity["exact_mode"] is not True:
        raise CorpusR6PopulationProfileError("solver must be exact mode")
    solver = {
        "name": _strict_string(solver_identity["name"], label="solver name"),
        "version": _strict_string(
            solver_identity["version"], label="solver version"
        ),
        "binary_sha256": _strict_sha(
            solver_identity["binary_sha256"], label="solver binary SHA-256"
        ),
        "options_sha256": _strict_sha(
            solver_identity["options_sha256"], label="solver options SHA-256"
        ),
        "exact_mode": True,
    }
    registry = population_profile_registry_v1()
    work_payload = selected_work.payload()
    work_sha = canonical_sha256_v1(work_payload)
    body: dict[str, object] = {
        "schema": SHARED_BANK_PLAN_SCHEMA,
        "run_id": run_id,
        "profile_registry": registry,
        "profile_registry_sha256": registry["registry_sha256"],
        "work": work_payload,
        "work_sha256": work_sha,
        "work_sha256_by_profile": {
            profile.profile_id: work_sha for profile in _PROFILES
        },
        "total_solve_attempts": (
            len(source_rows)
            * len(_PROFILES)
            * selected_work.solves_per_profile_per_slate
        ),
        "sources": source_rows,
        "code_identity": {
            "source_commit_sha": commit,
            "module_path": MODULE_PATH,
            "module_sha256": module_digest,
        },
        "solver_identity": solver,
        "inherited_constraint_surface": inherited_surface.payload(),
        "inherited_constraint_conflicts": [],
        "direct_request_local_model_seam": (
            "corpus_legal_feasibility.build_fresh_legal_model"
        ),
        "outcome_blind_generation": True,
        "realized_outcomes_read": False,
        "production_default_changes": [],
        "production_change_licensed": False,
    }
    return {**body, "plan_sha256": canonical_sha256_v1(body)}


def validate_shared_historical_bank_plan_v1(
    value: object,
) -> dict[str, object]:
    """Fail closed on tampering or unequal per-profile work identity."""
    if not isinstance(value, Mapping):
        raise CorpusR6PopulationProfileError("shared bank plan must be an object")
    plan = dict(value)
    expected_keys = {
        "schema", "run_id", "profile_registry", "profile_registry_sha256",
        "work", "work_sha256", "work_sha256_by_profile",
        "total_solve_attempts", "sources", "code_identity", "solver_identity",
        "inherited_constraint_surface", "inherited_constraint_conflicts",
        "direct_request_local_model_seam", "outcome_blind_generation",
        "realized_outcomes_read", "production_default_changes",
        "production_change_licensed", "plan_sha256",
    }
    if set(plan) != expected_keys or plan["schema"] != SHARED_BANK_PLAN_SCHEMA:
        raise CorpusR6PopulationProfileError("shared bank plan fields differ")
    plan_sha = _strict_sha(plan["plan_sha256"], label="plan SHA-256")
    if canonical_sha256_v1({
        key: item for key, item in plan.items() if key != "plan_sha256"
    }) != plan_sha:
        raise CorpusR6PopulationProfileError("shared bank plan SHA-256 differs")
    registry = population_profile_registry_v1()
    if (
        plan["profile_registry"] != registry
        or plan["profile_registry_sha256"] != registry["registry_sha256"]
    ):
        raise CorpusR6PopulationProfileError("shared bank profile registry differs")
    work_raw = plan["work"]
    if not isinstance(work_raw, Mapping) or set(work_raw) != {
        "schema", "world_blocks", "worlds_per_block",
        "solve_attempts_per_block", "solver_timeout_seconds",
        "selected_entry_budget", "solves_per_profile_per_slate",
        "profile_specific_overrides",
    } or work_raw.get("schema") != WORK_SCHEMA:
        raise CorpusR6PopulationProfileError("shared bank work fields differ")
    try:
        retained_work = SharedSolverWork(
            world_blocks=tuple(work_raw["world_blocks"]),
            worlds_per_block=work_raw["worlds_per_block"],
            solve_attempts_per_block=work_raw["solve_attempts_per_block"],
            solver_timeout_seconds=work_raw["solver_timeout_seconds"],
            selected_entry_budget=work_raw["selected_entry_budget"],
        )
    except (TypeError, KeyError) as exc:
        raise CorpusR6PopulationProfileError(
            "shared bank work payload differs"
        ) from exc
    if dict(work_raw) != retained_work.payload():
        raise CorpusR6PopulationProfileError("shared bank work payload differs")
    work_sha = _strict_sha(plan["work_sha256"], label="work SHA-256")
    if canonical_sha256_v1(plan["work"]) != work_sha or plan[
        "work_sha256_by_profile"
    ] != {profile_id: work_sha for profile_id in PROFILE_ORDER}:
        raise CorpusR6PopulationProfileError("per-profile solver work differs")
    sources_raw = plan["sources"]
    if isinstance(sources_raw, (str, bytes)) or not isinstance(
        sources_raw, Sequence
    ) or not sources_raw:
        raise CorpusR6PopulationProfileError("shared bank sources differ")
    normalized_sources: list[dict[str, object]] = []
    for index, raw in enumerate(sources_raw):
        if not isinstance(raw, Mapping) or set(raw) != {
            "slate_id", "source_identity", "world_schedule_sha256"
        }:
            raise CorpusR6PopulationProfileError("shared bank source row differs")
        slate_id = _strict_string(raw["slate_id"], label=f"source[{index}] slate id")
        normalized_sources.append({
            "slate_id": slate_id,
            "source_identity": _normalize_object_identity(
                raw["source_identity"], label=f"source[{index}]"
            ),
            "world_schedule_sha256": _strict_sha(
                raw["world_schedule_sha256"],
                label=f"source[{index}] world schedule SHA-256",
            ),
        })
    if normalized_sources != list(sources_raw) or [
        row["slate_id"] for row in normalized_sources
    ] != sorted(row["slate_id"] for row in normalized_sources) or len({
        row["slate_id"] for row in normalized_sources
    }) != len(normalized_sources):
        raise CorpusR6PopulationProfileError(
            "shared bank sources are not unique canonical slate order"
        )
    expected_total = (
        len(normalized_sources)
        * len(PROFILE_ORDER)
        * retained_work.solves_per_profile_per_slate
    )
    if _strict_int(
        plan["total_solve_attempts"], label="total solve attempts", minimum=1
    ) != expected_total:
        raise CorpusR6PopulationProfileError("total solve attempts differ")
    code = plan["code_identity"]
    if not isinstance(code, Mapping) or set(code) != {
        "source_commit_sha", "module_path", "module_sha256"
    }:
        raise CorpusR6PopulationProfileError("shared bank code identity differs")
    commit = _strict_string(code["source_commit_sha"], label="source commit")
    if (
        _COMMIT.fullmatch(commit) is None
        or code["module_path"] != MODULE_PATH
        or _SHA256.fullmatch(
            _strict_string(code["module_sha256"], label="module SHA-256")
        ) is None
    ):
        raise CorpusR6PopulationProfileError("shared bank code identity differs")
    solver = plan["solver_identity"]
    if not isinstance(solver, Mapping) or set(solver) != {
        "name", "version", "binary_sha256", "options_sha256", "exact_mode"
    } or solver["exact_mode"] is not True:
        raise CorpusR6PopulationProfileError("shared bank solver identity differs")
    _strict_string(solver["name"], label="solver name")
    _strict_string(solver["version"], label="solver version")
    _strict_sha(solver["binary_sha256"], label="solver binary SHA-256")
    _strict_sha(solver["options_sha256"], label="solver options SHA-256")
    if (
        plan["inherited_constraint_surface"]
        != InheritedConstraintSurface().payload()
        or plan["inherited_constraint_conflicts"] != []
        or plan["direct_request_local_model_seam"]
        != "corpus_legal_feasibility.build_fresh_legal_model"
        or plan["outcome_blind_generation"] is not True
        or plan["realized_outcomes_read"] is not False
        or plan["production_default_changes"] != []
        or plan["production_change_licensed"] is not False
    ):
        raise CorpusR6PopulationProfileError("shared bank safety boundary differs")
    return plan


__all__ = [
    "CorpusR6PopulationProfileError",
    "InheritedConstraintConflict",
    "InheritedConstraintSurface",
    "LEGACY_CONSTRAINT_AUDIT",
    "MODULE_PATH",
    "PROFILE_ORDER",
    "PopulationProfile",
    "SharedSolverWork",
    "audit_profile_roster_v1",
    "build_profile_model_v1",
    "build_shared_historical_bank_plan_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "inherited_constraint_conflicts_v1",
    "inherited_constraint_surface_v1",
    "iter_equal_work_cells_v1",
    "population_profile_registry_v1",
    "population_profile_v1",
    "population_profiles_v1",
    "require_neutral_inherited_constraints_v1",
    "roster_shape_v1",
    "validate_shared_historical_bank_plan_v1",
]
