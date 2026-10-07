"""Study 61's reader: the constants and printed level; the team aliases (every W5 form) and name normalisation; the time
forms; the spec's record rules (late, supersedes, versions); the join; the player groups; the residuals and Delta; the
looks; the union's content checks; the entered-union rule; the census reads no outcome; nothing textual is printed."""
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("s61_r14_grade", ROOT / "scripts" / "s61_r14_grade.py")
R = importlib.util.module_from_spec(spec); sys.modules["s61_r14_grade"] = R; spec.loader.exec_module(R)
PREREG = ROOT / "reports" / "2026-10-08-prereg-study61-r14-news-grading.md"
UTC = timezone.utc


def test_constants_and_the_printed_level():
    assert R.LOOKS == (8, 10) and R.MIN_WEEKS == 4 and R.MIN_SIDE == 10 and R.ONE_SIDED == 0.95 and R.PROSPECTIVE_FROM == 5
    assert R.SKILL == ("QB", "RB", "WR", "TE")
    src = (ROOT / "scripts" / "s61_r14_grade.py").read_text()
    assert "the two-sided 90% t interval (each side a one-sided 95% bound)" in src
    text = PREREG.read_text()
    assert "two-sided 90% t interval" in text and "one-sided 95% bound" in text and "at least 10 players" in text


@pytest.mark.parametrize("written,code", [
    ("Eagles", "PHI"), ("Mia", "MIA"), ("LV", "LV"), ("Jax", "JAX"), ("Philly", "PHI"), ("Washington", "WAS"),
    ("Cincinnati Bengals", "CIN"), ("Rams", "LA"), ("LAR", "LA"), ("Los Angeles Chargers", "LAC"), ("49ers", "SF"),
    ("San Francisco 49ers", "SF"), ("New York Giants", "NYG"), ("Jets", "NYJ"), ("Pittsburgh", "PIT"), ("KC", "KC"),
    ("Commanders", "WAS"), ("Was", "WAS"), ("Buccaneers", "TB"), ("Seattle Seahawks", "SEA"), ("GB", "GB"),
    ("Los Angeles", None), ("New York", None), ("FA", None), (None, None), (float("nan"), None)])
def test_team_aliases(written, code):
    assert R.team_code(written) == code


def test_every_code_maps_to_itself():
    assert all(R.team_code(c) == c for c in R._CODES) and len(R._CODES) == 32


def test_name_normalisation():
    assert R.norm_name("D.J. Moore") == R.norm_name("DJ Moore") == "dj moore"
    assert R.norm_name("Kenneth Walker III") == "kenneth walker" and R.norm_name("Marvin Harrison Jr.") == "marvin harrison"
    assert R.norm_name("Amon-Ra St. Brown") == "amon ra st brown" and R.norm_name("Ja'Marr Chase") == "jamarr chase"
    assert R.norm_name("Ja’Marr  Chase") == "jamarr chase"


def test_the_time_forms():
    want = datetime(2026, 10, 7, 14, 53, 3, 52565, tzinfo=UTC)
    assert R.when("2026-10-07 14:53:03.052565+00") == want
    assert R.when("2026-10-07T09:41:10.730Z") == datetime(2026, 10, 7, 9, 41, 10, 730000, tzinfo=UTC)
    assert R.when("2026-10-07T10:41:25+00:00") == datetime(2026, 10, 7, 10, 41, 25, tzinfo=UTC)
    assert R.when("2026-10-11 15:33:13.856511+00:00") == datetime(2026, 10, 11, 15, 33, 13, 856511, tzinfo=UTC)


def _rec(rid, player, ft="role_up", d=1, art="a1", sha="s1", pub="2026-10-06T15:00:00.000Z", ret="2026-10-07T09:00:00.000Z",
         logged="2026-10-07T10:00:00+00:00", team="Eagles", **kw):
    return {"record_id": rid, "article_id": art, "source_sha256": sha, "published_date": pub, "retrieved_at": ret,
            "logged_utc": logged, "player": player, "team": team, "fact_type": ft, "direction": d, "quote": f"QUOTE-{rid}", **kw}


