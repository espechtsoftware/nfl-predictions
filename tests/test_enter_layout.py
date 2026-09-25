"""The ENTER layout module (2026-09-24): the operator's Week-3 head layout, legacy equivalence of sequential/top,
the fewest-LOW order, and the writer/check round trip through relayout_enter.sh. Synthetic contests and ids only."""
from __future__ import annotations

import csv
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from nfl_dfs.inference import enter_layout as EL

ROOT = Path(__file__).resolve().parents[1]


def week3_shaped() -> list[dict]:
    """The Week-3 contest SHAPE (names, sizes, order) with made-up ids: 198 entries across 40 contests."""
    cs, cid = [], 1000
    def add(name, n, times):
        nonlocal cid
        for _ in range(times):
            cs.append({"name": name, "contest_id": str(cid), "entries": n, "keep": n}); cid += 1
    add("wildcat", 2, 2); add("sat20", 1, 19); add("supersat25hi", 17, 3); add("ffwc", 4, 1)
    add("supersat2", 5, 12); add("supersat25lo", 20, 3)
    return cs


# ---------------------------------------------------------------- the operator's head layout


def test_head_layout_is_the_operators_week3_spec():
    cs = week3_shaped()
    ranks = EL.assign_ranks(cs, "head")
    assert sum(len(r) for r in ranks) == 198
    assert EL.rows_needed(cs, "head") == 144
    one = [[x + 1 for x in r] for r in ranks]          # 1-based, as the operator stated it
    by = lambda name: [r for c, r in zip(cs, one) if c["name"] == name]
    assert by("wildcat") == [[1, 2], [3, 4]]
    # operator 2026-09-24: no two $2 single-entry satellites share a lineup; rows 1-4, then the best unique rows 5-19
    assert [r[0] for r in by("sat20")] == list(range(1, 20))
    for r in by("ffwc") + by("supersat2"):
        assert r[:2] == [1, 2] and all(x > 4 for x in r[2:])
    for r in by("supersat25hi") + by("supersat25lo"):
        assert r[:4] == [1, 2, 3, 4] and all(x > 4 for x in r[4:])
    for c, r in zip(cs, one):
        assert len(r) == c["entries"] and len(set(r)) == len(r)
    unique = [x for r in one for x in r if x > 4]
    assert len(unique) == len(set(unique)) == 140 and sorted(unique) == list(range(5, 145))


def test_head_unique_rows_are_dealt_snake_fashion():
    cs = [{"name": "a", "contest_id": "1", "entries": 5, "keep": 5}, {"name": "b", "contest_id": "2", "entries": 5, "keep": 5}]
    a, b = [[x + 1 for x in r] for r in EL.assign_ranks(cs, "head")]
    assert a == [1, 2, 5, 8, 9] and b == [1, 2, 6, 7, 10]


def test_head_small_groups_rotate_per_group():
    cs = [{"name": "x", "contest_id": str(i), "entries": 2, "keep": 2} for i in range(3)]
    assert [[v + 1 for v in r] for r in EL.assign_ranks(cs, "head")] == [[1, 2], [3, 4], [5, 6]]


def test_head_groups_by_size_not_name():
    """Laptop review F2: differently named single-entry contests must not share a lineup."""
    cs = [{"name": n, "contest_id": str(i), "entries": 1, "keep": 1} for i, n in enumerate(["sat20", "sat20b", "other"] * 3)]
    firsts = [r[0] for r in EL.assign_ranks(cs, "head")]
    assert len(set(firsts)) == len(firsts) == 9


def test_unknown_layout_and_bad_entries_fail_closed():
    with pytest.raises(EL.LayoutError):
        EL.assign_ranks(week3_shaped(), "snake")
    with pytest.raises(EL.LayoutError):
        EL.assign_ranks([{"name": "x", "contest_id": "1", "entries": 0, "keep": 0}], "head")
    with pytest.raises(EL.LayoutError, match="needs 144"):
        EL.contest_rows(week3_shaped(), 143, "head", list(range(143)))


# ---------------------------------------------------------------- legacy equivalence


