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


def test_dk_csv_prefers_draftable_ids():
    """Upload cells must carry the slate's draftable ID when the pool has
    one; the stable player id is only a last-resort fallback."""
    pool = make_pool()
    for p in pool:
        p["dk_id"] = p["id"] + 40_000_000
    lu = optimize(pool)
    csv_text = to_dk_csv([lu])
    row = csv_text.strip().splitlines()[1]
    for p in lu.players:
        assert f"({p['dk_id']})" in row
        assert f"({p['id']})" not in row


def test_fill_entries_csv_round_trip():
    from nfl_dfs.optimizer.export import entry_count, fill_entries_csv

    lineups = optimize_many(make_pool(), n_lineups=2)
    entries = (
        "\ufeffEntry ID,Contest Name,Contest ID,Entry Fee,"
        "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
        "4111111,NFL $100K Flea Flicker,987,$5,,,,,,,,,,,Fill in your entries\n"
        "4111112,NFL $100K Flea Flicker,987,$5\n"
        "4111113,\"NFL $2 Double, Up\",988,$2\n"
        ",,,,,,,,,,,,,,Name,ID\n"
        ",,,,,,,,,,,,,,Some Player,40000001\n"
    )
    assert entry_count(entries) == 3

    filled = fill_entries_csv(entries, lineups)
    import csv as csv_mod
    import io as io_mod

    rows = list(csv_mod.reader(io_mod.StringIO(filled)))
    # Metadata, instructions, and the player-list block are untouched
    assert rows[1][:4] == ["4111111", "NFL $100K Flea Flicker", "987", "$5"]
    assert rows[1][14] == "Fill in your entries"
    assert rows[3][:3] == ["4111113", "NFL $2 Double, Up", "988"]
    assert rows[5][14:16] == ["Some Player", "40000001"]
    # Each entry got 9 slot cells; entries cycle when lineups run out
    for r in (rows[1], rows[2], rows[3]):
        assert all(cell.endswith(")") for cell in r[4:13])
    assert rows[3][4:13] == rows[1][4:13]
    assert rows[2][4:13] != rows[1][4:13]


def test_fill_entries_csv_rejects_bad_input():
    import pytest as pt

    from nfl_dfs.optimizer.export import fill_entries_csv

    lineups = optimize_many(make_pool(), n_lineups=1)
    with pt.raises(ValueError, match="Not a DKEntries"):
        fill_entries_csv("QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n", lineups)
    showdown_file = (
        "Entry ID,Contest Name,Contest ID,Entry Fee,CPT,FLEX,FLEX,FLEX,FLEX,FLEX\n"
        "4111111,Showdown,55,$1\n"
    )
    with pt.raises(ValueError, match="mismatch"):
        fill_entries_csv(showdown_file, lineups)  # 9-man classic lineups
    with pt.raises(ValueError, match="No lineups"):
        fill_entries_csv(showdown_file, [])


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


def _kickoff_pool():
    def p(id, pos, proj, kickoff=None):
        return {"id": id, "pos": pos, "proj": proj, "salary": 5000,
                "kickoff": kickoff}

    # 3 RBs (surplus position), 3 WRs, 1 TE => RB's leftover goes to FLEX.
    # rb3 has the highest proj (would win the old proj-based leftover
    # pick if it were the *lowest*) but also the latest kickoff, while
    # rb2 has the lowest proj but an early kickoff.
    return [
        p("qb", "QB", 20, "2026-09-10T13:00:00Z"),
        p("rb1", "RB", 15, "2026-09-10T13:00:00Z"),
        p("rb2", "RB", 14, "2026-09-10T13:05:00Z"),
        p("rb3", "RB", 25, "2026-09-10T20:20:00Z"),
        p("wr1", "WR", 12, "2026-09-10T13:00:00Z"),
        p("wr2", "WR", 11, "2026-09-10T13:00:00Z"),
        p("wr3", "WR", 10, "2026-09-10T13:00:00Z"),
        p("te1", "TE", 8, "2026-09-10T13:00:00Z"),
        p("dst", "DST", 7, "2026-09-10T13:00:00Z"),
    ]


def test_slot_order_prefers_latest_kickoff_for_flex():
    """With every player's kickoff known, FLEX goes to the latest-kickoff
    player in the surplus position (roadmap #13.2: max late-swap
    flexibility, since FLEX is the only slot DK lets you fill with any of
    RB/WR/TE) even though it isn't the lowest-projected one."""
    ordered = Lineup(_kickoff_pool()).slot_order()
    assert [p["id"] for p in ordered[1:3]] == ["rb1", "rb2"]
    assert ordered[7]["id"] == "rb3"
    assert ordered[7]["pos"] == "RB"


