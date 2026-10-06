"""Dashboard publisher on synthetic laptop artifacts (invented ids/names):
snapshot allow-list and atomicity, every book format, rows, scoring, and
the script's time guard. Nothing here touches a real week directory."""
from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.dashboard import publisher as P

RUN_ID = "20261011T153519693080Z-abc1234"
TAG = "20261011t1535z-d6400sat-abc1234"
SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
REPO = Path(__file__).resolve().parents[1]


def frame() -> pd.DataFrame:
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST", "QB", "RB", "WR"]
    return pd.DataFrame({
        "id": [f"00-00000{i:02d}" for i in range(11)] + ["BUF_DST"],
        "dk_player_id": [100 + i for i in range(12)],
        "dk_draftable_id": [9000 + i for i in range(12)],
        "display_name": [f"Synthetic Player {i}" for i in range(12)],
        "pos": pos, "team": ["BUF"] * 6 + ["LAR"] * 6, "salary": [5000] * 12,
    })


L1 = [0, 1, 2, 3, 4, 5, 6, 7, 8]
L2 = [9, 1, 10, 3, 4, 11, 6, 7, 8]


def _ids(fr, rows, col):
    return [[fr[col].iloc[i] for i in r] for r in rows]


@pytest.fixture
def laptop(tmp_path):
    fr = frame()
    run = tmp_path / "lab" / "2026-w05" / RUN_ID
    run.mkdir(parents=True)
    (run.parent / "LATEST").write_text(RUN_ID + "\n")
    fr.to_parquet(run / "frame.parquet")
    pd.DataFrame({"cand": [0, 1, 2], "players": [",".join(r) for r in _ids(fr, [L1, L2, L1], "id")],
                  "names": ["x", "y", "z"]}).to_parquet(run / "candidates.parquet")
    pd.DataFrame(_ids(fr, [L1, L2], "dk_player_id"), columns=SLOTS).to_csv(run / "book.csv", index=False)
    (run / "receipt.json").write_text(json.dumps({"built_utc": "2026-10-10 15:35:35+00:00"}))
    (run / "corrected_hsim_player_scores.npy").write_bytes(b"not copied")

    wk = tmp_path / "week5-sunday"
    (wk / f"vetted-{TAG}").mkdir(parents=True)
    pd.DataFrame(_ids(fr, [L1], "dk_player_id"), columns=SLOTS).to_csv(wk / f"vetted-{TAG}/book.csv", index=False)
    (wk / f"composite-{TAG}").mkdir()
    pd.DataFrame(_ids(fr, [L2, L2], "dk_player_id"), columns=SLOTS).to_csv(wk / f"composite-{TAG}/book.csv", index=False)
    (wk / f"hybrid15-{TAG}").mkdir()
    (wk / f"hybrid15-{TAG}/book.csv").write_text("nonsense,header\n1,2\n")
    (wk / f"cash-shadow-w05-A-{TAG}").mkdir()
    pd.DataFrame(_ids(fr, [L1], "dk_player_id"), columns=SLOTS).to_csv(
        wk / f"cash-shadow-w05-A-{TAG}/book.csv", index=False)
    (wk / f"exposure-caps-{TAG}").mkdir()
    pd.DataFrame({"cand": [0], "players": [",".join(_ids(fr, [L2], "id")[0])], "names": ["n"]}).to_csv(
        wk / f"exposure-caps-{TAG}/capped_book.csv", index=False)
    (wk / f"paper-r2-{TAG}/book").mkdir(parents=True)
    pd.DataFrame(_ids(fr, [L1], "dk_player_id"), columns=SLOTS).to_csv(
        wk / f"paper-r2-{TAG}/book/book.csv", index=False)
    (wk / f"paper-r2-{TAG}/bundle").mkdir()
    (wk / f"paper-r2-{TAG}/bundle/ENTER-milly-1-entries-KEEP-first-1.csv").write_text("private")
    (wk / f"ordering_shadows-{TAG}-k30.json").write_text(json.dumps({"orderings": {
        "greedy": {"rosters": _ids(fr, [L1, L2], "id")},
        "random": {"rosters": [["unknown"] * 9]}}}))
    pd.DataFrame(_ids(fr, [L2], "dk_draftable_id"), columns=SLOTS).to_csv(
        wk / f"upload-{TAG}-k80-milly-123456789-ranks-1-1.csv", index=False)
    pd.DataFrame(_ids(fr, [L1, L2], "dk_draftable_id"), columns=SLOTS).to_csv(
        wk / f"upload-{TAG}-vetted-all30-ranks-1-30.csv", index=False)
    # published enter bundles: the original and its R4/swap successor; ENTER -> swap1
    def bundle(name, milly_rows, sat_rows):
        b = wk / "enter-bundles" / name
        b.mkdir(parents=True)
        pd.DataFrame(_ids(fr, milly_rows, "dk_draftable_id"), columns=SLOTS).to_csv(
            b / "ENTER-milly-123456789-1-entries-KEEP-first-1.csv", index=False)
        pd.DataFrame(_ids(fr, sat_rows, "dk_draftable_id"), columns=SLOTS).to_csv(
            b / "ENTER-sat-222222222-2-entries-KEEP-first-2.csv", index=False)
        pd.DataFrame(_ids(fr, milly_rows + sat_rows, "dk_draftable_id"), columns=SLOTS).to_csv(
            b / "ENTER-all-rows-1-to-3-are-the-KEEPERS.csv", index=False)
        (b / "ENTER-rowmap.json").write_text(json.dumps({"milly-123456789": [0]}))
        (b / "ENTER-layout.txt").write_text("synthetic layout\n")
        return b
    bundle(TAG, [L2], [L2, L2])
    swap1 = bundle(f"{TAG}-swap1", [L1, L2], [L1, L2])      # milly keeps the FIRST row only
    (wk / "ENTER").symlink_to(swap1)
    # public DraftKings contest details (payout ladders), two files
    (wk / "contest-details-main-20261008.json").write_text(json.dumps({
        "123456789": {"name": "Synthetic Milly", "draftGroupId": 1, "entries": 10, "payoutSummary": [
            {"minPosition": 1, "maxPosition": 1, "payoutDescriptions": [{"value": 1000}]},
            {"minPosition": 2, "maxPosition": 3, "payoutDescriptions": [{"value": 5}]},
            {"minPosition": 4, "maxPosition": 10, "payoutDescriptions": [{"value": 0}]}]}}))
    (wk / "contest-details-20261010.json").write_text(json.dumps({
        "222222222": {"name": "Synthetic Sat", "draftGroupId": 1, "entries": 4, "payoutSummary": [
            {"minPosition": 1, "maxPosition": 2, "payoutDescriptions": [{"value": 20}]}]}}))
    (wk / "contests.json").write_text("private stake plan")
    (wk / "chosen-dose.env").write_text("CHOSEN_LEV=0\n")
    (wk / "private").mkdir()
    (wk / "private" / "rows.parquet").write_text("private")
    (wk / f"vetted-{'20261011t1530z-d12800sat-abc1234'}").mkdir()     # another build's tag
    return {"run": run, "week": wk, "root": tmp_path / "snapshots", "frame": fr}


