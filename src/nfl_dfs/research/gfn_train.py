"""GFlowNet training loop for the lineup generator (plan §5.6-5.7).

Reward (plan §5.6): utility is computed *pre-lock only* — here
``P(lineup total >= line)`` estimated from a correlated draws matrix
(players x sims), the same draw machinery the simulator produces. The
GFlowNet reward transformation is the registered stable form

    reward = epsilon + exp(clip((utility - center) / temperature, lo, hi))

Actual historical scores are never used as training reward; they are
reserved for held-out candidate-frontier evaluation (gate script).

Training sequence (plan §5.7 steps 1-4): deterministic legal env with
verified masks; warm-start replay from existing MILP lineups; trajectory
balance on simulator rewards; off-policy replay of completed
trajectories (both strong and weak).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
import torch

from nfl_dfs.research.gfn_env import LineupEnv, State, canonical_hash
from nfl_dfs.research.gfn_model import GFNPolicy, trajectory_balance_loss


@dataclass
class RewardConfig:
    """reward = epsilon + exp(clip((utility - center) / temperature, lo, hi))

    center is fitted from early training samples when None (never from the
    evaluation draws — pass ``sim_cols`` to hold columns out).
    """

    epsilon: float = 1e-6
    center: float | None = None
    temperature: float = 0.05
    clip_low: float = -8.0
    clip_high: float = 8.0

    def log_reward(self, utility: float) -> float:
        center = 0.0 if self.center is None else self.center
        z = np.clip((utility - center) / self.temperature, self.clip_low, self.clip_high)
        return float(np.log(self.epsilon + np.exp(z)))


def lineup_utility(
    indices: Sequence[int],
    draws: np.ndarray,
    line: float,
    sim_cols: np.ndarray | slice | None = None,
) -> float:
    """P(lineup total >= line) from draws[player_idx, sim]."""
    cols = slice(None) if sim_cols is None else sim_cols
    totals = draws[np.asarray(list(indices))][:, cols].sum(axis=0)
    return float((totals >= line).mean())


class ReplayBuffer:
    """Uniform replay of completed trajectories (actions + log-reward),
    deduplicated by canonical lineup hash."""

    def __init__(self, capacity: int = 4096):
        self.capacity = capacity
        self._items: dict[str, tuple[list[int], float]] = {}

    def add(self, key: str, actions: list[int], log_reward: float) -> None:
        if key not in self._items and len(self._items) >= self.capacity:
            oldest = next(iter(self._items))
            del self._items[oldest]
        self._items[key] = (actions, log_reward)

    def __len__(self) -> int:
        return len(self._items)

    def sample(self, n: int, rng: np.random.Generator) -> list[tuple[list[int], float]]:
        items = list(self._items.values())
        if not items:
            return []
        picks = rng.choice(len(items), size=min(n, len(items)), replace=False)
        return [items[i] for i in picks]


@dataclass
class TrainResult:
    policy: GFNPolicy
    reward_cfg: RewardConfig
    history: list[dict] = field(default_factory=list)
    warm_started: int = 0
    warm_skipped: int = 0


def warm_start_buffer(
    env: LineupEnv,
    buffer: ReplayBuffer,
    lineups: Iterable[Any],
    draws: np.ndarray,
    line: float,
    reward_cfg: RewardConfig,
    sim_cols: np.ndarray | slice | None = None,
) -> tuple[int, int]:
    """Seed the replay buffer from existing lineups (plan §5.7 step 2).

    Accepts iterables of player ids or objects with ``.players`` dicts
    (``nfl_dfs.optimizer.lineup.Lineup``). Lineups illegal under this
    environment (e.g. below the salary floor) are skipped, not repaired.
    Returns (n_added, n_skipped).
    """
    added = skipped = 0
    for lu in lineups:
        ids = [p["id"] for p in lu.players] if hasattr(lu, "players") else list(lu)
        try:
            actions = env.actions_for_lineup(ids)
        except ValueError:
            skipped += 1
            continue
        u = lineup_utility(actions, draws, line, sim_cols)
        buffer.add(canonical_hash(ids), actions, reward_cfg.log_reward(u))
        added += 1
    return added, skipped


def train_gfn(
    env: LineupEnv,
    draws: np.ndarray,
    line: float,
    steps: int = 200,
    batch_size: int = 8,
    replay_batch: int = 8,
    lr: float = 5e-3,
    explore_eps: float = 0.1,
    hidden: int = 64,
    quantile_cols: tuple[str, ...] = (),
    warm_start_lineups: Iterable[Any] | None = None,
    reward_cfg: RewardConfig | None = None,
    sim_cols: np.ndarray | slice | None = None,
    seed: int = 0,
    policy: GFNPolicy | None = None,
) -> TrainResult:
    """Train a GFlowNet policy on one slate.

    ``draws`` is a (n_players x n_sims) correlated outcome matrix aligned
    with ``env.players``; ``sim_cols`` restricts reward estimation to a
    training subset so evaluation columns stay held out.
    """
    if draws.shape[0] != env.n_players:
        raise ValueError("draws must be aligned with env.players (rows)")
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    if policy is None:
        policy = GFNPolicy(env, hidden=hidden, quantile_cols=quantile_cols)
    cfg = reward_cfg or RewardConfig()
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    buffer = ReplayBuffer()
    reward_cache: dict[str, float] = {}

    def utility_of(state: State) -> float:
        return lineup_utility(state, draws, line, sim_cols)

    # Fit the reward center from an initial untrained batch (plan §5.6:
    # never fitted on evaluation data — sim_cols already excludes it).
    if cfg.center is None:
        probe = policy.sample(max(16, batch_size), explore_eps=1.0, rng=rng)
        cfg.center = float(np.median([utility_of(s) for s in probe]))

    result = TrainResult(policy=policy, reward_cfg=cfg)
    if warm_start_lineups is not None:
        result.warm_started, result.warm_skipped = warm_start_buffer(
            env, buffer, warm_start_lineups, draws, line, cfg, sim_cols
        )

    for step in range(steps):
        states = policy.sample(batch_size, explore_eps=explore_eps, rng=rng)
        batch: list[tuple[list[int], float]] = []
        utils = []
        for s in states:
            key = env.lineup_hash(s)
            if key not in reward_cache:
                reward_cache[key] = cfg.log_reward(utility_of(s))
            batch.append((list(s), reward_cache[key]))
            utils.append(utility_of(s))
            buffer.add(key, list(s), reward_cache[key])
        batch.extend(buffer.sample(replay_batch, rng))

        trajectories = [b[0] for b in batch]
        log_r = torch.tensor([b[1] for b in batch], dtype=torch.float32)
        loss = trajectory_balance_loss(policy, trajectories, log_r)
        opt.zero_grad()
        loss.backward()
        opt.step()
        result.history.append(
            {
                "step": step,
                "loss": float(loss.item()),
                "logZ": float(policy.logZ.item()),
                "mean_utility": float(np.mean(utils)),
            }
        )
    return result