def test_slot_order_ignores_kickoff_when_incomplete():
    """Missing kickoff for even one player must fall back to the original
    proj-based FLEX pick — half-known kickoff data is worse than none."""
    players = _kickoff_pool()
    next(p for p in players if p["id"] == "dst")["kickoff"] = None
    ordered = Lineup(players).slot_order()
    assert ordered[7]["id"] == "rb2"  # lowest-proj RB, the old behavior


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


# --- Showdown Captain Mode ---------------------------------------------------

from nfl_dfs.optimizer.export import showdown_exposure_summary, to_dk_showdown_csv
from nfl_dfs.optimizer.showdown import (
    CPT_MULT,
    cpt_salary,
    optimize_many_showdown,
    optimize_showdown,
)


def make_showdown_pool(seed=17):
    """One game, two teams, full showdown pool including K and DST."""
    rng = np.random.default_rng(seed)
    players = []
    pid = 0
    for team, opp in (("HOME", "AWAY"), ("AWAY", "HOME")):
        roster = [("QB", 1), ("RB", 2), ("WR", 4), ("TE", 2), ("K", 1), ("DST", 1)]
        for pos, n in roster:
            for i in range(n):
                base = {"QB": 20, "RB": 14, "WR": 12, "TE": 8, "K": 7, "DST": 6}[pos]
                proj = max(1.0, base - 3 * i + rng.normal(0, 1.5))
                players.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": 555,
                    "salary": int(np.clip(200 * round((1500 + proj * 450) / 200),
                                          1000, 11_600)),
                    "proj": proj,
                })
                pid += 1
    return players


def test_showdown_roster_cap_and_both_teams():
    lu = optimize_showdown(make_showdown_pool())
    assert lu is not None
    assert len(lu.players) == 6
    assert lu.captain["id"] not in {p["id"] for p in lu.flex}
    # Cap includes the 1.5x captain premium
    assert lu.salary <= 50_000
    assert lu.salary == cpt_salary(lu.captain["salary"]) + sum(
        p["salary"] for p in lu.flex
    )
    assert {p["team"] for p in lu.players} == {"HOME", "AWAY"}
    assert lu.proj == pytest.approx(
        CPT_MULT * lu.captain["proj"] + sum(p["proj"] for p in lu.flex)
    )


def test_showdown_captain_choice_is_value_aware():
    """The optimizer must weigh the 1.5x salary premium, not just points:
    an overpriced top scorer should be rostered as FLEX, with a cheaper
    player taking the captaincy."""
    pool = []
    for i in range(6):
        pool.append({"id": i, "name": f"H{i}", "pos": "WR", "team": "H",
                     "opp": "A", "game_id": 1, "salary": 7000, "proj": 20.0})
    for i in range(6, 12):
        pool.append({"id": i, "name": f"A{i}", "pos": "WR", "team": "A",
                     "opp": "H", "game_id": 1, "salary": 7000, "proj": 10.0})
    # Stud: best points, but captaining him busts the cap (16500 + 5*7000)
    pool.append({"id": 99, "name": "Stud", "pos": "QB", "team": "H",
                 "opp": "A", "game_id": 1, "salary": 11_000, "proj": 25.0})
    lu = optimize_showdown(pool)
    assert 99 in lu.ids  # worth rostering...
    assert lu.captain["id"] != 99  # ...but not at 1.5x salary
    assert lu.salary <= 50_000


def test_showdown_locks_bans_and_captain_lock():
    pool = make_showdown_pool()
    worst = min(pool, key=lambda p: p["proj"])
    best = max(pool, key=lambda p: p["proj"])
    lu = optimize_showdown(pool, locks={worst["id"]}, bans={best["id"]})
    assert worst["id"] in lu.ids and best["id"] not in lu.ids

    forced = next(p for p in pool if p["pos"] == "K")
    lu = optimize_showdown(pool, captain_lock=forced["id"])
    assert lu.captain["id"] == forced["id"]


def test_showdown_uniqueness_counts_the_captain():
    lineups = optimize_many_showdown(make_showdown_pool(), n_lineups=8)
    assert len(lineups) == 8
    keys = {lu.key for lu in lineups}
    assert len(keys) == 8  # no repeated (captain, roster) pair
    projs = [lu.proj for lu in lineups]
    assert all(projs[i] >= projs[i + 1] - 1e-6 for i in range(len(projs) - 1))

    # Tighter overlap forces the player sets themselves to differ
    diverse = optimize_many_showdown(make_showdown_pool(), n_lineups=4,
                                     max_overlap=4)
    for i, a in enumerate(diverse):
        for b in diverse[i + 1:]:
            assert len(a.ids & b.ids) <= 5


def test_showdown_infeasible_returns_none():
    one_team = [p for p in make_showdown_pool() if p["team"] == "HOME"]
    assert optimize_showdown(one_team) is None  # must roster both teams


