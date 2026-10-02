"""Weeks 1 and 3 of 2026, in hindsight: could our corpus have produced what won the major contests?

Run from the private data directory (~/corpus-audit). Inputs, all pulled read-only:
  field_points.parquet      every entry's score in the major contests (nfl_raw.contest_entries)
  field_top2pct.parquet     the top 2% of each of those contests, with lineups
  milly_ownership_fpts.parquet  realized points and ownership per player (nfl_raw.contest_ownership)
  dk_<group>.parquet        the DraftKings player list of the week's main draft group (nfl_raw.dk_salaries)
  pools/...                 our run dirs (candidates + frame + universe ledger)
Outcomes are used throughout: nothing here selects lineups. W2 is left out (the projection-defect week).

Three questions per week:
  A. The pool against the real lines: its best lineup, where that best would have finished, and how many of its
     lineups clear the top-1% / top-0.1% lines and the winning score (with the field's own rate for comparison).
  B. Could the house rules even build the winners? Each top-0.1% lineup is checked against the rules the optimizer
     enforces (QB + 2 WR/TE, 1 bring-back, no RB vs his own DST, no two RBs of one team, salary >= 49,000, <= 4 per
     game) and against our player universe (players the build excluded before solving).
  C. Headroom: the best DK-legal lineup in hindsight, and the best one under the house rules, against the winner.
"""
import json
import sys
from collections import Counter

import numpy as np
import pandas as pd
import pulp

CONTESTS = {1: {"Millionaire": "193028206", "Play-Action (20 max)": "193028208", "FFWC qualifier": "194478066"},
            3: {"Millionaire": "195905122", "FFWC qualifier": "195923609", "$25 supersat": "195920741"}}
POOLS = {1: [("entered pool: D800 build e7255e9", "pools/w1-e7255e9/candidates.parquet", "pools/w1-e7255e9")],
         3: [("entered pool: Saturday D12800 (65305f5)", "pools/w3-postmortem/cands_scored.pkl", "pools/w3-union-w3z"),
             ("replay in the Week-4 design: D12800 + T-70 union (w3z)", "pools/w3-union-w3z/candidates.parquet", "pools/w3-union-w3z")]}
GROUP = {1: 151307, 3: None}          # W3's group is read from the frame
MILLY = {1: "193028206", 3: "195905122"}


def norm(s: str) -> str:
    return " ".join(str(s).replace(".", "").split()).lower()


def week_points(own: pd.DataFrame, week: int) -> dict[str, float]:
    o = own[(own.week == week) & (own.contest_id == MILLY[week])]
    return {norm(n): float(p) for n, p in zip(o.display_name, o.fpts)}


def lineup_names(cell: str) -> list[str]:
    return [x for x in str(cell).split("|") if x]


def roster_table(week: int, frame: pd.DataFrame) -> pd.DataFrame:
    """Every player of the main draft group with team/pos/salary; opponent and game from the frame's teams."""
    g = GROUP[week] or int(frame.draft_group_id.iloc[0])
    dk = pd.read_parquet(f"dk_{g}.parquet").sort_values("pulled_at").drop_duplicates("dk_player_id", keep="last")
    opp = dict(zip(frame.team, frame.opp)); game = dict(zip(frame.team, frame.game_id))
    t = pd.DataFrame({"key": dk.display_name.map(norm), "name": dk.display_name, "pos": dk.position.str.split("/").str[0],
                      "team": dk.team_abbr, "salary": dk.salary})
    t["opp"] = t.team.map(opp); t["game"] = t.team.map(game)
    return t.drop_duplicates("key").set_index("key")


