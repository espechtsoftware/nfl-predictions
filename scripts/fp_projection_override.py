#!/usr/bin/env python3
"""Fantasy Points' projections as the build's projection source (operator 2026-10-05: "we should just use fantasy points
unless we've seen that our projections or the blend have beat them"). Writes the override file union_reselect.py reads
with --proj-source: for every T-70 frame player FP projects on the slate, FP's DraftKings fantasy points.

    python scripts/fp_projection_override.py --frame <T-70 run>/frame.parquet --season 2026 --week 5 \\
        --before 2026-10-11T15:50:00Z [--inactives-utc 2026-10-11T15:30:00Z] --out proj_fp-<tag>.csv

The capture: nfl_raw.fantasy_points_dfs_projections, operator DraftKings, the week's MAIN slate (slate_name 'Main'), the
NEWEST capture retrieved BEFORE --before (the build's start). The join is EXACT: FP's slate_player_id is DraftKings'
draftable id (the frame's dk_draftable_id). Gates (reviewer 2026-10-05), each REFUSES (exit 2, "FP PROJECTIONS REFUSED"):
  (a) coverage: >= 95% of the frame's skill players we project >= 5, and every DST;
  (b) salary: every matched row's FP salary equals the frame's (a wrong slate or draft group);
  (c) disagreement: Pearson r between FP and ours over the matched skill players either side projects >= 3 must be
      >= 0.7 (a stale, partial or wrong-week capture); the 15 largest |FP - ours| are printed;
  (d) freshness: a capture older than --inactives-utc (10:30 CT on Sunday) prints a CAPITALS banner (not a refusal).
Players FP does not project keep our projection (counted). FP gives a mean only: the simulations stay ours (disclosed).
Output: the CSV (id, dk_draftable_id, name, pos, ours, fp) and <out>.json (the capture, the frame's sha256, the gates).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
MIN_COVERAGE, MIN_R = 0.95, 0.7


class Refused(RuntimeError):
    pass


def _key(v) -> str:
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def build(fr: pd.DataFrame, fp: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Pure: the override rows and the gate record from the frame and ONE capture's rows. Raises Refused."""
    fr = fr.drop_duplicates("id").copy()
    fr["dk"] = fr["dk_draftable_id"].map(_key)
    fr["ours"] = pd.to_numeric(fr["mean_projection"], errors="coerce").fillna(0.0)
    fp = fp.copy(); fp["dk"] = fp["slate_player_id"].map(_key)
    if fp["dk"].duplicated().any():
        raise Refused(f"the capture repeats {int(fp['dk'].duplicated().sum())} draftable ids")
    m = fr.merge(fp[["dk", "fantasy_points", "salary"]].rename(columns={"salary": "fp_salary"}), on="dk", how="inner")
    skill5 = fr[fr.pos.isin(SKILL) & (fr.ours >= 5)]
    cov = float(skill5["dk"].isin(set(fp["dk"])).mean()) if len(skill5) else 0.0
    dst = fr[fr.pos == "DST"]; dst_missing = dst.loc[~dst["dk"].isin(set(fp["dk"])), "name"].tolist()
    if cov < MIN_COVERAGE:
        miss = skill5.loc[~skill5["dk"].isin(set(fp["dk"])), "name"].tolist()[:8]
        raise Refused(f"coverage {cov:.3f} of our skill players projected >= 5 < {MIN_COVERAGE} (missing e.g. {miss})")
    if dst_missing:
        raise Refused(f"DSTs without an FP projection: {dst_missing}")
    sal_bad = m[pd.to_numeric(m.salary, errors="coerce").round() != pd.to_numeric(m.fp_salary, errors="coerce").round()]
    if len(sal_bad):
        raise Refused(f"{len(sal_bad)} matched players' FP salary differs from the frame's (wrong slate?): "
                      f"{sal_bad[['name', 'salary', 'fp_salary']].head(5).to_dict('records')}")
    m["fp"] = pd.to_numeric(m.fantasy_points, errors="coerce").fillna(0.0)
    elig = m[m.pos.isin(SKILL) & ((m.ours >= 3) | (m.fp >= 3))]
    r = float(np.corrcoef(elig.ours, elig.fp)[0, 1]) if len(elig) > 2 else float("nan")
    top = elig.assign(diff=elig.fp - elig.ours).reindex((elig.fp - elig.ours).abs().sort_values(ascending=False).index).head(15)
    if not (r >= MIN_R):
        raise Refused(f"FP and ours disagree: Pearson r {r:.3f} < {MIN_R} over {len(elig)} players (stale or wrong capture?)")
    out = m[["id", "dk", "name", "pos", "ours", "fp"]].rename(columns={"dk": "dk_draftable_id"}).sort_values("id").reset_index(drop=True)
    gates = {"coverage_skill_ge5": round(cov, 4), "dst_covered": int(len(dst)), "matched": int(len(m)),
             "frame_players": int(len(fr)), "kept_ours": int(len(fr) - len(m)), "pearson_r": round(r, 4),
             "eligible_for_r": int(len(elig)),
             "top15_abs_diff": [{"name": n, "pos": p, "ours": round(float(o), 2), "fp": round(float(f), 2)}
                                for n, p, o, f in zip(top.name, top.pos, top.ours, top.fp)]}
    return out, gates


