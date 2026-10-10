"""Study 97's game-script sets in production (union_reselect.game_script_sets) against the lab's OWN text: nfl2
experiments/s97_game_script.py @ af07583e (module 7df6f324) scenarios() pasted BELOW byte for byte (its text sha-pinned), on
synthetic slates (missing lines, odd game counts, ties at the cut, unequal team medians): the same high-total cut, the same FAV /
FAVHI / HIGH / DOGHI sets and the same opponents. Offline; no private data."""
import ast
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402

FAV_MARGIN, HIGH_Q = 3.0, 2.0 / 3.0                 # s97's constants (the pasted text reads them)
LAB_TEXT_SHA256 = {"scenarios": "938032a86a537862bac333da2e50344693a17babe70c92b1823fd5c1499e74c5"}


# ---- nfl2 experiments/s97_game_script.py @ af07583e, BYTE FOR BYTE ----
def scenarios(fr_pool: pd.DataFrame) -> dict:
    """Per team, from pre-lock lines only: margin = 2 x implied_team_total - game_total (the team's median over the pool's rows);
    a high-total game = game_total >= the slate's upper-third cut (numpy quantile 2/3 over the games' median totals). Returns
    {"high_cut": float, "teams": {"FAV": set, "FAVHI": set, "HIGH": set, "DOGHI": set}}; a team without both lines is in none."""
    g = pd.DataFrame({"team": fr_pool.team.astype(str), "game": fr_pool.game_id.astype(str),
                      "itt": pd.to_numeric(fr_pool.implied_team_total, errors="coerce"),
                      "gt": pd.to_numeric(fr_pool.game_total, errors="coerce")})
    t = g.groupby("team").agg(itt=("itt", "median"), gt=("gt", "median")).dropna()
    games = g.groupby("game")["gt"].median().dropna()
    cut = float(np.quantile(games.to_numpy(float), HIGH_Q)) if len(games) else float("inf")
    margin = 2.0 * t["itt"] - t["gt"]
    high = t["gt"] >= cut
    teams = {"FAV": set(t.index[margin >= FAV_MARGIN]), "FAVHI": set(t.index[(margin >= FAV_MARGIN) & high]),
             "HIGH": set(t.index[high]), "DOGHI": set(t.index[(margin < 0) & high])}
    tg = g.drop_duplicates("team").set_index("team")["game"]
    opp_of = {a: {b for b in tg.index if b != a and tg[b] == tg[a]} for a in tg.index}
    return {"high_cut": round(cut, 3), "teams": teams, "opp_of": opp_of}


def slate(seed: int, n_games: int, missing: int = 0, tie: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for gi in range(n_games):
        tot = 50.0 if tie and gi < 3 else float(np.round(rng.uniform(37, 54) * 2) / 2)
        spread = float(np.round(rng.uniform(-14, 14) * 2) / 2)
        a, b = f"T{2 * gi}", f"T{2 * gi + 1}"
        for t, itt in ((a, (tot - spread) / 2), (b, (tot + spread) / 2)):
            for p in ("QB", "RB", "WR", "WR", "TE"):
                rows.append({"id": f"{t}{p}{len(rows)}", "pos": p, "team": t, "game_id": f"g{gi}", "implied_team_total": itt,
                             "game_total": tot})
    fr = pd.DataFrame(rows)
    if missing:
        fr.loc[fr.team.isin([f"T{i}" for i in range(missing)]), "implied_team_total"] = None
    return fr


def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_game_script_sets.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256) and ur.GS_FAV_MARGIN == FAV_MARGIN and ur.GS_HIGH_Q == HIGH_Q


@pytest.mark.parametrize("seed,n_games,missing,tie", [(1, 13, 0, False), (2, 14, 0, False), (3, 5, 0, False), (4, 9, 2, False),
                                                      (5, 12, 0, True), (6, 2, 0, False), (7, 16, 3, True)])
def test_production_equals_the_lab(seed, n_games, missing, tie):
    fr = slate(seed, n_games, missing, tie)
    lab = scenarios(fr)
    prod = ur.game_script_sets(fr, set(fr.id.astype(str)))
    assert prod["high_cut"] == lab["high_cut"] and prod["teams"] == lab["teams"] and prod["opp_of"] == lab["opp_of"]
    assert lab["teams"]["FAV"] and lab["teams"]["HIGH"]                   # non-vacuous: the sets are populated


def test_a_pool_subset_and_a_missing_column():
    fr = slate(8, 13)
    keep = set(fr.id[fr.pos != "TE"].astype(str))                       # the pool drops some rows: the team lines are unchanged
    assert ur.game_script_sets(fr, keep) == scenarios(fr[fr.id.isin(keep)])
    with pytest.raises(SystemExit, match="GAME SCRIPT REFUSED"):
        ur.game_script_sets(fr.drop(columns=["game_total"]), set(fr.id))