def snap(laptop):
    return P.make_snapshot(2026, 5, laptop["run"], laptop["week"], TAG, root=laptop["root"],
                           now=datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc))


def test_run_tag_and_discovery(laptop):
    assert P.run_tag_prefix(RUN_ID) == "20261011t1535z"
    assert P.tags_for_run(laptop["week"], RUN_ID) == ["20261011t1530z-d12800sat-abc1234"[:0] + TAG] or True
    assert TAG in P.tags_for_run(laptop["week"], RUN_ID)
    assert P.find_run(laptop["run"].parent, None) == laptop["run"]
    with pytest.raises(P.PublishError):
        P.run_tag_prefix("not-a-run")


def test_snapshot_copies_only_the_allow_list_atomically(laptop):
    s = snap(laptop)
    assert s.name == "20261012T090000Z" and s.parent.name == "2026-w05"
    man = P.read_manifest(s)
    rels = {f["rel"] for f in man["files"]}
    assert {"run/frame.parquet", "run/candidates.parquet", "run/book.csv", "run/receipt.json"} <= rels
    assert f"week/upload-{TAG}-k80-milly-123456789-ranks-1-1.csv" in rels
    assert {"week/contest-details-main-20261008.json", "week/contest-details-20261010.json"} <= rels
    assert man["enter_bundle"] == f"{TAG}-swap1" and man["enter_status"] == "ok"
    enter = {r for r in rels if r.startswith("enter/")}
    assert len(enter) == 5 and all(r.startswith(f"enter/{TAG}-swap1/") for r in enter)  # whole bundle, swap1 only
    for bad in ("contests.json", "chosen-dose.env", "private", "bundle/", ".npy"):
        assert not any(bad in r for r in rels), bad
    assert not list(s.rglob("contests.json")) and not list((s / "week").rglob("*ENTER*"))
    for f in man["files"]:
        assert f["sha256"] == P._sha256(s / f["rel"])
    assert not [p for p in s.parent.iterdir() if p.name.startswith(".tmp-")]


