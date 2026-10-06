"""The weekly FP vs FP + props check (scripts/weekly_fp_props_check.py), frozen 2026-10-06 before any Week-5 outcome.
Offline: synthetic frames."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("weekly_fp_props_check", ROOT / "scripts" / "weekly_fp_props_check.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def _nm(k: int) -> str:
    return f"Player {chr(97 + k // 26)}{chr(97 + k % 26)}"


def _frame(n=24, week=5, games=6):
    rows = [{"id": f"p{k}", "display_name": _nm(k), "pos": ["QB", "RB", "WR", "TE"][k % 4], "game_id": f"g{k % games}",
             "gsis_id": f"00-{k:04d}", "season": 2026, "week": week, "dk_draftable_id": float(1000 + k),
             "market_points": 5.0 + k, "dk_ppg": 1.0} for k in range(n)]
    return pd.DataFrame(rows)


def _fp(fr, scale=1.2):
    return pd.DataFrame({"slate_player_id": fr.dk_draftable_id.astype(int).astype(str), "fantasy_points": fr.market_points * scale})


def _actual(fr, scale=1.1):
    return pd.Series((fr.market_points * scale).to_numpy(), index=fr.display_name.map(C.norm))


def _active(fr, inactive=()):
    return pd.DataFrame({"season": 2026, "week": fr.week, "gsis_id": fr.gsis_id, "act": ~fr.id.isin(inactive)})


def test_the_paired_population_and_its_drops():
    fr = _frame()
    fr.loc[0, "market_points"] = np.nan                       # no props
    fr.loc[1, "market_points"] = 1.0                          # equals dk_ppg: the old fallback
    fp = _fp(fr); fp = fp[fp.slate_player_id != "1002"]        # no FP
    d, a = C.population(fr, fp, _actual(fr), _active(fr, inactive={"p3"}))
    assert a["dropped_no_props"] == 1 and a["dropped_props_fallback"] == 1 and a["dropped_no_fp"] == 1 and a["dropped_not_act"] == 1
    assert a["population"] == 20 and np.allclose(d.blend, 0.5 * d.fp + 0.5 * d.props)


def test_the_blend_is_offered_only_past_the_frozen_rule():
    fr = _frame(n=48, games=12)
    d, _ = C.population(fr, _fp(fr, 1.2), _actual(fr, 1.1), _active(fr))     # FP 20% high, props 10% low: the blend wins
    assert C.verdict(d, C.bootstrap(d)).startswith("THE BLEND IS OFFERED")
    d2, _ = C.population(fr, _fp(fr, 1.1), _actual(fr, 1.1), _active(fr))   # FP exact: the blend never wins
    assert C.verdict(d2, C.bootstrap(d2)).startswith("not offered")


def test_week_4_is_never_counted_and_the_rule_is_printed(tmp_path, capsys):
    for wk in (4, 5):
        fr = _frame(week=wk); d, _ = C.population(fr, _fp(fr), _actual(fr), _active(fr))
        d.to_csv(tmp_path / f"fp-props-2026-w{wk:02d}.csv", index=False)
    assert C.main(["pool", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "weeks [4] are before Week 5 (seen before the freeze): NOT counted" in out
    assert "POOLED (weeks >= 5): players 24" in out
    assert ("RULE: the 0.5 FP + 0.5 props blend is offered when its pooled MAE (weeks >= 5) is lower than FP's AND at least "
            "95% of B 2000 game-cluster resamples (seed 1, within week) are better") in out
    assert "CHECK:" in out


def test_frozen_constants():
    assert (C.B, C.SEED, C.SHARE, C.FIRST_WEEK) == (2000, 1, 0.95, 5)
