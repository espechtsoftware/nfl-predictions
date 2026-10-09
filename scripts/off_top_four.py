#!/usr/bin/env python3
"""Study row 72's Monday line: off-top-four stacks (descriptive; it gates nothing).

The operator closed study 72 on 10-08 ("Close it, track Monday") after its outcome-blind census
(reports/2026-10-08-s72-off-top4-already-in-book.md, lab 2ff5982) found the idea already in the live book: 9.2 of 26 rows
stack a QB from a game ranked 5th or lower, 7.5 of them in big seats (the 2022-24 average). This is its real-field
counterpart, one line a week (the format production agreed 10-08).

GAME RANK (the census's rule): the games with at least one POOL QB, by the T-70 frame's game_total descending, ties by
game_id ascending; rank 1 is the highest total. Off-top-four = rank >= 5 (--min-rank). Pool QBs = the frame's QBs whose
projection AS THE UNION SELECTED ON IT (the union dir's proj_source.csv `fp` where it holds the id, else the frame's
mean_projection: union_reselect.apply_proj_source) is >= the receipt's min_proj, minus the receipt's unavailable_players.
CONSTRUCTION (the census counterpart): the union's book.csv dealt into the week's contests by the money gate's head
layout (moneygate_build.layout_book, as P3 does): the rows whose QB's game is off-top-four, and how many are dealt into a
big contest (the plan's big flag, p3_score.plan_big).
RESULTS: our REAL entries in each big contest (the money gate's week: W.field rows whose entry id is ours), each classified
by its own QB, with DraftKings' real points and rank; a big seat = rank <= the plan's seats. Real entries whose lineup is
not a book.csv row (late swaps, edits) are counted. A big contest with none of our entries in W falls back to the book as
dealt there (placed among the real others, P3's rule), and its line says so.
FIELD: the week's Millionaire (--milly, else the largest-field contest moneygate_score.contest_class calls "Millionaire"):
among the OTHER entrants' identified lineups, the share whose QB's game is off-top-four, and the share built that way as a
stack (the QB plus >= 1 WR / TE of his team), in the whole field and in the top 1% / 0.1% (real rank <= ceil(share x N),
N = every entry, DraftKings' ties included). A lineup's QB is the one name that maps, by canonical name, to exactly one
QB of the frame; anything else is "not identified" and printed.

    python scripts/off_top_four.py --season 2026 --week 5 --t70-run <T-70 run dir> --union <entered union dir> \\
        --plan <plan-w05-s24.json> --out-dir ~/private/off-top-four [--summary <path>] [--milly <contest id>] [--min-rank 5]

It runs only behind the money gate's reconcile receipt (as P3 and pool_hit_density do). It refuses ("OFF-TOP-FOUR
REFUSED: ...") a missing input, a --t70-run frame other than the money gate's week frame, a union built on another frame,
a union proj_source.csv other than the one its receipt names, a ranked game without one game_total, a plan that lacks a
week contest, and a book row that is not 9 frame players with one QB. Writes PRIVATE rows (<out-dir>/ott-S-wWW.parquet +
.json: every book row and every real entry of ours); prints aggregates only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CENSUS = "study 72's census: 9.2 of 26 rows, 7.5 in big seats, the 2022-24 average"
PASS_CATCHERS = ("WR", "TE")
TOPS = (("top 1%", 0.01), ("top 0.1%", 0.001))
NOT_IDENTIFIED = "not identified"
ENTRY_COLUMNS = ["source", "contest_id", "entry_id", "lineup", "qb_game", "game_rank", "group", "stacked", "points", "rank",
                 "seat", "in_book", "fallback"]


def refuse(why: str):
    raise SystemExit(f"OFF-TOP-FOUR REFUSED: {why}")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _dk(x) -> str:
    return str(x).strip().removesuffix(".0")


# ----------------------------------------------------------------------------------------------------- pure parts
def union_projection(frame: pd.DataFrame, proj_csv: pd.DataFrame | None) -> dict[str, float]:
    """Frame id -> the projection the union selected on: proj_source.csv's fp for every frame id the file holds
    (union_reselect.apply_proj_source), the frame's mean_projection for the rest."""
    proj = dict(zip(frame["id"].astype(str), pd.to_numeric(frame["mean_projection"], errors="coerce")))
    if proj_csv is not None:
        fp = dict(zip(proj_csv["id"].astype(str), pd.to_numeric(proj_csv["fp"], errors="coerce")))
        proj.update({i: float(v) for i, v in fp.items() if i in proj})
    return proj


