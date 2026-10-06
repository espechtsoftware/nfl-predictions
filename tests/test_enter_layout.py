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


def test_pin_may_name_any_row_the_layout_already_reads(tmp_path):
    """Operator 2026-09-27: a 2-entry $18 qualifier on rows 1 and 5. A pin may reach past the head into rows the unpinned
    layout already reads, never beyond them, so the book does not grow and nothing else moves."""
    base = week3_shaped()
    pin = {"name": "ffwc18", "contest_id": "9100", "entries": 2, "keep": 2, "ranks": [1, 5]}
    cs = base + [pin]
    ranks = EL.assign_ranks(cs, "head")
    assert ranks[-1] == [0, 4] and ranks[:-1] == EL.assign_ranks(base, "head")
    assert EL.rows_needed(cs, "head") == EL.rows_needed(base, "head") == 144
    assert EL.protected_ranks(cs, "head") == EL.protected_ranks(base, "head") == 19     # row 5 stays in the clean head
    top = EL.rows_needed(base, "head")
    EL.assign_ranks(base + [{**pin, "ranks": [1, top]}], "head")                         # the last existing row is fine


def test_pins_may_add_rows_without_gaps_and_the_book_grows_to_them():
    """Operator 2026-10-06 (Rev3): "1-26 for the $20 satellites" -- 26 super-satellite entries, each its own lineup,
    while the big contests read 22 rows. Pins may ADD rows past the unpinned layout; the book grows to the highest pinned
    row (rows_needed, so K and the caps follow); nothing unpinned moves; a gap (an unread row) refuses."""
    base = [{"name": f"big{j}", "contest_id": str(100 + j), "entries": 1, "keep": 1} for j in range(18)]
    base += [{"name": f"wild{j}", "contest_id": str(200 + j), "entries": 2, "keep": 2} for j in range(4)]
    K0 = EL.rows_needed(base, "head")
    sats = [{"name": f"supersat{j}", "contest_id": str(300 + j), "entries": 5, "keep": 5, "ranks": list(range(5 * j + 1, 5 * j + 6))}
            for j in range(4)]
    sats += [{"name": "supersat6", "contest_id": "306", "entries": 2, "keep": 2, "ranks": [21, 22]},
             {"name": "supersat7", "contest_id": "307", "entries": 3, "keep": 3, "ranks": [23, 24, 25]},
             {"name": "supersat8", "contest_id": "308", "entries": 1, "keep": 1, "ranks": [26]},
             {"name": "ffwc", "contest_id": "309", "entries": 1, "keep": 1, "ranks": [1]}]
    assert K0 < 26
    cs = sats + base
    ranks = EL.assign_ranks(cs, "head")
    assert ranks[len(sats):] == EL.assign_ranks(base, "head")                     # the big contests' rows do not move
    assert sorted(x for r in ranks[:7] for x in r) == list(range(26))            # 26 satellite entries, 26 distinct rows
    assert EL.rows_needed(cs, "head") == 26 and EL.rows_needed(cs, "spread") == 26
    with pytest.raises(EL.LayoutError, match="no gap"):                          # row 26 unread: [27] would leave a hole
        EL.assign_ranks(sats[:-2] + [{**sats[-2], "ranks": [27]}, sats[-1]] + base, "head")
    with pytest.raises(EL.LayoutError, match="no gap"):                          # a typo never builds a 300-row book
        EL.assign_ranks(base + [{"name": "typo", "contest_id": "9", "entries": 1, "keep": 1, "ranks": [300]}], "head")
    one_past = base + [{"name": "q", "contest_id": "9", "entries": 2, "keep": 2, "ranks": [1, K0 + 1]}]
    assert EL.rows_needed(one_past, "head") == K0 + 1                            # one past the layout: the book grows by one


