"""Player-level walk-forward screen: does a kNN 'boom-similarity' score carry information about realized 30+/40+
games BEYOND the projection's own tail?  Player-level outcomes only (allowed walk-forward); no lineup result is read.
Seasons: history = all k1 slates of seasons < S; scored season S in (2021, 2022, 2023, 2024).  Same-position kNN
(K=100) on standardized point-in-time features (median-imputed per position on the history only)."""
import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from scipy.optimize import minimize
from scipy.stats import rankdata

def knn_indices(Xh, Xc, k):
    """Indices of the k nearest history rows for each query row (euclidean, chunked, numpy only)."""
    out = np.empty((len(Xc), k), dtype=np.int64); hh = (Xh ** 2).sum(axis=1)
    for a in range(0, len(Xc), 512):
        q = Xc[a:a + 512]; d = hh[None, :] - 2.0 * q @ Xh.T + (q ** 2).sum(axis=1)[:, None]
        out[a:a + 512] = np.argpartition(d, k - 1, axis=1)[:, :k]
    return out

def roc_auc_score(y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float); r = rankdata(s); n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

def log_loss(y, p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6); y = np.asarray(y); return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())

class LogisticRegression:
    def __init__(self, max_iter=2000, C=1.0): self.C = C
    def fit(self, X, y):
        X = np.asarray(X, dtype=float); y = np.asarray(y, dtype=float); self.mu = X.mean(axis=0); self.sd = X.std(axis=0) + 1e-9
        Z = (X - self.mu) / self.sd; n, d = Z.shape
        def f(w):
            z = Z @ w[:-1] + w[-1]; p = 1 / (1 + np.exp(-z)); reg = 0.5 / self.C * (w[:-1] ** 2).sum()
            ll = -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1))).sum() + reg
            g = np.append(Z.T @ (p - y) + w[:-1] / self.C, (p - y).sum()); return ll, g
        self.w = minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B").x; self.coef_ = self.w[None, :-1]; return self
    def predict_proba(self, X):
        Z = (np.asarray(X, dtype=float) - self.mu) / self.sd; p = 1 / (1 + np.exp(-(Z @ self.w[:-1] + self.w[-1]))); return np.column_stack([1 - p, p])
from nfl2.data import slates
from nfl2.pipeline import slate_frame

FEATS = ["salary", "mean_projection", "proj_p90", "proj_p10", "proj_std", "market_points", "proj_tourney", "own_est", "target_share_l4", "carry_share_l4",
         "snap_share_l4", "target_share_last", "carry_share_last", "snap_share_last", "target_share_jump", "dk_points_l4", "dk_points_std", "dk_points_vol",
         "implied_team_total", "spread", "game_total", "depth_rank", "games_played_prior", "xfp_l4", "wopr_l4", "air_yards_share_l4", "rz20_target_share_l4",
         "rz10_targets_l4", "gl3_carries_l4", "targets_l4", "carries_l4", "yards_per_target_l8", "adot_l8", "expected_plays", "pass_rate_l4", "pace_l4",
         "proe_l4", "qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6", "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6", "epa_per_dropback_allowed_l6",
         "epa_per_rush_allowed_l6", "practice_level", "team_top2_target_share_l6", "qb_cpoe_l6", "separation_l4", "ez_targets_l4", "deep_targets_l4",
         "salary_delta_wow", "team_vacated_target_share", "component_mean_targets", "component_mean_carries", "component_mean_rec_tds", "component_mean_rush_tds"]
BASE = ["mean_projection", "proj_p90", "proj_std", "salary", "market_points"]

frames = []
for s, w in slates("k1"):
    fr = slate_frame(s, w); fr = fr[fr.pos.isin(["QB", "RB", "WR", "TE"]) & (fr.salary > 0)].copy(); fr["season"] = s; fr["week"] = w; frames.append(fr)
