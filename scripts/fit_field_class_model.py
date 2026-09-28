#!/usr/bin/env python3
"""Fit the field-class model (operator decision 2026-09-28, 5435c539; review 5ac250a6 §4) on the settled Millionaire fields.

A shape-only logistic model of "this entry finished in the top 1%" (and a second one for "top 100"): features are the
entry's shape plus our pre-lock projected sum as a within-week field percentile; no ownership, so it is computable
before lock. Written as JSON (scaler means/scales, coefficients, intercept) so the lab scores pools with numpy alone;
the file's sha256 is printed and written beside it. Refit every Monday on all settled weeks.

    python scripts/fit_field_class_model.py --weeks 1:193028206:151307:2026-09-13T17:00:00Z,2:195648007:153427:2026-09-20T17:00:00Z,3:195905122:153769:2026-09-27T17:00:00Z \
        --out ~/week4-sunday/class_model_w4.json

--weeks: WEEK:MILLIONAIRE_CONTEST_ID:DRAFT_GROUP:LOCK_UTC per settled week (explicit; nothing is inferred). The lock bounds
the projection snapshot used for the projected sum (the latest player_projections row generated before it).
Also prints leave-one-week-out lifts (fit on the other weeks, score the held-out field) as the file's receipt.

PRE-LOCK PERCENTILE MAP (condition 1a). The model's proj_pct is an entry's projected-sum percentile within its week's
field, and a live build has no field. The file therefore carries `proj_ratio_quantiles`: the pooled distribution, over
the --map-weeks, of (entry projected sum / that week's salary-legal optimum by served projection, DK rules only). A live
build solves its own week's optimum from the same projections and reads proj_pct = F(proj_sum / optimum). Measured
2026-09-28: the ratio's quantiles are nearly identical in Weeks 1 and 3 (p50 0.884 / 0.885, p90 0.925 / 0.929,
p99 0.952 / 0.959); Week 2 (the backup-QB projection defect) sits lower (p50 0.835) and is excluded from the map.
(A field sampled from the Saturday sets' predicted ownership could not be filled under the $50k cap; not used.)
Read-only against BigQuery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SHAPE = ["proj_pct", "proj_pct2", "stack", "bring_back", "max_game", "qb_sal", "te_sal", "rb_sal", "sal_left",
         "flex_te", "flex_rb", "qb_game_total"]
TARGETS = {"top1": lambda d: d["rank"] <= 0.01 * d.n, "top100": lambda d: d["rank"] <= 100}


def parse_weeks(spec: str) -> list[dict]:
    out = []
    for part in spec.split(","):
        w, cid, dg, lock = part.split(":", 3)
        out.append({"week": int(w), "cid": cid, "dg": int(dg), "lock": lock.replace("Z", "")})
    return out


def field_sql(raw: str, pred: str, season: int, weeks: list[dict]) -> str:
    grp = " UNION ALL ".join(f"SELECT {w['week']} AS week, {w['dg']} AS dg, '{w['cid']}' AS cid, TIMESTAMP('{w['lock']}') AS lk"
                             for w in weeks)
    return f"""
WITH grp AS ({grp}),
sal AS (SELECT g.week, s.display_name, ANY_VALUE(s.team_abbr) team, ANY_VALUE(s.position) pos, ANY_VALUE(s.salary) salary
        FROM `{raw}.dk_salaries` s JOIN grp g ON s.draft_group_id = g.dg AND s.season = {season} GROUP BY 1, 2),
sch AS (SELECT week, home_team t, away_team o, total_line tl FROM `{raw}.schedules` WHERE season = {season}
        UNION ALL SELECT week, away_team, home_team, total_line FROM `{raw}.schedules` WHERE season = {season}),
gpj AS (SELECT p.week, MAX(p.generated_at) ga FROM `{pred}.player_projections` p JOIN grp USING (week)
        WHERE p.season = {season} AND p.generated_at < grp.lk GROUP BY 1),
pj AS (SELECT p.week, p.display_name, ANY_VALUE(p.proj_points) proj FROM `{pred}.player_projections` p
       JOIN gpj ON p.week = gpj.week AND p.generated_at = gpj.ga WHERE p.season = {season} GROUP BY 1, 2),
e AS (SELECT e.week, e.entry_id, e.rank, e.lineup_slots_json, COUNT(*) OVER (PARTITION BY e.week) n
      FROM `{raw}.contest_entries` e JOIN grp g ON e.contest_id = g.cid AND e.week = g.week
      WHERE e.season = {season} AND e.n_players = 9
      QUALIFY ROW_NUMBER() OVER (PARTITION BY e.week, e.entry_id ORDER BY e.imported_at DESC) = 1),
