#!/usr/bin/env python3
"""Study 61's weekly record (the prereg reports/2026-10-08-prereg-study61-r14-news-grading.md): the R14 fact log graded
on paper -- does FP's news predict what FP's projections miss?

Per week, from the ENTERED union dir (its frame.parquet and proj_source.csv, each checked by content against the
receipt) and the private fact log (~/private/r14-fact-log/<season>-wNN.jsonl):
  * the population: the T-70 frame's skill players (QB / RB / WR / TE) with an FP projection in proj_source.csv (`fp`,
    the projection the build used);
  * a record counts when it was logged before the frame's DraftKings pull (`pulled_at`), survives the spec's version
    rule (b) (per article, player, fact type: the records of the latest version that has any; ordered by
    published_date, then retrieved_at) and every counted `supersedes`, and joins a population player: the normalised
    name plus the aliased team, else the normalised name alone when exactly one population player has it;
  * a player's net direction n = the sign of the sum of his counted records' directions (+1 / -1 only);
  * r = DK points (nfl_features.player_week_actuals, by gsis id) - fp; r' = r - the mean r of his position that week;
  * Delta_w = mean r' (n = +1) - mean r' (n = -1); a week is valid with at least 10 players a side.
Looks at W8 and W10 over the valid weeks from W5: at least 4 valid weeks, else "too few valid weeks"; the two-sided 90%
t interval (each side a one-sided 95% bound, n - 1 df): lower > 0 "the articles carry information FP's projections had
not priced", upper < 0 "the articles point the wrong way", otherwise "no information shown". Advice; he decides.
Descriptive: by fact type, the primary without "other", the spec's priceable split, the sign rate, the direction-0
placebo, and the counts. Aggregates only: no quote, no article text and no player name is ever printed.

    python scripts/s61_r14_grade.py --weeks 5[,6,...] [--union 5=<dir>,...] [--log-dir <dir>] [--out <json>]
    python scripts/s61_r14_grade.py --census --weeks 5        (outcome-blind: no points are read)
The union dir defaults to moneygate weeks.json's entered_union, and any other dir is refused, except under --smoke
(mechanics only, labelled, never a record; --smoke-cutoff-utc replaces the frame's pull as the cut-off there).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

SEASON = 2026
SKILL = ("QB", "RB", "WR", "TE")
PROSPECTIVE_FROM, LOOKS, MIN_WEEKS, MIN_SIDE = 5, (8, 10), 4, 10
ONE_SIDED = 0.95                                   # each side of the two-sided 90% interval
LOG_DIR = Path.home() / "private" / "r14-fact-log"
TYPES = ("availability", "role_up", "role_down", "usage_quote", "matchup", "other")

# the log's free-text team -> the frame's team code (nflverse: LA = the Rams); "Los Angeles" / "New York" alone are
# ambiguous and map to nothing (the name-only join then applies)
_CODES = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
          "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"]
_NAMES = {
    "ARI": ("Arizona", "Cardinals"), "ATL": ("Atlanta", "Falcons"), "BAL": ("Baltimore", "Ravens"), "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"), "CHI": ("Chicago", "Bears"), "CIN": ("Cincinnati", "Bengals"), "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"), "DEN": ("Denver", "Broncos"), "DET": ("Detroit", "Lions"), "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"), "IND": ("Indianapolis", "Colts"), "JAX": ("Jacksonville", "Jaguars"), "KC": ("Kansas City", "Chiefs"),
    "LA": ("Los Angeles", "Rams"), "LAC": ("Los Angeles", "Chargers"), "LV": ("Las Vegas", "Raiders"), "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"), "NE": ("New England", "Patriots"), "NO": ("New Orleans", "Saints"), "NYG": ("New York", "Giants"),
    "NYJ": ("New York", "Jets"), "PHI": ("Philadelphia", "Eagles"), "PIT": ("Pittsburgh", "Steelers"), "SEA": ("Seattle", "Seahawks"),
    "SF": ("San Francisco", "49ers"), "TB": ("Tampa Bay", "Buccaneers"), "TEN": ("Tennessee", "Titans"), "WAS": ("Washington", "Commanders"),
}
_EXTRA = {"lar": "LA", "stl": "LA", "jac": "JAX", "gnb": "GB", "kan": "KC", "lvr": "LV", "oak": "LV", "nwe": "NE", "nor": "NO",
          "sfo": "SF", "tam": "TB", "wsh": "WAS", "sd": "LAC", "philly": "PHI", "niners": "SF", "bucs": "TB", "tampa": "TB",
          "la rams": "LA", "la chargers": "LAC", "ny giants": "NYG", "ny jets": "NYJ"}


def _tkey(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[.]", "", str(s))).strip().lower()


def team_aliases() -> dict[str, str]:
    a = {c.lower(): c for c in _CODES}
    for code, (city, nick) in _NAMES.items():
        a[_tkey(nick)] = code
        a[_tkey(f"{city} {nick}")] = code
        a.setdefault(_tkey(city), code)
    for amb in ("los angeles", "new york"):
        a.pop(amb, None)
    a.update(_EXTRA)
    return a


TEAM_ALIAS = team_aliases()


def team_code(written) -> str | None:
    if written is None or (isinstance(written, float) and math.isnan(written)):
        return None
    return TEAM_ALIAS.get(_tkey(written))


_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def norm_name(s) -> str:
    """Case, punctuation and the suffixes Jr / Sr / II-V removed; hyphens become spaces."""
    t = str(s).lower().replace("’", "").replace("'", "").replace(".", "").replace("-", " ").replace(",", " ")
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", t)).strip()


def when(ts) -> datetime:
    """An aware UTC datetime from the log's and BigQuery's forms ('...Z', '+00:00', or '+00' without minutes)."""
    t = str(ts).strip().replace(" ", "T", 1).replace("Z", "+00:00")
    if len(t) >= 3 and t[-3] in "+-" and t[-2:].isdigit() and ":" not in t[-3:]:
        t += ":00"
    d = datetime.fromisoformat(t)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_union(d: Path) -> dict:
    """The population, the cut-off and FP's last update, every file checked by content against the union receipt."""
    d = Path(d)
    un = json.loads((d / "receipt.json").read_text())["config"]["union"]
    want_fr = (un.get("input_sha256") or {}).get("t70_frame")
    if not want_fr or sha256(d / "frame.parquet") != want_fr:
        raise SystemExit(f"STUDY 61 REFUSED: {d}/frame.parquet is not the receipt's T-70 frame")
    ps = un.get("proj_source") or {}
    if not ps and not (d / "proj_source.csv").exists():
        # amendment 2: the T-70 fell back to OUR projections (no FP projection was used), so the week is NOT VALID for the
        # study -- recorded, never a refusal of the other weeks. An FP file the receipt names but which is missing or
        # different is still refused just below (integrity).
        return {"no_fp": True, "reason": "no FP projection: the T-70 build fell back to our projections"}
    if not ps.get("sha256") or not (d / "proj_source.csv").is_file() or sha256(d / "proj_source.csv") != ps["sha256"]:
        raise SystemExit(f"STUDY 61 REFUSED: {d}/proj_source.csv is missing or not the receipt's projection file")
    side = json.loads((d / "proj_source.csv.json").read_text()) if (d / "proj_source.csv.json").is_file() else {}
    fp_lu = side.get("fp_last_updated") or (side.get("capture") or {}).get("fp_last_updated")
    fr = pd.read_parquet(d / "frame.parquet")
    if fr["pulled_at"].nunique() != 1:
        raise SystemExit(f"STUDY 61 REFUSED: {d}/frame.parquet holds {fr['pulled_at'].nunique()} DK pulls")
    proj = pd.read_csv(d / "proj_source.csv", dtype={"id": str})
    sk = fr[fr["pos"].astype(str).isin(SKILL)][["id", "gsis_id", "dk_player_id", "display_name", "pos", "team"]].copy()
    sk["id"] = sk["id"].astype(str)
    sk["dk_player_id"] = sk["dk_player_id"].astype(str).str.removesuffix(".0")
    pop = sk.merge(proj[["id", "fp"]], on="id", how="inner")
    pop["fp"] = pd.to_numeric(pop["fp"], errors="coerce")
    pop = pop[pop["fp"].notna()].copy()
    pop["nname"] = pop["display_name"].map(norm_name)
    team_opp = {}                        # amendment 3: each team's opponent (team_change's mapping; the primary never reads it)
    if "opp" in fr.columns:
        opp = fr.groupby(fr["team"].astype(str))["opp"].agg(lambda s: str(s.iloc[0]) if s.nunique() == 1 else None)
        team_opp = {t: o for t, o in opp.items() if o is not None}
    return {"pop": pop.reset_index(drop=True), "cutoff": when(fr["pulled_at"].iloc[0]),
            "fp_last_updated": when(fp_lu) if fp_lu else None, "skill_on_frame": int(len(sk)), "team_opp": team_opp}


