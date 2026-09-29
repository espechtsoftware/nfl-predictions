"""G3/G4: per-season splits, bank-to-bank replication and bootstrap flip rates of the L-series paired verdicts.

Rule replicated from scripts/l17_report.py (REL=0.05):
  SUPPORTED  iff sum_a >= 1.05*sum_b AND a>=b in every season AND paired wins > losses
  HARMFUL    iff sum_a <= 0.95*sum_b AND a<=b in every season AND losses > wins
  else NEUTRAL (L13's V2 uses the same SUPPORTED test, else NOT SUPPORTED)
Two bootstraps, 2,000 draws each, seed 0:
  (i)  resample the 72 slate-banks with replacement (as asked);
  (ii) resample the 36 slates with replacement keeping both banks of a slate together (banks share the slate's realized field, so the slate is the independent unit).
Single-threaded numpy on 72-row frames.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("res")
REL = 0.05
DRAWS = 2000
rng = np.random.default_rng(0)


def load(d):
    rows = []
    for f in sorted(glob.glob(str(RES / d / "results_bank*.jsonl"))):
        for line in open(f):
            o = json.loads(line)
            if "result" in o:
                rows.append(o["result"])
    return pd.DataFrame(rows).drop_duplicates(["bank", "season", "week"], keep="last").reset_index(drop=True)


def verdict(df, a, b):
    ta, tb = df[a].sum(), df[b].sum()
    seas = {y: (df.loc[df.season == y, a].sum(), df.loc[df.season == y, b].sum()) for y in sorted(df.season.unique())}
    d = df[a] - df[b]
    w, l = int((d > 0).sum()), int((d < 0).sum())
    if ta >= (1 + REL) * tb and all(x >= y for x, y in seas.values()) and w > l:
        return "SUPPORTED"
    if ta <= (1 - REL) * tb and all(x <= y for x, y in seas.values()) and l > w:
        return "HARMFUL"
    return "NEUTRAL"


COMPARISONS = [
    # (panel, label, a_col, b_col)
    ("l09", "L09 MEAN vs EMAX t89 (K144)", "K144_MEAN_tickets89", "K144_EMAX_tickets89"),
    ("l09", "L09 PLF89 vs MEAN t89 (K144)", "K144_PLF89_tickets89", "K144_MEAN_tickets89"),
    ("l09", "L09 COVF89 vs MEAN t89 (K144)", "K144_COVF89_tickets89", "K144_MEAN_tickets89"),
    ("l10", "L10 CAP5 vs CAP4 MEAN t89 (K144)", "CAP5_K144_MEAN_tickets89", "CAP4_K144_MEAN_tickets89"),
    ("l10", "L10 (co) CAP4 MEAN vs EMAX t89", "CAP4_K144_MEAN_tickets89", "CAP4_K144_EMAX_tickets89"),
    ("l11", "L11 swap vs keep MEAN t89", "MEAN_tickets89_swap", "MEAN_tickets89_keep"),
    ("l11", "L11 (co) swap vs keep EMAX t89", "EMAX_tickets89_swap", "EMAX_tickets89_keep"),
    ("l12", "L12 T10 vs MEAN t89", "T10_tickets89", "MEAN_tickets89"),
    ("l12", "L12 (co) T20 vs MEAN t89", "T20_tickets89", "MEAN_tickets89"),
    ("l13", "L13 PMO_X50 vs MEAN t89", "PMO_X50_tickets89", "MEAN_tickets89"),
    ("l13", "L13 PMO vs MEAN t89", "PMO_tickets89", "MEAN_tickets89"),
    ("l13", "L13 PMO_X50 vs MEAN t99", "PMO_X50_tickets99", "MEAN_tickets99"),
    ("l13", "L13 PMO_X50 vs EMAX t99", "PMO_X50_tickets99", "EMAX_tickets99"),
    ("l13", "L13 PMO_X50 vs PMO t99", "PMO_X50_tickets99", "PMO_tickets99"),
    ("l13", "L13 (co) MEAN vs EMAX t89", "MEAN_tickets89", "EMAX_tickets89"),
    ("l14", "L14 EMPP99 vs MEAN t99", "EMPP99_tickets99", "MEAN_tickets99"),
    ("l14", "L14 SIMP99 vs MEAN t99", "SIMP99_tickets99", "MEAN_tickets99"),
    ("l14", "L14 EMPP998 vs MEAN t99.8", "EMPP998_tickets99.8", "MEAN_tickets99.8"),
    ("l14", "L14 (co) EMPP99 vs MEAN t89", "EMPP99_tickets89", "MEAN_tickets89"),
    ("l17", "L17 X67 vs X50 t89", "X67_tickets89", "X50_tickets89"),
    ("l17", "L17 X80 vs X50 t89", "X80_tickets89", "X50_tickets89"),
    ("l17", "L17 X100 vs X50 t89", "X100_tickets89", "X50_tickets89"),
    ("l17", "L17 X67 vs X50 t99", "X67_tickets99", "X50_tickets99"),
    ("l18", "L18 X40 vs X50 t89", "X40_tickets89", "X50_tickets89"),
    ("l18", "L18 X33 vs X50 t89", "X33_tickets89", "X50_tickets89"),
    ("l18", "L18 X25 vs X50 t89", "X25_tickets89", "X50_tickets89"),
    ("l18", "L18 X40 vs X50 t99", "X40_tickets99", "X50_tickets99"),
]

frames = {}
out_rows = []
for panel, label, a, b in COMPARISONS:
    df = frames.setdefault(panel, load(panel))
    v0 = verdict(df, a, b)
    ta, tb = int(df[a].sum()), int(df[b].sum())
    seas = {int(y): (int(df.loc[df.season == y, a].sum()), int(df.loc[df.season == y, b].sum())) for y in sorted(df.season.unique())}
    d = df[a] - df[b]
    w, l, t = int((d > 0).sum()), int((d < 0).sum()), int((d == 0).sum())
    sign = {y: np.sign(x - z) for y, (x, z) in seas.items()}
    agree = len(set(sign.values())) == 1
    # per-bank replication of the sign of the aggregate difference
    banks = {int(bk): int(df.loc[df.bank == bk, a].sum() - df.loc[df.bank == bk, b].sum()) for bk in sorted(df.bank.unique())}
    # (i) slate-bank bootstrap
    n = len(df)
    counts_sb = {"SUPPORTED": 0, "HARMFUL": 0, "NEUTRAL": 0}
    rel_sb = []
    for _ in range(DRAWS):
        idx = rng.integers(0, n, n)
        s = df.iloc[idx]
        counts_sb[verdict(s, a, b)] += 1
        rel_sb.append(s[a].sum() / max(s[b].sum(), 1) - 1)
    # (ii) slate-cluster bootstrap (both banks of a slate move together)
    keys = df[["season", "week"]].drop_duplicates().values.tolist()
    groups = {tuple(k): df[(df.season == k[0]) & (df.week == k[1])] for k in keys}
    m = len(keys)
    counts_sl = {"SUPPORTED": 0, "HARMFUL": 0, "NEUTRAL": 0}
    rel_sl = []
    for _ in range(DRAWS):
        idx = rng.integers(0, m, m)
        s = pd.concat([groups[tuple(keys[i])] for i in idx])
        counts_sl[verdict(s, a, b)] += 1
        rel_sl.append(s[a].sum() / max(s[b].sum(), 1) - 1)
    rel_sb = np.array(rel_sb)
    rel_sl = np.array(rel_sl)
    out_rows.append({
        "comparison": label, "verdict": v0, "a": ta, "b": tb, "rel": round(ta / max(tb, 1) - 1, 3),
        "2023": f"{seas.get(2023, ('-', '-'))[0]} vs {seas.get(2023, ('-', '-'))[1]}",
        "2024": f"{seas.get(2024, ('-', '-'))[0]} vs {seas.get(2024, ('-', '-'))[1]}",
        "seasons_agree_sign": agree, "paired_W-L-T": f"{w}-{l}-{t}",
        "bank_diffs": banks,
        "sb_boot_same_verdict": round(counts_sb[v0] / DRAWS, 3), "sb_boot_SUPP": round(counts_sb["SUPPORTED"] / DRAWS, 3),
        "sb_boot_HARM": round(counts_sb["HARMFUL"] / DRAWS, 3), "sb_boot_NEUT": round(counts_sb["NEUTRAL"] / DRAWS, 3),
        "sb_rel_90ci": f"[{np.percentile(rel_sb, 5):+.3f}, {np.percentile(rel_sb, 95):+.3f}]",
        "sl_boot_same_verdict": round(counts_sl[v0] / DRAWS, 3), "sl_boot_SUPP": round(counts_sl["SUPPORTED"] / DRAWS, 3),
        "sl_boot_HARM": round(counts_sl["HARMFUL"] / DRAWS, 3), "sl_boot_NEUT": round(counts_sl["NEUTRAL"] / DRAWS, 3),
        "sl_rel_90ci": f"[{np.percentile(rel_sl, 5):+.3f}, {np.percentile(rel_sl, 95):+.3f}]",
        "sl_P(rel>0)": round(float((rel_sl > 0).mean()), 3),
    })

out = pd.DataFrame(out_rows)
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_colwidth", 60)
print(out.to_string(index=False))
out.to_csv(Path(__file__).with_name("bootstrap_verdicts.csv"), index=False)

# X50 control replication across L13 (PMO_X50 K144, not comparable), L17 and L18 (K36 both)
print("\nX50 K36 control per bank (tickets89): L17", {int(bk): int(frames['l17'].loc[frames['l17'].bank == bk, 'X50_tickets89'].sum()) for bk in sorted(frames['l17'].bank.unique())},
      "L18", {int(bk): int(frames['l18'].loc[frames['l18'].bank == bk, 'X50_tickets89'].sum()) for bk in sorted(frames['l18'].bank.unique())})
a = frames["l17"].set_index(["season", "week", "bank"])["X50_tickets89"]
b = frames["l18"].set_index(["season", "week", "bank"])["X50_tickets89"]
a2 = frames["l17"].groupby(["season", "week"])["X50_tickets89"].sum()
b2 = frames["l18"].groupby(["season", "week"])["X50_tickets89"].sum()
print("X50 per-slate (2 banks summed) L17 vs L18: corr", round(float(np.corrcoef(a2.values, b2.values)[0, 1]), 3),
      "mean abs diff", round(float(np.abs(a2.values - b2.values).mean()), 2), "identical slates", int((a2.values == b2.values).sum()), "of", len(a2))
print("X50 per-slate-bank mean", round(float(a.mean()), 2), "sd", round(float(a.std()), 2), "zeros L17", int((a == 0).sum()), "zeros L18", int((b == 0).sum()))
# per-slate-bank difference SD for the L17 primary, to describe the noise floor
for panel, a_, b_ in [("l17", "X67_tickets89", "X50_tickets89"), ("l18", "X40_tickets89", "X50_tickets89"), ("l13", "PMO_X50_tickets89", "MEAN_tickets89")]:
    d = frames[panel][a_] - frames[panel][b_]
    print(panel, a_, "-", b_, "per-slate-bank diff mean", round(float(d.mean()), 3), "sd", round(float(d.std()), 3), "se(sum over 72)", round(float(d.std() * np.sqrt(len(d))), 1))