def test_tail_track_contests_take_a_sleeve_after_the_mean_rows():
    """Operator 2026-09-27: two tracks from one pool. Satellites (mean) keep the head layout exactly; Millionaire seats
    (tail) take sleeve rows after the last mean row, pins allowed inside the sleeve; the sleeve is never permuted."""
    base = week3_shaped()
    milly = {"name": "milly20", "contest_id": "9001", "entries": 1, "keep": 1, "track": "tail"}
    quali = {"name": "ffwc18", "contest_id": "9002", "entries": 2, "keep": 2, "track": "tail"}
    cs = [milly] + base + [quali]                                    # tail contests anywhere in the file
    ranks = EL.assign_ranks(cs, "head")
    K = EL.rows_needed(base, "head")                                  # 144: the mean rows are the base layout, untouched
    assert ranks[1:-1] == EL.assign_ranks(base, "head")
    assert ranks[0] == [K] and ranks[-1] == [K + 1, K + 2]           # the sleeve, in file order, unique rows
    assert EL.rows_needed(cs, "head") == K + 3 and EL.sleeve_size(cs, "head") == 3
    assert EL.protected_ranks(cs, "head") == EL.protected_ranks(base, "head") == 19   # the sleeve is not "protected"
    pinned = [{**milly, "ranks": [3]}] + base + [{**quali, "ranks": [1, 2]}]
    r2 = EL.assign_ranks(pinned, "head"); assert r2[0] == [K + 2] and r2[-1] == [K, K + 1]
    with pytest.raises(EL.LayoutError, match="sleeve"):
        EL.assign_ranks([{**milly, "ranks": [4]}] + base + [quali], "head")           # past the sleeve
    with pytest.raises(EL.LayoutError, match="needs ENTER_LAYOUT=head"):
        EL.assign_ranks(cs, "sequential")                                              # never silently laid out as mean
    with pytest.raises(EL.LayoutError, match="track must be one of"):
        EL.assign_ranks([{**milly, "track": "tial"}] + base, "head")
    # the order permutes the mean rows only; the sleeve keeps its book position
    n = K + 3
    perm = EL.fewest_low_order([[f"p{r}"] for r in range(n)], set(), flagged={0, 1}, pin_first=False, protect=19, fixed_tail=3)
    assert perm[-3:] == [K, K + 1, K + 2] and sorted(perm[:K]) == list(range(K)) and perm[0] not in (0, 1)
    rows = EL.contest_rows(cs, n, "head", perm)
    assert rows[0] == [K] and rows[-1] == [K + 1, K + 2]
    with pytest.raises(EL.LayoutError, match="exactly"):
        EL.contest_rows(cs, n + 1, "head", list(range(n + 1)))                        # a longer book: sleeve would slide


def test_sleeve_starts_right_after_the_mean_rows_and_the_floor_is_one():
    """Laptop 2026-09-28: the 90-row mean floor is gone (it built rows no contest read); the sleeve starts right after
    the layout's own mean rows and the book holds exactly mean + T rows. MEAN_ROWS_FLOOR is 1: a tail-only week still
    builds one mean row (the fallback track), so the sleeve starts at row 1."""
    cs = [{"name": "sat", "contest_id": str(i), "entries": 1, "keep": 1} for i in range(6)] + \
         [{"name": "milly", "contest_id": "99", "entries": 2, "keep": 2, "track": "tail"}]
    ranks = EL.assign_ranks(cs, "head")
    assert max(max(r) for r in ranks[:6]) + 1 == 6 and ranks[6] == [6, 7]
    assert EL.rows_needed(cs, "head") == 8 and EL.sleeve_size(cs, "head") == 2
    EL.contest_rows(cs, 8, "head", list(range(8)))
    assert EL.MEAN_ROWS_FLOOR == 1
    tail_only = [{"name": "milly", "contest_id": "99", "entries": 2, "keep": 2, "track": "tail"}]
    assert EL.assign_ranks(tail_only, "head") == [[1, 2]] and EL.rows_needed(tail_only, "head") == 3
    with pytest.raises(EL.LayoutError, match="needs 3 distinct lineups"):
        EL.contest_rows(tail_only, 2, "head", [0, 1])
    with pytest.raises(EL.LayoutError, match="exactly 3 rows"):
        EL.contest_rows(tail_only, 4, "head", [0, 1, 2, 3])
    with pytest.raises(EL.LayoutError, match="exactly 8 rows"):
        EL.contest_rows(cs, 9, "head", list(range(9)))            # a longer book: the sleeve would slide


