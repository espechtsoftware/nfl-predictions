"""vet_replace_v4 under --main mix (reviewer 2026-10-06, BLOCKING: no house candidate fits WS, so a WS row could not be
replaced on Sunday): an in-cell candidate first (the union's mix spares supply them), else the best HOUSE-legal candidate,
flagged; the final validation holds a flagged position to the house shape and every other mix position to its own cell.
Offline: synthetic gains and rosters."""
import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("vet_replace_v4", ROOT / "scripts" / "vet_replace_v4.py")
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
from nfl_dfs.inference.mix_shapes import ALL_CELLS, shape_violations  # noqa: E402


def test_an_in_cell_spare_beats_a_better_house_candidate():
    gain = np.array([5.0, 1.0, 3.0])                          # the house row (0) has the best gain
    cells = [{"A1"}, {"WS"}, {"WS", "B"}]                      # rows 1-2 fit WS (the union's spares)
    assert V.pick_replacement(gain, cells, "WS") == (2, None)


def test_no_in_cell_candidate_takes_the_best_house_one_flagged():
    gain = np.array([5.0, 7.0, 3.0])
    cells = [{"A1"}, {"A1", "A2"}, {"B"}]                      # nothing fits WS
    assert V.pick_replacement(gain, cells, "WS") == (1, "A1")


def test_used_candidates_and_nothing_left_fail_closed():
    gain = np.array([-np.inf, 2.0])                            # candidate 0 already used
    assert V.pick_replacement(gain, [{"WS"}, {"B"}], "WS") == (None, None)       # no WS left, no house candidate
    assert V.pick_replacement(np.array([-np.inf]), [{"A1"}], "A1") == (None, None)
    assert V.pick_replacement(np.array([1.0]), [{"B"}], "A1") == (None, None)    # a house row never falls back to itself


def _maps():
    pos = {"q": "QB", "w1": "WR", "w2": "WR", "t": "TE", "ob": "WR", "r1": "RB", "r2": "RB", "x": "WR", "d": "DST",
           "pa": "WR", "pb": "RB"}
    team = {"q": "A", "w1": "A", "w2": "A", "t": "A", "ob": "B", "r1": "C", "r2": "E", "x": "G", "d": "H", "pa": "C", "pb": "D"}
    opp = {"q": "B", "w1": "B", "w2": "B", "t": "B", "ob": "A", "r1": "D", "r2": "F", "x": "H", "d": "G", "pa": "D", "pb": "C"}
    game = {"q": "g1", "w1": "g1", "w2": "g1", "t": "g1", "ob": "g1", "r1": "g2", "r2": "g3", "x": "g4", "d": "g4",
            "pa": "g2", "pb": "g2"}
    return pos, team, opp, game


HOUSE_ROW = ["q", "w1", "w2", "ob", "r1", "r2", "x", "t", "d"]   # QB + 3 pass catchers + a bring-back: 5 from g1, no pair


def test_the_validation_holds_a_flagged_position_to_the_house_shape_only():
    pos, team, opp, game = _maps()
    cell_at = {0: "WS", 1: "WS"}; fallback_at = {0: "A1"}
    assert shape_violations(HOUSE_ROW, "WS", pos, team, opp, game)                       # a house row breaks WS
    assert shape_violations(HOUSE_ROW, V.row_cell(0, cell_at, fallback_at), pos, team, opp, game) == []   # flagged: held to A1
    assert shape_violations(HOUSE_ROW, V.row_cell(1, cell_at, fallback_at), pos, team, opp, game)         # unflagged: still WS
    assert V.row_cell(2, cell_at, fallback_at) is None                                   # an untagged (house / sleeve) row
    assert "A1" in ALL_CELLS


def test_the_script_uses_the_fallback_in_the_choice_the_validation_and_the_receipt():
    text = (ROOT / "scripts" / "vet_replace_v4.py").read_text()
    assert "j, fb = pick_replacement(gain, pool_cells, need)" in text
    assert "mix_violations(_t, row_cell(p, cell_at, fallback_at))" in text
    assert '**({"cell_fallback": "house"} if fb else {})' in text and '"cell_fallbacks": [' in text
    assert "BY THE HOUSE FALLBACK" in text                       # the capitals banner on the 'replaced' line (replacement-status)