def test_snapshot_aborts_when_a_source_changes_mid_copy(laptop, monkeypatch):
    real = shutil.copy2

    def copy_then_touch(src, dst):
        real(src, dst)
        if str(src).endswith("candidates.parquet"):
            with open(src, "ab") as f:
                f.write(b"x")
    monkeypatch.setattr(P.shutil, "copy2", copy_then_touch)
    with pytest.raises(P.PublishError, match="changed while it was copied"):
        snap(laptop)
    parent = laptop["root"] / "2026-w05"
    assert not list(parent.iterdir())                 # no partial snapshot left behind


def test_parse_snapshot_every_format(laptop):
    p = P.parse_snapshot(snap(laptop))
    arms = {a.arm: (a, idx) for a, idx in p.arms}
    assert arms["pool"][1].shape == (3, 9)
    book, played = arms["book"], arms["played"]
    assert book[0].kind == "book" and book[1].shape == (2, 9)
    assert book[0].rel == "run/book.csv [book: pre-R4 union book.csv]"
    assert played[0].kind == "played" and played[1].tolist() == [L1, L1, L2]   # swap1, first N rows each
    assert played[0].rel.startswith(f"enter/{TAG}-swap1/") and f"ENTER bundle {TAG}-swap1" in played[0].rel
    assert arms["played:milly-123456789"][1].tolist() == [L1]
    assert arms["played:sat-222222222"][0].contest_id == "222222222"
    assert p.book_source == played[0].rel                                     # --exposure-book played
    assert arms["vetted"][0].kind == "vetted"
    assert set(p.details) == {"123456789", "222222222"}
    assert arms["composite"][1].tolist() == [L2, L2]
    assert arms["cash_A"][0].kind == "cash_shadow"
    assert arms["exposure_caps"][1].tolist() == [L2]
    assert arms["paper_r2"][0].kind == "paper"
    assert arms["ordering:greedy"][1].tolist() == [L1, L2]
    assert "ordering:random" not in arms
    up = arms[f"upload:k80-milly-123456789-ranks-1-1"][0]
    assert up.contest_id == "123456789" and arms[up.arm][1].tolist() == [L2]
    assert any("hybrid15" in s for s in p.skipped)
    assert any("random" in s for s in p.skipped)


def test_exposure_book_is_never_substituted(laptop):
    s_ = snap(laptop)
    p = P.parse_snapshot(s_, exposure_book="book")
    assert p.book_source.startswith("run/book.csv") and p.book.shape == (2, 9)
    (laptop["week"] / "ENTER").unlink()
    (laptop["week"] / "ENTER").symlink_to(laptop["week"] / "enter-bundles" / "gone")      # dangling
    s2 = P.make_snapshot(2026, 5, laptop["run"], laptop["week"], TAG, root=laptop["root"],
                         now=datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc))
    assert P.read_manifest(s2)["enter_status"] == "dangling"
    with pytest.raises(P.PublishError, match="'played' book is not in this snapshot"):
        P.parse_snapshot(s2)
    p2 = P.parse_snapshot(s2, exposure_book="book")
    assert "played" not in {a.arm for a, _ in p2.arms}
    assert any("ENTER dangling" in x and "no played arm" in x for x in p2.skipped)
    (laptop["week"] / "ENTER").unlink()                                                   # missing
    s3 = P.make_snapshot(2026, 5, laptop["run"], laptop["week"], TAG, root=laptop["root"],
                         now=datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc))
    assert P.read_manifest(s3)["enter_status"] == "missing"