def test_late_game_only_questionable_flag(tmp_path, monkeypatch):
    """T-70 rule (iii), operator 2026-09-28: with ENTER_FLAG_LATE_Q_ONLY=1 an early-game Questionable still listed at
    the pull is not a flag; a late-game Questionable is; OUT/IR/D flag regardless; the rule fails closed."""
    rows = [["e1"], ["l1"], ["o1"], ["c1"]]                            # early Q, late Q, early OUT, clean
    vf = {"lineups": [{"position": i + 1, "flags": {}} for i in range(4)]}
    (tmp_path / "vf.json").write_text(json.dumps(vf))
    snap = tmp_path / "snap.csv"
    snap.write_text("id,status,game_start\ne1,Q,2026-09-27T17:00:00.0000000Z\nl1,Q,2026-09-27T20:25:00.0000000Z\n"
                    "o1,OUT,2026-09-27T17:00:00.0000000Z\nc1,,2026-09-27T17:00:00.0000000Z\n")
    monkeypatch.delenv("ENTER_FLAG_LATE_Q_ONLY", raising=False)
    assert EL.live_flagged_positions(tmp_path / "vf.json", 4, rows, snap) == {0, 1, 2}     # the old rule: every Q
    monkeypatch.setenv("ENTER_FLAG_LATE_Q_ONLY", "1"); monkeypatch.setenv("LOCK_UTC", "2026-09-27 17:00:00+00:00")
    assert EL.live_flagged_positions(tmp_path / "vf.json", 4, rows, snap) == {1, 2}        # early Q is active
    monkeypatch.delenv("LOCK_UTC")
    with pytest.raises(EL.LayoutError, match="LOCK_UTC"):
        EL.live_flagged_positions(tmp_path / "vf.json", 4, rows, snap)
    old = tmp_path / "old.csv"; old.write_text("id,status\ne1,Q\nl1,Q\no1,OUT\nc1,\n")
    monkeypatch.setenv("LOCK_UTC", "2026-09-27 17:00:00+00:00")
    with pytest.raises(EL.LayoutError, match="game_start"):
        EL.live_flagged_positions(tmp_path / "vf.json", 4, rows, old)                      # a snapshot without game starts


def test_frozen_swap_uses_the_row_map_when_the_sleeve_repeats_a_mean_row(tmp_path):
    """Sweep 2026-09-29 item 2: the mean sleeve repeats main rows by design; the published row map (not a reverse roster
    lookup) tells the swap re-publication which upload rows each contest holds."""
    import csv, json
    cs = [{"name": "sat", "contest_id": "1", "entries": 1, "keep": 1}, {"name": "milly", "contest_id": "2", "entries": 2, "keep": 2, "track": "tail"}]
    hdr = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    r1 = [str(100 + i) for i in range(9)]; r2 = [str(200 + i) for i in range(9)]
    body = [r1, r2, r1]                                   # mean row 0 = r1; sleeve rows 1, 2 = r2, r1 (a repeat of the mean row)
    up = tmp_path / "upload.csv"
    with up.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(hdr); w.writerows(body)
    stage = tmp_path / "bundle"
    EL.write(cs, up, stage, "head", (list(range(3)), {"order": "greedy"}))
    rowmap = json.loads((stage / EL.ROWMAP_NAME).read_text())
    assert rowmap == {"sat-1": [0], "milly-2": [1, 2]}
    (stage / "ENTER-all-rows-1-to-3-are-the-KEEPERS.csv").write_bytes(up.read_bytes())
    new = [r1, r2, r1[:8] + ["999"]]                      # one cell changed in the repeated sleeve row
    per, info = EL.frozen_contest_rows(cs, stage, new, None)
    assert per == [[0], [1, 2]] and info["rows_changed"] == [3]
    (stage / EL.ROWMAP_NAME).unlink()                     # a bundle without the map: the reverse lookup refuses repeats by name
    with pytest.raises(EL.LayoutError, match="no row map"):
        EL.frozen_contest_rows(cs, stage, new, None)


# ---------------------------------------------------------------- the spread layout (winners study 2026-09-29 §4.2; laptop W-C)


