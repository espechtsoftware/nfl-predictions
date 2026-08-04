"""LLM persona field ("silicon sampling") vs naive ownership vs REAL
contest ownership (raw.contest_ownership, 2022-25).

Test: for 3 held-out 2025 weeks, personas receive the same public info a
DFS player sees (salary, trailing form, Vegas context) and emit exposure
percentages. The persona mix's aggregate is scored against actual
pct_drafted from the largest imported GPP that week — Spearman rank corr
+ MAE on matched players — with the system's naive_ownership as the
incumbent. Personas only earn a September A/B if they beat naive here.
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
from scipy.stats import spearmanr

from nfl_dfs.backtest.field import naive_ownership
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

import anthropic

S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"
WEEKS = [(2025, 5), (2025, 10), (2025, 15)]
PERSONAS = {
    "casual": ("You are a casual DFS player who plays for fun on Sundays. "
               "You love famous names, players on good teams in high-total "
               "games, and anyone who scored a lot last week. You barely "
               "look at salary efficiency.", 0.55),
    "value": ("You are a value-hunting DFS regular. You grind points-per-"
              "dollar: recent production divided by salary drives you, and "
              "you jump on cheap starters after injuries elevate them.", 0.25),
    "sharp": ("You are a professional DFS player. You build around Vegas "
              "totals and spreads, target correlation (QB with receivers), "
              "and deliberately avoid over-owned obvious plays.", 0.15),
    "homer": ("You are a fan who rosters players from the teams in the "
              "biggest prime-time narrative spots and stars from your "
              "favorite big-market teams.", 0.05),
}

panel = pd.read_parquet(f"{S}/panel.parquet")
names = query_df(f"""
  SELECT DISTINCT gsis_id, ANY_VALUE(full_name) AS player_name
  FROM `{settings.raw}.rosters_weekly` WHERE season = 2025
  GROUP BY gsis_id""")
panel = panel.merge(names, on="gsis_id", how="left")
panel = panel[panel.player_name.notna()]
client = anthropic.Anthropic()

own = query_df(f"""
  SELECT season, week, contest_id, contest_name, display_name,
         roster_position, pct_drafted
  FROM `{settings.raw}.contest_ownership`
  WHERE season = 2025 AND week IN (5, 10, 15)
""")


def norm_name(s):
    s = str(s).lower().strip()
    s = re.sub(r"[^a-z ]", "", s)
    parts = s.split()
    return parts[0][0] + " " + parts[-1] if len(parts) >= 2 else s


results = []
for season, week in WEEKS:
    wk = panel[(panel.season == season) & (panel.week == week)].copy()
    wk = wk[wk.position.isin(["QB", "RB", "WR", "TE"])]
    wk = wk[wk.salary.notna() & (wk.salary >= 3000)]
    wk = wk.sort_values("salary", ascending=False).head(90)
    # the largest imported contest that week
    ow = own[(own.season == season) & (own.week == week)]
    if ow.empty:
        print(f"no ownership for {season} w{week}"); continue
    big = ow.groupby("contest_id").size().idxmax()
    ow = ow[ow.contest_id == big].copy()
    ow["pct"] = pd.to_numeric(ow.pct_drafted, errors="coerce")
    ow["key"] = ow.display_name.map(norm_name)
    ow = ow.groupby("key", as_index=False).pct.max()

    lines = [f"{r.player_name}|{r.position}|{r.team}|${int(r.salary)}|"
             f"l4avg {0 if pd.isna(r.dk_points_l4) else round(r.dk_points_l4,1)}|"
             f"teamtotal {0 if pd.isna(r.implied_team_total) else round(r.implied_team_total,1)}"
             for r in wk.itertuples()]
    slate_txt = "\n".join(lines)
    agg = pd.Series(0.0, index=wk.player_name)
    for pname, (sysmsg, wgt) in PERSONAS.items():
        msg = client.messages.create(
            model="claude-sonnet-5", max_tokens=6000,
            thinking={"type": "disabled"},
            system=sysmsg + " Reply ONLY with JSON.",
            messages=[{"role": "user", "content":
                f"DraftKings NFL main slate, {season} week {week}. Players "
                f"(name|pos|team|salary|recent avg|vegas team total):\n"
                f"{slate_txt}\n\nGive YOUR exposure percentage (how often "
                f"you'd roster each player across your entries, 0-100) for "
                f"the 40 players you'd actually consider, as JSON "
                f'{{"Player Name": pct, ...}}.'}])
        txt = next((b.text for b in msg.content if b.type == "text"), "")
        if not txt:
            print(f"  no text block {pname} {season} w{week}"); continue
        try:
            d = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        except Exception:
            print(f"  parse fail {pname} {season} w{week}"); continue
        s = pd.Series(d, dtype=float).clip(0, 100)
        agg = agg.add(s.reindex(agg.index).fillna(0) * wgt, fill_value=0)
        print(f"  {pname} w{week}: {len(d)} players", flush=True)

    wk = wk.assign(persona=agg.values)
    frame = wk.rename(columns={"position": "pos"}).copy()
    frame["proj"] = frame.dk_points_l4.fillna(0)
    frame["naive"] = naive_ownership(frame[["pos", "proj", "salary"]].assign(
        pos=frame.pos)) * 100 * 9  # weights->rough pct scale (9 slots)
    frame["key"] = frame.player_name.map(norm_name)
    m = frame.merge(ow, on="key", how="inner")
    m = m[m.pct.notna()]
    for col in ("persona", "naive"):
        rho = spearmanr(m[col], m.pct).statistic
        mae = float((m[col] / m[col].sum() - m.pct / m.pct.sum()).abs().mean() * 100)
        results.append({"week": week, "model": col, "n": len(m),
                        "spearman": round(float(rho), 3),
                        "mae_sharepts": round(mae, 3)})
        print(f"{season} w{week} {col:8s} n={len(m)} rho={rho:.3f} mae={mae:.3f}",
              flush=True)

print("\nSUMMARY")
r = pd.DataFrame(results)
if len(r):
    print(r.groupby("model")[["spearman", "mae_sharepts"]].mean().round(3))
print("PERSONA_DONE", flush=True)
