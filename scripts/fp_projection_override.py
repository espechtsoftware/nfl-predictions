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
  (d) freshness, by FP's OWN update time (the capture's MAX(last_updated); the outside review 10-07, H2), not our capture
      time. FP's numbers last updated before the --inactives-utc (10:30 CT Sunday) print a CAPITALS banner and are USED
      (the operator 10-07: "FP anyway, label it honestly"; the W4 test that adopted FP used FP's 08:58 CT numbers). With
      --require-after-inactives (the T-70 build only) it REFUSES only numbers last updated before Sunday MORNING
      (--content-floor-utc, default 06:00 CT on the inactives' date), and the build falls back to OUR post-inactives
      projections through its existing FP-failure path.
Every run prints one line "FP CAPTURE TIMING: captured <ts> AFTER|BEFORE the 10:30 CT inactives; FP last updated <ts>
AFTER|BEFORE them" for the upload sheet.
Players FP does not project keep our projection (counted), and so do players FP lists with NO projection (a null
fantasyPoints; the outside review 10-07, M1: they were set to 0 and dropped by the 1.0 floor) -- counted and NAMED. A null
is not coverage. FP gives a mean only: the simulations stay ours (disclosed).
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
    fp["fp_value"] = pd.to_numeric(fp["fantasy_points"], errors="coerce")
    projected = set(fp.loc[fp["fp_value"].notna(), "dk"])              # a null fantasyPoints is not a projection (M1)
    m_all = fr.merge(fp[["dk", "fantasy_points", "fp_value", "salary"]].rename(columns={"salary": "fp_salary"}), on="dk", how="inner")
    nulls = m_all[m_all["fp_value"].isna()]
    m = m_all[m_all["fp_value"].notna()].copy()
    skill5 = fr[fr.pos.isin(SKILL) & (fr.ours >= 5)]
    cov = float(skill5["dk"].isin(projected).mean()) if len(skill5) else 0.0
    dst = fr[fr.pos == "DST"]; dst_missing = dst.loc[~dst["dk"].isin(projected), "name"].tolist()
    if cov < MIN_COVERAGE:
        miss = skill5.loc[~skill5["dk"].isin(projected), "name"].tolist()[:8]
        raise Refused(f"coverage {cov:.3f} of our skill players projected >= 5 < {MIN_COVERAGE} (missing e.g. {miss})")
    if dst_missing:
        raise Refused(f"DSTs without an FP projection: {dst_missing}")
    sal_bad = m[pd.to_numeric(m.salary, errors="coerce").round() != pd.to_numeric(m.fp_salary, errors="coerce").round()]
    if len(sal_bad):
        raise Refused(f"{len(sal_bad)} matched players' FP salary differs from the frame's (wrong slate?): "
                      f"{sal_bad[['name', 'salary', 'fp_salary']].head(5).to_dict('records')}")
    m["fp"] = m["fp_value"].astype(float)
    elig = m[m.pos.isin(SKILL) & ((m.ours >= 3) | (m.fp >= 3))]
    r = float(np.corrcoef(elig.ours, elig.fp)[0, 1]) if len(elig) > 2 else float("nan")
    top = elig.assign(diff=elig.fp - elig.ours).reindex((elig.fp - elig.ours).abs().sort_values(ascending=False).index).head(15)
    if not (r >= MIN_R):
        raise Refused(f"FP and ours disagree: Pearson r {r:.3f} < {MIN_R} over {len(elig)} players (stale or wrong capture?)")
    out = m[["id", "dk", "name", "pos", "ours", "fp"]].rename(columns={"dk": "dk_draftable_id"}).sort_values("id").reset_index(drop=True)
    gates = {"coverage_skill_ge5": round(cov, 4), "dst_covered": int(len(dst)), "matched": int(len(m)),
             "frame_players": int(len(fr)), "kept_ours": int(len(fr) - len(m)), "pearson_r": round(r, 4),
             "fp_null_kept_ours": int(len(nulls)),
             "fp_null_players": [{"name": n, "pos": p, "ours": round(float(o), 2)} for n, p, o in
                                 sorted(zip(nulls.name, nulls.pos, nulls.ours), key=lambda x: -x[2])],
             "eligible_for_r": int(len(elig)),
             "top15_abs_diff": [{"name": n, "pos": p, "ours": round(float(o), 2), "fp": round(float(f), 2)}
                                for n, p, o, f in zip(top.name, top.pos, top.ours, top.fp)]}
    return out, gates


def content_floor(inactives_utc: str, explicit: str | None = None) -> pd.Timestamp:
    """The oldest FP update the T-70 build accepts: --content-floor-utc, else 06:00 CT on the inactives' local date
    (the operator 10-07: fall back to ours only if FP's numbers are from before Sunday morning)."""
    if explicit:
        return pd.Timestamp(explicit).tz_convert("UTC") if pd.Timestamp(explicit).tzinfo else pd.Timestamp(explicit).tz_localize("UTC")
    local = pd.Timestamp(inactives_utc).tz_convert("America/Chicago")
    return pd.Timestamp(local.date(), tz="America/Chicago").replace(hour=6).tz_convert("UTC")


def load_capture(season: int, week: int, before: str) -> tuple[pd.DataFrame, dict]:
    from google.cloud import bigquery
    from nfl_dfs.config import settings
    c = bigquery.Client(project=settings.project)
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", season),
                                                    bigquery.ScalarQueryParameter("w", "INT64", week),
                                                    bigquery.ScalarQueryParameter("b", "TIMESTAMP", before)])
    fp = c.query(f"""SELECT slate_id, slate_name, slate_player_id, name, position, salary, fantasy_points, retrieved_at, source_sha256,
               last_updated
        FROM `{settings.raw}.fantasy_points_dfs_projections`
        WHERE season = @s AND week = @w AND operator = 'DraftKings' AND slate_name = 'Main' AND retrieved_at < @b
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""", job_config=cfg).to_dataframe()
    if fp.empty:
        raise Refused(f"no FP DraftKings Main-slate capture for {season} W{week} before {before}")
    if fp.slate_id.nunique() != 1:
        raise Refused(f"the newest capture holds {fp.slate_id.nunique()} Main slates")
    lu = pd.to_datetime(fp.last_updated, utc=True, errors="coerce")
    meta = {"retrieved_at": pd.Timestamp(fp.retrieved_at.iloc[0]).isoformat(), "slate_id": str(fp.slate_id.iloc[0]),
            "source_sha256": str(fp.source_sha256.iloc[0]), "rows": int(len(fp)),
            "fp_last_updated": lu.max().isoformat() if lu.notna().any() else None}
    return fp, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True); ap.add_argument("--before", required=True)
    ap.add_argument("--inactives-utc", default=None); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-after-inactives", action="store_true",
                    help="the T-70 build: REFUSE FP numbers last updated before Sunday morning (--content-floor-utc); "
                         "numbers updated before the inactives are used and labelled (operator 10-07)")
    ap.add_argument("--content-floor-utc", default=None,
                    help="with --require-after-inactives: the oldest FP update accepted (default 06:00 CT on the inactives' date)")
    a = ap.parse_args(argv)
    try:
        fr = pd.read_parquet(a.frame)
        fp, cap = load_capture(a.season, a.week, a.before)
        out, gates = build(fr, fp)
    except Refused as e:
        print(f"FP PROJECTIONS REFUSED: {e}", file=sys.stderr)
        return 2
    fp_lu = pd.Timestamp(cap["fp_last_updated"]) if cap.get("fp_last_updated") else None
    inact = pd.Timestamp(a.inactives_utc) if a.inactives_utc else None
    captured_before = inact is not None and pd.Timestamp(cap["retrieved_at"]) < inact
    content_before = inact is not None and (fp_lu is None or fp_lu < inact)
    floor = content_floor(a.inactives_utc, a.content_floor_utc) if a.require_after_inactives and a.inactives_utc else None
    if inact is not None:
        print(f"FP CAPTURE TIMING: captured {cap['retrieved_at']} {'BEFORE' if captured_before else 'AFTER'} the 10:30 CT "
              f"inactives ({a.inactives_utc}); FP last updated {cap.get('fp_last_updated') or 'UNKNOWN'} "
              f"{'BEFORE' if content_before else 'AFTER'} them", file=sys.stderr)
    if a.require_after_inactives and (floor is None or fp_lu is None or fp_lu < floor):
        print(f"FP PROJECTIONS REFUSED: FP's numbers were last updated {cap.get('fp_last_updated') or 'UNKNOWN'}, before "
              f"Sunday morning ({floor.isoformat() if floor is not None else 'no --inactives-utc'}); the T-70 build uses OUR "
              "post-inactives projections (operator 10-07)", file=sys.stderr)
        return 2
    if content_before:
        print("!!! FP'S PROJECTIONS WERE LAST UPDATED BEFORE THE 10:30 CT INACTIVES "
              f"({cap.get('fp_last_updated') or 'UNKNOWN'}); USED ANYWAY (operator 10-07: label it honestly). DK OUT/IR "
              "players are still removed by the build; their teammates are not re-projected", file=sys.stderr)
    if gates["fp_null_kept_ours"]:
        print(f"FP NULL PROJECTIONS (kept ours): {gates['fp_null_kept_ours']} frame players: "
              + ", ".join(f"{x['name']} {x['pos']} {x['ours']}" for x in gates["fp_null_players"][:20]), file=sys.stderr)
    out.to_csv(a.out, index=False)
    meta = {"capture": cap, "frame": str(a.frame), "frame_sha256": hashlib.sha256(Path(a.frame).read_bytes()).hexdigest(),
            "before": a.before, "inactives_utc": a.inactives_utc,
            "before_inactives": content_before,                       # FP's numbers (last_updated) predate the inactives
            "captured_before_inactives": captured_before, "fp_last_updated": cap.get("fp_last_updated"),
            "content_floor_utc": floor.isoformat() if floor is not None else None, "gates": gates,
            "csv_sha256": hashlib.sha256(a.out.read_bytes()).hexdigest(),
            "note": "FP gives a mean only: the build's simulations (tail-sleeve P(line), vetting) stay ours",
            "written_utc": datetime.now(timezone.utc).isoformat()}
    Path(str(a.out) + ".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"FP PROJECTIONS: capture {cap['retrieved_at']} (slate {cap['slate_id']}); matched {gates['matched']} of "
          f"{gates['frame_players']} frame players (coverage {gates['coverage_skill_ge5']}, DSTs {gates['dst_covered']}); "
          f"r(FP, ours) {gates['pearson_r']}; kept ours for {gates['kept_ours']} (FP nulls among them "
          f"{gates['fp_null_kept_ours']}) -> {a.out}")
    for t in gates["top15_abs_diff"]:
        print(f"   {t['name']:28s} {t['pos']:3s} ours {t['ours']:6.2f}  FP {t['fp']:6.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