def test_spread_layout_keeps_the_head_book_size_and_spreads_each_contest():
    cs = week3_shaped()
    head = EL.assign_ranks(cs, "head"); spread = EL.assign_ranks(cs, "spread")
    # the last spread position of the last equal-size contest is 143 of the head layout's K = 144
    assert EL.rows_needed(cs, "head") == 144 and EL.rows_needed(cs, "spread") == 143
    assert sum(len(r) for r in spread) == 198
    K = 144
    for c, r in zip(cs, spread):
        assert len(r) == c["entries"] and len(set(r)) == len(r) and all(0 <= x < K for x in r)
    one = [[x + 1 for x in r] for r in spread]
    by = lambda name: [r for c, r in zip(cs, one) if c["name"] == name]
    # the three 20-entry contests sit K/20 = 7.2 rows apart along the sequence, offset from one another by a third of a
    # step (reviewer 2026-09-29: equal-size contests must not take identical rows)
    lo = by("supersat25lo")
    for g, r in enumerate(lo):
        assert r == [int((j + (g + 0.5) / 3) * K / 20) + 1 for j in range(20)]
        assert min(b - a for a, b in zip(r, r[1:])) >= 7
    assert lo[0][0] == 2 and lo[1][0] == 4 and lo[2][0] == 7 and lo[2][-1] == 143
    assert not (set(lo[0]) & set(lo[1])) and not (set(lo[1]) & set(lo[2])) and not (set(lo[0]) & set(lo[2]))
    hi = by("supersat25hi")
    assert not (set(hi[0]) & set(hi[1])) and not (set(hi[1]) & set(hi[2]))
    # distinct lineups entered by the multi-entry contests: every row of every contest, no two equal-size contests alike
    multi = [r for c, r in zip(cs, one) if c["entries"] > 2]
    assert len({tuple(r) for r in multi}) == len(multi)
    # the nineteen single-entry satellites never share a lineup and are spread over the whole block, not rows 1-19
    singles = [r[0] for r in by("sat20")]
    assert len(set(singles)) == 19 and singles[0] == 4 and singles[-1] == 141 and max(singles) - min(singles) > 100
    # the two 2-entry wildcats take a 4-row spread as one group, in blocks of 2
    assert by("wildcat") == [[19, 55], [91, 127]]
    # the head layout's own ranks are untouched
    assert head == EL.assign_ranks(cs, "head")


def test_spread_layout_two_tracks_pins_and_protection():
    cs = [{"name": "a", "contest_id": "1", "entries": 5, "keep": 5}, {"name": "b", "contest_id": "2", "entries": 5, "keep": 5},
          {"name": "milly", "contest_id": "9", "entries": 2, "keep": 2, "track": "tail"}]
    head = EL.assign_ranks(cs, "head"); spread = EL.assign_ranks(cs, "spread")
    k = max(max(r) + 1 for r in head[:2])                              # the mean block the head layout reads (10 rows)
    assert [x + 1 for x in spread[0]] == [1, 3, 5, 7, 9] and [x + 1 for x in spread[1]] == [2, 4, 6, 8, 10]   # offset by half a step
    assert spread[2] == head[2] == [k, k + 1]                          # the sleeve starts after the mean rows, as under head
    assert EL.sleeve_size(cs, "spread") == 2 and EL.rows_needed(cs, "spread") == EL.rows_needed(cs, "head") == 12
    pinned = [{"name": "q", "contest_id": "3", "entries": 2, "keep": 2, "ranks": [1, 5]}] + cs
    assert EL.assign_ranks(pinned, "spread")[0] == [0, 4]
    with pytest.raises(EL.LayoutError):
        EL.assign_ranks([{"name": "q", "contest_id": "3", "entries": 2, "keep": 2, "ranks": [1, 99]}] + cs, "spread")
    with pytest.raises(EL.LayoutError):                                # a tail contest needs a two-track layout
        EL.assign_ranks(cs, "top")
    # protected ranks reach to the last rank an all-head contest takes: singles are spread over the whole mean block
    singles = [{"name": "s", "contest_id": str(i), "entries": 1, "keep": 1} for i in range(4)] + [cs[0]]
    assert EL.protected_ranks(singles, "spread") == max(r[0] for r in EL.assign_ranks(singles, "spread")[:4]) + 1
    assert EL.protected_ranks(singles, "spread") > EL.protected_ranks(singles, "head")


# ---------------------------------------------------------------- the small-contest overlap limit (Week-5 candidate)

HDR9 = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]


def _players(rows_spec):
    """rows_spec: per rank, a list of 9 player tokens -> frozensets."""
    return [frozenset(r) for r in rows_spec]


