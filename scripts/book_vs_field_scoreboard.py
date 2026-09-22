#!/usr/bin/env python3
"""Monday book-vs-field scoreboard (external review §6.1).

For the Millionaire field, the field's top 1%, our live candidate pool and our entered book, report per
lineup: our served projection, realized DK points, skill slots with no box-score line ("did not play"),
and realized minus projection among skill players who played.  Splits a week's gap to the field into
availability (dead slots), information (played-player gap) and construction (the rest).

    python scripts/book_vs_field_scoreboard.py RUN_DIR SEASON WEEK CONTEST_ID [--book book.csv]

RUN_DIR is a lab live run directory (frame.parquet, candidates.parquet, book.csv).  Reads BigQuery
(weekly_stats, contest_ownership, contest_entries); writes nothing.  Run only after the operator has
released the week's outcomes.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")


def player_arrays(fr: pd.DataFrame, played: set[str], real: dict[str, float], pcol: str) -> dict:
    """Per-frame-row arrays used by summarize(); real is keyed by display_name (0 when absent)."""
    skill = fr.position.isin(SKILL).to_numpy()
    dnp = skill & ~fr.gsis_id.astype(str).isin(played).to_numpy()
    r = np.array([real.get(str(n), 0.0) for n in fr.display_name], float)
    p = pd.to_numeric(fr[pcol], errors="coerce").fillna(0.0).to_numpy(float)
    pl = skill & ~dnp
    return {"proj": p, "real": r, "dnp": dnp.astype(float), "gap": np.where(pl, r - p, 0.0),
            "played": pl.astype(float)}


def summarize(a: dict, idx: np.ndarray) -> dict:
    """idx: (n_lineups, 9) frame row indices."""
    n_pl = np.maximum(a["played"][idx].sum(1), 1)
    return {"n": len(idx), "proj": a["proj"][idx].sum(1).mean(), "realized": a["real"][idx].sum(1).mean(),
            "dnp_slots": a["dnp"][idx].sum(1).mean(), "gap_played": a["gap"][idx].sum(1).mean(),
            "gap_per_played": (a["gap"][idx].sum(1) / n_pl).mean()}


def book_rows(fr: pd.DataFrame, book: pd.DataFrame) -> np.ndarray:
    """Map a DK upload-style book (ids per slot) to frame rows; the id column is detected, not assumed."""
    ids = set(book.to_numpy().ravel().astype(int))
    cols = [c for c in ("dk_draftable_id", "dk_player_id") if c in fr]
    col = max(cols, key=lambda c: len(ids & set(pd.to_numeric(fr[c], errors="coerce").dropna().astype(int))))
    m = {int(v): i for i, v in enumerate(pd.to_numeric(fr[col], errors="coerce").fillna(-1))}
    missing = ids - set(m)
    if missing:
        raise SystemExit(f"book ids not in frame.{col}: {sorted(missing)[:5]}")
    return np.array([[m[int(v)] for v in row] for row in book.to_numpy()])


def name_rows(fr: pd.DataFrame, keys: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """'|'-joined display-name keys -> frame rows; returns (rows, matched-mask)."""
    n2i: dict[str, int] = {}
    for i, n in enumerate(fr.display_name.astype(str)):
        n2i.setdefault(n, i)
    parts = keys.str.split("|")
    ok = parts.map(lambda k: len(k) == 9 and all(x in n2i for x in k)).to_numpy()
    return np.array([[n2i[x] for x in k] for k in parts[ok]]), ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("season", type=int)
    ap.add_argument("week", type=int)
    ap.add_argument("contest_id")
    ap.add_argument("--book", type=Path, help="entered book CSV (default RUN_DIR/book.csv)")
    args = ap.parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    fr = pd.read_parquet(args.run_dir / "frame.parquet").reset_index(drop=True)
    pcol = "proj" if "proj" in fr else "mean_projection"
    s, w = args.season, args.week
    played = set(query_df(f"SELECT DISTINCT player_id gid FROM `{settings.raw}.weekly_stats` "
                          f"WHERE season={s} AND week={w}").gid.astype(str))
    if not played:
        raise SystemExit(f"weekly_stats has no rows for {s} week {w}; refresh nflverse first")
    own = query_df(f"SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership` "
                   f"WHERE season={s} AND week={w} GROUP BY 1")
    a = player_arrays(fr, played, dict(zip(own.display_name.astype(str), own.fpts.astype(float))), pcol)

    out = []
    f = query_df(f"SELECT points, players_key FROM `{settings.raw}.contest_entries` "
                 f"WHERE season={s} AND week={w} AND contest_id='{args.contest_id}'")
    if f.empty:
        raise SystemExit(f"no contest_entries for contest {args.contest_id}")
    idx, ok = name_rows(fr, f.players_key)
    print(f"field {len(f)} lineups, {ok.mean():.4f} fully matched to the frame")
    pts = f.points.to_numpy()[ok]
    out.append({"group": "field", **summarize(a, idx)})
    out.append({"group": "field top 1%", **summarize(a, idx[pts >= np.quantile(pts, 0.99)])})
    cands = pd.read_parquet(args.run_dir / "candidates.parquet")
    pidx, pok = name_rows(fr, cands.names)
    out.append({"group": f"our pool ({pok.mean():.3f} matched)", **summarize(a, pidx)})
    book = pd.read_csv(args.book or args.run_dir / "book.csv")
    out.append({"group": "our book", **summarize(a, book_rows(fr, book))})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(out).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
