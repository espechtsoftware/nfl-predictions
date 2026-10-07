"""Every factor for the players the winners had and we missed (operator 10-07: "were the matchups favorable? were there
injuries that made them get more plays?"), and the same factors as slate-wide predictors of an explosion.
PRE-LOCK (from the archived T-70 frame the build saw + the last pre-lock prop snapshot): projection played, the props-implied
projection (market_points), anytime-TD probability, matchup (the opponent's fantasy points allowed to the position, adjusted,
last 6: percentile among the slate's opponents, 100 = softest), the opponent's red-zone TD rate allowed, team total, spread,
teammates ruled Out (names + their shares) and the vacated target / carry share, depth change, own status.
OUTCOME (explanation only): that game's snaps %, targets, carries, red-zone targets / carries inside the 20, carries inside
the 5, touchdowns, yards; teammates whose snaps collapsed in the game (an in-game exit or benching) and their next-week
injury report. Part B: across every eligible skill player of the four weeks, the explosion rate (actual >= proj + 10 and
>= 1.8x proj) by each pre-lock factor's tercile. Usage: player_factors.py MISSING_TXT OUT_DIR"""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
FP_W4 = Path.home() / ".cache/laptop-agent/rehearsal/inputs/proj_fp-w4.csv"
OWN = {3: Path.home() / "moneygate/inputs/own/w3_ownership_sets.csv", 4: Path.home() / "moneygate/inputs/own/w4_ownership_fp.csv"}
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
# ---------------------------------------------------------------- the players (from missing_players.txt)
txt = Path(sys.argv[1]).read_text().splitlines(); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
players, wk, grp = [], None, None
for ln in txt:
    m = re.match(r"=== WEEK (\d)", ln)
    if m: wk, grp = int(m.group(1)), None; continue
    if ln.startswith("winner player"): grp = "winner"; continue
    if ln.startswith("--- the players our best"): grp = "ours_instead"; continue
    if ln.startswith("--- summary"): grp = None; continue
    if grp and len(ln) > 40 and not ln.startswith("---"):
        mm = re.search(r"[+-]\s*\d+\.\d\s+(yes|NO)\b", ln[70:]) if grp == "winner" else None
        players.append({"week": wk, "group": grp, "name": ln[:24].strip(), "pos": ln[25:29].strip(), "team": ln[30:34].strip(),
                        "in_ours": (mm is not None and mm.group(1) == "yes") if grp == "winner" else True})
