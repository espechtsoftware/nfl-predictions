"""The operator's TE idea on the 2026 real Millionaire fields (W1-4; the lineups the Neo4j graph holds, read at the source in
BigQuery): when the lineup's QB faces a STRONG pass defense (the frame's pre-lock epa_per_dropback_allowed_l6 for the QB's
opponent, lowest third of the slate = strong; the frames carry it from W3 on, so W3-4 only), do QB + TE stacks (a TE teammate and no WR teammate) finish in the top
1% / 5% more often than QB + WR stacks (a WR teammate and no TE teammate)? And QB + RB + TE vs QB + WR + WR? Within-user
Mantel-Haenszel odds ratios (users with 20+ entries), by defense third. Descriptive; four weeks."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); Uw = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name")
    qb = fr[fr.pos == "QB"]; epa = pd.to_numeric(qb.epa_per_dropback_allowed_l6, errors="coerce")
    if epa.notna().sum() < 6:
        print(f"W{w}: the frame has no pre-lock pass-defense value (epa_per_dropback_allowed_l6) -- skipped", flush=True); continue
    qb = qb[epa.notna()]; epa = epa[epa.notna()]
    third = pd.Series(pd.qcut(epa.rank(method="first"), 3, labels=["strong pass D", "middle", "weak pass D"]).astype(str).values, index=qb.display_name.values)
    dmap = {n: third.get(n, "") for n in fr.display_name}
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    q = """WITH m AS (SELECT n, p, t, o, d FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@pos) p WITH OFFSET k ON i = k JOIN UNNEST(@team) t WITH OFFSET a ON i = a
                       JOIN UNNEST(@opp) o WITH OFFSET b ON i = b JOIN UNNEST(@def) d WITH OFFSET c ON i = c),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      big AS (SELECT u FROM e GROUP BY u HAVING COUNT(*) >= 20),
      x AS (SELECT e.u, ANY_VALUE(e.rank) / ANY_VALUE(e.ne) rk, ARRAY_AGG(STRUCT(m.p, m.t, m.o, m.d)) pl, COUNT(m.n) matched
            FROM e JOIN big USING (u), UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.u, e.entry_id),
      y AS (SELECT u, rk, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt, (SELECT ANY_VALUE(z.d) FROM UNNEST(pl) z WHERE z.p = 'QB') qbd FROM x WHERE matched = 9)
      SELECT u, rk, qbd, (SELECT COUNTIF(z.t = qbt AND z.p = 'TE') FROM UNNEST(pl) z) te_m, (SELECT COUNTIF(z.t = qbt AND z.p = 'WR') FROM UNNEST(pl) z) wr_m,
             (SELECT COUNTIF(z.t = qbt AND z.p = 'RB') FROM UNNEST(pl) z) rb_m FROM y"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()),
        bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()), bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist()),
        bigquery.ArrayQueryParameter("def", "STRING", [dmap.get(n, "") for n in fr.display_name])])
    d = BQ.query(q, job_config=cfg).to_dataframe(); d["week"] = w; Uw.append(d); print(f"W{w}: multi-entry lineups {len(d):,}", flush=True)
D = pd.concat(Uw, ignore_index=True); D["uw"] = D.week.astype(str) + "|" + D.u.astype(str)
D["qb_te"] = (D.te_m >= 1) & (D.wr_m == 0); D["qb_wr"] = (D.wr_m >= 1) & (D.te_m == 0)
D["qb_rb_te"] = (D.rb_m >= 1) & (D.te_m >= 1) & (D.wr_m == 0); D["qb_wr_wr"] = (D.wr_m >= 2) & (D.te_m == 0) & (D.rb_m == 0)
for k in (1, 5):
    D[f"top{k}"] = D.rk <= k / 100.0
def mh(X, ex, ref, out):
    X = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X[out].astype(int))
    s = X.groupby(["uw", "E"]).o.agg(["size", "sum"]).reset_index().pivot_table(index="uw", columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d = s[("size", 0)] - c; n = a + b + c + d
    den = (b * c / n).sum(); return ((a * d / n).sum() / den if den > 0 else np.nan), int(X[X.E == 1].o.sum()), int((X.E == 1).sum())
rows = []
for third in ("strong pass D", "middle", "weak pass D"):
    T = D[D.qbd == third]
    for name, ex, ref in (("QB+TE vs QB+WR", T.qb_te, T.qb_wr), ("QB+RB+TE vs QB+WR+WR", T.qb_rb_te, T.qb_wr_wr)):
        r = {"QB faces": third, "contrast": name}
        for k in (1, 5):
            est, ev, nexp = mh(T, ex, ref, f"top{k}"); r[f"top{k}% OR"] = round(est, 2); r[f"top{k}% exposed events"] = f"{ev} of {nexp}"
        rows.append(r)
pd.set_option("display.width", 230); print("\nwithin-user odds ratio of a top finish, by the QB's opponent pass defense (pre-lock), W1-4 real fields:")
print(pd.DataFrame(rows).to_string(index=False))
print("\nshare of multi-entry lineups by stack type and the QB's opponent:"); print(D.groupby("qbd")[["qb_te", "qb_wr", "qb_rb_te", "qb_wr_wr"]].mean().round(3).to_string())
