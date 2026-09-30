"""2026 context rows for the live TabPFN ownership predictor (laptop request 2026-09-30 04:25, the operator's condition 1:
"fitted ... from the rows file plus 2026 Weeks 1-3"). One row per skill player (QB/RB/WR/TE, served mean_projection >= 1)
of each 2026 Sunday main slate W1-W3, with EXACTLY the columns and conventions of PREREG-L23's rows file
(nfl2 experiments/l23_build_rows.py @ 83da4955), so the live script can concatenate it after `rows.parquet`:

  season, week, id, gsis_id, name, pos, pos_code, salary, mean_projection, implied_team_total, game_total, spread,
  salary_delta_wow, value, own_l1, own_l3, linestar_own, target_own, is_eval, base_blend, base_lag

Sources (every input a past, settled week; nothing about Week 4):
  frames      each week's archived pre-lock T-70 frame (`--frame W=path`; the entered books' 15:50Z frame). The live
              frame's `spread` has the OPPOSITE sign to the history (live: implied = (total + spread)/2; history:
              implied = (total - spread)/2), so `spread` is rewritten in the historical convention as
              total - 2 * implied (or -spread where implied is missing), refusing if that disagrees with -spread by
              more than 1 point on more than 5% of rows.
  ownership   `raw.contest_ownership`, the week's largest Sunday Millionaire contest (the ownership_sets.py rule), rows
              one per roster SLOT, summed per player; keyed by ownership_sets.norm of the DK display name.
              target_own = that week's %, 0 when not listed (L23). own_l1 = week w-1's %, own_l3 = mean over the
              panel weeks among w-1..w-3, 0 when the week is in the panel and the player is not listed, NaN when no
              such week (L23's rule; W1 has none).
  linestar    LineStar's recorded projected ownership from its public archive endpoint (L15/L23's fetch and key: name +
              position, main slate, mode 0), cached OUTSIDE the repo in ~/.cache/linestar-2026. Not provably pre-lock
              (disclosed); where a pre-lock capture of the same period exists (`--prelock-linestar`), agreement is
              reported.
  is_eval = False; base_blend / base_lag = NaN.

The parquet holds third-party (LineStar) values and realized contest ownership: write it OUTSIDE the repo and push it
to the private bucket only. Prints counts and coverage only, never a predictor metric.

    python scripts/ownership_tabpfn_rows_2026.py --out ~/l23-panel/rows_2026_w1w3.parquet \
        --frame 1=~/week1-sunday/vetted-20260913t1550z-t70-e7255e9/frame.parquet \
        --frame 2=~/week2-sunday/vetted-20260920t1550z-d800-2dc116c/frame.parquet \
        --frame 3=~/week3-sunday/vetted-20260927t1550z-d800-65305f5/frame.parquet
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
POS = {p: i for i, p in enumerate(SKILL)}
FRAME_COLS = ("salary", "mean_projection", "implied_team_total", "game_total", "spread", "salary_delta_wow")
COLUMNS = ["season", "week", "id", "gsis_id", "name", "pos", "pos_code", "salary", "mean_projection",
           "implied_team_total", "game_total", "spread", "salary_delta_wow", "value", "own_l1", "own_l3",
           "linestar_own", "target_own", "is_eval", "base_blend", "base_lag"]
MILLIONAIRE_NAME_RE = r"Millionaire|^milly"          # ownership_sets.py
EXCLUDE_RE = r"\(Thu\)|MEGA|\$555"
LS_API = ("https://www.linestarapp.com/DesktopModules/DailyFantasyApi/API/Fantasy/GetSalariesV5"
          "?sport=1&site=1&periodId={pid}")
LS_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research"}
LS_CACHE = Path.home() / ".cache" / "linestar-2026"
SPREAD_TOL, SPREAD_MAX_BAD = 1.0, 0.05


def own_key(s: object) -> str:
    """ownership_sets.norm: the key the live lag features use."""
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower())
    return re.sub(r"[^a-z]", "", s)


def ls_norm(name: str) -> str:
    """l23_build_rows.norm (LineStar key, keeps spaces)."""
    s = str(name).lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    s = re.sub(r"[^a-z ]", "", s)
    return " ".join(s.split())


def linestar_slate(payload: dict) -> dict:
    """l23_build_rows.linestar_slate, verbatim."""
    own = payload.get("Ownership") or {}
    sc = json.loads(payload["SalaryContainerJson"])
    mains = [x for x in own.get("Slates", []) if x.get("SlateName") == "Main" and x.get("Mode") == 0]
    if not mains:
        return {}
    sid = mains[0]["Id"]
    proj = {o["SalaryId"]: o["Owned"] for o in (own.get("Projected") or {}).get(str(sid), [])}
    out = {}
    for r in sc["Salaries"]:
        if r["Id"] in proj:
            out.setdefault((ls_norm(r["Name"]), str(r["POS"]).upper()), float(proj[r["Id"]]))
    return out


def historical_spread(game_total: pd.Series, implied: pd.Series, live_spread: pd.Series) -> tuple[pd.Series, dict]:
    """The live frame's spread in the history's convention (favorite negative). Refuses on disagreement."""
    game_total, implied, live_spread = (pd.to_numeric(v, errors="coerce") for v in (game_total, implied, live_spread))
    derived = game_total - 2.0 * implied
    have = derived.notna() & live_spread.notna()
    bad = (derived[have] - (-live_spread[have])).abs() > SPREAD_TOL
    share = float(bad.mean()) if have.any() else 1.0
    if share > SPREAD_MAX_BAD:
        raise SystemExit(f"spread conversion refused: total - 2*implied disagrees with -spread on {share:.1%} of rows "
                         f"(> {SPREAD_MAX_BAD:.0%}); the frame's sign convention is not the one this script expects")
    out = derived.where(derived.notna(), -live_spread)
    return out, {"rows": int(len(out)), "derived": int(derived.notna().sum()), "from_minus_spread": int((derived.isna() & live_spread.notna()).sum()),
                 "disagree_gt_1pt": int(bad.sum()), "still_nan": int(out.isna().sum())}


def lag_columns(keys: list[str], week: int, by_week: dict[int, dict[str, float]]) -> tuple[object, object]:
    """L23's own_l1 / own_l3 for one slate: week w-1's %, and the mean over the panel weeks among w-1..w-3; 0 for a player
    not listed in a panel week; NaN (a scalar, as in L23) when no such week is in the panel."""
    prior = [week - k for k in (1, 2, 3) if (week - k) in by_week]
    l1 = by_week.get(week - 1)
    own_l1 = [l1.get(k, 0.0) for k in keys] if l1 is not None else np.nan
    own_l3 = [float(np.mean([by_week[p].get(k, 0.0) for p in prior])) for k in keys] if prior else np.nan
    return own_l1, own_l3


def millionaire_ownership(query_df, raw: str, season: int, weeks: list[int]) -> tuple[dict[int, dict[str, float]], dict]:
    """{week: {own_key: summed %}} from the week's largest Sunday Millionaire, plus the contest ids used."""
    wk = ", ".join(str(int(w)) for w in weeks)
    own = query_df(f"""
        WITH c AS (SELECT week, contest_id, ANY_VALUE(contest_name) nm, COUNT(*) n
                   FROM `{raw}.contest_ownership` WHERE season = {int(season)} AND week IN ({wk}) GROUP BY 1, 2),
        pick AS (SELECT week, ARRAY_AGG(contest_id ORDER BY n DESC LIMIT 1)[OFFSET(0)] cid FROM c
                 WHERE REGEXP_CONTAINS(nm, r"{MILLIONAIRE_NAME_RE}") AND NOT REGEXP_CONTAINS(nm, r"{EXCLUDE_RE}")
                 GROUP BY 1),
        slots AS (SELECT o.week, o.contest_id, o.display_name, o.roster_position, ANY_VALUE(o.pct_drafted) p
                  FROM `{raw}.contest_ownership` o JOIN pick ON o.week = pick.week AND o.contest_id = pick.cid
                  WHERE o.season = {int(season)} GROUP BY 1, 2, 3, 4)
        SELECT week, contest_id, display_name, roster_position, p FROM slots""")
    by_week, meta = {}, {}
    for w, g in own.groupby("week"):
        g = g.assign(key=g.display_name.map(own_key))
        by_week[int(w)] = g.groupby("key").p.sum().astype(float).to_dict()
        meta[int(w)] = {"contest_id": str(g.contest_id.iloc[0]), "sum_pct": round(float(g.p.sum()), 1),
                        "dst_slot_pct": round(float(g[g.roster_position.astype(str).str.upper() == "DST"].p.sum()), 1)}
    missing = sorted(set(weeks) - set(by_week))
    if missing:
        raise SystemExit(f"no Sunday Millionaire ownership for 2026 week(s) {missing}")
    return by_week, meta


