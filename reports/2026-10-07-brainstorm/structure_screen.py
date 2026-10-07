"""Whole-field structural screen (W1-4 real Millionaire fields): within-user-week Mantel-Haenszel odds ratios of a top-1%
finish (users with 20+ entries) for lineup structures, each vs a reference level; per week and pooled with a 95% bootstrap
over user-weeks. A structure is 'consistent' when all four weeks sit on the same side of 1. Server-side; names fingerprinted."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); Uw = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("display_name")
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    q = """WITH m AS (SELECT n, s, p, t, o, g FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
                       JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b JOIN UNNEST(@game) g WITH OFFSET c ON i = c),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      big AS (SELECT u FROM e GROUP BY u HAVING COUNT(*) >= 20),
      x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) <= 0.01 * ANY_VALUE(e.ne) top1, ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o, m.g)) pl, COUNT(m.n) matched
            FROM e JOIN big USING (u), UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.u, e.entry_id),
      y AS (SELECT u, top1, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo,
                   (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p = 'QB') qbs, (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p = 'DST') dsts,
                   (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'DST') dstt FROM x WHERE matched = 9)
      SELECT u, top1, 50000 - (SELECT SUM(z.s) FROM UNNEST(pl) z) sal_left,
             (SELECT COUNTIF(z.t = qbt AND z.p != 'QB' AND z.p != 'DST') FROM UNNEST(pl) z) stack_n,
             (SELECT COUNTIF(z.t = qbo AND z.p != 'DST') FROM UNNEST(pl) z) bring_n,
             (SELECT COUNTIF(z.p = 'RB') FROM UNNEST(pl) z) n_rb, (SELECT COUNTIF(z.p = 'WR') FROM UNNEST(pl) z) n_wr, (SELECT COUNTIF(z.p = 'TE') FROM UNNEST(pl) z) n_te,
             (SELECT COUNT(DISTINCT z.g) FROM UNNEST(pl) z) n_games,
             (SELECT MAX(c) FROM (SELECT COUNT(*) c FROM UNNEST(pl) z GROUP BY z.g)) max_game,
             qbs, dsts, (SELECT COUNTIF(z.t = dstt AND z.p = 'RB') FROM UNNEST(pl) z) rb_with_dst,
             (SELECT COUNTIF(z.o = dstt AND z.p != 'DST') FROM UNNEST(pl) z) vs_own_dst FROM y"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in fr.salary]),
        bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()),
        bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist()), bigquery.ArrayQueryParameter("game", "STRING", fr.game_id.astype(str).tolist())])
    d = BQ.query(q, job_config=cfg).to_dataframe(); d["week"] = w; Uw.append(d); print(f"W{w}: multi-entry lineups with 9 matched players {len(d):,}", flush=True)
D = pd.concat(Uw, ignore_index=True)
D["flex"] = np.select([D.n_rb == 3, D.n_wr == 4, D.n_te == 2], ["RB", "WR", "TE"], "other")
C = {  # name: (exposed predicate, reference predicate)
    "salary left >= $1,000 vs <= $200": (D.sal_left >= 1000, D.sal_left <= 200),
    "salary left $300-900 vs <= $200": (D.sal_left.between(300, 900), D.sal_left <= 200),
    "QB + 1 teammate vs QB + 2": (D.stack_n == 1, D.stack_n == 2),
    "QB + 3+ teammates vs QB + 2": (D.stack_n >= 3, D.stack_n == 2),
    "naked QB vs QB + 2": (D.stack_n == 0, D.stack_n == 2),
    "bring-back 1+ vs none": (D.bring_n >= 1, D.bring_n == 0),
    "FLEX RB vs FLEX WR": (D.flex == "RB", D.flex == "WR"),
    "FLEX TE vs FLEX WR": (D.flex == "TE", D.flex == "WR"),
    "games used <= 4 vs 6+": (D.n_games <= 4, D.n_games >= 6),
    "5+ players from one game vs <= 3": (D.max_game >= 5, D.max_game <= 3),
    "QB >= $7,000 vs < $6,000": (D.qbs >= 7000, D.qbs < 6000),
    "DST < $3,000 vs >= $3,500": (D.dsts < 3000, D.dsts >= 3500),
    "RB with own DST vs not": (D.rb_with_dst >= 1, D.rb_with_dst == 0),
    "a player vs own DST vs not": (D.vs_own_dst >= 1, D.vs_own_dst == 0),
}
def mh(ex, ref):
    X = D[ex | ref].assign(E=ex[ex | ref]); s = X.groupby(["week", "u", "E"]).top1.agg(["size", "sum"]).unstack("E", fill_value=0)
    a = s[("sum", True)]; b = s[("size", True)] - a; c = s[("sum", False)]; d = s[("size", False)] - c; n = a + b + c + d
    return a * d / n, b * c / n, X.E.mean()
rng = np.random.default_rng(9); rows = []
for name, (ex, ref) in C.items():
    num, den, share = mh(ex, ref); est = num.sum() / den.sum()
    bs = [num.values[i].sum() / den.values[i].sum() for i in (rng.integers(0, len(num), len(num)) for _ in range(1000))]
    wk = [num[num.index.get_level_values(0) == w].sum() / max(den[den.index.get_level_values(0) == w].sum(), 1e-12) for w in (1, 2, 3, 4)]
    cons = "ALL >1" if all(v > 1 for v in wk) else ("ALL <1" if all(v < 1 for v in wk) else "mixed")
    rows.append({"structure": name, "OR": round(est, 2), "lo": round(np.percentile(bs, 2.5), 2), "hi": round(np.percentile(bs, 97.5), 2), "W1": round(wk[0], 2), "W2": round(wk[1], 2),
                 "W3": round(wk[2], 2), "W4": round(wk[3], 2), "weeks": cons, "exposed_share_of_compared": round(share, 3)})
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
