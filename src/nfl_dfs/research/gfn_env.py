"""Deterministic legal lineup-construction environment for the GFlowNet
workstream (emerging-technologies-plan.md §5.3-5.4).

Lineup construction is a finite DAG walk over a canonical slot order

    QB, RB, RB, WR, WR, WR, TE, FLEX, DST

where each action adds one eligible player to the next open slot. Hard
masks enforce, *before* an action is taken:

- salary cap and registered salary floor (default 49_000);
- roster-slot position rules (FLEX in {RB, WR, TE}); the slot structure
  itself guarantees the DK totals of max 3 RB / 4 WR / 2 TE;
- no duplicate players;
- max players per team (``MAX_FROM_TEAM`` reused from the MILP optimizer);
- minimum number of distinct games (``MIN_GAMES``);
- feasibility lookahead: the remaining slots must be completable within
  the remaining salary window, checked exactly by a bounded depth-first
  search whose pruning uses the cheapest / most expensive remaining
  eligible players per slot.

Legality is therefore guaranteed by construction: every completed
trajectory is a legal lineup, never repaired after sampling.

Canonicalization (plan §5.3): within each of RB / WR / TE the player
indices must be strictly increasing over the pick order (fixed slots
first, FLEX last). Because the FLEX position of a player set is
determined by its position counts, every legal *player set* corresponds
to exactly one trajectory. That removes slot symmetry from diversity
metrics and makes the GFlowNet backward policy deterministic
(log P_B = 0), so trajectory balance simplifies exactly.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Iterator

import numpy as np

from nfl_dfs.optimizer.lineup import MAX_FROM_TEAM, MIN_GAMES, ROSTER_SIZE, SALARY_CAP

Player = dict[str, Any]  # id, name, pos, team, opp, game_id, salary, proj
State = tuple[int, ...]  # player indices (into env.players) in slot order

SLOT_ORDER: tuple[str, ...] = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
FLEX_POSITIONS: tuple[str, ...] = ("RB", "WR", "TE")
DEFAULT_SALARY_FLOOR = 49_000

_ORDERED_POSITIONS = frozenset(FLEX_POSITIONS)  # positions with >1 possible slot

# DFS safety valve: legality must never silently degrade, so exhausting
# the budget is an error, not a masked action.
_FEASIBILITY_NODE_BUDGET = 200_000


def canonical_hash(player_ids: Iterable[Any]) -> str:
    """Order-independent hash of a lineup's player set (plan §5.3)."""
    key = "|".join(sorted(str(i) for i in player_ids))
    return hashlib.sha1(key.encode()).hexdigest()


def check_lineup(
    players: list[Player],
    salary_cap: int = SALARY_CAP,
    salary_floor: int = DEFAULT_SALARY_FLOOR,
    max_from_team: int = MAX_FROM_TEAM,
    min_games: int = MIN_GAMES,
) -> list[str]:
    """Independent legality audit. Returns a list of violations (empty = legal).

    Used by tests and the gate script to verify environment output without
    trusting the environment's own masks.
    """
    violations: list[str] = []
    if len(players) != ROSTER_SIZE:
        violations.append(f"roster size {len(players)} != {ROSTER_SIZE}")
    ids = [p["id"] for p in players]
    if len(set(ids)) != len(ids):
        violations.append("duplicate players")
    counts: dict[str, int] = {}
    for p in players:
        counts[p["pos"]] = counts.get(p["pos"], 0) + 1
    if counts.get("QB", 0) != 1:
        violations.append(f"QB count {counts.get('QB', 0)} != 1")
    if counts.get("DST", 0) != 1:
        violations.append(f"DST count {counts.get('DST', 0)} != 1")
    if not 2 <= counts.get("RB", 0) <= 3:
        violations.append(f"RB count {counts.get('RB', 0)} outside 2-3")
    if not 3 <= counts.get("WR", 0) <= 4:
        violations.append(f"WR count {counts.get('WR', 0)} outside 3-4")
    if not 1 <= counts.get("TE", 0) <= 2:
        violations.append(f"TE count {counts.get('TE', 0)} outside 1-2")
    salary = sum(p["salary"] for p in players)
    if salary > salary_cap:
        violations.append(f"salary {salary} > cap {salary_cap}")
    if salary < salary_floor:
        violations.append(f"salary {salary} < floor {salary_floor}")
    team_counts: dict[str, int] = {}
    for p in players:
        team_counts[p["team"]] = team_counts.get(p["team"], 0) + 1
    for team, n in team_counts.items():
        if n > max_from_team:
            violations.append(f"{n} players from {team} > {max_from_team}")
    games = {p.get("game_id") for p in players}
    if len(games) < min_games:
        violations.append(f"{len(games)} games < {min_games}")
    return violations


