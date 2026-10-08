"""Screen of lineup SORT keys (operator 10-07: "how professionals sort lineups … I'd like other ideas"), on the four real
2026 Millionaire fields. For each week, the candidate pool is every lineup our builds kept that week (the union of the
archived runs' candidates for that week's draft group: lev + boom rows, built before lock on our projections). Each key
ranks the pool; the "book" is the top 26 by the key with at most 7 players shared between any two rows (Stokastic's
"uniques"); it is scored on the real field (each row's percentile; rows in the top 1%; the best row) and against 2,000
random 26-row books from the same pool (the monkeys benchmark: the key's percentile among random books). Every key is
pre-lock: frame facts, the last prop snapshot before the Sunday lock, the pre-lock ownership files (W3 lag/sets, W4 FP).
Keys: PROJ (sum of the projection the pool was built on), TD (sum of anytime-TD probabilities; the operator's request to
production), TD_VALUE (sum of TD-odds-above-salary z for players < $7k; the operator's cheap-upside idea), MARKET (sum of the
props-implied projections), OPTIMAL (sum of each player's share of the pool's boom rows, i.e. how often he is in a sampled
world's optimal lineup), LEVERAGE (sum of optimal share - projected ownership; W3/W4), UNIQUE (lowest ownership product among
rows above the pool's median projection; W3/W4), STACK (same-team pass-catchers with the QB + bring-backs), SALARY_LEFT
(most salary left among rows above the median projection). Usage: sort_screen.py OUT_DIR"""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
RUNS = Path.home() / "moneygate/inputs/runs"; OWN = {3: Path.home() / "moneygate/inputs/own/w3_ownership_sets.csv", 4: Path.home() / "moneygate/inputs/own/w4_ownership_fp.csv"}
GROUP = {1: 151307, 2: 153428, 3: 153769, 4: 154078}; K = 26; RNG = np.random.default_rng(20261007)
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
TDQ = BQ.query("""WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 4
      AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
  snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week) WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
  SELECT p.week, p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) td FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
  WHERE p.season = 2026 AND p.market = 'player_anytime_td' GROUP BY 1, 2""").to_dataframe(); TDQ["key"] = TDQ.player.map(canon)
