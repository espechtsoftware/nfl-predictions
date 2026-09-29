"""Shared loaders for the Theme B / D funnel analysis (read-only; single-threaded)."""
import os, re, csv, json
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
W1 = "/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01"
W2 = "/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/results/live/2026-w02"
W3 = "/home/erich/projects/.nfl2-worktrees/week3-live-center/results/live/2026-w03"
RUNS = {
    1: dict(sat=f"{W1}/20260912T204921889774Z-e7255e9",      # Saturday 20:49Z D3200 K90
            sun910=f"{W1}/20260913T141704065300Z-e7255e9",   # Sunday 09:17 CT D800 K90
            t70=f"{W1}/20260913T155648476725Z-e7255e9",      # Sunday 10:56 CT D800 K90 (T-70)
            final=f"{W1}/20260913T160405364118Z-e7255e9",    # Sunday 11:04 CT D800 K90, the entered source
            entered="/home/erich/week1-sunday/ENTERED/DKEntriesAFTERWITHDRAW.csv",
            milly="193028206", cash=166.36, dg=151307),
    2: dict(sat=f"{W2}/20260919T153008787414Z-2dc116c",      # Saturday 15:30Z D12800 K97, the entered source
            sun1030=f"{W2}/20260920T103006928913Z-2dc116c",  # Sunday 05:30 CT D6400
            sun910=f"{W2}/20260920T141013129933Z-2dc116c",   # Sunday 09:10 CT D3200
            t70=f"{W2}/20260920T155005557498Z-2dc116c",      # Sunday 10:50 CT D800 (T-70)
            entered="/home/erich/week2-sunday/ENTER/ENTER-all-rows-1-to-97-are-the-KEEPERS.csv",  # the DKEntries-2026-09-17b export is the reservation file (one placeholder lineup)
            milly="195648007", cash=137.98, dg=153428),
    3: dict(sat=f"{W3}/20260926T153408285093Z-65305f5",      # Saturday 15:34Z D12800 K144, the entered source
            sun910=f"{W3}/20260927T141021390603Z-65305f5",   # Sunday 09:10 CT D3200
            t70=f"{W3}/20260927T155027472554Z-65305f5",      # Sunday 10:50 CT D800 (T-70)
            entered="/home/erich/week3-sunday/ENTER/ENTER-all-rows-1-to-204-are-the-KEEPERS.csv",
            milly="195905122", cash=149.30, dg=153769),
}
FIELD = {1: dict(mean=142.07, top1=218.26, top1_line=209.04, p50=141.74),
         2: dict(mean=115.55, top1=188.97, top1_line=179.78, p50=113.82),
         3: dict(mean=128.47, top1=196.03, top1_line=188.20, p50=127.02)}
SKILL = ("QB", "RB", "WR", "TE")

_own = None
def realized_tables():
    global _own
    if _own is None:
        o = pd.read_csv(os.path.join(DATA, "contest_ownership_2026.csv"))
        o = o[o.week <= 3]
        by_name = o.groupby(["week", "display_name"]).fpts.max()
        milly = o[o.contest_id.astype(str).isin([RUNS[w]["milly"] for w in RUNS])]
        own = milly.groupby(["week", "display_name"]).pct_drafted.sum()   # per-slot rows summed per player
        a = pd.read_csv(os.path.join(DATA, "actuals_2026.csv"))
        by_gsis = a.groupby(["week", "gsis_id"]).dk_points.max()
        _own = (by_name, by_gsis, own)
    return _own

def load_frame(run):
    f = pd.read_parquet(os.path.join(run, "frame.parquet")).reset_index(drop=True)
    f["id"] = f["id"].astype(str)
    return f

def attach_realized(f, week):
    by_name, by_gsis, own = realized_tables()
    r1 = np.array([by_name.get((week, str(n)), np.nan) for n in f.display_name], float)
    r2 = np.array([by_gsis.get((week, str(g)), np.nan) for g in f.gsis_id], float)
    f = f.copy()
    f["real_src"] = np.where(~np.isnan(r1), "dk", np.where(~np.isnan(r2), "nflverse", "none"))
    f["realized"] = np.where(~np.isnan(r1), r1, np.where(~np.isnan(r2), r2, 0.0))
    f["field_own"] = [own.get((week, str(n)), 0.0) for n in f.display_name]
    return f

