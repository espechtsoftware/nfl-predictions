#!/usr/bin/env python3
"""Monday outcome line for each paper arm and the entered book against the real Millionaire field (operator 155ff97b).

Per book: finish share above best = the share of the contest's entries whose points are strictly above the book's best
realized lineup (lower is better; L02's endpoint, here on the real field), book best, book mean, and 194+ / 220+ clears.
Realized lineup points use the same player points as the field's own scoring (contest_ownership fpts by display name,
as scripts/book_vs_field_scoreboard.py does); a book slot with no fpts row counts 0 and is reported as unmatched.

    python paper_arm_outcomes.py SEASON WEEK CONTEST_ID LABEL=RUN_DIR[@BOOK_CSV] ... [--layouts SIZES --sets SETS_CSV]

Layout line (operator 97defaf9, external review 2026-09-24 section 5.4): with --layouts, each book is also dealt to the week's
contests under four layouts and scored per contest (each contest weighted equally): `sequential/greedy` (the pre-Week-3
default), and `snake`, `top` and `head` in the fewest-LOW-then-greedy order. SIZES is the contest list in contests.json
order as NAME:ENTRIES[xCOUNT] (the sizes are in HANDOFF; contests.json itself is never read), e.g.
wildcat:2x2,sat20:1x19,ffwc:4,supersat2:5x12,supersat25hi:17x3,supersat25lo:20x3. `head` and `top` use production's
enter_layout module (the rule the ENTER writer uses); snake deals one row per contest per round, reversing each round.

RUN_DIR is a lab live run directory (frame.parquet; book.csv unless @BOOK_CSV names another book, e.g. the entered book
mapped through the paper frame's DK ids). Read-only against BigQuery; writes nothing. Run only after the week's outcomes
are released and the standings are imported.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from book_vs_field_scoreboard import book_rows  # noqa: E402

THRESH = (194.0, 220.0)


def outcomes(book_points: np.ndarray, field_points: np.ndarray) -> dict:
    """Endpoints for one book's realized lineup points against the field's entry points."""
    best = float(book_points.max())
    return {"n": len(book_points), "finish_share_above_best": float((field_points > best).mean()),
            "book_best": best, "book_mean": float(book_points.mean()),
            **{f"clears_{int(t)}": int((book_points >= t).sum()) for t in THRESH}}


def parse_sizes(spec: str) -> list[dict]:
    out = []
    for part in spec.split(","):
        name, _, rest = part.partition(":")
        n, _, count = rest.partition("x")
        for _ in range(int(count or 1)):
            out.append({"name": name, "contest_id": str(len(out) + 1), "entries": int(n), "keep": int(n)})
    return out


def snake_ranks(contests: list[dict]) -> list[list[int]]:
    """Unique rows, dealt one per contest per round in contest order, reversing each round."""
    out, left, nxt, rnd = [[] for _ in contests], [int(c["entries"]) for c in contests], 0, 0
    while any(left):
        for i in (range(len(contests)) if rnd % 2 == 0 else reversed(range(len(contests)))):
            if left[i]:
                out[i].append(nxt)
                nxt += 1
                left[i] -= 1
        rnd += 1
    return out


def layout_lines(book_ids: list[list[str]], pts: np.ndarray, contests: list[dict], low_ids: set[str]) -> list[dict]:
    """Per layout: the mean over contests of each contest's best and average realized lineup."""
    from nfl_dfs.inference.enter_layout import assign_ranks, fewest_low_order
    fewest = fewest_low_order(book_ids, low_ids, set(), False)
    greedy = list(range(len(book_ids)))
    rows = []
    for name, ranks, perm in (("sequential/greedy", assign_ranks(contests, "sequential"), greedy),
                              ("snake/fewest-low", snake_ranks(contests), fewest),
                              ("top/fewest-low", assign_ranks(contests, "top"), fewest),
                              ("head/fewest-low", assign_ranks(contests, "head"), fewest)):
        need = max(max(r) for r in ranks) + 1
        if need > len(book_ids):
            rows.append({"layout": name, "note": f"needs {need} rows, the book has {len(book_ids)}"})
            continue
        per = [pts[[perm[r] for r in rs]] for rs in ranks]
        rows.append({"layout": name, "contest_best": float(np.mean([p.max() for p in per])),
                     "contest_mean": float(np.mean([p.mean() for p in per])),
                     "entries_194": int(sum((p >= 194).sum() for p in per)),
                     "distinct_rows": len({perm[r] for rs in ranks for r in rs})})
    return rows


