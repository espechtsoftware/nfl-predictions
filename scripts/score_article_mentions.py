"""PREREG-A3 reader: article mentions as an ownership input (frozen spec: reports/2026-10-02-PREREG-A3-B2-escalated.md).

Per week, from captures made BEFORE the lock only:
  articles  nfl_raw.fantasy_points_articles, the newest capture per slug before the lock (paywalled previews are never
            stored); counted when the title matches the frozen patterns: M over all six, M_DFS over the two DFS ones
  LAG       the Saturday lag file (pred_own, %)
  FP        nfl_raw.fantasy_points_projected_ownership, DraftKings, the newest capture before the lock
  C(player) = the number of distinct counted articles whose normalised text names the player (ownership_blend.norm, full
            name; a DST by nickname followed by D/ST, DST or defense)
Arms per base (LAG, FP): base x (1 + 0.25 C) and base + 2.0 C points, for C in (M, M_DFS): 8 arms; constants FIXED.
Target, population and matching: PREREG-O1's, from o1_common (reviewer 10-02): players priced by the base AND in the
realized table, matched to the slate by DK id then name + team; reported for all and skill-only. Each arm prints how
many players its count moved (C >= 1 within the population), so a dead arm is visible. Metric: Spearman of each arm against the target,
and its gain over its base. Prints per-arm gains and the coverage/match rates; decides nothing (the rule is applied
after Week 7, with the one interim after Week 5).

Usage: score_article_mentions.py --season 2026 --week 4 --group 154078 --contest <Millionaire id> --lock-utc 2026-10-04T17:00:00Z --lag f.csv
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--contest", required=True); ap.add_argument("--lock-utc", required=True); ap.add_argument("--lag", required=True)
    ap.add_argument("--group", type=int, required=True)
    a = ap.parse_args(argv)
    from google.cloud import bigquery
    import o1_common as O                       # O1's target, population and matching (reviewer 10-02)
    c = bigquery.Client(project=PROJECT); raw = f"{PROJECT}.nfl_raw"
    real = O.realized(c, a.season, a.week, a.contest)
    sl = O.slate(c, a.group, a.lock_utc)
    arts = c.query(f"""SELECT title, slug, text FROM `{raw}.fantasy_points_articles`
        WHERE season={a.season} AND week={a.week} AND retrieved_at < TIMESTAMP('{a.lock_utc}')
        QUALIFY ROW_NUMBER() OVER (PARTITION BY slug ORDER BY retrieved_at DESC) = 1""").to_dataframe()
    fp = c.query(f"""SELECT name, team, projected_ownership_pct FROM `{raw}.fantasy_points_projected_ownership`
        WHERE season={a.season} AND week={a.week} AND operator='DraftKings' AND retrieved_at < TIMESTAMP('{a.lock_utc}')
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""").to_dataframe()
    if len(fp):
        assert not fp.duplicated(["name", "team"]).any(), "FP capture holds duplicate (name, team): more than one slate?"
    bases = {"LAG": O.attach(pd.read_csv(a.lag), sl, "pred_own").rename(columns={"pred_own": "v"})}
    if len(fp):
        bases["FP"] = O.attach(fp, sl, "projected_ownership_pct").rename(columns={"projected_ownership_pct": "v"})
    players = sl[["key", "pos"]].assign(nickname=sl.display_name.where(sl.pos == "DST"))
    C = {"M": mention_counts(arts, players, M_TITLES), "M_DFS": mention_counts(arts, players, M_DFS_TITLES)}
    print(f"articles before lock: {len(arts)}; counted M {sum(counted(t, M_TITLES) for t in arts.title)}, "
          f"M_DFS {sum(counted(t, M_DFS_TITLES) for t in arts.title)}")
    dst = set(sl.key[sl.pos == "DST"]); top20 = set(real.sort_values(ascending=False).index[:20])
    for k, cs in C.items():
        print(f"  {k}: players with C>=1 {int((cs >= 1).sum())} (DSTs {int((cs[cs.index.isin(dst)] >= 1).sum())}); "
              f"realized top-20 covered {sum(1 for p in top20 if cs.get(p, 0) >= 1)}/20")
    rows = []
    for label, base in bases.items():
        pop = O.population(base, real)
        b_all = O.score_both(pop, "v", real)
        print(f"{label}: matched {len(base)}, population {b_all['n']} (skill {b_all['n_skill']}); Spearman all {b_all['spearman']}, skill {b_all['spearman_skill']}")
        for name, arm in arms(pop.set_index("key")["v"].astype(float), C, label).items():
            df = pop.assign(v=arm.reindex(pop.key).to_numpy())
            sc = O.score_both(df, "v", real); cname = name.split("_", 2)[2]
            moved = int((C[cname].reindex(pop.key).fillna(0) >= 1).sum())
            rows.append({"arm": name, "moved": moved, "sp_all": sc["spearman"], "gain_all": round(sc["spearman"] - b_all["spearman"], 4),
                         "sp_skill": sc["spearman_skill"], "gain_skill": round(sc["spearman_skill"] - b_all["spearman_skill"], 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
