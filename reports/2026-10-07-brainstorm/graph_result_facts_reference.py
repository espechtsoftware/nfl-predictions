"""Reference values for the Neo4j result facts and lineup labels proposed in the 10-07 brainstorm (D2, D3), so the loader
can be tested against them. W1-4 (weeks.json T-70 runs) on each week's largest Millionaire. Post-game facts: keep them
apart from the pre-lock facts. Aggregates only; no entry ids, no user names.

GAME facts (one row per game in the week's T-70 frame = the DK main slate):
  total          max of the frame's game_total over the game's rows
  total_rank     1 = highest total; ties broken by game_id order; a game without a total ranks last
                 (field_pattern_monitor.game_total_ranks -- the same rule the 2014-2025 base rates used)
  best_stack_pts for each of the game's two teams: the team's best QB (max DK points among its QBs, 0 if none) + its two
                 best non-QB skill players (RB/WR/TE) + the opponent's best non-QB skill player; max over the two teams.
                 DK points from nfl_features.player_week_actuals, positions from player_week_role (same season/week;
                 players without a role row are left out), team -> game through the frame. DST and K excluded.
  is_best_stack_game  best_stack_pts equals the week's maximum (ties: every tied game true)
  field_qb_share share of the contest's lineups (distinct entry_id) whose QB is from the game, among lineups whose QB
                 resolved to a priced frame QB by exact display name
  top1_qb_share  the same among lineups with rank <= 1% of expected_entries

LINEUP labels (every lineup whose nine names all match a priced frame row; DST's team/game = its team's):
  lbl_stack_n    players on the QB's team other than the QB and DST
  lbl_bring_n    players on the QB's opponent other than DST
  lbl_flex_pos   'RB' if 3 RBs, else 'WR' if 4 WRs, else 'TE' if 2 TEs (a legal classic lineup has exactly one)
  lbl_max_game   the most players (of 9, DST included) from one game
  (also printed for cross-checks: n_games = distinct games of the 9; sal_left = 50,000 - total salary)
Outputs: graph_result_facts_reference_games.csv, graph_result_facts_reference_labels.csv (label, value, lineups, top1)."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

HERE = Path(__file__).resolve().parent
_s = importlib.util.spec_from_file_location("fpm", HERE.parents[1] / "scripts" / "field_pattern_monitor.py"); FPM = importlib.util.module_from_spec(_s); _s.loader.exec_module(FPM)
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); GAMES, LABELS = [], []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    kmap = FPM.game_total_ranks(fr); tot = pd.to_numeric(fr.groupby("game_id").game_total.max(), errors="coerce")
    pr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name")
    team_game = dict(zip(fr.team.astype(str), fr.game_id.astype(str)))
    a = BQ.query(f"""SELECT a.team, r.position, a.dk_points FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r
        ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week WHERE a.season = 2026 AND a.week = {w} AND r.position IN ('QB','RB','WR','TE')""").to_dataframe()
    a["dk_points"] = pd.to_numeric(a.dk_points, errors="coerce").fillna(0.0); a["game_id"] = a.team.astype(str).map(team_game); a = a[a.game_id.notna()]
    best = {}
    for gid, g in a.groupby("game_id"):
        vals = []
        for tm, t in g.groupby("team"):
            qb = t[t.position == "QB"].dk_points.max(); qb = 0.0 if np.isnan(qb) else float(qb)
            mates = float(np.sort(t[t.position != "QB"].dk_points.values)[::-1][:2].sum())
            opp = g[(g.team != tm) & (g.position != "QB")].dk_points.max(); opp = 0.0 if np.isnan(opp) else float(opp)
            vals.append(qb + mates + opp)
        best[gid] = round(max(vals), 2)
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", pr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in pd.to_numeric(pr.salary)]),
        bigquery.ArrayQueryParameter("pos", "STRING", pr.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("team", "STRING", pr.team.astype(str).tolist()),
        bigquery.ArrayQueryParameter("opp", "STRING", pr.opp.astype(str).tolist()), bigquery.ArrayQueryParameter("game", "STRING", pr.game_id.astype(str).tolist())])
    base = """WITH m AS (SELECT n, s, p, t, o, g FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
                    JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b JOIN UNNEST(@game) g WITH OFFSET c ON i = c),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      x AS (SELECT e.entry_id, ANY_VALUE(e.rank) <= 0.01 * ANY_VALUE(e.ne) top1, ARRAY_AGG(IF(m.n IS NULL, NULL, STRUCT(m.s, m.p, m.t, m.o, m.g)) IGNORE NULLS) pl,
                   COUNT(m.n) matched FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.entry_id)"""
    q = BQ.query(base + """ SELECT (SELECT ANY_VALUE(z.g) FROM UNNEST(pl) z WHERE z.p = 'QB') qb_game, COUNT(*) n, COUNTIF(top1) t FROM x GROUP BY 1""", job_config=jc).to_dataframe()
    qr = q[q.qb_game.notna()]
    for gid in sorted(tot.index.astype(str)):
        r = qr[qr.qb_game == gid]
        GAMES.append({"week": w, "game_id": gid, "total": float(tot.get(gid, np.nan)), "total_rank": int(kmap[gid]), "best_stack_pts": best.get(gid, np.nan),
                      "field_qb_share": round(r.n.sum() / qr.n.sum(), 4), "top1_qb_share": round(r.t.sum() / max(qr.t.sum(), 1), 4)})
    lab = BQ.query(base + """, y AS (SELECT top1, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo
                                     FROM x WHERE matched = 9)
      SELECT top1, (SELECT COUNTIF(z.t = qbt AND z.p NOT IN ('QB', 'DST')) FROM UNNEST(pl) z) stack_n, (SELECT COUNTIF(z.t = qbo AND z.p != 'DST') FROM UNNEST(pl) z) bring_n,
             CASE WHEN (SELECT COUNTIF(z.p = 'RB') FROM UNNEST(pl) z) = 3 THEN 'RB' WHEN (SELECT COUNTIF(z.p = 'WR') FROM UNNEST(pl) z) = 4 THEN 'WR'
                  WHEN (SELECT COUNTIF(z.p = 'TE') FROM UNNEST(pl) z) = 2 THEN 'TE' ELSE 'other' END flex_pos,
             (SELECT MAX(c) FROM (SELECT COUNT(*) c FROM UNNEST(pl) z GROUP BY z.g)) max_game, (SELECT COUNT(DISTINCT z.g) FROM UNNEST(pl) z) n_games,
             50000 - (SELECT SUM(z.s) FROM UNNEST(pl) z) sal_left FROM y""", job_config=jc).to_dataframe()
    nall = int(q.n.sum())
    for col in ("stack_n", "bring_n", "flex_pos", "max_game", "n_games"):
        g = lab.groupby(col).top1.agg(["size", "sum"]).reset_index()
        for _, rr in g.iterrows():
            LABELS.append({"week": w, "label": col, "value": str(rr[col]), "lineups": int(rr["size"]), "top1": int(rr["sum"])})
    LABELS.append({"week": w, "label": "sal_left_mean", "value": f"{lab.sal_left.mean():.1f}", "lineups": len(lab), "top1": int(lab.top1.sum())})
    LABELS.append({"week": w, "label": "excluded_unmatched", "value": "lineups with < 9 matched names", "lineups": nall - len(lab), "top1": int(q.t.sum() - lab.top1.sum())})
    gw = pd.DataFrame([x for x in GAMES if x["week"] == w]); mx = gw.best_stack_pts.max()
    print(f"W{w}: contest {cid}; games {len(gw)}; best stack {mx:.2f} in total-rank {', '.join(str(int(k)) for k in gw[gw.best_stack_pts == mx].total_rank)}; "
          f"lineups {nall:,} (QB resolved {qr.n.sum() / nall:.3f}; 9 matched {len(lab) / nall:.3f})", flush=True)
G = pd.DataFrame(GAMES); G["is_best_stack_game"] = G.best_stack_pts == G.groupby("week").best_stack_pts.transform("max")
G.to_csv(HERE / "graph_result_facts_reference_games.csv", index=False); L = pd.DataFrame(LABELS); L.to_csv(HERE / "graph_result_facts_reference_labels.csv", index=False)
pd.set_option("display.width", 220)
print("\nGAME facts:"); print(G.to_string(index=False))
print("\nLABEL distributions (whole field, lineups with 9 matched names; top1 = of them in the top 1%):")
print(L.pivot_table(index=["label", "value"], columns="week", values="lineups", aggfunc="sum").fillna(0).astype(int).to_string())