def pool_qbs(frame: pd.DataFrame, proj: dict[str, float], min_proj: float, unavailable: set[str]) -> set[str]:
    """The frame's QBs the union's pool kept: projection >= min_proj (a missing one fails, as the union's floor does) and
    not unavailable."""
    q = frame[frame["pos"].astype(str) == "QB"]
    return {i for i in q["id"].astype(str) if i not in unavailable and bool(proj.get(i, float("nan")) >= min_proj)}


def game_ranks(frame: pd.DataFrame, pool_qb_ids: set[str]) -> pd.DataFrame:
    """The census's rule: the games with >= 1 pool QB, by game_total descending, ties by game_id ascending (rank 1 = the
    highest total). ValueError when a ranked game has no game_total or two different ones."""
    f = pd.DataFrame({"id": frame["id"].astype(str), "game_id": frame["game_id"].astype(str),
                      "game_total": pd.to_numeric(frame["game_total"], errors="coerce") if "game_total" in frame.columns
                      else np.nan})
    rows = []
    for g in sorted(set(f.loc[f["id"].isin(pool_qb_ids), "game_id"])):
        vals = sorted(set(f.loc[f["game_id"] == g, "game_total"].dropna().round(6)))
        if len(vals) != 1:
            raise ValueError(f"game {g} has game_total {vals if vals else 'missing'}")
        rows.append((g, float(vals[0])))
    out = pd.DataFrame(rows, columns=["game_id", "game_total"]).sort_values(["game_total", "game_id"], ascending=[False, True])
    out["rank"] = np.arange(1, len(out) + 1)
    return out.reset_index(drop=True)


def index_by_name(frame: pd.DataFrame, canon) -> dict[str, list[tuple[str, str, str]]]:
    """Canonical display name -> its frame entries (pos, team, game_id); a name two players share keeps both."""
    idx: dict[str, set] = {}
    for n, p, t, g in zip(frame["display_name"], frame["pos"].astype(str), frame["team"].astype(str), frame["game_id"].astype(str)):
        idx.setdefault(canon(n), set()).add((p, t, g))
    return {k: sorted(v) for k, v in idx.items()}


def classify(names, idx: dict) -> tuple[str | None, bool, str]:
    """A lineup by its canonical names -> (its QB's game, built as a stack, status). The QB is the ONE name whose frame
    entries hold a QB, and that name must hold exactly one QB; otherwise (None, False, "not identified"). A stack: >= 1
    other name whose only frame entry is a WR / TE of the QB's team."""
    cand = [(n, [e for e in idx.get(n, []) if e[0] == "QB"]) for n in names]
    cand = [(n, e) for n, e in cand if e]
    if len(cand) != 1 or len(cand[0][1]) != 1:
        return None, False, NOT_IDENTIFIED
    qn, ((_, team, game),) = cand[0]
    stacked = any(n != qn and len(idx.get(n, [])) == 1 and idx[n][0][0] in PASS_CATCHERS and idx[n][0][1] == team
                  for n in names)
    return game, stacked, "ok"


def top_cut(n_all: int, share: float) -> int:
    """The last real rank inside the top `share` of a field of n_all entries (at least 1)."""
    return max(1, math.ceil(share * n_all))


