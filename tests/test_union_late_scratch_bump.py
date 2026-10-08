"""union_reselect --proj-source-late-scratch-bump (the outside reviewer 2026-10-08): a player unavailable at the build whom
Fantasy Points still projects (FP has not processed the scratch) gives his depth-2 same-position teammate our T-70
next-man-up bump (cascade_adjust.find_t70_vacated_targets / T70_VACATED_TABLE) on top of FP's number. Synthetic frames
only; the pinned lab clone is not needed."""
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402
from nfl_dfs.inference import cascade_adjust as CA  # noqa: E402

DEPTHS = {"QB": 2, "RB": 3, "WR": 3, "TE": 2}


def _frame() -> pd.DataFrame:
    """Two synthetic teams, a depth chart per position, our projection falling with depth; a DST each."""
    rows, dk = [], 1000
    for t, opp in (("AAA", "BBB"), ("BBB", "AAA")):
        for p, n in DEPTHS.items():
            for d in range(1, n + 1):
                dk += 1
                rows.append({"id": f"{t.lower()}_{p.lower()}{d}", "name": f"{t} {p}{d}", "pos": p, "position": p, "team": t,
                             "opp": opp, "game_id": "g1", "salary": 5000, "depth_rank": d, "status": "", "injury_status": None,
                             "roster_status": "ACT", "dk_player_id": dk, "mean_projection": round(14.0 / d, 3)})
        dk += 1
        rows.append({"id": f"{t}_DST", "name": t, "pos": "DST", "position": "DST", "team": t, "opp": opp, "game_id": "g1",
                     "salary": 3000, "depth_rank": None, "status": "", "injury_status": None, "roster_status": None,
                     "dk_player_id": dk, "mean_projection": 6.0})
    fr = pd.DataFrame(rows)
    fr["depth_rank"] = fr["depth_rank"].astype("Int64")                 # the live frame's dtype
    return fr


def _fp(fr: pd.DataFrame, **override) -> dict[str, float]:
    """FP's numbers: ours + 1 for every player (so a replaced value is visible), with per-id overrides."""
    fp = {i: float(m) + 1.0 for i, m in zip(fr["id"], fr["mean_projection"])}
    fp.update(override)
    return fp


def _applied(fr: pd.DataFrame, fp: dict[str, float]) -> pd.DataFrame:
    """The frame as apply_proj_source leaves it: FP's number in mean_projection, ours beside it."""
    out = fr.copy()
    out["mean_projection_ours"] = out["mean_projection"]
    hit = out["id"].isin(fp)
    out.loc[hit, "mean_projection"] = out.loc[hit, "id"].map(fp).astype(float)
    return out


def _dk(fr: pd.DataFrame, out_ids: list[str], status: str = "O") -> pd.DataFrame:
    """The --dk-status snapshot (id = dk_player_id, status), every player Active except out_ids."""
    st = ["Active" if i not in out_ids else status for i in fr["id"]]
    return pd.DataFrame({"id": fr["dk_player_id"].astype(str), "status": st}).astype(str)


def _unchanged_except(before: pd.DataFrame, after: pd.DataFrame, bumped: dict[str, float]) -> None:
    b = dict(zip(before["id"], before["mean_projection"]))
    a = dict(zip(after["id"], after["mean_projection"]))
    for i in b:
        assert a[i] == pytest.approx(b[i] + bumped.get(i, 0.0)), i
    pd.testing.assert_series_equal(before["mean_projection_ours"], after["mean_projection_ours"])
    assert list(before.columns) == list(after.columns)


# ---- flag off: the union is unchanged ---------------------------------------------------------------------------------

def test_the_flag_defaults_off_and_is_the_only_way_in():
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert 'ap.add_argument("--proj-source-late-scratch-bump", action="store_true"' in src     # store_true: default False
    main_src = src[src.index("def main("):]
    calls = [m.start() for m in re.finditer(r"late_scratch_bump_step\(", main_src)]
    assert len(calls) == 1                                                                  # one call site in main()
    guard = main_src.rfind("if a.proj_source_late_scratch_bump:", 0, calls[0])
    assert guard != -1 and main_src[guard:calls[0]].count("\n") == 1                         # directly under the flag
    assert "late_scratch_bump" not in src[src.index("def apply_proj_source("):src.index("LATE_SCRATCH_RULE =")]


