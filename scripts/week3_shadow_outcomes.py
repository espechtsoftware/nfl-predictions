#!/usr/bin/env python3
"""Build the outcomes CSV for week3_shadow_reader.py from the canonical settled tables (production-owned).

This is the ONE step of the Week-3 shadow that reads realized scores, and it refuses to run unless (a) the operator's
release is confirmed on the command line and (b) every game represented by the run frame is final by the same rule the
authoritative B1 settlement uses (the game's latest play-by-play row reads "end game"). Sources mirror
scripts/run_b1_authoritative_settlement.py: skill players `nfl_features.player_week_actuals.dk_points` by gsis id;
defenses `nfl_features.team_defense_week.dst_dk_points` by team. A frame player with no actuals row after a final game
is written as 0.0 with source `absent_after_final` and counted in the receipt (DK scores an inactive player 0);
nothing is imputed for a game that is not final.

  PROD_PY scripts/week3_shadow_outcomes.py --run RUN_DIR --season 2026 --week 3 --out OUT_DIR --i-confirm-outcomes-released
          [--settlement-receipt PATH]
Writes OUT_DIR/outcomes.csv (id, actual_points, source, gsis_id, team, pos, game_id) and OUT_DIR/outcomes-receipt.json.
"""
import argparse, datetime as dt, hashlib, json, pathlib, sys
import pandas as pd

PROJECT = "nfl-predictions-503414"
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

SQL_SKILL = """SELECT CAST(gsis_id AS STRING) AS gsis_id, dk_points, has_stat_line
FROM `{P}.nfl_features.player_week_actuals` WHERE season = @season AND week = @week"""
SQL_DST = """SELECT UPPER(CAST(team AS STRING)) AS team, dst_dk_points FROM `{P}.nfl_features.team_defense_week`
WHERE season = @season AND week = @week"""
SQL_FINAL = """WITH latest_pbp AS (
  SELECT CAST(game_id AS STRING) AS game_id,
         ARRAY_AGG(STRUCT(play_id, `desc`) ORDER BY play_id DESC LIMIT 1)[OFFSET(0)] AS terminal
  FROM `{P}.nfl_raw.pbp` WHERE season = @season AND week = @week GROUP BY game_id)
SELECT CAST(s.game_id AS STRING) AS game_id, UPPER(CAST(s.home_team AS STRING)) AS home_team, UPPER(CAST(s.away_team AS STRING)) AS away_team,
       s.home_score, s.away_score,
       REGEXP_CONTAINS(TRIM(LOWER(COALESCE(p.terminal.`desc`, ''))), r'^end( of)? game$') AS is_final
FROM `{P}.nfl_raw.schedules` s LEFT JOIN latest_pbp p ON CAST(s.game_id AS STRING) = p.game_id
WHERE s.season = @season AND s.week = @week AND s.game_type = 'REG'"""


def bq_query(sql, season, week):
    from google.cloud import bigquery
    c = bigquery.Client(project=PROJECT)
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("season", "INT64", season), bigquery.ScalarQueryParameter("week", "INT64", week)])
    return c.query(sql.format(P=PROJECT), job_config=cfg).result().to_dataframe()


def build(frame: pd.DataFrame, skill: pd.DataFrame, dst: pd.DataFrame, final: pd.DataFrame):
    """Pure function: frame (id, gsis_id, pos, team, game_id) x settled tables -> (outcomes DataFrame, receipt dict).
    Raises RuntimeError if any represented game is not final."""
    fr = frame.copy(); fr["team"] = fr.team.astype(str).str.upper(); fr["game_id"] = fr.game_id.astype(str)
    games = sorted(set(fr.game_id)); fin = final.set_index(final.game_id.astype(str))
    not_final = [g for g in games if g not in fin.index or not bool(fin.loc[g, "is_final"])]
    if not_final:
        raise RuntimeError(f"{len(not_final)} represented game(s) not final: {not_final}")
    sk = skill.copy(); sk["gsis_id"] = sk.gsis_id.astype(str); sk = sk.drop_duplicates("gsis_id").set_index("gsis_id")
    ds = dst.copy(); ds["team"] = ds.team.astype(str).str.upper(); ds = ds.drop_duplicates("team").set_index("team")
    rows, counts = [], {"skill_row": 0, "dst_row": 0, "absent_after_final": 0, "dst_absent_after_final": 0}
    for r in fr.itertuples(index=False):
        if str(r.pos).upper() == "DST":
            if r.team in ds.index and pd.notna(ds.loc[r.team, "dst_dk_points"]):
                pts, src = float(ds.loc[r.team, "dst_dk_points"]), "team_defense_week.dst_dk_points"; counts["dst_row"] += 1
            else:
                pts, src = 0.0, "dst_absent_after_final"; counts["dst_absent_after_final"] += 1
        else:
            g = str(r.gsis_id)
            if g in sk.index and pd.notna(sk.loc[g, "dk_points"]):
                pts, src = float(sk.loc[g, "dk_points"]), "player_week_actuals.dk_points"; counts["skill_row"] += 1
            else:
                pts, src = 0.0, "absent_after_final"; counts["absent_after_final"] += 1
        rows.append({"id": str(r.id), "actual_points": pts, "source": src, "gsis_id": str(r.gsis_id), "team": r.team, "pos": r.pos, "game_id": r.game_id})
    out = pd.DataFrame(rows)
    receipt = {"games": {g: {"home": fin.loc[g, "home_team"], "away": fin.loc[g, "away_team"], "home_score": float(fin.loc[g, "home_score"]) if pd.notna(fin.loc[g, "home_score"]) else None,
                             "away_score": float(fin.loc[g, "away_score"]) if pd.notna(fin.loc[g, "away_score"]) else None, "is_final": True} for g in games},
               "counts": counts, "frame_rows": int(len(fr)), "outcome_rows": int(len(out))}
    return out, receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True); ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--i-confirm-outcomes-released", action="store_true"); ap.add_argument("--settlement-receipt", default=None)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if not a.i_confirm_outcomes_released:
        print("refusing: outcomes are read only after the operator's release; pass --i-confirm-outcomes-released", file=sys.stderr); sys.exit(2)
    run = pathlib.Path(a.run)
    frame = pd.read_parquet(run / "frame.parquet", columns=["id", "gsis_id", "pos", "team", "game_id"])
    skill, dst, final = (bq_query(s, a.season, a.week) for s in (SQL_SKILL, SQL_DST, SQL_FINAL))
    try:
        df, receipt = build(frame, skill, dst, final)
    except RuntimeError as e:
        (out / "OUTCOMES-NOT-FINAL").write_text(str(e) + "\n"); print(str(e), file=sys.stderr); sys.exit(3)
    df.to_csv(out / "outcomes.csv", index=False)
    receipt.update({"schema": "week3-shadow-outcomes/v1", "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "season": a.season, "week": a.week,
                    "run_dir": str(run), "frame_sha256": sha(run / "frame.parquet"), "release_confirmed_by_flag": True, "settlement_receipt": a.settlement_receipt,
                    "sources": ["nfl_features.player_week_actuals.dk_points", "nfl_features.team_defense_week.dst_dk_points", "nfl_raw.schedules + nfl_raw.pbp (end-game finality)"],
                    "query_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in (("skill", SQL_SKILL), ("dst", SQL_DST), ("final", SQL_FINAL))},
                    "outcomes_sha256": sha(out / "outcomes.csv"), "current_outcomes_read": True, "builder_sha256": sha(__file__)})
    (out / "outcomes-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"rows": receipt["outcome_rows"], "counts": receipt["counts"], "games": len(receipt["games"])}))


if __name__ == "__main__":
    main()