P = pd.DataFrame(players); P["group"] = np.where((P.group == "winner") & P.in_ours, "winner_shared", np.where(P.group == "winner", "winner_MISSED", "ours_instead"))
# ---------------------------------------------------------------- frames
frames = {}
for w in (1, 2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id").copy()
    fr["key"] = fr.display_name.map(canon); fr["proj_played"] = pd.to_numeric(fr.mean_projection, errors="coerce")
    if w == 4:
        fp = pd.read_csv(FP_W4); m = dict(zip(fp.dk_draftable_id.astype("Int64").astype(str), fp.fp))
        v = fr.dk_draftable_id.astype("Int64").astype(str).map(m); fr["proj_played"] = np.where(v.notna(), v, fr.proj_played)
    if w in OWN:
        o = pd.read_csv(OWN[w]); fr["pown"] = fr.dk_player_id.astype("Int64").astype(str).map(dict(zip(o.dk_player_id.astype("Int64").astype(str), o.pred_own)))
    else: fr["pown"] = np.nan
    # matchup percentile: the opponent's points allowed to the player's position (higher = softer), among the slate's opponents
    fr["matchup_raw"] = np.nan
    for pos in ("QB", "RB", "WR", "TE"):
        col = f"{pos.lower()}_fp_allowed_adj_l6"
        if col in fr: fr.loc[fr.pos == pos, "matchup_raw"] = pd.to_numeric(fr.loc[fr.pos == pos, col], errors="coerce")
    fr["matchup_pct"] = fr.groupby("pos").matchup_raw.rank(pct=True) * 100
    fr["week"] = w; frames[w] = fr
F = pd.concat(frames.values(), ignore_index=True)
# ---------------------------------------------------------------- matchup proxy (pre-lock): 2025 allowed-to-position as a 6-game prior + 2026 weeks before W
al = BQ.query("""WITH a AS (SELECT x.season, x.week, x.team, r.position, x.dk_points FROM `nfl_features.player_week_actuals` x
      JOIN `nfl_features.player_week_role` r ON r.gsis_id = x.gsis_id AND r.season = x.season AND r.week = x.week
      WHERE x.season IN (2025, 2026) AND r.position IN ('QB', 'RB', 'WR', 'TE'))
  SELECT a.season, a.week, s.opponent def, a.position, SUM(a.dk_points) pts FROM a JOIN `nfl_features.schedule_long` s ON s.season = a.season AND s.week = a.week AND s.team = a.team
  WHERE s.game_type = 'REG' GROUP BY 1, 2, 3, 4""").to_dataframe()
def matchup_for(w):
    p25 = al[al.season == 2025].groupby(["def", "position"]).pts.mean(); cur = al[(al.season == 2026) & (al.week < w)].groupby(["def", "position"]).pts.agg(["sum", "count"])
    m = pd.DataFrame({"p25": p25}).join(cur, how="outer").fillna({"sum": 0, "count": 0}); prior = m.p25.fillna(m.p25.groupby(level=1).transform("mean"))
    m["allowed"] = (6 * prior + m["sum"]) / (6 + m["count"]); return m.allowed.to_dict()
for w, fr in frames.items():
    mm_ = matchup_for(w); fr["matchup_raw2"] = [mm_.get((o, p), np.nan) for o, p in zip(fr.opp.astype(str), fr.pos.astype(str))]
    fr["matchup_pct"] = fr.groupby("pos").matchup_raw2.rank(pct=True) * 100
F = pd.concat(frames.values(), ignore_index=True)
# ---------------------------------------------------------------- TD odds (last snapshot before each Sunday lock)
td = BQ.query("""WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 4
      AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
  snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week) WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
  SELECT p.week, p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) p FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
  WHERE p.season = 2026 AND p.market = 'player_anytime_td' GROUP BY 1, 2""").to_dataframe()
td["key"] = td.player.map(canon); F = F.merge(td[["week", "key", "p"]].rename(columns={"p": "td_prob"}), on=["week", "key"], how="left")
# ---------------------------------------------------------------- outcomes: actuals, snaps, red zone (explanation only)
ids = sorted(set(F.gsis_id.dropna().astype(str)))
act = BQ.query("SELECT * FROM `nfl_features.player_week_actuals` WHERE season = 2026 AND week BETWEEN 1 AND 5").to_dataframe()
snaps = BQ.query("SELECT week, player, team, position, offense_snaps, offense_pct FROM `nfl_raw.snap_counts` WHERE season = 2026 AND game_type = 'REG' AND week BETWEEN 1 AND 4").to_dataframe()
snaps["key"] = snaps.player.map(canon)
rz = BQ.query("""SELECT week, pid, SUM(rzt) rz20_targets, SUM(rzc) rz20_carries, SUM(glc) gl5_carries, SUM(tdx) tds, SUM(yds) yards, SUM(big) plays_20plus FROM (
   SELECT week, receiver_player_id pid, IF(pass_attempt = 1 AND yardline_100 <= 20, 1, 0) rzt, 0 rzc, 0 glc, IF(touchdown = 1 AND td_player_id = receiver_player_id, 1, 0) tdx,
          IF(complete_pass = 1, yards_gained, 0) yds, IF(complete_pass = 1 AND yards_gained >= 20, 1, 0) big FROM `nfl_raw.pbp` WHERE game_id LIKE '2026_0%' AND season_type = 'REG' AND week BETWEEN 1 AND 4 AND receiver_player_id IS NOT NULL
   UNION ALL SELECT week, rusher_player_id, 0, IF(rush_attempt = 1 AND yardline_100 <= 20, 1, 0), IF(rush_attempt = 1 AND yardline_100 <= 5, 1, 0), IF(touchdown = 1 AND td_player_id = rusher_player_id, 1, 0),
          yards_gained, IF(yards_gained >= 20, 1, 0) FROM `nfl_raw.pbp` WHERE game_id LIKE '2026_0%' AND season_type = 'REG' AND week BETWEEN 1 AND 4 AND rusher_player_id IS NOT NULL) GROUP BY 1, 2""").to_dataframe()
inj = BQ.query("SELECT week, team, gsis_id, full_name, position, report_status, report_primary_injury FROM `nfl_raw.injuries` WHERE season = 2026 AND game_type = 'REG' AND week BETWEEN 1 AND 5").to_dataframe()
inj["key"] = inj.full_name.map(canon)
A = act.rename(columns={"gsis_id": "gsis"}); F["gsis"] = F.gsis_id.astype(str)
F = F.drop(columns=[c for c in ("actual",) if c in F.columns]).merge(A[["gsis", "week", "targets", "receptions", "rec_yards", "rec_tds", "carries", "rush_yards", "rush_tds", "pass_attempts", "pass_tds", "dk_points"]].rename(columns={"dk_points": "actual"}), on=["gsis", "week"], how="left")
F = F.merge(rz.rename(columns={"pid": "gsis"}), on=["gsis", "week"], how="left")
F = F.merge(snaps[["week", "key", "team", "offense_pct"]].rename(columns={"offense_pct": "snap_pct_game"}), on=["week", "key", "team"], how="left")
for c in ("actual",):
    F[c] = pd.to_numeric(F[c], errors="coerce")
F["resid"] = F.actual - F.proj_played
# ---------------------------------------------------------------- per-team context: teammates Out pre-lock; starters whose snaps collapsed in the game
def team_context(w, team, pos):
    fr = F[(F.week == w) & (F.team == team) & F.pos.isin(["RB", "WR", "TE"])]
    rep_ = inj[(inj.week == w) & (inj.team == team) & inj.report_status.isin(["Out", "Doubtful"]) & inj.position.isin(["RB", "WR", "TE"])]
    prevf = frames.get(w - 1); shares = []
    for q in rep_.itertuples():
        src = F[(F.week == w) & (F.key == q.key)]
        if (src.empty or src.target_share_l4.isna().all()) and prevf is not None: src = prevf[prevf.key == q.key]
        ts = float(src.target_share_l4.iloc[0]) if len(src) and pd.notna(src.target_share_l4.iloc[0]) else np.nan
        cs = float(src.carry_share_l4.iloc[0]) if len(src) and pd.notna(src.carry_share_l4.iloc[0]) else np.nan
        shares.append(f"{q.full_name} {q.position} {q.report_status} (tgt {ts:.2f}/car {cs:.2f})" if pd.notna(ts) else f"{q.full_name} {q.position} {q.report_status} (no prior share)")
    outs = F.iloc[0:0]; outs_txt = ", ".join(shares) or "-"
    act_ = fr[fr.snap_pct_game.notna() & (fr.snap_share_l4 >= 0.5) & ~fr.index.isin(outs.index)]
    coll = act_[act_.snap_pct_game < 0.6 * act_.snap_share_l4]
    nxt = inj[(inj.week == w + 1) & (inj.team == team)]
    coll_txt = ", ".join(f"{r.display_name} {r.pos} {r.snap_pct_game:.0%} vs {r.snap_share_l4:.0%}" + (f" [W{w+1}: {nxt[nxt.key == r.key].report_status.iloc[0]} {nxt[nxt.key == r.key].report_primary_injury.iloc[0]}]" if (nxt.key == r.key).any() else "") for r in coll.itertuples()) or "-"
    return outs_txt, coll_txt
rows = []
for r in P.itertuples():
    m = F[(F.week == r.week) & (F.display_name == r.name) & (F.team == r.team)]
    if m.empty: m = F[(F.week == r.week) & (F.key == canon(r.name))]
    if m.empty: rows.append({"week": r.week, "group": r.group, "name": r.name}); continue
    x = m.iloc[0]; outs_txt, coll_txt = team_context(r.week, x.team, x.pos) if x.pos != "DST" else ("-", "-")
    usage_l4 = (x.targets_l4 if x.pos in ("WR", "TE") else x.carries_l4) if x.pos != "QB" else np.nan
    usage_g = (x.targets if x.pos in ("WR", "TE") else (x.carries if x.pos == "RB" else x.pass_attempts)) if x.pos != "DST" else np.nan
    rows.append({"week": r.week, "group": r.group, "name": r.name, "pos": x.pos, "team": x.team, "opp": x.opp, "sal": int(x.salary),
        "proj": round(x.proj_played, 1), "market": round(x.market_points, 1) if pd.notna(x.market_points) else None, "td_prob": round(x.td_prob, 2) if pd.notna(x.td_prob) else None,
        "pown": round(x.pown, 1) if pd.notna(x.pown) else None, "matchup_pct": round(x.matchup_pct) if pd.notna(x.matchup_pct) else None,
        "opp_rz_td": round(x.rz_td_rate_allowed_l6, 2) if pd.notna(x.get("rz_td_rate_allowed_l6")) else None, "team_tot": x.implied_team_total, "spread": x.spread,
        "status": f"{x.status}/{x.injury_status}", "depth": x.depth_rank, "depth_delta": x.depth_rank_delta, "vac_tgt": round(x.team_vacated_target_share, 2), "vac_car": round(x.team_vacated_carry_share, 2),
        "teammates_out_prelock": outs_txt, "snap_l4": round(x.snap_share_l4, 2) if pd.notna(x.snap_share_l4) else None, "snap_game": round(x.snap_pct_game, 2) if pd.notna(x.snap_pct_game) else None,
        "usage_l4_per_game": round(usage_l4, 1) if pd.notna(usage_l4) else None, "usage_game": usage_g,
        "rz_tgt": x.rz20_targets, "rz_car": x.rz20_carries, "gl_car": x.gl5_carries, "tds": x.tds, "yards": x.yards, "plays20": x.plays_20plus,
        "actual": round(x.actual, 1), "resid": round(x.resid, 1), "teammates_collapsed_in_game": coll_txt})
D = pd.DataFrame(rows); D.to_csv(out / "player_factors.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
for w in (1, 2, 3, 4):
    print(f"\n=================== WEEK {w} ===================")
    d = D[D.week == w].sort_values(["group", "pos"])
    print(d[["group", "name", "pos", "team", "opp", "sal", "proj", "market", "td_prob", "pown", "matchup_pct", "opp_rz_td", "team_tot", "spread", "depth_delta", "vac_tgt", "vac_car", "actual", "resid"]].to_string(index=False))
    print("  -- pre-lock teammates Out (share >= .08) / in-game usage / teammates whose snaps collapsed:")
    for r in d.itertuples():
        if r.pos == "DST": continue
        print(f"  {r.group:13s} {r.name:22s} out: {r.teammates_out_prelock} | snaps {r.snap_l4}->{r.snap_game}, usage/g {r.usage_l4_per_game}->{r.usage_game}, rz tgt {r.rz_tgt} car {r.rz_car} gl {r.gl_car}, TD {r.tds}, 20+ plays {r.plays20} | collapsed: {r.teammates_collapsed_in_game}")
# ---------------------------------------------------------------- part B: slate-wide, do these pre-lock factors predict an explosion?
S = F[F.pos.isin(["RB", "WR", "TE"]) & (F.proj_played >= 5) & F.actual.notna() & ~F.status.astype(str).isin(["O", "IR", "D", "OUT"])].copy()
S["boom"] = (S.actual >= S.proj_played + 10) & (S.actual >= 1.8 * S.proj_played)
S["market_minus_proj"] = S.market_points - S.proj_played
S["vac_own_type"] = np.where(S.pos == "RB", S.team_vacated_carry_share, S.team_vacated_target_share)
print(f"\n=================== PART B: {len(S)} skill player-weeks projected >= 5, four weeks; explosion = actual >= proj+10 and >= 1.8x proj; base rate {S.boom.mean():.1%} ===================")
def by_tercile(col, label):
    s = S[S[col].notna()].copy()
    if s[col].nunique() < 3: return
    s["t"] = s.groupby("week")[col].transform(lambda v: pd.qcut(v.rank(method="first"), 3, labels=["low", "mid", "high"]))
    g = s.groupby("t", observed=True).boom.agg(["mean", "count"]); wk = s.groupby(["week", "t"], observed=True).boom.mean().unstack()
    hi_minus_lo = (wk["high"] - wk["low"]).round(3).to_dict()
    print(f"  {label:58s} low {g.loc['low','mean']:.1%}  mid {g.loc['mid','mean']:.1%}  high {g.loc['high','mean']:.1%}  (n {int(g['count'].sum())}; high-low by week {hi_minus_lo})")
by_tercile("matchup_pct", "matchup: opponent's points allowed to the position")
by_tercile("rz_td_rate_allowed_l6", "opponent's red-zone TD rate allowed")
by_tercile("implied_team_total", "team implied total")
by_tercile("market_minus_proj", "props-implied projection minus the projection played")
by_tercile("td_prob", "anytime-TD probability")
by_tercile("proj_played", "the projection played (for reference)")
by_tercile("salary", "salary")
def yesno(mask, label):
    y, n = S[mask].boom, S[~mask].boom
    wk = {int(w): (round(float(S[mask & (S.week == w)].boom.mean()), 3) if (mask & (S.week == w)).any() else None) for w in (1, 2, 3, 4)}
    print(f"  {label:58s} no {n.mean():.1%} (n {len(n)})  yes {y.mean() if len(y) else float('nan'):.1%} (n {len(y)})  yes-rate by week {wk}")
yesno(S.vac_own_type.fillna(0) >= 0.10, "teammates Out vacate >= 10% of the own-type share (pre-lock)")
yesno(S.depth_rank_delta.fillna(0).astype(float) < 0, "moved up the depth chart this week (pre-lock)")
yesno(S.market_minus_proj.fillna(0) >= 1.5, "props-implied projection >= projection + 1.5 (pre-lock)")
S.to_csv(out / "slate_explosions.csv", index=False)
