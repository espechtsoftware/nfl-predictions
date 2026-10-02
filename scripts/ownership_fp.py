"""Fantasy Points' projected DraftKings ownership as the ownership term's source (operator 2026-10-02: "I would like to
use it sunday"; a reversible Week-4 trial under adoption track v2; PREREG-O1 still grades it after the fact).

Reads the newest FP capture (nfl_raw.fantasy_points_projected_ownership, DraftKings) taken at or before --now and no
older than --max-age-hours, matches it to the build's frame, rescales it, and writes the file union_reselect's
--main-own-source reads (pred_own %, keyed by dk_player_id / gsis id / id).
- Matching: normalised name (ownership_blend.norm) + team; a name unique in the frame matches on the name alone (FP and
  the frame spell some team codes differently).
- Scale (the reviewer's rule for a trialled source, O1 amendment 2): the matched skill players' FP total is rescaled
  to the blend's skill total on the same players (the lag file's when no blend exists this run). The tilt then means
  what was tested (0.20 on the blend's scale).
- Refuses (exit 2, "FP OWNERSHIP REFUSED: ...") on no capture, a stale capture, another week, fewer than MIN_COVERAGE
  of the frame's skill players projected >= 5 matched, or no scale reference. The host then falls back LOUDLY to the
  TabPFN -> blend -> lag chain.

Usage: ownership_fp.py --season 2026 --week 4 --frame <K90>/frame.parquet --lag ownership_lag.csv [--blend f.csv] \
           [--max-age-hours 30] [--now ISO] --out ownership_fp-<tag>.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from o1_common import _key  # noqa: E402
from ownership_blend import norm  # noqa: E402

PROJECT = "nfl-predictions-503414"
SKILL = ("QB", "RB", "WR", "TE")
MIN_COVERAGE = 0.9
FLOOR_PROJ = 5.0


def refuse(why: str) -> None:
    raise SystemExit(f"FP OWNERSHIP REFUSED: {why}")


def match_to_frame(fp: pd.DataFrame, fr: pd.DataFrame) -> pd.DataFrame:
    """fp: name, team, projected_ownership_pct. fr: id, name/display_name, team, pos (+dk_player_id). Returns the frame
    rows that FP prices, with fp_own."""
    f = fr.copy(); f["key"] = f.get("display_name", f.get("name")).map(norm)
    p = fp.copy(); p["key"] = p.name.map(norm)
    by_team = f.merge(p[["key", "team", "projected_ownership_pct"]], on=["key", "team"], how="inner")
    rest = f[~f.id.isin(set(by_team.id))]
    # a name-only match needs the name unique in the WHOLE frame and in FP, and the FP row not already taken by a team
    # match (reviewer 10-02: two frame "Mike Williams", FP pricing one, must not hand his value to the other)
    dup = set(f.key[f.key.duplicated(keep=False)])
    unique = rest[~rest.key.isin(dup)]
    pk = p[~p.key.duplicated(keep=False) & ~p.key.isin(set(by_team.key))]
    by_name = unique.merge(pk[["key", "projected_ownership_pct"]], on="key", how="inner")
    out = pd.concat([by_team, by_name], ignore_index=True).drop_duplicates("id")
    return out.rename(columns={"projected_ownership_pct": "fp_own"})


def scale_factor(m: pd.DataFrame, ref: pd.DataFrame) -> float:
    """FP rescaled so its skill total equals the reference's on the same (matched) skill players."""
    r = ref.copy(); r["key"] = r.display_name.map(norm)
    if "key" not in m:
        m = m.assign(key=m.display_name.map(norm))
    sk = m[m.pos.isin(SKILL)].merge(r[["key", "pred_own"]], on="key", how="inner")
    fp_tot, ref_tot = float(sk.fp_own.sum()), float(pd.to_numeric(sk.pred_own, errors="coerce").clip(lower=0).sum())
    if fp_tot <= 0 or ref_tot <= 0:
        refuse(f"no scale reference (FP skill total {fp_tot:.1f}, reference {ref_tot:.1f} on {len(sk)} shared players)")
    return ref_tot / fp_tot


