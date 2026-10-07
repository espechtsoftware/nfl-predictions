"""The graph finding (10-07): within the regulars' portfolios and in the whole field, lineups with more sub-$4,000 non-DST
players hit the top 1% more often in all four weeks. As the operator's PREFERENCE (not a mandate): a bonus of +2 (cheap2) or
+4 (cheap4) projected points for every non-DST player under $4,000. Union bonus file: pred_own = bonus / 0.20."""
import json, sys
from pathlib import Path
import pandas as pd
out = Path(sys.argv[1]); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
for w in (2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id")
    for arm, b in (("cheap2", 2.0), ("cheap4", 4.0)):
        bonus = ((fr.salary < 4000) & fr.pos.isin(["QB", "RB", "WR", "TE"])).astype(float) * b
        pd.DataFrame({"dk_player_id": fr.dk_player_id.astype("Int64"), "display_name": fr.display_name, "pos": fr.pos, "salary": fr.salary,
                      "pred_own": (bonus / 0.20).round(4), "bonus_points": bonus}).to_csv(out / f"{arm}-w{w}.csv", index=False)
    print(f"W{w}: {int(((fr.salary < 4000) & fr.pos.isin(['QB','RB','WR','TE'])).sum())} sub-$4,000 skill players get the bonus")