class LineupEnv:
    """Legal-by-construction lineup environment over a fixed player pool.

    States are immutable tuples of player indices in canonical slot order;
    actions are player indices for the next open slot. ``legal_actions``
    only offers actions from which a legal terminal lineup remains
    reachable (exact feasibility lookahead), so rollouts never dead-end.
    """

    def __init__(
        self,
        players: list[Player],
        salary_cap: int = SALARY_CAP,
        salary_floor: int = DEFAULT_SALARY_FLOOR,
        max_from_team: int = MAX_FROM_TEAM,
        min_games: int = MIN_GAMES,
    ):
        if salary_floor > salary_cap:
            raise ValueError("salary_floor > salary_cap")
        for p in players:
            missing = [
                k for k in ("id", "pos", "team", "game_id", "salary")
                if p.get(k) is None
            ]
            if missing:
                raise ValueError(f"player {p.get('id')!r} missing fields {missing}")
        if len({p["id"] for p in players}) != len(players):
            raise ValueError("duplicate player ids in pool")
        self.players = players
        self.n_players = len(players)
        self.salary_cap = salary_cap
        self.salary_floor = salary_floor
        self.max_from_team = max_from_team
        self.min_games = min_games

        self._salaries = [p["salary"] for p in players]
        self._pos = [p["pos"] for p in players]
        self._teams = [p["team"] for p in players]
        self._games = [p["game_id"] for p in players]

        # Static per-slot candidate index lists (position eligibility only),
        # and suffix salary bounds for DFS pruning: suffix_min[s] is a lower
        # bound on the cheapest completion of slots s.. (repeats allowed, so
        # it never overestimates); suffix_max[s] the symmetric upper bound.
        self._slot_candidates: list[list[int]] = []
        for slot in SLOT_ORDER:
            allowed = FLEX_POSITIONS if slot == "FLEX" else (slot,)
            idxs = [i for i in range(self.n_players) if self._pos[i] in allowed]
            if not idxs:
                raise ValueError(f"no players eligible for slot {slot}")
            self._slot_candidates.append(idxs)
        slot_min = [min(self._salaries[i] for i in c) for c in self._slot_candidates]
        slot_max = [max(self._salaries[i] for i in c) for c in self._slot_candidates]
        n_slots = len(SLOT_ORDER)
        self._suffix_min = [0] * (n_slots + 1)
        self._suffix_max = [0] * (n_slots + 1)
        for s in range(n_slots - 1, -1, -1):
            self._suffix_min[s] = slot_min[s] + self._suffix_min[s + 1]
            self._suffix_max[s] = slot_max[s] + self._suffix_max[s + 1]

        self._legal_cache: dict[State, list[int]] = {}
        if not self.legal_actions(()):
            raise ValueError("infeasible slate: no legal lineup exists")

    # -- basic state accessors ------------------------------------------

    def reset(self) -> State:
        return ()

    def is_terminal(self, state: State) -> bool:
        return len(state) == len(SLOT_ORDER)

    def lineup_players(self, state: State) -> list[Player]:
        return [self.players[i] for i in state]

    def salary(self, state: State) -> int:
        return sum(self._salaries[i] for i in state)

    def lineup_hash(self, state: State) -> str:
        return canonical_hash(self.players[i]["id"] for i in state)

    # -- transition ------------------------------------------------------

    def step(self, state: State, action: int) -> State:
        if action not in self.legal_actions(state):
            raise ValueError(
                f"illegal action {action} at slot {len(state)} ({SLOT_ORDER[len(state)]})"
            )
        return state + (action,)

    def mask(self, state: State) -> np.ndarray:
        """Boolean mask over all players: True = legal next action."""
        m = np.zeros(self.n_players, dtype=bool)
        m[self.legal_actions(state)] = True
        return m

    def legal_actions(self, state: State) -> list[int]:
        """Player indices addable at the next slot such that a legal
        terminal lineup remains reachable. Empty only for terminal states."""
        if self.is_terminal(state):
            return []
        cached = self._legal_cache.get(state)
        if cached is not None:
            return cached
        slot_idx = len(state)
        used = set(state)
        spent = self.salary(state)
        team_counts: dict[str, int] = {}
        for i in state:
            team_counts[self._teams[i]] = team_counts.get(self._teams[i], 0) + 1
        pos_max = self._pos_max(state)
        games = {self._games[i] for i in state}

        legal: list[int] = []
        for i in self._static_eligible(slot_idx, used, team_counts, pos_max):
            budget = [_FEASIBILITY_NODE_BUDGET]
            if self._completable(
                used | {i},
                spent + self._salaries[i],
                self._bump(team_counts, self._teams[i]),
                games | {self._games[i]},
                slot_idx + 1,
                self._bump_pos_max(pos_max, i),
                budget,
            ):
                legal.append(i)
        self._legal_cache[state] = legal
        return legal

    # -- internals -------------------------------------------------------

    def _pos_max(self, state: State) -> dict[str, int]:
        """Highest chosen index per ordered position (canonicalization)."""
        pos_max: dict[str, int] = {}
        for i in state:
            pos = self._pos[i]
            if pos in _ORDERED_POSITIONS:
                pos_max[pos] = max(pos_max.get(pos, -1), i)
        return pos_max

    def _bump(self, counts: dict[str, int], team: str) -> dict[str, int]:
        out = dict(counts)
        out[team] = out.get(team, 0) + 1
        return out

    def _bump_pos_max(self, pos_max: dict[str, int], i: int) -> dict[str, int]:
        pos = self._pos[i]
        if pos not in _ORDERED_POSITIONS:
            return pos_max
        out = dict(pos_max)
        out[pos] = max(out.get(pos, -1), i)
        return out

    def _static_eligible(
        self,
        slot_idx: int,
        used: set[int],
        team_counts: dict[str, int],
        pos_max: dict[str, int],
    ) -> list[int]:
        """Slot/duplicate/team/ordering eligibility, before lookahead."""
        out = []
        for i in self._slot_candidates[slot_idx]:
            if i in used:
                continue
            if team_counts.get(self._teams[i], 0) >= self.max_from_team:
                continue
            pos = self._pos[i]
            if pos in _ORDERED_POSITIONS and i <= pos_max.get(pos, -1):
                continue
            out.append(i)
        return out

    def _completable(
        self,
        used: set[int],
        spent: int,
        team_counts: dict[str, int],
        games: set,
        slot_idx: int,
        pos_max: dict[str, int],
        budget: list[int],
    ) -> bool:
        """Exact lookahead: can slots ``slot_idx..`` be filled legally?

        Depth-first search over remaining slots; pruning uses the
        cheapest / most expensive remaining eligible salary per slot
        (``_suffix_min`` / ``_suffix_max``) against the cap and floor.
        """
        budget[0] -= 1
        if budget[0] < 0:
            raise RuntimeError(
                "feasibility search budget exhausted; pool too adversarial "
                "for exact lookahead"
            )
        if slot_idx == len(SLOT_ORDER):
            return (
                self.salary_floor <= spent <= self.salary_cap
                and len(games) >= self.min_games
            )
        if spent + self._suffix_min[slot_idx] > self.salary_cap:
            return False
        if spent + self._suffix_max[slot_idx] < self.salary_floor:
            return False

        candidates = self._static_eligible(slot_idx, used, team_counts, pos_max)
        if not candidates:
            return False
        # Aim for the middle of the remaining salary window so the first
        # dive usually lands inside [floor, cap].
        slots_left = len(SLOT_ORDER) - slot_idx
        lo = max(0, self.salary_floor - spent)
        hi = self.salary_cap - spent
        target = (lo + hi) / 2 / slots_left
        for i in sorted(candidates, key=lambda j: abs(self._salaries[j] - target)):
            if self._completable(
                used | {i},
                spent + self._salaries[i],
                self._bump(team_counts, self._teams[i]),
                games | {self._games[i]},
                slot_idx + 1,
                self._bump_pos_max(pos_max, i),
                budget,
            ):
                return True
        return False

    # -- canonical trajectories and enumeration -------------------------

    def actions_for_lineup(self, player_ids: Iterable[Any]) -> list[int]:
        """The unique canonical action sequence building this player set.

        Used to warm-start training from existing (e.g. MILP) lineups.
        Raises ValueError if the set is not a legal lineup for this env.
        """
        id_to_idx = {p["id"]: i for i, p in enumerate(self.players)}
        try:
            idxs = [id_to_idx[i] for i in player_ids]
        except KeyError as exc:
            raise ValueError(f"player {exc.args[0]!r} not in pool") from exc
        by_pos: dict[str, list[int]] = {}
        for i in idxs:
            by_pos.setdefault(self._pos[i], []).append(i)
        for v in by_pos.values():
            v.sort()

        n_rb = len(by_pos.get("RB", []))
        n_wr = len(by_pos.get("WR", []))
        n_te = len(by_pos.get("TE", []))
        flex_pos = {(3, 3, 1): "RB", (2, 4, 1): "WR", (2, 3, 2): "TE"}.get(
            (n_rb, n_wr, n_te)
        )
        if (
            flex_pos is None
            or len(by_pos.get("QB", [])) != 1
            or len(by_pos.get("DST", [])) != 1
            or len(idxs) != ROSTER_SIZE
        ):
            raise ValueError("player set does not fit QB/2RB/3WR/TE/FLEX/DST")

        rb, wr, te = by_pos["RB"], by_pos["WR"], by_pos["TE"]
        flex = {"RB": rb, "WR": wr, "TE": te}[flex_pos][-1]
        actions = (
            by_pos["QB"] + rb[:2] + wr[:3] + te[:1] + [flex] + by_pos["DST"]
        )
        # Replay through the masks so illegality is caught, not assumed.
        state: State = ()
        for a in actions:
            state = self.step(state, a)
        return actions

    def enumerate_lineups(self) -> Iterator[State]:
        """All legal terminal states (tiny slates only — exponential)."""

        def walk(state: State) -> Iterator[State]:
            if self.is_terminal(state):
                yield state
                return
            for a in self.legal_actions(state):
                yield from walk(state + (a,))

        yield from walk(())