def field_shares(field: pd.DataFrame, n_all: int, ranks: dict[str, int], idx: dict, min_rank: int) -> dict:
    """field: the Millionaire's OTHER entrants (columns rank, names). Per group (the field, the top 1%, the top 0.1%):
    entries, identified lineups (QB found and his game ranked), and among those the shares off-top-four and off-top-four
    as a stack."""
    cls = [classify(nm, idx) for nm in field["names"]]
    ok = np.array([c[2] == "ok" and c[0] in ranks for c in cls], dtype=bool)
    off = np.array([c[2] == "ok" and ranks.get(c[0], 0) >= min_rank for c in cls], dtype=bool)
    stk = np.array([c[1] for c in cls], dtype=bool)
    rk = field["rank"].to_numpy(np.int64)
    out = {}
    for label, mask in [("field", np.ones(len(field), dtype=bool))] + [(lab, rk <= top_cut(n_all, s)) for lab, s in TOPS]:
        m = mask & ok
        out[label] = {"entries": int(mask.sum()), "identified": int(m.sum()),
                      "off": float(off[m].mean()) if m.any() else float("nan"),
                      "off_stack": float((off & stk)[m].mean()) if m.any() else float("nan")}
    out["not_identified"] = int((~ok).sum())
    return out


def book_qb_games(body: list[list[str]], by_dk: dict[str, tuple[str, str, str]]) -> list[str]:
    """Each book row's QB game; refuses a row that is not 9 frame players with exactly one QB."""
    out = []
    for k, row in enumerate(body):
        ids = [_dk(x) for x in row if str(x).strip()]
        miss = [x for x in ids if x not in by_dk]
        if len(ids) != 9 or miss:
            refuse(f"book row {k + 1} has {len(ids)} ids, {len(miss)} not in the T-70 frame ({miss[:3]})")
        q = [by_dk[x][2] for x in ids if by_dk[x][0] == "QB"]
        if len(q) != 1:
            refuse(f"book row {k + 1} holds {len(q)} QBs")
        out.append(q[0])
    return out


def book_stacks(body: list[list[str]], by_dk: dict[str, tuple[str, str, str]]) -> list[bool]:
    """Each book row built as a stack: >= 1 WR / TE of its QB's team (rows already checked by book_qb_games). Every MIX
    cell has qb_stack_min >= 1 today; a QB-alone row (study 77's shape) would read False."""
    out = []
    for row in body:
        ent = [by_dk[_dk(x)] for x in row if str(x).strip()]
        team = next(t for p, t, _ in ent if p == "QB")
        out.append(any(p in PASS_CATCHERS and t == team for p, t, _ in ent))
    return out


def check_inputs(t70_run: Path, union: Path, plan: Path, cfg_frame: Path) -> dict:
    """The file and identity checks (refuses on any gap): the money gate's frame, the union's own frame, its projections."""
    frame_p, book_p, rec_p = t70_run / "frame.parquet", union / "book.csv", union / "receipt.json"
    for p in (frame_p, book_p, rec_p, plan, cfg_frame):
        if not Path(p).is_file():
            refuse(f"{p} is missing")
    fsha = sha256(frame_p)
    if fsha != sha256(cfg_frame):
        refuse(f"--t70-run's frame is not the money gate's week frame ({cfg_frame})")
    rec = json.loads(rec_p.read_text())
    u = (rec.get("config") or {}).get("union") or {}
    if (u.get("input_sha256") or {}).get("t70_frame") != fsha:
        refuse(f"the union in {union} was built on another T-70 frame ({str((u.get('input_sha256') or {}).get('t70_frame'))[:12]})")
    if u.get("min_proj") is None:
        refuse(f"the union receipt in {union} has no min_proj")
    proj_csv, proj_sha = None, None
    if u.get("proj_source"):
        pp = union / "proj_source.csv"
        if not pp.is_file():
            refuse(f"the union ran on --proj-source but {pp} is missing")
        proj_sha = sha256(pp)
        if proj_sha != u["proj_source"].get("sha256"):
            refuse(f"{pp} is not the projection file the union receipt names ({str(u['proj_source'].get('sha256'))[:12]})")
        proj_csv = pd.read_csv(pp, dtype={"id": str})
    return {"frame_p": frame_p, "book_p": book_p, "frame_sha256": fsha, "receipt": rec, "min_proj": float(u["min_proj"]),
            "unavailable": {str(x) for x in ((u.get("counts") or {}).get("unavailable_players") or [])},
            "proj_csv": proj_csv, "proj_sha256": proj_sha, "receipt_sha256": sha256(rec_p), "book_sha256": sha256(book_p),
            "plan_sha256": sha256(plan)}


