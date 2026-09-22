"""Week-3 availability dry run: what each live mechanism WILL touch, from the exact frame project-slate builds.

Read-only. Calls run_projections.upcoming_slate_features (the loader project-slate uses) and the live
cascade_adjust functions under the live flags (Q_HAIRCUT=0.80, CASCADE_DOUBTFUL=1; QB gate refinements at
their defaults), then prints the three log lines Sunday's project-slate should emit. The cascade line
lists only the triggering ids (inherit lines need usage history; not simulated here). Run against the
deployed code: PYTHONPATH=<worktree at the deployed commit>/src.
    python week3_availability_dry_run.py --season 2026 --week 3
"""
import argparse, os
os.environ.setdefault("Q_HAIRCUT", "0.80"); os.environ.setdefault("CASCADE_DOUBTFUL", "1")
import pandas as pd
from nfl_dfs.inference import run_projections as RP, cascade_adjust as CA
ap = argparse.ArgumentParser(); ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
a = ap.parse_args()
f = RP.upcoming_slate_features(a.season, a.week)
name = f.get("display_name", f.gsis_id).astype(str)
pos = CA._col(f, "position", "dk_position").astype(str); team = CA._col(f, "team", "team_abbr").astype(str)
st = CA._col(f, "status").fillna("").astype(str); rep = CA._col(f, "injury_status").fillna("").astype(str)
print(f"frame: {len(f)} rows, {f.gsis_id.nunique()} players; draft groups {sorted(f['draft_group_id'].unique().tolist()) if 'draft_group_id' in f else 'n/a'}; "
      f"injury-report rows {int((rep != '').sum())}; depth_rank rows {int(f['depth_rank'].notna().sum()) if 'depth_rank' in f else 0}")
print("\nDesignations (DK status | report):")
d = pd.DataFrame({"name": name, "pos": pos, "team": team, "dk": st, "report": rep}).drop_duplicates()
print(d[(d.dk.str.upper().isin(["O", "OUT", "IR", "D", "DOUBTFUL", "Q", "QUESTIONABLE"])) | (d.report != "")]
      .sort_values(["dk", "pos", "team"]).to_string(index=False))
nm = dict(zip(f.gsis_id.astype(str), name))
out_ids = CA.find_out_players(f); bq = CA.find_backup_qbs(f); q = CA.find_questionable_players(f); h = CA.questionable_haircut(f)
print(f"\nzeroed + cascade sources (O/IR/report-Out, and non-QB Doubtful with CASCADE_DOUBTFUL=1): {len(out_ids)}")
print("   ", ", ".join(sorted(nm.get(i, i) for i in out_ids)))
print(f"backup-QB gate zeroes {len(bq)}:", ", ".join(sorted(f"{nm.get(i, i)} ({team[f.gsis_id.astype(str) == i].iloc[0]})" for i in bq)))
print(f"questionable haircut x{h:.3f} on {len(q)}:", ", ".join(sorted(nm.get(i, i) for i in q)))
qbt = f[pos.str.upper().eq("QB")]
no_d1 = sorted(t for t, g in qbt.groupby(team[qbt.index]) if not (pd.to_numeric(g.depth_rank, errors="coerce") == 1).any())
print("teams with no depth-1 QB row on the slate (gate promotes the shallowest present):", no_d1)
print("\nEXPECTED project-slate log lines:")
print(f"  backup-QB gate: zeroed {len(bq)}")
print(f"  questionable haircut: x{h:.3f} on {len(q)}")
print(f"  cascade: adjusted slate for {len(out_ids)} inactive(s): {', '.join(out_ids)}")
