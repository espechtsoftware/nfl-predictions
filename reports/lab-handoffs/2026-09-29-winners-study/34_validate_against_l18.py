"""My reproduction of the armed main-book form must equal the lab's L18 X50 arm, bank 1240, slate by slate."""
import os, json, glob, numpy as np, pandas as pd
ref = {(r["season"], r["week"]): r for r in (json.loads(l)["result"] for l in open(os.environ["LAB_WT"] + "/results/l18/results_bank1240.jsonl"))}
rows = []
for f in sorted(glob.glob("pct/*.json")):
    s = json.load(open(f)); r = ref[(s["season"], s["week"])]; a = np.array(s["K36"]["score"])
    rows.append({"slate": f"{s['season']}w{s['week']}", "mean": a.mean(), "L18 mean": r["X50_mean"], "t89": int((a >= s["field_q"]["89"]).sum()), "L18 t89": r["X50_tickets89"],
                 "t99": int((a >= s["field_q"]["99"]).sum()), "L18 t99": r["X50_tickets99"]})
D = pd.DataFrame(rows)
print("slates", len(D), "| identical means:", int((abs(D["mean"] - D["L18 mean"]) < 0.01).sum()), "| identical t89:", int((D.t89 == D["L18 t89"]).sum()), "| identical t99:", int((D.t99 == D["L18 t99"]).sum()))