def load_log(week: int, log_dir: Path) -> list[dict]:
    f = Path(log_dir) / f"{SEASON}-w{week:02d}.jsonl"
    if not f.is_file():
        raise SystemExit(f"STUDY 61 REFUSED: no fact log {f}")
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()]


def counted_records(recs: list[dict], cutoff: datetime) -> tuple[list[dict], dict]:
    """The spec's rules: logged before the cut-off; not superseded by a counted record; the latest version per key."""
    c = Counter(logged=len(recs))
    early = [r for r in recs if when(r["logged_utc"]) < cutoff]
    c["late"] = len(recs) - len(early)
    sup = {r["supersedes"] for r in early if r.get("supersedes")}
    alive = [r for r in early if r.get("record_id") not in sup]
    c["superseded"] = len(early) - len(alive)
    vkey = lambda r: (when(r["published_date"]), when(r["retrieved_at"]))
    by = defaultdict(list)
    for r in alive:
        by[(r["article_id"], norm_name(r["player"]), r["fact_type"])].append(r)
    out = []
    for rs in by.values():
        top = max(vkey(r) for r in rs)
        keep = [r for r in rs if vkey(r) == top]
        out += keep
        c["older_version"] += len(rs) - len(keep)
    c["multi_version_keys"] = sum(1 for rs in by.values() if len({vkey(r) for r in rs}) > 1)
    c["kept"] = len(out)
    return out, dict(c)


