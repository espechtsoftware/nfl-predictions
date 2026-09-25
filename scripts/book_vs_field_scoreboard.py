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


def player_arrays(fr: pd.DataFrame, played: set[str], real: dict[str, float], pcol: str,
                  own: dict[str, float] | None = None) -> dict:
    """Per-frame-row arrays used by summarize(); real and own are keyed by display_name (0 when absent).
    `own` is slot-summed field ownership in percent (the 2026 import writes one row per roster slot)."""
    skill = fr.position.isin(SKILL).to_numpy()
    dnp = skill & ~fr.gsis_id.astype(str).isin(played).to_numpy()
    r = np.array([real.get(str(n), 0.0) for n in fr.display_name], float)
    p = pd.to_numeric(fr[pcol], errors="coerce").fillna(0.0).to_numpy(float)
    o = np.array([(own or {}).get(str(n), 0.0) for n in fr.display_name], float)
    sal = pd.to_numeric(fr.get("salary", pd.Series(0, index=fr.index)), errors="coerce").fillna(0).to_numpy(float)
    pl = skill & ~dnp
    return {"proj": p, "real": r, "own": o / 100.0, "dnp": dnp.astype(float), "gap": np.where(pl, r - p, 0.0),
            "played": pl.astype(float), "low": ((o < 5.0) & skill).astype(float),
            "chalk": (o >= 20.0).astype(float), "salary": sal}


def summarize(a: dict, idx: np.ndarray) -> dict:
    """idx: (n_lineups, 9) frame row indices."""
    n_pl = np.maximum(a["played"][idx].sum(1), 1)
    low = a["low"][idx].sum(1)
    return {"n": len(idx), "proj": a["proj"][idx].sum(1).mean(), "realized": a["real"][idx].sum(1).mean(),
            "dnp_slots": a["dnp"][idx].sum(1).mean(), "gap_played": a["gap"][idx].sum(1).mean(),
            "gap_per_played": (a["gap"][idx].sum(1) / n_pl).mean(),
            # corpus shape (external review §2.2): share with 3+ / 0-1 skill players under 5% owned,
            # share with no 20%+ player, mean salary left
            "pct_3plus_low": 100 * (low >= 3).mean(), "pct_0to1_low": 100 * (low <= 1).mean(),
            "pct_no_chalk": 100 * (a["chalk"][idx].sum(1) == 0).mean(),
            "salary_left": (50000 - a["salary"][idx].sum(1)).mean()}


def information_lines(a: dict, book_idx: np.ndarray) -> dict:
    """R10 (outside-the-box plan): Grinold-Kahn accounting of one book against the field, per week.

    Per player i (every player we hold or the field drafted): w_i = our expected count per lineup (book share), f_i = field
    ownership as expected count per lineup (slot-summed ownership / 100), active weight a_i = w_i - f_i, realized p_i,
    served projection mu_i. c_i = the crowd-implied value: within-slate OLS of mu on log ownership and log salary.
      IC             Spearman(a_i, p_i - mu_i): do our active bets beat our own projection's error?
      projection IC  Spearman(mu_i - c_i, p_i - c_i): is our view against the crowd right?
      TC             Pearson(mu_i - c_i, a_i): do the delivered active weights follow that view (transfer)?
      active share   0.5 x sum |w_i - f_i| / 9 (0 = the field's exposures, 1 = disjoint)
    Identity (a check, not a statistic): book mean - field mean = sum_i a_i p_i when field mean = sum_i f_i p_i."""
    from scipy import stats
    w = np.bincount(np.asarray(book_idx).ravel(), minlength=len(a["proj"])) / len(book_idx)
    f = a["own"]
    keep = (w > 0) | (f > 0)
    act, p, mu = (w - f)[keep], a["real"][keep], a["proj"][keep]
    X = np.column_stack([np.ones(keep.sum()), np.log(f[keep] + 1e-3), np.log(np.maximum(a["salary"][keep], 2000.0))])
    c = X @ np.linalg.lstsq(X, mu, rcond=None)[0]
    return {"players": int(keep.sum()),
            "IC": float(stats.spearmanr(act, p - mu)[0]),
            "projection_IC": float(stats.spearmanr(mu - c, p - c)[0]),
            "TC": float(np.corrcoef(mu - c, act)[0, 1]),
            "active_share": float(0.5 * np.abs(w - f).sum() / 9.0),
            "sum_a_p": float((act * p).sum()),
            "book_mean_minus_own_field_mean": float(a["real"][book_idx].sum(1).mean() - (f * a["real"]).sum())}


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


def heavy_user_mask(entry_names: pd.Series, lo: int = 51, hi: int = 150) -> np.ndarray:
    """Entries whose DK suffix "(i/N)" declares N in [lo, hi]; single entries carry no suffix."""
    n = entry_names.astype(str).str.extract(r"\(\d+/(\d+)\)\s*$")[0].astype(float)
    return n.between(lo, hi).to_numpy()


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
    field_own = query_df(f"""SELECT display_name, SUM(pct_drafted) own FROM (
        SELECT * FROM `{settings.raw}.contest_ownership`
        WHERE season={s} AND week={w} AND contest_id='{args.contest_id}'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY display_name, roster_position ORDER BY imported_at DESC) = 1)
        GROUP BY 1""")
    a = player_arrays(fr, played, dict(zip(own.display_name.astype(str), own.fpts.astype(float))), pcol,
                      dict(zip(field_own.display_name.astype(str), field_own.own.astype(float))))

    out = []
    f = query_df(f"SELECT points, players_key, entry_name FROM `{settings.raw}.contest_entries` "
                 f"WHERE season={s} AND week={w} AND contest_id='{args.contest_id}'")
    if f.empty:
        raise SystemExit(f"no contest_entries for contest {args.contest_id}")
    idx, ok = name_rows(fr, f.players_key)
    print(f"field {len(f)} lineups, {ok.mean():.4f} fully matched to the frame")
    pts = f.points.to_numpy()[ok]
    out.append({"group": "field", **summarize(a, idx)})
    out.append({"group": "field top 1%", **summarize(a, idx[pts >= np.quantile(pts, 0.99)])})
    heavy = heavy_user_mask(f.entry_name[ok])
    if heavy.any():
        out.append({"group": "heavy users (51-150 entries)", **summarize(a, idx[heavy])})
    cands = pd.read_parquet(args.run_dir / "candidates.parquet")
    pidx, pok = name_rows(fr, cands.names)
    out.append({"group": f"our pool ({pok.mean():.3f} matched)", **summarize(a, pidx)})
    book = pd.read_csv(args.book or args.run_dir / "book.csv")
    bidx = book_rows(fr, book)
    out.append({"group": "our book", **summarize(a, bidx)})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(out).round(2).to_string(index=False))
    ic = information_lines(a, bidx)
    print(f"information (R10): IC {ic['IC']:+.3f}, projection IC {ic['projection_IC']:+.3f}, TC {ic['TC']:+.3f}, "
          f"active share {ic['active_share']:.3f} over {ic['players']} players; identity: sum a*p {ic['sum_a_p']:+.2f} "
          f"= book mean - ownership-weighted field mean {ic['book_mean_minus_own_field_mean']:+.2f}")


if __name__ == "__main__":
    main()