def _book(n, core_rows=(), core=("q", "r1", "r2", "w1", "w2", "w3", "t")):
    """n rows; the ranks in core_rows share the 7-player core (+2 unique each); every other row is all-unique."""
    out = []
    for i in range(n):
        if i in core_rows:
            out.append(list(core) + [f"f{i}", f"d{i}"])
        else:
            out.append([f"p{i}_{j}" for j in range(9)])
    return out


def test_overlap_limit_replaces_only_the_violating_rank_and_keeps_the_rest():
    cs = [{"name": "sat3", "contest_id": "1", "entries": 3, "keep": 3},
          {"name": "big", "contest_id": "2", "entries": 10, "keep": 10},
          {"name": "one", "contest_id": "3", "entries": 1, "keep": 1}]
    head = EL.assign_ranks(cs, "head")
    K = max(max(r) for r in head) + 1
    rp = _players(_book(K, core_rows={0, 1}))            # ranks 0 and 1 share 7 players
    got, changes = EL.limit_small_overlap(cs, head, rp, 5)
    assert got[0][0] == head[0][0] == 0                   # the first rank is kept
    assert 1 not in got[0] and len(set(got[0])) == 3
    assert got[0][1] == 2 and got[0][2] == head[0][2]    # rank 1 -> the next fitting rank; the unique rank is kept
    assert changes == [{"contest": "sat3", "label": "sat3-1", "from_rank": 1, "to_rank": 2}]
    assert got[1] == head[1] and got[2] == head[2]       # a 10-entry and a 1-entry contest are untouched
    for a in got[0]:
        for b in got[0]:
            if a != b:
                assert len(rp[a] & rp[b]) <= 5


def test_overlap_limit_is_a_no_op_when_rows_already_fit_and_off_by_default():
    cs = [{"name": "sat2", "contest_id": "1", "entries": 2, "keep": 2}, {"name": "sat5", "contest_id": "2", "entries": 5, "keep": 5}]
    head = EL.assign_ranks(cs, "head")
    K = max(max(r) for r in head) + 1
    got, changes = EL.limit_small_overlap(cs, head, _players(_book(K)), 5)
    assert got == head and changes == []
    assert EL.final_ranks(cs, "head") == (head, [])      # unset = off
    assert EL.contest_rows(cs, K, "head", list(range(K))) == head


def test_overlap_limit_leaves_pinned_and_tail_contests_alone_and_wraps():
    cs = [{"name": "pin", "contest_id": "1", "entries": 2, "keep": 2, "ranks": [1, 2]},
          {"name": "tail", "contest_id": "2", "entries": 2, "keep": 2, "track": "tail"},
          {"name": "sat4", "contest_id": "3", "entries": 4, "keep": 4}]
    head = EL.assign_ranks(cs, "head")
    K = max(max(r) for r, c in zip(head, cs) if c.get("track", "mean") == "mean") + 1
    last = head[2][-1]
    rp2 = _players(_book(K + 2, core_rows={0, 1}))
    got, ch = EL.limit_small_overlap(cs, head, rp2, 5)
    assert got[0] == head[0] and got[1] == head[1]        # the pin and the tail contest keep their rows
    assert len(got[2]) == 4 and all(r < K for r in got[2]) and last in got[2]
    assert not [x for x in ch if "relaxed_to" in x]


def _core_book(n, core_size):
    """n rows that all share the same core_size players (the rest unique per row)."""
    core = [f"c{j}" for j in range(core_size)]
    return [core + [f"u{i}_{j}" for j in range(9 - core_size)] for i in range(n)]


