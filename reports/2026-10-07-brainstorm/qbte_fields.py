"""QB + pass-catching TE stacks on the 2026 real fields (the operator 10-07: "more testing on the QB tight end stacks right
away"). W1-4: the Millionaire (users with 20+ entries) and the priority contests ($4,444 / Warm Up / $555 / $333 / FFWC,
typed by the private shark-share CSVs at runtime). A pass-catching TE is, pre-lock, a TE whose T-70 frame target_share_l4
is >= 15%. Lineup stack types (teammates of the lineup's QB): QB+pcTE only (a pass-catching TE, no WR), QB+WR only (WRs, no
TE), QB+WR+pcTE (both), QB+WR+WR (2+ WRs, no TE). Within-user Mantel-Haenszel odds ratios of a top 1/5/10/20% finish.
Server-side; user names fingerprinted. Aggregates only."""
import csv, json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
TYPES = {}
for f in ("shark_share_by_contest.csv", "week5_type_mapping.csv"):
    p = Path.home() / "private/regulars-share" / f
    if p.exists():
        r = csv.DictReader(open(p)); idc = next(c for c in r.fieldnames if c.endswith("contest_id"))
        for row in r: TYPES[str(row[idc])] = row["type"]
PRI = {c for c, t in TYPES.items() if any(k in t for k in ("$4,444", "Warm Up", "$555", "$333", "FFWC"))}
rows = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name")
    tsh = pd.to_numeric(fr.get("target_share_l4"), errors="coerce").fillna(0.0)
    pc = ((fr.pos == "TE") & (tsh >= 0.15)).astype(int)
    cs = BQ.query(f"SELECT contest_id, COUNT(DISTINCT entry_id) n FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1").to_dataframe()
    milly = cs.sort_values("n", ascending=False).contest_id.iloc[0]
    cids = [milly] + [c for c in cs.contest_id.astype(str) if c in PRI]
    q = """WITH m AS (SELECT n, p, t, c FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@pos) p WITH OFFSET k ON i = k JOIN UNNEST(@team) t WITH OFFSET a ON i = a
                       JOIN UNNEST(@pc) c WITH OFFSET b ON i = b),
      e AS (SELECT DISTINCT contest_id, entry_id, rank, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries`
            WHERE season = 2026 AND week = @w AND contest_id IN UNNEST(@cids)),
      sz AS (SELECT contest_id, COUNT(*) n FROM e GROUP BY 1),
      x AS (SELECT e.contest_id, e.u, ANY_VALUE(e.rank) rank, ARRAY_AGG(STRUCT(m.p, m.t, m.c)) pl, COUNT(m.n) matched FROM e, UNNEST(SPLIT(e.players_key, '|')) nm
            LEFT JOIN m ON m.n = nm GROUP BY e.contest_id, e.u, e.entry_id),
      y AS (SELECT contest_id, u, rank, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt FROM x WHERE matched = 9)
      SELECT y.contest_id, u, rank / sz.n rk, (SELECT COUNTIF(z.t = qbt AND z.p = 'WR') FROM UNNEST(pl) z) wr_m,
             (SELECT COUNTIF(z.t = qbt AND z.p = 'TE') FROM UNNEST(pl) z) te_m, (SELECT COUNTIF(z.t = qbt AND z.p = 'TE' AND z.c = 1) FROM UNNEST(pl) z) pcte_m
      FROM y JOIN sz USING (contest_id)"""
    jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("w", "INT64", w), bigquery.ArrayQueryParameter("cids", "STRING", [str(c) for c in cids]),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()),
        bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()), bigquery.ArrayQueryParameter("pc", "INT64", pc.tolist())])
    d = BQ.query(q, job_config=jc).to_dataframe(); d["week"] = w; d["field"] = np.where(d.contest_id.astype(str) == str(milly), "Millionaire", "priority contests")
    rows.append(d); print(f"W{w}: lineups {len(d):,} (Millionaire {int((d.field == 'Millionaire').sum()):,}; priority {int((d.field != 'Millionaire').sum()):,}); pass-catching TEs in the frame {int(pc.sum())}", flush=True)
D = pd.concat(rows, ignore_index=True); D["uw"] = D.field + "|" + D.week.astype(str) + "|" + D.u.astype(str); D["n_u"] = D.groupby("uw").u.transform("size")
D["qb_pcte"] = (D.pcte_m >= 1) & (D.wr_m == 0); D["qb_wr"] = (D.wr_m >= 1) & (D.te_m == 0)
D["qb_wr_pcte"] = (D.wr_m >= 1) & (D.pcte_m >= 1); D["qb_wr_wr"] = (D.wr_m >= 2) & (D.te_m == 0)
D["qb_any_te"] = D.te_m >= 1; D["qb_no_te"] = D.te_m == 0
for k in (1, 5, 10, 20):
    D[f"top{k}"] = D.rk <= k / 100.0
def mh(X, ex, ref, out):
    X = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X[out].astype(int))
    s = X.groupby(["uw", "E"]).o.agg(["size", "sum"]).reset_index().pivot_table(index="uw", columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d = s[("size", 0)] - c; n = a + b + c + d
    num, den = (a * d / n).fillna(0), (b * c / n).fillna(0)
    rng = np.random.default_rng(4); nv, dv = num.values, den.values
    bs = [nv[i].sum() / dv[i].sum() for i in (rng.integers(0, len(nv), len(nv)) for _ in range(400)) if dv[i].sum() > 0]
    return (num.sum() / den.sum() if den.sum() > 0 else np.nan), (np.percentile(bs, 2.5) if bs else np.nan), (np.percentile(bs, 97.5) if bs else np.nan)
out = []
for field, F in D[D.n_u >= 3].groupby("field"):
    for name, ex, ref in (("QB+pcTE vs QB+WR (2-man)", "qb_pcte", "qb_wr"), ("QB+WR+pcTE vs QB+WR+WR (3-man)", "qb_wr_pcte", "qb_wr_wr"), ("any TE in the stack vs none", "qb_any_te", "qb_no_te")):
        r = {"field": field, "contrast": name}
        for k in (1, 5, 10, 20):
            e, lo, hi = mh(F, F[ex], F[ref], f"top{k}"); r[f"top{k}%"] = f"{e:.2f} [{lo:.2f}, {hi:.2f}]"
        r["per week, top 5%"] = " ".join(f"W{w}:{mh(F[F.week == w], F[F.week == w][ex], F[F.week == w][ref], 'top5')[0]:.2f}" for w in sorted(F.week.unique()))
        out.append(r)
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 40)
print("\nwithin-user odds ratio [95%] of finishing in the top k% (users with 3+ lineups in that field-week):"); print(pd.DataFrame(out).to_string(index=False))
print("\nshare of lineups by stack type:"); print(D.groupby("field")[["qb_pcte", "qb_wr", "qb_wr_pcte", "qb_wr_wr", "qb_any_te"]].mean().round(3).to_string())
print("\nWINNER-LIKE RATES: share of lineups with the QB stacked with ANY TE / a pass-catching TE, among all lineups vs the top 1% / top 5% (all entrants of the field, W2-4 where pass-catching TEs are defined):")
G = D[D.week >= 2]
for field, F in G.groupby("field"):
    for k in (1, 5):
        top = F[F[f"top{k}"]]
        print(f"  {field:17s} top {k}%: any TE stacked {top.qb_any_te.mean():.3f} (field {F.qb_any_te.mean():.3f}); pass-catching TE stacked {(top.pcte_m >= 1).mean():.3f} (field {(F.pcte_m >= 1).mean():.3f}); n top {len(top):,}")
