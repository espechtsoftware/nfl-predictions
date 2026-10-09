"""scripts/off_top_four.py (study row 72's Monday line): the census's game rank on the union's own pool, the QB / stack
classification, the top-percent cutoffs, the input refusals, and one end-to-end week on synthetic data (the money gate's
real place / Ladder / lineup_points / contest_class / canon; its file and BigQuery reads faked)."""
import csv
import hashlib
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
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


OTT = _load("off_top_four")
MS = _load("moneygate_score")
P3 = _load("p3_score")

# ---------------------------------------------------------------- the synthetic slate: 7 games, 14 teams (A..N)
GAMES = {"G1": ("A", "B", 50.0), "G2": ("C", "D", 49.0), "G3": ("E", "F", 48.5), "G4": ("G", "H", 48.5),
         "G5": ("I", "J", 45.0), "G6": ("K", "L", 44.0), "G7": ("M", "N", 52.0)}
SLOTS = ("QB", "RB", "WR", "WR2", "TE", "DST")


def frame() -> pd.DataFrame:
    rows, k = [], 1000
    for g, (h, a, tot) in GAMES.items():
        for team, opp in ((h, a), (a, h)):
            for s in SLOTS:
                k += 1
                rows.append({"id": f"{team}-{s}", "dk_player_id": k, "display_name": f"{team} {s}", "pos": "WR" if s == "WR2" else s,
                             "team": team, "opp": opp, "game_id": g, "game_total": tot, "mean_projection": 15.0})
    for team in ("J", "D"):                                        # two QBs sharing one display name: never identified
        k += 1
        g = next(g for g, (h, a, _) in GAMES.items() if team in (h, a))
        rows.append({"id": f"{team}-DUP", "dk_player_id": k, "display_name": "Dup QB", "pos": "QB", "team": team,
                     "opp": "?", "game_id": g, "game_total": GAMES[g][2], "mean_projection": 6.0})
    f = pd.DataFrame(rows)
    f.loc[f.id == "K-QB", "mean_projection"] = 0.5                 # ours below the floor; FP lifts it (in the pool)
    return f


PROJ = pd.DataFrame({"id": ["K-QB", "L-QB", "N-QB", "A-WR"], "fp": [12.0, 0.5, 0.2, 20.0]})   # L, N dropped by FP
UNAVAILABLE = {"M-QB"}                                          # so G7 (the top total, 52) has no pool QB


def test_union_projection_takes_fp_where_the_file_holds_the_id():
    p = OTT.union_projection(frame(), PROJ)
    assert p["K-QB"] == 12.0 and p["L-QB"] == 0.5 and p["A-WR"] == 20.0 and p["A-QB"] == 15.0
    assert OTT.union_projection(frame(), None)["K-QB"] == 0.5


def test_pool_qbs_and_the_census_game_rank():
    fr = frame()
    pqb = OTT.pool_qbs(fr, OTT.union_projection(fr, PROJ), 1.0, UNAVAILABLE)
    assert "K-QB" in pqb and not {"L-QB", "N-QB", "M-QB"} & pqb and {"J-DUP", "D-DUP"} <= pqb and len(pqb) == 13
    g = OTT.game_ranks(fr, pqb)
    assert list(g.game_id) == ["G1", "G2", "G3", "G4", "G5", "G6"]            # G7 unranked; the 48.5 tie by game_id
    assert list(g["rank"]) == [1, 2, 3, 4, 5, 6]
    # the frame's own projection would have kept N-QB and ranked G7 first: the union's projection decides
    assert OTT.game_ranks(fr, OTT.pool_qbs(fr, OTT.union_projection(fr, None), 1.0, UNAVAILABLE)).game_id.iloc[0] == "G7"


@pytest.mark.parametrize("bad, msg", [({"game_total": np.nan}, "missing"), ({"game_total": 47.0}, "47.0")])
def test_game_rank_refuses_a_missing_or_second_total(bad, msg):
    fr = frame()
    if msg == "missing":
        fr.loc[fr.game_id == "G2", "game_total"] = np.nan
    else:
        fr.loc[(fr.game_id == "G2") & (fr.pos == "DST"), "game_total"] = 47.0
    with pytest.raises(ValueError, match=f"game G2 has game_total .*{msg}"):
        OTT.game_ranks(fr, set(fr.id[fr.pos == "QB"]))