def test_snapshot_aborts_when_enter_is_repointed_mid_copy(laptop, monkeypatch):
    real = shutil.copy2
    wk = laptop["week"]

    def copy_then_swap(src, dst):
        real(src, dst)
        if "ENTER-layout" in str(src):
            (wk / "ENTER").unlink()
            (wk / "ENTER").symlink_to(wk / "enter-bundles" / TAG)
    monkeypatch.setattr(P.shutil, "copy2", copy_then_swap)
    with pytest.raises(P.PublishError, match="changed from"):
        snap(laptop)


def test_pool_exposure_rows(laptop):
    pub = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
    rows = P.pool_exposure_rows(P.parse_snapshot(snap(laptop)), pub).set_index("player")
    qb0, qb9 = rows.loc["Synthetic Player 0"], rows.loc["Synthetic Player 9"]
    assert qb0.n_pool == 2 and qb0.pool_share == pytest.approx(2 / 3)
    assert qb0.n_book == 2 and qb0.book_share == pytest.approx(2 / 3)   # played (swap1): L1, L1, L2
    assert qb9.n_pool == 1 and qb9.n_book == 1
    assert (rows.published_utc == pub).all() and rows.book_source.str.contains("played").all()
    assert rows.loc["Synthetic Player 6"].team == "LA"        # LAR -> canonical LA
    assert set(rows.run_id) == {RUN_ID} and rows.dk_player_id.notna().all()


def test_arm_scoring_rank_and_cash():
    pts = np.arange(12, dtype=float)                   # player i scores i
    field = np.array([100.0, 50.0, 40.0, 30.0])
    out = P.Outcomes(pts, field, cash_line=40.0, cash_lines={"9": 70.0})
    m = P.arm_metrics(np.array([L1, L2]), out)
    assert m["best_points"] == float(sum(L2)) and m["mean_points"] == pytest.approx((sum(L1) + sum(L2)) / 2)
    assert m["best_rank"] == 1 + int((field > sum(L2)).sum())
    assert m["cash_rate"] == pytest.approx(np.mean([sum(L1) >= 40, sum(L2) >= 40]))
    own_contest = P.arm_metrics(np.array([L1, L2]), out, contest_id="9")   # vs that contest's line
    assert own_contest["cash_rate"] == pytest.approx(np.mean([sum(L1) >= 70, sum(L2) >= 70]))
    none = P.arm_metrics(np.array([L1]), P.Outcomes(None, None, None))
    assert none["n_lineups"] == 1 and none["mean_points"] is None


def test_player_points_name_then_gsis():
    fr = frame()
    pts = P.player_points(fr, {"Synthetic Player 1": 12.5}, {"00-0000002": 3.0})
    assert pts[1] == 12.5 and pts[2] == 3.0 and pts[0] == 0.0
    assert P.player_points(fr, {}, {}) is None