def join(recs: list[dict], pop: pd.DataFrame) -> tuple[list[tuple[dict, int]], dict]:
    """(record, population row) pairs: the name plus the aliased team, else the name alone when it is unique."""
    by_name = defaultdict(list)
    for i, n in enumerate(pop["nname"]):
        by_name[n].append(i)
    out, c, unknown = [], Counter(), Counter()
    for r in recs:
        cand = by_name.get(norm_name(r["player"]), [])
        code = team_code(r.get("team"))
        if code is None and r.get("team") not in (None, "") and str(r.get("team")).strip().upper() != "FA":
            unknown[str(r.get("team")).strip()] += 1          # a team string the alias table does not know (counted, shown)
        hit = [i for i in cand if pop.at[i, "team"] == code] if code else []
        j = None
        if len(hit) == 1:
            j = hit[0]; c["name_team"] += 1
        elif len(cand) == 1:
            j = cand[0]; c["name_only"] += 1
        else:
            c["ambiguous" if len(cand) > 1 else "not_on_frame"] += 1
        if j is not None:
            if any(r.get(k) and str(r[k]).removesuffix(".0") != str(pop.at[j, k]) for k in ("gsis_id", "dk_player_id")):
                c["id_disagrees"] += 1                      # the spec's later id join must agree with this one
            else:
                out.append((r, j))
    c["joined"] = len(out)
    if unknown:
        c["team_unknown"] = dict(unknown)
    return out, dict(c)


