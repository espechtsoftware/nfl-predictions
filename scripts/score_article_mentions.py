"""PREREG-A3 reader: article mentions as an ownership input (frozen spec: reports/2026-10-02-PREREG-A3-B2-escalated.md).

Per week, from captures made BEFORE the lock only:
  articles  nfl_raw.fantasy_points_articles, the newest capture per slug before the lock (paywalled previews are never
            stored); counted when the title matches the frozen patterns: M over all six, M_DFS over the two DFS ones
  LAG       the Saturday lag file (pred_own, %)
  FP        nfl_raw.fantasy_points_projected_ownership, DraftKings, the newest capture before the lock
  C(player) = the number of distinct counted articles whose normalised text names the player (ownership_blend.norm, full
            name; a DST by nickname followed by D/ST, DST or defense)
Arms per base (LAG, FP): base x (1 + 0.25 C) and base + 2.0 C points, for C in (M, M_DFS): 8 arms; constants FIXED.
Target: PREREG-O1's (realized Millionaire ownership counted from contest_entries, book_vs_field_scoreboard's
field_ownership_sql); a base player absent from the field counts 0%. Metric: Spearman of each arm against the target,
and its gain over its base. Prints per-arm gains and the coverage/match rates; decides nothing (the rule is applied
after Week 7, with the one interim after Week 5).

Usage: score_article_mentions.py --season 2026 --week 4 --contest <Millionaire id> --lock-utc 2026-10-04T17:00:00Z --lag f.csv
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ownership_blend import norm  # noqa: E402

PROJECT = "nfl-predictions-503414"
M_TITLES = [r"dfs main slate early look", r"dfs slate breakdown", r"advanced matchups", r"the everything report",
            r"wr/cb .* matchups", r"ol/dl matchups"]
M_DFS_TITLES = [r"dfs main slate early look", r"dfs slate breakdown"]
MULT, ADD = 0.25, 2.0


def counted(title: str, patterns: list[str]) -> bool:
    return any(re.search(p, str(title), re.I) for p in patterns)


def text_key(text: str) -> str:
    """The article text under the same normaliser as the names, so a name is a space-delimited phrase in it."""
    return " " + norm(text) + " "


def mention_counts(articles: pd.DataFrame, players: pd.DataFrame, patterns: list[str]) -> pd.Series:
    """C per player key: distinct counted articles naming the player. players: key, name, pos, (nickname for DST)."""
    texts = [text_key(t) for t, ti in zip(articles.text, articles.title) if counted(ti, patterns)]
    raw = [str(t) for t, ti in zip(articles.text, articles.title) if counted(ti, patterns)]
    out = {}
    for key, pos, nick in zip(players.key, players.pos, players.get("nickname", pd.Series([None] * len(players)))):
        if pos == "DST" and nick:
            pat = re.compile(rf"\b{re.escape(str(nick))}\s*(d/st|dst|defense)\b", re.I)
            out[key] = sum(1 for t in raw if pat.search(t))
        else:
            out[key] = sum(1 for t in texts if f" {key} " in t)
    return pd.Series(out, dtype=float)


def arms(base: pd.Series, counts: dict[str, pd.Series], label: str) -> dict[str, pd.Series]:
    out = {}
    for cname, c in counts.items():
        c = c.reindex(base.index).fillna(0.0)
        out[f"{label}_mult_{cname}"] = base * (1 + MULT * c)
        out[f"{label}_add_{cname}"] = base + ADD * c
    return out


def spearman(pred: pd.Series, real: pd.Series) -> float:
    r = real.reindex(pred.index).fillna(0.0)          # absent from the field = 0% owned (O1's population rule)
    return float(pred.rank().corr(r.rank()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--contest", required=True); ap.add_argument("--lock-utc", required=True); ap.add_argument("--lag", required=True)
    a = ap.parse_args(argv)
    from google.cloud import bigquery

    from book_vs_field_scoreboard import field_ownership_sql
    c = bigquery.Client(project=PROJECT); raw = f"{PROJECT}.nfl_raw"
    real = c.query(field_ownership_sql(raw, a.season, a.week, a.contest)).to_dataframe()
    real = pd.Series(real.own.to_numpy(float), index=real.display_name.map(norm)).groupby(level=0).max()
    arts = c.query(f"""SELECT title, slug, text FROM `{raw}.fantasy_points_articles`
        WHERE season={a.season} AND week={a.week} AND retrieved_at < TIMESTAMP('{a.lock_utc}')
        QUALIFY ROW_NUMBER() OVER (PARTITION BY slug ORDER BY retrieved_at DESC) = 1""").to_dataframe()
    fp = c.query(f"""SELECT name, position, team, projected_ownership_pct FROM `{raw}.fantasy_points_projected_ownership`
        WHERE season={a.season} AND week={a.week} AND operator='DraftKings' AND retrieved_at < TIMESTAMP('{a.lock_utc}')
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""").to_dataframe()
    lag = pd.read_csv(a.lag)
    lag["key"] = lag.display_name.map(norm); fp["key"] = fp.name.map(norm)
    players = pd.concat([lag[["key", "pos"]].assign(nickname=lag.display_name.where(lag.pos == "DST")),
                         fp[["key", "position"]].rename(columns={"position": "pos"}).assign(nickname=fp.name.where(fp.position == "DST"))]
                        ).drop_duplicates("key")
    C = {"M": mention_counts(arts, players, M_TITLES), "M_DFS": mention_counts(arts, players, M_DFS_TITLES)}
    print(f"articles before lock: {len(arts)}; counted M {sum(counted(t, M_TITLES) for t in arts.title)}, "
          f"M_DFS {sum(counted(t, M_DFS_TITLES) for t in arts.title)}")
    top20 = set(real.sort_values(ascending=False).index[:20])
    for k, s in C.items():
        print(f"  {k}: players with C>=1 {int((s >= 1).sum())}; realized top-20 covered {sum(1 for p in top20 if s.get(p, 0) >= 1)}/20")
    rows = []
    for label, base in (("LAG", pd.Series(lag.pred_own.to_numpy(float), index=lag.key).groupby(level=0).max()),
                        ("FP", pd.Series(fp.projected_ownership_pct.to_numpy(float), index=fp.key).groupby(level=0).max())):
        if base.empty:
            print(f"{label}: no pre-lock data"); continue
        b = spearman(base, real)
        print(f"{label}: {len(base)} players, matched to the field {len(set(base.index) & set(real.index))}; Spearman {b:.4f}")
        for name, arm in arms(base, C, label).items():
            s = spearman(arm, real); rows.append({"arm": name, "spearman": round(s, 4), "gain_vs_base": round(s - b, 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