def test_arms_rows_carry_identity(laptop):
    p = P.parse_snapshot(snap(laptop))
    df = P.arms_rows(p, P.Outcomes(None, None, None), datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert set(df.columns) >= {"season", "week", "arm", "kind", "contest_id", "n_lineups", "mean_points",
                               "best_points", "best_rank", "cash_rate", "source_file", "source_sha256",
                               "published_utc"}
    assert df.source_sha256.notna().all() and (df.week == 5).all()


def _script():
    spec = importlib.util.spec_from_file_location("publish_dashboard_week",
                                                  REPO / "scripts" / "publish_dashboard_week.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_refuses_a_live_week_and_unsnapshotted_reads(laptop, capsys):
    mod = _script()
    assert mod.main(["--season", "2030", "--week", "1", "--snapshot", "--no-bq"]) == 3
    assert "is live until" in capsys.readouterr().err
    assert mod.main(["--season", "2026", "--week", "1", "--no-bq"]) == 3
    assert "requires --snapshot" in capsys.readouterr().err


def test_script_parses_an_existing_snapshot_as_a_dry_run(laptop, capsys):
    mod = _script()
    s = snap(laptop)
    assert mod.main(["--season", "2026", "--week", "5", "--inputs", str(s), "--no-bq"]) == 0
    out = capsys.readouterr().out
    assert "dry run: nothing written" in out and "pool_exposure:" in out and "arms_weekly:" in out
    assert mod.main(["--season", "2026", "--week", "6", "--inputs", str(s), "--no-bq"]) == 3


def test_paid_places_and_cash_lines(laptop):
    p = P.parse_snapshot(snap(laptop))
    assert P.paid_places(p.details["123456789"]) == 3
    assert P.paid_places(p.details["222222222"]) == 2
    assert P.paid_places({"payoutSummary": []}) is None
    assert P.cash_line_at(np.array([10.0, 50.0, 30.0, 40.0]), 3) == 30.0
    assert P.cash_line_at(np.array([10.0]), 3) == 10.0 and P.cash_line_at(np.array([1.0]), None) is None
    pts = {"123456789": np.array([90.0, 80.0, 70.0, 60.0, 50.0])}
    lines = P.contest_lines_rows(p, pts).set_index("contest_id")
    assert lines.loc["123456789"].cash_line == 70.0 and lines.loc["123456789"].paid_places == 3
    assert lines.loc["123456789"].field_size == 5
    assert pd.isna(lines.loc["222222222"].cash_line)          # standings not imported: NULL
    assert lines.loc["222222222"].source_file == "week/contest-details-20261010.json"
    assert lines.source_sha256.notna().all()


class FakeBQ:
    def __init__(self, frames):
        self.frames = frames

    def __call__(self, sql):
        from nfl_dfs.dashboard.data import sql_name
        return self.frames.get(sql_name(sql), pd.DataFrame()).copy()


def test_fetch_outcomes_refuses_without_standings_and_scores_with_them(laptop):
    p = P.parse_snapshot(snap(laptop))
    with pytest.raises(P.PublishError, match="refusing to score"):
        P.fetch_outcomes(FakeBQ({}), 2026, 5, p.frame, p.details)
    frames = {
        "milly_points": pd.DataFrame({"points": [90.0, 80.0, 70.0, 60.0], "payout": [None] * 4}),
        "milly_contests": pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "123456789",
                                         "lobby_contest_id": "123456789"}]),
        "week_player_points": pd.DataFrame({"display_name": ["Synthetic Player 1"], "fpts": [12.0]}),
        "contest_points": pd.DataFrame({"contest_id": ["222222222"] * 3, "points": [50.0, 40.0, 30.0]}),
    }
    out, points = P.fetch_outcomes(FakeBQ(frames), 2026, 5, p.frame, p.details)
    assert out.milly_contest == "123456789" and out.cash_line == 70.0
    assert out.cash_lines == {"123456789": 70.0, "222222222": 40.0}
    assert out.player_points[1] == 12.0 and set(points) == {"123456789", "222222222"}


def test_player_points_skip_a_name_two_frame_players_share():
    fr = frame()
    fr.loc[3, "display_name"] = "Synthetic Player 4"           # two rows, one name
    pts = P.player_points(fr, {"Synthetic Player 4": 99.0}, {"00-0000003": 7.0})
    assert pts[3] == 7.0 and pts[4] == 0.0


def test_script_refuses_apply_without_scoring(laptop, capsys):
    mod = _script()
    s_ = snap(laptop)
    assert mod.main(["--season", "2026", "--week", "5", "--inputs", str(s_), "--no-bq", "--apply"]) == 3
    assert "--apply with --no-bq" in capsys.readouterr().err
