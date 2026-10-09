#!/usr/bin/env python3
"""Tag every ENTERED lineup with how it was built, and join its settled result (the operator 10-09: "Do we tag each lineup so
that we know which strategy was used to select them?").

The union run records each book row's build tag in book.json (`mix_<cell>` for the shape mix, else the main's name), the
cheap block's book positions in receipt.json (config.union.mix.mix.term.term_positions, 0-based), the tail sleeve in
book.json's `tail_sleeve` and the mix spares in candidates.parquet (source_run `mix_spare`). The DraftKings upload keeps only
the nine players, so this script recovers each entered lineup's build record by its ROSTER (a set of canonical names), after
settlement, from the money gate's settled field (moneygate_score.load_week: our entries by entry id, their names):
  book        a book row: its rank, tag (cell), and whether its position is in the cheap (term) block;
  tail        a tail-sleeve row;
  replacement a Sunday replacement (the after-build chain's replace.json, --after): the removed row's cell (or "house" when
              it fell back) and its union rank, so a cheap-block row replaced on Sunday stays in its block;
  spare       a mix spare (the Sunday replacement pool), tagged with its cell;
  corpus      any other union candidate (a Sunday replacement drawn from the corpus), with the candidate's tag;
  unmatched   none of the above (a hand-added lineup, or a late swap on DraftKings).
Each entry's result comes from the money gate's reconcile file (rank, cash, ticket; the known-answer path), its buckets as
the calibration check defines them: top 1% / top 10% of the contest's entries, a cash (cash or ticket), a big win (cash >=
$500 or a ticket >= $300, his 10-05 rule).

READ-ONLY: changes nothing in the build or the money path. Private rows (entry ids) go to --out (default
~/private/entry_tags/w<W>.csv); stdout carries aggregates only (counts per tag; no ids, no dollars).

  python scripts/entry_tags.py --week 5 [--run <union run dir>] [--after <the T-70 after-build dir>] [--out <csv>]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402  (the gate's config, settled field, entry history, canon)

BIG_CASH, BIG_TICKET = 500.0, 300.0          # moneygate_describe.BIG_CASH / BIG_TICKET (his 10-05 rule)
KINDS = ("book", "tail", "replacement", "spare", "corpus", "unmatched")
REPLACE_DIRS = ("paid-vetted-replaced", "paid-vetted-replaced-fresh")   # sunday_after_build.sh / the run_promotion path


def roster_key(names) -> frozenset:
    return frozenset(MS.canon(n) for n in names)


def term_positions(receipt: dict) -> list[int]:
    term = ((((receipt.get("config") or {}).get("union") or {}).get("mix") or {}).get("mix") or {}).get("term") or {}
    return [int(p) for p in (term.get("term_positions") or [])]


def replace_file(after: Path) -> Path | None:
    """The after-build dir's replace.json (exactly one of REPLACE_DIRS), or None when the dir holds none."""
    found = [after / d / "replace.json" for d in REPLACE_DIRS if (after / d / "replace.json").exists()]
    if len(found) > 1:
        raise SystemExit(f"{after}: more than one replace.json ({[str(f) for f in found]}); pass the one entered as --after's parent")
    return found[0] if found else None


def build_index(book: dict, cands: pd.DataFrame, term_pos: list[int], replacements: list[dict] = ()) -> dict[frozenset, dict]:
    """roster -> its build record; the first source in KINDS order wins (a book row is never re-labelled by the corpus).
    A replacement carries the removed row's union rank (source_rank: the 1-based row of the union's book.csv, i.e. book.json's
    rank for the book rows, then the tail sleeve in order) and cell; a removed TAIL row (source_rank > the book's rows) is
    never in the cheap block and has no book cell."""
    idx: dict[frozenset, dict] = {}
    tset = set(term_pos)
    for e in book.get("entries") or []:
        idx.setdefault(roster_key(e["players"]), {"kind": "book", "book_rank": int(e["rank"]), "tag": str(e.get("tag")),
                                                  "term": (int(e["rank"]) - 1) in tset, "source_run": e.get("source_run")})
    for e in book.get("tail_sleeve") or []:
        idx.setdefault(roster_key(e["players"]), {"kind": "tail", "book_rank": int(e["rank"]), "tag": str(e.get("tag")),
                                                  "term": False, "source_run": e.get("source_run")})
    n_book = len(book.get("entries") or [])
    for r in replacements:
        rank = int(r["source_rank"]) if r.get("source_rank") is not None else None
        tail = rank is not None and rank > n_book
        idx.setdefault(roster_key(r["replacement"]), {"kind": "replacement", "book_rank": rank,
                                                      "removed_kind": None if rank is None else ("tail" if tail else "book"),
                                                      "tag": f"mix_{r['cell']}" if r.get("cell") and not tail else None,
                                                      "term": rank is not None and not tail and (rank - 1) in tset,
                                                      "source_run": r.get("candidate_source"), "cell_fallback": bool(r.get("cell_fallback"))})
    src = cands.get("source_run", pd.Series([""] * len(cands))).astype(str)
    for names, tag, s in zip(cands["names"].astype(str), cands["tag"].astype(str), src):
        if s == "mix_spare":
            idx.setdefault(roster_key(names.split("|")), {"kind": "spare", "book_rank": None, "tag": tag, "term": False, "source_run": s})
    for names, tag, s in zip(cands["names"].astype(str), cands["tag"].astype(str), src):
        idx.setdefault(roster_key(names.split("|")), {"kind": "corpus", "book_rank": None, "tag": tag, "term": False, "source_run": s})
    return idx


