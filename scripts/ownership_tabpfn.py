#!/usr/bin/env python3
"""The week's TabPFN predicted ownership for the ownership term (operator 2026-09-30: replaces the blend on the main book
in Week 4 if the smoke passes by Thursday 12:00 CT; PREREG-L23b's TABPFN_LS at full scale, stage 1 PASS). Writes the
same kind of file `union_reselect.py --main-own-source` reads (`pred_own` in %, keyed by dk_player_id / gsis_id / id).

Three steps, so the GPU environment never needs BigQuery:

  lags      (main venv, BigQuery; Saturday)  own_l1 / own_l3 per player from this season's Millionaire ownership, L23's
            definition: for each prior week w-1..w-3 with an ownership file, the player's ownership %, 0 when absent from
            that week's file; own_l1 = week w-1, own_l3 = the mean over those weeks.
    python scripts/ownership_tabpfn.py lags --season 2026 --week 4 --out ~/week4-sunday/ownership_lags.csv
  features  (main venv, no network; before each union)  the build frame's skill players with L23's eleven features, the
            newest LineStar capture (<= --max-age-hours, this week, with its receipt), and every transfer check below.
    python scripts/ownership_tabpfn.py features --season 2026 --week 4 --frame <run dir>/frame.parquet \\
        --lags ~/week4-sunday/ownership_lags.csv --linestar-dir ~/week4-sunday/linestar --history <rows.parquet> --out <feats.parquet>
  fit       (the GPU env ~/.local/tabpfn311-gpu; seconds)  TabPFN 2.2.1 on the history rows (L23's rows + 2026 W1-3,
            newest CTX_MAX kept), predicts the week, writes the pred_own csv and its receipt.
    ~/.local/tabpfn311-gpu/bin/python scripts/ownership_tabpfn.py fit --rows <rows.parquet> [--rows-2026 <parquet>] \\
        --features <feats.parquet> --out <ownership_tabpfn.csv>

Transfer checks (each refuses with "OWNERSHIP TABPFN REFUSED: ..." and exit 2; the chain then keeps the blend's file,
loudly): the frame's `spread` is the live convention (a favourite is positive) and L23's history uses the opposite, so
the feature is rebuilt as game_total - 2 x implied_team_total and must agree with -spread (|diff| <= 1 on >= 95% of rows);
every frame feature must sit inside the history's p0.5..p99.5 band on >= 95% of rows; LineStar must cover >= 50% of the
skill players projected >= 5 and its values must be percentages on the history's scale (per-slate total and top-20 mean within 2x);
the rows file must carry its pinned sha256; the fit needs CUDA; the predictions must cover every skill row and sum to a
live week's scale (150..900 over skill players).

Outputs carry third-party values (LineStar): the week's private directory only, never the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
POS = {p: i for i, p in enumerate(SKILL)}
FEATURES = ["pos_code", "salary", "mean_projection", "value", "implied_team_total", "game_total", "spread",
            "salary_delta_wow", "own_l1", "own_l3", "linestar_own"]          # PREREG-L23b's TABPFN_LS, in its order
FRAME_CHECKED = ["salary", "mean_projection", "value", "implied_team_total", "game_total", "spread", "salary_delta_wow"]
ROWS_SHA256 = "0bec4237eb4c4bc1228571e5628685b3cc26e8aaed433f8b8f2056d5062edde9"   # L23's rows file
CTX_MAX, N_ESTIMATORS, SEED = 28_000, 8, 0                                         # PREREG-L23b (repair 1 adds the flag)
# The Sunday Millionaire by DraftKings' name OR its import label ("milly", "milly20": Week 3's standings were imported
# under labels) -- ownership_sets.py's rule. "Millionaire" alone silently dropped Week 3 (production 2026-09-30).
MILLIONAIRE_NAME_RE = r"Millionaire|^milly"


def refuse(why: str):
    raise SystemExit(f"OWNERSHIP TABPFN REFUSED: {why}")


def norm(name: object) -> str:
    """L15/L23's name key: lower case, generational suffixes and punctuation dropped, single spaces."""
    s = str(name).lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    s = re.sub(r"[^a-z ]", "", s)
    return " ".join(s.split())


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- lags

