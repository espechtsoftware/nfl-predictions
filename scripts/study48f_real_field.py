#!/usr/bin/env python3
"""Study 48f (DRAFT, reports/2026-10-07-prereg-study48f-real-field-refit-DRAFT.md): the winner-likeness score refit on the
REAL 2026 Millionaire fields, graded prospectively from Week 5 with the WEEK as the unit.

    python scripts/study48f_real_field.py census --weeks 1,2,3,4          # outcome-blind counts (band, labels, dropped)
    python scripts/study48f_real_field.py fit --weeks 1,2,3,4 --out M.json  # the frozen SE / FULL fit (decision models)
    python scripts/study48f_real_field.py read --model M.json --weeks 5,6,7,8

Rows: every non-ours entrant of the week's Millionaire, resolved to the week's T-70 frame (others dropped, counted).
Features (pre-lock only): STRUCT + ENV + OWN (= SE) and SE + FACTS (= FULL) -- the frozen study-48 features
(`nfl_dfs.inference.winner_like`) plus the outside reviewer's environment facts (the QB's game-total RANK class, favourite,
the top-total-game count class, a cheap DST). The band: the top 20% of the field by the lineup's pre-lock projection
(ours W1-3, FP W4 on). The label: the real top 1% of the whole field. Two L2 logistic regressions (C = 1.0) on the
band's rows, standardized on the training rows. Private inputs (the real fields) are read from the money gate's cache;
outputs carry counts, coefficients and AUCs only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nfl_dfs.inference import winner_like as W          # noqa: E402

STRUCT = ("mates", "bringback", "rb_mate", "in_qb_game", "top_game", "salary")
ENV = ("qb_implied", "qb_spread", "qb_game_total", "qb_rank_top", "qb_rank_2_3", "qb_fav", "top_n_0", "top_n_1_2", "dst_cheap")
OWN = ("own_rank",)
FACTS = ("rz_targets", "ez_targets", "gl_carries", "target_share", "carry_share", "snap_share", "wopr", "route_share",
         "vacated", "td_l4", "td_l8", "qb_pass_td_l4", "qb_att_l4")
SE = STRUCT + ENV + OWN
FULL = SE + FACTS
SE_NOOWN = STRUCT + ENV                                  # descriptive: SE without the ownership feature
BAND = 0.20
BAND5 = 0.05                                             # descriptive: closer to our rows, few labels
C = 1.0
CANDIDATE_WEEKS = (5, 6, 7, 8, 9)                        # W5-W8 graded; W9 only as the one replacement
GRADED = 4
RESOLVED_FLOOR = 0.90                                    # a valid week resolves >= 90% of the field's non-ours entries
MIN_BAND_LABELS = 50                                     # ... and holds >= 50 top-1% labels in the 20% band
BOOT_B, BOOT_SEED = 20_000, 20261048                     # descriptive lineup bootstrap (assumes independent lineups)
MONKEYS, MONKEY_SEED = 10_000, 20261049                  # descriptive monkeys test


def env_features(L: np.ndarray, A: dict, game_total_rank: dict, top_game: str | None, dst_sal: np.ndarray) -> pd.DataFrame:
    """The outside reviewer's environment classes (pre-lock): the QB's game total rank (1 / 2-3 / other), favourite
    (spread < 0), players from the top-total game (0 / 1-2 / 3+), a DST priced under 3,500."""
    pos, game = A["pos"][L], A["game"][L]
    q = (pos == "QB").argmax(axis=1); r = np.arange(len(L))
    qrank = np.array([game_total_rank.get(g, 99) for g in game[r, q]])
    nodst = pos != "DST"
    top_n = (nodst & (game == top_game)).sum(axis=1) if top_game is not None else np.zeros(len(L))
    dst = (pos == "DST").argmax(axis=1)
    return pd.DataFrame({"qb_rank_top": (qrank == 1).astype(float), "qb_rank_2_3": ((qrank >= 2) & (qrank <= 3)).astype(float),
                         "qb_fav": (A["spread"][L][r, q] < 0).astype(float),
                         "top_n_0": (top_n == 0).astype(float), "top_n_1_2": ((top_n >= 1) & (top_n <= 2)).astype(float),
                         "dst_cheap": (dst_sal[L][r, dst] < 3500).astype(float)})


def band_mask(proj_sum: np.ndarray, share: float = BAND) -> np.ndarray:
    """The top `share` of the field by pre-lock projection (ties at the cut included)."""
    return proj_sum >= np.quantile(proj_sum, 1.0 - share)


def auc(score: np.ndarray, y: np.ndarray) -> float | None:
    y = np.asarray(y, bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if not n1 or not n0:
        return None
    r = pd.Series(score).rank().to_numpy()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def top1_label(ranks: np.ndarray, n_all: int) -> np.ndarray:
    """The real top 1% of the WHOLE field (n_all = every entry, ours included), never of the resolved rows."""
    return np.asarray(ranks) <= max(1, int(round(0.01 * n_all)))


def week_validity(meta: dict, band_labels: int | None) -> tuple[bool, list[str]]:
    """A graded week counts only if: its T-70 frame and FP projections were read, a pre-lock ownership file existed,
    >= RESOLVED_FLOOR of the field's non-ours entries resolved to the frame, and the 20% band holds >= MIN_BAND_LABELS
    top-1% labels. Returns (valid, reasons)."""
    why = []
    if not meta.get("frame_present"):
        why.append("no T-70 frame")
    if not meta.get("fp_proj_present"):
        why.append("no FP projection file")
    if meta.get("own_source", "none") == "none":
        why.append("no pre-lock ownership file")
    share = meta.get("resolved_share")
    if share is None or share < RESOLVED_FLOOR:
        why.append(f"resolved share {share} < {RESOLVED_FLOOR}")
    if band_labels is None or band_labels < MIN_BAND_LABELS:
        why.append(f"band labels {band_labels} < {MIN_BAND_LABELS}")
    return not why, why


def pick_weeks(validity: dict[int, bool]) -> list[int]:
    """The graded weeks: the first GRADED valid weeks of CANDIDATE_WEEKS in order (W9 can only replace an invalid week)."""
    return [w for w in CANDIDATE_WEEKS if validity.get(w)][:GRADED]


def decide(aucs: list[float | None]) -> str:
    """The frozen rule (revision 1): the WEEK is the unit -- PASS if the AUC > .50 in every graded week, WORSE if < .50
    in every one, NO PASS otherwise (fewer than four valid weeks: INCOMPLETE)."""
    vals = [a for a in aucs if a is not None]
    if len(vals) < 4:
        return "INCOMPLETE"
    if all(a > 0.5 for a in vals):
        return "PASS"
    if all(a < 0.5 for a in vals):
        return "WORSE"
    return "NO PASS"


def week_weights(weeks: np.ndarray) -> np.ndarray:
    """Equal weight per training week (the reviewer, 10-07; the week is the unit in grading too): each row weighs
    1 / (its week's band rows), normalized so the weights sum to the row count. W1's field is ~5x the others'."""
    weeks = np.asarray(weeks)
    counts = pd.Series(weeks).value_counts()
    w = 1.0 / pd.Series(weeks).map(counts).to_numpy(float)
    return w * (len(w) / w.sum())


def fit_models(X: pd.DataFrame, y: np.ndarray, weights: np.ndarray | None = None) -> dict:
    """The three frozen models (SE, FULL decision-bearing; SE_NOOWN descriptive), with the week-equal weights in the
    standardization (weighted mean / sd; a missing value = the weighted training mean) and in the logistic fit."""
    from sklearn.linear_model import LogisticRegression
    wts = np.ones(len(X)) if weights is None else np.asarray(weights, float)
    out = {}
    for name, cols in (("SE", SE), ("FULL", FULL), ("SE_NOOWN", SE_NOOWN)):
        Z = X[list(cols)].to_numpy(float)
        ok = ~np.isnan(Z)
        mu = np.array([np.average(Z[ok[:, j], j], weights=wts[ok[:, j]]) if ok[:, j].any() else 0.0 for j in range(Z.shape[1])])
        Z = np.where(np.isnan(Z), mu, Z)
        sd = np.sqrt(np.average((Z - mu) ** 2, axis=0, weights=wts))
        sd = np.where(sd > 0, sd, 1.0)
        m = LogisticRegression(C=C, max_iter=2000).fit((Z - mu) / sd, y, sample_weight=wts)
        out[name] = {"features": list(cols), "mu": mu.tolist(), "sd": sd.tolist(),
                     "beta": [float(m.intercept_[0])] + [float(b) for b in m.coef_[0]]}
    return out


def score(model: dict, X: pd.DataFrame) -> np.ndarray:
    mu = np.asarray(model["mu"])
    Z = X[model["features"]].to_numpy(float)
    Z = (np.where(np.isnan(Z), mu, Z) - mu) / np.asarray(model["sd"])
    b = np.asarray(model["beta"])
    return b[0] + Z @ b[1:]


# --------------------------------------------------------------------------------------------- the real-field loader
def load_week_rows(w: int) -> tuple[pd.DataFrame, dict]:
    """One row per resolved non-ours Millionaire entrant of week w: the features, the projection sum, the label."""
    spec = importlib.util.spec_from_file_location("MS", ROOT / "scripts" / "moneygate_score.py")
    MS = importlib.util.module_from_spec(spec); sys.modules["MS"] = MS; spec.loader.exec_module(MS)
    import winner_like_inputs as WI
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    cfg = MS.load_config()
    e = cfg["weeks"][str(w)]
    Wk = MS.load_week(cfg, w); cid = MS.milly_cid(Wk)
    field = Wk.field[(Wk.field.contest_id == cid) & ~Wk.field.entry_id.isin(Wk.ours)].reset_index(drop=True)
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet"); fr["id"] = fr["id"].astype(str)
    own_src = {3: (Path.home() / "moneygate/inputs/own/w3_ownership_sets.csv", "gsis_id"),
               4: (Path.home() / "moneygate/inputs/own/w4_ownership_fp.csv", "id")}
    if e.get("own_48f"):                                   # weeks 5+: the week's FP export, named in the money gate's config
        own_src[w] = (Path(e["own_48f"][0]), e["own_48f"][1])
    if w in own_src and own_src[w][0].is_file():
        o = pd.read_csv(own_src[w][0], dtype={own_src[w][1]: str}).rename(columns={own_src[w][1]: "id"})[["id", "pred_own"]]
    else:
        o = pd.DataFrame({"id": fr["id"], "pred_own": np.nan})
    lags = query_df(WI.LAG_SQL.format(features=settings.features), {"season": 2026, "week": w})
    inp = WI.build(fr, o, lags).drop_duplicates("id").set_index("id")
    cols = list(dict.fromkeys(["pos", "team", "opp", "game_id", "salary", "game_total", *[c for c in W.FRAME_FACTS if c in fr.columns]]))
    P = fr.drop_duplicates("id").set_index("id")[cols].join(inp[["own_proj", *W.LAG_COLUMNS]])
    proj = pd.to_numeric(fr.drop_duplicates("id").set_index("id").reindex(P.index).mean_projection, errors="coerce").fillna(0.0)
    if e.get("fp_proj_source") and Path(e["fp_proj_source"]).is_file():          # the projection we played (FP from W4)
        fp = pd.read_csv(e["fp_proj_source"])
        m = dict(zip(fp.dk_draftable_id.astype("Int64").astype(str), pd.to_numeric(fp.fp, errors="coerce")))
        dd = fr.drop_duplicates("id").set_index("id").reindex(P.index).dk_draftable_id.astype("Int64").astype(str).map(m)
        proj = pd.Series(np.where(dd.notna(), dd, proj), index=P.index)
    canon = {MS.canon(n): i for i, n in zip(fr["id"], fr.display_name)}
    dup = {n for n, c in fr.display_name.map(MS.canon).value_counts().items() if c > 1}
    at = {p: k for k, p in enumerate(P.index)}
    keep, L = [], []
    for j, names in enumerate(field.names):
        ids = [canon.get(n) for n in names]
        if len(ids) != 9 or any(i is None for i in ids) or any(n in dup for n in names):
            continue
        keep.append(j); L.append([at[i] for i in ids])
    L = np.array(L); f = field.iloc[keep].reset_index(drop=True)
    pos = P.pos.astype(str).to_numpy()
    ok = (pos[L] == "QB").sum(axis=1) == 1
    L, f = L[ok], f[ok].reset_index(drop=True)
    A = W.slate_arrays(P.reset_index(drop=True), W.game_top(P))
    own = W.rank_pct(pd.to_numeric(P.own_proj, errors="coerce").fillna(0.0).to_numpy(float), A["pos"])
    if w not in own_src or not own_src[w][0].is_file():
        own = np.full(len(P), np.nan)                       # no pre-lock ownership source: OWN is imputed downstream
    X = W.features(L, A, own, np.zeros(len(P)))
    gt = P[["game_id", "game_total"]].dropna().drop_duplicates("game_id").sort_values(["game_total", "game_id"], ascending=[False, True])
    grank = {str(g): i + 1 for i, g in enumerate(gt.game_id)}
    X = pd.concat([X.reset_index(drop=True), env_features(L, A, grank, W.game_top(P), P.salary.to_numpy(float))], axis=1)
    n_all = len(Wk.field[Wk.field.contest_id == cid])
    X["proj_sum"] = proj.to_numpy(float)[L].sum(axis=1)
    X["top1"] = top1_label(f["rank"].to_numpy(), n_all)
    X["points"] = f["points"].to_numpy()
    has_own = w in own_src and own_src[w][0].is_file()
    meta = {"week": w, "field_entries": int(n_all), "rows_resolved": int(len(X)), "dropped": int(len(field) - len(X)),
            "resolved_share": round(len(X) / max(len(field), 1), 4), "own_source": own_src[w][0].name if has_own else "none",
            "frame": Path(e["t70_run"]).name, "frame_present": (Path(e["t70_run"]) / "frame.parquet").is_file(),
            "fp_proj_present": bool(e.get("fp_proj_source") and Path(e["fp_proj_source"]).is_file())}
    ctx = {"P": P, "A": A, "own": own, "grank": grank, "proj": proj, "fr": fr, "others": np.sort(field.points.to_numpy()),
           "line_top1": float(np.sort(Wk.field[Wk.field.contest_id == cid].points.to_numpy())[::-1][max(1, int(round(0.01 * n_all))) - 1]),
           "e": e, "MS": MS, "Wk": Wk}
    return X, meta, ctx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("census", "fit", "read"):
        s = sub.add_parser(n); s.add_argument("--weeks", required=True)
        if n == "fit":
            s.add_argument("--out", type=Path, required=True)
        if n == "read":
            s.add_argument("--model", type=Path, required=True)
    a = ap.parse_args(argv)
    weeks = [int(x) for x in a.weeks.split(",")]
    if a.cmd == "census":
        for w in weeks:
            X, meta, _ = load_week_rows(w)
            b = band_mask(X.proj_sum.to_numpy())
            feats = [c for c in FULL if c != "own_rank" or meta.get("own_source", "none") != "none"]
            meta.update({"band_rows": int(b.sum()), "band_top1": int(X.top1[b].sum()), "all_top1": int(X.top1.sum()),
                         "band_features_defined": round(float(X.loc[b, feats].notna().all(axis=1).mean()), 4),
                         "band_features_checked": "FULL" if len(feats) == len(FULL) else "FULL without own_rank (no source; imputed at the training mean)",
                         "projection_used": "FP" if meta.get("fp_proj_present") else "ours"})
            print(json.dumps(meta))
        return 0
    if a.cmd == "fit":
        parts = []
        for w in weeks:
            X, meta, _ = load_week_rows(w)
            b = band_mask(X.proj_sum.to_numpy())
            parts.append(X[b].assign(_week=w)); print(json.dumps(meta))
        D = pd.concat(parts, ignore_index=True)
        wts = week_weights(D._week.to_numpy())
        models = fit_models(D, D.top1.to_numpy(), wts)
        rec = {"study": "48f", "weeks": weeks, "band": BAND, "C": C, "rows": int(len(D)), "labels": int(D.top1.sum()),
               "weighting": "week-equal (each row 1 / its week's band rows, normalized to sum to the row count)",
               "week_total_weight": {str(w): round(float(wts[D._week.to_numpy() == w].sum()), 6) for w in weeks},
               "week_rows": {str(w): int((D._week == w).sum()) for w in weeks}, "models": models}
        raw = json.dumps(rec, indent=1, sort_keys=True).encode()
        a.out.write_bytes(raw + b"\n")
        print(f"FIT -> {a.out} sha256 {hashlib.sha256(raw + b'\n').hexdigest()}")
        return 0
    model = json.loads(a.model.read_text())
    rows, metas, ctxs = {}, {}, {}
    for w in sorted(set(range(1, 5)) | set(weeks)):             # W1-W4 feed the descriptive walk-forward refits
        try:
            rows[w], metas[w], ctxs[w] = load_week_rows(w)
        except Exception as exc:                                  # a week that cannot load is invalid, with the reason
            metas[w] = {"week": w, "load_error": f"{type(exc).__name__}: {exc}"}
    validity, lines = {}, {}
    for w in weeks:
        if w not in rows:
            validity[w] = False; lines[w] = {"week": w, "valid": False, "reasons": [metas[w].get("load_error")]}
            continue
        X = rows[w]; b = band_mask(X.proj_sum.to_numpy())
        ok, why = week_validity(metas[w], int(X.top1[b].sum()))
        validity[w] = ok; lines[w] = {"week": w, "valid": ok, "reasons": why, **metas[w], "band_rows": int(b.sum()), "band_top1": int(X.top1[b].sum())}
    graded = pick_weeks(validity)
    print(f"GRADED WEEKS {graded} (candidates {list(CANDIDATE_WEEKS)}; invalid: "
          + ", ".join(f"W{w} {lines[w]['reasons']}" for w in weeks if not validity.get(w)) + ")")
    aucs = {"SE": [], "FULL": []}
    rng = np.random.default_rng(BOOT_SEED)
    for w in graded:
        X = rows[w]; y = X.top1.to_numpy(); b = band_mask(X.proj_sum.to_numpy()); b5 = band_mask(X.proj_sum.to_numpy(), BAND5)
        line = lines[w]
        for name in ("SE", "FULL"):
            s_ = score(model["models"][name], X)
            aucs[name].append(auc(s_[b], y[b])); line[f"auc_{name}"] = aucs[name][-1]
            line[f"desc_auc5_{name}"] = auc(s_[b5], y[b5])
            sb, yb = s_[b], y[b]; n = len(sb)
            boots = [auc(sb[i], yb[i]) for i in (rng.integers(0, n, n) for _ in range(BOOT_B))]
            boots = [x for x in boots if x is not None]
            line[f"desc_boot95_{name}_assumes_independent_lineups"] = [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))] if boots else None
        line["desc_auc_SE_NOOWN"] = auc(score(model["models"]["SE_NOOWN"], X)[b], y[b])
        prior = [rows[v][band_mask(rows[v].proj_sum.to_numpy())].assign(_week=v) for v in sorted(rows) if v < w]
        if prior:                                                 # the walk-forward refit, the frozen recipe on W1..W(w-1)
            D = pd.concat(prior, ignore_index=True)
            wf = fit_models(D, D.top1.to_numpy(), week_weights(D._week.to_numpy()))
            line["desc_auc_SE_walk_forward"] = auc(score(wf["SE"], X)[b], y[b])
        line["desc_monkeys"] = monkeys(model["models"]["SE"], ctxs[w])
        print(json.dumps(line, default=str))
    v = [x for x in aucs["SE"] if x is not None]
    print(f"PRIMARY SE band AUC by graded week {dict(zip(graded, aucs['SE']))}; mean {np.mean(v) if v else float('nan'):.4f} "
          f"sd {np.std(v, ddof=1) if len(v) > 1 else float('nan'):.4f} -> {decide(aucs['SE']) if len(graded) == GRADED else 'INCOMPLETE'}")
    diff = [None if a1 is None or a0 is None else a1 - a0 for a1, a0 in zip(aucs["FULL"], aucs["SE"])]
    print(f"SECONDARY FULL - SE by graded week {diff}: " + ("the player facts add (positive every graded week)"
          if len(diff) == GRADED and all(d is not None and d > 0 for d in diff) else "no gain shown"))
    return 0


