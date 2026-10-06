"""scripts/choose_entries.py and scripts/score_entry_choice.py end to end on a tiny synthetic run (offline: the field
sampler is replaced by a deterministic stand-in; the frozen rule itself is pinned in test_entry_choice.py)."""
import csv
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


CE, SC = _load("choose_entries"), _load("score_entry_choice")
POS = ["QB", "QB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "DST", "DST"]


def _run(tmp, pct=True):
    run = tmp / "run"; run.mkdir()
    fr = pd.DataFrame({"id": [f"p{i}" for i in range(12)], "dk_player_id": [100 + i for i in range(12)], "pos": POS,
                       "display_name": [f"Player {chr(65 + i)}" for i in range(12)], "team": ["A", "B"] * 6,
                       "salary": [6000] * 12})
    fr.to_parquet(run / "frame.parquet")
    rng = np.random.default_rng(7)
    for b in CE.BANKS:
        np.save(run / b, rng.gamma(2.0, 6.0, size=(12, 40)).astype(np.float32))
    rows = [[100 + q, 102, 103, 105, 106, 107, 109, 104, 110 + d] for q in (0, 1) for d in (0, 1)] + \
           [[100, 102, 104, 105, 106, 108, 109, 103, 110], [101, 103, 104, 106, 107, 108, 109, 102, 111]]
    book = tmp / "book.csv"
    with book.open("w", newline="") as h:
        w = csv.writer(h); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); w.writerows(rows)
    own = tmp / "own.csv"
    pd.DataFrame({"id": fr.id, "pred_own": np.linspace(2, 30, 12) / (1 if pct else 100)}).to_csv(own, index=False)
    plan = tmp / "contests.json"
    plan.write_text(json.dumps([{"name": f"c{j}", "contest_id": str(j), "entries": 1, "keep": 1} for j in range(4)]))
    return run, book, own, plan


@pytest.fixture(autouse=True)
def fake_sampler(monkeypatch):
    mod = types.ModuleType("field_sampler")

    def sample_field(fr, tgt, n, seed, ipf_rounds=6):
        rng = np.random.default_rng(seed)
        return rng.integers(0, len(fr), size=(n, 9)), {}
    mod.sample_field = sample_field
    monkeypatch.setitem(sys.modules, "field_sampler", mod)


def _args(run, book, own, *extra):
    return ["--run", str(run), "--book", str(book), "--ownership", str(own), "--N", "100", "--S", "20", *extra]


def test_the_pool_is_the_weeks_entered_mean_rows_and_all_rows_is_flagged(tmp_path, capsys):
    run, book, own, plan = _run(tmp_path)
    out = tmp_path / "c.json"
    assert CE.main(_args(run, book, own, "--contests", str(plan), "--m", "2", "--out", str(out))) == 0
    rec = json.loads(out.read_text()); txt = capsys.readouterr().out
    assert rec["K"] == 4 and all(1 <= r <= 4 for r in rec["R4_rows"]) and rec["R0_rows"] == [1, 2] and "K 4:" in txt
    assert len(rec["R4_names"]) == 2 and len(rec["R4_names"][0]) == 9
    assert CE.main(_args(run, book, own, "--all-rows", "--m", "4")) == 0
    txt = capsys.readouterr().out
    assert "K 6: ALL 6 book rows -- OUTSIDE the studied pool" in txt and "OUTSIDE the study (m <= 3)" in txt
    with pytest.raises(SystemExit, match="--contests"):
        CE.main(_args(run, book, own, "--m", "2"))


def test_fraction_scale_ownership_is_refused(tmp_path):
    run, book, own, plan = _run(tmp_path, pct=False)
    with pytest.raises(SystemExit, match="FRACTIONS"):
        CE.main(_args(run, book, own, "--contests", str(plan), "--m", "2"))


def _standings(path, points, players):
    with path.open("w", newline="", encoding="utf-8-sig") as h:
        w = csv.writer(h); w.writerow(["Rank", "EntryId", "EntryName", "TimeRemaining", "Points", "Lineup", "", "Player", "Roster Position", "%Drafted", "FPTS"])
        for i in range(max(len(points), len(players))):
            p = points[i] if i < len(points) else None
            pl = players[i] if i < len(players) else None
            w.writerow([i + 1 if p is not None else "", f"e{i}" if p is not None else "", "u", 0, "" if p is None else p, "", "",
                        pl[0] if pl else "", "", "", pl[1] if pl else ""])


def test_monday_scorer_ranks_with_ties_drops_the_entered_lineups_and_tallies(tmp_path, capsys):
    players = [("Alpha One", 50.0), ("Bravo Two", 100.0), ("Charlie Three", 40.0), ("Delta Four", 60.0)]
    st = tmp_path / "st.csv"; _standings(st, [200, 150, 150, 120, 100, 90], players)
    ch = tmp_path / "ch.json"
    ch.write_text(json.dumps({"contest_id": "9", "contest": "T", "m": 1, "K": 26, "S": 3,
                              "R4_names": [["Alpha One", "Bravo Two"]], "R0_names": [["Charlie Three", "Delta Four"]]}))
    tally = tmp_path / "tally.jsonl"
    assert SC.main(["--choice", str(ch), "--standings", str(st), "--entered", "R4", "--tally", str(tally), "--week", "6"]) == 0
    rec = json.loads(tally.read_text().splitlines()[0])
    # R4 scores 150: it was entered, so one 150 leaves the field -> 200, 150 at least as high -> rank 3 <= S 3: HIT
    assert rec["R4"]["best"] == 150.0 and rec["R4"]["best_rank"] == 3 and rec["R4"]["hit"]
    # R0 scores 100 on the reduced field (200, 150, 120, 100, 90): 4 at or above -> rank 5: miss
    assert rec["R0"]["best_rank"] == 5 and not rec["R0"]["hit"]
    assert "PAIRED TALLY: 1 contest(s); R4 hits 1, R0 hits 0; R4 - R0 = +1" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="already"):
        SC.main(["--choice", str(ch), "--standings", str(st), "--entered", "R4", "--tally", str(tally), "--week", "6"])
    ch.write_text(json.dumps({"contest_id": "9", "m": 1, "S": 3, "R4_names": [["Nobody Here"]], "R0_names": [["Alpha One"]]}))
    with pytest.raises(SystemExit, match="REFUSED"):
        SC.main(["--choice", str(ch), "--standings", str(st), "--entered", "none", "--tally", str(tally), "--week", "7"])


def test_entered_scores_match_dk_rounding_and_a_missing_one_refuses():
    # DK prints 150.04001; our lineup's per-player FPTS sum to 150.0399999: the same entry, removed
    f = np.array([200.0, 150.04001, 120.0, 100.0])
    r = SC.score_sets(f, [150.0399999], [100.0], S=2, entered="R4")
    assert r["R4"]["best_rank"] == 2 and r["R4"]["hit"]           # only 200 left at or above
    assert r["R0"]["best_rank"] == 4                              # 200, 120, 100 (ties lose) on the reduced field
    with pytest.raises(SystemExit, match="entered lineup score 140.0 not found"):
        SC.score_sets(f, [140.0], [100.0], S=2, entered="R4")