def test_apply_proj_source_is_untouched_by_the_new_step(tmp_path):
    """With the flag off main() runs apply_proj_source exactly as before: same frame, no late_scratch_bump in its record."""
    fr = _frame()
    fpath = tmp_path / "frame.parquet"; fr.to_parquet(fpath)
    fp = _fp(fr)
    csv = tmp_path / "proj_fp.csv"
    pd.DataFrame({"id": list(fp), "fp": list(fp.values())}).to_csv(csv, index=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    Path(str(csv) + ".json").write_text(json.dumps({"frame_sha256": sha(fpath), "csv_sha256": sha(csv)}))
    out, meta = ur.apply_proj_source(fr, csv, fpath)
    pd.testing.assert_frame_equal(out, _applied(fr, fp))
    assert "late_scratch_bump" not in meta


# ---- the bump ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("p", ["RB", "WR", "TE"])
def test_a_late_scratch_fp_still_projects_bumps_the_depth2_teammate_by_our_t70_bump(p, capsys):
    fr = _frame(); fp = _fp(fr)
    before = _applied(fr, fp)
    starter, backup = f"aaa_{p.lower()}1", f"aaa_{p.lower()}2"
    after, rec = ur.late_scratch_bump(before, fp, _dk(fr, [starter]), 1.0)
    gross = CA.T70_VACATED_TABLE[p]                                    # our pipeline's own T-70 number, not a new rule
    _unchanged_except(before, after, {backup: gross})
    assert rec["applied"] and rec["dk_status"] and rec["total_points"] == pytest.approx(gross)
    assert [s["id"] for s in rec["late_scratches"]] == [starter]
    (b,) = rec["bumps"]
    assert (b["teammate_id"], b["scratch_id"], b["points"]) == (backup, [starter], pytest.approx(gross))
    assert b["after"] == pytest.approx(b["before"] + gross) and b["before"] == pytest.approx(fp[backup])
    out = capsys.readouterr().out
    assert f"LATE-SCRATCH BUMP: AAA {p}2 ({p} AAA) +{gross:.2f} for AAA {p}1" in out
    assert "1 teammate(s) bumped" in out
    json.dumps(rec)                                                    # the receipt can carry it


def test_the_step_records_the_bump_in_the_proj_source_meta(tmp_path):
    fr = _frame(); fp = _fp(fr)
    csv = tmp_path / "proj_fp.csv"
    pd.DataFrame({"id": list(fp), "fp": list(fp.values())}).to_csv(csv, index=False)
    meta = {"file": str(csv), "replaced": len(fp)}
    after = ur.late_scratch_bump_step(_applied(fr, fp), csv, meta, _dk(fr, ["bbb_rb1"]), 1.0)
    assert meta["late_scratch_bump"]["bumps"][0]["teammate_id"] == "bbb_rb2"
    assert after.set_index("id").loc["bbb_rb2", "mean_projection"] == pytest.approx(fp["bbb_rb2"] + CA.T70_VACATED_TABLE["RB"])


def test_a_scratch_fp_already_zeroed_adds_nothing(capsys):
    fr = _frame(); fp = _fp(fr, aaa_rb1=0.0)                           # FP has processed the scratch
    before = _applied(fr, fp)
    after, rec = ur.late_scratch_bump(before, fp, _dk(fr, ["aaa_rb1"]), 1.0)
    _unchanged_except(before, after, {})
    assert rec["applied"] and rec["bumps"] == [] and rec["late_scratches"] == []
    assert [s["id"] for s in rec["fp_already_processed"]] == ["aaa_rb1"]
    assert "0 late scratch(es)" in capsys.readouterr().out


def test_only_late_scratches_count_not_players_out_before_the_frame():
    """A starter the frame already lists Out (FP processed: his mates are FP's) is not a source; only the snapshot's is."""
    fr = _frame()
    fr.loc[fr["id"] == "aaa_wr1", "injury_status"] = "Doubtful"        # known before the frame: production already bumped
    fp = _fp(fr)
    after, rec = ur.late_scratch_bump(_applied(fr, fp), fp, _dk(fr, ["aaa_rb1"]), 1.0)
    assert [b["teammate_id"] for b in rec["bumps"]] == ["aaa_rb2"]


def test_guards_never_bump_an_unavailable_unprojected_or_floored_teammate():
    fr = _frame()
    fp = _fp(fr, bbb_wr2=0.4)                                          # FP has the WR backup under the floor
    del fp["aaa_te2"]                                                  # FP has no number for the TE backup: ours is kept
    before = _applied(fr, fp)
    after, rec = ur.late_scratch_bump(before, fp, _dk(fr, ["aaa_rb1", "aaa_rb2", "aaa_te1", "bbb_wr1"]), 1.0)
    _unchanged_except(before, after, {})                              # nothing bumped
    why = {s.get("teammate_id"): s["why"] for s in rec["skipped"] if "teammate_id" in s}
    by_scratch = {s["scratch_id"]: s["why"] for s in rec["skipped"] if isinstance(s.get("scratch_id"), str)}
    assert "aaa_rb2" not in why                                        # the RB backup is out too: never a target ...
    assert by_scratch["aaa_rb1"] == "no depth-2 same-position teammate on the slate"   # ... and the RB scratch says so
    assert "ours is kept" in why["aaa_te2"]
    assert "never resurrected" in why["bbb_wr2"]


def test_a_depth2_or_qb_scratch_is_named_and_bumps_nobody():
    fr = _frame(); fp = _fp(fr)
    before = _applied(fr, fp)
    after, rec = ur.late_scratch_bump(before, fp, _dk(fr, ["aaa_wr2", "bbb_qb1"]), 1.0)
    _unchanged_except(before, after, {})
    why = {s["scratch_id"]: s["why"] for s in rec["skipped"] if "scratch_id" in s and isinstance(s["scratch_id"], str)}
    assert "depth_rank 2" in why["aaa_wr2"] and why["bbb_qb1"].startswith("QB")


def test_dk_status_out_spellings_follow_the_union_rule():
    fr = _frame(); fp = _fp(fr)
    after, rec = ur.late_scratch_bump(_applied(fr, fp), fp, _dk(fr, ["aaa_te1"], status="OUT"), 1.0)
    assert [b["teammate_id"] for b in rec["bumps"]] == ["aaa_te2"]
    after, rec = ur.late_scratch_bump(_applied(fr, fp), fp, _dk(fr, ["aaa_te1"], status="Q"), 1.0)
    assert rec["bumps"] == [] and rec["late_scratches"] == []        # Questionable is not out


# ---- missing inputs: a loud no-op, never a failed build ---------------------------------------------------------------

def test_no_projection_source_is_a_loud_noop(capsys):
    fr = _frame()
    meta: dict = {}
    assert ur.late_scratch_bump_step(fr, None, meta, _dk(fr, ["aaa_rb1"]), 1.0) is fr
    assert meta == {}
    assert "LATE-SCRATCH BUMP: NOT APPLIED -- no projection source" in capsys.readouterr().out


def test_an_unreadable_override_or_frame_without_columns_is_a_loud_noop(tmp_path, capsys):
    fr = _frame(); fp = _fp(fr)
    before = _applied(fr, fp)
    meta = {"file": "x"}
    assert ur.late_scratch_bump_step(before, tmp_path / "missing.csv", meta, _dk(fr, ["aaa_rb1"]), 1.0) is before
    assert meta["late_scratch_bump"]["not_applied"] == "the FP override file could not be read"
    after, rec = ur.late_scratch_bump(before.drop(columns=["depth_rank"]), fp, _dk(fr, ["aaa_rb1"]), 1.0)
    assert "depth_rank" in rec["not_applied"] and not rec["applied"] and rec["bumps"] == []
    after, rec = ur.late_scratch_bump(fr, fp, _dk(fr, ["aaa_rb1"]), 1.0)          # FP never applied: no mean_projection_ours
    assert after is fr and "mean_projection_ours" in rec["not_applied"]
    assert capsys.readouterr().out.count("!!! LATE-SCRATCH BUMP: NOT APPLIED") == 3


def test_no_dk_status_snapshot_says_the_step_is_blind_to_later_scratches(capsys):
    fr = _frame(); fp = _fp(fr)
    before = _applied(fr, fp)
    after, rec = ur.late_scratch_bump(before, fp, None, 1.0)
    _unchanged_except(before, after, {})
    assert rec["applied"] and not rec["dk_status"] and rec["bumps"] == []
    assert "NO --dk-status SNAPSHOT" in capsys.readouterr().out


def test_an_error_inside_the_rule_is_a_loud_noop(monkeypatch, capsys):
    fr = _frame(); fp = _fp(fr)
    before = _applied(fr, fp)

    def boom(_):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(CA, "find_t70_vacated_targets", boom)
    after, rec = ur.late_scratch_bump(before, fp, _dk(fr, ["aaa_rb1"]), 1.0)
    assert after is before and rec["bumps"] == [] and rec["total_points"] == 0.0
    assert rec["not_applied"] == "RuntimeError: synthetic failure"
    assert "NOT APPLIED -- RuntimeError: synthetic failure" in capsys.readouterr().out