def load_cands(run, f):
    c = pd.read_parquet(os.path.join(run, "candidates.parquet"))
    idx = {k: i for i, k in enumerate(f["id"])}
    rix = np.array([[idx[p] for p in s.split(",")] for s in c.players])
    c["fam"] = c.tag.astype(str).str.extract(r"^([a-z_]+)")[0].fillna(c.tag.astype(str))
    return c, rix

def lineup_stats(rix, f):
    """Per-lineup: realized sum, proj sum, proj_tourney sum, stack depth, bring-back, games."""
    R = f.realized.to_numpy(float); P = f.proj.to_numpy(float); PT = f.proj_tourney.to_numpy(float)
    pos = f.pos.to_numpy(); team = f.team.to_numpy(); game = f.game_id.to_numpy(); sal = f.salary.to_numpy(float)
    out = dict(realized=R[rix].sum(1), proj=P[rix].sum(1), proj_t=PT[rix].sum(1), salary=sal[rix].sum(1))
    depth = np.zeros(len(rix), int); depth_rb = np.zeros(len(rix), int); bb = np.zeros(len(rix), int); ng = np.zeros(len(rix), int)
    for i, row in enumerate(rix):
        p = pos[row]; t = team[row]; g = game[row]
        q = np.where(p == "QB")[0]
        if len(q):
            qt = t[q[0]]; qg = g[q[0]]
            depth[i] = int(((t == qt) & np.isin(p, ["WR", "TE"])).sum())
            depth_rb[i] = int(((t == qt) & np.isin(p, ["WR", "TE", "RB"])).sum())
            bb[i] = int(((g == qg) & (t != qt) & np.isin(p, SKILL)).sum())
        ng[i] = len(set(g[np.isin(p, SKILL) | (p == "DST")]))
    out.update(depth=depth, depth_rb=depth_rb, bringback=bb, games=ng)
    return pd.DataFrame(out)

def entered_rows(week, f):
    """Entered lineups as frame row indices (9 per row), mapped by DK draftable id."""
    p = RUNS[week]["entered"]
    lineups = []
    if week in (2, 3):
        df = pd.read_csv(p, dtype=str).dropna(subset=["QB"])
        for _, r in df.iterrows():
            lineups.append([str(x) for x in r.iloc[0:9]])
    else:
        with open(p, newline="") as fh:
            rd = csv.reader(fh); next(rd)
            for line in rd:
                if len(line) < 13 or not line[4].strip():
                    continue
                ids = []
                for cell in line[4:13]:
                    m = re.search(r"\((\d+)\)\s*$", cell)
                    ids.append(m.group(1) if m else cell.strip())
                lineups.append(ids)
    idx = {str(k): i for i, k in enumerate(f.dk_draftable_id.astype(str))}
    rix = np.array([[idx[i] for i in l] for l in lineups])
    # W1/W2 files carry one row per entry; collapse to distinct lineups
    keys = ["|".join(sorted(l)) for l in lineups]
    seen = set(); keep = []
    for i, k in enumerate(keys):
        if k not in seen:
            seen.add(k); keep.append(i)
    return rix[keep]

def topk_by_mean(rix, score, K, max_shared=7):
    order = np.argsort(-score)
    chosen = []
    sets = []
    for i in order:
        s = set(rix[i])
        if all(len(s & t) <= max_shared for t in sets):
            chosen.append(i); sets.append(s)
            if len(chosen) >= K:
                break
    return np.array(chosen)

SLOT = re.compile(r"\b(QB|RB|WR|TE|FLEX|DST)\s+")
def parse_field_lineup(s):
    p = SLOT.split(s.strip())
    return [p[i + 1].strip() for i in range(1, len(p) - 1, 2) if p[i + 1].strip()]

def field_sample(week):
    d = pd.read_csv(os.path.join(DATA, "field_lineups_sample.csv"))
    d = d[d.week == week].copy()
    d["names"] = d.lineup.map(parse_field_lineup)
    return d