def load_capture(season: int, week: int, before: str) -> tuple[pd.DataFrame, dict]:
    from google.cloud import bigquery
    from nfl_dfs.config import settings
    c = bigquery.Client(project=settings.project)
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", season),
                                                    bigquery.ScalarQueryParameter("w", "INT64", week),
                                                    bigquery.ScalarQueryParameter("b", "TIMESTAMP", before)])
    fp = c.query(f"""SELECT slate_id, slate_name, slate_player_id, name, position, salary, fantasy_points, retrieved_at, source_sha256
        FROM `{settings.raw}.fantasy_points_dfs_projections`
        WHERE season = @s AND week = @w AND operator = 'DraftKings' AND slate_name = 'Main' AND retrieved_at < @b
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""", job_config=cfg).to_dataframe()
    if fp.empty:
        raise Refused(f"no FP DraftKings Main-slate capture for {season} W{week} before {before}")
    if fp.slate_id.nunique() != 1:
        raise Refused(f"the newest capture holds {fp.slate_id.nunique()} Main slates")
    meta = {"retrieved_at": pd.Timestamp(fp.retrieved_at.iloc[0]).isoformat(), "slate_id": str(fp.slate_id.iloc[0]),
            "source_sha256": str(fp.source_sha256.iloc[0]), "rows": int(len(fp))}
    return fp, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True); ap.add_argument("--before", required=True)
    ap.add_argument("--inactives-utc", default=None); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        fr = pd.read_parquet(a.frame)
        fp, cap = load_capture(a.season, a.week, a.before)
        out, gates = build(fr, fp)
    except Refused as e:
        print(f"FP PROJECTIONS REFUSED: {e}", file=sys.stderr)
        return 2
    stale = bool(a.inactives_utc) and pd.Timestamp(cap["retrieved_at"]) < pd.Timestamp(a.inactives_utc)
    if stale:
        print("!!! FP PROJECTIONS ARE FROM BEFORE THE 10:30 CT INACTIVES "
              f"(capture {cap['retrieved_at']}); DK OUT/IR players are still removed by the build", file=sys.stderr)
    out.to_csv(a.out, index=False)
    meta = {"capture": cap, "frame": str(a.frame), "frame_sha256": hashlib.sha256(Path(a.frame).read_bytes()).hexdigest(),
            "before": a.before, "inactives_utc": a.inactives_utc, "before_inactives": stale, "gates": gates,
            "csv_sha256": hashlib.sha256(a.out.read_bytes()).hexdigest(),
            "note": "FP gives a mean only: the build's simulations (tail-sleeve P(line), vetting) stay ours",
            "written_utc": datetime.now(timezone.utc).isoformat()}
    Path(str(a.out) + ".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"FP PROJECTIONS: capture {cap['retrieved_at']} (slate {cap['slate_id']}); matched {gates['matched']} of "
          f"{gates['frame_players']} frame players (coverage {gates['coverage_skill_ge5']}, DSTs {gates['dst_covered']}); "
          f"r(FP, ours) {gates['pearson_r']}; kept ours for {gates['kept_ours']} -> {a.out}")
    for t in gates["top15_abs_diff"]:
        print(f"   {t['name']:28s} {t['pos']:3s} ours {t['ours']:6.2f}  FP {t['fp']:6.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
