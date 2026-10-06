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


def _setup(tmp, main="mix", k_main=2):
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
    (run / "receipt.json").write_text(json.dumps({"config": {"union": {"main": main}, "operational_k": k_main}}))   # row 2: the sleeve
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
    # dual: row A1 holds C and D players (g2) -> dual; row C: CRB1/CWR2/CWR3 and DWR2/DTE4/DRB1 -> dual; the sleeve row's
    # QB is C (g2) and g1 holds A and B -> dual
    assert out["shape"]["dual"] == 1.0
    assert "MIX DEALT (the entries as staged, after the small-contest overlap limit): A1 2 (0.4; quota 0.3)" in capsys.readouterr().out


def test_a_run_without_a_mix_main_reports_nothing(tmp_path, capsys):
    run, up, stage = _setup(tmp_path, main="pmo_x50")
    assert MD.main(["--stage", str(stage), "--upload", str(up), "--run", str(run)]) == 0
    assert capsys.readouterr().out.strip() == "MIX DEALT: not a mix main (nothing to report)"
    assert not (stage / "ENTER-mix-dealt.json").exists()


def test_an_untagged_main_row_is_counted_by_its_shape(tmp_path, capsys):
    # k 3: the untagged row 2 sits in the main block -- a Sunday replacement from the Saturday / T-70 corpus. Its shape
    # (QB C + CWR2 + CWR3, bring-back DRB1) fits A1 only, so it counts as A1, not house (laptop 10-06 rehearsal).
    run, up, stage = _setup(tmp_path, k_main=3)
    assert MD.main(["--stage", str(stage), "--upload", str(up), "--run", str(run)]) == 0
    out = json.loads((stage / "ENTER-mix-dealt.json").read_text())
    assert out["cells"] == {"A1": 3, "A2": 0, "B": 0, "C": 2, "house": 0} and out["untagged_main_entries_by_shape"] == {"A1": 1}
    assert "untagged main-block entries by shape {\"A1\": 1}" in capsys.readouterr().out


def test_a_row_fitting_several_cells_is_printed_as_ambiguous(tmp_path, monkeypatch):
    # the MIX cells are disjoint today; a portfolio whose cells overlap must never have a row silently assigned to one
    from nfl_dfs.inference import mix_shapes
    run, up, stage = _setup(tmp_path, k_main=3)
    overlap = {"X": (0.5, {"qb_stack_min": 1, "bring_back_min": 0}, None, None), "Y": (0.5, {"qb_stack_min": 2, "bring_back_min": 1}, None, None)}
    for name, cell in overlap.items():
        monkeypatch.setitem(mix_shapes.ALL_CELLS, name, cell)
    rowmap = json.loads((stage / "ENTER-rowmap.json").read_text())
    rows = [r for r in list(csv.reader(open(up, newline="")))[1:]]
    fr = pd.read_parquet(run / "frame.parquet"); d = fr.assign(dk=fr["dk_player_id"].astype(str))
    pos, team, opp, game = (dict(zip(d.dk, d[c].astype(str))) for c in ("pos", "team", "opp", "game_id"))
    out = MD.dealt_shares(rowmap, rows, {}, pos, team, opp, game, overlap, k_main=3)
    # rows 0 (2 entries) and 2 (1) are QB + 2 with a bring-back: X and Y; row 1 (2 entries) is QB + 1: X only
    assert out["cells"] == {"X": 2, "Y": 0, "fits X/Y": 3, "house": 0}
    assert out["untagged_main_entries_by_shape"] == {"X": 2, "fits X/Y": 3}