# amendment 3 (the R14 spec amendment of 2026-10-07, before W6's extraction): team_change records are UNIT records, kept
# out of the player join, the groups and the direction-0 placebo; their derived players form a descriptive line only
UNIT_TARGETS = {"pass_defense": ("opp", ("QB", "WR", "TE"), -1), "pass_rush": ("opp", ("QB", "WR", "TE"), -1),
                "run_defense": ("opp", ("RB",), -1), "offensive_line": ("own", ("QB", "RB"), 1),
                "receiving_corps": None, "backfield": None}


def derive_team_change(recs: list[dict], pop: pd.DataFrame, team_opp: dict[str, str]) -> tuple[list[tuple[dict, int, int]], dict]:
    """(record, population row, derived direction) for the spec's mapping: pass_defense / pass_rush -> the opponent's QB,
    WR and TE at -unit_effect; run_defense -> the opponent's RBs at -unit_effect; offensive_line -> the team's own QB and
    RBs at +unit_effect; receiving_corps / backfield -> counted only. A team not on the Main slate derives nothing."""
    out, c = [], Counter(records=len(recs))
    for r in recs:
        if not team_opp:                                     # the frame carried no opponent column: nothing can map
            c["no_opponent_map"] += 1; continue
        unit, eff = r.get("unit"), r.get("unit_effect")
        if unit not in UNIT_TARGETS:
            c["unit_unknown"] += 1; continue
        c[f"unit {unit}"] += 1
        code = team_code(r.get("team"))
        if code is None:
            c["team_unknown"] += 1; continue
        if code not in team_opp:
            c["team_not_on_slate"] += 1; continue
        tgt = UNIT_TARGETS[unit]
        if tgt is None:
            c["count_only"] += 1; continue
        side, poss, sign = tgt
        team = team_opp[code] if side == "opp" else code
        d = sign * int(eff) if eff in (-1, 0, 1) and not isinstance(eff, bool) else 0
        rows = pop.index[(pop["team"].astype(str) == team) & pop["pos"].isin(poss)].tolist()
        out += [(r, int(i), d) for i in rows]
        c["derived_pairs"] += len(rows)
    return out, dict(c)


def player_groups(pairs: list[tuple[dict, int]], exclude_types: tuple = ()) -> dict[int, int]:
    """Per population row: n = the sign of the sum of its counted +1 / -1 directions (0 = balanced)."""
    s, seen = defaultdict(int), set()
    for r, i in pairs:
        if r["fact_type"] in exclude_types:
            continue
        seen.add(i)
        if r["direction"] in (-1, 1):
            s[i] += int(r["direction"])
    return {i: (int(np.sign(s[i])) if i in s else 0) for i in seen}


def residuals(pop: pd.DataFrame, act: pd.DataFrame) -> pd.Series:
    """r' per population row with actuals: (DK points - fp) minus that position's mean that week."""
    m = pop.merge(act[["gsis_id", "dk_points"]], on="gsis_id", how="left")
    r = m["dk_points"] - m["fp"]
    rp = r - r.groupby(m["pos"]).transform("mean")
    return pd.Series(rp.to_numpy(), index=pop.index)


def delta(groups: dict[int, int], rp: pd.Series) -> dict:
    plus = [rp[i] for i, n in groups.items() if n == 1 and pd.notna(rp[i])]
    minus = [rp[i] for i, n in groups.items() if n == -1 and pd.notna(rp[i])]
    d = {"n_plus": len(plus), "n_minus": len(minus)}
    if plus and minus:
        d["delta"] = float(np.mean(plus) - np.mean(minus))
    d["valid"] = len(plus) >= MIN_SIDE and len(minus) >= MIN_SIDE
    return d