def test_overlap_limit_relaxes_loudly_instead_of_refusing():
    cs = [{"name": "sat3", "contest_id": "7", "entries": 3, "keep": 3}, {"name": "big", "contest_id": "8", "entries": 6, "keep": 6}]
    head = EL.assign_ranks(cs, "head")
    K = max(max(r) for r in head) + 1
    got, ch = EL.limit_small_overlap(cs, head, _players(_core_book(K, 6)), 5)     # every pair shares 6: M=5 cannot fit
    assert got[0] == head[0] and got[1] == head[1]        # dealt at M=6, where the head rows already fit
    assert [x for x in ch if "relaxed_to" in x] == [{"contest": "sat3", "label": "sat3-7", "relaxed_from": 5, "relaxed_to": 6}]
    assert EL.small_overlap_record(cs, 5, ch) == {"sat3-7": 6}
    assert EL.relaxation_banners(ch) == ["!!! SMALL-CONTEST OVERLAP LIMIT RELAXED for sat3-7: M=5 -> 6"]
    got, ch = EL.limit_small_overlap(cs, head, _players(_core_book(K, 8)), 5)     # every pair shares 8: nothing fits at 7
    assert got == head and EL.small_overlap_record(cs, 5, ch) == {"sat3-7": "head"}
    assert EL.relaxation_banners(ch) == ["!!! SMALL-CONTEST OVERLAP LIMIT RELAXED for sat3-7: M=5 -> head rows"]
    # the relaxation is the smallest M that fits: shares 6 with one pair structure fits at 6, never jumps to 7
    rows = _core_book(K, 6); rows[1] = rows[0][:7] + ["v1", "v2"]                  # rank 1 shares 7 with rank 0
    got, ch = EL.limit_small_overlap(cs, head, _players(rows), 5)
    assert EL.small_overlap_record(cs, 5, ch)["sat3-7"] == 6 and 1 not in got[0]


def test_overlap_limit_write_records_the_fallback_and_check_agrees(tmp_path, monkeypatch, capsys):
    cs = [{"name": "sat3", "contest_id": "7", "entries": 3, "keep": 3}, {"name": "big", "contest_id": "8", "entries": 6, "keep": 6}]
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    K = EL.rows_needed(cs, "head")
    rows = _core_book(K, 6); rows[1] = rows[0][:7] + ["v1", "v2"]                  # rank 1 shares 7 with rank 0
    up = tmp_path / "upload.csv"
    with open(up, "w", newline="") as f:
        w = csv.writer(f); w.writerow(HDR9); w.writerows(rows)
    monkeypatch.setenv("ENTER_SMALL_MAX_SHARED", "5")
    st = tmp_path / "stage"
    assert EL.main(["write", str(tmp_path / "contests.json"), str(up), st.as_posix(), "--layout", "head"]) == 0
    out = capsys.readouterr()
    assert "!!! SMALL-CONTEST OVERLAP LIMIT RELAXED for sat3-7: M=5 -> 6" in out.out and "!!! SMALL-CONTEST" in out.err
    assert 'small_overlap: {"sat3-7": 6}' in out.out
    assert EL.main(["check", str(tmp_path / "contests.json"), str(up), st.as_posix(), "--layout", "head"]) == 0
    monkeypatch.delenv("ENTER_SMALL_MAX_SHARED")
    assert EL.main(["check", str(tmp_path / "contests.json"), str(up), st.as_posix(), "--layout", "head"]) == 1


def test_frozen_swap_keeps_the_published_map_with_the_limit_on(tmp_path, monkeypatch):
    """A Sunday swap re-publication never re-deals: with ENTER_SMALL_MAX_SHARED set it keeps the bundle's row map."""
    cs = [{"name": "sat3", "contest_id": "1", "entries": 3, "keep": 3}, {"name": "big", "contest_id": "2", "entries": 6, "keep": 6}]
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    K = EL.rows_needed(cs, "head")
    rows = _book(K, core_rows={0, 1})
    up = tmp_path / "upload.csv"
    with open(up, "w", newline="") as f:
        w = csv.writer(f); w.writerow(HDR9); w.writerows(rows)
    monkeypatch.setenv("ENTER_SMALL_MAX_SHARED", "5")
    b = tmp_path / "bundle"
    assert EL.main(["write", str(tmp_path / "contests.json"), str(up), b.as_posix(), "--layout", "head"]) == 0
    (b / f"ENTER-all-rows-1-to-{K}-are-the-KEEPERS.csv").write_text(open(up).read())   # as publication copies it
    published = json.loads((b / EL.ROWMAP_NAME).read_text())
    assert published["sat3-1"] != EL.assign_ranks(cs, "head")[0]          # the limit moved sat3's rows
    # swap two of row 1's shared players: rows 1 and 2 now share 5, so a RE-DEAL would put rank 2 back into sat3
    new = [list(r) for r in rows]; new[0][3] = "SWAPPED_A"; new[0][4] = "SWAPPED_B"
    sw = tmp_path / "swapped.csv"
    with open(sw, "w", newline="") as f:
        csv.writer(f).writerows([HDR9] + new)
    (tmp_path / "swapped.csv.swap.json").write_text(json.dumps({"swaps": [
        {"row": 1, "slot_index": 3, "out": {"dd": rows[0][3]}, "in": {"dd": "SWAPPED_A"}},
        {"row": 1, "slot_index": 4, "out": {"dd": rows[0][4]}, "in": {"dd": "SWAPPED_B"}}]}))
    redeal = EL.contest_rows(cs, K, "head", list(range(K)), [EL.row_players(HDR9, r) for r in new], 5)
    assert redeal[0] != published["sat3-1"]                   # the test can tell a re-deal from the frozen map
    out = tmp_path / "out"
    assert EL.main(["write", str(tmp_path / "contests.json"), str(sw), out.as_posix(), "--layout", "head",
                    "--frozen-bundle", b.as_posix()]) == 0
    assert json.loads((out / EL.ROWMAP_NAME).read_text()) == published