x AS (SELECT e.week, e.entry_id, e.rank, e.n, JSON_VALUE(it, '$.slot') slot, sal.team,
        IF(sal.pos IN ('D', 'DST'), 'DST', sal.pos) pos, sal.salary, sch.o opp, LEAST(sal.team, sch.o) game, sch.tl, pj.proj
      FROM e, UNNEST(JSON_QUERY_ARRAY(e.lineup_slots_json)) it
      LEFT JOIN sal ON sal.week = e.week AND sal.display_name = JSON_VALUE(it, '$.player')
      LEFT JOIN sch ON sch.week = e.week AND sch.t = REPLACE(sal.team, 'LAR', 'LA')
      LEFT JOIN pj ON pj.week = e.week AND pj.display_name = JSON_VALUE(it, '$.player')),
q AS (SELECT week, entry_id, ANY_VALUE(IF(slot = 'QB', team, NULL)) qt, ANY_VALUE(IF(slot = 'QB', opp, NULL)) qo,
             ANY_VALUE(IF(slot = 'QB', tl, NULL)) qtl FROM x GROUP BY 1, 2),
gm AS (SELECT week, entry_id, MAX(c) max_game FROM (SELECT week, entry_id, game, COUNT(*) c FROM x GROUP BY 1, 2, 3) GROUP BY 1, 2)
SELECT x.week, x.entry_id, ANY_VALUE(x.rank) rank, ANY_VALUE(x.n) n, SUM(x.proj) proj_sum,
       COUNTIF(x.salary IS NULL) unmatched, COUNTIF(x.proj IS NULL AND x.pos != 'DST') proj_missing,
       MAX(IF(slot = 'QB', salary, NULL)) qb_sal, MAX(IF(x.pos = 'TE', salary, NULL)) te_sal,
       SUM(IF(x.pos = 'RB', salary, 0)) rb_sal, 50000 - SUM(salary) sal_left,
       COUNTIF(slot != 'QB' AND x.team = q.qt AND x.pos IN ('WR', 'TE')) stack,
       COUNTIF(x.team = q.qo AND x.pos IN ('RB', 'WR', 'TE')) bring_back,
       CAST(COUNTIF(x.pos = 'TE') >= 2 AS INT64) flex_te, CAST(COUNTIF(x.pos = 'RB') >= 3 AS INT64) flex_rb,
       ANY_VALUE(q.qtl) qb_game_total, ANY_VALUE(gm.max_game) max_game
FROM x JOIN q USING (week, entry_id) JOIN gm USING (week, entry_id) GROUP BY 1, 2"""


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df[(df.unmatched == 0)].copy()
    df["proj_sum"] = df.proj_sum.astype(float).fillna(0.0)
    df["proj_pct"] = df.groupby("week").proj_sum.rank(pct=True, method="average")
    df["proj_pct2"] = df.proj_pct ** 2
    for c in SHAPE:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["qb_game_total"] = df.qb_game_total.fillna(df.qb_game_total.median())
    return df.dropna(subset=SHAPE)


def optimum_sql(raw: str, pred: str, season: int, weeks: list[dict]) -> str:
    grp = " UNION ALL ".join(f"SELECT {w['week']} AS week, {w['dg']} AS dg, TIMESTAMP('{w['lock']}') AS lk" for w in weeks)
    return f"""
WITH grp AS ({grp}),
g AS (SELECT p.week, MAX(p.generated_at) ga FROM `{pred}.player_projections` p JOIN grp USING (week)
      WHERE p.season = {season} AND p.generated_at < grp.lk GROUP BY 1),
sl AS (SELECT g.week, s.display_name, ANY_VALUE(s.salary) salary, ANY_VALUE(IF(s.position IN ('D', 'DST'), 'DST', s.position)) pos
       FROM `{raw}.dk_salaries` s JOIN grp g ON s.draft_group_id = g.dg AND s.season = {season} GROUP BY 1, 2)
