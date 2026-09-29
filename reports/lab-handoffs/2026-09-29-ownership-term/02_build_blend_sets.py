"""BLEND_PCT on any sets file: mean(model %, LineStar projected %) where LineStar covers the player (normalized name +
position), the model % alone otherwise. The lab's l15_blend_sets.blend_sets rule, for the base-model files."""
import json, re, sys, glob, os
import numpy as np, pandas as pd
def norm(name):
    s = str(name).lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); s = re.sub(r"[^a-z ]", "", s)
    return " ".join(s.split())
def linestar_slate(payload):
    own = payload.get("Ownership") or {}; sc = json.loads(payload["SalaryContainerJson"])
    mains = [x for x in own.get("Slates", []) if x.get("SlateName") == "Main" and x.get("Mode") == 0]
    sid = mains[0]["Id"]
    proj = {o["SalaryId"]: o["Owned"] for o in (own.get("Projected") or {}).get(str(sid), [])}
    rows = [{"key": norm(r["Name"]), "pos": str(r["POS"]).upper(), "own_proj": float(proj[r["Id"]])} for r in sc["Salaries"] if r["Id"] in proj]
    return pd.DataFrame(rows).drop_duplicates(["key", "pos"])
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
pmap = {tuple(v): int(k) for k, v in json.load(open("lscache/pmap.json")).items()}
cov = []
for f in sorted(glob.glob(f"{src}/*-w*.csv")):
    m = re.match(r"(\d{4})-w(\d{2})\.csv", os.path.basename(f)); season, week = int(m.group(1)), int(m.group(2))
    d = pd.read_csv(f); ls = linestar_slate(json.load(open(f"lscache/p{pmap[(season, week)]}.json")))
    d["key"] = d.display_name.map(norm); d["pos"] = d.pos.astype(str).str.upper()
    d = d.merge(ls, on=["key", "pos"], how="left")
    c = d.own_proj.notna()
    d["model_own"] = d.pred_own.astype(float)
    d["pred_own"] = np.where(c, (d.model_own + d.own_proj.fillna(0)) / 2.0, d.model_own)
    d[["gsis_id", "id", "display_name", "pos", "team", "salary", "proj", "pred_own", "model_own", "own_proj"]].to_csv(f"{out}/{season}-w{week:02d}.csv", index=False)
    cov.append(c.sum())
print(len(cov), "files ->", out, "| LineStar-covered players per slate:", round(float(np.mean(cov)), 1))
