"""GFlowNet workstream tests (emerging-technologies-plan.md §5, §13.2).

Offline and synthetic: mask soundness by random rollout, canonical-hash
dedupe, and the toy-distribution test — on a slate small enough to
enumerate every legal lineup, trained sampling frequency must correlate
with reward. Training budgets are deliberately tiny (seconds).
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from scipy.stats import spearmanr

from nfl_dfs.research.gfn_env import (
    SLOT_ORDER,
    LineupEnv,
    canonical_hash,
    check_lineup,
)
from nfl_dfs.research.gfn_train import (
    ReplayBuffer,
    RewardConfig,
    lineup_utility,
    train_gfn,
    warm_start_buffer,
)


def make_pool(seed=0, n_teams=6):
    """Feasible synthetic pool: per team 1 QB / 3 RB / 4 WR / 2 TE / 1 DST."""
    rng = np.random.default_rng(seed)
    players, pid = [], 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        game = f"G{t // 2}"
        for pos, n in [("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1)]:
            base = {"QB": 20, "RB": 14, "WR": 12, "TE": 8, "DST": 7}[pos]
            for i in range(n):
                proj = max(1.0, base - 3 * i + rng.normal(0, 1.5))
                players.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": game,
                    "salary": int(np.clip(2800 + proj * 320 + rng.normal(0, 300),
                                          2500, 9500)),
                    "proj": proj,
                })
                pid += 1
    return players


def tiny_pool():
    """12 players / 4 teams / 2 games; small enough to enumerate."""
    spec = [
        ("QB", "A"), ("QB", "B"),
        ("RB", "A"), ("RB", "B"), ("RB", "C"),
        ("WR", "A"), ("WR", "B"), ("WR", "C"), ("WR", "D"),
        ("TE", "A"), ("TE", "B"),
        ("DST", "C"),
    ]
    game = {"A": "G0", "B": "G0", "C": "G1", "D": "G1"}
    opp = {"A": "B", "B": "A", "C": "D", "D": "C"}
    return [
        {"id": i, "name": f"{pos}_{team}{i}", "pos": pos, "team": team,
         "opp": opp[team], "game_id": game[team],
         "salary": 4000 + 100 * i, "proj": 10.0 + i}
        for i, (pos, team) in enumerate(spec)
    ]


def rollout(env, rng):
    state = env.reset()
    while not env.is_terminal(state):
        legal = env.legal_actions(state)
        assert legal, f"dead end at slot {len(state)} — lookahead failed"
        state = env.step(state, int(rng.choice(legal)))
    return state


# -- §13.1 property test: masks never allow an illegal completion --------


def test_random_rollouts_always_legal():
    for seed in range(3):
        pool = make_pool(seed=seed, n_teams=4 + seed)
        env = LineupEnv(pool)  # cap 50k, floor 49k
        rng = np.random.default_rng(seed)
        for _ in range(10):
            state = rollout(env, rng)
            players = env.lineup_players(state)
            assert check_lineup(
                players,
                salary_cap=env.salary_cap,
                salary_floor=env.salary_floor,
                max_from_team=env.max_from_team,
                min_games=env.min_games,
            ) == []


def test_mask_agrees_with_legal_actions_and_step_rejects_illegal():
    env = LineupEnv(make_pool(), salary_floor=0)
    state = env.reset()
    legal = env.legal_actions(state)
    mask = env.mask(state)
    assert sorted(np.flatnonzero(mask)) == sorted(legal)
    illegal = next(i for i in range(env.n_players) if i not in legal)
    with pytest.raises(ValueError):
        env.step(state, illegal)


def test_lookahead_masks_cap_trap():
    """A QB so expensive the remaining slots cannot fit under the cap
    must be masked at the root even though the slot itself allows QBs."""
    pool = tiny_pool()
    for p in pool:
        p["salary"] = 5500
    pool[0]["salary"] = 15_000  # QB_A: 15k + 8 * 5.5k = 59k > cap
    env = LineupEnv(pool, salary_floor=0)
    root_legal = env.legal_actions(env.reset())
    assert 0 not in root_legal
    assert 1 in root_legal  # the affordable QB stays legal


def test_lookahead_masks_floor_trap():
    """A QB so cheap the floor is unreachable must be masked."""
    pool = tiny_pool()
    for p in pool:
        p["salary"] = 6000
    pool[0]["salary"] = 1000  # QB_A: 1k + 8 * 6k = 49k < floor
    env = LineupEnv(pool, salary_floor=49_500, salary_cap=60_000)
    root_legal = env.legal_actions(env.reset())
    assert 0 not in root_legal
    assert 1 in root_legal


def test_min_games_enforced():
    """With only one game represented the pool must be infeasible."""
    pool = [p for p in tiny_pool() if p["game_id"] == "G0"]
    # add a DST in the same game so every slot has candidates
    pool.append({"id": 99, "name": "DST_A", "pos": "DST", "team": "A",
                 "opp": "B", "game_id": "G0", "salary": 4000, "proj": 6.0})
    with pytest.raises(ValueError, match="infeasible"):
        LineupEnv(pool, salary_floor=0)


# -- canonical hash and trajectory uniqueness ----------------------------


def test_canonical_hash_order_independent():
    ids = ["a", "b", "c", 1, 2, 3]
    assert canonical_hash(ids) == canonical_hash(list(reversed(ids)))
    assert canonical_hash(ids) != canonical_hash(ids[:-1] + [4])


def test_enumeration_yields_unique_player_sets():
    """Canonicalization: exactly one trajectory per legal player set."""
    env = LineupEnv(tiny_pool(), salary_floor=0)
    states = list(env.enumerate_lineups())
    hashes = [env.lineup_hash(s) for s in states]
    assert len(states) == len(set(hashes))
    # structural count per QB: (3RB,3WR,1TE)=C(3,3)C(4,3)C(2,1)=8,
    # (2,4,1)=C(3,2)C(4,4)C(2,1)=6, (2,3,2)=C(3,2)C(4,3)C(2,2)=12 -> 26; x2 QB
    assert len(states) == 52
    for s in states:
        assert check_lineup(env.lineup_players(s), salary_floor=0) == []


def test_actions_for_lineup_round_trip():
    env = LineupEnv(tiny_pool(), salary_floor=0)
    state = next(iter(env.enumerate_lineups()))
    ids = [p["id"] for p in env.lineup_players(state)]
    rng = np.random.default_rng(3)
    shuffled = list(ids)
    rng.shuffle(shuffled)
    actions = env.actions_for_lineup(shuffled)
    assert canonical_hash(shuffled) == canonical_hash(
        env.players[i]["id"] for i in actions
    )
    with pytest.raises(ValueError):
        env.actions_for_lineup(ids[:-1] + ["nope"])


# -- warm start and replay ----------------------------------------------


def test_warm_start_buffer_counts_and_skips():
    env = LineupEnv(tiny_pool(), salary_floor=0)
    state = next(iter(env.enumerate_lineups()))
    good = [p["id"] for p in env.lineup_players(state)]
    bad = good[:-1] + [good[0]]  # duplicate player
    buffer = ReplayBuffer()
    rng = np.random.default_rng(0)
    draws = rng.normal(10, 3, size=(env.n_players, 50))
    added, skipped = warm_start_buffer(
        env, buffer, [good, bad], draws, line=100.0,
        reward_cfg=RewardConfig(center=0.0),
    )
    assert (added, skipped) == (1, 1)
    assert len(buffer) == 1
    (actions, log_r) = buffer.sample(1, rng)[0]
    assert canonical_hash(env.players[i]["id"] for i in actions) == canonical_hash(good)
    assert np.isfinite(log_r)


# -- §13.2 toy-distribution test ----------------------------------------


def test_trained_sampling_tracks_reward():
    """On the enumerable slate, post-training sampling frequency must
    correlate with reward (plan §13.2: 'samples a known small reward
    distribution correctly')."""
    env = LineupEnv(tiny_pool(), salary_floor=0)
    rng = np.random.default_rng(7)
    # correlated-ish draws: shared game factor + idiosyncratic noise
    n_sims = 400
    game_f = {g: rng.normal(0, 2, size=n_sims) for g in ("G0", "G1")}
    draws = np.stack([
        p["proj"] + game_f[p["game_id"]] + rng.normal(0, 4, size=n_sims)
        for p in env.players
    ])
    # tail line: utilities span ~0.28-0.56 here, so reward discriminates
    # (a low line saturates P(total >= line) near 1 and kills the signal)
    line = 145.0

    result = train_gfn(
        env, draws, line, steps=200, batch_size=8, replay_batch=8,
        explore_eps=0.15, hidden=32, seed=5,
        reward_cfg=RewardConfig(temperature=0.05),
    )
    assert np.isfinite(result.history[-1]["loss"])

    # ground truth over every legal lineup
    states = list(env.enumerate_lineups())
    log_r = {
        env.lineup_hash(s): result.reward_cfg.log_reward(
            lineup_utility(s, draws, line)
        )
        for s in states
    }
    samples = result.policy.sample(1500, rng=np.random.default_rng(11))
    freq: dict[str, int] = {}
    for s in samples:
        freq[env.lineup_hash(s)] = freq.get(env.lineup_hash(s), 0) + 1

    keys = list(log_r)
    rho, _ = spearmanr(
        [log_r[k] for k in keys], [freq.get(k, 0) for k in keys]
    )
    assert rho > 0.6, f"sampling frequency does not track reward (rho={rho:.3f})"

    # every sample is a legal lineup
    for s in samples[:50]:
        assert check_lineup(env.lineup_players(s), salary_floor=0) == []
