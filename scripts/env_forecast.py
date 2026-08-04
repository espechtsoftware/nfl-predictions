"""Weekly LLM game-environment forecasts (research round 11, built
2026-08-03 for September live use — historical backtests of fuzzy
questions are contaminated by the model's knowledge of outcomes, so
this validates LIVE: log forecasts weekly, grade after the slate).

ForecastBench-style multi-stage pipeline per game:
  1. context: schedule, Vegas total/spread, key injury designations
  2. sub-questions (shootout? script lean? pace?), each forecast with
     probability + reasoning
  3. a critique pass reviews the reasoning and issues final probs
Output: JSON per game {shootout_p, run_lean_p, pace_note} written to
stdout and reports/env_forecasts/<season>-w<week>.json — consumed as
WATCHLIST context first; sim scenario-weight integration only after a
few graded live weeks show calibration.

Usage: python scripts/env_forecast.py --season 2026 --week 1
Needs ANTHROPIC_API_KEY.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, "src")

import anthropic

from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

MODEL = "claude-sonnet-5"


def slate_context(season: int, week: int) -> list[dict]:
    games = query_df(f"""
      SELECT game_id, home_team, away_team, total_line, spread_line
      FROM `{settings.raw}.schedules`
      WHERE season={season} AND week={week}""")
    inj = query_df(f"""
      SELECT team, full_name, position, report_status
      FROM `{settings.raw}.injuries`
      WHERE season={season} AND week={week}
        AND report_status IN ('Out', 'Doubtful', 'Questionable')""")
    out = []
    for g in games.itertuples():
        gi = inj[inj.team.isin([g.home_team, g.away_team])]
        out.append({
            "game_id": g.game_id, "home": g.home_team, "away": g.away_team,
            "total": g.total_line, "spread": g.spread_line,
            "injuries": [f"{r.team} {r.full_name} ({r.position}) "
                         f"{r.report_status}" for r in gi.itertuples()]})
    return out


def forecast_game(client: anthropic.Anthropic, g: dict) -> dict:
    ask = (f"{g['away']} @ {g['home']}, Vegas total {g['total']}, spread "
           f"{g['spread']}. Injury report: {'; '.join(g['injuries']) or 'clean'}.")
    stage1 = client.messages.create(
        model=MODEL, max_tokens=1500, thinking={"type": "disabled"},
        system="You are an NFL analyst. Decompose, then forecast each "
               "sub-question with a probability. Reply in prose then a "
               "JSON line.",
        messages=[{"role": "user", "content":
            f"{ask}\nForecast: (a) P(shootout: both teams 24+ points), "
            f"(b) P(game script leans run-heavy for either team by Q3), "
            f"(c) expected pace vs league average. End with JSON "
            f'{{"shootout_p": x, "run_lean_p": y, "pace": "fast|avg|slow"}}.'}])
    draft = next(b.text for b in stage1.content if b.type == "text")
    stage2 = client.messages.create(
        model=MODEL, max_tokens=800, thinking={"type": "disabled"},
        system="You are a forecast reviewer. Identify overconfidence or "
               "missed considerations, then output the corrected final "
               "JSON only.",
        messages=[{"role": "user", "content":
            f"Game: {ask}\nAnalyst draft:\n{draft}\nReturn final JSON "
            f'{{"shootout_p": x, "run_lean_p": y, "pace": "...", '
            f'"note": "one line"}}.'}])
    txt = next(b.text for b in stage2.content if b.type == "text")
    try:
        j = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception:
        j = {"error": "parse", "raw": txt[:200]}
    return {"game_id": g["game_id"], "matchup": f"{g['away']}@{g['home']}",
            **j}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()
    client = anthropic.Anthropic()
    results = [forecast_game(client, g)
               for g in slate_context(args.season, args.week)]
    outdir = pathlib.Path("reports/env_forecasts")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{args.season}-w{args.week}.json"
    path.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    print(f"\nwrote {path} — grade after the slate: shootout = both teams "
          f"24+; run_lean = either team's Q3+ run rate > 55%.")


if __name__ == "__main__":
    main()
