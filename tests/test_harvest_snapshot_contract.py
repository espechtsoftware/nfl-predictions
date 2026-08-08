import importlib.util
from pathlib import Path

import pandas as pd


_SPEC = importlib.util.spec_from_file_location(
    "harvest_accept",
    Path(__file__).parents[1] / "scripts" / "harvest_accept.py")
assert _SPEC and _SPEC.loader
accept = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(accept)


def _valid_frames():
    ids = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "TE2",
           "DST_A"]
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "DST"]
    salaries = [6000, 7000, 6500, 6000, 5500, 5000, 4000, 3500, 3000]
    actuals = [20, 20, 20, 20, 20, 20, 10, 10, 8]
    features = pd.DataFrame({
        "season": 2025, "week": 1, "slate_run_id": "run",
        "id": ids, "pos": pos,
        "team": ["A"] * 8 + ["A"], "opp": ["B"] * 9,
        "salary": salaries, "actual": actuals,
    })
    candidate = pd.DataFrame([{
        "season": 2025, "week": 1, "slate_run_id": "run", "cand_ix": 0,
        "players": ",".join(ids), "salary": sum(salaries),
        "actual_score": sum(actuals),
    }])
    pairs = pd.DataFrame([
        {"season": 2025, "week": 1, "team": "A", "opp": "B"},
    ])
    return candidate, features, pairs


def test_snapshot_contract_reconstructs_legal_candidate():
    candidate, features, pairs = _valid_frames()
    assert accept._snapshot_contract_failures(candidate, features, pairs) == []


def test_snapshot_contract_rejects_salary_score_and_off_main_drift():
    candidate, features, pairs = _valid_frames()
    candidate.loc[0, "salary"] += 100
    candidate.loc[0, "actual_score"] += 1
    features.loc[features.id.eq("WR1"), ["team", "opp"]] = ["X", "Y"]
    failures = accept._snapshot_contract_failures(candidate, features, pairs)
    assert any("off-main" in f for f in failures)
    assert any("salary reconstruction" in f for f in failures)
    assert any("actual reconstruction" in f for f in failures)


def test_snapshot_contract_rejects_missing_matchup():
    candidate, features, pairs = _valid_frames()
    features.loc[features.id.eq("WR1"), "opp"] = None
    failures = accept._snapshot_contract_failures(candidate, features, pairs)
    assert any("without team/opponent" in f for f in failures)


def test_authoritative_actual_contract_accepts_and_rejects_drift():
    _, features, _ = _valid_frames()
    actuals = features[["season", "week", "id", "actual"]].rename(
        columns={"actual": "authoritative_actual"})
    assert accept._authoritative_actual_failures(features, actuals) == []
    changed = features.copy()
    changed.loc[changed.id.eq("WR1"), "actual"] += 1
    failures = accept._authoritative_actual_failures(changed, actuals)
    assert any("authoritative actual mismatches" in f for f in failures)
