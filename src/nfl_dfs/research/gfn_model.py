"""Compact GFlowNet policy over the lineup environment (plan §5.5).

Architecture, deliberately small (few historical slates, see §5.5):

- per-player MLP encoder over projection, quantiles, salary, position
  one-hot, plus learned team and game embeddings;
- mean-pooled slate context;
- partial-lineup state = mean of chosen players' encodings + scalar
  state features (salary spent, slots remaining, next-slot type, games);
- a per-player scoring head producing action logits, masked to the
  environment's legal actions.

Trained with trajectory balance (learnable ``logZ``). Because the
environment admits exactly one trajectory per legal player set (see
``gfn_env`` canonicalization), the backward policy is deterministic and
``log P_B = 0``, so TB reduces to

    loss = (logZ + sum_t log P_F(a_t | s_t) - log R(x))^2.

CPU-capable; used by tests and the synthetic gate script.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from nfl_dfs.research.gfn_env import SLOT_ORDER, LineupEnv, State

POSITIONS = ("QB", "RB", "WR", "TE", "DST")
_SLOT_TYPES = ("QB", "RB", "WR", "TE", "DST", "FLEX")
_MASK_FILL = -1e9


class GFNPolicy(nn.Module):
    """Forward policy P_F(action | state) over one slate, plus logZ."""

    def __init__(
        self,
        env: LineupEnv,
        hidden: int = 64,
        embed_dim: int = 8,
        quantile_cols: tuple[str, ...] = (),
    ):
        super().__init__()
        self.env = env
        self.quantile_cols = quantile_cols

        teams = sorted({p["team"] for p in env.players})
        games = sorted({p["game_id"] for p in env.players})
        self._team_idx = torch.tensor(
            [teams.index(p["team"]) for p in env.players], dtype=torch.long
        )
        self._game_idx = torch.tensor(
            [games.index(p["game_id"]) for p in env.players], dtype=torch.long
        )
        self.team_emb = nn.Embedding(len(teams), embed_dim)
        self.game_emb = nn.Embedding(len(games), embed_dim)

        feats = self._player_features(env)
        self.register_buffer("player_feats", feats)
        in_dim = feats.shape[1] + 2 * embed_dim
        self.player_mlp = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(), nn.Linear(hidden, hidden)
        )
        # scalar state features: salary frac, slots-remaining frac,
        # next-slot one-hot, games-count frac
        self._n_state_scalars = 3 + len(_SLOT_TYPES)
        self.state_mlp = nn.Sequential(
            nn.Linear(hidden + self._n_state_scalars, hidden), nn.ReLU()
        )
        self.head = nn.Sequential(
            nn.Linear(3 * hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1)
        )
        self.logZ = nn.Parameter(torch.zeros(()))

    # -- feature construction -------------------------------------------

    def _player_features(self, env: LineupEnv) -> torch.Tensor:
        proj = np.array([float(p.get("proj", 0.0)) for p in env.players])
        proj_scale = max(1.0, float(np.abs(proj).max()))
        cols = [proj / proj_scale,
                np.array([p["salary"] for p in env.players]) / env.salary_cap]
        for q in self.quantile_cols:
            vals = np.array([float(p[q]) for p in env.players])
            cols.append(vals / proj_scale)
        for pos in POSITIONS:
            cols.append(np.array([1.0 if p["pos"] == pos else 0.0 for p in env.players]))
        return torch.tensor(np.stack(cols, axis=1), dtype=torch.float32)

    def _encode_players(self) -> torch.Tensor:
        """[n_players, hidden] encodings; state-independent."""
        x = torch.cat(
            [self.player_feats, self.team_emb(self._team_idx), self.game_emb(self._game_idx)],
            dim=1,
        )
        return self.player_mlp(x)

    def _state_scalars(self, state: State) -> torch.Tensor:
        env = self.env
        slot = SLOT_ORDER[len(state)] if len(state) < len(SLOT_ORDER) else "QB"
        one_hot = [1.0 if slot == s else 0.0 for s in _SLOT_TYPES]
        games = len({env.players[i]["game_id"] for i in state})
        return torch.tensor(
            [
                env.salary(state) / env.salary_cap,
                (len(SLOT_ORDER) - len(state)) / len(SLOT_ORDER),
                games / max(1, env.min_games),
                *one_hot,
            ],
            dtype=torch.float32,
        )

    # -- logits and log-probabilities -----------------------------------

    def batch_logits(
        self, states: list[State], player_h: torch.Tensor | None = None
    ) -> torch.Tensor:
        """[B, n_players] masked action logits for a batch of states."""
        h = self._encode_players() if player_h is None else player_h
        ctx = h.mean(dim=0)
        chosen = torch.stack(
            [h[list(s)].mean(dim=0) if s else torch.zeros_like(ctx) for s in states]
        )
        scalars = torch.stack([self._state_scalars(s) for s in states])
        srep = self.state_mlp(torch.cat([chosen, scalars], dim=1))  # [B, hidden]
        b, n = len(states), h.shape[0]
        inp = torch.cat(
            [
                h.unsqueeze(0).expand(b, n, -1),
                ctx.view(1, 1, -1).expand(b, n, -1),
                srep.unsqueeze(1).expand(b, n, -1),
            ],
            dim=2,
        )
        logits = self.head(inp).squeeze(-1)  # [B, n]
        masks = torch.from_numpy(np.stack([self.env.mask(s) for s in states]))
        return logits.masked_fill(~masks, _MASK_FILL)

    def action_logits(self, state: State, player_h: torch.Tensor | None = None) -> torch.Tensor:
        """Masked action logits over all players for one state."""
        return self.batch_logits([state], player_h=player_h)[0]

    def trajectory_log_pf(self, trajectories: list[list[int]]) -> torch.Tensor:
        """[B] differentiable sum of log P_F over each action sequence.

        All trajectories are full lineups (fixed length), so the batch
        advances in lockstep one slot at a time.
        """
        h = self._encode_players()
        n_steps = len(SLOT_ORDER)
        if any(len(t) != n_steps for t in trajectories):
            raise ValueError("trajectories must be complete lineups")
        log_pf = torch.zeros(len(trajectories))
        for t in range(n_steps):
            states = [tuple(a[:t]) for a in trajectories]
            logp = torch.log_softmax(self.batch_logits(states, player_h=h), dim=1)
            acts = torch.tensor([a[t] for a in trajectories], dtype=torch.long)
            log_pf = log_pf + logp.gather(1, acts.unsqueeze(1)).squeeze(1)
        return log_pf

    # -- sampling --------------------------------------------------------

    @torch.no_grad()
    def sample(
        self,
        n: int,
        temperature: float = 1.0,
        explore_eps: float = 0.0,
        rng: np.random.Generator | None = None,
    ) -> list[State]:
        """Sample n terminal states (lineups), advanced in lockstep.
        ``explore_eps`` mixes in uniform-over-legal actions for
        off-policy exploration."""
        rng = rng or np.random.default_rng()
        h = self._encode_players()
        states: list[State] = [() for _ in range(n)]
        for _ in range(len(SLOT_ORDER)):
            probs = torch.softmax(
                self.batch_logits(states, player_h=h) / temperature, dim=1
            ).numpy()
            for k in range(n):
                legal = self.env.legal_actions(states[k])
                if explore_eps and rng.random() < explore_eps:
                    a = int(rng.choice(legal))
                else:
                    p = probs[k][legal]
                    a = int(rng.choice(legal, p=p / p.sum()))
                states[k] = states[k] + (a,)
        return states


def trajectory_balance_loss(
    policy: GFNPolicy, trajectories: list[list[int]], log_rewards: torch.Tensor
) -> torch.Tensor:
    """Trajectory-balance loss with deterministic backward policy."""
    log_pf = policy.trajectory_log_pf(trajectories)
    return ((policy.logZ + log_pf - log_rewards) ** 2).mean()
