"""The operator 10-09: the limited-entry contests (4444 / 555 / 333 / FFWC / Milly satellites) -- what did the top 3 finishers
select, and how were their selections better than ours? Real rosters, real points (the money gate's W1-4 fields), the T-70
frame for salary / projection / game, ownership = the share of THAT contest's lineups holding the player. Private outputs
stay here; stdout carries aggregates and public NFL names."""
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import moneygate_score as MS  # noqa: E402

GROUP_OF = [("$4,444", "4444 sat"), ("$555", "555 sat"), ("$333", "333 sat"), ("FFWC", "FFWC"), ("World Championship", "FFWC"),
            ("SUPERSat to $20", "$20 Milly sat"), ("Satellite to $20", "$20 Milly sat")]


def group(name: str) -> str | None:
    for k, g in GROUP_OF:
        if k in name:
            return g
    return None


cfg = MS.load_config()
REC = []
DETAIL = []
for w in (1, 2, 3, 4):
    W = MS.load_week(cfg, w)
    e = cfg["weeks"][str(w)]
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
    fr["cn"] = fr.display_name.map(MS.canon)
    fr = fr[~fr.cn.duplicated(keep=False)].set_index("cn")
    fp = {}
    if e.get("fp_proj_source"):
        f = pd.read_csv(e["fp_proj_source"]); fp = dict(zip(f["id"].astype(str), f.fp))
    pts = {k: v / 100.0 for k, v in W.fpts.items()}
    names_by_cid = dict(zip(W.history.Contest_Key, W.history.Entry))
    for cid in sorted(set(W.history.Contest_Key)):
        nm = (W.details.get(cid, {}) or {}).get("name") or names_by_cid.get(cid, "?")
        g = group(nm)
        if g is None:
            continue
        fc = W.field[(W.field.contest_id == cid) & (W.field.names.map(len) == 9)]
        if len(fc) < 10:
            continue
        own = Counter(p for names in fc.names for p in names)
        n = len(fc)
        ours_ids = set(W.history[W.history.Contest_Key == cid].Entry_Key)

        def feats(names):
            r = [fr.loc[p] if p in fr.index else None for p in names]
            if any(x is None for x in r):
                return None
            pos = [x.pos for x in r]; team = [x.team for x in r]; opp = [x.opp for x in r]; game = [x.game_id for x in r]
            sal = [float(x.salary) for x in r]
            qb = pos.index("QB")
            mates = sum(1 for i in range(9) if pos[i] in ("WR", "TE") and team[i] == team[qb])
            rb_mate = sum(1 for i in range(9) if pos[i] == "RB" and team[i] == team[qb])
            bring = sum(1 for i in range(9) if pos[i] in ("RB", "WR", "TE") and team[i] == opp[qb])
            gcount = Counter(game[i] for i in range(9) if pos[i] != "DST")
            flex = [p for p in pos]
            nwr, nrb, nte = pos.count("WR"), pos.count("RB"), pos.count("TE")
            flex_pos = "WR" if nwr == 4 else "RB" if nrb == 3 else "TE" if nte == 2 else "?"
            o = [own[p] / n for p in names]
            pr = [float(x.mean_projection) for x in r]
            fpp = [fp.get(str(x.id), np.nan) for x in r]
            rp = [pts.get(p, 0.0) for p in names]
            return {"salary": sum(sal), "proj": sum(pr), "fp_proj": sum(fpp) if not any(np.isnan(fpp)) else np.nan,
                    "points": sum(rp), "own_sum": sum(o), "own_geo": float(np.exp(np.mean(np.log(np.maximum(o, 1e-4))))),
                    "low_own": sum(1 for x in o if x < 0.10), "very_low": sum(1 for x in o if x < 0.03),
                    "mates": mates, "rb_mate": rb_mate, "bring": bring, "top_game": max(gcount.values()), "games": len(gcount),
                    "flex": flex_pos, "studs": sum(1 for s, p in zip(sal, pos) if s >= 8000), "cheap": sum(1 for s, p in zip(sal, pos) if s < 4000 and p != "DST"),
                    "qb_sal": sal[qb], "te_sal": sal[pos.index("TE")], "dst_sal": sal[pos.index("DST")],
                    "boom": sum(1 for x in rp if x >= 25), "proj_rank_gap": None}
        fc = fc.assign(is_ours=fc.entry_id.isin(ours_ids))
        best_rank = fc["rank"].min()
        for _, row in fc.iterrows():
            f = feats(row.names)
            if f is None:
                continue
            kind = "ours" if row.is_ours else ("top3" if row["rank"] <= 3 else "field")
            REC.append({"week": w, "group": g, "contest": nm, "cid": cid, "n": n, "rank": int(row["rank"]), "kind": kind, **f})
            if kind == "top3" or (row.is_ours):
                DETAIL.append({"week": w, "group": g, "contest": nm, "n": n, "rank": int(row["rank"]), "kind": kind,
                               "players": [(p, round(pts.get(p, 0.0), 1), round(own[p] / n, 3)) for p in row.names], **f})
D = pd.DataFrame(REC)
D.to_csv((Path.home() / "private" / "limited-entry-winners" / "lineups.csv"), index=False)
pd.DataFrame(DETAIL).to_json((Path.home() / "private" / "limited-entry-winners" / "detail.json"), orient="records", indent=1)
print("contests:", D.groupby("group").cid.nunique().to_dict(), " lineups:", len(D))
cols = ["points", "proj", "salary", "own_sum", "own_geo", "low_own", "very_low", "mates", "rb_mate", "bring", "top_game", "games",
        "studs", "cheap", "qb_sal", "te_sal", "dst_sal", "boom"]
pd.set_option("display.width", 250)
for g, gd in D.groupby("group"):
    t = gd.groupby("kind")[cols].mean().round(2).reindex(["top3", "ours", "field"])
    fx = gd.groupby("kind").flex.value_counts(normalize=True).unstack().round(2).reindex(["top3", "ours", "field"])
    print(f"\n== {g}: contests {gd.cid.nunique()}, lineups: top3 {int((gd.kind == 'top3').sum())}, ours {int((gd.kind == 'ours').sum())}, field {int((gd.kind == 'field').sum())}")
    print(t.to_string())
    print("flex share:"); print(fx.to_string())