P = pd.concat(frames, ignore_index=True)
P = P[P.actual.notna() & (pd.to_numeric(P.mean_projection, errors="coerce") >= 3.0)].copy()   # rosterable players only
for c in FEATS: P[c] = pd.to_numeric(P.get(c), errors="coerce")
P["boom30"] = (P.actual >= 30).astype(int); P["boom40"] = (P.actual >= 40).astype(int); P["boom25"] = (P.actual >= 25).astype(int)
print(f"panel rows {len(P)} | seasons {sorted(P.season.unique())} | boom30 rate {P.boom30.mean():.3f} boom40 {P.boom40.mean():.3f}")
K = 100
rows = []
for S in (2021, 2022, 2023, 2024):
    hist = P[P.season < S]; cur = P[P.season == S].copy()
    cur["knn30"] = np.nan; cur["knn40"] = np.nan; cur["knn_mean"] = np.nan
    for pos in ("QB", "RB", "WR", "TE"):
        h = hist[hist.pos == pos]; c = cur[cur.pos == pos]
        if len(h) < K + 10 or len(c) == 0: continue
        med = h[FEATS].median(); Xh = h[FEATS].fillna(med); Xc = c[FEATS].fillna(med)
        mu, sd = Xh.mean(), Xh.std().replace(0, 1.0); Xh = ((Xh - mu) / sd).to_numpy(); Xc = ((Xc - mu) / sd).to_numpy()
        ind = knn_indices(Xh, Xc, K)
        cur.loc[c.index, "knn30"] = h.boom30.to_numpy()[ind].mean(axis=1); cur.loc[c.index, "knn40"] = h.boom40.to_numpy()[ind].mean(axis=1)
        cur.loc[c.index, "knn_mean"] = h.actual.to_numpy()[ind].mean(axis=1)
    cur = cur.dropna(subset=["knn30"]); hist2 = hist.dropna(subset=BASE)
    # walk-forward logistic baselines on prior seasons: projection tail only vs + knn (knn on history computed leave-season-out would be costly; use in-sample history knn as the feature -- approximated by refitting knn within history via one inner split)
    # inner: history's own knn score computed from the earlier part of history
    hist_scored = []
    for S2 in sorted(hist.season.unique())[1:]:
        h0 = hist[hist.season < S2]; c2 = hist[hist.season == S2].copy(); c2["knn30"] = np.nan
        for pos in ("QB", "RB", "WR", "TE"):
            h = h0[h0.pos == pos]; c = c2[c2.pos == pos]
            if len(h) < K + 10 or len(c) == 0: continue
            med = h[FEATS].median(); Xh = h[FEATS].fillna(med); Xc = c[FEATS].fillna(med); mu, sd = Xh.mean(), Xh.std().replace(0, 1.0)
            ind = knn_indices(((Xh - mu) / sd).to_numpy(), ((Xc - mu) / sd).to_numpy(), K)
            c2.loc[c.index, "knn30"] = h.boom30.to_numpy()[ind].mean(axis=1)
        hist_scored.append(c2.dropna(subset=["knn30"]))
    H = pd.concat(hist_scored).dropna(subset=BASE) if hist_scored else None
    for target in ("boom30", "boom40"):
        y = cur[target].to_numpy(); out = {"season": S, "target": target, "n": len(cur), "booms": int(y.sum())}
        out["auc_proj_p90"] = roc_auc_score(y, cur.proj_p90.fillna(0)); out["auc_mean_proj"] = roc_auc_score(y, cur.mean_projection); out["auc_knn"] = roc_auc_score(y, cur["knn30" if target == "boom30" else "knn40"])
        if H is not None and len(H) > 500:
            Xb_h = H[BASE].to_numpy(); Xb_c = cur[BASE].fillna(cur[BASE].median()).to_numpy(); yh = H[target].to_numpy()
            if yh.sum() >= 20:
                lb = LogisticRegression(max_iter=2000, C=1.0).fit(Xb_h, yh); pb = lb.predict_proba(Xb_c)[:, 1]
                lk = LogisticRegression(max_iter=2000, C=1.0).fit(np.column_stack([Xb_h, H.knn30.to_numpy()]), yh); pk = lk.predict_proba(np.column_stack([Xb_c, cur.knn30.to_numpy()]))[:, 1]
                out["auc_base_logit"] = roc_auc_score(y, pb); out["auc_base_plus_knn"] = roc_auc_score(y, pk)
                out["logloss_base"] = log_loss(y, pb); out["logloss_plus_knn"] = log_loss(y, pk); out["knn_coef"] = float(lk.coef_[0][-1])
        # precision among the top decile by each score (the players a lineup would actually use)
        top = max(1, len(cur) // 10)
        for name, sc in (("proj_p90", cur.proj_p90.fillna(0)), ("knn", cur["knn30" if target == "boom30" else "knn40"])):
            idx = np.argsort(-sc.to_numpy())[:top]; out[f"top10pct_boomrate_{name}"] = float(y[idx].mean())
        rows.append(out)
R = pd.DataFrame(rows); pd.set_option("display.width", 250)
print(R.round(4).to_string(index=False))
R.to_csv("/home/erich/week1-sunday/knn_boom_screen_results.csv", index=False)