def test_overlap_limit_env_parsing_fails_closed():
    assert EL.parse_max_shared(None) is None and EL.parse_max_shared("") is None and EL.parse_max_shared(" 5 ") == 5
    for bad in ("five", "9", "-1", "5.5"):
        with pytest.raises(EL.LayoutError, match=EL.SMALL_OVERLAP_ENV):
            EL.parse_max_shared(bad)
    with pytest.raises(EL.LayoutError, match="were not supplied"):
        EL.final_ranks([{"name": "a", "contest_id": "1", "entries": 3, "keep": 3}], "head", None, 5)
    with pytest.raises(EL.LayoutError, match="player columns"):
        EL.row_players(["QB", "RB"], ["1", "2"])


def test_overlap_limit_write_check_round_trip_through_main(tmp_path, monkeypatch):
    cs = [{"name": "sat3", "contest_id": "1", "entries": 3, "keep": 3}, {"name": "big", "contest_id": "2", "entries": 6, "keep": 6}]
    (tmp_path / "contests.json").write_text(json.dumps(cs))
    K = EL.rows_needed(cs, "head")
    rows = _book(K, core_rows={0, 1})
    up = tmp_path / "upload.csv"
    with open(up, "w", newline="") as f:
        w = csv.writer(f); w.writerow(HDR9); w.writerows(rows)
    monkeypatch.setenv("ENTER_SMALL_MAX_SHARED", "5")
    st = tmp_path / "stage"
    assert EL.main(["write", str(tmp_path / "contests.json"), str(up), str(st), "--layout", "head"]) == 0
    staged = list(csv.reader(open(st / EL.enter_filename(cs[0]))))[1:]
    sets = [frozenset(r) for r in staged]
    assert all(len(a & b) <= 5 for i, a in enumerate(sets) for b in sets[i + 1:])
    assert EL.main(["check", str(tmp_path / "contests.json"), str(up), str(st), "--layout", "head"]) == 0
    monkeypatch.delenv("ENTER_SMALL_MAX_SHARED")          # the head files differ: check without the limit must fail
    assert EL.main(["check", str(tmp_path / "contests.json"), str(up), str(st), "--layout", "head"]) == 1
    monkeypatch.setenv("ENTER_SMALL_MAX_SHARED", "nine")
    with pytest.raises(EL.LayoutError):
        EL.main(["write", str(tmp_path / "contests.json"), str(up), str(st), "--layout", "head"])


def test_book_view_of_the_overlap_limit_matches_the_upload_view(tmp_path, monkeypatch):
    """The exposure sheet (book rows, player ids) and the ENTER bundle (upload rows, draftable ids) deal the same rows."""
    cs = [{"name": "sat3", "contest_id": "1", "entries": 3, "keep": 3}, {"name": "sat5", "contest_id": "2", "entries": 5, "keep": 5},
          {"name": "big", "contest_id": "3", "entries": 6, "keep": 6}]
    K = EL.rows_needed(cs, "head")
    book = _book(K, core_rows={0, 1, 4})
    upload = [[f"d-{x}" for x in r] for r in book]           # a different id space, one-to-one with the book's
    perm = list(range(K))
    up_view = EL.contest_rows(cs, K, "head", perm, [EL.row_players(HDR9, r) for r in upload], 5)
    assert EL.contest_rows_from_book(cs, book, "head", perm, 5) == up_view
    assert EL.contest_rows_from_book(cs, book, "head", perm, None) == EL.contest_rows(cs, K, "head", perm)
    assert up_view != EL.contest_rows(cs, K, "head", perm)    # the limit moved something in this book