def load_actuals(season: int, week: int, gsis_ids: list[str]) -> tuple[pd.DataFrame, str]:
    from google.cloud import bigquery
    from nfl_dfs.config import settings
    c = bigquery.Client(project=settings.project)
    q = f"""SELECT gsis_id, dk_points FROM `{settings.features}.player_week_actuals`
            WHERE season = @s AND week = @w AND gsis_id IN UNNEST(@ids)"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", season),
                                                    bigquery.ScalarQueryParameter("w", "INT64", week),
                                                    bigquery.ArrayQueryParameter("ids", "STRING", sorted(set(gsis_ids)))])
    act = c.query(q, job_config=cfg).to_dataframe()
    if act["gsis_id"].duplicated().any():
        raise SystemExit(f"STUDY 61 REFUSED: W{week} actuals repeat a gsis id")
    body = "\n".join(f"{g},{p:.4f}" for g, p in sorted(zip(act.gsis_id, act.dk_points.astype(float))))
    return act, hashlib.sha256(body.encode()).hexdigest()


def week_descriptive(pairs, groups, rp, fp_lu, derived=()) -> dict:
    """By fact type (mean of direction x r' over records), the priceable split, the sign rate, the direction-0 placebo,
    and (amendment 3) team_change's derived players: the mean of derived direction x r', by unit."""
    by_type = {}
    for t in TYPES:
        v = [r["direction"] * rp[i] for r, i in pairs if r["fact_type"] == t and r["direction"] in (-1, 1) and pd.notna(rp[i])]
        by_type[t] = {"records": len(v), "mean_signed_r": float(np.mean(v)) if v else None}
    split = {}
    if fp_lu is not None:
        for name, test in (("priceable", lambda r: when(r["published_date"]) < fp_lu), ("after_fp_update", lambda r: when(r["published_date"]) >= fp_lu)):
            v = [r["direction"] * rp[i] for r, i in pairs if test(r) and r["direction"] in (-1, 1) and pd.notna(rp[i])]
            split[name] = {"records": len(v), "mean_signed_r": float(np.mean(v)) if v else None}
    nz = [(n, rp[i]) for i, n in groups.items() if n != 0 and pd.notna(rp[i])]
    sign_rate = float(np.mean([np.sign(x) == n for n, x in nz])) if nz else None
    dirs = defaultdict(set)
    for r, i in pairs:
        dirs[i].add(r["direction"])
    zero_only = [rp[i] for i, ds in dirs.items() if ds == {0} and pd.notna(rp[i])]
    tc = [(r["unit"], d * rp[i]) for r, i, d in derived if d != 0 and pd.notna(rp[i])]
    return {"by_type": by_type, "priceable_split": split, "sign_rate": sign_rate,
            "zero_only": {"players": len(zero_only), "mean_r": float(np.mean(zero_only)) if zero_only else None},
            "team_change_derived": {"pairs": len(tc), "mean_signed_r": float(np.mean([v for _, v in tc])) if tc else None,
                                    "by_unit": dict(Counter(u for u, _ in tc))}}


def read_look(values: list[float]) -> dict:
    n = len(values)
    if n < MIN_WEEKS:
        return {"n": n, "reading": f"too few valid weeks ({n} < {MIN_WEEKS})"}
    v = np.asarray(values, float); mean = float(v.mean())
    half = float(student_t.ppf(ONE_SIDED, n - 1) * v.std(ddof=1) / math.sqrt(n))
    out = {"n": n, "mean": mean, "lo": mean - half, "hi": mean + half}
    out["reading"] = ("the articles carry information FP's projections had not priced" if mean - half > 0 else
                      "the articles point the wrong way" if mean + half < 0 else "no information shown")
    return out


def looks_due(weeks: list[int]) -> list[int]:
    return [L for L in LOOKS if L <= max(weeks)]


def parse_map(text: str) -> dict[int, Path]:
    out = {}
    for part in text.split(","):
        w, _, d = part.partition("=")
        out[int(w)] = Path(d).expanduser()
    return out


def week_census(week: int, U: dict, recs: list[dict]) -> dict:
    kept, c1 = counted_records(recs, U["cutoff"])
    unit_recs = [r for r in kept if r["fact_type"] == "team_change"]          # amendment 3: unit records, apart
    pairs, c2 = join([r for r in kept if r["fact_type"] != "team_change"], U["pop"])
    derived, c3 = derive_team_change(unit_recs, U["pop"], U.get("team_opp") or {})
    g = player_groups(pairs)
    by_type = dict(Counter((r["fact_type"], r["direction"]) for r, _ in pairs))
    return {"records": c1, "join": c2, "joined_by_type_direction": {f"{t} {d:+d}": n for (t, d), n in sorted(by_type.items())},
            "players": {"plus": sum(1 for n in g.values() if n == 1), "minus": sum(1 for n in g.values() if n == -1),
                        "balanced": sum(1 for i, n in g.items() if n == 0 and any(r["direction"] for r, j in pairs if j == i)),
                        "zero_only": sum(1 for i in g if all(r["direction"] == 0 for r, j in pairs if j == i))},
            "population": int(len(U["pop"])), "skill_on_frame": U["skill_on_frame"], "cutoff_utc": U["cutoff"].isoformat(),
            "team_change": c3, "pairs": pairs, "groups": g, "derived": derived}


MONEYGATE_WEEKS = Path.home() / "moneygate" / "weeks.json"


def entered_union(week: int, weeks_json: Path = MONEYGATE_WEEKS) -> Path | None:
    try:
        u = json.loads(Path(weeks_json).read_text())["weeks"][str(week)].get("entered_union")
    except (OSError, KeyError, ValueError):
        return None
    return Path(u) if u else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", required=True)
    ap.add_argument("--union", default=None, help="W=<dir>,...; default: moneygate weeks.json's entered_union")
    ap.add_argument("--log-dir", type=Path, default=LOG_DIR); ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--census", action="store_true", help="outcome-blind: the records, the frame and the projection file only")
    ap.add_argument("--smoke", action="store_true", help="mechanics only: any union dir, labelled SMOKE, never a record")
    ap.add_argument("--smoke-cutoff-utc", default=None, help="with --smoke: the cut-off in place of the frame's pull")
    a = ap.parse_args(argv)
    if a.smoke_cutoff_utc and not a.smoke:
        raise SystemExit("STUDY 61 REFUSED: --smoke-cutoff-utc is for --smoke only")
    weeks = [int(x) for x in a.weeks.split(",")]
    given = parse_map(a.union) if a.union else {}
    unions = {}
    for w in weeks:
        ent = entered_union(w)
        d = given.get(w) or ent
        if d is None:
            raise SystemExit(f"STUDY 61 REFUSED: no union dir for W{w} (none given, none entered in weeks.json)")
        if not a.smoke and (ent is None or Path(d).resolve() != ent.resolve()):
            raise SystemExit(f"STUDY 61 REFUSED: W{w}'s union {d} is not weeks.json's entered_union ({ent}); --smoke for mechanics")
        unions[w] = Path(d)
    print(f"STUDY 61 RECORD  sha256 {sha256(Path(__file__))}" + ("   SMOKE (mechanics only; never a record)" if a.smoke else ""))
    out = {"weeks": weeks, "smoke": bool(a.smoke), "per_week": {}, "looks": {}}
    for w in weeks:
        U = load_union(unions[w])
        if U.get("no_fp"):                                 # amendment 2: a fallback week is recorded as not valid
            out["per_week"][w] = {"valid": False, "reason": U["reason"]}
            print(f"  W{w}: NOT VALID -- {U['reason']} (recorded; the other weeks stand)")
            continue
        recs = load_log(w, a.log_dir)
        if a.smoke_cutoff_utc:
            U["cutoff"] = when(a.smoke_cutoff_utc)
        cen = week_census(w, U, recs)
        pw = {k: v for k, v in cen.items() if k not in ("pairs", "groups", "derived")}     # counts only: no record text
        print(f"  W{w} CENSUS: population {cen['population']} of {cen['skill_on_frame']} frame skill players; cut-off "
              f"{cen['cutoff_utc']}; records {cen['records']}; join {cen['join']}; players {cen['players']}"
              + (f"; team_change {cen['team_change']}" if cen["team_change"].get("records") else ""))
        if not a.census:
            act, act_sha = load_actuals(SEASON, w, U["pop"]["gsis_id"].astype(str).tolist())
            rp = residuals(U["pop"], act)
            d = delta(cen["groups"], rp)
            d_no_other = delta(player_groups(cen["pairs"], exclude_types=("other",)), rp)
            desc = week_descriptive(cen["pairs"], cen["groups"], rp, U["fp_last_updated"], derived=cen["derived"])
            pw.update({"actuals_sha256": act_sha, "population_with_actuals": int(rp.notna().sum()), "primary": d,
                       "primary_without_other": d_no_other, "descriptive": desc})
            tag = "PROSPECTIVE" if w >= PROSPECTIVE_FROM else "BEFORE THE STUDY"
            print(f"  W{w} {tag}: Delta {d.get('delta', float('nan')):+.3f} DK points ({d['n_plus']} +1 vs {d['n_minus']} -1 players; "
                  f"{'valid' if d['valid'] else 'NOT VALID (< ' + str(MIN_SIDE) + ' a side)'}); without other "
                  f"{d_no_other.get('delta', float('nan')):+.3f}; sign rate {desc['sign_rate']}; direction-0 placebo {desc['zero_only']}")
            print("      by type (mean direction x r'): " + ", ".join(f"{t} {v['mean_signed_r']:+.2f} ({v['records']})" for t, v in desc["by_type"].items() if v["records"])
                  + " | priceable split: " + ", ".join(f"{k} {v['mean_signed_r']:+.2f} ({v['records']})" for k, v in desc["priceable_split"].items() if v["records"]))
            tcd = desc["team_change_derived"]
            if tcd["pairs"]:
                print(f"      team_change derived players (descriptive only, never the primary): mean derived direction x r' "
                      f"{tcd['mean_signed_r']:+.2f} over {tcd['pairs']} pairs, by unit {tcd['by_unit']}")
        out["per_week"][w] = pw
    if not a.census:
        ok = lambda w: bool((out["per_week"][w].get("primary") or {}).get("valid"))
        vals = [out["per_week"][w]["primary"]["delta"] for w in weeks if w >= PROSPECTIVE_FROM and ok(w)]
        print(f"STUDY 61 (prereg 2026-10-08): prospective from W{PROSPECTIVE_FROM}; looks at W{', W'.join(map(str, LOOKS))}; "
              f"the two-sided 90% t interval (each side a one-sided 95% bound); at least {MIN_SIDE} players a side, {MIN_WEEKS} valid weeks")
        for L in looks_due(weeks):
            upto = [out["per_week"][w]["primary"]["delta"] for w in weeks if PROSPECTIVE_FROM <= w <= L and ok(w)]
            r = read_look(upto); out["looks"][L] = r
            print(f"  LOOK W{L}: n {r['n']}" + (f", mean {r['mean']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] (two-sided 90%)" if "mean" in r else "")
                  + f" -> {r['reading']}")
        if not looks_due(weeks):
            print(f"  no look yet (valid prospective weeks so far: {len(vals)})")
    if a.out:
        a.out.write_text(json.dumps(out, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
