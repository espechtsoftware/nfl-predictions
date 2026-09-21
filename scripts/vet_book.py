"""Post-selection VETTING pass: look at every player in every lineup of a finished book for availability / dead-slot
risk, then reorder the book so risk-free lineups keep the selector's greedy order at the front and lineups carrying
flagged players are demoted (hard flags = pushed behind every clean lineup).  Emits an emitter-compatible sibling
run dir (book.csv in the vetted order + frame.parquet + receipt) and a report of every move.  Outcome-blind.

Signals (per player, all live at run time):
  DK feed status (frame.status): O / IR / OUT -> HARD;  D -> 3;  Q -> 1
  nfl_raw.injuries (latest report for season/week): Out -> HARD; Doubtful -> 3; Questionable -> 1;
                                                     practice DNP (real injury, market silent) -> 2; DNP with props posted -> 0.5;
                                                     DNP rest/NIR -> 0; Limited -> 0.5
  nfl_features.player_week_inference: injury_status (same map); practice_level < 1 -> 0.5; depth_rank >= 3 (RB/TE) -> 0.5;
                                       games_missed_l4 >= 2 -> 0.5
  prop lines (nfl_raw.prop_lines, two latest fetch days): implied >= 5 pts in the previous fetch but ABSENT now -> HARD
                                                          (market pulled the player); no props at all and salary >= 5000 -> 1
  placeholder salary (< 2500) -> HARD
Usage: PYTHONPATH=<prod>/src python vet_book.py RUN_DIR [--k 30] [--output-dir DIR] [--season 2026] [--week 1]"""
import argparse, csv, json, pathlib, shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
import numpy as np, pandas as pd
from google.cloud import bigquery
from nfl_dfs.names import norm_name

SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
W = {"player_reception_yds": 0.1, "player_rush_yds": 0.1, "player_pass_yds": 0.04, "player_receptions": 1.0, "player_pass_tds": 4.0}
HARD = 100.0

def implied_prob(a): a = float(a); return 100 / (a + 100) if a > 0 else -a / (-a + 100)