def house_rule_violations(names: list[str], R: pd.DataFrame, max_per_game: int = 4) -> list[str]:
    rows = R.reindex([norm(n) for n in names])
    if rows.team.isna().any():
        return ["unknown player: " + ", ".join(n for n, m in zip(names, rows.team.isna()) if m)]
    out = []
    if rows.salary.sum() < 49_000:
        out.append(f"salary {int(rows.salary.sum())} < 49000")
    qb = rows[rows.pos == "QB"].iloc[0]
    if ((rows.pos.isin(["WR", "TE"])) & (rows.team == qb.team)).sum() < 2:
        out.append("QB stack < 2")
    if ((rows.team == qb.opp) & (rows.pos != "DST")).sum() < 1:
        out.append("no bring-back")
    dst = rows[rows.pos == "DST"].iloc[0]
    if ((rows.pos == "RB") & (rows.team == dst.opp)).any():
        out.append("RB vs own DST")
    if rows[rows.pos == "RB"].team.value_counts().max() > 1:
        out.append("two RBs one team")
    if rows.game.value_counts().max() > max_per_game:
        out.append(f"> {max_per_game} in one game")
    return out


def best_lineup(R: pd.DataFrame, pts: dict[str, float], house: bool, universe: set[str] | None = None) -> tuple[float, list[str]]:
    P = R[R.index.isin(pts.keys())].copy()
    if universe is not None:
        P = P[P.index.isin(universe)]
    P["pts"] = [pts[k] for k in P.index]
    P = P[P.game.notna()]
    idx = list(P.index); x = pulp.LpVariable.dicts("x", idx, cat="Binary")
    m = pulp.LpProblem("best", pulp.LpMaximize); m += pulp.lpSum(P.pts[i] * x[i] for i in idx)
    pos = P.pos
    m += pulp.lpSum(x[i] for i in idx) == 9
    m += pulp.lpSum(P.salary[i] * x[i] for i in idx) <= 50_000
    m += pulp.lpSum(x[i] for i in idx if pos[i] == "QB") == 1
    m += pulp.lpSum(x[i] for i in idx if pos[i] == "DST") == 1
    m += pulp.lpSum(x[i] for i in idx if pos[i] == "RB") >= 2
    m += pulp.lpSum(x[i] for i in idx if pos[i] == "WR") >= 3
    m += pulp.lpSum(x[i] for i in idx if pos[i] == "TE") >= 1
    m += pulp.lpSum(x[i] for i in idx if pos[i] in ("RB", "WR", "TE")) == 7
    if house:
        m += pulp.lpSum(P.salary[i] * x[i] for i in idx) >= 49_000
        for t in set(P.team):
            qbs = [i for i in idx if pos[i] == "QB" and P.team[i] == t]
            if not qbs:
                continue
            q = pulp.lpSum(x[i] for i in qbs)
            m += pulp.lpSum(x[i] for i in idx if pos[i] in ("WR", "TE") and P.team[i] == t) >= 2 * q
            o = P.opp[qbs[0]]
            m += pulp.lpSum(x[i] for i in idx if P.team[i] == o and pos[i] != "DST") >= q
            m += pulp.lpSum(x[i] for i in idx if pos[i] == "RB" and P.team[i] == t) <= 1
            d = [i for i in idx if pos[i] == "DST" and P.team[i] == t]
            if d:   # no RB facing this DST
                m += pulp.lpSum(x[i] for i in idx if pos[i] == "RB" and P.team[i] == o) <= 2 * (1 - x[d[0]])
        for g in set(P.game):
            m += pulp.lpSum(x[i] for i in idx if P.game[i] == g) <= 4
    m.solve(pulp.PULP_CBC_CMD(msg=False))
    pick = [i for i in idx if x[i].value() > 0.5]
    return round(float(P.loc[pick, "pts"].sum()), 2), [R.loc[i, "name"] for i in pick]


