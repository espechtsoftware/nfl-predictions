import numpy as np
import pytest

from nfl_dfs.optimizer.export import exposure_summary, to_dk_csv
from nfl_dfs.optimizer.lineup import Lineup, StackRules, optimize, optimize_many


def make_pool(seed=31, n_teams=6):
    """A feasible synthetic player pool across n_teams teams / 3 games."""
    rng = np.random.default_rng(seed)
    players = []
    pid = 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        game = f"G{t // 2}"
        roster = [("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1)]
        for pos, n in roster:
            for i in range(n):
                base = {"QB": 20, "RB": 14, "WR": 12, "TE": 8, "DST": 7}[pos]
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


def counts(lineup):
    c = {}
    for p in lineup.players:
        c[p["pos"]] = c.get(p["pos"], 0) + 1
    return c


def test_roster_and_cap_constraints():
    lu = optimize(make_pool())
    assert lu is not None
    assert len(lu.players) == 9
    assert lu.salary <= 50_000
    c = counts(lu)
    assert c["QB"] == 1 and c["DST"] == 1
    assert 2 <= c["RB"] <= 3
    assert 3 <= c["WR"] <= 4
    assert 1 <= c["TE"] <= 2
    games = {p["game_id"] for p in lu.players}
    assert len(games) >= 2


def test_locks_and_bans():
    pool = make_pool()
    worst_wr = min((p for p in pool if p["pos"] == "WR"), key=lambda p: p["proj"])
    best_qb = max((p for p in pool if p["pos"] == "QB"), key=lambda p: p["proj"])
    lu = optimize(pool, locks={worst_wr["id"]}, bans={best_qb["id"]})
    ids = lu.ids
    assert worst_wr["id"] in ids
    assert best_qb["id"] not in ids


def test_qb_stack_and_bring_back():
    pool = make_pool()
    lu = optimize(pool, stack=StackRules(qb_stack_min=2, bring_back_min=1))
    qb = next(p for p in lu.players if p["pos"] == "QB")
    catchers = [p for p in lu.players
                if p["pos"] in ("WR", "TE") and p["team"] == qb["team"]]
    assert len(catchers) >= 2
    bring_back = [p for p in lu.players
                  if p["team"] == qb["opp"] and p["pos"] in ("RB", "WR", "TE")]
    assert len(bring_back) >= 1


def test_no_rb_vs_opposing_dst_and_single_rb_per_team():
    lu = optimize(make_pool(), stack=StackRules())
    dst = next(p for p in lu.players if p["pos"] == "DST")
    rbs = [p for p in lu.players if p["pos"] == "RB"]
    assert all(rb["team"] != dst["opp"] for rb in rbs)
    teams = [rb["team"] for rb in rbs]
    assert len(teams) == len(set(teams))


def test_multi_lineup_uniqueness():
    lineups = optimize_many(make_pool(), n_lineups=5, max_overlap=7)
    assert len(lineups) == 5
    for i, a in enumerate(lineups):
        for b in lineups[i + 1:]:
            assert len(a.ids & b.ids) <= 7
    # Projections should be non-increasing as constraints accumulate
    projs = [lu.proj for lu in lineups]
    assert all(projs[i] >= projs[i + 1] - 1e-6 for i in range(len(projs) - 1))


def test_infeasible_returns_none():
    pool = [p for p in make_pool() if p["pos"] != "QB"]
    assert optimize(pool) is None


def test_dk_csv_and_exposure():
    lineups = optimize_many(make_pool(), n_lineups=3)
    csv_text = to_dk_csv(lineups)
    lines = csv_text.strip().splitlines()
    assert lines[0].split(",") == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(lines) == 4
    # Each data row has 9 slots, each like "Name (id)"
    assert all(len(line.split(",")) == 9 for line in lines[1:])

    exp = exposure_summary(lineups)
    assert exp[0]["exposure"] <= 1.0
    assert sum(e["lineups"] for e in exp) == 27


def test_slot_order_flex_identification():
    lu = optimize(make_pool())
    ordered = lu.slot_order()
    positions = [p["pos"] for p in ordered]
    assert positions[0] == "QB"
    assert positions[1:3] == ["RB", "RB"]
    assert positions[3:6] == ["WR", "WR", "WR"]
    assert positions[6] == "TE"
    assert positions[7] in ("RB", "WR", "TE")  # FLEX
    assert positions[8] == "DST"


def test_auto_core_budget_guard_sheds_expensive_studs():
    """A consensus lineup stuffed with studs must shed its priciest members
    until every free slot keeps a mid-tier budget."""
    from nfl_dfs.optimizer.lineup import CORE_FREE_SLOT_BUDGET, Lineup, _auto_core

    players = []
    for i in range(9):
        salary = 9000 if i < 5 else 4000
        players.append({"id": i, "name": f"p{i}", "pos": "WR", "team": f"T{i}",
                        "opp": "X", "game_id": "G", "salary": salary,
                        "proj": salary / 400})
    # Pool with plenty of cheap high-value alternatives so studs are only
    # median value at their position
    pool = players + [
        {"id": 100 + j, "name": f"v{j}", "pos": "WR", "team": "T9", "opp": "X",
         "game_id": "G", "salary": 3500, "proj": 12.0}
        for j in range(9)
    ]
    counts = {p["id"]: 15 for p in players}  # everyone unanimous
    core = _auto_core(Lineup(players), counts, 15, pool)
    core_salary = sum(p["salary"] for p in core)
    assert 50_000 - core_salary >= (9 - len(core)) * CORE_FREE_SLOT_BUDGET
    # The shed members are the expensive ones
    assert max(p["salary"] for p in core) <= 9000
    assert sum(1 for p in core if p["salary"] == 9000) < 5