CUT = datetime(2026, 10, 11, 15, 33, tzinfo=UTC)


def test_the_record_rules():
    recs = [_rec("r1", "A One"), _rec("r2", "B Two", logged="2026-10-11T16:00:00+00:00"),       # r2 late
            _rec("r3", "C Three", ft="availability", d=-1), _rec("r4", "C Three", ft="availability", d=0, supersedes="r3"),
            _rec("r5", "D Four", sha="s1"), _rec("r6", "D Four", sha="s2", pub="2026-10-07T15:00:00.000Z", ret="2026-10-08T09:00:00.000Z", d=-1),
            _rec("r7", "E Five", sha="s1")]                                                              # v2 dropped E: still counts
    kept, c = R.counted_records(recs, CUT)
    ids = {r["record_id"] for r in kept}
    assert ids == {"r1", "r4", "r6", "r7"} and c["late"] == 1 and c["superseded"] == 1 and c["older_version"] == 1
    assert c["multi_version_keys"] == 1 and c["kept"] == 4


def _pop(rows):
    p = pd.DataFrame(rows, columns=["id", "gsis_id", "dk_player_id", "display_name", "pos", "team", "fp"])
    p["nname"] = p.display_name.map(R.norm_name)
    return p


POP = _pop([("g1", "g1", "11", "A One", "WR", "PHI", 10.0), ("g2", "g2", "12", "Sam Same", "RB", "DAL", 8.0),
            ("g3", "g3", "13", "Sam Same", "WR", "NYG", 6.0), ("g4", "g4", "14", "Traded Guy", "TE", "MIA", 5.0),
            ("g5", "g5", "15", "Plain Name", "QB", "BUF", 20.0)])


def test_the_join():
    recs = [_rec("j1", "A One"), _rec("j2", "Sam Same", team="Cowboys"), _rec("j3", "Sam Same", team=None),
            _rec("j4", "Traded Guy", team="Jets"), _rec("j5", "Nobody Here"), _rec("j6", "Plain Name", team=None),
            _rec("j7", "Plain Name", team="Bills", gsis_id="g9"), _rec("j8", "A One", team="Gotham Knights")]
    pairs, c = R.join(recs, POP)
    got = {r["record_id"]: int(i) for r, i in pairs}
    assert got == {"j1": 0, "j2": 1, "j4": 3, "j6": 4, "j8": 0}
    assert c["name_team"] == 3 and c["name_only"] == 3 and c["ambiguous"] == 1 and c["not_on_frame"] == 1
    assert c["id_disagrees"] == 1 and c["joined"] == 5 and c["team_unknown"] == {"Gotham Knights": 1}


def test_the_player_groups():
    pairs = [(_rec("p1", "x", d=1), 0), (_rec("p2", "x", d=1, ft="matchup"), 0), (_rec("p3", "y", d=-1), 1),
             (_rec("p4", "z", d=1), 2), (_rec("p5", "z", d=-1, ft="availability"), 2), (_rec("p6", "w", d=0), 3),
             (_rec("p7", "v", d=-1, ft="other"), 4)]
    assert R.player_groups(pairs) == {0: 1, 1: -1, 2: 0, 3: 0, 4: -1}
    assert R.player_groups(pairs, exclude_types=("other",)) == {0: 1, 1: -1, 2: 0, 3: 0}