def main() -> int:
    field = pd.read_parquet("field_points.parquet"); top = pd.read_parquet("field_top2pct.parquet")
    own = pd.read_parquet("milly_ownership_fpts.parquet")
    report = {}
    for week in (1, 3):
        pts = week_points(own, week)
        print(f"\n{'=' * 100}\nWEEK {week}")
        for label, cpath, rdir in POOLS[week]:
            c = pd.read_pickle(cpath) if cpath.endswith(".pkl") else pd.read_parquet(cpath)
            frame = pd.read_parquet(f"{rdir}/frame.parquet")
            names = c["names"].map(lineup_names)
            miss = Counter(n for row in names for n in row if norm(n) not in pts)
            score = names.map(lambda row: sum(pts.get(norm(n), 0.0) for n in row))
            print(f"\n--- {label}: {len(c):,} lineups; realized mean {score.mean():.1f}, best {score.max():.2f}, "
                  f"p99 {score.quantile(.99):.1f}; players with no realized score (counted 0): {dict(miss.most_common(5))}")
            rows = []
            for cname, cid in CONTESTS[week].items():
                f = field[field.contest_id == cid].points.to_numpy()
                n = len(f); win = f.max(); p999 = np.quantile(f, .999); p99 = np.quantile(f, .99)
                best = score.max(); rank = int((f > best).sum()) + 1
                rows.append({"contest": cname, "entries": n, "winner": round(win, 2), "top0.1% line": round(p999, 1),
                             "top1% line": round(p99, 1), "pool best": round(best, 2), "pool best's finish": f"{rank:,}",
                             "pool >= winner": int((score >= win).sum()),
                             "pool >= top0.1%": int((score >= p999).sum()), "share/0.1% (lift)": round((score >= p999).mean() / .001, 2),
                             "pool >= top1%": int((score >= p99).sum()), "share/1% (lift)": round((score >= p99).mean() / .01, 2)})
            T = pd.DataFrame(rows).set_index("contest"); print(T.to_string())
            report[f"w{week}:{label}"] = T.reset_index().to_dict("records")

        # B. the real top-0.1% lineups of the Millionaire against the house rules and our universe
        frame = pd.read_parquet(f"{POOLS[week][-1][2]}/frame.parquet")
        R = roster_table(week, frame)
        led = pd.read_parquet(f"{POOLS[week][-1][2]}/universe_ledger.parquet")
        universe = set(led[led.included].name.map(norm))
        f = field[field.contest_id == MILLY[week]].points.to_numpy(); p999 = np.quantile(f, .999)
        W = top[(top.contest_id == MILLY[week]) & (top.points >= p999)].copy()
        W["names"] = W.players_key.map(lineup_names)
        W["violations"] = W.names.map(lambda r: house_rule_violations(r, R))
        W["excluded"] = W.names.map(lambda r: [n for n in r if norm(n) not in universe])
        W["legal"] = W.violations.map(len).eq(0); W["in_universe"] = W.excluded.map(len).eq(0)
        print(f"\n--- the Millionaire's {len(W):,} top-0.1% lineups (>= {p999:.1f}) against the house rules and our universe")
        print(f"satisfy every house rule: {W.legal.mean():.1%}; all nine players in our universe: {W.in_universe.mean():.1%}; "
              f"both: {(W.legal & W.in_universe).mean():.1%}")
        print("rule broken (share of the top-0.1% lineups):", {k: round(v / len(W), 3) for k, v in Counter(
            v.split(" (")[0] if not v.startswith("unknown") else "unknown player" for vs in W.violations for v in vs).most_common()})
        print("players excluded from our universe, most frequent:", Counter(n for r in W.excluded for n in r).most_common(10))
        top10 = W.sort_values("points", ascending=False).head(10)
        print("the top 10:"); print(top10[["rank", "points", "legal", "violations", "excluded"]].to_string(index=False))
        report[f"w{week}:winners"] = {"n": len(W), "legal": float(W.legal.mean()), "in_universe": float(W.in_universe.mean()),
                                      "both": float((W.legal & W.in_universe).mean())}

        # C. headroom in hindsight
        b_dk, l_dk = best_lineup(R, pts, house=False)
        b_h, l_h = best_lineup(R, pts, house=True)
        b_hu, _ = best_lineup(R, pts, house=True, universe=universe)
        print(f"\n--- headroom: best DK-legal lineup {b_dk} | best under the house rules {b_h} | house rules inside our "
              f"universe {b_hu} | Millionaire winner {f.max():.2f}")
        print("  best DK-legal:", l_dk); print("  best house:", l_h)
        report[f"w{week}:headroom"] = {"dk_legal": b_dk, "house": b_h, "house_universe": b_hu, "winner": float(f.max())}
    json.dump(report, open("01_history.json", "w"), indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
