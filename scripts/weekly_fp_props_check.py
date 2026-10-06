#!/usr/bin/env python3
"""The weekly paired check: Fantasy Points vs 0.5 FP + 0.5 props on the prop-covered players (class C candidate).
FROZEN 2026-10-06, before any Week-5 outcome (reports/2026-10-06-prereg-fp-props-weekly-check.md; the props report
reports/2026-10-06-props-and-winners.md). Week 4 (FP + props beat FP by 0.09 points) was SEEN and is NOT counted.

    python scripts/weekly_fp_props_check.py week --season 2026 --week 5 --frame <T-70 run>/frame.parquet \\
        --lock-utc 2026-10-11T17:00:00Z --contest <the week's Millionaire id> --out-dir ~/private/fp-props-check
    python scripts/weekly_fp_props_check.py pool --out-dir ~/private/fp-props-check

Population (fixed): QB / RB / WR / TE in the T-70 frame with a REAL prop number (`market_points` present and not equal to
DraftKings' points-per-game, the old fallback), an FP projection (the newest DraftKings Main capture before the T-70
build: weekly_projection_accuracy.resolve_cutoff / load_fp, exact draftable-id join), the Millionaire's fpts (by
normalised name; slate-wide name collisions dropped) and game-day ACT (O-32). Both arms are scored on the SAME rows.
Arms (fixed): FP; BLEND = 0.5 FP + 0.5 props.
Uncertainty: the game-cluster bootstrap within week, B 2000, seed 1 (as the frozen weekly accuracy reader).
THE RULE (pooled weeks >= 5 only): the blend is OFFERED when its pooled MAE is lower than FP's AND at least 95% of the
resamples are better. The operator decides; nothing here changes production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ownership_blend import norm  # noqa: E402
import weekly_projection_accuracy as WPA  # noqa: E402  (frozen: resolve_cutoff, load_fp)

SKILL = ("QB", "RB", "WR", "TE")
B, SEED = 2000, 1
SHARE = 0.95
FIRST_WEEK = 5                       # Week 4 was seen before the freeze and is never counted
RULE = (f"RULE: the 0.5 FP + 0.5 props blend is offered when its pooled MAE (weeks >= {FIRST_WEEK}) is lower than FP's AND "
        f"at least {SHARE:.0%} of B {B} game-cluster resamples (seed {SEED}, within week) are better")


def _key(v) -> str:
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def population(fr: pd.DataFrame, fp: pd.DataFrame, actual: pd.Series, active: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    """Pure: the week's paired rows (id, name, pos, game, season, week, fp, props, blend, actual) and the drop counts."""
    fr = fr.drop_duplicates("id").copy()
    names = fr["display_name"].astype(str).map(norm)
    dup = set(names[names.duplicated(keep=False)])
    actual = actual[~actual.index.duplicated(keep=False)]
    s = fr[fr.pos.astype(str).isin(SKILL)]
    d = pd.DataFrame({"id": s["id"].astype(str), "name": s["display_name"].astype(str), "pos": s["pos"].astype(str),
                      "game": s["game_id"].astype(str), "gsis_id": s["gsis_id"].astype(str),
                      "season": s["season"].astype(int), "week": s["week"].astype(int),
                      "props": pd.to_numeric(s["market_points"], errors="coerce"),
                      "dk_ppg": pd.to_numeric(s["dk_ppg"], errors="coerce") if "dk_ppg" in s else np.nan,
                      "dk": s["dk_draftable_id"].map(_key)})
    fpm = fp.assign(dk=fp["slate_player_id"].map(_key)).drop_duplicates("dk").set_index("dk")["fantasy_points"].astype(float)
    d["fp"] = d.dk.map(fpm)
    audit = {"skill_rows": int(len(d))}
    audit["dropped_no_props"] = int(d.props.isna().sum()); d = d[d.props.notna()]
    fb = (d.props - d.dk_ppg).abs() < 0.01
    audit["dropped_props_fallback"] = int(fb.sum()); d = d[~fb]
    audit["dropped_no_fp"] = int(d.fp.isna().sum()); d = d[d.fp.notna()]
    nk = d.name.map(norm)
    audit["dropped_name_collision"] = int(nk.isin(dup).sum()); d = d[~nk.isin(dup)]
    d["actual"] = d.name.map(norm).map(actual)
    audit["dropped_no_actual"] = int(d.actual.isna().sum()); d = d[d.actual.notna()]
    if active is not None:
        from nfl_dfs.analysis.game_day_active import filter_game_day_active
        d, a = filter_game_day_active(d, active)
        audit["dropped_not_act"] = a["dropped_not_act"]; audit["dropped_no_roster_row"] = a["dropped_no_roster_row"]
    d["blend"] = 0.5 * d.fp + 0.5 * d.props
    audit["population"] = int(len(d)); audit["games"] = int(d.game.nunique())
    return d.drop(columns=["dk", "dk_ppg"]).sort_values("id").reset_index(drop=True), audit