def test_showdown_csv_and_exposure():
    lineups = optimize_many_showdown(make_showdown_pool(), n_lineups=3)
    csv_text = to_dk_showdown_csv(lineups)
    lines = csv_text.strip().splitlines()
    assert lines[0].split(",") == ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]
    assert len(lines) == 4
    # First slot of each row is that lineup's captain
    for lu, line in zip(lineups, lines[1:]):
        assert line.split(",")[0] == f"{lu.captain['name']} ({lu.captain['id']})"

    exp = showdown_exposure_summary(lineups)
    assert sum(e["lineups"] for e in exp) == 18
    assert sum(e["cpt_lineups"] for e in exp) == 3
    for e in exp:
        assert e["cpt_lineups"] <= e["lineups"]


def test_showdown_csv_uses_cpt_draftable_id():
    """The CPT cell must carry the CPT-slot draftable ID; FLEX cells the
    FLEX one — DK rejects a FLEX ID in the captain slot."""
    pool = make_showdown_pool()
    for p in pool:
        p["dk_id"] = p["id"] + 40_000_000
        p["cpt_dk_id"] = p["id"] + 50_000_000
    lu = optimize_showdown(pool)
    row = to_dk_showdown_csv([lu]).strip().splitlines()[1].split(",")
    assert row[0] == f"{lu.captain['name']} ({lu.captain['cpt_dk_id']})"
    for cell, p in zip(row[1:], lu.slot_order()[1:]):
        assert cell == f"{p['name']} ({p['dk_id']})"


def test_tournament_punt_slot_default():
    """Every default-built lineup must roster >=1 sub-$4k punt (94% of 2025
    Milly winners had one; punt_min defaults on in optimize_many)."""
    from nfl_dfs.optimizer.lineup import PUNT_MAX_SALARY, optimize_many

    slate = None
    from test_backtest import make_slate  # synthetic slate fixture

    pool = make_slate().to_dict("records")
    lineups = optimize_many(pool, n_lineups=5)
    assert lineups
    for lu in lineups:
        assert any(p["salary"] <= PUNT_MAX_SALARY for p in lu.players)


def test_showdown_punt_slot_default():
    from nfl_dfs.optimizer.showdown import optimize_many_showdown
    from nfl_dfs.optimizer.lineup import PUNT_MAX_SALARY
    import numpy as np

    rng = np.random.default_rng(6)
    pool = [{"id": i, "name": f"p{i}", "pos": "WR", "team": "A" if i % 2 else "B",
             "opp": None, "game_id": "G", "salary": int(rng.integers(2, 11)) * 500,
             "proj": float(rng.uniform(5, 25))} for i in range(20)]
    lineups = optimize_many_showdown(pool, n_lineups=3)
    assert lineups
    for lu in lineups:
        assert any(p["salary"] <= PUNT_MAX_SALARY for p in lu.players)


def test_game_lock_forces_concentration():
    pool = make_pool()
    gid = sorted({p["game_id"] for p in pool})[0]
    lu = optimize(pool, game_lock=(gid, 5))
    assert lu is not None
    assert sum(1 for p in lu.players if p["game_id"] == gid) >= 5
    # And without the lock the optimum is less concentrated or equal-proj
    free = optimize(pool)
    assert free.proj >= lu.proj


# select_tail_entries -------------------------------------------------------
# (restored after crash corruption zeroed these out of commit db8160c)

from nfl_dfs.optimizer.lineup import select_tail_entries


def test_tail_selection_prefers_complementary_booms():
    # A and B clear the line in the SAME sims; C clears a different sim.
    # Coverage selection must take one of {A,B} plus C — never A and B —
    # even though B beats C on every marginal stat.
    line = 100.0
    a = [120, 115, 0, 0, 0, 0]
    b = [125, 118, 0, 0, 0, 50]
    c = [0, 0, 110, 0, 0, 0]
    picked = select_tail_entries(np.array([a, b, c], dtype=float), 2, line)
    assert set(picked) == {1, 2}  # B (higher P and mean of the pair) + C


def test_tail_selection_fills_after_saturation():
    line = 100.0
    a = [120, 0, 0]   # covers sim 0
    b = [0, 0, 90]    # never clears
    c = [0, 0, 95]    # never clears, higher mean
    picked = select_tail_entries(np.array([a, b, c], dtype=float), 3, line)
    assert picked[0] == 0                 # only real coverage first
    assert picked[1] == 2                 # then best remaining mean
    assert len(picked) == 3


def test_tail_selection_caps_at_candidates():
    totals = np.array([[120.0, 0.0]])
    assert select_tail_entries(totals, 5, 100.0) == [0]