def tag_entries(ours: pd.DataFrame, idx: dict[frozenset, dict], recon: pd.DataFrame, n_by_contest: dict[str, int]) -> pd.DataFrame:
    """ours: contest_id, entry_id, names (tuple). recon: contest_id, entry_id, rank_calc, cash_calc, ticket_calc (str ids)."""
    r = recon.set_index(["contest_id", "entry_id"])
    rows = []
    for cid, eid, names in zip(ours.contest_id.astype(str), ours.entry_id.astype(str), ours.names):
        rec = idx.get(roster_key(names), {"kind": "unmatched", "book_rank": None, "tag": None, "term": False, "source_run": None})
        out = {"contest_id": cid, "entry_id": eid, "n_entries": int(n_by_contest[cid]), **rec}
        if (cid, eid) in r.index:
            x = r.loc[(cid, eid)]
            rank, cash, ticket = int(x.rank_calc), float(x.cash_calc), float(x.ticket_calc)
            n = out["n_entries"]
            out.update({"settled": True, "finish_rank": rank,
                        "top1": rank <= max(1, int(np.floor(0.01 * n))), "top10": rank <= max(1, int(np.floor(0.10 * n))),
                        "cash": (cash + ticket) > 1e-9, "big": cash >= BIG_CASH - 1e-9 or ticket >= BIG_TICKET - 1e-9})
        else:
            out.update({"settled": False, "finish_rank": None, "top1": None, "top10": None, "cash": None, "big": None})
        rows.append(out)
    return pd.DataFrame(rows)


def label(row) -> str:
    if row["kind"] == "book":
        return f"{row['tag']}{' +cheap block' if row['term'] else ''}"
    if row["kind"] == "replacement":
        if row.get("removed_kind") == "tail":
            return "replacement:tail"
        return f"replacement:{row['tag']}{' +cheap block' if row['term'] is True else ''}"
    return f"{row['kind']}:{row['tag']}" if isinstance(row["tag"], str) and row["tag"] else row["kind"]


def aggregates(t: pd.DataFrame) -> list[dict]:
    s = t[t.settled]
    out = []
    for lab, g in sorted(s.groupby(s.apply(label, axis=1)), key=lambda kv: -len(kv[1])):
        out.append({"group": lab, "entries": int(len(g)), "cash": int(g.cash.sum()), "top10": int(g.top10.sum()),
                    "top1": int(g.top1.sum()), "big": int(g.big.sum())})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--run", type=Path, default=None, help="the union run dir (default: the week's entered_union, else t70_run)")
    ap.add_argument("--after", type=Path, default=None, help="the entered after-build dir (its replace.json); read-only")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    cfg = MS.load_config()
    e = cfg["weeks"][str(a.week)]
    run = a.run or Path(e.get("entered_union") or e["t70_run"])
    book = json.loads((run / "book.json").read_text())
    receipt = json.loads((run / "receipt.json").read_text())
    cands = pd.read_parquet(run / "candidates.parquet")
    tpos = term_positions(receipt)
    rf = replace_file(a.after) if a.after else None
    rj = json.loads(rf.read_text()) if rf else {}
    if rf and str(rj.get("status", "")).upper() == "FAILED":
        raise SystemExit(f"{rf}: a FAILED replacement run; pass the after-build dir that was entered")
    reps = rj.get("replacements") or []
    idx = build_index(book, cands, tpos, reps)
    W = MS.load_week(cfg, a.week)
    ours = W.field[W.field.entry_id.isin(W.ours)]
    n_hist = len(W.history)
    if len(ours) != n_hist:
        raise SystemExit(f"W{a.week}: {n_hist} entries in the history but {len(ours)} in the settled field")
    n_by_contest = W.field.groupby("contest_id").size().to_dict()
    recon = pd.read_csv(MS.PRIVATE / "reconcile_entries.csv", dtype={"entry_id": str, "contest_id": str})
    recon = recon[recon.week == a.week]
    t = tag_entries(ours, idx, recon, n_by_contest)
    t.insert(0, "week", a.week)
    out = a.out or Path.home() / "private" / "entry_tags" / f"w{a.week}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(out, index=False)
    kinds = t.kind.value_counts().to_dict()
    n_book_term = int((t.kind.eq("book") & t.term).sum())
    print(f"ENTRY TAGS W{a.week}: run {run.name}  entries {len(t)} (settled {int(t.settled.sum())})  "
          + "  ".join(f"{k} {kinds.get(k, 0)}" for k in KINDS)
          + f"  cheap-block entries {n_book_term} (book positions in the block: {len(tpos)})  replacements read {len(reps)}"
          + f" ({rf if rf else 'no --after'})  private rows -> {out}")
    print("  by build group (settled entries; counts, no ids, no dollars):")
    for g in aggregates(t):
        print(f"    {g['group']:28s} entries {g['entries']:4d}  cash {g['cash']:3d}  top 10% {g['top10']:3d}  top 1% {g['top1']:2d}  big {g['big']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
