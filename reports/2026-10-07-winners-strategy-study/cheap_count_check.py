"""The graph finding (10-07): within the regulars' own portfolios, lineups with more sub-$4,000 non-DST players hit the top
1% far more often. Does the same hold (a) in the whole real field, (b) in our own candidate pool, and (c) how many such
players do our books carry? Pre-lock: salary < $4,000 from the week's T-70 frame. Usage: cheap_count_check.py OUT_DIR"""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
RUNS = Path.home() / "moneygate/inputs/runs"; GROUP = {1: 151307, 2: 153428, 3: 153769, 4: 154078}
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
res_field, res_pool, res_book = [], [], []
for w in (1, 2, 3, 4):
    t70 = Path(CFG["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(t70 / "frame.parquet").drop_duplicates("id")
    cheap = fr[(fr.salary < 4000) & (fr.pos != "DST")]; names = cheap.display_name.astype(str).tolist()
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    q = """WITH e AS (SELECT DISTINCT entry_id, rank, players_key, expected_entries n FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w)
      SELECT k, COUNT(*) lineups, COUNTIF(rank <= 0.01 * n) top1 FROM (SELECT entry_id, ANY_VALUE(rank) rank, ANY_VALUE(n) n, COUNTIF(nm IN UNNEST(@names)) k FROM e, UNNEST(SPLIT(players_key, '|')) nm GROUP BY entry_id) GROUP BY k ORDER BY k"""
    t = BQ.query(q, job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w), bigquery.ArrayQueryParameter("names", "STRING", names)])).to_dataframe()
    t["week"] = w; res_field.append(t)
    # our pool, scored on the real field
    own = BQ.query(f"SELECT display_name, ANY_VALUE(fpts) fpts FROM `nfl_raw.contest_ownership` WHERE contest_id = '{cid}' GROUP BY 1").to_dataframe(); fp = dict(zip(own.display_name.map(canon), own.fpts))
    field = np.sort(BQ.query(f"SELECT points FROM `nfl_raw.contest_entries` WHERE contest_id = '{cid}' AND season = 2026 AND week = {w}").to_dataframe().points.values.astype(float))
    act = dict(zip(fr.id.astype(str), fr.display_name.map(canon).map(fp).fillna(0.0))); sal = dict(zip(fr.id.astype(str), fr.salary)); pos = dict(zip(fr.id.astype(str), fr.pos))
    cands = []
    for d in sorted(RUNS.iterdir()):
        r = json.loads((d / "receipt.json").read_text())
        if r.get("week") == w and int(r.get("draft_group", 0)) == GROUP[w] and (d / "candidates.parquet").exists(): cands.append(pd.read_parquet(d / "candidates.parquet", columns=["players"]))
    C = pd.concat(cands).players.map(lambda s: tuple(sorted(str(s).split(",")))).drop_duplicates()
    rows = [(sum(1 for p in L if pos.get(p) != "DST" and sal.get(p, 9999) < 4000), sum(act.get(p, 0.0) for p in L)) for L in C if all(p in act for p in L)]
    P = pd.DataFrame(rows, columns=["k", "pts"]); P["top1"] = np.searchsorted(field, P.pts.values, "left") / len(field) >= 0.99
    p = P.groupby("k").top1.agg(["size", "sum"]).reset_index().rename(columns={"size": "lineups", "sum": "top1"}); p["week"] = w; res_pool.append(p)
    # our entered-style books: the live W5-settings replay books (W2-4) and the week's T-70 book
    for tag, bp in (("t70 book", t70 / "book.csv"),):
        if bp.exists():
            b = pd.read_csv(bp); ids = [c for c in b.columns if b[c].astype(str).str.contains("_DST|00-00").any()]
            ks = [sum(1 for p in row if pos.get(str(p)) != "DST" and sal.get(str(p), 9999) < 4000) for row in b[ids].astype(str).values] if ids else []
            res_book.append({"week": w, "book": tag, "rows": len(ks), "mean_cheap": round(float(np.mean(ks)), 2) if ks else None, "share_with_2plus": round(float(np.mean([k >= 2 for k in ks])), 3) if ks else None})
F = pd.concat(res_field); Pp = pd.concat(res_pool)
for name, T in (("THE WHOLE REAL FIELD", F), ("OUR CANDIDATE POOL (scored on the real field)", Pp)):
    T = T.assign(k=T.k.clip(upper=3)).groupby(["week", "k"])[["lineups", "top1"]].sum(); T["top1_rate_%"] = (100 * T.top1 / T.lineups).round(2); T["share_%"] = (100 * T.lineups / T.groupby(level=0).lineups.transform("sum")).round(1)
    print(f"\n{name}: top-1% rate by number of sub-$4,000 non-DST players (3 = 3+)"); print(T[["share_%", "top1_rate_%"]].unstack(0).to_string())
print("\nour T-70 books:"); print(pd.DataFrame(res_book).to_string(index=False))
F.to_csv(out / "cheap_field.csv", index=False); Pp.to_csv(out / "cheap_pool.csv", index=False)