def legacy_rows(contests, body, layout):
    """The pre-2026-09-24 inline writer (sunday_after_build.sh / relayout_enter.sh), verbatim in logic."""
    out = []
    if layout == "top":
        cursor = 0
        for c in contests:
            n = int(c["entries"])
            if c.get("block"):
                out.append(body[cursor:cursor + n]); cursor += n
            else:
                out.append(body[:n])
    else:
        keep_total = sum(int(c["keep"]) for c in contests); fill_next = keep_total + 1; keep_next = 1
        for c in contests:
            n, k = int(c["entries"]), int(c["keep"])
            keepers = body[keep_next - 1: keep_next - 1 + k]; keep_next += k
            fills = body[fill_next - 1: fill_next - 1 + (n - k)]; fill_next += n - k
            out.append(keepers + fills)
    return out


@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("layout", ["sequential", "top"])
def test_sequential_and_top_match_the_old_writer(seed, layout):
    rng = random.Random(seed)
    cs = []
    for i in range(rng.randint(1, 12)):
        n = rng.randint(1, 23)
        c = {"name": f"c{i}", "contest_id": str(i), "entries": n, "keep": rng.randint(0, n)}
        if layout == "top" and rng.random() < 0.3:
            c["block"] = True
        cs.append(c)
    n_rows = max(EL.rows_needed(cs, layout), 1) + rng.randint(0, 5)
    body = [[f"r{i}"] for i in range(n_rows)]
    new = [[body[i] for i in rows] for rows in EL.contest_rows(cs, n_rows, layout, list(range(n_rows)))]
    assert new == legacy_rows(cs, body, layout)


# ---------------------------------------------------------------- the fewest-LOW order


def test_fewest_low_order_pins_promoted_row_and_keeps_flagged_rows_behind():
    low = {"L"}
    rows = [["L", "L", "a"], ["L", "a", "a"], ["a", "a", "a"], ["L", "L", "L"], ["a", "a", "a"]]
    # row 3 (0-based 2) is flagged: no LOW, so it would rank first -- it is kept out of the protected head only
    assert EL.fewest_low_order(rows, low, flagged={2}, pin_first=True, protect=4) == [0, 4, 1, 3, 2]
    assert EL.fewest_low_order(rows, low, flagged={2}, pin_first=True, protect=2) == [0, 4, 2, 1, 3]
    assert EL.fewest_low_order(rows, low, flagged=set(), pin_first=False) == [2, 4, 1, 0, 3]


def test_single_entry_and_head_ranks_are_protected():
    """Operator 2026-09-24: the wildcats and all nineteen $2 single-entry satellites hold clean lineups."""
    cs = week3_shaped()
    assert EL.protected_ranks(cs, "head") == 19 and EL.protected_ranks(cs, "top") == 4
    n = 150
    flagged = set(range(0, n, 3))
    perm = EL.fewest_low_order([[f"p{r}"] for r in range(n)], set(), flagged, pin_first=False, protect=19)
    per = EL.contest_rows(cs, n, "head", perm)
    small = [i for c, r in zip(cs, per) if c["entries"] <= 2 for i in r]
    assert len(small) == 23 and not flagged & set(small)


def test_flagged_rows_spread_across_contests_not_into_the_last_dealt():
    """Operator 2026-09-24 after the external review: flagged rows stay out of rows 1-4 but are otherwise dealt like any
    other row, so they do not all land in the supersat25 contests."""
    cs = week3_shaped()
    n = 150
    rows = [[f"p{r}"] for r in range(n)]
    flagged = set(range(0, n, 3))                                # a third of the book, spread through it
    perm = EL.fewest_low_order(rows, set(), flagged, pin_first=False)
    assert not flagged & set(perm[:4])
    per = EL.contest_rows(cs, n, "head", perm)
    big = {i for c, r in zip(cs, per) if c["name"].startswith("supersat25") for i in r}
    other = {i for c, r in zip(cs, per) if not c["name"].startswith("supersat25") for i in r[2:] if c["entries"] > 2}
    assert flagged & other, "flagged rows must also reach the smaller multi-entry contests"
    assert len(flagged & big) < len(flagged & set(perm[:144]))