def lags_from_weeks(weeks: dict[int, dict[str, float]], week: int) -> pd.DataFrame:
    """L23's definition. weeks: {prior week: {name key: ownership %}} for the weeks that HAVE a Millionaire file.
    own_l1 = week-1's value (0 if absent from that file; NaN if week-1 has no file); own_l3 = mean over w-1..w-3 files."""
    keys = sorted({k for d in weeks.values() for k in d})
    prior = [week - k for k in (1, 2, 3) if (week - k) in weeks]
    rows = []
    for k in keys:
        l1 = weeks[week - 1].get(k, 0.0) if (week - 1) in weeks else np.nan
        l3 = float(np.mean([weeks[p].get(k, 0.0) for p in prior])) if prior else np.nan
        rows.append({"key": k, "own_l1": l1, "own_l3": l3})
    return pd.DataFrame(rows, columns=["key", "own_l1", "own_l3"])


def require_prior_week(weeks: dict[int, dict[str, float]], week: int) -> None:
    """own_l1 is last week's file: a missing week-1 Millionaire makes own_l1 NaN for EVERY player, which the fit would
    accept silently (L23 trained with NaN only in a season's first weeks). Refuse instead (-> the blend, loudly)."""
    if week > 1 and (week - 1) not in weeks:
        refuse(f"no Millionaire ownership for week {week - 1} (weeks found: {sorted(weeks)}); own_l1 would be NaN for "
               f"every player -- import last week's standings or check the contest name/label filter")


def cmd_lags(a) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from nfl_dfs.bq import query_df  # noqa: E402
    from nfl_dfs.config import settings as st  # noqa: E402
    own = query_df(f"""
        WITH c AS (SELECT week, contest_id, ANY_VALUE(contest_name) nm, COUNT(*) n
                   FROM `{st.raw}.contest_ownership` WHERE season = {int(a.season)} AND week < {int(a.week)} GROUP BY 1, 2),
        pick AS (SELECT week, ARRAY_AGG(contest_id ORDER BY n DESC LIMIT 1)[OFFSET(0)] cid FROM c
                 WHERE REGEXP_CONTAINS(nm, r"{MILLIONAIRE_NAME_RE}") AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555") GROUP BY 1),
        slots AS (SELECT o.week, o.display_name, o.roster_position, ANY_VALUE(o.pct_drafted) p
                  FROM `{st.raw}.contest_ownership` o JOIN pick ON o.week = pick.week AND o.contest_id = pick.cid
                  WHERE o.season = {int(a.season)} GROUP BY 1, 2, 3)
        SELECT week, display_name, SUM(p) own FROM slots GROUP BY 1, 2""")
    if own.empty:
        refuse(f"no Millionaire ownership rows for {a.season} before week {a.week}")
    own["key"] = own.display_name.map(norm)
    weeks = {int(w): g.groupby("key").own.sum().to_dict() for w, g in own.groupby("week")}
    require_prior_week(weeks, int(a.week))
    out = lags_from_weeks(weeks, int(a.week))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"wrote {a.out}: {len(out)} players; weeks with a Millionaire file {sorted(weeks)}; "
          f"own_l1 max {out.own_l1.max():.1f}%, own_l3 max {out.own_l3.max():.1f}%")
    return 0


# ---------------------------------------------------------------- features

def spread_historical(fr: pd.DataFrame, tol: float = 1.0, min_agree: float = 0.95) -> pd.Series:
    """L23's convention (implied_team_total = (game_total - spread) / 2, a favourite is negative) from the live frame,
    whose `spread` has the opposite sign. Rebuilt from the totals and checked against -spread."""
    tot = pd.to_numeric(fr.game_total, errors="coerce"); imp = pd.to_numeric(fr.implied_team_total, errors="coerce")
    sp = pd.to_numeric(fr.spread, errors="coerce")
    rebuilt = tot - 2.0 * imp
    both = rebuilt.notna() & sp.notna()
    if both.sum() == 0:
        refuse("no row carries game_total, implied_team_total and spread: the spread convention cannot be checked")
    agree = float(((rebuilt[both] - (-sp[both])).abs() <= tol).mean())
    if agree < min_agree:
        refuse(f"the frame's spread convention is not the one checked on 2026-09-30: game_total - 2 x implied agrees with "
               f"-spread on {agree:.1%} of rows (< {min_agree:.0%})")
    return rebuilt.where(rebuilt.notna(), -sp)


