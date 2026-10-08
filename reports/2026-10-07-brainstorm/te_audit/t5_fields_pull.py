"""Task 5a: pull the W3/W4 Millionaire lineups (aggregated per entry in BigQuery; users fingerprinted, never named) and tag each lineup's
QB stack. Writes fields_w3w4.parquet."""
import sys, json; sys.path.insert(0, ".")
from pathlib import Path
import numpy as np, pandas as pd
from bqh import q
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
out = []
for w in (3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].copy()
    assert not fr.display_name.duplicated().any()
    cid = CFG["weeks"][str(w)]["millionaire_contest"]
    sql = """
    WITH m AS (SELECT n, p, t, o FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
               JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b),
    e AS (SELECT entry_id, rank, points, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key
          FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
    x AS (SELECT e.entry_id, ANY_VALUE(e.u) u, ANY_VALUE(e.rank) rank, ANY_VALUE(e.points) points, ANY_VALUE(e.players_key) pk,
                 COUNT(m.n) matched, ARRAY_AGG(STRUCT(nm AS n, m.p, m.t, m.o)) pl
          FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.entry_id)
    SELECT entry_id, u, rank, points, matched, pk,
      (SELECT ANY_VALUE(z.n) FROM UNNEST(pl) z WHERE z.p = 'QB') qb,
      (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt,
      (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo,
      (SELECT STRING_AGG(z2.n, '|' ORDER BY z2.n) FROM UNNEST(pl) z2 WHERE z2.p = 'TE' AND z2.t = (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB')) te_mates,
      (SELECT STRING_AGG(z2.n, '|' ORDER BY z2.n) FROM UNNEST(pl) z2 WHERE z2.p = 'WR' AND z2.t = (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB')) wr_mates,
      (SELECT STRING_AGG(z2.n, '|' ORDER BY z2.n) FROM UNNEST(pl) z2 WHERE z2.p = 'RB' AND z2.t = (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB')) rb_mates,
      (SELECT COUNTIF(z2.t = (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') AND z2.p IN ('TE')) FROM UNNEST(pl) z2) te_m,
      (SELECT COUNTIF(z2.t = (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') AND z2.p IN ('WR')) FROM UNNEST(pl) z2) wr_m,
      (SELECT COUNTIF(z2.t = (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') AND z2.p IN ('RB')) FROM UNNEST(pl) z2) rb_m,
      (SELECT COUNTIF(z2.t = (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') AND z2.p IN ('WR','TE','RB')) FROM UNNEST(pl) z2) bring_m,
      (SELECT STRING_AGG(z2.n, '|' ORDER BY z2.n) FROM UNNEST(pl) z2 WHERE z2.p = 'TE') all_te
    FROM x"""
    d = q(sql, c=cid, w=w, names=fr.display_name.astype(str).tolist(), pos=fr.pos.astype(str).tolist(),
          team=fr.team.astype(str).tolist(), opp=fr.opp.astype(str).tolist())
    d["week"] = w; d["contest_id"] = cid; d["n_entries"] = len(d)
    # privacy: players_key holds only NFL player names; dropped after counting unmatched names
    um = pd.Series([nm for pk, mt in zip(d.pk, d.matched) if mt < 9 for nm in pk.split("|")])
    print(f"W{w} contest {cid}: {len(d):,} entries; all 9 matched: {(d.matched == 9).mean():.4f}; unmatched-name examples: "
          f"{um[~um.isin(fr.display_name)].value_counts().head(8).to_dict()}")
    out.append(d.drop(columns=["pk"]))
D = pd.concat(out, ignore_index=True)
D.to_parquet("fields_w3w4.parquet")
print(D.groupby("week").agg(n=("entry_id", "size"), users=("u", "nunique"), matched9=("matched", lambda s: (s == 9).mean())).to_string())
