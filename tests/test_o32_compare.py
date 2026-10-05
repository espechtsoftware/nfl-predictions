"""scripts/o32_compare.py: the O-32 three columns and the reproduction gate (protocol amendment 1)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("o32_compare", ROOT / "scripts" / "o32_compare.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def _setup(tmp_path, unc_brier, cor_disp="defense-proe-pass-game-tail-fails"):
    orig = {"disposition": "defense-proe-pass-game-tail-fails", "gate": {"passes": False},
            "aggregate": {"rows": 16110, "control_brier_30": 0.0092894}}
    p = tmp_path / C.ORIGINAL["defense-proe"]; p.parent.mkdir(parents=True); p.write_text(json.dumps(orig))
    out = tmp_path / "reports" / "o32-correction-runs" / "defense-proe"; out.mkdir(parents=True)
    unc = {**orig, "aggregate": {"rows": 16110, "control_brier_30": unc_brier}}
    cor = {"disposition": cor_disp, "gate": {"passes": cor_disp.endswith("passes")},
           "aggregate": {"rows": 14800, "control_brier_30": 0.0099}, "game_day_active": {"rows_kept": 14800}}
    (out / "uncorrected.txt").write_text("noise\nFP_DEFENSE_PROE_JSON=" + json.dumps(unc) + "\n")
    (out / "corrected.txt").write_text("FP_DEFENSE_PROE_JSON=" + json.dumps(cor) + "\n")


def test_reproduced_then_correction_reported(tmp_path, capsys):
    _setup(tmp_path, 0.0092894 * (1 + 1e-6))
    assert C.main(["defense-proe", "--runs-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "REPRODUCED" in out and "NOT REPRODUCED" not in out and "game_day_active.rows_kept" in out


def test_drift_stops_the_study(tmp_path, capsys):
    _setup(tmp_path, 0.0100)
    assert C.main(["defense-proe", "--runs-root", str(tmp_path)]) == 3
    out = capsys.readouterr().out
    assert "NOT REPRODUCED on 1 field(s): ['aggregate.control_brier_30']" in out and "STOPS" in out