def fill_unmatched(miss: pd.DataFrame, lag: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Skill players FP does not price get the lag file's value on the reference's scale (reviewer 10-02, BLEND_FP's
    "else LAG" rule; no term at all would act as 0% owned). The scale is ref/lag skill totals on their shared players
    (1 when the reference is the lag file). Matched by dk_player_id, else a name unique in the lag file."""
    if miss.empty:
        return pd.DataFrame(columns=["dk_player_id", "id", "display_name", "pos", "team", "pred_own", "fp_own_raw", "filled_from"])
    lg = lag.copy(); lg["key"] = lg.display_name.map(norm); lg["v"] = pd.to_numeric(lg.pred_own, errors="coerce").clip(lower=0)
    rf = ref.copy(); rf["key"] = rf.display_name.map(norm); rf["v"] = pd.to_numeric(rf.pred_own, errors="coerce").clip(lower=0)
    lk = lg[lg.pos.isin(SKILL) & ~lg.key.duplicated(keep=False)]; rk = rf[~rf.key.duplicated(keep=False)]
    sh = lk.merge(rk[["key", "v"]], on="key", suffixes=("", "_ref"))
    r = float(sh.v_ref.sum() / sh.v.sum()) if len(sh) and sh.v.sum() > 0 else 1.0
    by_dk = {_key(d): v for d, v in zip(lg.get("dk_player_id", pd.Series(dtype=str)), lg.v) if _key(d)}
    by_key = dict(zip(lk.key, lk.v))
    rows = []
    for _, x in miss.iterrows():
        name = x.get("display_name", x.get("name"))
        dk = _key(x.get("dk_player_id"))
        v = by_dk[dk] if dk in by_dk else by_key.get(norm(name))
        if v is not None and pd.notna(v):
            rows.append({"dk_player_id": x.get("dk_player_id"), "id": x.id, "display_name": name, "pos": x.pos,
                         "team": x.team, "pred_own": float(v) * r, "fp_own_raw": None, "filled_from": "lag"})
    return pd.DataFrame(rows, columns=["dk_player_id", "id", "display_name", "pos", "team", "pred_own", "fp_own_raw", "filled_from"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--lag", type=Path, required=True)
    ap.add_argument("--blend", type=Path); ap.add_argument("--max-age-hours", type=float, default=30.0)
    ap.add_argument("--now"); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    now = pd.Timestamp(a.now) if a.now else pd.Timestamp(datetime.now(UTC))
    from google.cloud import bigquery
    c = bigquery.Client(project=PROJECT)
    fp = c.query(f"""SELECT name, team, position, projected_ownership_pct, retrieved_at, last_updated
        FROM `{PROJECT}.nfl_raw.fantasy_points_projected_ownership`
        WHERE season={a.season} AND week={a.week} AND operator='DraftKings' AND retrieved_at <= TIMESTAMP('{now.isoformat()}')
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""").to_dataframe()
    if fp.empty:
        refuse(f"no FP capture for {a.season} week {a.week} at or before {now}")
    at = pd.Timestamp(fp.retrieved_at.max()); age = (now - at).total_seconds() / 3600
    if age > a.max_age_hours:
        refuse(f"the newest FP capture is {age:.1f} h old (limit {a.max_age_hours})")
    fr = pd.read_parquet(a.frame)
    m = match_to_frame(fp, fr)
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0)
    core = fr[fr.pos.isin(SKILL) & (proj >= FLOOR_PROJ)]
    cov = float(core.id.isin(set(m.id)).mean()) if len(core) else 0.0
    if cov < MIN_COVERAGE:
        refuse(f"FP matches {cov:.1%} of the frame's skill players projected >= {FLOOR_PROJ} (< {MIN_COVERAGE:.0%})")
    ref_path = a.blend if a.blend and a.blend.is_file() else a.lag
    ref = pd.read_csv(ref_path)
    k = scale_factor(m, ref)
    out = pd.DataFrame({"dk_player_id": m.get("dk_player_id"), "id": m.id, "display_name": m.get("display_name", m.get("name")),
                        "pos": m.pos, "team": m.team, "pred_own": m.fp_own * k, "fp_own_raw": m.fp_own, "filled_from": "fp"})
    miss = core[~core.id.isin(set(m.id))]
    filled = fill_unmatched(miss, pd.read_csv(a.lag), ref)
    if len(miss):
        print(f"FP unmatched skill players projected >= {FLOOR_PROJ}: {len(miss)}: "
              + ", ".join(f"{n} ({p} {t})" for n, p, t in zip(miss.get("display_name", miss.get("name")), miss.pos, miss.team)))
        print(f"  filled from the lag file on the reference scale: {len(filled)}; left without a term: {len(miss) - len(filled)}")
    out = pd.concat([out, filled], ignore_index=True)
    ref_tot = float(m.fp_own[m.pos.isin(SKILL)].sum() * k)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    receipt = {"source": "fantasy_points_projected_ownership (DraftKings)", "retrieved_at": str(at), "age_hours": round(age, 2),
               "fp_last_updated": str(fp.last_updated.max()), "matched": int(len(m)), "fp_rows": int(len(fp)),
               "coverage_skill_proj5": round(cov, 4), "scale_reference": ref_path.name, "scale_factor": round(k, 4),
               "reference_skill_total": round(ref_tot, 1), "unmatched_skill_proj5": int(len(miss)),
               "filled_from_lag": int(len(filled)), "csv_sha256": hashlib.sha256(a.out.read_bytes()).hexdigest()}
    Path(str(a.out) + ".receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(f"FP OWNERSHIP OK: capture {at} ({age:.1f} h old), matched {len(m)} of {len(fp)}, coverage {cov:.1%}, "
          f"scaled x{k:.3f} to {ref_path.name}'s skill total ({ref_tot:.1f} on the matched skill players) -> {a.out.name}")
    print(f"FP OWNERSHIP AGE {age:.1f} h; SCALE {ref_path.name} x{k:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
