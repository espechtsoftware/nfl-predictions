"""Row-level regeneration lineage (audit VET-001): every changed row needs a receipted reason, hashes bind books,
promotion is the recorded permutation, upload and entries files carry the promoted book, manifest is create-once."""
import csv, hashlib, json
import pandas as pd
import pytest

from nfl_dfs.inference import regeneration_lineage as rl

IDS = [str(1000 + i) for i in range(20)]
NAMES = {i: f"Player{i}" for i in IDS}
POS = ["QB"] * 3 + ["RB"] * 5 + ["WR"] * 6 + ["TE"] * 3 + ["DST"] * 3


def _frame(path):
    pd.DataFrame({"dk_player_id": [int(i) for i in IDS], "dk_draftable_id": [int(i) + 50000 for i in IDS], "name": [NAMES[i] for i in IDS], "pos": POS}).to_parquet(path)


def _write_book(path, rows):
    with open(path, "w", newline="") as h:
        w = csv.writer(h); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); [w.writerow(r) for r in rows]


def _sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def _row(qb, rbs, wrs, te, flex, dst): return (IDS[qb], IDS[rbs[0]], IDS[rbs[1]], IDS[wrs[0]], IDS[wrs[1]], IDS[wrs[2]], IDS[te], IDS[flex], IDS[dst])


def make_chain(tmp, *, break_reason=False, extra_change=False, bad_perm=False, bad_upload=False, wrong_reason=False):
    vetted = [_row(0, (3, 4), (8, 9, 10), 14, 5, 17), _row(1, (3, 5), (9, 10, 11), 15, 6, 18), _row(2, (4, 6), (8, 11, 12), 16, 7, 19), _row(0, (5, 7), (10, 12, 13), 14, 3, 17)]
    replaced = list(vetted); replaced[2] = _row(2, (4, 6), (8, 11, 13), 16, 7, 19)      # WR Player1012 -> Player1013 (row 3)
    if extra_change: replaced[0] = _row(0, (3, 4), (8, 9, 11), 14, 5, 17)               # a second change with no receipt
    perm = [3, 1, 2, 4] if not bad_perm else [1, 2, 3, 4]
    promoted = [replaced[p - 1] for p in [3, 1, 2, 4]]
    d = {k: tmp / k for k in ("vetted", "replaced", "promoted")}
    for k in d: d[k].mkdir(); _frame(d[k] / "frame.parquet")
    _write_book(d["vetted"] / "book.csv", vetted); _write_book(d["replaced"] / "book.csv", replaced); _write_book(d["promoted"] / "book.csv", promoted)
    reasons = {} if break_reason else {NAMES[IDS[12]]: ("dk:OUT" if not wrong_reason else "dk:Q")}
    receipt = {"version": "vet-replace-v4.3", "exclusion_set": {NAMES[IDS[12]]: "dk:OUT", NAMES[IDS[2]]: "backup_qb:x"} if False else {NAMES[IDS[12]]: "dk:OUT"},
               "removed_positions": [3], "replacements": [{"vetted_position": 3, "source_rank": 1, "removed": [NAMES[i] for i in vetted[2]], "removed_because": reasons,
                                                          "replacement": [NAMES[i] for i in replaced[2]], "candidate_index": 42}],
               "input_sha256": {str(d["vetted"] / "book.csv"): _sha(d["vetted"] / "book.csv")}, "output_sha256": {"book.csv": _sha(d["replaced"] / "book.csv")}}
    (d["replaced"] / "replace.json").write_text(json.dumps(receipt))
    promo = {"permutation": perm, "moved_rows": [{"position_before": 3, "position_after": 1, "contest_before": "flea", "contest_after": "milly"}, {"position_before": 1, "position_after": 2, "contest_before": "milly", "contest_after": "flea"}, {"position_before": 2, "position_after": 3, "contest_before": "flea", "contest_after": "flea"}],
             "input_sha256": {"replaced/book.csv": _sha(d["replaced"] / "book.csv")}, "output_sha256": {"book.csv": _sha(d["promoted"] / "book.csv")}}
    (d["promoted"] / "promotion.json").write_text(json.dumps(promo))
    up = tmp / "upload.csv"
    with open(up, "w", newline="") as h:
        w = csv.writer(h); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        rows = promoted if not bad_upload else promoted[::-1]
        [w.writerow([str(int(i) + 50000) for i in r]) for r in rows]
    ent = tmp / "DKEntries.csv"
    with open(ent, "w", newline="") as h:
        w = csv.writer(h); w.writerow(["Entry ID", "Contest Name", "Contest ID", "Entry Fee", "QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        for k, r in enumerate(promoted[::-1]):                       # contest-grouped: different order, same multiset
            w.writerow([str(9000 + k), "c", "1", "$1", *[f"{NAMES[i]} ({int(i) + 50000})" for i in r]])
    return d, up, ent


def test_real_shape_passes_and_manifest_is_create_once(tmp_path):
    d, up, ent = make_chain(tmp_path)
    m = rl.build_manifest(d["vetted"], d["replaced"], d["promoted"], upload_csv=up, entries_csv=ent)
    assert m["status"] == "OK" and m["problems"] == [] and m["changed_rows"] == 1
    row = m["lineage"][0]; assert row["upload_row"] == 3 and row["final_position"] == 1 and row["reasons"] == {"Player1012": "dk:OUT"}
    assert m["promotion"]["moved"] == [[1, 2], [2, 3], [3, 1]] or m["promotion"]["moved"] == [(1, 2), (2, 3), (3, 1)]
    assert m["upload_checks"]["upload_csv"]["check"] == "ordered" and m["upload_checks"]["entries_export"]["check"] == "multiset"
    out = tmp_path / "lineage.json"; rl.write_manifest_create_once(m, out); assert json.loads(out.read_text())["status"] == "OK"
    with pytest.raises(rl.LineageError, match="create-once"):
        rl.write_manifest_create_once(m, out)


@pytest.mark.parametrize("kw,needle", [
    (dict(break_reason=True), "without a recorded reason"),
    (dict(extra_change=True), "changed rows do not match the receipt"),
    (dict(wrong_reason=True), "not the exclusion set"),
    (dict(bad_perm=True), "not replaced row"),
    (dict(bad_upload=True), "differ from the promoted book in order"),
])
def test_every_lineage_defect_fails_closed(tmp_path, kw, needle):
    d, up, ent = make_chain(tmp_path, **kw)
    m = rl.build_manifest(d["vetted"], d["replaced"], d["promoted"], upload_csv=up, entries_csv=ent)
    assert m["status"] == "FAILED" and any(needle in p for p in m["problems"]), m["problems"]


def test_hash_binding_failure(tmp_path):
    d, up, ent = make_chain(tmp_path)
    r = json.loads((d["replaced"] / "replace.json").read_text()); r["output_sha256"]["book.csv"] = "0" * 64
    (d["replaced"] / "replace.json").write_text(json.dumps(r))
    m = rl.build_manifest(d["vetted"], d["replaced"], d["promoted"])
    assert m["status"] == "FAILED" and any("does not bind the replaced book" in p for p in m["problems"])