def _pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}%"


def _best(df: pd.DataFrame, n_field: int) -> str:
    if df.empty:
        return "best rank -"
    r = int(df["rank"].min())
    return f"best rank {r:,} (top {100.0 * r / max(n_field, 1):.2f}%)"


def contest_line(name: str, seats: int, n_field: int, ent: pd.DataFrame, fallback: bool) -> str:
    """One big contest: off-top-four vs top-four entries, best rank and big seats; the unclassified count when any."""
    o, t, u = ent[ent.group == "off"], ent[ent.group == "top"], ent[ent.group == NOT_IDENTIFIED]
    s = (f"      {name} (seats {seats}, field {n_field:,}): off-top-4 {len(o)}, {_best(o, n_field)}, seats {int(o.seat.sum())} | "
         f"top-4 {len(t)}, {_best(t, n_field)}, seats {int(t.seat.sum())}")
    if len(u):
        s += f" | QB not identified {len(u)}"
    return s + ("   (the book as dealt: none of our entries in the week data)" if fallback else "")


def results_line(ent: pd.DataFrame) -> str:
    """Our entries in big contests: per group, entries / distinct lineups, the distinct lineups' mean and best points,
    big seats."""
    def part(g):
        e = ent[ent.group == g]
        d = e.drop_duplicates("lineup")
        if e.empty:
            return "0 entries"
        return (f"{len(e)} entries / {len(d)} lineups, mean {d.points.mean():.1f}, best {d.points.max():.1f} points, "
                f"big seats {int(e.seat.sum())}")
    return f"off-top-4 {part('off')} | top-4 {part('top')} | QB not identified {int((ent.group == NOT_IDENTIFIED).sum())}"