allrows = []
for w in (1, 2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("id").copy(); fr["key"] = fr.display_name.map(canon)
    fr["proj"] = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0); fr["mkt"] = pd.to_numeric(fr.market_points, errors="coerce").fillna(fr.proj)
    fr = fr.merge(TDQ[TDQ.week == w][["key", "td"]], on="key", how="left")
    fr["tdres"] = np.nan
    for pos in ("RB", "WR", "TE"):
        g = fr[(fr.pos == pos) & fr.td.notna()]
        if len(g) > 5: b = np.polyfit(g.salary, g.td, 1); fr.loc[g.index, "tdres"] = g.td - np.polyval(b, g.salary)
    fr["tz"] = fr.groupby("pos").tdres.transform(lambda v: (v - v.mean()) / v.std())
    fr["td_value"] = np.where(fr.pos.isin(["RB", "WR", "TE"]) & (fr.salary < 7000), fr.tz.clip(lower=0).fillna(0), 0.0)
    fr["pown"] = np.nan
    if w in OWN:
        o = pd.read_csv(OWN[w]); fr["pown"] = fr.dk_player_id.astype("Int64").astype(str).map(dict(zip(o.dk_player_id.astype("Int64").astype(str), o.pred_own)))
    # actual points (the real contest's FPTS) and the field
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(fpts) fpts FROM `nfl_raw.contest_ownership` WHERE contest_id = '{cid}' GROUP BY 1").to_dataframe(); fp = dict(zip(own.display_name.map(canon), own.fpts))
    fr["act"] = fr.key.map(fp).fillna(0.0)
    field = np.sort(BQ.query(f"SELECT points FROM `nfl_raw.contest_entries` WHERE contest_id = '{cid}' AND season = 2026 AND week = {w}").to_dataframe().points.values.astype(float))
    top1 = field[int(0.99 * len(field))]
    # the pool: every archived run of the week's draft group
    cands = []
    for d in sorted(RUNS.iterdir()):
        r = json.loads((d / "receipt.json").read_text())
        if r.get("week") == w and int(r.get("draft_group", 0)) == GROUP[w] and (d / "candidates.parquet").exists():
            c = pd.read_parquet(d / "candidates.parquet", columns=["players", "tag"]); cands.append(c)
    C = pd.concat(cands, ignore_index=True); C["key9"] = C.players.map(lambda s: "|".join(sorted(str(s).split(",")))); C = C.drop_duplicates("key9").reset_index(drop=True)
    idx = {i: k for k, i in enumerate(fr.id.astype(str))}
    L = np.array([[idx.get(p, -1) for p in str(s).split(",")] for s in C.players]); ok = (L >= 0).all(axis=1); C, L = C[ok].reset_index(drop=True), L[ok]
    A = lambda col: fr[col].to_numpy(float)[L]
    pos = fr.pos.to_numpy()[L]; team = fr.team.astype(str).to_numpy()[L]; opp = fr.opp.astype(str).to_numpy()[L]
    act = A("act").sum(axis=1); pct = np.searchsorted(field, act, "left") / len(field)
    boom_rows = C.tag.astype(str).str.startswith("boom").to_numpy()
    share = np.zeros(len(fr))
    if boom_rows.any():
        for row in L[boom_rows]: share[row] += 1
        share /= boom_rows.sum()
    qi = (pos == "QB").argmax(axis=1); qteam = team[np.arange(len(L)), qi]; qopp = opp[np.arange(len(L)), qi]; sk = np.isin(pos, ["RB", "WR", "TE"]); pc = np.isin(pos, ["WR", "TE"])
    keys = {"PROJ": A("proj").sum(axis=1), "TD": np.nan_to_num(A("td")).sum(axis=1) - np.nan_to_num(A("td"))[np.arange(len(L)), qi],
            "TD_VALUE": A("td_value").sum(axis=1), "MARKET": A("mkt").sum(axis=1), "OPTIMAL": share[L].sum(axis=1),
            "STACK": (pc & (team == qteam[:, None])).sum(axis=1) + 0.9 * (sk & (team == qopp[:, None])).sum(axis=1) + 0.001 * A("proj").sum(axis=1)}
    sal = A("salary").sum(axis=1); proj = keys["PROJ"]; above = proj >= np.median(proj)
    keys["SALARY_LEFT"] = np.where(above, 50000 - sal, -1e9) + 0.001 * proj
    if np.isfinite(A("pown")).any():
        po = np.nan_to_num(A("pown"), nan=0.5).clip(0.1)
        keys["UNIQUE"] = np.where(above, -np.log(po / 100).sum(axis=1) * -1 * -1, -1e9)       # higher = rarer (lower ownership product)
        keys["LEVERAGE"] = (share[L] * 100 - po).sum(axis=1)
    def book(order):
        chosen, sets = [], []
        for i in order:
            s = set(L[i])
            if all(len(s & t) <= 7 for t in sets): chosen.append(i); sets.append(s)
            if len(chosen) == K: break
        return np.array(chosen)
    rand = np.array([RNG.choice(len(L), K, replace=False) for _ in range(2000)])
    r_top1 = (pct[rand] >= 0.99).sum(axis=1); r_best = pct[rand].max(axis=1); r_mean = pct[rand].mean(axis=1)
    print(f"\n== W{w}: pool {len(L):,} lineups (boom {int(boom_rows.sum()):,}); field {len(field):,}; top-1% line {top1:.1f}; pool rows in the top 1%: {(pct >= .99).mean():.2%}; random 26-row book: mean top-1% rows {r_top1.mean():.2f}, mean best pct {r_best.mean():.4f}", flush=True)
    for k, v in keys.items():
        b = book(np.argsort(-v, kind="stable")); t1 = int((pct[b] >= .99).sum()); bp = float(pct[b].max()); mp = float(pct[b].mean())
        rk = lambda x, dist: float((dist < x).mean() + 0.5 * (dist == x).mean())
        row = {"week": w, "key": k, "top1_rows": t1, "best_pct": round(bp, 5), "mean_pct": round(mp, 4), "vs_random_top1": round(rk(t1, r_top1), 3), "vs_random_best": round(rk(bp, r_best), 3), "vs_random_mean": round(rk(mp, r_mean), 3), "best_points": round(float(act[b].max()), 1)}
        allrows.append(row); print(f"   {k:12s} top-1% rows {t1:2d} (random-book pctile {row['vs_random_top1']:.2f}) | best row {row['best_points']:6.1f}, pct {bp:.4f} (rb pctile {row['vs_random_best']:.2f}) | mean pct {mp:.3f} (rb pctile {row['vs_random_mean']:.2f})", flush=True)
R = pd.DataFrame(allrows); R.to_csv(out / "sort_screen.csv", index=False)
print("\n== averages over the weeks each key exists (random-book percentile: 0.5 = no better than random)")
print(R.groupby("key")[["top1_rows", "vs_random_top1", "vs_random_best", "vs_random_mean"]].mean().round(3).sort_values("vs_random_best", ascending=False).to_string())