def newest_capture(d: Path, season: int, week: int, max_age_hours: float, now: datetime) -> tuple[Path, dict]:
    hits = sorted(c for c in Path(d).glob("linestar-own-*.csv") if c.with_name(c.name[:-4] + ".receipt.json").is_file())
    if not hits:
        refuse(f"no LineStar capture with a receipt under {d}")
    rec_of = {c: json.loads(c.with_name(c.name[:-4] + ".receipt.json").read_text()) for c in hits}
    cap = max(hits, key=lambda c: rec_of[c].get("captured_at_utc", ""))
    rec = rec_of[cap]
    if int(rec.get("season", -1)) != int(season) or int(rec.get("week", -1)) != int(week):
        refuse(f"the newest LineStar capture {cap.name} is for {rec.get('season')} week {rec.get('week')}, not {season} week {week}")
    at = datetime.fromisoformat(str(rec.get("captured_at_utc")).replace("Z", "+00:00"))
    age = (now - at).total_seconds() / 3600.0
    if age > max_age_hours:
        refuse(f"the newest LineStar capture {cap.name} is {age:.1f} h old (> {max_age_hours} h)")
    if rec.get("csv_sha256") != sha256_file(cap):
        refuse(f"the LineStar capture {cap.name} does not match its receipt's sha256")
    return cap, {**rec, "path": str(cap), "age_hours": round(age, 2)}


def build_features(fr: pd.DataFrame, lags: pd.DataFrame, ls: pd.DataFrame) -> pd.DataFrame:
    """One row per skill player projected >= 1, with L23's features in its conventions."""
    f = fr.copy()
    f["pos"] = f.pos.astype(str).str.upper()
    f = f[f.pos.isin(SKILL)].copy()
    f["mean_projection"] = pd.to_numeric(f.mean_projection, errors="coerce")
    f = f[f.mean_projection >= 1.0].copy()
    f["spread"] = spread_historical(f)
    for c in ("salary", "implied_team_total", "game_total", "salary_delta_wow"):
        f[c] = pd.to_numeric(f[c], errors="coerce") if c in f.columns else np.nan
    f["pos_code"] = f.pos.map(POS)
    f["value"] = f.mean_projection / (f.salary / 1000.0)
    name = f["name"] if "name" in f.columns else f["display_name"]
    f["_key"] = name.map(norm)
    lg = lags.drop_duplicates("key").set_index("key")
    f["own_l1"] = f._key.map(lg.own_l1) if len(lg) else np.nan
    f["own_l3"] = f._key.map(lg.own_l3) if len(lg) else np.nan
    # a player on the slate but absent from every prior Millionaire file: 0, as L23 (the weeks exist)
    if len(lg):
        has_l1 = lg.own_l1.notna().any(); has_l3 = lg.own_l3.notna().any()
        if has_l1: f["own_l1"] = f.own_l1.fillna(0.0)
        if has_l3: f["own_l3"] = f.own_l3.fillna(0.0)
    l = ls.assign(_key=ls.name.map(norm), _pos=ls.pos.astype(str).str.upper(), linestar_own=pd.to_numeric(ls.own_proj, errors="coerce"))
    l = l.drop_duplicates(["_key", "_pos"]).set_index(["_key", "_pos"]).linestar_own
    f["linestar_own"] = [l.get((k, p), np.nan) for k, p in zip(f._key, f.pos)]
    keep = [c for c in ("id", "dk_player_id", "gsis_id") if c in f.columns]
    out = f[keep + ["pos"]].copy()
    out["display_name"] = name.values
    for c in FEATURES:
        out[c] = pd.to_numeric(f[c], errors="coerce").values
    return out.reset_index(drop=True)