def bootstrap(d: pd.DataFrame, b: int = B, seed: int = SEED) -> dict:
    """MAE(FP) - MAE(blend) (> 0: the blend is more accurate), games resampled within week."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in d.groupby(["season", "week", "game"], sort=True)}
    byw: dict[tuple, list] = {}
    for key in groups:
        byw.setdefault((int(key[0]), int(key[1])), []).append(key)
    err = {k: np.array([(g.fp - g.actual).abs().sum(), (g.blend - g.actual).abs().sum()]) for k, g in groups.items()}
    cnt = {k: len(g) for k, g in groups.items()}
    v = []
    for _ in range(b):
        tot, n = np.zeros(2), 0
        for w in sorted(byw):
            keys = byw[w]
            for j in rng.integers(0, len(keys), len(keys)):
                tot += err[keys[j]]; n += cnt[keys[j]]
        v.append((tot[0] - tot[1]) / n)
    v = np.asarray(v)
    return {"mean": float(v.mean()), "p05": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95)),
            "share_better": float((v > 0).mean())}


def verdict(d: pd.DataFrame, boot: dict) -> str:
    m_fp, m_bl = float((d.fp - d.actual).abs().mean()), float((d.blend - d.actual).abs().mean())
    if m_bl < m_fp and boot["share_better"] >= SHARE:
        return f"THE BLEND IS OFFERED (MAE {m_bl:.3f} vs FP {m_fp:.3f}; {boot['share_better']:.3f} of resamples better): to the operator"
    return f"not offered at the frozen rule (MAE blend {m_bl:.3f} vs FP {m_fp:.3f}; {boot['share_better']:.3f} of resamples better)"


def report(d: pd.DataFrame, title: str) -> None:
    bs = bootstrap(d)
    print(f"{title}: players {len(d)}, games {d.groupby(['season', 'week', 'game']).ngroups}")
    for c in ("fp", "blend", "props"):
        e = d[c] - d.actual
        print(f"  {c:6s} MAE {float(e.abs().mean()):.3f}  bias {float(e.mean()):+.3f}  "
              + "  ".join(f"{p} {float(e[d.pos == p].abs().mean()):.2f}" for p in SKILL if (d.pos == p).any()))
    print(f"  FP - blend MAE improvement {bs['mean']:+.3f} (5-95% {bs['p05']:+.3f} to {bs['p95']:+.3f}); share of resamples better {bs['share_better']:.3f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week"); w.add_argument("--season", type=int, required=True); w.add_argument("--week", type=int, required=True)
    w.add_argument("--frame", type=Path, required=True); w.add_argument("--lock-utc", required=True)
    w.add_argument("--contest", required=True); w.add_argument("--out-dir", type=Path, required=True)
    w.add_argument("--capture-before", default=None)
    p = sub.add_parser("pool"); p.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "week":
        if not os.environ.get("GCP_PROJECT", "").strip():
            raise SystemExit("GCP_PROJECT is not set: this reader reads licensed FP data and runs only with an explicit project")
        from nfl_dfs.analysis.game_day_active import load_active
        from nfl_dfs.bq import query_df
        from nfl_dfs.config import settings
        fr = pd.read_parquet(a.frame)
        cutoff, src = WPA.resolve_cutoff(a.frame, a.capture_before, a.lock_utc)
        fp, cap = WPA.load_fp(a.season, a.week, cutoff)
        act = query_df(f"""SELECT display_name, MAX(CAST(fpts AS FLOAT64)) fpts FROM `{settings.raw}.contest_ownership`
            WHERE season = @s AND week = @w AND contest_id = @c GROUP BY 1""", params={"s": a.season, "w": a.week, "c": str(a.contest)})
        actual = pd.Series(act.fpts.to_numpy(float), index=act.display_name.map(norm))
        d, audit = population(fr, fp, actual, load_active([a.season]))
        a.out_dir.mkdir(parents=True, exist_ok=True)
        stem = a.out_dir / f"fp-props-{a.season}-w{a.week:02d}"
        d.to_csv(f"{stem}.csv", index=False)
        audit.update({"capture": cap, "capture_before": cutoff, "capture_before_source": src, "lock_utc": a.lock_utc,
                      "contest": str(a.contest), "rows_sha256": hashlib.sha256(Path(f"{stem}.csv").read_bytes()).hexdigest(),
                      "written_utc": datetime.now(timezone.utc).isoformat()})
        Path(f"{stem}.json").write_text(json.dumps(audit, indent=1) + "\n")
        print("population:", {k: v for k, v in audit.items() if isinstance(v, int)})
        print(f"player rows: {stem}.csv  n {len(d)}  sha256 {audit['rows_sha256']}")
        report(d, f"{a.season} W{a.week}")
        return 0
    files = sorted(a.out_dir.glob("fp-props-*-w*.csv"))
    pooled = pd.concat([pd.read_csv(f, dtype={"game": str, "gsis_id": str, "id": str}) for f in files], ignore_index=True) if files else pd.DataFrame()
    if pooled.empty:
        raise SystemExit(f"no weekly rows in {a.out_dir}")
    early = sorted(set(int(x) for x in pooled.week[pooled.week < FIRST_WEEK]))
    if early:
        print(f"weeks {early} are before Week {FIRST_WEEK} (seen before the freeze): NOT counted")
        pooled = pooled[pooled.week >= FIRST_WEEK]
    if pooled.empty:
        raise SystemExit("no counted week yet")
    for f in files:
        print(f"player rows: {f.name}  sha256 {hashlib.sha256(f.read_bytes()).hexdigest()}")
    for (s, wk), g in pooled.groupby(["season", "week"]):
        report(g, f"{s} W{wk}")
    report(pooled, "POOLED (weeks >= 5)")
    print(RULE)
    print("CHECK:", verdict(pooled, bootstrap(pooled)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