def fetch_linestar(season: int, weeks: list[int], cache: Path = LS_CACHE) -> dict[int, Path]:
    import requests
    cache.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    p0 = s.get(LS_API.format(pid=0), headers=LS_HEADERS, timeout=30).json()
    pmap = {}
    for p in p0["Periods"]:
        m = re.match(r"^Week (\d+), (\d{4})$", p.get("Name", ""))
        if m and int(m.group(2)) == season and int(m.group(1)) in weeks:
            pmap[int(m.group(1))] = int(p["Id"])
    (cache / "pmap.json").write_text(json.dumps({str(v): [season, k] for k, v in pmap.items()}))
    missing = sorted(set(weeks) - set(pmap))
    if missing:
        raise SystemExit(f"LineStar has no period for {season} week(s) {missing}")
    out = {}
    for w, pid in sorted(pmap.items()):
        path = cache / f"p{pid}.json"
        if not path.exists():
            time.sleep(1.2)
            r = s.get(LS_API.format(pid=pid), headers=LS_HEADERS, timeout=30); r.raise_for_status()
            path.write_text(json.dumps(r.json()))
        out[w] = path
    return out


def build_week(fr: pd.DataFrame, season: int, week: int, by_week: dict, ls: dict) -> tuple[pd.DataFrame, dict]:
    fr = fr.reset_index(drop=True)
    for col, want in (("season", season), ("week", week)):
        got = set(pd.to_numeric(fr[col], errors="coerce").dropna().astype(int))
        if got != {want}:
            raise SystemExit(f"frame for week {week} carries {col} {sorted(got)}, expected {want}")
    sk = fr[fr.pos.astype(str).isin(SKILL)].copy()
    full_keys = sk.display_name.map(own_key)
    if full_keys.duplicated().any():
        raise SystemExit(f"week {week}: duplicate name keys among skill players {sorted(full_keys[full_keys.duplicated()])}")
    tgt = by_week[week]
    # coverage of the realized ownership by the frame's skill players (before the projection filter)
    matched = float(sum(tgt.get(k, 0.0) for k in full_keys))
    sk = sk[pd.to_numeric(sk.mean_projection, errors="coerce") >= 1.0].copy()
    ids = sk.id.astype(str).to_numpy()
    keys = sk.display_name.map(own_key).tolist()
    d = pd.DataFrame({"season": season, "week": week, "id": ids,
                      "gsis_id": sk.gsis_id.astype(str).to_numpy() if "gsis_id" in sk else ids,
                      "name": sk.name.astype(str).to_numpy(), "pos": sk.pos.astype(str).to_numpy()})
    d["pos_code"] = d.pos.map(POS)
    for c in FRAME_COLS:
        d[c] = pd.to_numeric(sk[c], errors="coerce").to_numpy() if c in sk else np.nan
    d["spread"], spread_meta = historical_spread(d.game_total, d.implied_team_total, d.spread)
    d["value"] = d.mean_projection / (d.salary / 1000.0)
    d["own_l1"], d["own_l3"] = lag_columns(keys, week, by_week)
    d["linestar_own"] = [ls.get((ls_norm(n), p), np.nan) for n, p in zip(d.name, d.pos)]
    d["target_own"] = [tgt.get(k, 0.0) for k in keys]
    d["is_eval"] = False
    d["base_blend"] = np.nan; d["base_lag"] = np.nan
    meta = {"rows": len(d), "skill_frame_rows": int(len(full_keys)), "spread": spread_meta,
            "target_pct_matched_by_frame_skill": round(matched, 1), "target_pct_in_rows": round(float(d.target_own.sum()), 1),
            "linestar_coverage": round(float(d.linestar_own.notna().mean()), 3),
            "own_l1_all_nan": bool(d.own_l1.isna().all()), "own_l3_all_nan": bool(d.own_l3.isna().all())}
    return d[COLUMNS], meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frame", action="append", required=True, help="W=path to that week's archived T-70 frame.parquet")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--prelock-linestar", action="append", default=[], help="W=path to a pre-lock LineStar capture (agreement check)")
    ap.add_argument("--min-target-coverage", type=float, default=0.97,
                    help="refuse unless the frame's skill players carry this share of the Millionaire's non-DST ownership")
    a = ap.parse_args()
    frames = {int(k): Path(v).expanduser() for k, v in (x.split("=", 1) for x in a.frame)}
    weeks = sorted(frames)
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    by_week, own_meta = millionaire_ownership(query_df, settings.raw, a.season, weeks)
    ls_paths = fetch_linestar(a.season, weeks)
    rows, report = [], {"frames": {}, "ownership": own_meta, "linestar_payloads": {}}
    for w in weeks:
        raw = frames[w].read_bytes()
        report["frames"][w] = {"path": str(frames[w]), "sha256": hashlib.sha256(raw).hexdigest()}
        ls_bytes = ls_paths[w].read_bytes()
        report["linestar_payloads"][w] = {"path": str(ls_paths[w]), "sha256": hashlib.sha256(ls_bytes).hexdigest()}
        ls = linestar_slate(json.loads(ls_bytes))
        d, meta = build_week(pd.read_parquet(frames[w]), a.season, w, by_week, ls)
        non_dst = own_meta[w]["sum_pct"] - own_meta[w]["dst_slot_pct"]
        cov = meta["target_pct_matched_by_frame_skill"] / non_dst if non_dst else 0.0
        meta["target_coverage_of_non_dst"] = round(cov, 4)
        if cov < a.min_target_coverage:
            raise SystemExit(f"week {w}: the frame's skill players carry only {cov:.1%} of the Millionaire's non-DST "
                             f"ownership (< {a.min_target_coverage:.0%}); name keys or the slate do not match")
        report[f"week{w}"] = meta
        rows.append(d)
    for spec in a.prelock_linestar:
        w, p = spec.split("=", 1)
        pre = linestar_slate(json.loads(Path(p).expanduser().read_text()))
        arch = linestar_slate(json.loads(ls_paths[int(w)].read_text()))
        common = sorted(set(pre) & set(arch))
        diffs = np.array([abs(pre[k] - arch[k]) for k in common]) if common else np.array([])
        report.setdefault("prelock_linestar_agreement", {})[w] = {
            "capture": p, "players_prelock": len(pre), "players_archive": len(arch), "common": len(common),
            "identical_share": round(float((diffs < 1e-9).mean()), 3) if len(diffs) else None,
            "median_abs_diff_pct": round(float(np.median(diffs)), 3) if len(diffs) else None}
    out = pd.concat(rows, ignore_index=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(a.out, index=False)
    report.update({"out": str(a.out), "rows": len(out), "sha256": hashlib.sha256(a.out.read_bytes()).hexdigest(),
                   "columns": list(out.columns)})
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