def parse_book(spec: str) -> tuple[str, Path, Path]:
    label, _, rest = spec.partition("=")
    if not label or not rest:
        raise SystemExit(f"book spec {spec!r}: expected LABEL=RUN_DIR[@BOOK_CSV]")
    run, _, book = rest.partition("@")
    return label, Path(run).expanduser(), Path(book).expanduser() if book else Path(run).expanduser() / "book.csv"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("season", type=int)
    ap.add_argument("week", type=int)
    ap.add_argument("contest_id")
    ap.add_argument("books", nargs="+", help="LABEL=RUN_DIR[@BOOK_CSV]")
    ap.add_argument("--layouts", help="contest sizes NAME:ENTRIES[xCOUNT],... in contests.json order")
    ap.add_argument("--sets", type=Path, help="the week's ownership sets file (LOW labels by dk_player_id)")
    a = ap.parse_args()
    if a.layouts and not (a.sets and a.sets.is_file()):
        raise SystemExit("--layouts needs --sets (the week's ownership sets file) for the fewest-LOW order")
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    fpts = query_df(f"SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership` "
                    f"WHERE season={a.season} AND week={a.week} GROUP BY 1")
    real = dict(zip(fpts.display_name.astype(str), fpts.fpts.astype(float)))
    field = query_df(f"SELECT points FROM `{settings.raw}.contest_entries` "
                     f"WHERE season={a.season} AND week={a.week} AND contest_id='{a.contest_id}'").points.to_numpy(float)
    if not len(field) or not real:
        raise SystemExit(f"no contest_entries / contest_ownership for {a.season} week {a.week} contest {a.contest_id}")
    print(f"field {len(field)} entries; field best {field.max():.2f}")
    rows, lay = [], []
    contests = parse_sizes(a.layouts) if a.layouts else None
    if contests:
        try:
            import nfl_dfs.inference.enter_layout  # noqa: F401  (merged with the head layout, 2026-09-24)
        except ImportError:
            print("layout line skipped: nfl_dfs.inference.enter_layout is not in this checkout (head layout not merged)")
            contests = None
    if contests:
        s = pd.read_csv(a.sets, dtype={"dk_player_id": str})
        low_ids = set(s.loc[s["set"] == "LOW", "dk_player_id"].astype(str))
    for spec in a.books:
        label, run, book_csv = parse_book(spec)
        fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
        idx = book_rows(fr, pd.read_csv(book_csv))
        names = fr.display_name.astype(str).to_numpy()[idx]
        pts = np.vectorize(lambda n: real.get(n, 0.0))(names).sum(axis=1)
        unmatched = int(sum(n not in real for n in names.ravel()))
        rows.append({"book": label, **outcomes(pts, field), "unmatched_slots": unmatched})
        if contests:
            ids = pd.read_csv(book_csv, dtype=str).to_numpy().tolist()
            lay += [{"book": label, **r} for r in layout_lines(ids, pts, contests, low_ids)]
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).round({"finish_share_above_best": 5, "book_best": 2, "book_mean": 2}).to_string(index=False))
    if lay:
        print(f"\nlayout line ({len(contests)} contests, {sum(c['entries'] for c in contests)} entries; "
              "each contest weighted equally)")
        print(pd.DataFrame(lay).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