# ------------------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--t70-run", type=Path, required=True); ap.add_argument("--union", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True); ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--summary", type=Path, default=None); ap.add_argument("--milly", default=None)
    ap.add_argument("--min-rank", type=int, default=5)
    a = ap.parse_args(argv)
    if a.min_rank < 2:
        refuse(f"--min-rank {a.min_rank}: at least 2")
    M = _load("moneygate_score"); B = _load("moneygate_build"); P3 = _load("p3_score")
    rec = json.loads(M.receipt_path().read_text()) if M.receipt_path().is_file() else {}
    if a.week not in rec.get("weeks", []):
        refuse(f"the reconcile receipt does not cover week {a.week} (run moneygate_score.py reconcile)")
    M.require_reconcile(sorted(rec["weeks"]))                    # PASS, the scorer's sha, the week's data unchanged
    cfg = M.load_config()
    W = M.load_week(cfg, a.week)
    inp = check_inputs(a.t70_run, a.union, a.plan, Path(cfg["weeks"][str(a.week)]["t70_run"]) / "frame.parquet")
    fr = pd.read_parquet(inp["frame_p"]).drop_duplicates("id")

    # the game rank (the census's rule, on the union's own pool)
    proj = union_projection(fr, inp["proj_csv"])
    pqb = pool_qbs(fr, proj, inp["min_proj"], inp["unavailable"])
    try:
        games = game_ranks(fr, pqb)
    except ValueError as e:
        refuse(str(e))
    ranks = dict(zip(games.game_id, games["rank"].astype(int)))
    idx = index_by_name(fr, M.canon)
    by_dk = {_dk(k): (str(p), str(t), str(g)) for k, p, t, g in zip(fr["dk_player_id"], fr["pos"], fr["team"], fr["game_id"])}

    def group_of(game: str | None, status: str) -> str:
        if status != "ok" or game not in ranks:
            return NOT_IDENTIFIED
        return "off" if ranks[game] >= a.min_rank else "top"

    # construction: the book as built, dealt by the head layout
    big = P3.plan_big(a.plan)
    missing = [str(c["contest_id"]) for c in W.contests if str(c["contest_id"]) not in big]
    if missing:
        refuse(f"the plan {a.plan.name} lacks contests {missing}")
    _, body = B.read_book(inp["book_p"])
    bq = book_qb_games(body, by_dk)
    bs = book_stacks(body, by_dk)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    stem = a.out_dir / f"ott-{a.season}-w{a.week:02d}"
    layout = B.layout_book(W.contests, inp["book_p"], a.out_dir / f"stage-{a.season}-w{a.week:02d}")
    big_cids = [str(c["contest_id"]) for c in W.contests if big[str(c["contest_id"])][0]]
    dealt_big = {r for cid in big_cids for r in layout[cid]["rows"]}
    book_off = [ranks.get(g, 0) >= a.min_rank for g in bq]
    big_entries = sum(len(layout[cid]["rows"]) for cid in big_cids)
    big_off_entries = sum(book_off[r] for cid in big_cids for r in layout[cid]["rows"])

    # results: our real entries in each big contest, each by its own QB (the book as dealt where W has none of ours)
    book_sets = {frozenset(W.name_of[_dk(x)] for x in row if str(x).strip()) for row in body}
    ours_all = W.field[W.field.entry_id.isin(W.ours)]
    not_in_book = int(sum(frozenset(n) not in book_sets for n in ours_all.names))
    ent_rows, lines = [], []
    for cid in big_cids:
        seats = big[cid][1]
        name = (W.details.get(cid) or {}).get("name") or cid
        fc = W.field[W.field.contest_id == cid]
        mine = fc[fc.entry_id.isin(W.ours)]
        fallback = mine.empty
        if fallback:                                             # P3's rule: the dealt lineups placed among the real others
            names = [[W.name_of[_dk(x)] for x in lu] for lu in layout[cid]["lineups"]]
            pts = np.array([M.lineup_points(nm, W.fpts, impute_missing=True)[0] for nm in names], dtype=np.int64)
            others = W.others_sorted(cid)
            res = M.place(pts, others, M.Ladder.from_details(W.details[cid]))
            n_field = len(others) + len(pts)
            rows = [(f"book-{r + 1}", tuple(nm), int(p), int(rk)) for r, nm, p, rk in zip(layout[cid]["rows"], names, pts, res["rank"])]
        else:
            n_field = len(fc)
            rows = [(str(e), tuple(nm), int(p), int(rk)) for e, nm, p, rk in zip(mine.entry_id, mine.names, mine.points, mine["rank"])]
        for eid, nm, p, rk in rows:
            game, stacked, status = classify(nm, idx)
            ent_rows.append({"source": "entry", "contest_id": cid, "entry_id": eid, "lineup": "|".join(sorted(nm)),
                             "qb_game": game, "game_rank": ranks.get(game), "group": group_of(game, status), "stacked": stacked,
                             "points": p / 100.0, "rank": rk, "seat": rk <= seats, "in_book": frozenset(nm) in book_sets,
                             "fallback": fallback})
        e = pd.DataFrame([r for r in ent_rows if r["contest_id"] == cid], columns=ENTRY_COLUMNS)
        lines.append(contest_line(name, seats, n_field, e, fallback))
    ent = pd.DataFrame(ent_rows, columns=ENTRY_COLUMNS)

    # the field: the Millionaire's other entrants
    millys = [str(c["contest_id"]) for c in W.contests if M.contest_class((W.details.get(str(c["contest_id"])) or {}).get("name", "")) == "Millionaire"]
    milly = str(a.milly) if a.milly else (max(millys, key=lambda c: int((W.field.contest_id == c).sum())) if millys else None)
    fs = None
    if milly is not None:
        fm = W.field[W.field.contest_id == milly]
        if fm.empty:
            refuse(f"the Millionaire {milly} has no field rows in the week data")
        fs = field_shares(fm[~fm.entry_id.isin(W.ours)], len(fm), ranks, idx, a.min_rank)

    # private rows + sidecar
    book_df = pd.DataFrame({"source": "book", "contest_id": None, "entry_id": [f"book-{k + 1}" for k in range(len(body))],
                            "lineup": ["|".join(sorted(W.name_of[_dk(x)] for x in row if str(x).strip())) for row in body],
                            "qb_game": bq, "game_rank": [ranks.get(g) for g in bq],
                            "group": [group_of(g, "ok") for g in bq], "stacked": bs, "points": np.nan, "rank": np.nan,
                            "seat": False, "in_book": True, "fallback": False,
                            "dealt_big": pd.array([k in dealt_big for k in range(len(body))], dtype="boolean")})
    ent_out = ent.assign(dealt_big=pd.array([pd.NA] * len(ent), dtype="boolean"))
    pd.concat([book_df, ent_out], ignore_index=True).to_parquet(f"{stem}.parquet")
    side = {"week": a.week, "season": a.season, "min_rank": a.min_rank, "games": games.to_dict("records"),
            "pool_qbs": len(pqb), "unavailable": len(inp["unavailable"]), "min_proj": inp["min_proj"],
            "milly": milly, "field": fs, "not_in_book": not_in_book, "our_entries": int(len(ours_all)),
            "inputs": {"frame_sha256": inp["frame_sha256"], "book": str(inp["book_p"]), "book_sha256": inp["book_sha256"],
                       "union_receipt_sha256": inp["receipt_sha256"], "proj_source_sha256": inp["proj_sha256"],
                       "plan": str(a.plan), "plan_sha256": inp["plan_sha256"], "scorer_sha256": M.sha256(M.SCORER),
                       "week_receipt": json.loads((M.data_dir() / f"w{a.week}_receipt.json").read_text())},
            "rows_sha256": sha256(Path(f"{stem}.parquet")), "written_utc": datetime.now(timezone.utc).isoformat()}
    Path(f"{stem}.json").write_text(json.dumps(side, indent=1, default=str) + "\n")

    buf = io.StringIO()
    with redirect_stdout(buf):
        top4 = " / ".join(f"{t:g}" for t in games.game_total.head(a.min_rank - 1))
        print(f"== OFF-TOP-FOUR STACKS {a.season} W{a.week} -- descriptive, gates nothing; the real-field counterpart of {CENSUS}")
        print(f"   games ranked by the T-70 game_total over the {len(games)} with a pool QB ({len(pqb)} pool QBs: the union's "
              f"projections >= {inp['min_proj']:g}, minus {len(inp['unavailable'])} unavailable; ties: game_id); top "
              f"{a.min_rank - 1}: {top4}")
        print(f"   BOOK (as built, dealt by the head layout): {sum(book_off)} of {len(body)} rows stack a QB from a game ranked "
              f"{a.min_rank}+; {sum(book_off[k] for k in dealt_big)} of them dealt into big contests ({big_off_entries} of "
              f"{big_entries} big entries)")
        print(f"   RESULTS (our real entries in big contests, each by its own QB): {results_line(ent)}; our entries not a "
              f"book row: {not_in_book} of {len(ours_all)}")
        for ln in lines:
            print(ln)
        if fs is None:
            print("   MILLIONAIRE: no Millionaire this week")
        else:
            g = [("field", "field")] + [(lab, lab) for lab, _ in TOPS]
            print(f"   MILLIONAIRE {milly} ({fs['field']['entries']:,} other entries; ours removed): QB from a game ranked "
                  f"{a.min_rank}+: " + " | ".join(f"{lab} {_pct(fs[k]['off'])}" for k, lab in g)
                  + ";  as a stack: " + " | ".join(f"{lab} {_pct(fs[k]['off_stack'])}" for k, lab in g)
                  + f";  QB not identified: {fs['not_identified']}")
    text = buf.getvalue()
    print(text, end="")
    if a.summary:
        a.summary.parent.mkdir(parents=True, exist_ok=True)
        with a.summary.open("a") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