def names(qb_team: str, stacked: bool = True, qb_name: str | None = None) -> tuple[str, ...]:
    """A 9-name lineup: the QB, (stacked) his WR + TE or (not) his RB + the opponent's WR / TE, and fillers from teams
    outside his game."""
    g = next(g for g, (h, a, _) in GAMES.items() if qb_team in (h, a))
    opp = GAMES[g][1] if GAMES[g][0] == qb_team else GAMES[g][0]
    fill = [t for t in "ABCDEFGHIJKL" if t not in (qb_team, opp)]
    core = [qb_name or f"{qb_team} QB"] + ([f"{qb_team} WR", f"{qb_team} TE", f"{opp} WR"] if stacked
                                          else [f"{qb_team} RB", f"{opp} WR", f"{opp} TE"])
    return tuple(core + [f"{fill[0]} RB", f"{fill[1]} RB", f"{fill[2]} WR2", f"{fill[3]} WR2", f"{fill[4]} DST"])


def test_classify_qb_stack_and_not_identified():
    idx = OTT.index_by_name(frame(), MS.canon)
    assert OTT.classify(names("I"), idx) == ("G5", True, "ok")
    assert OTT.classify(names("I", stacked=False), idx) == ("G5", False, "ok")          # RB + the opponent's WR / TE only
    assert OTT.classify(names("I", qb_name="Dup QB"), idx) == (None, False, "not identified")   # one name, two QBs
    two_qbs = names("I")[:-1] + ("A QB",)
    assert OTT.classify(two_qbs, idx)[2] == "not identified"
    assert OTT.classify(tuple(n for n in names("I") if n != "I QB") + ("A RB",), idx)[2] == "not identified"


def test_top_cut_includes_draftkings_ties():
    assert OTT.top_cut(1000, 0.01) == 10 and OTT.top_cut(1000, 0.001) == 1 and OTT.top_cut(50, 0.001) == 1
    assert OTT.top_cut(1001, 0.01) == 11
    fr = frame(); idx = OTT.index_by_name(fr, MS.canon)
    ranks = {g: r for g, r in zip(*[OTT.game_ranks(fr, set(fr.id[fr.pos == "QB"]) - UNAVAILABLE - {"N-QB"})[c] for c in ("game_id", "rank")])}
    field = pd.DataFrame({"rank": [1, 2, 10, 10, 12], "names": [names("I"), names("A"), names("K"), names("K", False), names("A")]})
    s = OTT.field_shares(field, 1000, ranks, idx, 5)
    # ranks 1 (I, G5, stacked), 2 (A, G1), 10 and 10 (K, G6: stacked / not): both rank-10 ties are in
    assert s["top 1%"]["entries"] == 4 and s["top 1%"]["off"] == 0.75 and s["top 1%"]["off_stack"] == 0.5
    assert s["top 0.1%"]["entries"] == 1 and s["top 0.1%"]["off_stack"] == 1.0


