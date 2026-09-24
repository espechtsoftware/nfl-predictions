#!/usr/bin/env python3
"""Monday outcome line for each paper arm and the entered book against the real Millionaire field (operator 155ff97b).

Per book: finish share above best = the share of the contest's entries whose points are strictly above the book's best
realized lineup (lower is better; L02's endpoint, here on the real field), book best, book mean, and 194+ / 220+ clears.
Realized lineup points use the same player points as the field's own scoring (contest_ownership fpts by display name,
as scripts/book_vs_field_scoreboard.py does); a book slot with no fpts row counts 0 and is reported as unmatched.

    python paper_arm_outcomes.py SEASON WEEK CONTEST_ID LABEL=RUN_DIR[@BOOK_CSV] ...

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
    a = ap.parse_args()
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
    rows = []
    for spec in a.books:
        label, run, book_csv = parse_book(spec)
        fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
        idx = book_rows(fr, pd.read_csv(book_csv))
        names = fr.display_name.astype(str).to_numpy()[idx]
        pts = np.vectorize(lambda n: real.get(n, 0.0))(names).sum(axis=1)
        unmatched = int(sum(n not in real for n in names.ravel()))
        rows.append({"book": label, **outcomes(pts, field), "unmatched_slots": unmatched})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).round({"finish_share_above_best": 5, "book_best": 2, "book_mean": 2}).to_string(index=False))


if __name__ == "__main__":
    main()
