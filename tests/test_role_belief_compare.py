import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "compare_role_belief_panel",
    Path(__file__).parents[1] / "scripts" / "compare_role_belief_panel.py")
assert _SPEC and _SPEC.loader
compare = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(compare)


def _frames():
    weeks = [(2019, w) for w in range(1, 18)]
    for season in (2021, 2022, 2023, 2024, 2025):
        weeks.extend((season, w) for w in range(1, 19))
    control_clear = ({(s, w) for s, w in weeks if w <= 2}
                     | {(s, 3) for s in (2019, 2021, 2022, 2023, 2024)})
    treatment_clear = control_clear | {(2019, 4), (2021, 4)}
    control_rows, treatment_rows = [], []
    for season, week in weeks:
        for cand_ix in range(13):
            control_rows.append({
                "season": season, "week": week, "cand_ix": cand_ix,
                "tag": "lev", "all_tags": json.dumps(["lev"]),
                "players": f"c-{season}-{week}-{cand_ix}",
                "selected": cand_ix == 0,
                "actual_score": (195.0 if (season, week) in control_clear
                                 and cand_ix == 0 else 170.0 - cand_ix),
                "code_sha": "abc", "config_hash": "cfg",
                "lever_env": "control", "seeds": "seed",
            })
            is_epi = cand_ix < 12
            score = (196.0 if (season, week) in treatment_clear
                     and cand_ix == 0 else 170.0 - cand_ix)
            treatment_rows.append({
                "season": season, "week": week, "cand_ix": cand_ix,
                "tag": "epi" if is_epi else "lev",
                "all_tags": json.dumps(["epi"] if is_epi else ["lev"]),
                "players": f"t-{season}-{week}-{cand_ix}",
                "selected": cand_ix == 0, "actual_score": score,
                "code_sha": "abc", "config_hash": "cfg",
                "lever_env": "treatment", "seeds": "seed",
            })
    return pd.DataFrame(control_rows), pd.DataFrame(treatment_rows)


def test_frozen_role_belief_comparison_accepts_only_complete_lift(
        monkeypatch, capsys):
    control, treatment = _frames()
    source = control.copy()
    monkeypatch.setattr(
        compare, "_load",
        lambda panel: control if panel == "control" else treatment)
    monkeypatch.setattr(compare, "_load_source", lambda panel: source)
    monkeypatch.setattr(
        sys, "argv", ["compare", "control", "treatment",
                      "--source", "source"])
    assert compare.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "ADOPT"
    assert report["control_metrics"]["clear_194"] == 17
    assert report["treatment_metrics"]["clear_194"] == 19
    assert all(report["gate"].values())


def test_frozen_role_belief_comparison_rejects_unequal_pool(
        monkeypatch, capsys):
    control, treatment = _frames()
    source = control.copy()
    treatment = treatment.drop(treatment.index[-1])
    monkeypatch.setattr(
        compare, "_load",
        lambda panel: control if panel == "control" else treatment)
    monkeypatch.setattr(compare, "_load_source", lambda panel: source)
    monkeypatch.setattr(
        sys, "argv", ["compare", "control", "treatment",
                      "--source", "source"])
    assert compare.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "REJECT"
    assert not report["gate"]["exact_pool_pairing"]


def test_frozen_role_belief_comparison_rejects_degraded_control(
        monkeypatch, capsys):
    control, treatment = _frames()
    source = control.copy()
    source.loc[source.index[0], "players"] = "source-only-roster"
    monkeypatch.setattr(
        compare, "_load",
        lambda panel: control if panel == "control" else treatment)
    monkeypatch.setattr(compare, "_load_source", lambda panel: source)
    monkeypatch.setattr(
        sys, "argv", ["compare", "control", "treatment",
                      "--source", "source"])
    assert compare.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "REJECT"
    assert not report["gate"]["control_reproduces_source"]