def status_weight(s):
    s = str(s or "").strip().lower()
    if s in ("o", "out", "ir", "injured reserve", "pup", "nfi", "sus", "suspended"): return HARD, "OUT"
    if s in ("d", "doubtful"): return 3.0, "Doubtful"
    if s in ("q", "questionable"): return 1.0, "Questionable"
    return 0.0, None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--k", type=int, default=30); ap.add_argument("--output-dir"); ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True); ap.add_argument("--material-threshold", type=float, default=1.0); ap.add_argument("--qb-flags", default=""); a = ap.parse_args()
    run = pathlib.Path(a.run); out = pathlib.Path(a.output_dir or (str(run) + "-vetted")); out.mkdir(parents=True, exist_ok=True)
    f = pd.read_parquet(run / "frame.parquet"); f["dk"] = f.dk_player_id.astype(str)
    name = dict(zip(f.dk, f.display_name.astype(str))); pos = dict(zip(f.dk, f.position.astype(str))); team = dict(zip(f.dk, f.team.astype(str)))
    sal = dict(zip(f.dk, pd.to_numeric(f.salary, errors="coerce").fillna(0))); gsis = dict(zip(f.dk, f.gsis_id.astype(str))); dkstatus = dict(zip(f.dk, f.status.astype(str))) if "status" in f.columns else {}
    with (run / "book.csv").open(newline="") as h: rows = list(csv.reader(h))
    assert tuple(rows[0]) == SLOTS, rows[0]; book = rows[1:]; n = len(book)
    c = bigquery.Client(project="nfl-predictions-503414")
    ids = sorted({g for g in gsis.values() if g and g != "None" and g != "nan"})
    inj = c.query("""SELECT gsis_id, report_status, practice_status, practice_primary_injury, date_modified FROM `nfl-predictions-503414.nfl_raw.injuries`
                     WHERE CAST(season AS INT64)=@s AND CAST(week AS INT64)=@w AND gsis_id IN UNNEST(@ids)""",
                  job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week), bigquery.ArrayQueryParameter("ids", "STRING", ids)])).result().to_dataframe()
    inj = inj.sort_values("date_modified").groupby("gsis_id").tail(1).set_index("gsis_id") if len(inj) else pd.DataFrame(columns=["report_status", "practice_status", "practice_primary_injury"]).set_index(pd.Index([], name="gsis_id"))
    pwi = c.query("""SELECT gsis_id, injury_status, practice_level, depth_rank, games_missed_l4 FROM `nfl-predictions-503414.nfl_features.player_week_inference`
                     WHERE season=@s AND week=@w AND gsis_id IN UNNEST(@ids)""",
                  job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week), bigquery.ArrayQueryParameter("ids", "STRING", ids)])).result().to_dataframe().drop_duplicates("gsis_id").set_index("gsis_id")
    # backup-QB rule (2026-09-19): a QB listed at depth >= 2 behind a healthy depth-1 QB scores ~0 unconditionally
    # (2022-25: depth-2 QBs 1.8 pts/week, depth-3 0.8) while the served law carries E[points | played]. Team starter status
    # comes from every QB on the slate's teams, not only the book's players.
    teams = sorted({t for t in team.values() if t and t != "None" and t != "nan"})
    qbs = c.query("""SELECT gsis_id, team, depth_rank, injury_status FROM `nfl-predictions-503414.nfl_features.player_week_inference`
                     WHERE season=@s AND week=@w AND position='QB' AND team IN UNNEST(@teams)""",
                  job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week), bigquery.ArrayQueryParameter("teams", "STRING", teams)])).result().to_dataframe()
    starter_status = {}
    qb_roles = {}
    if a.qb_flags:
        _fl = pd.read_csv(a.qb_flags)
        qb_roles = {int(d): (r, c) for d, r, c in zip(_fl.dk_player_id, _fl.role, _fl.team_class) if pd.notna(d)}
    for t, g in qbs[qbs.depth_rank == 1].groupby("team"):
        starter_status[t] = str(g.injury_status.iloc[0] or "").strip().lower()
    L = c.query("""SELECT DATE(pulled_at) AS d, player, market, outcome_name, AVG(point) AS point, AVG(price) AS price FROM `nfl-predictions-503414.nfl_raw.prop_lines`
                   WHERE season=@s AND week=@w GROUP BY d, player, market, outcome_name""",
                job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week)])).result().to_dataframe()
    days = sorted(L.d.unique()); vanished_norm, present_norm = set(), set()
    if len(days) >= 2:
        def implied(df):
            pts = Counter()
            for r in df.itertuples():
                if r.market == "player_anytime_td":
                    if str(r.outcome_name).lower().startswith("yes") or r.outcome_name == r.player: pts[r.player] += 6.0 * implied_prob(r.price)
                elif r.market in W and str(r.outcome_name).lower().startswith("over") and pd.notna(r.point): pts[r.player] += W[r.market] * float(r.point)
            return pts
        p0, p1 = implied(L[L.d == days[-2]]), implied(L[L.d == days[-1]])
        vanished_norm = {norm_name(p) for p, v in p0.items() if v >= 5.0 and p not in p1}; present_norm = {norm_name(p) for p in p1}
    # per-player flags
    flags, weight = defaultdict(list), defaultdict(float)
    for dk in set(v for row in book for v in row):
        w, lab = status_weight(dkstatus.get(dk))
        if lab: flags[dk].append(f"DK:{lab}"); weight[dk] = max(weight[dk], w)
        g = gsis.get(dk)
        if g in inj.index:
            w2, lab2 = status_weight(inj.loc[g, "report_status"])
            if lab2: flags[dk].append(f"report:{lab2}"); weight[dk] = max(weight[dk], w2)
            ps = str(inj.loc[g, "practice_status"] or "").lower(); pinj = str(inj.loc[g, "practice_primary_injury"] or "").lower()
            if "did not" in ps or "dnp" in ps:
                if "not injury related" in pinj or "rest" in pinj: flags[dk].append("practice:DNP-rest")
                else:
                    # a real-injury DNP without a designation: material only if the market is silent on him too;
                    # with props still posted the market expects him to play -> soft flag
                    nn_ = norm_name(name[dk]); silent = (len(days) >= 2 and nn_ not in present_norm)
                    flags[dk].append("practice:DNP(" + (pinj or "injury") + (", market silent)" if silent else ", props posted)")); weight[dk] += 2.0 if silent else 0.5
            elif "limited" in ps: flags[dk].append("practice:Limited"); weight[dk] += 0.5
        if g in pwi.index:
            w3, lab3 = status_weight(pwi.loc[g, "injury_status"])
            if lab3 and not any(x.endswith(lab3) for x in flags[dk]): flags[dk].append(f"features:{lab3}"); weight[dk] = max(weight[dk], w3)
            pl = pwi.loc[g, "practice_level"]
            if pd.notna(pl) and float(pl) < 1 and not any(x.startswith("practice:") for x in flags[dk]): flags[dk].append(f"practice_level:{float(pl):.1f}"); weight[dk] += 0.5
            dr = pwi.loc[g, "depth_rank"]
            if pd.notna(dr) and float(dr) >= 3 and pos.get(dk) in ("RB", "TE"): flags[dk].append(f"depth:{int(dr)}"); weight[dk] += 0.5
            if pos.get(dk) == "QB" and qb_roles:
                # v2.1 (lab review, finding 3): one shared classifier (qb_classify.py via qb_flags.py). Only a backup
                # behind a HEALTHY primary is unavailable (HARD); a backup behind a Questionable/Doubtful primary or on a
                # team without a depth-1 row is ambiguous (material +1.0, information); primaries carry no flag.
                role, cls = qb_roles.get(int(dk), (None, None))
                if role == "gated": flags[dk].append(f"backup_qb:behind-healthy-primary"); weight[dk] = HARD
                elif role == "ambiguous": flags[dk].append(f"backup_qb:ambiguous({cls})"); weight[dk] += 1.0
                elif role == "unknown" and pd.notna(dr) and float(dr) >= 2: flags[dk].append(f"backup_qb:unknown({cls})"); weight[dk] += 0.5
            elif pd.notna(dr) and float(dr) >= 2 and pos.get(dk) == "QB":
                st = starter_status.get(team.get(dk))
                if st is None: flags[dk].append(f"backup_qb:depth{int(dr)}:no-depth-1-on-file"); weight[dk] += 1.0
                elif st in ("out", "ir", "injured reserve", "pup", "nfi", "sus", "suspended"): flags[dk].append(f"backup_qb:depth{int(dr)}:starter-OUT")
                elif st in ("doubtful", "questionable"): flags[dk].append(f"backup_qb:depth{int(dr)}:starter-{st}"); weight[dk] += 1.0
                else: flags[dk].append(f"backup_qb:depth{int(dr)}:behind-healthy-starter"); weight[dk] = HARD
            gm = pwi.loc[g, "games_missed_l4"]
            if pd.notna(gm) and float(gm) >= 2: flags[dk].append(f"missed_l4:{int(gm)}"); weight[dk] += 0.5
        if sal.get(dk, 0) and sal[dk] < 2500 and pos.get(dk) != "DST": flags[dk].append("placeholder_salary"); weight[dk] = HARD
        if pos.get(dk) != "DST" and len(days) >= 2:
            nn = norm_name(name[dk])
            if nn in vanished_norm: flags[dk].append("market:VANISHED"); weight[dk] = HARD
            elif nn not in present_norm and sal.get(dk, 0) >= 5000: flags[dk].append("market:no_props"); weight[dk] += 1.0
    lineups = []
    for i, row in enumerate(book):
        risk = sum(weight[dk] for dk in row); hard = any(weight[dk] >= HARD for dk in row)
        lineups.append({"rank": i + 1, "risk": round(risk, 2), "hard": hard, "flags": {name[dk]: flags[dk] for dk in row if flags[dk]}})
    # tiers: hard (vetoed to the back) > material (risk >= threshold: Q/D, silent-market DNP, no props) > clean/soft (selector order kept)
    thr = a.material_threshold
    for lu in lineups: lu["material"] = (not lu["hard"]) and lu["risk"] >= thr
    order = sorted(range(n), key=lambda i: (lineups[i]["hard"], lineups[i]["material"], i))
    with (out / "book.csv").open("w", newline="") as h:
        wr = csv.writer(h); wr.writerow(SLOTS); [wr.writerow(book[i]) for i in order]
    shutil.copy(run / "frame.parquet", out / "frame.parquet"); shutil.copy(run / "receipt.json", out / "source_receipt.json")
    k = a.k; top_before = set(range(k)); top_after = set(order[:k]); demoted = sorted(top_before - top_after); promoted = sorted(top_after - top_before)
    rec = {"version": "vet-book-v2.1-backup-qb-classified", "source_run": str(run), "k": k, "vetted_at_utc": datetime.now(UTC).isoformat(), "prop_fetch_days": [str(d) for d in days[-2:]],
           "signals": {"dk_status_players": sum(1 for d in weight if any(x.startswith("DK:") for x in flags[d])), "injury_report_players": len(inj), "inference_players": len(pwi), "vanished_lines": len(vanished_norm)},
           "order_source_ranks": [i + 1 for i in order], "demoted_out_of_top_k": [i + 1 for i in demoted], "promoted_into_top_k": [i + 1 for i in promoted],
           "material_threshold": thr, "lineups": lineups, "player_flags": {name[d]: {"dk": d, "pos": pos[d], "team": team[d], "weight": weight[d], "flags": fl} for d, fl in flags.items()}}
    (out / "vetting.json").write_text(json.dumps(rec, indent=1) + "\n")
    lines = [f"# Vetting report — {run.name} (k={k}, {datetime.now(UTC):%Y-%m-%d %H:%MZ})", "",
             f"Players flagged: {len(flags)} of {len(weight)} in the book; hard flags: {sum(1 for d in weight if weight[d] >= HARD)}; prop fetch days compared: {rec['prop_fetch_days']}", "",
             f"Lineups demoted out of the top {k}: {rec['demoted_out_of_top_k']}", f"Lineups promoted into the top {k}: {rec['promoted_into_top_k']}", "", "## Flagged players", "", "| player | pos | team | weight | flags |", "|---|---|---|---:|---|"]
    for d, fl in sorted(flags.items(), key=lambda kv: -weight[kv[0]]): lines.append(f"| {name[d]} | {pos[d]} | {team[d]} | {weight[d]:.1f} | {', '.join(fl)} |")
    lines += ["", f"Tiers: hard flags vetoed to the back; material risk (>= {thr}) demoted behind every clean or soft-flagged lineup; soft flags are informational.", "",
              "## Lineups (vetted order)", "", "| vetted pos | source rank | risk | tier | flagged players |", "|---:|---:|---:|---|---|"]
    for p_, i in enumerate(order, 1):
        lu = lineups[i]; tier = "HARD" if lu["hard"] else ("material" if lu["material"] else ("soft" if lu["risk"] > 0 else ""))
        lines.append(f"| {p_} | {lu['rank']} | {lu['risk']} | {tier} | {'; '.join(k2 + ' (' + ', '.join(v) + ')' for k2, v in lu['flags'].items())} |")
    (out / "vetting_report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k2: v for k2, v in rec.items() if k2 not in ("lineups", "order_source_ranks", "player_flags")}, indent=1)); print("flagged players:", {name[d]: fl for d, fl in flags.items()}); print("book ->", out / "book.csv")

if __name__ == "__main__":
    main()