def _book_fixture(tmp: Path, n: int, *, low_every: int = 3, flagged=(), vetting_kind="final"):
    ids = [[f"{r * 10 + s}" for s in range(9)] for r in range(n)]
    with open(tmp / "book.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); w.writerows(ids)
    up = [[f"9{x}" for x in r] for r in ids]                     # draftable ids differ from dk_player_id
    with open(tmp / "upload.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); w.writerows(up)
    with open(tmp / "sets.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["gsis_id", "dk_player_id", "display_name", "pos", "set"])
        for r, row in enumerate(ids):
            for s, pid in enumerate(row):
                pos = "DST" if s == 8 else "WR"
                w.writerow(["g", pid, "n", pos, "LOW" if (s < 8 and (r + s) % low_every == 0) else "MID"])
    if vetting_kind == "final":
        v = {"version": "t", "publishable": True,
             "lineups": [{"position": i + 1, "source": "x", "salary": 50000, "flags": ({"p": ["DK:Q"]} if i in flagged else {})}
                         for i in range(n)]}
    else:
        v = {"order_source_ranks": list(range(1, n + 1)),
             "lineups": [{"rank": i + 1, "hard": False, "material": i in flagged,
                          "flags": ({"p": ["report:Questionable"]} if i in flagged else {})} for i in range(n)]}
    (tmp / "vetting.json").write_text(json.dumps(v))
    return tmp / "book.csv", tmp / "upload.csv", tmp / "sets.csv", tmp / "vetting.json"


def test_both_vetting_forms_give_one_order(tmp_path):
    """Laptop review F3 + operator 2026-09-24 ("any injury flag"): the same book gets the same order from either file;
    practice/market tags never bar a row, DK/report/QB tags always do."""
    book, _, sets, _ = _book_fixture(tmp_path, 12)
    tags = {2: {"A": ["DK:Q"]}, 4: {"B": ["practice:Limited", "market:no_props"]}, 6: {"C": ["report:Questionable"]},
            8: {"D": ["qb:backup-risk"]}}
    final = {"lineups": [{"position": i + 1, "source": "x", "salary": 1, "flags": tags.get(i, {})} for i in range(12)]}
    plain = {"order_source_ranks": [12 - i for i in range(12)],       # vetter reversed the book: rank 12 is row 1
             "lineups": [{"rank": 12 - i, "hard": False, "material": False, "flags": tags.get(i, {})} for i in range(12)]}
    (tmp_path / "vf.json").write_text(json.dumps(final)); (tmp_path / "v.json").write_text(json.dumps(plain))
    assert EL.flagged_positions(tmp_path / "vf.json", 12) == EL.flagged_positions(tmp_path / "v.json", 12) == {2, 6, 8}
    a = EL.load_order("fewest-low", 12, book=book, vetting=tmp_path / "vf.json", sets=sets, pin_first=False)[0]
    b = EL.load_order("fewest-low", 12, book=book, vetting=tmp_path / "v.json", sets=sets, pin_first=False)[0]
    assert a == b and not {2, 6, 8} & set(a[:4])


def test_book_upload_alignment_is_checked(tmp_path):
    """Laptop review F4: a shifted upload is refused even when the row count matches."""
    rng = random.Random(3)
    rows = [[str(rng.randrange(25)) for _ in range(9)] for _ in range(12)]    # players recur across rows, as in a real book
    EL.check_aligned(rows, [[f"9{p}" for p in r] for r in rows])
    with pytest.raises(EL.LayoutError, match="not the same book"):
        EL.check_aligned(rows, [[f"9{p}" for p in r] for r in rows[1:] + rows[:1]])
    book, up, sets, vet = _book_fixture(tmp_path, 12)
    body = list(csv.reader(open(up)))[1:]
    EL.load_order("fewest-low", 12, book=book, vetting=vet, sets=sets, pin_first=False, upload_rows=body)
    shifted = [body[0][:1] + body[1][1:]] + body[1:]              # one slot swapped in from another lineup
    with pytest.raises(EL.LayoutError, match="not the same book"):
        EL.load_order("fewest-low", 12, book=book, vetting=vet, sets=sets, pin_first=False, upload_rows=shifted)


@pytest.mark.parametrize("kind", ["final", "plain"])
def test_load_order_reads_both_vetting_forms(tmp_path, kind):
    book, _, sets, vet = _book_fixture(tmp_path, 12, flagged={0, 5}, vetting_kind=kind)
    perm, info = EL.load_order("fewest-low", 12, book=book, vetting=vet, sets=sets, pin_first=False)
    assert sorted(perm) == list(range(12)) and not {0, 5} & set(perm[:4]) and info["flagged_rows"] == 2


def test_load_order_fails_closed_on_missing_inputs_and_wrong_ids(tmp_path):
    book, _, sets, vet = _book_fixture(tmp_path, 12)
    with pytest.raises(EL.LayoutError, match="needs --sets"):
        EL.load_order("fewest-low", 12, book=book, vetting=vet, sets=None, pin_first=False)
    with pytest.raises(EL.LayoutError, match="same book"):
        EL.load_order("fewest-low", 11, book=book, vetting=vet, sets=sets, pin_first=False)
    rows = list(csv.reader(open(sets)))
    with open(sets, "w", newline="") as f:           # a sets file for another slate: ids do not match the book
        w = csv.writer(f); w.writerow(rows[0]); w.writerows([[r[0], "x" + r[1]] + r[2:] for r in rows[1:]])
    with pytest.raises(EL.LayoutError, match="knows only"):
        EL.load_order("fewest-low", 12, book=book, vetting=vet, sets=sets, pin_first=False)
    with pytest.raises(EL.LayoutError):
        EL.load_order("random", 12, book=None, vetting=None, sets=None, pin_first=False)
    assert EL.load_order("greedy", 5, book=None, vetting=None, sets=None, pin_first=False)[0] == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------- writer / check / relayout end to end


def test_write_then_check_round_trip_and_tamper_detection(tmp_path):
    cs = week3_shaped()
    book, up, sets, vet = _book_fixture(tmp_path, 150, flagged={1, 7})
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    info = EL.load_order("fewest-low", 150, book=book, vetting=vet, sets=sets, pin_first=True)
    stage = tmp_path / "stage"
    EL.write(cs, up, stage, "head", info)
    assert EL.check(cs, up, stage, "head", info) == []
    body = list(csv.reader(open(up)))[1:]
    first = [body[i] for i in info[0][:4]]
    wild = list(csv.reader(open(stage / EL.enter_filename(cs[0]))))[1:]
    assert wild == first[:2] and list(csv.reader(open(stage / EL.enter_filename(cs[1]))))[1:] == first[2:4]
    assert info[0][0] == 0 and 1 not in info[0][:4]           # promoted row pinned; a flagged row never in the head
    f = stage / EL.enter_filename(cs[-1])
    rows = list(csv.reader(open(f))); rows[3], rows[4] = rows[4], rows[3]
    with open(f, "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    assert EL.check(cs, up, stage, "head", info)


def test_relayout_enter_publishes_the_head_layout(tmp_path):
    cs = week3_shaped()
    book, up, sets, vet = _book_fixture(tmp_path, 150)
    out = tmp_path / "out"; out.mkdir()
    (out / "contests.json").write_text(json.dumps(cs))
    env = {**os.environ, "PROD": str(ROOT), "PY": sys.executable, "CONTESTS_JSON": str(out / "contests.json"),
           "ENTER_LAYOUT": "head", "ENTER_ORDER": "fewest-low", "OWNERSHIP_SETS": str(sets),
           "ENTER_BOOK_DIR": str(tmp_path), "ENTER_PIN_FIRST": "1"}
    r = subprocess.run(["bash", str(ROOT / "scripts/relayout_enter.sh"), str(up), str(out), "t1"],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "published bundle t1" in r.stdout
    staged = out / "ENTER"
    assert len(list(staged.glob("ENTER-*-entries-KEEP-first-*.csv"))) == 40
    layout_txt = (staged / "ENTER-layout.txt").read_text()
    assert "layout head; order fewest-low; 198 entries from 144 distinct book rows of 150" in layout_txt
    # without the sets file the relayout refuses and leaves ENTER/ as it was
    env2 = {**env, "OWNERSHIP_SETS": str(tmp_path / "missing.csv")}
    r2 = subprocess.run(["bash", str(ROOT / "scripts/relayout_enter.sh"), str(up), str(out), "t2"],
                        env=env2, capture_output=True, text=True)
    assert r2.returncode != 0 and "ENTER layout FAILED" in r2.stdout
    assert os.readlink(staged).endswith("t1")


def test_exposure_sheet_counts_entries_under_head(tmp_path):
    import pandas as pd
    cs = week3_shaped()
    book, up, sets, vet = _book_fixture(tmp_path, 150)
    ids = [r for r in csv.reader(open(book))][1:]
    all_ids = sorted({x for r in ids for x in r})
    pd.DataFrame({"dk_player_id": all_ids, "name": all_ids, "pos": "WR", "team": "T", "salary": 5000,
                  "proj": 10.0}).to_parquet(tmp_path / "frame.parquet")
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    (tmp_path / "ms.csv").write_text("id,source,market_points\n")
    (tmp_path / "st.csv").write_text("id,status\n")
    env = {**os.environ, "ENTER_LAYOUT": "head", "ENTER_ORDER": "greedy"}
    r = subprocess.run([sys.executable, str(ROOT / "scripts/exposure_sheet.py"), "--book", str(book), "--frame",
                        str(tmp_path / "frame.parquet"), "--contests", str(tmp_path / "contests.json"), "--out",
                        str(tmp_path / "sheet"), "--market-source-csv", str(tmp_path / "ms.csv"), "--status-csv",
                        str(tmp_path / "st.csv"), "--vetting", str(vet)], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "150 book rows -> 198 entries" in r.stdout
    sheet = pd.read_csv(tmp_path / "sheet/exposure-sheet.csv", dtype={"id": str})
    # book row 1 (greedy order) holds ids 0..8: it is in 21 of 198 entries (wildcat A, one sat20, FFWC, 12 supersat2, 6 supersats)
    top = sheet.set_index("id").loc["0"]
    assert int(top["rows"]) == 1 + 1 + 3 + 1 + 12 + 3 and abs(top["share"] - int(top["rows"]) / 198) < 1e-3


def test_paper_relayout_live_flags_clears_resolved_actives(tmp_path):
    """Refinement 1 paper test: a player whose live DK status has cleared stops barring his rows from the protected
    ranks; the script writes only to a scratch dir and marks it paper-only."""
    cs = week3_shaped()
    n = 150
    book, up, sets, _ = _book_fixture(tmp_path, n)
    rows = list(csv.reader(open(book)))[1:]
    # Saturday: rows 0..29 carry a report:Questionable tag for their first player -> barred from ranks 1-19
    vf = {"lineups": [{"position": i + 1, "source": "x", "salary": 1,
                       "flags": ({rows[i][0]: ["report:Questionable"]} if i < 30 else {})} for i in range(n)]}
    bd = tmp_path / "bookdir"; bd.mkdir()
    (bd / "book.csv").write_text(open(book).read()); (bd / "vetting_final.json").write_text(json.dumps(vf))
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    st = tmp_path / "status.csv"
    with open(st, "w", newline="") as f:          # Sunday: rows 0..9's players still Q, rows 10..29 cleared
        w = csv.writer(f); w.writerow(["id", "status"]); w.writerows([[rows[i][0], "Q"] for i in range(10)])
    out = tmp_path / "paper"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/paper_relayout_live_flags.py"), "--book-dir", str(bd),
                        "--upload", str(up), "--contests", str(tmp_path / "contests.json"), "--sets", str(sets),
                        "--out", str(out), "--status-csv", str(st)], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads((out / "paper-relayout.json").read_text())
    assert summary["rows_newly_protected"] and all(11 <= x <= 30 for x in summary["rows_newly_protected"])
    assert (out / "PAPER-ONLY-NOT-FOR-UPLOAD.txt").is_file()
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts/paper_relayout_live_flags.py"), "--book-dir", str(bd),
                         "--upload", str(up), "--contests", str(tmp_path / "contests.json"), "--sets", str(sets),
                         "--out", str(out), "--status-csv", str(st)], capture_output=True, text=True,
                        env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert r2.returncode != 0 and "not empty" in (r2.stdout + r2.stderr)


def test_live_status_rule_clears_activated_players_and_keeps_qb_notes(tmp_path):
    """Refinement 1 on the money path: flags come from the live DK snapshot (plus QB notes), never the report tag."""
    book, up, sets, _ = _book_fixture(tmp_path, 12)
    rows = list(csv.reader(open(book)))[1:]
    vf = {"lineups": [{"position": i + 1, "source": "x", "salary": 1, "flags": (
        {rows[i][0]: ["report:Questionable", "DK:Q"]} if i in (1, 2) else
        {rows[i][0]: ["qb:backup-risk"]} if i == 3 else {})} for i in range(12)]}
    (tmp_path / "vf.json").write_text(json.dumps(vf))
    snap = tmp_path / "snap.csv"
    with open(snap, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "status"])
        w.writerows([[p, "Q" if p == rows[2][0] else ""] for r in rows for p in r])   # row 1's player now active
    assert EL.flagged_positions(tmp_path / "vf.json", 12) == {1, 2, 3}
    assert EL.live_flagged_positions(tmp_path / "vf.json", 12, rows, snap) == {2, 3}
    short = tmp_path / "short.csv"; short.write_text("id,status\n1,Q\n")
    with pytest.raises(EL.LayoutError, match="lacks"):
        EL.live_flagged_positions(tmp_path / "vf.json", 12, rows, short)


def _published_bundle(tmp_path, n=150):
    cs = week3_shaped()
    book, up, sets, vet = _book_fixture(tmp_path, n)
    info = EL.load_order("fewest-low", n, book=book, vetting=vet, sets=sets, pin_first=True,
                         protect=EL.protected_ranks(cs, "head"))
    b = tmp_path / "bundle"
    EL.write(cs, up, b, "head", info)
    (b / "ENTER-all-rows-1-to-198-are-the-KEEPERS.csv").write_text(open(up).read())
    return cs, up, b


def test_frozen_swap_changes_cells_only_and_keeps_every_contests_rows(tmp_path):
    """Laptop review HIGH (2026-09-24): a swap re-publication keeps the published row->contest map and edits every copy."""
    cs, up, b = _published_bundle(tmp_path)
    rows = list(csv.reader(open(up))); hdr, body = rows[0], rows[1:]
    top = list(csv.reader(open(b / EL.enter_filename(cs[0]))))[1][0:9]     # wildcat A's first entry
    r = next(i for i, x in enumerate(body) if x == top)
    new = [list(x) for x in body]; new[r][3] = "SWAPPED"
    sw = tmp_path / "swapped.csv"
    with open(sw, "w", newline="") as f:
        csv.writer(f).writerows([hdr] + new)
    (tmp_path / "swapped.csv.swap.json").write_text(json.dumps({"swaps": [{"row": r + 1, "slot_index": 3,
                                                                          "out": {"dd": body[r][3]}, "in": {"dd": "SWAPPED"}}]}))
    per, info = EL.frozen_contest_rows(cs, b, new, tmp_path / "swapped.csv.swap.json")
    out = tmp_path / "out"
    EL.write(cs, sw, out, "head", (list(range(len(new))), info), frozen=per)
    changed = 0
    for c in cs:
        a = list(csv.reader(open(b / EL.enter_filename(c))))[1:]; z = list(csv.reader(open(out / EL.enter_filename(c))))[1:]
        for x, y in zip(a, z):
            d = [(p, q) for p, q in zip(x, y) if p != q]
            assert d in ([], [(body[r][3], "SWAPPED")])
            changed += bool(d)
    assert changed >= 2                                   # the head row sits in many contests; every copy was edited
    assert EL.check(cs, sw, out, "head", (list(range(len(new))), info), frozen=per) == []


def test_frozen_swap_refuses_cells_the_receipt_does_not_name(tmp_path):
    cs, up, b = _published_bundle(tmp_path)
    rows = list(csv.reader(open(up))); body = rows[1:]
    new = [list(x) for x in body]; new[5][2] = "X"; new[9][4] = "Y"          # two edits, receipt names one
    rec = tmp_path / "r.json"
    rec.write_text(json.dumps({"swaps": [{"row": 6, "slot_index": 2, "out": {"dd": body[5][2]}, "in": {"dd": "X"}}]}))
    with pytest.raises(EL.LayoutError, match="does not name"):
        EL.frozen_contest_rows(cs, b, new, rec)
    new2 = [list(x) for x in body]; new2[5][2] = "X"; new2[5][3] = "Z"        # no receipt: two cells in one row
    with pytest.raises(EL.LayoutError, match="at most one cell"):
        EL.frozen_contest_rows(cs, b, new2, None)


def test_paper_layout_capped_book_slots_and_lays_out(tmp_path):
    """R2 paper bundle converter: gsis-id rosters -> DK slot order (FLEX = surplus with the latest kickoff), both id
    forms from the frame, Questionable rows kept out of the protected ranks, written to a scratch dir only."""
    import pandas as pd
    cs = [{"name": "a", "contest_id": "1", "entries": 1, "keep": 1}, {"name": "b", "contest_id": "2", "entries": 5, "keep": 5}]
    pos = ["QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"]
    frame, caps, sets = [], [], []
    for r in range(8):
        ids = []
        for s, p in enumerate(pos):
            g = f"g{r}_{s}" if p != "DST" else f"T{r}_DST"
            frame.append({"gsis_id": g if p != "DST" else "0.0", "id": g, "position": p, "dk_player_id": f"p{r}{s}",
                          "dk_draftable_id": f"d{r}{s}", "display_name": g,
                          "report_status": "Questionable" if (r == 0 and s == 1) else None,
                          "game_start": pd.Timestamp("2026-09-27 17:00", tz="UTC") + pd.Timedelta(hours=3 * (s == 3))})
            sets.append({"dk_player_id": f"p{r}{s}", "pos": p, "set": "MID"})
            ids.append(g)
        caps.append({"players": ",".join(reversed(ids)), "book_rank": r + 1})
    run = tmp_path / "run"; run.mkdir()
    pd.DataFrame(frame).to_parquet(run / "frame.parquet")
    pd.DataFrame(caps).to_csv(tmp_path / "capped.csv", index=False)
    pd.DataFrame(sets).to_csv(tmp_path / "sets.csv", index=False)
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    out = tmp_path / "paper"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/paper_layout_capped_book.py"), "--capped-book",
                        str(tmp_path / "capped.csv"), "--run-dir", str(run), "--contests", str(tmp_path / "contests.json"),
                        "--sets", str(tmp_path / "sets.csv"), "--out", str(out)], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert r.returncode == 0, r.stdout + r.stderr
    book = list(csv.reader(open(out / "book" / "book.csv")))
    assert book[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert book[1][7] == "p03" and book[1][8] == "p08"           # the late-kickoff RB is the FLEX; DST last
    single = list(csv.reader(open(out / "bundle" / EL.enter_filename(cs[0]))))[1]
    assert single[1] != "d01"                                     # the Questionable row is not the protected entry
    assert (out / "bundle" / "PAPER-ONLY-NOT-FOR-UPLOAD.txt").is_file()


def test_explicitly_pinned_ranks(tmp_path):
    """Operator 2026-09-25: the $20 Millionaire takes row 1 and three $13 satellites rows 1, 2, 3; the rest is unchanged."""
    base = week3_shaped()
    extra = [{"name": "milly20", "contest_id": "9001", "entries": 1, "keep": 1, "ranks": [1]}] + [
        {"name": "sat13", "contest_id": str(9002 + j), "entries": 1, "keep": 1, "ranks": [j + 1]} for j in range(3)]
    cs = extra + base
    ranks = EL.assign_ranks(cs, "head")
    assert [r for r in ranks[:4]] == [[0], [0], [1], [2]]
    assert ranks[4:] == EL.assign_ranks(base, "head")           # nothing else moves
    assert EL.rows_needed(cs, "head") == 144 and EL.protected_ranks(cs, "head") == 19
    for bad in ([5], [0], [1, 1], "1", [True]):
        with pytest.raises(EL.LayoutError, match="ranks"):
            EL.assign_ranks([{"name": "x", "contest_id": "1", "entries": len(bad) if isinstance(bad, list) else 1,
                              "keep": 1, "ranks": bad}], "head")