def test_residuals_and_delta():
    rng = np.random.default_rng(61)
    n = 60
    pop = _pop([(f"g{i}", f"g{i}", str(i), f"P {i}", ("WR", "RB")[i % 2], "PHI", 10.0) for i in range(n)])
    pts = 10.0 + rng.normal(0, 5, n)
    act = pd.DataFrame({"gsis_id": [f"g{i}" for i in range(n - 1)], "dk_points": pts[: n - 1]})   # one has no actuals
    rp = R.residuals(pop, act)
    for pos in ("WR", "RB"):
        assert abs(rp[pop.pos == pos].mean()) < 1e-9                                                # demeaned per position
    assert np.isnan(rp.iloc[n - 1])
    groups = {i: (1 if i < 20 else -1 if i < 40 else 0) for i in range(n)}
    d = R.delta(groups, rp)
    assert math.isclose(d["delta"], rp.iloc[:20].mean() - rp.iloc[20:40].mean()) and d["valid"] and d["n_plus"] == 20
    assert R.delta({i: 1 for i in range(9)} | {j: -1 for j in range(20, 40)}, rp)["valid"] is False   # < 10 a side


def test_the_looks():
    assert R.read_look([1.0, 2.0, 1.5])["reading"].startswith("too few valid weeks")
    v = [1.2, 1.5, 1.1, 1.4]
    r = R.read_look(v)
    half = student_t.ppf(0.95, 3) * np.std(v, ddof=1) / 2
    assert r["reading"] == "the articles carry information FP's projections had not priced" and math.isclose(r["lo"], np.mean(v) - half)
    assert R.read_look([-x for x in v])["reading"] == "the articles point the wrong way"
    assert R.read_look([1.0, -1.2, 0.5, -0.4])["reading"] == "no information shown"
    assert R.looks_due([5, 6, 7]) == [] and R.looks_due([5, 6, 7, 8]) == [8] and R.looks_due(list(range(5, 11))) == [8, 10]


def _union(d: Path, frame_ok=True, proj_ok=True):
    d.mkdir(parents=True)
    fr = pd.DataFrame({"pulled_at": ["2026-10-11 15:33:13.856511+00:00"] * 3, "id": ["g1", "g2", "355"],
                       "gsis_id": ["g1", "g2", "0.0"], "dk_player_id": [11.0, 12.0, 355.0], "display_name": ["A One", "B Two", "Bills"],
                       "pos": ["WR", "RB", "DST"], "team": ["PHI", "DAL", "BUF"]})
    fr.to_parquet(d / "frame.parquet")
    pd.DataFrame({"id": ["g1", "g2"], "dk_draftable_id": [1, 2], "name": ["A One", "B Two"], "pos": ["WR", "RB"],
                  "ours": [9.0, 7.0], "fp": [10.0, 8.0]}).to_csv(d / "proj_source.csv", index=False)
    (d / "proj_source.csv.json").write_text(json.dumps({"fp_last_updated": "2026-10-11T13:58:38+00:00"}))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    rec = {"config": {"union": {"input_sha256": {"t70_frame": sha(d / "frame.parquet") if frame_ok else "0" * 64},
                                "proj_source": {"sha256": sha(d / "proj_source.csv") if proj_ok else "0" * 64}}}}
    (d / "receipt.json").write_text(json.dumps(rec))
    return d


def test_the_union_is_checked_by_content(tmp_path):
    U = R.load_union(_union(tmp_path / "ok"))
    assert list(U["pop"].id) == ["g1", "g2"] and U["cutoff"] == datetime(2026, 10, 11, 15, 33, 13, 856511, tzinfo=UTC)
    assert U["fp_last_updated"] == datetime(2026, 10, 11, 13, 58, 38, tzinfo=UTC) and U["skill_on_frame"] == 2
    with pytest.raises(SystemExit, match="not the receipt's T-70 frame"):
        R.load_union(_union(tmp_path / "f", frame_ok=False))
    with pytest.raises(SystemExit, match="not the receipt's projection file"):
        R.load_union(_union(tmp_path / "p", proj_ok=False))


