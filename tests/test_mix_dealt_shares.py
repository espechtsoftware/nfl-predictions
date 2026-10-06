"""scripts/mix_dealt_shares.py: the operator sees the shape mix as DEALT (after the overlap limit), mapped through the
union's candidate tags (reviewer 2026-10-05, --main mix item c)."""
import csv
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mix_dealt_shares", ROOT / "scripts" / "mix_dealt_shares.py")
MD = importlib.util.module_from_spec(spec); spec.loader.exec_module(MD)


def _setup(tmp, main="mix"):
    run = tmp / "run"; run.mkdir(parents=True)
    players = []
    for t, o, g in (("A", "B", "g1"), ("B", "A", "g1"), ("C", "D", "g2"), ("D", "C", "g2")):
        for k, pos in enumerate(["QB", "RB", "WR", "WR", "TE", "DST"]):
            players.append({"id": f"{t}{pos}{k}", "dk_player_id": len(players) + 100, "pos": pos, "team": t, "opp": o, "game_id": g})
    fr = pd.DataFrame(players); fr.to_parquet(run / "frame.parquet")
    dk = dict(zip(fr["id"], fr["dk_player_id"].astype(str)))
    row_a1 = ["AQB0", "AWR2", "AWR3", "BRB1", "CRB1", "CWR2", "DWR2", "DTE4", "CDST5"]      # QB + 2, bring-back
    row_c = ["AQB0", "AWR2", "CRB1", "CWR2", "CWR3", "DWR2", "DTE4", "DRB1", "BDST5"]       # QB + 1, no bring-back
    row_h = ["CQB0", "CWR2", "CWR3", "DRB1", "ARB1", "AWR2", "BWR2", "BTE4", "ADST5"]       # untagged (a sleeve row)
    pd.DataFrame({"players": [",".join(r) for r in (row_a1, row_c, row_h)], "tag": ["mix_A1", "mix_C", "lev"]}).to_parquet(run / "candidates.parquet")
    (run / "receipt.json").write_text(json.dumps({"config": {"union": {"main": main}}}))
    up = tmp / "upload.csv"
    with up.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        for r in (row_a1, row_c, row_h):
            w.writerow([dk[i] for i in r])
    stage = tmp / "stage"; stage.mkdir()
    (stage / "ENTER-rowmap.json").write_text(json.dumps({"big": [0, 1, 1], "sat": [0], "milly": [2]}))
    return run, up, stage


def test_dealt_entries_are_counted_by_cell_with_the_shape(tmp_path, capsys):
    run, up, stage = _setup(tmp_path)
    assert MD.main(["--stage", str(stage), "--upload", str(up), "--run", str(run)]) == 0
    out = json.loads((stage / "ENTER-mix-dealt.json").read_text())
    assert out["entries"] == 5 and out["cells"] == {"A1": 2, "A2": 0, "B": 0, "C": 2, "house": 1}
    assert out["shape"]["qb_plus2"] == 0.6 and out["shape"]["bringback"] == 0.6     # the sleeve row is QB+2 with a bring-back too
    assert "MIX DEALT (the entries as staged, after the small-contest overlap limit): A1 2 (0.4; quota 0.3)" in capsys.readouterr().out


def test_a_run_without_a_mix_main_reports_nothing(tmp_path, capsys):
    run, up, stage = _setup(tmp_path, main="pmo_x50")
    assert MD.main(["--stage", str(stage), "--upload", str(up), "--run", str(run)]) == 0
    assert capsys.readouterr().out.strip() == "MIX DEALT: not a mix main (nothing to report)"
    assert not (stage / "ENTER-mix-dealt.json").exists()