def transfer_checks(feats: pd.DataFrame, hist: pd.DataFrame, min_in_band: float = 0.95, min_ls_cover: float = 0.5) -> dict:
    """Every frame feature inside the history's p0.5..p99.5 band on >= min_in_band of rows; LineStar coverage and scale."""
    out = {}
    for c in FRAME_CHECKED:
        h = pd.to_numeric(hist[c], errors="coerce").dropna(); v = pd.to_numeric(feats[c], errors="coerce").dropna()
        if len(v) == 0:
            refuse(f"feature {c} is empty on the live frame")
        lo, hi = float(h.quantile(0.005)), float(h.quantile(0.995))
        share = float(((v >= lo) & (v <= hi)).mean())
        out[c] = {"history_band": [round(lo, 2), round(hi, 2)], "live_in_band": round(share, 4), "live_nan": round(float(feats[c].isna().mean()), 4)}
        if share < min_in_band:
            refuse(f"feature {c}: {share:.1%} of live rows inside the history's band [{lo:.2f}, {hi:.2f}] (< {min_in_band:.0%})")
    core = feats[feats.mean_projection >= 5]
    cover = float(core.linestar_own.notna().mean()) if len(core) else 0.0
    if cover < min_ls_cover:
        refuse(f"LineStar covers {cover:.1%} of the skill players projected >= 5 (< {min_ls_cover:.0%})")
    hl = pd.to_numeric(hist.linestar_own, errors="coerce").dropna(); vl = feats.linestar_own.dropna()
    if float(vl.max()) <= 1.0 or float(vl.min()) < -0.5:
        refuse(f"LineStar values run {float(vl.min()):.3f}..{float(vl.max()):.3f}: not percentages")
    # the scale on a like-for-like basis: the per-slate total and the top-20 mean (2026-09-30 mechanics run on W3: the
    # live capture covers 83% of the projection-1-to-5 players with ~0.3% values where the history covers 33%, so the
    # median is not comparable; the totals are, 785 vs 793, top-20 19.2 vs 17.9)
    by = hist.assign(_ls=pd.to_numeric(hist.linestar_own, errors="coerce")).groupby(["season", "week"])._ls if {"season", "week"} <= set(hist.columns) else None
    h_sum = float(by.sum().median()) if by is not None else float(hl.sum())
    h_top = float(by.apply(lambda s: s.nlargest(20).mean()).median()) if by is not None else float(hl.nlargest(20).mean())
    l_sum, l_top = float(vl.sum()), float(vl.nlargest(20).mean())
    for what, live, histv in (("total", l_sum, h_sum), ("top-20 mean", l_top, h_top)):
        r = live / max(1e-9, histv)
        if not 0.5 <= r <= 2.0:
            refuse(f"LineStar's per-slate {what} is {r:.2f}x the history's ({live:.1f} vs {histv:.1f}; outside 0.5..2x): a scale change")
    out["linestar"] = {"coverage_projected_5": round(cover, 4), "coverage_all": round(float(feats.linestar_own.notna().mean()), 4),
                       "live_total": round(l_sum, 1), "history_total_median": round(h_sum, 1),
                       "live_top20_mean": round(l_top, 2), "history_top20_mean_median": round(h_top, 2)}
    return out


def cmd_features(a) -> int:
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    for p, what in ((a.frame, "the frame"), (a.lags, "the lags file"), (a.history, "the history rows")):
        if not Path(p).is_file():
            refuse(f"{what} {p} does not exist")
    cap, cap_meta = newest_capture(a.linestar_dir, a.season, a.week, a.max_age_hours, now)
    fr = pd.read_parquet(a.frame); lags = pd.read_csv(a.lags); ls = pd.read_csv(cap); hist = pd.read_parquet(a.history)
    feats = build_features(fr, lags, ls)
    checks = transfer_checks(feats, hist)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(a.out, index=False)
    rec = {"built_utc": now.isoformat(), "season": a.season, "week": a.week, "rows": len(feats), "features": FEATURES,
           "frame": {"path": str(a.frame), "sha256": sha256_file(a.frame)}, "lags": {"path": str(a.lags), "sha256": sha256_file(a.lags)},
           "linestar": cap_meta, "history_sha256": sha256_file(a.history), "checks": checks,
           "spread": "rebuilt as game_total - 2 x implied_team_total (L23's convention; the frame's spread is the opposite sign)"}
    Path(str(a.out) + ".receipt.json").write_text(json.dumps(rec, indent=1, default=str))
    print(f"features {a.out}: {len(feats)} skill players; LineStar {cap.name} ({cap_meta['age_hours']} h), "
          f"coverage {checks['linestar']['coverage_projected_5']:.1%}; every transfer check passed")
    return 0


# ---------------------------------------------------------------- fit

def context_rows(rows: pd.DataFrame, rows_2026: pd.DataFrame | None, ctx_max: int = CTX_MAX) -> pd.DataFrame:
    parts = [rows] + ([rows_2026] if rows_2026 is not None and len(rows_2026) else [])
    ctx = pd.concat([p[["season", "week"] + FEATURES + ["target_own"]] for p in parts], ignore_index=True)
    ctx = ctx.assign(_o=ctx.season * 100 + ctx.week).sort_values("_o", kind="stable")
    return ctx.tail(ctx_max).drop(columns="_o")