def test_replacement_sources_are_counted_and_no_term_rows_named():
    """The reviewer (10-06): under the ownership term, rows of the no-term paper control main ('mix_control') may fill
    replacements; the week's record counts them."""
    n, note = V.source_summary([{"candidate_source": "mix_spare"}, {"candidate_source": "mix_control"},
                                {"candidate_source": "mix_control"}, {"candidate_source": "t70"}])
    assert n == {"mix_control": 2, "mix_spare": 1, "t70": 1}
    assert note == "; sources {'mix_control': 2, 'mix_spare': 1, 't70': 1} (2 from the NO-TERM control main)"
    assert V.source_summary([]) == ({}, "")
    assert V.source_summary([{"candidate_source": "saturday"}])[1] == "; sources {'saturday': 1}"


def test_a_replacement_is_priced_on_fp_means_when_the_union_was():
    """The outside review (10-06): the union selected on FP's means, so the replacement's worlds are recentred on them
    (our spread and correlation kept); no FP file, an edited file or another frame's file -> ours, said in the record."""
    import hashlib, json, tempfile
    import numpy as np, pandas as pd
    from pathlib import Path
    VR = V
    d = Path(tempfile.mkdtemp())
    (d / "frame.parquet").write_bytes(b"frame-bytes")
    ids = ["a", "b", "c"]; mean = np.array([10.0, 5.0, 8.0])
    shift, rec = VR.fp_shift(mean, ids, d)
    assert not shift.any() and rec["objective"].startswith("ours (the run carries no FP source")
    pd.DataFrame({"id": ["a", "b"], "fp": [12.0, 4.0]}).to_csv(d / "proj_source.csv", index=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    meta = {"csv_sha256": sha(d / "proj_source.csv"), "frame_sha256": sha(d / "frame.parquet")}
    (d / "proj_source.csv.json").write_text(json.dumps(meta))
    shift, rec = VR.fp_shift(mean, ids, d)
    assert list(shift) == [2.0, -1.0, 0.0] and rec["fp_players"] == 2 and "Fantasy Points" in rec["objective"]
    (d / "proj_source.csv.json").write_text(json.dumps({**meta, "frame_sha256": "x"}))
    shift, rec = VR.fp_shift(mean, ids, d)
    assert not shift.any() and "another frame" in rec["objective"]
    (d / "proj_source.csv.json").write_text(json.dumps({**meta, "csv_sha256": "x"}))
    shift, rec = VR.fp_shift(mean, ids, d)
    assert not shift.any() and "does not match" in rec["objective"]


def test_the_fp_shift_is_applied_before_the_unavailable_rows_are_zeroed_and_recorded():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "vet_replace_v4.py").read_text()
    assert src.index("fp_shift(np.concatenate([inc, hs], axis=1)") < src.index("inc_g[zr, :] = 0.0")
    assert '"replacement_objective": repl_objective' in src


def test_an_unreadable_sidecar_falls_back_to_ours_never_a_crash():
    import tempfile
    import numpy as np, pandas as pd
    from pathlib import Path
    d = Path(tempfile.mkdtemp()); (d / "frame.parquet").write_bytes(b"f")
    pd.DataFrame({"id": ["a"], "fp": [3.0]}).to_csv(d / "proj_source.csv", index=False)
    (d / "proj_source.csv.json").write_text("{not json")
    shift, rec = V.fp_shift(np.array([1.0]), ["a"], d)
    assert not shift.any() and "sidecar unreadable" in rec["objective"]


def test_the_upload_sheet_names_the_replacement_pricing_and_banners_a_fallback(tmp_path):
    """The reviewer (10-06, R2): an FP book whose replacement fell back to our worlds must never read as a plain OK."""
    import re, subprocess
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
    fn = re.search(r"^repl_objective_note\(\) \{.*?^\}\n", src, re.S | re.M).group(0)
    assert '$(repl_objective_note "$lo/paid-replace.log")' in src
    cases = {"fp": "REPLACEMENT OBJECTIVE: the corrected mix recentred on Fantasy Points' means (the union's proj_source.csv)\n",
             "failed": "REPLACEMENT OBJECTIVE: ours (the FP source failed: the FP file was built for another frame)\n",
             "none": "replaced 2 unavailable lineup(s)\n"}
    out = {}
    for k, text in cases.items():
        log = tmp_path / f"{k}.log"; log.write_text(text)
        out[k] = subprocess.run(["bash", "-c", fn + f'printf "OK%s" "$(repl_objective_note {log})"'], capture_output=True, text=True).stdout
    assert out["fp"] == "OK; priced on: the corrected mix recentred on Fantasy Points' means (the union's proj_source.csv)"
    assert out["failed"].startswith("OK; *** REPLACEMENTS PRICED ON OUR PROJECTIONS: ours (the FP source failed") and out["failed"].endswith("***")
    assert out["none"] == "OK"
