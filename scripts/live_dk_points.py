#!/usr/bin/env python3
"""Live DraftKings points from ESPN's public box scores (laptop, 2026-09-28; late swap and late-inactive tooling).

No DraftKings access and no login: ESPN's public site API (scoreboard + per-game summary). Skill players are scored with
production's own DK Classic scoring (nfl_dfs.models.scoring.dk_points). A team DST is scored from its box score:
sacks 1, interceptions 2, opponent fumbles lost 2, defensive / return TDs 6, and the points-allowed tier on the
opponent's current score. Defensive / return TDs and safeties come from the game's scoring plays (the box-score
categories double-count some interception-return TDs); two-point conversions are credited from the scoring-play text
("A Pass to B for Two-Point Conversion", "A Run for Two-Point Conversion"). Blocked kicks are not in ESPN's feed
(declared; rare).

    python scripts/live_dk_points.py --date 20260928 [--out snapshot.json] [--validate-week 3]

--validate-week compares finished games against the week's official DK points (contest_ownership fpts) and prints the
match rate; run it on a settled week before trusting a live snapshot.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.models.scoring import StatLine, dk_points  # noqa: E402

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
PA_TIERS = ((0, 10.0), (6, 7.0), (13, 4.0), (20, 1.0), (27, 0.0), (34, -1.0))   # points allowed <= bound -> points


def get(url: str, tries: int = 3) -> dict:
    """urllib's own default User-Agent (ESPN refuses browser-like and custom agents with 403; tested 2026-09-28)."""
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))
    raise RuntimeError("unreachable")


def pa_points(pa: float) -> float:
    for bound, pts in PA_TIERS:
        if pa <= bound:
            return pts
    return -4.0


def _num(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


RETURN_TD = re.compile(r"(Interception|Fumble|Punt|Kickoff|Blocked \w+|Missed Field Goal) Return Touchdown", re.I)
TWO_PASS = re.compile(r"\(([^()]+?) Pass to ([^()]+?) for Two-Point Conversion\)")
TWO_RUN = re.compile(r"\(([^()]+?) Run for Two-Point Conversion\)")


def scoring_extras(summary: dict) -> tuple[dict, dict, dict]:
    """(defensive/return TDs by team, safeties by team, two-point conversions by player name) from the scoring plays."""
    tds, safeties, two = {}, {}, {}
    for sp in summary.get("scoringPlays", []):
        team = sp.get("team", {}).get("abbreviation"); ty = sp.get("type", {}).get("text", ""); txt = sp.get("text", "")
        if RETURN_TD.search(ty) or RETURN_TD.search(txt):
            tds[team] = tds.get(team, 0) + 1
        if "safety" in ty.lower():
            safeties[team] = safeties.get(team, 0) + 1
        for m in TWO_PASS.finditer(txt):
            for who in m.groups():
                two[who.strip()] = two.get(who.strip(), 0) + 1
        for m in TWO_RUN.finditer(txt):
            two[m.group(1).strip()] = two.get(m.group(1).strip(), 0) + 1
    return tds, safeties, two


def game_points(summary: dict, pa_excludes_return_tds: bool = False) -> tuple[list[dict], dict]:
    """(player rows, game state) for one ESPN game summary."""
    comp = summary["header"]["competitions"][0]
    score = {c["team"]["abbreviation"]: _num(c.get("score")) for c in comp["competitors"]}
    st = comp["status"]
    state = {"teams": sorted(score), "status": st["type"]["name"], "period": st.get("period"), "clock": st.get("displayClock")}
    lines: dict[tuple[str, str], dict] = {}
    team_def: dict[str, dict] = {}
    for team in summary.get("boxscore", {}).get("players", []):
        abbr = team["team"]["abbreviation"]
        td = team_def.setdefault(abbr, {"sacks": 0.0, "ints": 0.0, "def_td": 0.0, "fum_lost": 0.0})
        for cat in team.get("statistics", []):
            lab = cat.get("labels", [])
            for a in cat.get("athletes", []):
                name = a["athlete"]["displayName"]; v = dict(zip(lab, a.get("stats", [])))
                row = lines.setdefault((abbr, name), {"team": abbr, "name": name, "espn_id": a["athlete"].get("id"),
                                                     "pass_yards": 0.0, "pass_tds": 0.0, "interceptions": 0.0,
                                                     "rush_yards": 0.0, "rush_tds": 0.0, "receptions": 0.0,
                                                     "rec_yards": 0.0, "rec_tds": 0.0, "fumbles_lost": 0.0,
                                                     "return_tds": 0.0})
                n = cat["name"]
                if n == "passing":
                    row["pass_yards"] += _num(v.get("YDS")); row["pass_tds"] += _num(v.get("TD")); row["interceptions"] += _num(v.get("INT"))
                elif n == "rushing":
                    row["rush_yards"] += _num(v.get("YDS")); row["rush_tds"] += _num(v.get("TD"))
                elif n == "receiving":
                    row["receptions"] += _num(v.get("REC")); row["rec_yards"] += _num(v.get("YDS")); row["rec_tds"] += _num(v.get("TD"))
                elif n == "fumbles":
                    row["fumbles_lost"] += _num(v.get("LOST")); td["fum_lost"] += _num(v.get("LOST"))
                elif n in ("kickReturns", "puntReturns"):
                    row["return_tds"] += _num(v.get("TD"))
                elif n == "defensive":
                    td["sacks"] += _num(v.get("SACKS"))
                elif n == "interceptions":
                    td["ints"] += _num(v.get("INT"))
    ret_tds, safeties, two = scoring_extras(summary)
    rows = []
    for (_abbr, _name), r in lines.items():
        s = StatLine(**{k: r[k] for k in ("pass_yards", "pass_tds", "interceptions", "rush_yards", "rush_tds", "receptions",
                                          "rec_yards", "rec_tds", "fumbles_lost", "return_tds")},
                     two_point_conversions=float(two.get(r["name"], 0)))
        rows.append({"team": r["team"], "name": r["name"], "espn_id": r["espn_id"], "dk_points": round(float(dk_points(s)), 2)})
    for abbr, td in team_def.items():
        opp = next((t for t in score if t != abbr), None)
        opp_fum = team_def.get(opp, {}).get("fum_lost", 0.0) if opp else 0.0
        pa = score.get(opp, 0.0) - (6.0 * ret_tds.get(opp, 0) if pa_excludes_return_tds else 0.0)
        pts = (td["sacks"] + 2 * td["ints"] + 2 * opp_fum + 6 * ret_tds.get(abbr, 0) + 2 * safeties.get(abbr, 0)
               + pa_points(pa))
        rows.append({"team": abbr, "name": f"{abbr} DST", "espn_id": None, "dk_points": round(pts, 2), "dst": True})
    return rows, state


def snapshot(date: str, pa_excludes_return_tds: bool = False) -> dict:
    sb = get(f"{BASE}/scoreboard?dates={date}")
    games, players = [], []
    for e in sb.get("events", []):
        rows, state = game_points(get(f"{BASE}/summary?event={e['id']}"), pa_excludes_return_tds)
        state["event_id"] = e["id"]; state["name"] = e.get("shortName"); state["start"] = e.get("date")
        games.append(state); players += [{**r, "event_id": e["id"]} for r in rows]
    return {"taken_utc": datetime.now(timezone.utc).isoformat(), "date": date, "games": games, "players": players}


def norm(s: str) -> str:
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s.lower())
    return re.sub(r"[^a-z]", "", s)