def check_predictions(pred: np.ndarray, lo: float = 150.0, hi: float = 900.0) -> dict:
    p = np.asarray(pred, dtype=float)
    if len(p) == 0 or not np.all(np.isfinite(p)):
        refuse("the fit returned non-finite predictions")
    s = float(np.clip(p, 0, None).sum())
    if not lo <= s <= hi:
        refuse(f"the predictions sum to {s:.0f} over the skill players (outside {lo:.0f}..{hi:.0f}): not a live week's scale")
    return {"sum": round(s, 1), "max": round(float(p.max()), 2), "min": round(float(p.min()), 3)}


def fit_predict(ctx: pd.DataFrame, feats: pd.DataFrame, regressor=None) -> np.ndarray:
    if regressor is None:
        import torch
        if not torch.cuda.is_available():
            refuse("no CUDA device (the fit is PREREG-L23b's GPU form; no CPU fallback)")
        from tabpfn import TabPFNRegressor
        regressor = TabPFNRegressor(device="cuda", random_state=SEED, n_estimators=N_ESTIMATORS, ignore_pretraining_limits=True)
    regressor.fit(ctx[FEATURES].to_numpy(np.float32), ctx.target_own.to_numpy(np.float32))
    return np.clip(np.asarray(regressor.predict(feats[FEATURES].to_numpy(np.float32)), dtype=float), 0.0, None)


def cmd_fit(a) -> int:
    for p, what in ((a.rows, "the rows file"), (a.features, "the features file")):
        if not Path(p).is_file():
            refuse(f"{what} {p} does not exist")
    got = sha256_file(a.rows)
    if got != ROWS_SHA256:
        refuse(f"the rows file's sha256 {got[:12]}… is not L23's {ROWS_SHA256[:12]}…")
    rows = pd.read_parquet(a.rows); r26 = pd.read_parquet(a.rows_2026) if a.rows_2026 else None
    feats = pd.read_parquet(a.features)
    ctx = context_rows(rows, r26)
    import time
    t = time.time()
    pred = fit_predict(ctx, feats)
    stats = check_predictions(pred)
    out = feats[[c for c in ("id", "dk_player_id", "gsis_id", "display_name", "pos") if c in feats.columns]].copy()
    out["pred_own"] = pred
    out["pred_rank"] = out.pred_own.rank(ascending=False, method="first").astype(int)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.sort_values("pred_rank").to_csv(a.out, index=False)
    import tabpfn, torch  # noqa: E401
    rec = {"built_utc": datetime.now(timezone.utc).isoformat(), "predictor": "tabpfn (PREREG-L23b TABPFN_LS form)",
           "rows_sha256": got, "rows_2026": {"path": str(a.rows_2026), "sha256": sha256_file(a.rows_2026)} if a.rows_2026 else None,
           "features": {"path": str(a.features), "sha256": sha256_file(a.features)}, "context_rows": len(ctx), "ctx_max": CTX_MAX,
           "n_estimators": N_ESTIMATORS, "seed": SEED, "secs": round(time.time() - t, 1), "tabpfn": getattr(tabpfn, "__version__", "?"),
           "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0), "predictions": stats,
           "top5": [{"name": r.display_name, "pos": r.pos, "pred_own": round(float(r.pred_own), 2)} for r in out.nlargest(5, "pred_own").itertuples()]}
    Path(str(a.out) + ".receipt.json").write_text(json.dumps(rec, indent=1, default=str))
    print(f"wrote {a.out}: {len(out)} skill players, context {len(ctx)} rows, {rec['secs']} s; pred_own sum {stats['sum']}, max {stats['max']}%")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("lags"); g.add_argument("--season", type=int, required=True); g.add_argument("--week", type=int, required=True)
    g.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("features"); f.add_argument("--season", type=int, required=True); f.add_argument("--week", type=int, required=True)
    f.add_argument("--frame", type=Path, required=True); f.add_argument("--lags", type=Path, required=True)
    f.add_argument("--linestar-dir", type=Path, required=True); f.add_argument("--history", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True); f.add_argument("--max-age-hours", type=float, default=30.0)
    f.add_argument("--now", help="tests: the current time, ISO with offset")
    t = sub.add_parser("fit"); t.add_argument("--rows", type=Path, required=True); t.add_argument("--rows-2026", type=Path)
    t.add_argument("--features", type=Path, required=True); t.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    return {"lags": cmd_lags, "features": cmd_features, "fit": cmd_fit}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