def test_overlap_ceiling_extends_the_limit_to_larger_contests_without_touching_the_head_split(monkeypatch, tmp_path):
    """Reviewer 2026-09-30 §2: the 10-entry contests. The ceiling is its own setting: SMALL_MAX_ENTRIES (the head split)
    must not move, so with the ceiling raised and the limit off the head ranks are unchanged."""
    cs = [{"name": "sat3", "contest_id": "1", "entries": 3, "keep": 3}, {"name": "ten", "contest_id": "2", "entries": 10, "keep": 10},
          {"name": "twenty", "contest_id": "3", "entries": 20, "keep": 20}]
    head = EL.assign_ranks(cs, "head")
    K = max(max(r) for r in head) + 1
    rp = _players(_book(K, core_rows={0, 1, 2, 3}))                 # the four head rows share 7
    monkeypatch.delenv(EL.SMALL_OVERLAP_CEILING_ENV, raising=False)
    got, ch = EL.limit_small_overlap(cs, head, rp, 5)
    assert got[1] == head[1] and got[2] == head[2] and set(EL.small_overlap_record(cs, 5, ch)) == {"sat3-1"}
    monkeypatch.setenv(EL.SMALL_OVERLAP_CEILING_ENV, "10")
    assert EL.assign_ranks(cs, "head") == head                      # the head split is untouched by the ceiling
    got, ch = EL.limit_small_overlap(cs, head, rp, 5)
    assert got[1] != head[1] and got[2] == head[2]                  # the 10-entry contest is limited; the 20 is not
    ten = [rp[r] for r in got[1]]
    assert all(len(a & b) <= 5 for i, a in enumerate(ten) for b in ten[i + 1:])
    assert set(EL.small_overlap_record(cs, 5, ch)) == {"sat3-1", "ten-2"}
    for bad in ("1", "21", "ten"):
        monkeypatch.setenv(EL.SMALL_OVERLAP_CEILING_ENV, bad)
        with pytest.raises(EL.LayoutError, match=EL.SMALL_OVERLAP_CEILING_ENV):
            EL.overlap_ceiling()
    (tmp_path / "c.json").write_text(json.dumps(cs))
    with pytest.raises(EL.LayoutError, match=EL.SMALL_OVERLAP_CEILING_ENV):     # refuses before anything is written
        EL.main(["write", str(tmp_path / "c.json"), str(tmp_path / "u.csv"), str(tmp_path / "stage"), "--layout", "head"])
    assert not (tmp_path / "stage").exists()


def test_pins_are_refused_under_layouts_that_ignore_them():
    """2026-10-06, the operator's Rev2: Milly super-satellites pinned to the top rows. sequential / top have no pin
    handling, so a pinned plan there would silently deal new rows; they refuse instead. head honours the pins."""
    import pytest
    from nfl_dfs.inference import enter_layout as EL
    plan = [{"name": "milly", "contest_id": 1, "entries": 2, "keep": 2},
            {"name": "sat", "contest_id": 2, "entries": 1, "keep": 1},
            {"name": "sat2", "contest_id": 3, "entries": 1, "keep": 1},
            {"name": "supersat", "contest_id": 4, "entries": 3, "keep": 3, "ranks": [1, 2, 3]},
            {"name": "wildcat", "contest_id": 5, "entries": 2, "keep": 2}]
    for layout in ("sequential", "top"):
        with pytest.raises(EL.LayoutError, match=r"pinned contests \['supersat'\].*would ignore the pins"):
            EL.assign_ranks(plan, layout)
    ranks = EL.assign_ranks(plan, "head")
    assert ranks[3] == [0, 1, 2]                               # the pin: the top three rows, reused
    assert EL.rows_needed(plan, "head") == EL.rows_needed([c for c in plan if "ranks" not in c], "head")
    unpinned = [{k: v for k, v in c.items() if k != "ranks"} for c in plan]
    assert EL.assign_ranks(unpinned, "sequential")              # without pins sequential is unchanged
