"""Weekly outcomes for contest mixes with the 36-row main book, as armed and with the ownership term (rows dealt in rotation).

The mixes are PRIVATE (they are the week's entry counts): MIX_FILE is a JSON outside the repo,
    {"mix name": [["contest type as in 31_expect_by_contest.py", entries, first_row], ...], ...}
"""
import glob
import json
import os

import numpy as np
import pandas as pd

exec(open(os.path.join(os.path.dirname(__file__), "31_expect_by_contest.py")).read().split("rows = []")[0])     # ladders L, types T, slates S, cdf()
rng = np.random.default_rng(20260929)
L["Double-up $10 (top 45% doubles)"] = {"n": 10000, "fee": 10.0, "prize": np.concatenate([[0.0], np.full(4500, 20.0), np.zeros(5501)]), "name": "double-up"}
S1 = {(s["season"], s["week"]): s for s in (json.load(open(f)) for f in sorted(glob.glob("tilt/*.json")))}
S2 = {(s["season"], s["week"]): s for s in (json.load(open(f)) for f in sorted(glob.glob("tilt2/*.json")))}
G = {(s["season"], s["week"]): s for s in S}
keys = sorted(G)
OFF = {k: v[1] for k, v in T.items()}
OFF["Double-up $10 (top 45% doubles)"] = 5.0


def sample_prize(p_below, lad, reps):
    n, pr = lad["n"], lad["prize"]
    if n > 3000:
        return np.full(reps, pr[min(int(np.floor((1 - p_below) * n)) + 1, n)])
    return pr[np.minimum(rng.binomial(n - 1, 1 - p_below, size=reps) + 1, n)]


def run(mix, src, arm, reps=200):
    stake = sum(L[c]["fee"] * n for c, n, _ in mix)
    out = np.zeros((len(keys), reps))
    for si, k in enumerate(keys):
        sc = np.array(src[k]["arms"][arm]["score"])
        for ci, (c, n, _first) in enumerate(mix):
            for j in range(n):
                r = (ci * 5 + int(round(j * 36 / max(n, 1)))) % 36
                out[si] += sample_prize(float(cdf(G[k], sc[r] - OFF.get(c, 0.0))), L[c], reps)
    wk = (out / stake - 1).reshape(-1)
    return {"weeks ahead": (wk > 0).mean(), "weeks that lose half or more": (wk <= -.5).mean(), "median week": np.median(wk), "a good week (1 in 10)": np.percentile(wk, 90)}


MIX = json.load(open(os.environ["MIX_FILE"]))
MIX["double-ups (field assumed 5 points tougher)"] = [["Double-up $10 (top 45% doubles)", 1, i] for i in range(30)]
rows = []
for nm, mx in MIX.items():
    for lab, src, arm in (("as armed", S1, "base"), ("+ blended ownership (0.20)", S2, "blend20"), ("+ realized ownership (0.10), the ceiling", S1, "oracle10")):
        r = run([tuple(x) for x in mx], src, arm)
        r.update(mix=nm, book=lab)
        rows.append(r)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 90)
print(pd.DataFrame(rows)[["mix", "book", "weeks ahead", "weeks that lose half or more", "median week", "a good week (1 in 10)"]].round(3).to_string(index=False))