def test_only_the_entered_union_unless_smoke_and_nothing_textual_printed(tmp_path, monkeypatch, capsys):
    u = _union(tmp_path / "u")
    log = tmp_path / "log"; log.mkdir()
    recs = [_rec("t1", "A One", logged="2026-10-07T10:00:00+00:00"), _rec("t2", "B Two", team="Cowboys", d=-1)]
    (log / "2026-w05.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    monkeypatch.setattr(R, "entered_union", lambda w, *a: tmp_path / "elsewhere")
    with pytest.raises(SystemExit, match="is not weeks.json's entered_union"):
        R.main(["--census", "--weeks", "5", "--union", f"5={u}", "--log-dir", str(log)])
    assert R.main(["--census", "--smoke", "--weeks", "5", "--union", f"5={u}", "--log-dir", str(log)]) == 0
    out = capsys.readouterr().out
    assert "SMOKE (mechanics only; never a record)" in out and "'plus': 1, 'minus': 1" in out
    for text in ("QUOTE-t1", "QUOTE-t2", "A One", "B Two"):
        assert text not in out                                         # aggregates only
    monkeypatch.setattr(R, "entered_union", lambda w, *a: u)
    assert R.main(["--census", "--weeks", "5", "--log-dir", str(log)]) == 0      # the entered union, by default
    with pytest.raises(SystemExit, match="for --smoke only"):
        R.main(["--census", "--weeks", "5", "--log-dir", str(log), "--smoke-cutoff-utc", "2026-10-11T15:33:00Z"])


def test_the_census_reads_no_outcome():
    src = (ROOT / "scripts" / "s61_r14_grade.py").read_text()
    for fn in ("def week_census(", "def counted_records(", "def join(", "def player_groups(", "def load_union(", "def load_log("):
        body = src[src.index(fn):]; body = body[:body.index("\ndef ", 1)]
        for word in ("load_actuals", "dk_points", "bigquery", "residuals("):
            assert word not in body, (fn, word)
    main = src[src.index("def main("):]
    assert main.index("if not a.census:") < main.index("load_actuals(")                  # actuals only outside the census


def test_the_scored_path_on_a_synthetic_week(tmp_path, monkeypatch, capsys):
    """The whole scored path (the warehouse query replaced): 24 players a side, Delta, the descriptives, no look yet."""
    d = tmp_path / "u"; d.mkdir()
    n = 60
    ids = [f"g{i}" for i in range(n)]; names = [f"Player {chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(n)]
    pos = [("WR", "RB", "TE", "QB")[i % 4] for i in range(n)]
    pd.DataFrame({"pulled_at": ["2026-10-11 15:33:13+00:00"] * n, "id": ids, "gsis_id": ids, "dk_player_id": [float(i) for i in range(n)],
                  "display_name": names, "pos": pos, "team": ["PHI"] * n}).to_parquet(d / "frame.parquet")
    pd.DataFrame({"id": ids, "dk_draftable_id": range(n), "name": names, "pos": pos, "ours": [9.0] * n, "fp": [10.0] * n}).to_csv(d / "proj_source.csv", index=False)
    (d / "proj_source.csv.json").write_text(json.dumps({"capture": {"fp_last_updated": "2026-10-11T13:58:38+00:00"}}))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    (d / "receipt.json").write_text(json.dumps({"config": {"union": {"input_sha256": {"t70_frame": sha(d / "frame.parquet")},
                                                                     "proj_source": {"sha256": sha(d / "proj_source.csv")}}}}))
    log = tmp_path / "log"; log.mkdir()
    recs = [_rec(f"x{i}", names[i], d=(1 if i < 24 else -1 if i < 48 else 0), team="Eagles",
                 pub=("2026-10-06T15:00:00.000Z" if i % 2 else "2026-10-11T15:00:00.000Z")) for i in range(n)]
    (log / "2026-w05.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    pts = [14.0 if i < 24 else 8.0 if i < 48 else 10.0 for i in range(n)]               # good news +4, bad news -2
    monkeypatch.setattr(R, "entered_union", lambda w, *a: d)
    monkeypatch.setattr(R, "load_actuals", lambda s, w, g: (pd.DataFrame({"gsis_id": ids, "dk_points": pts}), "f" * 64))
    out_json = tmp_path / "o.json"
    assert R.main(["--weeks", "5", "--log-dir", str(log), "--out", str(out_json)]) == 0
    res = json.loads(out_json.read_text())["per_week"]["5"]
    assert res["primary"]["n_plus"] == 24 and res["primary"]["n_minus"] == 24 and res["primary"]["valid"]
    assert math.isclose(res["primary"]["delta"], 6.0, abs_tol=1e-9)                    # demeaning cancels in the difference
    assert res["descriptive"]["sign_rate"] == 1.0 and res["descriptive"]["zero_only"]["players"] == 12
    assert res["descriptive"]["priceable_split"]["priceable"]["records"] == 24 and res["actuals_sha256"] == "f" * 64
    out = capsys.readouterr().out
    assert "PROSPECTIVE: Delta +6.000 DK points (24 +1 vs 24 -1 players; valid)" in out and "no look yet" in out
    assert "Player" not in out and "QUOTE" not in out


def test_a_fallback_week_is_recorded_not_valid_and_the_others_stand(tmp_path, monkeypatch, capsys):
    """Amendment 2: a union with no FP projection (the T-70 fell back to ours) is a NOT VALID week, never a refusal of
    the other weeks; an FP file the receipt names but which is missing still refuses."""
    ok = _union(tmp_path / "w5")                                                     # a normal week
    fb = tmp_path / "w6"; fb.mkdir()                                                 # the fallback week: no proj_source
    pd.read_parquet(ok / "frame.parquet").to_parquet(fb / "frame.parquet")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    (fb / "receipt.json").write_text(json.dumps({"config": {"union": {"input_sha256": {"t70_frame": sha(fb / "frame.parquet")}}}}))
    assert R.load_union(fb) == {"no_fp": True, "reason": "no FP projection: the T-70 build fell back to our projections"}
    broken = _union(tmp_path / "w7"); (broken / "proj_source.csv").unlink()           # named by the receipt, missing
    with pytest.raises(SystemExit, match="not the receipt's projection file"):
        R.load_union(broken)
    log = tmp_path / "log"; log.mkdir()
    for w in (5, 6):
        (log / f"2026-w{w:02d}.jsonl").write_text(json.dumps(_rec(f"f{w}", "A One")) + "\n")
    monkeypatch.setattr(R, "entered_union", lambda w, *a: {5: ok, 6: fb}[w])
    monkeypatch.setattr(R, "load_actuals", lambda s, w, g: (pd.DataFrame({"gsis_id": ["g1", "g2"], "dk_points": [12.0, 6.0]}), "a" * 64))
    out_json = tmp_path / "o.json"
    assert R.main(["--weeks", "5,6", "--log-dir", str(log), "--out", str(out_json)]) == 0
    res = json.loads(out_json.read_text())["per_week"]
    assert res["6"] == {"valid": False, "reason": "no FP projection: the T-70 build fell back to our projections"}
    assert "primary" in res["5"] and res["5"]["primary"]["valid"] is False                # 1 vs 0 players: too few a side
    out = capsys.readouterr().out
    assert "W6: NOT VALID -- no FP projection" in out and "no look yet (valid prospective weeks so far: 0)" in out
    assert R.main(["--census", "--weeks", "5,6", "--log-dir", str(log)]) == 0          # the census passes over it too


TC_POP = _pop([("q1", "q1", "21", "Tb Qb", "QB", "TB", 18.0), ("w1", "w1", "22", "Tb Wr", "WR", "TB", 12.0),
               ("t1", "t1", "23", "Tb Te", "TE", "TB", 7.0), ("r1", "r1", "24", "Tb Rb", "RB", "TB", 11.0),
               ("q2", "q2", "25", "Dal Qb", "QB", "DAL", 17.0), ("r2", "r2", "26", "Dal Rb", "RB", "DAL", 10.0),
               ("w2", "w2", "27", "Dal Wr", "WR", "DAL", 13.0)])
TC_OPP = {"TB": "DAL", "DAL": "TB"}


def _tc(rid, unit, eff, team="Cowboys", player="A Corner", **kw):
    return _rec(rid, player, ft="team_change", d=0, team=team, unit=unit, unit_effect=eff, **kw)


def test_the_team_change_mapping():
    """Amendment 3: the spec's mapping, verbatim; a count-only unit, an unknown team and a team off the slate derive nothing."""
    der, c = R.derive_team_change([_tc("c1", "pass_defense", 1), _tc("c2", "run_defense", 1), _tc("c3", "offensive_line", -1),
                                   _tc("c4", "pass_rush", -1), _tc("c5", "receiving_corps", 1), _tc("c6", "backfield", -1),
                                   _tc("c7", "pass_defense", 1, team="Gotham"), _tc("c8", "pass_defense", 1, team="Steelers"),
                                   _tc("c9", "run_defense", 0), _tc("c10", "special_teams", 1)], TC_POP, TC_OPP)
    got = {(r["record_id"], TC_POP.at[i, "id"]): d for r, i, d in der}
    assert got == {("c1", "q1"): -1, ("c1", "w1"): -1, ("c1", "t1"): -1,                 # DAL pass D stronger: TB passing -1
                   ("c2", "r1"): -1,                                                    # DAL run D stronger: TB RBs -1
                   ("c3", "q2"): -1, ("c3", "r2"): -1,                                  # DAL line weaker: DAL QB / RB -1
                   ("c4", "q1"): 1, ("c4", "w1"): 1, ("c4", "t1"): 1,                   # DAL rush weaker: TB passing +1
                   ("c9", "r1"): 0}                                                     # unclear: derived 0, not in the mean
    assert c["count_only"] == 2 and c["team_unknown"] == 1 and c["team_not_on_slate"] == 1 and c["unit_unknown"] == 1
    assert c["records"] == 10 and c["derived_pairs"] == 10


def test_team_change_stays_out_of_the_groups_and_the_placebo():
    """A team_change record about a frame player (a traded WR) neither joins nor lands in the direction-0 placebo."""
    U = {"pop": TC_POP, "cutoff": CUT, "skill_on_frame": 7, "team_opp": TC_OPP}
    recs = [_tc("k1", "receiving_corps", 1, team="Cowboys", player="Dal Wr"), _rec("k2", "Tb Wr", team="Buccaneers", d=1)]
    cen = R.week_census(5, U, recs)
    assert [r["record_id"] for r, _ in cen["pairs"]] == ["k2"] and cen["players"]["zero_only"] == 0
    assert cen["team_change"]["records"] == 1 and cen["team_change"]["count_only"] == 1
    assert cen["records"]["kept"] == 2


def test_the_derived_line_in_the_descriptives():
    rp = pd.Series([2.0, -1.0, 0.5, 3.0, -2.0, 1.0, 0.0], index=TC_POP.index)
    der, _ = R.derive_team_change([_tc("d1", "pass_defense", 1), _tc("d2", "offensive_line", 1)], TC_POP, TC_OPP)
    desc = R.week_descriptive([], {}, rp, None, derived=der)
    t = desc["team_change_derived"]
    want = np.mean([-2.0, 1.0, -0.5, -2.0, 1.0])            # TB QB / WR / TE at -1, DAL QB / RB at +1
    assert t["pairs"] == 5 and math.isclose(t["mean_signed_r"], want) and t["by_unit"] == {"pass_defense": 3, "offensive_line": 2}


def test_a_frame_without_opponents_maps_no_team_change():
    der, c = R.derive_team_change([_tc("n1", "pass_defense", 1), _tc("n2", "run_defense", -1)], TC_POP, {})
    assert der == [] and c == {"records": 2, "no_opponent_map": 2}