def validate(snap: dict, season: int, week: int) -> None:
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    fp = query_df(f"SELECT display_name, MAX(fpts) f FROM `{settings.raw}.contest_ownership` WHERE season={season} AND week={week} GROUP BY 1")
    official = {norm(n): float(f) for n, f in zip(fp.display_name.astype(str), fp.f.astype(float))}
    final = {g["event_id"] for g in snap["games"] if g["status"] == "STATUS_FINAL"}
    skill = [p for p in snap["players"] if p["event_id"] in final and not p.get("dst")]
    dst = [p for p in snap["players"] if p["event_id"] in final and p.get("dst")]
    matched = [(p, official[norm(p["name"])]) for p in skill if norm(p["name"]) in official]
    exact = sum(abs(p["dk_points"] - f) < 0.05 for p, f in matched)
    print(f"skill players in final games {len(skill)}; matched to official {len(matched)}; exact (within 0.05) {exact} "
          f"({exact / max(len(matched), 1):.1%})")
    bad = sorted(((abs(p["dk_points"] - f), p["name"], p["dk_points"], f) for p, f in matched if abs(p["dk_points"] - f) >= 0.05), reverse=True)
    for d, n, ours, off in bad[:8]:
        print(f"  off by {d:.2f}: {n} ours {ours} official {off}")
    team_dst = {}
    for n, f in zip(fp.display_name.astype(str), fp.f.astype(float)):
        team_dst[norm(n)] = float(f)
    print("DST (ours vs official, by team name in contest_ownership where it matches):")
    for p in dst:
        print(f"  {p['name']}: {p['dk_points']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True, help="YYYYMMDD (US date of the games)")
    ap.add_argument("--out", type=Path); ap.add_argument("--validate-week", type=int); ap.add_argument("--season", type=int, default=2026)
    a = ap.parse_args()
    snap = snapshot(a.date)
    print(f"{len(snap['games'])} games; " + ", ".join(f"{g['name']} {g['status'].replace('STATUS_', '')} Q{g['period']} {g['clock']}" for g in snap["games"]))
    if a.out:
        a.out.write_text(json.dumps(snap))
        print(f"wrote {a.out} ({len(snap['players'])} player rows)")
    if a.validate_week:
        validate(snap, a.season, a.validate_week)


if __name__ == "__main__":
    main()