SELECT sl.week, sl.display_name, sl.salary, sl.pos, MAX(p.proj_points) proj FROM sl
JOIN `{pred}.player_projections` p ON p.display_name = sl.display_name AND p.season = {season} AND p.week = sl.week
JOIN g ON g.week = p.week AND g.ga = p.generated_at GROUP BY 1, 2, 3, 4"""


def salary_legal_optimum(proj: np.ndarray, salary: np.ndarray, pos: np.ndarray) -> float:
    """Max projected sum of a DK Classic lineup (positions, $50k cap; no house rules)."""
    import pulp
    n = len(proj); x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    m = pulp.LpProblem("opt", pulp.LpMaximize); m += pulp.lpSum(float(proj[i]) * x[i] for i in range(n))
    m += pulp.lpSum(x) == 9; m += pulp.lpSum(float(salary[i]) * x[i] for i in range(n)) <= 50_000
    P = lambda p: [i for i in range(n) if pos[i] == p]
    m += pulp.lpSum(x[i] for i in P("QB")) == 1; m += pulp.lpSum(x[i] for i in P("DST")) == 1
    for p, lo, hi in (("RB", 2, 3), ("WR", 3, 4), ("TE", 1, 2)):
        m += pulp.lpSum(x[i] for i in P(p)) >= lo; m += pulp.lpSum(x[i] for i in P(p)) <= hi
    m.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[m.status] != "Optimal":
        raise RuntimeError(f"optimum solve status {pulp.LpStatus[m.status]}")
    return float(sum(proj[i] for i in range(n) if x[i].value() > 0.5))


def fit(df: pd.DataFrame, target: str) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    X = df[SHAPE].to_numpy(float); y = TARGETS[target](df).to_numpy()
    sc = StandardScaler().fit(X); lr = LogisticRegression(max_iter=3000).fit(sc.transform(X), y)
    return {"target": target, "features": SHAPE, "scaler_mean": sc.mean_.tolist(), "scaler_scale": sc.scale_.tolist(),
            "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0]), "n_rows": int(len(df)), "positives": int(y.sum())}


def score(model: dict, X: np.ndarray) -> np.ndarray:
    z = (X - np.array(model["scaler_mean"])) / np.array(model["scaler_scale"])
    return z @ np.array(model["coef"]) + model["intercept"]


def lift(model: dict, te: pd.DataFrame, target: str, q: float) -> float:
    s = score(model, te[SHAPE].to_numpy(float)); y = TARGETS[target](te).to_numpy()
    top = s >= np.quantile(s, 1 - q)
    return float(y[top].mean() / max(y.mean(), 1e-12))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", required=True); ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--map-weeks", required=True, help="comma list of settled weeks whose fields form the pre-lock "
                                                        "percentile map (exclude defect weeks, e.g. 2)")
    a = ap.parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    weeks = parse_weeks(a.weeks)
    raw = query_df(field_sql(settings.raw, settings.predictions, a.season, weeks))
    df = prepare(raw)
    dropped = len(raw) - len(df)
    print(f"entries {len(raw)} over weeks {sorted(df.week.unique().tolist())}; dropped {dropped} (unmatched players / missing features)")
    receipt = {"leave_one_week_out": []}
    if df.week.nunique() >= 2:
        for tw in sorted(df.week.unique()):
            tr, te = df[df.week != tw], df[df.week == tw]
            for t in TARGETS:
                m = fit(tr, t)
                r = {"test_week": int(tw), "target": t, **{f"lift_top{int(q * 100)}pct": round(lift(m, te, t, q), 3) for q in (0.01, 0.05, 0.10)}}
                receipt["leave_one_week_out"].append(r); print("  walk-forward", r)
    models = {t: fit(df, t) for t in TARGETS}
    map_weeks = sorted(int(w) for w in a.map_weeks.split(","))
    if not set(map_weeks) <= set(df.week.unique()):
        raise SystemExit(f"--map-weeks {map_weeks} must be fitted weeks")
    opt_frame = query_df(optimum_sql(settings.raw, settings.predictions, a.season, [w for w in weeks if w["week"] in map_weeks]))
    optima = {int(w): salary_legal_optimum(g.proj.to_numpy(float), g.salary.to_numpy(float), g.pos.astype(str).to_numpy())
              for w, g in opt_frame.groupby("week")}
    ratios = np.concatenate([df.loc[df.week == w, "proj_sum"].to_numpy(float) / optima[w] for w in map_weeks])
    qs = np.quantile(ratios, np.linspace(0, 1, 2001))
    for w in map_weeks:
        r = df.loc[df.week == w, "proj_sum"].to_numpy(float) / optima[w]
        print(f"  map week {w}: optimum {optima[w]:.2f}; ratio p50 {np.median(r):.3f} p90 {np.percentile(r, 90):.3f} p99 {np.percentile(r, 99):.3f}")
    doc = {"kind": "field_class_model_v1", "season": a.season, "weeks": weeks, "fitted_utc": datetime.now(timezone.utc).isoformat(),
           "proj_pct_definition": "percentile of the entry's projected sum (latest pre-lock player_projections) within its week's field",
           "prelock_map": {"definition": "proj_pct = F(proj_sum / the week's salary-legal optimum by served projection, DK rules only)",
                           "map_weeks": map_weeks, "optima": optima, "proj_ratio_quantiles": [round(float(v), 6) for v in qs]},
           "models": models, "receipt": receipt}
    body = json.dumps(doc, indent=1, sort_keys=True).encode()
    a.out.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    a.out.with_suffix(a.out.suffix + ".sha256").write_text(f"{sha}  {a.out.name}\n")
    print(f"wrote {a.out} sha256 {sha}")
    for t, m in models.items():
        print(f"  {t}: " + ", ".join(f"{f} {c:+.2f}" for f, c in zip(m["features"], m["coef"])))


if __name__ == "__main__":
    main()