# ---------------------------------------------------------------- the input checks
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_inputs(tmp, body_names=None, proj=True):
    """T-70 dir, union dir (book.csv, receipt.json, proj_source.csv) and the plan; returns their paths."""
    fr = frame()
    t70 = tmp / "t70"; t70.mkdir(parents=True); fr.to_parquet(t70 / "frame.parquet")
    dk = dict(zip(fr.display_name, fr.dk_player_id.astype(str)))
    union = tmp / "union"; union.mkdir()
    body_names = body_names or [names("A"), names("C"), names("I"), names("K"), names("E"), names("G")]
    with (union / "book.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        for nm in body_names:
            w.writerow([dk[n] for n in nm])
    u = {"input_sha256": {"t70_frame": sha(t70 / "frame.parquet")}, "min_proj": 1.0,
         "counts": {"unavailable_players": sorted(UNAVAILABLE)}}
    if proj:
        PROJ.to_csv(union / "proj_source.csv", index=False)
        u["proj_source"] = {"sha256": sha(union / "proj_source.csv")}
    (union / "receipt.json").write_text(json.dumps({"config": {"union": u}}))
    plan = tmp / "plan.json"
    plan.write_text(json.dumps([{"contest_id": "C1", "big": True, "seats": 5}, {"contest_id": "C2", "big": True, "seats": 2},
                                {"contest_id": "C3", "big": False, "seats": 0}]))
    return t70, union, plan


def test_check_inputs_passes_and_reads_the_union_pool(tmp_path):
    t70, union, plan = write_inputs(tmp_path)
    got = OTT.check_inputs(t70, union, plan, t70 / "frame.parquet")
    assert got["min_proj"] == 1.0 and got["unavailable"] == UNAVAILABLE and got["proj_csv"] is not None


@pytest.mark.parametrize("breakage, msg", [
    ("frame", "not the money gate's week frame"),
    ("union_frame", "built on another T-70 frame"),
    ("proj_missing", "proj_source.csv is missing"),
    ("proj_changed", "not the projection file the union receipt names"),
    ("min_proj", "has no min_proj"),
    ("book", "book.csv is missing"),
])
def test_check_inputs_refusals(tmp_path, breakage, msg):
    t70, union, plan = write_inputs(tmp_path)
    cfg_frame = t70 / "frame.parquet"
    rec = json.loads((union / "receipt.json").read_text())
    if breakage == "frame":
        other = tmp_path / "gate"; other.mkdir(); frame().head(5).to_parquet(other / "frame.parquet"); cfg_frame = other / "frame.parquet"
    elif breakage == "union_frame":
        rec["config"]["union"]["input_sha256"]["t70_frame"] = "0" * 64
    elif breakage == "proj_missing":
        (union / "proj_source.csv").unlink()
    elif breakage == "proj_changed":
        (union / "proj_source.csv").write_text("id,fp\nK-QB,13.0\n")
    elif breakage == "min_proj":
        del rec["config"]["union"]["min_proj"]
    elif breakage == "book":
        (union / "book.csv").unlink()
    (union / "receipt.json").write_text(json.dumps(rec))
    with pytest.raises(SystemExit, match=f"OFF-TOP-FOUR REFUSED: .*{msg}"):
        OTT.check_inputs(t70, union, plan, cfg_frame)


def test_book_rows_must_be_nine_frame_players_with_one_qb():
    fr = frame()
    by_dk = {str(k): (p, t, g) for k, p, t, g in zip(fr.dk_player_id, fr.pos, fr.team, fr.game_id)}
    dk = dict(zip(fr.display_name, fr.dk_player_id.astype(str)))
    assert OTT.book_qb_games([[dk[n] for n in names("I")]], by_dk) == ["G5"]
    with pytest.raises(SystemExit, match="has 8 ids"):
        OTT.book_qb_games([[dk[n] for n in names("I")[:8]]], by_dk)
    with pytest.raises(SystemExit, match="holds 2 QBs"):
        OTT.book_qb_games([[dk[n] for n in names("I")[:-1]] + [dk["A QB"]]], by_dk)


def test_book_stacks_reads_each_row():
    fr = frame()
    by_dk = {str(k): (p, t, g) for k, p, t, g in zip(fr.dk_player_id, fr.pos, fr.team, fr.game_id)}
    dk = dict(zip(fr.display_name, fr.dk_player_id.astype(str)))
    body = [[dk[n] for n in names("I")], [dk[n] for n in names("I", stacked=False)], [dk[n] for n in names("A")]]
    assert OTT.book_stacks(body, by_dk) == [True, False, True]      # the QB alone (his RB + the opponent's WR / TE): False


# ---------------------------------------------------------------- one week end to end (fakes for the gate's IO only)
def milly_field():
    """C1: 1,000 entries. Ours: o1 (book row 1, rank 3) and o2 (book row 3, rank 400). The 998 others: the top 1%
    (ranks <= 10, one tie at 10) holds 6 off-top-four lineups (4 stacked) and 4 top-four; the rest 200 off-top-four (100
    stacked), 5 unidentifiable, the remainder top-four."""
    ranks = [r for r in range(1, 1001) if r not in (3, 400)]
    ranks[ranks.index(11)] = 10                                     # a DraftKings tie at the top-1% cutoff
    lus = []
    top = [names("I"), names("K"), names("J"), names("L"), names("I", False), names("K", False),
           names("A"), names("C"), names("E"), names("G")]
    for r in ranks:
        if r <= 10:
            lus.append(top.pop(0))
    rest = len(ranks) - len(lus)
    for i in range(rest):
        if i < 100:
            lus.append(names("I"))
        elif i < 200:
            lus.append(names("K", False))
        elif i < 205:
            lus.append(names("J", qb_name="Dup QB"))
        else:
            lus.append(names("C"))
    others = pd.DataFrame({"contest_id": "C1", "entry_id": [f"x{k}" for k in range(len(ranks))], "rank": ranks,
                           "points": [30000 - 10 * r for r in ranks], "names": lus})
    ours = pd.DataFrame({"contest_id": "C1", "entry_id": ["o1", "o2"], "rank": [3, 400], "points": [18000, 12000],
                         "names": [names("A"), names("I")]})
    return pd.concat([others, ours], ignore_index=True)


def fake_week(tmp):
    fr = frame()
    c2 = pd.DataFrame({"contest_id": "C2", "entry_id": [f"y{k}" for k in range(50)], "rank": range(1, 51),
                       "points": [12000 - 50 * k for k in range(50)], "names": [names("C")] * 50})
    edited = names("E")[:-1] + ("A DST",)
    c3 = pd.DataFrame({"contest_id": "C3", "entry_id": ["o3", "o4", "z1"], "rank": [1, 2, 3], "points": [9000, 8000, 7000],
                       "names": [names("C"), edited, names("G")]})
    field = pd.concat([milly_field(), c2, c3], ignore_index=True)
    ours = {"o1", "o2", "o3", "o4"}

    def others_sorted(cid):
        f = field[(field.contest_id == cid) & ~field.entry_id.isin(ours)]
        return np.sort(f.points.to_numpy(np.int64))
    lad = {"payoutSummary": [{"minPosition": 1, "maxPosition": 2, "tierPayoutDescriptions": {"Ticket": "seat"},
                              "payoutDescriptions": [{"value": 555.0, "quantity": 1}]}]}
    return types.SimpleNamespace(
        contests=[{"contest_id": "C1", "name": "NFL $1M Millionaire", "entries": 2},
                  {"contest_id": "C2", "name": "NFL $555 Satellite", "entries": 1},
                  {"contest_id": "C3", "name": "NFL Small GPP", "entries": 2}],
        details={"C1": {"name": "NFL Millionaire [$1M to 1st]"}, "C2": {"name": "NFL $555 Satellite", **lad},
                 "C3": {"name": "NFL Small GPP"}},
        field=field, ours=ours, fpts={n: 1000 for n in fr.display_name.map(MS.canon)},
        name_of={str(k): MS.canon(n) for k, n in zip(fr.dk_player_id, fr.display_name)}, others_sorted=others_sorted)


def install_fakes(monkeypatch, tmp, t70, weeks=(5,)):
    data = tmp / "mgdata"; data.mkdir(exist_ok=True)
    (data / "w5_receipt.json").write_text(json.dumps({"week": 5, "field_rows": 1}))
    (data / "reconcile_receipt.json").write_text(json.dumps({"weeks": list(weeks)}))
    W = fake_week(tmp)
    M = types.SimpleNamespace(receipt_path=lambda: data / "reconcile_receipt.json", require_reconcile=lambda w: None,
                              load_config=lambda: {"weeks": {"5": {"t70_run": str(t70)}}}, load_week=lambda cfg, w: W,
                              canon=MS.canon, lineup_points=MS.lineup_points, place=MS.place, Ladder=MS.Ladder,
                              contest_class=MS.contest_class, sha256=MS.sha256, SCORER=MS.SCORER, data_dir=lambda: data)

    def read_book(p):
        rows = list(csv.reader(open(p, newline="")))
        return rows[0], rows[1:]

    deal = {"C1": [0, 2], "C2": [3], "C3": [1, 4]}

    def layout_book(contests, book, stage):
        _, body = read_book(book)
        Path(stage).mkdir(parents=True, exist_ok=True)
        return {c: {"rows": r, "lineups": [body[i] for i in r]} for c, r in deal.items()}
    B = types.SimpleNamespace(read_book=read_book, layout_book=layout_book)
    monkeypatch.setattr(OTT, "_load", lambda name: {"moneygate_score": M, "moneygate_build": B, "p3_score": P3}[name])
    return W


def run(tmp, t70, union, plan, extra=()):
    return OTT.main(["--season", "2026", "--week", "5", "--t70-run", str(t70), "--union", str(union), "--plan", str(plan),
                     "--out-dir", str(tmp / "private"), "--summary", str(tmp / "summary.txt"), *extra])


def test_one_week_end_to_end(tmp_path, monkeypatch, capsys):
    t70, union, plan = write_inputs(tmp_path)
    install_fakes(monkeypatch, tmp_path, t70)
    assert run(tmp_path, t70, union, plan) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].startswith("== OFF-TOP-FOUR STACKS 2026 W5 -- descriptive, gates nothing")
    assert "over the 6 with a pool QB (13 pool QBs: the union's projections >= 1, minus 1 unavailable; ties: game_id); top 4: 50 / 49 / 48.5 / 48.5" in out
    assert "BOOK (as built, dealt by the head layout): 2 of 6 rows stack a QB from a game ranked 5+; 2 of them dealt into big contests (2 of 3 big entries)" in out
    assert ("RESULTS (our real entries in big contests, each by its own QB): off-top-4 2 entries / 2 lineups, mean 105.0, best 120.0 points, "
            "big seats 0 | top-4 1 entries / 1 lineups, mean 180.0, best 180.0 points, big seats 1 | QB not identified 0; "
            "our entries not a book row: 1 of 4") in out
    assert "NFL Millionaire [$1M to 1st] (seats 5, field 1,000): off-top-4 1, best rank 400 (top 40.00%), seats 0 | top-4 1, best rank 3 (top 0.30%), seats 1" in out
    assert ("NFL $555 Satellite (seats 2, field 51): off-top-4 1, best rank 51 (top 100.00%), seats 0 | top-4 0, best rank -, seats 0   "
            "(the book as dealt: none of our entries in the week data)") in out
    assert ("MILLIONAIRE C1 (998 other entries; ours removed): QB from a game ranked 5+: field 20.7% | top 1% 60.0% | top 0.1% 100.0%;  "
            "as a stack: field 10.5% | top 1% 40.0% | top 0.1% 100.0%;  QB not identified: 5") in out
    assert (tmp_path / "summary.txt").read_text() == out                     # the summary gets exactly the printed text
    rows = pd.read_parquet(tmp_path / "private" / "ott-2026-w05.parquet")
    assert (rows.source == "book").sum() == 6 and (rows.source == "entry").sum() == 3
    side = json.loads((tmp_path / "private" / "ott-2026-w05.json").read_text())
    assert side["pool_qbs"] == 13 and side["not_in_book"] == 1 and side["rows_sha256"] == sha(tmp_path / "private" / "ott-2026-w05.parquet")
    assert "o1" not in out and "x1" not in out and "A QB" not in out                 # aggregates only on screen


def test_end_to_end_refusals(tmp_path, monkeypatch):
    t70, union, plan = write_inputs(tmp_path)
    install_fakes(monkeypatch, tmp_path, t70, weeks=(4,))
    with pytest.raises(SystemExit, match="does not cover week 5"):
        run(tmp_path, t70, union, plan)
    install_fakes(monkeypatch, tmp_path, t70)
    plan.write_text(json.dumps([{"contest_id": "C1", "big": True, "seats": 5}]))
    with pytest.raises(SystemExit, match=r"lacks contests \['C2', 'C3'\]"):
        run(tmp_path, t70, union, plan)
    with pytest.raises(SystemExit, match="--min-rank 1"):
        run(tmp_path, t70, union, plan, ["--min-rank", "1"])