def monkeys(model: dict, ctx: dict) -> dict | None:
    """Descriptive: SE's top 26 of the union's candidate pool (its candidates.parquet + the book + the spares) against
    MONKEYS random 26-row draws from the same pool, all scored on the real field (P(>= 1 top-1% row), mean finish).
    The random draws ignore the caps. The pool's union dir is the week's `union_dir_48f` in the money gate's config."""
    e = ctx["e"]
    if not e.get("union_dir_48f") or not (Path(e["union_dir_48f"]) / "candidates.parquet").is_file():
        return None
    ud = Path(e["union_dir_48f"]); fr, P = ctx["fr"], ctx["P"]
    gs = set(P.index)
    dk2g = dict(zip(fr.dk_player_id.astype("Int64").astype(str), fr["id"].astype(str)))
    rows = [[p.strip() for p in str(r).split(",")] for r in pd.read_parquet(ud / "candidates.parquet").players]
    for f in ("book.csv",):
        if (ud / f).is_file():
            rows += [[dk2g.get(x, x) for x in r] for r in pd.read_csv(ud / f, dtype=str).itertuples(index=False)]
    rows = [list(r) for r in {tuple(sorted(r)) for r in rows if len(r) == 9 and all(x in gs for x in r)}]
    if len(rows) < 26:
        return None
    at = {p: k for k, p in enumerate(P.index)}
    L = np.array([[at[x] for x in r] for r in rows])
    ok = (ctx["A"]["pos"][L] == "QB").sum(axis=1) == 1
    L = L[ok]
    X = W.features(L, ctx["A"], ctx["own"], np.zeros(len(P)))
    X = pd.concat([X.reset_index(drop=True), env_features(L, ctx["A"], ctx["grank"], W.game_top(P), P.salary.to_numpy(float))], axis=1)
    sc = score(model, X)
    MS, Wk = ctx["MS"], ctx["Wk"]
    name = dict(zip(fr["id"].astype(str), fr.display_name))
    pts = np.array([sum(Wk.fpts.get(MS.canon(name.get(P.index[i], "")), 0) for i in r) for r in L], np.int64)
    fin = np.searchsorted(ctx["others"], pts, "left") / len(ctx["others"])
    hit = pts >= ctx["line_top1"]
    top = np.argsort(-sc, kind="stable")[:26]
    rng = np.random.default_rng(MONKEY_SEED)
    draws = np.array([rng.choice(len(L), 26, replace=False) for _ in range(MONKEYS)])
    r_hit = hit[draws].any(axis=1).astype(float); r_fin = fin[draws].mean(axis=1)
    pool_sha = hashlib.sha256(json.dumps(sorted(map(sorted, rows))).encode()).hexdigest()
    return {"pool_rows": int(len(L)), "pool_sha256": pool_sha, "se_any_top1": bool(hit[top].any()),
            "random_any_top1_rate": float(r_hit.mean()), "se_mean_finish": float(fin[top].mean()),
            "se_mean_finish_percentile_vs_random": float((r_fin < fin[top].mean()).mean()), "random_draws_ignore_caps": True}


if __name__ == "__main__":
    sys.exit(main())
